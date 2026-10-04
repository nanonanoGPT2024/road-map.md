# Kurikulum Enterprise Angular: Bab 05 - Modul 02
## Deep Dive, Implementasi Lanjutan & Arsitektur Routing Terdistribusi Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Principal Engineer / Senior Frontend Architect diharapkan mampu:
- Menguasai arsitektur internal Angular Router: Siklus hidup navigasi, evaluasi pohon rute (`RouterStateTree`), dan serialisasi URL.
- Merancang dan mengimplementasikan arsitektur routing terdistribusi modular berbasis *standalone components* dan *Module Federation* (Micro-frontends).
- Mengimplementasikan proteksi rute mutakhir (*Functional Guards*: `canMatch`, `canActivate`, `canDeactivate`) dengan integrasi *Signal-based reactive state* dan identitas OAuth2/OIDC RBAC (*Role-Based Access Control*).
- Membangun strategi *Custom Network-Aware & Predictive Preloading* untuk mengoptimalkan Core Web Vitals (khususnya LCP dan INP) pada aplikasi skala enterprise.
- Mengintegrasikan browser *View Transitions API* secara native dalam navigasi Angular untuk pengalaman UX setara native mobile.
- Mengatasi *race conditions*, memory leak pada route resolvers, serta desinkronisasi rute pada SSR (*Server-Side Rendering*) dengan Angular Hydration.

---

### 2. Prerequisites
Sebelum mendalami modul ini, peserta harus menguasai:
- **Angular Core Lanjutan**: Angular v16+ (Standalone APIs, `inject()` context, Signals, Control Flow `@if`/`@for`).
- **RxJS Concurrency & Multicasting**: Operator pemetaan (`switchMap`, `exhaustMap`, `concatMap`), `Subject`, `BehaviorSubject`, penanganan error (`catchError`), dan pembersihan memori (`takeUntilDestroyed`).
- **Web Performance & Network Protocol**: HTTP/2 multiplexing, code-splitting chunks, Resource Hints (`prefetch`, `preload`), dan Network Information API.
- **Arsitektur Enterprise**: Konsep dasar Micro-frontends (Module Federation), Single Sign-On (OIDC/PKCE), dan Multi-tenancy.

---

### 3. Concept & Internal Architecture

#### 3.1 Siklus Hidup Internal Angular Router
Navigasi pada Angular Router bukan sekadar manipulasi string URL dan render komponen. Navigasi adalah sebuah *state machine* asinkron yang kompleks.

```
[Trigger Navigasi]
       │
       ▼
1. URL Parsing & Serializer (DefaultUrlSerializer)
       │
       ▼
2. Route Matching (Tree Traversal & canMatch Guard Evaluation)
       │  ├── Evaluasi 'canMatch' (Bisa memblokir chunk download sepenuhnya)
       │  └── Cocokkan URL Segment dengan Route Configuration Tree
       ▼
3. Load Async Chunks (import('./feature/xyz') via dynamic import)
       │
       ▼
4. Guards Activation Lifecycle
       │  ├── canDeactivate (Komponen saat ini)
       │  ├── canActivateChild (Node cabang)
       │  └── canActivate (Node tujuan)
       ▼
5. Resolvers Resolution (ResolveFn paralel via forkJoin / sequential)
       │
       ▼
6. Component Activation & DOM Mutation
       │  ├── RouterOutlet matching
       │  ├── View Transitions API hook (jika diaktifkan)
       │  └── Instansiasi Komponen & Binding Inputs via 'withComponentInputBinding'
       ▼
7. Update History & Router State (RouterStateSnapshot dipublikasikan)
```

1. **URL Serialization & Parsing**: `UrlSerializer` mengubah raw URL menjadi `UrlTree`. Struktur `UrlTree` bersifat hierarkis, mencerminkan segment rute, matrix parameters, query parameters, dan fragments.
2. **Apply Redirects & Segment Matching**: Router melakukan traversal secara *depth-first search* pada pohon konfigurasi. Di sinilah `canMatch` dieksekusi. Jika `canMatch` mengembalikan `false`, router tidak melempar navigasi error, melainkan melanjutkan pencarian rute alternatif pada level yang sama (sangat krusial untuk A/B testing dan migrasi modular).
3. **Guards Chain Execution**: Guards dijalankan dalam observable stream. Kegagalan (false/UrlTree) pada guard awal langsung membatalkan eksekusi guard berikutnya menggunakan operator RxJS internal.
4. **Data Resolving**: Resolver dieksekusi tepat sebelum komponen diinstansiasi. Data di-*resolve* dan disimpan di dalam `ActivatedRouteSnapshot.data`.
5. **View Transition & Activation**: Router mendeaktivasi view lama, membuat `ComponentRef` baru melalui `ViewContainerRef` milik `RouterOutlet`, mengikat data input rute (jika menggunakan `withComponentInputBinding()`), dan menyinkronkan `RouterStateSnapshot`.

#### 3.2 canMatch vs canActivate: Keamanan Level Jaringan
- `canActivate`: Komponen chunk JS **sudah diunduh** melalui jaringan. Guard hanya mencegah komponen dirender ke DOM. Kode biner/JS chunk tetap dapat diinspeksi melalui Developer Tools Network Tab.
- `canMatch`: Dievaluasi **sebelum** chunk lazy-loaded diunduh. Jika guard menolak akses, file JavaScript tidak akan pernah dipanggil melalui jaringan, menjamin keamanan IP (Intellectual Property) dan menghemat bandwidth.

#### 3.3 Micro-Frontend Boundary & Distributed Routing
Pada arsitektur Module Federation atau Monorepo skala besar (Nx), shell application bertindak sebagai router orkestrator tingkat root, sedangkan remote apps mengimplementasikan *encapsulated child routes*. Isolasi ini membutuhkan penanganan khusus agar rute anak tidak bertabrakan (*namespace collision*) dengan shell host.

---

### 4. Why & What

| Fitur / Pola | Paradigma Tradisional | Paradigma Enterprise Modern |
| :--- | :--- | :--- |
| **Pola Guard** | Class-based (`implements CanActivate`) | Functional Guards (`CanActivateFn`, `CanMatchFn`) via `inject()` |
| **Data Extraction** | `ActivatedRoute.params.subscribe()` manual | `withComponentInputBinding()` langsung ke `@Input()` atau Signal inputs |
| **Preloading** | `PreloadAllModules` (pemborosan bandwidth) | Network-Aware Predictive Preloading (Quicklink / Connection-aware) |
| **Proteksi Chunk** | `canActivate` (chunk tetap terunduh) | `canMatch` (chunk diblokir sebelum request HTTP dikirim) |
| **UX Transisi** | CSS Animation wrapper / third-party | Native View Transitions API via `withViewTransitions()` |
| **State Resolution** | Resolver memblokir UI tanpa feedback | Non-blocking streaming state resolvers via RxJS/Signals |

---

### 5. How: Workflow Detail

```
               [Pengguna Mengklik Tautan Rute Dilindungi]
                                   │
                                   ▼
                   +───────────────────────────────+
                   │ Guard: canMatchFn             │
                   │ Verifikasi Sesi & Hak Akses   │
                   +───────────────────────────────+
                                   │
                ┌──────────────────┴──────────────────┐
        [Izin Diberikan]                      [Akses Ditolak]
                │                                     │
                ▼                                     ▼
+───────────────────────────────+     +───────────────────────────────+
│ Download Lazy Chunk JS        │     │ Evaluasi Fallback Route       │
│ import('./admin/routes')      │     │ atau Redirect ke /unauthorized│
+───────────────────────────────+     +───────────────────────────────+
                │
                ▼
+───────────────────────────────+
│ Guard: canActivateFn          │
│ Pengecekan State Runtime Terkini
+───────────────────────────────+
                │
                ▼
+───────────────────────────────+
│ Resolve Data (Async Service)  │
│ Resolving via Signals/RxJS    │
+───────────────────────────────+
                │
                ▼
+───────────────────────────────+
│ Native View Transition Hook   │
│ document.startViewTransition  │
+───────────────────────────────+
                │
                ▼
+───────────────────────────────+
│ Swap Component DOM via Outlet │
│ Inject Route Input Signals    │
+───────────────────────────────+
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Gerbang Masuk Kawasan Industri Berikat
Bayangkan sebuah bandar udara internasional:
- **URL Parser**: Petugas tiket di konter utama yang membaca paspor dan boarding pass Anda untuk menentukan terminal yang dituju.
- **`canMatch` (Pemeriksaan Visa di Kedutaan)**: Anda tidak diperbolehkan naik pesawat sama sekali jika visa tidak valid. Anda tidak akan pernah sampai ke negara tujuan (JavaScript chunk tidak pernah diunduh ke browser pengguna).
- **`canActivate` (Pemeriksaan Imigrasi di Pintu Kedatangan)**: Anda sudah terbang dan tiba di bandara tujuan (chunk sudah diunduh), namun petugas imigrasi memeriksa kembali dokumen Anda. Jika bermasalah, Anda ditahan di ruang tunggu isolasi (komponen tidak dirender, diarahkan ke `/403`).
- **Resolver**: Tim penjemput VIP yang mengambil bagasi Anda dan menyiapkan mobil di lobi sebelum Anda melangkah keluar dari pintu terminal (data siap saat komponen tampil).

```
[PENGGUNA]
   │
   ├── (Request: /ops/finance)
   │
[GERBANG canMatch] ──────(Gagal)──────> [Batal Muat Chunk / Coba Rute Lain]
   │ (Lolos)
   ▼
[UNDUH CHUNK JS (finance.chunk.js)]
   │
[GERBANG canActivate] ──(Gagal)──────> [Redirect ke /login atau /403]
   │ (Lolos)
   ▼
[RESOLVER DATA PIPELINE]
   │ (Data Siap)
   ▼
[VIEW TRANSITIONS ENGINE]
   │
[RENDER KE DOM: <router-outlet>]
```

---

### 7. Simple & Practical Implementation

#### 7.1 Konfigurasi Router Engine Terpusat (Enterprise Setup)
Implementasi modern menggunakan `provideRouter` dengan optimasi performa penuh:

```typescript
// app.config.ts
import { ApplicationConfig } from '@angular/core';
import { 
  provideRouter, 
  withComponentInputBinding, 
  withViewTransitions, 
  withPreloading, 
  withRouterConfig 
} from '@angular/router';
import { APP_ROUTES } from './app.routes';
import { NetworkAwarePreloadingStrategy } from './core/routing/network-aware-preloading.strategy';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(
      APP_ROUTES,
      withComponentInputBinding(),
      withViewTransitions({
        skipInitialTransition: true,
      }),
      withPreloading(NetworkAwarePreloadingStrategy),
      withRouterConfig({
        onSameUrlNavigation: 'reload',
        paramsInheritanceStrategy: 'always'
      })
    )
  ]
};
```

#### 7.2 Custom Network-Aware Preloading Strategy
Hanya melakukan *pre-load* jika jaringan pengguna berada di koneksi cepat (4G/Wi-Fi) dan perangkat tidak sedang dalam mode hemat data (*Save-Data*):

```typescript
// core/routing/network-aware-preloading.strategy.ts
import { Injectable } from '@angular/core';
import { PreloadingStrategy, Route } from '@angular/router';
import { Observable, EMPTY, of } from 'rxjs';

interface NetworkInformation extends EventTarget {
  readonly saveData: boolean;
  readonly effectiveType: 'slow-2g' | '2g' | '3g' | '4g';
}

@Injectable({ providedIn: 'root' })
export class NetworkAwarePreloadingStrategy implements PreloadingStrategy {
  preload(route: Route, load: () => Observable<unknown>): Observable<unknown> {
    // 1. Periksa ketersediaan Network Information API
    const connection = (navigator as unknown as { connection?: NetworkInformation }).connection;

    if (connection) {
      // Jangan preload jika mode Save-Data aktif
      if (connection.saveData) {
        return EMPTY;
      }
      // Batasi preload hanya pada koneksi berkualitas tinggi (4G atau setara)
      if (connection.effectiveType !== '4g') {
        return EMPTY;
      }
    }

    // 2. Evaluasi deklarasi preload kustom pada rute
    if (route.data && route.data['preload'] === true) {
      return load();
    }

    return EMPTY;
  }
}
```

#### 7.3 Functional RBAC Guards (`canMatch` & `canActivateChild`)

```typescript
// core/auth/guards/auth.guard.ts
import { inject } from '@angular/core';
import { CanMatchFn, CanActivateFn, Route, UrlSegment, Router, UrlTree } from '@angular/router';
import { AuthService } from '../auth.service';
import { catchError, map, of } from 'rxjs';

export const rbacMatchGuard = (requiredRole: string): CanMatchFn => {
  return (route: Route, segments: UrlSegment[]): Observable<boolean | UrlTree> => {
    const authService = inject(AuthService);
    const router = inject(Router);

    return authService.currentUser$.pipe(
      map(user => {
        if (!user) {
          // Arahkan ke login dengan parameter kembalian
          const fullPath = segments.map(s => s.path).join('/');
          return router.createUrlTree(['/auth/login'], { queryParams: { returnUrl: fullPath } });
        }

        const hasRole = user.roles.includes(requiredRole);
        if (!hasRole) {
          // Kembalikan false agar router mencari rute alternatif, 
          // atau arahkan langsung ke halaman Forbidden
          return router.createUrlTree(['/forbidden']);
        }

        return true;
      }),
      catchError(() => of(router.createUrlTree(['/auth/login'])))
    );
  };
};

export const unsavedChangesGuard: CanDeactivateFn<HasUnsavedChanges> = (component) => {
  if (component.hasUnsavedChanges()) {
    return window.confirm('Peringatan: Perubahan belum disimpan. Yakin ingin keluar?');
  }
  return true;
};

export interface HasUnsavedChanges {
  hasUnsavedChanges: () => boolean;
}
```

#### 7.4 Definisi Rute Terdistribusi Berbasis Fitur

```typescript
// app.routes.ts
import { Routes } from '@angular/router';
import { rbacMatchGuard } from './core/auth/guards/auth.guard';

export const APP_ROUTES: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'dashboard'
  },
  {
    path: 'dashboard',
    loadComponent: () => import('./features/dashboard/dashboard.component'),
    data: { preload: true }
  },
  {
    path: 'finance',
    canMatch: [rbacMatchGuard('FINANCE_ADMIN')],
    loadChildren: () => import('./features/finance/finance.routes'),
    data: { preload: false } // Fitur berat, hanya diunduh saat match lolos
  },
  {
    path: 'forbidden',
    loadComponent: () => import('./core/errors/forbidden.component')
  },
  {
    path: '**',
    loadComponent: () => import('./core/errors/not-found.component')
  }
];
```

---

### 8. Real-World Case Study: Enterprise Multi-Tenant FinTech Dashboard

#### 8.1 Latar Belakang & Masalah
Sebuah platform multi-tenant core-banking (FinTech) memiliki portal dengan 3 jenis tenant: `RETAIL`, `CORPORATE`, dan `INVESTMENT`. 
- Paket JavaScript aplikasi awal mencapai 18MB bundle size karena seluruh fitur analitik perbankan digabung dalam satu hierarki routing statis.
- Operator non-corporate mampu mengakses struktur internal melalui file manifest yang bocor di network layer.
- Resolver data transaksi mengalami *blocking execution*: perpindahan halaman terhenti hingga 4 detik jika backend API sedang mengalami latensi tinggi, menyebabkan pengguna mengklik tombol berkali-kali (*navigation race condition*).

#### 8.2 Arsitektur Solusi
1. Mengubah struktur rute menjadi *dynamic distributed routes* menggunakan `canMatch` tenant multiplexer.
2. Implementasi **Non-blocking Resolvers** yang memanfaatkan RxJS caching state store dan Angular Signals, sehingga transisi view langsung terjadi sementara skeleton screen diaktifkan.
3. Isolasi chunk secara ketat sehingga build pipeline menghasilkan isolated chunks per subdomain tenant.

#### 8.3 Implementasi Kode Kasus Nyata

```typescript
// features/finance/tenant-resolver.guard.ts
import { inject } from '@angular/core';
import { CanMatchFn, Route, UrlSegment } from '@angular/router';
import { TenantContextService } from '@core/tenant/tenant-context.service';

export const tenantCanMatchGuard = (expectedTenantType: 'CORPORATE' | 'RETAIL'): CanMatchFn => {
  return (route: Route, segments: UrlSegment[]) => {
    const tenantService = inject(TenantContextService);
    return tenantService.currentTenantType() === expectedTenantType;
  };
};
```

```typescript
// features/finance/finance-distributed.routes.ts
import { Routes } from '@angular/router';
import { tenantCanMatchGuard } from './tenant-resolver.guard';

export const FINANCE_ROUTING: Routes = [
  // Branch A: Khusus Corporate (Analitik Kompleks, Multi-Approval)
  {
    path: '',
    canMatch: [tenantCanMatchGuard('CORPORATE')],
    loadChildren: () => import('./corporate/corporate-finance.routes')
  },
  // Branch B: Khusus Retail (Pembayaran Sederhana, E-Wallet Transfer)
  {
    path: '',
    canMatch: [tenantCanMatchGuard('RETAIL')],
    loadChildren: () => import('./retail/retail-finance.routes')
  },
  // Fallback untuk tenant tidak terdefinisi
  {
    path: '',
    loadComponent: () => import('./fallback/unsupported-tenant.component')
  }
];
```

```typescript
// features/finance/corporate/resolvers/portfolio.resolver.ts
import { inject } from '@angular/core';
import { ResolveFn, ActivatedRouteSnapshot } from '@angular/router';
import { CorporatePortfolioService, PortfolioData } from '../services/portfolio.service';
import { catchError, of } from 'rxjs';

export interface ResolvedPortfolioState {
  data: PortfolioData | null;
  error: string | null;
}

export const portfolioResolver: ResolveFn<ResolvedPortfolioState> = (
  route: ActivatedRouteSnapshot
) => {
  const portfolioService = inject(CorporatePortfolioService);
  const accountId = route.paramMap.get('accountId');

  if (!accountId) {
    return of({ data: null, error: 'Missing Account ID' });
  }

  // Menggunakan pattern safe resolution tanpa melempar fatal exception ke Router Lifecycle
  return portfolioService.fetchPortfolioMetrics(accountId).pipe(
    catchError(err => {
      console.error('Resolver failure intercepted:', err);
      return of({ data: null, error: 'Gagal sinkronisasi portofolio. Menampilkan mode offline.' });
    })
  );
};
```

```typescript
// features/finance/corporate/portfolio-detail.component.ts
import { Component, input, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ResolvedPortfolioState } from './resolvers/portfolio.resolver';

@Component({
  standalone: true,
  imports: [CommonModule],
  selector: 'fin-corporate-portfolio-detail',
  template: `
    <section class="portfolio-container" [style.view-transition-name]="'portfolio-view'">
      @if (portfolioResolvedData().error; as errorMsg) {
        <div class="alert alert-warning">{{ errorMsg }}</div>
      }

      @if (portfolioResolvedData().data; as data) {
        <h1>Portofolio: {{ data.accountName }}</h1>
        <p>Valuasi: {{ data.valuation | currency:'IDR':'symbol':'1.2-2' }}</p>
      } @else {
        <div class="skeleton-loader">Memuat metrik portofolio...</div>
      }
    </section>
  `,
  styles: [`
    .portfolio-container {
      contain: layout;
    }
  `]
})
export default class CorporatePortfolioDetailComponent {
  // Input otomatis terikat dari Resolver berkat withComponentInputBinding()
  // Key input harus SAMA DENGAN nama key di konfigurasi route `resolve`
  portfolioResolvedData = input.required<ResolvedPortfolioState>({ alias: 'portfolioData' });
}
```

---

### 9. Trade-offs & Deep Analysis

| Pilihan Arsitektural | Keuntungan (Pros) | Biaya & Kerugian (Cons) | Dampak Produksi |
| :--- | :--- | :--- | :--- |
| **Strict `canMatch` Routing Multiplexing** | Payload awal sangat kecil; chunk code tidak bocor ke browser pihak ketiga yang tidak berhak. | Resolusi URL sedikit lebih lambat karena harus memeriksa *match predicate* di setiap tingkat tree. | Mengurangi Initial Bundle Size hingga ~65% pada kasus FinTech multi-role. |
| **Heavy Resolvers Blocking** | Komponen terjamin menerima data yang valid saat di-render; UI tidak mengalami layout shift (CLS). | Navigasi terasa lambat/macet bagi pengguna; jika API lambat, layar terlihat diam tanpa feedback (Blank State). | Merusak metrik INP (*Interaction to Next Paint*). Tidak disarankan untuk API dengan latensi > 200ms. |
| **Non-blocking / Streaming Resolvers** | Transisi halaman seketika (optimistic UI); Skeleton screen dapat langsung dipicu. | State management komponen menjadi lebih kompleks; harus mengelola status Loading, Error, dan Data secara eksplisit. | UX superior; menaikkan skor Core Web Vitals secara masif. |
| **`withViewTransitions()`** | Animasi perpindahan halaman setara aplikasi native dengan integrasi browser tingkat rendah (GPU-accelerated). | Membutuhkan browser modern (Chromium/Safari baru); potensi visual artifact jika CSS layout containment tidak diatur. | Meningkatkan retensi pengguna melalui *visual delight* kelas enterprise. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Resolver Race Conditions & Memory Leaks
- **Kesalahan Fatal**: Menggunakan observable tanpa penyelesaian (`take(1)` atau `first()`) di dalam resolver custom atau service yang dipanggil router. Router akan menggantung (*hang*) selamanya pada status `NavigationStart`.
- **Solusi**: Pastikan observable yang dialirkan ke Resolver berstatus `finite` (selesai setelah memancarkan 1 item).

```typescript
// SALAH: Subject/Event listener tidak pernah complete -> Router membeku
return myInfiniteSubject$;

// BENAR: Batasi 1 emisi data lalu terminate
return myInfiniteSubject$.pipe(take(1));
```

#### 10.2 Infinite Redirect Loop pada Guard
- **Kesalahan Fatal**: Guard me-redirect pengguna ke route `/unauthorized`, namun rute `/unauthorized` itu sendiri dilindungi oleh guard yang sama secara rekursif.
- **Troubleshooting**: Periksa properti `segments` atau `state.url`.

```typescript
export const safeGuard: CanActivateFn = (route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (!auth.isAuthenticated() && state.url !== '/auth/login') {
    return router.createUrlTree(['/auth/login']);
  }
  return true;
};
```

#### 10.3 SSR Hydration Router Mismatches
- **Gejala**: Halaman berkedip atau merender tampilan 404 sesaat setelah SSR selesai pada production hydration.
- **Penyebab**: Guard membaca `localStorage` atau `window.location` langsung saat server rendering.
- **Solusi**: Gunakan token `PLATFORM_ID` dan periksa `isPlatformBrowser`.

```typescript
import { isPlatformBrowser } from '@angular/common';
import { PLATFORM_ID, inject } from '@angular/core';

export const ssrSafeGuard: CanMatchFn = () => {
  const platformId = inject(PLATFORM_ID);
  if (!isPlatformBrowser(platformId)) {
    return true; // Izinkan render awal SSR, verifikasi ulang di browser jika diperlukan
  }
  // Logika browser di sini...
  return true;
};
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan Functional Guards Eksklusif**: Hindari class-based guards yang sudah deprecated.
- [ ] **Amankan Endpoint JS via `canMatch`**: Rute kritikal/administratif wajib diproteksi menggunakan `canMatch`, bukan semata `canActivate`.
- [ ] **Aktifkan `withComponentInputBinding()`**: Hilangkan injeksi `ActivatedRoute` yang repetitif di dalam komponen leaf.
- [ ] **Terapkan Network-Aware Preloading**: Cegah pemborosan kuota seluler pengguna berkecepatan lambat.
- [ ] **Pisahkan Rute per Domain Konteks**: Hindari deklarasi file `app.routes.ts` raksasa berukuran ribuan baris; delegasikan menggunakan `loadChildren` ke feature libraries.
- [ ] **Terapkan Fallback Route Handlers**: Pastikan terdapat rute wildcard (`**`) dan fallback error boundary yang jelas di setiap level modul.
- [ ] **Sertakan CSS `contain: layout` pada Kontainer View Transition**: Mencegah layout thrashing saat transisi halaman dieksekusi oleh GPU.

---

### 12. Hands-on Practice: Membangun Enterprise Distributed Router Engine

Struktur direktori yang akan dibangun di `hands-on/m02/`:
```text
hands-on/m02/
├── src/
│   ├── app/
│   │   ├── core/
│   │   │   ├── auth/
│   │   │   │   ├── auth.service.ts
│   │   │   │   └── enterprise-auth.guard.ts
│   │   │   └── preloading/
│   │   │       └── network-aware.strategy.ts
│   │   ├── features/
│   │   │   ├── analytics/
│   │   │   │   ├── analytics.component.ts
│   │   │   │   ├── analytics.routes.ts
│   │   │   │   └── resolvers/
│   │   │   │       └── analytics.resolver.ts
│   │   │   └── home/
│   │   │       └── home.component.ts
│   │   ├── app.config.ts
│   │   └── app.routes.ts
│   └── main.ts
├── angular.json
└── tsconfig.json
```

#### Langkah 1: Implementasi State & Auth Service Simulasi
Buat file `src/app/core/auth/auth.service.ts`:
```typescript
import { Injectable, signal } from '@angular/core';

export interface UserSession {
  username: string;
  permissions: string[];
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private session = signal<UserSession | null>({
    username: 'chief-officer',
    permissions: ['VIEW_ANALYTICS', 'EXECUTE_PAYMENT']
  });

  readonly userSession = this.session.asReadonly();

  hasPermission(perm: string): boolean {
    const user = this.session();
    return !!user && user.permissions.includes(perm);
  }

  logout(): void {
    this.session.set(null);
  }
}
```

#### Langkah 2: Buat Enterprise Auth Guard Menggunakan `canMatch`
Buat file `src/app/core/auth/enterprise-auth.guard.ts`:
```typescript
import { inject } from '@angular/core';
import { CanMatchFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

export const requirePermission = (permission: string): CanMatchFn => {
  return () => {
    const authService = inject(AuthService);
    const router = inject(Router);

    if (authService.hasPermission(permission)) {
      return true;
    }

    console.warn(`[Security Alert] Access denied for permission: ${permission}`);
    return router.createUrlTree(['/']);
  };
};
```

#### Langkah 3: Buat Resolver Data Analytics Terproteksi
Buat file `src/app/features/analytics/resolvers/analytics.resolver.ts`:
```typescript
import { ResolveFn } from '@angular/router';
import { of, delay } from 'rxjs';

export interface AnalyticsMetric {
  kpi: string;
  value: number;
}

export const analyticsDataResolver: ResolveFn<AnalyticsMetric[]> = () => {
  // Simulasi network call asinkronus (500ms latency)
  return of([
    { kpi: 'Net Margin Ratio', value: 24.8 },
    { kpi: 'Customer Churn', value: 1.2 }
  ]).pipe(delay(500));
};
```

#### Langkah 4: Buat Komponen Analytics dengan Input Binding
Buat file `src/app/features/analytics/analytics.component.ts`:
```typescript
import { Component, input } from '@angular/core';
import { AnalyticsMetric } from './resolvers/analytics.resolver';

@Component({
  standalone: true,
  selector: 'app-analytics',
  template: `
    <div style="border: 2px solid #0052cc; padding: 1.5rem; border-radius: 8px;">
      <h2>Dashboard Eksekutif Enterprise</h2>
      <ul>
        @for (item of metrics(); track item.kpi) {
          <li><strong>{{ item.kpi }}</strong>: {{ item.value }}%</li>
        }
      </ul>
    </div>
  `
})
export default class AnalyticsComponent {
  // Dipetakan langsung dari resolver 'metrics'
  metrics = input.required<AnalyticsMetric[]>();
}
```

#### Langkah 5: Buat Feature Routes
Buat file `src/app/features/analytics/analytics.routes.ts`:
```typescript
import { Routes } from '@angular/router';
import { analyticsDataResolver } from './resolvers/analytics.resolver';

export const ANALYTICS_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () => import('./analytics.component'),
    resolve: {
      metrics: analyticsDataResolver
    }
  }
];
```

#### Langkah 6: Wiring di `app.routes.ts` & `app.config.ts`
Buat file `src/app/app.routes.ts`:
```typescript
import { Routes } from '@angular/router';
import { requirePermission } from './core/auth/enterprise-auth.guard';

export const APP_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () => import('./features/home/home.component')
  },
  {
    path: 'analytics',
    canMatch: [requirePermission('VIEW_ANALYTICS')],
    loadChildren: () => import('./features/analytics/analytics.routes')
  },
  {
    path: '**',
    redirectTo: ''
  }
];
```

Buat file `src/app/app.config.ts`:
```typescript
import { ApplicationConfig } from '@angular/core';
import { provideRouter, withComponentInputBinding, withViewTransitions } from '@angular/router';
import { APP_ROUTES } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(
      APP_ROUTES,
      withComponentInputBinding(),
      withViewTransitions()
    )
  ]
};
```

---

### 13. Exercises

#### Level Easy
Ubah rute `analytics` di atas agar menambahkan title browser secara dinamis dengan mengimplementasikan properti `title: 'Executive Analytics | Core System'` tanpa membuat service kustom.
- **Kunci Evaluasi**: Pemahaman dasar konfigurasi `Route.title`.

#### Level Medium
Buat sebuah Functional Guard bernama `unsavedFormGuard` (`CanDeactivateFn`) yang mendeteksi perubahan formulir menggunakan Angular Signals. Jika signal `isDirty()` bernilai `true`, tampilkan konfirmasi berbasis dialog native browser sebelum mengizinkan transisi navigasi.
- **Kunci Evaluasi**: Kemampuan mengikat state signal komponen dengan parameter guard `component`.

#### Level Hard
Rancang sebuah `CustomTitleStrategy` yang mewarisi `TitleStrategy`. Engine ini harus membaca metadata rute secara rekursif dari root snapshot hingga leaf snapshot, kemudian menyusun title hierarkis terbalik: `[Leaf Title] | [Parent Title] | [Enterprise Shell]` dan menyinkronkannya dengan Document Title API browser secara reaktif.
- **Kunci Evaluasi**: Manipulasi `RouterStateSnapshot` dan deep traversal pohon konfigurasi.

---

### 14. Challenge: Arsitektur Zero-Downtime Dynamic Micro-Routing
**Konteks Kasus**:
Anda bertindak sebagai Principal Architect untuk aplikasi perbankan berskala internasional dengan lebih dari 20 domain fungsional. Tim DevOps merilis modul JavaScript mikro secara independen di AWS S3 bucket yang terpisah.

**Tantangan**:
1. Buat mekanisme Router custom loader di mana path rute `admin/:subfeature` tidak didefinisikan secara statis di Angular manifest.
2. Saat navigasi terjadi, sebuah service remote registry (`RemoteRegistryService`) harus dipanggil melalui HTTP untuk mengambil manifest URL chunk terbaru (mengatasi cache invalidation).
3. Evaluasi *feature flag* tenant saat runtime menggunakan `canMatch`.
4. Jika chunk remote gagal diunduh akibat gangguan CDN (misalnya HTTP 404/503), terapkan retry policy 3x dengan *exponential backoff*, dan jika tetap gagal, secara mulus redirect ke fallback template *Graceful Offline Component* tanpa memicu error unhandled promise exception pada konsol router pengguna.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic
1. Kapan `canMatch` dieksekusi dibandingkan dengan `canActivate` dalam siklus navigasi?
   - A. Bersamaan dengan `canActivate` setelah chunk diunduh.
   - B. Sebelum lazy chunk JavaScript diunduh melalui network.
   - C. Setelah seluruh resolver selesai berjalan.
   - D. Hanya saat komponen dihancurkan (unmounted).
   *Jawaban & Penjelasan*: **B**. `canMatch` mengevaluasi rute sebelum memicu lazy loader callback, mencegah transfer file chunk bila akses ditolak.

2. Fitur router mana yang memungkinkan parameter URL otomatis terisi ke dalam `@Input()` komponen tanpa menginjeksi `ActivatedRoute`?
   - A. `withDebugTracing()`
   - B. `withDisabledInitialNavigation()`
   - C. `withComponentInputBinding()`
   - D. `withInMemoryScrolling()`
   *Jawaban & Penjelasan*: **C**. `withComponentInputBinding()` memetakan path params, query params, dan resolved data langsung ke signal/standard inputs komponen.

3. Apa return value yang diizinkan pada functional `CanActivateFn` modern?
   - A. Hanya `boolean`.
   - B. `boolean | UrlTree | Observable<boolean | UrlTree> | Promise<boolean | UrlTree>`.
   - C. `string | number`.
   - D. Hanya `Observable<void>`.
   *Jawaban & Penjelasan*: **B**. Guard modern dapat mengembalikan synchronous boolean/UrlTree atau asynchronous stream via Observable atau Promise.

4. Bagaimana cara mengaktifkan View Transitions API native secara global di konfigurasi standalone Angular?
   - A. Menyertakan `BrowserAnimationsModule` di provider.
   - B. Menambahkan `withViewTransitions()` pada argument `provideRouter`.
   - C. Menambahkan meta tag di `index.html`.
   - D. Menjalankan `router.enableAnimations()`.
   *Jawaban & Penjelasan*: **B**. Angular v17+ menyediakan `withViewTransitions()` sebagai integrasi tingkat native dengan Document View Transitions API.

5. Apa dampak konfigurasi `paramsInheritanceStrategy: 'always'`?
   - A. Query parameter otomatis terhapus saat berpindah modul.
   - B. Komponen anak (child routes) mewarisi path params dari parent routes secara transparan.
   - C. Menghentikan pewarisan data resolver.
   - D. Mengubah URL menjadi mode hash-based.
   *Jawaban & Penjelasan*: **B**. Memudahkan akses path parameter parent dari child snapshot tanpa harus melakukan traversal `route.parent.snapshot`.

#### Bagian 2: Intermediate
6. Apa yang terjadi jika sebuah Observable pada Route Resolver tidak memancarkan status `complete()`?
   - A. Router langsung menampilkan rute dengan data default `null`.
   - B. Siklus navigasi terhenti (*hang*) tanpa batas waktu pada tahap data resolving, dan komponen tujuan tidak pernah dimuat.
   - C. Aplikasi melempar error `ResolutionTimeoutException`.
   - D. Komponen dirender tetapi tanpa binding input.
   *Jawaban & Penjelasan*: **B**. Angular router menunggu sinyal complete dari stream resolver sebelum melanjutkan ke tahap aktivasi view.

7. Mengapa penggunaan `canActivate` saja tidak cukup aman untuk menyembunyikan logika source code komersial pada aplikasi multi-tier?
   - A. Karena `canActivate` tidak mendukung async code.
   - B. Karena saat `canActivate` dievaluasi, file `.js` chunk yang berisi komponen dan business logic sudah terlanjur diunduh oleh browser.
   - C. Karena `canActivate` hanya berjalan di sisi server.
   - D. Karena `canActivate` mudah di-bypass dengan mematikan CSS.
   *Jawaban & Penjelasan*: **B**. Network inspection tools dapat mengekstrak string, endpoint API, dan logika kalkulasi dari file chunk yang sudah masuk ke browser cache.

8. Operator RxJS apa yang secara konseptual digunakan oleh Angular Router untuk membatalkan proses navigasi sebelumnya jika ada request navigasi baru yang dipicu oleh pengguna?
   - A. `mergeMap`
   - B. `concatMap`
   - C. `switchMap`
   - D. `exhaustMap`
   *Jawaban & Penjelasan*: **C**. `switchMap` secara otomatis membatalkan (*unsubscribe/cancel*) stream operasi navigasi lama ketika stream navigasi baru dimulai sebelum yang lama selesai.

9. Kapan kita harus mengembalikan `EMPTY` pada strategi kustom `PreloadingStrategy`?
   - A. Saat terjadi runtime error di aplikasi.
   - B. Ketika sebuah modul rute diputuskan untuk tidak di-preload berdasarkan evaluasi kriteria (misal jaringan lambat/data saver).
   - C. Hanya jika user sudah logout.
   - D. Untuk menghapus cache memori browser.
   *Jawaban & Penjelasan*: **B**. Mengembalikan observable `EMPTY` memberi instruksi pada preloading engine untuk mengabaikan modul tersebut dari antrean unduhan di latar belakang.

10. Jika kita mendefinisikan dua rute dengan segmen path yang sama, teknik apa yang memungkinkan Angular untuk memilih salah satu rute berdasarkan kondisi runtime (misal Feature Flag)?
    - A. Menggunakan `canDeactivate` pada kedua rute.
    - B. Menggunakan `canMatch` yang mengembalikan `true` pada rute yang aktif dan `false` pada yang tidak aktif.
    - C. Mengubah `matcher` menjadi null.
    - D. Menggunakan service worker redirect.
    *Jawaban & Penjelasan*: **B**. Saat `canMatch` mengembalikan `false`, router tidak membatalkan seluruh navigasi, melainkan melanjutkan pencarian kecocokan rute berikutnya pada daftar konfigurasi.

#### Bagian 3: Production Scenarios
11. **Skenario Kasus 1**: Pada dashboard perbankan dengan volume transaksi tinggi, pengguna melaporkan bahwa ketika mereka mengklik cepat antara tab "Rekening Giro" dan "Rekening Deposito", terjadi kondisi *race condition* di mana data Giro muncul di dalam layar Deposito. Apa akar masalah arsitekturalnya dan bagaimana mengatasinya secara tuntas?
    - **Solusi Arsitektural**: Masalah terjadi karena fetching data dilakukan secara terpisah di dalam `ngOnInit` komponen menggunakan subscription yang tidak dibatalkan saat URL berubah. Solusi: Gunakan Route Resolvers yang terikat langsung dengan URL, atau manfaatkan `switchMap` dengan input parameter berbasis signal (`toObservable(this.accountId)`), dipadukan dengan operator `takeUntilDestroyed()`.

12. **Skenario Kasus 2**: Sebuah aplikasi E-Commerce berskala enterprise mengalami penurunan drastis skor Core Web Vitals (INP dan LCP) setelah rilis versi standalone router baru. Analisis menunjukkan bahwa router preloading mengunduh 40 chunk JavaScript secara simultan tepat setelah halaman pertama selesai dirender. Tindakan korektif apa yang harus diambil?
    - **Solusi Arsitektural**: Ganti strategi `PreloadAllModules` dengan *Selective Network-Aware Preloading Strategy* yang memanfaatkan Network Information API (`navigator.connection`). Terapkan pembatasan preloading hanya untuk rute prioritas tinggi (diberi flag `data: { preload: true }`) dan batasi concurrency preload dengan menjadwalkan download menggunakan `requestIdleCallback` agar CPU thread utama tidak diblokir saat pengguna sedang berinteraksi.

13. **Skenario Kasus 3**: Di sistem ERP Multi-Tenant, rute admin `/company-settings` harus mengarah ke komponen UI yang berbeda secara radikal antara tenant standar dan tenant premium. Menggunakan percabangan `ngIf` di dalam satu file komponen menyebabkan bundle file membengkak dan pelanggaran prinsip *Single Responsibility*. Bagaimana mendesain rute ini secara terdistribusi dan efisien?
    - **Solusi Arsitektural**: Deklarasikan dua entri rute dengan path yang sama (`company-settings`) di array konfigurasi routes. Pasang `canMatch` guard custom pada masing-masing rute (misalnya `tenantTierGuard('STANDARD')` dan `tenantTierGuard('PREMIUM')`). Arahkan masing-masing ke `loadComponent()` yang independen. Chunk code untuk tenant premium tidak akan pernah diunduh oleh browser pengguna tenant standar.

---

### 16. Summary
- **Internal Router State Machine**: Navigasi Angular adalah alur asinkron kompleks: serialisasi URL -> matching segment -> security gating -> resource fetching -> activation DOM.
- **Keamanan Tingkat Jaringan via `canMatch`**: Melindungi hak cipta intelektual dan payload rahasia dengan memblokir download chunk file JavaScript sebelum sampai ke browser.
- **Produktivitas dengan Modern Standalone APIs**: Menggantikan deklarasi kelas usang dengan `provideRouter`, Functional Guards, dan Input Component Binding (`withComponentInputBinding`) menyederhanakan kode hingga 40%.
- **Optimasi Network-Aware**: Strategi preloading harus cerdas dengan mempertimbangkan kondisi koneksi pengguna untuk menjaga metrik performa web modern (Core Web Vitals).
- **Arsitektur Terdistribusi**: Mengisolasi dependensi fitur besar ke dalam sub-rute independen memungkinkan skalabilitas monorepo raksasa tanpa mengorbankan performa runtime.