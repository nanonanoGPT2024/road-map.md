# BAB 10: Quiz, Challenge, & Knowledge Check
**Enterprise Architecture: SPM, Multiplatform, & TCA**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Static vs. Dynamic Linking pada Swift Package Manager (SPM):**
   Jelaskan secara mendalam bagaimana runtime dyld (dynamic linker) memperlakukan modularisasi SPM saat sebuah target dikonfigurasi sebagai `.static` dibandingkan `.dynamic`. Apa dampaknya terhadap ukuran binary final, alokasi memori heap/stack, dan metrik pre-main execution time (*dyld bootstrap & dylib loading time*) saat cold launch aplikasi enterprise?

2. **Unidirectional Data Flow (UDF) & Mutasi Value Semantics pada TCA:**
   The Composable Architecture (TCA) secara ketat membatasi mutasi `State` hanya melalui `Reducer` menggunakan inout parameter (`inout State`). Mengapa TCA menolak reference-type semantics (`class`) untuk domain state, dan bagaimana mekanisme structural sharing pada Swift `struct` mencegah overhead duplikasi alokasi memori (*copy-on-write optimization*) saat snapshot state bertransformasi?

3. **Abstraksi Arsitektur Multiplatform (iOS, macOS, visionOS):**
   Dalam merancang modul SPM multiplatform berskala enterprise, mengapa menggunakan conditional compilation `#if os(...)` secara masif di dalam layer Presentation/View dianggap sebagai *architectural smell*? Bagaimana memisahkan domain logic, state management, dan platform-specific rendering menggunakan teknik polymorphic feature injection atau adapter protocol?

4. **Modern Dependency Management via `@Dependency` (TCA):**
   Bagaimana sistem `@Dependency` pada TCA modern memanfaatkan Swift Task Local values untuk menggantikan Service Locator dan EnvironmentObject standar? Analisis perbedaan lifecycle antara `liveValue`, `testValue`, dan `previewValue` dalam konteks deterministic testing serta preview canvas execution.

5. **Komposisi State & Feature Isolation (`Scope` Reducer):**
   Jelaskan mekanisme internal operator `Scope` dalam TCA. Bagaimana parent reducer mendelegasikan child action ke child reducer tanpa memecahkan isolasi enkapsulasi child domain, dan bagaimana mekanisme runtime mencegah child feature memodifikasi bagian state parent yang tidak berada dalam domain tanggung jawabnya?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Diamond Dependency & Duplicate Symbol Collision:**
   Sebuah aplikasi enterprise memecah fiturnya menjadi beberapa package: `FeatureA`, `FeatureB`, dan keduanya bergantung pada modul `SharedUtilities`. Jika `FeatureA` dan `FeatureB` di-link sebagai dynamic framework oleh main app target, tetapi `SharedUtilities` didefinisikan sebagai library `.static` implisit, jelaskan apa yang terjadi saat runtime linker mengeksekusi biner. Bagaimana cara mengidentifikasi dan merektifikasi duplikasi symbol collision tersebut di SPM manifest (`Package.swift`)?

2. **Diagnostik Infinite Action Loop pada TCA:**
   Perhatikan pola reducer berikut:
   ```swift
   case .dataLoaded(let items):
       state.items = items
       return .run { send in
           await send(.refreshAnalytics)
       }
   case .refreshAnalytics:
       return .run { send in
           await send(.dataLoaded([])) // Potensi rekursif
       }
   ```
   Bagaimana Anda menganalisis, mendeteksi stack trace overflow, dan mendesain arsitektur action yang benar menggunakan non-emitting side-effects atau fire-and-forget effects (`Effect.fireAndForget` / `cancellable`) agar siklus reduksi runtime tidak mengalami deadlock atau starvation pada Cooperative Thread Pool?

3. **Edge Case Strict Concurrency (Swift 6) pada SPM Packages:**
   Saat mengaktifkan `SWIFT_STRICT_CONCURRENCY = complete` pada modul SPM enterprise, compiler melemparkan error:
   `Capture of non-sendable type 'LegacyAnalyticsTracker' into a '@Sendable' closure`.
   Bagaimana Anda merefaktor integrasi dependensi warisan (*legacy SDK*) ini ke dalam TCA Client pattern tanpa menggunakan `@unchecked Sendable` secara sembrono?

4. **Multiplatform Window Management & Scene Phase Discrepancy:**
   Pada macOS, aplikasi SwiftUI berjalan dengan kapabilitas multi-window (`WindowGroup` multi-instance) dan independen scene life-cycle, berbeda dengan iOS yang umumnya berupa single-scene (atau Stage Manager iPadOS). Bagaimana arsitektur Store TCA harus di-*scope* agar state synchronization antar window di macOS tidak mengalami race condition atau mutasi paralel yang saling menimpa?

5. **Exhaustive Testing Failure pada TestStore:**
   Saat menjalankan unit test menggunakan `TestStore` pada TCA, test gagal dengan assertion:
   `Assertion failed: An effect returned for this action is still running. It must complete before the test finishes.`
   Jelaskan root cause internal dari error ini terkait asynchronous task scheduling (Clock/ContinuousClock) dan bagaimana menerapkan `TestClock` untuk memvalidasi efek debouncing atau throttling tanpa menggunakan `Thread.sleep` atau `Task.sleep` nyata.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Clean Architecture Regression pasca Modularisasi Skala Besar
*Konteks:* Tim Engineering Anda bermigrasi dari monolitik monolith-target ke modular multi-package SPM dengan 45 package independen. CI/CD build time melonjak dari 6 menit menjadi 24 menit pada clean build, dan metrik Time-To-Interactive (TTI) saat cold launch aplikasi di production mengalami degradasi sebesar 1.8 detik akibat ratusan dylib yang harus di-*rebase* dan di-*bind* oleh dyld di runtime.
* **Pertanyaan Diagnostik:**
  1. Audit teknis apa yang harus Anda lakukan terhadap skema linkage (`type: .dynamic` vs default `.static`) pada konfigurasi `Package.swift` untuk mereduksi overhead dyld pre-main time?
  2. Bagaimana Anda merancang strategi package caching, binary dependencies (`.xcframework`), dan parallel compilation graph untuk memangkas CI clean build time kembali di bawah target SLA?

### Skenario B: Race Condition & Data Corruption pada High-Frequency TCA WebSocket Stream
*Konteks:* Modul Trading/Fintech enterprise menggunakan TCA untuk menampilkan order book crypto secara real-time via WebSocket. Saat market mengalami volatilitas ekstrem, WebSocket mem-push 300+ paket update per detik. Implementasi `Effect.run` yang memicu puluhan action ke Store menyebabkan Main Thread hitching (UI drop hingga 12 FPS), memory allocation melonjak tajam, dan sesekali child state mengalami out-of-order execution sehingga tampilan harga menampilkan data lama (*stale snapshot*).
* **Pertanyaan Diagnostik:**
  1. Mengapa mem-dispatch Action TCA secara granular langsung dari high-frequency async sequence merupakan anti-pattern struktural?
  2. Rancang solusi end-to-end menggunakan buffering, throttle/debounce custom operator, task cancellation identifier (`Effect.cancel(id:)`), dan state batching agar render rate stabil di 60/120 FPS tanpa kehilangan data integrity.

### Skenario C: Multiplatform Architecture: iPadOS, macOS, dan visionOS Adaptability
*Konteks:* Perusahaan ingin merilis aplikasi enterprise kolaborasi dokumen yang mendukung platform macOS (dengan native Menu Bar, window snapping, keyboard shortcuts), iPadOS (dengan Apple Pencil hover, Split View), dan visionOS (dengan Volumes & Spatial RealityKit attachments). 80% bisnis logika dan persistence layer harus di-*share* secara murni tanpa ada kebocoran framework target khusus ke modul domain inti.
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda menyusun boundary graph di SPM (Core Domain, Infrastructure, Features, Platform Adaptors) agar kode platform-specific tidak mencemari TCA Reducer inti?
  2. Bagaimana merancang pola handling input multiplatform (misal: Keyboard Commands di macOS vs Spatial Gesture di visionOS) agar keduanya dapat menerjemahkan event platform yang berbeda menjadi Action domain TCA yang identik?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Multiplatform Core & Feature Modularization dengan TCA
Rancang arsitektur modul enterprise SPM monorepo lengkap untuk fitur **"Global Fleet Asset Monitoring"** yang berjalan cross-platform di iOS dan macOS.

#### Problem:
Aplikasi enterprise saat ini mengalami tight coupling antara view presentation dan logic tracking aset armada. Saat ditugaskan membuat versi macOS dashboard untuk supervisor dan iOS app untuk operator lapangan, tim engineer terjebak copy-pasting kode bisnis dan network client.

#### Requirements:
1. **SPM Modular Structure:** Buat struktur workspace SPM monorepo minimal dengan pemisahan boundary ketat:
   - `CoreModels`: Domain entities murni (Swift Structs, Sendable, tidak ada import dependensi luar).
   - `AssetClient`: Protocol / TCA Dependency Client interface + implementasi live/mock.
   - `FleetFeature`: Reducer TCA (`@Reducer`) yang mengelola fetch asset, status streaming, dan filtering.
   - `FleetUI-iOS` & `FleetUI-macOS`: Presentation layer spesifik platform yang mengonsumsi `StoreOf<FleetFeature>`.
2. **TCA Implementation:**
   - Gunakan macro `@Reducer`, `@ObservableState`, dan `@Dependency`.
   - Implementasikan side-effect monitoring aset secara asynchronous (simulasi live polling/stream) dengan kapabilitas start dan explicit cancel saat view disappear.
3. **Exhaustive Unit Testing:**
   - Buat minimal 1 skenario unit test menggunakan `TestStore` dan `TestClock` yang memvalidasi transisi state saat streaming aset menerima update data baru dan saat proses fetch mengalami network failure.
4. **Swift Concurrency:** Modul harus compile tanpa peringatan pada level `SWIFT_STRICT_CONCURRENCY = complete`.

#### Constraints:
- Dilarang keras menggunakan `#if os(iOS)` atau `#if os(macOS)` di dalam `FleetFeature` Reducer. Logika state machine harus 100% agnostic terhadap sistem operasi.
- Dilarang membuat dependensi siklikal antar package target SPM.
- Mock client harus sepenuhnya deterministik via `withDependencies`.

#### Expected Output:
- Kode snippet `Package.swift` yang mendeklarasikan target, dependencies, dan library products.
- File `FleetFeature.swift` berisi deklarasi Reducer, State, Action, dan Effect Handling.
- File `FleetClient.swift` berisi abstraksi dependency injection via `@DependencyClient`.
- File `FleetFeatureTests.swift` berisi pengujian deterministik menggunakan `TestStore`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara `.static` dan `.dynamic` linkage pada SPM serta dampaknya terhadap virtual memory paging dan dyld cold-start performance.
- [ ] Mekanisme pemisahan Store TCA: Root Store, Scoped Store, dan lifecycle `@ObservableState` untuk mencegah *unnecessary view invalidations*.
- [ ] Anatomi Dependency Client modern di TCA (`@DependencyClient`, `liveValue`, `testValue`) untuk abstraksi boundary IO (Network, Database, Sensors).
- [ ] Aturan isolasi data pada Swift 6 Concurrency: `Sendable`, Actor boundaries, dan Cooperative Thread Pool starvation risk saat mengeksekusi asynchronous side-effects.
- [ ] Best practices arsitektur platform-agnostic: Memisahkan domain action/state dari API UI spesifik OS (seperti `AppKit` vs `UIKit`).

### Saya tidak perlu menghafal:
- [ ] Seluruh macro expansion code yang digenerate oleh `@Reducer` atau `@ObservableState` di level abstract syntax tree (AST).
- [ ] Sintaks legacy TCA versi terdahulu (seperti `AnyReducer`, `ViewStore`, atau `WithViewStore`).
- [ ] Parameter build flag compiler LLVM internal tingkat rendah di luar konfigurasi SPM standar Swift Settings (`-Xfrontend`, dsb.).

### Saya harus bisa melakukan:
- [ ] Menganalisis dan merekayasa struktur multi-package SPM untuk meminimalkan compile time menggunakan modular boundaries yang tepat.
- [ ] Mengonfigurasi `Package.swift` dengan dynamic target products secara selektif untuk menghindari diamond dependency issue.
- [ ] Menulis exhaustive unit test menggunakan `TestStore` lengkap dengan manipulasi timing via `TestClock`.
- [ ] Melakukan profiling runtime TCA menggunakan Xcode Instruments (Time Profiler & Allocations) untuk mendeteksi re-render yang tidak efisien atau memory leak pada task cancellation token.
- [ ] Mengabstraksikan fitur multiplatform kompleks sehingga logic state machine dapat di-*share* secara penuh antara iOS, macOS, watchOS, dan visionOS tanpa branching kode yang kotor.