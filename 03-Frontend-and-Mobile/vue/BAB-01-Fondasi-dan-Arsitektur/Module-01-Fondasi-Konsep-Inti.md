# Bab 01 Modul 01: Arsitektur Vue 3, Mental Model Composition API, dan Engine Reaktivitas Proxy

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

*   **Menganalisis (C4)** perbedaan fundamental antara arsitektur Vue 2 (`Object.defineProperty`) dan Vue 3 (`Proxy`-based reactivity) pada level alokasi memori dan operasi runtime engine.
*   **Mengonseptualisasikan (C4)** mental model Composition API (`<script setup>`) untuk mengeliminasi problem fragmentasi logika yang inheren pada Options API.
*   **Mengevaluasi (C5)** trade-off struktural antara penggunaan primitive `ref()` dan complex object `reactive()` pada layer state management komponen.
*   **Mengimplementasikan (C6)** custom reactivity watcher dan dependency tracking menggunakan core engine primitives (`track`, `trigger`, `effect`) secara decoupled dari Virtual DOM.

---

### 2. Concept Overview

Vue 3 dirancang ulang dari nol menggunakan TypeScript dengan pendekatan monorepo terdecoupling. Inti dari evolusi ini adalah pemisahan total antara **Reactivity Engine** (`@vue/reactivity`), **Runtime Core** (`@vue/runtime-core`), dan **Compiler** (`@vue/compiler-sfc`). 

Perubahan paradigma paling kritikal terletak pada transisi dari **Options API** ke **Composition API**:

```
+-----------------------------------------------------------------+
|                        Options API (Vue 2)                      |
|  [data] ---------> [methods] ---------> [computed] -----------> |
|  (State terpecah berdasarkan tipe opsi, bukan domain fitur)    |
+-----------------------------------------------------------------+
                                vs
+-----------------------------------------------------------------+
|                     Composition API (Vue 3)                     |
|  Feature A: [state + logic + effect]                            |
|  Feature B: [state + logic + effect]                            |
|  (Colocation: Logika dan reaktivitas dikelompokkan per domain) |
+-----------------------------------------------------------------+
```

Composition API memanfaatkan JavaScript execution context (closure) untuk menyusun kode modular, menghilangkan keterikatan ambigu terhadap konteks runtime `this`, serta memberikan integrasi statis kelas satu (*first-class static inference*) terhadap compiler TypeScript.

---

### 3. Why It Matters

Pada basis kode skala enterprise berumur panjang, Options API menimbulkan beban pemeliharaan kognitif yang tinggi (*high cognitive load*):

1.  **Code Scattering:** Fitur bisnis yang kompleks terpecah ke dalam blok `data`, `methods`, `computed`, dan lifecycle hooks yang terpisah puluhan hingga ratusan baris.
2.  **Limitas Mixins:** Mekanisme code-sharing legasi melalui *Mixins* menciptakan konflik namespace (*implicit name collisions*) dan mengaburkan sumber asal state (*unclear data provenance*).
3.  **Keterbatasan Deteksi Reaktivitas Mutasi:** Engine berbasis `Object.defineProperty` pada Vue 2 tidak dapat mendeteksi penambahan properti baru secara langsung maupun mutasi array via indeks tanpa bantuan `Vue.set()`.
4.  **Tree-Shaking Barrier:** Karena instance komponen berbasis objek monolitik `this`, compiler bundler (seperti Rollup atau Vite/esbuild) tidak dapat mengeliminasi kode fitur yang tidak terpakai secara optimal.

---

### 4. What It Is

Vue 3 adalah framework frontend progresif berbasis komponen yang mengadopsi model **Reaktifitas Fine-Grained berbasis ES6 Proxy** yang digabungkan dengan **Virtual DOM teroptimasi secara hybrid**.

Komponen fundamental Vue 3 terdiri dari:

*   **Reactivity System:** Abstraksi runtime non-intrusif yang meng-intercept operasi baca/tulis (`get`/`set`) pada objek JavaScript untuk membangun dependency graph secara transparan.
*   **Single File Component (SFC) Compiler:** Pipeline parsing khusus yang mengonversi template deklaratif menjadi fungsi render teroptimasi dengan penanda statis (*patch flags*) dan hoisting elemen statis.
*   **Composition Setup Context:** Fase inisialisasi sinkron di mana state reaktif, computed derivations, dan side effects didaftarkan sebelum instance DOM dipasang (*mounted*).

---

### 5. How It Works

Di balik layar, reaktivitas Vue 3 dioperasikan oleh struktur data global: `targetMap`.

```
targetMap: WeakMap<TargetObject, KeyToDepMap>
    │
    └── KeyToDepMap: Map<PropertyKey, DepSet>
            │
            └── DepSet: Set<ReactiveEffect>
```

#### Mekanisme Eksekusi:

1.  **Fase Intersepsi (`get` Trap - Tracking):**
    Saat suatu fungsi render atau closure dieksekusi di dalam context sebuah `ReactiveEffect` (misal: template render, `watchEffect`), sistem menandai effect tersebut sebagai *activeEffect*. Ketika properti pada objek reaktif dibaca, proxy trap `get` terpicu. Engine memanggil `track(target, key)`. `track` akan mengasosiasikan `activeEffect` yang sedang berjalan ke dalam `DepSet` spesifik untuk pasangan `target[key]` tersebut di `targetMap`.

2.  **Fase Mutasi (`set` Trap - Triggering):**
    Ketika nilai dari sebuah properti diubah, proxy trap `set` terpicu. Engine mengevaluasi apakah nilai baru berbeda dari nilai lama via `Object.is()`. Jika terjadi mutasi riil, engine memanggil `trigger(target, key)`. `trigger` mengumpulkan seluruh `ReactiveEffect` dari `DepSet` terkait dan menjadwalkannya (*scheduling*) untuk dieksekusi ulang secara asinkron via microtask queue.

---

### 6. Architecture / Flow Diagram

Berikut adalah alur interaksi dependency tracking dan triggering pada engine Vue 3:

```
[ Inisialisasi ]
       │
       ▼
 [ reactive(obj) ] ───► Bungkus objek dengan ES6 Proxy
       │
       ▼
[ Jalankan Effect / Render Function ]
       │
       ▼
  Set activeEffect = CurrentEffect
       │
       ├──────────────────────────────────────────────┐
       ▼                                              ▼
Operasi Baca: proxy.prop                       Operasi Tulis: proxy.prop = newVal
       │                                              │
       ▼                                              ▼
  Trap: get()                                    Trap: set()
       │                                              │
       ▼                                              ▼
  track(target, "prop")                          trigger(target, "prop")
       │                                              │
       ▼                                              ▼
Apakah activeEffect ada?                      Ambil DepSet dari targetMap
       ├── Tidak ──► (Abaikan)                        │
       └── Ya                                         ▼
           │                                 Jadwalkan eksekusi ulang
           ▼                                 semua ReactiveEffect
Tambahkan activeEffect ke targetMap                   │
[targetMap -> key -> DepSet]                          ▼
                                             Batch Update / Re-render VDOM
```

---

### 7. Simple Code Example

Membandingkan primitive `ref` dan `reactive`:

```typescript
import { ref, reactive, computed } from 'vue'

// 1. Primitive State menggunakan ref()
// Membungkus nilai di dalam objek RefImpl dengan properti .value
const executionCount = ref<number>(0)

// 2. Complex Object menggunakan reactive()
// Mengembalikan Proxy langsung dari objek target
const systemMetrics = reactive({
  cpuLoad: 12.5,
  memoryUsage: 256,
  status: 'OPTIMAL'
})

// 3. Derived State (Computed)
// Otomatis men-track executionCount dan systemMetrics.cpuLoad
const performanceReport = computed(() => {
  return `Execution #${executionCount.value} - CPU: ${systemMetrics.cpuLoad}%`
})

// Mutasi State
function recordMetric(newCpu: number) {
  executionCount.value++ // Wajib menggunakan .value pada TypeScript/JS
  systemMetrics.cpuLoad = newCpu // Mutasi langsung via Proxy
}
```

---

### 8. Practical Real-World Example

Skenario: Implementasi telemetri network resilience engine yang memonitor status koneksi, melakukan retry dengan backoff eksponensial, dan mengelola state antrean pengiriman secara reaktif.

```typescript
// composables/useResilientTelemetry.ts
import { ref, reactive, computed, readonly, onUnmounted } from 'vue'

interface TelemetryPayload {
  eventId: string
  payload: Record<string, unknown>
  timestamp: number
}

interface CircuitBreakerState {
  failureCount: number
  state: 'CLOSED' | 'OPEN' | 'HALF_OPEN'
  lastFailureTime: number | null
}

export function useResilientTelemetry(endpoint: string, maxRetries = 3) {
  // Queue didesain dengan reactive array untuk deep mutation tracking
  const eventQueue = reactive<TelemetryPayload[]>([])
  
  // Primitives untuk tracking metrics
  const isSyncing = ref<boolean>(false)
  const lastSyncTimestamp = ref<number | null>(null)
  
  // Circuit breaker state
  const circuitBreaker = reactive<CircuitBreakerState>({
    failureCount: 0,
    state: 'CLOSED',
    lastFailureTime: null
  })

  const queueLength = computed(() => eventQueue.length)
  const isHealthy = computed(() => circuitBreaker.state === 'CLOSED')

  let retryTimer: ReturnType<typeof setTimeout> | null = null

  const dispatch = (data: Record<string, unknown>) => {
    const item: TelemetryPayload = {
      eventId: crypto.randomUUID(),
      payload: data,
      timestamp: Date.now()
    }
    eventQueue.push(item)
    triggerFlush()
  }

  const triggerFlush = async () => {
    if (isSyncing.value || eventQueue.length === 0 || circuitBreaker.state === 'OPEN') {
      return
    }

    isSyncing.value = true

    while (eventQueue.length > 0) {
      const currentBatch = eventQueue.slice(0, 10)
      
      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(currentBatch)
        })

        if (!response.ok) throw new Error(`HTTP error: ${response.status}`)

        // Berhasil: hapus item yang telah terkirim
        eventQueue.splice(0, currentBatch.length)
        circuitBreaker.failureCount = 0
        circuitBreaker.state = 'CLOSED'
        lastSyncTimestamp.value = Date.now()
      } catch (err) {
        circuitBreaker.failureCount++
        circuitBreaker.lastFailureTime = Date.now()

        if (circuitBreaker.failureCount >= maxRetries) {
          circuitBreaker.state = 'OPEN'
          // Schedule half-open transition setelah 30 detik
          retryTimer = setTimeout(() => {
            circuitBreaker.state = 'HALF_OPEN'
            triggerFlush()
          }, 30000)
        }
        break // Hentikan batch loop saat error terjadi
      }
    }

    isSyncing.value = false
  }

  onUnmounted(() => {
    if (retryTimer) clearTimeout(retryTimer)
  })

  return {
    dispatch,
    isHealthy,
    isSyncing: readonly(isSyncing),
    queueLength,
    lastSyncTimestamp: readonly(lastSyncTimestamp)
  }
}
```

---

### 9. Step-by-Step Implementation Guide

Berikut panduan mengonstruksi komponen consumer untuk modul telemetri di atas menggunakan `<script setup lang="ts">`.

#### Langkah 1: Konstruksi File Komponen SFC
Buat file `TelemetryMonitor.vue`. Gunakan blok skrip deklaratif:

```html
<script setup lang="ts">
import { useResilientTelemetry } from './composables/useResilientTelemetry'

// Inisialisasi composable
const { dispatch, isHealthy, isSyncing, queueLength, lastSyncTimestamp } = 
  useResilientTelemetry('/api/v1/telemetry')

const handleManualEmit = () => {
  dispatch({
    userAction: 'HEARTBEAT_TRIGGERED',
    viewport: `${window.innerWidth}x${window.innerHeight}`
  })
}
</script>
```

#### Langkah 2: Konstruksi Template Deklaratif
Binding langsung primitive `ref` ke template tanpa menggunakan `.value`. Vue compiler secara otomatis melakukan unref pada top-level bindings di dalam template context.

```html
<template>
  <div class="telemetry-panel">
    <h3>Engine Telemetri Runtime</h3>
    
    <div class="status-indicator">
      <span>Status Circuit: </span>
      <strong :class="{ healthy: isHealthy, down: !isHealthy }">
        {{ isHealthy ? 'STABLE' : 'DEGRADED / HALTED' }}
      </strong>
    </div>

    <div class="metrics">
      <p>Antrean Tertunda: {{ queueLength }} item</p>
      <p>Sinkronisasi Berjalan: {{ isSyncing ? 'Sedang Transmit...' : 'Idle' }}</p>
      <p>Terakhir Sinkron: {{ lastSyncTimestamp ? new Date(lastSyncTimestamp).toISOString() : 'Belum Pernah' }}</p>
    </div>

    <button :disabled="isSyncing" @click="handleManualEmit">
      Enqueue Manual Telemetry Event
    </button>
  </div>
</template>
```

#### Langkah 3: Scoped Style Styling
Gunakan CSS terisolasi via CSS modules atau scoped attributes:

```html
<style scoped>
.telemetry-panel {
  border: 1px solid #2a2a2a;
  padding: 1.5rem;
  border-radius: 6px;
  background-color: #121212;
  color: #ededed;
  font-family: monospace;
}
.healthy { color: #42b883; }
.down { color: #e35050; }
button {
  background-color: #35495e;
  color: #fff;
  border: none;
  padding: 0.5rem 1rem;
  cursor: pointer;
  border-radius: 4px;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
```

---

### 10. Edge Cases & Corner Scenarios

#### 1. Reactivity Loss via Destructuring
Mendestrukturisasi objek dari `reactive()` merusak mekanisme dependency tracking:

```typescript
const telemetryConfig = reactive({ timeout: 5000, maxRetries: 3 })

// SALAH: Reaktivitas putus total. 'timeout' kini hanya primitive number biasa!
const { timeout } = telemetryConfig 

// BENAR: Gunakan toRefs() untuk mengonversi properti objek menjadi sekumpulan RefImpl
import { toRefs } from 'vue'
const { timeout: safeTimeout } = toRefs(telemetryConfig)
// safeTimeout.value terhubung secara reaktif ke telemetryConfig.timeout
```

#### 2. Shallow vs Deep Proxy pada Non-Standard Collection Types
Engine `reactive()` hanya meng-intercept native collection types (`Map`, `Set`, `WeakMap`, `WeakSet`, `Array`, `Object`). Custom non-enumerable class instance atau dynamic internal objects (seperti native WebSockets atau DOM nodes) yang dibungkus `reactive()` dapat mengalami runtime exception atau memory leaks karena masalah invalid context receiver (`this`).

*Mitigasi:* Gunakan `shallowRef()` atau `markRaw()` untuk instance third-party library, socket connection, atau class eksternal.

```typescript
import { shallowRef, markRaw } from 'vue'

// BENAR: Engine reaktivitas hanya mengamati perubahan referensi instance socket, bukan internal properties
const socketConnection = shallowRef(new WebSocket('wss://telemetry.internal'))
```

---

### 11. Common Pitfalls & Antipatterns

*   **Antipattern: Mengganti Seluruh Objek `reactive`:**
    ```typescript
    let state = reactive({ data: [] })
    // FATAL: Mutasi referensi pointer menghancurkan wrapper Proxy awal.
    // Template dan effect yang me-listen Proxy lama tidak akan pernah menerima update!
    state = reactive({ data: [1, 2, 3] }) 
    
    // Solusi: Gunakan ref() jika objek target harus sering di-reassign
    const stateRef = ref({ data: [] })
    stateRef.value = { data: [1, 2, 3] }
    ```

*   **Pitfall: Asynchronous Scope Disconnection pada Lifecycle:**
    Jika fungsi seperti `watchEffect()` atau `computed()` dideklarasikan di dalam closure asinkron (misalnya di dalam `setTimeout` atau setelah `await`), reaktivitas tersebut tidak terikat ke *lifecycle scope* instance komponen, sehingga **tidak akan dibersihkan otomatis** saat komponen di-unmount, berpotensi menyebabkan *memory leak*.

---

### 12. Performance Considerations

1.  **Overhead Alokasi Proxy:**
    Membungkus ribuan baris data tabel berukuran besar menggunakan `reactive()` akan melakukan iterasi traversal rekursif secara mendalam. Untuk data tabular yang bersifat *read-only* dari REST/GraphQL API:
    ```typescript
    import { shallowRef } from 'vue'
    // Mengurangi alokasi ribuan Proxy instances menjadi 1 reference check saja
    const largeDataset = shallowRef(hugeApiPayload)
    ```
2.  **Vue 3 Compiler Optimizations (PatchFlags):**
    Template compiler Vue 3 mendeteksi node mana yang statis dan mana yang dinamis. Elemen statis di-hoist keluar fungsi `render`, sehingga runtime patching kompleksitasnya berkurang dari $O(N)$ (seluruh node template) menjadi $O(M)$ (hanya node dinamis yang ditandai patch flag).

---

### 13. Security Considerations

1.  **Vulnerability `v-html` dan XSS Injection:**
    Engine reaktivitas merefleksikan string mentah secara apa adanya. Mengikat API payloads yang tidak ter-sanitasi ke dalam directive `v-html` memicu potensi eksekusi script berbahaya (*Cross-Site Scripting*).
    *Proteksi:* Gunakan library DOMPurify sebelum merender string HTML pihak ketiga:
    ```typescript
    import DOMPurify from 'dompurify'
    const safeContent = computed(() => DOMPurify.sanitize(rawHtmlContent.value))
    ```
2.  **Prototype Pollution via Deep Reactive Assignment:**
    Hindari melakukan deep merge objek reaktif secara sembarangan dari JSON input user tanpa validasi skema (seperti Zod), karena dapat memanipulasi properti `__proto__`.

---

### 14. Debugging & Observability

Vue 3 mengekspos lifecycle hooks internal untuk men-trace siklus dependency tracking secara spesifik:

```typescript
import { ref, onRenderTracked, onRenderTriggered } from 'vue'

const counter = ref(0)

// Terpicu ketika dependency selesai didaftarkan (Read Operation)
onRenderTracked((debuggerEvent) => {
  console.log({
    type: 'TRACK_DEPENDENCY',
    target: debuggerEvent.target,
    key: debuggerEvent.key,
    effect: debuggerEvent.effect
  })
})

// Terpicu ketika mutasi menginisiasi re-render (Write Operation)
onRenderTriggered((debuggerEvent) => {
  console.warn({
    type: 'TRIGGER_RE-RENDER',
    key: debuggerEvent.key,
    oldValue: debuggerEvent.oldValue,
    newValue: debuggerEvent.newValue
  })
})
```

Gunakan `toRaw()` untuk mengakses objek native murni non-proxy saat debugging untuk membaca snapshot memory tanpa memicu side effects:
```typescript
import { toRaw } from 'vue'
console.log('Raw underlying object:', toRaw(systemMetrics))
```

---

### 15. Trade-offs & Comparisons

| Parameter | Vue 3 (Composition API) | React 18+ (Hooks) | Svelte 5 (Runes) |
| :--- | :--- | :--- | :--- |
| **Reactivity Mechanism** | Fine-grained via ES6 Proxy | Coarse-grained (Component-level re-render) | Compiler-driven Signals |
| **Execution Model** | `setup()` hanya dieksekusi **satu kali** saat inisialisasi | Functional component dieksekusi **berulang-ulang** di tiap state update | Transpiled compile-time reactive assignments |
| **Dependency Arrays** | Tidak perlu (`computed`/`watchEffect` auto-track) | Wajib secara eksplisit (`useEffect(fn, [dep])`) | Tidak perlu (Compiler auto-derives) |
| **Closure Stale State** | Kebal secara fundamental (mengacu pada objek pembungkus stabil) | Rawan stale closures jika dependency array salah | Kebal (Transpiled variable access) |
| **Memory Footprint** | Menengah (Alokasi Proxy & Dependency Set Map) | Rendah (Native JS primitives, stateless renders) | Paling Rendah (Minimal runtime abstraction) |

---

### 16. Best Practices & Guidelines

*   **Aturan Penulisan `ref` vs `reactive`:**
    *   Gunakan `ref()` sebagai default utama untuk seluruh primitive types (`string`, `number`, `boolean`, `null`, `undefined`).
    *   Gunakan `ref()` untuk struktur data yang memerlukan re-assignment menyeluruh (seperti data response API).
    *   Gunakan `reactive()` hanya jika Anda memodelkan entitas state yang terisolasi dan padat interaksi (misalnya: sub-form state atau dictionary stateful internal).
*   **Standarisasi Ekstraksi Composables:**
    *   Selalu gunakan konvensi nama `use<DomainName>()`.
    *   Kembalikan plain object berisi plain `ref` references atau explicit `toRefs(state)` agar consumer dapat mendestrukturisasi hasil composable tanpa merusak reaktivitas:
        ```typescript
        // Pola Ideal Composable API
        return {
          metric: readonly(metric), // Mencegah mutasi ilegal di luar boundary
          updateMetric
        }
        ```

---

### 17. Testing Strategies

Gunakan **Vitest** dan `@vue/test-utils` untuk memvalidasi engine logic terisolasi secara head-to-head tanpa harus melakukan render DOM secara penuh jika menguji business logic composables.

```typescript
// tests/composables/useResilientTelemetry.spec.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useResilientTelemetry } from '../../composables/useResilientTelemetry'

describe('useResilientTelemetry Subsystem', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('harus memvalidasi reaktivitas status queue secara sinkron', () => {
    const { dispatch, queueLength } = useResilientTelemetry('/api/mock')

    expect(queueLength.value).toBe(0)
    dispatch({ test: 'payload_alpha' })
    expect(queueLength.value).toBe(1)
  })

  it('harus memicu circuit breaker ke status OPEN saat max retries terlewati', async () => {
    // Mock network fetch failure
    global.fetch = vi.fn().mockRejectedValue(new Error('Network Down'))

    const { dispatch, isHealthy } = useResilientTelemetry('/api/mock', 2)

    expect(isHealthy.value).toBe(true)

    // Trigger fails
    dispatch({ action: 'TEST_FAIL_1' })
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1))

    dispatch({ action: 'TEST_FAIL_2' })
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2))

    // State harus berevolusi secara reaktif
    expect(isHealthy.value).toBe(false)
  })
})
```

---

### 18. Integration with Existing Systems

Jika mengintegrasikan komponen Vue 3 ke dalam sistem monolith legasi (Laravel Blade, Django Templates, Ruby on Rails, atau aplikasi ASP.NET Core):

#### Pola Multi-Root Custom Mounting
Anda tidak perlu membungkus seluruh aplikasi ke dalam Single Page Application (SPA). Mount Vue 3 secara parsial pada elemen penampung (*island architecture* sederhana):

```typescript
// main-legacy-entry.ts
import { createApp } from 'vue'
import TelemetryMonitor from './components/TelemetryMonitor.vue'

// Temukan seluruh target penampung yang disuntikkan oleh server template engine
const widgetMountPoints = document.querySelectorAll<HTMLElement>('.vue-telemetry-island')

widgetMountPoints.forEach((mountNode) => {
  // Parsing parameter inisialisasi yang dirender server-side via data-attributes
  const endpoint = mountNode.dataset.endpoint || '/default-telemetry'

  const app = createApp(TelemetryMonitor, { endpoint })
  app.mount(mountNode)
})
```

---

### 19. Summary & Cheat Sheet

```
+----------------+-------------------------------+-----------------------------------------+
| API Primitive  | Parameter Target             | Mental Model / Karakteristik            |
+----------------+-------------------------------+-----------------------------------------+
| ref(x)         | Primitives, Objects, Arrays   | Membungkus x dalam { value: x }.         |
|                |                               | Di-unref otomatis di template root.    |
+----------------+-------------------------------+-----------------------------------------+
| reactive(x)    | Object, Array, Map, Set       | Mengembalikan ES6 Proxy asli objek.     |
|                |                               | Jangan didestruktur tanpa toRefs().     |
+----------------+-------------------------------+-----------------------------------------+
| computed(fn)   | Getter (Optional Setter) fn   | Lazy derivation. Melakukan caching      |
|                |                               | berbasis dirty tracking dependency.     |
+----------------+-------------------------------+-----------------------------------------+
| shallowRef(x)  | Mutasi via .value replacement | Non-deep proxy. Optimal untuk large     |
|                |                               | datasets & instances pihak ketiga.      |
+----------------+-------------------------------+-----------------------------------------+
| toRefs(obj)    | Reactive Object               | Mengonversi seluruh key object menjadi  |
|                |                               | kumpulan isolated ref().                |
+----------------+-------------------------------+-----------------------------------------+
| readonly(x)    | Proxy / Ref                   | Memblokir operasi mutasi pada write     |
|                |                               | trap (Fail in dev mode / no-op in prod).|
+----------------+-------------------------------+-----------------------------------------+
```

---

### 20. Self-Assessment Exercises

#### Soal Analisis
1. Mengapa engine reaktivitas Vue 3 tidak lagi memerlukan method bantuan `$set` seperti pada Vue 2 (`Vue.set(object, key, value)`)? Jelaskan keterbatasan internal `Object.defineProperty` dibanding ES6 Proxy yang menjadi akar masalah ini!
2. Diberikan potongan kode berikut:
   ```typescript
   const state = reactive({ count: 0 })
   const increment = () => { state.count++ }
   const { count } = state
   ```
   Jika `count` dirender ke dalam template, mengapa nilai yang tampil di layar tidak pernah ter-update saat `increment()` dieksekusi? Deskripsikan alur memori variabel tersebut.

#### Tantangan Implementasi Kode
Rancanglah sebuah custom composable bernama `useDebouncedReactiveHistory(sourceRef, delayMs)` yang memiliki spesifikasi berikut:
*   Menerima sebuah `ref` bertipe primitif atau objek.
*   Menyimpan history perubahan nilai `sourceRef` secara ter-debounce menggunakan `watch()`.
*   Mengekspos API:
    *   `history`: Array reaktif berisi history list snapshots nilai.
    *   `undo()`: Fungsi untuk membalikkan nilai `sourceRef` ke snapshot sebelumnya.
    *   `canUndo`: Property `computed` boolean yang bernilai `true` jika history masih tersedia.
*   Wajib membersihkan internal timer saat lifecycle scope unmount terjadi secara otomatis.