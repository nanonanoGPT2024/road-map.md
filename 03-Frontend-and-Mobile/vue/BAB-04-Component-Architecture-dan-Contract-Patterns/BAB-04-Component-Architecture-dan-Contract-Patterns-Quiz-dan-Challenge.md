# BAB-04-Component-Architecture-dan-Contract-Patterns: Quiz, Challenge, & Knowledge Check

Selamat datang di instrumen evaluasi mandiri untuk **BAB 04: Component Architecture dan Contract Patterns**. Bagian ini dirancang untuk menguji, memvalidasi, dan mengonsolidasikan pemahaman arsitektur komponen Vue 3 tingkat lanjut, perancangan kontrak antarmuka tipe (TypeScript contracts), pemanfaatan generic components, scoped slots typesafe, hingga compound component patterns di lingkungan enterprise.

---

## Bagian 1: 5 Basic Questions

### Soal 1: Prop Mutation Anti-Pattern
**Pertanyaan:**
Mengapa mengubah (`mutate`) nilai prop secara langsung di dalam child component (misalnya `props.modelValue = 'baru'` atau `props.user.name = 'Budi'`) dianggap sebagai anti-pattern fatal dalam arsitektur Vue 3, dan apa konsekuensinya terhadap prediktabilitas reaktivitas?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Jawaban:**
Vue menganut prinsip **One-Way Data Flow (Unidirectional Data Flow)**. Semua props membentuk *one-way-down binding* antara parent dan child component. 

Jika child component memutasi prop secara langsung:
1. **Kehilangan Single Source of Truth:** State mutasi menjadi tidak terlacak karena parent component tidak mengetahui kapan dan dari mana data diubah.
2. **Reactivity Race Condition & Inconsistent State:** Setiap kali parent component mengalami re-render, nilai mutasi lokal pada child component akan ditimpa (*overwritten*) oleh nilai prop asli dari parent.
3. **Debugging Nightmare:** Pada objek referensial (`Object` atau `Array`), memutasi property objek child akan berdampak ke state parent secara implisit tanpa melalui event dispatcher (`emit`), merusak isolasi modul dan mempersulit auditing melalui Vue DevTools / Time-travel debugging.

**Solusi Arsitektural:** Emit event update ke parent (misalnya melalui `emit('update:modelValue', val)`) atau gunakan macro `defineModel()` di Vue 3.4+.
</details>

---

### Soal 2: `defineProps` Runtime vs Type-Based Declaration
**Pertanyaan:**
Apa perbedaan mendasar antara runtime declaration (`defineProps({ count: Number })`) dan type-based declaration (`defineProps<{ count: number }>()`) pada `<script setup lang="ts">`, serta bagaimana Vue compiler menangani default value pada type-based declaration?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Jawaban:**
1. **Runtime Declaration:**
   - Menggunakan opsi objek JavaScript standar (`{ count: Number, required: true }`).
   - Validasi dilakukan saat runtime di browser (menghasilkan console warning jika tipe data tidak cocok).
   - Tidak menghasilkan strict type inference otomatis di level compiler/IDE tanpa konfigurasi manual tambahan.

2. **Type-Based Declaration:**
   - Menggunakan TypeScript generic syntax (`defineProps<{ count: number; optionalTag?: string }>()`).
   - Memberikan inferensi tipe statis yang sangat ketat (strict typing) di IDE (Volar/vue-tsc) selama fase kompilasi.
   - Di-compile secara statis oleh compiler `@vue/compiler-sfc` menjadi runtime options ekuivalen demi efisiensi bundle.

3. **Penanganan Default Values:**
   - Pada type-based declaration, default value tidak bisa langsung ditulis di dalam generic argument. Vue menyediakan compile-time macro **`withDefaults()`**:
     ```ts
     export interface Props {
       count?: number
       theme?: 'light' | 'dark'
     }

     const props = withDefaults(defineProps<Props>(), {
       count: 0,
       theme: 'light'
     })
     ```
   - Di Vue 3.5+, fitur *Reactivity Transform* digantikan oleh *Reactive Props Destructure*, di mana destrukturisasi langsung `const { count = 0 } = defineProps<Props>()` mempertahankan reaktivitas dan menetapkan nilai default secara native.
</details>

---

### Soal 3: Native Fallthrough Attributes & `inheritAttrs`
**Pertanyaan:**
Kapan mekanisme fallthrough attributes (`class`, `style`, `id`, `v-on` listeners) otomatis bekerja di Vue 3, dan kapan pengembang wajib menyetel `inheritAttrs: false` beserta penerapan `$attrs` eksplisit?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Jawaban:**
- **Otomatis Bekerja:** Ketika komponen memiliki **tepat satu root element (single root node)**. Vue akan secara otomatis menggabungkan (`merge`) attribute seperti `class` dan event listener parent langsung ke root element child tersebut.
- **Wajib `inheritAttrs: false` Ketika:**
  1. Komponen memiliki **multi-root elements (Fragments)**, di mana Vue tidak dapat menebak root element mana yang harus menerima atribut fallthrough, memicu compiler warning jika tidak di-bind secara eksplisit.
  2. Komponen wrapper (seperti BaseInput atau Modal) di mana root node adalah `<div>` pembungkus, tetapi developer ingin atribut seperti `type`, `placeholder`, `aria-*`, atau event listener dipasang langsung pada elemen internal target (seperti `<input>`), bukan pada wrapper luar.
  
Contoh penerapan:
```vue
<script setup lang="ts">
defineOptions({
  inheritAttrs: false
})
</script>

<template>
  <div class="input-wrapper">
    <label>Field</label>
    <input v-bind="$attrs" class="native-input" />
  </div>
</template>
```
</details>

---

### Soal 4: Type-Safe Provide / Inject Menggunakan `InjectionKey`
**Pertanyaan:**
Bagaimana cara mencegah runtime bug akibat inject key yang bertabrakan (name collision) atau bertipe data `unknown` saat menerapkan pattern dependency injection di Vue 3 TypeScript?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Jawaban:**
Gunakan **`InjectionKey<T>`** yang disediakan oleh Vue bersama dengan ES6 `Symbol`.

1. Definisikan kontrak interface dan buat `InjectionKey`:
   ```ts
   // context.ts
   import type { InjectionKey, Ref } from 'vue'

   export interface TabContext {
     activeTab: Ref<string>
     registerTab: (id: string) => void
   }

   export const TabContextKey: InjectionKey<TabContext> = Symbol('TabContextKey')
   ```

2. Sediakan context di parent component:
   ```ts
   // TabGroup.vue
   provide(TabContextKey, {
     activeTab,
     registerTab
   })
   ```

3. Ambil context di child component dengan type safety terjamin:
   ```ts
   // TabItem.vue
   const context = inject(TabContextKey)
   if (!context) {
     throw new Error('TabItem must be used within TabGroup')
   }
   // context otomatis terinferensi sebagai TabContext tanpa casting 'as TabContext'
   ```
Pola ini mengeliminasi tabrakan nama string global dan menjamin validasi tipe pada saat build time.
</details>

---

### Soal 5: Controlled Component Menggunakan `defineModel`
**Pertanyaan:**
Jelaskan evolusi contract binding dua arah antara Vue 3.3 (menggunakan `v-model` via explicit props & emits) dan Vue 3.4+ yang memanfaatkan macro `defineModel()`. Apa keunggulan arsitektural dari `defineModel()`?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Jawaban:**
- **Sebelum Vue 3.4 (Explicit Boilerplate):**
  Untuk membuat controlled input:
  ```ts
  const props = defineProps<{ modelValue: string }>()
  const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>()
  // Harus membuat computed getter/setter atau event handler manual untuk sinkronisasi
  ```
- **Sejak Vue 3.4 (`defineModel()`):**
  ```ts
  const modelValue = defineModel<string>({ required: true })
  ```
- **Keunggulan Arsitektural:**
  1. Mengurangi boilerplate hingga 70% untuk controlled component.
  2. Menghasilkan variabel bertipe `Ref<T>` yang dapat langsung di-bind ke `v-model` pada native input internal.
  3. Mendukung multiple named v-models (`const title = defineModel<string>('title')`) dan custom modifier parsing (`const [model, modifiers] = defineModel({ set(val) { ... } })`) secara declarative dan type-safe.
</details>

---

## Bagian 2: 5 Intermediate Questions

### Soal 6: Type-Safe Scoped Slots Menggunakan `defineSlots`
**Pertanyaan:**
Pada Vue 3.3+, bagaimana macro `defineSlots` digunakan untuk menetapkan kontrak tipe yang ketat pada scoped slots, dan bagaimana mekanisme ini mencegah error saat konsumen komponen mengakses slot props?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Jawaban:**
Macro `defineSlots` memungkinkan pendefinisian slot dictionary interface di mana setiap properti mewakili nama slot dan fungsinya menerima parameter berupa payload data slot.

Contoh implementasi:
```vue
<script setup lang="ts">
export interface UserRecord {
  id: string
  name: string
  role: 'admin' | 'user'
}

defineSlots<{
  default?: (props: { item: UserRecord; index: number }) => any
  header?: (props: { totalCount: number }) => any
  empty?: () => any
}>()
</script>
```

**Dampak Arsitektural:**
- Jika parent menggunakan `<template #default="{ item }">`, TypeScript IDE language tools (seperti Vue Language Tools/Volar) secara otomatis mengetahui bahwa `item` memiliki field `id`, `name`, dan `role`.
- Jika parent mencoba mengakses field yang tidak ada (`item.nonExistentField`), build error atau linting warning akan langsung dimunculkan sebelum kode masuk ke tahap kompilasi produksi.
</details>

---

### Soal 7: Generic Components (`generic="..."`)
**Pertanyaan:**
Bagaimana cara merancang komponen reusable `DataTable.vue` yang generic terhadap struktur item data yang diterimanya, sehingga tipe slot props dan event payload selalu selaras dengan array tipe data yang dimasukkan ke prop `items`?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Jawaban:**
Gunakan atribut `generic` pada tag `<script setup>`:

```vue
<!-- DataTable.vue -->
<script setup lang="ts" generic="TItem extends { id: string | number }, TKey extends keyof TItem">
interface Props {
  items: TItem[]
  keyField: TKey
  loading?: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'row-click', item: TItem): void
}>()

defineSlots<{
  row?: (props: { item: TItem; index: number }) => any
  cell?: (props: { value: TItem[TKey]; item: TItem }) => any
}>()
</script>

<template>
  <table>
    <tr v-for="(item, index) in items" :key="item[keyField]" @click="emit('row-click', item)">
      <slot name="row" :item="item" :index="index">
        <td>{{ item[keyField] }}</td>
      </slot>
    </tr>
  </table>
</template>
```

**Analisis:**
Ketika konsumen memakai `<DataTable :items="users" keyField="id" @row-click="(u) => ...">`, tipe `u` di-infer secara statis sebagai tipe item dari array `users` (misalnya `User`), mengeliminasi casting `(u as User)` yang rapuh.
</details>

---

### Soal 8: Compound Component Pattern vs Giant Monolithic Prop List
**Pertanyaan:**
Bandingkan arsitektur *Monolithic Component* (misal: `<Dropdown :options="data" :searchable="true" :grouped="true" :customTheme="..." />`) dengan *Compound Component Pattern* (misal: `<Dropdown><DropdownSearch /><DropdownList><DropdownItem /></DropdownList></Dropdown>`). Kapan Compound Component lebih unggul dan apa trade-off-nya?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Jawaban:**
1. **Masalah Monolithic Prop List:**
   - Menghasilkan "Prop Explosion" di mana sebuah komponen menerima puluhan konfigurasi props dan ribuan percabangan internal (`v-if`/`v-else`).
   - Sangat kaku: Mengubah markup atau urutan visual memerlukan prop baru atau scoped slot tambahan.
   - Tree-shaking buruk dan cognitive load tinggi.

2. **Keunggulan Compound Component:**
   - **Inversion of Control (IoC):** Konsumen memiliki kendali penuh atas komposisi DOM, tata letak, dan styling.
   - **Enkapsulasi State Bersama:** Komunikasi state internal ditangani di belakang layar via `provide/inject` (misal: index fokus keyboard, state buka/tutup).
   - **Separation of Concerns:** Setiap sub-komponen bertanggung jawab atas perannya masing-masing (Search, Trigger, Panel, Item).

3. **Trade-offs:**
   - Sedikit lebih verbose dalam markup konsumen.
   - Memerlukan kontrak dependensi implisit (anak komponen wajib berada di dalam parent context), sehingga membutuhkan error handling ketat (`if (!context) throw new Error(...)`).
</details>

---

### Soal 9: Polymorphic Component Contract Menggunakan Dynamic Component `<component :is="...">`
**Pertanyaan:**
Bagaimana merancang komponen tombol universal (`BaseButton`) yang dapat bertindak sebagai `<button>`, `<a>` (link eksternal), atau `<RouterLink>` secara type-safe tanpa menduplikasi styling atau logic aksesibilitas?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Jawaban:**
Gunakan dynamic component `<component :is="...">` yang dikombinasikan dengan discriminated union props di TypeScript:

```vue
<!-- BaseButton.vue -->
<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, type RouteLocationRaw } from 'vue-router'

type ButtonVariants = 'primary' | 'secondary' | 'danger'

type ButtonProps = 
  | { as?: 'button'; to?: never; href?: never; type?: 'button' | 'submit' | 'reset'; disabled?: boolean }
  | { as: 'a'; href: string; to?: never; target?: string; rel?: string; disabled?: boolean }
  | { as: typeof RouterLink; to: RouteLocationRaw; href?: never; disabled?: boolean }

interface CommonProps {
  variant?: ButtonVariants
}

const props = withDefaults(defineProps<ButtonProps & CommonProps>(), {
  variant: 'primary',
  as: 'button'
})

const isComponent = computed(() => {
  if (props.as === 'a') return 'a'
  if (props.as === RouterLink) return RouterLink
  return 'button'
})
</script>

<template>
  <component
    :is="isComponent"
    :to="to"
    :href="href"
    :type="as === 'button' ? (type || 'button') : undefined"
    :aria-disabled="disabled ? 'true' : undefined"
    class="base-btn"
    :class="[`base-btn--${variant}`, { 'base-btn--disabled': disabled }]"
  >
    <slot />
  </component>
</template>
```
Pattern ini mencegah kesalahan kontrak, seperti memberikan prop `to` ketika `as` adalah native HTML button.
</details>

---

### Soal 10: Headless Component Architecture & Separation of Concerns
**Pertanyaan:**
Apa definisi dari *Headless Component* dalam ekosistem Vue 3, bagaimana perbedaannya dengan *Presentational Component*, dan bagaimana scoped slots atau composables digunakan untuk mengimplementasikannya?

<details>
<summary><b>Jawaban & Pembahasan</b></summary>

**Jawaban:**
- **Headless Component:** Komponen yang **hanya mengelola state machine, keyboard accessibility (WAI-ARIA), event handling, dan lifecycle logic**, tanpa memaksakan struktur HTML atau styling visual tertentu.
- **Presentational Component:** Komponen yang berfokus murni pada visual rendering, CSS styling, dan layouting.

**Metode Implementasi:**
1. **Renderless Component (Scoped Slots):**
   Komponen headless membungkus logic dan mengekspos state serta aksi ke default scoped slot:
   ```vue
   <!-- HeadlessToggle.vue -->
   <script setup lang="ts">
   import { ref } from 'vue'
   const isOn = ref(false)
   const toggle = () => (isOn.value = !isOn.value)
   defineSlots<{ default: (props: { isOn: boolean; toggle: () => void }) => any }>()
   </script>
   <template>
     <slot :is-on="isOn" :toggle="toggle" />
   </template>
   ```
2. **Composable Alternative (`useToggle`):**
   Di Vue 3 Composition API, pola headless kini paling sering diwujudkan dalam bentuk **Composables** (seperti Radix Vue / TanStack Table / VueUse), sedangkan komponen pembungkus hanya menerapkan binding ARIA dan directives.
</details>

---

## Bagian 3: 3 Skenario Kasus Nyata Produksi

### Skenario 1: The "Prop Drilling Explosion" pada Dashboard Finansial Multi-Tier
* **Konteks:** Tim frontend membangun dashboard portofolio investasi multi-level: `DashboardView` -> `PortfolioSection` -> `AssetTable` -> `TableRow` -> `ActionMenu`.
* **Masalah:** Developer sebelumnya mengoper 14 props (termasuk `currencyFormat`, `permissionMatrix`, `activeTenantId`, dan fungsi callback audit) melalui setiap lapisan komponen. Ketika `TableRow` membutuhkan format currency baru, seluruh 4 komponen perantara harus diubah dan diuji ulang. Refactoring berujung regression bugs di puluhan test suite.
* **Tantangan Arsitektural:** 
  1. Bagaimana merancang arsitektur kontrak baru yang memutus prop drilling tanpa mengorbankan isolasi testing unit pada `ActionMenu`?
  2. Bagaimana menjamin bahwa komponen level bawah tetap mendapatkan inferensi TypeScript secara otomatis saat me-resolve currency dan permission?
* **Solusi Terstruktur:**
  - Bentuk Context Domain khusus menggunakan `provide`/`inject` dengan `InjectionKey<PortfolioContext>`.
  - Kelompokkan shared concerns ke dalam domain provider tingkat section (`PortfolioProvider.vue`).
  - Untuk isolasi testing: buat composable wrapper `usePortfolioContext()` yang mengembalikan nilai default fallback jika dijalankan di luar provider (berguna untuk isolated unit test `ActionMenu.spec.ts`).

---

### Skenario 2: Dynamic Form Builder dengan Validasi Schema Zod
* **Konteks:** Sistem ERP membutuhkan generator formulir dinamis berdasarkan konfigurasi backend JSON (`fields: [{ type: 'select', name: 'dept', validation: ... }]`).
* **Masalah:** Penggunaan runtime validation berbasis switch-case biasa di dalam satu template monolitik membuat performa form berantakan, rendering lambat pada 80+ fields, dan developer tidak memiliki autocomplete typesafe untuk form state.
* **Tantangan Arsitektural:**
  1. Bagaimana menyusun *Component Registry Pattern* yang memetakan field type ke dedicated micro-components (`FieldText`, `FieldSelect`, `FieldDate`) secara modular?
  2. Bagaimana merancang kontrak form state dua arah typesafe menggunakan `defineModel` dan integrasi Zod schema parsing?
* **Solusi Terstruktur:**
  - Buat Form Field Registry menggunakan tokenized key map: `Record<FieldType, Component>`.
  - Terapkan generic form container: `<DynamicForm :schema="zodSchema" v-model="formData">`.
  - Masing-masing field component hanya mengekspos kontrak standar: `modelValue`, `error`, dan emit `blur`/`focus`. State management pusat dikelola secara reaktif via parent context provider.

---

### Skenario 3: Desain System Reusable Modal dengan Teleport & Accessibility Trap
* **Konteks:** Modul core design system organisasi menyediakan `BaseModal.vue` yang digunakan oleh 15 sub-aplikasi mikro-frontend.
* **Masalah:** 
  1. Z-index bertabrakan dengan elemen navbar floating fixed parent.
  2. Pengguna tunanetra dan keyboard-only navigation kehilangan fokus navigasi: tombol `Tab` keluar dari modal dan berfokus pada konten latar belakang yang tersembunyi (*focus leak*).
  3. Ketika modal ditutup melalui tombol ESC, state `isOpen` di parent tidak tersinkronisasi.
* **Tantangan Arsitektural:**
  1. Rancang komponen modal headless/accessible yang memanfaatkan `<Teleport to="body">`.
  2. Implementasikan kontrak sinkronisasi lifecycle dua arah yang aman menggunakan `defineModel<boolean>()`.
  3. Terapkan keyboard trap handling (`keydown.esc`, trap focus tab) dan atribut ARIA standar (`role="dialog"`, `aria-modal="true"`).

---

## Bagian 4: 1 Practical Chapter Challenge

### Challenge: Membangun Type-Safe Headless Stepper (Wizard) Compound Component
Terapkan sekumpulan komponen compound yang type-safe untuk menangani alur wizard multi-langkah (multi-step form).

#### Spesifikasi Kebutuhan Komponen:
1. **`StepWizard.vue` (Parent Container):**
   - Menerima `v-model` berupa `currentStep: number` atau `currentStepId: string` menggunakan `defineModel()`.
   - Mengelola navigasi (`nextStep`, `prevStep`, `goToStep`, `isLastStep`, `isFirstStep`).
   - Menyediakan context type-safe melalui `InjectionKey<WizardContext>`.
   - Mencegah perpindahan step jika step aktif memiliki form validator async yang mengembalikan `false`.

2. **`StepItem.vue` (Child Step):**
   - Menerima prop `id: string`, `title: string`, dan fungsi validator opsional `validate?: () => Promise<boolean> | boolean`.
   - Mendaftarkan diri ke parent saat di-mount dan unregister saat di-unmount.
   - Hanya menampilkan konten (`<slot />`) jika step tersebut sedang aktif.

3. **`StepControls.vue` (Child Action Bar):**
   - Merender tombol Back dan Next/Finish secara dinamis berdasarkan state wizard.
   - Menyediakan slot kustom jika konsumen ingin mengganti desain tombol.

#### Kriteria Keberhasilan:
- Tidak ada type `any` yang diizinkan. Seluruh contracts, emits, slots, dan injections wajib di-type secara eksplisit di TypeScript.
- Error runtime yang ramah developer harus dilemparkan jika `StepItem` atau `StepControls` digunakan di luar `StepWizard`.
- Validasi step async harus dicegah jika proses validasi sedang `loading`.

---

## Bagian 5: Checklist Pemahaman

Gunakan tabel verifikasi di bawah ini untuk menilai kesiapan kompetensi arsitektur komponen Anda:

| Kompetensi Inti | Indikator Keberhasilan | Status Diri |
| :--- | :--- | :---: |
| **Strict Type Contracts** | Mampu menulis `defineProps<T>()` dan `defineEmits<T>()` tanpa runtime fallback objects serta menguasai macro `withDefaults`. | [ ] Siap |
| **Controlled Models** | Memahami arsitektur `defineModel()` di Vue 3.4+ untuk single maupun multiple bindings beserta modifier parsing. | [ ] Siap |
| **Generic Components** | Mampu mengimplementasikan `<script setup generic="...">` untuk komponen list/table dinamis yang type-safe hingga level slot props. | [ ] Siap |
| **Type-Safe Slots** | Mampu mendeklarasikan kontrak slot yang ketat menggunakan macro `defineSlots<T>()`. | [ ] Siap |
| **Compound Components** | Mampu merancang komponen yang berbagi state internal via `provide`/`inject` dengan `InjectionKey<Symbol>` dan proper unmount cleanup. | [ ] Siap |
| **Fallthrough & Attributes** | Memahami aturan pewarisan atribut otomatis, penggunaan `inheritAttrs: false`, dan delegasi atribut via `$attrs`. | [ ] Siap |
| **Polymorphism & A11y** | Mampu mengimplementasikan dynamic root `<component :is="...">` dan mematuhi standar dasar WAI-ARIA pada reusable UI. | [ ] Siap |
