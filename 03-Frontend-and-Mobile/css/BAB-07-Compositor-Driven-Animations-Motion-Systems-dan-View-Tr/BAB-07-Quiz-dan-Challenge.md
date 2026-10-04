# BAB 07: Quiz, Challenge, & Knowledge Check
**Compositor-Driven Animations, Motion Systems, dan View Transitions**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Separasi Thread Arsitektur Rendering Engine:**
   Jelaskan secara mendalam bagaimana Chromium (Blink + V8 + cc) memproses properti animasi yang bersifat *compositor-driven* (seperti `transform` dan `opacity`) dibandingkan dengan properti yang memicu siklus *Paint* atau *Layout* (seperti `top`, `width`, atau `box-shadow`). Mengapa modifikasi *composited property* menjamin kelancaran 60/120 FPS meskipun Main Thread sedang diblokir oleh eksekusi JavaScript yang intensif?

2. **Topologi Pseudo-Element View Transitions API:**
   Uraikan hirarki dan pohon *pseudo-element* yang dibuat oleh browser secara runtime saat memanggil `document.startViewTransition()`:
   ```text
   ::view-transition
   └── ::view-transition-group(name)
       └── ::view-transition-image-pair(name)
           ├── ::view-transition-old(name)
           └── ::view-transition-new(name)
   ```
   Jelaskan peran spesifik dari masing-masing node di atas, format tangkapan visual (*rasterized snapshot* vs *live DOM*), serta bagaimana browser menginterpolasi ukuran (bounding box) dan posisi antar *state*.

3. **Motion Systems: Bézier Curve vs. Spring Dynamics:**
   Dalam perancangan sistem gerak tingkat enterprise, bandingkan karakteristik matematis dan perseptual antara interpolasi parametrik berbasis waktu (`cubic-bezier(x1, y1, x2, y2)`) dengan simulasi fisika berbasis pegas (*spring-physics*: mass, stiffness, damping). Mengapa animasi berbasis waktu kerap terkesan "sintetik" ketika menangani interupsi interaksi pengguna (misal: *mid-gesture gesture cancel*), dan bagaimana *spring systems* menyelesaikannya?

4. **Biaya Nyata Properti `will-change`:**
   Meskipun `will-change: transform` sering digunakan untuk mengeliminasi latensi inisiasi animasi, jelaskan konsekuensi negatif terhadap arsitektur memori GPU (*VRAM footprint*), *layer creation overhead*, dan resiko *compositing layer explosion*. Kapan promosi layer harus dibatalkan (di-deregister)?

5. **Aksesibilitas Kinestetik (`prefers-reduced-motion`):**
   Jelaskan batasan dan kesalahan konsepsi umum dalam mengimplementasikan `@media (prefers-reduced-motion: reduce)`. Mengapa aturan global seperti `* { animation: none !important; transition: none !important; }` dianggap merusak aksesibilitas dan fungsionalitas UI, serta bagaimana strategi adaptasi gerak spasial non-vestibular yang benar?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Sub-Pixel Text Degradation & Layer Promotion:**
   Saat sebuah container teks dipromosikan menjadi *Hardware-Accelerated Compositing Layer* (baik menggunakan `will-change: transform` atau `transform: translateZ(0)`), sering kali teks tampak buram (*blurry*) atau kehilangan ketebalan tipografinya secara tiba-tiba. Analisis mengapa mekanisme *LCD subpixel anti-aliasing* (ClearType/CoreText) dinonaktifkan oleh rasterizer engine dan beralih ke *greyscale anti-aliasing* pada composited layers, serta bagaimana cara mengatasinya tanpa memicu layout shift.

2. **Exception Handling & Lifecycle Rollback pada `startViewTransition`:**
   Perhatikan siklus hidup asinkron berikut:
   ```javascript
   const transition = document.startViewTransition(async () => {
     const data = await fetchCriticalData();
     updateDOMState(data);
   });
   ```
   Apa yang terjadi secara internal pada rendering engine jika `fetchCriticalData()` melempar *unhandled network rejection*? Bagaimana status pohon DOM saat itu, bagaimana nasib snapshot visual yang telah dibekukan (*frozen*), dan bagaimana cara memprogram penanganan error agar transisi visual tidak "membeku" (*hang*) di layar pengguna?

3. **Layer Squashing vs. Memory Overhead:**
   Dalam arsitektur pipeline Compositor Chrome (`cc`), jelaskan apa yang dimaksud dengan fenomena **Layer Squashing** dan **Overlapping Composited Layers**. Bagaimana dua elemen yang saling tumpang-tindih (overlap) di mana salah satu elemen memiliki promosi layer paksa dapat memicu terciptanya *unintended stacking contexts* dan melipatgandakan alokasi memori tekstur di GPU?

4. **Dynamic Name Collision pada View Transitions:**
   Spesifikasi View Transitions API mensyaratkan bahwa `view-transition-name` harus unik secara global pada satu dokumen di satu frame yang sama. Jelaskan skenario di mana duplikasi identitas ini dapat terjadi secara tidak sengaja pada aplikasi berbasis komponen dinamis (misal: manipulasi array state di React/Vue/Svelte), apa perilaku default browser saat kondisi ini terdeteksi (*transition skip/abort behavior*), dan bagaimana pola arsitektural untuk sanitasi identitas nama transisi tersebut.

5. **Layout Thrashing yang Tersembunyi (Hidden Reflows) dalam Motion Loops:**
   Ketika melakukan implementasi animasi *pan-and-drag* kustom berbasis Pointer Events, seorang developer mengaplikasikan transformasi CSS secara langsung ke elemen sambil membaca metrik posisi:
   ```javascript
   function onPointerMove(e) {
     element.style.transform = `translate3d(${e.clientX}px, ${e.clientY}px, 0)`;
     const rect = element.getBoundingClientRect(); // Analisis baris ini
     adjustBoundaryCollisions(rect);
   }
   ```
   Jelaskan secara mendalam mengapa kode di atas merusak siklus frame rendering (*Forced Synchronous Layout*) meskipun properti yang dimodifikasi adalah `transform`, dan restrukturisasi kode tersebut menggunakan *Compositor Worklet* atau pemisahan siklus baca/tulis (*read/write batching*).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Investigasi Crash Browser (OOM) pada Infinite Masonry Grid
Sebuah aplikasi e-commerce otomotif global memiliki halaman katalog *infinite scroll* dengan ribuan kartu produk yang memuat gambar beresolusi tinggi, badge harga, dan deskripsi teknis. Untuk memberikan interaksi yang responsif, tim UI mengaplikasikan CSS berikut secara global pada setiap kartu:
```css
.catalog-card {
  will-change: transform, opacity, box-shadow;
  transition: transform 0.3s cubic-bezier(0.2, 0, 0, 1), box-shadow 0.3s ease;
}
.catalog-card:hover {
  transform: translateY(-8px) scale(1.02);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.2);
}
```
**Dampak Insiden:**
Pada perangkat Android low-to-mid end dan tablet, aplikasi mengalami *hard crash* (tab browser memuat ulang secara tiba-tiba atau menampilkan *black screens*) setelah pengguna melakukan scrolling melewati 150–200 item. Main Thread CPU tercatat idle, namun penggunaan memori grafis (*GPU VRAM*) meroket hingga batas limitasi sistem operasi.

* **Pertanyaan Diagnostik:**
  1. Identifikasi akar penyebab masalah (*root cause*) struktural dari crash tersebut berdasarkan arsitektur alokasi memori rendering engine.
  2. Gunakan tooling profiling Chrome DevTools apa saja untuk membuktikan hipotesis Anda secara kuantitatif?
  3. Rancang arsitektur refaktorisasi CSS dan teknik aktivasi layer berbasis lifecycle (just-in-time promotion) yang mempertahankan estetika interaksi mikro namun menurunkan konsumsi VRAM hingga 90%.

---

### Skenario B: Race Condition dan Visual Tearing pada Real-Time Dashboard (SPA)
Sebuah platform analitik finansial memuat dashboard metrik transaksi secara real-time yang menerima *high-frequency delta updates* via WebSocket (hingga 20 mutasi state per detik). Aplikasi tersebut mengadopsi Single-Page Application (SPA) View Transitions API untuk menganimasikan perubahan tab visual antar dashboard:
```javascript
function switchDashboardTab(tabId) {
  document.startViewTransition(async () => {
    renderTabUI(tabId);
  });
}

// WebSocket handler yang berjalan secara konkuren di Main Thread:
socket.on('metric_update', (payload) => {
  mutateMetricDOMNodes(payload);
});
```
**Dampak Insiden:**
Sering kali saat perpindahan tab terjadi bertepatan dengan lonjakan data transaksi, visual animasi mengalami *tearing*, snapshot tab lama menangkap fragmen dari data tab baru yang belum selesai dirender, atau transisi selesai seketika (*skip*) tanpa animasi. Pada konsol browser muncul peringatan bahwa transisi diaborsi.

* **Pertanyaan Diagnostik:**
  1. Bedah secara kronologis *race condition* yang terjadi antara siklus mutasi DOM oleh WebSocket callback dengan fase tangkapan visual (*Capture Old -> Update Callback Execution -> Capture New*) pada View Transitions API.
  2. Mengapa mutasi DOM di luar kendali callback transisi merusak integritas *snapshot rendering* browser?
  3. Rancang sebuah *State Synchronization Gate* (arsitektur antrean atau pembatasan mutasi berbasis promise lifecycle) untuk mengisolasi mutasi background DOM tanpa mengorbankan integritas data analitik finansial.

---

### Skenario C: Cross-Platform Enterprise Design System & Fallback Strategy
Anda adalah Lead UI Architect untuk aplikasi perbankan digital yang wajib berjalan di beragam lingkungan: Chromium modern (desktop & mobile), Safari (WebKit) dengan dukungan View Transitions parsial, dan browser legacy non-supporting. Desain mensyaratkan interaksi *Shared Element Transition* yang kompleks: ketika pengguna mengklik kartu transaksi di riwayat pembayaran, kartu tersebut harus membesar (*expand*) secara kontinu menjadi halaman detail transaksi secara spasial.

**Kendala Arsitektural:**
1. Anda dilarang memuat library animasi pihak ketiga eksternal seperti Framer Motion atau GSAP untuk membatasi ukuran initial bundle di bawah 50KB.
2. Anda harus menggunakan satu abstraksi kode yang sama pada layer komponen.
3. Transisi tidak boleh menghasilkan pergeseran visual (*visual jank*) dan wajib mendukung perangkat dengan refresh rate tinggi (90Hz/120Hz ProMotion).

* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda merancang pola arsitektural *Progressive Enhancement* untuk Motion System ini?
  2. Implementasikan teknik fallback komputasi spasial menggunakan pola FLIP (*First, Last, Invert, Play*) murni native berbasis CSS Transitions / Web Animations API (WAAPI) ketika `document.startViewTransition` tidak terdefinisi di browser target.
  3. Bagaimana memetakan design tokens animasi (durasi, kurva kelengkungan) agar dapat digunakan secara seragam oleh CSS native, pseudo-elements View Transition, maupun JavaScript WAAPI fallback?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Shared Element Modal & Motion Engine

#### Problem Statement
Rancang dan bangun sistem interaksi mikro dan navigasi makro untuk komponen **"Product Gallery to Fullscreen Viewer"** yang sepenuhnya ditenagai oleh *Compositor Thread* dan *View Transitions API*. Sistem ini harus mempertahankan rendering rate stabil 60 FPS pada monitor 60Hz dan 120 FPS pada display high-refresh-rate, tanpa mengorbankan memori perangkat seluler.

#### Requirements
1. **Design Tokens & Motion System:**
   * Definisikan arsitektur Motion Tokens menggunakan CSS Custom Properties yang terstruktur:
     * Durasi: Token mikro (interaksi hover/press: `< 150ms`), makro (ekspansi kontainer: `300ms - 450ms`).
     * Kurva Easing: Definisikan token kurva custom (e.g., `--ease-standard`, `--ease-emphasized-decelerate`, `--ease-emphasized-accelerate`).
     * Fallback Token: Kurva non-pergerakan untuk context `@media (prefers-reduced-motion: reduce)`.
2. **View Transitions Implementation:**
   * Setiap thumbnail galeri yang diklik harus bertransformasi secara mulus ke modal tampilan penuh menggunakan View Transitions API (`view-transition-name: product-hero`).
   * Selama transisi, elemen teks metadata judul dan harga harus bertransisi menggunakan efek *fade-through-scale*, bukan morphing distorsi teks.
   * Tombol navigasi (Close/Back) harus muncul menggunakan animasi independen (*staggered compositor animation*).
3. **Compositor Guarantee & Memory Management:**
   * Dilarang menginterpolasi properti geometri (`top`, `left`, `width`, `height`) secara langsung di CSS transitions regular.
   * Terapkan strategi alokasi layer dinamis (*Just-In-Time Layer Promotion*): Properti `will-change` hanya boleh aktif sesaat sebelum interaksi dimulai (misal: saat `pointerdown` atau `focus-visible`), dan wajib dilepas (*unset*) setelah animasi berakhir (`transitionend`/`animationend`).
4. **Resilience & Graceful Degradation:**
   * Jika browser tidak mendukung `document.startViewTransition`, sistem harus secara otomatis beralih (*fallback gracefully*) ke transisi modal standar berbasis *Composited Opacity & Scale Transform* tanpa melempar runtime exception.

#### Constraints
* **Pure Web Standards:** Hanya menggunakan Vanilla JavaScript (ES2024+), Native CSS, dan Web Platform APIs. Dilarang menggunakan dependency eksternal.
* **GPU Memory Ceiling:** Alokasi layer tambahan di GPU tidak boleh melebihi 2 layer aktif secara bersamaan pada steady-state.
* **Strict Anti-Jank Budget:** Nol *Long Frame Times* (> 16.6ms / 8.3ms). Total blocking time pada Main Thread selama transisi harus 0ms.

#### Expected Output
1. Blok token CSS `:root` yang memuat seluruh Motion Tokens.
2. Markup HTML semantik untuk galeri dan container modal.
3. Blok CSS terpadu yang memetakan kustomisasi pseudo-elements View Transitions (`::view-transition-*`) dan mitigasi `prefers-reduced-motion`.
4. Kode JavaScript kelas controller (`ProductMotionEngine`) yang menangani:
   * Lifecycle transisi dengan deteksi kapabilitas fitur.
   * JIT layer promotion dan de-promotion logic.
   * Handling interupsi gesture (klik berulang/cancel) yang stabil.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental eksekusi Main Thread (Layout, Paint) vs Compositor Thread (Composite) pada Chromium Compositor Pipeline.
- [ ] Mengapa properti `transform` dan `opacity` tidak memicu *Paint Invalidation* ketika telah dialokasikan ke composited layer mandiri.
- [ ] Anatomi dan siklus rendering pohon pseudo-element View Transitions API (`::view-transition`, `::view-transition-group`, `::view-transition-image-pair`, `::view-transition-old`, `::view-transition-new`).
- [ ] Hubungan antara alokasi VRAM kartu grafis dengan *compositing layer promotion* yang tidak terkendali (Over-promotion/Layer Explosion).
- [ ] Mekanisme kehilangan LCD Subpixel Font Rendering saat elemen dipromosikan ke komposisi GPU.
- [ ] Matriks fisika Motion Tokens: Kapan menggunakan *Emphasized Decelerate*, *Standard Easing*, atau *Linear Curves*.
- [ ] Persyaratan spesifikasi keunikan global `view-transition-name` per siklus rendering dokumen.
- [ ] Dampak psikofisik gerakan UI terhadap pengguna dengan gangguan vestibular (*vestibular disorders*).

### Saya tidak perlu menghafal:
- [ ] Seluruh nilai numerik koordinat kontrol polinomial Bézier (misal: `cubic-bezier(0.05, 0.7, 0.1, 1.0)`) di luar kepala; gunakan visual curve generator atau token sistem.
- [ ] Detail internal implementasi C++ kelas `cc::LayerTreeHostImpl` atau `DisplayItemList` di Chromium source code.
- [ ] Seluruh variasi sintaks vendor-prefix usang untuk akselerasi perangkat keras grafis (seperti `-webkit-transform: translate3d(0,0,0)`).

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi dan memecahkan masalah *Layout Thrashing* dan *Compositor Jank* menggunakan tab Performance, Rendering (Paint Flashing, Layer Borders), dan Layers di Chrome DevTools.
- [ ] Mengimplementasikan *Shared Element Transitions* lintas rute SPA menggunakan `document.startViewTransition()` dengan penanganan error asinkron yang tangguh.
- [ ] Menulis modul *Motion System* terpusat berbasis CSS Variables yang responsif terhadap context `@media (prefers-reduced-motion)`.
- [ ] Mengimplementasikan teknik promosi layer JIT (*Just-In-Time Layer Promotion*) untuk menghemat konsumsi memori grafis perangkat bergerak.
- [ ] Membangun mekanisme fallback *Graceful Degradation* untuk View Transitions API bagi peramban yang belum mengadopsi spesifikasi tersebut secara penuh.