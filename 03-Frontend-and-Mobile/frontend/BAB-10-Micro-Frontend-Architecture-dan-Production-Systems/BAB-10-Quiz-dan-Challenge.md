# BAB 10: Quiz, Challenge, & Knowledge Check
**Bab 10: Frontend Performance Engineering, Memory Profiling, & Resilience Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Browser Critical Rendering Path & Compositing Engine**  
   Jelaskan transformasi siklus hidup DOM tree dari tokenisasi HTML mentah hingga pembentukan frame visual di layar (DOM $\rightarrow$ CSSOM $\rightarrow$ Render Tree $\rightarrow$ Layout $\rightarrow$ Paint $\rightarrow$ Composite). Mengapa modifikasi properti geometris seperti `width` atau `top` memicu *Reflow* (Layout Thrashing) di Main Thread, sedangkan manipulasi via `transform` dan `opacity` dapat dilembagakan sepenuhnya di Compositor Thread melalui akselerasi GPU?

2. **Core Web Vitals Internal: LCP, CLS, dan INP**  
   Uraikan metrik Core Web Vitals (Largest Contentful Paint, Cumulative Layout Shift, dan Interaction to Next Paint). Khusus untuk **INP** (yang menggantikan FID), bagaimana JavaScript Event Loop membagi fase interaksi ke dalam *Input Delay*, *Processing Time*, dan *Presentation Delay*? Apa yang menyebabkan *Presentation Delay* membengkak meskipun handler JavaScript mengeksekusi callback di bawah 16ms?

3. **V8 Memory Management: Scavenger vs. Major GC (Mark-Sweep-Compact)**  
   Bagaimana V8 membagi Heap memory menjadi *New Space* (Nursery & Intermediate) dan *Old Space*? Jelaskan algoritma *Cheney's Copying Algorithm* pada Minor GC (Scavenger) dan transisinya menuju Major GC (*Incremental Marking*, *Concurrent Sweeping*, dan *Lazy Compacting*). Kondisi apa yang menyebabkan objek dipromosikan (*tenured*) prematur ke Old Space?

4. **HTTP Caching Directives & Stale-While-Revalidate Mechanics**  
   Analisis perbedaan semantik dan perilaku browser saat menangani `Cache-Control: no-cache`, `Cache-Control: no-store`, dan `Cache-Control: public, max-age=300, stale-while-revalidate=86400`. Bagaimana browser menangani validasi kondisional menggunakan *ETag* (Entity Tag / If-None-Match) versus *Last-Modified* (If-Modified-Since) ketika *max-age* telah kedaluwarsa?

5. **Client-Side Hydration vs. Islands Architecture**  
   Jelaskan bottleneck arsitektur dari *Full Client-Side Hydration* pada aplikasi Server-Side Rendered (SSR) monolitik (fenomena *Uncanny Valley*). Bandingkan mekanisme tersebut dengan *Islands Architecture* (seperti Astro) dan *Resumability* (seperti Qwik). Bagaimana serialisasi status (*state serialization*) dieksekusi tanpa mengharuskan runtime mengunduh dan mengeksekusi ulang seluruh pohon komponen?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Deteksi dan Mitigasi Detached DOM Tree via Chrome DevTools Memory Profiler**  
   Sebuah *Single Page Application* (SPA) mengalami kenaikan memori linear setiap kali pengguna berpindah rute (route transition). Saat mengambil *Heap Snapshot*, Anda melihat ribuan node dengan label `Detached HTMLDivElement`. Jelaskan akar masalah penyebab referensi memori tertahan (*retaining paths*) pada JavaScript heap, bagaimana membaca grafik alokasi retainer, dan pola kode apa yang paling sering mengunci siklus pembersihan garbage collector pada event listener atau closure.

2. **Debounce, Throttle, dan `requestAnimationFrame` Synchronization**  
   Diberikan kasus di mana sebuah visual canvas atau infinite list harus merespons event `scroll` dan `mousemove` dengan densitas tinggi. Analisis perbedaan performa mikro antara:
   - Debouncing berbasis timer (`setTimeout`)
   - Throttling berbasis timestamp
   - Penjadwalan frame via `window.requestAnimationFrame()` (rAF)  
   Kapan `requestIdleCallback` harus diintegrasikan, dan apa konsekuensinya jika fungsi manipulasi DOM dipanggil langsung di dalam callback `requestIdleCallback`?

3. **Content Security Policy (CSP) Level 3 & Dynamic Script Injection**  
   Sebuah aplikasi skala enterprise menerapkan CSP ketat:  
   `script-src 'self' 'nonce-rAnd0m123' 'strict-dynamic'; object-src 'none'; base-uri 'none';`  
   Jelaskan bagaimana mekanisme `'strict-dynamic'` bekerja ketika sebuah library pihak ketiga (misalnya loader analitik terpercaya) mencoba menyuntikkan elemen `<script>` baru ke dalam DOM runtime. Mengapa atribut `unsafe-inline` secara otomatis diabaikan oleh browser modern jika `nonce` atau `hash` dideklarasikan bersamaan?

4. **Service Worker Lifecycle & Cache Poisoning Mitigation**  
   Pada pembaruan aplikasi PWA, berkas Service Worker (`sw.js`) baru gagal mengambil alih kendali klien yang sedang aktif (*stuck at waiting phase*). Jelaskan siklus hidup Service Worker (*Register*, *Install*, *Wait/Activate*). Bagaimana cara memanfaatkan event `skipWaiting()` dan `clients.claim()` secara aman tanpa menyebabkan inkonsistensi aset (*version skew/cache poisoning*) bagi pengguna yang sedang membuka tab aktif?

5. **Micro-Frontend Isolation: Shadow DOM vs. Scoped CSS & Global Window Pollution**  
   Dalam arsitektur Micro-Frontend berbasis Module Federation, dua aplikasi mikro independen diinjeksi ke dalam satu shell host. Tim A menggunakan Tailwind v3, sedangkan Tim B memodifikasi CSS global framework legacy. Evaluasi trade-off isolasi menggunakan:
   - Web Components (*Shadow DOM* dengan `mode: 'closed'`)
   - CSS Modules / PostCSS scoping prefixes
   - JavaScript Sandboxing via Proxy (`window` sandbox proxy)  
   Bagaimana cara mencegah memory leak ketika sebuah Micro-Frontend di-*unmount* dari Host DOM namun meninggalkan event listener pada `window.document` global?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Degradasi Masif LCP & INP pada Event Flash Sale E-Commerce
Platform e-commerce mengalami lonjakan trafik 10x lipat saat flash sale. Tim pemantau Real User Monitoring (RUM) melaporkan bahwa skor LCP melonjak dari 1.8 detik menjadi 6.4 detik pada perangkat mobile low-end, sementara skor INP drop ke kategori *Poor* (> 500ms) saat pengguna menekan tombol "Beli Sekarang". Analisis profiler menunjukkan:
- Banner pahlawan (*hero image*) dimuat terlambat karena *font swapping* (FOIT) dan ratusan kilobyte script analitik/marketing pihak ketiga yang memblokir parser HTML di tag `<head>`.
- Tombol "Beli Sekarang" memicu validasi form sinkron yang berat, manipulasi state global yang memicu *re-render* pada seluruh komponen keranjang, dan pengiriman 4 event analitik sinkron menggunakan `fetch` sebelum redirect.

**Pertanyaan Diagnostik:**
1. Rancang arsitektur pemuatan aset pada critical path untuk menormalkan LCP (minimalisasi resource contention, strategi `fetchpriority`, preloading, dan decoding font).
2. Dekonstruksi alur kerja handler klik "Beli Sekarang" untuk memangkas Presentation Delay dan Input Delay pada INP di bawah 200ms menggunakan teknik task splitting (`scheduler.yield()` atau message channel queuing) dan non-blocking tracking (`navigator.sendBeacon`).

---

### Skenario B: Race Condition dan Cache Desynchronization pada Optimistic UI
Aplikasi kolaborasi dokumen real-time mengimplementasikan *Optimistic Updates* pada mutasi data kanban board. Saat koneksi jaringan pengguna berada pada status *flaky* (tinggi latensi dan sering putus-sambung):
- Pengguna memindahkan Card X dari "To Do" ke "In Progress", lalu langsung memindahkannya ke "Done" dalam rentang waktu 300ms.
- Permintaan jaringan pertama (mutasi ke "In Progress") mengalami timeout lokal, memicu mekanisme rollback state di frontend.
- Namun, permintaan jaringan kedua (mutasi ke "Done") berhasil mencapai server terlebih dahulu sebelum permintaan pertama benar-benar dibatalkan oleh jaringan upstream.
- Akibatnya, UI klien melakukan rollback ke status "To Do", sementara database backend menyimpan status "Done", merusak integritas konsistensi data klien-server.

**Pertanyaan Diagnostik:**
1. Analisis mengapa arsitektur state management lokal gagal menangani *out-of-order execution* dan pembatalan asinkron ini.
2. Rancang state machine berbasis *Deterministic Event Sourcing* atau mekanisme *Vector Clock / AbortController registry* di sisi klien untuk memastikan state lokal tetap sinkron dan bebas dari race condition tanpa harus memblokir interaksi pengguna dengan loading spinner global.

---

### Skenario C: Kebocoran Memori Skala Besar pada Dashboard FinTech Real-Time
Dashboard analitik finansial memproses streaming harga instrumen derivatif via WebSocket dengan throughput rata-rata 1.500 pesan per detik. Dashboard dibangun menggunakan React dan pustaka visualisasi grafik Canvas/WebGL. Setelah aplikasi berjalan selama 45 menit di browser agen trading, konsumsi RAM browser melonjak dari 180MB menjadi 3.2GB, menyebabkan tab crash (*OOM - Out of Memory*).
Investigasi awal menunjukkan:
- Objek WebSocket message ditambahkan langsung ke dalam state array tanpa batasan ukuran (*unbounded sliding window*).
- Setiap frame data grafik memicu pembuatan closure baru di dalam fungsi render yang mengikat referensi ke state instrumen sebelumnya.
- Objek WebGL texture tidak pernah dipanggil `gl.deleteTexture()` saat instrumen ditutup oleh pengguna.

**Pertanyaan Diagnostik:**
1. Rancang strategi pengolahan data stream berkecepatan tinggi di frontend tanpa membebani Main Thread UI (analisis penggunaan *Web Workers*, *Transferable Objects / SharedArrayBuffer*, dan *Ring Buffers / Circular Data Structures*).
2. Buat protokol manajemen siklus hidup memori untuk resource eksternal (WebGL/Canvas context) agar garbage collection dapat berjalan mulus tanpa fragmentasi memory pool.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Virtualized Infinite Ledger Engine with Zero Layout Thrashing

#### Problem Statement
Anda ditugaskan membangun engine tabel virtual (*Virtualized Grid Engine*) zero-dependency murni dari vanilla TypeScript. Engine ini harus mampu merender **1.000.000 (satu juta) baris data finansial transaksi real-time** dengan 20 kolom per baris pada frame rate konsisten 60/120 FPS tanpa lag, memory leak, atau layout thrashing, bahkan ketika data diperbarui via streaming mock WebSocket (100 updates/detik).

#### Requirements:
1. **Virtualization Math Engine**:
   - Hitung offset tampilan secara presisi: hanya render node DOM yang berada di dalam *Viewport Window* ditambah *Buffer Zone* (misal: 5 baris di atas dan di bawah viewport).
   - Terapkan teknik *Absolute Positioning with Hardware Accelerated Transforms* (`transform: translateY(...)`) untuk memposisikan baris virtual, menghindari manipulasi manual properti `top`.
2. **DOM Node Recycling**:
   - Jumlah total DOM elements di dalam container harus konstan (misal: maksimal 30 elemen `<tr>` atau `<div>` baris saja yang ada di DOM tree sepanjang waktu).
   - Jangan pernah melakukan `document.createElement` berulang saat scroll; lakukan pembaruan data (*node textContent patching*) pada pool elemen yang sudah ada.
3. **Decoupled Scroll Pipeline**:
   - Pisahkan pembacaan posisi scroll (`scrollTop`) dari penulisan visual DOM. Wajib menggunakan `requestAnimationFrame` untuk throttling pembacaan dan rendering.
   - Cegah layout thrashing: tidak boleh ada operasi *read-then-write-then-read* pada properti layout browser dalam frame yang sama.
4. **Resilient Stream Ingestion**:
   - Simulasi data stream: terima pembaruan data acak (100 baris diperbarui per detik).
   - Update nilai sel tanpa me-render ulang seluruh viewport virtual jika sel yang diperbarui berada di luar viewport.

#### Constraints:
- Dilarang menggunakan pustaka pihak ketiga (misal: TanStack Virtual, React Virtualized, Lodash, dll.).
- Konsumsi memori Heap JavaScript tidak boleh melampaui **50MB** secara stabil setelah dijalankan selama 5 menit continuous scrolling.
- INP (Interaction to Next Paint) saat pengguna melakukan sort/filter pada 1 juta baris data tidak boleh melebihi **100ms** (gunakan `Web Worker` untuk operasi komputasi berat sorting/filtering).

#### Expected Output:
- Modul TypeScript modular:
  1. `Worker.ts`: Komputasi sort/filter pada TypedArrays/ArrayBuffers.
  2. `VirtualScroller.ts`: Core virtualizer, kalkulasi indeks, dan listener scroll berbasis rAF.
  3. `DomPool.ts`: Pool daur ulang node DOM baris tabel.
  4. `index.html` & `style.css`: Antarmuka minimalis untuk demonstrasi performa lengkap dengan visual counter FPS real-time dan memory consumption display (`performance.memory`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme parsing HTML, kalkulasi CSSOM, pembuatan Layout Tree, Paint Layers, dan Compositing pada browser engine (Blink/Gecko/WebKit).
- [ ] Tiga metrik utama Core Web Vitals (LCP, CLS, INP): metrik ambang batas, metode pengukuran RUM vs. Lab, dan teknik optimasinya.
- [ ] Arsitektur internal V8 Heap: siklus Minor GC (Scavenger) dan Major GC (Mark-Sweep-Compact), serta penyebab fatal terjadinya retain pointer memory leak.
- [ ] Perbedaan eksekusi mikro-tugas (*microtasks*), makro-tugas (*macrotasks*), animasi frame (`requestAnimationFrame`), dan background tasks (`requestIdleCallback`, `scheduler.postTask`).
- [ ] Model eksekusi Service Worker: caching strategies (*Cache First*, *Network First*, *Stale-While-Revalidate*), streaming response, dan penanganan lifecycle update.
- [ ] Ancaman keamanan client-side (XSS, CSRF, Clickjacking) dan perimeter pertahanannya (Strict Content Security Policy, Trusted Types, Subresource Integrity, Cross-Origin Isolation).

### Saya tidak perlu menghafal:
- [ ] Daftar lengkap vendor prefix CSS historis (`-webkit-`, `-moz-`, `-ms-`) yang sudah di-deprecate oleh standar modern.
- [ ] Nilai byte heksadesimal representasi opcode internal V8 engine.
- [ ] Seluruh tabel konfigurasi HTTP/2 dan HTTP/3 framing bits di level protokol transport.
- [ ] Urutan numerik spesifik dari puluhan flag experimental di `chrome://flags`.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan mengeliminasi Long Tasks (> 50ms) menggunakan panel Chrome DevTools Performance, Flamegraph, dan Bottom-Up call tree.
- [ ] Mengambil Heap Snapshot dan menganalisis Retainer Tree untuk melacak akar penyebab Detached DOM nodes dan uncollected closures.
- [ ] Mengonfigurasi bundle analyzer (Webpack/Vite/Rollup) untuk mengeliminasi dead code (*Tree Shaking*), memecah chunk (*Code Splitting*), dan mengisolasi dynamic imports.
- [ ] Mengimplementasikan *Web Workers* dan *OffscreenCanvas* untuk memindahkan komputasi matematika kompleks dan render visual intensif dari Main Thread.
- [ ] Mengonfigurasi header keamanan tingkat enterprise (`Content-Security-Policy`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Embedder-Policy`) tanpa merusak fungsionalitas aplikasi produksi.
- [ ] Membangun custom instrumentation pelaporan performa menggunakan `PerformanceObserver` API untuk menangkap *Long Animation Frames* (LoAF) dan metrik web vitals secara programmatic.