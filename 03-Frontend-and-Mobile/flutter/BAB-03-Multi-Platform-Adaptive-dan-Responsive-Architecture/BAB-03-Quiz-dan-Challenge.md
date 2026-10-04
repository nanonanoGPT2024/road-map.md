# BAB 03: Quiz, Challenge, & Knowledge Check
**Multi-Platform Adaptive & Responsive Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Dikotomi "Responsive" vs "Adaptive"
Jelaskan perbedaan fundamental antara arsitektur *Responsive Design* dan *Adaptive Design* dalam ekosistem Flutter. Analisis mengapa memperlakukan keduanya sebagai konsep yang sama dapat menghasilkan aplikasi desktop/web yang terasa seperti "aplikasi mobile yang diregangkan" (*stretched mobile app*), khususnya ditinjau dari aspek input mechanics, densitas informasi (*information density*), dan paradigma navigasi!

### Soal 1.2: Mekanisme Propagasi BoxConstraints
Dalam aturan fundamental Flutter: *"Constraints go down, Sizes go up, Parent sets position"*, jelaskan bagaimana transisi dari *Tight Constraints* ke *Loose Constraints* terjadi saat membangun antarmuka multi-kolom yang adaptif. Apa dampak layouting jika sebuah widget adaptif mereturn `Row` tanpa batasan lebar (*unbounded width*) di dalam parent dengan *infinite width*?

### Soal 1.3: `MediaQuery` vs `LayoutBuilder` – Granularitas dan Rebuild Tree
Bandingkan `MediaQuery.of(context)` dan `LayoutBuilder` dalam konteks penentuan breakpoint tampilan. Ditinjau dari lifecycle widget dan relayout boundary, kapankah `LayoutBuilder` mutlak lebih diunggulkan dibanding `MediaQuery`, dan bagaimana implikasi performa rebuild dari kedua pendekatan tersebut terhadap sub-tree yang kompleks?

### Soal 1.4: Abstraksi Platform via `ThemeData` & TargetPlatform
Bagaimana engine Flutter mengisolasi dependensi sistem operasi melalui `ThemeData.platform`, `TargetPlatform`, dan `kIsWeb`? Jelaskan bahaya arsitektural (*architectural hazard*) dari memanggil `dart:io` `Platform.isAndroid` / `Platform.isWindows` secara langsung di dalam presentation/UI layer pada aplikasi multi-platform!

### Soal 1.5: Input Paradigm Multi-Device: Touch vs Pointer vs Keyboard
Jelaskan perbedaan mendasar pipeline dispatch event antara sentuhan (*touch events*) dan tetikus (*pointer events*) di level layer Gestures Flutter. Mengapa arsitektur antarmuka multi-platform wajib mengimplementasikan `FocusNode`, `Shortcuts`, dan `Actions` selain mengandalkan `GestureDetector` semata?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Rebuild Cascading Mitigation via InheritedModel
Sebelum Flutter 3.10, pemanggilan `MediaQuery.of(context).size` akan me-rebuild widget pemanggil setiap kali terjadi perubahan metrik window apa pun (seperti keyboard muncul atau padding sistem berubah). Jelaskan arsitektur internal berbasis `InheritedModel` pada `MediaQuery` modern (`MediaQuery.sizeOf`, `MediaQuery.paddingOf`, `MediaQuery.viewInsetsOf`) dan bagaimana mekanisme ini memutus rantai *unnecessary rebuild cascade*!

### Soal 2.2: Memory Leak & Orphan Nodes pada Dynamic Layout Swapping
Sebuah aplikasi beralih secara dinamis antara `BottomNavigationBar` (mobile) dan `NavigationRail` (desktop) berdasarkan breakpoint lebar layar. Pengembang mendapati bahwa state dari halaman aktif ter-reset (kehilangan input form dan scroll position) setiap kali ukuran jendela desktop di-resize melewati ambang breakpoint. Bedah akar penyebab masalah ini di level Element Tree dan jelaskan cara mitigasinya menggunakan `GlobalKey` atau arsitektur persistensi state!

### Soal 2.3: Layout Thrashing & Debugging Intrinsic Dimensions
Saat merancang tabel adaptif, seorang insinyur menggunakan `IntrinsicHeight` atau `IntrinsicWidth` di dalam hierarki widget yang kompleks agar child memiliki tinggi yang seragam. Mengapa penggunaan widget intrinsic dapat menyebabkan degradasi performa $O(N^2)$ (*speculative layout pass*)? Bagaimana cara mendeteksi dan mengeliminasi layout pass ganda ini menggunakan Flutter DevTools Timeline?

### Soal 2.4: Foldable Devices & Hinges: Menangani `DisplayFeature`
Bagaimana Flutter menangani hardware engsel (*hinge*) dan pemisahan layar fisik (*folding posture*) pada perangkat dual-screen atau foldable melalui `MediaQueryData.displayFeatures`? Jelaskan implementasi teknis pembagian layout agar konten tidak terpotong atau terdistorsi di area engsel fisik!

### Soal 2.5: Relayout Boundary Breakdown pada Desktop Window Resizing
Jelaskan apa itu *Relayout Boundary* di level `RenderObject` Flutter. Mengapa resizing window secara agresif pada desktop platform sering kali memicu drop frame drastis jika sebuah widget adaptif gagal mengisolasi relayout boundary-nya? Parameter apa saja yang mendefinisikan boundary tersebut secara internal?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Desktop ERP Enterprise Drop ke 15 FPS saat Window Resizing
Sebuah sistem ERP Enterprise berbasis Flutter Desktop (Windows & macOS) menampilkan dashboard analitik dengan 20+ visualisasi data, tabel real-time, dan form input. Ketika pengguna melakukan resize window, frame rate anjlok dari 120 FPS ke 15 FPS (*extreme jank*). Hasil profiling menunjukkan bahwa setiap frame resizing memicu eksekusi ulang method `build()` pada ribuan widget dari root hingga leaf node, disertai re-kalkulasi parsing data mentah.

* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda merestrukturisasi root layout dan manajemen breakpoint agar perubahan ukuran window terisolasi hanya pada layout container tanpa mengeksekusi ulang komputasi data dan widget visualisasi?
  2. Implementasikan skema debouncing / throttling atau isolasi `RenderObject` untuk meredam layout pass selama proses resize interaktif berlangsung!

### Skenario B: Race Condition State & Form Destruction pada Tablet Dynamic Folding
Aplikasi mobile perbankan mendukung perangkat Samsung Galaxy Z Fold. Pengguna sedang mengisi formulir pengajuan kredit panjang pada layar cover (kondisi terlipat). Ketika pengguna membuka lipatan layar (*unfold*), aplikasi otomatis berpindah dari layout single-pane vertikal ke master-detail two-pane layout. 
**Insiden:** Teks yang telah diketik pengguna di 5 field mendadak hilang, validation error terpicu secara acak, dan cursor keyboard melompat ke field pertama, menyebabkan komplain nasabah dan kegagalan submit data.

* **Pertanyaan Diagnostik:**
  1. Identifikasi kegagalan manajemen identitas widget (`Key`) dan retensi `Element` saat pohon widget berpindah struktur dari single tree ke two-pane tree!
  2. Rancang arsitektur penyimpanan draft state (memisahkan UI Presentation Lifecycle dari Form State Repository) yang menjamin zero data loss di tengah mutasi form factor yang ekstrem!

### Skenario C: Dilema Arsitektur Navigasi Multi-Platform (GoRouter vs Adaptive Shell)
Sebuah startup SaaS multi-platform ingin membangun sistem navigasi tunggal yang harus mendukung:
* Mobile: Bottom Navigation Bar + Push transitions mendalam.
* Tablet: Persistent Navigation Rail.
* Desktop/Web: Collapsible Sidebar Menu + Dynamic Browser URL deep-linking + State preservation saat beralih tab.

Tim terbelah antara menggunakan *Conditional Layout Switching* di dalam satu shell widget atau memecah rute navigasi menjadi pohon rute deklaratif yang berbeda menggunakan `GoRouter` `StatefulShellRoute`.

* **Pertanyaan Diagnostik:**
  1. Analisis *trade-off* kedua pendekatan tersebut terhadap kompleksitas sinkronisasi URL Web, pemeliharaan Element Tree, dan bundle size aplikasi!
  2. Buat rekomendasi arsitektur definitif (beserta pseudo-code struktur deklarasi navigasi) yang memisahkan antara state navigasi inti dan adaptive shell layout!

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Multi-Pane Adaptive Workspace Dashboard

#### Problem Statement
Sebuah platform monitoring infrastruktur server membutuhkan modul workspace monitoring yang berjalan mulus di Mobile, Tablet, Foldable, Desktop, dan Web. Dashboard ini harus mampu menampilkan daftar metrik (*Master List*) dan detail grafik performa (*Detail Pane*) dengan responsivitas tinggi, adaptasi input yang natural (mouse vs touch), serta nol kehilangan state saat berpindah dimensi layar.

#### Requirements
1. **Dynamic Breakpoints Architecture:**
   * **Compact (< 600dp):** Menampilkan single-pane (Master List atau Detail Pane via push/pop navigasi standar).
   * **Medium (600dp - 1024dp) / Foldable:** Menampilkan dual-pane side-by-side secara adaptif; wajib menghindari physical hinge/seam jika terdeteksi `DisplayFeatureType.hinge`.
   * **Expanded (> 1024dp):** Menampilkan triple-pane (Navigation Drawer/Rail + Master List + Full Detail Workspace) dengan densitas visual tinggi.
2. **Rebuild Optimization:** Dilarang keras menggunakan `MediaQuery.of(context)` yang memicu rebuild global. Wajib memanfaatkan `MediaQuery.sizeOf(context)` atau `LayoutBuilder` murni dengan relayout boundaries yang ketat.
3. **Multi-Modal Input Parity:**
   * Sentuhan: Swipe gesture untuk aksi cepat pada list item.
   * Mouse: Hover state highlight (`MouseRegion`), kursor pointer yang dinamis, dan context menu via right-click (`SecondaryTap`).
   * Keyboard: Navigasi item menggunakan panah atas/bawah (`Shortcuts` & `Actions`), dan trigger aksi detail via `Enter`.
4. **State Preservation:** Input filter pencarian dan scroll offset pada Master List tidak boleh ter-reset saat ukuran layar diubah dari Compact ke Expanded secara dinamis.

#### Constraints
* Tidak boleh menggunakan package pihak ketiga untuk responsive layout (seperti `responsive_builder` atau `sizer`). Semua harus diimplementasikan menggunakan primitive widgets Flutter murni (`LayoutBuilder`, `CustomMultiChildLayout`, `FocusableActionDetector`, dll).
* UI harus tetap render pada 60/120 FPS tanpa frame drop saat window di-resize secara kontinu di Desktop/Web.

#### Expected Output
* File arsitektur Dart modular yang bersih:
  * `adaptive_scaffold.dart`: Shell presentation adaptif.
  * `input_adapter.dart`: Abstraksi mouse, touch, dan keyboard actions.
  * `workspace_controller.dart`: State holder yang decoupling dari UI tree.
* Kode implementasi production-ready lengkap dengan defensive typing dan dokumentasi architectural rationale.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan esensial antara Responsive Layout (skalabilitas dimensi) dan Adaptive Layout (spesialisasi platform & behavioral input).
- [ ] Cara kerja propagasi batasan layout (`BoxConstraints`) dari parent ke child, serta karakteristik *tight*, *loose*, dan *unbounded constraints*.
- [ ] Arsitektur internal `MediaQuery` pasca-Flutter 3.10 berbasis `InheritedModel` (`sizeOf`, `paddingOf`, `viewInsetsOf`) untuk mencegah rebuild thrashing.
- [ ] Konsep *Speculative Layout* dan overhead komputasi dari pemanggilan widget *Intrinsic* (`IntrinsicWidth`, `IntrinsicHeight`).
- [ ] Mekanisme isolasi render pohon melalui *Relayout Boundaries* (`isRelayoutBoundary`) dan bagaimana `LayoutBuilder` berinteraksi dengannya.
- [ ] Peran `FocusNode`, `FocusableActionDetector`, `Shortcuts`, dan `Actions` dalam menghadirkan keyboard navigation parity pada Desktop dan Web.
- [ ] Pemanfaatan `DisplayFeature` untuk layouting adaptif pada perangkat *foldable* dan *dual-screen*.

### Saya tidak perlu menghafal:
- [ ] Dimensi piksel absolut spesifik dari setiap model perangkat di pasaran (cukup pahami batas ambang / *breakpoints standard* seperti Material 3 Window Size Classes: Compact, Medium, Expanded).
- [ ] Semua konfigurasi default theme platform (misal: Cupertino vs Material color palette bawaan), karena hal ini diabstraksikan oleh token tema design system.
- [ ] Nilai eksak `Platform.operatingSystemVersion` hingga minor digit.

### Saya harus bisa melakukan:
- [ ] Merancang dan mengimplementasikan breakpoint engine modular tanpa dependensi package pihak ketiga.
- [ ] Melakukan profiling dan mitigasi layout jank saat window resize menggunakan Flutter DevTools Timeline & Performance Overlay.
- [ ] Mempertahankan state UI dan Element lifecycle saat layout berganti secara dinamis (menggunakan `GlobalKey`, `PageStorageKey`, atau state hoisting).
- [ ] Mengimplementasikan multi-modal input (Touch, Mouse Hover, Right-Click Context Menu, Keyboard Shortcuts) secara native dan ergonomis.
- [ ] Memisahkan presentation logic platform-agnostic dari integrasi spesifik OS agar kode dapat di-test dengan unit & widget tests secara deterministik.