# SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran**: Pemrograman JavaScript Lanjutan (Advanced JavaScript & Browser Internals)
* **Kategori**: 02-Programming-Languages
* **Modul**: Bab 08 Module 01: Browser Runtime, Network Protocols & Rendering Engine Pipelines
* **Prasyarat**:
  * Pemahaman mendalam tentang JavaScript Event Loop (Microtask vs Macrotask).
  * Pemahaman dasar arsitektur DOM (Document Object Model) dan CSSOM (CSS Object Model).
  * Pengenalan protokol jaringan dasar (model OSI, TCP/IP, HTTP).
* **Estimasi Waktu**: 6–8 Jam (Teori Mendalam, Analisis Trace Profiling, dan Implementasi Hands-on)
* **Tingkat Kesulitan**: Advanced / Enterprise-Grade

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Multi-Process Architecture pada Modern Browser Engine**: Menguraikan isolasi tanggung jawab antara Browser Process, Renderer Process, GPU Process, dan Network Service, serta mengidentifikasi mekanisme Inter-Process Communication (IPC) via Mojo.
2. **Membedah Transmisi Data Protokol Jaringan**: Menganalisis alur request-response tingkat rendah mulai dari DNS Resolution, TCP 3-Way Handshake, TLS 1.3 Cryptographic Handshake, hingga perbedaan transport layer antara HTTP/1.1 (pipelining hol-blocking), HTTP/2 (binary framing & multiplexing), dan HTTP/3 (QUIC via UDP).
3. **Mengurai Critical Rendering Path (CRP)**: Menjelaskan deterministik parsing HTML/CSS menjadi DOM dan CSSOM, konstruksi Render Tree, Layouting (Reflow), Painting, Rasterization, hingga Compositing oleh GPU.
4. **Mencegah Layout Thrashing & Forced Synchronous Layouts**: Mendeteksi pembacaan dan penulisan geometri DOM yang tidak sinkron secara programmatic dan mengoptimalkannya dengan batching serta micro-benchmarking via Performance APIs.
5. **Mengimplementasikan Strategi Rendering 60/120 FPS**: Merancang komponen UI kompleks yang mengeliminasi bottleneck Main Thread dengan mendelegasikan transform, opacity, dan clipping ke Compositor Thread secara hardware-accelerated.
6. **Menerapkan Advanced Browser Security Boundary**: Mengonfigurasi Cross-Origin Opener Policy (COOP), Cross-Origin Embedder Policy (COEP), dan Site Isolation untuk mengamankan isolasi memori terhadap eksploitasi mikroarsitektur CPU tingkat rendah (seperti Spectre/Meltdown).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: Orkes Industri Modern Berbasis Pabrik Multi-Unit
Banyak developer membayangkan peramban (browser) sebagai satu executable monolitik sederhana yang membaca teks HTML lalu menggambar piksel ke layar. Mental model ini berbahaya dan menghasilkan aplikasi web yang lambat, rentan memory leak, dan rawan eksploitasi keamanan.

Pahami browser modern (seperti Chromium atau Gecko) sebagai sebuah **jaringan pabrik manufaktur multi-proses terdistribusi**:

```
+-----------------------------------------------------------------------+
|                            BROWSER PROCESS                            |
|             (Kantor Pusat / CEO: UI Chrome, Tab, Storage, I/O)        |
+-----------------------------------------------------------------------+
          | (IPC - Mojo)                   | (IPC - Mojo)
          v                                v
+----------------------+        +---------------------------------------+
|   NETWORK SERVICE    |        |           RENDERER PROCESS            |
| (Logistik Ekspedisi: |        |      (Pabrik Perakitan / Sandbox)     |
| DNS, TLS, HTTP/2/3)  |        |  Main Thread: JS, DOM, Style, Layout  |
+----------------------+        |  Compositor Thread: Layer Tiling      |
                                +---------------------------------------+
                                                   | (IPC / Shared Memory)
                                                   v
                                        +--------------------+
                                        |    GPU PROCESS     |
                                        | (Mesin Cetak Akhir)|
                                        +--------------------+
```

1. **Browser Process (Kantor Pusat)**: Mengatur antarmuka pengguna luar (address bar, bookmark, tombol back), mengatur lifecycle proses anak, dan mengelola hak akses sistem operasi (file system, hardware).
2. **Network Service (Departemen Logistik)**: Mengambil raw byte stream dari jaringan melalui protokol TCP/UDP, TLS, HTTP/2, dan HTTP/3. Tidak memedulikan arti visual dari byte tersebut.
3. **Renderer Process (Pabrik Perakitan Terisolasi / Sandbox)**: Satu instance per tab/situs (Site Isolation). Di sinilah V8 (JavaScript Engine) dan Blink/WebCore (Layout Engine) berjalan. Jika kode JavaScript crash, tab lain tetap beroperasi karena sandbox tidak memiliki akses langsung ke OS.
4. **GPU Process (Mesin Cetak & Rasterisasi)**: Menerima *display list* dan *compositor layers* dari Renderer Process, mengubahnya menjadi piksel mentah (*rasterization*) menggunakan instruksi OpenGL/Vulkan/DirectX untuk ditampilkan langsung pada frame buffer layar.

### Aturan Emas Eksekusi
*Main Thread adalah jalur sempit satu arah*. Main Thread pada Renderer Process bertanggung jawab mengeksekusi JavaScript, mem-parse HTML, merekayasa CSSOM, menjalankan Style Calculation, serta menghitung Layout dan Paint. Setiap milidetik JavaScript Anda memblokir Main Thread, Anda membekukan pipeline rendering, yang berujung pada hilangnya frame visual (jank/stutter).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah diagram komprehensif dari navigasi URL hingga output visual di monitor (End-to-End Navigation & Rendering Engine Lifecycle):

```
+---------------------------------------------------------------------------------------------------------------------+
| FASE 1: JARINGAN & PROTOKOL (Browser Process -> Network Service)                                                    |
+---------------------------------------------------------------------------------------------------------------------+
  [User Input URL] 
         │
         ▼
  [DNS Resolution] ────► [TCP 3-Way Handshake] ────► [TLS 1.3 Cryptographic Handshake]
  (DoH / Cache)          (SYN -> SYN-ACK -> ACK)     (ClientHello -> ServerHello + Keys)
                                                                 │
                                                                 ▼
  [HTTP/2 Multiplexing / HTTP/3 QUIC Engine] ◄───────────────────┘
  (Stream ID, Frame Header, HPACK/QPACK Compression)
         │
         ▼ (HTTP Response 200 OK + Payload Payload Bytes)
  [MIME Type Sniffing & SafeBrowsing Check]
         │
         ▼ (Commit Navigation via IPC Mojo)
+---------------------------------------------------------------------------------------------------------------------+
| FASE 2: CRITICAL RENDERING PATH PIPELINE (Renderer Process - Main Thread)                                           |
+---------------------------------------------------------------------------------------------------------------------+
  [Raw Bytes: HTML] 
         │
         ▼
  [Bytes to Characters] ──► [Tokenizer] ──► [Node Construction] ──► [DOM Tree]
                                                                        │
  [Raw Bytes: CSS]                                                      │
         │                                                              │
         ▼                                                              │
  [CSS Tokenizer] ──────► [CSS Rules Parser] ──────► [CSSOM Tree]       │
                                                           │            │
                                                           ▼            ▼
                                                 [Style Calculation (Attachment)]
                                                 (Computed Styles resolved)
                                                           │
                                                           ▼
                                                   [Render Tree Engine]
                                           (Only Visible Nodes: Display != none)
                                                           │
                                                           ▼
                                                    [Layout / Reflow]
                                        (Geometry: x, y, width, height calculations)
                                                           │
                                                           ▼
                                                   [Paint Invalidation]
                                            (Display List creation: Draw calls)
                                                           │
+---------------------------------------------------------------------------------------------------------------------+
| FASE 3: COMPOSITING & RASTER ENGINE (Compositor Thread & GPU Process)                                               |
+---------------------------------------------------------------------------------------------------------------------+
                                                           │ (Commit Layer Tree)
                                                           ▼
                                               [Compositor Thread (Renderer)]
                                          (Split into Layers, Divide into Tiles)
                                                           │
                                                           ▼ (IPC / Shared Bitmap)
                                                  [GPU Process (Raster)]
                                         (Rasterize Tiles via Skia/Ganesh/Graphite)
                                                           │
                                                           ▼
                                                [Draw Quad Generation]
                                                           │
                                                           ▼
                                                [DirectX/Vulkan/Metal] ──► [Frame Buffer Screen]
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. IPC (Inter-Process Communication) & Chromium Mojo
Renderer Process berjalan di dalam OS sandbox yang sangat ketat (tidak bisa membaca disk langsung, tidak bisa membuka network socket). Ketika JavaScript mengeksekusi `fetch('https://api.domain.com')`:
1. V8 mengeksekusi binding C++ internal browser.
2. Renderer Process mengirim pesan serialize melalui **Mojo IPC message pipe** ke Browser Process.
3. Browser Process meneruskan request ke Network Service.
4. Network Service membuka socket TCP/UDP, mengambil data, lalu menulis raw buffer ke **Shared Memory Ring Buffer**.
5. Handle shared memory dikirimkan kembali ke Renderer Process via IPC untuk dibaca langsung oleh V8 tanpa overhead serialisasi ganda.

### 2. Network Stack: HTTP/1.1 vs HTTP/2 vs HTTP/3
* **HTTP/1.1**: Bergantung pada multiple persistent TCP connection per domain (maksimal 6 koneksi paralel di browser engine). Menderita **Head-of-Line (HoL) Blocking** pada level HTTP: jika request pertama lambat, request kedua pada socket yang sama terhambat.
* **HTTP/2**: Menggunakan 1 koneksi TCP dengan multiplexing. Frame data diberi label `Stream Identifier` (4 byte). Beberapa stream request/response dapat berjalan serentak pada satu pipa TCP. Namun, HTTP/2 masih menderita **HoL Blocking pada transport layer**: jika 1 paket TCP hilang (*packet loss*), seluruh koneksi TCP terhenti menunggu transmisi ulang ACK-packet dari kernel OS.
* **HTTP/3**: Mengganti TCP dengan **QUIC** (Quick UDP Internet Connections) yang berjalan di atas protokol UDP. QUIC mengimplementasikan mekanisme error-recovery, congestion control, dan TLS 1.3 langsung di user-space per-stream. Kehilangan paket pada Stream A tidak menghentikan transmisi pada Stream B.

### 3. Parsing Phase: Speculative Pre-parser & Tokenization
HTML parsing menggunakan algoritma berstandar WHATWG yang memproses input stream secara *incremental* (tidak menunggu 100% file HTML selesai diunduh):
1. **Tokenization**: State machine yang memetakan karakter `Character Tokens` menjadi `StartTag`, `EndTag`, `Comment`, atau `Character`.
2. **Tree Construction**: Membangun relasi induk-anak (parent-child pointer).
3. **Speculative Parsing (Preload Scanner)**: Di saat Main Thread terblokir oleh `<script src="...">` eksternal yang sedang dieksekusi atau diunduh, thread terpisah membaca sisa HTML untuk menemukan tag resource eksternal lain (`<img>`, `<link rel="stylesheet">`, `<script>`) dan langsung meluncurkan download request secara spekulatif ke Network Service.

### 4. Style, Layout, Paint, dan Compositor
* **Style Calculation**: Menggabungkan CSS dari user agent, stylesheet eksternal, inline style, dan CSS variables, lalu menerapkan aturan *Cascade & Specificity* untuk menghasilkan representasi computed properties per elemen DOM.
* **Layout (Reflow)**: Menghitung struktur geometri: dimensi eksak (`width`, `height`) dan koordinat absolut (`x`, `y`, `z`) elemen di viewport. Menghasilkan struktur internal yang disebut **Layout Tree** (atau Render Object Tree).
* **Paint**: Menerjemahkan Layout Tree menjadi serangkaian instruksi penggambaran visual (*Display List*). Contoh instruksi: `drawRect`, `drawText`, `clipPath`.
* **Compositing**: Mengelompokkan elemen-elemen ke dalam *Composited Layers*. Layer ini diserahkan kepada **Compositor Thread**, yang memotong layer menjadi petak-petak (*tiles*), lalu mengirimkannya ke **GPU Process** untuk di-*rasterize* (mengubah vektor grafis menjadi bitmap piksel).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Critical Rendering Path & Frame Budget
Layar modern beroperasi pada refresh rate 60 Hz (standar) atau 120 Hz (high-refresh display). 
* Pada 60 Hz, peramban memiliki jendela waktu **16.66 milidetik** per frame.
* Pada 120 Hz, peramban hanya memiliki **8.33 milidetik** per frame.

Di dalam jendela waktu tersebut, browser harus menyelesaikan seluruh lifecycle:
$$\text{Frame Budget} = T_{\text{JS}} + T_{\text{Style}} + T_{\text{Layout}} + T_{\text{Paint}} + T_{\text{Composite}}$$

Jika durasi total melampaui $16.66\text{ ms}$, terjadi **Dropped Frame (Jank)**.

### Forced Synchronous Layout & Layout Thrashing
Secara default, browser engine melakukan optimasi penundaan Layout: modifikasi DOM dikumpulkan dan di-flush di akhir giliran task sebelum painting dilakukan. 

**Forced Synchronous Layout (FSL)** terjadi ketika JavaScript menulis perubahan ke DOM, lalu pada baris berikutnya langsung meminta pembacaan metrik geometri DOM. Ini memaksa Layout Engine menghitung ulang geometri secara instan di tengah eksekusi kode JS.

**Layout Thrashing** terjadi ketika proses FSL ini diulang terus-menerus di dalam sebuah loop:

```
[Loop Iterasi 1]
  JS Write (el.style.width = ...)   ──► Menandai layout "DIRTY"
  JS Read  (el.offsetWidth)         ──► FORCE ENGINE MEMULAI REFLOW LENGKAP
[Loop Iterasi 2]
  JS Write (el.style.width = ...)   ──► Menandai layout "DIRTY"
  JS Read  (el.offsetWidth)         ──► FORCE ENGINE MEMULAI REFLOW LENGKAP KEMBALI
... (Dijalankan ratusan kali = Main Thread Hang)
```

### Fast Path vs Slow Path Rendering
Ketika sebuah style dimodifikasi via JavaScript atau CSS Animations, dampaknya berbeda drastis pada tahapan pipeline:

| Property Dimodifikasi | Layout (Reflow)? | Paint? | Composite? | Jalur Eksekusi |
| :--- | :--- | :--- | :--- | :--- |
| `width`, `height`, `margin`, `top`, `fontSize` | **YA** | **YA** | **YA** | *Slow Path* (Seluruh Pipeline Diulang) |
| `background-color`, `color`, `box-shadow` | **TIDAK** | **YA** | **YA** | *Medium Path* (Layout di-skip) |
| `transform`, `opacity`, `filter` | **TIDAK** | **TIDAK** | **YA** | *Fast Path* (Compositor Thread Only) |

Modifikasi `transform` dan `opacity` tidak memerlukan intervensi Main Thread untuk menghitung ulang koordinat atau menggambar ulang display list. GPU memproses modifikasi ini langsung di Compositor Thread secara hardware accelerated.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode fungsional murni yang mendemonstrasikan secara presisi perbedaan antara **Layout Thrashing (Pola Buruk)** dan **Batched Layout with Compositor Animation (Pola Optimal)**, dilengkapi pencatatan metrik performa via High-Resolution Timer (`performance.now()`).

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Layout Thrashing Benchmark</title>
  <style>
    .box {
      position: absolute;
      width: 20px;
      height: 20px;
      background-color: #e11d48;
      border-radius: 4px;
      /* Memaksa elemen memiliki layer composited independen */
      will-change: transform;
    }
    #container {
      position: relative;
      width: 100vw;
      height: 80vh;
      overflow: hidden;
      border-bottom: 2px solid #334155;
    }
  </style>
</head>
<body>
  <div id="container"></div>
  <button id="btn-thrash">Jalankan Layout Thrashing</button>
  <button id="btn-optimized">Jalankan Batched Pipeline</button>
  <div id="output">Status: Siaga</div>

  <script>
    const container = document.getElementById('container');
    const output = document.getElementById('output');
    const TOTAL_ELEMENTS = 1500;

    // Inisialisasi elemen visual
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < TOTAL_ELEMENTS; i++) {
      const el = document.createElement('div');
      el.className = 'box';
      el.style.top = `${(i % 30) * 25}px`;
      el.style.left = `${Math.floor(i / 30) * 25}px`;
      fragment.appendChild(el);
    }
    container.appendChild(fragment);

    const elements = Array.from(document.querySelectorAll('.box'));

    // 1. POLA ANTI-PATTERN: Layout Thrashing (Read/Write bergantian)
    document.getElementById('btn-thrash').addEventListener('click', () => {
      const startTime = performance.now();

      for (let i = 0; i < elements.length; i++) {
        // READ GEOMETRI (Memaksa Reflow Instan karena state dirty)
        const currentLeft = elements[i].offsetLeft;
        
        // WRITE STATE (Menandai DOM tree sebagai dirty)
        elements[i].style.left = `${(currentLeft + 10) % 800}px`;
      }

      const duration = performance.now() - startTime;
      output.innerText = `Layout Thrashing selesai: ${duration.toFixed(2)} ms (Main Thread Terblokir)`;
    });

    // 2. POLA OPTIMAL: Separate Read & Write Phase + Fast Path Compositing
    document.getElementById('btn-optimized').addEventListener('click', () => {
      const startTime = performance.now();

      // FASE 1: BATCH READ (Mengumpulkan data tanpa modifikasi DOM)
      const currentPositions = new Float64Array(elements.length);
      for (let i = 0; i < elements.length; i++) {
        currentPositions[i] = elements[i].offsetLeft;
      }

      // FASE 2: BATCH WRITE menggunakan Transform (Compositor Thread Delegated)
      requestAnimationFrame(() => {
        for (let i = 0; i < elements.length; i++) {
          const nextPos = (currentPositions[i] + 10) % 800;
          // Transform mengabaikan Layout dan Paint, langsung dikirim ke Compositing
          elements[i].style.transform = `translate3d(${nextPos}px, 0, 0)`;
        }
        const duration = performance.now() - startTime;
        output.innerText = `Optimized Execution selesai: ${duration.toFixed(2)} ms (Zero Reflow Block)`;
      });
    });
  </script>
</body>
</html>
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Tombol `#btn-thrash` (Pola Buruk):
1. **Baris 48**: `const currentLeft = elements[i].offsetLeft;`
   Engine browser mendeteksi bahwa ada perintah baca properti geometri (`offsetLeft`). Karena pada iterasi sebelumnya terjadi penulisan style, struktur geometri pohon DOM saat ini berstatus invalid ("dirty"). Engine dipaksa berhenti (*block*), memanggil modul C++ layout internal, dan menghitung ulang seluruh geometri window saat itu juga.
2. **Baris 51**: `elements[i].style.left = ...;`
   Main thread mengubah atribut style layout. Browser menandai Layout Tree sebagai *dirty*.
3. **Konsekuensi Loop (1500 Iterasi)**:
   Terjadi 1.500 kali eksekusi algoritma Reflow secara berulang dalam satu synchronous call. Durasi melonjak dari ratusan mikrodetik menjadi **50–150 milidetik**, menyebabkan freeze total pada UI, freezing animasi lain, dan menunda event handler pengguna.

### Analisis Tombol `#btn-optimized` (Pola Optimal):
1. **Baris 62**: `const currentPositions = new Float64Array(elements.length);`
   Mengalokasikan typed array biner berkinerja tinggi untuk meminimalkan alokasi memori garbage-collected pada JavaScript Heap.
2. **Baris 63–65 (Fase Batch Read)**:
   Seluruh loop pertama hanya menjalankan instruksi `read`. Engine browser hanya melakukan **satu kali Reflow** untuk mengembalikan semua nilai `offsetLeft`.
3. **Baris 68**: `requestAnimationFrame(() => { ... })`
   Menginstruksikan JavaScript Runtime untuk menunda modifikasi style hingga tepat sebelum frame visual berikutnya digambar oleh peramban, menyinkronkan eksekusi dengan V-Sync hardware monitor.
4. **Baris 71**: `elements[i].style.transform = 'translate3d(...)';`
   Menggunakan properti `transform` alih-alih `left`. Properti `transform` tidak mempengaruhi tata letak elemen di sekitarnya. Engine sepenuhnya melewati tahap Layout dan Paint. Instruksi langsung dialihkan ke Compositor Thread untuk dimanipulasi oleh chip GPU melalui shared memory. Durasi runtime turun drastis ke kisaran **< 2 milidetik**.

---

# SEKSI 09 — STUDI KASUS NYATA

### Konteks Skenario
Sebuah platform analitik finansial real-time (**ApexTrade Global**) mengalami degradasi performa akut pada dasbor trading mereka. Platform ini menampilkan feed transaksi order book secara live dengan frekuensi update 50–100 tick per detik melalui WebSocket.

### Masalah yang Ditemukan di Lapangan
1. **Critical Jank**: Nilai frame rate anjlok hingga 10–14 FPS. Pengguna melaporkan bahwa saat feed data ramai, antarmuka tidak merespons klik (Interaction to Next Paint / INP melonjak hingga **850ms**).
2. **Network Protocol Serialization Waterfall**: Klien menggunakan pooling HTTP/1.1 yang mengeksekusi puluhan request aset grafik terpisah secara serial karena keterbatasan 6 koneksi browser per domain.
3. **CPU Pegging**: Pemakaian satu core CPU mencapai 100% secara persisten pada Renderer Process Main Thread.

### Akar Masalah (Root Cause Analysis)
* Pada setiap tick WebSocket, modul UI secara naif memanggil `document.getElementById(...)`, membuat node `<div>` baru, menghitung tinggi kontainer dengan `element.scrollHeight`, lalu mengubah `container.scrollTop`.
* Pembacaan `scrollHeight` tepat setelah menyisipkan elemen menyebabkan **Forced Synchronous Layout** beruntun 100 kali per detik.
* Pemuatan data historis grafik menggunakan REST endpoint terfragmentasi yang memicu TCP slow-start berulang di HTTP/1.1.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah solusi arsitektural berskala produksi: membangun **High-Throughput Virtualized Stream Renderer** menggunakan `ReadableStream`, `OffscreenCanvas`/Direct Compositing, dan `requestAnimationFrame` Batching Queue untuk memproses ribuan data tanpa memblokir Main Thread.

```javascript
/**
 * Production-Grade High-Throughput Stream Pipeline
 * Menggabungkan Network Streaming Engine, Mutex Rendering Queue,
 * dan Compositor-Optimized Virtual DOM update.
 */

class HighFrequencyTradingDashboard {
  constructor(containerElement) {
    this.container = containerElement;
    this.renderQueue = [];
    this.isFrameScheduled = false;
    this.maxBufferedItems = 500;
    
    // Inisialisasi High Performance Observer
    this.initObserver();
  }

  initObserver() {
    // Memantau layout shift secara programmatic via Layout Instability API
    if ('PerformanceObserver' in window) {
      const clsObserver = new PerformanceObserver((entryList) => {
        for (const entry of entryList.getEntries()) {
          if (!entry.hadRecentInput) {
            console.warn(`[PERF ALERT] Unwanted Layout Shift detected: ${entry.value}`);
          }
        }
      });
      clsObserver.observe({ type: 'layout-shift', buffered: true });
    }
  }

  /**
   * Menghubungkan ke back-end menggunakan HTTP/2 atau HTTP/3 Byte Stream
   * Menggunakan Fetch Streams API alih-alih parsing JSON massal di memori
   */
  async connectOrderStream(streamUrl) {
    try {
      const response = await fetch(streamUrl);
      if (!response.body) throw new Error('ReadableStream tidak didukung');

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let partialBuffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        // Streaming chunk processing: parsing token tanpa menunggu request selesai
        partialBuffer += decoder.decode(value, { stream: true });
        const lines = partialBuffer.split('\n');
        
        // Simpan token yang belum selesai di buffer
        partialBuffer = lines.pop();

        for (const line of lines) {
          if (line.trim()) {
            const transaction = JSON.parse(line);
            this.pushTransactionToQueue(transaction);
          }
        }
      }
    } catch (err) {
      console.error('[NETWORK CRITICAL] Stream disconnected:', err);
    }
  }

  /**
   * Push data ke Antrean Thread-Safe (In-Memory Ring Buffer)
   */
  pushTransactionToQueue(transaction) {
    this.renderQueue.push(transaction);

    // Mencegah Memory Bloat jika background tab tidak merender
    if (this.renderQueue.length > this.maxBufferedItems) {
      this.renderQueue.splice(0, this.renderQueue.length - this.maxBufferedItems);
    }

    // Jadwalkan rendering batch jika belum ada frame yang aktif
    if (!this.isFrameScheduled) {
      this.isFrameScheduled = true;
      requestAnimationFrame(this.flushQueueToPipeline.bind(this));
    }
  }

  /**
   * FLUSH PIPELINE: Memproses data tepat sebelum V-Sync.
   * Tidak ada percampuran Read/Write geometri di Main Thread.
   */
  flushQueueToPipeline() {
    this.isFrameScheduled = false;

    if (this.renderQueue.length === 0) return;

    // Ambil seluruh snapshot data saat ini dan bersihkan antrean
    const itemsToRender = [...this.renderQueue];
    this.renderQueue = [];

    // FASE MENULIS MURNI (Batch Write DOM via DocumentFragment)
    const fragment = document.createDocumentFragment();

    for (let i = 0; i < itemsToRender.length; i++) {
      const item = itemsToRender[i];
      const row = document.createElement('div');
      
      // Menggunakan inline styling berbasis GPU Compositor primitives
      row.className = 'trade-row';
      row.style.cssText = `
        contain: strict;
        will-change: transform;
        height: 24px;
        color: ${item.side === 'BUY' ? '#10b981' : '#ef4444'};
      `;
      row.textContent = `[${item.timestamp}] ${item.symbol} | Vol: ${item.volume} @ ${item.price}`;
      fragment.appendChild(row);
    }

    // Mutasi DOM Tunggal: Layout Engine hanya mengevaluasi fragment sekali
    this.container.appendChild(fragment);

    // Pangkas node lama di luar viewport untuk menjaga ukuran DOM Tree tetap konstan
    const totalChildren = this.container.children.length;
    if (totalChildren > this.maxBufferedItems) {
      const deleteCount = totalChildren - this.maxBufferedItems;
      for (let i = 0; i < deleteCount; i++) {
        this.container.removeChild(this.container.firstElementChild);
      }
    }
  }
}

// Inisialisasi pada container
const dashboard = new HighFrequencyTradingDashboard(document.getElementById('ticker-mount'));
// Simulasi stream masuk
// dashboard.connectOrderStream('https://api.apextrade.internal/v3/feed/stream');
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Arsitektur Jaringan (Transport Layer)

| Parameter | HTTP/1.1 | HTTP/2 | HTTP/3 (QUIC) |
| :--- | :--- | :--- | :--- |
| **Transport Protocol** | TCP murni | TCP murni | UDP murni |
| **Multiplexing** | Tidak ada (Perlu multi-socket) | Ya (Stream multiplexing) | Ya (True Independent Stream) |
| **Head-of-Line Blocking** | Di Application Layer | Di TCP Transport Layer | Teratasi Sepenuhnya |
| **Handshake Latency** | 2-3 RTT (TCP + TLS) | 2-3 RTT (TCP + ALPN + TLS) | 0-1 RTT (Combined Crypto & Transport) |
| **Connection Migration** | Putus saat ganti IP (Wi-Fi ke Seluler) | Putus saat ganti IP | Aman (Berdasarkan Connection ID 64-bit) |
| **CPU Overhead** | Rendah | Sedang (Framing HPACK) | Tinggi (Enkripsi/Dekripsi UDP di User Space) |

### Mekanisme Manipulasi Grafis di Browser

| Pendekatan | Beban Main Thread | Beban GPU Memory (VRAM) | Efisiensi Animasi | Skalabilitas Node |
| :--- | :--- | :--- | :--- | :--- |
| **Direct DOM Manipulation (`left`, `top`)** | Sangat Tinggi (Reflow loop) | Sangat Rendah | Sangat Buruk (Jank) | Buruk (< 1.000 elemen) |
| **Composited DOM (`transform: translate3d`)** | Rendah | Tinggi (Layer Allocation) | Optimal (60/120 FPS Stabil) | Sedang (Hingga 5.000 elemen) |
| **OffscreenCanvas (Web Worker Driven)** | Nol (Off-thread execution) | Sangat Tinggi | Maksimal (Hardware blit) | Sangat Tinggi (> 50.000 elemen) |

---

# SEKSI 12 — EDGE CASES & PITFALLS

1. **Compositor Layer Explosion**:
   Menggunakan `will-change: transform` atau `translateZ(0)` secara serampangan pada ribuan elemen akan memaksa browser engine mengalokasikan tekstur GPU (backing store) independen untuk setiap elemen. Hal ini menyebabkan crash mendadak pada peramban mobile akibat **OOM (Out Of Memory) Killer** pada kartu grafis/VRAM.
2. **Back-Forward Cache (bfcache) Breakage**:
   Navigasi instan saat tombol *Back* ditekan dapat gagal total jika halaman Anda memiliki koneksi terbuka yang tidak tertutup dengan benar pada event `pagehide`, atau jika script memuat listener `unload`. Browser terpaksa membuang seluruh snapshot memori dari Renderer Process dan mengulang network navigation dari awal.
3. **Font Swapping FOUT/FOIT Reflow Cascades**:
   Memuat custom web font tanpa properti `font-display: optional` atau `swap` yang terukur dapat memicu *Flash of Invisible Text* (FOIT). Ketika font selesai diunduh beberapa detik kemudian, browser membatalkan seluruh Layout Tree teks dan menghitung ulang posisi setiap paragraf di viewport, merusak metrik Cumulative Layout Shift (CLS).
4. **Detached DOM Tree Memory Leaks**:
   Jika elemen DOM dihapus dari document body (`element.remove()`), namun referensinya masih disimpan di dalam closure JavaScript atau global array, memori C++ wrapper (`Native DOM`) tidak dapat di-garbage collect oleh V8 engine, menahan node sub-tree di heap selamanya.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Membaca Layout Metrics di Dalam Loop Pengubahan Ukuran
*Anti-Pattern:*
```javascript
// BAD: Menyebabkan Forced Synchronous Layout berulang
function resizeAllCards(cards) {
  for (let i = 0; i < cards.length; i++) {
    const card = cards[i];
    // Membaca offsetHeight memaksa browser melakukan reflow instan
    if (card.offsetHeight > 200) {
      card.style.height = '200px';
    }
  }
}
```
*Solusi (Fast DOM Read-Write Pattern):*
```javascript
// GOOD: Pisahkan fase pengukuran dengan fase modifikasi
function resizeAllCards(cards) {
  // 1. Read Phase
  const oversizedIndices = [];
  for (let i = 0; i < cards.length; i++) {
    if (cards[i].offsetHeight > 200) {
      oversizedIndices.push(i);
    }
  }
  // 2. Write Phase
  requestAnimationFrame(() => {
    for (const index of oversizedIndices) {
      cards[index].style.height = '200px';
    }
  });
}
```

### 2. Memblokir Preload Scanner dengan CSS Import `@import`
*Anti-Pattern:*
```css
/* BAD: Di dalam styles.css */
@import url('theme.css'); /* Mematikan speculative parallel download */
```
*Solusi:*
Gunakan tag `<link rel="stylesheet">` langsung di dalam HTML `<head>`. Engine browser preload scanner dapat melihatnya sejak byte pertama tiba dari Network Service dan mengunduhnya secara paralel.

### 3. Menggunakan Scroll Listener Tanpa Passive Flag
*Anti-Pattern:*
```javascript
// BAD: Browser harus menunggu JS mengeksekusi event handler untuk melihat
// apakah event.preventDefault() dipanggil sebelum melakukan scrolling.
window.addEventListener('scroll', handleScroll);
```
*Solusi:*
```javascript
// GOOD: Memberi tahu Compositor Thread bahwa JS tidak akan membatalkan event scroll,
// scroll dapat langsung diproses dengan lancar oleh GPU.
window.addEventListener('scroll', handleScroll, { passive: true });
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **CSS Containment (`contain`)**:
   Gunakan CSS property `contain: content;` atau `contain: layout style;` pada komponen-komponen yang berdiri sendiri (seperti widgets, modal, order book rows). Ini mengisolasi sub-tree DOM tersebut dari sisa halaman. Ketika elemen di dalamnya berubah, browser hanya menghitung ulang geometri sub-tree tersebut tanpa memicu Reflow pada elemen induk atau saudara (*sibling*).
2. **Resource Hints Precedence Architecture**:
   Petakan hierarki pemuatan resource dengan presisi di `<head>`:
   * `rel="preconnect"`: Menginisialisasi DNS + TCP + TLS handshake lebih awal untuk domain API pihak ketiga yang kritikal.
   * `rel="preload"`: Memberi tahu Preload Scanner untuk mengambil file biner prioritas tinggi yang tersembunyi di dalam CSS/JS (misalnya font critical WOFF2).
3. **Sub-pixel Anti-Aliasing Isolation**:
   Gunakan properti CSS `content-visibility: auto;` untuk elemen yang berada di luar batas viewport awal (*off-screen*). Browser akan melewatkan tahap Layout dan Paint secara total untuk elemen-elemen tersebut hingga user mendekati area scroll yang bersangkutan.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Core Web Vitals Pipeline Alignment
* **Largest Contentful Paint (LCP)**:
  * Eliminasi network waterfall: Render LCP image tanpa lazy loading (`loading="eager"` dan `fetchpriority="high"`).
  * Pastikan byte delivery melalui HTTP/2 multiplexing atau CDN berprotokol HTTP/3 untuk mengurangi Time to First Byte (TTFB).
* **Interaction to Next Paint (INP)**:
  * Pecah synchronous tasks panjang (> 50ms) menggunakan Scheduler API modern: `scheduler.yield()` atau `setTimeout(..., 0)`. Hal ini mengembalikan kendali ke Main Thread untuk memproses input pengguna dan rendering frame.
* **Cumulative Layout Shift (CLS)**:
  * Selalu tetapkan atribut rasio aspek eksplisit pada elemen gambar atau kontainer iklan (`aspect-ratio: 16 / 9;` atau `width` & `height` eksplisit). Browser akan mencadangkan ruang geometris pada Layout Tree sebelum aset biner gambar tiba dari jaringan.

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Site Isolation & Out-of-Process iframes (OOPIF)
Chromium memisahkan dokumen berbeda domain ke dalam Renderer Process yang sepenuhnya berbeda. Tujuannya adalah mencegah eksploitasi mikroarsitektur seperti **Spectre**, di mana kode JavaScript penyerang membaca memori byte yang bukan miliknya melalui *speculative execution branch target buffer*.

### 2. Keamanan Tingkat Lanjut: COOP dan COEP
Untuk mengaktifkan fitur browser tingkat lanjut seperti `SharedArrayBuffer` dan `performance.measureUserAgentSpecificMemory()`, halaman wajib berada dalam status **Cross-Origin Isolated**. Konfigurasi HTTP Response Headers berikut harus dikirim oleh server web:

```http
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
Cross-Origin-Resource-Policy: same-origin
```

* **COOP (`same-origin`)**: Mengisolasi browsing context group tab Anda dari tab lain, mencegah manipulasi objek `window.opener`.
* **COEP (`require-corp`)**: Memblokir resource eksternal cross-origin yang tidak secara eksplisit memberikan izin pemuatan via Cross-Origin Resource Policy (CORP) atau CORS.

### 3. Content Security Policy (CSP) Level 3
Lindungi pipeline parsing peramban dari injeksi skrip tak terpercaya:
```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-EDN4f89xzQ'; object-src 'none'; base-uri 'none'; require-trusted-types-for 'script';
```
Penggunaan `require-trusted-types-for 'script'` menghentikan DOM XSS di tingkat V8 engine dengan menolak eksekusi manipulasi teks mentah pada injection sinks seperti `element.innerHTML` tanpa sanitasi berbasis Typed Objects.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Berikut skrip observabilitas industri berbasis **PerformanceObserver API** untuk menangkap eksekusi Long Tasks yang memblokir Main Thread, melacak layout instability, serta mencatat network latency metrik langsung dari dalam aplikasi web:

```javascript
/**
 * Advanced Browser Pipeline Telemetry Observer
 * Memantau Long Animation Frames, Frame Drops, dan Resource Metrics
 */
class PerformanceTelemetryEngine {
  constructor() {
    this.initLongTaskObserver();
    this.initLayoutShiftObserver();
    this.initNavigationObserver();
  }

  // 1. Deteksi Long Tasks yang memblokir Main Thread (> 50ms)
  initLongTaskObserver() {
    if (!PerformanceObserver.supportedEntryTypes.includes('longtask')) {
      console.warn('Telemetry: Long Tasks API tidak didukung');
      return;
    }

    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        console.error('[PERF REGRESSION: Long Task Detected]', {
          durationMs: entry.duration.toFixed(2),
          startTime: entry.startTime.toFixed(2),
          attribution: JSON.stringify(entry.attribution)
        });
      }
    });

    observer.observe({ entryTypes: ['longtask'] });
  }

  // 2. Deteksi Cumulative Layout Shift secara Programmatic
  initLayoutShiftObserver() {
    if (!PerformanceObserver.supportedEntryTypes.includes('layout-shift')) return;

    let totalClsScore = 0;
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) {
          totalClsScore += entry.value;
          console.warn(`[CLS UPDATE] Score: ${totalClsScore.toFixed(4)}`, {
            shiftedElements: entry.sources
          });
        }
      }
    });

    observer.observe({ type: 'layout-shift', buffered: true });
  }

  // 3. Ekstraksi Metrik Jaringan Transmisi Data
  initNavigationObserver() {
    window.addEventListener('load', () => {
      const [navTiming] = performance.getEntriesByType('navigation');
      if (!navTiming) return;

      const networkMetrics = {
        dnsLookupTime: navTiming.domainLookupEnd - navTiming.domainLookupStart,
        tcpHandshakeTime: navTiming.connectEnd - navTiming.connectStart,
        tlsNegotiationTime: navTiming.requestStart - navTiming.secureConnectionStart,
        ttfb: navTiming.responseStart - navTiming.requestStart,
        downloadTime: navTiming.responseEnd - navTiming.responseStart,
        domProcessingTime: navTiming.domComplete - navTiming.domInteractive
      };

      console.table(networkMetrics);
    });
  }
}

// Inisialisasi telemetry
const telemetry = new PerformanceTelemetryEngine();
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### Alur Singkat Critical Rendering Path
$$\text{Raw Bytes} \longrightarrow \text{Tokens} \longrightarrow \text{Nodes (DOM/CSSOM)} \longrightarrow \text{Render Tree} \longrightarrow \text{Layout} \longrightarrow \text{Paint} \longrightarrow \text{Composite}$$

### Properti CSS Pemicu Pipeline

| Kategori Modifikasi | Properti CSS Tipikal | Dampak Pipeline |
| :--- | :--- | :--- |
| **Geometry Changes** | `width`, `height`, `padding`, `margin`, `left`, `top`, `display`, `border-width` | **Reflow $\rightarrow$ Repaint $\rightarrow$ Recomposite** |
| **Visual Changes Only** | `color`, `background-color`, `box-shadow`, `visibility`, `outline` | **Repaint $\rightarrow$ Recomposite** |
| **Composited Only** | `transform`, `opacity`, `filter`, `backdrop-filter` | **Recomposite Only (GPU Direct)** |

### Perintah Cepat Chrome DevTools
* Buka **Rendering Drawer**: `Cmd + Shift + P` (Mac) atau `Ctrl + Shift + P` (Win) $\rightarrow$ Ketik *"Show Rendering"*.
  * Aktifkan **Paint Flashing**: Melacak area layar yang sedang digambar ulang (warna hijau).
  * Aktifkan **Layout Shift Regions**: Melacak elemen yang meloncat posisi saat proses parsing (warna biru).
  * Aktifkan **Layer Borders**: Menampilkan garis batas Compositor Layers dan GPU Tiling (oranye/biru).

---

# SEKSI 019 — KUIS EVALUASI PEMAHAMAN

### Soal Pilihan Ganda (Tingkat Dasar)

1. **Mengapa peramban modern seperti Chromium memisahkan Renderer Process ke dalam sandbox terpisah dari Browser Process?**
   * A. Untuk menghemat alokasi memori RAM.
   * B. Untuk keamanan, mencegah eksploitasi kode web berbahaya mengakses filesystem atau kernel OS secara langsung.
   * C. Karena JavaScript engine V8 tidak mendukung multi-threading.
   * D. Agar browser dapat membuka tab dalam jumlah tak terbatas.

2. **Properti CSS manakah yang TIDAK memicu tahapan Layout maupun Paint saat nilainya dimanipulasi melalui animasi JavaScript?**
   * A. `left`
   * B. `background-color`
   * C. `transform`
   * D. `margin-top`

3. **Apa fungsi utama dari Speculative Preload Scanner pada HTML Parser?**
   * A. Menghapus kode CSS yang tidak terpakai secara otomatis.
   * B. Mengambil link resource eksternal dari HTML saat Main Thread sedang terblokir eksekusi JavaScript.
   * C. Mengompilasi JavaScript ke WebAssembly secara spekulatif.
   * D. Mengompres ukuran DOM Tree sebelum disimpan di memori.

4. **Kondisi apa yang secara presisi mendefinisikan Forced Synchronous Layout (FSL)?**
   * A. Ketika koneksi HTTP/2 multiplexing mengalami dropped packet.
   * B. Ketika CSSOM selesai dibentuk sebelum DOM Tree siap.
   * C. Ketika kode JavaScript memodifikasi style layout lalu langsung membaca properti geometri sebelum task selesai.
   * D. Ketika browser crash akibat Out of Memory (OOM).

5. **Apa keunggulan transport layer HTTP/3 (QUIC) dibandingkan HTTP/2?**
   * A. Menggunakan TCP port 80 tanpa enkripsi.
   * B. Menghilangkan Head-of-Line Blocking pada layer transport dengan berjalan di atas UDP.
   * C. Tidak memerlukan IP address untuk pengiriman data.
   * D. Mengizinkan transfer DOM nodes secara langsung dari server.

---

### Soal Pilihan Ganda (Tingkat Menengah)

6. **Diberikan urutan kode berikut:**
   ```javascript
   const w1 = elementA.offsetWidth;
   elementA.style.width = (w1 + 10) + 'px';
   const w2 = elementB.offsetWidth;
   elementB.style.width = (w2 + 10) + 'px';
   ```
   **Apa yang terjadi pada engine browser saat mengeksekusi baris ke-3 (`const w2 = ...`)?**
   * A. Engine mengembalikan nilai dari cache tanpa kalkulasi ulang.
   * B. Engine mengeksekusi asynchronous microtask queue.
   * C. Engine terpaksa melakukan synchronous reflow/layout kalkulasi ulang karena baris ke-2 membuat status geometri invalid.
   * D. Engine melemparkan error "Invalid DOM State".

7. **Fitur keamanan browser manakah yang wajib diaktifkan untuk mengizinkan pemanfaatan `SharedArrayBuffer` guna mencegah eksploitasi cache timing Spectre?**
   * A. Content Security Policy (CSP) dengan mode `unsafe-inline`.
   * B. Cross-Origin Opener Policy (COOP) dan Cross-Origin Embedder Policy (COEP).
   * C. Mengganti semua pemanggilan `fetch` dengan XMLHttpRequest.
   * D. Menonaktifkan Site Isolation pada setting peramban.

8. **Apa dampak performa dari penggunaan properti CSS `will-change: transform` pada 10.000 elemen secara bersamaan?**
   * A. Aplikasi menjadi 10.000 kali lebih cepat karena seluruh elemen di-cache di VRAM.
   * B. Compositor Layer Explosion, menghabiskan memori VRAM GPU dan berpotensi memicu browser tab crash.
   * C. Main thread layout time menjadi 0 milidetik secara permanen.
   * D. Mematikan fungsi rendering engine secara permanen.

9. **Bagaimana mekanisme `passive: true` pada event listener seperti `touchstart` meningkatkan performa scrolling?**
   * A. Mengompres data event touch menjadi binary.
   * B. Memberitahu Compositor Thread bahwa event handler tidak akan memanggil `preventDefault()`, sehingga rendering scroll dapat segera dieksekusi tanpa menunggu Main Thread selesai memproses JavaScript.
   * C. Menjalankan listener di dalam Web Worker terpisah.
   * D. Mengubah rendering engine menjadi WebGL secara otomatis.

10. **Apa perbedaan mendasar antara Render Tree dan DOM Tree?**
    * A. DOM Tree menyimpan representasi node XML/HTML lengkap, sedangkan Render Tree hanya mencakup node visual yang aktif (mengabaikan elemen seperti `<head>`, `<script>`, dan elemen dengan style `display: none`).
    * B. DOM Tree dihitung oleh GPU, sedangkan Render Tree dihitung oleh V8.
    * C. Render Tree dibuat sebelum HTML tokenization dimulai.
    * D. DOM Tree hanya menyimpan text content, sedangkan Render Tree menyimpan class name.

---

### Kunci Jawaban & Rasional Singkat

1. **B**: Sandbox isolasi mencegah kode berbahaya di renderer process mengeksekusi arbitrary system calls ke OS host.
2. **C**: Properti `transform` di-offload ke Compositor Thread dan diproses GPU langsung tanpa memicu Layout dan Paint.
3. **B**: Preload scanner bekerja secara non-blocking di latar belakang untuk menemukan dan me-request URL aset sementara parser utama menunggu script eksternal selesai.
4. **C**: FSL terjadi ketika JavaScript meminta metrik pembacaan geometri langsung setelah melakukan penulisan style DOM yang belum di-commit secara batch.
5. **B**: QUIC berjalan di atas UDP di mana setiap data stream independen; hilangnya paket pada satu stream tidak membekukan stream lainnya.
6. **C**: Baris kedua menandai geometri DOM sebagai "dirty". Baris ketiga memaksa browser membersihkan status "dirty" tersebut secara sinkron dengan menghitung ulang reflow seketika.
7. **B**: COOP (`same-origin`) dan COEP (`require-corp`) memastikan tab berada dalam lingkungan cross-origin isolated yang terlindungi dari side-channel timing attack.
8. **B**: Alokasi Composited Layer independen untuk elemen dalam jumlah masif menyebabkan kehabisan memori VRAM GPU (Layer Explosion).
9. **B**: Browser tidak perlu memblokir gerakan scroll untuk menunggu JavaScript mengevaluasi apakah scrolling akan dibatalkan via `preventDefault()`.
10. **A**: Elemen non-visual (`display: none`, metadata) tetap ada di dalam DOM Tree, namun dieliminasi dari Render Tree karena tidak menghasilkan representasi geometri visual pada layar.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Engine-Grade Real-Time Visual Flight Tracker"

### Spesifikasi Teknis Proyek:
Bangun sebuah dashboard pemantauan penerbangan radar real-time yang mampu me-render dan menganimasikan **5.000 objek pesawat secara simultan pada 60 frame per detik stabil (Frame Budget < 16.6ms)** tanpa mengalami Layout Thrashing.

### Kriteria Wajib:
1. **Network Layer**:
   * Implementasikan simulasi client-side stream generator menggunakan `ReadableStream` atau WebSocket client untuk mengalirkan 500 koordinat pesawat per detik secara continuous.
2. **Rendering Layer**:
   * Elemen pesawat dirender ke DOM. Anda dilarang keras memanipulasi properti `top`, `left`, `margin`, atau `width`/`height` untuk menggerakkan elemen.
   * Seluruh mutasi pergerakan posisi wajib memanfaatkan `transform: translate3d(x, y, 0)` untuk memastikan eksekusi murni di **Compositor Thread**.
3. **DOM Batching Architecture**:
   * Buat custom class `RenderBatcher` yang memisahkan pembacaan geometri (*Read Phase*) dan penulisan style (*Write Phase*) menggunakan antrean `requestAnimationFrame`.
4. **Performance Hardening**:
   * Terapkan `contain: strict;` pada wrapper item visual.
   * Pasang `PerformanceObserver` untuk mendeteksi:
     * Adanya Long Task (> 50ms).
     * Nilai Cumulative Layout Shift (CLS) wajib bernilai **0.000**.
5. **Security Isolation**:
   * Terapkan arsitektur Trusted Types sederhana untuk seluruh sanitasi template string sebelum dimasukkan ke dalam DOM.

### Verifikasi Hasil:
Buka **Chrome DevTools Performance Panel**, rekam profil selama 10 detik saat simulasi 5.000 pesawat aktif berjalan. Analisis trace profil Anda: pastikan grafik menunjukkan frame rate 60 FPS datar berwarna hijau, tidak ada baris merah bertuliskan *Forced Reflow*, dan alokasi waktu *Rendering/Painting* berada di bawah $2\text{ ms}$ per frame.