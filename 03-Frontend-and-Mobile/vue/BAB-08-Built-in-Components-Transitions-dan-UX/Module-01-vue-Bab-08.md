# Bab 08 Module 01: Built-in Components, Transitions, & UX

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum**: `03-Frontend-and-Mobile`
*   **Teknologi Utama**: Vue 3 (Core Engine, Composition API, `<script setup>`)
*   **Modul**: `Bab 08 Module 01`
*   **Topik**: `Built-in Components, Transitions, & UX`
*   **Prasyarat Kognitif**:
    *   Penguasaan Vue 3 Virtual DOM (VNode lifecycle) & Reactivity System Engine (`Proxy`, `Ref`, `Reactive`).
    *   Pemahaman siklus hidup komponen (`onMounted`, `onUnmounted`, `onActivated`, `onDeactivated`).
    *   Pemahaman browser rendering pipeline: Parsing $\rightarrow$ Style $\rightarrow$ Layout (Reflow) $\rightarrow$ Paint $\rightarrow$ Compositing.
    *   Konsep CSS Transitions, CSS Animations, dan asynchronous DOM updating batching via microtask queue.
*   **Target Engine Target**: Vue.js $\ge 3.4.x$, Modern ECMAScript (ES2023+), Modern Evergreen Browsers (Chrome 120+, Safari 17+, Firefox 120+).

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, engineer diharapkan memiliki kemampuan definitif untuk:

1.  **Mendekomposisi dan Mengonfigurasi Komponen Inti Vue Engine**: Mengimplementasikan `<Transition>`, `<TransitionGroup>`, `<KeepAlive>`, dan `<Teleport>` pada level produksi enterprise tanpa menimbulkan memory leak atau degradasi performa compositing.
2.  **Menguasai Transisi Siklus Hidup Virtual DOM**: Mengendalikan mutasi VNode saat rendering kondisional (`v-if`, `v-show`, komponen dinamis) menggunakan 6 fase transisi CSS kelas inti Vue serta hook JavaScript berbasis asynchronous control flow (`done()` callback dan Web Animations API).
3.  **Mengoptimalkan State Caching Tingkat Lanjut**: Merancang arsitektur caching dynamic component berbasis LRU (Least Recently Used) menggunakan `<KeepAlive>` dengan integrasi lifecycle hooks spesifik (`onActivated`, `onDeactivated`) serta mitigasi state staling.
4.  **Mencegah Frame Drops & Layout Thrashing**: Menghubungkan eksekusi animasi dengan GPU acceleration (`transform`, `opacity`, `will-change`) serta menghindari paksaan reflow melalui synchronous layout queries di dalam transisi JavaScript.
5.  **Menangani Portal Rendering Aman Berstandar Web Content Accessibility Guidelines (WCAG)**: Memproyeksikan subtree DOM ke target target eksternal via `<Teleport>` dengan mempertahankan context reactivity, scope style, fokus aksesibilitas keyboard (Focus Trap), dan proteksi z-index context collision.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model 1: Intersepsi Siklus Hidup VNode oleh `<Transition>`
Vue bukan sebuah pustaka animasi; Vue adalah sebuah *state reconciler*. Ketika VNode masuk (*insert*) atau keluar (*remove*) dari Virtual DOM tree:
*   Secara normal, DOM node langsung disisipkan via `Node.insertBefore()` atau dihapus via `Node.removeChild()`.
*   `<Transition>` bertindak sebagai **interseptor siklus hidup rendering**. Saat node keluar, `<Transition>` menunda pemanggilan `Node.removeChild()` yang sebenarnya hingga seluruh transisi CSS selesai (dideteksi via `transitionend`/`animationend`) atau hingga hook JavaScript `leave(el, done)` memanggil fungsi `done()`.
*   Pengembang harus memandang `<Transition>` sebagai *wrapper kontraktual* yang memanipulasi waktu eksekusi patching DOM browser, bukan generator CSS dinamis secara langsung.

```
Mutasi State (v-if = false)
       │
       ▼
[Virtual DOM Reconciler: Mark node as unmounted]
       │
       ├─► Tanpa <Transition>: Node.removeChild() seketika di-flush ke DOM.
       │
       └─► Dengan <Transition>: 
             1. Tambahkan kelas .*-leave-from, inject .*-leave-active
             2. Delay Node.removeChild()
             3. Tunggu event 'transitionend'
             4. Flush Node.removeChild() dari DOM nyata.
```

### Mental Model 2: Subtree Persistence dan LRU Cache pada `<KeepAlive>`
`<KeepAlive>` bukanlah peredam `v-show`.
*   `v-show` mempertahankan node fisik di dalam DOM tree nyata dan hanya memanipulasi deklarasi `display: none`. Implikasinya: memory footprint DOM tetap ada, style sheet engine tetap memproses selector, namun komponen tidak pernah di-unmount.
*   `<KeepAlive>` meng-unmount node fisik dari **Live DOM Tree**, tetapi menahan instance komponen internal, VNode tree, dan reactive scope-nya di dalam **In-Memory Cache (LRU cache)**.
*   Komponen tidak dihancurkan (lifecycle `onUnmounted` tidak dipanggil), melainkan ditidurkan (*deactivated*). Saat disisipkan kembali, DOM dipasang ulang secara instan tanpa re-initialisasi state atau inisiasi network request ulang yang tidak perlu.

### Mental Model 3: `<Teleport>` Bukan Pemecah Reactivity Scope
Ketika elemen di-teleportasi ke target lain di luar root aplikasi (misal `to="body"`):
*   Secara fisik (Real DOM), node tersebut direlokasi di bawah hierarki elemen target.
*   Secara logis (Virtual DOM Tree & Component Tree), node tersebut **tetap merupakan anak langsung** dari komponen induk pemanggilnya.
*   Scope injeksi dependensi (`provide`/`inject`), alur reactive state, dan event bubbling tetap berjalan mengikuti struktur Virtual DOM pohon komponen Vue, bukan pohon HTML DOM native.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Siklus Hidup Transisi CSS: Entering & Leaving

```
MASUK (ENTER TRANSITION)
─────────────────────────────────────────────────────────────────────────────
Frame:         Frame 0 (Pre-insert)   Frame 1 (Post-insert)   Frame N (Final)
VNode:         [Unmounted]            [Mounted to Real DOM]   [Active]
Classes:       v-enter-from           v-enter-to              (Semua class
               v-enter-active ──────► v-enter-active ───────► transisi dilepas)
Events:        before-enter           enter                   after-enter


KELUAR (LEAVE TRANSITION)
─────────────────────────────────────────────────────────────────────────────
Frame:         Trigger State = false  Frame 1 (Next Frame)    Anim End (Final)
VNode:         [Active]               [Leave In-Flight]       [Destroyed/Detached]
Classes:       v-leave-from           v-leave-to              Node.removeChild()
               v-leave-active ──────► v-leave-active ───────► (Class dihapus)
Events:        before-leave           leave                   after-leave
```

### 2. Alur Eksekusi Internal `<KeepAlive>` Cache Strategy

```
Dynamic Component Render Request (<component :is="activeComponent">)
                            │
                            ▼
               Apakah Target VNode valid?
                     ├─ Tidak ──► Render VNode langsung
                     └─ Ya
                            │
                            ▼
           Daftar Match `include` & `exclude`?
                     ├─ Tidak ──► Render langsung tanpa cache
                     └─ Ya
                            │
                            ▼
              Periksa Cache Map internal KeepAlive
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
       [CACHE HIT]                    [CACHE MISS]
            │                               │
  Ambil cached Subtree            Instansiasi Komponen Baru
  Ambil saved Component Instance  Mount DOM Node fisik
            │                               │
  Update LRU Key Sequence                   │
  (Pindahkan key ke akhir daftar)           │
            │                               │
  Sematkan bendera `shapeFlag`:             │
  COMPONENT_KEPT_ALIVE                      │
            │                               ▼
            │                     Simpan VNode ke Cache Map
            │                     Periksa limit `max`:
            │                     Jika keys.length > max:
            │                       Prune key terlama (index 0)
            │                       Jalankan destroy instance target
            ▼                               ▼
    Mount Cached DOM                Mount Fresh DOM
            │                               │
            ▼                               ▼
  Invoke `onActivated()`          Invoke `onMounted()`
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Mekanisme Internal `<Transition>`
`<Transition>` adalah functional built-in component yang tidak me-render elemen fisiknya sendiri (komponen transparan tingkat tinggi). Implementasi internalnya membungkus VNode anaknya dengan sejumlah lifecycle navigation guards:

1.  **Ekstraksi Child Node tunggal**:
    `<Transition>` memeriksa VNode children melalui slot default. Jika terdapat lebih dari 1 node (kecuali terbungkus `v-if`/`v-else`), engine melempar warning run-time.
2.  **Hook Injection via `cloneVNode`**:
    Engine menyuntikkan transisi metadata hooks (`transition` object) langsung ke instance VNode anak:
    *   `beforeEnter(el)`: Membaca style awal, menerapkan kelas CSS `.v-enter-from` dan `.v-enter-active`.
    *   `enter(el)`: Pada tick frame berikutnya (`requestAnimationFrame`), menghapus `.v-enter-from` dan menambahkan `.v-enter-to`.
    *   `leave(el, rm)`: Menyuntikkan callback `rm` (fungsi native `parent.removeChild(el)`) ke dalam hook `onComplete` dari CSS transition detection logic.
3.  **Deteksi Event Transisi**:
    Vue menginspeksi properti computed CSS dari elemen (`window.getComputedStyle(el)`) untuk menentukan apakah transisi menggunakan CSS `transition` atau `animation`. Engine mengukur nilai `transition-duration`, `transition-delay`, `animation-duration`, dan `animation-delay` secara matematis untuk menjadwalkan batas waktu absolut (timeout fallback) pencegah memory leak jika browser gagal memicu event `transitionend`.

### Mekanisme Internal `<TransitionGroup>`
Berbeda dari `<Transition>`, `<TransitionGroup>`:
1.  **Merender Node Pembungkus Nyata**: Menggunakan prop `tag` (default: `Fragment` pada Vue 3).
2.  **FLIP Animation Engine**:
    Untuk menangani perpindahan urutan item (reordering), Vue mengimplementasikan teknik **FLIP** (*First, Last, Invert, Play*):
    *   **First**: Membaca koordinat awal setiap anak melalui `getBoundingClientRect()` sebelum DOM dimutasi.
    *   **Last**: Memperbarui state reactive, membiarkan DOM memperbarui posisi elemen secara logis, lalu membaca kembali koordinat barunya via `getBoundingClientRect()`.
    *   **Invert**: Menghitung $\Delta x = x_1 - x_2$ dan $\Delta y = y_1 - y_2$. Menyuntikkan style inline: `transform: translate(Δx px, Δy px); transition: transform 0s;` secara seketika sehingga elemen terlihat tetap di koordinat awal.
    *   **Play**: Pada frame berikutnya, menghapus inline transform dan menambahkan kelas `.v-move`. Elemen meluncur secara mulus dari posisi inverse ke posisi aslinya menggunakan akselerasi GPU.

### Mekanisme Internal `<KeepAlive>`
Komponen ini diimplementasikan menggunakan arsitektur cache berbasis `Map<CacheKey, VNode>` dan `Set<CacheKey>` untuk pelacakan LRU.
*   **Instance Pinning**: `<KeepAlive>` menahan referensi VNode internal dan `componentInstance`.
*   **Subtree Deactivation**: Alih-alih merusak instance saat navigasi keluar, host runtime container memanggil platform-specific operator untuk melepas DOM node dari parent (`container.removeChild(el)`), lalu mengubah `shapeFlag` VNode menjadi non-active.
*   **Direct Mutation Prevention**: Reactivity scope tidak dihentikan; subscriber effect tetap aktif. Oleh karena itu, modifikasi state global yang diobservasi oleh komponen yang ditidurkan akan tetap memicu pembaruan Virtual DOM secara internal, namun DOM patch sebenarnya ditunda hingga komponen diaktifkan kembali (`onActivated`).

### Mekanisme Internal `<Teleport>`
`<Teleport>` memiliki implementasi tingkat rendah khusus pada level renderer Vue (`renderer.ts`):
1.  Engine menerima parameter `to` (string CSS selector atau referensi HTMLElement).
2.  Renderer memvalidasi apakah target selector ada di DOM nyata saat komponen di-mount.
3.  Target relokasi dipertahankan pada instance VNode sebagai `targetAnchor`. Subtree DOM anak dibuat dan disisipkan langsung ke bawah `targetElement` menggunakan `target.insertBefore(el, anchor)` platform DOM API.
4.  Pemisahan ini tidak memutus rantai parent-child pada pohon komponen logis internal; context injection, custom events, dan props cascading tetap mempertahankan hirarki deklarasi SFC-nya.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Transisi Berbasis State: Mode Transisi (`mode="out-in"` vs `"in-out"`)
Secara default, transisi elemen masuk dan elemen keluar terjadi secara simultan (*simultaneous rendering*). Pada tata letak dokumen normal (Normal Document Flow), ini memicu masalah layout:

$$\text{Simultaneous Rendering} \implies \text{Node Baru Masuk} + \text{Node Lama Keluar Ada di DOM} \implies \text{Layout Jitter / Stacking Shift}$$

*   **Mode `default`**: Node masuk dan keluar diproses di frame yang sama. Keduanya menempati ruang render bersamaan, menyebabkan elemen di bawahnya terdorong ke bawah secara drastis sebelum node lama dihapus.
*   **Mode `out-in`**: Node saat ini dianimasikan keluar terlebih dahulu. Engine menunggu hingga transisi keluar selesai secara absolut (`leave` sequence complete), baru me-mount dan menganimasikan node baru. Ini menjamin kestabilan dimensi kontainer penampung.
*   **Mode `in-out`**: Node baru dianimasikan masuk terlebih dahulu. Setelah selesai, node lama baru dianimasikan keluar. Mode ini jarang digunakan, umumnya terbatas pada efek penumpukan kartu (*card deck swaps*).

### Algoritma Least Recently Used (LRU) Cache pada `<KeepAlive>`
Ketika properti `:max="N"` dideklarasikan, engine menerapkan strategi pruning LRU ketat untuk membatasi konsumsi memori heap:

1.  Disediakan sebuah set `keys: Set<CacheKey>` yang mempertahankan urutan insersi (insertion-order preservation).
2.  Setiap kali komponen diakses (baik instansiasi baru maupun pemulihan via cache hit):
    *   Jika key sudah ada di `keys`, key tersebut dihapus dari lokasinya saat ini dan ditambahkan kembali ke akhir set:
        $$\text{keys.delete(key)} \implies \text{keys.add(key)}$$
3.  Jika jumlah elemen dalam `keys` melampaui ambang batas $N$:
    *   Ambil key paling usang dari iterator:
        $$\text{oldestKey} = \text{keys.values().next().value}$$
    *   Hapus referensi dari cache:
        $$\text{cache.delete(oldestKey)}$$
    *   Panggil metode internal `pruneCacheEntry(entry)` yang secara eksplisit menjalankan siklus unmount penuh pada komponen instance yang dibuang tersebut (`destroy(entry.component)`), melepaskan seluruh event listeners, dan membebaskan memori heap dari DOM subtree yang tidak terpakai.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi komprehensif yang mendemonstrasikan kombinasi `<KeepAlive>`, dynamic component, transisi mode `out-in`, transisi berbasis Javascript Hooks, dan `<Teleport>` yang dikemas dalam arsitektur komponen modular.

```vue
<!-- AppWorkspace.vue -->
<script setup lang="ts">
import { ref, shallowRef, defineAsyncComponent, type Component } from 'vue';

// Menggunakan shallowRef untuk performa komponen dinamis
const AnalysisTab = defineAsyncComponent(() => import('./tabs/AnalysisTab.vue'));
const MetricsTab = defineAsyncComponent(() => import('./tabs/MetricsTab.vue'));

interface TabItem {
  id: string;
  name: string;
  component: Component;
}

const tabs: TabItem[] = [
  { id: 'analysis', name: 'System Analysis', component: AnalysisTab },
  { id: 'metrics', name: 'Real-time Metrics', component: MetricsTab }
];

const activeTabId = ref<string>('analysis');
const currentComponent = shallowRef<Component>(AnalysisTab);

const switchTab = (tab: TabItem) => {
  activeTabId.value = tab.id;
  currentComponent.value = tab.component;
};

// JavaScript Transition Hooks dengan Web Animations API
const onBeforeEnter = (el: Element): void => {
  const htmlEl = el as HTMLElement;
  htmlEl.style.opacity = '0';
  htmlEl.style.transform = 'translateY(12px) scale(0.98)';
};

const onEnter = (el: Element, done: () => void): void => {
  const htmlEl = el as HTMLElement;
  const animation = htmlEl.animate(
    [
      { opacity: 0, transform: 'translateY(12px) scale(0.98)' },
      { opacity: 1, transform: 'translateY(0px) scale(1)' }
    ],
    {
      duration: 250,
      easing: 'cubic-bezier(0.16, 1, 0.3, 1)',
      fill: 'forwards'
    }
  );
  
  animation.onfinish = () => {
    done();
  };
};

const onLeave = (el: Element, done: () => void): void => {
  const htmlEl = el as HTMLElement;
  const animation = htmlEl.animate(
    [
      { opacity: 1, transform: 'scale(1)' },
      { opacity: 0, transform: 'scale(0.96)' }
    ],
    {
      duration: 180,
      easing: 'cubic-bezier(0.7, 0, 0.84, 0)',
      fill: 'forwards'
    }
  );

  animation.onfinish = () => {
    done();
  };
};
</script>

<template>
  <main class="workspace-container">
    <nav class="tab-navigation" aria-label="Workspace Tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-button', { active: activeTabId === tab.id }]"
        @click="switchTab(tab)"
      >
        {{ tab.name }}
      </button>
    </nav>

    <div class="viewport-stage">
      <!-- Transisi out-in dengan keep-alive ber-limit -->
      <Transition
        mode="out-in"
        :css="false"
        @before-enter="onBeforeEnter"
        @enter="onEnter"
        @leave="onLeave"
      >
        <KeepAlive :max="5">
          <component :is="currentComponent" :key="activeTabId" />
        </KeepAlive>
      </Transition>
    </div>
  </main>
</template>

<style scoped>
.workspace-container {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  min-height: 80vh;
}

.tab-navigation {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 8px;
}

.tab-button {
  padding: 8px 16px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-weight: 500;
  color: #64748b;
  border-radius: 6px;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.tab-button.active {
  color: #0f172a;
  background-color: #f1f5f9;
}

.viewport-stage {
  margin-top: 16px;
  position: relative;
  width: 100%;
}
</style>
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari kode implementasi fundamental di atas:

*   **Baris 5-6 (`shallowRef` & `defineAsyncComponent`)**: Menggunakan `shallowRef` alih-alih `ref` untuk menyimpan definisi komponen. Komponen Vue adalah struktur objek kompleks berlapis; membungkusnya dalam deep-reactive proxy (`ref`) memicu degradasi memori dan overhead performa runtime yang tidak perlu.
*   **Baris 24 (`onBeforeEnter`)**: Menginisialisasi style elemen sebelum browser memulai layout paint. Properti `opacity` dan `transform` diatur ke kondisi awal untuk mencegah terjadinya efek FOUC (*Flash of Unstyled Content*).
*   **Baris 30-46 (`onEnter` via Web Animations API)**:
    *   Penggunaan Web Animations API (WAAPI) memberikan kontrol deterministik atas siklus hidup animasi, mengeksekusinya langsung di Compositor Thread.
    *   Parameter callback `done()` **wajib dipanggil** saat `animation.onfinish` terpicu. Kegagalan memanggil callback ini akan membekukan Virtual DOM reconciler, menahan unmounting node secara permanen dari memori.
*   **Baris 78 (`:css="false"`)**: Menginstruksikan Vue untuk sepenuhnya mematikan evaluasi CSS string parser dan auto-detection listener `transitionend`/`animationend`. Ini memangkas runtime overhead sekitar 15-20% pada skenario animasi JavaScript berulang.
*   **Baris 77 (`mode="out-in"`)**: Mencegah tab baru ter-render sebelum tab lama ter-unmount. Ini menghalangi browser melakukan duplikasi render box model yang merusak kestabilan vertikal halaman (*layout shifts*).
*   **Baris 84 (`<KeepAlive :max="5">`)**:
    *   Membatasi footprint memori browser hanya untuk menyimpan maksimal 5 instance tab dalam LRU cache.
    *   Saat berpindah tab dari Analysis ke Metrics, instance `AnalysisTab` tidak di-destroy. Lifecycle `onDeactivated` dipanggil di internal komponen tersebut, state lokal form, posisi scroll, atau data cache dipertahankan seutuhnya di memori heap.

---

## SEKSI 09 — STUDI KASUS NYATA (Enterprise Production Scenario)

### Konteks Bisnis & Masalah
Sebuah platform analitik finansial enterprise berskala multi-tenant memproses data feed transaksi real-time (*millisecond-level throughput*). Platform memiliki dua tantangan performa UX yang kritis:

1.  **Drawer Transaction Inspector Lag**: Ketika pengguna mengklik baris pada virtualized grid berukuran 100.000 transaksi, drawer inspeksi data detail dibuka dari sisi kanan. Aplikasi sering mengalami drop framerate secara masif ($< 25\text{ FPS}$) dan sesekali memicu memory leak yang membuat tab browser crash setelah 2 jam pemantauan terus-menerus.
2.  **Destructive Modals Stacking**: Modal dialog eksekusi trading (`TradeConfirmationModal`) dideklarasikan di dalam hierarchy anak grid yang kompleks. Akibatnya, modal terpotong oleh `overflow: hidden` pada container induk grid, dan properti CSS `z-index` kalah saing dengan visual wrapper panel sebelah kiri. Selain itu, form validation di dalam drawer tereset tiap kali panel ditutup secara tidak sengaja oleh user.

### Sasaran Rekayasa
1.  Mengisolasi drawer rendering ke layer DOM teratas menggunakan `<Teleport>` untuk menghindari restriksi `overflow: hidden` dan stacking context z-index nesting.
2.  Menerapkan transisi berbasis GPU hardware-accelerated (`transform: translate3d`) menggunakan `<Transition>` tanpa layout thrashing.
3.  Mempertahankan state formulir inspeksi analitik menggunakan `<KeepAlive>` yang diatur secara selektif dengan auto-cleanup memory leak pada transaksi yang sudah berstatus 'CLOSED'.
4.  Mencegah focus leak untuk kepatuhan regulasi WCAG 2.1 Level AA via custom keyboard focus-trap engine.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Struktur arsitektur produksi: Drawer audit transaksi keuangan dengan optimasi performa penuh.

```vue
<!-- components/TransactionDrawer.vue -->
<script setup lang="ts">
import {
  ref,
  watch,
  onMounted,
  onUnmounted,
  nextTick
} from 'vue';

interface TransactionDetail {
  id: string;
  referenceNumber: string;
  amount: number;
  currency: string;
  timestamp: number;
}

const props = defineProps<{
  isOpen: boolean;
  transaction: TransactionDetail | null;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'commit-override', id: string, note: string): void;
}>();

const drawerContainerRef = ref<HTMLElement | null>(null);
const overrideNote = ref<string>('');
const previousActiveElement = ref<HTMLElement | null>(null);

// Trap Focus Implementation untuk Kepatuhan WCAG AA Accessibility
const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    emit('close');
    return;
  }

  if (event.key !== 'Tab' || !drawerContainerRef.value) {
    return;
  }

  const focusableElements = drawerContainerRef.value.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );

  if (focusableElements.length === 0) return;

  const firstElement = focusableElements[0];
  const lastElement = focusableElements[focusableElements.length - 1];

  if (event.shiftKey) {
    if (document.activeElement === firstElement) {
      lastElement.focus();
      event.preventDefault();
    }
  } else {
    if (document.activeElement === lastElement) {
      firstElement.focus();
      event.preventDefault();
    }
  }
};

watch(
  () => props.isOpen,
  async (newVal) => {
    if (newVal) {
      previousActiveElement.value = document.activeElement as HTMLElement;
      window.addEventListener('keydown', handleKeyDown);
      await nextTick();
      drawerContainerRef.value?.focus();
    } else {
      window.removeEventListener('keydown', handleKeyDown);
      if (previousActiveElement.value) {
        previousActiveElement.value.focus();
      }
    }
  }
);

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown);
});

const submitOverride = () => {
  if (props.transaction) {
    emit('commit-override', props.transaction.id, overrideNote.value);
    emit('close');
  }
};
</script>

<template>
  <!-- Menghindari CSS stacking context issue dengan Teleport ke body -->
  <Teleport to="body">
    <Transition name="drawer-backdrop">
      <div
        v-if="isOpen"
        class="audit-drawer-backdrop"
        @click="emit('close')"
        aria-hidden="true"
      />
    </Transition>

    <Transition name="drawer-slide">
      <aside
        v-if="isOpen"
        ref="drawerContainerRef"
        class="audit-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        tabindex="-1"
      >
        <header class="drawer-header">
          <h2 id="drawer-title">Inspection: {{ transaction?.referenceNumber }}</h2>
          <button
            class="close-btn"
            @click="emit('close')"
            aria-label="Close Inspection Drawer"
          >
            &times;
          </button>
        </header>

        <main class="drawer-body" v-if="transaction">
          <section class="metric-row">
            <span class="label">Amount:</span>
            <span class="value">{{ transaction.currency }} {{ transaction.amount.toLocaleString() }}</span>
          </section>
          <section class="metric-row">
            <span class="label">Timestamp:</span>
            <span class="value">{{ new Date(transaction.timestamp).toISOString() }}</span>
          </section>

          <div class="override-form">
            <label for="override-note">Audit Adjustment Note:</label>
            <textarea
              id="override-note"
              v-model="overrideNote"
              rows="4"
              placeholder="Provide reason for audit override..."
            ></textarea>
          </div>
        </main>

        <footer class="drawer-footer">
          <button class="btn btn-secondary" @click="emit('close')">Cancel</button>
          <button class="btn btn-primary" @click="submitOverride">Submit Override</button>
        </footer>
      </aside>
    </Transition>
  </Teleport>
</template>

<style scoped>
.audit-drawer-backdrop {
  position: fixed;
  inset: 0;
  background-color: rgba(15, 23, 42, 0.6);
  z-index: 9998;
  backdrop-filter: blur(2px);
}

.audit-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 480px;
  background-color: #ffffff;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.15);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  outline: none;
  /* GPU Compositing Enforcer */
  will-change: transform;
}

.drawer-header {
  padding: 16px 24px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #64748b;
}

.drawer-body {
  padding: 24px;
  flex: 1;
  overflow-y: auto;
}

.metric-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.override-form {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.override-form textarea {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  padding: 8px;
  font-family: inherit;
}

.drawer-footer {
  padding: 16px 24px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
}

.btn-secondary {
  background: #f1f5f9;
  border: 1px solid #cbd5e1;
}

.btn-primary {
  background: #0284c7;
  color: #ffffff;
  border: none;
}

/* =========================================================================
   PERFORMANCE-ORIENTED CSS TRANSITIONS (COMPOSITOR-ONLY PROPERTIES)
   ========================================================================= */

/* Backdrop: Fade (Opacity Only) */
.drawer-backdrop-enter-active,
.drawer-backdrop-leave-active {
  transition: opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.drawer-backdrop-enter-from,
.drawer-backdrop-leave-to {
  opacity: 0;
}

.drawer-backdrop-enter-to,
.drawer-backdrop-leave-from {
  opacity: 1;
}

/* Panel: Slide (Transform Only) */
.drawer-slide-enter-active {
  transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

.drawer-slide-leave-active {
  transition: transform 0.25s cubic-bezier(0.7, 0, 0.84, 0);
}

.drawer-slide-enter-from {
  transform: translate3d(100%, 0, 0);
}

.drawer-slide-enter-to {
  transform: translate3d(0, 0, 0);
}

.drawer-slide-leave-from {
  transform: translate3d(0, 0, 0);
}

.drawer-slide-leave-to {
  transform: translate3d(100%, 0, 0);
}
</style>
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter / Dimensi | `<KeepAlive>` Cache Strategy | Conditional Re-rendering (`v-if`) | Hidden CSS Toggling (`v-show`) |
| :--- | :--- | :--- | :--- |
| **Initial Mount Cost** | Normal (dieksekusi saat first-render) | Minimal (tertunda hingga kondisi bernilai `true`) | Maksimal (seluruh cabang DOM di-mount di awal) |
| **Memory Footprint** | **Tinggi** (VNode, Component Instances, Reactive Scope di-hold di heap) | **Nol / Paling Minimal** (Instance dan DOM hancur, eligible Garbage Collection) | **Sedang-Tinggi** (DOM fisik tetap berada di DOM tree global) |
| **Switch Latency (UX)**| **$< 5\text{ ms}$** (Hanya attaching DOM node yang sudah diproses) | **$50\text{ ms} - 500\text{ ms}$** (Membutuhkan parsing VNode, setup reactivity, DOM creation) | **$< 2\text{ ms}$** (Hanya mengubah computed inline CSS `display`) |
| **Lifecycle Hooks** | `onActivated`, `onDeactivated` | `onMounted`, `onUnmounted` | Tidak ada trigger unmount; hanya trigger watcher |
| **Use Case Terbaik** | Formulir kompleks multi-step, dynamic dashboard tabs, filter tables. | Modal sekali pakai, state navigasi permanen yang jarang dibuka kembali. | Accordion toggle sederhana, tooltips, dropdown menu cepat.