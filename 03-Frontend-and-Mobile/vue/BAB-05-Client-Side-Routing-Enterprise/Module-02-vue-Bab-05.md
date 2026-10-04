# BAB 05: Client-Side Routing Enterprise
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, software engineer diharapkan mampu:
- Menguasai arsitektur internal Vue Router 4, mencakup sinkronisasi State Tree, Reactive History Stack, dynamic route matching berbasis radix tree/Trie-like tokenization, serta lifecycles pipeline navigasi.
- Mengimplementasikan sistem otorisasi berlapis berbasis Enterprise Role-Based Access Control (RBAC) dan Attribute-Based Access Control (ABAC) secara asinkron via Navigation Guards.
- Mendesain strategi dynamic route registration (`addRoute`/`removeRoute`) untuk micro-frontends atau arsitektur modular multi-tenant.
- Mengontrol scroll behavior lanjutan pada Single Page Application (SPA) multi-layout, mencakup deferred transition, asynchronous scroll restoration, dan deep linking handling.
- Mengatasi bottleneck performa routing pada aplikasi skala enterprise melalui prefetching prediktif, chunk grouping, dan pembatalan request tertunda via `AbortController`.

---

### 2. Prerequisite
Engineer wajib memiliki pemahaman mendalam pada domain berikut:
- **Core Vue 3 Internals**: Reactivity API (`effectScope`, `shallowRef`, `computed`), Lifecycle Hooks, dan Dynamic Components (`<component :is="...">`, `<KeepAlive>`, `<Suspense>`).
- **Browser Runtime & Web APIs**: History API (`pushState`, `replaceState`, event `popstate`), DOM Navigation Timing API, dan `AbortController`/`AbortSignal`.
- **TypeScript Advanced**: Discriminated Unions, Generics, Declaration Merging, dan Type Narrowing.
- **Modern Bundlers**: Mekanisme code-splitting, dynamic imports (`import()`), dan chunk loading pada Vite/Rollup.

---

### 3. Concept & Internal Architecture
Vue Router 4 bukan sekadar pembungkus (wrapper) dari Browser History API. Router ini merupakan state machine deterministik yang bertindak sebagai *single source of truth* untuk visual state pada level window.

```
+-------------------------------------------------------------------------------+
|                             Vue Router 4 Internals                            |
+-------------------------------------------------------------------------------+
|                                                                               |
|   1. Matched Tokens               2. Matcher Engine                           |
|      [/admin/:tenantId]   ===>       - Trie/Radix Engine Parser               |
|                                      - Rank Scoring Matrix                    |
|                                      - Branch Normalization                   |
|                                                     |                         |
|   3. Transition Guard Pipeline                      v                         |
|      +--------------------------------------------------------------------+   |
|      | Global BeforeResolve -> Matched Component Guards -> In-Component   |   |
|      +--------------------------------------------------------------------+   |
|                                                     |                         |
|   4. Reactive Synchronization                       v                         |
|      +---------------------+      Sync Trigger      +---------------------+   |
|      | currentRoute (ref)  | <====================> | History Driver      |   |
|      | Reactive RouteLocation                       | HTML5 / Memory / Hash|  |
|      +---------------------+                        +---------------------+   |
+-------------------------------------------------------------------------------+
```

#### Radix Tree Tokenization & Route Matcher
Vue Router 4 melakukan kompilasi array routing menjadi struktur data tree datar dengan skor presisi (path ranking). Ketika path didaftarkan, string path diurai menjadi token ekspresi reguler.
- Setiap segmen path diberi skor numerik berdasarkan kekhususan: segmen statis bernilai paling tinggi, diikuti segmen dinamis bertingkat (`:id`), segmen regex kustom, dan segmen wildcard/catch-all (`.*`) dengan nilai paling rendah.
- Proses pencarian tidak memakai pencarian linear $O(N)$ sederhana, melainkan pencocokan ekspresi terkompilasi yang dioptimalkan dengan penelusuran hierarki berbasis skor tertinggi untuk memitigasi ambiguitas routing.

#### Reactive History Bridge
Vue Router 4 menggunakan wrapper reaktif yang mengisolasi Web API History:
- **Router History Driver**: Mengontrol sinkronisasi antara URL browser dan state memory internal. Terdapat 3 implementasi: `createWebHistory` (HTML5 history), `createWebHashHistory` (hash fallback), dan `createMemoryHistory` (SSR/Node.js testing).
- Objek `router.currentRoute` dibungkus menggunakan `shallowRef` di dalam runtime Vue. Ketika navigasi diverifikasi dan commit dieksekusi, nilai `currentRoute` diperbarui satu kali secara atomik. Ini mencegah re-render DOM ganda yang tidak diinginkan pada hierarki view berlapis.

#### Complete Navigation Resolution Pipeline
Setiap trigger transisi (baik via `<RouterLink>`, `router.push()`, maupun tombol navigasi browser) melewati lifecycle deterministik:

```
[Navigation Triggered]
          |
          v
[1. Leave Guards: beforeRouteLeave (komponen aktif yang akan nonaktif)]
          |
          v
[2. Global Guards: router.beforeEach]
          |
          v
[3. Reused Component Guards: beforeRouteUpdate]
          |
          v
[4. Route Config Guards: beforeEnter (pada route definition)]
          |
          v
[5. Resolve Async Route Components (Chunk download)]
          |
          v
[6. In-Component Guards: beforeRouteEnter (belum ada instance 'this')]
          |
          v
[7. Global Guards: router.beforeResolve (Semua hook data/komponen selesai)]
          |
          v
[8. Commit Navigation: URL bar terupdate, router.currentRoute diperbarui]
          |
          v
[9. Global Guards: router.afterEach (Logging, Telemetry, DOM Title)]
          |
          v
[10. DOM Updates & Render via RouterView]
          |
          v
[11. Trigger beforeRouteEnter callbacks (next(vm => ...))]
```

---

### 4. Why & What
- **Why**: Pada aplikasi enterprise monolitik atau multi-tenant, rute tidak bersifat statis. Hak akses ditentukan oleh claims payload JWT, data tenant organisasi, dan feature-flag dinamis. Meload seluruh manifest rute di awal memperlambat Initial Server Response, membocorkan rute internal administratif, dan memicu memory leak jika layout SPA berukuran masif.
- **What**: Diperlukan arsitektur routing berbasis kontrol imperatif dinamis menggunakan `addRoute` secara modular, proteksi navigasi asinkron berlapis (RBAC/ABAC Guarding System), automasi pembatalan thread HTTP via `AbortSignal`, serta scroll restoration adapter yang adaptif terhadap layout dinamis dan virtual scrolling.

---

### 5. How (Workflow Detail)
1. **Dynamic Route Injection Flow**:
   - Bootstrap aplikasi hanya mendaftarkan Public Shell routes (Login, 404, Error).
   - Pengguna melakukan autentikasi; identitas diverifikasi melalui JWT/OIDC identity provider.
   - Guard `beforeEach` mendeteksi sesi aktif dan status registrasi routing (`hasDynamicRoutesRegistered: false`).
   - Guard memanggil Menu/Permissions Service, mengambil manifest hak akses, lalu memetakan endpoint layout modular ke dalam internal format `RouteRecordRaw`.
   - Modul diinjeksikan secara atomik via `router.addRoute(parentName, routeRecord)`.
   - Mengembalikan target navigasi ulang: `return { ...to, replace: true }`. Ini memaksa router menghentikan navigasi saat ini dan memetakan ulang URL pada pohon rute yang baru diinjeksi.

2. **Network Interruption Integration**:
   - Sebelum transisi commit, guard membatalkan token/controller HTTP yang terikat dengan halaman sebelumnya melalui hook `beforeEach` atau Pinia Store teardown.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Keamanan Kereta Cepat
Bayangkan rute aplikasi adalah rel kereta api berkecepatan tinggi:
- **Matcher Engine**: Sistem pensinyalan wesel otomatis yang membaca nomor kereta dan mengarahkan ke peron yang tepat berdasarkan prioritas tertinggi.
- **Navigation Pipeline**: Rangkaian gerbang tiket bertingkat:
  - *beforeRouteLeave*: Petugas memastikan penumpang tidak meninggalkan barang di kursi lama.
  - *beforeEach*: Pemeriksaan validitas paspor dan visa nasional (Autentikasi & RBAC).
  - *beforeEnter*: Pemeriksaan tiket khusus peron/gerbong VIP (Hak akses rute spesifik).
  - *beforeResolve*: Pengecekan barang bawaan saat hendak menaiki kereta.
  - *afterEach*: Pelaporan manifes penumpang ke pusat kontrol setelah kereta berangkat.

#### Diagram Transisi RBAC & State Injection
```
Browser URL Change
       |
       v
+--------------+
| router.match | ===> Path terdaftar?
+--------------+        |
                        +---> [TIDAK] ---> Periksa Dynamic Route Registry
                        |                     |
                        |                     +--> Belum Load? -> Fetch API -> addRoute() -> Re-run
                        |                     +--> Sudah Load? -> Redirect to /404
                        |
                        +---> [YA]
                                |
                                v
                      +-------------------+
                      | Navigation Guards |
                      +-------------------+
                                |
               +----------------+----------------+
               | Is Public?                      | Is Protected?
               v                                 v
          [Allow Next]                 Check Auth Store Valid?
                                                 |
                                       +---------+---------+
                                       | Valid             | Invalid
                                       v                   v
                               RBAC Role Allowed?    Redirect to /login?redirect=...
                                       |
                                +------+------+
                                | Yes         | No
                                v             v
                           [Proceed]     Redirect to /403-forbidden
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Runtime Route Injection & Navigation Signal
```typescript
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  { path: '/', component: () => import('./views/HomeView.vue') },
  { path: '/login', component: () => import('./views/LoginView.vue') },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

let isDynamicRoutesLoaded = false;

router.beforeEach(async (to, from) => {
  const token = localStorage.getItem('auth_token');
  
  // Public Route Access
  if (to.path === '/login') return true;
  if (!token) return { path: '/login', query: { redirect: to.fullPath } };

  // Register routes on reload if authenticated
  if (!isDynamicRoutesLoaded) {
    // Simulasi injection
    router.addRoute({
      path: '/analytics',
      name: 'Analytics',
      component: () => import('./views/AnalyticsView.vue'),
    });
    isDynamicRoutesLoaded = true;
    return { ...to, replace: true }; // Trigger reroute
  }

  return true;
});
```

#### Practical Example: Production Grade Enterprise Router Configuration
Implementasi Typed Metadata, ABAC Evaluation, Asynchronous Dynamic Route Loading, dan AbortController Integration.

##### Step 1: Type Declaration Merging (`src/types/router.d.ts`)
```typescript
import 'vue-router';

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth: boolean;
    permissions?: string[];
    requiredTenantRole?: 'OWNER' | 'ADMIN' | 'MEMBER';
    layout?: 'ConsoleLayout' | 'BlankLayout';
    breadcrumb?: string;
    preserveScroll?: boolean;
  }
}
```

##### Step 2: Global Navigation Controller & Core Engine (`src/router/index.ts`)
```typescript
import {
  createRouter,
  createWebHistory,
  type RouteRecordRaw,
  type RouterScrollBehavior,
} from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useNetworkAbortStore } from '@/stores/networkAbort';

const staticRoutes: RouteRecordRaw[] = [
  {
    path: '/auth/login',
    name: 'Login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { requiresAuth: false, layout: 'BlankLayout' },
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('@/views/error/403View.vue'),
    meta: { requiresAuth: false, layout: 'BlankLayout' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/404View.vue'),
    meta: { requiresAuth: false, layout: 'BlankLayout' },
  },
];

const scrollBehavior: RouterScrollBehavior = (to, from, savedPosition) => {
  if (savedPosition) {
    return savedPosition;
  }
  if (to.hash) {
    return {
      el: to.hash,
      behavior: 'smooth',
      top: 64, // Floating Header Offset
    };
  }
  if (to.meta.preserveScroll) {
    return false;
  }
  return new Promise((resolve) => {
    // Memberikan jeda waktu agar CSS Page Transitions selesai sebelum scroll dilakukan
    setTimeout(() => {
      resolve({ left: 0, top: 0, behavior: 'smooth' });
    }, 250);
  });
};

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: staticRoutes,
  scrollBehavior,
});

// Guard Pipeline: Network Cancellation & ABAC Security Evaluation
router.beforeEach(async (to, from) => {
  // 1. Batalkan semua pending HTTP request dari view sebelumnya
  const abortStore = useNetworkAbortStore();
  abortStore.abortPendingRequests();

  const authStore = useAuthStore();

  // 2. Evaluasi Rute Publik
  if (!to.meta.requiresAuth) {
    return true;
  }

  // 3. Evaluasi Sesi Login
  if (!authStore.isAuthenticated) {
    return {
      path: '/auth/login',
      query: { redirect: to.fullPath },
      replace: true,
    };
  }

  // 4. Injeksi Dynamic Routes jika belum terinisialisasi
  if (!authStore.isRoutesHydrated) {
    try {
      const dynamicRoutes = await authStore.fetchUserRoutesManifest();
      
      dynamicRoutes.forEach((route) => {
        router.addRoute(route);
      });

      authStore.setRoutesHydrated(true);
      // Re-trigger matcher pipeline dengan target awal
      return { ...to, replace: true };
    } catch (error) {
      console.error('Failed to load secure dynamic manifest:', error);
      await authStore.purgeSession();
      return { path: '/auth/login', replace: true };
    }
  }

  // 5. Evaluasi Otorisasi Berbasis Permissions (RBAC/ABAC)
  if (to.meta.permissions && to.meta.permissions.length > 0) {
    const hasPermission = to.meta.permissions.every((perm) =>
      authStore.permissions.includes(perm)
    );

    if (!hasPermission) {
      return { name: 'Forbidden', replace: true };
    }
  }

  // 6. Evaluasi Tenant Scope Role
  if (to.meta.requiredTenantRole) {
    const roleRank: Record<string, number> = { MEMBER: 1, ADMIN: 2, OWNER: 3 };
    const userRole = authStore.tenantRole;

    if (!userRole || roleRank[userRole] < roleRank[to.meta.requiredTenantRole]) {
      return { name: 'Forbidden', replace: true };
    }
  }

  return true;
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Platform B2B SaaS FinTech Multi-Tenant:
- Melayani 100.000+ pengguna concurrent di 50+ domain bank regional.
- Setiap bank mengaktifkan modul berbeda (misal: Bank A menggunakan Modul Core Treasury + Remittance; Bank B hanya menggunakan Modul Multi-Payment).
- Pengguna enterprise memiliki izin kontekstual: Seorang `Operator` hanya dapat mengakses `/remittance` jika nilai transaksi akun berada di bawah batas tertentu (ABAC Policy).

#### Solusi Arsitektur
1. **Dynamic Manifest Micro-Module**:
   - Router Vue di host application tidak memuat kode modul sub-domain sejak awal.
   - Panggilan API `/api/v1/workspaces/manifest` mengembalikan payload skema manifest modul yang diizinkan untuk tenant tersebut.
   - Route Engine mengurai manifest tersebut dan menyusun rute menggunakan dynamic import Vite yang dipisahkan ke dalam sub-folder.
2. **Atomic Route Switching**:
   - Saat pengguna berpindah antar workspace organisasi di dalam SPA tanpa me-refresh halaman:
     - `router.getRoutes()` dibaca.
     - Semua rute milik workspace sebelumnya dihapus melalui `router.removeRoute(routeName)`.
     - Manifest workspace baru dimuat dan diinjeksi via `router.addRoute()`.
3. **HTTP Abort Controller Registry**:
   - Ketika berpindah dari halaman analisis data berbeban tinggi (misal: query transaksi 100k data) ke halaman lain, koneksi Axios/Fetch yang masih terbuka langsung di-abort via `AbortController` global. Hal ini menghemat bandwidth server dan mencegah race condition pada state management.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian | Skala Penerapan Rekomendasi |
| :--- | :--- | :--- | :--- |
| **All-Static Route Bundle Definition** | - Waktu kompilasi cepat.<br>- Analisis dependensi typesafe optimal.<br>- Tidak ada latency saat guard berjalan. | - Ukuran initial bundle membesar.<br>- Struktur rute internal terekspos ke klien.<br>- Tidak mendukung modularitas multi-tenant. | Aplikasi Internal/SaaS Skala Kecil (<50 Rute). |
| **Full Dynamic Server-Driven Routing** | - Bundle awal minimal.<br>- Isolasi keamanan tinggi (klien hanya menerima rute yang diizinkan).<br>- Mendukung load modul dinamis per tenant. | - Menambahkan network round-trip saat bootstrap.<br>- Manajemen state lebih rumit saat halaman di-refresh.<br>- Potensi flashing layar jika hydration tidak ditangani dengan benar. | Enterprise Multi-Tenant Platform & Core Banking Portal. |
| **Aggressive Prefetching (`beforeRouteResolve`)** | - Transisi antar halaman instan bagi pengguna. | - Pemborosan bandwidth pada koneksi data terbatas (3G/4G).<br>- Beban tak terduga pada backend server. | Layanan B2C High Traffic, E-Commerce Katalog. |
| **Cancel HTTP on Route Change** | - Mencegah memory leak dan race condition.<br>- Menghemat resource thread backend API. | - Boilerplate bertambah pada API Client/Store.<br>- Data caching lokal memerlukan manajemen state tambahan. | Aplikasi Data-Intensive & Dashboard Analytics. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Deadlock / Infinite Loop pada Dynamic Navigation
*Gejala*: Browser mengalami hang dan muncul error: `RangeError: Maximum call stack size exceeded` di dalam console.  
*Akar Masalah*: Kode guard memanggil redirect tanpa memeriksa apakah target URL sudah berada di rute tujuan.
```typescript
// SALAH: Memicu infinite loop
router.beforeEach((to) => {
  if (!isAuthenticated) return '/login'; // Terus looping jika to.path sudah '/login'
});

// BENAR: Evaluasi kondisi tujuan secara deterministik
router.beforeEach((to) => {
  if (!isAuthenticated && to.path !== '/login') {
    return { path: '/login', query: { redirect: to.fullPath } };
  }
  if (isAuthenticated && to.path === '/login') {
    return { path: '/dashboard' };
  }
  return true;
});
```

#### 2. Resolusi Asinkron Dynamic Route `addRoute` Menghasilkan Blank Screen (404)
*Gejala*: Setelah memanggil `router.addRoute()`, navigasi langsung menuju wildcard 404 handler atau layar kosong saat halaman di-refresh langsung pada target dinamis.  
*Akar Masalah*: `router.addRoute()` memperbarui state matcher, namun navigasi saat ini sedang berjalan menggunakan matcher pipeline lama.  
*Solusi*: Interupsi navigasi berjalan dan mulai navigasi baru dengan context matcher yang sudah diperbarui:
```typescript
// SALAH
router.addRoute(newRouteRecord);
return true; // Matcher lama gagal menemukan newRouteRecord!

// BENAR
router.addRoute(newRouteRecord);
return { ...to, replace: true }; // Mengabaikan pipeline lama dan memicu pencocokan ulang
```

#### 3. Memory Leak State pada In-Component Route Guards
*Gejala*: Penggunaan memory bertambah drastis setelah perpindahan halaman intensif.  
*Akar Masalah*: Menyimpan referensi DOM atau callback lifecycle pada guard tanpa pembersihan yang tepat saat komponen ditinggalkan.
*Solusi*: Bersihkan semua interval, WebSocket subscriptions, dan pembatalan API pada hook `onBeforeRouteLeave` atau `onUnmounted`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Type-Safe Route Location**: Gunakan augmentasi interface `RouteMeta` untuk semua metadata rute (permissions, layouts, breadcrumbs).
- [ ] **Deterministic Chunk Naming**: Definisikan chunk group eksplisit pada Vite dynamic import (`/* webpackChunkName: "p-finance" */` atau chunking Rollup di `vite.config.ts`) agar file chunk terorganisir dengan rapi.
- [ ] **Centralized Abort Controller**: Hubungkan semua pemanggilan request API klien ke lifecycle router, sehingga request yang sedang berlangsung dapat dibatalkan saat pengguna berpindah halaman.
- [ ] **Sanitized Redirect Queries**: Lakukan validasi URL redirect target setelah proses login berhasil. Cegah serangan Open Redirect Vulnerability dengan memastikan query `redirect` diawali karakter `/` dan bukan host eksternal (`//malicious.com`).
- [ ] **Isolate Memory History pada Automated Testing**: Pastikan testing unit/integration instansiasi router selalu menggunakan `createMemoryHistory()` guna mencegah modifikasi state global browser saat pengujian berjalan paralel.
- [ ] **Scroll Restoration Stability**: Saat menggunakan CSS Transitions antar view, tunda penyesuaian scroll hingga animasi transisi selesai untuk menghindari layout jumping.

---

### 12. Hands-on Practice

Buatlah implementasi Enterprise Routing Engine mini pada direktori `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── src/
    ├── App.vue
    ├── main.ts
    ├── api/
    │   └── routeManifest.ts
    ├── router/
    │   ├── guard.ts
    │   └── index.ts
    ├── stores/
    │   └── abort.ts
    ├── types/
    │   └── router.d.ts
    └── views/
        ├── AnalyticsView.vue
        ├── DashboardView.vue
        ├── ForbiddenView.vue
        └── LoginView.vue
```

#### Step 1: Package Configuration (`hands-on/m02/package.json`)
```json
{
  "name": "enterprise-router-lab",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build"
  },
  "dependencies": {
    "pinia": "^2.1.7",
    "vue": "^3.4.15",
    "vue-router": "^4.2.5"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.3",
    "typescript": "^5.3.3",
    "vite": "^5.0.12",
    "vue-tsc": "^1.8.27"
  }
}
```

#### Step 2: Request Abort Registry Store (`hands-on/m02/src/stores/abort.ts`)
```typescript
import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useAbortRegistry = defineStore('abortRegistry', () => {
  const activeControllers = ref<AbortController[]>([]);

  function getNewSignal(): AbortSignal {
    const controller = new AbortController();
    activeControllers.value.push(controller);
    return controller.signal;
  }

  function abortAll() {
    activeControllers.value.forEach((controller) => {
      controller.abort('Navigation Cancellation Interruption');
    });
    activeControllers.value = [];
  }

  return { getNewSignal, abortAll };
});
```

#### Step 3: Mock Manifest Backend Provider (`hands-on/m02/src/api/routeManifest.ts`)
```typescript
import type { RouteRecordRaw } from 'vue-router';

export interface RouteManifestDTO {
  path: string;
  name: string;
  componentPath: string;
  permissions: string[];
}

export async function fetchUserManifestAPI(): Promise<RouteManifestDTO[]> {
  // Simulasi network I/O
  await new Promise((resolve) => setTimeout(resolve, 300));
  
  return [
    {
      path: '/analytics',
      name: 'DynamicAnalytics',
      componentPath: 'AnalyticsView',
      permissions: ['FINANCE_READ'],
    },
  ];
}
```

#### Step 4: Router Guard Factory (`hands-on/m02/src/router/guard.ts`)
```typescript
import type { Router } from 'vue-router';
import { useAbortRegistry } from '../stores/abort';
import { fetchUserManifestAPI } from '../api/routeManifest';

// Registry pemetaan import komponen
const componentRegistry: Record<string, () => Promise<unknown>> = {
  AnalyticsView: () => import('../views/AnalyticsView.vue'),
};

export function setupNavigationGuards(router: Router) {
  let isManifestHydrated = false;

  router.beforeEach(async (to, from) => {
    // 1. Eksekusi pembatalan API in-flight
    const abortRegistry = useAbortRegistry();
    abortRegistry.abortAll();

    const token = localStorage.getItem('saas_token');

    if (to.meta.requiresAuth === false) {
      return true;
    }

    if (!token) {
      return { path: '/login', query: { redirect: to.fullPath } };
    }

    if (!isManifestHydrated) {
      try {
        const manifest = await fetchUserManifestAPI();
        
        manifest.forEach((item) => {
          router.addRoute({
            path: item.path,
            name: item.name,
            component: componentRegistry[item.componentPath],
            meta: { requiresAuth: true, permissions: item.permissions },
          });
        });

        isManifestHydrated = true;
        return { ...to, replace: true };
      } catch (err) {
        console.error('Hydration failed', err);
        return { path: '/login' };
      }
    }

    return true;
  });
}
```

#### Step 5: Master Router Entrypoint (`hands-on/m02/src/router/index.ts`)
```typescript
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';
import { setupNavigationGuards } from './guard';

const baseRoutes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('../views/ForbiddenView.vue'),
    meta: { requiresAuth: false },
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes: baseRoutes,
});

setupNavigationGuards(router);
```

#### Step 6: Testing Setup
1. Jalankan `npm install` kemudian `npm run dev`.
2. Akses `http://localhost:5173/`. Sistem otomatis me-redirect ke `/login`.
3. Buka Console DevTools, set token manual: `localStorage.setItem('saas_token', 'enterprise_token_123')`.
4. Navigasi manual menuju URL `/analytics`. Amati network tab: guard akan mengunduh manifest, memetakan rute dinamis, melakukan dynamic import untuk `AnalyticsView.vue`, dan menampilkan UI tanpa me-reload aplikasi.

---

### 13. Exercise

#### Level Easy
Ubah konfigurasi Router Scroll Behavior agar ketika pengguna bernavigasi menggunakan tombol Forward/Backward browser, scroll position kembali persis pada pixel sebelumnya (`savedPosition`). Jika bukan back/forward, arahkan layout ke koordinat paling atas (`top: 0, left: 0`).

#### Level Medium
Buat sebuah In-Component Guard (`onBeforeRouteLeave`) pada form pembayaran. Tampilkan konfirmasi native (`window.confirm`) jika form dalam status kotor/berisi input teks yang belum disimpan (`dirty`). Batalkan navigasi jika pengguna menolak meninggalkan halaman.

#### Level Hard
Rancang arsitektur RBAC + ABAC Policy Engine di dalam `router.beforeEach`.
- **Kondisi ABAC**: Pengguna dengan role `CASHIER` diperbolehkan masuk ke rute `/refund`, HANYA JIKA property jam lokal berada di antara rentang operational shift time (`08:00 - 17:00`) dan property tenant IP berada pada list allowed enterprise subnet. Jika melanggar, redirect ke `/403` dengan query context alasan penolakan.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Frontend Engineer pada platform SaaS Multitenant. Pengguna dapat berganti workspace tenant (misal: dari Tenant "Acme Corp" ke "Globex Corp") melalui menu dropdown di navigation bar, tanpa me-reload browser (zero full page reload).
- Tenant "Acme Corp" memiliki plugin: `['INVOICING', 'HRIS']`.
- Tenant "Globex Corp" memiliki plugin: `['INVOICING', 'LOGISTICS']`. Rute untuk modul `HRIS` sama sekali tidak boleh dapat diakses oleh user saat berada di "Globex Corp".

**Tantangan**:
Rancang arsitektur stateful routing lifecycle manager yang:
1. Mampu mencabut (*unmount* & *deregister*) seluruh rute milik plugin workspace aktif sebelumnya tanpa menyisakan jejak di internal router match tree.
2. Memuat dan mendaftarkan manifest plugin workspace tujuan secara dinamis.
3. Menangani situasi fallback gracefully jika rute yang saat ini sedang aktif ternyata tidak tersedia pada workspace tujuan yang baru.
4. Pastikan tidak ada race condition pada network calls yang memuat manifest antar workspace saat pergantian tenant dilakukan secara beruntun dengan cepat.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level (5 Soal)
1. Kapan lifecycle guard `beforeResolve` dipanggil dalam urutan eksekusi navigasi Vue Router?
   - a. Sebelum `beforeEach` dan sebelum komponen resolve.
   - b. Setelah seluruh guard komponen selesai dan seluruh async route components selesai di-resolve, tepat sebelum commit navigasi.
   - c. Tepat setelah URL browser terupdate dan trigger `afterEach`.
   - d. Saat komponen DOM dimounting ke layar.
2. Apa fungsi parameter ketiga `savedPosition` pada implementasi `scrollBehavior`?
   - a. Menentukan animasi easing CSS.
   - b. Mengembalikan posisi koordinat scroll sebelumnya hanya ketika transisi dipicu aksi browser popstate (Back/Forward).
   - c. Menghitung tinggi elemen virtual scrolling.
   - d. Menghentikan default scroll browser secara permanen.
3. Apa kegunaan utama method `router.removeRoute(name)`?
   - a. Menghapus history navigasi dari cache browser.
   - b. Menghapus konfigurasi rute aktif berdasarkan nama uniknya untuk memproteksi atau mengisolasi hak akses runtime.
   - c. Menghentikan rendering DOM RouterView secara paksa.
   - d. Menghapus parameter query dan hash dari URL.
4. Mengapa hook `beforeRouteEnter` tidak dapat mengakses variabel konteks `this` komponen secara langsung?
   - a. Karena hook tersebut dideklarasikan sebagai arrow function secara internal.
   - b. Karena saat hook tersebut dieksekusi, komponen target navigasi belum selesai dibuat/di-instansiasi.
   - c. Karena `this` telah di-deprecated pada Vue 3.
   - d. Karena guard berjalan di Web Worker thread.
5. Bagaimana cara yang benar untuk mendefinisikan layout per-route menggunakan Vue Router dan TypeScript?
   - a. Membuat instance router ganda per layout.
   - b. Memasukkan layout identifier di dalam objek property `meta` dan memanfaatkan declaration merging interface `RouteMeta`.
   - c. Menuliskannya di query parameters URL.
   - d. Melakukan replace instance App secara paksa di guard `afterEach`.

#### Intermediate Level (5 Soal)
6. Jika Anda memanggil `router.addRoute()` di dalam guard `router.beforeEach`, mengapa return value berupa `return { ...to, replace: true }` sangat disarankan dibandingkan `return true`?
   - a. Agar riwayat navigasi browser tersimpan dua kali.
   - b. Untuk memaksa routing engine menghentikan transisi saat ini dan menjalankan ulang matcher engine dengan tabel rute yang baru diinjeksi.
   - c. Menghindari garbage collection pada browser runtime.
   - d. Tidak berpengaruh, keduanya bekerja dengan cara yang sama.
7. Mengapa `router.currentRoute` menggunakan `shallowRef` dan bukan `ref` biasa secara internal pada Vue Router 4?
   - a. Untuk mencegah reaktivitas berjalan.
   - b. Mengurangi overhead tracking reaktivitas deep-nested pada URL objects besar dan menjaga pembaruan state router berjalan secara atomik saat commit navigasi.
   - c. Merupakan batasan implementasi TypeScript compiler.
   - d. Agar history stack dapat dimodifikasi secara direct mutation.
8. Apa yang terjadi jika transisi route dibatalkan dengan return `false` di dalam `beforeEach` sementara terdapat pending asynchronous HTTP calls di halaman sebelumnya?
   - a. HTTP call secara otomatis dihentikan oleh browser network process.
   - b. URL dikembalikan ke URL asal dan HTTP calls tetap berjalan di background kecuali dibatalkan manual via `AbortController`.
   - c. Terjadi runtime error `DOMException: Transaction Aborted`.
   - d. Browser me-reload seluruh halaman secara otomatis.
9. Manakah pernyataan yang BENAR mengenai sistem penilaian skor (path ranking scoring) pada Route Matcher Vue Router 4?
   - a. Rute yang didaftarkan paling pertama selalu memiliki prioritas pencocokan paling tinggi.
   - b. Segmen rute statis bernilai skor lebih tinggi daripada segmen dinamis parameter (`:id`) dan regex catch-all (`.*`).
   - c. Menggunakan regex linear tanpa skor presisi token.
   - d. Seluruh dynamic segment memiliki prioritas yang setara dengan static segment.
10. Pada skenario penggunaan `<RouterView v-slot="{ Component }">` yang dibungkus dengan `<KeepAlive>` dan `<Transition>`, bagaimana urutan hierarki komponen wrapper yang tepat dari luar ke dalam?
    - a. `RouterView` -> `Transition` -> `KeepAlive` -> `component :is`.
    - b. `Transition` -> `RouterView` -> `KeepAlive` -> `component :is`.
    - c. `KeepAlive` -> `RouterView` -> `Transition` -> `component :is`.
    - d. `RouterView` -> `component :is` -> `Transition` -> `KeepAlive`.

#### Production Scenarios (3 Soal)
11. Sebuah aplikasi sistem lelang enterprise mendadak mengalami kebocoran data (state leak). Ketika Operator A berganti rute secara cepat dari Dashboard Detail Akun Investor X ke Investor Y, data ringkasan portofolio milik Investor X sesekali muncul selama beberapa milidetik pada layar Investor Y. Apa akar arsitektural masalah routing ini dan bagaimana solusinya?
    - a. Vue Router mengalami korupsi data internal. Solusinya adalah mematikan history mode dan beralih ke hash mode.
    - b. Terjadi async race condition karena komponen view di-reuse (`beforeRouteUpdate`) dan network call dari route pertama selesai terlambat setelah route kedua aktif. Solusinya: implementasikan request cancellation via `AbortController` yang dipicu pada route guard/unmount, atau gunakan dynamic watch query key.
    - c. Bug internal engine browser Chromium. Solusinya: force hard-reload via `window.location.reload()`.
    - d. `shallowRef` pada RouterView tidak me-refresh DOM tree. Solusinya: hapus parameter route.
12. Anda menemukan bahwa halaman checkout e-commerce lambat merespons klik link rute berikutnya selama 1.5 detik. Setelah inspeksi, ditemukan ada sebuah `beforeRouteLeave` guard yang menunggu operasi sinkronisasi log analytics batching via `await fetch(...)`. Pendekatan arsitektural mana yang paling tepat untuk mengatasi latensi ini tanpa kehilangan data telemetri?
    - a. Mengubah navigasi menjadi synchronous navigation tanpa guard.
    - b. Pindahkan log analytics ke lifecycle `afterEach` atau gunakan browser Web API `navigator.sendBeacon()`, sehingga navigasi UI tidak terblokir oleh network payload I/O.
    - c. Meningkatkan spesifikasi hardware server backend analytics.
    - d. Menggunakan `setTimeout` 10 detik di dalam guard.
13. Dalam arsitektur micro-frontend berbasis dynamic module federation, rute didaftarkan menggunakan `router.addRoute()`. Terjadi bug: ketika user me-refresh browser pada URL modul terisolasi `/finance/general-ledger`, aplikasi selalu menampilkan layout 404 Not Found. Padahal navigasi via tombol di dalam aplikasi berjalan normal. Mengapa hal ini terjadi dan bagaimana solusinya?
    - a. Refresh memicu request ke web server yang salah konfigurasi HTTP 404 rewrite.
    - b. State in-memory router ter-reset pada hard-refresh, sementara dynamic route registration baru dipanggil oleh komponen UI yang belum dimount. Solusinya: pindahkan pengecekan registrasi manifest rute ke dalam `router.beforeEach` sebelum target navigasi di-resolve oleh router matcher.
    - c. Dynamic import tidak didukung oleh browser saat menggunakan hard reload.
    - d. Modul Micro-Frontend harus selalu menggunakan `createMemoryHistory`.

---

### Kunci Jawaban Quiz

#### Basic
1. **b** - `beforeResolve` dieksekusi tepat setelah seluruh guard komponen dan chunk async components berhasil dimuat, menjadi kesempatan evaluasi terakhir sebelum URL ditulis.
2. **b** - Parameter `savedPosition` hanya terisi objek koordinat pixel saat pemicu transisi adalah event `popstate` native (tombol back/forward browser).
3. **b** - Menghapus referensi rute secara dinamis berdasarkan identifier namanya, krusial untuk isolasi hak akses saat tenant/sesi pengguna berganti.
4. **b** - Guard `beforeRouteEnter` berjalan sebelum izin navigasi disahkan, sehingga instance komponen Vue belum diinstansiasi ke memori.
5. **b** - Pendekatan enterprise standar menggunakan interface augmentation pada `RouteMeta` agar metadata rute strictly-typed dan mudah dievaluasi pada layout engine wrapper.

#### Intermediate
6. **b** - Return `{ ...to, replace: true }` menginterupsi navigasi saat ini dan mengeksekusi navigasi baru menggunakan daftar routing table yang telah diperbarui dengan route hasil injeksi.
7. **b** - `shallowRef` mencegah Vue melakukan deep reactivity observation pada objek rute yang kompleks, menjaga performa dan memicu re-render view secara terisolasi dan atomik.
8. **b** - Browser mengembalikan URL state ke titik awal, namun HTTP request yang sudah terlanjur berjalan di background network thread akan terus berjalan kecuali diterminasi eksplisit oleh signal `AbortController`.
9. **b** - Matcher engine memberi skor presisi numerik: segmen statis memiliki bobot ranking tertinggi dibanding dynamic parameter maupun catch-all regex.
10. **a** - Struktur hierarki yang valid secara arsitektural pada Vue 3 adalah `<RouterView>` membungkus `<Transition>`, lalu membungkus `<KeepAlive>`, dan diakhiri dengan `<component :is="...">`.

#### Production Scenarios
11. **b** - Merupakan classic race condition akibat persistensi komponen yang digunakan kembali tanpa pembatalan request lama. Solusinya adalah membatalkan thread network aktif menggunakan `AbortController` terintegrasi dengan lifecycle routing.
12. **b** - `navigator.sendBeacon()` didesain khusus oleh platform web browser untuk mengirim payload telemetri latar belakang secara asynchronous tanpa menunda atau memblokir transisi navigasi halaman pengguna.
13. **b** - Pada hard reload, state JavaScript kembali kosong. Pendaftaran rute dinamis harus diletakkan di fase awal Navigation Guard (`router.beforeEach`) agar tree rute baru tersedia sebelum URL dievaluasi oleh matcher engine.

---

### 16. Summary
Arsitektur routing pada enterprise Single Page Application bukan sekadar mencocokkan string URL, melainkan orkestrator state navigasi terdistribusi. Implementasi modern menuntut decoupling antara core routing shell dan manifest dinamis modular (Dynamic Route Injection). 

Dengan menguasai alur transisi pipeline (Navigation Lifecycle Phase), kontrol otorisasi tingkat lanjut (RBAC/ABAC guards), koordinasi thread network (Cancellation via `AbortController`), serta manajemen presisi memori DOM (Scroll Restoration dan Cleanup), arsitek frontend dapat menyajikan platform SPA yang aman, berperforma tinggi, dan minim memory leak di lingkungan produksi skala besar.