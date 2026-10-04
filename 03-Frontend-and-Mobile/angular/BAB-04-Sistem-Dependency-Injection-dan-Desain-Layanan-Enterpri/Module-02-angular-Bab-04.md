# BAB 04: Sistem Dependency Injection dan Desain Layanan Enterprise
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** arsitektur internal Angular Dependency Injection (DI), mencakup dual-tree hierarchy (`EnvironmentInjector` vs `ElementInjector`) dan algoritma resolusi berbasis *Bloom Filter*.
- **Mengimplementasikan** pola injeksi modern menggunakan fungsi `inject()` dan execution context primitives (`runInInjectionContext`, `assertInInjectionContext`).
- **Merancang** abstraksi dependensi tingkat lanjut menggunakan `InjectionToken`, factory providers, multi-token, dan resolution modifiers (`@Self`, `@SkipSelf`, `@Optional`, `@Host`).
- **Membangun** arsitektur layanan berbasis Enterprise Facade Pattern yang memadukan Angular Signals dan RxJS untuk isolasi *state management* dan integrasi API.
- **Mengoptimalkan** efisiensi *bundle size* dan konsumsi memori melalui *tree-shakable tokens*, pencegahan *circular dependency*, serta eliminasi *memory leak* pada hierarchical scoped services.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta harus menguasai:
- TypeScript tingkat lanjut: Generics, Mapped Types, Abstract Classes, Decorators, dan Type Narrowing.
- Dasar Angular Standalone Components dan Lifecycle Hooks (`ngOnInit`, `ngOnDestroy`).
- Konsep reaktivitas Angular: RxJS observables/operators (`Observable`, `Subject`, `takeUntilDestroyed`) dan Angular Signals primitives (`signal`, `computed`, `effect`).
- Materi Bab 04 Modul 01: Dasar Dependency Injection, Provider Scopes (`root`, component-level), dan Constructor Injection konvensional.

---

### 3. Concept & Internal Architecture

Sistem Dependency Injection pada Angular modern (v16+) dirancang menggunakan arsitektur dual-tree yang berjalan paralel selama fase eksekusi aplikasi: **EnvironmentInjector Hierarchy** dan **ElementInjector Hierarchy**.

```
                           [ Platform Injector ]
                                     │
                        [ Root EnvironmentInjector ]
                         (providedIn: 'root', AppConfig)
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
    [ Route EnvironmentInjector A ]       [ Route EnvironmentInjector B ]
     (Lazy Loaded Route Providers)         (Lazy Loaded Route Providers)
                 │                                       │
=================╪=======================================╪================
                 │ Node Injector Lookup Path             │
=================╪=======================================╪================
                 ▼                                       ▼
     [ Root ElementInjector ]                [ Root ElementInjector ]
       (<app-root> Node)                       (<app-root> Node)
                 │                                       │
        [ ElementInjector ]                     [ ElementInjector ]
     (<feature-shell> Node)                  (<feature-shell> Node)
                 │                                       │
        [ ElementInjector ]                     [ ElementInjector ]
     (<data-table> + ViewProviders)          (<data-table> + ViewProviders)
```

#### Dual-Tree Injector Engine
1. **EnvironmentInjector Tree**:
   - Berakar pada `Platform Injector` (layanan platform seperti `PLATFORM_ID`, dom sanitizers).
   - Di bawah platform terdapat `Root EnvironmentInjector` yang menampung semua service beranotasi `{ providedIn: 'root' }` dan provider yang didaftarkan pada fungsi `bootstrapApplication(App, appConfig)`.
   - Ketika routing Angular memuat modul/komponen secara *lazy* menggunakan `loadChildren` atau `providers` pada konfigurasi route, Angular membuat `EnvironmentInjector` baru sebagai anak cabang (*child*) dari Root Injector.
2. **ElementInjector Tree**:
   - Dibuat secara implisit pada setiap elemen DOM yang memiliki direktif atau komponen dengan konfigurasi `providers: [...]` atau `viewProviders: [...]`.
   - Berstruktur identik dengan Document Object Model (DOM) template aplikasi Anda.
   - Bersifat efemeral: dibuat saat komponen diinisialisasi ke view, dan dihancurkan bersamaan dengan pembersihan DOM komponen tersebut.

#### NodeInjector Lookup Mechanism & Bloom Filters
Angular merepresentasikan setiap node di template dalam struktur internal `LView` (Logical View) dan `TView` (Template View). Ketika dependensi diminta melalui token:
- Angular mencari token di dalam **ElementInjector** tempat dependensi diminta.
- Untuk menghindari penelusuran array linier $O(N)$ yang lambat pada struktur DOM yang dalam, Angular mengimplementasikan **Cumulative Bloom Filter** (berukuran 256-bit atau 4 blok integer 64-bit per node template).
- Setiap token memiliki hash ID unik. Jika bitwise AND antara token hash dan Bloom Filter node menghasilkan nilai 0, Angular secara instan ($O(1)$) mengetahui bahwa dependensi tersebut **pasti tidak ada** pada node tersebut, dan langsung melompat (*short-circuit*) ke parent node tanpa mengecek instansiasi tabel provider.
- Jika Bloom filter bernilai `true` (*positive* atau *false positive*), Angular melakukan pengecekan tabel provider aktual (`TData`). Jika cocok, instance dikembalikan atau dibuat.
- Jika pencarian mencapai akar `ElementInjector` (root component) tanpa hasil, resolusi berpindah mencari ke **EnvironmentInjector** dari rute yang aktif hingga berakhir di `NullInjector`. Jika token tidak bertanda `@Optional()`, `NullInjector` melempar `NullInjectorError: No provider for [Token]!`.

---

### 4. Why & What

#### Mengapa Beralih ke Functional `inject()` API?
Sebelum Angular 14, injeksi dependensi sepenuhnya bergantung pada *Constructor Parameter Decorators*:

```typescript
// Legacy Approach
constructor(
  private http: HttpClient,
  @Optional() @Inject(API_CONFIG) private config: ApiConfig | null
) {}
```

Keterbatasan pendekatan legacy:
- **Inheritance Hell**: Subclass yang mewarisi class induk (`extends BaseComponent`) harus memanggil `super(http, config, router, ...)` secara repetitif, merusak prinsip *Open/Closed Principle*.
- **Typing Boilerplate**: Membutuhkan sinkronisasi antara parameter tipe TypeScript dan metadata dekorator `@Inject()`.
- **Inflexible Composition**: Dependensi tidak dapat dibuat modular di luar struktur class (misal: composable functions ala React Hooks atau Vue Composables).

Pendekatan modern functional `inject()`:
```typescript
// Modern Approach
private readonly http = inject(HttpClient);
private readonly config = inject(API_CONFIG, { optional: true });
```
- Menghilangkan *constructor boilerplate* secara total.
- Subclass tidak perlu memelihara signature `super()` induk.
- Memungkinkan pembuatan reusable logic functions yang mengeksekusi dependensi Angular secara modular.

---

### 5. How (Workflow Resolusi Dependensi)

Algoritma pemrosesan injeksi dependensi berjalan melalui langkah sekuensial berikut:

```
[Token Request Diterima]
          │
          ▼
[Periksa ElementInjector Saat Ini]
          │
          ├──> [Apakah Bloom Filter bernilai POSITIF?]
          │         │
          │         ├──> YES: Cari di TView.data
          │         │           │
          │         │           ├──> Ditemukan? ──> Return/Instantiate
          │         │           └──> False Positive? ──> Lanjut ke Parent Node
          │         │
          │         └──> NO: Lewati pemeriksaan detail
          │
          ├──> Naik ke Parent Node (ElementInjector)
          │
          └──> Apakah sudah melewati batas Root Node (<app-root>)?
                    │
                    ├──> NO: Ulangi periksa ElementInjector Parent
                    └──> YES: Lompat ke EnvironmentInjector
                              │
                              ▼
                    [Periksa Route EnvironmentInjector]
                              │
                              ▼
                    [Periksa Root EnvironmentInjector]
                              │
                              ▼
                    [Periksa Platform EnvironmentInjector]
                              │
                              ▼
                    [NullInjector] ──> Throw NullInjectorError
                                       (atau return null jika optional)
```

1. **Resolution Initialization**: Fungsi `inject(Token)` atau constructor scanning memicu pemanggilan fungsi internal `ɵɵdirectiveInject`.
2. **Context Validation**: Angular memastikan pemanggilan berada dalam *Injection Context* aktif (instansiasi class, field initializer, atau pembungkus `runInInjectionContext`).
3. **Element-level Traversal**:
   - Jika dependensi dibatasi oleh modifier `@Self()`, pencarian hanya berhenti di node lokal.
   - Jika modifier `@SkipSelf()` aktif, pencarian langsung dimulai dari parent node dari elemen pemanggil.
   - Jika modifier `@Host()` digunakan, pencarian berhenti di komponen yang menampung template/view tempat direktif dideklarasikan.
4. **Environment Fallback**: Jika traversal tree elemen DOM mencapai root tanpa hasil dan modifier `@Host()` tidak membatasi, eksekusi berpindah ke rantai `EnvironmentInjector`.
5. **Singleton vs Multi Instance Lifecycle**:
   - Jika provider didaftarkan di root: instance dibuat sekali dan disimpan di memorized array injector root.
   - Jika didaftarkan di level elemen/komponen: instance baru dialokasikan untuk setiap instance komponen tersebut dan didaftarkan pada lifecycle destruction node terkait.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Perizinan Korporat Bertingkat
Bayangkan sebuah dokumen persetujuan pengeluaran dana operasional pada gedung kantor bertingkat:
- **ElementInjector (Lantai/Ruangan)**: Anda berada di meja kerja Anda (komponen lokal). Anda mencari printer atau stempel unit. Anda bertanya pada asisten meja lokal (`NodeInjector`). Jika tidak ada, Anda bertanya ke supervisor ruangan Anda (`Parent ElementInjector`).
- **Host Component (Kepala Divisi)**: Jika stempel itu harus persetujuan internal divisi (`@Host`), Anda tidak boleh keluar mencari ke divisi sebelah.
- **EnvironmentInjector (Kantor Pusat Korporat)**: Jika barang tersebut berupa fasilitas korporat terpusat (seperti sistem payroll pusat atau legal corporate), Anda tidak mencarinya di meja rekan kerja, melainkan langsung meminta memo ke Departemen Manajemen Pusat (`providedIn: 'root'`).
- **NullInjector**: Bagian penolakan akhir. Jika dokumen yang Anda minta tidak terdaftar sama sekali di seluruh sistem kantor pusat, permohonan Anda langsung ditolak dengan cap galat (*Error*).

```
[DOM / Element Tree]                       [Scope Boundary]
┌───────────────────────────────────────┐
│ <app-dashboard>                       │
│  Providers: [ DashboardLocalService ] │
│  ┌─────────────────────────────────┐  │
│  │ <app-widget-container>          │  │
│  │   ┌───────────────────────────┐ │  │
│  │   │ <app-metric-chart>        │ │  │
│  │   │ inject(DashboardLocalSvc) │ │  │ ──> Resolves to: <app-dashboard>
│  │   │ inject(AuthService)       │ │  │ ──> Not found in DOM!
│  │   └───────────────────────────┘ │  │      │
│  └─────────────────────────────────┘  │      │ (Escapes to Environment)
└───────────────────────────────────────┘      │
                                               ▼
[Environment Tree]                  ┌───────────────────────────────┐
                                    │ Root EnvironmentInjector      │
                                    │ Providers: [ AuthService ]    │ ──> Resolved!
                                    └───────────────────────────────┘
```

---

### 7. Implementation: Simple to Production

#### Skenario 1: Custom InjectionToken & Factory Provider (Standalone Approach)

```typescript
// app/core/tokens/api-config.token.ts
import { InjectionToken, inject } from '@angular/core';

export interface ApiConfiguration {
  readonly baseUrl: string;
  readonly timeoutMs: number;
  readonly retryAttempts: number;
}

export const API_CONFIGURATION = new InjectionToken<ApiConfiguration>(
  'API_CONFIGURATION_TOKEN',
  {
    providedIn: 'root',
    factory: (): ApiConfiguration => {
      // Default fallback jika tidak ada provider spesifik yang meng-override
      return {
        baseUrl: 'https://api.enterprise.domain.com/v1',
        timeoutMs: 10000,
        retryAttempts: 3,
      };
    },
  }
);
```

#### Skenario 2: Advanced Multi-Token Extensibility Pattern

```typescript
// app/core/monitoring/telemetry-reporter.token.ts
import { InjectionToken, Provider } from '@angular/core';

export interface TelemetryReporter {
  reportEvent(name: string, payload: Record<string, unknown>): void;
  reportError(error: Error, metadata?: Record<string, unknown>): void;
}

export const TELEMETRY_REPORTER = new InjectionToken<TelemetryReporter[]>(
  'TELEMETRY_REPORTER_MULTI_TOKEN'
);

export function provideTelemetryReporter(
  reporterClass: new (...args: any[]) => TelemetryReporter
): Provider {
  return {
    provide: TELEMETRY_REPORTER,
    useClass: reporterClass,
    multi: true,
  };
}
```

```typescript
// app/core/monitoring/telemetry.service.ts
import { Injectable, inject } from '@angular/core';
import { TELEMETRY_REPORTER, TelemetryReporter } from './telemetry-reporter.token';

@Injectable({ providedIn: 'root' })
export class EnterpriseTelemetryService {
  // Inject seluruh reporter yang didaftarkan ke array multi-token
  private readonly reporters = inject(TELEMETRY_REPORTER, { optional: true }) ?? [];

  public track(eventName: string, payload: Record<string, unknown> = {}): void {
    const timestampedPayload = {
      ...payload,
      timestamp: Date.now(),
    };

    for (const reporter of this.reporters) {
      try {
        reporter.reportEvent(eventName, timestampedPayload);
      } catch (err) {
        console.error(`Telemetry sink error in ${reporter.constructor.name}:`, err);
      }
    }
  }
}
```

#### Skenario 3: Execution Context Manipulation (`runInInjectionContext`)

```typescript
// app/core/utils/dynamic-injector.ts
import { EnvironmentInjector, inject, Injectable, runInInjectionContext } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class DynamicExecutionEngine {
  private readonly envInjector = inject(EnvironmentInjector);

  public executeTaskOutsideInjectionChain<T>(action: () => T): T {
    // Mengeksekusi fungsi yang memanfaatkan inject() di luar lifecycle constructor/field
    return runInInjectionContext(this.envInjector, () => {
      return action();
    });
  }
}
```

---

### 8. Real-World Enterprise Case Study: White-Label Core Banking Engine

#### Problem Statement
Sebuah bank multinasional mengoperasikan aplikasi portal web tunggal (*mono-repository*) yang harus mendukung 3 sub-brand perbankan ritel: **Retail Bank A**, **Private Wealth B**, dan **Islamic Finance C**. 

Kebutuhan arsitektur:
1. Skema perhitungan bunga/margin pembiayaan berbeda drastis di runtime berdasarkan *tenant ID* pengguna yang login.
2. Form validator rekening bersifat spesifik untuk setiap negara operasional.
3. Aplikasi tidak boleh me-recompile bundle untuk setiap brand (*dynamic runtime strategy selection*).
4. State transaksi harus diisolasi strictly per halaman modul transaksi; tidak boleh ada kebocoran state antar navigasi tab transaksi.

#### Solusi Arsitektur
Menerapkan kombinasi **Hierarchical ElementInjectors**, **Dynamic Factory Providers**, dan **Stateful Isolated Service Facades**.

```
                        ┌───────────────────────────────┐
                        │      TenantContextService     │
                        │  (Global: Holds active Tenant) │
                        └───────────────┬───────────────┘
                                        │
                                        ▼
                        ┌───────────────────────────────┐
                        │    FEE_CALCULATOR_FACTORY     │
                        │   (Dynamic InjectionToken)    │
                        └───────────────┬───────────────┘
                                        │
                   ┌────────────────────┼────────────────────┐
                   ▼                    ▼                    ▼
        [RetailFeeStrategy]  [WealthFeeStrategy]   [IslamicFeeStrategy]
                   │
                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ TransactionShellComponent (Route Level)                                │
│   Providers: [                                                         │
│     TransactionFacadeService, // Component-scoped (Isolated State)     │
│     { provide: FEE_STRATEGY, useFactory: feeStrategyFactory }          │
│   ]                                                                    │
│                                                                        │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │ TransactionDetailComponent                                   │     │
│   │   inject(TransactionFacadeService)                           │     │
│   │   inject(FEE_STRATEGY)                                       │     │
│   └──────────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────────────┘
```

#### Implementasi Teknis

```typescript
// 1. Domain Contracts & Injection Token
import { InjectionToken, inject, signal, computed, Injectable, DestroyRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

export interface FeeCalculationStrategy {
  calculateFee(principalAmount: number): number;
  getRegulatoryDisclaimer(): string;
}

export const FEE_STRATEGY = new InjectionToken<FeeCalculationStrategy>('FEE_STRATEGY');

// 2. Concrete Strategy Implementations
export class RetailBankingFeeStrategy implements FeeCalculationStrategy {
  calculateFee(amount: number): number {
    return Math.max(5.0, amount * 0.015); // Biaya tetap minimum atau 1.5%
  }
  getRegulatoryDisclaimer(): string {
    return 'Biaya standar transaksi ritel berlaku regulasi Bank Sentral Tier-1.';
  }
}

export class PrivateWealthFeeStrategy implements FeeCalculationStrategy {
  calculateFee(amount: number): number {
    return amount > 100000 ? 0 : 50.0; // Bebas biaya untuk nasabah affluent
  }
  getRegulatoryDisclaimer(): string {
    return 'Nasabah Platinum Privilege: Bebas biaya transaksi di atas ambang batas.';
  }
}

export class IslamicBankingFeeStrategy implements FeeCalculationStrategy {
  calculateFee(amount: number): number {
    // Sesuai prinsip akad Ujrah (flat fee tanpa persentase berbunga)
    return 12.5;
  }
  getRegulatoryDisclaimer(): string {
    return 'Dikenakan biaya administrasi tetap berdasarkan akad Ijarah / Ujrah.';
  }
}

// 3. Tenant Management Service (Singleton Root)
export type TenantType = 'RETAIL' | 'WEALTH' | 'ISLAMIC';

@Injectable({ providedIn: 'root' })
export class TenantManagementService {
  private readonly currentTenantSignal = signal<TenantType>('RETAIL');
  public readonly currentTenant = this.currentTenantSignal.asReadonly();

  public switchTenant(tenant: TenantType): void {
    this.currentTenantSignal.set(tenant);
  }
}

// 4. Component-Scoped Isolated Transaction Facade (Menggunakan Angular Signals)
export interface TransactionState {
  recipientAccount: string;
  amount: number;
  isProcessing: boolean;
  transactionId: string | null;
}

@Injectable() // NOT providedIn: 'root' -> Wajib scoped per shell lifecycle
export class TransactionFacadeService {
  private readonly http = inject(HttpClient);
  private readonly feeStrategy = inject(FEE_STRATEGY);
  private readonly destroyRef = inject(DestroyRef);

  // Reactive State
  private readonly state = signal<TransactionState>({
    recipientAccount: '',
    amount: 0,
    isProcessing: false,
    transactionId: null,
  });

  // Selectors
  public readonly amount = computed(() => this.state().amount);
  public readonly calculatedFee = computed(() => 
    this.feeStrategy.calculateFee(this.state().amount)
  );
  public readonly totalDebited = computed(() => 
    this.amount() + this.calculatedFee()
  );
  public readonly disclaimer = computed(() => 
    this.feeStrategy.getRegulatoryDisclaimer()
  );
  public readonly isProcessing = computed(() => this.state().isProcessing);

  public updateAmount(newAmount: number): void {
    this.state.update((curr) => ({ ...curr, amount: Math.max(0, newAmount) }));
  }

  public updateRecipient(account: string): void {
    this.state.update((curr) => ({ ...curr, recipientAccount: account }));
  }

  public submitTransaction(): void {
    const currentState = this.state();
    if (currentState.amount <= 0 || !currentState.recipientAccount) {
      throw new Error('Validasi gagal: Nominal atau rekening tujuan tidak valid.');
    }

    this.state.update((curr) => ({ ...curr, isProcessing: true }));

    this.http
      .post<{ id: string }>('/api/v1/banking/transfers', {
        amount: currentState.amount,
        fee: this.calculatedFee(),
        recipient: currentState.recipientAccount,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          this.state.update((curr) => ({
            ...curr,
            isProcessing: false,
            transactionId: response.id,
          }));
        },
        error: (err) => {
          this.state.update((curr) => ({ ...curr, isProcessing: false }));
          console.error('Transaksi ditolak oleh core banking engine:', err);
        },
      });
  }
}
```

```typescript
// 5. Transaction Route Shell Component
import { Component, ChangeDetectionStrategy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { 
  TransactionFacadeService, 
  FEE_STRATEGY, 
  RetailBankingFeeStrategy, 
  PrivateWealthFeeStrategy, 
  IslamicBankingFeeStrategy 
} from './transaction-facade.service';
import { TenantManagementService } from './tenant-management.service';

@Component({
  selector: 'app-transaction-shell',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="transaction-container p-6 bg-slate-900 text-white rounded-lg">
      <h2 class="text-xl font-bold">Transfer Dana Antar Bank</h2>
      <p class="text-sm text-amber-400 mb-4">{{ facade.disclaimer() }}</p>

      <div class="form-group mb-3">
        <label>Nominal Transfer (IDR):</label>
        <input 
          type="number" 
          [value]="facade.amount()" 
          (input)="onAmountChange($event)"
          class="w-full p-2 bg-slate-800 rounded border border-slate-700"
        />
      </div>

      <div class="summary bg-slate-800 p-4 rounded mb-4">
        <div>Biaya Layanan: Rp {{ facade.calculatedFee() | number }}</div>
        <div class="font-bold text-lg">Total Debit: Rp {{ facade.totalDebited() | number }}</div>
      </div>

      <button 
        (click)="facade.submitTransaction()"
        [disabled]="facade.isProcessing()"
        class="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded disabled:opacity-50">
        {{ facade.isProcessing() ? 'Memproses...' : 'Kirim Pembayaran' }}
      </button>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    // Dynamic Factory Provider
    {
      provide: FEE_STRATEGY,
      useFactory: (): RetailBankingFeeStrategy | PrivateWealthFeeStrategy | IslamicBankingFeeStrategy => {
        const tenantService = inject(TenantManagementService);
        switch (tenantService.currentTenant()) {
          case 'WEALTH':
            return new PrivateWealthFeeStrategy();
          case 'ISLAMIC':
            return new IslamicBankingFeeStrategy();
          case 'RETAIL':
          default:
            return new RetailBankingFeeStrategy();
        }
      },
    },
    // Scoped Service: Lifecycle instansiasi terikat hanya pada TransactionShellComponent
    TransactionFacadeService,
  ],
})
export class TransactionShellComponent {
  protected readonly facade = inject(TransactionFacadeService);

  protected onAmountChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.facade.updateAmount(parseFloat(input.value) || 0);
  }
}
```

---

### 9. Trade-Offs & Architecture Matrix

| Strategi Provider | Startup Latency | Memory Footprint | Tree-Shaking Capability | Maintenance & Testing Complexity |
| :--- | :--- | :--- | :--- | :--- |
| **`providedIn: 'root'`** | Sangat Cepat (Lazy instantiated saat pertama di-inject) | Rendah (Hanya 1 instance singleton selama runtime app) | **Optimal** (Jika tidak di-import/di-inject, class di-strip saat build) | Sederhana. Mocking mudah di unit test via `TestBed.overrideProvider`. |
| **Route-level `EnvironmentInjector`** | Cepat (Di-load chunk lazy route terkait) | Sedang (Dihancurkan saat rute dinavigasi keluar jika arsitekturnya modular) | **Baik** (Terikat ke bundle chunk rute tertentu) | Sedang. Butuh konfigurasi TestBed router testing harness. |
| **Component-level `providers: [...]`** | Marginal overhead per component instantiation | Tinggi jika komponen dirender massal (misal: baris tabel virtualized) | **Buruk** (Komponen menahan referensi class, sulit di-tree-shake) | Perlu kehati-hatian: state terisolasi, mudah diuji secara hermetis per komponen. |
| **Multi-Tokens (`multi: true`)** | Marginal linear instantiation cost saat token di-resolve pertama | Berbanding lurus dengan jumlah provider yang terdaftar | **Rendah** (Semua provider multi-token yang di-import akan masuk bundle) | Tinggi. Urutan array provider dipengaruhi oleh urutan pendaftaran modul/fitur. |

---

### 10. Common Pitfalls & Troubleshooting

#### 1. Circular Dependency via Inter-Service Injection
- **Symptom**: `NullInjectorError` atau `ReferenceError: Cannot access 'XService' before initialization` di runtime.
- **Root Cause**: `ServiceA` menginjeksi `ServiceB`, dan `ServiceB` secara langsung atau transitif menginjeksi `ServiceA`.
- **Solusi Rekayasa**: Gunakan arsitektur pemisahan state berbasis **Mediator/Dispatcher Pattern** atau isolasi token abstraksi:

```typescript
// WRONG: Circular Dependency
@Injectable({ providedIn: 'root' })
export class AuthService {
  private userState = inject(UserStateService); // Depends on UserStateService
}

@Injectable({ providedIn: 'root' })
export class UserStateService {
  private auth = inject(AuthService); // Depends on AuthService -> CYCLE!
}

// CORRECT: Ekstraksi shared state ke Interface Token atau Store independen
export const AUTH_CREDENTIAL_STREAM = new InjectionToken<Observable<UserCredential>>('AUTH_STREAM');
```

#### 2. Context Loss dengan `inject()` di Operasi Asinkron
- **Symptom**: `NG0203: inject() must be called from an injection context such as a constructor, a factory function, a field initializer...`
- **Root Cause**: Memanggil `inject()` di dalam callback asynchronous (seperti di dalam `.subscribe()`, `setTimeout()`, atau setelah keyword `await`).
- **Solusi**: Panggil `inject()` pada field initializer atau tangkap injector aktif terlebih dahulu menggunakan `assertInInjectionContext` atau `runInInjectionContext`:

```typescript
// WRONG
export function executeLazyQuery() {
  setTimeout(() => {
    const http = inject(HttpClient); // RUNTIME ERROR! Context is lost
    http.get('/api/data').subscribe();
  }, 1000);
}

// CORRECT
export function executeLazyQuery() {
  const http = inject(HttpClient); // Inject synchronous di valid context
  setTimeout(() => {
    http.get('/api/data').subscribe();
  }, 1000);
}

// ALTERNATIVE: Explicit capture
export function createDeferredTask() {
  const injector = inject(EnvironmentInjector);
  return () => {
    runInInjectionContext(injector, () => {
      const http = inject(HttpClient); // Works correctly!
      http.get('/api/data').subscribe();
    });
  };
}
```

#### 3. State Leakage Akibat Lupa Menghapus `providedIn: 'root'` pada Facade
- **Symptom**: Ketika pengguna berpindah form/halaman, sisa input dari sesi transaksi sebelumnya masih muncul.
- **Root Cause**: Layanan Facade diberi metadata `{ providedIn: 'root' }`, mengubahnya menjadi global singleton bukan component-scoped.
- **Solusi**: Hapus `{ providedIn: 'root' }` dari dekorator `@Injectable()` pada stateful facade, dan daftarkan secara eksplisit di array `providers: [TransactionFacadeService]` pada komponen container host.

---

### 11. Best Practices & Production Checklist

- [ ] **Gunakan `providedIn: 'root'` Secara Default**: Jadikan ini baseline untuk 90% stateless utility, domain data service, dan business rules engine demi *tree-shakability* optimal.
- [ ] **Gunakan Standalone Functional `inject()`**: Tinggalkan constructor injection konvensional demi fleksibilitas inheritance dan komposisi functional.
- [ ] **Immutability pada InjectionToken**: Tandai properti konfigurasi token dengan `readonly` dan `Object.freeze()` untuk mencegah mutasi state konfigurasi global secara sengaja atau tidak sengaja di runtime.
- [ ] **Selalu Gunakan `takeUntilDestroyed` pada Scoped Service**: Service yang di-provide pada level Element/Route harus menghentikan seluruh stream RxJS internalnya saat injector dihancurkan untuk menghindari *zombie subscriptions*.
- [ ] **Hindari Penggunaan `viewProviders` Kecuali pada Komposit Elemen Slot Konten**: Gunakan `providers` reguler kecuali jika Anda sengaja membatasi provider agar **tidak dapat diakses** oleh konten transklusi (`<ng-content>`).
- [ ] **Enforce Type Safety pada Factory Provider**: Selalu tentukan generic return type secara eksplisit pada fungsi `useFactory: (): T => ...`.

---

### 12. Hands-on Practice Guide

Simpan struktur kode praktikum berikut ke dalam repositori lokal pada path: `hands-on/m02/`.

#### Langkah 1: Struktur Proyek
Buat direktori dan file berikut:
```text
hands-on/m02/
├── tokens/
│   └── payment-gateway.token.ts
├── services/
│   ├── stripe-gateway.service.ts
│   ├── paypal-gateway.service.ts
│   └── checkout-facade.service.ts
└── components/
    └── checkout-panel.component.ts
```

#### Langkah 2: Definisikan Kontrak dan InjectionToken
`hands-on/m02/tokens/payment-gateway.token.ts`:
```typescript
import { InjectionToken } from '@angular/core';
import { Observable } from 'rxjs';

export interface PaymentTransactionResult {
  status: 'SUCCESS' | 'FAILED';
  referenceId: string;
}

export interface PaymentGatewayDriver {
  initialize(): void;
  processPayment(amount: number): Observable<PaymentTransactionResult>;
}

export const PAYMENT_GATEWAY = new InjectionToken<PaymentGatewayDriver>(
  'PAYMENT_GATEWAY_DRIVER'
);
```

#### Langkah 3: Implementasikan Dua Driver Berbeda
`hands-on/m02/services/stripe-gateway.service.ts`:
```typescript
import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { delay } from 'rxjs/operators';
import { PaymentGatewayDriver, PaymentTransactionResult } from '../tokens/payment-gateway.token';

@Injectable()
export class StripeGatewayDriver implements PaymentGatewayDriver {
  initialize(): void {
    console.log('[StripeGateway] Initializing Stripe SDK Elements v3...');
  }

  processPayment(amount: number): Observable<PaymentTransactionResult> {
    console.log(`[StripeGateway] Charging $${amount} via Stripe PaymentIntent API.`);
    return of({
      status: 'SUCCESS' as const,
      referenceId: `ch_stripe_${Math.random().toString(36).substring(7)}`,
    }).pipe(delay(800));
  }
}
```

`hands-on/m02/services/paypal-gateway.service.ts`:
```typescript
import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { delay } from 'rxjs/operators';
import { PaymentGatewayDriver, PaymentTransactionResult } from '../tokens/payment-gateway.token';

@Injectable()
export class PayPalGatewayDriver implements PaymentGatewayDriver {
  initialize(): void {
    console.log('[PayPalGateway] Rendering PayPal Smart Buttons SDK...');
  }

  processPayment(amount: number): Observable<PaymentTransactionResult> {
    console.log(`[PayPalGateway] Executing capture order for $${amount}.`);
    return of({
      status: 'SUCCESS' as const,
      referenceId: `PAYPAL-CAPTURE-${Math.random().toString(36).substring(7).toUpperCase()}`,
    }).pipe(delay(1200));
  }
}
```

#### Langkah 4: Bangun Checkout Facade
`hands-on/m02/services/checkout-facade.service.ts`:
```typescript
import { Injectable, inject, signal, computed, DestroyRef } from '@angular/core';
import { PAYMENT_GATEWAY } from '../tokens/payment-gateway.token';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

@Injectable()
export class CheckoutFacadeService {
  private readonly gateway = inject(PAYMENT_GATEWAY);
  private readonly destroyRef = inject(DestroyRef);

  private readonly isBusySignal = signal<boolean>(false);
  private readonly lastTxIdSignal = signal<string | null>(null);

  public readonly isBusy = this.isBusySignal.asReadonly();
  public readonly lastTransactionId = this.lastTxIdSignal.asReadonly();

  constructor() {
    this.gateway.initialize();
  }

  public checkout(total: number): void {
    this.isBusySignal.set(true);
    this.gateway
      .processPayment(total)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.isBusySignal.set(false);
          this.lastTxIdSignal.set(res.referenceId);
        },
        error: () => {
          this.isBusySignal.set(false);
        }
      });
  }
}
```

#### Langkah 5: Wiring Menggunakan Dynamic Provider Pada Komponen
`hands-on/m02/components/checkout-panel.component.ts`:
```typescript
import { Component, ChangeDetectionStrategy, inject, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CheckoutFacadeService } from '../services/checkout-facade.service';
import { PAYMENT_GATEWAY } from '../tokens/payment-gateway.token';
import { StripeGatewayDriver } from '../services/stripe-gateway.service';
import { PayPalGatewayDriver } from '../services/paypal-gateway.service';

@Component({
  selector: 'app-checkout-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="border border-neutral-700 p-4 rounded bg-neutral-900 text-white">
      <h3 class="font-bold text-lg mb-2">Panel Pembayaran Terisolasi</h3>
      <p class="text-sm mb-4">Driver Aktif: {{ driverName }}</p>
      
      <button 
        (click)="facade.checkout(199.99)" 
        [disabled]="facade.isBusy()"
        class="bg-emerald-600 hover:bg-emerald-500 px-4 py-2 rounded text-white font-medium">
        {{ facade.isBusy() ? 'Memproses Gateway...' : 'Bayar $199.99' }}
      </button>

      @if (facade.lastTransactionId(); as txId) {
        <div class="mt-4 p-2 bg-emerald-950 border border-emerald-800 rounded text-emerald-300 text-sm">
          Pembayaran Sukses! Referensi: {{ txId }}
        </div>
      }
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    // Driver disesuaikan di level ElementInjector
    {
      provide: PAYMENT_GATEWAY,
      useFactory: () => {
        // Simulasi pemilihan driver via environment flag / attribute
        const isStripe = true; 
        return isStripe ? new StripeGatewayDriver() : new PayPalGatewayDriver();
      }
    },
    CheckoutFacadeService
  ]
})
export class CheckoutPanelComponent {
  protected readonly facade = inject(CheckoutFacadeService);
  protected readonly driverName = 'StripeGatewayDriver';
}
```

---

### 13. Exercises

#### Level Easy
1. Buat custom `InjectionToken<string>` dengan nama `APP_VERSION`.
2. Sediakan token tersebut secara global melalui `ApplicationConfig` pada file `app.config.ts` dengan nilai hardcoded `'2.4.0-production'`.
3. Injeksi token tersebut ke dalam komponen standalone menggunakan fungsi modern `inject()`.

#### Level Medium
1. Buat directive Angular bernama `CardThemeDirective` yang memiliki `providers: [...]` sendiri.
2. Buat `ThemeContextService` yang di-provide di level direktif tersebut (bukan root).
3. Buat dua instance direktif tersebut pada elemen parent berbeda di template yang sama dengan warna tema berbeda (`'dark'` dan `'light'`). Buktikan bahwa sub-komponen anak di masing-masing tree membaca instance warna yang berbeda sesuai hierarki parent-nya masing-masing.

#### Level Hard
1. Buat logging interceptor berbasis multi-token `HTTP_INTERCEPTORS` (atau functional interceptor via `HttpInterceptorFn`) yang menggunakan `InjectionToken<LoggerService[]>` custom.
2. Salah satu logger harus mengirim log ke `console.log`, sedangkan logger kedua menulis ke buffer memory internal yang akan di-flush secara batch ke server setiap interval 5 detik.
3. Pastikan tidak terjadi *memory leak* jika HTTP error 500 terus-menerus terjadi.

---

### 14. Enterprise Architecture Challenge (Tanpa Solusi Instan)

**Skenario Kasus**:
Anda adalah Principal Frontend Architect pada platform trading Crypto Multi-Asset. Sistem memiliki dashboard kompleks dengan 20 widget grafik (*candlestick chart*, *order book*, *depth chart*, *recent trades*).

**Kebutuhan Kompleks**:
1. Setiap widget dapat di-duplicate oleh pengguna ke workspace yang sama.
2. Setiap widget membutuhkan akses ke `RealtimeDataStreamService`, namun parameter *ticker* aset (misal: `BTC/USD`, `ETH/USDT`) ditentukan oleh dropdown pada header masing-masing widget container.
3. Seluruh widget anak di dalam container widget tertentu **harus** secara otomatis menerima stream data dari *ticker* yang dipilih container tersebut tanpa menggunakan `@Input()` prop drilling yang dalam.
4. Jika widget container dihancurkan oleh pengguna (*close widget*), seluruh WebSocket multiplexed stream untuk widget tersebut **harus terputus seketika** tanpa sisa referensi memori di WebSocket Master Hub.
5. Anda **dilarang** menggunakan third-party library state management (NGRX, Akita, Elf, dll). Arsitektur harus murni dibangun di atas Angular Dependency Injection Engine, Signals, RxJS, dan Injection Lifecycles.

**Rancang dan spesifikasikan arsitektur DI yang memenuhi seluruh batasan tersebut!**

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa fungsi utama internal dari mekanisme Cumulative Bloom Filter pada NodeInjector Angular?
   - A. Menjamin enkripsi data antar dependensi di memori.
   - B. Mempercepat lookup ketiadaan token ($O(1)$ short-circuit) sebelum menelusuri array pohon DOM.
   - C. Mengubah constructor injection menjadi functional injection secara otomatis saat compile-time.
   - D. Menghapus instance service yang tidak digunakan melalui Garbage Collection.
   *Jawaban*: **B**.

2. Apa yang terjadi jika token yang di-inject tidak ditemukan di ElementInjector maupun EnvironmentInjector, dan tidak diberi modifier `{ optional: true }`?
   - A. Aplikasi mereturn nilai `undefined`.
   - B. Angular membuat instance kosong secara otomatis.
   - C. `NullInjector` melempar `NullInjectorError`.
   - D. Sistem me-restart aplikasi ke rute root `/`.
   *Jawaban*: **C**.

3. Di mana lokasi eksekusi yang **tidak valid** untuk memanggil fungsi `inject()`?
   - A. Property initializer pada deklarasi class field.
   - B. Di dalam body fungsi `constructor()`.
   - C. Di dalam closure factory function sebuah `InjectionToken`.
   - D. Di dalam body method `ngAfterViewInit()` secara asinkron tanpa `runInInjectionContext`.
   *Jawaban*: **D**.

4. Apa dampak penggunaan `{ providedIn: 'root' }` terhadap ukuran *production bundle* (bundle size) jika service tersebut sama sekali tidak di-inject oleh komponen mana pun?
   - A. Ukuran bundle tetap bertambah karena didekorasi `@Injectable`.
   - B. Service dieliminasi dari bundle akhir melalui proses *Tree-Shaking*.
   - C. Compiler akan menghasilkan error build `NG8001`.
   - D. Service dipaksa masuk ke bundle `polyfills.js`.
   *Jawaban*: **B**.

5. Kapan sebuah instance service yang dideklarasikan pada `providers: [MyService]` di level Component akan dihancurkan (destroyed)?
   - A. Saat browser ditutup atau direfresh.
   - B. Saat navigasi rute pertama terjadi.
   - C. Bersamaan dengan saat node komponen tersebut di-destroy dari DOM.
   - D. Tidak pernah dihancurkan karena disimpan di Root Injector.
   *Jawaban*: **C**.

---

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Kasus)
6. Manakah konfigurasi modifier yang memastikan dependency lookup **hanya** memeriksa ElementInjector pada host elemen komponen itu sendiri dan langsung melempar error jika tidak ditemukan di node lokal?
   - A. `inject(Token, { optional: true })`
   - B. `inject(Token, { self: true })`
   - C. `inject(Token, { skipSelf: true })`
   - D. `inject(Token, { host: true })`
   *Jawaban*: **B**.

7. Perhatikan kode berikut:
   ```typescript
   export const BASE_URL = new InjectionToken<string>('BASE_URL', {
     providedIn: 'root',
     factory: () => 'https://api.dev.local'
   });
   // Pada child component:
   providers: [{ provide: BASE_URL, useValue: 'https://api.prod.enterprise.com' }]
   ```
   Nilai apa yang diperoleh jika sebuah service singleton root (`providedIn: 'root'`) meng-inject `BASE_URL`?
   - A. `'https://api.prod.enterprise.com'`
   - B. `'https://api.dev.local'`
   - C. `null`
   - D. Error `NG0209: Multiple Token Collision`
   *Jawaban*: **B**. *Penjelasan*: Layanan di level `Root EnvironmentInjector` tidak dapat menelusuri ke bawah (*downward lookup*) ke `ElementInjector` anak. Resolusinya berhenti di level root factory.

8. Apa perbedaan mendasar antara `providers: [...]` dan `viewProviders: [...]` pada metadata `@Component`?
   - A. `viewProviders` hanya mendukung injeksi primitives string, bukan class.
   - B. Dependensi di `viewProviders` tidak dapat diakses oleh komponen/elemen yang diproyeksikan melalui `<ng-content>`.
   - C. `providers` dieksekusi secara asinkron, sedangkan `viewProviders` sinkron.
   - D. `viewProviders` membuat instance baru pada setiap deteksi perubahan (*change detection cycle*).
   *Jawaban*: **B**.

9. Kapan modifier `{ skipSelf: true }` wajib digunakan dalam perancangan hierarki service?
   - A. Ketika service tersebut bersifat stateless.
   - B. Ketika directive/komponen turunan ingin meng-override service parent tanpa menimpa instance dirinya sendiri, atau mencegah recursive infinite lookup saat membungkus (*decorating*) layanan sejenis.
   - C. Ketika service tersebut di-load melalui Web Worker.
   - D. Saat menggunakan RxJS Subject di dalam service.
   *Jawaban*: **B**.

10. Bagaimana cara yang benar menangani *unsubscription* otomatis pada service yang di-provide di level Component tanpa mengimplementasikan lifecycle `ngOnDestroy` secara manual?
    - A. Memanggil `window.gc()` di constructor.
    - B. Menggunakan operator `.pipe(takeUntilDestroyed(inject(DestroyRef)))`.
    - C. Mengubah semua observable menjadi signal primitif secara paksa.
    - D. Membungkus service dengan `Object.freeze()`.
    *Jawaban*: **B**.

---

#### Bagian 3: Production Scenarios (Analisis & Rekomendasi Solusi)

11. **Skenario Kasus 1**:
    Sebuah aplikasi e-commerce besar mengalami lonjakan penggunaan memori (Memory Leak) hingga 1.5 GB setelah pengguna menelusuri katalog produk yang memiliki *infinite scroll virtual-scroll-viewport*. Setiap kartu produk menggunakan direktif `appPriceFormatter` yang menyediakan `CurrencyConverterService` pada array `providers`-nya.
    *Analisis masalah internal DI dan berikan tindakan perbaikan arsitekturnya!*
    - **Solusi**: Pendaftaran `CurrencyConverterService` pada `providers` direktif kartu produk menyebabkan Angular membuat ribuan instance injector dan service yang terduplikasi di setiap baris/kartu DOM virtual. Walaupun virtual scroll mendaur ulang node, referensi penutupan RxJS atau callback internal yang tertahan mencegah garbage collection. 
    *Tindakan*: Ubah `CurrencyConverterService` menjadi stateless singleton dengan `{ providedIn: 'root' }`, dan hapus konfigurasi `providers: [CurrencyConverterService]` dari direktif lokal.

12. **Skenario Kasus 2**:
    Tim engineering membuat modul Micro-Frontend (MFE) menggunakan Angular Standalone Components yang di-load secara dinamis via Webpack Module Federation ke dalam Container App. Ketika Micro-Frontend mencoba mengakses layanan `AuthSessionManager` milik Container App, terjadi runtime error: `NullInjectorError: No provider for AuthSessionManager!`. Padahal Container App telah mendaftarkan `AuthSessionManager` di `bootstrapApplication(App, { providers: [AuthSessionManager] })`.
    *Mengapa error ini terjadi di level platform injector dan bagaimana solusinya?*
    - **Solusi**: Module Federation memuat dua instance bundle Angular core (`@angular/core`) yang berbeda jika share configuration package tidak di-set sebagai *singleton strict-version*. Akibatnya, `Platform Injector` dan `EnvironmentInjector` root terisolasi di memory space masing-masing bundle.
    *Tindakan*: Konfigurasi `federation.config.js` untuk memastikan `@angular/core`, `@angular/common`, dan package platform utama dideklarasikan sebagai `{ singleton: true, strictVersion: true, requiredVersion: 'auto' }`. Opsi kedua: Gunakan platform level injector bridge secara eksplisit via custom DOM events atau global window symbol injector.

13. **Skenario Kasus 3**:
    Pada unit test enterprise menggunakan Jest/Spectator, pengembang mendapati bahwa penulisan kode:
    ```typescript
    TestBed.configureTestingModule({
      providers: [OrderProcessingService]
    });
    ```
    selalu mengeksekusi panggilan HTTP aktual ke gateway perbankan nyata di lingkungan development sandbox, sehingga pengujian pipeline CI/CD sering *timeout*.
    *Tentukan arsitektur mocking yang tepat menggunakan DI primitives!*
    - **Solusi**: `OrderProcessingService` kemungkinan bergantung langsung pada class HTTP driver konkret tanpa token abstraksi, atau factory provider yang mengeksekusi koneksi network nyata.
    *Tindakan*: Definisikan `PAYMENT_GATEWAY_CLIENT` sebagai `InjectionToken<PaymentGatewayContract>`. Pada test suite, override implementasi dependensi menggunakan:
    ```typescript
    TestBed.configureTestingModule({
      providers: [
        OrderProcessingService,
        {
          provide: PAYMENT_GATEWAY_CLIENT,
          useValue: {
            charge: jest.fn().mockReturnValue(of({ status: 'SUCCESS', id: 'TEST-TX' }))
          }
        }
      ]
    });
    ```
    Hal ini menjamin isolasi hermetis total tanpa dependensi eksternal.

---

### 16. Summary

1. Arsitektur Dependency Injection Angular modern beroperasi menggunakan **Dual-Tree Hierarchy**: `EnvironmentInjector` (untuk modul, rute lazy-load, dan singleton root) dan `ElementInjector` (terikat langsung pada node elemen hierarki DOM).
2. Mekanisme pencarian pada `ElementInjector` dioptimalkan secara ekstrem menggunakan **Cumulative 256-bit Bloom Filters** untuk mencapai efisiensi deterministik sebelum Angular menelusuri DOM tree ke atas.
3. Functional API **`inject()`** menggantikan batasan konvensional constructor injection: menghilangkan overhead `super()` boilerplate pada skenario class inheritance dan memfasilitasi pembuatan composable architecture yang modular.
4. Desain layanan enterprise skala besar menuntut pemisahan tegas antara:
   - **Stateless/Global Shared Services**: Didaftarkan di `{ providedIn: 'root' }` untuk memaksimalkan *tree-shakability*.
   - **Isolated/Stateful Facades**: Didaftarkan di level komponen/rute untuk membatasi lifecycle state dan mengisolasi memori agar tidak bocor ke domain bisnis lain.
5. Pemanfaatan **InjectionToken**, factory functions (`useFactory`), resolution modifiers (`@Host`, `@SkipSelf`, `@Self`, `@Optional`), dan execution context manipulation (`runInInjectionContext`) merupakan fondasi utama dalam merancang sistem enterprise yang *loosely coupled*, *modular*, dan *testable*.