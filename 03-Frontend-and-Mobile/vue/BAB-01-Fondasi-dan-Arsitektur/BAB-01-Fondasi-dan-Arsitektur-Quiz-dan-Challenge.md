# BAB-01-Fondasi-dan-Arsitektur: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang untuk menguji, memvalidasi, dan memperdalam pemahaman arsitektural serta teknis seputar fondasi Vue 3, Reactivity System berbasis Proxy, Virtual DOM vs Incremental/Direct DOM update, Composition API vs Options API, struktur Single File Component (SFC), dan pipeline tooling modern (Vite / Rollup).

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1.1: Mekanisme Inti Proxy vs `Object.defineProperty`
**Pertanyaan:**  
Mengapa Vue 3 beralih dari `Object.defineProperty` (digunakan pada Vue 2) ke JavaScript ES6 `Proxy` sebagai fondasi reactivity engine? Sebutkan setidaknya dua limitasi fundamental pada Vue 2 yang diselesaikan oleh perubahan arsitektur ini.

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**  
Vue 3 beralih ke ES6 `Proxy` karena `Proxy` membungkus seluruh objek target dan mencegat operasi di level objek (seperti get, set, deleteProperty, has, ownKeys), bukan di level mutasi properti individual seperti `Object.defineProperty`.

Dua limitasi fundamental Vue 2 yang terselesaikan:
1. **Penambahan & Penghapusan Properti Baru Secara Dinamis:** Pada Vue 2, properti baru yang ditambahkan ke objek reaktif setelah inisialisasi tidak memicu reaktivitas tanpa bantuan API khusus `Vue.set()` atau `this.$set()`. Begitu pula operasi `delete` membutuhkan `Vue.delete()`. Di Vue 3, `Proxy` mencegat penambahan/penghapusan properti secara otomatis tanpa bantuan helper method.
2. **Mutasi Indeks & Panjang Array:** Vue 2 tidak dapat mendeteksi mutasi array langsung via indeks (misal `arr[0] = val`) atau perubahan properti `arr.length = 0` secara efisien melalui setter properti, sehingga Vue 2 memodifikasi prototype method array (`push`, `pop`, `splice`, dll.). Di Vue 3, `Proxy` secara native menangani mutasi indeks dan mutasi length array tanpa monkey-patching prototype.
</details>

---

### Soal 1.2: Perbedaan Fundamental `ref()` vs `reactive()`
**Pertanyaan:**  
Kapan Anda harus menggunakan `ref()` dibandingkan `reactive()`, dan apa yang terjadi jika Anda melakukan destructuring (`const { count } = state`) pada objek yang dibuat dengan `reactive()`?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**  
- **`ref()`**: Digunakan untuk nilai primitif (`string`, `number`, `boolean`, `null`, `undefined`, `symbol`, `bigint`) maupun objek kompleks. `ref` membungkus nilai dalam objek wrapper dengan properti `.value`. Di dalam template SFC, `ref` di-unwrap secara otomatis sehingga tidak membutuhkan penulisan `.value`.
- **`reactive()`**: Hanya menerima tipe referensi (`object`, `array`, `Map`, `Set`). Objek dikonversi langsung menjadi reactive proxy secara deep.

**Dampak Destructuring pada `reactive()`:**  
Ketika melakukan destructuring pada objek `reactive()`, variabel hasil dekonstruksi akan kehilangan reaktivitas (menjadi nilai primitif lepas atau referensi biasa yang terputus dari handler proxy getter/setter). Untuk mempertahankan reaktivitas saat dekonstruksi, harus menggunakan utilitas `toRefs()` atau `toRef()`.
</details>

---

### Soal 1.3: Siklus Hidup SFC: Compilation Pipeline
**Pertanyaan:**  
Bagaimana arsitektur compiler `@vue/compiler-sfc` memproses blok `<template>`, `<script setup>`, dan `<style scoped>` dalam sebuah file `.vue` sebelum di-bundle oleh Vite/Rollup?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**  
Compiler SFC mem-parse file `.vue` menjadi SFC Descriptor (AST) melalui method `parse()`:
1. **`<template>`**: Di-compile oleh `@vue/compiler-dom` menjadi JavaScript `render()` function murni. Compiler menganalisis binding statis vs dinamis, menghasilkan hoistable vnodes dan PatchFlags untuk optimalisasi runtime vdom.
2. **`<script setup>`**: Ditransformasikan oleh compiler script menjadi setup function tubuh komponen. Deklarasi level teratas (variabel, fungsi, import) secara otomatis diekspos ke scope render function tanpa perlu eksplisit `return { ... }`.
3. **`<style scoped>`**: Di-scope menggunakan PostCSS plugin internal Vue. Compiler menghasilkan atribut unik pada elemen (misalnya `data-v-7ba5bd90`) dan menambahkan atribut tersebut ke CSS selector (misal `.btn[data-v-7ba5bd90]`).
Hasil akhir dari ketiga blok digabungkan menjadi sebuah modul JavaScript ES standar yang mengekspor definisi komponen.
</details>

---

### Soal 1.4: Peran PatchFlags dan Hoisting pada Virtual DOM Vue 3
**Pertanyaan:**  
Jelaskan konsep **Static Hoisting** dan **PatchFlags** pada compiler template Vue 3, serta bagaimana keduanya membuat Virtual DOM Vue 3 jauh lebih cepat daripada Virtual DOM konvensional.

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**  
- **Static Hoisting:** Compiler mendeteksi node, elemen, atau atribut yang sepenuhnya statis (tidak memiliki data binding dinamis). Node ini "diangkat" (hoist) ke luar fungsi `render()`, sehingga hanya dialokasikan di memori sekali saat evaluasi modul pertama kali, bukan dibuat ulang setiap kali re-render terjadi.
- **PatchFlags:** Compiler menyematkan bitwise flags numerik pada setiap dynamic VNode yang di-generate. Flag ini mengindikasikan secara presisi bagian apa yang dinamis (contoh: `1 /* TEXT */`, `2 /* CLASS */`, `8 /* PROPS */`).

**Keunggulan Performa:**  
Virtual DOM konvensional melakukan recursive tree diffing menyeluruh pada seluruh cabang VNode. Di Vue 3, runtime diffing hanya memeriksa dynamic children di dalam "Block Tree" dan menggunakan PatchFlags untuk melompati pemeriksaan properti statis. Diffing berlangsung O(dynamic content), bukan O(total DOM hierarchy).
</details>

---

### Soal 1.5: `watch` vs `watchEffect`
**Pertanyaan:**  
Apa perbedaan utama antara `watch` dan `watchEffect` dalam hal dependency tracking dan lazy execution?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**  
1. **Lazy Execution:**
   - `watch` bersifat *lazy by default*; callback tidak dieksekusi saat inisialisasi kecuali properti `{ immediate: true }` didefinisikan.
   - `watchEffect` bersifat *eager*; callback langsung dieksekusi sekali saat inisialisasi untuk melacak dependency secara otomatis.
2. **Dependency Tracking:**
   - `watch` mengharuskan developer mendeklarasikan sumber data reaktif secara eksplisit (misal: `watch(source, (newVal, oldVal) => {})`).
   - `watchEffect` melacak semua properti reaktif yang diakses (read) di dalam closure fungsi eksekusinya secara implisit, dan tidak menyediakan akses langsung ke nilai sebelum perubahan (`oldValue`).
</details>

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 2.1: Memory Leak pada Custom Reactive Subscriptions
**Pertanyaan:**  
Di dalam komponen `<script setup>`, seorang insinyur membuat subscription ke WebSocket server dan mendengarkan event DOM global (`window.addEventListener('resize')`) di dalam fungsi `setup()`. Mengapa hal ini berpotensi memicu memory leak jika komponen tersebut di-mount dan di-unmount berulang kali dalam arsitektur SPA? Lifecycle hook apa dan helper API apa yang wajib diterapkan untuk mitigasi?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**  
**Penyebab Memory Leak:**  
Closure yang dibuat di dalam scope komponen mempertahankan referensi terhadap instance komponen dan variabel lokalnya. Saat komponen di-unmount dari DOM oleh router atau conditional rendering (`v-if`), garbage collector browser tidak dapat membersihkan instance komponen dari heap memory karena event emitter global (`window`) dan connection instance WebSocket masih memegang pointer fungsi callback tersebut.

**Mitigasi:**  
1. **Lifecycle Hook:** Gunakan `onUnmounted()` atau `onBeforeUnmount()` untuk melepaskan listener secara eksplisit:
   ```ts
   window.removeEventListener('resize', handleResize)
   socket.disconnect()
   ```
2. **Helper API / Effect Scope:** Gunakan `effectScope()` untuk composable yang kompleks agar seluruh reactive effects dan watcher dapat dihentikan sekaligus via `scope.stop()`.
</details>

---

### Soal 2.2: Reactive Loss pada Parameter Composable
**Pertanyaan:**  
Perhatikan potongan kode composable berikut:
```ts
export function useUserData(userId: number) {
  const user = ref(null)
  const fetchUser = async () => {
    user.value = await api.getUser(userId)
  }
  watchEffect(() => {
    fetchUser()
  })
  return { user }
}
```
Jika komponen pemanggil memanggil `useUserData(props.currentUserId)` di mana `props.currentUserId` berubah sepanjang waktu, mengapa `fetchUser` tidak pernah dipicu ulang saat prop berganti nilai? Bagaimana cara merekayasa signature composable agar mendukung VueUse paradigm (`MaybeRefOrGetter`)?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**  
**Penyebab Masalah:**  
Argumen `userId: number` dievaluasi saat fungsi `useUserData()` pertama kali dipanggil. Nilai yang dioper ke fungsi adalah nilai primitif number statis hasil copy-by-value saat evaluasi awal. Di dalam `watchEffect`, tidak ada reaktif getter yang dibaca; `userId` hanyalah variabel lokal number statis, sehingga watcher tidak memiliki reactive dependency untuk melacak perubahan.

**Solusi Arsitektur (`toValue` / `MaybeRefOrGetter`):**
Ubah signature agar menerima `MaybeRefOrGetter<number>` dan gunakan utilitas `toValue()`:
```ts
import { ref, watchEffect, toValue, type MaybeRefOrGetter } from 'vue'

export function useUserData(userId: MaybeRefOrGetter<number>) {
  const user = ref(null)
  
  watchEffect(async () => {
    const id = toValue(userId) // Memicu dependency tracking jika berupa ref atau getter () => props.currentUserId
    user.value = await api.getUser(id)
  })
  
  return { user }
}
```
Pemanggil kemudian dapat memanggil: `useUserData(() => props.currentUserId)` atau `useUserData(toRef(props, 'currentUserId'))`.
</details>

---

### Soal 2.3: `nextTick()` dan Batch Update Lifecycle
**Pertanyaan:**  
Ketika Anda mengubah nilai reaktif `count.value = 10` lalu segera membaca elemen DOM `document.getElementById('counter').innerText`, Anda masih mendapati nilai lama. Jelaskan arsitektur microtask scheduler pada Vue 3 yang mendasari fenomena ini, dan bagaimana `nextTick()` menyelesaikan problem sinkronisasi DOM.

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**  
**Arsitektur Scheduler:**  
Ketika dependensi reaktif mengalami mutasi, Vue tidak langsung memicu sinkronisasi DOM secara sinkron (synchronous DOM rendering) demi menghindari overhead performa akibat layout thrashing jika terjadi mutasi bertubi-tubi. Sebaliknya, component update job dimasukkan ke dalam antrean (*queue*) unik.

Vue menggunakan **Microtask Queue** JavaScript (`Promise.resolve().then()`) untuk melakukan batch update:
1. Beberapa perubahan state dalam satu tick eksekusi JavaScript digabungkan.
2. Duplicate render jobs untuk komponen yang sama dieliminasi.
3. Seluruh queue di-flush dalam satu microtask tick.

**Peran `nextTick()`:**  
`nextTick(callback)` mengembalikan Promise yang di-resolve setelah queue microtask scheduler Vue selesai menjalankan operasi patch DOM. Dengan melakukan `await nextTick()`, kode berikutnya dijamin membaca representasi DOM terbaru setelah proses render selesai.
</details>

---

### Soal 2.4: `shallowRef` vs `ref` untuk Optimasi Large-Scale Data
**Pertanyaan:**  
Mengapa penggunaan `ref()` atau `reactive()` pada koleksi dataset besar (misalnya GeoJSON 50MB atau tabel 100.000 records dari WebSocket) dapat mengakibatkan degradasi performa drastis atau browser tab freeze? Bagaimana `shallowRef()` memecahkan masalah ini dan bagaimana cara memicu pembaruan tampilannya?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**  
**Penyebab Degradasi Performa:**  
`ref()` dan `reactive()` menerapkan konversi reaktivitas secara *deep* (mendalam). Setiap sub-objek, child array, dan properti nested dalam struktur 50MB akan dibungkus ke dalam ES6 Proxy instance saat diakses atau diinisialisasi. Overhead pembuatan ribuan objek Proxy dan pemetaan dependensi memakan alokasi memori yang masif dan CPU processing yang memicu frame drops.

**Solusi `shallowRef()`:**  
`shallowRef()` hanya membuat properti `.value` itu sendiri yang reaktif. Seluruh isi nested di dalam objek target dibiarkan sebagai JavaScript object biasa tanpa dibungkus Proxy:
1. Mutasi internal properti (misal `geoData.value.features[0].geometry = ...`) tidak akan memicu trigger reaksi reaktivitas secara otomatis.
2. Pembaruan tampilan dipicu dengan mengganti seluruh referensi objek (`geoData.value = newGeoData`) atau dengan memanggil helper eksplisit `triggerRef(geoData)`.
</details>

---

### Soal 2.5: Scoped CSS Leakage melalui Child Root Node
**Pertanyaan:**  
Pada implementasi `<style scoped>`, selector CSS di komponen induk terkadang secara tidak sengaja menimpa (leak) styling root element di komponen anak. Jelaskan mengapa secara teknis hal ini terjadi menurut spesifikasi Scoped CSS Vue, dan apa solusinya jika styling hanya boleh berlaku strictly di komponen induk?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**  
**Penyebab Teknis:**  
Menurut desain PostCSS Scoped CSS di Vue, root node dari sebuah child component menerima dua data attribute scoped identifier sekaligus:
1. Scope ID milik komponen anak itu sendiri (`data-v-child`).
2. Scope ID milik komponen induk langsung (`data-v-parent`).

Desain ini dibuat secara sengaja agar komponen induk dapat mengatur tata letak (layout/positioning, margin, grid placement) dari komponen anak langsung dari parent style context. Namun, jika selector di parent menggunakan selector generik (misal `div` atau `.card`), selector tersebut akan cocok dengan root node child component.

**Solusi:**  
1. Hindari tag selector telanjang pada parent scoped style; gunakan penamaan class BEM yang spesifik.
2. Gunakan wrapper container di parent jika diperlukan isolasi total.
3. Hindari komponen anak memiliki single root node jika ingin menonaktifkan pewarisan atribut otomatis (gunakan multi-root fragment component di Vue 3) atau terapkan `inheritAttrs: false`.
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 3.1: Infinite Loop pada Watcher Mutasi Data Real-Time
**Konteks Masalah:**  
Tim frontend mengimplementasikan modul trading dashboard yang menampilkan order book. Order book diperbarui via WebSocket setiap 100ms. Seorang developer menulis kode berikut di komponen utama:

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'

interface Order { id: string; price: number; amount: number }
const orders = ref<Order[]>([])
const normalizedOrders = ref<Order[]>([])

watch(orders, (newOrders) => {
  // Melakukan sorting dan normalisasi data
  const processed = [...newOrders].sort((a, b) => b.price - a.price)
  normalizedOrders.value = processed
  
  // Mencatat log analitik internal
  orders.value.forEach(o => {
    o.amount = Math.round(o.amount * 100) / 100
  })
}, { deep: true })
</script>
```

**Insiden:**  
Aplikasi mengalami freeze, CPU usage browser melonjak ke 100%, dan console melemparkan error:
`Maximum recursive updates exceeded. This means you've got a reactive effect that is mutating its own dependencies.`

**Pertanyaan Analisis & Solusi:**
1. Bedah secara mendalam mengapa infinite loop tersebut terjadi di runtime Vue.
2. Refactor kode tersebut menjadi arsitektur yang idomatik, bersih, dan berperforma tinggi tanpa watcher side-effect mutasi.

<details>
<summary>Solusi & Pembahasan Arsitektural</summary>

**1. Analisis Akar Masalah:**  
- Parameter `{ deep: true }` menginstruksikan Vue untuk melacak setiap mutasi properti di dalam array `orders`, termasuk nested property `o.amount`.
- Di dalam callback watcher, kode melakukan: `orders.value.forEach(o => { o.amount = ... })`.
- Mutasi langsung pada `o.amount` mencegat Proxy `set` handler pada item di dalam `orders`.
- Karena `orders` sedang diamati secara `deep`, mutasi `o.amount` di dalam callback watcher memicu kembali watcher yang sama (self-triggering).
- Akibatnya, scheduler kehabisan slot siklus iterasi dan melempar exception `Maximum recursive updates exceeded`.

**2. Refactoring Solusi Idiomatik:**  
Gunakan `computed()` murni untuk data turunan tanpa memutasi sumber asli, dan pisahkan normalisasi data saat penerimaan WebSocket payload:

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'

interface Order { id: string; price: number; amount: number }
const rawOrders = ref<readonly Order[]>([])

// Menggunakan computed: lazy, memoized, murni, dan tanpa side-effect
const normalizedOrders = computed<Order[]>(() => {
  return rawOrders.value
    .map(order => ({
      ...order,
      amount: Math.round(order.amount * 100) / 100
    }))
    .sort((a, b) => b.price - a.price)
})

// Fungsi handler saat data diterima dari WebSocket
function onWebSocketMessage(incomingData: Order[]) {
  // Perlakukan incoming state sebagai immutable snapshot
  rawOrders.value = Object.freeze(incomingData)
}
</script>
```
</details>

---

### Skenario 3.2: Reaktivitas Hilang saat Transisi Migrasi Vue 2 Options API ke Vue 3 Composition API
**Konteks Masalah:**  
Sebuah aplikasi ERP enterprise sedang dimigrasikan bertahap dari Vue 2 Options API ke Vue 3 `<script setup>`. Seorang developer memindahkan state form multi-step dari data options menjadi reactive object:

```vue
<script setup lang="ts">
import { reactive } from 'vue'

let formData = reactive({
  organization: '',
  taxId: '',
  address: {
    city: '',
    postalCode: ''
  }
})

// Fungsi reset form saat user menekan tombol 'Clear Form'
const resetForm = () => {
  formData = reactive({
    organization: '',
    taxId: '',
    address: {
      city: '',
      postalCode: ''
    }
  })
}
</script>

<template>
  <form @submit.prevent>
    <input v-model="formData.organization" placeholder="Nama Organisasi" />
    <button type="button" @click="resetForm">Clear Form</button>
  </form>
</template>
```

**Insiden:**  
Ketika user mengetik pertama kali, input form bekerja. Namun setelah menekan tombol "Clear Form", input field tidak ter-reset, dan pengetikan berikutnya sama sekali tidak memperbarui `formData.organization`.

**Pertanyaan Analisis & Solusi:**
1. Mengapa assignment ulang `formData = reactive(...)` memutus reaktivitas template binding secara permanen?
2. Berikan 2 alternatif perbaikan arsitektural yang benar untuk mengimplementasikan fungsionalitas reset form tersebut.

<details>
<summary>Solusi & Pembahasan Arsitektural</summary>

**1. Analisis Penyebab:**  
- Ketika komponen di-compile, fungsi render mengunci referensi proxy awal yang ditunjuk oleh `formData`.
- Variabel lokal `formData` dideklarasikan dengan `let`. Saat `resetForm` dieksekusi, ekspresi `formData = reactive(...)` hanya mengalihkan pointer variabel lokal `formData` ke objek Proxy baru di memori lokal fungsi.
- Template render function dan watcher internal masih memegang referensi ke Proxy instance lama. Binding `v-model` pada template tetap terikat pada instance lama yang sudah ditinggalkan, sehingga UI tidak ter-refresh dan input field berhenti merespons.

**2. Dua Alternatif Perbaikan:**

*Alternatif A: Menggunakan `ref()` (Direkomendasikan):*
```vue
<script setup lang="ts">
import { ref } from 'vue'

const createInitialState = () => ({
  organization: '',
  taxId: '',
  address: { city: '', postalCode: '' }
})

const formData = ref(createInitialState())

const resetForm = () => {
  formData.value = createInitialState() // Mengganti .value aman karena wrapper ref tetap utuh
}
</script>

<template>
  <form @submit.prevent>
    <input v-model="formData.organization" />
    <button type="button" @click="resetForm">Clear Form</button>
  </form>
</template>
```

*Alternatif B: Mempertahankan Objek `reactive` dengan `Object.assign`:*
```ts
const initialValues = {
  organization: '',
  taxId: '',
  address: { city: '', postalCode: '' }
}

const formData = reactive({ ...initialValues, address: { ...initialValues.address } })

const resetForm = () => {
  Object.assign(formData, {
    ...initialValues,
    address: { ...initialValues.address }
  })
}
```
</details>

---

### Skenario 3.3: Komponen Dropdown Berat Menyebabkan Lag pada Virtual DOM Diffing
**Konteks Masalah:**  
Sebuah aplikasi logistik memiliki tabel pemantauan armada dengan 2.000 baris. Di setiap baris, terdapat komponen custom action menu (`<RowActionDropdown />`) yang memiliki modal konfirmasi, tooltip, dan 8 menu item.

Ketika user mengubah filter status (yang memicu re-render tabel), browser mengalami jank selama 800ms. Profiling via Chrome DevTools Performance panel menunjukkan waktu habis di execution script: `patchElement` dan `renderComponentRoot`.

**Pertanyaan Analisis & Solusi:**
1. Evaluasi arsitektur komponen tersebut. Mengapa Virtual DOM tree diffing menjadi bottleneck saat 2.000 sub-komponen dirender bersamaan?
2. Strategi arsitektur apa saja (minimal 3 level optimasi) yang harus diimplementasikan untuk menurunkan render time menjadi di bawah 50ms?

<details>
<summary>Solusi & Pembahasan Arsitektural</summary>

**1. Analisis Bottleneck:**  
Meskipun Vue 3 memiliki optimasi block tree dan patch flags, menginisialisasi dan men-diff 2.000 instance komponen lengkap dengan 8 sub-elemen, tooltip, dan modal berarti Vue harus:
- Mengalokasikan 2.000 component instances di memory heap.
- Mengevaluasi lifecycle hooks, props normalization, reactive proxy scope untuk masing-masing dropdown.
- Men-generate puluhan ribu VNode objects di memory saat re-render.
Bottleneck terletak pada pembuatan component instance dan DOM allocation yang melampaui kemampuan rendering frame 60fps browser.

**2. Tiga Level Solusi Arsitektural:**

1. **Virtual Windowing / Virtual Scrolling (Data-level):**  
   Gunakan library virtual scrolling (seperti `@tanstack/vue-virtual` atau `vue-virtual-scroller`). Render hanya 20-30 baris yang terlihat di dalam viewport layar, bukan 2.000 baris sekaligus. Ini memangkas jumlah VNode dari puluhan ribu menjadi ratusan saja.

2. **Teleport & Single Shared Modal/Dropdown Pattern (DOM Architecture-level):**  
   Jangan merender 2.000 instance modal dan 2.000 dropdown menu di dalam setiap baris tabel.  
   Gunakan arsitektur **Shared Flyweight Overlay**: Hanya letakkan satu tombol pemicu ringan di baris tabel. Saat tombol diklik, simpan state baris yang aktif (`activeRowId`) di store/parent, dan buka satu instance global floating dropdown yang di-mount via `<Teleport to="body">`.

3. **`v-once` atau `v-memo` (VNode Caching-level):**  
   Untuk baris tabel yang datanya tidak mengalami mutasi saat filter berganti, bungkus baris menggunakan direktif `v-memo="[row.id, row.status, row.updatedAt]"`. Vue akan melompati seluruh sub-tree diffing dan pembuatan VNode baru jika nilai dependensi memoization tidak berubah.
</details>

---

## Bagian 4: Practical Chapter Challenge (1 Tantangan Praktek)

### Tantangan: Membangun Lightweight Reusable Mini-Store Engine dengan Pure Vue 3 Reactivity

#### Latar Belakang & Spesifikasi Kebutuhan
Dalam arsitektur micro-frontend atau modul independen berskala kecil, menginstal Pinia terkadang dianggap terlalu berlebih jika modul hanya membutuhkan reactive state management lokal yang terisolasi namun dapat dibagikan antar komponen dalam modul tersebut.

Anda diminta untuk merancang dan mengimplementasikan modul TypeScript bernama `createMiniStore` yang memanfaatkan primitive reactivity engine Vue 3 murni (`reactive`, `computed`, `readonly`, `effectScope`).

#### Persyaratan Teknis (Technical Requirements):
1. **Type-Safe State & Getters:** Mendukung inferensi TypeScript penuh untuk state, getters, dan actions.
2. **State Protection:** State internal tidak boleh dapat dimutasi secara langsung dari luar store (`readonly` state exposure). Seluruh mutasi hanya boleh dilakukan melalui actions.
3. **Computed Getters:** Mendukung deklarasi getters yang bersifat computed (memiliki caching dan dependensi otomatis).
4. **Lifecycle & Scope Disposal:** Menggunakan `effectScope()` untuk mengisolasi semua reactive effects dan computed getters di dalam store, serta menyediakan method `dispose()` untuk membersihkan seluruh subscription dari memori saat modul di-unmount.
5. **Reset Capability:** Menyediakan built-in method `$reset()` yang mengembalikan state ke initial snapshot saat store pertama kali diinisialisasi.

#### Kode Implementasi Solusi Acuan

```ts
// miniStore.ts
import { reactive, readonly, computed, effectScope, toRaw, type DeepReadonly, type EffectScope } from 'vue'

export type StoreOptions<
  TState extends Record<string, any>,
  TGetters extends Record<string, (state: DeepReadonly<TState>) => any>,
  TActions extends Record<string, (...args: any[]) => any>
> = {
  id: string
  state: () => TState
  getters?: TGetters
  actions: (context: {
    state: TState
    getters: { [K in keyof TGetters]: ReturnType<TGetters[K]> }
  }) => TActions
}

export type MiniStore<TState, TGetters, TActions> = {
  id: string
  state: DeepReadonly<TState>
  getters: { [K in keyof TGetters]: ReturnType<TGetters[K]> }
  actions: TActions
  $reset: () => void
  dispose: () => void
}

export function createMiniStore<
  TState extends Record<string, any>,
  TGetters extends Record<string, (state: DeepReadonly<TState>) => any> = Record<string, never>,
  TActions extends Record<string, (...args: any[]) => any> = Record<string, never>
>(options: StoreOptions<TState, TGetters, TActions>): MiniStore<TState, TGetters, TActions> {
  const scope: EffectScope = effectScope(true)
  
  // Ambil initial snapshot untuk kemampuan $reset()
  const initialFactory = options.state
  const internalState = reactive<TState>(initialFactory())
  
  let storeGetters = {} as { [K in keyof TGetters]: ReturnType<TGetters[K]> }
  let storeActions = {} as TActions

  scope.run(() => {
    // 1. Inisialisasi Getters dengan proteksi state readonly
    if (options.getters) {
      const computedGetters = {} as Record<string, any>
      const readonlyStateForGetters = readonly(internalState)

      for (const [getterKey, getterFn] of Object.entries(options.getters)) {
        computedGetters[getterKey] = computed(() => getterFn(readonlyStateForGetters))
      }
      storeGetters = computedGetters as any
    }

    // 2. Inisialisasi Actions dengan binding state internal
    storeActions = options.actions({
      state: internalState,
      getters: storeGetters
    })
  })

  // 3. Reset function: mengembalikan state ke struktur pabrikasi awal
  const $reset = () => {
    const freshState = initialFactory()
    // Hapus properti lama jika ada yang dinamis
    for (const key of Object.keys(internalState)) {
      if (!(key in freshState)) {
        delete (internalState as any)[key]
      }
    }
    // Salin kembali nilai awal ke state reaktif
    Object.assign(internalState, freshState)
  }

  // 4. Dispose: matikan seluruh watcher & computed effects di dalam scope
  const dispose = () => {
    scope.stop()
  }

  return {
    id: options.id,
    state: readonly(internalState),
    getters: storeGetters,
    actions: storeActions,
    $reset,
    dispose
  }
}
```

#### Contoh Penggunaan & Verifikasi:
```ts
// useCounterStore.ts
export const useCounterStore = () => createMiniStore({
  id: 'counter',
  state: () => ({
    count: 0,
    history: [] as number[]
  }),
  getters: {
    doubleCount: (state) => state.count * 2,
    isPositive: (state) => state.count > 0
  },
  actions: ({ state }) => ({
    increment() {
      state.count++
      state.history.push(state.count)
    },
    decrement() {
      state.count--
      state.history.push(state.count)
    }
  })
})
```

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan checklist ini untuk mengukur kesiapan arsitektural sebelum melanjutkan ke **BAB 02: Komponen dan Sistem Reaktivitas Lanjutan**:

- [ ] **Mekanika Reaktivitas:** Mampu menjelaskan alur `track()` (dependensi dikumpulkan via `activeEffect` dan `WeakMap -> Map -> Set`) dan `trigger()` (memicu scheduler/effects) pada source code `@vue/reactivity`.
- [ ] **Unwrapping Behaviour:** Memahami kapan `ref` di-unwrap otomatis (pada root template, di dalam `reactive()` object) dan kapan tidak di-unwrap (di dalam `reactive()` Array atau Map/Set collections).
- [ ] **Compilation Anatomy:** Mengetahui perbedaan peran parser SFC, template compiler (`@vue/compiler-dom`), dan script transformer (`@vue/compiler-sfc`).
- [ ] **Effect Scope Mastery:** Memahami alasan penggunaan `effectScope()` pada arsitektur library/plugin dan bagaimana cara menghentikan detached effects untuk mencegah memory leaks.
- [ ] **Vite Optimization Pipeline:** Memahami bagaimana Vite memanfaatkan ES Modules (ESM) native di development mode dan transisi ke Rollup di production build dengan code splitting.
- [ ] **Virtual DOM Heuristics:** Mampu menganalisis kapan VDOM overhead lebih tinggi daripada direct DOM manipulation dan bagaimana compiler hints (PatchFlags, cache handlers, static hoists) memitigasi overhead tersebut.
