# Kurikulum Enterprise Vue.js 3 — Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 03: Directives, Template Engine, dan DOM Manipulation**

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, *Staff/Principal Frontend Engineer* ditargetkan mampu:
*   **Menganalisis Internal Compiler Pipeline:** Menguraikan transformasi dari string template Vue menjadi *Abstract Syntax Tree* (AST), *JavaScript AST*, hingga *Optimized Render Function* (`_createBlock`, `_openBlock`, patch flags).
*   **Mengoptimasi Virtual DOM Reconciliation:** Memanfaatkan *PatchFlags*, *ShapeFlags*, *Static Hoisting*, dan *Block Tree Optimization* untuk mereduksi *runtime diffing overhead* pada aplikasi skala besar.
*   **Membangun Custom Directives Enterprise-Grade:** Mengimplementasikan siklus hidup *custom directive* (`created` hingga `unmounted`) yang bebas kebocoran memori (*zero memory leak*), aman terhadap arsitektur SSR/Nuxt 3 (*hydration-safe*), dan terintegrasi dengan *cleanup register*.
*   **Mengontrol Manipulasi DOM Imperatif:** Menjembatani *declarative rendering* Vue dengan pustaka pihak ketiga berbasis DOM imperatif (seperti Monaco Editor, Chart.js, Canvas) menggunakan template refs modern (`useTemplateRef`) dan strategi *lifecycle decoupling*.
*   **Menerapkan Strategi Fine-Grained Update:** Menggunakan `v-memo` dan `v-once` untuk mengeliminasi siklus rendering VNode redundan pada komponen *high-frequency update* (seperti data grid streaming/financial order books).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta harus menguasai:
*   **Vue 3 Core Essentials:** Pemahaman mendalam tentang Composition API (`ref`, `shallowRef`, `reactive`, `effectScope`).
*   **Modern JavaScript & TypeScript:** ESNext features, `WeakMap`, `WeakSet`, ArrayBuffer/TypedArrays, serta pemahaman AST dasar.
*   **Browser Internals:** Layout, Paint, Composite pipeline, DOM mutation observer, dan Garbage Collection behavior.
*   **Tooling:** Node.js v20+, Vite 5+, `@vue/compiler-dom`, serta TypeScript 5+.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Template Compilation Pipeline

Kompiler Vue (`@vue/compiler-core` dan `@vue/compiler-dom`) bekerja melalui 3 fase deterministik:

```
[Template String]
       │
       ▼
┌──────────────┐
│ 1. Parser    │  --> Menghasilkan Template AST (Tokenizing, Element, Expression nodes)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 2. Transform │  --> Node Transforms, Structural Directives (v-if, v-for),
└──────┬───────┘      Static Hoisting, PatchFlag Calculation, Block Extraction
       │
       ▼
┌──────────────┐
│ 3. Codegen   │  --> Menghasilkan Javascript Render Function code string
└──────────────┘
```

1.  **Parse Stage:** String template diubah menjadi AST berbasis hirarki node DOM dan ekspresi Vue.
2.  **Transform Stage:** Fase paling kritikal. Di sini kompiler:
    *   **Menganalisis Reaktivitas Statis vs Dinamis:** Properti statis diangkat (*hoisted*) keluar dari *render function execution scope*.
    *   **Menghitung PatchFlags:** Bitwise integer ditambahkan ke setiap dynamic node untuk memberi tahu runtime algoritma patching node mana yang berubah.
    *   **Block Tree Construction:** Mengubah hirarki pohon DOM menjadi array satu dimensi datar (`dynamicChildren`) yang hanya berisi node dinamis.
3.  **Codegen Stage:** Mentransformasi AST yang sudah dioptimasi menjadi kode executable JavaScript `render(_ctx, _cache)` yang mengeksekusi `_createElementVNode`, `_createBlock`, dan `_withDirectives`.

#### 3.2. Patch Flags & Bitwise Reconciliation

Algoritma diffing Vue 3 tidak menelusuri seluruh VNode tree secara rekursif murni (seperti React VDOM standar). Vue menggunakan *bitwise mask* untuk membatasi operasi pembandingan DOM:

```typescript
export const enum PatchFlags {
  TEXT = 1,              // 0b00000000001 (Dynamic textcontent)
  CLASS = 1 << 1,        // 0b00000000010 (Dynamic class binding)
  STYLE = 1 << 2,        // 0b00000000100 (Dynamic inline style)
  PROPS = 1 << 3,        // 0b00000001000 (Dynamic props except class/style)
  NEED_PATCH = 1 << 5,   // 0b00000100000 (Non-props updates e.g. directives)
  DYNAMIC_SLOTS = 1 << 10// 0b10000000000 (Slots dynamic dependencies)
}
```

Saat state berubah, runtime mengeksekusi perbandingan bitwise:
```javascript
if (patchFlag & PatchFlags.TEXT) {
  if (oldVNode.children !== newVNode.children) {
    hostSetElementText(el, newVNode.children);
  }
}
```
Jika tidak ada bitwise flag untuk class atau style, runtime sama sekali mengabaikan pengecekan atribut tersebut.

#### 3.3. Block Tree Architecture

Elemen dasar pengoptimalan rendering adalah konsep **Block**. Sebuah block dibuat via `_openBlock()` dan `_createBlock()`. Block melacak semua *descendant* dinamisnya secara flat dalam array `dynamicChildren`, menembus kedalaman hierarki statis:

```html
<div> <!-- Root Block -->
  <section>
    <p>Static Label</p>
    <span>{{ dynamicValue }}</span> <!-- Dynamic Node -->
  </section>
</div>
```

Representasi runtime Block:
```javascript
// dynamicChildren hanya melacak <span>, mengabaikan <section> dan <p>
blockVNode.dynamicChildren = [ spanVNode ];
```
Ketika update terjadi, loop patching hanya mengeksekusi `patch(oldBlock.dynamicChildren[i], newBlock.dynamicChildren[i])`. Kompleksitas runtime reconciliation berkurang dari $O(\text{total nodes})$ menjadi $O(\text{dynamic nodes})$.

#### 3.4. Custom Directives Internal Architecture

Di balik layar, custom directive dikompilasi oleh transform directive menjadi wrapper `withDirectives`:

```typescript
// Template: <input v-focus:border.lazy="dynamicVal" />
// Dikompilasi menjadi:
_withDirectives(_createElementVNode("input", null, null, 512 /* NEED_PATCH */), [
  [
    _directive_focus,
    _ctx.dynamicVal,
    "border",
    { lazy: true }
  ]
])
```

Fungsi `withDirectives` menyematkan *lifecycle hooks* custom directive ke dalam hook VNode runtime internal. Siklus hidup custom directive adalah:
*   `created(el, binding, vnode)`: Terpanggil sebelum atribut elemen atau event listener diinisialisasi.
*   `beforeMount(el, binding, vnode)`: Terpanggil saat elemen belum terpasang ke DOM fisik.
*   `mounted(el, binding, vnode)`: Elemen terpasang ke DOM fisik. Operasi DOM imperatif aman di sini.
*   `beforeUpdate(el, binding, vnode, prevVnode)`: Terpanggil sebelum komponen penampung memperbarui VNode tree-nya.
*   `updated(el, binding, vnode, prevVnode)`: Terpanggil setelah komponen penampung dan elemen memperbarui layout/DOM.
*   `beforeUnmount(el, binding, vnode)`: Terpanggil sebelum elemen induk dilepas dari DOM.
*   `unmounted(el, binding, vnode)`: Terpanggil setelah elemen dilepas dari DOM. Wajib untuk membersihkan event listeners, observers, dan memory references.

---

### 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan (Business & Performance Impact) | Apa Sebenarnya (Mekanisme Teknis) |
| :--- | :--- | :--- |
| **Compiler Optimization (PatchFlags/Block Tree)** | Mencegah degradasi CPU saat rendering data masif pada perangkat klien berspesifikasi rendah. | Kompilator menandai slot dinamis dan meratakan tree VNode dinamis menjadi list 1D untuk $O(K)$ diffing. |
| **`v-memo` Directive** | Mencegah recalculation VNode subtree saat ribuan baris list dirender ulang tetapi hanya 1 baris berubah. | Melakukan caching manual sub-tree VNode berdasarkan array dependensi kondisi (`[item.id, item.selected]`). |
| **Custom Directives vs Child Components** | Menghindari *component instance overhead* (setup reactive state, slot allocation, VNode wrapper overhead) hanya untuk fungsionalitas DOM reuse. | Ekstensi imperatif langsung pada lifecycle level native DOM node tanpa menambah overhead instance Vue component. |
| **`useTemplateRef` (Vue 3.5+)** | Type-safety penuh, decoupling dari scoping template, dan mencegah bug string-ref collision. | API reaktif modern berbasis Symbol/Typed Keys untuk mengakses host DOM node atau component instance. |

---

### 5. How (Workflow Detail)

Alur kerja evaluasi direktif dan manipulasi DOM imperatif dalam engine runtime:

```
[Trigger State Mutation]
           │
           ▼
[Runtime Scheduler (flushJobs)]
           │
           ▼
[Invoke Component Render Function]
           │
           ▼
[Evaluate withDirectives()] 
           │
           ├─► Binding comparison (oldBinding.value vs newBinding.value)
           ▼
[VNode Diffing via DynamicChildren (PatchFlags Filter)]
           │
           ├─► Apply DOM attributes/style/classes
           ▼
[Invoke Directive Lifecycle: beforeUpdate]
           │
           ▼
[Native DOM Patch Operation (DOM Mutation by Vue)]
           │
           ▼
[Invoke Directive Lifecycle: updated]
           │
           ▼
[Flush Post Cbs / DOM Template Refs Updated]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Kompiler Vue vs Traditional Virtual DOM
*   **Traditional VDOM (React-style):** Bayangkan seorang inspektur gedung yang harus memeriksa setiap bata di dinding (elemen statis dan dinamis) setiap kali terjadi getaran kecil untuk memastikan tidak ada retakan.
*   **Vue 3 Compiler Block Tree:** Saat dinding dibangun, arsitek menandai hanya bata yang memiliki engsel bergerak (elemen dinamis) dengan cat fosfor. Saat terjadi getaran, inspektur mematikan lampu dan hanya memeriksa bata yang menyala dalam daftar khusus.

```
TRADITIONAL VDOM DIFF (O(N)):
[DIV] ────────────────────────── (Check)
  ├── [SECTION] ──────────────── (Check)
  │     ├── [P (Static)] ─────── (Check - Waste)
  │     └── [SPAN (Dynamic)] ─── (Check - Found diff)
  └── [FOOTER (Static)] ──────── (Check - Waste)

VUE 3 BLOCK TREE DIFF (O(1) dynamic):
[BLOCK: dynamicChildren Array]
  └── [SPAN (PatchFlags: TEXT)] ─► Langsung patch el.nodeValue! 
                                   (SECTION, P, FOOTER diabaikan total)
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Deep Dive Custom Directive (Click Outside dengan Modifier Engine)

Implementasi custom directive enterprise-ready dengan typesafe modifiers, weak cleanup mapping, dan handling pointer events.

```typescript
// directives/vClickOutside.ts
import type { Directive, DirectiveBinding } from 'vue';

interface ClickOutsideElement extends HTMLElement {
  __clickOutsideHandler__?: (event: PointerEvent) => void;
}

export interface ClickOutsideModifiers {
  capture?: boolean;
  stop?: boolean;
}

export const vClickOutside: Directive<ClickOutsideElement, (e: PointerEvent) => void> = {
  mounted(el: ClickOutsideElement, binding: DirectiveBinding<(e: PointerEvent) => void>) {
    if (typeof binding.value !== 'function') {
      console.warn(`[v-click-outside]: Handler must be a function, received ${typeof binding.value}`);
      return;
    }

    const handler = (event: PointerEvent) => {
      const target = event.target as Node | null;
      // Validasi apakah klik berasal dari child atau elemen itu sendiri
      if (!target || el === target || el.contains(target)) {
        return;
      }

      if (binding.modifiers.stop) {
        event.stopPropagation();
      }

      binding.value(event);
    };

    el.__clickOutsideHandler__ = handler;
    const useCapture = !!binding.modifiers.capture;
    
    document.addEventListener('pointerdown', handler, { capture: useCapture, passive: true });
  },

  beforeUnmount(el: ClickOutsideElement, binding: DirectiveBinding) {
    if (el.__clickOutsideHandler__) {
      const useCapture = !!binding.modifiers.capture;
      document.removeEventListener('pointerdown', el.__clickOutsideHandler__, { capture: useCapture });
      delete el.__clickOutsideHandler__;
    }
  }
};
```

#### 7.2. Practical Example: High-Frequency High-Performance Canvas Bridge

Integrasi rendering Canvas imperatif 60 FPS menggunakan Template Refs modern Vue 3.5+ (`useTemplateRef`) dengan lifecycle teardown yang ketat.

```vue
<!-- components/TelemetryChart.vue -->
<script setup lang="ts">
import { useTemplateRef, onMounted, onBeforeUnmount, watch } from 'vue';

interface MetricPoint {
  timestamp: number;
  value: number;
}

const props = defineProps<{
  metrics: MetricPoint[];
  color: string;
}>();

// Vue 3.5+ explicit typed template ref
const canvasRef = useTemplateRef<HTMLCanvasElement>('canvasTarget');

let animationFrameId: number | null = null;
let ctx: CanvasRenderingContext2D | null = null;

function renderCanvas(): void {
  const canvas = canvasRef.value;
  if (!canvas || !ctx) return;

  const { width, height } = canvas;
  ctx.clearRect(0, 0, width, height);
  
  if (props.metrics.length < 2) return;

  ctx.beginPath();
  ctx.strokeStyle = props.color;
  ctx.lineWidth = 1.5;

  const minVal = Math.min(...props.metrics.map(m => m.value));
  const maxVal = Math.max(...props.metrics.map(m => m.value)) || 1;
  const range = maxVal - minVal;

  props.metrics.forEach((point, index) => {
    const x = (index / (props.metrics.length - 1)) * width;
    const normalizedY = 1 - (point.value - minVal) / (range === 0 ? 1 : range);
    const y = normalizedY * (height - 10) + 5;

    if (index === 0) {
      ctx!.moveTo(x, y);
    } else {
      ctx!.lineTo(x, y);
    }
  });

  ctx.stroke();
}

function scheduleRender(): void {
  if (animationFrameId !== null) return;
  animationFrameId = requestAnimationFrame(() => {
    renderCanvas();
    animationFrameId = null;
  });
}

// Sinkronisasi data imperatif tanpa memicu siklus diffing Virtual DOM Vue
watch(() => props.metrics, scheduleRender, { deep: false });

onMounted(() => {
  if (canvasRef.value) {
    ctx = canvasRef.value.getContext('2d');
    // Sinkronisasi pixel ratio untuk Retina display
    const dpr = window.devicePixelRatio || 1;
    const rect = canvasRef.value.getBoundingClientRect();
    canvasRef.value.width = rect.width * dpr;
    canvasRef.value.height = rect.height * dpr;
    ctx?.scale(dpr, dpr);
    renderCanvas();
  }
});

onBeforeUnmount(() => {
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId);
    animationFrameId = null;
  }
  ctx = null;
});
</script>

<template>
  <div class="telemetry-wrapper">
    <!-- Static block: VDOM engine mengabaikan canvas internal saat rendering -->
    <canvas 
      ref="canvasTarget" 
      class="telemetry-canvas"
      aria-label="High Frequency Metric Stream"
    ></canvas>
  </div>
</template>

<style scoped>
.telemetry-wrapper {
  position: relative;
  width: 100%;
  height: 200px;
}
.telemetry-canvas {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Real-Time Trading Order Book (L2 Market Depth)
*   **Konteks:** Sebuah exchange crypto enterprise memproses hingga 2.500 mutasi order per detik via WebSocket. Komponen order book me-render 100 baris *bids* dan 100 baris *asks*.
*   **Bottleneck:** Komponen awal menggunakan rendering standar `v-for`. Setiap kali single tick order masuk, seluruh list 200 baris VNode ter-diffing ulang. Hasil profiling Chrome DevTools: CPU utilization mencapai 92%, Frame rate jatuh ke 18 FPS (terjadi Long Task rata-rata 48ms di main thread).
*   **Solusi Arsitektur:**
    1.  Menerapkan direktif `v-memo` pada level node baris untuk memoize VNode subtree.
    2.  Menggunakan *IntersectionObserver Directive* kustom untuk menghentikan kalkulasi visual bagi order rows yang ter-scroll keluar layar.
    3.  Mengisolasi format mata uang menggunakan directive statis native DOM text-mutation alih-alih dynamic component bindings.

```vue
<!-- components/OrderBookRow.vue -->
<script setup lang="ts">
export interface OrderRecord {
  id: string;
  price: number;
  size: number;
  total: number;
  side: 'bid' | 'ask';
  updatedAt: number;
}

defineProps<{
  orders: OrderRecord[];
}>();
</script>

<template>
  <div class="order-container">
    <!-- 
      v-memo membekukan VNode diffing sepenuhnya KECUALI nilai dependency berubah.
      Jika sebuah tick data mengalir tapi item.size dan item.total sama,
      Vue sama sekali TIDAK menjalankan Virtual DOM reconciliation untuk node ini.
    -->
    <div
      v-for="order in orders"
      :key="order.id"
      v-memo="[order.size, order.total, order.side]"
      class="order-row"
      :class="order.side"
    >
      <span class="col-price">{{ order.price.toFixed(2) }}</span>
      <span class="col-size">{{ order.size.toFixed(4) }}</span>
      <span class="col-total">{{ order.total.toFixed(4) }}</span>
      
      <!-- Micro depth visual bar: Menggunakan CSS custom property untuk bypass dynamic style parsing -->
      <div 
        class="depth-visual"
        :style="{ '--depth-percent': `${(order.size / 10) * 100}%` }"
      ></div>
    </div>
  </div>
</template>

<style scoped>
.order-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  position: relative;
  contain: strict; /* CSS Containment: Mengisolasi repaint/reflow dari seluruh dokumen */
  height: 24px;
}
.depth-visual {
  position: absolute;
  top: 0;
  bottom: 0;
  right: 0;
  width: var(--depth-percent);
  opacity: 0.15;
  pointer-events: none;
}
.bid .depth-visual { background-color: #00c087; }
.ask .depth-visual { background-color: #ff3b30; }
</style>
```

**Hasil Pengukuran:**
*   Main Thread Execution Time turun dari **48ms** ke **3.2ms** per frame tick.
*   Frame Rate stabil di **60 FPS**.
*   Garbage Collector invocations berkurang hingga **74%** karena alokasi VNode dihilangkan oleh `v-memo`.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian & Batasan | Kondisi Penggunaan Tepat |
| :--- | :--- | :--- | :--- |
| **`v-memo` Subtree Caching** | Meniadakan overhead patch VNode; memori CPU dihemat secara signifikan. | Mengonsumsi memori memori referensi array; resiko *stale state* jika dependensi array tidak lengkap. | List tabular besar (>500 items) dengan high-frequency mutation stream. |
| **Custom Directives** | Direct raw-DOM access; reusable lintas elemen; tidak ada wrapper component overhead. | Tidak kompatibel dengan SSR/SSG secara out-of-the-box (perlu SSR hook/Nuxt plugins); mengaburkan flow reaktivitas jika disalahgunakan untuk mengubah state internal Vue. | Fitur fungsional murni DOM (focus, outside click, drag-drop, masking, visibility telemetry). |
| **Direct Native DOM Manipulation via Template Ref** | Performa mutasi absolut (bypass compiler & runtime VDOM); mendukung integrasi canvas/WebGL. | Mengabaikan engine declarative Vue; rawan memory leaks; manual state cleanup saat unmount. | Heavy third-party UI libraries (Monaco, Mapbox, D3.js, Chart.js). |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: SSR Hydration Mismatch Akibat Custom Directive
*   **Gejala:** Console melempar warning: `[Vue warn]: Hydration completed but contains mismatches.` disertai DOM flicker.
*   **Penyebab:** Custom directive mengeksekusi manipulasi DOM pada hook `created` atau `beforeMount` di mana struktur DOM SSR belum terhidrasi di client, atau directive mengubah atribut tanpa SSR-directive transform yang setara di server.
*   **Solusi:** Batasi intervensi native DOM hanya pada hook `mounted`. Pastikan directive yang mempengaruhi atribut SSR didaftarkan dengan compiler transform khusus jika menggunakan SSR/Nuxt:

```typescript
// Solusi: SSR-safe guard di dalam directive
export const vSafeDirective: Directive = {
  mounted(el, binding) {
    // Jalankan DOM manipulation murni di client-side lifecycle
    el.setAttribute('data-active', binding.value ? 'true' : 'false');
  },
  // JANGAN manipulasi DOM di created/beforeMount untuk directive universal SSR!
};
```

#### Kasus 2: Memory Leak Akibat Closure Event Listener pada Directive
*   **Gejala:** Konsumsi heap memory browser terus meningkat seiring pergantian route/halaman hingga tab browser crash.
*   **Penyebab:** Mengikat anonymous handler langsung pada event target tanpa referensi terisolasi untuk proses pelepasan:
```typescript
// BAD: Impossible to remove
el.addEventListener('resize', () => { ... });
```
*   **Solusi:** Simpan referensi method handler langsung ke property native element atau gunakan `WeakMap`:

```typescript
const handlerMap = new WeakMap<HTMLElement, (e: Event) => void>();

export const vWindowResize: Directive = {
  mounted(el, binding) {
    const onResize = (e: Event) => binding.value(e);
    handlerMap.set(el, onResize);
    window.addEventListener('resize', onResize);
  },
  unmounted(el) {
    const onResize = handlerMap.get(el);
    if (onResize) {
      window.removeEventListener('resize', onResize);
      handlerMap.delete(el);
    }
  }
};
```

#### Kasus 3: `v-memo` Stale State Dependency Bug
*   **Gejala:** Data pada layar tidak berubah meskipun property di objek data berubah.
*   **Penyebab:** Lupa menyertakan field data baru ke dalam dependency array `v-memo`:
```html
<!-- BUG: order.status berubah, tetapi UI tidak me-render ulang karena status tidak ada di dependensi! -->
<div v-for="order in list" :key="order.id" v-memo="[order.price]">
  {{ order.price }} - {{ order.status }}
</div>
```
*   **Solusi:** Selalu audit dependensi `v-memo` agar mencakup seluruh parameter dinamis yang dirender di dalam template subtree tersebut.

---

### 11. Best Practices (Production Checklist)

* [ ] **Strict Directive Cleanup:** Setiap event listener, interval, `ResizeObserver`, atau `IntersectionObserver` yang diinisialisasi dalam `mounted` **harus** didestruksi tuntas di `unmounted`.
* [ ] **WeakMap Storage:** Gunakan `WeakMap` untuk mengasosiasikan metadata/instance pihak ketiga dengan native `HTMLElement` agar tidak menahan referensi sampah dari garbage collector.
* [ ] **Avoid Mutating VNode-Managed DOM:** Jangan pernah menghapus atau menambah elemen anak secara imperatif (`el.appendChild`, `el.removeChild`) di dalam elemen yang dikontrol oleh template Vue (`v-for`, `v-if`), karena akan merusak sinkronisasi Block dynamic children tree runtime Vue.
* [ ] **Audited `v-memo` Keying:** Saat menggunakan `v-memo`, pastikan selalu dikombinasikan dengan `:key` yang unik dan deterministik pada node yang sama.
* [ ] **SSR Isolation:** Tambahkan pengecekan lingkungan `typeof window !== 'undefined'` atau isolasi directive registration pada build Nuxt/SSR runtime.
* [ ] **Template Ref Nullability:** Jangan pernah mengakses `.value` dari sebuah template ref di level `setup()` root execution. Akses hanya di dalam hook `onMounted`, `watchPostEffect`, atau event handler.

---

### 12. Hands-on Practice

Buat skenario lab integrasi custom direct-manipulation framework.

#### Folder Setup
```bash
mkdir -p hands-on/m02/src/directives hands-on/m02/src/components
cd hands-on/m02
```

#### File 1: `src/directives/vDraggable.ts`
Implementasi custom directive drag-and-drop performa tinggi yang memanipulasi GPU transform tanpa memicu layout re-flow.

```typescript
import type { Directive, DirectiveBinding } from 'vue';

interface DraggableState {
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
  isDragging: boolean;
  onPointerDown: (e: PointerEvent) => void;
  onPointerMove: (e: PointerEvent) => void;
  onPointerUp: (e: PointerEvent) => void;
}

const stateMap = new WeakMap<HTMLElement, DraggableState>();

export const vDraggable: Directive<HTMLElement> = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const state: DraggableState = {
      startX: 0,
      startY: 0,
      currentX: 0,
      currentY: 0,
      isDragging: false,
      onPointerDown: () => {},
      onPointerMove: () => {},
      onPointerUp: () => {}
    };

    state.onPointerDown = (e: PointerEvent) => {
      // Hanya tangani primary click (tombol kiri)
      if (e.button !== 0) return;
      
      state.isDragging = true;
      state.startX = e.clientX - state.currentX;
      state.startY = e.clientY - state.currentY;
      
      el.setPointerCapture(e.pointerId);
      el.style.willChange = 'transform';
      el.style.cursor = 'grabbing';
    };

    state.onPointerMove = (e: PointerEvent) => {
      if (!state.isDragging) return;
      
      state.currentX = e.clientX - state.startX;
      state.currentY = e.clientY - state.startY;

      // Transformasi murni via GPU compositor
      el.style.transform = `translate3d(${state.currentX}px, ${state.currentY}px, 0)`;
    };

    state.onPointerUp = (e: PointerEvent) => {
      if (!state.isDragging) return;
      
      state.isDragging = false;
      el.releasePointerCapture(e.pointerId);
      el.style.willChange = 'auto';
      el.style.cursor = 'grab';

      // Opsional: invoke callback jika directive value bertipe function
      if (typeof binding.value === 'function') {
        binding.value({ x: state.currentX, y: state.currentY });
      }
    };

    el.style.cursor = 'grab';
    el.addEventListener('pointerdown', state.onPointerDown);
    el.addEventListener('pointermove', state.onPointerMove);
    el.addEventListener('pointerup', state.onPointerUp);
    el.addEventListener('pointercancel', state.onPointerUp);

    stateMap.set(el, state);
  },

  unmounted(el: HTMLElement) {
    const state = stateMap.get(el);
    if (state) {
      el.removeEventListener('pointerdown', state.onPointerDown);
      el.removeEventListener('pointermove', state.onPointerMove);
      el.removeEventListener('pointerup', state.onPointerUp);
      el.removeEventListener('pointercancel', state.onPointerUp);
      stateMap.delete(el);
    }
  }
};
```

#### File 2: `src/components/InteractiveBoard.vue`
Komponen testbed yang menguji stabilitas template ref dan performa custom directive.

```vue
<script setup lang="ts">
import { ref, useTemplateRef } from 'vue';
import { vDraggable } from '../directives/vDraggable';

interface ItemPosition {
  id: number;
  label: string;
  x: number;
  y: number;
}

const items = ref<ItemPosition[]>([
  { id: 1, label: 'Task Box Alpha', x: 0, y: 0 },
  { id: 2, label: 'Task Box Beta', x: 0, y: 0 },
]);

const statusRef = useTemplateRef<HTMLParagraphElement>('statusBar');

function handleDragEnd(id: number, pos: { x: number; y: number }) {
  const target = items.value.find(i => i.id === id);
  if (target) {
    target.x = pos.x;
    target.y = pos.y;
  }
  if (statusRef.value) {
    statusRef.value.innerText = `Moved node ${id} to -> X: ${pos.x.toFixed(0)}px, Y: ${pos.y.toFixed(0)}px`;
  }
}
</script>

<template>
  <div class="board-canvas">
    <p ref="statusBar" class="status-bar">Drag elements to evaluate events</p>
    
    <div
      v-for="item in items"
      :key="item.id"
      v-draggable="(pos: any) => handleDragEnd(item.id, pos)"
      class="draggable-node"
    >
      <h3>{{ item.label }}</h3>
      <p>ID: {{ item.id }}</p>
    </div>
  </div>
</template>

<style scoped>
.board-canvas {
  width: 100%;
  height: 500px;
  background-color: #1e1e24;
  border: 1px solid #333;
  position: relative;
  overflow: hidden;
  user-select: none;
}
.status-bar {
  position: absolute;
  top: 10px;
  left: 10px;
  color: #a0aec0;
  font-family: monospace;
}
.draggable-node {
  position: absolute;
  top: 60px;
  left: 60px;
  width: 160px;
  padding: 16px;
  background-color: #2d3748;
  color: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.3);
  touch-action: none;
}
</style>
```

---

### 13. Exercise

#### Tingkat Kesulitan: Easy
*   **Deskripsi Tugas:** Buat custom directive `v-autofocus` yang memberikan fokus otomatis pada elemen `<input>` atau `<textarea>` saat pertama kali dirender ke DOM. Tangani kasus modifier `.select` (misal: `v-autofocus.select`) yang jika ada, tidak hanya memfokuskan kursor tetapi juga mengeksekusi `el.select()`.
*   **Kriteria Evaluasi:**
    1. Elemen berhasil difokuskan saat transisi komponen selesai.
    2. Modifier dinilai dengan benar menggunakan `binding.modifiers`.
    3. Type-safe pada TypeScript compiler tanpa `any`.

#### Tingkat Kesulitan: Medium
*   **Deskripsi Tugas:** Implementasikan directive `v-tooltip` yang menerima string teks, lalu merender custom DOM element tooltip floating (menggunakan native `div` yang dipasang ke `document.body` via dynamic pointer binding). Directive wajib menghancurkan elemen floating tersebut saat elemen target di-unmount agar tidak terjadi kebocoran DOM (*detached DOM tree*).
*   **Kriteria Evaluasi:**
    1. Tooltip diposisikan secara presisi terhadap target (`getBoundingClientRect`).
    2. Event `pointerenter` dan `pointerleave` terdaftar dan terlepas secara simetris.
    3. Memory leaks zero threshold terverifikasi pada DevTools Heap Profiler.

#### Tingkat Kesulitan: Hard
*   **Deskripsi Tugas:** Buat custom virtualization directive `v-render-viewport` yang memantau elemen list panjang. Directive ini harus mengamati elemen target via `IntersectionObserver`. Ketika elemen berada di luar viewport (+/- 200px threshold margin), terapkan visibilitas terisolasi menggunakan `content-visibility: hidden` dan set `contain-intrinsic-size` dinamis sesuai tinggi elemen saat terakhir dirender.
*   **Kriteria Evaluasi:**
    1. Mencegah alokasi repaint layout browser saat scrolling cepat.
    2. Layout shifting dicegah via kalkulasi intrinsic size yang presisi.
    3. Multi-instance observer dikelola secara efisien menggunakan singleton Shared Observer Pattern untuk menghemat context switching browser.

---

### 14. Challenge

#### Skenario Kasus Kompleks: "Enterprise Real-time Canvas Dashboard with Hybrid VNode Layering"

**Spesifikasi Masalah:**
Perusahaan IoT logistik membutuhkan dashboard peta armada yang memonitor 50.000 kontainer kargo bergerak secara real-time. Tim Anda dihadapkan pada arsitektur hibrida:
1.  **Engine Grafis Imperatif:** Sebuah WebGL/Canvas layer di latar belakang yang menggambar visual kontainer dengan mutasi koordinat 30 FPS.
2.  **HTML Declarative Interaction Layer:** Lapisan interaktif Vue di atas kanvas yang merender panel detail konfigurasi, popup telemetry, dan context-menu kontainer saat kontainer di klik.

**Tantangan Arsitektur:**
1.  **Sinkronisasi Imperatif-Deklaratif:** Bagaimana Anda mendesain arsitektur di mana event klik pada Canvas imperatif memicu kemunculan popup Vue di koordinat target secara reaktif tanpa menyebabkan siklus re-render pada seluruh layer aplikasi?
2.  **Zero-Allocation Custom Directive:** Rancang arsitektur directive kustom bernama `v-spatial-sync` yang mengikat posisi DOM Vue node floating tepat di atas objek koordinat Canvas, menggunakan dirty-checking berkinerja tinggi yang disinkronisasikan ke refresh rate layar (`requestAnimationFrame`) tanpa membebani runtime reactivity dependency tree Vue.
3.  **Stress Testing Bounds:** Rancang skenario pengujian di mana memory heap harus tetap flat di bawah 80MB stabil selama 1 jam operasi terus-menerus tanpa ada object retention dari detach element.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)

1.  **Kapan lifecycle hook `beforeMount` pada custom directive dieksekusi?**
    *   a) Setelah elemen disisipkan ke DOM fisik induknya.
    *   b) Tepat sebelum template AST dibuat oleh parser.
    *   c) Setelah VNode dibuat tetapi sebelum elemen DOM fisik disisipkan ke dokumen.
    *   d) Setelah seluruh child components selesai dimount.
    *   *Kunci Jawaban:* **c**
    *   *Penjelasan:* `beforeMount` dipanggil saat VNode elemen telah diasosiasikan dengan instance rendering, tetapi proses manipulasi penyisipan elemen fisik ke dalam dokumen nyata belum dieksekusi.

2.  **Apa fungsi utama dari PatchFlag pada internal engine Vue 3?**
    *   a) Mengubah kode template menjadi string CSS otomatis.
    *   b) Memberikan penanda integer numerik (bitwise) ke VNode agar runtime hanya mengecek properti yang relevan saat diffing.
    *   c) Menandakan bahwa komponen harus di-mount di server-side rendering.
    *   d) Menghentikan rendering template secara asinkron.
    *   *Kunci Jawaban:* **b**
    *   *Penjelasan:* PatchFlag adalah bitmask yang dihasilkan saat tahap transformasi kompiler untuk mengidentifikasi mutasi spesifik (misal: hanya TEXT atau CLASS) yang perlu diperiksa saat patch.

3.  **Directive bawaan manakah yang digunakan untuk mem-bypass diffing VNode subtree berdasarkan array dependensi data?**
    *   a) `v-pre`
    *   b) `v-once`
    *   c) `v-memo`
    *   d) `v-cloak`
    *   *Kunci Jawaban:* **c**
    *   *Penjelasan:* `v-memo` menerima array dependensi. Jika tiap nilai dependensi sama dengan evaluasi render sebelumnya, runtime akan langsung melompati rekonsiliasi VNode subtree bersangkutan.

4.  **Apa yang membedakan `v-once` dengan `v-memo`?**
    *   a) `v-once` tidak menerima dependensi dan membekukan render selamanya, sedangkan `v-memo` dapat mengevaluasi ulang jika dependensi berubah.
    *   b) `v-once` khusus untuk tag `<canvas>`, sedangkan `v-memo` untuk elemen tabular.
    *   c) `v-memo` dieksekusi di server, `v-once` di browser.
    *   d) `v-once` menghapus elemen dari DOM tree setelah mount pertama.
    *   *Kunci Jawaban:* **a**
    *   *Penjelasan:* `v-once` hanya dirender tepat satu kali saat inisialisasi dan tidak pernah diperbarui lagi. `v-memo` dapat diperbarui kembali jika ada array dependensinya yang berubah nilainya.

5.  **Pada Vue 3.5+, API manakah yang direkomendasikan secara native untuk mengikat referensi elemen DOM secara aman dan terisolasi dari type casting manual?**
    *   a) `document.getElementById`
    *   b) `useTemplateRef`
    *   c) `getCurrentInstance().refs`
    *   d) `ref<HTMLElement>(null)` (legacy pattern)
    *   *Kunci Jawaban:* **b**
    *   *Penjelasan:* Vue 3.5 memperkenalkan `useTemplateRef` yang secara eksplisit menghubungkan variabel TypeScript dengan ref string di template secara type-safe.

---

#### Bagian 2: Intermediate (5 Soal)

6.  **Mengapa penggunaan `el.parentNode.removeChild(el)` di dalam lifecycle `unmounted` custom directive dianggap sebagai anti-pattern fatal pada Vue 3?**
    *   a) Karena browser akan otomatis menutup window target.
    *   b) Karena node fisik tersebut sebenarnya sudah dicabut dari DOM oleh algoritma patcher Vue; memanggil parentNode yang bernilai null akan melempar runtime exception.
    *   c) Karena akan menghapus seluruh data store Pinia secara global.
    *   d) Karena compiler tidak bisa lagi memproduksi AST Javascript.
    *   *Kunci Jawaban:* **b**
    *   *Penjelasan:* Pada hook `unmounted`, elemen bersangkutan telah dicabut dari tree dokumen oleh internal virtual DOM remover. Menjalankan traversal `el.parentNode` beresiko fatal karena referensi parent-nya telah bernilai `null`.

7.  **Apa yang terjadi pada level kompiler ketika elemen memiliki penanda static hoisting?**
    *   a) Elemen tersebut diubah menjadi image base64.
    *   b) VNode elemen diekstraksi ke luar dari fungsi render komponen dan hanya dialokasikan satu kali di memori.
    *   c) Elemen tersebut disisipkan ke dalam `localStorage`.
    *   d) Elemen dipaksa menjadi asynchronous component.
    *   *Kunci Jawaban:* **b**
    *   *Penjelasan:* Static hoisting memindahkan pembuatan VNode statis keluar dari fungsi `render()`. Saat komponen me-render ulang, fungsi render menggunakan referensi VNode statis yang sama tanpa alokasi memori baru.

8.  **Bagaimana representasi struktur Block Tree mempengaruhi traversal perbandingan virtual DOM?**
    *   a) Traversal beralih dari $O(N)$ (seluruh node) menjadi $O(1)$ dynamic nodes via flattening array `dynamicChildren`.
    *   b) Traversal mengabaikan dynamic children dan hanya memvalidasi node statis.
    *   c) Block tree mematikan seluruh siklus Garbage Collection browser.
    *   d) Block tree mengharuskan rendering berbasis multi-threading Web Worker.
    *   *Kunci Jawaban:* **a**
    *   *Penjelasan:* Block tree melacak seluruh elemen dinamis dalam array 1D (`dynamicChildren`). Patching langsung melompat antar dynamic node tanpa menelusuri cabang pohon statis.

9.  **Manakah implementasi lifecycle custom directive yang tepat untuk mengupdate posisi elemen saat re-render komponen terjadi?**
    *   a) Menggunakan hook `created` dan `mounted`.
    *   b) Menggunakan hook `beforeMount` dan `unmounted`.
    *   c) Menggunakan hook `beforeUpdate` atau `updated`.
    *   d) Hanya menggunakan hook `unmounted`.
    *   *Kunci Jawaban:* **c**
    *   *Penjelasan:* Mutasi runtime yang dipicu oleh perubahan state data pada komponen penampung harus ditangani di dalam hook `beforeUpdate` atau `updated`.

10. **Apa implikasi penggunaan modifier `.stop` pada direktif click-outside jika target berada di dalam `<iframe>`?**
    *   a) Event iframe otomatis terpantul ke parent container.
    *   b) Pointer event di dalam iframe tidak memicu event listener pada document host karena perbedaan window execution context.
    *   c) Browser mematikan rendering iframe demi alasan keamanan CORS.
    *   d) Handler click-outside akan crash karena ketiadaan memory pointer.
    *   *Kunci Jawaban:* **b**
    *   *Penjelasan:* Iframe memiliki context execution `window` dan `document` terpisah. Event listener yang dipasang pada document parent tidak akan menerima dispatch pointer event yang terjadi di dalam dokumen iframe.

---

#### Bagian 3: Enterprise Scenarios (3 Soal)

11. **Skenario:** Anda memimpin migrasi dashboard analitik finansial enterprise dari Nuxt 2 ke Nuxt 3 (Universal SSR). Komponen chart kustom Anda yang menggunakan custom directive `v-chart-render` melempar error fatal saat initial load: `ReferenceError: document is not defined`. Apa akar masalah dan solusi arsitektural yang paling tepat?
    *   a) Mengubah Node.js runtime server menjadi WebAssembly.
    *   b) Direktif mencoba mengakses objek browser global (`document`/`window`) saat kompilasi SSR di Node.js context; solusinya adalah mendefinisikan directive getSSRProps lifecycle terpisah atau membatasi eksekusi imperatif native DOM hanya pada hook `mounted`.
    *   c) Mengganti seluruh directive menjadi `v-html`.
    *   d) Mematikan TypeScript validation pada Nuxt configuration file.
    *   *Kunci Jawaban:* **b**
    *   *Penjelasan:* Di server-side rendering, `window` dan `document` tidak tersedia. Custom directive yang mengakses DOM sebelum client hydration (`created`/setup) akan crash. Solusinya adalah memindahkan operasi DOM ke `mounted` yang hanya berjalan di client-side, atau menyediakan plugin directive universal khusus.

12. **Skenario:** Di sebuah platform e-commerce dengan sistem infinite scroll yang merender 10.000 ulasan produk, engineer mengeluhkan browser memory footprint yang naik sebesar 450MB setelah scroll selama 3 menit. Setiap card ulasan memiliki directive kustom `v-badge-tooltip` yang menautkan event listener ke `window.addEventListener('scroll', handler)`. Inspeksi memory heap menunjukkan ribuan instance fungsi listener tidak terlepas. Mengapa ini terjadi dan bagaimana perbaikan permanennya?
    *   a) Directive Vue tidak memiliki akses ke garbage collector; solusi satu-satunya adalah me-refresh halaman tiap 100 items.
    *   b) Handler function dibuat secara inline/closure di `mounted` tanpa menyimpan referensi fungsi yang sama untuk dipanggil pada `unmounted`, sehingga listener di `window` terus menumpuk; solusinya menyimpan referensi handler pada elemen atau menggunakan `WeakMap` dan melepasnya via `window.removeEventListener` pada `unmounted`.
    *   c) Masalah berada di CSS layout containment; solusinya mengubah display card menjadi `display: flex`.
    *   d) Patcher Vue 3 secara default menahan seluruh referensi VNode di global scope.
    *   *Kunci Jawaban:* **b**
    *   *Penjelasan:* Jika fungsi listener dideklarasikan secara anonymous di dalam scope `mounted`, referensi fungsi tersebut tidak dapat diakses saat `unmounted` untuk dibatalkan via `removeEventListener`. Karena terikat ke `window`, objek context tidak dapat di-garbage collect dan menyebabkan kebocoran memori parah.

13. **Skenario:** Tim backend Anda menyajikan data live streaming via SSE (Server-Sent Events) yang mengupdate 500 baris tabel setiap 100ms. UI tabel mulai mengalami freezing input dan frame rate jatuh di bawah 15 FPS. Tim telah mencoba menambahkan `:key="row.id"`, namun freezing tetap terjadi. Manakah intervensi optimasi compiler & rendering template Vue yang memberikan dampak reduksi overhead diffing paling signifikan?
    *   a) Menghapus atribut `:key` dari seluruh elemen baris.
    *   b) Mengganti Composition API kembali ke Options API.
    *   c) Menerapkan direktif `v-memo="[row.value, row.status]"` pada elemen baris untuk mengeliminasi rekonsiliasi VNode jika data substansial tidak berubah, dikombinasikan dengan pemisahan immutable data state.
    *   d) Mengubah seluruh tabel menjadi native string HTML via `v-html`.
    *   *Kunci Jawaban:* **c**
    *   *Penjelasan:* Penggunaan `v-memo` secara eksplisit menginstruksikan runtime Vue untuk mem-bypass pembuatan dan rekonsiliasi VNode subtree baris tabel jika nilai-nilai dalam dependency array tidak mengalami mutasi, memangkas penggunaan CPU main-thread hingga di bawah batas bahaya rendering frame.

---

### 16. Summary

1.  **Compiler-Informed Reconciliation:** Kekuatan performa Vue 3 bersumber dari sinergi antara *compiler* dan *runtime*. Template dikompilasi menjadi AST, dianalisis secara statis untuk menghasilkan **PatchFlags** dan **Block Tree**, yang mengubah traversal perbandingan VNode dari $O(N)$ total node menjadi $O(K)$ dynamic node saja.
2.  **Fine-Grained DOM Caching:** Direktif `v-memo` dan `v-once` menyediakan kendali level enterprise bagi engineer untuk membatasi eksekusi rekonsiliasi VDOM pada komponen berkepadatan tinggi (*high-throughput real-time systems*).
3.  **Enterprise Custom Directives:** Custom directives adalah abstraksi terbersih untuk fungsionalitas manipulasi DOM native yang reusable. Direktif enterprise wajib mengimplementasikan isolasi state (via `WeakMap`), simetri siklus hidup pembersihan (`mounted` $\leftrightarrow$ `unmounted`), serta mitigasi kompatibilitas SSR.
4.  **Imperative-Declarative Decoupling:** Penggunaan `useTemplateRef` (Vue 3.5+) memungkinkan kontrol presisi atas integrasi library pihak ketiga berbasis native DOM (Canvas, WebGL, Heavy Editors) tanpa merusak keutuhan status reaktif deklaratif inti aplikasi.