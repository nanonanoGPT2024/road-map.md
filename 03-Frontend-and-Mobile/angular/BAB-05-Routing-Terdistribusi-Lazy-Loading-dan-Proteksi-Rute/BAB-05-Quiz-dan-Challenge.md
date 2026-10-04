# BAB 05: Quiz, Challenge, & Knowledge Check
**Routing Terdistribusi, Lazy Loading, dan Proteksi Rute**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Standalone Components Route Tree vs. Legacy Module Routing
Jelaskan transformasi mendasar dari arsitektur routing Angular berbasis `RouterModule.forChild()` ke pendekatan modern *Standalone Routing* (`provideRoutes` / inline route arrays). Bagaimana *underlying build toolchain* (seperti Vite/ESBuild pada Angular modern) memetakan `loadComponent` dan `loadChildren` dengan dynamic import (`() => import(...)`) ke dalam physical bundle chunking yang berbeda, dan apa pengaruhnya terhadap eliminasi dead-code (*tree-shaking*) pada shared utility code yang diimpor oleh rute tersebut?

### Soal 1.2: Anatomi dan Siklus Eksekusi Functional Route Guards
Angular beralih dari *Class-based Guards* (implementasi interface `CanActivate`) ke *Functional Guards* (`CanActivateFn`). Analisis bagaimana *dependency injection context* dipelihara dalam functional guards melalui fungsi `inject()`. Apa yang terjadi secara internal jika sebuah guard memicu async operation (berupa `Observable` atau `Promise`) yang tidak pernah complete (`never emits / hangs`) terhadap *Navigation Lifecycle* dan memory heap aplikasi?

### Soal 1.3: Perilaku Snapshot vs. Observable pada ActivatedRoute
Bandingkan secara komparatif konsumsi state routing menggunakan `route.snapshot.paramMap` versus `route.paramMap.subscribe()` (atau Signal-based input routing via `withComponentInputBinding()`). Identifikasi skenario arsitektur rute di mana penggunaan `snapshot` secara pasti menghasilkan *stale data* atau UI bug ketika navigasi dilakukan antar child-path yang menggunakan komponen yang sama (*route reuse*).

### Soal 1.4: Preloading Strategies dan Trade-Off Bandwidth
Jelaskan mekanisme kerja interface `PreloadingStrategy` pada Angular. Bandingkan profil performa runtime antara `NoPreloading`, `PreloadAllModules`, dan custom strategy berbasis *Network Information API* (`navigator.connection.saveData` atau koneksi 2G/3G). Bagaimana engine routing menentukan prioritas thread utama browser saat proses preloading resource lazy-loaded dijalankan bersamaan dengan inisialisasi thread rendering aktif?

### Soal 1.5: Resolver Lifecycle dan Dampak terhadap Perceived Performance
Analisis secara kronologis posisi eksekusi `ResolveFn` dalam *Angular Navigation Transition pipeline*. Mengapa perancangan aplikasi berskala enterprise modern cenderung meninggalkan pattern "Resolver-blocks-navigation" dan beralih ke pattern "Optimistic navigation with component-level skeleton loading states"? Evaluasi trade-off arsitektur kedua pendekatan tersebut dari perspektif *Core Web Vitals* (terkhusus metric LCP dan INP).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: CanActivate vs. CanMatch dalam Dynamic Bundle Protection
Dua buah rute didefinisikan dengan path yang sama (`path: 'dashboard'`), satu untuk role `Admin` dan satu untuk role `User`. Mengapa penggunaan `CanActivateFn` pada skenario ini merupakan *anti-pattern* dan rentan membocorkan bundle code, sedangkan `CanMatchFn` adalah solusi yang presisi secara arsitektural? Jelaskan mekanisme internal router pipeline dalam melakukan traversal pada rute berikutnya ketika `CanMatchFn` mengembalikan nilai `false`.

### Soal 2.2: Diagnostik Navigation Cancellation & Infinite Redirect Loops
Perhatikan kondisi di mana sebuah guard memicu pengalihan rute melalui `Router.parseUrl()` atau instansiasi `RedirectCommand`.
```typescript
// Skenario Kode:
export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  
  if (!authService.isAuthenticated()) {
    return new RedirectCommand(router.parseUrl('/login?redirect=' + state.url), {
      skipLocationChange: false
    });
  }
  return true;
};
```
Jika rute `/login` juga secara tidak sengaja terdaftar di bawah subtree yang menerapkan `authGuard`, bagaimana router internal mendeteksi atau gagal mendeteksi loop tersebut? Event apa saja yang dipancarkan oleh `Router.events` selama proses ini, dan bagaimana strategi debugging berbasis `withDebugTracing()` untuk mengisolasi titik terminasi navigasi?

### Soal 2.3: Race Conditions pada Router-Driven State Management
Sebuah aplikasi memantau `router.events` untuk menyinkronkan global application state (misal: Redux/NgRx Store atau custom Signals Store) menggunakan event `NavigationEnd`. Jika terjadi kondisi di mana pengguna mengklik navigasi dari Route A ke Route B, namun sebelum Route B selesai resolve, pengguna membatalkan dan mengklik Route C:
1. Bagaimana urutan sequence emission `NavigationStart`, `NavigationCancel`, dan `NavigationError`?
2. Bagaimana Anda mencegah mutasi state yang usang (*out-of-order execution*) jika data-fetching pada Route B dijalankan di background tanpa lifecycle cancellation token?

### Soal 2.4: Hierarchical Route Matchers dan Matrix Parameters
Jelaskan limitasi dari built-in URL matching engine Angular (konfigurasi `path` standar berbasis regex internal). Kapan implementasi custom `UrlMatcher` mutlak diperlukan dalam distributed routing? Berikan analisis teknis bagaimana router membedakan dan mem-parse *Query Parameters* (`?key=val`), *Matrix Parameters* (`;key=val`), dan *Path Parameters* (`:id`) dalam konteks shared micro-frontends atau isolated nested router contexts.

### Soal 2.5: Isolasi Context pada CanDeactivate dengan Unsaved Form Changes
Pada implementasi `CanDeactivateFn<T>`, guard membutuhkan akses terhadap instance internal komponen target form (`T`).
1. Bagaimana cara mendesain generic interface `HasUnsavedChanges` agar guard tidak coupled secara langsung dengan kelas komponen konkret?
2. Apa yang terjadi secara internal terhadap browser history popstate ketika pengguna menekan tombol *Browser Back Button*, memicu `CanDeactivateFn` yang mengembalikan `false`? Bagaimana Angular me-restore posisi URL stack browser tanpa memicu refetch rute sebelumnya?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Performa pada Enterprise Resource Planning (ERP) Multi-Region
*Konteks Sistem:*  
Sebuah aplikasi ERP skala besar mengalami degradasi performa dramatis. Aplikasi memiliki lebih dari 150 sub-rute fungsional. Laporan APM (Application Performance Monitoring) menunjukkan bahwa Time to Interactive (TTI) di jaringan kantor regional (low-bandwidth) mencapai 8,4 detik, dan initial bundle download membengkak hingga 12MB. 

*Temuan Investigasi:*  
Ditemukan bahwa seluruh module diimpor secara distributed melalui file-file routing terpisah, tetapi pada root `app.routes.ts`, terdapat shared services barrel-file (`index.ts`) yang diimpor oleh routing guard global. Selain itu, developer menggunakan custom dynamic route injector yang memanipulasi `router.resetConfig()` secara real-time setiap kali profil user di-load.

*Pertanyaan Diagnostik:*
1. Mengapa keberadaan shared barrel-file pada guard global dapat merusak code splitting pada lazily-loaded routes meskipun routes tersebut sudah menggunakan `loadChildren`?
2. Analisis dampak arsitektural dan lifecycle cost dari penggunaan `router.resetConfig()` pada production environment. Mengapa pendekatan ini destruktif terhadap Router Tree memoization dan route-matching cache?
3. Rancang rencana remediasi arsitektur routing modular berbasis distributed feature routes yang mempertahankan pemisahan chunk bundle dan sepenuhnya kompatibel dengan modern Angular build optimizer.

---

### Skenario B: Race Condition dan Silent Data Loss pada Multi-Step Financial Underwriting Wizard
*Konteks Sistem:*  
Sistem underwriting asuransi multi-step (Route: `/apply/step-1` s.d. `/apply/step-5`) mengizinkan nasabah berpindah-pindah antar step melalui sidebar navigation stepper. Setiap step memiliki auto-save form mechanism yang terpicu via `CanDeactivateFn` atau form value changes debounce.

*Insiden:*  
Banyak data isian nasabah pada Step 2 tertimpa secara acak oleh data Step 3, atau hilang sepenuhnya (*silent loss*). Logs menunjukkan bahwa underwriting agent melakukan klik navigasi dengan sangat cepat antar step saat verifikasi dokumen. 

*Temuan Investigasi:*  
Implementasi `CanDeactivateFn` mengeksekusi asynchronous HTTP PATCH untuk menyimpan snapshot form sebelum navigasi diizinkan (`return http.patch(...).pipe(mapTo(true))`). Ketika user mengklik Step 3 lalu seketika mengklik Step 4, navigasi pertama di-cancel oleh Angular Router, tetapi HTTP request auto-save Step 2 masih in-flight di jaringan, dan responnya kembali setelah form model Step 4 aktif di memori klien.

*Pertanyaan Diagnostik:*
1. Uraikan anatomy bug race condition ini berdasarkan interaksi antara *Router Navigation Cancellation* dan *RxJS HTTP execution context*.
2. Bagaimana Anda mengimplementasikan mekanisme pembatalan mutasi async in-flight secara deterministik saat `CanDeactivateFn` dilewati atau dibatalkan?
3. Desain arsitektur transactional routing state yang menjamin integritas data (tidak ada data loss atau data overwrite) saat transisi rute dipicu secara konkurensi tinggi.

---

### Skenario C: Dynamic RBAC Routing Architecture vs. Client-Side Security Obfuscation
*Konteks Sistem:*  
Perusahaan fintech membangun platform SaaS dengan model multi-tenancy. Terdapat 4 tier pengguna: `Viewer`, `Operator`, `Compliance Officer`, dan `SuperAdmin`. Tim sekuritas melakukan audit penetrasi dan menemukan bahwa rute `/admin/audit-logs` dan source code javascript untuk bundle compliance logs dapat diunduh langsung oleh akun `Viewer` hanya dengan menebak file hash URL di network tab atau dengan memanipulasi local state di browser console.

*Temuan Tim Developer:*  
Developer berargumen bahwa mereka sudah memasang guard:
```typescript
{
  path: 'admin',
  canActivate: [RoleGuard],
  loadChildren: () => import('./admin/admin.routes')
}
```
RoleGuard memvalidasi token JWT di local storage. Jika token role adalah `Viewer`, rute melempar redirect ke `/unauthorized`. Namun, file chunk JS untuk `admin.routes` tetap terunduh di browser console via Network log segera setelah URL `/admin` diakses atau dipicu oleh preloading strategy.

*Pertanyaan Diagnostik:*
1. Mengapa `canActivate` secara fundamental gagal melindungi kerahasiaan kekayaan intelektual (source code bundle) dari client yang tidak terotorisasi?
2. Jelaskan bagaimana Anda merekayasa ulang arsitektur routing distributed ini menggunakan kombinasi `CanMatchFn`, dynamic host module delivery, dan secure CDN endpoint strategy untuk memastikan *zero bundle leakage* bagi user non-admin.
3. Bahas batasan filosofis dan teknis dari keamanan berbasis Client-Side Routing: Apa tanggung jawab mutlak yang tidak boleh dialihkan dari Backend API ke Angular Route Guards?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Multi-Tenant Routing Engine dengan Resilient Route Guards, Predictive Preloading, dan Zero-Flicker Transitions

#### Problem Statement
Anda ditugaskan merancang core routing infrastructure untuk platform perbankan global (SaaS). Sistem harus melayani tenancy publik (Retail Banking) dan internal (Corporate Treasury) dalam single-page application yang sama. Kebutuhan utamanya adalah: segmentasi bundle mutlak antar tenancy, dynamic permissions-based routing berbasis lazy loading murni, proteksi formulir transaksi berisiko tinggi tanpa data loss, dan predictive resource preloading yang adaptif terhadap konektivitas jaringan pengguna.

#### Requirements
1. **Dynamic Architecture & Distributed Route Manifest:**
   - Pisahkan routes menjadi isolated feature libraries/files tanpa referensi silang: `public.routes.ts`, `corporate.routes.ts`, dan `auth.routes.ts`.
   - Gunakan pendekatan modern standalone routing (tanpa `NgModule`).
2. **Deterministic Route Security via `CanMatchFn` & `CanActivateFn`:**
   - Implementasikan `corporateAccessMatchGuard` (`CanMatchFn`) yang secara absolut mencegah chunk JS corporate di-download jika JWT/Session context tidak memiliki claim `TENANT_CORPORATE`.
   - Rancang functional authentication fallback redirector menggunakan model `RedirectCommand` yang menyimpan original attempt target (termasuk query parameters dan dynamic fragments) untuk auto-resume pasca autentikasi.
3. **Resilient Form Deactivation Engine (`CanDeactivateFn`):**
   - Bangun generic guard `pendingChangesGuard` yang dapat menangani interface:
     ```typescript
     export interface ComponentCanDeactivate {
       canDeactivate: () => boolean | Observable<boolean> | Promise<boolean>;
       isDirty: () => boolean;
       discardChanges?: () => void;
     }
     ```
   - Guard harus memicu konfirmasi dialog (UI berbasis modal/dialog stream) dan memiliki fail-safe: jika navigasi browser terinterupsi/dibatalkan, form model lokal harus tetap berada dalam state terisolasi tanpa memory leak.
4. **Adaptive Predictive Preloader:**
   - Buat implementasi custom class `AdaptiveNetworkPreloadingStrategy implements PreloadingStrategy`.
   - Engine hanya boleh melakukan preloading jika:
     - Route metadata secara eksplisit menandai `data: { preload: true }`.
     - Device network state (`navigator.connection`) bukan berstatus `save-data: true` dan memiliki effective connection type `4g`.
   - Tambahkan idle-time execution wrapper menggunakan `requestIdleCallback` (dengan polyfill fallback) agar proses dynamic import tidak memblokir main-thread frame budget (16.6ms).

#### Constraints
* **Framework Version:** Angular v17+ (wajib menggunakan functional guards dan standalone APIs).
* **Bundle Rules:** Tidak boleh ada dependency cycles (`madge --circular` must pass). Root routing configuration tidak boleh mengimpor langsung komponen dari child features (wajib dynamic import).
* **Memory & Event Safety:** Tidak boleh ada subscription yang *leaking* pada router events atau navigation cancellation.

#### Expected Output
1. File `app.routes.ts` yang mendefinisikan hierarchical route tree terdistribusi dengan lazy loading murni.
2. File `security.guards.ts` yang memuat `corporateAccessMatchGuard` dan `authRedirectGuard`.
3. File `unsaved-changes.guard.ts` yang memuat interface dan implementasi functional `CanDeactivateFn` yang decoupled dan async-safe.
4. File `adaptive-preloading.strategy.ts` yang memuat logika network-aware preloader berbasis `PreloadingStrategy`.
5. Ringkasan arsitektural (maksimal 200 kata) yang menguraikan alur resolusi navigasi mulai dari URL match pertama hingga render view berhasil.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara `CanActivateFn` (evaluasi pasca-resolusi chunk) dan `CanMatchFn` (evaluasi pra-resolusi chunk bundle).
- [ ] Dampak lifecycle `ResolveFn` terhadap metrik LCP (Largest Contentful Paint) dan strategi mitigasi menggunakan deferred loading / skeleton states.
- [ ] Mekanisme Router Tree parsing: traversal, matching precedence, wildcard (`**`) ordering, dan hierarchical inheritance params (`paramsInheritanceStrategy`).
- [ ] Dynamic component input binding dari route parameters (`withComponentInputBinding`) dan siklus reaktivitasnya via Angular Signals.
- [ ] Internal lifecycle events sequence (`NavigationStart`, `RoutesRecognized`, `GuardsCheckStart`, `GuardsCheckEnd`, `ResolveStart`, `ResolveEnd`, `NavigationEnd`, `NavigationCancel`, `NavigationError`).
- [ ] Bagaimana ESBuild/Webpack memecah code boundary via `loadChildren: () => import(...)` dan mengapa barrel files merusak isolasi bundle tersebut.
- [ ] Implementasi functional guard berbasis Context Injection (`inject()`, `runInInjectionContext`).

### Saya tidak perlu menghafal:
- [ ] Seluruh signature method deprecated dari class-based interfaces (`CanActivate`, `CanActivateChild`, `Resolve`, dll.).
- [ ] Struktur internal implementasi Regex dari default URL parser parser Angular.
- [ ] Urutan property numerik internal dari enum `NavigationCancellationCode`.

### Saya harus bisa melakukan:
- [ ] Mengonversi route tree monolithic legacy berbasis NgModule menjadi arsitektur modular standalone yang terdistribusi secara decoupled.
- [ ] Membangun custom functional guards berkemampuan redirect menggunakan `RedirectCommand` dan memitigasi infinite navigation loop.
- [ ] Menulis custom `PreloadingStrategy` yang adaptif terhadap kapasitas komputasi perangkat dan bandwidth koneksi pengguna.
- [ ] Mengimplementasikan async-safe `CanDeactivateFn` generic untuk form multi-step yang mencegah race condition saat navigasi dibatalkan.
- [ ] Mendebug navigation stall, route reject, dan error cancellation menggunakan `withDebugTracing()` dan Router Event telemetry streams.
- [ ] Mengonfigurasi Dynamic Matched Routes untuk arsitektur Multi-Tenant yang aman dari kebocoran chunk code di level browser.