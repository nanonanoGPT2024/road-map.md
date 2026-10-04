# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran:** Frontend and Mobile Engineering
*   **Kategori:** 03-Frontend-and-Mobile
*   **Kurikulum:** Vue.js Ecosystem Core & Architecture
*   **Bab:** 06 — State Management & Data Flow Architecture
*   **Modul:** 01 — State Management Skala Besar (Pinia)
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** Vue 3 Composition API (`ref`, `reactive`, `computed`, `effectScope`), TypeScript Generics & Type Narrowing, Asynchronous Control Flow, Vue Router Lifecycle.

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta ajar memiliki kompetensi tingkat produksi untuk:

1.  **Mendekomposisi State Terdistribusi:** Merancang arsitektur global state multi-store yang *decoupled*, *domain-driven*, dan *type-safe* menggunakan Setup Stores Pinia.
2.  **Menguasai Reaktivitas Internal Pinia:** Menjelaskan secara mekanistik bagaimana Pinia membungkus Vue 3 Reactivity Engine melalui `effectScope`, proxy traps, serta implikasi dereferensi state via `storeToRefs`.
3.  **Membangun Ekosistem Plugin Kustom:** Mengimplementasikan plugin Pinia tingkat lanjut untuk sinkronisasi `BroadcastChannel` (multi-tab sync), persistensi terenkripsi, dan automasi *undo/redo transaction log*.
4.  **Mitigasi Bottleneck Performa & Kebocoran Memori:** Mencegah kebocoran memori akibat retensi `effectScope` yang tidak ter-garbage-collect, serta mengoptimalkan reaktivitas data berukuran besar menggunakan `markRaw` dan `shallowRef`.
5.  **Menegakkan Pola Arsitektur Skala Besar:** Mengimplementasikan orkestrasi *Cross-Store Composition*, isolasi Server-Side Rendering (SSR) state hydration, dan *enterprise-grade observability* berbasis plugin telemetri.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam aplikasi monolitik frontend skala enterprise, kesalahan terbesar arsitek perangkat lunak adalah memperlakukan global store sebagai "database global tanpa skema". Mental model yang benar memandang global state sebagai **State Machine Terdistribusi yang Terikat Siklus Hidup Runtime**.

```
+-------------------------------------------------------------------------+
|                  MENTAL MODEL: LOCAL VS GLOBAL STATE                    |
+-------------------------------------------------------------------------+
|                                                                         |
|  [Ephemeral Component State]                                            |
|  - UI-only concerns (isDropdownOpen, hoverState, activeTab)             |
|  - Scope: Mati saat unmount. Gunakan: ref(), reactive() lokal.          |
|                                                                         |
|  [Server Cache State]                                                   |
|  - Data mirror dari backend (Users, Transactions, Entities)             |
|  - Scope: Di-fetch, di-cache, di-invalidasi. Gunakan: TanStack Query/SWR |
|                                                                         |
|  [Global Client State (PINIA)]                                          |
|  - Sync UI state antar domain terpisah, session, optimistic mutations   |
|  - Scope: Runtime session aplikasi. Gunakan: Pinia Setup Stores.        |
|                                                                         |
+-------------------------------------------------------------------------+
```

### Prinsip Utama Pergeseran Paradigma dari Vuex ke Pinia:
*   **Hilangkan Mutasi Berulang:** Mutasi dihilangkan secara fungsional. Action mengeksekusi mutasi langsung secara sinkron maupun asinkron. Keamanan tipe data tidak lagi terkompromi oleh magic string mutations.
*   **Store Bukanlah Monolit (Flat Architecture):** Berhenti membuat nested modules yang kaku. Pinia mendikte struktur *flat*, granular, dan modular. Satu store = satu bounded context domain.
*   **Store Adalah Composable Eksklusif:** Pahami bahwa store Pinia hakikatnya adalah *singleton composable* yang dibungkus oleh Vue `effectScope`. Kapan pun Anda memanggil `useUserStore()`, Anda mengeksekusi composable yang instansiasinya dijaga secara global oleh `pinia` instance plugin.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di balik kesederhanaan sintaks Pinia, terdapat alur kontrol berbasis reaktivitas Vue 3 yang mengelola siklus hidup dispatch action, langganan mutasi, dan plugin pipeline:

```
[ Vue Component / Composable ]
         |
         | 1. Memanggil Action / Mutasi State Langsung
         v
+-------------------------------------------------------------------+
| Pinia Action Proxy Layer                                          |
|  - Intersepsi via Action Subscriptions (store.$onAction)         |
|  - Eksekusi Hook 'before'                                         |
+-------------------------------------------------------------------+
         |
         | 2. Eksekusi Fungsi Action
         v
+-------------------------------------------------------------------+
| Pinia State Layer (Root EffectScope)                              |
|  - State dimutasi secara reaktif (ref / shallowRef)               |
|  - Emit Mutasi (store.$subscribe / Pinia Mutation Type)           |
+-------------------------------------------------------------------+
         |                                                 |
         | 3. State Berubah                                | 4. Trigger Plugins
         v                                                 v
+-----------------------------------+     +-------------------------+
| Computed Properties (Getters)    |     | Pinia Plugin Pipeline   |
|  - Re-evaluasi otomatis           |     |  - Persistence Eng      |
|  - Dependency tracking aktif     |     |  - Telemetry Logger     |
+-----------------------------------+     |  - Cross-tab Broadcaster|
         |                                +-------------------------+
         | 5. Trigger Re-render
         v
[ Vue Virtual DOM / Watchers ]
```

### Hubungan Root Injection, EffectScope, dan Store Registry:

```
                  +-----------------------------------+
                  |        App (Vue Instance)         |
                  +-----------------------------------+
                                    |
                             app.use(pinia)
                                    v
                  +-----------------------------------+
                  |          Pinia Instance           |
                  |  - _s: Map<string, Store>         |
                  |  - _e: EffectScope (Master)       |
                  |  - state: Ref<Record<string,any>> |
                  +-----------------------------------+
                       /            |            \
      Instansiasi Panggilan Pertama via useDomainStore()
                     /              |              \
                    v               v               v
            +---------------+ +---------------+ +---------------+
            | Store: 'auth' | | Store: 'cart' | |Store: 'order' |
            | - EffectScope | | - EffectScope | | - EffectScope |
            | - Proxy Store | | - Proxy Store | | - Proxy Store |
            +---------------+ +---------------+ +---------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Peran `effectScope`
Pinia memanfaatkan `effectScope(true)` (detached effect scope) di tingkat root. Hal ini krusial:
*   Ketika store dibuat di dalam komponen melalui `useStore()`, store tersebut **tidak boleh terikat** pada lifecycle unmount komponen pemanggil.
*   Jika diikat ke komponen pemanggil, ketika komponen di-unmount, semua watcher, computed, dan state tracking internal store akan di-dispose oleh Vue runtime.
*   Pinia melepaskan instansiasi store ke root `pinia._e` sehingga store tetap hidup sepanjang siklus aplikasi client berlangsung.

### 2. Bahaya Destrukturisasi & Solusi `storeToRefs`
Objek store yang dihasilkan Pinia adalah `reactive()` object.
*   **Destrukturisasi Langsung:** `const { count } = useStore()` akan memutus proxy getter Vue. Properti `count` berubah menjadi primitive number statis.
*   **Mekanisme `storeToRefs`:** Helper ini mengiterasi properti store, memfilter action, dan membungkus setiap properti state/getter menggunakan `toRef()` internal yang mempertahankan koneksi reaktif dua arah ke underlying store proxy.

### 3. Setup Store vs Option Store
*   **Option Store:** Menyediakan deklarasi mirip Vue 2 (`state: () => ({})`, `getters: {}`, `actions: {}`). Di balik layar, Pinia memetakan ini menjadi runtime reactive wrappers.
*   **Setup Store:** Menggunakan sintaksis `defineStore('id', () => { ... })`. Memberikan kontrol penuh setara Vue Composition API, memungkinkan penggunaan composables eksternal di dalam store, serta memiliki inferensi tipe TypeScript yang superior tanpa batas boilerplate.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Isolasi Konteks Server-Side Rendering (SSR)
Pada server-side rendering, store Pinia tidak boleh berupa objek global tunggal (singleton across requests). Jika singleton digunakan, request dari Pengguna A dapat membaca kebocoran data session dari Pengguna B (Cross-Request State Contamination).
*   **Solusi:** Pinia mengikat instansi root store ke `app` context melalui dependency injection Vue (`provide/inject`). Tiap request SSR membuat instance `createPinia()` baru yang terisolasi total.

### Serialisasi dan Dehidrasi / Hidrasi
Pada arsitektur universal (SSR):
1.  **Server Execution:** State diisi melalui server actions.
2.  **Dehidrasi:** State di-ekstrak menjadi payload JSON (`pinia.state.value`) dan disisipkan ke dalam window HTML (`window.__INITIAL_STATE__`).
3.  **Hidrasi Client:** Saat aplikasi client dimuat, `pinia.state.value` di-timpa (*hydrated*) dengan data server sebelum komponen pertama me-render dirinya sendiri.

### Granular Subscriptions vs Actions
*   `$subscribe`: Mendengarkan mutasi state langsung. Berguna untuk sinkronisasi side-effect persistensi disk (LocalStorage/IndexedDB).
*   `$onAction`: Menggunakan *action interceptor pattern*. Menyediakan hook lifecycle:
    *   `after()`: Dieksekusi setelah action resolve.
    *   `onError()`: Menangkap kegagalan asinkron untuk sentralisasi logging.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah contoh implementasi Setup Store yang menangani domain otentikasi secara reaktif dan type-safe.

```typescript
// stores/auth.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface UserSession {
  id: string
  email: string
  roles: string[]
}

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref<string | null>(null)
  const session = ref<UserSession | null>(null)
  const isHydrating = ref<boolean>(true)

  // Getters
  const isAuthenticated = computed<boolean>(() => token.value !== null && session.value !== null)
  const isAdmin = computed<boolean>(() => session.value?.roles.includes('ROLE_ADMIN') ?? false)

  // Actions
  function setSessionData(newToken: string, user: UserSession): void {
    token.value = newToken
    session.value = user
  }

  function purgeSession(): void {
    token.value = null
    session.value = null
  }

  async function fetchSessionInfo(): Promise<void> {
    if (!token.value) {
      isHydrating.value = false
      return
    }

    try {
      isHydrating.value = true
      const response = await fetch('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${token.value}` }
      })
      if (!response.ok) throw new Error('Sesi tidak valid')
      const payload: UserSession = await response.json()
      session.value = payload
    } catch (err) {
      purgeSession()
      throw err
    } finally {
      isHydrating.value = false
    }
  }

  return {
    // State
    token,
    session,
    isHydrating,
    // Getters
    isAuthenticated,
    isAdmin,
    // Actions
    setSessionData,
    purgeSession,
    fetchSessionInfo
  }
})
```

```vue
<!-- components/AuthStatus.vue -->
<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// State dan Getter WAJIB menggunakan storeToRefs
const { session, isAuthenticated, isAdmin, isHydrating } = storeToRefs(authStore)

// Actions dapat didestrukturisasi secara langsung
const { purgeSession } = authStore
</script>

<template>
  <div class="auth-panel">
    <div v-if="isHydrating">Memvalidasi sesi...</div>
    <div v-else-if="isAuthenticated && session">
      <p>Pengguna: {{ session.email }}</p>
      <span v-if="isAdmin" class="badge">Akses Administrator</span>
      <button @click="purgeSession">Logout</button>
    </div>
    <div v-else>
      <p>Silakan masuk ke akun Anda.</p>
    </div>
  </div>
</template>
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File `stores/auth.ts`:
*   `export const useAuthStore = defineStore('auth', () => {`: Menggunakan *Setup Store*. Token `'auth'` adalah unique identifier internal yang digunakan Pinia untuk keying di master state map.
*   `const token = ref<string | null>(null)`: Deklarasi state eksplisit berbasis TypeScript generic.
*   `const isAuthenticated = computed(...)`: Getter yang secara reaktif melakukan tracking dependency terhadap `token` dan `session`.
*   `purgeSession()`: Action murni sinkron yang langsung mereset ref ke state awal tanpa mutator wrapper.
*   `return { ... }`: Setup store **wajib** me-return semua properti publik. Properti yang tidak di-return akan dianggap *private internal variable* yang tidak terekspos ke devtools maupun komponen.

### Analisis File `components/AuthStatus.vue`:
*   `const { session, isAuthenticated, isAdmin } = storeToRefs(authStore)`: Mencegah hilangnya reaktivitas saat destrukturisasi. `storeToRefs` menghasilkan `ToRef<T>` untuk setiap state/getter.
*   `const { purgeSession } = authStore`: Action tidak perlu dan tidak boleh dibungkus `storeToRefs`, karena action adalah referensi fungsi biasa yang context `this`-nya sudah di-bind oleh Pinia proxy.

---

# SEKSI 09 — STUDI KASUS NYATA (Real-World Enterprise Production Scenario)

### Skenario: Financial High-Frequency Order Execution System
Sebuah institusi pertukaran aset keuangan membutuhkan sistem Terminal Perdagangan (Trading Desk). Sistem ini menerima pembaruan data order book dan status eksekusi hingga ratusan transaksi per detik via WebSocket.

### Masalah Arsitektur:
1.  **State Desynchronization Across Tabs:** Trader membuka beberapa tab browser untuk melihat charting dan order list secara bersamaan. Jika pesanan dieksekusi di Tab A, status limit belanja di Tab B harus terupdate tanpa me-refresh jaringan.
2.  **Reactivity Bottleneck:** Ratusan mutasi data per detik membekukan UI (*event loop congestion*) jika seluruh array orderbook di-track secara deep reactive.
3.  **Audit Trail Requirement:** Setiap perubahan state harus memiliki transaction footprint yang dapat direkam dan di-rollback jika server membatalkan pesanan (Optimistic UI with Rollback).

### Solusi Teknis:
1.  Mengembangkan **Optimistic Execution Store** dengan struktur Map normalisasi.
2.  Menggunakan `shallowRef` untuk menampung order book bervolume tinggi guna mematikan overhead dynamic deep proxy.
3.  Menerapkan arsitektur **Pinia Plugin Custom** berbasis `BroadcastChannel` API untuk menyinkronkan snapshot transaksi antar tab browser secara peer-to-peer.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

### Arsitektur Direktori:
```
src/
├── plugins/
│   └── piniaBroadcastSync.ts
└── stores/
    ├── trading.ts
    └── wallet.ts
```

### 1. Pinia Plugin: Multi-Tab Synchronization Engine

```typescript
// plugins/piniaBroadcastSync.ts
import type { PiniaPluginContext } from 'pinia'

interface SyncMessage {
  storeId: string
  patch: Record<string, unknown>
  timestamp: number
  sourceInstanceId: string
}

const INSTANCE_ID = crypto.randomUUID()

export function createCrossTabSyncPlugin(channelName: string = 'pinia_cross_tab_sync') {
  const channel = new BroadcastChannel(channelName)

  return (context: PiniaPluginContext) => {
    const { store } = context

    // 1. Terima patch dari tab lain
    channel.onmessage = (event: MessageEvent<SyncMessage>) => {
      const { storeId, patch, sourceInstanceId } = event.data

      // Abaikan jika pesan berasal dari instansi tab ini sendiri atau store beda
      if (sourceInstanceId === INSTANCE_ID || store.$id !== storeId) {
        return
      }

      // Aplikasikan perubahan state tanpa men-trigger broadcast balik
      store.$patch((state) => {
        Object.assign(state, patch)
      })
    }

    // 2. Subscribe terhadap perubahan state di tab ini
    store.$subscribe((mutation, state) => {
      // Hanya sinkronkan mutasi langsung atau patch, hindari infinite loop
      if (mutation.type === 'direct' || mutation.type === 'patch object') {
        const payload: SyncMessage = {
          storeId: store.$id,
          patch: mutation.payload || { [mutation.events?.key as string]: mutation.events?.newValue },
          timestamp: Date.now(),
          sourceInstanceId: INSTANCE_ID
        }
        channel.postMessage(payload)
      }
    }, { detached: true }) // Tetap aktif terlepas dari lifecycle komponen pemanggil
  }
}
```

### 2. Implementasi Trading Store (Optimistic & High-Performance)

```typescript
// stores/trading.ts
import { defineStore } from 'pinia'
import { ref, shallowRef, computed } from 'vue'
import { useWalletStore } from './wallet'

export type OrderSide = 'BUY' | 'SELL'
export type OrderStatus = 'PENDING' | 'EXECUTED' | 'FAILED'

export interface Order {
  id: string
  symbol: string
  side: OrderSide
  price: number
  amount: number
  status: OrderStatus
}

export const useTradingStore = defineStore('trading', () => {
  const walletStore = useWalletStore()

  // State
  // Gunakan shallowRef untuk koleksi besar yang sering di-replace agar meniadakan deep reactivity overhead
  const activeOrders = shallowRef<Map<string, Order>>(new Map())
  const orderHistory = ref<Order[]>([])
  const isExecuting = ref<boolean>(false)

  // Getters
  const pendingOrders = computed<Order[]>(() => {
    return Array.from(activeOrders.value.values()).filter(o => o.status === 'PENDING')
  })

  const totalCommittedCapital = computed<number>(() => {
    return pendingOrders.value.reduce((acc, order) => {
      return order.side === 'BUY' ? acc + (order.price * order.amount) : acc
    }, 0)
  })

  // Actions
  async function placeOptimisticOrder(orderRequest: Omit<Order, 'id' | 'status'>): Promise<string> {
    const tempId = `temp_${crypto.randomUUID()}`
    const requiredCapital = orderRequest.price * orderRequest.amount

    if (orderRequest.side === 'BUY' && walletStore.availableBalance < requiredCapital) {
      throw new Error('Saldo margin tidak mencukupi untuk membuka order ini.')
    }

    // Snapshot state untuk kompensasi Rollback jika transaksi gagal
    const optimisticOrder: Order = {
      ...orderRequest,
      id: tempId,
      status: 'PENDING'
    }

    // 1. Optimistic Mutation: Kurangi saldo wallet & masukkan ke active orders
    walletStore.reserveBalance(requiredCapital)
    
    // Perbarui map dengan clone baru untuk men-trigger shallowRef reactivity
    const updatedMap = new Map(activeOrders.value)
    updatedMap.set(tempId, optimisticOrder)
    activeOrders.value = updatedMap

    try {
      isExecuting.value = true
      
      // Simulasi panggilan I/O WebSocket/RPC Backend
      const confirmedOrder = await executeOrderViaGateway(optimisticOrder)

      // 2. Commit State jika berhasil
      const finalMap = new Map(activeOrders.value)
      finalMap.delete(tempId)
      finalMap.set(confirmedOrder.id, confirmedOrder)
      activeOrders.value = finalMap

      return confirmedOrder.id
    } catch (error) {
      // 3. Rollback Transaction jika gagal
      const rollbackMap = new Map(activeOrders.value)
      rollbackMap.delete(tempId)
      activeOrders.value = rollbackMap
      
      // Rollback saldo
      walletStore.releaseReservedBalance(requiredCapital)

      throw new Error(`Eksekusi order gagal: ${(error as Error).message}. State di-rollback.`)
    } finally {
      isExecuting.value = false
    }
  }

  // Gateway mock
  async function executeOrderViaGateway(order: Order): Promise<Order> {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        // Simulasi error acak 15% rate untuk membuktikan rollback
        if (Math.random() < 0.15) {
          reject(new Error('Liquidity Timeout / Engine Reject'))
        } else {
          resolve({
            ...order,
            id: `ord_${Date.now()}`,
            status: 'EXECUTED'
          })
        }
      }, 400)
    })
  }

  return {
    activeOrders,
    orderHistory,
    isExecuting,
    pendingOrders,
    totalCommittedCapital,
    placeOptimisticOrder
  }
})
```

### 3. Implementasi Dependent Store: Wallet Store

```typescript
// stores/wallet.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useWalletStore = defineStore('wallet', () => {
  const totalBalance = ref<number>(100000.00) // Default balance 100k USD
  const reservedBalance = ref<number>(0.00)

  const availableBalance = computed<number>(() => {
    return totalBalance.value - reservedBalance.value
  })

  function reserveBalance(amount: number): void {
    if (amount > availableBalance.value) {
      throw new Error('Overdraft Error: Dana tersedia melampaui limit.')
    }
    reservedBalance.value += amount
  }

  function releaseReservedBalance(amount: number): void {
    reservedBalance.value = Math.max(0, reservedBalance.value - amount)
  }

  function deductBalance(amount: number): void {
    totalBalance.value -= amount
    reservedBalance.value = Math.max(0, reservedBalance.value - amount)
  }

  return {
    totalBalance,
    reservedBalance,
    availableBalance,
    reserveBalance,
    releaseReservedBalance,
    deductBalance
  }
})
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektur | Pinia Setup Stores | Pinia Option Stores | Vuex 4 | Plain Composable (`export const useSharedState`) |
| :--- | :--- | :--- | :--- | :--- |
| **Paradigma** | Functional Composition API | Object Property Declaration | Mutation-Action-Getter | Pure Vue Reactivity Scope |
| **Dukungan TypeScript** | Native & Flawless (Full Inference) | Parsial (butuh type cast eksplisit) | Buruk (string mutations butuh overhead) | Sempurna |
| **Tree-shaking Support** | Sangat Tinggi (Store terisolasi) | Sangat Tinggi | Buruk (Monolithic object store) | Maksimal |
| **DevTools Integration** | Native Timeline & Inspection | Native Timeline & Inspection | Native | Tidak ada tanpa wiring manual |
| **SSR Memory Isolation** | Ditangani secara internal via Injection | Ditangani secara internal via Injection | Ditangani secara internal | Bahaya Kebocoran Data (Singleton Leak) |
| **Kompleksitas Boilerplate** | Sangat Rendah | Rendah | Sangat Tinggi | Paling Rendah |
| **Kesesuaian Penggunaan** | **Sistem Enterprise Kompleks** | Transisi Migrasi Vue 2 | Warisan Legacy Saja | State Lokal Sederhana Multi-Komponen |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Circular Dependencies Antar Store
*   **Masalah:** `storeA` memanggil `useStoreB()`, dan di dalam top-level `storeB` memanggil `useStoreA()`. Hal ini memicu loop tak terbatas (*Maximum call stack exceeded*) saat registrasi store pertama kali.
*   **Mitigasi:** Panggil instansiasi store target di dalam action, bukan di *root scope* setup store.

```typescript
// JANGAN LAKUKAN INI DI TOP-LEVEL:
export const useStoreA = defineStore('a', () => {
  const storeB = useStoreB() // Bahaya jika storeB juga memanggil useStoreA di top-level
})

// LAKUKAN INI (LAZY INVOCATION):
export const useStoreA = defineStore('a', () => {
  function executeCrossAction() {
    const storeB = useStoreB() // Resolusi aman saat runtime action dipanggil
    storeB.doWork()
  }
  return { executeCrossAction }
})
```

### 2. State Hydration Mismatch pada SSR
*   **Masalah:** Nilai yang dihasilkan server berbeda dengan client (contoh: kalkulasi waktu `Date.now()` atau akses `localStorage` di dalam store action saat hidrasi).
*   **Mitigasi:** Jangan membaca browser API di root body store. Tunda pembacaan sampai hook `onMounted` dieksekusi atau periksa guard `typeof window !== 'undefined'`.

### 3. Pemutusan Reaktivitas akibat Rest-Spread Destructuring
*   **Masalah:** Melakukan cloning state dengan spread operator: `const stateCopy = { ...store.state }`.
*   **Mitigasi:** Gunakan `storeToRefs` atau gunakan `$patch` jika melakukan manipulasi mutasi agregat.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Mereset State Menggunakan Re-assignment Langsung pada Setup Store
*   *Salah:*
    ```typescript
    // Di dalam Setup Store
    let user = ref({ name: 'John' })
    function reset() {
      user = ref({ name: '' }) // FATAL: Memutus referensi variabel dari objek yang di-return sebelumnya!
    }
    ```
*   *Benar:*
    ```typescript
    const user = ref({ name: 'John' })
    function reset() {
      user.value = { name: '' } // Tetap pertahankan proxy wrapper
    }
    ```

### 2. Mengakses Pinia Store di Luar Vue Context Sebelum Inisialisasi
*   *Salah:*
    ```typescript
    // main.ts
    const auth = useAuthStore() // ERROR: [🍍]: "getActivePinia()" was called but there was no active Pinia.
    const app = createApp(App)
    app.use(createPinia())
    ```
*   *Benar:*
    ```typescript
    // main.ts
    const app = createApp(App)
    const pinia = createPinia()
    app.use(pinia)
    // Panggil useAuthStore HANYA setelah app.use(pinia) dieksekusi
    const auth = useAuthStore()
    ```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan Setup Store secara Konsisten:** Setup store memberikan keseragaman arsitektur karena identik dengan composable biasa (`script setup`).
2.  **Satu Domain, Satu Store:** Pecah domain berdasarkan bounded context (misal: `useAuthStore`, `useCartStore`, `useNotificationStore`). Hindari pembuatan store raksasa yang menangani seluruh domain aplikasi.
3.  **Terapkan Explicit Return Types pada Actions dan Getters:** Hal ini mempercepat kompilasi TypeScript dan mencegah komputasi tipe sirkular (*circular type inference issues*).
4.  **Terapkan Prinsip Command-Query Separation (CQS):** State seharusnya hanya dimutasi melalui actions yang terdokumentasi, bahkan ketika Pinia memperbolehkan direct mutation `store.data = 'value'`. Hal ini krusial untuk pelacakan debugging.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Penggunaan `markRaw` dan `shallowRef` untuk Payload Skala Besar
Vue secara default melakukan rekursif proxy wrapping (`deep reactive`) pada setiap array dan objek. Jika Anda menyimpan data tabular berukuran 10.000 baris, overhead memori proxy trap bisa mencapai 300% lebih besar dari raw JSON:

```typescript
import { shallowRef, markRaw } from 'vue'

export const useAuditStore = defineStore('audit', () => {
  // Hanya track referensi root array. Mengabaikan observasi pada level row data.
  const auditLogs = shallowRef<AuditLog[]>([])

  function pushLogs(newLogs: AuditLog[]) {
    // Tandai objek eksternal agar diabaikan sepenuhnya dari reaktivitas engine
    const rawLogs = markRaw(newLogs)
    auditLogs.value = [...auditLogs.value, ...rawLogs]
  }

  return { auditLogs, pushLogs }
})
```

### 2. Batching State Updates Menggunakan `$patch`
Hindari memicu beberapa trigger reaktivitas berulang kali dalam satu event loop:

```typescript
// Buruk: Memicu 3 kali notifikasi reaktif
authStore.token = newToken
authStore.session = newSession
authStore.isHydrating = false

// Optimal: Memicu TEPAT 1 kali microtask flush
authStore.$patch({
  token: newToken,
  session: newSession,
  isHydrating: false
})
```

---

# SEKSI 16 — KEAMANAN & HARDENING

1.  **Sanitisasi State Persistence:** Jangan pernah menyimpan data otentikasi mentah seperti password, pin, atau *refresh token* yang sensitif ke dalam `localStorage` tanpa enkripsi. LocalStorage rentan terhadap Cross-Site Scripting (XSS).
2.  **State Freezing pada Komponen Presentational:** Cegah modifikasi state yang tidak sengaja dari komponen Vue via runtime freezing:
    ```typescript
    // Mengembalikan data readonly ke pemanggil
    import { readonly } from 'vue'
    
    export const useDataStore = defineStore('data', () => {
      const _internalSensitiveData = ref<SensitiveData>({ ... })
      return {
        // Ekspos sebagai ReadonlyRef
        sensitiveData: readonly(_internalSensitiveData)
      }
    })
    ```
3.  **Mitigasi Prototype Pollution pada Plugin Persistensi:** Saat melakukan hidrasi state JSON dari external storage, hindari merger rekursif yang mengevaluasi `__proto__` atau `constructor`.

---

# SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Di lingkungan production, Anda tidak memiliki akses ke browser devtools milik pengguna akhir. Anda wajib memiliki sentralisasi telemetri terhadap mutasi state dan kegagalan action.

### Implementasi Observability Tracing Plugin:

```typescript
// plugins/piniaTelemetry.ts
import type { PiniaPluginContext } from 'pinia'

interface ErrorTelemetryEvent {
  store: string
  action: string
  args: unknown[]
  error: string
  stack?: string
  timestamp: string
}

export function createPiniaTelemetryPlugin(sink: (event: ErrorTelemetryEvent) => void) {
  return ({ store }: PiniaPluginContext) => {
    store.$onAction(({ name, args, after, onError }) => {
      const startTime = performance.now()

      after((result) => {
        const executionDuration = performance.now() - startTime
        if (executionDuration > 100) { // Log slow actions > 100ms
          console.warn(`[Slow Action Detection] ${store.$id}.${name} took ${executionDuration.toFixed(2)}ms`)
        }
      })

      onError((error) => {
        sink({
          store: store.$id,
          action: name,
          args: sanitizeArguments(args),
          error: (error as Error).message,
          stack: (error as Error).stack,
          timestamp: new Date().toISOString()
        })
      })
    })
  }
}

function sanitizeArguments(args: unknown[]): unknown[] {
  // Samarkan data sensitif seperti password/credit card token sebelum dikirim ke sink log
  return JSON.parse(JSON.stringify(args, (key, value) => {
    if (['password', 'token', 'secret'].includes(key.toLowerCase())) return '***REDACTED***'
    return value
  }))
}
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Setup Store Syntax:** `defineStore('id', () => { ... return { state, getters, actions } })`
*   **Akses Reaktif Aman Komponen:** Wajib gunakan `storeToRefs(store)` untuk mengambil state dan getter.
*   **Direct Destructuring:** HANYA untuk *Actions*, jangan untuk state atau getters.
*   **Optimasi Skala Besar:** Gunakan `shallowRef()` dan `markRaw()` jika menangani > 1.000 records.
*   **Cross-Store Communication:** Panggil `useOtherStore()` di dalam actions untuk menghindari runtime circular dependency deadlocks.
*   **Lifecycle Store:** Pinia stores adalah singleton yang hidup di dalam `effectScope` detached, terisolasi per Vue application root instance.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Seorang insinyur melakukan refactoring store menggunakan destrukturisasi:
```typescript
const { balance } = useWalletStore()
```
Mengapa variabel `balance` di template tidak lagi mengupdate antarmuka ketika action `deductBalance()` dipanggil?
*   A. Karena `balance` harus dideklarasikan menggunakan `let`, bukan `const`.
*   B. Karena `useWalletStore()` mengembalikan reactive proxy object; destrukturisasi melepaskan getter trap dan menghasilkan direct copy nilai primitif.
*   C. Karena action `deductBalance()` berjalan secara asynchronous.
*   D. Karena Pinia mengharuskan mutasi dipanggil melalui `store.commit()`.

### Soal 2
Bagaimana cara terbaik menangani dependency melingkar (circular dependency) di mana `Store A` membutuhkan logika dari `Store B`, dan sebaliknya?
*   A.