# Kurikulum Komprehensif Rekayasa Perangkat Lunak: SwiftUI Enterprise Architecture

Dokumen ini merupakan spesifikasi silabus resmi dan panduan kurikulum tingkat lanjut untuk penguasaan mendalam **SwiftUI**. Kurikulum ini dirancang untuk mentransformasi *engineer* dari pemahaman imperatif UIKit tradisional atau tingkat pemula menuju penguasaan arsitektur deklaratif modern, optimasi *AttributeGraph*, rendering performa tinggi, dan orkestrasi sistem multimodular berskala *enterprise*.

---

## 1. Course Overview & Mindset

### Paradigma Deklaratif vs Imperatif
Pemrograman antarmuka modern di ekosistem Apple menuntut pergeseran mental (*mental model shift*) mendasar: antarmuka pengguna tidak lagi dimutasi secara langsung melalui serangkaian instruksi prosedural (`addSubView`, `updateFrame`, `reloadRows`), melainkan merupakan **fungsi murni dari state**:

$$\text{UI} = f(\text{State})$$

SwiftUI mengabstraksi siklus hidup *view* menjadi struktur data nilai (*value types*) yang ringan dan efisien. Di balik layar, mesin *runtime* SwiftUI mengompilasi representasi hierarki ini ke dalam **AttributeGraph**, sebuah graf dependensi terarah (*directed acyclic graph*) yang secara dinamis melacak dependensi state dan memvalidasi ulang nodus graf yang terpengaruh tanpa mengorbankan siklus CPU pada *rendering pass* yang redundan.

### Filosofi Arsitektur & Rekayasa
Kurikulum ini dirancang dengan prinsip-prinsip rekayasa tingkat tinggi:
*   **Predictable State Invariants**: Mengeliminasi *race conditions* dan *inconsistent UI states* dengan memanfaatkan kapabilitas sistem tipe Swift, *Swift Concurrency* (`Sendable`, `Actor`, `@MainActor`), dan *Observation framework* modern.
*   **Zero Overhead Abstractions**: Memahami implikasi alokasi memori pada *stack* versus *heap* untuk *View structs*, serta mekanisme *copy-on-write* dan diferensiasi *view body*.
*   **Production Telemetry & Profiling**: Pendekatan diagnostik berbasis data menggunakan Apple Instruments (SwiftUI View Sweeps, Time Profiler, Allocations) serta metode `_printChanges()` untuk mendeteksi *invalidation cascades*.
*   **Platform Versatility & Modularity**: Memisahkan logika bisnis dari lapisan presentasi untuk memfasilitasi penggunaan kembali kode di seluruh platform Apple (iOS, iPadOS, macOS, watchOS, tvOS, dan visionOS) melalui Swift Package Manager (SPM).

---

## 2. Learning Roadmap

```plaintext
SwiftUI Enterprise Architecture Roadmap
│
├── [Bab 01] Paradigma Deklaratif & Fondasi Runtime
│   ├── Modul 01: View Protocol, AttributeGraph, & Render Tree
│   └── Modul 02: Value Semantics, Identity, & View Lifecycle
│
├── [Bab 02] Layout Engine & Adaptive System
│   ├── Modul 01: SwiftUI Layout Protocol & Geometry Negotiation
│   ├── Modul 02: Advanced Stacks, Grid, & Container Customization
│   └── Modul 03: Adaptive Layouts, Size Classes, & Dynamic Type
│
├── [Bab 03] State Management & Data Flow Reaktif
│   ├── Modul 01: Primitif State Lokal (@State, @Binding)
│   ├── Modul 02: Modern Swift Observation (@Observable, ObservationTracking)
│   └── Modul 03: Dependency Injection & Environment Propagation
│
├── [Bab 04] Navigation Engine & Structural Routing
│   ├── Modul 01: NavigationStack, NavigationPath, & Type-Safe Routing
│   ├── Modul 02: Split Views, Deep Linking, & Window Management
│   └── Modul 03: Modal Presentations, Sheet Lifecycle, & Coordinators
│
├── [Bab 05] Modern Concurrency & Async UI Orchestration
│   ├── Modul 01: Task Lifecycles, AsyncSequence, & MainActor Integration
│   └── Modul 02: Structured Concurrency, Actor Reentrancy, & Cancelation
│
├── [Bab 06] Graphics, Metal, & Advanced Animations
│   ├── Modul 01: Transaction System & Explicit Animations
│   ├── Modul 02: Keyframe & Phase Animators
│   └── Modul 03: Custom Canvas, Vector Graphics, & Metal Shaders
│
├── [Bab 07] Interoperabilitas Ekosistem: Bridge UIKit & AppKit
│   ├── Modul 01: UIViewRepresentable, UIViewControllerRepresentable, & Coordinator
│   └── Modul 02: Hosting Controllers, Bridging Views, & Legacy Embeds
│
├── [Bab 08] Persistensi & Offline-First Data Pipeline
│   ├── Modul 01: SwiftData Integration, ModelActor, & Schema Migration
│   └── Modul 02: Core Data Interop, Background Contexts, & CloudKit Sync
│
├── [Bab 09] Performance Engineering, Profiling, & Diagnostics
│   ├── Modul 01: Invalidation Cascade Analysis & Profiling Instruments
│   └── Modul 02: Memory Leaks, Retain Cycles, & ViewInspector Unit Tests
│
└── [Bab 10] Enterprise Architecture: SPM, Multiplatform, & TCA
    ├── Modul 01: SPM Multi-Module Dependency Architecture
    ├── Modul 02: The Composable Architecture (TCA) & Redux Paradigms
    └── Modul 03: Cross-Platform Parity: iOS, macOS, watchOS, & visionOS
```

---

## 3. Navigasi Silabus

### Bab 01: Paradigma Deklaratif & Fondasi Runtime
Eksplorasi mendalam mekanisme internal *runtime* SwiftUI, representasi tipe `some View`, dan evaluasi *AttributeGraph*.
*   [Modul 01: View Protocol, AttributeGraph, & Render Tree](./bab-01-paradigma-fondasi-runtime/01-view-protocol-attribute-graph.md)
    *Membahas dekompilasi struktur View, ViewBuilder, cara SwiftUI menyusun AST graf komponen, dan siklus evaluasi Render Tree.*
*   [Modul 02: Value Semantics, Identity, & View Lifecycle](./bab-01-paradigma-fondasi-runtime/02-value-semantics-identity-lifecycle.md)
    *Analisis Structural Identity vs Explicit Identity, dampak performa identitas terhadap instansiasi memori, dan titik kritis `.onAppear`/`.onDisappear`.*

### Bab 02: Layout Engine & Adaptive System
Penguasaan sistem penataan posisi SwiftUI, negosiasi dimensi layout 3-fase, dan perancangan antarmuka adaptif.
*   [Modul 01: SwiftUI Layout Protocol & Geometry Negotiation](./bab-02-layout-adaptive-system/01-layout-protocol-geometry.md)
    *Implementasi kustom `Layout` protocol, perhitungan `IntrinsicContentSize`, kalkulasi *cache-subviews*, dan batasan `GeometryReader`.*
*   [Modul 02: Advanced Stacks, Grid, & Container Customization](./bab-02-layout-adaptive-system/02-advanced-stacks-grid.md)
    *Pemanfaatan `LazyVStack`, `LazyHGrid`, `GridRow`, `ViewThatFits`, dan pembuatan *flow layouts* dinamis tanpa *re-render* destruktif.*
*   [Modul 03: Adaptive Layouts, Size Classes, & Dynamic Type](./bab-02-layout-adaptive-system/03-adaptive-layouts-dynamic-type.md)
    *Strategi penanganan multi-form factor via `HorizontalSizeClass`, Dynamic Type scaling matrix, dan arsitektur aksesibilitas inklusif.*

### Bab 03: State Management & Data Flow Reaktif
Arsitektur aliran data unidireksional, pelacakan dependensi, dan eliminasi *mutation race conditions*.
*   [Modul 01: Primitif State Lokal (@State, @Binding)](./bab-03-state-data-flow/01-primitif-state-binding.md)
    *Mekanisme internal `DynamicProperty`, representasi penyimpanan memori oleh framework, dan pembuatan custom two-way bindings.*
*   [Modul 02: Modern Swift Observation (@Observable, ObservationTracking)](./bab-03-state-data-flow/02-modern-swift-observation.md)
    *Transisi dari `ObservableObject` / `Combine` ke framework `Observation`, optimasi dependensi properti secara granular, dan mitigasi overhead.*
*   [Modul 03: Dependency Injection & Environment Propagation](./bab-03-state-data-flow/03-dependency-injection-environment.md)
    *Perancangan arsitektur dependensi berlapis menggunakan `EnvironmentValues`, `@Environment`, `EntryMacro`, dan *scoped resolution*.*

### Bab 04: Navigation Engine & Structural Routing
Pola perutean hierarki modern yang modular, dapat di-*deep link*, dan terpisah dari implementasi *View*.
*   [Modul 01: NavigationStack, NavigationPath, & Type-Safe Routing](./bab-04-navigation-routing/01-navigationstack-path-routing.md)
    *Arsitektur router terdesentralisasi, manipulasi `NavigationPath` berbasis enum bertipe data aman, dan pemulihan state navigasi.*
*   [Modul 02: Split Views, Deep Linking, & Window Management](./bab-04-navigation-routing/02-split-views-deep-linking-windows.md)
    *Pemanfaatan `NavigationSplitView` untuk iPadOS/macOS, manajemen multi-window, parsing URL Scheme, dan `Universal Links` ingestion.*
*   [Modul 03: Modal Presentations, Sheet Lifecycle, & Coordinators](./bab-04-navigation-routing/03-modal-presentations-coordinators.md)
    *Orkestrasi presentasi sheet, detents kustom (`presentationDetents`), isolasi interaksi latar belakang, dan implementasi Coordinator Pattern.*

### Bab 05: Modern Concurrency & Async UI Orchestration
Sinkronisasi antarmuka dengan kapabilitas Swift Concurrency modern tanpa *race conditions* dan *deadlocks*.
*   [Modul 01: Task Lifecycles, AsyncSequence, & MainActor Integration](./bab-05-concurrency-async-ui/01-task-lifecycles-asyncsequence.md)
    *Integrasi `.task` lifecycle modifier, konsumsi real-time stream via `AsyncStream`/`AsyncSequence`, dan garansi eksekusi thread `@MainActor`.*
*   [Modul 02: Structured Concurrency, Actor Reentrancy, & Cancelation](./bab-05-concurrency-async-ui/02-structured-concurrency-cancelation.md)
    *Penanganan kooperatif pembatalan tugas async, mitigasi *Actor reentrancy issues* pada mutasi UI, dan implementasi debounce/throttle asinkron.*

### Bab 06: Graphics, Metal, & Advanced Animations
Eksekusi grafis performa tinggi, animasi berbasis fisika, dan manipulasi piksel menggunakan Metal Shading Language.
*   [Modul 01: Transaction System & Explicit Animations](./bab-06-graphics-metal-animations/01-transactions-explicit-animations.md)
    *Mekanika internal `Transaction`, interupsi kurva interpolasi, perancangan transisi kustom dengan `GeometryEffect` dan `AnimatableModifier`.*
*   [Modul 02: Keyframe & Phase Animators](./bab-06-graphics-metal-animations/02-keyframe-phase-animators.md)
    *Orkestrasi sekuensial multi-tahap kompleks menggunakan `PhaseAnimator` dan kurva Bézier non-linear via `KeyframeAnimator`.*
*   [Modul 03: Custom Canvas, Vector Graphics, & Metal Shaders](./bab-06-graphics-metal-animations/03-canvas-metal-shaders.md)
    *Rendering primitif 2D via `Canvas`, integrasi Metal Shading Language (MSL) dengan `.colorEffect`, `.distortionEffect`, dan `.layerEffect`.*

### Bab 07: Interoperabilitas Ekosistem: Bridge UIKit & AppKit
Integrasi dua arah antara SwiftUI modern dan pustaka imperatif legasi UIKit/AppKit tanpa *memory leak*.
*   [Modul 01: UIViewRepresentable, UIViewControllerRepresentable, & Coordinator](./bab-07-interoperabilitas-uikit-appkit/01-representable-coordinator.md)
    *Menjembatani komponen kompleks imperatif (seperti `MKMapView` dan `WKWebView`), manajemen delegasi, dan pemeliharaan siklus hidup state.*
*   [Modul 02: Hosting Controllers, Bridging Views, & Legacy Embeds](./bab-07-interoperabilitas-uikit-appkit/02-hosting-controllers-legacy-embeds.md)
    *Strategi penanaman SwiftUI ke dalam `UICollectionViewCell` melalui `UIHostingController`, ukuran dinamis (`self-sizing`), dan performa scrolling.*

### Bab 08: Persistensi & Offline-First Data Pipeline
Manajemen state persisten skala enterprise menggunakan model modern SwiftData dan bridging Core Data.
*   [Modul 01: SwiftData Integration, ModelActor, & Schema Migration](./bab-08-persistensi-offline-pipeline/01-swiftdata-modelactor-migration.md)
    *Implementasi `@Model`, manipulasi data terisolasi di background via `ModelActor`, versioning skema (`SchemaMigrationPlan`), dan optimasi query.*
*   [Modul 02: Core Data Interop, Background Contexts, & CloudKit Sync](./bab-08-persistensi-offline-pipeline/02-coredata-background-cloudkit.md)
    *Konkurensi multi-konteks Core Data, sinkronisasi otomatis CloudKit, pemecahan konflik data (*conflict resolution*), dan bridging ke SwiftUI via `@FetchRequest`.*

### Bab 09: Performance Engineering, Profiling, & Diagnostics
Metodologi eliminasi *hitch rate*, minimasi *invalidation cascades*, dan otomasi validasi antarmuka.
*   [Modul 01: Invalidation Cascade Analysis & Profiling Instruments](./bab-09-performance-diagnostics/01-invalidation-cascades-instruments.md)
    *Teknik profiling menggunakan Xcode Instruments (SwiftUI template), analisis `Self._printChanges()`, dan identifikasi komputasi berat di dalam *view body*.*
*   [Modul 02: Memory Leaks, Retain Cycles, & ViewInspector Unit Tests](./bab-09-performance-diagnostics/02-leaks-retain-cycles-viewinspector.md)
    *Deteksi kebocoran memori berbasis `DynamicProperty`, unit testing hierarki deklaratif secara headless via `ViewInspector`, dan pengujian regresi UI.*

### Bab 10: Enterprise Architecture: SPM, Multiplatform, & TCA
Desain arsitektur aplikasi berskala jutaan pengguna, modularisasi paket, dan konsistensi platform.
*   [Modul 01: SPM Multi-Module Dependency Architecture](./bab-10-enterprise-architecture/01-spm-multimodule-architecture.md)
    *Isolasi modul fitur, pemisahan kontrak domain (*interface vs implementation*), dan optimasi waktu kompilasi (*build-graph optimization*).*
*   [Modul 02: The Composable Architecture (TCA) & Redux Paradigms](./bab-10-enterprise-architecture/02-tca-redux-paradigms.md)
    *Penerapan *state management deterministic*, efek samping terkontrol (*dependencies/reducers*), dan *test-driven development* terisolasi.*
*   [Modul 03: Cross-Platform Parity: iOS, macOS, watchOS, & visionOS](./bab-10-enterprise-architecture/03-cross-platform-multiplatform-targets.md)
    *Strategi penggunaan kembali 90%+ basis kode di seluruh platform Apple dengan memanfaatkan perlakuan kondisional modular dan input modalitas unik (misal: spatial computing pada visionOS).*

---

## 4. Spesifikasi Capstone Project Enterprise

### Nama Proyek: **AuraTrade — Multi-Asset High-Frequency Institutional Trading Desk**

AuraTrade adalah platform terminal perdagangan multi-aset institusional (*real-time equities, FX, & digital derivatives*) yang dirancang khusus untuk ekosistem Apple (iOS, iPadOS, macOS, visionOS) dengan kinerja 120 FPS tanpa kompromi (*zero dropped frames*).

```plaintext
                               ┌──────────────────────────────────────────┐
                               │           AuraTrade Client Core          │
                               └────────────────────┬─────────────────────┘
                                                    │
                   ┌────────────────────────────────┼────────────────────────────────┐
                   ▼                                ▼                                ▼
     ┌──────────────────────────┐     ┌──────────────────────────┐     ┌──────────────────────────┐
     │     Streaming Engine     │     │      Local Database      │     │      Rendering Core      │
     │  WebSocket / gRPC Stream │     │   SwiftData (ModelActor) │     │ Custom Metal Shaders     │
     │  Real-time Order Book    │     │   Timeseries Tick Data   │     │ Canvas Real-time Charts  │
     └─────────────┬────────────┘     └─────────────┬────────────┘     └─────────────┬────────────┘
                   │                                │                                │
                   └────────────────────────────────┼────────────────────────────────┘
                                                    ▼
                                      ┌───────────────────────────┐
                                      │   Modular Presentation    │
                                      │   TCA / Observation Graph │
                                      │   NavigationSplitView     │
                                      └───────────────────────────┘
```

### Kebutuhan Fungsional & Arsitektur
1.  **Ingestion & State Engine Berkecepatan Tinggi**:
    *   Menerima ribuan perubahan data (*ticks*) per detik via WebSocket/gRPC multiplexed stream.
    *   Memanfaatkan *Actor Model* dan `AsyncSequence` untuk melakukan *throttling* serta *batching* state update pada 16.6ms intervals (60Hz) atau 8.3ms intervals (120Hz ProMotion).
    *   State global diatur menggunakan arsitektur modular **TCA (The Composable Architecture)** atau modul kustom berbasis macro `@Observable` dengan isolasi dependensi absolut.
2.  **Visualisasi Grafis Kustom & Akselerasi Metal**:
    *   Grafik Candlestick dan Depth-Chart interaktif dirender menggunakan `Canvas` primitif dan custom Metal Shaders (`.colorEffect` dan `.distortionEffect` untuk visualisasi volatilitas).
    *   Pencapaian performa 120 FPS konstan saat melakukan *panning* dan *zooming* data timeseries jutaan candle.
3.  **Offline-First & Persistensi Timeseries**:
    *   Penyimpanan lokal menggunakan **SwiftData** terisolasi via `ModelActor` kustom untuk penulisan transaksi background tanpa memblokir thread `@MainActor`.
    *   Mekanisme sinkronisasi inkremental saat konektivitas terputus, dengan schema migration plan bertingkat.
4.  **Multiplatform Adaptability**:
    *   Mengimplementasikan tata letak tiga kolom adaptif menggunakan `NavigationSplitView` di iPadOS dan macOS.
    *   Integrasi *Spatial Windows* dan *Volumes* khusus visionOS untuk visualisasi kedalaman pasar 3D.
5.  **Audit Performa & Tolok Ukur Kualitas (KPIs)**:
    *   **Hitch Rate**: `< 1.0 ms/s` di semua skenario animasi dan scrolling cepat.
    *   **Memory Footprint**: Stabil di bawah `150 MB` bahkan saat mengonsumsi data feed terus-menerus.
    *   **Test Coverage**: Cakupan minimum 85% untuk Reducer/Business Logic, dengan uji integrasi UI headless via `ViewInspector`.

---

## Standar Kode & Panduan Kontribusi
Setiap berkas materi modul dan implementasi capstone diwajibkan:
1. Mematuhi gaya penulisan Swift standar industri (*Swift API Design Guidelines*).
2. Memisahkan *Side Effects* dari rendering deklaratif.
3. Melampirkan diagram alur arsitektur, penjelasan komputasi kompleksitas waktu/ruang, serta demonstrasi kode berbasis skenario produksi riil.