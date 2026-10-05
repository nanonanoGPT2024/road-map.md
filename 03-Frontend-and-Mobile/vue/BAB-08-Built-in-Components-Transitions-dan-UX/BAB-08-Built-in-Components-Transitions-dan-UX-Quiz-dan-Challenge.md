# BAB-08-Built-in-Components-Transitions-dan-UX: Quiz, Challenge, & Knowledge Check

Dokumen evaluasi mandiri ini dirancang untuk menguji pemahaman konseptual, arsitektural, dan implementasi praktis terkait Built-in Components di Vue 3 (`<Transition>`, `<TransitionGroup>`, `<KeepAlive>`, `<Teleport>`, dan `<Suspense>`).

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1 (Konseptual Transition Hook)
Sebutkan 6 class CSS dasar yang digenerate secara otomatis oleh komponen `<Transition name="fade">` sepanjang siklus hidup animasi elemen, serta jelaskan fase aktif untuk masing-masing class.

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**6 Class CSS:**
1. `fade-enter-from`: Titik awal transisi masuk. Ditambahkan sebelum elemen dimasukkan ke DOM, dihapus 1 frame setelah elemen dimasukkan.
2. `fade-enter-active`: Diterapkan selama seluruh fase masuk. Digunakan untuk mendefinisikan `transition-property`, `duration`, dan `timing-function`.
3. `fade-enter-to`: Titik akhir transisi masuk. Ditambahkan 1 frame setelah elemen dimasukkan (bersamaan saat `fade-enter-from` dihapus), dihapus saat transisi selesai.
4. `fade-leave-from`: Titik awal transisi keluar. Ditambahkan seketika pemicu leave dipanggil.
5. `fade-leave-active`: Diterapkan selama seluruh fase keluar. Digunakan untuk konfigurasi durasi dan easing saat elemen menghilang.
6. `fade-leave-to`: Titik akhir transisi keluar. Ditambahkan 1 frame setelah pemicu leave, dihapus saat animasi selesai dan elemen dicabut dari DOM.
</details>

---

### Soal 2 (Mode Transisi)
Secara default, jika sebuah elemen berganti dengan elemen lain di dalam `<Transition>` (misal via conditional rendering `v-if` / `v-else`), elemen masuk dan elemen keluar akan beranimasi secara simultan. Atribut apa yang digunakan untuk mengatur agar elemen lama keluar terlebih dahulu hingga selesai sebelum elemen baru masuk?

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban:** Atribut `mode="out-in"`.

**Pembahasan:**
Nilai `mode` pada `<Transition>` memiliki dua opsi utama:
- `out-in`: Elemen saat ini keluar terlebih dahulu hingga transisi leave selesai, baru kemudian elemen pengganti di-mount dan menjalankan transisi enter. Mode ini mencegah lonjakan layout (layout shift) pada UI container.
- `in-out`: Elemen baru masuk terlebih dahulu, baru kemudian elemen lama keluar setelah transisi enter selesai.
</details>

---

### Soal 3 (Lifecycle Hooks KeepAlive)
Komponen yang dibungkus oleh `<KeepAlive>` tidak mengalami siklus hidup `unmounted` saat dinonaktifkan dari tampilan. Dua lifecycle hooks apa yang disediakan Vue 3 untuk mendeteksi kapan komponen masuk dan keluar dari status cache aktif?

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban:** `onActivated()` dan `onDeactivated()`.

**Pembahasan:**
- `onActivated`: Dipanggil saat komponen pertama kali di-mount atau ketika komponen yang tersimpan dalam cache dimasukkan kembali ke pohon DOM aktif.
- `onDeactivated`: Dipanggil saat komponen dicopot dari pohon DOM tetapi status internalnya tetap disimpan dalam memori cache `<KeepAlive>`.
</details>

---

### Soal 4 (Teleport Target & Stacking Context)
Apa fungsi utama dari komponen `<Teleport>` dan parameter `to` apa saja yang valid untuk menentukan target mounting?

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
Komponen `<Teleport>` memungkinkan template sub-tree dari suatu komponen di-render pada node DOM lain di luar hierarki DOM induk komponen tersebut, tanpa merusak hubungan hierarki reaktivitas Vue (provide/inject, parent-child props, event emitting tetap utuh).

Target parameter `to` menerima CSS selector string atau referensi node DOM aktual:
- CSS Query Selector: `to="body"`, `to="#modal-root"`, `to=".overlay-portal"`
- DOM Node Expression: `:to="targetElementRef"`
</details>

---

### Soal 5 (TransitionGroup Prasyarat)
Mengapa setiap elemen anak langsung di dalam `<TransitionGroup>` wajib memiliki atribut `key` yang unik dan stabil (bukan index array)?

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
`<TransitionGroup>` memanfaatkan algoritma FLIP (First, Last, Invert, Play) untuk menggerakkan elemen-elemen yang bergeser posisinya saat daftar item dimutasi (ditambah, dihapus, atau diurutkan). Kunci `key` yang stabil dan unik berbasis ID data memungkinkan algoritma diffing Vue melacak identitas elemen DOM secara presisi antar-render. Jika menggunakan index array, mutasi data seperti penambahan item di awal array akan menggeser index semua elemen lain, menyebabkan Vue memperbarui teks in-place alih-alih menggeser posisi fisik node DOM, sehingga transisi perpindahan (`v-move`) gagal dieksekusi.
</details>

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 6 (TransitionGroup FLIP & v-move)
Bagaimana cara kerja class CSS `.list-move` (atau `[name]-move`) pada `<TransitionGroup>`, dan properti CSS apa yang mutlak diperlukan pada elemen leave agar transisi pergeseran elemen di sekitarnya tidak patah (snapping)?

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
Class `.list-move` diterapkan otomatis oleh Vue saat posisi layout elemen berubah akibat mutasi list. Vue menghitung koordinat awal (First), koordinat baru (Last), membalikkan transformasi dengan `transform: translate()` (Invert), lalu menghapus transform secara transisi (Play).

Agar elemen sekitarnya bergeser secara halus saat ada item yang dihapus (leave), elemen yang meninggalkan DOM harus dikeluarkan dari alur normal dokumen (document flow) menggunakan:
```css
.list-leave-active {
  position: absolute;
  /* opsional: width agar elemen tidak menyusut saat absolute */
  width: 100%;
}
```
Tanpa `position: absolute`, elemen yang sedang leave tetap memakan ruang fisik layout hingga transisi selesainya tercapai. Akibatnya, elemen-elemen di bawahnya baru akan "loncat" (snapping) ke posisi baru saat elemen leave benar-benar dihapus dari DOM.
</details>

---

### Soal 7 (LRU Cache Management di KeepAlive)
Jelaskan cara kerja atribut `max`, `include`, dan `exclude` pada `<KeepAlive>`. Jika `max="3"` ditentukan dan pengguna membuka komponen ke-4, bagaimana Vue menentukan komponen mana yang harus dibuang dari memori?

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
- `include`: String, RegExp, atau Array nama komponen yang diizinkan untuk di-cache.
- `exclude`: String, RegExp, atau Array nama komponen yang dilarang untuk di-cache (prioritas lebih tinggi dari `include`).
- `max`: Batas maksimum jumlah instance komponen yang disimpan di memori.

**Mekanisme Eviction:**
Vue menggunakan algoritma **LRU (Least Recently Used)**. Setiap kali komponen diakses atau di-mount, instance tersebut dipindahkan ke posisi paling mutakhir di set cache. Ketika batas `max` terlampaui saat instance baru dimasukkan, instance komponen yang paling lama tidak pernah diakses (berada di ujung terlama antrean LRU) akan dibuang dari cache dan hook `unmounted` pada komponen tersebut akan dipanggil secara permanen.
</details>

---

### Soal 8 (Suspense & Asynchronous Dependencies)
Kondisi apa saja yang menyebabkan komponen `<Suspense>` mengaktifkan slot `#fallback`, dan bagaimana penanganan error (error boundary) dilakukan jika salah satu async dependency di slot `#default` melempar unhandled rejection?

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
Slot `#fallback` diaktifkan ketika salah satu komponen turunan di slot `#default` memiliki async dependency yang belum resolve. Async dependency mencakup:
1. Komponen dengan `async setup()` atau penggunaan top-level `await` di `<script setup>`.
2. Komponen asinkron yang diimpor via `defineAsyncComponent()`.

**Penanganan Error:**
`<Suspense>` sendiri tidak menangkap error. Jika terjadi rejection/error pada async setup, fallback tidak akan berhenti atau aplikasi akan crash kecuali ditangkap oleh hook `onErrorCaptured()` di komponen induk atau error handler global (`app.config.errorHandler`). Komponen induk pembungkus Suspense bertindak sebagai Error Boundary.
</details>

---

### Soal 9 (JavaScript Hooks pada Transition)
Mengapa saat menggunakan JavaScript transition hooks (misal integrasi dengan GSAP) atribut `:css="false"` sangat direkomendasikan pada `<Transition>`, dan apa konsekuensinya jika callback `done` tidak dipanggil pada hook `enter(el, done)` / `leave(el, done)`?

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
1. **Atribut `:css="false"`**:
   Memberitahu Vue untuk mengabaikan deteksi otomatis event CSS (`transitionend` atau `animationend`). Ini menghemat komputasi rendering karena Vue tidak memindai aturan CSS styling elemen dan mencegah interferensi jika ada class CSS lain yang secara tidak sengaja memicu event transition.

2. **Konsekuensi tidak memanggil `done`**:
   Jika transisi berbasis JavaScript tidak menyertakan parameter `done` atau lupa memanggil `done()`, Vue menganggap fase hook masih berjalan. Akibatnya, pada fase leave, node DOM tidak akan pernah dicopot dari memori dan pohon dokumen, menyebabkan memory leak dan kebuntuan rendering.
</details>

---

### Soal 10 (Teleport Disabled Prop & Responsiveness)
Jelaskan use-case teknis dari properti `:disabled` pada `<Teleport>` dan berikan contoh arsitektur UI di mana properti ini sangat bermanfaat.

<details>
<summary>Kunci Jawaban & Pembahasan</summary>

**Jawaban:**
Properti `:disabled="true"` menonaktifkan teleportasi fisik node DOM. Elemen template akan tetap di-mount di posisi hierarki aslinya di dalam komponen induk, bukan dipindahkan ke target selector `to`.

**Use-case Arsitektural:**
*Responsive Modal to Bottom Sheet / Embedded Panel*:
- Pada layar Desktop (`isMobile === false`), modal dipindahkan via Teleport ke `body` (`:disabled="false"`).
- Pada layar Mobile (`isMobile === true`), sidebar filter atau detail panel tetap berada inline di dalam alur scroll komponen utama (`:disabled="true"`). Logika reaktivitas dan state form filter tetap identik tanpa duplikasi kode template.
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 1: Konflik CSS Stacking Context pada Modal & Tooltip
**Masalah Produksi:**
Sebuah dashboard enterprise memiliki table data kompleks dengan overflow scroll horizontal dan baris tabel yang memiliki animasi CSS 3D (`transform: translate3d(0,0,0)`). Developer membuat komponen tooltip dan dialog konfirmasi aksi langsung di dalam baris table (`<tr>`). Ketika dialog dibuka dengan `z-index: 999999`, dialog tersebut terpotong oleh batas container tabel (`overflow: auto`) dan tetap tertutup oleh header tabel yang memiliki `z-index: 10`.

**Tugas Evaluasi:**
1. Jelaskan secara mekanika CSS spesifikasi mengapa `z-index: 999999` gagal menembus batas container tabel.
2. Rancang solusi arsitektural menggunakan `<Teleport>` di Vue 3 untuk mengatasi masalah ini tanpa merusak data binding baris tabel.

<details>
<summary>Solusi Teknis Arsitektural</summary>

1. **Akar Masalah CSS:**
   Properti CSS `transform` (termasuk `translate3d`), `filter`, atau `perspective` yang diterapkan pada elemen induk akan secara otomatis membentuk **Stacking Context baru** dan **Containing Block baru** untuk semua elemen turunan dengan posisi `fixed` atau `absolute`. Nilai `z-index` turunan hanya berlaku di dalam stacking context lokal tersebut dan tidak akan pernah bisa melampaui z-index elemen di luar stacking context induknya. Selain itu, `overflow: auto/hidden` pada induk memotong konten lokal.

2. **Solusi Teleport:**
   Pindahkan mounting DOM dialog konfirmasi langsung ke root dokumen (misal `#modal-target` atau `body`), sambil mempertahankan deklarasi komponen di dalam template baris tabel agar tetap memiliki akses langsung ke closure `row.id` atau emit event baris.

```vue
<!-- TableRow.vue -->
<template>
  <tr>
    <td>{{ row.title }}</td>
    <td>
      <button @click="isConfirmOpen = true">Delete</button>
      
      <!-- Teleport ke root dokumen untuk bypass parent transform & overflow -->
      <Teleport to="#modal-root" v-if="isConfirmOpen">
        <div class="modal-backdrop" @click="isConfirmOpen = false">
          <div class="modal-card" @click.stop>
            <h3>Konfirmasi Hapus</h3>
            <p>Hapus item {{ row.title }} (ID: {{ row.id }})?</p>
            <button @click="executeDelete(row.id)">Konfirmasi</button>
          </div>
        </div>
      </Teleport>
    </td>
  </tr>
</template>
```
</details>

---

### Skenario 2: Memory Leak & Stale Data pada Tab Navigation KeepAlive
**Masalah Produksi:**
Sebuah aplikasi ERP memuat lusinan tab transaksi menggunakan dynamic component `<component :is="currentTab" />` yang dibungkus `<KeepAlive>`. Setelah pengguna bekerja selama 3 jam, tab browser mengalami degradasi performa drastis dan crash karena Out of Memory. Selain itu, saat berpindah dari Tab "Manajemen Order" ke Tab "Laporan Keuangan", data total omzet di Tab Laporan Keuangan tidak pernah diperbarui karena fetch API hanya dijalankan di hook `onMounted`.

**Tugas Evaluasi:**
1. Bagaimana strategi pembatasan memori pada `<KeepAlive>` untuk mencegah memori membengkak tanpa batas?
2. Bagaimana cara merefaktor pemanggilan data fetching agar komponen tetap tersinkronisasi saat tab dibuka kembali tanpa kehilangan input form lokal yang belum disimpan?

<details>
<summary>Solusi Teknis Arsitektural</summary>

1. **Pencegahan Memory Leak:**
   - Tambahkan batas kapasitas cache dengan properti `max="5"` untuk mengaktifkan kebijakan LRU eviction.
   - Gunakan atribut `include` secara eksplisit berbasis whitelist array state tab aktif, bukan men-cache semua komponen acak.

2. **Sinkronisasi Data vs State Form:**
   - Pisahkan inisialisasi state form lokal (yang harus dipertahankan) dari data agregat eksternal (yang harus diperbarui).
   - Gunakan lifecycle hook `onActivated()` untuk memicu background refresh data server, dan hook `onDeactivated()` untuk membatalkan timer aktif atau koneksi WebSocket yang tidak terpakai.

```vue
<!-- FinancialReportTab.vue -->
<script setup>
import { ref, onMounted, onActivated, onDeactivated } from 'vue'

const draftNotes = ref('') // Input lokal yang tidak boleh hilang
const financialData = ref(null)
let pollInterval = null

async function fetchLatestReport() {
  const res = await fetch('/api/reports/live')
  financialData.value = await res.json()
}

onMounted(() => {
  // Hanya inisialisasi awal jika diperlukan
})

onActivated(() => {
  // Selalu segarkan data live saat tab kembali dilihat
  fetchLatestReport()
  pollInterval = setInterval(fetchLatestReport, 15000)
})

onDeactivated(() => {
  // Matikan polling saat tab berada di background agar hemat CPU & network
  if (pollInterval) clearInterval(pollInterval)
})
</script>
```
</details>

---

### Skenario 3: Layout Shift & Flickering pada Animasi Pergantian List Filter
**Masalah Produksi:**
Pada halaman e-commerce produk list, ketika pengguna memilih kategori filter baru, daftar kartu produk mengalami efek "berkedip" (flickering), dan beberapa kartu produk melompat secara tiba-tiba tanpa transisi posisi yang mulus. Inspeksi elemen menunjukkan bahwa item-item kategori lama masih ada di DOM saat item-item kategori baru sudah masuk, sehingga layout grid pecah sementara.

**Tugas Evaluasi:**
1. Apa penyebab terjadinya tabrakan layout pada pergantian massal item list?
2. Buat konfigurasi CSS dan template `<TransitionGroup>` yang tepat untuk memastikan animasi perpindahan (FLIP) berjalan mulus tanpa merusak grid layout.

<details>
<summary>Solusi Teknis Arsitektural</summary>

1. **Penyebab Masalah:**
   Ketika item baru masuk dan item lama keluar bersamaan, keduanya berada di dalam document flow yang sama di dalam container CSS Grid/Flexbox. Item leave mendorong item enter ke bawah hingga waktu leave berakhir. Selain itu, ketiadaan konfigurasi class `-move` mencegah browser menginterpolasi posisi koordinat grid elemen yang bertahan.

2. **Solusi Implementasi CSS & Template:**
```vue
<template>
  <TransitionGroup name="product-grid" tag="div" class="product-container">
    <div 
      v-for="item in filteredProducts" 
      :key="item.id" 
      class="product-card"
    >
      <h4>{{ item.name }}</h4>
      <p>{{ item.price }}</p>
    </div>
  </TransitionGroup>
</template>

<style scoped>
.product-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  position: relative;
}

/* Transisi perubahan posisi untuk elemen yang bertahan */
.product-grid-move {
  transition: all 0.5s cubic-bezier(0.25, 1, 0.5, 1);
}

.product-grid-enter-active,
.product-grid-leave-active {
  transition: all 0.4s ease;
}

.product-grid-enter-from,
.product-grid-leave-to {
  opacity: 0;
  transform: scale(0.8);
}

/* Kunci: Elemen leave harus absolute agar tidak memecah kalkulasi grid item lain */
.product-grid-leave-active {
  position: absolute;
  z-index: 0;
}
</style>
```
</details>

---

## Bagian 4: Practical Chapter Challenge

### Tantangan: "Enterprise Multi-Tab Workspace with KeepAlive, Teleport, & Suspense"

Bangun komponen arsitektur modular Vue 3 SFC (`WorkspaceShell.vue`) yang memadukan seluruh pilar UX Built-in Components dengan kriteria spesifikasi berikut:

1. **KeepAlive Tab System:**
   - Navigasi antar 2 tab: `EditorTab` (memiliki form input) dan `AnalyticsTab` (komponen asinkron).
   - Tab yang aktif dibungkus oleh `<KeepAlive>` dengan `max="3"`.
   - Form input di `EditorTab` tidak boleh ter-reset saat pengguna berpindah ke `AnalyticsTab` dan kembali lagi.

2. **Suspense with Loading Skeleton:**
   - `AnalyticsTab` mensimulasikan pemuatan data asinkron via top-level `await`.
   - Bungkus dynamic tab dengan `<Suspense>` yang menampilkan fallback loading skeleton saat `AnalyticsTab` pertama kali di-resolve.

3. **Smooth View Transitions:**
   - Pergantian tab dianimasikan menggunakan `<Transition>` dengan `mode="out-in"`.

4. **Global Teleported Drawer:**
   - Terdapat tombol "Buka Catatan Global" di workspace header.
   - Panel Drawer di-teleport langsung ke target selector `#workspace-drawer-portal` (atau `body`).
   - Panel drawer memiliki animasi slide-in transisi dari sisi kanan.

### Solusi Kode Komprehensif:

```vue
<!-- WorkspaceShell.vue -->
<script setup>
import { ref, shallowRef, defineAsyncComponent } from 'vue'
import EditorTab from './tabs/EditorTab.vue'

// Simulasi Asynchronous Component untuk Analytics
const AnalyticsTab = defineAsyncComponent(() => 
  new Promise((resolve) => {
    setTimeout(() => {
      resolve(import('./tabs/AnalyticsTab.vue'))
    }, 1200)
  })
)

const activeTabName = ref('EditorTab')
const currentTab = shallowRef(EditorTab)

function switchTab(name, component) {
  activeTabName.value = name
  currentTab.value = component
}

const isDrawerOpen = ref(false)
const globalNotes = ref('')
</script>

<template>
  <div class="workspace-layout">
    <!-- Header Navigasi -->
    <header class="workspace-header">
      <div class="tab-triggers">
        <button 
          :class="{ active: activeTabName === 'EditorTab' }" 
          @click="switchTab('EditorTab', EditorTab)"
        >
          Draft Editor
        </button>
        <button 
          :class="{ active: activeTabName === 'AnalyticsTab' }" 
          @click="switchTab('AnalyticsTab', AnalyticsTab)"
        >
          Realtime Analytics
        </button>
      </div>

      <button class="btn-drawer" @click="isDrawerOpen = !isDrawerOpen">
        Catatan Global
      </button>
    </header>

    <!-- Konten Tab Utama -->
    <main class="workspace-content">
      <Transition name="fade-slide" mode="out-in">
        <Suspense>
          <!-- Slot Default: Komponen Asinkron & Ber-cache -->
          <template #default>
            <KeepAlive :max="3" include="EditorTab,AnalyticsTab">
              <component :is="currentTab" :key="activeTabName" />
            </KeepAlive>
          </template>

          <!-- Slot Fallback: Skeleton Loader -->
          <template #fallback>
            <div class="skeleton-container">
              <div class="skeleton-shimmer bar-title"></div>
              <div class="skeleton-shimmer card-grid"></div>
              <p>Memuat modul asinkron...</p>
            </div>
          </template>
        </Suspense>
      </Transition>
    </main>

    <!-- Teleport Portal untuk Drawer Layer -->
    <Teleport to="body">
      <Transition name="drawer">
        <div v-if="isDrawerOpen" class="drawer-overlay" @click.self="isDrawerOpen = false">
          <aside class="drawer-body">
            <div class="drawer-head">
              <h3>Catatan Global Workspace</h3>
              <button @click="isDrawerOpen = false">×</button>
            </div>
            <textarea 
              v-model="globalNotes" 
              placeholder="Catatan ini di-teleport ke root DOM..."
              rows="12"
            ></textarea>
          </aside>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.workspace-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  font-family: system-ui, sans-serif;
}

.workspace-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background-color: #1e293b;
  color: white;
}

.tab-triggers button {
  background: transparent;
  border: 1px solid #475569;
  color: #94a3b8;
  padding: 8px 16px;
  cursor: pointer;
  border-radius: 4px;
  margin-right: 8px;
}

.tab-triggers button.active {
  background: #3b82f6;
  color: white;
  border-color: #3b82f6;
}

.workspace-content {
  flex: 1;
  padding: 24px;
  position: relative;
  overflow-y: auto;
}

/* Transisi Tab (fade-slide) */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* Transisi Drawer (slide in dari kanan) */
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.3s ease;
}

.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}

.drawer-enter-active .drawer-body,
.drawer-leave-active .drawer-body {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.drawer-enter-from .drawer-body {
  transform: translateX(100%);
}

.drawer-leave-to .drawer-body {
  transform: translateX(100%);
}

.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: flex-end;
  z-index: 10000;
}

.drawer-body {
  width: 360px;
  background: white;
  height: 100%;
  padding: 20px;
  box-sizing: border-box;
}

/* Loading Skeleton */
.skeleton-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.skeleton-shimmer {
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 6px;
}
.bar-title { height: 28px; width: 40%; }
.card-grid { height: 180px; width: 100%; }

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
```

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan checklist ini untuk memverifikasi kesiapan arsitektural sebelum beralih ke BAB berikutnya:

- [ ] Memahami 6 lifecycle CSS class transisi (`*-enter-from`, `*-enter-active`, `*-enter-to`, `*-leave-from`, `*-leave-active`, `*-leave-to`).
- [ ] Mampu mengatasi layout jumping saat transisi antar elemen menggunakan konfigurasi `mode="out-in"`.
- [ ] Menguasai algoritma CSS FLIP pada `<TransitionGroup>` dan mengimplementasikan class `*-move` serta `position: absolute` pada state leave.
- [ ] Mampu mengelola performa memori pada `<KeepAlive>` menggunakan atribut `include`, `exclude`, dan `max` berbasis LRU eviction.
- [ ] Menggunakan lifecycle hook `onActivated()` dan `onDeactivated()` secara tepat untuk menyinkronkan event subscriber, polling, dan live data refresh.
- [ ] Memahami cara kerja `<Teleport>` untuk mengatasi CSS Stacking Context trap (`transform`, `filter`, `overflow: hidden`) pada modal, popover, dan toast.
- [ ] Mampu menggunakan properti `:disabled` pada `<Teleport>` untuk menciptakan pola layout responsif adaptif.
- [ ] Mengetahui cara orkestrasi `<Suspense>` bersama asynchronous component (`defineAsyncComponent`) dan top-level `await` dengan visual loading fallback skeleton.
- [ ] Mengetahui cara menangani error boundary pada komponen asinkron di dalam `<Suspense>` menggunakan `onErrorCaptured()`.
