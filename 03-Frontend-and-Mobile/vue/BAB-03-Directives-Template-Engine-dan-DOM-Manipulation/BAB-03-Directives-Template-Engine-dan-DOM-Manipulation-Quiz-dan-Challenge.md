# BAB-03-Directives-Template-Engine-dan-DOM-Manipulation: Quiz, Challenge, & Knowledge Check

Dokumen evaluasi mandiri ini dirancang untuk menguji pemahaman mendalam seputar sistem template Vue 3, compiler directives (`v-bind`, `v-model`, `v-if`, `v-for`, `v-memo`, `v-once`, `v-html`), custom directives lifecycle, serta mekanisme manipulasi DOM dan patch virtual DOM (VNode diffing).

---

## Bagian A: 5 Basic Questions

### Soal 1: Perbedaan Mendasar `v-if` vs `v-show`
**Pertanyaan:**  
Jelaskan perbedaan mendasar antara direktif `v-if` dan `v-show` dalam hal siklus hidup komponen (component lifecycle), representasi DOM fisik, serta overhead performa awal (*initial render cost*) versus pergantian visibilitas (*toggle cost*)!

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
1. **Representasi DOM:**
   - `v-if` adalah *conditional rendering* sejati. Ketika kondisi bernilai `false`, elemen atau subtree komponen benar-benar dihancurkan (*unmounted*) dan tidak ada di DOM tree (atau digantikan oleh HTML comment placeholder node `<!--v-if-->`).
   - `v-show` merender elemen ke DOM tree sejak rendering awal tanpa mempedulikan nilai ekspresi boolean, kemudian hanya memodifikasi properti CSS inline `display: none` ketika kondisi bernilai `false`.
2. **Lifecycle:**
   - Komponen anak di dalam `v-if` akan memicu hook `onBeforeMount`/`onMounted` saat kondisi berubah menjadi `true`, dan `onBeforeUnmount`/`onUnmounted` saat kondisi berubah menjadi `false`.
   - Komponen anak di dalam `v-show` di-*mount* sekali pada siklus awal dan tidak pernah di-*unmount* saat disembunyikan.
3. **Karakteristik Biaya (Cost):**
   - `v-if` memiliki *initial render cost* lebih rendah bila kondisi awal bernilai `false` (karena node tidak dibuat), tetapi memiliki *toggle cost* tinggi karena melibatkan alokasi memori, destruksi DOM, dan eksekusi lifecycle hooks.
   - `v-show` memiliki *initial render cost* lebih tinggi (seluruh node diinisialisasi dan di-render), tetapi *toggle cost* sangat murah (hanya mutasi properti CSS).
</details>

---

### Soal 2: Mekanisme Atribut `key` pada `v-for`
**Pertanyaan:**  
Mengapa penggunaan index array (`(item, index) in list` -> `:key="index"`) sangat tidak direkomendasikan pada list yang elemen-elemennya bersifat dinamis (mengalami penambahan, penghapusan, atau pengurutan)? Apa dampaknya terhadap algoritma in-place patch Vue?

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
Secara default, algoritma diffing Vue menggunakan strategi *in-place patch* bila tidak ada `key` unik atau bila `key` yang digunakan adalah indeks urutan numerik:
1. Ketika elemen dihapus di awal array, item pada indeks ke-1 bergeser ke indeks ke-0. Vue mencocokkan VNode lama pada key `0` dengan VNode baru pada key `0`, menganggapnya sebagai elemen yang sama, dan hanya memperbarui properti text/props yang terikat secara reaktif.
2. Jika elemen tersebut memiliki state internal tidak terkontrol (seperti `<input>` HTML murni, CSS state focus/animation, atau temporary component state), state tersebut tidak akan ikut bergeser atau terhapus, melainkan menempel pada data item yang baru menempati indeks tersebut.
3. Penggunaan primary identifier yang stabil dan persisten (misal `item.id` dari database) memastikan VNode diffing algoritma mengenali identitas unik tiap node, memindahkan node DOM fisik ke posisi yang tepat (*reordering*), serta menghancurkan node yang benar-benar dihapus.
</details>

---

### Soal 3: Sintaks Gula (*Syntax Sugar*) `v-model` pada Native Element
**Pertanyaan:**  
Pada elemen input standar `<input v-model="searchText" />`, kode tersebut sebenarnya merupakan sintaks gula untuk kombinasi attribute binding dan event listener apa?

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
Secara default pada `<input type="text">`, kode `<input v-model="searchText" />` dikompilasi menjadi:
```html
<input
  :value="searchText"
  @input="searchText = $event.target.value"
/>
```
*Catatan Tambahan:*  
Vue compiler secara cerdas mengadaptasi implementasi `v-model` bergantung pada elemen target:
- Pada `<input type="checkbox">` atau `<input type="radio">`, v-model mengikat properti `:checked` dan mendengarkan event `@change`.
- Pada elemen `<select>`, v-model mengikat properti `:value` dan mendengarkan event `@change`.
- Dengan modifier `.lazy`, event listener `@input` diubah menjadi `@change`.
</details>

---

### Soal 4: Kerentanan Keamanan pada `v-html`
**Pertanyaan:**  
Apa risiko keamanan kritis saat menggunakan direktif `v-html` untuk menampilkan data dinamis, dan bagaimana mitigasi standar industri yang wajib dilakukan?

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
1. **Risiko Keamanan:**  
   `v-html` melakukan injeksi raw HTML langsung ke dalam elemen DOM melalui properti `innerHTML`. Jika konten tersebut bersumber dari input pengguna (*User-Generated Content*) atau sumber eksternal yang tidak tepercaya, aplikasi rentan terhadap serangan **Cross-Site Scripting (XSS)**. Penyerang dapat menyisipkan payload seperti `<script>`, tag `<img>` dengan handler `onerror`, atau link berbahaya untuk mencuri token sesi (*session hijack*) dan mengeksekusi aksi ilegal atas nama pengguna.
2. **Mitigasi:**
   - Hindari penggunaan `v-html` untuk data pengguna, gunakan interpolasi `{{ text }}` atau `v-text` yang otomatis melakukan HTML escaping.
   - Jika perenderan rich text wajib dilakukan (misal output Markdown editor), lakukan sanitasi ketat di sisi klien maupun server menggunakan pustaka tepercaya seperti **DOMPurify** (`DOMPurify.sanitize(rawHtml)`) sebelum data di-*pass* ke `v-html`.
</details>

---

### Soal 5: Direktif Optimasi `v-once` dan `v-memo`
**Pertanyaan:**  
Jelaskan perbedaan fungsi dan skenario penggunaan antara `v-once` dan `v-memo` pada Vue 3!

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
- **`v-once`:**  
  Merender elemen atau komponen tepat satu kali. Pada rendering ulang berikutnya, elemen beserta seluruh node anaknya diperlakukan sebagai konten statis dan dilewati sepenuhnya oleh algoritma VNode diffing/patching. Digunakan untuk konten bernilai tetap (statis murni) seperti header legal, disclaimer, atau ikon SVG kompleks statis.
- **`v-memo="[dep1, dep2]"` (Vue 3.2+):**  
  Menyediakan memorisasi bersyarat (*conditional memoization*). Subtree hanya akan di-diff dan di-patch ulang jika setidaknya salah satu dependensi dalam array dependensi mengalami perubahan nilai (`dep1 !== prevDep1 || dep2 !== prevDep2`). Jika nilainya identik, seluruh subtree diskip selama proses patch. Sangat berguna untuk optimasi list besar (`v-for`) dengan ribuan baris di mana hanya baris tertentu yang statusnya berubah (misal toggle `isSelected`).
</details>

---

## Bagian B: 5 Intermediate Questions

### Soal 6: Evaluasi Prioritas Compiler `v-if` vs `v-for` di Vue 3
**Pertanyaan:**  
Jelaskan perbedaan hierarki prioritas antara `v-if` dan `v-for` pada Vue 2 versus Vue 3 ketika keduanya dituliskan pada elemen yang sama, dan mengapa pola penulisan tersebut dianggap sebagai *bad practice*?

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
1. **Perubahan Prioritas:**
   - Di **Vue 2**, `v-for` memiliki prioritas lebih tinggi daripada `v-if`. Artinya, perulangan dieksekusi terlebih dahulu, lalu kondisi `v-if` dievaluasi pada setiap iterasi (pemborosan siklus render).
   - Di **Vue 3**, `v-if` memiliki prioritas lebih tinggi daripada `v-for`. Konsekuensinya, kondisi `v-if` dievaluasi sebelum variabel perulangan `v-for` tersedia dalam scope. Jika ekspresi `v-if` merujuk pada variabel lokal `v-for`, compiler akan melemparkan runtime error (*variable is undefined*).
2. **Best Practice:**
   - Jangan pernah menyatukan `v-if` dan `v-for` pada satu elemen yang sama.
   - Jika tujuannya memfilter data, gunakan **`computed` property** untuk menghasilkan list yang sudah terfilter sebelum di-loop.
   - Jika tujuannya menyembunyikan list secara menyeluruh, tempatkan `v-if` pada elemen pembungkus (atau `<template v-if="...">`) di luar elemen `v-for`.
</details>

---

### Soal 7: Lifecycle Hook Custom Directive pada Vue 3
**Pertanyaan:**  
Sebutkan urutan lengkap lifecycle hooks yang tersedia saat membuat custom directive di Vue 3, serta jelaskan parameter yang diterima oleh hook tersebut!

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
1. **Urutan Hook Custom Directive (sejajar dengan component lifecycle):**
   - `created(el, binding, vnode, prevVnode)`: Dipanggil sebelum atribut elemen atau event listeners diterapkan.
   - `beforeMount(el, binding, vnode, prevVnode)`: Dipanggil saat direktif terikat ke elemen, sebelum elemen di-insert ke DOM.
   - `mounted(el, binding, vnode, prevVnode)`: Dipanggil setelah elemen induk dan seluruh child-nya di-mount ke DOM fisik.
   - `beforeUpdate(el, binding, vnode, prevVnode)`: Dipanggil sebelum VNode induk diperbarui.
   - `updated(el, binding, vnode, prevVnode)`: Dipanggil setelah VNode induk dan seluruh child-nya selesai diperbarui.
   - `beforeUnmount(el, binding, vnode, prevVnode)`: Dipanggil sebelum elemen induk di-unmount dari DOM.
   - `unmounted(el, binding, vnode, prevVnode)`: Dipanggil ketika elemen induk telah dihapus dari DOM.
2. **Argumen Utama:**
   - `el`: Elemen DOM fisik aktual yang diikat oleh direktif.
   - `binding`: Objek metadata berisi `{ value, oldValue, arg, modifiers, instance, dir }`.
   - `vnode`: Virtual DOM node yang mendasari elemen target.
   - `prevVnode`: VNode sebelumnya (hanya tersedia pada `beforeUpdate` dan `updated`).
</details>

---

### Soal 8: Custom Multi-Value `v-model` pada Komponen
**Pertanyaan:**  
Bagaimana arsitektur implementasi custom component pada Vue 3 yang mengikat lebih dari satu parameter `v-model` (contoh: `v-model:firstName` dan `v-model:lastName`)? Tuliskan deklarasi `defineProps` dan `defineEmits`-nya!

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
Di Vue 3, argumen pada `v-model:paramName` menggantikan konsep `.sync` modifier pada Vue 2. Komponen child menerima props dengan nama argumen tersebut dan memancarkan event dengan pola `update:argName`.

Implementasi `<script setup>`:
```vue
<script setup lang="ts">
interface Props {
  firstName: string
  lastName: string
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:firstName', value: string): void
  (e: 'update:lastName', value: string): void
}>()

function onFirstNameChange(e: Event) {
  emit('update:firstName', (e.target as HTMLInputElement).value)
}

function onLastNameChange(e: Event) {
  emit('update:lastName', (e.target as HTMLInputElement).value)
}
</script>

<template>
  <div class="name-inputs">
    <input :value="firstName" @input="onFirstNameChange" placeholder="First Name" />
    <input :value="lastName" @input="onLastNameChange" placeholder="Last Name" />
  </div>
</template>
```
</details>

---

### Soal 9: Perilaku Event Modifiers (`.passive`, `.stop`, `.prevent`, `.self`)
**Pertanyaan:**  
Jelaskan dampak teknis modifier `.passive` pada event scroll/touch di mobile browser, dan mengapa modifier `.passive` tidak boleh digabungkan dengan modifier `.prevent`?

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
1. **Dampak Teknis `.passive`:**  
   Browser menjalankan UI rendering thread dan JavaScript execution thread secara terpisah. Ketika pengguna melakukan scroll atau touch, browser biasanya menahan eksekusi scrolling halus (*smooth scrolling*) sampai JavaScript event listener selesai dieksekusi guna memeriksa apakah listener memanggil `event.preventDefault()`. Penambahan modifier `@scroll.passive="onScroll"` secara eksplisit memberi tahu engine browser bahwa handler tidak akan memanggil `preventDefault()`. Hal ini memungkinkan browser langsung mengeksekusi scrolling di thread compositor tanpa lag atau frame drop (60fps scrolling).
2. **Inkompatibilitas dengan `.prevent`:**  
   Modifier `.prevent` otomatis memanggil `event.preventDefault()`. Menggabungkannya dengan `.passive` menghasilkan kontradiksi logika: browser telah diinstruksikan untuk mengabaikan pencegahan default melalui `passive: true`. Jika keduanya dipaksakan, browser akan mengabaikan pemanggilan `preventDefault()` dan mengeluarkan peringatan console (*console warning*).
</details>

---

### Soal 10: Penggunaan Dynamic Arguments pada Directives
**Pertanyaan:**  
Diberikan template berikut:  
`<button @[eventName]="handleAction" :[attrName]="attrValue">Click</button>`  
Apa aturan batasan sintaksis untuk `eventName` dan `attrName`, dan nilai apa yang harus dikembalikan oleh variabel reaktif tersebut jika kita ingin menghapus binding/listener secara dinamis?

<details>
<summary>👉 Lihat Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
1. **Batasan Sintaksis:**
   - Ekspresi dalam kurung siku `[...]` dievaluasi sebagai JavaScript expression dinamis.
   - Tidak boleh mengandung spasi atau karakter kutip (seperti spasi dalam properti objek atau quote string). Jika butuh ekspresi kompleks, gunakan `computed property`.
   - Huruf besar (*uppercase*) pada in-DOM template (HTML murni di browser) akan otomatis diubah menjadi huruf kecil (*lowercased*) oleh parser browser (`:[someAttr]` menjadi `:[someattr]`), sehingga disarankan menggunakan SFC (.vue files).
2. **Penghapusan Binding Dinamis:**
   - Jika nilai variabel reaktif bernilai `null` secara eksplisit, Vue compiler akan menghapus binding attribute atau mencopot event listener tersebut dari elemen DOM fisik. (Nilai selain string atau `null` akan memicu peringatan runtime).
</details>

---

## Bagian C: 3 Skenario Kasus Nyata Produksi

### Kasus 1: Performa Drop & Memory Leaks pada Tab Switcher Kompleks
**Latar Belakang:**  
Sebuah aplikasi web dashboard analitik keuangan menampilkan 8 tab report. Tab ke-3 berisi tabel data transaksi bursa dengan 2.500 baris, pagination internal, form filter, dan integrasi chart SVG. Arsitektur awal menggunakan `v-if` untuk me-render komponen tab yang sedang aktif:
```html
<div class="tab-content">
  <TransactionsTable v-if="activeTab === 'transactions'" />
  <PortfolioOverview v-else-if="activeTab === 'portfolio'" />
  <AnalyticsCharts v-else-if="activeTab === 'charts'" />
  <!-- tab lainnya -->
</div>
```
Pengguna mengeluhkan bahwa saat mereka berpindah dari tab 'transactions' ke tab lain, browser mengalami lag/freeze selama 600-900ms. Ketika mereka kembali ke tab 'transactions', filter input yang sebelumnya diketik hilang dan tabel mengambil waktu lama untuk tampil kembali.

**Tugas Analisis & Solusi:**
1. Identifikasi akar masalah (*root cause*) performa tersebut.
2. Berikan solusi arsitektural menggunakan kombinasi `KeepAlive`, `v-show`, atau virtualisasi.

<details>
<summary>👉 Lihat Solusi Kasus 1</summary>

**Akar Masalah:**
- Penggunaan `v-if` menyebabkan 2.500 node DOM beserta instance komponen anaknya di-unmount, dihancurkan (*destroyed*), dan dibuang ke Garbage Collector saat tab berpindah.
- Saat kembali, proses rekonsiliasi VNode, mounting 2.500 node baru, parsing SVG, dan eksekusi lifecycle hook mengunci JavaScript Main Thread. State lokal komponen juga tereset karena instance baru dibuat dari awal.

**Solusi Arsitektur:**
1. Bungkus komponen dinamis dengan `<KeepAlive>` untuk mempertahankan state dan instance komponen di memori cache tanpa menghancurkan instance saat tab berganti:
```vue
<template>
  <div class="tab-content">
    <KeepAlive :max="5">
      <component :is="currentTabComponent" :key="activeTab" />
    </KeepAlive>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import TransactionsTable from './TransactionsTable.vue'
import PortfolioOverview from './PortfolioOverview.vue'
import AnalyticsCharts from './AnalyticsCharts.vue'

const activeTab = ref('transactions')

const currentTabComponent = computed(() => {
  switch (activeTab.value) {
    case 'transactions': return TransactionsTable
    case 'portfolio': return PortfolioOverview
    case 'charts': return AnalyticsCharts
    default: return null
  }
})
</script>
```
2. Pada `TransactionsTable.vue`, implementasikan virtual scrolling (seperti `@tanstack/vue-virtual`) sehingga hanya ~20 baris yang ada di viewport yang dirender ke DOM fisik, bukan 2.500 baris sekaligus.
</details>

---

### Kasus 2: State Glitch pada List Editing & Reordering
**Latar Belakang:**  
Tim frontend membuat modul daftar tugas (*todo list*) interaktif dengan fitur inline edit nama tugas dan drag-and-drop reordering. Kode ditulis sebagai berikut:
```html
<ul>
  <li v-for="(task, index) in tasks" :key="index">
    <input type="checkbox" :checked="task.completed" @change="toggle(task)" />
    <input type="text" :value="task.title" @input="updateTitle(task, $event)" />
    <button @click="removeTask(index)">Hapus</button>
  </li>
</ul>
```
Ketika pengguna menghapus item pertama dari 3 item, item ke-3 yang terhapus dari tampilan layar secara visual, dan teks input pada baris pertama mempertahankan input yang sedang diketik sebelumnya.

**Tugas Analisis & Solusi:**
1. Jelaskan mengapa bug visual tersebut terjadi secara teknis berdasarkan algoritma DOM diffing.
2. Tunjukkan kode perbaikan yang benar.

<details>
<summary>👉 Lihat Solusi Kasus 2</summary>

**Akar Masalah:**
- Penggunaan `:key="index"` menyebabkan VNode diffing algoritma mengira node dengan key `0` tidak berubah identitasnya saat elemen ke-0 dihapus (elemen ke-1 sekarang menjadi indeks `0`).
- Vue menggunakan strategi *in-place patch*: daripada memindahkan elemen DOM asli, Vue hanya mengupdate props `:value` dan `:checked`. Namun jika elemen input memiliki active focus, uncommitted buffer, atau native DOM state yang belum tersinkronisasi sempurna, DOM fisik tidak di-*rerender* dengan benar, mengakibatkan data pada indeks terakhir yang tampak "hilang" dari DOM.

**Kode Perbaikan:**
Gunakan ID unik stabil dari entity data (misal `task.id` berbasis UUID atau primary key database):
```html
<ul>
  <li v-for="task in tasks" :key="task.id">
    <input 
      type="checkbox" 
      :checked="task.completed" 
      @change="toggle(task)" 
    />
    <input 
      type="text" 
      :value="task.title" 
      @input="updateTitle(task, ($event.target as HTMLInputElement).value)" 
    />
    <button @click="removeTaskById(task.id)">Hapus</button>
  </li>
</ul>
```
</details>

---

### Kasus 3: Memory Leak pada Custom Directive `v-click-outside`
**Latar Belakang:**  
Untuk menangani modal dropdown, developer membuat custom directive global:
```typescript
app.directive('click-outside', {
  mounted(el, binding) {
    document.addEventListener('click', (event) => {
      if (!el.contains(event.target)) {
        binding.value(event)
      }
    })
  }
})
```
Setelah pengguna menggunakan aplikasi seharian (membuka dan menutup ratusan dropdown dalam SPA), konsumsi memori browser meningkat dari 60MB menjadi 1.2GB. Profiling via Chrome DevTools Memory Heap Snapshot menunjukkan ribuan referensi detached HTML nodes tertahan.

**Tugas Analisis & Solusi:**
1. Mengapa terjadi memory leak dan detached DOM tree retention?
2. Tuliskan implementasi custom directive `v-click-outside` yang *leak-free* dan aman untuk produksi!

<details>
<summary>👉 Lihat Solusi Kasus 3</summary>

**Akar Masalah:**
- Closure listener anonim yang didaftarkan pada objek global `document` tidak pernah dilepas saat elemen dropdown di-unmount dari DOM.
- Listener tersebut menahan referensi terhadap `el` (`el.contains`), yang menahan elemen DOM beserta seluruh scope komponen anak di memori (Detached DOM Element), sehingga Garbage Collector tidak dapat mereklamasi alokasi heap memori tersebut.

**Implementasi Leak-Free yang Benar:**
```typescript
import type { Directive, DirectiveBinding } from 'vue'

interface ClickOutsideElement extends HTMLElement {
  __clickOutsideHandler__?: (event: MouseEvent) => void
}

export const vClickOutside: Directive<ClickOutsideElement, (event: MouseEvent) => void> = {
  mounted(el, binding) {
    const handler = (event: MouseEvent) => {
      // Pastikan target event bukan elemen itu sendiri atau child node di dalamnya
      if (el && !el.contains(event.target as Node)) {
        binding.value(event)
      }
    }
    // Simpan referensi fungsi pada DOM node untuk pelepasan nantinya
    el.__clickOutsideHandler__ = handler
    document.addEventListener('click', handler, true) // Gunakan capture phase jika diperlukan
  },

  unmounted(el) {
    if (el.__clickOutsideHandler__) {
      document.removeEventListener('click', el.__clickOutsideHandler__, true)
      delete el.__clickOutsideHandler__
    }
  }
}
```
</details>

---

## Bagian D: 1 Practical Chapter Challenge

### Tantangan: Implementasi Custom Directive `v-debounce-click` & Virtual List Viewer
Buat implementasi custom directive Vue 3 bernama `v-debounce-click` yang menerima delay waktu (default: 300ms) melalui argumen/modifier, serta mampu menonaktifkan klik ganda sebelum jeda waktu berakhir. Lengkapi juga dengan komponen demo yang aman dan siap produksi.

#### Spesifikasi Kebutuhan:
1. Directive dapat digunakan dengan sintaks:
   - `v-debounce-click="submitForm"` (default 300ms)
   - `v-debounce-click:500="submitForm"` (argumen 500ms)
   - `v-debounce-click.immediate="submitForm"` (modifier untuk trigger langsung di awal)
2. Mencegah event bubbling ganda dan membersihkan timer internal saat elemen di-unmount untuk mencegah kebocoran memori.
3. Ditulis dalam TypeScript murni dengan type safety.

#### Solusi Referensi Implementasi:

```typescript
// directives/vDebounceClick.ts
import type { Directive, DirectiveBinding } from 'vue'

interface DebounceElement extends HTMLElement {
  __debounceClickHandler__?: (e: MouseEvent) => void
  __debounceTimer__?: ReturnType<typeof setTimeout> | null
}

export const vDebounceClick: Directive<DebounceElement, (e: MouseEvent) => void> = {
  mounted(el, binding: DirectiveBinding<(e: MouseEvent) => void>) {
    if (typeof binding.value !== 'function') {
      console.warn('[v-debounce-click]: Nilai binding harus berupa fungsi!')
      return
    }

    // Ambil delay dari argumen direktif (misal: v-debounce-click:500)
    const delay = binding.arg ? parseInt(binding.arg, 10) : 300
    const isImmediate = binding.modifiers.immediate ?? false

    el.__debounceTimer__ = null

    el.__debounceClickHandler__ = (event: MouseEvent) => {
      event.preventDefault()

      if (isImmediate) {
        const canExecute = !el.__debounceTimer__
        if (el.__debounceTimer__) {
          clearTimeout(el.__debounceTimer__)
        }

        el.__debounceTimer__ = setTimeout(() => {
          el.__debounceTimer__ = null
        }, delay)

        if (canExecute) {
          binding.value(event)
        }
      } else {
        if (el.__debounceTimer__) {
          clearTimeout(el.__debounceTimer__)
        }

        el.__debounceTimer__ = setTimeout(() => {
          binding.value(event)
          el.__debounceTimer__ = null
        }, delay)
      }
    }

    el.addEventListener('click', el.__debounceClickHandler__)
  },

  unmounted(el) {
    if (el.__debounceTimer__) {
      clearTimeout(el.__debounceTimer__)
      el.__debounceTimer__ = null
    }
    if (el.__debounceClickHandler__) {
      el.removeEventListener('click', el.__debounceClickHandler__)
      delete el.__debounceClickHandler__
    }
  }
}
```

```vue
<!-- components/DebounceDemo.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import { vDebounceClick } from '../directives/vDebounceClick'

const clickCount = ref(0)
const lastExecutedTime = ref('-')

function handlePayment() {
  clickCount.value++
  lastExecutedTime.value = new Date().toLocaleTimeString()
}
</script>

<template>
  <div class="p-6 border rounded-lg max-w-md mx-auto space-y-4">
    <h3 class="text-lg font-bold">Demo v-debounce-click</h3>
    <p>Jumlah Eksekusi Riil: <strong>{{ clickCount }}</strong></p>
    <p>Waktu Terakhir: <strong>{{ lastExecutedTime }}</strong></p>

    <div class="flex gap-2">
      <!-- Uji coba klik cepat bertubi-tubi -->
      <button
        v-debounce-click:600="handlePayment"
        class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
      >
        Bayar Sekarang (Delay 600ms)
      </button>

      <button
        v-debounce-click:1000.immediate="handlePayment"
        class="px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-700"
      >
        Trigger Cepat (Immediate 1000ms)
      </button>
    </div>
  </div>
</template>
```

---

## Bagian E: Checklist Pemahaman Mandiri

Tandai pemahaman Anda setelah menyelesaikan bab ini:

- [ ] **Dasar Directives:** Memahami seluruh built-in directives (`v-bind`, `v-model`, `v-if`, `v-else`, `v-show`, `v-for`, `v-text`, `v-html`, `v-pre`, `v-once`, `v-memo`).
- [ ] **Karakteristik Patching & Diffing:** Mengetahui cara kerja VNode key tracking dan bahaya penggunaan indeks numerik array sebagai key pada mutable list.
- [ ] **Event Modifiers:** Menguasai penggunaan `.prevent`, `.stop`, `.capture`, `.self`, `.once`, dan `.passive` untuk optimasi responsivitas browser.
- [ ] **Two-Way Binding Arsitektur:** Memahami transformasi kompilasi `v-model` pada native inputs dan multiple `v-model:name` pada custom components.
- [ ] **Custom Directives Lifecycle:** Mengetahui siklus hidup custom directive (`created`, `beforeMount`, `mounted`, `beforeUpdate`, `updated`, `beforeUnmount`, `unmounted`) dan cara mencegah memory leak dengan membersihkan event listener/timer di `unmounted`.
- [ ] **Keamanan:** Memahami mitigasi XSS saat bekerja dengan konten dinamis menggunakan sanitizer seperti DOMPurify sebelum diinjeksikan via `v-html`.
