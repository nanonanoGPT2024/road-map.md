# BAB 03: Quiz, Challenge, & Knowledge Check
**Arsitektur UI Imperatif & Pola Klasik UIKit**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Siklus Hidup UIViewController dan Determinasi Geometri Tampilan
Jelaskan urutan eksekusi metode siklus hidup `UIViewController` mulai dari inisialisasi hingga tampilan muncul di layar (`loadView`, `viewDidLoad`, `viewWillAppear`, `viewWillLayoutSubviews`, `viewDidLayoutSubviews`, `viewDidAppear`). Pada tahap mana `view.frame` atau `view.bounds` pertama kali dijamin memiliki dimensi riil sesuai ukuran layar perangkat target (bukan *placeholder* dari XIB/Storyboard atau *frame zero*), dan mengapa melakukan mutasi layer berbasis ukuran (seperti `CAGradientLayer.frame`) di dalam `viewDidLoad` merupakan anti-pattern struktural?

### Soal 1.2: Dualitas UIView dan CALayer dalam Rendering Pipeline
`UIView` bertindak sebagai pembungkus (*wrapper*) tipis di atas `CALayer`. Jelaskan pembagian tanggung jawab arsitektural antara keduanya terkait *event handling*, rendering konten, dan animasi. Mengapa manipulasi properti animasi pada `CALayer` secara *default* memicu *implicit animation*, sedangkan pada `UIView` animasi implisit tersebut dinonaktifkan kecuali dieksekusi di dalam blok `UIView.animate`? Mekanisme internal UIKit apa yang mengontrol perilaku ini?

### Soal 1.3: Siklus Update Auto Layout dan Mekanisme Deferred Layout Pass
Auto Layout tidak langsung mengkalkulasi ulang koordinat visual seketika sebuah *constraint* diubah. Jelaskan konsep *deferred layout pass* pada UIKit RunLoop. Analisis perbedaan mendasar antara:
1. `setNeedsLayout()`
2. `layoutIfNeeded()`
3. `setNeedsUpdateConstraints()`
4. `updateConstraintsIfNeeded()`

Bagaimana urutan eksekusi pass *update constraints* dan *layout pass* bekerja dalam satu iterasi RunLoop?

### Soal 1.4: Mekanisme Responder Chain dan Algoritma Hit-Testing
Ketika sebuah interaksi sentuhan (*touch event*) terjadi pada layar, bagaimana UIKit menentukan target visual penerima *event* pertama (*initial first responder*)? Jelaskan implementasi rekursif internal dari metode `hitTest(_:with:)` dan hubungannya dengan `point(inside:with:)`. Apa yang terjadi pada alur penjaluran event jika sebuah `subview` berada di luar batas `bounds` dari *parent view*-nya (`clipsToBounds = false`), dan bagaimana cara memperbaikinya?

### Soal 1.5: Siklus Hidup Daur Ulang Sel (Cell Reuse Lifecycle)
Jelaskan alur kerja daur ulang sel pada `UICollectionView` / `UITableView` yang menggunakan mekanisme `dequeueReusableCell`. Mengapa implementasi pembersihan state internal dan pembatalan operasi asinkron (seperti unduhan gambar melalui URLSession atau Task) harus diletakkan pada `prepareForReuse()` daripada di dalam metode konfigurasi sel atau delegasi `cellForItemAt`? Apa dampak kegagalan pembersihan state ini terhadap konsistensi visual saat *fast-scrolling*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Kompleksitas Komputasi Cassowary Algorithm dan Layout Churn
Mesin Auto Layout UIKit ditenagai oleh *Cassowary constraint-solving algorithm*. Jelaskan bagaimana penambahan *constraint* dinamis yang berlebihan atau penggunaan hierarki view yang terlalu dalam (*deeply nested views*) dapat memicu *exponential layout cost* $O(2^n)$ alih-alih $O(n)$. Apa yang dimaksud dengan *layout thrashing/churning*, dan bagaimana cara mendiagnosis serta mengisolasi siklus rekursif layout (*layout feedback loops*) yang memicu crash atau pembekuan antarmuka?

### Soal 2.2: Memory Leaks, Retain Cycles, dan Target-Action Semantics
Pola klasik UIKit banyak mengandalkan *Delegation*, *Target-Action*, dan *NotificationCenter*. Analisis implikasi manajemen memori (*retain cycle*) dari:
1. Properti `delegate` yang tidak dideklarasikan sebagai `weak` pada protokol berbasis objek.
2. Penambahan target pada `UIButton` via `addTarget(_:action:for:)` terhadap referensi `self`. Mengapa *target-action* secara konvensional tidak menyebabkan siklus referensi kuat (*strong reference cycle*), namun penggunaan closure-based action (`UIAction`) modern dapat menyebabkan kebocoran memori jika *capture list* diabaikan?

### Soal 2.3: Anatomi Off-Screen Rendering dan GPU Pipeline Stalls
Penggunaan properti kosmetik seperti `layer.cornerRadius` yang digabungkan dengan `layer.masksToBounds = true`, `layer.shadowOffset` tanpa `layer.shadowPath`, serta penerapan `layer.mask` sering menyebabkan penurunan *frame rate* (terutama pada layar ProMotion 120Hz). Jelaskan fenomena teknis *Off-Screen Rendering* dari sudut pandang *Render Server* dan GPU memory tiling architecture. Mengapa GPU terpaksa mengalokasikan *off-screen pass-buffer* dan melakukan *context switching* yang mahal?

### Soal 2.4: Custom UIViewController Transition State Machines
Saat mengimplementasikan transisi kustom non-interaktif maupun interaktif menggunakan `UIViewControllerAnimatedTransitioning` dan `UIPercentDrivenInteractiveTransition`, kegagalan memanggil `transitionContext.completeTransition(!transitionContext.transitionWasCancelled)` pada saat transisi dibatalkan akan menyebabkan aplikasi berada dalam *corrupted UI state*. Jelaskan secara teknis apa yang terjadi pada *view hierarchy containment* dan *window layer* jika pemanggilan metode penyelesaian tersebut gagal dieksekusi.

### Soal 2.5: Isolasi dan Diagnostik Main Thread Stalls via RunLoop Observers
Aplikasi mengalami micro-stutter (hitch) sporadis yang sulit dideteksi oleh static analyzer. Bagaimana Anda memanfaatkan `CFRunLoopObserver` kustom untuk memantau aktivitas `kCFRunLoopBeforeSources`, `kCFRunLoopBeforeWaiting`, dan `kCFRunLoopAfterWaiting` guna mengukur durasi pengerjaan *task* di antrean utama? Bagaimana membedakan apakah sebuah stall disebabkan oleh eksekusi kode sinkron CPU-bound, *blocking I/O*, atau *IPC/XPC sync waiting* pada Render Server?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Frame Drops Parah pada Infinite Feed dengan Variasi Tinggi Konten
**Konteks Insiden:**
Sebuah aplikasi jejaring sosial enterprise mengalami penurunan *frame rate* ekstrem dari 120 FPS menjadi 25-35 FPS saat pengguna melakukan *fast scrolling* pada feed utama. Feed tersebut menggunakan `UICollectionViewCompositionalLayout` dengan sel yang memuat teks kaya (*rich formatted text* via `NSAttributedString`), lencana status dinamis, dan gambar berdimensi variatif. Seluruh sel menggunakan Auto Layout dengan *self-sizing cells* (`preferredLayoutAttributesFitting`).

**Diagnostik & Investigasi:**
Hasil profiling menggunakan Instruments (*Time Profiler* dan *Core Animation*) mengindikasikan bahwa 65% beban kerja CPU di Main Thread teralokasi pada:
1. `NSAttributedString.boundingRect(with:options:context:)`
2. `Engine.solve()` dari Auto Layout
3. Alokasi CoreGraphics pada *backing store* teks

**Pertanyaan:**
1. Desainlah strategi arsitektur layout hibrida yang mengeliminasi komputasi Cassowary berulang di Main Thread tanpa mengorbankan fleksibilitas teks multi-baris dinamis.
2. Bagaimana Anda merancang sistem kalkulasi dan *caching* dimensi layout secara *asinkron* di *background thread* sebelum data diserahkan ke UI layer? Jelaskan batasan thread-safety UIKit yang wajib diakomodasi dalam pendekatan ini.

---

### Skenario B: Crash Masif `NSInternalInconsistencyException` pada Batch Updates
**Konteks Insiden:**
Aplikasi perbankan menampilkan daftar transaksi real-time yang menerima pembaruan data secara *streaming* melalui WebSocket. Aplikasi menggunakan `UITableView` klasik dengan metode `beginUpdates()` dan `endUpdates()` (atau `performBatchUpdates`) untuk menyisipkan (*insert*), menghapus (*delete*), dan memindahkan (*move*) baris data. Di lingkungan produksi dengan frekuensi mutasi tinggi, terjadi lonjakan crash dengan laporan:
`Fatal Exception: NSInternalInconsistencyException: Invalid update: invalid number of rows in section 0. The number of rows contained in an existing section after the update must be equal to the number of rows contained in that section before the update, plus or minus the number of rows inserted or deleted...`

**Akar Masalah:**
Terdapat *race condition* antara array data model yang dimutasi di background thread worker dan eksekusi callback visual pada Main Thread RunLoop.

**Pertanyaan:**
1. Analisis secara matematis dan prosedural mengapa UIKit melempar eksepsi fatal ini saat terjadi desinkronisasi antara status data backing array dengan instruksi mutasi indeks `UITableView`.
2. Susun perbaikan arsitektural menggunakan `UICollectionViewDiffableDataSource` dan `NSDiffableDataSourceSnapshot`. Bagaimana mekanisme `DiffableDataSource` mengisolasi kalkulasi perbedaan (*diffing*) ke background queue via Myers Difference Algorithm, dan bagaimana ia menjamin integritas referensial data tanpa manual index-path tracking?

---

### Skenario C: Massive View Controller (MVC) Refactoring & Routing Decoupling
**Konteks Insiden:**
Sebuah modul checkout e-commerce memiliki kelas `CheckoutViewController` dengan panjang 4.200 baris kode. Kelas ini bertanggung jawab atas:
- Manajemen jaringan (pembayaran, validasi kupon, pengambilan alamat).
- Validasi form transaksi secara imperatif.
- Presentasi navigasi langsung menggunakan `self.navigationController?.pushViewController(...)` atau `self.present(...)` secara *hardcoded* ke setidaknya 8 layar berbeda.
- Pengaturan constraint Auto Layout manual dan event delegation untuk 15 custom view components.

Kode ini sangat rapuh, sulit diuji (*untestable*), dan menyebabkan *dependency coupling* yang tinggi antarlayar, menghambat migrasi modul ke arsitektur modular dynamic framework.

**Pertanyaan:**
1. Rancang arsitektur refaktorisasi menggunakan pola **Coordinator** yang dipadukan dengan **MVP (Model-View-Presenter)** atau **MVVM**. Tunjukkan diagram relasi atau interface kontrak Swift yang mengabstraksi navigasi keluar dari `UIViewController`.
2. Bagaimana strategi Anda memutus ketergantungan langsung terhadap implementasi konkret UIKit view controller lain tanpa memicu memory leak (*retain cycle* antara Coordinator dan View Controller)?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Imperative Interactive Sheet Component

#### Deskripsi Masalah
Banyak aplikasi modern memerlukan komponen bottom sheet kustom interaktif (seperti Apple Maps) yang mendukung snapping ke berbagai ketinggian (*collapsed*, *half-expanded*, *fully-expanded*), mengikuti gesture pengguna secara real-time, menampung hierarki scroll bersarang (`UIScrollView`/`UITableView`), dan memiliki performa rendering konstan pada 60/120 FPS tanpa hitch. Anda diminta untuk membangun komponen ini murni menggunakan UIKit imperatif tanpa ketergantungan library pihak ketiga.

#### Persyaratan Teknis (Requirements)
1. **Custom Interactive Container Controller:**
   Buat subclass `UIViewController` bernama `InteractiveSheetContainerController` yang menampung `contentViewController` (layar latar belakang) dan `sheetViewController` (layar bottom sheet).
2. **Gesture Pan & Scroll Coexistence:**
   Implementasikan penanganan gesture interaktif menggunakan `UIPanGestureRecognizer`. Jika `sheetViewController` memuat `UIScrollView`, koordinasikan kedua interaksi tersebut menggunakan delegasi `UIGestureRecognizerDelegate` (`gestureRecognizer(_:shouldRecognizeSimultaneouslyWith:)`) sehingga:
   - Ketika sheet belum berada pada posisi *fully-expanded*, gesture scroll pada konten dialihkan menjadi gesture translasi posisi sheet.
   - Ketika sheet berada pada posisi *fully-expanded*, dragging ke atas men-scroll konten, dan dragging ke bawah (saat `contentOffset.y <= 0`) menarik sheet turun.
3. **Dynamic Physics-Based Snapping:**
   Ketika sentuhan dilepas, sheet harus meluncur (*snap*) ke target terdekat (*anchor points*: 15% tinggi layar, 50% tinggi layar, 90% tinggi layar) menggunakan `UIViewPropertyAnimator` dengan kurva pegas (*spring timing parameters* `UISpringTimingParameters`) yang memperhitungkan proyeksi kecepatan akhir gesture (*gesture velocity* via `velocity(in:)`).
4. **Zero Off-Screen Rendered Visual Effects:**
   Sheet harus memiliki sudut membulat atas (*top rounded corners*) dan bayangan (*drop shadow*). Anda dilarang menggunakan `layer.cornerRadius` dengan `layer.masksToBounds = true` bersamaan dengan `layer.shadowOpacity`. Terapkan optimasi rendering menggunakan `UIBezierPath` eksplisit pada `layer.shadowPath` dan sub-masking terisolasi agar GPU tidak memicu off-screen pass.

#### Batasan Implementasi (Constraints)
- Murni bahasa Swift (Modern Concurrency / Strict Concurrency compliant).
- Dilarang keras menggunakan `UISheetPresentationController` bawaan iOS 15+ (tujuan tantangan ini adalah menguasai mekanika dasar UIKit imperatif tingkat lanjut).
- Dilarang menggunakan autolayout constraints di dalam tracking gesture loop (`panGestureDidChange`). Seluruh manipulasi posisi sheet selama dragging harus dilakukan via mutasi langsung pada `transform` (`CGAffineTransform`) atau `frame` layer guna memotong ongkos kalkulasi constraint engine.
- Alokasi memori harus konstan; tidak ada retain cycle antara container, child view controllers, dan gesture recognizer.

#### Output yang Diharapkan
1. Kode sumber terstruktur untuk:
   - `InteractiveSheetContainerController.swift`
   - Implementasi koordinasi gesture dan kustomisasi layer layout.
   - Animasi transisi snapped state via `UIViewPropertyAnimator`.
2. Analisis teknis singkat (1-2 paragraf) yang menjelaskan bagaimana arsitektur Anda menghindari *jitter* visual saat pergantian kontrol sentuh antara `UIPanGestureRecognizer` dan *internal scroll view pan gesture*.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme siklus hidup `UIViewController` secara presisi dan keterkaitannya dengan siklus rendering window OS.
- [ ] Hubungan arsitektural antara `UIResponder`, `UIView`, `CALayer`, dan *Render Server*.
- [ ] Cara kerja internal Auto Layout Engine (Cassowary) dan struktur *Deferred Layout Pass* pada UIKit RunLoop.
- [ ] Penjaluran event sentuhan melalui algoritma *Hit-Testing* rekursif dan struktur *Responder Chain*.
- [ ] Alur daur ulang objek dan pembersihan state pada `UITableView` / `UICollectionView` (`prepareForReuse`).
- [ ] Dampak properti grafis `CALayer` terhadap *Off-Screen Rendering* dan GPU memory stalls.
- [ ] Mekanisme containment view controller dan orkestrasi transisi custom interaktif via `UIViewControllerAnimatedTransitioning`.
- [ ] Prinsip pemisahan tanggung jawab untuk memecah *Massive View Controller* menggunakan pola Coordinator, Presenter, atau ViewModel.

### Saya tidak perlu menghafal:
- [ ] Nilai numerik konstanta metrik sistem bawaan (seperti tinggi pasti `UINavigationBar` atau margin default layout).
- [ ] Seluruh parameter sintaks visual format language (VFL) Auto Layout yang sudah deprecated.
- [ ] Seluruh daftar enum style `UIModalPresentationStyle` atau `UIModalTransitionStyle` di luar penggunaannya pada kasus nyata.
- [ ] Boilerplate kode integrasi storyboard/XIB jika fokus arsitektur mengarah pada *programmatic UI construction*.

### Saya harus bisa melakukan:
- [ ] Menyusun antarmuka kompleks murni secara programatik (*Pure Code Layout*) menggunakan Auto Layout (`NSLayoutConstraint` / Layout Anchors) tanpa layout feedback loops.
- [ ] Mendiagnosis dan mengeliminasi off-screen rendering menggunakan Xcode Instruments (*Core Animation*, *Time Profiler*).
- [ ] Mengimplementasikan subclassing komponen UIKit tingkat lanjut dengan gesture handling yang saling tumpang tindih (*simultaneous recognition*).
- [ ] Menulis arsitektur feed adaptif dengan *Diffable Data Source* yang bebas crash multithreading dan memiliki performa 60/120 FPS konstan.
- [ ] Mengisolasi navigasi dan logika bisnis dari `UIViewController` ke dalam layer arsitektur terpisah yang *unit-testable*.