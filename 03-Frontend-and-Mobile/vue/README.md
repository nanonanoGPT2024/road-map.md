Berikut adalah draf lengkap file `README.md` kurikulum enterprise untuk roadmap Vue.js sesuai dengan standar arsitektur GEMINI.md.

---

# Enterprise Vue.js Engineering: From Reactivity Internals to Large-Scale Architecture

Selamat datang di repositori kurikulum resmi **Enterprise Vue.js Engineering**. Silabus ini dirancang oleh Senior Technical Curriculum Architect untuk mentransformasi *frontend developer* menjadi *lead engineer* yang menguasai ekosistem Vue 3 secara mendalam, berbasis standar industri modern, performa tinggi, dan ketahanan arsitektur skala besar.

---

## 1. Course Overview & Mindset

### Filosofi Kurikulum
Vue 3 bukan sekadar *view library*; ia adalah ekosistem progresif berkinerja tinggi yang dibangun di atas fondasi reaktivitas mutakhir berbasis ES6 `Proxy`. Kurikulum ini dirancang dengan pendekatan **Zero-Magic & Production-First**:
*   **Deep-Dive Internals:** Memahami bagaimana Virtual DOM, compiler optimizations (patch flags, shape flags), dan reactivity core bekerja di balik layar, bukan hanya menghafal sintaksis API.
*   **Composition API & Scalable Composables:** Menghindari jebakan Options API legacy dengan mengadopsi Composition API tingkat lanjut (`<script setup>`) untuk modularitas kode, reusabilitas logika tipe-aman (*type-safe*), dan isolasi *side-effects*.
*   **Enterprise Tooling & TypeScript:** Menggunakan ekosistem Vite, Vitest, Pinia, dan TypeScript secara ketat (*strict mode*) untuk menjamin skalabilitas basis kode tim skala menengah hingga enterprise.
*   **Resilience & Performance:** Fokus pada optimasi runtime, reduksi ukuran bundle (*tree-shaking*), rendering hybrid (Nuxt 3), serta strategi caching dan arsitektur pengujian menyeluruh (Unit, Component, E2E).

---

## 2. Learning Roadmap

```text
Ecosistem Enterprise Vue.js
│
├── [BAB 01] Fondasi Vue 3, Arsitektur Reaktivitas, & Tooling Modern
│     │
│     └── [BAB 02] Composition API & Custom Composables In-Depth
│           │
│           └── [BAB 03] Directives, Template Engine, & DOM Manipulation
│                 │
│                 └── [BAB 04] Component Architecture & Contract Patterns
│                       │
│                       └── [BAB 05] Client-Side Routing Enterprise (Vue Router 4)
│                             │
│                             └── [BAB 06] State Management Skala Besar (Pinia)
│                                   │
│                                   └── [BAB 07] Asynchronous Flow, Forms, & Data Fetching
│                                         │
│                                         └── [BAB 08] Built-in Components, Transitions, & UX
│                                               │
│                                               └── [BAB 09] Enterprise Testing Strategy (Vitest & Playwright)
│                                                     │
│                                                     └── [BAB 10] Performance, SSR/Nuxt 3, & Production Hardening
│                                                           │
│                                                           └── [CAPSTONE PROJECT] Multi-Tenant SaaS Platform
```

---

## 3. Navigasi Silabus

### [Bab 01: Fondasi Vue 3, Arsitektur Reaktivitas, & Tooling Modern](./01-fondasi-vue-dan-reaktivitas/README.md)
*Membedah mekanisme internal Vue 3 reactivity engine, evolusi dari Vue 2, dan modern tooling orchestration.*
*   [01.1 Arsitektur Reaktivitas: Proxy vs Object.defineProperty](./01-fondasi-vue-dan-reaktivitas/01-arsitektur-reaktivitas-proxy-vs-define-property.md)
*   [01.2 Vite Tooling, Hot Module Replacement (HMR), & Single File Component (SFC) Compiler](./01-fondasi-vue-dan-reaktivitas/02-vite-tooling-hmr-dan-sfc-compiler.md)
*   [01.3 Integrasi TypeScript Strict-Mode & Volar Ecosystem Setup](./01-fondasi-vue-dan-reaktivitas/03-integrasi-typescript-strict-dan-volar.md)

### [Bab 02: Composition API & Custom Composables In-Depth](./02-composition-api-dan-composables/README.md)
*Penguasaan Composition API secara idiomatis, lifecycle hooks, dan perancangan stateful logic headless.*
*   [02.1 Primitive Reactivity: ref, reactive, toRefs, shallowRef, dan triggerRef](./02-composition-api-dan-composables/01-primitive-reactivity-ref-reactive-shallow.md)
*   [02.2 Computed Properties & Watchers Execution Pipeline (watch vs watchEffect)](./02-composition-api-dan-composables/02-computed-dan-watchers-execution-pipeline.md)
*   [02.3 Pola Perancangan Enterprise Headless Composables (VueUse Paradigm)](./02-composition-api-dan-composables/03-pola-perancangan-headless-composables.md)

### [Bab 03: Directives, Template Engine, & DOM Manipulation](./03-directives-template-dan-dom/README.md)
*Mekanisme template compilation, custom directives tingkat lanjut, dan integrasi DOM interop.*
*   [03.1 Compiler Internals: Patch Flags, Hoisting, dan Block Trees](./03-directives-template-dan-dom/01-compiler-internals-patch-flags-hoisting.md)
*   [03.2 Advanced Built-in Directives & Deep Two-Way Binding (`v-model` modifier chains)](./03-directives-template-dan-dom/02-built-in-directives-dan-custom-v-model.md)
*   [03.3 Custom Directives Lifecycle & Integrasi Non-Vue 3rd Party Libraries](./03-directives-template-dan-dom/03-custom-directives-dan-non-vue-libraries.md)

### [Bab 04: Component Architecture & Contract Patterns](./04-component-architecture-and-contracts/README.md)
*Perancangan komponen modular dengan strong typing, event contracts, dynamic injection, dan slots pattern.*
*   [04.1 Interface Contracts: Generic Components, Typed Props, dan Typed Emits](./04-component-architecture-and-contracts/01-typed-props-emits-generic-components.md)
*   [04.2 Advanced Content Projection: Scoped Slots, Dynamic Slots, & Render Functions](./04-component-architecture-and-contracts/02-scoped-slots-dynamic-slots-dan-jsx.md)
*   [04.3 Dependency Injection Skala Besar: Provide/Inject dengan InjectionKey Symbols](./04-component-architecture-and-contracts/03-dependency-injection-injection-key-symbols.md)

### [Bab 05: Client-Side Routing Enterprise (Vue Router 4)](./05-vue-router-enterprise/README.md)
*Manajemen navigasi terdistribusi, dynamic code-splitting, role-based access control (RBAC), dan scroll orchestration.*
*   [05.1 Arsitektur Rute: Nested Routes, Dynamic Path Matching, dan Route Aliasing](./05-vue-router-enterprise/01-nested-routes-dan-dynamic-path-matching.md)
*   [05.2 Multi-Stage Navigation Guards, Auth Pipelines, & Route Metadata RBAC](./05-vue-router-enterprise/02-navigation-guards-auth-pipeline-rbac.md)
*   [05.3 Dynamic Routing Extension, Data Loaders Pattern, & Chunk Optimization](./05-vue-router-enterprise/03-dynamic-routing-data-loaders-chunk-optimization.md)

### [Bab 06: State Management Skala Besar (Pinia)](./06-state-management-pinia/README.md)
*Manajemen global state yang modular, fully typed, SSR-compatible, serta terintegrasi dengan middleware/plugins.*
*   [06.1 Store Topology: Option Stores vs Setup Stores & Domain Isolation](./06-state-management-pinia/01-store-topology-option-vs-setup-stores.md)
*   [06.2 Subscriptions, Actions Interception, dan Custom Pinia Plugins](./06-state-management-pinia/02-subscriptions-action-interception-pinia-plugins.md)
*   [06.3 Normalisasi State Relasional, Local Persistence, & Multi-Tab Sync](./06-state-management-pinia/03-normalisasi-state-persistence-multi-tab-sync.md)

### [Bab 07: Asynchronous Flow, Forms, & Data Fetching](./07-async-flow-forms-dan-data-fetching/README.md)
*Orkestrasi asynchronous data, server-state caching, serta validasi form kompleks berbasis skema.*
*   [07.1 Server State Synchronization dengan TanStack Query (Vue Query)](./07-async-flow-forms-dan-data-fetching/01-server-state-tanstack-vue-query.md)
*   [07.2 Complex Form Orchestration: Vee-Validate, Zod Schema, dan Dynamic Fields](./07-async-flow-forms-dan-data-fetching/02-vee-validate-zod-dynamic-forms.md)
*   [07.3 Error Handling Boundaries, Async Components, dan `<Suspense>` Execution](./07-async-flow-forms-dan-data-fetching/03-error-boundaries-async-components-suspense.md)

### [Bab 08: Built-in Components, Transitions, & UX Orchestration](./08-builtin-components-dan-ux/README.md)
*Optimalisasi performa view rendering dinamis, modal portals, state preservation, dan animasi tingkat lanjut.*
*   [08.1 Layout Performance: `<KeepAlive>` Caching Strategy & Lifecycle Hooks](./08-builtin-components-dan-ux/01-keep-alive-caching-strategy-lifecycle.md)
*   [08.2 Sub-DOM Portals: `<Teleport>` untuk Modal Hierarchies & Overlay Management](./08-builtin-components-dan-ux/02-teleport-modal-hierarchies-overlay.md)
*   [08.3 Visual Continuity: `<Transition>` & `<TransitionGroup>` dengan Web Animations API](./08-builtin-components-dan-ux/03-transition-transition-group-web-animations.md)

### [Bab 09: Enterprise Testing Strategy (Vitest & Playwright)](./09-enterprise-testing-strategy/README.md)
*Strategi pengujian komprehensif mengikuti piramida testing modern tanpa false-positives.*
*   [09.1 Unit Testing Pure Composables & Reactive State Menggunakan Vitest](./09-enterprise-testing-strategy/01-unit-testing-composables-vitest.md)
*   [09.2 Component Integration Testing: Vue Test Utils & Testing Library](./09-enterprise-testing-strategy/02-component-testing-vue-test-utils.md)
*   [09.3 End-to-End (E2E) Flow Testing & Visual Regression Menggunakan Playwright](./09-enterprise-testing-strategy/03-e2e-testing-visual-regression-playwright.md)

### [Bab 10: Performance, SSR/Nuxt 3, & Production Hardening](./10-performance-nuxt-production-hardening/README.md)
*Optimasi performa ekstrim, rendering hybrid server-side, audit security, serta automasi pipeline deployment.*
*   [10.1 Rendering Internals: Hydration Mismatch, Virtual List, & Memory Leaks Audit](./10-performance-nuxt-production-hardening/01-hydration-virtual-list-memory-leaks.md)
*   [10.2 Transisi ke Nuxt 3: Server-Side Rendering (SSR), SSG, ISR, dan Nitro Engine](./10-performance-nuxt-production-hardening/02-nuxt3-ssr-ssg-isr-nitro-engine.md)
*   [10.3 Bundle Size Optimization, Security Hardening (CSP, XSS), & CI/CD Pipeline](./10-performance-nuxt-production-hardening/03-bundle-optimization-security-cicd.md)

---

## 4. Capstone Project: Enterprise Multi-Tenant Cloud Platform

### Gambaran Proyek
Sebagai syarat kelulusan kurikulum, peserta wajib merancang dan mengimplementasikan **"PulseFlow"**: Sistem Manajemen Observabilitas Cloud & Marketplace Terdistribusi Multi-Tenant. Aplikasi ini mensimulasikan dashboard operasional dengan beban data tinggi, throughput pembaruan real-time cepat, serta isolasi data multi-penyewa (*multi-tenant*).

### Arsitektur Teknis
```text
[ Browser Client ]
       │
       ├── Core: Vue 3 (v3.4+) + TypeScript (Strict) + Vite
       ├── State Hub: Pinia (Setup Stores) + Normalized Cache (TanStack Query)
       ├── Routing: Vue Router 4 (Guards + Dynamic RBAC Code-Splitting)
       ├── UI Foundation: TailwindCSS + Headless UI + Custom Canvas Composables
       │
[ Real-time Transport: WebSockets + SSE ]
       │
[ API Gateway / Microservices ]
```

### Spesifikasi Wajib & Persyaratan Non-Fungsional

1.  **Arsitektur & Reaktivitas:**
    *   Mengimplementasikan custom canvas chart engine menggunakan composables terspesialisasi yang mampu me-render pembaruan metrik telemetri 60 FPS (1.000 data point/detik) tanpa frame-drop.
    *   Tidak boleh menggunakan sintaks Options API; 100% Composition API dengan `<script setup lang="ts">`.
2.  **Manajemen State & Routing:**
    *   State global diatur secara modular menggunakan Pinia setup-stores, dipisahkan berdasarkan domain: `AuthContext`, `TelemetryStream`, `BillingEngine`, dan `TenantCatalog`.
    *   Implementasi multi-level dynamic RBAC navigation guard yang mengamankan rute berdasarkan subscription tier tenant (Free, Pro, Enterprise).
3.  **Form & Data Validation:**
    *   Formulir provisioning tenant multi-step yang kompleks dengan integrasi `Vee-Validate` + `Zod`, mendukung *field arrays*, dynamic schema validation, dan autosave draft ke IndexedDB.
4.  **Standar Kualitas & Testing:**
    *   Minimum Code Coverage: **85%** pada unit testing composables dan component testing menggunakan **Vitest** dan `@vue/test-utils`.
    *   Skrip testing E2E lengkap menggunakan **Playwright** yang mencakup: alur autentikasi, switching workspace antar-tenant, dan transaksi checkout marketplace.
5.  **Performa & Deployment:**
    *   Lighthouse Performance Score minimum **95+** pada production build.
    *   Zero *Hydration Mismatches* jika dijalankan di atas mode hybrid rendering (Nuxt 3).
    *   Ukuran initial bundle size (gzipped) tidak boleh melebihi **120 KB** (tercapai melalui lazy loading route chunks dan manual chunk splitting via Rollup).

---

## Panduan Kontribusi & Eksekusi

Setiap direktori bab (`01` sampai `10`) memuat modul pembelajaran mendalam beserta latihan kode terstruktur. Peserta diwajibkan menyelesaikan studi kasus mandiri di setiap akhir bab sebelum memprogram Capstone Project. Silakan menuju ke [Bab 01: Fondasi Vue 3, Arsitektur Reaktivitas, & Tooling Modern](./01-fondasi-vue-dan-reaktivitas/README.md) untuk memulai.