# BAB 03: Quiz, Challenge, & Knowledge Check
**Bab 03: Arsitektur Komponen, State Management Reaktif, & Rendering Engine Internals**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Prinsip Immutability vs Mutability dalam Change Detection:**
   Jelaskan bagaimana paradigma *immutable data structures* memfasilitasi algoritma *change detection* (misalnya perbandingan referensial $O(1)$) dibandingkan dengan pendekatan mutasi langsung yang membutuhkan *deep comparison* $O(n)$. Apa konsekuensi alokasi memori (*garbage collection pressure*) dari pembuatan objek baru secara terus-menerus dan bagaimana *structural sharing* memitigasi masalah tersebut?

2. **Heuristic Diffing Algorithm pada Virtual DOM:**
   Algoritma perbandingan pohon (*tree reconciliation*) standar memiliki kompleksitas komputasi $O(n^3)$. Jelaskan dua asumsi heuristik utama yang diambil oleh *rendering engine modern* (seperti React Reconciliation Engine) untuk mereduksi kompleksitas tersebut menjadi $O(n)$, serta jelaskan kegagalan struktural yang terjadi jika asumsi heuristik tersebut dilanggar oleh developer.

3. **Unidirectional Data Flow vs Two-Way Data Binding:**
   Bandingkan arsitektur *Unidirectional Data Flow* (seperti Flux/Redux/React core) dengan *Two-Way Data Binding* (seperti Angular/Vue v-model). Analisis dari sudut pandang prediktabilitas mutasi state, kemudahan penelusuran bug (*time-travel debugging*), dan *overhead* sinkronisasi runtime saat graph dependensi komponen menjadi deeply nested.

4. **Lifecycle & Cleanup Mechanics:**
   Mengapa abstraksi siklus hidup komponen modern (seperti `useEffect` cleanup atau unmount hooks) mewajibkan pembersihan efek samping (*side-effect teardown*)? Jelaskan skenario kebocoran memori (*memory leak*) dan *zombie callbacks* yang terjadi pada *Single Page Application* (SPA) ketika listener pada objek global (`window`, `EventTarget`, atau WebSocket) tidak dilepas setelah komponen di-unmount.

5. **Pull-based vs Push-based Reactivity:**
   Jelaskan perbedaan mendasar antara model reaktivitas *pull-based* (seperti Virtual DOM re-render traversal) dengan *push-based* (seperti Signals/Fine-grained Reactivity pada Solid.js atau Svelte 5). Bagaimana push-based reactivity mengeliminasi kebutuhan re-evaluasi seluruh subtree komponen saat sebuah atom state terisolasi mengalami mutasi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Stale Closures dalam Hook / Functional Components:**
   Diberikan potongan kode berikut:
   ```javascript
   function RealTimeCounter() {
     const [count, setCount] = useState(0);

     useEffect(() => {
       const timer = setInterval(() => {
         setCount(count + 1);
       }, 1000);
       return () => clearInterval(timer);
     }, []);

     return <div>{count}</div>;
   }
   ```
   Bedah secara internal pada level *JavaScript Execution Context* dan lexical environment: Mengapa nilai `count` di layar tidak pernah bertambah melebihi angka `1`? Jelaskan dua cara refactoring untuk memperbaikinya beserta implikasi lifecycle-nya.

2. **Microtask Batching & Event Loop Scheduling:**
   Bagaimana modern UI framework mengimplementasikan mekanisme *batching* terhadap pembaruan state berturut-turut? Analisis urutan eksekusi queue antara *Macro-task* (`setTimeout`), *Micro-task* (`Promise.resolve()`), dan `requestAnimationFrame` dalam hubungannya dengan siklus render browser (Style Calculation, Layout, Paint, Composite).

3. **Diagnostik Detached DOM Tree:**
   Saat menganalisis aplikasi frontend berskala enterprise menggunakan Chrome DevTools Memory Heap Snapshot, Anda menemukan node bertipe `Detached HTMLDivElement` yang menahan memori sebesar puluhan megabyte. Bagaimana skenario arsitektural kode frontend yang menyebabkan DOM element terlepas dari DOM tree aktif namun tetap tertahan di heap memory? Bagaimana langkah metodologis untuk mengisolasi retainers-nya?

4. **Anomali Rekonsiliasi Penggunaan `key={index}`:**
   Jelaskan secara deterministik kerusakan visual atau state corruption yang terjadi ketika array data dinamis yang dapat dihapus (*delete*), disisipkan (*prepend*), atau diurutkan (*sort*) menggunakan indeks array (`key={index}`) sebagai identifier unik pada list komponen yang memiliki local/uncontrolled state (misalnya `<input />`).

5. **Context Propagation vs Re-render Boundary:**
   Pada React Context API, setiap kali nilai `value` pada `Context.Provider` berubah referensi, seluruh komponen konsumen (*consumers*) akan dipaksa melakukan re-render, mengabaikan optimasi `React.memo`. Jelaskan mekanisme internal yang memicu *bypass* terhadap memoization boundary ini dan bagaimana arsitektur state harus dipecah (*split context*) atau dioptimasi menggunakan selektor untuk mencegah render cascade berskala besar.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi Render pada Platform Trading FinTech
Sebuah dashboard trading mata uang kripto menerima streaming data pesanan via WebSocket dengan frekuensi rata-rata 120 pesan per detik. Aplikasi frontend mengalami frame drop parah (turun ke 12-18 FPS), thread UI macet (*freezing*), dan latency masukan pengguna (*input delay*) melonjak drastis hingga lebih dari 800ms. Profiler menunjukkan JavaScript Execution dan Garbage Collector mengonsumsi 90% waktu pada main thread akibat re-render komponen orderbook yang terus menerus.

**Pertanyaan Diagnostik & Solutif:**
1. Rancang arsitektur buffering dan throttling data stream dari WebSocket sebelum dialirkan ke state UI agar sinkron dengan refresh rate layar pengguna (60Hz / 120Hz).
2. Tentukan strategi rendering komponen orderbook: Apakah DOM virtualization, off-screen rendering via Web Workers, atau selective DOM manipulation via direct mutation/Canvas/Signals yang paling tepat? Berikan justifikasi teknis dan analisis trade-off performanya.

---

### Skenario B: Race Condition dan Out-of-Order Execution pada Mesin Pencarian E-Commerce
Pada aplikasi e-commerce global, fitur *search-as-you-type* mengirimkan request HTTP asynchronous ke API backend setiap kali event debounced input terpicu. Pengguna mengetik string `"laptop"`, kemudian dengan cepat menghapus dan mengetik `"mouse"`. Akibat latensi jaringan yang fluktuatif, response untuk query `"laptop"` (durasi 1500ms) tiba di browser **setelah** response untuk query `"mouse"` (durasi 200ms) selesai diproses. Akibatnya, input box menampilkan kata `"mouse"`, namun daftar produk di layar menampilkan hasil pencarian untuk `"laptop"`.

**Pertanyaan Diagnostik & Solutif:**
1. Bedah titik kegagalan arsitektur async di atas dan jelaskan mengapa pendekatan flag boolean lokal sering kali gagal menyelesaikan masalah ini secara bersih.
2. Implementasikan pola pembatalan asynchronous (*cancellation pattern*) berstandar industri menggunakan `AbortController` pada Fetch API atau operator pembatalan pada reactive stream (misalnya `switchMap` pada RxJS). Berikan abstraksi kode produksinya.

---

### Skenario C: Dilema Arsitektur State Management Aplikasi Multi-Region Enterprise
Perusahaan Anda sedang membangun ulang aplikasi core SaaS yang memiliki lebih dari 400 form input dinamis lintas ratusan modal, dynamic tab, dan komponen kolaboratif multi-user real-time. Tim terbelah menjadi tiga kubu:
- **Kubu A:** Mengusulkan Global Redux/Zustand Store terpusat dengan deep structural normalization.
- **Kubu B:** Mengusulkan Fine-grained Signals (Solid-style / Preact Signals) yang memutus dependensi re-render tree.
- **Kubu C:** Mengusulkan Server-driven state via React Server Components (RSC) dikombinasikan dengan URL state dan URL search params.

**Pertanyaan Diagnostik & Solutif:**
1. Lakukan analisis komparatif mendalam mengenai kelemahan dan kelebihan ketiga pendekatan di atas berdasarkan metrik: *Runtime Memory Footprint*, *Bundle Size Overhead*, *Developer Experience (DX) / Maintainability*, dan *Edge Network Latency*.
2. Rancang arsitektur hybrid yang optimal yang memetakan jenis state tertentu (misal: *Server Cache, Ephemeral UI State, URL State, Collaborative State*) ke solusi teknologi yang paling sesuai tanpa menciptakan fragmentasi arsitektur yang berlebihan.

---

## 4. Chapter Challenge

**Tantangan Praktis: Membangun "MicroSignal" – Fine-Grained Reactive State Engine & Auto-Batching Virtual Renderer dari Nol**

### Deskripsi Masalah:
Banyak developer menggunakan library state management modern tanpa memahami dependency graph tracking dan microtask scheduling yang mendasarinya. Tugas Anda adalah membangun reactive engine mandiri tanpa dependensi pihak ketiga (*vanilla JavaScript/TypeScript*).

### Functional Requirements:
1. **Core Reactivity (`createSignal`, `createEffect`, `createMemo`):**
   - Mengimplementasikan observer pattern otomatis via implicit dependency tracking (menggunakan execution stack context).
   - `createSignal(initialValue)` mengembalikan tuple `[getter, setter]`. Saat `getter()` dieksekusi di dalam `createEffect`, efek tersebut harus otomatis terdaftar sebagai subscriber.
   - Bersihkan dependensi lama (*dynamic dependency clean-up*) pada setiap eksekusi efek untuk mencegah memory leak jika terjadi percabangan kondisional (`if/else`).
   - Implementasikan `createMemo` yang menghitung nilai turunan secara *lazy* dan menerapkan caching nilai selama sinyal dependensinya belum bermutasi.
2. **Batching Execution Engine:**
   - Mutasi beberapa sinyal secara sinkron dalam satu blok instruksi tidak boleh memicu eksekusi efek secara berulang (*redundant re-runs*).
   - Efek harus dijadwalkan secara otomatis (*auto-batched*) dan dieksekusi sekali pada microtask turn berikutnya (`queueMicrotask`).
3. **Reactive DOM Binder:**
   - Buat fungsi `bindDOM(element, getter)` yang langsung memperbarui `textContent` atau atribut DOM element secara atomik dan terisolasi tanpa me-render ulang parent element.

### Constraints & Edge Cases:
- **Zero External Dependencies:** Tidak boleh mengimpor framework, runtime, atau library apa pun.
- **Circular Dependency Detection:** Engine harus mampu mendeteksi pemanggilan reaktif sirkular (sinyal memicu efek yang memutasi sinyal tersebut secara sinkron) dan melempar *runtime error* sebelum browser mengalami *Maximum call stack size exceeded*.
- **Memory Hygiene:** Efek yang dibuang (*disposed*) harus menghapus seluruh referensinya dari dependensi sinyal upstream.

### Expected Output:
Sebuah module JavaScript/TypeScript tunggal yang lolos skenario pengujian verifikasi berikut:
```javascript
const [count, setCount] = createSignal(0);
const [show, setShow] = createSignal(true);

let effectRunCount = 0;
createEffect(() => {
  effectRunCount++;
  if (show()) {
    console.log("Count is:", count());
  } else {
    console.log("Count is hidden");
  }
});

// Verifikasi Dynamic Cleanup & Auto-batching:
queueMicrotask(() => {
  // Test 1: Multiple updates in same synchronous frame -> Only 1 additional effect run
  setCount(1);
  setCount(2);
  setCount(3);
  
  queueMicrotask(() => {
    // Test 2: Conditional switching -> count() should no longer be a dependency
    setShow(false);
    
    queueMicrotask(() => {
      const prevRuns = effectRunCount;
      setCount(100); // Should NOT trigger effect because show() is false
      
      queueMicrotask(() => {
        console.assert(effectRunCount === prevRuns, "Failed: Dynamic dependency cleanup failed!");
        console.log("All Reactive Engine assertions passed successfully.");
      });
    });
  });
});
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme kerja Call Stack, Event Loop, Task (Macrotask), dan Microtask queue dalam konteks sinkronisasi frame rate browser (60fps / 16.6ms budget).
- [ ] Perbedaan fundamental antara Structural Sharing pada Immutable Data (misalnya via structural cloning / persistent data structures) vs Mutable in-place mutation.
- [ ] Heuristik rekonsiliasi DOM: Mengapa tipe elemen berbeda akan menghancurkan subtree, dan bagaimana atribut `key` mempertahankan identitas komponen melintasi cycle render.
- [ ] Mekanisme Dependency Injection dan Event Propagation pada arsitektur komponen bertingkat (Prop Drilling vs Inversion of Control vs Context Provider).
- [ ] Konsep fine-grained reactivity: Dependency Graph Resolution, Subscriber Sets, Dynamic Dependency Pruning, dan Top-down Push/Pull Evaluation.
- [ ] Metodologi profiling aplikasi frontend: Membaca Flame Graph, menganalisis Forced Synchronous Layout / Layout Thrashing, dan mendeteksi Memory Leaks via Heap Allocation Timelines.

### Saya tidak perlu menghafal:
- [ ] Seluruh signature method internal dari framework tertentu (misalnya daftar hook langka React atau internal lifecycle flags Vue).
- [ ] Sintaks spesifik library state management pihak ketiga (Redux Toolkit, MobX, Recoil, Pinia) secara mendetail; cukup menguasai pola dasarnya (Flux, Proxy-based Observables, Atom-based, Directed Acyclic Graph).
- [ ] Nilai byte numerik spesifik dari representasi objek Virtual DOM di heap memory.

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi dan memperbaiki masalah performa rendering (*unnecessary re-renders*) menggunakan profiler bawaan browser dan DevTools framework.
- [ ] Melakukan isolasi dan pembatalan (*cancellation*) operasi asynchronous yang berkompetisi (*race conditions*) menggunakan standard Web APIs (`AbortController`).
- [ ] Mengaudit heap dump memori aplikasi frontend untuk menemukan dan mengeliminasi *detached DOM nodes* dan kebocoran event listener.
- [ ] Menerapkan teknik pemisahan state (*state colocation*) dan memoization boundary untuk mencegah re-render cascade pada skala aplikasi ribuan komponen.
- [ ] Mengabstraksi logika bisnis murni (*pure business logic*) ke luar dari layer presentasi UI menggunakan State Machines (misal: XState) atau Custom Headless Hooks.