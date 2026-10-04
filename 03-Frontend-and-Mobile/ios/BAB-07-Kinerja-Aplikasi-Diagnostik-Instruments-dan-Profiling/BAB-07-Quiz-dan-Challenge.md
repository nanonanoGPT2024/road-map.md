# BAB 07: Quiz, Challenge, & Knowledge Check
**Kinerja Aplikasi, Diagnostik Instruments, & Profiling**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Jelaskan perbedaan arsitektural antara *Clean Memory*, *Dirty Memory*, dan *Compressed Memory* pada iOS.** Mengapa sistem operasi iOS tidak menggunakan *swap disk* seperti macOS ketika kehabisan RAM, dan bagaimana mekanisme pembunuhan proses oleh *Jetsam daemon* bekerja berdasarkan parameter *dirty memory footprint*?
2. **Definisikan metrik *Hitch Rate* (Scroll Hitch)** sesuai spesifikasi modern Apple (WWDC standard). Apa perbedaan matematis serta penyebab mendasar antara **Commit Hitch** (yang terjadi pada proses aplikasi) dan **Render Hitch** (yang terjadi pada Render Server)?
3. **Analisis siklus hidup *Render Pipeline* pada Core Animation** mulai dari fase *Layout*, *Display*, *Prepare*, *Commit*, hingga pemrosesan oleh *Render Server* dan GPU execution. Di fase manakah operasi *image decompression* secara *default* dieksekusi jika tidak dilakukan secara asinkron?
4. **Secara internal, bagaimana Swift Runtime mengelola *Side Table* untuk alokasi objek?** Jelaskan konsekuensi kinerja (memori overhead dan CPU cycles) ketika sebuah objek memiliki referensi `weak` dibandingkan referensi `unowned`, serta kapan tepatnya *Side Table* dialokasikan dan dihancurkan.
5. **Mengapa penggunaan API `os_signpost` jauh lebih direkomendasikan untuk analisis performa produksi dan diagnostik Instruments** dibandingkan mekanisme logging konvensional seperti `print()` atau `NSLog()`? Jelaskan dampaknya terhadap *observer effect* dan latensi eksekusi *thread*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mekanisme *Offscreen Rendering*:** Sebutkan 4 kondisi spesifik pada level `CALayer` yang memicu GPU untuk mengalokasikan *offscreen render pass*. Jelaskan secara teknis mengapa *offscreen rendering* memotong *memory bandwidth* GPU secara drastis melalui mekanisme *context switching* antar *framebuffers*.
2. **Deteksi *Abandoned Memory* vs *Memory Leaks*:** Tool *Leaks Instrument* gagal mendeteksi lonjakan memori pada sebuah *singleton cache* yang terus membesar hingga memicu OOM (*Out Of Memory*). Jelaskan mengapa *Leaks Instrument* menganggap memori tersebut valid, dan uraikan metodologi profiling menggunakan **Allocations Instrument (Generational Analysis / Mark Generation)** untuk mengisolasi akar masalahnya.
3. **Priority Inversion pada GCD & Swift Concurrency:** Bagaimana mekanisme kerja *Quality of Service (QoS)* propagation di GCD ketika *thread* bertaraf `.userInteractive` menunggu mutual exclusion lock (*os_unfair_lock* atau *actor isolation*) yang sedang dipegang oleh *thread* bertaraf `.background`? Apa yang terjadi jika sistem gagal melakukan *priority escalation*?
4. **Analisis *Main RunLoop Stalls*:** Anda mendapati UI terhenti (*hang*) selama 250ms saat pengguna mengetuk tombol. Bagaimana cara membedakan secara presisi di Time Profiler apakah *stall* tersebut diakibatkan oleh:
   - Terblokirnya *main thread* oleh I/O sinkron (*kernel wait*).
   - Beban komputasi berlebih (*high CPU core saturation*).
   - Antrean pembaruan hierarki Auto Layout yang terlalu dalam (*recursive layout passes*).
5. **Dinamika `@autoreleasepool` pada High-Throughput Processing:** Dalam sebuah *loop* pemrosesan 10.000 data gambar berukuran besar menggunakan Swift, konsumsi memori melonjak hingga 1.5 GB sebelum akhirnya anjlok seketika saat fungsi selesai. Mengapa ARC tidak langsung mendealokasikan memori tersebut di setiap iterasi loop, dan bagaimana penempatan struktural `@autoreleasepool` memanipulasi *high-water mark* memori?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Masalah Bottleneck & Frame Drops Parah pada Infinite Feed
Sebuah aplikasi *social commerce* dengan `UICollectionView` menggunakan *compositional layout* dan *custom cells* mengalami *frame rate drop* ekstrem (dari 120 FPS ProMotion anjlok hingga 22–34 FPS) saat pengguna melakukan *fast-scrolling*. Sel berisi avatar lingkaran, teks berformat *rich-text*, serta gambar produk beresolusi tinggi dari CDN.
* **Pertanyaan Diagnostik:**
  1. Bagaimana langkah sistematis Anda memvalidasi apakah bottleneck bersumber dari CPU (App Process), CPU (Render Server), atau GPU menggunakan Instruments (Time Profiler & Core Animation template)?
  2. Jika ditemukan bahwa GPU mengalami *load* tinggi akibat *offscreen rendering* pada avatar lingkaran (`layer.cornerRadius` + `layer.masksToBounds = true`) dan bayangan kartu (`layer.shadowPath = nil`), solusi komputasi apa yang harus diterapkan pada *pipeline* rendering layer tersebut tanpa mengorbankan estetika desain?
  3. Bagaimana strategi *downsampling* dan *asynchronous decoding* diimplementasikan menggunakan `CGImageSourceCreateThumbnailAtIndex` untuk mencegah saturasi memori pada fase *Prepare* Core Animation?

### Skenario B: Race Condition & Memory Corruption Pasca-Migrasi Swift Concurrency
Pasca migrasi modul *networking & image caching* dari completion handler (GCD) ke Swift Concurrency (`async/await` & `actor`), crash rate aplikasi naik sebesar 4.2% di produksi dengan log: `EXC_BAD_ACCESS (KERN_INVALID_ADDRESS)` yang sporadis dan sulit direproduksi di lingkungan *simulator*. Crash terjadi ketika banyak sel seluler membatalkan task pengunduhan secara bersamaan saat di-*scroll*.
* **Pertanyaan Diagnostik:**
  1. Bagaimana fenomena *Actor Reentrancy* dapat menciptakan kondisi *data race* atau inkonsistensi *state* saat operasi *caching* melintasi *suspension points* (`await`), dan bagaimana hal tersebut bisa berujung pada memory corruption atau referensi pointer invalid?
  2. Perangkat diagnostik apa di Xcode (seperti *Thread Sanitizer*, *Concurrency Diagnostics*, atau *Zombie Objects*) yang harus diaktifkan, dan bagaimana konfigurasi runtime-nya untuk menangkap anomali akses memori konkurensi ini?
  3. Rancanglah solusi isolasi konkurensi yang *thread-safe* untuk membatalkan `Task` dan membersihkan `URLSessionDataTask` secara aman tanpa menimbulkan *race window* antara pembatalan dan pemulihan *buffer*.

### Skenario C: Arsitektur & Trade-off Cache Video Berdurasi Singkat (Short-form Video Engine)
Tim Anda merancang arsitektur pemutar video pendek (mirip TikTok/Reels) yang menggunakan `AVPlayerLooper`. Terdapat dua opsi arsitektur manajemen memori *cache*:
- **Opsi 1 (Aggressive Pre-buffering):** Menjaga 5 instance `AVPlayer` terisi penuh di memori untuk transisi instan (0ms latency), dengan konsekuensi *dirty memory footprint* mendekati batas kritis perangkat low-end (misal: iPhone SE gen 2 / iPhone 8).
- **Opsi 2 (Lazy-Loading & On-Demand Purging):** Hanya memuat 1 video aktif dan 1 video berikutnya, memanfaatkan *disk-caching proxy* lokal dan `CVPixelBufferPool` daur ulang, namun membutuhkan latensi pemutaran 50–100ms saat di-*swipe*.
* **Pertanyaan Diagnostik:**
  1. Berdasarkan metrik arsitektur sistem operasi iOS (Jetsam threshold, thermal throttling state, dan battery drain), parameter kuantitatif apa saja yang harus dijadikan indikator *kill-switch* dinamis untuk menurunkan Opsi 1 menjadi Opsi 2 secara *runtime*?
  2. Bagaimana Anda memanfaatkan `os_proc_available_memory()` dan `MetricKit` (`MXCPUExceptionMetric`, `MXDiskWriteExceptionMetric`) untuk mengotomatisasi evaluasi performa *cache* di level CI/CD dan rilis bertahap (*staged rollout*)?

---

## 4. Chapter Challenge

### Tantangan Praktis: Remidiasi Zero-Hitch Feed Framework & Memory Leak Remediation

#### Problem Statement
Anda menerima sebuah basis kode modul galeri media ("MegaGallery") yang mengalami degradasi performa akut:
1. *Scroll hitch rate* berada pada angka **18.4 ms/s** (ambang batas kritis Apple adalah > 5 ms/s).
2. Terjadi lonjakan *dirty memory* hingga mencapai **650 MB** setelah melakukan scroll 50 halaman, yang secara konsisten memicu *crash* Jetsam pada perangkat dengan RAM 3GB/4GB.
3. Alokasi closure delegate pada komponen sel teridentifikasi membentuk *strong reference cycle* (retain cycle) dengan kontroler utama.

#### Requirements
1. **Instrument Baseline Analysis:** Rekam dan dokumentasikan metrik awal menggunakan Instruments (*Time Profiler*, *Allocations*, dan *Core Animation*) yang menunjukkan titik kritis:
   - Persentase CPU time pada *Main Thread* saat scrolling.
   - Grafik pertumbuhan alokasi memori (*Allocations generation trace*).
   - Jumlah *offscreen rendered frames*.
2. **Remidiasi Zero-Hitch:**
   - Implementasikan *asynchronous image downsampling* ke ukuran *bounding box* tampilan sebelum rendering, menggunakan background queue / cooperative thread pool.
   - Hilangkan seluruh operasi pemotongan sudut berbasis GPU (*offscreen masking*) dan ganti dengan *Core Graphics pre-rendered bezier clipping* atau `UIBackgroundConfiguration`.
   - Pastikan teks di-render menggunakan *pre-computed text layout engine* (`NSTextLayoutManager` / `TextKit 2`) di luar *main thread* jika diperlukan.
3. **Memory Neutrality Implementation:**
   - Putus semua retain cycle menggunakan referensi `weak` eksplisit dan bersihkan *event-listener closures*.
   - Bungkus proses *batch extraction* metadata gambar menggunakan struktur `@autoreleasepool`.
   - Terapkan kebijakan *eviction* berbasis `NSCache` yang merespons `UIApplication.didReceiveMemoryWarningNotification` dengan pembersihan total.
4. **Telemetri & Benchmarking:**
   - Sematkan pengukuran latensi menggunakan subsistem `os_signpost` (kategori: `"CellRendering"`, `"ImageDecompress"`).
   - Tambahkan *unit/performance test* berbasis `XCTOSSignpostMetric` dan `XCTMemoryMetric` yang memverifikasi kode baru tidak melewati batas regresi.

#### Constraints
- **Target Platform:** iOS 16.0+.
- **FPS Target:** Stabil di 60 FPS (non-ProMotion) dan 120 FPS (ProMotion devices); *Scroll Hitch Rate* harus **< 2.5 ms/s**.
- **Memory Ceiling:** *Dirty memory footprint* tidak boleh melebihi **95 MB** dalam kondisi pengujian beban scroll 100 entri gambar beresolusi 4K.
- **Dependencies:** Dilarang menggunakan pustaka pihak ketiga (misal: SDWebImage, Kingfisher). Seluruh algoritma *downsampling*, *caching*, dan *concurrency* wajib menggunakan API bawaan Foundation, UIKit, dan Core Graphics.

#### Expected Output
1. File kode perbaikan:
   - `OptimizedFeedViewController.swift`
   - `FastMediaCell.swift`
   - `DecoupledImagePipeline.swift`
2. Berkas pengujian performa `FeedPerformanceTests.swift` yang memanfaatkan `measure(metrics:)`.
3. Laporan Teknis Markdown ringkas (Executive Summary Profiling) berisi:
   - Tabel komparasi Sebelum vs Sesudah (Hitch Rate, Peak Memory, Main Thread Hang Time).
   - Analisis screenshot jejak *Instruments trace* yang membuktikan hilangnya alokasi tak wajar dan hilangnya *offscreen passes*.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batasan memori absolut iOS (Jetsam limits) dan perbedaan fundamental antara *resident memory*, *dirty memory*, dan *virtual memory footprint*.
- [ ] Arsitektur internal Core Animation Pipeline dan perbedaan peran CPU (App), Render Server, serta GPU hardware.
- [ ] Definisi teknis metrik *Hitch Rate* Apple (Commit Hitches vs Render Hitches) dan ambang batas performa visual (WWDC metrics).
- [ ] Mekanisme kerja ARC di level assembly/runtime: *Retain count*, *Side Table pointer*, *Inline ref counts*, dan *Destructor invocation*.
- [ ] Dampak arsitektural dari operasi pemicu *Offscreen Rendering* (`layer.cornerRadius`, `masksToBounds`, `shouldRasterize`, `shadowPath`, `layer.allowsGroupOpacity`).
- [ ] Perilaku *RunLoop* iOS (kategori mode: `.default`, `.tracking`, `.commonModes`) serta bagaimana penguncian *RunLoop* memicu *system watchdog termination* (0x8badf00d).
- [ ] Pola kerja `os_signpost` dan bagaimana mengaitkannya dengan visualizer kustom di Instruments.

### Saya tidak perlu menghafal:
- [ ] Nilai numerik heksadesimal dari alamat *Side Table* atau offset pointer internal Swift Object Header.
- [ ] Ukuran pasti ambang batas RAM Jetsam dalam megabyte untuk setiap tipe model iPhone lama (karena dinamis dan bervariasi per konfigurasi kernel iOS).
- [ ] Struktur internal byte-per-byte dari representasi biner file `.trace` bawaan Xcode Instruments.
- [ ] Setiap baris kode interface privat Core Animation (`CA::Render::*`).

### Saya harus bisa melakukan:
- [ ] Melakukan profiling aplikasi secara mandiri menggunakan Instruments template: **Time Profiler**, **Allocations**, **Leaks**, dan **Core Animation Hitches**.
- [ ] Mengidentifikasi dan memperbaiki *retain cycles* menggunakan kombinasi *Xcode Memory Graph Debugger* dan *Instruments Allocations (Generations)*.
- [ ] Mengimplementasikan *zero-copy* atau *efficient image downsampling* menggunakan Core Graphics API tanpa memuat seluruh *full-resolution buffer* ke RAM.
- [ ] Mengonfigurasi dan mengoperasikan *Thread Sanitizer (TSan)* untuk mendeteksi *data races* pada aplikasi berbasis GCD maupun Swift Concurrency.
- [ ] Menulis performa otomatis (*performance unit tests*) menggunakan `XCTest` dengan metrik `XCTClockMetric`, `XCTMemoryMetric`, dan `XCTCPUMetric`.
- [ ] Membaca serta menginterpretasikan crash log berformat IPS, khususnya kode terminasi `0x8badf00d` (Watchdog), `EXC_RESOURCE (CPU/Disk)`, dan `0xDEAD10CC`.