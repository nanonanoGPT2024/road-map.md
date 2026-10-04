# DATA MUTATION, SERVER ACTIONS, & STATEFUL FORMS

---

## SEKSI 01 — IDENTITAS MODUL

* **Track:** Frontend and Mobile Engineering
* **Kategori:** 03-Frontend-and-Mobile
* **Kurikulum:** Next.js Enterprise Architecture
* **Topik:** Data Mutation, Server Actions, & Stateful Forms
* **Modul:** Bab 04, Modul 01
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat:** Next.js App Router Core (`app/` directory), React Server Components (RSC) vs Client Components mental model, TypeScript 5.x Generics, React 19 Canary / Baseline Hooks (`useActionState`, `useFormStatus`, `useOptimistic`).

---

## SEKSI 02 — LEARNING OBJECTIVES

1. Menguasai arsitektur Server Actions sebagai Remote Procedure Call (RPC) berbasis HTTP `POST` yang terintegrasi langsung ke dalam siklus hidup React Server Components.
2. Mengimplementasikan stateful form handling end-to-end menggunakan kombinasi hook React 19 (`useActionState`, `useFormStatus`, `useOptimistic`) tanpa ketergantungan pada pustaka pihak ketiga.
3. Mendesain validasi mutasi data multi-tier yang type-safe menggunakan Zod dengan pemisahan field-level errors dan actionable form-level state.
4. Menerapkan strategi cache invalidation deterministik via `revalidatePath` dan `revalidateTag` tanpa memicu over-fetching atau waterfall rendering.
5. Membangun proteksi mutasi tingkat enterprise: CSRF mitigation via Host/Origin verification, distributed rate-limiting berbasis Redis, authorization gatekeeper, dan sanitasi input.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: REST Client-Side vs Next.js Server Actions

Sebelum Server Actions, aplikasi React menangani mutasi data melalui alur asinkronus client-side:

```
[Form Input] -> [onSubmit Handler] -> [fetch('/api/v1/resource')] -> [API Route Handler] 
                     ^                                                        |
                     |--- (Manual state: loading, error, success) <-----------|
```

Paradigma ini membebankan manajemen siklus hidup jaringan, parsing JSON, sinkronisasi state error, dan invalidasi cache secara manual pada bundle JavaScript di sisi klien.

Server Actions mengubah mutasi menjadi RPC native berbasis protokol HTTP standar web:

```
[Form (HTML Native / Hydrated)] 
          |
   (action attribute)
          v
[Server Action (RPC Entrypoint)] ---> [Database / Microservices]
          |
   (RSC Flight Stream Payload)
          v
[Automated Revalidation & Seamless DOM Update]
```

### Mental Model Inti

1. **Functions are Network Endpoints:** Direktif `'use server'` tidak mengubah fungsi menjadi modul yang dieksekusi di background thread statis; direktif tersebut menginstruksikan compiler Next.js untuk mengekstrak fungsi tersebut, memberikannya hash ID kriptografis unik, dan mengeksposnya sebagai endpoint HTTP `POST` internal.
2. **Progressive Enhancement sebagai Fondasi:** Form web yang dirancang dengan benar harus dapat mengeksekusi mutasi bahkan sebelum JavaScript selesai dimuat (`hydration`), menggunakan standar HTML `<form action="...">`.
3. **Flight Protocol Synchronicity:** Server Action mengembalikan stream komponen React (React Server Component Payload/Flight data) bersamaan dengan hasil eksekusi mutasi. Artinya, mutasi dan sinkronisasi tampilan terjadi dalam satu round-trip HTTP.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah diagram alur end-to-end yang menunjukkan bagaimana data mengalir dari interaksi UI, melewati network boundary melalui RSC Wire Format, validasi Zod, eksekusi mutasi database, hingga cache invalidation deterministik:

```
+---------------------------------------------------------------------------------------------------+
| CLIENT BROWSER (Hydrated / Non-Hydrated DOM)                                                      |
+---------------------------------------------------------------------------------------------------+
  |
  | 1. User Menekan Submit (Event Dispatch / Native Submit)
  v
+---------------------------------------------------------------------------------------------------+
| React Runtime (useActionState & useOptimistic)                                                   |
| - Optimistic State dirender seketika ke UI (Rollback ready)                                       |
| - Pending State aktif via useFormStatus()                                                         |
+---------------------------------------------------------------------------------------------------+
  |
  | 2. HTTP POST Request
  |    Headers: 
  |      - Next-Action: <ACTION_ID_HASH>
  |      - Content-Type: multipart/form-data OR application/json
  |      - Accept: text/x-component (React Flight Stream)
  v
+===================================================================================================+
| NETWORK BOUNDARY                                                                                  |
+===================================================================================================+
  |
  | 3. Middleware Pipeline (Rate Limiting, Session Token Check)
  v
+---------------------------------------------------------------------------------------------------+
| NEXT.JS SERVER HOST (App Router Core)                                                            |
|                                                                                                   |
|  [Action Router Registry]                                                                         |
|         | Resolve Hash: <ACTION_ID_HASH> -> fn updateProfile(prevState, formData)                 |
|         v                                                                                         |
|  [Security & Context Barrier]                                                                     |
|         |-- Origin vs Host header check (CSRF Guard)                                              |
|         |-- Authentication context assertion (RBAC)                                               |
|         v                                                                                         |
|  [Zod Validation & Sanitization Engine]                                                           |
|         |                                                                                         |
|         +---> (Invalid) --+                                                                       |
|         |                 | Return FormState { status: 'ERROR', fieldErrors, ... }                |
|         v (Valid)         v                                                                       |
|  [Database Transaction (Prisma / Drizzle / ORM)]                                                  |
|         |                                                                                         |
|         +---> (DB Crash) -> Rollback & Return FormState { status: 'DATABASE_ERROR' }              |
|         v (Success)                                                                               |
|  [Next.js Cache Management System]                                                                |
|         |-- revalidateTag('profile-cache')                                                        |
|         |-- revalidatePath('/dashboard/profile')                                                  |
+---------------------------------------------------------------------------------------------------+
  |
  | 4. HTTP 200 OK Response Payload
  |    - React Flight Protocol Stream: [New Server Component Tree]
  |    - Action Return Value: { status: 'SUCCESS', data: {...} }
  v
+===================================================================================================+
| NETWORK BOUNDARY                                                                                  |
+===================================================================================================+
  |
  | 5. Client Re-conciliation
  v
+---------------------------------------------------------------------------------------------------+
| React Fiber Engine & DOM Reconciliation                                                           |
| - useActionState menerima status terbaru                                                          |
| - useOptimistic di-commit atau di-rollback jika mutasi gagal                                      |
| - Layout & Pages re-render otomatis berdasarkan RSC Flight Stream yang diperbarui                |
+---------------------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Direktif `'use server'`

Direktif `'use server'` bukanlah deklarasi lingkup eksekusi universal layaknya runtime engine node.js; ini adalah penanda batas (boundary marker) untuk bundler (Turbopack / Webpack).

* **Pada tingkat file:** Menandai seluruh fungsi yang diekspor dari file tersebut sebagai RPC Server Actions. File ini tidak boleh mengekspor tipe data non-fungsi.
* **Pada tingkat fungsi (inline):** Ditempatkan di baris pertama blok fungsi di dalam React Server Component. Bundler akan mengekstrak closure fungsi tersebut ke dalam build manifest terpisah di sisi server.

### 2. Mekanisme Wire Protocol (Flight Data)

Ketika sebuah Server Action dipanggil dari client, browser tidak menerima JSON konvensional `{ "success": true }`. Browser mengirim request dengan header khusus:

```http
POST /dashboard/invoices HTTP/1.1
Host: app.enterprise.com
Next-Action: 7f8a9c2d5e6b1a3f
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary
Accept: text/x-component
```

Next.js mengeksekusi fungsi terkait, dan jika fungsi tersebut memicu `revalidatePath` atau `revalidateTag`, server akan merender ulang segmen Server Component tree yang terdampak. Respons yang dikembalikan berupa *Flight Data*:

```http
HTTP/1.1 200 OK
Content-Type: text/x-component

0:["$@1",["$","div",null,{"className":"p-4","children":[...]}]]
1:{"status":"SUCCESS","recordId":"inv_99812"}
```

Client-side React runtime mem-parsing payload ini, mengembalikan status RPC ke pemanggil, dan secara simultan melakukan *morphing* subtree DOM tanpa memuat ulang halaman (*full page refresh*).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### React 19 Hook Primitive: `useActionState` vs `useFormState`

React 19 secara formal menggantikan `useFormState` dengan `useActionState`. Hook ini membungkus Server Action untuk menyediakan status transaksional yang persisten.

```typescript
const [state, formAction, isPending] = useActionState(fn, initialState, permalink?);
```

* `fn`: Server action dengan signature `async (prevState: Awaited<State>, formData: FormData) => State`.
* `initialState`: Nilai state sebelum pemanggilan pertama.
* `formAction`: Fungsi wrapper yang di-pass langsung ke atribut `<form action={formAction}>`.
* `isPending`: Boolean flag transisi yang diatur secara otomatis tanpa perlu deklarasi `useTransition` terpisah.

### Manajemen Status Pending: `useFormStatus`

Hook `useFormStatus` membaca status form induk (*contextual injection*) tanpa perlu meneruskan props `isPending` secara manual. Hook ini **harus** dipanggil di dalam komponen anak yang berada di dalam tag `<form>`:

```typescript
// BENAR: Terisolasi dalam child component
function SubmitButton() {
  const { pending, data, method, action } = useFormStatus();
  return <button disabled={pending}>{pending ? 'Menyimpan...' : 'Kirim'}</button>;
}

// SALAH: Dijalankan pada komponen yang sama dengan deklarasi form
function FormComponent() {
  const { pending } = useFormStatus(); // Selalu mengembalikan false
  return <form>...</form>;
}
```

### Optimistic UI: `useOptimistic`

`useOptimistic` memungkinkan antarmuka diperbarui secara instan sebelum server menyelesaikan pemrosesan jaringan. Jika server mengembalikan kegagalan, hook secara otomatis membuang state sementara dan mengembalikan UI ke kondisi sinkron server terakhir.

* Nilai optimistik langsung direfleksikan dalam reconciliation cycle berikutnya.
* Di-rollback secara implisit saat *Flight stream* kembali tanpa optimistic payload tersebut.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi mutasi status pesanan dasar menggunakan Server Actions dan React 19 hooks.

### 1. Definisi Tipe dan Server Action

```typescript
// actions/order-actions.ts
'use server';

export type ActionResponse = {
  success: boolean;
  message: string;
  errors?: Record<string, string[]>;
};

export async function updateOrderStatus(
  prevState: ActionResponse,
  formData: FormData
): Promise<ActionResponse> {
  const orderId = formData.get('orderId') as string;
  const status = formData.get('status') as string;

  // Simulasi validasi field
  if (!orderId || !status) {
    return {
      success: false,
      message: 'ID Pesanan dan Status wajib diisi.',
    };
  }

  try {
    // Simulasi operasi database I/O
    await new Promise((resolve) => setTimeout(resolve, 800));

    if (status === 'REJECTED') {
      return {
        success: false,
        message: 'Status pesanan tidak dapat diubah ke REJECTED secara manual.',
      };
    }

    return {
      success: true,
      message: `Status pesanan ${orderId} berhasil diubah ke ${status}.`,
    };
  } catch (error) {
    return {
      success: false,
      message: 'Terjadi kesalahan sistem internal.',
    };
  }
}
```

### 2. Implementasi Client Component

```tsx
// components/OrderStatusForm.tsx
'use client';

import React, { useActionState } from 'react';
import { useFormStatus } from 'react-dom';
import { updateOrderStatus, ActionResponse } from '@/actions/order-actions';

const initialState: ActionResponse = {
  success: false,
  message: '',
};

function SubmitButton() {
  const { pending } = useFormStatus();

  return (
    <button
      type="submit"
      disabled={pending}
      className="px-4 py-2 bg-blue-600 text-white rounded disabled:bg-slate-400"
    >
      {pending ? 'Memproses Pembaruan...' : 'Perbarui Status'}
    </button>
  );
}

export default function OrderStatusForm() {
  const [state, formAction] = useActionState(updateOrderStatus, initialState);

  return (
    <div className="max-w-md p-6 border rounded-lg bg-white shadow-sm">
      <h3 className="text-lg font-bold mb-4">Ubah Status Pesanan</h3>
      
      <form action={formAction} className="space-y-4">
        <div>
          <label htmlFor="orderId" className="block text-sm font-medium">Order ID</label>
          <input
            type="text"
            id="orderId"
            name="orderId"
            defaultValue="ORD-84920"
            className="w-full border p-2 rounded mt-1"
          />
        </div>

        <div>
          <label htmlFor="status" className="block text-sm font-medium">Status Baru</label>
          <select id="status" name="status" className="w-full border p-2 rounded mt-1">
            <option value="PROCESSING">PROCESSING</option>
            <option value="SHIPPED">SHIPPED</option>
            <option value="REJECTED">REJECTED (Memicu Error)</option>
          </select>
        </div>

        <SubmitButton />
      </form>

      {state.message && (
        <div
          className={`mt-4 p-3 rounded text-sm ${
            state.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
          }`}
        >
          {state.message}
        </div>
      )}
    </div>
  );
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File `actions/order-actions.ts`

* **Baris 2:** `'use server';`
  * *Mekanisme:* Menandai file sebagai server boundary. Compiler Next.js mengekstraksi seluruh ekspor fungsi di dalamnya menjadi endpoint POST terproteksi dan menghapus body fungsi ini dari bundle client JS.
* **Baris 9-12:** `export async function updateOrderStatus(prevState: ActionResponse, formData: FormData): Promise<ActionResponse>`
  * *Mekanisme:* Signature ini dirancang khusus agar kompatibel dengan `useActionState`. Argumen pertama `prevState` adalah snapshot state sebelum pemanggilan; argumen kedua `formData` adalah representasi payload HTML native.
* **Baris 13-14:** `formData.get('orderId') as string;`
  * *Mekanisme:* Mengambil nilai langsung dari payload `multipart/form-data` berdasarkan atribut `name` elemen HTML form.

### Analisis File `components/OrderStatusForm.tsx`

* **Baris 1:** `'use client';`
  * *Mekanisme:* Mengubah file menjadi Client Component boundary agar dapat menggunakan React state engine dan hooks (`useActionState`, `useFormStatus`).
* **Baris 16-27:** `function SubmitButton() { ... const { pending } = useFormStatus(); ... }`
  * *Mekanisme:* Mengambil context `pending` langsung dari tag `<form>` induk. Komponen ini **wajib** dipisahkan dari form utama agar React runtime dapat mengisolasi render ulang status `pending` tanpa me-render ulang seluruh field input formulir.
* **Baris 30:** `const [state, formAction] = useActionState(updateOrderStatus, initialState);`
  * *Mekanisme:* Mengikat Server Action ke life-cycle React. `formAction` adalah wrapper function yang mengarahkan submission ke RPC bridge. `state` adalah nilai reaktif yang diperbarui otomatis saat RPC selesai memproses.
* **Baris 36:** `<form action={formAction} className="space-y-4">`
  * *Mekanisme:* Melakukan binding handler form. Jika JS aktif, interaksi form dicegat via AJAX/Fetch Flight Request. Jika JS dinonaktifkan (Progressive Enhancement), browser mengeksekusi native standard POST request ke endpoint yang sama.

---

## SEKSI 09 — STUDI KASUS NYATA

### Enterprise Scenario: Pembaruan Profil Organisasi Skala Multi-Tenant B2B SaaS

Sebuah platform Enterprise SaaS memfasilitasi organisasi pelanggan untuk mengelola identitas domain, konfigurasi penagihan, dan kuota pengguna. 

**Kebutuhan Sistem:**
1. Mutasi form harus memvalidasi data kompleks (nama domain, kuota multi-tier, identifier pajak) menggunakan Zod.
2. Validasi harus bersifat multi-tier: Field-level error (input spesifik) dan Action-level error (masalah umum seperti kegagalan otentikasi atau error database).
3. State UI harus memanfaatkan `useOptimistic` untuk nama domain, sehingga admin langsung melihat perubahan nama tanpa jeda latensi jaringan.
4. Ketika transaksi database berhasil, server harus meng-invalidate cache cache Next.js pada tag spesifik organisasi (`revalidateTag`) tanpa memicu re-fetch data tenant lain.
5. Mutasi dilindungi oleh verifikasi session dan distributed token-bucket rate limiter berbasis Redis.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Struktur arsitektur produksi:
* `schemas/tenant-schema.ts`: Skema validasi Zod murni.
* `lib/action-client.ts`: Utility pembungkus Action State yang type-safe.
* `actions/tenant-actions.ts`: Server action dengan validasi Zod, tag revalidation, dan penanganan error.
* `components/tenant-profile-form.tsx`: Client component lengkap dengan `useActionState`, `useFormStatus`, dan `useOptimistic`.

### 1. Skema Validasi (`schemas/tenant-schema.ts`)

```typescript
import { z } from 'zod';

export const TenantProfileSchema = z.object({
  tenantId: z.string().uuid({ message: 'Tenant ID tidak valid.' }),
  companyName: z
    .string()
    .min(3, { message: 'Nama perusahaan minimal 3 karakter.' })
    .max(50, { message: 'Nama perusahaan maksimal 50 karakter.' }),
  billingEmail: z
    .string()
    .email({ message: 'Format alamat email penagihan tidak valid.' }),
  seatCapacity: z.coerce
    .number()
    .int()
    .min(5, { message: 'Kapasitas minimal 5 kursi pengguna.' })
    .max(10000, { message: 'Kapasitas maksimum adalah 10.000 kursi.' }),
});

export type TenantProfileInput = z.infer<typeof TenantProfileSchema>;
```

### 2. Form State Abstraction Contract (`lib/action-client.ts`)

```typescript
export type FormFieldErrors<T> = {
  [K in keyof T]?: string[];
};

export type ActionState<TData, TInput = unknown> = {
  status: 'IDLE' | 'SUCCESS' | 'VALIDATION_ERROR' | 'SERVER_ERROR';
  message: string;
  data?: TData | null;
  fieldErrors?: FormFieldErrors<TInput>;
  timestamp: number;
};

export function createInitialActionState<TData, TInput>(): ActionState<TData, TInput> {
  return {
    status: 'IDLE',
    message: '',
    data: null,
    fieldErrors: {},
    timestamp: Date.now(),
  };
}
```

### 3. Production Server Action (`actions/tenant-actions.ts`)

```typescript
'use server';

import { revalidateTag } from 'next/cache';
import { TenantProfileSchema, TenantProfileInput } from '@/schemas/tenant-schema';
import { ActionState } from '@/lib/action-client';

// Mock representasi database tenant
interface TenantRecord {
  id: string;
  companyName: string;
  billingEmail: string;
  seatCapacity: number;
  updatedAt: string;
}

// Simulasi database store
const mockDatabase: Record<string, TenantRecord> = {
  'e2d3d922-83b4-4b57-9d7a-1293a9042b41': {
    id: 'e2d3d922-83b4-4b57-9d7a-1293a9042b41',
    companyName: 'Acme Mega Corp',
    billingEmail: 'billing@acme.com',
    seatCapacity: 50,
    updatedAt: new Date().toISOString(),
  },
};

export async function mutateTenantProfile(
  prevState: ActionState<TenantRecord, TenantProfileInput>,
  formData: FormData
): Promise<ActionState<TenantRecord, TenantProfileInput>> {
  // Simulasi artificial latency untuk network I/O
  await new Promise((resolve) => setTimeout(resolve, 600));

  // 1. Ekstraksi Field dari FormData
  const rawData: Record<string, unknown> = {
    tenantId: formData.get('tenantId'),
    companyName: formData.get('companyName'),
    billingEmail: formData.get('billingEmail'),
    seatCapacity: formData.get('seatCapacity'),
  };

  // 2. Skema Validasi Menggunakan Zod
  const validationResult = TenantProfileSchema.safeParse(rawData);

  if (!validationResult.success) {
    const flattenedErrors = validationResult.error.flatten().fieldErrors;
    return {
      status: 'VALIDATION_ERROR',
      message: 'Validasi form gagal. Silakan periksa kembali input Anda.',
      fieldErrors: flattenedErrors as Record<keyof TenantProfileInput, string[]>,
      data: null,
      timestamp: Date.now(),
    };
  }

  const validatedData = validationResult.data;

  // 3. Security Assertions & Mutasi Data
  try {
    const targetTenant = mockDatabase[validatedData.tenantId];

    if (!targetTenant) {
      return {
        status: 'SERVER_ERROR',
        message: 'Organisasi tidak ditemukan di dalam sistem.',
        fieldErrors: {},
        data: null,
        timestamp: Date.now(),
      };
    }

    // Eksekusi mutasi
    const updatedRecord: TenantRecord = {
      ...targetTenant,
      companyName: validatedData.companyName,
      billingEmail: validatedData.billingEmail,
      seatCapacity: validatedData.seatCapacity,
      updatedAt: new Date().toISOString(),
    };

    mockDatabase[validatedData.tenantId] = updatedRecord;

    // 4. Invalidation Cache Tingkat Segmen
    revalidateTag(`tenant-${validatedData.tenantId}`);

    return {
      status: 'SUCCESS',
      message: 'Profil organisasi berhasil diperbarui.',
      fieldErrors: {},
      data: updatedRecord,
      timestamp: Date.now(),
    };
  } catch (error) {
    // Audit log internal
    console.error('[DATABASE_MUTATION_FAILURE]', {
      error,
      tenantId: validatedData.tenantId,
    });

    return {
      status: 'SERVER_ERROR',
      message: 'Terjadi kegagalan I/O pada klaster database utama.',
      fieldErrors: {},
      data: null,
      timestamp: Date.now(),
    };
  }
}
```

### 4. Stateful Client Component (`components/tenant-profile-form.tsx`)

```tsx
'use client';

import React, { useActionState, useOptimistic, startTransition } from 'react';
import { useFormStatus } from 'react-dom';
import { mutateTenantProfile } from '@/actions/tenant-actions';
import { createInitialActionState, ActionState } from '@/lib/action-client';
import { TenantProfileInput } from '@/schemas/tenant-schema';

interface TenantProfileProps {
  initialTenant: {
    id: string;
    companyName: string;
    billingEmail: string;
    seatCapacity: number;
  };
}

function SubmitButton() {
  const { pending } = useFormStatus();

  return (
    <button
      type="submit"
      disabled={pending}
      className="inline-flex items-center justify-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
    >
      {pending ? (
        <>
          <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          Menyimpan Perubahan...
        </>
      ) : (
        'Simpan Profil Organisasi'
      )}
    </button>
  );
}

export function TenantProfileForm({ initialTenant }: TenantProfileProps) {
  const [state, formAction] = useActionState(
    mutateTenantProfile,
    createInitialActionState()
  );

  // Implementasi Optimistic UI untuk nama perusahaan
  const [optimisticName, setOptimisticName] = useOptimistic(
    state.data?.companyName ?? initialTenant.companyName,
    (current: string, updateValue: string) => updateValue
  );

  // Client-side dispatcher dengan optimistik trigger
  const handleClientAction = (formData: FormData) => {
    const rawCompanyName = formData.get('companyName') as string;
    
    // Terapkan render optimistik langsung sebelum network latency terjadi
    if (rawCompanyName) {
      startTransition(() => {
        setOptimisticName(rawCompanyName);
      });
    }

    formAction(formData);
  };

  return (
    <div className="bg-slate-50 min-h-screen p-8">
      <div className="max-w-2xl mx-auto bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="border-b border-slate-200 px-6 py-4 bg-slate-50/50 flex justify-between items-center">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Pengaturan Organisasi</h2>
            <p className="text-sm text-slate-500">Konfigurasi entitas dan kuota lisensi tenant.</p>
          </div>
          <div className="text-right">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Preview Optimistik</span>
            <div className="text-sm font-bold text-indigo-600 truncate max-w-[180px]">
              {optimisticName}
            </div>
          </div>
        </div>

        <form action={handleClientAction} className="p-6 space-y-6">
          {/* Tenant ID (Hidden Identifier) */}
          <input type="hidden" name="tenantId" value={initialTenant.id} />

          {/* Form-Level Feedback Banner */}
          {state.status === 'SUCCESS' && (
            <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm">
              {state.message}
            </div>
          )}

          {state.status === 'SERVER_ERROR' && (
            <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm">
              {state.message}
            </div>
          )}

          {state.status === 'VALIDATION_ERROR' && (
            <div className="p-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm">
              {state.message}
            </div>
          )}

          {/* Input: Company Name */}
          <div>
            <label htmlFor="companyName" className="block text-sm font-medium text-slate-700">
              Nama Resmi Perusahaan
            </label>
            <input
              type="text"
              id="companyName"
              name="companyName"
              defaultValue={state.data?.companyName ?? initialTenant.companyName}
              className={`mt-1 block w-full rounded-md px-3 py-2 border text-sm shadow-sm transition-colors focus:outline-none focus:ring-2 ${
                state.fieldErrors?.companyName
                  ? 'border-rose-300 focus:border-rose-500 focus:ring-rose-500 text-rose-900'
                  : 'border-slate-300 focus:border-indigo-500 focus:ring-indigo-500 text-slate-900'
              }`}
            />
            {state.fieldErrors?.companyName && (
              <p className="mt-1 text-xs text-rose-600" id="companyName-error">
                {state.fieldErrors.companyName[0]}
              </p>
            )}
          </div>

          {/* Input: Billing Email */}
          <div>
            <label htmlFor="billingEmail" className="block text-sm font-medium text-slate-700">
              Email Penagihan Invoice
            </label>
            <input
              type="email"
              id="billingEmail"
              name="billingEmail"
              defaultValue={state.data?.billingEmail ?? initialTenant.billingEmail}
              className={`mt-1 block w-full rounded-md px-3 py-2 border text-sm shadow-sm transition-colors focus:outline-none focus:ring-2 ${
                state.fieldErrors?.billingEmail
                  ? 'border-rose-300 focus:border-rose-500 focus:ring-rose-500 text-rose-900'
                  : 'border-slate-300 focus:border-indigo-500 focus:ring-indigo-500 text-slate-900'
              }`}
            />
            {state.fieldErrors?.billingEmail && (
              <p className="mt-1 text-xs text-rose-600" id="billingEmail-error">
                {state.fieldErrors.billingEmail[0]}
              </p>
            )}
          </div>

          {/* Input: Seat Capacity */}
          <div>
            <label htmlFor="seatCapacity" className="block text-sm font-medium text-slate-700">
              Kapasitas Lisensi Kursi (Seats)
            </label>
            <input
              type="number"
              id="seatCapacity"
              name="seatCapacity"
              defaultValue={state.data?.seatCapacity ?? initialTenant.seatCapacity}
              className={`mt-1 block w-full rounded-md px-3 py-2 border text-sm shadow-sm transition-colors focus:outline-none focus:ring-2 ${
                state.fieldErrors?.seatCapacity
                  ? 'border-rose-300 focus:border-rose-500 focus:ring-rose-500 text-rose-900'
                  : 'border-slate-300 focus:border-indigo-500 focus:ring-indigo-500 text-slate-900'
              }`}
            />
            {state.fieldErrors?.seatCapacity && (
              <p className="mt-1 text-xs text-rose-600" id="seatCapacity-error">
                {state.fieldErrors.seatCapacity[0]}
              </p>
            )}
          </div>

          {/* Submit Action Subtree */}
          <div className="pt-4 border-t border-slate-100 flex items-center justify-end space-x-3">
            <SubmitButton />
          </div>
        </form>
      </div>
    </div>
  );
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Dimensi Arsitektur | Next.js Server Actions | API Route Handler (`route.ts`) | Third-Party Mutation (tRPC) |
| :--- | :--- | :--- | :--- |
| **Beban Network Bundle** | **Nol / Sangat Rendah** (Tidak ada library fetching tambahan seperti Axios/TanStack Query di client). | **Tergantung Client** (Memerlukan fetch wrapper atau hooks library seperti React Query). | **Sedang** (Memerlukan `@trpc/client` runtime dan wrapper query). |
| **Progressive Enhancement** | **Tinggi** (Secara native mendukung standard form submit tanpa JS saat menggunakan `<form action>`). | **Rendah** (Harus diimplementasikan secara manual via format form POST standard). | **Nol** (Membutuhkan JS engine runtime untuk mengeksekusi serialization). |
| **Cache Invalidation** | **Native & Atomic** (`revalidatePath`, `revalidateTag` menyatu dengan Flight Response). | **Manual** (Klien harus memanggil router refresh atau invalidasi query key secara terpisah). | **Manual** (Client invalidates queries secara eksplisit melalui event handler). |
| **Fleksibilitas Konsumsi** | **Spesifik Aplikasi Web** (Sulit dikonsumsi