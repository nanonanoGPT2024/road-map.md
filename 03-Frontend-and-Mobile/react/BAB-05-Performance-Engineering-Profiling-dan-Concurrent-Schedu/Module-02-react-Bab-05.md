# Kurikulum Rekayasa Perangkat Lunak Enterprise: React
## Kategori: 03-Frontend-and-Mobile
### BAB 05: Performance Engineering, Profiling, dan Concurrent Scheduler
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Internal Scheduler & Lane Model:** Membedah mekanisme *cooperative multitasking*, representasi 31-bit integer *Lanes*, dan siklus *workLoopConcurrent* dalam runtime Fiber React 18/19.
2. **Mengorkestrasikan Prioritas Rendering:** Mengimplementasikan pola penjadwalan mutasi state non-blocking menggunakan `useTransition`, `useDeferredValue`, dan custom scheduling hooks untuk mengoptimalkan Core Web Vitals (khususnya *Interaction to Next Paint* / INP).
3. **Menerapkan Programmatic Profiling:** Mengintegrasikan `<Profiler>` API level enterprise dengan *User Timing API* (W3C) dan OpenTelemetry untuk memonitor *render-duration*, *commit-duration*, serta de-opt reconciliation di pipeline CI/CD dan sistem monitoring produksi.
4. **Mencegah & Memitigasi Bottleneck Runtime:** Mendiagnosis fenomena *priority starvation*, *waterfall suspense*, *unintentional de-bouncing*, serta *memory retention/leaks* yang dipicu oleh Fiber dual-buffering dan async transitions.

---

### 2. Prerequisite

Peserta wajib menguasai:
* **Fiber Reconciliation Dasar:** Siklus hidup Render Phase (Reconciliation) dan Commit Phase, struktur data Fiber (*child*, *sibling*, *return*, *alternate*).
* **JavaScript Concurrency Model:** Event Loop, Microtasks (`queueMicrotask`, `Promise`), Macrotasks (`MessageChannel`, `setTimeout`), dan Rendering Pipeline browser (`requestAnimationFrame`, *layout*, *paint*, *composite*).
* **TypeScript Advanced:** Generic constraints, mapped types, discriminated unions, dan typing modul React DOM/Internals.
* **Dasar Chrome DevTools Performance Panel:** Identifikasi *Long Tasks* (>50ms), flame graph analysis, dan tracing thread visual browser.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Evolusi dari BatchedUpdates ke Bitmask Priority Lanes
Pada React versi awal, scheduling prioritas mengandalkan model hierarki angka linear (*expiration times*). Model ini memiliki limitasi fundamental: tidak mampu mengekspresikan relasi batching diskrit non-linear (misalnya: menggabungkan dua task unrelated tanpa memproses task di antara keduanya).

React Concurrent memperkenalkan **Lanes Model**. Lane adalah bit field 31-bit di mana setiap bit merepresentasikan subset kapasitas eksekusi:

```
0b0000000000000000000000000000001 -> SyncLane (User click, direct input)
0b0000000000000000000000000000010 -> InputContinuousHydrationLane
0b0000000000000000000000000000100 -> InputContinuousLane (Mouse move, scroll)
0b0000000000000000000000000001000 -> DefaultHydrationLane
0b0000000000000000000000000010000 -> DefaultLane (Normal setState, network responses)
...
0b0000000001111111111111100000000 -> TransitionLanes (16 bits: useTransition, startTransition)
...
0b0100000000000000000000000000000 -> OffscreenLane / IdleLane
```

Operasi bitwise digunakan untuk kalkulasi performa tinggi:
* **Penentuan prioritas tertinggi:** Mengisolasi bit paling signifikan yang aktif:
  $$\text{highestPriorityLane} = \text{lanes} \ \& \ (-\text{lanes})$$
* **Penggabungan lane (Merge):** `lanesA | lanesB`
* **Pengecekan overlap:** `(lanesA & lanesB) !== 0`

#### 3.2. Engine Scheduler: Cooperative Multitasking via `MessageChannel`
React tidak menggunakan `requestIdleCallback` di lingkungan browser produksi karena memiliki batasan frame rate yang tidak konsisten (biasanya dibatasi hingga 20Hz oleh browser) dan interval yang tidak dapat diprediksi.

React Scheduler mengimplementasikan polyfill *cooperative time-slicing* dengan alokasi target frame budget sebesar **5ms** (`frameInterval = 5`). Mekanismenya:
1. Scheduler mengantrekan task ke sebuah min-heap priority queue (`taskQueue` vs `timerQueue`).
2. Saat thread utama diizinkan berjalan, scheduler mengeksekusi *work loop*.
3. Setiap unit kerja Fiber diproses dalam fungsi `workLoopConcurrent`:

```typescript
function workLoopConcurrent() {
  // Lakukan komparasi performa dan alokasi waktu
  while (workInProgress !== null && !shouldYield()) {
    performUnitOfWork(workInProgress);
  }
}
```

4. Fungsi `shouldYield()` memvalidasi:
   $$\text{performance.now()} \ge \text{deadline}$$
5. Jika waktu $\ge 5\text{ms}$ dan masih terdapat sisa tree traversal, Fiber melepaskan eksekusi thread ke browser (*yields control*) via:
   ```javascript
   const channel = new MessageChannel();
   const port = channel.port2;
   channel.port1.onmessage = performWorkUntilDeadline;
   port.postMessage(null);
   ```
   Penggunaan Macrotask via `MessageChannel` memastikan browser memiliki kesempatan untuk mengeksekusi Style Recalculation, Layout, Paint, dan merespons interaksi input pengguna sebelum melanjutkan rendering React berikutnya.

#### 3.3. Dual-Buffering Engine & Interruption Cycle
* **Current Tree:** Merepresentasikan tree yang saat ini ter-mount dan aktif di DOM.
* **Work-In-Progress (WIP) Tree:** Tree klon yang sedang dimutasi di memori pada Render Phase.

Ketika update berprioritas rendah (`TransitionLane`) sedang berjalan di WIP Tree dan user melakukan interaksi berprioritas tinggi (`SyncLane`):
1. Scheduler menginterupsi eksekusi `workLoopConcurrent`.
2. Pointer WIP di-discard atau ditangguhkan.
3. React beralih memproses `SyncLane`, membangun WIP Tree baru untuk input tersebut.
4. WIP Tree berprioritas tinggi di-commit ke DOM.
5. Scheduler me-restart atau me-resume pengerjaan `TransitionLane` dari checkpoint terakhir yang konsisten.

---

### 4. Why & What

| Dimensi | Sinkronus (Legacy React) | Konkuren (Modern React Enterprise) |
| :--- | :--- | :--- |
| **Model Eksekusi** | Run-to-completion (Monolitik, blocking). | Time-sliced (Interruptible, cooperative scheduling). |
| **User Interaction** | Input freeze saat reconciliation komponen kompleks berlangsung. | Zero-latency feedback untuk event interaktif (`Sync`/`Continuous`). |
| **Priority Handling** | FIFO (First-In, First-Out) update queue. | Preemptive priority-based interruption berbasis Lanes. |
| **Metrik Terdampak** | INP buruk (>200ms), Long Tasks mendominasi main thread. | Sub-50ms INP, frame rate terjaga di 60/120 FPS. |
| **State Consistency** | Single intermediate frame langsung masuk paint cycle. | Virtual intermediate states ditahan di memori hingga stabil. |

---

### 5. How (Workflow Detail)

Alur internal penjadwalan concurrent dari interaksi ke commit:

```
[User Trigger: e.g., Filter Input]
               │
               ▼
   [startTransition Callback]
               │
               ▼
[Assign TransitionLane to Update] ──► (Bitmask marking pada Fiber node)
               │
               ▼
 [markUpdateLaneFromFiberToRoot] ───► (Bubble up lanes ke HostRootFiber)
               │
               ▼
    [ensureRootIsScheduled]
               │
               ├───────────────────────────────────────────┐
               ▼                                           ▼
      {Is Priority higher?}                     {Sync or Async Work?}
               │                                           │
         Yes ──┴──► Interrupt Current WIP                  ▼
                                            [Scheduler_scheduleCallback]
                                                           │
                                                           ▼
                                            [MessageChannel Port Trigger]
                                                           │
                                                           ▼
                                                [performConcurrentWork]
                                                           │
                                    ┌──────────────────────┴─────────────────────┐
                                    ▼                                            ▼
                           [workLoopConcurrent]                         [shouldYield() == true]
                                    │                                            │
                                    ▼                                            ▼
                           [Complete Unit of Work]                      [Yield to Main Thread]
                                    │                                      (Post Message)
                                    ▼
                         [Render Phase Selesai?]
                                    │
                                   Yes
                                    ▼
                          [Commit Phase: DOM Mut] ──► (Synchronous & Non-interruptible)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional Single-Runway
Bayangkan sebuah bandara dengan satu landasan pacu (*Single Thread Main JS Runtime*):
* **Legacy Mode:** Pesawat kargo raksasa (*Heavy Re-rendering 10,000 components*) mendarat. Selama proses pendaratan dan bongkar muat yang lambat, jet eksekutif darurat medis (*User Click / Key Press*) tertahan di udara, kehabisan bahan bakar (*Dropped frames / Unresponsive UI*).
* **Concurrent Mode:** Pesawat kargo mendarat bertahap menggunakan taxiway transit. Menara pengawas (*Scheduler*) mendeteksi panggilan darurat medis (*SyncLane*). Pesawat kargo diinstruksikan menepi (*interruptible render*), jet medis diberi hak mendarat instan (*0ms latency response*). Setelah landasan steril, pesawat kargo melanjutkan perjalanannya.

#### Arsitektur Transisi Bitmask Lanes & Scheduling Loop
```
Main Thread:
═════════════════════════════════════════════════════════════════════════════════════════► Time
  [Frame 1: 5ms]         [Yield: 1ms]   [Frame 2: 5ms]         [Interrupted!]   [Sync Task: 2ms]
┌──────────────────────┐  Layout/Paint ┌──────────────────────┐ User Click Event ┌──────────────┐
│ workLoopConcurrent() │ ────────────► │ workLoopConcurrent() │ ───────────────► │ Flush Sync   │
│ Fiber A -> B -> C    │               │ Fiber D -> E         │                  │ Commit Immed.│
└──────────────────────┘               └──────────────────────┘                  └──────────────┘
           ▲                                      ▲                                     │
           │                                      │                                     ▼
 ┌─────────────────────────────────────────────────────────────────┐               [Paint Screen]
 │ react/packages/scheduler/src/forks/Scheduler.js                 │
 │ Priority Queue: [SyncLane (Immediate)] > [TransitionLane (Idle)]│
 └─────────────────────────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Perbandingan Mutasi Blocking vs Non-Blocking
File: `src/components/SimpleTransitionDemo.tsx`

```tsx
import React, { useState, useTransition, ChangeEvent, ReactElement } from 'react';

export const SimpleTransitionDemo = (): ReactElement => {
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [deferredResults, setDeferredResults] = useState<string[]>([]);
  const [isPending, startTransition] = useTransition();

  const handleSearch = (e: ChangeEvent<HTMLInputElement>): void => {
    const value = e.target.value;
    
    // Prioritas Tinggi (SyncLane): Immediate visual feedback pada input field
    setSearchTerm(value);

    // Prioritas Rendah (TransitionLane): Mengizinkan interupsi jika user mengetik karakter berikutnya
    startTransition(() => {
      const items: string[] = [];
      for (let i = 0; i < 20000; i++) {
        items.push(`${value} - Data Index Record #${i}`);
      }
      setDeferredResults(items);
    });
  };

  return (
    <div style={{ padding: '24px', fontFamily: 'sans-serif' }}>
      <h3>Concurrent Transition Demo</h3>
      <input
        type="text"
        value={searchTerm}
        onChange={handleSearch}
        placeholder="Ketik untuk simulasi beban..."
        style={{ padding: '8px', width: '300px' }}
      />
      {isPending && <span style={{ marginLeft: '12px', color: '#ff9800' }}>Menjadwalkan ulang render...</span>}
      <ul style={{ maxHeight: '300px', overflowY: 'auto', marginTop: '16px' }}>
        {deferredResults.slice(0, 100).map((item, idx) => (
          <li key={idx}>{item}</li>
        ))}
      </ul>
    </div>
  );
};
```

#### 7.2. Practical Example: Enterprise High-Frequency Data Matrix Scheduler
Sistem visualisasi matriks portofolio finansial dengan profiling otomatis dan adaptive frame degradation.

File: `src/components/EnterpriseFinancialMatrix.tsx`

```tsx
import React, { 
  useState, 
  useTransition, 
  useDeferredValue, 
  useMemo, 
  Profiler, 
  ProfilerOnRenderCallback, 
  ReactElement 
} from 'react';

// Tipe Data untuk Domain Keuangan
export interface InstrumentTicket {
  id: string;
  ticker: string;
  nominal: number;
  delta: number;
  gamma: number;
  volatility: number;
  lastUpdated: number;
}

// Global Tracing Sink untuk OpenTelemetry / APM ingestion
const reportProfilerMetrics: ProfilerOnRenderCallback = (
  id,
  phase,
  actualDuration,
  baseDuration,
  startTime,
  commitTime
) => {
  // Hanya agregasikan metrik jika melampaui batas toleransi INP Budget (16ms = 60fps)
  if (actualDuration > 16.0) {
    const payload = {
      profilerId: id,
      phase,
      actualDurationMs: Number(actualDuration.toFixed(2)),
      baseDurationMs: Number(baseDuration.toFixed(2)),
      startTime,
      commitTime,
      timestamp: Date.now(),
    };
    
    // Simulasi pengiriman telemetry non-blocking
    if (typeof window !== 'undefined' && 'sendBeacon' in navigator) {
      navigator.sendBeacon('/api/telemetry/profiler', JSON.stringify(payload));
    } else {
      console.warn(`[PERF ALERT] Component ${id} [${phase}] took ${actualDuration.toFixed(2)}ms`);
    }
  }
};

const HeavyRow = ({ data }: { data: InstrumentTicket }): ReactElement => {
  // Komputasi matematis kalkulasi Greeks sintetik (simulasi render cost)
  const syntheticCalculation = useMemo(() => {
    let acc = 0;
    for (let i = 0; i < 5000; i++) {
      acc += Math.sin(data.delta) * Math.cos(data.gamma) * Math.sqrt(data.volatility + i);
    }
    return acc.toFixed(4);
  }, [data.delta, data.gamma, data.volatility]);

  return (
    <tr style={{ borderBottom: '1px solid #e0e0e0', fontSize: '13px' }}>
      <td style={{ padding: '8px' }}>{data.ticker}</td>
      <td style={{ padding: '8px' }}>{data.nominal.toLocaleString('en-US', { style: 'currency', currency: 'USD' })}</td>
      <td style={{ padding: '8px', color: data.delta >= 0 ? '#2e7d32' : '#d32f2f' }}>{data.delta.toFixed(4)}</td>
      <td style={{ padding: '8px' }}>{data.gamma.toFixed(4)}</td>
      <td style={{ padding: '8px' }}>{(data.volatility * 100).toFixed(2)}%</td>
      <td style={{ padding: '8px' }}>{syntheticCalculation}</td>
    </tr>
  );
};

export const EnterpriseFinancialMatrix = (): ReactElement => {
  const [filterThreshold, setFilterThreshold] = useState<number>(0);
  const [datasetSize, setDatasetSize] = useState<number>(3000);
  const [isPending, startTransition] = useTransition();

  // Inisialisasi Mock Data Generator
  const rawDataset: InstrumentTicket[] = useMemo(() => {
    const array: InstrumentTicket[] = new Array(datasetSize);
    for (let i = 0; i < datasetSize; i++) {
      array[i] = {
        id: `TICK-${i}`,
        ticker: `ASSET-${(i % 100).toString().padStart(3, '0')}`,
        nominal: Math.random() * 1_000_000,
        delta: (Math.random() - 0.5) * 2,
        gamma: Math.random() * 0.1,
        volatility: Math.random() * 0.8,
        lastUpdated: Date.now(),
      };
    }
    return array;
  }, [datasetSize]);

  // Deferred State untuk filtering kompleks non-blocking
  const deferredFilter = useDeferredValue(filterThreshold);

  const filteredData = useMemo(() => {
    return rawDataset.filter((item) => item.nominal >= deferredFilter);
  }, [rawDataset, deferredFilter]);

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const nextVal = Number(e.target.value);
    // Prioritas Default untuk responsivitas dragging slider
    setFilterThreshold(nextVal);
  };

  const handleDatasetScale = (size: number): void => {
    // Transisi massal didelegasikan ke TransitionLane agar tidak membekukan DOM
    startTransition(() => {
      setDatasetSize(size);
    });
  };

  return (
    <Profiler id="EnterpriseFinancialMatrix-Root" onRender={reportProfilerMetrics}>
      <div style={{ padding: '24px', backgroundColor: '#fcfcfc', color: '#111' }}>
        <header style={{ marginBottom: '16px' }}>
          <h2>Institutional Orderbook & Risk Matrix</h2>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center', margin: '16px 0' }}>
            <label htmlFor="filter-slider" style={{ fontWeight: 'bold' }}>
              Minimum Nominal Filter: ${filterThreshold.toLocaleString()}
            </label>
            <input
              id="filter-slider"
              type="range"
              min={0}
              max={1_000_000}
              step={10_000}
              value={filterThreshold}
              onChange={handleSliderChange}
              style={{ width: '250px' }}
            />
            {filterThreshold !== deferredFilter && (
              <span style={{ fontSize: '12px', color: '#ed6c02', fontWeight: 600 }}>
                Lagging update behind interactive thread...
              </span>
            )}
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button 
              disabled={isPending} 
              onClick={() => handleDatasetScale(1000)}
              style={{ padding: '6px 12px', cursor: 'pointer' }}
            >
              Scale 1K
            </button>
            <button 
              disabled={isPending} 
              onClick={() => handleDatasetScale(5000)}
              style={{ padding: '6px 12px', cursor: 'pointer' }}
            >
              Scale 5K (Stress Test)
            </button>
            <button 
              disabled={isPending} 
              onClick={() => handleDatasetScale(10000)}
              style={{ padding: '6px 12px', cursor: 'pointer' }}
            >
              Scale 10K (Concurrent Workload)
            </button>
          </div>
        </header>

        <main>
          <div style={{ opacity: isPending ? 0.6 : 1, transition: 'opacity 150ms ease' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #333' }}>
                  <th>Instrument</th>
                  <th>Nominal Exposures</th>
                  <th>Delta (Δ)</th>
                  <th>Gamma (Γ)</th>
                  <th>Impl. Volatility</th>
                  <th>Synthetic Greeks (Sync CPU)</th>
                </tr>
              </thead>
              <tbody>
                {filteredData.slice(0, 500).map((ticket) => (
                  <HeavyRow key={ticket.id} data={ticket} />
                ))}
              </tbody>
            </table>
          </div>
          {filteredData.length > 500 && (
            <p style={{ textAlign: 'center', color: '#666', marginTop: '12px' }}>
              Truncated for DOM safety. Menampilkan 500 dari {filteredData.length} records.
            </p>
          )}
        </main>
      </div>
    </Profiler>
  );
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Platform Core Trading Analytics (FinTech) berskala Tier-1 melayani streaming 20.000 events/detik via WebSocket. Pengguna mengeluhkan browser mengalami *freezing* total selama 2–4 detik ketika membuka menu dropdown atau mengetik filter pencarian portofolio pada jam pembukaan bursa (peak market hours).

#### Problem Breakdown
1. **INP Terdegradasi:** Nilai P99 INP melonjak hingga **1.850ms** (Batas aman Core Web Vitals < 200ms).
2. **Main Thread Monopolization:** Setiap pesan WebSocket memicu update state sinkronus ke store global (Redux/Zustand), menjalankan reconciliation serentak di 40 sub-komponen dashboard secara sinkronus.
3. **Event Queue Starvation:** Event input pengguna (`KeyboardEvent`, `PointerEvent`) tertahan di browser queue karena JavaScript thread terus-menerus mengeksekusi long tasks berdurasi >120ms.

#### Solusi Arsitektural Menggunakan Concurrent Scheduling
1. **Lanes Isolation:**
   WebSocket stream diarahkan ke layer buffer memory murni (off-react state). Update state UI diturunkan prioritasnya menggunakan `startTransition`.
2. **High-Frequency Batching Engine:**
   Dibuat custom batch scheduler yang mengumpulkan WebSocket chunks dan mengaplikasikannya via `startTransition` ber-budget waktu:

```typescript
// Production Snippet: WebSocket Ingestion De-coupling Engine
import { startTransition } from 'react';

class MarketDataBatchCoordinator {
  private buffer: Map<string, InstrumentTicket> = new Map();
  private isFlushScheduled = false;
  private onDispatch: (aggregated: InstrumentTicket[]) => void;

  constructor(onDispatch: (aggregated: InstrumentTicket[]) => void) {
    this.onDispatch = onDispatch;
  }

  public ingest(payload: InstrumentTicket): void {
    this.buffer.set(payload.id, payload);
    this.scheduleFlush();
  }

  private scheduleFlush(): void {
    if (this.isFlushScheduled) return;
    this.isFlushScheduled = true;

    // Alokasikan ke Macrotask berprioritas rendah menggunakan requestAnimationFrame + scheduler
    requestAnimationFrame(() => {
      const batchedItems = Array.from(this.buffer.values());
      this.buffer.clear();
      this.isFlushScheduled = false;

      // Gunakan Lane Transition agar jika user melakukan klik atau filter, render ini diinterupsi!
      startTransition(() => {
        this.onDispatch(batchedItems);
      });
    });
  }
}
```

#### Hasil Metrik
* **INP (P99):** Turun dari **1.850ms** menjadi **48ms** (Peningkatan sebesar 97.4%).
* **Long Tasks:** Berkurang sebesar 84% pada flame chart Chrome DevTools.
* **CPU Throttle Resistance:** Dashboard tetap responsif terhadap pengetikan pada CPU 4x slowdown simulation.

---

### 9. Trade-offs

```
                  ┌──────────────────────────────────────────┐
                  │      Concurrent Scheduling Matrix        │
                  └──────────────────────────────────────────┘
                         ▲                          ▲
                         │                          │
        High Interactivity (Low INP)       Memory Overhead (Dual-Buffering)
                         │                          │
                         ▼                          ▼
       ┌───────────────────────────────────────────────────────────────┐
       │ - UI responsif thd input         - Fiber duplicate allocation │
       │ - Render phase interruptible     - GC pressure under load     │
       │ - Non-blocking frame delivery    - Code complexity & tearing  │
       └───────────────────────────────────────────────────────────────┘
```

| Parameter | Pendekatan Synchronous | Pendekatan Concurrent / Time-Sliced |
| :--- | :--- | :--- |
| **Performance (INP)** | Buruk pada komponen berat (>200ms). | Sangat Baik (Mendekati native speed, <50ms). |
| **Throughput Mutasi** | Maksimal: Re-render tereksekusi tanpa jeda. | Lebih rendah: Scheduler memperkenalkan overhead evaluasi budget 5ms. |
| **Memory Footprint** | Rendah: Hanya 1 snapshot tree aktif di heap. | Tinggi: Dual tree allocations + persistent closure pending states. |
| **DX & Architectural Cost** | Sederhana: Predictable stack trace visualizer. | Kompleks: Asynchronous stack trace, potensi *tear states*, edge cases. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Membungkus Synchronous Side Effects di dalam `startTransition`
* *Anti-Pattern:*
  ```typescript
  startTransition(() => {
    // FATAL: Side effect dieksekusi selama phase scheduling
    fetch('/api/data'); 
    localStorage.setItem('key', value);
    setState(value);
  });
  ```
* *Perbaikan:* `startTransition` dirancang **hanya** untuk membungkus updater state React. Eksekusi network I/O atau storage access di luar transisi.

#### 2. Starvation Rendah Prioritas Akibat Infinite Updates Loop
* *Gejala:* Konten transisi tidak pernah selesai ter-render (*isPending selamanya true*).
* *Penyebab:* Terdapat event continuous (misal listener scroll tanpa debounce) yang terus memicu `SyncLane` atau `InputContinuousLane`, sehingga Scheduler meng-abort dan me-restart `TransitionLane` berulang kali.
* *Solusi:* Implementasikan starvation protection menggunakan lane auto-escalation timer atau berikan throttling pada producer event berprioritas tinggi.

#### 3. State Tearing pada Global Store Eksternal
* *Gejala:* Komponen anak membaca nilai store yang berbeda dari komponen induk dalam frame yang sama (*Inconsistent UI snapshot*).
* *Penyebab:* Penggunaan mutasi variabel mutable/store custom non-React yang tidak terintegrasi dengan bitmask concurrency.
* *Solusi:* Selalu gunakan `useSyncExternalStore` untuk integrasi global store (seperti Redux/Zustand) agar tearing dideteksi dan di-flush secara atomik.

---

### 11. Best Practices (Production Checklist)

- [ ] **Lanes Segregation:** Pisahkan state interaksi instan (`searchTerm`, `isExpanded`) dari state komputasi berat (`analyticsCalculations`, `massiveListProjection`).
- [ ] **Profiler Tree Shaking:** Nonaktifkan custom `<Profiler>` tracing logic di production build bundle jika tidak terhubung ke ingest server APM, guna memotong traversal overhead.
- [ ] **Suspense Boundary Topology:** Pecah monolithic components menjadi isolated Suspense boundaries; pastikan slow-loading async boundaries tidak memblok UI shell global.
- [ ] **Sanitasi useDeferredValue:** Berikan dependency check atau React Compiler memoization pada komponen yang mengonsumsi `useDeferredValue` untuk mencegah redundant tree reconciliations:
  ```typescript
  const deferredQuery = useDeferredValue(query);
  const memoizedList = useMemo(() => <HeavyList query={deferredQuery} />, [deferredQuery]);
  ```
- [ ] **INP Real-User Monitoring (RUM):** Setup monitoring metrik `web-vitals` library v4+ untuk menangkap exact `interactionTarget` dan mendeteksi korelasi dengan long-running transitions.

---

### 12. Hands-on Practice

Buat dan simpan struktur praktikum ini pada direktori: `hands-on/m02/`

#### Struktur Proyek
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── index.tsx
│   ├── App.tsx
│   ├── metrics/
│   │   └── traceSink.ts
│   └── components/
│       ├── HeavyWorkloadGrid.tsx
│       └── ConcurrentSearchEngine.tsx
```

#### File: `hands-on/m02/package.json`
```json
{
  "name": "hands-on-concurrent-scheduler",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.4.5",
    "vite": "^5.2.11"
  }
}
```

#### File: `hands-on/m02/src/metrics/traceSink.ts`
```typescript
import { ProfilerOnRenderCallback } from 'react';

export interface PerfMetricTrace {
  id: string;
  phase: 'mount' | 'update';
  actualDuration: number;
  baseDuration: number;
  timestamp: number;
}

export const inMemoryTracer: PerfMetricTrace[] = [];

export const handleEnterpriseProfileTrace: ProfilerOnRenderCallback = (
  id,
  phase,
  actualDuration,
  baseDuration
) => {
  const metric: PerfMetricTrace = {
    id,
    phase,
    actualDuration: Number(actualDuration.toFixed(2)),
    baseDuration: Number(baseDuration.toFixed(2)),
    timestamp: performance.now(),
  };

  inMemoryTracer.push(metric);
  
  if (actualDuration > 5) {
    console.info(
      `%c[SCHEDULER TRACE: ${id}] Phase: ${phase} | Duration: ${actualDuration.toFixed(2)}ms`,
      'color: #00bcd4; font-weight: bold;'
    );
  }
};
```

#### File: `hands-on/m02/src/components/HeavyWorkloadGrid.tsx`
```typescript
import React, { ReactElement, useMemo } from 'react';

interface GridProps {
  density: number;
  pattern: string;
}

export const HeavyWorkloadGrid = React.memo(({ density, pattern }: GridProps): ReactElement => {
  const gridCells = useMemo(() => {
    const total = density * 100;
    const items: Array<{ id: number; val: number }> = new Array(total);
    for (let i = 0; i < total; i++) {
      // Injeksi algoritma deterministik berat
      let comp = 0;
      for (let j = 0; j < 300; j++) {
        comp += Math.sin(i) * Math.cos(j);
      }
      items[i] = { id: i, val: comp };
    }
    return items;
  }, [density]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(60px, 1fr))', gap: '4px', marginTop: '12px' }}>
      {gridCells.map((cell) => (
        <div 
          key={cell.id} 
          style={{ 
            padding: '4px', 
            fontSize: '9px', 
            backgroundColor: cell.val > 0 ? '#e8f5e9' : '#ffebee', 
            border: '1px solid #ccc',
            textAlign: 'center'
          }}
        >
          {pattern}-{cell.id}
        </div>
      ))}
    </div>
  );
});
```

#### File: `hands-on/m02/src/components/ConcurrentSearchEngine.tsx`
```typescript
import React, { useState, useTransition, useDeferredValue, ReactElement } from 'react';
import { HeavyWorkloadGrid } from './HeavyWorkloadGrid';

export const ConcurrentSearchEngine = (): ReactElement => {
  const [interactiveInput, setInteractiveInput] = useState<string>('INIT');
  const [gridDensity, setGridDensity] = useState<number>(30);
  const [isPending, startTransition] = useTransition();

  // Deferring teks pola agar input DOM tetap instan merespons ketukan keyboard
  const deferredPattern = useDeferredValue(interactiveInput);

  const handleDensityScale = (val: number): void => {
    startTransition(() => {
      setGridDensity(val);
    });
  };

  return (
    <div style={{ padding: '16px', border: '1px solid #ddd', borderRadius: '8px' }}>
      <h3>Concurrent Workload Laboratory</h3>
      <div style={{ display: 'flex', gap: '16px', marginBottom: '16px' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '4px' }}>Input Instan (SyncLane):</label>
          <input
            type="text"
            value={interactiveInput}
            onChange={(e) => setInteractiveInput(e.target.value)}
            style={{ padding: '8px', fontSize: '14px', width: '220px' }}
          />
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: '4px' }}>Tingkat Beban (Grid Density):</label>
          <button onClick={() => handleDensityScale(20)} style={{ marginRight: '6px' }}>Ringan (2k)</button>
          <button onClick={() => handleDensityScale(60)} style={{ marginRight: '6px' }}>Sedang (6k)</button>
          <button onClick={() => handleDensityScale(120)}>Ekstrem (12k)</button>
        </div>
      </div>

      <div style={{ marginBottom: '8px' }}>
        Status Transisi: {isPending ? <strong style={{ color: '#d32f2f' }}>YIELDING / RENDERING...</strong> : <strong style={{ color: '#388e3c' }}>IDLE</strong>}
      </div>

      <HeavyWorkloadGrid density={gridDensity} pattern={deferredPattern} />
    </div>
  );
};
```

#### File: `hands-on/m02/src/App.tsx`
```typescript
import React, { Profiler, ReactElement } from 'react';
import { ConcurrentSearchEngine } from './components/ConcurrentSearchEngine';
import { handleEnterpriseProfileTrace } from './metrics/traceSink';

export const App = (): ReactElement => {
  return (
    <Profiler id="RootApplicationProfiler" onRender={handleEnterpriseProfileTrace}>
      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '32px 16px' }}>
        <h1>React Scheduler & Profiling Deep-Dive</h1>
        <p>Buka Chrome DevTools Console dan Performance Panel untuk memverifikasi alokasi frame budget.</p>
        <ConcurrentSearchEngine />
      </main>
    </Profiler>
  );
};
```

#### File: `hands-on/m02/src/index.tsx`
```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';

const container = document.getElementById('root');
if (!container) {
  throw new Error('Target container root tidak ditemukan pada DOM.');
}

const root = ReactDOM.createRoot(container);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

---

### 13. Exercise

#### Level: Easy
* **Instruksi:** Buat sebuah custom hook bernama `useDebouncedTransition(value: string, delayMs: number)` yang menggabungkan teknik debouncing tradisional untuk payload network dengan `useTransition` untuk penjadwalan UI update.
* **Ekspektasi Output:** Hook mengembalikan `[deferredValue, isPending]` di mana network call tidak di-spam dan frame rendering UI tidak drop di bawah 60 FPS.

#### Level: Medium
* **Instruksi:** Implementasikan sebuah komponen higher-order (HOC) bernama `withRenderBudget(Component, budgetMs)`. HOC ini membungkus komponen dalam `<Profiler>` dan otomatis mendeteksi jika rata-rata render time komponen selama 5 cycle terakhir melebihi `budgetMs`. Jika melebihi, HOC harus mengaktifkan fallback low-fidelity mode (misalnya me-render static placeholders ketimbang interactive elements).
* **Ekspektasi Output:** Komponen dinamis yang mampu menurunkan derajat fidelitas visual secara otomatis jika perangkat klien memiliki CPU throttle yang parah.

#### Level: Hard
* **Instruksi:** Bangun custom Lane starvation emulator. Buat loop background via `setInterval` yang memicu update berprioritas `SyncLane` setiap 4ms. Terapkan state update berprioritas `TransitionLane`. Buktikan bahwa update `Transition` terhambat, kemudian implementasikan mekanisme *emergency flush* yang mengelevasi `TransitionLane` menjadi `SyncLane` setelah waktu tunggu melebihi 500ms.
* **Ekspektasi Output:** Replikasi programmatic dari starvation-recovery model internal React Fiber scheduler.

---

### 14. Challenge

#### Skenario:
Anda adalah Principal Architect pada aplikasi platform Desain Grafis Kolaboratif berbasis web (serupa Figma/Canva). Kanvas mendukung hingga 15.000 elemen vektor individual yang di-render via React Virtual DOM ke SVG tree. 

Saat seorang pengguna menyeret (*dragging*) seleksi box yang mencakup 2.000 vektor sekaligus:
1. Koordinat bounding box harus bergerak dengan frame-rate murni **60 FPS / 120 FPS** (Sync Priority).
2. Properti kalkulasi analitik dimensi, snap grid lines, dan kolaborator kursor broadcast via WebRTC harus diperbarui secara real-time tanpa mengorbankan input latency dragging kursor.
3. Seluruh telemetry profiler harus dikirim ke OpenTelemetry Collector secara non-blocking tanpa mendegradasi heap memory browser.

#### Persyaratan Arsitektur:
* Desain arsitektur penjadwalan state multi-tier yang mengombinasikan `MessageChannel`, `useSyncExternalStore`, bitwise isolation, dan `<Profiler>`.
* Selesaikan kasus di atas tanpa menggunakan library eksternal (murni vanilla TypeScript dan React 18/19 primitives).
* Buat dokumen arsitektur komparatif dan implementasi kode proof-of-concept (PoC) lengkap yang mencakup error mitigation terhadap kemungkinan state desynchronization (*state tearing*).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa alasan utama React beralih dari linear expiration times ke 31-bit integer Lanes model?
   * A. Mengurangi konsumsi memori heap JavaScript hingga 90%.
   * B. Memungkinkan ekspresi multi-task grouping yang non-linear dan diskrit.
   * C. Menghilangkan kebutuhan Commit Phase pada rendering browser.
   * D. Memaksa seluruh render berjalan secara paralel pada Web Worker.

2. API scheduling browser apa yang digunakan secara default oleh React Scheduler untuk time-slicing?
   * A. `requestIdleCallback`
   * B. `setTimeout(fn, 0)`
   * C. `MessageChannel`
   * D. `queueMicrotask`

3. Berapa target frame budget default yang dialokasikan oleh React Scheduler sebelum melepaskan (*yield*) eksekusi kembali ke thread utama browser?
   * A. 1ms
   * B. 5ms
   * C. 16.6ms
   * D. 50ms

4. Manakah fase dalam siklus rendering React yang dijamin bersifat sinkronus dan tidak dapat diinterupsi (*non-interruptible*)?
   * A. Render Phase
   * B. Reconciliation Phase
   * C. Commit Phase
   * D. Scheduling Phase

5. Nilai boolean `isPending` yang dikembalikan oleh `useTransition` menunjukkan:
   * A. Sedang terjadi HTTP Network Request yang belum selesai.
   * B. React sedang mengerjakan WIP Fiber Tree untuk transisi tersebut di latar belakang.
   * C. Browser mengalami Out-of-Memory (OOM) error.
   * D. Komponen anak sedang menunggu fallback `<Suspense>` selesai di-mount.

#### Bagian 2: Intermediate (Analisis Benar/Salah & Pilihan Ganda)
6. *True/False:* Membungkus update state ke dalam `startTransition` menjamin kode tersebut dieksekusi di Web Worker terpisah di luar thread utama browser.
7. *True/False:* React Profiler API (`onRender`) mencatat fase commit browser (Layout & Paint ke pixel layar) secara langsung dalam metrik `actualDuration`.
8. Apa yang membedakan prioritas `SyncLane` dari `InputContinuousLane`?
   * A. `SyncLane` digunakan untuk klik mouse diskrit, sedangkan `InputContinuousLane` digunakan untuk event terus-menerus seperti drag dan hover.
   * B. `InputContinuousLane` memiliki prioritas lebih tinggi daripada `SyncLane`.
   * C. `SyncLane` diproses melalui time-slicing 5ms, sedangkan `InputContinuousLane` tidak pernah di-yield.
   * D. Tidak ada perbedaan, keduanya diabaikan di lingkungan React production.

9. Manakah skenario di bawah ini yang memicu terjadinya *Priority Starvation* pada React Scheduler?
   * A. Terlalu banyak komponen menggunakan memoization `React.memo`.
   * B. Aliran update berprioritas tinggi (`SyncLane`) yang konstan dan tidak pernah berhenti memblok eksekusi `TransitionLane`.
   * C. Penggunaan hook `useDeferredValue` pada level root aplikasi.
   * D. Server me-render komponen menggunakan dynamic streaming SSR.

10. Mengapa `useSyncExternalStore` wajib digunakan untuk sinkronisasi state eksternal pada Concurrent React, ketimbang kombinasi `useEffect` + `useState` biasa?
    * A. Menghindari alokasi microtask berlebihan.
    * B. Mencegah fenomena *state tearing* akibat pembacaan intermediate value yang tidak sinkron di Render Phase.
    * C. Memastikan library pihak ketiga dapat berjalan secara offline.
    * D. Memotong durasi bundle size JavaScript hingga 50%.

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario A:** Pada dashboard enterprise, engineer membungkus fungsi parsing file CSV lokal berukuran 50MB (yang membutuhkan waktu CPU 1.2 detik) langsung di dalam `startTransition(() => { parseCsvSync(file); })`. Mengapa UI browser tetap mengalami freezing total selama 1.2 detik tersebut, dan bagaimana perbaikan arsitektural yang tepat?
12. **Skenario B:** Sebuah komponen tabel virtual menampilkan 5.000 transaksi. Saat input filter diketik cepat, pengguna melaporkan teks yang diketik terasa melompat-lompat dan terpotong. Dari inspeksi flame chart, diketahui developer menggunakan `const [query, setQuery] = useState('')` dan membungkus `setQuery` ke dalam `startTransition`. Identifikasi kegagalan pola ini dan berikan solusinya.
13. **Skenario C:** Sistem monitoring produksi APM melaporkan bahwa nilai `actualDuration` pada sebuah `<Profiler>` root stabil di bawah 4ms, tetapi Google Search Console melaporkan INP situs tersebut berada di kategori "Poor" (>400ms). Analisis anomali ini: apa yang terlewat dari pengukuran React Profiler internal dibandingkan dengan metrik INP browser nyata?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian 1
1. **B** — Lanes mengekspresikan bitmask non-linear untuk decoupled task scheduling.
2. **C** — `MessageChannel` digunakan untuk yield macrotask di thread utama.
3. **B** — 5ms adalah frame budget internal (`frameInterval`).
4. **C** — Commit Phase memutasi host tree secara langsung dan bersifat non-interruptible.
5. **B** — `isPending` mengindikasikan bahwa WIP tree sedang aktif diproses pada lane transisi.

#### Bagian 2
6. **False** — React tetap berjalan sepenuhnya pada Single Thread utama JavaScript.
7. **False** — `actualDuration` mengukur waktu pengerjaan Render Phase pada Fiber tree, bukan waktu Layout/Paint native browser.
8. **A** — `SyncLane` untuk discrete clicks/taps; `InputContinuousLane` untuk continuous movement (scroll/drag).
9. **B** — Aliran update discrete yang tiada henti me-restart loop transisi.
10. **B** — Mencegah read tearing saat mutable external store berubah di tengah interruptible render cycle.

#### Bagian 3
11. **Analisis Skenario A:** `startTransition` hanya membuat **proses reconciliation Fiber** React menjadi interruptible. Fungsi parsing `parseCsvSync` adalah single heavy synchronous JavaScript task; ia akan memblok thread JavaScript secara penuh sebelum React bahkan sempat mengevaluasi unit kerja Fiber pertamanya. Solusi: Pindahkan proses parsing sinkronus tersebut ke **Web Worker** menggunakan `Comlink` atau `Worker API`, lalu kirimkan hasilnya secara bertahap ke state React via `startTransition`.
12. **Analisis Skenario B:** Membungkus controlled input state setter langsung ke dalam `startTransition` menurunkan prioritas display input field itu sendiri ke `TransitionLane`. Karakter yang diketik menjadi *laggy* karena penampilannya di-defer. Solusi: Gunakan dua state terpisah (State sinkronus untuk input text field, dan State transisi/deferred untuk filter data grid), atau gunakan kombinasi `useState` biasa untuk input + `useDeferredValue` untuk kalkulasi list.
13. **Analisis Skenario C:** React Profiler API hanya mengukur waktu eksekusi kode internal React (Render Phase dan Commit Hooks). Metrik INP W3C mengukur durasi total dari *Input Delay* (antrean event di browser), *Processing Duration* (Reconciliation + Mutasi DOM), hingga *Presentation Delay* (Style recalculation, layout, paint, dan compositing di browser GPU pipeline). Komponen mungkin selesai di-render cepat di React, namun menghasilkan modifikasi DOM masif yang memicu layout recalculation browser yang sangat lambat (>300ms) di luar jangkauan deteksi React Profiler.

---

### 16. Summary

1. **Lanes Model:** Arsitektur penjadwalan prioritas React 18/19 beroperasi menggunakan aljabar bitwise 31-bit integer. Ini memungkinkan isolasi mutasi state ke dalam bucket prioritas berbeda (`SyncLane`, `InputContinuousLane`, `DefaultLane`, `TransitionLanes`, `IdleLane`).
2. **Cooperative Multitasking:** Melalui `MessageChannel` dan alokasi budget waktu ~5ms, React Scheduler dapat melepaskan thread utama kembali ke browser, mengizinkan paint cycle dan interaksi pengguna berprioritas tinggi menyela rendering berprioritas rendah.
3. **Optimasi Core Web Vitals (INP):** Pola arsitektur enterprise memisahkan feedback visual diskrit (*high priority*) dari rendering data berskala masif (*transition priority*), mengeliminasi *Long Tasks* dan mempertahankan latensi input di bawah batas aman 50ms.
4. **Programmatic Telemetry:** Menggunakan `<Profiler>` API secara selektif memberikan visibilitas terhadap *actual* vs *base* duration. Namun, arsitek sistem harus memahami batasan profiler internal dan tetap menggabungkannya dengan metrik User Timing API browser untuk mengukur *end-to-end presentation delay*.