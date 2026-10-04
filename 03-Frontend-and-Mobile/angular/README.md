# Enterprise Angular Architecture: From Core Signals to Hyperscale Micro-Frontends

Selamat datang di kurikulum arsitektur rekayasa perangkat lunak modern untuk **Angular**. Repositori ini dirancang sebagai panduan komprehensif, berbasis produksi (*production-grade*), dan terstruktur secara modular untuk mentransformasi insinyur perangkat lunak menjadi **Lead Angular Architect**. Kurikulum ini berfokus secara eksklusif pada era modern Angular (v17, v18, dan seterusnya)—meninggalkan pola usang (*legacy*) berbasis `NgModule` dan beralih sepenuhnya ke paradigma **Standalone Components**, **Fine-grained Reactivity via Signals**, **Zoneless Change Detection**, **Hydration-ready SSR**, dan **Micro-Frontends**.

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
Membangun aplikasi web skala enterprise menuntut stabilitas tipe data (*type safety*), determinisme komputasi (*deterministic state*), efisiensi alokasi memori (*zero-leak lifecycles*), dan performa render mendekati native. Di Angular modern, arsitektur tidak lagi bergantung pada *dirty checking* global oleh Zone.js atau *boilerplate* deklarasi modul yang redundan. Fokus utama kurikulum ini adalah:

1. **Reaktivitas Deterministik**: Menguasai reaktivitas presisi tinggi (*fine-grained*) menggunakan Angular Signals untuk mutasi data sinkron dan mengombinasikannya dengan RxJS secara presisi untuk aliran data asinkron berbasis waktu (*event stream*).
2. **Kemandirian Komponen (*Standalone First*)**: Membangun pohon komponen yang bersih, modular, *tree-shakeable*, dan decoupled tanpa dependensi modul yang kompleks.
3. **Zoneless & Rendering Optimal**: Memahami mekanisme internal *change detection*, eliminasi Zone.js untuk pengurangan *bundle size*, serta implementasi *event replay* dan *hydration* non-destruktif pada SSR/SSG.
4. **Resiliensi dan Skalabilitas Enterprise**: Pola arsitektur enterprise mencakup *Hierarchical Dependency Injection*, *Decentralized State Management* (SignalStore/NgRx), serta arsitektur Micro-Frontend terdistribusi berbasis Native Federation.

### Target Audiens
- **Senior Software Engineers & Tech Leads** yang memimpin migrasi aplikasi monolitik enterprise ke arsitektur Angular modern.
- **Frontend Architects** yang bertanggung jawab merancang fondasi UI berskala jutaan pengguna dengan tata kelola performa (*performance budgets*) dan keamanan (*strict CSP*) yang ketat.
- **Full-stack Developers** yang ingin mendalami desain reaktivitas, integrasi API resilient, dan performa *server-side execution*.

### Prasyarat Teknis
- Penguasaan mendalam terhadap **TypeScript** tingkat lanjut (*Generics, Conditional Types, Type Narrowing, Decorators, Utility Types*).
- Pemahaman fundamental mengenai **DOM APIs**, **Event Loop**, dan paradigma pemrograman reaktif.
- Pengalaman dasar dalam manipulasi asynchronous stream (**RxJS Observables, Subjects, Operators**).
- Node.js LTS (>= 20.x) dan Angular CLI terbaru terpasang di mesin lokal.

---

## 2. Learning Roadmap

```text
========================================================================================
                          ENTERPRISE ANGULAR CURRICULUM ROADMAP
========================================================================================
[Bab 01: Fondasi Arsitektur Modern & Standalone Components]
 ├── Standalone Components, Directives, Pipes & Standalone Bootstrap
 ├── Built-in Control Flow (@if, @for, @switch) & Optimasi @defer
 └── Arsitektur Workspace Enterprise, Monorepo NX, dan Strict Mode
        │
        ▼
[Bab 02: Reaktivitas Inti: Signals, RxJS, dan Interoperabilitas]
 ├── Primitif Signals: signal(), computed(), dan effect()
 ├── Signal-Based Inputs, Outputs, Model, dan Queries
 └── Paradigma Hibrida: Interoperabilitas RxJS dan Signals (toSignal, toObservable)
        │
        ▼
[Bab 03: Arsitektur Komponen Tingkat Lanjut & Komposisi UI]
 ├── Siklus Hidup Komponen Modern & AfterRender Hooks
 ├── Directive Composition API, HostDirectives, dan Ekstensibilitas
 └── Dynamic Component Loading, ViewContainerRef, dan Advanced Content Projection
        │
        ▼
[Bab 04: Sistem Dependency Injection (DI) & Desain Layanan Enterprise]
 ├── Pohon Injector Hierarkis: EnvironmentInjector vs NodeInjector
 ├── Advanced Injection Tokens, Multi-Providers, dan Factory Functions
 └── Modern DI Menggunakan inject() Function dan Functional Design Patterns
        │
        ▼
[Bab 05: Routing Terdistribusi, Lazy Loading, dan Proteksi Rute]
 ├── Lazy-loaded Standalone Routes & Prefetching Strategies
 ├── Functional Guards (canActivateFn, canMatchFn) dan Dynamic Resolvers
 └── View Transitions API & State Preservation Routing
        │
        ▼
[Bab 06: Form Enterprise & Validasi Reaktif Lanjutan]
 ├── Strictly Typed Reactive Forms & Value/Status Changes Signals
 ├── Custom Asynchronous Validators dengan Dynamic Debouncing & Cancellation
 └── Form Engine Modular: Schema-Driven Dynamic Form Architecture
        │
        ▼
[Bab 07: State Management Terdesentralisasi & Skala Besar]
 ├── Arsitektur NgRx SignalStore: Signals, Methods, Hooks & Custom Features
 ├── Klasik NgRx: Store Terpusat, Reducers, Actions, dan ComponentStore
 └── Sinkronisasi State, Normalized Entities, dan Immutability Patterns
        │
        ▼
[Bab 08: Komunikasi Jaringan, Interceptors, dan Ketahanan API]
 ├── Modern HttpClient & Functional HttpInterceptors (Retry, Auth, Cache)
 ├── Penanganan Eror Terdistribusi, Global ErrorHandler, & Circuit Breaker
 └── Streaming Data Skala Riil: Server-Sent Events (SSE) & WebSocket Integration
        │
        ▼
[Bab 09: Rendering Sisi Server (SSR), Prerendering (SSG), & Hydration]
 ├── Angular Universal / SSR Engine Berbasis Vite dan Nitro
 ├── Non-Destructive Hydration & Event Replay Mechanics
 └── Server State Transfer (TransferState) dan SEO/OpenGraph Dynamics
        │
        ▼
[Bab 10: Performa Lanjutan, Zoneless Architecture, & Micro-Frontends]
 ├── Arsitektur Zoneless (provideExperimentalZonelessChangeDetection)
 ├── Profiling Memori, OnPush Detection, dan Runtime Performance Budgets
 └── Micro-Frontends Enterprise Berbasis Module Federation & Native Federation
========================================================================================
```

---

## 3. Navigasi Detail Modul (Bab 01 - Bab 10)

### [Bab 01: Fondasi Arsitektur Modern & Standalone Components](./bab-01-fondasi-arsitektur-dan-standalone-components/README.md)
Fokus pada rekonstruksi fondasi aplikasi web dengan menghilangkan lapisan abstraksi `NgModule`, memprioritaskan arsitektur berbasis Standalone Components, dan memanfaatkan template syntax bawaan terbaru untuk efisiensi kompilasi maksimal.
- [Modul 01: Standalone Components, Directives, Pipes, dan Bootstrap API](./bab-01-fondasi-arsitektur-dan-standalone-components/01-standalone-components-dan-bootstrap.md)
  *Mekanisme bootstrapping via `bootstrapApplication`, deklarasi standalone, import langsung, eliminasi overhead mental NgModule.*
- [Modul 02: Built-in Control Flow (@if, @for, @switch) dan Template Optimization](./bab-01-fondasi-arsitektur-dan-standalone-components/02-built-in-control-flow-dan-defer.md)
  *Sintaks deklaratif baru, optimasi pelacakan item melalui `track`, serta pembebanan modular dinamis menggunakan blok `@defer (on viewport, on idle)`.*
- [Modul 03: Arsitektur Monorepo Enterprise dengan Standar NX & Strict Mode](./bab-01-fondasi-arsitektur-dan-standalone-components/03-enterprise-workspace-dan-strict-mode.md)
  *Struktur monorepo berskala besar, isolasi domain library, modular boundary tagging, linting boundaries, dan konfigurasi TypeScript strict mode.*

### [Bab 02: Reaktivitas Inti: Signals, RxJS, dan Interoperabilitas](./bab-02-reaktivitas-inti-signals-dan-rxjs/README.md)
Mendalami revolusi paradigma reaktivitas Angular melalui Signals untuk operasi status sinkron berkinerja tinggi, dipadukan secara harmonis dengan RxJS untuk penanganan *stream* asinkron.
- [Modul 01: Primitif Signals: State Sinkron, Mutasi, dan Efek Samping](./bab-02-reaktivitas-inti-signals-dan-rxjs/01-primitif-signals.md)
  *Implementasi mendalam dari `signal()`, derivasi data menggunakan `computed()`, eksekusi efek samping terkontrol dengan `effect()`, serta mitigasi infinite loop.*
- [Modul 02: Signal-Based Inputs, Outputs, Model, dan Template Queries](./bab-02-reaktivitas-inti-signals-dan-rxjs/02-signal-inputs-outputs-dan-queries.md)
  *Peralihan dari decorator `@Input/@Output/@ViewChild` ke `input()`, `output()`, `model()`, `viewChild()`, dan `viewChildren()` berbasis signal.*
- [Modul 03: Interoperabilitas RxJS dan Signals dalam Arsitektur Hibrida](./bab-02-reaktivitas-inti-signals-dan-rxjs/03-interoperabilitas-rxjs-dan-signals.md)
  *Transformasi data stream dua arah menggunakan `toSignal()` dan `toObservable()`, penanganan initial value, injector context, dan unsubscription otomatis.*

### [Bab 03: Arsitektur Komponen Tingkat Lanjut & Komposisi UI](./bab-03-arsitektur-komponen-lanjutan-dan-komposisi-ui/README.md)
Membangun sistem komponen modular tingkat enterprise dengan memanfaatkan fitur komposisi langsung, manipulasi DOM berbasis hook modern, dan injeksi template dinamis.
- [Modul 01: Siklus Hidup Komponen Modern & AfterRender Hooks](./bab-03-arsitektur-komponen-lanjutan-dan-komposisi-ui/01-lifecycle-dan-afterrender-hooks.md)
  *Pola baru pasca-lifecycle klasik: `afterRender`, `afterNextRender`, manajemen referensi DOM yang aman dari context SSR.*
- [Modul 02: Directive Composition API dan HostDirectives Pattern](./bab-03-arsitektur-komponen-lanjutan-dan-komposisi-ui/02-directive-composition-api.md)
  *Menerapkan prinsip "composition over inheritance" menggunakan `hostDirectives`, mengekspos inputs/outputs directive secara selektif pada komponen target.*
- [Modul 03: Dynamic Component Loading, ViewContainerRef, dan Advanced Projection](./bab-03-arsitektur-komponen-lanjutan-dan-komposisi-ui/03-dynamic-components-dan-projection.md)
  *Instansiasi komponen runtime programmatic via `createComponent`, manipulasi slot proyeksi multi-slot `ng-content`, dan `ngTemplateOutlet` kontekstual.*

### [Bab 04: Sistem Dependency Injection (DI) & Desain Layanan Enterprise](./bab-04-sistem-dependency-injection-enterprise/README.md)
Menguasai inti dari fleksibilitas Angular: sistem Dependency Injection hierarkis, token kustom, dan penghapusan constructor injection demi pola fungsional modern.
- [Modul 01: Hierarki Injector: EnvironmentInjector vs NodeInjector](./bab-04-sistem-dependency-injection-enterprise/01-hierarki-injector-dan-resolusi.md)
  *Arsitektur pencarian dependensi dari level platform, root, environment, hingga ke node DOM elemen, serta implikasi performa alokasi injector.*
- [Modul 02: Injeksi Modern via inject() dan Functional Providers](./bab-04-sistem-dependency-injection-enterprise/02-inject-function-dan-functional-di.md)
  *Refactoring constructor injection ke fungsi `inject()`, pembuatan fungsi komposisi kustom (*injection context assertions*), dan functional tokens.*
- [Modul 03: Advanced Injection Tokens, Multi-Providers, dan Factory Patterns](./bab-04-sistem-dependency-injection-enterprise/03-tokens-multi-providers-dan-factories.md)
  *Implementasi `InjectionToken<T>`, penggunaan konfigurasi `multi: true` untuk interceptor modular, extensibility plugins, serta runtime factory providers.*

### [Bab 05: Routing Terdistribusi, Lazy Loading, dan Proteksi Rute](./bab-05-routing-terdistribusi-dan-proteksi-rute/README.md)
Mendesain sistem navigasi tangguh untuk aplikasi berskala besar, mengoptimalkan waktu muat halaman awal via segment splitting, serta mengamankan traversal data rute.
- [Modul 01: Lazy-Loaded Standalone Routes & Smart Prefetching Strategies](./bab-05-routing-terdistribusi-dan-proteksi-rute/01-lazy-loading-dan-prefetching.md)
  *Arsitektur modular routing via `loadChildren` dan `loadComponent`, strategi preloading terkustomisasi (*NetworkAwarePreloadStrategy*).*
- [Modul 02: Functional Guards, CanMatchFn, dan Isolated Resolvers](./bab-05-routing-terdistribusi-dan-proteksi-rute/02-functional-guards-dan-resolvers.md)
  *Pencegahan perutean tak terotorisasi menggunakan `CanActivateFn`, pencegahan loading bundle via `CanMatchFn`, dan pre-fetching data state via functional resolvers.*
- [Modul 03: Native View Transitions API Integration & State Persistence](./bab-05-routing-terdistribusi-dan-proteksi-rute/03-view-transitions-dan-state-routing.md)
  *Integrasi seamless View Transitions API untuk animasi transisi antar halaman tingkat native dan sinkronisasi rute dengan browser history state.*

### [Bab 06: Form Enterprise & Validasi Reaktif Lanjutan](./bab-06-form-enterprise-dan-validasi-reaktif/README.md)
Merancang mekanisme penanganan input kompleks, isolasi mutasi data pengguna dengan strict type safety, serta perancangan engine form berbasis skema.
- [Modul 01: Strictly Typed Reactive Forms & Signal Form Bridges](./bab-06-form-enterprise-dan-validasi-reaktif/01-strictly-typed-reactive-forms.md)
  *Penerapan `FormGroup`, `FormControl`, dan `FormArray` strictly typed, pembacaan reaktif status/nilai ke dalam Signals tanpa memori bocor.*
- [Modul 02: Asynchronous Validation Engine dengan Debouncing & Cancellation](./bab-06-form-enterprise-dan-validasi-reaktif/02-asynchronous-validators-dan-pembatalan.md)
  *Membangun custom async validators yang terintegrasi dengan backend, menangani race conditions via RxJS `switchMap`, dan isolasi status UI validasi.*
- [Modul 03: Dynamic Schema-Driven Form Generation Engine](./bab-06-form-enterprise-dan-validasi-reaktif/03-schema-driven-dynamic-forms.md)
  *Merancang engine renderer form otomatis berbasis JSON/Zod metadata skema untuk antarmuka formulir multi-langkah (*stepper*) berskala masif.*

### [Bab 07: State Management Terdesentralisasi & Skala Besar](./bab-07-state-management-terdesentralisasi/README.md)
Mengimplementasikan arsitektur state management modern, memilih antara pola terdistribusi SignalStore, ComponentStore, atau Redux global terpusat sesuai kebutuhan skala.
- [Modul 01: NgRx SignalStore: Modern, Lightweight & Signal-First State](./bab-07-state-management-terdesentralisasi/01-ngrx-signalstore-architecture.md)
  *Membangun store menggunakan `@ngrx/signals`: manipulasi state via `withState`, kalkulasi derivatif via `withComputed`, dan operasi async via `withMethods`.*
- [Modul 02: NgRx Store Terpusat: Actions, Reducers, Effects, dan Immutability](./bab-07-state-management-terdesentralisasi/02-global-ngrx-store-dan-effects.md)
  *Penerapan pola Redux global enterprise, optimasi efek samping kompleks via RxJS operators, dan isolasi entity manipulation via `@ngrx/entity`.*
- [Modul 03: State Persistence, Local Sync, dan Architectural Scalability](./bab-07-state-management-terdesentralisasi/03-state-persistence-dan-sinkronisasi.md)
  *Teknik serialisasi dan penyimpanan state lokal, sinkronisasi antar tab menggunakan `BroadcastChannel`, serta evaluasi batas modularitas state lokal vs global.*

### [Bab 08: Komunikasi Jaringan, Interceptors, dan Ketahanan API](./bab-08-komunikasi-jaringan-dan-ketahanan-api/README.md)
Mengelola lapisan integrasi HTTP, merancang pipeline interceptor intercepting fungsional, dan menangani komunikasi dupleks real-time yang resilient.
- [Modul 01: Modern HttpClient Architecture & Functional Interceptors](./bab-08-komunikasi-jaringan-dan-ketahanan-api/01-modern-httpclient-dan-interceptors.md)
  *Konfigurasi `provideHttpClient(withInterceptors([...]))`, mutasi request/response, token injection dinamis, dan deduplikasi request.*
- [Modul 02: Resilient Error Handling, Retry Policies, dan Circuit Breakers](./bab-08-komunikasi-jaringan-dan-ketahanan-api/02-resilient-error-handling-dan-circuit-breaker.md)
  *Strategi penanganan eror tersentralisasi, exponential backoff retry via RxJS, pelaporan telemetri sentral, dan degradasi layanan yang elegan.*
- [Modul 03: Real-Time Stream Integration: WebSockets dan Server-Sent Events](./bab-08-komunikasi-jaringan-dan-ketahanan-api/03-realtime-websockets-dan-sse.md)
  *Membangun layanan client stream adaptif untuk transmisi data real-time, otomatisasi reconnect, heartbeats, dan konversi stream data ke Angular Signals.*

### [Bab 09: Rendering Sisi Server (SSR), Prerendering (SSG), & Hydration](./bab-09-ssr-ssg-dan-hydration/README.md)
Mengoptimalkan First Contentful Paint (FCP) dan Largest Contentful Paint (LCP) melalui SSR modern berbasis Vite/Nitro engine, non-destructive hydration, dan mitigasi layout shifts.
- [Modul 01: Arsitektur SSR Modern Berbasis Vite & Nitro Engine](./bab-09-ssr-ssg-dan-hydration/01-ssr-engine-dan-prerendering.md)
  *Implementasi SSR modern pada Angular CLI baru, prerendering statis (SSG), manajemen context eksekusi server vs platform browser.*
- [Modul 02: Non-Destructive Hydration & Event Replay Engine](./bab-09-ssr-ssg-dan-hydration/02-non-destructive-hydration-dan-event-replay.md)
  *Mekanisme preservasi DOM server, aktivasi event hydration bertahap via Event Replay, dan pelacakan hydration mismatch pada komponen UI.*
- [Modul 03: State Transfer System (TransferState) & Dynamic Meta Tags](./bab-09-ssr-ssg-dan-hydration/03-transferstate-dan-seo-dynamics.md)
  *Mencegah duplicate HTTP fetches menggunakan `TransferState`, serialisasi data aman dari XSS, serta manajemen OpenGraph/SEO dinamis berbasis rute.*

### [Bab 10: Performa Lanjutan, Zoneless Architecture, & Micro-Frontends](./bab-10-performa-lanjutan-zoneless-dan-microfrontends/README.md)
Mencapai batas performa tertinggi aplikasi frontend: mengeliminasi dependensi Zone.js, profiling alokasi memori runtime, dan orkestrasi arsitektur federasi modular berskala global.
- [Modul 01: Arsitektur Zoneless: provideExperimentalZonelessChangeDetection](./bab-10-performa-lanjutan-zoneless-dan-microfrontends/01-arsitektur-zoneless.md)
  *Transisi ke aplikasi murni Zoneless, sinkronisasi manual ke scheduler Angular, eliminasi polyfill Zone.js, dan optimasi bundle footprint.*
- [Modul 02: Diagnostic Profiling, OnPush Change Detection, dan Memory Budgets](./bab-10-performa-lanjutan-zoneless-dan-microfrontends/02-profiling-onpush-dan-memory-leaks.md)
  *Analisis performa via Angular DevTools, deteksi siklus CD berulang, eliminasi *detached DOM nodes*, serta penegakan Angular CLI performance budgets.*
- [Modul 03: Enterprise Micro-Frontends Berbasis Native Federation](./bab-10-performa-lanjutan-zoneless-dan-microfrontends/03-micro-frontends-native-federation.md)
  *Perancangan arsitektur Host-Remote independen menggunakan Native Federation (ESM-based), dynamic remote loading, shared dependencies, dan sandbox routing.*

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Sistem
**OmniCloud Nexus: Hyperscale Infrastructure Observability & Governance Control Plane**

### Gambaran Umum
Sistem kontrol observabilitas cloud multi-tenant tingkat enterprise yang menyajikan metrik telemetri waktu nyata (*real-time metrics*), tata kelola konfigurasi cluster (*governance policy engine*), dan audit log transaksi infrastruktur secara terdesentralisasi. Sistem ini dibangun dengan arsitektur micro-frontend terdistribusi, sepenuhnya bebas dari Zone.js (*pure zoneless*), memanfaatkan SignalStore modular, serta mengimplementasikan SSR dengan non-destructive hydration.

### Persyaratan Arsitektural & Fungsional

```text
+---------------------------------------------------------------------------------------+
|                                HOST SHELL (Zoneless SSR)                              |
|  - Nitro / Node Engine  - Security CSP Policy  - Module Federation Loader             |
|  - Global Identity & Auth SignalStore          - Global Navigation Shell              |
+------------------------------------------+--------------------------------------------+
                                           |
         +---------------------------------+---------------------------------+
         |                                                                   |
         ▼                                                                   ▼
+-----------------------------------+             +-------------------------------------+
| REMOTE 1: Telemetry Dashboard     |             | REMOTE 2: Governance & Security     |
| (Micro-Frontend / Native Fed)     |             | (Micro-Frontend / Native Fed)       |
| - High-frequency WebSocket Feeds  |             | - Schema-driven Policy Forms        |
| - Zoneless Chart Visualizer       |             | - Complex Async Validation Engine   |
| - Signal-driven Buffer Pools      |             | - Role-based Functional Guards      |
+-----------------------------------+             +-------------------------------------+
         |                                                                   |
         +---------------------------------+---------------------------------+
                                           |
                                           ▼
+---------------------------------------------------------------------------------------+
| SHARED CORE & UTILITY LIBRARIES (NX Monorepo)                                         |
| - Signals-to-RxJS Interop Abstractions                                                |
| - Functional HTTP Interceptors (Idempotency, Token Refresh, Resilient Retry)          |
| - Headless Component Design System via Directive Composition API                      |
+---------------------------------------------------------------------------------------+
```

1. **Host-Remote Micro-Frontend Federation**:
   - Monorepo NX yang memisahkan aplikasi menjadi `shell` (Host), `telemetry-mfe` (Remote 1), dan `governance-mfe` (Remote 2) menggunakan **Native Federation** berbasis ES Modules.
   - Pemuatan modul remote secara lazy menggunakan token keamanan dinamis dan fallback UI instan jika remote server tidak tersedia.

2. **Zoneless State & High-Frequency Streaming**:
   - Seluruh pipeline rendering dijalankan dalam konfigurasi `provideExperimentalZonelessChangeDetection()`.
   - Modul telemetri menangani konsumsi data WebSocket berfrekuensi tinggi (50-100 pesan/detik), di-buffer menggunakan RxJS operator, lalu disalurkan secara efisien ke primitif Signal untuk merender grafik metrik infrastruktur tanpa memicu thrashing render frame.

3. **Enterprise Dynamic Governance Engine (Forms & Validation)**:
   - Modul tata kelola menyajikan dynamic policy editor yang dirender secara programmatic via schema model JSON (Zod-validated).
   - Mengintegrasikan form validasi asynchronous kustom untuk verifikasi kuota infrastruktur cloud secara live dengan mekanisme auto-cancellation (*race-condition prevention*).

4. **SSR, Hydration & Security Compliance**:
   - Host shell dirender di sisi server menggunakan engine SSR modern.
   - Hidrasi komponen menggunakan `provideClientHydration(withEventReplay(), withHttpTransferCacheOptions(...))` untuk menjamin nol kedipan layar (*zero-flicker UI*).
   - Pengaturan header keamanan ketat: implementasi CSP (Content Security Policy) ketat tanpa injeksi inline scripts yang tidak aman, sanitasi DOM berbasis platform, dan isolasi token sesi.

5. **Kriteria Kesiapan Produksi (*Production Readiness Checklist*)**:
   - Skor Lighthouse Performance: **>= 95** pada koneksi throttling 4G.
   - Ukuran Initial Bundle Host: **< 120 kB gzip**.
   - Zero Memory Leaks: Diverifikasi melalui pengujian profiler alokasi Heap Snapshot di Chrome DevTools selama 30 menit sesi aktif.
   - Strict TypeScript: `noImplicitAny: true`, `strictNullChecks: true`, dan `noUnusedLocals: true`.

---

## 5. Panduan Berkontribusi & Standar Kode
Setiap modul di repositori ini disertai dengan panduan implementasi kode sumber konkret, skenario error produksi nyata (*common pitfalls*), dan benchmark arsitektur. Ikuti struktur penamaan file berbasis kebab-case dan pastikan seluruh demonstrasi kode mengacu pada standar Angular modern tanpa ketergantungan pada modul warisan.