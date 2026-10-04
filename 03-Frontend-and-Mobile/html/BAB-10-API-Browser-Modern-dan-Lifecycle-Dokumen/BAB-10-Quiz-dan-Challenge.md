# BAB 10: Quiz, Challenge, & Knowledge Check
**API Browser Modern & Lifecycle Dokumen**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: State Transitions & ReadyState Mapping
Jelaskan secara komparatif transisi status dokumen dari `document.readyState === 'loading'`, `'interactive'`, hingga `'complete'`. Bagaimana korelasi eksak masing-masing state tersebut terhadap firing event `DOMContentLoaded` dan `window.onload`, serta bagaimana eksekusi script sinkron mempengaruhi transisi state tersebut pada Main Thread?

### Soal 1.2: Script Execution Semantics: Defer vs Async vs Module
Bandingkan mekanisme parser-blocking, urutan eksekusi (*execution order guarantee*), dan timing eksekusi antara:
1. `<script src="..." defer>`
2. `<script src="..." async>`
3. `<script type="module" src="...">`
4. Dynamic Script Injection (`document.createElement('script')`)

Jelaskan skenario di mana `async` script dapat mengeksekusi sebelum DOM selesai diparse dan memicu runtime error pada manipulasi DOM!

### Soal 1.3: Paradigma Asinkron: Observer APIs vs Event Listener Polling
Mengapa arsitektur modern browser meninggalkan pendekatan scroll/resize listener berbasis polling (`window.addEventListener('scroll', ...)` dengan debounce/throttle) dan menggantinya dengan Observer APIs (`IntersectionObserver`, `ResizeObserver`)? Jelaskan perbedaannya dari perspektif browser rendering pipeline (Recalculate Style, Layout, Paint, Composite) dan Main Thread offloading!

### Soal 1.4: Telemetri dan Terminasi Dokumen: Navigator.sendBeacon vs Fetch Keepalive
Jelaskan limitasi fatal dari penggunaan synchronous `XMLHttpRequest` atau asynchronous `fetch()` biasa di dalam event listener `beforeunload` atau `unload`. Mengapa `navigator.sendBeacon()` atau `fetch(url, { keepalive: true })` dirancang untuk menyelesaikan masalah tersebut, dan bagaimana kernel jaringan browser menangani payload transmisi saat proses renderer sudah diterminasi?

### Soal 1.5: Page Lifecycle API vs Legacy Unload Lifecycle
W3C/Chrome memformalkan *Page Lifecycle API* yang memperkenalkan state seperti `active`, `passive`, `hidden`, `frozen`, dan `terminated`. Mengapa event `unload` saat ini dikategorikan sebagai *bad practice* (*deprecated/discouraged*), dan mengapa developer modern diwajibkan beralih ke event `visibilitychange` dan `pagehide` untuk persistensi state?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Microtask Batching pada MutationObserver
Ketika terjadi ribuan mutasi DOM secara berurutan dalam satu event loop frame, bagaimana `MutationObserver` mencegah Main Thread starvation? Jelaskan siklus hidup mutasi DOM dari delivery record, antrean microtask, hingga triggering callback observer, serta apa dampaknya jika callback observer memicu mutasi DOM baru secara rekursif?

### Soal 2.2: Back/Forward Cache (bfcache) Disqualification Mechanics
bfcache menyimpan *in-memory snapshot* dari seluruh execution context halaman (termasuk JS heap). Identifikasi minimal 4 kondisi atau penggunaan API modern yang secara otomatis mendiskualifikasi halaman dari bfcache. Bagaimana cara memvalidasi via Chrome DevTools Application Panel dan bagaimana cara memanfaatkan event `pageshow` (`event.persisted`) untuk memulihkan koneksi realtime (misal: WebSocket) yang terputus saat freeze?

### Soal 2.3: IntersectionObserver Nested Clipping & Layout Shifts
Diberikan sebuah komponen dalam struktur DOM: `Root Scroller > Overflow Hidden Container > iframe > Target Element`. Bagaimana `IntersectionObserver` menghitung `intersectionRatio` dengan kompleksitas *clipping boundary* bertingkat tersebut? Jelaskan bagaimana threshold clipping dihitung jika salah satu ancestor memiliki properti CSS `transform: scale(...)` atau `contain: paint`!

### Soal 2.4: Storage Quota, Persistence Mode, dan Eviction Pressure
Pada kondisi storage pressure (ruang disk menipis), browser akan membersihkan data client-side via LRU (*Least Recently Used*). Jelaskan perbedaan antara *Best-Effort Storage* dan *Persistent Storage* dalam konteks Storage API (`navigator.storage`). Bagaimana mekanisme degradasi IndexedDB jika kuota tercapai, dan bagaimana parameter `durability: "relaxed"` vs `"strict"` pada transaksi IndexedDB mempengaruhi physical disk write (fsync)?

### Soal 2.5: User Activation Gating & Beforeunload Dialog Hijacking
Browser modern menerapkan *User Activation Gating* (Transient User Activation). Jelaskan mengapa pemanggilan `window.open()`, `navigator.clipboard.writeText()`, atau rendering kustom modal dialog pada `window.onbeforeunload` akan diblokir oleh browser jika tidak terdapat interaksi pengguna yang valid. Bagaimana spesifikasi HTML menangani mitigasi anti-phishing pada event `beforeunload` saat ini?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Infinite Scroll Memory Leak & Layout Thrashing pada E-Commerce Enterprise
Sebuah aplikasi e-commerce enterprise memiliki fitur infinite scroll dengan ribuan produk kompleks yang dirender ke DOM. Pengguna melaporkan bahwa setelah melakukan scroll sejauh 50 halaman, browser mengalami lag parah (Long Tasks > 350ms, frame drop hingga < 15 FPS), konsumsi memori renderer melonjak hingga 1.8 GB, dan aplikasi akhirnya crash (OOM crash) pada perangkat mobile kelas menengah.

Inspeksi awal menunjukkan penggunaan `IntersectionObserver` untuk lazy-loading gambar, namun komponen DOM dari item yang telah dilewati tetap dibiarkan berada di DOM tree, dan beberapa tooltip component menginisialisasi instance `ResizeObserver` independen pada setiap card produk.

*   **Pertanyaan Diagnostik:**
    1. Identifikasi *root cause* dari degradasi performa render pipeline (Style recalculation & Composite layers) akibat membiarkan elemen out-of-viewport tetap berada di live DOM tree.
    2. Rancang arsitektur refactoring menggunakan teknik *DOM Virtualization* dipadukan dengan `IntersectionObserver`. Bagaimana lifecycle observer harus dimanage saat elemen di-recycle?
    3. Mengapa instansiasi individual `ResizeObserver` per item adalah anti-pattern, dan bagaimana cara mendesain pola *Flyweight Observer* (single shared observer instance) untuk ribuan target elemen?

### Skenario B: Race Condition Telemetri Checkout dan Data Drop pada Tab Unload
Sebuah platform checkout perbankan mencatat hilangnya 8.4% data telemetri analitik "Checkout Abort" ketika pengguna menutup tab atau berpindah aplikasi secara tiba-tiba di iOS Safari dan Chrome Mobile. Analisis log menemukan bahwa tim menggunakan skrip berikut:

```javascript
window.addEventListener('beforeunload', () => {
  fetch('/api/telemetry/abort', {
    method: 'POST',
    body: JSON.stringify(collectCheckoutMetrics()),
    headers: { 'Content-Type': 'application/json' }
  });
});
```

Di sisi lain, ketika kode diubah menjadi `navigator.sendBeacon`, tim backend melaporkan bahwa payload berukuran 75 KB sering kali gagal diterima secara acak (*silent network drop*) tanpa throwing JavaScript exception di client.

*   **Pertanyaan Diagnostik:**
    1. Mengapa iOS Safari dan browser mobile berbasis Chromium membatalkan request `fetch` asinkron pada saat event `beforeunload` dieksekusi? Jelaskan dari siklus hidup proses renderer vs network process!
    2. Mengapa payload 75 KB pada `navigator.sendBeacon` mengalami *silent drop*? Analisis limitasi spesifikasi kuota transmisi payload pada Web Beacon API!
    3. Rancang arsitektur transmisi data yang *fail-safe* menggunakan kombinasi `visibilitychange`, `pagehide`, `fetch` dengan flag `keepalive: true`, fallback IndexedDB, dan batasan chunking payload yang sesuai standar RFC/W3C!

### Skenario C: Micro-Frontend (MFE) Sub-App Lifecycle & Observer Memory Leak
Sebuah enterprise portal mengadopsi arsitektur Single Page Application (SPA) berbasis Micro-Frontend. Sub-aplikasi (misal: "Analytics Widget") di-*load* dan di-*unmount* secara dinamis ke dalam container DOM `#widget-slot` menggunakan *Dynamic Script Injection* tanpa full-page refresh. 

Setelah 2 jam penggunaan intensif di mana pengguna berganti-ganti widget, DevTools Heap Snapshot menunjukkan adanya ribuan *detached HTML elements*, puluhan instance `MutationObserver` dan `ResizeObserver` yang masih memproses mutasi di background, serta lonjakan CPU konstan meskipun sistem dalam keadaan idle.

*   **Pertanyaan Diagnostik:**
    1. Jelaskan bagaimana referensi sirkular antara *DOM Node References*, observer callback closures, dan window global context mencegah Garbage Collector (V8/JSC) membersihkan memory heap sub-aplikasi yang telah di-unmount!
    2. Buatlah rancangan *Contract/Lifecycle Interface* (`mount()`, `unmount()`) standar yang harus diimplementasikan oleh setiap vendor sub-aplikasi untuk menjamin teardown komprehensif (termasuk `.disconnect()`, pembatalan pending microtasks, dan event listener cleanup).
    3. Bagaimana cara mengimplementasikan layer isolasi atau automated leak-detection menggunakan weak references (`WeakRef` & `FinalizationRegistry`) untuk mendeteksi sub-aplikasi yang gagal membersihkan resource DOM/Observer saat di-unmount?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Resilient Telemetry & Viewport Virtualization Engine (RTV-Engine)

#### Problem Statement
Anda ditugaskan membangun library core JavaScript murni (*Vanilla TypeScript/JavaScript zero-dependency*) bernama **RTV-Engine**. Modul ini bertindak sebagai fondasi untuk enterprise web app yang menangani rendering data besar dan pelaporan analitik mission-critical dengan jaminan *zero data loss* saat lifecycle terminasi halaman, tahan terhadap kondisi *bfcache restore*, dan tidak menyebabkan main-thread blocking.

#### Architectural Requirements
1. **Viewport Intersection & Batching Manager:**
   * Buat class `ViewportTracker` berbasis singleton `IntersectionObserver` untuk memantau visibilitas ratusan elemen.
   * Elemen yang masuk ke dalam viewport harus diberi status `VISIBLE`, dan jika berada di luar viewport sejauh margin toleransi (`rootMargin: "200px 0px"`), elemen harus di-*recycle* / di-unrender konten beratnya untuk menjaga total node count DOM tetap rendah.
   * Tidak boleh ada layout thrashing (`getBoundingClientRect()` terlarang di dalam loop scroll).

2. **Lifecycle State Machine & Bfcache Handling:**
   * Implementasikan state machine yang memetakan: `ACTIVE` $\rightarrow$ `PASSIVE` $\rightarrow$ `HIDDEN` $\rightarrow$ `FROZEN` $\rightarrow$ `TERMINATED`.
   * Tangani event `visibilitychange`, `pagehide`, dan `pageshow`.
   * Saat `pageshow` mendeteksi `event.persisted === true` (restorasi dari bfcache), engine harus secara otomatis merefresh koneksi telemetry, merevalidasi sinkronisasi waktu, dan memancarkan event internal `BFCacheRestored`.

3. **Resilient Telemetry Queue & Safe Flushing:**
   * Buat `TelemetryQueue` dengan mekanisme in-memory buffering.
   * Queue harus otomatis melakukan *flush* data ketika:
     1. Ukuran batch mencapai ambang batas 15 item, ATAU
     2. Interval timer 5000ms tercapai, ATAU
     3. Dokumen berpindah ke state `hidden` (via `visibilitychange`), ATAU
     4. Lifecycle mencapai `pagehide`.
   * Pengiriman data pada terminasi wajib menggunakan `fetch()` dengan `{ keepalive: true }` sebagai primary path, dengan fallback ke `navigator.sendBeacon()`.
   * Jika payload melebihi safe limit (64 KB), engine harus melakukan auto-chunking payload secara sinkron sebelum proses terminasi dieksekusi.
   * Jika browser sepenuhnya offline saat unload, persistensikan payload ke `IndexedDB` atau `localStorage` sebagai *dead-letter queue* untuk dikirim ulang pada lifecycle `active` berikutnya.

#### Constraints
* **Pure Native APIs:** Dilarang menggunakan external library (No React, No Lodash, No RxJS).
* **Bundle Budget:** Ukuran bundle terkompilasi < 4 KB minified + gzipped.
* **No Deprecated Lifecycle APIs:** Terlarang menggunakan `window.onunload` atau sync XHR.
* **Performance Budget:** Execution time pada callback lifecycle tidak boleh melebihi 16ms (1 frame budget) untuk menghindari freezing visual.

#### Expected Output
1. Script TypeScript/ES6 modular lengkap yang siap dijalankan di browser modern.
2. Demonstrasi test bench sederhana (HTML mockup) yang membuktikan:
   * Event terkirim sukses via keepalive/beacon saat tab ditutup/di-refresh.
   * State bfcache tertrigger dan pulih dengan benar.
   * Dynamic virtualization berhasil menambah/mencopot DOM node secara transparan berdasarkan viewport tracking.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Timeline eksekusi HTML parser: dari tokenisasi bytes, pembentukan DOM, CSSOM compilation, hingga firing event `DOMContentLoaded` dan `window.onload`.
- [ ] Atribut pemuatan script modern (`defer`, `async`, ES Module `<script type="module">`) dan interaksinya terhadap blocking behavior Main Thread.
- [ ] Mekanisme internal Browser Rendering Engine (Parse $\rightarrow$ Style $\rightarrow$ Layout $\rightarrow$ Pre-Paint $\rightarrow$ Paint $\rightarrow$ Layerize $\rightarrow$ Commit $\rightarrow$ Composite).
- [ ] Perbedaan fundamental antara Event Polling vs Observer APIs (`IntersectionObserver`, `ResizeObserver`, `MutationObserver`, `PerformanceObserver`).
- [ ] Arsitektur Page Lifecycle API spesifikasi W3C (`active`, `passive`, `hidden`, `frozen`, `terminated`) dan bahaya penggunaan event `unload`.
- [ ] Mekanisme Back/Forward Cache (bfcache), faktor-faktor yang mendiskualifikasinya, dan cara penanganannya via event `pageshow`/`pagehide`.
- [ ] Arsitektur network unload: limitasi ukuran buffer `navigator.sendBeacon` (64 KB limit) dan konfigurasi `fetch(..., { keepalive: true })`.
- [ ] Isolasi storage, kuota, mode ketahanan (*Best-Effort* vs *Persistent*), serta algoritma penggusuran data (*eviction*) pada browser client-side storage.

### Saya tidak perlu menghafal:
- [ ] Struktur byte persis dari low-level HTTP network packet yang ditransmisikan oleh Beacon API.
- [ ] Vendor-specific internal engine codes (seperti ID numbering parser C++ pada WebKit atau Blink).
- [ ] Syntax konfigurasi legacy browser fallback (misal: IE8 `attachEvent`, `document.all`, atau Flash-based local storage).
- [ ] Angka kuota penyimpanan statis per browser secara absolut (karena kuota dihitung dinamis berdasarkan persentase sisa disk space perangkat pengguna).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi strategi loading resource script secara optimal menggunakan `defer`, `async`, atau native ES Module sesuai dependensi pohon eksekusi.
- [ ] Mengimplementasikan *Virtual Scrolling* atau *Lazy Loading* berkinerja tinggi menggunakan single-instance `IntersectionObserver` untuk mencegah layout thrashing.
- [ ] Melakukan profiling Main Thread dan mendeteksi layout thrashing atau Long Tasks (>50ms) menggunakan Chrome DevTools Performance Panel.
- [ ] Menulis pipeline telemetri pengiriman data analitik yang tahan banting (*resilient*) pada siklus hidup terminasi dokumen tanpa menghilangkan data pengguna.
- [ ] Mendiagnosis dan mengeliminasi *detached DOM trees* dan memory leak yang disebabkan oleh dangling event listeners atau uncleaned Observer APIs via DevTools Heap Profiler.
- [ ] Mengaudit status kompatibilitas bfcache pada halaman web menggunakan Application Panel DevTools dan mengatasi blocker seperti WebSocket dangling atau event listener `unload`.