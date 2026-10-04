# BAB 06: Data Synchronization & Enterprise State Management
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Mengimplementasikan** pemisahan fundamental antara *Server State* (asinkron, cache-driven, out-of-process) dan *Client/UI State* (sinkron, ephemeral, in-process) pada arsitektur frontend skala enterprise.
- **Membongkar Mekanisme Internal TanStack Query Core**: Query Observer Pattern, Garbage Collection lifecycle (`gcTime`), Stale Lifetime (`staleTime`), serta algoritma *Structural Sharing* untuk mencegah mutasi referensial yang tidak perlu.
- **Mencegah Masalah UI Tearing** pada React 18/19 Concurrent Rendering menggunakan integrasi `useSyncExternalStore` dengan store eksternal.
- **Mendesain Pipeline Sinkronisasi Real-Time Dua Arah** yang menggabungkan Server-Sent Events (SSE) / WebSocket dengan Query Cache Invalidation Graph secara deterministik.
- **Mengembangkan Mutasi Kompleks dengan Optimistic UI Rollback Engine** yang tahan terhadap kegagalan jaringan parsial, race conditions, dan out-of-order execution.

---

### 2. Prerequisite

Sebelum memulai modul ini, Anda wajib menguasai:
- **TypeScript Tingkat Lanjut**: Generic Constraints, Discriminated Unions, Utility Types (`Extract`, `Exclude`, `Parameters`, `ReturnType`), serta manipulasi tuple/array literal (`as const`).
- **React Internals**: Mekanisme Fiber Tree reconciliation, Suspense boundary lifecycle, dan Concurrent Features (`useTransition`, `useDeferredValue`).
- **Dasar State Management**: Konsep *Immutability*, Redux Pattern/Flux Architecture, dan dasar-dasar TanStack Query v5 (useQuery, useMutation).
- **Protokol Jaringan**: Dasar-dasar HTTP caching headers (`ETag`, `Cache-Control`, `stale-while-revalidate`), WebSockets, dan SSE stream handling.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Server State vs. Client State Segregation
Dalam arsitektur frontend modern skala enterprise, salah satu kegagalan arsitektural terbesar adalah **Global State Monolith** (menyimpan seluruh payload API ke dalam Redux/Zustand store). 

```
+-----------------------------------------------------------------------------------+
|                                 APPLICATION STATE                                 |
+-----------------------------------------+-----------------------------------------+
|              SERVER STATE               |              CLIENT STATE               |
+-----------------------------------------+-----------------------------------------+
| Karakteristik:                          | Karakteristik:                          |
| - Tidak dimiliki oleh browser           | - Dimiliki seutuhnya oleh browser       |
| - Diambil secara asinkron (remote)      | - Sinkron & deterministik               |
| - Berpotensi stale/usang kapan saja     | - Ephemeral (hilang saat refresh)       |
| - Dibagi bersama banyak user            | - Bersifat lokal ke user/sesi ini       |
|                                         |                                         |
| Tanggung Jawab Engine Cache:            | Tanggung Jawab Client Store:            |
| - Deduplikasi request                   | - Toggle Sidebar, Dark/Light Mode       |
| - Invalidation & Polling                | - Multi-step Wizard Form progress       |
| - Pagination & Infinite scroll cache    | - Client-side draft filtering           |
| - Optimistic response reconciliation    | - Modals, Toasts, Focus trapping        |
+-----------------------------------------+-----------------------------------------+
```

#### 3.2 TanStack Query Cache Machine: Observer Pattern & Structural Sharing
TanStack Query v5 tidak mengandalkan React Context untuk transport data query. Ia menggunakan arsitektur **Sub-Pub / Observer Pattern** murni di luar React:

1. **`QueryClient`**: Mengelola instance tunggal dari `QueryCache` dan `MutationCache`.
2. **`Query`**: Unit dasar yang menyimpan metadata, state (data, error, status), dan timers (`staleTime`, `gcTime`).
3. **`QueryObserver`**: Jembatan antara satu komponen React dan satu `Query`. Obserber mengawasi perubahan query dan memicu re-render melalui `useSyncExternalStore`.
4. **Structural Sharing**: Ketika data baru diambil, query engine membandingkan data lama (`prevData`) dan data baru (`nextData`) secara rekursif hingga ke level node terdalam. Jika sebuah subtree secara struktural identik, referensi objek lama dipertahankan:
   
$$\text{prevData.user} === \text{nextData.user} \implies \text{No React Fiber Re-render}$$

```
+-----------------------------------------------------------------------------+
|                          STRUCTURAL SHARING ENGINE                          |
+-----------------------------------------------------------------------------+
Old Data: { id: 1, user: { name: "Alice", role: "Dev" }, stats: { hits: 40 } }
New Data: { id: 1, user: { name: "Alice", role: "Dev" }, stats: { hits: 41 } }
                                    |
                                    v
Result:   { id: 1, user: [Old Ref], stats: [New Ref] }
                 (Subtree identik: referensi memori tidak berubah)
```

#### 3.3 Penanganan Concurrent Mode & Tearing
Sebelum React 18, pembacaan store eksternal di tengah concurrent render dapat menghasilkan **Tearing** (keadaan di mana dua komponen di layar menampilkan data yang berbeda untuk versi store yang sama akibat interupsi rendering berprioritas tinggi).

TanStack Query dan Zustand mengimplementasikan `useSyncExternalStore`:
```ts
useSyncExternalStore(
  subscribe,     // Daftarkan listener ke QueryObserver / Store
  getSnapshot,   // Mengembalikan referensi data sinkron saat ini (harus immutable)
  getServerSnapshot // Mengembalikan snapshot untuk SSR hydration
)
```
Engine React mengecek konsistensi snapshot sebelum me-commit Fiber tree ke DOM. Jika terdeteksi perubahan snapshot di tengah-tengah concurrent render, React membuang tree tersebut dan merender ulang dari awal secara sinkron.

---

### 4. Why & What

| Dimensi | Mengapa Arsitektur Ini Dipilih? | Apa Masalah yang Diselesaikan? |
| :--- | :--- | :--- |
| **Pemisahan Cache vs Store** | Menghilangkan 90% boilerplate action/reducer yang hanya bertugas menampung data backend. | Menghilangkan memory leak, race conditions pada asinkronisitas, dan data staleness. |
| **Structural Sharing** | Komponen murni (`memo`) atau selector hanya merender ulang jika data internalnya benar-benar berubah referensinya. | Menghilangkan bottleneck re-render pada dashboard data berskala tinggi (ribuan node data per detik). |
| **Optimistic Updates Engine** | Pengguna enterprise membutuhkan respons instan tanpa menunggu round-trip latency jaringan (~200-800ms). | Menghilangkan loading spinner yang mengganggu alur kerja operasional intensif. |
| **Deduplikasi Request** | Dua puluh komponen yang meminta query key yang sama hanya akan memicu 1 permintaan jaringan HTTP tunggal. | Menghilangkan overhead thundering-herd effect pada backend API gateway. |

---

### 5. How (Workflow Detail)

Alur mutasi optimistik tingkat produksi dengan mitigasi rollback dan invalidasi berbasis SSE:

```
[User Action] 
      │
      ▼
1. onMutate(variables)
      │
      ├─► A. queryClient.cancelQueries({ queryKey }) ──► Mencegah outgoing fetches menimpa state optimistik
      ├─► B. context.previousSnapshot = getQueryData(queryKey) ──► Simpan rollback snapshot
      └─► C. queryClient.setQueryData(queryKey, optimisticTransform) ──► Update cache secara instan
      │
      ▼
2. HTTP Mutation Request Dispatch (Network Boundary)
      │
      ├───────────────────────────────┬──────────────────────────────┐
      ▼                               ▼                              ▼
  [Success (2xx)]             [Network/5xx Failure]          [WebSocket / SSE Event]
      │                               │                              │
      ▼                               ▼                              │
3. onSuccess()                  3. onError(err, vars, ctx)          │
      │                               │                              │
      │                               └─► queryClient.setQueryData(  │
      │                                     queryKey,                │
      │                                     ctx.previousSnapshot     │
      │                                   )                          │
      │                                  (Rollback otomatis)         │
      │                               │                              │
      └───────────────┬───────────────┘                              │
                      ▼                                              ▼
               4. onSettled() ◄──────────────────────────────────────┘
                      │
                      └─► queryClient.invalidateQueries({ queryKey })
                          (Ambil data autoritatif final dari server)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Pinjaman & Papan Pengumuman
- **Server API** adalah *Gudang Pusat Penerbit Buku*.
- **TanStack Query Cache** adalah *Meja Resepsionis Perpustakaan Lokal*. Jika Anda meminta buku, resepsionis memberikannya langsung dari rak meja jika masih ada (`gcTime`) dan belum kedaluwarsa (`staleTime`). Jika sudah berdebu (`stale`), resepsionis memberikan buku tersebut kepada Anda sambil mengirim kurir ke gudang pusat untuk mengambil edisi revisi terbaru di latar belakang.
- **Client State (Zustand)** adalah *Buku Catatan Pribadi di Saku Anda*. Anda menuliskan preferensi posisi duduk Anda, bookmark halaman, dan status kacamata Anda di sini. Resepsionis tidak perlu mengetahui hal ini.

#### Diagram Arsitektur Integrasi Enterprise
```
+-------------------------------------------------------------------------------------------------+
|                                     BROWSER ENVIRONMENT                                         |
|                                                                                                 |
|   +------------------------------------+             +--------------------------------------+   |
|   |         React UI Components        |             |            Client UI Store           |   |
|   |   (Fiber Tree / Suspense Boundaries)  |◄────────────┤               (Zustand)              |   |
|   +-----------------+------------------+             |  - Modal State                       |   |
|                     │                                |  - User Theme Preference             |   |
|       useQuery() /  │ useSyncExternalStore           |  - Filter & Sort Criteria            |   |
|       useMutation() │                                +--------------------------------------+   |
|                     ▼                                                                           |
|   +-----------------------------------------------------------------------------------------+   |
|   |                                  TANSTACK QUERY CLIENT                                  |   |
|   |                                                                                         |   |
|   |   +-----------------------+     Structural Sharing      +---------------------------+   |   |
|   |   |      Query Cache      | ◄─────────────────────────  |    QueryObserver Engine   |   |   |
|   |   |  - Entities, Tuples   |                             +---------------------------+   |   |
|   |   |  - Garbage Collector  |                                           ▲                 |   |
|   |   +-----------+-----------+                                           │                 |   |
|   +---------------│-------------------------------------------------------│-----------------+   |
|                   │                                                       │                     |
|                   ▼                                                       │                     |
|   +-------------------------------+                       +---------------+-----------------+   |
|   |     Network Layer (Axios/Fetch)│                       |   Real-Time Client (WS / SSE)   |   |
|   +---------------+---------------+                       +---------------+-----------------+   |
+-------------------│-------------------------------------------------------│---------------------+
                    │ HTTPS REST/GraphQL                                    │ WSS / EventSource
                    ▼                                                       ▼
+-------------------------------------------------------------------------------------------------+
|                                      BACKEND ENTERPRISE CLOUD                                   |
|                                                                                                 |
|   +-------------------------------+                       +---------------------------------+   |
|   |     API Gateway / Microservices|                       |    Message Broker (Kafka/Redis) |   |
|   +-------------------------------+                       +---------------------------------+   |
+-------------------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Menghindari Tearing dengan `useSyncExternalStore`
Berikut implementasi dasar custom store yang aman terhadap concurrent rendering tanpa library eksternal:

```typescript
// store/counterStore.ts
type Listener = () => void;

class CounterStore {
  private state = { count: 0 };
  private listeners = new Set<Listener>();

  getState = () => this.state;

  increment = () => {
    this.state = { count: this.state.count + 1 };
    this.listeners.forEach((listener) => listener());
  };

  subscribe = (listener: Listener) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };
}

export const counterStore = new CounterStore();

// hooks/useCounterStore.ts
import { useSyncExternalStore } from 'react';

export function useCounterStore<T>(selector: (state: { count: number }) => T): T {
  return useSyncExternalStore(
    counterStore.subscribe,
    () => selector(counterStore.getState()),
    () => selector({ count: 0 }) // Snapshot untuk SSR
  );
}
```

#### 7.2 Practical Example: Enterprise TanStack Query Architecture + Optimistic Mutation Engine

Di bawah ini adalah struktur implementasi standar enterprise yang memisahkan **Query Factory**, **Optimistic Updates**, dan **SSE Synchronization**.

##### Step 1: Query Key Factory yang Type-Safe
```typescript
// src/lib/query-keys.ts
export const orderKeys = {
  all: ['orders'] as const,
  lists: () => [...orderKeys.all, 'list'] as const,
  list: (filters: { status?: string; page: number }) => [...orderKeys.lists(), filters] as const,
  details: () => [...orderKeys.all, 'detail'] as const,
  detail: (id: string) => [...orderKeys.details(), id] as const,
};
```

##### Step 2: Domain Entity Model
```typescript
// src/types/order.ts
export interface Order {
  id: string;
  orderNumber: string;
  totalAmount: number;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'CANCELLED';
  version: number;
  updatedAt: string;
}

export interface UpdateOrderStatusDTO {
  orderId: string;
  newStatus: Order['status'];
  currentVersion: number;
}
```

##### Step 3: Optimistic Mutation Hook dengan Rollback Matrix
```typescript
// src/features/orders/hooks/useUpdateOrderStatus.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { orderKeys } from '../../../lib/query-keys';
import { Order, UpdateOrderStatusDTO } from '../../../types/order';

interface MutationContext {
  previousOrders?: Order[];
  previousOrderDetail?: Order;
}

export function useUpdateOrderStatus() {
  const queryClient = useQueryClient();

  return useMutation<Order, Error, UpdateOrderStatusDTO, MutationContext>({
    mutationFn: async ({ orderId, newStatus, currentVersion }) => {
      const response = await fetch(`/api/v1/orders/${orderId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus, version: currentVersion }),
      });

      if (!response.ok) {
        if (response.status === 409) {
          throw new Error('VERSION_CONFLICT: Data telah diubah oleh operator lain.');
        }
        throw new Error(`NETWORK_ERROR: ${response.statusText}`);
      }

      return response.json();
    },

    // LANGKAH 1: Optimistic Interception
    onMutate: async (variables) => {
      // Hentikan queries yang relevan agar tidak menimpa state optimistik
      await queryClient.cancelQueries({ queryKey: orderKeys.all });

      // Ambil snapshot data lama untuk potensi rollback
      const previousOrderDetail = queryClient.getQueryData<Order>(
        orderKeys.detail(variables.orderId)
      );

      // Mutasi optimistik pada detail query
      if (previousOrderDetail) {
        queryClient.setQueryData<Order>(orderKeys.detail(variables.orderId), {
          ...previousOrderDetail,
          status: variables.newStatus,
          version: variables.currentVersion + 1,
          updatedAt: new Date().toISOString(),
        });
      }

      // Kembalikan context snapshot
      return { previousOrderDetail };
    },

    // LANGKAH 2: Rollback jika eksekusi gagal
    onError: (err, variables, context) => {
      if (context?.previousOrderDetail) {
        queryClient.setQueryData(
          orderKeys.detail(variables.orderId),
          context.previousOrderDetail
        );
      }
      console.error(`[Mutation Error] Gagal mengubah status order: ${err.message}`);
    },

    // LANGKAH 3: Rekonsiliasi Autoritatif (Selalu dijalankan)
    onSettled: (_data, _error, variables) => {
      queryClient.invalidateQueries({ queryKey: orderKeys.detail(variables.orderId) });
      queryClient.invalidateQueries({ queryKey: orderKeys.lists() });
    },
  });
}
```

##### Step 4: Real-time Invalidation Bridge via SSE
```typescript
// src/lib/sse-cache-sync.ts
import { QueryClient } from '@tanstack/react-query';
import { orderKeys } from './query-keys';

interface InvalidationMessage {
  entity: 'ORDER' | 'INVENTORY';
  action: 'CREATED' | 'UPDATED' | 'DELETED';
  entityId: string;
}

export function initializeSSECacheSync(queryClient: QueryClient, sseUrl: string) {
  const eventSource = new EventSource(sseUrl, { withCredentials: true });

  eventSource.onmessage = (event: MessageEvent) => {
    try {
      const payload: InvalidationMessage = JSON.parse(event.data);

      switch (payload.entity) {
        case 'ORDER':
          if (payload.action === 'UPDATED') {
            // Target invalidate spesifik untuk meminimalkan re-fetch tak perlu
            queryClient.invalidateQueries({
              queryKey: orderKeys.detail(payload.entityId),
              refetchType: 'active', // Hanya refetch jika komponen aktif di layar
            });
            queryClient.invalidateQueries({
              queryKey: orderKeys.lists(),
              refetchType: 'none', // Tandai stale tanpa auto-refetch seketika
            });
          }
          break;
        default:
          break;
      }
    } catch (err) {
      console.error('[SSE Parse Error] Stream corrupt:', err);
    }
  };

  eventSource.onerror = (err) => {
    console.error('[SSE Connection Failed] Reconnecting in background...', err);
  };

  return () => {
    eventSource.close();
  };
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Sistem Manajemen Portofolio FinTech (Multi-Tenant Trading Desk)
* **Konteks**: Dashboard manajemen order trading sekuritas digunakan oleh 2.000+ manajer portofolio. Setiap detik terjadi 300+ perubahan harga dan eksekusi order.
* **Problem**: 
  1. Arsitektur lama menggabungkan live ticker harga dan status order ke dalam satu Redux Store monolith.
  2. Rendering terhambat (*frame drop* hingga 15 FPS) karena Redux memicu re-render pada seluruh komponen grid portofolio setiap kali ticker harga berubah.
  3. Terjadi **Race Condition**: Operator mengklik tombol "Approve Order", tetapi status ter-overwrite kembali ke "PENDING" karena polling HTTP lama menyelesaikan request belakangan dibanding payload REST terkini.
* **Solusi Arsitektur**:
  1. **Segregasi State**: Live Ticker dipindahkan ke WebSocket buffer berbasis IndexedDB + Canvas graph rendering.
  2. Order Execution dipindahkan ke **TanStack Query** dengan **Optimistic Concurrency Control (OCC)** menggunakan versi entitas (`version` field / ETag header).
  3. Sebelum eksekusi mutasi optimistik, query yang tertunda dibatalkan secara deterministik menggunakan `queryClient.cancelQueries()`.
  4. Komponen UI menggunakan `React.memo` yang dipadukan dengan *Structural Sharing* bawaan TanStack Query.
* **Hasil Pengukuran**:
  - Re-render per detik berkurang dari **480 re-renders/sec** menjadi **3 re-renders/sec** pada layar order list.
  - Latensi visual respon aksi klik berkurang dari **380ms** (menunggu HTTP 200 OK) menjadi **< 16ms** (1 cycle refresh rate frame via Optimistic UI).
  - Race condition turun hingga **0%** berkat OCC dan request cancellation.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian / Biaya | Konteks Terbaik |
| :--- | :--- | :--- | :--- |
| **Optimistic Updates** | Persepsi performa instan (Zero latency UI), UX kelas satu. | Logika rollback sangat kompleks, rentan terhadap UI flicker jika request sering gagal. | Mutasi berisiko rendah & berprobabilitas sukses tinggi (>99%) seperti like, toggle, task move. |
| **Pessimistic Updates** | Deterministik murni, implementasi sederhana, tidak memerlukan rollback handling. | UI terasa lambat; pengguna harus menunggu spinner selama network round-trip time (RTT). | Operasi finansial kritis (misal: Transfer Dana, Submit Transaksi Pembayaran). |
| **Structural Sharing (Enabled)** | Mencegah cascade re-render pada nested tree data besar. | Overhead CPU tambahan saat melakukan recursive shallow-diffing pada payload JSON raksasa (>10MB). | Sebagian besar aplikasi enterprise dengan update data sering pada subset kecil data. |
| **SSE Invalidation vs Direct WS Push Data** | Menyimpan data lewat HTTP cache resmi, traffic payload socket sangat kecil (hanya ID entitas). | Membutuhkan extra round-trip HTTP GET setelah event invalidasi diterima. | Skalabilitas jutaan user; memaksimalkan infrastruktur CDN/Reverse-Proxy Caching. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Mutasi Objek Langsung di dalam Cache
* **Kesalahan**: Mengubah properti objek cache secara in-place sebelum menyimpannya ke `setQueryData`.
  ```typescript
  // SALAH FATAL! Merusak referensi structural sharing
  queryClient.setQueryData(orderKeys.detail(id), (old: any) => {
    old.status = 'CANCELLED'; 
    return old;
  });
  ```
* **Solusi**: Terapkan Immutability murni.
  ```typescript
  queryClient.setQueryData<Order>(orderKeys.detail(id), (old) => {
    if (!old) return undefined;
    return { ...old, status: 'CANCELLED' };
  });
  ```

#### 2. Query Key Inconsistency (String vs Non-deterministic Objects)
* **Kesalahan**: Menggunakan objek key yang urutan kuncinya berubah-ubah atau array key yang tidak konsisten secara tipe.
  ```typescript
  // Query 1:
  queryKey: ['orders', { page: 1, filter: 'active' }]
  // Query 2:
  queryKey: ['orders', { filter: 'active', page: 1 }] // Secara internal TanStack mengurutkannya, tetapi berisiko jika ada custom serializer
  ```
* **Solusi**: Gunakan **Query Key Factory Pattern** terpusat dengan tipe `as const` yang tidak dapat dimodifikasi sembarangan.

#### 3. Zombie Child Phenomenon pada Concurrent Tree
* **Gejala**: Komponen anak membaca data dari cache store eksternal yang baru saja dihapus oleh komponen induk, menghasilkan `TypeError: Cannot read properties of undefined`.
* **Troubleshooting Engine**: Pastikan data dibaca melalui `useSyncExternalStore` dengan null-safety guard atau manfaatkan React Suspense boundaries yang terisolasi per level card/list item.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan Factory Terpusat untuk Query Keys**: Hindari penggunaan hardcoded array strings di sembarang hook/komponen.
- [ ] **Konfigurasi `staleTime` vs `gcTime` Secara Tepat**: 
  - `staleTime` default adalah `0` (anggap data langsung usang). Set default enterprise minimal `30_000` (30 detik) untuk menghindari refetch berulang pada perpindahan tab router.
  - `gcTime` harus selalu lebih besar dari `staleTime` (misal: default 5 menit).
- [ ] **Selalu Panggil `cancelQueries` Sebelum Optimistic Update**: Hindari overwriting data optimistik oleh query yang sedang berjalan di *background*.
- [ ] **Isolasi Mutasi Network Error**: Gunakan HTTP status code semantik (misal: 409 Conflict) untuk memberikan feedback interaktif kepada pengguna, bukan sekadar toast error umum.
- [ ] **Nonaktifkan `refetchOnWindowFocus` pada Data Read-Heavy Statis**: Matikan fitur ini pada dashboard analytical yang memiliki jutaan baris data agar tidak membebani server backend saat user berganti tab.
- [ ] **Gunakan Selector Function**: Manfaatkan argumen `select` pada `useQuery` untuk mengambil turunan data spesifik, sehingga komponen hanya merender ulang jika hasil selector tersebut berubah nilainya.

---

### 12. Hands-on Practice

Buat dan jalankan modul latihan enterprise state synchronization ini pada direktori `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── lib/
    │   ├── queryClient.ts
    │   └── queryKeys.ts
    ├── types/
    │   └── inventory.ts
    └── features/
        └── inventory/
            ├── hooks/
            │   ├── useInventoryData.ts
            │   └── useAdjustStockOptimistic.ts
            └── components/
                └── InventoryDashboard.tsx
```

#### File Implementation

##### 1. `hands-on/m02/package.json`
```json
{
  "name": "enterprise-data-sync-m02",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.28.4",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.66",
    "@types/react-dom": "^18.2.22",
    "@vitejs/plugin-react": "^4.2.1",
    "typescript": "^5.2.2",
    "vite": "^5.1.6"
  }
}
```

##### 2. `hands-on/m02/src/types/inventory.ts`
```typescript
export interface InventoryItem {
  id: string;
  sku: string;
  name: string;
  stock: number;
  reserved: number;
  version: number;
}
```

##### 3. `hands-on/m02/src/lib/queryKeys.ts`
```typescript
export const inventoryKeys = {
  all: ['inventory'] as const,
  lists: () => [...inventoryKeys.all, 'list'] as const,
  detail: (id: string) => [...inventoryKeys.all, 'item', id] as const,
};
```

##### 4. `hands-on/m02/src/lib/queryClient.ts`
```typescript
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 menit
      gcTime: 1000 * 60 * 5, // 5 menit
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // Jangan retry jika error disebabkan oleh validasi bisnis
        if (error.message.includes('OUT_OF_STOCK')) return false;
        return failureCount < 3;
      },
    },
  },
});
```

##### 5. `hands-on/m02/src/features/inventory/hooks/useInventoryData.ts`
```typescript
import { useQuery } from '@tanstack/react-query';
import { inventoryKeys } from '../../../lib/queryKeys';
import { InventoryItem } from '../../../types/inventory';

// Mock in-memory database server
const MOCK_INVENTORY_DB: InventoryItem[] = [
  { id: 'item-1', sku: 'LAPTOP-PRO-15', name: 'MacBook Pro 15', stock: 12, reserved: 2, version: 1 },
  { id: 'item-2', sku: 'MONITOR-4K-27', name: 'Dell UltraSharp 27"', stock: 4, reserved: 0, version: 1 },
];

export function useInventoryData() {
  return useQuery<InventoryItem[], Error>({
    queryKey: inventoryKeys.lists(),
    queryFn: async () => {
      // Simulasi delay jaringan HTTP 300ms
      await new Promise((res) => setTimeout(res, 300));
      return structuredClone(MOCK_INVENTORY_DB);
    },
  });
}
```

##### 6. `hands-on/m02/src/features/inventory/hooks/useAdjustStockOptimistic.ts`
```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { inventoryKeys } from '../../../lib/queryKeys';
import { InventoryItem } from '../../../types/inventory';

interface AdjustStockInput {
  itemId: string;
  adjustment: number;
}

interface Context {
  previousList?: InventoryItem[];
}

export function useAdjustStockOptimistic() {
  const queryClient = useQueryClient();

  return useMutation<InventoryItem, Error, AdjustStockInput, Context>({
    mutationFn: async ({ itemId, adjustment }) => {
      // Simulasi delay eksekusi server
      await new Promise((res) => setTimeout(res, 700));

      // Simulasi error acak jika stock bernilai minus untuk mendemonstrasikan Rollback Engine
      if (adjustment < -10) {
        throw new Error('OUT_OF_STOCK: Pengurangan melebihi batas toleransi sistem');
      }

      return {
        id: itemId,
        sku: 'UPDATED-SKU',
        name: 'Item Confirmed',
        stock: 99, // Dummy return
        reserved: 0,
        version: Date.now(),
      };
    },
    onMutate: async ({ itemId, adjustment }) => {
      // 1. Batalkan query aktif
      await queryClient.cancelQueries({ queryKey: inventoryKeys.lists() });

      // 2. Snapshot state lama
      const previousList = queryClient.getQueryData<InventoryItem[]>(inventoryKeys.lists());

      // 3. Modifikasi cache optimistik
      if (previousList) {
        queryClient.setQueryData<InventoryItem[]>(
          inventoryKeys.lists(),
          previousList.map((item) => {
            if (item.id === itemId) {
              return {
                ...item,
                stock: item.stock + adjustment,
                version: item.version + 1,
              };
            }
            return item;
          })
        );
      }

      return { previousList };
    },
    onError: (err, _variables, context) => {
      // 4. Rollback ke state awal jika request gagal
      if (context?.previousList) {
        queryClient.setQueryData(inventoryKeys.lists(), context.previousList);
      }
      alert(`[ERROR ROLLBACK EXECUTED] ${err.message}`);
    },
    onSettled: () => {
      // 5. Selalu re-validate untuk menjamin sinkronisasi absolut
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
    },
  });
}
```

##### 7. `hands-on/m02/src/features/inventory/components/InventoryDashboard.tsx`
```typescript
import React from 'react';
import { useInventoryData } from '../hooks/useInventoryData';
import { useAdjustStockOptimistic } from '../hooks/useAdjustStockOptimistic';

export const InventoryDashboard: React.FC = () => {
  const { data: items, isLoading, isError, error } = useInventoryData();
  const mutation = useAdjustStockOptimistic();

  if (isLoading) return <div>Memuat Enterprise State Cache...</div>;
  if (isError) return <div>Terjadi Kesalahan: {error.message}</div>;

  return (
    <div style={{ fontFamily: 'sans-serif', padding: '24px' }}>
      <h2>Real-Time Inventory State Engine</h2>
      <p style={{ color: '#666' }}>
        Perhatikan perubahan counter stock: update terjadi <b>seketika</b> (0ms) secara optimistik.
      </p>

      <table border={1} cellPadding={8} style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr style={{ background: '#f4f4f4' }}>
            <th>SKU</th>
            <th>Nama Item</th>
            <th>Tersedia (Stock)</th>
            <th>Versi Entitas</th>
            <th>Aksi Optimistik</th>
          </tr>
        </thead>
        <tbody>
          {items?.map((item) => (
            <tr key={item.id}>
              <td><code>{item.sku}</code></td>
              <td>{item.name}</td>
              <td style={{ fontWeight: 'bold', fontSize: '1.2em' }}>{item.stock}</td>
              <td>v{item.version}</td>
              <td>
                <button
                  disabled={mutation.isPending}
                  onClick={() => mutation.mutate({ itemId: item.id, adjustment: 1 })}
                >
                  +1 Stok (Valid)
                </button>
                {' '}
                <button
                  disabled={mutation.isPending}
                  onClick={() => mutation.mutate({ itemId: item.id, adjustment: -15 })}
                  style={{ color: 'red' }}
                >
                  -15 Stok (Trigger Rollback Error)
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {mutation.isPending && <p style={{ color: 'orange' }}>Sinkronisasi background ke server...</p>}
    </div>
  );
};
```

##### 8. `hands-on/m02/src/App.tsx` & `main.tsx`
```typescript
// src/App.tsx
import React from 'react';
import { InventoryDashboard } from './features/inventory/components/InventoryDashboard';

export const App: React.FC = () => {
  return <InventoryDashboard />;
};

// src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';
import { App } from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
);
```

#### Instruksi Menjalankan
1. Navigasi ke direktori modul:
   ```bash
   cd hands-on/m02/
   ```
2. Pasang dependensi:
   ```bash
   npm install
   ```
3. Jalankan development server:
   ```bash
   npm run dev
   ```
4. Buka peramban di URL yang ditampilkan (default: `http://localhost:5173`). Uji klik tombol valid vs tombol pemicu rollback untuk melihat mutasi visual cache dan restorasi otomatis.

---

### 13. Exercise

#### Level Easy
* **Tugas**: Tambahkan selector function ke dalam custom hook `useInventoryData` untuk hanya mengekstrak item yang memiliki stok di bawah 10 unit (`lowStockItems`).
* **Kriteria Keberhasilan**: Komponen konsumen tidak merender ulang jika perubahan data inventaris hanya mempengaruhi item dengan stok $\ge 10$.

#### Level Medium
* **Tugas**: Implementasikan mekanisme **Infinite Scroll Pagination Query** menggunakan `useInfiniteQuery` untuk entitas Log Audit. Query key harus menangani filter dinamis `severity` (`INFO`, `WARN`, `CRITICAL`).
* **Kriteria Keberhasilan**: Cache halaman sebelumnya tidak hilang saat memuat halaman berikutnya, dan cursor token di-pass secara konsisten melalui payload `getNextPageParam`.

#### Level Hard
* **Tugas**: Buat arsitektur **Cache Sync Engine Dua Sisi** menggunakan BroadcastChannel API. Ketika Tab Browser A melakukan mutasi dan menginvalidasi query, Tab Browser B harus otomatis menginvalidasi query yang sama di memori lokalnya tanpa memerlukan koneksi WebSocket backend aktif.
* **Kriteria Keberhasilan**: Mutasi pada Tab A langsung memicu refetch sinkron pada Tab B dalam waktu $\le 50$ms tanpa race condition.

---

### 14. Challenge

Rancang dan bangun **Distributed Offline Queue Sync Architecture** untuk modul order entry warehouse di area dengan konektivitas buruk:
1. Ketika koneksi terputus (`navigator.onLine === false`), mutasi yang dipicu operator tidak boleh gagal.
2. Mutasi harus disimpan ke dalam antrean persisten di browser (`IndexedDB`) dengan metadata stempel waktu dan ID idempotent (UUID v4).
3. Buat algoritma rekonsiliasi berbasis **Vector Clock** sederhana untuk mendeteksi *Conflict Update* jika order yang sama telah diubah oleh operator lain saat offline.
4. Ketika peramban mendeteksi status `online`, pipeline secara otomatis mengeksekusi antrean mutasi dengan pembatasan konkurensi (maksimal 2 request simultan) dan memutakhirkan TanStack Query Cache tanpa menyebabkan *UI freeze*.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konsep Dasar (5 Pertanyaan)
1. Apa perbedaan arsitektural fundamental antara `staleTime` dan `gcTime` (dulu `cacheTime`) di TanStack Query v5?
2. Mengapa memasukkan seluruh respons API dari server ke dalam global client store seperti Redux/Zustand dianggap sebagai sebuah *anti-pattern* pada aplikasi skala enterprise?
3. Masalah render concurrency apa yang dicegah secara spesifik oleh hook `useSyncExternalStore`?
4. Apa peran algoritma *Structural Sharing* pada TanStack Query terhadap proses reconciliation di React Fiber tree?
5. Mengapa pemanggilan `queryClient.cancelQueries()` sangat krusial di awal siklus mutasi optimistik (`onMutate`)?

#### Bagian B: Analisis Tingkat Menengah (5 Pertanyaan)
6. Sebuah mutasi optimistik memodifikasi cache array lokal. Jika server merespons dengan HTTP 500 setelah 1 detik, bagaimana cara engine memastikan UI kembali ke state sebelum mutasi tanpa kehilangan mutasi lain yang terjadi di antara interval waktu tersebut?
7. Apa bahaya performa mematikan `structuralSharing` secara global (`structuralSharing: false`) pada aplikasi dengan ribuan data table row?
8. Bagaimana strategi invalidasi cache yang tepat saat menggunakan arsitektur event-driven Server-Sent Events (SSE) agar terhindar dari *thundering herd problem* pada server backend?
9. Jika Anda menggunakan `select` transformation di dalam hook `useQuery`, di tahapan mana seleksi data dieksekusi: sebelum atau sesudah data masuk ke dalam Query Cache internal?
10. Jelaskan apa yang terjadi jika sebuah komponen meng-unmount ketika sebuah `useMutation` sedang berada pada status *in-flight* (menunggu respons network)!

#### Bagian C: Skenario Kasus Produksi (3 Skenario)
11. **Skenario 1**: Pada dashboard perbankan, pengguna mengeklik tombol transfer berkali-kali secara cepat akibat koneksi internet yang lambat. Tombol tidak ter-disable dengan benar. Bagaimana Anda merancang layer sinkronisasi mutasi di frontend menggunakan ID Idempotensi dan TanStack Mutation State untuk menjamin backend hanya mengeksekusi transfer tepat satu kali?
12. **Skenario 2**: Aplikasi micro-frontend Anda memuat dua bundle independen yang sama-sama menggunakan TanStack Query Client masing-masing. Ketika Micro-frontend A memperbarui profil pengguna, Micro-frontend B tetap menampilkan data avatar lama. Apa akar masalah arsitektur ini dan bagaimana mengatasinya tanpa menyatukan seluruh bundle menjadi monolith?
13. **Skenario 3**: Sebuah query dengan polling interval setiap 2 detik (`refetchInterval: 2000`) menyebabkan konsumsi memori browser meningkat secara bertahap (*memory leak*) setelah 4 jam dijalankan terus-menerus pada layar monitoring operator. Langkah diagnosis dan perbaikan teknis apa yang harus Anda ambil pada level Query Observer?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Solusi Bagian A
1. `staleTime` menentukan durasi (ms) sebuah data dianggap masih "segar". Selama data masih fresh, query tidak akan memicu refetch ke jaringan saat komponen mount ulang. Sedangkan `gcTime` menentukan durasi data yang tidak aktif (tidak memiliki observer/komponen yang menggunakannya) tetap dipertahankan di memori sebelum dibersihkan oleh Garbage Collector.
2. Karena Server State bukan milik browser; data tersebut hanya representasi snapshot sesaat dari basis data remote. Menyimpan server state di Redux menuntut developer mengelola siklus invalidasi manual, deduplikasi, retry, garbage collection, dan race conditions sendiri—yang menghasilkan ribuan baris boilerplate rentan bug.
3. Mencegah **Tearing** (inkonsistensi visual di mana bagian UI yang berbeda menampilkan versi data yang tidak selaras karena concurrent renderer menginterupsi rendering untuk prioritas lain).
4. Algoritma ini mempertahankan referensi memori node objek lama jika isinya tidak berubah. Hal ini memastikan `React.memo` atau `useMemo` downstream tidak terpicu secara keliru, menghindari re-render yang tidak esensial.
5. Untuk mencegah *in-flight network response* dari query fetch sebelumnya menyelesaikan prosesnya dan menimpa perubahan optimistik lokal yang baru saja ditulis ke cache.

#### Solusi Bagian B
6. Dengan menyimpan snapshot cache lama di context `onMutate` dan mengembalikannya secara deterministik di blok callback `onError`. Jika ada mutasi berurutan yang saling bergantung, sistem harus menggunakan queue mutasi berantai atau membatalkan mutasi paralel berikutnya sebelum rollback dieksekusi.
7. Setiap data baru tiba (bahkan jika identik 100%), TanStack Query akan membuat referensi objek baru secara utuh. Ini membatalkan seluruh optimasi memoization (`React.memo`), menyebabkan seluruh baris tabel me-render ulang dari awal dan menghasilkan stutter pada UI thread.
8. Event SSE tidak boleh memuat payload data raksasa secara serentak ke ribuan client untuk memaksa update. Cukup kirim sinyal invalidasi ringan (Entity ID). Di sisi client, tambahkan *jitter* (random delay antara 0-1500ms) sebelum refetch, atau ubah `refetchType` menjadi `'none'` agar data baru hanya di-fetch saat komponen tersebut benar-benar aktif/dilihat oleh user.
9. Fungsi `select` dieksekusi **sesudah** data asli disimpan ke dalam Query Cache internal. Query Cache selalu menyimpan data mentah dari server, sementara komponen hanya menerima turunan hasil transformasi `select`.
10. Secara default di TanStack Query v5, mutasi akan terus berjalan di latar belakang hingga selesai (*fire-and-forget* pada level promise). Callback `onSuccess` atau `onError` pada hook level komponen mungkin tidak terpicu jika komponen sudah unmounted, tetapi callback pada `MutationCache` global tetap dieksekusi.

#### Solusi Bagian C
11. Buat custom hook wrapper mutasi yang membuat `idempotencyKey` (UUIDv4) yang di-generate pada saat tombol pertama kali diklik dan diikat ke lifecycle mutasi. Sisipkan header `Idempotency-Key: <UUID>` pada request HTTP. Selain itu, periksa status mutasi menggunakan helper `useIsMutating({ mutationKey })` untuk menonaktifkan tombol secara global di level UI form.
12. Masalahnya adalah isolasi memori: setiap bundle micro-frontend membuat instance `new QueryClient()` terpisah yang tidak saling berbagi cache bus. Solusinya: Ekspor satu instance `QueryClient` tunggal ke objek global runtime (`window.__SHARED_QUERY_CLIENT__`) atau distribusikan invalidasi event antar aplikasi menggunakan `window.dispatchEvent(new CustomEvent('app:invalidate', { detail: { queryKey } }))`.
13. Memory leak pada polling interval biasanya disebabkan oleh:
    1. Callback polling yang membuat closure terhadap objek besar yang tidak pernah dilepas.
    2. Kegagalan Garbage Collector karena query observer tidak di-unsubscribe saat unmount.
    3. Structural sharing terus memegang referensi ke objek nested lama yang terus membesar (misal: array histori yang membengkak).
    *Solusi*: Gunakan Chrome DevTools Heap Snapshot, periksa retainers dari `QueryObserver`, pastikan array respons dari polling di-slice atau di-clear, dan setel batas retensi log secara eksplisit.

---

### 16. Summary

1. **Arsitektur Enterprise Memisahkan State Secara Tegas**: Batasi penggunaan global client store (Zustand/Redux) hanya untuk state UI murni yang sinkron dan ephemeral. Serahkan seluruh sinkronisasi data server ke query cache machine.
2. **Kekuatan Internal TanStack Query**: Penggunaan Observer Pattern independen yang dijembatani oleh `useSyncExternalStore` menjamin konkurensi React 18/19 aman tanpa UI tearing, sementara *Structural Sharing* melindungi aplikasi dari degradasi performa render.
3. **Kematangan Optimistic Engine**: Implementasi optimistik tingkat produksi menuntut siklus tiga lapis yang disiplin: **Cancel Ongoing Queries** $\rightarrow$ **Snapshot for Rollback** $\rightarrow$ **Authoritative Revalidation (`onSettled`)**.
4. **Sinkronisasi Terpadu**: Kombinasi arsitektur Event-Driven (SSE/WS) dengan Cache Invalidation Graph menghasilkan sistem frontend enterprise yang *real-time*, hemat bandwidth, dan konsisten secara deterministik.