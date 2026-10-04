# BAB 08: Built-in Components, Transitions, dan UX
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Menganalisis dan Membedah Arsitektur Internal Built-in Components:** Memahami siklus hidup Virtual DOM (VNode), manipulasi patch renderer, dan state persistence pada komponen abstrak Vue 3 (`<Transition>`, `<TransitionGroup>`, `<KeepAlive>`, `<Teleport>`, `<Suspense>`).
2. **Mengimplementasikan Algoritma FLIP secara Native:** Mengoptimalkan animasi list reordering berkinerja tinggi pada `<TransitionGroup>` tanpa memicu Layout Thrashing (Reflow).
3. **Membangun Strategi Caching Skala Besar dengan `<KeepAlive>`:** Mengembangkan custom eviction policy (LRU - *Least Recently Used*) terintegrasi dengan State Management (Pinia) dan Vue Router untuk mencegah memory leak pada Single Page Application (SPA) enterprise.
4. **Menghindari Perangkap Konteks CSS dan Stacking Context via `<Teleport>`:** Menata arsitektur portal global untuk modal, popover, dan toast yang aman terhadap layout isolation, micro-frontends, dan hydration SSR.
5. **Mendesain Pola Asinkron Lanjutan dengan `<Suspense>`:** Mengatur streaming hydration, nested async dependencies, skeleton orchestration, dan robust error boundaries.
6. **Menerapkan Profiling dan GPU Acceleration:** Mengukur performa transisi menggunakan Chrome DevTools Performance panel, memastikan eksekusi animasi murni berjalan di Compositor Thread melalui properti `transform` dan `opacity`.

---

### 2. Prerequisite

Peserta wajib menguasai:
* **Vue 3 Composition API & Reactivity Core:** Ref, reactive, computed, effect scope, dan lifecycle hooks (`onMounted`, `onUnmounted`).
* **Browser Rendering Pipeline:** Pemahaman mendalam tentang tahapan parsing DOM/CSSOM, Recalculate Style, Layout (Reflow), Paint, dan Compositing.
* **TypeScript Lanjutan:** Generics, Utility Types, Typing dynamic components, dan VNode rendering functions (`h()`).
* **Dasar Vue Virtual DOM:** Struktur objek VNode, patch flags, shape flags, dan mekanisme reconciler.

---

### 3. Concept & Internal Architecture

Built-in components pada Vue 3 (`KeepAlive`, `Teleport`, `Transition`, `TransitionGroup`, `Suspense`) bukanlah komponen biasa. Secara internal di dalam `@vue/runtime-core`, komponen-komponen ini diklasifikasikan sebagai **Abstract Components** atau diperlakukan secara khusus oleh *Renderer*.

```
+-------------------------------------------------------------------+
|                        @vue/runtime-core                          |
|                                                                   |
|   +------------------+    +------------------+    +-----------+   |
|   |   KeepAliveImpl  |    |   TeleportImpl   |    |  Suspense |   |
|   |  (ShapeFlag.     |    |  (ShapeFlag.     |    |  (Async   |   |
|   |  COMPONENT_      |    |  TELEPORT)       |    |  Boundary)|   |
|   |  KEPT_ALIVE)     |    |                  |    |           |   |
|   +--------+---------+    +--------+---------+    +-----+-----+   |
|            |                       |                    |         |
|            v                       v                    v         |
|   +-----------------------------------------------------------+   |
|   |                    Base Renderer / Patch                  |   |
|   |   - Intercepts mounting / unmounting                      |   |
|   |   - Redirects target container (Teleport)                 |   |
|   |   - Cache subTree instead of unmounting (KeepAlive)       |   |
|   |   - Orchestrates async resolve / fallback (Suspense)      |   |
|   +-----------------------------+-----------------------------+   |
+---------------------------------|---------------------------------+
                                  v
+-------------------------------------------------------------------+
|                         @vue/runtime-dom                          |
|                                                                   |
|   +-----------------------------------------------------------+   |
|   |                Transition / TransitionGroup               |   |
|   |   - Injects enter/leave hooks onto VNode hooks            |   |
|   |   - Evaluates CSS classes & JavaScript transition hooks   |   |
|   |   - Calculates FLIP bounding rects for siblings           |   |
|   +-----------------------------------------------------------+   |
+-------------------------------------------------------------------+
```

#### A. Internal `<KeepAlive>`: Cache Engine & VNode Hijacking
Komponen `<KeepAlive>` bekerja langsung di level renderer engine. Ia tidak me-render elemen DOM miliknya sendiri (komponen pembungkus abstrak: `render() { return null }` secara langsung tidak ada, melainkan mengembalikan child slot tunggalnya).

1. **Storage Structure:** `<KeepAlive>` mengelola dua struktur data internal:
   - `keys`: `Set<InjectionKey | string | number | ConcreteComponent>` untuk melacak urutan pemanggilan (dasar LRU cache).
   - `cache`: `Map<CacheKey, VNode>` yang menyimpan VNode instance beserta DOM fisik riil (`subTree.el`).
2. **Lifecycle Interception:** Saat komponen dalam `<KeepAlive>` dinonaktifkan:
   - Renderer mengecek bitmask flag: `shapeFlag & ShapeFlags.COMPONENT_KEPT_ALIVE`.
   - Alih-alih memanggil `unmountComponent()`, renderer memanggil internal hook: `deactivate(instance)`.
   - Node DOM fisik dicabut dari parent via `hostRemove(child.el)`, tetapi subtree VNode dan instance internal Vue (`instance.subTree`, scopes, states) tetap tersimpan di memori.
   - Lifecycle `onDeactivated()` dipicu.
3. **Re-activation:** Ketika kunci komponen kembali aktif:
   - Renderer mengecek cache. Jika VNode ditemukan, flag diubah menjadi `COMPONENT_KEPT_ALIVE`.
   - Node DOM yang telah ada di-inject kembali ke kontainer fisik via `hostInsert(vnode.el, hostContainer)`.
   - Lifecycle `onActivated()` dipicu.

#### B. Internal `<Teleport>`: Target Container Resolution & Hydration Order
`<Teleport>` memiliki method internal `process()` yang mengambil alih proses patch standar:
- Node dipisahkan dari alur traversal tree komponen induk.
- **Anchor Placement:** Renderer menempatkan *anchor node* (komentar kosong `<!--teleport start-->` dan `<!--teleport end-->`) di lokasi template asal sebagai placeholder layout virtual.
- **Physical Insertion:** Target query selector (`to="body"`, dsb.) dievaluasi saat runtime DOM. Komponen anak di-patch langsung di bawah node target tersebut.
- **SSR Hydration:** Pada SSR (Server-Side Rendering), hydration membutuhkan target DOM telah dieksekusi sebelum teleport client dihidrasi, atau menggunakan teleport boundary agar tidak terjadi hydration mismatch.

#### C. Internal `<Transition>` & `<TransitionGroup>`: FLIP & Style Injections
- **`<Transition>`:** Mencegat siklus mount dan unmount. Pada fase unmount, ia menunda `remove()` fisik elemen sampai event `transitionend` atau `animationend` ditembakkan oleh browser, atau eksekusi callback `done()` dari JS hook selesai.
- **`<TransitionGroup>` FLIP Mechanism:**
  1. **First:** Mengukur posisi awal semua elemen anak via `getBoundingClientRect()`.
  2. **Last:** Mengeksekusi mutasi DOM (penambahan/penghapusan/pengurutan list), lalu mengukur posisi akhir elemen-elemen tersebut.
  3. **Invert:** Menghitung selisih koordinat:
     $$\Delta X = X_{\text{first}} - X_{\text{last}}$$
     $$\Delta Y = Y_{\text{first}} - Y_{\text{last}}$$
     Vue secara otomatis mengaplikasikan inline style `transform: translate(ΔXpx, ΔYpx)` secara instan (tanpa transisi) agar elemen seolah-olah tetap di posisi asal.
  4. **Play:** Memaksa browser mengeksekusi reflow/repaint via property reading, kemudian menghapus inline transform dan menambahkan class `*-move` yang memiliki `transition: transform ...`, sehingga browser menggerakkan elemen secara mulus ke posisi akhir (*Last*).

#### D. Internal `<Suspense>`: Async Dependency Tree Resolution
`<Suspense>` mengamati seluruh turunan VNode yang memiliki *async setup* (`setup()` yang mengembalikan `Promise`). 
- Menghitung counter dependensi asinkron yang belum tuntas.
- Jika satu atau lebih child Promise berstatus `pending`, `<Suspense>` mengalihkan rendering slot ke slot `fallback`.
- Hanya ketika seluruh subtree Promise ter-resolve secara sukses, slot `default` di-mount ke DOM secara atomik dalam satu batch render traversal.

---

### 4. Why & What

| Fitur / Komponen | What (Definisi & Mekanisme) | Why (Alasan Arsitektural & Masalah yang Diatasi) |
| :--- | :--- | :--- |
| **Declarative Transition System** | Abstraksi koordinasi animasi CSS/JS terintegrasi dengan reactive VNode patching. | Menghilangkan manipulasi manual DOM via jQuery/vanilla JS yang rawan race condition, memory leak event listener, dan mismatch Virtual DOM. |
| **FLIP Technique dalam TransitionGroup** | Pendekatan komputasi aljabar koordinat untuk animasi perubahan layout list. | Mengubah operasi layout berbiaya mahal (perubahan `top`, `margin`, `left`) menjadi operasi hardware-accelerated (`transform`), menjaga target 60-120 FPS. |
| **`<KeepAlive>` Architecture** | Caching subTree VNode & physical DOM in-memory berbasis LRU / dynamic keys. | Menghindari re-fetching data masif, kalkulasi ulang state komponen, dan re-rendering DOM yang merusak responsivitas aplikasi bertipe dashboard multi-tab. |
| **`<Teleport>` Escape Hatch** | Pemisahan posisi render DOM fisik dari hierarki Virtual Component Tree. | Mengatasi limitasi CSS Stacking Context (seperti `z-index`, `overflow: hidden`, `filter`, `transform`) pada parent yang memotong atau merusak posisi Modal, Drawer, dan Tooltip. |
| **`<Suspense>` Orchestration** | Boundary kontrol berbasis Promise untuk pemuatan komponen asinkron bersarang. | Mengeliminasi *Waterfall Skeleton Problem*, di mana sub-komponen memicu skeleton masing-masing secara berulang (*flickering UI*), digantikan dengan transisi state UI tunggal terpadu. |

---

### 5. How (Workflow Detail)

#### Execution Pipeline: Lifecycle `<Transition>` saat Component Teardown

```
[VNode Patch Triggered: Component Unmount]
                   |
                   v
[Check VNode inside <Transition>]
                   |
                   v
[Add Class: *-leave-from] 
[Call Hook: onBeforeLeave(el)]
                   |
                   v (Next Tick / Double rAF)
[Add Class: *-leave-active, *-leave-to]
[Remove Class: *-leave-from]
[Call Hook: onLeave(el, done)]
                   |
                   +------------------------------+
                   | Wait for transitionend event |
                   | OR invoke done() execution   |
                   +------------------------------+
                                  |
                                  v
                   [Remove Class: *-leave-active, *-leave-to]
                   [Call Hook: onAfterLeave(el)]
                                  |
                                  v
                   [Execute hostRemove(el)] -> Detach from Real DOM
```

#### Execution Pipeline: Komputasi FLIP `<TransitionGroup>`

1. **State Mutation:** Array reaktif mengalami perubahan urutan item (misal: pengurutan, filter, penghapusan).
2. **Snapshot First:** Hook internal `beforeUpdate` mengiterasi setiap VNode anak, membaca DOM node fisiknya, memanggil `el.getBoundingClientRect()`, dan menyimpannya di `Map<Key, DOMRect>`.
3. **DOM Mutation:** Vue melakukan reconciliation/patching VNode ke DOM fisik secara sinkron. Posisi node berubah di DOM.
4. **Snapshot Last:** Hook internal `updated` memanggil `el.getBoundingClientRect()` baru untuk setiap elemen.
5. **Invert Calculation:**
   - Dihitung: $dx = \text{Rect}_{\text{old}}.left - \text{Rect}_{\text{new}}.left$, $dy = \text{Rect}_{\text{old}}.top - \text{Rect}_{\text{new}}.top$.
   - Jika $dx \neq 0$ atau $dy \neq 0$, terapkan style: `el.style.transform = 'translate(' + dx + 'px, ' + dy + 'px)'; el.style.transitionDuration = '0s';`.
6. **Force Reflow:** Akses read-property (misal: `el.offsetWidth`) untuk memaksa engine browser mencatat posisi inversi.
7. **Play Phase:** Terapkan class `*-move`. Hapus inline transform dan inline transition-duration. Browser secara native melakukan interpolasi hardware-accelerated kembali ke matriks identitas (`translate(0, 0)`).

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
- **`<KeepAlive>`:** Seperti *Ruang Tunggu Aktor (Backstage)*. Saat aktor keluar dari panggung (deactivated), ia tidak diganti atau dipecat (unmount); pakaian dan riasan tetap utuh. Saat nomor panggungnya tiba kembali, ia langsung melangkah ke panggung (activated) seketika tanpa perlu proses make-up dari nol.
- **`<Teleport>`:** Seperti *Drone Pengantar Barang Jarak Jauh*. Remote kendali dan instruksi dipegang di kantor pusat (Parent Component), tetapi muatannya dilepaskan dan ditempatkan langsung di puncak gedung lain (Target DOM: `document.body`), melompati semua sekat, pintu, dan batasan lantai di bawahnya.
- **`<Suspense>`:** Seperti *Manajer Orkestra Simfoni*. Konduktor melarang orkestra mulai memainkan musik (render slot default) hingga seluruh pemain alat musik (Promise-promise asinkron) telah duduk di kursinya dan selesai melakukan tuning. Selama masa persiapan, penonton dipersilakan membaca pamflet acara (fallback slot).

#### ASCII Visual Architecture

##### 1. FLIP Coordinate Inversion
```
Timeline: Frame 0 (First)      Mutasi & Render (Last)       Inversion applied (Invert)   Compositor Action (Play)
+--------------+               +--------------+             +--------------+             +--------------+
| Item A (Y=0) |               | Item B (Y=0) |             | Item B (Y=0) |             | Item B       |
+--------------+               +--------------+             +--------------+             |   | (Animate)|
| Item B (Y=50)| --(Sort)-->   | Item A (Y=50)|             | Item A (Y=50)|             |   v          |
+--------------+               +--------------+             | ^            |             |              |
                                                            | | transform: |             |              |
                                                            | | translateY |             +--------------+
                                                            | | (-50px)    |             | Item A       |
                                                            +--------------+             +--------------+
                                                            [Tampak di Y=0]               Transitioning...
```

##### 2. KeepAlive LRU Eviction & Subtree Caching
```
Capacity = 2
-------------------------------------------------------------------------
State 1: Access Tab A -> Cache: [A]
State 2: Access Tab B -> Cache: [A, B]
State 3: Access Tab A -> Cache: [B, A] (A diperbarui ke status most-recent)
State 4: Access Tab C -> Cache: [A, C] (B terdepak: unmountComponent(B))
-------------------------------------------------------------------------

  [ Component Viewport ]
           |
     activeSubTree
           |
           v
+----------------------+         LRU Double-Linked Mechanism
| KeepAlive Container  | --->  [ Head: Node C ] <-> [ Tail: Node A ]
+----------------------+                      \
           |                                   +-- [ Evicted: Node B (Purged) ]
  Cached VNodes in Memory
```

##### 3. Stacking Context Breakout via Teleport
```
#app (Root) [transform: scale(0.95)] <-- Isolasi Stacking Context Tercipta di Sini!
 |
 +-- Component Page
      |
      +-- Overflow Container [overflow: hidden; z-index: 1]
           |
           +-- <Teleport to="#modal-target">
           |        |
           |        +---- (VNode Logical Link dipelihara secara reactive)
           |
           x (DOM Fisik Terputus dari Hierarki Parent)

#modal-target (Langsung di bawah <body>)
 |
 +-- Physical DOM Node: <div class="modal-dialog"> [z-index: 99999] 
     (Bebas dari pengaruh 'transform' dan 'overflow' milik #app)
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Accessible, FLIP-Enabled Reordering List

```vue
<!-- components/PriorityTaskQueue.vue -->
<script setup lang="ts">
import { ref } from 'vue';

interface Task {
  id: number;
  label: string;
}

const tasks = ref<Task[]>([
  { id: 1, label: 'Audit Vulnerability Kernel' },
  { id: 2, label: 'Optimasi DB Connection Pool' },
  { id: 3, label: 'Patch Hydration Mismatch SSR' }
]);

const moveUp = (index: number): void => {
  if (index === 0) return;
  const target = tasks.value[index];
  tasks.value.splice(index, 1);
  tasks.value.splice(index - 1, 0, target);
};

const moveDown = (index: number): void => {
  if (index === tasks.value.length - 1) return;
  const target = tasks.value[index];
  tasks.value.splice(index, 1);
  tasks.value.splice(index + 1, 0, target);
};
</script>

<template>
  <div class="queue-container">
    <h3>Urutan Eksekusi Sistem</h3>
    <TransitionGroup name="flip-list" tag="ul" class="task-list">
      <li v-for="(task, index) in tasks" :key="task.id" class="task-item">
        <span>{{ task.label }}</span>
        <div class="actions">
          <button 
            type="button" 
            :disabled="index === 0" 
            @click="moveUp(index)"
            aria-label="Pindahkan ke atas"
          >
            &uarr;
          </button>
          <button 
            type="button" 
            :disabled="index === tasks.length - 1" 
            @click="moveDown(index)"
            aria-label="Pindahkan ke bawah"
          >
            &darr;
          </button>
        </div>
      </li>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.queue-container {
  max-width: 480px;
  margin: 1rem auto;
  font-family: monospace;
}

.task-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.task-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  margin-bottom: 0.5rem;
  background: #1e1e24;
  color: #f7f7f7;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
}

/* FLIP Core Animation: Menggunakan translate murni */
.flip-list-move {
  transition: transform 0.3s cubic-bezier(0.25, 1, 0.5, 1);
}

.flip-list-enter-active,
.flip-list-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.flip-list-enter-from,
.flip-list-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

/* Pastikan elemen yang leave keluar dari flow agar animasi move berjalan mulus */
.flip-list-leave-active {
  position: absolute;
  width: 100%;
}
</style>
```

#### Practical Example: Enterprise Windowing Tab Orchestrator dengan LRU `<KeepAlive>`, `<Teleport>`, dan `<Suspense>`

Di bawah ini adalah sistem enterprise dashboard yang mengombinasikan cache management via `<KeepAlive>`, modal injection via `<Teleport>`, serta asinkron skeleton via `<Suspense>`.

```vue
<!-- components/EnterpriseWorkspace.vue -->
<script setup lang="ts">
import { ref, shallowRef, defineAsyncComponent, computed, onErrorCaptured } from 'vue';

// Definisikan dynamic async views
const AnalyticsView = defineAsyncComponent({
  loader: () => import('./views/AnalyticsView.vue'),
  delay: 200,
  timeout: 10000
});

const LiveOrderBookView = defineAsyncComponent({
  loader: () => import('./views/LiveOrderBookView.vue'),
  delay: 200,
  timeout: 10000
});

const AuditLogView = defineAsyncComponent({
  loader: () => import('./views/AuditLogView.vue'),
  delay: 200,
  timeout: 10000
});

type TabKey = 'Analytics' | 'OrderBook' | 'Audit';

interface TabConfig {
  key: TabKey;
  label: string;
  component: any;
}

const tabs: TabConfig[] = [
  { key: 'Analytics', label: 'Analisis Portofolio', component: AnalyticsView },
  { key: 'OrderBook', label: 'Live Order Book (L2)', component: LiveOrderBookView },
  { key: 'Audit', label: 'Security Logs', component: AuditLogView }
];

const activeTab = ref<TabKey>('Analytics');
const asyncError = ref<Error | null>(null);

// LRU Cache tracking array (Max 2 tabs di-cache bersamaan)
const CACHE_LIMIT = 2;
const cachedTabs = ref<TabKey[]>(['Analytics']);

const switchTab = (tab: TabKey): void => {
  asyncError.value = null;
  activeTab.value = tab;

  // Manual LRU Reordering logic
  const index = cachedTabs.value.indexOf(tab);
  if (index > -1) {
    cachedTabs.value.splice(index, 1);
  }
  cachedTabs.value.push(tab);

  if (cachedTabs.value.length > CACHE_LIMIT) {
    cachedTabs.value.shift(); // Depak tab paling lama tidak diakses
  }
};

const currentComponent = computed(() => {
  return tabs.find(t => t.key === activeTab.value)?.component;
});

// Error Boundary handling
onErrorCaptured((err: Error) => {
  asyncError.value = err;
  return false; // Stop error propagation
});
</script>

<template>
  <div class="workspace-wrapper">
    <header class="tab-bar" role="tablist">
      <button
        v-for="t in tabs"
        :key="t.key"
        role="tab"
        :aria-selected="activeTab === t.key"
        :class="['tab-button', { active: activeTab === t.key }]"
        @click="switchTab(t.key)"
      >
        {{ t.label }}
        <span v-if="cachedTabs.includes(t.key)" class="badge-cached">Cached</span>
      </button>
    </header>

    <main class="tab-viewport">
      <div v-if="asyncError" class="error-boundary-box" role="alert">
        <h4>Komponen Mengalami Kerusakan Kritis</h4>
        <p>{{ asyncError.message }}</p>
        <button @click="switchTab(activeTab)">Muat Ulang Komponen</button>
      </div>

      <router-view v-else v-slot="{ Component }">
        <Suspense>
          <template #default>
            <KeepAlive :include="cachedTabs" :max="CACHE_LIMIT">
              <component :is="currentComponent" :key="activeTab" />
            </KeepAlive>
          </template>
          <template #fallback>
            <div class="skeleton-wrapper" aria-busy="true">
              <div class="skeleton-line header-skeleton"></div>
              <div class="skeleton-grid">
                <div class="skeleton-card" v-for="i in 3" :key="i"></div>
              </div>
            </div>
          </template>
        </Suspense>
      </router-view>
    </main>

    <!-- Global App-level Floating Drawer via Teleport -->
    <Teleport to="#global-layer-root">
      <aside class="floating-teleport-status" aria-live="polite">
        <span>Active Tab: <strong>{{ activeTab }}</strong></span>
        <span>Allocated Cache: <strong>[{{ cachedTabs.join(', ') }}]</strong></span>
      </aside>
    </Teleport>
  </div>
</template>

<style scoped>
.workspace-wrapper {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0f111a;
  color: #e2e8f0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.tab-bar {
  display: flex;
  background: #1a1d2d;
  border-bottom: 1px solid #2d3748;
}

.tab-button {
  background: transparent;
  border: none;
  padding: 0.85rem 1.5rem;
  color: #a0aec0;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.2s ease;
}

.tab-button.active {
  color: #63b3ed;
  border-bottom: 2px solid #63b3ed;
  background: rgba(99, 179, 237, 0.05);
}

.badge-cached {
  font-size: 0.65rem;
  background: #2d3748;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
}

.tab-viewport {
  flex: 1;
  padding: 1.5rem;
  position: relative;
  overflow-y: auto;
}

/* Skeletons */
.skeleton-wrapper {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.skeleton-line {
  height: 32px;
  background: #1e2235;
  border-radius: 4px;
  animation: pulse 1.5s infinite ease-in-out;
}

.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

.skeleton-card {
  height: 140px;
  background: #1e2235;
  border-radius: 6px;
  animation: pulse 1.5s infinite ease-in-out;
}

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 0.2; }
}

.floating-teleport-status {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  background: #2b6cb0;
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-size: 0.75rem;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  display: flex;
  gap: 1rem;
  z-index: 10000;
}
</style>
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: High-Frequency Trading (HFT) Institutional Terminal
* **Platform:** Sistem dashboard sekuritas finansial dengan 40+ panel chart (TradingView canvas integration), real-time order books (WebSockets, 150 mutasi data/detik), dan transaksi order entry drawers.
* **Insiden:**
  1. Pengguna mengalami drop frame parah ($< 15\text{ FPS}$) dan tab browser sering *crash* (*Out of Memory / OOM*) setelah berpindah-pindah antar instrumen derivatif secara kontinu.
  2. Order Entry Modal yang dipicu dari dalam scrollable container terpotong (*clipped*) secara visual pada layar beresolusi ultrawide akibat CSS container `contain: paint` dan `overflow-x: scroll`.

#### Root Cause Analysis (RCA)
1. **OOM & DOM Memory Leak:** Tab menggunakan `<KeepAlive>` tanpa konfigurasi atribut `:max`, sehingga puluhan instrumen tersimpan permanen di memori. WebSocket listeners pada instrumen derivatif yang tidak aktif tetap berjalan karena siklus `onUnmounted` terhenti saat dibungkus `<KeepAlive>`.
2. **Stacking Context & Layout Clipping Bug:** Modal Drawer di-mount langsung di dalam DOM hierarchy tabel yang memiliki properti CSS `transform: translate3d(0,0,0)` untuk virtual-scroll optimization. Hal ini mendirikan *Stacking Context* terisolasi, mengabaikan `z-index: 9999` milik modal drawer.

#### Solusi Arsitektur
1. **Penerapan Dynamic Eviction Engine + Lifecycle Interception:**
   - Gunakan `<KeepAlive :max="3">` yang ketat.
   - Pindahkan seluruh *event loop listener* dan koneksi stream WebSocket berfrekuensi tinggi dari `onMounted`/`onUnmounted` ke `onActivated`/`onDeactivated`. Saat tab masuk mode hibernate, WebSocket stream di-pause atau di-*throttle* ke interval rendah.
2. **Teleport Escape Boundary:**
   - Seluruh drawer dan modal diisolasi menggunakan `<Teleport to="#dock-overlay-layer">`.
   - Element overlay ditempatkan sebagai *sibling langsung* dari tag `<body>`, membypass CSS containment dan stacking context milik container tabel virtual.

```
[WebSocket Inbound: 150 msg/s]
          |
          v
   +--------------+     onDeactivated()     +-----------------------------+
   |  Tab Active  | ----------------------> | Tab Suspended (KeepAlive)   |
   |              |                         | - Throttle stream ke 1 msg/s|
   | Full Render  | <---------------------- | - Detach Heavy WebGL Canvas |
   +--------------+      onActivated()      +-----------------------------+
```

---

### 9. Trade-offs

| Dimensi Arsitektural | Keuntungan Pendekatan | Konsekuensi & Trade-off Negatif | Mitigasi Enterprise |
| :--- | :--- | :--- | :--- |
| **KeepAlive Max Size** | Mengurangi latensi navigasi ke ~0ms (instan), menghemat load CPU untuk re-render VNode. | Konsumsi Heap Memory meningkat seiring akumulasi state; resiko retain memory leak dari closure. | Terapkan batas `:max` kecil (2-4); bersihkan payload data berukuran masif di hook `onDeactivated`. |
| **FLIP Transitions pada Data Masif** | Visual rendering sangat halus; layout bergeser secara alami (superior UX). | Eksekusi `getBoundingClientRect()` pada ratusan node anak memicu synchronous reflow beruntun (*Layout Thrashing*). | Batasi FLIP transisi hanya untuk slice item yang terlihat di viewport ($N \le 50$), gunakan Virtual Scrolling tanpa CSS enter/leave berlebihan. |
| **Teleport SSR Hydration** | Membebaskan layout dari batasan Stacking Context CSS di client. | Potensi *Hydration Mismatch* jika node target `#teleport-target` belum terbentuk di DOM saat proses hydration server berjalan. | Gunakan pola Client-Only wrapper atau pastikan teleport target dirender di luar alur hydration dinamis (misal tepat di akhir template `index.html`). |
| **JavaScript Animation Hooks (GSAP/WAAPI)** | Kontrol transisi kompleks secara absolut (timeline-based, interupsi, chaining). | Membebani Main Thread CPU. Jika JavaScript thread padat akibat komputasi state, animasi mengalami stuttering. | Utamakan CSS Transitions murni yang berjalan di *Compositor Thread* (`transform`, `opacity`), gunakan JS Hooks hanya jika kalkulasi posisi dinamis mutlak diperlukan. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Layout Thrashing pada Animasi `<TransitionGroup>`
* **Penyebab:** Melakukan animasi properti geometrik browser (seperti `height`, `width`, `top`, `margin-top`) di dalam class `*-move`.
* **Dampak:** Browser dipaksa menghitung ulang geometri (*Layout/Reflow*) pada setiap frame rendering (16.6ms), mengakibatkan UI lagging parah.
* **Solusi:** Hanya gunakan properti `transform` (misal: `translate`, `scale`) dan `opacity` yang diakselerasi langsung oleh GPU (Compositor-only properties).

#### 2. Zombie Listeners dalam Komponen `<KeepAlive>`
* **Penyebab:** Memasang interval timer (`setInterval`) atau global event listener (`window.addEventListener`) pada hook `onMounted`, dengan harapan akan di-cleanup di `onUnmounted`.
* **Dampak:** Komponen yang di-cache tidak pernah memanggil `onUnmounted` saat disembunyikan. Timer dan listener terus aktif di latar belakang, memakan resource CPU dan memicu eksekusi mutasi reaktif siluman.
* **Solusi:**

```typescript
// SALAH (Bocor di KeepAlive)
onMounted(() => window.addEventListener('resize', calculateLayout));
onUnmounted(() => window.removeEventListener('resize', calculateLayout));

// BENAR (Aman untuk KeepAlive)
onActivated(() => {
  window.addEventListener('resize', calculateLayout);
});
onDeactivated(() => {
  window.removeEventListener('resize', calculateLayout);
});
```

#### 3. Nested Transition Key Collision
* **Penyebab:** Menggunakan `<Transition mode="out-in">` di sekitar `<router-view>` tanpa menyediakan `:key` dinamis yang unik pada level component.
* **Dampak:** Vue menggunakan strategi reuse VNode secara default. Perubahan parameter URL (misal: dari `/users/1` ke `/users/2`) tidak memicu transisi keluar/masuk karena tipe komponen dianggap identik.
* **Solusi:**

```vue
<router-view v-slot="{ Component, route }">
  <Transition name="fade" mode="out-in">
    <component :is="Component" :key="route.fullPath" />
  </Transition>
</router-view>
```

#### 4. SSR Hydration Error dengan `<Teleport>`
* **Penyebab:** Melakukan teleport ke target DOM yang dibuat secara dinamis oleh komponen Vue lain yang belum ter-mount.
* **Dampak:** Error fatal runtime: `Cannot read properties of null (reading 'appendChild')` atau hydration mismatch warning.
* **Solusi:** Pasang guard reaktif memastikan komponen telah selesai di-mount di browser client:

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue';
const isMounted = ref(false);
onMounted(() => { isMounted.value = true; });
</script>

<template>
  <Teleport to="#modals-slot" v-if="isMounted">
    <div class="modal">Konten Modal</div>
  </Teleport>
</template>
```

---

### 11. Best Practices (Production Checklist)

| Kategori | Item Checklist | Status Wajib |
| :--- | :--- | :--- |
| **Transitions** | Properti `will-change: transform, opacity` dipasang hanya saat transisi aktif dan dihapus setelahnya untuk menghindari GPU memory bloat. | WAJIB |
| **Transitions** | Selalu definisikan `mode="out-in"` atau `mode="default"` secara eksplisit saat membungkus elemen dinamis dengan kondisi bersyarat (`v-if` / `v-else`). | WAJIB |
| **TransitionGroup** | Setiap item anak di `<TransitionGroup>` **HARUS** memiliki key unik berbasis identitas stabil (misal: `item.id`), bukan indeks array (`index`). | MUTLAK |
| **KeepAlive** | Komponen yang dibungkus `<KeepAlive>` wajib membatasi cache via `:max="N"` untuk mencegah unbounded memory leak. | MUTLAK |
| **KeepAlive** | Komponen yang memiliki koneksi persistent (WebSocket, EventSource, Timer) harus melepaskannya pada hook `onDeactivated`. | MUTLAK |
| **Teleport** | Target DOM (`to`) harus berada di luar cakupan container dengan CSS transform/filter untuk mencegah rusaknya stacking context. | WAJIB |
| **Teleport** | Komponen modal/overlay wajib mengimplementasikan Focus Trapping dan restorasi tombol Escape demi aksesibilitas WCAG 2.1 AAA. | WAJIB |
| **Suspense** | Semua tree `<Suspense>` produksi harus dipasangkan dengan hook `onErrorCaptured` pada parent container untuk mencegah blank screen. | MUTLAK |

---

### 12. Hands-on Practice

Dalam praktikum ini, kita akan membangun modul **Dynamic Resilient Workflow Engine** yang mengombinasikan FLIP reordering, state caching dengan batas LRU, dan overlay portal.

#### Struktur Direktori
Pastikan seluruh file tersimpan dengan struktur berikut di dalam `hands-on/m02/`:

```
hands-on/m02/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── src/
    ├── App.vue
    ├── main.ts
    ├── components/
    │   ├── DynamicTabHost.vue
    │   ├── ReorderPipeline.vue
    │   └── TransactionModal.vue
    └── views/
        ├── AnalyticsPanel.vue
        └── SettingsPanel.vue
```

#### Langkah 1: Persiapan Project & Konfigurasi
Jalankan inisialisasi pada terminal di workspace:

```bash
mkdir -p hands-on/m02/src/components hands-on/m02/src/views
cd hands-on/m02
```

Tulis file konfigurasi dependencies `package.json`:

```json
{
  "name": "enterprise-vue-builtins",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build"
  },
  "dependencies": {
    "vue": "^3.4.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "vue-tsc": "^1.8.0"
  }
}
```

Tulis konfigurasi `vite.config.ts`:

```typescript
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000
  }
});
```

Tulis entry point HTML `index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Vue Built-ins Lab</title>
</head>
<body style="margin: 0; background: #090a0f;">
  <div id="app"></div>
  <!-- Teleport Target Destination -->
  <div id="modal-portal-root"></div>
</body>
</html>
```

#### Langkah 2: Implementasi Dynamic Views untuk Testing KeepAlive

Tulis `src/views/AnalyticsPanel.vue`:

```vue
<script setup lang="ts">
import { ref, onMounted, onActivated, onDeactivated } from 'vue';

const counter = ref(0);
const logs = ref<string[]>([]);

const appendLog = (msg: string) => {
  logs.value.unshift(`[${new Date().toISOString().substring(11, 19)}] ${msg}`);
};

onMounted(() => appendLog('Component Initial Mount (DOM Ready)'));
onActivated(() => appendLog('Component Activated from KeepAlive Cache'));
onDeactivated(() => appendLog('Component Deactivated to KeepAlive Cache'));
</script>

<template>
  <div class="panel-card">
    <h3>Modul Analitik Finansial</h3>
    <div class="counter-box">
      <p>Local Reactive Counter: <strong>{{ counter }}</strong></p>
      <button @click="counter++">Tambah Counter State</button>
    </div>
    <div class="log-viewport">
      <h4>Lifecycle Execution Logs:</h4>
      <ul>
        <li v-for="(log, idx) in logs" :key="idx">{{ log }}</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.panel-card {
  background: #151824;
  padding: 1.5rem;
  border-radius: 8px;
  color: #e2e8f0;
}
.counter-box {
  margin-bottom: 1rem;
}
button {
  background: #3182ce;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}
.log-viewport {
  background: #0d0f17;
  padding: 1rem;
  border-radius: 4px;
  max-height: 180px;
  overflow-y: auto;
  font-family: monospace;
  font-size: 0.8rem;
}
ul { margin: 0; padding-left: 1.2rem; }
li { color: #48bb78; }
</style>
```

Tulis `src/views/SettingsPanel.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue';
const apiKey = ref('sk_live_enterprise_9983719482');
</script>

<template>
  <div class="panel-card">
    <h3>Konfigurasi Sistem</h3>
    <label>API Deployment Key:</label>
    <input v-model="apiKey" class="input-field" />
  </div>
</template>

<style scoped>
.panel-card {
  background: #151824;
  padding: 1.5rem;
  border-radius: 8px;
  color: #e2e8f0;
}
.input-field {
  width: 100%;
  padding: 0.5rem;
  background: #0d0f17;
  border: 1px solid #2d3748;
  color: #a0aec0;
  border-radius: 4px;
  margin-top: 0.5rem;
}
</style>
```

#### Langkah 3: Implementasi Modal Menggunakan `<Teleport>` & `<Transition>`

Tulis `src/components/TransactionModal.vue`:

```vue
<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue';

const props = defineProps<{
  isOpen: boolean;
  title: string;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && props.isOpen) {
    emit('close');
  }
};

onMounted(() => window.addEventListener('keydown', handleKeyDown));
onUnmounted(() => window.removeEventListener('keydown', handleKeyDown));
</script>

<template>
  <Teleport to="#modal-portal-root">
    <Transition name="modal-fade">
      <div v-if="isOpen" class="modal-backdrop" @click.self="emit('close')">
        <div class="modal-content" role="dialog" aria-modal="true">
          <header class="modal-header">
            <h4>{{ title }}</h4>
            <button class="close-btn" @click="emit('close')">&times;</button>
          </header>
          <div class="modal-body">
            <slot />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.modal-content {
  background: #1a1d2e;
  border: 1px solid #2d3748;
  border-radius: 8px;
  width: 90%;
  max-width: 500px;
  color: #fff;
  padding: 1.5rem;
  box-shadow: 0 10px 25px rgba(0,0,0,0.5);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: #a0aec0;
  cursor: pointer;
}

/* Transisi Modal Hardware Accelerated */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-fade-enter-active .modal-content,
.modal-fade-leave-active .modal-content {
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-from .modal-content,
.modal-fade-leave-to .modal-content {
  transform: scale(0.95) translateY(-10px);
}
</style>
```

#### Langkah 4: Root Application Assembly

Tulis `src/App.vue`:

```vue
<script setup lang="ts">
import { ref, shallowRef } from 'vue';
import AnalyticsPanel from './views/AnalyticsPanel.vue';
import SettingsPanel from './views/SettingsPanel.vue';
import TransactionModal from './components/TransactionModal.vue';

const currentView = shallowRef(AnalyticsPanel);
const currentViewName = ref('Analytics');
const isModalOpen = ref(false);

const setView = (view: any, name: string) => {
  currentView.value = view;
  currentViewName.value = name;
};
</script>

<template>
  <div class="app-layout">
    <nav class="nav-control">
      <button 
        :class="{ active: currentViewName === 'Analytics' }" 
        @click="setView(AnalyticsPanel, 'Analytics')"
      >
        Analitik
      </button>
      <button 
        :class="{ active: currentViewName === 'Settings' }" 
        @click="setView(SettingsPanel, 'Settings')"
      >
        Pengaturan
      </button>
      <button class="btn-action" @click="isModalOpen = true">Buka Transaksi Portal</button>
    </nav>

    <div class="view-viewport">
      <Transition name="view-slide" mode="out-in">
        <KeepAlive :max="2">
          <component :is="currentView" />
        </KeepAlive>
      </Transition>
    </div>

    <TransactionModal 
      :isOpen="isModalOpen" 
      title="Validasi Blok Transaksi" 
      @close="isModalOpen = false"
    >
      <p>Data payload siap disubmit langsung via Teleport portal layer.</p>
    </TransactionModal>
  </div>
</template>

<style>
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  background: #090a0f;
}

.app-layout {
  padding: 2rem;
  max-width: 800px;
  margin: 0 auto;
}

.nav-control {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
}

.nav-control button {
  padding: 0.6rem 1.2rem;
  background: #1a1d2e;
  color: #a0aec0;
  border: 1px solid #2d3748;
  border-radius: 4px;
  cursor: pointer;
}

.nav-control button.active {
  background: #3182ce;
  color: white;
  border-color: #3182ce;
}

.nav-control .btn-action {
  margin-left: auto;
  background: #38a169;
  color: white;
  border: none;
}

/* Page Slide Transition */
.view-slide-enter-active,
.view-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.view-slide-enter-from {
  opacity: 0;
  transform: translateX(15px);
}

.view-slide-leave-to {
  opacity: 0;
  transform: translateX(-15px);
}
</style>
```

Tulis `src/main.ts`:

```typescript
import { createApp } from 'vue';
import App from './App.vue';

const app = createApp(App);
app.mount('#app');
```

Jalankan perintah pengujian:
```bash
npm install
npm run dev
```
Uji fungsionalitas:
1. Naikkan angka counter pada tab **Analitik**.
2. Berpindahlah ke tab **Pengaturan**, kemudian kembali lagi ke **Analitik**. Perhatikan bahwa state counter tidak ter-reset, membuktikan bahwa VNode subTree dipertahankan oleh `<KeepAlive>`.
3. Buka tombol "Buka Transaksi Portal". Buka Inspect Element, periksa bahwa modal fisik terletak tepat di bawah node `<div id="modal-portal-root">`, bukan di dalam `<div id="app">`.

---

### 13. Exercise

#### Tingkat Easy: Basic `<Transition>` with Mode Configuration
* **Tugas:** Buat komponen konfirmasi toggle tombol sederhana (Tombol A: "Kunci Vault", Tombol B: "Buka Vault").
* **Syarat:**
  - Gunakan `v-if` / `v-else`.
  - Bungkus menggunakan `<Transition>` dengan `mode="out-in"`.
  - Pasang transisi fade & scale menggunakan transisi CSS murni (`opacity`, `transform`).
  - Cegah layout melompat (*flickering layout jump*) saat proses pergantian elemen terjadi.

#### Tingkat Medium: Nested Dynamic Transitions with Vue Router Simulation
* **Tugas:** Bangun komponen navigasi multi-step form wizard (Step 1, Step 2, Step 3).
* **Syarat:**
  - Arah animasi harus dinamis: Jika pengguna mengklik tombol "Next", step baru bergeser dari kanan ke kiri (`slide-left`). Jika mengklik tombol "Back", step bergeser dari kiri ke kanan (`slide-right`).
  - Manfaatkan dynamic transition name binding: `<Transition :name="transitionDirection">`.
  - State setiap form input pada tiap langkah tidak boleh hilang ketika pengguna bergerak bolak-balik (gunakan konfigurasi `<KeepAlive>`).

#### Tingkat Hard: LRU Cache Size Limiter with Memory Snapshot
* **Tugas:** Bangun abstraction wrapper component `<KeepAliveLRU :max="3">` kustom yang terhubung ke Pinia Store.
* **Syarat:**
  - Komponen menerima list keys dinamis dari props.
  - Saat eviction terjadi (komponen tertua dibuang dari cache), sistem harus memicu custom callback `onEvict(componentKey)` yang mencatat total memory release dan menyimpan serialisasi state form terakhir ke LocalStorage secara terisolasi.
  - Jika komponen yang didepak diakses kembali di masa mendatang, state harus di-rehidrasi kembali ke form secara transparan tanpa merusak Virtual DOM lifecycle.

---

### 14. Challenge

#### Skenario Kompleks Enterprise: Dynamic Canvas-Dashboard Workspace dengan Zero-Leak Lifecycle & Fluid FLIP Orchestration

**Deskripsi Tantangan:**
Perusahaan Anda mengelola platform Business Intelligence realtime berskala besar. Dashboard memiliki 20 jenis widget analisis modular (grafik WebGL, real-time WebSocket tabular logs, SVG maps). Pengguna dapat menambah, menghapus, mengubah posisi (drag-and-drop sort), serta meminimalkan widget ke tab bar bawah.

**Spesifikasi Persyaratan:**
1. **Dynamic Grid FLIP:**
   - Seluruh mutasi urutan posisi widget akibat interaksi drag-and-drop wajib dianimasikan menggunakan alur teknik FLIP murni pada `<TransitionGroup>`.
   - Animasi harus 60 FPS terkunci, dilarang menyebabkan reflow beruntun (ukur via Chrome DevTools Rendering -> *Rendering: Paint Flashing*).
2. **Aggressive Resource Teardown on KeepAlive Deactivation:**
   - Widget WebGL/Canvas yang di-minimize ke tab bar harus dibungkus oleh `<KeepAlive :max="5">`.
   - Saat hook `onDeactivated` terpanggil: konteks rendering WebGL wajib melepaskan buffer texture VRAM ke GPU memory, namun menyimpan koordinat kamera 3D terakhir di objek JavaScript ringan.
   - Saat hook `onActivated` terpanggil: bangun kembali buffer WebGL seketika tanpa flicker visual yang terdeteksi user.
3. **Stacked Modals & Popover Isolation via Dynamic Portal Tree:**
   - Setiap widget dapat membuka modal konfigurasinya sendiri, dan dari modal tersebut dapat dibuka tooltip atau submenu dropdown.
   - Seluruh layer visual ini harus di-teleportasi ke container `#portal-engine` di root, dengan preservasi otomatis hierarki `z-index` terhitung (computed z-index stacking order) tanpa konflik class selector.
4. **Resilient Suspense Layer:**
   - Gunakan `<Suspense>` untuk merender widget secara modular. Jika satu widget gagal terhubung ke backend analytics (Promise reject), hanya widget tersebut yang merender error boundary state lokal. Widget lain di dalam grid tidak boleh terganggu pemuatannya (*Isolation Boundary*).

**Kriteria Keberhasilan:**
- Kode ditulis sepenuhnya dengan TypeScript `strict: true`.
- Zero memory leakage: Lakukan profiling snapshot heap memory pada browser; tidak ada retain detached DOM elements setelah 100 kali aksi minimize/restore widget.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (5 Soal)

##### 1. Mengapa properti CSS seperti `height` atau `top` dihindari saat membuat transisi animasi pada Vue, dan disarankan menggunakan `transform`?
* A. Browser tidak mendukung CSS transitions untuk properti `height`.
* B. Mutasi `height` dan `top` memicu tahapan Layout (Reflow) pada Browser Rendering Pipeline yang berbiaya komputasi CPU mahal, sedangkan `transform` diproses di Compositor Thread oleh GPU.
* C. Virtual DOM Vue tidak dapat melacak perubahan koordinat dari properti non-transform.
* D. Properti `transform` secara otomatis membersihkan memori Virtual DOM saat transisi berakhir.

##### 2. Pada komponen `<Transition>`, apa fungsi dari atribut `mode="out-in"`?
* A. Memaksa animasi masuk (enter) dan animasi keluar (leave) dieksekusi secara simultan di frame yang sama.
* B. Memastikan elemen lama yang keluar menyelesaikan animasi leave-nya terlebih dahulu sebelum elemen baru dimasukkan ke DOM.
* C. Mengaktifkan mode rendering out-of-order execution pada Virtual DOM renderer.
* D. Menginstruksikan Vue untuk merender elemen di luar kontainer root aplikasi.

##### 3. Komponen abstrak `<KeepAlive>` secara default mencocokkan target caching menggunakan apa?
* A. Nama tag HTML elemen root di dalam template.
* B. Nilai properti `name` dari komponen yang dibungkus atau nama file komponen jika menggunakan SFC.
* C. Nilai CSS class ID dari elemen pembungkus terluar.
* D. Timestamp saat komponen pertama kali di-mount.

##### 4. Di mana letak node fisik DOM dari komponen yang dibungkus oleh `<Teleport to="#layer">` pada output akhir dokumen browser?
* A. Tetap berada di bawah elemen parent di mana `<Teleport>` dituliskan dalam template.
* B. Dihapus secara total dari dokumen DOM dan disimpan di Shadow Root memory.
* C. Dipindahkan secara fisik sebagai child langsung dari elemen dengan ID `layer`.
* D. Di-duplikasi: satu di lokasi asal dan satu di target `#layer`.

##### 5. Hook siklus hidup mana yang dipicu pada komponen saat komponen tersebut disembunyikan di dalam struktur `<KeepAlive>`?
* A. `onUnmounted`
* B. `onDestroyed`
* C. `onDeactivated`
* D. `onBeforeUnmount`

---

#### B. Pertanyaan Intermediate (5 Soal)

##### 6. Pada implementasi algoritma FLIP dalam `<TransitionGroup>`, apa yang sebenarnya terjadi pada fase "Invert"?
* A. Urutan array reaktif di-reverse (dibalik) dari indeks akhir ke awal.
* B. Vue membaca koordinat First dan Last, lalu segera menerapkan inline transform berupa selisih delta koordinat untuk membatalkan pergeseran fisik sehingga elemen tampak diam di posisi asal.
* C. Engine membalikkan nilai `opacity` dari 1 menjadi 0 untuk menyembunyikan kalkulasi render.
* D. Renderer menukar status bitmask VNode dari `MOUNTED` menjadi `UNMOUNTED`.

##### 7. Apa yang terjadi jika atribut `:key` pada anak langsung dari `<TransitionGroup>` diisi menggunakan indeks array perulangan (`v-for="(item, index) in items" :key="index"`) saat sebuah item dihapus dari tengah list?
* A. Vue memunculkan pesan error kompilasi dan menolak me-render template.
* B. Animasi FLIP gagal mengidentifikasi pergerakan fisik elemen secara presisi, karena elemen sesudahnya akan mengambil alih indeks yang ditinggalkan, menyebabkan artefak visual dan kehilangan animasi transisi `move`.
* C. Elemen terakhir dari list akan terhapus secara permanen dari memory Heap.
* D. Seluruh list akan di-unmount dan di-mount ulang dari awal tanpa transisi.

##### 8. Di balik layar, mengapa `<Teleport>` tetap memungkinkan reactive state props dan event propagation (`$emit`) terhubung lancar ke parent asalnya meskipun letak DOM fisiknya berada di tempat lain?
* A. `<Teleport>` menduplikasi instance Vue secara menyeluruh ke target container.
* B. Virtual DOM parent-child hierarchy tree tetap dipertahankan utuh pada memori runtime core, yang dipisahkan secara terisolasi dari penempatan fisik real DOM tree.
* C. Komunikasi dilakukan melalui mekanisme window `postMessage` internal browser.
* D. Event dilewatkan melalui global root broadcast event emitter bawaan DOM.

##### 9. Apa fungsi properti bitmask `ShapeFlags.COMPONENT_KEPT_ALIVE` di dalam engine reconciler Vue 3?
* A. Menandakan bahwa instance komponen harus di-destroy secara paksa saat memori browser penuh.
* B. Memberi instruksi pada renderer patcher agar tidak memanggil `unmountComponent()`, melainkan mengalihkan operasi ke pelepasan DOM fisik via `hostRemove()` sembari mempertahankan instance VNode di memori cache.
* C. Mengabaikan eksekusi custom directive pada komponen tersebut.
* D. Mengunci reaktivitas agar state di dalam komponen menjadi immutable (read-only).

##### 10. Mengapa komponen anak di dalam `<Suspense>` dapat memblokir rendering slot `#default`?
* A. Karena komponen anak menggunakan async function pada event listeners miliknya.
* B. Karena fungsi `setup()` milik komponen anak (atau `<script setup>` tingkat teratas) mengembalikan `Promise` yang masih berstatus pending.
* C. Karena komponen anak belum selesai men-download stylesheet CSS eksternal.
* D. Karena komponen anak memiliki ukuran bundle javascript lebih dari 500 KB.

---

#### C. Skenario Kasus Produksi (3 Soal)

##### 11. Skenario Kasus: Memory Leak Tab Dashboard Keuangan
Sebuah dashboard analitik trading menggunakan `<KeepAlive>` untuk menyimpan 10 tab instrumen trading. Setiap tab menginstansiasi library chart pihak ketiga (seperti Canvas/WebGL engine) dan memasang WebSocket listener langsung ke bursa. Setelah berpindah tab bolak-balik selama 2 jam, konsumsi memori browser melonjak dari 120MB menjadi 2.8GB, menyebabkan browser tab mengalami force closed (OOM Crash).

* **Analisis Pertanyaan:**
  Identifikasi secara presisi penyebab kebocoran memori ini meskipun `<KeepAlive>` dirancang untuk efisiensi render. Langkah-langkah rekayasa software apa yang harus diterapkan untuk mengeliminasi memory leak tanpa mengorbankan fungsionalitas caching state input data pengguna?

##### 12. Skenario Kasus: Stacking Context & Transform Clipping pada Teleport
Sebuah tim frontend memindahkan modal dialog lama ke komponen `<Teleport to="#modal-layer">`. Namun, saat modal dibuka, posisinya tampak terdistorsi dan tidak mengisi seluruh viewport screen (`position: fixed; width: 100vw; height: 100vh` terpotong di tengah layar). Setelah ditelusuri pada CSS DOM inspector, elemen `<div id="modal-layer">` berada di dalam sebuah wrapper layout `<div class="dashboard-shell">` yang memiliki properti CSS `filter: drop-shadow(...)` dan `transform: translateZ(0)`.

* **Analisis Pertanyaan:**
  Jelaskan secara spesifik menurut standar CSS Compositing and Blending W3C mengapa `position: fixed` pada modal gagal berfungsi relatif terhadap viewport browser dalam skenario ini. Bagaimana arsitektur penempatan portal DOM yang valid untuk skala enterprise?

##### 13. Skenario Kasus: FLIP Animation Churn pada Data Table 10.000 Baris
Sebuah aplikasi ERP memuat data tabel 1.000 baris data aktif. Tim memasang `<TransitionGroup name="table-flip" tag="tbody">` pada list tersebut. Ketika pengguna mengklik fitur "Sort by Revenue", browser mengalami freezing total selama kurang lebih 850 milidetik sebelum animasi dimulai, menghasilkan status *Long Task (>50ms)* pada Core Web Vitals (INP - Interaction to Next Paint melonjak buruk).

* **Analisis Pertanyaan:**
  Bedah apa yang dieksekusi oleh JavaScript engine dan browser rendering pipeline pada rentang 850 milidetik tersebut terkait cara kerja internal FLIP `<TransitionGroup>`. Berikan rancangan arsitektur alternatif yang menjaga fluiditas transisi tabel tanpa membebani thread rendering utama browser.

---

### Kunci Jawaban & Pembahasan Evaluasi

#### Jawaban Pertanyaan Basic
1. **B — Mutasi `height` dan `top` memicu tahapan Layout (Reflow)...**
   *Pembahasan:* Animasi berbasis layout (`height`, `top`, `margin`) memaksa browser mengeksekusi *Recalculate Style*, *Layout/Reflow*, *Paint*, dan *Composite* pada setiap frame. Sebaliknya, properti `transform` dan `opacity` melewati tahap layout dan paint, langsung diproses oleh GPU pada *Compositor Thread*, menghindari frame dropping.
2. **B — Memastikan elemen lama yang keluar menyelesaikan animasi leave-nya terlebih dahulu...**
   *Pembahasan:* Tanpa `mode="out-in"`, elemen baru yang masuk (enter) dan elemen lama yang keluar (leave) akan hadir di DOM secara bersamaan pada waktu tertentu, yang umumnya merusak layout visual antarmuka pengguna kecuali diberi positioning absolut.
3. **B — Nilai properti `name` dari komponen...**
   *Pembahasan:* Atribut `include` dan `exclude` pada