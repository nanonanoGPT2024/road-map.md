# Modul Pembelajaran Enterprise Architecture: Vue.js

---

## SEKSI 01 — IDENTITAS MODUL
* **Kategori**: 03-Frontend-and-Mobile
* **Kurikulum**: Vue.js Core & Scaled Ecosystem
* **Bab**: 05 — Routing, State Flow, & Edge Delivery
* **Modul**: 01 — Client-Side Routing Enterprise (Vue Router 4)
* **Tingkat Kemahiran**: Advanced / Staff Engineer
* **Prasyarat**: Vue 3 Core (Reactivity Engine, Composition API, Suspense), TypeScript 5.x Deep Fundamentals, Web Performance Metrics (Core Web Vitals), Browser Navigation Lifecycle Specifications (HTML5 History API vs. RFC 3986).

---

## SEKSI 02 — LEARNING OBJECTIVES
Pada akhir modul ini, Anda dituntut untuk:
1. Menganalisis dan merekayasa ulang alur internal *state transition*, mekanisme *route matching*, dan *lifecycle hook pipelines* pada Vue Router 4.
2. Membangun sistem perutean terdesentralisasi (*Decentralized/Dynamic Route Registration*) yang memfasilitasi arsitektur micro-frontend dan pemuatan modul termutakhir (*lazy-loading with deterministic prefetching*).
3. Mengonfigurasi *Navigation Guards* enterprise yang menangani asinkronisitas, otorisasi berbasis hak akses peran (*Role-Based Access Control* / RBAC), pembatalan balapan jaringan (*race condition cancellation*), serta manajemen memori cache state.
4. Menerapkan skema optimasi performa *Sub-Second Navigation* dengan mengeliminasi *waterfall dynamic import*, mengatur rute berbasis chunk hash, dan membatasi ukuran heap JavaScript.
5. Membangun strategi mitigasi keamanan terhadap celah eksploitasi URL: *Open Redirects*, *State Mutation Injection*, *History Manipulation*, dan penanganan sanitasi rute dinamis berbasis TypeScript end-to-end.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma
Dalam sistem enterprise skala besar, router bukan sekadar mekanisme pergantian tampilan DOM (*view switcher*). Router adalah **Finite State Machine (FSM)** sentral yang mengontrol state deterministik dari seluruh antarmuka aplikasi. URL adalah *Single Source of Truth* eksternal yang dipertukarkan antara browser, server, dan memori klien.

```
+-------------------------------------------------------------------------------+
| TRADITIONAL SPA PERSPECTIVE (Fragile)                                         |
| User Click -> Change URL -> Force Component Mount -> Fetch Inside onMounted   |
| (Result: Loading Cascades, Blank Screen Flash, Memory Leaks)                  |
+-------------------------------------------------------------------------------+
                                      VS
+-------------------------------------------------------------------------------+
| ENTERPRISE FSM ROUTER ENGINE (Deterministic)                                  |
| Navigation Trigger                                                            |
|   │                                                                           |
|   ▼                                                                           |
| Resolution Loop ──► Auth/Permissions Check ──► Parallel Chunk/Data Prefetch   |
|                                                      │                        |
|   ◄──────────────────────────────────────────────────┘                        |
|   ▼                                                                           |
| State Atomic Commit ──► View Morph / Transition                               |
| (Result: Instant UI, Zero Flash, Predictable Garbage Collection)              |
+-------------------------------------------------------------------------------+
```

Setiap transisi navigasi merupakan *asynchronous transaction*. Sama seperti transaksi database, jika satu fase dalam pipa (*pipeline*) navigasi gagal—baik karena otentikasi kedaluwarsa, kegagalan pemuatan chunk jaringan (*network chunk failure*), atau pembatalan sinyal (*aborted by newer navigation*)—seluruh transaksi harus dibatalkan secara atomik tanpa merusak state antarmuka yang ada saat itu.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Mekanisme internal Vue Router 4 memproses transisi melalui pipa interseptor yang kaku. Diagram berikut memetakan perjalanan request dari resolusi URL hingga komponen berhasil dimuat ke dalam pohon DOM.

```
[ Inisiasi Navigasi: router.push() / PopStateEvent ]
                         │
                         ▼
             [ Normalisasi Target TargetRoute ]
                         │
                         ▼
      < Adakah Navigasi Tertunda/Aktif Lain? > 
     ┌───────────────────┴───────────────────┐
     │ Ya                                    │ Tidak
     ▼                                       │
[ Batalkan Navigasi Sebelumnya (AbortError) ] │
     │                                       │
     └───────────────────┬───────────────────┘
                         ▼
        [ Ekstraksi Route Records: Matched[] ]
   (Hitung perbedaan komponen: Deactivated vs Activated)
                         │
                         ▼
         [ 1. beforeEach Global Guards ] ──────────(Return false/Redirect?)──► [ Batal / Redirect ]
                         │                                                             ▲
                         ▼                                                             │
         [ 2. beforeRouteLeave (In-Component) ] ───(Return false/Redirect?)────────────┤
                         │                                                             │
                         ▼                                                             │
         [ 3. beforeResolve / beforeEnter Guards ] (Per-route) ────────────────────────┤
                         │                                                             │
                         ▼                                                             │
        [ 4. Dynamic Chunk Resolution & Fetch ] ───(Chunk Load Error?)─────────────────┼──► [ Trigger Error Handler ]
                         │                                                             │
                         ▼                                                             │
       [ 5. beforeRouteUpdate (In-Component) ] ────(Return false/Redirect?)────────────┘
                         │
                         ▼
         [ 6. beforeRouteEnter (In-Component) ]
       (Catatan: Instans komponen BELUM tercipta)
                         │
                         ▼
       === ATOMIC NAVIGATION COMMIT POINT ===
 (URL History diupdate, currentRoute.value diubah)
                         │
                         ▼
         [ 7. afterEach Global Hooks ]
   (Metrik Telemetri, Page Title, Scroll Reset)
                         │
                         ▼
       [ DOM Transition & Mount Component ]
                         │
                         ▼
    [ Eksekusi Callback next() from beforeRouteEnter ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Route Normalization & Matcher Engine
Router menginisialisasi `RouteMatcher` internal yang mengonversi pohon definisi rute rekursif menjadi daftar flat tokenized records:
* Pola URL dipecah menggunakan *parser regex* internal berbasis path-to-regexp parser.
* Penilaian rute (*Score Sorting Algorithm*): Berbeda dengan Vue Router 3 yang mengandalkan urutan deklarasi, Vue Router 4 menerapkan skema skor presisi. Pola rute statis (skor tertinggi) dievaluasi lebih dulu dibanding rute dinamis bertingkat (*dynamic segment*), yang kemudian mendahului segmen *catch-all/wildcard* (`/:pathMatch(.*)*`).

### 2. State Resolution: History Implementation Internals
Vue Router 4 mengabstraksi navigasi browser melalui antarmuka `RouterHistory`:
* `createWebHistory()` membungkus `window.history.pushState` dan `window.history.replaceState`. Router mendaftarkan listener tunggal pada event `popstate`. Setiap *push* menyematkan `history.state` buatan router untuk melacak *scroll positions* dan penanda navigasi internal (*forward/backward tracking index*).
* `createMemoryHistory()` mengabaikan browser DOM secara total, menyimpan stack navigasi murni di dalam array internal JavaScript. Esensial untuk Server-Side Rendering (SSR) guna mencegah *cross-request state pollution* dan isolasi testing Vitest.

### 3. ShallowRef Reactive Bridge
State rute aktif disimpan sebagai `shallowRef<RouteLocationNormalizedLoaded>`. Vue Router secara sengaja **tidak** menggunakan `ref` standar yang reaktif secara mendalam (*deep reactive*). Mengapa? Komponen rute, parameter, query, dan metadata adalah objek imutabel (*immutable objects*) pada setiap navigasi. Menggunakan `shallowRef` menghemat ribuan operasi reaktivitas Proxy overhead pada URL yang memuat query kompleks.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Asynchronous Navigation Pipeline Execution
Secara arsitektural, setiap *guard* dieksekusi secara sekuensial melalui fungsi rantai janji (*promise chaining engine*). Jika Anda mendaftarkan 5 buah `beforeEach` guards, router tidak mengeksekusinya secara paralel melalui `Promise.all`. Router menggunakan pola *serial async reducer*:

$$\text{Pipeline} = \text{Guard}_n \circ \dots \circ \text{Guard}_2 \circ \text{Guard}_1$$

Jika $\text{Guard}_x$ mengembalikan nilai `false`, melempar `Error`, atau mengembalikan rute pengalihan (`RouteLocationRaw`), eksekusi $\text{Guard}_{x+1}$ akan langsung diputus (*short-circuited*).

### Microtask Race Conditions & Abort Controller
Masalah umum enterprise SPA: Pengguna mengklik rute A, jaringan mengalami latensi 400ms. Pada milidetik ke-150, pengguna mengklik rute B yang kembali dalam 50ms.
Jika sistem tidak memiliki pembatalan deterministik, rute A dapat menyelesaikan eksekusi setelah rute B ter-render, menyebabkan *race condition* di mana tampilan UI menampilkan rute B, tetapi data dan lifecycle didominasi oleh rute A.
Vue Router 4 menangani ini dengan menyematkan token kenaikan bertahap internal (`navigationId`). Jika `navigationId` yang kembali tidak identik dengan `currentNavigationId` terkini, hasil resolusi dibuang dan menghasilkan objek error dengan tipe:
`NavigationFailureType.cancelled`.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Implementasi konfigurasi dasar router dengan *Strict Type Safety* dan penanganan asinkronisitas:

```typescript
// src/router/index.ts
import { 
  createRouter, 
  createWebHistory, 
  type RouteRecordRaw,
  type NavigationGuardNext,
  type RouteLocationNormalized
} from 'vue-router';

// 1. Deklarasi Rute Terstruktur
const routes: ReadonlyArray<RouteRecordRaw> = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: {
      requiresAuth: true,
      roles: ['ADMIN', 'OPERATOR'],
    },
  },
  {
    path: '/identity/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: {
      guestOnly: true,
    },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
  },
];

// 2. Instansiasi Router
export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    }
    if (to.hash) {
      return { el: to.hash, behavior: 'smooth' };
    }
    return { top: 0 };
  },
});

// 3. Pipeline Interseptor Global
router.beforeEach(
  async (
    to: RouteLocationNormalized,
    from: RouteLocationNormalized
  ): Promise<boolean | string | { name: string }> => {
    // Simulasi Service Token (Pada Enterprise: Gunakan Secure Token Store)
    const token = localStorage.getItem('access_token');
    
    if (to.meta.requiresAuth && !token) {
      return { name: 'Login' };
    }

    if (to.meta.guestOnly && token) {
      return { name: 'Dashboard' };
    }

    return true;
  }
);
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 11**: `ReadonlyArray<RouteRecordRaw>` — Mengunci array konfigurasi secara statis menggunakan TypeScript compiler untuk mencegah manipulasi array di runtime tanpa melalui API resmi router.
* **Baris 15**: `component: () => import('@/views/DashboardView.vue')` — Pemisahan bundle (*Dynamic Code Splitting*). Vite/Webpack memisahkan file ini menjadi chunk JavaScript terisolasi yang hanya diunduh ketika rute aktif.
* **Baris 16–19**: `meta: { requiresAuth: true, roles: [...] }` — Pemanfaatan `RouteMeta` interface untuk menginjeksi metadata kustom yang akan dibaca oleh *Navigation Guards*.
* **Baris 29**: `path: '/:pathMatch(.*)*'` — Parameter *catch-all regex*. Tanda kurung mendefinisikan regex penangkap, dan tanda bintang (`*`) menandai parameter dapat berulang, menangkap URL hirarkis seperti `/foo/bar/baz` yang tidak cocok dengan rute lain.
* **Baris 38–46**: `scrollBehavior(to, from, savedPosition)` — Logika restorasi posisi gulir native. Menjamin bila pengguna menggunakan tombol back/forward browser, koordinat scroll dikembalikan ke titik simpanan `savedPosition`.
* **Baris 51–64**: `router.beforeEach(async (to, from) => ...)` — Tidak lagi menggunakan argumen `next()`. Vue Router 4 mengadopsi sintaksis modern berbasis Promise return values. Mengembalikan `true` menyetujui navigasi, `false` membatalkannya, dan rute objek memicu *redirection loop safe*.

---

## SEKSI 09 — STUDI KASUS NYATA (Enterprise ERP / Banking)

### Konteks Skenario
Aplikasi Core Banking memiliki 15 domain sub-sistem (Treasury, Ledger, AML/CFT, Loans, Audit). 
Tantangan Teknis:
1. Bundle monolithic mencapai 18MB jika seluruh rute didaftarkan di muka (*upfront*).
2. Setiap pengguna memiliki konfigurasi hak akses granular (ACL) yang divalidasi ke server. Menu dan rute yang tidak diizinkan tidak boleh terdaftar di runtime router guna memitigasi *source code sniffing*.
3. Akses token memiliki waktu kedaluwarsa singkat (5 menit) dengan mekanisme *silent refresh* yang harus terintegrasi tanpa memutus pipeline navigasi.

### Arsitektur Solusi
Membangun **Dynamic Hierarchical RBAC Router Manager**. Rute terdaftar secara kosong pada awal *bootstrap*. Navigasi guard pertama mencegat alur, mengeksekusi sesi pengguna, memuat manifest rute yang diizinkan dari backend, memanggil `router.addRoute()` secara dinamis, lalu melakukan *idempotent retry navigation*.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi skala industri untuk sistem perutean dinamis berbasis izin dan token refresh race-condition safe:

### 1. Definisi Tipe Meta Aman (Type Augmentation)
```typescript
// src/types/router.d.ts
import 'vue-router';

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean;
    permissions?: string[];
    layout?: 'AppLayout' | 'AuthLayout' | 'BlankLayout';
    breadcrumb?: string;
  }
}
```

### 2. Guard State & Dynamic Registration Engine
```typescript
// src/router/guard-manager.ts
import { type Router, type RouteRecordRaw } from 'vue-router';
import { useAuthStore } from '@/stores/auth.store';
import { usePermissionStore } from '@/stores/permission.store';

// Manifest Modul Dinamis (Lazy Modules Mapping)
const enterpriseViewModules = import.meta.glob('../views/**/*.vue');

export function setupEnterpriseGuards(router: Router): void {
  let isDynamicRoutesLoaded = false;

  router.beforeEach(async (to, from) => {
    const authStore = useAuthStore();
    const permStore = usePermissionStore();

    // Skenario 1: Public Route langsung dialirkan
    if (!to.meta.requiresAuth) {
      return true;
    }

    // Skenario 2: Token Check & Silent Refresh Mechanism
    if (!authStore.isAuthenticated) {
      const refreshed = await authStore.attemptSilentRefresh();
      if (!refreshed) {
        return { 
          name: 'Login', 
          query: { redirect: to.fullPath } 
        };
      }
    }

    // Skenario 3: Inject dynamic routes jika belum terdaftar
    if (!isDynamicRoutesLoaded) {
      try {
        const allowedRoutesPayload = await permStore.fetchUserRouteManifest();
        
        allowedRoutesPayload.forEach((routeDef) => {
          const resolvedComponent = enterpriseViewModules[`../views/${routeDef.componentPath}.vue`];
          
          if (!resolvedComponent) {
            throw new Error(`Modul komponen tidak ditemukan: ${routeDef.componentPath}`);
          }

          const dynamicRouteRecord: RouteRecordRaw = {
            path: routeDef.path,
            name: routeDef.name,
            component: resolvedComponent,
            meta: {
              requiresAuth: true,
              permissions: routeDef.permissions,
              layout: routeDef.layout,
            },
          };

          // Registrasi rute ke dalam state router
          router.addRoute('AuthenticatedRoot', dynamicRouteRecord);
        });

        isDynamicRoutesLoaded = true;
        
        // Picu kembali navigasi ke target awal dengan replace: true untuk membersihkan history stack
        return { ...to, replace: true };
      } catch (error) {
        await authStore.forceLogout();
        return { name: 'Login', query: { error: 'SESSION_CORRUPTED' } };
      }
    }

    // Skenario 4: Role-Based Access Control (RBAC) Fine-Grained Guard
    if (to.meta.permissions && to.meta.permissions.length > 0) {
      const hasPermission = permStore.hasRequiredPermissions(to.meta.permissions);
      if (!hasPermission) {
        return { name: 'Forbidden403' };
      }
    }

    return true;
  });

  router.onError((error, to) => {
    // Tangani Dynamic Chunk Loading Error (Misal deploy baru saat user navigasi)
    if (error.message.includes('Failed to fetch dynamically imported module')) {
      window.location.assign(to.fullPath);
    } else {
      console.error('[Router Critical Telemetry]', error);
    }
  });
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Karakteristik | HTML5 History API (`createWebHistory`) | Hash Mode (`createWebHashHistory`) | Memory Mode (`createMemoryHistory`) |
| :--- | :--- | :--- | :--- |
| **Bentuk URL** | Bersih: `https://bank.com/ledger/102` | Terdapat fragmen: `https://bank.com/#/ledger/102` | Abstrak: URL browser tidak berubah |
| **Ketergantungan Server** | **Tinggi**: Membutuhkan `try_files` (Nginx) / URL Rewrite | **Nol**: Request browser berhenti sebelum karakter `#` | **Nol**: Tidak terikat DOM/Jendela browser |
| **Dampak SEO** | Optimal untuk Search Engine Crawlers | Buruk; crawler tradisional mengabaikan fragmen | Tidak relevan (Kecuali dieksekusi di Node.js SSR) |
| **Penggunaan Kasus** | Production Web Enterprise, Public Portals | Prototipe Cepat, Electron Apps, Hybrid WebView | SSR Rendering, Vitest/Jest Unit Test suites |
| **State Retention** | Mendukung payload native `history.state` | Rentan hilang pada sejumlah parser legacy | Eksklusif di heap memory; hilang saat hard refresh |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Inifinite Redirection Loops
Jika rute target fallback (`/login`) juga dideklarasikan dengan `meta: { requiresAuth: true }`, navigasi guard akan memanggil redirect secara tak hingga (*infinite loop*).
*Mitigasi*: Pisahkan rute otentikasi secara tegas di luar guard tree, atau validasi `to.name !== 'Login'` sebelum mengembalikan redirect target.

### 2. Component Re-use pada URL Params Change
Secara default, jika berpindah dari `/clients/101` ke `/clients/102`, Vue Router **tidak akan** me-mount ulang komponen `ClientDetail.vue`. Vue menggunakan ulang instans yang sama untuk efisiensi DOM. Konsekuensi: `onMounted` tidak terpicu kembali.
*Mitigasi*:
Gunakan `onBeforeRouteUpdate` lifecycle hook:
```typescript
import { onBeforeRouteUpdate } from 'vue-router';

onBeforeRouteUpdate(async (to, from) => {
  if (to.params.id !== from.params.id) {
    await fetchClientData(to.params.id as string);
  }
});
```
Atau paksa re-mount menggunakan key pada template: `<router-view :key="$route.fullPath" />` (Gunakan dengan bijak, trade-off performa render ulang meningkat).

### 3. Dynamic Chunk Loading Failure pasca CD Deploy
Saat pipeline CI/CD melakukan build baru, file chunk lama (misal: `Dashboard.a83bf.js`) terhapus dari server CDN dan diganti `Dashboard.99fca.js`. Pengguna lama yang masih membuka aplikasi akan mengalami error fatal `ChunkLoadError` ketika berpindah menu.
*Mitigasi*: Gunakan penanganan interseptor `router.onError()` untuk memicu reload halaman penuh menggunakan `window.location.assign()`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Mencampur Pola Callback `next()` dan `Promise Return`
```typescript
// ANTI-PATTERN: Menyebabkan mutasi ganda dan hanging lifecycle
router.beforeEach((to, from, next) => {
  if (to.meta.requiresAuth) {
    next('/login'); // BAD!
    return true;    // BAD! Bentrok antara eksekusi callback dan promise resolution
  }
  next();
});

// CORRECT: Gunakan nilai kembalian murni (Vue Router 4 standard)
router.beforeEach((to, from) => {
  if (to.meta.requiresAuth) {
    return '/login';
  }
  return true;
});
```

### 2. Melupakan Deklarasi Asinkron pada `beforeRouteEnter`
Argumen callback `next` pada `beforeRouteEnter` adalah satu-satunya tempat untuk mengakses komponen via `vm`. Pemanggilan asynchronous tanpa penanganan presisi sering menyebabkan *leaked access*.
```typescript
// SALAH: Mengakses this secara langsung
beforeRouteEnter(to, from) {
  // console.log(this.userData); // ERROR! 'this' bernilai undefined
}

// BENAR: Gunakan callback vm
beforeRouteEnter(to, from, next) {
  next((vm) => {
    // Instance komponen dapat diakses via variabel vm
    (vm as any).initializeSpecificData();
  });
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Strict Modular Route Files**: Pisahkan routing tree per business domain (`/modules/billing/billing.routes.ts`, `/modules/identity/identity.routes.ts`) lalu gabungkan via *Spread Operator* atau `addRoute()`.
2. **Deterministic Prefetching on Hover**: Gunakan directive custom untuk mengunduh modul chunk JavaScript sebelum pengguna benar-benar mengklik tautan:
   ```typescript
   // Directives: v-prefetch-route
   const prefetchRoute = {
     mounted(el: HTMLElement, binding: { value: string }) {
       el.addEventListener('mouseenter', () => {
         const route = router.resolve(binding.value);
         route.matched.forEach((record) => {
           for (const key in record.components) {
             const comp = record.components[key];
             if (typeof comp === 'function') (comp as Function)();
           }
         });
       }, { once: true });
     }
   };
   ```
3. **Always Normalize Query Parameters**: Query parameter bernilai fleksibel (string atau array). Selalu bungkus query URL dengan *parser validator* (seperti Zod) sebelum mengonsumsinya di state pinia/komponen.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Vite Chunk Splitting Strategy
Kompilasi rute Vue harus dikelompokkan secara logis untuk menghindari fragmentasi HTTP request berlebihan (*over-fragmentation*). Konfigurasikan pada `vite.config.ts`:

```typescript
// vite.config.ts
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('vue-router') || id.includes('pinia')) {
              return 'vendor-core';
            }
            return 'vendor-libs';
          }
          if (id.includes('/views/finance/')) {
            return 'finance-domain';
          }
        },
      },
    },
  },
});
```

### Pembersihan Garbage Collector pada Component Unmount
Pastikan store subscriptions, WebSocket listeners, atau abort controllers yang terhubung dengan rute tertentu dibatalkan secara eksplisit menggunakan lifecycle guard `onBeforeRouteLeave` guna mencegah *Detached DOM Tree Memory Leaks*.

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Mitigasi Serangan Open Redirect
Pola umum: Mengarahkan pengguna kembali ke rute asal via query `?redirect=/path`. Penyerang dapat menyuntikkan: `?redirect=https://evil-phishing.com`.

```typescript
// Sanitasi query redirect
function sanitizeRedirectUri(target: unknown): string {
  if (typeof target !== 'string') return '/';
  
  // Validasi: Harus diawali satu slash '/' dan bukan skema eksternal '//' atau 'http'
  const isPathSafe = target.startsWith('/') && !target.startsWith('//');
  return isPathSafe ? target : '/';
}

// Implementasi di Navigation Guard:
router.push(sanitizeRedirectUri(route.query.redirect));
```

### 2. State Tampering Defense
Hindari mengekspos data kredensial atau peran otorisasi melalui `history.state` karena state ini dapat dimutasi secara langsung oleh pengguna melalui DevTools Console (`window.history.replaceState(...)`). Validasi hak akses harus tetap bersumber dari payload token JWT yang terenkripsi atau state management internal yang terkunci.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Pasang telemetri terpadu untuk mengukur durasi transisi setiap rute (*User Experience Route Latency*). Gunakan Performance API browser:

```typescript
// src/router/telemetry.ts
import { type Router } from 'vue-router';

export function setupRouterTelemetry(router: Router) {
  let navigationStartTime = 0;

  router.beforeEach((to, from) => {
    navigationStartTime = performance.now();
  });

  router.afterEach((to, from, failure) => {
    const duration = performance.now() - navigationStartTime;
    
    const payload = {
      from: from.fullPath,
      to: to.fullPath,
      durationMs: Math.round(duration),
      hasFailed: !!failure,
      failureType: failure ? failure.type : null,
      timestamp: new Date().toISOString(),
    };

    // Broadcast ke Data Collector (misal: Sentry / Datadog RUM)
    if (duration > 1000) {
      console.warn('[Slow Navigation Alert]', payload);
    }

    if (window.performance && window.performance.mark) {
      window.performance.mark(`route_change_${to.name?.toString()}`);
    }
  });
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Pilih History Mode**: Gunakan `createWebHistory` untuk produksi aplikasi berbasis browser standar. Wajib konfigurasi server rewrite fallback ke `index.html`.
* **Guard Flow Return Values**:
  * `return true`: Transisi dizinkan.
  * `return false`: Batalkan transisi secara instan, kembalikan posisi URL/history stack.
  * `return '/path'`: Redirect ke URL baru.
  * Hindari penggunaan callback argumen `next()` pada Vue Router 4.
* **Perubahan Param Rute**: Rute dengan komponen sama tidak mengeksekusi `onMounted` ulang. Gunakan watcher pada `route.params` atau implementasikan `onBeforeRouteUpdate`.
* **Dynamic Routes**: Gunakan `router.addRoute(parent, route)` dan pastikan mengembalikan `return { ...to, replace: true }` jika rute dinamis belum terindeks saat siklus transisi sedang berlangsung.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah satu jawaban yang paling tepat serta analisis implikasinya:

1. **Apa yang terjadi secara internal jika sebuah navigasi guard asinkron membutuhkan waktu 3000ms untuk resolve, dan sebelum selesai pengguna mengklik rute lain?**
   * A. Router crash dan melempar *Unhandled Promise Rejection*.
   * B. Transisi pertama memaksakan mount UI, lalu transisi kedua menimpanya secara paksa.
   * C. Transisi pertama dibatalkan secara atomik dengan error `NavigationFailureType.cancelled`, dan router memproses navigasi kedua.
   * D. Kedua komponen dirender bersamaan dalam `router-view` multi-layer.

2. **Mengapa Vue Router 4 membungkus state rutenya ke dalam `shallowRef` alih-alih `ref` konvensional?**
   * A. Karena `ref` tidak mendukung tipe objek yang kompleks.
   * B. Menghindari rekursi Proxy reaktivitas yang tidak perlu, karena objek rute diganti secara atomik (*immutable replacement*) pada setiap navigasi.
   * C. Keterbatasan API browser History yang menolak Proxy bawaan Vue.
   * D. Memaksa developer menggunakan `watch` alih-alih `computed`.

3. **Manakah lifecycle guard berikut yang merupakan SATU-SATUNYA tempat yang TIDAK DAPAT mengakses instance `this` komponen secara langsung, namun dapat mengaksesnya via callback khusus?**
   * A. `beforeRouteUpdate`
   * B. `beforeRouteLeave`
   * C. `beforeResolve`
   * D. `beforeRouteEnter`

4. **Dalam konfigurasi Nginx untuk SPA dengan `createWebHistory`, baris direktif manakah yang wajib ada guna mencegah HTTP 404 saat pengguna melakukan hard reload pada rute dalam?**
   * A. `proxy_pass http://localhost:8080;`
   * B. `try_files $uri $uri/ /index.html;`
   * C. `rewrite ^/(.*)$ /index.html permanent;`
   * D. `error_page 404 /404.html;`

5. **Apa risiko keamanan paling kritis ketika mengarahkan pengguna via URL: `router.push(route.query.target as string)` tanpa validasi?**
   * A. Server-Side Request Forgery (SSRF)
   * B. Cross-Site Request Forgery (CSRF)
   * C. Open Redirection Vulnerability
   * D. SQL Injection

---

### Kunci Jawaban & Analisis
1. **Jawaban: C**. Vue Router 4 mengimplementasikan *Internal Navigation Counter*. Transisi lama yang tertimpa akan langsung ditandai usang dan dibatalkan via abort token internal untuk menjaga konsistensi state UI.
2. **Jawaban: B**. Komposisi objek rute bersifat imutabel. Setiap navigasi menciptakan objek rute baru secara utuh. `shallowRef` menghemat beban komputasi CPU secara masif karena engine tidak perlu melacak reaktivitas hingga ke tingkat terdalam query URL.
3. **Jawaban: D**. `beforeRouteEnter` dijalankan sebelum guard resolusi komponen selesai dan sebelum instansiasi komponen Vue dieksekusi. Karenanya, `this` bernilai `undefined`. Satu-satunya cara mengakses instance adalah memberikan callback ke fungsi argumen `next((vm) => ...)`.
4. **Jawaban: B**. Pada `createWebHistory`, path URL browser dikirim ke server. Server harus mencoba mencari file fisik yang cocok (`$uri`), direktori fisik (`$uri/`), dan jika keduanya tidak ada, mengalihkan eksekusi ke berkas fallback SPA `/index.html`.
5. **Jawaban: C**. Tanpa validasi, penyerang dapat memanipulasi link phishing resmi dengan menambahkan parameter `target=https://malicious-site.com/auth-steal`. Pengguna yang berasumsi link aman akan teralihkan ke luar sistem tanpa peringatan.

---

## SEKSI 20 — TANTANGAN MANDIRI & PROYEK PRAKTIKUM

### Rancang & Bangun: Enterprise Navigation Orchestrator Module
Bangun modul independen Vue Router 4 dengan spesifikasi teknis berikut:

1. **Desentralisasi Rute**: 
   * Buat struktur proyek di mana terdapat 2 sub-domain fungsional terpisah: Modul `Finance` dan Modul `HumanResources`.
   * Masing-masing modul harus mendeklarasikan berkas rute mereka sendiri secara independen tanpa diimpor langsung di file `router/index.ts` utama.
2. **Dynamic Ingestion**:
   * Implementasikan loader function yang memindai dan meregistrasi rute dari modul-modul tersebut menggunakan mekanisme `import.meta.glob` dan `router.addRoute()` secara aman pada saat runtime setelah pengguna berhasil login.
3. **Telemetry & Abort Handling**:
   * Implementasikan custom global guard yang melacak setiap perpindahan rute dan mengirimkan metrik durasi ke console table jika durasi transisi melampaui ambang batas 200 milidetik.
   * Tambahkan penanganan `ChunkLoadError` terpadu yang memicu fallback mekanisme reload halaman secara otomatis.
4. **Verifikasi Strict Type**:
   * Buat type augmentation pada namespace `vue-router` untuk menambahkan atribut `requiredRole: 'SUPERADMIN' | 'MANAGER' | 'EMPLOYEE'` serta pastikan kompilator TypeScript melempar error jika rute didefinisikan tanpa metadata tersebut.