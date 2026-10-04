# BAB 07: Asynchronous Flow, Forms, dan Data Fetching
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis & Mengeliminasi Race Conditions**: Mengimplementasikan mekanisme pembatalan request asinkron (*request cancellation*) menggunakan `AbortController` terintegrasi dengan siklus hidup reaktivitas Vue 3 (`onScopeDispose`, `watchEffect` cleanup).
2. **Merancang Custom Async State Machine**: Membangun composable *data fetching* tingkat lanjut yang mengisolasi state transition (`idle`, `pending`, `success`, `error`), deduplikasi request (*in-flight request deduplication*), dan *stale-while-revalidate* (SWR) cache pattern.
3. **Mengorkestrasi Enterprise Form State**: Mengembangkan arsitektur formulir berbasis *schema validation* (Zod) dengan dukungan *deeply nested arrays*, *dirty/touched tracking*, *asynchronous cross-field validation*, dan zero re-render overhead.
4. **Mengeksekusi Optimistic UI Updates dengan Rollback**: Mengimplementasikan mutasi data dengan pembaruan cache optimistik, snapshotting state lokal, dan mekanisme *rollback* deterministik saat terjadi kegagalan jaringan (*network partition*).
5. **Menerapkan Concurrency Strategies**: Menerapkan strategi konkurensi (SwitchMap, ExhaustMap, ConcatMap equivalent) pada composable Vue untuk menangani event berfrekuensi tinggi (autocompletion, real-time polling, dan batching mutasi).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* **Vue 3 Reactivity Internals**: Pemahaman mendalam mengenai `EffectScope`, `shallowRef`, `triggerRef`, `toValue`, `customRef`, serta perbedaan microtask batching pada Vue Reactivity Scheduler vs Browser Event Loop.
* **Modern JavaScript & TypeScript Concurrency**: ECMAScript Promises, `AsyncIterator`, microtask queue vs macrotask queue, `AbortSignal.any()` (ES2024), Typed Generics lanjutan, dan Type Narrowing / Discriminated Unions.
* **HTTP/Network Protocols**: Semantik REST, HTTP Caching headers (`ETag`, `Cache-Control`, `If-None-Match`), SSE (Server-Sent Events), WebSocket lifecycle, dan idempotent vs non-idempotent operations.

---

### 3. Concept & Internal Architecture

#### 3.1 Lifecycle Reactivity Scheduler vs Asynchronous Microtasks

Pada Vue 3, interaksi antara Reactivity System (`reactive`, `ref`, `computed`) dan operasi asinkron tidak berjalan pada thread terpisah. Keduanya berbagi *Call Stack* dan *Event Loop* browser yang sama.

```
+-------------------------------------------------------------------------+
|                              EVENT LOOP                                 |
|                                                                         |
|  +------------------+    +-------------------------------------------+  |
|  |    Task Queue    |    |              Microtask Queue              |  |
|  |  (Macrotasks)    |    |                                           |  |
|  |                  |    |  +-------------------------------------+  |  |
|  |  - I/O           |    |  | Vue Scheduler Job Queue             |  |  |
|  |  - UI Events     |    |  | (queueJob, queuePostFlushCb)        |  |  |
|  |  - setTimeout    |    |  +-------------------------------------+  |  |
|  |                  |    |  - Native Promise.then()                  |  |
|  |                  |    |  - MutationObserver                       |  |
|  +--------+---------+    +---------------------+---------------------+  |
|           |                                    |                        |
+-----------|------------------------------------|------------------------+
            v                                    v
     [Exec Task] -----------------------> [Flush Microtasks]
```

Ketika nilai reaktif berubah di dalam blok asinkron (`await fetchData()`):
1. **Sebelum `await`**: Kode dieksekusi secara sinkron di dalam *Effect Scope* aktif. Depedensi reaktif terlacak (*tracked*).
2. **Titik `await`**: Eksekusi fungsi ditangguhkan. Mesin browser mendaftarkan callback kelanjutan ke dalam *Microtask Queue*.
3. **Setelah `await`**: Callback kelanjutan dieksekusi. Pada titik ini, jika fungsi composable telah menyelesaikan eksekusi sinkron awalnya, pelacakan dependensi otomatis (`track`) dapat terputus jika tidak diisolasi dalam EffectScope yang persisten. Jika komponen telah di-*unmount* sebelum microtask selesai, penulisan ke state reaktif dapat memicu mutasi state terlantar (*dangling state mutation*) atau *memory leak*.

#### 3.2 Race Conditions & Cleanup Mechanism pada `watchEffect`

Salah satu masalah paling kritis pada data-fetching berbasis input reaktif (misalnya: parameter pencarian atau pagination) adalah *out-of-order response resolution*. 

```
Timeline:
T1: Query 'A' dikirim (Request 1 - Latensi 800ms)
T2: Query 'AB' dikirim (Request 2 - Latensi 200ms)
T3: Request 2 selesai -> State diisi data 'AB'
T4: Request 1 selesai -> State ditimpa data 'A' (DATA TIDAK KONSISTEN!)
```

Vue 3 mengatasi ini secara native via parameter `onCleanup` pada `watch` dan `watchEffect`. Secara internal:
* Setiap kali efek dijalankan ulang (*re-run*), Vue memanggil fungsi pembersih (*cleanup callback*) yang didaftarkan pada eksekusi sebelumnya.
* Cleanup juga dieksekusi secara otomatis saat *EffectScope* pemilik dihancurkan (misalnya saat komponen mengalami *unmount*).

```
watch(param, async (newVal, oldVal, onCleanup) => {
  const controller = new AbortController();
  onCleanup(() => controller.abort()); // Dijalankan SEBELUM efek berikutnya jalan / saat unmount

  const data = await fetch(`/api/search?q=${newVal}`, { signal: controller.signal });
  state.value = data;
});
```

#### 3.3 Dynamic Schema-Driven Form Architecture

Pada tingkat enterprise, manajemen state form tidak boleh mengandalkan `v-model` primitif yang berserakan. Dibutuhkan arsitektur yang memisahkan:
1. **Values State**: Data mentah yang sedang diedit.
2. **Meta State**: Pelacakan status per-field (`touched`, `dirty`, `validating`, `valid`, `invalid`).
3. **Validation Engine**: Validator asinkron terisolasi (Zod schema compiler) yang berjalan di luar thread reaktivitas template untuk mencegah blocking render.

```
+-------------------------------------------------------------+
|                     Form Controller                         |
+-------------------------------------------------------------+
         |                                           ^
         | Updates                                   | Validates
         v                                           |
+------------------+    Diff Check     +----------------------+
|   Values Store   | ----------------> |  Zod Schema Engine   |
| (Deep Reactive)  |                   | (Sync/Async Parser)  |
+------------------+                   +----------------------+
         |                                           |
         +--------------------+                      |
                              v                      v
                   +------------------------------------+
                   |             Meta Store             |
                   | (Dirty, Touched, Error Collections)|
                   +------------------------------------+
                                      |
                                      v
                             [Exposed to UI Tree]
```

---

### 4. Why & What

| Pendekatan Konvensional | Pendekatan Enterprise Modern |
| :--- | :--- |
| `ref(null)` + `fetch` langsung di lifecycle hook `onMounted`. | Composable terisolasi dengan state machine eksplisit (`idle`, `pending`, `success`, `error`). |
| Mengabaikan pembatalan request saat komponen ditutup/parameter berubah. | Penggunaan `AbortController` deterministik dengan *auto-teardown* via `onScopeDispose`. |
| Menggunakan `v-model` langsung tanpa tracking status `dirty` atau `touched`. | Form state orchestration dengan validasi schema Zod, dirty-checking via baseline snapshot, dan field-level isolation. |
| Menunggu API selesai merespons sebelum memperbarui UI (Pessimistic UI). | Optimistic UI Updates dengan immutable cache snapshotting dan automatic rollback saat mutasi gagal. |
| Global loading overlay blocking seluruh layar aplikasi. | Granular async boundaries dengan status lokal per field/operasi dan deduplikasi request in-flight. |

---

### 5. How (Workflow Detail)

Alur kerja arsitektur *Optimistic Mutation Engine* dengan *Network Reconciliation*:

```
[User Action: Edit Record]
           |
           v
[1. Create Snapshot of Current State]
           |
           v
[2. Optimistically Mutate Local Cache/State]
           |
           v
[3. Update UI Reactively (Zero Latency Perceived)]
           |
           v
[4. Dispatch HTTP Network Mutation (POST/PUT/PATCH)]
           |
           +-----------------------+-----------------------+
           |                                               |
           v (Success: HTTP 2xx)                           v (Error: HTTP 4xx/5xx/Network)
[5A. Commit State]                                 [5B. Revert State to Snapshot]
           |                                               |
           v                                               v
[6A. Reconcile with Server Payload]                [6B. Display Granular Error Banner]
           |                                               |
           v                                               v
[7A. Invalidate Correlated Query Caches]           [7B. Mark Form as Out-of-Sync]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kasir Pesanan Restoran Cepat Saji (Fast Food Order Counter)

Bayangkan proses memesan burger di restoran berkecepatan tinggi:
* **Naive Approach**: Kasir menerima pesanan Anda, berjalan ke dapur, menunggu koki memanggang daging selama 5 menit, mengambil burger, lalu kembali ke meja kasir untuk melayani orang berikutnya. Pelanggan lain menunggu dalam antrean panjang yang terblokir.
* **Enterprise Asynchronous Flow**: Kasir mencatat pesanan Anda, memberikan nomor antrean (Promise/Signal), dan langsung melayani antrean berikutnya. Koki di dapur bekerja secara asinkron.
* **Race Condition**: Pelanggan A memesan Burger, lalu berubah pikiran memesan Salad. Dapur harus membatalkan (*AbortSignal*) pembuatan burger agar pelanggan tidak menerima makanan yang salah ketika keduanya selesai dimasak.
* **Optimistic Update**: Kasir langsung memberikan struk berstatus "Pesanan Anda Sedang Disiapkan" dan memperbarui monitor tampilan tanpa harus menunggu daging selesai digoreng. Jika ternyata kompor meledak (Server Error), kasir membatalkan pesanan, mengembalikan uang Anda, dan memperbarui monitor kembali ke state awal (*Rollback*).

```
                      RACE CONDITION RESOLUTION
                      
 Client Request Timeline               Backend Execution
 -----------------------               -----------------
 Param: 'vue'     ---[Request #1]----------> [Process...] (Late Response)
                        |
 Param: 'vue-router' -[Request #2]-----> [Process...] (Fast Response)
                        |                      |
                        |                      v
                        |                 [Resolves #2] ---> Render 'vue-router'
                        |
            [#1 Aborted via Signal]            x
                        |
                        +-------------------- [Signal Abort Triggered]
                                              Payload Rejected!
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Composable `useAsyncQuery` dengan Auto-cancellation

Contoh composable murni TypeScript tanpa dependensi pihak ketiga, yang mengimplementasikan eksekusi asinkron deterministik dengan `AbortController`.

```typescript
// composables/useAsyncQuery.ts
import { ref, shallowRef, isRef, watchEffect, toValue, type Ref, type MaybeRefOrGetter } from 'vue';

export interface AsyncState<T> {
  data: Ref<T | null>;
  error: Ref<Error | null>;
  isLoading: Ref<boolean>;
  execute: () => Promise<void>;
  abort: () => void;
}

export function useAsyncQuery<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  watchSource?: MaybeRefOrGetter<unknown>
): AsyncState<T> {
  const data = shallowRef<T | null>(null);
  const error = shallowRef<Error | null>(null);
  const isLoading = ref<boolean>(false);

  let currentController: AbortController | null = null;

  const abort = () => {
    if (currentController) {
      currentController.abort();
      currentController = null;
    }
  };

  const execute = async () => {
    // Batalkan request yang sedang berjalan (In-flight cancellation)
    abort();

    currentController = new AbortController();
    const signal = currentController.signal;

    isLoading.value = true;
    error.value = null;

    try {
      const result = await fetcher(signal);
      if (!signal.aborted) {
        data.value = result;
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // Abaikan abort error karena ini aksi yang diharapkan
        return;
      }
      if (!signal.aborted) {
        error.value = err instanceof Error ? err : new Error(String(err));
      }
    } finally {
      if (!signal.aborted) {
        isLoading.value = false;
      }
    }
  };

  if (watchSource) {
    watchEffect((onCleanup) => {
      // Akses dependensi agar terdaftar secara reaktif
      toValue(watchSource);
      execute();
      onCleanup(() => abort());
    });
  }

  return {
    data: data as Ref<T | null>,
    error,
    isLoading,
    execute,
    abort
  };
}
```

#### 7.2 Practical Example: Enterprise Dynamic Form Manager dengan Zod Schema & Optimistic Mutation

Implementasi sistem formulir dinamis dengan validasi schema mendalam, pelacakan *dirty state*, dan integrasi mutasi optimistik.

```typescript
// types/form.ts
import { z } from 'zod';

export const UserProfileSchema = z.object({
  fullName: z.string().min(3, 'Nama minimal 3 karakter').max(50),
  email: z.string().email('Format email tidak valid'),
  roles: z.array(z.string()).min(1, 'Minimal pilih satu peran'),
  addresses: z.array(
    z.object({
      street: z.string().min(5, 'Alamat minimal 5 karakter'),
      city: z.string().min(2, 'Kota minimal 2 karakter'),
      isPrimary: z.boolean()
    })
  ).min(1, 'Minimal satu alamat terdaftar')
});

export type UserProfileForm = z.infer<typeof UserProfileSchema>;
```

```typescript
// composables/useEnterpriseForm.ts
import { ref, reactive, computed, toRaw } from 'vue';
import { z } from 'zod';

export function useEnterpriseForm<T extends Record<string, any>>(
  schema: z.ZodSchema<T>,
  initialValues: T
) {
  // Deep clone initial state untuk perbandingan dirty-checking
  const initialSnapshot = JSON.parse(JSON.stringify(initialValues)) as T;
  const values = reactive<T>(JSON.parse(JSON.stringify(initialValues)));
  
  const errors = ref<Partial<Record<keyof T | string, string>>>({});
  const touched = reactive<Record<string, boolean>>({});
  const isSubmitting = ref(false);

  const isDirty = computed(() => {
    return JSON.stringify(toRaw(values)) !== JSON.stringify(initialSnapshot);
  });

  const validateField = (path: string) => {
    const result = schema.safeParse(values);
    if (result.success) {
      delete errors.value[path];
      return true;
    }

    const fieldError = result.error.issues.find(
      (issue) => issue.path.join('.') === path
    );

    if (fieldError) {
      errors.value[path] = fieldError.message;
      return false;
    } else {
      delete errors.value[path];
      return true;
    }
  };

  const setTouched = (path: string) => {
    touched[path] = true;
    validateField(path);
  };

  const validateAll = (): boolean => {
    const result = schema.safeParse(values);
    if (result.success) {
      errors.value = {};
      return true;
    }

    const formattedErrors: Record<string, string> = {};
    for (const issue of result.error.issues) {
      const path = issue.path.join('.');
      if (!formattedErrors[path]) {
        formattedErrors[path] = issue.message;
      }
    }
    errors.value = formattedErrors;
    return false;
  };

  const reset = () => {
    Object.assign(values, JSON.parse(JSON.stringify(initialSnapshot)));
    Object.keys(touched).forEach((key) => delete touched[key]);
    errors.value = {};
  };

  return {
    values,
    errors,
    touched,
    isDirty,
    isSubmitting,
    setTouched,
    validateField,
    validateAll,
    reset
  };
}
```

```vue
<!-- components/UserProfileEditor.vue -->
<template>
  <form @submit.prevent="handleSubmit" class="p-6 max-w-4xl mx-auto space-y-6 bg-white shadow rounded-lg">
    <div class="border-b pb-4">
      <h2 class="text-xl font-bold text-gray-900">Manajemen Profil Pengguna</h2>
      <p class="text-sm text-gray-500">Edit informasi profil dengan validasi instan dan sinkronisasi data.</p>
    </div>

    <!-- Alert Status -->
    <div v-if="submissionError" class="p-4 bg-red-50 border-l-4 border-red-500 text-red-700">
      <p class="font-medium">Kesalahan Sinkronisasi</p>
      <p class="text-sm">{{ submissionError }}</p>
    </div>

    <!-- Full Name -->
    <div>
      <label class="block text-sm font-medium text-gray-700">Nama Lengkap</label>
      <input
        v-model="values.fullName"
        @blur="setTouched('fullName')"
        type="text"
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
        :class="{ 'border-red-500': touched['fullName'] && errors['fullName'] }"
      />
      <span v-if="touched['fullName'] && errors['fullName']" class="text-xs text-red-600 mt-1 block">
        {{ errors['fullName'] }}
      </span>
    </div>

    <!-- Email -->
    <div>
      <label class="block text-sm font-medium text-gray-700">Email Perusahaan</label>
      <input
        v-model="values.email"
        @blur="setTouched('email')"
        type="email"
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
        :class="{ 'border-red-500': touched['email'] && errors['email'] }"
      />
      <span v-if="touched['email'] && errors['email']" class="text-xs text-red-600 mt-1 block">
        {{ errors['email'] }}
      </span>
    </div>

    <!-- Dynamic Addresses Sub-form -->
    <div class="space-y-4">
      <div class="flex justify-between items-center">
        <h3 class="text-lg font-medium text-gray-900">Daftar Alamat</h3>
        <button
          type="button"
          @click="addAddress"
          class="px-3 py-1 bg-indigo-50 text-indigo-600 rounded-md text-sm font-semibold hover:bg-indigo-100"
        >
          + Tambah Alamat
        </button>
      </div>

      <div
        v-for="(address, idx) in values.addresses"
        :key="idx"
        class="p-4 border rounded-md relative bg-gray-50 space-y-3"
      >
        <button
          type="button"
          @click="removeAddress(idx)"
          class="absolute top-2 right-2 text-gray-400 hover:text-red-500 text-sm"
        >
          Hapus
        </button>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-medium text-gray-700">Jalan</label>
            <input
              v-model="address.street"
              @blur="setTouched(`addresses.${idx}.street`)"
              type="text"
              class="mt-1 block w-full rounded-md border-gray-300 shadow-sm sm:text-xs"
            />
            <span
              v-if="touched[`addresses.${idx}.street`] && errors[`addresses.${idx}.street`]"
              class="text-xs text-red-600 mt-1 block"
            >
              {{ errors[`addresses.${idx}.street`] }}
            </span>
          </div>

          <div>
            <label class="block text-xs font-medium text-gray-700">Kota</label>
            <input
              v-model="address.city"
              @blur="setTouched(`addresses.${idx}.city`)"
              type="text"
              class="mt-1 block w-full rounded-md border-gray-300 shadow-sm sm:text-xs"
            />
            <span
              v-if="touched[`addresses.${idx}.city`] && errors[`addresses.${idx}.city`]"
              class="text-xs text-red-600 mt-1 block"
            >
              {{ errors[`addresses.${idx}.city`] }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Form Actions -->
    <div class="flex items-center justify-end space-x-4 border-t pt-4">
      <button
        type="button"
        @click="reset"
        :disabled="!isDirty || isSubmitting"
        class="px-4 py-2 border rounded-md text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
      >
        Reset Perubahan
      </button>
      <button
        type="submit"
        :disabled="isSubmitting"
        class="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 flex items-center"
      >
        <span v-if="isSubmitting" class="inline-block animate-spin mr-2">⟳</span>
        Simpan Profil
      </button>
    </div>
  </form>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { UserProfileSchema, type UserProfileForm } from '../types/form';
import { useEnterpriseForm } from '../composables/useEnterpriseForm';

const props = defineProps<{
  initialData: UserProfileForm;
  onSave: (payload: UserProfileForm) => Promise<void>;
}>();

const emit = defineEmits<{
  (e: 'saved', payload: UserProfileForm): void;
}>();

const submissionError = ref<string | null>(null);

const {
  values,
  errors,
  touched,
  isDirty,
  isSubmitting,
  setTouched,
  validateAll,
  reset
} = useEnterpriseForm<UserProfileForm>(UserProfileSchema, props.initialData);

const addAddress = () => {
  values.addresses.push({ street: '', city: '', isPrimary: false });
};

const removeAddress = (index: number) => {
  if (values.addresses.length > 1) {
    values.addresses.splice(index, 1);
  }
};

const handleSubmit = async () => {
  submissionError.value = null;

  if (!validateAll()) {
    return;
  }

  isSubmitting.value = true;

  // Snapshot data sebelum mutasi (Optimistic UI Pattern)
  const previousData = JSON.parse(JSON.stringify(props.initialData));

  try {
    await props.onSave(values);
    emit('saved', values);
  } catch (err: unknown) {
    // Rollback error logic
    submissionError.value = err instanceof Error ? err.message : 'Gagal menyimpan perubahan ke server.';
    console.error('Optimistic mutation failure. Reverting state or signaling UI...', previousData);
  } finally {
    isSubmitting.value = false;
  }
};
</script>
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Real-Time Ledger Reconciliation & High-Frequency Allocation Engine
* **Konteks**: Platform SaaS FinTech B2B yang menangani alokasi portofolio perbankan dengan frekuensi pembaruan tinggi melalui Server-Sent Events (SSE) dan REST mutasi simultan.
* **Tantangan Arsitektur**:
  1. Operator mengubah bobot alokasi portofolio pada formulir tabular dinamis (ratusan baris aset).
  2. Data harga pasar terus berfluktuasi via stream SSE setiap 250ms.
  3. Pengiriman pesanan alokasi baru harus menerapkan *Optimistic UI* di frontend untuk latensi perceived 0ms, namun harus dapat melakukan rollback parsial per baris aset jika *core banking* menolak eksekusi (misal: *liquidity limit exceeded*).
  4. Mencegah *race condition* antara snapshot SSE yang masuk dan request mutasi pengguna yang sedang *in-flight*.

#### Solusi Arsitektur
Pemisahan cache layer menjadi dua tingkat:
1. **Server-Synchronized Baseline Cache**: Dikendalikan secara eksklusif oleh SSE stream dan request query.
2. **Local Work-In-Progress (WIP) Mutation Layer**: Reactive proxy yang mencatat *delta patching* yang belum di-commit.

```
                    +--------------------------------+
                    | Real-Time SSE Market Feed Stream|
                    +--------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
|                          Ledger Cache Engine                           |
|                                                                        |
|  +---------------------------+       +------------------------------+  |
|  | Base Server State (Store) | <---  | Reconciliation Resolver      |  |
|  +---------------------------+       | (Locks baseline on in-flight)|  |
|               |                      +------------------------------+  |
|               v                                     ^                  |
|  +---------------------------+                      |                  |
|  | Computed Effective State  |                      |                  |
|  | (Base + Optimistic Deltas)|                      |                  |
|  +---------------------------+                      |                  |
|               |                                     |                  |
+---------------|-------------------------------------|------------------+
                v                                     |
       [Render Ledger UI]                             |
                |                                     |
    (User Adjusts Allocation)                         |
                |                                     |
                v                                     |
    +-----------------------+                         |
    | Optimistic Delta Log  | ------------------------+
    | (UUID -> Payload)     |  (Dispatched HTTP Mutation POST)
    +-----------------------+
```

```typescript
// composables/useLedgerReconciliation.ts
import { shallowRef, ref, computed } from 'vue';

export interface LedgerItem {
  id: string;
  assetCode: string;
  weight: number; // Percentage 0 - 100
  valuation: number;
}

export function useLedgerReconciliation() {
  const baseLedger = shallowRef<Map<string, LedgerItem>>(new Map());
  const pendingDeltas = shallowRef<Map<string, Partial<LedgerItem>>>(new Map());
  const networkLock = ref(false);

  // Computed state yang menggabungkan base data dengan perubahan optimistik
  const effectiveLedger = computed(() => {
    const combined = new Map<string, LedgerItem>(baseLedger.value);
    for (const [id, delta] of pendingDeltas.value.entries()) {
      const baseItem = combined.get(id);
      if (baseItem) {
        combined.set(id, { ...baseItem, ...delta });
      }
    }
    return Array.from(combined.values());
  });

  // Dipanggil ketika stream data pasar SSE tiba
  const applyServerStreamUpdate = (serverItems: LedgerItem[]) => {
    const nextMap = new Map(baseLedger.value);
    for (const item of serverItems) {
      nextMap.set(item.id, item);
    }
    baseLedger.value = nextMap;
  };

  // Eksekusi mutasi optimistik dengan rollback atomik
  const mutateAllocationOptimistic = async (
    assetId: string,
    newWeight: number,
    apiClient: (id: string, weight: number) => Promise<LedgerItem>
  ) => {
    const deltaKey = `${assetId}-${Date.now()}`;
    
    // 1. Terapkan delta optimistik secara lokal
    const nextDeltas = new Map(pendingDeltas.value);
    nextDeltas.set(assetId, { weight: newWeight });
    pendingDeltas.value = nextDeltas;

    try {
      networkLock.value = true;
      // 2. Kirim mutasi ke backend
      const confirmedItem = await apiClient(assetId, newWeight);

      // 3. Rekonsiliasi: Update base ledger dengan data otoritatif server
      const nextBase = new Map(baseLedger.value);
      nextBase.set(assetId, confirmedItem);
      baseLedger.value = nextBase;
    } catch (error) {
      // 4. Rollback: Hapus delta optimistik jika gagal
      console.error(`Mutation failed for asset ${assetId}. Rolling back delta.`, error);
      throw error;
    } finally {
      // 5. Bersihkan delta lokal dari pending map
      const cleanupDeltas = new Map(pendingDeltas.value);
      cleanupDeltas.delete(assetId);
      pendingDeltas.value = cleanupDeltas;
      networkLock.value = false;
    }
  };

  return {
    effectiveLedger,
    applyServerStreamUpdate,
    mutateAllocationOptimistic,
    networkLock
  };
}
```

---

### 9. Trade-offs

| Kriteria | Custom Composables (`ref` + `AbortController`) | TanStack Query (`@tanstack/vue-query`) | Pinia Store Actions |
| :--- | :--- | :--- | :--- |
| **Bundle Size Overhead** | **Nol / Sangat Rendah** (~0.5KB runtime native). | **Sedang** (~12-15KB gzipped). | **Rendah** (~1.5KB gzipped untuk Pinia core). |
| **Cache Management & Garbage Collection** | Manual. Harus merancang mekanisme `Map` & `WeakMap` sendiri. | **Otomatis & Komprehensif** (Stale time, GC time, Structural Sharing). | Semi-manual. State disimpan di memory secara persisten kecuali di-clear. |
| **Deduping & Background Invalidation** | Harus diimplementasikan manual secara modular. | **Native Out-of-the-Box**. Sangat matang untuk enterprise flow. | Memerlukan implementasi Promise memoization manual. |
| **Optimistic Rollback Complexity** | Manual (memerlukan closure snapshot state sebelum mutasi). | **Deklaratif via Context Lifecycle** (`onMutate`, `onError`, `onSettled`). | Manual menggunakan try/catch/finally di dalam action logic. |
| **Cocok Untuk Kasus** | Komponen SDK terisolasi, micro-frontends dengan limit bundle ketat. | Aplikasi skala enterprise dengan relasi data kompleks dan caching intensif. | Operasi state global yang membutuhkan persistensi lintas halaman/rute. |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Zombie Callbacks & Memory Leaks pada Unmounted Components
* **Penyebab**: Menjalankan asynchronous promise tanpa mendeteksi apakah komponen tempat composable aktif sudah di-*unmount* sebelum mengeksekusi reaktifitas.
* **Dampak**: Mutasi memory internal yang tidak terpakai, warning Vue runtime: *Cannot set reactive property on unmounted component*, serta pemborosan memori.
* **Solusi**: Gunakan `getCurrentScope()` dan `onScopeDispose` untuk membersihkan atau membatalkan operasi asinkron.

```typescript
// FIX
import { getCurrentScope, onScopeDispose } from 'vue';

export function useSafeAsyncOperation() {
  const scope = getCurrentScope();

  const runOperation = async () => {
    const res = await fetch('/api/data');
    const json = await res.json();

    // Verifikasi apakah EffectScope masih aktif sebelum memproses state
    if (scope && scope.active) {
      data.value = json;
    }
  };

  return { runOperation };
}
```

#### Mistake 2: Destructuring Objek Reaktif yang Mengakibatkan Reactivity Loss
* **Penyebab**: Melakukan destructuring langsung pada kembalian composable async atau reactive props tanpa `toRefs` atau `toValue`.
* **Dampak**: Variabel kehilangan sifat reaktif (*loss of reactivity*). Form tidak memicu update, atau perubahan parameter tidak memicu pemanggilan ulang `watchEffect`.
* **Solusi**: Selalu pertahankan referensi reaktif atau bungkus dengan `toRefs()`.

#### Mistake 3: Unhandled Promise Rejections dari `AbortController.abort()`
* **Penyebab**: Membatalkan `fetch` menggunakan `AbortSignal` memicu pelemparan native DOMException bertipe `AbortError`. Jika try/catch menganggap semua error adalah network error fatal, antarmuka akan menampilkan "Koneksi Gagal" secara keliru.
* **Solusi**: Filter error spesifik `err.name === 'AbortError'` di blok `catch`.

#### Mistake 4: Async Validation Race Condition pada Dynamic Forms
* **Penyebab**: Validasi async (misal: cek keunikan email) memicu network request. Pengguna mengetik cepat `user@a` lalu `user@acme.com`. Respons dari `user@a` selesai belakangan dan menimpa validasi `user@acme.com`.
* **Solusi**: Gunakan pembatalan sinyal atau pembungkus *debounce* berbasis switchMap untuk seluruh async validator.

#### Mistake 5: Deep Mutation Tracking Tanpa Structural Sharing
* **Penyebab**: Melakukan `JSON.parse(JSON.stringify(obj))` setiap kali *keystroke* untuk mendeteksi `isDirty`.
* **Dampak**: UI jank/frame drop parah pada form kompleks dengan ribuan field atau array bersarang.
* **Solusi**: Buat perbandingan terfokus per field menggunakan Hash Map atau gunakan library diffing berbasis *shallow object equality* bertahap.

---

### 11. Best Practices (Production Checklist)

- [ ] **Signal Cancellation**: Setiap async network request terhubung dengan `AbortController` yang merespons perubahan dependensi atau unmount komponen.
- [ ] **Scope Teardown**: Semua listener (SSE, WebSocket, Window Events) dibersihkan dalam `onScopeDispose` atau `onUnmounted`.
- [ ] **Explicit Loading States**: Membedakan antara `isInitialLoading` (fetch pertama), `isFetching` (background refetch), dan `isMutating`.
- [ ] **Schema Immutability**: Schema validasi (Zod/Valibot) didefinisikan secara statis di luar runtime scope composable untuk mencegah recompilation overhead.
- [ ] **Debounced Async Field Validation**: Validasi asinkron yang terhubung ke server (misal: pengecekan keunikan username) selalu menggunakan debounce (minimal 300-500ms).
- [ ] **Optimistic Rollback Safety**: Setiap optimistic update wajib menyimpan snapshot immutable sebelum modifikasi lokal.
- [ ] **Shallow Ref for Large Payloads**: Menggunakan `shallowRef` untuk payload API berukuran besar (> 500 records) untuk mencegah Vue melakukan deep reactivity wrapping yang mahal.
- [ ] **Centralized HTTP Interceptor Integration**: Mengintegrasikan sistem penanganan refresh token JWT secara transparan tanpa merusak concurrency controller pada caller level.

---

### 12. Hands-on Practice

Buka direktori proyek Anda dan buat berkas berikut pada path: `hands-on/m02/`

#### Task 1: Setup File Struktur
Pastikan folder `hands-on/m02/` sudah terinisialisasi:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

#### Task 2: Implementasi Reusable Async Concurrency Composable
Buat file `hands-on/m02/useTaskQueue.ts`:

```typescript
// hands-on/m02/useTaskQueue.ts
import { ref, shallowRef, onScopeDispose } from 'vue';

export type Task<T> = (signal: AbortSignal) => Promise<T>;

export function useTaskQueue<T>() {
  const data = shallowRef<T | null>(null);
  const error = shallowRef<Error | null>(null);
  const isRunning = ref(false);

  let activeController: AbortController | null = null;

  const cancel = () => {
    if (activeController) {
      activeController.abort();
      activeController = null;
    }
  };

  const run = async (task: Task<T>): Promise<T | null> => {
    cancel();

    activeController = new AbortController();
    const signal = activeController.signal;

    isRunning.value = true;
    error.value = null;

    try {
      const result = await task(signal);
      if (!signal.aborted) {
        data.value = result;
        return result;
      }
      return null;
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return null;
      }
      const resolvedError = err instanceof Error ? err : new Error(String(err));
      if (!signal.aborted) {
        error.value = resolvedError;
      }
      throw resolvedError;
    } finally {
      if (!signal.aborted) {
        isRunning.value = false;
      }
    }
  };

  onScopeDispose(() => {
    cancel();
  });

  return {
    data,
    error,
    isRunning,
    run,
    cancel
  };
}
```

#### Task 3: Implementasi Test Runner Lokal
Buat file `hands-on/m02/testRunner.ts` untuk memverifikasi fungsionalitas concurrency:

```typescript
// hands-on/m02/testRunner.ts
import { effectScope } from 'vue';
import { useTaskQueue } from './useTaskQueue';

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function executeTest() {
  console.log('--- STARTING CONCURRENCY SUITE ---');
  const scope = effectScope();

  await scope.run(async () => {
    const queue = useTaskQueue<string>();

    console.log('[Test 1] Dispatching Task A (Long: 500ms)...');
    queue.run(async (signal) => {
      await delay(500);
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
      return 'Result A';
    }).then(res => console.log('Task A resolved with:', res))
      .catch(() => console.log('Task A rejected (expected abort)'));

    await delay(100);

    console.log('[Test 2] Dispatching Task B (Fast: 150ms) -> Should abort Task A...');
    queue.run(async (signal) => {
      await delay(150);
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
      return 'Result B';
    }).then(res => {
      console.log('Task B resolved with:', res);
      console.assert(res === 'Result B', 'Task B must succeed');
      console.assert(queue.data.value === 'Result B', 'Queue state must be Result B');
      console.log('--- TEST PASSED SUCCESSFULLY ---');
    });

    await delay(600);
  });

  scope.stop();
}

executeTest();
```

---

### 13. Exercise

#### Level: Easy
Implementasikan custom ref Vue bernama `useDebouncedRef(initialValue, delayMs)` menggunakan native `customRef` API. Ref ini harus menunda propagasi reaktivitas trigger hingga interval debounce tercapai tanpa melakukan re-render layout yang tidak perlu.

#### Level: Medium
Buat composable formulir `useAsyncValidation` yang menerima string input ref dan fungsi async `checkAvailability: (val: string) => Promise<boolean>`. Composable ini wajib:
1. Menghindari pemanggilan fungsi jika panjang input < 3 karakter.
2. Membatalkan request validasi yang sedang berjalan bila user mengetik karakter baru.
3. Mengembalikan state: `isValidating: Ref<boolean>`, `isAvailable: Ref<boolean | null>`, dan `validationError: Ref<string | null>`.

#### Level: Hard
Kembangkan subsistem offline mutation queue `useOfflineMutationSync`. 
Kriteria arsitektur:
1. Menyimpan antrean mutasi yang gagal akibat hilangnya koneksi jaringan ke dalam `IndexedDB` atau `localStorage`.
2. Mendeteksi event browser `online` dan melakukan *auto-drain queue* secara sequential (FIFO).
3. Mendukung resolusi konflik: jika record server memiliki `updatedAt` yang lebih baru dari timestamp mutasi antrean, jalankan hook strategi resolusi kustom `onConflict(serverData, localData)`.

---

### 14. Challenge

**Skenario**: Anda memimpin tim rekayasa frontend pada sistem *Collaborative Multi-Tenant Spreadsheet*. Setiap sel dapat diedit oleh banyak pengguna secara bersamaan, memicu mutasi parsial HTTP PATCH dan menerima patch masuk via WebSocket.

**Tugas Arsitektur & Implementasi**:
Rancang dan implementasikan composable engine `useCollaborativeCellEngine`:
1. **Lokal Optimism**: Mengetik pada sel harus segera memperbarui UI tanpa menunggu balasan roundtrip HTTP (P99 < 5ms render).
2. **Deterministic Vector Clocks**: Setiap mutasi dikirim bersama integer urutan revisi (`revisionId`).
3. **Out-of-order Reconciliation**: Jika server membalas error status `409 Conflict`, engine harus menarik data sel terbaru dari server, menerapkan kembali modifikasi lokal pengguna yang belum di-commit di atas data terbaru tersebut (Operational Transformation sederhana), atau menandai sel dengan status *Merge Conflict* merah jika nilai tidak dapat disatukan.
4. **Leak-proof Memory**: Ribuan instansiasi sel tidak boleh menyebabkan pembengkakan memori; seluruh reaktivitas sel harus didaftarkan di bawah *Centralized Registry Scope* yang dapat dihancurkan secara bertahap saat komponen virtual scrolling mengalami *unmount*.

*Instruksi: Tulis arsitektur dan composable murni dalam TypeScript menggunakan Vue 3 Composition API tanpa pustaka state pihak ketiga.*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)

1. Apa fungsi utama dari objek `AbortSignal` yang diteruskan ke API browser seperti `fetch`?
   - A. Mempercepat bandwidth request.
   - B. Mengizinkan pemanggilan fungsi pembatalan request secara deterministik.
   - C. Mengenkripsi payload sebelum dikirim.
   - D. Menghubungkan fetch langsung ke Pinia store.

2. Di dalam composable Vue 3, di mana hook terbaik untuk mendaftarkan pelepasan resource eksternal (seperti pembersihan interval atau pembatalan network request) secara otomatis saat scope composable hancur?
   - A. `onBeforeMount`
   - B. `onScopeDispose`
   - C. `onUpdated`
   - D. `onErrorCaptured`

3. Apa keuntungan menggunakan `shallowRef` dibandingkan `ref` standar saat menyimpan respons payload data fetching berskala ribuan objek?
   - A. Menghindari deep reactivity tracking yang memakan banyak alokasi memori dan CPU overhead.
   - B. Otomatis mengubah data menjadi immutable freeze.
   - C. Membuat data tidak dapat dimodifikasi sama sekali.
   - D. Mempercepat serialisasi JSON menjadi XML.

4. Kapan parameter `onCleanup` pada Vue `watchEffect` dijalankan?
   - A. Hanya saat seluruh aplikasi di-refresh.
   - B. Sesaat sebelum efek dijalankan ulang (*re-run*) atau saat scope efek dihentikan.
   - C. Tepat setelah efek berhasil menyelesaikan Promise.
   - D. Ketika server mengembalikan status kode HTTP 200 OK.

5. Apa status field `dirty` pada sistem manajemen form enterprise?
   - A. Menunjukkan field mengandung format teks tidak aman (XSS).
   - B. Menunjukkan nilai field saat ini berbeda dengan nilai awal (*initial baseline*).
   - C. Menunjukkan field sudah pernah difokuskan dan kehilangan fokus (*blurred*).
   - D. Menunjukkan field sedang dalam proses validasi ke server.

---

#### Bagian 2: Intermediate (5 Soal)

6. Perhatikan kode berikut:
   ```typescript
   const search = ref('');
   const results = ref([]);
   watch(search, async (query) => {
     const data = await fetch(`/api?q=${query}`).then(r => r.json());
     results.value = data;
   });
   ```
   Kerentanan arsitektural apa yang ada pada implementasi ini?
   - A. Menggunakan `search.value` secara ilegal di dalam watch.
   - B. Memory leak karena array results tidak dibersihkan dengan `splice`.
   - C. Race condition di mana request pencarian lambat dapat menimpa hasil dari pencarian terbaru yang selesai lebih cepat.
   - D. Kode tersebut memicu infinite loop pada watch.

7. Bagaimana cara mencegah exception `AbortError` yang tidak diinginkan agar tidak mencemari reporting error log ketika request sengaja dibatalkan via `AbortController`?
   - A. Menghapus blok catch dari try/catch.
   - B. Memeriksa apakah `err instanceof DOMException && err.name === 'AbortError'` di blok catch.
   - C. Memanggil `event.preventDefault()` pada browser window.
   - D. Menggunakan Promise tanpa kata kunci async/await.

8. Mengapa mutasi optimistik (*Optimistic UI*) wajib menyimpan snapshot data sebelum eksekusi API dijalankan?
   - A. Untuk menyediakan riwayat data bagi browser back button.
   - B. Sebagai cadangan rollback deterministik guna mengembalikan state UI ke kondisi semula jika server mengembalikan error.
   - C. Untuk menghindari validasi schema Zod.
   - D. Agar data dapat disalin secara otomatis ke local storage.

9. Apa perbedaan esensial antara penandaan meta status `touched` vs `dirty` pada input form?
   - A. `touched` berubah saat elemen kehilangan fokus (`blur`), sedangkan `dirty` berubah saat nilai dimodifikasi dari nilai awal.
   - B. `touched` hanya ada pada radio button, sedangkan `dirty` hanya ada pada text field.
   - C. Keduanya adalah istilah sinonim tanpa perbedaan fungsional.
   - D. `dirty` berubah saat elemen di-klik, sedangkan `touched` berubah saat form di-submit.

10. Mengapa destructuring properti langsung dari kembalian `reactive()` merusak reaktivitas, dan bagaimana solusinya?
    - A. Karena JavaScript passing by value pada properti primitif; gunakan `toRefs()` atau bungkus dalam `computed`.
    - B. Karena Vue melarang deklarasi variabel bertipe const; ubah variabel menjadi var.
    - C. Karena TypeScript akan mengubah tipe data menjadi unknown; gunakan keyword `as any`.
    - D. Karena reactive proxy akan otomatis terhapus oleh garbage collector jika di-destructure.

---

#### Bagian 3: Skenario Kasus Produksi (3 Soal)

11. **Skenario Permintaan Autocomplete Berkecepatan Tinggi**:
    Aplikasi e-commerce Anda memiliki kolom pencarian global. Ketika pengguna mengetik "Laptop Asus ROG", setiap penekanan tombol memicu request ke endpoint `/api/suggestions`. Server memiliki latensi tidak stabil (P50: 100ms, P99: 1200ms). Kadang saran untuk "Laptop" muncul di layar setelah pengguna selesai mengetik "Laptop Asus ROG", merusak UI suggestions.
    **Solusi arsitektural terbaik adalah:**
    - A. Memasang overlay loading fullscreen setiap kali pengguna menekan satu tombol keyboard.
    - B. Menggabungkan debounce (misal: 300ms) dengan pembatalan request sebelumnya menggunakan `AbortController` via `watch` `onCleanup`.
    - C. Menyimpan semua suggestion di memory frontend (100.000 kata) saat pertama kali aplikasi dimuat.
    - D. Mengubah HTTP request menjadi method synchronous XMLHttpRequest (XHR) blocking.

12. **Skenario Validasi Multi-step Form dengan Validasi Asinkron Silang (Cross-field Validation)**:
    Sebuah formulir pendaftaran rekening bisnis memiliki Field A (Nomor Pokok Wajib Pajak) dan Field B (Kategori Badan Hukum). Validasi ke server untuk memeriksa format NPWP tergantung pada Kategori yang dipilih. Saat pengguna mengubah Kategori Badan Hukum setelah mengisi NPWP, sistem harus:
    - A. Mengabaikan perubahan hingga tombol submit ditekan.
    - B. Mengosongkan seluruh formulir dan memaksa user mengisi dari langkah pertama.
    - C. Menandai field NPWP kembali menjadi `validating`, memicu re-validasi async dengan dependensi baru via schema context, dan membatalkan request validasi NPWP sebelumnya jika masih aktif.
    - D. Mengunci dropdown Kategori Badan Hukum agar tidak bisa diedit setelah diisi.

13. **Skenario Putus Jaringan Saat Mutasi Optimistik Beruntun**:
    Operator gudang menandai 5 barang sebagai "Dispatched" secara berurutan dalam rentang waktu 2 detik via interface web mobile. Pada barang ke-3, koneksi 4G mengalami packet drop total (*offline*).
    **Bagaimana arsitektur antarmuka Vue harus menangani state ini?**
    - A. Langsung me-refresh paksa seluruh halaman web.
    - B. Menahan 2 mutasi tersisa, menandai mutasi ke-3 dengan status "Gagal Sinkronisasi", mengembalikan item ke status "Pending" (Rollback dari snapshot), serta menawarkan opsi "Coba Lagi" tanpa menghilangkan progres barang 1 & 2 yang sudah terkonfirmasi.
    - C. Terus mencoba melakukan request loop tak terbatas tanpa memberi indikasi visual apa pun ke operator.
    - D. Menampilkan modal window alert JavaScript native blocking (`window.alert`) untuk setiap error.

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **B** — `AbortSignal` menyediakan token pembatalan standar browser untuk membatalkan operasi asynchronous seperti fetch.
2. **B** — `onScopeDispose` adalah hook reaktivitas Vue yang dieksekusi saat effect scope composable dilepas/dihancurkan.
3. **A** — `shallowRef` hanya melacak perubahan pada `.value` (akses root), menghindari traversal deep-proxying pada struktur data besar yang membebani memori dan prosesor.
4. **B** — `onCleanup` dieksekusi tepat sebelum efek dijalankan ulang akibat perubahan dependensi atau saat effect scope dimatikan.
5. **B** — Status `dirty` mengindikasikan bahwa nilai formulir telah berubah jika dibandingkan dengan baseline initial value-nya.

#### Bagian 2: Intermediate
6. **C** — Pola tersebut rentan terhadap out-of-order execution / race condition karena request sebelumnya tidak dibatalkan dan waktu resolusi jaringan tidak dapat diprediksi.
7. **B** — Error pembatalan eksplisit teridentifikasi melalui `DOMException` dengan atribut name `'AbortError'` dan harus di-filter secara elegan.
8. **B** — Snapshot berfungsi sebagai safety net deterministik untuk memulihkan state UI kembali ke kondisi valid terakhir jika server menolak mutasi.
9. **A** — `touched` merefleksikan interaksi fokus/blur oleh pengguna, sedangkan `dirty` merefleksikan modifikasi nilai data terhadap baseline.
10. **A** — Destructuring object reactive JavaScript akan memutus getter/setter proxy dari engine reaktivitas; pembungkusan via `toRefs` mempertahankan tracking referensial.

#### Bagian 3: Skenario Kasus Produksi
11. **B** — Kombinasi debounce membatasi intensitas throughput request, dan pembatalan `AbortController` menjamin hanya request untuk query paling mutakhir yang dapat mengupdate state UI.
12. **C** — Re-evaluasi reaktif terhadap field yang dependen dengan pembatalan request usang memastikan integritas data formulir tanpa merusak User Experience.
13. **B** — Pola granular optimistic failure management mengisolasi kesalahan pada item yang gagal, melakukan rollback deterministik pada item tersebut, dan menjaga kontinuitas operasional data lainnya.

---

### 16. Summary

1. **Reactivity & Concurrency Harmony**: Async flow di dalam Vue 3 harus selalu mengindahkan sinkronisasi siklus hidup reaktivitas. Penulisan ke state reaktif pasca microtask harus divalidasi terhadap keaktifan *EffectScope* pemiliknya.
2. **Deterministic Cancellation**: Gunakan `AbortController` yang terikat pada `onCleanup` atau `onScopeDispose` untuk memastikan request usang tidak memicu race condition pada antarmuka.
3. **Structured Form Engine**: Formulir skala besar memerlukan arsitektur berlapis: decoupling antara raw values, status meta (`touched`/`dirty`), dan schema compiler validator independen (Zod).
4. **Optimistic Architecture**: Peningkatan responsivitas aplikasi tingkat tinggi dicapai melalui mutasi optimistik, dengan syarat mutlak adanya mekanisme *immutable snapshotting* dan *state reconciliation/rollback* yang deterministik ketika terjadi anomali jaringan.