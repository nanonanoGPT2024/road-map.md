# BAB 08: Quiz, Challenge, & Knowledge Check
**Browser Runtime, Network Protocols & Rendering Engine Pipelines**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Critical Rendering Path (CRP) dan Eksekusi Script
Jelaskan secara mendalam siklus hidup Critical Rendering Path sejak byte HTML pertama diterima melalui soket jaringan hingga *First Meaningful Paint*. Uraikan bagaimana *HTML Tokenizer* dan *CSSOM Construction* berinteraksi secara deterministik. Mengapa tag `<script>` standar bersifat *parser-blocking*, bagaimana mekanisme *speculative parsing* (*preload scanner*) memitigasinya, dan apa perbedaan internal status eksekusi antara atribut `defer` dan `async` dalam kaitannya dengan siklus hidup `DOMContentLoaded`?

### Soal 1.2: Orkestrasi Event Loop vs Rendering Pipeline
Spesifikasi HTML Living Standard mendefinisikan bahwa *Rendering Opportunity* terjadi di antara perputaran task pada Event Loop. Jelaskan urutan eksekusi presisi dari:
1. Task (Macrotask)
2. Microtask Queue (termasuk rekursi via `queueMicrotask` / `Promise`)
3. `requestAnimationFrame` (rAF) callback
4. IntersectionObserver callback
5. Style Recalculation, Layout, Pre-Paint, Paint, dan Composite.

Apa kriteria teknis yang digunakan browser runtime untuk memutuskan apakah sebuah *Rendering Opportunity* akan dieksekusi atau dilewati (*dropped frame*) pada layar 60Hz/120Hz?

### Soal 1.3: Arsitektur Multi-Process Chromium dan Sandboxing
Arsitektur peramban modern (seperti Chromium) memisahkan runtime ke dalam beberapa proses terisolasi: *Browser Process*, *Renderer Process*, *GPU Process*, dan *Network Service*. Uraikan tanggung jawab masing-masing proses ini serta mekanisme IPC (*Inter-Process Communication*) berbasis Mojo. Jelaskan implikasi keamanan dari arsitektur *Site Isolation* pasca kerentanan Spectre/Meltdown dan mengapa isolasi memori level-proses ini membatasi berbagi objek memori JavaScript secara langsung antar tab/iframe.

### Soal 1.4: Evolusi Protokol Transportasi: HTTP/1.1 vs HTTP/2 vs HTTP/3
Analisis batas performa dari ketiga protokol jaringan berikut dalam konteks browser loading pipeline:
- **HTTP/1.1**: *Head-of-Line (HoL) Blocking* pada level aplikasi dan soket starvation (domain sharding).
- **HTTP/2**: Binary Framing, multiplexing, stream prioritization, dan kelemahan laten *TCP-level HoL Blocking* saat packet loss tinggi.
- **HTTP/3 (QUIC)**: Enkapsulasi UDP, independent byte-stream recovery, 0-RTT handshakes, dan migrasi koneksi (*Connection ID*).

Bagaimana arsitektur *Network Service* peramban mengelola stream state machine pada HTTP/2 dan HTTP/3 untuk mencegah resource contention?

### Soal 1.5: Taksonomi Mutasi DOM: Reflow, Repaint, dan Compositing
Definisikan perbedaan komputasional antara:
1. **Layout / Reflow** (Blink/Gecko geometry calculation)
2. **Paint** (Rasterization display-list generation via Skia/Impeller)
3. **Composite** (Layer positioning and GPU drawing via Direct3D/Metal/Vulkan)

Jelaskan bagaimana konsep *Composited Layer* (GraphicsLayer) dibentuk. Properti CSS apa saja yang dijamin dapat diakselerasi secara murni pada *Compositor Thread* tanpa melibatkan *Main Thread*, dan mengapa over-compositing (*layer explosion*) justru dapat menurunkan frame rate serta membebani VRAM secara drastis?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik Layout Thrashing & Forced Synchronous Layout
Perhatikan potongan kode berikut:
```javascript
function updateElementWidths(elements) {
  for (let i = 0; i < elements.length; i++) {
    const parentWidth = elements[i].parentElement.getBoundingClientRect().width;
    elements[i].style.width = `${parentWidth * 0.5}px`;
  }
}
```
Bedah secara internal apa yang terjadi pada antrean dirty bit tree pada rendering engine ketika kode di atas dieksekusi. Mengapa pola *interleaved read-write* ini memicu *Forced Synchronous Layout* (Layout Thrashing)? Tuliskan refactoring optimal menggunakan paradigma batched read-write atau `requestAnimationFrame` scheduler manual, serta jelaskan bagaimana Anda memverifikasi perbaikannya melalui Chromium Performance DevTools Flame Chart.

### Soal 2.2: Detached DOM Tree & Heap Snapshot Forensics
Sebuah Single Page Application (SPA) berskala enterprise mengalami pertumbuhan konsumsi memori sistem secara linear dari waktu ke waktu (*slow memory leak*). Setelah dilakukan *Garbage Collection (GC)* paksa di Chromium DevTools, alokasi memori tidak kunjung turun.
1. Jelaskan konsep *Retainer Tree*, *Shallow Size*, dan *Retained Size* pada V8 Heap Profiler.
2. Apa yang dimaksud dengan *Detached HTMLCanvasElement* atau *Detached DOM Tree*, dan bagaimana sebuah *closure* event listener atau referensi pada `WeakMap` yang salah dikonfigurasi dapat mencegah sub-tree DOM tersebut di-*sweep* oleh V8 Mark-Sweep-Compact collector?
3. Rancang prosedur 4 langkah investigatif menggunakan *Allocation Instrumentation on Timeline* untuk mengisolasi baris kode JavaScript yang menahan referensi tersebut.

### Soal 2.3: Lifecycle Service Worker, Caching Engine, dan Streaming Responses
Ketika Service Worker mengintersepsi network request melalui event `fetch`:
```javascript
self.addEventListener('fetch', (event) => {
  // Scenario: Streaming responses
});
```
Bagaimana Anda memanfaatkan antarmuka `ReadableStream` dan `TransformStream` dalam Service Worker untuk menggabungkan header shell ter-cache (*Cache Storage API*) dengan stream payload data yang datang secara langsung dari origin server via HTTP/2? Jelaskan siklus *chunked transfer-encoding* yang terjadi di antara SW thread, network stack, dan renderer document parser untuk mencapai TTFB (*Time to First Byte*) mendekati 0ms pada navigasi halaman berikutnya.

### Soal 2.4: Compositor Thread Offloading & Scroll Jank Mitigation
Mengapa penggunaan event handler seperti `window.addEventListener('scroll', handler)` atau `touchmove` secara default dapat mengunci *Compositor Thread* dan menyebabkan *Scroll Jank*, meskipun handler tersebut kosong?
- Jelaskan mekanisme internal penandaan area sebagai *Fast Scrollable Region* vs *Non-Fast Scrollable Region* oleh Blink rendering engine.
- Bagaimana atribut `{ passive: true }` memodifikasi dispatch sequence event loop dari level browser kernel ke compositor queue?
- Apa peran CSS `touch-action` dalam mitigasi latency gesture pada antarmuka mobile?

### Soal 2.5: Early Hints (HTTP 103), Resource Hints, dan Socket Warm-Up
Analisis arsitektur pertukaran data pada level jaringan ketika peramban menerima response status code `HTTP 103 Early Hints`:
1. Bagaimana browser socket manager menangani link rel headers (`preload`, `preconnect`) yang dikirimkan pada fase 103 sebelum response body 200 OK dipancarkan oleh backend server?
2. Bandingkan dampak latensi dari `dns-prefetch`, `preconnect`, `prefetch`, dan `preload` terhadap *Network Prioritization Engine* di Chromium (ResourceFetcher priority matrix: *VeryHigh*, *High*, *Medium*, *Low*, *VeryLow*).
3. Apa risiko performa (*bandwidth saturation* & *cache poisoning*) jika developer salah mendefinisikan prioritas dependency CSS/Font via preload?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Crash dan Drop Frame Masif pada Mobile Trading Terminal
**Konteks**: Sebuah platform Web Trading FinTech menyajikan grafik candlestick real-time dan buku pesanan (*Order Book*) dengan throughput 2.000 pembaruan harga per detik via WebSocket. Pada perangkat mobile kelas menengah ke bawah (*low-to-mid tier Android*), tab browser mengalami degradasi performa ekstrem: frame rate jatuh ke 4–8 FPS, terjadi *input delay* hingga 2.500ms, dan setelah 30 detik aplikasi mengalami crash tanpa uncaught JavaScript error (*Out-Of-Memory / OOM termination* oleh OS LMK - Low Memory Killer).

**Investigasi Awal**:
- Main Thread terus-menerus didominasi oleh kalkulasi parsing data JSON dari WebSocket dan mutasi innerHTML/text DOM nodes.
- DevTools memaparkan jutaan mutasi style micro-batches dan alokasi objek sementara yang memicu V8 GC scavenge setiap 40 milidetik.
- GPU Process memory consumption meningkat tajam akibat penggunaan CSS `box-shadow` dinamis dan `will-change: transform` pada ribuan baris order book.

**Pertanyaan Diagnostik**:
1. **Analisis Bottleneck**: Identifikasi dan jelaskan 3 akar masalah fundamental pada CRP, Event Loop, dan Memory Subsystem yang menyebabkan crash dan drop frame tersebut.
2. **Redesain Arsitektur**: Rancang arsitektur decoupled pipeline yang memindahkan tugas deserialisasi data dan throttling pembaruan keluar dari Main Thread (misal: Web Workers, `SharedArrayBuffer` / `OffscreenCanvas`, atau `Atomics`).
3. **Optimasi Rendering**: Bagaimana Anda merestrukturisasi representasi visual Order Book untuk mengeliminasi alokasi DOM yang berlebihan (*virtualization technique*) dan memangkas alokasi VRAM pada Compositor Layer?

---

### Skenario B: Race Condition dan Cache Invalidation pada Micro-Frontend Shell
**Konteks**: Sebuah portal enterprise menggunakan arsitektur Micro-Frontend berbasis runtime module loading (Module Federation) yang di-cache menggunakan Service Worker dengan strategi *Stale-While-Revalidate* (SWR). Selama deployment versi baru v2.1.0 di jam sibuk, sekitar 15% pengguna melaporkan antarmuka yang pecah (*blank white screen* atau crash JavaScript: `TypeError: Cannot read properties of undefined`).

**Investigasi Awal**:
- Shell container mendownload modul core via Service Worker, sementara beberapa dynamic chunks diunduh langsung dari CDN menggunakan HTTP/2 multi-stream.
- Terjadi ketidakcocokan hash file: Host container v2.1.0 mengeksekusi chunk legacy v2.0.4 yang tersimpan di Cache Storage lokal, sementara chunk dependensinya meminta chunk v2.1.0 dari network yang memiliki contract API berbeda.
- Beberapa aset gagal dimuat dengan galat `net::ERR_HTTP2_PROTOCOL_ERROR` karena origin edge CDN membatasi concurrent streams per TCP connection saat traffic spike.

**Pertanyaan Diagnostik**:
1. **Root Cause Mapping**: Jelaskan bagaimana race condition antara Service Worker fetch event handling, cache updating lifecycle, dan HTTP/2 stream multiplexing dapat menyebabkan diskrepansi versi dependensi runtime ini.
2. **Mitigasi Protokol Jaringan**: Mengapa `ERR_HTTP2_PROTOCOL_ERROR` terjadi pada skenario concurrent chunk loading, dan bagaimana konfigurasi network headers serta HTTP client throttling di runtime browser dapat mencegahnya?
3. **Atomic Deployment Strategy**: Rancang mekanisme sinkronisasi cache level-klien yang deterministik (misalnya: *Atomic Cache Versioning* atau *Service Worker Skip Waiting orchestration*) untuk memastikan bahwa sebuah sesi peramban tidak pernah mengeksekusi aset heterogen dari dua versi rilis yang berbeda.

---

### Skenario C: Trade-off Arsitektur Visualisasi Big Data: DOM vs Canvas vs WebGL/WebGPU
**Konteks**: Tim Anda ditugaskan membangun modul *Network Topology Graph* interaktif yang harus memvisualisasikan 50.000 simpul (*nodes*) dan 150.000 relasi (*edges*). Pengguna menuntut kemampuan drag-and-drop, zoom-pan halus pada 60 FPS, serta dynamic node clustering dan real-time filtering berdasarkan data stream telemetry.

**Trade-off Pilihan Teknologi**:
- **Pendekatan 1**: Pure SVG / HTML DOM elements dengan CSS Transitions dan library D3.js.
- **Pendekatan 2**: Single 2D `<canvas>` element yang dikendalikan oleh Main Thread rendering loop.
- **Pendekatan 3**: `OffscreenCanvas` di dalam Web Worker yang merender visualisasi via WebGL / WebGPU pipeline, berkomunikasi dengan Main Thread hanya untuk delegasi event input user.

**Pertanyaan Diagnostik**:
1. **Analisis Skalabilitas Pipeline**: Evaluasi keterbatasan teknis Pendekatan 1 dan Pendekatan 2 ditinjau dari footprint memori per node (DOM overhead), kompleksitas kalkulasi *Style/Layout/Paint*, dan saturasi Main Thread.
2. **Deep Dive Web Worker + OffscreenCanvas (Pendekatan 3)**:
   - Bagaimana penanganan sinkronisasi *Hit Testing* (mendeteksi node mana yang di-klik pengguna) saat rendering dilakukan di Worker thread yang tidak memiliki akses ke DOM events (`MouseEvent`, `TouchEvent`)?
   - Bagaimana memory model transfer data (`ArrayBuffer` transferable objects vs structured clone) harus diimplementasikan agar pertukaran data telemetry ke worker beroperasi dengan latensi sub-milidetik tanpa *GC pausing*?
3. **Rekomendasi Arsitektural**: Susun matriks keputusan teknis yang mencakup: Throughput, FPS Stability, Kompleksitas Kode, dan Kompatibilitas Peramban untuk membenarkan pilihan arsitektur Anda di hadapan Enterprise Architecture Board.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance 60 FPS Data Stream Engine
Rancang dan bangun sebuah modul JavaScript vanilla modular (*Production-Grade, Zero External Dependencies*) yang menerima continuous high-frequency stream data jaringan dan merendernya ke layar tanpa pernah menyebabkan *Forced Synchronous Layout*, meminimalkan garbage collection, dan menjaga rendering stabil pada kecepatan 60/120 FPS.

#### Problem Statement
Sebagian besar antarmuka pemantauan data real-time gagal memisahkan antara *network ingestion rate* dan *screen refresh rate*, mengakibatkan *micro-freezes* akibat over-rendering DOM dan memory thrashing. Anda diminta membangun engine visualisasi streaming feed yang terisolasi dan tangguh.

#### Requirements
1. **Network Streaming Ingestion**:
   - Konsumsi mock data stream menggunakan `ReadableStream` over `fetch` (atau simulasikan via `TransformStream` yang memancarkan 5.000 entri data per detik).
   - Parsing chunk biner/teks dilakukan secara progresif menggunakan `TextDecoderStream` tanpa memblokir thread eksekusi utama.
2. **Backpressure & Decoupled State Management**:
   - Implementasikan *ring buffer* (circular buffer) berbasis `Uint32Array` atau `Float64Array` tetap (*fixed size*) untuk menampung data mentah sebelum dirender.
   - Buat mekanisme *Backpressure*: jika consumer rendering engine tertinggal di belakang network producer, terapkan strategi *drop/coalesce telemetry oldest frames* secara otomatis tanpa kebocoran memori.
3. **Render Pipeline Coordination**:
   - Sinkronisasikan render pipeline secara eksklusif menggunakan `requestAnimationFrame`.
   - Implementasikan arsitektur *DOM Recycling / Windowing Virtual List* (hanya merender elemen yang masuk dalam *viewport* ditambah *overscan buffer* kecil).
   - Hindari *layout thrashing* total: semua kalkulasi dimensi posisi (`getBoundingClientRect` / offset reading) harus dieksekusi terisolasi dari proses penulisan mutasi style (`transform: translate3d(...)`).
4. **Telemetry Instrumentation**:
   - Sertakan FPS Meter dan Performance Observer in-app menggunakan `PerformanceObserver` API untuk memantau metrik:
     - `longtask` duration
     - Frame Drops / Interrupted Frames
     - Cumulative Layout Shift (CLS)

#### Constraints
- **Murni Vanilla JavaScript (ES2022+)**: Dilarang menggunakan UI Frameworks (React, Vue, dll.) atau library virtualisasi (TanStack Virtual, dll.).
- **Zero Style-Recalculation Leak**: Mutasi DOM visual murni hanya boleh menyentuh properti `transform` dan `opacity` pada elemen yang telah di-promote ke *Compositor Layer* menggunakan `will-change: transform`.
- **Memory Footprint**: Heap usage JavaScript harus konstan (*flat profile*) pada DevTools Memory Profiler setelah berjalan stabil selama 5 menit (Zero Object Allocation dalam loop rAF).

#### Expected Output
1. File modul implementasi lengkap: `StreamProcessor.js`, `VirtualRenderer.js`, dan `PerformanceMonitor.js`.
2. Contoh file HTML `index.html` pengujian beban (*stress-test testbed*) yang mensimulasikan ingest 50.000 baris data dengan viewport scrolling interaktif.
3. Skrip verifikasi profil performa konsol yang mencatat laporan audit real-time:
   ```text
   [TELEMETRY REPORT]
   Average FPS        : 59.8 FPS
   Long Tasks Count   : 0 detected
   Heap Allocated Var : < 2.5 MB variance over 60s
   Forced Reflows     : 0 instances
   ```

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis Anda pada domain Browser Internals, Network Pipelines, dan High-Performance Web Execution.

### Saya harus memahami:
- [ ] Mekanisme parsing rekursif HTML Parser, CSSOM Parser, dan penyusunan internal *Render Tree*.
- [ ] Siklus pasti fase rendering: *Parsing -> Style -> Layout -> Pre-Paint -> Paint -> Layerization -> Rasterization -> Composite*.
- [ ] Peran dan batasan arsitektur multi-thread/multi-process Chromium (*Main Thread, Worker Threads, Compositor Thread, GPU Thread*).
- [ ] Detail antrean Event Loop: prioritas Task, penanganan Microtask starvation, dan titik intervensi rendering engine (*Rendering Opportunity*).
- [ ] Karakteristik transport layer HTTP/1.1, HTTP/2 binary framing layer, dan arsitektur QUIC/UDP pada HTTP/3.
- [ ] Mekanisme *Layer Promotion* (faktor pemicu, trade-off alokasi VRAM, dan artefak *implicit compositing*).
- [ ] Lifecycle lengkap Service Worker: instalasi, aktivasi, network fetch interception, dan Cache Storage management.
- [ ] Algoritma Garbage Collection V8 (Scavenger / Minor GC vs Mark-Sweep-Compact / Major GC) serta pemicu write-barrier.
- [ ] Cara kerja *Speculative HTML Parser* / *Preload Scanner* dan prioritas resolusi aset jaringan.
- [ ] Perbedaan teknis rendering berbasis DOM vs Canvas 2D vs Hardware-Accelerated Contexts (WebGL/WebGPU).

### Saya tidak perlu menghafal:
- [ ] Nilai integer bitmask dari status internal node C++ pada source code WebCore/Blink.
- [ ] Binary packet structure internal (header bytes) frame individual QUIC atau TLS record layer di luar konsep logisnya.
- [ ] Daftar lengkap dari 100+ properti CSS yang memicu layout recalculation (cukup memahami prinsip bahwa mutasi dimensi/geometri memicu Reflow, sedangkan tampilan visual/warna memicu Repaint).
- [ ] Signature parameter C++ binding untuk Mojo IPC calls di antara Chromium components.

### Saya harus bisa melakukan:
- [ ] Menganalisis flame chart Chromium DevTools Performance panel untuk mendiagnosis *Long Tasks*, *Layout Thrashing*, dan *Dropped Frames*.
- [ ] Mengambil, membaca, dan membandingkan *Heap Snapshots* untuk menemukan *Retained DOM Nodes* dan closure memory leaks.
- [ ] Menulis kode manipulasi DOM dinamis yang menjamin *zero forced synchronous reflows*.
- [ ] Mengonfigurasi antarmuka `ReadableStream` untuk streaming network response langsung ke parsing data stream atau Service Worker context.
- [ ] Menggunakan `PerformanceObserver` API untuk mengukur metrik *Web Vitals* secara programatis (LCP, INP, CLS) dan mendeteksi script blocking time langsung di lingkungan produksi.
- [ ] Mengimplementasikan *Compositor-only animations* menggunakan Web Animations API atau CSS transforms/opacity murni untuk mencapai performa UI 60/120 FPS tanpa degradasi.