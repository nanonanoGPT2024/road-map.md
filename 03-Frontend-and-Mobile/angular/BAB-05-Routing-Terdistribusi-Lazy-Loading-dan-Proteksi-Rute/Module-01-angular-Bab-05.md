# Modul Pembelajaran: Routing Terdistribusi, Lazy Loading, dan Proteksi Rute

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Topik:** Angular Core Architecture
* **Bab:** 05 — Navigasi & Arsitektur Modular Skala Enterprise
* **Modul:** 01 — Routing Terdistribusi, Lazy Loading, dan Proteksi Rute
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Target Stack:** Angular 17/18+ (Standalone Components, Signals, Functional Guards, Modern Router APIs, Vite/ESBuild)

---

## SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta mampu:
1. Merancang arsitektur rute terdistribusi bertingkat menggunakan paradigma modern Angular Standalone APIs (`loadChildren`, `loadComponent`) tanpa dependensi legacy `NgModule`.
2. Menganalisis siklus hidup eksekusi internal Angular Router: URL parsing, routing tree resolution, guard traversal, preloading, component instantiation, hingga router-outlet activation.
3. Mengimplementasikan proteksi rute multi-layer menggunakan Functional Guards (`CanActivateFn`, `CanMatchFn`, `CanDeactivateFn`) terintegrasi dengan reactive store dan signals.
4. Menerapkan strategi *differential preloading* berbasis jaringan pengguna (Network-Aware Preloading) untuk mengoptimalkan *Largest Contentful Paint* (LCP) dan *Total Blocking Time* (TBT).
5. Mencegah kerentanan keamanan sisi klien seperti bypass otorisasi rute, kebocoran state URL (open redirects), dan memory leaks akibat lingering router event subscriptions.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: Router Sebagai Distributed State Machine
Jangan memandang Angular Router sekadar sebagai mekanisme pemetaan string URL ke template HTML. Pandanglah router sebagai **Hierarchical Finite State Machine (HFSM)** terdistribusi.

```
[URL Mutation] ---> [Lexical Parser] ---> [Async Verification (Guards)]
                                                    |
                                      +-------------+-------------+
                                      | Passed                    | Rejected
                                      v                           v
                           [Code Splitting Boundary]      [Redirect / Halt]
                                      |
                                      v
                           [Dynamic Module Resolution]
                                      |
                                      v
                           [Fiber/Component Assembly]
```

1. **State Isolation:** Setiap segmen URL merepresentasikan node independen dalam pohon rute (`ActivatedRouteSnapshot`). Node anak tidak boleh bergantung langsung pada dependensi privat node induk; komunikasi rute dilakukan via parameter, query, dan state contracts.
2. **Laziness by Default:** Setiap boundary rute adalah physical chunk boundary di level bundler (Vite/Rollup). Memuat kode yang belum dibutuhkan pengguna adalah cacat arsitektur.
3. **Guards sebagai Pipeline Interceptor:** Guards bukan sekadar filter *boolean*. Mereka adalah asynchronous middleware stream yang dapat menunda (*defer*), mengubah arah (*redirect*), atau membatalkan mutasi state sebelum alokasi memori komponen terjadi.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram Siklus Hidup Eksekusi Angular Router

```
User Action (click/navigateByUrl)
  │
  ▼
[1] NavigationStart Event emitted
  │
  ▼
[2] URL Tokenization & Parsing ─────────► Router.parseUrl() ───► UrlTree Generated
  │
  ▼
[3] Route Matching & CanMatch Execution (Async Engine)
  │
  ├─► CanMatchFn Check ─────────────────► [Fail] ──► Try next matching Route definition
  │                                             └──► (404 jika tidak ada rute lain)
  │        │ [Pass]
  │        ▼
[4] Lazy Load Boundary Processing ──────► Dynamic import() fetches bundle (.js chunk)
  │                                       Injectors Hierarchical Branch Created
  ▼
[5] Guard Resolution Pipeline
  │
  ├─► CanDeactivateFn (Leaving Component) ──► [Fail] ──► NavigationCancel
  │        │ [Pass]
  │        ▼
  ├─► CanActivateFn (Target Component)   ──► [Fail] ──► NavigationCancel / Redirect
  │        │ [Pass]
  │        ▼
  └─► ResolveFn (Pre-fetch Data)         ──► [Fail] ──► NavigationError
           │ [Pass]
           ▼
[6] Component Activation Phase
  │
  ├─► ActivatedRoute / RouteConfig Activated
  ├─► ViewContainerRef.createComponent() via <router-outlet>
  │
  ▼
[7] NavigationEnd Event emitted (State Stabilized)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Route Configuration Tree (`Routes`)
Dalam Angular modern tanpa module, rute dikonfigurasi sebagai array of plain objects berulang:
* `path`: Pola pencocokan token string. Matcher menggunakan Trie traversal algorithm.
* `loadComponent`: Mengembalikan promise dynamic import (`() => import('./comp').then(m => m.Comp)`). Bundler memisahkan ini menjadi asset chunk terisolasi.
* `loadChildren`: Digunakan untuk merutekan seluruh sub-tree konfigurasi rute (`() => import('./routes').then(m => m.ADMIN_ROUTES)`).

### 2. CanMatch vs CanActivate
* `CanMatchFn`: Dieksekusi **sebelum** Angular mencoba mengunduh chunk kode lazy-loaded. Jika bernilai `false`, Angular mengabaikan rute tersebut dan melanjutkan traversal ke entri rute berikutnya pada level yang sama. Sangat penting untuk Feature Toggling dan A/B Testing berbasis peran.
* `CanActivateFn`: Dieksekusi **setelah** chunk kode diunduh, tetapi sebelum komponen diinstansiasi ke dalam DOM tree via `router-outlet`.

### 3. Environment Injectors vs Node Injectors
Saat lazy loading rute via `loadChildren`, Angular menciptakan cabang `EnvironmentInjector` baru. Service yang disediakan di dalam `providers: [...]` pada level rute terdistribusi bersifat unik untuk cabang rute tersebut dan dibersihkan dari memori (*garbage collected*) saat rute dibongkar total jika tidak direferensikan secara global.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Internal Router Traversal: Tokenizing & Structural Matching
Ketika rute dieksekusi, URL string dipecah menjadi `UrlTree`, representasi berbasis struktur pohon serializable:
* `UrlSegmentGroup`: Kumpulan segmen rute yang dibagi berdasarkan outlet.
* `UrlSegment`: Potongan jalur URL antara dua slash (`/`), memiliki properti path dan matrix parameters.

Angular mencocokkan `UrlTree` terhadap array rute secara rekursif:
```typescript
// Konseptual pseudocode dari router matching engine
function matchRoute(route: Route, urlGroup: UrlSegmentGroup): MatchResult | null {
  if (route.matcher) return route.matcher(urlGroup.segments, urlGroup, route);
  if (route.path === '**') return { consumed: urlGroup.segments, remaining: [] };
  
  const parts = route.path.split('/');
  // Memeriksa token URL terhadap path pattern
  return evaluateSegments(parts, urlGroup.segments);
}
```

Jika rute memiliki guard `CanMatch`, Angular menunda eksekusi traversal berikutnya:
```typescript
// Resolusi CanMatch di router engine
async function processRouteMatching(route: Route, segments: UrlSegment[]): Promise<boolean> {
  if (!route.canMatch) return true;
  for (const guard of route.canMatch) {
    const result = await executeGuard(guard, route, segments);
    if (!result) return false; // Menghentikan pencocokan rute ini; cari fallback rute
  }
  return true;
}
```

### Preloading Architecture & Service Worker Synergy
Preloading diatur oleh class implementasi `PreloadingStrategy`. Default-nya adalah `NoPreloading` atau `PreloadAllModules`. Namun, untuk aplikasi enterprise, `PreloadAllModules` merusak metrik jaringan di mobile. 
Modern enterprise menggunakan pendekatan kustom:
1. Membaca properti `data` pada konfigurasi rute (`data: { preload: true }`).
2. Mengintegrasikan Network Information API (`navigator.connection.saveData` atau `navigator.connection.effectiveType`).
3. Menunda preloading hingga `requestIdleCallback` dieksekusi oleh runtime browser.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah struktur hirarki rute terdistribusi menggunakan Standalone APIs:

```typescript
// app.routes.ts (Root Router Configuration)
import { Routes } from '@angular/router';
import { authCanMatchGuard } from './core/guards/auth-can-match.guard';

export const APP_ROUTES: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'dashboard'
  },
  {
    path: 'auth',
    loadChildren: () => import('./features/auth/auth.routes').then(m => m.AUTH_ROUTES)
  },
  {
    path: 'dashboard',
    canMatch: [authCanMatchGuard],
    loadChildren: () => import('./features/dashboard/dashboard.routes').then(m => m.DASHBOARD_ROUTES)
  },
  {
    path: '**',
    loadComponent: () => import('./core/pages/not-found.component').then(m => m.NotFoundComponent)
  }
];
```

```typescript
// features/dashboard/dashboard.routes.ts (Child Distributed Configuration)
import { Routes } from '@angular/router';
import { canDeactivateFormGuard } from '../../core/guards/can-deactivate-form.guard';
import { roleCanActivateGuard } from '../../core/guards/role-can-activate.guard';
import { DashboardLayoutComponent } from './dashboard-layout.component';

export const DASHBOARD_ROUTES: Routes = [
  {
    path: '',
    component: DashboardLayoutComponent,
    children: [
      {
        path: '',
        pathMatch: 'full',
        redirectTo: 'analytics'
      },
      {
        path: 'analytics',
        loadComponent: () => import('./pages/analytics.component').then(m => m.AnalyticsComponent)
      },
      {
        path: 'settings',
        canActivate: [roleCanActivateGuard],
        canDeactivate: [canDeactivateFormGuard],
        data: { roles: ['ADMIN', 'SUPERUSER'] },
        loadComponent: () => import('./pages/settings.component').then(m => m.SettingsComponent)
      }
    ]
  }
];
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File: `app.routes.ts`
* `pathMatch: 'full', redirectTo: 'dashboard'`: Memastikan pencocokan tepat string kosong sebelum redirect dieksekusi, menghindari loop tak hingga pada pencocokan parsial (`prefix`).
* `path: 'dashboard', canMatch: [authCanMatchGuard]`: Guard `CanMatch` dipasang pada boundary rute lazy. Jika user belum login, router tidak akan mengeksekusi network request untuk mengunduh bundle `dashboard.routes`.
* `loadChildren: () => import('./features/dashboard/...').then(m => m.DASHBOARD_ROUTES)`: Menginstruksikan bundler untuk membuat chunking terpisah (`dashboard.routes-[hash].js`). Resolver mengembalikan token array rute.

### Analisis File: `dashboard.routes.ts`
* `component: DashboardLayoutComponent`: Berperan sebagai Host Container yang memiliki template `<router-outlet></router-outlet>`, mengelola navigasi sekunder atau layout shell.
* `canActivate: [roleCanActivateGuard]`: Guard dijalankan saat chunk telah tersedia, memvalidasi apakah kredensial sesi memenuhi kriteria `data: { roles: [...] }`.
* `canDeactivate: [canDeactivateFormGuard]`: Mencegah navigasi keluar jika form pada komponen masih memiliki state *dirty* atau mutasi yang belum disimpan.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Multi-Tenant Enterprise Banking & Settlement Console
Aplikasi memiliki ribuan pengguna dengan dua tipe lisensi berbeda: **Standard Corporate** dan **High-Frequency Treasury**.
* Modul **Treasury** berisi dependensi visualisasi chart WebGL berat (skala bundle ~3.5MB).
* Pengguna Standard Corporate **dilarang keras** mengunduh chunk JavaScript Treasury untuk alasan keamanan lisensi, integritas audit, dan efisiensi bandwidth seluler.
* Jika pengguna Standard mencoba mengakses URL `/settlement/treasury`, sistem tidak boleh menampilkan error 403 setelah download selesai, melainkan harus mengeksekusi fallback rute 404 (seakan-akan rute tersebut tidak pernah ada) tanpa memuat satu byte pun dari chunk Treasury.
* Sistem harus mengimplementasikan Network-Aware Adaptive Preloading untuk tenant yang memiliki akses valid.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

### 1. Model & Interface
```typescript
// core/models/auth.models.ts
export type UserRole = 'CORPORATE_USER' | 'TREASURY_ADMIN' | 'AUDITOR';

export interface UserSession {
  userId: string;
  tenantId: string;
  roles: UserRole[];
  token: string;
}

export interface ComponentCanDeactivate {
  canDeactivate: () => boolean | Promise<boolean>;
}
```

### 2. State & Session Store (Signals Architecture)
```typescript
// core/services/auth-session.service.ts
import { Injectable, signal, computed } from '@angular/core';
import { UserSession, UserRole } from '../models/auth.models';

@Injectable({ providedIn: 'root' })
export class AuthSessionService {
  private readonly _session = signal<UserSession | null>(null);

  readonly session = this._session.asReadonly();
  readonly isAuthenticated = computed(() => this._session() !== null);
  readonly roles = computed(() => this._session()?.roles ?? []);

  setSession(session: UserSession | null): void {
    this._session.set(session);
  }

  hasRole(requiredRoles: UserRole[]): boolean {
    const currentRoles = this.roles();
    return requiredRoles.some(role => currentRoles.includes(role));
  }
}
```

### 3. Functional Guards Implementation
```typescript
// core/guards/security.guards.ts
import { inject } from '@angular/core';
import { CanMatchFn, CanActivateFn, CanDeactivateFn, Router, Route, UrlSegment } from '@angular/router';
import { AuthSessionService } from '../services/auth-session.service';
import { ComponentCanDeactivate } from '../models/auth.models';

/**
 * Mencegah chunk downloading jika user tidak memiliki role valid.
 * Mengembalikan false menyebabkan Angular melanjutkan pencarian ke rute lain (fallback).
 */
export const featureAccessCanMatchGuard = (requiredRoles: string[]): CanMatchFn => {
  return (route: Route, segments: UrlSegment[]) => {
    const authService = inject(AuthSessionService);
    
    if (!authService.isAuthenticated()) {
      return false;
    }

    return authService.hasRole(requiredRoles as any);
  };
};

/**
 * Memastikan proteksi rute detail dan validasi redirection.
 */
export const strictRoleCanActivateGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthSessionService);
  const router = inject(Router);
  const expectedRoles = route.data['roles'] as string[] | undefined;

  if (!authService.isAuthenticated()) {
    return router.createUrlTree(['/auth/login'], { queryParams: { returnUrl: state.url } });
  }

  if (expectedRoles && !authService.hasRole(expectedRoles as any)) {
    return router.createUrlTree(['/forbidden']);
  }

  return true;
};

/**
 * Menahan navigasi jika ada uncommitted memory state.
 */
export const pendingChangesCanDeactivateGuard: CanDeactivateFn<ComponentCanDeactivate> = (
  component
) => {
  if (component && typeof component.canDeactivate === 'function') {
    return component.canDeactivate() || confirm('Perubahan Anda belum tersimpan. Tinggalkan halaman?');
  }
  return true;
};
```

### 4. Advanced Network-Aware Preloading Strategy
```typescript
// core/strategies/network-aware-preload.strategy.ts
import { Injectable } from '@angular/core';
import { PreloadingStrategy, Route } from '@angular/router';
import { Observable, of } from 'rxjs';

declare global {
  interface Navigator {
    connection?: {
      saveData: boolean;
      effectiveType: 'slow-2g' | '2g' | '3g' | '4g';
    };
  }
}

@Injectable({ providedIn: 'root' })
export class NetworkAwarePreloadStrategy implements PreloadingStrategy {
  preload(route: Route, load: () => Observable<any>): Observable<any> {
    // 1. Periksa apakah rute secara eksplisit mengaktifkan preload
    if (!route.data || !route.data['preload']) {
      return of(null);
    }

    // 2. Periksa constraint jaringan klien
    const conn = navigator.connection;
    if (conn) {
      if (conn.saveData) {
        return of(null); // Mode hemat data aktif
      }
      if (conn.effectiveType === '2g' || conn.effectiveType === 'slow-2g') {
        return of(null); // Koneksi terlalu lambat, jangan preload
      }
    }

    // 3. Jalankan pemuatan chunk
    return load();
  }
}
```

### 5. Root Application Setup & Route Tree Assembler
```typescript
// app.routes.ts
import { Routes } from '@angular/router';
import { featureAccessCanMatchGuard } from './core/guards/security.guards';

export const APP_ROUTES: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'settlement'
  },
  {
    path: 'settlement',
    children: [
      // HIGH PRIVILEGE ROUTE (Ukuran bundle masif)
      {
        path: 'treasury',
        canMatch: [featureAccessCanMatchGuard(['TREASURY_ADMIN'])],
        data: { preload: false }, // Jangan pernah preload modul ini
        loadChildren: () =>
          import('./features/treasury/treasury.routes').then(m => m.TREASURY_ROUTES)
      },
      // STANDARD CORPORATE ROUTE
      {
        path: 'corporate',
        canMatch: [featureAccessCanMatchGuard(['CORPORATE_USER', 'TREASURY_ADMIN'])],
        data: { preload: true }, // Preload jika kondisi jaringan optimal
        loadChildren: () =>
          import('./features/corporate/corporate.routes').then(m => m.CORPORATE_ROUTES)
      }
    ]
  },
  {
    path: 'forbidden',
    loadComponent: () => import('./core/pages/forbidden.component').then(m => m.ForbiddenComponent)
  },
  {
    path: '**',
    loadComponent: () => import('./core/pages/not-found.component').then(m => m.NotFoundComponent)
  }
];
```

```typescript
// main.ts
import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter, withPreloading, withComponentInputBinding } from '@angular/router';
import { AppComponent } from './app.component';
import { APP_ROUTES } from './app.routes';
import { NetworkAwarePreloadStrategy } from './core/strategies/network-aware-preload.strategy';

bootstrapApplication(AppComponent, {
  providers: [
    provideRouter(
      APP_ROUTES,
      withComponentInputBinding(), // Memetakan parameter rute langsung ke Signals component inputs
      withPreloading(NetworkAwarePreloadStrategy)
    )
  ]
}).catch(err => console.error(err));
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek | CanMatch Guard | CanActivate Guard | CanLoad Guard (Deprecated) |
| :--- | :--- | :--- | :--- |
| **Download Chunk Execution** | Dibatalkan total jika guard gagal (`false`). | File chunk tetap diunduh via jaringan sebelum guard dievaluasi. | Mencegah download, tetapi arsitekturnya usang dan tidak fleksibel. |
| **URL Fallback Behavior** | Melanjutkan pencarian traversal ke route candidate berikutnya. | Menghentikan traversal rute; memicu `NavigationCancel` kecuali dialihkan (`UrlTree`). | Menghentikan routing secara kaku tanpa fleksibilitas chain matching. |
| **Kasus Penggunaan Optimal** | Feature Flags, Multi-tenant routing, A/B Testing layout. | Otentikasi standar, verifikasi token kedaluwarsa, izin parameter URL. | Tidak direkomendasikan lagi untuk Angular Standalone modern. |
| **Overhead Traversal** | Sedikit lebih tinggi karena mengevaluasi dynamic matchers berulang. | Minimum, dieksekusi sekali setelah rute tunggal dikunci. | Sedang. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### Edge Case 1: Race Condition pada Otentikasi Asinkron
* **Skenario:** Pengguna me-refresh halaman pada URL `/settlement/corporate`. `AuthSessionService` membutuhkan 250ms untuk membaca token dari IndexedDB/Cookie via network refresh token handshake.
* **Failure Mode:** `CanMatch` atau `CanActivate` langsung mengembalikan `false` secara sinkron, melempar user ke halaman login secara keliru.
* **Mitigasi:** Guard wajib mereturn `Observable<boolean | UrlTree>` yang menunggu hingga status otentikasi bertransisi dari `PENDING` ke `INITIALIZED`.

```typescript
export const asyncAuthGuard: CanActivateFn = () => {
  const authService = inject(AuthSessionService);
  return toObservable(authService.isAuthInitialized).pipe(
    filter(isInit => isInit === true),
    take(1),
    map(() => authService.isAuthenticated())
  );
};
```

### Edge Case 2: Memory Leak dari Event Subscriptions Router Induk
* **Skenario:** Melakukan `inject(Router).events.subscribe()` di level shared component atau root layout tanpa manual unsubscribing atau lifecycle teardown.
* **Failure Mode:** Setiap perpindahan rute lazy bertingkat membuat subscription baru yang mempertahankan referensi closure komponen sebelumnya di heap memory.
* **Mitigasi:** Wajib gunakan `takeUntilDestroyed()` operator di Angular modern atau gunakan API router berbasis Signal.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Hardcoded Redirect Loop pada Wildcard (`**`)
* **Salah:**
  ```typescript
  { path: '', redirectTo: '/home', pathMatch: 'prefix' } // Salah! Prefix match string kosong akan selalu valid dan trigger rekursif tak terbatas.
  ```
* **Benar:**
  ```typescript
  { path: '', redirectTo: '/home', pathMatch: 'full' }
  ```

### 2. Menggunakan Direct Boolean True/False pada Guard Kegagalan Navigasi
* **Salah:**
  ```typescript
  // Mengembalikan false tanpa navigasi fallback membingungkan pengguna (UI hang/stuck)
  export const badGuard: CanActivateFn = () => false;
  ```
* **Benar:**
  ```typescript
  // Mengembalikan UrlTree memicu redirect eksplisit, menjaga kontinuitas UX
  export const goodGuard: CanActivateFn = () => {
    const router = inject(Router);
    return router.createUrlTree(['/login']);
  };
  ```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Functional Guards Eksklusif:** Hindari class-based guards (`implements CanActivate`). Functional guards meminimalkan boilerplate, lebih *tree-shakeable*, dan memanfaatkan function composition murni.
2. **Pemanfaatan `withComponentInputBinding()`:** Hindari injeksi `ActivatedRoute` hanya untuk membaca snapshot query parameters atau matrix parameters. Binding langsung ke input component mengisolasi komponen dari dependensi langsung Router framework:
   ```typescript
   // Component modern
   export class UserDetailComponent {
     @Input() id!: string; // Otomatis terpetakan dari /user/:id via withComponentInputBinding
   }
   ```
3. **Pemisahan Konfigurasi Rute Terisolasi:** Setiap modul domain harus memiliki filenya sendiri (misal: `orders.routes.ts`, `customers.routes.ts`) yang diekspor sebagai konstanta `const`, menjaga boundary modularitas arsitektur.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Chunk Budgeting & Vite Analysis
Atur chunk sizing thresholds pada `angular.json` untuk mencegah bundling bloat:
```json
"budgets": [
  {
    "type": "initial",
    "maximumWarning": "500kB",
    "maximumError": "1MB"
  },
  {
    "type": "anyComponentStyle",
    "maximumWarning": "4kB",
    "maximumError": "8kB"
  }
]
```

### Tree-Shaking Providers pada Boundary Rute
Deklarasikan service langsung di rute tree untuk cakupan terisolasi jika tidak dipakai global:
```typescript
export const SETTINGS_ROUTES: Routes = [
  {
    path: '',
    providers: [SettingsFeatureStore], // Akan di-destroy otomatis saat modul rute ini ditinggalkan
    component: SettingsComponent
  }
];
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### Client-Side Guard Bukan Batas Otorisasi Nyata
* **Ancaman:** Penyerang mengubah state `canActivate` via runtime JavaScript patching (misal melalui Chrome DevTools Console) untuk memaksa router merender tampilan admin.
* **Hardening:** Guard UI **hanya** untuk UX/Alur Pengguna. Backend API wajib melakukan verifikasi token otentikasi (JWT/Session) pada setiap panggilan API endpoint. Jangan pernah menaruh secrets, konfigurasi privat, atau logika komputasi kritikal di dalam rute Angular chunk.

### Validasi Parameter Open Redirect
* **Ancaman:** Pengguna memanipulasi parameter query `returnUrl` untuk mengarahkan pengguna ke situs phishing: `/login?returnUrl=https://attacker.com`.
* **Hardening:**
  ```typescript
  function sanitizeReturnUrl(url: string | null): string {
    if (!url || !url.startsWith('/') || url.startsWith('//')) {
      return '/dashboard'; // Safe fallback
    }
    return url;
  }
  ```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Lacak performa navigasi dan kegagalan Guard secara global menggunakan router event tracing:

```typescript
// core/telemetry/router-telemetry.service.ts
import { Injectable, inject } from '@angular/core';
import { Router, NavigationStart, NavigationEnd, NavigationCancel, NavigationError } from '@angular/router';

@Injectable({ providedIn: 'root' })
export class RouterTelemetryService {
  private router = inject(Router);
  private navigationStartTime = 0;

  initializeLogging(): void {
    this.router.events.subscribe(event => {
      if (event instanceof NavigationStart) {
        this.navigationStartTime = performance.now();
        console.info(`[Router::Start] ID: ${event.id} -> Navigating to ${event.url}`);
      }

      if (event instanceof NavigationEnd) {
        const duration = (performance.now() - this.navigationStartTime).toFixed(2);
        console.info(`[Router::Success] ID: ${event.id} -> Settled to ${event.urlAfterRedirects} in ${duration}ms`);
      }

      if (event instanceof NavigationCancel) {
        console.warn(`[Router::Canceled] ID: ${event.id} -> Nav to ${event.url} canceled. Reason: ${event.reason}`);
      }

      if (event instanceof NavigationError) {
        console.error(`[Router::Error] ID: ${event.id} -> Failed URL: ${event.url}`, event.error);
      }
    });
  }
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **`loadComponent` vs `loadChildren`:** Gunakan `loadComponent` untuk single standalone page. Gunakan `loadChildren` jika merutekan ke daftar sub-rute terdistribusi (`Routes` array).
* **`canMatch`:** Guard pertahanan awal; menggagalkan routing tanpa mengunduh bundle asset `.js`. Sangat tepat untuk AB testing dan segmentasi peran skala besar.
* **`canActivate`:** Guard sekunder; mengecek izin instansiasi setelah asset chunk terdownload.
* **`canDeactivate`:** Guard proteksi dirty-state; mengonfirmasi penyimpanan perubahan sebelum komponen dihancurkan.
* **`withComponentInputBinding()`:** Praktik modern mengambil parameter rute/query langsung melalui signal/component input decorators tanpa inject `ActivatedRoute`.
* **`UrlTree`:** Format kembalian wajib dari Guard ketika memicu redirection, mencegah state router terkunci.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Kapan `CanMatchFn` guard dieksekusi oleh runtime Angular?
* A. Setelah seluruh lifecycle `ngOnInit` dari komponen selesai dieksekusi.
* B. Setelah file JavaScript dari lazy chunk selesai diunduh oleh browser.
* C. Sebelum file JavaScript lazy chunk diunduh, selama proses evaluasi kesesuaian rute kandidat.
* D. Tepat sebelum event `NavigationEnd` dipancarkan oleh Router.
* *Jawaban yang Benar:* **C**.

### Soal 2
Apa dampak teknis penggunaan `{ path: '', redirectTo: 'dashboard', pathMatch: 'prefix' }` pada root router?
* A. Router bekerja normal tanpa error.
* B. Terjadi infinite redirection loop error karena string kosong selalu cocok dengan konfigurasi match prefix.
* C. Angular compiler akan gagal mengompilasi (compile-time error).
* D. Dashboard chunk akan dimuat dua kali secara bersamaan.
* *Jawaban yang Benar:* **B**.

### Soal 3
Bagaimana functional guard merespons jika ingin menghentikan navigasi saat ini dan memindahkan pengguna ke rute `/login` secara aman?
* A. Mengembalikan nilai `false`.
* B. Memanggil `window.location.href = '/login'`.
* C. Mengembalikan objek `Router.createUrlTree(['/login'])`.
* D. Melempar runtime error `throw new Error('Unauthorized')`.
* *Jawaban yang Benar:* **C**.

### Soal 4
Pada arsitektur router lazy loading, di manakah scope `providers` yang didaftarkan pada rute anak (`loadChildren`) akan dialokasikan?
* A. Pada Root Application Injector secara global.
* B. Pada Environment Injector baru yang terisolasi khusus untuk cabang rute tersebut.
* C. Diabaikan, karena rute tidak mendukung pendaftaran providers.
* D. Pada Window Context Object.
* *Jawaban yang Benar:* **B**.

### Soal 5
Mengapa penggunaan strategi `PreloadAllModules` dianggap antipattern pada aplikasi skala enterprise yang menargetkan pengguna perangkat seluler?
* A. Karena Angular Router tidak memiliki fungsionalitas HTTP client.
* B. Karena memaksa pengunduhan semua asset chunk aplikasi di latar belakang, memboroskan kuota internet pengguna dan membebani parsing JS engine pada koneksi lambat.
* C. Karena merusak kerja dari `canActivate` guards.
* D. Karena memicu race condition pada router outlet state.
* *Jawaban yang Benar:* **B**.

---

## SEKSI 20 — TANTANGAN MANDIRI & PROYEK PRAKTIKUM

### Instruksi Proyek Praktikum
Bangun sistem arsitektur navigasi untuk modul **Supply Chain Execution Portal**:

1. **Rute 1: Public Module (`/auth`)**
   * Berisi halaman login terisolasi.
2. **Rute 2: Logistics Operations (`/logistics`)**
   * Diproteksi oleh `CanMatchFn`. Modul ini hanya bisa diakses dan diunduh jika pengguna memiliki role `LOGISTICS_OPERATOR`.
   * Memiliki form mutasi kontainer di sub-rute `/logistics/dispatch`.
   * Form wajib menerapkan `canDeactivateFormGuard` untuk mencegah user tidak sengaja menutup rute ketika data input telah diubah (`dirty = true`).
3. **Rute 3: Executive Analytics (`/analytics`)**
   * Diproteksi oleh `strictRoleCanActivateGuard` dengan role `VP_OPERATIONS`.
   * Menerapkan kustom `data: { preload: true }` yang memanfaatkan implementasi `NetworkAwarePreloadStrategy`.
4. **Validasi Deliverables:**
   * Pastikan inspect network tab pada Chrome Developer Tools: Saat login sebagai `LOGISTICS_OPERATOR`, chunk bundle JS milik `analytics` tidak boleh diunduh jika terdeteksi koneksi 2G atau mode Save-Data aktif.
   * Tidak ada penggunaan decorator legacy `@NgModule` di seluruh codebase. Semuanya murni Standalone APIs dan Functional Guards.