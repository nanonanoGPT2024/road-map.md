# Bab 07 Module 01: Asynchronous Flow, Forms, & Data Fetching

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Utama:** Vue.js Ecosystem & Architecture
*   **Kode Modul:** VUE-ASYNC-07-01
*   **Judul:** Asynchronous Flow, Forms, & Data Fetching
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** Pemahaman mendalam tentang Vue 3 Reactivity System (`ref`, `reactive`, `computed`, `watchEffect`), Lifecycle Hooks (`onMounted`, `onUnmounted`, `onScopeDispose`), TypeScript Generics, serta Promise/Async-Await spec ES2022.

---

## SEKSI 02 — LEARNING OBJECTIVES

1.  **Mengarsiteksi Abstraksi Asinkron Bersih:** Membangun *data-fetching composable* kustom yang aman dari kebocoran memori (*memory leaks*), pembatalan otomatis via `AbortController`, dan penanganan status reaktif deterministik (*idle, loading, success, error*).
2.  **Mitigasi Masalah Konkurensi & Race Conditions:** Mendiagnosis dan mengeliminasi bug kondisi balapan (*out-of-order execution*) pada pencarian real-time dan transisi halaman menggunakan teknik *token invalidation* dan *cancellation signals*.
3.  **Mengimplementasikan Validasi Formulir Skala Enterprise:** Mengintegrasikan form engine reaktif dengan validasi berbasis skema (`zod`) yang mendukung *field-level debouncing*, *dependent-field validation*, dan mutasi *dirty/touched/pristine state tracking*.
4.  **Eksekusi Mutasi Optimistik (*Optimistic UI Updates*):** Merancang alur pembaruan antarmuka instan dengan mekanisme *rollback* deterministik ketika terjadi kegagalan jaringan atau validasi server.
5.  **Penguatan Keamanan Transmisi Data Klien:** Mengimplementasikan sanitasi input berlapis, proteksi terhadap injeksi muatan asinkron, dan penanganan CSRF/XSS token pada siklus formulir.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Mengelola data asinkron dalam aplikasi Single Page Application (SPA) reaktif sering kali memicu kesalahan konsepsi: *developer menganggap asinkronisitas hanyalah sebuah Promise yang menunggu respons*. Dalam Vue 3, asinkronisitas adalah **State Machine Temporal**. 

```
[Idle] ---> (Trigger: Invoke Fetch) ---> [Pending / In-Flight]
                                               |
             +---------------------------------+---------------------------------+
             |                                 |                                 |
      (HTTP 200 OK)                     (HTTP 4xx/5xx)                  (Abort / Stale)
             v                                 v                                 v
     [Resolved/Success]                 [Rejected/Error]                 [Ignored/GC'd]
```

### Mental Model Pergeseran Waktu (Temporal Shift)
Komponen Vue terus bernapas selama transmisi data berlangsung. Komponen dapat di-*unmount*, rute dapat berpindah, dan pengguna dapat mengetik karakter baru saat *payload* lama masih berada di kabel jaringan. Karena itu:
1.  **Data di kabel tidak memiliki nilai hierarki mutlak:** Respons yang datang terakhir tidak selalu merupakan data terbaru (*Out-of-Order Resolution*).
2.  **Koneksi jaringan bukan milik siklus hidup komponen:** Respons HTTP yang mendarat pada *unmounted instance* yang mencoba memutasi reaktivitas lokal akan memicu kebocoran memori atau eksepsi tak terduga.
3.  **Formulir bukan sekadar wadah `v-model`:** Formulir adalah agregasi status diskrit yang memproses data kotor (*dirty*), data tersentuh (*touched*), data valid (*validating*), dan dependensi silang yang bergantung pada resolusi I/O eksternal.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur aliran data asinkron end-to-end yang mengintegrasikan UI Form, Composable Data Fetcher, Abort Controller, dan Caching Layer:

```
+----------------------------------------------------------------------------------------------------+
|                                         VUE 3 UI COMPONENT                                         |
|                                                                                                    |
|   +--------------------------+                         +---------------------------------------+   |
|   |   Form State Machine     |                         |           Component Template          |   |
|   |  (values, errors, flags) |                         | (Loading Spinners, Form, Data Tables) |   |
|   +------------+-------------+                         +-------------------+-------------------+   |
+----------------|-----------------------------------------------------------|-----------------------+
                 | (Trigger Submit / Input Change)                           | (Binds Reactively)
                 v                                                           v
+----------------------------------------------------------------------------------------------------+
|                                    COMPOSABLE INTERMEDIARY LAYER                                   |
|                                     (e.g., useFetch / useMutation)                                 |
|                                                                                                    |
|    +-----------------------------+                           +--------------------------------+    |
|    |    Signal Cancellation      |  (Instantiates New)       |        Reactive State          |    |
|    |      (AbortController)      | ========================> |  data: Ref<T | null>           |    |
|    +--------------+--------------+                           |  error: Ref<AppError | null>   |    |
|                   |                                          |  status: Ref<RequestStatus>    |    |
|                   | (.abort() on Stale/Unmount)              +----------------+---------------+    |
+-------------------|-----------------------------------------------------------|--------------------+
                    |                                                           |
                    v                                                           | (Pushes State)
+--------------------------------------------------------------------------+    |
|                        NETWORK TRANSPORT ENGINE                          |    |
|                        (Native Fetch / Axios)                            |    |
|                                                                          |    |
|    [Outgoing HTTP Request with AbortSignal]                              |    |
|         |                                                                |    |
|         v                                                                |    |
|    [Wire: Network / Backend REST/GraphQL API]                            |    |
|         |                                                                |    |
|         +------------------+------------------+                          |    |
|                            |                  |                          |    |
|                     (HTTP Success)      (HTTP Error)                     |    |
|                            |                  |                          |    |
|                            v                  v                          |    |
|                     [Parse Payload]    [Format Error]                    |    |
|                            |                  |                          |    |
|                            +--------+---------+                          |    |
|                                     |                                    |    |
|                                     +====================================+    |
+-------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Reaktivitas Asinkron dan Batching Effect
Vue 3 mengandalkan antrean mikro-tugas (*microtask queue*) melalui fungsi `nextTick()` untuk melakukan batch pembaruan DOM. Ketika data diterima dari operasi asinkron:
* Mutasi terhadap `ref` memicu penandaan *dep* (dependensi) sebagai kotor (*dirty*).
* Komponen tidak langsung merender ulang seketika. Vue menjadwalkan pekerjaan *render effect* di antrean mikro-tugas via fungsi internal `queueJob()`.
* Jika dua pembaruan asinkron mendarat di *tick* JavaScript yang sama, Vue menggabungkan (*coalesces*) pembaruan tersebut untuk mencegah *layout thrashing*.

### 2. Siklus Hidup Composable: Scope Cleanup
Penyedia logika harus menjamin pelepasan sumber daya. Di dalam Vue 3, instance `EffectScope` aktif mencatat semua efek reaktif dan hook siklus hidup.
```typescript
// Konseptualisasi Internal Vue Core
const scope = effectScope();
scope.run(() => {
  // Semua watch, computed, dan hook yang diinisialisasi di sini
  // terdaftar pada scope internal ini
  onScopeDispose(() => {
    // Dipanggil otomatis saat komponen induk di-unmount
    abortController.abort();
  });
});
// Membatalkan semua efek sekaligus saat scope.stop() dipanggil
```

### 3. Anatomisasi Input Reaktif Formulir (`v-model`)
Pengikatan direktif `v-model="formData.email"` di bawah kap mesin merupakan kompilasi dari dua elemen mekanis:
```html
<!-- Input Biasa -->
<input 
  :value="formData.email" 
  @input="formData.email = $event.target.value" 
/>

<!-- Input dengan IME Composition (Cina, Jepang, Korea) -->
<!-- Vue secara internal mendengarkan 'compositionstart' dan 'compositionend' -->
<!-- Nilai tidak dipancarkan hingga komposisi teks selesai sempurna. -->
```

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Penanganan Masalah Konkurensi (Concurrency Hazards)

#### 1. Masalah Balapan Klasik (*The Search Problem*)
Misalkan pengguna mengetik string `"vue"` di kotak pencarian:
1. Mengetik `"v"` $\rightarrow$ Request A ditembakkan (Latensi: 800ms)
2. Mengetik `"vu"` $\rightarrow$ Request B ditembakkan (Latensi: 150ms)
3. Mengetik `"vue"` $\rightarrow$ Request C ditembakkan (Latensi: 300ms)

Timeline mendaratnya data:
* $t = 150\text{ ms}$: Request B kembali. UI menampilkan hasil `"vu"`.
* $t = 300\text{ ms}$: Request C kembali. UI menampilkan hasil `"vue"`.
* $t = 800\text{ ms}$: Request A kembali. UI tertimpa hasil `"v"`. **(BUG: Tampilan tidak sinkron dengan input pengguna).**

#### Mitigasi: AbortController Signal Multiplexing
Solusi deterministik adalah membatalkan *in-flight request* sebelumnya sesaat sebelum request baru dieksekusi:

$$\forall \text{ Request}_{n}, \quad \text{Abort}(\text{Request}_{n-1}) \implies \text{ActiveState} \equiv \text{Request}_{n}$$

Browser tingkat rendah akan langsung menghentikan transmisi paket TCP/HTTP2 stream level, menghemat bandwidth dan memblokir emisi resolusi Promise ke dalam Vue runtime.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi mendasar dari Composable Data Fetching enterprise-grade dengan proteksi pembatalan otomatis (*auto-cancellation*) dan pelacakan status deterministik.

```typescript
// composables/useFetchSecure.ts
import { ref, isRef, unref, watchEffect, onScopeDispose, type Ref } from 'vue';

export type RequestStatus = 'idle' | 'pending' | 'success' | 'error';

export interface UseFetchOptions {
  immediate?: boolean;
  timeout?: number;
}

export interface UseFetchReturn<T> {
  data: Ref<T | null>;
  error: Ref<Error | null>;
  status: Ref<RequestStatus>;
  execute: () => Promise<void>;
  abort: () => void;
}

export function useFetchSecure<T>(
  url: string | Ref<string> | (() => string),
  options: UseFetchOptions = {}
): UseFetchReturn<T> {
  const { immediate = true, timeout = 10000 } = options;

  const data = ref<T | null>(null) as Ref<T | null>;
  const error = ref<Error | null>(null);
  const status = ref<RequestStatus>('idle');

  let currentAbortController: AbortController | null = null;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  const abort = () => {
    if (currentAbortController) {
      currentAbortController.abort('Request dibatalkan oleh pemanggil.');
      currentAbortController = null;
    }
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
  };

  const execute = async (): Promise<void> => {
    abort(); // Batalkan operasi yang sedang berjalan sebelumnya

    currentAbortController = new AbortController();
    const { signal } = currentAbortController;

    status.value = 'pending';
    error.value = null;

    if (timeout > 0) {
      timeoutId = setTimeout(() => {
        abort();
        error.value = new Error(`Batas waktu permintaan (${timeout}ms) terlampaui.`);
        status.value = 'error';
      }, timeout);
    }

    try {
      const resolvedUrl = typeof url === 'function' ? url() : unref(url);
      const response = await fetch(resolvedUrl, { credentials: 'same-origin', credentials: 'include', signal });

      if (!response.ok) {
        throw new Error(`HTTP Error: Terjadi kesalahan dengan status ${response.status} (${response.statusText})`);
      }

      const json = (await response.json()) as T;
      data.value = json;
      status.value = 'success';
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // Request dibatalkan sengaja, abaikan perubahan status menjadi error
        return;
      }
      error.value = err instanceof Error ? err : new Error(String(err));
      status.value = 'error';
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
      currentAbortController = null;
    }
  };

  if (immediate) {
    if (isRef(url) || typeof url === 'function') {
      watchEffect(() => {
        execute();
      });
    } else {
      execute();
    }
  }

  onScopeDispose(() => {
    abort();
  });

  return {
    data,
    error,
    status,
    execute,
    abort
  };
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut bedah teknis implementasi `useFetchSecure`:

*   **Baris 24-27:** `data`, `error`, dan `status` diisolasi sebagai reaktif `Ref`. Status diinisialisasi secara eksplisit menjadi `'idle'`, bukan `'loading'`, mengimplementasikan mesin status yang bersih sebelum aksi dieksekusi.
*   **Baris 29-30:** `currentAbortController` dan `timeoutId` disimpan di luar reaktivitas (*raw references*). Variabel ini tidak perlu bersifat reaktif karena pembaruannya tidak boleh memicu rendering ulang UI, mencegah degradasi siklus CPU.
*   **Baris 40:** Pemanggilan `abort()` tepat di awal `execute()` memastikan adanya mekanisme pembatalan implisit: mengeksekusi fetch baru otomatis menganulir fetch lama yang belum rampung.
*   **Baris 42:** `const { signal } = currentAbortController;` mengekstrak token pembatalan tingkat rendah untuk disuntikkan ke native web API `window.fetch`.
*   **Baris 58:** `unref(url)` mengatasi variasi input URL. Composable dapat menerima `string` statis, `Ref<string>`, atau *getter function* `() => string`.
*   **Baris 66-69:** Pengecekan `err instanceof DOMException && err.name === 'AbortError'`. Jika pembatalan terjadi secara terkontrol, kita *silent ignore* error tersebut agar antarmuka tidak menampilkan pesan galat yang mengganggu pengguna.
*   **Baris 82-88:** Pemanfaatan `watchEffect()`. Jika URL berupa reaktif dan opsi `immediate: true` diset, Composable ini otomatis berlangganan ke perubahan URL tersebut, memicu *refetch* otomatis tanpa rekayasa tambahan.
*   **Baris 92-94:** `onScopeDispose(() => abort())` adalah pertahanan utama against memory leak. Jika komponen pengguna composable ini di-*unmount* dari DOM, sinyal abort langsung ditembakkan, mematikan transmisi seketika.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Sistem Transfer Dana Multimata Uang Enterprise (FinTech)
Sebuah platform perbankan digital memiliki antarmuka transfer dana antarnegara. Kebutuhan arsitektur:
1.  **Validasi Input Real-Time Terdistribusi:** Input nominal transfer harus diverifikasi terhadap batas saldo dan kurs fluktuatif secara real-time via API eksternal (dengan debounce 400ms).
2.  **Mitigasi Double-Submission:** Mencegah pengguna mengklik tombol "Kirim Dana" secara berulang saat koneksi lambat, yang berpotensi menghasilkan *double debit*.
3.  **Audit State Terstruktur:** Lacak status formulir: `pristine` (belum diedit), `dirty` (telah diedit), `validating` (sedang dicek skema/API), dan `submitting`.
4.  **Mutasi Optimistik:** Ketika tombol ditekan, UI instan menampilkan log transaksi sementara dan saldo langsung berkurang di UI lokal, namun jika backend menolak (e.g., *Fraud Detection Triggered*), saldo dikembalikan (*rollback*) dan status transaksi diubah menjadi gagal beserta log alasannya.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi skala enterprise menggunakan TypeScript murni dan Zod untuk validasi skema.

```typescript
// types/transfer.ts
import { z } from 'zod';

export const TransferSchema = z.object({
  recipientIban: z
    .string()
    .min(15, 'IBAN terlalu pendek.')
    .max(34, 'IBAN melebihi batas standar.')
    .regex(/^[A-Z]{2}[0-9]{2}[A-Z0-9]+$/, 'Format IBAN tidak valid.'),
  amount: z
    .number({ invalid_type_error: 'Nominal harus berupa angka.' })
    .positive('Nominal transfer harus lebih besar dari 0.')
    .max(50000, 'Batas transaksi harian adalah 50.000 USD.'),
  notes: z.string().max(140, 'Catatan maksimal 140 karakter.').optional()
});

export type TransferFormValues = z.infer<typeof TransferSchema>;

export interface TransactionResult {
  transactionId: string;
  status: 'COMPLETED' | 'FAILED';
  timestamp: string;
}
```

```vue
<!-- components/TransferForm.vue -->
<template>
  <div class="transfer-card">
    <h2>Transfer Dana Antar Bank</h2>
    <div class="balance-display">
      <span>Saldo Saat Ini: </span>
      <strong>{{ currentBalance.toLocaleString('en-US', { style: 'currency', currency: 'USD' }) }}</strong>
    </div>

    <form @submit.prevent="handleSubmit" novalidate>
      <!-- Recipient IBAN Field -->
      <div class="form-group" :class="{ 'has-error': errors.recipientIban }">
        <label for="iban">IBAN Penerima:</label>
        <input
          id="iban"
          type="text"
          v-model="values.recipientIban"
          @blur="touchField('recipientIban')"
          :disabled="isSubmitting"
          placeholder="GB29NWBK60161331926819"
        />
        <span v-if="touched.recipientIban && errors.recipientIban" class="error-msg">
          {{ errors.recipientIban }}
        </span>
      </div>

      <!-- Amount Field -->
      <div class="form-group" :class="{ 'has-error': errors.amount }">
        <label for="amount">Nominal (USD):</label>
        <input
          id="amount"
          type="number"
          v-model.number="values.amount"
          @blur="touchField('amount')"
          :disabled="isSubmitting"
          step="0.01"
        />
        <span v-if="touched.amount && errors.amount" class="error-msg">
          {{ errors.amount }}
        </span>
      </div>

      <!-- Notes Field -->
      <div class="form-group" :class="{ 'has-error': errors.notes }">
        <label for="notes">Catatan Transaksi:</label>
        <textarea
          id="notes"
          v-model="values.notes"
          @blur="touchField('notes')"
          :disabled="isSubmitting"
        ></textarea>
        <span v-if="touched.notes && errors.notes" class="error-msg">
          {{ errors.notes }}
        </span>
      </div>

      <!-- Submission Feedback -->
      <div v-if="submissionError" class="alert-box error">
        {{ submissionError }}
      </div>
      <div v-if="submissionSuccess" class="alert-box success">
        Transaksi Berhasil! ID: {{ submissionSuccess.transactionId }}
      </div>

      <button
        type="submit"
        class="submit-btn"
        :disabled="isSubmitting || !isValid || !isDirty"
      >
        <span v-if="isSubmitting">Memproses Transaksi...</span>
        <span v-else>Kirim Dana</span>
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, watch } from 'vue';
import { TransferSchema, type TransferFormValues, type TransactionResult } from './types/transfer';

// Saldo Mock Enterprise
const currentBalance = ref<number>(100000.00);

// Status Form
const values = reactive<TransferFormValues>({
  recipientIban: '',
  amount: 0,
  notes: ''
});

const touched = reactive<Record<keyof TransferFormValues, boolean>>({
  recipientIban: false,
  amount: false,
  notes: false
});

const errors = reactive<Partial<Record<keyof TransferFormValues, string>>>({});
const isSubmitting = ref(false);
const submissionError = ref<string | null>(null);
const submissionSuccess = ref<TransactionResult | null>(null);

// Flag Pelacak Modifikasi (Dirty Tracker)
const initialValues = JSON.stringify(values);
const isDirty = computed(() => JSON.stringify(values) !== initialValues);

// Evaluasi Validitas Skema Berbasis Zod
const validate = () => {
  const result = TransferSchema.safeParse(values);
  // Bersihkan error lama
  Object.keys(errors).forEach((key) => {
    delete errors[key as keyof TransferFormValues];
  });

  if (!result.success) {
    result.error.issues.forEach((issue) => {
      const path = issue.path[0] as keyof TransferFormValues;
      if (!errors[path]) {
        errors[path] = issue.message;
      }
    });
    return false;
  }
  return true;
};

// Reaktif Validasi setiap kali data berubah
watch(values, () => {
  validate();
}, { deep: true });

const isValid = computed(() => {
  return TransferSchema.safeParse(values).success;
});

const touchField = (field: keyof TransferFormValues) => {
  touched[field] = true;
};

// Logika Pengiriman dengan Mutasi Optimistik
const handleSubmit = async () => {
  // Tandai seluruh input sebagai tersentuh
  Object.keys(touched).forEach((key) => {
    touched[key as keyof TransferFormValues] = true;
  });

  if (!validate()) return;
  if (values.amount > currentBalance.value) {
    submissionError.value = 'Saldo akun tidak mencukupi untuk nominal transaksi ini.';
    return;
  }

  isSubmitting.value = true;
  submissionError.value = null;
  submissionSuccess.value = null;

  // 1. Catat Snapshot Nilai untuk Rollback
  const previousBalance = currentBalance.value;
  const transferAmount = values.amount;

  // 2. Eksekusi Pembaruan Optimistik (Antarmuka bereaksi seketika)
  currentBalance.value -= transferAmount;

  try {
    // Simulasi Transmisi Jaringan
    const response = await fetch('/api/v1/transfers', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Idempotency-Key': crypto.randomUUID() // Proteksi mutasi ganda
      },
      body: JSON.stringify(values)
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      throw new Error(errorPayload.message || `Gagal mengirim dana. Server merespons dengan HTTP ${response.status}`);
    }

    const result = (await response.json()) as TransactionResult;
    submissionSuccess.value = result;

    // Reset Form jika berhasil
    values.recipientIban = '';
    values.amount = 0;
    values.notes = '';
    Object.keys(touched).forEach((k) => (touched[k as keyof TransferFormValues] = false));
  } catch (err: unknown) {
    // 3. Rollback Mutasi Jika Server Menolak Permintaan
    currentBalance.value = previousBalance;
    submissionError.value = err instanceof Error ? err.message : 'Terjadi kesalahan sistem yang tidak diketahui.';
  } finally {
    isSubmitting.value = false;
  }
};
</script>

<style scoped>
.transfer-card {
  max-width: 500px;
  margin: 2rem auto;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  background: #ffffff;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
.balance-display {
  margin-bottom: 1.5rem;
  padding: 0.75rem;
  background: #f0f4f8;
  border-radius: 4px;
}
.form-group {
  margin-bottom: 1.25rem;
  display: flex;
  flex-direction: column;
}
.form-group label {
  margin-bottom: 0.25rem;
  font-weight: 600;
  font-size: 0.875rem;
}
.form-group input, .form-group textarea {
  padding: 0.5rem;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  font-size: 1rem;
}
.form-group.has-error input, .form-group.has-error textarea {
  border-color: #ef4444;
}
.error-msg {
  color: #ef4444;
  font-size: 0.75rem;
  margin-top: 0.25rem;
}
.alert-box {
  padding: 0.75rem;
  border-radius: 4px;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}
.alert-box.error { background: #fee2e2; color: #b91c1c; }
.alert-box.success { background: #dcfce7; color: #15803d; }
.submit-btn {
  width: 100%;
  padding: 0.75rem;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
}
.submit-btn:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}
</style>
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Pendekatan / Library | Keunggulan (Pros) | Kelemahan (Cons) | Rekomendasi Kasus Penggunaan |
| :--- | :--- | :--- | :--- |
| **Native Composable** (`useFetchSecure` buatan sendiri) | • Nol dependensi eksternal<br>• Kontrol total atas alur memory cleanup<br>• Ukuran bundle minimal (<1KB) | • Harus mengelola cache & revalidasi sendiri<br>• Tidak ada deduplikasi request global bawaan | Proyek internal berukuran kecil-menengah, arsitektur micro-frontend terisolasi ketat. |
| **TanStack Query (Vue Query)** | • Cache otomatis, *stale-while-revalidate*<br>• Window focus refetching<br>• Penanganan mutasi & rollback mutakhir | • Menambah ukuran bundle (~12KB gzipped)<br>• Kurva pembelajaran konsep query keys dan invalidation | Aplikasi Enterprise SaaS kompleks, banyak relasi data server yang dinamis dan berulang. |
| **Vee-Validate + Yup/Zod** | • Arsitektur formulir standar de-facto<br>• Manajemen error dan touched fields otomatis<br>• Integrasi native komponen kustom | • Abstraksi berat jika formulir hanya 1-2 input<br>• Memerlukan binding khusus (`useField`, `Form`) | Aplikasi FinTech, CRM, atau sistem administrasi dengan lusinan form masif dan validasi dinamis. |
| **Manual Reactive Form (`reactive({})`)** | • Performa eksekusi raw tercepat<br>• Fleksibilitas logika validasi absolut<br>• Tanpa overhead library | • Rawan *boilerplate code* yang berulang<br>• Risiko inkonsistensi struktur antar tim pengembang | Formulir sederhana (Login, Register, Simple Search Filter). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The "Dangling Promise" Pasca Komponen Unmount
*   **Masalah:** Permintaan asinkron tetap memproses callback saat komponen telah dihancurkan oleh Vue Router. Jika callback mencoba mengubah `ref` lokal yang masih dipegang referensinya oleh penutupan (*closure*), memori komponen tidak dapat dibersihkan oleh Garbage Collector (*Retained Memory Leak*).
*   **Mitigasi:** Pasang `onScopeDispose` atau `onUnmounted` untuk selalu mengeksekusi `abortController.abort()`. Periksa `signal.aborted` sebelum menjalankan mutasi lanjutan pasca `await`.

### 2. Modifikasi Bersamaan (Mutation Serialization Race)
*   **Masalah:** Pengguna memicu dua event pembaruan patch secara berurutan. Patch kedua selesai diproses di server lebih cepat daripada patch pertama (*network jitter*), sehingga patch pertama menimpa status patch kedua di akhir.
*   **Mitigasi:** Gunakan header `X-Idempotency-Key` atau implementasikan *queue concurrency scheduler* di level composable, membatasi request mutasi pada satu resource secara sekuensial.

### 3. Masalah Desinkronisasi IME Composition pada Formulir Cepat
*   **Masalah:** Masukan teks via bahasa berbasis karakter kompleks (seperti Hiragana, Pinyin) memicu event `compositionstart`. Validasi real-time langsung mengevaluasi potongan suku kata yang belum final, menghasilkan galat validasi palsu.
*   **Mitigasi:** Jangan validasi manual saat `event.isComposing === true`. Direktif `v-model` Vue secara native mengisolasi ini, tetapi *custom listener* `@input` langsung tidak memilikinya.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mengabaikan Asinkronisitas dalam `watch`
```typescript
// SALAH: Race condition tercipta secara eksplisit
watch(searchQuery, async (newQuery) => {
  const res = await fetch(`/api/search?q=${newQuery}`);
  searchResults.value = await res.json(); // Hasil lama dapat menimpa hasil baru!
});

// BENAR: Menggunakan callback pembersihan (onCleanup)
watch(searchQuery, (newQuery, _, onCleanup) => {
  const controller = new AbortController();
  
  onCleanup(() => {
    controller.abort(); // Batalkan request sebelumnya jika query berubah lagi!
  });

  fetch(`/api/search?q=${newQuery}`, { signal: controller.signal })
    .then(res => res.json())
    .then(data => { searchResults.value = data; })
    .catch(err => {
      if (err.name !== 'AbortError') console.error(err);
    });
});
```

### Kesalahan 2: Membocorkan Error HTTP Tanpa Normalisasi
```typescript
// SALAH: Asumsi bahwa fetch() melempar error pada HTTP 404 / 500
const res = await fetch('/api/user');
const data = await res.json(); // Fetch TIDAK melempar error pada kode status 500!

// BENAR: Validasi eksplisit properti ok
const res = await fetch('/api/user');
if (!res.ok) {
  throw new HttpError(res.status, `Network response was not ok: ${res.statusText}`);
}
const data = await res.json();
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Immutabilitas Identitas Idempotensi:** Selalu sertakan `Idempotency-Key` unik berbasis UUIDv4 pada header mutasi sensitif (`POST`, `PATCH`, `DELETE`) guna mencegah eksekusi ganda jika terjadi kegagalan jaringan sementara.
2.  **Gunakan Zod Transformasi Ketat:** Validasi tipe runtime formulir tidak hanya memverifikasi, tetapi harus melakukan *casting/sanitasi* (contoh: memotong *whitespace* ekstra via `z.string().trim()`).
3.  **Standarisasi Format Error State:** Error di antarmuka harus berupa objek terstruktur, minimal memuat: `{ code: string, message: string, fieldErrors?: Record<string, string> }`.
4.  **Terapkan Prinsip "Clean Boundary":** Jangan pernah membiarkan objek `Response` dari `fetch` masuk ke lapisan UI atau template Vue. Serialisasikan payload secepat mungkin ke dalam DTO (*Data Transfer Object*) berbasis TypeScript murni.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Debouncing vs Throttling pada Operasi Asinkron
*   **Debounce (Penundaan):** Wajib untuk pencarian teks formulir. Tunda request hingga pengguna berhenti mengetik selama $N$ ms.
*   **Throttle (Pembatasan Frekuensi):** Tepat untuk pembaruan data yang dipicu pergerakan terus menerus (seperti update status koordinat input range/drag).

```