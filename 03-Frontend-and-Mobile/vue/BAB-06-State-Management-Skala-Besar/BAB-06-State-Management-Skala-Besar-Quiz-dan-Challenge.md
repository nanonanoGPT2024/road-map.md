# BAB-06-State-Management-Skala-Besar: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang untuk menguji, memvalidasi, dan mengonsolidasikan pemahaman arsitektur state management berskala enterprise menggunakan Pinia pada ekosistem Vue 3. Uji pemahaman Anda mencakup teori reaktivitas, modularisasi store, sinkronisasi state terdistribusi, optimasi performa, hingga penanganan skenario crash di lingkungan produksi.

---

## Bagian 1: Basic Questions (5 Pertanyaan Pilihan Ganda/Singkat)

### Soal 1
**Mengapa destrukturisasi langsung pada state Pinia seperti `const { count, user } = useCounterStore()` merusak reaktivitas, dan utilitas apa dari Pinia yang harus digunakan untuk mengatasinya?**

- **A.** Destrukturisasi menghilangkan getter; gunakan `toRaw()`.
- **B.** Destrukturisasi memutus referensi proxy reaktif ES6; gunakan `storeToRefs()`.
- **C.** Pinia menggunakan shallow ref secara default; gunakan `triggerRef()`.
- **D.** Pinia mengharuskan pemanggilan method `clone()`; gunakan `reactive()`.

> **Kunci Jawaban:** **B**  
> **Penjelasan:** Instance store Pinia dibungkus dalam `reactive()`. Ketika Anda mendestrukturisasi property bertipe primitif atau objek dari objek reaktif tanpa helper, Anda hanya mengekstrak nilai mentahnya pada saat itu, bukan referensi reaktifnya. `storeToRefs()` mengekstrak setiap state dan getter sebagai Vue `ref`, sehingga koneksi reaktivitas tetap terjaga tanpa membungkus actions.

---

### Soal 2
**Apa perbedaan arsitektural paling fundamental antara Pinia dan Vuex 4 dalam penanganan mutasi state?**

- **A.** Pinia masih memerlukan `mutations` eksplisit untuk tracking SSR, sedangkan Vuex 4 tidak.
- **B.** Pinia menghapus konsep `mutations` dan mengizinkan mutasi langsung pada state atau melalui `actions` (baik sinkron maupun asinkron).
- **C.** Pinia tidak mendukung async actions; seluruh proses async dialihkan ke composables.
- **D.** Pinia mengisolasi state di Web Worker terpisah secara default.

> **Kunci Jawaban:** **B**  
> **Penjelasan:** Vuex memisahkan mutasi sinkron (`mutations`) dan operasi asinkron (`actions`) untuk keperluan tracking devtools. Pinia mendesain ulang sistem reaktivitasnya menggunakan arsitektur Vue 3 Effect Scope dan Proxy, sehingga mutasi dapat dilakukan langsung via property assignment, `$patch`, atau `actions` sinkron/asinkron tanpa boilerplate mutations.

---

### Soal 3
**Fungsi `$patch` pada Pinia menerima dua bentuk argumen: objek parsial (`{ ... }`) dan fungsi mutator (`(state) => { ... }`). Kapan penggunaan fungsi mutator mutlak direkomendasikan dibanding objek parsial?**

- **A.** Ketika hanya ingin mengubah 1 tipe data string primitif.
- **B.** Ketika melakukan mutasi koleksi kompleks seperti `Array.push()`, `splice()`, atau modifikasi `Set`/`Map`.
- **C.** Ketika mutating state di dalam lifecycle hook `beforeMount`.
- **D.** Ketika store berjalan di lingkungan unit test Vitest.

> **Kunci Jawaban:** **B**  
> **Penjelasan:** Memberikan objek parsial ke `$patch` melakukan iterasi keys dan copy shallow/deep merge sederhana. Jika Anda memanipulasi array (misal menambahkan item), mengirim objek mengharuskan Anda membuat array baru secara penuh (`items: [...state.items, newItem]`). Dengan fungsi callback mutator `store.$patch((state) => { state.items.push(newItem) })`, mutasi in-place array/koleksi dilakukan dalam satu siklus flush reaktivitas yang efisien.

---

### Soal 4
**Manakah pernyataan yang benar mengenai siklus hidup dan pembersihan subscription pada Pinia via `$subscribe` dan `$onAction`?**

- **A.** Subscription Pinia otomatis terhapus saat berpindah halaman meskipun didefinisikan di luar `setup()`.
- **B.** Secara default, subscription yang dipanggil di dalam `setup()` komponen terikat pada instance komponen aktif dan otomatis di-`dispose` saat komponen unmounted.
- **C.** Opsi `{ detached: true }` digunakan agar subscription otomatis mati saat komponen unmount.
- **D.** `$onAction` tidak mendukung penanganan error melalui hook `onError`.

> **Kunci Jawaban:** **B**  
> **Penjelasan:** Pinia mengikat subscription `$subscribe` dan `$onAction` ke scope efek aktif (`effectScope`) dari komponen pemanggil. Begitu komponen unmount, listener otomatis di-detach. Jika developer menginginkan subscription tetap hidup melewati siklus hidup komponen (misal analytics / background sync), opsi `{ detached: true }` harus disematkan.

---

### Soal 5
**Dalam Setup Store (`defineStore('id', () => { ... })`), elemen apa yang merepresentasikan Getter dalam sintaks composable Vue 3?**

- **A.** Variabel `ref()` atau `reactive()`.
- **B.** Fungsi biasa `function doSomething() {}`.
- **C.** Variabel yang dibungkus dengan `computed(() => ...)`.
- **D.** Pemanggilan hook `watchEffect()`.

> **Kunci Jawaban:** **C**  
> **Penjelasan:** Pada Setup Store, `ref()` / `reactive()` merepresentasikan State, `computed()` merepresentasikan Getter, dan fungsi reguler merepresentasikan Actions.

---

## Bagian 2: Intermediate Questions (5 Pertanyaan Analisis & Kode)

### Soal 6
**Perhatikan potongan kode Pinia plugin berikut:**

```typescript
export function piniaAuditPlugin({ store }: PiniaPluginContext) {
  store.$onAction(({ name, args, after, onError }) => {
    const startTime = performance.now();
    console.log(`[ACTION START] ${store.$id}.${name} args:`, args);

    after((result) => {
      console.log(`[ACTION SUCCESS] ${store.$id}.${name} took ${performance.now() - startTime}ms`);
    });

    onError((error) => {
      console.error(`[ACTION ERROR] ${store.$id}.${name} failed:`, error);
    });
  });
}
```

**Jika suatu action melempar rejected Promise (`throw new Error('Network timeout')`), urutan eksekusi callback manakah yang valid?**

- **A.** `[ACTION START]` -> `after` -> `onError`
- **B.** `[ACTION START]` -> `onError` (blok `after` di-skip)
- **C.** `onError` dieksekusi sebelum `[ACTION START]`
- **D.** `after` tetap berjalan dengan nilai `result = undefined`, lalu aplikasi crash.

> **Kunci Jawaban:** **B**  
> **Penjelasan:** Hook `after` hanya dipicu apabila Promise dari action berhasil di-resolve (`fulfilled`). Jika terjadi exception atau rejection, eksekusi melompat langsung ke hook `onError` dan mengabaikan callback `after`.

---

### Soal 7
**Diberikan kasus: Sebuah e-commerce memiliki `cartStore` dan `couponStore`. `cartStore` membutuhkan diskon yang dihitung dari `couponStore`, sedangkan `couponStore` membutuhkan total belanja dari `cartStore` untuk memvalidasi syarat minimum pembelanjaan (circular dependency). Apa solusi arsitektur terbaik di Pinia?**

- **A.** Menggabungkan seluruh aplikasi ke dalam satu root store raksasa tanpa modularisasi.
- **B.** Memanggil `useCartStore()` dan `useCouponStore()` di dalam getter masing-masing pada waktu evaluasi (lazy evaluation di dalam getter/action body), bukan di top-level file store.
- **C.** Menggunakan `window.localStorage` sebagai jembatan pembacaan data antar-store.
- **D.** Memaksa salah satu store menggunakan Vuex dan store lainnya menggunakan Pinia.

> **Kunci Jawaban:** **B**  
> **Penjelasan:** Circular dependency modul JavaScript terjadi jika pemanggilan instansiasi store ditaruh pada top-level module scope (`const other = useOtherStore()`). Di Pinia, store dapat diimpor dan dipanggil langsung di dalam body `getter` atau `action`. Karena getter dievaluasi secara lazy saat dipanggil, referensi siklik tidak akan menyebabkan runtime initialization error (`undefined reference`).

---

### Soal 8
**Perhatikan potongan kode optimasi reaktivitas berikut:**

```typescript
export const useFeedStore = defineStore('feed', () => {
  const largeDataset = ref<Article[]>([]);

  async function fetchFeed() {
    const response = await api.getHeavyArticles();
    // Dataset berisi 10.000 objek kompleks yang sifatnya read-only
    largeDataset.value = markRaw(response.data);
  }

  return { largeDataset, fetchFeed };
});
```

**Apa implikasi teknis penggunaan `markRaw()` pada skenario di atas?**

- **A.** `largeDataset` tidak bisa dirender sama sekali di template Vue.
- **B.** Array `largeDataset.value` tidak dapat diganti lagi dengan array baru.
- **C.** Properti di dalam setiap objek `Article` tidak diubah menjadi Proxy reaktif, menghemat ribuan alokasi memori secara signifikan, namun mutasi internal item (`article.title = 'New'`) tidak akan memicu re-render UI.
- **D.** Menyebabkan memory leak saat komponen Vue unmounted.

> **Kunci Jawaban:** **C**  
> **Penjelasan:** `markRaw()` menandai objek agar tidak pernah dikonversi menjadi reaktif oleh Vue (`reactive()` atau `ref()`). Untuk dataset raksasa (ribuan entri) yang bersifat immutable/read-only, ini menghilangkan overhead deep proxying hingga 80-90% pemakaian memori dan waktu komputasi, selama mutasi granular per property tidak diharapkan mentrigger template update.

---

### Soal 9
**Pada aplikasi SSR (Server-Side Rendering) menggunakan Nuxt 3 / Vue SSR native, apa bahaya mendefinisikan store Pinia di luar fungsi request handler atau mendefinisikan variabel global reaktif di luar `defineStore`?**

- **A.** Data otomatis terenkripsi saat dikirim ke client.
- **B.** Terjadinya State Pollution (kebocoran state lintas pengguna/cross-request state pollution), di mana data User A terbaca oleh User B karena variabel singleton persisten di memori Node.js process.
- **C.** DevTools akan terkunci dalam mode read-only.
- **D.** Node.js akan langsung crash dengan status `SIGSEGV`.

> **Kunci Jawaban:** **B**  
> **Penjelasan:** Di server, satu proses Node.js melayani ribuan request konkuren. Jika state dibuat sebagai singleton di luar konteks request (misal global state tanpa isolasi Pinia instance per request), memori tersebut dipakai bersama oleh seluruh sesi request, memicu kebocoran data sensitif (State Pollution). Pinia mencegah ini dengan mengaitkan store ke instance `app` aktif per HTTP request.

---

### Soal 10
**Bagaimana cara kerja `$reset()` pada Setup Store (`defineStore('id', () => { ... })`) dan bagaimana cara implementasi standar untuk menyediakannya kembali?**

- **A.** `$reset()` langsung tersedia di Setup Store secara bawaan tanpa konfigurasi tambahan.
- **B.** `$reset()` tidak didukung bawaan pada Setup Store karena Pinia tidak mencatat snapshot initial state composable closure; solusinya adalah mendefinisikan fungsi reset kustom manual atau membuat plugin Pinia yang merekam initial state saat store dibuat.
- **C.** `$reset()` dapat dipanggil dengan `store.$state = null`.
- **D.** Setup Store harus di-reload menggunakan `location.reload()`.

> **Kunci Jawaban:** **B**  
> **Penjelasan:** Options Store menyimpan fungsi `state: () => ({ ... })` yang dapat dieksekusi ulang untuk `$reset()`. Pada Setup Store, closures dan refs dinamis dieksekusi saat registrasi, sehingga Pinia tidak memiliki template state awal bawaan. Developer perlu mengekspos fungsi `reset()` kustom atau menyuntikkan plugin `$reset` yang menyalin `deepClone(store.$state)` saat inisialisasi.

---

## Bagian 3: Real-World Enterprise Production Scenarios (3 Kasus Nyata)

---

### Kasus 1: State Inconsistency pada Distributed Tabs & Offline Resilience
**Latar Belakang:**  
Aplikasi Fintech Dashboard memungkinkan pengguna membuka beberapa tab browser secara bersamaan. Pengguna melakukan top-up saldo di Tab A, namun saldo di Tab B tetap menampilkan saldo lama hingga halaman direfresh manual. Selain itu, jika koneksi internet terputus di tengah pengiriman transaksi, aplikasi membeku dan state order berada dalam kondisi ambigu (`pending` selamanya).

**Pertanyaan & Tugas Analisis:**
1. Bagaimana arsitektur sinkronisasi multi-tab yang paling efisien tanpa membebani server backend dengan polling HTTP terus-menerus?
2. Rancang skema state machine untuk menangani status transaksi offline/online resilience.

```
+-----------------------------------------------------------------------------------+
|                            ARSITEKTUR MULTI-TAB & RESILIENCE                      |
|                                                                                   |
|   [ Tab A (Active) ]                 [ Tab B (Passive) ]        [ IndexedDB / LS ]|
|          |                                   |                          |         |
|   1. Action TopUp()                          |                          |         |
|   2. Update Pinia Store                      |                          |         |
|   3. Broadcast Channel  ===================> |                          |         |
|   4. Save Cache snapshot ---------------------------------------------> |         |
|                                              | 5. On Message Received   |         |
|                                              | 6. store.$patch()        |         |
|                                              |    (State Synchronized!) |         |
+-----------------------------------------------------------------------------------+
```

**Solusi & Best Practice Implementasi:**
1. **BroadcastChannel API + Pinia Plugin:**
   - Gunakan `BroadcastChannel('fintech_wallet_sync')`.
   - Buat Pinia plugin yang mengamati perubahan mutasi pada `walletStore`. Setiap kali saldo atau mutasi akun berubah di Tab A, kirim payload payload delta via channel.
   - Tab B mendengarkan event `onmessage` dan melakukan `walletStore.$patch(payload)`, menjaga kedua tab selalu sinkron secara real-time tanpa latensi jaringan backend.
2. **Optimistic UI dengan Rollback State:**
   - Transaksi diberi UUID lokal, status `QUEUED`, dan disimpan ke IndexedDB (via localforage / idb-keyval).
   - Gunakan event listener `navigator.onLine` dan Web Worker / Service Worker Background Sync untuk mengeksekusi ulang antrean transaksi yang tertunda saat koneksi pulih.
   - Jika server menolak (HTTP 4xx/5xx), jalankan action rollback untuk mengembalikan state saldo ke snapshot sebelumnya.

---

### Kasus 2: Memory Leak & Detached DOM Nodes pada Data Streaming Skala Besar
**Latar Belakang:**  
Sebuah aplikasi IoT monitoring memantau 5.000 sensor metrik per detik menggunakan WebSocket. Setelah aplikasi berjalan selama 30 menit, browser mengalami lag hebat (framerate turun ke <10 FPS) dan penggunaan RAM Chrome membengkak dari 150 MB menjadi 2,8 GB. Profiling via Chrome DevTools Memory Heap Snapshot menunjukkan jutaan objek Proxy reaktif dan closure `watch` yang tidak terlepas.

**Analisis Masalah:**
- Seluruh event WebSocket mentah langsung di-`push` ke dalam array reaktif di Pinia store: `readings.value.push(metric)`.
- Komponen grafik mendaftarkan watcher mendalam: `watch(() => store.readings, callback, { deep: true })`.
- Komponen widget dashboard yang sering di-mount dan unmount (saat filter diubah) mendaftarkan listener Pinia `$subscribe({ detached: true })` tanpa pernah memanggil fungsi un-subscribe pembersihnya.

**Solusi Arsitektural:**
1. **Ring Buffer (Circular Buffer) State:**  
   Batasi panjang array data sensor. Jika data melebihi batas maksimum (misal 1.000 titik per sensor), keluarkan data tertua (`shift()` atau implementasikan bounded circular buffer).
2. **Decouple Ingestion Rate dari Render Loop:**  
   Gunakan buffer non-reaktif untuk menampung aliran WebSocket. Lakukan flush ke Pinia store menggunakan `requestAnimationFrame` atau interval berkala (misal tiap 250ms batch update), bukan memicu reaktivitas per 1 millisecond.
3. **Pembersihan Listener & Hindari Deep Watcher:**  
   Ganti deep watch pada array besar dengan derived state atau event emitter spesifik. Pastikan semua subscription terikat pada scope komponen atau simpan teardown function:
   ```typescript
   // On component
   const unsubscribe = metricStore.$onAction(...);
   onUnmounted(() => {
     unsubscribe();
   });
   ```

---

### Kasus 3: SSR Hydration Mismatch & Secure Token Leakage
**Latar Belakang:**  
Aplikasi B2B SaaS menggunakan Vue 3 SSR. Saat halaman pertama kali dimuat, browser melempar warning konsol:  
`Hydration completed but contains mismatches`. Beberapa elemen UI berkedip (flicker) antara tampilan "Guest" dan "User Profile". Lebih buruk lagi, access token rahasia perusahaan bocor ke dalam source HTML publik (`view-source`) pada blok `<script id="__INITIAL_STATE__">`.

**Penyebab:**
- Di server, Pinia store menginisialisasi user profile berdasarkan cookies request. Data dimasukkan utuh ke `store.user = { id, name, role, secretCompanyToken }`.
- State diserialisasikan secara global ke HTML untuk hydration client. Akibatnya, credential sensitif tereskpos di HTML payload publik.
- Client merender komponen sebelum Pinia hydration selesai sempurna atau mengevaluasi kondisi `localStorage` yang tidak ada di server, menyebabkan DOM tree server dan client berbeda.

**Solusi Keamanan & Arsitektur:**
1. **Sanitasi State Serialisasi (Dehydration Hook):**  
   Implementasikan sanitasi payload sebelum disuntikkan ke SSR context. Token otentikasi wajib menggunakan `HttpOnly`, `Secure` cookie, bukan disimpan di dalam state Pinia yang di-serialize ke client payload JSON.
2. **Karantina State Client-Only:**  
   Untuk data yang hanya hidup di client (misal preferensi dark mode dari local storage atau window innerWidth), tandai dan inisialisasi hanya di hook `onMounted()` atau bungkus dengan komponen `<ClientOnly>`.
3. **Hydration Pipeline:**
   ```typescript
   // Server Entry
   const pinia = createPinia();
   app.use(pinia);
   // Serialize hanya state publik
   context.state = sanitizeState(pinia.state.value);

   // Client Entry
   const pinia = createPinia();
   if (window.__INITIAL_STATE__) {
     pinia.state.value = window.__INITIAL_STATE__;
   }
   app.use(pinia);
   ```

---

## Bagian 4: Practical Chapter Challenge

### Tantangan: Bangun Enterprise Order Fulfillment Store dengan Plugin & Undo/Redo

**Instruksi:**  
Tuliskan implementasi lengkap module Pinia TypeScript yang memenuhi kriteria berikut dalam standar kode enterprise:

1. **Setup Store:** Diberi ID `orderFulfillment`.
2. **State & Types:**
   - `orderId: string`
   - `items: Array<{ sku: string; qty: number; unitPrice: number }>`
   - `status: 'DRAFT' | 'PROCESSING' | 'COMPLETED' | 'CANCELLED'`
   - `appliedCoupons: Set<string>`
3. **Getters:**
   - `subtotal`: Jumlah `qty * unitPrice` seluruh item.
   - `itemCount`: Total kuantitas barang.
   - `isLocked`: Boolean (true jika status `COMPLETED` atau `CANCELLED`).
4. **Actions:**
   - `addItem(item: OrderItem): void` (Blokir jika `isLocked` true).
   - `removeItem(sku: string): void`.
   - `applyCoupon(code: string): Promise<boolean>`.
   - `checkout(): Promise<void>`.
5. **Plugin History (Undo/Redo):**
   - Buat plugin mandiri Pinia `createPiniaHistoryPlugin()` yang mampu merekam histori mutasi state (`$subscribe`) dan menyediakan method `$undo()` dan `$redo()` pada store.

```typescript
// ============================================================================
// 1. DEFINISI TIPE & INTERFACE
// ============================================================================
export interface OrderItem {
  sku: string;
  qty: number;
  unitPrice: number;
}

export type OrderStatus = 'DRAFT' | 'PROCESSING' | 'COMPLETED' | 'CANCELLED';

// ============================================================================
// 2. PINIA HISTORY PLUGIN (Undo / Redo Capability)
// ============================================================================
import { PiniaPluginContext } from 'pinia';
import { ref, toRaw } from 'vue';

declare module 'pinia' {
  export interface PiniaCustomProperties {
    $undo: () => void;
    $redo: () => void;
    $canUndo: () => boolean;
    $canRedo: () => boolean;
  }
}

export function createPiniaHistoryPlugin() {
  return ({ store }: PiniaPluginContext) => {
    // Terapkan hanya pada store yang mengaktifkan opsi history
    const historyStack = ref<string[]>([]);
    const forwardStack = ref<string[]>([]);
    let isTraveling = false;

    // Rekam initial state snapshot
    historyStack.value.push(JSON.stringify(toRaw(store.$state)));

    store.$subscribe((mutation, state) => {
      if (isTraveling) return;

      // Catat mutasi baru, reset stack forward
      historyStack.value.push(JSON.stringify(toRaw(state)));
      forwardStack.value = [];

      // Batasi kedalaman undo hingga 20 history
      if (historyStack.value.length > 20) {
        historyStack.value.shift();
      }
    });

    store.$undo = () => {
      if (historyStack.value.length <= 1) return;

      isTraveling = true;
      const currentState = historyStack.value.pop()!;
      forwardStack.value.push(currentState);

      const prevState = JSON.parse(historyStack.value[historyStack.value.length - 1]);
      store.$patch(prevState);
      isTraveling = false;
    };

    store.$redo = () => {
      if (forwardStack.value.length === 0) return;

      isTraveling = true;
      const nextState = forwardStack.value.pop()!;
      historyStack.value.push(nextState);

      store.$patch(JSON.parse(nextState));
      isTraveling = false;
    };

    store.$canUndo = () => historyStack.value.length > 1;
    store.$canRedo = () => forwardStack.value.length > 0;
  };
}

// ============================================================================
// 3. IMPLEMENTASI STORE (Setup Store Pattern)
// ============================================================================
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export const useOrderFulfillmentStore = defineStore('orderFulfillment', () => {
  // State
  const orderId = ref<string>(crypto.randomUUID());
  const items = ref<OrderItem[]>([]);
  const status = ref<OrderStatus>('DRAFT');
  const appliedCoupons = ref<string[]>([]); // Serialized array for reactive reactivity

  // Getters
  const subtotal = computed<number>(() => {
    return items.value.reduce((acc, curr) => acc + curr.qty * curr.unitPrice, 0);
  });

  const itemCount = computed<number>(() => {
    return items.value.reduce((acc, curr) => acc + curr.qty, 0);
  });

  const isLocked = computed<boolean>(() => {
    return status.value === 'COMPLETED' || status.value === 'CANCELLED';
  });

  // Actions
  function assertNotLocked() {
    if (isLocked.value) {
      throw new Error(`Tidak dapat memanipulasi pesanan dalam status ${status.value}`);
    }
  }

  function addItem(newItem: OrderItem) {
    assertNotLocked();
    if (newItem.qty <= 0) throw new Error('Kuantitas barang harus lebih dari 0');

    const existingIndex = items.value.findIndex((i) => i.sku === newItem.sku);
    if (existingIndex > -1) {
      items.value[existingIndex].qty += newItem.qty;
    } else {
      items.value.push({ ...newItem });
    }
  }

  function removeItem(sku: string) {
    assertNotLocked();
    items.value = items.value.filter((i) => i.sku !== sku);
  }

  async function applyCoupon(code: string): Promise<boolean> {
    assertNotLocked();
    const cleanCode = code.trim().toUpperCase();

    if (appliedCoupons.value.includes(cleanCode)) {
      return false;
    }

    // Simulasi verifikasi asynchronous ke API
    if (cleanCode.startsWith('PROMO')) {
      appliedCoupons.value.push(cleanCode);
      return true;
    }

    return false;
  }

  async function checkout() {
    assertNotLocked();
    if (items.value.length === 0) {
      throw new Error('Keranjang belanja kosong');
    }

    status.value = 'PROCESSING';
    try {
      // Mock payment gateway delay
      await new Promise((resolve) => setTimeout(resolve, 800));
      status.value = 'COMPLETED';
    } catch (err) {
      status.value = 'DRAFT';
      throw err;
    }
  }

  function $reset() {
    orderId.value = crypto.randomUUID();
    items.value = [];
    status.value = 'DRAFT';
    appliedCoupons.value = [];
  }

  return {
    // State & Getters
    orderId,
    items,
    status,
    appliedCoupons,
    subtotal,
    itemCount,
    isLocked,
    // Actions
    addItem,
    removeItem,
    applyCoupon,
    checkout,
    $reset,
  };
});
```

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan checklist ini untuk mengaudit kematangan pemahaman arsitektur state management aplikasi Anda sebelum melangkah ke tahap produksi:

| Area Fokus | Indikator Keberhasilan | Status (OK / Perlu Review) |
| :--- | :--- | :---: |
| **Prinsip Dasar Reaktivitas** | Memahami alasan `storeToRefs()` wajib digunakan untuk dekonstruksi state dan getter, serta bahaya hilangnya reaktivitas saat passing direct property. | [ ] |
| **Pola Modularisasi Store** | Memisahkan domain store secara bersih (auth, billing, catalog, UI), dan mengatasi relasi circular cross-store via in-action dynamic imports. | [ ] |
| **Efisiensi Mutasi State** | Mampu membedakan kapan menggunakan direct assignment, `$patch` dengan payload objek, dan `$patch` dengan fungsi callback untuk array/koleksi in-place mutation. | [ ] |
| **Lifecycle & Teardown** | Menguasai siklus hidup `$subscribe` dan `$onAction`, mengaplikasikan auto-cleanup saat unmount, serta memahami implikasi flag `{ detached: true }`. | [ ] |
| **Sistem Ekstensibilitas Plugin** | Mampu menulis custom Pinia Plugin dengan TypeScript typing augmentation (`PiniaCustomProperties`) untuk logging, local persistence, atau undo/redo. | [ ] |
| **Skalabilitas & Memory Performance** | Menggunakan `markRaw()` atau `shallowRef()` untuk data berukuran masif (read-only datasets) dan mampu mendeteksi memory leak akibat uncleaned listeners. | [ ] |
| **Kesiapan Server-Side Rendering (SSR)** | Memahami pencegahan Cross-Request State Pollution di Node.js, mekanisme serialisasi state, dan sanitasi payload untuk mencegah kebocoran secret keys. | [ ] |
