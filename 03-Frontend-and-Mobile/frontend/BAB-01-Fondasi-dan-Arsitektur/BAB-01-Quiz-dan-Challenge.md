# BAB 01: Quiz, Challenge, & Knowledge Check
**Bab 01: Modern JavaScript Runtime, Event Loop, dan Critical Rendering Path**

---
## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **V8 Compilation Pipeline & Execution Context**
   Jelaskan siklus hidup eksekusi JavaScript dari parsing *source code* mentah hingga kompilasi *machine code* pada V8 engine (Ignition & TurboFan). Bagaimana *Variable Environment* dan *Lexical Environment* dibentuk selama fase Creation sebelum fase Execution berjalan, dan bagaimana hal ini menjelaskan mekanisme *hoisting* serta *Temporal Dead Zone* (TDZ) pada deklarasi `let`/`const`?

2. **Memory Allocation & Garbage Collection Mechanics**
   Bedah alokasi memori antara *Stack* vs *Heap* pada browser runtime. Bagaimana algoritma *Mark-and-Sweep* dan mekanisme *Generational Collection* (Young Generation vs Old Generation via Scavenger & Major GC) menentukan apakah sebuah referensi objek dapat dialokasikan kembali atau dihapus?

3. **Event Loop: Microtasks vs Macrotasks vs Rendering Phases**
   Analisis urutan preseden eksekusi antara Microtask Queue (`Promise.then`, `MutationObserver`, `queueMicrotask`), Macrotask/Task Queue (`setTimeout`, `setInterval`, I/O), dan fase Rendering Pipeline browser (`requestAnimationFrame`, Style Calculation, Layout, Paint). Mengapa *infinite microtask recursion* membekukan UI secara instan sementara *infinite macrotask recursion* tidak?

4. **Critical Rendering Path (CRP) & Parse-Blocking Scripts**
   Uraikan tahap pembentukan DOM dan CSSOM hingga menghasilkan *Render Tree*. Jelaskan implikasi langsung terhadap *First Contentful Paint* (FCP) ketika parser menemukan tag `<script>` reguler, `<script async>`, dan `<script defer>`, serta bagaimana CSSOM berinteraksi secara sinkron dengan eksekusi JavaScript inline.

5. **Layout Thrashing & Composite Layers**
   Jelaskan apa yang menyebabkan *Layout Thrashing* (atau *Forced Synchronous Layout*) di level browser layout engine saat operasi baca-tulis DOM dilakukan secara bergantian. Mengapa manipulasi properti CSS via `transform` dan `opacity` dialihkan langsung ke *Compositor Thread* tanpa memicu *Reflow* atau *Repaint*?

---
## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Closures, Scope Chains, and Retainer Trees Memory Leaks**
   Perhatikan potongan kode berikut:
   ```javascript
   function createLeakEmitter() {
     let largePayload = new Array(2000000).fill("payload_data");
     return function listener() {
       const unused = function() {
         if (largePayload) console.log("retained");
       };
       return function actualHandler() {
         console.log("handler executed");
       };
     };
   }
   ```
   Secara spesifik, mengapa eksekusi `actualHandler` dapat menahan `largePayload` di Heap memory meskipun `actualHandler` tidak secara eksplisit mereferensikan `largePayload`? Bagaimana representasi *Retainer Tree* di Chrome DevTools Heap Snapshot membuktikannya?

2. **Microtask Queue Saturation vs UI Responsiveness**
   Diberikan fungsi rekursif pemrosesan data array raksasa:
   ```javascript
   function processBatch(items) {
     if (items.length === 0) return;
     const chunk = items.splice(0, 100);
     computeSync(chunk);
     queueMicrotask(() => processBatch(items));
   }
   ```
   Apa dampak langsung dari implementasi ini terhadap *Total Blocking Time* (TBT) dan frame rate (60 FPS / 16.6ms window)? Bagaimana Anda merefaktor fungsi ini menggunakan `scheduler.postTask()` atau `MessageChannel` untuk mencegah frame dropping?

3. **Event Loop Race Condition pada Web Workers Communication**
   Saat mentransfer buffer data berukuran 200MB menggunakan `postMessage`, apa perbedaan mendasar dalam overhead memori dan CPU antara *Structured Clone Algorithm* dengan *Transferable Objects* (`ArrayBuffer`)? Mengapa akses ke *SharedArrayBuffer* tanpa koordinasi `Atomics` dapat menyebabkan data corruption/tearing pada level thread?

4. **Style Invalidation & CSS Containment**
   Mengapa modifikasi class pada root node (`<body>` atau `<html>`) dapat menyebabkan full-document layout invalidation? Bagaimana properti `contain: strict` atau `contain: content` mengisolasi subtree DOM sehingga layout engine membatasi kalkulasi batas rendering lokal tanpa melakukan traversal ke seluruh ancestor tree?

5. **Detached DOM Nodes Identification & GC Root Tracking**
   Sebuah single-page application (SPA) menghapus modul modal dialog dari DOM saat tombol *Close* ditekan, namun konsumsi memori browser terus meningkat seiring bertambahnya iterasi buka-tutup. Bagaimana cara melacak apakah referensi event listener window, closure internal, atau global store cache yang mempertahankan *detached DOM element* dari garbage collector?

---
## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Degenerasi TBT & Frame Drop pada E-Commerce Checkout Dashboard
Sebuah aplikasi e-commerce enterprise mengalami lonjakan metrik *Interaction to Next Paint* (INP) hingga 2400ms dan *Total Blocking Time* (TBT) mencapai 4200ms pada halaman checkout dengan 300+ field dinamis dan komponen tabel inventaris real-time. Trace Performance Profiler Chrome menunjukkan indikator *Long Task* berdurasi 350ms berulang kali diiringi baris merah bertuliskan *Forced Reflow / Layout Thrashing*. 
Investigasi awal menunjukkan bahwa setiap kali terjadi polling status harga via WebSocket (setiap 250ms), aplikasi membaca properti `.offsetHeight` dari container utama, lalu mengupdate lebar masing-masing baris secara berurutan dalam loop `forEach`.

* **Pertanyaan Diagnostik:**
  1. Identifikasi secara tepat baris eksekusi penyebab *Forced Synchronous Layout* dan jelaskan fase internal browser yang dipaksa berjalan secara prematur.
  2. Rancang arsitektur solusi mitigasi: Bagaimana Anda memisahkan fase *read* dan *write* DOM menggunakan teknik batching atau memanfaatkan `ResizeObserver` dan `requestAnimationFrame`?

---

### Skenario B: Race Condition Stateful Fetch pada Search Autocomplete
Fitur global search autocomplete memicu permintaan jaringan via `fetch()` pada event `input`. Pengguna mengetik string `"react"`, memicu 5 request paralel (`"r"`, `"re"`, `"rea"`, `"reac"`, `"react"`). Akibat latensi jaringan yang fluktuatif, response untuk request `"rea"` selesai pada $t = 800\text{ ms}$, sedangkan response untuk `"react"` selesai pada $t = 300\text{ ms}$. Hasil akhir yang tertampil di layar adalah data hasil pencarian untuk `"rea"`, menimpa hasil `"react"`.

* **Pertanyaan Diagnostik:**
  1. Mengapa penanganan promise chaining standar gagal mengatasi anomali temporal ini dari sudut pandang asinkronitas JavaScript?
  2. Implementasikan solusi tingkat produksi menggunakan `AbortController` untuk membatalkan sinyal request yang *stale*, atau rancang strategi *monotonic sequence identifier* untuk mengabaikan response out-of-order tanpa memory leak.

---

### Skenario C: Trade-off Arsitektur SSR Hydration Mismatch & Script Loading Strategy
Sebuah platform publikasi media berskala 50 juta hit/hari melakukan transisi arsitektur dari Client-Side Rendering (CSR) murni ke Server-Side Rendering (SSR). Namun, metrik *Largest Contentful Paint* (LCP) mereka turun drastis karena bundle JavaScript hidrasi sebesar 1.8MB memblokir interaksi pengguna selama 3.5 detik setelah markup HTML selesai di-render server. Selama masa *uncanny valley* tersebut, link navigasi tidak merespons klik, dan font web mengalami *Flash of Unstyled Text* (FOUT).

* **Pertanyaan Diagnostik:**
  1. Analisis arsitektur pemuatan resource: Bagaimana strategi penataan tag `<link rel="preload">`, loading font non-blocking, serta konfigurasi `<script type="module">` / `defer` harus dirombak untuk memprioritaskan CRP?
  2. Evaluasi trade-off antara *Full Client Hydration* vs *Progressive/Partial Hydration* (misalnya via Astro / React Server Components / Islands Architecture) dalam menekan TBT mendekati nol pada halaman yang didominasi konten statis.

---

## 4. Chapter Challenge
**Tantangan Praktis: High-Performance Virtualized List & Micro-Task Scheduler Engine**

### Deskripsi Masalah
Rendering 50.000 baris data tabular secara langsung ke dalam DOM akan membekukan UI thread, melipatgandakan alokasi heap browser hingga ratusan megabyte, dan memicu crash akibat memory pressure atau frame rate anjlok (< 5 FPS).

### Requirements
1. **Zero-Dependency Virtual Scroller Engine:**
   * Bangun modul TypeScript/ES2022 murni tanpa framework pihak ketiga.
   * Render hanya node DOM yang masuk dalam viewport dinamis plus buffer atas/bawah (misal: total ~30 DOM nodes aktif), terlepas dari jumlah total data (50.000 items).
   * Update visualisasi posisi scrollbar menggunakan `transform: translateY()` untuk memanfaatkan GPU Layer Compositing tanpa memicu *Layout Reflow*.
2. **Cooperative Task Scheduler:**
   * Bangun scheduler yang memecah pemrosesan/penyaringan (filtering) 50.000 item data tersebut menjadi potongan-potongan *time-sliced* (masing-masing < 5ms).
   * Gunakan `requestIdleCallback` (dengan fallback ke `MessageChannel`) agar UI tetap responsif pada 60 FPS selama komputasi berlangsung.
3. **Leak-Proof Resource Disposal:**
   * Implementasikan method `.destroy()` yang menghapus seluruh event listeners, memutus `ResizeObserver`, mengosongkan internal map cache, dan memastikan *Heap Snapshot* tidak menyisakan *Detached DOM Tree*.

### Constraints
* Dilarang menggunakan library virtualisasi eksternal (TanStack Virtual, react-window, dsb).
* Operasi scroll harus mempertahankan 60 FPS konstan di Chrome DevTools Rendering/Performance Monitor.
* Memory Heap delta maksimal setelah list di-unmount dan dilakukan *Force GC* adalah **$\le 5\%$** dari baseline awal.

### Expected Output
1. File modul implementasi `virtual-scroller.ts` dan `task-scheduler.ts` yang modular dan strictly-typed.
2. File pengujian performa HTML/JS untuk demonstrasi 50.000 baris data acak lengkap dengan benchmark metrics:
   * Frame rate logger via `requestAnimationFrame`.
   * Real-time calculation visual counter (read vs write DOM).
3. Bukti profil DevTools (Performance tab summary) yang memverifikasi ketiadaan *Long Task* (> 50ms) selama scrolling dan filtering berlangsung.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi V8 engine: Parser, AST, Bytecode via Ignition, Optimization pipeline via TurboFan, dan deoptimization triggers.
- [ ] Struktur memori Stack vs Heap, serta mekanisme kerja Generational Garbage Collection (Scavenger vs Full Mark-Sweep-Compact).
- [ ] Perilaku Event Loop W3C/HTML5 spec: Microtask queue, Macrotask/Task queue, Animation frame callbacks, dan browser repaint cycles.
- [ ] Detail Critical Rendering Path (CRP): HTML Parsing -> DOM, CSS Parsing -> CSSOM, Render Tree construction, Layout/Reflow, Paint, dan GPU Compositing.
- [ ] Penyebab Layout Thrashing dan perbedaan rendering cost antara layout-triggering properties (`width`, `top`), paint-triggering properties (`color`, `background`), dan composite-only properties (`transform`, `opacity`).
- [ ] Lifecycle dan scope deklarasi variabel: Scope Chains, Lexical Scoping, Hoisting, dan Temporal Dead Zone (TDZ).

### Saya tidak perlu menghafal:
- [ ] Angka pasti byte-size dari internal memory overhead objek C++ V8 di level kompilator.
- [ ] Nomor versi internal implementasi V8 di setiap update rilis berkala browser Chromium.
- [ ] Seluruh tabel matriks spesifikasi CSS properties lengkap dengan pemetaannya ke pipeline layout/paint (cukup memahami prinsip isolasi komposit dan menggunakan tooling profiling).

### Saya harus bisa melakukan:
- [ ] Membaca dan menganalisis Chrome DevTools *Performance Trace* untuk mendeteksi *Long Tasks*, *Layout Thrashing*, dan frame drops.
- [ ] Menganalisis *Heap Snapshots* dan *Allocation Instrumentation on Timeline* untuk mengisolasi memori bocor (*detached DOM nodes*, *retained closures*).
- [ ] Mengonfigurasi resource loading modern secara presisi: `preload`, `prefetch`, `modulepreload`, serta penempatan atribut `async` dan `defer`.
- [ ] Menulis kode manipulasi DOM performa tinggi dengan memisahkan batch operasi read/write menggunakan API native seperti `requestAnimationFrame` dan `ResizeObserver`.
- [ ] Mengimplementasikan *AbortController* dan *cooperative multi-tasking* untuk menjaga *Interaction to Next Paint* (INP) di bawah threshold 200ms pada beban pemrosesan berat.