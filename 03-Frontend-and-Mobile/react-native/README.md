# Silabus Kurikulum Enterprise: React Native Architecture & Engineering

> Dokumen ini merupakan silabus teknis komprehensif untuk penguasaan platform React Native modern (New Architecture: Fabric, TurboModules, JSI, dan Hermes). Kurikulum dirancang untuk mentransformasi Frontend/Mobile Engineer menjadi Mobile Systems Architect yang mampu membangun aplikasi lintas platform berskala jutaan pengguna dengan performa setara native (*60/120 FPS*).

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
React Native bukan sekadar "menulis React di atas ponsel". Paradigma ini menuntut pemahaman mendalam tentang dua *runtime* yang berjalan paralel: JavaScript Runtime (Hermes) dan Native Host Platform (Android Virtual Machine/ART dan iOS Darwin/Objective-C/Swift Runtime). Kegagalan memahami batas konkurensi, thread scheduling, dan marshaling data antar-runtime adalah akar dari 90% masalah performa dan stabilitas aplikasi skala enterprise.

Kurikulum ini mengadopsi standar **New Architecture (Bridgeless + Fabric + TurboModules)** sebagai fondasi utama, bukan lagi arsitektur bridge legacy JSON asynchronous. Anda dituntut untuk berpikir dalam struktur C++ JSI (*JavaScript Scripting Interface*), eksekusi layout thread-safe Yoga, memori deterministik, serta pola reaktif event-driven.

```
       [ JavaScript Context (Hermes) ]
                     │
         Direct Memory Access (JSI)
                     │
    ┌────────────────┴────────────────┐
    ▼                                 ▼
[ Fabric C++ Core ]          [ TurboModules C++ Core ]
    │                                 │
    ├─ Concurrent Yoga Layout         ├─ Native Host Platform
    ├─ Thread-Safe Immutability       │  (iOS/macOS via Swift/ObjC)
    └─ Surface Mounting               └─ (Android via Kotlin/Java)
```

### Mental Model Inti
1. **Zero-Bridge Latency Mindset:** Memahami bahwa komunikasi JS-ke-Native melalui JSI bersifat sinkron dan berbagi memori (*shared memory reference*), mengeliminasi overhead serialisasi JSON namun memperkenalkan risiko race condition jika mutasi thread tidak dikontrol.
2. **Deterministic UI Scheduling:** Memisahkan beban kerja JS Thread (event loop React) dari Native Main Thread (render UI, gestur) agar interaksi tetap konsisten pada 120 FPS tanpa frame drop (*jank*).
3. **Offline-First & Eventual Consistency:** Menganggap konektivitas jaringan selalu tidak stabil (*unreliable*). Arsitektur aplikasi harus mampu melakukan pembacaan dan penulisan lokal terlebih dahulu (Zero-blocking storage engine), lalu menyinkronkannya melalui pipeline rekonsiliasi yang idempoten.
4. **Platform Parity vs Platform Idiom:** Menyeimbangkan abstraksi kode universal lintas platform dengan integrasi idiomatis spesifik (Human Interface Guidelines untuk iOS dan Material 3 untuk Android).

### Prasyarat Teknis
* Pemahaman mendalam JavaScript ESNext, Event Loop, Memory Allocation, dan TypeScript level *Advanced* (Conditional Types, Template Literal Types, Generic Constraints).
* Penguasaan fundamental React (Reconciliation, Hooks internals, Fiber Architecture, Concurrent Mode).
* Pemahaman dasar sistem operasi: Threading, Process, Memory Layout (Heap/Stack), Garbage Collection, serta dasar sintaks C++/Kotlin/Swift untuk membaca bridge native.
* Terinstalasi di mesin lokal: Node.js LTS, JDK 17, Android Studio (SDK, NDK, CMake), Xcode (khusus macOS untuk build target iOS), CocoaPods, dan Watchman.

### Script Verifikasi Environment
Jalankan script diagnosa berikut pada shell Unix untuk memvalidasi kesiapan toolchain lokal Anda:

```bash
#!/usr/bin/env bash
set -eo pipefail

echo "=== MEMERIKSA DEPENDENSI KURSUS REACT NATIVE ==="

command -v node >/dev/null 2>&1 && echo "[OK] Node.js: $(node -v)" || { echo "[FAIL] Node.js tidak ditemukan."; exit 1; }
command -v npm >/dev/null 2>&1 && echo "[OK] npm: $(npm -v)" || { echo "[FAIL] npm tidak ditemukan."; exit 1; }
command -v watchman >/dev/null 2>&1 && echo "[OK] Watchman: $(watchman -v)" || echo "[WARN] Watchman tidak ditemukan (direkomendasikan)."
command -v javac >/dev/null 2>&1 && echo "[OK] JDK: $(javac -version 2>&1)" || { echo "[FAIL] JDK tidak ditemukan."; exit 1; }

if [ -n "$ANDROID_HOME" ]; then
  echo "[OK] ANDROID_HOME terkonfigurasi: $ANDROID_HOME"
else
  echo "[FAIL] ANDROID_HOME belum diset pada environment variables."; exit 1;
fi

if [[ "$OSTYPE" == "darwin"* ]]; then
  command -v xcodebuild >/dev/null 2>&1 && echo "[OK] Xcode: $(xcodebuild -version | head -n 1)" || echo "[WARN] Xcode CLI tidak ditemukan."
  command -v pod >/dev/null 2>&1 && echo "[OK] CocoaPods: $(pod --version)" || echo "[WARN] CocoaPods tidak terinstalasi."
fi

echo "=== VERIFIKASI SISTEM SELESAI ==="
```

---

## 2. Learning Roadmap

```
React Native Architecture & Engineering
|
+-- Bab 01: Core Architecture & Foundations
|   |-- Modul 01: The New Architecture Internals: Fabric, TurboModules & JSI
|   |-- Modul 02: Hermes Bytecode Engine & Memory Management
|   \-- Modul 03: Yoga Layout Engine & Bridged-to-Bridgeless Migration
|
+-- Bab 02: Declarative UI, Component Lifecycle & Styling Systems
|   |-- Modul 01: Component Primitives & React 18+ Reconciliation
|   |-- Modul 02: High-Performance Layouts: Flexbox Deep Dive & Pixel Density
|   \-- Modul 03: Enterprise Styling Architecture: Unistyles vs NativeWind
|
+-- Bab 03: State Management & Local Data Persistence
|   |-- Modul 01: Atomic vs Centralized State: Zustand & XState
|   |-- Modul 02: Server-State Synchronization with TanStack Query
|   \-- Modul 03: Ultra-Fast Storage: MMKV, SQLite & WatermelonDB
|
+-- Bab 04: Navigation & Deep Linking Architecture
|   |-- Modul 01: Stack, Tab & Drawer Mechanics via React Navigation
|   |-- Modul 02: File-Based Routing with Expo Router
|   \-- Modul 03: Universal Links, Deep Linking & Navigation State Restoration
|
+-- Bab 05: Native Device Features & Sensor Integration
|   |-- Modul 01: Camera Subsystems & Frame Processors (VisionCamera)
|   |-- Modul 02: Background Geolocation, Geofencing & WorkManager/BGTask
|   \-- Modul 03: Hardware Biometrics, Secure Enclave & Keystore
|
+-- Bab 06: High-Performance Animations & Gestures
|   |-- Modul 01: Declarative Gesture Processing (React Native Gesture Handler)
|   |-- Modul 02: 120 FPS Fluid Animations with Reanimated 3
|   \-- Modul 03: Hardware-Accelerated 2D Graphics with React Native Skia
|
+-- Bab 07: Native Modules & Bridge/JSI Custom Extensions
|   |-- Modul 01: Codegen Specification & Type-Safe Native Contracts
|   |-- Modul 02: Writing Custom TurboModules (Swift & Kotlin)
|   \-- Modul 03: Direct C++ JSI Bindings for High-Throughput Compute
|
+-- Bab 08: Network Resiliency, Offline-First Architecture & Security
|   |-- Modul 01: Network Layer Resiliency: Circuit Breaker & Offline Mutex
|   |-- Modul 02: Mobile App Hardening: Certificate Pinning & Root/Jailbreak Detection
|   \-- Modul 03: Data at Rest Encryption & Memory Dump Prevention
|
+-- Bab 09: Profiling, Memory Leaks & Performance Optimization
|   |-- Modul 01: Profiling via Hermes Memory Inspector & React DevTools
|   |-- Modul 02: Virtualized Lists Mastery: FlatList vs FlashList V2
|   \-- Modul 03: Mitigating Thread Starvation, Layout Thrashing & Overdraw
|
\-- Bab 10: CI/CD, Automated Testing & App Store Deployment
    |-- Modul 01: Testing Pyramid: Jest, RNTL & E2E Automation via Maestro
    |-- Modul 02: Production Build Pipeline: Fastlane, EAS & Code Signing
    \-- Modul 03: Deterministic Over-The-Air (OTA) Updates & Rollback Strategies
```

---

## 3. Navigasi Detail Modul Silabus

### [Bab 01: Core Architecture & Foundations](./bab-01-core-architecture-and-foundations/README.md)
*Fokus Produksi:* Membedah arsitektur internal platform untuk mengidentifikasi bottleneck eksekusi kode dan memahami perbedaan mendasar runtime engine.
* **[Modul 01: The New Architecture Internals: Fabric, TurboModules & JSI](./bab-01-core-architecture-and-foundations/01-new-architecture-internals.md)**
  * Mekanisme JavaScript Interface (JSI) menghapus *asynchronous batched bridge*.
  * Struktur C++ Core Fabric Renderer, Shadow Tree, dan Mounting phase.
  * TurboModules: Lazy-loading native modules berbasis on-demand binding.
  * *Tugas Hands-on:* Buat demonstrasi profiler sederhana yang mengukur waktu serialisasi bridge legacy vs transfer data langsung via JSI pointer.
  * *Failure Mode:* Memory leak akibat retain cycle referensi pointer C++ JSI pada runtime Hermes.
* **[Modul 02: Hermes Bytecode Engine & Memory Management](./bab-01-core-architecture-and-foundations/02-hermes-bytecode-engine.md)**
  * AOT (Ahead-of-Time) compilation: Kompilasi JavaScript menjadi bytecode `.hbc`.
  * Hermes Garbage Collection (Hades): Generational, Concurrent, multi-threaded GC.
  * Analisis TTI (Time to Interactive) dan jejak footprint RAM.
  * *Tugas Hands-on:* Ekstraksi dan analisa bundle `.hbc` menggunakan `hermes-engine` CLI untuk memetakan alokasi heap.
  * *Failure Mode:* Crash aplikasi akibat alokasi array berskala masif yang memicu OOM (*Out Of Memory*) pada low-end Android hardware.
* **[Modul 03: Yoga Layout Engine & Bridged-to-Bridgeless Migration](./bab-01-core-architecture-and-foundations/03-yoga-engine-and-bridgeless.md)**
  * Yoga C++ layout recalculation: Flexbox mapping ke Native Layout params.
  * Mode Bridgeless: Menghilangkan `BridgeJSExecutor` sepenuhnya.
  * Strategi migrasi aplikasi enterprise legacy ke New Architecture.
  * *Tugas Hands-on:* Mengaktifkan mode New Architecture secara manual pada template murni tanpa dependensi automasi eksternal.
  * *Failure Mode:* Deadlock antar-thread saat library legacy pihak ketiga mencoba mengirimkan callback asynchronous via bridge yang sudah dinonaktifkan.

---

### [Bab 02: Declarative UI, Component Lifecycle & Styling Systems](./bab-02-ui-lifecycle-styling/README.md)
*Fokus Produksi:* Membangun sistem antarmuka berskala enterprise yang konsisten, deterministik, adaptif terhadap fragmentasi perangkat, dan bebas layout-thrashing.
* **[Modul 01: Component Primitives & React 18+ Reconciliation](./bab-02-ui-lifecycle-styling/01-primitives-and-reconciliation.md)**
  * Primitif inti: `<View>`, `<Text>`, `<Pressable>` vs element platform native.
  * Concurrent React di React Native: `useTransition` dan `useDeferredValue` untuk mencegah freeze pada frame render UI.
  * Subtree mounting dan rerender mitigation via custom memoization semantics.
  * *Tugas Hands-on:* Mengimplementasikan antarmuka pencarian multi-filter real-time tanpa menurunkan frame-rate UI menggunakan React 18 concurrent primitives.
  * *Failure Mode:* Unmounted component state update memory leak yang memicu app silent error.
* **[Modul 02: High-Performance Layouts: Flexbox Deep Dive & Pixel Density](./bab-02-ui-lifecycle-styling/02-flexbox-and-pixel-density.md)**
  * Implementasi Flexbox pada Yoga: Perbedaan kalkulasi web vs native platform.
  * Dynamic Pixel Ratio calculation (`PixelDensity`, points vs hardware pixels).
  * Penanganan Notch, Dynamic Island, Safe Area, dan Keyboard avoidance native-driven.
  * *Tugas Hands-on:* Membangun adaptive responsive canvas yang mempertahankan rasio visual identik pada resolusi ldpi, xxhdpi, hingga Retina display.
  * *Failure Mode:* Sub-pixel rendering bug yang memicu garis patah (*border clipping*) pada perangkat Android dengan scaling density ganjil.
* **[Modul 03: Enterprise Styling Architecture: Unistyles vs NativeWind](./bab-02-ui-lifecycle-styling/03-enterprise-styling-architecture.md)**
  * Evaluasi kinerja StyleSheet bawaan vs Atomic CSS compile-time (NativeWind v4).
  * Unistyles: Arsitektur styling level C++ tanpa overhead runtime theme-provider.
  * Dynamic theming (Dark/Light mode, multi-tenant branding) tanpa full-tree re-render.
  * *Tugas Hands-on:* Refaktor arsitektur theming berbasis context runtime menjadi zero-runtime dynamic stylesheets menggunakan Unistyles.
  * *Failure Mode:* Theme-switching frame drop masif akibat ratusan komponen mengeksekusi re-render secara sinkron di JS thread.

---

### [Bab 03: State Management & Local Data Persistence](./bab-03-state-and-persistence/README.md)
*Fokus Produksi:* Mengelola state berskala besar, meminimalisir overhead thread JS, dan menyimpan data secara aman dengan performa I/O tinggi.
* **[Modul 01: Atomic vs Centralized State: Zustand & XState](./bab-03-state-and-persistence/01-atomic-vs-centralized-state.md)**
  * Zustand selectors untuk isolasi rerender pada critical rendering path.
  * State Machine via XState untuk alur checkout/autentikasi yang deterministik.
  * Pola mutasi state tanpa mencederai prinsip immutability.
  * *Tugas Hands-on:* Desain State Machine autentikasi kompleks dengan token refresh otomatis dan penanganan sesi kedaluwarsa.
  * *Failure Mode:* Cascade rerenders yang membekukan interaksi UI akibat penggunaan selector non-deterministik pada global state.
* **[Modul 02: Server-State Synchronization with TanStack Query](./bab-03-state-and-persistence/02-server-state-synchronization.md)**
  * Optimistic UI updates, automated re-fetching, dan garbage collection cache.
  * Prefetching data pada background thread sebelum transisi layar.
  * Penanganan status konektivitas offline-to-online reconciliation pipeline.
  * *Tugas Hands-on:* Implementasi timeline feed interaktif dengan infinite loading dan optimistic liking/commenting.
  * *Failure Mode:* Inkonsistensi data lokal akibat race condition respons jaringan yang datang tidak berurutan (*out-of-order execution*).
* **[Modul 03: Ultra-Fast Storage: MMKV, SQLite & WatermelonDB](./bab-03-state-and-persistence/03-ultra-fast-persistence.md)**
  * Keterbatasan `AsyncStorage` dan keunggulan MMKV (memory-mapped file I/O).
  * SQLite relational storage via raw C++ bindings.
  * WatermelonDB: Database reaktif berorientasi offline-first dengan lazy loading records.
  * *Tugas Hands-on:* Benchmark performa baca/tulis 50.000 record data antara AsyncStorage, MMKV, dan SQLite.
  * *Failure Mode:* UI freezing parah akibat blocking bridge saat membaca payload JSON besar secara sinkron dari legacy storage.

---

### [Bab 04: Navigation & Deep Linking Architecture](./bab-04-navigation-and-deep-linking/README.md)
*Fokus Produksi:* Mendesain arsitektur navigasi multi-stack yang terisolasi secara memori, deep linking multi-platform, dan pemulihan state navigasi.
* **[Modul 01: Stack, Tab & Drawer Mechanics via React Navigation](./bab-04-navigation-and-deep-linking/01-react-navigation-internals.md)**
  * Arsitektur native view stack melalui `react-native-screens`.
  * Optimasi konsumsi memori pada deep hierarchical stacks (screen freezing).
  * Tab View dan custom tab-bar transitions level UI-thread.
  * *Tugas Hands-on:* Bangun arsitektur multi-stack dengan screen disposal memory-saving pada navigation stack dengan kedalaman > 10 layer.
  * *Failure Mode:* Memory exhaustion (OOM) akibat kegagalan destruksi komponen layar yang tertumpuk di background stack.
* **[Modul 02: File-Based Routing with Expo Router](./bab-04-navigation-and-deep-linking/02-file-based-routing.md)**
  * Konsep dan filosofi file-system based routing pada aplikasi mobile.
  * Nested routes, layout groups `(group)`, dan protected routes.
  * Static rendering dan dynamic segment handling.
  * *Tugas Hands-on:* Arsitektur ulang rute navigasi modular enterprise ke struktur Expo Router v3.
  * *Failure Mode:* Unmatched route fallback loops saat aplikasi menerima routing parameters bertipe data invalid.
* **[Modul 03: Universal Links, Deep Linking & Navigation State Restoration](./bab-04-navigation-and-deep-linking/03-deep-linking-and-restoration.md)**
  * Apple Universal Links (`apple-app-site-association`) & Android App Links (`assetlinks.json`).
  * Deserialisasi link eksternal ke internal router context.
  * Navigation state persistence dan restoration pasca OS-initiated process death.
  * *Tugas Hands-on:* Konfigurasi end-to-end deep link handling yang mengarahkan user langsung ke spesifik modal sub-order flow.
  * *Failure Mode:* Kehilangan navigasi state dan crash aplikasi saat menerima cold-start deep link dengan token auth yang kadaluarsa.

---

### [Bab 05: Native Device Features & Sensor Integration](./bab-05-native-device-features/README.md)
*Fokus Produksi:* Berinteraksi langsung dengan subsistem perangkat keras seluler (kamera, background services, sensor) secara aman dan efisien.
* **[Modul 01: Camera Subsystems & Frame Processors (VisionCamera)](./bab-05-native-device-features/01-vision-camera-frame-processors.md)**
  * Arsitektur VisionCamera v4 dan integrasi C++ Worklets.
  * Real-time machine learning frame processing (OCR / QR Scanning) pada GPU/NPU native thread.
  * Sinkronisasi orientation handling, flash, focus, dan exposure controls.
  * *Tugas Hands-on:* Buat plugin scanner barcode/QR berbasis frame-processor native yang memproses feed kamera tanpa frame delay di JS runtime.
  * *Failure Mode:* Thermal throttling dan battery drain agresif akibat memproses frame kamera resolusi tinggi langsung di JS Thread.
* **[Modul 02: Background Geolocation, Geofencing & WorkManager/BGTask](./bab-05-native-device-features/02-background-geolocation-and-tasks.md)**
  * Perbedaan siklus hidup background Android (WorkManager/Foreground Service) vs iOS (`BGAppRefreshTask`).
  * Pelacakan lokasi presisi tinggi dengan baterai adaptif (*significant motion changes*).
  * Geofencing logic dan broadcast receivers.
  * *Tugas Hands-on:* Bangun modul background telemetry yang mengirimkan koordinat GPS secara periodik ketika aplikasi dalam kondisi killed/background.
  * *Failure Mode:* Sistem Operasi Android/iOS mematikan background service secara sepihak (*OS Kill*) karena penggunaan memori atau baterai yang melampaui batas kuota platform.
* **[Modul 03: Hardware Biometrics, Secure Enclave & Keystore](./bab-05-native-device-features/03-biometrics-and-secure-storage.md)**
  * Integrasi FaceID, TouchID, dan Android BiometricPrompt API.
  * Akses iOS Keychain Services dan Android TEE (Trusted Execution Environment) / Keystore.
  * Kriptografi public/private key generation di level hardware.
  * *Tugas Hands-on:* Implementasi flow otentikasi biometrik non-repudiation menggunakan cryptographic signature generation.
  * *Failure Mode:* Rentan terhadap bypass biometrik level perangkat apabila engineer hanya mengandalkan boolean result dari library tanpa validasi cryptographic challenge-response dari backend.

---

### [Bab 06: High-Performance Animations & Gestures](./bab-06-animations-and-gestures/README.md)
*Fokus Produksi:* Menciptakan pengalaman interaktif mikro 120 FPS menggunakan direct UI-thread manipulation tanpa mengorbankan responsiveness JS.
* **[Modul 01: Declarative Gesture Processing (React Native Gesture Handler)](./bab-06-animations-and-gestures/01-gesture-handler-internals.md)**
  * Integrasi RNGH v2: Gesture interaction composition (Simultaneous, Exclusive, Race).
  * Arsitektur Native Pan, Pinch, Tap, dan LongPress gesture recognizers.
  * Menghindari ambiguitas gesture scrollview horizontal vs vertical.
  * *Tugas Hands-on:* Bangun komponen Bottom Sheet swipeable native-like dengan multi-point snap locking.
  * *Failure Mode:* Gesture hijacking oleh parent ScrollView akibat penanganan conflict event responder yang tidak terdefinisi dengan benar.
* **[Modul 02: 120 FPS Fluid Animations with Reanimated 3](./bab-06-animations-and-gestures/02-reanimated-3-worklets.md)**
  * Konsep Reanimated Worklets: Fungsi JS yang dieksekusi di context UI-Thread.
  * `useSharedValue`, `useAnimatedStyle`, `withSpring`, dan `withTiming` mechanics.
  * Shared Element Transitions lintas navigasi layar.
  * *Tugas Hands-on:* Desain interaksi swipe-to-delete card kompleks dengan physics-based springs dan layout reorganization real-time.
  * *Failure Mode:* Eksekusi method asynchronous atau pemanggilan UI-blocking functions di dalam worklet yang mengakibatkan render thread crash.
* **[Modul 03: Hardware-Accelerated 2D Graphics with React Native Skia](./bab-06-animations-and-gestures/03-react-native-skia-graphics.md)**
  * Google Skia Engine binding pada React Native.
  * Path manipulation, shader effects (GLSL), gradients, dan rendering matrix.
  * Desain dynamic real-time data visualizer (financial charts, waveform audio).
  * *Tugas Hands-on:* Buat visualisasi grafik interaktif financial candlestick charting dengan pinch-to-zoom real-time rendering.
  * *Failure Mode:* GPU overdraw dan memory consumption spiking akibat redrawing full-canvas tanpa bounding box invalidation.

---

### [Bab 07: Native Modules & Bridge/JSI Custom Extensions](./bab-07-native-modules-and-jsi/README.md)
*Fokus Produksi:* Menembus batasan React Native dengan menulis custom extension langsung menggunakan Kotlin, Swift, dan C++ via modern Codegen.
* **[Modul 01: Codegen Specification & Type-Safe Native Contracts](./bab-07-native-modules-and-jsi/01-codegen-and-typed-contracts.md)**
  * TypeScript/Flow specification parsing untuk Codegen.
  * Auto-generation boilerplate C++ bindings, JNI wrappers, dan ObjC protocols.
  * Strict typing lintas batas platform (*cross-language type safety*).
  * *Tugas Hands-on:* Definisikan spesifikasi Codegen untuk modul enkripsi custom dan verifikasi file generate C++ pada direktori build Android/iOS.
  * *Failure Mode:* Build error C++ compiler yang ambigu akibat inkonsistensi penamaan interface atau tipe data nullable yang tidak didukung pada skema Codegen.
* **[Modul 02: Writing Custom TurboModules (Swift & Kotlin)](./bab-07-native-modules-and-jsi/02-turbomodules-swift-kotlin.md)**
  * Penulisan TurboModule platform Android menggunakan Modern Kotlin.
  * Penulisan TurboModule platform iOS menggunakan Modern Swift via Objective-C++ bridging header.
  * Concurrency execution via Kotlin Coroutines dan Swift Concurrency (async/await).
  * *Tugas Hands-on:* Bangun custom TurboModule untuk mengambil telemetry low-level baterai (suhu, voltase, resistansi internal) secara instan.
  * *Failure Mode:* Main UI thread lock pada Android akibat memanggil proses IO sinkron di dalam method native module tanpa context switching ke `Dispatchers.IO`.
* **[Modul 03: Direct C++ JSI Bindings for High-Throughput Compute](./bab-07-native-modules-and-jsi/03-direct-cpp-jsi-bindings.md)**
  * JSI Runtime internals: `jsi::Value`, `jsi::Object`, `jsi::Function`, dan `jsi::HostObject`.
  * Komputasi matriks matematis berkecepatan tinggi tanpa overhead marshalling.
  * Instalasi global JSI pointers pada JavaScript Global Object.
  * *Tugas Hands-on:* Implementasikan algoritma Fast Fourier Transform (FFT) atau Image Filter matrix calculation murni menggunakan C++ via JSI.
  * *Failure Mode:* Hard segmentation fault (`SIGSEGV`) yang langsung mematikan aplikasi seketika akibat *dangling pointer* atau memory misallocation di layer C++.

---

### [Bab 08: Network Resiliency, Offline-First Architecture & Security](./bab-08-network-offline-and-security/README.md)
*Fokus Produksi:* Menjamin integritas data dan keamanan aplikasi mobile pada lingkungan jaringan yang rentan terhadap mitigasi *man-in-the-middle* dan tampering.
* **[Modul 01: Network Layer Resiliency: Circuit Breaker & Offline Mutex](./bab-08-network-offline-and-security/01-network-resiliency-and-offline-queue.md)**
  * Interceptors pada Axios/Ky: Retry mechanism dengan Exponential Backoff + Jitter.
  * Arsitektur antrian mutasi offline (*Offline Mutation Queue*) dengan SQLite synchronization lock.
  * Konflik resolusi data (Last-Write-Wins vs Vector Clocks).
  * *Tugas Hands-on:* Rancang pipeline mutasi transaksi offline yang secara otomatis mengantrekan aksi user dan melakukan replay ketika jaringan pulih.
  * *Failure Mode:* Duplicate transactions di database backend akibat submission retry yang tidak memiliki idempoten token (*Idempotency Key*).
* **[Modul 02: Mobile App Hardening: Certificate Pinning & Root/Jailbreak Detection](./bab-08-network-offline-and-security/02-certificate-pinning-and-tampering.md)**
  * Public Key Pinning (HPKP alternative) via `react-native-ssl-pinning` atau native networking client.
  * Mitigasi proxy inspection (Burp Suite, Charles Proxy, Proxyman).
  * Deteksi Jailbreak/Root, Magisk, emulator detection, dan integrity attestation (Play Integrity API / App Attest).
  * *Tugas Hands-on:* Pasang dynamic public key pinning berbasis SHA-256 hash dan integrasikan audit device integrity yang menutup aplikasi jika environment terinfeksi hook Frida.
  * *Failure Mode:* Aplikasi *brick* total bagi seluruh user saat sertifikat backend kadaluarsa tanpa adanya strategi rotation pin yang disiapkan di aplikasi.
* **[Modul 03: Data at Rest Encryption & Memory Dump Prevention](./bab-08-network-offline-and-security/03-data-encryption-and-memory-protection.md)**
  * Enkripsi database SQLite menggunakan SQLCipher (AES-256).
  * Obfuscation konfigurasi runtime via dynamic key derivation.
  * Sanitasi memori: Mencegah *sensitive data leaks* pada iOS Snapshot Caching dan Android Task Switcher screen previews.
  * *Tugas Hands-on:* Terapkan screen shielding (Privacy Blurring) ketika aplikasi masuk status AppState `background` serta enkripsi penuh storage MMKV menggunakan AES.
  * *Failure Mode:* Kebocoran data sensitif (PII, nomor kartu kredit) melalui Android Logcat atau OS level app screenshot previews.

---

### [Bab 09: Profiling, Memory Leaks & Performance Optimization](./bab-09-profiling-and-performance/README.md)
*Fokus Produksi:* Menganalisis jejak memori secara empiris, melacak sumber degradasi performa, dan memastikan stabilitas frame time 120 FPS.
* **[Modul 01: Profiling via Hermes Memory Inspector & React DevTools](./bab-09-profiling-and-performance/01-hermes-profiler-and-devtools.md)**
  * Menganalisis CPU sampling profile dengan Chrome DevTools dan Hermes DevTools.
  * Membaca heap snapshots dan tracking retainers untuk mengidentifikasi unreleased memory.
  * Deteksi rendering bottlenecks menggunakan React Profiler (Commit phase vs Render phase).
  * *Tugas Hands-on:* Rekam sesi interaksi bermasalah menggunakan Hermes profiler, lalu diagnosis dan selesaikan fungsi JS yang memblokir thread lebih dari 16.6ms.
  * *Failure Mode:* Salah membaca profiling sampling yang mengarah pada over-optimasi kode yang sebenarnya bukan bottleneck arsitektural.
* **[Modul 02: Virtualized Lists Mastery: FlatList vs FlashList V2](./bab-09-profiling-and-performance/02-virtualized-lists-mastery.md)**
  * Anatomi virtualisasi: Windowing, initialNumToRender, maxToRenderPerBatch, dan windowSize.
  * Mengapa FlatList boros memori: Pembuatan dan penghancuran native view yang berlebihan.
  * Shopify FlashList V2: Konsep cell recycling berbasis recycling engine internal.
  * *Tugas Hands-on:* Konversi FlatList performa rendah berisi ribuan item kompleks menjadi FlashList dengan maintain stabilitas 60 FPS saat fling scrolling cepat.
  * *Failure Mode:* Blank cell flickering saat user melakukan fast scroll akibat estimasi `estimatedItemSize` yang salah secara drastis.
* **[Modul 03: Mitigating Thread Starvation, Layout Thrashing & Overdraw](./bab-09-profiling-and-performance/03-thread-starvation-and-overdraw.md)**
  * Menyelidiki UI vs JS thread starvation menggunakan Systrace / Perfetto / Xcode Instruments.
  * Mengurangi overdraw rendering via Android "Show GPU Overdraw" inspector.
  * Inline function dan anonymous closures allocations audit.
  * *Tugas Hands-on:* Reduksi level render overdraw dari True Red (4x overdraw) menjadi Blue/Green (1x overdraw) pada hierarki layout bertumpuk.
  * *Failure Mode:* Micro-stuttering yang persisten saat scrolling karena layout recalculation berulang pada native Yoga layer (*Layout Thrashing*).

---

### [Bab 10: CI/CD, Automated Testing & App Store Deployment](./bab-10-testing-cicd-and-deployment/README.md)
*Fokus Produksi:* Mengotomatisasi jalur perakitan aplikasi (build pipeline), pengujian otomatis komprehensif, rilis multi-channel, dan pembaruan OTA.
* **[Modul 01: Testing Pyramid: Jest, RNTL & E2E Automation via Maestro](./bab-10-testing-cicd-and-deployment/01-testing-pyramid-and-maestro.md)**
  * Unit testing murni logic & state menggunakan Jest.
  * Integration testing UI menggunakan React Native Testing Library (RNTL) dengan user-centric queries.
  * E2E UI Automation testing modern menggunakan Maestro (eliminasi flakiness Appium/Detox).
  * *Tugas Hands-on:* Buat test suite lengkap mencakup unit test auth store, integration test login form, dan Maestro E2E flow untuk end-to-end checkout.
  * *Failure Mode:* Flaky E2E tests akibat penggunaan hardcoded sleep ketimbang dynamic element assertion.
* **[Modul 02: Production Build Pipeline: Fastlane, EAS & Code Signing](./bab-10-testing-cicd-and-deployment/02-fastlane-eas-and-code-signing.md)**
  * Manajemen Keystore Android (JKS) dan Apple Signing Identifiers, Profiles, & Certificates.
  * Automasi build native menggunakan Fastlane (Gym, Match, Pilot, Supply).
  * EAS (Expo Application Services) Build cloud configuration untuk bare dan managed workflow.
  * *Tugas Hands-on:* Tulis script Fastlane lanes yang mengotomatisasi bump build number, compile native binary, sign APK/AAB dan IPA, lalu submit ke TestFlight dan Google Play Internal Sharing.
  * *Failure Mode:* Kegagalan deployment rilis akibat invalid Provisioning Profile signature mismatch antara CI server dan Apple Developer Portal.
* **[Modul 03: Deterministic Over-The-Air (OTA) Updates & Rollback Strategies](./bab-10-testing-cicd-and-deployment/03-ota-updates-and-rollbacks.md)**
  * Arsitektur OTA Runtime (EAS Update): Bagaimana binary native me-load dynamic JS bundles.
  * Versioning constraints: Kompatibilitas `runtimeVersion` dengan native libraries runtime dependencies.
  * Automated canary releases dan instant rollback pipeline ketika Sentry mendeteksi surge crash rate.
  * *Tugas Hands-on:* Setup pipeline OTA updates yang memvalidasi fingerprint native sebelum menyajikan bundle baru kepada target klien secara berjenjang.
  * *Failure Mode:* App crash loop seketika pada end-user akibat merilis OTA update yang membutuhkan native dependencies baru yang belum terkompilasi pada base binary native.

---

## 4. Enterprise Capstone Project: OmniChannel Logistics & Field Fleet Management Suite

### Deskripsi Sistem
Pada akhir program, peserta akan membangun sistem mobile enterprise berskala nyata: **"OmniRoute Enterprise"**, sebuah aplikasi manajemen armada logistik dan pelacakan kurir lapangan kelas industri yang dirancang untuk kondisi jaringan minim (remote operations), sinkronisasi data intensif, dan interaksi hardware tingkat tinggi.

### Arsitektur Tingkat Tinggi
Aplikasi dibangun di atas pondasi **React Native New Architecture murni (Bridgeless Mode)**, memanfaatkan direct memory bridge C++ untuk kalkulasi telemetri sensor, penyimpanan lokal berbasis relational database terenkripsi, serta background-sync engine yang beroperasi tanpa gangguan sistem operasi.

```
+-----------------------------------------------------------------------------------+
|                        REACT NATIVE RUNTIME (Hermes Engine)                       |
|                                                                                   |
|  [ Presentation Layer ]                                                           |
|    - FlashList V2 Virtualized Cargo Manifests                                     |
|    - Skia Hardware-Accelerated Interactive Dynamic Route Heatmaps                 |
|    - Reanimated 3 Swipe-to-Action Bottom Sheet Controls                           |
|                                                                                   |
|  [ Application Logic Layer ]                                                      |
|    - Zustand State Store + XState Finite State Machines (Delivery Journey)        |
|    - TanStack Query v5 Cache Reconciliation                                       |
|                                                                                   |
|  [ Data / Persistence Layer ]                                                     |
|    - Offline Mutex Sync Engine (Priority Queue)                                   |
|    - WatermelonDB + SQLCipher (AES-256 Embedded Encryption)                       |
+------------------------------------------+----------------------------------------+
                                           |
                               JSI Direct C++ Bindings
                                           |
+------------------------------------------+----------------------------------------+
|                           NATIVE HARDWARE PLATFORM                                |
|                                                                                   |
|  [ TurboModules C++ / Swift / Kotlin ]                                            |
|    - VisionCamera Frame Processors (High-speed QR/Barcode Consignment Scanners)   |
|    - Secure Enclave Cryptographic Proof-of-Delivery Signing Engine                |
|    - Android Foreground Service / iOS BGAppRefresh Location Engine                |
|    - Network Integrity & Certificate Pinning Transport Layer                      |
+-----------------------------------------------------------------------------------+
```

### Kebutuhan Fungsional Minimum (Spesifikasi Teknis)
1. **Low-Latency Consignment Scanner:** Menggunakan VisionCamera v4 dengan frame processor native C++ untuk membaca barcode/QR resi barang secara terus menerus dengan zero frame-loss di rendering pipeline.
2. **Offline-First Delivery Lifecycle State Machine:** Memetakan status paket (`MANIFESTED` -> `IN_TRANSIT` -> `OUT_FOR_DELIVERY` -> `DELIVERED` / `FAILED`) menggunakan XState. Transisi status harus ditulis seketika ke SQLCipher storage secara lokal, dan tetap konsisten meskipun aplikasi dihentikan paksa (*force kill*) oleh sistem operasi.
3. **High-Accuracy Persistent Telemetry:** Melacak posisi armada secara real-time via Foreground Service di Android dan Background Location di iOS, memfilter jitter GPS menggunakan algoritma filter Kalman berbasis native C++, serta melakukan kompresi buffer titik koordinat sebelum dikirim ke API server.
4. **Hardware Cryptographic Proof-of-Delivery (PoD):** Pengambilan tanda tangan digital dan foto bukti pengiriman yang langsung dienkripsi menggunakan private key yang dibuat di dalam iOS Secure Enclave / Android Hardware Keystore.
5. **Interactive Skia Fleet Dashboard:** Render visualisasi rute perjalanan, load capacity gauge, dan thermal/fuel telemetry kurir menggunakan kanvas React Native Skia yang berjalan pada 120 FPS tanpa membebani JS Thread.

### Database Schema (Local SQLite / WatermelonDB)
```sql
CREATE TABLE consignments (
    id TEXT PRIMARY KEY NOT NULL,
    tracking_number TEXT UNIQUE NOT NULL,
    recipient_name TEXT NOT NULL,
    recipient_address TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    status TEXT CHECK(status IN ('MANIFESTED', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'DELIVERED', 'FAILED')) NOT NULL,
    pod_signature_blob BLOB,
    synced_at INTEGER,
    created_at INTEGER NOT NULL
);

CREATE TABLE offline_mutation_queue (
    id TEXT PRIMARY KEY NOT NULL,
    endpoint TEXT NOT NULL,
    payload TEXT NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    retry_count INTEGER DEFAULT 0,
    created_at INTEGER NOT NULL
);

CREATE TABLE telemetry_breadcrumbs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    accuracy REAL NOT NULL,
    speed REAL NOT NULL,
    timestamp INTEGER NOT NULL,
    is_synced INTEGER DEFAULT 0
);
```

### Standar Kriteria Kelulusan (Production-Grade Definition of Done)
* **Kinerja Rendering:** Tidak terjadi jank (0 frame drop di bawah 59 FPS pada monitor standar, atau di bawah 118 FPS pada layar ProMotion 120 Hz) saat rendering dan scrolling list berisi minimal 10.000 data konsinyasi.
* **Memori:** Konsumsi heap memory JS stabil di bawah batas 120MB tanpa tren kenaikan linear (*zero leak*) selama proses stress-testing scrolling dan scanning selama 30 menit terus-menerus.
* **Ketahanan Jaringan:** Transaksi status pengiriman yang disimulasikan dalam mode Airplane Mode harus tersimpan di antrian lokal tanpa kegagalan, dan seluruh mutasi berhasil disinkronisasi ke server mock secara otomatis dalam urutan yang tepat ketika koneksi dialihkan kembali ke online.
* **Keamanan:** Terproteksi penuh dari sniffing MITM (HTTP Toolkit/Proxyman) via SSL Pinning, bundle JavaScript terenkripsi dan ter-obfuscate dengan benar, serta proteksi screen capture aktif saat beralih ke app switcher.
* **Otomasi CI/CD:** Script pipeline Fastlane / EAS berhasil melakukan build artifact `.aab` (Android) dan `.ipa` (iOS) secara mandiri di runner CI, lulus pengujian unit/integration (minimal 80% coverage), dan lulus scenario test E2E via Maestro tanpa kegagalan.