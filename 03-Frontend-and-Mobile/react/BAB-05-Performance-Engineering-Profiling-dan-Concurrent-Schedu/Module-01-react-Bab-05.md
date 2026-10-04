# SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Kurikulum:** React Enterprise Architecture & Performance Engineering
* **Bab:** 05 — Advanced Optimization, Runtimes, & Profiling
* **Modul:** 01 — Performance Engineering, Profiling, & Concurrent Scheduling
* **Prasyarat:** Pemahaman mendalam tentang React Fiber Architecture, Reconciliation Algorithm, Hook Lifecycles, Browser Event Loop, Frame Budgets (16.6ms / 60fps & 8.3ms / 120fps).
* **Alokasi Waktu:** 8 Jam (Teori Mendalam, Instrumentasi Profiling, Bedah Runtime, & Hands-on Implementation)

---

# SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta didik pada level Staff/Principal Engineer diharapkan mampu:
1. Mengurai siklus hidup eksekusi **Fiber Reconciler** pada fase Render (Interruptible) vs Commit (Synchronous/Mutation) serta dampaknya terhadap thread execution budget.
2. Membedah mekanika **Cooperative Multitasking** dan **Lanes Engine** di dalam React 18/19 Scheduler (`scheduler/src/Scheduler.js`) menggunakan priority bitmasks.
3. Menguasai API Concurrent Scheduling (`useTransition`, `useDeferredValue`, `startTransition`) untuk mencegah blocking pada browser main-thread selama CPU-bound computations.
4. Melakukan profiling deterministik pada aplikasi React enterprise menggunakan React DevTools Profiler, Chrome Performance Profiler (User Timing API), dan Long Animation Frames API (`LoAF`).
5. Menemukan dan mengeliminasi pola degradasi performa: cascade re-renders, premature optimizations, thrashing memory leaks akibat closure retention, serta synthetic layout thrashing.
6. Mengimplementasikan telemetri performa sisi klien skala produksi menggunakan Web Vitals (INP, LCP, CLS) yang terhubung langsung ke OpenTelemetry / Datadog.

---

# SEKSI 03 — MINDSET & MENTAL MODEL
### Rendering adalah Perhitungan Matematis, Bukan Manipulasi DOM Langsung
Mental model konvensional menganggap bahwa memanggil fungsi komponen React langsung mengubah simpul DOM di layar. Pada arsitektur concurrent modern, rendering hanyalah **penghitungan proyeksi state berikutnya ke dalam struktur data pohon virtual memory-resident (Fiber)**.

React memisahkan pekerjaan menjadi dua fase absolut:
1. **Render Phase (Asynchronous / Non-Blocking):** Menghitung pohon Fiber baru (*work-in-progress* tree). Fase ini bersifat spekulatif, dapat dijeda (paused), dibatalkan (aborted), atau dimulai ulang oleh Scheduler berdasarkan prioritas lane.
2. **Commit Phase (Synchronous / Blocking):** Menerapkan mutasi yang dihitung ke Host DOM nyata, menjalankan lifecycle effects (`useLayoutEffect`, diikuti browser paint, kemudian `useEffect`). Fase ini tidak boleh dan tidak dapat diinterupsi.

### Filosofi "Budget-Driven Scheduling"
Main thread browser adalah sumber daya bersama dengan bandwidth waktu terbatas. Untuk mempertahankan animasi 60 FPS yang mulus, setiap frame memiliki batas waktu 16.67 milidetik. Dalam batas waktu ini, browser harus menangani input OS, menjalankan JavaScript, menghitung CSS style recalculation, layouting, painting, dan compositing.

React Concurrent Scheduler bertindak layaknya **Operating System Kernel** untuk UI: ia mengimplementasikan cooperative time-slicing. Alih-alih mengeksekusi long-running JavaScript execution monolitik yang menyebabkan UI *freeze* (frame dropping / jank), Scheduler memecah proses reconciler menjadi chunk waktu berukuran kecil (~5ms via `MessageChannel`), menyerahkan kontrol kembali ke Event Loop browser untuk merespons interaksi kritis (ketikan keyboard, pointer clicks).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

```
+--------------------------------------------------------------------------------------------------+
|                                    EVENT LOOP & USER INTERACTION                                 |
+--------------------------------------------------------------------------------------------------+
          | (User Type: Urgent)                                   | (Data Filter: Transition)
          v                                                       v
  [ Discrete Event ]                                     [ Transition Event ]
  (SyncLane: Priority 1)                             (TransitionLane: Priority 64-1024)
          |                                                       |
          +---------------------------+---------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------------------------------+
|                                   REACT SCHEDULER ENGINE                                         |
|  - Min-Heap Priority Queue (taskQueue vs timerQueue)                                             |
|  - Cooperative Time-Slicing via MessageChannel (5ms default slice budget)                        |
+--------------------------------------------------------------------------------------------------+
                                      |
                           Work Request Scheduled
                                      v
+--------------------------------------------------------------------------------------------------+
|                            RENDER PHASE (Interruptible / Non-Blocking)                           |
|                                                                                                  |
|   Current Fiber Tree                        Work-in-Progress (WIP) Fiber Tree                    |
|   +------------------+                      +------------------+                                 |
|   | Fiber (Root)     |                      | Fiber (Root-WIP) |                                 |
|   +------------------+                      +------------------+                                 |
|            |                                         |                                           |
|            v                                         v                                           |
|   +------------------+   Alternate Pointer  +------------------+                                 |
|   | Fiber (Parent)   |<====================>| Fiber (Parent-WIP|                                 |
|   +------------------+                      +------------------+                                 |
|            |                                         | (Yield if frame budget expired > 5ms)     |
|            v                                         v                                           |
|   +------------------+                      +------------------+                                 |
|   | Fiber (Child)    |                      | Fiber (Child-WIP)|                                 |
|   +------------------+                      +------------------+                                 |
|                                                                                                  |
|   [Scheduler Interrupt Detection]:                                                               |
|   if (navigator.scheduling.isInputPending() || performance.now() >= deadline)                   |
|       => Yield control back to Host Browser Main Thread via MessageChannel postMessage           |
+--------------------------------------------------------------------------------------------------+
                                      |
                               Work Complete
                                      v
+--------------------------------------------------------------------------------------------------+
|                              COMMIT PHASE (Strictly Synchronous)                                 |
|                                                                                                  |
|   1. Before Mutation: Mengambil snapshot DOM (getSnapshotBeforeUpdate)                           |
|   2. Mutation: Swap root pointer (current = workInProgress), Mutasi DOM Host nyata               |
|   3. Layout: Eksekusi useLayoutEffect synchronous (DOM up-to-date, paint belum terjadi)          |
+--------------------------------------------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------------------------------+
|                                  BROWSER RENDER PIPELINE                                         |
|            Recalculate Style ---> Layout / Reflow ---> Paint ---> Composite Layers               |
+--------------------------------------------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------------------------------+
|                                     POST-PAINT PHASE                                             |
|                     Passive Effects Executed (useEffect asynchronous batch)                      |
+--------------------------------------------------------------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Fiber Node Internals
Sebuah Fiber adalah unit kerja (unit of work) JavaScript object yang merepresentasikan komponen beserta state, props, dan dependensinya.
* **`tag`**: Identifikasi tipe komponen (e.g., `FunctionComponent = 0`, `ClassComponent = 1`, `HostComponent = 5`).
* **`stateNode`**: Referensi ke instance objek lokal (misal: node DOM HTMLDivElement atau class instance).
* **`alternate`**: Pointer krusial untuk arsitektur *Double Buffering*. Node `current.alternate` merujuk ke `workInProgress`, dan sebaliknya. Ini mencegah alokasi memori berlebih antar-siklus render.
* **`lanes` & `childLanes`**: 31-bit bitmask yang menyimpan prioritas pembaruan komponen ini dan keturunannya.
* **`memoizedState`**: Linked-list dari hook instances untuk functional components.
* **`return`, `child`, `sibling`**: Struktur data unidirectional tree traversal pointers yang mengeliminasi kebutuhan call-stack rekursif dalam JavaScript runtime.

### 2. Lanes Priority Architecture
React meninggalkan arsitektur *Expiration Time* numerik linear dan beralih ke representasi bitmask 32-bit yang disebut **Lanes**. Hal ini memungkinkan React mengelompokkan tugas yang tidak berurutan, melakukan *batching*, *suspending*, dan *prioritizing*:

```javascript
// Konsep Sederhana Bitmask Lanes di React Source Code (ReactFiberLane.js)
export const TotalLanes           = 31;
export const NoLanes              = 0b0000000000000000000000000000000;
export const SyncLane             = 0b0000000000000000000000000000001; // Discrete user input (click, keydown)
export const InputContinuousLane  = 0b0000000000000000000000000000010; // Continuous input (drag, scroll)
export const DefaultLane          = 0b0000000000000000000000001000000; // Normal fetch / state update
export const TransitionLanes      = 0b0000000011111111000000000000000; // useTransition, non-urgent
export const IdleLane             = 0b0100000000000000000000000000000; // Off-screen / low-priority work
```
Operasi penentuan apakah suatu komponen memiliki pekerjaan mendesak dilakukan melalui operasi bitwise kilat:
```javascript
const hasUrgentWork = (workInProgress.lanes & (SyncLane | InputContinuousLane)) !== NoLanes;
```

### 3. Cooperative Time-Slicing Scheduler
Alih-alih menggunakan `window.requestIdleCallback` yang memiliki latensi unpredictable pada berbagai browser platform (sering kali diturunkan prioritasnya hingga 50ms saat background activity tinggi), Scheduler React menggunakan kombinasi:
* Pola perulangan task via `MessageChannel` (macro-task) untuk menjadwalkan eksekusi antar frame.
* `performance.now()` deadline checks: Alokasi yield frame budget default adalah **5 milidetik**. Jika eksekusi reconciler melebihi 5ms dan masih ada item tersisa di heap queue, Scheduler menyerahkan eksekusi ke browser agar proses paint/input handling berjalan tanpa hambatan.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Rendering Cascades dan Rekonsiliasi Kompleks
Masalah utama dalam aplikasi berskala besar adalah *Cascading Re-renders*. Ketika komponen *root* memperbarui state-nya, secara *default* React menelusuri seluruh sub-tree di bawah komponen tersebut secara top-down, memanggil fungsi render untuk setiap komponen anak kecuali dicegah secara eksplisit.

#### Analisis Matematis Work Tree Traversal
Misalkan sebuah aplikasi memiliki kedalaman pohon komponen $D$ dengan rata-rata faktor percabangan (branching factor) $B$. Kompleksitas traversal rekonsiliasi naive adalah:
$$\mathcal{O}(B^D)$$
Dengan `React.memo`, React memotong cabang (*pruning*): jika `prevProps === nextProps` (evaluasi referensial dangkal / shallow equality), React menyalin pointer `current.child` langsung ke `workInProgress.child`, mengubah sub-tree traversal time untuk cabang tersebut menjadi $\mathcal{O}(1)$.

### Mekanisme `useTransition` vs `useDeferredValue`
Keduanya dirancang untuk memisahkan **Urgent Updates** (misalnya, mengetik di keyboard, klik tombol submit) dari **Non-Urgent / Transition Updates** (misalnya, pemfilteran daftar data 10.000 baris, rendering visual chart).

* **`useTransition` (Action-centric):** Digunakan ketika kita memiliki akses langsung ke kode pembaruan state (`setState`). Kode yang dibungkus di dalam callback `startTransition(() => { setState(val) })` ditandai dengan bitmask `TransitionLane`. React akan mengeksekusi render ini dengan prioritas rendah dan dapat membatalkannya jika input baru terdeteksi di `SyncLane`.
* **`useDeferredValue` (Value-centric):** Digunakan ketika state dikontrol oleh library pihak ketiga, diteruskan via props, atau ketika pembaruan state terjadi di luar kendali langsung komponen lokal. `useDeferredValue` menerima sebuah value dan mengembalikan salinan baru yang ditunda perubahannya jika ada eksekusi prioritas tinggi yang sedang berjalan. Komponen anak yang bergantung pada value ini akan memproses render secara deferred.

### Metrik Interaksi Modern: Interaction to Next Paint (INP)
INP adalah metrik Core Web Vital yang mengukur responsivitas interaksi pengguna secara menyeluruh di sepanjang siklus hidup halaman. INP mengukur waktu dari input pengguna hingga frame visual berikutnya di-render oleh browser.
$$\text{INP} = \text{Input Delay} + \text{Processing Duration} + \text{Presentation Delay}$$

1. **Input Delay:** Waktu tunggu sebelum event handler mulai berjalan (disebabkan oleh thread contention / long tasks lain).
2. **Processing Duration:** Waktu eksekusi murni JavaScript event listener + sinkronisasi render React.
3. **Presentation Delay:** Waktu yang dihabiskan browser untuk styling, recalculate layout, composition, dan hardware paint.

Concurrent scheduling secara spesifik memangkas **Input Delay** untuk interaksi berikutnya dan mendistribusikan **Processing Duration** agar tidak menciptakan Long Tasks (> 50ms) yang merusak skor INP.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi bare-metal concurrent orchestration yang membedakan **Urgent State Updates** dan **Transition Rendering** menggunakan `useTransition` dan profiling markers kustom.

```tsx
import React, { useState, useTransition, useId, useMemo, ChangeEvent } from 'react';

// Representasi Item Dataset Kompleks
interface TelemetryRecord {
  id: string;
  metricName: string;
  value: number;
  hash: string;
}

// Simulasi generator data berat secara deterministik
function generateHeavyDataset(size: number, query: string): TelemetryRecord[] {
  const records: TelemetryRecord[] = [];
  for (let i = 0; i < size; i++) {
    records.push({
      id: `metric-${i}`,
      metricName: `cpu_core_${i % 64}_utilization_percentage`,
      value: Math.sin(i) * 100,
      hash: `${query}-chunk-${Math.imul(i, 0x5bd1e995).toString(16)}`,
    });
  }
  return records;
}

export function HighThroughputDashboard(): React.JSX.Element {
  const inputId = useId();
  // 1. State Input Segera (Urgent State)
  const [inputValue, setInputValue] = useState<string>('');
  
  // 2. State Pemrosesan Berat (Transition State)
  const [deferredFilter, setDeferredFilter] = useState<string>('');
  
  // 3. React Concurrent Scheduler Hook
  const [isPending, startTransition] = useTransition();

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const nextValue = e.target.value;
    
    // PRIORITY 1 (SyncLane / Urgent): Segera sinkronkan nilai input DOM
    setInputValue(nextValue);

    // Instrumentasi Custom Profiling Mark
    if (typeof performance !== 'undefined') {
      performance.mark('transition-scheduled');
    }

    // PRIORITY 2 (TransitionLane): Tunda pemrosesan kalkulasi dataset
    startTransition(() => {
      setDeferredFilter(nextValue);
    });
  };

  return (
    <div style={{ padding: '24px', fontFamily: 'monospace' }}>
      <h1>Enterprise Metrics Monitor</h1>
      
      <div style={{ marginBottom: '16px' }}>
        <label htmlFor={inputId}>Filter Metric Stream: </label>
        <input
          id={inputId}
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          placeholder="Ketik untuk memfilter..."
          style={{ padding: '8px', fontSize: '16px', width: '300px' }}
        />
        {isPending && (
          <span style={{ marginLeft: '12px', color: '#d97706', fontWeight: 'bold' }}>
            [Scheduler: Yielding Frame Budget...]
          </span>
        )}
      </div>

      <MetricsVisualizer filter={deferredFilter} />
    </div>
  );
}

interface MetricsVisualizerProps {
  filter: string;
}

// Sub-komponen yang mengeksekusi komputasi berat
const MetricsVisualizer = React.memo(function MetricsVisualizer({ filter }: MetricsVisualizerProps) {
  // Simulasi pemfilteran dan kalkulasi CPU-bound
  const dataset = useMemo(() => {
    const rawData = generateHeavyDataset(20000, filter);
    if (!filter) return rawData.slice(0, 100);
    return rawData.filter(item => item.hash.includes(filter)).slice(0, 100);
  }, [filter]);

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
      <thead>
        <tr style={{ borderBottom: '2px solid #333' }}>
          <th>ID</th>
          <th>METRIC NAME</th>
          <th>VALUE</th>
          <th>HASH DIGEST</th>
        </tr>
      </thead>
      <tbody>
        {dataset.map((row) => (
          <tr key={row.id} style={{ borderBottom: '1px solid #ccc' }}>
            <td>{row.id}</td>
            <td>{row.metricName}</td>
            <td>{row.value.toFixed(4)}</td>
            <td>{row.hash}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
});
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Bedah Mekanisme Kode Seksi 07
* **Baris 27–31 (`useState`, `useTransition`)**:
  * `inputValue` bertindak sebagai *source of truth* lokal yang harus berfluktuasi secara real-time mengikuti event hardware keyboard.
  * `isPending` mengembalikan status boolean yang dikontrol oleh Scheduler untuk mengindikasikan apakah lane transition yang dijadwalkan masih berada di heap antrean atau sedang dalam proses pengerjaan.
* **Baris 33–46 (`handleInputChange`)**:
  * `setInputValue(nextValue)` dieksekusi secara instan di dalam konteks native browser event handler, mendapatkan prioritas `SyncLane`.
  * `performance.mark('transition-scheduled')`: Menetapkan marker User Timing API yang dapat dianalisis di devtools tracing timeline.
  * `startTransition(() => { setDeferredFilter(nextValue); })`: Callback ini membungkus modifikasi `deferredFilter`. React menurunkan prioritas work fiber ini ke rentang `TransitionLanes`. Jika pengguna terus mengetik karakter baru sebelum transisi sebelumnya selesai, React menginterupsi *work-in-progress* tree lama, membuangnya secara instan, dan memulai penghitungan baru menggunakan nilai filter teranyar.
* **Baris 78 (`React.memo`)**:
  * Menerapkan optimasi evaluasi referensial pada `MetricsVisualizer`. Jika props `filter` tidak berubah saat re-render parent lainnya terjadi, komponen ini langsung melompati fase reconciler (*bailout phase*).
* **Baris 80–84 (`useMemo`)**:
  * Melindungi alokasi array dan pemrosesan komputasi dari eksekusi redundant. Hanya dihitung ulang jika `filter` bertransisi.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Wall-Street Real-Time Financial Ledger
* **Konteks:** Sebuah platform perdagangan derivatif institusional memproses WebSocket stream berisi rata-rata 1.500 quote perubahan harga per detik.
* **Masalah:** UI membeku (UI lockup / *jank* parah). Setiap kali input text box (pencarian aset) diketik, latensi pengetikan mencapai **450 milidetik** per keystroke (INP buruk, > 500ms). Konsumsi memori browser meningkat tajam (*sawtooth pattern* parah) berujung pada crash browser tab karena alokasi garbage collection yang masif.
* **Akar Penyebab (Root Causes):**
  1. WebSocket event handler langsung memicu `setState` di komponen root dashboard tanpa throttling/batching.
  2. Komponen chart dan grid order-book me-render ulang seluruh sub-tree (lebih dari 12.000 node Fiber) pada setiap pesan socket.
  3. Terjadi *Forced Synchronous Layout (Layout Thrashing)* karena komponen tabel membaca properti DOM `element.getBoundingClientRect()` di dalam loop perenderan untuk menghitung zebra-striping dan tooltips.
* **Target Optimasi:**
  * Menurunkan INP dari **450ms** ke **< 35ms** (Good range).
  * Menstabilkan frame rate pada 60 FPS stabil di bawah beban 1.500 socket payload/detik.
  * Menghilangkan long tasks browser (> 50ms) dari main-thread.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Solusi berstandar produksi yang menerapkan:
1. **Ring-Buffer Event Batching Engine** untuk WebSocket.
2. **Concurrent Lane Isolation** dengan `useDeferredValue`.
3. **Virtual Windowing Engine Ringan** (tanpa dependency eksternal).
4. **Layout Thrashing Elimination**.

```tsx
import React, { 
  useState, 
  useEffect, 
  useRef, 
  useDeferredValue, 
  useCallback, 
  useMemo, 
  UIEvent 
} from 'react';

// Struct Data Ledger
export interface OrderBookEntry {
  readonly orderId: string;
  readonly instrument: string;
  readonly price: number;
  readonly volume: number;
  readonly timestamp: number;
}

// 1. Production Telemetry & Profiler Integration
function reportInteractionLag(metricName: string, durationMs: number): void {
  if (typeof window !== 'undefined' && 'performance' in window) {
    performance.measure(`[INP-Audit] ${metricName}`, {
      start: performance.now() - durationMs,
      duration: durationMs
    });
  }
}

export function HighFrequencyTradingPlatform(): React.JSX.Element {
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [rawOrders, setRawOrders] = useState<readonly OrderBookEntry[]>([]);
  
  // Isolasi konkurensi: deferred search term untuk memangkas long-task
  const deferredSearch = useDeferredValue(searchTerm);
  
  // Buffer referensial untuk mengumpulkan payload throughput tinggi tanpa re-render instan
  const ingestBufferRef = useRef<OrderBookEntry[]>([]);
  const isComponentMounted = useRef<boolean>(true);

  // 2. High-Frequency WebSocket Batching Ingest Pipeline
  useEffect(() => {
    isComponentMounted.current = true;
    let animationFrameId: number;

    // Simulasi generator koneksi data stream berkecepatan tinggi
    const intervalTimer = setInterval(() => {
      const now = performance.now();
      const mockBatchedTick: OrderBookEntry[] = Array.from({ length: 50 }, (_, idx) => ({
        orderId: `ORD-${now.toFixed(0)}-${idx}`,
        instrument: idx % 2 === 0 ? 'BTC-USD' : 'ETH-USD',
        price: 50000 + Math.random() * 2000,
        volume: Math.random() * 10,
        timestamp: now
      }));
      ingestBufferRef.current.push(...mockBatchedTick);
    }, 16); // ~60 batch payload per detik

    // Flush batching loop secara aman pada micro-frame boundary
    const flushBatchToState = () => {
      if (ingestBufferRef.current.length > 0) {
        const bufferedData = ingestBufferRef.current;
        ingestBufferRef.current = []; // Drain queue
        
        setRawOrders((prevOrders) => {
          // Batasi retensi in-memory ring-buffer maksimal 5.000 entitas terbaru
          const merged = [...bufferedData, ...prevOrders];
          return merged.length > 5000 ? merged.slice(0, 5000) : merged;
        });
      }
      if (isComponentMounted.current) {
        animationFrameId = requestAnimationFrame(flushBatchToState);
      }
    };

    animationFrameId = requestAnimationFrame(flushBatchToState);

    return () => {
      isComponentMounted.current = false;
      clearInterval(intervalTimer);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  // Filter deterministik dieksekusi di transition-state boundary via deferred value
  const filteredOrders = useMemo(() => {
    if (!deferredSearch.trim()) return rawOrders;
    const query = deferredSearch.toLowerCase();
    return rawOrders.filter(
      (order) =>
        order.instrument.toLowerCase().includes(query) ||
        order.orderId.toLowerCase().includes(query)
    );
  }, [rawOrders, deferredSearch]);

  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const startTime = performance.now();
    setSearchTerm(e.target.value);
    const duration = performance.now() - startTime;
    reportInteractionLag('OrderSearchInput', duration);
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', padding: 20 }}>
      <h2>Ultra-Low Latency Order Ledger</h2>
      <div style={{ marginBottom: 12 }}>
        <input
          type="text"
          value={searchTerm}
          onChange={handleSearchChange}
          placeholder="Filter Instrument / Order ID..."
          style={{ width: '100%', padding: '10px 14px', fontSize: 16 }}
        />
      </div>

      <div style={{ flex: 1, overflow: 'hidden' }}>
        <VirtualizedOrderTable dataset={filteredOrders} rowHeight={32} />
      </div>
    </div>
  );
}

// 3. High-Performance Deterministic Virtual Grid
interface VirtualizedOrderTableProps {
  dataset: readonly OrderBookEntry[];
  rowHeight: number;
}

const VirtualizedOrderTable = React.memo(function VirtualizedOrderTable({
  dataset,
  rowHeight,
}: VirtualizedOrderTableProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState<number>(0);
  const [viewportHeight, setViewportHeight] = useState<number>(600);

  // ResizeObserver untuk kalkulasi viewport bebas thrashing
  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setViewportHeight(entry.contentRect.height);
      }
    });

    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const handleScroll = (event: UIEvent<HTMLDivElement>) => {
    setScrollTop(event.currentTarget.scrollTop);
  };

  // Virtual Window Indices Boundaries
  const totalCount = dataset.length;
  const totalHeight = totalCount * rowHeight;
  
  const startIndex = Math.max(0, Math.floor(scrollTop / rowHeight) - 2);
  const endIndex = Math.min(
    totalCount - 1,
    Math.floor((scrollTop + viewportHeight) / rowHeight) + 2
  );

  const visibleRows = useMemo(() => {
    const items: React.JSX.Element[] = [];
    for (let i = startIndex; i <= endIndex; i++) {
      const order = dataset[i];
      if (!order) continue;
      items.push(
        <div
          key={order.orderId}
          style={{
            position: 'absolute',
            top: `${i * rowHeight}px`,
            left: 0,
            right: 0,
            height: `${rowHeight}px`,
            display: 'grid',
            gridTemplateColumns: '2fr 2fr 2fr 2fr',
            alignItems: 'center',
            padding: '0 8px',
            borderBottom: '1px solid #eee',
            fontSize: 13,
            backgroundColor: i % 2 === 0 ? '#fff' : '#f9f9f9',
          }}
        >
          <span>{order.orderId}</span>
          <span>{order.instrument}</span>
          <span style={{ color: order.price >= 51000 ? '#16a34a' : '#dc2626' }}>
            {order.price.toFixed(2)}
          </span>
          <span>{order.volume.toFixed(4)}</span>
        </div>
      );
    }
    return items;
  }, [dataset, startIndex, endIndex, rowHeight]);

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      style={{
        position: 'relative',
        height: '100%',
        overflowY: 'auto',
        border: '1px solid #e5e7eb',
        contain: 'strict', // Memberitahu browser untuk mengisolasi rendering sub-tree
      }}
    >
      <div style={{ height: `${totalHeight}px`, position: 'relative' }}>
        {visibleRows}
      </div>
    </div>
  );
});
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Pola | Pendekatan Direct Rendering (Naive) | Pendekatan Debounce / Throttle Tradisional | Pendekatan Concurrent Scheduling (`useTransition`) |
| :--- | :--- | :--- | :--- |
| **Mekanika Eksekusi** | Render dieksekusi sinkron pada setiap event handler. | Eksekusi render ditunda secara artifisial via `setTimeout`. | Render dihitung secara spekulatif pada background task via time-slicing. |
| **Responsivitas Input (INP)** | **Sangat Buruk.** Main thread terblokir secara total selama durasi reconciler. | **Menengah.** Menunda kalkulasi, namun begitu dimulai tetap memblokir thread. | **Sangat Baik.** Komputasi render diinterupsi seketika saat user memberikan input baru. |
| **Latensi Visual UI** | Minimal jika dataset kecil, catastrophic freeze jika dataset masif. | Tertunda fix sesuai interval debounce (contoh: +300ms latency artifisial). | Adaptif: secepat kemampuan hardware klien (bisa < 5ms pada hardware cepat). |
| **Beban Memori (Footprint)** | Rendah (tidak ada state buffering ganda). | Rendah hingga Menengah (menyimpan closure timers). | Sedikit Lebih Tinggi (mempertahankan Work-in-Progress & Current tree bersamaan). |
| **User Experience (UX)** | Input ketikan drop characters (stutter). | UI terasa "berat" dan memiliki jeda sebelum merespons. | UI terasa responsif instan; bagian berat ter-update secara progresif. |
| **Kompleksitas Kode** | Sangat Sederhana. | Sederhana. Memerlukan penanganan teardown timer. | Memerlukan pemahaman state lifecycle & profiling lanes. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Suspense Fallback Flickering Pitfall
Ketika `useTransition` dipadukan dengan Suspense-driven Data Fetching, transisi state yang salah penanganan dapat menyebabkan transisi terjebak pada fallback rendering yang berkedip (*flash of loading UI*).
* **Failure Mode:** Menggunakan `setState` yang tidak ditandai transisi di dalam promise chains yang me-resolve data baru, memaksa sub-tree masuk ke mode Suspense fallback alih-alih mempertahankan layout lama.
* **Mitigasi:** Selalu bungkus eksekusi dispatch penentu rute/fetcher data di dalam cakupan `startTransition`.

### 2. Retensi Memory Leaks via Closed-Over Scopes pada Lanes Rendah
Jika sebuah transisi prioritas rendah dibatalkan karena ada 10 interaksi prioritas tinggi secara berturut-turut, React akan membuang Work-In-Progress tree yang sedang dihitung.
* **Failure Mode:** Jika render function komponen Anda mengalokasikan resources native di luar React (misalnya `new AbortController()`, instansiasi worker, atau append listener ke global target tanpa `useEffect`), memori tersebut akan bocor (*leak*) karena reconciler membuang tree tanpa memanggil unmount cleanup logic.
* **Aturan Kritis:** *Render phase functions MUST remain purely functional and free of side effects.* Side effects hanya diizinkan di dalam `useEffect` atau `useLayoutEffect`.

### 3. Layout Thrashing via Read-Write DOM Interleaving
Memanggil pembacaan ukuran layout geometri DOM (`offsetHeight`, `clientWidth`, `getComputedStyle`) tepat setelah menulis mutasi DOM (`element.style.width = ...`) mematikan optimasi browser rendering engine.
* **Failure Mode:** Browser dipaksa menghentikan pipeline parsing dan menjalankan synchronous recalculate-style & reflow berulang-ulang dalam 1 tick perulangan.
* **Mitigasi:** Baca semua ukuran DOM terlebih dahulu (Read Phase), kemudian terapkan semua mutasi kelas CSS atau style (Write Phase), atau gunakan `ResizeObserver`.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Menyelimuti Primitive State Setter dengan `useCallback` Tanpa Dependensi Berat
```typescript
// ANTI-PATTERN: Menambah overhead closure & allocation tanpa optimasi nyata
const handleClick = useCallback(() => {
  setCount(c => c + 1);
}, []); // Tidak memberikan dampak jika diteruskan ke native element <button>!

// CORRECT PATTERN:
// Cukup inline function kecuali diteruskan ke komponen anak yang di-memoize via React.memo
<button onClick={() => setCount(c => c + 1)}>Increment</button>
```

### Kesalahan 2: Membungkus Pembaruan Input Terkontrol di dalam `startTransition`
```typescript
// ANTI-PATTERN: Input kehilangan sinkronisasi dengan hardware typing buffer!
const [text, setText] = useState('');
const [isPending, startTransition] = useTransition();

const handleChange = (e) => {
  startTransition(() => {
    // FATAL: Ini akan membuat input terasa "laggy", karakter melompat atau kursor meloncat
    setText(e.target.value