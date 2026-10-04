# Bab 10: Server-Driven Paradigms dan React Server Components
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Internal Flight Protocol**: Mengurai format wire-protocol RSC (`chunked text/x-component`), parsing model AST, referensi modul (`$L`), dan resolusi dependensi klien pada runtime browser.
- **Merancang Arsitektur Server Actions Lanjutan**: Mengimplementasikan mutasi data non-trivial dengan proteksi CSRF otomatis, enkripsi ID aksi (`$$id`), transaksionalitas DB, dan integrasi `useActionState` serta `useOptimistic`.
- **Mencegah Kebocoran Data Sensitif Menggunakan React Taint APIs**: Menerapkan `experimental_taintUniqueValue` dan `experimental_taintObjectReference` untuk mengisolasi kredensial, token privat, dan data PII dari boundary serialisasi klien.
- **Mengoptimalkan Multi-Tier Caching & Streaming**: Mengorkestrasi interaksi antara Request Memoization, Data Cache, Full Route Cache, dan Router Cache untuk meminimalkan TTFB (*Time to First Byte*) dan CWV (*Core Web Vitals*).
- **Membangun Custom RSC Bundler & Edge Runtime Pipeline**: Menyusun konfigurasi produksi berbasis sub-path exports, module splitting, dan streaming HTTP/2/3 multi-region.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Arsitektur React 18/19 Core**: Fiber reconciler, Concurrent Rendering, Suspense boundaries, dan Selective Hydration.
- **Protokol HTTP/Streaming**: HTTP/2 Multiplexing, HTTP Chunked Transfer Encoding, Server-Sent Events (SSE), dan MIME types.
- **Sistem Modul JavaScript Tingkat Lanjut**: ECMAScript Modules (ESM), CommonJS interop, Node.js Subpath Exports, dan AST tooling (Rollup/Webpack/Turbopack internals).
- **Fundamental Module 01**: Transisi mental model dari Server-Side Rendering (SSR) konvensional ke arsitektur komponen dwiguna (*Client vs Server components*).

---

### 3. Concept & Internal Architecture

#### 3.1 RSC Wire Format (React Flight Protocol)
React Server Components tidak mengembalikan representasi HTML murni dari server melainkan representasi serialisasi pohon UI yang dikenal sebagai **Flight Wire Format** dengan Content-Type `text/x-component`.

```
M1:{"id":"./src/components/CartBadge.tsx","name":"CartBadge","chunks":["client-chunk.js"],"async":false}
J0:["$","div",null,{"className":"layout","children":[["$","$L1",null,{"initialCount":3}],["$","main",null,{"children":["$","p",null,{"children":"Konten Server"}]}]]}]
```

Keterangan token Flight Protocol:
- **`M` (Module Reference)**: Meregistrasikan client component reference. Berisi ID modul, nama export, dan chunk script yang harus dimuat oleh browser.
- **`J` (JSON Tree)**: Pohon virtual DOM terserialisasi. Simbol `$` merepresentasikan elemen React (`React.createElement`).
- **`$L<ID>` (Lazy Client Component)**: Placeholder referensi modul klien yang didefinisikan pada tag `M`.
- **`S` (Suspense Boundary)**: Penanda batas Suspense (`$Sreact.suspense`), memungkinkan server mengirim fallback UI terlebih dahulu dan men-stream node resolusi promise secara terpisah menggunakan ID segmen.
- **`H` (Hint)**: Mengirimkan instruksi prefetch link/script/font ke klien.

#### 3.2 Server Actions under the Hood
Server Action dikompilasi menjadi endpoint RPC (*Remote Procedure Call*) internal:
1. Bundler memberikan hash ID unik (`$$id`) ke setiap fungsi bertanda `'use server'`.
2. Pada Client Component, pemanggilan fungsi Server Action diubah menjadi HTTP `POST` multipart/form-data atau `application/json` dengan header khusus `Next-Action` atau RSC Action Dispatcher.
3. Server mengeksekusi fungsi target, melakukan mutasi basis data, lalu memicu revalidasi cache path/tag.
4. Server merespons langsung dengan Flight Protocol payload baru berisi segmen UI yang terpengaruh tanpa memerlukan full page reload.

#### 3.3 Taint API & Boundary Security
Masalah kritikal pada RSC adalah serialisasi implisit: objek yang tidak sengaja dioper dari Server Component ke Client Component akan masuk ke payload Flight dalam bentuk plaintext.

React Taint API memblokir hal ini pada engine level:
- **`taintUniqueValue(errorMessage, lifetime, value)`**: Mencegah string/angka unik (misal: API Secret, Private Encryption Key) masuk ke boundary serialisasi klien.
- **`taintObjectReference(errorMessage, object)`**: Mencegah referensi seluruh objek (misal: `UserSession` yang memuat `passwordHash`) lolos ke Client Component.

```
       [ Server Environment ]                   [ Client Environment ]
  +--------------------------------+       +-------------------------------+
  | Data Source (DB / Auth Service)|       | Browser Window                |
  +--------------------------------+       +-------------------------------+
                 |                                         |
          (Fetch Raw Object)                               |
                 v                                         |
  +--------------------------------+                       |
  | Server Component Layer         |                       |
  | - Calls taintObjectReference() |                       |
  | - Strips sensitive fields      |                       |
  +--------------------------------+                       |
                 |                                         |
        (Flight Serialization)                             |
                 |                                         |
         [ Serialization Boundary ]                        |
                 |   X (Throws Error if Tainted)           |
                 v                                         v
  +--------------------------------+  HTTP Stream  +-------------------------------+
  | Flight Protocol Stream Engine  | ------------> | Flight Client Parser          |
  | (text/x-component)             |               | Reconstructs VDOM & Hydrates  |
  +--------------------------------+               +-------------------------------+
```

---

### 4. Why & What

| Fitur / Paradigma | Tradisional SSR (Next.js Pages / Remix v1) | React Server Components (RSC) Architecture |
| :--- | :--- | :--- |
| **Output Server** | Dokumen HTML string monolitik | Stream chunk Flight Protocol (`text/x-component`) |
| **Client Bundle Size** | Semua library dependensi SSR di-bundle ke klien untuk hidrasi | 0 KB bundle untuk dependensi khusus Server Component |
| **State Retention** | Navigasi halaman mereset state DOM pohon klien | Klien mempertahankan state (input focus, audio, video) saat data server di-refresh |
| **Data Fetching Layer**| API Route, `getServerSideProps`, `loader` terpisah | Async/Await native langsung di dalam JSX komponen |
| **Mutation Paradigm** | API endpoint kustom + `fetch` manual + revalidasi manual | Server Actions terintegrasi compiler + otomatis refresh Flight Stream |

---

### 5. How (Workflow Detail)

Alur eksekusi request pada arsitektur Server-Driven Component:

```
[Browser]             [Edge Router]            [Server Component Runtime]        [DB / Microservice]
   |                        |                              |                              |
   |--- 1. HTTP GET ------->|                              |                              |
   |    (Initial Load)      |--- 2. Forward Request ------>|                              |
   |                        |                              |--- 3. Execute Async SQL ---->|
   |                        |                              |<-- 4. Stream DB Result ------|
   |                        |                              |                              |
   |                        |<- 5. Stream Flight & SSR ----| (Render RSC to Flight AST)   |
   |                        |   HTML Chunk 1 (Shell)       |                              |
   |<- 6. Render Shell -----|                              |                              |
   |                        |                              |--- 7. Resolve Suspense ----->|
   |                        |                              |<-- 8. Final DB Chunk --------|
   |                        |<- 9. Stream Flight Chunk 2 --|                              |
   |<- 10. Progressive -----|                              |                              |
   |    Hydration (Slot)    |                              |                              |
```

1. Browser mengirim request awal untuk rute `/analytics`.
2. Node.js/Edge runtime menginisiasi SSR rendering stream (`renderToPipeableStream` atau `renderToReadableStream`).
3. Root Server Component mengeksekusi fetching asinkron non-blocking. Komponen yang belum selesai dibungkus oleh `<Suspense>`.
4. Server menghasilkan HTML Shell awal berbasis fallback Suspense, langsung dikirim ke browser (TTFB ultra-rendah).
5. Bersamaan dengan itu, runtime mengompilasi pohon komponen menjadi payload Flight Protocol.
6. Browser menerima HTML shell, menampilkannya ke pengguna, dan mulai mengunduh chunk JS klien yang direferensikan oleh tag `M`.
7. Ketika promise di server selesai, runtime men-stream chunk Flight pengganti beserta inline script tag untuk menggantikan fallback Suspense secara selektif tanpa merusak state DOM klien yang sudah ada.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pabrik Furnitur Modular vs Flat-pack Retail
- **SPA Tradisional**: Pabrik mengirim truk penuh kayu mentah, gergaji, dan instruksi manual (Mega JavaScript Bundle). Rumah Anda (Browser) harus memotong kayu dan merakit semuanya sendiri hingga selesai sebelum bisa ditinggali.
- **SSR Tradisional**: Pabrik mengirim rumah yang sudah dirakit utuh dari beton (HTML murni). Namun, untuk membuka pintu dan menyalakan saklar, pabrik tetap harus mengirim truk alat konstruksi untuk merekatkan kembali semua sambungan baut secara manual (Hydration Overhead).
- **RSC Paradigm**: Pabrik mengirim struktur dinding permanen yang tidak perlu diubah (Server Component). Untuk bagian yang memerlukan interaksi (saklar lampu, gagang pintu), pabrik menyematkan modul rakitan pintar siap pakai (Client Components). Jika ingin mengubah warna cat, pabrik hanya mengirim lapisan warna via pos tanpa perlu merombak fondasi rumah (Flight Streaming).

```
   POHON KOMPONEN RSC SECARA ARSITEKTURAL:
   
   [RootLayout (Server)]
   |
   +---> [Header (Server)]
   |     |
   |     +---> [Navigation (Client Boundary - 'use client')]
   |
   +---> [AnalyticsContainer (Server)]
         |
         +---> <Suspense fallback={<Skeleton />}>
               |
               +---> [MetricsDataGrid (Server - Async DB Query)]
                     |
                     +---> [InteractiveChart (Client Boundary - 'use client')]
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Menghindari Client Leak dengan Taint API
Contoh proteksi kredensial sensitif di tingkat engine.

```typescript
// server/secrets.ts
import { experimental_taintObjectReference, experimental_taintUniqueValue } from 'react';

export interface DatabaseCredentials {
  connectionString: string;
  maxPoolSize: number;
}

const secureConfig: DatabaseCredentials = {
  connectionString: "postgres://admin:SUPER_SECRET_TOKEN@db.internal:5432/core",
  maxPoolSize: 20
};

// Taint seluruh referensi objek
experimental_taintObjectReference(
  'FATAL ERROR: Dilarang mengirim Database Credentials ke Client Component!',
  secureConfig
);

// Taint nilai string spesifik
experimental_taintUniqueValue(
  'FATAL ERROR: API Secret Token terdeteksi bocor ke Client Payload!',
  globalThis,
  secureConfig.connectionString
);

export function getInternalConfig(): DatabaseCredentials {
  return secureConfig;
}
```

```tsx
// app/dashboard/page.tsx (Server Component)
import { getInternalConfig } from '@/server/secrets';
import { ClientViewer } from '@/components/ClientViewer';

export default function DashboardPage() {
  const config = getInternalConfig();

  return (
    <main>
      <h1>Server Secure Area</h1>
      {/* 
        RUNTIME ERROR DI LEVEL COMPILER/FLIGHT SERIALIZER:
        Error: FATAL ERROR: Dilarang mengirim Database Credentials ke Client Component!
      */}
      {/* @ts-expect-error Pengujian keamanan taint */}
      <ClientViewer payload={config} />
    </main>
  );
}
```

#### 7.2 Practical Enterprise Example: Enterprise Audit Logging & Optimistic Data Grid

Implementasi sistem audit mutasi data berskala enterprise menggunakan RSC, Server Action dengan rollback transaksional, dan Optimistic Update.

```typescript
// types/audit.ts
export interface AuditLogEntry {
  id: string;
  action: string;
  actor: string;
  status: 'PENDING' | 'COMMITTED' | 'FAILED';
  timestamp: string;
}

export interface ActionResult<T> {
  success: boolean;
  data?: T;
  error?: string;
}
```

```typescript
// actions/auditActions.ts
'use server'

import { revalidateTag } from 'next/cache';
import { AuditLogEntry, ActionResult } from '@/types/audit';

export async function recordAuditEvent(
  prevState: ActionResult<AuditLogEntry> | null,
  formData: FormData
): Promise<ActionResult<AuditLogEntry>> {
  const actionName = formData.get('actionName') as string;
  const actor = formData.get('actor') as string;

  if (!actionName || !actor) {
    return {
      success: false,
      error: 'Payload tidak valid: actionName dan actor wajib diisi.'
    };
  }

  try {
    // Simulasi Network Latency I/O
    await new Promise((resolve) => setTimeout(resolve, 800));

    if (actionName.includes('CRASH')) {
      throw new Error('Database transaction abort: Integrity constraint violation.');
    }

    const newEntry: AuditLogEntry = {
      id: crypto.randomUUID(),
      action: actionName,
      actor,
      status: 'COMMITTED',
      timestamp: new Date().toISOString()
    };

    // Dalam implementasi nyata: await db.insert(auditLogs).values(newEntry);
    revalidateTag('audit-logs');

    return {
      success: true,
      data: newEntry
    };
  } catch (err: unknown) {
    return {
      success: false,
      error: err instanceof Error ? err.message : 'Kesalahan internal server.'
    };
  }
}
```

```tsx
// components/AuditLogTable.tsx
'use client'

import React, { useActionState, useOptimistic, useTransition } from 'react';
import { recordAuditEvent } from '@/actions/auditActions';
import { AuditLogEntry, ActionResult } from '@/types/audit';

interface AuditLogTableProps {
  initialLogs: AuditLogEntry[];
}

export function AuditLogTable({ initialLogs }: AuditLogTableProps) {
  const [, startTransition] = useTransition();

  // React 19 Action State Hook
  const [state, formAction, isPending] = useActionState<ActionResult<AuditLogEntry> | null, FormData>(
    recordAuditEvent,
    null
  );

  // Optimistic UI state
  const [optimisticLogs, setOptimisticLogs] = useOptimistic<AuditLogEntry[], AuditLogEntry>(
    initialLogs,
    (currentLogs, newOptimisticEntry) => [newOptimisticEntry, ...currentLogs]
  );

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const formData = new FormData(formElement);

    const actionName = formData.get('actionName') as string;
    const actor = formData.get('actor') as string;

    startTransition(async () => {
      setOptimisticLogs({
        id: `opt-${Date.now()}`,
        action: actionName,
        actor: actor,
        status: 'PENDING',
        timestamp: new Date().toISOString()
      });

      formAction(formData);
      formElement.reset();
    });
  };

  return (
    <div className="audit-system">
      <form onSubmit={handleSubmit} className="mb-4 flex gap-2">
        <input
          name="actionName"
          placeholder="Nama Tindakan (mis: DEPOSIT_FUNDS)"
          className="border p-2 rounded"
          required
        />
        <input
          name="actor"
          placeholder="Actor ID"
          className="border p-2 rounded"
          required
        />
        <button
          type="submit"
          disabled={isPending}
          className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
        >
          {isPending ? 'Memproses...' : 'Catat Log'}
        </button>
      </form>

      {state?.error && (
        <div className="p-3 bg-red-100 text-red-700 rounded mb-4">
          Gagal: {state.error}
        </div>
      )}

      <table className="w-full border-collapse border border-gray-300">
        <thead>
          <tr className="bg-gray-100">
            <th className="border p-2 text-left">ID</th>
            <th className="border p-2 text-left">Action</th>
            <th className="border p-2 text-left">Actor</th>
            <th className="border p-2 text-left">Status</th>
            <th className="border p-2 text-left">Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {optimisticLogs.map((log) => (
            <tr
              key={log.id}
              className={log.status === 'PENDING' ? 'opacity-50 bg-yellow-50' : ''}
            >
              <td className="border p-2 font-mono text-sm">{log.id}</td>
              <td className="border p-2">{log.action}</td>
              <td className="border p-2">{log.actor}</td>
              <td className="border p-2">
                <span className={`px-2 py-1 text-xs rounded ${
                  log.status === 'COMMITTED' ? 'bg-green-100 text-green-800' :
                  log.status === 'PENDING' ? 'bg-yellow-200 text-yellow-800' : 'bg-red-100 text-red-800'
                }`}>
                  {log.status}
                </span>
              </td>
              <td className="border p-2 text-sm">{log.timestamp}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

```tsx
// app/audit/page.tsx (Server Component)
import { Suspense } from 'react';
import { AuditLogTable } from '@/components/AuditLogTable';
import { AuditLogEntry } from '@/types/audit';

async function fetchAuditLogs(): Promise<AuditLogEntry[]> {
  // Simulasi fetch basis data berkecepatan tinggi dengan caching
  return [
    {
      id: 'init-1',
      action: 'SYS_BOOT',
      actor: 'system',
      status: 'COMMITTED',
      timestamp: new Date().toISOString()
    }
  ];
}

export default async function AuditPage() {
  const initialLogs = await fetchAuditLogs();

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-2xl font-bold mb-4">Enterprise Security Audit Logs</h1>
      <Suspense fallback={<div>Memuat audit stream dari database cluster...</div>}>
        <AuditLogTable initialLogs={initialLogs} />
      </Suspense>
    </div>
  );
}
```

---

### 8. Real World Case Study

#### FinSecure Bank: Migrasi Core Banking Portal ke RSC
- **Kondisi Awal**: Dashboard analitik transaksi dibangun dengan client-side SPA (React Vite). Bundle size mencapai 4.2 MB (akibat library visualisasi, formaters date-fns, crypto wrappers, dan parser CSV). FCP (*First Contentful Paint*) berada di angka 4.8 detik pada jaringan 4G tier-2. Latensi tinggi menyebabkan churn user bisnis hingga 18%.
- **Arsitektur Baru**:
  - Semua library analitik heavy-weight (`exceljs`, `echarts-stat`, modul enkripsi audit) diisolasi 100% di dalam Server Components.
  - Interaktivitas (filter tanggal, toggle visualisasi) didelegasikan ke micro-client components.
  - Data transfer menggunakan HTTP/2 Server Streaming melalui format Flight.
- **Hasil**:
  - Ukuran Client JS bundle anjlok dari **4.2 MB menjadi 184 KB** (-95.6%).
  - LCP (*Largest Contentful Paint*) turun drastis dari **5.1s menjadi 1.1s**.
  - Server memory footprint stabil berkat zero-hydration overhead pada static transaction table grid berkapasitas 5.000 baris.

---

### 9. Trade-offs

| Dimensi Arsitektural | Keuntungan RSC | Konsekuensi / Biaya yang Harus Dibayar |
| :--- | :--- | :--- |
| **Performance (Bundle Size)** | Ukuran bundle JavaScript di browser menurun mendekati nol untuk node non-interaktif. | Meningkatnya penggunaan CPU server untuk kalkulasi Flight AST serialization pada load tinggi. |
| **Latency (Network)** | Streaming HTML & Flight memangkas TTFB dan memungkinkan Selective Rendering. | Jika perancangan rute buruk, timbul *waterfall execution* antar Server Components bersarang. |
| **Scalability (Compute Cost)**| Database queries terjadi lokal di VPC datacenter, memangkas latensi Client-to-DB. | Serverless compute bill (Vercel/AWS Lambda) berpotensi melonjak jika cache layer tidak dirancang presisi. |
| **Developer Experience** | Tidak perlu menulis boilerplate REST/GraphQL resolver manual untuk UI display logic. | Mental model split ketat (*Server vs Client Context*). Hilangnya akses langsung browser lifecycle hooks (`useEffect`, `window`) di server components. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Serialization Boundary Poisoning
- **Penyebab**: Mengirim objek complex (Class instances, Functions, atau Promises yang unresolved) melalui props dari Server Component ke Client Component.
- **Solusi**: Hanya kirim Plain Old JavaScript Object (POJO), primitives, atau typed Array. Gunakan serializer eksplisit atau data mapping boundary DTO.

#### 10.2 Server-side Data Waterfall
- **Penyebab**: Memanggil fungsi `await` secara berurutan dalam komponen anak yang bersarang:
  ```tsx
  // SALAH: Waterfall Latency
  async function ComponentA() {
    const user = await getUser();
    return <ComponentB id={user.id} />
  }
  async function ComponentB({ id }) {
    const data = await getTransactions(id); // Menunggu ComponentA selesai
    return <div>...</div>
  }
  ```
- **Solusi**: Paralelisasi pemanggilan data menggunakan `Promise.all` di level atas atau pisahkan segmen independen ke dalam `<Suspense>` terpisah agar stream dapat berjalan konkuren:
  ```tsx
  // BENAR: Suspense-driven Parallel Streaming
  function Dashboard() {
    return (
      <main>
        <Suspense fallback={<SkeletonA />}><AsyncComponentA /></Suspense>
        <Suspense fallback={<SkeletonB />}><AsyncComponentB /></Suspense>
      </main>
    );
  }
  ```

#### 10.3 Ghost Client Execution
- **Penyebab**: Menambahkan directive `'use client'` pada file utilitas umum yang menyebabkan sub-dependensi besar terseret masuk ke browser bundle.
- **Solusi**: Terapkan package boundary guard seperti `import 'server-only'` di bagian paling atas modul yang hanya boleh diakses di sisi server. Kompiler akan membatalkan build jika modul ini diimpor oleh Client Component.

---

### 11. Best Practices (Production Checklist)

- [ ] **Pasang Boundary Isolation**: Wajib menyertakan `import 'server-only'` pada setiap layer data access, repository, dan utilitas token/kredensial.
- [ ] **Validasi Taint Engine**: Terapkan `experimental_taintObjectReference` pada entitas domain sensitif seperti objek sesi user, token vault, dan private keys.
- [ ] **Granular Suspense Placement**: Letakkan boundary `<Suspense>` sedekat mungkin dengan leaf node dinamis untuk mencegah blocking rendering pada keseluruhan halaman.
- [ ] **Idempotensi Server Actions**: Pastikan seluruh Server Actions yang memicu mutasi basis data memiliki mekanisme validasi form token / idempotency key untuk mencegah double-invocation akibat jaringan lambat.
- [ ] **Omit Overhead Payload**: Jangan mengambil seluruh kolom SQL (`SELECT *`). Ambil hanya field yang dirender untuk memperkecil ukuran Flight Protocol wire stream.

---

### 12. Hands-on Practice

Implementasikan custom edge-compliant pipeline dan validasi Flight streaming di direktori `hands-on/m02/`.

#### Langkah 1: Inisialisasi Project Workspace
```bash
mkdir -p hands-on/m02/src/{actions,components,server,types}
cd hands-on/m02
npm init -y
npm install react@rc react-dom@rc server-only
npm install -D typescript @types/react @types/node tsx
```

#### Langkah 2: Konfigurasi TypeScript Standar
Buat file `hands-on/m02/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "jsx": "react-jsx",
    "strict": true,
    "skipLibCheck": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

#### Langkah 3: Definisikan Komponen Tainted Core
Buat file `hands-on/m02/src/server/vault.ts`:
```typescript
import 'server-only';
import { experimental_taintObjectReference } from 'react';

export interface SensitiveVault {
  systemKey: string;
  treasuryBalance: number;
}

export const vaultData: SensitiveVault = {
  systemKey: 'SYS-SEC-9988-XKL',
  treasuryBalance: 550_000_000
};

// Pasang proteksi taint
experimental_taintObjectReference(
  'SECURITY BREACH: Server Vault Data dilarang dirender langsung ke Client boundary!',
  vaultData
);

export function getPublicMetrics() {
  return {
    treasuryBalance: vaultData.treasuryBalance
  };
}
```

#### Langkah 4: Simulasikan Engine Runner
Buat runner simulasi pada `hands-on/m02/src/index.ts`:
```typescript
import { getPublicMetrics, vaultData } from './server/vault.js';

console.log('--- RUNNING RSC SECURITY SIMULATION ---');
const metrics = getPublicMetrics();
console.log('Public Data aman diserialisasi:', JSON.stringify(metrics));

try {
  console.log('Mencoba menyusupkan vault data mentah...');
  // Simulasi serialisasi Flight
  JSON.stringify(vaultData);
  console.log('WARNING: Serialisasi berhasil, pastikan runtime React engine aktif untuk memicu Taint Trap.');
} catch (error) {
  console.error('Taint guard intercepted payload:', error);
}
```

Jalankan script verifikasi:
```bash
npx tsx src/index.ts
```

---

### 13. Exercise

#### Level Easy
Ubah Server Component berikut agar memfilter data sebelum diserialisasikan ke Client Component tanpa membocorkan field `hashedPassword`:
```typescript
// Skenario Awal
export async function UserList() {
  const users = await db.query('SELECT id, name, hashedPassword FROM users');
  return <ClientGrid users={users} />; // Masalah: Data password bocor di wire stream!
}
```

#### Level Medium
Buat sebuah Server Action `updateInventory(itemId: string, delta: number)` yang mengimplementasikan rollback otomatis bila stok bernilai negatif, dipasangkan dengan `useOptimistic` di antarmuka klien.

#### Level Hard
Rancang arsitektur kustom *Flight-like payload multiplexer* sederhana di atas Node.js HTTP stream native yang memecah dua proses asinkron independen (Fast Service 100ms dan Slow Service 2000ms) menjadi format multi-chunk serialisasi.

---

### 14. Challenge

**Skenario**: Sistem Rekonsiliasi Finansial Global dengan Beban Data 50.000 Baris Realtime.
- **Tantangan**: Anda dilarang melakukan pagination. Seluruh 50.000 baris ringkasan ledger harus dapat dimuat tanpa membekukan thread browser, dengan ukuran initial JS bundle tetap di bawah **50 KB**.
- **Kebutuhan Teknis**:
  - Terapkan Server Component berbasis streaming chunking terfragmentasi.
  - Kombinasikan dengan Client-Side Virtualized Scroller yang mengonsumsi stream Flight yang masuk secara progresif.
  - Sediakan proteksi penuh terhadap kebocoran master ledger encryption seed menggunakan API Taint.
  - Implementasikan Server Action untuk rekonsiliasi satu-baris secara in-place tanpa memicu refetch 50.000 baris data lainnya.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic
1. Apa fungsi dari MIME type `text/x-component` pada arsitektur React Server Components?
   - A. Menjalankan skrip service worker di browser
   - B. Mentransfer payload representasi pohon UI Flight Protocol dari server ke client
   - C. Menggantikan format JSON standar untuk seluruh REST API
   - D. Merender file CSS langsung dari server database
   *Kunci*: B. Runtime klien RSC memerlukan content-type ini untuk memicu decoder Flight stream.

2. Manakah ekstensi kode yang mengindikasikan file HANYA boleh dieksekusi di server?
   - A. `'use client'`
   - B. `import 'client-only'`
   - C. `import 'server-only'`
   - D. `export default dynamic`
   *Kunci*: C. Pustaka ini memblokir impor file ke boundary klien saat fase bundler build.

3. Apakah Server Component menghasilkan ukuran bundle JavaScript di sisi browser?
   - A. Ya, sama seperti SSR konvensional
   - B. Tidak, dependensi Server Component murni dieksekusi di server dan tidak masuk ke bundle JS browser
   - C. Ya, tetapi hanya jika menggunakan TypeScript
   - D. Tergantung apakah CSS module digunakan
   *Kunci*: B. Zero client-side JS bundle overhead adalah karakteristik fundamental RSC.

4. Kapan direktif `'use server'` harus disematkan pada fungsi?
   - A. Ketika ingin menjadikan file sebagai Server Component biasa
   - B. Ketika mendefinisikan Server Action (RPC endpoint yang dapat dipanggil oleh klien)
   - C. Di setiap awal file konfigurasi database
   - D. Saat menulis middleware Node.js
   *Kunci*: B. `'use server'` adalah penanda boundary RPC Server Action, bukan deklarasi Server Component.

5. Hook manakah yang digunakan untuk mengelola mutasi asinkron dan membaca state hasil kembalian dari Server Action secara native di React 19?
   - A. `useEffect`
   - B. `useActionState`
   - C. `useCallback`
   - D. `useLayoutEffect`
   *Kunci*: B. `useActionState` adalah API resmi untuk mengikat Server Action dengan state tracking (pending, data, error).

#### Bagian 2: Intermediate
6. Pada payload Flight Protocol, representasi baris yang diawali dengan `M:` merepresentasikan:
   - A. Database Migration chunk
   - B. Client Component Module Reference
   - C. Server Memory dump
   - D. Suspense Error fallback
   *Kunci*: B. Tag `M` memetakan ID modul klien dan file chunk JavaScript yang perlu diunduh oleh browser.

7. Mengapa memanggil `taintUniqueValue` lebih disarankan dibanding manual object mapping pada skenario keamanan data tingkat tinggi?
   - A. Karena manual mapping membuat aplikasi menjadi lebih lambat hingga 500%
   - B. Taint engine memblokir kebocoran nilai sensitif tersebut di mana pun ia berada, bahkan jika developer tidak sengaja mengopernya via properti bersarang
   - C. `taintUniqueValue` otomatis mengenkripsi data di dalam basis data PostgreSQL
   - D. Taint engine menonaktifkan inspect element di devtools browser
   *Kunci*: B. Taint API bekerja di level React serialization runtime, mencegah human error saat developer menstruktur ulang prop tree.

8. Apa dampak utama dari meletakkan boundary `<Suspense>` di tingkat paling atas (Root Layout) terhadap streaming performance?
   - A. Meningkatkan kecepatan streaming secara drastis
   - B. Mematikan fitur Server Components sepenuhnya
   - C. Menahan rendering antarmuka hingga komponen terlambat selesai, menghilangkan keuntungan selective streaming UI
   - D. Menyebabkan browser me-refresh halaman berulang kali
   *Kunci*: C. Granularitas Suspense yang terlalu luas memaksa klien menunggu komponen paling lambat sebelum shell utama bisa digambar secara utuh.

9. Bagaimana Server Action menangani proteksi CSRF (*Cross-Site Request Forgery*) secara arsitektural?
   - A. Membutuhkan konfigurasi manual `cors.json`
   - B. Menggunakan pencocokan Action ID acak yang di-generate per-build dan validasi header `Origin` vs `Host`
   - C. Memblokir seluruh koneksi browser selain Google Chrome
   - D. Mengubah seluruh metode HTTP menjadi GET
   *Kunci*: B. Modern RSC implementations memverifikasi hash ID aksi internal serta header Origin untuk menangkal manipulasi CSRF lintas domain secara otomatis.

10. Apa yang terjadi jika Client Component mengimpor Server Component secara langsung?
    - A. Server Component otomatis diturunkan derajatnya menjadi Client Component dan dependensinya bocor ke bundle browser
    - B. Build gagal secara otomatis dengan error compiler boundary
    - C. Server Component dieksekusi secara instan di local storage browser
    - D. Database terhapus
    *Kunci*: A. Mengimpor file Server Component ke file bertanda `'use client'` akan memaksa compiler memperlakukannya sebagai Client Component kecuali dioper via *composition* (`children` pattern).

#### Bagian 3: Production Scenarios
11. **Skenario Kasus**: Tim Anda mendapati bahwa TTFB rute `/dashboard` sangat lambat (3.8 detik). Profiling menunjukkan ada 3 async fetch queries: `getProfile()` (50ms), `getRecentOrders()` (120ms), dan `getFinancialSummary()` (3600ms). Bagaimana arsitektur refactoring terbaik menggunakan RSC?
    - A. Membungkus ketiga pemanggilan ke dalam `Promise.all` di root komponen page
    - B. Mengubah seluruh halaman menjadi `'use client'` dan memanggil data menggunakan `useEffect`
    - C. Render `getProfile` dan `getRecentOrders` langsung di shell utama, dan bungkus `getFinancialSummary` di dalam `<Suspense fallback={<SummarySkeleton />}>`
    - D. Menghapus query `getFinancialSummary` dari server dan memindahkannya ke Web Worker
    *Kunci*: C. Isolasi fetch lambat ke dalam boundary Suspense independen agar server langsung men-stream segmen yang cepat tanpa menahan koneksi HTTP awal.

12. **Skenario Kasus**: Saat melakukan audit keamanan, ditemukan bahwa API key pihak ketiga bocor ke tab Network browser dalam stream `text/x-component`. Komponen tersebut berjenis Server Component yang mengoper konfigurasi ke Client Component wrapper:
    ```tsx
    // DataConfigProvider.tsx ('use client')
    export function DataConfigProvider({ config }) { ... }
    ```
    Langkah remediasi paling arsitektural dan permanen adalah:
    - A. Mengenkripsi payload menggunakan Base64 sebelum dikirim ke Client Component
    - B. Memasang `experimental_taintUniqueValue` pada API key tersebut di layer konfigurasi server dan merefaktor provider agar hanya menerima data non-sensitif (public DTO)
    - C. Mengganti nama variabel dari `API_KEY` menjadi `PUBLIC_API_KEY`
    - D. Mengubah server component menjadi client component seutuhnya
    *Kunci*: B. Penggunaan Taint API secara eksplisit memberikan jaminan sistemik bahwa engine Flight akan memutus proses dan melempar error build/runtime jika token tersebut dikirimkan ke client boundary.

13. **Skenario Kasus**: Pada sistem e-commerce berskala 10.000 RPM, sebuah Server Action mutasi stok sering mengalami race condition saat dua user checkout produk terakhir bersamaan. Pendekatan integrasi manakah yang paling tepat di layer RSC?
    - A. Mengandalkan `useOptimistic` di browser untuk mengunci stok
    - B. Menerapkan transaksi database tingkat isolasi `SERIALIZABLE` atau atomic update (`UPDATE ... WHERE stock > 0`) di dalam Server Action, lalu merespons dengan failure result jika stok habis
    - C. Melakukan looping `fetch` berulang kali di sisi browser sampai berhasil
    - D. Menonaktifkan JavaScript di browser pengguna
    *Kunci*: B. Optimistic UI di klien hanya untuk tampilan kosmetik sementara; integritas transaksi data mutlak dikelola secara atomik di dalam runtime Server Action di sisi basis data.

---

### 16. Summary

Arsitektur React Server Components (RSC) merevolusi paradigma pengembangan antarmuka web enterprise dengan memisahkan komputasi data statis murni dari interaktivitas browser. Melalui transmisi **Flight Protocol** yang efisien, RSC memungkinkan aplikasi memuat UI secara progresif via HTTP streaming tanpa membengkakkan ukuran JavaScript bundle di sisi klien.

Keberhasilan implementasi produksi menuntut pemahaman mendalam atas batas serialisasi (*serialization boundaries*), mitigasi keamanan menggunakan **React Taint APIs**, orkestrasi mutasi data modern via **Server Actions**, dan perancangan pohon komponen berbasis **Suspense boundaries** guna mengeliminasi rendering waterfalls dan menghadirkan performa web berstandar kelas dunia.