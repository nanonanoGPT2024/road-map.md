---
[⬅️ BAB 02 Quiz & Challenge](../BAB-02-React-Internals-dan-State-Management/BAB-02-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Next.js Multi-Layer Caching ➡️](./Module-02-Nextjs-Multi-Layer-Caching-dan-Edge-Middleware.md)
---

# Module 01: React Server Components (RSC), Streaming SSR, & Server Actions

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Menguasai paradigma revolusioner **React Server Components (RSC)**: membedakan peran dan batasan eksekusi antara **Server Components (Default)** vs **Client Components (`'use client'`)**.
- Memahami mengapa Server Components memiliki **Nol Ukuran Bundle JavaScript Klien (Zero-Bundle-Size Overhead)** dan mampu mengakses database langsung tanpa mengekspos API endpoints publik.
- Menguasai teknik **Streaming SSR** menggunakan boundary `<Suspense>` untuk mengalirkan potongan HTML secara progresif dari server ke browser melalui satu koneksi HTTP berkelanjutan.
- Menguasai paradigma mutasi data mutakhir: **Server Actions (`'use server'`)** untuk menangani form submission, validasi, dan cache revalidation tanpa memerlukan REST API controller terpisah.
- Memahami format serialisasi data **RSC Flight Protocol Payload** yang dikirimkan antara server dan browser saat navigasi transisi halaman.

---

## 2. Prerequisite
- Memahami siklus render SSR tradisional dan proses Hydration (BAB 01).
- Memahami React Fiber dan Virtual DOM diffing (BAB 02).
- Dasar arsitektur database query SQL / ORM (Backend BAB 04 & 05).

---

## 3. Concept
Selama satu dekade (2013-2023), ekosistem React membagi dunia aplikasi web menjadi dua kutub:
- Backend: Menulis REST / GraphQL API endpoints.
- Frontend: Mengunduh bundle JavaScript besar, memanggil API via `fetch`, dan me-render UI di browser.

Paradigma ini memicu masalah besar yang disebut **Network Waterfall**: komponen induk melakukan fetch data, selesai, me-render komponen anak, komponen anak melakukan fetch data lagi, memicu rangkaian latensi jaringan bertingkat yang lambat.

Next.js App Router dan **React Server Components (RSC)** menyatukan kedua dunia ini ke dalam satu model komputasi terpadu:
- Komponen dieksekusi **murni di server**. Komponen dapat langsung menjalankan query SQL atau memanggil Redis di dalam fungsi komponen (`async function ProductPage() { const products = await db.select()... }`).
- Kode logika server, library parsing berat (seperti markdown parser atau formatters), dan kredensial database **tidak pernah dikirim ke browser**. Ukuran bundle JavaScript klien tetap ramping (0 KB overhead untuk Server Components).
- Hanya bagian antarmuka yang membutuhkan interaktivitas pengguna (seperti tombol klik, event listeners, atau `useState`) yang ditandai dengan direktif `'use client'`.

---

## 4. Why?
Tanpa pemahaman RSC dan Streaming SSR:
1. **Kebocoran Kredensial Database ke Browser:** Developer pemula mencoba memanggil query database langsung di dalam komponen yang salah dideklarasikan sebagai Client Component, mengekspos connection string database ke tab Network browser!
2. **Keterlambatan Halaman Lambat (*All-or-Nothing SSR*):** Pada SSR tradisional, jika ada satu widget rekomendasi lambat yang membutuhkan waktu 3 detik untuk query database, seluruh halaman HTML tertahan selama 3 detik sebelum satu byte pun dikirim ke browser pengguna.
3. **Duplikasi Kode API yang Membosankan:** Menulis API route `/api/products`, membuat controller, membuat DTO, lalu menulis `fetch('/api/products')` di frontend hanya untuk menampilkan daftar produk sederhana.
4. **Ukuran Bundle Browser yang Membengkak:** Mengimpor library kalkulasi matematika seberat 300 KB ke dalam aplikasi hanya untuk memformat satu angka laporan, membebani kuota data internet pengguna mobile.

---

## 5. What? (Komparasi Server Components vs Client Components)

| Fitur & Karakteristik | Server Component (Default) | Client Component (`'use client'`) |
|---|---|---|
| **Tempat Eksekusi** | **Hanya di Server** (Node.js / Edge runtime)| Di Server (pre-render awal) DAN di Browser Klien |
| **Akses Database / Secrets**| **Bisa Langsung** (`db.query()`, env rahasia)| **Dilarang Keras** (Kredensial akan bocor ke publik) |
| **Dampak Ukuran Bundle JS Klien**| **0 KB (Zero Bundle Size)** | Menambah ukuran file bundle JavaScript klien |
| **Dukungan React Hooks** | Tidak Bisa (`useState`, `useEffect` dilarang)| **Bisa Penuh** (`useState`, `useEffect`, Custom Hooks)|
| **Interaktivitas DOM Browser** | Tidak Ada (Hanya menghasilkan markup statis)| **Bisa Penuh** (`onClick`, `onChange`, Web APIs) |
| **Format Serialisasi** | Dikirim sebagai stream **RSC Payload** | Dikirim sebagai file JavaScript + HTML Hydration |

---

## 6. How? (Arsitektur Streaming SSR dengan React Suspense)

Streaming SSR memecahkan masalah *All-or-Nothing SSR* dengan memanfaatkan fitur **HTTP Chunked Transfer Encoding**:

```
[ HTTP GET /dashboard ]
            │
            ▼
 ┌────────────────────────────────────────────────────────┐
 │ SERVER MERENDER CANGKANG CEPAT (SHELL)                 │
 │ - Layout navigasi, Header, Footer                      │
 │ - Komponen lambat dibungkus <Suspense fallback={<Skel/>}│
 └──────────────────────────┬─────────────────────────────┘
                            │
                            ▼ (CHUNKS PERTAMA DIKIRIM INSTAN! ~20 ms)
 ┌────────────────────────────────────────────────────────┐
 │ BROWSER MENERIMA & LANGSUNG MERENDER LAYAR:            │
 │ - Pengguna langsung melihat Header, Navigasi, &        │
 │   Skeleton Loader animasi berputar (LCP Terjaga Baik!) │
 └────────────────────────────────────────────────────────┘
                            │
              (Query Database Lambat Selesai: 800 ms)
                            │
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │ SERVER MENGALIRKAN CHUNK KEDUA MELALUI KONEKSI SAMA:   │
 │ - <script> menyuntikkan HTML konten asli dan mengganti │
 │   elemen skeleton secara otomatis tanpa reload!        │
 └────────────────────────────────────────────────────────┘
```

---

## 7. Analogy
- **SSR Tradisional ibarat Makanan Pesanan Khusus di Meja:** Pelayan restoran tidak akan membawa piring apa pun ke meja Anda sampai seluruh 5 hidangan (nasi, ayam, sup, sambal, jus) selesai dimasak. Jika sup butuh waktu 30 menit, Anda duduk bengong kelaparan di depan meja kosong selama 30 menit.
- **Streaming SSR dengan Suspense ibarat Meja Prasmanan yang Mengalir:** Pelayan langsung membawakan sepiring nasi putih hangat dan air putih dalam 10 detik (**Cangkang Cepat**). Anda bisa langsung makan nasi, sementara pelayan secara bertahap membawakan ayam panggang dan sup begitu matang dari kompor (**Streaming Chunks**).
- **Server Actions ibarat Pelayan yang Mengantar Formulir Langsung ke Dapur:** Anda tidak perlu keluar restoran mencari kantor kurir pos untuk mengirimkan pesanan tambahan; pelayan mengambil kertas formulir dari meja Anda dan langsung menyerahkannya ke koki di dapur.

---

## 8. Diagram: Alur Kerja Server Actions (`'use server'`)

```
[ BROWSER KLIEN ]                                    [ NEXT.JS SERVER ]
       │                                                      │
 1. Pengguna Submit Form:                                     │
    <form action={createInvoiceAction}>                       │
       │                                                      │
       ▼ (Otomatis mengirim HTTP POST di latar belakang       │
          membawa data form terenkripsi / FormData)           │
       │ ──POST /dashboard (Action ID: $ACTION_ID_88)────────▶│
       │                                                      │
       │                                             2. Eksekusi 'use server':
       │                                                - Validasi Zod
       │                                                - Otentikasi Sesi
       │                                                - INSERT INTO invoices
       │                                                - revalidatePath('/dashboard')
       │                                                      │
       │◀── Stream Response: RSC Payload Baru (Data Terupdate)┘
       │
 3. React memutakhirkan tampilan UI
    secara otomatis tanpa Full Page Reload!
```

---

## 9. Simple Example: Komposisi Server Component & Client Component

```tsx
// 1. FILE: components/LikeButton.tsx (CLIENT COMPONENT)
// Ditandai dengan 'use client' karena membutuhkan interaktivitas onClick & useState
'use client';

import { useState } from 'react';

export function LikeButton({ initialLikes }: { initialLikes: number }) {
  const [likes, setLikes] = useState(initialLikes);

  return (
    <button onClick={() => setLikes(likes + 1)} className="btn-like">
      ❤️ Disukai: {likes}
    </button>
  );
}

// 2. FILE: app/products/[id]/page.tsx (SERVER COMPONENT - DEFAULT)
// Komponen ini async dan mengakses database server secara langsung!
import { db } from '@/lib/db';
import { LikeButton } from '@/components/LikeButton';

export default async function ProductDetailPage({ params }: { params: { id: string } }) {
  // Query database langsung di server! Tanpa butuh fetch() atau API Route!
  const product = await db.query('SELECT * FROM products WHERE id = $1', [params.id]);

  return (
    <main className="container">
      <h1>{product.title}</h1>
      <p>{product.description}</p>
      <p className="price">Harga: Rp {product.price.toLocaleString('id-ID')}</p>
      
      {/* Mengoper data server ke Client Component via props */}
      <LikeButton initialLikes={product.likesCount} />
    </main>
  );
}
```

---

## 10. Practical Example: Implementasi Streaming SSR & Server Action Mutasi

```tsx
// FILE: app/invoices/page.tsx
import { Suspense } from 'react';
import { revalidatePath } from 'next/cache';
import { db } from '@/lib/db';

// SERVER ACTION: Fungsi mutasi data murni di server
async function createInvoiceAction(formData: FormData) {
  'use server';

  const customerName = formData.get('customerName') as string;
  const amount = Number(formData.get('amount'));

  // Eksekusi mutasi langsung ke database
  await db.query('INSERT INTO invoices (customer, amount) VALUES ($1, $2)', [customerName, amount]);

  // Hancurkan cache halaman dan revalidasi data baru secara instan!
  revalidatePath('/invoices');
}

// KOMPONEN LAMBAT (Mengambil data histori transaksi yang berat)
async function SlowInvoiceTable() {
  await new Promise(r => setTimeout(r, 2000)); // Simulasi query lambat 2 detik
  const invoices = await db.query('SELECT * FROM invoices ORDER BY created_at DESC');

  return (
    <table className="table">
      {invoices.map((inv: any) => (
        <tr key={inv.id}>
          <td>{inv.customer}</td>
          <td>Rp {inv.amount.toLocaleString('id-ID')}</td>
        </tr>
      ))}
    </table>
  );
}

export default function InvoicesPage() {
  return (
    <div className="p-6">
      <h1>Manajemen Faktur & Tagihan</h1>

      {/* Form terhubung langsung ke Server Action */}
      <form action={createInvoiceAction} className="my-4">
        <input name="customerName" placeholder="Nama Pelanggan" required />
        <input name="amount" type="number" placeholder="Nominal" required />
        <button type="submit">Buat Faktur</button>
      </form>

      <h2>Riwayat Faktur</h2>
      {/* STREAMING SSR: Skeleton muncul instan, data tabel menyusul via chunked stream */}
      <Suspense fallback={<div className="animate-pulse">Memuat tabel faktur dari server...</div>}>
        <SlowInvoiceTable />
      </Suspense>
    </div>
  );
}
```

---

## 11. Real World Example: Optimalisasi Halaman Produk E-Commerce Skala Besar

Pada platform marketplace dengan jutaan pengunjung:
- Halaman produk memiliki 3 bagian:
  1. Header, Gambar, dan Spesifikasi Teknis (Statis dan sangat cepat).
  2. Status Stok & Promo Flash Sale (Dinamis dari Redis, latensi 15 ms).
  3. Ulasan Pengguna & Rekomendasi Mesin AI (Komputasi berat, latensi 1.800 ms).
- Solusi Arsitektur RSC:
  - Seluruh halaman adalah Server Component.
  - Bagian 1 dan 2 dikirimkan seketika dalam **First Contentful Paint (FCP) di bawah 200 ms**. Pembeli langsung dapat melihat foto produk dan harga diskon.
  - Bagian 3 dibungkus dengan `<Suspense fallback={<ReviewSkeleton />}>`.
- Hasil: Pembeli tidak pernah melihat layar putih kosong; konversi penjualan meningkat 18% karena waktu respons halaman terasa instan.

---

## 12. Trade-offs

| Aspek Arsitektural | Single Page App (CSR murni) | Next.js Pages Router (SSR Lama) | Next.js App Router (RSC Modern) |
|---|---|---|---|
| **Ukuran Bundle JS Klien** | Sangat Besar (Seluruh app di JS) | Menengah | **Paling Ringan (Server Comps = 0 KB)** |
| **Kecepatan FCP** | Lambat (Menunggu unduh JS) | Cepat (HTML dari server) | **Paling Cepat (Streaming Shell)** |
| **Kebutuhan API Endpoints** | Wajib Buat REST/GraphQL API | Wajib Buat API Routes | **Minimal (Bisa langsung Server Actions)** |
| **Batas Mental Pemrogram** | Sederhana (Semua jalan di browser)| Sedang (Pemisahan SSR & Klien) | **Tinggi (Harus paham batas Server vs Klien)**|
| **Dukungan Library Pihak Ketiga**| Universal (Semua library jalan)| Universal | Terbatas (Library UI lama butuh 'use client')|

---

## 13. When To Use
- **Gunakan Server Components (Default):** Untuk 80-90% komponen aplikasi Anda (komponen layout, navigasi statis, render konten teks, tabel data hasil query DB, footer).
- **Gunakan Client Components (`'use client'`):** Hanya saat komponen membutuhkan:
  - Event listeners (`onClick`, `onSubmit`, `onKeyDown`).
  - React State Hooks (`useState`, `useReducer`, `useEffect`).
  - Akses Web APIs browser murni (`window`, `localStorage`, `geolocation`).
- **Gunakan Server Actions:** Untuk menangani formulir entri data, mutasi CRUD, tombol toggle status, dan operasi backend yang membutuhkan revalidasi cache instan.

---

## 14. When NOT To Use
- **Jangan Beri Label `'use client'` di Seluruh File Secara Global:** Memasang `'use client'` di baris paling atas `app/layout.tsx` akan membatalkan seluruh manfaat React Server Components dan mengubah aplikasi Anda kembali menjadi CSR yang lambat! Dorong Client Component sejauh mungkin ke ujung daun pohon komponen (*Leaves of the Tree*).
- **Jangan Gunakan Server Actions untuk Polling Frekuensi Tinggi Real-Time:** Menjalankan polling data setiap 100 milidetik via Server Actions akan membebani serverless backend secara berlebihan. Gunakan WebSockets atau Server-Sent Events (SSE).

---

## 15. Common Mistakes
1. **Mengimpor Fungsi Server di Client Component:** Mengimpor modul database (`import { db } from '@/lib/db'`) di dalam file yang memiliki deklarasi `'use client'`. Next.js build compiler akan langsung memblokir kompilasi untuk mencegah kebocoran kode server ke browser.
2. **Melewatkan Suspense Boundary pada Komponen Asinkron:** Menggunakan `await` pada komponen anak tanpa membungkusnya dengan `<Suspense>`, menyebabkan seluruh halaman tertahan dan membatalkan manfaat streaming.
3. **Mengabaikan Validasi Input pada Server Actions:** Mengira bahwa karena fungsi berjalan di server, parameter `formData` sudah pasti aman. Penyerang dapat memanggil Server Actions secara langsung via HTTP POST dengan parameter buatan! **Wajib lakukan validasi skema via Zod di dalam Server Action!**

---

## 16. Best Practices

### Must Have
- Perlakukan Server Actions sama seperti Endpoint API Publik: Selalu lakukan **Autentikasi Sesi** dan **Validasi Skema (Zod)** di baris pertama setiap Server Action.
- Bungkus setiap komponen yang melakukan fetch asinkron lambat dengan boundary `<Suspense fallback={<Skeleton />}>`.
- Simpan komponen interaktif kecil (seperti SearchBar atau CounterButton) di dalam direktori `components/client/` terisolasi.

### Recommended
- Manfaatkan fungsi `revalidatePath()` atau `revalidateTag()` setelah mutasi Server Action untuk memperbarui cache halaman secara selektif.
- Gunakan hook `useActionState` dan `useFormStatus` (React 19 / Next.js 14+) untuk menangani status pending submit dan umpan balik error formulir secara elegan.

### Advanced
- Gabungkan Server Actions dengan **Optimistic UI Updates** menggunakan hook `useOptimistic` untuk menghadirkan umpan balik visual instan di sisi klien sebelum Server Action selesai dikonfirmasi oleh database server.

---

## 17. Troubleshooting

| Gejala Error | Indikasi Akar Masalah | Langkah Investigasi | Tindakan Perbaikan |
|---|---|---|---|
| **Error: `You're importing a component that needs useState...`** | Menggunakan hooks di dalam komponen yang tidak memiliki deklarasi `'use client'` | Cek file komponen yang disebutkan di stack trace | Tambahkan baris string `'use client';` di baris paling pertama file |
| **Build Error: `Cannot resolve module 'fs' or 'net'`** | Library backend Node.js murni terimpor secara tidak sengaja ke Client Component | Periksa pohon impor di file client | Pindahkan logika pemanggilan library Node.js ke Server Action atau Server Component |
| **Server Action Gagal: `Failed to find Server Action`** | ID hash fungsi Server Action berubah pasca deployment baru sementara browser masih membuka versi lama | Periksa versi deployment di log server | Implementasikan penanganan retry otomatis atau tampilkan dialog reload versi baru aplikasi |

---

## 18. Exercise
1. Bangun simulasi Node.js murni yang memodelkan **HTTP Chunked Streaming SSR**: kirimkan header dan kerangka dasar halaman dalam chunk 1, lalu setelah jeda 1 detik kirimkan chunk 2 berisi data konten dan script injeksi DOM.
2. Implementasikan simulator validasi Server Action dengan skema Zod dan buktikan eksekusi gagal jika input nominal bernilai negatif.
3. Rancang pembagian hierarki komponen untuk halaman profil pengguna: tentukan komponen mana yang Server Component dan mana yang Client Component.

---

## 19. Challenge
Rancang arsitektur Full-Stack Next.js 14 App Router untuk platform lelang online real-time (*Live Auction Platform*):
1. Halaman lelang harus memadukan foto barang beresolusi tinggi (Statis via CDN), riwayat penawaran terakhir (Streaming SSR via Suspense), dan tombol "Ajukan Tawaran / Bid Now" (Client Component dengan Server Action mutasi).
2. Terapkan hook `useOptimistic` agar nominal tawaran penawar melonjak instan di layarnya sebelum dikonfirmasi oleh database PostgreSQL transaksi!

---

## 20. Summary
React Server Components dan Streaming SSR bukan sekadar pembaruan sintaks minor, melainkan reposisi mendasar cara kerja aplikasi web modern. Dengan memindahkan beban komputasi berat dan query database ke server, merampingkan bundle JavaScript browser hingga nol kilobyte untuk komponen statis, serta menyatukan mutasi data via Server Actions, seorang Full-Stack Architect mampu membangun produk digital dengan kecepatan akses, keamanan, dan keindahan interaksi yang belum pernah terbayangkan sebelumnya.

---
[⬅️ BAB 02 Quiz & Challenge](../BAB-02-React-Internals-dan-State-Management/BAB-02-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Next.js Multi-Layer Caching ➡️](./Module-02-Nextjs-Multi-Layer-Caching-dan-Edge-Middleware.md)
---
