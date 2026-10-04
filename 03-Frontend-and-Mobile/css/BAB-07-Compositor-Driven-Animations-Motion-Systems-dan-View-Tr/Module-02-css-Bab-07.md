# BAB 07: Compositor-Driven Animations, Motion Systems, dan View Transitions
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menganalisis siklus render internal engine browser (Blink/WebKit/Gecko) untuk membedakan eksekusi di Main Thread vs. Compositor Thread vs. Render/GPU Process.
- Merancang dan mengimplementasikan **Motion Design System** berbasis Design Tokens, Typed OM (Object Model), dan Web Animations API (WAAPI) yang hemat daya serta mematuhi kriteria WCAG 2.2 (`prefers-reduced-motion`).
- Menguasai arsitektur dan lifecycle dari **View Transitions API** (Single-Page Application dan Multi-Page Application), termasuk manipulasi pohon pseudo-element runtime (`::view-transition-*`).
- Mengoptimalkan alokasi memori VRAM GPU, mencegah *layer explosion*, serta meniadakan *Layout Thrashing* dan *Subpixel Anti-Aliasing degradation* pada animasi layer terpromosi.
- Mendiagnosis dan mengaudit masalah performa rendering menggunakan Chrome DevTools (Layers panel, Performance Profiler, Rendering HUD, Frame Rendering Stats).

---

### 2. Prerequisite

Sebelum mendalami modul ini, Anda wajib memiliki pemahaman mendalam tentang:
- **Rendering Pipeline Fundamental**: Tahapan Parsing HTML/CSS, Style Calculation, Layout (Reflow), Paint (Repaint), Tiling, Rasterization, dan Compositing.
- **CSS Object Model & Modern CSS**: CSS Custom Properties tingkat lanjut, CSS Math Functions (`clamp()`, `calc()`), CSS Containment (`contain: layout paint style`).
- **JavaScript Asynchronous & DOM Execution**: Event Loop (Microtask, Macrotask, `requestAnimationFrame`), Promise lifecycle, dan DOM mutation semantics.
- **Tools**: Chrome DevTools Profiler, WebPageTest, serta pemahaman dasar arsitektur grafis (Raster, Texture quad, GPU Buffer/VRAM).

---

### 3. Concept & Internal Architecture

#### 3.1 Chromium Rendering Engine Architecture (Blink, cc, Viz)

Rendering engine modern memisahkan tugas komputasi dokumen dan presentasi frame ke dalam proses dan thread yang berbeda:

```
[Browser Process]
       │  (IPC / Mojo)
       ▼
[Renderer Process]
  ├── Main Thread:
  │     DOM, CSSOM, Style Recalc, Layout, Pre-Paint, Paint (Display Lists Creation)
  │     (Commit via Commit-flow)
  │     │
  │     ▼
  └── Compositor Thread (Chrome Compositor / cc):
        Layer Tree, Tiling, Scroll/Pinch Handling, Layer Animations (transform, opacity, filter)
        (Raster Tasks via PaintWorklet / GPU Process)
        │
        ▼
[GPU Process (Viz)]
  ├── Raster Worker Threads (Skia / Ganesh / Graphite) -> Menghasilkan Bitmaps di VRAM
  └── Display Compositor Thread -> Output Draw Quads -> OpenGL/Vulkan/Metal Context -> OS Display Server
```

1. **Paint Phase**: Bukan menghasilkan piksel langsung di layar, melainkan sekumpulan instruksi grafis (**Display Item List**) seperti `drawRect`, `clipRect`, `drawTextBlob`.
2. **Commit Phase**: Data layer tree dan Display Lists ditransfer dari Main Thread ke Compositor Thread (`cc`). Main thread dibebaskan untuk mengeksekusi JavaScript berikutnya.
3. **Tiling & Raster**: Compositor thread membagi layer besar menjadi ubin-ubin kecil (**Tiles**, biasanya 256x256 atau 512x512 piksel). Tile dikirim ke GPU Process untuk di-rasterisasi menjadi bitmapped texture yang disimpan dalam VRAM.
4. **Draw Phase**: Compositor thread mengalkulasi posisi proyeksi tiap tile (**Draw Quads**) berdasarkan matriks transformasi saat ini, lalu Viz menggabungkannya ke dalam framebuffer layar.

#### 3.2 Compositor-Driven Properties: Transform, Opacity, Filter, Clip-Path

Hanya dua properti yang dijamin 100% bebas dari Main Thread Layout & Paint pada semua engine modern:
- `transform`: Memanipulasi matriks transformasi 4x4 affine/projective layer tanpa mengubah geometri layout saudara/induknya.
- `opacity`: Memodifikasi alpha channel dari texture buffer layer saat digambar oleh GPU.

Properti `filter` dan `clip-path` dapat dijalankan pada compositor jika:
- Efek filter tidak bergantung pada layout dinamis elemen lain.
- Bentuk `clip-path` menggunakan path dasar (`polygon`, `circle`, `inset`) yang dapat direpresentasikan langsung sebagai shader scissor/stencil pada GPU, bukan clipping bertingkat terhadap teks DOM.

Jika properti seperti `width`, `margin-top`, atau `top` dianimasikan, pipeline dipaksa kembali ke tahap **Layout**:
$$\text{Layout} \longrightarrow \text{Paint} \longrightarrow \text{Commit} \longrightarrow \text{Raster} \longrightarrow \text{Draw}$$
Animasi compositor-driven hanya mengeksekusi:
$$\text{Compositor Thread Transform Calculation} \longrightarrow \text{Draw Quads to Screen}$$
Ini memastikan laju penyegaran frame tetap **60 FPS / 120 FPS ProMotion** meskipun Main Thread terblokir eksekusi JavaScript yang berat selama 500ms.

#### 3.3 Layer Promotion & VRAM Overhead

Elemen dipromosikan menjadi Composited Layer (GraphicsLayer/cc::Layer) akibat pemicu:
- Direct Reasons: Properti 3D transform (`translateZ(0)`, `transform: translate3d(...)`), `will-change: transform`, elemen `<video>`, `<canvas>`, atau animasi CSS aktif pada properti compositor.
- Indirect Reasons (Overlap Injection): Elemen normal yang secara visual berada di atas (*z-index stacking*) elemen yang terpromosi, memaksa browser mempromosikannya untuk menjaga stacking order visual.

**Rumus Estimasi Konsumsi VRAM Layer:**
$$\text{VRAM Usage (Bytes)} = \text{Width (px)} \times \text{Height (px)} \times 4 \text{ bytes (RGBA8888)} \times \text{Device Pixel Ratio}^2$$

*Contoh Perhitungan:*
Sebuah elemen modal dengan ukuran $1920 \times 1080$ pada layar Retina/HiDPI ($\text{DPR} = 2$):
$$\text{Total Pixels} = (1920 \times 2) \times (1080 \times 2) = 3840 \times 2160 = 8.294.400 \text{ piksel}$$
$$\text{Memory} = 8.294.400 \times 4 \text{ bytes} = 33.177.600 \text{ bytes} \approx 31.64 \text{ MB VRAM}$$
Promosi layer tanpa kontrol (**Layer Explosion**) pada 100 elemen daftar akan langsung mengonsumsi $\approx 3 \text{ GB VRAM}$, memicu low-memory warning, OOM (Out Of Memory) crash pada mobile, atau terminasi Renderer Process oleh OS.

#### 3.4 Anatomi & State Machine View Transitions API

View Transitions API mengabstraksi mekanisme *cross-fade* dan koordinat *morphing* antar dua status DOM (SPA maupun MPA).

Saat `document.startViewTransition(updateCallback)` dieksekusi:
1. Engine mengambil snapshot visual dari elemen terdaftar (`view-transition-name`). Ini menjadi state **Old**.
2. Rendering pipeline dibekukan sementara.
3. `updateCallback()` dipanggil, melakukan mutasi DOM (misal: router navigasi memuat view baru).
4. Engine menganalisis state **New**, menghitung layout, dan mengambil snapshot visual elemen baru.
5. Engine membuat pohon pseudo-element sementara di root dokumen (`::view-transition`):

```
::view-transition
└── ::view-transition-group(root)
    └── ::view-transition-image-pair(root)
        ├── ::view-transition-old(root)  --> Animasi: Fade-out / Transform
        └── ::view-transition-new(root)  --> Animasi: Fade-in / Transform
```

Jika elemen kustom memiliki `view-transition-name: hero-card`:
```
::view-transition
├── ::view-transition-group(root)
└── ::view-transition-group(hero-card)
    └── ::view-transition-image-pair(hero-card)
        ├── ::view-transition-old(hero-card)
        └── ::view-transition-new(hero-card)
```
Engine secara otomatis menginterpolasi posisi $(x, y)$ dan ukuran $(\text{width}, \text{height})$ dari batas *old* ke *new* menggunakan GPU transform, mengeliminasi kebutuhan komputasi manual matriks FLIP (First, Last, Invert, Play).

---

### 4. Why & What

| Dimensi | Animasi Klasik (Main-Thread Driven) | Animasi Modern (Compositor-Driven & View Transitions) |
| :--- | :--- | :--- |
| **Pemicu Mutasi** | Mengubah `top`, `left`, `margin`, `height`, `width`. | Mengubah `transform`, `opacity`, `view-transition-name`. |
| **Dampak Threading** | Bergantung pada Main Thread. Jika JS sibuk, terjadi *jank* (frame drop parah). | Berjalan mandiri pada Compositor Thread & GPU Viz. Tetap smooth 60/120 FPS saat Main Thread macet. |
| **Interpolasi State Antar Halaman** | Memerlukan JavaScript library FLIP eksternal yang rumit (GSAP Flip, Framer Motion) dengan overhead DOM berlebih. | Didukung native oleh engine browser via `::view-transition` pseudo-tree; hardware-accelerated tanpa payload runtime JS. |
| **Konsumsi Baterai & Daya** | CPU utilization tinggi akibat Layout & Paint loop kontinu. | Efisien; GPU rasterisasi sekali, sisanya kalkulasi matriks vertex transform. |
| **Aksesibilitas Visual** | Kerap mengabaikan `prefers-reduced-motion`, rentan memicu disorientasi vestibular. | Diintegrasikan terstruktur lewat sistem token CSS yang secara otomatis mematikan durasi atau mengubah axis motion. |

---

### 5. How (Workflow Detail)

Langkah-langkah merekayasa sistem motion tingkat enterprise:

```
[Tahap 1: Desain Token & Motion System]
  ├── Tetapkan durasi terstandarisasi: Instant (100ms), Fast (200ms), Base (300ms), Deliberate (500ms)
  ├── Tetapkan easing curves: Enter (Decelerate), Exit (Accelerate), Standard (Emphasized)
  └── Definisikan token fallback via @media (prefers-reduced-motion: reduce)

[Tahap 2: Deklarasi Layer Management]
  ├── Identifikasi elemen dinamis tinggi
  ├── Pasang `will-change` kontekstual sebelum animasi berjalan; hapus setelah selesai
  └── Audit komparasi memori via Chrome DevTools Layers panel

[Tahap 3: Konstruksi Transisi Status & View Transitions]
  ├── Identifikasi elemen persisten (Shared Element)
  ├── Pasang `view-transition-name` unik saat transisi aktif
  └── Pasang hooks pada SPA Router / Framework Navigation lifecycle

[Tahap 4: Eksekusi Hardware Acceleration]
  ├── Validasi animasi hanya menyentuh `transform` dan `opacity`
  └── Enforce boundary clipping via Compositor (CSS containment: `contain: layout paint`)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pencetakan Buku Animasi (Flipbook) vs. Proyektor Layer Bioskop

- **Main Thread Animation (Layout/Paint Driven):** Seperti seorang juru gambar yang harus menggambar ulang setiap frame karakter dan latar belakangnya di kertas kosong dari nol setiap 16 milidetik. Jika tangannya kram (JavaScript macet), seluruh pertunjukan terhenti total.
- **Compositor-Driven Animation:** Karakter dan latar belakang digambar di atas dua lembar mika plastik transparan terpisah (GPU Layers). Juru gambar tidak perlu menggambar ulang; operator proyektor (Compositor Thread) hanya perlu menggeser lembar mika karakter ke kanan menggunakan motor mekanis. Pertunjukan tetap berjalan mulus tanpa peduli apakah juru gambar sedang pingsan.

#### Diagram Transisi Arsitektural View Transitions API

```
   DOM State A (Katalog Produk)             DOM State B (Detail Produk)
   ┌───────────────────────────┐           ┌───────────────────────────┐
   │ [Card Image 100x100]      │           │ [Hero Image 400x400]      │
   │ (view-transition-name:    │           │ (view-transition-name:    │
   │  product-art)             │           │  product-art)             │
   └─────────────┬─────────────┘           └─────────────▲─────────────┘
                 │                                       │
                 ▼                                       │
      1. Capture Old Snapshot                 2. Capture New Snapshot
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     │
                                     ▼
        Pseudo-Element Tree Diaktifkan di Root::view-transition
   ┌─────────────────────────────────────────────────────────────────┐
   │ ::view-transition                                               │
   │  └── ::view-transition-group(product-art)                       │
   │       │ [Browser menginterpolasi rect dimensi & posisi GPU]     │
   │       └── ::view-transition-image-pair(product-art)             │
   │            ├── ::view-transition-old(product-art)               │
   │            │   (Opasitas: 1 -> 0, Scale: 100x100 -> 400x400)    │
   │            └── ::view-transition-new(product-art)               │
   │                (Opasitas: 0 -> 1, Scale: 100x100 -> 400x400)    │
   └─────────────────────────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Safe Compositor Layer Animation dengan Accessibility Fallback

```css
/* Definisikan Motion Design Tokens */
:root {
  --motion-duration-fast: 150ms;
  --motion-duration-normal: 300ms;
  --motion-ease-standard: cubic-bezier(0.2, 0, 0, 1);
  --motion-ease-decelerate: cubic-bezier(0, 0, 0.2, 1);
  --motion-ease-accelerate: cubic-bezier(0.3, 0, 1, 1);
}

/* Base interactive card */
.interactive-card {
  transform: translateZ(0); /* Force initial composite layer */
  transition: transform var(--motion-duration-normal) var(--motion-ease-standard),
              box-shadow var(--motion-duration-normal) var(--motion-ease-standard);
  contain: layout paint; /* Mengisolasi layout dari dokumen utama */
}

.interactive-card:hover {
  /* Menggunakan scale + translateY (100% compositor-driven) */
  transform: translateY(-4px) scale(1.02);
}

/* Wajib Enterprise: Reduced Motion Fallback */
@media (prefers-reduced-motion: reduce) {
  :root {
    --motion-duration-fast: 0ms;
    --motion-duration-normal: 0ms;
  }
  
  .interactive-card {
    transition: none !important;
  }
  
  .interactive-card:hover {
    transform: none !important;
    outline: 2px solid var(--color-primary-focus); /* Ganti motion dengan visual cue statis */
  }
}
```

#### 7.2 Practical Example: Enterprise-Grade Dynamic View Transition System

Sistem transisi SPA headless berkinerja tinggi yang mendukung cross-surface shared element transition dan safe fallbacks.

```css
/* style.css */
:root {
  --transition-speed: 350ms;
  --transition-curve: cubic-bezier(0.4, 0, 0.2, 1);
}

/* View Transition Base Overrides */
::view-transition-group(root) {
  animation-duration: var(--transition-speed);
  animation-timing-function: var(--transition-curve);
}

/* Shared Element Spesifik */
::view-transition-group(product-detail-hero) {
  animation-duration: var(--transition-speed);
  animation-timing-function: cubic-bezier(0.16, 1, 0.3, 1); /* Custom spring-like easing */
  border-radius: 8px;
  overflow: hidden;
}

/* Matikan crossfade default browser jika melakukan pure shape-morphing */
::view-transition-old(product-detail-hero),
::view-transition-new(product-detail-hero) {
  height: 100%;
  width: 100%;
  object-fit: cover;
}

/* Mencegah default snapshot blend yang memicu flickering warna teks */
::view-transition-old(product-detail-hero) {
  animation: none;
  opacity: 0;
}
::view-transition-new(product-detail-hero) {
  animation: none;
}

/* Handling Reduced Motion pada View Transition */
@media (prefers-reduced-motion: reduce) {
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
  }
}
```

```javascript
// motion-controller.js
export class EnterpriseNavigationTransition {
  /**
   * Mengeksekusi navigasi transisi aman dengan proteksi engine legacy
   * @param {Function} stateUpdateCallback - Fungsi mutasi DOM / State
   * @param {HTMLElement|null} sourceElement - Elemen yang memicu shared-element transition
   * @param {string} transitionName - Identitas view-transition-name
   */
  static async navigate(stateUpdateCallback, sourceElement = null, transitionName = '') {
    const isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Fallback untuk browser yang tidak mendukung View Transitions API atau User mematikan motion
    if (!document.startViewTransition || isReducedMotion) {
      await stateUpdateCallback();
      return;
    }

    try {
      // 1. Tagging dynamic source element jika ada
      if (sourceElement && transitionName) {
        sourceElement.style.viewTransitionName = transitionName;
      }

      // 2. Eksekusi View Transition
      const transition = document.startViewTransition(async () => {
        try {
          await stateUpdateCallback();
        } finally {
          // Bersihkan dynamic style dari DOM lama untuk mencegah memory leaks
          if (sourceElement && transitionName) {
            sourceElement.style.viewTransitionName = '';
          }
        }
      });

      // 3. Menunggu layout siap dan sinkronisasi element target
      await transition.ready;
      
    } catch (err) {
      console.error('[Motion Controller] Transisi dibatalkan atau gagal:', err);
      // Fail gracefully: pastikan callback tetap selesai
      await stateUpdateCallback();
    } finally {
      // Pastikan status DOM bersih setelah transisi selesai sepenuhnya
      if (sourceElement && transitionName) {
        sourceElement.style.viewTransitionName = '';
      }
    }
  }
}
```

---

### 8. Real World Case Study: E-Commerce Mega-App (Streaming Grid to PDP Transition)

#### Skenario Masalah
Sebuah platform marketplace global memiliki halaman listing dengan 80 item interaktif berisi gambar resolusi tinggi. Pada implementasi awal:
- Developer menggunakan `will-change: transform, opacity` di seluruh kartu pada CSS statis.
- Transisi dari Catalog Page ke Product Detail Page (PDP) menggunakan JavaScript framework FLIP library seberat 45 KB.

#### Gejala & Temuan Root Cause
1. **Layer Explosion**: Setiap kartu memicu alokasi composited layer independen.
   - Hasil audit Chrome DevTools: **80 Composited Layers**.
   - Memori GPU melonjak drastis hingga **420 MB VRAM** pada perangkat mobile mid-end. Browser mobile sering me-reload tab (*Low Memory Crash*).
2. **Layout Thrashing**: JS FLIP library membaca koordinat bounding rect (`element.getBoundingClientRect()`) dari puluhan item tepat setelah mutasi DOM, memicu forced synchronous layout secara rekursif selama 48ms (drop ke 18 FPS).

#### Rekayasa Solusi
1. **Dynamic Will-Change Lifecycle**: Menghapus `will-change` dari stylesheet statis. Elemen hanya menerima layer promotion saat event `pointerenter` atau `focus-visible`, dan dihapus via listener `animationend` / `pointerleave`.
2. **Transisi Native SPA via View Transitions API**: Menggantikan library JS FLIP dengan API platform browser, memangkas bundle sebesar 45 KB dan memindahkan seluruh koordinasi matriks visual ke Compositor Thread.
3. **CSS Containment**: Menerapkan `contain: layout paint` pada item grid agar mutasi internal tidak mencederai tree painting global.

#### Hasil Metrik Kinerja (Before vs After)

| Metrik | Arsitektur Awal (JS FLIP + Static will-change) | Arsitektur Baru (View Transitions + Containment) | Peningkatan |
| :--- | :--- | :--- | :--- |
| **GPU Memory Footprint** | 420 MB VRAM | 42 MB VRAM | **-90% Penurunan Memori** |
| **Interaction to Next Paint (INP)**| 210 ms (Poor) | 28 ms (Good) | **+86.6% Peningkatan Kecepatan** |
| **Frame Rate Selama Transisi** | 18 - 24 FPS (Janky) | 60 / 120 FPS Lock | **Animasi Tanpa Frame Drop** |
| **Vendor JS Payload** | 45 KB | 0 KB (Native Browser Engine API)| **-45 KB Total Bundle** |

---

### 9. Trade-offs: Analisis Keputusan Rekayasa

Setiap optimasi rendering memiliki implikasi tradeoffs:

```
                  [Karakteristik Optimasi Rendering]
                                   ▲
                                   │
                   (Tinggi)        │        (Tinggi)
             VRAM Consumption      │    Compositor Isolation
                                   │
       ◄───────────────────────────┼───────────────────────────►
      Main Thread Workload         │         Subpixel Quality
      (Tinggi: Reflow / Repaint)   │         (Penurunan: Blur effect)
                                   ▼
```

#### 1. Hardware Accelerated Layers (`transform: translateZ(0)` / `will-change`)
- **Keuntungan**: Membebaskan Main Thread. Animasi tidak terpengaruh oleh eksekusi blocking microtask JS.
- **Kerugian**: Menguras VRAM secara eksponensial. Promosi layer juga memutus **Subpixel Font Antialiasing** pada engine WebKit/Blink (teks berubah menjadi grayscale antialiasing yang terlihat sedikit lebih tipis dan buram saat layer bergerak).

#### 2. View Transitions API vs CSS Micro-Animations
- **Keuntungan**: Tidak butuh mapping koordinat manual. Menghubungkan state asinkronus multi-komponen secara deklaratif.
- **Kerugian**: Tidak semua versi browser lama mendukung (membutuhkan progressive enhancement). Snapshot visual adalah bitmap raster statis; elemen formulir seperti kursor teks atau input fokus di dalam transisi tidak dapat merespons input ketikan secara real-time selama durasi transisi berlangsung.

#### 3. Strict CSS Containment (`contain: strict` / `contain: content`)
- **Keuntungan**: Membatasi jangkauan style recalculation dan layout pass hanya pada sub-tree elemen tersebut.
- **Kerugian**: Memaksa elemen memiliki ukuran eksplisit atau formatting context yang kaku, mempersulit komponen fleksibel yang bergantung pada ukuran konten dinamis (*intrinsic sizing*).

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Penyalahgunaan Statis `will-change: transform`
```css
/* ANTI-PATTERN: Jangan pernah pasang will-change di class global terus-menerus */
.card-item {
  will-change: transform, opacity; /* Layer dialokasikan permanen di VRAM */
}
```
**Troubleshooting**:
Gunakan JavaScript lifecycle atau CSS trigger transien:
```css
/* BEST-PRACTICE */
.card-item {
  /* Biarkan pada flat layer */
}
.card-item:hover {
  will-change: transform; /* Layer baru dipromosikan saat ada indikasi interaksi user */
}
.card-item:not(:hover) {
  will-change: auto;
}
```

#### Kesalahan 2: Transisi pada Properti Dimensi Non-Composited
```css
/* ANTI-PATTERN: Memaksa Main Thread Layout recalculation pada setiap frame */
.drawer {
  transition: height 300ms ease;
  height: 0px;
}
.drawer.open {
  height: 400px; /* Reflow memicu layout tree recalculation di seluruh halaman */
}
```
**Troubleshooting**:
Ganti representasi dimensi dengan komposit `transform: scaleY()` atau struktur flex parent terisolasi:
```css
/* BEST-PRACTICE */
.drawer {
  transform: scaleY(0);
  transform-origin: top;
  transition: transform 300ms cubic-bezier(0.16, 1, 0.3, 1);
  contain: layout paint;
}
.drawer.open {
  transform: scaleY(1);
}
```

#### Kesalahan 3: Tabrakan Identitas `view-transition-name`
Menetapkan `view-transition-name: product-hero` ke lebih dari satu elemen yang terlihat di viewport secara bersamaan pada DOM baru.
- **Dampak Error**: View transition gagal total (langsung melakukan hard-swap tanpa transisi), dan console melempar exception:
  `DOMException: Duplicate view-transition-name: product-hero`.
- **Troubleshooting**: Pasang transition-name hanya pada satu instance unik yang sedang berinteraksi, dan bersihkan nama tersebut setelah transisi selesai.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis modul interaktif ke production:

- [ ] **Animasi Terbatas pada Compositor**: Pastikan hanya properti `transform`, `opacity`, dan subset `filter` yang dianimasikan dalam `@keyframes` atau `transition`.
- [ ] **Accessibility WCAG 2.2 Compliant**: Setiap animasi pergerakan wajib dibungkus dalam kueri `@media (prefers-reduced-motion: reduce)` yang meniadakan durasi atau mengubah translasi menjadi `opacity` murni.
- [ ] **Isolasi Containment**: Pasang `contain: layout paint` pada parent container dari elemen yang dianimasikan untuk mencegah layout leak.
- [ ] **Audit Alokasi Layer GPU**: Buka Chrome DevTools -> Tiga Titik -> More Tools -> **Layers**. Pastikan jumlah composited layer tidak bertambah secara liar saat scrolling atau hover.
- [ ] **Audit Frame Drops (HUD)**: Aktifkan Chrome DevTools -> Rendering -> Centang **Frame Rendering Stats**. Jalankan stress test; pastikan GPU frame rate stabil pada angka native layar (60Hz / 120Hz) dan drop frame < 1%.
- [ ] **Clean-up View Transition Names**: Pastikan atribut CSS inline `viewTransitionName` dihapus via `Promise.finally()` setelah `transition.finished` ter-resolve.

---

### 12. Hands-on Practice

Buat struktur file berikut pada direktori kerja Anda:

```
hands-on/
└── m02/
    ├── index.html
    ├── styles.css
    └── app.js
```

#### Langkah 1: Siapkan Skeleton Dokumen & CSS Terisolasi
Tuliskan berkas `hands-on/m02/index.html`:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Compositor Motion & View Transitions</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="app-header">
    <h1>Enterprise Motion Lab</h1>
    <div id="stats-hud" class="stats-badge">Main-Thread Status: Active</div>
  </header>

  <main id="app-viewport">
    <!-- View 1: Product Grid -->
    <section id="catalog-view" class="view-surface">
      <h2>Katalog Produk</h2>
      <div class="grid-container">
        <article class="product-card" id="card-101" data-id="101">
          <div class="image-wrapper">
            <img src="https://picsum.photos/id/1060/400/400" alt="Produk Kopi" class="product-thumb">
          </div>
          <div class="product-content">
            <h3>Espresso Blend Roaster</h3>
            <p>Biji kopi sangrai pilihan beraroma cokelat pekat.</p>
            <button class="action-btn">Lihat Detail</button>
          </div>
        </article>
      </div>
    </section>

    <!-- View 2: Product Detail (Hidden Secara Dinamis) -->
    <template id="detail-view-template">
      <section id="detail-view" class="view-surface">
        <button id="back-btn" class="action-btn secondary">&larr; Kembali ke Katalog</button>
        <div class="hero-detail">
          <div class="image-wrapper hero">
            <img src="https://picsum.photos/id/1060/800/800" alt="Produk Kopi Detail" class="product-hero-image">
          </div>
          <div class="hero-info">
            <h2>Espresso Blend Roaster</h2>
            <p class="lead-text">Deskripsi lengkap produk dengan interpolasi performa tinggi menggunakan compositor hardware-accelerated View Transitions API.</p>
            <div class="price-tag">IDR 145.000</div>
          </div>
        </div>
      </section>
    </template>
  </main>

  <script type="module" src="app.js"></script>
</body>
</html>
```

#### Langkah 2: Konstruksi CSS Compositor-Driven & View Transitions
Tuliskan berkas `hands-on/m02/styles.css`:

```css
:root {
  --color-bg: #0f172a;
  --color-surface: #1e293b;
  --color-text: #f8fafc;
  --color-accent: #38bdf8;
  
  --ease-spring: cubic-bezier(0.175, 0.885, 0.32, 1.275);
  --ease-standard: cubic-bezier(0.4, 0, 0.2, 1);
  --duration-motion: 400ms;
}

body {
  margin: 0;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: var(--color-bg);
  color: var(--color-text);
  overflow-x: hidden;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background-color: var(--color-surface);
}

.stats-badge {
  font-size: 0.75rem;
  background-color: #059669;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
}

.grid-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 2rem;
  padding: 2rem;
}

.product-card {
  background-color: var(--color-surface);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  contain: layout paint;
  /* Optimasi: Default Transform Layer */
  transform: translateZ(0);
  transition: transform var(--duration-motion) var(--ease-spring),
              box-shadow var(--duration-motion) var(--ease-standard);
}

.product-card:hover {
  transform: translateY(-6px) scale(1.01);
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
}

.image-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  overflow: hidden;
}

.image-wrapper.hero {
  aspect-ratio: 1 / 1;
  max-width: 450px;
}

.product-thumb, .product-hero-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.product-content, .hero-info {
  padding: 1.5rem;
}

.action-btn {
  background-color: var(--color-accent);
  color: #0f172a;
  font-weight: bold;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 6px;
  cursor: pointer;
  transform: translateZ(0);
  transition: filter 200ms ease;
}

.action-btn:hover {
  filter: brightness(1.15);
}

.hero-detail {
  display: flex;
  gap: 3rem;
  padding: 2rem;
  align-items: center;
}

/* View Transitions Deep-Dive Styling */
::view-transition-group(product-transition-layer) {
  animation-duration: var(--duration-motion);
  animation-timing-function: var(--ease-standard);
}

::view-transition-old(product-transition-layer),
::view-transition-new(product-transition-layer) {
  mix-blend-mode: normal;
  height: 100%;
  width: 100%;
}

/* Fallback Aksesibilitas */
@media (prefers-reduced-motion: reduce) {
  .product-card, .action-btn {
    transition: none !important;
    transform: none !important;
  }
  
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) {
    animation-duration: 0.01ms !important;
  }
}
```

#### Langkah 3: Implementasi Controller Script
Tuliskan berkas `hands-on/m02/app.js`:

```javascript
document.addEventListener('DOMContentLoaded', () => {
  const viewport = document.getElementById('app-viewport');
  const catalogView = document.getElementById('catalog-view');
  const detailTemplate = document.getElementById('detail-view-template');

  // Delegasi Event untuk Navigasi Maju (Catalog -> PDP)
  catalogView.addEventListener('click', async (e) => {
    const trigger = e.target.closest('.action-btn');
    if (!trigger) return;

    const card = trigger.closest('.product-card');
    const thumb = card.querySelector('.product-thumb');

    // Konfigurasi Dynamic Shared-Element Tag
    thumb.style.viewTransitionName = 'product-transition-layer';

    const renderPDP = () => {
      catalogView.style.display = 'none';
      const detailNode = detailTemplate.content.cloneNode(true);
      const heroImage = detailNode.querySelector('.product-hero-image');
      
      // Berikan name yang sama ke target DOM baru
      heroImage.style.viewTransitionName = 'product-transition-layer';
      viewport.appendChild(detailNode);
      bindBackButton();
    };

    // Eksekusi API Transisi
    if (!document.startViewTransition) {
      renderPDP();
    } else {
      const transition = document.startViewTransition(() => {
        renderPDP();
      });

      try {
        await transition.finished;
      } finally {
        // Pembersihan Transition Name
        const heroImage = document.querySelector('.product-hero-image');
        if (heroImage) heroImage.style.viewTransitionName = '';
        if (thumb) thumb.style.viewTransitionName = '';
      }
    }
  });

  // Delegasi Event untuk Navigasi Mundur (PDP -> Catalog)
  function bindBackButton() {
    const backBtn = document.getElementById('back-btn');
    if (!backBtn) return;

    backBtn.addEventListener('click', async () => {
      const detailView = document.getElementById('detail-view');
      const heroImage = detailView.querySelector('.product-hero-image');
      const thumb = catalogView.querySelector('.product-thumb');

      // Pasang name pada source kembali
      heroImage.style.viewTransitionName = 'product-transition-layer';

      const renderCatalog = () => {
        detailView.remove();
        catalogView.style.display = 'block';
        thumb.style.viewTransitionName = 'product-transition-layer';
      };

      if (!document.startViewTransition) {
        renderCatalog();
      } else {
        const transition = document.startViewTransition(() => {
          renderCatalog();
        });

        try {
          await transition.finished;
        } finally {
          if (thumb) thumb.style.viewTransitionName = '';
        }
      }
    });
  }
});
```

---

### 13. Exercise

#### Level Easy
Ubah berkas `styles.css` pada latihan di atas untuk menambahkan animasi `fade-in` berdurasi `200ms` pada teks deskripsi detail produk saat masuk ke layar tanpa memicu Main Thread Layout (hanya boleh menggunakan `opacity` dan compositor translate).
*Acceptance Criteria*:
- Teks tidak muncul mendadak.
- Audit *Performance Panel* menunjukkan 0 milidetik *Layout duration* saat teks beranimasi masuk.

#### Level Medium
Buat class utilitas JavaScript `PerformanceLayerProfiler` yang mendeteksi apakah `prefers-reduced-motion` aktif. Jika ya, hapus atribut `style.viewTransitionName` secara instan sebelum transisi dijalankan untuk mematikan interpolasi pergerakan.
*Acceptance Criteria*:
- Saat sistem operasi mengaktifkan "Reduce Motion", transisi halaman berganti seketika (hard swap atau crossfade murni tanpa morphing pergerakan posisi).
- Tidak ada console warning dari browser engine.

#### Level Hard
Modifikasi sistem `hands-on/m02` untuk mendukung list dinamis berisi 50 item yang di-generate via JavaScript loop. Implementasikan algoritma *dynamic layer cleanup*:
- Hanya elemen yang berada di dalam intersection viewport (`IntersectionObserver`) dan menerima event pointer kursor yang boleh mendapatkan optimasi GPU.
*Acceptance Criteria*:
- Melalui Chrome DevTools **Layers Panel**, total layer terpromosi tidak boleh lebih dari 5 layer pada saat bersamaan di seluruh dokumen, berapa pun total elemen DOM yang ada.

---

### 14. Challenge

Rancang arsitektur **Enterprise Multi-Stage Fluid Navigation Coordinator** dengan skenario berikut:
- **Konteks**: Anda membangun platform SaaS kolaborasi visual (seperti Figma/Miro web canvas). Pengguna dapat beralih antara "Grid Overview", "Infinite Board Canvas", dan "Properties Inspector Panel".
- **Problem Constraint**:
  1. Kanvas menggunakan rendering WebGL (`<canvas>`), sedangkan UI shell menggunakan DOM standard/HTML5.
  2. Transisi antara state board harus mulus tanpa mengorbankan framerate interaksi kanvas (harus terkunci di 60 FPS).
  3. Memory VRAM perangkat dibatasi maksimal 128 MB untuk seluruh layer browser tab guna mencegah crash pada perangkat laptop low-end enterprise.
- **Tugas Arsitektur**:
  - Tuliskan dokumen arsitektur (spesifikasi alur dan pseudo-kode orkestrator) yang memetakan bagaimana koordinasi antara `document.startViewTransition`, WebGL Context lifecycle, dan Dynamic CSS GPU Layer promotion dikelola.
  - Tentukan mekanisme graceful degradation jika GPU context hilang (`webglcontextlost`) di tengah transisi berlangsung.
  - *Zero instant solution*: Solusi harus memperhitungkan race-condition antara frame render canvas dan async DOM update callback.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Properti CSS manakah di bawah ini yang dieksekusi secara native pada Compositor Thread tanpa memicu siklus Layout maupun Paint ulang?
   - A. `width` dan `height`
   - B. `top` dan `left`
   - C. `transform` dan `opacity`
   - D. `margin` dan `padding`
   *(Jawaban: C. Hanya `transform` dan `opacity` yang dapat dimanipulasi secara penuh oleh compositor tanpa kalkulasi geometri DOM).*

2. Mengapa memasang `will-change: transform` pada semua elemen di stylesheet global dianggap sebagai anti-pattern berbahaya?
   - A. Menyebabkan browser melempar syntax error pada CSS.
   - B. Mengalokasikan composited layer permanen di VRAM untuk tiap elemen yang memicu Layer Explosion dan memory crash.
   - C. Menonaktifkan eksekusi JavaScript pada Main Thread.
   - D. Mematikan dukungan flexbox dan CSS Grid.
   *(Jawaban: B. Layer promotion memakan alokasi buffer memori GPU. Penggunaan masif menguras VRAM).*

3. Apa nama root pseudo-element yang dibuat oleh browser secara runtime saat `document.startViewTransition()` dipanggil?
   - A. `::view-transition-container`
   - B. `::view-transition`
   - C. `::transition-root`
   - D. `::view-port-transition`
   *(Jawaban: B. `::view-transition` adalah top-level pseudo-element yang menampung hierarki transisi).*

4. Media feature CSS apa yang wajib digunakan untuk mematuhi kriteria aksesibilitas vestibular WCAG 2.2 terkait animasi?
   - A. `@media (animation: disabled)`
   - B. `@media (prefers-contrast: high)`
   - C. `@media (prefers-reduced-motion: reduce)`
   - D. `@media (pointer: coarse)`
   *(Jawaban: C. `prefers-reduced-motion` mendeteksi konfigurasi sistem operasi pengguna yang sensitif terhadap motion).*

5. Apa dampak visual langsung terhadap tipografi teks (font) ketika sebuah elemen dipromosikan ke Hardware Accelerated Layer pada browser WebKit/Blink?
   - A. Teks berubah menjadi huruf kapital otomatis.
   - B. Ukuran font membesar 2 piksel.
   - C. Font Subpixel Anti-Aliasing dinonaktifkan dan beralih ke Grayscale Anti-Aliasing (terlihat sedikit lebih tipis).
   - D. Teks berkedip merah.
   *(Jawaban: C. Layer independen tidak dapat memadukan subpixel RGB stripe dengan background di belakangnya, sehingga engine mundur ke grayscale filtering).*

#### 5 Pertanyaan Intermediate
6. Dalam proses render engine Chromium, komponen manakah yang bertanggung jawab menerima Draw Quads dan mengirimkan instruksi grafis final ke Display Server OS?
   - A. Blink Main Thread
   - B. Chrome Compositor (`cc`)
   - C. Viz Service pada GPU Process
   - D. V8 Engine
   *(Jawaban: C. Viz menerima output quads dari cc layer tree dan mengomposisikannya ke hardware screen).*

7. Jika terjadi kondisi `DOMException: Duplicate view-transition-name: XYZ` saat menjalankan View Transitions API, apa yang sebenarnya terjadi pada rendering engine?
   - A. Memory GPU penuh sehingga alokasi ID gagal.
   - B. Dua elemen visual aktif di DOM target baru memiliki deklarasi `view-transition-name` yang identik secara simultan.
   - C. Transition name belum didaftarkan di HTTP header.
   - D. Browser tidak mendukung CSS Nesting.
   *(Jawaban: B. Spesifikasi View Transition mengharuskan tiap `view-transition-name` bersifat unik di dalam visual tree pada waktu render yang sama).*

8. Mengapa teknik animasi FLIP manual berbasis JavaScript (`getBoundingClientRect()`) berisiko memicu *Layout Thrashing* jika diterapkan pada banyak elemen secara bersamaan?
   - A. Karena JavaScript berjalan paralel dengan Compositor Thread.
   - B. Karena pembacaan properti geometri memaksa browser mengeksekusi Style Recalculation dan Layout seketika (*Forced Synchronous Layout*) di tengah siklus frame.
   - C. Karena operasi matriks 3D tidak didukung CPU.
   - D. Karena `requestAnimationFrame` membatasi pembacaan DOM maksimal 3 kali per detik.
   *(Jawaban: B. Membaca dimensi geometri setelah ada mutasi DOM memaksa Main Thread melakukan layout instan untuk mengembalikan nilai akurat).*

9. Apa fungsi dari deklarasi CSS `contain: layout paint` pada elemen container yang sering mengalami animasi internal?
   - A. Mempercepat koneksi network asset gambar.
   - B. Memastikan layout dan paint subtree diisolasi sehingga mutasi di dalamnya tidak memicu reflow pada elemen di luar container tersebut.
   - C. Memaksa elemen selalu berada di layer z-index paling atas.
   - D. Mengubah rendering model dokumen menjadi SVG canvas.
   *(Jawaban: B. Containment memberitahu engine bahwa boundary geometri internal terkunci, meminimalkan invalidation path).*

10. Pseudo-element `::view-transition-old(name)` secara visual merepresentasikan:
    - A. Elemen target setelah mutasi DOM selesai dilakukan.
    - B. Snapshot bitmap visual dari elemen sebelum mutasi DOM dijalankan.
    - C. Placeholder kosong untuk menahan layout reflow.
    - D. Indikator loading native engine browser.
    *(Jawaban: B. Old pseudo-element memegang tangkapan visual state awal sebelum callback mutasi mengeksekusi DOM baru).*

#### 3 Skenario Kasus Produksi
11. **Skenario Kasus 1**: Pada dashboard finansial dengan 200 komponen kartu metrik yang sering me-refresh data via WebSocket, developer mengeluhkan nilai Interaction to Next Paint (INP) yang sangat buruk (>500ms) saat kursor hover di atas grid kartu.
    - *Akar Masalah*: Kartu memiliki CSS `.card:hover { transform: translateY(-5px); }`, namun container induk tidak memiliki containment dan kartu memiliki border shadow dinamis yang belum terpromosi, memicu re-rastering area luas pada main thread.
    - *Pertanyaan*: Solusi refaktorisasi arsitektur CSS apa yang paling tepat tanpa menambah overhead memori GPU?
    - *Solusi Rekayasa*: Pasang `contain: layout paint` pada kartu, ganti box-shadow hover dinamis dengan pseudo-element `::after` yang menampung shadow terkomputasi sebelumnya dan cukup animasikan `opacity` pseudo-element tersebut via compositor, serta hindari layer promotion permanen.

12. **Skenario Kasus 2**: Sebuah aplikasi e-commerce SPA mengimplementasikan transisi halaman katalog ke detail menggunakan View Transitions API. Namun di perangkat Safari iOS terbaru, animasi transisi terlihat berkedip putih (*white flash*) selama 1 frame sebelum berpindah.
    - *Akar Masalah*: Callback di dalam `document.startViewTransition(async () => { ... })` menyelesaikan fetch data API secara lambat di dalam body callback, sehingga timeout rendering internal WebKit terlampaui dan engine merender snapshot kosong.
    - *Solusi Rekayasa*: Pisahkan data fetching dari DOM mutation lifecycle. Data harus di-fetch terlebih dahulu (pre-fetching); callback View Transition hanya boleh berisi sinkronisasi state DOM yang berjalan instan (< 16ms) tanpa ada network awaiting di dalamnya.

13. **Skenario Kasus 3**: Tim QA melaporkan bahwa animasi modal dialog pada aplikasi internal perusahaan memicu keluhan pusing dan mual dari pengguna dengan gangguan vestibular, namun penambahan `@media (prefers-reduced-motion)` sederhana merusak logika JavaScript yang menunggu event `transitionend`.
    - *Akar Masalah*: Menyetel `transition: none` menyebabkan event `transitionend` tidak pernah ditembakkan oleh engine browser, sehingga Promise/Callback JavaScript menggantung (*dangling promise*), menyebabkan UI modal membeku (freeze).
    - *Solusi Rekayasa*: Alih-alih `transition: none`, setel durasi transisi menjadi angka terkecil yang valid secara komputasi engine: `transition-duration: 0.001ms`. Browser tetap menembakkan event `transitionend` secara asinkron tanpa menahan eksekusi flow JS, sementara pergerakan fisik visual ditiadakan bagi user.

---

### 16. Summary

- **Separation of Concerns Engine**: Main Thread menangani dokumen dan business logic (DOM/Style/Layout/Paint), sedangkan Compositor Thread dan GPU Process (Viz) menangani orchestrasi pergerakan piksel dan rendering layer.
- **Efisiensi Hardware Acceleration**: Batasi animasi hanya pada `transform` dan `opacity`. Kelola layer GPU secara hati-hati; layer yang dialokasikan sembarangan memicu *Layer Explosion* dan degradasi performa memori VRAM drastis.
- **View Transitions API Paradigms**: Menyediakan mekanisme level-platform modern untuk melakukan *shared element transition* tanpa framework JS eksternal, dieksekusi secara mulus melalui pseudo-tree `::view-transition-*`.
- **Aksesibilitas adalah Kebutuhan Rekayasa Inti**: Selalu kombinasikan token animasi dengan `@media (prefers-reduced-motion: reduce)`. Pengabaian toleransi motion dapat mengakibatkan disorientasi fisik pada user dan kegagalan kepatuhan standar WCAG 2.2 Enterprise.