# Bab 07 Module 01: Compositor-Driven Animations, Motion Systems, & View Transitions

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Topik:** CSS Engine, Hardware Acceleration, Motion Systems, & Modern Transitions
* **Kode Modul:** CSS-ENG-0701
* **Tingkat Kesulitan:** Advanced / Staff-Level Engineering
* **Prasyarat:** DOM Tree & Render Tree Lifecycle, CSS Box Model, JavaScript Event Loop & Microtasks, Dasar GPU Rasterization.

---

## SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. Menganalisis alur eksekusi Chromium Rendering Pipeline (Parse $\rightarrow$ Style $\rightarrow$ Layout $\rightarrow$ Pre-Paint $\rightarrow$ Paint $\rightarrow$ Composite) dan mengidentifikasi pemicu jank pada Main Thread.
2. Mengisolasi animasi CSS dan Web Animations API (WAAPI) secara eksklusif ke Compositor Thread menggunakan properti terakselerasi GPU (`transform`, `opacity`, `filter`, `clip-path`).
3. Merancang Motion System skala enterprise berbasis CSS Custom Properties, Cubic-Bezier Curves tokens, dan spatial physics yang konsisten lintas platform.
4. Mengimplementasikan View Transitions API (Single-Page Application dan Multi-Page Application) dengan pseudo-element architecture (`::view-transition-*`) untuk transisi state yang mulus tanpa interupsi threading.
5. Mendeteksi dan memitigasi memory leaks pada Video RAM (VRAM) akibat layer promotion berlebih (*layer explosion*).
6. Mengintegrasikan audit rendering frame (Interaction to Next Paint / INP, Frame Drop) ke dalam pipeline observabilitas frontend.

---

## SEKSI 03 — MINDSET & MENTAL MODEL
### Main Thread vs. Compositor Thread
Mayoritas kegagalan performa animasi pada UI modern berakar dari kesalahpahaman mendasar: memperlakukan browser sebagai penampil grafis monolitik. Kenyataannya, arsitektur modern browser (Blink, Gecko, WebKit) membagi beban visual ke dalam minimal dua entitas thread runtime:
* **Main Thread:** Tempat JavaScript dieksekusi, DOM dimutasi, CSS di-resolve, Layout (Reflow) dihitung, dan Paint dikalkulasi menjadi display item lists. Ketika JavaScript mengeksekusi operasi berat (misal: JSON parsing besar atau rendering komponen kompleks), Main Thread akan terblokir (*starvation*).
* **Compositor Thread & Viz/GPU Process:** Berjalan paralel dan asinkron terhadap Main Thread. Bertanggung jawab memotong halaman menjadi lapisan-lapisan bitmap (*Layers/Tiles*), mengirimkannya ke GPU memory (VRAM), dan menggambar ulang posisi lapisan tersebut di layar setiap refresh cycle (misal: 60Hz = 16.6ms, 120Hz = 8.3ms).

```
[Mental Model: The Motion Factory]
Main Thread       = Pabrik Perancang (Merancang bentuk, menjahit kain, lambat jika sibuk)
Compositor/GPU    = Tim Pengantar & Proyektor (Hanya menggeser, memutar, dan menyinari transparansi slide)
```
Tugas Anda sebagai Staff Engineer bukan membuat animasi yang "indah secara visual", melainkan menyusun arsitektur CSS sedemikian rupa sehingga pekerjaan visual didelegasikan seluruhnya ke Compositor Thread setelah inisialisasi awal. Jika properti animasi menyentuh Layout (`width`, `margin`, `top`) atau Paint (`background-color`, `box-shadow`), Main Thread dipaksa bekerja pada setiap frame. Jika animasi murni Compositor (`transform`, `opacity`), frame rate tetap terkunci pada 60/120 FPS meskipun Main Thread sedang membeku total (*frozen*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Chromium Rendering Lifecycle & Fast Path Compositing

```
+---------------------------------------------------------------------------------------------------+
| MAIN THREAD                                                                                       |
|                                                                                                   |
|  +---------+     +---------+     +----------+     +-----------+     +---------+                   |
|  |  DOM    | --> | Style   | --> |  Layout  | --> | Pre-Paint | --> |  Paint  |                   |
|  | Mutate  |     | Compute |     | (Reflow) |     |  (Trees)  |     | (Record)|                   |
|  +---------+     +---------+     +----------+     +-----------+     +---------+                   |
|       ^                                                                  |                        |
|       | [Layout Invalidation Path: width, top, padding]                  | Display Item Lists     |
|       +------------------------------------------------------------------+                        |
|                                                                          v                        |
|                                                                    +-----------+                  |
|                                                                    |   Commit  |                  |
+--------------------------------------------------------------------|-----------|------------------+
                                                                     |   Sync    |
+--------------------------------------------------------------------v-----------|------------------+
| COMPOSITOR THREAD                                                  | (Tiles)   |                  |
|                                                                    +-----------+                  |
|                                                                          |                        |
|  +---------------------+                                                 v                        |
|  | Direct Input Events |                                           +-----------+                  |
|  |  (Pinch / Scroll)   |                                           |   Tiling  |                  |
|  +---------------------+                                           +-----------+                  |
|            |                                                             |                        |
|            v                                                             v                        |
|  +---------------------------------------------------------+       +-----------+                  |
|  | Compositor Animation Engine                             | ----> | Rasterize |                  |
|  | (transform / opacity updates bypass Main Thread totally)|       +-----------+                  |
|  +---------------------------------------------------------+             |                        |
+--------------------------------------------------------------------------|------------------------+
                                                                           | Quads
+--------------------------------------------------------------------------v------------------------+
| GPU PROCESS (Viz)                                                                                 |
|                                                                                                   |
|  +-----------------+      +-----------------------+      +--------------------+                   |
|  | Draw Quad Batch | ---> | GPU Command Buffer    | ---> | Display (Swap      |                   |
|  | Calculation     |      | (VRAM Primitive Draw) |      | Buffers / Screen)  |                   |
|  +-----------------+      +-----------------------+      +--------------------+                   |
+---------------------------------------------------------------------------------------------------+
```

### View Transitions State Machine Workflow

```
[State A: Halaman Aktif]
         |
         | document.startViewTransition(updateDOMCallback)
         v
[Browser Mengambil Screenshot State A]
   - Menghasilkan layer ::view-transition-old(root)
   - Membekukan rendering UI sementara
         |
         v
[Eksekusi updateDOMCallback()]
   - DOM dimutasi ke State B
   - Asinkron (menunggu promise resolve)
         |
         v
[Browser Mengambil State B Pasca-Mutasi]
   - Menghasilkan layer ::view-transition-new(root)
         |
         v
[Pseudo-Element Tree Ditancapkan ke Document Root]
   ::view-transition
   └── ::view-transition-group(root)
       └── ::view-transition-image-pair(root)
           ├── ::view-transition-old(root) (Cross-fade out / Transform out)
           └── ::view-transition-new(root) (Cross-fade in / Transform in)
         |
         v
[Compositor Thread Menganimasikan Layer Lama ke Layer Baru]
         |
         v
[Transisi Selesai -> Pseudo Elements Dihapus dari DOM]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Accelerated Compositing Pipeline
Ketika sebuah elemen dideklarasikan dengan animasi `transform: translate3d(0, 0, 0)` atau `will-change: transform`, browser mengevaluasi apakah elemen tersebut memenuhi syarat untuk dipromosikan menjadi **Composited Layer** (GraphicsLayer).
* **Paint Artifacts Isolation:** Elemen dipisahkan dari GraphicsLayer root. Paint record elemen tersebut diubah menjadi tekstur bitmap independen di memori GPU.
* **Property Trees:** Pipeline modern Blink menggunakan *Property Trees* (Transform Tree, Clip Tree, Effect Tree, Scroll Tree). Alih-alih menghitung ulang geometri node pada seluruh dokumen, update transform hanya mengubah matriks transformasi 4x4 pada satu node di Transform Tree.
* **Draw Quads:** Compositor memetakan layer menjadi kumpulan poligon segiempat (Draw Quads) yang merujuk pada tekstur GPU. Quads ini langsung dikirim ke GPU process via IPC channel tanpa memicu fase Layout dan Paint pada Main Thread.

### 2. View Transitions API Pseudo-Element Architecture
Saat `document.startViewTransition()` dipanggil, browser membangun pohon pseudo-element sementara di root document:

```
::view-transition
└─ ::view-transition-group(ident-name)
   └─ ::view-transition-image-pair(ident-name)
      ├─ ::view-transition-old(ident-name)  <-- Tagged visual snapshot lama
      └─ ::view-transition-new(ident-name)  <-- Live render stream status baru
```

* `::view-transition`: Mengisolasi viewport seluruh transisi, mencegah pointer event selama setup berlangsung jika dikonfigurasi.
* `::view-transition-group()`: Mengatur ukuran dan posisi geometris bounding box dari elemen yang ditransisikan. Browser secara otomatis menginterpolasi ukuran (`width`, `height`) dan transformasi posisi (`translate`) antara elemen lama dan baru di tingkat Compositor.
* `::view-transition-image-pair()`: Berperan sebagai wadah blending mode (secara default `isolation: isolate`) untuk old snapshot dan new snapshot.
* `::view-transition-old()` & `::view-transition-new()`: Merupakan representasi raster actual visual elements. Browser memperlakukan keduanya seperti elemen `<img>` yang memiliki `object-fit: contain` atau `100% 100%`. Transisi default adalah animasi `opacity` (cross-fade), namun dapat di-override menggunakan CSS keyframes standar.

### 3. Layer Promotion Mechanics & Will-Change Traps
Penggunaan `will-change: transform` memberi petunjuk (*hint*) kepada browser saat parse-time/layout-time untuk mempromosikan elemen ke GraphicsLayer-nya sendiri sebelum animasi berjalan.
* **Under-the-hood:** Alokasi backing store bitmap di GPU memory setara dengan: 
  $$\text{Memori (Bytes)} = \text{Lebar Element (px)} \times \text{Tinggi Element (px)} \times 4 \text{ (RGBA)}$$
* **Device Pixel Ratio (DPR) Factor:** Pada layar Retina/HiDPI ($DPR = 2$ atau $3$), formula dikalikan $DPR^2$. Elemen ukuran $1000 \times 1000$ px pada layar $DPR=3$ mengonsumsi $1000 \times 1000 \times 9 \times 4 = 36\text{ MB}$ VRAM hanya untuk satu layer.
* Jika digunakan serampangan pada ribuan elemen list (`* { will-change: transform; }`), browser akan mengalami **Layer Explosion**. VRAM habis (*out-of-memory thrashing*), memaksa compositing fall-back ke software mode di CPU, yang mengakibatkan penurunan performa drastis hingga frame-rate $< 10\text{ FPS}$.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. Matematika Interpolasi & Fisika Kurva Gerak
Animasi CSS non-linear digerakkan oleh parametric cubic Bézier curve, didefinisikan oleh empat titik kontrol: $P_0(0,0)$, $P_1(x_1, y_1)$, $P_2(x_2, y_2)$, dan $P_3(1,1)$. Persamaan koordinatnya adalah:

$$B(t) = (1-t)^3 P_0 + 3(1-t)^2 t P_1 + 3(1-t) t^2 P_2 + t^3 P_3, \quad t \in [0, 1]$$

Karena $P_0$ selalu $(0,0)$ dan $P_3$ selalu $(1,1)$, percepatan waktu $x$ dan perubahan nilai $y$ direpresentasikan oleh:

$$x(t) = 3(1-t)^2 t x_1 + 3(1-t) t^2 x_2 + t^3$$
$$y(t) = 3(1-t)^2 t y_1 + 3(1-t) t^2 y_2 + t^3$$

Untuk menghitung progress animasi $y$ pada titik waktu $x$, browser harus menyelesaikan persamaan polinomial $x(t) - x = 0$ untuk menemukan nilai parameter $t$ menggunakan algoritma numerik (seperti Newton-Raphson iteration), lalu menyubstitusikan $t$ ke fungsi $y(t)$.
* Kurva mekanis kaku (linear) terasa tidak natural bagi mata manusia.
* Kurva natural meniru hambatan fisik: **Deceleration** (in-out atau pure ease-out dengan control point melengkung tajam di awal) memberikan ilusi massa yang masuk ke viewport dengan momentum nyata, lalu melambat secara elastis.

### 2. Standarisasi Motion System Skala Enterprise
Motion System kelas enterprise tidak memperbolehkan engineer menuliskan arbitrary `transition: all 0.3s ease`. Motion System harus didasarkan pada tiga pilar:
* **Durasi Adaptif Berbasis Jarak (Spatial Scale):** Objek yang berpindah jarak kecil (misal: dropdown menu $20\text{px}$) membutuhkan durasi lebih singkat ($150\text{ms}$) dibanding elemen yang melintasi seluruh viewport ($400\text{ms}$), guna menjaga kecepatan konstan (*perceptual velocity*).
* **Token Timing Bezier Berdasarkan Semantik:**
  * *Entrance (Incoming):* Objek masuk viewport $\rightarrow$ `ease-out` (mulai cepat, berhenti perlahan). Pengguna ingin konten segera terlihat.
  * *Exit (Outgoing):* Objek keluar viewport $\rightarrow$ `ease-in` (mulai perlahan, akselerasi keluar). Pengguna tidak perlu menunggu elemen hilang.
  * *Standard/Persistent:* Objek berubah state di dalam viewport $\rightarrow$ `ease-in-out` (asimetris).
* **Aksesibilitas (Vestibular Disorders):** Implementasi wajib mendengarkan media query `@media (prefers-reduced-motion: reduce)`. Pengurangan gerak bukan berarti mematikan transisi sepenuhnya, melainkan mentransformasikan gerak spasial translasi/rotasi ekstrem menjadi transisi opasitas murni (*instant cross-fade*).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi sistem token motion terpusat, pengoptimalan layer promotion menggunakan CSS murni, dan demonstrasi eksekusi Compositor Thread.

```css
/* ==========================================================================
   1. ENTERPRISE MOTION SYSTEM DESIGN TOKENS
   ========================================================================== */
:root {
  /* Motion Primitives: Physics-based Cubic Bezier curves */
  --ease-standard: cubic-bezier(0.2, 0.0, 0.0, 1.0);     /* Natural material movement */
  --ease-decelerate: cubic-bezier(0.0, 0.0, 0.2, 1.0);   /* Incoming elements */
  --ease-accelerate: cubic-bezier(0.3, 0.0, 1.0, 1.0);   /* Exiting elements */
  --ease-spring-snappy: cubic-bezier(0.175, 0.885, 0.32, 1.15); /* Micro-interactions */

  /* Temporal Primitives */
  --duration-inst: 100ms;
  --duration-fast: 150ms;
  --duration-base: 250ms;
  --duration-deliberate: 400ms;
}

/* ==========================================================================
   2. HARDWARE ACCELERATED COMPONENT
   ========================================================================== */
.card-primitive {
  /* Isolasi layer konteks rendering agar cat ulang child tidak bocor keluar */
  contain: layout style paint;
  position: relative;
  width: 320px;
  height: 200px;
  background-color: #1a1a24;
  border-radius: 8px;
  cursor: pointer;

  /* Composite property transformation: ONLY transform & opacity */
  transition: transform var(--duration-base) var(--ease-standard),
              opacity var(--duration-fast) var(--ease-standard);

  /* Hindari will-change statis di sini untuk mencegah layer permanent allocation */
}

/* Terapkan will-change hanya saat ada niat interaksi pengguna (Hover/Focus) */
.card-primitive:hover {
  will-change: transform;
}

.card-primitive:active {
  transform: scale3d(0.96, 0.96, 1);
  transition-duration: var(--duration-inst);
}

/* Isolasi visual effect (Shadow) menggunakan psuedo-element composite layer 
   Bukan menganimasikan box-shadow secara langsung (yang memicu Paint) */
.card-primitive::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  box-shadow: 0 12px 24px -4px rgba(0, 0, 0, 0.5);
  opacity: 0;
  transition: opacity var(--duration-base) var(--ease-standard);
  pointer-events: none;
}

.card-primitive:hover::after {
  opacity: 1;
}

.card-primitive:hover {
  transform: translate3d(0, -4px, 0);
}

/* ==========================================================================
   3. ACCESSIBILITY OVERRIDE (CRITICAL)
   ========================================================================== */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 6–10:** Mendefinisikan kurva polinomial Bézier semantik. Kurva `--ease-standard` ($0.2, 0.0, 0.0, 1.0$) memiliki akselerasi awal agresif dan pengereman panjang, meniadakan kesan artifisial dari bawaan browser (`ease`).
* **Baris 20:** `contain: layout style paint;` secara tegas mengisolasi subtree DOM elemen dari Global Layout Tree. Browser diinstruksikan bahwa perubahan di dalam elemen ini tidak akan pernah mempengaruhi posisi layout elemen di luarnya.
* **Baris 27–28:** Properti transisi dibatasi secara eksplisit pada `transform` dan `opacity`. Jangan pernah menggunakan `transition: all`. Menuliskan `all` memaksa Compositor terus memeriksa properti non-composited selama interpolasi.
* **Baris 33–35:** Strategi alokasi dinamis `will-change`. Elemen tidak dipromosikan ke GraphicsLayer secara permanen sejak load halaman. Promosi layer hanya terjadi sesaat sebelum animasi dijalankan (ketika pointer melayang di atas target), menghemat alokasi VRAM secara signifikan.
* **Baris 38:** `scale3d(0.96, 0.96, 1)`. Menggunakan format 3D memaksa matriks transformasi 4x4 dieksekusi langsung oleh GPU matrix register, mencegah fallback interpolasi 2D matrix di beberapa versi WebKit lama.
* **Baris 43–57:** Desain arsitektural untuk performa: Animasi `box-shadow` murni memicu Layout/Paint pipeline pada setiap frame. Solusinya, buat elemen bayangan di `::after` dengan render status bitmap pre-baked, lalu animasikan nilai `opacity` (hanya Compositor yang bekerja).
* **Baris 63–72:** Pola `@media (prefers-reduced-motion: reduce)`. Penggunaan durasi `0.01ms` (alih-alih `0s`) merupakan teknik hardening browser rendering engine: transisi secara teknis tetap dieksekusi secara instan sehingga event JavaScript seperti `transitionend` atau `animationend` tetap terpicu dan tidak merusak logika alur aplikasi Anda.

---

## SEKSI 09 — STUDI KASUS NYATA
### Transisi Kompleks Media Player & Detail View pada Platform SaaS Streaming
* **Konteks:** Tim Engineering di platform streaming media enterprise menghadapi masalah performa fatal: Ketika pengguna beralih dari mode *List Video* ke mode *Expanded Detail Player*, halaman mengalami jank parah. 
* **Metrik Awal:** 
  * Interaction to Next Paint (INP): $380\text{ms}$ (Rating: Poor).
  * Frame Drop: $48\%$ frame hilang pada perangkat kelas menengah (CPU throttle 4x).
  * VRAM Overhead: $420\text{ MB}$ pada browser tab karena developer mempromosikan seluruh card dengan `will-change: transform`.
* **Akar Masalah:**
  1. Elemen video mini diubah ukurannya menggunakan transisi CSS langsung pada properti `width`, `height`, dan `top` untuk mengisi layar. Hal ini memaksa Main Thread melakukan layouting ulang (Reflow) seluruh struktur dom di setiap frame (60 kali per detik).
  2. Thumbnail gambar dan teks di-rerender secara bersamaan oleh framework SPA (React) di Main Thread saat transisi berjalan, memblokir thread rendering Compositor untuk menerima instruksi commit.
* **Solusi Arsitektural:**
  1. Migrasi perpindahan screen ke **View Transitions API** dengan nama transisi terisolasi (`view-transition-name`).
  2. Implementasi **FLIP (First, Last, Invert, Play)** berbasis Transform Tree untuk elemen yang belum mendukung native View Transitions API.
  3. Mengisolasi decoding gambar dengan `decoding="async"` dan mengamankan layer promo dengan *Just-In-Time layer teardown*.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Arsitektur aplikasi multi-view terakselerasi penuh dengan fallback FLIP manual dan integrasi View Transitions API native.

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Compositor & View Transitions</title>
  <style>
    /* ====================================================================
       1. SYSTEM ARCHITECTURE & RESET
       ==================================================================== */
    :root {
      --motion-timing-fluid: cubic-bezier(0.16, 1, 0.3, 1);
      --duration-page: 350ms;
    }

    body {
      margin: 0;
      background: #090a0f;
      color: #f1f2f6;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      overflow-x: hidden;
    }

    /* ====================================================================
       2. VIEW TRANSITIONS API INFRASTRUCTURE
       ==================================================================== */
    /* Berikan nama transisi unik pada elemen persisten */
    .player-surface {
      view-transition-name: active-player;
    }

    .player-meta {
      view-transition-name: active-meta;
    }

    /* Kustomisasi root transition layer agar tidak menggunakan cross-fade default */
    ::view-transition-group(active-player) {
      animation-duration: var(--duration-page);
      animation-timing-function: var(--motion-timing-fluid);
    }

    ::view-transition-old(active-player),
    ::view-transition-new(active-player) {
      /* Mencegah snapshot scaling artifacts */
      height: 100%;
      width: 100%;
      object-fit: cover;
    }

    ::view-transition-old(root) {
      animation: var(--duration-page) var(--motion-timing-fluid) both fade-out;
    }

    ::view-transition-new(root) {
      animation: var(--duration-page) var(--motion-timing-fluid) both fade-in;
    }

    @keyframes fade-out {
      from { opacity: 1; }
      to { opacity: 0; }
    }

    @keyframes fade-in {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    /* ====================================================================
       3. VIEW LAYOUTS
       ==================================================================== */
    .gallery-view {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 24px;
      padding: 32px;
    }

    .card {
      background: #141622;
      border-radius: 12px;
      overflow: hidden;
      cursor: pointer;
      contain: paint;
    }

    .thumbnail {
      width: 100%;
      aspect-ratio: 16 / 9;
      background-size: cover;
      background-position: center;
      background-color: #23273a;
    }

    .card-body {
      padding: 16px;
    }

    /* Detail View Overlay */
    .detail-view {
      display: flex;
      flex-direction: column;
      min-height: 100vh;
      padding: 48px;
      box-sizing: border-box;
    }

    .detail-view .player-surface {
      width: 100%;
      max-width: 900px;
      aspect-ratio: 16 / 9;
      border-radius: 16px;
      box-shadow: 0 24px 48px -12px rgba(0, 0, 0, 0.7);
    }

    .back-btn {
      align-self: flex-start;
      margin-bottom: 24px;
      background: #23273a;
      border: none;
      color: white;
      padding: 10px 20px;
      border-radius: 6px;
      cursor: pointer;
    }

    /* Utility state */
    .hidden {
      display: none !important;
    }
  </style>
</head>
<body>

  <!-- Dynamic SPA View Container -->
  <main id="app-viewport">
    <div id="gallery" class="gallery-view">
      <article class="card" data-id="stream-1" onclick="navigateToDetail('stream-1')">
        <div class="thumbnail player-surface" style="background-image: url('https://picsum.photos/seed/tech/800/450');"></div>
        <div class="card-body player-meta">
          <h3>Architecting Zero-Jank Interfaces</h3>
          <p>Compositor Pipeline & Layer Optimization</p>
        </div>
      </article>
      <!-- Additional elements omitted for brevity -->
    </div>

    <div id="detail" class="detail-view hidden">
      <button class="back-btn" onclick="navigateToGallery()">← Kembali ke Katalog</button>
      <div id="detail-video-container" class="thumbnail player-surface"></div>
      <div class="player-meta">
        <h1 id="detail-title">Architecting Zero-Jank Interfaces</h1>
        <p>Deep dive materi rendering engine dengan zero main-thread blockage.</p>
      </div>
    </div>
  </main>

  <script>
    // ========================================================================
    // 4. TRANSITION ORCHESTRATOR CLASS (Production Grade)
    // ========================================================================
    class MotionNavigator {
      constructor() {
        this.galleryView = document.getElementById('gallery');
        this.detailView = document.getElementById('detail');
        this.detailContainer = document.getElementById('detail-video-container');
        this.isTransitioning = false;
      }

      async transitionView(mutationCallback) {
        if (this.isTransitioning) return;
        this.isTransitioning = true;

        // Cek dukungan asli browser terhadap View Transitions API
        if (!document.startViewTransition) {
          console.warn('View Transitions API unsupported. Falling back to discrete DOM mutation.');
          mutationCallback();
          this.isTransitioning = false;
          return;
        }

        try {
          const transition = document.startViewTransition(() => {
            mutationCallback();
          });

          // Tunggu hingga Compositor Thread siap mengeksekusi animasi
          await transition.ready;
        } catch (error) {
          console.error('Transition engine failed:', error);
          mutationCallback();
        } finally {
          this.isTransitioning = false;
        }
      }

      toDetail(streamId) {
        this.transitionView(() => {
          this.galleryView.classList.add('hidden');
          this.detailContainer.style.backgroundImage = "url('https://picsum.photos/seed/tech/800/450')";
          this.detailView.classList.remove('hidden');
        });
      }

      toGallery() {
        this.transitionView(() => {
          this.detailView.classList.add('hidden');
          this.galleryView.classList.remove('hidden');
        });
      }
    }

    const navigatorInstance = new MotionNavigator();

    function navigateToDetail(id) {
      navigatorInstance.toDetail(id);
    }

    function navigateToGallery() {
      navigatorInstance.toGallery();
    }
  </script>
</body>
</html>
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Evaluasi | Animasi Main Thread (`width`, `margin`, `top`) | Compositor-Driven Animation (`transform`, `opacity`) | FLIP Manual Technique (JS Web Animations API) | Native View Transitions API (`startViewTransition`) |
| :--- | :--- | :--- | :--- | :--- |
| **Pemicu Lifecycle** | Layout $\rightarrow$ Pre-Paint $\rightarrow$ Paint $\rightarrow$ Composite | Composite Only | Pre-Paint $\rightarrow$ Composite (Pasca First/Last calc) | Internal Compositor Snapshot Matching |
| **Resistensi Main Thread Jank** | Sangat Buruk (Jank instan jika JS sibuk) | Mutlak (Frame tetap 60/120 FPS saat CPU 100%) | Parsial (Hanya lancar setelah perhitungan FLIP selesai) | Mutlak (Animasi berjalan independen pasca state-capture) |
| **Konsumsi Memori VRAM** | Sangat Rendah (Tidak ada alokasi layer khusus) | Sedang - Tinggi (Membutuhkan Backing Store) | Sedang (Alokasi dinamis sementara) | Terkendali (Layer otomatis dihapus pasca transisi) |
| **Kompleksitas Kode** | Sangat Sederhana | Sederhana - Menengah | Sangat Tinggi (Kalkulasi `getBoundingClientRect` manual) | Minimal (Deklaratif via CSS dan 1 method JS) |
| **Fleksibilitas Desain** | Bebas (Dapat mengubah reflow text wrap) | Terbatas pada transformasi geometri visual | Sangat Tinggi untuk elemen single DOM | Sangat Tinggi bahkan untuk pergantian Document Dokumen Luar (MPA) |
| **Dukungan Browser (2024)** | $100\%$ | $100\%$ | $98\%$ | Modern Chromium, Safari 18+, Gecko (Dalam Pengembangan) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Subpixel Text Blurring Phenomenon
* **Masalah:** Saat mengaplikasikan `transform: scale()` atau `translate3d()` dengan floating point (misal: `translate(10.5px, 20.4px)`), teks di dalam layer terlihat buram (*fuzzy/blurry*).
* **Mekanisme Penyebab:** Elemen dipromosikan menjadi bitmap tekstur tetap. GPU merasterisasi teks pada skala awal $1\times$. Ketika di-scale up atau diposisikan di antara grid subpixel fisik layar, GPU melakukan interpolasi bilinear pada tekstur raster tersebut, bukan me-render ulang vektor font (karena teks tidak melalui tahapan Paint ulang).
* **Mitigasi:**
  Hindari transformasi non-integer. Gunakan `round(up, ...)` atau bulatkan via CSS math:
  ```css
  /* Pembulatan nilai koordinat */
  transform: translate3d(round(var(--tx), 1px), round(var(--ty), 1px), 0);
  ```
  Untuk skala, render elemen pada ukuran visual terbesarnya menggunakan font size murni, lalu gunakan `transform: scale()` ke bawah (downscale) untuk mengecilkan ukuran awal, alih-alih melakukan *upscaling*.

### 2. Stacking Context & Clipping Leaks
* **Masalah:** Elemen anak dengan `position: fixed` tiba-tiba berperilaku seperti `position: absolute` dan terpotong oleh parent container.
* **Mekanisme Penyebab:** Berdasarkan CSS Specification, properti seperti `transform`, `will-change`, `contain: paint`, atau `filter` yang memiliki nilai non-default akan menciptakan **Local Stacking Context** dan **Containing Block baru** untuk elemen berkategori `fixed` dan `absolute`. Elemen `fixed` tidak lagi mengacu pada root Viewport dokumen.
* **Mitigasi:** Pisahkan komponen modal, toast, dan overlay keluar dari containment hierarchy elemen yang dianimasikan (gunakan Native HTML `<dialog>` atau React/Vue Portals langsung di bawah `<body>`).

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan `transition: all`
```css
/* FATAL: Menghancurkan performa dan memicu layout/paint pass pada ratusan atribut */
.bad-practice {
  transition: all 0.3s ease;
}

/* BENAR: Targetkan strictly compositor-promoted properties */
.good-practice {
  transition-property: transform, opacity;
  transition-duration: 250ms;
  transition-timing-function: cubic-bezier(0.2, 0.0, 0, 1);
}
```

### 2. Animasi Height Otomatis (The `height: auto` Trap)
```css
/* SALAH: Memicu Reflow menyeluruh pada setiap frame */
.accordion-content {
  height: 0;
  overflow: hidden;
  transition: height 0.3s ease-out;
}
.accordion-content.expanded {
  height: 500px; /* Nilai magic arbitrer */
}

/* BENAR: Menggunakan scaleY atau Grid 0fr -> 1