# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Kategori: 03-Frontend-and-Mobile
### Topik: Vue.js (Vue 3, Pinia, TypeScript, Vitest, MSW, Playwright)
### BAB 09: Enterprise Testing Strategy
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Mengonstruksi Arsitektur Pengujian Multi-Tier**: Merancang dan mengimplementasikan strategi pengujian menyeluruh (*Unit, Integration, Component, E2E, Contract Testing*) yang mengisolasi kegagalan pada lapisan terendah dan meminimalkan ketergantungan pada lingkungan produksi langsung.
2. **Menguasai Internal Siklus Reaktivitas & Microtask Vue**: Mengendalikan dan memvalidasi siklus *tick* Vue (`nextTick`, job scheduler queues, asynchronous dynamic imports, Teleport, dan Suspense) dalam lingkungan headless DOM (*Happy-DOM* dan *JSDOM*).
3. **Mengisolasi dan Menguji State Management Skala Enterprise**: Menerapkan teknik isolasi store Pinia, *cross-store subscriptions*, *action orchestration*, dan composable headless logic yang melibatkan *lifecycle hooks* (`onMounted`, `onUnmounted`, `watchEffect`) tanpa menimbulkan *state leakage* antar *worker threads*.
4. **Mengimplementasikan Network Virtualization dengan MSW v2**: Mengintegrasikan *Mock Service Worker* (MSW) secara deterministik pada lapisan *Node.js integration runner* (Vitest) dan *Browser runtime* (Playwright), menjamin *zero-leak network testing* serta validasi kepatuhan skema (*contract verification*).
5. **Menerapkan Automation Pipeline & Quarantine Mechanism**: Membangun konfigurasi CI/CD matrix untuk eksekusi paralel terdistribusi, instrumentasi *v8 code coverage*, deteksi otomatis *flaky tests*, dan analisis efektivitas pengujian menggunakan *Mutation Testing* (Stryker).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta harus menguasai:
* **Runtime & Package Engine**: Node.js >= 20.10.0 (LTS), pnpm >= 9.x.
* **Core Framework**: Vue 3.4+ (Reactivity Transform deprecation, Composition API, `<script setup>`, Custom Directives, Provide/Inject, Teleport, Suspense).
* **Language**: TypeScript 5.4+ (Generics, Type Narrowing, Discriminated Unions, Utility Types, Module Augmentation).
* **Testing Libraries**: Vitest >= 1.6.0, `@vue/test-utils` >= 2.4.5, `@playwright/test` >= 1.44.0, `msw` >= 2.3.0.
* **Asynchronous Programming**: Event Loop internal (Call Stack, Microtask Queue vs Macrotask Queue, Promise Resolution, MutationObserver).

---

### 3. Concept & Internal Architecture

Strategi testing enterprise pada Vue 3 memerlukan pemahaman mendalam tentang bagaimana Vitest, `@vue/test-utils`, dan sistem reaktivitas Vue berinteraksi di balik layar.

```
+---------------------------------------------------------------------------------------+
|                                    Vitest Worker Pool                                 |
|  +---------------------------------------------------------------------------------+  |
|  | Isolated Worker Process (tinypool / Piscina)                                    |  |
|  |                                                                                 |  |
|  |  +--------------------------+  Interceptors  +-------------------------------+  |  |
|  |  |     Global Environment   | <------------> |      MSW Node Interceptor     |  |  |
|  |  |    (Happy-DOM / JSDOM)   |                |    (fetch, xhr, http client)  |  |  |
|  |  +--------------------------+                +-------------------------------+  |  |
|  |               ^                                                                 |  |
|  |               | Mounts VNode                                                    |  |
|  |  +--------------------------+                                                   |  |
|  |  |  Vue Test Utils Runner   |                                                   |  |
|  |  |   - global.plugins       |                                                   |  |
|  |  |   - global.provide       |                                                   |  |
|  |  +--------------------------+                                                   |  |
|  |               |                                                                 |  |
|  |               v Instantiates Component Tree                                     |  |
|  |  +---------------------------------------------------------------------------+  |  |
|  |  | Vue Reactivity Core Engine                                                |  |  |
|  |  |  [Reactivity Effect] -> [Trigger Dependency] -> [Queue Job (Job Queue)]  |  |  |
|  |  |                                                         |                 |  |  |
|  |  |                                                         v                 |  |  |
|  |  |               Microtask Engine (Promise.resolve().then())                 |  |  |
|  |  |                 [Flush: nextTick() / flushPromises()]                     |  |  |
|  |  |                                                         |                 |  |  |
|  |  |                                                         v                 |  |  |
|  |  |                                            [Virtual DOM Patch Engine]     |  |  |
|  |  |                                                         |                 |  |  |
|  |  |                                                         v                 |  |  |
|  |  |                                            [DOM Mutation Assertion]       |  |  |
|  |  +---------------------------------------------------------------------------+  |  |
|  +---------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
```

#### A. Vitest Execution Model & Happy-DOM Integration
Vitest mengeksekusi suite pengujian menggunakan *worker pools* berbasis `tinypool` (abstraksi `node:worker_threads`). Setiap file pengujian mendapatkan konteks terisolasi di mana global DOM diinjeksikan melalui Happy-DOM atau JSDOM. Happy-DOM mem-parsing dokumen HTML secara signifikan lebih cepat daripada JSDOM karena mengabaikan sejumlah implementasi styling level rendah dan *canvas rendering*, menjadikannya pilihan optimal untuk *unit/component test* berskala besar.

#### B. Vue Scheduler, Microtasks, dan DOM Updates
Sistem reaktivitas Vue tidak langsung memperbarui DOM setiap kali sebuah `ref` atau `reactive` termutasi. Sebaliknya, mutasi memicu *job scheduler*:
1. Mutasi state memicu *setter trap* pada objek proxy.
2. Proxy mengeksekusi fungsi `trigger()` yang mendaftarkan efek dependensi ke dalam *queue internal*.
3. Scheduler men-deduplikasi pekerjaan tersebut dan menjadwalkan eksekusinya pada *Microtask Queue* menggunakan `Promise.resolve().then(flushJobs)`.
4. Jika test assertion dieksekusi secara sinkron tepat setelah state diubah, DOM belum diperbarui. Di sinilah `await nextTick()` atau `await flushPromises()` menjadi krusial. 
   - `nextTick()`: Menunggu penyelesaian antrean *job* internal Vue saat ini.
   - `flushPromises()`: Memaksa penyelesaian *seluruh* unresolved microtasks dan macrotasks dalam antrean global JavaScript engine, termasuk Promise yang dirantai oleh library pihak ketiga atau pemanggilan API asynchronous.

#### C. Isolasi State & Cleanroom Sandbox
Dalam aplikasi enterprise, Pinia beroperasi sebagai singleton per instance aplikasi Vue (`createPinia()`). Jika satu instance Pinia dibagi di antara file tes, mutasi state dari file Test A akan mencemari ekspektasi Test B (*State Leakage*). Arsitektur pengujian yang benar mewajibkan injeksi instance Pinia baru (`setActivePinia(createPinia())`) pada *hook* `beforeEach` di setiap blok pengujian, serta penghentian *zombie listeners* pada composable yang memegang referensi ke objek global.

---

### 4. Why & What

| Paradigma Lama (Fragile Testing) | Paradigma Enterprise Modern (Behavior-Driven Testing) |
|---|---|
| Menguji implementasi internal (e.g., memeriksa nilai internal `wrapper.vm.myPrivateData`). | Menguji kontrak perilaku eksternal (*Input DOM Events / Props* -> *Output State / DOM Updates*). |
| Shallow rendering ekstrem (`shallow: true`) yang mematikan logika anak dan lifecycle. | Context-aware Mount: Merender hierarki terkait, menggunakan stub selektif hanya untuk batasan batas domain (I/O, Analytics, 3rd Party UI). |
| Melakukan mocking pada `axios` atau `fetch` menggunakan `vi.fn().mockResolvedValue()`. | Network Virtualization via MSW pada level transport: Intersepsi HTTP/HTTPS native, menjaga keutuhan parsing header, status code, dan serialisasi payload. |
| Pengujian composable yang diikat paksa ke DOM wrapper kosong. | Headless Testing Harness: Menjalankan composable dalam wrapper scope reaktif minimal untuk menguji dependensi injection dan lifecycle tanpa overhead render DOM. |
| Test suite lambat dengan JSDOM monolithic. | Multi-threaded Worker Pool Vitest menggunakan Happy-DOM dengan sub-millisecond setup time per test suite. |

Mengapa strategi ini mutlak diperlukan?
Dalam aplikasi enterprise dengan ratusan pengembang dan ribuan komponen, pengujian yang rapuh (*brittle tests*) akan sering gagal bukan karena adanya bug fungsional, melainkan akibat refaktorisasi internal (misalnya memecah method internal menjadi sub-fungsi). Strategi pengujian modern memperlakukan komponen sebagai *black box*: sistem pengujian hanya memvalidasi antarmuka yang terlihat oleh pengguna akhir atau komponen induknya.

---

### 5. How (Workflow Detail)

Alur kerja eksekusi pengujian komponen enterprise mengikuti siklus 6 fase deterministik:

```
[Phase 1: Environment Preparation]
   │  - Inisialisasi Mock Service Worker (MSW) server
   │  - Instansiasi Pinia Root Sandbox
   │  - Registrasi Plugin (Vue Router Mock, I18n)
   ▼
[Phase 2: Component Mount & Context Provision]
   │  - Render komponen via `@vue/test-utils` (mount())
   │  - Injeksi Teleport target container (e.g., <div id="modal-root">)
   │  - Injeksi Provide/Inject token (e.g., AuthService, EventBus)
   ▼
[Phase 3: Trigger Reactive Interactions]
   │  - Simulasi event pengguna melalui wrapper (trigger('click'), setValue())
   │  - Modifikasi Props eksternal (wrapper.setProps())
   ▼
[Phase 4: Microtask Queue Flush]
   │  - Eksekusi `await flushPromises()` untuk menghabiskan job scheduler
   │  - Memastikan seluruh chained promise pada lifecycle async selesai
   ▼
[Phase 5: Contract & DOM Assertions]
   │  - Verifikasi perubahan DOM yang tampak (accessibility roles, text content)
   │  - Verifikasi efek samping (Pinia store updates, Event emit, MSW network calls)
   ▼
[Phase 6: Teardown & Leak Prevention]
   │  - Clear MSW runtime handlers (`server.resetHandlers()`)
   │  - Unmount wrapper (`wrapper.unmount()`)
   │  - Reset timers (`vi.clearAllTimers()`)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Inspeksi Pabrik Otomotif Terotomasi
Membangun sistem pengujian enterprise analog dengan menguji mobil pada lini perakitan:
* **Unit Testing (Composable & Utilities)**: Menguji kinerja alternator atau busi pada *test bench* statis di laboratorium. Komponen diuji secara terisolasi total dengan simulasi voltase buatan.
* **Component Testing (Vue Test Utils)**: Memasang sistem kendali dasbor mobil (Dashboard Console) ke generator kabel simulator. Penguji menekan tombol "Hazard" di layar fisik dan memverifikasi apakah sirkuit relay mengirimkan tegangan yang tepat tanpa harus merakit sasis mobil lengkap.
* **Network Mocking (MSW)**: Stasiun pengisian bahan bakar simulasi. Alih-alih mengisi bensin asli, pipa bahan bakar dihubungkan ke sensor simulator yang melaporkan volume bensin dan tekanan secara tepat.
* **End-to-End Testing (Playwright)**: Mobil dirakit utuh, ditaruh di atas trek uji nyata, dikendarai oleh robot untuk memastikan rem ABS berfungsi saat jalan basah dan sistem kemudi berbelok presisi.

#### Diagram: Penjadwalan Microtask vs Eksekusi Test Runner

```
Timeline: (JavaScript Thread)
----------------------------------------------------------------------------------->
[Call Stack]         : wrapper.find('button').trigger('click')
                             |
                             v (State changes: count.value++)
[Vue Scheduler Queue]: [Queue Watcher Effect] (Tersimpan di heap, belum dieksekusi)
                             |
                             v (Scheduler menjadwalkan microtask)
[Microtask Queue]    : [Promise.resolve().then(flushJobs)]
                             |
                             |-- Test runner melanjutkan baris kode sinkron berikutnya:
                             |   expect(wrapper.text()).toContain('1') -> GAGAL (DOM Masih '0')
                             |
[Await nextTick()]   : Test runner menyerahkan giliran eksekusi ke Microtask Queue
                             |
[Microtask Flushed]  : flushJobs() dieksekusi -> VNode Re-rendered -> Patch DOM Nyata
                             |
[Resume Test]        : expect(wrapper.text()).toContain('1') -> BERHASIL
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Headless Composable Testing
Menguji composable yang mengelola siklus hidup (*lifecycle*), debouncing, dan reaktivitas murni tanpa mengikatnya ke komponen visual.

```typescript
// src/composables/useDebouncedSearch.ts
import { ref, watch, onUnmounted, type Ref } from 'vue';

export interface UseDebouncedSearchOptions {
  delay?: number;
  onSearch: (query: string) => Promise<void> | void;
}

export function useDebouncedSearch(
  sourceQuery: Ref<string>,
  options: UseDebouncedSearchOptions
) {
  const isPending = ref(false);
  const error = ref<Error | null>(null);
  const { delay = 300, onSearch } = options;
  let timerId: ReturnType<typeof setTimeout> | null = null;

  const stopWatcher = watch(sourceQuery, (newVal) => {
    if (timerId) clearTimeout(timerId);

    if (!newVal.trim()) {
      isPending.value = false;
      return;
    }

    isPending.value = true;
    timerId = setTimeout(async () => {
      try {
        await onSearch(newVal);
      } catch (err) {
        error.value = err instanceof Error ? err : new Error(String(err));
      } finally {
        isPending.value = false;
      }
    }, delay);
  });

  onUnmounted(() => {
    if (timerId) clearTimeout(timerId);
    stopWatcher();
  });

  return {
    isPending,
    error,
  };
}
```

```typescript
// src/composables/__tests__/useDebouncedSearch.spec.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ref } from 'vue';
import { withSetup } from '../../test-utils/test-harness';
import { useDebouncedSearch } from '../useDebouncedSearch';

describe('useDebouncedSearch Composable', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('harus menunda pemanggilan fungsi search sesuai delay yang ditentukan', async () => {
    const searchQuery = ref('');
    const searchMock = vi.fn().mockResolvedValue(undefined);

    // Menggunakan custom harness untuk mengisolasi Vue lifecycle scope
    const [result, app] = withSetup(() =>
      useDebouncedSearch(searchQuery, { delay: 500, onSearch: searchMock })
    );

    expect(result.isPending.value).toBe(false);
    expect(searchMock).not.toHaveBeenCalled();

    // Trigger mutasi reaktivitas
    searchQuery.value = 'Enterprise Architecture';
    expect(result.isPending.value).toBe(true);

    // Majukan timer parsial (belum mencapai 500ms)
    vi.advanceTimersByTime(250);
    expect(searchMock).not.toHaveBeenCalled();

    // Majukan sisa waktu
    vi.advanceTimersByTime(250);
    expect(searchMock).toHaveBeenCalledTimes(1);
    expect(searchMock).toHaveBeenCalledWith('Enterprise Architecture');

    // Menunggu microtasks resolve
    await vi.runAllTicks();
    expect(result.isPending.value).toBe(false);

    // Unmount untuk memverifikasi cleanup hook
    app.unmount();
  });

  it('harus membersihkan timeout saat komponen unmount sebelum timer selesai', () => {
    const searchQuery = ref('');
    const searchMock = vi.fn();

    const [, app] = withSetup(() =>
      useDebouncedSearch(searchQuery, { delay: 500, onSearch: searchMock })
    );

    searchQuery.value = 'Cancelled Query';
    vi.advanceTimersByTime(200);

    // Trigger unmount mendadak
    app.unmount();

    // Habiskan seluruh waktu tersisa
    vi.advanceTimersByTime(500);
    expect(searchMock).not.toHaveBeenCalled();
  });
});
```

Harness Helper implementation:
```typescript
// src/test-utils/test-harness.ts
import { createApp, type App } from 'vue';

export function withSetup<T>(composable: () => T): [T, App] {
  let result!: T;
  const app = createApp({
    setup() {
      result = composable();
      return () => {};
    },
  });
  app.mount(document.createElement('div'));
  return [result, app];
}
```

---

#### B. Practical Enterprise Example: Modul Pembayaran Transaksi Suspense, Teleport & MSW

Implementasi komponen alur otentikasi checkout enterprise yang mencakup pemanggilan API aman, Pinia Store terisolasi, Modal Konfirmasi berbasis Teleport, dan Suspense Asinkron.

```typescript
// src/types/checkout.ts
export interface PaymentPayload {
  orderId: string;
  amount: number;
  currency: 'IDR' | 'USD';
  idempotencyKey: string;
}

export interface PaymentReceipt {
  transactionId: string;
  status: 'SUCCESS' | 'DECLINED' | 'REQUIRES_2FA';
  timestamp: string;
}
```

```typescript
// src/stores/checkoutStore.ts
import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { PaymentReceipt, PaymentPayload } from '../types/checkout';

export const useCheckoutStore = defineStore('checkout', () => {
  const currentReceipt = ref<PaymentReceipt | null>(null);
  const isProcessing = ref(false);
  const failureReason = ref<string | null>(null);

  async function processPayment(payload: PaymentPayload): Promise<void> {
    isProcessing.value = true;
    failureReason.value = null;

    try {
      const response = await fetch('/api/v1/payments/charge', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Idempotency-Key': payload.idempotencyKey,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `HTTP_${response.status}`);
      }

      const data: PaymentReceipt = await response.json();
      currentReceipt.value = data;
    } catch (err) {
      failureReason.value = err instanceof Error ? err.message : 'UNKNOWN_ERROR';
      throw err;
    } finally {
      isProcessing.value = false;
    }
  }

  function resetState() {
    currentReceipt.value = null;
    isProcessing.value = false;
    failureReason.value = null;
  }

  return {
    currentReceipt,
    isProcessing,
    failureReason,
    processPayment,
    resetState,
  };
});
```

Komponen Vue yang diuji:
```vue
<!-- src/components/PaymentModal.vue -->
<template>
  <button
    data-test="open-modal-btn"
    class="btn-primary"
    @click="isModalOpen = true"
  >
    Bayar Sekarang
  </button>

  <Teleport to="#modal-root">
    <div
      v-if="isModalOpen"
      class="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div class="modal-card">
        <h2 id="modal-title">Konfirmasi Pembayaran</h2>
        <p>Order ID: {{ payload.orderId }}</p>
        <p>Jumlah: {{ payload.currency }} {{ payload.amount.toLocaleString() }}</p>

        <div v-if="checkoutStore.failureReason" class="error-banner" role="alert">
          {{ checkoutStore.failureReason }}
        </div>

        <div class="action-buttons">
          <button
            data-test="cancel-btn"
            :disabled="checkoutStore.isProcessing"
            @click="isModalOpen = false"
          >
            Batal
          </button>
          <button
            data-test="confirm-btn"
            :disabled="checkoutStore.isProcessing"
            @click="handleExecution"
          >
            <span v-if="checkoutStore.isProcessing">Memproses...</span>
            <span v-else>Konfirmasi Transaksi</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useCheckoutStore } from '../stores/checkoutStore';
import type { PaymentPayload } from '../types/checkout';

const props = defineProps<{
  payload: PaymentPayload;
}>();

const emit = defineEmits<{
  (e: 'success', transactionId: string): void;
  (e: 'failure', error: string): void;
}>();

const checkoutStore = useCheckoutStore();
const isModalOpen = ref(false);

async function handleExecution() {
  try {
    await checkoutStore.processPayment(props.payload);
    if (checkoutStore.currentReceipt?.status === 'SUCCESS') {
      emit('success', checkoutStore.currentReceipt.transactionId);
      isModalOpen.value = false;
    }
  } catch (err) {
    emit('failure', checkoutStore.failureReason || 'Transaksi Gagal');
  }
}
</script>
```

Spesifikasi Pengujian Komprehensif (Unit + Integration via Vitest, Pinia, Happy-DOM, MSW):

```typescript
// src/components/__tests__/PaymentModal.spec.ts
import { describe, it, expect, beforeEach, afterEach, afterAll, beforeAll } from 'vitest';
import { mount, flushPromises, VueWrapper } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import PaymentModal from '../PaymentModal.vue';
import type { PaymentPayload, PaymentReceipt } from '../../types/checkout';

// 1. Setup Mock Service Worker Interceptors
const mockHandlers = [
  http.post('/api/v1/payments/charge', async ({ request }) => {
    const body = (await request.json()) as PaymentPayload;
    const idempotencyKey = request.headers.get('X-Idempotency-Key');

    if (!idempotencyKey) {
      return new HttpResponse(
        JSON.stringify({ message: 'MISSING_IDEMPOTENCY_KEY' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    if (body.amount <= 0) {
      return new HttpResponse(
        JSON.stringify({ message: 'INVALID_AMOUNT' }),
        { status: 422, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const receipt: PaymentReceipt = {
      transactionId: 'TX-ENTERPRISE-884920',
      status: 'SUCCESS',
      timestamp: new Date().toISOString(),
    };

    return HttpResponse.json(receipt, { status: 200 });
  }),
];

const server = setupServer(...mockHandlers);

describe('PaymentModal Component Integration', () => {
  let wrapper: VueWrapper;
  let modalTargetContainer: HTMLDivElement;

  beforeAll(() => {
    // Memulai virtual server network interceptor
    server.listen({ onUnhandledRequest: 'error' });
  });

  beforeEach(() => {
    // Isolasi state Pinia untuk setiap unit test
    setActivePinia(createPinia());

    // Konfigurasi container host Teleport pada Happy-DOM environment
    modalTargetContainer = document.createElement('div');
    modalTargetContainer.id = 'modal-root';
    document.body.appendChild(modalTargetContainer);
  });

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount();
    }
    server.resetHandlers();
    document.body.removeChild(modalTargetContainer);
  });

  afterAll(() => {
    server.close();
  });

  const defaultPayload: PaymentPayload = {
    orderId: 'ORD-99120',
    amount: 1500000,
    currency: 'IDR',
    idempotencyKey: 'idemp-uuid-alpha-1234',
  };

  it('tidak boleh merender modal sebelum tombol pemicu diklik', () => {
    wrapper = mount(PaymentModal, {
      props: { payload: defaultPayload },
    });

    expect(document.querySelector('.modal-card')).toBeNull();
  });

  it('harus merender modal ke elemen teleport (#modal-root) setelah tombol diklik', async () => {
    wrapper = mount(PaymentModal, {
      props: { payload: defaultPayload },
    });

    const triggerBtn = wrapper.find('[data-test="open-modal-btn"]');
    await triggerBtn.trigger('click');
    await flushPromises();

    const modalInTeleport = document.querySelector('#modal-root .modal-card');
    expect(modalInTeleport).not.toBeNull();
    expect(modalInTeleport?.textContent).toContain('ORD-99120');
    expect(modalInTeleport?.textContent).toContain('IDR 1,500,000');
  });

  it('harus menyelesaikan transaksi sukses, memancarkan event emit, dan menutup modal', async () => {
    wrapper = mount(PaymentModal, {
      props: { payload: defaultPayload },
    });

    // Buka modal
    await wrapper.find('[data-test="open-modal-btn"]').trigger('click');
    await flushPromises();

    // Query modal target secara global dari DOM body (efek Teleport)
    const confirmBtn = document.querySelector('[data-test="confirm-btn"]') as HTMLButtonElement;
    expect(confirmBtn).not.toBeNull();

    // Klik tombol konfirmasi eksekusi
    confirmBtn.click();
    await flushPromises();

    // Validasi emisi event success
    const emittedSuccess = wrapper.emitted('success');
    expect(emittedSuccess).toBeTruthy();
    expect(emittedSuccess![0]).toEqual(['TX-ENTERPRISE-884920']);

    // Validasi bahwa modal otomatis tertutup
    expect(document.querySelector('.modal-card')).toBeNull();
  });

  it('harus menangani respon error HTTP 422 dari server dan menampilkan banner pesan kesalahan', async () => {
    // Override handler khusus untuk skenario kegagalan
    server.use(
      http.post('/api/v1/payments/charge', () => {
        return HttpResponse.json(
          { message: 'LIMIT_HARIAN_TERLAMPAUI' },
          { status: 422 }
        );
      })
    );

    wrapper = mount(PaymentModal, {
      props: { payload: defaultPayload },
    });

    await wrapper.find('[data-test="open-modal-btn"]').trigger('click');
    await flushPromises();

    const confirmBtn = document.querySelector('[data-test="confirm-btn"]') as HTMLButtonElement;
    confirmBtn.click();
    await flushPromises();

    // Pastikan error banner muncul di DOM teleport
    const errorBanner = document.querySelector('[role="alert"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.textContent).toContain('LIMIT_HARIAN_TERLAMPAUI');

    // Validasi emisi failure
    const emittedFailure = wrapper.emitted('failure');
    expect(emittedFailure).toBeTruthy();
    expect(emittedFailure![0]).toEqual(['LIMIT_HARIAN_TERLAMPAUI']);

    // Modal harus tetap terbuka agar user tahu ada kegagalan
    expect(document.querySelector('.modal-card')).not.toBeNull();
  });
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Bank Digital Regional dengan jutaan transaksi harian memigrasikan Single Page Application Core Banking mereka ke arsitektur Vue 3. Fitur kritis yang ditangani: *Multi-Step Wire Transfer Form* yang terintegrasi dengan modul biometrik WebAuthn, 2FA Dynamic Polling, dan Real-time Currency Conversion.

#### Masalah Produksi Teridentifikasi
1. **Flaky CI Builds**: Tingkat kegagalan *pipeline* CI/CD mencapai 22% akibat *race condition* pada pengujian E2E dan *memory leak* pada instance worker Vitest.
2. **False Positives (Brittle Mocks)**: Mock API tradisional (`vi.spyOn(axios, 'post')`) menyembunyikan bug integrasi riil. Payload yang dikirim klien berubah secara tidak sengaja oleh interceptor, tetapi mock tetap meloloskan pengujian karena parameter validasi tidak di-assert secara mendalam.
3. **Ghost State Collisions**: Pengujian yang berjalan paralel pada 16 Core CPU CI Server saling mempengaruhi state Pinia, menyebabkan transaksi tes pengguna A muncul pada sesi pengujian pengguna B.

#### Solusi Arsitektural Enterprise
1. **Implementasi MSW v2 Strict Schema Contracts**:
   Menghentikan penggunaan mocking langsung pada layer service. Seluruh komunikasi jaringan dialihkan melalui MSW dengan middleware validasi skema runtime menggunakan library *Zod*. Jika frontend mengirim payload yang melanggar skema OpenAPI backend, MSW otomatis menggagalkan tes dengan status `400 Bad Request`.
2. **Multi-Stage Test Quarantine & Parallel Runner**:
   - Memisahkan tes ke dalam tiga ring terproteksi: *Unit-Fast* (Happy-DOM, execution target < 15 detik), *Integration-DOM* (Vitest + MSW), dan *E2E Browser Real* (Playwright).
   - Menerapkan arsitektur *Dynamic Storage State* pada Playwright: Otentikasi dilakukan sekali per skenario worker menggunakan pre-baked cookie injection, memangkas durasi testing E2E sebesar 65%.
3. **Enforcement Pinia Cleanrooms via Global Hooks**:
   Mengonfigurasi file setup Vitest global yang mengeksekusi `pinia.state.value = {}` dan me-mount kembali app context di setiap siklus eksekusi file.

#### Hasil Metrik Terukur
- CI Build Reliability naik dari **78% menjadi 99.85%**.
- Eksekusi Test Suite (4.200 assertions) terpangkas dari **18 menit menjadi 3 menit 40 detik** melalui paralelisasi worker berbasis sharding.
- Deteksi regresi API sebelum rilis ke staging meningkat **400%**.

---

### 9. Trade-offs

| Parameter | Unit/Composable Testing (Vitest + Happy-DOM) | Integration Component Testing (VTU + MSW) | Playwright Component Testing (CT) | End-to-End Testing (Playwright Browser) |
|---|---|---|---|---|
| **Kecepatan Eksekusi** | Ultra Cepat (~1-5ms / test) | Cepat (~20-80ms / test) | Sedang (~200-500ms / test) | Lambat (~1-5 detik / flow) |
| **Fidelitas Lingkungan** | Rendah (Simulasi memori node.js, DOM tidak lengkap) | Sedang-Tinggi (DOM parsial, emulasi events, simulated microtasks) | Sangat Tinggi (Dirender pada Chromium/WebKit/Firefox engine asli) | Maksimal (Sistem utuh, CSS layout riil, network stack native) |
| **Biaya Pemeliharaan** | Rendah | Sedang | Sedang-Tinggi | Tinggi (Rawan perubahan UI layout mikro) |
| **Konsumsi Memori CI** | Rendah (~100-200MB / worker) | Sedang (~300-500MB / worker) | Sangat Tinggi (~1GB+ / browser process) | Sangat Tinggi (~1.5GB+ / instance) |
| **Kelemahan Utama** | Tidak mendeteksi masalah layout CSS, paint rendering, atau cross-origin policy riil. | Keterbatasan Happy-DOM pada API kompleks (misal: `IntersectionObserver`, `Canvas`). | Setup kompilasi Vite khusus runtime browser uji; debugging overhead lebih tinggi. | Lambat jika digunakan untuk menguji validasi form detail (*negative path permutations*). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan: Menggunakan `nextTick()` Tunggal untuk Operasi Asinkron Bertingkat
* **Gejala**: Assertion gagal secara acak saat menguji komponen yang memanggil API, lalu memutasi state, lalu memicu watcher sekunder.
* **Akar Masalah**: `await nextTick()` hanya menguras antrean microtask Vue yang ada pada *saat pemanggilan*. Jika respons API baru diselesaikan melalui microtask terpisah, watcher sekunder baru dijadwalkan *setelah* nextTick selesai.
* **Solusi**: Gunakan `await flushPromises()` dari `@vue/test-utils` yang memaksa seluruh siklus *promise resolution* di microtask queue JavaScript habis sebelum berlanjut ke assertion.

```typescript
// SALAH
await wrapper.find('button').trigger('click');
await nextTick();
expect(wrapper.text()).toContain('Data Loaded'); // FLAKY / GAGAL

// BENAR
await wrapper.find('button').trigger('click');
await flushPromises();
expect(wrapper.text()).toContain('Data Loaded'); // DETERMINISTIK
```

#### 2. Kesalahan: State Leakage Antar Tes pada Pinia Store
* **Gejala**: Urutan eksekusi pengujian mengubah hasil. Test B lulus jika dijalankan sendiri (`vitest run -t "test B"`), tetapi gagal jika dijalankan bersama seluruh test suite.
* **Akar Masalah**: Mengimpor dan menggunakan Pinia store tanpa mereset context *ActivePinia*. Objek store tetap mempertahankan state di memori proses worker.
* **Solusi**: Selalu lakukan inisialisasi ulang Pinia pada `beforeEach`.

```typescript
// setup.ts atau pada spec file
beforeEach(() => {
  setActivePinia(createPinia());
});
```

#### 3. Kesalahan: Teleport Container Hilang pada Happy-DOM / JSDOM
* **Gejala**: Error runtime: `Cannot read properties of null (reading 'appendChild')` atau komponen anak di dalam `<Teleport to="#target">` lenyap dari wrapper.
* **Akar Masalah**: Elemen `#target` tidak terdefinisi di objek `document.body` default lingkungan virtual headless.
* **Solusi**: Buat elemen host secara dinamis di `beforeEach` dan bersihkan di `afterEach`.

```typescript
let target: HTMLElement;
beforeEach(() => {
  target = document.createElement('div');
  target.id = 'teleport-target';
  document.body.appendChild(target);
});
afterEach(() => {
  document.body.removeChild(target);
});
```

#### 4. Kesalahan: Bocornya Unhandled Network Request pada MSW
* **Gejala**: Log CI dipenuhi error jaringan `FetchError: request to http://... failed, reason: connect ECONNREFUSED 127.0.0.1`.
* **Akar Masalah**: Komponen memicu pemanggilan URL yang tidak memiliki *matching handler* di MSW configuration, sehingga lolos ke network layer OS nyata.
* **Solusi**: Konfigurasikan opsi ketat `onUnhandledRequest: 'error'` saat memanggil `server.listen()`. Ini menjamin tes langsung gagal jika frontend memanggil API liar yang belum didefinisikan kontraknya.

#### 5. Kesalahan: Menguji Reaktivitas Objek Props yang Didekonstruksi Secara Non-Reaktif
* **Gejala**: Mengubah props via `wrapper.setProps()` tidak memperbarui tampilan komponen anak.
* **Akar Masalah**: Komponen yang diuji melakukan dekonstruksi props secara langsung (`const { title } = defineProps()`) sehingga memutus proxy reaktivitas Vue.
* **Solusi**: Pastikan komponen mematuhi aturan reaktivitas (menggunakan `toRefs()`, computed, atau langsung membaca `props.title`).

---

### 11. Best Practices (Production Checklist)

1. [ ] **Isolated Store Sandboxes**: Setiap blok tes (`describe` / `it`) harus berjalan di atas Pinia instance baru (`setActivePinia(createPinia())`).
2. [ ] **Deterministic Async Management**: Tidak boleh ada pemanggilan `setTimeout` manual pada file spec untuk menunggu DOM. Selalu gunakan `flushPromises()`, `vi.advanceTimersByTime()`, atau waitFor utility.
3. [ ] **Zero Network Egress**: Jalankan `server.listen({ onUnhandledRequest: 'error' })` untuk memblokir seluruh pemanggilan jaringan fisik ke internet dari runner CI.
4. [ ] **Accessibility-First Queries**: Prioritaskan selektor berbasis role dan testing-library semantic daripada class selector (e.g., Gunakan `find('[role="button"]')` atau `getByRole('button')` daripada `find('.btn-submit')`).
5. [ ] **Clean DOM Teardown**: Jalankan `wrapper.unmount()` secara konsisten untuk memastikan lifecycle hook `onUnmounted` terpanggil, membersihkan event listener window/document.
6. [ ] **Strict Contract Testing**: Selaraskan model MSW payload dengan schema type validator (misal: Zod, Valibot) yang bersumber dari OpenAPI/Swagger backend.
7. [ ] **Mutation Testing Thresholds**: Jalankan Stryker Mutator secara berkala di pipeline malam (nightly build) dengan target Mutation Score >= 75% untuk mendeteksi *false confidence* pada unit tests.

---

### 12. Hands-on Practice

Struktur direktori kerja:
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── vitest.config.ts
├── vitest.setup.ts
├── src/
│   ├── api/
│   │   └── client.ts
│   ├── components/
│   │   ├── NotificationCenter.vue
│   │   └── __tests__/
│   │       └── NotificationCenter.spec.ts
│   ├── stores/
│   │   ├── notificationStore.ts
│   │   └── __tests__/
│   │       └── notificationStore.spec.ts
│   └── mocks/
│       ├── handlers.ts
│       └── server.ts
```

#### Langkah 1: Inisialisasi Project & Dependensi
Simpan ke `hands-on/m02/package.json`:
```json
{
  "name": "enterprise-vue-testing-m02",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest watch",
    "test:coverage": "vitest run --coverage"
  },
  "dependencies": {
    "pinia": "^2.1.7",
    "vue": "^3.4.27"
  },
  "devDependencies": {
    "@types/node": "^20.12.12",
    "@vitejs/plugin-vue": "^5.0.4",
    "@vue/test-utils": "^2.4.6",
    "@vitest/coverage-v8": "^1.6.0",
    "happy-dom": "^14.12.0",
    "msw": "^2.3.0",
    "typescript": "^5.4.5",
    "vite": "^5.2.11",
    "vitest": "^1.6.0"
  }
}
```

#### Langkah 2: Konfigurasi Vitest & Setup Global
Simpan ke `hands-on/m02/vitest.config.ts`:
```typescript
import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./vitest.setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'vitest.setup.ts', 'src/mocks/**'],
      all: true,
      lines: 85,
      branches: 80,
      functions: 85,
      statements: 85,
    },
  },
});
```

Simpan ke `hands-on/m02/vitest.setup.ts`:
```typescript
import { beforeAll, afterEach, afterAll } from 'vitest';
import { server } from './src/mocks/server';

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});
```

#### Langkah 3: Setup Mock Service Worker (MSW)
Simpan ke `hands-on/m02/src/mocks/handlers.ts`:
```typescript
import { http, HttpResponse } from 'msw';

export interface NotificationItem {
  id: string;
  message: string;
  read: boolean;
}

export const handlers = [
  http.get('/api/v1/notifications', () => {
    const list: NotificationItem[] = [
      { id: 'nt-01', message: 'Sistem patching dijadwalkan malam ini', read: false },
      { id: 'nt-02', message: 'Faktur tagihan #9081 berhasil diunggah', read: true },
    ];
    return HttpResponse.json(list, { status: 200 });
  }),

  http.patch('/api/v1/notifications/:id/mark-read', ({ params }) => {
    const { id } = params;
    return HttpResponse.json({ success: true, id }, { status: 200 });
  }),
];
```

Simpan ke `hands-on/m02/src/mocks/server.ts`:
```typescript
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
```

#### Langkah 4: Implementasi Layer Pinia Store
Simpan ke `hands-on/m02/src/stores/notificationStore.ts`:
```typescript
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { NotificationItem } from '../mocks/handlers';

export const useNotificationStore = defineStore('notification', () => {
  const items = ref<NotificationItem[]>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  const unreadCount = computed(() => {
    return items.value.filter((n) => !n.read).length;
  });

  async function fetchNotifications() {
    isLoading.value = true;
    error.value = null;
    try {
      const response = await fetch('/api/v1/notifications');
      if (!response.ok) throw new Error('ERR_FETCH_FAILED');
      items.value = await response.json();
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'UNKNOWN_ERROR';
    } finally {
      isLoading.value = false;
    }
  }

  async function markAsRead(id: string) {
    try {
      const response = await fetch(`/api/v1/notifications/${id}/mark-read`, {
        method: 'PATCH',
      });
      if (!response.ok) throw new Error('ERR_PATCH_FAILED');
      const target = items.value.find((n) => n.id === id);
      if (target) {
        target.read = true;
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'UNKNOWN_ERROR';
    }
  }

  return {
    items,
    isLoading,
    error,
    unreadCount,
    fetchNotifications,
    markAsRead,
  };
});
```

#### Langkah 5: Implementasi Komponen Vue
Simpan ke `hands-on/m02/src/components/NotificationCenter.vue`:
```vue
<template>
  <div class="notification-container">
    <header class="header">
      <h2>Notifikasi Sistem</h2>
      <span data-test="unread-badge" class="badge">
        {{ store.unreadCount }} Belum Dibaca
      </span>
    </header>

    <button
      data-test="refresh-btn"
      :disabled="store.isLoading"
      @click="store.fetchNotifications()"
    >
      Muat Ulang
    </button>

    <div v-if="store.isLoading" data-test="loading-indicator">
      Mengambil notifikasi...
    </div>

    <div v-if="store.error" data-test="error-indicator" class="error">
      {{ store.error }}
    </div>

    <ul v-if="!store.isLoading" data-test="notification-list" class="list">
      <li
        v-for="item in store.items"
        :key="item.id"
        :data-test="`item-${item.id}`"
        :class="{ unread: !item.read }"
      >
        <span class="message">{{ item.message }}</span>
        <button
          v-if="!item.read"
          :data-test="`read-btn-${item.id}`"
          @click="store.markAsRead(item.id)"
        >
          Tandai Dibaca
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useNotificationStore } from '../stores/notificationStore';

const store = useNotificationStore();

onMounted(async () => {
  if (store.items.length === 0) {
    await store.fetchNotifications();
  }
});
</script>
```

#### Langkah 6: Implementasi Pengujian Pinia Store
Simpan ke `hands-on/m02/src/stores/__tests__/notificationStore.spec.ts`:
```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useNotificationStore } from '../notificationStore';
import { server } from '../../mocks/server';
import { http, HttpResponse } from 'msw';

describe('NotificationStore Unit/Integration Spec', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('harus memvalidasi state awal kosong', () => {
    const store = useNotificationStore();
    expect(store.items).toEqual([]);
    expect(store.isLoading).toBe(false);
    expect(store.unreadCount).toBe(0);
    expect(store.error).toBeNull();
  });

  it('harus berhasil memuat notifikasi dan menghitung unreadCount', async () => {
    const store = useNotificationStore();
    await store.fetchNotifications();

    expect(store.items.length).toBe(2);
    expect(store.unreadCount).toBe(1);
    expect(store.isLoading).toBe(false);
  });

  it('harus menangani kegagalan API jaringan', async () => {
    server.use(
      http.get('/api/v1/notifications', () => {
        return new HttpResponse(null, { status: 500 });
      })
    );

    const store = useNotificationStore();
    await store.fetchNotifications();

    expect(store.items).toEqual([]);
    expect(store.error).toBe('ERR_FETCH_FAILED');
    expect(store.isLoading).toBe(false);
  });

  it('harus memperbarui status notifikasi menjadi read secara optimistik', async () => {
    const store = useNotificationStore();
    await store.fetchNotifications();
    expect(store.unreadCount).toBe(1);

    await store.markAsRead('nt-01');
    expect(store.unreadCount).toBe(0);
    const target = store.items.find((item) => item.id === 'nt-01');
    expect(target?.read).toBe(true);
  });
});
```

#### Langkah 7: Implementasi Pengujian Komponen Lengkap
Simpan ke `hands-on/m02/src/components/__tests__/NotificationCenter.spec.ts`:
```typescript
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mount, flushPromises, VueWrapper } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import NotificationCenter from '../NotificationCenter.vue';

describe('NotificationCenter Component Spec', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    setActivePinia(createPinia());
  });

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount();
    }
  });

  it('harus memuat dan merender daftar notifikasi saat onMounted', async () => {
    wrapper = mount(NotificationCenter);

    // Saat onMounted dieksekusi, loading indicator muncul
    expect(wrapper.find('[data-test="loading-indicator"]').exists()).toBe(true);

    // Kuras antrean microtasks pemanggilan MSW
    await flushPromises();

    expect(wrapper.find('[data-test="loading-indicator"]').exists()).toBe(false);
    expect(wrapper.find('[data-test="unread-badge"]').text()).toContain('1 Belum Dibaca');

    const items = wrapper.findAll('[data-test="notification-list"] li');
    expect(items.length).toBe(2);
    expect(wrapper.find('[data-test="item-nt-01"]').classes()).toContain('unread');
  });

  it('harus mengizinkan user mengklik tombol tandai telah dibaca', async () => {
    wrapper = mount(NotificationCenter);
    await flushPromises();

    const markReadBtn = wrapper.find('[data-test="read-btn-nt-01"]');
    expect(markReadBtn.exists()).toBe(true);

    await markReadBtn.trigger('click');
    await flushPromises();

    // Badge unread harus menjadi 0
    expect(wrapper.find('[data-test="unread-badge"]').text()).toContain('0 Belum Dibaca');
    // Tombol tandai dibaca harus hilang karena sudah dibaca
    expect(wrapper.find('[data-test="read-btn-nt-01"]').exists()).toBe(false);
  });
});
```

---

### 13. Exercise

#### Level Easy
* **Tugas**: Tambahkan fitur pencarian (*filter input*) di komponen `NotificationCenter.vue` yang menyaring item notifikasi secara lokal berdasarkan string input teks.
* **Kriteria Pengujian**:
  1. Tulis tes yang memastikan daftar item yang dirender berkurang saat karakter diketik ke dalam input filter.
  2. Pastikan unread badge tetap menampilkan total notifikasi yang belum dibaca dari store global, bukan hasil filter.
* **Instruksi Eksekusi**: Buat file `src/components/__tests__/NotificationCenter.filter.spec.ts`.

#### Level Medium
* **Tugas**: Buat composable `useOnlineStatus` yang mendengarkan event sistem `window.addEventListener('online')` dan `window.addEventListener('offline')`.
* **Kriteria Pengujian**:
  1. Tulis tes menggunakan Vitest fake window event dispatcher.
  2. Validasi bahwa event listener dilepaskan secara bersih saat composable scope di-unmount.
  3. Verifikasi reaktivitas state boolean `isOnline`.

#### Level Hard
* **Tugas**: Implementasikan mekanisme *Optimistic UI with Rollback* pada aksi `markAsRead` di `notificationStore.ts`. Jika endpoint API mengembalikan status HTTP 500, state `read` dari item harus dikembalikan ke status semula (`false`), dan error message harus terisi.
* **Kriteria Pengujian**:
  1. Tulis integration test menggunakan MSW `server.use()` untuk mensimulasikan kegagalan jaringan acak (500).
  2. Assert bahwa UI sesaat menampilkan item sebagai `read: true`, kemudian setelah Promise ditolak (*rejected*), item otomatis kembali menjadi `read: false` dan menampilkan pesan error.

---

### 14. Challenge

**Skenario**:
Anda adalah Principal Frontend Engineer pada platform SaaS Enterprise Multi-Tenant. Anda ditugaskan membangun suite pengujian arsitektur untuk sistem **Dynamic Schema-Driven Form Generator Component** (`DynamicFormRenderer.vue`).

**Spesifikasi Kompleks**:
1. Komponen menerima `schemaUrl: string` via props.
2. Komponen menggunakan Suspense untuk mem-fetch JSON Schema yang mendefinisikan layout form dinamis (tipe input: Text, Currency, Nested Dependent Dropdown).
3. Salah satu field dropdown (Provinsi -> Kota) bersifat *cascading*: memilih Provinsi memicu pemanggilan API kedua ke `/api/geo/cities?provinceId={id}`.
4. Terdapat fitur auto-save draft setiap 30 detik menggunakan web-worker atau debounced timer.
5. Form dienkapsulasi dengan otentikasi token yang diinjeksi via `provide('authContext')`.

**Tantangan Pengujian (Harus Dibuat Tanpa Kompromi Mock Taraf Rendah)**:
1. Bangun pengujian integrasi lengkap menggunakan Vitest, Happy-DOM, dan MSW v2.
2. Tidak boleh mem-mock composable form secara langsung; biarkan seluruh logika binding internal berjalan.
3. Simulasikan skenario di mana pengguna memilih provinsi, jaringan untuk memuat kota mengalami latensi 1200ms, lalu pengguna berganti memilih provinsi lain sebelum request pertama selesai (*Race Condition Cancellation Test*).
4. Verifikasi bahwa data form draft tersimpan ke LocalStorage secara berkala dengan memajukan Fake Timers Vitest tanpa membekukan event loop scheduler Vue.
5. Pertahankan ambang batas *code coverage* 100% lines/branches pada skenario kegagalan parsing skema invalid.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (Pilihan Ganda)
1. Apa fungsi utama dari `flushPromises()` dalam pengujian komponen Vue 3?
   - A. Menghapus seluruh memori cache di Happy-DOM.
   - B. Memaksa pengurasan seluruh antrean microtask dan promise resolver yang tertunda pada event loop JavaScript.
   - C. Meng-unmount komponen secara paksa dari DOM.
   - D. Mereset konfigurasi state Pinia ke nilai inisialisasi awal.

2. Mengapa Happy-DOM sering dipilih menggantikan JSDOM pada arsitektur pengujian Vitest modern?
   - A. Happy-DOM mendukung eksekusi browser WebKit secara fisik.
   - B. Happy-DOM memiliki footprint memori yang jauh lebih ringan dan kecepatan inisialisasi lebih tinggi karena simplifikasi parsing DOM.
   - C. Happy-DOM mengeksekusi tes di dalam container Docker.
   - D. Happy-DOM tidak memerlukan instalasi Node.js.

3. Di mana lokasi eksekusi virtual interceptor yang dilakukan oleh Mock Service Worker (MSW) dalam lingkungan Vitest?
   - A. Pada proxy browser Chromium headless.
   - B. Pada interceptor tingkat kernel sistem operasi.
   - C. Pada Node.js runtime process melalui patch modul native seperti `http`, `https`, dan global `fetch`.
   - D. Pada router internal Vue Router.

4. Kapan kita wajib menggunakan `vi.useFakeTimers()`?
   - A. Saat menguji komponen yang memiliki animasi CSS.
   - B. Saat menguji logika yang mengandalkan fungsi berbasis waktu seperti `setTimeout`, `setInterval`, atau debounce/throttle.
   - C. Saat memanggil API menggunakan MSW.
   - D. Saat menggunakan Vue Router dalam mode history.

5. Apa efek samping jika kita tidak mengeksekusi `wrapper.unmount()` di blok `afterEach`?
   - A. File konfigurasi Vitest akan rusak.
   - B. Event listener global atau timer pada lifecycle `onUnmounted` tidak dibersihkan, memicu memory leak antar worker.
   - C. Komponen otomatis beralih ke mode JSDOM.
   - D. Seluruh tes berikutnya otomatis dianggap lulus.

#### B. Pertanyaan Intermediate (Pilihan Ganda & Analisis)
6. Manakah urutan eksekusi yang benar dari siklus update reaktivitas Vue saat event click terjadi?
   - A. Trigger event -> Setter Trap Proxy -> Microtask flush -> Job Queue Scheduler -> DOM Patch.
   - B. Trigger event -> DOM Patch -> Microtask flush -> Setter Trap Proxy.
   - C. Trigger event -> Setter Trap Proxy -> Scheduler mendaftarkan Job -> Microtask Queue terjadwal -> flushJobs mem-patch DOM.
   - D. Microtask Queue -> Trigger event -> Setter Trap Proxy -> DOM Patch.

7. Perhatikan kode berikut:
   ```typescript
   it('test state', () => {
     const store = useMyStore();
     store.counter = 5;
     expect(store.counter).toBe(5);
   });
   ```
   Apa kerentanan terbesar dari penggalan kode pengujian Pinia di atas?
   - A. `counter` tidak dapat diubah secara langsung tanpa aksi mutasi.
   - B. Pengujian tidak mengisolasi instance Pinia via `setActivePinia(createPinia())`, berpotensi mencemari nilai store pada pengujian selanjutnya.
   - C. Variabel `store` harus dideklarasikan di luar blok `it`.
   - D. Ekspektasi harus dibungkus di dalam `nextTick()`.

8. Bagaimana cara menguji komponen yang me-render kontennya menggunakan `<Teleport to="#dropdown">` di lingkungan headless DOM?
   - A. Menambahkan flag `teleport: false` pada mounting options `@vue/test-utils`.
   - B. Teleport tidak dapat diuji pada unit test dan wajib menggunakan Playwright.
   - C. Menyuntikkan elemen `<div id="dropdown"></div>` secara langsung ke `document.body` sebelum komponen di-mount, lalu memeriksa DOM via native `document.querySelector`.
   - D. Mengubah elemen tujuan Teleport menjadi `body` secara manual di kode produksi.

9. Dalam pengujian composable murni, apa manfaat mengeksekusi composable di dalam helper `withSetup` menggunakan instance `createApp()` minimal?
   - A. Meningkatkan kecepatan eksekusi Vitest menjadi dua kali lipat.
   - B. Memungkinkan composable mengakses lifecycle hooks (`onMounted`, `onUnmounted`) dan dependency injection (`provide/inject`) tanpa overhead merender komponen SFC lengkap.
   - C. Mengonversi Promise asynchronous menjadi synchronous secara otomatis.
   - D. Mencegah penggunaan memori heap V8.

10. Apa indikasi utama terjadinya "Flaky Test" pada pipeline CI/CD frontend?
    - A. Test selalu gagal di setiap run pipeline.
    - B. Test gagal hanya ketika dijalankan di sistem operasi Windows.
    - C. Test kadang berhasil dan kadang gagal pada commit kode yang identik tanpa perubahan apapun.
    - D. Test menghasilkan warning depresiasi pada konsol.

#### C. Skenario Kasus Produksi (Analisis Arsitektur)
11. **Skenario 1**:
    Sebuah test suite untuk komponen dashboard keuangan menghasilkan eksekusi yang sangat lambat (membutuhkan waktu 45 detik untuk 15 tes). Hasil profiling menunjukkan bahwa setiap tes menunggu timeout jaringan gagal selama 3000ms. Setelah diinvestigasi, komponen tersebut mengeksekusi request pelacakan analytics latar belakang ke `https://telemetry.enterprise.com/collect`.
    *Pertanyaan*: Apa perbaikan arsitektural tercepat dan terbersih pada layer Vitest/MSW untuk menanggulangi masalah ini tanpa mematikan fitur analytics di kode produksi?

12. **Skenario 2**:
    Sebuah komponen form transaksi asinkron mengimplementasikan proteksi tombol Submit ganda:
    ```typescript
    const isSubmitting = ref(false);
    async function submit() {
      if (isSubmitting.value) return;
      isSubmitting.value = true;
      await api.transfer();
      isSubmitting.value = false;
    }
    ```
    Pada test suite, pengembang memicu tombol dua kali secara berurutan:
    ```typescript
    await wrapper.find('button').trigger('click');
    await wrapper.find('button').trigger('click');
    ```
    Namun, mock API mendeteksi bahwa fungsi `api.transfer()` tetap terpanggil 2 kali. Jelaskan penyebab internal pada level *call stack* dan event loop, serta solusinya.

13. **Skenario 3**:
    Tim arsitektur mewajibkan transisi dari Mocking Unit VTU ke Playwright Component Testing (CT) untuk komponen interaktif tingkat tinggi (DataGrid dengan Virtual Scrolling).
    *Pertanyaan*: Sebutkan dua alasan teknis mengapa Happy-DOM gagal memvalidasi fungsionalitas Virtual Scrolling, dan bagaimana arsitektur browser nyata Playwright menyelesaikan limitasi tersebut?

---

#### Kunci Jawaban & Panduan Evaluasi

##### Bagian A & B
1. **B** — `flushPromises` menuntaskan seluruh rantai antrean microtask dan promise yang tertunda di global microtask queue.
2. **B** — Happy-DOM mengeliminasi kalkulasi layout dan rendering visual kompleks yang tidak diperlukan, menghasilkan kecepatan parsing yang masif.
3. **C** — MSW Node mengintersepsi network stack native di lapisan engine runtime Node.js.
4. **B** — Fake timers mengendalikan simulasi waktu secara deterministik tanpa menahan thread eksekusi aktual.
5. **B** — Tidak melakukan unmount membiarkan instance komponen tetap hidup di memori, menjaga listener aktif yang mencemari tes berikutnya.
6. **C** — Siklus reaktivitas: Event -> Setter Trap Proxy -> Scheduler Job Queue -> Microtask Enqueue -> Microtask Flush -> DOM Patch.
7. **B** — Pengujian memanipulasi store global tanpa isolasi Pinia (`setActivePinia`), memicu state leakage.
8. **C** — Teleport memindahkan VNode di luar hierarchy wrapper; elemen target harus dibuat manual di `document.body` sandbox.
9. **B** — `withSetup` menyediakan context app minimal yang valid sehingga lifecycle hooks dan provide/inject dapat berfungsi legal tanpa template rendering.
10. **C** — Flaky test didefinisikan sebagai tes non-deterministik yang menghasilkan status pas/fail berbeda pada basis kode yang tidak berubah.

##### Bagian C (Kasus Produksi)
11. **Solusi Skenario 1**:
    Konfigurasikan MSW default fallback handler atau mock global handler untuk rute telemetri tersebut:
    ```typescript
    http.post('https://telemetry.enterprise.com/collect', () => {
      return new HttpResponse(null, { status: 204 });
    })
    ```
    Dan pastikan runner Vitest dijalankan dengan flag `server.listen({ onUnhandledRequest: 'error' })` agar URL liar yang belum di-mock langsung memicu kegagalan instan (fail-fast) alih-alih menunggu network timeout sistem operasi.

12. **Solusi Skenario 2**:
    *Penyebab*: Pemanggilan `trigger('click')` pertama kali mengubah `isSubmitting.value = true`, namun jika pemanggilan `trigger('click')` kedua dilakukan secara sinkron berturut-turut pada baris berikutnya tanpa memberi jeda mikro, scheduler Vue belum sempat menyelesaikan transisi DOM atau state locking jika pengecekan bergantung pada atribut `:disabled` elemen tombol di DOM. Lebih lanjut, jika pemanggilan fungsi di-debounce melalui scheduler, loop sinkronus akan mengeksekusi blok kode sebelum microtask resolving pertama dieksekusi.
    *Solusi*: Lakukan assertion sinkronisasi eksplisit dengan `await flushPromises()` atau pastikan tombol