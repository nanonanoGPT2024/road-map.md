# BAB 06: State Management Skala Besar
## MODULE 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Internal Arsitektur Pinia & Vue Reactivity Core**: Membedah bagaimana `effectScope`, `reactive()`, dan `Proxy` bekerja di balik layar Pinia untuk mengelola state global tanpa menyebabkan memory leak.
2. **Merancang Dynamic & Federated Store Architecture**: Mengimplementasikan registrasi store secara dinamis (code-split stores) untuk aplikasi berskala enterprise, modular monolith, maupun micro-frontend.
3. **Membangun Advanced Pinia Plugins**: Mengembangkan plugin kustom tingkat lanjut untuk state persistence terenkripsi, sinkronisasi state lintas tab/window via `BroadcastChannel`, dan action telemetry/auditing.
4. **Mengeksekusi Strategi Optimistic UI Updates & Rollback Engine**: Mengelola mutasi data asinkronus berlatensi tinggi dengan jaminan konsistensi data melalui skema rollback otomatis saat terjadi network error.
5. **Mengisolasi SSR State Contamination**: Mengonfigurasi Pinia pada arsitektur Server-Side Rendering (Nuxt/Custom SSR Node.js engine) untuk mencegah kebocoran state antarsesi pengguna (*cross-request state leakage*).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **TypeScript Tingkat Lanjut**: Generic constraints, Conditional Types, Template Literal Types, dan Type Mappings.
- **Vue 3 Reactivity System Internals**: Pemahaman tentang `Ref`, `Reactive`, `ComputedRef`, `effectScope`, dan siklus hidup dependency tracking (`track` & `trigger`).
- **Dasar State Management Pinia**: Sintaks dasar Setup Store vs Option Store, getters, dan actions standar.
- **Protokol Web Modern**: Dasar kerja Web Worker, `BroadcastChannel` API, dan `localStorage`/`IndexedDB`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Anatomi Internal Pinia: Di Balik Abstraksi Store
Pinia bukan sekadar wrapper tipis di atas objek `reactive()`. Pinia mengisolasi setiap instance store ke dalam struktur `EffectScope` terdedikasi yang diikat ke root aplikasi Vue melalui instance `Pinia` (diinjeksikan via provide/inject).

```
                      +---------------------------------------+
                      |             App Instance              |
                      +---------------------------------------+
                                          |
                                    provides Pinia
                                          v
                      +---------------------------------------+
                      |            Pinia Root State           |
                      |   pinia._s = Map<string, Store>()     |
                      |   pinia.state = Ref<Record<id, State>>|
                      +---------------------------------------+
                                          |
            +-----------------------------+-----------------------------+
            |                                                           |
            v                                                           v
+-----------------------+                                   +-----------------------+
|  Store Instance: "A"  |                                   |  Store Instance: "B"  |
|  - scope: EffectScope |                                   |  - scope: EffectScope |
|  - state: reactive()  |                                   |  - state: reactive()  |
|  - actions: wrapped   |                                   |  - actions: wrapped   |
+-----------------------+                                   +-----------------------+
            |                                                           |
      track/trigger                                               track/trigger
            v                                                           v
+-----------------------------------------------------------------------------------+
|                            Vue Reactivity Engine                                  |
|         Dep Graph -> ReactiveEffect -> Scheduler -> DOM Update Batching          |
+-----------------------------------------------------------------------------------+
```

1. **Root State Consolidation**:
   Setiap store yang dibuat tidak berdiri sendiri secara terfragmentasi. Pinia menyimpan seluruh state pohon aplikasi di dalam single reactive object `pinia.state.value[storeId]`. Ini memfasilitasi SSR hydration dan Time-Travel Debugging (Vue DevTools).
2. **Lifecycle Scoping via `effectScope(true)`**:
   Ketika store didefinisikan menggunakan Setup Store Syntax (`defineStore('id', () => { ... })`), Pinia mengeksekusi factory function di dalam `effectScope(true)`. Parameter `true` menandakan bahwa scope ini adalah *detached scope*. Artinya, siklus hidup reactivity (seperti `computed` atau `watch` di dalam store) tidak akan terbunuh ketika komponen pemanggil pertama kali di-*unmount*. Store hidup selama instance Pinia hidup.
3. **Action Interception & Patches**:
   Setiap pemanggilan action dibungkus oleh mekanisme callback internal (`actionSubscribers`). Ketika action dieksekusi, Pinia membuat context execution:
   ```typescript
   // Representasi pseudo-kode internal Pinia
   function wrapAction(name, action) {
     return function (...args) {
       // trigger hooks: before
       const afterCallbacks = []
       const onErrorCallbacks = []
       triggerSubscriptions(actionSubscribers, { name, store, args, after, onError })
       
       return Promise.resolve()
         .then(() => action.apply(this, args))
         .then((res) => {
           // trigger hooks: after
           return res
         })
         .catch((error) => {
           // trigger hooks: error
           throw error
         })
     }
   }
   ```

#### B. Dynamic Store Registration & Code Splitting
Dalam modular enterprise frontend (misal: dashboard dengan 50 sub-modul), memuat seluruh store saat bootstrap aplikasi adalah anti-pattern. Pinia secara native mendukung dynamic store registration.
Jika store diimpor menggunakan dynamic `import()`, Pinia tidak akan mendaftarkan state-nya ke `pinia.state` sampai fungsi `useSomeStore()` dipanggil untuk pertama kali. 

Saat dipanggil:
- Pinia memeriksa apakah instance `storeId` sudah ada di `pinia._s` (Store Map).
- Jika belum, Pinia menginisialisasi `effectScope`, mengeksekusi fungsi setup, menempelkan reactive properties ke `pinia.state`, mengikat plugins, dan mengembalikannya sebagai proxy object.

---

### 4. Why & What

| Dimensi Arsitektur | Legacy Global EventBus / Ad-Hoc Reactivity | Vuex 4 (Legacy Vue 3) | Pinia Enterprise Pattern |
| :--- | :--- | :--- | :--- |
| **Type-Safety** | Nol. Berbasis string event dan payload untyped. | Terbatas. Butuh complex type-mapping, mutations string literals. | 100% Native TypeScript Inference. Tanpa boilerplate types. |
| **Dead Code Elimination** | Buruk. Event listeners sulit di-tree-shake. | Buruk. Single nested global state object dimuat di awal. | Ekselen. Dynamic stores di-split secara granular via chunking engine. |
| **SSR Safety** | Rentan Memory Leak & Cross-Request Pollution. | Rentan jika module state tidak di-reset per request. | Terisolasi per request secara native melalui lifecycle `app.use(pinia)`. |
| **Side Effects Handling** | Tidak terpusat, tracing mustahil saat race-condition. | Wajib via Actions (kompleksitas mutations vs actions). | Action terpadu dengan hook interceptors (`$onAction`) dan scope lifecycle. |

---

### 5. How (Workflow Detail)

Siklus Eksekusi Action & State Sync:
```
[User Interaction] -> [Dispatch Action]
                            |
                            v
               [$onAction: 'before' Subscriptions]
                            |
                            v
             [Execute Optimistic State Mutation]
                            |
            +---------------+---------------+
            |                               |
     (Network Success)               (Network Failure)
            |                               |
            v                               v
  [Confirm Final State]          [Trigger Rollback Mechanism]
            |                               |
            v                               v
 [$onAction: 'after' Hooks]      [$onAction: 'onError' Hooks]
            |                               |
            +---------------+---------------+
                            |
                            v
          [Notify BroadcastChannel Subscriptions]
                            |
                            v
        [External Windows / Tabs Re-hydrated]
```

1. **Interception**: Dispatching action memicu hook *before*, menyimpan *snapshot* state sebelumnya ke stack memory sementara.
2. **Optimistic Mutation**: State lokal langsung dimutasi seketika tanpa menunggu response I/O server.
3. **Execution**: Promise API dieksekusi secara asinkronus.
4. **Resolution/Rejection**:
   - Jika sukses: Snapshot dibersihkan, perubahan disebarkan ke tab lain melalui `BroadcastChannel`.
   - Jika gagal: Snapshot dikembalikan (*rollback*), sistem memicu error notification handler, dan UI kembali konsisten dengan server.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Perbankan Transaksional Terdistribusi
Bayangkan Pinia sebagai sistem pembukuan bank cabang enterprise:
- **`pinia.state`**: Brankas pusat data cadangan.
- **Store Instance**: Meja teller individu (tiap nasabah dilayani teller independen tanpa mengunci seluruh brankas).
- **`effectScope`**: Jam kerja operasional teller. Jika teller tutup, seluruh draft kerja yang belum tersimpan otomatis dibersihkan tanpa mengganggu teller lain.
- **Optimistic UI with Rollback**: Teller langsung mengeluarkan bukti transaksi sementara kepada nasabah, tetapi jika sistem kliring kluster pusat menolak (network failure), teller memiliki catatan koreksi otomatis (jurnal balik) untuk mengembalikan nominal saldo semula.

#### Diagram Relasi Memory & State Interception
```
+--------------------------------------------------------------------------+
| Browser Memory Space                                                     |
|                                                                          |
|  +--------------------------------------------------------------------+  |
|  | Window Tab A                                                       |  |
|  |  [Component] ---> [useOrderStore()]                                |  |
|  |                         |                                          |  |
|  |                         v                                          |  |
|  |                +------------------+                                |  |
|  |                | OrderStore Proxy |                                |  |
|  |                +------------------+                                |  |
|  |                   |        |                                       |  |
|  |     (Local Mutate)|        | (Action: createOrder)                 |  |
|  |                   v        v                                       |  |
|  |              +-------------------+                                 |  |
|  |              | Plugin: Broadcast |                                 |  |
|  |              +-------------------+                                 |  |
|  |                        |                                           |  |
|  +------------------------|-------------------------------------------+  |
|                           | BroadcastChannel('orders_channel')           |
|                           |                                              |
|  +------------------------|-------------------------------------------+  |
|  | Window Tab B           v                                           |  |
|  |              +-------------------+                                 |  |
|  |              | Plugin: Listener  |                                 |  |
|  |              +-------------------+                                 |  |
|  |                        |                                           |  |
|  |                        v                                           |  |
|  |                +------------------+                                |  |
|  |                | OrderStore Proxy |                                |  |
|  |                +------------------+                                |  |
|  |                         |                                          |  |
|  |                         v                                          |  |
|  |                 [DOM Auto-Updates]                                 |  |
|  +--------------------------------------------------------------------+  |
+--------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Native Setup Store dengan Type-Safe Actions
File: `src/stores/counter.store.ts`
```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useCounterStore = defineStore('counter', () => {
  // State
  const count = ref<number>(0)
  
  // Getters
  const doubleCount = computed<number>(() => count.value * 2)

  // Actions
  function increment(): void {
    count.value++
  }

  function $reset(): void {
    count.value = 0
  }

  return { count, doubleCount, increment, $reset }
})
```

#### Practical Example: Production-Ready Optimistic Store dengan Rollback Engine
File: `src/stores/order.store.ts`
```typescript
import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'

export interface OrderItem {
  id: string
  sku: string
  quantity: number
  price: number
}

export interface OrderState {
  items: OrderItem[]
  status: 'idle' | 'syncing' | 'error'
  lastError: string | null
}

export const useOrderStore = defineStore('orders', () => {
  const items = ref<OrderItem[]>([])
  const status = ref<'idle' | 'syncing' | 'error'>('idle')
  const lastError = shallowRef<string | null>(null)

  // Action dengan Built-in Optimistic Reconciliation
  async function addItemOptimistic(newItem: OrderItem): Promise<void> {
    // 1. Simpan checkpoint snapshot untuk rollback
    const previousSnapshot = structuredClone(items.value)
    
    // 2. Terapkan mutasi optimistik ke state lokal seketika
    items.value.push(newItem)
    status.value = 'syncing'
    lastError.value = null

    try {
      // 3. Network Transport Execution
      const response = await fetch('/api/v1/orders/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newItem),
      })

      if (!response.ok) {
        throw new Error(`Server responded with HTTP ${response.status}: ${response.statusText}`)
      }

      // Ambil payload resmi dari server jika ID digenerasi backend
      const persistedItem: OrderItem = await response.json()
      
      // Rekonsiliasi ID lokal dengan server
      const targetIndex = items.value.findIndex(i => i.id === newItem.id)
      if (targetIndex !== -1) {
        items.value[targetIndex] = persistedItem
      }

      status.value = 'idle'
    } catch (err: unknown) {
      // 4. Rollback Engine diaktifkan
      items.value = previousSnapshot
      status.value = 'error'
      lastError.value = err instanceof Error ? err.message : 'Unknown communication error'
      
      // Propagasi error agar caller dapat memicu UI alerts
      throw err
    }
  }

  return {
    items,
    status,
    lastError,
    addItemOptimistic,
  }
})
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Multi-Tenant Real-time Analytics State Synchronization
**Konteks**: Aplikasi dashboard finansial B2B diakses oleh multi-user dalam satu perusahaan. Saat satu analis mengubah konfigurasi filter atau model kalkulasi portofolio, perubahan harus disinkronkan ke seluruh tab browser dan rekan satu tenant secara real-time via WebSockets, dengan kemampuan fallback ke IndexedDB jika koneksi terputus.

#### Solusi Arsitektur: Dynamic Pinia Store Plugin dengan BroadcastChannel & IndexedDB
File: `src/plugins/pinia-realtime-sync.ts`
```typescript
import { PiniaPluginContext } from 'pinia'

export interface SyncOptions {
  channelName?: string
  excludedStores?: string[]
}

export function createCrossTabSyncPlugin(options: SyncOptions = {}) {
  const channelName = options.channelName ?? 'enterprise_app_sync_bus'
  const excludedStores = new Set(options.excludedStores ?? [])

  return (context: PiniaPluginContext) => {
    const { store } = context

    if (excludedStores.has(store.$id)) {
      return
    }

    const broadcast = new BroadcastChannel(`${channelName}_${store.$id}`)

    // 1. Kirim perubahan lokal ke tab lain
    store.$subscribe((mutation, state) => {
      // Mutasi hanya dibroadcast jika bukan berasal dari incoming cross-tab event
      if (mutation.payload?.__isCrossTabSync) {
        return
      }

      broadcast.postMessage({
        type: 'STATE_MUTATION',
        storeId: store.$id,
        mutationType: mutation.type,
        payload: mutation.payload,
        fullState: state,
        timestamp: Date.now(),
      })
    }, { detached: true })

    // 2. Terima perubahan dari tab lain
    broadcast.onmessage = (event: MessageEvent) => {
      const data = event.data
      if (data && data.type === 'STATE_MUTATION' && data.storeId === store.$id) {
        // Terapkan state secara patch langsung untuk menghindari trigger rekursif tak terbatas
        store.$patch((state) => {
          Object.assign(state, data.fullState)
        })
      }
    }

    // 3. Resource Cleanup saat store dilepas
    const originalDispose = store._customDispose
    store._customDispose = () => {
      broadcast.close()
      if (originalDispose) originalDispose()
    }
  }
}
```

File: `src/main.ts` (Integrasi Plugin)
```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { createCrossTabSyncPlugin } from './plugins/pinia-realtime-sync'

const app = createApp(App)
const pinia = createPinia()

pinia.use(createCrossTabSyncPlugin({
  excludedStores: ['ephemeralSessionUi'],
}))

app.use(pinia)
app.mount('#app')
```

---

### 9. Trade-offs

| Parameter | Fine-Grained Modular Stores | Monolithic Single Store Pattern | Local Component State (Provide/Inject) |
| :--- | :--- | :--- | :--- |
| **Runtime Performance** | **Tinggi**: Re-evaluasi hanya terjadi pada subscriber store individual. | **Sedang**: Rentan unnecessary compute jika getter menyentuh root state. | **Maksimal**: Mengeliminasi overhead runtime Pinia context. |
| **Latency Network/Sync** | **Rendah**: Granular sync payload via selective WebSocket/Broadcast. | **Tinggi**: Mengirim representasi state yang terlalu besar عبر network. | **Nol**: State terisolasi secara internal di memori komponen. |
| **Scalability (Team & Code)** | **Ekselen**: Domain-Driven Design (DDD), tiap domain tim memiliki store sendiri. | **Buruk**: Bottleneck merge conflict, rentan dependency hell. | **Terbatas**: State sharing antarcabang pohon DOM sangat rapuh. |
| **Cost & Bundle Overhead** | **Optimal**: Dynamic lazy-loaded chunks dipecah otomatis oleh Vite. | **Sub-optimal**: Bundle besar di-*load* di muka (upfront loading). | **Paling Murah**: Tidak ada library dependensi eksternal. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kehilangan Reaktivitas Karena Destructuring Langsung
*Problem*: Mengambil properti state dari Pinia menggunakan sintaks ES6 destructuring memutus tautan `Proxy`.
```typescript
// FATAL ERROR: Reaktivitas putus seketika!
const store = useUserStore()
const { username, isAuthenticated } = store 
```
*Solution*: Gunakan helper resmi `storeToRefs`.
```typescript
import { storeToRefs } from 'pinia'

const store = useUserStore()
// AMAN: Properti dibungkus kembali menjadi instance Ref
const { username, isAuthenticated } = storeToRefs(store)
// Actions tetap dapat di-destructure secara langsung tanpa helper
const { login, logout } = store 
```

#### 2. Cross-Request State Leakage pada Server-Side Rendering (SSR)
*Problem*: Menginisialisasi store di lingkup global file level (di luar factory request Nuxt/SSR), menyebabkan request User B melihat data User A.
```typescript
// FATAL ERROR DI SSR: Mengakses store di luar lifecycle komponen/handler request
const store = useUserStore() // Dieksekusi saat module evaluating, shared di seluruh thread Node.js!

export default defineComponent({ /* ... */ })
```
*Solution*: Selalu inisialisasi Pinia per-request dan panggil `useStore()` hanya di dalam lifecycle fungsi (`setup()`, lifecycle hooks, atau Pinia plugin scope).

#### 3. Memory Leak Akibat `$subscribe` yang Terisolasi Manual
*Problem*: Menambahkan `$subscribe` atau `$onAction` di dalam komponen tanpa mematikan langganan saat unmount, atau menggunakan `{ detached: true }` tanpa tracking lifecycle.
*Solution*: Jika didaftarkan di dalam `setup()`, Pinia otomatis membersihkan subscriber saat komponen di-*unmount*. Jika dibuat di luar komponen atau via detached scope, tangani dereferensiasi pembersihan secara eksplisit menggunakan native `scope.stop()` atau simpan handler return value untuk di-dispose.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan Setup Store Syntax**: Memungkinkan integrasi native composable functions di dalam store (Vue Use, native composables).
- [ ] **Strict Typing dengan Zero `any`**: Definisikan interface eksplisit untuk setiap return value state dan actions.
- [ ] **Terapkan Action Hydration Safeguard**: Hindari *cascading network calls* dengan memeriksa apakah data sudah terisi sebelum melakukan refetch (`if (items.value.length > 0) return`).
- [ ] **Gunakan `shallowRef` untuk Payload Besar**: Jika store memuat dataset analitik ratusan ribu baris yang bersifat immutable per-fetch, gunakan `shallowRef` alih-alih `ref` untuk memangkas overhead pembuatan deep-proxy.
- [ ] **Enkripsi Local Storage Sync**: Jangan simpan data PII (Personally Identifiable Information) dalam format JSON mentah di Web Storage; gunakan encryption layer (misal: AES-GCM via Web Crypto API) pada plugin storage.
- [ ] **Strict Atomic Patches**: Hindari mutasi langsung pada nested object deep hierarchy dari komponen (`store.a.b.c = 2`). Bungkus mutasi di dalam action atau `$patch` agar terlacak di DevTools history.

---

### 12. Hands-on Practice

Tulis dan susun modul enterprise di dalam folder: `hands-on/m02/`

#### Struktur Direktori
```
hands-on/m02/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── src/
    ├── main.ts
    ├── App.vue
    ├── plugins/
    │   └── auditLog.plugin.ts
    └── stores/
        └── inventory.store.ts
```

#### Langkah 1: Siapkan `hands-on/m02/package.json`
```json
{
  "name": "enterprise-pinia-architecture",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build"
  },
  "dependencies": {
    "pinia": "^2.1.7",
    "vue": "^3.4.15"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.3",
    "typescript": "^5.3.3",
    "vite": "^5.0.12",
    "vue-tsc": "^1.8.27"
  }
}
```

#### Langkah 2: Buat Action Auditing Plugin
File: `hands-on/m02/src/plugins/auditLog.plugin.ts`
```typescript
import { PiniaPluginContext } from 'pinia'

export interface AuditEntry {
  storeId: string
  actionName: string
  timestamp: string
  args: unknown[]
  status: 'SUCCESS' | 'FAILED'
  executionTimeMs: number
  error?: string
}

export function createAuditLogPlugin() {
  return ({ store }: PiniaPluginContext) => {
    store.$onAction(({ name, store, args, after, onError }) => {
      const startTime = performance.now()

      after((result) => {
        const duration = performance.now() - startTime
        const log: AuditEntry = {
          storeId: store.$id,
          actionName: name,
          timestamp: new Date().toISOString(),
          args,
          status: 'SUCCESS',
          executionTimeMs: parseFloat(duration.toFixed(2)),
        }
        console.info(`[PINIA AUDIT LOG] [SUCCESS] ${store.$id}.${name} -> ${duration.toFixed(2)}ms`, log)
      })

      onError((error) => {
        const duration = performance.now() - startTime
        const log: AuditEntry = {
          storeId: store.$id,
          actionName: name,
          timestamp: new Date().toISOString(),
          args,
          status: 'FAILED',
          executionTimeMs: parseFloat(duration.toFixed(2)),
          error: error instanceof Error ? error.message : String(error),
        }
        console.error(`[PINIA AUDIT LOG] [FAILED] ${store.$id}.${name} -> ${duration.toFixed(2)}ms`, log)
      })
    })
  }
}
```

#### Langkah 3: Implementasikan Store dengan Deep Reactivity & Error Handling
File: `hands-on/m02/src/stores/inventory.store.ts`
```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface ProductItem {
  id: string
  name: string
  stock: number
  unitPrice: number
}

export const useInventoryStore = defineStore('inventory', () => {
  const products = ref<ProductItem[]>([
    { id: 'SKU-001', name: 'Server Rack Enterprise 42U', stock: 12, unitPrice: 1200 },
    { id: 'SKU-002', name: 'Managed Switch L3 48-Port', stock: 25, unitPrice: 850 },
  ])
  
  const isUpdating = ref<boolean>(false)

  const totalValuation = computed<number>(() => {
    return products.value.reduce((acc, curr) => acc + (curr.stock * curr.unitPrice), 0)
  })

  async function adjustStock(skuId: string, delta: number): Promise<void> {
    isUpdating.value = true
    
    // Simulate Network Latency
    await new Promise((resolve) => setTimeout(resolve, 600))

    const target = products.value.find((p) => p.id === skuId)
    if (!target) {
      isUpdating.value = false
      throw new Error(`Inventory item ${skuId} not found in database.`)
    }

    if (target.stock + delta < 0) {
      isUpdating.value = false
      throw new Error(`Insufficient stock for ${skuId}. Current: ${target.stock}, Requested delta: ${delta}`)
    }

    target.stock += delta
    isUpdating.value = false
  }

  return {
    products,
    isUpdating,
    totalValuation,
    adjustStock,
  }
})
```

#### Langkah 4: Hubungkan App ke View
File: `hands-on/m02/src/App.vue`
```vue
<template>
  <main style="font-family: sans-serif; padding: 2rem;">
    <h1>Enterprise Inventory State Monitor</h1>
    <div style="margin-bottom: 1rem; padding: 1rem; background: #eee; border-radius: 4px;">
      <strong>Total Asset Valuation:</strong> ${{ inventory.totalValuation.toLocaleString() }}
    </div>

    <table border="1" cellpadding="8" style="width: 100%; border-collapse: collapse;">
      <thead>
        <tr>
          <th>SKU</th>
          <th>Name</th>
          <th>Stock</th>
          <th>Unit Price</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in products" :key="item.id">
          <td>{{ item.id }}</td>
          <td>{{ item.name }}</td>
          <td>{{ item.stock }}</td>
          <td>${{{ item.unitPrice }}}</td>
          <td>
            <button :disabled="inventory.isUpdating" @click="handleStockChange(item.id, 1)">+ Add</button>
            <button :disabled="inventory.isUpdating" @click="handleStockChange(item.id, -1)">- Dec</button>
            <button :disabled="inventory.isUpdating" @click="handleStockChange(item.id, -9999)">Trigger Fault</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="inventory.isUpdating" style="color: blue;">Menyimpan status ke ledger...</p>
    <p v-if="uiError" style="color: red; font-weight: bold;">Error: {{ uiError }}</p>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useInventoryStore } from './stores/inventory.store'

const inventory = useInventoryStore()
const { products } = storeToRefs(inventory)
const uiError = ref<string | null>(null)

async function handleStockChange(skuId: string, delta: number) {
  uiError.value = null
  try {
    await inventory.adjustStock(skuId, delta)
  } catch (err: unknown) {
    uiError.value = err instanceof Error ? err.message : 'Execution failed'
  }
}
</script>
```

#### Langkah 5: Bootstrap Entry Point
File: `hands-on/m02/src/main.ts`
```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { createAuditLogPlugin } from './plugins/auditLog.plugin'

const app = createApp(App)
const pinia = createPinia()

pinia.use(createAuditLogPlugin())

app.use(pinia)
app.mount('#app')
```

---

### 13. Exercise

#### Level Easy
Buat store `useThemeStore` dengan state `theme` ('light' | 'dark'). Tambahkan action `toggleTheme()` yang otomatis mengaplikasikan class `.dark` pada elemen `document.documentElement`.
*Batasan*: Wajib menggunakan Setup Store Syntax.

#### Level Medium
Buat custom Pinia plugin bernama `pinia-secure-storage`. Plugin ini harus menyinkronkan state store ke `sessionStorage` dengan enkripsi sederhana Base64 encoding. Ketika browser di-refresh, state pada store harus terhidrasi kembali (*hydrate*) secara otomatis dari storage.

#### Level Hard
Buat implementasi dynamic store bernama `useDocumentEditorStore(docId: string)`. Store ini harus terisolasi unik per `docId` (*dynamic multiton pattern*). Jika dua tab membuka ID dokumen yang berbeda, state keduanya tidak boleh tercampur. Buat mekanisme penghancuran (*teardown*) otomatis menggunakan `scope.stop()` jika dokumen ditutup untuk mengeliminasi memory leakage.

---

### 14. Challenge

**Skenario**: Anda memimpin arsitektur sistem state frontend untuk platform perdagangan derivatif crypto skala besar. Platform menerima update ticker harga order-book hingga 2.500 mutasi per detik melalui raw WebSocket stream.
**Tantangan**:
1. Rancang arsitektur Pinia Store yang mampu mengonsumsi data stream berkecepatan 2.500 TPS tanpa memblokir Main Thread (tanpa frame drops di bawah 60 FPS).
2. Terapkan strategi *batching & throttling update* menggunakan `requestAnimationFrame` dan struktur data `shallowRef`.
3. Komponen-komponen UI yang menampilkan harga agregat (volatilitas, high/low spread) harus diupdate secara reaktif menggunakan `computed`, tetapi tidak boleh dievaluasi ulang pada setiap pesan WebSocket individual.
4. Buat prototipe fungsional lengkap (store + throttler engine) yang mendemonstrasikan bahwa pemanggilan mutasi Pinia tetap stabil pada high-throughput stress testing.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (Pilihan Ganda)

1. Mengapa mendestrukturisasi store Pinia secara langsung (e.g., `const { count } = useStore()`) menyebabkan hilangnya reaktivitas?
   - A. Karena Pinia membekukan (freezes) semua objek setelah inisialisasi.
   - B. Properti di dalam store adalah JavaScript getter/Proxy yang binding dereferensinya terputus saat di-unpack ke variabel primitif lokal.
   - C. Pinia hanya mendukung pemanggilan method, bukan direct property access.
   - D. Browser engine secara otomatis membersihkan pointer memory destructuring.

2. API internal Vue 3 apa yang digunakan Pinia untuk mengontrol masa hidup (*lifecycle*) seluruh komputasi dan watcher di dalam store?
   - A. `provide / inject`
   - B. `watchEffect`
   - C. `effectScope`
   - D. `reactiveToRaw`

3. Apa perbedaan mendasar antara implementasi SSR di Pinia dibandingkan Vuex versi lama?
   - A. Pinia tidak mendukung SSR sama sekali.
   - B. Pinia membutuhkan inisialisasi server per-thread terpisah.
   - C. Pinia mengisolasi instance root state pada level request melalui `createPinia()` di factory function, mencegah pencemaran data antar-klien.
   - D. Pinia menyimpan state SSR di cookies alih-alih memory context.

4. Kapan waktu yang tepat menggunakan `shallowRef` di dalam Pinia state?
   - A. Saat menyimpan tipe data primitif seperti `boolean` atau `string`.
   - B. Saat memegang data berukuran sangat besar (ribuan entri array/objek bertingkat) yang digantikan secara utuh saat mutasi, guna menghindari overhead wrapping proxy rekursif.
   - C. Ketika store membutuhkan auto-sync ke LocalStorage.
   - D. Ketika store menggunakan plugin DevTools.

5. Di mana letak penyimpanan terpusat seluruh child-state store di dalam instance Pinia?
   - A. `pinia._s`
   - B. `pinia.state.value`
   - C. `window.__PINIA_GLOBAL_STATE__`
   - D. `pinia.modules`

---

#### B. Pertanyaan Intermediate (Pilihan Ganda)

6. Apa yang terjadi jika sebuah action di dalam store memodifikasi state, sementara di saat yang sama terdapat listener `$subscribe` terdaftar dengan opsi `{ detached: true }`?
   - A. Subscriber akan otomatis dihentikan paksa saat komponen pembuat di-*unmount*.
   - B. Subscriber akan tetap aktif mendengarkan perubahan mutasi store sepanjang siklus hidup aplikasi browser, meskipun komponen asal tempat pendefinisian telah hancur.
   - C. Terjadi error lemparan `CircularDependencyException`.
   - D. Mutasi dibatalkan secara otomatis karena status detached mengunci state.

7. Perhatikan kode berikut:
   ```typescript
   export const useDataStore = defineStore('data', () => {
     const items = ref([])
     return { items }
   })
   ```
   Bagaimana cara mereset state di atas jika store menggunakan Setup Syntax?
   - A. Memanggil `useDataStore().$reset()` bawaan Pinia.
   - B. Memanggil `useDataStore().$clear()`.
   - C. Pinia tidak menyediakan implementasi bawaan `$reset()` untuk Setup Store, sehingga pengembang harus membuat dan mengembalikan fungsi reset kustom sendiri di dalam closure.
   - D. Mengubah pointer array dengan `items = []`.

8. Dalam pembuatan custom plugin Pinia, bagaimana cara menghentikan propagasi mutasi agar tidak memicu infinite-loop saat melakukan sinkronisasi dua arah via WebSocket?
   - A. Menggunakan method `store.$stopPropagation()`.
   - B. Menyematkan metadata custom atau flag pada objek mutasi payload (e.g. `mutation.payload.__isRemote`) dan memeriksanya di subscription listener.
   - C. Menutup koneksi socket setiap kali payload diterima.
   - D. Membungkus mutasi di dalam blok `setTimeout(..., 0)`.

9. Mengapa `storeToRefs()` mengabaikan actions dan hanya mengekstrak `ref` serta `computed` dari store instance?
   - A. Karena TypeScript tidak mengizinkan pemetaan fungsi ke dalam generic record.
   - B. Karena actions adalah fungsi murni yang tidak memerlukan reaktivitas `Ref`, dan dapat di-destrukturisasi secara langsung tanpa kehilangan referensi konteks.
   - C. Karena actions tidak dapat diakses di template.
   - D. Untuk membatasi memory consumption pada virtual DOM.

10. Apa kegunaan callback `after()` dan `onError()` yang disediakan oleh parameter context di dalam `$onAction` subscription?
    - A. Untuk menangani middleware Express pada Node.js backend.
    - B. Untuk menyuntikkan interceptor pelacakan telemetri, auditing, atau state-rollback yang dieksekusi secara terjamin saat Promise action selesai atau gagal dilempar (*rejected*).
    - C. Untuk mengubah action synchronous menjadi fully asynchronous.
    - D. Untuk meregister dynamic reducer layaknya arsitektur Redux.

---

#### C. Skenario Kasus Produksi (Analisis Arsitektur)

11. **Skenario Kasus 1: Memory Leak pada Dashboard Multi-Tenant**
    Aplikasi Vue 3 Enterprise mencatat penambahan penggunaan RAM sebesar ~15MB setiap kali operator berpindah antardokumen analitik. Setelah ditelusuri via Chrome DevTools Heap Snapshot, terdapat ribuan instance `EffectScope` dan array subscriber yang tersangkut di memory retention tree pada path `pinia._s`.
    *Pertanyaan*: Berdasarkan internal arsitektur Pinia, analisislah kemungkinan penyebab utamanya dan berikan solusi arsitektural konkret untuk memperbaiki memory leak tersebut.

12. **Skenario Kasus 2: Race Condition pada Data Fetching Konkuren**
    Pengguna berpindah tab navigasi secara cepat: Tab "All Transactions" (Request A - latensi 800ms) diklik, lalu 100ms kemudian mengklik Tab "Pending Transactions" (Request B - latensi 200ms). Di UI, data yang tertampil akhirnya adalah Request A, padahal navigasi aktif berada di Tab "Pending Transactions".
    *Pertanyaan*: Bagaimana Anda menyusun strategi penanganan state di dalam action Pinia untuk menyelesaikan masalah *stale response out-of-order execution* ini secara elegan menggunakan standar Web API?

13. **Skenario Kasus 3: SSR Cross-Session Leakage di Nuxt 3**
    Dalam sistem perbankan internet berbasis Nuxt 3, Nasabah B secara berkala mendapati nama profil dan balance Nasabah A terpampang di header dashboard saat server mengalami beban trafik puncak.
    *Pertanyaan*: Bedah secara teknis bagaimana insiden keamanan fatal ini dapat terjadi pada interaksi Node.js thread context dengan Pinia, serta apa konfigurasi/pola coding yang melanggar arsitektur SSR tersebut.

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Kunci Jawaban Basic & Intermediate
1. **B** - Binding getter Proxy putus jika di-destructure ke primitive value.
2. **C** - `effectScope` mengelola seluruh dynamic reactivity collection.
3. **C** - Isolasi per-request context mencegah kebocoran antar pengguna.
4. **B** - Menghindari wrapping jutaan nested proxy nodes via `shallowRef`.
5. **B** - State root dikonsolidasikan pada ref internal `pinia.state.value`.
6. **B** - Flag detached melepaskan subscriber dari lifecycle scope pemanggilnya.
7. **C** - Setup Store syntax tidak memiliki default `$reset()` bawaan (hanya Option Store yang memilikinya).
8. **B** - Metadata tracking payload menghindari circular loop re-broadcast.
9. **B** - Action adalah method murni yang tidak membutuhkan wrapper proxy ref.
10. **B** - Interceptor hooks untuk fine-grained action auditing & error rollback.

#### Panduan Jawaban Skenario Kasus Produksi

11. **Analisis Skenario 1**:
    - *Penyebab*: Aplikasi kemungkinan mendefinisikan dynamic store baru dengan unique ID secara runtime (misal: `useDocStore(docId)()`) menggunakan isolated `effectScope(true)` atau mendaftarkan `$subscribe` dengan `{ detached: true }` tanpa pernah memanggil mekanisme cleanup (`store._customDispose()` atau deregistrasi dari `pinia._s.delete(storeId)`). Akibatnya, Pinia terus menahan pointer referensi store di root map `_s`.
    - *Solusi Arsitektur*: Gunakan satu store dokumen statis dengan parameter ID aktif, atau jika wajib menggunakan isolated dynamic store, implementasikan lifecycle unmount di komponen terkait: panggil method cleanup yang mengeksekusi `scope.stop()` internal dan menghapus reference store dari `pinia._s` dan `pinia.state.value[id]`.

12. **Analisis Skenario 2**:
    - *Penyebab*: Terjadi *race condition* akibat resolusi network I/O yang bersifat non-deterministik (*out-of-order execution*). Request A selesai lebih lambat dibanding Request B, menimpa state akhir store.
    - *Solusi Arsitektur*: Manfaatkan native `AbortController` di dalam Pinia store. Di action fetching, simpan instance controller yang sedang berjalan. Saat action dipanggil kembali sebelum request sebelumnya selesai, panggil `currentController.abort()` untuk membatalkan sinyal request lama sebelum instansiasi fetch baru dijalankan. Alternatif lain: gunakan request transaction id token untuk mencocokkan apakah response yang tiba sesuai dengan ID eksekusi paling mutakhir.

13. **Analisis Skenario 3**:
    - *Penyebab*: Pengembang mendeklarasikan/menginstansiasi store instance di luar lifecycle eksekusi context request (misal: di top-level script file sebagai global singleton variable, atau di custom shared cache object). Pada arsitektur Node.js SSR, modul file hanya di-*evaluate* satu kali dan memorinya di-*share* ke seluruh concurrent requests. Akibatnya, `pinia.state` terkontaminasi silang antar thread event-loop execution.
    - *Solusi Arsitektur*: Pastikan `createPinia()` selalu dijalankan di dalam SSR request factory lifecycle (di Nuxt di-handle otomatis via NuxtApp context). Jangan pernah mengekspor instance `const store = useStore()` di luar method `defineComponent`, `setup()`, atau handler middleware SSR yang terikat pada instance context request spesifik.

---

### 16. Summary

State management skala besar pada ekosistem Vue 3 modern menuntut pemahaman mendalam tentang **Vue Reactivity Engine**, khususnya peran `effectScope` dan internal `Proxy`. Pinia dirancang bukan hanya sebagai pengganti Vuex yang lebih ringkas, tetapi sebagai arsitektur modular yang memfasilitasi granular tree-shaking, isolasi state berbasis domain, dan kemudahan ekstensibilitas melalui sistem plugin.

Kunci keandalan sistem enterprise terletak pada:
1. **Prediktabilitas State**: Penggunaan setup stores dengan pengetikan TypeScript yang ketat tanpa mengorbankan reaktivitas melalui pemahaman mekanisme `storeToRefs`.
2. **Resiliensi Jaringan & Transaksi**: Pemanfaatan *Optimistic UI Updates* dengan rollback engine untuk menjamin UI tetap responsif dengan konsistensi data yang terverifikasi.
3. **Isolasi Lingkungan**: Pemahaman boundaries siklus hidup memori pada browser (mencegah leak detached subscribers) dan isolasi server context pada SSR (mencegah *cross-request contamination*).