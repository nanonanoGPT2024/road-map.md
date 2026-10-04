# Enterprise Modern Android Engineering: From Architecture to Zero-Jank Scale

Selamat datang di kurikulum rekayasa perangkat lunak Android modern tingkat lanjut. Silabus ini disusun dengan pendekatan **Modern Android Development (MAD)** berstandar industri skala besar (*enterprise-grade*). Kurikulum ini dirancang untuk mentransformasi *software engineer* menjadi **Senior/Staff Android Engineer** yang mampu merancang, membangun, mengamankan, dan mengoptimalkan aplikasi Android berskala puluhan juta *Daily Active Users* (DAU) dengan prinsip keandalan tinggi, *zero-downtime*, dan *zero-jank performance*.

---

## 1. Course Overview & Engineering Mindset

Dalam ekosistem *enterprise*, pengembangan Android tidak lagi berfokus pada "bagaimana membuat tampilan UI berfungsi", melainkan pada **stabilitas arsitektural, determinisme state, efisiensi konsumsi daya/memori, isolasi dependensi, serta ketahanan jaringan**. 

### Paradigma & Pola Pikir Utama:
1. **Modern Android Development (MAD) First:** 100% Kotlin idiomatik, Jetpack Compose deklaratif, Kotlin Coroutines & Structured Concurrency, serta Android Jetpack libraries modern. Pola imperatif lawas (XML, AsyncTask, Java interop fragmentasi tinggi) dieliminasi.
2. **Deterministic Unidirectional Data Flow (UDF):** Memastikan state aplikasi dapat diprediksi secara matematis melalui Clean Architecture dan MVI (*Model-View-Intent*), mencegah *race condition* dan *state inconsistency*.
3. **Decoupled Multi-Module Architecture:** Membagi sistem ke dalam modul-modul independen (*core*, *feature*, *domain*, *data*, *ui-kit*) untuk skalabilitas tim lintas negara (*cross-functional pods*) dan *build time* yang optimal melalui *caching* & *parallel execution*.
4. **Resilience & Offline-First:** Mengasumsikan jaringan selalu rentan gagal (*network is fallible*). Aplikasi harus berfungsi mulus dalam keadaan luring (*offline-first*), memanfaatkan *conflict resolution engine*, *local persistence caching*, dan sinkronisasi latar belakang yang andal.
5. **Hardened Security by Default:** Enkripsi *at-rest* dan *in-transit*, isolasi kriptografi berbasis *hardware* (*Android Keystore Provider*, StrongBox), proteksi integritas aplikasi dari *reverse-engineering*, *rooting*, dan manipulasi *runtime*.
6. **Zero-Tolerance on Performance Degradation:** Mengukur performa menggunakan metrik objektif: Frame rate stabil 60/120 FPS (*zero dropped frames*), *Time-to-Initial-Display* (TID) di bawah 800ms, serta alokasi memori yang bebas dari kebocoran (*leak-free lifecycle*).

---

## 2. Learning Roadmap

```text
Enterprise Modern Android Engineering
│
├── [Bab 01] Fondasi Modern Android & Kotlin Coroutines/Flow Internal
│   ├── Modul 01-1: Kotlin Memory Model, Bytecode, & Metaprogramming
│   ├── Modul 01-2: Coroutines Internal: Continuation, Dispatchers, & Scopes
│   └── Modul 01-3: Reactive Streams: Hot vs Cold Flow, Channels, & SharedFlow
│
├── [Bab 02] Declarative UI dengan Jetpack Compose & State Management
│   ├── Modul 02-1: Compose Runtime, Compiler, Gap Buffer, & Recomposition
│   ├── Modul 02-2: Deterministic State Hoisting, Snapshot State, & Side Effects
│   └── Modul 02-3: Custom Layouts, SubcomposeLayout, Canvas, & RenderNode
│
├── [Bab 03] Arsitektur Android Modern (Clean Architecture, MVI, & UDF)
│   ├── Modul 03-1: Unidirectional Data Flow (UDF) & MVI State Machine Pattern
│   ├── Modul 03-2: Domain Boundaries: Purity, Interactors, & Business Invariants
│   └── Modul 03-3: Navigation Compose, Deep Linking, & Screen Lifecycle Scoping
│
├── [Bab 04] Dependency Injection Enterprise (Dagger-Hilt & KSP)
│   ├── Modul 04-1: Dependency Inversion, Compile-Time Graph, & Hilt Internals
│   ├── Modul 04-2: Scopes Lifecycle, Custom Qualifiers, & Dynamic Module Injection
│   └── Modul 04-3: Assisted Injection & High-Performance Test Orchestration
│
├── [Bab 05] Data Layer, Offline-First, & Room ORM Persistence
│   ├── Modul 05-1: Room DB Architecture, SQLite Engines, & WAL Mode Internals
│   ├── Modul 05-2: Offline-First Synchronization & Distributed Conflict Resolution
│   └── Modul 05-3: Jetpack DataStore, Protobuf Serialization, & Data Integrity
│
├── [Bab 06] Networking, Serialization, & API Resilience
│   ├── Modul 06-1: OkHttp Engine, Retrofit/Ktor Architecture, & HTTP/3 QUIC
│   ├── Modul 06-2: Kotlinx.Serialization & Protocol Buffers Serialization
│   └── Modul 06-3: Network Resilience: Circuit Breakers, Backoff, & SSE
│
├── [Bab 07] Asynchronous Background Processing & WorkManager
│   ├── Modul 07-1: Android OS Power Buckets, Doze Mode, & Execution Limits
│   ├── Modul 07-2: Jetpack WorkManager: Chaining, Expedited Work, & Constraints
│   └── Modul 07-3: Foreground Services, Media Playback, & Location Tracking
│
├── [Bab 08] Android Security, Keystore, & App Hardening
│   ├── Modul 08-1: Android Keystore Provider, Hardware TEE, & StrongBox Keymaster
│   ├── Modul 08-2: TLS/SSL Pinning, Network Security Config, & MitM Defense
│   └── Modul 08-3: Bytecode Obfuscation, R8 Optimization, & Anti-Tamper/Root Detection
│
├── [Bab 09] Performance Profiling, Memory Leaks, & Benchmarking
│   ├── Modul 09-1: Android Profiler: CPU Tracing, Systrace, & Thread Contention
│   ├── Modul 09-2: JVM Heap Dumps, GC Analysis, & Eliminating Memory Leaks
│   └── Modul 09-3: Macrobenchmark, Microbenchmark, & Cloud-Ready Baseline Profiles
│
└── [Bab 10] Multi-Modular Architecture, Gradle Optimization, & CI/CD
    ├── Modul 10-1: Multi-Module Graph Decoupling: Feature-by-Layer vs Feature-by-Module
    ├── Modul 10-2: Gradle Build Cache, Configuration Cache, & Custom Convention Plugins
    └── Modul 10-3: Industrial CI/CD Pipeline: Static Analysis, Fastlane, & Play Delivery
```

---

## 3. Navigasi Detail Bab 01 s/d Bab 10

### [Bab 01: Fondasi Modern Android & Kotlin Coroutines/Flow Internal](bab-01/README.md)
Menguasai model eksekusi bahasa Kotlin pada level *runtime* JVM/ART serta fondasi konkurensi non-blocking menggunakan Coroutines dan Reactive Flow.
- **[Modul 01-1: Kotlin Memory Model, Bytecode, & Metaprogramming](bab-01/modul-01-1.md)**: Analisis Kotlin Bytecode, Inline Classes, Value Classes, Memory Allocation pada ART, dan Java-interoperability overhead.
- **[Modul 01-2: Coroutines Internal: Continuation, Dispatchers, & Scopes](bab-01/modul-01-2.md)**: Dekonstruksi state machine Coroutine, alokasi thread pada CoroutineDispatcher, Structured Concurrency, serta penanganan Exception propagation.
- **[Modul 01-3: Reactive Streams: Hot vs Cold Flow, Channels, & SharedFlow](bab-01/modul-01-3.md)**: Penguasaan `Flow`, `StateFlow`, `SharedFlow`, `Channel`, dan *backpressure strategy* untuk sistem *event-driven*.

### [Bab 02: Declarative UI dengan Jetpack Compose & State Management](bab-02/README.md)
Mendalami paradigma UI deklaratif dengan Jetpack Compose, dekonstruksi Compose Compiler, alur rekomposisi, serta optimasi *rendering pipeline*.
- **[Modul 02-1: Compose Runtime, Compiler, Gap Buffer, & Recomposition](bab-02/modul-02-1.md)**: Cara kerja Compose Compiler, Slot API, Gap Buffer data structure, penentuan stabilitas tipe (`@Stable`, `@Immutable`), dan mitigasi *unnecessary recompositions*.
- **[Modul 02-2: Deterministic State Hoisting, Snapshot State, & Side Effects](bab-02/modul-02-2.md)**: Implementasi Snapshot State system, pengelolaan efek samping (`LaunchedEffect`, `rememberCoroutineScope`, `DisposableEffect`, `derivedStateOf`).
- **[Modul 02-3: Custom Layouts, SubcomposeLayout, Canvas, & RenderNode](bab-02/modul-02-3.md)**: Siklus pengukuran (*Measure*), tata letak (*Layout*), dan penggambaran (*Draw*); optimalisasi `LayoutModifier`, `SubcomposeLayout`, dan *Hardware-accelerated Canvas*.

### [Bab 03: Arsitektur Android Modern (Clean Architecture, MVI, & UDF)](bab-03/README.md)
Perancangan arsitektur enterprise dengan pemisahan dependensi ketat berbasis Clean Architecture dan mesin state deterministik Model-View-Intent.
- **[Modul 03-1: Unidirectional Data Flow (UDF) & MVI State Machine Pattern](bab-03/modul-03-1.md)**: Perancangan UI State, UI Events/Intents, Side-Effects, dan reducers deterministik yang tahan terhadap perubahan konfigurasi.
- **[Modul 03-2: Domain Boundaries: Purity, Interactors, & Business Invariants](bab-03/modul-03-2.md)**: Domain-Driven Design (DDD) sub-context, pembuatan *pure Kotlin* Use Cases/Interactors, pemodelan entitas murni, dan penanganan kegagalan bisnis terstandar.
- **[Modul 03-3: Navigation Compose, Deep Linking, & Screen Lifecycle Scoping](bab-03/modul-03-3.md)**: Implementasi *Type-Safe Navigation Compose*, pengelolaan *BackStackEntry lifecycle*, transmisi *parcelable arguments*, dan orkestrasi deep linking kompleks.

### [Bab 04: Dependency Injection Enterprise (Dagger-Hilt & KSP)](bab-04/README.md)
Manajemen dependensi skala enterprise memanfaatkan Dagger-Hilt yang dioptimalkan dengan Kotlin Symbol Processing (KSP).
- **[Modul 04-1: Dependency Inversion, Compile-Time Graph, & Hilt Internals](bab-04/modul-04-1.md)**: Evaluasi grafik dependensi waktu-kompilasi (*compile-time graph validation*), integrasi KSP, dan *code generation analysis*.
- **[Modul 04-2: Scopes Lifecycle, Custom Qualifiers, & Dynamic Module Injection](bab-04/modul-04-2.md)**: Hierarki Scope (`@Singleton`, `@ActivityRetainedScoped`, `@ViewModelScoped`), Qualifiers, dan integrasi injeksi dependensi pada *dynamic-feature modules*.
- **[Modul 04-3: Assisted Injection & High-Performance Test Orchestration](bab-04/modul-04-3.md)**: Pola `@AssistedInject` untuk parameter *runtime*, isolasi dependensi pengujian (*test doubles/fakes*), dan integrasi Hilt dalam unit test serta instrumented test.

### [Bab 05: Data Layer, Offline-First, & Room ORM Persistence](bab-05/README.md)
Membangun lapisan data *resilient* dengan skema persistensi relasional lokal Room, enkripsi data, dan mesin sinkronisasi offline-first.
- **[Modul 05-1: Room DB Architecture, SQLite Engines, & WAL Mode Internals](bab-05/modul-05-1.md)**: Threading model Room, Write-Ahead Logging (WAL), indeks komposit, kompleksitas query, dan strategi migrasi skema data (otomatis & manual).
- **[Modul 05-2: Offline-First Synchronization & Distributed Conflict Resolution](bab-05/modul-05-2.md)**: Pola *Single Source of Truth* (SSOT), *optimistic updates*, sinkronisasi dua arah, dan resolusi konflik deterministik (misal: *vector clocks / last-write-wins*).
- **[Modul 05-3: Jetpack DataStore, Protobuf Serialization, & Data Integrity](bab-05/modul-05-3.md)**: Migrasi dari SharedPreferences ke Proto DataStore yang thread-safe, non-blocking, serta bebas dari resiko *UI-blocking ANR*.

### [Bab 06: Networking, Serialization, & API Resilience](bab-06/README.md)
Arsitektur komunikasi jaringan tingkat enterprise: protokol modern, serialization cepat, dan pola ketahanan sistem terdistribusi.
- **[Modul 06-1: OkHttp Engine, Retrofit/Ktor Architecture, & HTTP/3 QUIC](bab-06/modul-06-1.md)**: Connection pooling, interceptor pipelines, multiplexing HTTP/2 dan HTTP/3, serta perancangan Network Client berbasis Ktor & Retrofit.
- **[Modul 06-2: Kotlinx.Serialization & Protocol Buffers Serialization](bab-06/modul-06-2.md)**: Serialisasi biner dan JSON performa tinggi, polimorfisme kelas, dan pemanfaatan Protocol Buffers (gRPC/Protobuf) untuk efisiensi *payload*.
- **[Modul 06-3: Network Resilience: Circuit Breakers, Backoff, & SSE](bab-06/modul-06-3.md)**: Implementasi Exponential Backoff dengan Jitter, pola Circuit Breaker untuk degradasi bertahap (*graceful degradation*), dan integrasi Server-Sent Events (SSE)/WebSockets.

### [Bab 07: Asynchronous Background Processing & WorkManager](bab-07/README.md)
Eksekusi tugas latar belakang yang patuh pada regulasi daya Android OS (Doze Mode, App Standby Buckets) menggunakan Jetpack WorkManager.
- **[Modul 07-1: Android OS Power Buckets, Doze Mode, & Execution Limits](bab-07/modul-07-1.md)**: Arsitektur manajemen daya Android modern, pembatasan eksekusi latar belakang, optimasi baterai, dan alokasi kuota pemrosesan.
- **[Modul 07-2: Jetpack WorkManager: Chaining, Expedited Work, & Constraints](bab-07/modul-07-2.md)**: Perancangan WorkRequests berantai (*chaining*), *parallel execution*, Work Constraints (jaringan/baterai/penyimpanan), dan *Expedited Jobs* via CoroutineWorker.
- **[Modul 07-3: Foreground Services, Media Playback, & Location Tracking](bab-07/modul-07-3.md)**: Penanganan Foreground Service yang patuh terhadap izin Android 13/14+, integrasi notifikasi sistem, dan pemrosesan lokasi berkelanjutan.

### [Bab 08: Android Security, Keystore, & App Hardening](bab-08/README.md)
Melindungi aset, identitas pengguna, dan integritas biner aplikasi dari eksploitasi, pembajakan data, dan serangan *man-in-the-middle*.
- **[Modul 08-1: Android Keystore Provider, Hardware TEE, & StrongBox Keymaster](bab-08/modul-08-1.md)**: Kriptografi simetris/asimetris (AES-GCM, RSA), isolasi kunci di Hardware Security Module (HSM)/TEE, dan otentikasi biometrik (*BiometricPrompt API*).
- **[Modul 08-2: TLS/SSL Pinning, Network Security Config, & MitM Defense](bab-08/modul-08-2.md)**: Public Key Pinning, Certificate Transparency, mitigasi serangan Proxy/Burp Suite, dan validasi sertifikat dinamis tingkat enterprise.
- **[Modul 08-3: Bytecode Obfuscation, R8 Optimization, & Anti-Tamper/Root Detection](bab-08/modul-08-3.md)**: Konfigurasi tingkat lanjut R8/ProGuard (rules optimization), deteksi root/jailbreak, deteksi emulator, Play Integrity API, dan pencegahan *re-packaging*.

### [Bab 09: Performance Profiling, Memory Leaks, & Benchmarking](bab-09/README.md)
Analisis mendalam performa aplikasi menggunakan profiler perangkat keras/lunak, eliminasi *memory leaks*, dan optimalisasi kompilasi ART via Baseline Profiles.
- **[Modul 09-1: Android Profiler: CPU Tracing, Systrace, & Thread Contention](bab-09/modul-09-1.md)**: Penggunaan Android Studio Profiler, Perfetto trace, Systrace visualizer, identifikasi *thread locking*, dan pemantauan utilisasi CPU core.
- **[Modul 09-2: JVM Heap Dumps, GC Analysis, & Eliminating Memory Leaks](bab-09/modul-09-2.md)**: Analisis Hprof heap dump, penanganan Garbage Collection thrashing, isolasi referensi siklik dengan LeakCanary, dan kepatuhan terhadap StrictMode.
- **[Modul 09-3: Macrobenchmark, Microbenchmark, & Cloud-Ready Baseline Profiles](bab-09/modul-09-3.md)**: Automasi pengujian waktu luncur (*Startup Timing*: Cold, Warm, Hot), pengukuran UI Jank via Jetpack Macrobenchmark, dan pembuatan *custom Baseline Profiles*.

### [Bab 10: Multi-Modular Architecture, Gradle Optimization, & CI/CD](bab-10/README.md)
Skalabilitas basis kode enterprise: modularisasi modular, otomasi proses build dengan Gradle Kotlin DSL, serta implementasi *Continuous Integration / Continuous Deployment*.
- **[Modul 10-1: Multi-Module Graph Decoupling: Feature-by-Layer vs Feature-by-Module](bab-10/modul-10-1.md)**: Strategi modularisasi tingkat tinggi: module graph decoupling, pemisahan `api` vs `implementation`, modul *core-model*, *core-database*, *core-network*, dan integrasi dinamis.
- **[Modul 10-2: Gradle Build Cache, Configuration Cache, & Custom Convention Plugins](bab-10/modul-10-2.md)**: Pemanfaatan *Gradle Build Cache*, *Configuration Cache*, *Gradle Version Catalogs* (`libs.versions.toml`), dan perancangan *custom build convention plugins* (`build-logic`).
- **[Modul 10-3: Industrial CI/CD Pipeline: Static Analysis, Fastlane, & Play Delivery](bab-10/modul-10-3.md)**: Pipeline GitHub Actions otomatis: linting (ktlint, detekt), static analysis (Android Lint, SonarQube), Fastlane deployment, dan Google Play Store internal app sharing/track release.

---

## 4. Enterprise Capstone Project Specification

Di akhir kurikulum ini, peserta wajib mengimplementasikan proyek akhir kelas dunia yang membuktikan penguasaan komprehensif atas seluruh modul:

### Judul Capstone:
**"OmniTrade Mobile: Enterprise Real-Time Multi-Asset Trading Platform"**

### Ikhtisar Proyek:
Sebuah platform perdagangan instrumen keuangan global (saham & kripto) multi-modul yang beroperasi secara *real-time* via WebSocket, mengimplementasikan mesin *offline-first synchronization*, antarmuka grafik interaktif dengan *zero dropped frames*, otentikasi biometrik berbasis hardware, dan arsitektur modular berskala enterprise.

### Persyaratan Teknis & Fungsional Inti:
1. **Arsitektur & Modularisasi:**
   - Multi-modul murni berbasis Gradle Kotlin DSL (`build-logic` custom convention plugins).
   - Isolasi modul: `:app`, `:core:model`, `:core:network`, `:core:database`, `:core:designsystem`, `:core:security`, `:feature:auth`, `:feature:watchlist`, `:feature:ordertrade`, `:feature:portfolio`.
   - Pola Clean Architecture + MVI murni dengan Unidirectional Data Flow (UDF).
2. **Kinerja UI & Jetpack Compose:**
   - Custom Canvas Chart interaktif untuk visualisasi *candlestick realtime* dengan indikator Moving Average tanpa jank (stabil 60/120 FPS).
   - Zero recomposition leaks pada komponen *order book stream*.
   - Integrasi Jetpack Macrobenchmark membuktikan *Startup Time* Cold Launch di bawah 800ms menggunakan Baseline Profiles.
3. **Konkurensi & Aliran Jaringan:**
   - Ktor/OkHttp WebSocket client dengan mekanisme *auto-reconnect*, *exponential backoff*, dan buffer management via Kotlin Channels/StateFlow.
   - Circuit breaker terpasang pada order execution REST API endpoints.
4. **Data Persistence & Offline-First:**
   - Room ORM terenkripsi (SQLCipher) dengan Write-Ahead Logging (WAL).
   - Sinkronisasi mutasi order saat jaringan terputus via WorkManager (Expedited Work) dengan deteksi konflik server-side.
5. **Keamanan Finansial:**
   - Otentikasi Biometrik terintegrasi Android Keystore (kunci kriptografi privat disimpan dalam Hardware TEE/StrongBox).
   - Network Security Config dengan SSL/TLS Public Key Pinning.
   - Proteksi biner: ProGuard/R8 rules ketat, deteksi *rooted device*, dan verifikasi status *Play Integrity API*.
6. **Automasi, Testing, & CI/CD:**
   - Test Coverage: Unit Test (Use Cases, Reducers) > 85%, Compose UI Tests, dan TestContainers/MockWebServer integration.
   - Pipeline GitHub Actions otomatis menjalankan Static Analysis (detekt, ktlint, Android Lint) dan integrasi Fastlane untuk merilis App Bundle (`.aab`) secara terotomatisasi.

### Format Deliverable & Rubrik Kelulusan:
- **Source Code Repository:** Monorepo privat GitHub/GitLab terstruktur rapi.
- **Architecture Decision Record (ADR):** Dokumen teknis yang menguraikan alasan di balik pemilihan arsitektur, trade-off, dan benchmarking performa.
- **Benchmark & Profiling Report:** Laporan Systrace/Macrobenchmark sebelum dan sesudah penerapan Baseline Profiles serta grafik alokasi memori heap dump bebas kebocoran (*0 memory leaks via LeakCanary*).
- **Automated Pipeline Logs:** Bukti eksekusi CI/CD pipeline dengan status *green pass* pada seluruh suite pengetesan dan *automated build packaging*.