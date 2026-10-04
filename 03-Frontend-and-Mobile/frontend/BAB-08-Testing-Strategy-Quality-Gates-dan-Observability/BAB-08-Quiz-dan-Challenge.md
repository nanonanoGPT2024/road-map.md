# BAB 08: Quiz, Challenge, & Knowledge Check
**Micro-Frontend Architecture, Module Federation, & Enterprise System Resiliency**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi dan Lifecycle Module Federation Runtime
Jelaskan secara mendalam bagaimana Webpack/Rspack/Vite Module Federation mengeksekusi *handshake* antara **Host Container** dan **Remote Application** di runtime! Secara spesifik:
1. Apa fungsi file `remoteEntry.js`?
2. Bagaimana container `init()` dan container `get()` bekerja dalam memfasilitasi injeksi shared scope?
3. Apa perbedaan fundamental antara dynamic remote resolution (resolusi URL runtime via script injection) dibanding static configuration di level build tool?

### Soal 1.2: Matriks Komposisi Micro-Frontend
Bandingkan secara komparatif tiga paradigma integrasi Micro-Frontend berikut:
*   **Build-time composition** (e.g., npm packages monorepo)
*   **Server-side composition** (e.g., Edge-Side Includes/ESI, Next.js Multi-Zones, Reverse Proxy route stitching)
*   **Client-side runtime composition** (e.g., Module Federation, Single-SPA, Web Components)

Evaluasi ketiganya berdasarkan 4 parameter kritis: **Build isolation / Deployment coupling**, **Initial page load latency (TTFB/FCP)**, **Runtime overhead / Memory footprint**, dan **Independent rollbacks**.

### Soal 1.3: Sandboxing & Boundary Isolation
Isolasi aplikasi micro-frontend adalah syarat mutlak dalam arsitektur multi-tim.
1. Bagaimana cara mengisolasi runtime JavaScript agar modifikasi mutasi global `window` atau `document` oleh Micro-App A tidak mencemari Micro-App B tanpa menggunakan `<iframe>`?
2. Mengapa isolasi CSS berbasis BEM atau CSS Modules sering kali gagal pada skala ratusan micro-app, dan apa kelebihan serta trade-off performa penggunaan **Shadow DOM (`attachShadow({ mode: 'open' })`)** dalam membendung *CSS cascading bleed*?

### Soal 1.4: Cross-Micro-Frontend Communication & State Topology
Dalam arsitektur micro-frontend terdistribusi, komunikasi antar-aplikasi rentan menimbulkan *tight coupling* jika salah dirancang.
1. Bandingkan pola komunikasi via **Browser Custom Events (Pub/Sub on `window`)**, **Reactive Shared Store (e.g., RxJS Subject / Micro-Store)**, dan **URL/Query Params as Single Source of Truth**.
2. Jelaskan bahaya arsitektural dari konsep "Global Shared Store" (seperti shared Redux singleton antar micro-app) dan kapan pola tersebut harus ditolak secara kategoris (*architectural anti-pattern*).

### Soal 1.5: Shared Dependency Resolution & SemVer Negotiation
Module Federation mengandalkan mekanisme *shared scope* untuk mencegah *bloated bundle* (misalnya mengunduh React berkali-kali).
1. Jelaskan bagaimana runtime container mengevaluasi parameter: `singleton: true`, `strictVersion: true`, dan `requiredVersion: "^18.2.0"`.
2. Apa yang terjadi di balik layar jika Host mengekspos React `18.2.0` (`singleton: true`), sedangkan Remote meminta React `19.0.0` (`singleton: true`, `strictVersion: false`)? Bagaimana resolusi *fallback* dijalankan oleh runtime Module Federation?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Debugging "Invalid Hook Call Warning" & Duplicate React Instance
Sebuah remote micro-frontend dimuat ke dalam Host Dashboard. Di local environment berjalan lancar, namun di staging environment remote melempar uncaught error:
```text
Error: Invalid hook call. Hooks can only be called inside of the body of a function component.
1. You might have mismatching versions of React and the renderer (such as React DOM)
2. You might be breaking the Rules of Hooks
3. You might have more than one copy of React in the same app
```
1. Bedah mekanisme internal React (khususnya referensi internal dispatcher `ReactCurrentDispatcher`) yang memicu error ini saat ada dua copy React di memory.
2. Identifikasi kemungkinan *root cause* pada konfigurasi `shared` di Module Federation Host dan Remote.
3. Tuliskan blueprint konfigurasi Module Federation untuk memastikan runtime *guaranteed deduplication* dan *fail-safe resolution*.

### Soal 2.2: Mitigasi Cascading Failure pada Dynamic Remote Initialization
Jika sebuah remote container mengalami HTTP 503 atau connection timeout saat Host mencoba mengunduh `remoteEntry.js`, secara default seluruh Host application dapat mengalami *uncaught dynamic import promise rejection* dan white-screen crash.
1. Rancang arsitektur pemuatan remote yang menerapkan pola **Circuit Breaker** dan **Asynchronous Fallback**.
2. Bagaimana cara mengabstraksikan fungsi `loadRemoteComponent(remoteUrl, scope, module)` agar mendukung timeout threshold, automated retry dengan exponential backoff, dan graceful degradation (menampilkan Safe Error Boundary UI) tanpa merusak lifecycle aplikasi utama?

### Soal 2.3: Desinkronisasi Routing & Nested History Collision
Host menggunakan React Router v6 dengan `BrowserRouter`, sedangkan Remote App A menggunakan `BrowserRouter` internalnya sendiri.
1. Mengapa keberadaan dua instance `BrowserRouter` (atau history object yang berbeda) menyebabkan desinkronisasi URL, *infinite navigation loop*, atau hilangnya fungsi tombol browser Back/Forward?
2. Bagaimana arsitektur routing yang benar untuk Micro-Frontend (misalnya: Host mengelola top-level routing via `MemoryRouter` vs `BrowserRouter` synchronizer pattern pada Remote)?

### Soal 2.4: Memory Leak pada Micro-App Unmounting Lifecycle
Dalam dashboard Single-Page Application, pengguna sering berpindah antar-tab micro-app. Setelah 30 menit penggunaan, memory browser meningkat dari 120 MB menjadi 1.8 GB hingga tab browser mengalami crash (*OOM kill*).
1. Bagaimana lifecycle *unmounting* sebuah micro-frontend harus diimplementasikan?
2. Sebutkan minimal 4 penyebab tersembunyi kebocoran memory pada saat micro-app di-unmount (terkait DOM detached nodes, timer runtime, Web Workers, dan cross-application event listeners).
3. Bagaimana metodologi profiling kebocoran memory ini menggunakan Chrome DevTools Heap Snapshot dan Allocation Instrumentation on Timeline?

### Soal 2.5: CSS Specificity Wars & Dynamic Injection Clashes
Remote Micro-Frontend A menggunakan Tailwind CSS v3 dengan preflight aktif (`normalize.css`). Remote Micro-Frontend B menggunakan Ant Design legacy. Ketika Remote A di-mount, layout tombol dan form di Remote B seketika rusak berantakan.
1. Analisis apa yang terjadi pada runtime DOM `<head>` ketika kedua remote menginjeksi style tags mereka.
2. Mengapa mengubah urutan rendering atau mengubah `z-index` bukan solusi struktural?
3. Rancang 2 solusi arsitektural: satu berbasis **PostCSS/Tailwind configuration isolation (scoping/prefixing)** dan satu berbasis **Native Shadow DOM Style Encapsulation**, lengkap dengan trade-off masing-masing terhadap modal/portal dialog popover.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Catastrophic Network Waterfall & TTI Degenerasi pada E-Commerce Dashboard
**Konteks Insiden:**
Sebuah platform e-commerce enterprise memiliki Dashboard Penjual yang dipecah menjadi 8 Micro-Frontend independen (Analytics, Inventory, Orders, Ads, Notifications, Chat, Reviews, Profile).
Saat peluncuran kampanye 12.12, dashboard mengalami lonjakan pengguna 500%. Time-to-Interactive (TTI) melonjak drastis dari 2.1 detik menjadi **14.8 detik**, dengan First Meaningful Paint (FMP) 8 detik. Profiling Network tab menunjukkan:
*   Host memuat 8 file `remoteEntry.js` secara paralel di `<head>`.
*   Masing-masing remote melakukan fetch shared dependencies chunk (`vendors-node_modules_...js`) yang saling tumpang-tindih (waterfall chain mencapai 18 level).
*   Bandwidth throttling pada koneksi 4G menyebabkan request queueing terhenti (*stalled*) karena browser mencapai batas 6 koneksi concurrent TCP per domain HTTP/1.1.

```
Host Load 
 ├──> remoteEntry (Analytics) ──> vendor.js ──> index.js ──> API Call
 ├──> remoteEntry (Inventory) ──> vendor.js ──> index.js ──> API Call
 ├──> remoteEntry (Orders)    ──> vendor.js ──> index.js ──> API Call
 └──> ... (5 remote lainnya dieksekusi serentak)
```

**Pertanyaan Diagnostik & Solusi:**
1. Bedah cacat arsitektur pemuatan (*loading orchestration*) pada sistem ini!
2. Rancang strategi **Progressive & Deferred Loading Framework** untuk dashboard ini:
   *   Tentukan mana yang harus di-load sebagai Critical Initial View, Lazy View, dan On-Demand/Hover View.
   *   Bagaimana Anda mengoptimalkan multiplexing aset via HTTP/2 atau HTTP/3 CDN Edge?
3. Bagaimana Anda mengonfigurasi module federation shared chunks agar Host bertindak sebagai *Primary Pre-loader* untuk vendor-vendor kritis (React, UI core engine) sehingga remote tidak memicu network waterfall sekunder?

---

### Skenario B: Race Condition dan State Contamination pada High-Frequency Trading Desk
**Konteks Insiden:**
Sistem B2B Wealth Management menggunakan arsitektur micro-frontend:
*   **MFE-Ticker:** Menerima stream harga saham real-time via WebSocket (50 tick/detik).
*   **MFE-OrderForm:** Memproses kalkulasi margin dan submit order beli/jual.
*   **MFE-Portfolio:** Menampilkan total valuasi aset dan cash balance.

Ketiga MFE berkomunikasi melalui global `window.postMessage` / EventTarget bus tanpa payload validation dan sequence control.
Selama volatilitas pasar tinggi:
1. Pengguna mengklik "Execute Order" untuk membeli 100 lot saham saat harga Rp 5.000.
2. MFE-OrderForm membaca harga dari event stream yang datang terlambat (*out-of-order execution*) dibanding WebSocket stream yang sudah mencapai Rp 5.250 di MFE-Ticker.
3. Validasi margin di MFE-OrderForm lolos menggunakan data cash balance lama dari MFE-Portfolio yang belum menyelesaikan kalkulasi reaktif dari transaksi sebelumnya.
4. Terjadi eksekusi order dengan data stale yang mengakibatkan margin call negatif pada akun klien.

```
[MFE-Ticker]      ---(Price: 5250, Event #102)---> [Global Event Bus]
[MFE-Ticker]      ---(Price: 5000, Event #101 delayed) -> [Global Event Bus] 
                                                                 │
                                                       (Race Condition)
                                                                 │
[MFE-OrderForm]   <---- Receives Event #101 AFTER #102 ----------┘
                  ==> Trigger BUY @ 5000 (Mismatch with Exchange State!)
```

**Pertanyaan Diagnostik & Solusi:**
1. Identifikasi vulnerability mendasar dari komunikasi asynchronous berbasis event bus unversioned antar-MFE pada sistem transaksional kritis!
2. Rancang protokol komunikasi data yang **Deterministic & Race-Condition Proof** untuk Micro-Frontend tersebut:
   *   Terapkan konsep **Vector Clocks / Monotonic Sequence IDs** dan **Contract-driven Event Schema** (e.g., JSON Schema / Zod runtime validation).
3. Jika Order Execution membutuhkan status validasi mutlak dari 2 MFE berbeda, bagaimana Anda menerapkan arsitektur **Two-Phase Commit (2PC) / Request-Response Orchestration** di level client-side runtime sebelum API request dikirim ke backend gateway?

---

### Skenario C: Dilema Migrasi Monolith Legacy Core-Banking (AngularJS to Modern React)
**Konteks Strategis:**
Anda ditunjuk sebagai Principal Architect untuk meremajakan platform Internet Banking enterprise:
*   Aplikasi eksisting adalah SPA Monolith berbasis **AngularJS 1.6** (1.2 juta baris kode, build time 18 menit, zero modern bundling).
*   Manajemen menolak *total rewrite* (Big Bang Rewrite) karena risiko downtime dan regulasi kepatuhan audit perbankan.
*   Target: Fitur-fitur baru (misal: Investasi Obligasi & Pinjaman Digital) harus dibangun menggunakan **React 18 / TypeScript / Tailwind CSS**, berjalan di dalam shell AngularJS yang ada secara mulus tanpa mengorbankan performa dan user experience.

Tim terbelah menjadi dua kubu arsitektur:
*   **Kubu A:** Mengusulkan embedding via **`<iframe>`** terisolasi dengan bridge `postMessage` untuk fitur-fitur React baru.
*   **Kubu B:** Mengusulkan **Runtime Micro-Frontend Co-existence (Micro-App Wrappers / Web Components)** di mana React di-mount langsung di dalam AngularJS DOM container di bawah satu runtime execution context.

**Pertanyaan Diagnostik & Solusi:**
1. Bedah secara objektif kelebihan, kelemahan fatal, dan *hidden operational costs* dari pendekatan **Kubu A (Iframe)** vs **Kubu B (DOM Co-existence)** untuk domain perbankan (Tinjau aspek: Shared Session & Auth Token handling, Modal/Accessibility trapping, Mobile Responsiveness, SEO/Deep Linking, dan Memory Consumption).
2. Jika Anda memilih pendekatan **Strangler Fig Pattern** berbasis DOM Co-existence (Kubu B):
   *   Bagaimana desain wrapper adaptor bridge (React-in-AngularJS directive)?
   *   Bagaimana strategi *Unified Authentication & Session Timeout Synchronizer* bekerja saat pengguna idle di modul React tetapi AngularJS session monitor tetap harus sinkron?
   *   Rancang roadmap decommissioning bertahap hingga seluruh shell AngularJS tereliminasi tanpa *feature regression*.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Resilient Federated Micro-Frontend Engine (From Scratch)

#### Problem Statement
Tim frontend Anda ditugaskan membangun **Host Micro-Frontend Shell Engine** untuk Enterprise Portal tanpa menggunakan framework pihak ketiga tingkat tinggi (seperti Single-SPA framework abstractions). Shell harus mampu memuat remote modules berbasis Webpack/Rspack/Vite Module Federation dengan standar ketahanan tingkat militer (*fault-tolerant, isolated, and performant*).

#### Requirements
1. **Dynamic Module Loader dengan Circuit Breaker:**
   *   Implementasikan fungsi `federatedComponentLoader(options)`:
       ```typescript
       interface LoadOptions {
         remoteUrl: string;
         scope: string;
         module: string;
         fallbackComponent: React.ComponentType<{ error: Error }>;
         timeoutMs?: number;
         retries?: number;
       }
       ```
   *   Jika CDN remote gagal diakses atau timeout (default 3000ms), lakukan auto-retry hingga batas `retries`. Jika tetap gagal, isolasi error dan render `fallbackComponent` tanpa merusak rendering modul lain di layar.
2. **Context-Isolated Typed Event Bus:**
   *   Bangun generic pub/sub communication bus `createFederatedEventBus<T>()`:
       *   Harus decoupled dari `window` global scope (gunakan scoped namespace identifier).
       *   Mendukung schema validation di runtime (verifikasi payload sebelum di-dispatch ke subscriber).
       *   Mencegah *memory leak*: Wajib menyediakan fungsi `unsubscribe()` dan lifecycle tracker otomatis yang membuang subscriber ketika host meng-unmount container MFE.
3. **CSS Collision Guard & Sandbox Injection:**
   *   Komponen remote harus di-render di dalam **Isolated Boundary**:
       *   Pilihan 1: Shadow DOM wrapper dengan automatic Emotion/Tailwind style insertion point.
       *   Pilihan 2: Scoped namespace wrapper dengan dynamic style tag cleaner saat unmount.
4. **Shared State & Health Diagnostic Monitor:**
   *   Sediakan Mini Dashboard Debugger (floating HUD) di Host Shell yang menampilkan:
       *   Daftar remote yang terdaftar, statusnya (LOADING, HEALTHY, FAILED, DEGRADED).
       *   Latency pengunduhan masing-masing remote container.
       *   Daftar shared dependencies dan versi yang sedang aktif di runtime shared scope (`window.__federation_shared__`).

#### Constraints
*   **Zero Framework Micro-Frontend Dependencies:** Dilarang menggunakan `single-spa`, `qiankun`, atau `piral`. Gunakan native Web API dan Native Module Federation runtime API (`__webpack_init_sharing__`, `__webpack_share_scopes__`, dsb).
*   **Performance Budget:** Overhead library shell engine ini tidak boleh melebihi **8 KB (gzipped)**.
*   **Strict Type-Safety:** Kode harus 100% TypeScript dengan generic types ketat, no `any`.

#### Expected Output
1. File `federationEngine.ts`: Mengandung core logic dynamic loading, circuit breaker, retry, dan promise timeout race.
2. File `eventBus.ts`: Engine pub/sub terisolasi, type-safe, dan leak-proof.
3. File `FederatedBoundary.tsx`: React wrapper component yang menyatukan dynamic loader, Error Boundary, Suspense fallback, dan Shadow DOM/Namespace CSS isolation.
4. Diagram Sequence Flow (ASCII atau Mermaid) yang memvisualisasikan bagaimana Host menginisialisasi shared scope, memuat remote, menangani fallback ketika remote 500, hingga unmounting cleanup.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal Module Federation: runtime flow `remoteEntry.js`, `__webpack_init_sharing__`, `__webpack_share_scopes__`, dan initialization handshake.
- [ ] Perbedaan trade-off antara Build-time Integration, Server-Side Integration (Edge/Proxy), dan Client-Side Runtime Integration.
- [ ] Mekanisme SemVer resolution pada shared scope: konfigurasi `singleton`, `strictVersion`, `requiredVersion`, dan dampak binary footprint-nya.
- [ ] Penyebab teknis terjadinya `Invalid Hook Call` dan *Multiple Dispatcher Instantiation* pada shared React dependencies.
- [ ] Teknik sandboxing JavaScript (Proxy Sandboxing, Realm/Iframe isolation) dan CSS Isolation (Native Shadow DOM vs PostCSS Scoping).
- [ ] Dampak arsitektural penggunaan un-namespaced Global Event Bus terhadap determinisme state dan data integrity antar-tim.
- [ ] Lifecycle unmounting micro-frontend: garbage collection DOM, listener cleanup, worker termination, dan memory profiling.
- [ ] Pola migrasi Strangler Fig untuk meremajakan sistem monolitik frontend legacy secara bertahap tanpa downtime.

### Saya tidak perlu menghafal:
- [ ] Sintaks baris-per-baris konfigurasi Webpack/Rspack Module Federation plugin (cukup memahami semantik konfigurasinya: `name`, `remotes`, `exposes`, `shared`).
- [ ] Daftar lengkap kode error internal Webpack runtime container chunk loader.
- [ ] Seluruh implementasi spesifikasi W3C Web Components API secara detail di luar kebutuhan isolasi Shadow DOM.

### Saya harus bisa melakukan:
- [ ] Membangun dynamic remote loader resilient dengan fitur timeout, retry backoff, dan circuit breaking tanpa dependensi eksternal.
- [ ] Mendiagnosa dan memecahkan masalah CSS specificity clash dan CSS preflight leakage antar remote micro-frontend.
- [ ] Melakukan heap snapshot profiling di browser DevTools untuk melacak retainers path yang menyebabkan memory leak saat switching antar micro-apps.
- [ ] Mendesain arsitektur komunikasi antar micro-app yang decoupled, contract-tested, type-safe, dan bebas race condition.
- [ ] Mengonfigurasi host and remote sharing topology untuk mengoptimalkan Core Web Vitals (LCP, INP, CLS) dan mencegah cascading network waterfalls.