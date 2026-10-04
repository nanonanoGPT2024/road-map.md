# BAB-05-Performance-Engineering-Profiling-dan-Concurrent-Schedu: Quiz, Challenge, & Knowledge Check

Dokumen evaluasi mandiri ini dirancang untuk menguji, memvalidasi, dan mengukur pemahaman teknis mendalam Anda terkait **Performance Engineering, React Profiling, Memory Profiling, Fiber Architecture, Lane Model, serta Concurrent Scheduling (`useTransition`, `useDeferredValue`)** pada React 18/19.

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1.1: Virtual DOM Diffing vs Re-rendering
**Pertanyaan:**
Apa perbedaan mendasar antara komponen yang mengalami *re-render* dan *commit phase* (DOM mutation)? Mengapa pemanggilan fungsi komponen berkali-kali tidak selalu menyebabkan reflow atau repaint pada browser DOM?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Jawaban:**
- **Render Phase (Virtual DOM / Fiber Tree Reconciliation):** Saat state atau props berubah, React mengeksekusi fungsi komponen untuk menghasilkan Fiber tree baru (JSX/Virtual DOM). React membandingkan (*diffing*) output Fiber baru dengan Fiber *current*. Fase ini murni eksekusi komputasi JavaScript di memori tanpa menyentuh Web API browser.
- **Commit Phase:** Jika hasil komparasi diffing menemukan adanya mutasi (misalnya teks berubah, atribut berubah, atau node baru disisipkan), React menjadwalkan mutasi fisik ke Host DOM melalui `commitRoot()`.
- **Alasan tidak selalu terjadi reflow/repaint:** Jika hasil eksekusi fungsi komponen menghasilkan representasi JSX yang identik secara struktur dan nilai props dengan tree sebelumnya, React akan menandai *flags* mutasi kosong (`NoFlags`). Dengan demikian, fase commit dilewati atau tidak menyentuh DOM riil, sehingga browser engine tidak perlu menjalankan *style recalculation*, *layout/reflow*, atau *paint*.
</details>

---

### Soal 1.2: Perilaku Dasar `React.memo` dan Object Reference Equality
**Pertanyaan:**
Diberikan komponen:
```tsx
const UserCard = React.memo(({ profile, onSelect }: { profile: { id: string; name: string }; onSelect: () => void }) => {
  return <div onClick={onSelect}>{profile.name}</div>;
});
```
Jika komponen induk melakukan *re-render* dan mengoper objek literal `profile={{ id: '1', name: 'John' }}` serta inline handler `onSelect={() => console.log('clicked')}`, mengapa `React.memo` gagal menghentikan re-render `UserCard`?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Jawaban:**
Secara *default*, `React.memo` menggunakan perbandingan dangkal (*shallow equality comparison* via `Object.is`) pada setiap prop antar render (`prevProps[key] === nextProps[key]`).
1. Literal objek `{ id: '1', name: 'John' }` diinstansiasi ulang pada setiap siklus eksekusi parent, menghasilkan referensi memori heap baru (`0x001 !== 0x002`).
2. Fungsi inline `() => console.log('clicked')` juga dialokasikan sebagai closures baru pada setiap siklus render (`0x003 !== 0x004`).
Karena referensi memori berbeda, `Object.is` mengembalikan `false`, membatalkan bailout optimasi `React.memo`. Solusinya adalah menstabilkan referensi menggunakan `useMemo` untuk objek/array dan `useCallback` untuk fungsi callback, atau merestrukturisasi props menjadi tipe data primitif.
</details>

---

### Soal 1.3: Mekanisme dan Waktu Eksekusi `useMemo` vs `useCallback`
**Pertanyaan:**
Apakah `useCallback(fn, deps)` memiliki perbedaan fungsional dengan `useMemo(() => fn, deps)`? Kapan overhead alokasi dependency array dan pemanggilan hook justru lebih mahal daripada membuat fungsi inline biasa?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Jawaban:**
- Secara internal pada arsitektur React Fiber (`ReactFiberHooks.js`), `useCallback(fn, deps)` diimplementasikan sebagai pembungkus sintaksis identik dari `useMemo(() => fn, deps)`. Keduanya menyimpan referensi nilai di dalam *memoizedState* cell milik hook Fiber tersebut.
- **Overhead `useCallback`/`useMemo`:** Setiap deklarasi hook mengalokasikan array dependencies di heap, menjalankan loop komparasi `areHookInputsEqual`, dan mengonsumsi memori linked-list Fiber node.
- Jika sebuah fungsi callback hanya dioper ke elemen native DOM (seperti `<button onClick={fn}>`) atau komponen anak yang **tidak di-memoize** dengan `React.memo`, fungsi anak akan tetap re-render apa pun yang terjadi. Dalam kasus ini, pemakaian `useCallback` murni menjadi *premature optimization* yang justru menambah beban CPU cycles dan alokasi memori garbage collection.
</details>

---

### Soal 1.4: Perbedaan Tujuan Antara `useTransition` dan Debouncing/Throttling
**Pertanyaan:**
Keduanya sering digunakan untuk menangani input pencarian yang berat. Mengapa `useTransition` tidak dapat sepenuhnya menggantikan teknik debouncing saat berhadapan dengan API network request eksternal?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Jawaban:**
- **`useTransition` (CPU-bound concurrency):** Menurunkan prioritas pembaruan state lokal ke dalam *Transition Lane* agar rendering React dapat diinterupsi oleh input berprioritas tinggi (keystroke, click). React tetap memproses state transition segera setelah main thread idle, dan jika user mengetik 10 karakter dengan cepat, React mungkin tetap mencoba merender beberapa frame transisi jika CPU sempat.
- **Debouncing (I/O & Network Throttling):** Berfungsi menahan eksekusi operasi selama periode waktu tertentu ($T$ ms idle) sejak event terakhir.
- Jika pencarian memicu HTTP request ke backend, `useTransition` tanpa debouncing akan memicu pemanggilan *fetch* pada setiap perubahan state yang berhasil diproses, menyebabkan banjir request (*request storm*) dan potensi *race condition*. Oleh karena itu, debouncing wajib digunakan untuk *rate-limiting I/O/Network calls*, sedangkan `useTransition` digunakan untuk menjaga *UI responsiveness* saat merender data masif di client-side.
</details>

---

### Soal 1.5: Dasar Metrik Core Web Vitals untuk React: INP dan LCP
**Pertanyaan:**
Apa hubungan langsung antara render tree React yang terlalu dalam (*deeply nested components*) dengan metrik Interaction to Next Paint (INP)?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Jawaban:**
INP mengukur latensi keseluruhan dari interaksi user (klik, tap, ketik) hingga browser menampilkan frame visual berikutnya (*next paint*). Durasi ini mencakup:
$$\text{INP} = \text{Input Delay} + \text{Processing Duration} + \text{Presentation Delay}$$
Ketika render tree sangat dalam atau memiliki ribuan komponen tanpa virtualisasi:
1. **Processing Duration:** Main thread JavaScript terkunci (*Long Task* > 50ms) karena mengeksekusi diffing rekursif Fiber reconciliation secara sinkron.
2. **Presentation Delay:** DOM mutation yang masif memaksa browser layout engine melakukan kalkulasi style dan tree layout yang memakan waktu lama sebelum frame dapat diproyeksikan ke GPU.
Akibatnya, interaksi user membeku, frame rate anjlok di bawah 60 FPS, dan skor INP melampaui batas ambang baik (> 200ms).
</details>

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 2.1: React 18/19 Fiber Lane Model vs Old Priority Levels
**Pertanyaan:**
Pada React 16-17, prioritas task dikelola melalui integer *Expiration Time*. Di React 18+, arsitektur ini digantikan oleh **Lane Model** berbasis 31-bit integer bitmask. Jelaskan keunggulan komputasi bitwise Lane Model dalam mendukung *Concurrent React* (seperti batched transitions, lane suspension, dan lane entangling).

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Jawaban:**
1. **Representasi Himpunan Prioritas Non-Linier:** Expiration time membatasi prioritas pada skala linier tunggal (task dengan waktu kedaluwarsa lebih pendek selalu didahulukan). Bitmask 32-bit (31 lanes aktif + 0) memungkinkan React merepresentasikan banyak prioritas sekaligus sebagai sekumpulan bit (misal `SyncHydrationLane = 0b0001`, `InputContinuousLane = 0b0100`, `TransitionLanes = 0b...11111110000`).
2. **Operasi Himpunan Berkecepatan $O(1)$:**
   - Memeriksa apakah ada transition lane: `(lanes & TransitionLanes) !== NoLanes`
   - Menggabungkan antrean update: `root.pendingLanes |= updateLane`
   - Menghapus lane yang selesai dikomit: `root.pendingLanes &= ~finishedLanes`
3. **Lane Entanglement & Suspension:** Jika sebuah data query di dalam Transition Lane melakukan *suspend*, React dapat "menjerat" (*entangle*) lane tersebut dengan lane lain tanpa memblokir *Sync/InputContinuous lanes*. Hal ini mustahil dilakukan secara efisien dengan angka integer linier.
</details>

---

### Soal 2.2: `useDeferredValue` vs `useTransition` Lifecycle & Fallback
**Pertanyaan:**
Jelaskan perbedaan mekanika internal antara `useTransition` dan `useDeferredValue`. Kapan Anda wajib memilih `useDeferredValue` daripada `useTransition` dalam arsitektur komponen terisolasi?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Jawaban:**
- **`useTransition`:** Mengontrol pembaruan state pada **sumbernya** (*producer-driven*). Eksekusi `startTransition(() => setState(val))` menandai pembaruan Fiber yang dihasilkan oleh hook state tersebut langsung dengan `TransitionLane`. Selain itu, hook ini menyediakan flag boolean `isPending`.
- **`useDeferredValue`:** Bekerja pada **konsumsi nilai** (*consumer-driven*). Hook ini menerima nilai (props/state) dan menunda penyebaran nilai tersebut ke anak pohon. Pada render pertama setelah nilai berubah, `useDeferredValue` mengembalikan nilai lama (*stale value*) sementara React menjadwalkan render latar belakang (*concurrent fork*) dengan nilai baru pada *Deferred Lane*.
- **Kapan wajib menggunakan `useDeferredValue`:** Ketika komponen anak menerima data yang dihitung dari props eksternal atau third-party store di mana kita tidak memiliki akses langsung ke dispatcher `setState` (misalnya komponen library yang hanya menerima `query: string` dari router URL atau context wrapper).
</details>

---

### Soal 2.3: Analisis Flamegraph Profiler: Self Time vs Base Time
**Pertanyaan:**
Pada React DevTools Profiler, sebuah komponen bernama `<DataGridRow>` menunjukkan **Base Duration: 18.4ms** dan **Self Duration: 0.2ms**. Interpretasikan arti metrik tersebut, apa yang menyebabkan tingginya Base Duration, dan di mana optimasi harus dipusatkan?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Jawaban:**
- **Self Duration (0.2ms):** Waktu murni yang dihabiskan untuk mengeksekusi kode komponen `<DataGridRow>` itu sendiri (menghitung JSX lokal, hook lokal) di luar waktu rendering anak-anaknya.
- **Base Duration (18.4ms):** Estimasi waktu komputasi terburuk (*worst-case*) untuk merender seluruh subtree di bawah `<DataGridRow>`, dihitung dari akumulasi *self-duration* terakhir dari seluruh anak-anaknya saat mereka benar-benar dirender tanpa memoization/bailout.
- **Interpretasi & Aksi:** Komponen `<DataGridRow>` itu sendiri sangat ringan (hanya 0.2ms). Tingginya *Base Duration* (18.4ms) menandakan bahwa komponen ini memiliki subtree turunan (komponen anak/cucu) yang sangat banyak atau memiliki komputasi berat. Optimasi tidak boleh difokuskan pada manipulasi logika internal `<DataGridRow>`, melainkan pada pemangkasan tree anak (misalnya implementasi *windowing/virtualization* dengan `tanstack-virtual`) atau memoisasi komponen anak individual yang mahal.
</details>

---

### Soal 2.4: Memory Leak Patterns pada React Hooks & Fiber Detachment
**Pertanyaan:**
Mengapa closure di dalam `useEffect` yang menyimpan referensi ke state objek besar dapat memicu *Retained Memory Leak* di Chrome DevTools Heap Snapshot, meskipun komponen bersangkutan telah di-*unmount* dari DOM?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Jawaban:**
1. Ketika sebuah efek berlangganan event listener global (misalnya `window.addEventListener('resize', handler)` atau websocket message bus) tanpa fungsi *cleanup* (`return () => window.removeEventListener('resize', handler)`), fungsi `handler` tetap berada dalam retention graph V8 JavaScript Engine melalui root global context (`window`).
2. Fungsi `handler` menahan *Lexical Scope Closure* dari siklus render tempat ia dibuat. Closure ini menyimpan variabel state atau props lokal (misalnya array data 50MB).
3. Melalui rantai scope tersebut, V8 GC tidak dapat membebaskan memori objek data maupun Fiber node yang terafiliasi dengannya, menyebabkan *Detached Window / Detached Fiber Tree leak*.
</details>

---

### Soal 2.5: Pitfalls `useSyncExternalStore` dengan Non-Memoized Snapshot Selector
**Pertanyaan:**
Apa konsekuensi fatal jika fungsi `getSnapshot` pada `useSyncExternalStore` mengembalikan objek/array baru yang dibuat secara inline pada setiap pemanggilan? Mengapa ini menyebabkan "Maximum update depth exceeded"?

<details>
<summary>Jawaban & Analisis Teknis</summary>

**Jawaban:**
`useSyncExternalStore` dirancang untuk mencegah masalah *tearing* pada Concurrent React dengan memeriksa kestabilan data store eksternal.
1. React mengecek apakah store berubah dengan memanggil `getSnapshot()` dan membandingkan hasilnya dengan snapshot sebelumnya menggunakan `Object.is(prevSnapshot, nextSnapshot)`.
2. Jika fungsi `getSnapshot` mengembalikan referensi baru pada setiap pemanggilan (misalnya: `() => store.getState().items.filter(x => x.active)` yang menghasilkan array baru):
3. `Object.is` akan selalu bernilai `false`.
4. React mengasumsikan store eksternal bermutasi secara terus-menerus tepat di tengah proses rendering atau re-evaluasi sinkronisasi, sehingga React menjadwalkan ulang re-render sinkron tanpa henti.
5. Hal ini memicu loop tak terbatas (*infinite render loop*) hingga runtime React melempar error kritis: `Error: Maximum update depth exceeded`.
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 3.1: Keystroke Lag pada Real-Time Financial Trading Terminal
**Konteks Masalah:**
Sebuah aplikasi web dashboard trading crypto menerima ticker update 50 kali per detik melalui WebSocket. Dashboard menampilkan komponen form order input (`<OrderInput />`) dan grafik orderbook real-time (`<OrderBookVisualizer />`) yang merender 2,000 baris depth chart dalam satu canvas/SVG container. Saat user mengetikkan jumlah aset pada `<OrderInput />`, terjadi *keystroke lag* parah (input macet hingga 350ms per karakter).

**Investigasi Profiling:**
Hasil Chrome Performance Trace menunjukkan Long Tasks konstan (70-120ms) yang didominasi oleh `performConcurrentWorkOnRoot` -> `OrderBookVisualizer`. Profiler React DevTools mendeteksi bahwa setiap update ticker WebSocket memicu render ulang root context, yang mengalir ke seluruh subtree.

**Tugas & Solusi Arsitektural:**
1. Pisahkan dependensi rendering antara *high-priority user input* dan *high-frequency background streaming*.
2. Implementasikan arsitektur state yang memisahkan update ticker ke dalam *Concurrent Transition* atau *Isolated External Store*.
3. Tuliskan refaktor komponen menggunakan pola state splitting dan `useDeferredValue`/`useTransition`.

```tsx
// IMPLEMENTASI SOLUSI ARSITEKTURAL
import React, { useState, useTransition, useDeferredValue, memo } from 'react';

// 1. Isolasikan Komponen OrderBook agar tidak terpengaruh re-render parent input
interface OrderBookProps {
  depthData: Array<{ price: number; volume: number }>;
}

export const OrderBookVisualizer = memo(({ depthData }: OrderBookProps) => {
  // Render virtualized / memoized row depth
  return (
    <div className="order-book-container">
      {depthData.map((row) => (
        <div key={row.price} className="order-book-row">
          <span>{row.price.toFixed(2)}</span>
          <span style={{ width: `${Math.min(row.volume, 100)}%` }} className="depth-bar" />
        </div>
      ))}
    </div>
  );
});

// 2. Hubungkan Trading Dashboard dengan Concurrency Boundary
export function TradingTerminal({ incomingStreamData }: { incomingStreamData: Array<{ price: number; volume: number }> }) {
  const [orderAmount, setOrderAmount] = useState<string>('');
  
  // Pisahkan prioritas: incomingStreamData yang masif ditangguhkan saat user mengetik
  const deferredStreamData = useDeferredValue(incomingStreamData);
  const isStale = incomingStreamData !== deferredStreamData;

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Input pengguna berada pada Urgent/Sync Lane (High Priority)
    setOrderAmount(e.target.value);
  };

  return (
    <div className="terminal-grid">
      <div className="order-form-panel">
        <label htmlFor="amount">Order Amount</label>
        <input
          id="amount"
          type="text"
          value={orderAmount}
          onChange={handleInputChange}
          placeholder="0.00 BTC"
          autoComplete="off"
        />
      </div>

      <div className={`order-book-panel ${isStale ? 'opacity-80 transition-opacity' : ''}`}>
        <OrderBookVisualizer depthData={deferredStreamData} />
      </div>
    </div>
  );
}
```

---

### Skenario 3.2: Severe Memory Leak & Tab Crash pada Infinite-Scroll E-Commerce Catalog
**Konteks Masalah:**
Katalog produk SPA e-commerce mengalami browser tab crash (*Error code: Out of Memory*) ketika user melakukan scroll lebih dari 20 halaman produk (sekitar 1,000 item produk dengan gambar interaktif, 3D card preview, dan tooltips). Heap snapshot menunjukkan memory heap naik stabil dari 45 MB menjadi 890 MB dan tidak turun meskipun user berpindah ke rute statis lain.

**Investigasi Profiling:**
Pada Chrome Memory Heap Snapshot:
- Ditemukan ratusan ribu objek bertipe `HTMLDivElement` dan `FiberNode` di bagian *Detached HTMLElement*.
- Distance ke GC root ditahan oleh closure `IntersectionObserver` dan instance `EventEmitter` yang diinisialisasi di dalam custom hook `useProductIntersection` tanpa dereferensi pembersihan.

**Tugas & Solusi Arsitektural:**
1. Desain custom hook pembersihan observer yang benar-benar menjamin pelepasan pointer GC.
2. Terapkan DOM Virtualization (Windowing) sehingga jumlah node DOM yang ada di memori dibatasi hanya pada viewport yang terlihat plus overscan buffer.

```tsx
// IMPLEMENTASI SOLUSI ARSITEKTURAL: Virtualized Catalog Container dengan Zero-Leak Hook
import React, { useRef, useState, useEffect, useCallback } from 'react';

interface Product {
  id: string;
  name: string;
  price: number;
}

export function VirtualizedCatalog({ products }: { products: Product[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);

  const ITEM_HEIGHT = 120;
  const VIEWPORT_HEIGHT = 600;
  const OVERSCAN = 3;

  const totalHeight = products.length * ITEM_HEIGHT;
  const startIndex = Math.max(0, Math.floor(scrollTop / ITEM_HEIGHT) - OVERSCAN);
  const endIndex = Math.min(
    products.length - 1,
    Math.floor((scrollTop + VIEWPORT_HEIGHT) / ITEM_HEIGHT) + OVERSCAN
  );

  const onScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  const visibleItems = products.slice(startIndex, endIndex + 1);
  const offsetY = startIndex * ITEM_HEIGHT;

  return (
    <div
      ref={containerRef}
      onScroll={onScroll}
      style={{
        height: `${VIEWPORT_HEIGHT}px`,
        overflowY: 'auto',
        position: 'relative',
        border: '1px solid #ccc',
      }}
    >
      <div style={{ height: `${totalHeight}px`, width: '100%', position: 'relative' }}>
        <div style={{ transform: `translateY(${offsetY}px)`, position: 'absolute', width: '100%' }}>
          {visibleItems.map((product) => (
            <div
              key={product.id}
              style={{
                height: `${ITEM_HEIGHT}px`,
                boxSizing: 'border-box',
                padding: '12px',
                borderBottom: '1px solid #eee',
              }}
            >
              <h3>{product.name}</h3>
              <p>USD ${product.price.toLocaleString()}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

---

### Skenario 3.3: Waterfalls Cascade dan UI Thrashing pada Analytics Filtering System
**Konteks Masalah:**
Dashboard analytics memiliki panel filter multi-dimensi (Date Range, Region, Category, Metric Types). Saat user memilih satu filter:
1. State filter induk memicu update ke 12 komponen chart individual.
2. Setiap chart melakukan ekstraksi data berat (`array.reduce`, `array.sort`) berulang kali di dalam fungsi render.
3. Chart juga memanggil `getBoundingClientRect()` di dalam `useLayoutEffect` untuk menghitung responsive width.
Hasilnya: Browser mengalami **Layout Thrashing** (forced synchronous layout) berulang kali dan FPS turun menjadi 8 FPS selama 1.2 detik.

**Tugas & Solusi Arsitektural:**
1. Eliminasi read-write layout thrashing dengan memigrasikan pengukuran layout ke `ResizeObserver` asynchronous atau container queries.
2. Memoize kalkulasi data analitik yang berat menggunakan `useMemo` dengan representasi key terkompresi.
3. Bungkus update filtering dalam `useTransition` agar render UI utama tidak memblokir event loop.

```tsx
// REFAKTOR SOLUSI ARSITEKTURAL
import React, { useState, useTransition, useMemo, memo } from 'react';

interface MetricItem {
  timestamp: number;
  region: string;
  category: string;
  revenue: number;
}

export const HeavyAnalyticsChart = memo(({ data }: { data: MetricItem[] }) => {
  // Pindahkan pemrosesan data berat ke useMemo
  const aggregatedStats = useMemo(() => {
    return data.reduce(
      (acc, curr) => {
        acc.totalRevenue += curr.revenue;
        acc.count += 1;
        return acc;
      },
      { totalRevenue: 0, count: 0 }
    );
  }, [data]);

  return (
    <div className="chart-card">
      <h4>Metric Overview</h4>
      <p>Total Revenue: ${aggregatedStats.totalRevenue.toLocaleString()}</p>
      <p>Transactions: {aggregatedStats.count}</p>
      {/* Menggunakan pure CSS container query untuk responsive sizing alih-alih getBoundingClientRect */}
      <div className="chart-canvas-container" style={{ containerType: 'inline-size' }}>
        <div className="dynamic-bar" style={{ width: `${Math.min(aggregatedStats.totalRevenue / 10000, 100)}%` }} />
      </div>
    </div>
  );
});

export function AnalyticsDashboard({ dataset }: { dataset: MetricItem[] }) {
  const [selectedRegion, setSelectedRegion] = useState<string>('ALL');
  const [isPending, startTransition] = useTransition();

  const handleFilterSelect = (region: string) => {
    // Deklarasikan perubahan filter sebagai transition non-urgent
    startTransition(() => {
      setSelectedRegion(region);
    });
  };

  const filteredData = useMemo(() => {
    if (selectedRegion === 'ALL') return dataset;
    return dataset.filter((item) => item.region === selectedRegion);
  }, [dataset, selectedRegion]);

  return (
    <div className="dashboard-layout">
      <div className="filter-bar">
        {['ALL', 'APAC', 'EMEA', 'NA'].map((reg) => (
          <button
            key={reg}
            onClick={() => handleFilterSelect(reg)}
            className={selectedRegion === reg ? 'active' : ''}
          >
            {reg}
          </button>
        ))}
        {isPending && <span className="spinner-indicator">Recalculating charts...</span>}
      </div>

      <div className="grid-charts" style={{ opacity: isPending ? 0.7 : 1, transition: 'opacity 0.2s' }}>
        <HeavyAnalyticsChart data={filteredData} />
      </div>
    </div>
  );
}
```

---

## Bagian 4: Practical Chapter Challenge

### Tantangan: Bangun High-Performance Concurrent Virtualized Matrix Explorer

#### Deskripsi Tantangan
Anda diminta membangun arsitektur komponen React berkemampuan tinggi bernama `<ConcurrentMatrixExplorer />` yang mampu merender matriks data tabular dinamis berukuran $100 \times 1,000$ sel (100,000 data nodes) dengan latensi input **INP < 50ms** dan alokasi memori stabil.

#### Persyaratan Fungsional & Kriteria Penerimaan:
1. **Zero-Lag Search Filtering:**
   - Terdapat input pencarian teks real-time yang memfilter baris matriks berdasarkan substring teks.
   - Pengetikan karakter pada input wajib berjalan tanpa latensi (60 FPS / < 16ms frame budget), sementara komputasi filtering data 100,000 sel dijalankan menggunakan `useTransition` atau `useDeferredValue`.
   - Menampilkan visual indicator (*skeleton/subtle opacity transition*) ketika komputasi filter latar belakang sedang berjalan.
2. **Dynamic Viewport Virtualization (Windowing):**
   - Hanya merender sel yang terlihat di layar ditambah buffer overscan 5 baris atas/bawah dan 2 kolom kiri/kanan.
   - Larangan keras menyisipkan seluruh 100,000 elemen `<div>` ke dalam Real DOM tree.
3. **Optimasi Profiler & Render Bailout:**
   - Setiap sel harus di-memoize dengan selektor perbandingan properti yang efisien (`React.memo` dengan custom equality atau granular props splitting).
   - Memilih/mengklik satu sel tidak boleh memicu re-render pada sel lain yang tidak mengalami mutasi state seleksi.
4. **Leak-Free Destruction:**
   - Komponen harus bersih saat di-unmount tanpa menyisakan detached event listeners, pending microtasks, atau memory retention di Chrome heap snapshot.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan checklist ini untuk memverifikasi kesiapan penguasaan materi Bab 5 sebelum melanjutkan ke tahap pengujian berikutnya:

- [ ] **Mekanisme Render vs Commit:** Mampu membedakan dengan tepat kapan React mengeksekusi fungsi JavaScript komponen dan kapan React memutasikan Host DOM.
- [ ] **React Profiler Mastery:** Mampu membaca flamegraph DevTools, memahami perbedaan antara *Self Duration* dan *Base Duration*, serta mengidentifikasi *cascading re-renders*.
- [ ] **Chrome DevTools Performance & Memory:** Mampu merekam CPU profile, mendeteksi *Long Tasks* (> 50ms), membaca *Call Tree*, dan mengambil *Heap Snapshot* untuk menganalisis *Detached Fiber/DOM Nodes*.
- [ ] **Memoization Trade-offs:** Memahami kapan penggunaan `React.memo`, `useMemo`, dan `useCallback` memberikan penghematan nyata vs kapan hook tersebut justru membebani memori dan runtime CPU.
- [ ] **Fiber Architecture & Concurrency:** Memahami struktur Fiber node (`child`, `sibling`, `return`, `memoizedState`, `flags`, `lanes`) dan alasan sistem kooperatif multithreading React bergantung pada model ini.
- [ ] **Bitwise Lane Model:** Mengetahui cara kerja 31-bit Lane Mask dalam membedakan `SyncLane`, `InputContinuousLane`, `DefaultLane`, dan `TransitionLanes`.
- [ ] **Concurrent Primitives:** Mampu mengimplementasikan `useTransition` untuk pembaruan state berbasis produsen dan `useDeferredValue` untuk optimasi konsumsi data subtree anak.
- [ ] **DOM Virtualization Architecture:** Mampu menghitung kalkulasi offset scroll, total container height, slice array, dan overscan buffer secara mandiri tanpa library eksternal jika diperlukan.
- [ ] **Layout Thrashing Prevention:** Menghindari pola anti-pattern pembacaan dimensi DOM sinkron (`offsetHeight`, `getBoundingClientRect`) yang disusul penulisan style seketika di dalam satu siklus event loop.
