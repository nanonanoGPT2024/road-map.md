# BAB-09-Enterprise-Testing-Strategy-Unit-Integration-dan-E2E: Quiz, Challenge, & Knowledge Check

Dokumen evaluasi mandiri ini dirancang untuk menguji penguasaan arsitektur pengujian aplikasi frontend modern skala enterprise. Mencakup Testing Trophy, Mock Service Worker (MSW), React Testing Library (RTL), Playwright E2E, Visual Regression Testing, dan CI/CD matrix optimization.

---

## Bagian 1: 5 Basic Questions

### Soal 1 (Filosofi React Testing Library)
**Pertanyaan:**
Mengapa React Testing Library (RTL) secara eksplisit tidak menyarankan (dan bahkan tidak menyediakan API mudah untuk) menguji internal state komponen (`wrapper.state()`) atau props internal child component secara langsung seperti Enzyme di masa lalu?

*Jawaban & Analisis Teknis:*
RTL dibangun berdasarkan prinsip panduan: *"The more your tests resemble the way your software is used, the more confidence they can give you."* 
Pengujian detail implementasi internal (seperti nama variabel state `isOpen`, internal ref, atau private handler) menimbulkan dua masalah fatal:
1. **False Positives:** Pengujian lolos padahal UI rusak secara visual atau aksesibilitasnya patah bagi pengguna nyata/screen reader.
2. **False Negatives:** Pengujian gagal saat developer melakukan refactoring internal (misalnya mengganti `useState` dengan `useReducer` atau XState), padahal output visual, aksesibilitas DOM, dan interaksi pengguna tidak berubah sama sekali.
RTL memaksa pengembang melakukan query berdasarkan accessibility tree (`getByRole`, `getByLabelText`, `getByText`) sehingga tes bertindak sebagai *black-box consumer*.

---

### Soal 2 (Query Priority pada DOM Testing)
**Pertanyaan:**
Urutkan prioritas selector query React Testing Library dari yang paling direkomendasikan hingga yang paling dihindari, dan jelaskan mengapa `getByTestId` berada di urutan bawah!

*Jawaban & Analisis Teknis:*
Urutan prioritas menurut standar Accessible Rich Internet Applications (ARIA) dan RTL:
1. **Queries Accessible to Everyone:**
   - `getByRole` (dengan accessible name `{ name: /submit/i }`)
   - `getByLabelText` (untuk form control)
   - `getByPlaceholderText` (fallback jika label tidak tersedia)
   - `getByText` (untuk konten non-interaktif seperti paragraf atau heading statis)
   - `getByDisplayValue` (untuk nilai input yang sudah terisi)
2. **Semantic HTML Queries:**
   - `getByAltText` (gambar), `getByTitle`
3. **Test IDs:**
   - `getByTestId`

`getByTestId` ditempatkan di prioritas paling bawah karena atribut `data-testid` bersifat *developer-only artifact*. Pengguna tunanetra dengan screen reader atau pengguna visual tidak membaca `data-testid`. Jika accessible name atau semantic role elemen berubah menjadi `div` tanpa role, `getByTestId` tetap lolos, sehingga gagal mendeteksi regresi aksesibilitas di level produksi.

---

### Soal 3 (Karakteristik Mocking: MSW vs Jest Spy)
**Pertanyaan:**
Apa keunggulan arsitektural utama menggunakan Mock Service Worker (MSW) di layer network dibandingkan melakukan monkey-patching via `jest.spyOn(global, 'fetch')` atau `vi.mock('axios')`?

*Jawaban & Analisis Teknis:*
- **MSW (Layer Intersepsi Nyata):** Bekerja pada level transport jaringan. Di lingkungan Node.js/Vitest, MSW mencegat via patch HTTP core stream (`http`/`https` module), sedangkan di browser/E2E MSW menggunakan Service Worker API nyata. Kode aplikasi memanggil `fetch` atau instance `axios` asli tanpa modifikasi implementasi adapter/interceptors.
- **`jest.spyOn` / `vi.mock` (Object-Level Patching):** Mengganti referensi modul TypeScript/JavaScript secara virtual. Hal ini sering menyembunyikan bug konfigurasi HTTP client, parsing header, serialization format, serialization cookie/auth credentials, atau custom axios middleware. MSW memberikan fleksibilitas mock terpadu yang dapat digunakan lintas test runner (Vitest, Jest, Storybook, dan Playwright browser mode).

---

### Soal 4 (Behavior `act(...)` Warning)
**Pertanyaan:**
Apa arti teknis dari warning `Warning: An update to MyComponent inside a test was not wrapped in act(...)`, dan mengapa menggunakan arbitrary delay seperti `await new Promise(r => setTimeout(r, 1000))` adalah anti-pattern dalam memperbaikinya?

*Jawaban & Analisis Teknis:*
React menggunakan `act()` untuk memastikan semua lifecycle updates, microtasks, effect hooks (`useEffect`), dan DOM re-renders telah diselesaikan dan di-flush ke DOM sebelum assertion dijalankan. Warning muncul saat sebuah promise atau asynchronous event menyelesaikan mutasi state setelah scope test sinkron selesai tanpa ditunggu oleh runner test.
Menggunakan `setTimeout` adalah anti-pattern karena:
1. Menghasilkan *flaky tests* akibat *timing race conditions* di CI runner yang berdaya komputasi rendah.
2. Memperlambat total durasi pipeline test secara artifisial.
Solusi yang benar adalah menunggu perubahan status DOM yang dapat diobservasi menggunakan utilities RTL seperti `waitFor(() => expect(...))` atau `await screen.findByRole(...)`.

---

### Soal 5 (Flakiness pada End-to-End Testing)
**Pertanyaan:**
Sebutkan 3 penyebab utama *flaky tests* pada Playwright E2E testing dan bagaimana arsitektur locator berbasis *Auto-waiting* mengatasinya!

*Jawaban & Analisis Teknis:*
Tiga penyebab utama:
1. **Network Latency & Hydration Race Condition:** DOM elemen sudah ada di HTML markup (SSR), tetapi JavaScript event handler React belum terhidrasi saat klik dieksekusi.
2. **Animasi & Transisi CSS:** Elemen sedang bergerak atau fading (`opacity < 1` / transform) sehingga posisi kalkulasi bounding-box berubah saat pointer trigger.
3. **Hard-coded sleeps (`page.waitForTimeout`):** Waktu tunggu manual yang tidak sinkron dengan kondisi state backend/rendering.

*Mekanisme Auto-waiting Playwright:*
Sebelum menjalankan aksi (seperti `.click()`, `.fill()`), locator Playwright secara otomatis menjalankan serangkaian *Actionability Checks*:
- Attached ke DOM
- Visible (tidak display: none, width/height > 0)
- Stable (tidak sedang dalam animasi transform/layout shift)
- Receives Events (tidak tertutup oleh modal backdrop atau spinner)
- Enabled (tidak disabled)

---

## Bagian 2: 5 Intermediate Questions

### Soal 1 (Testing Asynchronous React Suspense & Error Boundaries)
**Pertanyaan:**
Diberikan komponen yang menggunakan React 18/19 Suspense untuk data fetching. Tuliskan pola pengujian unit/integrasi menggunakan Vitest & RTL untuk memastikan *fallback loading skeleton* muncul lebih dulu, lalu menghilang saat data sukses di-render, serta transisi ketika terjadi rejection (Error Boundary terpancing).

*Jawaban & Analisis Teknis:*
```tsx
import { render, screen, waitForElementToBeRemoved } from '@testing-library/react';
import { http, HttpResponse, delay } from 'msw';
import { setupServer } from 'msw/node';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Suspense } from 'react';
import { ErrorBoundary } from 'react-error-boundary';
import { UserProfile } from './UserProfile';

const server = setupServer();
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function createTestWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary fallback={<div role="alert">Terjadi kesalahan sistem</div>}>
        <Suspense fallback={<div role="status">Memuat data profil...</div>}>
          {children}
        </Suspense>
      </ErrorBoundary>
    </QueryClientProvider>
  );
}

test('merender loading fallback skeleton lalu menampilkan data profil', async () => {
  server.use(
    http.get('/api/user', async () => {
      await delay(50);
      return HttpResponse.json({ id: 'USR-01', name: 'Budi Santoso' });
    })
  );

  render(<UserProfile />, { wrapper: createTestWrapper() });

  // 1. Verifikasi fallback skeleton berstatus accessible role
  expect(screen.getByRole('status')).toHaveTextContent(/memuat data profil/i);

  // 2. Tunggu fallback dilepas dari DOM
  await waitForElementToBeRemoved(() => screen.queryByRole('status'));

  // 3. Verifikasi data berhasil di-render
  expect(screen.getByRole('heading', { name: /budi santoso/i })).toBeInTheDocument();
});

test('menangkap error dan menampilkan Error Boundary saat network failure', async () => {
  server.use(
    http.get('/api/user', () => {
      return new HttpResponse(null, { status: 500 });
    })
  );

  render(<UserProfile />, { wrapper: createTestWrapper() });

  expect(await screen.findByRole('alert')).toHaveTextContent(/terjadi kesalahan sistem/i);
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});
```

---

### Soal 2 (Debounced Input & Fake Timers)
**Pertanyaan:**
Bagaimana cara menguji komponen Auto-Suggest Input yang memiliki debounce 400ms menggunakan `vi.useFakeTimers()` dan `@testing-library/user-event` tanpa menimbulkan kebocoran microtask queue atau infinite loops?

*Jawaban & Analisis Teknis:*
Secara default, `userEvent.setup()` modern bergantung pada native real timers. Jika mengombinasikan `vi.useFakeTimers()` dengan `userEvent`, inisialisasi `userEvent` harus dilakukan dengan opsi `advanceTimers: vi.advanceTimersByTime`.

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { SearchAutoComplete } from './SearchAutoComplete';

test('hanya memicu API pencarian setelah debounce period 400ms tercapai', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  const handleSearch = vi.fn();

  render(<SearchAutoComplete onSearch={handleSearch} debounceMs={400} />);

  const input = screen.getByRole('combobox', { name: /cari produk/i });

  // Input karakter bertahap
  await user.type(input, 'macbook');

  // Sebelum waktu debounce habis, handler belum boleh terpanggil
  expect(handleSearch).not.toHaveBeenCalled();

  // Majukan waktu sebesar 399ms
  vi.advanceTimersByTime(399);
  expect(handleSearch).not.toHaveBeenCalled();

  // Majukan 1ms terakhir untuk memenuhi ambang batas 400ms
  vi.advanceTimersByTime(1);
  expect(handleSearch).toHaveBeenCalledTimes(1);
  expect(handleSearch).toHaveBeenCalledWith('macbook');

  vi.useRealTimers();
});
```

---

### Soal 3 (Custom Render Pattern untuk Enterprise Context)
**Pertanyaan:**
Dalam aplikasi enterprise dengan lusinan global provider (TanStack Query, Redux/Zustand, React Router, i18next, ThemeProvider), rancang utilitas custom `render` wrapper yang modular, type-safe, dan memungkinkan override initial state untuk tiap skenario uji.

*Jawaban & Analisis Teknis:*
```tsx
import React, { ReactElement } from 'react';
import { render as rtlRender, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, InitialEntry } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore, RootState } from '@/store';

interface ExtendedRenderOptions extends Omit<RenderOptions, 'queries'> {
  preloadedState?: Partial<RootState>;
  initialRoutes?: InitialEntry[];
  queryClient?: QueryClient;
}

export function renderWithProviders(
  ui: ReactElement,
  {
    preloadedState = {},
    initialRoutes = ['/'],
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    }),
    ...renderOptions
  }: ExtendedRenderOptions = {}
) {
  const store = configureStore(preloadedState);

  function AllTheProviders({ children }: { children: React.ReactNode }) {
    return (
      <Provider store={store}>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={initialRoutes}>
            {children}
          </MemoryRouter>
        </QueryClientProvider>
      </Provider>
    );
  }

  return {
    store,
    queryClient,
    ...rtlRender(ui, { wrapper: AllTheProviders, ...renderOptions }),
  };
}

export * from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';
```

---

### Soal 4 (Playwright Network Mocking vs Real Backend HAR)
**Pertanyaan:**
Kapan tim QA/Frontend Engineer harus menggunakan `page.route()` (Mocking) versus HAR Recording/Replay pada Playwright, dan bagaimana strategi menghindari *stale mocks* saat schema backend berubah?

*Jawaban & Analisis Teknis:*
- **`page.route()` (Selective In-Memory Mocking):** Digunakan untuk skenario edge cases yang sulit direproduksi di staging (contoh: HTTP 504 Gateway Timeout, 429 Rate Limit, response payload korup, latency 10 detik).
- **HAR Recording/Replay:** Digunakan untuk isolasi deterministik dari kumpulan dataset backend yang kompleks tanpa harus menjalankan 20 microservices di runner CI.
- **Strategi Mitigasi Stale Mocks (Schema Drift):**
  1. *Contract Testing (Pact / OpenAPI Spec Validation):* Jalankan validator TypeScript/Zod pada MSW mock response dan payload response `page.route()`.
  2. *Synthetic Canary Runs:* Jadwalkan nightly E2E job di Playwright yang berjalan 100% melawan live staging environment (tanpa mocking sama sekali) untuk mendeteksi breaking changes backend lebih dini.

---

### Soal 5 (Visual Regression Testing Thresholds)
**Pertanyaan:**
Dalam implementasi visual regression testing (misalnya dengan Playwright `toHaveScreenshot()` atau Applitools), parameter apa saja yang menentukan toleransi perbedaan pixel (`maxDiffPixelRatio`, `threshold`), dan bagaimana menangani perbedaan render akibat sub-pixel font anti-aliasing di OS yang berbeda (Linux CI vs macOS Developer)?

*Jawaban & Analisis Teknis:*
1. **Parameter Kunci:**
   - `threshold`: Nilai sensitivitas warna per-pixel (0.0 sampai 1.0). Nilai default `0.2` menoleransi variasi minor saturasi warna.
   - `maxDiffPixels` / `maxDiffPixelRatio`: Batas rasio jumlah pixel yang boleh berbeda sebelum assertion dinyatakan gagal (misal `0.01` untuk toleransi 1% pixel).
2. **Penanganan Cross-Platform Anti-Aliasing Bug:**
   - **Dockerized CI Consistency:** Jalankan Playwright visual regression di dalam official Docker container (`mcr.microsoft.com/playwright`) baik di local maupun CI.
   - **CSS Font Smoothing:** Terapkan `-webkit-font-smoothing: antialiased;` dan disable animasi sebelum capture:
     ```ts
     await expect(page).toHaveScreenshot('dashboard.png', {
       animations: 'disabled',
       caret: 'hide',
       scale: 'css',
       maxDiffPixelRatio: 0.02
     });
     ```

---

## Bagian 3: 3 Skenario Kasus Nyata Produksi

### Kasus 1: "CI Hijau tapi Checkout Produksi Error 500 Akibat Payload Typo"
**Latar Belakang Kasus:**
Sebuah aplikasi e-commerce memiliki coverage 92%. Semua unit test dan mock integration test hijau di GitHub Actions. Namun ketika deploy ke production, form submit checkout gagal total dengan status 500. Investigasi membuktikan bahwa modul frontend mengirimkan properti `{ user_shipping_address }` (snake_case) sementara backend API v2 mewajibkan `{ userShippingAddress }` (camelCase).

**Analisis Root Cause:**
Developer menulis unit test dengan `vi.mock('axios')` dan MSW handler yang ditulis manual secara terisolasi tanpa validasi kontrak terhadap schema OpenAPI backend yang sebenarnya. Test runner menguji ekspektasi programmer, bukan validasi runtime yang valid terhadap OpenAPI schema.

**Solusi & Arsitektur Pencegahan:**
1. Gunakan Contract-Driven Mocking dengan `openapi-typescript` atau `msw-auto-mock` yang divalidasi langsung terhadap Swagger/OpenAPI JSON backend.
2. Terapkan Zod validation schema pada API client layer yang di-share antara production build dan test runner.
3. Tambahkan minimal 1 flow Playwright E2E smoke-test yang mengeksekusi order nyata di ephemeral staging environment sebelum deployment diverifikasi.

---

### Kasus 2: "Pipeline CI Memakan Waktu 45 Menit Akibat E2E Serosensitif"
**Latar Belakang Kasus:**
Suite pengujian E2E terdiri dari 420 skenario Playwright. Pipeline CI memakan waktu 45-55 menit, sering gagal secara acak (*flaky* pada 3-5 tes), sehingga developer terbiasa melakukan klik tombol *Re-run failed jobs*.

**Analisis Root Cause:**
1. Eksekusi tes berjalan secara serial pada 1 single runner VM.
2. Setiap tes melakukan flow otentikasi login manual lengkap melalui antarmuka web form (memasukkan username, password, menunggu OTP/session).
3. Pengujian bergantung pada sleep manual (`page.waitForTimeout(3000)`).
4. Tidak ada isolasi data (tes saling berebut entitas database yang sama).

**Solusi & Transformasi:**
1. **StorageState Reusability:** Buat setup global auth project di Playwright. Login dilakukan sekali, lalu state cookies/localStorage disimpan ke file `auth.json` yang di-injeksi ke context setiap worker.
2. **Sharding Matrix:** Konfigurasikan matrix sharding pada GitHub Actions (`shard: [1/4, 2/4, 3/4, 4/4]`) untuk membagi beban ke 4 mesin paralel, memotong waktu menjadi ~12 menit.
3. **Pembersihan Sleep:** Ganti seluruh `page.waitForTimeout` dengan explicit web-first assertions (`expect(locator).toBeVisible()`).

---

### Kasus 3: "Memory Leak pada Vitest Suite yang Mengakibatkan Heap Out Of Memory (OOM)"
**Latar Belakang Kasus:**
Saat jumlah test suite unit/integrasi melampaui 1.200 file, perintah `vitest run` di Docker CI crash dengan pesan: `FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory`.

**Analisis Root Cause:**
1. DOM leak: Komponen dirender dengan global listeners (`window.addEventListener('resize')` atau interval timer) yang tidak di-clean-up pada `unmount`.
2. Mock instance leak: Mock functions (`vi.fn()`) dan setup listeners MSW diakumulasikan ke memory tanpa pembersihan di `afterEach`.
3. Isolasi thread Vitest: Alokasi memory pool default mencoba menjalankan terlalu banyak worker threads yang masing-masing mempertahankan instance `jsdom` atau `happy-dom`.

**Solusi Arsitektur:**
1. Tambahkan pembersihan global otomatis pada `vitest.setup.ts`:
   ```ts
   import { cleanup } from '@testing-library/react';
   import { afterEach } from 'vitest';

   afterEach(() => {
     cleanup();
     vi.clearAllMocks();
     vi.restoreAllMocks();
   });
   ```
2. Migrasi environment dari `jsdom` ke `happy-dom` yang mengonsumsi RAM hingga 60% lebih hemat.
3. Batasi worker concurrency di lingkungan CI via `vitest.config.ts`:
   ```ts
   export default defineConfig({
     test: {
       pool: 'forks',
       poolOptions: {
         forks: {
           maxForks: process.env.CI ? 2 : undefined,
           minForks: 1,
         },
       },
     },
   });
   ```

---

## Bagian 4: 1 Practical Chapter Challenge

### Judul Challenge: "Enterprise Flight Booking Checkout Engine Test Harness"

### Deskripsi Masalah:
Anda ditugaskan membangun suite pengujian terintegrasi penuh untuk komponen wizard pemesanan tiket pesawat (`FlightCheckoutWizard.tsx`). Alur checkout memiliki 3 langkah:
1. **Langkah 1: Pemilihan Kursi (Seat Map)** - Pengguna memilih kursi.
2. **Langkah 2: Informasi Penumpang & Asuransi** - Validasi nomor paspor (harus alphanumeric 8-9 karakter) dan checkbox proteksi bagasi opsional.
3. **Langkah 3: Pembayaran & Konfirmasi** - Integrasi payment gateway dengan polling status pembayaran setiap 2 detik hingga status berubah dari `PENDING` menjadi `COMPLETED`.

### Persyaratan Uji yang Wajib Dipenuhi:
1. **Unit/Integration Test (Vitest + RTL + MSW):**
   - Mock network request booking menggunakan MSW v2 (`http.post('/api/checkout/book')` dan `http.get('/api/checkout/status/:orderId')`).
   - Uji validasi form inline saat paspor salah tanpa memicu request network.
   - Uji transisi polling dari status `PENDING` sebanyak 2x poll hingga response mengembalikan `COMPLETED`, lalu verifikasi teks konfirmasi akhir muncul di layar.
   - Uji skenario jika payment timeout / status `FAILED`, sistem menampilkan alert tombol *Coba Lagi* yang mengembalikan pengguna ke langkah pembayaran.
2. **A11y (Accessibility) Test:**
   - Gunakan `axe-core` via `jest-axe` untuk memvalidasi bahwa tidak ada pelanggaran WCAG 2.1 AA di setiap langkah wizard.
3. **Playwright E2E Spec:**
   - Tulis 1 spec file Playwright lengkap (`flight-booking.spec.ts`) yang mencakup *happy path*:
     - Interaksi UI dari pemilihan kursi hingga booking sukses.
     - Menggunakan Page Object Model (POM).
     - Menghindari hardcoded timeout.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan matriks checklist ini untuk mengevaluasi kesiapan tim dalam mengimplementasikan strategi testing enterprise:

| Topik Pengujian | Kriteria Penguasaan | Status (Paham / Butuh Review) |
|---|---|---|
| **Testing Philosophy** | Memahami perbedaan Trade-off Testing Pyramid vs Testing Trophy (fokus pada Integration). | [ ] |
| **DOM Querying** | Menguasai penggunaan ARIA roles (`role`, `name`, `accessible description`) dibandingkan CSS/id selectors. | [ ] |
| **Network Mocking** | Mampu mengonfigurasi MSW v2 di lingkungan node (`setupServer`) dan browser (`setupWorker`). | [ ] |
| **Asynchronous UI** | Menggunakan `findBy*` dan `waitFor` dengan tepat tanpa bergantung pada `sleep` / `setTimeout`. | [ ] |
| **Form Interaction** | Menggunakan `@testing-library/user-event` v14+ untuk mensimulasikan event pengetikan dan click yang realistis. | [ ] |
| **Accessibility Audit** | Mampu mengintegrasikan audit otomatis `axe-core` ke dalam unit dan E2E pipeline. | [ ] |
| **Playwright Automation**| Mampu merancang Page Object Model (POM) yang modular, type-safe, dan auto-waiting compliant. | [ ] |
| **Authentication in E2E**| Mampu mengimplementasikan penyimpanan state otentikasi via `storageState` untuk bypass re-login di E2E. | [ ] |
| **CI/CD Optimization** | Memahami teknik test sharding, test caching, dan alokasi memory heap di runner Linux headless. | [ ] |
| **Visual Regression** | Mampu menetapkan baseline snapshot, toleransi threshold per-pixel, dan standardisasi rendering lintas OS. | [ ] |
