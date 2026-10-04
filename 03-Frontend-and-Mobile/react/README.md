# Kurikulum Arsitektur Enterprise React: Zero to Production Masterclass

Selamat datang di kurikulum rekayasa perangkat lunak enterprise berbasis **React**. Kurikulum ini dirancang untuk mencetak *Frontend Engineer* dan *UI Architect* berstandar industri kelas dunia yang menguasai ekosistem React modern (React 18 & React 19) dari level mekanika internal *runtime* hingga orkestrasi arsitektur skala besar (*large-scale production systems*).

---

## 1. Course Overview & Mindset

### Engineering Mindset: Declarative UI, Reconciliation, & Predictability
React bukan sekadar library UI; React adalah sebuah paradigma komputasi berbasis deklaratif (*Declarative State-Driven UI*). Model mental fundamental yang harus dikuasai oleh seorang insinyur React:

$$\text{UI} = f(\text{state})$$

Di mana:
- **Purity & Idempotency:** Fungsi render komponen harus deterministik dan bebas *side-effect* yang tidak terkontrol.
- **Unidirectional Data Flow:** Data mengalir ke bawah (*props down*), event mengalir ke atas (*events up*), memastikan keterlacakan (*traceability*) mutasi aplikasi.
- **Fiber Engine & Concurrent Scheduler:** Memahami cara kerja *cooperative multitasking*, pemilahan prioritas pembaruan (*priority-based rendering*), dan teknik *virtual reconciliation* untuk menghindari *blocking* pada *main thread*.
- **Client State vs. Server State Separation:** Memutus ketergantungan buruk pada *fat client stores* dengan memisahkan *server cache synchronization* secara tegas dari *ephemeral local UI state*.

Kurikulum ini menolak pendekatan rekayasa berbasis *trial-and-error*. Anda akan diajak membedah *call stack*, menganalisis alokasi heap memori, memitigasi *unnecessary re-renders*, dan merancang sistem antarmuka yang tahan uji (*fault-tolerant*), dapat diuji (*testable*), dan siap melayani puluhan juta pengguna.

---

## 2. Learning Roadmap

```text
========================================================================================
                      REACT ENTERPRISE ARCHITECTURE ROADMAP
========================================================================================
                                       [START]
                                          │
 ┌────────────────────────────────────────┴────────────────────────────────────────────┐
 │  Bab 01: Core Foundations, JSX, & React Fiber Engine                                │
 │  ├── 01.1 JSX Transpilation, Virtual DOM, & Fiber Tree Mechanics                    │
 │  ├── 01.2 Declarative Mental Model & Purity Constraints                             │
 │  └── 01.3 Component Anatomy, Props Contracts, & Children Composition               │
 └────────────────────────────────────────┬────────────────────────────────────────────┘
                                          │
 ┌────────────────────────────────────────┴────────────────────────────────────────────┐
 │  Bab 02: State Primitives & Re-render Lifecycle                                     │
 │  ├── 02.1 useState Internals, Immutability, & Automatic Batching                    │
 │  ├── 02.2 Complex State Machine via useReducer & State Lifting Strategies           │
 │  └── 02.3 Derived State & Anti-pattern Synchronization Hazards                      │
 └────────────────────────────────────────┬────────────────────────────────────────────┘
                                          │
 ┌────────────────────────────────────────┴────────────────────────────────────────────┐
 │  Bab 03: Side Effects, Refs, & Imperative Interop Boundary                          │
 │  ├── 03.1 useEffect Lifecycles, Cleanup Phasing, & Race Condition Mitigation        │
 │  ├── 03.2 useLayoutEffect vs useEffect & DOM Paint Pipeline                        │
 │  └── 03.3 useRef, Imperative Handle, & Third-Party Library Integration Boundaries  │
 └────────────────────────────────────────┬────────────────────────────────────────────┘
                                          │
 ┌────────────────────────────────────────┴────────────────────────────────────────────┐
 │  Bab 04: Advanced Component Patterns & Headless UI Architecture                     │
 │  ├── 04.1 Compound Components & Context Provider Pattern                            │
 │  ├── 04.2 Control Props, Inversion of Control, & Headless Design System             │
 │  └── 04.3 Custom Hooks Architecture: Encapsulation & Reusability Contracts          │
 └────────────────────────────────────────┬────────────────────────────────────────────┘
                                          │
 ┌────────────────────────────────────────┴────────────────────────────────────────────┐
 │  Bab 05: Performance Engineering, Profiling, & Concurrent Scheduling                │
 │  ├── 05.1 Memoization Mechanics: memo, useMemo, & useCallback Internals             │
 │  ├── 05.2 Profiler API, React DevTools, & Flamegraph Bottleneck Analysis            │
 │  └── 05.3 Concurrent Features: useTransition, useDeferredValue, & Virtualization    │
 └────────────────────────────────────────┬────────────────────────────────────────────┘
                                          │
 ┌────────────────────────────────────────┴────────────────────────────────────────────┐
 │  Bab 06: Data Synchronization & Enterprise State Management                         │
 │  ├── 06.1 Server State Synchronization with TanStack Query                          │
 │  ├── 06.2 Pragmatic Global Client State with Zustand                                │
 │  └── 06.3 Context vs External Store: Mitigating Tearing via useSyncExternalStore   │
 └────────────────────────────────────────┬────────────────────────────────────────────┘
                                          │
 ┌────────────────────────────────────────┴────────────────────────────────────────────┐
 │  Bab 07: Routing Architecture, Code-Splitting, & Code Organization                  │
 │  ├── 07.1 Declarative Client Routing & Data Loaders with React Router               │
 │  ├── 07.2 Granular Code Splitting: Suspense, Error Boundaries, & Dynamic Imports   │
 │  └── 07.3 Feature-Sliced Design (FSD) & Scalable Monorepo Directory Architecture    │
 └────────────────────────────────────────┬────────────────────────────────────────────┘
                                          │
 ┌────────────────────────────────────────┴────────────────────────────────────────────┐
 │  Bab 08: Enterprise Form Systems & Mutation Workflows                               │
 │  ├── 08.1 Uncontrolled Forms with React Hook Form & Zod Schema Validation           │
 │  ├── 08.2 Optimistic Updates & Rollback Strategies                                 │
 │  └── 08.3 Modern React Actions: useActionState, useFormStatus, & useOptimistic      │
 └────────────────────────────────────────┬────────────────────────────────────────────┘
                                          │
 ┌────────────────────────────────────────┴────────────────────────────────────────────┐
 │  Bab 09: Enterprise Testing Strategy: Unit, Integration, & E2E                      │
 │  ├── 09.1 Unit & Integration Testing via Vitest & React Testing Library (RTL)       │
 │  ├── 09.2 Mocking Network Layer via Mock Service Worker (MSW)                       │
 │  └── 09.3 End-to-End User Journeys & Visual Regression with Playwright              │
 └────────────────────────────────────────┬────────────────────────────────────────────┘
                                          │
 ┌────────────────────────────────────────┴────────────────────────────────────────────┐
 │  Bab 10: Server-Driven Paradigms & React Server Components (RSC)                    │
 │  ├── 10.1 React Server Components Architecture: Server vs Client Boundaries         │
 │  ├── 10.2 Streaming SSR, Progressive Hydration, & Selective Hydration               │
 │  └── 10.3 Next.js / Modern Meta-framework Integration Fundamentals                 │
 └────────────────────────────────────────┬────────────────────────────────────────────┘
                                          │
                                       [FINISH]
                         -> Enterprise Capstone Project <-
```

---

## 3. Navigasi Detail Modul Kurikulum

### [Bab 01: Core Foundations, JSX, & React Fiber Engine](./01-core-foundations-and-fiber/README.md)
Membedah arsitektur internal React: dari transpiler JSX hingga struktur *singly-linked list* pada React Fiber.
- [01.1 Transpilasi JSX, Virtual DOM, dan Mekanisme Fiber Tree](./01-core-foundations-and-fiber/01-jsx-vdom-fiber.md)
- [01.2 Model Mental Deklaratif, Deterministik, dan Batasan Kemurnian Komponen](./01-core-foundations-and-fiber/02-declarative-mental-model.md)
- [01.3 Anatomi Komponen, Kontrak Props, dan Komposisi Children](./01-core-foundations-and-fiber/03-component-anatomy-composition.md)

### [Bab 02: State Primitives & Re-render Lifecycle](./02-state-primitives-and-lifecycle/README.md)
Eksplorasi mendalam siklus hidup rendering React, rekayasa mutasi *state* secara *immutable*, dan orkestrasi *batching*.
- [02.1 Internal useState, Prinsip Immutability, dan Automatic Batching](./02-state-primitives-and-lifecycle/01-usestate-batching.md)
- [02.2 Finite State Machine via useReducer dan Strategi Lifting State Up](./02-state-primitives-and-lifecycle/02-usereducer-state-lifting.md)
- [02.3 Derived State dan Bahaya Anti-Pattern Duplikasi State](./02-state-primitives-and-lifecycle/03-derived-state-hazards.md)

### [Bab 03: Side Effects, Refs, & Imperative Interop Boundary](./03-effects-refs-and-interop/README.md)
Menguasai sinkronisasi sistem eksternal tanpa melanggar siklus render deklaratif.
- [03.1 Lifecycle useEffect, Mekanika Cleanup, dan Penanganan Race Condition](./03-effects-refs-and-interop/01-useeffect-cleanup-race-conditions.md)
- [03.2 useLayoutEffect vs useEffect: Pipeline Painting DOM dan Layout Thrashing](./03-effects-refs-and-interop/02-uselayouteffect-dom-pipeline.md)
- [03.3 useRef, useImperativeHandle, dan Isolasi Boundary DOM Pihak Ketiga](./03-effects-refs-and-interop/03-useref-imperative-boundaries.md)

### [Bab 04: Advanced Component Patterns & Headless UI Architecture](./04-component-patterns-and-headless-ui/README.md)
Membangun *Design System* enterprise yang *scalable*, *reusable*, dan *accessible*.
- [04.1 Compound Components Pattern dan Context Provider Orchestration](./04-component-patterns-and-headless-ui/01-compound-components.md)
- [04.2 Control Props, Inversion of Control (IoC), dan Headless Design Patterns](./04-component-patterns-and-headless-ui/02-control-props-headless.md)
- [04.3 Rekayasa Custom Hooks: Abstraksi Logika Bisnis & Isolasi Stateful](./04-component-patterns-and-headless-ui/03-custom-hooks-architecture.md)

### [Bab 05: Performance Engineering, Profiling, & Concurrent Scheduling](./05-performance-and-concurrency/README.md)
Optimasi performa tingkat lanjut, isolasi *hot-path rendering*, dan pemanfaatan *Concurrent Scheduler*.
- [05.1 Mekanisme Memoization: Bedah Internal memo, useMemo, dan useCallback](./05-performance-and-concurrency/01-memoization-internals.md)
- [05.2 Profiler API, React DevTools, dan Analisis Flamegraph Bottleneck](./05-performance-and-concurrency/02-profiling-and-flamegraphs.md)
- [05.3 Concurrent Mode: useTransition, useDeferredValue, dan List Virtualization](./05-performance-and-concurrency/03-concurrent-virtualization.md)

### [Bab 06: Data Synchronization & Enterprise State Management](./06-data-sync-and-state-management/README.md)
Strategi integrasi data asynchronous, *caching layer*, dan isolasi state global vs server.
- [06.1 Server State Synchronization dan Cache Invalidation dengan TanStack Query](./06-data-sync-and-state-management/01-tanstack-query-synchronization.md)
- [06.2 Global Client State Store Skala Besar menggunakan Zustand](./06-data-sync-and-state-management/02-zustand-architecture.md)
- [06.3 Context API vs External Stores: Mengatasi State Tearing via useSyncExternalStore](./06-data-sync-and-state-management/03-usesyncexternalstore-tearing.md)

### [Bab 07: Routing Architecture, Code-Splitting, & Code Organization](./07-routing-splitting-architecture/README.md)
Struktur arsitektur navigasi, isolasi kesalahan (*error containment*), dan modularitas basis kode.
- [07.1 Client-Side Routing, Route Loaders, dan Actions dengan React Router](./07-routing-splitting-architecture/01-react-router-loaders.md)
- [07.2 Granular Code Splitting: Suspense Boundaries, Error Boundaries, dan Dynamic Chunking](./07-routing-splitting-architecture/02-suspense-error-boundaries.md)
- [07.3 Feature-Sliced Design (FSD) dan Skalabilitas Arsitektur Monorepo](./07-routing-splitting-architecture/03-fsd-monorepo-patterns.md)

### [Bab 08: Enterprise Form Systems & Mutation Workflows](./08-forms-and-mutations/README.md)
Menangani alur input pengguna yang kompleks, validasi berkinerja tinggi, dan mutasi optimistik.
- [08.1 Uncontrolled Form Architecture dengan React Hook Form dan Skema Zod](./08-forms-and-mutations/01-react-hook-form-zod.md)
- [08.2 Pola Mutasi Optimistik, State Rollback, dan Konflik Konkurensi Jaringan](./08-forms-and-mutations/02-optimistic-mutations-rollback.md)
- [08.3 Primitive React 19: useActionState, useFormStatus, dan useOptimistic Action Workflow](./08-forms-and-mutations/03-react19-action-primitives.md)

### [Bab 09: Enterprise Testing Strategy: Unit, Integration, & E2E](./09-enterprise-testing-strategy/README.md)
Memastikan ketahanan sistem melalui piramida pengujian otomatis berstandar *production-grade*.
- [09.1 Unit & Integration Component Testing menggunakan Vitest dan React Testing Library](./09-enterprise-testing-strategy/01-vitest-rtl-fundamentals.md)
- [09.2 Mocking Jaringan Komprehensif dengan Mock Service Worker (MSW)](./09-enterprise-testing-strategy/02-msw-network-mocking.md)
- [09.3 End-to-End User Flow, Critical Path Testing, dan Visual Diffing via Playwright](./09-enterprise-testing-strategy/03-playwright-e2e-testing.md)

### [Bab 10: Server-Driven Paradigms & React Server Components (RSC)](./10-server-components-and-ssr/README.md)
Memahami transisi modern dari SPA murni menuju arsitektur *hybrid client-server rendering*.
- [10.1 Arsitektur React Server Components: Boundary 'use client' vs 'use server'](./10-server-components-and-ssr/01-rsc-architecture-boundaries.md)
- [10.2 Streaming SSR, Progressive Hydration, dan Selektif Hydration Engine](./10-server-components-and-ssr/02-streaming-ssr-hydration.md)
- [10.3 Paradigma Meta-Framework Modern (Next.js App Router & Remix Architecture)](./10-server-components-and-ssr/03-metaframework-deep-dive.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title:
**ApexTrading: Real-time Multi-Asset Portfolio & Algorithmic Execution Terminal**

### Deskripsi Sistem
ApexTrading adalah *mission-critical trading terminal* berbasis web yang menangani pemantauan harga saham dan kripto secara real-time via WebSockets, eksekusi order multi-leg, analisis grafik interaktif dengan volume data tinggi, serta konfigurasi analitik portofolio yang dapat disesuaikan secara dinamis. Proyek ini mengintegrasikan seluruh materi teknis dari Bab 01 hingga Bab 10.

```text
                                APEXTRADING SYSTEM TOPOLOGY
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              BROWSER / CLIENT RUNTIME                                  │
│                                                                                        │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │                      TanStack Query + Zustand Sync Layer                       │   │
│   │   ┌───────────────────────────────┐        ┌───────────────────────────────┐   │   │
│   │   │   Real-time Orderbook Cache   │        │     Client Workspace State    │   │   │
│   │   │    (WebSocket / Shared Worker)│        │   (Tabs, Active Filters, UI)  │   │   │
│   │   └──────────────┬────────────────┘        └──────────────┬────────────────┘   │   │
│   └──────────────────┼────────────────────────────────────────┼────────────────────┘   │
│                      │                                        │                        │
│   ┌──────────────────▼────────────────────────────────────────▼────────────────────┐   │
│   │                    Concurrent Rendering & UI Virtualization                    │   │
│   │   ┌─────────────────────────┐ ┌──────────────────────────┐ ┌───────────────┐   │   │
│   │   │ Virtualized Tick Stream │ │ Canvas / Chart Subsystem │ │ Action Forms  │   │   │
│   │   │ (useTransition / Window)│ │ (useLayoutEffect / RAF)  │ │ (RHF + Zod)   │   │   │
│   │   └─────────────────────────┘ └──────────────────────────┘ └───────────────┘   │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────┬───────────────────▲─────────────────────────────┘
                                       │                   │
                  HTTPS Mutations / REST                   │ Real-time Binary / JSON Streams
                                       │                   │
┌──────────────────────────────────────▼───────────────────┴─────────────────────────────┐
│                           EDGE API GATEWAY / BACKEND ENGINE                            │
│    - Streaming Server Side Rendering (SSR) Node Instance                               │
│    - WebSocket Feed: Market Orderbook & Trade Telemetry Engine                         │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Arsitektur & Spesifikasi Teknis Wajib:
1. **Concurrency & Performance Budget:**
   - Terminal harus mempertahankan frame rate konstan **60 FPS** ketika menerima pembaruan data streaming WebSocket dengan throughput minimal **100 ticks/detik**.
   - Implementasi `useTransition` dan `useDeferredValue` untuk mencegah UI blocking saat memfilter 50.000+ riwayat transaksi.
   - List transaksi menggunakan teknik DOM Virtualization (`@tanstack/react-virtual`).
   - *Bundle Size:* Main bundle JS awal $\le 120\text{ KB}$ (gzipped) melalui dynamic dynamic code-splitting dan route-level lazy loading.

2. **State Management & Data Synchronization:**
   - **Server State:** TanStack Query untuk REST/GraphQL fetching, pagination, caching, dan stale-while-revalidate strategy.
   - **Real-time Engine:** Custom React Hook yang mengorkestrasi WebSocket native dengan auto-reconnect, heartbeat, dan buffer queue untuk streaming orderbook.
   - **Global Client State:** Zustand untuk interaksi layout antarmuka (docking panel, active theme, multi-tab terminal state) dengan optimasi *atomic selectors* untuk mencegah unnecessary re-renders.

3. **Form Architecture & Optimistic Actions:**
   - Formulir eksekusi order instan dengan validasi schema kompleks (kondisi *Stop-Loss*, *Take-Profit*, *Leverage Slider*) menggunakan React Hook Form dan Zod.
   - Menggunakan paradigma modern React Actions (`useActionState` dan `useOptimistic`) untuk memberikan *instant visual feedback* saat menempatkan order baru, dengan otomatisasi *rollback handling* jika server menolak transaksi.

4. **Reliability & Enterprise Testing Strategy:**
   - **Code Coverage Minimum:** Total Line Coverage $\ge 85\%$.
   - **Unit & Integration:** Menguji Custom Hooks isolasi dan komponen headless menggunakan Vitest & React Testing Library (menguji fungsionalitas dari sudut pandang interaksi aksesibilitas ARIA).
   - **Network Mocking:** Seluruh network interaction (REST & WebSocket) wajib disimulasikan menggunakan Mock Service Worker (MSW).
   - **End-to-End (E2E):** Suite pengujian Playwright mencakup *Critical User Path*: Auth Flow $\rightarrow$ Workspace Customization $\rightarrow$ Order Placement $\rightarrow$ Optimistic Verification $\rightarrow$ History Log Confirmation.

5. **Codebase Architecture:**
   - Direktori terstruktur menggunakan pendekatan **Feature-Sliced Design (FSD)**:
     ```text
     src/
     ├── app/              # Application layer (Providers, Router, Global styles)
     ├── processes/        # Cross-feature workflows (Authentication, Checkout)
     ├── pages/            # View routes with loaders and suspense boundaries
     ├── widgets/          # Self-contained UI assemblies (OrderBookPanel, ChartWidget)
     ├── features/         # User interactions with business value (ExecuteOrder, FilterTicks)
     ├── entities/         # Domain models and business data (Order, Trade, Instrument)
     └── shared/           # Reusable UI primitives, hooks, API clients, utilities
     ```

### Deliverables Capstone Project:
1. **Source Code Repository:** Monorepo/Polyrepo clean architecture lengkap dengan konfigurasi TypeScript *Strict Mode* tanpa penggunaan tipe `any`.
2. **Architecture Decision Records (ADR):** Dokumen teknis yang merinci alasan pemilihan library, trade-off arsitektur state management, dan mitigasi bottleneck memori.
3. **Lighthouse CI & Profiler Report:** Skor Web Vitals minimal: LCP $< 1.8\text{s}$, FID/INP $< 100\text{ms}$, CLS $< 0.05$ pada pengujian CPU throttling 4x.
4. **Automated CI/CD Pipeline:** GitHub Actions workflow yang menjalankan Linter, Type Check, Vitest Suite, dan Playwright E2E secara otomatis sebelum merge ke branch `main`.