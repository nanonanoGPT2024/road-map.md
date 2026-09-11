---
[⬅️ Module 02: Next.js Multi-Layer Caching](./Module-02-Nextjs-Multi-Layer-Caching-dan-Edge-Middleware.md) | [📋 Silabus Induk](../README.md) | [BAB 04: End-to-End Type Safety ➡️](../BAB-04-End-to-End-Type-Safety-TypeScript-tRPC/Module-01-Advanced-TypeScript-Generics-Conditional-Types.md)
---

# BAB 03: Evaluasi Pemahaman, Quiz, & Tantangan Meta-Frameworks (Next.js App Router)

Selamat! Anda telah menyelesaikan **BAB 03: Full-Stack Frameworks & Meta-Frameworks (Next.js App Router)**. Lembar evaluasi ini menguji pemahaman mendalam Anda mengenai paradigma React Server Components (RSC), Streaming SSR dengan Suspense, Server Actions mutakhir, arsitektur 4 lapisan caching, serta eksekusi Edge Middleware.

---

## 1. Pertanyaan Konseptual Fundamental (Basic)

1. **Jelaskan perbedaan mendasar antara Server Components (Default) dan Client Components (`'use client'`) di Next.js App Router!** Mengapa Server Components memiliki ukuran bundle JavaScript 0 KB di browser klien?
2. **Apa yang dimaksud dengan Streaming SSR?** Masalah apa pada arsitektur SSR konvensional (*All-or-Nothing SSR*) yang berhasil dipecahkan menggunakan boundary React `<Suspense>`?
3. **Bagaimana cara kerja Server Actions (`'use server'`)?** Mengapa Server Actions meniadakan kebutuhan untuk membuat route handler API REST terpisah untuk formulir mutasi data?
4. **Sebutkan dan jelaskan 4 lapisan sistem caching pada Next.js App Router!**
5. **Apa yang membedakan Node.js Runtime biasa dengan Edge Runtime pada Next.js Middleware?** Mengapa library yang membutuhkan modul native `fs` dilarang dijalankan di Edge Middleware?

---

## 2. Pertanyaan Analisis & Rekayasa Sistem (Intermediate)

6. **On-Demand Revalidation: `revalidateTag()` vs `revalidatePath()`:**
   Dalam arsitektur e-commerce berskala 1.000.000 produk, mengapa menggunakan `revalidateTag('product-101')` jauh lebih efisien dan hemat komputasi server dibandingkan memanggil `revalidatePath('/products/[id]')`?
7. **Mekanisme Kerja Request Memoization (React `cache()`):**
   Jika 3 komponen anak yang berada di hierarki terpisah memanggil fungsi `fetch('https://api.internal/user')` dengan URL dan header yang identik di dalam satu siklus render halaman server, berapa kali request HTTP fisik yang benar-benar dieksekusi ke server API? Mengapa Request Memoization otomatis ter-reset pada request pengguna berikutnya?
8. **Dampak Pemanggilan `cookies()` atau `headers()` terhadap Caching:**
   Mengapa memanggil fungsi `cookies()` atau `headers()` di dalam Server Component secara otomatis mengubah rute halaman tersebut dari status *Static (Prerendered)* menjadi *Dynamic (Server-Rendered on Demand)*?
9. **Keamanan Server Actions (Validasi Skema):**
   Mengapa menganggap Server Action aman hanya karena dieksekusi di server adalah sebuah kesalahan fatal? Bagaimana peretas dapat memanggil Server Action secara langsung menggunakan tool cURL atau Postman tanpa melalui antarmuka formulir web?
10. **Edge Middleware Routing Guards:**
    Bagaimana mengeksekusi pemeriksaan token sesi JWT di Edge Middleware mampu memangkas waktu redirect pengguna yang belum terotentikasi dari 350 ms (server origin) menjadi $< 15 \text{ ms}$ (Edge PoP)?

---

## 3. Studi Kasus Skenario Produksi (Scenario-Based)

### Skenario A: Kebocoran Data Antar Pengguna di Halaman Profil
Sebuah platform perbankan digital membangun halaman profil nasabah di Next.js App Router: `/dashboard/profile`.
Developer mengambil data nasabah menggunakan kode:
```typescript
const user = await fetch('https://api.bank.com/user/me').then(r => r.json());
```
Setelah di-deploy ke server produksi, Pengguna A login dan melihat datanya sendiri. Namun satu menit kemudian, Pengguna B login dan secara mengejutkan melihat nomor rekening dan saldo milik Pengguna A di layarnya!
- **Identifikasi Masalah:** Lapisan cache Next.js mana yang secara keliru meng-cache response tersebut secara global (*Cross-User Data Leak*)?
- **Remediasi:** Tuliskan opsi fetch yang tepat (`cache: 'no-store'` atau penggunaan `cookies()`) untuk memastikan data profil selalu bersifat dinamis per request pengguna!

### Skenario B: Seluruh Halaman Tertahan Akibat Widget Rekomendasi Lambat
Sebuah marketplace memiliki halaman detail produk. Header dan spesifikasi produk dapat di-query dari database dalam waktu 15 ms. Namun, ada komponen "Rekomendasi AI Produk Serupa" di bagian bawah halaman yang membutuhkan waktu 3.500 ms (3.5 detik).
Sebelumnya, pengguna melihat layar putih kosong selama 3.5 detik sebelum seluruh halaman muncul bersamaan.
- **Solusi Arsitektur:** Rancang dekomposisi komponen menggunakan **Streaming SSR** dan `<Suspense fallback={<RecommendationSkeleton />}>` agar pembeli langsung dapat membaca deskripsi produk dalam 20 ms sementara rekomendasi AI mengalir menyusul di latar belakang!

### Skenario C: Harga Diskon Tidak Berubah Pasca Update Admin
Admin toko online mengubah harga diskon laptop dari Rp 20.000.000 menjadi Rp 15.000.000 di dashboard backoffice. Namun ketika admin membuka halaman produk di browser, harga yang tertampil tetap Rp 20.000.000 selama berjam-jam.
- **Investigasi:** Cek konfigurasi Data Cache dan Full Route Cache pada halaman produk tersebut!
- **Solusi:** Tunjukkan bagaimana menyematkan `next: { tags: ['product:laptop-01'] }` saat fetch dan memanggil `revalidateTag('product:laptop-01')` di dalam Server Action update produk untuk memperbarui cache secara seketika!

---

## 4. Chapter Challenge: Desain Global Multi-Region SaaS Dashboard

### Deskripsi Masalah
Sebagai Principal Full-Stack Architect, Anda diminta menyusun arsitektur frontend & meta-framework untuk platform SaaS Analytics Global:
1. **Edge Middleware Layer:**
   - Deteksi geolokasi negara (`x-vercel-ip-country` atau `cf-ipcountry`).
   - Otentikasi JWT Cookie: Jika token tidak ada atau tidak valid, redirect seketika ke `/auth/login` di Edge terdekat dengan latensi $< 20 \text{ ms}$.
2. **Hybrid Rendering Strategy:**
   - Navbar, Sidebar, dan Shell Halaman: Di-cache 100% statis di Full Route Cache.
   - Grafik Metrik Utama: Streaming SSR dengan Suspense.
   - Tombol Export PDF Laporan: Client Component yang memicu Server Action mutasi.
3. **Multi-Layer Caching Architecture:**
   - Rancang skema invalidasi on-demand berbasis tag (`revalidateTag`) saat pengguna menambahkan data transaksi baru.

---

## 5. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Batasan dan aturan penggunaan React Server Components (RSC) vs Client Components (`'use client'`).
- [ ] Mekanisme Streaming SSR dengan React `<Suspense>` via HTTP Chunked Transfer Encoding.
- [ ] Cara kerja Server Actions (`'use server'`) untuk mutasi formulir tanpa REST API terpisah.
- [ ] 4 lapisan sistem caching Next.js: Request Memoization, Data Cache, Full Route Cache, dan Router Cache.
- [ ] Perbedaan time-based revalidation (`revalidate: N`) vs on-demand tag revalidation (`revalidateTag`).
- [ ] Arsitektur Edge Middleware dan batasan runtime V8 Isolate.

### Saya Tidak Perlu Menghafal:
- Format string biner payload serialisasi internal React Flight protocol (cukup pahami konsep alirannya).
- Seluruh ratusan opsi compiler Next.js di `next.config.js`.

### Saya Harus Bisa Melakukan:
- [ ] Mengomposisikan Server Component dengan Client Component secara aman tanpa membocorkan kode server ke browser.
- [ ] Mengalirkan komponen lambat menggunakan Suspense boundary untuk mengamankan nilai Core Web Vitals (LCP/FCP).
- [ ] Menulis Server Action yang memvalidasi input skema Zod dan mengeksekusi `revalidatePath` / `revalidateTag`.
- [ ] Menulis file `middleware.ts` yang memvalidasi cookie sesi dan menyematkan security headers di Edge.

---
[⬅️ Module 02: Next.js Multi-Layer Caching](./Module-02-Nextjs-Multi-Layer-Caching-dan-Edge-Middleware.md) | [📋 Silabus Induk](../README.md) | [BAB 04: End-to-End Type Safety ➡️](../BAB-04-End-to-End-Type-Safety-TypeScript-tRPC/Module-01-Advanced-TypeScript-Generics-Conditional-Types.md)
---
