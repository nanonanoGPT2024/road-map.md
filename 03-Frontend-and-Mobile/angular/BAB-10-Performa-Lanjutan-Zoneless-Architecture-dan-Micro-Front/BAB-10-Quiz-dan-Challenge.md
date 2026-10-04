# BAB 10: Quiz, Challenge, & Knowledge Check
**Performa Lanjutan, Zoneless Architecture, & Micro-Frontends**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Mekanisme Monkey-Patching Zone.js vs. Zoneless Signal Notification**
   Jelaskan bagaimana `zone.js` melakukan *monkey-patching* terhadap API asynchronous browser (seperti `setTimeout`, `fetch`, `addEventListener`) untuk memicu *change detection*, dan bandingkan mekanisme ini dengan model Zoneless modern (`provideExperimentalZonelessChangeDetection()`). Bagaimana Angular Zoneless mengetahui secara presisi kapan harus menjadwalkan *render pass* tanpa ketergantungan pada global monkey-patching?

2. **Anatomi Internal Deferrable Views (`@defer`)**
   Bagaimana Angular Compiler memecah dependensi komponen di dalam blok `@defer` menjadi *dynamic chunk* terpisah saat build time? Jelaskan perbedaan mendasar antara pemicu render (*render trigger*) dan pemicu pra-pemuatan (*prefetch trigger*), serta bagaimana interaksi antara `on viewport` dan `IntersectionObserver` diimplementasikan secara efisien.

3. **Prinsip Sharing Scope pada Webpack Module Federation & Native Federation**
   Dalam arsitektur Micro-Frontend berbasis Module Federation, jelaskan bagaimana mekanisme `shared` configuration bekerja di tingkat runtime. Apa konsekuensi teknis jika Remote Micro-Frontend dan Shell/Host gagal bersepakat pada *singleton dependency* untuk `@angular/core` atau library berbasis state global?

4. **Evolusi `ChangeDetectionStrategy.OnPush` Menuju Zoneless**
   Pada era Zone.js, `ChangeDetectionStrategy.OnPush` bergantung pada mutasi `@Input()` reference, synchronous event handling di dalam template, atau pemanggilan manual `ChangeDetectorRef.markForCheck()`. Mengapa dalam arsitektur Zoneless murni, paradigma `markForCheck()` mulai usang dan digantikan sepenuhnya oleh notifikasi reaktivitas berbasis Signal (`signal()`, `computed()`)?

5. **Native Federation (ESM/Import Maps) vs. Webpack Module Federation**
   Bandingkan arsitektur Native Federation yang memanfaatkan *native browser standards* (seperti Browser ESM dan Import Maps) dengan Webpack Module Federation klasik. Jelaskan perbedaannya dari aspek build speed (misal: integrasi dengan esbuild/Vite), dynamic loading runtime, dan isolasi *scope*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Investigasi Detached DOM Trees & Memory Leak pada Dynamic Remote Destruction**
   Saat navigasi Angular Router berpindah dari *Remote Micro-Frontend A* ke *Remote Micro-Frontend B*, profiling memori via Chrome DevTools menunjukkan penumpukan *Detached HTMLElement* dan *Retained Size* yang terus membesar. Bagaimana Anda melacak apakah *leak* tersebut berasal dari uncleaned event listener pada *window/document*, RxJS *subscription* yang tidak di-unsubscribe di Remote, atau sisa referensi injection token pada Root Injector Shell?

2. **Microtask Coalescing & Tick Starvation pada Aplikasi Zoneless**
   Pada aplikasi Zoneless yang menerima pembaruan data frekuensi tinggi via WebSocket, ribuan Signal termutasi secara simultan. Jelaskan bagaimana *scheduler* internal Angular melakukan *microtask coalescing* untuk menggabungkan pembaruan tersebut menjadi satu *render frame*. Apa indikator terjadinya *tick starvation* (UI lagging) dan bagaimana cara memitigasinya?

3. **Debugging Hydration Mismatch Saat Penggunaan `@defer` dengan SSR**
   Aplikasi Angular 17+ menggunakan Server-Side Rendering (SSR) dengan Hydration aktif. Pada template terdapat `@defer (on timer(5s))` yang membungkus komponen berat. Di browser client, console memunculkan error *NG0500: During hydration, Angular expected an element to match...*. Jelaskan secara teknis mengapa *hydration mismatch* ini terjadi antara Server DOM dan Client DOM, dan bagaimana konfigurasi server-side rendering fallback (`@placeholder`) harus diatur untuk mencegah *DOM thrashing*.

4. **Shared Dependency Version Mismatch & Broken Injection Context**
   Sebuah Host Shell berjalan di Angular `18.1.0`, sedangkan Remote MFE di-deploy secara independen dengan Angular `18.2.0`. Jika `shared` dependency diset dengan `singleton: false` atau `strictVersion: true`, apa manifestasi runtime error yang sering muncul terkait `inject()` function execution context (`NG0203: inject() must be called from an injection context`)? Bagaimana cara Module Federation menangani fallback runtime factory-nya?

5. **Bottleneck Analysis Menggunakan Angular DevTools Profiler**
   Saat melakukan profiling pada aplikasi Zoneless hybrid (sebagian komponen menggunakan Signals, sebagian komponen legacy OnPush), Anda melihat adanya *Change Detection Loop* yang tidak berkesudahan di DevTools flame chart. Bagaimana cara mengidentifikasi apakah root cause-nya adalah *circular computed signal dependency*, side-effect di dalam `effect()`, atau template expression yang mengembalikan referensi objek baru setiap siklus evaluasi?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck FinTech Dashboard (High-Frequency Trading)
Sebuah platform dashboard perdagangan crypto enterprise mengalami drop frame rate drastis dari 60 FPS ke 12 FPS saat volume transaksi pasar melonjak tajam (menerima ~800 payload WebSocket/detik). Arsitektur saat ini masih menggunakan Angular monolitik dengan Zone.js aktif. DevTools Performance panel menunjukkan bahwa 85% waktu CPU dihabiskan dalam eksekusi fungsi `ZoneTask.invoke` dan `ApplicationRef.tick()`, menyebabkan *Total Blocking Time (TBT)* mencapai 4.2 detik.
* **Pertanyaan Diagnostik & Solutif:**
  1. Bagaimana Anda merefaktor jalur data WebSocket ini menggunakan `ngZone.runOutsideAngular` atau migrasi ke Zoneless Signal primitive untuk memutus eksekusi siklus *change detection* global pada setiap payload?
  2. Bagaimana mendesain strategi rendering komponen grafik/order-book agar buffer update data di-throttle pada frekuensi refresh rate layar (misal: `requestAnimationFrame`) tanpa memicu re-render pada seluruh component tree?

### Skenario B: Race Condition State & Session Desynchronization pada MFE E-Commerce
Sistem e-commerce enterprise mengadopsi arsitektur Micro-Frontend:
- **Host Shell**: Mengelola otentikasi global, session token, dan layout.
- **Remote A (Cart)**: Mengelola keranjang belanja pengguna.
- **Remote B (Checkout)**: Mengelola validasi pembayaran dan order placement.
Token otentikasi disimpan di shared memory state (RxJS BehaviorSubject pada shared library). Ketika token kedaluwarsa, Host Shell memicu *silent refresh*. Namun, terjadi *race condition*: Remote B memicu request API `POST /checkout` menggunakan token lama yang kedaluwarsa sebelum Remote A selesai memvalidasi diskon cart, menghasilkan error 401 dan state cart lokal ter-desinkronisasi dari backend.
* **Pertanyaan Diagnostik & Solutif:**
  1. Identifikasi kegagalan arsitektur dalam manajemen state terdistribusi di atas. Mengapa penggunaan shared memory state via singleton library rentan terhadap *race condition* lintas bundle?
  2. Rancang arsitektur komunikasi lintas MFE yang decoupled, idempoten, dan tahan *race condition* (misalnya menggunakan Event-Driven Bus via `CustomEvent`/BroadcastChannel dengan schema validation, atau reactive query synchronization) untuk menjamin konsistensi transaksi checkout.

### Skenario C: Migrasi Monolith Legacy ke Zoneless Micro-Frontends
Sebuah aplikasi web perbankan monolitik dengan 450+ module Angular berbasis `NgModule` dan Zone.js perlu dimodernisasi. Manajemen menuntut:
- Tim independen (5 tim fitur) harus bisa deploy tanpa koordinasi build (*independent CI/CD*).
- Core Web Vitals (LCP < 2.0s, INP < 100ms) harus tercapai.
- Migrasi harus bertahap (*strangler fig pattern*), mendukung koeksistensi module legacy dan module zoneless baru.
* **Pertanyaan Diagnostik & Solutif:**
  1. Tentukan pilihan arsitektur antara **Webpack Module Federation** vs. **Native Federation**: Apa trade-off build tooling (Webpack vs esbuild), deployment agility, dan overhead bundle browser?
  2. Bagaimana merancang strategi isolasi CSS/styling antar micro-frontend (misal: Tailwind scoping, CSS Modules, atau Shadow DOM) agar style Remote tidak bocor (*style bleeding*) ke Host atau Remote lainnya?
  3. Bagaimana strategi mengoperasikan hybrid runtime di mana Host Shell sudah Zoneless (`provideExperimentalZonelessChangeDetection`), namun memuat Remote legacy yang masih memerlukan notifikasi CD konvensional?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Zoneless Analytics Terminal with Native Federation

#### Problem Statement
Anda ditugaskan membangun prototipe arsitektur untuk sistem analitik telemetri IoT industri berskala besar. Sistem harus mampu merender ribuan metrics stream secara real-time tanpa UI jank, modular dalam bentuk Micro-Frontend, dan mengeliminasi Zone.js secara total untuk mencapai efisiensi memori dan waktu eksekusi CPU optimal.

#### Technical Requirements
1. **Shell Application (Host)**:
   - Dikonfigurasi menggunakan **Angular 18+ Standalone API** dan **Native Federation**.
   - Mengaktifkan `provideExperimentalZonelessChangeDetection()`. Tidak boleh ada import `zone.js` dalam runtime bundle.
   - Mengimplementasikan layout dinamis yang memuat Remote MFE secara asynchronous via router menggunakan `loadComponent()` / `loadRemoteModule()`.
2. **Telemetry Remote MFE**:
   - Dideploy sebagai micro-frontend mandiri via Native Federation.
   - Menyediakan komponen `TelemetryStreamComponent` yang menerima *mock high-frequency data stream* (50 tick/detik via RxJS `interval`).
   - Transformasi stream ke UI dilakukan murni menggunakan Angular Signals (`toSignal`, `signal`, `computed`).
   - Implementasikan *virtualized rendering* atau *coalesced render updates* (UI hanya me-refresh ringkasan data setiap ~100ms meskipun stream data lebih cepat).
3. **Optimized Resource Loading**:
   - Gunakan blok `@defer (on viewport; prefetch on idle)` untuk memuat sub-komponen visualisasi grafik berat (`MetricChartComponent`) hanya saat elemen mendekati viewport layar pengguna.
   - Sediakan block `@placeholder`, `@loading`, dan `@error` secara semantik.
4. **Resilient Inter-App Communication**:
   - Komunikasi antara Shell (pengatur filter global: *Device ID*) dan Remote Telemetry harus diisolasi menggunakan abstraksi event-driven berbasis `CustomEvent` yang *type-safe* atau lightweight shared contract service, tanpa membuat coupling dependency build-time.

#### Constraints
- **Strictly Zoneless**: Build output analyzer tidak boleh mendeteksi `zone.js` masuk ke runtime bundle.
- **Zero Style Leakage**: Styling pada Remote (misalnya theme dark-mode) tidak boleh merusak elemen Shell atau remote lain.
- **Error Boundary**: Jika Remote MFE offline/gagal dimuat, Shell tidak boleh crash (white-screen of death) dan harus menampilkan UI fallback graceful.

#### Expected Output
1. File konfigurasi Native Federation: `federation.config.js` untuk Host dan Remote.
2. File bootstrap Zoneless: `app.config.ts` untuk Host dan Remote.
3. Kode implementasi `telemetry-stream.component.ts` berbasis Signals murni.
4. Kode integrasi routing Host dengan dynamic loading Remote dan handling fallback error.
5. Screenshot / Profiler Dump report text yang membuktikan tidak ada Zone task dan frame rate tetap stabil di ~60 FPS saat data streaming berjalan.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme kerja internal `Zone.js` (monkey patching microtask, macrotask, event loop) dan alasan Angular beralih ke Zoneless.
- [ ] Arsitektur internal Zoneless Angular: bagaimana Signal Producer-Consumer dependency graph memberitahu scheduler `ApplicationRef.tick()` melalui microtask queue.
- [ ] Siklus hidup dan kompilasi Deferrable Views (`@defer`, `@loading`, `@placeholder`, `@error`) serta triggering conditions-nya.
- [ ] Prinsip kerja Module Federation: Shared Scope, Container API, Remote Entry point, dan Manifest Resolution.
- [ ] Perbedaan implementasi Webpack Module Federation vs. Native Federation (ESM, Import Maps, esbuild support).
- [ ] Penyebab umum dan mitigasi Hydration Error (`NG0500`) pada Angular SSR saat berinteraksi dengan dynamic runtime injection dan `@defer`.
- [ ] Strategi isolasi Style & CSS lintas Micro-Frontend (Shadow DOM encapsulation vs. PostCSS namespace scoping).

### Saya tidak perlu menghafal:
- [ ] Seluruh tabel konfigurasi properti Webpack Module Federation (`shareScope`, `eager`, `singleton`) secara sintaksis di luar kepala; cukup pahami konsep semantik konfigurasinya.
- [ ] Implementasi byte-level algoritma diffing internal Angular LView/TView data structure.
- [ ] Daftar lengkap ribuan API browser yang di-monkey-patch oleh `zone.js`.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi aplikasi Angular full Zoneless menggunakan `provideExperimentalZonelessChangeDetection()` dan membuang `zone.js` dari `angular.json` / `polyfills`.
- [ ] Melakukan refactor komponen legacy berbasis `ChangeDetectorRef.markForCheck()` dan RxJS Subscription menjadi model reaktif murni berbasis Angular Signals (`computed`, `toSignal`).
- [ ] Mengaudit, mendeteksi, dan memperbaiki memory leak pada integrasi Micro-Frontend menggunakan Chrome DevTools Memory Heap Snapshot dan Allocation Instrumentation.
- [ ] Mengonfigurasi Native Federation untuk komunikasi Host-Remote berbasis Standalone Components.
- [ ] Menggunakan Angular DevTools Profiler untuk menganalisis frame rate drop, CD duration, dan mengeliminasi redundant UI paint loops.
- [ ] Mengimplementasikan dynamic error boundaries saat remote micro-frontend mengalami crash pada runtime network fetching.