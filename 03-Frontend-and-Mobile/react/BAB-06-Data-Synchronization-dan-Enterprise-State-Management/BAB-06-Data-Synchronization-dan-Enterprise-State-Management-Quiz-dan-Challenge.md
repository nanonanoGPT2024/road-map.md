# BAB-06-Data-Synchronization-dan-Enterprise-State-Management: Quiz, Challenge, & Knowledge Check

Dokumen evaluasi mandiri ini dirancang untuk menguji pemahaman konseptual, arsitektur, dan penanganan kasus teknis tingkat produksi seputar sinkronisasi data server (*Server State*), manajemen *Client State* terdistribusi, strategi invalidasi cache, hingga sinkronisasi data *real-time* dan *offline-first* pada aplikasi React Enterprise.

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1: Perbedaan Mendasar Server State vs Client State
**Pertanyaan:**  
Mengapa arsitektur React modern memisahkan pengelolaan *Server State* (menggunakan library seperti TanStack Query atau RTK Query) dari *Client State* (seperti Zustand atau Redux core)? Sebutkan setidaknya 3 karakteristik pembeda utama!

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban:**  
*Server State* dan *Client State* memiliki siklus hidup (*lifecycle*) dan kepemilikan data yang bertolak belakang:

1. **Kepemilikan & Lokasi Kebenaran (*Single Source of Truth*):**  
   *Server State* dimiliki dan dikendalikan oleh remote server; klien hanya menyimpan *snapshot* atau cache sementara yang sewaktu-waktu bisa usang (*stale*). Sebaliknya, *Client State* (seperti state modal terbuka, form input sementara, atau tema UI) sepenuhnya dimiliki dan dikontrol oleh memori browser klien.
2. **Karakteristik Asinkron & Jaringan:**  
   *Server State* bersifat asinkron dan selalu berhadapan dengan latensi jaringan, error HTTP, retry policy, dan deduplikasi request. *Client State* beroperasi sinkron di dalam memori JavaScript.
3. **Mekanisme Kedaluwarsa (*Staleness & Eviction*):**  
   *Server State* memerlukan strategi invalidasi berkala, background re-fetching saat window focus, dan garbage collection cache (*staleTime* vs *gcTime*). *Client State* bertahan selama sesi aplikasi atau lifecycle komponen tanpa perlu khawatir disinkronkan ke entitas eksternal.

Memisahkan keduanya mencegah "Redux bloat" di mana developer sebelumnya harus menulis ratusan boilerplate action/reducer hanya untuk tracking status `LOADING`, `SUCCESS`, dan `ERROR`.
</details>

---

### Soal 2: `staleTime` vs `gcTime` (Sebelumnya `cacheTime`) pada TanStack Query
**Pertanyaan:**  
Jelaskan perbedaan fungsi mekanis antara konfigurasi `staleTime` dan `gcTime` pada TanStack Query v5! Apa yang terjadi jika `staleTime` diatur ke `5000` (5 detik) dan `gcTime` diatur ke `300000` (5 menit)?

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban:**  
- **`staleTime`:** Durasi (dalam milidetik) data dianggap masih segar (*fresh*). Selama data berstatus *fresh*, re-render komponen yang me-mount query yang sama tidak akan memicu request jaringan di latar belakang (*background refetch*). Setelah durasi ini habis, data bertransisi menjadi *stale*.
- **`gcTime` (Garbage Collection Time):** Durasi data yang tidak aktif (*inactive*, yaitu tidak ada komponen yang me-mount observer query tersebut) tetap dipertahankan di memori sebelum dihapus secara permanen oleh garbage collector TanStack Query.

**Skenario `staleTime: 5000` dan `gcTime: 300000`:**
1. Dalam rentang 5 detik pertama sejak fetch sukses, data berstatus *fresh*. Navigasi kembali ke komponen tersebut menyajikan data instan tanpa fetch ulang.
2. Setelah 5 detik, data dianggap *stale*. Jika ada komponen me-mount query tersebut atau terjadi window focus, data dari memori langsung ditampilkan (SWR - *Stale-While-Revalidate*), lalu network request dikirimkan di background untuk memperbarui data.
3. Jika user meninggalkan halaman (semua subscriber unmount), timer `gcTime` 5 menit mulai berjalan. Jika user tidak kembali dalam 5 menit, cache query dihapus dari memori; fetch berikutnya akan menampilkan status loading dari awal (`isPending: true`).
</details>

---

### Soal 3: Atom vs Slice: Mental Model Jotai/Recoil vs Redux Toolkit
**Pertanyaan:**  
Bagaimana model atomik (*atomic state management* seperti Jotai) bekerja dibandingkan dengan model top-down (*centralized slice* seperti Redux Toolkit)?

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban:**  
- **Top-Down (Centralized Store - RTK/Redux):**  
  State aplikasi disimpan dalam satu pohon objek raksasa (*monolithic state tree*). Data dipecah secara logis ke dalam *slices*. Akses state membutuhkan selector (`useSelector`), dan perubahan state dikirimkan melalui *dispatched actions* yang diproses oleh *reducer pure functions*.
- **Bottom-Up (Atomic State - Jotai/Recoil):**  
  State dipecah menjadi unit-unit reaktif terkecil yang independen (*atoms*). Komponen hanya berlangganan atom spesifik yang diperlukannya. Ketika satu atom berubah nilainya, hanya komponen yang membaca atom tersebut yang me-render ulang tanpa memicu evaluasi selector pohon secara keseluruhan. Atom juga dapat dikomposisikan secara deklaratif (*derived/computed atoms*).

Model atomik sangat unggul untuk UI interaktif dinamis dengan ribuan elemen independen (seperti kanvas diagram, spreadsheet, atau visualizer grafik).
</details>

---

### Soal 4: Struktur Query Keys Dinamis dan Invalidation Hierarki
**Pertanyaan:**  
Diberikan Query Key berikut pada TanStack Query:
```ts
const userTodoQueryKey = ['todos', 'detail', userId, { filter: 'completed' }];
```
Bagaimana cara melakukan invalidasi cache agar mencakup seluruh item `'todos'` milik seorang `userId` tanpa harus menginvalidsasi data milik user lain?

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban:**  
TanStack Query melakukan pencocokan key secara hierarki dari kiri ke kanan (*fuzzy matching* secara default). Anda dapat memanggil `queryClient.invalidateQueries` dengan prefix array query key:

```ts
queryClient.invalidateQueries({
  queryKey: ['todos', 'detail', userId],
});
```

Perintah di atas akan mencocokkan dan menginvalidasi seluruh query key yang diawali dengan `['todos', 'detail', userId, ...]`, mencakup variasi `{ filter: 'completed' }`, `{ filter: 'all' }`, maupun tanpa filter tambahan, namun **tidak** akan menyentuh `['todos', 'detail', otherUserId, ...]`.
</details>

---

### Soal 5: Konsep Dasar Optimistic Updates
**Pertanyaan:**  
Apa yang dimaksud dengan *Optimistic Updates* dalam arsitektur data synchronization, dan siklus 3 langkah apa yang wajib diterapkan untuk mencegah desinkronisasi UI saat terjadi *network failure*?

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban:**  
*Optimistic Updates* adalah teknik pembaruan UI seketika sebelum server memberikan respons resmi atas mutasi HTTP/RPC, dengan asumsi bahwa permintaan jaringan kemungkinan besar berhasil, guna memberikan latensi interaksi mendekati nol (0ms).

**Siklus 3 Langkah Penanganan Wajib:**
1. **Cancel & Snapshot (`onMutate`):**  
   Batalkan semua *outgoing refetches* pada query terkait agar tidak menimpa state optimis, lalu simpan snapshot data terkini (*previous data*) ke dalam konteks sebagai mekanisme rollback. Terapkan data baru langsung ke cache.
2. **Rollback (`onError`):**  
   Jika mutasi gagal (status code 4xx/5xx atau timeout), pulihkan state cache menggunakan snapshot *previous data* yang disimpan pada tahap pertama, lalu tampilkan notifikasi kegagalan kepada user.
3. **Settled Invalidation (`onSettled`):**  
   Baik mutasi berhasil ataupun gagal, lakukan `queryClient.invalidateQueries` untuk memastikan klien tersinkronisasi 100% dengan kondisi database server yang sebenarnya.
</details>

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 6: Race Condition Penanganan Pagination / Rapid Tab Switching
**Pertanyaan:**  
Pada aplikasi katalog produk, user melakukan klik cepat antar tab kategori: Kategori A -> Kategori B -> Kategori C. Jika request untuk Kategori A memakan waktu 2000ms dan Kategori C selesai dalam 400ms, bagaimana cara mencegah *race condition* di mana respons lambat Kategori A menimpa data Kategori C? Bandingkan solusi menggunakan raw `useEffect` vs TanStack Query!

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban:**  
**1. Pada Raw `useEffect`:**  
Terjadi *race condition* karena *closure stale* saat promise Kategori A resolve setelah Kategori C selesai. Solusinya adalah menggunakan flag boolean pembersih atau standar browser `AbortController`:
```ts
useEffect(() => {
  const abortController = new AbortController();

  fetchProducts(category, { signal: abortController.signal })
    .then((data) => setProducts(data))
    .catch((err) => {
      if (err.name !== 'AbortError') handleGenericError(err);
    });

  return () => {
    // Membatalkan request sebelumnya jika category berubah sebelum fetch selesai
    abortController.abort();
  };
}, [category]);
```

**2. Pada TanStack Query:**  
TanStack Query menyelesaikan ini secara *out-of-the-box* dengan mengasosiasikan query key dengan status observer. Ketika query key berubah dari `['products', 'A']` ke `['products', 'C']`:
- Observer berpindah ke query key C. Respons data query key A yang tiba terlambat hanya disimpan ke dalam cache key A tanpa memicu pembaruan state pada komponen kategori C.
- TanStack Query juga menyuntikkan `AbortSignal` ke dalam `QueryFunctionContext` (`queryFn: ({ signal }) => fetch(..., { signal })`), sehingga request A otomatis di-*abort* pada level HTTP jika tidak ada observer aktif lain.
</details>

---

### Soal 7: Selective Subscription & Shallow Equality pada Zustand
**Pertanyaan:**  
Perhatikan cuplikan store Zustand berikut:
```ts
interface AppState {
  theme: 'light' | 'dark';
  sidebarOpen: boolean;
  user: { id: string; name: string; avatar: string };
  setTheme: (t: 'light' | 'dark') => void;
  toggleSidebar: () => void;
}
```
Jika sebuah komponen tombol Navbar hanya ingin memicu `toggleSidebar` dan membaca nilai `sidebarOpen`, bagaimana implementasi pemanggilan hook yang benar agar komponen **tidak** me-render ulang saat properti `user` atau `theme` berubah? Jelaskan peran `useShallow`!

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban:**  
Jika kita menulis:
```tsx
// SALAH: Mengambil seluruh store atau membuat objek baru tanpa shallow comparator
const { sidebarOpen, toggleSidebar } = useAppStore(); // Re-render pada SEMUA perubahan state!
```
Setiap properti dalam store berubah (misalnya `user` di-fetch), komponen akan me-render ulang karena referensi store berubah.

**Solusi 1: Granular Selector Terpisah (Best Practice)**
```tsx
const sidebarOpen = useAppStore((state) => state.sidebarOpen);
const toggleSidebar = useAppStore((state) => state.toggleSidebar);
```
Komponen hanya berlangganan nilai primitif `sidebarOpen` dan referensi fungsi `toggleSidebar` yang stabil.

**Solusi 2: Multi-Property Selector dengan `useShallow` (Zustand v4/v5)**
```tsx
import { useShallow } from 'zustand/react/shallow';

const { sidebarOpen, toggleSidebar } = useAppStore(
  useShallow((state) => ({
    sidebarOpen: state.sidebarOpen,
    toggleSidebar: state.toggleSidebar,
  }))
);
```
Selector mengembalikan objek baru, tetapi `useShallow` melakukan komparasi dangkal (*shallow comparison* level 1) antar properti objek. Karena `sidebarOpen` bernilai boolean yang sama dan `toggleSidebar` stabil, re-render diabaikan meskipun `user` atau `theme` berubah.
</details>

---

### Soal 8: Infinite Query Pagination & Bidirectional Windowing
**Pertanyaan:**  
Ketika mengimplementasikan `useInfiniteQuery` pada feed data besar, mengapa *unconstrained pagination* (terus menambah page ke memory tanpa batas) menyebabkan degradasi performa pada React? Parameter apa yang disediakan TanStack Query v5 untuk membatasi ukuran halaman di memori, dan bagaimana cara kerjanya?

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban:**  
- **Penyebab Masalah:**  
  Setiap halaman baru yang diambil ditambahkan ke array `data.pages`. Jika user melakukan scroll hingga 100 halaman, React harus menyimpan puluhan ribu node DOM dan objek JavaScript di memori. Akibatnya terjadi lonjakan memori (heap bloat) dan FPS anjlok drastis saat terjadi rekonsiliasi VDOM.
- **Solusi TanStack Query v5:** Parameter **`maxPages`**:
  ```ts
  useInfiniteQuery({
    queryKey: ['feed'],
    queryFn: fetchFeedPage,
    initialPageParam: 1,
    getNextPageParam: (lastPage) => lastPage.nextCursor,
    getPreviousPageParam: (firstPage) => firstPage.prevCursor,
    maxPages: 5, // Mempertahankan maksimal 5 halaman di memori
  });
  ```
- **Cara Kerja:**  
  Ketika halaman ke-6 di-fetch via `fetchNextPage()`, TanStack Query secara otomatis menghapus halaman pertama (halaman paling awal) dari array `pages`. Jika user melakukan scroll balik ke atas, `fetchPreviousPage()` dipanggil menggunakan `getPreviousPageParam` untuk memuat kembali data atas secara dua arah (*bidirectional windowing*). Dipadukan dengan virtualisasi DOM (misal `@tanstack/react-virtual`), ukuran memori dan node DOM tetap konstan terlepas dari sejauh mana user melakukan scroll.
</details>

---

### Soal 9: Normalisasi Relasional Normalizr / RTK `createEntityAdapter`
**Pertanyaan:**  
Mengapa struktur state terdenormalisasi (nested array of objects seperti `{ posts: [{ id: 1, author: { id: 99, name: 'Alice' }, comments: [...] }] }`) bermasalah pada aplikasi skala enterprise? Bagaimana `createEntityAdapter` pada Redux Toolkit menyelesaikan problem ini?

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban:**  
**Permasalahan State Bersarang (Nested State):**
1. **Duplikasi Data:** Jika profil `Alice` muncul di 10 post dan 5 komentar berbeda, update nama Alice mengharuskan traversal rekursif ke seluruh tree untuk memperbarui setiap referensi.
2. **Kompleksitas Reducer:** Mutasi objek bersarang dalam format immutable membutuhkan spread operator multi-level yang rawan bug dan sulit dibaca.
3. **Accidental Re-renders:** Komponen yang hanya tertarik pada metadata post akan ikut me-render ulang ketika satu komentar anak mengalami perubahan.

**Solusi `createEntityAdapter`:**  
Mengubah bentuk data ke struktur terindeks (*normalized lookup table*) mirip struktur database relasional:
```ts
{
  ids: [1, 2],
  entities: {
    1: { id: 1, authorId: 99, commentIds: [101, 102] },
    2: { id: 2, authorId: 99, commentIds: [] }
  }
}
```
Manfaat utama:
- Operasi CRUD (insert, update, delete) menjadi $O(1)$ berdasarkan ID tanpa loop array ($O(N)$).
- RTK `createEntityAdapter` menyediakan selektor bawaan (`selectAll`, `selectById`, `selectIds`) yang teroptimasi memoizasi secara otomatis.
</details>

---

### Soal 10: Server-Sent Events (SSE) & WebSocket Bridge ke Query Cache
**Pertanyaan:**  
Jelaskan pola arsitektur untuk menjembatani stream event WebSocket/SSE ke dalam cache TanStack Query tanpa menyebabkan *over-fetching* akibat pemanggilan `invalidateQueries` secara membabi-buta!

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

**Jawaban:**  
Pola arsitektur terbaik adalah **Event-Driven Targeted Cache Mutation** melalui `queryClient.setQueryData`:

1. **Inisialisasi Koneksi Global:**  
   Buka koneksi WebSocket/SSE pada level service singleton atau hook top-level (`useWebSocketSync`).
2. **Kategorisasi Payload Event:**  
   Bagi tipe pesan event dari backend ke dalam dua kategori:
   - **Full Entity / Patch Payload:** Backend menyertakan detail entitas yang berubah (misal `{ type: 'TASK_UPDATED', payload: { id: '42', status: 'COMPLETED' } }`).
   - **Invalidation Flag Only:** Backend hanya memberi tahu bahwa ada perubahan tanpa data detail (misal `{ type: 'METRICS_REFRESH' }`).
3. **Penerapan ke Cache:**
   - Untuk tipe patch entitas: Gunakan `queryClient.setQueryData` untuk memutasi item langsung di dalam cache secara sinkron tanpa query jaringan baru:
     ```ts
     socket.on('TASK_UPDATED', (updatedTask) => {
       queryClient.setQueryData<Task[]>(['tasks'], (oldTasks = []) =>
         oldTasks.map((t) => (t.id === updatedTask.id ? { ...t, ...updatedTask } : t))
       );
       queryClient.setQueryData(['task', updatedTask.id], updatedTask);
     });
     ```
   - Untuk data agregat atau relasi rumit: Gunakan *throttled / debounced* `queryClient.invalidateQueries` agar 50 event masuk dalam 1 detik hanya memicu 1 kali re-fetch ke server.
</details>

---

## Bagian 3: Real-World Production Scenarios (3 Kasus)

### Skenario 1: Problem "Cache Thundering Herd" pada Real-Time Trading Dashboard
**Deskripsi Masalah:**  
Sebuah platform pertukaran aset kripto memiliki dashboard yang menampilkan 10 widget berbeda (order book, mini chart, summary header, transaction history, dll.). Masing-masing widget me-mount hook kustom yang memanggil data akun user:
```ts
// Terpasang di 10 komponen terpisah di layar yang sama
const { data: userProfile } = useQuery({
  queryKey: ['user', 'profile'],
  queryFn: fetchUserProfile,
  staleTime: 0,
});
```
Ketika sistem melakukan broadcast WebSocket yang memicu `queryClient.invalidateQueries({ queryKey: ['user', 'profile'] })`, terjadi lonjakan 10 HTTP GET request simultan ke endpoint `/api/user/profile`, menyebabkan rate-limiting (HTTP 429) dari API Gateway.

**Tugas Analisis & Solusi:**
1. Mengapa TanStack Query mengeksekusi multiple HTTP request padahal query key-nya identik?
2. Bagaimana strategi konfigurasi cache dan *request deduplication* yang harus diterapkan untuk menjamin hanya ada tepat 1 HTTP request yang terbang ke server?

<details>
<summary><b>Analisis & Solusi Teknis</b></summary>

**Akar Masalah:**  
TanStack Query secara internal memiliki mekanisme *request deduplication* otomatis untuk query key yang sama. Namun, jika request dieksekusi saat cache berstatus `staleTime: 0` dan terjadi trigger event eksternal yang di-broadcast tanpa batching, atau jika `queryFn` membungkus promise baru tanpa pembagian instance promise yang tepat, komponen yang unmount/remount secara cepat dapat memicu siklus ganda. Namun penyebab paling sering pada kasus di atas adalah **pemanggilan invalidasi query yang tidak ter-batch atau instansiasi queryClient yang dibuat di dalam bodi komponen React tanpa `useRef` / `useState`** (sehingga QueryClient ter-reset di tiap render).

**Solusi Teknis:**
1. **Pastikan QueryClient Singleton:**  
   Pastikan instance `QueryClient` diinisialisasi sekali di luar komponen root atau diikat dengan `useState(() => new QueryClient())`.
2. **Konfigurasi `staleTime` yang Rasional:**  
   Hindari `staleTime: 0` jika data bersifat real-time via WebSocket. Atur `staleTime: 30_000` (30 detik). Saat ada data baru dari WebSocket, lakukan mutasi langsung dengan `setQueryData` alih-alih `invalidateQueries`.
3. **Throttled Batch Invalidation:**  
   Jika backend mengirimkan sinyal invalidasi berkali-kali dalam hitungan milidetik, gunakan lodash throttle/debounce pada invalidator:
   ```ts
   const debouncedInvalidate = debounce(() => {
     queryClient.invalidateQueries({
       queryKey: ['user', 'profile'],
       refetchType: 'active', // Hanya refetch observer yang sedang aktif di layar
     });
   }, 300);
   ```
4. **Validasi Request Deduplication:**  
   TanStack Query akan membagi 1 promise yang sama ke 10 widget sekaligus jika dipicu secara bersamaan, sehingga hanya ada 1 request di Network tab browser.
</details>

---

### Skenario 2: Desinkronisasi Offline-First & Konflik Data Multi-Tab (CRDT/Vector Clock vs Last-Write-Wins)
**Deskripsi Masalah:**  
Sebuah aplikasi ERP pergudangan digunakan oleh operator lapangan di area yang sinyal internetnya sering hilang. Operator membuka aplikasi di Tab A (desktop) dan Tab B (tablet). 
- Di Tab A, saat offline, operator mengedit kuantitas item SKU-101 dari `100` menjadi `80`.
- Di Tab B, saat masih online, operator lain mengedit kuantitas item SKU-101 dari `100` menjadi `95`.
Ketika Tab A kembali mendapatkan koneksi internet, mutasi offline yang tersimpan di IndexedDB dikirimkan ke server. Server saat ini menggunakan strategi *Last-Write-Wins* (LWW) murni berdasarkan timestamp perangkat klien. Akibatnya, nilai Tab A menimpa nilai Tab B, menghapus mutasi 15 unit yang sah.

**Tugas Analisis & Solusi:**
1. Jelaskan mengapa strategi *Last-Write-Wins* berbasis *client timestamp* sangat berbahaya pada aplikasi enterprise offline-first!
2. Rancang arsitektur sinkronisasi mutasi menggunakan *Optimistic Locking* dengan *Entity Versioning* atau *Delta Operations* untuk mencegah korupsi data!

<details>
<summary><b>Analisis & Solusi Teknis</b></summary>

**Analisis Bahaya LWW Berbasis Client Timestamp:**  
Jam perangkat klien (*client clock*) tidak dapat dipercaya karena rentan terhadap *clock drift*, manipulasi waktu oleh user, dan perbedaan zona waktu. Lebih fatal lagi, LWW memperlakukan seluruh baris data sebagai atomik tunggal (*coarse-grained*), menimpa seluruh field meskipun operator hanya mengubah kuantitas parsial.

**Rancangan Solusi Arsitektur:**

1. **Optimistic Locking via Version Header (`If-Match` / `version` field):**  
   Setiap entitas SKU memiliki nomor versi monotonik (`version: 4`).
   - Ketika Tab A melakukan mutasi, payload memuat `{ id: 'SKU-101', quantity: 80, expectedVersion: 4 }`.
   - Karena Tab B telah mengubah versi menjadi `5`, server menolak permintaan Tab A dengan status code `HTTP 409 Conflict`.

2. **Transformasi ke Delta Mutation (Intent-based Updates):**  
   Alih-alih mengirimkan status mutlak (`quantity = 80`), kirimkan operasi diferensial matematis (*delta*):
   ```json
   {
     "op": "ADJUST_STOCK",
     "skuId": "SKU-101",
     "delta": -20,
     "clientMutationId": "uuid-v4-tab-a",
     "timestampUtc": "2026-10-05T04:40:00Z"
   }
   ```
   Server memproses operasi ini sebagai event log:
   - Initial: 100
   - Tab B (delta -5): 95
   - Tab A masuk dari antrean offline (delta -20): 95 - 20 = 75 (Data konsisten tanpa data loss!).

3. **Client-Side Queue Management:**  
   Gunakan plugin persisten TanStack Query (`persistQueryClient` + `createAsyncStoragePersister` menggunakan `idb-keyval`). Tempatkan mutasi ke dalam antrean *outbox* offline. Jika server mengembalikan `HTTP 409`, picu UI rekonsiliasi manual (*Conflict Resolution Modal*) agar operator dapat memilih merger data.
</details>

---

### Skenario 3: Memory Leak Akibat Zombie Subscribers pada Custom State Store
**Deskripsi Masalah:**  
Sebuah tim frontend membuat custom global state store sederhana berbasis publish-subscribe dengan React `useSyncExternalStore` untuk menghindari dependensi eksternal. Namun setelah aplikasi beroperasi selama 3 jam, tab browser crash dengan error `Out of Memory` (JavaScript Heap > 1.8 GB). Analisis memory heap snapshot menunjukkan jutaan closure fungsi subscriber tertahan di memori meskipun komponen pemanggilnya sudah di-unmount berminggu-minggu lalu.

```ts
// Custom Store Implementation yang dibuat tim
export function createCustomStore<T>(initialState: T) {
  let state = initialState;
  const listeners = new Set<() => void>();

  return {
    getState: () => state,
    setState: (fn: (prev: T) => T) => {
      state = fn(state);
      listeners.forEach((listener) => listener());
    },
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      // Bug tersembunyi di sini!
    },
  };
}
```

**Tugas Analisis & Solusi:**
1. Temukan letak kesalahan pada fungsi `subscribe` dan jelaskan bagaimana integrasi dengan `useSyncExternalStore` menyebabkan *zombie memory retention*.
2. Tuliskan implementasi perbaikan fungsi `createCustomStore` yang benar dan aman dari *memory leak*.

<details>
<summary><b>Analisis & Solusi Teknis</b></summary>

**Akar Masalah:**  
Fungsi `subscribe` pada kontrak `useSyncExternalStore(store.subscribe, store.getState)` **wajib mengembalikan fungsi cleanup** (pembersih unsubscribe) dengan tipe `() => void`. 

Pada implementasi di atas:
- `subscribe` tidak mengembalikan fungsi apapun (`undefined`).
- Ketika komponen React unmount, React memanggil fungsi cleanup yang seharusnya meng-unregister listener. Karena tidak ada fungsi yang dikembalikan, referensi callback listener tetap tersimpan di dalam `listeners = new Set()`.
- Karena closure listener tersebut mengikat scope VDOM komponen yang sudah unmount (komponen beserta state lokal dan DOM references), Garbage Collector tidak dapat mereklamasi memori komponen tersebut (*Zombie Subscriber*). Setiap kali komponen di-mount ulang, listener baru terus bertambah tanpa pernah dihapus.

**Implementasi Perbaikan yang Benar:**

```ts
export function createCustomStore<T>(initialState: T) {
  let state = initialState;
  const listeners = new Set<() => void>();

  return {
    getState: () => state,
    setState: (updater: T | ((prev: T) => T)) => {
      state = typeof updater === 'function' 
        ? (updater as (prev: T) => T)(state) 
        : updater;
      // Iterasi salinan Set untuk menghindari issues jika listener memodifikasi Set saat berjalan
      listeners.forEach((listener) => listener());
    },
    subscribe: (listener: () => void): (() => void) => {
      listeners.add(listener);
      
      // WAJIB: Mengembalikan fungsi pembersih untuk mencabut listener dari Set
      return () => {
        listeners.delete(listener);
      };
    },
  };
}
```
Ketika dihubungkan ke React via `useSyncExternalStore`:
```tsx
import { useSyncExternalStore } from 'react';

export function useStore<T, Slice>(
  store: ReturnType<typeof createCustomStore<T>>,
  selector: (state: T) => Slice
): Slice {
  return useSyncExternalStore(
    store.subscribe,
    () => selector(store.getState()),
    () => selector(store.getState()) // Untuk Server-Side Rendering hydration
  );
}
```
Sekarang, saat komponen unmount, `listeners.delete(listener)` dipanggil, memutus rantai referensi closure dan membebaskan heap memori secara tuntas.
</details>

---

## Bagian 4: Practical Chapter Challenge

### Tantangan Arsitektur: "Production-Grade E-Commerce Cart & Sync Engine"

Bangun modul arsitektur manajemen state dan sinkronisasi data untuk aplikasi E-Commerce skala Enterprise yang memadukan **Zustand** (untuk Client UI & Offline Cart) dan **TanStack Query** (untuk Server Sync & Stock Reservation).

#### Spesifikasi Kebutuhan:
1. **Zustand Store (`useCartStore`):**
   - Menyimpan daftar `items` (id, sku, quantity, price).
   - Flag `isSyncing: boolean` dan `lastSyncedAt: number | null`.
   - Menggunakan middleware `persist` ke `localStorage`.
   - Selector teroptimasi agar penambahan kuantitas satu item tidak me-render ulang total summary harga jika komponen hanya mendengarkan item tertentu.
2. **TanStack Query Mutation dengan Optimistic Updates:**
   - Implementasikan custom hook `useUpdateCartQuantity()` menggunakan `useMutation`.
   - Mutasi meng-update kuantitas item di backend API (`PATCH /api/cart/items/:id`).
   - Menerapkan siklus penuh *Optimistic Update*:
     - `onMutate`: Batalkan query yang sedang berjalan, ambil snapshot state saat ini, update cache lokal seketika.
     - `onError`: Rollback ke snapshot sebelum mutasi dan munculkan error toast.
     - `onSettled`: Invalidate query `['cart']`.
3. **Penanganan Konflik Stok (*Out-of-Stock Fallback*):**
   - Jika backend merespons dengan status 409 (Stok tidak mencukupi, sisa unit tersedia: X), mutasi harus secara otomatis menyesuaikan nilai di keranjang lokal ke angka maksimal yang tersedia tanpa merusak keseluruhan isi keranjang.

#### Kriteria Keberhasilan Implementasi:
- Kode ditulis dalam TypeScript dengan type safety yang ketat (tanpa penggunaan `any`).
- Penanganan error komprehensif.
- Selector Zustand menggunakan komparator dangkal (*shallow*) atau granular selector.

---

## Bagian 5: Checklist Pemahaman (Self-Assessment)

Gunakan daftar periksa mandiri ini untuk memvalidasi kesiapan Anda sebelum melangkah ke implementasi sistem produksi:

- [ ] **Konseptual Arsitektur State:** Saya mampu membedakan dengan tegas kapan sebuah data harus dikelola sebagai *Server State* (TanStack Query/SWR), *Global Client State* (Zustand/Redux), *Atomic State* (Jotai), atau sekadar *Local Component State* (`useState`).
- [ ] **Mekanika Cache TanStack Query:** Saya memahami dengan tepat siklus transisi query dari `fresh` -> `stale` -> `inactive` -> `garbage collected`, serta perbedaan peran `staleTime` vs `gcTime`.
- [ ] **Teknik Invalidation Dinamis:** Saya mampu merancang hierarki Query Key yang aman terhadap *fuzzy matching* dan dapat melakukan invalidasi selektif tanpa memicu *over-fetching*.
- [ ] **Ketahanan Optimistic UI:** Saya menguasai pola 3 langkah mutasi optimis (`onMutate` cancel & snapshot, `onError` rollback, `onSettled` invalidation) beserta mitigasi kesalahan jaringan.
- [ ] **Pemberantasan Render Redundansi:** Saya memahami cara menggunakan selector granular dan shallow equality pada Zustand/Redux untuk mencegah cascade re-render pada ribuan komponen.
- [ ] **Koneksi Real-time:** Saya memahami pola integrasi WebSocket/SSE ke dalam cache query menggunakan `setQueryData` untuk menghindari badai invalidasi (*cache storming*).
- [ ] **Penanganan Offline & Sinkronisasi:** Saya memahami bahaya strategi *Last-Write-Wins* dan tahu cara mengimplementasikan *versioning* / *delta mutations* pada aplikasi *offline-first*.
- [ ] **Memory Management:** Saya memahami siklus langganan `useSyncExternalStore` dan cara mendeteksi serta memperbaiki *zombie subscribers* yang memicu *memory leak*.
