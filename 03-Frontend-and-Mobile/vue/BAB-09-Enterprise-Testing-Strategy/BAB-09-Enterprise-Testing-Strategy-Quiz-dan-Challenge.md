# BAB-09-Enterprise-Testing-Strategy: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi komprehensif untuk menguji pemahaman arsitektural dan implementasi praktis terkait enterprise testing strategy pada ekosistem Vue 3. Evaluasi mencakup Unit Testing (Vitest), Component Testing (Vue Test Utils), Store & State Isolation (Pinia), Network Mocking (Mock Service Worker / MSW), End-to-End Testing (Playwright), hingga orkestrasi CI/CD Quality Gates.

---

## Bagian 1: 5 Basic Questions

### 1. Apa perbedaan mendasar antara `shallowMount` dan `mount` pada Vue Test Utils, serta kapan `shallowMount` berpotensi menimbulkan *false positive*?
**Jawaban & Penjelasan Teknis:**
- `mount` me-render komponen target beserta seluruh hierarki child component secara rekursif (full DOM tree). Komponen anak dieksekusi siklus hidupnya (`setup`, `mounted`) dan template-nya dirender secara utuh.
- `shallowMount` me-render komponen target namun me-replace semua child component dengan stub element (dummy placeholder `<component-stub>`).
- **Potensi False Positive:** `shallowMount` mengisolasi komponen target dari bug anak, namun dapat meloloskan tes (*false positive*) saat komponen target bergantung pada side-effect child component (misalnya child meng-emit event tertentu saat mount, menginjeksi provide/inject contract, atau mutasi DOM slot spesifik). Komponen terlihat lulus uji secara terisolasi padahal integrasi antarkomponen rusak di runtime.

---

### 2. Mengapa pemanggilan `await wrapper.setValue(...)` atau mutasi state reaktif membutuhkan mekanisme asynchronous (`await nextTick()` / `flushPromises()`) sebelum melakukan assertion?
**Jawaban & Penjelasan Teknis:**
Vue mengimplementasikan asynchronous DOM update queue. Ketika properti reaktif bermutasi (`ref`, `reactive`), Vue tidak langsung memperbarui DOM secara sinkron, melainkan membungkus perubahan dalam scheduler queue (`microtask` batching) untuk efisiensi rendering. 
- `wrapper.setValue()` atau trigger event mengembalikan Promise yang menunggu `nextTick()`.
- Jika assertion DOM dijalankan secara sinkron langsung setelah mutasi non-wrapper, DOM belum selesai di-patching.
- `flushPromises()` dari `@vue/test-utils` menyelesaikan semua pending Promise (termasuk microtask queue dari network call atau debounce macro/microtask) sehingga state reaktif dan DOM sinkron sepenuhnya sebelum assertion dievaluasi.

---

### 3. Dalam pengujian composable independen, mengapa fungsi pembungkus seperti `withSetup()` sering dibutuhkan jika composable menggunakan lifecycle hook atau dependency injection?
**Jawaban & Penjelasan Teknis:**
Composable yang mengeksekusi `onMounted`, `onUnmounted`, `provide`, atau `inject` membutuhkan *active Vue component instance* yang terikat ke thread eksekusi `getCurrentInstance()`. Jika composable dipanggil langsung sebagai fungsi JavaScript biasa di luar konteks komponen:
```ts
// Akan melempar warning/error: "onMounted is called when there is no active component instance"
const { data } = useMyComposable();
```
`withSetup()` membungkus composable di dalam dummy host component (`defineComponent({ setup() { ... } })`) yang di-mount menggunakan `mount()`, menyediakan runtime lifecycle context dan context injection host yang valid.

---

### 4. Mengapa penggunaan `setActivePinia(createPinia())` wajib dieksekusi di blok `beforeEach()` saat menguji Pinia store atau komponen yang mengonsumsi Pinia?
**Jawaban & Penjelasan Teknis:**
Pinia menggunakan singleton instance secara default di memory runtime. Tanpa reset eksplisit di `beforeEach()`:
1. State yang dimutasi pada Test Case A akan terbawa (*state bleed* / cross-test contamination) ke Test Case B.
2. Plugin dan subscription yang terdaftar di test sebelumnya tetap aktif.
3. Menjalankan `setActivePinia(createPinia())` menjamin instansiasi Pinia root yang segar (*clean slate*) untuk setiap unit tes, mencegah flaky tests akibat *inter-dependency state*.

---

### 5. Apa perbedaan peran arsitektural antara Unit Test, Integration Test, dan End-to-End (E2E) Test dalam piramida pengujian aplikasi enterprise Vue 3?
**Jawaban & Penjelasan Teknis:**
- **Unit Test (Vitest):** Memverifikasi unit terkecil kode (pure functions, utility composables, isolasi kalkulasi matematis/bisnis) tanpa dependensi eksternal. Sangat cepat, deterministik, dan berbiaya eksekusi rendah.
- **Integration/Component Test (Vitest + Vue Test Utils + MSW):** Memverifikasi kolaborasi antar unit: template Vue, interaksi komponen dengan Pinia store, form validation, dan integrasi HTTP network mock via MSW. Menjamin kontrak antar-lapisan bekerja sesuai spesifikasi.
- **End-to-End (E2E) Test (Playwright):** Menguji aplikasi dari sudut pandang pengguna akhir di lingkungan browser nyata (Chromium, Firefox, WebKit). Memvalidasi user journey kritis (checkout, otentikasi OAuth, navigasi router, rendering CSS) terhadap backend staging atau containerized mock services.

---

## Bagian 2: 5 Intermediate Questions

### 1. Bagaimana strategi mencegah leaking instance dan dangling timers saat menguji komponen yang menggunakan `setInterval` atau debounce logic di Vitest?
**Jawaban & Penjelasan Teknis:**
Saat menguji timer atau debounce:
1. Aktifkan fake timers via `vi.useFakeTimers()` di `beforeEach()`.
2. Jangan biarkan timer menggantung ke test berikutnya; jalankan `vi.clearAllTimers()` dan kembalikan timer native dengan `vi.useRealTimers()` di `afterEach()`.
3. Panggil `wrapper.unmount()` di `afterEach()` untuk memicu lifecycle `onBeforeUnmount` / `onUnmounted` pada komponen agar pembersihan listener atau `clearInterval` native komponen dieksekusi.
4. Gunakan `vi.advanceTimersByTime(ms)` atau `vi.runOnlyPendingTimers()` untuk memajukan waktu virtual secara presisi daripada mengandalkan `setTimeout` riil yang memperlambat execution pipeline dan memicu flakiness.

---

### 2. Mengapa Mock Service Worker (MSW) lebih direkomendasikan daripada mocking Axios/Fetch global (`vi.spyOn(axios, 'get')`) dalam Enterprise Integration Testing?
**Jawaban & Penjelasan Teknis:**
- **Boundary Mocking vs Implementation Mocking:** Mem-mock `axios.get` atau `fetch` mengikat tes pada detail implementasi library HTTP client. Jika arsitektur beralih dari Axios ke Fetch native atau `ofetch`, seluruh mock test akan rusak (*high coupling*).
- **Network Level Interception:** MSW mencegat network request di lapisan jaringan nyata (Service Worker di browser atau Node.js `undici`/`http` interceptor). 
- **Fidelitas Kontrak:** MSW menguji keseluruhan stack client: interceptor token otentikasi, serializer header, transformer query params, error handling status code (401, 403, 500), dan response parsing secara realistis tanpa mock tiruan method internal.

---

### 3. Dalam pengujian Vue Router v4, bagaimana pendekatan ideal antara menggunakan `createRouter` riil (in-memory history) versus mocking `useRouter` / `useRoute` via `vi.mock`?
**Jawaban & Penjelasan Teknis:**
- **Gunakan `createRouter` dengan `createMemoryHistory()`** ketika menguji alur integrasi navigasi nyata, guards (`beforeEach`), breadcrumbs dinamis, atau komponen yang perilakunya berubah berdasarkan rute aktif dan redirect logic. Ini memvalidasi ekosistem routing secara utuh tanpa membuka URL browser fisik.
- **Gunakan Mocking (`vi.mock('vue-router')` atau inject mock router object)** jika komponen target hanya membaca satu parameter statis (misal `route.params.id`) atau memicu navigasi satu baris (`router.push('/dashboard')`), dan fokus pengujian murni pada presentational logic komponen tersebut. Mocking di level ini menghemat alokasi memori dan overhead setup router.

---

### 4. Bagaimana cara mengisolasi dan menguji custom directive pada Vue 3 (misalnya `v-permission="'ADMIN'"`) tanpa harus me-mount aplikasi root penuh?
**Jawaban & Penjelasan Teknis:**
Custom directive dapat diuji secara terisolasi dengan me-mount host component sederhana via `mount()` dan mendaftarkan directive tersebut di konfigurasi `global.directives`:
```ts
import { mount } from '@vue/test-utils';
import { permissionDirective } from '@/directives/permission';

const createWrapper = (role: string) => {
  return mount({
    template: `<button v-permission="'ADMIN'">Panel Admin</button>`,
  }, {
    global: {
      directives: { permission: permissionDirective },
      provide: { userRole: role } // atau inject context store
    }
  });
};
```
Assertion dilakukan dengan memeriksa apakah elemen target dihapus dari DOM (`wrapper.find('button').exists() === false`) atau diberikan attribute `disabled`/`hidden` sesuai spesifikasi implementasi directive.

---

### 5. Apa kelemahan metrik Line/Statement Coverage dalam Code Coverage Report, dan mengapa Branch/Path Coverage lebih krusial untuk aplikasi enterprise?
**Jawaban & Penjelasan Teknis:**
- **Line Coverage** hanya menandai apakah suatu baris kode tereksekusi setidaknya satu kali. Satu baris kode yang mengandung complex ternary operator atau logical short-circuiting:
  ```ts
  const status = isValid && isAuthorized ? 'APPROVED' : 'REJECTED';
  ```
  bisa mendapatkan skor line coverage 100% hanya dengan satu test case yang mengevaluasi skenario `APPROVED`, padahal cabang `REJECTED` atau kombinasi `isValid=false, isAuthorized=true` belum pernah diuji sama sekali.
- **Branch/Path Coverage** mengukur seluruh kemungkinan jalur percabangan logika Boolean (`if/else`, `switch/case`, optional chaining `?.`, nullish coalescing `??`). Dalam arsitektur enterprise, kegagalan menangani salah satu branch kondisi edge-case adalah penyebab utama runtime unhandled exception di produksi.

---

## Bagian 3: 3 Skenario Kasus Nyata Produksi

### Skenario 1: Memory Leak dan Process Timeout pada CI Pipeline Akibat Unhandled Asynchronous Microtasks di Vitest
**Konteks Masalah:**
Pada repositori monorepo dengan 1.200 unit test komponen Vue, build runner GitHub Actions sering mengalami status *exit code 137 (Out of Memory)* atau *Job Timeout 60 menit*. Saat dijalankan secara lokal di mesin developer, tes lulus normal namun memakan memori hingga 14 GB RAM.

**Investigasi Akar Masalah:**
1. Banyak komponen menggunakan `MutationObserver`, WebSockets, atau long-polling request di dalam composable.
2. Wrapper komponen di-mount di blok `it()` tanpa pemanggilan `wrapper.unmount()` di `afterEach()`.
3. Event listener pada `window` atau interval timer tetap hidup di memori runtime Node.js antar-test file, menyebabkan garbage collector gagal merebut memori (retained DOM references).

**Solusi & Remediasi Arsitektur:**
1. **Enforce Cleanup Hook:**
   Konfigurasi Vitest global setup (`tests/setup.ts`) untuk melakukan teardown otomatis:
   ```ts
   import { afterEach } from 'vitest';
   import { config } from '@vue/test-utils';

   afterEach(() => {
     // Membersihkan wrapper global jika didaftarkan
     vi.clearAllMocks();
     vi.restoreAllMocks();
   });
   ```
2. **Lifecycle Explicit Unmount:**
   Pastikan setiap custom composable yang mendaftarkan event listener pada `window`/`document` menggunakan `onScopeDispose()` atau `onUnmounted()` untuk me-remove listener, dan tes wajib memanggil `wrapper.unmount()`.
3. **Vitest Pool & Isolation Tuning:**
   Atur konfigurasi pool di `vitest.config.ts` untuk membatasi fork thread dan isolasi memori:
   ```ts
   export default defineConfig({
     test: {
       pool: 'threads',
       poolOptions: {
         threads: {
           minThreads: 2,
           maxThreads: 4,
           isolate: true,
         },
       },
       teardownTimeout: 5000,
     }
   });
   ```

---

### Skenario 2: Cross-Test State Leakage pada Pinia Store dalam Suite Pengujian Monorepo E-Commerce
**Konteks Masalah:**
Sebuah tim menguji komponen `CartSummary.vue` dan `CheckoutPayment.vue`. Ketika test dijalankan secara acak (`--shuffle`), pengujian `CheckoutPayment.vue` sering gagal pada assertion:
`expect(cartStore.totalItems).toBe(0)` yang mengembalikan nilai `3`.

**Investigasi Akar Masalah:**
Test case sebelumnya (`CartSummary.spec.ts`) memanggil action `cartStore.addItem(...)`. Store diinisialisasi di level modul luar `describe()`:
```ts
// KESALAHAN FATAL: Single instance dibagi ke seluruh scope test file
const store = useCartStore();

describe('Cart Tests', () => {
  it('adds item', () => {
    store.addItem({ id: 1, name: 'Item A' });
  });
});
```
Meskipun `setActivePinia` dipanggil di `beforeEach`, instance store yang disimpan pada variabel global file tetap merujuk ke reference objek store lama atau instance Pinia yang tidak ter-reset secara modular.

**Solusi & Remediasi Arsitektur:**
1. Jangan pernah menginstansiasi store di top-level file di luar siklus `beforeEach()` / `it()`.
2. Selalu bungkus instansiasi store di dalam fungsi pembantu atau panggil di dalam test case setelah Pinia di-reset:
   ```ts
   describe('CheckoutPayment.vue', () => {
     let cartStore: ReturnType<typeof useCartStore>;

     beforeEach(() => {
       setActivePinia(createPinia());
       cartStore = useCartStore();
     });

     it('starts with empty cart', () => {
       expect(cartStore.totalItems).toBe(0);
     });
   });
   ```

---

### Skenario 3: Flaky E2E Tests pada Playwright Akibat Animasi CSS Transitions dan Hydration Race Condition
**Konteks Masalah:**
Pada pipeline E2E testing menggunakan Playwright, skenario "User submit form checkout dan modal konfirmasi muncul" menghasilkan tingkat kegagalan acak sebesar 18% di CI. Error log menunjukkan:
`locator.click: Target closed` atau `Element is not clickable at point (500, 300) because another element <div class="fade-overlay"> obscures it`.

**Investigasi Akar Masalah:**
1. Developer menggunakan arbitrary sleep / delay: `await page.waitForTimeout(1000)`. Durasi ini tidak deterministik pada CPU runner CI yang memiliki variasi beban kerja tinggi.
2. Vue `<Transition>` modal checkout memiliki durasi animasi CSS 300ms. Tombol konfirmasi diklik saat overlay backdrop masih berada dalam fase interpolasi animasi `opacity` atau `pointer-events`.
3. Komponen belum sepenuhnya terhidrasi di sisi client saat server-side rendered (SSR/Nuxt) halaman pertama kali dimuat.

**Solusi & Remediasi Arsitektur:**
1. **Hapus Seluruh Fixed Timeout:** Ganti `page.waitForTimeout()` dengan state assertion berbasis locator.
2. **Disable Animasi pada Environment E2E Testing:**
   Konfigurasi Playwright untuk menyuntikkan CSS pencegah animasi saat pengujian:
   ```ts
   test.use({
     reducedMotion: 'always',
   });
   ```
   Atau inject styling:
   ```css
   *, *::before, *::after {
     transition-duration: 0s !important;
     animation-duration: 0s !important;
   }
   ```
3. **Auto-Waiting Locators dengan Web-First Assertions:**
   Gunakan locator berantai yang menunggu elemen stabil dan clickable:
   ```ts
   const confirmBtn = page.getByRole('button', { name: 'Konfirmasi Pembayaran' });
   await expect(confirmBtn).toBeVisible();
   await expect(confirmBtn).toBeEnabled();
   await confirmBtn.click();
   ```

---

## Bagian 4: 1 Practical Chapter Challenge

### Tantangan: Implementasi Resilient Test Suite untuk Multi-Step Checkout Flow
Bangun test suite komprehensif menggunakan **Vitest**, **Vue Test Utils**, **Pinia**, dan **MSW** untuk memvalidasi alur checkout enterprise multi-step (`CheckoutWizard.vue`).

#### Spesifikasi Fitur Komponen:
1. **Step 1: Input Shipping Address**
   - Validasi form (Nama, Alamat, Kode Pos).
   - Tombol "Lanjut" hanya aktif jika form valid.
2. **Step 2: Payment Method & Dynamic Fee Calculation**
   - Mengambil metode pembayaran dari endpoint backend: `GET /api/v1/payment-methods`.
   - Mengirim kalkulasi fee ke backend: `POST /api/v1/checkout/calculate`.
   - Jika response server error 500, tampilkan banner alert error dengan tombol "Coba Lagi".
3. **Step 3: Review & Final Confirmation**
   - Menampilkan ringkasan pesanan dari Pinia store (`cartStore`).
   - Tombol "Bayar Sekarang" memicu `POST /api/v1/checkout/submit`.
   - Saat proses submit berlangsung, tombol menampilkan status loading dan dalam kondisi `disabled`.
   - Jika sukses (201 Created), emit event `checkout-completed` dengan payload `orderId`.

#### Kebutuhan Test Suite yang Wajib Diimplementasikan:
Buat file uji `tests/components/CheckoutWizard.spec.ts` dengan cakupan skenario:
1. **Unit/Component Integration Test (MSW Interception):**
   - Setup MSW server interceptor untuk mock `/api/v1/payment-methods` dan `/api/v1/checkout/submit`.
   - Simulasikan user mengisi form step 1 dan beralih ke step 2.
   - Uji skenario kegagalan jaringan (MSW merespons status 500 pada kalkulasi fee) dan verifikasi banner alert error muncul di DOM.
   - Uji skenario sukses: user menyelesaikan step 3, verifikasi button loading state, dan validasi emit event `checkout-completed`.
2. **Pinia Store Interaction:**
   - Verifikasi store `cartStore` di-query untuk data summary.
   - Pastikan store state tidak mengalami kebocoran data (*leak*) antar-test.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan checklist ini untuk memvalidasi kesiapan implementasi arsitektur testing Anda:

- [ ] **Test Architecture & Philosophy:**
  - [ ] Memahami perbedaan batasan antara Unit, Integration, dan E2E testing.
  - [ ] Tidak mengandalkan detail implementasi internal (e.g. state internal instance) dalam assertion, melainkan perilaku observable (DOM output, emitted events, network contracts).

- [ ] **Vitest & Vue Test Utils Mastery:**
  - [ ] Mampu menggunakan `mount` dengan konfigurasi global plugins, provide/inject, dan mocks secara terisolasi.
  - [ ] Memahami penanganan asynchronous Vue (`await nextTick()`, `flushPromises()`).
  - [ ] Mampu mengontrol waktu virtual via `vi.useFakeTimers()` dan mengembalikannya secara deterministik.

- [ ] **State & Network Mocking Isolation:**
  - [ ] Menerapkan `setActivePinia(createPinia())` di setiap siklus `beforeEach`.
  - [ ] Menggunakan MSW untuk Network Level Mocking alih-alih mem-patch method HTTP client secara manual.
  - [ ] Membersihkan mock dan handler MSW (`server.resetHandlers()`, `server.close()`) setelah siklus tes selesai.

- [ ] **E2E & CI/CD Quality Gates:**
  - [ ] Mengonfigurasi Playwright dengan best practices (locator role-based, auto-waiting, dynamic timeouts elimination).
  - [ ] Mencegah flaky test akibat animasi CSS, timing race condition, dan unhandled rejection.
  - [ ] Menetapkan target threshold branch coverage (>80%) pada pipeline pull request sebagai quality gate sebelum deployment produksi.
