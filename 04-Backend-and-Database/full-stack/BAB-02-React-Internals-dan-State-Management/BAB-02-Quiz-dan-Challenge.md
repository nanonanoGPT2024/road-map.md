---
[⬅️ Module 02: Server State vs Client State](./Module-02-Server-State-Client-State-dan-Optimistic-UI.md) | [📋 Silabus Induk](../README.md) | [BAB 03: Meta-Frameworks Next.js ➡️](../BAB-03-Meta-Frameworks-Nextjs-App-Router/Module-01-React-Server-Components-Streaming-SSR-Server-Actions.md)
---

# BAB 02: Evaluasi Pemahaman, Quiz, & Tantangan React Internals & State Management

Selamat! Anda telah menuntaskan materi **BAB 02: Modern Frontend Engineering: React Internals, Virtual DOM, & State Management**. Lembar evaluasi ini dirancang untuk menguji penguasaan arsitektural Anda terhadap mesin rekonsiliasi React Fiber, heuristik diffing, pemisahan server state vs client state, serta implementasi mutasi optimistik.

---

## 1. Pertanyaan Konseptual Fundamental (Basic)

1. **Jelaskan perbedaan mendasar antara Stack Reconciler (React 15) dan Fiber Reconciler (React 16+)!** Masalah performa apa pada Main Thread browser yang berhasil dipecahkan oleh Fiber?
2. **Apa yang dimaksud dengan dua fase kerja React: Render Phase dan Commit Phase?** Mengapa Render Phase dapat dijeda atau dibatalkan, sementara Commit Phase wajib berjalan secara sinkron?
3. **Mengapa menggunakan `key={index}` (indeks array) pada daftar elemen dinamis yang dapat disortir atau dihapus dianggap sebagai antipattern berbahaya?**
4. **Jelaskan perbedaan mendasar antara Server State dan Client State!** Mengapa menyimpan data hasil query REST API di dalam store Redux/Zustand dinilai kurang ideal dibandingkan menggunakan TanStack Query?
5. **Apa perbedaan fungsi antara parameter `staleTime` dan `gcTime` (Garbage Collection Time) pada TanStack Query?**

---

## 2. Pertanyaan Analisis & Rekayasa Sistem (Intermediate)

6. **Mekanika Internal React Hooks (Rules of Hooks):**
   Jelaskan bagaimana Fiber Node menyimpan data state dari setiap hook menggunakan struktur data *Singly Linked List*! Mengapa melanggar aturan Hooks (memanggil hook di dalam percabangan `if-else` atau perulangan `for`) merusak urutan penelusuran pointer linked list tersebut?
7. **Penyelamatan Responsivitas Antarmuka dengan `useTransition`:**
   Bagaimana React membedakan pembaruan state berkategori **Urgent** (ketikan keyboard, klik tombol) dengan pembaruan berkategori **Transition** (penyaringan 50.000 data di latar belakang)? Apa peran flag `isPending` dalam meningkatkan kenyamanan visual pengguna?
8. **Anatomi Mutasi Optimistic UI dengan Automatic Rollback:**
   Jelaskan 3 langkah wajib yang harus dieksekusi di dalam hook `useMutation` TanStack Query:
   - Apa fungsi `queryClient.cancelQueries` pada saat `onMutate`?
   - Mengapa snapshot data lama wajib di-return dari `onMutate`?
   - Kapan tepatnya `queryClient.invalidateQueries` harus dipanggil?
9. **Deduplikasi Request Jaringan pada TanStack Query:**
   Jika sebuah dashboard menampilkan 4 widget berbeda yang semuanya memanggil `useUserQuery(['user', 'me'])` pada saat bersamaan, bagaimana QueryClient mencegah terjadinya 4 kali pemanggilan HTTP terpisah ke server?
10. **Zustand Atomic Selectors vs React Context API Re-render Trap:**
    Mengapa memperbarui satu nilai di React Context API dapat memicu render ulang massal pada seluruh komponen konsumen yang tidak menggunakan nilai tersebut? Bagaimana mekanisme *Selector Subscription* pada Zustand menghentikan pemborosan CPU ini?

---

## 3. Studi Kasus Skenario Produksi (Scenario-Based)

### Skenario A: Form Input yang Tertukar Pasca Hapus Baris Keranjang
Aplikasi kasir e-commerce memiliki daftar keranjang belanja dinamis. Setiap baris memiliki input kuantitas dan catatan khusus (*Custom Notes*). Developer menggunakan `key={index}` pada perulangan komponen baris barang.
Ketika kasir menghapus barang pertama di urutan teratas, barang kedua bergeser ke atas. Namun, catatan khusus dari barang pertama yang baru dihapus secara aneh tertinggal dan menempel pada barang kedua.
- **Identifikasi Akar Masalah:** Jelaskan bagaimana algoritma heuristik diffing React terkecoh oleh indeks array yang bergeser!
- **Solusi:** Tunjukkan perubahan kode JSX yang menjamin identitas state lokal melekat pada entitas produk asli (`item.id`)!

### Skenario B: UI Macet 400 ms saat Mengetik di Kolom Pencarian Filter
Sebuah aplikasi web direktori karyawan memiliki 25.000 profil staf. Ketika pengguna mengetik satu huruf di kolom pencarian, kursor membeku (*Freeze*) selama 400 milidetik sebelum huruf tersebut muncul di layar, karena aplikasi langsung memfilter 25.000 elemen dan me-render ulang DOM secara sinkron.
- **Analisis:** Mengapa rendering sinkron menghancurkan nilai metrik Core Web Vitals **INP (Interaction to Next Paint)**?
- **Rancang Solusi:** Tuliskan implementasi refaktorisasi komponen menggunakan `useTransition` atau `useDeferredValue` agar ketikan pengguna merespons instan (< 16 ms) sementara tabel hasil filter diperbarui secara asinkron di latar belakang!

### Skenario C: Saldo E-Wallet Kadaluwarsa pada Tab yang Ditinggal Tidur
Seorang pengguna membuka tab aplikasi investasi saham di browser laptopnya pada jam 09:00 pagi, lalu mengunci laptopnya. Pengguna kembali membuka laptop pada jam 15:00 sore. Tanpa me-refresh browser, pengguna melihat harga saham masih berada di harga pagi hari dan langsung melakukan transaksi jual.
- **Evaluasi Masalah:** Mengapa fetch data tradisional (`useEffect + fetch`) gagal menangani skenario ini?
- **Solusi:** Jelaskan bagaimana konfigurasi `refetchOnWindowFocus: true` dan pemanfaatan `staleTime` di TanStack Query secara otomatis mendeteksi kembalinya pengguna dan memperbarui data harga saham terbaru tanpa intervensi manual!

---

## 4. Chapter Challenge: Desain State Management Aplikasi Real-Time Collaborative Whiteboard

### Deskripsi Masalah
Sebagai Frontend Principal Engineer, Anda diminta merancang arsitektur state management untuk aplikasi papan tulis kolaboratif real-time (seperti Miro / Excalidraw):
1. **Client State (Lokal & Cepat):**
   - Posisi kursor mouse pengguna dan koordinat dragging bentuk (*Shapes*) yang bergerak pada kecepatan 120 FPS. Wajib bebas dari latensi dan tidak boleh membebani komponen lain.
2. **Server State (Sinkronisasi Remote):**
   - Daftar 10.000 objek bentuk kanvas yang tersimpan di database Postgres dan disinkronkan via WebSocket.
3. **Optimistic UI:**
   - Menghapus bentuk atau mengubah warna bentuk harus terjadi secara instan di layar pengguna dalam 0 ms, namun dapat di-rollback jika server menolak aksi tersebut (misal: objek sedang dikunci oleh pengguna lain).

### Instruksi Pengerjaan
Buat laporan arsitektur state yang memuat:
1. Pemilihan tool state management (Zustand Atomic Store vs TanStack Query) dan pemetaan batas tanggung jawabnya.
2. Struktur data Store Zustand untuk koordinat kursor dan selektor performa tinggi.
3. Alur diagram alir mutasi Optimistic UI lengkap dengan penanganan konflik jaringan.

---

## 5. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Arsitektur internal React Fiber: Time-slicing, struktur linked list fiber node, dan pemisahan Render vs Commit Phase.
- [ ] 2 aturan dasar algoritma heuristik Virtual DOM Diffing $O(N)$.
- [ ] Bahaya state corruption akibat penggunaan `key={index}`.
- [ ] Taksonomi 3 state web modern: Client State, Server State, dan URL State.
- [ ] Parameter siklus hidup caching TanStack Query: `staleTime`, `gcTime`, dan deduplikasi request.
- [ ] Mekanisme mutasi Optimistic UI dan automatic rollback saat kegagalan jaringan HTTP 500.

### Saya Tidak Perlu Menghafal:
- Seluruh konstanta biner flags internal React Fiber (cukup pahami konsep Placement, Update, dan Deletion).
- Kode implementasi source C++ V8 engine di balik event loop browser.

### Saya Harus Bisa Melakukan:
- [ ] Menggunakan `useTransition` untuk mengamankan responsivitas input pengguna pada aplikasi berat.
- [ ] Menulis custom mutation hook dengan TanStack Query yang mengimplementasikan `onMutate`, `onError`, dan `onSettled`.
- [ ] Mengonfigurasi micro-store Zustand dengan atomic selectors untuk menghentikan render ulang berlebih.
- [ ] Mendeteksi dan mengeliminasi kebocoran memori pada subscription `useEffect`.

---
[⬅️ Module 02: Server State vs Client State](./Module-02-Server-State-Client-State-dan-Optimistic-UI.md) | [📋 Silabus Induk](../README.md) | [BAB 03: Meta-Frameworks Next.js ➡️](../BAB-03-Meta-Frameworks-Nextjs-App-Router/Module-01-React-Server-Components-Streaming-SSR-Server-Actions.md)
---
