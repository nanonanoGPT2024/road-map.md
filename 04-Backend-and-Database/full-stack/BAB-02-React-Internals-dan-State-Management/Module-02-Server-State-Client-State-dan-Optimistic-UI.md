---
[⬅️ Module 01: React Fiber Reconciler](./Module-01-React-Fiber-Reconciler-Diffing-dan-Concurrent.md) | [📋 Silabus Induk](../README.md) | [BAB 02 Quiz & Challenge ➡️](./BAB-02-Quiz-dan-Challenge.md)
---

# Module 02: State Management: Server State (TanStack Query) vs Client State (Zustand) & Optimistic UI

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Mengidentifikasi taksonomi 3 jenis state web modern: **Client State (UI State)**, **Server State (Remote Cache)**, dan **URL State (Search Params)**.
- Memahami mengapa menggunakan Redux tradisional untuk menyimpan data API dari server adalah *Antipattern*, dan menguasai paradigma **Server State Management (TanStack Query / React Query)**.
- Menguasai parameter siklus hidup caching data: **`staleTime`** vs **`gcTime` (Garbage Collection Time)**, deduplikasi request otomatis, dan *Window Focus Revalidation*.
- Menguasai arsitektur state klien modern berbasis atom / micro-store (**Zustand** & **Jotai**) yang bebas dari *Boilerplate Hell*.
- Mengimplementasikan pola mutasi antarmuka mutakhir: **Optimistic UI Updates** dengan mekanisme *Automatic Rollback* saat transaksi jaringan mengalami kegagalan.

---

## 2. Prerequisite
- Memahami siklus render React Fiber dan aturan immutability (Modul 01).
- Pemahaman operasi asynchronous JavaScript (`async/await`, `Promise`).
- Dasar komunikasi data REST API / GraphQL (Backend BAB 03).

---

## 3. Concept
Dalam pengembangan frontend klasik, pengembang sering membuat satu store Redux raksasa untuk menampung segala hal: status dropdown terbuka, daftar 50 produk dari database, token autentikasi, hingga input form checkout.

Arsitektur Full-Stack modern menyadari bahwa **Data dari Server bukanlah milik Frontend**. Data tersebut hanyalah **Snapshot Temporer di Masa Lalu (Cache)** dari basis data yang berada di server.

Oleh karena itu, arsitektur state modern memisahkan tanggung jawab secara tegas:
1. **Server State (Dikelola oleh TanStack Query / SWR):** Menangani asynchronous fetching, caching memori otomatis, deduplikasi request, polling background, retry saat network error, dan mutasi optimistik.
2. **Client State (Dikelola oleh Zustand / Jotai):** Menyimpan status murni antarmuka lokal yang bersifat sementara (apakah sidebar tertutup, preferensi dark mode, atau koordinat kanvas grafis).
3. **URL State (Dikelola oleh Query Params):** Menyimpan filter pencarian, nomor halaman paginasi, dan parameter tab agar dapat di-bookmark dan dibagikan (*Shareable URL*).

---

## 4. Why?
Tanpa pemisahan Server State dan Client State:
1. **Over-fetching & Request Duplikasi Masif:** 5 komponen independen di layar membutuhkan data profil user yang sama. Tanpa TanStack Query, masing-masing komponen memanggil `fetch('/api/user')` sendiri-sendiri, memboroskan 5 round-trip jaringan HTTP dalam milidetik yang sama.
2. **Stale Data yang Tidak Pernah Diperbarui:** Pengguna membiarkan tab browser terbuka selama 4 jam. Ketika kembali, saldo e-wallet yang ditampilkan adalah saldo 4 jam lalu karena tidak ada mekanisme *Refetch on Window Focus*.
3. **Loading Spinner Berlebihan (*Spinner Fatigue*):** Pengguna mengklik tombol "Like" postingan media sosial. Pengguna harus menunggu 1 detik melihat icon spinner berputar sebelum jumlah like bertambah, membuat aplikasi terasa lambat dan kaku.
4. **Redux Boilerplate Raksasa:** Menulis 5 file terpisah (*action types, action creators, reducers, selectors, thunks*) hanya untuk menampilkan satu daftar nama barang sederhana.

---

## 5. What? (Parameter Kunci TanStack Query: `staleTime` vs `gcTime`)

Dua parameter ini adalah jantung efisiensi caching data di frontend:

```
[ Data Diterima dari Server ] ──▶ [ STATUS: FRESH ] ──(staleTime Berakhir)──▶ [ STATUS: STALE ]
                                         │                                            │
                             Data dianggap valid 100%.                     Data dianggap usang!
                             Query komponen baru TIDAK                    Jika komponen baru butuh data,
                             perlu fetch ulang ke server.                  tampilkan data cache DULU, lalu
                                                                           FETCH ULANG di background!
                                                                                      │
                                                                       (Komponen di-unmount dari layar)
                                                                                      │
                                                                                      ▼
                                                                        [ GC TIMER BERJALAN: gcTime ]
                                                                        (Data tetap disimpan di RAM
                                                                         selama durasi gcTime, misal 5 menit)
                                                                                      │
                                                                           (gcTime Habis / Expired)
                                                                                      ▼
                                                                        [ DATA DIHAPUS DARI MEMORI RAM ]
```

- **`staleTime` (Waktu Basi):** Durasi berapa lama data dianggap masih segar. Selama data masih fresh, React tidak akan pernah melakukan refetch ke server. Default: `0` (langsung dianggap stale).
- **`gcTime` (Garbage Collection Time):** Durasi berapa lama data yang tidak lagi digunakan oleh komponen aktif tetap disimpan di memori RAM sebelum dihapus permanen. Default: `5 menit`.

---

## 6. How? (Arsitektur Optimistic UI Updates dengan Automatic Rollback)

Optimistic UI memberikan ilusi kecepatan seketika kepada pengguna: antarmuka langsung diperbarui **sebelum request jaringan selesai dikirim ke server**.

```
[ Pengguna Klik Tombol "Like Post" ]
                 │
                 ▼
 ┌────────────────────────────────────────────────────────┐
 │ LANGKAH 1: BATALKAN REFETCH AKTIF                      │
 │ - queryClient.cancelQueries({ queryKey: ['post', 1] }) │
 └──────────────────────────┬─────────────────────────────┘
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │ LANGKAH 2: SIMPAN SNAPSHOT STATE LAMA (UNTUK ROLLBACK) │
 │ - const previousPost = queryClient.getQueryData(...)   │
 └──────────────────────────┬─────────────────────────────┘
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │ LANGKAH 3: UPDATE MEMORI CACHE SECARA OPTIMIS (INSTAN!)│
 │ - queryClient.setQueryData(['post', 1], old => ({      │
 │     ...old, likes: old.likes + 1, isLiked: true        │
 │   }))                                                  │
 │ ==> Layar pengguna LANGSUNG BERUBAH DALAM 0 MILIDETIK! │
 └──────────────────────────┬─────────────────────────────┘
                            │
              Kirim Request HTTP PATCH ke Server
                            │
               ┌────────────┴────────────┐
            (Sukses)                  (Gagal / Error 500)
               │                         │
               ▼                         ▼
 ┌───────────────────────────┐ ┌────────────────────────────────────────┐
 │ LANGKAH 4A: REVALIDASI    │ │ LANGKAH 4B: ROLLBACK OTOMATIS          │
 │ - Sinkronkan data resmi   │ │ - Kembalikan cache ke 'previousPost'!  │
 │   terakhir dari database. │ │ - Tampilkan pesan toast error merah:   │
 └───────────────────────────┘ │   "Koneksi gagal, like dibatalkan."    │
                               └────────────────────────────────────────┘
```

---

## 7. Analogy
- **Client State ibarat Dompet di Saku Celana:** Anda memutuskan sendiri berapa lembar uang kertas yang ingin Anda tata di saku. Anda tidak perlu izin dari siapa pun untuk membuka resleting dompet Anda.
- **Server State ibarat Saldo Rekening Bank di Layar ATM:** Angka yang tertera di layar ATM bukanlah uang fisik Anda; itu hanyalah cetakan informasi status komputer bank pusat beberapa detik lalu. Jika istri Anda menarik uang di ATM lain 1 menit lalu, angka di layar Anda sudah basi (*Stale*).
- **Optimistic UI ibarat Mengirim Pesan di WhatsApp:** Saat Anda menekan tombol "Kirim", gelembung pesan langsung muncul seketika di layar Anda dengan tanda jam kecil (**Optimistic Feedback**). Anda tidak dipaksa menunggu tanda centang dua dari server baru pesannya boleh muncul. Jika koneksi internet mati, tanda jam berubah menjadi tanda seru merah (**Rollback / Error**).

---

## 8. Diagram: Zustand Micro-Store vs Context API Re-render Trap

```
BAHAYA REACT CONTEXT API (UNNECESSARY RE-RENDER TRAP):
┌────────────────────────────────────────────────────────────────────────┐
│ Context Provider: { user: { name: 'Budi' }, theme: 'dark' }           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
               ┌────────────────────┴────────────────────┐
               ▼                                         ▼
      [ UserProfile Component ]                 [ ThemeToggle Component ]
      (Hanya butuh data 'user')                 (Hanya butuh data 'theme')
                                                         │
                                  Theme berubah dari 'dark' ke 'light'!
                                                         │
                                                         ▼
               KEDUA KOMPONEN DI-RENDER ULANG REKURSIF! ❌
               (UserProfile ikut re-render padahal data user tidak berubah!)

SOLUSI ZUSTAND (ATOMIC SELECTOR SUBSCRIPTION):
const theme = useAppStore(state => state.theme); // Selector Spesifik!
==> HANYA ThemeToggle yang me-render ulang! UserProfile diam tenang di memori! ✅
```

---

## 9. Simple Example: Store Klien Zustand Modern (TypeScript)

```typescript
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

interface UIState {
  isSidebarOpen: boolean;
  theme: 'light' | 'dark';
  toggleSidebar: () => void;
  setTheme: (theme: 'light' | 'dark') => void;
}

export const useUIStore = create<UIState>()(
  devtools(
    persist(
      (set) => ({
        isSidebarOpen: true,
        theme: 'dark',
        
        // Aksi mutasi atomik sederhana tanpa reducer berbelit-belit
        toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
        setTheme: (theme) => set({ theme })
      }),
      { name: 'ui-storage-v1' } // Otomatis tersimpan persisten di localStorage!
    )
  )
);
```

---

## 10. Practical Example: Implementasi Optimistic UI dengan TanStack Query v5

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query';

interface Todo {
  id: string;
  title: string;
  completed: boolean;
}

export function useToggleTodoMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (todoId: string) => {
      const response = await fetch(`/api/todos/${todoId}/toggle`, { method: 'PATCH' });
      if (!response.ok) throw new Error('Gagal memperbarui status tugas di server');
      return response.json();
    },

    // 1. Eksekusi Optimistis Tepat Sebelum Request Jaringan Dikirim
    onMutate: async (todoId: string) => {
      // Batalkan refetch aktif agar tidak menimpa pembaruan optimis kita
      await queryClient.cancelQueries({ queryKey: ['todos'] });

      // Simpan snapshot data lama
      const previousTodos = queryClient.getQueryData<Todo[]>(['todos']);

      // Perbarui cache secara optimis di memori
      queryClient.setQueryData<Todo[]>(['todos'], (old = []) =>
        old.map((t) => (t.id === todoId ? { ...t, completed: !t.completed } : t))
      );

      // Kembalikan konteks yang memuat data cadangan untuk rollback
      return { previousTodos };
    },

    // 2. Jika Terjadi Error di Jaringan / Server: ROLLBACK INSTAN!
    onError: (err, todoId, context) => {
      if (context?.previousTodos) {
        queryClient.setQueryData(['todos'], context.previousTodos);
        console.warn('⚠️ Mutasi gagal! Status UI berhasil di-rollback ke kondisi semula.');
      }
    },

    // 3. Revalidasi Data Resmi Setelah Selesai (Sukses maupun Gagal)
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['todos'] });
    }
  });
}
```

---

## 11. Real World Example: Fitur Chat & Feed Twitter / Linear App

Aplikasi produktivitas kelas dunia seperti **Linear.app** dan **Twitter/X**:
- Pengguna Linear dapat menandai 10 tiket task selesai dalam 1 detik.
- Setiap aksi langsung mengubah UI dalam **0 milidetik** berkat Optimistic UI + local state store.
- Permintaan sinkronisasi dialirkan di latar belakang melalui antrean mutasi TanStack Query.
- Jika pengguna kehilangan koneksi internet (masuk terowongan kereta), aplikasi tetap dapat digunakan secara mulus (*Offline Tolerant*). Saat koneksi pulih, mutasi yang tertunda secara otomatis di-retry ke server.

---

## 12. Trade-offs

| Aspek Pertimbangan | Redux Toolkit Tradisional | TanStack Query + Zustand | Context API Bawaan |
|---|---|---|---|
| **Pemisahan Server/Client**| Buruk (Bercampur aduk di Redux)| **Sempurna** (Server State mandiri)| Manual (Rentan tercampur) |
| **Boilerplate Kode** | Sangat Tinggi (Actions, Reducers)| Sangat Rendah (Hooks murni)| Rendah |
| **Deduplikasi Request** | Harus ditulis manual via Thunk| **Otomatis Bawaan** | Tidak ada |
| **Optimistic UI Engine**| Rumit (Harus buat custom reducers)| **Terintegrasi (`onMutate`)**| Sangat Rumit |
| **Ukuran Bundle JS** | Menengah (~11 KB) | Sangat Ringan (Zustand ~1 KB)| **0 KB (Bawaan React)** |

---

## 13. When To Use
- **Gunakan TanStack Query:** Wajib untuk **seluruh pengambilan data API eksternal** (REST, GraphQL, microservices endpoints) yang memiliki status loading, error, caching, dan revalidasi.
- **Gunakan Zustand:** Untuk state global murni antarmuka klien (posisi panel sidebar, preferensi modal dialog, status keranjang belanja sementara sebelum checkout).
- **Gunakan Optimistic UI:** Pada interaksi pengguna yang sering dilakukan dan memiliki tingkat keberhasilan server tinggi (> 99%), seperti tombol Like, Upvote, Toggle Checkbox, dan pengiriman pesan chat.

---

## 14. When NOT To Use
- **Jangan Gunakan Optimistic UI untuk Transaksi Finansial Berisiko Tinggi:** Mengupdate status saldo bank pengguna secara optimistik sebelum bank sentral mengonfirmasi pembayaran adalah pelanggaran integritas data yang fatal.
- **Jangan Gunakan Zustand untuk Menyimpan Data Hasil Query REST API:** Menyimpan data produk di Zustand memaksa Anda menulis logika manual untuk refetch on focus, retry timer, dan polling yang sebenarnya sudah diselesaikan dengan sempurna oleh TanStack Query.

---

## 15. Common Mistakes
1. **Mengabaikan Query Key Dependency:** Menulis query key statis `['products']` untuk endpoint pencarian yang memiliki filter kata kunci (`/api/products?search=shoes`). Akibatnya, saat kata kunci pencarian berubah, TanStack Query tetap menyajikan hasil cache lama karena query key-nya tidak menyertakan variabel filter `['products', searchTerm]`.
2. **Tidak Mengembalikan `previousData` pada `onMutate`:** Lupa me-return snapshot state lama di callback `onMutate`, menyebabkan fungsi `onError` tidak memiliki data referensi untuk melakukan rollback.
3. **Mengatur `staleTime: Infinity` Tanpa Invalidation:** Menyeting staleTime tak terbatas membuat data aplikasi tidak pernah diperbarui dari database kecuali browser di-refresh manual oleh pengguna.

---

## 16. Best Practices

### Must Have
- Sertakan seluruh parameter filter dan paginasi ke dalam **Array Query Key**: `queryKey: ['orders', userId, page, filterStatus]`.
- Pasang mekanisme pembatalan query (`queryClient.cancelQueries`) pada setiap mutasi optimistik untuk mencegah balapan update data (*Race Conditions*).
- Pisahkan kode Custom Query Hooks ke dalam direktori independen (`/hooks/queries/useUserQuery.ts`).

### Recommended
- Atur nilai default `staleTime: 1000 * 60` (1 menit) pada QueryClient global untuk menghindari lonjakan request berulang yang tidak perlu.
- Gunakan fitur **Prefetching**: Panggil `queryClient.prefetchQuery()` saat user mengarahkan kursor mouse (*hover*) di atas kartu produk.

### Advanced
- Gabungkan TanStack Query dengan **Persistence Plugins** (seperti `@tanstack/query-persist-client-core`) untuk menyimpan cache server state di IndexedDB browser agar aplikasi dapat dibuka secara instan bahkan saat mode offline.

---

## 17. Troubleshooting

| Gejala Masalah | Indikasi Akar Masalah | Langkah Investigasi | Tindakan Perbaikan |
|---|---|---|---|
| **Data Selalu Fetch Ulang Setiap Ganti Tab Browser** | Konfigurasi default `refetchOnWindowFocus: true` aktif saat `staleTime: 0` | Cek opsi global di `QueryClientProvider` | Tetapkan nilai `staleTime` wajar (misal 30 detik) jika data tidak sering berubah |
| **Rollback Optimistik Berkedip (*UI Flickering*)** | Query invalidation terpanggil sebelum mutasi POST/PATCH di server selesai dikomit | Cek urutan pemanggilan di `onSettled` vs `onSuccess` | Pastikan `await invalidateQueries()` menunggu respon final server |
| **Zustand Selector Tidak Mencegah Re-render** | Selector mengembalikan objek baru anonim: `state => ({ a: state.a, b: state.b })` | Periksa referensi equality selector | Gunakan hook `useShallow` dari Zustand: `useAppStore(useShallow(state => ({ ... })))` |

---

## 18. Exercise
1. Tulis simulator state manager berbasis Node.js yang memodelkan siklus hidup TanStack Query cache (`staleTime`, `gcTime`, cache invalidation).
2. Implementasikan alur mutasi Optimistic UI untuk penambahan komentar pada postingan blog.
3. Simulasikan kegagalan jaringan acak (HTTP 500) dan buktikan mekanisme rollback memulihkan daftar komentar ke kondisi awal.

---

## 19. Challenge
Rancang arsitektur state management untuk aplikasi **Kanban Board Kolaboratif (seperti Trello / Jira)**:
1. Dukung drag-and-drop pemindahan kartu tugas antar kolom secara optimistik dalam latensi 0 ms.
2. Jika ada 3 pengguna lain yang memindahkan kartu yang sama secara simultan via WebSocket, rancang mekanisme rekonsiliasi state agar tidak terjadi konflik data (*Last-Write-Wins vs Operational Transformation*)!

---

## 20. Summary
State management modern bukan lagi tentang membuat wadah global tunggal yang kaku, melainkan tentang ketepatan memilah antara data milik server (Server State) dan data milik antarmuka (Client State). Dengan mengintegrasikan TanStack Query untuk orkestrasi caching dan Optimistic UI, dipadukan dengan kelincahan Zustand untuk state lokal, seorang Full-Stack Engineer menghadirkan antarmuka web yang tangguh, responsif seketika, dan bebas dari overhead komputasi yang tidak perlu.

---
[⬅️ Module 01: React Fiber Reconciler](./Module-01-React-Fiber-Reconciler-Diffing-dan-Concurrent.md) | [📋 Silabus Induk](../README.md) | [BAB 02 Quiz & Challenge ➡️](./BAB-02-Quiz-dan-Challenge.md)
---
