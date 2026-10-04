---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 11**: `ReadonlyArray<RouteRecordRaw>` — Mengunci array konfigurasi secara statis menggunakan TypeScript compiler untuk mencegah manipulasi array di runtime tanpa melalui API resmi router.
* **Baris 15**: `component: () => import('@/views/DashboardView.vue')` — Pemisahan bundle (*Dynamic Code Splitting*). Vite/Webpack memisahkan file ini menjadi chunk JavaScript terisolasi yang hanya diunduh ketika rute aktif.
* **Baris 16–19**: `meta: { requiresAuth: true, roles: [...] }` — Pemanfaatan `RouteMeta` interface untuk menginjeksi metadata kustom yang akan dibaca oleh *Navigation Guards*.
* **Baris 29**: `path: '/:pathMatch(.*)*'` — Parameter *catch-all regex*. Tanda kurung mendefinisikan regex penangkap, dan tanda bintang (`*`) menandai parameter dapat berulang, menangkap URL hirarkis seperti `/foo/bar/baz` yang tidak cocok dengan rute lain.
* **Baris 38–46**: `scrollBehavior(to, from, savedPosition)` — Logika restorasi posisi gulir native. Menjamin bila pengguna menggunakan tombol back/forward browser, koordinat scroll dikembalikan ke titik simpanan `savedPosition`.
* **Baris 51–64**: `router.beforeEach(async (to, from) => ...)` — Tidak lagi menggunakan argumen `next()`. Vue Router 4 mengadopsi sintaksis modern berbasis Promise return values. Mengembalikan `true` menyetujui navigasi, `false` membatalkannya, dan rute objek memicu *redirection loop safe*.

---

## SEKSI 09 — STUDI KASUS NYATA (Enterprise ERP / Banking)

### Konteks Skenario
Aplikasi Core Banking memiliki 15 domain sub-sistem (Treasury, Ledger, AML/CFT, Loans, Audit). 
Tantangan Teknis:
1. Bundle monolithic mencapai 18MB jika seluruh rute didaftarkan di muka (*upfront*).
2. Setiap pengguna memiliki konfigurasi hak akses granular (ACL) yang divalidasi ke server. Menu dan rute yang tidak diizinkan tidak boleh terdaftar di runtime router guna memitigasi *source code sniffing*.
3. Akses token memiliki waktu kedaluwarsa singkat (5 menit) dengan mekanisme *silent refresh* yang harus terintegrasi tanpa memutus pipeline navigasi.

### Arsitektur Solusi
Membangun **Dynamic Hierarchical RBAC Router Manager**. Rute terdaftar secara kosong pada awal *bootstrap*. Navigasi guard pertama mencegat alur, mengeksekusi sesi pengguna, memuat manifest rute yang diizinkan dari backend, memanggil `router.addRoute()` secara dinamis, lalu melakukan *idempotent retry navigation*.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi skala industri untuk sistem perutean dinamis berbasis izin dan token refresh race-condition safe:

### 1. Definisi Tipe Meta Aman (Type Augmentation)
