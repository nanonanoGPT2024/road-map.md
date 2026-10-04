# Bab 10 Module 01: Micro-Frontend Architecture & Production Systems

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Frontend and Mobile Development
*   **Kategori:** 03-Frontend-and-Mobile
*   **Bab:** 10 — Advanced Frontend Systems & Distributed Architectures
*   **Modul:** 01 — Micro-Frontend Architecture & Production Systems
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** Penguasaan mendalam atas Modern ECMAScript (ES2022+), Browser Runtime Execution Contexts, Module Bundlers (Webpack, Vite/Rollup), Browser Security Model (CORS, CSP, Origin Isolation), CI/CD Automation, dan State Management Systems.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta mampu:

1.  **Menganalisis dan Memilih Pola Integrasi Micro-Frontend:** Mengevaluasi trade-off arsitektur antara integrasi Build-Time (NPM packages), Server-Side (Edge Side Includes, SSR Composition), dan Client-Side Dynamic Composition (Module Federation, Custom Elements, Single-SPA).
2.  **Mengimplementasikan Module Federation Lanjut:** Merancang host application dan remote modules menggunakan Webpack 5 / Vite Federation Runtime, mencakup isolasi dependensi, dynamic remotes resolution, serta shared memory optimization.
3.  **Mengonfigurasi Sandboxing dan Isolasi Runtime:** Mengisolasi Execution Context dan CSS Scope pada browser menggunakan Shadow DOM, CSS Modules, serta JavaScript Global Proxy Wrapping untuk mencegah collision dan state pollution.
4.  **Membangun Komunikasi Antar-Domain yang Terdekopel:** Mengimplementasikan Event Bus berbasis EventTarget/CustomEvent yang fully-typed, RxJS Streams, dan cross-origin iframe communication via `postMessage` dengan skema verifikasi payload yang ketat.
5.  **Menerapkan Resiliensi dan Fallback Orquestration:** Membangun runtime orchestration yang mampu menangani network failure pada remote asset menggunakan Circuit Breakers, Retry Exponential Backoff, dan Graceful Degradation.
6.  **Mengoptimalkan Metrik Web Vitals & Shared Dependencies:** Mereduksi bundle duplication, mengeliminasi layout shifts (CLS), dan memitigasi latensi jaringan (FCP, LCP) akibat pemanggilan manifest dan chunks secara bertingkat (waterfall network requests).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam sistem monolitik frontend, browser mengeksekusi satu pohon dependensi (dependency graph) yang dikompilasi oleh satu bundler, menghasilkan artefak yang terikat secara kaku. Jika satu modul mengalami kegagalan fatal atau terjadi kesalahan pada deklarasi tipe global, seluruh build pipeline atau seluruh eksekusi runtime aplikasi dapat terhenti.

Micro-Frontend (MFE) mengubah model mental ini: **Frontend bukan lagi satu aplikasi tunggal, melainkan sebuah ekosistem layanan terdistribusi (Distributed Client-Side Runtime) yang dieksekusi di dalam browser klien.**

```
+---------------------------------------------------------------------------------+
|                              MENTAL MODEL TRANSITION                            |
+---------------------------------------------------------------------------------+
|  MONOLITHIC FRONTEND:                                                           |
|  [ Single Git Repo ] ---> [ Unified Bundler ] ---> [ Single Immutable Bundle ]   |
|                                                                                 |
|  DISTRIBUTED MICRO-FRONTEND:                                                    |
|  [ Team Cart Repo ]     ---> [ Cart Bundle (CDN) ]   ---+                       |
|  [ Team Checkout Repo ] ---> [ Checkout Bundle (CDN) ] -+-> [ Browser Dynamic ] |
|  [ Team Core Repo ]     ---> [ Host/Shell (CDN) ]    ---+   [ Composite Runtime]|
+---------------------------------------------------------------------------------+
```

### Hukum Conway dan Batasan Domain (Domain Boundaries)
Arsitektur Micro-Frontend adalah perwujudan langsung dari Hukum Conway (*Conway's Law*): struktur perangkat lunak mencerminkan struktur komunikasi organisasi. Pemisahan domain bisnis (misalnya: *Catalog*, *Billing*, *Identity*) harus dipetakan secara jelas menjadi modul independen yang memiliki:
*   Repositori terpisah (atau monorepo dengan isolated build pipelines).
*   Siklus rilis independen (*Autonomous Deployments*). Tidak ada *lock-step release*.
*   Kepemilikan penuh dari database, API Gateway, hingga User Interface slice.

### Paradigma Runtime Independence
Sebuah micro-frontend harus didesain dengan asumsi bahwa lingkungan eksternal (Host Shell maupun Micro-Frontend lain) **tidak dapat dipercaya secara mutlak**. Komponen yang di-mount harus mampu hidup mandiri, mengisolasi memory leaks, menangani kegagalan dependensi pihak ketiga, serta mempertahankan fungsionalitas minimal ketika dependensi eksternal mati (*fail-safe operation*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah representasi end-to-end arsitektur Enterprise Micro-Frontend berbasis Client-Side Dynamic Module Federation dengan Resilient Edge Fallback.

```
+----------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE MFE RUNTIME TOPOLOGY                                 |
+----------------------------------------------------------------------------------------------------+
                                               |
                                     [ Client Browser Hits URL ]
                                               |
                                               v
+----------------------------------------------------------------------------------------------------+
| Edge / Cloudflare Workers / Fastly (CDN & Ingress)                                                 |
| - Inspects Request, injects Edge-Side Dynamic Config (Remote Manifest URLs based on Tenant/Region)  |
+----------------------------------------------------------------------------------------------------+
       |                                       |                                      |
       | Fetches Shell Entry                   | Fetches Manifest                     | Healthchecks
       v                                       v                                      v
+------------------+                 +--------------------+                 +--------------------+
|  Host Shell App  |                 | Dynamic Discovery  |                 | Remote Service C   |
| (Root Orchestrator|                | Service (Registry) |                 | (e.g. Checkout)    |
+------------------+                 +--------------------+                 +--------------------+
       |                                       |                                      |
       +=======================================+======================================+
                                               |
                                               v
+----------------------------------------------------------------------------------------------------+
| BROWSER RUNTIME CONTEXT (Memory Space)                                                             |
|                                                                                                    |
|  +----------------------------------------------------------------------------------------------+  |
|  | HOST SHELL CONTAINER                                                                         |  |
|  |  - MicroFrontend Orchestrator (Router, Dynamic Loader)                                        |  |
|  |  - Global Event Bus / Typed Message Broker (RxJS, EventTarget)                               |  |
|  |  - Error Boundary Root & Performance Telemetry Collector                                     |  |
|  +----------------------------------------------------------------------------------------------+  |
|             |                                                  |                                   |
|             | Loads via Module Federation                      | Loads with Sandboxing             |
|             v                                                  v                                   |
|  +-------------------------------------+            +-------------------------------------+        |
|  | REMOTE A: CATALOG DOMAIN            |            | REMOTE B: ACCOUNT DOMAIN            |        |
|  | - React 18 Engine                   |            | - Vue 3 Engine                      |        |
|  | - Shadow DOM (Scoped Styles)        |            | - Scoped Custom Element Target      |        |
|  | - Shared React/ReactDOM (Singleton)|            | - Separate Dependency Graph         |        |
|  +-------------------------------------+            +-------------------------------------+        |
|             |                                                  |                                   |
|             +-------------------------+------------------------+                                   |
|                                       | (Zero Global State Coupling)                               |
|                                       v                                                            |
|  +----------------------------------------------------------------------------------------------+  |
|  | BROWSER STORAGE & INFRASTRUCTURE                                                             |  |
|  |  - Shared Storage (IndexedDB, LocalStorage via Scoped Keys)                                  |  |
|  |  - Session Context / HTTP Only Cookies                                                       |  |
|  +----------------------------------------------------------------------------------------------+  |
+----------------------------------------------------------------------------------------------------+
```

### Alur Eksekusi Runtime Bootstrapping (Sequence Lifecycle)

```
Browser               Host Shell           Discovery API          Remote A (Cart)       Remote B (Auth)
   |                       |                     |                       |                     |
   |--- 1. Get Shell ----->|                     |                       |                     |
   |<-- 2. HTML/Shell JS --|                     |                       |                     |
   |                       |                     |                       |                     |
   |--- 3. Execute Bootstrap ------------------->|                       |                     |
   |                       |--- 4. Fetch Manifest ---------------------->|                     |
   |                       |<-- 5. Endpoints URLs -----------------------|                     |
   |                       |                     |                       |                     |
   |                       |--- 6. Load remoteEntry.js (Async) --------->|                     |
   |                       |<-- 7. Initialize Remote A Scope ------------|                     |
   |                       |                     |                       |                     |
   |                       |--- 8. Match Route /cart ------------------->|                     |
   |                       |                     |                       |                     |
   |                       |--- 9. Dynamic Import Container.get('Cart') >|                     |
   |                       |<-- 10. Instantiate Component ----------------                     |
   |                       |                     |                                             |
   |                       |--- 11. Mount to DOM (with Shadow Boundary)                        |
   |                       |                     |                                             |
   |                       |=== 12. Publish Event "CART_UPDATED" ====> Event Bus               |
   |                       |                     |                          |                  |
   |                       |<== 13. Receive Event via Subscription =========+=================>|
   v                       v                     v                          v                  v
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Module Federation Container Engine
Module Federation bekerja di level bundler dan browser loader. Terdapat tiga entitas utama:
*   **Host Container:** Aplikasi pertama yang menginisialisasi Module Federation shared scope dan bertindak sebagai konsumen remote modules.
*   **Remote Container:** Aplikasi yang mengekspos variabel antarmuka global (misalnya `window.checkoutApp`) yang berisi metadata modul melalui file `remoteEntry.js`.
*   **Shared Scope Object:** Objek memori browser bersama (biasanya dialokasikan pada `__webpack_share_scopes__.default`) yang memetakan modul-modul yang dibagi (seperti `react`, `react-dom`, `@tanstack/react-query`).

Di balik layar, inisialisasi kontainer mengikuti kontrak dua fase:

```javascript
// Fase 1: Inisialisasi Share Scope
await remoteContainer.init(__webpack_share_scopes__.default);

// Fase 2: Ekstraksi Modul Factory (Getter Pattern)
const factory = await remoteContainer.get("./ComponentModule");
const ComponentModule = factory();
```

### 2. Dependency Negotiation & SemVer Resolution
Ketika host dan remote mendeklarasikan dependensi yang sama pada runtime, Webpack/Vite menjalankan algoritma resolusi SemVer:
1.  Setiap kontainer mendaftarkan versi dependensi yang dimilikinya ke dalam tabel global `shareScope`.
2.  Jika sebuah dependensi ditandai sebagai `singleton: true`:
    *   Sistem mencari versi tertinggi yang memenuhi batasan `requiredVersion`.
    *   Jika versi tidak kompatibel dan `strictVersion: true`, runtime melempar exception fail-fast.
    *   Jika `strictVersion: false`, sistem memilih versi tertinggi yang ada namun memunculkan peringatan di konsol.
3.  Jika modul bukan singleton (`singleton: false`), kontainer yang membutuhkan versi berbeda akan mengunduh bundle versinya sendiri secara independen, mencegah tabrakan eksekusi (*graceful duplicate resolution*).

### 3. DOM & CSS Sandboxing Engine
Isolasi visual dan runtime dicapai melalui perpaduan teknik browser-native:

```
+-------------------------------------------------------------+
| Light DOM: Host Shell Styles (Reset CSS, Tailwind, Fonts)   |
|                                                             |
|   <div id="mfe-catalog-container">                          |
|     #shadow-root (open)                                     |
|       <style>                                               |
|         /* Terisolasi penuh dari Light DOM */              |
|         h1 { color: red; font-size: 16px; }                 |
|       </style>                                              |
|       <div class="catalog-scope">                           |
|         <h1>Produk Unggulan</h1>                            |
|       </div>                                                |
|   </div>                                                    |
+-------------------------------------------------------------+
```

Jika Web Components / Shadow DOM tidak dimungkinkan (misalnya karena library pihak ketiga seperti DatePicker atau Modal merender langsung ke `document.body`), isolasi dilakukan via:
*   **PostCSS Namespace Prefixing:** Seluruh selector CSS remote otomatis ditambahkan prefix unik (misal: `.mfe-catalog-scope .btn`).
*   **JavaScript Proxy Window Sandboxing:** Setiap micro-frontend membungkus `window` global menggunakan `new Proxy(window, handler)` untuk mencegah penulisan variabel secara liar ke lingkungan global eksekusi browser.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Orchestrator Engine Internals
Orchestrator bertanggung jawab atas siklus hidup aplikasi remote: `Load -> Init -> Mount -> Update -> Unmount -> Teardown`.

```
               [ROUTE TRIGGER]
                      |
                      v
             [Check Module Cache]
              /                \
      (Hit)  /                  \ (Miss)
            v                    v
      [Resolve Scope]    [Fetch remoteEntry.js]
            |                    |
            |            [Parse & Init Scope]
            |                    |
            +----------+---------+
                       |
                       v
            [Evaluate Error Boundary]
             /                      \
      (Success)                     (Failure)
         /                              \
        v                                v
  [Mount Component]             [Activate Circuit Breaker]
        |                                |
  [Attach EventBus]             [Render Fallback Component]
```

### Sandboxing Menggunakan JavaScript Proxy (Hard Isolation)
Untuk mencegah kontaminasi global `window`, kita dapat mengimplementasikan mekanisme sandboxing aktif yang merekam mutasi global dan membatalkannya saat modul di-unmount.

```javascript
class ProxySandbox {
  constructor(name) {
    this.name = name;
    this.proxy = null;
    this.updatedProperties = new Map();
    this.isRunning = false;

    const rawWindow = window;
    const fakeWindow = Object.create(null);

    this.proxy = new Proxy(fakeWindow, {
      set: (target, prop, value) => {
        if (!this.isRunning) return true;
        if (!rawWindow.hasOwnProperty(prop)) {
          this.updatedProperties.set(prop, value);
        }
        target[prop] = value;
        rawWindow[prop] = value;
        return true;
      },
      get: (target, prop) => {
        // Fallback ke window asli jika tidak ditemukan di fakeWindow
        const value = prop in target ? target[prop] : rawWindow[prop];
        if (typeof value === 'function') {
          return value.bind(rawWindow);
        }
        return value;
      }
    });
  }

  active() {
    this.isRunning = true;
    this.updatedProperties.forEach((value, prop) => {
      window[prop] = value;
    });
  }

  inactive() {
    this.isRunning = false;
    this.updatedProperties.forEach((_, prop) => {
      delete window[prop];
    });
  }
}
```

### Event-Driven Cross-MFE Communication (Decoupled Mediator Pattern)
Keterikatan langsung antar modul melalui *window properties* atau *direct import* dilarang keras dalam skala enterprise. Pola yang valid adalah asynchronous message passing menggunakan instance `EventTarget` terisolasi atau RxJS Subject yang di-expose melalui kontrak TypeScript yang kaku.

```typescript
// Core Message Structure Definition
interface MicroFrontendEvent<T = unknown> {
  type: string;
  payload: T;
  sourceDomain: string;
  correlationId: string;
  timestamp: number;
}
```

Komunikasi ini menjamin bahwa jika Micro-Frontend `A` (misal: *Checkout*) mendengarkan event dari Micro-Frontend `B` (misal: *Cart*), hilangnya Micro-Frontend `B` dari halaman tidak akan menyebabkan Micro-Frontend `A` mengalami crash (*temporal decoupling*).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi dasar Module Federation menggunakan Webpack 5.

### File 1: `remote-cart/webpack.config.js` (Remote Provider)

```javascript
const HtmlWebpackPlugin = require('html-webpack-plugin');
const { ModuleFederationPlugin } = require('webpack').container;
const path = require('path');

module.exports = {
  entry: './src/index.js',
  mode: 'production',
  output: {
    publicPath: 'auto',
    path: path.resolve(__dirname, 'dist'),
    clean: true,
  },
  module: {
    rules: [
      {
        test: /\.jsx?$/,
        loader: 'babel-loader',
        exclude: /node_modules/,
        options: {
          presets: ['@babel/preset-react'],
        },
      },
    ],
  },
  plugins: [
    new ModuleFederationPlugin({
      name: 'cartRemote',
      filename: 'remoteEntry.js',
      exposes: {
        './CartWidget': './src/components/CartWidget.jsx',
      },
      shared: {
        react: {
          singleton: true,
          requiredVersion: '^18.2.0',
          strictVersion: true,
        },
        'react-dom': {
          singleton: true,
          requiredVersion: '^18.2.0',
          strictVersion: true,
        },
      },
    }),
    new HtmlWebpackPlugin({
      template: './public/index.html',
    }),
  ],
};
```

### File 2: `host-shell/webpack.config.js` (Host Consumer)

```javascript
const HtmlWebpackPlugin = require('html-webpack-plugin');
const { ModuleFederationPlugin } = require('webpack').container;
const path = require('path');

module.exports = {
  entry: './src/index.js',
  mode: 'production',
  output: {
    publicPath: '/',
    path: path.resolve(__dirname, 'dist'),
    clean: true,
  },
  module: {
    rules: [
      {
        test: /\.jsx?$/,
        loader: 'babel-loader',
        exclude: /node_modules/,
        options: {
          presets: ['@babel/preset-react'],
        },
      },
    ],
  },
  plugins: [
    new ModuleFederationPlugin({
      name: 'hostShell',
      remotes: {
        cartRemote: 'cartRemote@https://cdn.enterprise.domain/cart/remoteEntry.js',
      },
      shared: {
        react: {
          singleton: true,
          requiredVersion: '^18.2.0',
          strictVersion: true,
        },
        'react-dom': {
          singleton: true,
          requiredVersion: '^18.2.0',
          strictVersion: true,
        },
      },
    }),
    new HtmlWebpackPlugin({
      template: './public/index.html',
    }),
  ],
};
```

### File 3: `host-shell/src/bootstrap.jsx` (Bootstrap Inisialisasi)

```jsx
import React, { Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';

// Lazy loading remote federated component
const CartWidget = lazy(() => import('cartRemote/CartWidget'));

class ModuleErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Remote Component Crash:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '1rem', border: '1px solid red', color: 'red' }}>
          <h3>Gagal Memuat Komponen Cart</h3>
          <p>{this.state.error?.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}

const App = () => {
  return (
    <main style={{ fontFamily: 'sans-serif', padding: '2rem' }}>
      <header>
        <h1>Host Application Shell</h1>
      </header>
      <section style={{ marginTop: '2rem' }}>
        <h2>Belanjaan Anda</h2>
        <ModuleErrorBoundary>
          <Suspense fallback={<div>Memuat Cart Remote Module...</div>}>
            <CartWidget />
          </Suspense>
        </ModuleErrorBoundary>
      </section>
    </main>
  );
};

const container = document.getElementById('root');
const root = createRoot(container);
root.render(<App />);
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis komponen fundamental di atas:

### `remote-cart/webpack.config.js`
*   **Baris 23 (`name: 'cartRemote'`):** Mendefinisikan namespace global unik. File `remoteEntry.js` yang dihasilkan akan menugaskan antarmuka internalnya ke `window.cartRemote`.
*   **Baris 24 (`filename: 'remoteEntry.js'`):** Manifest dan loader container entry point yang bertindak sebagai tabel indeks untuk chunk-chunk yang diekspos.
*   **Baris 25-27 (`exposes: { './CartWidget': ... }`):** Memetakan public identifier `./CartWidget` ke implementasi file internal `./src/components/CartWidget.jsx`. Webpack akan mengekstrak dependensi internal file ini dan membungkusnya dalam modul async.
*   **Baris 28-39 (`shared: { react: { singleton: true, ... } }`):**
    *   `singleton: true`: Menginstruksikan runtime Webpack untuk hanya memuat satu instance React di seluruh memori browser. Mencegah bug "Rules of Hooks" akibat fragmentasi multi-instance React runtime.
    *   `strictVersion: true`: Menolak eksekusi jika Host menyediakan React dengan versi yang tidak sesuai dengan `requiredVersion`, memaksa fallback deterministik.

### `host-shell/src/bootstrap.jsx`
*   **Baris 5 (`const CartWidget = lazy(...)`):** Eksekusi dynamic `import('cartRemote/CartWidget')` memicu pemanggilan chunk resolver internal Webpack. Browser akan mengunduh chunk JavaScript fisik dari CDN cart remote secara asinkron.
*   **Baris 7-29 (`class ModuleErrorBoundary ...`):** Komponen batas kegagalan (Fault-Isolation Boundary). Wajib dibungkus di setiap modul federasi. Tanpa penanganan ini, kegagalan jaringan (HTTP 404/500/Timeout) saat mengunduh remote bundle akan menyebabkan White Screen of Death (WSoD) di seluruh Host Shell.
*   **Baris 37-41 (`<Suspense fallback={...}>`):** Mengelola asynchronous waterfall loading state, mereduksi Cumulative Layout Shift (CLS) saat chunk sedang diambil dari jaringan.

---

## SEKSI 09 — STUDI KASUS NYATA (Enterprise Scenario)

### Konteks Masalah
Sebuah platform e-commerce FinTech berskala global memproses transaksi harian senilai jutaan dolar. Arsitektur front-end sebelumnya adalah monolit berbasis Next.js dengan 120 insinyur perangkat lunak yang melakukan push ke repositori yang sama.

### Gejala Masalah (Pain Points)
1.  **Build Time Degradation:** CI build pipeline memakan waktu **48 menit** untuk setiap PR.
2.  **Deployment Blockers:** Bug pada modul pendaftaran Akun (*Identity*) memblokir rilis fitur mendesak dari tim Pembayaran (*Checkout*).
3.  **Blast Radius Bencana:** Tim Marketing merilis library diskon baru yang menyebabkan kebocoran memori (Memory Leak) dan tabrakan style global (CSS mutation), mengakibatkan tombol *Pay Now* tidak dapat diklik pada 22% pengguna Safari.

### Solusi Desain
Migrasi ke Arsitektur Micro-Frontend berbasis **Dynamic Asynchronous Federation via Webpack 5 + TypeScript Shared Shell Orchestrator + Resilient Circuit Breakers**.

### Target Metrik Keberhasilan
*   Pemisahan deployment pipelines menjadi 4 domain mandiri: *Host Shell*, *Core Auth*, *Catalog*, dan *Checkout*.
*   CI/CD pipeline time turun dari 48 menit menjadi **< 4 menit** per tim.
*   Zero Cross-CSS Collisions dengan Shadow DOM encapsulation.
*   Zero Single-Point-of-Failure: Jika modul Checkout gagal inisialisasi, fallback sistem ke antarmuka Checkout Lite berbasis Server-Side Rendered form.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & PRODUCTION CODE

Berikut adalah implementasi sistem produksi modular skala enterprise yang mencakup:
1.  **Dynamic Remote Loader** dengan timeout dan Circuit Breaker pattern.
2.  **Typed Event Bus** untuk komunikasi lintas micro-frontend.
3.  **Shadow DOM Container Wrapper** untuk isolasi stylesheet total.

```typescript
// ============================================================================
// FILE: src/core/EventBus.ts (Decoupled Message Broker)
// ============================================================================

export interface EventEnvelope<T = unknown> {
  type: string;
  payload: T;
  sourceDomain: string;
  timestamp: number;
}

export type EventHandler<T = unknown> = (event: EventEnvelope<T>) => void;

export class TypedEventBus {
  private static instance: TypedEventBus;
  private target: EventTarget;

  private constructor() {
    this.target = new EventTarget();
  }

  public static getInstance(): TypedEventBus {
    if (!TypedEventBus.instance) {
      TypedEventBus.instance = new TypedEventBus();
    }
    return TypedEventBus.instance;
  }

  public publish<T>(type: string, sourceDomain: string, payload: T): void {
    const envelope: EventEnvelope<T> = {
      type,
      payload,
      sourceDomain,
      timestamp: Date.now(),
    };
    const customEvent = new CustomEvent<EventEnvelope<T>>(type, {
      detail: envelope,
    });
    this.target.dispatchEvent(customEvent);
  }

  public subscribe<T>(type: string, handler: EventHandler<T>): () => void {
    const eventListener = (event: Event) => {
      const customEvent = event as CustomEvent<EventEnvelope<T>>;
      handler(customEvent.detail);
    };

    this.target.addEventListener(type, eventListener);
    // Teardown callback untuk mencegah memory leak
    return () => {
      this.target.removeEventListener(type, eventListener);
    };
  }
}

// ============================================================================
// FILE: src/core/FederationLoader.ts (Dynamic Dynamic Module Loader Engine)
// ============================================================================

interface LoadRemoteOptions {
  remoteUrl: string;
  scope: string;
  module: string;
  timeoutMs?: number;
}

enum CircuitBreakerState {
  CLOSED,
  OPEN,
  HALF_OPEN,
}

class FederationLoaderService {
  private failureCount: Map<string, number> = new Map();
  private circuitState: Map<string, CircuitBreakerState> = new Map();
  private readonly FAILURE_THRESHOLD = 3;
  private readonly RESET_TIMEOUT = 30000; // 30 detik

  private loadScript(url: string, timeoutMs: number): Promise<void> {
    return new Promise((resolve, reject) => {
      const existingScript = document.querySelector(`script[src="${url}"]`);
      if (existingScript) {
        resolve();
        return;
      }

      const script = document.createElement('script');
      script.src = url;
      script.type = 'text/javascript';
      script.async = true;

      const timer = setTimeout(() => {
        script.remove();
        reject(new Error(`Timeout loading remote asset: ${url} (${timeoutMs}ms)`));
      }, timeoutMs);

      script.onload = () => {
        clearTimeout(timer);
        resolve();
      };

      script.onerror = () => {
        clearTimeout(timer);
        script.remove();
        reject(new Error(`Network error loading script: ${url}`));
      };

      document.head.appendChild(script);
    });
  }

  public async loadRemoteModule<T = unknown>(options: LoadRemoteOptions): Promise<T> {
    const { remoteUrl, scope, module, timeoutMs = 8000 } = options;
    const currentState = this.circuitState.get(scope) || CircuitBreakerState.CLOSED;

    if (currentState === CircuitBreakerState.OPEN) {
      throw new Error(`Circuit breaker is OPEN for scope: ${scope}. Request aborted.`);
    }

    try {
      // 1. Download Remote Entry Script
      await this.loadScript(remoteUrl, timeoutMs);

      // 2. Inisialisasi Share Scope Webpack
      await __webpack_init_sharing__('default');
      const container = (window as Record<string, any>)[scope];

      if (!container) {
        throw new Error(`Global container scope [${scope}] not found on window.`);
      }

      await container.init(__webpack_share_scopes__.default);

      // 3. Resolve Module Factory
      const factory = await container.get(module);
      const resolvedModule = factory();

      // Reset Failure Count on success
      this.failureCount.set(scope, 0);
      this.circuitState.set(scope, CircuitBreakerState.CLOSED);

      return resolvedModule;
    } catch (error) {
      const currentFailures = (this.failureCount.get(scope) || 0) + 1;
      this.failureCount.set(scope, currentFailures);

      if (currentFailures >= this.FAILURE_THRESHOLD) {
        this.circuitState.set(scope, CircuitBreakerState.OPEN);
        // Atur timeout untuk transisi ke HALF_OPEN
        setTimeout(() => {
          this.circuitState.set(scope, CircuitBreakerState.HALF_OPEN);
        }, this.RESET_TIMEOUT);
      }

      throw error;
    }
  }
}

export const federationLoader = new FederationLoaderService();

// ============================================================================
// FILE: src/components/ShadowMfeWrapper.tsx (Shadow DOM Isolation Renderer)
// ============================================================================

import React, { useEffect, useRef, useState } from 'react';
import ReactDOM from 'react-dom/client';

interface ShadowMfeWrapperProps {
  remoteUrl: string;
  scope: string;
  module: string;
  cssUrl?: string;
  fallback: React.ReactNode;
}

export const ShadowMfeWrapper: React.FC<ShadowMfeWrapperProps> = ({
  remoteUrl,
  scope,
  module,
  cssUrl,
  fallback,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const [hasError, setHasError] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const shadowRootRef = useRef<ShadowRoot | null>(null);
  const reactRootRef = useRef<ReactDOM.Root | null>(null);

  useEffect(() => {
    let isMounted = true;

    const bootstrapModule = async () => {
      try {
        setIsLoading(true);
        // Load federated module secara dinamis
        const ComponentModule = await federationLoader.loadRemoteModule<{ default: React.ComponentType<any> }>({
          remoteUrl,
          scope,
          module,
        });

        if (!isMounted || !mountRef.current) return;

        // Inisialisasi Shadow Root jika belum ada
        if (!shadowRootRef.current) {
          shadowRootRef.current = mountRef.current.attachShadow({ mode: 'open' });
        }

        const shadow = shadowRootRef.current;

        // Injeksi Stylesheet remote langsung ke Shadow DOM
        if (cssUrl && !shadow.querySelector(`link[href="${cssUrl}"]`)) {
          const link = document.createElement('link');
          link.rel = 'stylesheet';
          link.href = cssUrl;
          shadow.appendChild(link);
        }

        // Siapkan Mount Point internal di dalam Shadow DOM
        let innerContainer = shadow.getElementById('inner-root');
        if (!innerContainer) {
          innerContainer = document.createElement('div');
          innerContainer.id = 'inner-root';
          shadow.appendChild(innerContainer);
        }

        // Render Remote React Component menggunakan React 18 createRoot
        const RemoteComponent = ComponentModule.default;
        if (!reactRootRef.current) {
          reactRootRef.current = ReactDOM.createRoot(innerContainer);
        }
        
        reactRootRef.current.render(<RemoteComponent eventBus={TypedEventBus.getInstance()} />);
        setIsLoading(false);
      } catch (err) {
        console.error(`Failed to orchestrate remote ${scope}/${module}:`, err);
        if (isMounted) {
          setHasError(true);
          setIsLoading(false);
        }
      }
    };

    bootstrapModule();

    return () => {
      isMounted = false;
      if (reactRootRef.current) {
        // Unmount lifecycle cleanup untuk mencegah memory leak
        reactRootRef.current.unmount();
        reactRootRef.current = null;
      }
    };
  }, [remoteUrl, scope, module, cssUrl]);

  if (hasError) {
    return <>{fallback}</>;
  }

  return (
    <div ref={mountRef} className="mfe-boundary-slot">
      {isLoading && <div className="animate-pulse p-4">Memuat Remote Container...</div>}
    </div>
  );
};
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Evaluasi | Build-Time Integration (NPM Packages) | Iframe-Based Isolation | Single-SPA / Vanilla Dynamic Imports | Module Federation (Webpack 5/Vite) |
| :--- | :--- | :--- | :--- | :--- |
| **Pemisahan Deployment** | **Buruk:** Setiap rilis remote mewajibkan rebuild dan redeploy host shell. | **Sempurna:** Komponen dideploy terpisah di origin mana pun. | **Tinggi:** Modul di-bundle terpisah dan dimuat via dynamic `import()`. | **Sempurna:** Autonomi penuh via manifest & remote entry runtime. |
| **Isolasi Runtime & CSS** | **Nol:** Semua CSS dan JS menyatu di Light DOM dan memori bersama. | **Sempurna:** Hard isolation via browser sandbox security context. | **Sedang:** Membutuhkan manual namespacing atau Shadow DOM manual. | **Kustom:** Perlu Shadow DOM atau PostCSS scoping rules.