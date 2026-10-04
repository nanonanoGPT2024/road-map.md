# Bab 01: Fondasi Arsitektur & Core Engine React
## Modul 01: Paradigma Komputasi UI Deklaratif, Virtual DOM, dan Rekonsiliasi Fiber

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

*   **Menganalisis (Analyze)** secara komparatif model komputasi rendering imperatif browser DOM versus arsitektur rekonsiliasi deklaratif React.
*   **Mendekonstruksi (Deconstruct)** struktur data internal `FiberNode`, termasuk pointer graf navigasi (`child`, `sibling`, `return`, `alternate`) dan perannya dalam fase rendering.
*   **Mengimplementasikan (Implement)** pipeline rendering berbasis konsep komputasi *double buffering* dan kooperatif penjadwalan (*cooperative scheduling*) untuk mencegah *frame drops*.
*   **Mendiagnosis (Diagnose)** anomali rendering seperti *layout thrashing*, siklus *render cascading*, dan kebocoran memori akibat penanganan referensi objek yang salah pada fase *commit*.
*   **Mengevaluasi (Evaluate)** trade-off performa antara strategi dirty-checking, fine-grained reactivity, dan Virtual DOM diffing berbasis heuristik $O(n)$.

---

### 2. Conceptual Foundation

Secara fundamental, antarmuka pengguna modern adalah representasi proyeksi visual dari status aplikasi (*application state*) pada satu titik waktu tertentu:

$$UI = f(\text{state})$$

Di mana:
*   $\text{state}$ merepresentasikan struktur data deterministik pada layer aplikasi (memori heap).
*   $f$ adalah fungsi proyeksi idempotent yang mengubah input data menjadi pohon representasi visual.
*   $UI$ adalah realisasi grafis pada layar pengguna.

Dalam model imperatif tradisional (misalnya via manipulasi langsung W3C Document Object Model / DOM), pengembang bertanggung jawab memetakan setiap mutasi status $\Delta \text{state}$ menjadi serangkaian mutasi DOM granular $\Delta \text{DOM}$:

$$\text{state}_0 \xrightarrow{\Delta \text{state}} \text{state}_1 \implies \text{DOM}_0 \xrightarrow{\Delta \text{DOM}} \text{DOM}_1$$

Model ini rentan terhadap kesalahan (*error-prone*) dan memiliki kompleksitas $O(M \times N)$, di mana $M$ adalah jumlah mutasi status dan $N$ adalah jumlah node DOM target.

React mengabstraksi mekanisme ini menjadi model **deklaratif**. Pengembang hanya mendefinisikan bentuk akhir UI yang diinginkan untuk status tertentu ($\text{state}_1$). React Engine kemudian bertindak sebagai mesin komputasi diferensial runtime yang mengevaluasi:

$$\Delta \text{DOM} = \text{Reconcile}(f(\text{state}_0), f(\text{state}_1))$$

Komputasi ini menerapkan prinsip **Double Buffering** dari grafika komputer: perubahan dihitung pada representasi struktur data in-memory terisolasi (Virtual DOM/Fiber Tree) sebelum disinkronisasikan ke target tampilan fisik (Real DOM) dalam satu siklus flush atomik.

---

### 3. Why This Matters

DOM W3C bawaan browser tidak didesain untuk aplikasi satu halaman (*Single Page Applications*) dengan throughput data tinggi. Akses dan manipulasi DOM membawa overhead performa yang signifikan:

1.  **Reflow dan Repaint Overhead**: Setiap pembacaan dimensi DOM (misalnya `offsetWidth`) setelah penulisan DOM (misalnya `element.style.width`) memicu *Forced Synchronous Layout* (Layout Thrashing). Jika dilakukan secara berulang dalam satu *frame budget* (16.67ms untuk 60 FPS, atau 8.33ms untuk 120 FPS), thread utama (*Main Thread*) browser akan mengalami pemblokiran (*jank*).
2.  **State Synchronization Desynchronization**: Pada arsitektur imperatif berskala besar, risiko hilangnya sinkronisasi (*state drift*) antara data internal JavaScript dan status visual native DOM meningkat secara eksponensial seiring pertambahan event asinkron (WebSocket, interaksi pengguna, timer).

Virtual DOM dan mesin rekonsiliasi Fiber memecahkan masalah ini dengan memindahkan proses diferensiasi struktural ke alokasi memori heap murni dalam thread JavaScript yang sangat cepat, meminimalkan operasi I/O native DOM ke jumlah seminimal mungkin secara terkelompok (*batched writes*).

---

### 4. What It Is: Deep Architecture

React Fiber Engine adalah implementasi ulang dari algoritma inti rekonsiliasi React. Inti dari Fiber adalah **struktur data linked-list berbasis tumpukan panggilan virtual (*virtual stack frame*)** yang memungkinkan React menjeda, membatalkan, atau memprioritaskan ulang pekerjaan komputasi pohon komponen.

#### Anatomi FiberNode

Sebuah `FiberNode` adalah objek JavaScript standar yang merepresentasikan unit kerja (*unit of work*). Struktur dasarnya mencakup pointer navigasi dan field status:

```typescript
interface FiberNode {
  // Tag identifikasi tipe unit kerja (FunctionComponent, ClassComponent, HostComponent, dll)
  tag: WorkTag;
  
  // Identifier unik untuk pencocokan elemen antar-render
  key: null | string;
  
  // Tipe elemen (misal: 'div', fungsi komponen MyComponent)
  elementType: any;
  type: any;
  
  // Referensi ke instance native (DOM Node) atau instance komponen
  stateNode: any;

  // Pointer Navigasi Pohon (Singly Linked List)
  return: FiberNode | null;     // Pointer ke parent Fiber
  child: FiberNode | null;      // Pointer ke anak pertama
  sibling: FiberNode | null;    // Pointer ke saudara kandung berikutnya
  index: number;

  // Payload Props dan State
  pendingProps: any;            // Props baru yang akan diproses
  memoizedProps: any;           // Props yang digunakan untuk menghasilkan output saat ini
  memoizedState: any;           // State saat ini (linked-list dari hook state)
  updateQueue: unknown;         // Antrean mutasi status

  // Efek Samping dan Mutasi
  flags: Flags;                 // Bitmask efek DOM (Placement, Update, Deletion)
  subtreeFlags: Flags;          // Bitmask agregasi efek dari seluruh turunan

  // Double Buffering
  alternate: FiberNode | null;  // Pointer ke Fiber kembaran di pohon alternatif
  
  // Prioritas Penjadwalan (Lanes Architecture)
  lanes: Lanes;
  childLanes: Lanes;
}
```

#### Siklus Double Buffering

React mempertahankan dua instansiasi struktur data pohon Fiber secara paralel:
1.  **`current` Tree**: Merepresentasikan status UI yang sedang aktif dirender pada Real DOM layar saat ini.
2.  **`workInProgress` (WIP) Tree**: Pohon yang sedang dirakit dan dikalkulasi secara inkremental pada memori latar belakang selama fase *render*.

Pointer `alternate` menghubungkan node yang bersesuaian di antara kedua pohon ini:
`current.alternate === workInProgress` dan `workInProgress.alternate === current`.

Ketika mutasi selesai dikomputasi, React cukup mengubah satu pointer referensi tingkat atas (*root pointer*):

$$\text{FiberRoot.current} \leftarrow \text{workInProgress}$$

Proses penggantian pointer ini bersifat atomik, instan ($O(1)$), dan mencegah visual inkonsisten (*tearing*) terlihat oleh pengguna akhir.

---

### 5. How It Works: The Execution Lifecycle

Siklus eksekusi React terbagi menjadi dua fase utama yang memiliki karakteristik eksekusi berbeda secara fundamental:

```
[Trigger Update] 
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Phase 1: Render Phase (Asynchronous, Interruptible)    │
│ 1. Scheduler menentukan prioritas tugas (Lanes)        │
│ 2. workLoopConcurrent() memproses unit kerja           │
│ 3. beginWork() mengevaluasi diffing & hook             │
│ 4. completeWork() merakit struktur DOM in-memory       │
│    dan mengumpulkan 'flags' mutasi                     │
└────────────────────────────────────────────────────────┘
       │
       │ (WIP Tree siap & diverifikasi)
       ▼
┌────────────────────────────────────────────────────────┐
│ Phase 2: Commit Phase (Synchronous, Uninterruptible)   │
│ 1. Before Mutation Phase (pembacaan getSnapshotBefore) │
│ 2. Mutation Phase (Penulisan ke Real DOM, flags reset) │
│ 3. Layout Phase (Eksekusi useLayoutEffect, ref attach) │
│ 4. Swap Root: Root.current = workInProgress            │
└────────────────────────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Post-Commit: Passive Effects (useEffect callbacks)     │
└────────────────────────────────────────────────────────┘
```

#### 1. Fase Render (Rekonsiliasi)
*   **Sifat**: Asinkron, dapat dijeda (*interruptible*), dan dapat dibatalkan sewaktu-waktu jika ada tugas berprioritas lebih tinggi masuk (misalnya, input ketikan pengguna menginterupsi transisi data besar).
*   **Operasi**:
    *   `performUnitOfWork(fiber)` dipanggil secara berulang dalam loop kooperatif.
    *   `beginWork(current, workInProgress, renderLanes)`: Membandingkan props/state. Jika node tidak berubah dan prioritas tidak mendesak, proses traversal dapat memotong (*bailout*) subtree tersebut tanpa komputasi ulang.
    *   Jika anak ditemukan, fungsi mengembalikan `fiber.child`. Jika mencapai daun (*leaf node*), fungsi mengeksekusi `completeUnitOfWork(fiber)`.
    *   `completeWork()`: Mempersiapkan instance node DOM in-memory dan menggelembungkan (*bubble up*) flag mutasi (`subtreeFlags`) ke parent.

#### 2. Heuristik Diffing ($O(n)$)
React tidak menggunakan algoritma pembandingan pohon generik (seperti Levenshtein tree edit distance yang beroperasi pada $O(n^3)$). Sebagai gantinya, React mengadopsi tiga asumsi heuristik deterministik untuk menekan kompleksitas menjadi linear $O(n)$:
1.  **Tipe Elemen Berbeda Menghasilkan Subtree Berbeda**: Jika elemen root berubah dari `<div />` menjadi `<span />`, React akan menghancurkan (*unmount*) seluruh pohon lama beserta status internalnya dan membangun pohon baru dari awal.
2.  **Identitas Kunci Stabil (`key`)**: Elemen anak dalam daftar koleksi mempertahankan identitasnya lintas render melalui prop `key` string/unik. Reordering tidak memicu rekonstruksi DOM, melainkan sekadar relokasi posisi (*reordering pointer*).
3.  **Level Traversal Terisolasi**: React hanya membandingkan node-node pada kedalaman graf yang sama (*breadth-first per level*). Tidak ada rekursi perbandingan menyilang antar level pohon hierarki yang berbeda.

#### 3. Fase Commit
*   **Sifat**: Sinkron dan tidak dapat diinterupsi (*uninterruptible*). Sekali dimulai, thread browser tidak boleh diputus sampai seluruh operasi DOM selesai untuk mencegah inkonsistensi rendering UI visual.
*   **Sub-tahap**:
    *   *Before Mutation*: DOM belum disentuh; aman membaca status baca-saja layout.
    *   *Mutation*: Operasi W3C DOM seperti `appendChild`, `removeChild`, dan `setAttribute` dieksekusi secara masif berdasarkan flag yang dikumpulkan selama fase render.
    *   *Layout*: Node DOM baru sudah berada di tree browser. React memicu callback layout sinkron seperti hook `useLayoutEffect`.

---

### 6. Architecture & Data Flow Diagram

Diagram berikut mengilustrasikan transisi state dari status pohon berjalan (*current*) ke pohon perakitan latar belakang (*workInProgress*) menggunakan skema navigasi pointer Fiber:

```
                  FIBER ROOT (ContainerInfo: #root)
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │       FiberRootNode       │
                    │   current: [Pointer] ────┼───────┐
                    └─────────────┬─────────────┘       │
                                  │                     │
                CURRENT TREE      │                     │   WORK-IN-PROGRESS TREE
                                  ▼                     ▼
                           ┌─────────────┐       ┌─────────────┐
                           │   HostRoot  │◄═════►│   HostRoot  │ (WIP)
                           └──────┬──────┘       └──────┬──────┘
                                  │ child               │ child
                                  ▼                     ▼
                           ┌─────────────┐       ┌─────────────┐
                    ┌─────►│  App (div)  │◄═════►│  App (div)  │ (WIP)
                    │      └──────┬──────┘       └──────┬──────┘
                    │             │ child               │ child
     return pointer │             ▼                     ▼
                    │      ┌─────────────┐       ┌─────────────┐
                    └──────┤  Sidebar    │◄═════►│  Sidebar    │ (Clone/Bailout)
                           └──────┬──────┘       └──────┬──────┘
                                  │ sibling             │ sibling
                                  ▼                     ▼
                           ┌─────────────┐       ┌─────────────┐
                           │   Content   │◄═════►│   Content   │ (Flags: Update)
                           └─────────────┘       └─────────────┘
                                  ▲                     ▲
                                  ╚═════════════════════╝
                                      alternate pointer
```

---

### 7. Minimal Implementation (From Scratch)

Berikut adalah implementasi instruksional minimal mesin reaktif berbasis Fiber, algoritma diffing sederhana, dan penjadwalan kooperatif menggunakan API native `requestIdleCallback`.

```javascript
// mini-react.js
(function () {
  // Representasi tipe efek
  const PLACEMENT = 1;
  const UPDATE = 2;
  const DELETION = 3;

  let nextUnitOfWork = null;
  let wipRoot = null;
  let currentRoot = null;
  let deletions = [];

  function createElement(type, props, ...children) {
    return {
      type,
      props: {
        ...props,
        children: children.flat().map((child) =>
          typeof child === "object" ? child : createTextElement(child)
        ),
      },
    };
  }

  function createTextElement(text) {
    return {
      type: "TEXT_ELEMENT",
      props: {
        nodeValue: text,
        children: [],
      },
    };
  }

  function createDom(fiber) {
    const dom =
      fiber.type === "TEXT_ELEMENT"
        ? document.createTextNode("")
        : document.createElement(fiber.type);

    updateDom(dom, {}, fiber.props);
    return dom;
  }

  const isEvent = (key) => key.startsWith("on");
  const isProperty = (key) => key !== "children" && !isEvent(key);
  const isGone = (prev, next) => (key) => !(key in next);
  const isNew = (prev, next) => (key) => prev[key] !== next[key];

  function updateDom(dom, prevProps, nextProps) {
    // Hapus listener event lama
    Object.keys(prevProps)
      .filter(isEvent)
      .filter((key) => !(key in nextProps) || isNew(prevProps, nextProps)(key))
      .forEach((name) => {
        const eventType = name.toLowerCase().substring(2);
        dom.removeEventListener(eventType, prevProps[name]);
      });

    // Hapus properti lama
    Object.keys(prevProps)
      .filter(isProperty)
      .filter(isGone(prevProps, nextProps))
      .forEach((name) => {
        dom[name] = "";
      });

    // Setel properti baru atau yang diperbarui
    Object.keys(nextProps)
      .filter(isProperty)
      .filter(isNew(prevProps, nextProps))
      .forEach((name) => {
        dom[name] = nextProps[name];
      });

    // Tambah listener event baru
    Object.keys(nextProps)
      .filter(isEvent)
      .filter(isNew(prevProps, nextProps))
      .forEach((name) => {
        const eventType = name.toLowerCase().substring(2);
        dom.addEventListener(eventType, nextProps[name]);
      });
  }

  function commitRoot() {
    deletions.forEach(commitWork);
    commitWork(wipRoot.child);
    currentRoot = wipRoot;
    wipRoot = null;
  }

  function commitWork(fiber) {
    if (!fiber) return;

    let domParentFiber = fiber.return;
    while (!domParentFiber.dom) {
      domParentFiber = domParentFiber.return;
    }
    const domParent = domParentFiber.dom;

    if (fiber.effectTag === PLACEMENT && fiber.dom != null) {
      domParent.appendChild(fiber.dom);
    } else if (fiber.effectTag === UPDATE && fiber.dom != null) {
      updateDom(fiber.dom, fiber.alternate.props, fiber.props);
    } else if (fiber.effectTag === DELETION) {
      commitDeletion(fiber, domParent);
      return;
    }

    commitWork(fiber.child);
    commitWork(fiber.sibling);
  }

  function commitDeletion(fiber, domParent) {
    if (fiber.dom) {
      domParent.removeChild(fiber.dom);
    } else {
      commitDeletion(fiber.child, domParent);
    }
  }

  function render(element, container) {
    wipRoot = {
      dom: container,
      props: {
        children: [element],
      },
      alternate: currentRoot,
      child: null,
      sibling: null,
      return: null,
    };
    deletions = [];
    nextUnitOfWork = wipRoot;
  }

  function workLoop(deadline) {
    let shouldYield = false;
    while (nextUnitOfWork && !shouldYield) {
      nextUnitOfWork = performUnitOfWork(nextUnitOfWork);
      shouldYield = deadline.timeRemaining() < 1;
    }

    if (!nextUnitOfWork && wipRoot) {
      commitRoot();
    }

    requestIdleCallback(workLoop);
  }

  requestIdleCallback(workLoop);

  function performUnitOfWork(fiber) {
    const isFunctionComponent = fiber.type instanceof Function;
    if (isFunctionComponent) {
      updateFunctionComponent(fiber);
    } else {
      updateHostComponent(fiber);
    }

    if (fiber.child) {
      return fiber.child;
    }
    let nextFiber = fiber;
    while (nextFiber) {
      if (nextFiber.sibling) {
        return nextFiber.sibling;
      }
      nextFiber = nextFiber.return;
    }
    return null;
  }

  function updateFunctionComponent(fiber) {
    const children = [fiber.type(fiber.props)];
    reconcileChildren(fiber, children);
  }

  function updateHostComponent(fiber) {
    if (!fiber.dom) {
      fiber.dom = createDom(fiber);
    }
    reconcileChildren(fiber, fiber.props.children);
  }

  function reconcileChildren(wipFiber, elements) {
    let index = 0;
    let oldFiber = wipFiber.alternate && wipFiber.alternate.child;
    let prevSibling = null;

    while (index < elements.length || oldFiber != null) {
      const element = elements[index];
      let newFiber = null;

      const sameType = oldFiber && element && element.type === oldFiber.type;

      if (sameType) {
        newFiber = {
          type: oldFiber.type,
          props: element.props,
          dom: oldFiber.dom,
          return: wipFiber,
          alternate: oldFiber,
          effectTag: UPDATE,
        };
      }
      if (element && !sameType) {
        newFiber = {
          type: element.type,
          props: element.props,
          dom: null,
          return: wipFiber,
          alternate: null,
          effectTag: PLACEMENT,
        };
      }
      if (oldFiber && !sameType) {
        oldFiber.effectTag = DELETION;
        deletions.push(oldFiber);
      }

      if (oldFiber) {
        oldFiber = oldFiber.sibling;
      }

      if (index === 0) {
        wipFiber.child = newFiber;
      } else if (element) {
        prevSibling.sibling = newFiber;
      }

      prevSibling = newFiber;
      index++;
    }
  }

  window.MiniReact = { createElement, render };
})();
```

---

### 8. Real-World Production Scenario

#### Kasus: Dashboard Pemantauan Order Book Finansial Frekuensi Tinggi (High-Frequency Trading)
Pada sistem pemantauan bursa efek, aliran data WebSocket mentransmisikan hingga 5.000 pembaruan harga per detik. 

**Kegagalan Sistem yang Kerap Terjadi**:
Jika aplikasi React langsung memicu `setState` pada setiap paket data WebSocket yang masuk:
1.  Fase rekonsiliasi dipicu 5.000 kali per detik.
2.  React tidak sempat menyelesaikan fase render sebelum frame berikutnya tiba, menyebabkan antrean mikro-tugas (*microtask queue*) meluap.
3.  Thread utama terblokir penuh (100% CPU core utilization), memicu UI unresponsive, frame rate anjlok hingga 0-5 FPS, dan input pengguna (seperti pembatalan order darurat) tidak dieksekusi oleh browser.

**Solusi Arsitektural**:
Menerapkan isolasi state frekuensi tinggi dari siklus render sinkron, menggunakan teknik *sliding window buffer*, memanfaatkan React 18 Concurrent Primitives (`useDeferredValue` atau `startTransition`), serta mengontrol mutasi DOM tabular menggunakan identitas `key` yang stabil untuk mengoptimalkan heuristik algoritma rekonsiliasi.

---

### 9. Practical Implementation

Komponen produksi berikut menangani aliran volume data pesat secara deterministik tanpa membekukan thread utama browser:

```tsx
import React, { useState, useEffect, useTransition, useMemo, memo } from "react";

export interface OrderBookEntry {
  readonly id: string;
  readonly price: number;
  readonly volume: number;
  readonly timestamp: number;
}

interface OrderBookProps {
  readonly streamUrl: string;
}

// Komponen baris tabel di-memoize untuk mencegah re-render jika props tidak bermutasi
const OrderRow = memo(function OrderRow({ entry }: { readonly entry: OrderBookEntry }) {
  return (
    <tr className="border-b border-neutral-800 font-mono text-sm hover:bg-neutral-900">
      <td className="px-4 py-2 text-left text-neutral-400">{entry.id}</td>
      <td className="px-4 py-2 text-right text-emerald-400">
        {entry.price.toFixed(2)}
      </td>
      <td className="px-4 py-2 text-right text-neutral-200">
        {entry.volume.toFixed(4)}
      </td>
      <td className="px-4 py-2 text-right text-neutral-500">
        {new Date(entry.timestamp).toISOString().substring(11, 23)}
      </td>
    </tr>
  );
});

export const HighThroughputOrderBook: React.FC<OrderBookProps> = ({ streamUrl }) => {
  // Master state lokal: menampung snapshot terkomitmen
  const [orders, setOrders] = useState<ReadonlyMap<string, OrderBookEntry>>(new Map());
  const [filterThreshold, setFilterThreshold] = useState<number>(0);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    // Ring buffer lokal untuk menahan throughput tinggi sebelum batch flush
    let backpressureBuffer: OrderBookEntry[] = [];
    let animationFrameId: number;

    const flushBufferToState = () => {
      if (backpressureBuffer.length > 0) {
        const bufferedData = [...backpressureBuffer];
        backpressureBuffer = [];

        // Menggunakan startTransition agar rekonsiliasi daftar besar tidak memblokir input UI
        startTransition(() => {
          setOrders((prevMap) => {
            const nextMap = new Map(prevMap);
            for (let i = 0; i < bufferedData.length; i++) {
              const item = bufferedData[i];
              nextMap.set(item.id, item);
            }
            // Batasi ukuran map maksimum 500 baris untuk membatasi footprint memori VDOM
            if (nextMap.size > 500) {
              const keysToDelete = Array.from(nextMap.keys()).slice(0, nextMap.size - 500);
              for (const k of keysToDelete) {
                nextMap.delete(k);
              }
            }
            return nextMap;
          });
        });
      }
      animationFrameId = requestAnimationFrame(flushBufferToState);
    };

    // Simulasi atau inisiasi WebSocket stream
    const ws = new WebSocket(streamUrl);
    ws.binaryType = "arraybuffer";

    ws.onmessage = (event: MessageEvent) => {
      try {
        const rawPayload: OrderBookEntry = JSON.parse(event.data as string);
        backpressureBuffer.push(rawPayload);
      } catch (err) {
        console.error("Payload parse error:", err);
      }
    };

    // Jalankan consumer loop sinkron dengan refresh rate browser (60Hz/120Hz)
    animationFrameId = requestAnimationFrame(flushBufferToState);

    return () => {
      ws.close();
      cancelAnimationFrame(animationFrameId);
      backpressureBuffer = [];
    };
  }, [streamUrl]);

  // Derived filtered state yang terisolasi dari re-render yang tidak relevan
  const displayOrders = useMemo(() => {
    const list: OrderBookEntry[] = [];
    orders.forEach((val) => {
      if (val.volume >= filterThreshold) {
        list.push(val);
      }
    });
    return list.sort((a, b) => b.price - a.price);
  }, [orders, filterThreshold]);

  return (
    <div className="flex flex-col h-full w-full bg-black text-white p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold tracking-tight">Order Execution Engine</h1>
        <div className="flex items-center space-x-4">
          {isPending && (
            <span className="text-xs text-amber-500 animate-pulse">
              Reconciling Tree...
            </span>
          )}
          <label className="text-sm text-neutral-400">
            Min Volume:
            <input
              type="number"
              value={filterThreshold}
              onChange={(e) => setFilterThreshold(Number(e.target.value))}
              className="ml-2 bg-neutral-900 border border-neutral-700 px-2 py-1 rounded text-white"
            />
          </label>
        </div>
      </div>

      <div className="overflow-y-auto border border-neutral-800 rounded-lg max-h-[600px]">
        <table className="w-full border-collapse">
          <thead className="bg-neutral-900 sticky top-0">
            <tr>
              <th className="px-4 py-3 text-left text-xs text-neutral-400 font-semibold">ID</th>
              <th className="px-4 py-3 text-right text-xs text-neutral-400 font-semibold">PRICE</th>
              <th className="px-4 py-3 text-right text-xs text-neutral-400 font-semibold">VOLUME</th>
              <th className="px-4 py-3 text-right text-xs text-neutral-400 font-semibold">TIMESTAMP</th>
            </tr>
          </thead>
          <tbody>
            {displayOrders.map((entry) => (
              // KRITIKAL: ID stabil menjamin algoritma rekonsiliasi mengeksekusi UPDATE,
              // bukan DELETION + PLACEMENT secara konstan
              <OrderRow key={entry.id} entry={entry} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
```

---

### 10. Critical Edge Cases

#### 1. Mutasi Objek State In-Place (Reference Identity Hazard)
```typescript
// ERROR: Mutasi in-place tidak menghasilkan referensi objek baru
const [user, setUser] = useState({ name: "Alice", meta: { unread: 0 } });
user.meta.unread += 1;
setUser(user); 
// Dampak: React mengevaluasi `Object.is(prevUser, nextUser) === true` pada beginWork().
// Rekonsiliasi subtree di-bailout, UI tidak pernah terupdate di layar.
```

#### 2. Key Mutasi Acak (*Unstable Keys Trap*)
```tsx
// FATAL: Menggunakan Math.random() atau UUID yang digenerate sewaktu render
{items.map((item) => (
  <ListItem key={Math.random()} data={item} />
))}
// Dampak: Rekonsiliator berasumsi seluruh hierarki berubah total pada SETIAP render.
// Semua node DOM lama dihapus dan dibangun ulang. State lokal komponen anak lenyap,
// fokus input hilang, dan beban alokasi GC (Garbage Collection) melonjak drastis.
```

#### 3. State Update Loop Tak Berujung dalam Layout Phase
```typescript
useLayoutEffect(() => {
  // Bahaya: Dijalankan sinkron SEBELUM browser melukis (paint).
  // Memicu setState di sini memaksa React menjadwalkan ulang fase render
  // dan memproses rekonsiliasi ulang secara instan, memblokir thread hingga browser crash.
  setHeight(ref.current.getBoundingClientRect().height);
}, [height]);
```

---

### 11. Performance Characteristics

#### Kompleksitas Teoretis dan Empiris
| Operasi | Kompleksitas Waktu | Alokasi Ruang / Memori | Keterangan |
| :--- | :--- | :--- | :--- |
| **Heuristic Tree Diffing** | $O(N)$ | $O(N)$ | $N$ adalah jumlah total node dalam pohon aktif. |
| **Bailout Subtree Check** | $O(1)$ | $O(0)$ | Pengecekan kesamaan referensi pointer props/state. |
| **Commit Mutation Pass** | $O(M)$ | $O(1)$ | $M$ adalah jumlah node terindikasi `flags` mutasi ($M \le N$). |
| **List Key Lookup** | $O(K)$ | $O(K)$ | $K$ adalah ukuran array anak; map hashing instan via key. |

#### Alokasi Memori
Setiap instansiasi `FiberNode` memerlukan sekitar 400 hingga 900 byte memori JavaScript heap tergantung arsitektur browser V8. Dalam aplikasi berskala *enterprise* dengan $10.000$ komponen aktif, keberadaan dua pohon paralel (`current` dan `workInProgress`) dapat menempati sekitar 10MB hingga 25MB memori hanya untuk representasi graf Virtual DOM dasar, di luar data pengguna.

---

### 12. Memory & Resource Management

1.  **Dangling Closures pada Unmounted Fibers**:
    Event listener atau subscription yang tidak dibersihkan saat fase unmount (`return () => cleanup()` pada `useEffect`) mempertahankan referensi ke Fiber scope induknya, mencegah V8 Garbage Collector membersihkan seluruh subtree Fiber tersebut (*Detached Fiber Node Leak*).
2.  **Detached DOM Trees**:
    Menyimpan referensi manual elemen DOM (misalnya via variabel global atau closure di luar React) yang telah dihapus oleh fase commit React akan menyebabkan *Detached Window/Node Memory Leak*. Elemen tersebut tetap hidup di heap C++ browser bersama seluruh struktur data yang terikat.

```typescript
// PENANGANAN LEAK SECARA BENAR
useEffect(() => {
  const handler = () => { /* ... */ };
  window.addEventListener("resize", handler);
  return () => {
    // WAJIB: Memutus rantai closure agar Garbage Collector dapat membersihkan memory
    window.removeEventListener("resize", handler);
  };
}, []);
```

---

### 13. Anti-Patterns & Pitfalls

#### Anti-Pattern: Penggunaan Indeks Array Sebagai `key`
Saat urutan array berubah (misal: penyisipan di posisi pertama), algoritma rekonsiliasi salah memetakan indeks ke node DOM yang salah.

##### Kode Bermasalah:
```tsx
// BURUK: Menyebabkan anomali state visual pada input field
{todos.map((todo, index) => (
  <TodoItem key={index} title={todo.title} />
))}
```

##### Kode Solusi:
```tsx
// BENAR: Menggunakan identifier permanen dan unik dari data domain
{todos.map((todo) => (
  <TodoItem key={todo.uuid} title={todo.title} />
))}
```

#### Komparasi Perilaku Mutasi:
```
Status Awal:   [ItemA (key: 0), ItemB (key: 1)]
Operasi:       Unshift ItemC ke awal array

Menggunakan INDEX:
Pohon Baru:    [ItemC (key: 0), ItemA (key: 1), ItemB (key: 2)]
Diffing:       Node 0 (A -> C) UPDATE DOM! Node 1 (B -> A) UPDATE DOM! Node 2 INSERT DOM!
Hasil:         3 Mutasi DOM berat. State lokal Input Node 0 menetap di ItemC.

Menggunakan IDENTIFIER STABIL:
Pohon Baru:    [ItemC (key: 'c'), ItemA (key: 'a'), ItemB (key: 'b')]
Diffing:       Node 'c' PLACEMENT! Node 'a' & 'b' TIDAK BERUBAH (Bailout).
Hasil:         1 Mutasi DOM ringan (Insert Before). State lokal terisolasi sempurna.
```

---

### 14. Automated Testing Strategy

Pengujian mekanisme rendering internal harus berfokus pada verifikasi stabilitas komitmen DOM tanpa terpapar detail implementasi privat.

```typescript
// OrderBook.test.tsx
import React from "react";
import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { HighThroughputOrderBook } from "./HighThroughputOrderBook";

describe("HighThroughputOrderBook Reconciliation Tests", () => {
  let mockServer: any;

  beforeEach(() => {
    // Mock WebSocket global
    class MockWebSocket {
      public onmessage: ((ev: any) => void) | null = null;
      public close = vi.fn();
      public binaryType = "arraybuffer";
      constructor(public url: string) {
        setTimeout(() => {
          // Push payload awal
          this.onmessage?.({
            data: JSON.stringify({
              id: "order-1",
              price: 100.5,
              volume: 1.25,
              timestamp: Date.now(),
            }),
          });
        }, 10);
      }
    }
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("mempertahankan integritas DOM saat reconciler memproses data batching", async () => {
    render(<HighThroughputOrderBook streamUrl="ws://localhost:8080" />);

    // Verifikasi initial loading state
    const orderCell = await screen.findByText("100.50");
    expect(orderCell).toBeDefined();

    // Verifikasi bahwa elemen baris DOM mempertahankan instance referensinya
    const initialRowElement = screen.getByText("order-1").closest("tr");

    // Simulasi update tick berikutnya
    act(() => {
      // Trigger requestAnimationFrame tick manual jika di-mock
    });

    const activeRowElement = screen.getByText("order-1").closest("tr");
    // Pointer integritas: elemen DOM tidak boleh di-destroy jika key konstan
    expect(initialRowElement).toBe(activeRowElement);
  });
});
```

---

### 15. Observability & Debugging

Untuk memantau fase rekonsiliasi dan mendeteksi rendering berlebih (*wasted renders*) secara runtime di lingkungan produksi:

#### 1. React Profiler API Programatik
```tsx
import React, { Profiler, ProfilerOnRenderCallback } from "react";

const onRenderCallback: ProfilerOnRenderCallback = (
  id, // id pohon Profiler yang diukur
  phase, // "mount" atau "update"
  actualDuration, // Waktu komputasi render phase (Fiber diffing)
  baseDuration, // Estimasi waktu render tanpa memoization
  startTime, // Titik waktu React mulai rendering
  commitTime // Titik waktu React me-commit perubahan ke DOM
) => {
  if (actualDuration > 16.0) {
    // Frame budget terlampaui (Jank terdeteksi)
    console.warn(`[Profiling Alert] Component ${id} took ${actualDuration}ms to render in phase: ${phase}`);
    // Kirim telemetri ke OpenTelemetry / Datadog
  }
};

export const MonitoredView = () => (
  <Profiler id="OrderBookRoot" onRender={onRenderCallback}>
    <HighThroughputOrderBook streamUrl="wss://trade.internal/feed" />
  </Profiler>
);
```

#### 2. Pelacakan Layout Thrashing via Chrome Tracing
*   Jalankan Chrome DevTools $\rightarrow$ Panel **Performance**.
*   Nyalakan opsi **Screenshots** dan **Web Vitals**.
*   Cari garis penanda berwarna merah pada baris *Main Thread* berlabel **Long Task** (> 50ms) atau **Recalculate Style** berulang dengan penanda ungu (*Forced Synchronous Layout*).

---

### 16. Trade-off Matrix

| Dimensi Arsitektural | Virtual DOM (React Fiber) | Fine-Grained Signals (SolidJS) | Compile-Time Reactive (Svelte 5) | Manipulasi Direct Imperatif (Vanilla JS) |
| :--- | :--- | :--- | :--- | :--- |
| **Pendekatan Runtime** | Runtime reconciliation via tree diffing | Direct graph dependency subscription | Compiler-generated code; minimal runtime | Manual W3C DOM calls |
| **Alokasi Memori Heap** | Tinggi (Mempertahankan 2 graf Fiber in-memory) | Sangat Rendah (Hanya signal subscriber closures) | Rendah (Hanya flat variables) | Terendah (Hanya native DOM wrappers) |
| **Throughput Mutasi Granular** | Menengah (Dibatasi overhead diffing dan batching) | Ekstrem (O(1) langsung ke node target spesifik) | Sangat Tinggi (Direct mutation via generated code) | Teoretis Tertinggi (Jika dioptimasi sempurna secara manual) |
| **Developer Ergonomics** | Deklaratif murni, mental model bebas dependensi | Reaktif granular, aturan tracking ketat | Sintaks intuitif, compiler overhead | Kompleks, rawan layout thrashing & state drift |
| **Interupsi Prioritas Render** | Didukung (Concurrent Lane Architecture) | Tidak (Synchronous propagate by default) | Terbatas | Harus dirancang manual sepenuhnya |

---

### 17. Production Checklist

1.  [ ] **Key Stability Audit**: Pastikan tidak ada list rendering yang menggunakan array index atau random generated values sebagai prop `key`.
2.  [ ] **Reference Boundary Check**: Pastikan props yang dipassing ke child components yang di-`memo` tidak dibuat ulang secara inline (`useCallback` / `useMemo`).
3.  [ ] **DOM Node Count Budget**: Batasi jumlah total node W3C DOM di layar tidak melebihi 1.500 node secara bersamaan (terapkan virtualisasi daftar/windowing).
4.  [ ] **Side-Effect Purity**: Pastikan fungsi render komponen bersifat idempotensial tanpa efek samping ke luar (*zero side effects during render phase*).
5.  [ ] **Layout Effect Containment**: Batasi penggunaan `useLayoutEffect` hanya untuk kalkulasi geometri layout sebelum melukis; gunakan `useEffect` untuk semua tugas non-geometri.
6.  [ ] **Batching Strategy**: Verifikasi batching mutasi state berkecepatan tinggi menggunakan event queue throttling atau `startTransition`.
7.  [ ] **Memory Disconnection**: Implementasikan destructor cleanup untuk setiap interval, timer, subscription WebSocket, dan native listener.
8.  [ ] **Profiler Budget Tracing**: Jalankan profiling berkala; tetapkan budget bahwa waktu komputasi render phase tidak boleh melampaui ambang 8ms pada perangkat mobile standar.
9.  [ ] **Tree Depth Enforcement**: Hindari nesting komponen melebihi 30 level hierarki untuk menghindari kedalaman stack rekursi traversi Fiber yang berlebihan.
10. [ ] **Production Build Assertion**: Pastikan `process.env.NODE_ENV === 'production'` aktif untuk membuang seluruh verifikasi runtime internal development yang memperlambat engine hingga 3-5x lipat.

---

### 18. Enterprise Case Study

#### Permasalahan: Kegagalan Latensi Eksekusi pada Dasbor Trading Global
Sebuah platform manajemen likuiditas multinasional menghadapi masalah kritis: Pada saat terjadi volatilitas pasar yang tinggi, antarmuka web mengalami *unresponsiveness* selama 1,2 detik hingga 3,4 detik secara berkala. Analisis *thread flame chart* menunjukkan thread utama terkunci penuh akibat proses rekonsiliasi yang membengkak di lebih dari 8.000 komponen DOM secara bersamaan.

#### Investigasi Teknis Mendalam:
1.  Setiap data harga instrumen yang diterima memicu re-render pada tingkat root component karena status disimpan dalam satu store monolithic raksasa.
2.  Seluruh komponen baris tabel menggunakan `key={index}`, yang menyebabkan algoritma rekonsiliasi Fiber memproses ulang setiap baris saat penyortiran data berlangsung, alih-alih merelokasi node DOM.
3.  Tiap komponen mengeksekusi operasi baca-tulis DOM secara bergantian di dalam `componentDidUpdate`/`useLayoutEffect` mereka masing-masing, memicu 400x *Forced Synchronous Layouts* per detik.

#### Solusi Arsitektural:
1.  **Isolasi Partisi State**: State monolitik dipecah menjadi sub-store atomik per baris instrumen finansial.
2.  **Fiber-Friendly List Keys**: Mengubah key array menjadi UUID instrumen yang diindeks permanen.
3.  **Concurrent Scheduler Execution**: Mengarahkan proses pengurutan tabel ke API `startTransition`, sehingga pembaruan harga tidak lagi mengunci input interaktif trader.

```typescript
// Implementasi Desain Baru
function handleIncomingTick(tickUpdate: MarketTick) {
  // Update state prioritas rendah didelegasikan ke concurrent lane
  React.startTransition(() => {
    instrumentStateRegistry.get(tickUpdate.symbol)?.update(tickUpdate);
  });
}
```

#### Hasil Metrik Kinerja:
*   **Total Blocking Time (TBT)**: Turun dari 1.840ms menjadi 42ms (-97.7%).
*   **Frame Rate Runtime**: Naik dari rata-rata 11 FPS menjadi stabil di 58-60 FPS pada beban 5.000 ticks/detik.
*   **Penggunaan Heap Memori V8**: Berkurang dari 142MB menjadi 48MB berkat bailout rekonsiliasi yang efektif dan hilangnya pembuatan node DOM berulang.

---

### 19. Exercise & Self-Assessment

Selesaikan tiga problem arsitektural berikut dengan kode produksi valid:

#### Problem 1: Deteksi & Pencegahan Re-render Masif (Tingkat: Dasar)
Diberikan sebuah komponen parent yang mengeksekusi timer detik `setInterval` setiap 1000ms. Di dalamnya terdapat komponen anak `HeavyGraph` yang membutuhkan waktu komputasi 50ms untuk me-render data props array statis. Buat kode isolasi agar perubahan timer tidak memicu rekonsiliasi ke dalam `HeavyGraph`.
*Kriteria Penerimaan*: Waktu render fase update komponen anak harus 0.00ms setelah mount awal.

#### Problem 2: Custom List Reconciler Validator (Tingkat: Menengah)
Buatlah sebuah fungsi JavaScript murni `reconcileKeys(prevKeys: string[], nextKeys: string[])` yang menyimulasikan algoritma heuristik list diffing React. Fungsi harus menghasilkan daftar operasi minimal dengan output berupa array aksi: `INSERT(key, index)`, `REMOVE(key)`, atau `MOVE(key, index)`.
*Kriteria Penerimaan*: Operasi perpindahan item dari `['A', 'B', 'C']` menjadi `['B', 'A', 'C']` tidak boleh menghasilkan deklarasi `REMOVE` atau `INSERT` baru, melainkan hanya `MOVE`.

#### Problem 3: Scheduler Pembagi Unit Kerja (Tingkat: Lanjutan)
Rancang sebuah prototype penjadwal *time-slicing* fungsional bernama `runConcurrentWork(tasks: Array<() => void>, timeSliceMs: number): Promise<void>`. Penjadwal harus memproses array antrean tugas fungsional tanpa memblokir thread browser lebih lama dari alokasi budget `timeSliceMs` (misal 5ms). Gunakan `MessageChannel` untuk yielding mekanik eksekusi makrotask.
*Kriteria Penerimaan*: 10.000 loop komputasi matematika kompleks tidak boleh membekukan interaksi ketik antarmuka pengguna pada elemen input teks yang aktif di halaman.

---

### 20. Further Exploration

*   **Repositori React Source Code**:
    *   `packages/react-reconciler/src/ReactFiberWorkLoop.new.js` (Loop kerja fundamental rekonsiliasi)
    *   `packages/react-reconciler/src/ReactFiberBeginWork.new.js` (Logika diffing, bailout, dan hook verification)
*   **Makalah Akademik & Desain Sistem**:
    *   *A Survey on Tree Edit Distance and Related Problems* (Bille, 2005) – Telaah matematis mengapa algoritma generik $O(N^3)$ tidak dapat diterapkan secara langsung pada frame budget antarmuka interaktif 60 FPS.
    *   *React Fiber Architecture Design RFC* oleh Andrew Clark (Official RFC Archive).
*   **W3C Specifications**:
    *   *Cooperative Scheduling of Background Tasks* (W3C Working Group Note: `window.requestIdleCallback`).
    *   *Long Animation Frame API (LoAF)* - Pengukuran komprehensif performa render frame terkini.