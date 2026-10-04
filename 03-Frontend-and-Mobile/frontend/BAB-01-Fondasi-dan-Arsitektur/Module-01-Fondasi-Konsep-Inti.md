# Kurikulum Rekayasa Frontend Modern
## Bab 01: Arsitektur Eksekusi Browser & Runtime Environment
### Modul 01: Mekanika Internal Browser & The Critical Rendering Path (CRP)

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** siklus hidup pemrosesan dokumen web dari fase penerimaan byte network hingga komposit piksel pada GPU.
- **Mendiagnosis** hambatan performa akibat operasi *parser-blocking* dan *render-blocking* pada pipeline eksekusi.
- **Mengimplementasikan** optimasi *Critical Rendering Path* (CRP) untuk mencapai target sub-100ms *First Contentful Paint* (FCP) dan *Largest Contentful Paint* (LCP).
- **Mengevaluasi** dampak modifikasi antarmuka berbasis DOM API terhadap fase *Reflow* (Layout), *Repaint*, dan *Compositing*.
- **Merancang** arsitektur antarmuka pengguna berbasis pemisahan *thread* (Main Thread vs Compositor/Worker Thread) untuk mempertahankan *frame budget* 16.67ms (60 FPS) atau 8.33ms (120 FPS).

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib menguasai:
- Arsitektur protokol jaringan: Model TCP/IP, TLS Handshake, HTTP/1.1 pipelining vs HTTP/2 multiplexing vs HTTP/3 (QUIC).
- Mekanisme parsing data: Teori otomata dasar, *lexical analysis*, *tokenization*, dan representasi struktur data *Tree* (Pohon).
- Dasar-dasar web standards: Spesifikasi sintaksis HTML5, CSS3 *cascading & specificity rules*, serta runtime execution context JavaScript (ECMAScript 2020+).

---

### 3. Core Concept
Browser modern bukanlah sekadar parser dokumen sederhana; browser adalah sistem operasi mini terdistribusi yang mengorkestrasi komputasi konkuren melalui proses-proses terisolasi (*Multi-Process Architecture*). 

```
[Network Stream: Octets]
         │
         ▼
[Lexical Analysis / Tokenization]
         │
         ▼
[Node Construction & Tree Building] ──► [DOM Tree]
                                            │
[CSS Tokenization & Cascade Engine] ──► [CSSOM Tree]
                                            │
                                            ├──► [Render Tree]
                                                       │
                                                       ▼
                                                [Layout Engine]
                                                (Geometry/Box Metrics)
                                                       │
                                                       ▼
                                                [Paint Engine]
                                                (Draw Calls & Display Lists)
                                                       │
                                                       ▼
                                                [Raster Engine]
                                                (Tiles to Bitmaps via Skia)
                                                       │
                                                       ▼
                                                [Compositor / GPU]
```

Inti dari rekayasa performa frontend berakar pada manipulasi **Critical Rendering Path (CRP)**: urutan sekuensial yang dilalui browser untuk mengonversi data HTML, CSS, dan JavaScript menjadi representasi visual piksel pada layar display.

---

### 4. Why it Matters
Mengabaikan mekanika internal browser mengarah pada:
- **Jank & Frame Drops**: Interaksi antarmuka yang tersendat akibat eksekusi skrip komputasi berat pada *Main Thread*, melanggar batas *Interaction to Next Paint* (INP).
- **Core Web Vitals Degradation**: Kegagalan metrik LCP dan *Cumulative Layout Shift* (CLS) yang berdampak langsung pada *ranking* SEO teknis dan konversi bisnis.
- **Konsumsi Baterai & Memori yang Eksplosif**: Alokasi *layer* GPU tanpa kalkulasi matang (*excessive layer promotion*) memicu *memory bloat* dan terminasi proses peramban oleh *Out-Of-Memory* (OOM) killer pada perangkat *mobile*.

---

### 5. What it Is & What it is Not

#### What it Is
- **Pipeline Render Terstruktur**: Jalur deterministik dari input representasi teks deklaratif menuju instruksi grafis tingkat rendah (*rasterization*).
- **Sistem Bersifat Asinkron & Konkuren**: Pemanfaatan *Speculative Parsing* untuk memicu pre-fetching aset secara paralel sementara *Main Thread* terblokir oleh eksekusi JavaScript.
- **Model Berbasis *Event-Loop***: Eksekusi berkesinambungan antara evaluasi makrotask, mikrotask, *requestAnimationFrame*, dan siklus *render steps*.

#### What it is Not
- **Bukan DOM Manipulation Instan**: Pemanggilan `element.appendChild()` tidak seketika mengubah piksel di monitor; pemanggilan tersebut hanya memutasi representasi in-memory DOM Tree sebelum dijadwalkan ulang dalam *tick* render berikutnya.
- **Bukan Single-Threaded System**: Meskipun eksekusi JavaScript aplikasi bersifat *single-threaded*, browser menjalankan *Network Thread*, *Storage Thread*, *Compositor Thread*, dan *Tile Raster Worker Threads* secara independen.

---

### 6. How it Works Under the Hood

#### A. Multi-Process Architecture (Chromium Base)
1. **Browser Process**: Mengelola *address bar*, *bookmarks*, navigasi jaringan, dan hak akses sistem file.
2. **Renderer Process**: Menjalankan *Blink engine* dan *V8 JavaScript runtime*. Bertanggung jawab atas konversi kode web menjadi piksel. Setiap tab umumnya dialokasikan ke dalam Renderer Process yang terpisah (*Process-per-site-instance*).
3. **GPU Process**: Mengisolasi panggilan antarmuka grafis (DirectX, Metal, Vulkan, OpenGL) dari sisa proses browser lainnya.

#### B. Pipeline Konstruksi DOM & CSSOM
1. **Conversion**: Browser membaca *raw bytes* dari jaringan atau disk lokal, kemudian menerjemahkannya menjadi karakter berdasarkan *encoding* yang didefinisikan (misal: UTF-8).
2. **Tokenizing**: *State-machine parser* mengonversi deretan karakter menjadi *tokens* yang divalidasi oleh standar W3C (misal: `StartTag: <html>`, `StartTag: <body>`, `Character: Hello`, `EndTag: </body>`).
3. **Lexing / Node Creation**: Objek *Node* instansiasi dibuat, menyimpan properti metadata dan kaitannya dengan node lain.
4. **Tree Construction**: Node dikaitkan dalam struktur relasional pohon (*DOM Tree*). Parser HTML bersifat pemaaf (*error-tolerant*), menangani tag tak tertutup via koreksi otomatis W3C HTML5 spec.
5. **CSSOM Generation**: Bersamaan dengan itu, CSS diparsing. Berbeda dengan HTML yang dapat diolah secara parsial/streaming, **CSSOM bersifat render-blocking** dan tidak toleran terhadap parsing parsial; CSSOM harus di-parsing tuntas sebelum Render Tree dapat dihitung untuk menghindari *Flash of Unstyled Content* (FOUC).

#### C. Script Parsing & V8 Execution Interruption
Ketika parser menemukan tag `<script>` tanpa atribut asinkron (`async` / `defer`):
- HTML parsing **berhenti total**.
- Kontrol dialihkan ke JavaScript Engine (V8).
- Jika ada network request eksternal untuk skrip tersebut, Main Thread memasuki kondisi *idle-wait* hingga aset terunduh, kecuali jika didukung oleh *Preload Scanner* yang berjalan di thread pembantu untuk melanjutkan unduhan di latar belakang.
- V8 mengeksekusi skrip melalui pipeline: Code -> Parser -> AST -> Ignition (Interpreter/Bytecode) -> TurboFan (JIT Compiler).
- Jika skrip memodifikasi CSSOM atau mengakses *computed style* (misal: `offsetHeight`), engine mengeksekusi *synchronous reflow*.

#### D. Layout, Paint, dan Rasterization
1. **Render Tree**: Menggabungkan DOM dan CSSOM. Elemen dengan `display: none` diabaikan sepenuhnya; elemen dengan `visibility: hidden` tetap disertakan karena mempertahankan dimensi spasial.
2. **Layout (Reflow)**: Menghitung koordinat absolut kartesian dan ukuran geometri setiap node (*bounding boxes*) relatif terhadap *viewport*.
3. **Paint**: Menghasilkan daftar instruksi grafis (*Display List*), seperti `drawRect()`, `drawText()`. Fase ini dibagi menjadi beberapa lapisan (*layers*).
4. **Compositing**: Mengelompokkan layer-layer visual, mengunggah tekstur ke GPU memory, dan memanipulasinya (transformasi matriks 3D, opasitas) tanpa melibatkan CPU *Main Thread*.

---

### 7. Architecture / Flow Diagram

```
                 NETWORKING LAYER (HTTP/2 / HTTP/3 Stream)
                                     │
                     [Raw Bytes: e.g., 0x3C 0x68 0x74 0x6D]
                                     │
                                     ▼
                        [Character Stream (UTF-8)]
                                     │
                                     ▼
                            [Tokenization Phase]
                         (Tags, Attributes, Values)
                                     │
                                     ▼
                            [Tree Construction]
                         ┌───────────┴───────────┐
                         ▼                       ▼
                   [DOM Builder]           [CSS Builder]
                   (Error Tolerance)     (Strict Cascade Engine)
                         │                       │
                         ▼                       ▼
                    [DOM Tree]              [CSSOM Tree]
                         │                       │
                         └───────────┬───────────┘
                                     ▼
                            [Render Tree Fusion]
                 (Filters nodes with display: none, applies styles)
                                     │
                                     ▼
                              [Layout Engine]
                (Calculate X, Y, Width, Height relative to Viewport)
                                     │
                                     ▼
                              [Paint Pipeline]
               (Generate Display Lists: z-index, background, text)
                                     │
                                     ▼
                            [Layer Compositing]
              (Main Thread delegates to Compositor Thread)
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
        [Tiling Engine]                         [Compositor Thread]
   (Splits layers into tiles)              (Calculates scroll offset,
                 │                               Transforms)
                 ▼                                       │
        [Rasterizer Worker]                              │
   (GPU via Skia converts tiles                          │
         into bitmapped pixels)                          │
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     ▼
                                [GPU Draw]
                     (Direct display output buffer)
```

---

### 8. Syntax / API Breakdown

Berikut adalah primitif browser API yang berinteraksi langsung dengan mekanisme internal CRP:

```javascript
// 1. Memeriksa performa metrik navigasi secara mikro
const navigationTiming = performance.getEntriesByType('navigation')[0];
const crpMetrics = {
  // Waktu dari awal fetch hingga dokumen tuntas di-parse
  domInteractive: navigationTiming.domInteractive,
  // Titik waktu saat DOM dan CSSOM tuntas dikonstruksi
  domContentLoaded: navigationTiming.domContentLoadedEventEnd,
  // Seluruh sub-resource (gambar, frame) telah diunduh
  domComplete: navigationTiming.domComplete,
};

// 2. Modifikasi atribut script execution
const script = document.createElement('script');
script.src = '/dist/bundle.js';
script.async = false; // Mempertahankan urutan eksekusi, tetap non-blocking parser jika true
script.defer = true;  // Parsing DOM tidak terhambat; eksekusi ditunda hingga DOM parsed

// 3. Mengontrol invalidasi layer secara hardware-accelerated via CSS Typed OM
// Menghindari Main Thread Layout & Paint
const cardElement = document.querySelector('.metric-card');
cardElement.attributeStyleMap.set('transform', new CSSTransformValue([
  new CSSTranslate(CSS.px(10), CSS.px(20))
]));
```

---

### 9. Minimal Working Example

Contoh berikut menunjukkan optimasi struktur HTML guna mencegah *CRP Waterfall Stoppage*:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Minimal CRP Benchmark</title>

  <!-- 1. Resource Hint: Preconnect untuk koneksi eksternal kritis -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

  <!-- 2. Critical CSS: Di-inlining langsung di dalam Head guna memangkas roundtrip CSSOM -->
  <style>
    :root { --surface-primary: #121212; --text-primary: #f5f5f5; }
    body { margin: 0; background: var(--surface-primary); color: var(--text-primary); font-family: sans-serif; }
    .hero-container { min-height: 100vh; display: grid; place-items: center; }
    .skeleton-box { width: 300px; height: 150px; background-color: #2a2a2a; border-radius: 8px; }
  </style>

  <!-- 3. Non-critical CSS: Diload asinkron menggunakan media query toggle trick -->
  <link rel="stylesheet" href="/assets/css/non-critical.css" media="print" onload="this.media='all'">
  <noscript><link rel="stylesheet" href="/assets/css/non-critical.css"></noscript>

  <!-- 4. JavaScript dimuat tanpa menghambat Tokenizer / Parser -->
  <script src="/assets/js/core-tracker.js" defer></script>
</head>
<body>
  <div class="hero-container">
    <div class="skeleton-box" id="app-root">
      <p>Memuat Sistem...</p>
    </div>
  </div>
</body>
</html>
```

---

### 10. Enterprise / Practical Implementation

Contoh implementasi arsitektur frontend tingkat lanjut: Penjadwalan DOM Mutasi Massal guna Mencegah **Forced Synchronous Layout** (Layout Thrashing) dengan memanfaatkan *Virtual Render Queue* berbasis *Task Batching*:

```typescript
/**
 * RenderQueueManager
 * Mengisolasi mutasi DOM (Write) dan pembacaan geometri (Read)
 * ke fase terpisah guna mencegah layout thrashing dalam 1 frame render tick.
 */
type ReadTask = () => void;
type WriteTask = () => void;

export class LayoutBatchScheduler {
  private static instance: LayoutBatchScheduler;
  private readQueue: ReadTask[] = [];
  private writeQueue: WriteTask[] = [];
  private isFrameScheduled: boolean = false;

  private constructor() {}

  public static getInstance(): LayoutBatchScheduler {
    if (!LayoutBatchScheduler.instance) {
      LayoutBatchScheduler.instance = new LayoutBatchScheduler();
    }
    return LayoutBatchScheduler.instance;
  }

  public read(task: ReadTask): void {
    this.readQueue.push(task);
    this.scheduleFlush();
  }

  public write(task: WriteTask): void {
    this.writeQueue.push(task);
    this.scheduleFlush();
  }

  private scheduleFlush(): void {
    if (this.isFrameScheduled) return;

    this.isFrameScheduled = true;
    requestAnimationFrame((timestamp: DOMHighResTimeStamp) => {
      this.flushQueues(timestamp);
    });
  }

  private flushQueues(timestamp: DOMHighResTimeStamp): void {
    const startTime = performance.now();

    // 1. Eksekusi seluruh operasi READ (Geometry computation)
    // Tidak ada dirty styles, sehingga tidak terjadi reflow berulang
    while (this.readQueue.length > 0) {
      const readTask = this.readQueue.shift();
      if (readTask) readTask();
    }

    // 2. Eksekusi seluruh operasi WRITE (Style mutations)
    // DOM ditandai dirty, browser akan menjadwalkan 1 kali layout komposit pada akhir tick
    while (this.writeQueue.length > 0) {
      const writeTask = this.writeQueue.shift();
      if (writeTask) writeTask();
    }

    this.isFrameScheduled = false;

    const executionDuration = performance.now() - startTime;
    if (executionDuration > 16.67) {
      console.warn(`[Frame Budget Breached] Eksekusi memakan waktu: ${executionDuration.toFixed(2)}ms`);
    }
  }
}

// ==========================================
// Penggunaan di Sistem Berskala Besar
// ==========================================

const scheduler = LayoutBatchScheduler.getInstance();

// Simpan elemen-elemen DOM
const nodes = document.querySelectorAll<HTMLElement>('.data-grid-row');

// ANTI-PATTERN:
// nodes.forEach(node => {
//   const h = node.offsetHeight; // READ (memicu reflow paksa)
//   node.style.height = `${h * 2}px`; // WRITE (merusak tree)
// });

// SOLUSI ENTERPRISE:
nodes.forEach((node) => {
  // Batching READ
  scheduler.read(() => {
    const currentHeight = node.getBoundingClientRect().height;
    
    // Batching WRITE
    scheduler.write(() => {
      // Mengubah property transform ketimbang height untuk memotong tahapan Reflow
      node.style.transform = `scaleY(${currentHeight > 100 ? 1.2 : 0.8})`;
      node.style.willChange = 'transform';
    });
  });
});
```

---

### 11. Edge Cases & Gotchas

1. **The Script Preload Scanner Blindspot**: Script parser yang disuntikkan via ekspresi JavaScript murni (`document.write('<script ...')` atau string templates kompleks) tidak dapat diidentifikasi oleh *speculative parsing engine*. Hal ini menunda pengunduhan resource hingga evaluasi kode mencapai statement tersebut.
2. **Webfont Invisible Text (FOIT vs FOUT)**: Font eksternal yang diunduh via `@font-face` memicu *Flash of Invisible Text* secara default di engine WebKit/Blink jika `font-display: swap` tidak dikonfigurasi, menyebabkan teks tidak dapat dibaca hingga aset font terunduh sempurna.
3. **Cumulative Layout Shift dari Dynamic Responsive Images**: Gambar tanpa rasio dimensi yang didefinisikan secara eksplisit (`width` dan `height` atribut HTML atau CSS `aspect-ratio`) akan memiliki ukuran $0 \times 0$ piksel selama fase *Initial Layout*, lalu memicu reflow masif di seluruh dokumen saat byte citra selesai didekode.

---

### 12. Performance Considerations

| Metrik Engine | Batas Aman | Dampak Buruk |
| :--- | :--- | :--- |
| **Main Thread Long Task** | $\le 50\text{ ms}$ | Membekukan antarmuka, melanggar batas INP (> 200ms). |
| **Total Blocking Time (TBT)** | $\le 200\text{ ms}$ | Menunda kesiapan aplikasi untuk menerima interaksi pengguna. |
| **DOM Tree Depth** | $\le 32\text{ level}$ | Meningkatkan kompleksitas traversal rekursif saat kalkulasi style ($O(N \cdot M)$). |
| **Total DOM Nodes** | $\le 1.400\text{ node}$ | Mengonsumsi memori berlebih dan memperlambat fase kloning virtual/real DOM. |

#### Optimasi Transformasi Ruang Rendering
Manipulasi properti visual harus diprioritaskan pada level *Composite-Only*:
- **Memicu Reflow + Repaint + Composite**: `width`, `height`, `margin`, `padding`, `top`, `left`, `border`, `font-size`.
- **Memicu Repaint + Composite**: `background-color`, `color`, `visibility`, `box-shadow`.
- **Hanya Memicu Composite (GPU Target)**: `transform`, `opacity`, `filter` (khusus implementasi tertentu).

---

### 13. Security Implications

Siklus eksekusi parsing memiliki implikasi langsung terhadap celah keamanan aplikasi web:

```
Unsanitized Payload ──► Tokenizer ──► Injeksi Malicious Node ──► DOM-based XSS
```

1. **DOM-based Cross-Site Scripting (XSS)**: Pemanggilan API parser internal secara tidak aman melalui sink seperti `.innerHTML`, `outerHTML`, atau `document.write()` memaksa engine mem-parse string acak sebagai markup token. Penyerang dapat menyuntikkan payload vektor eksekusi:
   ```javascript
   // CRITICAL VULNERABILITY:
   const searchParam = new URLSearchParams(window.location.search).get('q');
   targetNode.innerHTML = `<div>Hasil: ${searchParam}</div>`; 
   // Payload '?q=<img src=x onerror=alert(document.cookie)>' langsung dieksekusi parser.
   ```
2. **Mitigasi**: Selalu gunakan `element.textContent`, manipulasi teks langsung via `document.createTextNode`, atau sanitasi menggunakan API platform seperti `sanitizer.sanitizeFor()` (W3C Sanitizer API) atau pustaka terverifikasi (DOMPurify).
3. **Content Security Policy (CSP)**: Terapkan header respons HTTP guna menonaktifkan evaluasi skrip inline tanpa *nonce* kriptografi yang valid:
   ```http
   Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-rAnd0m123'; object-src 'none';
   ```

---

### 14. Accessibility (a11y) & Standards Compliance

Proses rendering memiliki percabangan krusial yang berjalan paralel dengan Render Tree: **The Accessibility Tree (AOM - Accessibility Object Model)**.

1. **Paralelisasi AOM**: Engine browser memetakan DOM Tree ke dalam AOM yang dikonsumsi oleh teknologi asistif (*Screen Reader*). Elemen dengan `display: none` **dihapus** dari Accessibility Tree; namun elemen dengan `opacity: 0` atau `position: absolute; left: -9999px` **tetap diproses**.
2. **Standard Compliance (Semantics)**: Penggunaan tag generik (`<div>`, `<span>`) untuk kontrol interaktif merusak mapping AOM.
   ```html
   <!-- BURUK: Aksesibilitas gagal, butuh modifikasi manual AOM via ARIA -->
   <div class="custom-button" onclick="submit()">Kirim</div>

   <!-- SESUAI STANDAR: Terintegrasi otomatis ke AOM dengan role, focusable, & keyboard action -->
   <button type="button" onclick="submit()">Kirim</button>
   ```

---

### 15. Trade-off Matrix

| Pola Arsitektur | Keuntungan | Kerugian / Risiko | Skenario Ideal |
| :--- | :--- | :--- | :--- |
| **Inlined Critical CSS** | Menghilangkan network roundtrip CSS; FCP instan. | Mengurangi efisiensi *HTTP Caching*; ukuran base HTML membesar. | Halaman pendaratan (*Landing Page*) dengan retensi pengguna baru. |
| **Monolithic External CSS** | Efisiensi caching browser tinggi antar navigasi halaman. | Render-blocking pada First Load; menunda pemrosesan First Paint. | Aplikasi berbasis dasbor internal dengan sesi penggunaan lama. |
| **CSS-in-JS (Runtime Injection)** | *Scoped styling*; penghapusan style mati (*dead code*) deterministik. | Overhead evaluasi JS besar; injeksi runtime memicu style recalculation konstan. | Sistem komponen berskala tinggi dengan variasi tema yang sangat dinamis. |
| **GPU Layer Promotion (`will-change`)**| Isolasi repaint ke GPU; animasi berjalan mulus pada 60/120 FPS. | *VRAM Consumption Bloat*; berisiko memicu efek *font blurriness* akibat subpixel anti-aliasing dinonaktifkan. | Digunakan secara eksklusif sesaat sebelum elemen visual dianimasikan. |

---

### 16. Anti-Patterns & Code Smells

#### Anti-Pattern: Layout Thrashing (Forced Synchronous Layout)
Terjadi saat developer membaca properti geometrik elemen tepat setelah memodifikasi gaya visualnya, memaksa browser menghentikan eksekusi JavaScript guna menjalankan Layout seketika itu juga.

```javascript
// CODE SMELL:
function resizeAllCards() {
  const cards = document.querySelectorAll('.card');
  for (let i = 0; i < cards.length; i++) {
    // Menulis ke DOM (Style invalidated)
    cards[i].style.width = '200px';
    
    // MEMBACA DARI DOM: Engine terpaksa Reflow synchronous pada setiap iterasi loop!
    const clientHeight = cards[i].clientHeight; 
    console.log(`Card height: ${clientHeight}`);
  }
}

// REFACTORED SOLUTION:
function resizeAllCardsOptimized() {
  const cards = document.querySelectorAll('.card');
  
  // Fase 1: WRITE secara masif
  for (let i = 0; i < cards.length; i++) {
    cards[i].style.width = '200px';
  }
  
  // Fase 2: READ terkonsolidasi setelah batch write selesai
  for (let i = 0; i < cards.length; i++) {
    const clientHeight = cards[i].clientHeight;
    console.log(`Card height: ${clientHeight}`);
  }
}
```

---

### 17. Best Practices & Design Patterns

1. **Minimize Critical Resource Count**: Kurangi berkas pemblokir render awal ke batas seminimal mungkin. Manfaatkan atribut `media` pada `<link rel="stylesheet">` agar file style cetak atau desktop-only tidak memblokir render seluler.
2. **Prioritas Pemuatan via Resource Priorities**:
   - `rel="preload"`: Resource kritis yang dibutuhkan dalam beberapa detik awal (misal: hero font, LCP image).
   - `rel="prefetch"`: Resource untuk kebutuhan navigasi halaman berikutnya.
   - `fetchpriority="high"`: Diberikan langsung pada elemen visual utama pelopor metrik LCP.
3. **Pemisahan Logika Komputasi dari Visual Core**: Delegasikan pemrosesan data biner, komputasi kriptografi, atau pemilahan array berukuran masif ke dalam **Web Workers** agar *Main Thread* sepenuhnya didedikasikan untuk respons input antarmuka dan pipeline render 60 FPS.

---

### 18. Debugging & Observability

#### Mengisolasi Masalah CRP Menggunakan Chrome DevTools:
1. **Performance Panel**:
   - Rekam alur navigasi menggunakan profil CPU Throttling (misal: *4x/6x slowdown*) untuk mensimulasikan kapabilitas perangkat *low-end*.
   - Amati segmen *Main*: Cari indikator segitiga merah di pojok kanan atas aktivitas task yang menandai *Long Task* (> 50ms).
   - Evaluasi baris rekaman: Temukan blok berulang **Recalculate Style** -> **Layout** -> **Update Layer Tree** dalam satu frame cycle (*Forced Synchronous Layout warning*).
2. **Rendering Tab**:
   - Aktifkan **Paint Flashing**: Mengidentifikasi area visual mana saja yang mengalami *repaint* (ditandai dengan kilatan warna hijau). Area yang konstan berkedip saat scrolling menandakan kegagalan isolasi layer.
   - Aktifkan **Layer Borders**: Menampilkan batas *composited layers* (garis oranye) dan *render tiles* (garis biru).
3. **PerformanceObserver API (In-Production Telemetry)**:
   ```javascript
   const observer = new PerformanceObserver((list) => {
     for (const entry of list.getEntries()) {
       if (entry.duration > 50) {
         // Kirim telemetry Long Task ke endpoint analitik
         navigator.sendBeacon('/analytics/long-tasks', JSON.stringify({
           name: entry.name,
           startTime: entry.startTime,
           duration: entry.duration
         }));
       }
     }
   });
   observer.observe({ entryTypes: ['longtask'] });
   ```

---

### 19. Hands-on Exercises & Challenges

#### Skenario Latihan:
Anda diberikan sebuah aplikasi web e-commerce legacy yang memiliki nilai skor Core Web Vitals LCP 4.8 detik dan INP 420ms.

#### Tugas:
1. **Refactoring File Eksekusi**: Identifikasi berkas CSS pihak ketiga (seperti font libraries dan analytics tracker) yang diletakkan secara blocking di dalam blok `<head>`.
2. **Implementasikan Lazy Hydration Script**: Buat sebuah custom loader menggunakan `IntersectionObserver` untuk memuat *heavy components* hanya saat kontainer target hampir memasuki *viewport*.
3. **Eliminasi Reflow Loop**: Refactor fungsi resize kalkulasi masonry grid dari sistem legacy yang memicu layout thrashing. Ganti manipulasi koordinat `top`/`left` menjadi representasi *GPU-Accelerated* `transform: translate3d(x, y, 0)`.

#### Kriteria Keberhasilan:
- Nilai LCP tereduksi hingga $< 1.8\text{ detik}$ pada simulasi throttling jaringan Fast 3G.
- DevTools Performance Panel tidak lagi mencatat peringatan *Forced Reflow* berwarna merah pada event scroll atau window resize.

---

### 20. Summary & Knowledge Check

#### Rangkuman Konsep Kunci:
- Browser merender web via serangkaian tahapan deterministik: **Network Bytes -> Tokens -> DOM/CSSOM -> Render Tree -> Layout -> Paint -> Composite**.
- HTML parsing dapat berjalan secara streaming, namun **CSSOM bersifat render-blocking**, dan JavaScript default bersifat **parser-blocking**.
- Menghindari perombakan layout (Reflow) adalah kunci menjaga frame-budget; prioritaskan modifikasi layer pada level GPU Compositing via `transform` dan `opacity`.

#### Kuis Evaluasi Diri:
1. *Mengapa penempatan tag `<script>` standar tanpa atribut `defer` atau `async` di awal elemen `<head>` menyebabkan penundaan kemunculan visual pertama halaman web?*
2. *Jelaskan perbedaan spesifik antara fase "Layout" dan "Compositing" dalam kaitannya dengan alokasi pemrosesan CPU vs GPU!*
3. *Apa yang terjadi secara internal pada layout engine jika Anda menjalankan instruksi `element.classList.add('active')` lalu langsung memanggil `window.scrollY` pada baris kode berikutnya?*
4. *Mengapa elemen dengan properti CSS `visibility: hidden` tetap masuk ke dalam konstruksi Render Tree, sedangkan elemen dengan `display: none` diabaikan sepenuhnya?*