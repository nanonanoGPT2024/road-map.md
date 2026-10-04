# Bab 09 Module 01: Enterprise Testing Strategy: Unit, Integration, & E2E

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori**: 03-Frontend-and-Mobile
* **Jalur Kurikulum**: React Advanced & Enterprise Architecture
* **Topik Modul**: Enterprise Testing Strategy: Unit, Integration, & E2E
* **Tingkat Kesulitan**: Advanced / Staff Engineer Level
* **Prasyarat**: React 18+ Core (Concurrent Features, Hooks), TypeScript Enterprise Patterns, DOM API & Browser Event Loop, Dasar CI/CD Pipeline Automation
* **Alokasi Waktu**: 8 - 10 Jam Pembelajaran Intensif

---

## SEKSI 02 — LEARNING OBJECTIVES

1. **Mendesain Enterprise Testing Architecture**: Mampu merancang strategi pengujian piramida dan trofi pengujian (*Testing Trophy*) yang menyeimbangkan *speed*, *cost*, dan *confidence* untuk aplikasi frontend berskala besar.
2. **Menguasai Unit & Component Testing dengan Vitest & React Testing Library (RTL)**: Mampu menguji *pure functions*, *custom hooks*, serta komponen terisolasi berdasar perilaku pengguna (*user-centric behavior*) tanpa bergantung pada detail implementasi internal.
3. **Mengimplementasikan Network Mocking Tingkat Lanjut**: Menguasai integrasi Mock Service Worker (MSW v2) untuk mengabstraksi lapisan I/O jaringan tanpa merusak *Fetch API / XMLHttpRequest* asli.
4. **Membangun Resilient End-to-End (E2E) Suites Menggunakan Playwright**: Mampu mengimplementasikan *Page Object Models* (POM), autentikasi terisolasi berbasis penyimpanan sesi (*storage state*), serta pengujian paralel yang deterministik dan tahan flakiness.
5. **Menjamin Keamanan dan Efisiensi Eksekusi Pengujian**: Menegakkan *deterministic assertions*, mitigasi kebocoran memori pada *test runners*, dan integrasi *Test Impact Analysis* (TIA) pada pipeline CI/CD enterprise.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa perangkat lunak enterprise, pengujian frontend bukan sekadar upaya mencapai metrik *code coverage* 100%. Mental model utama pengujian modern adalah: **"Uji perilaku (behavior), bukan implementasi (implementation detail)."**

```
+--------------------------------------------------------------------+
|                      MENTAL MODEL MATRIX                           |
+--------------------------------------------------------------------+
|  ANTI-PATTERN (Brittle)           |  ENTERPRISE PATTERN (Resilient)|
+-----------------------------------+--------------------------------+
|  Menguji State internal (isOpen)  |  Menguji Elemen Layar (Visible)|
|  Mocking modul berlebihan         |  Mocking pada Boundary Jaringan|
|  Snapshot testing seluruh DOM     |  Eksplisit pada Kontrak Data   |
|  Query DOM via CSS Class/ID       |  Query via ARIA Role / Semantik|
|  Asumsi Eksekusi Sekuensial       |  Asumsi Konkurensi & Isolasi   |
+--------------------------------------------------------------------+
```

Pengembang enterprise memperlakukan *test suite* sebagai konsumen pertama dari API atau UI yang dibangun. Jika refaktorisasi internal (misalnya, mengganti `useState` menjadi `useReducer` atau XState) merusak *test suite* Anda padahal antarmuka visual dan alur pengguna tidak berubah, pengujian Anda bernilai negatif (*false negative*) dan menghambat kecepatan rilis.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur pengujian frontend enterprise membagi pengujian ke dalam tiga lapisan utama dengan batas batas isolasi (*boundary isolation*) yang jelas:

```
+-------------------------------------------------------------------------------+
|                        ENTERPRISE TEST ARCHITECTURE                           |
+-------------------------------------------------------------------------------+
|                                                                               |
|  [ E2E Layer: Playwright ]                                                    |
|  +-------------------------------------------------------------------------+  |
|  | Real Headless Browser (Chromium / WebKit / Firefox)                     |  |
|  | Real Network (or Staging Backend) / Global State Storage State          |  |
|  +-------------------------------------------------------------------------+  |
|                                       |                                       |
|                                       v                                       |
|  [ Integration Layer: Vitest + RTL + MSW v2 ]                                 |
|  +-------------------------------------------------------------------------+  |
|  | Node.js / JSDOM Environment                                             |  |
|  | MSW Service Worker / Interceptor (Intercepts at Node/Browser HTTP level)|  |
|  | State Providers (Redux/Zustand, React Query, Router) Diinjeksi Lengkap  |  |
|  +-------------------------------------------------------------------------+  |
|                                       |                                       |
|                                       v                                       |
|  [ Unit Layer: Vitest ]                                                       |
|  +-------------------------------------------------------------------------+  |
|  | Pure Functions, Domain Entities, Isolated Custom Hooks                  |  |
|  | Zero DOM Dependency (Node.js Environment murni)                         |  |
|  +-------------------------------------------------------------------------+  |
|                                                                               |
+-------------------------------------------------------------------------------+
```

Alur eksekusi saat pengujian integrasi berbasis MSW dijalankan di lingkungan Node/JSDOM:

```
+-------------+         +------------------+         +------------------+
| React Test  | ------> | Component Render | ------> | Fetch / Axios    |
| (RTL Script)|         | (Virtual DOM)    |         | (HTTP Invocation)|
+-------------+         +------------------+         +------------------+
                                                               |
                                                               v
+-------------+         +------------------+         +------------------+
| RTL Assert  | <------ | Synthetic Event  | <------ | MSW Interceptor  |
| Expectations|         | DOM Re-render    |         | (Node / Bypass)  |
+-------------+         +------------------+         +------------------+
                                                               |
                                                               v
                                                     +------------------+
                                                     | Mock Handler     |
                                                     | Returns Mock JSON|
                                                     +------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. React Testing Library (RTL) & JSDOM Mechanics
RTL membungkus `ReactDOM.render` menggunakan `render()` miliknya ke dalam penampung JSDOM (`document.body`). Ketika event ditembakkan via `@testing-library/user-event`:
* User-event menyimulasikan urutan mikro event peramban asli (misal: `pointerdown` -> `mousedown` -> `focus` -> `pointerup` -> `mouseup` -> `click`).
* Pembaruan state komponen dimasukkan ke dalam antrean *scheduler* React.
* Method asinkron RTL seperti `findByRole` mengeksekusi siklus polling (menggunakan `MutationObserver` internal yang memantau mutasi node pada sub-tree DOM) hingga elemen target terpasang (*mounted*) atau batas *timeout* tercapai.

### 2. Mock Service Worker (MSW v2) Interception
MSW tidak menimpa (*monkey-patch*) `window.fetch` secara manual. 
* Di lingkungan browser (E2E), MSW mendaftarkan *Service Worker* nyata via API `navigator.serviceWorker` yang memotong network requests pada level protokol HTTP sistem operasi peramban.
* Di lingkungan JSDOM/Node.js, MSW menggunakan library `@mswjs/interceptors` yang mencegat modul dasar `http`, `https`, dan implementasi global `fetch` bawaan Node runtime secara transparan.

### 3. Playwright Process Model
Playwright berkomunikasi langsung dengan proses browser engines (Chromium, Firefox, WebKit) melalui protokol internal tingkat rendah (seperti *Chrome DevTools Protocol - CDP* via WebSocket IPC). Hal ini menghilangkan latensi *WebDriver* tradisional, memungkinkan determinisme tingkat tinggi via *auto-waiting* (otomatis menunggu elemen terlihat, stabil, dan dapat menerima aksi sebelum mengeksekusi klik).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Flakiness: Musuh Terbesar Skala Enterprise
*Test flakiness* terjadi ketika pengujian menghasilkan status pass/fail yang berbeda pada commit kode yang sama tanpa modifikasi apa pun. Penyebab utama pada React meliputi:
1. **Asynchronous Race Conditions**: Mengandalkan `setTimeout` buatan manusia ketimbang mendengarkan perubahan DOM via `waitFor` atau penanda accessibility (`aria-busy`).
2. **Shared State Pollution**: Penyimpanan modul global (seperti Singleton client, in-memory caches React Query, atau global event emitter) yang tidak di-*reset* antar pengujian.
3. **Improper Async Act Warning**: Terjadi saat mutasi state dieksekusi setelah pengujian selesai berjalan, menunjukkan adanya operasi asynchronous tak tertangani yang bocor dari daur hidup komponen.

### Accessibility-Driven Selectors Hierarchy
Gunakan hierarki prioritas pemilihan elemen berbasis RTL:
1. **Dapat Diakses Semua Orang (Accessible to Everyone)**:
   * `getByRole`: Merefleksikan bagaimana screen reader membedah Accessibility Tree (`role="button"`, `role="heading"`, name mapping via `aria-label` / inner text).
   * `getByLabelText`: Ideal untuk form inputs.
   * `getByPlaceholderText`, `getByText`, `getByDisplayValue`.
2. **Semantic Queries**:
   * `getByAltText`, `getByTitle`.
3. **Test IDs (Escape Hatches)**:
   * `getByTestId`: Hanya digunakan jika konteks dinamis tidak memiliki representasi semantik atau teks berubah secara dinamis berdasarkan lokalisasi (i18n).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi custom hook `useDebouncedSearch` beserta rangkaian unit test komprehensif menggunakan Vitest.

### File: `src/hooks/useDebouncedSearch.ts`
```typescript
import { useState, useEffect } from 'react';

export interface UseDebouncedSearchResult<T> {
  query: string;
  setQuery: (q: string) => void;
  debouncedQuery: string;
  isDebouncing: boolean;
}

export function useDebouncedSearch(delay = 300): UseDebouncedSearchResult<string> {
  const [query, setQuery] = useState<string>('');
  const [debouncedQuery, setDebouncedQuery] = useState<string>('');
  const [isDebouncing, setIsDebouncing] = useState<boolean>(false);

  useEffect(() => {
    if (query === debouncedQuery) {
      setIsDebouncing(false);
      return;
    }

    setIsDebouncing(true);
    const handler = setTimeout(() => {
      setDebouncedQuery(query);
      setIsDebouncing(false);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [query, delay, debouncedQuery]);

  return { query, setQuery, debouncedQuery, isDebouncing };
}
```

### File: `src/hooks/useDebouncedSearch.test.ts`
```typescript
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDebouncedSearch } from './useDebouncedSearch';

describe('useDebouncedSearch Unit Test Suite', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('harus mengembalikan initial state yang valid', () => {
    const { result } = renderHook(() => useDebouncedSearch(500));

    expect(result.current.query).toBe('');
    expect(result.current.debouncedQuery).toBe('');
    expect(result.current.isDebouncing).toBe(false);
  });

  it('harus menunda pembaruan nilai debouncedQuery sesuai durasi delay', () => {
    const delay = 500;
    const { result } = renderHook(() => useDebouncedSearch(delay));

    act(() => {
      result.current.setQuery('Microfrontends');
    });

    expect(result.current.query).toBe('Microfrontends');
    expect(result.current.debouncedQuery).toBe('');
    expect(result.current.isDebouncing).toBe(true);

    // Fast-forward waktu secara terkontrol sebelum timer selesai
    act(() => {
      vi.advanceTimersByTime(250);
    });

    expect(result.current.debouncedQuery).toBe('');
    expect(result.current.isDebouncing).toBe(true);

    // Selesaikan sisa durasi delay
    act(() => {
      vi.advanceTimersByTime(250);
    });

    expect(result.current.debouncedQuery).toBe('Microfrontends');
    expect(result.current.isDebouncing).toBe(false);
  });

  it('harus membatalkan timer sebelumnya jika nilai query diperbarui kembali sebelum batas waktu berakhir', () => {
    const delay = 400;
    const { result } = renderHook(() => useDebouncedSearch(delay));

    act(() => {
      result.current.setQuery('React');
    });
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(result.current.debouncedQuery).toBe('');

    // Trigger update baru sebelum 400ms tercapai
    act(() => {
      result.current.setQuery('React Testing');
    });
    act(() => {
      vi.advanceTimersByTime(200);
    });
    
    // Total waktu sejak kata pertama = 400ms, tapi timer baru di-reset 200ms lalu
    expect(result.current.debouncedQuery).toBe('');
    expect(result.current.isDebouncing).toBe(true);

    // Selesaikan sisa timer yang baru
    act(() => {
      vi.advanceTimersByTime(200);
    });

    expect(result.current.debouncedQuery).toBe('React Testing');
    expect(result.current.isDebouncing).toBe(false);
  });
});
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Pada implementasi `useDebouncedSearch.test.ts`:
1. `vi.useFakeTimers()`: Menginstruksikan runtime Vitest untuk mengabaikan pewaktu CPU internal dan membungkus `setTimeout`/`clearTimeout` dengan mock deterministik.
2. `vi.useRealTimers()`: Pada hook siklus teardown `afterEach`, pewaktu dikembalikan ke state native sistem untuk mengisolasi efek samping terhadap *test suite* lainnya.
3. `renderHook(() => useDebouncedSearch(delay))`: Membungkus eksekusi custom hook ke dalam komponen virtual sintetis internal RTL, mengekspos properti `result.current`.
4. `act(() => { ... })`: Memastikan semua siklus pembaruan state reaktif React dan pengosongan antrean mikro-tugas (*microtask queue*) diselesaikan sebelum eksekusi berlanjut ke baris assertion `expect()`.
5. `vi.advanceTimersByTime(250)`: Secara presisi memajukan jam virtual sebesar 250 milidetik tanpa memblokir thread eksekusi OS, membuktikan ketahanan logika pembersihan (*cleanup*) `clearTimeout`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Financial Transfer Execution Engine
Sebuah platform perbankan digital enterprise memiliki alur transfer dana kritis:
* Komponen menerima input akun target, nominal, dan catatan transfer.
* Validasi input terjadi secara real-time via validasi skema.
* Mengambil data limit harian via REST API secara asinkron.
* Eksekusi transfer memicu dialog konfirmasi multi-step dengan state loading interaktif, mitigasi *double-click submit*, error recovery saat saldo tidak mencukupi, dan redirect halaman dengan state transaksi.

Kita akan membangun:
1. **Mock Service Worker Integration Layer** untuk network interception.
2. **Integration Test Suite** menggunakan RTL untuk menguji flow transfer secara holistik.
3. **Playwright E2E Test Suite** untuk menguji sistem di browser sesungguhnya.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

### 1. MSW Network Boundary Definition
File: `src/mocks/handlers.ts`
```typescript
import { http, HttpResponse, delay } from 'msw';

export interface TransferPayload {
  recipientId: string;
  amount: number;
}

export const handlers = [
  http.get('/api/v1/account/limits', async () => {
    return HttpResponse.json({
      dailyLimit: 50000000,
      remainingLimit: 25000000,
    });
  }),

  http.post('/api/v1/transfers', async ({ request }) => {
    const body = (await request.json()) as TransferPayload;
    
    // Simulasi latensi jaringan
    await delay(100);

    if (body.amount > 25000000) {
      return HttpResponse.json(
        { message: 'Transaksi melebihi sisa limit harian.' },
        { status: 422 }
      );
    }

    return HttpResponse.json({
      transactionId: 'TX-99882233',
      status: 'SUCCESS',
      amount: body.amount,
      recipientId: body.recipientId,
      timestamp: new Date().toISOString(),
    });
  }),
];
```

File: `src/mocks/server.ts`
```typescript
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
```

### 2. Implementation Component
File: `src/features/transfers/TransferForm.tsx`
```typescript
import React, { useState, useEffect } from 'react';

export const TransferForm: React.FC = () => {
  const [recipientId, setRecipientId] = useState('');
  const [amount, setAmount] = useState<number | ''>('');
  const [remainingLimit, setRemainingLimit] = useState<number | null>(null);
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [txId, setTxId] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    fetch('/api/v1/account/limits')
      .then((res) => res.json())
      .then((data) => {
        if (isMounted) setRemainingLimit(data.remainingLimit);
      })
      .catch(() => {
        if (isMounted) setErrorMessage('Gagal memuat limit harian');
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!amount || Number(amount) <= 0 || !recipientId) return;

    setStatus('submitting');
    setErrorMessage(null);

    try {
      const res = await fetch('/api/v1/transfers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recipientId, amount: Number(amount) }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || 'Gagal memproses transaksi');
      }

      setTxId(data.transactionId);
      setStatus('success');
    } catch (err: unknown) {
      setStatus('error');
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Terjadi kesalahan internal');
      }
    }
  };

  if (status === 'success') {
    return (
      <div role="status" aria-label="Bukti Transfer">
        <h2>Transfer Berhasil!</h2>
        <p>ID Transaksi: {txId}</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} aria-label="Form Transfer Dana">
      <h2>Transfer Dana</h2>
      
      {remainingLimit !== null && (
        <p aria-live="polite">Sisa Limit Harian: Rp {remainingLimit.toLocaleString('id-ID')}</p>
      )}

      {errorMessage && (
        <div role="alert" style={{ color: 'red' }}>
          {errorMessage}
        </div>
      )}

      <div>
        <label htmlFor="recipient">Nomor Rekening Tujuan</label>
        <input
          id="recipient"
          type="text"
          value={recipientId}
          onChange={(e) => setRecipientId(e.target.value)}
          disabled={status === 'submitting'}
          required
        />
      </div>

      <div>
        <label htmlFor="amount">Jumlah Transfer</label>
        <input
          id="amount"
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value === '' ? '' : Number(e.target.value))}
          disabled={status === 'submitting'}
          required
        />
      </div>

      <button type="submit" disabled={status === 'submitting'}>
        {status === 'submitting' ? 'Memproses...' : 'Kirim Sekarang'}
      </button>
    </form>
  );
};
```

### 3. Integration Testing Suite (Vitest + RTL + MSW)
File: `src/features/transfers/TransferForm.test.tsx`
```typescript
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { server } from '../../mocks/server';
import { TransferForm } from './TransferForm';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('TransferForm Integration Suite', () => {
  it('harus merender form, mengambil data limit, dan berhasil mengeksekusi transfer', async () => {
    const user = userEvent.setup();
    render(<TransferForm />);

    // Memverifikasi pengambilan data limit harian (asynchronous data fetch)
    const limitInfo = await screen.findByText(/Sisa Limit Harian: Rp 25\.000\.000/i);
    expect(limitInfo).toBeInTheDocument();

    // Mengisi form interaktif
    const recipientInput = screen.getByRole('textbox', { name: /nomor rekening tujuan/i });
    const amountInput = screen.getByRole('spinbutton', { name: /jumlah transfer/i });
    const submitBtn = screen.getByRole('button', { name: /kirim sekarang/i });

    await user.type(recipientInput, '081299887766');
    await user.type(amountInput, '5000000');

    expect(submitBtn).toBeEnabled();
    await user.click(submitBtn);

    // State submitting verifikasi
    expect(screen.getByRole('button', { name: /memproses\.\.\./i })).toBeDisabled();

    // Verifikasi output akhir sukses
    const successHeader = await screen.findByRole('heading', { name: /transfer berhasil!/i });
    expect(successHeader).toBeInTheDocument();
    expect(screen.getByText(/ID Transaksi: TX-99882233/i)).toBeInTheDocument();
  });

  it('harus menampilkan pesan error saat transfer melebihi sisa limit transaksi', async () => {
    const user = userEvent.setup();
    render(<TransferForm />);

    await screen.findByText(/Sisa Limit Harian:/i);

    await user.type(screen.getByRole('textbox', { name: /nomor rekening tujuan/i }), '081299887766');
    await user.type(screen.getByRole('spinbutton', { name: /jumlah transfer/i }), '30000000');

    await user.click(screen.getByRole('button', { name: /kirim sekarang/i }));

    const errorAlert = await screen.findByRole('alert');
    expect(errorAlert).toHaveTextContent(/Transaksi melebihi sisa limit harian\./i);
    
    // Memastikan tombol kembali interaktif setelah gagal
    expect(screen.getByRole('button', { name: /kirim sekarang/i })).toBeEnabled();
  });
});
```

### 4. Playwright End-to-End Testing Suite
File: `e2e/pages/TransferPage.ts` (Page Object Model)
```typescript
import { Page, Locator, expect } from '@playwright/test';

export class TransferPage {
  readonly page: Page;
  readonly recipientInput: Locator;
  readonly amountInput: Locator;
  readonly submitButton: Locator;
  readonly successHeader: Locator;
  readonly alertBanner: Locator;

  constructor(page: Page) {
    this.page = page;
    this.recipientInput = page.getByRole('textbox', { name: /nomor rekening tujuan/i });
    this.amountInput = page.getByRole('spinbutton', { name: /jumlah transfer/i });
    this.submitButton = page.getByRole('button', { name: /kirim sekarang/i });
    this.successHeader = page.getByRole('heading', { name: /transfer berhasil!/i });
    this.alertBanner = page.getByRole('alert');
  }

  async goto() {
    await this.page.goto('/transfers');
  }

  async executeTransfer(recipient: string, amount: string) {
    await this.recipientInput.fill(recipient);
    await this.amountInput.fill(amount);
    await this.submitButton.click();
  }

  async assertTransferSuccess(txPrefix: string) {
    await expect(this.successHeader).toBeVisible();
    await expect(this.page.getByText(new RegExp(txPrefix, 'i'))).toBeVisible();
  }
}
```

File: `e2e/transfers.spec.ts`
```typescript
import { test, expect } from '@playwright/test';
import { TransferPage } from './pages/TransferPage';

test.describe('E2E Transfer Funds Journey', () => {
  test.beforeEach(async ({ page }) => {
    // Simulasi otentikasi enterprise lewat cookie / storage state injection
    await page.context().addCookies([
      {
        name: 'session_token',
        value: 'mock_enterprise_jwt_token',
        domain: 'localhost',
        path: '/',
        httpOnly: true,
        secure: false,
        sameSite: 'Lax',
      },
    ]);
  });

  test('User berhasil melakukan transfer normal hingga terminal screen', async ({ page }) => {
    const transferPage = new TransferPage(page);
    await transferPage.goto();

    await transferPage.executeTransfer('9876543210', '1500000');
    await transferPage.assertTransferSuccess('TX-');
  });

  test('Sistem memblokir eksekusi jika input invalid secara native browser validation', async ({ page }) => {
    const transferPage = new TransferPage(page);
    await transferPage.goto();

    // Klik submit tanpa mengisi input 'required'
    await transferPage.submitButton.click();

    // Assert URL tidak berubah dan form tidak submit
    await expect(transferPage.successHeader).not.toBeVisible();
  });
});
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Evaluasi | Unit Testing (Pure Vitest) | Integration Testing (RTL + MSW) | End-to-End Testing (Playwright) |
| :--- | :--- | :--- | :--- |
| **Eksekusi Waktu (Execution Speed)** | Sangat Cepat (~1-5ms per test) | Cepat (~50-300ms per test) | Lambat (~1-5 detik per test) |
| **Tingkat Keyakinan (Confidence Level)** | Rendah (Hanya isolasi logika) | Tinggi (Menguji kolaborasi komponen & DOM) | Maksimal (Browser nyata, environment identik) |
| **Biaya Pemeliharaan (Maintenance Cost)** | Rendah | Menengah | Tinggi (Rentan flakiness infrastruktur jaringan) |
| **Isolasi Kegagalan (Failure Localization)** | Sangat Presisi (Menunjuk baris kode spesifik) | Cukup Presisi (Menunjuk komponen/boundary) | Luas (Perlu inspeksi log/video/trace) |
| **Ketergantungan Infrastruktur** | Nihil (Node.js engine murni) | JSDOM/Node Interceptors | Headless Browser binaries, display server, OS APIs |
| **Optimal Coverage Target** | Domain logic, Math, Custom Hooks | 70% dari seluruh alur aplikasi UI | Happy Path kritis & Alur Finansial Inti |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Memory Leaks pada JSDOM Antar Uji Coba
* **Mekanisme Kegagalan**: Objek `window`, event listener global (`window.addEventListener('resize', ...)`), atau modul cache tidak dibersihkan saat rendering banyak komponen di satu runner instance.
* **Mitigasi**: Pastikan React unmount dipanggil secara otomatis oleh RTL dan gunakan pembersihan eksplisit pada `afterEach`:
```typescript
afterEach(() => {
  vi.clearAllMocks();
  // RTL secara default memanggil cleanup(), namun jika menggunakan custom render wrapper:
  // cleanup();
});
```

### 2. Flaky Async Polling Timeouts
* **Mekanisme Kegagalan**: `waitFor` bawaan RTL memiliki default timeout 1000ms. Pada CI runner dengan CPU throttling (misal GitHub Actions shared runner), operasi async valid memakan waktu 1100ms dan menyebabkan status *failed*.
* **Mitigasi**: Konfigurasikan global async timeout secara terpusat pada file konfigurasi setup Vitest:
```typescript
import { configure } from '@testing-library/react';
configure({ asyncUtilTimeout: 4500 });
```

### 3. Request Interception Leaks pada Parallel Execution
* **Mekanisme Kegagalan**: Menggunakan `server.use()` di satu test tanpa memanggil `server.resetHandlers()` di `afterEach`, menyebabkan mock handler dari file A bocor dan mengeksekusi assertion palsu di file B.
* **Mitigasi**: Definisikan konfigurasi lifecycle MSW secara seragam di `setupFiles` Vitest.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Query Menggunakan CSS Class atau Komponen Internal
```typescript
// ❌ BURUK: Sangat rapuh terhadap perubahan refactoring CSS/HTML
const submitBtn = container.querySelector('.btn-primary-blue-submit');
expect(submitBtn).toBeDefined();

// ✅ BENAR: Mengikuti standar Aksesibilitas (Role & Accessible Name)
const submitBtn = screen.getByRole('button', { name: /kirim/i });
expect(submitBtn).toBeInTheDocument();
```

### Anti-Pattern 2: Membungkus Pemanggilan RTL dengan `act()` Manual Tanpa Alasan
```typescript
// ❌ BURUK: act() redundan, fireEvent sudah usang
await act(async () => {
  fireEvent.click(button);
});

// ✅ BENAR: userEvent secara otomatis membungkus operasi dalam act()
await user.click(button);
```

### Anti-Pattern 3: Menggunakan `waitFor` untuk Membungkus Assertion Sederhana
```typescript
// ❌ BURUK: Memboroskan polling loop untuk synchronous query
await waitFor(() => {
  expect(screen.getByText('Hello')).toBeInTheDocument();
});

// ✅ BENAR: Gunakan findByText secara langsung
expect(await screen.findByText('Hello')).toBeInTheDocument();
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Factory Method Pattern untuk Mock Data**: Hindari hardcoding literal JSON yang berulang di setiap test file. Gunakan libraries seperti `@faker-js/faker` atau Factory builders.
2. **Page Object Model (POM) pada Playwright**: Selalu enkapsulasi interaksi selector DOM ke dalam class modular untuk menjaga maintainability test saat struktur DOM berubah.
3. **Konfigurasi `onUnhandledRequest: 'error'`**: Paksa suite test gagal jika ada request API jaringan yang tidak didefinisikan mock-nya di MSW, untuk menghindari *silent fallback* ke jaringan publik.
4. **Isolasi Otentikasi Menggunakan Storage State**: Hindari login manual via antarmuka UI di setiap test Playwright. Lakukan autentikasi satu kali via API setup project, lalu bagikan file `storageState.json` ke seluruh browser context.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI

### Vitest Threads & JSDOM Pool Optimization
JSDOM memiliki footprint memori yang berat. Gunakan konfigurasi pool isolasi thread secara proporsional di `vitest.config.ts`:
```typescript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    pool: 'threads',
    poolOptions: {
      threads: {
        minThreads: 2,
        maxThreads: Math.max(1, Math.floor(navigator.hardwareConcurrency ? navigator.hardwareConcurrency / 2 : 4)),
      },
    },
    isolate: true,
  },
});
```

### Playwright Sharding pada CI Pipeline
Distribusikan eksekusi pengujian E2E ke beberapa mesin virtual terpisah secara paralel menggunakan fitur sharding bawaan:
```bash
# Matrix job 1
npx playwright test --shard=1/4
# Matrix job 2
npx playwright test --shard=2/4
# ...
```

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Sanitasi Kredensial Pengujian**: Jangan pernah menyematkan kata sandi, production tokens, atau PII (Personally Identifiable Information) ke dalam assertions atau fixtures repository Git. Gunakan variabel lingkungan yang disuntikkan secara dinamis saat runtime CI.
2. **Pemberian Izin Eksplisit di Playwright**: Kunci permissions browser Playwright agar hanya mengakses domain yang diizinkan untuk mencegah XSS yang memicu eksfiltrasi data via domain lokal:
```typescript
const context = await browser.newContext({
  permissions: [], // Blokir akses geolocation, kamera, notifikasi secara eksplisit
});
```
3. **Pemberian Mocking pada Sensitif Storage**: Saat menguji integrasi token JWT pada `localStorage`, pastikan mock storage dibersihkan setelah pengujian untuk mencegah *session leakage* ke dalam context test suite lain.

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### Playwright Trace Viewer