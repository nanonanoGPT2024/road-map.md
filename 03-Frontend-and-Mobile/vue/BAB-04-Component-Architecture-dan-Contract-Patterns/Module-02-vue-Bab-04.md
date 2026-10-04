# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Component Architecture & Contract Patterns)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengonstruksi kontrak komponen (*component contracts*) berskala enterprise menggunakan **Generic Components (`generic="T"`)**, **Discriminated Union Props**, serta **Typed Emits & Slots (`defineSlots`, `defineEmits`)**.
- Menguasai implementasi **Compound Component Pattern** dan **Headless/Renderless Component Pattern** dengan proteksi reaktivitas tingkat rendah (*reactivity boundary preservation*) menggunakan `InjectionKey<T>`.
- Menganalisis cara kerja internal Vue Core dalam kompilasi slot, resolusi Virtual DOM (VNode), serta siklus hidup pelacakan dependensi (*dependency tracking*) pada hierarki komponen bersarang (*nested components*).
- Membangun arsitektur komponen polimorfik (*polymorphic components*) yang aman secara tipe data (*type-safe*) tanpa mengorbankan performa *render* dan alokasi memori heap V8.
- Mengidentifikasi, mengukur, dan memitigasi *performance bottleneck* akibat kebocoran reaktivitas (*reactivity leaks*), *unnecessary re-renders*, dan *slot closure retainment*.

---

## 2. Prerequisite

Untuk menguasai materi ini secara optimal, Anda wajib memahami:
- **TypeScript Tingkat Lanjut**: Generics, Discriminated Unions, Utility Types (`Extract`, `Omit`, `Record`), dan Mapped Types.
- **Vue 3 Composition API Dasar**: `ref`, `reactive`, `computed`, `watchEffect`, dan SFC Lifecycle Hooks (`onMounted`, `onUnmounted`).
- **Konsep Kompilasi Frontend**: Pemahaman dasar tentang Abstract Syntax Tree (AST), perenderan Virtual DOM (VNode), dan tree-shaking mekanik ES Modules.
- **Node.js & Tooling**: Node.js 18+, Vite 5+, Vue 3.4+ (`defineSlots`, Generic SFCs stabil).

---

## 3. Concept & Internal Architecture

Arsitektur komponen modern menuntut pemisahan tegas antara kontrak input-output (API komponen), logika state internal, dan representasi visual (DOM). Untuk membangun abstraksi yang tangguh, kita harus menyelami dapur pacu *runtime-core* Vue 3.

```
                    ┌───────────────────────────────────────────────┐
                    │            Component Contract (API)           │
                    │  - Generic Types: <script setup generic="T"> │
                    │  - Discriminated Union Props                  │
                    │  - Typed Emits & Typed Slots (defineSlots)    │
                    └───────────────────────┬───────────────────────┘
                                            │
                                            ▼
                    ┌───────────────────────────────────────────────┐
                    │            Dependency Injection Bus           │
                    │  - Provide / Inject (InjectionKey<T>)         │
                    │  - Context Propagation Engine                 │
                    │  - ShallowReadonly State Boundary             │
                    └───────────────────────┬───────────────────────┘
                                            │
                        ┌───────────────────┴───────────────────┐
                        ▼                                       ▼
        ┌───────────────────────────────┐       ┌───────────────────────────────┐
        │       Compiler Layer          │       │        Runtime Layer          │
        │ - Slot Function Generation    │       │ - Effect Scope Boundaries     │
        │ - Static Hoisting             │       │ - VNode Tree Reconciliation   │
        │ - Patch Flag Assignment       │       │ - Reactive Trigger & Track    │
        └───────────────────────────────┘       └───────────────────────────────┘
```

### 3.1. Anatomi Kontrak Komponen & Generic SFC
Pada Vue 3.3+, SFC mendukung sintaks `generic="T"`. Di balik layar, compiler `@vue/compiler-sfc` mentransformasikan deklarasi generic ini ke dalam fungsi pembungkus ekspor default modul JavaScript:

```typescript
// Konseptual transformasi compiler
export default {
  setup<T extends Record<string, any>>(props: Props<T>, { slots, emit }: SetupContext) {
    // Runtime execution scope dengan bound generic type
  }
}
```

Ketika generic dipadukan dengan **Discriminated Unions**, kompilator TypeScript dapat memvalidasi properti yang bergantung satu sama lain secara kondisional. Sebagai contoh, jika prop `mode="server"`, maka prop `fetcher` wajib ada, sedangkan jika `mode="client"`, prop `dataset` yang wajib disediakan.

### 3.2. Kompilasi Slot & Runtime Scoped Slots
Banyak pengembang menganggap slot hanyalah *placeholder* DOM. Secara internal, slot direpresentasikan sebagai **fungsi JavaScript murni (*slot functions*)**.
- Slot biasa (*non-scoped*) dikompilasi menjadi fungsi statis yang dievaluasi saat *parent component* melakukan render.
- Scoped slot dikompilasi menjadi fungsi dinamis: `(slotProps) => VNodeChildren`.
- **Mekanisme Reaktivitas Slot**: Saat parent me-render child yang memiliki slot, child menerima *slot function* di properti `$slots`. Eksekusi fungsi tersebut menghasilkan Virtual DOM node di dalam konteks render child. Jika dependensi reaktif yang dibaca berada di dalam slot function, dependensi tersebut akan dilacak oleh *render effect* milik komponen yang mengeksekusi fungsi tersebut (biasanya child, kecuali compiler mengoptimalkannya via *slot flags*).

### 3.3. Provide/Inject Internals & Prototype Chain Inheritance
Sistem `provide` dan `inject` pada Vue 3 bekerja menggunakan manipulasi *prototype chain* dari objek instance komponen:
1. Setiap komponen memiliki objek instance internal `ComponentInternalInstance`.
2. Properti `instance.provides` pada root instance diinisialisasi sebagai objek kosong atau mewarisi dari `app._context.provides`.
3. Ketika sebuah child component memanggil `provide(key, value)`:
   - Jika `instance.provides` masih menunjuk langsung ke *parent provides*, Vue membuat objek baru dengan prototipe objek parent:
     ```javascript
     instance.provides = Object.create(parent.provides);
     ```
   - Nilai baru kemudian disimpan pada `instance.provides[key]`.
4. Ketika child level berapa pun memanggil `inject(key)`:
   - Vue mencari `key` langsung pada `currentInstance.parent.provides[key]`. Karena inheritance prototipe JavaScript (`Object.create`), pencarian berjalan ke atas sepanjang pohon hierarki (*lookup chain*) dengan kompleksitas waktu $O(1)$ hingga $O(d)$ (di mana $d$ adalah kedalaman nesting provide baru), tanpa traversal manual yang lambat.

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal di Skala Enterprise?
Pada aplikasi monolitik frontend skala besar dengan puluhan pengembang:
1. **Prop-Drilling & "Mega-Components"**: Komponen sering kali menerima 40+ props konfigurasi opsional (god-components), mengakibatkan tingginya *cyclomatic complexity* dan fragmentasi logika render.
2. **Loss of Type Safety**: Menggunakan `any` atau `Object as PropType<any>` menghilangkan kemampuan refaktor aman (*safe refactoring*) dan IDE auto-completion.
3. **Reactivity Leaking & State Mutation Anti-patterns**: Menyuntikkan objek `reactive` mentah melalui provide/inject memungkinkan child component mengubah state parent secara implisit tanpa jejak (*side-effect mutation*), menyulitkan debugging dan penelusuran regresi data.

### Apa Solusinya?
- **Arsitektur Berbasis Kontrak Kuat (*Strict Contract-Driven Architecture*)**: Memanfaatkan Generic Components, Discriminated Unions, `defineSlots`, dan `InjectionKey` bertipe ketat.
- **Compound Components Pattern**: Memecah komponen raksasa menjadi sub-komponen terisolasi yang saling berkomunikasi secara implisit melalui context aman (*encapsulated dependency injection*).
- **Headless & Renderless Components**: Memisahkan 100% *behavioral logic* & *state machine* dari markup DOM visual melalui scoped slots dan composables, memudahkan penggantian tampilan (misalnya migrasi design system dari Tailwind ke CSS Modules) tanpa menulis ulang logika bisnis.

---

## 5. How (Workflow Detail)

Untuk menerapkan arsitektur kontrak enterprise, ikuti alur kerja sistematis berikut:

```
┌────────────────────────────────────────────────────────┐
│ 1. Define Strict Domain Contracts & Tokens             │
│    - Deklarasikan TypeScript types & InjectionKey<T>   │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ 2. Construct Headless / Context Controller Layer       │
│    - Inisialisasi state reaktif parent                 │
│    - Batasi mutasi: export ReadonlyState & TypedAction │
│    - Provide context via Typed InjectionKey           │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ 3. Build Compound Child Sub-Components                 │
│    - Inject context dengan fail-fast assertion guard   │
│    - Delegasikan rendering via Scoped / Typed Slots    │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ 4. Expose Public Generic Contract Interface            │
│    - Tetapkan generic types pada Root Container SFC    │
│    - Definisikan Typed Emits dan Typed Slots           │
└────────────────────────────────────────────────────────┘
```

1. **Definisi Type & Context Token**: Definisikan semua interface payload, event, dan token unik menggunakan `Symbol() as InjectionKey<T>` dalam modul khusus kontrak (`*.types.ts`).
2. **Penyusunan Parent Provider Component**: Buat root component yang mengelola state. Jangan mengekspos `ref` mutable langsung jika ingin mencegah *accidental mutation*. Ekspos `readonly(state)` beserta fungsi aksi mutator (*dispatchers*).
3. **Penyusunan Child Compound Component**: Setiap child wajib mengonsumsi context melalui custom injection function yang memvalidasi apakah child berada di dalam cakupan (*scope*) parent. Jika tidak ditemukan, lempar pesan *descriptive runtime error*.
4. **Implementasi Typed Slots**: Gunakan makro `defineSlots<{ default(props: T): any }>()` untuk mendefinisikan API visual yang fleksibel namun terlindungi oleh static analyzer TypeScript.

---

## 6. Analogy & Diagram ASCII

### Analogi Real-World: Kontrak Pembangunan Gedung (Arsitek vs Subkontraktor)
Bayangkan pembangunan gedung pencakar langit:
- **Arsitek (Root Container Component)** menentukan cetak biru (*blueprint*) dan menyediakan utilitas dasar: air, listrik, dan jalur lift (**Context/Provide**). Arsitek melarang subkontraktor memodifikasi gardu pusat sembarangan, tetapi memberikan panel kontrol khusus (**Action Dispatchers**).
- **Subkontraktor Spesialis (Compound Child Components)** seperti ahli HVAC, ahli interior, dan teknisi pipa air mengonsumsi utilitas dari lantai tempat mereka bekerja (**Inject**) dan memasang fitur spesifik tanpa perlu tahu arsitektur internal gardu utama.
- **Ruang Kustom (Slots)**: Klien pemilik gedung dapat mengisi ruangan interior sesuai selera mereka, selama sesuai dengan dimensi dan spesifikasi struktural yang digariskan (**Typed Slot Props**).

```
                        PARENT COMPOUND CONTAINER
                 ┌──────────────────────────────────────┐
                 │ State: selectedId, items[], loading  │
                 │ Actions: selectItem(), reset()       │
                 │ Symbol(DataTableContextKey)          │
                 └──────────────────┬───────────────────┘
                                    │ Provide (Context)
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
│ Child: Search   │        │ Child: Table    │        │ Child: Pager    │
│ - inject(Key)   │        │ - inject(Key)   │        │ - inject(Key)   │
│ - triggers      │        │ - reads state   │        │ - reads state   │
│   search query  │        │ - passes scoped │        │ - dispatches    │
│                 │        │   slots to host │        │   page changes  │
└─────────────────┘        └────────┬────────┘        └─────────────────┘
                                    │
                                    ▼
                      ┌───────────────────────────┐
                      │ Typed Scoped Slot (Row)   │
                      │ Consumer renders custom   │
                      │ template with item data   │
                      └───────────────────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Typed Custom Modifiers pada `v-model`
Berikut adalah implementasi custom modifiers pada `v-model` dengan pengetikan ketat (*strict typing*) menggunakan Vue 3.4+ `defineModel`.

```vue
<!-- components/NumericInput.vue -->
<script setup lang="ts">
// Mendefinisikan v-model dengan modifier kustom bertipe spesifik
const [modelValue, modelModifiers] = defineModel<number, 'capitalize' | 'positiveOnly'>({
  default: 0,
  set(value) {
    if (modelModifiers.positiveOnly && value < 0) {
      return 0;
    }
    return value;
  }
});
</script>

<template>
  <div class="input-wrapper">
    <input
      type="number"
      :value="modelValue"
      @input="e => modelValue = Number((e.target as HTMLInputElement).value)"
      class="border px-3 py-2 rounded"
    />
    <span v-if="modelModifiers.positiveOnly" class="text-xs text-gray-500">
      Mode: Positive Numbers Only
    </span>
  </div>
</template>
```

---

### 7.2. Practical Example: Production Compound & Generic Data Grid

Mari implementasikan sistem Compound Data Table yang sepenuhnya type-safe, generic, menggunakan dynamic slots, dan terisolasi dari *uncontrolled mutations*.

#### Bagian 1: Definisi Kontrak & Tipe Data
```typescript
// components/data-table/data-table.types.ts
import type { InjectionKey, Ref, ComputedRef } from 'vue';

export interface ColumnDefinition<T> {
  key: keyof T | string;
  header: string;
  sortable?: boolean;
  width?: string;
}

export type SortOrder = 'asc' | 'desc' | null;

export interface DataTableContext<T> {
  data: ComputedRef<T[]>;
  columns: Ref<ColumnDefinition<T>[]>;
  selectedRows: Ref<Set<string | number>>;
  sortKey: Ref<string | null>;
  sortOrder: Ref<SortOrder>;
  toggleSort: (key: string) => void;
  toggleRowSelection: (id: string | number) => void;
  registerColumn: (column: ColumnDefinition<T>) => void;
  unregisterColumn: (key: string) => void;
}

// Injection Key Factory dengan perlindungan generic casting
export const DataTableContextKey = Symbol('DataTableContextKey') as InjectionKey<DataTableContext<any>>;
```

#### Bagian 2: Parent Component (Container)
```vue
<!-- components/data-table/DataTableRoot.vue -->
<script setup lang="ts" generic="T extends { id: string | number }">
import { ref, computed, provide, readonly, toRef } from 'vue';
import { DataTableContextKey, type DataTableContext, type ColumnDefinition, type SortOrder } from './data-table.types';

interface Props {
  items: T[];
  trackBy?: keyof T;
}

const props = withDefaults(defineProps<Props>(), {
  trackBy: 'id' as unknown as keyof T
});

const emit = defineEmits<{
  (e: 'rowClick', payload: T): void;
  (e: 'selectionChange', selectedIds: (string | number)[]): void;
}>();

// Slots Contract: Memungkinkan kustomisasi kolom atau toolbar
defineSlots<{
  default(): any;
  toolbar(props: { totalCount: number; selectedCount: number }): any;
  empty(): any;
}>();

const columns = ref<ColumnDefinition<T>[]>([]) as Ref<ColumnDefinition<T>[]>;
const selectedRows = ref<Set<string | number>>(new Set());
const sortKey = ref<string | null>(null);
const sortOrder = ref<SortOrder>(null);

const toggleSort = (key: string) => {
  if (sortKey.value !== key) {
    sortKey.value = key;
    sortOrder.value = 'asc';
  } else if (sortOrder.value === 'asc') {
    sortOrder.value = 'desc';
  } else {
    sortKey.value = null;
    sortOrder.value = null;
  }
};

const toggleRowSelection = (id: string | number) => {
  const nextSet = new Set(selectedRows.value);
  if (nextSet.has(id)) {
    nextSet.delete(id);
  } else {
    nextSet.add(id);
  }
  selectedRows.value = nextSet;
  emit('selectionChange', Array.from(nextSet));
};

const registerColumn = (column: ColumnDefinition<T>) => {
  const index = columns.value.findIndex(c => c.key === column.key);
  if (index === -1) {
    columns.value.push(column);
  } else {
    columns.value[index] = column;
  }
};

const unregisterColumn = (key: string) => {
  columns.value = columns.value.filter(c => c.key !== key);
};

const sortedData = computed(() => {
  if (!sortKey.value || !sortOrder.value) return props.items;
  
  const key = sortKey.value as keyof T;
  const orderMultiplier = sortOrder.value === 'asc' ? 1 : -1;

  return [...props.items].sort((a, b) => {
    const valA = a[key];
    const valB = b[key];
    if (valA === valB) return 0;
    return (valA > valB ? 1 : -1) * orderMultiplier;
  });
});

// Provide context yang aman ke seluruh subkomponen
const context: DataTableContext<T> = {
  data: sortedData,
  columns,
  selectedRows,
  sortKey,
  sortOrder,
  toggleSort,
  toggleRowSelection,
  registerColumn,
  unregisterColumn
};

provide(DataTableContextKey, context);
</script>

<template>
  <div class="data-table-container border rounded-lg overflow-hidden bg-white shadow-sm">
    <div v-if="$slots.toolbar" class="p-4 border-b bg-gray-50">
      <slot name="toolbar" :total-count="items.length" :selected-count="selectedRows.size" />
    </div>

    <!-- Hidden default slot untuk render deklaratif subkomponen registrator -->
    <div style="display: none;">
      <slot />
    </div>

    <div class="overflow-x-auto">
      <table class="w-full text-left text-sm border-collapse">
        <thead class="bg-gray-100 uppercase text-xs font-semibold text-gray-700">
          <tr>
            <th class="p-3 w-10">
              <span class="sr-only">Selection</span>
            </th>
            <th
              v-for="col in columns"
              :key="String(col.key)"
              @click="col.sortable ? toggleSort(String(col.key)) : undefined"
              :class="['p-3 select-none', col.sortable ? 'cursor-pointer hover:bg-gray-200' : '']"
              :style="{ width: col.width }"
            >
              <div class="flex items-center gap-1">
                <span>{{ col.header }}</span>
                <span v-if="sortKey === col.key" class="text-xs">
                  {{ sortOrder === 'asc' ? '▲' : sortOrder === 'desc' ? '▼' : '' }}
                </span>
              </div>
            </th>
          </tr>
        </thead>

        <tbody class="divide-y divide-gray-200">
          <tr v-if="sortedData.length === 0">
            <td :colspan="columns.length + 1" class="p-6 text-center text-gray-500">
              <slot name="empty">Data tidak ditemukan.</slot>
            </td>
          </tr>
          <tr
            v-for="row in sortedData"
            :key="String(row[props.trackBy])"
            @click="emit('rowClick', row)"
            :class="[
              'hover:bg-blue-50/50 transition-colors',
              selectedRows.has(row[props.trackBy]) ? 'bg-blue-50' : ''
            ]"
          >
            <td class="p-3">
              <input
                type="checkbox"
                :checked="selectedRows.has(row[props.trackBy])"
                @click.stop="toggleRowSelection(row[props.trackBy])"
              />
            </td>
            <td
              v-for="col in columns"
              :key="String(col.key)"
              class="p-3 text-gray-800"
            >
              {{ (row as any)[col.key] }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
```

#### Bagian 3: Compound Child Component (Column Declarator)
```vue
<!-- components/data-table/DataTableColumn.vue -->
<script setup lang="ts" generic="T">
import { inject, onMounted, onUnmounted, watch } from 'vue';
import { DataTableContextKey, type DataTableContext, type ColumnDefinition } from './data-table.types';

const props = defineProps<{
  prop: keyof T | string;
  header: string;
  sortable?: boolean;
  width?: string;
}>();

// Assertion Guard: Memastikan sub-komponen hanya digunakan di dalam root yang valid
const context = inject(DataTableContextKey, null) as DataTableContext<T> | null;

if (!context) {
  throw new Error('[DataTableColumn]: Komponen ini wajib dibungkus di dalam <DataTableRoot />');
}

const columnConfig: ColumnDefinition<T> = {
  key: props.prop,
  header: props.header,
  sortable: props.sortable,
  width: props.width
};

onMounted(() => {
  context.registerColumn(columnConfig);
});

onUnmounted(() => {
  context.unregisterColumn(String(props.prop));
});

// Respon terhadap perubahan konfigurasi props dinamis
watch(
  () => [props.header, props.sortable, props.width],
  () => {
    context.registerColumn({
      key: props.prop,
      header: props.header,
      sortable: props.sortable,
      width: props.width
    });
  }
);
</script>

<template>
  <!-- Komponen headless/declarative: tidak menghasilkan representasi visual fisik di tree ini -->
</template>
```

#### Bagian 4: Penggunaan di Tingkat Aplikasi
```vue
<!-- views/OrderListView.vue -->
<script setup lang="ts">
import { ref } from 'vue';
import DataTableRoot from '@/components/data-table/DataTableRoot.vue';
import DataTableColumn from '@/components/data-table/DataTableColumn.vue';

interface Order {
  id: number;
  orderNumber: string;
  customer: string;
  total: number;
  status: 'PENDING' | 'COMPLETED' | 'CANCELLED';
}

const orders = ref<Order[]>([
  { id: 1, orderNumber: 'ORD-001', customer: 'Budi Santoso', total: 550000, status: 'COMPLETED' },
  { id: 2, orderNumber: 'ORD-002', customer: 'Siti Aminah', total: 1200000, status: 'PENDING' },
  { id: 3, orderNumber: 'ORD-003', customer: 'Agus Pratama', total: 250000, status: 'CANCELLED' }
]);

const handleRowClick = (order: Order) => {
  console.log('Navigating to detail:', order.orderNumber);
};

const handleSelectionChange = (ids: (string | number)[]) => {
  console.log('Selected ids for batch processing:', ids);
};
</script>

<template>
  <div class="p-8">
    <h1 class="text-2xl font-bold mb-4">Enterprise Order Dashboard</h1>

    <DataTableRoot
      :items="orders"
      track-by="id"
      @row-click="handleRowClick"
      @selection-change="handleSelectionChange"
    >
      <template #toolbar="{ totalCount, selectedCount }">
        <div class="flex justify-between items-center">
          <span class="text-sm text-gray-600">Total Transaksi: {{ totalCount }}</span>
          <span v-if="selectedCount > 0" class="text-sm font-semibold text-blue-600">
            {{ selectedCount }} item terpilih
          </span>
        </div>
      </template>

      <!-- Definisi Kolom Deklaratif via Compound Components -->
      <DataTableColumn<Order> prop="orderNumber" header="No. Invoice" sortable width="180px" />
      <DataTableColumn<Order> prop="customer" header="Pelanggan" sortable />
      <DataTableColumn<Order> prop="total" header="Total Nilai (IDR)" sortable />
      <DataTableColumn<Order> prop="status" header="Status Pemesanan" />

      <template #empty>
        <div class="py-12">
          <p class="text-gray-400">Tidak ada riwayat transaksi yang cocok dengan kriteria.</p>
        </div>
      </template>
    </DataTableRoot>
  </div>
</template>
```

---

## 8. Real World Case Study: High-Concurrency Dynamic Form Engine

### Latar Belakang Masalah
Sebuah platform perbankan digital skala enterprise membutuhkan sistem pengajuan pinjaman dinamis (*Loan Origination System*). Spesifikasi sistem meliputi:
1. Skema formulir berubah secara *runtime* tergantung negara, profil risiko nasabah, dan regulasi kepatuhan (*compliance engine*).
2. Terdapat lebih dari 120 input dinamis dalam satu form hierarkis (informasi pribadi, pekerjaan, aset, dokumen pendukung).
3. **Problem**: Implementasi awal menggunakan satu komponen monolitis raksasa berbasis `v-for` dan event bus. Ketika nasabah mengetik pada satu text input, seluruh form (120+ field) melakukan *re-render* yang menyebabkan *input latency* hingga 85ms pada perangkat *low-end*, serta hilangnya fokus input kursor secara intermiten (*focus dropping*).

### Arsitektur Solusi
Tim arsitek frontend merekonstruksi sistem dengan:
1. **Compound Form Context Engine** dengan isolasi render per-field: State field disimpan menggunakan `shallowRef` dan Map terindeks.
2. Form field didaftarkan secara *headless*. Hanya komponen input yang nilainya berubah atau mengalami error validasi yang melakukan komputasi ulang Virtual DOM.
3. Menggunakan **Strict Contract Discriminated Unions** untuk menangani variasi field (Text, Select, Currency, File Upload).

```typescript
// types/form-engine.types.ts
export type FieldType = 'text' | 'number' | 'currency' | 'select';

interface BaseFieldConfig<TValue> {
  id: string;
  name: string;
  label: string;
  required?: boolean;
  defaultValue: TValue;
  validationRules?: Array<(val: TValue) => string | null>;
}

export interface TextFieldConfig extends BaseFieldConfig<string> {
  type: 'text';
  placeholder?: string;
  maxLength?: number;
}

export interface CurrencyFieldConfig extends BaseFieldConfig<number> {
  type: 'currency';
  currencyCode: 'IDR' | 'USD' | 'EUR';
  min?: number;
  max?: number;
}

export interface SelectFieldConfig extends BaseFieldConfig<string> {
  type: 'select';
  options: Array<{ label: string; value: string }>;
}

export type DynamicFieldSchema = TextFieldConfig | CurrencyFieldConfig | SelectFieldConfig;
```

### Hasil Optimasi
- **Rendering Performance**: Input latency berkurang dari 85ms menjadi < 4ms (mencapai target *120fps smooth input budget*).
- **Type Safety**: Menghilangkan 100% bug *undefined access* pada runtime formulir dinamis berkat Discriminated Union guard pada rendering logic.
- **Maintainability**: Penambahan tipe input baru (misal: Biometric Verification Field) hanya membutuhkan satu subkomponen baru tanpa menyentuh kode engine inti.

---

## 9. Trade-offs

| Parameter | Compound Component Pattern | Mega Monolithic Component (Props-Heavy) | Composables / Headless Pure Function |
| :--- | :--- | :--- | :--- |
| **Performance (Render Cycle)** | **Optimal**: Subkomponen merender secara lokal melalui *dependency isolation*. | **Buruk**: Perubahan satu prop memicu re-evaluation luas pada keseluruhan template. | **Tinggi**: Tidak memiliki overhead VNode tree komponen tambahan. |
| **Cognitive Complexity & DX** | **Menengah-Tinggi**: Pola deklaratif sangat bersih, namun memerlukan pemahaman provide/inject dan lifecycle. | **Rendah pada awal, Sangat Buruk pada skala besar**: Mudah dimulai, namun kode menjadi ratusan baris props berantakan (*prop soup*). | **Menengah**: Membutuhkan pengembang untuk menghubungkan markup DOM manual dengan logic bindings. |
| **Bundle Footprint** | Sedikit lebih besar karena registrasi beberapa SFC / class instance. | Sangat padat (*monolithic*), sulit di-tree-shake secara individual. | Paling kecil (*minimal*), tree-shaking berjalan secara sempurna hingga ke fungsi terkecil. |
| **Flexibility Layout** | **Sangat Fleksibel**: Pengguna bebas menyusun markup, layout kolom, grid, dan slot wrapper. | **Kaku**: Layout dikunci di dalam template monolitik parent. | **Maksimal**: Pengembang memiliki kebebasan total terhadap 100% markup HTML/CSS. |
| **Cost of Maintenance** | Rendah: Kontrak antar-komponen dijaga ketat oleh TypeScript Compiler. | Tinggi: Modifikasi satu fitur berisiko merusak fungsionalitas lain (*high coupling*). | Rendah: Logika terpisah dari representasi visual. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Unintentional Reactivity Unwrapping pada Inject
**Kesalahan**:
```typescript
// Parent
const activeStep = ref(1);
provide('stepContext', activeStep.value); // BUG: Mengirimkan primitive number, BUKAN Ref!

// Child
const currentStep = inject('stepContext'); // Bernilai static 1, tidak pernah update!
```
**Solusi**:
Selalu kirimkan objek `Ref`, atau bungkus dalam `readonly(ref)` jika child tidak boleh memutasi langsung:
```typescript
provide(StepContextKey, readonly(activeStep));
```

### 10.2. Slot Closure Memory Leak
**Masalah**: Ketika slot function mengekspos objek besar dari setup scope child, dan parent menyimpan referensi fungsi slot tersebut pada variabel global atau event listener berumur panjang.
```vue
<!-- Child -->
<slot :heavy-context="largeDataSet" />
```
V8 Engine akan menahan `largeDataSet` di dalam memori heap selama *closure* dari slot function masih dirujuk.
**Solusi**:
Kirimkan hanya data mutlak yang dibutuhkan oleh konsumen slot (*least privilege data exposure*), atau gunakan shallow references.

### 10.3. Broken Generic Inference pada Dynamic Component (`<component :is="...">`)
**Masalah**: TypeScript tidak dapat menyimpulkan kontrak generic dari komponen polimorfik yang dirender secara dinamis melalui atribut `:is`.
```vue
<component :is="resolvedComponent" :data="genericData" /> <!-- Type check hilang -->
```
**Solusi**:
Hindari penggunaan string atau runtime polymorphic rendering jika kontrak komponen bersifat generik. Gunakan conditional rendering terarah:
```vue
<TableTypeA v-if="mode === 'A'" :data="dataA" />
<TableTypeB v-else :data="dataB" />
```
Atau manfaatkan functional component bertipe eksplisit via JSX/TSX (`defineComponent`).

---

## 11. Best Practices (Production Checklist)

- [ ] **Contract Centralization**: Simpan semua antarmuka types, discriminated unions, dan `InjectionKey` di dalam berkas terisolasi `.types.ts`.
- [ ] **Explicit Injection Guards**: Jangan pernah menggunakan `inject(KEY) as ContextType` secara buta. Selalu validasi nullability context menggunakan assertion guard dan berikan runtime error informatif jika context hilang.
- [ ] **State Immutability Boundary**: Ekspos state dari provide menggunakan `readonly()` untuk mencegah mutasi liar dari child component. Hanya izinkan perubahan state melalui fungsi mutator / aksi yang diekspos secara eksplisit.
- [ ] **Memory-Clean Compound Registration**: Selalu batalkan pendaftaran child component dari parent di dalam hook `onUnmounted` untuk mencegah *zombie child memory retention*.
- [ ] **Strict Typed Slots**: Deklarasikan seluruh signature scoped slots menggunakan `defineSlots<{ [key: string]: (props: SpecificProps) => any }>()` untuk mencegah bug runtime template.
- [ ] **Zero Any Policy**: Dilarang menggunakan tipe data `any` dalam props, emits, slots, atau injection keys. Manfaatkan generic constraints (`<T extends Record<string, unknown>>`).

---

## 12. Hands-on Practice

Buka terminal proyek Anda dan lakukan langkah demi langkah berikut di dalam folder: `hands-on/m02/`.

### Langkah 1: Inisialisasi Environment
```bash
mkdir -p hands-on/m02/src/components/tabs
cd hands-on/m02
npm init -y
npm install vue@latest
npm install -D typescript vite @vitejs/plugin-vue vue-tsc
```

### Langkah 2: Buat Token & Kontrak Types
Buat berkas `src/components/tabs/tabs.types.ts`:
```typescript
import type { InjectionKey, Ref } from 'vue';

export interface TabItem {
  id: string;
  label: string;
  disabled?: boolean;
}

export interface TabsContext {
  activeTab: Ref<string>;
  tabs: Ref<TabItem[]>;
  selectTab: (id: string) => void;
  registerTab: (tab: TabItem) => void;
  unregisterTab: (id: string) => void;
}

export const TabsContextKey: InjectionKey<TabsContext> = Symbol('TabsContextKey');
```

### Langkah 3: Bangun TabsRoot Container
Buat berkas `src/components/tabs/TabsRoot.vue`:
```vue
<script setup lang="ts">
import { ref, provide, readonly } from 'vue';
import { TabsContextKey, type TabsContext, type TabItem } from './tabs.types';

const props = defineProps<{
  defaultTab?: string;
}>();

const emit = defineEmits<{
  (e: 'change', tabId: string): void;
}>();

const activeTab = ref<string>(props.defaultTab || '');
const tabs = ref<TabItem[]>([]);

const selectTab = (id: string) => {
  const target = tabs.value.find(t => t.id === id);
  if (target && !target.disabled) {
    activeTab.value = id;
    emit('change', id);
  }
};

const registerTab = (tab: TabItem) => {
  if (!tabs.value.some(t => t.id === tab.id)) {
    tabs.value.push(tab);
    if (!activeTab.value) {
      activeTab.value = tab.id;
    }
  }
};

const unregisterTab = (id: string) => {
  tabs.value = tabs.value.filter(t => t.id !== id);
  if (activeTab.value === id && tabs.value.length > 0) {
    activeTab.value = tabs.value[0].id;
  }
};

provide(TabsContextKey, {
  activeTab: readonly(activeTab) as any,
  tabs: readonly(tabs) as any,
  selectTab,
  registerTab,
  unregisterTab
});
</script>

<template>
  <div class="tabs-container border rounded">
    <div class="flex border-b bg-gray-50">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :disabled="tab.disabled"
        @click="selectTab(tab.id)"
        :class="[
          'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
          activeTab === tab.id
            ? 'border-blue-600 text-blue-600 font-bold bg-white'
            : 'border-transparent text-gray-500 hover:text-gray-700',
          tab.disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
        ]"
      >
        {{ tab.label }}
      </button>
    </div>
    <div class="p-4">
      <slot />
    </div>
  </div>
</template>
```

### Langkah 4: Bangun TabPanel Child Component
Buat berkas `src/components/tabs/TabPanel.vue`:
```vue
<script setup lang="ts">
import { inject, onMounted, onUnmounted, computed } from 'vue';
import { TabsContextKey } from './tabs.types';

const props = defineProps<{
  id: string;
  label: string;
  disabled?: boolean;
}>();

const context = inject(TabsContextKey, null);

if (!context) {
  throw new Error('[TabPanel]: Wajib digunakan di dalam komponen <TabsRoot>');
}

onMounted(() => {
  context.registerTab({
    id: props.id,
    label: props.label,
    disabled: props.disabled
  });
});

onUnmounted(() => {
  context.unregisterTab(props.id);
});

const isSelected = computed(() => context.activeTab.value === props.id);
</script>

<template>
  <div v-show="isSelected" role="tabpanel" class="tab-content-panel">
    <slot />
  </div>
</template>
```

### Langkah 5: Uji Type-Check
Jalankan validasi tipe:
```bash
npx vue-tsc --noEmit
```
Pastikan kompilasi berjalan tanpa ada satu pun error TypeScript.

---

## 13. Exercise

### Level Easy
Ubah implementasi `NumericInput.vue` pada Section 7.1 untuk menambahkan modifier kustom baru bernama `roundToTwoDecimals`. Pastikan modifier tersebut membulatkan nilai input menjadi dua angka desimal di belakang koma ketika nilai berubah.

### Level Medium
Tambahkan fungsionalitas **Pagination Controller** pada Compound Component Data Table di Section 7.2:
1. Buat sub-komponen `<DataTablePagination :page-size="10" />`.
2. Pastikan sub-komponen ini menggunakan `inject(DataTableContextKey)` dan memotong data (`slice`) yang dirender pada `tbody` parent tanpa merusak sorting data.

### Level Hard
Buat implementasi **Polymorphic Button Component** (`AppButton.vue`) menggunakan `script setup` dan render functions (`h()`) atau standard SFC:
1. Menerima prop `:as` (default `'button'`, bisa diubah menjadi `'a'`, `'router-link'`, atau custom component).
2. Props harus memiliki pengetikan ketat secara dinamis: Jika `:as="'a'"`, prop `href` dan `target` menjadi valid. Jika `:as="'button'"`, prop `type` (`'button' | 'submit' | 'reset'`) menjadi valid dan `href` menjadi compile error.

---

## 14. Challenge

### Skenario Kasus Kompleks: "Enterprise Dynamic Rule & Permission Matrix"

**Konteks**:
Perusahaan SaaS Anda memiliki panel konfigurasi perizinan role-based yang sangat dinamis. Diperlukan komponen `<PermissionMatrixRoot />` beserta subkomponen compound-nya.

**Spesifikasi Tantangan**:
1. **Generic Constraints**: Matriks harus generic terhadap tipe `UserRole` dan tipe `ActionScope`.
2. **Context Integrity & Batch Mutator**:
   - Komponen harus menyediakan sistem *optimistic state update*.
   - Jika pengguna mencentang perizinan, child mengirim event mutasi ke context. Context mengumpulkan mutasi dalam antrean (buffer debounce 300ms) sebelum memicu event emit `@batch-save`.
   - Jika terjadi network error pada level parent, parent dapat memanggil aksi `rollback()` yang diekspos melalui ref imperatif (`defineExpose`), dan seluruh state di semua child components harus otomatis sinkron kembali ke state stabil terakhir.
3. **Headless Scoped Slots**:
   - Sub-komponen `<PermissionItem />` harus mendukung mode renderless/headless total: konsumen bebas mengganti checkbox standar dengan custom toggle switch Tailwind melalui *scoped slot props* `{ isChecked: boolean, toggle: () => void, isPending: boolean }`.
4. **Zero Any Violation**: Seluruh kontrak wajib lolos `vue-tsc --strict` tanpa ada `any`, tanpa `@ts-ignore`, dan tanpa bypass type cast manual (`as unknown as ...`).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic
1. Apa keuntungan utama menggunakan `generic="T"` pada SFC Vue 3 dibanding mendefinisikan prop dengan `PropType<T>` biasa?
2. Bagaimana cara mengamankan state yang dibagikan melalui `provide` agar tidak dapat dimutasi secara langsung oleh komponen pemanggil `inject`?
3. Apa perbedaan cara kerja kompilasi template antara slot biasa (*default slot*) dan *scoped slot*?
4. Mengapa kita wajib menggunakan objek `Symbol` sebagai `InjectionKey` alih-alih menggunakan tipe data `string`?
5. Makro apa yang digunakan pada Vue 3.4+ untuk mendeklarasikan kontrak tipe data dari slots yang diterima oleh komponen?

### 15.2. Pertanyaan Intermediate
6. Mengapa manipulasi array pada state yang diprovide oleh parent terkadang tidak memicu reaktivitas pada subkomponen jika menggunakan `shallowRef`?
7. Jelaskan apa yang terjadi pada *prototype chain* dari `instance.provides` ketika sebuah child component menyediakan `provide()` baru dengan kunci yang sama dengan parent-nya!
8. Apa yang dimaksud dengan *Discriminated Union Props* dan pada skenario arsitektur komponen seperti apa teknik ini mutlak dibutuhkan?
9. Bagaimana cara menangani kondisi di mana sebuah subkomponen dipasang di luar batas (*boundary*) parent provider yang semestinya tanpa menyebabkan aplikasi *crash* secara hening?
10. Mengapa mengekspos slot props berupa objek reaktif berukuran besar dapat menyebabkan risiko retensi memori (*memory leak*) pada JavaScript Heap?

### 15.3. Skenario Kasus Produksi
11. **Skenario A**: Tim Anda menemukan bahwa sebuah form wizard multi-step yang menggunakan Compound Component Pattern selalu mereset state input setiap kali pengguna berpindah tab. Setelah diperiksa, subkomponen dibungkus dengan `<component :is="...">` dinamis. Apa akar masalah arsitektur tersebut dan bagaimana solusinya tanpa memindahkan state ke state management global (Pinia)?
12. **Skenario B**: Pada sebuah aplikasi e-commerce, sebuah tabel dengan 500 baris data menggunakan Scoped Slot untuk merender baris kustom. Pengembang mengeluhkan bahwa saat satu baris dipilih, seluruh 500 baris ikut ter-render ulang secara bersamaan. Identifikasi sumber inefisiensi reaktivitas pada pemanggilan slot ini dan bagaimana membatasi *render effect*-nya!
13. **Skenario C**: Anda sedang mereview PR (*Pull Request*) junior developer yang membuat komponen autocomplete generic. Developer tersebut menggunakan `provide/inject` yang mengizinkan child mengubah `ref` milik parent melalui `const data = inject('data'); data.value = ...`. Berikan kritik arsitektural berbasis *clean code* serta berikan alternatif implementasi berbasis *Command/Dispatcher pattern*!

---

## 16. Summary

- **Component Contracts** berskala enterprise memerlukan pengetikan statis yang kuat menggunakan kombinasi **Generic Components (`generic="T"`)**, **Discriminated Unions**, serta makro compile-time Vue 3.4+ (`defineSlots`, `defineEmits`, `defineModel`).
- **Compound Components** memecah kompleksitas arsitektur dengan memisahkan *container logic* dari *presentational subcomponents*. Pola ini memanfaatkan dependensi implisit yang aman melalui **`provide`/`inject`** yang dilindungi oleh **`InjectionKey<T>`**.
- **Internal Vue Runtime** mengompilasi slot menjadi fungsi JavaScript murni. Memahami batas *effect scope* dan *tracking boundary* pada slot function adalah kunci mutlak untuk menghindari masalah performa re-render massal (*waterfall re-renders*) dan kebocoran alokasi heap memori.
- Pola arsitektur yang kokoh selalu menerapkan prinsip **Immutability Boundaries**: State internal harus dilindungi via `readonly()`, dan setiap mutasi harus didelegasikan melalui *action dispatchers* eksplisit yang disediakan oleh provider.