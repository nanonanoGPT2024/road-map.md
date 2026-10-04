```markdown
# Enterprise Flutter & Dart Engineering: Production-Grade Mobile & Cross-Platform Architecture

Selamat datang di kurikulum **Enterprise Flutter Engineering**. Silabus ini dirancang oleh Senior Technical Curriculum Architect dengan mengacu pada standar kompetensi industri dan peta jalan resmi [roadmap.sh: Flutter](https://roadmap.sh/flutter).

Kurikulum ini tidak sekadar mengajarkan pembuatan UI sederhana, melainkan membongkar mekanisme internal Flutter engine, arsitektur *clean & reactive*, manajemen state deterministik, optimasi memori dan grafis (Impeller), hingga penggelaran otomatis skala enterprise.

---

## 1. Course Overview & Mindset

### Mindset Transisi: Dari Widget Assembler ke Engine-Level Engineer
Mayoritas pengembang Flutter pemula terjebak sebagai *widget assembler*—mereka menumpuk widget pihak ketiga tanpa memahami implikasi terhadap *rebuild cost*, *pipeline rendering* (Layout, Paint, Composite), dan konsumsi memori. 

Dalam kurikulum ini, Anda akan dilatih dengan prinsip-prinsip berikut:

* **Engine-Aware Mindset:** Pahami bagaimana Dart VM berinteraksi dengan Flutter Engine (C++) melalui UI Thread, Raster Thread, Platform Thread, dan I/O Thread. Kenali transisi engine grafis dari Skia ke **Impeller**.
* **Deterministic State Flow:** Hilangkan ketergantungan pada *anti-pattern* *imperative state mutation*. Terapkan *unidirectional data flow* (UDF), immutability mutlak, dan segregasi *business logic* dari framework UI.
* **Offline-First Resilience:** Rancang aplikasi yang memperlakukan konektivitas sebagai komoditas opsional. Terapkan *local-first persistence*, sinkronisasi multi-master, dan *outbox pattern*.
* **Defensive Engineering & Zero-Regression:** Kode yang tidak memiliki tes adalah liabilitas. Kuasai piramida pengujian lengkap: Unit Testing, Widget Testing, Golden (Snapshot) Testing, hingga Integration Testing headless di lingkungan CI/CD.

---

## 2. Learning Roadmap

```plaintext
Flutter & Dart Enterprise Architecture Roadmap
│
├── [01] Core Runtime, Dart Internals & Platform Fundamentals
│    ├── 01-dart-type-system-sound-null-safety.md
│    ├── 02-flutter-engine-under-the-hood.md
│    └── 03-widget-element-renderobject-trees.md
│
├── [02] Declarative UI Engineering & Advanced Rendering
│    ├── 01-custom-layouts-and-renderobjects.md
│    ├── 02-inherited-widgets-and-buildcontext-lookup.md
│    └── 03-keys-identity-and-rebuild-optimizations.md
│
├── [03] Multi-Platform Adaptive & Responsive Architecture
│    ├── 01-adaptive-layouts-and-constraint-systems.md
│    └── 02-cross-platform-parity-desktop-web-mobile.md
│
├── [04] Deterministic Enterprise State Management
│    ├── 01-reactive-programming-and-bloc-pattern.md
│    ├── 02-riverpod-2-and-code-generation-architecture.md
│    └── 03-state-machines-and-side-effects-handling.md
│
├── [05] Asynchronous Concurrency, Network & API Layer
│    ├── 01-dart-event-loop-isolates-and-concurrency.md
│    ├── 02-dio-resilience-interceptors-and-token-rotation.md
│    └── 03-websockets-and-grpc-streaming.md
│
├── [06] Offline-First Systems & Local Persistence
│    ├── 01-drift-sqlite-reactive-persistence.md
│    ├── 02-secure-storage-and-biometric-keychains.md
│    └── 03-conflict-resolution-and-outbox-sync-engine.md
│
├── [07] Animation, Canvas, & Custom Painting Pipeline
│    ├── 01-explicit-animations-and-physics-simulations.md
│    ├── 02-custompainter-and-low-level-canvas-api.md
│    └── 03-custom-fragment-shaders-with-impeller.md
│
├── [08] Platform Interoperability: Channels & FFI
│    ├── 01-platform-channels-method-and-event-streams.md
│    ├── 02-pigeon-type-safe-ipc-generation.md
│    └── 03-dart-ffi-c-cpp-rust-binding.md
│
├── [09] Enterprise Clean Architecture & Quality Assurance
│    ├── 01-feature-first-modular-architecture.md
│    ├── 02-test-pyramid-unit-widget-golden-integration.md
│    └── 03-devtools-memory-leaks-and-frame-budget-profiling.md
│
└── [10] DevSecOps, Continuous Delivery, & Observability
     ├── 01-app-hardening-obfuscation-and-anti-tampering.md
     ├── 02-fastlane-and-github-actions-ci-cd-pipelines.md
     └── 03-crash-telemetry-and-distributed-tracing-sentry.md
```

---

## 3. Detail Navigasi Modul

### Bab 01: Core Runtime, Dart Internals & Platform Fundamentals
Membangun fondasi pemahaman mendalam tentang eksekusi kode Dart, thread pool engine, dan internal *three-tree architecture* Flutter.
* [Modul 01: Dart Type System, Sound Null Safety, & Memory Allocation](./01-core-runtime-dart-internals/01-dart-type-system-sound-null-safety.md)
  * Membedah Dart Type System: static analysis, sound null safety, tipe `Never`, `Object?`, generics variance, dynamic vs Object.
  * Alokasi memori Dart VM: Garbage Collection (Scavenger / Young Generation & Mark-Sweep / Old Generation).
* [Modul 02: Flutter Engine Architecture: Skia vs Impeller & The 4-Thread Model](./01-core-runtime-dart-internals/02-flutter-engine-under-the-hood.md)
  * Struktur C++ Flutter Engine: Platform Thread, UI Thread, Raster (GPU) Thread, dan I/O Thread.
  * Analisis mesin rendering: Mengapa Impeller menggantikan Skia (eliminasi runtime shader compilation jank / AOT shader compilation).
* [Modul 03: The Three Trees: Widget, Element, and RenderObject Demystified](./01-core-runtime-dart-internals/03-widget-element-renderobject-trees.md)
  * Siklus hidup konfigurasi: Immutability dari Widget Tree vs Mutable lifecycle pada Element Tree.
  * Peran krusial `RenderObject`: Menghitung geometri, hit testing, layout sizing, dan painting pipeline.

---

### Bab 02: Declarative UI Engineering & Advanced Rendering
Meninggalkan widget dasar untuk menguasai sistem rendering tingkat rendah, optimalisasi rebuild, dan manipulasi konteks secara langsung.
* [Modul 01: Custom Layouts and RenderObject Subclassing](./02-declarative-ui-advanced-rendering/01-custom-layouts-and-renderobjects.md)
  * Implementasi `SingleChildRenderObjectWidget` dan `MultiChildRenderObjectWidget`.
  * Algoritma `performLayout()`, constraints downward, sizes upward, dan optimalisasi *relayout boundaries*.
* [Modul 02: InheritedWidget & The Mechanics of BuildContext Lookup](./02-declarative-ui-advanced-rendering/02-inherited-widgets-and-buildcontext-lookup.md)
  * Cara kerja internal `dependOnInheritedWidgetOfExactType` vs `getElementForInheritedWidgetOfExactType`.
  * Merancang reactive data propagation kustom dengan efisiensi O(1) tanpa rebuild cascade yang tidak perlu.
* [Modul 03: Keys Identity, Element Reconciliation, & Frame Budget Optimization](./02-declarative-ui-advanced-rendering/03-keys-identity-and-rebuild-optimizations.md)
  * Analisis mendalam: Kapan menggunakan `ValueKey`, `ObjectKey`, `UniqueKey`, dan bahaya performa dari `GlobalKey`.
  * Teknik audit rebuild: Menjaga frame rate stabil di 60/120 FPS dengan target render budget < 8.33ms / 16.6ms.

---

### Bab 03: Multi-Platform Adaptive & Responsive Architecture
Membangun UI skalabel yang beradaptasi secara elegan terhadap form factor ponsel, tablet, layar lipat (*foldable*), desktop, dan web.
* [Modul 01: Adaptive Layouts, Window Size Classes, & Constraint Systems](./03-multiplatform-adaptive-responsive/01-adaptive-layouts-and-constraint-systems.md)
  * Penerapan Material 3 Window Size Classes (Compact, Medium, Expanded).
  * Menghindari jebakan `MediaQuery.of(context)` global dengan `LayoutBuilder` dan `BoxConstraints` lokal.
* [Modul 02: Cross-Platform Parity: Desktop, Web, and Mobile Nuances](./03-multiplatform-adaptive-responsive/02-cross-platform-parity-desktop-web-mobile.md)
  * Input adaptation: Pointer/mouse hover, multi-windowing, keyboard shortcuts, dan gamepad events.
  * Nuansa Web (Wasm vs CanvasKit / HTML renderer) dan isolasi dependensi platform-specific melalui conditional exports.

---

### Bab 04: Deterministic Enterprise State Management
Menguasai pola manajemen state berbasis industri untuk aplikasi kompleks dengan reliabilitas dan skalabilitas tinggi.
* [Modul 01: Reactive Streams & The Enterprise BLoC/Cubit Architecture](./04-enterprise-state-management/01-reactive-programming-and-bloc-pattern.md)
  * Arsitektur BLoC deterministik: Event-to-State transformations, buffering, transformer custom (debounce, throttle, droppable).
  * State immutability dengan Freezed/Equatable dan strategi testing BLoC secara matematis (*given, when, then*).
* [Modul 02: Riverpod 2.0: Scoped Inversion of Control & Code Generation](./04-enterprise-state-management/02-riverpod-2-and-code-generation-architecture.md)
  * Penguasaan Provider Container, compile-time safety, auto-dispose mechanics, dan family modifiers.
  * Migrasi legacy state ke `@riverpod` annotation architecture dengan integrasi async notifier.
* [Modul 03: State Machines & Global Side-Effects Handling](./04-enterprise-state-management/03-state-machines-and-side-effects-handling.md)
  * Implementasi Finite State Machines (FSM) formal untuk alur autentikasi dan *checkout flow*.
  * Manajemen efek samping terisolasi: Navigasi deklaratif (GoRouter), alert dialogs, dan toast tanpa merusak kemurnian state.

---

### Bab 05: Asynchronous Concurrency, Network & API Layer
Mengelola konkurensi skala berat, isolasi thread, dan layer komunikasi jaringan yang tangguh terhadap kegagalan.
* [Modul 01: Dart Event Loop, Microtasks, & Isolates Multi-Threading](./05-concurrency-network-api/01-dart-event-loop-isolates-and-concurrency.md)
  * Mekanisme Event Queue vs Microtask Queue dalam event loop single-threaded Dart.
  * Offloading pemrosesan CPU-heavy (enkripsi, JSON parsing masif) menggunakan `Isolate.spawn` dan `Isolate.run`.
* [Modul 02: Production Dio: Custom Interceptors, Retries, & Token Refresh Mutex](./05-concurrency-network-api/02-dio-resilience-interceptors-and-token-rotation.md)
  * Rekayasa pipeline HTTP: Implementasi interceptor untuk *bearer token auto-refresh* menggunakan lock/mutex mechanism.
  * Exponential backoff, jitter, network circuit breaker, dan SSL Pinning (Certificate & Public Key Pinning).
* [Modul 03: Real-Time Communication: WebSockets & gRPC Streaming](./05-concurrency-network-api/03-websockets-and-grpc-streaming.md)
  * Implementasi arsitektur duplex: WebSocket connection lifecycle, auto-reconnect, dan heartbeat ping-pong.
  * Penggunaan gRPC dan Protocol Buffers (protobuf) untuk komunikasi payload biner berkecepatan tinggi.

---

### Bab 06: Offline-First Systems & Local Persistence
Membangun arsitektur data lokal yang tangguh, reaktif, dan mampu beroperasi sepenuhnya tanpa koneksi internet.
* [Modul 01: Drift (SQLite) Reactive Persistence Engine](./06-offline-first-persistence/01-drift-sqlite-reactive-persistence.md)
  * Type-safe SQL querying via Drift/Moor: Relasi multi-tabel, database migrations, dan indexing strategies.
  * Mengintegrasikan data streams dari database lokal secara langsung ke layer presentasi UI.
* [Modul 02: Secure Storage, Keychains, & Biometric Hardware Binding](./06-offline-first-persistence/02-secure-storage-and-biometric-keychains.md)
  * Enkripsi data lokal at-rest: Integrasi Android Keystore dan iOS Keychain Services.
  * Alur autentikasi biometrik (Fingerprint, FaceID) dan penyimpanan aman kunci enkripsi SQLCipher.
* [Modul 03: Conflict Resolution & The Outbox Sync Pattern](./06-offline-first-persistence/03-conflict-resolution-and-outbox-sync-engine.md)
  * Perancangan transaksi offline: Implementasi Transactional Outbox Pattern untuk aksi yang tertunda.
  * Strategi resolusi konflik data: Last-Write-Wins (LWW), vector clocks, dan custom reconciliation rules.

---

### Bab 07: Animation, Canvas, & Custom Painting Pipeline
Menciptakan pengalaman pengguna tingkat tinggi dengan kontrol penuh atas piksel, animasi terkoordinasi, dan shader hardware.
* [Modul 01: Explicit Animations, Controllers, & Physics-Based Motion](./07-animation-canvas-pipeline/01-explicit-animations-and-physics-simulations.md)
  * `AnimationController`, `TickerProvider`, `CurvedAnimation`, dan `TweenSequence`.
  * Implementasi fisika interaktif: `SpringSimulation`, `FrictionSimulation`, dan koordinasi gesture terinterupsi.
* [Modul 02: CustomPainter & Low-Level Canvas Path Manipulation](./07-animation-canvas-pipeline/02-custompainter-and-low-level-canvas-api.md)
  * Menggambar primitif dan kurva Bezier: Manipulasi `Path`, `Paint`, `Canvas.drawPath`, dan clipping masks.
  * Menghindari alokasi objek baru di dalam metode `paint()` untuk mencegah garbage collection spikes.
* [Modul 03: Custom Fragment Shaders (GLSL/SLANG) with Impeller](./07-animation-canvas-pipeline/03-custom-fragment-shaders-with-impeller.md)
  * Menulis custom fragment shader (GLSL) untuk efek grafis performa tinggi (ripple, blur, chromatic aberration).
  * Binding shader inputs ke Flutter Paint pipeline di bawah engine Impeller.

---

### Bab 08: Platform Interoperability: Channels & FFI
Menembus batas cross-platform untuk mengakses API native host dan mengeksekusi kode sistem C/C++/Rust.
* [Modul 01: Platform Channels: MethodChannel, EventChannel, & BinaryMessenger](./08-platform-interop-channels-ffi/01-platform-channels-method-and-event-streams.md)
  * Mekanisme decoding/encoding `StandardMessageCodec` dan komunikasi asynchronous antar thread.
  * Streaming data native terus-menerus menggunakan `EventChannel` (sensor telemetry, baterai, network status).
* [Modul 02: Type-Safe Interop with Pigeon Code Generation](./08-platform-interop-channels-ffi/02-pigeon-type-safe-ipc-generation.md)
  * Eliminasi human error: Menggunakan generator Pigeon untuk type-safe RPC antara Dart, Kotlin, dan Swift.
  * Penanganan error struktural antar platform tanpa *runtime cast exceptions*.
* [Modul 03: Dart FFI (Foreign Function Interface): C/C++ & Rust Integration](./08-platform-interop-channels-ffi/03-dart-ffi-c-cpp-rust-binding.md)
  * Pemanggilan kode biner langsung via `dart:ffi` tanpa overhead serialisasi MethodChannel.
  * Alokasi memori manual, struct mapping, dynamic library binding, dan integrasi modul kriptografi Rust.

---

### Bab 09: Enterprise Clean Architecture & Quality Assurance
Menerapkan arsitektur enterprise yang sepenuhnya terisolasi dan dapat diuji secara menyeluruh di semua level.
* [Modul 01: Feature-First Modular Clean Architecture](./09-clean-architecture-qa/01-feature-first-modular-architecture.md)
  * Struktur domain, data, dan presentation terpisah: Entities, Value Objects, Use Cases, dan Repository interfaces.
  * Modularisasi kode menggunakan internal path dependencies (melalui Melos / Monorepo workspaces).
* [Modul 02: The Test Pyramid: Unit, Widget, Golden, & Integration Testing](./09-clean-architecture-qa/02-test-pyramid-unit-widget-golden-integration.md)
  * Unit testing mendalam: Mocking dengan `mocktail`, mock platform channels.
  * Golden Testing tingkat pixel-perfect cross-OS dan headless Integration Test menggunakan Flutter Driver / IntegrationTest package.
* [Modul 03: Performance Profiling: Dart DevTools, Memory Leaks, & Jank Analysis](./09-clean-architecture-qa/03-devtools-memory-leaks-and-frame-budget-profiling.md)
  * Analisis jejak timeline di DevTools: Mendeteksi shader jank, memory retain cycles, dan image decode overhead.
  * Menggunakan `MemoryAllocations` event listener untuk melacak memory leak pada controller yang tidak di-dispose.

---

### Bab 10: DevSecOps, Continuous Delivery, & Observability
Mengamankan aplikasi dari dekompilasi, mengotomatisasi delivery pipeline, dan memantau crash runtime secara real-time.
* [Modul 01: App Hardening, Code Obfuscation, & Anti-Tampering](./10-devsecops-cicd-observability/01-app-hardening-obfuscation-and-anti-tampering.md)
  * Obfuscation bytecode Dart (`--obfuscate --split-debug-info`), deteksi Root/Jailbreak, dan deteksi Frida/reverse engineering.
  * Penerapan Network Security Config dan proteksi runtime memory inspection.
* [Modul 02: CI/CD Pipeline Automation with Fastlane and GitHub Actions](./10-devsecops-cicd-observability/02-fastlane-and-github-actions-ci-cd-pipelines.md)
  * Konfigurasi match signing: Keystore Android & iOS Distribution Certificates via Fastlane.
  * GitHub Actions workflows untuk linting otomatis, format check, parallel testing, build artifact, dan upload ke Firebase App Distribution, TestFlight, & Play Console.
* [Modul 03: Crash Telemetry, Distributed Tracing, & Real-Time Observability](./10-devsecops-cicd-observability/03-crash-telemetry-and-distributed-tracing-sentry.md)
  * Integrasi enterprise observability menggunakan Sentry / Datadog: Breadcrumbs otomatis, custom metric, dan error grouping.
  * Simbolikasi de-obfuscation stack traces menggunakan upload mapping file otomatis pada saat deployment.

---

## 4. Enterprise Capstone Project: "AegisPay Terminal & Vault"

### Overview Proyek
Sebagai puncak kurikulum, Anda akan membangun **AegisPay Terminal & Vault**: sebuah aplikasi *Point-of-Sale (POS) & Crypto-Fiat Hybrid Custody Engine* multi-platform enterprise yang siap dideploy ke produksi. Sistem ini dirancang untuk beroperasi di lingkungan konektivitas rendah (*low-connectivity*), memiliki standard kepatuhan keamanan data tinggi, dan menuntut performa render 120 FPS tanpa kompromi.

### Persyaratan Arsitektural & Fungsional
1. **Arsitektur Inti (Clean Architecture & Monorepo):**
   * Menggunakan struktur Monorepo (Melos) dengan paket terpisah: `core_ui`, `network_engine`, `persistence_vault`, `crypto_security`, dan feature modules (`payment`, `analytics`, `vault`).
   * Manajemen state menggunakan **BLoC** (Core Financial Transactions) dipadukan dengan **Riverpod** (Dependency Injection & Lightweight UI State).

2. **Offline-First Synchronization Engine:**
   * Local storage berbasis **Drift (Cipher-encrypted SQLite)**.
   * Transaksi pembayaran disimpan ke dalam *Transactional Outbox Table* jika offline.
   * Sync engine otomatis berjalan di background thread (**Isolate**) dengan resolusi konflik deterministik berbasis Cryptographic Nonces saat koneksi pulih.

3. **Hardware Interoperability (Channels & FFI):**
   * Menggunakan **Pigeon** untuk komunikasi dengan EMV Card Reader native (Android/iOS).
   * Modul verifikasi tanda tangan kriptografi (secp256k1) diintegrasikan langsung via **Dart FFI** menggunakan library compiled Rust (`libcrypto_aegis.so` / `libcrypto_aegis.dylib`).

4. **Kustom Rendering & Visualisasi Interaktif:**
   * Dasbor visualisasi grafik transaksi finansial *real-time* yang digambar dari nol menggunakan `CustomPainter` dan modul **Custom Fragment Shaders** untuk rendering efek fluid visual pada saat tap-to-pay berhasil.
   * Framerate stabil pada 60/120 FPS tanpa frame drop pada layar ProMotion/High Refresh Rate.

5. **Keamanan & Hardening Ketat:**
   * Dynamic SSL Pinning dengan Certificate Transparency validation.
   * Root / Jailbreak check dan integrity verification saat runtime.
   * Code obfuscation diaktifkan untuk semua production builds.

6. **Kualitas & Otomatisasi (CI/CD):**
   * Code coverage minimum **85%** mencakup Unit, Widget, dan Golden Tests.
   * Headless E2E Integration test yang memvalidasi *checkout-to-sync lifecycle*.
   * Pipeline **GitHub Actions + Fastlane** lengkap: Mulai dari push pull request hingga distribusi otomatis ke TestFlight dan Google Play Internal App Sharing.

---

## Standar Kode & Kontribusi
Semua modul dalam kurikulum ini wajib tunduk pada *linter rules* ketat (`flutter_lints` enterprise edition). Kode harus bebas dari peringatan linter (`zero-warning policy`) dan mengikuti paradigma functional-declarative yang aman, modern, dan scalable.
```