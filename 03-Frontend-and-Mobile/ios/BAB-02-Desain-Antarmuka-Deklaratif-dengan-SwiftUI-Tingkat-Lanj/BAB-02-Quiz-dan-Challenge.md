# BAB 02: Quiz, Challenge, & Knowledge Check
**Desain Antarmuka Deklaratif dengan SwiftUI Tingkat Lanjut**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Structural Identity vs. Explicit Identity:**
   Jelaskan perbedaan mendasar antara *Structural Identity* dan *Explicit Identity* pada SwiftUI runtime engine (AttributeGraph). Bagaimana penggunaan conditional logic (`if-else` vs. `.opacity()`) mempengaruhi pemeliharaan state internal, alokasi memori, dan siklus hidup animasi dari sebuah sub-view?

2. **The 3-Step Layout Negotiation Algorithm:**
   Uraikan secara presisi tiga langkah algoritma negosiasi layout SwiftUI antara Parent View dan Child View. Apa yang terjadi secara komputasi jika Parent mengusulkan `ProposedViewSize.unspecified`, dan bagaimana Child View seperti `Text`, `Image`, atau `Rectangle` merespons usulan tersebut?

3. **Mekanisme Data-Flow Terbalik melalui `PreferenceKey`:**
   SwiftUI menganut prinsip *single source of truth* dan *downward data flow*. Jelaskan arsitektur teknis di balik `PreferenceKey` yang memungkinkan child view mengirimkan data layout (misalnya `GeometryProxy`) ke ancestor view. Mengapa mutasi `@State` langsung di dalam closure `.onPreferenceChange` berisiko memicu infinite layout loop, dan bagaimana mitigasi formalnya?

4. **Observation Engine: `@Observable` (Observation Framework) vs. `ObservableObject` (Combine):**
   Bandingkan arsitektur tracking dependensi antara Swift 5.9 `@Observable` macro dengan legacy `@ObservedObject` (Combine). Mengapa `@Observable` mampu mengeliminasi *unnecessary body re-evaluations* secara signifikan pada level granularitas property access?

5. **Animatable Protocol & VectorArithmetic:**
   Bagaimana sistem rendering SwiftUI memecah mutasi diskrit state menjadi frame animasi kontinu (60/120 FPS)? Jelaskan peran `AnimatableModifier`, `animatableData`, dan tipe data yang mengimplementasikan `VectorArithmetic` dalam menginterpolasi perubahan data kustom yang tidak didukung secara *out-of-the-box* oleh SwiftUI layout engine.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Layout Protocol Cache Subsystem (iOS 16+):**
   Saat mengimplementasikan custom container menggunakan `Layout` protocol, metode `makeCache(subviews:)` dan `updateCache(_:subviews:)` disediakan oleh framework. Jelaskan siklus hidup cache ini, kondisi apa yang memicu pembaruannya, dan bagaimana Anda mendesain struktur data cache untuk memangkas kompleksitas komputasi layout dari $\mathcal{O}(N^2)$ menjadi $\mathcal{O}(N)$ pada hierarki antarmuka dinamis?

2. **Forensic Debugging dengan `Self._printChanges()`:**
   Saat menjalankan instrumentasi performa, Anda menyisipkan `let _ = Self._printChanges()` di dalam komputasi `body` sebuah view performa-kritis. Jika console mencetak pesan `@self changed` padahal tidak ada perubahan pada `@State` lokal, parameter input apa saja yang memicu invalidasi AttributeGraph tersebut, dan bagaimana cara membedah dependensi tersembunyi (*hidden dependencies*) tersebut?

3. **Re-entrancy & Lifecycle Synchronization pada `UIViewRepresentable`:**
   Pada integrasi view UIKit lama ke dalam SwiftUI via `UIViewRepresentable`, sering terjadi anomali saat `updateUIView(_:context:)` dipanggil secara asinkron selama siklus layout SwiftUI berlangsung. Jelaskan skenario terjadinya siklus *re-entrant layout update*, dan bagaimana cara mendesain komunikasi dua arah (Delegate/Target-Action ke SwiftUI `@Binding`) tanpa memicu Runtime Warning: *"Modifying state during view update, this will cause undefined behavior"*?

4. **Transaction Tree & Animation Disabling Interception:**
   Jelaskan bagaimana sebuah `Transaction` dipropagasikan melalui hierarki View. Bagaimana Anda secara terprogram mengintersepsi, menimpa (override), atau mendisposisi transaksi animasi dari parent menggunakan modifier `.transaction()` atau `Transaction(animation: nil)` agar animasi eksplisit pada root container tidak merusak layout transisi lokal pada isolated child component?

5. **Virtualization Hazards: `GeometryReader` di dalam Lazy Containers:**
   Mengapa penempatan `GeometryReader` secara naif di dalam baris `LazyVStack` atau `List` dapat merusak virtualisasi memori dan menyebabkan *scroll hitch rate* yang tinggi pada layar ProMotion (120Hz)? Jelaskan interaksi layout engine SwiftUI saat mengukur ukuran konten fleksibel terhadap viewport virtualization boundary.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Rendering Bottleneck & Frame Drops (Fintech Real-Time Order Book)
Sebuah aplikasi trading kripto enterprise memiliki komponen *Order Book* yang menampilkan daftar limit order secara real-time. Data diperbarui melalui WebSocket dengan frekuensi rata-rata 30-50 tick per detik. Komponen saat ini menggunakan `LazyVStack` dengan baris-baris kustom yang menampilkan volume bar, harga, dan animasi flash warna saat data berubah.
* **Gejala:** Aplikasi mengalami frame-drop parah (turun ke 15-20 FPS), konsumsi CPU Core UI mencapai 100%, dan terjadi memory pressure bertahap hingga aplikasi crash karena OOM (*Out of Memory*).
* **Pertanyaan Diagnostik:**
  1. Identifikasi akar masalah pada arsitektur rendering SwiftUI saat menerima streaming data frekuensi tinggi ke dalam declarative hierarchy.
  2. Rancang refaktorisasi arsitektur rendering komponen ini menggunakan kombinasi SwiftUI `Canvas` (Immediate Mode Rendering / Metal-backed), isolasi data stream via `@Observable` projection/buffering, dan teknik throttling/coalescing state mutations untuk mempertahankan target rendering konstan 120 FPS.

### Skenario B: State Mutation Cycle & Navigation Crash (NavigationStack Race Condition)
Pada aplikasi checkout e-commerce berskala besar, tim Anda mengimplementasikan flow checkout bertingkat menggunakan `NavigationStack(path: $path)` yang terikat pada centralized routing store.
* **Gejala:** Saat pengguna menekan tombol "Bayar Cepat" yang memicu pembayaran via Apple Pay sekaligus mengarahkan rute navigasi ke receipt page, Xcode Thread Sanitizer memunculkan ungu (*purple warning*): *"Modifying state during view update"* berulang kali, diikuti dengan UI freeze dan crash fatal berulang: `SwiftUI/NavigationPath.swift: CoreData/AttributeGraph cycle detected`.
* **Pertanyaan Diagnostik:**
  1. Bedah secara mekanistis apa yang terjadi pada runtime AttributeGraph ketika eksekusi async callback (misal: completion handler PaymentSheet) memicu mutasi `NavigationPath` secara simultan saat view transitions sedang berlangsung.
  2. Bagaimana arsitektur state routing yang deterministik (menggunakan state machine, isolation via `@MainActor`, dan penjadwalan transaksi atomik) untuk menjamin navigasi deep-link/pop-to-root tidak pernah berbenturan dengan siklus komputasi layout view?

### Skenario C: UIKit Interop Memory Leak & Context Destruction (Custom Camera/Metal Engine)
Sebuah modul scanner ID pada aplikasi perbankan membungkus custom `AVCaptureSession` dan Metal-based rendering preview layer ke dalam SwiftUI via `UIViewControllerRepresentable`.
* **Gejala:** Ketika user bernavigasi bolak-balik antara view scanner ini dan tab lain di dalam `TabView`, konsumsi RAM bertambah sebesar ~80MB per kunjungan (leakage). Selain itu, sesekali aplikasi membeku karena `Coordinator` masih menerima capture output saat underlying `UIView` telah dilepas (*deallocated*) oleh SwiftUI runtime.
* **Pertanyaan Diagnostik:**
  1. Analisis siklus hidup (lifecycle mismatch) antara SwiftUI container struct dan UIKit `UIViewController` yang dipertahankan oleh Coordinator. Di mana letak potensi retain cycle yang umum terjadi?
  2. Implementasikan blueprint dekonstruksi lifecycle yang aman dengan mengimplementasikan `dismantleUIViewController(_:coordinator:)`, pembatalan asynchronous delegation pipelines, dan pembersihan Metal context guna mencegah memory fragmentation dan background execution crashes.

---

## 4. Chapter Challenge

**Tantangan Praktis: High-Performance Tag Cloud / Dynamic Chips Flow Engine (`AdaptiveFlowLayout`)**

### Deskripsi Masalah:
Komponen native `HStack` dan `VStack` pada SwiftUI tidak memiliki kapabilitas untuk melakukan *multiline dynamic wrapping* (layout mirip CSS Flexbox `flex-wrap: wrap`) berdasarkan intrinsic content size dari masing-masing subview. Penggunaan wrapping library berbasis `GeometryReader` dan `PreferenceKey` warisan masa lalu memicu komputasi layout multi-pass yang menghasilkan glitch visual pada frame pertama dan rendering overhead tinggi saat data dinamis berubah.

### Requirement:
Buat sebuah kustom container bernama `AdaptiveFlowLayout` yang mengimplementasikan protocol `Layout` (iOS 16+):
1. **Algoritma Dynamic Line-Breaking:** Menghitung ukuran intrinsic dari setiap subview via `subviews.map { $0.sizeThatFits(...) }`, menyusun subview secara horizontal dengan spasi tertentu (`horizontalSpacing`), dan jika subview melebihi batas lebar horizontal yang diusulkan parent (`proposal.width`), subview secara otomatis dibungkus ke baris baru dengan jarak vertikal (`verticalSpacing`).
2. **Alignment Support:** Mendukung alignment baris yang dapat dikonfigurasi: `.leading`, `.center`, atau `.trailing`.
3. **High-Performance Caching:** Mengimplementasikan `LayoutCache` kustom yang menyimpan perhitungan geometri baris, offset posisi, dan total frame bounding box. Cache hanya boleh dihitung ulang jika lebar yang diusulkan atau struktur/identitas subviews berubah.
4. **Fluid Transitions:** Mendukung smooth animations saat chip item ditambahkan atau dihapus menggunakan `.animation(.spring(), value: tags)` tanpa terjadi layout clipping atau frame stutter.

### Constraints:
* Wajib murni menggunakan Swift `Layout` protocol (dilarang menggunakan `GeometryReader`, UIKit wrappers, atau deprecated preferences-based flow layout).
* Operasi kalkulasi layout pada `placeSubviews` harus bersifat $\mathcal{O}(N)$ dengan membaca data yang telah dipra-kalkulasi di dalam cache.
* Menangani edge cases: `proposal.width == nil` (proposal unspecified/infinite scroll horizontal fallback), subview tunggal yang lebarnya melebihi lebar layar, dan empty state.

### Expected Output:
Sebuah file Swift mandiri berstandar enterprise yang memuat:
* Struct `AdaptiveFlowLayout: Layout` beserta implementasi:
  * `struct LayoutCache`
  * `func makeCache(subviews: Subviews) -> LayoutCache`
  * `func updateCache(_ cache: inout LayoutCache, subviews: Subviews)`
  * `func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout LayoutCache) -> CGSize`
  * `func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout LayoutCache)`
* Kode preview pengujian yang mendemonstrasikan tag cloud dengan 50 item, toggle filter interaktif (tambah/hapus elemen dinamis), dan switch layout alignment secara runtime pada ProMotion 120Hz display.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal AttributeGraph (AG) dan bagaimana SwiftUI melacak dependensi data secara deklaratif.
- [ ] Perbedaan fundamental antara Structural Identity (alokasi memori berbasis hirarki AST) dan Explicit Identity (penggunaan `.id(_:)`).
- [ ] Siklus hidup lengkap Layout Protocol (`makeCache`, `sizeThatFits`, `placeSubviews`) serta trade-off performanya dibanding Auto Layout.
- [ ] Cara kerja interpolasi geometri pada sistem animasi via protocol `Animatable` dan implementasi `animatableData`.
- [ ] Perbedaan transmisi state antara Macro `@Observable` (property-level tracking) dan Combine-based `ObservableObject` (object-level tracking via `objectWillChange`).
- [ ] Aturan perambatan `Transaction`, pemanfaatan `TransactionKey`, dan cara memutus rantai animasi implisit menggunakan context mutasi lokal.
- [ ] Siklus hidup representable view wrappers (`UIViewRepresentable`, `dismantleUIView`) dan pencegahan leak pada context retainment.

### Saya tidak perlu menghafal:
- [ ] Syntax signature eksak dari seluruh method `UIViewRepresentable` atau `Layout` protocol (cukup pahami kontrak eksekusinya dan biarkan Xcode auto-complete melengkapinya).
- [ ] Nilai numeric exact timing curve dari curve animasi bawaan seperti `.spring()` atau `.easeInOut` (gunakan visual timeline inspector atau insting tuning UI).
- [ ] Semua implementasi primitif dari `VectorArithmetic` pada standard library types (cukup pahami kapan harus menggunakan `AnimatablePair`).

### Saya harus bisa melakukan:
- [ ] Menganalisis dan mengeliminasi redudansi siklus rendering menggunakan `Self._printChanges()` dan Instruments (Time Profiler & SwiftUI View Body template).
- [ ] Mengimplementasikan custom container layout engine berperforma tinggi menggunakan `Layout` protocol dengan layout cache optimal.
- [ ] Merancang jembatan integrasi dua arah yang aman dari UIKit ke SwiftUI tanpa menghasilkan *state mutation cycle warnings* atau leak retain cycle pada Coordinator.
- [ ] Mengisolasi pembaruan data frekuensi tinggi (high-frequency ticks) menggunakan Metal Canvas atau direct drawing groups agar tidak membebani main thread.
- [ ] Mengaudit hierarki view kompleks untuk mengidentifikasi degradasi performa yang dipicu oleh penempatan `GeometryReader` yang tidak tepat pada lazy containers.