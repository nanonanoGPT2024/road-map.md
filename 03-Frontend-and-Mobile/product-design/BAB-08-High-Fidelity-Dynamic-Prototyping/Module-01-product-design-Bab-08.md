# Bab 08 Module 01: High-Fidelity Dynamic Prototyping

---

## SEKSI 01 — IDENTITAS MODUL

* **Domain Kurikulum:** Product Design Engineering
* **Kategori:** `03-Frontend-and-Mobile`
* **Kode Modul:** `PDE-03-08-01`
* **Tingkat Kompleksitas:** Advanced / Staff Engineer Level
* **Prasyarat Pengetahuan:** 
  * Intermediate-to-Advanced React/TypeScript
  * Finite State Machines (FSM) & Statecharts (XState)
  * CSS Hardware Acceleration & Web Animations API (WAAPI)
  * Design Token Systems & Headless Component Architecture
* **Alokasi Waktu Pembelajaran:** 8 Jam Teori & Analisis Mendalam + 12 Jam Praktik Terpandu
* **Target Kompetensi:** Mampu merancang, mengarsitekturi, dan mengimplementasikan artefak *high-fidelity dynamic prototype* berbasis kode yang deterministik, responsif terhadap mutasi data real-time, mendekati performa native runtime 60–120 FPS, serta terintegrasi langsung dengan kontrak desain sistem produksi.

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik memiliki kapabilitas terukur untuk:

1. **Membedakan Paradigma Prototyping:** Mendekonstruksi batasan *canvas-based prototyping tools* (Figma, ProtoPie) versus *code-driven runtime prototypes*, serta memetakan kapan prototyping berbasis Web/React engine mutlak diperlukan untuk validasi interaksi berisiko tinggi (*high-risk UX validation*).
2. **Mengimplementasikan Statechart Terdistribusi:** Merancang state-machine deterministik menggunakan XState v5 untuk mengelola mikrostated, makrostated, asinkronisitas jaringan simulasi, dan kondisi balapan (*race conditions*) tanpa runtime bugs.
3. **Mengoptimalkan Pipeline Grafis Frontend:** Menerapkan transformasi 60-120 FPS menggunakan Framer Motion dan Web Animations API (WAAPI), memanfaatkan properti non-layout-triggering (`transform`, `opacity`) serta isolasi compositing layer (`will-change`).
4. **Membangun Simulasi Data Asinkron & Stateful In-Memory Storage:** Menyusun mock server terisolasi pada client-side runtime menggunakan MSW (Mock Service Worker) dan IndexedDB guna mereplikasi latensi jaringan riil, kegagalan parsial paket data (*network jitter/drop*), dan persistensi data lokal.
5. **Mengintegrasikan Aksesibilitas Dinamis (a11y):** Mengotomatisasi live regions (`aria-live`), focus trapping, dan navigasi keyboard spasial pada antarmuka dinamis tingkat lanjut.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### 1. Prototype Sebagai Production-Grade Specification, Bukan Mockup Statis
Banyak tim produk terjebak dalam ilusi bahwa desain visual setara dengan spesifikasi interaksi. Kanvas statis gagal merepresentasikan dimensi waktu ($t$), divergensi latensi jaringan ($ms$), saturasi thread runtime ($FPS$), dan konkurensi state pengguna. Mental model seorang Senior Product Design Engineer memandang prototipe tingkat tinggi sebagai *living executable specification*. Prototipe ini bukan sekadar alat presentasi kepada stakeholder, melainkan alat verifikasi batas-batas sistem, *edge cases*, dan interaksi mikro yang valid sebelum jutaan baris kode backend dibangun.

### 2. Dual-Engine Interaction Model: Rendering vs Compute
Dalam antarmuka dinamis berkecepatan tinggi, state komputasi aplikasi (*application state*) harus dipisahkan secara tegas dari state rendering gesture (*ephemeral gesture state*). Jika setiap pergeseran kursor atau gestur sentuh ($pointermove$, $touchmove$) memicu re-render pada React Virtual DOM root, frame rate akan anjlok drastis (frame drop). 

```
[ User Input Device ]
        │
   ┌────┴─────────────────────────────┐
   ▼                                   ▼
[ Ephemeral Gesture Engine ]   [ Deterministic Statechart ]
(Raw Coordinates, Physics)     (Application Logic & Flow)
   │                                   │
   │ (Bypass React VDOM)               │ (Discrete Action Dispatch)
   ▼                                   ▼
[ Compositor / Direct GPU ]    [ React VDOM Reconciler ]
   │                                   │
   └───────────────┬───────────────────┘
                   ▼
          [ Hardware Screen ]
```

Prototipe berperforma tinggi membagi eksekusi menjadi dua jalur:
* **The Render Track (GPU Thread):** Menangani interpolasi fisika, transisi visual, transfromasi matriks, dan gesture tracking langsung pada compositing layer tanpa menabrak render cycle framework.
* **The Logic Track (Main JS Thread):** Menggerakkan Finite State Machine untuk validasi aturan bisnis, otentikasi data, dan percabangan alur interaksi secara transparan dan deterministik.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur dari high-fidelity dynamic prototype berskala enterprise beroperasi pada lapisan modular terisolasi. Arsitektur ini memastikan interaksi bebas lag, deterministik, dan dapat dialihkan ke kode produksi secara modular.

```
+-----------------------------------------------------------------------------------------+
|                                    USER INTERFACE LAYER                                 |
|  +---------------------------+   +----------------------------+   +------------------+  |
|  | Complex Gesture Surfaces  |   | Virtualized Dynamic Lists  |   | Spatial Canvas   |  |
|  +-------------+-------------+   +--------------+-------------+   +--------+---------+  |
+----------------┼────────────────────────────────┼──────────────────────────┼------------+
                 | Pointer Events                 | Scroll/Selection         | Drag/Drop  
                 ▼                                ▼                          ▼            
+-----------------------------------------------------------------------------------------+
|                             INTERACTION RUNTIME ENGINE                                  |
|                                                                                         |
|  +-------------------------------------+      +--------------------------------------+  |
|  |      Continuous Interaction         |      |         Discrete Event Bus           |  |
|  |  (Framer Motion / Direct WAAPI)     |      |       (Custom Synthetic Events)      |  |
|  |  * Direct Transform Manipulations   |      +-------------------+------------------+  |
|  |  * Physics / Spring Solvers         |                          |                     |
|  +-------------------------------------+                          ▼                     |
|                                               +--------------------------------------+  |
|                                               |        State Machine Core            |  |
|                                               |            (XState v5)               |  |
|                                               |  * Deterministic Transitions         |  |
|                                               |  * Extended Context Validation       |  |
|                                               +-------------------+------------------+  |
+-------------------------------------------------------------------|---------------------+
                                                                    | Actions / Services  
                                                                    ▼                     
+-----------------------------------------------------------------------------------------+
|                              LOCAL MOCK DATA & PERSISTENCE                              |
|                                                                                         |
|  +-------------------------------------+      +--------------------------------------+  |
|  |      MSW Service Worker Hook        |      |       Client-Side In-Memory DB       |  |
|  |  (Intercepts Network Requests)      |◄────►|            (Dexie / IndexedDB)       |  |
|  |  * Latency Injection (0 - 4000ms)   |      |  * Relational Entity Graph           |  |
|  |  * Fault Injection (4xx, 5xx, Jitter)      |  * ACID Local Storage Engine         |  |
|  +-------------------------------------+      +--------------------------------------+  |
+-----------------------------------------------------------------------------------------+
```

### Penjelasan Alur Eksekusi Data & Render:
1. **Input Intercept:** Pengguna melakukan gestur (misal: *drag-to-swap card*). Event koordinat kontinu disalurkan ke *Continuous Interaction Engine* guna memperbarui matriks CSS 3D (`transform: translate3d(...)`) melewati pipeline React VDOM agar frame rate terkunci pada 60/120 FPS.
2. **Discrete Transition Trigger:** Ketika threshold gesture terpenuhi (*drag release* pada koordinat target), event diskrit dikirim ke *State Machine Core*.
3. **State Transition & Validation:** XState memvalidasi apakah perpindahan state diizinkan berdasarkan konteks internal dan invariants bisnis.
4. **Asynchronous Local Network Emulation:** State machine memicu panggilan HTTP/RPC tiruan yang dicegat langsung di network layer browser oleh *Mock Service Worker (MSW)*.
5. **Persistence Mutation:** MSW membaca atau menulis data terstruktur ke *Client-Side IndexedDB*, menyimulasikan round-trip latency jaringan riil secara terkonfigurasi, lalu mengembalikan data terisolasi ke state machine untuk memicu pembaruan final pada UI.

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

Komponen-komponen penyusun arsitektur dynamic prototype terdiri dari subsistem berikut:

```
 dynamic-prototype-runtime/
 ├── State Core/
 │   ├── Context (Extended Memory Store)
 │   ├── States & Nested Hierarchies
 │   ├── Guard Conditions (Invariants)
 │   └── Actions & Side-Effects Executer
 ├── Interaction & Animation Engine/
 │   ├── Spring-Physics Resolver
 │   ├── GPU Transform Pipeline
 │   └── Focus & Accessibility Synchronizer
 └── Data Emulation Layer/
     ├── Service Worker Network Interceptor
     ├── Network Fluctuation Controller (Latency/Drop)
     └── Reactive In-Memory Database (IndexedDB)
```

### Mekanisme Internal Komponen

#### 1. Context & Guards (State Machine Core)
XState memisahkan komputasi state kualitatif (e.g., `idle`, `dragging`, `validating`, `persisting`) dari data kuantitatif yang disimpan dalam `context`. Ketika event dipicu, engine melakukan evaluasi selektif:
$$\text{State}_{n+1} = \delta(\text{State}_n, \text{Event}, \text{Context}_n)$$
Jika guard condition bernilai `false`, state machine membatalkan transisi, menjaga sistem berada dalam state stabil (*state predictability invariant*).

#### 2. Spring Physics Resolver (Animation Engine)
Alih-alih menggunakan kurva Bezier parametrik berbasis waktu standar (`cubic-bezier(x1, y1, x2, y2)`), interaksi dinamis menggunakan formulasi matematis *damped spring-mass system*:
$$F = -k \cdot x - c \cdot v$$
Dimana $k$ adalah kekakuan pegas (*stiffness*), $c$ adalah koefisien redaman (*damping*), $x$ adalah deviasi posisi dari titik ekuilibrium, dan $v$ adalah kecepatan (*velocity*). Model ini mempertahankan momentum gestur pengguna (*velocity preservation*) sehingga antarmuka terasa natural saat dilepas di tengah gerakan.

#### 3. Network Fluctuation Controller (MSW Interceptor Layer)
MSW memotong traffic jaringan di level `WorkerGlobalScope` via native `fetch` interception. Simulasi latensi diinjeksikan secara deterministik menggunakan distribusi log-normal untuk meniru konektivitas seluler dunia nyata (latensi bervariasi dengan spike periodik), bukan sekadar `setTimeout` konstan.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Dynamic Fidelity Spectrum
Dalam rekayasa produk digital, fidelitas prototipe bukanlah konsep biner (*low-fi* vs *high-fi*), melainkan tensor multi-dimensi:

1. **Visual Fidelity:** Kesesuaian warna, tipografi, elevation, dan design token dengan sistem desain target.
2. **Spatial/Motion Fidelity:** Kesesuaian fisika gerakan, respons elastisitas, transformasi geometrik, dan frame cadence.
3. **Behavioral Fidelity:** Kemampuan prototype bereaksi terhadap *edge cases*, input error, konkurensi aksi pengguna, dan state hierarkis.
4. **Data Fidelity:** Realisme data yang disajikan, persistensi data antar sesi, serta anomali struktur muatan payload.

Canvas tools umumnya hanya menguasai Visual Fidelity dan sebagian Spatial Fidelity sederhana. Behavioral dan Data Fidelity mutlak membutuhkan eksekusi kode tingkat runtime browser.

### The Physics of Natural Motion
Perbedaan mencolok antara prototipe buatan desainer grafis dan sistem native terletak pada *kinematic continuity*. Transisi CSS konvensional berbasis durasi diskrit ($300\text{ms}$) membuang vektor kecepatan pengguna saat sentuhan dilepaskan. Apabila pengguna menyapu (*flick*) layar dengan kecepatan $1200\text{px/s}$, transisi berdurasi tetap akan menghentikan kecepatan secara mendadak sebelum memulai animasi baru, menciptakan diskontinuitas perseptual (*perceptual hitch*).

Framer Motion mengintegrasikan initial velocity ($v_0$) ke dalam penyelesaian persamaan diferensial gerak teredam:
$$x(t) = e^{-\gamma t} \left( c_1 \cos(\omega_d t) + c_2 \sin(\omega_d t) \right)$$
Hal ini mengasimilasi kecepatan gestur fisik pengguna langsung ke transisi pelepasan elemen visual tanpa diskontinuitas percepatan ($a = \frac{dv}{dt}$).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi dasar statechart menggunakan **XState v5** yang mengatur mekanisme *Swipe-to-Action Item* lengkap dengan guard limits, penanganan error, dan integrasi animasi.

```typescript
// swipeStateMachine.ts
import { setup, assign } from 'xstate';

export interface SwipeContext {
  dragDistance: number;
  threshold: number;
  errorMessage: string | null;
}

export type SwipeEvent =
  | { type: 'POINTER_DOWN' }
  | { type: 'POINTER_MOVE'; deltaX: number }
  | { type: 'POINTER_UP' }
  | { type: 'NETWORK_SUCCESS' }
  | { type: 'NETWORK_FAILURE'; error: string }
  | { type: 'RESET' };

export const swipeMachine = setup({
  types: {
    context: {} as SwipeContext,
    events: {} as SwipeEvent,
  },
  guards: {
    hasExceededThreshold: ({ context }) => context.dragDistance >= context.threshold,
  },
  actions: {
    updatePosition: assign({
      dragDistance: (_, params: { deltaX: number }) => Math.max(0, params.deltaX),
    }),
    resetPosition: assign({
      dragDistance: 0,
      errorMessage: null,
    }),
    setError: assign({
      errorMessage: (_, params: { error: string }) => params.error,
    }),
  },
}).createMachine({
  id: 'swipeAction',
  initial: 'idle',
  context: {
    dragDistance: 0,
    threshold: 160,
    errorMessage: null,
  },
  states: {
    idle: {
      on: {
        POINTER_DOWN: { target: 'tracking' },
      },
    },
    tracking: {
      on: {
        POINTER_MOVE: {
          actions: {
            type: 'updatePosition',
            params: ({ event }) => ({ deltaX: event.deltaX }),
          },
        },
        POINTER_UP: [
          {
            guard: 'hasExceededThreshold',
            target: 'committing',
          },
          {
            target: 'springBack',
          },
        ],
      },
    },
    springBack: {
      entry: 'resetPosition',
      always: { target: 'idle' },
    },
    committing: {
      initial: 'persisting',
      states: {
        persisting: {
          on: {
            NETWORK_SUCCESS: { target: '#swipeAction.dismissed' },
            NETWORK_FAILURE: {
              target: 'failed',
              actions: {
                type: 'setError',
                params: ({ event }) => ({ error: event.error }),
              },
            },
          },
        },
        failed: {
          on: {
            RESET: { target: '#swipeAction.idle', actions: 'resetPosition' },
          },
        },
      },
    },
    dismissed: {
      type: 'final',
    },
  },
});
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 1–16:** Mengimpor `setup` dan `assign` dari modul `xstate` v5. Menyusun interface strongly-typed untuk `SwipeContext` dan `SwipeEvent`. Penentuan tipe ketat ini krusial untuk mencegah propagasi state invalid selama manipulasi data berkecepatan tinggi.
* **Baris 18–34:** Blok `setup` memisahkan implementasi concrete dari struktur state machine. Guard `hasExceededThreshold` mengevaluasi context secara deterministik; aksi `updatePosition` membatasi pergerakan negatif (`Math.max(0, params.deltaX)`) guna mencegah item terseret ke arah yang tidak diinginkan secara anatomis.
* **Baris 40–44:** Inisialisasi statechart dengan `initial: 'idle'` dan menetapkan threshold geser pada nilai terisolasi `160px`.
* **Baris 45–66:** State `tracking`. Menangani mutasi koordinat kontinu via event `POINTER_MOVE`. Pada event `POINTER_UP`, array transisi bersyarat dieksekusi: jika guard `hasExceededThreshold` terpenuhi, mesin berpindah ke state hierarkis `committing`; jika tidak, jatuh ke `springBack`.
* **Baris 67–70:** State `springBack` memanggil action `resetPosition` dan secara langsung (`always`) kembali ke `idle`, memicu pemulihan koordinat visual ke zero point.
* **Baris 71–89:** State hierarkis `committing`. Mengisolasi logika komunikasi asynchronous di bawah sub-state `persisting`. Jika gagal (`NETWORK_FAILURE`), mesin beralih ke sub-state `failed` tanpa merusak integritas state machine utama, memungkinkan antarmuka menampilkan pesan galat terisolasi dan menyediakan transisi pemulihan via event `RESET`.
* **Baris 90–92:** State terminal `dismissed`. Komponen mengidentifikasi bahwa siklus hidup item telah selesai dan dapat dilepas dari tree rendering secara aman.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: "Apex Trader" — High-Frequency Order Execution Drawer
*Apex Financial Corp* mengembangkan sistem perdagangan instrumen derivatif berkecepatan tinggi. Tim UX mendesain fitur krusial: **"Slide-to-Execute Market Order"** dengan visualisasi pergerakan harga bid-ask riil (*streaming ticks*) secara simultan.

### Masalah pada Prototyping Konvensional
1. **Desinkronisasi State UI:** Desainer membuat prototype Figma dengan smart animate, namun gagal memodelkan situasi saat harga berubah drastis (*price slippage*) di tengah-tengah gerakan geser pengguna.
2. **Frame Drops Parah:** Prototipe React awal memicu re-render seluruh root drawer pada setiap perubahan posisi pointer, menyebabkan frame rate anjlok hingga 18 FPS pada perangkat iPad Pro penguji saat canvas charting me-render candle data secara paralel.
3. **Ketiadaan Simulasi Gangguan Jaringan:** Prototype tidak merefleksikan kegagalan transisi ketika order ditolak server (*partial fill* / *rejection limit*), sehingga eksekutif tidak menyadari kegagalan UX yang fatal pada handling status error saat rilis beta.

### Persyaratan Arsitektural Solusi
* Gestur kontinu diisolasi menggunakan motion value terkomputasi langsung pada hardware compositing layer.
* Alur eksekusi divalidasi oleh Finite State Machine deterministik yang menangani pembatalan order akibat slippage real-time.
* Mock Service Worker bertugas menyimulasikan round-trip latency jaringan lengkap dengan error rejection rate sebesar 20%.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Implementasi berikut menggunakan **React 18/19**, **TypeScript**, **Framer Motion**, dan **XState v5**.

### 1. Inisialisasi Mock Service Worker (MSW) Network Simulator

```typescript
// mocks/handlers.ts
import { http, HttpResponse, delay } from 'msw';

export const handlers = [
  http.post('/api/v1/orders/execute', async ({ request }) => {
    // Injeksi latensi asinkron realistik (antara 600ms - 1500ms)
    await delay(Math.floor(Math.random() * 900) + 600);

    const payload = (await request.json()) as { symbol: string; targetPrice: number; currentPrice: number };

    // Simulasi kegagalan eksekusi akibat Price Slippage (> 0.5% deviasi)
    const deviation = Math.abs((payload.currentPrice - payload.targetPrice) / payload.targetPrice);
    if (deviation > 0.005) {
      return HttpResponse.json(
        { errorCode: 'ERR_PRICE_SLIPPAGE', message: 'Slippage tolerance exceeded. Execution aborted.' },
        { status: 409 }
      );
    }

    // Simulasi failure rate jaringan 10%
    if (Math.random() < 0.1) {
      return HttpResponse.json(
        { errorCode: 'ERR_LIQUIDITY_TIMEOUT', message: 'Liquidity pool timed out.' },
        { status: 504 }
      );
    }

    return HttpResponse.json({
      orderId: `ORD-${crypto.randomUUID()}`,
      status: 'FILLED',
      executedPrice: payload.currentPrice,
      timestamp: Date.now(),
    });
  }),
];
```

### 2. State Machine Mesin Eksekusi Order

```typescript
// machines/orderExecutionMachine.ts
import { setup, assign, fromPromise } from 'xstate';

export interface OrderContext {
  symbol: string;
  lockedPrice: number;
  currentMarketPrice: number;
  orderId: string | null;
  errorMessage: string | null;
}

export type OrderEvent =
  | { type: 'TICK'; newPrice: number }
  | { type: 'DRAG_INITIATED' }
  | { type: 'DRAG_CANCELLED' }
  | { type: 'EXECUTE_CONFIRMED' }
  | { type: 'RETRY' };

export const orderExecutionMachine = setup({
  types: {
    context: {} as OrderContext,
    events: {} as OrderEvent,
  },
  actors: {
    executeOrderService: fromPromise<
      { orderId: string; executedPrice: number },
      { symbol: string; lockedPrice: number; currentMarketPrice: number }
    >(async ({ input }) => {
      const response = await fetch('/api/v1/orders/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Execution failed');
      }

      return response.json();
    }),
  },
  actions: {
    updateMarketPrice: assign({
      currentMarketPrice: (_, params: { price: number }) => params.price,
    }),
    lockCurrentPrice: assign({
      lockedPrice: ({ context }) => context.currentMarketPrice,
      errorMessage: null,
    }),
    setError: assign({
      errorMessage: ({ event }) => (event as any).error?.message || 'Unknown network failure',
    }),
    setSuccessData: assign({
      orderId: ({ event }) => (event as any).output.orderId,
      lockedPrice: ({ event }) => (event as any).output.executedPrice,
    }),
  },
}).createMachine({
  id: 'orderExecution',
  initial: 'idle',
  context: {
    symbol: 'ETH-USD',
    lockedPrice: 3200.0,
    currentMarketPrice: 3200.0,
    orderId: null,
    errorMessage: null,
  },
  states: {
    idle: {
      on: {
        TICK: {
          actions: {
            type: 'updateMarketPrice',
            params: ({ event }) => ({ price: event.newPrice }),
          },
        },
        DRAG_INITIATED: {
          target: 'dragging',
          actions: 'lockCurrentPrice',
        },
      },
    },
    dragging: {
      on: {
        TICK: {
          actions: {
            type: 'updateMarketPrice',
            params: ({ event }) => ({ price: event.newPrice }),
          },
        },
        DRAG_CANCELLED: {
          target: 'idle',
        },
        EXECUTE_CONFIRMED: {
          target: 'executing',
        },
      },
    },
    executing: {
      invoke: {
        src: 'executeOrderService',
        input: ({ context }) => ({
          symbol: context.symbol,
          lockedPrice: context.lockedPrice,
          currentMarketPrice: context.currentMarketPrice,
        }),
        onDone: {
          target: 'settled',
          actions: 'setSuccessData',
        },
        onError: {
          target: 'rejected',
          actions: 'setError',
        },
      },
    },
    rejected: {
      on: {
        RETRY: {
          target: 'idle',
        },
      },
    },
    settled: {
      type: 'final',
    },
  },
});
```

### 3. Komponen Antarmuka High-Performance Motion UI

```tsx
// components/SlideToExecuteOrder.tsx
import React, { useEffect, useRef } from 'react';
import { useMachine } from '@xstate/react';
import { motion, useMotionValue, useTransform, useAnimation, PanInfo } from 'framer-motion';
import { orderExecutionMachine } from '../machines/orderExecutionMachine';

const TRACK_WIDTH = 320;
const THUMB_WIDTH = 64;
const DRAG_LIMIT = TRACK_WIDTH - THUMB_WIDTH;
const COMMIT_THRESHOLD = DRAG_LIMIT * 0.85;

export const SlideToExecuteOrder: React.FC = () => {
  const [state, send] = useMachine(orderExecutionMachine);
  const dragX = useMotionValue(0);
  const controls = useAnimation();
  const trackRef = useRef<HTMLDivElement>(null);

  // Transformasi visual dioperasikan langsung di Compositor layer
  const fillWidth = useTransform(dragX, [0, DRAG_LIMIT], [THUMB_WIDTH, TRACK_WIDTH]);
  const textOpacity = useTransform(dragX, [0, DRAG_LIMIT / 2], [1, 0]);
  const handleScale = useTransform(dragX, [0, DRAG_LIMIT], [1, 1.05]);

  // Simulasi WebSocket market tick data engine
  useEffect(() => {
    const interval = setInterval(() => {
      const volatility = (Math.random() - 0.49) * 4.5;
      const nextPrice = Number((state.context.currentMarketPrice + volatility).toFixed(2));
      send({ type: 'TICK', newPrice: nextPrice });
    }, 400);

    return () => clearInterval(interval);
  }, [state.context.currentMarketPrice, send]);

  const handleDragStart = () => {
    send({ type: 'DRAG_INITIATED' });
  };

  const handleDragEnd = async (_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (dragX.get() >= COMMIT_THRESHOLD) {
      // Mengunci thumb di ujung kanan saat eksekusi
      controls.start({ x: DRAG_LIMIT, transition: { type: 'spring', stiffness: 500, damping: 40 } });
      send({ type: 'EXECUTE_CONFIRMED' });
    } else {
      // Pegas elastis mengembalikan handle ke titik nol dengan mempertahankan momentum pelepasan
      controls.start({
        x: 0,
        transition: {
          type: 'spring',
          stiffness: 400,
          damping: 28,
          velocity: info.velocity.x,
        },
      });
      send({ type: 'DRAG_CANCELLED' });
    }
  };

  // Observasi pemulihan saat order gagal
  useEffect(() => {
    if (state.matches('rejected')) {
      controls.start({ x: 0, transition: { type: 'spring', stiffness: 300, damping: 20 } });
      dragX.set(0);
    }
  }, [state.value, controls, dragX]);

  const isInteractive = state.matches('idle') || state.matches('dragging');

  return (
    <div className="flex flex-col items-center justify-center min-h-[480px] p-6 bg-slate-950 text-slate-100 font-sans select-none">
      <div className="w-full max-w-sm p-6 bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl">
        {/* Header Telemetri & Harga */}
        <div className="flex justify-between items-baseline mb-6">
          <div>
            <h2 className="text-sm font-semibold tracking-wider text-slate-400 uppercase">
              {state.context.symbol}
            </h2>
            <p className="text-xs text-slate-500">Perpetual Contract</p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-mono font-bold tracking-tight text-emerald-400">
              ${state.context.currentMarketPrice.toFixed(2)}
            </div>
            <div className="text-xs text-slate-400 font-mono">
              Locked: ${state.context.lockedPrice.toFixed(2)}
            </div>
          </div>
        </div>

        {/* State Status Banner */}
        <div className="h-10 mb-6 flex items-center justify-center">
          {state.matches('executing') && (
            <div className="flex items-center gap-2 text-amber-400 text-sm font-medium animate-pulse">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
              Routing to liquidity venue...
            </div>
          )}
          {state.matches('rejected') && (
            <div className="text-rose-400 text-xs text-center font-medium bg-rose-950/40 border border-rose-800/50 p-2 rounded-lg w-full">
              {state.context.errorMessage}
            </div>
          )}
          {state.matches('settled') && (
            <div className="text-emerald-400 text-sm font-semibold bg-emerald-950/30 border border-emerald-800/40 p-2 rounded-lg text-center w-full">
              ORDER FILLED: {state.context.orderId}
            </div>
          )}
        </div>

        {/* Slider Component Housing */}
        <div
          ref={trackRef}
          role="slider"
          aria-valuemin={0}
          aria-valuemax={DRAG_LIMIT}
          aria-valuenow={dragX.get()}
          tabIndex={0}
          className="relative h-16 bg-slate-950 border border-slate-800 rounded-full p-1 overflow-hidden focus:outline-none focus:ring-2 focus:ring-emerald-500"
          style={{ width: TRACK_WIDTH }}
        >
          {/* Animated Dynamic Fill Layer */}
          <motion.div
            className="absolute top-0 left-0 bottom-0 bg-emerald-950 border-r border-emerald-500/50 rounded-full"
            style={{ width: fillWidth }}
          />

          {/* Interactive Guide Typography */}
          <motion.div
            style={{ opacity: textOpacity }}
            className="absolute inset-0 flex items-center justify-center pointer-events-none text-xs font-semibold uppercase tracking-widest text-slate-400 pl-8"
          >
            Slide to Confirm
          </motion.div>

          {/* Touch / Mouse Scrub Handle */}
          <motion.div
            drag={isInteractive ? 'x' : false}
            dragConstraints={{ left: 0, right: DRAG_LIMIT }}
            dragElastic={0.05}
            dragMomentum={false}
            animate={controls}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
            style={{ x: dragX, scale: handleScale, width: THUMB_WIDTH }}
            className={`relative z-10 h-full rounded-full flex items-center justify-center cursor-grab active:cursor-grabbing transition-colors ${
              state.matches('settled')
                ? 'bg-emerald-500 text-slate-950'
                : state.matches('rejected')
                ? 'bg-rose-500 text-white'
                : 'bg-emerald-400 text-slate-950 hover:bg-emerald-300'
            }`}
          >
            {state.matches('executing') ? (
              <svg className="animate-spin h-5 w-5 text-slate-950" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            ) : (
              <span className="font-bold text-lg select-none">&rarr;</span>
            )}
          </motion.div>
        </div>

        {/* Retry Fallback Mechanism */}
        {state.matches('rejected') && (
          <button
            onClick={() => send({ type: 'RETRY' })}
            className="mt-6 w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold tracking-wider uppercase rounded-lg transition-colors border border-slate-700"
          >
            Dismiss & Reset Buffer
          </button>
        )}
      </div>
    </div>
  );
};
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Dimensi Arsitektural | Canvas Prototyping (Figma / ProtoPie