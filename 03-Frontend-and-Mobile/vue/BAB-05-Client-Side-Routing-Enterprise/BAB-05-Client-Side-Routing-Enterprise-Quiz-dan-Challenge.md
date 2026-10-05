# BAB-05-Client-Side-Routing-Enterprise: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi mandiri, verifikasi pemahaman konsep, serta pengujian problem-solving praktis untuk arsitektur *Client-Side Routing* skala enterprise menggunakan Vue Router 4 dan Vue 3.

---

## Bagian 1: 5 Pertanyaan Basic (Fundamental)

### Soal 1: HTML5 History Mode vs Hash Mode di Lingkungan Produksi
**Pertanyaan:**  
Mengapa mode `createWebHistory()` membutuhkan konfigurasi fallback khusus pada web server (seperti Nginx, Caddy, atau Apache), sedangkan `createWebHashHistory()` dapat berjalan langsung tanpa konfigurasi server tambahan? Apa implikasi arsitektural dan SEO dari kedua mode tersebut?

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban & Pembahasan:**
1. **Mekanisme Server Request:**
   - **`createWebHashHistory()`**: URL menggunakan tanda pagar (contoh: `https://app.enterprise.com/#/dashboard/analytics`). Karakter setelah `#` (fragment identifier) tidak pernah dikirimkan ke web server dalam HTTP request header. Server selalu hanya menerima request untuk dokumen root `/` (`index.html`).
   - **`createWebHistory()`**: Menggunakan HTML5 History API (`pushState` dan `replaceState`). URL tampak bersih seperti aplikasi MPA konvensional (contoh: `https://app.enterprise.com/dashboard/analytics`). Ketika user melakukan direct URL access atau refresh browser, browser mengirimkan HTTP GET request ke server dengan path `/dashboard/analytics`.
2. **Kebutuhan Server Fallback:**
   - Karena file fisik `/dashboard/analytics` tidak ada di storage server (semua asset dibundel ke dalam single-page app), web server akan merespons dengan HTTP `404 Not Found`.
   - Diperlukan konfigurasi rewrite rule (misalnya `try_files $uri $uri/ /index.html;` pada Nginx) agar semua request yang tidak cocok dengan asset statis fisik diarahkan kembali ke `index.html` dan Vue Router mengeksekusi routing di sisi client.
3. **Implikasi SEO dan Profesionalitas:**
   - Hash mode buruk untuk indexing crawler web modern dan analitik tracking URL, serta terlihat usang. HTML5 History mode menghasilkan struktur URL standar web yang ramah SEO dan memenuhi standar web enterprise.
</details>

---

### Soal 2: Perbedaan Eksekusi `beforeEach`, `beforeResolve`, dan `afterEach`
**Pertanyaan:**  
Jelaskan urutan siklus eksekusi (lifecycle sequence) antara global navigation guards: `router.beforeEach`, `router.beforeResolve`, dan `router.afterEach`. Pada fase mana data pre-fetching atau integrasi third-party analytics paling tepat dieksekusi?

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban & Pembahasan:**
1. **Urutan Eksekusi Guard:**
   - `router.beforeEach`: Guard pertama yang dipicu sebelum navigasi dimulai. Digunakan untuk otentikasi, otorisasi RBAC (Role-Based Access Control), dan validasi awal token.
   - Guard di tingkat route (`beforeEnter`) dan guard di tingkat komponen (`beforeRouteEnter`).
   - `router.beforeResolve`: Dieksekusi tepat sebelum navigasi dikonfirmasi, **setelah semua in-component guards dan async route components selesai di-resolve**.
   - Navigasi dikonfirmasi.
   - `router.afterEach`: Dieksekusi setelah navigasi selesai sepenuhnya. Guard ini tidak menerima fungsi `next` dan tidak dapat membatalkan navigasi.
2. **Penempatan Kasus Nyata:**
   - **Data Pre-fetching / Loading Progress:** Paling ideal pada `router.beforeResolve` jika Anda ingin memastikan semua dependensi data atau async chunk siap sebelum rute ditampilkan, atau memicu progress bar (`NProgress.start()` di `beforeEach` dan `NProgress.done()` di `afterEach`).
   - **Third-party Analytics (Google Analytics, Mixpanel, Datadog RUM):** Wajib ditempatkan di `router.afterEach` karena Anda hanya ingin mencatat page view saat navigasi dipastikan berhasil dan URL telah aktif.
</details>

---

### Soal 3: Dynamic Route Matching dan `route.params` Reactivity
**Pertanyaan:**  
Ketika pengguna bernavigasi dari `/users/10` ke `/users/20` pada rute dinamis `{ path: '/users/:id', component: UserDetail }`, mengapa lifecycle hook `onMounted()` pada komponen `UserDetail` tidak terpanggil kembali? Bagaimana dua cara terbaik mengatasi isu reaktivitas parameter ini?

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban & Pembahasan:**
1. **Penyebab Component Reuse:**
   - Vue Router mengoptimalkan performa dengan menggunakan kembali instance komponen yang sama (*component reuse*) ketika rute target menggunakan komponen yang sama persis dan hanya mengubah parameter rute. Penghancuran (*unmount*) dan pembuatan ulang (*mount*) komponen dihindari demi efisiensi DOM.
2. **Solusi Reaktivitas:**
   - **Metode 1 (Watch `route.params` atau `props`):**
     Gunakan `watch` pada parameter rute untuk memicu pengambilan data ulang:
     ```typescript
     import { watch } from 'vue';
     import { useRoute } from 'vue-router';

     const route = useRoute();
     watch(
       () => route.params.id,
       (newId) => {
         fetchUserData(newId);
       },
       { immediate: true }
     );
     ```
   - **Metode 2 (Dynamic Key pada `<RouterView />`):**
     Memaksa re-instantiation komponen dengan menetapkan `:key="$route.fullPath"`:
     ```vue
     <RouterView :key="$route.fullPath" />
     ```
     *Catatan:* Metode 2 efektif namun mematikan optimasi reuse sehingga memiliki overhead rendering lebih tinggi dibanding reactive watcher.
</details>

---

### Soal 4: Props De-coupling vs `useRoute()`
**Pertanyaan:**  
Mengapa menggunakan `props: true` atau fungsi mapper props pada konfigurasi route dianggap sebagai *best practice* modularitas arsitektur dibandingkan langsung mengonsumsi `useRoute()` di dalam subkomponen presentasional?

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban & Pembahasan:**
1. **Tight Coupling vs Reusability:**
   - Mengakses `useRoute().params.id` di dalam komponen mengikat komponen tersebut secara erat (*tight coupling*) dengan konteks Vue Router. Komponen tidak lagi murni (*pure presentation*) dan sulit digunakan di luar router, misalnya di dalam Storybook, modal pop-up, unit testing, atau layout alternatif.
2. **Dekoupling dengan Props:**
   - Dengan menyetel `props: true` atau `props: (route) => ({ id: Number(route.params.id), query: route.query.q })`:
     ```typescript
     const routes = [
       {
         path: '/invoices/:id',
         component: InvoiceDetail,
         props: (route) => ({ invoiceId: route.params.id })
       }
     ];
     ```
   - Komponen target hanya mendeklarasikan `defineProps<{ invoiceId: string }>()`. Komponen menjadi stateless terhadap rute, mudah diuji via unit test dengan passing props langsung tanpa perlu me-mock router instance.
</details>

---

### Soal 5: Named Views vs Nested Routes
**Pertanyaan:**  
Jelaskan perbedaan mendasar antara pola **Named Views** dan **Nested Routes** pada Vue Router 4. Berikan contoh kasus struktural kapan masing-masing pola wajib digunakan.

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban & Pembahasan:**
1. **Nested Routes (`children: [...]`):**
   - Menggambarkan hierarki relasi antar rute induk dan rute anak (URL berjenjang).
   - Menampilkan komponen anak di dalam tag `<RouterView />` yang terletak di dalam template komponen induk.
   - *Kasus Penggunaan:* Panel Dashboard di mana layout utama memiliki Sidebar dan Header persisten, sementara area konten utama berubah-ubah (`/dashboard/overview`, `/dashboard/settings`).
2. **Named Views (`components: { default: ..., sidebar: ..., footer: ... }`):**
   - Menampilkan beberapa komponen secara bersamaan pada level hierarki yang sama tanpa nesting URL.
   - Menggunakan beberapa `<RouterView name="..." />` yang memiliki atribut `name` berbeda pada template yang sama.
   - *Kasus Penggunaan:* Split-view layout enterprise di mana halaman tertentu membutuhkan Sidebar custom khusus (`name="sidebar"`), area Workspace utama (`name="default"`), dan Inspector panel (`name="inspector"`), yang dikonfigurasikan secara granular per route record.
</details>

---

## Bagian 2: 5 Pertanyaan Intermediate (Architectural & Performance)

### Soal 6: Route Meta Fields & Strict TypeScript Typing
**Pertanyaan:**  
Bagaimana cara mengimplementasikan deklarasi Route Meta Fields yang memiliki *type-safety* ketat pada TypeScript (menggunakan Module Augmentation) untuk mendukung fitur enterprise seperti RBAC Permissions, Layout Selection, dan Document Title?

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban & Pembahasan:**
Vue Router mengizinkan penambahan metadata kustom via properti `meta`. Tanpa deklarasi tipe, `route.meta` bertipe `Record<string | number | symbol, unknown>`.

**Implementasi Strict Type Augmentation (`vue-router.d.ts`):**
```typescript
import 'vue-router';

declare module 'vue-router' {
  interface RouteMeta {
    title: string;
    requiresAuth: boolean;
    permissions?: Array<'READ_DASHBOARD' | 'MANAGE_USERS' | 'BILLING_ADMIN'>;
    layout?: 'AppLayoutDefault' | 'AppLayoutDashboard' | 'AppLayoutBlank';
    cacheBustKey?: string;
  }
}
```
**Manfaat Enterprise:**
- Autocomplete otomatis pada IDE saat menulis route definition.
- Mencegah typo pada pengecekan guard RBAC (`meta.permissions`).
- Compile-time error jika ada rute yang tidak menyertakan metadata esensial saat strict config diaktifkan.
</details>

---

### Soal 7: Code Splitting & Dynamic Imports dengan Chunk Grouping
**Pertanyaan:**  
Dalam bundler modern (Vite / Rollup), bagaimana Anda mengelompokkan beberapa rute yang terkait erat (misalnya modul Finansial: Invoices, Billing, Transactions) ke dalam satu file bundle JavaScript (*chunk*) yang sama saat di-lazy-load? Mengapa over-splitting dapat merugikan performa aplikasi?

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban & Pembahasan:**
1. **Chunk Grouping pada Vite / Rollup:**
   Rollup chunking dapat diatur via comment `/* webpackChunkName: "financial" */` jika didukung plugin, atau lebih direkomendasikan melalui konfigurasi `manualChunks` di `vite.config.ts`:
   ```typescript
   // vite.config.ts
   export default defineConfig({
     build: {
       rollupOptions: {
         output: {
           manualChunks: {
             'finance-module': [
               './src/views/finance/InvoicesView.vue',
               './src/views/finance/BillingView.vue',
               './src/views/finance/TransactionsView.vue'
             ]
           }
         }
       }
     }
   });
   ```
2. **Dampak Negatif Over-Splitting:**
   - Membagi setiap komponen kecil menjadi chunk terpisah (*micro-chunks*) mengakibatkan lonjakan jumlah HTTP network request (*network waterfalls*), membebani parser browser, dan menurunkan efisiensi kompresi Gzip/Brotli (kompresi bekerja lebih optimal pada file berukuran medium ~50-150KB dibanding puluhan file berukuran <2KB).
</details>

---

### Soal 8: Penanganan Asynchronous Navigation Failure
**Pertanyaan:**  
Mengapa memanggil `router.push('/dashboard')` dapat menghasilkan unhandled promise rejection? Bagaimana cara mendeteksi dan mengkategorikan tipe kegagalan navigasi menggunakan utility `isNavigationFailure` dan `NavigationFailureType`?

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban & Pembahasan:**
1. **Penyebab Promise Rejection:**
   `router.push` mengembalikan `Promise<NavigationFailure | void | undefined>`. Jika navigasi dicegah oleh guard (misalnya mengembalikan `false` atau dialihkan ke rute lain via redirect), promise akan me-resolve failure object atau melempar rejection jika navigasi dibatalkan secara kritis.
2. **Mendeteksi Failure Type:**
   ```typescript
   import { useRouter, isNavigationFailure, NavigationFailureType } from 'vue-router';

   const router = useRouter();

   async function navigateSafely(targetPath: string) {
     const failure = await router.push(targetPath);

     if (isNavigationFailure(failure, NavigationFailureType.aborted)) {
       console.warn('Navigasi dibatalkan oleh guard atau user: ', failure.to);
     } else if (isNavigationFailure(failure, NavigationFailureType.cancelled)) {
       console.warn('Navigasi baru dimulai sebelum navigasi ini selesai.');
     } else if (isNavigationFailure(failure, NavigationFailureType.duplicated)) {
       console.info('Aplikasi sudah berada pada rute yang dituju.');
     }
   }
   ```
</details>

---

### Soal 9: Scroll Behavior & Manual Scroll Position Management
**Pertanyaan:**  
Rancang konfigurasi fungsi `scrollBehavior` untuk aplikasi enterprise yang memenuhi kriteria:
1. Kembali ke posisi tersimpan saat navigasi browser Back/Forward (*popstate*).
2. Smooth scroll ke elemen target jika URL memiliki hash anchor (`#section`).
3. Selalu reset ke posisi paling atas `(0, 0)` untuk rute normal, namun ditunda (*delay*) sampai animasi transisi halaman selesai.

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban & Pembahasan:**
```typescript
import { createRouter, createWebHistory, type RouterScrollBehavior } from 'vue-router';

const scrollBehavior: RouterScrollBehavior = (to, from, savedPosition) => {
  if (savedPosition) {
    // 1. Mempertahankan posisi saat tombol Back/Forward ditekan
    return savedPosition;
  }

  if (to.hash) {
    // 2. Smooth scroll ke ID selector jika tersedia
    return {
      el: to.hash,
      behavior: 'smooth',
      top: 80 // Offset untuk fixed header/navbar
    };
  }

  // 3. Delay scroll position ke top agar sinkron dengan transisi CSS (250ms)
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({ left: 0, top: 0, behavior: 'smooth' });
    }, 250);
  });
};
```
</details>

---

### Soal 10: State Management Synchronization & Async Guards Pitfalls
**Pertanyaan:**  
Mengapa memanggil fungsi guard asynchronous yang bergantung pada Pinia Store (seperti validasi session token) dapat menyebabkan *infinite redirection loop* atau *race condition* jika tidak ditangani dengan benar? Bagaimana pola resolusi token validation yang aman?

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban & Pembahasan:**
1. **Akar Permasalahan Infinite Loop:**
   Ketika guard memeriksa token, mendapati token kedaluwarsa, lalu mengarahkan navigasi ke `return '/login'`, guard akan terpanggil kembali untuk rute `/login`. Jika rute `/login` tidak dikecualikan dari guard atau pengecekan auth dijalankan tanpa memeriksa `to.path === '/login'`, aplikasi akan terus-menerus me-redirect ke dirinya sendiri.
2. **Pola Resolusi Aman:**
   ```typescript
   router.beforeEach(async (to, from) => {
     const authStore = useAuthStore();

     // Inisialisasi token session jika belum di-load (refresh page scenario)
     if (!authStore.isInitialized) {
       await authStore.initializeAuthSession();
     }

     if (to.meta.requiresAuth && !authStore.isAuthenticated) {
       // Cegah redirect jika sudah menuju login
       if (to.name !== 'Login') {
         return {
           name: 'Login',
           query: { redirect: to.fullPath } // Simpan redirect URL
         };
       }
     }

     // Jika pengguna sudah login tapi mencoba mengakses halaman Login/Register
     if (to.meta.guestOnly && authStore.isAuthenticated) {
       return { name: 'Dashboard' };
     }
   });
   ```
</details>

---

## Bagian 3: 3 Skenario Kasus Nyata Produksi (Incident Investigation)

### Skenario 1: The "Dead Guard" RBAC Security Bypass
- **Konteks Masalah:** Tim QA menemukan bahwa pengguna dengan role *Guest/Operator* dapat mengakses halaman audit sensitif `/admin/security-audit` jika mereka mengetikkan URL langsung di browser address bar dan menekan Enter. Namun, ketika mereka mengklik link menu navigasi di UI, akses berhasil dicegah dengan benar.
- **Hasil Investigasi Kode:**
  Ditemukan guard navigasi ditulis seperti ini:
  ```typescript
  // router.ts
  router.beforeEach((to, from, next) => {
    const authStore = useAuthStore();
    if (to.meta.requiresAdmin) {
      if (authStore.userRole === 'ADMIN') {
        next();
      } else {
        next('/unauthorized');
      }
    }
    next(); // <--- MASALAH KRITIS
  });
  ```
- **Tugas Anda:** Identifikasi secara presisi bug pada guard di atas dan tulis perbaikannya menggunakan standar modern Vue Router 4 (tanpa callback `next()`).

<details>
<summary>👉 Analisis Root Cause & Solusi</summary>

**Root Cause:**
1. **Multiple `next()` Calls:** Callback `next()` dipanggil lebih dari satu kali dalam satu alur eksekusi. Pada pengecekan pertama, meskipun `next('/unauthorized')` dijalankan, kode di bawah blok `if` terus berjalan dan memanggil `next()` kedua. Hal ini menyebabkan kondisi *race condition* pada lifecycle guard.
2. **Async State Unavailability:** Saat browser di-refresh pada direct URL access, `authStore` belum selesai melakukan rehidrasi user profile dari API backend (default role masih null atau ter-bypass karena kesalahan pemanggilan `next()`).

**Solusi Standar Vue Router 4 (Return Value Based):**
```typescript
router.beforeEach(async (to, from) => {
  const authStore = useAuthStore();

  // Pastikan profile terhidrasi sebelum mengevaluasi role
  if (authStore.token && !authStore.userProfile) {
    try {
      await authStore.fetchUserProfile();
    } catch (error) {
      authStore.resetSession();
      return { name: 'Login', query: { redirect: to.fullPath } };
    }
  }

  if (to.meta.requiresAdmin) {
    if (authStore.userRole !== 'ADMIN') {
      return { name: 'Unauthorized' };
    }
  }

  // Izinkan navigasi secara implisit dengan return true atau void
  return true;
});
```
</details>

---

### Skenario 2: Lazy Chunk 404 Loading Error Pasca Deployment Baru
- **Konteks Masalah:** Sesaat setelah pipeline CI/CD melakukan build dan deployment versi baru aplikasi ke server produksi, ratusan log error masuk ke Sentry: `Failed to fetch dynamically imported module: https://app.corp.com/assets/BillingView-a8d29b.js (404 Not Found)`. Hal ini terjadi pada pengguna aktif yang sedang membuka aplikasi versi lama saat mencoba membuka menu baru.
- **Tugas Anda:** Jelaskan penyebab teknis insiden ini dan implementasikan strategi auto-recovery di level Vue Router untuk memulihkan user experience tanpa crash.

<details>
<summary>👉 Analisis Root Cause & Solusi</summary>

**Root Cause:**
Vite/Rollup menghasilkan nama hash unik untuk setiap chunk file pada setiap build produksi (misalnya `BillingView-a8d29b.js`). Ketika build baru di-deploy:
1. Asset lama di server digantikan oleh asset baru (misalnya `BillingView-c3e91f.js`).
2. Single-page app yang sedang aktif di browser pengguna masih menyimpan referensi URL chunk lama.
3. Saat pengguna mengklik rute yang di-lazy-load, browser mencoba mengunduh chunk lama yang sudah dihapus dari server, menghasilkan HTTP 404.

**Solusi Global Router Error Handler:**
```typescript
// router/index.ts
router.onError((error, to) => {
  const isChunkLoadFailed =
    error.message.includes('Failed to fetch dynamically imported module') ||
    error.message.includes('Importing a module script failed');

  if (isChunkLoadFailed) {
    const reloadKey = `chunk_reload_${to.fullPath}`;
    const hasReloaded = sessionStorage.getItem(reloadKey);

    if (!hasReloaded) {
      sessionStorage.setItem(reloadKey, 'true');
      console.warn('Versi aplikasi baru terdeteksi. Memuat ulang browser...');
      // Force reload dari server untuk mengambil index.html dan manifest baru
      window.location.href = to.fullPath;
    } else {
      sessionStorage.removeItem(reloadKey);
      console.error('Gagal memuat modul bahkan setelah reload penuh:', error);
      // Arahkan ke rute error offline/maintenance
      router.push({ name: 'SystemError', params: { code: 'CHUNK_LOAD_FAILED' } });
    }
  }
});
```
</details>

---

### Skenario 3: Form Dirty State Loss & Guard Navigation Leaks
- **Konteks Masalah:** Aplikasi ERP Enterprise memiliki form input transaksi finansial yang kompleks. Pengguna sering kali tidak sengaja menekan tombol Back atau mengklik menu sidebar sehingga seluruh isian form hilang tanpa peringatan konfirmasi simpan. Tim pengembang mencoba menggunakan `window.onbeforeunload`, namun menyadari bahwa event tersebut hanya menangani browser refresh/tab close dan **tidak menangani navigasi SPA internal**.
- **Tugas Anda:** Implementasikan mekanisme *Unsaved Changes Guard* menggunakan `onBeforeRouteLeave` pada komponen Vue 3 Composition API dengan dukungan modal konfirmasi kustom (bukan browser alert bawaan).

<details>
<summary>👉 Analisis Root Cause & Solusi</summary>

**Solusi Implementasi Composition API:**
```vue
<script setup lang="ts">
import { ref } from 'vue';
import { onBeforeRouteLeave } from 'vue-router';
import { useModalDialog } from '@/composables/useModalDialog';

const isDirty = ref(false);
const isSubmitting = ref(false);
const { openConfirmModal } = useModalDialog();

// Hook navigasi rute internal Vue Router
onBeforeRouteLeave(async (to, from) => {
  // Jika form tidak dimodifikasi atau sedang submit yang valid, izinkan navigasi
  if (!isDirty.value || isSubmitting.value) {
    return true;
  }

  // Tampilkan custom modal enterprise non-blocking
  const userConfirmed = await openConfirmModal({
    title: 'Perubahan Belum Disimpan',
    content: 'Anda memiliki draf transaksi yang belum disimpan. Yakin ingin meninggalkan halaman ini?',
    confirmText: 'Tinggalkan Halaman',
    cancelText: 'Lanjutkan Mengedit'
  });

  if (!userConfirmed) {
    // Membatalkan navigasi internal
    return false;
  }

  return true;
});

// Listener terpisah untuk pencegahan refresh / close browser window
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', (event) => {
    if (isDirty.value && !isSubmitting.value) {
      event.preventDefault();
      event.returnValue = ''; // Standard requirement browser
    }
  });
}
</script>
```
</details>

---

## Bagian 4: Practical Chapter Challenge

### Tantangan Arsitektur: "Enterprise Multi-Tier Guard Pipeline & Breadcrumbs Engine"

#### Deskripsi Misi
Anda diminta membangun modul routing inti untuk platform enterprise multi-tenant. Modul ini harus mampu menangani rute hierarkis yang dalam, validasi permission berlapis, dan pembuatan metadata navigasi (breadcrumbs dinamis) secara otomatis.

#### Kriteria Spesifikasi Teknis:
1. **Dynamic Breadcrumbs Generator:**
   - Bangun composable `useBreadcrumbs()` yang membaca hierarki `matched` routes (`route.matched`) secara reaktif.
   - Mendukung label statis dari `route.meta.breadcrumb` maupun label dinamis yang dievaluasi dari parameter rute (contoh: `/organizations/:orgId/projects/:projectId` menghasilkan label nama organisasi dan nama proyek yang sebenarnya).
2. **Composable Guard Pipeline:**
   - Jangan tumpuk puluhan `if/else` di satu file `router.beforeEach`.
   - Buat fungsi guard chainable:
     - `authGuard`: Validasi keberadaan session.
     - `tenantGuard`: Memastikan tenant aktif sesuai URL subdomain/param.
     - `roleGuard`: Memeriksa kecukupan permission berdasarkan `route.meta.permissions`.
3. **Automated Title and Telemetry Injector:**
   - Mengubah `document.title` sesuai pola: `[Nama Route] | Enterprise Cloud Platform`.
   - Memicu event telemetri performa rute pada `afterEach` yang mengukur durasi resolusi navigasi.

#### Contoh Kerangka Kerja Guard Pipeline (`src/router/guards/pipeline.ts`):
```typescript
import type { RouteLocationNormalized, NavigationGuardNext } from 'vue-router';

export type PipelineGuard = (
  to: RouteLocationNormalized,
  from: RouteLocationNormalized
) => Promise<boolean | string | object | void> | boolean | string | object | void;

export function createGuardPipeline(guards: PipelineGuard[]) {
  return async (to: RouteLocationNormalized, from: RouteLocationNormalized) => {
    for (const guard of guards) {
      const result = await guard(to, from);
      // Jika guard mengembalikan false atau rute redirect (string/object), stop pipeline
      if (result === false || typeof result === 'string' || typeof result === 'object') {
        return result;
      }
    }
    return true;
  };
}
```

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan checklist ini untuk mengukur kesiapan Anda sebelum melangkah ke topik state management tingkat lanjut dan integrasi arsitektur frontend skala besar:

- [ ] Saya memahami perbedaan arsitektur antara HTML5 Web History dan Hash History serta konfigurasi server web yang diwajibkannya.
- [ ] Saya memahami lifecycle lengkap eksekusi navigasi Vue Router (`beforeRouteLeave` -> `beforeEach` -> `beforeRouteUpdate` -> `beforeEnter` -> `beforeRouteEnter` -> `beforeResolve` -> `afterEach`).
- [ ] Saya tidak lagi menggunakan callback `next()` pada Vue Router 4 dan beralih sepenuhnya ke pengembalian nilai (`return true | false | RouteLocationRaw`).
- [ ] Saya memahami bahaya *component reuse* pada rute dinamis dan tahu kapan harus menggunakan `watch(route)` vs `:key="$route.fullPath"`.
- [ ] Saya mampu mendeklasikan type augmentation untuk `RouteMeta` di TypeScript secara aman dan terstruktur.
- [ ] Saya mampu mendeteksi dan menangani `NavigationFailure` secara programatik untuk mencegah silent errors.
- [ ] Saya memahami teknik proteksi kehilangan data formulir menggunakan `onBeforeRouteLeave` yang dikombinasikan dengan modal konfirmasi asinkron.
- [ ] Saya memiliki strategi mitigasi insiden chunk 404 pasca deployment produksi menggunakan `router.onError`.
