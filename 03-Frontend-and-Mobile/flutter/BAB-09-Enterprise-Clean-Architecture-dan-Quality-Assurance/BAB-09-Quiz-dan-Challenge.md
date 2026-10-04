# BAB 09: Quiz, Challenge, & Knowledge Check
**Enterprise Clean Architecture & Quality Assurance**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **The Dependency Inversion Principle & Domain Purity**
   Dalam implementasi Clean Architecture murni menurut Robert C. Martin di ekosistem Flutter, lapisan Domain didefinisikan sebagai *agnostic* terhadap *framework*. Jelaskan secara mendalam mengapa import package seperti `flutter/material.dart`, `dart:ui`, atau bahkan state management solution (seperti `flutter_bloc` atau `riverpod`) di dalam direktori `domain/` dikategorikan sebagai pelanggaran arsitektur (*architectural violation*). Apa dampak langsungnya terhadap *unit testability* dan portabilitas kode?

2. **Entities vs. Data Transfer Objects (Models)**
   Banyak *engineer* mencampuradukkan entitas (*Domain Entity*) dengan model data (*Data Transfer Object / DTO*). Bedakan kedua konsep ini dari perspektif:
   - Imutabilitas dan validasi *business invariants*.
   - Keterikatan terhadap serialisasi/deserialisasi (`toJson`, `fromJson`, integrasi database seperti SQLite/Isar).
   - Strategi *mapping* antar-lapisan (*presentation-domain-data*) beserta konsekuensi performa alokasi memorinya.

3. **Exception Handling Strategy: Exceptions vs. Functional Error Handling**
   Bandingkan arsitektur *error handling* berbasis `try-catch` konvensional dengan *Functional Error Handling* menggunakan `Either<Failure, T>` (atau `Result<T, E>`). Mengapa *enterprise-grade Flutter applications* cenderung mengadopsi tipe data *monadic* atau *sealed classes* untuk merepresentasikan status kegagalan daripada melempar *unhandled exception* menembus batas (*boundaries*) lapisan Data ke Presentation?

4. **The Testing Pyramid in Flutter**
   Jelaskan komposisi ideal *Test Pyramid* (Unit Tests, Widget Tests, Integration Tests) dalam aplikasi Flutter skala *enterprise*. Analisis trade-off dari masing-masing level berdasarkan:
   - Kecepatan eksekusi (*execution speed*).
   - Tingkat kepercayaan hasil uji (*confidence level*).
   - Biaya pemeliharaan (*maintenance cost*) ketika terjadi *refactoring* UI besar-besaran.

5. **Determinism in Golden Toolkit / Golden Tests**
   Golden Tests memverifikasi regresi visual berbasis perbandingan piksel (*pixel-by-pixel rendering*). Namun, tes ini rentan mengalami kegagalan non-deterministik (*flaky*) di lingkungan *Continuous Integration* (CI) berbasis Linux dibanding mesin lokal macOS/Windows. Jelaskan akar penyebab masalah ini (seperti sub-pixel anti-aliasing, variasi font engine, dan platform-specific canvas rendering) serta bagaimana arsitektur QA enterprise mengatasi determinisme tersebut.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **`pumpAndSettle()` Timeout Under Continuous Microtasks / Animations**
   Dalam pengujian widget (*Widget Testing*), eksekusi `tester.pumpAndSettle()` menghasilkan exception `FlutterError: pumpAndSettle timed out`. Diagnosis apa yang terjadi di balik `TestWidgetsFlutterBinding`? Identifikasi skenario umum di mana `pumpAndSettle()` gagal berhenti (misal: `CircularProgressIndicator`, *infinite animation loop*, atau Stream yang terus memancarkan event), dan bagaimana Anda memodifikasi pengujian menggunakan parameter `pump()` dengan durasi spesifik untuk menstabilkannya.

2. **Isolate Boundaries vs. Clean Architecture State**
   Operasi komputasi berat (misalnya *payload parsing* JSON 50MB atau enkripsi data lokal) didelegasikan ke `Isolate` independen (via `compute` atau `Isolate.spawn`). Bagaimana Anda mendesain arsitektur use case dan repository agar isolasi thread ini tidak melanggar *Dependency Rule* dan tidak menyebabkan kebocoran memori (*memory leaks*) akibat transfer data antar-isolate yang melewati *send/receive port*?

3. **Mocking Streams and Concurrency Control**
   Saat menguji *Use Case* yang bergantung pada reactive data source (misalnya, listenable database queries atau WebSocket stream), pengujian sering mengalami *race condition* di mana ekspektasi `emitsInOrder` selesai sebelum semua transformasi stream selesai dievaluasi. Bagaimana Anda mendesain mock repository menggunakan `StreamController` dan bagaimana implementasi `fakeAsync` / `async/await` microtask flush mengontrol eksekusi event loop dalam test harness?

4. **Cache Invalidation & Optimistic UI Concurrency**
   Sebuah Repository menerapkan pola *Cache-First with Background Sync*. Ketika dua interaksi pengguna terjadi secara simultan (misalnya *toggle bookmark* dan *update metadata*), terjadi *write-conflict* antara cache lokal (Hive/ObjectBox) dan data remote. Bagaimana Anda merekayasa repository pattern tersebut dengan *mutex/locking mechanism* atau *atomic transactions* agar konsistensi data entitas di lapisan domain tetap terjamin tanpa mengorbankan reaktivitas UI?

5. **Flaky Integration Tests on Hybrid State (Platform Channels)**
   Ketika menjalankan `integration_test` yang menguji alur login dengan *Third-Party Native SDK* (misal: Biometric Authentication / Local Auth via Platform Channel), proses testing sering *hang* atau *intermittent failure* di CI headless emulator. Bagaimana Anda merancang *Platform Channel Mocking Strategy* atau *Dependency Injection override* pada level integrasi tanpa mengubah kode produksi aplikasi?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Memory Leak & UI Jitter pada Real-Time High-Frequency Trading App
Sebuah aplikasi crypto-brokerage enterprise menampilkan data *order book* yang diperbarui melalui WebSocket hingga 100 kali per detik. Implementasi saat ini mengalirkan data langsung dari Data Source -> Repository -> Use Case -> Bloc -> UI Widget via Stream.

Setelah aplikasi berjalan selama 15 menit:
1. Frame rate drop drastis dari 60/120 FPS ke <15 FPS (*extreme UI jank*).
2. Android VSS/RSS dan iOS Memory footprint melonjak hingga sistem mematikan proses (*OOM Crash*).
3. Profiling menggunakan *DevTools Memory Allocation* menunjukkan jutaan alokasi instans Entity dan DTO yang tertahan di *old generation heap*.

**Pertanyaan Diagnostik:**
- Analisis kegagalan arsitektural pada rantai reaktif ini. Di lapisan mana *throttling/buffering* harus diintegrasikan menurut Clean Architecture?
- Mengapa pembuatan instans immutable *Value Objects/Entities* baru sebanyak 100x/detik menghancurkan kinerja Dart Garbage Collector (GC)? 
- Rancang strategi arsitektur konkret (melibatkan isolat, modifikasi Stream pipeline, dan memory-pooling/selective-rebuild) untuk menjaga latensi <16ms dengan konsumsi memori konstan.

---

### Skenario B: Silent Data Corruption pada Offline-First Field Operations App
Aplikasi inspeksi logistik beroperasi di area minim sinyal (*offline-first*). Aplikasi menggunakan repository dengan sinkronisasi dua arah: perubahan lokal dicatat di SQLite lokal, kemudian disinkronkan ke backend saat koneksi terdeteksi via background worker.

Setelah rilis versi 3.2.0, terjadi insiden integritas data fatal:
1. Inspektur A mengubah status inspeksi barang dari "Pending" menjadi "Passed" saat offline.
2. Ketika koneksi pulih secara sporadis selama 2 detik, background worker mencoba melakukan sinkronisasi *mutation*.
3. Pada saat yang sama, aplikasi menerima event SSE (*Server-Sent Events*) dari server yang membawa status lama ("Pending") dari inspektur B, menimpa SQLite lokal.
4. Mutasi lokal Inspektur A hilang tanpa memicu exception apa pun (*silent loss of updates*).

**Pertanyaan Diagnostik:**
- Identifikasi anti-pattern pada layer Repository dan Local Data Source yang memicu kondisi *Lost Update* ini.
- Bagaimana Anda merekonstruksi skema data lokal dan use case dengan menerapkan *Event Sourcing*, *Outbox Pattern*, atau *Conflict-Free Replicated Data Types (CRDTs)* untuk menjamin determinisme konsistensi data?
- Buat sebuah rancangan *integration/widget test* spesifik yang mereproduksi *race condition* sinkronisasi ini secara deterministik untuk mencegah regresi di masa depan.

---

### Skenario C: CI Pipeline Degradation & Circular Dependency Hell pada Multi-Package Monorepo
Sebuah aplikasi super-app Flutter dengan 45 kontributor aktif dibagi menjadi 30+ internal packages (menggunakan Melos) mengikuti prinsip Feature-First Clean Architecture (`feature_auth`, `feature_checkout`, `core_network`, `core_ui`, dll.).

Dalam 3 bulan terakhir, tim menghadapi masalah skalabilitas teknis:
1. *Circular Dependency*: `feature_checkout` membutuhkan data profil dari `feature_user`, tetapi `feature_user` membutuhkan riwayat transaksi dari `feature_checkout`. Tim mulai melakukan *quick-hack* dengan saling melempar import atau memindahkan class sembarangan ke `core`.
2. `core` package menjadi *God Module* yang membengkak, memicu kompilasi ulang seluruh aplikasi pada setiap commit kecil.
3. Waktu eksekusi CI pipeline untuk unit & golden tests melonjak dari 6 menit menjadi 55 menit, melumpuhkan ritme deployment harian.

**Pertanyaan Diagnostik:**
- Bagaimana Anda merestrukturisasi batas kontrak (*interfaces/ports*) antar-fitur untuk memutus dependensi sirkular tersebut tanpa menggabungkan kedua package?
- Terapkan konsep *Inversion of Control* pada level modular packaging: di mana dependensi lintas fitur harus dirakit (*composition root*)?
- Strategi arsitektur dan caching apa (misal: *Turborepo-like caching*, *fine-grained test execution* via Melos/Bazel, dynamic mocking) yang harus diimplementasikan pada pipeline QA untuk memangkas waktu eksekusi CI hingga <10 menit?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Assurance Offline-First Ledger Engine dengan Strict Clean Architecture & Comprehensive QA

#### Problem Statement
Anda ditugaskan merancang modul perbankan mikro: **"Offline-First Audit Ledger"**. Modul ini mencatat mutasi finansial sensitif. Syarat mutlak: **Nol toleransi terhadap kehilangan data**, **nol toleransi terhadap keterikatan framework pada domain logic**, dan **memiliki coverage testing menyeluruh (Unit, Widget, Golden, & Integration)**.

#### Requirements
1. **Architecture Layering**:
   - `Domain`: Harus murni Dart (`dart:core`, `dart:async`). Mendefinisikan `LedgerEntry` entity, `LedgerRepository` interface, `PostTransactionUseCase`, dan custom failure classes. Validasi bisnis mutlak: Saldo tidak boleh negatif; setiap entri mutasi harus memiliki ID UUIDv4, timestamp ISO-8601, tipe (`debit`/`credit`), dan tanda tangan hash SHA-256 integritas data.
   - `Data`: Mengimplementasikan `LedgerRepositoryImpl` dengan dua data source: `LedgerLocalDataSource` (in-memory mockable/database) dan `LedgerRemoteDataSource` (HTTP API). Mengimplementasikan *Outbox Pattern* untuk transaksi offline.
   - `Presentation`: State management menggunakan Bloc/Cubit. Mengelola status: `Idle`, `Submitting`, `Success`, `SyncPending`, dan `Error`.
2. **Quality Assurance Requirements**:
   - **Unit Tests**: Coverage Use Case dan Repository minimum 95%. Mocking data source menggunakan `mocktail` atau `mockito`. Pengujian harus memverifikasi handling kegagalan network, rollback data lokal jika hashing gagal, dan validasi domain invariant.
   - **Widget Tests**: Uji komponen form transaksi. Verifikasi interaksi tombol, rendering validasi error, dan transisi state bloc ke UI secara deterministik.
   - **Golden Test**: Render form transaksi dan status kartu mutasi pada resolusi multi-screen (Phone vs. Tablet) dengan resolusi font deterministik.
   - **Integration / Flow Test**: Uji skenario offline: Buat transaksi saat network disconnect -> verifikasi status tersimpan sebagai `SyncPending` -> simulasikan network reconnect -> verifikasi auto-sync ke remote data source berhasil dan status berubah menjadi `Synced`.

#### Constraints
- Dilarang keras mengimpor Flutter UI package apa pun ke dalam direktori `domain/`.
- Tidak boleh ada dependensi global/singleton tersembunyi; seluruh dependensi harus diinjeksi via constructor (*Constructor-based Dependency Injection*).
- Dilarang menggunakan `tester.pumpAndSettle()` tanpa durasi eksplisit atau batasan iterasi yang aman.
- Semua asynchronous testing harus bebas dari `Future.delayed` buatan (*no arbitrary sleeps*); gunakan sinkronisasi microtask atau mock streams.

#### Expected Output
1. Struktur direktori modular yang merefleksikan pemisahan *Domain*, *Data*, dan *Presentation*.
2. Implementasi kode inti:
   - `LedgerEntry` (Domain Entity dengan immutable integrity hash calculation).
   - `PostTransactionUseCase` (Domain Use Case).
   - `LedgerRepositoryImpl` (Data Repository dengan Outbox logic).
3. Berkas-berkas pengujian lengkap:
   - `post_transaction_use_case_test.dart` (Unit Test).
   - `transaction_form_widget_test.dart` (Widget Test).
   - `transaction_card_golden_test.dart` (Golden Visual Regression Test).
   - `offline_sync_integration_test.dart` (End-to-End Simulation Test).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Aturan mutlak *The Dependency Rule* (ketergantungan kode hanya boleh mengarah ke dalam, menuju Domain).
- [ ] Perbedaan fungsional antara *Entities*, *Value Objects*, dan *Data Transfer Objects (Models)*.
- [ ] Mekanisme kerja `TestWidgetsFlutterBinding`, *Phase of Frames* (Animate, Build, Layout, Paint), dan perbedaannya dengan runtime sesungguhnya.
- [ ] Alasan mengapa functional error handling (`Either`/`Result`) lebih terprediksi dibanding runtime throwing exception di level arsitektur UI.
- [ ] Cara kerja *Golden Toolkit* dalam membandingkan digest bitmap dan mitigasi perbedaan font rasterization antar OS.
- [ ] Karakteristik *Memory Leaks* di Dart yang disebabkan oleh lingering stream subscriptions, static caches, dan unbound closures di presentation layer.

### Saya tidak perlu menghafal:
- [ ] Seluruh parameter API dan method signature dari package `mocktail`, `mockito`, atau `golden_toolkit`.
- [ ] Konfigurasi boilerplate JSON serialization (`build_runner`, file `.g.dart`).
- [ ] Nilai exact pixel rendering atau path binary font file di level low-level engine Skia/Impeller.
- [ ] Kode template boilerplate untuk pendaftaran service locator (GetIt/Injectable).

### Saya harus bisa melakukan:
- [ ] Memisahkan business logic murni dari ekosistem Flutter ke dalam Domain layer tanpa ada kebocoran framework (`BuildContext`, `Color`, `Widget`).
- [ ] Menulis unit test komprehensif untuk Use Cases dengan mock dependencies menggunakan mocking framework dan matchers asinkron.
- [ ] Melakukan debugging dan perbaikan pada widget tests yang mengalami `pumpAndSettle timed out` atau *flakiness*.
- [ ] Mengonfigurasi Golden Tests deterministik yang dapat berjalan konsisten baik di lokal developer maupun di CI Pipeline (Docker/Linux environment).
- [ ] Mengisolasi pemrosesan payload data masif ke background Isolate tanpa melanggar prinsip Dependency Inversion.
- [ ] Menganalisis *memory profiling heap dump* via Dart DevTools untuk melacak retainers objek yang menyebabkan kebocoran memori.