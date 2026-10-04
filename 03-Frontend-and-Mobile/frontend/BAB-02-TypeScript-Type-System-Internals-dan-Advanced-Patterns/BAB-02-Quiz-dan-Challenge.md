# BAB 02: Quiz, Challenge, & Knowledge Check
**Bab 02: Browser Rendering Pipeline, Critical Rendering Path (CRP), & Advanced Web APIs**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Critical Rendering Path (CRP)
Jelaskan transformasi deterministik yang dilakukan browser engine (seperti Blink atau Gecko) saat mengonversi raw bytes dari network stream menjadi representasi visual di layar. Uraikan tahapan berikut:
1. Tokenization & Tree Construction (DOM & CSSOM).
2. Render Tree Generation (bagaimana engine menangani elemen dengan `display: none` vs `visibility: hidden`).
3. Layout / Reflow (koordinat geometri dan box model).
4. Paint & Compositing.
Mengapa CSS secara default diklasifikasikan sebagai *render-blocking resource*, sedangkan parsing HTML dapat berjalan secara inkremental?

### Soal 1.2: Mekanika Perbedaan Layout, Paint, dan Composite
Sebutkan perbedaan mendasar komputasi internal engine antara operasi **Layout (Reflow)**, **Paint (Repaint)**, dan **Compositing**. Jelaskan mengapa modifikasi properti CSS seperti `transform` dan `opacity` dapat dieksekusi langsung oleh *Compositor Thread* (didukung GPU) tanpa memicu siklus Layout dan Paint pada *Main Thread*.

### Soal 1.3: Sinkronisasi Rendering dalam Event Loop Browser
Di mana tepatnya posisi fase *"Update the Rendering"* dalam siklus Event Loop HTML5? Jelaskan urutan eksekusi presisi antara:
- Macrotask (misal: `setTimeout`)
- Microtask queue (misal: `Promise.then`, `queueMicrotask`)
- Callback `requestAnimationFrame` (rAF)
- Style Recalculation & Layout
- IntersectionObserver Callbacks
Apa konsekuensi performa jika microtask queue dibanjiri rekursi mikro (*microtask starvation*) terhadap rendering pipeline?

### Soal 1.4: Dualitas DOM Enkapsulasi: Shadow DOM vs. Virtual DOM
Bandingkan secara fundamental arsitektural antara **Shadow DOM** (W3C Web Components standard) dan **Virtual DOM** (in-memory tree abstraction seperti pada React/Vue):
1. Dari sisi isolasi styling dan event bubbling/retargeting.
2. Dari sisi biaya komputasi runtime (memory allocation dan reconciliation overhead).
Bagaimana browser engine mengintegrasikan Shadow Root ke dalam flat render tree global?

### Soal 1.5: Model Komunikasi Threading: Main Thread vs. Web Worker
Web Worker dirancang untuk mencegah blocking pada Main Thread. Jelaskan:
1. Mengapa Worker diisolasi secara ketat dari akses ke DOM API, objek `window`, dan parent scope?
2. Bagaimana mekanisme transfer data bekerja di balik layar: perbedaan antara *Structured Clone Algorithm* (deep-copy serialization) vs *Transferable Objects* (`ArrayBuffer`) vs `SharedArrayBuffer` dengan konkurensi `Atomics`?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik Forced Synchronous Layout & Layout Thrashing
Perhatikan potongan kode berikut:

```javascript
function updateElementWidths(elements) {
  for (let i = 0; i < elements.length; i++) {
    const parentWidth = elements[i].parentElement.offsetWidth; // Read
    elements[i].style.width = `${parentWidth * 0.5}px`;         // Write
  }
}
```

Jelaskan secara mendalam mengapa kode di atas memicu fenomena **Forced Synchronous Layout (Layout Thrashing)**. Apa yang terjadi pada internal queue rendering browser saat operasi *read* dan *write* geometri diselingi secara berulang? Bagaimana Anda merefaktor fungsi ini agar berjalan dalam $O(1)$ layout recalculation?

### Soal 2.2: Layer Promotion, Memory Footprint, dan Layer Squashing
Penggunaan properti CSS `will-change: transform` atau manipulasi 3D transform (`translateZ(0)`) memaksa browser mempromosikan elemen menjadi *Compositing Layer* (Graphics Layer) terpisah.
1. Kapan layer promotion menguntungkan performa, dan kapan ia berubah menjadi anti-pattern (*memory explosion*) pada perangkat mobile?
2. Apa yang dimaksud dengan **Layer Squashing**, dan bagaimana browser menangani trade-off antara rendering overhead versus konsumsi GPU VRAM ketika terdapat ratusan elemen tumpang tindih (*overlapping layers*)?

### Soal 2.3: Analisis Asinkronitas Web Observer APIs
Bandingkan karakteristik internal dan scheduling browser antara:
- `MutationObserver`
- `ResizeObserver`
- `IntersectionObserver`

Mengapa `ResizeObserver` dapat melempar error *"ResizeObserver loop completed with undelivered notifications"*, dan bagaimana browser engine mencegah infinite recursion saat callback observer memodifikasi dimensi elemen yang sedang diobservasi?

### Soal 2.4: Resource Prioritization & Critical Path Optimization
Bagaimana browser Resource Fetch Scheduler membedakan dan memprioritaskan download serta eksekusi dari tag berikut:
- `<link rel="preload" as="script">`
- `<link rel="prefetch">`
- `<script async>`
- `<script defer>`
- Atribut `fetchpriority="high"`

Jelaskan skenario *resource starvation* di mana konfigurasi `preload` yang salah dapat merusak performa *Largest Contentful Paint* (LCP).

### Soal 2.5: Thread Synchronization & Passive Event Listeners
Mengapa mendaftarkan event listener `touchstart` atau `wheel` secara default memblokir fluiditas scrolling pada browser mobile? Jelaskan interaksi antara *Compositor Thread* dan *Main Thread*, serta bagaimana penambahan flag `{ passive: true }` mengeliminasi *scroll jank* pada level IPC (Inter-Process Communication) browser.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Frame Drops Masif pada Financial Real-Time Dashboard
Sebuah aplikasi web dashboard analitik finansial menerima tick update data pasar saham via WebSocket berkecepatan 60 pesan/detik. Setiap tick memperbarui nilai pada tabel berisi 5.000 baris DOM node aktif.
- **Gejala:** UI membeku (*freeze*), scroll macet total, DevTools Performance tab merekam frame rate anjlok ke 4-8 FPS dengan long tasks berdurasi rata-rata 140ms yang didominasi oleh fase `"Recalculate Style"` dan `"Layout"`.
- **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi akar masalah pada level arsitektur DOM dan render loop.
  2. Rancang arsitektur baru menggunakan teknik **DOM Virtualization (Windowing)**, CSS Containment (`contain: strict`), dan pengolahan data off-thread menggunakan **Web Worker**.
  3. Bagaimana strategi batching rendering frame menggunakan `requestAnimationFrame` agar DOM mutation tidak melebihi alokasi budget 16.67ms (target 60 FPS)?

### Skenario B: Hydration Mismatch & Script Race Condition pada Platform E-Commerce
Platform e-commerce global mengintegrasikan multi-vendor analytics, dynamic A/B testing suite, dan kerangka Server-Side Rendering (SSR).
- **Gejala:** Metrik *Cumulative Layout Shift* (CLS) melonjak ke 0.65 di production. Beberapa pengguna melaporkan tombol "Checkout" tidak responsif selama 3-5 detik pertama setelah UI tampak ter-render visual, atau memicu reload halaman yang tidak diinginkan (*broken event listeners*).
- **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana Anda menganalisis timeline eksekusi script menggunakan Chrome DevTools (Network waterfall, Coverage tab, dan Performance Insights) untuk mengisolasi tabrakan antara dynamic script injection dan hydration SSR?
  2. Mengapa eksekusi script analytics pihak ketiga via `<script async>` dapat merusak proses rehidrasi tree DOM?
  3. Susun mitigasi teknis berbasis **Islands Architecture** atau **Progressive Hydration** serta penataan prioritas eksekusi script menggunakan *Resource Hints* dan sandboxing `iframe` / Web Worker (misal: via Partytown).

### Skenario C: Infinite Scroll Memory Leak & GC Thrashing pada Media Feed
Sebuah web app sosial media dengan infinite feed memuat media visual resolusi tinggi. Pengguna yang melakukan scroll terus-menerus selama lebih dari 5 menit mengalami degradasi performa dramatis: konsumsi RAM browser tab melonjak dari 150MB menjadi 2.2GB, diiringi stuttering periodik setiap 2-3 detik.
- **Gejala:** Memory tab pada DevTools menunjukkan pola *"Sawtooth Pattern"* yang sangat tajam dengan baseline memori yang terus meningkat (*Garbage Collection Thrashing*).
- **Pertanyaan Diagnostik & Solusi:**
  1. Mengapa membiarkan node DOM yang sudah berada jauh di luar viewport tetap berada di tree dapat melumpuhkan subsystem memori dan GPU composite?
  2. Bandingkan trade-off antara **Dynamic Node Recycling (DOM Node Pooling)** vs penggunaan properti CSS modern `content-visibility: auto` beserta `contain-intrinsic-size`.
  3. Bagaimana mengaudit dan membersihkan memory leak yang berasal dari dangling references pada `IntersectionObserver`, detached DOM trees, dan image decoding cache di memori GPU?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Virtualized Data Grid Engine (Zero-Dependency)

#### Problem Statement
Anda ditugaskan membangun engine inti komponen **Data Grid** berbasis Vanilla TypeScript tanpa menggunakan UI framework eksternal (no React, no Vue, no TanStack Table). Grid ini harus mampu merender dataset finansial sebesar **100.000 baris $\times$ 20 kolom** secara mulus tanpa mengorbankan interaktivitas Main Thread.

#### Requirements
1. **Virtual Viewport Scrolling:**
   - Hanya render elemen baris yang terlihat di layar (*viewport*) ditambah buffer atas dan bawah (masing-masing 5 baris).
   - Tinggi baris harus dinamis (dapat bervariasi antara 35px hingga 80px berdasarkan konten teks).
   - Sinkronisasi scroll bar native semu (*virtual scrollbar height*) yang merefleksikan total ketinggian estimasi 100.000 baris.
2. **Off-Thread Data Operations:**
   - Implementasikan Web Worker untuk operasi sorting multi-kolom dan text-filtering pada 100.000 baris data. Main Thread tidak boleh melakukan operasi komputasi array berat.
   - Gunakan `Transferable Objects` atau compact serializable flat array buffer untuk transfer dataset antara Worker dan Main Thread guna meminimalkan biaya kloning.
3. **CSS Containment & Layout Stability:**
   - Elemen baris wajib diisolasi menggunakan CSS `contain: strict` atau `contain: content` untuk mencegah mutasi satu baris memicu relayout pada parent kontainer.
   - Posisi baris virtual harus menggunakan CSS `transform: translate3d(0, Ypx, 0)` untuk memanfaatkan hardware acceleration GPU alih-alih memanipulasi properti `top`.
4. **Performance Monitoring Layer:**
   - Terapkan pemantauan real-time menggunakan `PerformanceObserver` untuk mendeteksi *Long Tasks* (>50ms) dan FPS counter internal.

#### Constraints
- **Zero External Dependencies:** Hanya gunakan native Web APIs (DOM, CSSOM, Web Workers, PerformanceObserver).
- **Memory Footprint:** Konsumsi heap memory tab browser tidak boleh melebihi 60 MB saat navigasi/scrolling intensif dilakukan.
- **Budget Performa:** Waktu eksekusi script pada Main Thread saat scrolling cepat tidak boleh melebihi 10ms per frame (memastikan kestabilan 60 FPS).
- **Type Safety:** Ditulis sepenuhnya dalam TypeScript dengan *strict mode* diaktifkan (`"strict": true`).

#### Expected Output
1. File modul `VirtualGrid.ts` yang mengimplementasikan class inti rendering, kalkulasi index viewport, dan event orchestration.
2. File `grid.worker.ts` untuk backend pengolahan data array (sort/filter engine).
3. File demonstrasi `index.html` dan `style.css` yang mendemonstrasikan grid merender 100.000 baris mock data finansial dengan visual FPS counter dan memory consumption meter.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Rincian siklus hidup Critical Rendering Path: Parse HTML $\rightarrow$ DOM, Parse CSS $\rightarrow$ CSSOM, Render Tree, Layout, Paint, dan Composite.
- [ ] Perbedaan internal engine antara operasi yang berjalan di Main Thread (Layout, Paint) vs Compositor Thread (GPU-accelerated layers).
- [ ] Posisi fase rendering dalam Event Loop HTML5 terhadap Macrotask, Microtask, dan `requestAnimationFrame`.
- [ ] Mekanisme terjadinya Layout Thrashing / Forced Synchronous Layout dan cara mengauditnya menggunakan DevTools Performance Panel.
- [ ] Perilaku pemuatan dan urutan eksekusi skrip (`async`, `defer`, `type="module"`, `preload`, `prefetch`).
- [ ] Batasan, model memori, dan skema transfer data pada Web Worker (Structured Clone vs Transferable Objects).
- [ ] Prinsip kerja enkapsulasi Shadow DOM vs optimasi tree reconciliation Virtual DOM.
- [ ] Cara kerja API modern browser untuk observasi: `IntersectionObserver`, `ResizeObserver`, dan `MutationObserver`.

### Saya tidak perlu menghafal:
- [ ] Nilai byte spesifik dari setiap format encoding HTTP header browser.
- [ ] Ratusan nama properti CSS yang masuk ke dalam kategori trigger Layout vs Paint secara luar kepala (gunakan referensi seperti *CSS Triggers* / DevTools).
- [ ] Algoritma internal C++ browser engine (misal: implementasi parsing token Blink di `HTMLDocumentParser.cpp`).
- [ ] Sintaks legacy vendor prefixes (`-webkit-`, `-moz-`, `-ms-`) untuk fitur yang sudah terstandardisasi secara penuh.

### Saya harus bisa melakukan:
- [ ] Melakukan profiling dan membaca Flame Chart pada Chrome DevTools Performance tab untuk mengidentifikasi *Long Tasks*, *Forced Synchronous Layout*, dan *Dropped Frames*.
- [ ] Merefaktor kode JavaScript manipulasi DOM yang memicu Layout Thrashing menjadi pola *read-then-write* yang dioptimasi via `requestAnimationFrame`.
- [ ] Mengimplementasikan *passive event listeners* untuk menstabilkan input scrolling pada antarmuka sentuh / mousewheel.
- [ ] Membangun mekanisme virtualisasi viewport (DOM windowing) custom untuk menangani dataset skala besar secara performan.
- [ ] Mendelegasikan tugas komputasi intensif (sorting, filtering, transformation data masif) dari Main Thread ke Web Worker menggunakan transfer data bebas overhead copy.
- [ ] Menggunakan CSS Containment (`contain: strict`, `content-visibility: auto`) untuk mengisolasi biaya kalkulasi layout pada komponen UI independen.