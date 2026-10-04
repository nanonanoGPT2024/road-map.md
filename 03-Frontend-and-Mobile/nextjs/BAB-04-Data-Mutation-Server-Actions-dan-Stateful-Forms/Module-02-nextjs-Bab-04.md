# Kurikulum Enterprise Next.js: Data Mutation, Server Actions & Stateful Forms
**Kategori:** 03-Frontend-and-Mobile  
**Bab 04:** Data Mutation, Server Actions, dan Stateful Forms  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi  

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   Menganalisis arsitektur internal kompilasi Server Action pada Next.js App Router (AST transformations, Action ID generation, dan RSC Flight Protocol streaming).
*   Mengimplementasikan stateful form berbasis React 19 primitive (`useActionState`, `useOptimistic`, `useFormStatus`) dengan dukungan *Progressive Enhancement* penuh.
*   Merancang arsitektur mutasi data skala enterprise yang tahan banting (*resilient*) menggunakan pola *Safe Action*, validasi skema berlapis (*Zod/Valibot*), dan mekanisme *idempotency*.
*   Mengorkestrasikan invalidasi cache yang presisi (*granular revalidation*) menggunakan `revalidateTag` dan `revalidatePath` tanpa memicu *full-tree re-render*.
*   Menangani mitigasi konkurensi, *race conditions*, *optimistic rollback*, dan eksfiltrasi data akibat *closure capture* pada runtime server.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
*   **Next.js App Router Core:** Pemahaman mendalam tentang *Server Components* (RSC) vs *Client Components*, serta pembatasan serialisasi props.
*   **Protokol HTTP & Form API:** Pemahaman mekanisme *multipart/form-data*, *application/x-www-form-urlencoded*, spesifikasi Fetch API, dan siklus hidup HTTP Request/Response.
*   **TypeScript Lanjutan:** *Generics*, *discriminated unions*, *type narrowing*, dan *type inference*.
*   **State Management React:** Pola rekonsiliasi DOM, *Fiber reconciliation*, dan konsep dasar *concurrency* di React 19.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Kompilasi Server Action & AST Transformations
Ketika Next.js (via Turbopack atau SWC) mendeteksi direktif `'use server'` di tingkat berkas atau fungsi, terjadi transformasi AST (*Abstract Syntax Tree*) secara signifikan:

1.  **Action Manifest Generation:** Fungsi tidak lagi diekspor sebagai kode JavaScript mentah ke klien. Compiler mengekstraksi fungsi tersebut ke dalam build manifest server (`server-reference-manifest.json`).
2.  **Action ID Assignment:** Setiap fungsi mutasi diberi identifier kriptografis unik (hash 40-karakter berbasis file path dan nama fungsi yang di-salt dengan *build secret*), misalnya: `$$ACTION_ID_4f8b2c...`.
3.  **Client-Side Stubbing:** Di sisi bundle klien, fungsi tersebut digantikan oleh *proxy stub* bertipe `createServerReference(actionId, callServer)`. Ketika dieksekusi, stub ini tidak memanggil fungsi secara lokal, melainkan menginisialisasi request HTTP POST balik ke URL saat ini dengan membawa header khusus `Next-Action: <action-id>`.

```
[ Developer Code ]
"use server";
export async function updateProfile(formData) { ... }
                  │
                  ▼ (SWC Compiler via Next.js)
┌──────────────────────────────────────────────┬──────────────────────────────────────────────┐
│ CLIENT BUNDLE (Proxy Stub)                   │ SERVER RUNTIME (Actual Code)                 │
├──────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ export const updateProfile =                 │ export async function $$ACTION_updateProfile │
│   createServerReference("4f8b2c9d...",       │   (formData) {                               │
│     callServer);                             │     // Validasi & mutasi database asli       │
│                                              │   }                                          │
└──────────────────────────────────────────────┴──────────────────────────────────────────────┘
```

### 3.2 Wire Protocol & RSC Flight Streaming saat Mutasi
Server Action bukan sekadar REST endpoint biasa. Eksekusi Server Action menggunakan **RSC Flight Protocol**:

1.  Client mengirimkan request `POST` yang memuat argumen terenkapsulasi (baik `FormData` maupun JSON serialized payload).
2.  Server mengeksekusi aksi dalam konteks Node.js atau Edge Runtime.
3.  Server **tidak** mengembalikan JSON statis standar. Sebaliknya, server mengeksekusi alur mutasi, menjalankan invalidasi cache (`revalidateTag`/`revalidatePath`), dan langsung merender ulang segmen pohon RSC yang terdampak.
4.  Server mengembalikan stream `text/x-component` (Flight Data) yang berisi dua komponen:
    *   Hasil eksekusi fungsi (nilai kembalian / return value).
    *   Diff payload UI baru dari komponen yang di-revalidate.
5.  Client React Router mengonsumsi stream tersebut, memperbarui data lokal, dan melakukan patching DOM tanpa reload halaman, mempertahankan state klien di komponen lain yang tidak terpengaruh.

### 3.3 Anatomi React 19 State Mutation Primitives
Model mutasi modern meninggalkan hook usang seperti `useFormState` dan beralih ke arsitektur React 19:
*   `useActionState(action, initialState, permalink?)`: Mengelola siklus hidup hasil aksi (data, state, pending status) secara atomik.
*   `useFormStatus()`: Hook berbasis React Context internal yang membaca status form induk terdekat (`pending`, `data`, `method`, `action`) tanpa perlu *prop drilling*.
*   `useOptimistic(state, updateFn)`: Memungkinkan mutasi UI instan (*zero-latency*) sebelum aksi server tuntas, dengan mekanisme rollback otomatis jika server melempar error (*exception*).

---

## 4. Why & What

### Mengapa Menggunakan Server Actions Dibandingkan API Route Handlers Tradisional?

| Fitur / Metrik | Route Handlers (`/api/...`) | Server Actions (`'use server'`) |
| :--- | :--- | :--- |
| **Paradigma** | Endpoint-centric (REST/RPC). | Function-centric (RPC terintegrasi bahasa). |
| **Progressive Enhancement** | Sulit; membutuhkan JavaScript manual untuk `e.preventDefault()` & `fetch`. | Otomatis; form HTML `<form action={action}>` berfungsi tanpa JS. |
| **Cache Invalidation** | Manual via client fetch ulang atau SWR/React Query mutations. | Terintegrasi native via `revalidatePath` / `revalidateTag` dalam satu RTT. |
| **Type Safety** | Membutuhkan tRPC atau OpenAPI code generator eksternal. | *End-to-end type safety* native via TypeScript inference langsung. |
| **Bundle Impact** | Mengirim handler logic jika client-rendered, boilerplate fetch. | Zero client runtime size overhead untuk logic server. |

---

## 5. How (Workflow Detail)

Siklus hidup mutasi data skala produksi berjalan melalui 8 tahapan terorkestrasi:

```
[ Client: Submit Event ]
           │
           ▼
[ 1. Optimistic Update ] ──> UI langsung ter-update di Client Virtual DOM
           │
           ▼
[ 2. Progressive Enhancement Check ]
     ├── Tanpa JS ──> Native HTTP POST form action multipart
     └── Dengan JS ─> Intercept via React Transition Engine
           │
           ▼
[ 3. Network Transport ] ──> HTTP POST (Header: `Next-Action: <hash>`, Body: payload)
           │
           ▼
[ 4. Middleware & Auth Shield ] ──> Validasi Session Token, Rate Limiting & Idempotency Key
           │
           ▼
[ 5. Server Action Dispatch ]
     ├── 5.1 Zod Input Schema Validation
     ├── 5.2 Business Logic Execution & Database Transaction
     └── 5.3 Cache Purge Operations (revalidateTag)
           │
           ▼
[ 6. RSC Flight Stream Construction ]
     ├── Return value serialization
     └── Segment rerender payload aggregation
           │
           ▼
[ 7. Response Processing ]
     ├── SUCCESS ──> Apply new RSC payload to Router Cache & Confirm Optimistic State
     └── FAILURE ──> Discard RSC diff & Rollback useOptimistic state to initial
           │
           ▼
[ 8. UI Synchronization & Toast Notification ]
```

---

## 6. Analogy & Diagram ASCII

### Analogi Perbankan: Setor Tunai Bersegel vs Loket Reguler
*   **Route Handler Tradisional:** Anda pergi ke loket umum, mengisi formulir manual, menyerahkannya, menunggu teller menghitung, menerima kuitansi, lalu Anda harus berjalan ke loket terpisah untuk mencetak buku tabungan terbaru Anda secara manual.
*   **Server Actions:** Seperti tabung pneumatik diplomatik (*pneumatic tube*) di perbankan modern. Anda memasukkan uang ke kapsul tersegel (*safe wrapper*), menembakkannya langsung ke brankas pusat. Brankas memvalidasi, menyimpan uang, mencetak saldo baru ke layar Anda, dan memperbarui catatan pembukuan bank dalam satu siklus tertutup seketika.

### Diagram Arsitektur Eksekusi Mutasi

```
+-----------------------------------------------------------------------------------+
| BROWSER RUNTIME                                                                   |
|                                                                                   |
|  <Form action={formAction}>                                                       |
|    |                                                                              |
|    +--> (useOptimistic) ---> Update Local State UI instantly                      |
|    |                                                                              |
|    +--> (React 19 Action Dispatcher)                                              |
|            |                                                                      |
|            | HTTP POST (Stream Payload)                                           |
+------------|----------------------------------------------------------------------+
             | Next-Action: $3f7a19d...
             | Next-Router-State-Tree: ...
             v
+-----------------------------------------------------------------------------------+
| NEXT.JS RUNTIME (Node.js / Edge)                                                  |
|                                                                                   |
|  [Action Interceptor]                                                             |
|    |                                                                              |
|    +--> [Idempotency Guard] ---> Check Key in Redis Cache                         |
|    |                                                                              |
|    +--> [Safe Action Wrapper]                                                     |
|    |      |-- Session & RBAC Verification                                         |
|    |      |-- Zod Runtime Validation (Input Sanitization)                         |
|    |                                                                              |
|    +--> [Domain Service / DB Transaction]                                         |
|    |      |-- UPDATE accounts SET balance = balance - 100 ...                     |
|    |                                                                              |
|    +--> [Cache Invalidation Engine]                                               |
|           |-- revalidateTag('account-ledger')                                     |
|           |-- revalidatePath('/dashboard')                                        |
|                                                                                   |
|  [Flight Serializer]                                                              |
|    |-- Generate UI Chunk Diff for /dashboard RSC                                  |
|    |-- Generate Action Response { success: true, newBalance: 400 }                |
+------------|----------------------------------------------------------------------+
             |
             | text/x-component (Multipart Response Stream)
             v
+-----------------------------------------------------------------------------------+
| BROWSER RECONCILIATION                                                            |
|                                                                                   |
|  - Resolve useActionState Promise                                                 |
|  - Sync useOptimistic state with actual Server State                              |
|  - Seamlessly patch DOM using newly streamed RSC Segment Payload                  |
+-----------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Primitive `useActionState` & `useFormStatus`
Contoh mendasar pemanfaatan form stateful berbasis standar React 19 tanpa client fetch overhead.

```tsx
// app/simple-todo/actions.ts
'use server';

export type ActionState = {
  error?: string;
  success?: boolean;
};

export async function createTodoAction(
  prevState: ActionState,
  formData: FormData
): Promise<ActionState> {
  const title = formData.get('title') as string;

  if (!title || title.trim().length < 3) {
    return { error: 'Judul minimal harus berisi 3 karakter.' };
  }

  // Simulasi persistensi data
  await new Promise((res) => setTimeout(res, 500));
  return { success: true };
}
```

```tsx
// app/simple-todo/form.tsx
'use client';

import { useActionState } from 'react';
import { useFormStatus } from 'react-dom';
import { createTodoAction, ActionState } from './actions';

const initialState: ActionState = {};

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
    >
      {pending ? 'Menyimpan...' : 'Tambah Task'}
    </button>
  );
}

export function SimpleTodoForm() {
  const [state, formAction] = useActionState(createTodoAction, initialState);

  return (
    <form action={formAction} className="space-y-4">
      <div>
        <input
          name="title"
          type="text"
          placeholder="Tuliskan pekerjaan..."
          className="border p-2 rounded"
        />
        {state.error && <p className="text-red-500 text-sm mt-1">{state.error}</p>}
        {state.success && <p className="text-green-500 text-sm mt-1">Berhasil ditambahkan!</p>}
      </div>
      <SubmitButton />
    </form>
  );
}
```

---

### 7.2 Practical Example: Enterprise Safe Action Wrapper + Optimistic UI
Implementasi arsitektur produksi: Safe Action Handler (Auth + Zod Validation), Optimistic updates, dan rollback resilience.

#### Step 1: Type-Safe Action Pipeline Architecture
```typescript
// lib/safe-action.ts
import { z } from 'zod';

export type ActionResponse<TOutput> = {
  data?: TOutput;
  error?: string;
  fieldErrors?: Record<string, string[]>;
};

export function createSafeActionClient<Context>(
  getContext: () => Promise<Context>
) {
  return function <TInputSchema extends z.ZodTypeAny, TOutput>(
    schema: TInputSchema,
    handler: (parsedInput: z.infer<TInputSchema>, ctx: Context) => Promise<TOutput>
  ) {
    return async (rawInput: unknown): Promise<ActionResponse<TOutput>> => {
      try {
        const ctx = await getContext();
        const parsed = schema.safeParse(rawInput);

        if (!parsed.success) {
          return {
            fieldErrors: parsed.error.flatten().fieldErrors,
            error: 'Validasi skema input gagal.',
          };
        }

        const data = await handler(parsed.data, ctx);
        return { data };
      } catch (err) {
        console.error('[SAFE_ACTION_ERROR]:', err);
        return {
          error: err instanceof Error ? err.message : 'Terjadi kegagalan server internal.',
        };
      }
    };
  };
}
```

#### Step 2: Konfigurasi Client & Context (Session & Auth Injection)
```typescript
// server/actions/safe-client.ts
import { createSafeActionClient } from '@/lib/safe-action';
import { cookies } from 'next/headers';

export const authenticatedAction = createSafeActionClient(async () => {
  const cookieStore = await cookies();
  const sessionToken = cookieStore.get('auth-token')?.value;

  if (!sessionToken) {
    throw new Error('Sesi tidak valid atau telah berakhir. Harap login kembali.');
  }

  // Simulasi resolve user dari auth service
  return {
    user: { id: 'usr_99x8a', role: 'FINANCE_ADMIN' },
  };
});
```

#### Step 3: Implementasi Action dengan Invalidation
```typescript
// server/actions/invoice-actions.ts
'use server';

import { z } from 'zod';
import { authenticatedAction } from './safe-client';
import { revalidateTag } from 'next/cache';

const UpdateInvoiceSchema = z.object({
  id: z.string().uuid(),
  amount: z.number().positive('Nominal harus lebih dari 0'),
  note: z.string().min(5, 'Catatan minimal 5 karakter'),
});

export const updateInvoiceAction = authenticatedAction(
  UpdateInvoiceSchema,
  async (input, { user }) => {
    // Audit Logging
    console.log(`[AUDIT] User ${user.id} modifying invoice ${input.id}`);

    // Persistensi ke database
    await new Promise((resolve) => setTimeout(resolve, 800)); // Latency sim

    // Granular Cache Invalidation
    revalidateTag(`invoice-${input.id}`);
    revalidateTag('dashboard-metrics');

    return {
      id: input.id,
      amount: input.amount,
      note: input.note,
      updatedAt: new Date().toISOString(),
    };
  }
);
```

#### Step 4: UI Component Menggunakan `useOptimistic` dan Action
```tsx
// components/invoices/editable-invoice-card.tsx
'use client';

import { useOptimistic, useTransition } from 'react';
import { updateInvoiceAction } from '@/server/actions/invoice-actions';

interface Invoice {
  id: string;
  amount: number;
  note: string;
}

export function EditableInvoiceCard({ initialInvoice }: { initialInvoice: Invoice }) {
  const [isPending, startTransition] = useTransition();
  const [optimisticInvoice, setOptimisticInvoice] = useOptimistic(
    initialInvoice,
    (current, update: Partial<Invoice>) => ({
      ...current,
      ...update,
    })
  );

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const amount = Number(formData.get('amount'));
    const note = String(formData.get('note'));

    // 1. Jalankan optimistik render terlebih dahulu
    startTransition(async () => {
      setOptimisticInvoice({ amount, note });

      // 2. Eksekusi server action
      const result = await updateInvoiceAction({
        id: initialInvoice.id,
        amount,
        note,
      });

      if (result.error) {
        alert(`Gagal menyimpan: ${result.error}`);
        // State otomatis rollback karena startTransition context selesai dengan invariant error
      }
    });
  };

  return (
    <div className="border p-6 rounded-lg shadow-sm bg-white">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-semibold text-lg">Invoice #{optimisticInvoice.id}</h3>
        {isPending && <span className="text-xs bg-amber-100 text-amber-800 px-2 py-1 rounded">Sinkronisasi...</span>}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Nominal (USD)</label>
          <input
            name="amount"
            type="number"
            defaultValue={optimisticInvoice.amount}
            className="w-full border px-3 py-2 rounded focus:ring-2 focus:ring-blue-500 outline-none"
            disabled={isPending}
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Catatan</label>
          <textarea
            name="note"
            defaultValue={optimisticInvoice.note}
            className="w-full border px-3 py-2 rounded focus:ring-2 focus:ring-blue-500 outline-none"
            rows={2}
            disabled={isPending}
          />
        </div>

        <button
          type="submit"
          disabled={isPending}
          className="w-full bg-slate-900 text-white py-2 rounded hover:bg-slate-800 disabled:opacity-50"
        >
          {isPending ? 'Memproses Transaksi...' : 'Perbarui Invoice'}
        </button>
      </form>
    </div>
  );
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: High-Frequency Flash-Sale Allocation Engine
**Skala Kasus:** Sistem inventaris *flash-sale* e-commerce memproses 10,000 checkout bersamaan per detik untuk produk dengan stok terbatas.

### Masalah Arsitektur:
1.  **Over-Allocation (Double-spend):** Multiple request lolos pada waktu bersamaan, menjual kuantitas melebihi stok fisik.
2.  **Server Action Race Condition:** User mengklik tombol mutasi berkali-kali secara simultan (double-submit).
3.  **Database Connection Exhaustion:** Invocations Server Actions membanjiri pool database Postgres secara langsung.

### Solusi Desain Rekayasa:
*   Menerapkan **Distributed Idempotency Layer** berbasis Redis sebelum eksekusi mutasi domain logic.
*   Membuat mekanisme **Conditional Lua Scripting** di Redis untuk decrement inventaris atomik.
*   Server Action mengeksekusi mutasi terisolasi, mengirim event ke transactional outbox, dan hanya memicu granular invalidasi cache pada tag SKU terkait.

```typescript
// server/actions/checkout.ts
'use server';

import { z } from 'zod';
import { Redis } from 'ioredis';
import { revalidateTag } from 'next/cache';
import { headers } from 'next/headers';

const redis = new Redis(process.env.REDIS_URL!);

const CheckoutSchema = z.object({
  skuId: z.string(),
  userId: z.string(),
  idempotencyKey: z.string().uuid(),
});

// LUA Script untuk Atomik Idempotency + Decrement
const allocateInventoryScript = `
  local idempKey = KEYS[1]
  local stockKey = KEYS[2]
  local userId   = ARGV[1]

  -- Cek idempotency
  if redis.call('EXISTS', idempKey) == 1 then
    return {0, 'IDEMPOTENT_HIT'}
  end

  -- Cek ketersediaan stok
  local stock = tonumber(redis.call('GET', stockKey) or '0')
  if stock <= 0 then
    return {-1, 'OUT_OF_STOCK'}
  end

  -- Decrement stok dan set Idempotency lock selama 1 jam
  redis.call('DECR', stockKey)
  redis.call('SETEX', idempKey, 3600, userId)

  return {1, 'SUCCESS'}
`;

export async function processAllocation(prevState: any, formData: FormData) {
  const rawInput = {
    skuId: formData.get('skuId'),
    userId: formData.get('userId'),
    idempotencyKey: formData.get('idempotencyKey'),
  };

  const parsed = CheckoutSchema.safeParse(rawInput);
  if (!parsed.success) {
    return { status: 'ERROR', message: 'Input tidak valid.' };
  }

  const { skuId, userId, idempotencyKey } = parsed.data;

  try {
    const result = (await redis.eval(
      allocateInventoryScript,
      2,
      `idemp:${idempotencyKey}`,
      `inventory:${skuId}`,
      userId
    )) as [number, string];

    const [statusCode, statusMessage] = result;

    if (statusCode === -1) {
      return { status: 'FAILED', message: 'Stok barang telah habis!' };
    }

    if (statusCode === 0) {
      return { status: 'WARNING', message: 'Permintaan duplikat terdeteksi, abaikan.' };
    }

    // Invalidate tag hanya untuk SKU ini
    revalidateTag(`stock-${skuId}`);

    return { status: 'SUCCESS', message: 'Alokasi stok berhasil diamankan.' };
  } catch (error) {
    console.error('[CRITICAL] Flash-sale allocation failure:', error);
    return { status: 'FATAL', message: 'Terjadi kesalahan sistem cluster.' };
  }
}
```

---

## 9. Trade-offs

| Pendekatan | Keuntungan Utama | Kerugian / Trade-off | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Server Actions Direct Mutate** | *DX sangat tinggi*, zero plumbing endpoint terpisah, auto RSC payload streaming. | Terikat erat (*tight coupling*) dengan arsitektur Next.js; payload overhead RSC jika revalidasi tidak dikontrol. | Form web internal, CRUD B2B SaaS, manipulasi dokumen dinamis. |
| **Route Handlers (`/api`)** | Bersifat netral (*platform-agnostic*), dapat diakses oleh mobile apps (iOS/Android), integrasi webhook pihak ketiga. | Membutuhkan penanganan client fetch boilerplate, serialisasi manual, tidak ada auto revalidation. | Public API, Consumer Mobile Endpoints, Webhook Listeners. |
| **External tRPC / GraphQL Engine** | End-to-end type sharing mutlak antar repositori/microservices terpisah, granular query batching. | Kompleksitas tooling tinggi, overhead parsing GraphQL AST, layer tambahan di pipeline CI/CD. | Arsitektur federasi microservices dengan banyak client heterogen. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Closure Scope Leakage (Security Vulnerability)
*   **Kesalahan:** Menggunakan variabel closure sensitif di dalam file client yang mengekspor aksi server inline.
```tsx
// JANGAN LAKUKAN INI:
export default function ClientProfile({ apiSecretToken }: { apiSecretToken: string }) {
  async function actionHandler() {
    'use server';
    // apiSecretToken bisa bocor ke bundle atau dieksploitasi jika context tertangkap secara tidak benar
    await sendPayment(apiSecretToken);
  }
  return <button onClick={() => actionHandler()}>Pay</button>;
}
```
*   **Solusi:** Selalu definisikan Server Actions di file terpisah bertanda `'use server'` di paling atas. Ambil credential dan session langsung dari state server internal (`cookies()`, `headers()`).

### 10.2 Cache Invalidation Overkill (Waterfall Cascade)
*   **Kesalahan:** Memanggil `revalidatePath('/', 'layout')` setelah mutasi form kecil.
*   **Dampak:** Mengakibatkan *Full Route Cache* seluruh aplikasi terhapus, database dibanjiri pembacaan data ulang untuk setiap user session.
*   **Solusi:** Gunakan `revalidateTag(specificTag)` terdistribusi hanya untuk entitas data yang bermutasi.

### 10.3 Form Reset Mismatch dengan `useOptimistic`
*   **Kesalahan:** Mengosongkan form via `form.reset()` sebelum promise action selesai, menyebabkan visual flash jika action server gagal.
*   **Solusi:** Gunakan state kontrol yang diikat pada respons action, atau tangani pengosongan form dalam callback `.then()` setelah promise Action resolve sukses.

---

## 11. Best Practices (Production Checklist)

* [ ] **Defense in Depth Authorization:** Validasi session dan role langsung di dalam eksekusi Server Action terlepas dari middleware edge.
* [ ] **Strict Input Parsing:** Gunakan schema parser (`Zod`, `Valibot`) di baris pertama eksekusi Server Action. Tolak form data mentah tanpa parsing.
* [ ] **Distributed Idempotency:** Pasang Idempotency Key unik (UUID v4) yang di-cache di Redis/KV untuk setiap mutasi finansial/transaksional.
* [ ] **Granular Tagging:** Gunakan arsitektur cache tag `unstable_cache` dengan konvensi penamaan terstruktur (`entity:id`, misal: `orders:9872`).
* [ ] **Optimistic State Boundary:** Pastikan setiap `useOptimistic` dibungkus dalam React `useTransition` untuk menjamin konsistensi concurrent scheduler.
* [ ] **Telemetry Injection:** Bungkus Server Action dalam Span Distributed Tracing (OpenTelemetry/Datadog) untuk mendeteksi database query latency bottlenecks.
* [ ] **File Payload Limits:** Tentukan batas maksimum ukuran `serverActions.bodySizeLimit` di `next.config.js` untuk mencegah Denial of Service via buffer flooding.

---

## 12. Hands-on Practice

Implementasikan project mini terstandarisasi untuk menguji pemahaman arsitektur ini. Simpan struktur berkas Anda di direktori: `hands-on/m02/`.

### Struktur Folder
```text
hands-on/m02/
├── app/
│   ├── actions/
│   │   ├── audit.ts
│   │   └── product-actions.ts
│   ├── components/
│   │   ├── submit-button.tsx
│   │   └── product-form.tsx
│   ├── page.tsx
│   └── layout.tsx
├── lib/
│   └── safe-action-client.ts
└── next.config.ts
```

### File Implementasi

#### File 1: Base Safe Action Client (`hands-on/m02/lib/safe-action-client.ts`)
```typescript
import { z } from 'zod';

export function createActionBuilder<Context>(contextProvider: () => Promise<Context>) {
  return function <TSchema extends z.ZodTypeAny, TResult>(
    schema: TSchema,
    executor: (data: z.infer<TSchema>, ctx: Context) => Promise<TResult>
  ) {
    return async (input: unknown) => {
      try {
        const ctx = await contextProvider();
        const validation = schema.safeParse(input);

        if (!validation.success) {
          return {
            success: false as const,
            error: 'Payload tidak valid',
            validationErrors: validation.error.flatten().fieldErrors,
          };
        }

        const data = await executor(validation.data, ctx);
        return { success: true as const, data };
      } catch (err) {
        return {
          success: false as const,
          error: err instanceof Error ? err.message : 'Kesalahan sistem tak terduga',
        };
      }
    };
  };
}
```

#### File 2: Product Mutation Action (`hands-on/m02/app/actions/product-actions.ts`)
```typescript
'use server';

import { z } from 'zod';
import { createActionBuilder } from '../../lib/safe-action-client';
import { revalidateTag } from 'next/cache';

const protectedAction = createActionBuilder(async () => {
  // Simulasi cek session
  return { tenantId: 'tenant_enterprise_01' };
});

const ProductPayload = z.object({
  id: z.string().min(1),
  name: z.string().min(3, 'Nama minimal 3 karakter'),
  stock: z.coerce.number().int().nonnegative('Stok tidak boleh negatif'),
});

export const updateProduct = protectedAction(ProductPayload, async (data, ctx) => {
  console.log(`[STORAGE] Updating product ${data.id} for tenant ${ctx.tenantId}`);
  
  // Simulasi Latency I/O
  await new Promise((resolve) => setTimeout(resolve, 600));

  // Invalidate specific cache
  revalidateTag(`product-${data.id}`);

  return { ...data, updatedAt: new Date().toISOString() };
});
```

#### File 3: Form Status Aware Button (`hands-on/m02/app/components/submit-button.tsx`)
```tsx
'use client';

import { useFormStatus } from 'react-dom';

export function SubmitButton({ label }: { label: string }) {
  const { pending } = useFormStatus();

  return (
    <button
      type="submit"
      disabled={pending}
      className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-4 rounded transition-all disabled:opacity-50 flex items-center justify-center gap-2"
    >
      {pending && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
      {pending ? 'Menyimpan...' : label}
    </button>
  );
}
```

#### File 4: Interactive Client Form (`hands-on/m02/app/components/product-form.tsx`)
```tsx
'use client';

import { useActionState, useOptimistic } from 'react';
import { updateProduct } from '../actions/product-actions';
import { SubmitButton } from './submit-button';

interface Product {
  id: string;
  name: string;
  stock: number;
}

export function ProductForm({ initialProduct }: { initialProduct: Product }) {
  const [optimisticProduct, setOptimisticProduct] = useOptimistic(
    initialProduct,
    (current, update: Partial<Product>) => ({ ...current, ...update })
  );

  const [state, formAction] = useActionState(
    async (_prevState: unknown, formData: FormData) => {
      const payload = {
        id: initialProduct.id,
        name: formData.get('name') as string,
        stock: Number(formData.get('stock')),
      };

      setOptimisticProduct(payload);
      return await updateProduct(payload);
    },
    null
  );

  return (
    <div className="max-w-md mx-auto p-6 bg-slate-50 border rounded-xl shadow-lg">
      <div className="mb-4">
        <h2 className="text-xl font-bold">Edit Inventaris</h2>
        <p className="text-sm text-slate-500">ID: {optimisticProduct.id}</p>
        <p className="text-sm font-semibold text-indigo-600 mt-1">
          Optimistic Value: {optimisticProduct.name} - ({optimisticProduct.stock} unit)
        </p>
      </div>

      <form action={formAction} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Nama Produk</label>
          <input
            name="name"
            defaultValue={optimisticProduct.name}
            className="w-full border p-2 rounded bg-white"
            required
          />
          {state?.validationErrors?.name && (
            <p className="text-red-500 text-xs mt-1">{state.validationErrors.name[0]}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Jumlah Stok</label>
          <input
            name="stock"
            type="number"
            defaultValue={optimisticProduct.stock}
            className="w-full border p-2 rounded bg-white"
            required
          />
          {state?.validationErrors?.stock && (
            <p className="text-red-500 text-xs mt-1">{state.validationErrors.stock[0]}</p>
          )}
        </div>

        {state?.error && (
          <div className="p-3 bg-red-100 text-red-700 text-sm rounded">{state.error}</div>
        )}

        {state?.success && (
          <div className="p-3 bg-green-100 text-green-700 text-sm rounded">
            Perubahan berhasil disimpan pada database!
          </div>
        )}

        <SubmitButton label="Simpan Perubahan" />
      </form>
    </div>
  );
}
```

---

## 13. Exercise

### Level Easy
Ubah implementasi `SimpleTodoForm` pada bab 7.1 agar menggunakan `useOptimistic` hook. Tampilkan item todo yang baru dimasukkan seketika di bagian bawah form secara langsung dengan status visual *opacity-50* sebelum Server Action merespons.

### Level Medium
Bangun sistem *Multi-Field Dynamic Validation*. Buatlah form pendaftaran yang memvalidasi nama pengguna secara asinkron (mengecek availability di database) menggunakan kombinasi Server Actions dan status debounce di client side, menampilkan pesan *error boundary* jika database timeout.

### Level Hard
Implementasikan Server Action Transactional Pipeline dengan mekanisme rollback total. Jika aksi menyimpan ke 2 tabel berbeda (contoh: `insertOrder` dan `decrementStock`) dan salah satu gagal, lakukan kompensasi mutasi (Saga Pattern ringan) di server, lalu kembalikan RSC stream yang menginstruksikan client me-render komponen Fallback Dialog khusus dengan data error detail.

---

## 14. Challenge

### Studi Kasus: Offline-First Synchronized Queueing Engine
**Objektif:** Rancang form mutasi data pengiriman armada logistik yang tetap dapat menerima input mutasi saat koneksi internet driver terputus di tengah jalan (*offline mode*), dengan spesifikasi berikut:

1.  Ketika koneksi offline, form tidak boleh melempar eksepsi network, melainkan beralih menyimpan state antrean (*queue*) di browser IndexedDB.
2.  Saat jaringan online kembali (`navigator.onLine === true`), jalankan sinkronisasi serial ke Server Action secara otomatis.
3.  Implementasikan mekanisme **Conflict Resolution Matrix** di Server Action: Jika status armada di server telah ditandai `CANCELLED` oleh supervisor kantor pusat selama driver offline, tolak update driver dari antrean offline dan picu auto-rollback UI pada perangkat driver dengan notifikasi spesifik.
4.  Tuliskan solusi Anda tanpa menggunakan third-party state manager library (hanya gunakan Next.js core, React 19 primitives, dan native Web APIs).

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Apa fungsi dari header HTTP `Next-Action` yang dikirim oleh browser ke server Next.js?
2. Bagaimana cara kerja hook `useFormStatus` dalam mendeteksi status form tanpa memerlukan prop dari form induk?
3. Mengapa sebuah file yang ditandai `'use server'` tidak menyertakan implementasi logika aslinya ke dalam JavaScript client bundle?
4. Apa perbedaan mendasar antara `revalidatePath` dan `revalidateTag`?
5. Kapan `useOptimistic` melakukan rollback terhadap perubahan UI sementara?

### 5 Pertanyaan Intermediate
1. Mengapa mendefinisikan Server Action secara inline di dalam Client Component dianggap berisiko terhadap kebocoran informasi (*security risk*)?
2. Mengapa mutasi Server Action mengembalikan stream `text/x-component` alih-alih format JSON murni?
3. Bagaimana mekanisme *Progressive Enhancement* bekerja pada Server Actions jika JavaScript dimatikan di browser pengguna?
4. Mengapa kita harus membungkus pemanggilan mutasi state optimistik di dalam API `startTransition`?
5. Bagaimana cara menangani *double-submit* pada Server Action jika pengguna mengklik tombol submit berkali-kali dalam latensi jaringan tinggi?

### 3 Skenario Kasus Produksi
1. **Skenario:** Aplikasi Anda menggunakan `revalidatePath('/dashboard')` di dalam Server Action. Metrik Datadog menunjukkan lonjakan CPU 90% pada container server database setiap kali ada user yang menekan tombol *Save*. Jelaskan akar masalahnya dan bagaimana memperbaikinya secara arsitektural.
2. **Skenario:** User A dan User B melakukan pengeditan pada dokumen teknis yang sama melalui Server Action secara bersamaan. Terjadi fenomena *Last Write Wins* yang menimpa pekerjaan User A. Rancang arsitektur Server Action untuk mengatasi masalah ini menggunakan *Optimistic Locking* dan *ETags/Version Columns*.
3. **Skenario:** Sistem pembayaran e-commerce Anda gagal mengeksekusi aksi karena gateway pihak ketiga timeout. Namun, UI client tetap menampilkan state optimistik "Pembayaran Berhasil" selama 30 detik sebelum melempar unhandled runtime error. Analisis letak kegagalan alur kontrol tersebut dan tuliskan pseudo-code perbaikan penanganan error boundary-nya.

---

## 16. Summary

*   **Penyatuan Logika Mutasi:** Server Actions menjembatani interaksi mutasi data client-server secara deklaratif melalui RPC terstandarisasi, mengeliminasi kebutuhan boilerplate REST API tradisional untuk mutasi UI internal.
*   **Fondasi React 19:** Pemanfaatan `useActionState`, `useFormStatus`, dan `useOptimistic` memberikan kontrol mutasi tingkat tinggi dengan dukungan bawaan untuk konkurensi, status pending terisolasi, dan *Optimistic UI* tanpa latency visual.
*   **Keamanan & Skalabilitas Enterprise:** Implementasi produksi wajib menggunakan Safe Action Pattern, pemisahan berkas mutasi server, validasi skema yang ketat (`Zod`), mekanisme *Idempotency*, serta invalidasi cache presisi (`revalidateTag`) guna mencegah lonjakan beban database yang tidak terkendali.