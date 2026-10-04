---
[⬅️ Module 01: RSC, Streaming SSR, & Server Actions](./Module-01-React-Server-Components-Streaming-SSR-Server-Actions.md) | [📋 Silabus Induk](../README.md) | [BAB 03 Quiz & Challenge ➡️](./BAB-03-Quiz-dan-Challenge.md)
---

# Module 02: Next.js Multi-Layer Caching, Revalidasi Dinamis, & Edge Middleware

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Menguasai anatomi arsitektur **Next.js 4-Tier Caching System**: **Request Memoization**, **Data Cache**, **Full Route Cache**, dan **Router Cache**.
- Memahami siklus hidup dan perbedaan mekanisme **Time-Based Revalidation** (`next: { revalidate: 60 }`) vs **On-Demand Revalidation** (`revalidateTag()` vs `revalidatePath()`).
- Mengetahui kapan dan bagaimana mematikan caching secara eksplisit (**Opt-out Caching**) menggunakan `export const dynamic = 'force-dynamic'` atau `noStore()`.
- Menguasai eksekusi **Edge Middleware**: komputasi V8 Isolate di titik kehadiran jaringan terdistribusi (*Edge Points of Presence*) untuk autentikasi rute, deteksi geolokasi, dan A/B testing.
- Menganalisis batasan runtime: **Node.js Full Runtime** vs **Edge Runtime** (ketiadaan API native seperti `fs` atau `child_process`).

---

## 2. Prerequisite
- Memahami konsep React Server Components (RSC) dan Server Actions (Modul 01).
- Pemahaman hierarki caching L1/L2, RAM, dan HTTP Cache-Control (Backend BAB 06).
- Pemahaman routing HTTP, cookie sesi, dan redirect URL.

---

## 3. Concept
Next.js App Router bukan sekadar framework rendering; Next.js adalah **sistem komputasi berbasis cache berlapis (*Opinionated Multi-Layer Caching Engine*)**.

Tujuan desain Next.js adalah: secara default, seluruh halaman dan pengambilan data bersifat **Statis dan Di-cache secara Agresif** demi mencapai performa latensi milidetik dan biaya komputasi server seminimal mungkin.

Namun, agresivitas caching ini sering menjadi sumber kebingungan terbesar bagi pengembang yang belum memahami arsitekturnya: *"Mengapa data di database sudah saya ubah, tetapi di browser tampilannya tidak pernah berubah?"*

Untuk mengendalikan sistem ini, seorang Full-Stack Architect harus memahami dengan presisi pada lapisan mana data disimpan, berapa lama masa berlakunya, dan pemicu apa yang mampu membatalkan (*invalidate*) cache tersebut.

---

## 4. Why?
Tanpa pemahaman mendalam tentang Next.js Caching & Edge Middleware:
1. **Kebocoran Data Antar Pengguna (*Cross-User Data Bleed*):** Meng-cache halaman profil pengguna yang seharusnya dinamis ke dalam Full Route Cache statis, menyebabkan Pengguna B melihat data privasi milik Pengguna A.
2. **Latensi Redirect Lambat:** Melakukan pemeriksaan autentikasi dan redirect URL di dalam serverless function di region us-east-1 yang jauh (latensi 400 ms), alih-alih mengeksekusinya di **Edge Middleware** terdekat dengan ISP pengguna (latensi 15 ms).
3. **Database Overload Akibat `force-dynamic` yang Berlebihan:** Karena frustrasi dengan cache, developer memasang `force-dynamic` di seluruh halaman aplikasi, menghancurkan performa TTFB dan membanjiri database dengan ribuan query duplikat.
4. **Stale Data pada Katalog E-Commerce:** Harga barang yang sudah diganti di database admin tetap menampilkan harga diskon lama selama berhari-hari karena developer tidak memasang tag revalidasi.

---

## 5. What? (Anatomi 4 Lapisan Cache Next.js)

```
                       ┌────────────────────────────────────────────────────────┐
                       │ 1. ROUTER CACHE (SISI KLIEN / BROWSER MEMORY)          │
                       │ - Menyimpan RSC payload di memori tab browser user.    │
                       │ - Bertahan selama sesi browsing aktif.                 │
                       └──────────────────────────┬─────────────────────────────┘
                                                  │ (Cache Miss di Browser)
                                                  ▼
                       ┌────────────────────────────────────────────────────────┐
                       │ 2. FULL ROUTE CACHE (SISI SERVER)                      │
                       │ - Menyimpan HTML statis & RSC payload utuh di disk/mem │
                       │ - Di-generate saat Build Time atau ISR Revalidation.   │
                       └──────────────────────────┬─────────────────────────────┘
                                                  │ (Halaman Dinamis / Dynamic Render)
                                                  ▼
                       ┌────────────────────────────────────────────────────────┐
                       │ 3. REQUEST MEMOIZATION (REACT RENDER LIFECYCLE)        │
                       │ - Men-deduplikasi fungsi fetch() dengan URL & opsi     │
                       │   yang identik selama SATU kali siklus render pohon.   │
                       │ - Umur: Hanya selama request diproses (< 100 ms).      │
                       └──────────────────────────┬─────────────────────────────┘
                                                  │ (Panggilan Fetch Pertama)
                                                  ▼
                       ┌────────────────────────────────────────────────────────┐
                       │ 4. DATA CACHE (PERSISTEN LINTAS REQUEST / SERVER)      │
                       │ - Menyimpan hasil fetch data lintas pengguna & request.│
                       │ - Diatur via 'revalidate: seconds' atau 'tags: [...]'. │
                       └────────────────────────────────────────────────────────┘
```

| Lapisan Cache | Lokasi Penyimpanan | Umur Siklus Hidup | Cara Mengabaikan / Invalidate |
|---|---|---|---|
| **Request Memoization** | Server Memory (React) | 1 Siklus Render Request | Otomatis reset tiap request baru |
| **Data Cache** | Server Persistent Store | Persisten (Bisa permanen) | `revalidateTag()`, `revalidatePath()`, `no-store` |
| **Full Route Cache** | Server Storage (HTML/RSC) | Persisten | Revalidasi Data Cache terkait atau redeploy |
| **Router Cache** | Browser RAM Klien | Sesi Navigasi (~30s dinamis, 5m statis) | `router.refresh()`, Server Action revalidate |

---

## 6. How? (Strategi Revalidasi & Edge Middleware)

### A. Strategi Revalidasi Data Cache

#### 1. Time-Based Revalidation (Cocok untuk Berita / Data Berkala)
```typescript
// Data di-cache selama 60 detik. Request berikutnya setelah 60s memicu revalidasi background
const res = await fetch('https://api.crypto.com/rates', {
  next: { revalidate: 60 }
});
```

#### 2. On-Demand Revalidation dengan Tags (Standar Emas Enterprise)
```typescript
// 1. Ambil data dengan label tag spesifik
const res = await fetch('https://api.store.com/products/88', {
  next: { tags: ['product-88', 'products'] }
});

// 2. Di tempat lain (misal di Server Action saat admin mengupdate stok):
import { revalidateTag } from 'next/cache';

export async function updateProductStock(id: string) {
  'use server';
  await db.updateStock(id);
  revalidateTag(`product-${id}`); // HANYA cache produk ini yang dihanguskan!
}
```

### B. Arsitektur Edge Middleware
Edge Middleware dieksekusi **sebelum** sebuah request menyentuh routing pages atau cache server. Berjalan pada runtime V8 Isolate yang sangat ringan di ratusan lokasi global (*Cloudflare / Vercel Edge*).

```typescript
// FILE: middleware.ts (di root project)
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/request';

export function middleware(request: NextRequest) {
  const token = request.cookies.get('session_token')?.value;

  // 1. ROUTE GUARD: Proteksi rute private
  if (request.nextUrl.pathname.startsWith('/dashboard')) {
    if (!token) {
      // Redirect instan di Edge terdekat dalam 10 ms!
      return NextResponse.redirect(new URL('/login', request.url));
    }
  }

  // 2. A/B TESTING: Distribusi variasi antarmuka berdasarkan cookie
  const response = NextResponse.next();
  if (!request.cookies.has('ab_bucket')) {
    const bucket = Math.random() < 0.5 ? 'variant-A' : 'variant-B';
    response.cookies.set('ab_bucket', bucket);
  }

  // 3. SECURITY HEADERS
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('X-Content-Type-Options', 'nosniff');

  return response;
}

export const config = {
  matcher: ['/dashboard/:path*', '/checkout/:path*']
};
```

---

## 7. Analogy
- **Request Memoization ibarat Menulis di Kertas Coretan saat Belanja:** Anda butuh tahu harga beras di 3 resep masakan berbeda. Anda cukup menanyakan harga beras sekali ke kasir, lalu mencatatnya di kertas memo saku. Anda tidak perlu lari bolak-balik bertanya ke kasir 3 kali dalam menit yang sama.
- **Data Cache ibarat Lemari Arsip Kantor:** Laporan keuangan dicetak dan disimpan di lemari. Siapapun karyawan yang meminta salinannya akan diberikan fotokopi dari lemari arsip tersebut tanpa perlu menghitung ulang dari buku besar.
- **On-Demand `revalidateTag` ibarat Tombol Alarm di Lemari Arsip:** Saat auditor menemukan kesalahan cetak pada dokumen 'pajak-2026', auditor menekan tombol `revalidateTag('pajak-2026')`. Mesin penghancur kertas otomatis memusnahkan dokumen tersebut dan mencetak versi terbaru.
- **Edge Middleware ibarat Satpam Gerbang Kompleks Perumahan:** Satpam berdiri di pintu gerbang terdepan jalan raya. Sebelum mobil Anda masuk ke dalam kompleks (Server Utama), satpam memeriksa kartu akses Anda. Jika Anda tidak punya kartu, Anda langsung disuruh putar balik di gerbang (**Redirect di Edge**) tanpa membebani jalanan di dalam kompleks.

---

## 8. Diagram: Alur Penanganan Request melalui Edge Middleware & Cache Layers

```
[ Request Browser Pengguna ]
             │
             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 1. EDGE MIDDLEWARE (V8 Isolate)                        │
 │ - Validasi Auth Cookie, Geo-routing, Bot protection    │
 └──────────────────────────┬─────────────────────────────┘
                            │ (Lolos Validasi)
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │ 2. FULL ROUTE CACHE EVALUATION                         │
 │ - Apakah halaman berstatus Static (SSG/ISR)?           │
 └──────────────────────────┬─────────────────────────────┘
               ┌────────────┴────────────┐
           (HIT: Statis)             (MISS: Dinamis)
               │                         │
               ▼                         ▼
 ┌───────────────────────────┐ ┌────────────────────────────────────────┐
 │ Kembalikan HTML & RSC     │ │ 3. SERVER COMPONENT RUNTIME EXECUTION  │
 │ Payload Instan dari CDN!  │ │ - Jalankan kode komponen async         │
 └───────────────────────────┘ │ - Evaluasi Request Memoization &       │
                               │   Data Cache per fetch()               │
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  ▼
                                       [ Kirim Response ke Client ]
```

---

## 9. Simple Example: Memilih Pola Render (Statis vs Dinamis)

```tsx
// KASUS 1: HALAMAN DINAMIS MURNI (SELALU FRESH PER REQUEST)
// Cocok untuk: Dashboard analytics user, saldo bank
import { cookies } from 'next/headers';

export const dynamic = 'force-dynamic'; // Mematikan Full Route Cache

export default async function UserDashboard() {
  const cookieStore = cookies(); // Mengakses cookies otomatis mengubah route menjadi dinamis!
  const userId = cookieStore.get('uid')?.value;
  
  const balance = await fetch(`https://api.bank.com/balance/${userId}`, {
    cache: 'no-store' // Mematikan Data Cache
  }).then(r => r.json());

  return <div>Saldo Terkini: Rp {balance.amount}</div>;
}

// KASUS 2: HALAMAN STATIS DENGAN ISR (REVALIDASI ON-DEMAND)
// Cocok untuk: Blog, e-commerce catalog
export default async function ProductCatalog() {
  const products = await fetch('https://api.store.com/products', {
    next: { tags: ['catalog-list'], revalidate: 3600 } // Cache 1 jam atau sampai revalidateTag
  }).then(r => r.json());

  return <div>Total Produk: {products.length}</div>;
}
```

---

## 10. Practical Example: Request Memoization pada Komponen Bertingkat

```tsx
// Tanpa Next.js, memanggil getSiteConfig() di 3 komponen berbeda akan memicu 3 kali query DB!
// Dengan React cache() / Next.js fetch memoization, pemanggilan ini HANYA TERJADI 1 KALI!

import { cache } from 'react';
import { db } from '@/lib/db';

// React cache() men-deduplikasi panggilan fungsi di dalam 1 siklus render server
export const getSiteConfig = cache(async () => {
  console.log('⚡ Query getSiteConfig dieksekusi ke Database!');
  return await db.query('SELECT * FROM configurations WHERE id = 1');
});

// Komponen 1: Header
export async function Header() {
  const config = await getSiteConfig(); // Mengambil dari eksekusi asli
  return <header>{config.siteName}</header>;
}

// Komponen 2: Footer
export async function Footer() {
  const config = await getSiteConfig(); // 100% MEMOIZED! Nol query DB tambahan!
  return <footer>Hak Cipta {config.companyName}</footer>;
}

// Komponen 3: Meta Head
export async function generateMetadata() {
  const config = await getSiteConfig(); // 100% MEMOIZED! Nol query DB tambahan!
  return { title: config.siteName };
}
```

---

## 11. Real World Example: Arsitektur E-Commerce Global Nike / Vercel

Pada platform retail skala global:
- Toko memiliki 50.000 produk yang tersebar di 40 negara dengan mata uang berbeda.
- Arsitektur Cache yang Diterapkan:
  1. Halaman produk menggunakan ISR dengan tag unik `next: { tags: [`product-${id}`] }`.
  2. Saat harga produk didiskon di dashboard inventaris SAP, sistem backend ERP mengirimkan webhook ke Next.js yang memanggil `revalidateTag('product-101')`.
  3. Dalam hitungan **30 milidetik**, cache produk 101 di seluruh Edge CDN global (Tokyo, Frankfurt, Washington, Jakarta) langsung diperbarui serentak.
- Edge Middleware mendeteksi header `cf-ipcountry` untuk mengarahkan pengguna secara otomatis ke mata uang lokal (IDR, USD, EUR) tanpa perlu Full Page Reload.

---

## 12. Trade-offs

| Strategi Caching | Kecepatan Respon (TTFB) | Keaktualan Data | Beban Database | Kompleksitas Invalidasi |
|---|---|---|---|---|
| **Static Full Route (SSG)** | Ekstrem (< 15 ms di CDN) | Basi hingga deployment baru | Nol | Sederhana |
| **ISR Time-based (60s)** | Ekstrem (< 15 ms di CDN) | Semi Real-time (Tertinggal 60s)| Sangat Rendah | Sederhana |
| **ISR Tag-based (On-Demand)**| Ekstrem (< 15 ms di CDN) | **100% Real-Time saat mutasi** | Rendah | **Tinggi (Perlu webhook sync)**|
| **Dynamic (`no-store`)** | Menengah (~100-400 ms) | 100% Real-Time | Tinggi di Jam Sibuk | Nol (Tanpa cache) |

---

## 13. When To Use
- **Gunakan On-Demand Tag Revalidation (`revalidateTag`):** Untuk sistem e-commerce, portal berita besar, dan direktori konten yang menuntut performa Edge CDN super cepat namun wajib langsung berubah saat admin menekan tombol Simpan.
- **Gunakan Edge Middleware:** Untuk routing guards (pengecekan token sesi JWT cookie), redirect otomatis berdasarkan bahasa browser, A/B testing cookies, dan penyisipan header keamanan HTTP (CSP, HSTS).
- **Gunakan Request Memoization (`cache()`):** Saat beberapa Server Components yang berada di hierarki terpisah membutuhkan data yang persis sama tanpa perlu mengoper props melalui *Prop Drilling*.

---

## 14. When NOT To Use
- **Jangan Letakkan Komputasi Berat atau SDK Database Besar di Edge Middleware:** Edge Runtime berjalan pada V8 Isolate yang memiliki batasan ukuran memori dan CPU time yang ketat (misal: 10-50 ms CPU budget). Jangan lakukan query SQL kompleks di middleware! Gunakan middleware hanya untuk routing dan validasi token ringan.
- **Jangan Gunakan `noStore()` pada Seluruh Halaman Jika Hanya 1 Komponen yang Dinamis:** Manfaatkan React `<Suspense>` untuk mengisolasi komponen dinamis dan biarkan sisa halaman tetap di-cache oleh Full Route Cache.

---

## 15. Common Mistakes
1. **Mengabaikan Dampak Akses `cookies()` atau `headers()`:** Memanggil `cookies()` di dalam layout komponen induk secara otomatis mengubah seluruh rute halaman di bawahnya menjadi dinamis (*Opt-out from Full Route Cache*), mematikan seluruh manfaat optimasi halaman statis.
2. **Revalidasi Path Terlalu Luas:** Memanggil `revalidatePath('/', 'layout')` saat hanya ada satu komentar baru di halaman artikel, memicu penghangusan cache seluruh halaman di seluruh situs web secara brutal.
3. **Menggunakan Node.js Native API di Edge Runtime:** Mengimpor `fs` (file system) atau `crypto.createCipheriv` lama di file `middleware.ts`. Edge Runtime hanya mendukung Web Standard APIs (`crypto.subtle`, `fetch`, `Request`, `Response`).

---

## 16. Best Practices

### Must Have
- Beri label **Cache Tags** yang semantik dan terstruktur: gunakan format hierarkis seperti `entity:id` (contoh: `products`, `product:88`, `categories`).
- Pisahkan logika Edge Middleware agar seringan mungkin: gunakan middleware murni untuk *Gatekeeping* dan *Redirects*.
- Terapkan konfigurasi matcher yang presisi di `middleware.ts` untuk mengecualikan aset statis (`_next/static`, favicon, gambar).

### Recommended
- Gunakan `revalidateTag` di dalam **Server Actions** tepat setelah mutasi database berhasil dikomit.
- Manfaatkan tool analitik **Vercel Data Cache Analytics** atau log cache header (`x-nextjs-cache: HIT / MISS / STALE`) untuk memverifikasi efektivitas cache.

### Advanced
- Rancang strategi **Stale-While-Revalidate Global**: Sajikan data cache instan ke pengguna saat revalidasi asinkron berlangsung di latar belakang (*Background Regeneration Worker*).

---

## 17. Troubleshooting

| Gejala Masalah | Indikasi Akar Masalah | Langkah Investigasi | Tindakan Perbaikan |
|---|---|---|---|
| **Header `x-nextjs-cache` Selalu Bernilai `MISS`** | Request memuat parameter dinamis, `no-store`, atau header otorisasi unik | Cek opsi `fetch` di komponen | Ganti `no-store` dengan `revalidate: N` atau gunakan `revalidateTag` |
| **Edge Middleware Melempar Error: `Edge runtime does not support Node.js API...`** | Dependensi npm yang diimpor di middleware menggunakan modul C/C++ Node.js | Audit daftar library yang diimpor di `middleware.ts` | Ganti dengan library ringan yang kompatibel dengan Web Standards (misal: `jose` untuk JWT) |
| **Data Baru Tidak Muncul di Browser Pengguna Meski Server Di-update** | Router Cache sisi klien masih menyimpan snapshot selama 30 detik | Buka tab konsol klien, navigasi halaman | Panggil `router.refresh()` di sisi klien setelah mutasi berhasil |

---

## 18. Exercise
1. Bangun simulator in-memory Next.js Caching Lifecycle di Node.js yang memodelkan 4 tingkatan cache: Request Memoization, Data Cache, dan Full Route Cache.
2. Simulasikan pemanggilan fetch data produk yang diulang 3 kali dalam 1 render request dan buktikan Request Memoization memangkas query menjadi 1 kali.
3. Terapkan mekanisme on-demand `revalidateTag('products')` dan buktikan cache lama tereliminasi dan digantikan oleh data baru.

---

## 19. Challenge
Rancang arsitektur caching dan Edge routing untuk platform **Tiket Konser Musik Skala Nasional**:
1. Halaman pemilihan kursi memiliki 100.000 penonton serentak.
2. Rancang strategi pembagian cache: layout peta kursi (Statis Edge CDN), status ketersediaan kursi sisa (Dinamis via Redis dengan TTL 2 detik), dan proteksi bot via Edge Middleware (Cloudflare Turnstile captcha check).
3. Rancang mekanisme on-demand invalidation saat kuota kursi kategori VIP habis terjual!

---

## 20. Summary
Next.js App Router menghadirkan lompatan arsitektural terbesar dalam sejarah pengembangan web modern dengan menyatukan kekuatan server, client, dan edge network. Dengan menguasai 4 lapisan caching, mengeksekusi revalidasi data secara on-demand berbasis tag, dan memanfaatkan kelincahan Edge Middleware, seorang Full-Stack Engineer mampu menghadirkan aplikasi web enterprise yang memiliki kecepatan instan bak konten statis namun dengan kedalaman data dinamis real-time.

---
[⬅️ Module 01: RSC, Streaming SSR, & Server Actions](./Module-01-React-Server-Components-Streaming-SSR-Server-Actions.md) | [📋 Silabus Induk](../README.md) | [BAB 03 Quiz & Challenge ➡️](./BAB-03-Quiz-dan-Challenge.md)
---
