# KURIKULUM SISTEM ENTERPRISE: FRONTEND ENGINEERING
## BAB 10: Micro-Frontend Architecture dan Production Systems
### MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai arsitektur internal **Module Federation** (Webpack 5 / Vite Federation Engine) pada level runtime dan memory allocation.
- Merancang dan mengimplementasikan mekanisme **Dynamic Remote Container Loading** berbasis Service Registry atau Dynamic Manifest tanpa memerlukan build ulang pada container Host (Shell).
- Mengimplementasikan komunikasi lintas Micro-Frontend (MFE) yang decoupled, type-safe, dan memory-leak free menggunakan **Custom Event Bus berbasis pub/sub** dan State Reconciliation.
- Menyelesaikan permasalahan isolasi CSS tingkat lanjut (CSS Bleeding, specificity war) menggunakan Shadow DOM encapsulation, scoped design systems, dan build-time name-mangling.
- Mengonfigurasi strategi penanganan dependensi bersama (*shared dependencies*), negosiasi SemVer otomatis, dan mitigasi duplikasi runtime React/ReactDOM (Singleton violations).
- Mengembangkan sistem **Resilience & Fault Tolerance** (Circuit Breaker, Fallback UI, Telemetry) untuk mencegah *single point of failure* pada aplikasi Host ketika Remote MFE mengalami *network drop* atau *runtime crash*.

---

### 2. Prerequisite
Peserta wajib memiliki pemahaman mendalam pada:
- **Arsitektur Webpack/Rollup Modern**: Dependency graphs, dynamic imports, chunk splitting, dan lifecycle compilation.
- **Advanced TypeScript & DOM APIs**: EventTarget, CustomEvent, Shadow DOM (open/closed modes), Dynamic Script Execution (`HTMLScriptElement`).
- **Core React 18+ Internals**: Concurrent Mode, Error Boundaries, Suspense boundaries, Context API, lifecycle unmounting, dan garbage collection awareness.
- **Networking & Delivery Systems**: CDN Caching strategies (stale-while-revalidate, cache busting), Content Security Policy (CSP), Cross-Origin Resource Sharing (CORS).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Mekanisme Internal Webpack Module Federation Runtime
Module Federation tidak mentransfer kode mentah antar-aplikasi; ia mengeksekusi protokol negosiasi runtime berbasis container interface.

```
+-------------------------------------------------------------------------------+
|                             Host Application Runtime                          |
|                                                                               |
|  1. Inisialisasi: window.__webpack_share_scopes__['default']                  |
|  2. Dynamic Injection: <script src="https://remote.cdn/remoteEntry.js">       |
|  3. container = window[remoteScope]                                           |
|  4. await container.init(__webpack_share_scopes__['default'])                  |
|  5. factory = await container.get('./Module')                                 |
|  6. Component = factory()                                                     |
+-------------------------------------------------------------------------------+
```

1. **Shared Scope Negotiation (`__webpack_share_scopes__`)**:
   Saat runtime menginisialisasi bundle, runtime Host menciptakan objek global namespace internal `__webpack_share_scopes__`. Objek ini memetakan dependensi:
   ```javascript
   __webpack_share_scopes__.default = {
     react: {
       "18.2.0": {
         loaded: 1,
         get: () => Promise.resolve().then(() => () => window.React),
         from: "host_app"
       }
     }
   }
   ```
2. **Container Handshake (`init` & `get`)**:
   Setiap remote file `remoteEntry.js` mengekspos variabel global (atau UMD container) yang mengimplementasikan dua fungsi antarmuka wajib:
   - `init(sharedScope)`: Menggabungkan (*merges*) dependensi lokal remote ke dalam shared scope Host dan menyelesaikan konflik versi SemVer berdasarkan aturan `singleton`, `strictVersion`, dan `requiredVersion`.
   - `get(moduleName)`: Mengembalikan *factory function* untuk modul yang diekspos (`exposes`). Module ini di-resolve secara asinkron (*dynamic chunk loading*).

#### B. Dynamic Manifest & Service Discovery Architecture
Pada skala enterprise, *hardcoding* URL remote (misal: `http://localhost:3001/remoteEntry.js`) dalam konfigurasi build adalah anti-pattern. Pendekatan produksi memanfaatkan **Dynamic Asset Manifest Registry**.

```
[Client Shell] ---> HTTP GET /api/v1/mfe-manifest ---> [API Gateway / Config Service]
       |                                                         |
       | Returns: { "checkout": "https://cdn.corp/checkout/v2.1.4/remoteEntry.js" }
       v
Inject Script Tag ---> Dynamic Module Resolution ---> Mount Remote Component
```

Arsitektur ini memungkinkan deployment atomik independen: tim modul remote cukup mengupdate endpoint manifest registry (bisa berupa edge worker seperti Cloudflare Workers atau Lambda@Edge) tanpa perlu men-deploy ulang Host Shell.

#### C. Isolasi DOM dan CSS Mechanics
Terdapat trade-off tajam antara enkapsulasi total dan kemudahan integrasi:
1. **Shadow DOM (Native Isolation)**:
   - Membuat boundary sub-DOM terisolasi (`element.attachShadow({ mode: 'open' })`).
   - Mencegah *style leakage* dua arah: CSS Host tidak merusak Remote, dan CSS Remote tidak mengotori Host.
   - *Tantangan*: Komponen library berbasis Portal (Modal, Dropdown, Tooltip) yang me-render elemen pada `document.body` akan kehilangan akses ke style jika tidak di-inject langsung ke dalam Shadow Root.
2. **PostCSS Scoping / Name-Mangling (Build-Time Isolation)**:
   - Menggunakan prefix namespace unik pada build pipeline (contoh: `.mfe-checkout-btn-primary`).
   - Berkinerja optimal, tidak memiliki kendala Portal, namun rentan apabila terdapat developer yang menggunakan selector elemen mentah (misal: `h1`, `button`) tanpa class.

---

### 4. Why & What

| Dimensi | Monolith Frontend | Micro-Frontend Konvensional (Iframe) | Modern Micro-Frontend (Module Federation) |
| :--- | :--- | :--- | :--- |
| **Pemisahan Deployment** | Tidak Ada (Satu build raksasa) | Penuh | Penuh (via Dynamic Remotes) |
| **Runtime Performance** | Optimal (Shared memory) | Sangat Buruk (High memory, multiple DOM trees) | Tinggi (Near-native shared memory) |
| **Duplikasi Dependensi** | Nol | 100% duplikasi di tiap iframe | Nol hingga Minimal (Tergantung SemVer) |
| **Komunikasi Antar-Modul**| Memory Direct (Store/Context) | Terbatas (`postMessage` serialization) | Decoupled Event-Bus / Custom Events |
| **Deep-Linking / UX** | Mulus (*Seamless*) | Canggung (Sync URL antar-iframe sulit) | Mulus (*Native single-page app behavior*) |

**Mengapa ini penting bagi arsitektur enterprise?**
Ketika organisasi rekayasa perangkat lunak tumbuh melampaui 50-100 frontend engineer, bottleneck bergeser dari masalah komputasi ke masalah koordinasi tim (*organizational friction*). Micro-frontend dengan Module Federation memungkinkan skalabilitas organisasi: otonomi rilis tim, isolasi domain bisnis, dan kegagalan terisolasi (*blast radius reduction*), tanpa mengorbankan metrik Core Web Vitals (LCP, FID/INP, CLS) secara signifikan.

---

### 5. How (Workflow Detail)

Alur eksekusi end-to-end saat Host memuat Remote Micro-Frontend secara asinkron:

```
[Host Component Rendered]
         │
         ▼
[Cek Cache Modul] ──(Ada)──► [Ambil Factory dari Cache] ──┐
         │                                                │
       (Tidak)                                            │
         ▼                                                │
[Fetch Registry Config]                                   │
         │                                                │
         ▼                                                │
[Inject <script src="remoteEntry.js">]                    │
         │                                                │
         ▼                                                │
[Handshake: remote.init(__webpack_share_scopes__.default)]│
         │                                                │
         ▼                                                │
[Execute: remote.get(modulePath)]                         │
         │                                                │
         ▼                                                │
[Eksekusi Module Factory] ◄───────────────────────────────┘
         │
         ▼
[Mount React Node via React.Suspense]
         │
         ├─ (Error Terjadi?) ──► [Tangkap di Error Boundary] ──► [Tampilkan Fallback]
         │
         ▼
[Lifecycle Active: Listen ke EventBus / Render UI]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pelabuhan Peti Kemas Global
Bayangkan aplikasi **Host** adalah sebuah **Kapal Kargo Peti Kemas**, dan **Remote MFE** adalah **Peti Kemas Modular (ISO Container)**.
- Kapal Kargo menyediakan generator listrik, navigasi, dan bahan bakar bersama (*Host Shell: Shared React Runtime, Auth Session, Global Event System*).
- Setiap Peti Kemas berisi muatan spesifik yang dibangun oleh pabrik berbeda (*Checkout MFE, Inventory MFE*).
- Sebelum peti kemas dihubungkan ke listrik kapal, dilakukan pengecekan kompatibilitas soket (*Module Federation SemVer Negotiation*).
- Jika sistem pendingin satu peti kemas rusak, sirkuit pemutus (*Circuit Breaker*) memutus aliran listrik lokal tersebut agar mesin utama kapal tidak meledak (*Fault Isolation*).

#### Diagram Arsitektur Runtime & Shared Scope Resolution

```
+---------------------------------------------------------------------------------------+
| HOST BROWSER PROCESS                                                                  |
|                                                                                       |
|  +---------------------------------------------------------------------------------+  |
|  | window.__webpack_share_scopes__.default                                         |  |
|  |   ├── react: { '18.2.0': { loaded: true, from: 'host-shell' } }                 |  |
|  |   └── @corp/event-bus: { '1.0.0': { loaded: true, from: 'host-shell' } }         |  |
|  +---------------------------------------------------------------------------------+  |
|                                                                                       |
|  +---------------------------+       Dynamic Network Call     +--------------------+  |
|  | Host Shell (App.tsx)      | ─────────────────────────────> | Service Registry   |  |
|  |                           | <───────────────────────────── | (manifest.json)    |  |
|  +---------------------------+                                +--------------------+  |
|               │                                                                       |
|               │ 1. Inject remoteEntry.js                                              |
|               v                                                                       |
|  +--------------------------------------------------------------------+               |
|  | Remote MFE: Checkout (remoteEntry.js)                              |               |
|  |   - Menggunakan react dari scope Host (tanpa download ulang)        |               |
|  |   - Menjalankan Style Encapsulation (Shadow/Scoped CSS)             |               |
|  |   - Berkomunikasi lewat Global Event Bus                            |               |
|  +--------------------------------------------------------------------+               |
|                                                                                       |
+---------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Inisialisasi Dinamis Low-Level
Contoh pemanggilan Remote Container via Webpack Low-Level Container API secara imperatif.

```typescript
// dynamicLoader.ts
interface WebpackContainer {
  init(shareScope: unknown): Promise<void>;
  get(module: string): Promise<() => { default: React.ComponentType<any> }>;
}

declare global {
  interface Window {
    [key: string]: WebpackContainer;
    __webpack_share_scopes__: {
      default: unknown;
    };
  }
}

export async function loadRemoteModule(
  remoteUrl: string,
  scopeName: string,
  moduleName: string
): Promise<React.ComponentType<any>> {
  // 1. Injeksi script ke DOM secara asinkron
  await new Promise<void>((resolve, reject) => {
    if (window[scopeName]) return resolve();

    const script = document.createElement('script');
    script.src = remoteUrl;
    script.type = 'text/javascript';
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Gagal memuat remote container: ${remoteUrl}`));
    document.head.appendChild(script);
  });

  // 2. Inisialisasi shared scope
  await window.__webpack_init_sharing__('default');
  const container = window[scopeName];
  await container.init(window.__webpack_share_scopes__.default);

  // 3. Ambil module factory
  const factory = await container.get(moduleName);
  const Module = factory();
  return Module.default;
}
```

---

#### B. Practical Example: Implementasi Produksi Lengkap (Industrial Grade)

Berikut adalah implementasi sistem produksi modular mencakup:
1. Konfigurasi Webpack Host dengan dependensi strictly-managed.
2. Cross-MFE Type-Safe Event Bus.
3. React Production Remote Component Loader dengan Circuit Breaker dan Suspense.

##### File: `host/webpack.config.js`
```javascript
const HtmlWebpackPlugin = require('html-webpack-plugin');
const { ModuleFederationPlugin } = require('webpack').container;
const path = require('path');
const deps = require('./package.json').dependencies;

module.exports = {
  entry: './src/index.ts',
  mode: 'production',
  output: {
    publicPath: 'auto',
    clean: true,
  },
  resolve: {
    extensions: ['.ts', '.tsx', '.js'],
  },
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        loader: 'babel-loader',
        exclude: /node_modules/,
      },
    ],
  },
  plugins: [
    new ModuleFederationPlugin({
      name: 'host_shell',
      shared: {
        react: {
          singleton: true,
          requiredVersion: deps.react,
          strictVersion: true,
        },
        'react-dom': {
          singleton: true,
          requiredVersion: deps['react-dom'],
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

##### File: `packages/event-bus/src/index.ts`
Implementasi Type-Safe Decoupled Event-Bus yang tidak bergantung pada dependensi framework apapun (agnostik).

```typescript
export type EventPayloadMap = {
  'USER_AUTHENTICATED': { userId: string; token: string };
  'CART_ITEM_ADDED': { sku: string; quantity: number };
  'PAYMENT_COMPLETED': { transactionId: string; status: 'SUCCESS' | 'FAILED' };
};

export class EnterpriseEventBus {
  private static instance: EnterpriseEventBus;

  private constructor() {}

  public static getInstance(): EnterpriseEventBus {
    if (!EnterpriseEventBus.instance) {
      EnterpriseEventBus.instance = new EnterpriseEventBus();
    }
    return EnterpriseEventBus.instance;
  }

  public publish<K extends keyof EventPayloadMap>(event: K, payload: EventPayloadMap[K]): void {
    const customEvent = new CustomEvent(`corp:${event}`, {
      detail: payload,
      bubbles: true,
      composed: true, // Tembus batas Shadow DOM
    });
    window.dispatchEvent(customEvent);
  }

  public subscribe<K extends keyof EventPayloadMap>(
    event: K,
    callback: (payload: EventPayloadMap[K]) => void
  ): () => void {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent<EventPayloadMap[K]>;
      callback(customEvent.detail);
    };

    window.addEventListener(`corp:${event}`, handler);
    return () => {
      window.removeEventListener(`corp:${event}`, handler);
    };
  }
}

export const eventBus = EnterpriseEventBus.getInstance();
```

##### File: `host/src/components/DynamicRemoteLoader.tsx`
Komponen wrapper dengan kapabilitas **Circuit Breaker Pattern**, Dynamic Script Ingestion, dan Graceful Fallback.

```tsx
import React, { Component, ErrorInfo, ReactNode, Suspense } from 'react';

// --- CIRCUIT BREAKER STATE & TYPES ---
interface RemoteManifest {
  url: string;
  scope: string;
  module: string;
}

interface ErrorBoundaryProps {
  fallback: ReactNode;
  children: ReactNode;
  onReset?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

export class MfeErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = { hasError: false };

  public static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[MFE Circuit Breaker] Remote Crash Terdeteksi:', error, errorInfo);
    // Kirim telemetri error ke observability platform (misal: Sentry, Datadog)
  }

  public render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

// --- DYNAMIC MODULE RESOLVER ENGINE ---
function loadComponent(scope: string, module: string, url: string) {
  return async () => {
    // 1. Pemuatan Script Runtime
    if (!window[scope]) {
      await new Promise<void>((resolve, reject) => {
        const existingScript = document.querySelector(`script[data-webpack="${scope}"]`);
        if (existingScript) {
          existingScript.addEventListener('load', () => resolve());
          existingScript.addEventListener('error', () => reject(new Error(`Gagal fetch script ${url}`)));
          return;
        }

        const script = document.createElement('script');
        script.src = url;
        script.type = 'text/javascript';
        script.async = true;
        script.setAttribute('data-webpack', scope);

        script.onload = () => resolve();
        script.onerror = () => reject(new Error(`Gagal network load untuk container: ${scope} dari ${url}`));

        document.head.appendChild(script);
      });
    }

    // 2. Shared Scope Negotiation
    // @ts-ignore
    await __webpack_init_sharing__('default');
    const container = window[scope];
    // @ts-ignore
    await container.init(__webpack_share_scopes__.default);

    // 3. Module Resolution
    const factory = await container.get(module);
    return factory();
  };
}

// --- HIGHER-ORDER PRODUCTION COMPONENT ---
interface RemoteComponentProps {
  manifest: RemoteManifest;
  fallbackUi: ReactNode;
  loadingUi: ReactNode;
  componentProps?: Record<string, any>;
}

export const DynamicRemoteWidget: React.FC<RemoteComponentProps> = ({
  manifest,
  fallbackUi,
  loadingUi,
  componentProps = {},
}) => {
  const LazyComponent = React.useMemo(() => {
    return React.lazy(loadComponent(manifest.scope, manifest.module, manifest.url));
  }, [manifest.scope, manifest.module, manifest.url]);

  return (
    <MfeErrorBoundary fallback={fallbackUi}>
      <Suspense fallback={loadingUi}>
        <LazyComponent {...componentProps} />
      </Suspense>
    </MfeErrorBoundary>
  );
};
```

##### File: `remote-checkout/src/CheckoutWidget.tsx`
Implementasi modul remote yang berinteraksi dengan DOM isolasi & event bus.

```tsx
import React, { useEffect } from 'react';
import { eventBus } from '@corp/event-bus';

export const CheckoutWidget: React.FC = () => {
  useEffect(() => {
    // Membaca event dari Shell atau MFE lain
    const unsubscribe = eventBus.subscribe('CART_ITEM_ADDED', (payload) => {
      console.log(`[Checkout MFE] Menerima item baru: ${payload.sku}, Qty: ${payload.quantity}`);
    });

    return () => {
      unsubscribe();
    };
  }, []);

  const handleCheckoutSuccess = () => {
    eventBus.publish('PAYMENT_COMPLETED', {
      transactionId: `TX-${Date.now()}`,
      status: 'SUCCESS',
    });
  };

  return (
    <div style={{ border: '2px solid #2563eb', padding: '16px', borderRadius: '8px' }}>
      <h2 style={{ margin: '0 0 8px 0' }}>Panel Pembayaran Mandiri (Remote MFE)</h2>
      <p>Modul ini terisolasi dan berkomunikasi melalui secure bus.</p>
      <button
        onClick={handleCheckoutSuccess}
        style={{
          background: '#2563eb',
          color: '#ffffff',
          padding: '8px 16px',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
        }}
      >
        Konfirmasi Pembayaran
      </button>
    </div>
  );
};

export default CheckoutWidget;
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Super-App Perbankan & FinTech (Bank Digital Nasional)
- **Kondisi Awal**: Aplikasi portal web nasabah dibangun di atas monolitik Next.js tunggal. Rilis melibatkan 14 *squad engineering* yang berbeda (Payment, Mutual Funds, Lending, Core Banking, Account Settings).
- **Insiden Kritis**: Regresi kode CSS pada rilis fitur pinjaman (Lending Squad) menimpa style tombol konfirmasi transfer (Payment Squad), menyebabkan 30% transaksi transfer gagal klik selama 4 jam pada jam sibuk. Build pipeline monolitik memakan waktu 48 menit, memperlambat proses rollback.
- **Transformasi Arsitektur**:
  1. Monolith dipecah menjadi **1 Core Shell** dan **5 Micro-Frontends** terdistribusi.
  2. Implementasi **Edge Asset Manifest Registry** berbasis CDN Cloudflare Workers.
  3. Mengadopsi Tailwind CSS dengan prefix build-time per-squad (`tw-pay-`, `tw-lend-`).
  4. Menerapkan Circuit Breaker pada setiap boundary widget.
- **Hasil Operasional**:
  - Build pipeline per-squad turun drastis dari **48 menit** menjadi **3.5 menit**.
  - Rollback versi modul remote dapat dilakukan dalam **< 15 detik** cukup dengan membalikkan hash URL file di Edge Manifest via REST API, tanpa re-deploy Core Shell.
  - Saat core cluster microservice tim Reksa Dana (Mutual Funds) down, UI hanya mengaktifkan *degraded mode* (banner fallback lokal) tanpa membuat crash flow Transfer atau Dashboard utama.

---

### 9. Trade-offs

| Aspek | Keputusan Arsitektur | Keuntungan | Biaya / Kerugian (*Trade-off*) |
| :--- | :--- | :--- | :--- |
| **Performance (Bundle Size)** | Singleton Dependencies (`react`, `react-dom`) | Mencegah duplikasi download library masif di browser klien. | Rentan crash runtime jika versi remote melanggar rentang SemVer ketat Host Shell. |
| **Latency (Network Overhead)** | Multi-Chunk Dynamic Loading | Membuka remote hanya saat dibutuhkan (*lazy consumption*). | Rantai waterfall request jaringan: Host bundle -> Registry API -> remoteEntry.js -> chunks. |
| **Style Isolation** | Web Components (Shadow DOM) | Isolasi absolut 100% dari style leaks. | Kompleksitas tinggi saat mengintegrasikan Modal/Popper libs dan form-data handling native. |
| **Scalability (Tim)** | Polyrepo MFE Architecture | Kebebasan independensi siklus CI/CD tiap squad. | Rentan terhadap *dependency drift* dan kesulitan dalam testing end-to-end terintegrasi (*contract breakage*). |
| **Cost (Infrastruktur)** | Dynamic Multi-CDN Edge Invalidation | Kemampuan zero-downtime micro deployment instan. | Biaya tambahan untuk runtime Edge/API Gateway dan kompleksitas purging cache CDN. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Invariant Violation: "Invalid Hook Call" / Multiple React Instances
- **Penyebab**: Module Federation tidak dikonfigurasi dengan flag `singleton: true` pada host dan remote, menyebabkan dua instance React berjalan paralel dalam memory graph browser.
- **Troubleshooting & Fix**:
  ```javascript
  // Pada SEMUA webpack.config.js (Host dan Remotes)
  shared: {
    react: {
      singleton: true,
      strictVersion: true,
      requiredVersion: '^18.2.0'
    }
  }
  ```

#### 2. CSS Specificity Bleeding Melalui Global Resets
- **Penyebab**: Tim modul A mengimpor `normalize.css` atau Tailwind CSS mentah yang mereset style tag `* { box-sizing: border-box; margin: 0; }` dan `body { font-size: 14px; }`, merusak tata letak Host Shell.
- **Troubleshooting & Fix**: Terapkan prefixing otomatis pada PostCSS config remote:
  ```javascript
  // postcss.config.js (Remote Modul)
  module.exports = {
    plugins: {
      tailwindcss: {},
      autoprefixer: {},
      'postcss-prefix-selector': {
        prefix: '.remote-scope-namespace',
        transform(prefix, selector, prefixedSelector) {
          if (selector.startsWith('html') || selector.startsWith('body')) {
            return prefix;
          }
          return prefixedSelector;
        },
      },
    },
  };
  ```

#### 3. Memory Leaks dari Global Event Listener
- **Penyebab**: Developer melakukan `window.addEventListener` di dalam `useEffect` modul Remote namun lupa menghapus handler saat unmount. Akibatnya, saat Host berpindah route dan meng-unmount remote, referensi function closure tertahan di objek `window`.
- **Troubleshooting & Fix**: Selalu pastikan cleanup function mengembalikan referensi unbind listener (lihat implementasi `EnterpriseEventBus`). Gunakan DevTools Memory Heap Snapshot: filter instance modul remote setelah di-unmount untuk memastikan memory dibebaskan.

---

### 11. Best Practices (Production Checklist)

- [ ] **Dependency Enforcement**: Konfigurasi `singleton: true` dan `strictVersion: true` untuk semua library fundamental yang berbasis global memory context (`react`, `react-dom`, `@tanstack/react-query`).
- [ ] **Cross-Origin Configuration**: Pastikan header `Access-Control-Allow-Origin: *` (atau origin domain internal) terkonfigurasi dengan benar di CDN penyedia file `remoteEntry.js`.
- [ ] **Subresource Integrity (SRI)**: Jangan gunakan dynamic hash acak jika menggunakan static SRI. Jika menggunakan SRI di MFE, implementasikan sistem manifest runtime yang menyertakan checksum hash SHA-384 bersamaan dengan URL chunk.
- [ ] **Resilience Isolation**: Setiap import dinamik MFE **wajib** dibungkus oleh kombinasi `React.Suspense` dan `MfeErrorBoundary`.
- [ ] **Agnostic State Management**: Jangan pernah membagikan instance Redux Store atau Zustand Store internal antar MFE secara langsung. Gunakan event-driven payload atau Custom DOM Events untuk menghindari kopling dependensi logic.
- [ ] **Cache Header Policy**: Set header file `remoteEntry.js` dengan `Cache-Control: no-cache, no-store, must-revalidate` (atau max-age rendah dengan etag), sedangkan file static chunk JS/CSS hasil build (ber-hash seperti `chunk.8f7b2c.js`) diset dengan `Cache-Control: public, max-age=31536000, immutable`.
- [ ] **Observability Injection**: Suntikkan correlation trace ID (misal: OpenTelemetry) ke header event lintas MFE untuk melacak user journey antar remote container.

---

### 12. Hands-on Practice
Instruksi langkah-demi-langkah yang harus dieksekusi di workspace direktori `hands-on/m02/`:

#### Langkah 1: Persiapan Struktur Direktori
Buat struktur monorepo ringan untuk simulasi lokal:
```bash
mkdir -p hands-on/m02/{shell-host,remote-cart,shared-bus}
cd hands-on/m02
npm init -y
```

#### Langkah 2: Setup Shared Bus
Buat paket TypeScript agnostik di `hands-on/m02/shared-bus`:
1. Buat file `index.ts` sesuai rancangan praktikal (Bab 7).
2. Lakukan compile/transpile menjadi format ESM dan CJS via `tsc`.

#### Langkah 3: Setup Webpack Module Federation Remote (Cart)
1. Inisialisasi React app sederhana pada `remote-cart`.
2. Pasang Webpack 5 dan konfigurasi `ModuleFederationPlugin` yang mengekspos `./CartWidget`.
3. Tambahkan tombol interaktif yang mem-publish event `CART_ITEM_ADDED` ke shared-bus.
4. Jalankan pada port `3002`.

#### Langkah 4: Setup Dynamic Host (Shell)
1. Buat aplikasi Shell yang berjalan di port `3000`.
2. Implementasikan fungsi `DynamicRemoteWidget` dan `MfeErrorBoundary`.
3. Buat mock service manifest lokal via file JSON statis:
   ```json
   {
     "cart": {
       "url": "http://localhost:3002/remoteEntry.js",
       "scope": "remote_cart",
       "module": "./CartWidget"
     }
   }
   ```
4. Render Remote Cart secara asinkronus di layar Shell.

#### Langkah 5: Simulasi Chaos Engineering (Fault Tolerance)
1. Verifikasi integrasi data bekerja (klik tombol di cart, state di host terupdate).
2. Matikan paksa server `remote-cart` (Ctrl+C di terminal port 3002).
3. Lakukan hard-refresh pada Shell di port 3000.
4. Verifikasi bahwa **Shell Host tetap hidup**, dan fallback error UI dari `MfeErrorBoundary` tampil dengan rapi tanpa merusak bagian navigasi Host.

---

### 13. Exercise

#### Level: Easy
Konfigurasikan sebuah file `webpack.config.js` untuk aplikasi Host yang mengonsumsi modul remote secara statis (build-time URL) dengan dependensi bersama `lodash` yang tidak boleh berstatus singleton, tetapi harus membagikan versi yang sama jika kompatibel.

#### Level: Medium
Tulis sebuah Custom React Hook bernama `useMicroFrontendEvent(eventName, callback)` yang secara otomatis menangani registrasi event listener pada objek `window` saat komponen di-mount dan melakukan deregistrasi/clean-up secara aman saat komponen di-unmount guna mencegah kebocoran memory (*memory leaks*).

#### Level: Hard
Rancang dan implementasikan dynamic asset loader yang mendukung fallback bertingkat: jika remote versi `v2` pada CDN utama gagal di-fetch (mengembalikan HTTP 5xx atau timeout > 3 detik), sistem secara otomatis mengalihkan permintaan (*failover*) untuk mengambil versi stabil `v1` dari bucket CDN sekunder (*disaster recovery pipeline*), sebelum menyerah ke Error Boundary.

---

### 14. Challenge
**Studi Kasus Arsitektur Tanpa Solusi Instan:**
Sebuah platform E-Commerce multinasional mengalami anomali saat event promo "Flash Sale". Terdapat lonjakan akses yang mengakibatkan CDN penyedia `remoteEntry.js` untuk modul "Checkout" mengembalikan respons *stale* dan lambat (*high latency response* hingga 8 detik).

Pengguna yang menekan tombol *Order* berkali-kali memicu race condition:
- Modul remote lama dan modul remote baru ter-mount secara bergantian di DOM tree yang sama.
- Instance token autentikasi nasabah tersinkronisasi sebagian, menyebabkan *order split* (dua tagihan dengan ID transaksi berbeda terbit di database backend).
- Sebagian pengguna mengalami *white-screen crash* mendadak karena bundle chunk lama bentrok dengan chunk baru yang membawa breaking change pada runtime state.

**Instruksi:**
Rancang cetak biru arsitektur komprehensif untuk memecahkan krisis di atas:
1. Formulasikan strategi caching dan version-locking per-sesi transaksi pengguna (*Session-Affinity Version Pinning*).
2. Definisikan state machine guard di level Shell untuk mencegah *concurrency mounting* modul beda versi.
3. Rancang strategi mitigasi network timeout dan idempotency token handling pada komunikasi antar-MFE.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Pemahaman Konseptual)
1. **Apa tujuan utama dari inisialisasi `__webpack_init_sharing__('default')` pada runtime Module Federation?**
   - A. Men-download seluruh modul remote yang tersedia di network.
   - B. Menginisialisasi ruang lingkup memory bersama untuk negosiasi versi dependensi.
   - C. Mengonversi kode JSX menjadi JavaScript native ES5.
   - D. Menghapus script tag yang tidak terpakai dari DOM.

2. **Apa yang terjadi secara default jika Host membutuhkan React `^18.2.0` dengan status `singleton: true`, sedangkan Remote MFE memaksakan React `^17.0.0` dengan `strictVersion: true`?**
   - A. Webpack akan otomatis men-downgrade React Host menjadi 17.0.0.
   - B. Webpack akan mengunduh kedua React dan menjalankannya secara aman tanpa error.
   - C. Webpack akan melempar fatal runtime error saat handshake inisialisasi container.
   - D. Browser akan me-refresh halaman secara terus-menerus (*infinite loop*).

3. **Mengapa komunikasi antar-MFE dianjurkan menggunakan CustomEvent / Pub-Sub murni dibanding membagikan Redux store secara global?**
   - A. Karena Redux tidak mendukung TypeScript.
   - B. Agar tidak ada keterikatan (*tight coupling*) runtime state dan dependensi antar squad.
   - C. Karena CustomEvent berjalan di thread background web worker.
   - D. Redux dilarang oleh konsorsium W3C untuk dipakai di arsitektur micro frontend.

4. **Sifat isolasi apa yang ditawarkan oleh Shadow DOM mode 'closed'?**
   - A. Script luar sama sekali tidak dapat membaca DOM dalam shadow tree via JavaScript (`element.shadowRoot` bernilai `null`).
   - B. CSS luar tetap dapat masuk, tetapi JavaScript dilarang dieksekusi.
   - C. Shadow root otomatis hilang saat halaman di-scroll.
   - D. Menolak seluruh koneksi jaringan yang dipicu di dalam elemen.

5. **Header HTTP `Cache-Control` manakah yang paling ideal untuk file `remoteEntry.js` pada arsitektur produksi continuous delivery?**
   - A. `public, max-age=31536000, immutable`
   - B. `no-store, no-cache, must-revalidate`
   - C. `max-age=86400`
   - D. `public, stale-while-revalidate=604800`

---

#### Bagian 2: Intermediate (Analisis Arsitektur & Mekanisme)
6. Jelaskan bagaimana Webpack menyelesaikan dependensi jika dua remote yang dimuat sama-sama menyediakan modul utilitas `lodash` dengan versi yang identik dan parameter `singleton: false`!
7. Mengapa penggunaan library UI modal (seperti Radix UI atau React Portal) sering kali bermasalah di dalam lingkungan Micro-Frontend berbasis Shadow DOM, dan bagaimana solusinya?
8. Bagaimana implementasi `composed: true` pada instance `CustomEvent` memengaruhi penjalaran event melintasi batas (*boundary*) Shadow DOM ke Host DOM tree?
9. Apa bahaya terbesar dari penggunaan Dynamic Remote Injection (`document.createElement('script')`) ditinjau dari aspek keamanan web (Security Vector), dan tindakan mitigasi apa yang wajib diterapkan?
10. Terangkan perbedaan mendasar antara implementasi Micro-Frontend berbasis **Build-Time Integration** (misal: npm packages) dibandingkan **Runtime Integration** (misal: Module Federation) dari sudut pandang siklus rilis dan skalabilitas tim!

---

#### Bagian 3: Skenario Kasus Produksi
11. **Kasus 1**: Pada dashboard perbankan, squad A merilis update MFE "Kartu Kredit". Pengguna yang sedang membuka aplikasi tiba-tiba mendapati seluruh layar menjadi putih (*Blank Page*). Hasil log Sentry mencatat error: `ChunkLoadError: Loading chunk 404 failed`. Selidiki penyebab kegagalan ini terkait siklus rilis CI/CD dan jelaskan cara perbaikannya!
12. **Kasus 2**: Tim analitik perusahaan memasang script pelacak global di Host Shell. Namun, modul MFE "Checkout" yang berada di dalam encapsulation Shadow DOM melaporkan bahwa event klik tombol nasabah tidak pernah tercatat di dashboard analitik. Analisis mengapa ini terjadi dan bagaimana arsitektur event-routing yang tepat!
13. **Kasus 3**: Sebuah aplikasi Shell memuat 4 buah Remote MFE secara bersamaan pada landing page pertama. Lighthouse Score aplikasi anjlok dengan metrik TBT (Total Blocking Time) > 1.2 detik dan LCP > 4.5 detik. Setelah diaudit, terjadi eksekusi script overhead yang masif pada fase startup. Buat strategi optimasi sistematis untuk merestrukturisasi pemuatan keempat MFE tersebut!

---

### 16. Summary
Arsitektur Micro-Frontend berbasis Module Federation pada level enterprise bukan sekadar pemecahan bundle aplikasi, melainkan integrasi sistem terdistribusi di sisi klien (*client-side distributed systems*). 

Kunci keberhasilan implementasi produksi bertumpu pada 4 pilar arsitektur:
1. **Runtime Orchestration yang Dinamis**: Pemuatan modul via Manifest Registry untuk menjamin independensi rilis penuh antar tim.
2. **Strict Shared Dependency Boundary**: Pencegahan duplikasi framework via runtime SemVer negotiation untuk menjaga Core Web Vitals.
3. **Decoupled System Communication**: Pertukaran data yang agnostik dan bebas *memory leak* melalui Event-Driven Protocol.
4. **Resilience Engineering**: Penerapan isolasi kegagalan (*Circuit Breakers*, *Error Boundaries*, *Degraded Fallbacks*) sehingga crash pada satu modul tidak pernah meruntuhkan keseluruhan platform bisnis.