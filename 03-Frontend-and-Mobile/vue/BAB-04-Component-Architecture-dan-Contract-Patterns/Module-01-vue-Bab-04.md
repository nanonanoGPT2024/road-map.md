# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Utama:** Vue.js Enterprise Engineering
*   **Bab:** 04 — Advanced Component Architecture & System Design
*   **Modul:** 01 — Component Architecture & Contract Patterns
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** Vue 3 Composition API, TypeScript Generics, Reaktivitas Mendalam (`proxy`, `effectScope`), Desain Komponen Dasar (`props`, `emits`, `slots`).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta ajar diharapkan memiliki kapabilitas teknis untuk:

1.  **Merancang Kontrak Komponen Bersih:** Mengabstraksikan antarmuka komponen (*public API*) menggunakan TypeScript Generic Interfaces untuk `props`, `emits`, `slots`, dan eksposur `expose` tanpa kebocoran implementasi (*implementation leak*).
2.  **Menerapkan Pola Komposisi Maju:** Mengimplementasikan pola *Compound Components*, *Headless Components*, dan *Control Inversion* menggunakan Reactive Provide/Inject berbobot enterprise.
3.  **Mengoptimalkan Siklus Rendering dan Reaktivitas:** Menghindari *unnecessary re-renders* dengan mengisolasi ketergantungan reaktif antar batas (*boundaries*) komponen anak dan induk.
4.  **Membangun Sistem Kontrak Type-Safe Secara Penuh:** Menggunakan *generic components* (`<script setup lang="ts" generic="...">`) untuk validasi *compile-time* yang ketat pada komponen data-driven (misalnya Data Table, Dynamic Form).
5.  **Menerapkan Strategi Mitigasi Anti-Pattern:** Mengidentifikasi dan membongkar *prop drilling*, *god components*, serta kebocoran memori akibat *circular reactive references*.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa perangkat lunak front-end skala enterprise, komponen bukanlah sekadar potongan markup HTML yang dibundel bersama CSS dan JavaScript. **Komponen adalah sebuah Micro-Contract (Kontrak Mikro)**.

### Paradigma: Component as a Micro-Service / Black Box
Sebagaimana arsitektur *microservices* berkomunikasi secara ketat melalui protokol jaringan (gRPC, REST) dengan skema payload yang divalidasi (Protocol Buffers, OpenAPI), sebuah komponen Vue harus dipandang sebagai entitas otonom yang berkomunikasi secara terisolasi melalui:
*   **Inbound Channel (Inputs):** `Props` dan context injection (`inject`). Diperlakukan sebagai *read-only assertions*.
*   **Outbound Channel (Outputs):** `Emits` dan event dispatchers. Diperlakukan sebagai *declarative signals/telemetry*.
*   **Content Injection (Transclusion):** `Slots` dan scoped slot payloads. Diperlakukan sebagai *Inversion of Control (IoC)* untuk visual rendering.
*   **Imperative Escapes:** `defineExpose`. Diperlakukan sebagai *RPC methods* yang digunakan hanya jika model deklaratif tidak lagi mencukupi.

```
       +-------------------------------------------------------+
       |                  PARENT CONTEXT                       |
       +-------------------------------------------------------+
            |                        ^                    |
  Props (Read-Only)          Emits (Signals)       Slots (IoC Inversion)
            |                        |                    |
            v                        |                    v
       +-------------------------------------------------------+
       |             COMPONENT BLACK-BOX BOUNDARY              |
       |                                                       |
       |  [Internal State] <---> [Pure Business Logic]        |
       |          |                                            |
       |          v                                            |
       |   [Virtual DOM Tree]                                  |
       +-------------------------------------------------------+
            |
       defineExpose (Strict Minimal Imperative Interface)
            |
            v
```

### Prinsip Desain Fundamental
1.  **Strict Boundary Encapsulation:** Sebuah komponen anak tidak boleh mengetahui *siapa* induknya atau *bagaimana* status induk dikelola. Komponen anak hanya mengetahui kontraknya sendiri.
2.  **Explicit over Implicit:** Hindari mutasi implisit atau akses via `$parent` / `$root`. Seluruh pertukaran data harus terlacak dalam antarmuka TypeScript.
3.  **Unidirectional Data Flow (UDF):** Aliran data selalu turun (*down*), perubahan selalu naik lewat peristiwa (*up*). Mutasi langsung terhadap prop objek adalah pelanggaran batas sistem (*system boundary violation*).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah representasi siklus data dan batas isolasi antara Compound Component Set (`AccordionGroup` & `AccordionItem`) yang mengimplementasikan Control Inversion dan Shared Context via Injection Key:

```
[Parent View Context]
         |
         | (Instantiates)
         v
+-----------------------------------------------------------------------------------+
| AccordionGroup.vue (Root Provider)                                                |
|                                                                                   |
|  State Management:                                                                |
|  - activeId: Ref<string | null>                                                   |
|  - registerItem(id: string): void                                                 |
|  - toggleItem(id: string): void                                                   |
|                                                                                   |
|  Dependency Injection Context:                                                    |
|  provide(ACCORDION_INJECTION_KEY, { activeId, registerItem, toggleItem })         |
|                                                                                   |
|  Slots:                                                                           |
|  <slot /> -------------------------------------------------------------+          |
+------------------------------------------------------------------------|----------+
                                                                         |
                                    +------------------------------------+
                                    | Transcluded into default slot
                                    v
+-----------------------------------------------------------------------------------+
| AccordionItem.vue (Consumer & Provider Context)                                   |
|                                                                                   |
|  Injected Dependency:                                                             |
|  - const context = inject(ACCORDION_INJECTION_KEY)                                |
|                                                                                   |
|  Internal Computed:                                                               |
|  - isOpen = computed(() => context.activeId.value === props.id)                   |
|                                                                                   |
|  Render Tree:                                                                     |
|  +-----------------------------------------------------------------------------+  |
|  | <button @click="context.toggleItem(props.id)">                              |  |
|  |    <slot name="header" :isOpen="isOpen"> Default Header </slot>             |  |
|  | </button>                                                                   |  |
|  +-----------------------------------------------------------------------------+  |
|  | <div v-show="isOpen">                                                       |  |
|  |    <slot name="content" :isOpen="isOpen" />                                 |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### Alur Mutasi Kontrak dan Penanganan Event

```
User Clicks Header Button
          │
          ▼
AccordionItem.vue catches Native Click Event
          │
          ▼
AccordionItem memanggil injected method: context.toggleItem(props.id)
          │
          ▼
AccordionGroup.vue context updates: activeId.value = newId
          │
    ┌─────┴─────────────────────────────────┐
    ▼                                       ▼
Effect triggers in AccordionItem A       Effect triggers in AccordionItem B
(activeId === id_A -> true)              (activeId === id_B -> false)
    │                                       │
    ▼                                       ▼
isOpen: true                             isOpen: false
    │                                       │
    ▼                                       ▼
VNode Patch Engine: Update DOM           VNode Patch Engine: Update DOM
(Display Content)                        (Hide Content)
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Engine Pembungkus Script Setup (`<script setup>`)
Di balik layar, Vue Compiler (`@vue/compiler-sfc`) mengonversi SFC `<script setup>` menjadi fungsi `setup(props, { emit, slots, attrs, expose })` standar.

Ketika menggunakan macro compiler:
*   `defineProps<T>()` diekspansi menjadi runtime object schema validator oleh compiler AST parser. Jika kompilasi mendeteksi interface TS murni, kompiler menyusun array runtime types atau struktur validasi otomatis via metadata analisis AST.
*   `defineEmits<T>()` dikonversi menjadi registrasi runtime emit metadata untuk memvalidasi pemanggilan emit pada context VNode.
*   `defineSlots<T>()` tidak mengeksekusi kode JavaScript saat runtime, melainkan memodifikasi tipe VNode rendering engine internal untuk memvalidasi passing children dan slot parameters pada saat kompilasi TypeScript (*type check*).

### 2. Resolusi Dependency Injection Engine (`provide` / `inject`)
Mesin internal Vue menyimpan context dependency injection pada properti instance komponen internal: `currentInstance.provides`.

*   Saat komponen memanggil `provide(key, value)`:
    Vue mengecek apakah `currentInstance.provides` menunjuk ke instance parent yang sama (`Object.create(parent.provides)`). Jika ya, Vue melakukan inheritance prototipikal internal:
    ```typescript
    // Konseptual engine internal Vue:
    let provides = currentInstance.provides;
    const parentProvides = currentInstance.parent && currentInstance.parent.provides;
    if (parentProvides === provides) {
      provides = currentInstance.provides = Object.create(parentProvides);
    }
    provides[key as string | symbol] = value;
    ```
*   Saat komponen memanggil `inject(key)`:
    Vue melakukan lookup traversing ke atas rantai prototipe objek `currentInstance.parent.provides[key]`. Lookup ini beroperasi pada kompleksitas $O(1)$ untuk setiap kedalaman rantai karena sifat prototype lookup engine V8 JavaScript, bukan manipulasi array traversal linier berbiaya tinggi.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Generics pada `<script setup generic="...">`
Semenjak Vue 3.3, Vue memperkenalkan first-class support untuk generic component syntax:

```html
<script setup lang="ts" generic="TItem extends { id: string | number }, TFilter = string">
```

Secara mendalam, deklarasi ini mengubah signature internal komponen SFC yang diekspor dari tipe `DefineComponent<...>` standar menjadi fungsi komponen generik polimorfik:

$$\text{Type}(\text{Component}) = \forall TItem \in \mathcal{O}, \forall TFilter \in \mathcal{U} : \text{Props}(TItem, TFilter) \to \text{VNode}$$

Ini memecahkan kelemahan historis pada Vue di mana koleksi data dinamis (`items: any[]`) kehilangan konteks tipe data ketika diproyeksikan ke *scoped slot props* atau *emitted event payload*.

### Pattern 1: Compound Components Pattern
Pola ini membagi fungsionalitas kompleks menjadi serangkaian komponen terpisah yang bekerja bersama di bawah satu *shared state*, menjaga markup HTML tetap fleksibel dan ekspresif bagi konsumen komponen.

*Keuntungan Arsitektural:*
*   Konsumen komponen memiliki kontrol penuh atas tata letak hierarki visual (*inversion of markup*).
*   Mencegah *Mega-Props* anti-pattern (seperti memberikan 40 props berbeda pada komponen `<Table />` tunggal).

### Pattern 2: Headless Component / Logic Inversion Pattern
Pola pemisahan logika tanpa menyertakan DOM layout visual. Diimplementasikan via **Renderless Components** (memanfaatkan `<slot v-bind="scope" />`) atau **Composables Hooks** (`useComponentLogic()`).

Aturan arsitektur menentukan:
*   Gunakan **Composables** ketika logika sepenuhnya terpisah dari siklus hidup VNode atau struktur pohon templating.
*   Gunakan **Headless Components (Renderless)** ketika logika sangat terikat dengan struktur pohon hierarki UI, transitions, atau scoped slot orchestration.

### Pattern 3: Strict Contract via `InjectionKey<T>`
Pemberian payload konteks tanpa `InjectionKey` bertipe adalah celah kerapuhan runtime enterprise (*runtime vulnerability*). Kita wajib mendefinisikan *Symbol-based InjectionKey*:

```typescript
import type { InjectionKey, Ref } from 'vue';

export interface DataGridContract<T> {
  selectedRow: Ref<T | null>;
  selectRow: (item: T) => void;
  registerColumn: (columnId: string, meta: Record<string, unknown>) => void;
}

// Menjamin type safety downstream saat inject dijalankan
export function createDataGridKey<T>(): InjectionKey<DataGridContract<T>> {
  return Symbol('DataGridContractKey') as InjectionKey<DataGridContract<T>>;
}
```

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental: **Type-Safe Dynamic Select Dropdown** yang mendemonstrasikan generic props, typesafe emits, generic scoped slots, dan controlled exposure.

#### Berkas: `src/components/base/BaseSelect.vue`
```html
<script setup lang="ts" generic="TValue extends string | number, TOption extends { label: string; value: TValue }">
import { ref, computed } from 'vue';

// 1. Definition of Generic Props Contract
interface Props {
  options: TOption[];
  modelValue: TValue | null;
  placeholder?: string;
  disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: 'Pilih opsi...',
  disabled: false
});

// 2. Definition of Strict Emits Contract
interface Emits {
  (e: 'update:modelValue', value: TValue): void;
  (e: 'change', option: TOption): void;
}

const emit = defineEmits<Emits>();

// 3. Definition of Scoped Slots Contract
defineSlots<{
  default?(props: { option: TOption; isSelected: boolean }): any;
  header?(props: { count: number }): any;
}>();

// Internal state
const isOpen = ref<boolean>(false);

const selectedOption = computed<TOption | undefined>(() => {
  return props.options.find(opt => opt.value === props.modelValue);
});

function handleSelect(option: TOption): void {
  if (props.disabled) return;
  emit('update:modelValue', option.value);
  emit('change', option);
  isOpen.value = false;
}

function toggleDropdown(): void {
  if (!props.disabled) {
    isOpen.value = !isOpen.value;
  }
}

// 4. Controlled Imperative API Surface Exposure
function reset(): void {
  isOpen.value = false;
}

defineExpose({
  reset,
  isOpen: computed(() => isOpen.value)
});
</script>

<template>
  <div class="select-container" :class="{ 'is-disabled': disabled }">
    <div v-if="$slots.header" class="select-header">
      <slot name="header" :count="options.length" />
    </div>

    <div class="select-trigger" @click="toggleDropdown">
      <span v-if="selectedOption">{{ selectedOption.label }}</span>
      <span v-else class="placeholder">{{ placeholder }}</span>
    </div>

    <ul v-if="isOpen" class="select-dropdown">
      <li
        v-for="option in options"
        :key="option.value"
        class="select-item"
        :class="{ 'is-selected': option.value === modelValue }"
        @click="handleSelect(option)"
      >
        <slot :option="option" :isSelected="option.value === modelValue">
          {{ option.label }}
        </slot>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.select-container { position: relative; width: 100%; font-family: sans-serif; }
.select-trigger { border: 1px solid #ccc; padding: 8px 12px; cursor: pointer; border-radius: 4px; }
.select-dropdown { position: absolute; top: 100%; left: 0; right: 0; border: 1px solid #ccc; background: #fff; list-style: none; padding: 0; margin: 4px 0 0 0; z-index: 10; max-height: 200px; overflow-y: auto; }
.select-item { padding: 8px 12px; cursor: pointer; }
.select-item:hover { background-color: #f0f0f0; }
.select-item.is-selected { background-color: #e6f7ff; font-weight: bold; }
.is-disabled { opacity: 0.6; pointer-events: none; }
</style>
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Mendedah arsitektur internal dari implementasi `BaseSelect.vue`:

*   **Baris 1:** `<script setup lang="ts" generic="TValue extends string | number, TOption extends { label: string; value: TValue }">`
    *Mekanisme:* Mendeklarasikan parameter generic level SFC. `TValue` dikunci agar hanya berupa tipe primitif yang valid sebagai identifier (`string | number`). `TOption` mewajibkan tipe data minimal memiliki properti `label` dan `value` bertipe `TValue`. Compiler Vue mengubah seluruh inferensi template terhadap komponen ini secara type-safe.
*   **Baris 5–10:** `interface Props { options: TOption[]; ... }` & `withDefaults(defineProps<Props>(), { ... })`
    *Mekanisme:* Mengikat props dengan contract static interface murni. Macro `withDefaults` menyuntikkan fallback value pada fase kompilasi tanpa menciptakan mutasi reaktif buatan runtime.
*   **Baris 18–21:** `interface Emits { (e: 'update:modelValue', value: TValue): void; ... }`
    *Mekanisme:* Mendefinisikan signature payload type-safe untuk implementasi dua-arah `v-model`. Emit `update:modelValue` hanya menerima argumen tipe `TValue`, mencegah lolosnya tipe yang salah ke parent.
*   **Baris 26–29:** `defineSlots<{ default?(props: { option: TOption; isSelected: boolean }): any; ... }>()`
    *Mekanisme:* Melakukan registrasi tipe scoped slots. Ketika developer memanfaatkan template slot default, compiler Vue Language Tools (Volar) mengekstrapolasi bahwa parameter slot tersebut membawa properti `option` bertipe `TOption` secara presisi.
*   **Baris 33–35:** `computed<TOption | undefined>(() => { ... })`
    *Mekanisme:* Pipeline caching memori. Komputasi hanya dijalankan ulang ketika pointer reaktivitas `props.options` atau `props.modelValue` mengalami mutasi referensial.
*   **Baris 48–53:** `defineExpose({ reset, isOpen: computed(...) })`
    *Mekanisme:* Menjalankan isolasi *public API boundary*. Hanya fungsi `reset` dan `isOpen` yang dapat diakses oleh Parent component via template refs. Seluruh internal method (`handleSelect`, dll) disegel secara privat di dalam scope lexical SFC.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Multi-Tenant Enterprise Data Query Orchestrator
**Domain:** Sistem Analytics Core SaaS Perbankan.
**Masalah:**
Tim frontend menghadapi ledakan duplikasi kode pada 12 dashboard analitik yang berbeda. Tim sebelumnya membangun sebuah "God Component" bernama `<MasterTable.vue>` yang menerima lebih dari 65 props (handling pagination, sorting, row expansion, inline editing, column toggling, batch selection, server sync). 

Setiap kali modul analitik baru membutuhkan variasi kolom atau aksi baru:
1. File komponen raksasa (3,500 baris) tersebut dimodifikasi, memicu regresi pengujian (*regression bugs*) pada modul lain.
2. Render payload tree menjadi lambat: Perubahan filter pada satu field memicu re-render keseluruhan 500 VNodes baris data karena isolasi reaktivitas yang bocor.
3. Sulitnya kustomisasi UI per tenant (misal: beberapa tenant menuntut kustom cell rendering berupa sparkline visual, tenant lain hanya teks angka biasa).

**Solusi Arsitektur:**
Merekonstruksi modul tabel analitik menggunakan arsitektur **Compound Component Contract Pattern**:
*   `DataTableProvider`: Mengorkestrasi state transaksi server, sorting, dan multi-row selections.
*   `DataTable`: Komponen layout murni pembungkus semantic markup.
*   `DataColumn`: Komponen deklarator struktur metadata kolom dan slot visual.
*   `DataTableToolbar`: Inversion of control untuk aksi batch dan konfigurasi filter.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Arsitektur Compound Component: Modular, Type-Safe, Production-Ready.

#### 1. Kontrak Komponen & Injection Token (`types.ts`)
```typescript
import type { InjectionKey, Ref, ComputedRef } from 'vue';

export type SortDirection = 'asc' | 'desc' | 'none';

export interface ColumnRegistration<T> {
  id: string;
  header: string;
  sortable: boolean;
  field?: keyof T;
}

export interface DataTableContext<T extends Record<string, any>> {
  items: ComputedRef<T[]>;
  selectedIds: Ref<Set<string | number>>;
  sortColumn: Ref<string | null>;
  sortDirection: Ref<SortDirection>;
  columns: Ref<ColumnRegistration<T>[]>;
  registerColumn: (column: ColumnRegistration<T>) => void;
  unregisterColumn: (id: string) => void;
  toggleSort: (columnId: string) => void;
  toggleSelectRow: (id: string | number) => void;
  toggleSelectAll: () => void;
  isAllSelected: ComputedRef<boolean>;
}

export const DATA_TABLE_KEY: InjectionKey<DataTableContext<any>> = Symbol('DATA_TABLE_CONTEXT');
```

#### 2. Root Provider Orchestrator (`DataTableRoot.vue`)
```html
<script setup lang="ts" generic="T extends { id: string | number }">
import { ref, computed, provide, toRef } from 'vue';
import { DATA_TABLE_KEY, type DataTableContext, type ColumnRegistration, type SortDirection } from './types';

interface Props {
  items: T[];
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: 'selectionChange', selected: (string | number)[]): void;
  (e: 'sortChange', payload: { column: string; direction: SortDirection }): void;
}>();

const columns = ref<ColumnRegistration<T>[]>([]) as Ref<ColumnRegistration<T>[]>;
const selectedIds = ref<Set<string | number>>(new Set());
const sortColumn = ref<string | null>(null);
const sortDirection = ref<SortDirection>('none');

function registerColumn(column: ColumnRegistration<T>): void {
  const exists = columns.value.some(col => col.id === column.id);
  if (!exists) {
    columns.value.push(column);
  }
}

function unregisterColumn(id: string): void {
  columns.value = columns.value.filter(col => col.id !== id);
}

function toggleSort(columnId: string): void {
  if (sortColumn.value !== columnId) {
    sortColumn.value = columnId;
    sortDirection.value = 'asc';
  } else {
    if (sortDirection.value === 'asc') sortDirection.value = 'desc';
    else if (sortDirection.value === 'desc') {
      sortColumn.value = null;
      sortDirection.value = 'none';
    }
  }
  emit('sortChange', { column: columnId, direction: sortDirection.value });
}

function toggleSelectRow(id: string | number): void {
  const updated = new Set(selectedIds.value);
  if (updated.has(id)) {
    updated.delete(id);
  } else {
    updated.add(id);
  }
  selectedIds.value = updated;
  emit('selectionChange', Array.from(updated));
}

const isAllSelected = computed(() => {
  return props.items.length > 0 && selectedIds.value.size === props.items.length;
});

function toggleSelectAll(): void {
  if (isAllSelected.value) {
    selectedIds.value = new Set();
  } else {
    selectedIds.value = new Set(props.items.map(item => item.id));
  }
  emit('selectionChange', Array.from(selectedIds.value));
}

// Context Exposure
provide(DATA_TABLE_KEY, {
  items: computed(() => props.items),
  selectedIds,
  sortColumn,
  sortDirection,
  columns,
  registerColumn,
  unregisterColumn,
  toggleSort,
  toggleSelectRow,
  toggleSelectAll,
  isAllSelected
});
</script>

<template>
  <div class="data-table-root">
    <slot />
  </div>
</template>

<style scoped>
.data-table-root {
  display: flex;
  flex-direction: column;
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}
</style>
```

#### 3. Metadata Transclusion Column Declarator (`DataTableColumn.vue`)
```html
<script setup lang="ts" generic="T extends Record<string, any>">
import { inject, onMounted, onUnmounted } from 'vue';
import { DATA_TABLE_KEY, type DataTableContext } from './types';

interface Props {
  id: string;
  header: string;
  field?: keyof T;
  sortable?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  sortable: false
});

const context = inject<DataTableContext<T>>(DATA_TABLE_KEY);

if (!context) {
  throw new Error('<DataTableColumn> must be rendered within a <DataTableRoot> context.');
}

// Scoped slot contract definition for this column's cell renderer
defineSlots<{
  cell?(props: { row: T; value: unknown }): any;
}>();

onMounted(() => {
  context.registerColumn({
    id: props.id,
    header: props.header,
    field: props.field,
    sortable: props.sortable
  });
});

onUnmounted(() => {
  context.unregisterColumn(props.id);
});
</script>

<template>
  <!-- Renderless declarative node. Markups are managed by DataTableViewport -->
</template>
```

#### 4. Viewport Consumer Render Engine (`DataTableViewport.vue`)
```html
<script setup lang="ts">
import { inject } from 'vue';
import { DATA_TABLE_KEY, type DataTableContext } from './types';

const context = inject<DataTableContext<Record<string, any>>>(DATA_TABLE_KEY);

if (!context) {
  throw new Error('<DataTableViewport> must be rendered within a <DataTableRoot> context.');
}

const {
  items,
  columns,
  selectedIds,
  sortColumn,
  sortDirection,
  toggleSort,
  toggleSelectRow,
  toggleSelectAll,
  isAllSelected
} = context;
</script>

<template>
  <table class="enterprise-table">
    <thead>
      <tr>
        <th class="selection-cell">
          <input
            type="checkbox"
            :checked="isAllSelected"
            @change="toggleSelectAll"
          />
        </th>
        <th
          v-for="col in columns"
          :key="col.id"
          :class="{ 'sortable-header': col.sortable }"
          @click="col.sortable ? toggleSort(col.id) : undefined"
        >
          <div class="th-content">
            {{ col.header }}
            <span v-if="col.sortable && sortColumn === col.id" class="sort-indicator">
              {{ sortDirection === 'asc' ? '▲' : sortDirection === 'desc' ? '▼' : '' }}
            </span>
          </div>
        </th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="item in items"
        :key="item.id"
        :class="{ 'row-selected': selectedIds.has(item.id) }"
      >
        <td class="selection-cell">
          <input
            type="checkbox"
            :checked="selectedIds.has(item.id)"
            @change="toggleSelectRow(item.id)"
          />
        </td>
        <td v-for="col in columns" :key="col.id">
          <!-- Mengakses cell data melalui dynamic property fallback -->
          {{ col.field ? item[col.field] : '-' }}
        </td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
.enterprise-table { width: 100%; border-collapse: collapse; text-align: left; }
.enterprise-table th, .enterprise-table td { padding: 12px 16px; border-bottom: 1px solid #e2e8f0; }
.enterprise-table th { background-color: #f8fafc; font-weight: 600; }
.selection-cell { width: 40px; text-align: center; }
.sortable-header { cursor: pointer; user-select: none; }
.sortable-header:hover { background-color: #f1f5f9; }
.th-content { display: flex; align-items: center; gap: 6px; }
.sort-indicator { font-size: 10px; color: #3b82f6; }
.row-selected { background-color: #eff6ff; }
</style>
```

#### 5. Konsumsi di Parent / Page Application (`App.vue`)
```html
<script setup lang="ts">
import { ref } from 'vue';
import DataTableRoot from './DataTableRoot.vue';
import DataTableColumn from './DataTableColumn.vue';
import DataTableViewport from './DataTableViewport.vue';

interface BankAccount {
  id: string;
  accountNumber: string;
  holderName: string;
  balance: number;
}

const accounts = ref<BankAccount[]>([
  { id: 'acc_01', accountNumber: '109-002-991', holderName: 'PT Teknologi Bangsa', balance: 500000000 },
  { id: 'acc_02', accountNumber: '401-882-112', holderName: 'John Doe', balance: 14500000 },
  { id: 'acc_03', accountNumber: '772-001-334', holderName: 'Jane Smith', balance: 89000000 }
]);

function handleSelection(ids: (string | number)[]): void {
  console.log('Selected IDs:', ids);
}

function handleSort(payload: { column: string; direction: string }): void {
  console.log('Sort triggered:', payload);
}
</script>

<template>
  <main class="container">
    <h2>Daftar Akun Rekening Perusahaan</h2>

    <DataTableRoot :items="accounts" @selectionChange="handleSelection" @sortChange="handleSort">
      <!-- Registrasi Skema Kolom Menggunakan Decoupled Column Entities -->
      <DataTableColumn id="acc_num" header="No. Rekening" field="accountNumber" :sortable="true" />
      <DataTableColumn id="holder" header="Nama Pemilik" field="holderName" :sortable="true" />
      <DataTableColumn id="bal" header="Saldo (IDR)" field="balance" :sortable="false" />

      <!-- Rendering Viewport Engine -->
      <DataTableViewport />
    </DataTableRoot>
  </main>
</template>

<style scoped>
.container { max-width: 900px; margin: 40px auto; font-family: system-ui, sans-serif; }
</style>
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektur | Monolithic Mega-Component | Headless Composables (`useTable`) | Compound Components (`Provider + SubComponents`) |
| :--- | :--- | :--- | :--- |
| **Ekspresifitas Template** | Sangat Rendah (Konfigurasi terpusat via JSON / 50+ props) | Tinggi (Konsumen membangun template HTML sendiri dari awal) | **Sangat Tinggi** (Deklaratif via markup Vue, modular) |
| **Pemisahan Perhatian (SoC)** | Buruk (Logika UI, markup, dan data bercampur dalam 1 berkas) | **Sempurna** (Logika murni JavaScript/TS, bebas dari rendering) | Sangat Baik (Batas tanggung jawab terdistribusi per elemen) |
| **Overhead Runtime Memory** | Rendah (Hanya ada 1 instance VNode komponen) | **Paling Rendah** (Hanya fungsi reaktif, meminimalisir virtual DOM) | Sedang (Terdapat multi-instance komponen VNode anak) |
| **Kurva Pembelajaran (DX)** | Rendah di awal, Menyakitkan di skala besar (*Maintenance Nightmare*) | Menengah (Memerlukan pemahaman wiring state ke elemen native) | Sedang - Menuntut pemahaman Dependency Injection |
| **Refactoring Safety** | Rapuh (Perubahan pada satu baris merusak keseluruhan use-case) | Aman (Unit test terisolasi pada logic composable murni) | **Sangat Aman** (Isolasi komponen via typed boundary interface) |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Reaktivitas Hilang Akibat Destructuring Context (`Destructuring Anti-Pattern`)
*Failure Mode:* Jika komponen anak mengekstrak nilai primitif dari injected context via destructuring langsung:
```typescript
// PITFALL PADA CHILD
const { isAllSelected } = inject(DATA_TABLE_KEY)!; 
// isAllSelected kehilangan status keterikatan reaktif jika bukan diekstrak sebagai Ref / Computed!
```
*Mitigasi:* Pastikan struktur kontrak Interface Injection selalu membungkus tipe mutable dalam bentuk `Ref<T>` atau `ComputedRef<T>`. Saat melakukan destructuring, perlakukan variabel sebagai ref (`isAllSelected.value`) atau gunakan utilitas `toRefs()` / `toRef()`.

### 2. Injection Provider Hilang pada Render Tree Berbeda (`Orphan Components`)
*Failure Mode:* Developer menempatkan `<DataTableColumn>` di luar `<DataTableRoot>`. Tanpa guard asserting, kode akan melempar TypeError: *Cannot read properties of undefined (reading 'registerColumn')* saat runtime produksi.
*Mitigasi:* Selalu buat **Context Guard Consumer**:
```typescript
export function useDataTableContext<T>() {
  const context = inject<DataTableContext<T>>(DATA_TABLE_KEY);
  if (!context) {
    throw new Error('System Boundary Exception: Injected context was