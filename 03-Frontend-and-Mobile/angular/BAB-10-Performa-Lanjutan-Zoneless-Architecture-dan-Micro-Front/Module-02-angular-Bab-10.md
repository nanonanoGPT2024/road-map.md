# Kurikulum Tingkat Enterprise: Angular (03-Frontend-and-Mobile)
## Bab 10: Performa Lanjutan, Zoneless Architecture, dan Micro-Frontend
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal/Senior Frontend Engineer mampu:
1. **Mengonstruksi dan Mengoperasikan Arsitektur Zoneless** pada Angular modern menggunakan `provideExperimentalZonelessChangeDetection()`, mengeliminasi overhead eksekusi `zone.js`, dan mengelola reaktivitas mutlak berbasis Angular Signals.
2. **Mendesain Arsitektur Micro-Frontend (MFE) Skala Enterprise** dengan `@angular-architects/native-federation` berbasis standar platform web (ESM/Import Maps), memitigasi ketergantungan pada bundler proprietary.
3. **Membangun Mekanisme Komunikasi Antar-MFE yang Decoupled** menggunakan reactive cross-boundary state sharing tanpa membocorkan memory leak antar-container.
4. **Mengimplementasikan Resilience dan Fault Tolerance Pattern** pada runtime federasi (Circuit Breaker, Dynamic Remote Manifest, dan Graceful UI Degradation via `@defer` blocks).
5. **Mengaudit, Mendiagnosis, dan Mengatasi Bottleneck Performa** terkait shared singleton single-instance conflicts, synchronous microtask queuing, dan cross-micro-frontend style/DOM bleeding.

---

### 2. Prerequisite

Peserta wajib menguasai kompetensi dasar hingga intermediate berikut:
- Pemahaman mendalam tentang **Angular Change Detection** standar (`Default` vs `OnPush`), LView/TView data structure internals.
- Penguasaan penuh primitives **Angular Signals**: `signal()`, `computed()`, `effect()`, `untracked()`, serta interoperabilitas RxJS (`toSignal`, `toObservable`).
- Konsep runtime browser: JavaScript Event Loop, Microtask Queue vs Macrotask Queue, Web APIs, dan native Browser ES Modules (ESM).
- Arsitektur Microservices/Micro-Frontends: Konsep Host (Shell) vs Remote, Shared Dependencies, dan CORS policy pada distributed frontend assets.
- Node.js versi 20+ LTS, Angular CLI v18+, dan TypeScript 5.4+.

---

### 3. Concept & Internal Architecture

#### 3.1. Internal Engine: Dari Zone.js ke Reactive Zoneless Scheduler

Secara historis, Angular bergantung pada `zone.js` untuk mendeteksi kapan sinkronisasi State-ke-DOM harus dijalankan. `zone.js` melakukan *monkey-patching* terhadap seluruh API asinkron browser:

```
[Browser Web APIs] (setTimeout, fetch, addEventListener, Promise)
        ▲
        │ (Monkey-Patched oleh zone.js)
[NgZone Outer/Inner Execution Context]
        │ (Menembakkan onMicrotaskEmpty)
[ApplicationRef.tick()] ──▶ Traversing Component Tree dari Root
```

Kelemahan arsitektur ini di skala enterprise:
1. **Payload Cost**: ~35-40 KB gzipped payload hanya untuk runtime Zone.js.
2. **Overhead Eksekusi**: Setiap kali sebuah event kecil (seperti `mousemove` atau micro-Promise internal) dieksekusi, `onMicrotaskEmpty` dipicu, menyebabkan Angular memeriksa komponen yang tidak mengalami perubahan state.
3. **Async/Await Transpilation**: `zone.js` tidak dapat mencegat native JavaScript `async`/`await` secara langsung tanpa me-transpile sintaksis tersebut ke generator atau Promise ES5/ES2015, yang mendegradasi performa engine V8.

##### Zoneless Change Detection Scheduler

Pada arsitektur **Zoneless**, Angular mengeliminasi `zone.js` sepenuhnya dan beralih ke engine reaktif internal berbasis `ChangeDetectionScheduler`:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ZONELESS ARCHITECTURE                           │
└────────────────────────────────────────────────────────────────────────┘

 [Signal Writes / set()]     [Async Pipe]     [Component Events / Output]
            │                     │                        │
            ▼                     ▼                        ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │                      NotificationSource Engine                       │
 │      (Menandai LView flag: Consumer Dirty & Traversing Path)          │
 └──────────────────────────────────┬───────────────────────────────────┘
                                    │
                                    ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │                    ChangeDetectionScheduler                          │
 │  (Mengkonsolidasi batch notifications via requestAnimationFrame/      │
 │   queueMicrotask untuk mencegah multiple layout thrashing)            │
 └──────────────────────────────────┬───────────────────────────────────┘
                                    │
                                    ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │                     Targeted Template Refresh                        │
 │  (Hanya mengeksekusi refreshView() pada komponen berstatus Dirty)     │
 └──────────────────────────────────────────────────────────────────────┘
```

Scheduler mengandalkan notifikasi eksplisit dari tiga sumber utama:
1. Primitif Signals yang dibaca di template mengalami perubahan nilai (`producer` memberitahu `consumer`).
2. Komponen memicu UI Event handler yang diikat via template binding (misalnya `(click)="handler()"`).
3. Pemanggilan eksplisit `ChangeDetectorRef.markForCheck()` atau binding via `AsyncPipe`.

#### 3.2. Native Federation Architecture

Arsitektur micro-frontend berbasis bundler lama (seperti Webpack 5 Module Federation) mengikat Host dan Remote ke compiler yang sama. Native Federation memecahkan masalah ini dengan memanfaatkan native browser primitives: **Import Maps** dan **ES Modules (ESM)**.

```
┌───────────────────────────────────────────────────────────────────────┐
│                           HOST APPLICATION                            │
│                                                                       │
│  import { initFederation } from '@angular-architects/native-federation'│
│                                                                       │
│  1. Fetch `federation.manifest.json`                                  │
│  2. Resolusi Shared Dependencies (Angular Core, Common, Signals)       │
│  3. Menulis dynamic native <script type="importmap"> ke DOM            │
└───────────────────┬───────────────────────────────┬───────────────────┘
                    │                               │
       Dynamic HTTP │ GET remoteEntry.json          │ Dynamic ESM import()
                    ▼                               ▼
     ┌────────────────────────────┐   ┌────────────────────────────┐
     │      REMOTE A (Billing)    │   │      REMOTE B (Catalog)    │
     │ - remoteEntry.json         │   │ - remoteEntry.json         │
     │ - exposed billing.module.js│   │ - exposed catalog.comp.js  │
     │ - shared libs (hashes)     │   │ - shared libs (hashes)     │
     └────────────────────────────┘   └────────────────────────────┘
```

Tahapan Inisialisasi Native Federation:
1. **Manifest Loading**: Host membaca berkas JSON konfigurasi runtime (`federation.manifest.json`).
2. **Dependency Negotiation**: Host dan seluruh Remote bertukar metadata paket shared (`@angular/core`, `rxjs`). Algoritma menentukan versi kompatibel tertinggi yang memenuhi rentang SemVer.
3. **Import Map Synthesis**: Browser menginjeksi elemen `<script type="importmap">` yang memetakan bare-import specifiers (misalnya `import { Component } from '@angular/core'`) langsung ke URL chunk JavaScript yang di-*share* secara runtime.
4. **Isolated Module Loading**: Komponen remote dimuat via native `import(/* webpackIgnore: true */ remoteUrl)` tanpa wrapper runtime proprietary.

---

### 4. Why & What

| Dimensi | Pendekatan Klasik (Zone.js + Monolithic/Webpack MFE) | Pendekatan Modern (Zoneless + Native Federation) | Dampak Enterprise |
| :--- | :--- | :--- | :--- |
| **Runtime Overhead** | Engine `zone.js` membebani memory; inspeksi dirty-checking bersifat top-down cascade. | Dirty checking terisolasi pada targeted reactive graph; zero monkey-patching. | Penurunan Interaction to Next Paint (INP) hingga 40-60%. |
| **Bundle Footprint** | Beban bawaan `zone.js` (~36 KB) + overhead code-splitting Webpack runtime bootstrap. | Murni ESM standar; bundle dasar terpangkas signifikan; engine tree-shaking lebih agresif. | First Contentful Paint (FCP) dan Total Blocking Time (TBT) berkurang signifikan. |
| **Bundler Dependency** | Host dan Remote terkunci secara ketat (*tightly coupled*) pada Webpack versi tertentu. | Bundler-agnostic (Vite, Esbuild, Webpack) karena berbasis spesifikasi W3C Import Maps. | Siklus hidup upgrade dependensi remote terisolasi sepenuhnya antar-skuad. |
| **Error Isolation** | Unhandled exception di satu komponen dalam Zone dapat merusak deteksi siklus hidup global. | Error terisolasi pada sub-tree reaktif; boundary MFE dapat ditangani via Error Boundary. | Downtime regional tidak melumpuhkan seluruh platform perbankan/dashboard. |

---

### 5. How (Workflow Detail)

Alur migrasi dan eksekusi platform dari Zone-based Monolith menuju Zoneless Micro-Frontend:

```
[FASE 1: Zoneless Migration]
  1. Hapus 'zone.js' dan 'zone.js/testing' dari angular.json (polyfills array).
  2. Tambahkan `provideExperimentalZonelessChangeDetection()` pada ApplicationConfig.
  3. Konversi seluruh mutable state ke Angular Signals (`signal`, `computed`).
  4. Ganti event listening manual window/document dengan inject(DestroyRef) & takeUntilDestroyed.

[FASE 2: Native Federation Setup]
  1. Jalankan schematics: `ng g @angular-architects/native-federation:init --type dynamic-host`
  2. Pada remote: `ng g @angular-architects/native-federation:init --type remote --port 4201`
  3. Konfigurasi `federation.config.js` untuk mengekspos domain modules dan mendefinisikan shared libraries.

[FASE 3: Runtime Orchestration]
  1. Host mengambil manifest konfigurasi endpoint remote secara dinamis via API backend/CDN.
  2. Host memanggil `initFederation('assets/federation.manifest.json')`.
  3. Dynamic routing menggunakan fungsi `loadRemoteModule()` untuk meresolusi remote bundles.
  4. Komunikasi state antar-MFE dijaga menggunakan Signal Stores berbasis token injection atau window-level shared event bus.
```

---

### 6. Analogy & Diagram ASCII

#### 6.1. Analogi
- **Zone.js (Sistem Patroli Satpam Terpusat)**: Bayangkan sebuah gedung kantor besar (aplikasi web). Setiap kali ada kurir mengantar paket, telepon berdering, atau seseorang menekan tombol lift (event asinkron), satpam kantor (`zone.js`) harus berjalan memeriksa setiap ruangan dari lantai teratas hingga lantai terbawah (`root tick checking`) untuk melihat apakah ada dokumen yang berpindah meja. Ini menghabiskan tenaga dan waktu.
- **Zoneless + Signals (Sistem Sensor Pintar Langsung)**: Setiap meja kerja memiliki sensor inframerah (`Signal`). Ketika dokumen baru diletakkan di sebuah meja, sensor tersebut langsung menyalakan lampu peringatan tepat di ruangan tersebut. Tim kebersihan (`Renderer`) langsung bergerak ke meja tersebut tanpa perlu memeriksa ruangan lain yang tidak aktif.

#### 6.2. Diagram Interaksi Zoneless Micro-Frontend

```
+---------------------------------------------------------------------------------------+
| HOST SHELL CONTAINER (Browser Window Context)                                         |
|                                                                                       |
|  +-------------------------+     initFederation()     +-----------------------------+  |
|  |   AppRoot (Zoneless)    | -----------------------> | ESM Import Map Manager      |  |
|  +-------------------------+                          +-----------------------------+  |
|               |                                                      |                |
|               | Dynamic Router Navigation                            | Resolves ESM   |
|               ▼                                                      ▼                |
|  +-------------------------------------+             +------------------------------+ |
|  | <router-outlet>                     |             | Shared Singleton Context     | |
|  |                                     |             | - @angular/core (Zoneless CD)| |
|  |  +-------------------------------+  |             | - SharedStateService (Signal)| |
|  |  | @defer (on viewport)          |  |             +------------------------------+ |
|  |  |                               |  |                             ▲                |
|  |  |  +-------------------------+  |  | Dynamic Module Loading      │                |
|  |  |  | REMOTE: Payment Remote   |  |  | (HTTP GET port 4201)        │ Reference      |
|  |  |  | (Zoneless, Signal-Driven)| -+--+-----------------------------+                |
|  |  |  +-------------------------+  |  |                                              |
|  |  |                               |  |                                              |
|  |  |  @placeholder { <Skeleton/> } |  |                                              |
|  |  |  @error { <FallbackUI/> }     |  |                                              |
|  |  +-------------------------------+  |                                              |
|  +-------------------------------------+                                              |
+---------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Inisialisasi Zoneless Application

Berkas: `src/app/app.config.ts`
```typescript
import { ApplicationConfig, provideExperimentalZonelessChangeDetection } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    // Mengaktifkan Scheduler Zoneless native, meniadakan ketergantungan zone.js
    provideExperimentalZonelessChangeDetection(),
    provideRouter(routes, withComponentInputBinding())
  ]
};
```

Berkas: `src/app/counter-zoneless.component.ts`
```typescript
import { Component, signal, computed, ChangeDetectionStrategy } from '@angular/core';

@Component({
  selector: 'app-counter-zoneless',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="p-4 border rounded shadow">
      <h2>Zoneless Reactive Counter</h2>
      <p>Current Count: <strong>{{ count() }}</strong></p>
      <p>Double Count: <strong>{{ doubleCount() }}</strong></p>
      <button (click)="increment()" class="px-4 py-2 bg-blue-600 text-white rounded">
        Increment Value
      </button>
    </div>
  `
})
export class CounterZonelessComponent {
  // Pure Signal State
  readonly count = signal<number>(0);
  
  // Derivasi state otomatis tanpa Zone dirty checking
  readonly doubleCount = computed(() => this.count() * 2);

  increment(): void {
    this.count.update((v) => v + 1);
  }
}
```

#### 7.2. Practical Enterprise Example: Host Shell & Dynamic Federated Remote

##### A. Konfigurasi Remote (`projects/mfe-payment/federation.config.js`)
```javascript
const { withNativeFederation, shareAll } = require('@angular-architects/native-federation/config');

module.exports = withNativeFederation({
  name: 'mfe-payment',
  filename: 'remoteEntry.json',
  exposes: {
    // Mengekspos entry point komponen transaksi pembayaran
    './PaymentProcessor': './projects/mfe-payment/src/app/payment/payment-processor.component.ts',
  },
  shared: {
    ...shareAll({
      singleton: true,
      strictVersion: true,
      requiredVersion: 'auto'
    }),
  },
  skip: [
    'rxjs/ajax',
    'rxjs/fetch',
    'rxjs/testing',
    'rxjs/webSocket'
  ]
});
```

##### B. Remote Component (`projects/mfe-payment/src/app/payment/payment-processor.component.ts`)
```typescript
import { Component, signal, inject, OnInit, ChangeDetectionStrategy, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';

export interface TransactionPayload {
  transactionId: string;
  amount: number;
  currency: string;
}

@Component({
  selector: 'mfe-payment-processor',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="payment-card p-6 bg-slate-900 text-white rounded-xl border border-slate-700">
      <h3 class="text-xl font-bold mb-4">Secure Payment Terminal (Remote MFE)</h3>
      <div class="mb-4">
        <label class="block text-sm text-slate-400">Merchant Reference</label>
        <span class="font-mono text-emerald-400">{{ referenceCode() }}</span>
      </div>
      <div class="mb-4">
        <label class="block text-sm text-slate-400">Total Payable</label>
        <span class="text-2xl font-bold">{{ currency() }} {{ amount() }}</span>
      </div>
      
      <button 
        [disabled]="isProcessing()" 
        (click)="executePayment()"
        class="w-full py-3 bg-emerald-500 hover:bg-emerald-600 disabled:bg-slate-600 rounded-lg font-semibold transition-all">
        @if (isProcessing()) {
          <span>Authorizing Transaction via HSM...</span>
        } @else {
          <span>Submit Settlement</span>
        }
      </button>
    </div>
  `
})
export class PaymentProcessorComponent implements OnInit {
  // Modern Component Inputs via Signal
  readonly amount = input.required<number>();
  readonly currency = input<string>('USD');
  readonly referenceCode = input.required<string>();

  // Event Outputs
  readonly paymentCompleted = output<TransactionPayload>();
  readonly paymentFailed = output<string>();

  readonly isProcessing = signal<boolean>(false);

  ngOnInit(): void {
    // Validasi invariant enterprise pada inisialisasi lifecycle
    if (this.amount() <= 0) {
      throw new Error(`[PaymentProcessor] Invalid amount: ${this.amount()}`);
    }
  }

  async executePayment(): Promise<void> {
    this.isProcessing.set(true);

    try {
      // Simulasi panggilan Secure Vault Payment Gateway (Promise Native - Tanpa Zone.js)
      const confirmation = await this.mockPaymentGatewayCall({
        amount: this.amount(),
        currency: this.currency(),
        reference: this.referenceCode()
      });

      this.paymentCompleted.emit(confirmation);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown gateway timeout';
      this.paymentFailed.emit(errorMessage);
    } finally {
      // Zoneless scheduler secara otomatis mengenali update Signal ini
      this.isProcessing.set(false);
    }
  }

  private mockPaymentGatewayCall(data: { amount: number; currency: string; reference: string }): Promise<TransactionPayload> {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        if (data.amount > 1000000) {
          reject(new Error('Transaction limits exceeded: AML Verification required.'));
        } else {
          resolve({
            transactionId: `TXN-${Math.random().toString(36).substring(2, 9).toUpperCase()}`,
            amount: data.amount,
            currency: data.currency
          });
        }
      }, 1500);
    });
  }
}
```

##### C. Konfigurasi Host Dynamic Route & Bootstrap (`projects/host-shell/src/app/app.routes.ts`)
```typescript
import { Routes } from '@angular/router';
import { loadRemoteModule } from '@angular-architects/native-federation';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./home.component').then((m) => m.HomeComponent)
  },
  {
    path: 'checkout',
    // Dynamic Federated Lazy Loading dengan fallback error boundary
    loadComponent: () =>
      loadRemoteModule({
        remoteName: 'mfe-payment',
        exposedModule: './PaymentProcessor'
      })
      .then((m) => m.PaymentProcessorComponent)
      .catch((err) => {
        console.error('Remote MFE Payment fails to load. Initiating Circuit Breaker.', err);
        return import('./fallback/payment-fallback.component').then((m) => m.PaymentFallbackComponent);
      })
  }
];
```

##### D. Host Container Viewport Deferral (`projects/host-shell/src/app/checkout-wrapper.component.ts`)
```typescript
import { Component, signal, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PaymentFallbackComponent } from './fallback/payment-fallback.component';
import { TransactionPayload } from './models/payment.types';

@Component({
  selector: 'app-checkout-wrapper',
  standalone: true,
  imports: [CommonModule, PaymentFallbackComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="max-w-xl mx-auto py-10">
      <h1 class="text-2xl font-bold mb-6">Enterprise Checkout Infrastructure</h1>
      
      <!-- Defer block dengan native Zoneless Change Detection Scheduler -->
      @defer (on viewport; prefetch on idle) {
        <ng-container *ngComponentOutlet="paymentComponent(); inputs: paymentInputs()" />
      } @placeholder (minimum 300ms) {
        <div class="animate-pulse h-64 bg-slate-800 rounded-xl flex items-center justify-center text-slate-500">
          Mounting Secure Remote Container...
        </div>
      } @loading {
        <div class="p-4 text-cyan-400">Loading federated chunk over network...</div>
      } @error {
        <app-payment-fallback [errorMessage]="'Failed to stream micro-frontend container.'" />
      }
    </div>
  `
})
export class CheckoutWrapperComponent {
  readonly paymentComponent = signal<any>(null);
  
  readonly paymentInputs = signal({
    amount: 75000,
    currency: 'USD',
    referenceCode: 'INV-2026-X99'
  });

  constructor() {
    this.loadPaymentFederatedComponent();
  }

  private async loadPaymentFederatedComponent(): Promise<void> {
    try {
      const { loadRemoteModule } = await import('@angular-architects/native-federation');
      const module = await loadRemoteModule({
        remoteName: 'mfe-payment',
        exposedModule: './PaymentProcessor'
      });
      this.paymentComponent.set(module.PaymentProcessorComponent);
    } catch (e) {
      console.error('Failed to resolve payment module in wrapper', e);
    }
  }

  handleSuccess(event: TransactionPayload): void {
    console.warn(`[Audit Trail] Transaction Confirmed: ${event.transactionId}`);
  }
}
```

---

### 8. Real World Case Study: Arsitektur Perbankan Skala Enterprise

#### 8.1. Konteks Skenario
Sebuah institusi perbankan tier-1 memiliki portal *Corporate Treasury Management*. Portal ini dikembangkan oleh 4 skuad terpisah:
- **Core Shell Squad**: Menguasai Navigation, Security Identity Context, dan Zoneless Master Layout.
- **Account Summary Squad**: Mengelola visualisasi saldo dan mutasi ledger ribuan rekening secara real-time via WebSockets.
- **Fx-Trading Remote Squad**: Membutuhkan eksekusi sub-milidetik untuk streaming nilai tukar mata uang valas (high frequency update).
- **Payment & Clearing Squad**: Mengatur instruksi pengiriman uang massal (SKN/RTGS/SWIFT).

#### 8.2. Permasalahan Arsitektur
1. Saat Fx-Trading menerima update data via WebSocket sebanyak 60 FPS, aplikasi berbasis `zone.js` mengeksekusi `ApplicationRef.tick()` pada seluruh pohon komponen. Dampaknya, input form di skuad *Payment* mengalami *keyboard typing latency* sebesar >180ms (kategori *Poor* pada metrik INP).
2. Skuad *Fx-Trading* menggunakan chart engine WebGL yang berat. Ketika library ini di-*bundle* di aplikasi monolitik, First Contentful Paint (FCP) melonjak hingga 4.8 detik di koneksi VPN korporat.

#### 8.3. Solusi Arsitektural
1. **Migrasi Host & Remotes ke Full Zoneless**: Mengadopsi `provideExperimentalZonelessChangeDetection()`. WebSocket stream di Fx-Trading dipetakan langsung ke Angular Signals lokal. Komponen yang tidak membaca signal tersebut **nol persen** terpengaruh oleh dirty-checking overhead.
2. **Native Federation dengan Dynamic Manifest**: Dynamic routing berdasarkan peran otorisasi karyawan (RBAC) via backend-driven JSON manifest.
3. **Cross-Boundary Reactive State**: Menggunakan Shared Encapsulated Token Bus untuk sinkronisasi token JWT tanpa coupling instance runtime.

```typescript
// Shared Identity Library (@enterprise/auth-context)
// Dipetakan sebagai singleton di federation.config.js
import { Injectable, signal, computed } from '@angular/core';

export interface SessionToken {
  sub: string;
  roles: string[];
  accessToken: string;
  exp: number;
}

@Injectable({ providedIn: 'root' })
export class EnterpriseSessionContext {
  private readonly _session = signal<SessionToken | null>(null);

  // Read-only Signal exposed to all MFEs
  readonly session = this._session.asReadonly();
  readonly isAuthenticated = computed(() => !!this._session() && (this._session()!.exp * 1000 > Date.now()));
  readonly roles = computed(() => this._session()?.roles ?? []);

  setSession(token: SessionToken): void {
    this._session.set(token);
  }

  clearSession(): void {
    this._session.set(null);
  }

  hasRole(requiredRole: string): boolean {
    return this.roles().includes(requiredRole);
  }
}
```

#### 8.4. Hasil Metrik Pasca Implementasi
- **INP (Interaction to Next Paint)**: Turun dari 185ms ke 18ms (penurunan 90.2%).
- **Lighthouse Performance Score**: Naik dari 54 menjadi 96.
- **Initial JavaScript Transfer**: Turun dari 3.4 MB menjadi 280 KB (Host Shell initial bundle). Remote chunks di-stream secara on-demand via `@defer`.

---

### 9. Trade-offs & Arsitektur Alternatif

| Kategori | Keputusan Arsitektur | Keuntungan | Kerugian & Konsekuensi | Skenario Mitigasi |
| :--- | :--- | :--- | :--- | :--- |
| **Change Detection** | Zoneless (`provideExperimentalZonelessChangeDetection`) | Mengeliminasi runtime overhead `zone.js`; optimasi native V8 engine; INP sangat stabil. | Library pihak ketiga (3rd party UI libraries jadul) yang mengandalkan mutable property update tanpa Signal/Event akan macet (*UI freeze*). | Bungkus pemanggilan library legacy menggunakan `ChangeDetectorRef.markForCheck()` atau audit dependencies sebelum migrasi. |
| **Federasi Arsitektur** | Native Federation (W3C Import Maps / ESM) | Bebas dependensi bundler; build super cepat via Esbuild/Vite; isolasi build dependency. | Memerlukan browser modern yang mendukung Import Maps (Chromium 89+, Safari 16.4+, Firefox 108+). Polyfill dibutuhkan jika mendukung platform lawas. | Terapkan `es-module-shims` pada `index.html` Host Shell untuk legacy browser enterprise. |
| **State Sharing** | Shared Singleton Library via Scope Federation | Penggunaan memori rendah; referensi state sinkron secara global. | Risiko *version mismatch* tinggi. Jika satu Remote mengompilasi versi Angular berbeda dengan breaking change internal, runtime crash total. | Terapkan `strictVersion: true` dan bangun automated contract testing pada CI/CD pipeline federasi. |
| **Dynamic Remotes** | Manifest-Driven Backend Registry | Deploy remote MFE independen tanpa perlu re-compile/re-deploy Host Shell. | Risiko transient failure: Jika CDN remote down, host berisiko menampilkan blank page jika error handling tidak didesain ketat. | Implementasikan Circuit Breaker pattern dan Fallback UI pada level routing wrapper. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Fatal: Menggunakan Mutasi Objek Tradisional pada Zoneless
```typescript
// FATAL ERROR PADA ZONELESS:
@Component({
  template: `<div>{{ user.name }}</div>`
})
export class BadZonelessComponent {
  user = { name: 'Budi' };

  updateUser(): void {
    // Pada Zone.js, ini berhasil karena event handler memicu global tick.
    // Pada Zoneless, scheduler TIDAK MENERIMA NOTIFIKASI jika ini bukan Signal
    // atau tanpa intervensi ChangeDetectorRef!
    setTimeout(() => {
      this.user.name = 'Andi'; // DOM TIDAK AKAN PERNAH BERUBAH!
    }, 1000);
  }
}

// SOLUSI BENAR ENTERPRISE:
@Component({
  template: `<div>{{ user().name }}</div>`
})
export class CorrectZonelessComponent {
  readonly user = signal({ name: 'Budi' });

  updateUser(): void {
    setTimeout(() => {
      this.user.set({ name: 'Andi' }); // Signal otomatis memberitahu Scheduler
    }, 1000);
  }
}
```

#### 10.2. Dependency Version Skew: Multiple Copies of `@angular/core`
*Gejala*: Error runtime `NG0203: inject() must be called from an injection context` atau kegagalan inisialisasi Signal lintas MFE.
*Akar Masalah*: Host dan Remote memuat dua instance `@angular/core` yang berbeda ke dalam memori runtime karena deklarasi `federation.config.js` tidak menetapkan rule `singleton: true`.

*Solusi Perbaikan*:
Pastikan konfigurasi `federation.config.js` Host dan Remote identik pada level shared core:
```javascript
// federation.config.js
module.exports = withNativeFederation({
  shared: {
    '@angular/core': { singleton: true, strictVersion: true, requiredVersion: '^18.0.0' },
    '@angular/common': { singleton: true, strictVersion: true, requiredVersion: '^18.0.0' },
    '@angular/router': { singleton: true, strictVersion: true, requiredVersion: '^18.0.0' },
    'rxjs': { singleton: true, strictVersion: true, requiredVersion: '^7.8.0' }
  }
});
```

#### 10.3. Memory Leak Lintas Boundary Micro-Frontend
*Penyebab*: Remote MFE menambahkan global listener (`window.addEventListener('message')` atau `document.addEventListener`) tanpa membersihkannya saat remote komponen di-unmount oleh Angular router Host.

*Solusi*:
Gunakan `DestroyRef` native Angular untuk menggaransi unregistering callback secara deterministik:
```typescript
import { Component, inject, DestroyRef, OnInit } from '@angular/core';

@Component({ standalone: true, template: `...` })
export class LeakFreeRemoteComponent implements OnInit {
  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    const handleGlobalMessage = (event: MessageEvent) => {
      // Logic pemrosesan data
    };

    window.addEventListener('message', handleGlobalMessage);

    // Lifecycle clean up otomatis saat MFE di-unmount
    this.destroyRef.onDestroy(() => {
      window.removeEventListener('message', handleGlobalMessage);
    });
  }
}
```

---

### 11. Best Practices (Production Checklist)

#### 11.1. Checklist Arsitektur Zoneless
- [ ] Paket `zone.js` telah dihapus seutuhnya dari `dependencies` di `package.json` dan entri `polyfills` di `angular.json`.
- [ ] Provider `provideExperimentalZonelessChangeDetection()` terdaftar di root application level.
- [ ] Seluruh komponen menggunakan `ChangeDetectionStrategy.OnPush` sebagai proteksi struktural.
- [ ] Tidak ada penggunaan mutable fields internal yang diikat langsung ke template tanpa `signal()`.
- [ ] Semua asynchronous stream (RxJS) di template dikonsumsi menggunakan `toSignal()` atau `AsyncPipe`.
- [ ] Operasi DOM langsung (Direct DOM mutation) dieliminasi; seluruh mutasi view didorong melalui state signal.

#### 11.2. Checklist Micro-Frontend & Native Federation
- [ ] CORS headers (`Access-Control-Allow-Origin: *` atau whitelist domain host) terkonfigurasi dengan benar pada server origin/CDN penyedia remote assets.
- [ ] Host dan Remote mengunci konfigurasi core singleton libraries (`@angular/core`, `@angular/common`, dsb.).
- [ ] Setiap Remote module loading dibungkus dengan Error Boundary pattern (`try/catch` atau fallback `@error` pada `@defer`).
- [ ] Berkas `federation.manifest.json` diarahkan ke dynamic backend gateway untuk mendukung zero-downtime rolling updates.
- [ ] Menggunakan CSS scoping (Shadow DOM atau Angular default `ViewEncapsulation.Emulated`) untuk mencegah Global Style Bleeding antar-MFE.

---

### 12. Hands-on Practice

Struktur direktori kerja:
```
hands-on/m02/
├── host-shell/
│   ├── src/
│   │   ├── app/
│   │   │   ├── app.config.ts
│   │   │   ├── app.routes.ts
│   │   │   └── app.component.ts
│   │   └── assets/
│   │       └── federation.manifest.json
│   ├── federation.config.js
│   └── angular.json
└── remote-analytics/
    ├── src/
    │   └── app/
    │       └── analytics/
    │           ├── analytics-dashboard.component.ts
    │           └── analytics.service.ts
    ├── federation.config.js
    └── angular.json
```

#### Langkah 1: Setup Proyek & Konfigurasi Zoneless Host
Jalankan di terminal:
```bash
# Inisialisasi workspace monorepo
npx -y @angular/cli@18 new hands-on-m02 --create-application=false --directory=hands-on/m02
cd hands-on/m02
ng g application host-shell --routing --style=css --inline-style=false
ng g application remote-analytics --routing --style=css --inline-style=false

# Install Native Federation
npm i -D @angular-architects/native-federation
```

#### Langkah 2: Konfigurasi Polyfill dan Zoneless pada Host
Edit `hands-on/m02/host-shell/src/app/app.config.ts`:
```typescript
import { ApplicationConfig, provideExperimentalZonelessChangeDetection } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideExperimentalZonelessChangeDetection(),
    provideRouter(routes, withComponentInputBinding())
  ]
};
```

Pastikan pada `hands-on/m02/host-shell/project.json` (atau `angular.json`), entri `polyfills` tidak lagi memuat `zone.js`.

#### Langkah 3: Konfigurasi Federation Config Remote Analytics
Buat file `hands-on/m02/remote-analytics/federation.config.js`:
```javascript
const { withNativeFederation, shareAll } = require('@angular-architects/native-federation/config');

module.exports = withNativeFederation({
  name: 'remote-analytics',
  filename: 'remoteEntry.json',
  exposes: {
    './Dashboard': './projects/remote-analytics/src/app/analytics/analytics-dashboard.component.ts'
  },
  shared: {
    ...shareAll({
      singleton: true,
      strictVersion: true,
      requiredVersion: 'auto'
    })
  }
});
```

#### Langkah 4: Buat Remote Analytics Component (Pure Zoneless Signals)
Buat `hands-on/m02/remote-analytics/src/app/analytics/analytics-dashboard.component.ts`:
```typescript
import { Component, signal, ChangeDetectionStrategy, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'mfe-analytics-dashboard',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div style="padding: 1.5rem; background: #1e293b; color: white; border-radius: 8px;">
      <h2 style="margin-top: 0; color: #38bdf8;">Analytics Real-Time Telemetry (Zoneless Remote)</h2>
      <div style="display: flex; gap: 2rem;">
        <div>
          <p style="color: #94a3b8; margin: 0;">Throughput / sec</p>
          <h3 style="font-size: 2rem; margin: 0;">{{ throughput() }} req/s</h3>
        </div>
        <div>
          <p style="color: #94a3b8; margin: 0;">Error Rate</p>
          <h3 style="font-size: 2rem; margin: 0; color: #f87171;">{{ errorRate() }}%</h3>
        </div>
      </div>
    </div>
  `
})
export class AnalyticsDashboardComponent implements OnInit, OnDestroy {
  readonly throughput = signal<number>(120);
  readonly errorRate = signal<number>(0.02);
  private timerId: any;

  ngOnInit(): void {
    // Pure async timer tanpa Zone.js
    this.timerId = setInterval(() => {
      this.throughput.set(Math.floor(100 + Math.random() * 50));
      this.errorRate.set(parseFloat((Math.random() * 0.05).toFixed(3)));
    }, 1000);
  }

  ngOnDestroy(): void {
    if (this.timerId) {
      clearInterval(this.timerId);
    }
  }
}
```

#### Langkah 5: Dynamic Routing Host Shell
Edit `hands-on/m02/host-shell/src/app/app.routes.ts`:
```typescript
import { Routes } from '@angular/router';
import { loadRemoteModule } from '@angular-architects/native-federation';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'analytics'
  },
  {
    path: 'analytics',
    loadComponent: () =>
      loadRemoteModule({
        remoteName: 'remote-analytics',
        exposedModule: './Dashboard'
      }).then((m) => m.AnalyticsDashboardComponent)
  }
];
```

#### Langkah 6: Host Manifest Configuration & Bootstrap
Edit `hands-on/m02/host-shell/src/assets/federation.manifest.json`:
```json
{
  "remote-analytics": "http://localhost:4201/remoteEntry.json"
}
```

Edit `hands-on/m02/host-shell/src/main.ts`:
```typescript
import { initFederation } from '@angular-architects/native-federation';

initFederation('/assets/federation.manifest.json')
  .catch((err) => console.error('Failed to initialize Native Federation', err))
  .then((_) => import('./bootstrap'))
  .catch((err) => console.error(err));
```

Pindahkan logika bootstrap aplikasi ke file baru `hands-on/m02/host-shell/src/bootstrap.ts`:
```typescript
import { bootstrapApplication } from '@angular/platform-browser';
import { AppComponent } from './app/app.component';
import { appConfig } from './app/app.config';

bootstrapApplication(AppComponent, appConfig)
  .catch((err) => console.error(err));
```

---

### 13. Exercise

#### Level Easy
Ubah sebuah komponen konvensional yang masih menggunakan `setTimeout` dan manual mutable state di bawah ini agar 100% kompatibel dan reaktif di lingkungan Zoneless tanpa memanggil `ChangeDetectorRef`:
```typescript
// Legacy Component to Refactor:
@Component({
  selector: 'app-easy-status',
  template: `<span>Server Status: {{ status }}</span>`
})
export class EasyStatusComponent {
  status = 'INITIALIZING';
  constructor() {
    setTimeout(() => { this.status = 'HEALTHY'; }, 2000);
  }
}
```

#### Level Medium
Buat sebuah Dynamic Error Boundary Component untuk Host Shell yang menangani error saat remote MFE gagal di-load (misal: port remote mati). Komponen fallback harus menyediakan tombol **"Retry Handshake"** yang mencoba memuat ulang remote entry point secara dinamis menggunakan `loadRemoteModule()` kembali tanpa me-refresh seluruh halaman browser.

#### Level Hard
Rancang dan implementasikan sebuah Cross-MFE Shared Signal Store (`EventAuditorStore`) menggunakan arsitektur Vanilla TypeScript (tanpa coupling dependency Angular Injection). State store ini harus:
1. Menampung log transaksi audit trail maksimum 100 entri.
2. Memfasilitasi subscribe/reactivity dari Host Shell maupun Remote MFE secara independen.
3. Terbebas dari memory leak jika salah satu Remote di-destroy berulang kali oleh router navigasi.

---

### 14. Challenge: Arsitektur Zero-Downtime Multi-Remote Resilience

#### Skenario Kasus Kompleks:
Sebuah platform E-Commerce Skala Global membagi aplikasinya menjadi 1 Host Shell dan 3 Remote:
1. `remote-catalog` (Port 4201)
2. `remote-cart` (Port 4202)
3. `remote-checkout` (Port 4203)

Arsitektur aplikasi berjalan 100% **Zoneless**. Sistem deployment menggunakan Kubernetes Rolling Update dengan multi-region CDN di mana URL hash dari remote bundles berubah setiap kali rilis.

#### Target Tantangan:
Rancang dan bangun arsitektur produksi lengkap yang mencakup:
1. **Dynamic Manifest Discovery**: Host Shell tidak boleh bergantung pada file statis `assets/federation.manifest.json`. Shell harus mengonsumsi endpoint API `/api/v1/mfe-manifest` yang mengembalikan URL remote entry terkini sesuai region klien.
2. **Version Mismatch Isolation**: Jika `remote-cart` secara tidak sengaja ter-deploy menggunakan breaking-change versi shared library internal (contoh: `@org/shared-ui` versi v3.0, sedangkan Host masih menggunakan v2.0), aplikasi tidak boleh memicu runtime White-Screen of Death (WSoD). Remote yang bermasalah harus masuk ke status isolasi (*Quarantine Mode*) dan merender antarmuka fallback minimal, sementara `remote-catalog` dan shell tetap beroperasi normal.
3. **Optimistic Cart State Synchronization**: Host dan seluruh Remote harus mengonsumsi data jumlah item di keranjang belanja melalui sinkronisasi reaktif Signals. Jika eksekusi network mutasi item gagal di background, state Signal harus melakukan rollback otomatis (*Rollback Transaction*) dan memicu event notifikasi global.

*Deliverable*: Serahkan rancangan arsitektur, diagram alur kegagalan, dan kode implementasi Host Dynamic Discovery Engine serta Custom Fallback Boundary Router.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Apa fungsi utama dari `provideExperimentalZonelessChangeDetection()` dalam konfigurasi aplikasi Angular?**
   - A. Menghapus router bawaan Angular dan beralih ke native browser routing.
   - B. Mematikan Angular Signals dan kembali ke arsitektur manual dirty checking.
   - C. Menginstruksikan Angular runtime untuk tidak mengandalkan Zone.js dan mengaktifkan scheduler berbasis Signals/NotificationSource.
   - D. Mengaktifkan kompilasi Ahead-of-Time (AOT) tingkat lanjut.

2. **Berapa payload size rata-rata yang dihemat dari JavaScript bundle awal ketika `zone.js` dieliminasi seutuhnya?**
   - A. Sekitar 1 - 2 KB.
   - B. Sekitar 35 - 50 KB (sebelum gzipping/kompresi network).
   - C. Lebih dari 500 KB.
   - D. 0 KB, karena ukurannya dipindahkan ke library lain.

3. **Spesifikasi web standar platform apa yang menjadi fondasi utama `@angular-architects/native-federation`?**
   - A. Web Workers dan SharedArrayBuffer.
   - B. W3C Import Maps dan native Browser ES Modules (ESM).
   - C. WebAssembly (Wasm).
   - D. CommonJS Modules.

4. **Bagaimana cara Angular Zoneless mendeteksi perubahan state pada template jika suatu nilai baru diberikan ke Signal?**
   - A. Melakukan polling setiap 16 milidetik ke seluruh memori heap.
   - B. Producer Signal menandai consumer node (LView) sebagai dirty dan memicu `ChangeDetectionScheduler`.
   - C. Menginterupsi kernel OS via native background thread.
   - D. Menjalankan traversal top-down dari root component seketika itu juga.

5. **Apa ekstensi file metadata default yang diekspos oleh Remote pada Native Federation?**
   - A. `manifest.xml`
   - B. `remoteEntry.js`
   - C. `remoteEntry.json`
   - D. `module-federation.config.ts`

#### Intermediate (5 Soal)
6. **Mengapa pemanggilan native JavaScript `async/await` lebih optimal secara performa pada arsitektur Zoneless dibanding dengan arsitektur berbasis Zone.js?**
   - A. Karena Zone.js tidak lagi perlu memecah dan mentranspile native `async/await` ke generator/Promise ES5 untuk pelacakan context.
   - B. Karena `async/await` pada Zoneless otomatis dijalankan di Web Worker terpisah.
   - C. Karena compiler Angular menghapus fungsi asynchronous tersebut dari AST.
   - D. Karena browser mematikan garbage collector untuk eksekusi fungsi tersebut.

7. **Konfigurasi `singleton: true` pada `federation.config.js` ditujukan untuk menyelesaikan masalah apa?**
   - A. Memastikan hanya ada satu instance package/library (misal: `@angular/core`) yang dimuat ke dalam runtime browser.
   - B. Membatasi pengguna aplikasi hanya bisa membuka satu tab browser.
   - C. Mengharuskan seluruh komponen didaftarkan sebagai Standalone Component tunggal.
   - D. Mengubah seluruh arsitektur routing menjadi Single Page tanpa lazy loading.

8. **Apa implikasi negatif jika developer melakukan mutasi state lokal `this.counter = this.counter + 1` (bukan Signal) di dalam callback asynchronous `fetch().then()` pada aplikasi Zoneless?**
   - A. Aplikasi melempar error `NullPointerException`.
   - B. Browser mengalami memory leak seketika.
   - C. Template tidak akan ter-refresh secara otomatis karena tidak ada notifikasi yang mencapai internal Scheduler.
   - D. Komponen secara otomatis di-destroy oleh Angular Garbage Collector.

9. **Fitur Angular apa yang ideal dipadukan dengan Native Federation untuk menunda streaming dan parsing chunk remote MFE hingga komponen masuk ke dalam viewport browser pengguna?**
   - A. Dynamic Directives (`ngComponentOutlet`) tanpa binding.
   - B. Blok `@defer (on viewport)`.
   - C. Resolvers pada Angular Router.
   - D. Directive `*ngIf="true"`.

10. **Bagaimana menangani masalah CORS jika remote chunks di-hosting pada AWS S3/CloudFront yang terpisah dari Host Shell?**
    - A. Memasang proxy reverse di client-side menggunakan Service Worker.
    - B. Mengatur header respons HTTP server asset remote dengan `Access-Control-Allow-Origin: *` (atau domain spesifik Host Shell) dan method `GET, OPTIONS`.
    - C. Mengonversi seluruh JavaScript bundle menjadi data URL Base64 inline.
    - D. Menghapus konfigurasi HTTPS pada seluruh host.

#### Skenario Kasus Produksi (3 Soal)

11. **Skenario Produksi 1**:
    Tim Anda meluncurkan Remote MFE baru untuk alur klaim asuransi. Saat diuji pada environment staging, navigasi ke route remote tersebut memicu error: `Error: Shared module @angular/core not found in shared scope`. Namun pada Host monolitik lama, error ini tidak pernah muncul. Apa diagnosa paling akurat dan tindakan mitigasinya?
    - A. CDN remote memblokir akses port 80; pindahkan ke HTTPS port 443.
    - B. Host gagal mengeksekusi `initFederation()` sebelum aplikasi Angular di-bootstrap; pisahkan bootstrapping ke file terpisah (`bootstrap.ts`) dan pastikan `initFederation()` selesai di `main.ts`.
    - C. Remote menggunakan versi CSS yang tidak valid; hapus import TailwindCSS dari remote.
    - D. Host memiliki versi node yang terlalu baru di server production.

12. **Skenario Produksi 2**:
    Sebuah aplikasi retail skala enterprise mengintegrasikan remote checkout. Tim remote menggunakan library third-party analytics yang melakukan manipulasi DOM via `document.getElementById('checkout-root')` secara langsung di luar Angular lifecycle. Pada arsitektur Zoneless, chart analytics sering kali hilang atau tidak ter-render saat navigasi bolak-balik. Apa solusi arsitektural yang paling elegan tanpa merusak prinsip Zoneless?
    - A. Memasang kembali `zone.js` ke seluruh aplikasi Host dan Remote.
    - B. Menggunakan Angular `ElementRef` dan membungkus inisialisasi library pihak ketiga di dalam fungsi `afterNextRender()` atau `afterRender()` pada Injection Context komponen.
    - C. Menghindari navigasi routing dan memaksa `window.location.reload()` setiap kali berpindah halaman.
    - D. Memindahkan script analytics langsung ke tag `<head>` pada `index.html` Host Shell.

13. **Skenario Produksi 3**:
    Pada saat rolling deployment remote MFE perbankan, sejumlah pengguna aktif menerima pesan error: `ChunkLoadError: Loading chunk failed` saat mencoba membuka sub-menu transfer dana, yang disebabkan karena hash file JS remote telah berubah di CDN akibat deployment versi baru. Pola arsitektur apa yang wajib diimplementasikan pada level Router Host untuk mengatasi masalah ini secara transparan bagi user?
    - A. Memasang polling berkala untuk me-reload browser user setiap 2 menit.
    - B. Mengimplementasikan Global Error Handler yang mendeteksi dynamic import failure, memperbarui cache manifest secara paksa di background, dan melakukan re-fetch chunk dengan auto-retry policy sebelum melempar exception ke UI.
    - C. Memaksa server mematikan fitur dynamic code-splitting dan menyatukan seluruh remote menjadi satu bundle raksasa.
    - D. Mengubah seluruh aplikasi remote menjadi iFrame statis.

---

### Kunci Jawaban & Rasionalisasi Quiz

1. **C** - `provideExperimentalZonelessChangeDetection()` mendaftarkan provider internal yang memberitahu Angular untuk mengabaikan `zone.js` dan murni mendengarkan event scheduler (Signals, output events, markForCheck).
2. **B** - Ukuran file bundle Zone.js mentah adalah sekitar ~35-50 KB. Menghapusnya menghasilkan penghematan network transfer dan parsing execution time secara instan.
3. **B** - Native Federation mengandalkan spesifikasi resmi W3C Import Maps dan native ESM browser, berbeda dengan Webpack Module Federation yang menggunakan custom runtime bootstrap.
4. **B** - Dalam arsitektur Zoneless, Signal write memicu cascading notification ke dependency graph-nya. Konsumen (komponen view) ditandai dirty, dan `ChangeDetectionScheduler` menjadwalkan pass rendering via microtask.
5. **C** - `@angular-architects/native-federation` menggunakan berkas manifest `remoteEntry.json` yang berisi metadata modul terekspos dan daftar shared dependencies beserta hash-nya.
6. **A** - Zone.js perlu me-monkey patch asynchronous operations. Karena native browser `async/await` menyembunyikan Promise di level V8 C++ engine, Zone.js terpaksa mentranspile sintaks native tersebut ke ES5 Promise, yang membebani kinerja runtime. Pada Zoneless, native `async/await` berjalan murni tanpa de-optimasi.
7. **A** - `singleton: true` menjamin bahwa satu dan hanya satu instance dari modul tersebut (seperti Angular core dependency injection container) yang aktif dalam memori browser bersama antara Host dan semua Remotes.
8. **C** - Zoneless engine tidak memiliki monkey-patching pada `setTimeout` atau `fetch`. Mutasi variabel biasa (bukan Signal) tidak mengirimkan sinyal apa pun ke `ChangeDetectionScheduler`, sehingga UI tidak akan bereaksi terhadap perubahan state tersebut.
9. **B** - `@defer (on viewport)` menunda evaluasi template dan fetching bundle hingga elemen placeholder memasuki viewport pengguna, sangat ideal untuk micro-frontend lazy loading.
10. **B** - Browser memblokir pengambilan cross-origin script/json via `fetch` atau ESM dynamic `import()` jika header CORS tidak dikonfigurasi secara eksplisit oleh server origin penyedia aset remote.
11. **B** - Shared scope dependensi Native Federation diinisialisasi melalui panggilan asynchronous `initFederation()`. Jika bootstrapping Angular dijalankan serentak sebelum promise tersebut selesai, import map belum siap dan resolusi `@angular/core` akan gagal total.
12. **B** - `afterNextRender()` dieksekusi tepat setelah Angular menyelesaikan pass rendering DOM pada browser, menjadikannya tempat paling aman untuk integrasi library pihak ketiga non-Angular tanpa merusak siklus hidup Zoneless.
13. **B** - Mengimplementasikan Custom Retry Strategy pada level dynamic loader atau Global Error Handler memungkinkan aplikasi mendeteksi URL chunk yang *stale*, menarik manifest terbaru dari CDN, dan mengunduh hash chunk baru tanpa mengganggu sesi perbankan nasabah.

---

### 16. Summary

1. **Arsitektur Zoneless** memodernisasi Angular dengan meniadakan beban komputasi dan bundle dari `zone.js`. Sebagai gantinya, **Angular Signals** berperan sebagai pilar utama reaktivitas, memberikan notifikasi granular ke `ChangeDetectionScheduler` hanya pada sub-tree yang mengalami mutasi state.
2. **Native Federation** menghadirkan solusi Micro-Frontend yang decoupled dan bundler-agnostic dengan memanfaatkan W3C Import Maps dan native Browser ES Modules. Hal ini membebaskan arsitektur frontend enterprise dari keterikatan monolitik terhadap satu jenis bundler spesifik.
3. Keberhasilan implementasi Zoneless Micro-Frontend di level produksi bergantung pada isolasi dependensi yang ketat (`singleton: true`), penanganan asinkron yang tepat (meniadakan mutasi objek primitif tanpa sinyal), sanitasi lifecycle menggunakan `DestroyRef`, serta penanganan kegagalan yang tangguh melalui Circuit Breaker dan deferrable views (`@defer`).