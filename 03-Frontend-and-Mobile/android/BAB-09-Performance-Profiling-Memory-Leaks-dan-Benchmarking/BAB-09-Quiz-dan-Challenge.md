# BAB 09: Quiz, Challenge, & Knowledge Check
**Performance Profiling, Memory Leaks, & Benchmarking**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Siklus Render Android dan Frame Budget
Jelaskan secara terperinci bagaimana interaksi antara `Choreographer`, `VSYNC` signal, `Main Thread` (UI Thread), dan `RenderThread` bekerja dalam pipeline grafis modern Android (Hardware-accelerated pipeline). Mengapa target render modern berada pada 16.6ms (60 Hz) atau 8.3ms (120 Hz), dan apa konsekuensi mekanis internal pada GPU/BufferQueue ketika komputasi UI Thread dan RenderThread melebihi batas waktu tersebut (*frame drop* / *jank*)?

### Soal 1.2: Mekanisme Garbage Collector (ART Generational Concurrent Copying)
Android Runtime (ART) menggunakan algoritma *Generational Concurrent Copying* (CC) Collector. Jelaskan bagaimana ART membagi heap ke dalam ruang memori (*Young Generation* vs *Old Generation* / *Large Object Space*). Mengapa fenomena *Allocation Churn* (alokasi memori berfrekuensi tinggi dalam durasi sangat singkat) memicu *thread preemption* atau micro-stutters, meskipun CC Collector diklaim bersifat *mostly-concurrent*?

### Soal 1.3: Taksonomi Retensi Objek dan Akar Masalah Memory Leak
Bedakan definisi teknis antara *Memory Bloat*, *Allocation Churn*, dan *Memory Leak*. Ditinjau dari graf objek memori JVM/ART, jelaskan bagaimana sebuah node dapat diidentifikasi sebagai *leaked* oleh GC Root melalui *strongly reachable paths*. Mengapa referensi implisit dari *anonymous inner class*, non-static inner class, atau capturing lambda terhadap lifecycle-bound context (seperti `Activity`) menjadi penyebab utama kegagalan GC dalam mereklamasi memori?

### Soal 1.4: Metode Profiling CPU: Tracing vs Sampling vs System Tracing
Bandingkan secara komparatif tiga metodologi profiling performa CPU berikut:
1. *Method Tracing* (Instrumented)
2. *Callstack Sampling* (Sample-based)
3. *System Tracing* (Perfetto / ATrace)

Evaluasi trade-off dari ketiganya ditinjau dari aspek *runtime overhead*, distorsi pengukuran (*observer effect*), resolusi granularitas data, dan visibilitas context switch / kernel scheduling.

### Soal 1.5: Taksonomi Metrik Start-up & Profil Kompilasi (AOT, JIT, PGO)
Jelaskan perbedaan mendasar antara *Cold Start*, *Warm Start*, dan *Hot Start* dari perspektif operating system (forking Zygote process, inisialisasi class loading, `Application.onCreate()`, dan rendering first frame). Bagaimana integrasi antara *Just-In-Time* (JIT), *Ahead-Of-Time* (AOT), dan *Profile-Guided Optimization* (PGO) via **Baseline Profiles** mampu mereduksi *Cold Start latency* secara drastis?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Internal Engine LeakCanary
Bagaimana LeakCanary mendeteksi retensi objek yang tidak semestinya tanpa mengorbankan performa aplikasi selama proses inspeksi awal? Jelaskan peran teknis dari `ObjectWatcher`, `WeakReference`, dan `ReferenceQueue`. Mengapa LeakCanary sengaja menunda *heap dump* (`android.os.Debug.dumpHprofData()`) sampai tercapai ambang batas ambang retensi (misal: 5 objek tertahan) pada saat UI berada di background?

### Soal 2.2: Deep Dive ANR (Application Not Responding) & Parsing `/data/anr/traces.txt`
Sebuah ANR dipicu jika aplikasi tidak merespons input event dalam waktu 5 detik. Diberikan skenario di mana UI Thread mengalami *Monitor Contention* (terkunci menunggu mutex/synchronized block yang dipegang oleh thread background). Jelaskan langkah-langkah diagnostik dalam membaca file `traces.txt`, mengidentifikasi thread state (`BLOCKED`, `WAITING`, `TIMED_WAITING`), dan menemukan thread pemegang kunci (*lock owner*) yang menyebabkan *deadlock* atau *priority inversion*.

### Soal 2.3: Lifecycle Bitmap & Native Allocation vs Java Heap
Semenjak Android 8.0 (API 26), pixel data Bitmap dipindahkan dari Java Heap kembali ke Native Heap menggunakan pointer `nativePtr` (Skia engine). Jelaskan implikasi arsitektural dari perpindahan ini terhadap pelaporan memori di Android Studio Profiler (`Native` vs `Graphic` vs `Java`). Mengapa pemanggilan `Bitmap.recycle()` tetap relevan secara teknis pada skenario tertentu, dan bagaimana mekanisme `BitmapFactory.Options.inBitmap` serta `Bitmap.Config.HARDWARE` memitigasi tekanan native memory pressure?

### Soal 2.4: Diagnostik Jank Menggunakan Systrace / Perfetto
Saat menganalisis trace interaksi scrolling pada Jetpack Compose/RecyclerView via Perfetto, Anda melihat irisan slice bernama `Choreographer#doFrame` memakan waktu 45ms. Di dalam irisan tersebut terdapat aktivitas:
- `traversal` -> `measure` / `layout` yang memakan waktu 32ms.
- Sub-slice kustom berisi IPC call `BinderProxy.transact`.

Bagaimana Anda mengidentifikasi bahwa terjadi *Layout Thrashing* atau *IPC on Main Thread*? Apa dampak teknis eksekusi Binder synchronous call terhadap scheduler thread kernel (SCHED_FIFO / SCHED_NORMAL) pada RenderThread?

### Soal 2.5: Metodologi Benchmarking: Microbenchmark vs Macrobenchmark
Mengapa pengujian performa mikro (misal: kecepatan parsing JSON atau kalkulasi enkripsi) tidak boleh menggunakan `System.nanoTime()` murni di dalam Android Test runner standar? Jelaskan arsitektur Jetpack `BenchmarkRule` (Microbenchmark) dalam mengontrol *CPU frequency scaling* (thermal throttling), clock locking, dan JIT warm-up cycles dibandingkan dengan `MacrobenchmarkRule` yang mengukur *black-box system metrics* seperti frame-timing dan launch time.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Infinite Feed Memory Leak & Native Crash Out-Of-Memory
*Konteks*: Sebuah aplikasi e-commerce skala enterprise mengalami peningkatan drastis crash rate sebesar 4.2% setelah peluncuran fitur "Infinite Dynamic Feed" berbasis Jetpack Compose. Crash log yang terekam di Google Play Console menunjukkan error `OutOfMemoryError: Failed to allocate a [...] allocation until OOM` dan native signal `SIGSEGV` / `SIGABRT` pada library grafis `libhwui.so`.

*Karakteristik Masalah*:
- Tim monitoring menemukan bahwa Java Heap stabil di rentang 80MB - 120MB.
- Metrik native heap terus naik linear seiring pengguna men-scroll feed, hingga menembus 1.2GB sebelum proses dimatikan paksa oleh Low Memory Killer (LMK).
- Feed menampilkan custom image carousel dengan asynchronous image loading kustom (menggunakan coroutine dan raw Canvas decoding, bukan Coil/Glide).

*Pertanyaan Diagnostik*:
1. Apa hipotesis teknis utama yang menjelaskan mengapa Java Heap stabil namun Native Heap membengkak hingga memicu LMK?
2. Bagaimana Anda merancang investigasi menggunakan Android Studio Memory Profiler (Native Memory Allocation tracking) untuk melacak alokasi C++ / Skia object yang bocor?
3. Rancang strategi arsitektural perbaikan untuk membatasi konsumsi memori grafis (misal: implementasi pool decoder, hardware buffer recycling, dan pemanfaatan `ImageDecoder` dengan subsampling).

### Skenario B: UI Thread Starvation Akibat Reactive Stream & Configuration Change
*Konteks*: Aplikasi perbankan memiliki fitur real-time market tracker yang mengonsumsi websocket stream berkecepatan 50 payload per detik. Komponen UI menggunakan `StateFlow` yang di-collect pada level Fragment/Activity. Saat pengguna memutar orientasi layar (configuration change) secara berulang-ulang, aplikasi mengalami penurunan frame rate dari 120 FPS ke 14 FPS, dan beberapa detik kemudian muncul dialog ANR.

*Karakteristik Masalah*:
- Profiling CPU menunjukkan thread `main` mengalami CPU usage 100%.
- Heap dump menunjukkan terdapat 4 instance dari Activity yang sama tertahan di memori (`retained size` mencapai 350MB).
- LeakCanary melaporkan: `Leak: CoroutineScope capturing outer Activity instance via ViewModel event observer`.

*Pertanyaan Diagnostik*:
1. Mengapa retain instance Activity tersebut dapat melipatgandakan beban eksekusi pada UI Thread secara eksponensial setelah rotasi berkali-kali?
2. Analisis bagaimana lifecycle collection (`repeatOnLifecycle` vs `launchWhenStarted`) berinteraksi dengan StateFlow dan coroutine job cancellation, serta tunjukkan kesalahan struktural yang menyebabkan alokasi collector tidak dihentikan.
3. Tunjukkan skema resolusi komprehensif untuk memutus retaining reference, mencegah *backpressure starvation* pada Main Thread, dan mengisolasi downstream UI update menggunakan `flowOn(Dispatchers.Default)` dan *conflation*.

### Skenario C: Migrasi Arsitektur Feed: Jetpack Compose vs Legacy XML View
*Konteks*: Sebuah aplikasi transportasi online ingin memigrasikan layar "Search & Booking" dari Legacy RecyclerView (XML) ke full Jetpack Compose. Pada perangkat flagship (Pixel 8), Compose feed berjalan lancar pada 120 FPS. Namun, pada perangkat low-end (Android Go Edition, 2GB RAM, MediaTek Quad-core), Compose feed mengalami *frozen frames* sebesar 18%, jauh lebih buruk dibanding implementasi XML lama yang hanya mencatatkan 3% *frozen frames*.

*Karakteristik Masalah*:
- Metrik Macrobenchmark menunjukkan `FrameDurationCpu100` pada Compose membengkak drastis.
- Profiling menggunakan Compose Layout Inspector menunjukkan angka *Recomposition Count* yang eksorbitan pada item-item list yang tidak mengalami mutasi data.
- Profil kompilasi rilis menggunakan model kompilasi default tanpa kustomisasi Baseline Profile.

*Pertanyaan Diagnostik*:
1. Evaluasi akar masalah performa Jetpack Compose pada perangkat berspesifikasi rendah: mengapa overhead Recomposition dan Runtime Snapshot system membebani CPU secara signifikan dibanding model *in-place view mutation* milik View System?
2. Bagaimana teknik audit stabilitas tipe (`@Stable`, `@Immutable`, primitif collections vs `kotlinx.collections.immutable`) dapat digunakan untuk menghilangkan *unnecessary recompositions*?
3. Rancang rencana implementasi rilis produksi yang menggabungkan: (a) Baseline Profiles generasi otomatis via CI/CD, (b) R8 Rule tuning, dan (c) optimasi lazy-layout item reuse strategy untuk memangkas *frozen frames* hingga setara atau melampaui performa legacy XML.

---

## 4. Chapter Challenge

### Tantangan Praktis: Audit, Profiling, dan Optimasi High-Jank & High-Memory Android Application

#### Deskripsi Masalah
Anda menerima sebuah basis kode dari tim legacy: aplikasi pemutar media & kurasi konten bernama **"PulseStream"**. Aplikasi ini memiliki reputasi buruk di Play Store: rating 2.4, rating uninstalls tinggi karena *battery drain*, ANR konstan, dan freeze visual setiap kali pengguna melakukan fast-scrolling pada katalog video.

#### Requirements Teknis
1. **Memory Leak Remediation**:
   - Temukan minimal 3 kebocoran memori tersembunyi pada repository yang diberikan:
     1. Static context reference via Singleton.
     2. Retained listener pada Hardware Sensor / Location Manager.
     3. Capturing lambda di dalam Background Worker/Coroutine yang mengunci `FragmentBinding`.
   - Konfirmasi eliminasi kebocoran menggunakan analisis *Leak Trace* dari LeakCanary dan perbandingan Heap Dump (sebelum vs sesudah).

2. **Frame-Rate Optimization (Jank Busters)**:
   - Identifikasi dan perbaiki masalah *Overdraw* pada hirarki layout (target: maksimum 1x overdraw pada seluruh layar).
   - Optimalkan scrolling list (Compose `LazyColumn` atau RecyclerView) agar mencapai metric **< 1% Janky Frames** (diukur menggunakan Jetpack Macrobenchmark pada emulator/device pengujian target).
   - Singkirkan seluruh operasi I/O dan alokasi objek berat di dalam method gambar (`onDraw()`, Compose measure/layout blocks).

3. **Macrobenchmark & Baseline Profile Deployment**:
   - Buat modul Macrobenchmark baru pada project (`:macrobenchmark`).
   - Tulis skenario pengujian start-up (`StartupBenchmark`) untuk mengukur:
     - `Cold Startup` metrik `Time to Initial Display` (TTID) dan `Time to Full Display` (TTFD).
     - Scroll frame performance (`FrameTimingBenchmark`).
   - Hasilkan file `baseline-prof.txt` yang valid dan integrasikan ke dalam modul `:app`.
   - Buktikan peningkatan metrik startup time minimal **30%** pada mode kompilasi `CompilationMode.Partial(baselineProfile = ...)` dibandingkan `CompilationMode.None()`.

#### Constraints & Aturan Eksekusi
- **Dilarang** mematikan fitur atau simplifikasi UI untuk mencapai performa yang ditargetkan (kompleksitas visual harus tetap identik).
- Tidak boleh menggunakan library caching pihak ketiga selain yang sudah terpasang; optimalisasi cache harus dilakukan pada level arsitektur dan konfigurasi engine image loader yang ada.
- Verifikasi hasil benchmark harus dijalankan pada Release build type dengan flag `isDebuggable = false` dan `R8/Proguard` aktif via *minified sandbox*.

#### Expected Output
1. **Laporan Audit Performa (Markdown)**:
   - Perbandingan metrik *Before vs After*: TTID, TTFD, P50, P90, dan P99 Frame Durations.
   - Diagram Retensi Memori (Root to Leaf) dari kebocoran memori yang telah diisolasi.
   - Screenshot / Perfetto Trace Slice yang menunjukkan hilangnya frame spikes.
2. **Pull Request / Code Patch**:
   - Refactor struktural kode sumber aplikasi.
   - Konfigurasi modul `:macrobenchmark` lengkap dengan file class test `BaselineProfileGenerator.kt` dan `ScrollPerformanceBenchmark.kt`.
   - File `baseline-prof.txt` terverifikasi.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal pipeline rendering Android: Peran VSYNC, Choreographer, Main Thread, RenderThread, SurfaceFlinger, dan Hardware Composer (HWC).
- [ ] Cara kerja ART Generational Concurrent Copying Garbage Collector dan akar pemicu GC pauses.
- [ ] Anatomi memory graph di runtime: GC Roots, Path to Root, Dominator Tree, Shallow Size vs Retained Size.
- [ ] Perbedaan fungsionalitas dan overhead antara tracing tools: Android Studio Profiler, Perfetto, Systrace, dan Simpleperf.
- [ ] Siklus kompilasi Android runtime: Peran Interpreter, JIT compilation, AOT (dex2oat), Cloud Profiles, dan Baseline Profiles.
- [ ] Penyebab utama ANR: UI thread lock contention, heavy I/O, synchronous Binder calls, dan starvation akibat background worker.
- [ ] Arsitektur alokasi grafis Bitmap: Evolusi dari Dalvik Heap (pre-3.0), Native Heap (3.0-7.1 via ashmem), Java Heap (8.0-), hingga Hardwared Bitmaps via GraphicBuffer.
- [ ] Compose performance mechanics: Stability inference rules, Recomposition vs Relayout vs Redraw phases, Smart Recomposition limits.

### Saya tidak perlu menghafal:
- [ ] Nilai hexa memory address mentah dari pointer objek pada file hprof dump.
- [ ] Seluruh flag C++ compiler internals untuk building `libart.so`.
- [ ] Format biner spesifik dari serialization protocol protobuf Perfetto.
- [ ] Sintaks exact perintah shell `dumpsys gfxinfo` secara harfiah (cukup pahami metrik output utamanya).

### Saya harus bisa melakukan:
- [ ] Menganalisis file `.hprof` menggunakan Android Studio Memory Profiler atau Eclipse Memory Analyzer (MAT) untuk menemukan retained reference path.
- [ ] Mengonfigurasi dan mengoperasikan LeakCanary, serta menginterpretasikan stack trace kebocoran memori hingga ke layer arsitektur kode.
- [ ] Menjalankan rekaman Perfetto via Android Studio atau CLI, menavigasi trace slices, dan mendiagnosis bottleneck frame drops (Layout Thrashing, Long UI measure, GPU wait).
- [ ] Membaca dan membedah file ANR (`/data/anr/traces.txt`) untuk mengidentifikasi deadlocks atau synchronous locks pada Main Thread.
- [ ] Membangun dan mengonfigurasi modul Jetpack Macrobenchmark untuk mengotomasi profiling TTID/TTFD dan frame timing.
- [ ] Menghasilkan Baseline Profiles (`BaselineProfileGenerator`) untuk meningkatkan startup performance dan frame rate aplikasi pada production environment.
- [ ] Menggunakan Layout Inspector untuk mengaudit recomposition count dan mengidentifikasi penyebab *skipping failure* pada Jetpack Compose.