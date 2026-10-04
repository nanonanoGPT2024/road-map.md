# Kurikulum Komprehensif Rekayasa Perangkat Lunak iOS (iOS Software Engineering)

Selamat datang di kurikulum spesialisasi rekayasa perangkat lunak iOS. Silabus ini dirancang oleh Senior Technical Curriculum Architect untuk mentransformasi rekayasawan perangkat lunak menjadi iOS Engineer tingkat lanjut (*enterprise-ready*). Silabus ini merefleksikan seluruh spektrum kompetensi resmi roadmap.sh iOS dengan pendekatan berorientasi produksi, zero-compromise pada kebersihan kode, performa deterministik, dan standar keamanan perbankan/fintech.

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
Membangun aplikasi iOS modern bukan sekadar menyusun antarmuka visual di atas canvas SwiftUI atau menulis *view controller* UIKit. Di tingkat enterprise, rekayasa iOS menuntut pemahaman mendalam tentang:
1. **Swift Memory Model & Runtime Engine**: Memahami bagaimana kompilator Swift mengalokasikan memori pada *stack* versus *heap*, cara kerja *Automatic Reference Counting* (ARC), semantik *Copy-on-Write* (CoW), hingga *dynamic* versus *static dispatch* pada tabel saksi (*witness tables*).
2. **Swift Concurrency Model (Swift 6 Ready)**: Beralih sepenuhnya dari paradigma *GCD (Grand Central Dispatch)* dan *completion handler spaghetti* menuju *Structured Concurrency*, isolasi memori mutlak via *Actors*, perlindungan terhadap *data race* saat waktu kompilasi (*compile-time data-race safety*), dan penanganan *actor reentrancy*.
3. **Arsitektur Modular Skala Besar**: Menghindari antipola *Massive View Controller* atau *God-View SwiftUI*. Kurikulum ini menekankan pemisahan batas domain murni (*Domain-Driven Design*), *The Composable Architecture* (TCA), Clean Architecture, serta pemecahan monolit aplikasi menggunakan *Swift Package Manager* (SPM) lokal yang terisolasi.
4. **Mechanical Sympathy & Profiling**: Memperlakukan ekosistem perangkat keras Apple (Apple Silicon, Neural Engine, ProMotion Display 120Hz) secara terhormat melalui diagnostik mendalam via Instruments (*Allocations*, *Leaks*, *Time Profiler*, *System Trace*), optimasi *render-loop*, pemahaman format biner Mach-O, dan reduksi waktu peluncuran aplikasi (*dyld pre-warming*).

### Prasyarat Mutlak
- **Fondasi Ilmu Komputer**: Pemahaman kuat mengenai Struktur Data, Algoritma, Manajemen Memori (Pointer, Heap, Stack), Pemrograman Berorientasi Objek (OOP), dan Paradigma Fungsional murni.
- **Lingkungan Pengembangan**: Perangkat Mac berbasis Apple Silicon (M1/M2/M3/M4) dengan RAM minimal 16 GB, menjalankan versi Xcode dan Swift Compiler terbaru.
- **Komitmen Teknis**: Kemauan membaca proposal Swift Evolution (SE), membaca kode sumber open-source Swift Runtime, menganalisis grafik dependensi, dan menolak solusi instan tanpa analisis komparatif alokasi memori.

---

## 2. Learning Roadmap

Berikut adalah peta jalan terstruktur dari 10 bab pembelajaran yang wajib diselesaikan secara linear untuk memastikan kontinuitas pemahaman sistem:

```text
Ecosystem Mastery: iOS Software Engineering
│
├── [Bab 01: Fondasi Bahasa Swift Modern, Runtime, & Sistem Memori]
│   ├── Memory Layout, Stack vs Heap, ARC, Retain Cycles
│   ├── Type System: Generics, Existential Types, Opaque Return Types
│   └── Swift Runtime Internals & Method Dispatch Engine
│
├── [Bab 02: Desain Antarmuka Deklaratif dengan SwiftUI Tingkat Lanjut]
│   ├── View Hierarchy, Render Graph, Dependency Tracking
│   ├── State Management Engine: Observation Framework & Property Wrappers
│   └── Interoperabilitas Dua Arah UIKit & SwiftUI
│
├── [Bab 03: Arsitektur UI Imperatif & Pola Klasik UIKit]
│   ├── UIViewController Lifecycle & UIWindow Scene Management
│   ├── Auto Layout Engine: Cassowary, Constraints, & Custom Layouts
│   └── Modern UICollectionView: Diffable Data Source & Compositional Layout
│
├── [Bab 04: Pemrograman Asinkron Modern & Swift Concurrency]
│   ├── Async/Await, Task, TaskGroup, & Structured Concurrency
│   ├── Actor Isolation, Global Actors, & Data Race Safety (Swift 6)
│   └── AsyncSequence, Custom Streams, & Backpressure Handling
│
├── [Bab 05: Pola Arsitektur Skala Besar (Clean Architecture, MVVM, & TCA)]
│   ├── Modularization via Local Swift Packages (SPM)
│   ├── Clean Architecture + MVVM-C (Coordinator Pattern)
│   └── The Composable Architecture (TCA): State Machines & Reducers
│
├── [Bab 06: Jaringan, Serialisasi Data, & Offline-First Persistence]
│   ├── Enterprise Networking Engine (URLSession, Interceptors, SSL)
│   ├── Core Data vs SwiftData Deep-Dive (Under the Hood)
│   └── Offline-First Sync Engine & SQLite Low-Level Optimization
│
├── [Bab 07: Kinerja Aplikasi, Diagnostik Instruments, & Profiling]
│   ├── Instruments: Allocations, Leaks, Memory Graph, & Zombie Objects
│   ├── CPU Optimization: Time Profiler, Thermal Throttling, Frame Hitch
│   └── App Launch Optimization: dyld, Mach-O, & Pre-main Reduction
│
├── [Bab 08: Pengujian Perangkat Lunak Komprehensif (XCTest & UI Testing)]
│   ├── Unit Testing, Mocking Strategies, & Inversion of Control
│   ├── Integration Testing, Network Stubbing, & Concurrency Testing
│   └── UI Automation, Snapshot Testing, & Flaky Test Elimination
│
├── [Bab 09: Keamanan Aplikasi iOS & Enkripsi Tingkat Enterprise]
│   ├── Keychain Services, Secure Enclave, & Local Authentication
│   ├── Cryptography: CryptoKit, AES-GCM, & Ephemeral Key Exchanges
│   └── Binary Hardening, Anti-Jailbreak, Obfuscation, & TLS Pinning
│
└── [Bab 10: CI/CD, Automasi Fastlane, & App Store Deployment]
    ├── Pipeline Otomasi: Fastlane, Match, Code Signing Identity
    ├── Enterprise CI/CD: GitHub Actions, Mac Runners, TestFlight
    └── App Review Guidelines, Phased Rollout, & Production Crash Triage
```

---

## 3. Navigasi Detail Modul Pembelajaran

### [Bab 01: Fondasi Bahasa Swift Modern, Runtime, & Sistem Memori](./01-swift-foundations-and-runtime/README.md)
Fokus: Mengupas cara kerja Swift di bawah kap mesin kompilator LLVM, layout memori, semantik nilai vs referensi, dan determinasi alokasi memori.
- [01. Type System, Generics, Value vs Reference Semantics, & Memory Layout](./01-swift-foundations-and-runtime/01-type-system-memory-layout.md)
- [02. Automatic Reference Counting (ARC), Memory Leaks, & Retain Cycles](./01-swift-foundations-and-runtime/02-arc-and-memory-management.md)
- [03. Swift Runtime Internals, Dynamic vs Static Dispatch, & Witness Tables](./01-swift-foundations-and-runtime/03-swift-runtime-and-dispatch.md)

### [Bab 02: Desain Antarmuka Deklaratif dengan SwiftUI Tingkat Lanjut](./02-advanced-declarative-swiftui/README.md)
Fokus: Arsitektur rendering deklaratif Apple, manajemen state reaktif, optimasi render tree, dan integrasi mulus dengan framework UIKit warisan.
- [01. SwiftUI Render Graph, View Lifecycle, & Identifiable Identity Traps](./02-advanced-declarative-swiftui/01-render-graph-and-identity.md)
- [02. State Management Modern: @Observable Framework & Property Wrappers](./02-advanced-declarative-swiftui/02-state-management-observation.md)
- [03. Interoperabilitas: UIViewRepresentable, UIHostingController, & Coordinator Bridge](./02-advanced-declarative-swiftui/03-uikit-swiftui-interop.md)

### [Bab 03: Arsitektur UI Imperatif & Pola Klasik UIKit](./03-imperative-uikit-architecture/README.md)
Fokus: Menguasai platform dasar UI iOS, siklus hidup UIViewController, algoritma Cassowary pada Auto Layout, dan sistem antarmuka berbasis koleksi berperforma tinggi.
- [01. UIViewController Lifecycle, SceneDelegate, & Memory Leak Mitigation](./03-imperative-uikit-architecture/01-viewcontroller-lifecycle-scenedelegate.md)
- [02. Auto Layout Internals, Cassowary Constraints, & Custom UI Control Development](./03-imperative-uikit-architecture/02-autolayout-cassowary-custom-controls.md)
- [03. Modern UICollectionView: Compositional Layouts & Diffable Data Sources](./03-imperative-uikit-architecture/03-collectionview-diffable-data-sources.md)

### [Bab 04: Pemrograman Asinkron Modern & Swift Concurrency](./04-swift-concurrency-deep-dive/README.md)
Fokus: Rekayasa multi-threading tanpa kompromi; meninggalkan model lama DispatchQueue menuju model isolasi kompilator Swift 6 yang sepenuhnya tahan terhadap *data race*.
- [01. Async/Await, Task Cancellation, & Structured Concurrency Tree](./04-swift-concurrency-deep-dive/01-async-await-structured-concurrency.md)
- [02. Actors, Global Actors (@MainActor), Reentrancy, & Compile-Time Data Safety](./04-swift-concurrency-deep-dive/02-actors-and-data-race-safety.md)
- [03. AsyncStream, AsyncSequence, & Custom Backpressure Mechanism](./04-swift-concurrency-deep-dive/03-asyncstream-and-backpressure.md)

### [Bab 05: Pola Arsitektur Skala Besar (Clean Architecture, MVVM, & TCA)](./05-enterprise-ios-architecture/README.md)
Fokus: Mendesain aplikasi monolitik menjadi puluhan modul independen, mengisolasi logika bisnis domain dari framework Apple, dan menerapkan state machine deterministik.
- [01. Multi-Module Project Architecture using Local Swift Packages (SPM)](./05-enterprise-ios-architecture/01-modularization-spm-architecture.md)
- [02. Clean Architecture, Domain-Driven Design, & MVVM-Coordinator (MVVM-C)](./05-enterprise-ios-architecture/02-clean-architecture-and-mvvm-c.md)
- [03. The Composable Architecture (TCA): Deterministic Reducers, State, & Effects](./05-enterprise-ios-architecture/03-the-composable-architecture-tca.md)

### [Bab 06: Jaringan, Serialisasi Data, & Offline-First Persistence](./06-networking-and-persistence/README.md)
Fokus: Membangun *network layer* enterprise berbasis actor, deserialisasi berperforma tinggi, dan strategi *persistence* data lokal menggunakan Core Data dan SwiftData.
- [01. Robust Networking Engine: URLSession, Actor-Based Interceptors, & Retry Policies](./06-networking-and-persistence/01-actor-urlsession-network-layer.md)
- [02. Core Data Internals vs SwiftData Architecture: Schema, Migration, & Context Concurrency](./06-networking-and-persistence/02-coredata-vs-swiftdata.md)
- [03. Offline-First Sync Strategies, Conflict Resolution, & SQLite-Level Profiling](./06-networking-and-persistence/03-offline-first-sync-sqlite.md)

### [Bab 07: Kinerja Aplikasi, Diagnostik Instruments, & Profiling](./07-performance-profiling-and-instruments/README.md)
Fokus: Melakukan profil mendalam sistem dengan Xcode Instruments, mencegah frame hitching pada Core Animation, dan memangkas waktu start aplikasi secara drastis.
- [01. Xcode Instruments: Allocations, Leaks, Memory Footprint, & Retain Graph Traversal](./07-performance-profiling-and-instruments/01-instruments-allocations-leaks.md)
- [02. Core Animation Pipeline, GPU Frame Drop Diagnosis, & ProMotion 120Hz Smoothness](./07-performance-profiling-and-instruments/02-time-profiler-core-animation.md)
- [03. App Startup Optimization: Mach-O Binary, dyld4 Engine, & Pre-main Trimming](./07-performance-profiling-and-instruments/03-app-startup-mach-o-dyld.md)

### [Bab 08: Pengujian Perangkat Lunak Komprehensif (XCTest & UI Testing)](./08-testing-and-quality-assurance/README.md)
Fokus: Standar industri pengujian perangkat lunak, mencakup *unit test* terisolasi, pengujian state asinkron, *snapshot testing*, dan pengujian fungsional otomatis end-to-end.
- [01. Unit Testing Engine, Mocking/Stubbing Strategies, & IoC Container Verification](./08-testing-and-quality-assurance/01-unit-testing-and-mocking.md)
- [02. Testing Swift Concurrency, Custom Schedulers, & Inverted Expectations](./08-testing-and-quality-assurance/02-testing-async-and-concurrency.md)
- [03. End-to-End Automation with XCUITest, Snapshot View Testing, & Performance Metrices](./08-testing-and-quality-assurance/03-xcuitest-and-snapshot-testing.md)

### [Bab 09: Keamanan Aplikasi iOS & Enkripsi Tingkat Enterprise](./09-enterprise-security-and-hardening/README.md)
Fokus: Proteksi data perbankan, enkripsi kriptografis tingkat militer, integrasi perangkat keras *Secure Enclave*, pencegahan inspeksi biner, dan *jailbreak mitigation*.
- [01. Keychain Services API, Secure Enclave Coprocessor, & Biometric Auth Policy](./09-enterprise-security-and-hardening/01-keychain-secure-enclave.md)
- [02. CryptoKit: AES-GCM, ChaCha20-Poly1305, Ephemeral Keys, & Dynamic TLS Pinning](./09-enterprise-security-and-hardening/02-cryptokit-and-tls-pinning.md)
- [03. Binary Hardening, Anti-Tamper/Jailbreak Detection, & Runtime Integrity Verification](./09-enterprise-security-and-hardening/03-binary-hardening-anti-jailbreak.md)

### [Bab 10: CI/CD, Automasi Fastlane, & App Store Deployment](./10-cicd-automation-and-deployment/README.md)
Fokus: Menghilangkan proses manual dengan orkestrasi pipeline otomatis kelas industri, distribusi internal dan publik, penandatanganan kode sertifikat, serta pemantauan produksi.
- [01. Code Signing Deconstructed: Certificates, Provisioning Profiles, & Fastlane Match](./10-cicd-automation-and-deployment/01-code-signing-and-fastlane-match.md)
- [02. CI/CD Pipeline Automation: GitHub Actions, Mac Mini Farm, & TestFlight Distribution](./10-cicd-automation-and-deployment/02-github-actions-cicd-pipeline.md)
- [03. App Thinning (Slicing/Bitcode), Phased Release Strategies, & DSYM Symbolication](./10-cicd-automation-and-deployment/03-app-thinning-dsym-crash-triage.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Nama Proyek: **AuraTrade: Institutional Multi-Asset Trading & Portfolio Engine**

### Deskripsi Sistem
AuraTrade adalah aplikasi perdagangan aset terdesentralisasi dan multi-pasar yang dirancang dengan standar keandalan finansial perbankan (*Fintech Institutional-Grade*). Aplikasi ini melayani jutaan transaksi volume tinggi, menerima *market feed tick-by-tick* melalui koneksi WebSocket ganda, menyediakan grafik interaktif 120 FPS tanpa penurunan frame, bekerja secara offline melalui database lokal terenkripsi, dan menjaga data otentikasi menggunakan chip perangkat keras *Secure Enclave*.

### Architectural Blueprint & Tech Stack
```text
                      [ Presentation Layer: SwiftUI + TCA (Swift 6) ]
                                            │
                      [ Dependency Injection & Feature Module SPM ]
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
        [ Domain: Core Trading Engine ]               [ Domain: Real-Time Telemetry ]
                     │                                             │
      ┌──────────────┴──────────────┐                              │
      ▼                             ▼                              ▼
[ CryptoKit Security ]     [ Data Persistence ]         [ Network: WebSocket Actor ]
[  Secure Enclave    ]     [ SwiftData + SQLite]        [ Actor-Isolated URLSession]
```

- **Bahasa & Kompilator**: Swift 6, Strict Concurrency Checking (`-strict-concurrency=complete`), Zero Swift 6 warnings.
- **Antarmuka Utama**: SwiftUI murni dengan integrasi UIKit khusus untuk *high-frequency rendering canvas*.
- **Pola Arsitektur**: The Composable Architecture (TCA) versi terbaru atau Modular Clean Architecture dengan Coordinator Pattern.
- **Dependency Management**: Swift Package Manager (SPM) lokal (100% modularisasi: CoreKit, NetworkKit, StorageKit, SecurityKit, FeatureTrading, FeaturePortfolio, UIDesignSystem).
- **Asinkron & Concurrency**: Swift Concurrency murni (`actor`, `TaskGroup`, `AsyncStream` untuk WebSocket events). Dilarang keras menggunakan *DispatchQueue* secara manual kecuali untuk interaksi antarmuka driver C-level.
- **Persistensi Data**: SwiftData terintegrasi dengan sinkronisasi deterministik SQLite untuk audit trail dan penyimpanan riwayat transaksi lokal yang terenkripsi SQLCipher.
- **Jaringan**: Network Layer kustom berbasis `actor` dengan dukungan HTTP/3, TLS Pinning dinamis, dan fallback otomatis ke buffer lokal jika offline.
- **Keamanan**: Penyimpanan token sesi di Secure Enclave menggunakan enkripsi asimetris kurva P-256 (`SecKeyProxy`), biometrik via `LocalAuthentication`, dan deteksi root/jailbreak berbasis komputasi biner.

### Acceptance Criteria (Kriteria Keberterimaan Produksi)
1. **Performa Render**:
   - Tampilan grafik pasar (*Orderbook & Candlestick*) harus mempertahankan rendering konstan 120 FPS pada layar ProMotion dan 60 FPS pada layar standar tanpa *frame drop* (*zero hitch rate*), bahkan saat menerima 100 pesanan per detik via WebSocket.
2. **Kestabilan Memori & Runtime**:
   - Zero Retain Cycles saat dianalisis menggunakan *Xcode Memory Graph Debugger* dan Instruments *Leaks*.
   - Alokasi memori (*heap footprint*) tidak boleh melebihi 85 MB selama pengujian stress test berjalan 30 menit terus-menerus.
3. **Konkurensi & Integritas Data**:
   - Wajib lolos audit Thread Sanitizer (TSan) tanpa satu pun temuan *data race* atau *priority inversion*.
   - Dukungan pemulihan jaringan secara transparan: ketika jaringan terputus tiba-tiba, aplikasi masuk ke status degradasi offline terisolasi tanpa memicu crash, dan melakukan sinkronisasi otomatis (*reconciliation*) saat jaringan pulih.
4. **Cakupan Pengujian**:
   - Cakupan pengujian unit (*Unit Test Coverage*) minimal 90% pada Domain Layer dan State Reducers.
   - Tersedia pengujian otomatis *Snapshot Testing* untuk semua varian status komponen UI (Light, Dark, Dynamic Type Accessibility XXXL).
5. **Otomasi CI/CD**:
   - Pipa integrasi berkelanjutan (CI/CD) wajib mengompilasi biner, menjalankan linter (SwiftLint/SwiftFormat), mengeksekusi seluruh rangkaian pengujian unit, memverifikasi tanda tangan digital via Fastlane Match, dan merilis berkas `.ipa` ke TestFlight tanpa intervensi manual.

### Rubrik Evaluasi

| Dimensi Penilaian | Bobot | Kriteria Skor Sempurna (100%) | Kriteria Kegagalan (0%) |
| :--- | :--- | :--- | :--- |
| **Arsitektur & Modularitas** | 25% | Modularisasi penuh via SPM lokal; pemisahan mutlak antara UI, Domain, dan Data; dependensi modular satu arah tanpa dependensi sirkular. | Struktur monolitik; kode bisnis bercampur di dalam View; dependensi sirkular antar modul. |
| **Swift Concurrency & Thread Safety** | 25% | Bebas peringatan pada Swift 6 mode lengkap; penggunaan Actor dan GlobalActor yang tepat; tidak ada deadlock atau race condition. | Terdeteksi data race oleh TSan; menggunakan lock manual yang memicu deadlock; pemblokiran thread utama (*main thread freeze*). |
| **Optimasi Performa & Diagnostik** | 20% | Lolos verifikasi Instruments (Leaks, Allocations); zero memory leaks; frame rate stabil di 120/60 FPS; konsumsi baterai efisien. | Terdeteksi retain cycle; visual lag kentara (<40 FPS); konsumsi memori membengkak secara eksponensial (*uncontrolled growth*). |
| **Keamanan & Ketahanan Sistem** | 15% | SSL Pinning aktif; Secure Enclave terimplementasi untuk token kritis; mitigasi deteksi *jailbreak*; enkripsi data lokal. | Kredensial disimpan dalam `UserDefaults` secara plain text; sertifikat SSL tidak divalidasi; data sensitif terekspos di log konsol. |
| **Kualitas Pengujian & CI/CD** | 15% | Code coverage >90% pada core domain; pengujian asinkron berjalan deterministik; Fastlane pipeline mengotomasi build & deploy ke TestFlight. | Tidak ada unit test; pengujian bersifat flaki (*flaky tests*); proses build dan signing masih dilakukan manual melalui GUI Xcode. |

---

> **Panduan Belajar**: Mulailah dari [Bab 01: Fondasi Bahasa Swift Modern, Runtime, & Sistem Memori](./01-swift-foundations-and-runtime/README.md). Pahami konsep teoritis secara mendalam sebelum melompat ke implementasi praktis dan proyek capstone. Eksekusi setiap modul dengan membuka Xcode, membuat unit test terisolasi, dan memverifikasi alokasi memori menggunakan Instruments.