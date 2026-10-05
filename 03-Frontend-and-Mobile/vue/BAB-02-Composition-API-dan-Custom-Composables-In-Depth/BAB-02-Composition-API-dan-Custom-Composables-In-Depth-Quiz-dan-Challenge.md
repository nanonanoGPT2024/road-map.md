# BAB-02-Composition-API-dan-Custom-Composables-In-Depth: Quiz, Challenge, & Knowledge Check

Dokumen evaluasi mandiri ini dirancang untuk menguji penguasaan konsep, mekanisme reaktivitas internal, implementasi custom composable tingkat lanjut, serta penanganan memory leak pada Vue 3 Composition API.

---

## Bagian 1: Basic Questions (5 Pertanyaan)

### 1. Kapan sebaiknya menggunakan `ref()` dibandingkan dengan `reactive()`?
**Jawaban & Penjelasan Teknis:**
- `ref()` membungkus nilai dalam objek reaktif dengan properti `.value` menggunakan `RefImpl` class. Sangat ideal untuk tipe data primitif (`string`, `number`, `boolean`, `null`, `undefined`, `symbol`) serta referensi objek yang butuh diganti secara utuh (re-assigned) tanpa kehilangan reaktivitas.
- `reactive()` menggunakan JavaScript Proxy secara langsung pada objek JavaScript (`Object`, `Array`, `Map`, `Set`). `reactive()` tidak dapat membungkus tipe primitif secara langsung.
- Best practice ekosistem Vue 3 modern cenderung menstandarkan penggunaan `ref()` untuk hampir semua state karena konsistensi mental model: setiap kali nilai dibaca atau dimutasi di `<script>`, developer sadar menggunakan `.value`, serta aman saat di-destructure menggunakan `toRefs()`.

### 2. Mengapa dekonstruksi (destructuring) objek hasil `reactive()` dapat menghilangkan reaktivitas? Bagaimana cara mengatasinya?
**Jawaban & Penjelasan Teknis:**
Ketika mendestruktur properti dari objek `reactive()`:
```ts
const state = reactive({ count: 0, title: 'Dashboard' });
const { count } = state; // Reaktivitas terputus!
```
Variabel `count` sekarang hanya menampung nilai skalar primitif `0` pada saat dekonstruksi dilakukan, bukan referensi Proxy milik `state`. Perubahan pada `state.count` tidak akan memicu reaktivitas pada `count`.

**Solusi:**
Gunakan fungsi utilitas `toRefs()` atau `toRef()` dari `vue`:
```ts
import { reactive, toRefs, toRef } from 'vue';

const state = reactive({ count: 0, title: 'Dashboard' });
const { count, title } = toRefs(state); // count dan title bertipe Ref<T>
// Atau untuk satu properti:
const countRef = toRef(state, 'count');
```
`toRefs` membungkus setiap properti objek proxy ke dalam wrapper `customRef`/`getter-setter` ref yang mempertahankan tautan reaktif dua arah ke objek induknya.

### 3. Apa perbedaan mendasar antara `watch` dan `watchEffect`?
**Jawaban & Penjelasan Teknis:**
- **`watch` (Explicit Dependency Tracking & Lazy Execution):**
  - Hanya melacak dependensi yang didefinisikan secara eksplisit pada argumen pertama (ref, reactive object, array of sources, atau getter function).
  - Berjalan secara *lazy* secara default (callback tidak dieksekusi saat inisialisasi awal, kecuali diberikan opsi `{ immediate: true }`).
  - Menyediakan nilai lama (`oldValue`) dan nilai baru (`newValue`).
- **`watchEffect` (Automatic Dependency Tracking & Immediate Execution):**
  - Melacak secara otomatis reaktivitas setiap state yang dibaca di dalam blok fungsi callback selama siklus sinkron eksekusi.
  - Berjalan secara *immediate* saat pertama kali didefinisikan.
  - Tidak menyediakan argumen `oldValue` secara default karena melacak kombinasi dinamis dari state yang diakses di dalamnya.

### 4. Apa peran `toValue()` (diperkenalkan pada Vue 3.3+) dalam perancangan composable yang fleksibel?
**Jawaban & Penjelasan Teknis:**
`toValue()` menormalisasi input yang bisa berupa nilai statis mentah, `Ref`, atau fungsi getter (`() => value`) menjadi nilai aslinya (*unwrapped value*).
```ts
import { toValue, type MaybeRefOrGetter } from 'vue';

function useDoubled(input: MaybeRefOrGetter<number>) {
  return computed(() => toValue(input) * 2);
}
```
Jika input berupa `ref`, `toValue()` memanggil `unref()`. Jika input berupa fungsi getter, `toValue()` mengeksekusi fungsi tersebut dan mengembalikan nilainya. Ini menyederhanakan signature fungsi composable yang mendukung tipe `MaybeRefOrGetter<T>`.

### 5. Mengapa pemanggilan `onMounted` atau lifecycle hook lainnya di dalam fungsi asinkron (setelah `await`) akan memicu peringatan runtime (*warning*)?
**Jawaban & Penjelasan Teknis:**
Vue melacak instans komponen aktif (`currentInstance`) melalui variabel global internal selama siklus sinkron fungsi `setup()` dijalankan. 
Ketika eksekusi mencapai `await`, eksekusi fungsi ditangguhkan ke event loop microtask queue. Saat microtask selesai dan konteks melanjutkan baris berikutnya, konteks sinkron `setup()` telah selesai dan Vue telah membersihkan `currentInstance = null`. Akibatnya, pemanggilan lifecycle hook setelah `await` kehilangan referensi komponen pemiliknya dan memicu warning:
`[Vue warn]: onMounted is called when there is no active component instance to be associated with.`

---

## Bagian 2: Intermediate Questions (5 Pertanyaan)

### 1. Bagaimana lifecycle listener DOM (misal: `addEventListener`) harus dikelola di dalam custom composable agar tidak menimbulkan *memory leak*?
**Jawaban & Penjelasan Teknis:**
Composable harus bertanggung jawab penuh terhadap side-effect yang dibuatnya.
- Pasang event listener saat inisialisasi atau di dalam `onMounted`.
- Wajib membersihkan event listener menggunakan `removeEventListener` di dalam `onScopeDispose` atau `onUnmounted`.
- Penggunaan `onScopeDispose` lebih dianjurkan daripada `onUnmounted` karena `onScopeDispose` bekerja baik di dalam komponen (lifecycle SFC) maupun di luar komponen jika composable diinisialisasi di dalam `effectScope()` kustom.

```ts
import { onMounted, onScopeDispose } from 'vue';

export function useEventListener(
  target: EventTarget | null | (() => EventTarget | null),
  event: string,
  handler: (e: Event) => void
) {
  const el = typeof target === 'function' ? target() : target;
  if (el) {
    el.addEventListener(event, handler);
    onScopeDispose(() => {
      el.removeEventListener(event, handler);
    });
  }
}
```

### 2. Jelaskan mekanisme `flush: 'post'` vs `flush: 'pre'` vs `flush: 'sync'` pada `watch`/`watchEffect` dan implikasinya terhadap akses DOM Template Ref.
**Jawaban & Penjelasan Teknis:**
- **`flush: 'pre'` (Default untuk `watch` dan `watchEffect`):** Callback dieksekusi sebelum Vue melakukan patch/render DOM komponen. Jika mencoba mengakses Template Ref di dalam callback, nilainya belum diperbarui dengan render cycle terbaru.
- **`flush: 'post'` (atau via alias helper `watchPostEffect`):** Callback ditangguhkan hingga seluruh patch DOM dan update lifecycle komponen selesai dieksekusi pada scheduler tick tersebut. Wajib digunakan jika callback perlu membaca elemen DOM yang baru saja di-render atau mengukur dimensi elemen (bounding client rect).
- **`flush: 'sync'` (or alias helper `watchSyncEffect`):** Callback dieksekusi secara instan dan sinkron tepat saat mutasi state terjadi, memotong antrean scheduler Vue. Jarang digunakan kecuali untuk mutasi state internal yang butuh kepastian integritas data tinggi sebelum scheduler melanjutkan loop berikutnya (hati-hati: dapat menurunkan performa rendering jika sering dipicu).

### 3. Apa fungsi dari `shallowRef()` dan `shallowReactive()`, serta skenario arsitektur apa yang membutuhkan keduanya?
**Jawaban & Penjelasan Teknis:**
- `ref()` dan `reactive()` secara default melakukan konversi reaktif secara mendalam (*deep reactivity*). Setiap nested object di-wrap ke dalam Proxy.
- `shallowRef()` hanya melacak properti `.value`. Mutasi pada properti di dalam `.value` (misal: `state.value.user.name = 'John'`) tidak akan memicu trigger efek reaktif. Trigger hanya terjadi jika seluruh `.value` diganti referensinya (`state.value = { ... }`).
- `shallowReactive()` hanya memproksi properti level pertama (akar) dari objek. Properti turunan/nested tetap berupa objek JS biasa.

**Skenario Penggunaan:**
1. **Third-Party Complex Instances:** Mengintegrasikan library eksternal yang memiliki state internal kompleks (misal: Three.js scenes, Leaflet/Mapbox map instances, Monaco Editor, Chart.js instances). Membungkus objek-objek ini dengan deep proxy akan merusak performa dan sering menimbulkan konflik prototype internal.
2. **Dataset Raksasa Read-Only:** List data besar (ribuan baris) hasil agregasi REST/GraphQL API yang hanya dibaca di UI atau diganti secara utuh saat pagination. `shallowRef` menghemat alokasi memori puluhan ribu Proxy instance.

### 4. Mengapa kita memerlukan `effectScope()` saat membangun arsitektur composable global atau state management kustom?
**Jawaban & Penjelasan Teknis:**
Setiap kali `computed`, `watch`, atau `watchEffect` dipanggil di dalam fungsi `setup()`, Vue secara otomatis mendaftarkan efek-efek tersebut ke dalam *component effect scope*. Ketika komponen di-unmount, semua efek tersebut dibersihkan secara otomatis.
Namun, jika Anda membuat reaktivitas pada level global (singleton composable yang hidup di luar lifecycle komponen atau modul state management mandiri), efek-efek tersebut tidak terikat ke komponen mana pun dan akan tetap aktif di memori (*memory leak*).
Dengan `effectScope(detached?: boolean)`:
```ts
const scope = effectScope();

scope.run(() => {
  const doubled = computed(() => state.count * 2);
  watch(doubled, (val) => console.log(val));
});

// Ketika ingin memusnahkan seluruh computed dan watch di dalam scope:
scope.stop();
```
`effectScope` memungkinkan pengembang mengelompokkan dan memusnahkan sekumpulan reaktivitas sekaligus secara deterministik.

### 5. Bagaimana cara menangani race condition pada asynchronous composable ketika user melakukan request berkali-kali secara cepat?
**Jawaban & Penjelasan Teknis:**
Ada 2 pendekatan utama:
1. **AbortController API:** Membatalkan request network sebelumnya sebelum memulai request baru:
   ```ts
   let currentController: AbortController | null = null;
   async function fetchData(url: string) {
     if (currentController) currentController.abort();
     currentController = new AbortController();
     return fetch(url, { signal: currentController.signal });
   }
   ```
2. **Execution ID / Request Sequence Counter:** Menyimpan sequence ID lokal pada setiap pemanggilan dan memverifikasi apakah response yang kembali masih merupakan sequence terkini sebelum meng-update state reaktif:
   ```ts
   let currentRequestId = 0;
   async function execute() {
     const id = ++currentRequestId;
     loading.value = true;
     const res = await apiCall();
     if (id !== currentRequestId) return; // Abaikan respon basi (stale response)
     data.value = res;
     loading.value = false;
   }
   ```
3. **Menggunakan `onCleanup` / `onWatcherCleanup` (Vue 3.5+):** Membersihkan efek atau membatalkan request saat watcher dipicu kembali sebelum async task selesai.

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 1: Memory Leak Akibat Window Resize Composable pada Dashboard Real-time
**Kasus:**
Sebuah aplikasi analitik menggunakan composable `useWindowSize()` di 15 komponen widget berbeda pada dashboard yang sering ditutup dan dibuka melalui tab navigasi dinamis. Tim DevOps melaporkan penggunaan memori peramban naik dari 120 MB hingga 1.8 GB setelah beberapa jam pemakaian.

**Analisis:**
Implementasi `useWindowSize` lama:
```ts
// KODE BERMASALAH
import { ref } from 'vue';

export function useWindowSize() {
  const width = ref(window.innerWidth);
  const height = ref(window.innerHeight);

  window.addEventListener('resize', () => {
    width.value = window.innerWidth;
    height.value = window.innerHeight;
  });

  return { width, height };
}
```
**Akar Masalah:**
1. Event listener `window.addEventListener('resize', ...)` anonim didaftarkan setiap kali komponen memanggil composable, tanpa pernah memanggil `removeEventListener`.
2. Setiap listener menahan closure referensi `width` dan `height`, mencegah garbage collection pada komponen yang telah di-unmount.
3. Ada multiplikasi listener (jika ada 15 widget, tercipta 15 resize listener terpisah di `window`).

**Solusi Arsitektur:**
Gunakan pembersihan via `onScopeDispose` serta pertimbangkan pola *shared state / singleton listener* jika diinginkan efisiensi maksimal:
```ts
// KODE PERBAIKAN
import { ref, onMounted, onScopeDispose } from 'vue';

export function useWindowSize() {
  const width = ref(window.innerWidth);
  const height = ref(window.innerHeight);

  function handleResize() {
    width.value = window.innerWidth;
    height.value = window.innerHeight;
  }

  onMounted(() => {
    window.addEventListener('resize', handleResize, { passive: true });
  });

  onScopeDispose(() => {
    window.removeEventListener('resize', handleResize);
  });

  return { width, height };
}
```

---

### Skenario 2: Debounced Search Input Mengalami Stale State dan Race Condition
**Kasus:**
Pada halaman pencarian inventaris gudang, pencarian produk menggunakan input teks yang terhubung dengan API backend via composable `useProductSearch()`. User mengetik `"laptop"`, lalu dengan cepat menghapus dan mengetik `"mouse"`. UI sesaat menampilkan daftar mouse, lalu tiba-tiba berubah kembali menampilkan daftar laptop.

**Analisis:**
1. Request untuk kata kunci `"laptop"` memakan waktu respon 800ms di server karena dataset besar.
2. Request untuk kata kunci `"mouse"` hanya memakan waktu 150ms.
3. Respon `"mouse"` tiba lebih dahulu dan merender produk mouse.
4. Respon `"laptop"` yang lambat tiba belakangan dan menimpa state `products.value` dengan hasil laptop (*stale response override*).

**Solusi Arsitektur:**
Kombinasikan `AbortController` dengan `watch` dan debounce:
```ts
import { ref, watch, onScopeDispose, type Ref } from 'vue';

export function useProductSearch(searchQuery: Ref<string>, delayMs = 300) {
  const products = ref<any[]>([]);
  const isLoading = ref(false);
  const error = ref<Error | null>(null);

  let timer: ReturnType<typeof setTimeout> | null = null;
  let abortController: AbortController | null = null;

  async function performFetch(query: string) {
    if (abortController) {
      abortController.abort(); // Batalkan request sebelumnya
    }
    abortController = new AbortController();

    if (!query.trim()) {
      products.value = [];
      isLoading.value = false;
      return;
    }

    isLoading.value = true;
    error.value = null;

    try {
      const response = await fetch(`/api/products?q=${encodeURIComponent(query)}`, {
        signal: abortController.signal
      });
      if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
      const data = await response.json();
      products.value = data;
    } catch (err: any) {
      if (err.name === 'AbortError') {
        // Request dibatalkan dengan sengaja, bukan error operasional
        return;
      }
      error.value = err;
    } finally {
      isLoading.value = false;
    }
  }

  watch(searchQuery, (newQuery) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      performFetch(newQuery);
    }, delayMs);
  }, { immediate: true });

  onScopeDispose(() => {
    if (timer) clearTimeout(timer);
    if (abortController) abortController.abort();
  });

  return { products, isLoading, error };
}
```

---

### Skenario 3: Penurunan Performa Rendering Grid Virtualisasi dengan Pola Deep Reactivity
**Kasus:**
Aplikasi back-office memuat data transaksi keuangan sebanyak 10.000 objek ke dalam state reaktif menggunakan `const transactions = ref<Transaction[]>([])`. Saat data dimasukkan, browser freeze selama 400ms - 800ms. Setiap kali ada satu properti filter diubah, framerate turun drastis di bawah 20 FPS.

**Analisis:**
1. `ref([])` dengan 10.000 elemen yang masing-masing memiliki 25 properti nested menyebabkan Vue mengiterasi seluruh pohon objek secara rekursif untuk membuat ratusan ribu Proxy traps (`get`, `set`).
2. Data transaksi adalah data historis mutlak (*immutable snapshot*), tidak ada manipulasi properti di level sel individual (`transaction[i].status = 'foo'`).

**Solusi Arsitektur:**
Gunakan `shallowRef()` dan bekukan objek menggunakan `Object.freeze()` untuk mencegah overhead Proxy yang tidak dibutuhkan:
```ts
import { shallowRef, triggerRef } from 'vue';

export function useTransactionLedger() {
  // Hanya melacak pergantian array utuh, bukan deep mutation
  const transactions = shallowRef<ReadonlyArray<Transaction>>([]);
  const isLoading = shallowRef(false);

  async function loadData() {
    isLoading.value = true;
    const rawData = await fetchLargeTransactions();
    // Object.freeze memastikan Vue mengabaikan reaktivitas deep
    transactions.value = Object.freeze(rawData);
    isLoading.value = false;
  }

  function updateSingleTransaction(updatedItem: Transaction) {
    // Buat array baru dan ganti referensi shallowRef
    transactions.value = transactions.value.map(item => 
      item.id === updatedItem.id ? Object.freeze({ ...item, ...updatedItem }) : item
    );
  }

  return { transactions, isLoading, loadData, updateSingleTransaction };
}
```

---

## Bagian 4: Practical Chapter Challenge

### Tantangan: Membangun Composable `useAsyncState` Standar Produksi

**Deskripsi Tugas:**
Buat sebuah custom composable mandiri bernama `useAsyncState<T>` yang memenuhi spesifikasi berikut:

1. **Signature & Parameter Fleksibel:**
   - Menerima fungsi asinkron `promiseFactory: (...args: any[]) => Promise<T>`.
   - Menerima `initialState: T`.
   - Menerima opsi:
     - `immediate?: boolean` (default: `true`).
     - `resetOnExecute?: boolean` (kembalikan state ke `initialState` saat request baru dimulai, default: `false`).
     - `onSuccess?: (data: T) => void`.
     - `onError?: (err: Error) => void`.

2. **State Output:**
   - `state: Ref<T>`
   - `isLoading: Ref<boolean>`
   - `isReady: Ref<boolean>`
   - `error: Ref<Error | null>`
   - `execute: (delay?: number, ...args: any[]) => Promise<T | undefined>`

3. **Guardrails & Anti-Leak:**
   - Penanganan pembatalan otomatis (*abort mechanism*) jika `execute()` dipanggil kembali saat request sebelumnya masih berjalan.
   - Menggunakan `onScopeDispose` untuk membatalkan request yang sedang aktif jika komponen penggunanya di-unmount sebelum request selesai.
   - Type-safe penuh dengan generic TypeScript.

### Implementasi Referensi Solusi:

```ts
import { ref, shallowRef, onScopeDispose, type Ref } from 'vue';

export interface UseAsyncStateOptions<T> {
  immediate?: boolean;
  resetOnExecute?: boolean;
  onSuccess?: (data: T) => void;
  onError?: (err: Error) => void;
}

export interface UseAsyncStateReturn<T, Args extends any[]> {
  state: Ref<T>;
  isLoading: Ref<boolean>;
  isReady: Ref<boolean>;
  error: Ref<Error | null>;
  execute: (...args: Args) => Promise<T | undefined>;
  abort: () => void;
}

export function useAsyncState<T, Args extends any[] = []>(
  promiseFactory: (signal: AbortSignal, ...args: Args) => Promise<T>,
  initialState: T,
  options: UseAsyncStateOptions<T> = {}
): UseAsyncStateReturn<T, Args> {
  const {
    immediate = true,
    resetOnExecute = false,
    onSuccess,
    onError
  } = options;

  const state = ref<T>(initialState) as Ref<T>;
  const isLoading = ref<boolean>(false);
  const isReady = ref<boolean>(false);
  const error = shallowRef<Error | null>(null);

  let currentController: AbortController | null = null;

  function abort() {
    if (currentController) {
      currentController.abort();
      currentController = null;
    }
  }

  async function execute(...args: Args): Promise<T | undefined> {
    abort(); // Batalkan task sebelumnya jika sedang running

    currentController = new AbortController();
    const signal = currentController.signal;

    if (resetOnExecute) {
      state.value = initialState;
    }

    isLoading.value = true;
    error.value = null;

    try {
      const result = await promiseFactory(signal, ...args);
      
      // Pastikan bukan aborted sebelum update state
      if (!signal.aborted) {
        state.value = result;
        isReady.value = true;
        isLoading.value = false;
        onSuccess?.(result);
        return result;
      }
    } catch (err: any) {
      if (err.name === 'AbortError' || signal.aborted) {
        return; // Task dibatalkan, jangan set error state
      }
      const actualError = err instanceof Error ? err : new Error(String(err));
      error.value = actualError;
      isLoading.value = false;
      onError?.(actualError);
    } finally {
      if (!signal.aborted) {
        isLoading.value = false;
      }
    }
  }

  if (immediate) {
    // @ts-expect-error args empty on immediate
    execute();
  }

  onScopeDispose(() => {
    abort();
  });

  return {
    state,
    isLoading,
    isReady,
    error,
    execute,
    abort
  };
}
```

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan checklist ini untuk memvalidasi kesiapan Anda sebelum melangkah ke Bab 3:

- [ ] **Dasar Reaktivitas:**
  - [ ] Saya memahami struktur internal `RefImpl` vs Proxy object pada `ref` vs `reactive`.
  - [ ] Saya tahu kapan harus menggunakan `toRef()` dan `toRefs()` untuk mencegah hilangnya reaktivitas saat dekonstruksi.
  - [ ] Saya paham cara kerja `toValue()` dan fleksibilitas tipe `MaybeRefOrGetter<T>`.

- [ ] **Watchers & Lifecycle:**
  - [ ] Saya dapat menentukan kapan harus menggunakan `watch`, `watchEffect`, `watchPostEffect`, dan `watchSyncEffect`.
  - [ ] Saya paham mengapa mendaftarkan lifecycle hook setelah keyword `await` dilarang.
  - [ ] Saya tahu cara membersihkan side-effect di dalam watcher menggunakan parameter `onCleanup` atau `onWatcherCleanup`.

- [ ] **Optimalisasi & Arsitektur Composable:**
  - [ ] Saya menguasai penggunaan `shallowRef` dan `shallowReactive` untuk mencegah overhead memory pada objek pihak ketiga atau dataset raksasa.
  - [ ] Saya memahami penggunaan `onScopeDispose` sebagai best practice pembersihan resource (event listener, interval, socket, abort controller) di dalam composable.
  - [ ] Saya memahami peran `effectScope()` untuk mengisolasi dan memusnahkan sekumpulan reaktivitas pada global/singleton composable.
  - [ ] Saya mampu merancang composable asinkron yang kebal terhadap race condition dan memory leak.
