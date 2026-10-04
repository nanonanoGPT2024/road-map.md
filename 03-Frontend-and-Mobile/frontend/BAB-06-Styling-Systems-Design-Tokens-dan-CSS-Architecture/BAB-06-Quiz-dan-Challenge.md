# BAB 06: Quiz, Challenge, & Knowledge Check
**Bab 06: Enterprise Micro-frontends, Concurrency, & Distributed Frontend Architecture (Module Federation, Web Workers, & Offline Systems)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Module Federation Runtime & Dependency Negotiation
Jelaskan siklus hidup (*lifecycle*) inisialisasi runtime Webpack Module Federation saat Host me-load `remoteEntry.js` dari Remote Application. Bagaimana runtime menegosiasikan shared dependencies ketika konfigurasi `singleton: true` diaktifkan dan terdapat perbedaan rentang versi (*semver ranges*) antara Host dan Remote?

### Soal 1.2: Perbedaan Mendasar Threading Model Browser
Bandingkan model eksekusi, cakupan memori (*memory scope*), kemampuan akses API, serta siklus hidup (*lifecycle*) antara **Dedicated Web Worker**, **Shared Worker**, **Service Worker**, dan **Audio/Paint Worklet**. Mengapa Worklet dirancang dengan thread execution model yang jauh lebih ketat dibanding Web Worker?

### Soal 1.3: Data Marshalling: Structured Clone vs Transferable Objects vs SharedArrayBuffer
Ketika data dikirimkan antar-thread via `postMessage`, jelaskan secara mendalam perbedaan mekanisme komputasi dan memori antara:
1. **Structured Clone Algorithm**
2. **Transferable Objects** (`ArrayBuffer`)
3. **SharedArrayBuffer** dengan sinkronisasi `Atomics`

Sebutkan pula persyaratan header HTTP (*Cross-Origin Opener/Embedder Policy*) yang wajib diterapkan agar browser mengizinkan penggunaan `SharedArrayBuffer`.

### Soal 1.4: Arsitektur Komposisi Micro-frontends: SSR vs Edge vs Client-Side
Analisis *trade-off* mendalam antara arsitektur komposisi Micro-frontends di:
1. **Server-Side** (misal: Podium, Tailor, Node.js proxy assembly)
2. **Edge-Side** (misal: Cloudflare Workers / Fastly ESI)
3. **Client-Side** (misal: Module Federation, Single-SPA, Web Components)

Fokuskan analisis pada metrik *Core Web Vitals* (FCP, LCP, CLS, INP), *infrastructure operational overhead*, dan isolasi kegagalan (*fault blast-radius*).

### Soal 1.5: Service Worker Lifecycle & Dual-Layer Caching Dilemma
Jelaskan siklus status Service Worker dari `parsed` $\rightarrow$ `installing` $\rightarrow$ `installed (waiting)` $\rightarrow$ `activating` $\rightarrow$ `redundant`. Mengapa strategi caching pada Service Worker (*CacheStorage API*) sering kali berkonflik secara destruktif dengan HTTP Cache (*Browser Cache/CDN headers*) jika tidak dikonfigurasi secara harmonis?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Module Federation "StrictVersion" Violation & Shared Scope Crash
Anda mengonfigurasi sebuah Micro-frontend dengan pengaturan:
```javascript
shared: {
  react: { singleton: true, strictVersion: true, requiredVersion: "^18.2.0" }
}
```
Host berjalan pada React `18.2.0`. Sebuah Remote baru di-deploy ke produksi menggunakan React `19.0.0`. Apa yang terjadi pada runtime browser ketika Host me-load Remote tersebut? Telusuri alur eksekusi `__webpack_require__.S` (Shared Scope Object) dan bagaimana Anda mengimplementasikan fallback handling tanpa menyebabkan *hard crash* pada Global Shell.

### Soal 2.2: The `skipWaiting()` Chunk Mismatch Trap
Sebuah Single Page Application (SPA) berskala enterprise menggunakan Service Worker dengan pemanggilan `self.skipWaiting()` langsung di dalam event handler `install`. Tiga menit setelah deploy rilis baru, puluhan user melaporkan crash beruntun dengan error:
`ChunkLoadError: Loading chunk 404 failed (missing: /assets/dashboard.[hash].js)`.
Jelaskan mekanisme internal mengapa `self.skipWaiting()` yang tidak terkontrol memicu kondisi ini pada client yang sedang aktif, dan bagaimana arsitektur reload berbasis *soft-prompt/deferred activation* menyelesaikan problem ini.

### Soal 2.3: IndexedDB Transaction Inactivity & Event Loop Starvation
Perhatikan snippet fungsi dalam Web Worker berikut:
```javascript
async function persistLargeDataset(db, data) {
  const tx = db.transaction("records", "readwrite");
  const store = tx.objectStore("records");
  
  const token = await fetchRemoteSyncToken(); // Async network call
  
  for (const item of data) {
    store.put({ ...item, token });
  }
}
```
Mengapa kode di atas memicu exception `TransactionInactiveError` pada pemanggilan `store.put()` di browser modern? Jelaskan mekanisme internal *auto-commit* transaksi IndexedDB dalam hubungannya dengan microtask queue dan macro-task event loop browser.

### Soal 2.4: Cross-Origin Web Worker Instantiation & CSP Sandbox
Sebuah aplikasi Host di-deploy pada `https://app.enterprise.com`. Anda diwajibkan me-load Web Worker script yang disimpan di CDN terpisah: `https://cdn.enterprise-assets.com/workers/heavy-computation.js`.
Browser menolak eksekusi dengan `SecurityError: Script at '...' cannot be accessed from origin '...'`.
Bagaimana cara menginstansiasi Web Worker cross-origin ini secara legal menggunakan teknik `Blob` / `URL.createObjectURL` atau dynamic import, serta bagaimana konfigurasi Content Security Policy (`worker-src`, `script-src`, `connect-src`) yang tepat agar tidak menimbulkan celah keamanan XSS?

### Soal 2.5: Profiling Worker Memory Retention & Detached Contexts
Anda membuat sistem task execution pool berbasis Web Worker yang men-generate dedicated worker untuk setiap operasi intensif lalu memanggil `worker.terminate()`. Namun, setelah 4 jam pengujian beban tinggi, memori sistem Host terus meningkat hingga tab mengalami OOM (*Out of Memory* crash).
Bagaimana `worker.terminate()` bekerja di level V8 Isolate? Apa saja referensi tersembunyi (misal: uncleaned `MessagePort`, event listener closures, circular object retention pada Host thread) yang dapat mencegah V8 me-reclaim memori dari terminated worker context?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Global Shell Degradation pada Super-App Micro-frontend
* **Konteks:** Perusahaan Fintech mengoperasikan aplikasi Super-App yang terdiri dari 1 Host Shell dan 14 Micro-frontends (Remotes) independen via Webpack Module Federation. Tim Checkout melakukan hotfix deployment Remote mereka pada pukul 14:00.
* **Gejala:** Pukul 14:05, metrik error rate di Datadog melonjak 800%. Ribuan user di safari iOS mengalami blank screen total saat navigasi ke tab manapun. User di Chrome mengalami styling global shell yang hancur (CSS layout runtuh) dan tombol login menjadi unresponsive. Tim Checkout mengklaim mereka hanya mengubah styling internal dan dependensi internal tanpa menyentuh Host.
* **Pertanyaan Diagnostik:**
  1. Apa akar masalah (*root cause*) arsitektural yang paling mungkin menyebabkan kebocoran CSS global dan kegagalan chunk loading antar-remotes pada Safari?
  2. Bagaimana mekanisme dynamic CSS injection pada Module Federation berinteraksi dengan DOM? Mengapa urutan evaluasi chunk (*cascading order*) bisa terbalik saat lazy-loading concurrent remotes?
  3. Rancang arsitektur pencegahan (*zero-trust isolation*) untuk Host Shell yang mencakup CSS Scoping (Shadow DOM vs CSS Modules/Prefixing namespace), version pin locking, dan *circuit breaker pattern* pada runtime dynamic remote loading.

---

### Skenario B: Race Condition & State Split-Brain pada Field-Agent PWA
* **Konteks:** Sebuah aplikasi logistik digunakan oleh ribuan kurir di daerah dengan konektivitas *intermittent* (sering offline). Aplikasi menggunakan Service Worker (`Background Sync API`), IndexedDB lokal sebagai source-of-truth offline, dan REST API backend.
* **Gejala:** Kurir A menandai paket #9901 sebagai "Delivered" saat offline pada pukul 10:00 (tersimpan di IndexedDB). Kurir B (rekan kerja yang mengambil alih) mengakses server via web portal pada pukul 10:15 saat koneksi normal dan menandai paket #9901 sebagai "Returned to Hub". Pada pukul 10:30, Kurir A mendapatkan sinyal 4G; Service Worker secara otomatis melakukan flushing queue mutasi lokal ke backend.
* **Dampak:** Status di backend tertimpa menjadi "Delivered" tanpa mencatat status "Returned to Hub", memicu anomali logistik fatal (*silent data corruption*). Selain itu, jika proses sync gagal di tengah jalan akibat koneksi putus tiba-tiba, request terkirim ganda (*duplicate execution*).
* **Pertanyaan Diagnostik:**
  1. Analisis mengapa arsitektur "Last-Write-Wins" gagal total dalam skenario distributed offline-first ini.
  2. Rancang protokol sinkronisasi data dua arah (*bidirectional synchronization engine*) yang tahan banting menggunakan:
     - Vector Clocks atau Logical Timestamps (CRDTs).
     - Idempotency Keys pada Service Worker queue payload.
     - Dead-Letter Queue (DLQ) pada IndexedDB lokal untuk menangani konflik data yang membutuhkan intervensi manual kurir.
  3. Bagaimana Service Worker memastikan bahwa jika proses sinkronisasi terputus di tengah jalan, mutasi tidak dieksekusi ulang dua kali oleh server (*at-most-once* vs *at-least-once semantics*)?

---

### Skenario C: Concurrency Bottleneck pada Real-Time Financial Trading Terminal
* **Konteks:** Anda membangun platform trading crypto/forex enterprise yang menerima 25.000 pembaruan harga (*ticks*) per detik via WebSocket. UI menampilkan visualisasi Order Book 100 kedalaman level, grafik candlestick interaktif (Canvas/WebGL), dan riwayat eksekusi trade.
* **Gejala:** Saat volatilitas pasar ekstrem, *Total Blocking Time* (TBT) melonjak ke >3000ms. UI freeze, slider order tidak dapat digeser, dan browser menampilkan peringatan "Page Unresponsive".
* **Audit Awal:** Tim memindahkan kalkulasi agregasi data ke dedicated Web Worker via Comlink library. Namun, CPU usage tetap 100%, dan performa UI justru semakin lambat karena overhead serialisasi JSON/Object yang masif pada `postMessage` (terjadi *memory thrashing* dan garbage collection pause konstan setiap 500ms).
* **Pertanyaan Diagnostik:**
  1. Mengapa memindahkan komputasi ke Web Worker konvensional gagal menyelesaikan masalah ini ketika throughput data sangat tinggi (*high-frequency streaming*)?
  2. Rancang arsitektur zero-copy data pipeline yang memisahkan ingestion, kalkulasi, dan rendering dari Main Thread menggunakan:
     - `SharedArrayBuffer` dan `Atomics` untuk implementasi Circular Ring Buffer lock-free antar-thread.
     - `OffscreenCanvas` yang di-transfer ke Worker context agar seluruh proses rendering tidak menyentuh Main Thread sama sekali.
  3. Apa saja limitasi browser dan kompromi keamanan yang harus dihadapi saat mengimplementasikan arsitektur ini, dan bagaimana strategi fallback untuk environment yang tidak mendukung `SharedArrayBuffer`?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Multi-Threaded Micro-frontend Data Engine
**Deskripsi Masalah:**
Sebuah enterprise analytics dashboard membutuhkan modul widget performa tinggi yang di-load secara dinamis sebagai Micro-frontend (Remote). Widget ini bertugas menerima dataset terkompresi berukuran puluhan megabyte, mendekompresi, mem-parsing, melakukan agregasi statistik kompleks (P95, P99, standard deviation, anomaly detection), dan merendernya pada grafik 60 FPS tanpa menyebabkan *long tasks* (>16ms) pada Host Shell.

**Requirements Teknis:**
1. **Remote Module Architecture:**
   - Bangun modul Remote via Webpack/Vite Module Federation yang meng-expose satu komponen entry point: `<AnalyticsEngineWidget />`.
   - Host Shell bertindak sebagai consumer independen. Tidak boleh ada dependency duplication untuk React/React-DOM.
2. **Concurrency Architecture (Off-Main-Thread Processing):**
   - `<AnalyticsEngineWidget />` dilarang keras melakukan parsing dan komputasi matematika pada Main Thread.
   - Instansiasi dedicated Web Worker di dalam lifecycle Remote.
   - Gunakan mekanisme **Transferable Objects** (`ArrayBuffer`) untuk mengirim dataset mentah ke Web Worker guna mengeliminasi serialisasi/deserialisasi payload.
   - Gunakan `OffscreenCanvas` di dalam Web Worker untuk rendering visualisasi histogram secara langsung dari thread Worker. Main Thread hanya menyediakan elemen `<canvas>` sebagai target transfer control (`canvas.transferControlToOffscreen()`).
3. **Resilient Offline Cache & Update Management:**
   - Pasang Service Worker pada Host Shell yang meng-cache shell dan Remote Module (`remoteEntry.js` & chunks).
   - Implementasikan strategi:
     - `Stale-While-Revalidate` untuk chunks Remote dengan background validation.
     - Skema *safe update notification*: Jika remote baru terdeteksi, berikan signal ke Host Shell UI untuk menampilkan toast: *"Versi baru tersedia. Klik untuk menyegarkan"* tanpa merusak state komputasi yang sedang berjalan di Worker.
4. **Failure Tolerance & Circuit Breaker:**
   - Jika CDN Remote offline atau URL `remoteEntry.js` mengembalikan error 500, Host Shell tidak boleh crash. Shell harus menampilkan fallback state visual yang elegan (*graceful degradation*) dan me-retry load remote dengan *exponential backoff*.

**Constraints:**
- Framework: React 18+ atau Vanilla JS Modern (ES2022+).
- Dilarang memblokir Main Thread lebih dari 16ms (Wajib lolos audit Performance Profiler: TBT = 0ms selama kalkulasi data).
- Kode Worker harus terisolasi rapi dan tidak boleh membocorkan memori (Pastikan lifecycle cleanup: pembatalan kalkulasi via `AbortController` saat unmount).

**Expected Output:**
- Dokumen/Kode implementasi konfigurasi Webpack/Vite (`federation.config`).
- Kode orchestrator Host Shell yang membungkus Remote dengan Error Boundary & Suspense.
- Kode implementasi Web Worker (`analytics.worker.js`) lengkap dengan penanganan `Transferable Objects` dan `OffscreenCanvas`.
- Kode Service Worker lifecycle management dengan mekanisma update handling yang aman.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal runtime Module Federation (`sharedScope`, `init`, dynamic remotes container).
- [ ] Perbedaan eksekusi antara Main Thread, Web Worker, Service Worker, dan UI Compositor Thread browser.
- [ ] Limitasi Structured Clone Algorithm dan keunggulan transfer kepemilikan memori via Transferable Objects.
- [ ] Aturan isolasi keamanan Spectre, Cross-Origin Isolation (`Cross-Origin-Opener-Policy: same-origin` dan `Cross-Origin-Embedder-Policy: require-corp`), serta dampaknya terhadap ketersediaan API browser (`SharedArrayBuffer`, `performance.measureUserAgentSpecificMemory()`).
- [ ] Mekanisme internal Service Worker lifecycle, byte-for-byte update check, dan jebakan `skipWaiting()` vs `clients.claim()`.
- [ ] Batasan IndexedDB transaction lifecycle dan cara browser menangani auto-closing transaction saat microtask queue exhausted.
- [ ] Metode integrasi dan isolasi Micro-frontend (Module Federation vs Web Components vs iframe sandbox) beserta trade-off performa masing-masing.

### Saya tidak perlu menghafal:
- [ ] Baris-per-baris konfigurasi low-level boilerplate Webpack runtime plugins.
- [ ] Daftar lengkap kode numerik IndexedDB DOMExceptions.
- [ ] Syntax spesifik library third-party Micro-frontend wrapper (misal: Single-SPA helpers), selama memahami implementasi native Module Federation dan Web Components.
- [ ] Konfigurasi byte binary exact dari WebAssembly header format saat komputasi di Worker.

### Saya harus bisa melakukan:
- [ ] Men-debug error Module Federation terkait version mismatch, singleton violation, dan chunk-loading 404 pada network tab dan console.
- [ ] Mengimplementasikan off-main-thread heavy computing pipeline menggunakan Web Worker native atau Comlink tanpa membekukan antarmuka (TBT 0ms).
- [ ] Mengonfigurasi `OffscreenCanvas` untuk mendelegasikan rendering grafis/animasi kompleks langsung dari Worker thread.
- [ ] Mendesain strategi caching Service Worker multi-layer yang mencegah state inkonsistensi (*chunk mismatch*) saat deploy aplikasi skala besar.
- [ ] Menganalisis memory leak pada Worker dan Service Worker menggunakan Chrome DevTools Heap Snapshot dan Allocation Instrumentation.
- [ ] Membangun fallback boundary yang resilient terhadap network failure remote component pada sistem Micro-frontend enterprise.