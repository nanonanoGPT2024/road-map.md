# Bab 03 Module 01: Directives, Template Engine, & DOM Manipulation

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Utama:** Vue.js Core Architecture
*   **Modul:** Bab 03 Module 01: Directives, Template Engine, & DOM Manipulation
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat Konseptual:** JavaScript ESNext (Proxies, WeakMap, Symbols), Virtual DOM reconciliation concepts, Abstract Syntax Tree (AST), Browser Rendering Pipeline (Layout, Paint, Composite).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1.  **Mendekomposisi Pipeline Kompilasi Vue 3:** Memahami transisi deterministik dari string template mentah menjadi Abstract Syntax Tree (AST), intermediate representation (IR), hingga eksekusi `render()` function berbasis Virtual DOM (vnode).
2.  **Menganalisis Mekanika Directives Internal:** Membedah implementasi bawaan (`v-bind`, `v-model`, `v-for`, `v-if` vs `v-show`, `v-memo`) dan lifecycle custom directive (`created`, `beforeMount`, `mounted`, `beforeUpdate`, `updated`, `beforeUnmount`, `unmounted`).
3.  **Menguasai Paradigma Template Optimization Compiler:** Mengidentifikasi mekanisme patch flags, dynamic children tracking via *Block Tree*, static hoisting, dan cache handlers untuk menekan computational cost pada render pipeline.
4.  **Mengeksekusi Manipulasi DOM Tingkat Rendah Secara Aman:** Mengintegrasikan imperatif DOM mutator (seperti integrasi library pihak ketiga, canvas engine, atau virtual scroller) dengan reactive runtime Vue tanpa memicu memory leak atau rendering desynchronization.
5.  **Mendeteksi & Memitigasi Vector Vulnerability (XSS):** Mengisolasi bahaya injeksi HTML berbasis `v-html` dan menyusun arsitektur sanitasi berbasis context-aware parsing.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### 1. Template Adalah Antarmuka Deklaratif Terkompilasi, Bukan Evaluasi Runtime Naif
Jangan memandang template Vue seperti engine string interpolation konvensional (misal: Handlebars, Mustache, atau EJS). Template Vue tidak mengevaluasi string via `eval()` pada runtime. Template Vue adalah representasi deklaratif strictly-typed yang diubah secara deterministik pada *build time* (atau initial runtime compile) menjadi pure JavaScript JavaScript Engine-optimized Render Function.

### 2. The Duality of Vue's Engine: Compiler + Runtime Coordination
Pemisahan mental yang tegas harus dibangun antara **Compiler** dan **Runtime**:
*   *Compiler* membedah template menjadi AST, mencari node statis dan dinamis, membubuhkan metadata optimasi numerik bitwise (*Patch Flags*), dan memilah struktur tree ke dalam *Block Trees*.
*   *Runtime* (`@vue/runtime-core` dan `@vue/runtime-dom`) mengonsumsi output compiler tersebut. Saat state reaktif berubah, runtime tidak melakukan diffing mendalam (O(n) traversal) pada seluruh node VNode. Runtime hanya melintasi array linear berisi node dinamis yang telah ditandai compiler.

### 3. Escape Hatch Governance: Declarative by Default, Imperative by Exception
Manipulasi DOM langsung via browser API (`document.querySelector`, `element.appendChild`) merusak determinisme single source of truth yang dijaga oleh Reactivity Engine Vue. DOM manipulation langsung hanya diperbolehkan melalui *Custom Directives* atau *Template Refs* dengan pemahaman siklus hidup vnode yang ketat. Jika manipulasi dilakukan di luar koordinasi runtime Vue, State dan Layout Tree browser akan mengalami split-brain state (inkonsistensi representasi internal dan visual nyata).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur kompilasi dan rendering end-to-end dari template mentah menuju browser real DOM:

```
[ Vue Single File Component (.vue Template) ]
                     |
                     v
+-------------------------------------------------------+
| COMPILER PHASE (@vue/compiler-core & compiler-dom)    |
|                                                       |
|  1. Lexer & Tokenizer                                 |
|     -> Parsing template string ke stream of tokens    |
|                                                       |
|  2. Parser AST (Abstract Syntax Tree Generation)      |
|     -> Konstruksi node hirarki (ElementNode, Root)    |
|                                                       |
|  3. Transform Engine (Static Analysis)                |
|     -> Hoisting node murni statis                     |
|     -> Bitwise Patch Flags assignment                 |
|     -> Block Tree structural boundary marking         |
|                                                       |
|  4. Code Generator                                    |
|     -> Menghasilkan JavaScript Render Function AST    |
|     -> Output: function render(_ctx, _cache) { ... }  |
+-------------------------------------------------------+
                     |
                     v
+-------------------------------------------------------+
| RUNTIME INITIALIZATION (@vue/runtime-core)            |
|                                                       |
|  1. Inisialisasi Reactive State via Proxy             |
|  2. Eksekusi Render Function di dalam Reactive Effect |
|  3. Output: Virtual DOM Tree (VNode Trees)            |
|     - Blok root menyimpan array `dynamicChildren`     |
+-------------------------------------------------------+
                     |
                     v
+-------------------------------------------------------+
| RENDERER MOUNT PHASE (@vue/runtime-dom)               |
|                                                       |
|  1. hostCreateElement() -> Native DOM nodes           |
|  2. Directive Hook Trigger: `created`, `beforeMount`  |
|  3. hostInsert() -> Menancapkan elemen ke DOM Tree    |
|  4. Directive Hook Trigger: `mounted`                 |
+-------------------------------------------------------+
                     |
           Reaktif State Berubah (Proxy Setter)
                     |
                     v
+-------------------------------------------------------+
| RUNTIME PATCH / DIFF PHASE (Optimized Diffing)        |
|                                                       |
|  1. Reactive Effect trigger rerender                  |
|  2. Runtime membaca array `dynamicChildren` (Block)   |
|  3. Skip structural diff untuk node statis            |
|  4. Evaluasi bitwise Patch Flags:                     |
|     - TEXT: Mutasi textContent saja                   |
|     - CLASS: Mutasi className saja                    |
|     - PROPS: Mutasi atribut spesifik via fast path    |
|  5. Directive Hook Trigger: `beforeUpdate`, `updated` |
|  6. Minimal browser repaint/reflow layout calculation |
+-------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Objek Abstract Syntax Tree (AST) Template
Saat compiler menerima markup:
```html
<div id="app">
  <span :class="activeClass">{{ message }}</span>
</div>
```
Parser membangun representasi AST berbasis interface berikut:

```typescript
interface ElementNode {
  type: NodeTypes.ELEMENT;
  tag: 'div';
  props: Array<AttributeNode | DirectiveNode>;
  children: Array<ElementNode | TextNode | InterpolationNode>;
  isSelfClosing: boolean;
  loc: SourceLocation; // Metadata line, column, offset untuk source-mapping
}

interface DirectiveNode {
  type: NodeTypes.DIRECTIVE;
  name: 'bind'; // Normalisasi dari ':'
  exp: ExpressionNode; // Node JS expression: 'activeClass'
  arg: ExpressionNode; // Argument directive: 'class'
  modifiers: string[]; // Modifier array: e.g., ['prevent', 'stop']
  loc: SourceLocation;
}
```

### 2. Patch Flags: Optimasi Bitwise Engine
Vue mengeliminasi algoritma reconciliation universal O(n) murni dengan menyematkan integer bitmask ke dalam argumen VNode. Bitmask ini menginstruksikan VNode patcher operasi mana yang diizinkan untuk dieksekusi:

```typescript
export const enum PatchFlags {
  TEXT = 1,                 // 0b00000000001 - Dynamic textContent
  CLASS = 1 << 1,          // 0b00000000010 - Dynamic class binding
  STYLE = 1 << 2,          // 0b00000000100 - Dynamic inline style
  PROPS = 1 << 3,          // 0b00000001000 - Dynamic props selain class/style
  NEED_PATCH = 1 << 9,      // 0b10000000000 - Elemen butuh directive update (e.g. custom directive)
  HOISTED = -1,             // Node statis, patch engine melompatinya
  BAIL = -2                 // Keluar dari mode optimized, fallback ke full diff
}
```

Saat renderer mengevaluasi patch:
```typescript
if (patchFlag & PatchFlags.TEXT) {
  if (prevVNode.children !== nextVNode.children) {
    hostSetElementText(el, nextVNode.children);
  }
}
if (patchFlag & PatchFlags.CLASS) {
  // Langsung set via classList atau className tanpa loop properties
  hostSetClassName(el, nextVNode.props.class);
}
```

### 3. VNode Structure & Block Tree
Blok adalah VNode khusus yang memiliki array `dynamicChildren`. Node statis diabaikan dari array ini.

```typescript
interface VNode {
  __v_isVNode: true;
  type: string | Component | Symbol;
  props: Record<string, any> | null;
  children: VNodeNormalizedChildren;
  el: HostNode | null; // Pointer ke DOM Node riil
  patchFlag: number;
  dynamicChildren: VNode[] | null; // Kunci dari Fast Path Diffing
  dirs?: DirectiveBindingInternal[]; // Custom directive runtime context
}
```

### 4. Custom Directive Runtime Hook Interface
Directive dieksekusi melalui serangkaian low-level hooks yang selaras dengan lifecycle komponen host:

```typescript
export interface Directive<T = any, V = any> {
  created?(el: T, binding: DirectiveBinding<V>, vnode: VNode<any, T>, prevVNode: null): void;
  beforeMount?(el: T, binding: DirectiveBinding<V>, vnode: VNode<any, T>, prevVNode: null): void;
  mounted?(el: T, binding: DirectiveBinding<V>, vnode: VNode<any, T>, prevVNode: null): void;
  beforeUpdate?(el: T, binding: DirectiveBinding<V>, vnode: VNode<any, T>, prevVNode: VNode<any, T>): void;
  updated?(el: T, binding: DirectiveBinding<V>, vnode: VNode<any, T>, prevVNode: VNode<any, T>): void;
  beforeUnmount?(el: T, binding: DirectiveBinding<V>, vnode: VNode<any, T>, prevVNode: null): void;
  unmounted?(el: T, binding: DirectiveBinding<V>, vnode: VNode<any, T>, prevVNode: null): void;
}

export interface DirectiveBinding<V = any> {
  instance: ComponentPublicInstance | null;
  value: V;
  oldValue: V | null;
  arg?: string;
  modifiers: Record<string, boolean>;
  dir: Directive<any, V>;
}
```

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Structural Directive: `v-if` vs `v-show`
*   `v-if`: Kondisional struktural nyata. Mengubah pohon VNode. Saat bernilai `false`, elemen dan dependensinya tidak dibuat di memori DOM; node digantikan oleh *Comment VNode* (`createCommentVNode('')`). Operasi ini memicu parsing DOM tree, destruction instance komponen anak, dan re-layout cycle saat kondisi berubah.
*   `v-show`: Kondisional visual. Elemen *selalu* dirender ke native DOM, diregistrasikan ke rendering tree browser, dan styling CSS dimutasi secara langsung via inline property `display: none`. Tidak memicu penghancuran vnode atau cleanup hook.

### Mekanisme `v-model` Under the Hood
`v-model` bukan sintaks primitif, melainkan *compiler macro expansion* komposit:
Untuk elemen native form:
```html
<input v-model="searchText" />
```
Dikomparasi oleh compiler menjadi:
```javascript
createVNode("input", {
  value: _ctx.searchText,
  onInput: $event => ((_ctx.searchText) = $event.target.value)
}, null, 40 /* PROPS, NEED_HYDRATION */, ["value", "onInput"])
```
*Catatan:* Untuk input text composition (misal: input karakter aksara Jepang, Mandarin, atau Korea), Vue secara otomatis mengaitkan event handler internal untuk `compositionstart` dan `compositionend`. State internal Vue tidak akan memicu reaktif mutasi string hingga IME composition selesai (`compositionend`).

### Algoritma Kompilasi: Static Hoisting & Cache Handlers
Pertimbangkan template berikut:
```html
<div class="panel">
  <h1 class="header">System Monitoring</h1>
  <button @click="resetMetric">Reset</button>
  <span :id="metricId">{{ metricValue }}</span>
</div>
```

Tanpa optimasi, setiap kali `metricValue` berubah, `h1` dan `button` akan dibuat ulang objek VNode-nya di memori heap. Vue 3 Compiler mengeksekusi:

1.  **Static Hoisting:** Node `h1` di-hoist ke luar render function level modul scope:
    ```javascript
    const _hoisted_1 = /*#__PURE__*/ createBaseVNode("h1", { class: "header" }, "System Monitoring", -1 /* HOISTED */)
    ```
    Objek VNode ini hanya dibuat **satu kali** saat script file di-evaluasi dan di-reuse lintas render cycles.

2.  **Event Handler Caching:** Directive `@click="resetMetric"` diubah untuk menyematkan caching reference:
    ```javascript
    onClick: _cache[0] || (_cache[0] = (...args) => (_ctx.resetMetric && _ctx.resetMetric(...args)))
    ```
    Mekanisme ini mencegah event handler dianggap sebagai "prop baru" pada setiap render, yang mana dapat menggagalkan optimasi shallow compare pada komponen child murni (`shouldUpdate`).

3.  **Dynamic Block Creation:** Root `div` menjadi parent block:
    ```javascript
    return (_openBlock(), _createElementBlock("div", { class: "panel" }, [
      _hoisted_1,
      _createElementVNode("button", { onClick: _cache[0] || ... }, "Reset"),
      _createElementVNode("span", { id: _ctx.metricId }, _toDisplayString(_ctx.metricValue), 9 /* TEXT, PROPS */, ["id"])
    ]))
    ```
    Saat runtime diffing, hanya elemen `span` yang didorong ke `dynamicChildren` dari block `div`. Elemen `h1` dan `button` dilompati secara total dari reconciliation diff cycle.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode yang mendemonstrasikan custom directive enterprise: **`v-intersection-observer`** dengan memory lifecycle management, argument support, dynamic options updates, dan fallback handling.

```vue
<!-- components/PerformanceIntersectionDemo.vue -->
<script setup lang="ts">
import { ref, type Directive } from 'vue';

interface IntersectionPayload {
  ratio: number;
  isIntersecting: boolean;
}

const visibilityState = ref<string>('Not Visible');
const thresholdValue = ref<number>(0.5);

// Definisi Custom Directive dengan tipe terikat
const vIntersect: Directive<HTMLElement, (payload: IntersectionPayload) => void> = {
  created(el, binding) {
    // WeakMap fallback atau property attachment yang aman dari namespace pollution
    (el as any).__observer_state__ = {
      observer: null as IntersectionObserver | null,
      callback: binding.value
    };
  },
  mounted(el, binding) {
    const options: IntersectionObserverInit = {
      root: null,
      threshold: binding.arg ? parseFloat(binding.arg) : 0.0
    };

    const state = (el as any).__observer_state__;
    state.callback = binding.value;

    state.observer = new IntersectionObserver((entries) => {
      const entry = entries[0];
      if (entry && state.callback) {
        state.callback({
          ratio: entry.intersectionRatio,
          isIntersecting: entry.isIntersecting
        });
      }
    }, options);

    state.observer.observe(el);
  },
  beforeUpdate(el, binding) {
    // Sinkronisasi mutasi callback secara reaktif tanpa re-instantiate observer
    const state = (el as any).__observer_state__;
    if (state) {
      state.callback = binding.value;
    }
  },
  unmounted(el) {
    // CRITICAL: Mencegah memory leak dengan pemutusan koneksi observer
    const state = (el as any).__observer_state__;
    if (state && state.observer) {
      state.observer.disconnect();
      state.observer = null;
    }
    delete (el as any).__observer_state__;
  }
};

function handleIntersection(payload: IntersectionPayload) {
  if (payload.isIntersecting) {
    visibilityState.value = `Elemen Terlihat! (${(payload.ratio * 100).toFixed(1)}%)`;
  } else {
    visibilityState.value = 'Elemen Tersembunyi di Luar Viewport';
  }
}
</script>

<template>
  <div class="container">
    <div class="status-panel">
      <h3>Observer Status: {{ visibilityState }}</h3>
    </div>
    
    <div class="scroll-wrapper">
      <div class="spacer">Gulir ke bawah untuk memicu directive...</div>
      
      <!-- Penggunaan Custom Directive dengan Argumen Dinamis -->
      <div 
        v-intersect:0.5="handleIntersection" 
        class="target-box"
      >
        Target Node
      </div>
      
      <div class="spacer">Bagian Bawah Ruang Scroll</div>
    </div>
  </div>
</template>

<style scoped>
.container {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.status-panel {
  padding: 1rem;
  background-color: #1e293b;
  color: #f8fafc;
  border-radius: 6px;
}
.scroll-wrapper {
  height: 300px;
  overflow-y: auto;
  border: 2px dashed #94a3b8;
  padding: 1rem;
}
.spacer {
  height: 400px;
  background: repeating-linear-gradient(
    45deg,
    #f1f5f9,
    #f1f5f9 10px,
    #e2e8f0 10px,
    #e2e8f0 20px
  );
  display: flex;
  align-items: center;
  justify-content: center;
}
.target-box {
  height: 100px;
  background-color: #0ea5e9;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  border-radius: 4px;
}
</style>
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 13 (`const vIntersect: Directive<HTMLElement, ...>`):** Mendeklarasikan objek direktif lokal berformat camelCase (`vIntersect`), yang diekstrak oleh template engine menjadi binding ekspresi kebab-case (`v-intersect`). Kita mengikat tipe generic ke `HTMLElement` dan callback function payload untuk type-safety.
*   **Baris 14-20 (`created(el, binding)`):** Hook awal saat VNode diinstansiasi namun belum terpasang di DOM dokumen fisik. Di sini kita menginisialisasi properti private `__observer_state__` pada node fisik untuk menghindari penggunaan global storage yang rentan fragmentation.
*   **Baris 21-25 (`mounted(el, binding)`):** Hook yang berjalan tepat setelah elemen fisik ditancapkan ke DOM oleh *Renderer Host*. Kita membaca properti argumen `binding.arg` yang dievaluasi (`0.5`), mengonversi string ke float native untuk parameter `threshold`.
*   **Baris 29-37 (`state.observer = new IntersectionObserver(...)`):** Mendaftarkan instance platform Web API. Di dalam callback, kita memanggil `state.callback` secara dinamis dari reference, bukan hardcoded closure.
*   **Baris 40-46 (`beforeUpdate(el, binding)`):** Hook krusial. Jika komponen parent merender ulang dan passing fungsi callback baru (misalnya anonymous inline function), kita *tidak* boleh merusak (destroy) dan membuat ulang (re-instantiate) `IntersectionObserver` karena operasi tersebut memicu computational overhead browser thread. Kita hanya memperbarui pointer reference `state.callback = binding.value`.
*   **Baris 47-54 (`unmounted(el)`):** Mencegah *Dead Instance Retain & Memory Leaks*. Ketika elemen dihapus oleh struktur kondisional (`v-if`) atau unmount router, listener platform API wajib dihentikan via `observer.disconnect()`. Menghapus property node `__observer_state__` memungkinkan Garbage Collector membersihkan node dan closures di balik layer.
*   **Baris 73 (`v-intersect:0.5="handleIntersection"`):** Sintaks directive Vue. `v-intersect` memetakan nama directive, `:0.5` menetapkan metadata `binding.arg`, dan `"handleIntersection"` mengevaluasi ekspresi konteks komponen ke `binding.value`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks Produksi
Sebuah platform analitik finansial enterprise berskala tinggi, *Global Markets Execution Desk*, menampilkan stream fluktuasi tick-by-tick order book (ribuan order per detik). 

### Permasalahan
Setiap entitas tick yang masuk memicu pembaruan styling visual (animasi *flash update* hijau/merah) dan tooltips dinamis berbasis rendering DOM Native Canvas/SVG. Ketika tim menggunakan deklarasi reaktif murni Vue bawaan:
```html
<tr v-for="order in orders" :key="order.id" :class="order.flashClass">
  <td>{{ order.price }}</td>
</tr>
```
Reactivity pipeline tercekik (*High Microtask Queue Congestion*). Rerender Virtual DOM mendatangkan overhead alokasi memory heap ekstrem: ribuan patch flag checking dieksekusi per detik, memicu Garbage Collection pauses (Stop-The-World GC spikes) yang menyebabkan frame drop tajam dari 60 FPS ke < 15 FPS di mesin terminal trader.

### Solusi Teknis
1.  Mengisolasi mutasi styling dan high-frequency micro-animations sepenuhnya dari siklus komputasi Virtual DOM Vue.
2.  Membangun Custom Directive tingkat rendah **`v-ticker-flash`** yang beroperasi secara direct-mutation terhadap DOM Native (`HTMLElement.classList` dan Web Animations API) yang terkoordinasi melalui internal animation loop (`requestAnimationFrame`) dan decoupled buffer ring queue.
3.  Mempertahankan Vue Template Engine hanya untuk layouting struktur awal dokumen, memotong 90% waktu komputasi VNode patching pipeline.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistem performa tinggi modular untuk kasus enterprise di atas:

```typescript
// directives/vTickerFlash.ts
import type { Directive, DirectiveBinding } from 'vue';

type FlashType = 'bid' | 'ask';

interface FlashQueueItem {
  type: FlashType;
  timestamp: number;
}

interface FlashDOMState {
  queue: FlashQueueItem[];
  animationFrameId: number | null;
  lastAppliedType: FlashType | null;
  activeAnimation: Animation | null;
}

const flashStateMap = new WeakMap<HTMLElement, FlashDOMState>();

const KEYFRAMES_BID: Keyframe[] = [
  { backgroundColor: 'rgba(34, 197, 94, 0.65)', transform: 'scale(1.02)' },
  { backgroundColor: 'rgba(34, 197, 94, 0)', transform: 'scale(1)' }
];

const KEYFRAMES_ASK: Keyframe[] = [
  { backgroundColor: 'rgba(239, 68, 68, 0.65)', transform: 'scale(0.98)' },
  { backgroundColor: 'rgba(239, 68, 68, 0)', transform: 'scale(1)' }
];

const ANIMATION_TIMING: KeyframeAnimationOptions = {
  duration: 400,
  easing: 'cubic-bezier(0, 0, 0.2, 1)',
  fill: 'none'
};

function processDOMFlash(el: HTMLElement, state: FlashDOMState): void {
  if (state.queue.length === 0) {
    state.animationFrameId = null;
    return;
  }

  // Mengambil state perubahan mutakhir, membuang transisi yang basi
  const latestMutation = state.queue[state.queue.length - 1];
  state.queue = [];

  if (state.activeAnimation) {
    state.activeAnimation.cancel();
  }

  const keyframes = latestMutation.type === 'bid' ? KEYFRAMES_BID : KEYFRAMES_ASK;

  // Mutasi imperatif langsung via Web Animations API (Melewati CSS recalculation pipeline Vue)
  state.activeAnimation = el.animate(keyframes, ANIMATION_TIMING);
  
  state.activeAnimation.onfinish = () => {
    state.activeAnimation = null;
  };

  state.animationFrameId = null;
}

export const vTickerFlash: Directive<HTMLElement, { price: number; type: FlashType }> = {
  created(el) {
    flashStateMap.set(el, {
      queue: [],
      animationFrameId: null,
      lastAppliedType: null,
      activeAnimation: null
    });
  },

  beforeUpdate(el, binding: DirectiveBinding<{ price: number; type: FlashType }>) {
    // Mengecek apakah ada perubahan harga riil sebelum menjadwalkan mutasi layout
    if (binding.oldValue && binding.value.price === binding.oldValue.price) {
      return;
    }

    const state = flashStateMap.get(el);
    if (!state) return;

    state.queue.push({
      type: binding.value.type,
      timestamp: performance.now()
    });

    // Mengamankan mutasi DOM hanya dalam vsync browser via requestAnimationFrame
    if (state.animationFrameId === null) {
      state.animationFrameId = requestAnimationFrame(() => {
        processDOMFlash(el, state);
      });
    }
  },

  unmounted(el) {
    const state = flashStateMap.get(el);
    if (state) {
      if (state.animationFrameId !== null) {
        cancelAnimationFrame(state.animationFrameId);
      }
      if (state.activeAnimation) {
        state.activeAnimation.cancel();
      }
      flashStateMap.delete(el);
    }
  }
};
```

Berikut komponen consumer yang menangani ribuan update per detik:

```vue
<!-- components/OrderBookStream.vue -->
<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { vTickerFlash } from '../directives/vTickerFlash';

interface OrderBookRow {
  id: string;
  symbol: string;
  price: number;
  type: 'bid' | 'ask';
  volume: number;
}

const orderBook = ref<OrderBookRow[]>([
  { id: 'ORD-1', symbol: 'BTCUSDT', price: 65420.50, type: 'bid', volume: 1.45 },
  { id: 'ORD-2', symbol: 'ETHUSDT', price: 3480.10, type: 'ask', volume: 12.0 },
  { id: 'ORD-3', symbol: 'SOLUSDT', price: 145.85, type: 'bid', volume: 45.2 }
]);

let timer: NodeJS.Timeout | null = null;

// Simulasi High-Frequency Trading Tick Socket Influx
onMounted(() => {
  timer = setInterval(() => {
    const randomIndex = Math.floor(Math.random() * orderBook.value.length);
    const target = orderBook.value[randomIndex];
    const isIncrease = Math.random() > 0.5;
    const delta = (Math.random() * 2).toFixed(2);
    
    // In-place reactive mutation
    target.price = isIncrease 
      ? parseFloat((target.price + parseFloat(delta)).toFixed(2))
      : parseFloat((target.price - parseFloat(delta)).toFixed(2));
    target.type = isIncrease ? 'bid' : 'ask';
    target.volume = parseFloat((Math.random() * 10).toFixed(2));
  }, 100); // Trigger setiap 100 milidetik
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>

<template>
  <div class="terminal-wrapper">
    <table class="order-table">
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Side</th>
          <th>Size</th>
          <th>Price Execution</th>
        </tr>
      </thead>
      <tbody>
        <!-- Menggunakan v-memo untuk mengisolasi rendering vnode structural 
             dan mendelegasikan styling frekuensi tinggi ke direct directive -->
        <tr 
          v-for="order in orderBook" 
          :key="order.id"
          v-memo="[order.id, order.price, order.volume]"
        >
          <td>{{ order.symbol }}</td>
          <td :class="order.type">{{ order.type.toUpperCase() }}</td>
          <td>{{ order.volume }}</td>
          <td 
            v-ticker-flash="{ price: order.price, type: order.type }" 
            class="price-cell"
          >
            {{ order.price.toFixed(2) }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.terminal-wrapper {
  background-color: #0b0e14;
  color: #e5e7eb;
  padding: 1.5rem;
  font-family: 'JetBrains Mono', 'Courier New', monospace;
}
.order-table {
  width: 100%;
  border-collapse: collapse;
}
.order-table th, .order-table td {
  padding: 0.5rem 1rem;
  text-align: right;
  border-bottom: 1px solid #1f2937;
}
.order-table th:first-child, .order-table td:first-child {
  text-align: left;
}
.bid { color: #22c55e; }
.ask { color: #ef4444; }
.price-cell {
  position: relative;
  font-weight: bold;
  will-change: transform, background-color;
}
</style>
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter / Dimensi | Directives (`v-ticker-flash`) | Virtual DOM Class Binding (`:class`) | Direct DOM Mutator (`ref` + DOM API manual) |
| :--- | :--- | :--- | :--- |
| **Abstraksi & Declarativeness** | Tinggi, deklaratif pada template, modular & terisolasi di runtime. | Sangat tinggi, sepenuhnya deklaratif, murni Vue idiomatic code. | Sangat rendah, imperatif murni, mencemari logika komponen script. |
| **Diffing Overhead** | **Nol:** Operasi melewati vnode diffing, dihandle langsung via microtask/rAF. | **Tinggi:** Setiap tick memicu traversal vnode & reconciler props verification. | **Nol:** Menghindari Virtual DOM secara absolut. |
| **Memory Footprint** | Rendah: Menggunakan `WeakMap`, tidak ada garbage allocation per tick. | Menengah-Tinggi: Pembuatan VNode wrapper baru & patch context closure. | Rawan Kebocoran: Mengharuskan developer mengelola array referensi secara manual. |
| **Reusability** | **Sangat Tinggi:** Dapat ditempelkan ke elemen HTML atau komponen apa pun via template. | Sedang: Terikat pada arsitektur state internal komponen itu sendiri. | Buruk: Logika terikat tightly-coupled pada satu single root ref elemen. |
| **Hydration / SSR Safety** | Aman: Hook `beforeMount`/`mounted` tidak berjalan di server Node.js runtime. | Aman: Terkompilasi langsung ke string SSR markup tanpa error. | Rawan Error: Memerlukan wrapping pengecekan manual `typeof window !== 'undefined'`. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Desinkronisasi Input IME (Input Method Editor)
*   **Masalah:** Menggunakan directive custom manipulasi input atau binding event listeners native `keydown` tanpa memperhitungkan IME (input karakter alfabet berbasis komposisi aksara seperti CJK).
*   **Akar Masalah:** IME memicu sinyal `keydown` untuk setiap ketukan tombol sebelum kombinasi karakter diselesaikan. Jika directive memotong atau memformat value saat itu juga, komposisi karakter user akan terputus.
*   **Mitigasi:** Dengarkan flag komposisi:
    ```typescript
    let isComposing = false;
    el.addEventListener('compositionstart', () => { isComposing = true; });
    el.addEventListener('compositionend', (e) => {
      isComposing = false;
      triggerMutation(e.target.value);
    });
    el.addEventListener('input', (e) => {
      if (!isComposing) triggerMutation(e.target.value);
    });
    ```

### 2. Shallow vs Deep VNode Mutation Mengakibatkan Missed Updates
*   **Masalah:** Direktif membaca `binding.value` berupa objek non-reaktif atau mutasi deep nested property tanpa reaktif proxy trigger.
*   **Mitigasi:** Selalu pasang identifier komparasi yang tegas di dalam `beforeUpdate`. Jika direktif bergantung pada nested array/object mutasi, wajib informasikan consumer untuk mengekspos payload dengan shallow copy trigger atau gunakan `watch(() =>