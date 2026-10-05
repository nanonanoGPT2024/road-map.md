# BAB-03-State-Management-dan-Local-Data-Persistence: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang untuk menguji pemahaman konseptual, arsitektur, dan kemampuan teknis hands-on terkait manajemen state global, sinkronisasi state server, dan persistensi data lokal performa tinggi pada React Native (Zustand, TanStack Query, MMKV, WatermelonDB/OP-SQLite, serta Keystore/Keychain).

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1: Perbedaan Fundamental Local State vs Global State
**Pertanyaan:** Kapan sebuah state sebaiknya dipertahankan sebagai local state (`useState` / `useReducer`) di dalam komponen, dan kapan harus diekstrak menjadi global client state (misalnya menggunakan Zustand store)? Jelaskan dampak arsitekturalnya terhadap re-rendering tree.

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
- **Local State (`useState` / `useReducer`):** Digunakan untuk state yang siklus hidup dan dependensinya terisolasi hanya pada satu komponen atau tree anak langsung yang dangkal (shallow). Contohnya: status input text form, visibilitas modal lokal, atau status toggle dropdown. Dampak re-render hanya terjadi dari komponen pemilik ke subtree di bawahnya.
- **Global Client State (Zustand):** Digunakan ketika state dibutuhkan oleh multiple komponen yang berjauhan pada hierarki visual tree tanpa hubungan parent-child langsung (menghindari *prop drilling*), atau state yang perlu bertahan melewati siklus unmount layar (misal: session token, cart items, theme setting).
- **Dampak Arsitektural:** Menaruh local state ke global store secara membabi-buta menyebabkan unnecessary overhead pub/sub subscription dan berpotensi memicu re-render global jika selector tidak dikonfigurasi dengan tepat (`shallow` / fine-grained atomic selector).
</details>

---

### Soal 2: Bottleneck Arsitektur AsyncStorage Tradisional
**Pertanyaan:** Mengapa `@react-native-async-storage/async-storage` dianggap memiliki batasan performa signifikan untuk aplikasi mobile modern berkecepatan 60/120 FPS, terutama dibandingkan solusi synchronous berbasis JSI seperti `react-native-mmkv`?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
1. **Asynchronous Bridge Serialization:** `AsyncStorage` klasik beroperasi melalui React Native asynchronous bridge. Setiap operasi `getItem` atau `setItem` memerlukan serialisasi JSON string via bridge, context switching thread (JS Thread -> Native Module Thread -> Disk I/O Thread -> JS Thread), yang menyebabkan frame drop jika dipanggil secara intensif pada saat render kritis.
2. **Synchronous JSI Execution:** `react-native-mmkv` mengimplementasikan JavaScript Interface (JSI). Fungsi C++ diekspos langsung ke JavaScript engine (Hermes/JSC) tanpa melalui bridge serialization. Operasi baca/tulis dieksekusi secara synchronous secara direct memory access (mmap), memangkas latensi dari belasan milidetik menjadi sub-milidetik (<0.1ms).
</details>

---

### Soal 3: Server State vs Client State
**Pertanyaan:** Mengapa menyimpan data response REST API atau GraphQL ke dalam client state manager (seperti Redux / Zustand) dianggap sebagai *anti-pattern* pada arsitektur React Native modern? Solusi apa yang direkomendasikan?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
- **Karakteristik Berbeda:** Server state bersifat *asynchronous*, dimiliki oleh remote server, berpotensi *stale* (basi), dan membutuhkan strategi deduplikasi request, caching, background refetching, serta garbage collection.
- **Masalah jika ditaruh di Client Store:** Pengembang terpaksa menulis boilerplate masif (reducer, action types, loading states, error states, timestamp validation, cache invalidation logic manual) yang rentan race condition dan out-of-sync bugs.
- **Rekomendasi Modern:** Pisahkan concern:
  - Gunakan **Server State Manager** seperti TanStack Query (`@tanstack/react-query`) atau RTK Query untuk menangani fetch, caching, background sync, dan revalidasi otomatis.
  - Gunakan **Client State Manager** murni (Zustand) hanya untuk state synchronous murni aplikasi (UI flags, multi-step wizard, active filters, transient state).
</details>

---

### Soal 4: Mekanisme Garbage Collection dan Caching TanStack Query
**Pertanyaan:** Jelaskan perbedaan konsep `staleTime` dan `gcTime` (sebelumnya `cacheTime` pada v4) dalam TanStack Query v5!

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
- **`staleTime`:** Durasi (dalam milidetik) di mana data cache dianggap masih segar (*fresh*). Selama data fresh, query component mount tidak akan memicu refetch ke jaringan. Nilai default adalah `0` (langsung dianggap stale setelah di-fetch, memicu background refetch otomatis jika trigger mount/window focus aktif).
- **`gcTime` (Garbage Collection Time):** Durasi data yang tidak aktif (*inactive* / tidak ada observer/komponen yang menggunakannya) tetap disimpan di in-memory cache sebelum dihapus permanen oleh garbage collector. Nilai default adalah 5 menit (300.000 ms).
- **Relasi:** `staleTime` mengontrol *kapan background network request terjadi*, sedangkan `gcTime` mengontrol *kapan data memory dihapus saat layar di-unmount*.
</details>

---

### Soal 5: Penyimpanan Kredensial Sensitif di Mobile
**Pertanyaan:** Mengapa token autentikasi (JWT / Refresh Token / Biometric Secret) tidak boleh disimpan di `AsyncStorage` atau `MMKV` biasa tanpa proteksi tambahan? Library apa yang wajib digunakan?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
- `AsyncStorage` dan default instance `MMKV` menyimpan data dalam format plain XML/binary file di sandbox internal aplikasi. Pada perangkat Android yang di-root atau iOS yang di-jailbreak, file sandbox dapat dibaca secara langsung oleh proses lain.
- Token autentikasi dan kunci enkripsi wajib disimpan di secure hardware container:
  - **Android:** Android Keystore System / EncryptedSharedPreferences.
  - **iOS:** iOS Keychain Services.
- **Library Standar Industri:** `react-native-keychain` atau `expo-secure-store`. Alternatif lain: simpan encryption key di Keychain/Keystore, lalu gunakan key tersebut untuk membuka instance encrypted `react-native-mmkv`.
</details>

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 1: Mencegah Re-render Storm dengan Atomic Selectors di Zustand
**Pertanyaan:** Perhatikan potongan kode berikut:

```tsx
// Komponen Profil Pengguna
const UserProfile = () => {
  const { user, logout } = useAppStore(); // Baris A
  return <Text>{user.name}</Text>;
};
```

Jika `useAppStore` juga menyimpan `cartItems` dan `notificationsCount` yang diperbarui setiap 2 detik, apa masalah performa pada Baris A dan bagaimana cara refactoring ke pola optimal menggunakan selector dan shallow equality?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
- **Permasalahan:** Baris A memanggil store tanpa selector atomik (`useAppStore()`), yang berarti komponen me-subscribe ke seluruh root state object. Setiap kali ada mutasi state apapun di dalam store (misal: `cartItems` bertambah atau `notificationsCount` berganti), referensi store berubah dan `UserProfile` dipaksa re-render meskipun nilai `user.name` tidak berubah.
- **Refactoring Optimal:**
  ```tsx
  import { useShallow } from 'zustand/react/shallow';

  // Opsi 1: Single primitive selector (Paling direkomendasikan jika hanya butuh 1 properti)
  const userName = useAppStore((state) => state.user.name);
  const logout = useAppStore((state) => state.logout);

  // Opsi 2: Object slice dengan useShallow (mencegah re-render jika referensi properti internal identik)
  const { user, logout } = useAppStore(
    useShallow((state) => ({
      user: state.user,
      logout: state.logout,
    }))
  );
  ```
</details>

---

### Soal 2: Offline Mutation Queue dan Optimistic Updates
**Pertanyaan:** Bagaimana arsitektur implementasi Optimistic Update pada TanStack Query ketika pengguna mobile melakukan aksi "Like Post" dalam kondisi sinyal intermittent/offline?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
Alur arsitektur standar TanStack Query:
1. **`onMutate` Lifecycle:**
   - Batalkan outgoing queries terkait menggunakan `queryClient.cancelQueries({ queryKey: ['post', postId] })` agar response lama tidak menimpa optimistic state.
   - Ambil snapshot previous data cache menggunakan `queryClient.getQueryData`.
   - Update cache secara synchronous menggunakan `queryClient.setQueryData` dengan data baru (misal: `isLiked: true`, `likeCount: likeCount + 1`).
   - Return context object yang berisi `{ previousPost }`.
2. **`onError` Lifecycle:**
   - Jika mutasi gagal (network error / timeout), rollback cache menggunakan snapshot dari context:
     `queryClient.setQueryData(['post', postId], context.previousPost)`.
   - Tampilkan toast notification error ke pengguna.
3. **`onSettled` Lifecycle:**
   - Selalu panggil `queryClient.invalidateQueries({ queryKey: ['post', postId] })` untuk memastikan data lokal akhirnya konsisten dengan data faktual dari database backend.
</details>

---

### Soal 3: Skalabilitas Database Relasional Lokal (SQLite / WatermelonDB)
**Pertanyaan:** Dalam use-case apa penyimpanan berbasis key-value (seperti MMKV) menjadi tidak layak digunakan, sehingga arsitektur aplikasi harus beralih ke database relasional (seperti WatermelonDB atau OP-SQLite)?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
MMKV tidak layak dan harus diganti relational database ketika:
1. **Volume Data Besar (>10.000 records):** Parsing array JSON ribuan item di memory JS memicu crash OOM (Out Of Memory) dan freeze UI thread.
2. **Kebutuhan Complex Querying & Filtering:** Butuh query gabungan (*JOIN* antar tabel, *indexing*, *sorting*, *pagination cursor*, *full-text search*). Key-value hanya mendukung lookup direct key `O(1)`.
3. **Observable Reactive Rows:** WatermelonDB menyediakan observable records berbasis RxJS. Ketika 1 row di database berubah, hanya komponen yang mengikat row tersebut yang di-render ulang tanpa me-load seluruh array ke JavaScript memory.
4. **Relasi Many-to-Many / One-to-Many:** Contoh: Chat application (Conversation -> Messages -> Attachments -> Reactions).
</details>

---

### Soal 4: Hydration & Race Condition pada Zustand Persist
**Pertanyaan:** Saat menggunakan middleware `persist` pada Zustand bersama storage adapter asynchronous atau synchronous MMKV, bagaimana menangani status *hydration* agar komponen UI tidak merender data kosong (*flash of empty state*) sebelum persistensi selesai dimuat?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
Zustand middleware `persist` menyediakan API listener `onRehydrateStorage` dan hook `useStore.persist.hasHydrated()`.
1. **Arsitektur Custom Hydration Hook:**
   ```tsx
   export const useStoreHydration = () => {
     const [hydrated, setHydrated] = useState(useAppStore.persist.hasHydrated());

     useEffect(() => {
       const unsubHydrate = useAppStore.persist.onHydrate(() => setHydrated(false));
       const unsubFinish = useAppStore.persist.onFinishHydration(() => setHydrated(true));
       setHydrated(useAppStore.persist.hasHydrated());
       return () => {
         unsubHydrate();
         unsubFinish();
       };
     }, []);

     return hydrated;
   };
   ```
2. **Pencegahan Flash of Empty Content:** Pada entry point aplikasi (`RootLayout` atau `App.tsx`), tahan rendering navigation stack atau tampilkan native Splash Screen (`BootSplash.hide()` / `SplashScreen.preventAutoHideAsync()`) hingga `hydrated === true`.
</details>

---

### Soal 5: Sinkronisasi Focus State dan AppState pada React Native Query
**Pertanyaan:** TanStack Query secara default bergantung pada event browser `window.addEventListener('focus')` dan `navigator.onLine`. Mengapa ini tidak berfungsi otomatis di React Native dan konfigurasi apa yang wajib diinjeksi?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
React Native tidak berjalan di browser DOM, sehingga event global `focus` dan `online` tidak tersedia. TanStack Query memerlukan integrasi adapter native:
1. **Focus Manager (`AppState`):**
   ```tsx
   import { AppState, Platform } from 'react-native';
   import { focusManager } from '@tanstack/react-query';

   focusManager.setEventListener((handleFocus) => {
     const subscription = AppState.addEventListener('change', (status) => {
       if (Platform.OS !== 'web') {
         handleFocus(status === 'active');
       }
     });
     return () => subscription.remove();
   });
   ```
2. **Online Status Manager (`NetInfo`):**
   ```tsx
   import NetInfo from '@react-native-community/netinfo';
   import { onlineManager } from '@tanstack/react-query';

   onlineManager.setEventListener((setOnline) => {
     return NetInfo.addEventListener((state) => {
       setOnline(Boolean(state.isConnected && state.isInternetReachable));
     });
   });
   ```
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 1: Konflik Offline-First Synchronizer pada Aplikasi Field Worker
**Konteks Masalah:**
Aplikasi inspeksi gudang digunakan oleh petugas di area bawah tanah tanpa koneksi internet. Petugas memperbarui status 50 item inventaris secara offline. Saat kembali ke area dengan sinyal, aplikasi menyinkronkan data kembali ke server. Namun, di saat bersamaan, manajer pusat telah mengubah harga 10 item tersebut dari dashboard web.

**Pertanyaan Arsitektur:**
1. Desain model data mutasi antrean (*mutation queue*) offline lokal.
2. Tentukan strategi resolusi konflik (*Last-Write-Wins* vs *Server-Wins* vs *Three-Way Merge*) untuk skenario ini dan jelaskan alasannya.

<details>
<summary>Solusi & Analisis Arsitektur</summary>

**1. Model Data Mutation Queue:**
Simpan antrean mutasi di SQLite/WatermelonDB dengan struktur tabel `outbox_mutations`:
```sql
CREATE TABLE outbox_mutations (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  mutation_type TEXT NOT NULL, -- 'UPDATE_STATUS'
  payload TEXT NOT NULL,       -- JSON payload
  created_at INTEGER NOT NULL,
  base_version INTEGER NOT NULL, -- Versi data saat diedit petugas
  retry_count INTEGER DEFAULT 0,
  status TEXT DEFAULT 'PENDING'  -- 'PENDING', 'PROCESSING', 'FAILED'
);
```

**2. Strategi Resolusi Konflik:**
- **Pendekatan Rekomendasi: Field-Level Merging dengan Version Vector (Three-Way Merge parsial).**
  - Mengapa *Last-Write-Wins (LWW)* ditolak? LWW akan menimpa harga baru dari manajer pusat dengan harga lama yang dibawa snapshot petugas, menyebabkan kerugian finansial.
  - Mengapa *Server-Wins* ditolak? Perubahan status fisik yang dilakukan petugas di lapangan akan hilang total.
- **Implementasi:** Backend membandingkan `base_version` mutasi dengan current server version. Karena perubahan manajer hanya pada field `price` dan perubahan petugas hanya pada field `inspection_status` dan `condition_notes`, backend melakukan auto-merge kedua perubahan tersebut dan menaikkan `version = version + 1`. Jika terjadi overlap pada *field yang sama*, record ditandai `CONFLICT` dan dikembalikan ke antrean aplikasi mobile untuk diselesaikan manual oleh supervisor via dialog rekonsiliasi.
</details>

---

### Skenario 2: Enkripsi Data MMKV vs Keystore Performance Degradation
**Konteks Masalah:**
Tim sekuriti mewajibkan seluruh cache key-value dienkripsi menggunakan AES-256. Pengembang baru mengimplementasikan enkripsi dengan cara memanggil `react-native-keychain` secara langsung di setiap get/set state Zustand. Akibatnya, scroll list menjadi patah-patah (FPS anjlok ke 20 FPS).

**Pertanyaan Analisis:**
1. Mengapa memanggil Keychain/Keystore di setiap operasi state management merusak frame rate?
2. Bagaimana pola arsitektur yang benar untuk mempertahankan enkripsi kelas militer tanpa mengorbankan performa 60/120 FPS?

<details>
<summary>Solusi & Analisis Arsitektur</summary>

**1. Root Cause:**
Hardware Security Module (Secure Enclave di iOS dan Android TEE/Keystore) dirancang untuk keamanan tingkat tinggi, bukan throughput tinggi. Setiap pemanggilan native bridge ke Keychain melibatkan dekripsi hardware berkecepatan rendah (10-50 ms per request) dan context switching thread asynchronous. Memanggilnya di loop scroll atau selector memblokir thread.

**2. Pola Arsitektur Optimal (Hybrid Envelope Encryption):**
1. **Bootstrapping Aplikasi:**
   - Saat aplikasi pertama kali launch, periksa apakah master encryption key ada di `react-native-keychain`.
   - Jika belum ada, generate random 256-bit cryptographically secure string, lalu simpan ke Keychain.
   - Ambil master key tersebut **satu kali saja** saat cold start aplikasi via asynchronous bridge.
2. **Inisialisasi MMKV Terenkripsi:**
   - Gunakan master key tersebut untuk menginisialisasi MMKV native encrypted storage:
     ```ts
     import { MMKV } from 'react-native-mmkv';
     export const secureStorage = new MMKV({
       id: 'app-secure-storage',
       encryptionKey: masterKeyFromKeychain, // Enkripsi AES C++ level JSI
     });
     ```
3. **Hasil:** Operasi baca/tulis state selanjutnya dieksekusi secara synchronous via JSI C++ memory-mapped file dengan akselerasi hardware AES tanpa overhead bridge dan tanpa menyentuh Secure Enclave berulang kali.
</details>

---

### Skenario 3: Re-render Storm pada Chat Room dengan Riwayat Pesan Tinggi
**Konteks Masalah:**
Aplikasi mobile chat memiliki layar chat room dengan 5.000 riwayat pesan. State disimpan dalam array Zustand `messages: Message[]`. Setiap kali ada pesan WebSocket baru masuk, pengembang melakukan update:
```ts
set((state) => ({ messages: [...state.messages, incomingMessage] }))
```
Layar mengalami freeze selama 400ms setiap kali pesan baru diterima saat user sedang mengetik atau scrolling.

**Pertanyaan Optimasi:**
Identifikasi minimal 3 bottleneck utama pada implementasi di atas dan jelaskan solusi refactoring arsitekturnya!

<details>
<summary>Solusi & Analisis Arsitektur</summary>

**Bottleneck & Solusi Refactoring:**
1. **Bottleneck 1: Un-normalized Array State Mutations.**
   - *Masalah:* Menyalin array 5.000 objek (`[...state.messages, newMsg]`) mengalokasikan memory baru dan memicu garbage collection spike.
   - *Solusi:* Normalisasi state menjadi ID-based dictionary:
     ```ts
     interface ChatState {
       ids: string[];
       entities: Record<string, Message>;
     }
     ```
2. **Bottleneck 2: FlatList / VirtualizedList Re-render Subtree.**
   - *Masalah:* Jika `ListRenderItem` tidak di-memoize, atau mengoper inline callback/object, seluruh 5.000 item mengevaluasi virtual DOM saat array referensi berubah.
   - *Solusi:* Gunakan `@shopify/flash-list` dengan `estimatedItemSize`. Bungkus item component dengan `React.memo` yang hanya me-subscribe ke item ID spesifik (`entities[id]`).
3. **Bottleneck 3: Main Thread Blocking oleh Local Persistence.**
   - *Masalah:* Jika setiap update pesan langsung diserialisasi ulang ke disk secara penuh (`JSON.stringify(messages)`), IO blocking menghentikan UI thread.
   - *Solusi:* Gunakan database lokal berbasis SQLite (OP-SQLite / WatermelonDB) untuk append single row secara native asynchronous query tanpa menduplikasi data di JS memory heap.
</details>

---

## Bagian 4: Practical Chapter Challenge

### Judul Challenge: "Offline-First Sync Engine dengan Zustand, MMKV, dan TanStack Query"

#### Objektif:
Bangun arsitektur mini modul toko offline-first yang mampu menangani keranjang belanja (*Shopping Cart*), sinkronisasi offline mutation, serta persistent encrypted storage.

#### Spesifikasi Kebutuhan Teknis:

1. **Storage Adapter Layer (`storage.ts`):**
   - Buat instance MMKV terenkripsi.
   - Buat interface custom storage adapter yang kompatibel dengan middleware `persist` milik Zustand.

2. **Zustand Cart Slice (`useCartStore.ts`):**
   - State wajib ternormalisasi (`items: Record<string, CartItem>`, `itemIds: string[]`).
   - Actions: `addItem(product, qty)`, `removeItem(id)`, `updateQty(id, qty)`, `clearCart()`.
   - Gunakan middleware `persist` dengan selective filtering (`partialize`) agar hanya `items` dan `itemIds` yang disimpan ke MMKV (flags seperti `isSyncing` tidak boleh di-persist).

3. **Offline Sync Queue (`useSyncQueueStore.ts`):**
   - Simpan antrean aksi mutasi yang gagal saat offline:
     ```ts
     interface MutationJob {
       id: string;
       endpoint: string;
       method: 'POST' | 'PUT' | 'DELETE';
       payload: unknown;
       timestamp: number;
     }
     ```
   - Sediakan action `enqueueMutation`, `dequeueMutation`, dan `retryFailedMutations`.

4. **TanStack Query Network Resiliency (`queryClient.ts`):**
   - Konfigurasi `onlineManager` menggunakan `@react-native-community/netinfo`.
   - Konfigurasi default query options: `staleTime: 1000 * 60 * 5` (5 menit), `retry: 3`.

#### Kode Solusi Acuan (Reference Implementation):

```typescript
// 1. storage.ts
import { MMKV } from 'react-native-mmkv';
import { StateStorage } from 'zustand/middleware';

export const mmkvInstance = new MMKV({
  id: 'cart-storage',
  encryptionKey: 'super-secure-production-key-from-keychain',
});

export const zustandStorage: StateStorage = {
  setItem: (name, value) => mmkvInstance.set(name, value),
  getItem: (name) => {
    const value = mmkvInstance.getString(name);
    return value ?? null;
  },
  removeItem: (name) => mmkvInstance.delete(name),
};

// 2. useCartStore.ts
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { zustandStorage } from './storage';

export interface CartItem {
  id: string;
  name: string;
  price: number;
  qty: number;
}

interface CartState {
  items: Record<string, CartItem>;
  itemIds: string[];
  isSyncing: boolean;
  addItem: (product: Omit<CartItem, 'qty'>, qty?: number) => void;
  removeItem: (id: string) => void;
  clearCart: () => void;
  getTotalPrice: () => number;
}

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      items: {},
      itemIds: [],
      isSyncing: false,

      addItem: (product, qty = 1) =>
        set((state) => {
          const existing = state.items[product.id];
          const newQty = (existing?.qty ?? 0) + qty;
          const updatedItem: CartItem = { ...product, qty: newQty };

          return {
            items: { ...state.items, [product.id]: updatedItem },
            itemIds: existing ? state.itemIds : [...state.itemIds, product.id],
          };
        }),

      removeItem: (id) =>
        set((state) => {
          const newItems = { ...state.items };
          delete newItems[id];
          return {
            items: newItems,
            itemIds: state.itemIds.filter((itemId) => itemId !== id),
          };
        }),

      clearCart: () => set({ items: {}, itemIds: [] }),

      getTotalPrice: () => {
        const { items, itemIds } = get();
        return itemIds.reduce((sum, id) => sum + items[id].price * items[id].qty, 0);
      },
    }),
    {
      name: 'cart-storage-key',
      storage: createJSONStorage(() => zustandStorage),
      partialize: (state) => ({
        items: state.items,
        itemIds: state.itemIds,
      }),
    }
  )
);
```

---

## Bagian 5: Checklist Pemahaman (Self-Assessment Matrix)

Gunakan checklist ini untuk mengukur kesiapan arsitektur sebelum melangkah ke bab berikutnya:

| Kriteria Kemampuan / Konsep | Level Pemahaman | Sudah Dikuasai? (Centang) |
|---|---|:---:|
| Mampu membedakan Client State (Zustand) vs Server State (TanStack Query) tanpa tumpang tindih arsitektur | Fundamental | [ ] |
| Mampu mengonfigurasi `react-native-mmkv` dengan JSI synchronous storage adapter untuk Zustand | Intermediate | [ ] |
| Memahami bahaya re-rendering dan terampil menggunakan atomic selector (`useShallow` / single property selector) | Intermediate | [ ] |
| Mampu mengintegrasikan `AppState` dan `NetInfo` ke dalam TanStack Query Focus & Online Managers | Intermediate | [ ] |
| Memahami strategi proteksi kredensial sensitif via Keychain / Keystore envelope encryption | Advanced | [ ] |
| Mampu mendesain model data antrean mutasi offline (*outbox pattern*) dan mekanisme resolusi konflik sinkronisasi | Advanced | [ ] |
| Mengetahui batasan performa key-value storage dan kapan harus bermigrasi ke SQLite / WatermelonDB | Advanced | [ ] |
