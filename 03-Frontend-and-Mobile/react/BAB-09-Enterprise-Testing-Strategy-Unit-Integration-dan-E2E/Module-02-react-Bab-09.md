# BAB 09: Enterprise Testing Strategy: Unit, Integration, dan E2E
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonstruksi arsitektur *integration testing* tingkat lanjut menggunakan **React Testing Library (RTL)** dan **Mock Service Worker (MSW) v2** dengan mengisolasi network layer tanpa memotong *lifecycle* browser/Node runtime.
- Mendesain pipeline pengujian deterministik untuk menangani skenario asinkron kompleks: *race conditions*, Suspense boundary, Server-Sent Events (SSE), dan mutasi state konkuren pada React 18/19.
- Mengimplementasikan framework **Playwright** untuk pengujian End-to-End (E2E) dengan arsitektur *Page Object Model* (POM), autentikasi berbasis *storage state*, serta paralelisasi berbasis kontainer di CI/CD.
- Menganalisis ketahanan suite pengujian melalui teknik **Mutation Testing** (Stryker) guna membuktikan efektivitas assertion melampaui metrik *code coverage* konvensional.
- Mengeliminasi *test flakiness* pada level arsitektural menggunakan pola sinkronisasi berbasis *microtask queue* dan penanganan *deterministic time mocking*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer harus menguasai:
- **Testing Pyramid Fundamentals**: Pemahaman dasar pemisahan Unit, Integration, dan E2E test.
- **TypeScript Advanced Types**: Discriminated unions, generics, dan conditional types untuk mock tooling.
- **React Concurrent Internals**: Pemahaman tentang Fiber architecture, Lanes, microtask scheduling, dan `act()` environment.
- **HTTP/Network Stack**: RESTful conventions, WebSocket/SSE handshake, dan interception browser context.

---

### 3. Concept & Internal Architecture

#### A. Network Mocking Internals: MSW v2 vs. Spies/Stubs
Pengujian integrasi modern menolak pendekatan `jest.spyOn(global, 'fetch')` atau mem-mock modul Axios secara langsung. Mengganti implementasi HTTP client merusak fidelity pengujian karena melewati serializer, interceptor, dan parser payload riil aplikasi.

```
+-----------------------------------------------------------------------+
| NODE.JS RUNTIME (Vitest / RTL)      | BROWSER RUNTIME (Playwright/E2E)|
|                                     |                                 |
|  [ React Component Tree ]           |  [ React Component Tree ]       |
|              |                      |              |                  |
|          fetch()                    |          fetch()                |
|              v                      |              v                  |
|     [@mswjs/interceptors]           |     [Service Worker Engine]     |
|   (Hooks into Node http/https)      |     (Intercepts fetch event)    |
|              |                      |              |                  |
|      +-------v-------+              |      +-------v-------+          |
|      | MSW Handler   |              |      | MSW Handler   |          |
|      +-------+-------+              |      +-------+-------+          |
|              | (Mocked Response)    |              | (Mocked Response)|
|              v                      |              v                  |
|    Parsed Data -> Component         |    Parsed Data -> Component     |
+-----------------------------------------------------------------------+
```

MSW v2 beroperasi pada batas jaringan (*network boundary*):
1. **Node Environment (Integration Testing)**: MSW memanfaatkan `@mswjs/interceptors` yang menambal modul bawaan Node.js (`http`, `https`, `XMLHttpRequest`, `fetch`) di level C++/binding layer. Interceptor mengidentifikasi URL target dan mengalihkan request ke handler tanpa membuka soket TCP.
2. **Browser Environment (E2E / Development)**: Menggunakan Service Worker API via `mockServiceWorker.js`. Event `fetch` didengarkan di background thread, mencegah request keluar ke gateway eksternal dan mengembalikan `Response` sintetis secara transparan.

#### B. React Testing Library: The Accessibility Tree & MutationObserver
RTL menguji komponen dari sudut pandang *Accessibility Tree* (AOM), bukan DOM mentah.
- Saat pemanggilan fungsi `screen.getByRole('button', { name: /kirim/i })` dieksekusi, RTL menelusuri DOM tree dan menghitung atribut komputasi aksesibilitas elemen (Accessible Name Computation specification).
- Fungsi asinkron `waitFor` dan `findBy*` bekerja dengan membungkus assertions ke dalam polling loop yang dipicu oleh instans `MutationObserver`. Ketika React Fiber melakukan commit mutasi ke DOM, `MutationObserver` memicu microtask callback untuk mengevaluasi assertion kembali hingga batas *timeout* tercapai.

#### C. React Concurrent Mode and the `act()` Environment
Dalam React 18+, pembaruan state dikelompokkan (*batched*) dan dapat diinterupsi oleh scheduler. Pembungkus `act()` memastikan seluruh scheduled task di *Immediate Priority Queue*, *Normal Priority Queue*, dan *Microtask Queue* dikosongkan (*flushed*) sebelum runtime pengujian melakukan inspeksi DOM. Tanpa sinkronisasi ini, assertion terjadi sebelum Fiber selesai me-reconcile perubahan, memicu false negatives dan peringatan memory leak.

#### D. Playwright Architecture: Chrome DevTools Protocol (CDP)
Tidak seperti Selenium yang mengandalkan HTTP-based WebDriver wire protocol dengan latensi komunikasi per-perintah, Playwright berkomunikasi langsung via soket WebSocket bi-direksional menggunakan **Chrome DevTools Protocol (CDP)** (atau protokol setara pada Gecko/WebKit). Ini memungkinkan Playwright mengeksekusi operasi evaluasi kode in-process, network routing langsung di level browser kernel, dan auto-waiting deterministik berbasis event loop browser.

---

### 4. Why & What

| Dimensi | Pendekatan Naif / Legacy | Pendekatan Enterprise Modern |
| :--- | :--- | :--- |
| **Mocking Strategy** | `jest.mock('../api')` (Mocking library logic) | MSW v2 (Mocking raw network transport) |
| **Element Selection**| CSS Selector (`.btn-primary`, `#submit-id`) | Accessibility Queries (`getByRole`, `getByLabelText`) |
| **Asynchronous Assertion** | `sleep(2000)` / Arbitrary Delay | MutationObserver Auto-Wait (`waitFor`, `findBy*`) |
| **Auth State di E2E**| Form login ulang di setiap test suite | Reusable `storageState` (Inject cookies/tokens) |
| **Coverage Metric** | 100% Line/Branch Coverage (Kuantitatif) | Mutation Testing / Stryker (Kualitatif) |

- **Why MSW?** Mengurangi drift antara mock data dan API riil; kode integrasi yang sama dapat dites di Node.js (Vitest) tanpa perubahan implementasi.
- **Why Accessibility Queries?** Memaksa developer menulis markup HTML yang semantik dan kompatibel dengan Screen Reader. Jika test gagal ditemukan via role, aplikasi memiliki cacat aksesibilitas (a11y).
- **Why Storage State?** Menghapus overhead 2–5 detik per pengujian E2E untuk memvalidasi proses login berulang kali.

---

### 5. How (Workflow Detail)

Alur eksekusi pipeline pengujian enterprise dari level lokal ke CI/CD:

```
[Local Dev / Pre-Push Hook]
   |
   +---> Vitest + MSW (Unit & Component Integration)
   |       - Verifikasi logic & UI state isolation
   |       - Fast Feedback Loop (< 30 detik)
   |
   +---> Stryker Mutation Testing (Targeted/Diff Mode)
           - Memastikan assertion test memvalidasi bug
   |
[CI Pipeline Matrix]
   |
   +---> Linter, Type-Check (tsc), Format Check
   |
   +---> Vitest Coverage Report Generation
   |
   +---> Playwright Sharded Execution (Matrix: 4 Runners)
           - Worker 1: Shard 1/4 (Cart & Checkout Flow)
           - Worker 2: Shard 2/4 (Account & Security Flow)
           - Worker 3: Shard 3/4 (Dashboard Analytics Flow)
           - Worker 4: Shard 4/4 (Edge Cases & Visual Regres)
           - Semua worker menggunakan pre-cached authentication state
   |
   +---> Merge Playwright Reports & Publish Artifacts
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Simulator Penerbangan
- **Unit Test (Fungsi/Hook)**: Menguji instrumen altimeter secara terpisah di meja kerja lab. Memastikan sensor angka bergerak ketika tekanan udara sintetis diubah.
- **Integration Test (RTL + MSW)**: Menguji kokpit utuh. Pilot menekan tombol, sistem kemudi merespons, layar dashboard membaca navigasi. Transmisi radio menara pengawas disimulasikan oleh operator dari ruangan sebelah (MSW); kokpit tidak mengetahui bahwa sinyal radio tersebut bukan berasal dari menara asli.
- **E2E Test (Playwright)**: Pesawat utuh diterbangkan di landasan pacu sungguhan dengan kondisi angin dan cuaca nyata. Menguji interoperabilitas dari awal menyalakan mesin turbin hingga mendarat di terminal tujuan.

```
       [E2E: Full Application Sandbox]
        +-----------------------------------+
        | Browser Window (Playwright)       |
        |  +-----------------------------+  |
        |  | React SPA + LocalStorage    |  |
        |  +--------------+--------------+  |
        |                 | Network Wire    |
        +-----------------|-----------------+
                          v
         [Integration: In-Memory Host]
          +-----------------------------+
          | RTL Render Container        |
          |  +-----------------------+  |
          |  | Component Tree        |  |
          |  +-----------+-----------+  |
          |              | HTTP calls   |
          |   +----------v-----------+  |
          |   | MSW Interceptor      |  |
          |   +----------------------+  |
          +-----------------------------+
                          | Function Call
         [Unit: Pure Logic Isolation]
          +-----------------------------+
          | Hook / Utility Function     |
          +-----------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Konfigurasi MSW v2 Global & Custom Test Renderer
Abstraksi render kustom wajib menyediakan state wrappers (QueryClient, Theme, Auth, MemoryRouter) dengan arsitektur isolasi cache per-test.

```typescript
// src/test/test-utils.tsx
import React, { PropsWithChildren, ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, MemoryRouterProps } from 'react-router-dom';

interface ExtendedRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  initialEntries?: MemoryRouterProps['initialEntries'];
  queryClient?: QueryClient;
}

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false, // Menghindari false positive timeout saat skenario error
        gcTime: 0,
      },
    },
  });
}

export function renderWithProviders(
  ui: ReactElement,
  {
    initialEntries = ['/'],
    queryClient = createTestQueryClient(),
    ...renderOptions
  }: ExtendedRenderOptions = {}
) {
  function AllTheProviders({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={initialEntries}>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  return {
    ...render(ui, { wrapper: AllTheProviders, ...renderOptions }),
    queryClient,
  };
}

export * from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';
```

#### B. Practical Example: Integration Test Transaksi Finansial
Komponen checkout dengan *optimistic update*, pemanggilan API mutasi, dan penanganan kegagalan transaksi via MSW v2.

```typescript
// src/features/billing/components/TransferFundModal.tsx
import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';

interface TransferPayload {
  recipientId: string;
  amount: number;
}

export const TransferFundModal: React.FC<{ onSuccess: () => void }> = ({ onSuccess }) => {
  const [recipientId, setRecipientId] = useState('');
  const [amount, setAmount] = useState<number>(0);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (payload: TransferPayload) => {
      const res = await fetch('/api/v1/transfers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.message || 'Transfer failed');
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['balance'] });
      onSuccess();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (amount <= 0 || !recipientId) return;
    mutation.mutate({ recipientId, amount });
  };

  return (
    <form onSubmit={handleSubmit} aria-label="form-transfer-dana">
      <h2>Transfer Dana</h2>
      
      {mutation.isError && (
        <div role="alert" aria-live="assertive">
          {mutation.error.message}
        </div>
      )}

      <label htmlFor="recipient">ID Rekening Penerima</label>
      <input
        id="recipient"
        type="text"
        value={recipientId}
        onChange={(e) => setRecipientId(e.target.value)}
        disabled={mutation.isPending}
      />

      <label htmlFor="amount">Jumlah Transfer</label>
      <input
        id="amount"
        type="number"
        value={amount}
        onChange={(e) => setAmount(Number(e.target.value))}
        disabled={mutation.isPending}
      />

      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? 'Memproses...' : 'Kirim Sekarang'}
      </button>
    </form>
  );
};
```

Uji integrasi deterministik dengan MSW v2:

```typescript
// src/features/billing/components/__tests__/TransferFundModal.test.tsx
import { describe, it, expect, vi, beforeAll, afterAll, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { renderWithProviders, screen, userEvent } from '../../../../test/test-utils';
import { TransferFundModal } from '../TransferFundModal';

// Setup Mock Service Worker instance
const server = setupServer(
  http.post('/api/v1/transfers', async ({ request }) => {
    const body = (await request.json()) as { recipientId: string; amount: number };
    
    if (body.amount > 10_000_000) {
      return HttpResponse.json(
        { message: 'Batas limit transfer harian terlampaui' },
        { status: 422 }
      );
    }
    
    return HttpResponse.json({ transactionId: 'TXN-99812', status: 'SUCCESS' }, { status: 201 });
  })
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Integration: <TransferFundModal />', () => {
  it('berhasil melakukan transfer dan mengeksekusi callback onSuccess', async () => {
    const user = userEvent.setup();
    const handleSuccess = vi.fn();

    renderWithProviders(<TransferFundModal onSuccess={handleSuccess} />);

    // Query via accessible roles
    const recipientInput = screen.getByRole('textbox', { name: /id rekening penerima/i });
    const amountInput = screen.getByRole('spinbutton', { name: /jumlah transfer/i });
    const submitButton = screen.getByRole('button', { name: /kirim sekarang/i });

    // User interactions
    await user.type(recipientInput, 'ACC-001293');
    await user.type(amountInput, '500000');

    expect(submitButton).toBeEnabled();
    await user.click(submitButton);

    // Assert transient UI state
    expect(screen.getByRole('button', { name: /memproses\.\.\./i })).toBeDisabled();

    // Assert asynchronous success state resolution
    await screen.findByRole('button', { name: /kirim sekarang/i });
    expect(handleSuccess).toHaveBeenCalledTimes(1);
  });

  it('menampilkan pesan error jika request ditolak oleh API gateway', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TransferFundModal onSuccess={vi.fn()} />);

    await user.type(screen.getByRole('textbox', { name: /id rekening penerima/i }), 'ACC-001293');
    await user.type(screen.getByRole('spinbutton', { name: /jumlah transfer/i }), '50000000');
    await user.click(screen.getByRole('button', { name: /kirim sekarang/i }));

    // Assert error alert element presence in DOM
    const alertBox = await screen.findByRole('alert');
    expect(alertBox).toHaveTextContent(/batas limit transfer harian terlampaui/i);
    expect(screen.getByRole('button', { name: /kirim sekarang/i })).toBeEnabled();
  });
});
```

#### C. Production E2E: Playwright Page Object Model dengan Session Storage Reuse
Menghilangkan overhead autentikasi di seluruh test flow.

```typescript
// e2e/pages/TransferPage.ts
import { Page, Locator, expect } from '@playwright/test';

export class TransferPage {
  readonly page: Page;
  readonly recipientInput: Locator;
  readonly amountInput: Locator;
  readonly submitButton: Locator;
  readonly confirmationToast: Locator;

  constructor(page: Page) {
    this.page = page;
    this.recipientInput = page.getByRole('textbox', { name: /id rekening penerima/i });
    this.amountInput = page.getByRole('spinbutton', { name: /jumlah transfer/i });
    this.submitButton = page.getByRole('button', { name: /kirim sekarang/i });
    this.confirmationToast = page.getByRole('status');
  }

  async goto() {
    await this.page.goto('/dashboard/transfers');
    await expect(this.submitButton).toBeVisible();
  }

  async executeTransfer(recipient: string, amount: string) {
    await this.recipientInput.fill(recipient);
    await this.amountInput.fill(amount);
    await this.submitButton.click();
  }
}
```

```typescript
// e2e/specs/transfer.spec.ts
import { test, expect } from '@playwright/test';
import { TransferPage } from '../pages/TransferPage';

// Menggunakan auth storage state yang sudah digenerate saat global setup
test.use({ storageState: 'playwright/.auth/user.json' });

test.describe('E2E: Transfer Flow Multi-devices', () => {
  test('Menjalankan pengiriman dana dari dashboard hingga verifikasi mutasi', async ({ page }) => {
    const transferPage = new TransferPage(page);
    
    // Intercept network call untuk memvalidasi idempotency header
    let idempotencyKeyHeader: string | null = null;
    await page.route('**/api/v1/transfers', async (route) => {
      idempotencyKeyHeader = route.request().headers()['x-idempotency-key'];
      await route.continue();
    });

    await transferPage.goto();
    await transferPage.executeTransfer('ACC-TEST-999', '150000');

    // Assertion kualitatif E2E
    await expect(transferPage.confirmationToast).toContainText('Transfer berhasil diproses');
    expect(idempotencyKeyHeader).toBeDefined();
  });
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Dashboard Trading Saham Skala Enterprise
**Latar Belakang**: Aplikasi single-page trading derivatif mengalami kegagalan regresi reguler pada pipeline rilis. Kerusakan terjadi pada sinkronisasi *Order Book* yang menerima mutasi data gabungan antara WebSocket streaming dan REST query (TanStack Query). Test suite lama (Cypress) memakan waktu 48 menit di CI dan memiliki rasio flakiness mencapai 14.8%.

**Arsitektur Penyelesaian**:
1. **Network Layer Isolation**: Mengganti mock manual berbasis Cypress dengan integrasi MSW WebSocket API (`ws.link`) untuk mengontrol deterministic streaming event ticker saham pada integration test level RTL.
2. **Deterministic Time Mocking**: Menggunakan API `vi.useFakeTimers()` yang disinkronisasikan dengan batch updates React 18 Concurrent Rendering untuk menguji chart rendering tanpa menunggu interval waktu riil.
3. **Optimasi Playwright Sharding**: Memecah 280 test case E2E ke dalam 4 paralel Docker matrix runners di GitHub Actions, menggunakan `storageState` bersama yang dikonstruksi sekali pada tahapan initialization runner.

```
Execution Time Matrix:
Before (Cypress Non-sharded):  [48 Menit] Flakiness: 14.8%
After (Playwright 4x Sharded): [ 6 Menit] Flakiness:  0.2%
```

**Dampak Bisnis**: 
- Waktu siklus Deployment Lead Time turun dari 120 menit menjadi 18 menit.
- Zero P1 incident akibat *race condition* order matching pada UI selama 3 kuartal pasca migrasi.

---

### 9. Trade-offs

```
                  Unit (Pure Functions)
                       /\
                      /  \     Cost: Rendah | Speed: Instan | Fidelity: Rendah
                     /    \
                    / Integration \
                   / (RTL + MSW)   \ Cost: Moderat | Speed: Cepat | Fidelity: Tinggi
                  /-----------------\
                 /    End-to-End     \
                /    (Playwright)     \ Cost: Tinggi | Speed: Lambat | Fidelity: Maksimal
               +-----------------------+
```

| Tipe Testing | Metrik Kinerja | Kompleksitas Maintenance | Kelebihan Arsitektural | Kelemahan / Konsekuensi |
| :--- | :--- | :--- | :--- | :--- |
| **Unit Testing** | ~2-5 ms / test | Sangat Rendah | Feedback loop instan, eksekusi cabang logika ekstrem. | Gagal mendeteksi kegagalan integrasi antarmuka/kontrak data. |
| **Integration (RTL + MSW)** | ~50-200 ms / test | Moderat | Mendeteksi bug DOM-lifecycle & state race conditions; network tetap terisolasi. | Tidak mengevaluasi performa rendering CSS asli, rendering WebGL, cross-browser engine quirks. |
| **E2E (Playwright)** | ~2-15 s / test | Tinggi | Validasi end-to-end, layout regression, third-party redirects, otentikasi browser riil. | Membutuhkan resource compute CI besar; risiko flakiness akibat timeout jaringan eksternal tinggi. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan: Menguji Implementation Details
*Anti-Pattern*:
```typescript
// SALAH: Menguji state internal & instance component
const wrapper = shallow(<Counter />);
expect(wrapper.state('count')).toBe(1);
expect(wrapper.find('div.container').length).toBe(1);
```
*Solusi Enterprise*:
Uji efek observable yang dirasakan oleh end-user atau assistive technology.
```typescript
// BENAR: Menguji perubahan semantik pada accessibility tree
renderWithProviders(<Counter />);
await userEvent.click(screen.getByRole('button', { name: /tambah/i }));
expect(screen.getByRole('status')).toHaveTextContent('1');
```

#### 2. Kesalahan: Pembungkus `act()` yang Berlebihan (*Over-wrapping*)
*Masalah*: Peringatan `Warning: An update to Component inside a test was not wrapped in act(...)`. Developer sering panik lalu membungkus semua baris pengujian dengan `await act(async () => ...)`.
*Solusi Root-Cause*: RTL secara default telah membungkus pemanggilan via `userEvent` dan `waitFor` ke dalam `act()`. Peringatan ini muncul hampir selalu akibat adanya promise asinkron yang *belum terselesaikan* saat test selesai. Pastikan semua efek asinkron di-`await` via `waitFor` atau assertion `findBy*`.

#### 3. Kesalahan: Memory Leak pada Jest/Vitest Runner
*Gejala*: CI kehabisan memori (OOM Error: JavaScript heap out of memory) setelah menjalankan ratusan file test.
*Mitigasi*:
- Hancurkan instance React Query client: Buat fresh client baru per test instance via factory pattern, bukan instans singleton global.
- Bersihkan DOM dan unmount: Vitest mengeksekusi `cleanup()` secara implisit jika diaktifkan, namun event listener non-DOM atau custom sub-engine (misal: visual libraries) harus di-dispose eksplisit di `afterEach()`.
- Hindari variable capture scope global yang menahan referensi instance DOM.

---

### 11. Best Practices (Production Checklist)

- [ ] **Semantik Query Terstandarisasi**: Terapkan hierarki query RTL: `getByRole` > `getByLabelText` > `getByPlaceholderText` > `getByText` > `getByTestId`. Larang eksplisit penggunaan CSS class selectors (`querySelector`).
- [ ] **Data Isolation**: Database mock atau handler MSW tidak boleh mengoperasikan variabel global yang mutable antartest tanpa implementasi `server.resetHandlers()` di `afterEach`.
- [ ] **CI Sharding Determinism**: Setiap shard Playwright di CI harus mandiri (*self-contained*), tidak bergantung pada urutan eksekusi (*order independent*), dan membersihkan mutasi data storage secara terisolasi.
- [ ] **Explicit Waiting Policy**: Hilangkan pemanggilan statis `page.waitForTimeout(5000)` atau `setTimeout` pada test harness. Gantikan secara absolut dengan `expect(locator).toBeVisible()` atau event predicates.
- [ ] **Mutation Testing Threshold**: Jalankan Stryker pada setiap *Pull Request* yang menyentuh *core domain logic* (misal: modul pricing engine, otentikasi) dengan ambang batas *Mutation Score Indicator (MSI)* minimal 80%.

---

### 12. Hands-on Practice

Buat dan implementasikan suite pengujian integrasi enterprise di workspace: `hands-on/m02/`

#### Langkah 1: Inisialisasi Environment
Pasang package dependensi:
```bash
npm install -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom msw@latest @tanstack/react-query
```

#### Langkah 2: Setup Konfigurasi Stryker Mutation Testing
Buat berkas konfigurasi Stryker:
```javascript
// hands-on/m02/stryker.config.json
{
  "$schema": "https://raw.githubusercontent.com/stryker-mutator/stryker-js/master/packages/api/schema/stryker-core.json",
  "packageManager": "npm",
  "reporters": ["html", "clear-text", "progress"],
  "testRunner": "vitest",
  "testRunner_comment": "Pastikan vitest terkonfigurasi dengan vite.config.ts",
  "coverageAnalysis": "perTest",
  "mutate": [
    "src/features/**/*.{ts,tsx}",
    "!src/features/**/*.test.{ts,tsx}",
    "!src/**/*.d.ts"
  ],
  "thresholds": { "high": 85, "low": 70, "break": 75 }
}
```

#### Langkah 3: Setup Network Interception Handler
Konfigurasikan mock handler MSW v2:
```typescript
// hands-on/m02/src/mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/v1/user/portfolio', () => {
    return HttpResponse.json({
      portfolioId: 'PF-001',
      totalValueUSD: 142500.5,
      riskLevel: 'AGGRESSIVE',
    });
  }),
];
```

#### Langkah 4: Implementasi Hook & Test Assertion
Implementasikan hook dan jalankan pengujian integrasi:
```bash
npx vitest run hands-on/m02/src/
npx stryker run hands-on/m02/stryker.config.json
```

---

### 13. Exercise

#### Level: Easy
Refaktor blok kode assertion berikut yang menguji tombol submit form agar memenuhi standar accessibility testing modern:
```typescript
// Kode Asal:
const { container } = render(<LoginForm />);
const button = container.querySelector('.submit-btn-cls');
fireEvent.click(button);
expect(container.querySelector('.alert-success')).not.toBeNull();
```

#### Level: Medium
Tuliskan test suite menggunakan Vitest dan MSW v2 untuk komponen `<SessionRefresher />`. Komponen ini melakukan polling setiap 10 detik ke endpoint `/api/v1/ping`. Jika endpoint merespons status `401 Unauthorized`, komponen harus memanggil callback `onSessionExpired()`. Manfaatkan `vi.useFakeTimers()` secara aman.

#### Level: Hard
Kembangkan custom fixture Playwright bernama `authenticatedWorkerPage` yang secara otomatis meng-inject token otentikasi JWT yang valid (beserta data payload terenkripsi ke IndexedDB) sebelum halaman dinavigasi, tanpa melewati form input login UI fisik pada setiap skenario test E2E.

---

### 14. Challenge

**Skenario**: Sistem Checkout E-Commerce Multichannel dengan Sinkronisasi Stok Real-time (Optimistic Locking & SSE).

Sebuah komponen `<CheckoutGate />` mengunci reservasi item selama 60 detik. Saat user menekan tombol checkout:
1. Dikirim request POST `/api/v1/checkout/lock`.
2. Koneksi Server-Sent Events (SSE) dibuka ke `/api/v1/checkout/stream-status` untuk memantau status pembayaran pihak ketiga.
3. Jika terdapat pesan SSE `EVENT_PAYMENT_TIMEOUT`, UI harus menampilkan modal pembatalan transaksi dan mengembalikan cart ke state awal.
4. Jika koneksi jaringan pengguna putus di tengah proses (offline), sistem harus mencoba reconnect sebanyak 3 kali (backoff multiplier 1.5x) sebelum menampilkan pesan `Network Connectivity Lost`.

**Tugas Arsitektur**:
Rancang dan bangun arsitektur test integrasi komprehensif menggunakan **React Testing Library** dan **MSW v2** yang membuktikan bahwa mekanisme reconnection backoff, penanganan stream event SSE sintetis, dan fallback rollback state beroperasi secara deterministik tanpa menimbulkan memory leak ataupun false positive unhandled promise rejection.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. Mengapa selector `getByRole` diposisikan pada prioritas tertinggi dalam metodologi React Testing Library dibanding `getByTestId`?
2. Bagaimana mekanisme kerja internal MSW v2 saat mengeksekusi interception request pada Node.js environment?
3. Apa perbedaan mendasar antara fungsi query RTL `getBy*`, `queryBy*`, dan `findBy*`?
4. Mengapa penggunaan `fireEvent` dari RTL tidak direkomendasikan dan harus digantikan oleh `@testing-library/user-event`?
5. Apa konsekuensi arsitektural jika `server.resetHandlers()` dihilangkan pada blok lifecycle hook `afterEach` saat menggunakan MSW?

#### Intermediate (5 Pertanyaan)
6. Bagaimana cara MutationObserver pada fungsi `waitFor` RTL mendeteksi bahwa assertion siap dievaluasi kembali tanpa melakukan CPU-intensive busy-waiting?
7. Terangkan bagaimana `storageState` pada Playwright dapat secara signifikan memotong latensi eksekusi rangkaian E2E test!
8. Apa kelemahan metrik "100% Code Line Coverage" yang berhasil dipecahkan oleh pendekatan Mutation Testing (Stryker)?
9. Bagaimana strategi menangani component Suspense yang sedang berada pada fallback state saat diuji menggunakan React Testing Library?
10. Dalam skenario React 18 Concurrent Rendering, apa fungsi spesifik dari `IS_REACT_ACT_ENVIRONMENT = true` yang diatur oleh engine runner pengujian?

#### Production Scenarios (3 Kasus)
11. **Kasus 1**: Suite pengujian integrasi Vitest mendadak gagal (*intermittent failure*) hanya ketika dijalankan di runner VM CI/CD (Ubuntu), namun selalu sukses (100% pass) di laptop developer lokal (macOS M-series). Analisis 3 kemungkinan arsitektural penyebab kegagalan dan langkah mitigasinya!
12. **Kasus 2**: Di aplikasi Anda, komponen form checkout mengalami bug di production: tombol submit tertekan dua kali secara cepat (*double-tap/race condition*), mendebit rekening customer dua kali. Seluruh unit dan integration test yang ada sebelumnya berstatus lolos (passing). Mengapa test harness yang ada gagal mendeteksi cacat ini dan bagaimana merancang skenario assertion RTL yang presisi untuk mereproduksinya?
13. **Kasus 3**: Tim QA Anda mengeluhkan runtime E2E test dengan Playwright melonjak dari 15 menit ke 75 menit seiring bertambahnya fitur aplikasi enterprise. Analisis langkah rekonstruksi arsitektural pipeline pengujian tersebut untuk menurunkannya kembali ke bawah 10 menit tanpa memangkas jumlah cakupan skenario test!

---

### 16. Summary

Implementasi enterprise testing strategy pada React menuntut pergeseran paradigma dari pengujian *implementation details* ke validasi fungsionalitas berbasis kontrak pengguna (*user-centric black box testing*). 

Dengan mengombinasikan **React Testing Library** yang berorientasi pada Accessibility Object Model (AOM), **MSW v2** yang mengisolasi network layer pada batas soket/thread terendah, serta **Playwright** yang beroperasi via protokol browser level rendah (CDP) dengan paralelisasi storage state, kita membangun benteng pertahanan perangkat lunak yang memiliki *high confidence*, minim *maintenance drag*, dan tahan terhadap refaktor arsitektur internal aplikasi. 

Keandalan seluruh ekosistem ini divalidasi bukan semata melalui metrik cakupan baris kode mentah (*line coverage*), melainkan melalui ketahanan assertion terhadap mutasi logika sengaja via **Mutation Testing**.