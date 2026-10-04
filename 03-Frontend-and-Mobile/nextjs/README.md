```markdown
# Next.js Enterprise Engineering: Architecture, Performance & Scalability

Kurikulum teknis komprehensif ini dirancang untuk mencetak **Principal Frontend Engineer** dan **Next.js Solution Architect**. Kurikulum ini berfokus pada ekosistem Next.js modern (App Router, React Server Components, Server Actions, Partial Prerendering, dan Edge Architecture). Anda akan mempelajari cara membangun aplikasi terdistribusi, *zero-waterfall*, aman dari celah eksploitasi data sensitif, serta teroptimasi untuk beban kerja jutaan pengguna per hari.

---

## 1. Course Overview & Mindset

### The Server-First Mental Model
Next.js dengan arsitektur App Router bukan sekadar *library routing* atau framework Single Page Application (SPA) biasa. Paradigma ini merevolusi komputasi antarmuka melalui pendekatan **Server-First Hybrid Architecture**:

* **Eliminasi Client-Side Waterfalls**: Memindahkan *data fetching* langsung ke tingkat komputasi paling dekat dengan database melalui React Server Components (RSC) tanpa membengkakkan ukuran bundle JavaScript di sisi klien.
* **Granular Revalidation vs. Over-fetching**: Mengganti pembaruan cache berbasis waktu konvensional dengan *Cache Tags*, *Path-based Invalidation*, dan optimasi 4 tingkat layer cache Next.js.
* **Zero-Bundle-Cost Abstractions**: Mengembalikan *data-heavy logic*, parser markdown/HTML, enkripsi, dan integrasi library enterprise ke Node.js/Edge server. Klien hanya menerima representasi stream Virtual DOM (RSC payload) dan HTML murni.
* **Unified Mutation Lifecycle**: Menghapus boilerplate REST API endpoints untuk mutasi sederhana melalui **Server Actions**, yang terintegrasi langsung dengan React 19 primitives (`useActionState`, `useOptimistic`, `useFormStatus`).

---

## 2. Learning Roadmap

```plaintext
Next.js Enterprise Architecture
│
├── 01. Arsitektur Komputasi & Mental Model App Router
├── 02. Routing Lanjutan, Parallel, & Intercepting Patterns
├── 03. Paradigma Rendering: RSC, Streaming, & Partial Prerendering (PPR)
├── 04. Data Mutation, Server Actions, & Stateful Forms
├── 05. Anatomi Mendalam 4-Tier Caching Pipeline
├── 06. Optimasi Aset, Web Vitals, & Zero-Runtime Overhead
├── 07. Enterprise Security, Identity Management, & RBAC
├── 08. Integrasi Database, Connection Pooling, & Edge Storage
├── 09. Strategi Pengujian End-to-End & Automasi CI/CD
└── 10. Observabilitas, Resiliensi, & Deployment Berskala Besar
```

---

## 3. Navigasi Detail Modul Kurikulum

### [Bab 01: Arsitektur Komputasi & Mental Model App Router](./01-arsitektur-dan-mental-model/)
Membedah dekonstruksi Pages Router menuju App Router, boundary serialisasi RSC, dan siklus eksekusi request.
* [Modul 01: Dekonstruksi Server vs Client Component Boundaries](./01-arsitektur-dan-mental-model/01-server-vs-client-boundaries.md)
  * RSC Payload vs HTML, batasan `use client`, komputasi kompilasi SWC, dan aturan dependensi pohon komponen.
* [Modul 02: Siklus Hidup Eksekusi Request & Server-Side Bootstrapping](./01-arsitektur-dan-mental-model/02-request-lifecycle-and-runtimes.md)
  * Perbedaan runtime `nodejs` vs `edge`, dynamic imports server-side, and memory footprints.
* [Modul 03: Strategi Komposisi Slot: Children, Inversion of Control, & Props Serialization](./01-arsitektur-dan-mental-model/03-composition-patterns.md)
  * Menembus *client barrier* dengan mengalirkan RSC sebagai children, penanganan non-serializable props.

### [Bab 02: Routing Lanjutan, Parallel, & Intercepting Patterns](./02-routing-dan-navigasi-lanjutan/)
Implementasi antarmuka pengguna kompleks, rute paralel bersyarat, modal routing berbasis URL, dan middleware mutakhir.
* [Modul 01: Parallel Routes (`@slot`) dan Kondisional Render Lanjutan](./02-routing-dan-navigasi-lanjutan/01-parallel-routes-and-slots.md)
  * State independent loading, error boundaries per slot, dan default handling pada soft navigation.
* [Modul 02: Intercepting Routes (`(.)`, `(..)`, `(...)`) & URL Synchronization](./02-routing-dan-navigasi-lanjutan/02-intercepting-routes.md)
  * Arsitektur modal foto/detail bergaya Instagram/Twitter, shareable URL state, dan fallback rute langsung.
* [Modul 03: Edge Middleware: Routing Control, Rewrite Engine, & Geo-Targeting](./02-routing-dan-navigasi-lanjutan/03-middleware-internals.md)
  * Runtime limits edge middleware, header manipulation, rate-limiting upstream, dan custom internationalization routing.

### [Bab 03: Paradigma Rendering: RSC, Streaming, & Partial Prerendering (PPR)](./03-paradigma-rendering/)
Menguasai streaming SSR modern, isolasi skeleton, dan arsitektur hibrida teranyar.
* [Modul 01: Streaming Rendering dengan React Suspense & Chunked Transfer](./03-paradigma-rendering/01-streaming-suspense.md)
  * Mekanisme HTTP/1.1 Transfer-Encoding Chunked vs HTTP/2 streaming, prioritas render, dan progressive hydration.
* [Modul 02: Static Shells & Dynamic Holes: Partial Prerendering (PPR)](./03-paradigma-rendering/02-partial-prerendering.md)
  * Implementasi eksperimental PPR, eliminasi kompromi antara static generation (SSG) dan server dynamic runtime (SSR).
* [Modul 03: Resilient Error Boundaries & Global Handling](./03-paradigma-rendering/03-error-boundaries-and-fallbacks.md)
  * Penanganan fatal dynamic render exceptions, degradasi fungsional terkendali via `error.tsx` dan `global-error.tsx`.

### [Bab 04: Data Mutation, Server Actions, & Stateful Forms](./04-mutasi-data-dan-server-actions/)
Menjalankan modifikasi basis data tanpa manual API glue-code secara aman dan terstruktur.
* [Modul 01: Anatomi Server Actions & RPC Under-the-Hood](./04-mutasi-data-dan-server-actions/01-server-actions-internals.md)
  * Protokol POST internal Next.js, hidden action IDs, CORS constraints, dan integrasi form standard web platform.
* [Modul 02: React 19 Action Hooks Integration](./04-mutasi-data-dan-server-actions/02-useactionstate-useoptimistic.md)
  * Mutasi stateful menggunakan `useActionState`, rendering optimistik dengan `useOptimistic`, dan form tracking via `useFormStatus`.
* [Modul 03: Validasi Schema Type-Safe & Sanitasi Input](./04-mutasi-data-dan-server-actions/03-zod-mutation-validation.md)
  * Standardisasi layer validasi berbasis Zod, penanganan file uploads secara aman, dan format error terstruktur.

### [Bab 05: Anatomi Mendalam 4-Tier Caching Pipeline](./05-caching-pipeline-internals/)
Membongkar dan menguasai layer cache tersulit di Next.js untuk skalabilitas tanpa stale state bug.
* [Modul 01: Request Memoization vs Data Cache Engine](./05-caching-pipeline-internals/01-memoization-and-datacache.md)
  * Extended `fetch()`, deduplikasi per request lifecycle, Persistent File-System Cache, dan kustomisasi fetch caching tags.
* [Modul 02: Full Route Cache & Router Cache Invalidation Lifecycle](./05-caching-pipeline-internals/02-route-and-router-cache.md)
  * Menyelaraskan cache di server (Full Route) dan in-memory cache browser (Router Cache); mitigasi *hard refresh* issues.
* [Modul 03: On-Demand Revalidation: Tags, Paths, & Distributed Purging](./05-caching-pipeline-internals/03-revalidation-strategies.md)
  * `revalidatePath` vs `revalidateTag`, webhook cache purge implementation, dan integrasi redis cache handler eksternal.

### [Bab 06: Optimasi Aset, Web Vitals, & Zero-Runtime Overhead](./06-optimasi-performa-dan-assets/)
Mencapai skor Google Lighthouse 100/100 pada aplikasi skala produksi.
* [Modul 01: Advanced Core Web Vitals Optimization (LCP, INP, CLS)](./06-optimasi-performa-dan-assets/01-core-web-vitals.md)
  * Menembus metrik Interaction to Next Paint (INP), memory leak profiling, dan script scheduling strategies.
* [Modul 02: Asset Pipeline Engine: Next/Image, Next/Font, & Next/Script](./06-optimasi-performa-dan-assets/02-asset-optimizations.md)
  * Zero CLS font pre-loading, automatic image transcode (AVIF/WebP), custom image loaders, dan subresource integrity.
* [Modul 03: Bundle Analysis, Dynamic Chunking, & Server Component Decoupling](./06-optimasi-performa-dan-assets/03-bundle-analysis-chunks.md)
  * Audit @next/bundle-analyzer, modularizing large libraries, dan dynamic import deferral strategies.

### [Bab 07: Enterprise Security, Identity Management, & RBAC](./07-enterprise-security-dan-auth/)
Pondasi pertahanan modern terhadap kebocoran informasi server, session hijacking, dan kontrol akses granular.
* [Modul 01: Implementasi Auth.js (NextAuth v5) & Session Strategy Architecture](./07-enterprise-security-dan-auth/01-authjs-v5-implementation.md)
  * JWT vs Database sessions, Edge-compatible auth primitives, dan OAuth 2.0 / SAML Single Sign-On (SSO).
* [Modul 02: Role-Based & Attribute-Based Access Control (RBAC/ABAC)](./07-enterprise-security-dan-auth/02-rbac-and-abac-authorization.md)
  * Multi-tier authorization: Edge middleware routing barrier vs Server Action data-level defense-in-depth.
* [Modul 03: Proteksi Vulnerability: Taint API, CSRF, Nonces, & Content Security Policy (CSP)](./07-enterprise-security-dan-auth/03-security-hardening-csp-taint.md)
  * Eksploitasi isolasi token dengan `experimental_taintUniqueValue`, dynamic nonces untuk inline scripts, dan HTTP hardening headers.

### [Bab 08: Integrasi Database, Connection Pooling, & Edge Storage](./08-database-dan-edge-storage/)
Arsitektur database performa tinggi yang disesuaikan dengan siklus hidup stateless serverless functions.
* [Modul 01: Serverless PostgreSQL & Connection Pooling](./08-database-dan-edge-storage/01-database-pooling-serverless.md)
  * Menghindari kehabisan pool koneksi DB: Prisma Data Proxy, PgBouncer, Neon Serverless Driver, dan Drizzle ORM.
* [Modul 02: Distributed Caching Layer dengan Upstash Redis](./08-database-dan-edge-storage/02-edge-redis-distributed-cache.md)
  * Global rate limiting di Edge, distributed locks untuk mutasi data paralel, dan transient state caching.
* [Modul 03: Streaming File Uploads & Object Storage Architecture](./08-database-dan-edge-storage/03-s3-direct-storage-uploads.md)
  * Signed URLs generation via Server Actions, direct multi-part uploads ke AWS S3/Cloudflare R2 tanpa membebani server memory.

### [Bab 09: Strategi Pengujian End-to-End & Automasi CI/CD](./09-testing-dan-cicd-pipeline/)
Rangkaian validasi otomatis untuk Server Components, Server Actions, dan alur kerja mission-critical.
* [Modul 01: Unit & Component Testing Server/Client Boundaries via Vitest](./09-testing-dan-cicd-pipeline/01-unit-testing-rsc.md)
  * Mocking Next.js headers, async components unit testing, dan isolasi Client Component harness.
* [Modul 02: End-to-End Testing Tingkat Lanjut dengan Playwright](./09-testing-dan-cicd-pipeline/02-playwright-e2e-testing.md)
  * Pengujian state otentikasi terisolasi, revalidasi cache browser assertion, dan visual regression testing.
* [Modul 03: Multi-Stage Dockerfile Optimization & GitHub Actions CI/CD](./09-testing-dan-cicd-pipeline/03-docker-and-github-actions.md)
  * Standalone output tracing Next.js (`output: 'standalone'`), optimasi cache layer Docker, dan deployment automated checks.

### [Bab 10: Observabilitas, Resiliensi, & Deployment Berskala Besar](./10-observabilitas-dan-skalabilitas/)
Mengoperasikan Next.js pada kluster Kubernetes enterprise atau edge fleet dengan telemetri kelas satu.
* [Modul 01: OpenTelemetry Instrumentation & APM Integration](./10-observabilitas-dan-skalabilitas/01-opentelemetry-apm.md)
  * Tracing Next.js internal calls, HTTP request tracing ke database, export data ke Datadog / Grafana Tempo.
* [Modul 02: Centralized Error Monitoring, Sentry, & Structured Logging](./10-observabilitas-dan-skalabilitas/02-sentry-and-structured-logging.md)
  * Source map hidden security, correlation IDs injection via middleware, and structured JSON logs.
* [Modul 03: Multi-Zones Architecture, Micro-frontends, & Self-Hosting Scaling](./10-observabilitas-dan-skalabilitas/03-multi-zones-and-self-hosting.md)
  * Menggabungkan beberapa aplikasi Next.js independen via Multi-Zones, zero-downtime rolling deployment pada Kubernetes cluster.

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title: "OmniChannel B2B Commerce & Wholesale Procurement Engine"

### Arsitektur Sistem
Proyek akhir mengimplementasikan platform e-commerce multi-tenant B2B dengan integrasi katalog volume tinggi, negosiasi kuotasi real-time, dan portal admin tenant terisolasi.

```plaintext
                               [ Client Browser ]
                                       │
                                       ▼
                       [ Cloudflare Edge CDN / WAF ]
                                       │
                                       ▼
                     [ Next.js Edge Middleware Engine ]
                    (Tenant Resolution & RBAC Pre-flight)
                                       │
                   ┌───────────────────┴───────────────────┐
                   ▼                                       ▼
        [ Next.js App Router (Node.js) ]       [ Multi-Zone Micro-Frontend ]
       ├── Static Shells with Dynamic PPR      ├── /analytics (Reporting App)
       ├── Server Actions (Zod Validation)     └── /docs (Edge-rendered Hub)
       ├── Custom Redis Cache Handler
       └── OpenTelemetry Instrumentation
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
[ Serverless Postgres ] [ Upstash Redis ] ──► [ S3 / R2 Asset Bucket ]
  (Drizzle ORM via        (Distributed Cache,
   PgBouncer Pool)         Rate Limiters)
```

### Core Technical Requirements & Production Metrics

1. **Routing & Composition Architecture**:
   * Multi-tenant routing berbasis subdomain (`tenant.omnichannel.com`) yang di-rewrite secara dinamis di Edge Middleware.
   * Intercepting Route untuk preview pesanan wholesale secara instan dalam slide-over modal tanpa kehilangan navigasi URL langsung.
   * Render produk dinamis menggunakan **Partial Prerendering (PPR)**: Header, layout, dan ringkasan statis instan, sementara ketersediaan stok inventaris dan harga negosiasi dialirkan dinamis via Suspense.

2. **Data Ingestion & Server Actions**:
   * Seluruh mutasi keranjang, approval plafon kredit, dan pemesanan batch diproses melalui **Server Actions**.
   * Optimistic UI rendering wajib diaktifkan pada keranjang belanja grosir menggunakan hook `useOptimistic`.
   * Integrasi **Zod schema validation** berlapis dan proteksi serialisasi variabel kredensial via `experimental_taintUniqueValue`.

3. **Enterprise 4-Tier Cache Strategy**:
   * Membangun Custom Redis Cache Handler untuk menggantikan default file-system Data Cache, memungkinkan invalidasi terdistribusi antar kontainer multi-pod.
   * Penggunaan granular Tag-based revalidation (`revalidateTag`) pada setiap pembaruan katalog produk dari webhook sistem ERP.

4. **Testing, Deployment & Observability**:
   * Minimum **85% code coverage** melalui perpaduan Vitest untuk server utilities dan Playwright untuk alur kritis (Checkout & Order Lifecycle).
   * **Multi-Stage Dockerized Build** menghasilkan container image berbasis `alpine` dengan ukuran maksimal 150MB via `output: 'standalone'`.
   * Pipeline OpenTelemetry lengkap yang mengirimkan spans dari Next.js runtime ke OTel Collector.
   * Skor Google Core Web Vitals: **LCP < 1.2s, INP < 100ms, CLS = 0**.

---

## 5. Standar Kontribusi & Panduan Kode

Setiap file modul dalam repositori ini harus memuat:
1. **Mental Model & Background Context**: Penjelasan alasan teknis di balik solusi, bukan sekadar "bagaimana cara kerjanya".
2. **Production-Ready Code Example**: Menggunakan TypeScript mode strict, tanpa komentar pemalas (`// implement here`), dan mencakup error handling.
3. **Anti-Patterns & Pitfalls**: Komparasi implementasi buruk vs implementasi optimal enterprise-grade.
4. **Architectural Trade-offs**: Analisis dampak terhadap konsumsi CPU, memori, network round-trip, dan bundle size.