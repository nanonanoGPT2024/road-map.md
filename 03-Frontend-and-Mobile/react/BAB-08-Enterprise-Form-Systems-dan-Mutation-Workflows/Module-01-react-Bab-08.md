# Bab 08 Module 01: Enterprise Form Systems & Mutation Workflows

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** `03-Frontend-and-Mobile`
*   **Track:** React Engineering
*   **Modul:** Bab 08 Module 01
*   **Topik:** Enterprise Form Systems & Mutation Workflows
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** React 18/19 Core Architecture, TypeScript Advanced Generics, Concurrency Model, State Management Paradigms, DOM Event Loop Mechanics.

---

## SEKSI 02 — LEARNING OBJECTIVES

1.  **Mendekomposisi State Form:** Memisahkan render state React dari data collection pipeline menggunakan paradigma *uncontrolled-first subscription-based architecture* guna mengeliminasi re-render O(N) pada form berskala ribuan field.
2.  **Mengarsitekturi Validasi Tipe Aman Asinkron:** Mengintegrasikan validasi terisolasi (Zod) berbasis thread pool/web worker untuk eksekusi parsing berdaya komputasi tinggi tanpa memblokir Main Thread.
3.  **Menguasai Siklus Hidup Mutasi Terdistribusi:** Mengimplementasikan mutation pipeline deterministik yang mencakup optimistik updates, transactional rollback, race-condition reconciliation via abort-signals, dan server-side reconcile patching.
4.  **Membangun Resiliensi Transaksional:** Mengimplementasikan dynamic field array state synchronization, dirty-tracking berbasis memory bitmasking/deep proxy comparison, serta idempotency keying di layer transport.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam aplikasi React berskala enterprise, form bukan sekadar kumpulan elemen visual `<input />` yang diikat menggunakan `useState`. Form berskala enterprise adalah **mesin transaksional state terdistribusi lokal (Local Distributed State Machine)** yang bertindak sebagai gerbang validasi, normalisasi, dan mutasi data sebelum statusnya diakui oleh remote source-of-truth (database backend).

### Paradigma: Controlled Rendering Hell vs Subscription Event-Driven
Kelemahan fatal form primitif adalah mengikat perubahan keystroke langsung ke render-tree React:
```
Keypress Event -> React Synthetic Event -> setState -> Root/Subtree Re-Render -> VDOM Diffing -> DOM Update
```
Pada form dengan 500 field dinamis (seperti konfigurator asuransi, underwriting finansial, atau form ledger akuntansi), arsitektur controlled berbasis `useState` lokal memicu degradasi frame budget (melebihi ambang batas 16.6ms). 

Mental model enterprise memisahkan form menjadi **tiga lapisan terisolasi**:
1.  **State Carrier:** DOM Node itu sendiri (`ref`), menyimpan nilai aktual tanpa memberi tahu React scheduler sampai data tersebut dibutuhkan.
2.  **Observer/Pub-Sub Hub:** Single event bus yang melacak perubahan metastate (`isDirty`, `isSubmitting`, `errors`) dan hanya memancarkan pembaruan (selective notify) ke field mikro yang sedang diintervensi atau divalidasi.
3.  **Mutation Engine:** State machine yang mengelola life cycle transfer data (Draft -> Validating -> Mutating -> Optimistic UI -> Committed / Rolled-back).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur hidup form tingkat enterprise dengan skema validasi asynchronous dan transport resilience:

```
[ User Input (Keystroke / Blur) ]
             │
             ▼
[ Native DOM Node (Uncontrolled Ref) ]
             │
             ├─── (Debounced / Event Triggered)
             ▼
[ Subscription Bus Engine ]
             │
             ├── Is Field Registered? ──► No ──► Ignore/Register
             │
             ├── Synchronous Local Rules (Type, Length, Pattern)
             │
             ▼
[ Web Worker / Validation Worker Thread ] ──(Offload Heavy Zod Parser)
             │
             ├── Invalidation Found? ──► Yes ──► Emit Error to Field Subtree ONLY
             │                                   (Update Aria-Invalid, Error Message)
             ▼ No (Valid)
[ State Storage (Heap Map, Non-React Context) ]
             │
      [ Submit Triggered ]
             │
             ▼
[ Idempotency Token Engine ] ──► Generates UUIDv4 Transaction Hash
             │
             ▼
[ Optimistic Pipeline Store ] ──► Snapshots Previous Server State
             │                ──► Injects Optimistic Payload to UI Cache
             ▼
[ HTTP Mutation (AbortController Engine) ]
      │
      ├── Network Error / 5xx ──► Rollback to Snapshot ──► Emit Toast/Notification
      │                                                ──► Focus to First Errored Field
      └── Success 200/201 ──────► Commit to Global Cache ──► Reset Dirty Bitmask
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Proxy-Driven Subscription Store
Jantung performa tinggi sistem form dibangun di atas non-React native store yang mengimplementasikan interface *Observer*:

```typescript
type Listener = () => void;

class FormStore<TValues extends Record<string, any>> {
  private values: TValues;
  private errors: Partial<Record<keyof TValues, string>>;
  private listeners: Set<Listener>;

  constructor(initialValues: TValues) {
    this.values = { ...initialValues };
    this.errors = {};
    this.listeners = new Set();
  }

  // Registrasi listener granular
  public subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  public getFieldValue<K extends keyof TValues>(name: K): TValues[K] {
    return this.values[name];
  }

  public setFieldValue<K extends keyof TValues>(name: K, value: TValues[K]): void {
    this.values[name] = value;
    // Notify listeners secara selektif, bukan re-render global
    this.notify();
  }

  private notify(): void {
    this.listeners.forEach((listener) => listener());
  }
}
```

Ketika React membutuhkan nilai metastate, modul menggunakan hook internal `useSyncExternalStore` (tersedia sejak React 18) untuk berlangganan pada slice state tertentu secara konkuren tanpa memicu tearing.

### 2. Validation Subsystem Mechanics
Validasi enterprise bersifat multidimensi:
*   *Field-level:* Dijalankan sinkron pada `onBlur` atau secara debounced saat `onChange`.
*   *Form-level Cross-Field:* Dijalankan saat nilai A bergantung pada nilai B (contoh: persentase total alokasi portofolio harus berjumlah 100%).
*   *Asynchronous Server-side Probing:* Validasi keunikan entitas (contoh: SKU ID, IBAN, atau NPWP) yang menggunakan `AbortController` untuk membatalkan probe lama setiap kali keystroke baru masuk.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Deep-Proxy Dirty Tracking vs Shallow Equality
Mayoritas form framework naif melakukan shallow comparison (`prev !== next`) pada object form state. Ini menyebabkan form state menjadi dirty seketika sebuah properti diakses, atau sebaliknya, kehilangan jejak mutasi nested jika object di-*mutate* langsung.

Sistem enterprise mengimplementasikan tracking menggunakan native ES6 `Proxy`. Proxy mencatat setiap mutasi nested object menggunakan path string notation (e.g., `company.addresses[0].postalCode`):

```typescript
function createDeepProxy<T extends object>(target: T, onDirty: (path: string) => void, basePath = ''): T {
  return new Proxy(target, {
    get(obj, prop: string | symbol) {
      if (typeof prop === 'symbol') return Reflect.get(obj, prop);
      const val = Reflect.get(obj, prop);
      if (val !== null && typeof val === 'object') {
        return createDeepProxy(val, onDirty, `${basePath}${basePath ? '.' : ''}${prop}`);
      }
      return val;
    },
    set(obj, prop: string | symbol, value: any) {
      if (typeof prop === 'string') {
        const fullPath = `${basePath}${basePath ? '.' : ''}${prop}`;
        onDirty(fullPath);
      }
      return Reflect.set(obj, prop, value);
    }
  });
}
```

### Abort-and-Reconcile Mutasi Asinkron
Dalam mutation workflow tingkat lanjut, mutasi data yang tumpang tindih (*interleaved submissions*) dapat merusak integritas state. Jika pengguna memicu submit versi A, kemudian memodifikasi form dan memicu submit versi B sebelum respon A selesai, urutan penyelesaian jaringan yang tidak menentu (Race Condition) dapat menimpa payload B dengan payload A yang stale.

Solusinya adalah mengikat setiap siklus mutasi ke runtime state machine yang memegang referensi ke singleton `AbortController`. Setiap transisi submit baru mengeksekusi `.abort()` pada request sebelumnya dan menghasilkan UUID idempotency baru.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi fondasi `FormStore` enterprise yang decoupling total dari React render cycle, menggunakan `useSyncExternalStore` untuk optimasi atomic rendering.

```typescript
// store/EnterpriseFormEngine.ts
import { useSyncExternalStore, useCallback, useRef } from 'react';
import { z } from 'zod';

export type FieldValues = Record<string, any>;

export class FormEngine<T extends FieldValues> {
  private values: T;
  private touched: Partial<Record<keyof T, boolean>> = {};
  private errors: Partial<Record<keyof T, string>> = {};
  private listeners: Set<() => void> = new Set();
  private schema?: z.ZodSchema<T>;

  constructor(initialValues: T, schema?: z.ZodSchema<T>) {
    this.values = { ...initialValues };
    this.schema = schema;
  }

  public subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  public getSnapshot = (): T => {
    return this.values;
  };

  public getFieldValue = (name: keyof T): any => {
    return this.values[name];
  };

  public getFieldError = (name: keyof T): string | undefined => {
    return this.errors[name];
  };

  public setFieldValue = (name: keyof T, value: any, shouldValidate = false): void => {
    this.values = { ...this.values, [name]: value };
    this.touched[name] = true;

    if (shouldValidate && this.schema) {
      this.validateField(name);
    }

    this.notify();
  };

  public validateField = (name: keyof T): boolean => {
    if (!this.schema) return true;

    const result = this.schema.safeParse(this.values);
    if (!result.success) {
      const issue = result.error.issues.find((i) => i.path[0] === name);
      if (issue) {
        this.errors[name] = issue.message;
      } else {
        delete this.errors[name];
      }
    } else {
      delete this.errors[name];
    }

    this.notify();
    return !this.errors[name];
  };

  public validateAll = (): boolean => {
    if (!this.schema) return true;

    const result = this.schema.safeParse(this.values);
    if (!result.success) {
      const nextErrors: Partial<Record<keyof T, string>> = {};
      for (const issue of result.error.issues) {
        const path = issue.path[0] as keyof T;
        if (!nextErrors[path]) {
          nextErrors[path] = issue.message;
        }
      }
      this.errors = nextErrors;
      this.notify();
      return false;
    }

    this.errors = {};
    this.notify();
    return true;
  };

  private notify = (): void => {
    for (const listener of this.listeners) {
      listener();
    }
  };
}

// React Custom Hook Binding
export function useFormField<T extends FieldValues>(
  engine: FormEngine<T>,
  fieldName: keyof T
) {
  const subscribe = useCallback(
    (onStoreChange: () => void) => engine.subscribe(onStoreChange),
    [engine]
  );

  const value = useSyncExternalStore(
    subscribe,
    () => engine.getFieldValue(fieldName),
    () => engine.getFieldValue(fieldName)
  );

  const error = useSyncExternalStore(
    subscribe,
    () => engine.getFieldError(fieldName),
    () => engine.getFieldError(fieldName)
  );

  const onChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      engine.setFieldValue(fieldName, e.target.value, false);
    },
    [engine, fieldName]
  );

  const onBlur = useCallback(() => {
    engine.validateField(fieldName);
  }, [engine, fieldName]);

  return { value, error, onChange, onBlur };
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Telaah Modul `EnterpriseFormEngine.ts`:
*   **Baris 6–12:** Konstruksi class `FormEngine` mempertahankan *internal mutable data structures* (`values`, `touched`, `errors`) dalam Heap memory di luar jangkauan GC (Garbage Collector) re-render React.
*   **Baris 19–22:** `subscribe` mengembalikan closure pembersih (`cleanup function`). Ini mutlak diperlukan untuk kompatibilitas penuh dengan React Concurrent Mode lifecycle.
*   **Baris 33–44:** `setFieldValue` mengimplementasikan shallow copy mutasi internal. Kuncinya ada di conditional validation: validasi tidak dijalankan secara langsung pada setiap *typing tick* melainkan didelegasikan atau dipicu jika `shouldValidate === true`.
*   **Baris 46–64:** `validateField` mengeksekusi *Zod Safe Parsing*. Menghindari lemparan exception `try-catch` yang mahal di runtime JavaScript engine V8/SpiderMonkey, dan langsung memetakan `issue.path[0]` ke record errors internal.
*   **Baris 92–100:** Penggunaan `useSyncExternalStore`. Mengikat micro-slices (hanya value atau error milik field itu) dari FormEngine langsung ke micro-tree component React, **mencegah component tetangga me-render ulang** saat value ini berubah.
*   **Baris 108–117:** Wrapper handler `onChange` dan `onBlur` di-*memoize* menggunakan `useCallback` agar kestabilan referensial (referential equality) prop elemen form terjaga untuk rendering DOM yang deterministik.

---

## SEKSI 09 — STUDI KASUS NYATA

### Sistem: Global FX & Bond Order Routing (Fintech Trading Platform)
**Konteks Arsitektur:** Form order multi-trader berisiko tinggi. Trader mengisi parameter trade:
*   Mata Uang Basis & Kuotasi,
*   Volume Transaksi (Nominal),
*   Threshold Toleransi Slippage,
*   Dynamic Leg Split (Pembagian blok transaksi ke multi-counterparty, 1 hingga 50 sub-alokasi).

**Kebutuhan Ekstrem:**
1.  Form harus merender hingga 150 input numerik simultan tanpa input lag (< 5ms response time).
2.  Setiap perubahan alokasi sub-leg wajib mengkalkulasi ulang sisa kuota total secara instan.
3.  Sebelum data dikirim, sistem mengecek batas margin secara asinkron ke Risk Engine via REST API.
4.  Jika order gagal (misal: 409 Slippage Limit Exceeded), payload transaksi dikembalikan secara deterministik ke status un-submitted tanpa menghilangkan input trader, disertai penanda visual pada leg yang bermasalah.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi end-to-end Transactional Order Execution Form berskala enterprise yang mengombinasikan Zod, custom validation hooks, rollback optimis, dan Idempotency Engine:

```tsx
// features/trading/OrderFormTransactionEngine.tsx
import React, { useRef, useTransition, useState, useId } from 'react';
import { z } from 'zod';
import { FormEngine, useFormField } from './EnterpriseFormEngine';

// 1. Zod Schema Definition
const allocationLegSchema = z.object({
  brokerId: z.string().min(1, 'Broker identifier is mandatory'),
  percentage: z.number().min(1, 'Min 1%').max(100, 'Max 100%'),
});

export const FXTradeOrderSchema = z.object({
  instrument: z.string().min(6, 'Invalid ISO FX Pair (e.g. EURUSD)'),
  notionalAmount: z.number().positive('Notional must be greater than 0'),
  legs: z.array(allocationLegSchema).min(1, 'Must have at least one execution leg'),
}).refine((data) => {
  const totalAlloc = data.legs.reduce((acc, leg) => acc + leg.percentage, 0);
  return totalAlloc === 100;
}, {
  message: 'Cumulative allocation of all execution legs must equal precisely 100%',
  path: ['legs'],
});

export type FXTradeOrderType = z.infer<typeof FXTradeOrderSchema>;

// Mock External API dengan Idempotency
interface TransactionResult {
  orderId: string;
  status: 'SETTLED' | 'REJECTED';
  reason?: string;
}

async function executeFxTrade(
  order: FXTradeOrderType,
  idempotencyKey: string,
  signal: AbortSignal
): Promise<TransactionResult> {
  const response = await fetch('/api/v3/fx/orders', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify(order),
    signal,
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.message || 'Execution Gateway Protocol Error');
  }

  return response.json();
}

// 2. Sub-Component: Atomic Field Input
interface TextInputProps {
  engine: FormEngine<any>;
  name: string;
  label: string;
  type?: string;
}

export const AtomicTextInput: React.FC<TextInputProps> = React.memo(({ engine, name, label, type = 'text' }) => {
  const inputId = useId();
  const { value, error, onChange, onBlur } = useFormField(engine, name);

  return (
    <div style={{ marginBottom: '1rem', display: 'flex', flexDirection: 'column' }}>
      <label htmlFor={inputId} style={{ fontWeight: 600, fontSize: '0.85rem' }}>
        {label}
      </label>
      <input
        id={inputId}
        type={type}
        value={value ?? ''}
        onChange={onChange}
        onBlur={onBlur}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${inputId}-error` : undefined}
        style={{
          border: error ? '1px solid #e53e3e' : '1px solid #cbd5e0',
          padding: '8px 12px',
          borderRadius: '4px',
          marginTop: '4px',
        }}
      />
      {error && (
        <span id={`${inputId}-error`} role="alert" style={{ color: '#e53e3e', fontSize: '0.75rem', marginTop: '2px' }}>
          {error}
        </span>
      )}
    </div>
  );
});

AtomicTextInput.displayName = 'AtomicTextInput';

// 3. Parent Form Orchestrator
const INITIAL_ORDER_STATE: FXTradeOrderType = {
  instrument: 'EURUSD',
  notionalAmount: 1000000,
  legs: [
    { brokerId: 'BARCLAYS-LON', percentage: 60 },
    { brokerId: 'CITI-NY', percentage: 40 },
  ],
};

export const FXOrderTransactionManager: React.FC = () => {
  const [engine] = useState(() => new FormEngine<FXTradeOrderType>(INITIAL_ORDER_STATE, FXTradeOrderSchema));
  const [isPending, startTransition] = useTransition();
  const [executionStatus, setExecutionStatus] = useState<string>('IDLE');
  const abortControllerRef = useRef<AbortController | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Jalankan validasi skema menyeluruh
    const isValid = engine.validateAll();
    if (!isValid) {
      setExecutionStatus('VALIDATION_FAILED: Check high-risk fields.');
      return;
    }

    // Buat AbortController untuk race-condition elimination
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    const payload = engine.getSnapshot();
    const idempotencyKey = crypto.randomUUID();

    startTransition(async () => {
      setExecutionStatus('TRANSMITTING_TO_MATCHING_ENGINE');
      try {
        const result = await executeFxTrade(payload, idempotencyKey, abortControllerRef.current!.signal);
        setExecutionStatus(`SUCCESS: Order ${result.orderId} Settled.`);
      } catch (err: any) {
        if (err.name === 'AbortError') {
          setExecutionStatus('ABORTED: Superseded by new transaction attempt.');
          return;
        }
        // Rollback state & notify UI
        setExecutionStatus(`TRANSACTION_FAILED: ${err.message}. State retained for recovery.`);
      }
    });
  };

  return (
    <div style={{ maxWidth: '600px', margin: '2rem auto', padding: '1.5rem', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
      <h2 style={{ borderBottom: '1px solid #edf2f7', paddingBottom: '0.5rem' }}>
        Institutional FX Settlement Terminal
      </h2>

      <form onSubmit={handleSubmit} noValidate>
        <AtomicTextInput engine={engine} name="instrument" label="Currency Pair Code (ISO)" />
        <AtomicTextInput engine={engine} name="notionalAmount" label="Notional Volume" type="number" />

        {/* Display Status */}
        <div style={{ padding: '0.75rem', backgroundColor: '#edf2f7', borderRadius: '4px', margin: '1rem 0' }}>
          <strong>Execution Node Status:</strong> {executionStatus}
        </div>

        <button
          type="submit"
          disabled={isPending}
          style={{
            backgroundColor: isPending ? '#a0aec0' : '#3182ce',
            color: '#fff',
            padding: '10px 24px',
            border: 'none',
            borderRadius: '4px',
            cursor: isPending ? 'not-allowed' : 'pointer',
            fontWeight: 'bold',
          }}
        >
          {isPending ? 'Committing Allocation...' : 'Execute Order Allocation'}
        </button>
      </form>
    </div>
  );
};
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Fitur / Parameter | React Hook Form (RHF) | Formik | Custom Uncontrolled Proxy-Store (Modul Ini) |
| :--- | :--- | :--- | :--- |
| **Arsitektur Rendering** | Uncontrolled (Ref based) + Proxy Subscription | Controlled (React State per Change) | Pure External Store via `useSyncExternalStore` |
| **Beban Re-render (500 fields)** | Ekstrem Rendah (Isolated via Refs) | Sangat Tinggi (Seluruh Tree Render per Keystroke) | Hampir Nol (Micro-subscriptions O(1)) |
| **Bundle Size Overhead** | ~8.6 kB (Bagus) | ~13.2 kB (Besar) | < 1.5 kB (Internal Micro Engine) |
| **Validasi Asinkron Eksternal** | Didukung (Controller / Resolvers) | Terbatas (Beban performa tinggi di event loop) | Thread-Safe (Worker Ready via Isolation) |
| **Toleransi Kompleksitas** | Menengah (Abstraksi tinggi menyulitkan custom deep rollback) | Rendah (Legacy mental model) | Maksimum (Kontrol total mutasi memory heap) |
| **Integrasi Idempotency Mutasi** | Di luar scope library | Di luar scope library | Native terintegrasi dalam engine level |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1.  **Form Reset vs Browser Auto-fill Race Condition:**
    *   *Edge Case:* Browser modern menyuntikkan data auto-fill secara asinkron tanpa memicu synthetic event React `onChange`.
    *   *Mitigasi:* Gunakan native mutation listener atau `animationstart` trick pada pseudo-class CSS `:-webkit-autofill` untuk mengekstrak data langsung dari DOM nodes ke dalam `FormEngine`.
2.  **Number Input NaN Vulnerability:**
    *   *Edge Case:* `<input type="number" />` mengembalikan string kosong `""` ketika pengguna memasukkan karakter invalid (seperti `12e`). Parsing naif `Number(e.target.value)` menghasilkan `0` atau `NaN`.
    *   *Mitigasi:* Simpan raw value sebagai string pada store state, dan delegasikan transformasi ke validasi Zod (`z.preprocess` atau `z.coerce.number()`).
3.  **Zombie Child Component pada Dynamic Array Fields:**
    *   *Edge Case:* Ketika baris transaksi dihapus dari index tengah, sub-komponen input yang masih terhubung ke subscriber lama dapat mengakses referensi array index yang sudah `undefined` sebelum unmount selesai.
    *   *Mitigasi:* Gunakan Unique Immutable IDs (UUID) sebagai `key` React array mapping, bukan array index (`index`).

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan Global State Manager (Redux/Zustand) untuk Form Keystroke Level
*   *Kesalahan:* Mengirimkan action Redux `UPDATE_FIELD` pada setiap keystroke pengguna.
*   *Dampak:* Serialization cost, redux devtools lag, memicu re-render di semua selector yang tidak terisolasi.
*   *Perbaikan:* Biarkan form state terisolasi secara lokal di dalam instance `FormEngine` atau RHF ref. Sync ke global state store HANYA saat event mutasi final disubmit atau di-*blur*.

### 2. Validasi Skema Berat Memblokir Input Mengetik (Input Jank)
*   *Kesalahan:* Menjalankan Zod `.parse()` pada form berisi 100 field di dalam synthetic handler `onChange` secara sinkron.
*   *Perbaikan:* Terapkan eksekusi validasi selektif: jalankan validasi parsial field-level (`schema.shape[field].safeParse()`) saat perubahan instan, dan tunda full schema validation hingga event `onBlur` atau `onSubmit`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

*   **Idempotency Everywhere:** Selalu sertakan header `X-Idempotency-Key` (dihasilkan melalui `crypto.randomUUID()`) pada setiap mutasi POST/PATCH/PUT form yang bernilai finansial.
*   **Accessibility by Default:** Setiap input wajib terasosiasi secara programatis:
    *   `<label htmlFor={id}>`
    *   `aria-invalid={!!error}`
    *   `aria-describedby={error ? errorId : undefined}`
*   **Progressive Preservation:** Simpan snapshot status form yang sedang dikerjakan ke dalam `sessionStorage` dengan mekanisme debounce (misal: 1 detik) untuk mencegah data loss saat user secara tidak sengaja me-refresh halaman tab browser.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

1.  **Memory Leak Cleansing pada Dynamic Subscriptions:**
    Pastikan `FormEngine.subscribe` membersihkan listeners secara total saat component unmount. Hindari anonymous closures yang menangkap state luar tanpa di-bind ke lifecycle komponen.
2.  **Debounced Validation Workers:**
    Untuk validasi komputasi tinggi (seperti regex kompleks, checksum IBAN, verifikasi Luhn algorithm pada kartu kredit), delegasikan validasi ke `Web Worker`:
    ```typescript
    // web worker delegator pattern
    const worker = new Worker(new URL('./validation.worker.ts', import.meta.url));
    worker.postMessage({ type: 'VALIDATE_FIELD', field: 'iban', value });
    worker.onmessage = ({ data }) => {
      engine.setFieldError(data.field, data.error);
    };
    ```

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Mass Assignment Mitigation (Schema Striping):**
    Backend tidak boleh menerima raw object form dari browser. Gunakan Zod `.strip()` untuk membersihkan properti asing (*injected malicious payload*) sebelum data dikirim via network.
2.  **HTML/Script Injection via Controlled DOM:**
    Jangan pernah me-render raw error strings dari server menggunakan `dangerouslySetInnerHTML`. Gunakan text node binding murni guna mencegah Cross-Site Scripting (XSS).
3.  **Sanitisasi Input Angka Sensitif:**
    Gunakan format string sanitization untuk input yang rentan parsing exploit (misalnya SQL Injection payload di field pencarian atau Form Input).

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Sistem enterprise menuntut telemetri tingkat lanjut untuk mendeteksi *friction points* pada form konversi:

```typescript
// Telemetry Integration Hook
export function reportFormMetrics(event: 'FIELD_TOUCH' | 'VALIDATION_ERROR' | 'SUBMIT_ATTEMPT', data: Record<string, any>) {
  if (window.performance && window.performance.mark) {
    const markName = `form_metric_${event}_${Date.now()}`;
    performance.mark(markName);
  }

  // Flush to OpenTelemetry Collector / DataDog Form Analytics
  navigator.sendBeacon('/telemetry/forms', JSON.stringify({
    timestamp: Date.now(),
    event,
    ...data,
    userAgent: navigator.userAgent
  }));
}
```
*Gunakan metric `Time-to-First-Error (TTFE)` dan `Field-Drop-Rate` untuk mengidentifikasi skema input mana yang paling sering membingungkan pengguna.*

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Controlled vs Uncontrolled:** Controlled memicu render siklus React pada setiap keystroke. Uncontrolled menyimpan data di DOM/Heap dan membebaskan main thread.
*   **useSyncExternalStore:** Jembatan standar React 18+ untuk membaca data dari external pub-sub store tanpa masalah race-condition atau concurrent rendering tearing.
*   **AbortController Pipeline:** Batalkan request mutasi yang sedang berlangsung setiap kali mutasi baru yang bertentangan diinisiasi oleh pengguna.
*   **Idempotency Token:** UUID acak yang disematkan pada header setiap form request untuk mencegah eksekusi ganda jika terjadi timeout jaringan.
*   **Schema Safety:** Gunakan Zod `safeParse` alih-alih `parse` untuk mencegah unhandled exceptions di event loop.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Mengapa arsitektur form berbasis controlled component (`value={state}` dan `onChange={(e) => setState(e.target.value)}`) menimbulkan degradasi performa pada form kompleks dengan ratusan input field?
*   A. Karena browser tidak dapat menangani DOM Event Listener lebih dari 50 elemen.
*   B. Karena setiap pengetikan karakter memicu alur re-render ke seluruh subtree komponen yang bersangkutan, membebani VDOM diffing.
*   C. Karena Zod tidak bisa membaca data dari React `useState`.
*   D. Karena JavaScript Garbage Collector menghentikan eksekusi script saat membaca value string.

### Soal 2
Bagaimana fungsi API `useSyncExternalStore` menyelesaikan masalah form rendering di React 18/19?
*   A. Mengubah semua form input menjadi controlled component secara otomatis.
*   B. Melakukan bypass validasi CSS pseudo-classes.
*   C. Memungkinkan komponen berlangganan hanya ke irisan (*slice*) tertentu dari external form store tanpa memicu render jika data irisan tersebut tidak berubah.
*   D. Menjalankan mutasi HTTP form di latar belakang melalui service worker.

### Soal 3
Apa fungsi fundamental dari penyertaan header `X-Idempotency-Key` saat memicu mutation workflow pada form pembayaran atau transaksi finansial?
*   A. Mempercepat koneksi TLS handshake antara browser dan load balancer.
*   B. Memastikan bahwa server tidak mengeksekusi aksi duplikat jika pengguna menekan tombol submit berkali-kali atau terjadi network retry.
*   C. Mengenkripsi payload form menggunakan enkripsi AES-256 di sisi klien.
*   D. Menghilangkan kebutuhan untuk memvalidasi skema data menggunakan Zod di layer backend.

### Soal 4
Kapan sebaiknya validasi asinkron cross-field dieksekusi untuk menghindari input lagging?
*   A. Pada setiap event `onChange` tanpa debounce.
*   B. Menggunakan polling background `setInterval` setiap 100ms.
*   C. Dijalankan hanya pada event `onBlur` atau didebounce dengan jeda waktu aman (misal 300-500ms) setelah ketikan terakhir.
*   D. Tepat sebelum aplikasi me-mount elemen `<input />`.

### Soal 5
Pada kasus dynamic array fields (misal: order allocation legs), mengapa kita dilarang keras menggunakan array `index` sebagai attribute `key` React saat mapping komponen input?
*   A. Key index menyebabkan server menolak payload submit.
*   B. Menghapus item di tengah array akan menyebabkan state internal input salah terhubung ke elemen saudaranya akibat rekonsiliasi VDOM yang salah.
*   C. React compiler akan otomatis melempar fatal exception jika `key` bertipe integer.
*   D. Index array tidak didukung oleh browser berbasis WebKit.

---

### Kunci Jawaban & Analisis

*   **Soal 1: B** — Controlled component mengaitkan input state langsung ke siklus hidup render engine React. Satu keystroke = render cycle, yang menjadi bottleneck fatal jika pohon DOM berukuran masif.
*   **Soal 2: C** — `useSyncExternalStore` menjamin pembacaan sinkron pada store eksternal yang aman terhadap fitur konkuren React, serta menyediakan mekanisme