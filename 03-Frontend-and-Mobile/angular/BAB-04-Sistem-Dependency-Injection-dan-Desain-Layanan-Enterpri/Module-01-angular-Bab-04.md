# Bab 04 Module 01: Sistem Dependency Injection (DI) & Desain Layanan Enterprise

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Kurikulum:** Angular Enterprise Engineering
* **Bab:** 04 — Arsitektur Layanan & Manajemen State Skala Besar
* **Modul:** 01 — Sistem Dependency Injection (DI) & Desain Layanan Enterprise
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat:** Pemahaman mendalam tentang TypeScript Decorators & Metadata Reflection, Angular Component Architecture, Lifecycle Hooks, serta pola reaktif RxJS.

---

## SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Menguasai arsitektur hierarkis dua cabang Angular DI (`EnvironmentInjector` vs `ElementInjector`) beserta aturan resolusi dependensi mendalam.
2. Mengimplementasikan token injection khusus (`InjectionToken<T>`) dengan konfigurasi factory yang mendukung *tree-shaking* penuh.
3. Mengontrol traversal resolusi injektor menggunakan modifier resolusi (`@Self()`, `@SkipSelf()`, `@Optional()`, `@Host()`, atau objek opsi fungsi `inject()`).
4. Mengaudit dan mengeliminasi kebocoran memori (*memory leaks*) serta instansiasi ganda (*split-brain singletons*) yang disebabkan oleh kesalahan konfigurasi `providedIn` atau multi-level providers.
5. Merancang arsitektur isolasi multi-tenant yang aman menggunakan *hierarchical scoping* di lingkungan runtime enterprise.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma
Dalam JavaScript murni, pengikatan dependensi bersifat instansiasi langsung (*imperative coupling*) melalui keyword `new` atau impor modul statis. Pendekatan ini merusak prinsip *Inversion of Control* (IoC) dan mempersulit pengujian unit, pemisahan perhatian (*separation of concerns*), serta dynamic module swapping.

Angular memperlakukan *Dependency Injection* bukan sekadar service locator, melainkan sebuah **Hierarchical Graph Directed Acyclic Graph (DAG) Runtime Engine**. Dependensi tidak diambil dari global scope secara naif, melainkan diminta melalui kontrak antarmuka ke *node* terdekat dalam pohon injektor. Jika sebuah *node* tidak memiliki dependensi tersebut, ia mendelegasikan pencarian ke simpul induknya (*parent node*) hingga mencapai batas absolut (*NullInjector*).

```
[Mental Model: Imperative Coupling vs Inversion of Control]

Imperatif (Tightly Coupled):
[Komponen Consumer] ---> new AuthService() ---> [Instans AuthService]
Masalah: Sulit di-mock, konfigurasi kaku, siklus hidup terikat erat pada pemanggil.

Inversion of Control (Angular DI):
[Komponen Consumer] ---> Minta Token: AUTH_SERVICE ---> [Injector Node]
                                                              |
                                           +------------------+------------------+
                                           | Cek Cache Lokal?                     |
                                           | - Ya: Kembalikan instance           |
                                           | - Tidak: Buat via Provider Factory  |
                                           |          Delegasikan ke Parent...   |
                                           +-------------------------------------+
```

Sebagai perancang sistem enterprise, pandanglah injector Angular sebagai serangkaian *scope containment zones* yang melindungi isolasi status (*state isolation*) dari modul-modul yang berbeda.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah kap mesin (dimulai dari Angular v14+ ke arsitektur standalone modern), pohon injeksi Angular dipisahkan menjadi dua pohon independen yang saling berkomunikasi: **ElementInjector Tree** dan **EnvironmentInjector Tree**.

### Diagram Resolusi Dependensi Dua Jalur

```
                +-------------------------+
                |      NullInjector       | (Melempar error NG0203 jika not found)
                +-------------------------+
                             ^
                             |
                +-------------------------+
                |    PlatformInjector     | (Platform-level: DOM sanitizer, platform ID)
                +-------------------------+
                             ^
                             |
                +-------------------------+
                |  Root EnvironmentInjector| (Layanan: @Injectable({ providedIn: 'root' }))
                +-------------------------+
                   ^                     ^
                   |                     |
     +-------------+-------+      +------+----------------+
     | EnvironmentInjector |      |  EnvironmentInjector  | (Route Lazy Load / Modul)
     +---------------------+      +-----------------------+
                ^
                | (Fallback saat ElementInjector habis)
                |
     +---------------------+
     | ElementInjector (App|
     |      Root Node)     | (AppComponent: providers: [...])
     +---------------------+
                ^
                |
     +---------------------+
     | ElementInjector     |
     | (Feature Parent)    | (ParentComponent: viewProviders / providers)
     +---------------------+
                ^
                |
     +---------------------+
     | ElementInjector     |
     | (Active Child Node) | (ChildComponent -> Memanggil inject(TOKEN))
     +---------------------+
```

### Diagram Alur Algoritma Traversal Resolusi

```
[Mulai Resolusi: inject(TOKEN)]
              |
              v
    +-------------------+
    | Periksa modifier  | ---> (@Self / self: true) ---> [Cari di Current ElementInjector saja]
    | pencarian?        |
    +-------------------+
              |
              +---------------> (@SkipSelf / skipSelf: true) ---> [Lewati Current, mulai dari Parent Element]
              |
              v
[Cari di Current ElementInjector Node]
              |
      [Ditemukan?] -- Ya --> [Return Instance (Singleton dalam scope ini)]
              |
            Tidak
              |
              v
[Apakah ada Parent ElementInjector?]
              |
      +-------+-------+
      | Ya            | Tidak
      v               v
[Pindah ke Parent]  [Pindah ke EnvironmentInjector (Scope Aktif)]
                      |
              [Ditemukan di Environment Tree?]
                      |
              +-------+-------+
              | Ya            | Tidak
              v               v
    [Return Instance]    [Naik ke Root -> Platform -> NullInjector]
                                  |
                           [@Optional() digunakan?]
                                  |
                          +-------+-------+
                          | Ya            | Tidak
                          v               v
                     [Return null]   [LEMPAR RUNTIME EXCEPTION]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. `ElementInjector`
Dibuat secara implisit pada setiap komponen DOM atau direktif. Jika komponen mendefinisikan array `providers: [...]` atau `viewProviders: [...]`, Angular akan menginstansiasi node `ElementInjector` yang terisi penuh. Jika array tersebut kosong, Angular membuat injektor kosong yang langsung mendelegasikan pencarian ke induknya untuk efisiensi memori.

### 2. `EnvironmentInjector`
Menggantikan hierarki modular lama. Node ini disediakan oleh:
* Node `root` (diinisialisasi saat `bootstrapApplication`).
* Rute yang dimuat secara malas (*lazy-loaded routes*) yang memiliki definisi `providers: [...]` di konfigurasi rute.
* Fitur modular legacy melalui `@NgModule()`.

### 3. Struktur Memori: Bloom Filter Internal
Untuk mempercepat pengecekan apakah sebuah *token* ada pada suatu *node* tanpa memindai seluruh *array providers*, Angular mengompilasi representasi bitwise melalui **Bloom Filter** (berbasis array 8-angka `bloomFilter` pada node kompilasi Ivy). Jika bitwise AND bernilai `0`, Angular langsung melompati *node* tersebut ke *parent node*, memotong waktu penelusuran dari $O(N)$ menjadi $O(1)$ untuk kondisi kegagalan.

### 4. Perbedaan `providers` vs `viewProviders`
* `providers`: Dependensi dapat diakses oleh komponen itu sendiri, seluruh elemen turunannya di dalam template, dan komponen proyeksi (`<ng-content>`).
* `viewProviders`: Membatasi injeksi hanya untuk *View Children* internal komponen tersebut. Dependensi **tidak akan bocor** ke proyeksi konten (`ng-content`), mencegah manipulasi internal oleh library pihak ketiga atau pemanggil eksternal.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Tree-Shakable Providers
Pola klasik Angular mendaftarkan dependensi langsung ke dalam modul:
```typescript
// ANTI-PATTERN: Menghalangi Dead-Code Elimination (DCE)
@NgModule({
  providers: [LargeAnalyticsService]
})
export class AnalyticsModule {}
```
Pola ini memaksa bundler (seperti ESBuild atau Webpack) mempertahankan `LargeAnalyticsService` di dalam berkas produksi meskipun tidak ada komponen yang mengonsumsinya.

Pendekatan enterprise modern mengharuskan *inverted link*, di mana token atau service mereferensikan dirinya sendiri:
```typescript
@Injectable({
  providedIn: 'root' // Bundler akan menghapus class ini jika tidak ada yang menginjeksi
})
export class ModernAnalyticsService {}
```

### Multi Providers & Pluggable Architecture
Kunci `multi: true` memungkinkan satu token tunggal memiliki banyak implementasi yang terdaftar secara independen. Sistem mengumpulkan semua nilai ke dalam sebuah larik (*array*).

```typescript
export const METRIC_COLLECTOR = new InjectionToken<MetricCollector[]>('METRIC_COLLECTOR');

// Pada provider runtime:
{ provide: METRIC_COLLECTOR, useClass: DatadogMetricCollector, multi: true },
{ provide: METRIC_COLLECTOR, useClass: PrometheusMetricCollector, multi: true }
```

### Fungsi `inject()` vs Constructor Injection
Fungsi `inject()` beroperasi dalam **Injection Context** yang aktif (saat instantiasi kelas, eksekusi factory, atau inisialisasi properti). Fungsi ini memberikan pengetikan yang lebih kuat (*type-safety*) dan memungkinkan komposisi dependensi tingkat lanjut melalui fungsi pembantu fungsional tanpa memicu *constructor bloat*.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah perbandingan deklarasi provider enterprise yang memanfaatkan token injection, abstraksi interface, factory kustom, dan pembatasan visibilitas.

```typescript
// app/core/tokens/api-config.token.ts
import { InjectionToken, inject } from '@angular/core';

export interface ApiGatewayConfig {
  readonly baseUrl: string;
  readonly timeoutMs: number;
  readonly retryAttempts: number;
}

// Tree-shakable factory InjectionToken
export const API_GATEWAY_CONFIG = new InjectionToken<ApiGatewayConfig>(
  'API_GATEWAY_CONFIG',
  {
    providedIn: 'root',
    factory: () => ({
      baseUrl: 'https://api.enterprise.internal/v1',
      timeoutMs: 5000,
      retryAttempts: 3,
    }),
  }
);
```

```typescript
// app/core/services/logger.service.ts
import { Injectable, InjectionToken } from '@angular/core';

export interface LoggerService {
  log(message: string): void;
}

export const LOGGER_TOKEN = new InjectionToken<LoggerService>('LOGGER_TOKEN');

@Injectable({ providedIn: 'root' })
export class ConsoleLoggerService implements LoggerService {
  log(message: string): void {
    console.info(`[SYSTEM LOG]: ${message}`);
  }
}
```

```typescript
// app/features/widget/scoped-widget.component.ts
import { 
  Component, 
  inject, 
  Optional, 
  Self, 
  SkipSelf 
} from '@angular/core';
import { API_GATEWAY_CONFIG, ApiGatewayConfig } from '../tokens/api-config.token';
import { LOGGER_TOKEN, LoggerService, ConsoleLoggerService } from '../services/logger.service';

@Component({
  selector: 'app-scoped-widget',
  standalone: true,
  template: `
    <div class="p-4 border">
      <p>Base URL: {{ config.baseUrl }}</p>
    </div>
  `,
  providers: [
    // Instansiasi LoggerService baru hanya untuk siklus hidup komponen ini
    { provide: LOGGER_TOKEN, useClass: ConsoleLoggerService }
  ]
})
export class ScopedWidgetComponent {
  // 1. Ekstraksi config dengan global fallback
  protected readonly config: ApiGatewayConfig = inject(API_GATEWAY_CONFIG);

  // 2. Ekstraksi logger hanya dari ElementInjector milik komponen ini sendiri
  protected readonly localLogger: LoggerService = inject(LOGGER_TOKEN, { 
    self: true 
  });

  // 3. Resolusi logger dari leluhur (parent), jika tidak ada return null tanpa crash
  protected readonly parentLogger: LoggerService | null = inject(LOGGER_TOKEN, { 
    skipSelf: true, 
    optional: true 
  });

  constructor() {
    this.localLogger.log('WidgetComponent initialized locally.');
    if (this.parentLogger) {
      this.parentLogger.log('WidgetComponent child notified parent.');
    }
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanika penting dari kode di atas:

1. `export const API_GATEWAY_CONFIG = new InjectionToken<ApiGatewayConfig>(...)`:
   Menciptakan objek *reified token*. Karena JavaScript menghapus antarmuka TypeScript saat kompilasi (*type erasure*), antarmuka `ApiGatewayConfig` tidak dapat digunakan sebagai kunci hash DI. Token ini bertindak sebagai representasi runtime unik dari antarmuka tersebut.
2. `providedIn: 'root', factory: () => ({ ... })`:
   Mendefinisikan *default factory*. Jika modul atau komponen tidak menyediakan provider eksplisit untuk token ini, injektor akar akan otomatis menjalankan fungsi pabrik ini. Jika token tidak pernah dirujuk di mana pun, seluruh fungsi pabrik akan dibuang dari hasil build akhir oleh bundler.
3. `providers: [{ provide: LOGGER_TOKEN, useClass: ConsoleLoggerService }]`:
   Menginstruksikan Angular untuk membuat node `ElementInjector` baru khusus untuk instans `ScopedWidgetComponent` ini. Setiap kali komponen ini dibuat dalam DOM, instans `ConsoleLoggerService` yang baru dan independen akan diisolasi di tingkat memori komponen.
4. `inject(LOGGER_TOKEN, { self: true })`:
   Menginstruksikan resolusi untuk **hanya** memeriksa node `ElementInjector` lokal milik komponen. Jika provider tidak terdaftar di metadata `providers` komponen itu sendiri, sistem akan langsung melempar exception `NullInjectorError: No provider for LOGGER_TOKEN`, tanpa memeriksa parent atau root.
5. `inject(LOGGER_TOKEN, { skipSelf: true, optional: true })`:
   * `skipSelf: true`: Mengabaikan injektor lokal dan langsung melompati pencarian ke komponen leluhur.
   * `optional: true`: Mengubah perilaku default Angular yang fail-fast. Jika dependensi tidak ditemukan hingga mencapai `NullInjector`, runtime tidak akan melempar error, melainkan menetapkan nilai variabel menjadi `null`.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Enterprise Production Scenario)

### Permasalahan: Arsitektur Multi-Tenant Dashboard FinTech
Sebuah sistem perbankan korporat multinasional memiliki satu dashboard web tunggal yang berjalan di ratusan cabang secara bersamaan. 

**Persyaratan Bisnis:**
1. Pengguna dapat berganti konteks tenant (misal: Unit Bisnis Indonesia vs Unit Bisnis Singapura) tanpa memuat ulang aplikasi (*zero full-page reload*).
2. Setiap tenant memiliki konfigurasi API gateway, protokol enkripsi data, dan state sesi (*session state*) yang sepenuhnya terisolasi.
3. **Persyaratan Keamanan:** State audit tenant A **tidak boleh** bocor atau terbaca oleh tenant B melalui instansiasi singleton bersama (*Strict Memory Isolation*).
4. Layanan audit harus mencatat riwayat transaksi secara otomatis dengan menyuntikkan tenant-id yang relevan secara dinamis ke seluruh rute transaksi di dalamnya.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistem isolasi tenant tingkat enterprise yang tangguh menggunakan `InjectionToken`, rute dinamis, dan `EnvironmentInjector`.

```typescript
// app/core/tenant/tenant.types.ts
export interface TenantConfig {
  tenantId: string;
  currency: string;
  cryptoSignatureAlgorithm: 'SHA-256' | 'RSA-PSS';
}

export abstract class TenantSessionContext {
  abstract getSessionData(): TenantConfig;
  abstract flushSession(): void;
}
```

```typescript
// app/core/tenant/tenant.tokens.ts
import { InjectionToken } from '@angular/core';
import { TenantConfig, TenantSessionContext } from './tenant.types';

export const TENANT_CONFIG = new InjectionToken<TenantConfig>('TENANT_CONFIG');
export const TENANT_SESSION_CONTEXT = new InjectionToken<TenantSessionContext>('TENANT_SESSION_CONTEXT');
```

```typescript
// app/core/tenant/tenant-crypto.service.ts
import { Injectable, inject } from '@angular/core';
import { TENANT_CONFIG } from './tenant.tokens';

@Injectable()
export class TenantCryptoService {
  private readonly config = inject(TENANT_CONFIG);

  public signPayload(payload: string): string {
    return `[Signed with ${this.config.cryptoSignatureAlgorithm} for Tenant ${this.config.tenantId}]: ${payload}`;
  }
}
```

```typescript
// app/core/tenant/isolated-tenant-session.service.ts
import { Injectable, inject, OnDestroy } from '@angular/core';
import { TENANT_CONFIG } from './tenant.tokens';
import { TenantConfig, TenantSessionContext } from './tenant.types';

@Injectable()
export class IsolatedTenantSessionService implements TenantSessionContext, OnDestroy {
  private readonly config = inject(TENANT_CONFIG);
  private cache: Map<string, unknown> = new Map();

  constructor() {
    console.info(`[ALLOCATION] Tenant Session ${this.config.tenantId} initialized.`);
  }

  getSessionData(): TenantConfig {
    return this.config;
  }

  flushSession(): void {
    this.cache.clear();
  }

  ngOnDestroy(): void {
    this.flushSession();
    console.info(`[DEALLOCATION] Tenant Session ${this.config.tenantId} purged safely.`);
  }
}
```

```typescript
// app/features/tenant/tenant-scope.component.ts
import { 
  Component, 
  Input, 
  inject, 
  Host, 
  ChangeDetectionStrategy 
} from '@angular/core';
import { 
  TENANT_CONFIG, 
  TENANT_SESSION_CONTEXT 
} from '../../core/tenant/tenant.tokens';
import { TenantCryptoService } from '../../core/tenant/tenant-crypto.service';
import { IsolatedTenantSessionService } from '../../core/tenant/isolated-tenant-session.service';
import { TenantConfig } from '../../core/tenant/tenant.types';

@Component({
  selector: 'app-tenant-scope-wrapper',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    // Sub-pohon injector terisolasi per batas DOM komponen wrapper
    TenantCryptoService,
    {
      provide: TENANT_SESSION_CONTEXT,
      useClass: IsolatedTenantSessionService
    },
    {
      provide: TENANT_CONFIG,
      useFactory: (comp: TenantScopeWrapperComponent): TenantConfig => {
        return {
          tenantId: comp.tenantId,
          currency: comp.currency,
          cryptoSignatureAlgorithm: comp.algo
        };
      },
      deps: [TenantScopeWrapperComponent]
    }
  ],
  template: `
    <div class="tenant-boundary p-6 border-2 border-indigo-700 rounded-lg">
      <h3 class="text-xl font-bold">Scope Aktif: {{ session.getSessionData().tenantId }}</h3>
      <ng-content></ng-content>
    </div>
  `
})
export class TenantScopeWrapperComponent {
  @Input({ required: true }) tenantId!: string;
  @Input({ required: true }) currency!: string;
  @Input({ required: true }) algo: 'SHA-256' | 'RSA-PSS' = 'SHA-256';

  protected readonly session = inject(TENANT_SESSION_CONTEXT, { self: true });
}
```

```typescript
// app/features/tenant/transaction-view.component.ts
import { Component, inject } from '@angular/core';
import { TENANT_SESSION_CONTEXT } from '../../core/tenant/tenant.tokens';
import { TenantCryptoService } from '../../core/tenant/tenant-crypto.service';

@Component({
  selector: 'app-transaction-view',
  standalone: true,
  template: `
    <div class="transaction-panel">
      <p>Tenant ID Terikat: {{ session.getSessionData().tenantId }}</p>
      <button (click)="executeTransaction()">Proses Pembayaran</button>
    </div>
  `
})
export class TransactionViewComponent {
  // Mengambil instance dari TenantScopeWrapper terdekat di hierarki DOM
  protected readonly session = inject(TENANT_SESSION_CONTEXT);
  private readonly crypto = inject(TenantCryptoService);

  executeTransaction(): void {
    const signature = this.crypto.signPayload('TRX_AMOUNT=500000');
    console.info('Transaksi Diproses:', signature);
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Parameter | `@Injectable({ providedIn: 'root' })` | `Component.providers: [...]` | `Component.viewProviders: [...]` | `Route.providers: [...]` |
| :--- | :--- | :--- | :--- | :--- |
| **Pohon Injektor** | EnvironmentInjector (Root) | ElementInjector | ElementInjector | EnvironmentInjector (Route Branch) |
| **Siklus Hidup** | Seumur hidup aplikasi berjalan | Terikat pada mount/unmount DOM Komponen | Terikat pada mount/unmount DOM Komponen | Terikat pada navigasi keluar rute |
| **Tree-Shakable?** | Sangat Tinggi (Jika tak dirujuk) | Tidak (Tercakup pada bundle chunk komponen) | Tidak (Tercakup pada bundle chunk komponen) | Rendah-Sedang (Tergantung bundle chunk route) |
| **Isolasi State** | Nol (Global State / Singleton Mutlak) | Tinggi (Isolasi per instans DOM elemen) | Maksimal (Tidak bocor ke `<ng-content>`) | Menengah (Bisa diakses seluruh anak rute) |
| **Beban Memori** | Rendah (Hanya 1 instans untuk semua) | Tinggi jika elemen di-render dalam `*ngFor` masif | Tinggi jika elemen di-render dalam `*ngFor` masif | Efisien untuk sub-pohon fitur kompleks |
| **Rekomendasi Kasus** | HTTP Clients, Auth State global, Logger | Form state lokal, Tenant encapsulation wrapper | Custom UI Kit, Design System Component | Feature Module Scope, Multi-step Wizard |

---

## SEKSI 12 — EDGE CASES & PITFALLS (Failure Modes & Mitigation)

### 1. The Split-Brain Singleton Issue
* **Kasus:** Layanan global `AuthService` yang seharusnya unik di seluruh aplikasi secara tidak sengaja didaftarkan pada array `providers: [AuthService]` di dalam sebuah komponen `LoginFeatureComponent`.
* **Dampak Kerusakan:** Komponen login dan anak-anaknya beroperasi menggunakan instans `AuthService` lokal, sementara navbar dan route guards membaca instans global dari `providedIn: 'root'`. Akibatnya, status login berhasil diubah di form, tetapi user tetap dianggap unauthorized oleh guard aplikasi.
* **Mitigasi:** Pasang guard di constructor layanan singleton untuk mencegah instansiasi ganda secara langsung di runtime:

```typescript
@Injectable({ providedIn: 'root' })
export class CriticalAuthEngine {
  constructor() {
    const parentInstance = inject(CriticalAuthEngine, { 
      optional: true, 
      skipSelf: true 
    });
    
    if (parentInstance) {
      throw new Error(
        'CriticalAuthEngine terdeteksi ganda! Layanan ini adalah Root Singleton dan dilarang dimasukkan ke array providers komponen manapun.'
      );
    }
  }
}
```

### 2. Dependency Token Cycle (Circular Dependencies)
* **Kasus:** Service A menginjeksi Service B, dan Service B menginjeksi Service A secara langsung di constructor.
* **Dampak Kerusakan:** Runtime melempar error: `Circular dependency detected: ServiceA -> ServiceB -> ServiceA` atau kegagalan resolusi variabel `undefined`.
* **Mitigasi Teknis:**
  1. *Refactoring:* Pisahkan domain logika bersama (*shared domain logic*) ke Service C yang diinjeksi oleh keduanya.
  2. Gunakan `Injector` langsung dan resolusikan dependensi secara malas (*lazy-resolution*) hanya pada saat metode dipanggil:

```typescript
@Injectable({ providedIn: 'root' })
export class ServiceA {
  private readonly injector = inject(Injector);

  public executeTask(): void {
    // Resolusi di-defer sampai metode dieksekusi, memutus loop saat siklus konstruksi
    const serviceB = this.injector.get(ServiceB);
    serviceB.doSomething();
  }
}
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Menggunakan Factory Tanpa Penanganan Konteks
* **Kode Salah:**
```typescript
// DI LUAR INJECTION CONTEXT
const token = new InjectionToken('ERR', {
  factory: () => {
    // Menjalankan operasi asinkron yang memanggil inject di kemudian hari
    setTimeout(() => {
      const http = inject(HttpClient); // RUNTIME CRASH: NG0203!
    }, 1000);
  }
});
```
* **Cara Memperbaiki:** Tangkap dependensi secara serempak (*synchronously*) pada siklus inisialisasi factory:
```typescript
const token = new InjectionToken('FIX', {
  factory: () => {
    const http = inject(HttpClient); // Ditangkap tepat pada injection context
    return {
      fetchData: () => http.get('/api')
    };
  }
});
```

### Kesalahan Fatal 2: Kebocoran Abstraksi Melalui Kelas Konkret
* **Kode Salah:** Menggunakan kelas implementasi langsung sebagai tipe token DI di enterprise library. Hal ini menyebabkan pengujian unit harus memuat seluruh dependensi internal dari kelas tersebut.
* **Cara Memperbaiki:** Pisahkan interface definisi dari kelas implementasi, gunakan `InjectionToken<Interface>` yang diekspor terpisah dari modul internal.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan `inject()` Function:** Standarisasi codebase modern Anda untuk meninggalkan constructor injection. Fungsi `inject()` mempermudah implementasi *Higher-Order Functions* (misal: composable functions ala `injectDestroy()`, `injectParams()`).
2. **Prinsip Immutability Konfigurasi:** Jadikan semua konfigurasi yang diinjeksi melalui `InjectionToken` bertipe `readonly` atau gunakan `Object.freeze()` untuk mencegah mutasi state konfigurasi antar modul.
3. **Pemberian Nama Token yang Jelas:** Gunakan konvensi penamaan huruf kapital dengan akhiran `_TOKEN` untuk kejelasan identitas (contoh: `APP_CONFIG_TOKEN`, `TENANT_ID_TOKEN`).
4. **Isolasi Fitur Modular:** Jangan pernah memasukkan *stateful data services* ke `providedIn: 'root'` jika data tersebut hanya dibutuhkan pada satu rute spesifik. Pasang provider tersebut langsung pada konfigurasi rutenya:
```typescript
export const FEATURE_ROUTES: Route[] = [
  {
    path: 'checkout',
    providers: [CheckoutStateService], // Dihancurkan otomatis saat meninggalkan sub-rute
    component: CheckoutRootComponent,
  }
];
```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Menghindari "Bloated ElementInjectors"
Setiap kali Anda mendeklarasikan `providers: [...]` di sebuah komponen, Angular mengalokasikan memori untuk satu node `ElementInjector` baru, instance layanan, serta tabel pencariannya. Jika komponen tersebut di-render sebanyak 10.000 kali di dalam sebuah tabel virtual, overhead memorinya akan sangat signifikan.

* **Strategi Mitigasi:** Pindahkan penyediaan dependency ke tingkat penampung utama (*container component*), dan alirkan data ke bawah menggunakan `@Input()` signals murni atau *lightweight presentation pattern*.

### 2. Manual EnvironmentInjector Creation untuk Dynamic Component
Saat membuat komponen secara terprogram (*programmatic dynamic component rendering*) menggunakan `ViewContainerRef.createComponent`, hindari pembuatan injector manual yang tidak perlu jika Anda bisa mewariskan injektor yang sudah ada:

```typescript
@Component({ /* ... */ })
export class DynamicHostComponent {
  private readonly vcr = inject(ViewContainerRef);
  private readonly envInjector = inject(EnvironmentInjector);

  public renderDynamic(tenantCustomInjector: Injector): void {
    // Injector hierarkis kustom dihubungkan langsung ke komponen dinamis
    this.vcr.createComponent(CustomWidgetComponent, {
      environmentInjector: this.envInjector,
      injector: tenantCustomInjector
    });
  }
}
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Mencegah Kebocoran Secret melalui Injection Token
Nilai konfigurasi sensitif yang disediakan melalui `InjectionToken` dapat diekstraksi dari DOM browser jika aplikasi berjalan dalam mode pengujian atau jika tools inspeksi runtime Angular diaktifkan (`ng.probe`).
* **Aturan Mutlak:** Jangan pernah mengalirkan private API keys, master signature keys, atau data kredensial rahasia langsung ke Angular DI token di sisi client. Semua rahasia harus tetap berada di layer backend atau BFF (Backend-For-Frontend).

### 2. Isolasi Proyeksi Menggunakan `viewProviders`
Jika komponen Anda memproyeksikan konten eksternal menggunakan `<ng-content>`, komponen eksternal yang diproyeksikan tersebut dapat mengakses provider internal komponen Anda jika didaftarkan di array `providers`.
* **Tindakan Hardening:** Gunakan `viewProviders` untuk layanan internal yang mengelola kredensial sesi lokal agar terisolasi dari proyeksi pihak ketiga:

```typescript
@Component({
  selector: 'app-secure-zone',
  standalone: true,
  template: `
    <div class="secure-wrapper">
      <internal-vault-ui></internal-vault-ui>
      <ng-content></ng-content> <!-- Komponen di sini TIDAK BISA menginjeksi SecureVaultService -->
    </div>
  `,
  // viewProviders mencegah akses token dari anak proyeksi luar
  viewProviders: [SecureVaultService] 
})
export class SecureZoneComponent {}
```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### 1. Melacak Hierarki Resolusi di DevTools
Gunakan API runtime bawaan Angular di konsol JavaScript browser untuk mendebug rantai DI pada elemen DOM yang aktif:

```javascript
// Dapatkan node ElementInjector dari elemen DOM yang dipilih di Inspect Elements ($0)
const node = ng.getContext($0);
const injector = ng.getInjector($0);

// Resolusi dependensi secara manual dari console
const activeTenant = injector.get(TENANT_CONFIG_TOKEN);
console.log('Inspected Active Tenant:', activeTenant);
```

### 2. Middleware Telemetri Melalui Multi-Tokens
Rancang telemetri terdistribusi berbasis token dengan memetakan seluruh interaksi injeksi menggunakan proxy:

```typescript
export interface DiagnosticHook {
  onServiceInstantiated(serviceName: string): void;
}

export const DIAGNOSTIC_HOOKS = new InjectionToken<DiagnosticHook[]>('DIAGNOSTIC_HOOKS');

export function createObservedService<T extends object>(serviceClass: new (...args: any[]) => T): T {
  const instance = inject(serviceClass);
  const hooks = inject(DIAGNOSTIC_HOOKS, { optional: true }) ?? [];
  
  hooks.forEach(hook => hook.onServiceInstantiated(serviceClass.name));
  return instance;
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **`providedIn: 'root'`**: Default mutlak untuk stateless utility, global state management, dan layanan singleton berorientasi tree-shake.
* **`providers: [...]` pada Komponen**: Menciptakan instance baru untuk setiap instance komponen. Terlihat oleh komponen itu sendiri, view-child, dan konten yang diproyeksikan (`ng-content`).
* **`viewProviders: [...]` pada Komponen**: Sama seperti di atas, namun **tidak terlihat** oleh elemen yang diproyeksikan melalui `ng-content`.
* **`providers: [...]` pada Rute**: Menciptakan EnvironmentInjector yang terisolasi untuk rute tersebut beserta seluruh sub-rute turunannya. Dibersihkan saat rute dihancurkan.
* **Modifiers Flags**:
  * `{ self: true }` $\rightarrow$ Hanya periksa node saat ini.
  * `{ skipSelf: true }` $\rightarrow$ Mulai pencarian dari parent, abaikan node sendiri.
  * `{ optional: true }` $\rightarrow$ Kembalikan `null` jika tidak ditemukan, jangan lempar runtime error.
  * `{ host: true }` $\rightarrow$ Batasi pencarian hingga node template komponen induk penampung (*host component*).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Sebuah layanan `AuditService` **tidak** memiliki dekorator `{ providedIn: 'root' }`. Layanan ini terdaftar di array `providers: [AuditService]` pada `ParentComponent`. `ChildComponent` berada di dalam template `ParentComponent` dan memiliki dependensi:
`audit = inject(AuditService, { skipSelf: true, self: true });`
Apa yang akan terjadi pada runtime saat `ChildComponent` dirender?
* A. Berhasil mengambil instance dari `ParentComponent`.
* B. Melempar `Runtime Error (NG0203 atau NullInjectorError)` karena modifier saling berkontradiksi secara logika.
* C. Mengembalikan nilai `null`.
* D. Menginstansiasi instance baru secara diam-diam.

### Soal 2
Bagaimana cara yang paling tepat untuk mendesain token injection konfigurasi enterprise agar dapat dibuang (*tree-shaken*) dari berkas akhir produksi jika fitur terkait tidak diimpor oleh aplikasi?
* A. Mendaftarkannya di modul utama via `AppModule.forRoot({ ... })`.
* B. Menggunakan `new InjectionToken('TOKEN')` dan menyediakannya di `main.ts`.
* C. Menggunakan `new InjectionToken('TOKEN', { providedIn: 'root', factory: () => DEFAULT_CONFIG })`.
* D. Mendaftarkannya ke dalam file `environment.ts` secara langsung.

### Soal 3
Apa perbedaan teknis paling mendasar antara `providers` dan `viewProviders` pada metadata dekorator `@Component`?
* A. `viewProviders` hanya bekerja pada arsitektur berbasis Module lama, bukan Standalone Component.
* B. `providers` mencakup instansiasi layanan untuk komponen yang diproyeksikan melalui `<ng-content>`, sedangkan `viewProviders` menutup akses injeksi tersebut bagi konten proyeksi.