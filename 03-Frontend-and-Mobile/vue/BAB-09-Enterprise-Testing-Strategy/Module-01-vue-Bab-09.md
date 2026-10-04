# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran:** 03-Frontend-and-Mobile
*   **Topik Kurikulum:** Vue.js Enterprise Engineering
*   **Bab:** 09 (Quality Assurance, Testing & Resiliency)
*   **Modul:** 01
*   **Judul Modul:** Enterprise Testing Strategy (Vitest & Playwright)
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat Konseptual:** Vue 3 Composition API, TypeScript Generics, Reactive Systems (Proxy), Vite internals, DOM manipulation, HTTP mock patterns, asynchronous event loop, CI/CD pipeline fundamentals.

---

# SEKSI 02 — LEARNING OBJECTIVES

1.  **Membangun Arsitektur Testing Berlapis (Multi-Tier Testing Matrix):** Mampu mengklasifikasikan pengujian ke dalam Unit, Integration, Component, dan End-to-End (E2E) berdasarkan *confidence-to-cost ratio* menggunakan Vitest dan Playwright.
2.  **Menguasai Vitest Internals & Component Isolation:** Mampu mengonfigurasi Vitest dengan Vite pipeline bawaan, mengisolasi Pinia store, composable functions, dan Vue Test Utils (VTU) v2 secara deterministik tanpa membocorkan state antar-test runner worker.
3.  **Mengimplementasikan Kontrak Testing API (Mocking vs Contract):** Mampu menerapkan Mock Service Worker (MSW) di tingkat unit/integration untuk menguji boundary HTTP tanpa coupling langsung ke implementasi internal UI.
4.  **Menjalankan End-to-End Testing Resilien dengan Playwright:** Mengonfigurasi Playwright untuk skenario distributed auth, cross-browser concurrency, visual regression, dan auto-waiting strategy guna mengeliminasi pengujian non-deterministik (*flaky tests*).
5.  **Mengintegrasikan Testing ke Pipeline CI/CD:** Mengoptimalkan eksekusi paralel melalui dynamic test sharding, artifact capturing (trace viewer/flame graphs), serta audit coverage berbasis V8.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Testing pada aplikasi Vue tingkat enterprise bukanlah sekadar validasi fungsionalitas kode baris per baris (*line coverage vanity metric*), melainkan asuransi perubahan (*change tolerance insurance*).

```
          Mental Model: Testing Pyramid vs Enterprise Testing Diamond

       Traditional Pyramid                        Enterprise Testing Diamond
             / \                                            / \
            /E2E\                                          /E2E\  (Playwright: Critical User Paths)
           /-----\                                        /=====\
          / Integ \                                      / Integ \ (Component + MSW + Pinia Integration)
         /---------\                                     \       / (Vitest + Vue Test Utils)
        /   Unit    \                                     \=====/
       /=============\                                     \Unit/ (Composables, Math, Pure Functions)
                                                            \ - /
```

Di tingkat Enterprise:
1.  **Tinggalkan "Shallow Testing" Membabi Buta:** Melakukan mock pada setiap sub-komponen menciptakan pengujian yang terikat kuat (*tightly coupled*) pada struktur DOM alih-alih perilaku (*behavior*).
2.  **Black-Box vs White-Box:** Unit test murni composables dieksekusi dengan pendekatan *white-box* (menguji state internal & invariants), sedangkan Component dan E2E test dieksekusi dengan pendekatan *black-box* (menguji aksi pengguna dan visual boundary).
3.  **The Inversion of Control Rule:** Kode yang sulit diuji adalah indikator arsitektur yang buruk (*design smell*). Jika composable memerlukan 15 mock dependencies untuk diuji, composable tersebut melanggar *Single Responsibility Principle*.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Alur Eksekusi Vitest & Playwright dalam Pipeline

```
+---------------------------------------------------------------------------------------------------+
|                                      TEST RUNNER EXECUTION FLOW                                   |
+---------------------------------------------------------------------------------------------------+

     [Source Code: Vue 3 + TS]
                 │
                 ├───▶ [Vitest Runner (Node.js Worker Threads)]
                 │         │
                 │         ├── Vite Transformation Pipeline (ESbuild / Rollup AST)
                 │         │
                 │         ├── Environment: happy-dom / jsdom (In-Memory Virtual DOM)
                 │         │
                 │         ├── Mock Layer: MSW (Network-level Interception via Node http/undici)
                 │         │
                 │         ├── Execution Targets:
                 │         │     ├─ Pure Unit (Composables, Services, State Actions)
                 │         │     └─ Component Integration (Vue Test Utils + Real Subcomponents)
                 │         │
                 │         └── Output: V8 Coverage Reports + TAP/JUnit Artifacts
                 │
                 └───▶ [Playwright Runner (Out-of-Process Automation Driver)]
                           │
                           ├── Target: Production-ready Build (Vite Preview / Container)
                           │
                           ├── Protocol: Chrome DevTools Protocol (CDP) / WebDriver BiDi
                           │
                           ├── Isolation: Browser Contexts (Incognito-style ephemeral state)
                           │
                           ├── Execution Targets:
                           │     ├─ Multi-Tenant Auth Workflows (StorageState reuse)
                           │     ├─ Cross-Domain Payment Gateways
                           │     └─ Visual Snapshot Regressions (Pixelmatch Differential)
                           │
                           └── Output: Trace Zip, Video, Network HAR, Screenshots
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Vitest Internals
Vitest beroperasi langsung di atas pipeline resolusi modul Vite:
*   **Vite Dev Server Integration:** Tidak memerlukan kompilasi terpisah via Webpack/Babel. Kode `.vue` diproses secara on-demand menggunakan transformer internal plugin `@vitejs/plugin-vue`.
*   **Worker Pool Multithreading:** Vitest memanfaatkan Node.js `worker_threads` (atau `tinypool`) untuk mendistribusikan test suite ke core CPU secara isolated. Setiap thread memiliki memory heap tersendiri, mengurangi risiko memory leak global yang persisten.
*   **DOM Emulation Engine:** Berbeda dengan Node runtime standar, Vitest menyuntikkan `happy-dom` atau `jsdom` untuk mensimulasikan web APIs (`window`, `document`, `customElements`, `MutationObserver`). `happy-dom` lebih diutamakan karena overhead deserialisasi string DOM 2-3x lebih rendah daripada `jsdom`.

### 2. Playwright Internals
Playwright mengontrol browser engines (Chromium, Firefox, WebKit) pada level kernel browser:
*   **Single WebSocket Connection per Process:** Playwright berkomunikasi via WebSocket tunggal ke browser engine binary, menghindari overhead HTTP polling seperti pada arsitektur legacy Selenium.
*   **Auto-Waiting Engine:** Sebelum mengeksekusi aksi (`click`, `fill`), Playwright mengevaluasi rangkaian *Actionability Checks*:
    1.  *Attached:* Elemen terpasang pada DOM tree.
    2.  *Visible:* Elemen memiliki dimensi bounding box non-zero dan tidak bertumpuk CSS `display: none` / `visibility: hidden`.
    3.  *Stable:* Elemen tidak sedang beranimasi (posisi koordinat identik dalam 2 frame berturut-turut).
    4.  *Enabled:* Elemen form input tidak memiliki attribute `disabled`.
    5.  *Editable:* Input tidak berstatus `read-only`.
*   **Browser Context Isolation:** Playwright tidak membuka instance browser baru per test suite. Satu browser process dapat memiliki ribuan `BrowserContext` yang terisolasi secara kriptografis (cache, cookies, IndexedDB, local storage terpisah), menghemat alokasi memori hingga 80%.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Asynchronous Reactivity Timing di Vue Test Utils
Ketika state Vue diubah di environment pengujian:
```ts
count.value++
```
DOM **tidak langsung** berubah secara sinkron. Vue menjadwalkan update DOM menggunakan microtask queue via scheduler internal (`queueJob`). 

```
State Mutated (count.value++)
     │
     ▼
Dep.notify() ──▶ Reactive Effect Triggered
     │
     ▼
Scheduler pushes job to internal queue
     │
     ▼
[Microtask Checkpoint: await flushPromises() / nextTick()]
     │
     ▼
Jobs executed ──▶ Virtual DOM Patching ──▶ Real DOM Nodes Updated
```

Jika assertion dieksekusi secara sinkron sebelum microtask checkpoint diselesaikan, test akan membaca state DOM yang stale:
```ts
// GAGAL: DOM masih membaca nilai lama
wrapper.find('button').trigger('click');
expect(wrapper.find('span').text()).toBe('1'); 

// SUKSES: Memaksa engine mengosongkan microtask queue
await wrapper.find('button').trigger('click');
// atau: await flushPromises();
expect(wrapper.find('span').text()).toBe('1');
```

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi isolasi composable business-logic dengan dependency injection state management:

### File: `src/composables/useCheckoutEngine.ts`
```typescript
import { ref, computed, type Ref } from 'vue';
import { defineStore } from 'pinia';

export interface CartItem {
  id: string;
  name: string;
  price: number;
  quantity: number;
}

export const useCartStore = defineStore('cart', () => {
  const items: Ref<CartItem[]> = ref([]);
  
  function addItem(item: CartItem) {
    const existing = items.value.find(i => i.id === item.id);
    if (existing) {
      existing.quantity += item.quantity;
    } else {
      items.value.push({ ...item });
    }
  }

  const subtotal = computed(() => 
    items.value.reduce((acc, curr) => acc + (curr.price * curr.quantity), 0)
  );

  return { items, addItem, subtotal };
});

export function useCheckoutEngine() {
  const cart = useCartStore();
  const taxRate = 0.11; // 11% PPN
  const isProcessing = ref(false);
  const checkoutError = ref<string | null>(null);

  const grandTotal = computed(() => {
    return cart.subtotal + (cart.subtotal * taxRate);
  });

  async function processOrder(paymentGatewayClient: (amount: number) => Promise<{ success: boolean; txId?: string }>) {
    if (cart.items.length === 0) {
      checkoutError.value = 'CART_EMPTY';
      return false;
    }

    isProcessing.value = true;
    checkoutError.value = null;

    try {
      const response = await paymentGatewayClient(grandTotal.value);
      if (!response.success) {
        throw new Error('PAYMENT_REJECTED');
      }
      cart.items = [];
      return true;
    } catch (err: unknown) {
      checkoutError.value = err instanceof Error ? err.message : 'UNKNOWN_ERROR';
      return false;
    } finally {
      isProcessing.value = false;
    }
  }

  return {
    grandTotal,
    isProcessing,
    checkoutError,
    processOrder
  };
}
```

### File: `src/composables/__tests__/useCheckoutEngine.spec.ts`
```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useCartStore, useCheckoutEngine } from '../useCheckoutEngine';

describe('useCheckoutEngine Enterprise Unit Test', () => {
  beforeEach(() => {
    // Isolasi state Pinia antar eksekusi test
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('harus menghitung grandTotal dengan pajak 11% secara akurat', () => {
    const cart = useCartStore();
    const { grandTotal } = useCheckoutEngine();

    cart.addItem({ id: 'SKU-001', name: 'Mechanical Keyboard', price: 1000000, quantity: 2 });
    
    // Subtotal: 2,000,000. GrandTotal (+11%): 2,220,000
    expect(cart.subtotal).toBe(2000000);
    expect(grandTotal.value).toBe(2220000);
  });

  it('harus menggagalkan proses jika keranjang kosong tanpa memanggil payment client', async () => {
    const { processOrder, checkoutError, isProcessing } = useCheckoutEngine();
    const mockPaymentClient = vi.fn();

    const result = await processOrder(mockPaymentClient);

    expect(result).toBe(false);
    expect(checkoutError.value).toBe('CART_EMPTY');
    expect(mockPaymentClient).not.toHaveBeenCalled();
    expect(isProcessing.value).toBe(false);
  });

  it('harus mengosongkan keranjang ketika pembayaran berhasil', async () => {
    const cart = useCartStore();
    const { processOrder, checkoutError } = useCheckoutEngine();
    
    cart.addItem({ id: 'SKU-002', name: 'Mouse Wireless', price: 500000, quantity: 1 });
    
    const mockPaymentClient = vi.fn().mockResolvedValue({ success: true, txId: 'TX-9981' });

    const result = await processOrder(mockPaymentClient);

    expect(result).toBe(true);
    expect(cart.items.length).toBe(0);
    expect(checkoutError.value).toBeNull();
    expect(mockPaymentClient).toHaveBeenCalledWith(555000);
  });
});
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Meninjau `src/composables/__tests__/useCheckoutEngine.spec.ts`:
*   **Baris 7-9 (`setActivePinia(createPinia())`):**
    *   Mekanisme: Membuat instance root Pinia baru secara in-memory dan menjadikannya active scope.
    *   Mengapa krusial: Jika diabaikan, state antar unit test akan tercemar (*cross-test pollution*). Item yang ditambahkan di Test A akan tetap berada di memori ketika Test B berjalan.
*   **Baris 10 (`vi.clearAllMocks()`):**
    *   Membersihkan tracking history call count, instances, dan invocation arguments dari mock functions. Menjamin integritas assertion `mockPaymentClient`.
*   **Baris 17 (`cart.addItem(...)`):**
    *   Menguji composable via interaksi state langsung (kontrak antar-modul), bukan mocking store. Ini memvalidasi interaksi reaktivitas riil antara `useCartStore` dan `useCheckoutEngine`.
*   **Baris 38 (`vi.fn().mockResolvedValue(...)`):**
    *   Mengganti external dependency (`paymentGatewayClient`) dengan sinonim mock yang mengembalikan Promise resolve. Pendekatan ini merupakan *Dependency Injection* murni tanpa memanipulasi network stack global.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Enterprise Multi-Currency Order Checkout Matrix
Sebuah platform B2B SaaS memproses transaksi ribuan enterprise user. Masalah yang sering terjadi di environment CI:
1.  **Vitest Network Race Conditions:** Developer melakukan `vi.spyOn(global, 'fetch')` secara manual di berbagai file. Ketika tests berjalan paralel via worker threads, mock fetch saling menimpa, menghasilkan HTTP 404/500 acak di CI runner.
2.  **Playwright Authentication Bottleneck:** E2E suite mengeksekusi login UI via form submission untuk 150 skenario test, mengakibatkan durasi pipeline melonjak hingga 45 menit dan memicu *rate limiting* pada identity provider (IdP).

### Solusi Arsitektur
1.  Standardisasi intersep jaringan level Vitest menggunakan **Mock Service Worker (MSW)**. MSW bekerja di level node runtime via interceptor internal undici/http, terisolasi per lifecycle process tanpa mengotori `globalThis.fetch`.
2.  Implementasi pola **Playwright Global Authentication Caching** via `storageState`, di mana sesi login dieksekusi satu kali di fase bootstrap CI, disimpan sebagai representasi file JSON terenkripsi, lalu diinjeksikan secara transparan ke seluruh instance `BrowserContext`.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

### 1. Vitest + MSW Component Testing

#### File: `src/mocks/handlers.ts`
```typescript
import { http, HttpResponse } from 'msw';

export const handlers = [
  http.post('https://api.enterprise.com/v1/orders', async ({ request }) => {
    const payload = await request.json() as { amount: number; currency: string };
    
    if (payload.amount > 50000000) {
      return HttpResponse.json(
        { code: 'CREDIT_LIMIT_EXCEEDED', message: 'Corporate credit limit reached' },
        { status: 422 }
      );
    }

    return HttpResponse.json({
      orderId: 'ORD-90210',
      status: 'CONFIRMED',
      timestamp: new Date().toISOString()
    }, { status: 201 });
  })
];
```

#### File: `src/components/EnterpriseCheckout.vue`
```vue
<script setup lang="ts">
import { ref } from 'vue';

const props = defineProps<{
  companyId: string;
  totalAmount: number;
  currency: string;
}>();

const emit = defineEmits<{
  (e: 'order-success', orderId: string): void;
  (e: 'order-failed', errorCode: string): void;
}>();

const isSubmitting = ref(false);
const errorMessage = ref<string | null>(null);

async function handleCheckout() {
  isSubmitting.value = true;
  errorMessage.value = null;

  try {
    const res = await fetch('https://api.enterprise.com/v1/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        companyId: props.companyId,
        amount: props.totalAmount,
        currency: props.currency
      })
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.code || 'UNKNOWN_ERROR');
    }

    emit('order-success', data.orderId);
  } catch (err: unknown) {
    const code = err instanceof Error ? err.message : 'INTERNAL_EXCEPTION';
    errorMessage.value = code;
    emit('order-failed', code);
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <div class="checkout-panel">
    <h3>Corporate Billing: {{ companyId }}</h3>
    <p data-test="total-display">Total: {{ totalAmount }} {{ currency }}</p>
    
    <div v-if="errorMessage" role="alert" class="error-banner">
      {{ errorMessage }}
    </div>

    <button 
      type="button"
      :disabled="isSubmitting"
      data-test="submit-order-btn"
      @click="handleCheckout"
    >
      <span v-if="isSubmitting">Processing Transaction...</span>
      <span v-else>Authorize & Place Order</span>
    </button>
  </div>
</template>
```

#### File: `src/components/__tests__/EnterpriseCheckout.spec.ts`
```typescript
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { setupServer } from 'msw/node';
import { handlers } from '../../mocks/handlers';
import EnterpriseCheckout from '../EnterpriseCheckout.vue';

const server = setupServer(...handlers);

describe('<EnterpriseCheckout /> Component Integration', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());

  it('mengirim payload transaksi dan memancarkan event order-success ketika API berhasil', async () => {
    const wrapper = mount(EnterpriseCheckout, {
      props: {
        companyId: 'CORP-CORP-44',
        totalAmount: 15000000,
        currency: 'IDR'
      }
    });

    const submitBtn = wrapper.find('[data-test="submit-order-btn"]');
    expect(submitBtn.attributes('disabled')).toBeUndefined();

    await submitBtn.trigger('click');

    // UI state assertion selama processing (sebelum network resolve)
    expect(submitBtn.attributes('disabled')).toBeDefined();
    expect(wrapper.text()).toContain('Processing Transaction...');

    // Tunggu update microtask & network tick
    await vi.waitFor(() => {
      expect(wrapper.emitted('order-success')).toBeTruthy();
    });

    expect(wrapper.emitted('order-success')![0]).toEqual(['ORD-90210']);
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
  });

  it('menampilkan alert error dan memancarkan order-failed ketika credit limit exceeded', async () => {
    const wrapper = mount(EnterpriseCheckout, {
      props: {
        companyId: 'CORP-CORP-44',
        totalAmount: 60000000, // Memicu MSW mock boundary (amount > 50,000,000)
        currency: 'IDR'
      }
    });

    await wrapper.find('[data-test="submit-order-btn"]').trigger('click');

    await vi.waitFor(() => {
      expect(wrapper.find('[role="alert"]').exists()).toBe(true);
    });

    expect(wrapper.find('[role="alert"]').text()).toBe('CREDIT_LIMIT_EXCEEDED');
    expect(wrapper.emitted('order-failed')![0]).toEqual(['CREDIT_LIMIT_EXCEEDED']);
  });
});
```

---

### 2. Playwright Enterprise End-to-End Suite

#### File: `playwright.config.ts`
```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  expect: {
    timeout: 5000
  },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? '100%' : undefined,
  reporter: [
    ['html', { open: 'never' }],
    ['junit', { outputFile: 'results.xml' }]
  ],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:4173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },
  projects: [
    {
      name: 'setup',
      testMatch: /.*\.setup\.ts/
    },
    {
      name: 'Chromium E2E',
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'e2e/.auth/enterprise-user.json'
      }
    }
  ],
  webServer: {
    command: 'npm run build && npm run preview',
    url: 'http://localhost:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 120000
  }
});
```

#### File: `e2e/auth.setup.ts`
```typescript
import { test as setup, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const authFile = path.join(__dirname, '.auth/enterprise-user.json');

setup('authenticate enterprise user via session storage injection', async ({ page }) => {
  // Pastikan folder .auth tersedia
  const dir = path.dirname(authFile);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  await page.goto('/login');
  await page.locator('#corporate-email').fill('cfo@enterprise-corp.com');
  await page.locator('#corporate-password').fill('P@ssw0rdSecureEnterprise!2025');
  await page.locator('button[type="submit"]').click();

  // Tunggu konfirmasi URL dashboard & validasi indikator login
  await page.waitForURL('/dashboard');
  await expect(page.getByRole('heading', { name: 'Executive Overview' })).toBeVisible();

  // Simpan state cookie + localStorage
  await page.context().storageState({ path: authFile });
});
```

#### File: `e2e/checkout-flow.spec.ts`
```typescript
import { test, expect } from '@playwright/test';

test.describe('B2B Enterprise Procurement Suite', () => {
  test('harus memvalidasi multi-item purchase order hingga order invoice page', async ({ page }) => {
    // Navigasi langsung ke inventory (sudah bypass auth berkat storageState)
    await page.goto('/catalog/procurement');

    // Filter produk enterprise
    const searchInput = page.getByPlaceholder('Search enterprise catalog...');
    await searchInput.fill('Ultra-Bandwidth Server Rack');
    await page.keyboard.press('Enter');

    // Pilih item dan tambahkan ke pesanan
    const productCard = page.locator('.product-card').filter({ hasText: 'Ultra-Bandwidth Server Rack' });
    await expect(productCard).toBeVisible();
    
    // Validasi auto-waiting Playwright pada tombol yang dinamis
    const addToOrderBtn = productCard.getByRole('button', { name: 'Add to Order' });
    await addToOrderBtn.click();

    // Verifikasi badge floating cart berubah secara reaktif
    const cartBadge = page.locator('[data-test="cart-item-count"]');
    await expect(cartBadge).toHaveText('1');

    // Masuk ke checkout overview
    await page.locator('[data-test="floating-cart-trigger"]').click();
    await page.getByRole('link', { name: 'Proceed to Corporate Review' }).click();

    await page.waitForURL('/checkout/review');

    // Eksekusi checkout modal authorization
    const confirmOrderBtn = page.locator('[data-test="submit-order-btn"]');
    await expect(confirmOrderBtn).toBeEnabled();
    await confirmOrderBtn.click();

    // Verifikasi redirection ke Invoice Success page
    await expect(page).toHaveURL(/\/checkout\/invoices\/ORD-/);
    
    // Assertion konten faktur PDF download button
    const downloadInvoiceBtn = page.getByRole('button', { name: 'Download Tax Invoice (PDF)' });
    await expect(downloadInvoiceBtn).toBeVisible();
  });
});
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Dimensi | Unit Tests (Vitest) | Component Integration (VTU + MSW) | End-to-End Tests (Playwright) |
| :--- | :--- | :--- | :--- |
| **Eksekusi Speed** | ~1 - 5 ms per test | ~50 - 200 ms per test | ~1.500 - 8.000 ms per test |
| **Flakiness Risk** | Sangat Rendah (< 0.1%) | Rendah (< 1%) | Sedang - Tinggi (3 - 8%) |
| **Refactoring Resilience** | Rendah (Gampang pecah jika code signature berubah) | Tinggi (Menguji kontrak visual/state) | Maksimal (Agnostik terhadap framework internal) |
| **Resource Consumption** | Rendah (Node CPU/RAM minimal) | Sedang (In-memory DOM heap) | Sangat Berat (Headless Browser processes) |
| **Confidence Level** | Rendah (Hanya menguji isolated logic) | Tinggi (Menguji Vue lifecycle & rendering) | Absolut (Menguji real browser engine & CSS) |
| **Lokasi Identifikasi Bug** | Presisi tinggi (Spesifik baris & fungsi) | Presisi sedang (Komponen level) | Presisi rendah (Tracing menyeluruh dari UI ke Backend) |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Asynchronous DOM Timing Trap
**Masalah:** Menggunakan native assertion Node `expect()` pada perubahan UI reaktif tanpa menunggu rendering cycle.
```typescript
// PITFALL
wrapper.find('input').setValue('Enterprise Inc');
expect(wrapper.find('.preview-name').text()).toBe('Enterprise Inc'); // FAIL!
```
**Mitigasi:** `setValue()` dan `trigger()` pada Vue Test Utils v2 adalah operasi *asinkron*. Gunakan `await`:
```typescript
await wrapper.find('input').setValue('Enterprise Inc');
expect(wrapper.find('.preview-name').text()).toBe('Enterprise Inc'); // PASS!
```

### 2. Leaking Event Listeners / Timers di Vitest
**Masalah:** Composable yang menggunakan `setInterval` atau global `window.addEventListener` tidak di-teardown, mengakibatkan alokasi memory leak antar run pada thread yang sama.
**Mitigasi:** 
```typescript
afterEach(() => {
  vi.clearAllTimers();
  vi.restoreAllMocks();
});
// Konfigurasi vitest.config.ts:
// poolOptions: { threads: { isolate: true } }
```

### 3. Playwright Strict Mode Violation
**Masalah:** Selector mencocokkan lebih dari satu elemen pada DOM tree.
```typescript
// PITFALL: Terdapat 3 tombol dengan label 'Save'
await page.getByRole('button', { name: 'Save' }).click(); // Error: strict mode violation resolved to 3 elements
```
**Mitigasi:** Gunakan locator scoping hierarkis via `.filter()` atau locator berbasis parent yang unik:
```typescript
const modal = page.locator('#corporate-contract-modal');
await modal.getByRole('button', { name: 'Save' }).click();
```

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Menguji Implementation Details vs Public Interface
*Anti-pattern:* Mengakses properti privat komponen via `wrapper.vm.privateStateVariable`.
*Konsekuensi:* Ketika developer me-refactor variabel reaktif tanpa mengubah output visual, unit test gagal.
*Solusi:* Uji apa yang dilihat user (DOM text, attributes) atau apa yang dikeluarkan komponen (Custom Events).

### Kesalahan 2: Over-reliance pada Hardcoded Sleep (`page.waitForTimeout`)
*Anti-pattern:*
```typescript
await page.locator('button#submit').click();
await page.waitForTimeout(5000); // MISTAKE!
expect(await page.locator('.success').isVisible()).toBe(true);
```
*Konsekuensi:* Menghasilkan flakiness di CI yang lambat, dan membuang waktu eksekusi jika server selesai dalam 200ms.
*Solusi:* Andalkan *Web-First Assertions* dari Playwright:
```typescript
await page.locator('button#submit').click();
await expect(page.locator('.success')).toBeVisible({ timeout: 5000 });
```

### Kesalahan 3: Berbagi State Global tanpa Reset
*Anti-pattern:* Menggunakan singleton instance state management antar file test tanpa instance re-creation.
*Solusi:* Selalu panggil `beforeEach(() => { setActivePinia(createPinia()) })`.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan Atribut Selektor Khusus Testing (`data-test` / `data-testid`):** Hindari mengikat selektor pada class CSS (`.btn-primary`) yang rentan berubah karena restyling visual.
2.  **Web-First Assertions:** Gunakan `expect(locator).toBeVisible()` daripada `expect(await locator.isVisible()).toBe(true)`. Bentuk pertama memiliki mekanisme internal retry hingga timeout terlampaui.
3.  **Page Object Model (POM) secara Terukur:** Terapkan POM pada Playwright hanya untuk halaman yang kompleks dan memiliki workflow berulang. Jangan membuat POM untuk form satu baris yang berlebihan (*over-engineering*).
4.  **Deterministic Test Data via Factory Pattern:** Jangan melakukan hardcode ID database yang statis. Gunakan library seperti `@faker-js/faker` dengan seeding deterministik (`faker.seed(123)`).

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Vitest Execution Optimization
Ubah runner environment berdasarkan target test suite. File yang murni menguji pure business logic / domain model tidak memerlukan overhead in-memory DOM parser:
```typescript
// vitest.config.ts
export default defineConfig({
  test: {
    environmentMatchGlobs: [
      ['src/domain/**', 'node'], // 3x lebih cepat daripada happy-dom
      ['src/components/**', 'happy-dom']
    ]
  }
});
```

### 2. Playwright Network Interception & Asset Blocking
Dalam eksekusi E2E, font files, images skala besar, dan analytics tracking (misal: Google Tag Manager) menghabiskan bandwidth dan memperlambat render page:
```typescript
// e2e/base-fixtures.ts
import { test as base } from '@playwright/test';

export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route('**/*', (route) => {
      const request = route.request();
      if (['image', 'media', 'font'].includes(request.resourceType())) {
        return route.abort();
      }
      if (request.url().includes('google-analytics.com')) {
        return route.abort();
      }
      return route.continue();
    });
    await use(page);
  }
});
```

---

# SEKSI 16 — KEAMANAN & HARDENING

1.  **Sanitisasi Storage State:** File hasil auth Playwright (`storageState.json`) berisi live JWT token atau corporate session cookies.
    *   Tambahkan `.auth/` dan `*.json` state artifacts ke `.gitignore`.
    *   Di lingkungan CI, gunakan environment variables sementara yang didelegasikan melalui IAM OIDC / short-lived STS tokens.
2.  **Cegah XSS dalam Test Mock Data:** Pastikan data dummy pada unit test mencakup payload string berbahaya (`<script>alert(1)</script>`) untuk memverifikasi bahwa template compiler Vue melakukan escaping HTML secara benar pada binding non-`v-html`.
3.  **MSW Request Isolation:** Pastikan konfigurasi MSW meny