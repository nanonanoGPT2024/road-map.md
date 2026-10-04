---
[⬅️ Module 01: Modern ORMs & Pooling](./Module-01-Modern-ORMs-Drizzle-Prisma-Connection-Pooling.md) | [📋 Silabus Induk](../README.md) | [BAB 05 Quiz & Challenge ➡️](./BAB-05-Quiz-dan-Challenge.md)
---

# Module 02: Serverless Database Scaling: Neon / PlanetScale, Upstash Redis Edge Caching, & Zero-Downtime Migrations

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami arsitektur **Serverless Relational Database** modern (seperti Neon PostgreSQL, PlanetScale Vitess, dan Turso libSQL) yang memisahkan komputasi (*Compute*) dari penyimpanan (*Storage*) dan mendukung *Autoscaling to Zero*.
- Mengimplementasikan pola arsitektur **Edge Caching** menggunakan **Upstash Redis** melalui protokol HTTP/REST untuk menghadirkan latensi sub-10ms pada serverless dan edge workers.
- Merancang sistem **Multi-Region Read Replicas** dan mengatasi tantangan konsistensi data replikasi seperti fenomena *Read-Your-Own-Writes Consistency*.
- Menerapkan strategi **Zero-Downtime Database Migration** menggunakan metodologi industri **Expand-and-Contract Pattern (Parallel Run)** saat melakukan migrasi skema pada sistem produksi berkecepatan tinggi.
- Memanfaatkan fitur **Database Branching** (ala Git branch) pada environment preview / pull request untuk pengujian data yang aman dan terisolasi.

---

## 2. Prerequisite
- Memahami konsep Connection Pooling dan Drizzle ORM dari Module 01.
- Memahami siklus request-response HTTP dan caching header.
- Memahami dasar-dasar replikasi database (Primary vs Replica / Read-Only).

---

## 3. Concept
Dalam komputasi awan generasi pertama, database relasional berjalan pada satu server virtual persisten (seperti AWS EC2 atau RDS) di mana unit komputasi (CPU/RAM) dan disk (SSD) menyatu secara erat. Anda membayar biaya sewa 24 jam sehari, 7 hari seminggu, terlepas dari apakah ada pengguna yang mengakses atau tidak.

**Serverless Database** mengubah paradigma ini dengan memisahkan (*decoupling*) **Compute Layer** dari **Storage Layer**:

```
[ Stateless Serverless Compute Node (Autoscales 0 -> 100 Cores) ]
                                |
                     (Jaringan Storage Cloud)
                                v
[ Distributed Page-Based Storage (S3 / Cloud Storage / WAL Logs) ]
```

Ketika aplikasi tidak menerima request selama 5 menit, node komputasi dapat ditidurkan (*scale to zero*), sehingga biaya tagihan menjadi nol. Saat request pertama tiba, node komputasi menyala kembali dalam waktu puluhan milidetik. Selain itu, penyimpanan terdistribusi memungkinkan fitur revolusioner seperti **Database Branching** instan: membuat salinan database berukuran ratusan gigabyte dalam 1 detik untuk setiap Pull Request GitHub pengembang!

---

## 4. Why? (Mengapa Membutuhkan Edge Caching & Zero-Downtime Migration?)
1. **Mengatasi Hukum Fisika (Latensi Jaringan Geografis)**:
   - Jika primary database Anda berada di Virginia (`us-east-1`) dan pengguna mengakses web dari Jakarta (`ap-southeast-3`), setiap query database TCP bolak-balik membutuhkan latensi minimum 220ms.
   - Dengan meletakkan **Upstash Redis di Edge** terdekat (Singapura / Jakarta), data katalog produk atau sesi pengguna dapat disajikan dalam waktu **5ms**.
2. **Kebutuhan HTTP/REST API di Edge Worker**:
   - Runtime edge seperti Cloudflare Workers dan Vercel Edge Runtime tidak selalu mendukung koneksi TCP socket murni secara bebas. Upstash Redis menyediakan SDK berbasis **HTTP REST**, memungkinkan edge worker membaca dan menulis cache tanpa terkendala firewall soket.
3. **Mencegah Insiden Downtime saat Rilis Fitur**:
   - Pada aplikasi dengan jutaan pengguna aktif, mengeksekusi perintah SQL seperti `ALTER TABLE users RENAME COLUMN username TO handle;` langsung di database produksi akan **mengakibatkan downtime fatal**. Instance aplikasi lama yang sedang berjalan akan melempar error `column "username" does not exist` sebelum deployment versi baru selesai menyebar.

---

## 5. What? (Komponen Utama Serverless Data Layer)

### A. Neon (Serverless Postgres)
- **Karakteristik**: Engine PostgreSQL 100% kompatibel yang memisahkan komputasi dari penyimpanan. Mendukung autoscaling CPU otomatis, scale-to-zero, dan *database branching* berbasis copy-on-write.
- **Neon Serverless Driver**: Driver khusus yang menggunakan WebSocket / HTTP tunnel sehingga dapat berjalan di Vercel Edge dan Cloudflare Workers tanpa batasan koneksi TCP.

### B. Upstash Redis
- **Karakteristik**: Database Redis Serverless yang ditagih per request (*Pay-per-request*).
- **Keunggulan**: Menyediakan REST API over HTTP, dukungan replikasi global otomatis, dan integrasi mulus dengan ekosistem Vercel KV / Next.js.

### C. Expand and Contract Pattern
- Metodologi migrasi skema database yang memecah satu perubahan destruktif (seperti ganti nama kolom, ubah tipe data, atau pecah tabel) menjadi **4 fase bertahap** tanpa pernah menghentikan layanan aplikasi.

---

## 6. How? (Implementasi Edge Caching & Expand-Contract)

### 1. Pola Cache-Aside dengan Upstash Redis di Next.js
```typescript
import { Redis } from "@upstash/redis";
import { db } from "./db";
import { products } from "./schema";
import { eq } from "drizzle-orm";

// Inisialisasi REST Redis Client (Kompatibel dengan Edge Runtime!)
const redis = Redis.fromEnv();

export async function getProductByIdCached(productId: string) {
  const cacheKey = `product:${productId}`;

  // 1. Coba baca dari Edge Cache (Latensi ~5ms)
  const cachedData = await redis.get(cacheKey);
  if (cachedData) {
    return { data: cachedData, source: "CACHE_HIT" };
  }

  // 2. Jika Cache Miss, baca dari Primary Database
  const [product] = await db
    .select()
    .from(products)
    .where(eq(products.id, productId));

  if (product) {
    // 3. Simpan ke Cache dengan TTL 1 Jam (3600 detik)
    await redis.set(cacheKey, product, { ex: 3600 });
  }

  return { data: product, source: "DATABASE_MISS" };
}
```

### 2. Invalidasi Cache Berbasis Mutasi (Write-Through / Invalidate)
```typescript
export async function updateProductPrice(productId: string, newPrice: string) {
  // 1. Update di Primary Database
  await db
    .update(products)
    .set({ price: newPrice })
    .where(eq(products.id, productId));

  // 2. Hapus Cache di Edge seketika
  const cacheKey = `product:${productId}`;
  await redis.del(cacheKey);

  return { success: true };
}
```

---

## 7. Analogy: Zero-Downtime Migration "Expand and Contract"
Bayangkan sebuah jembatan layang yang padat kendaraan setiap hari:
- **Pendekatan Naif (Destructive)**: Anda merobohkan jembatan lama pada hari Senin, lalu membangun jembatan baru selama 3 hari. Selama 3 hari tersebut, lalu lintas terputus total (*Total Outage / Downtime*).
- **Pendekatan Expand and Contract**:
  1. **Expand**: Anda membangun lajur jembatan baru di sebelah jembatan lama tanpa mengganggu kendaraan yang sedang lewat.
  2. **Dual-Route**: Kendaraan mulai diarahkan ke lajur baru dan lama secara paralel.
  3. **Backfill**: Anda memastikan seluruh rambu dan sistem tol di lajur baru telah teruji 100%.
  4. **Contract**: Setelah semua lalu lintas beralih lancar ke jembatan baru, barulah jembatan lama dibongkar dengan tenang.

---

## 8. Diagram Expand and Contract Migration Pattern

```
FASE 1: EXPAND (Tambah kolom baru nullable)
+--------------------------------------------------------+
| Kolom Lama: `name` (Aktif Digunakan Aplikasi Versi 1)   |
| Kolom Baru: `full_name` (NULLABLE - Siap Menerima Data)|
+--------------------------------------------------------+
                           |
FASE 2: PARALLEL RUN (Dual-Write di Aplikasi Versi 2)
+--------------------------------------------------------+
| Aplikasi menulis ke `name` DAN `full_name` sekaligus.  |
| Aplikasi membaca dari `name` (fallback ke full_name).  |
+--------------------------------------------------------+
                           |
FASE 3: DATA BACKFILL (Sinkronisasi Data Historis)
+--------------------------------------------------------+
| Script background: UPDATE users SET full_name = name   |
| WHERE full_name IS NULL;                               |
+--------------------------------------------------------+
                           |
FASE 4: CONTRACT (Aplikasi Beralih Total ke Kolom Baru)
+--------------------------------------------------------+
| Aplikasi Versi 3 hanya membaca dan menulis ke `full_name`|
| Kolom `name` lama aman untuk di-DROP via DDL!          |
+--------------------------------------------------------+
```

---

## 9. Simple Example: Neon Database Branching untuk CI/CD Preview
Setiap kali pull request dibuka di GitHub, GitHub Action memicu API Neon untuk membuat klon instan dari database staging:

```bash
# Membuat branch database baru secara instan (Copy-on-Write)
curl -X POST "https://console.neon.tech/api/v2/projects/$PROJECT_ID/branches" \
  -H "Authorization: Bearer $NEON_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"endpoints": [{"type": "read_write"}], "branch": {"name": "pr-preview-404"}}'
```
Hasilnya adalah connection string baru yang sepenuhnya terisolasi. Pengembang dapat menguji migrasi skema destruktif tanpa takut merusak data rekan satu tim.

---

## 10. Practical Example: Mengatasi Read-Your-Own-Writes Consistency
Ketika aplikasi menggunakan Read Replicas di region yang berbeda, ada penundaan replikasi (*Replication Lag*) sekitar 50ms–500ms. Jika seorang pengguna mengubah nama profilnya lalu halaman langsung me-refresh dan membaca dari read-replica, pengguna akan melihat nama lamanya kembali (*Stale Read*).

```typescript
// Solusi: Pinning Session ke Primary Writer sesaat setelah Mutasi
import { cookies } from "next/headers";

const WRITER_PIN_COOKIE = "x-pin-primary-db";

export async function updateUserProfile(userId: string, newBio: string) {
  // 1. Tulis ke Primary Database
  await primaryDb.update(users).set({ bio: newBio }).where(eq(users.id, userId));

  // 2. Set cookie bahwa user ini baru saja mutasi (misal berlaku 5 detik)
  cookies().set(WRITER_PIN_COOKIE, "true", { maxAge: 5, path: "/" });
}

export async function getUserProfile(userId: string) {
  const isPinned = cookies().get(WRITER_PIN_COOKIE);

  // Jika baru mutasi, paksa baca dari PRIMARY untuk menjamin Strong Consistency!
  if (isPinned) {
    return await primaryDb.select().from(users).where(eq(users.id, userId));
  }

  // Jika tidak, baca dari READ REPLICA lokal untuk efisiensi latensi
  return await replicaDb.select().from(users).where(eq(users.id, userId));
}
```

---

## 11. Real-World Example: Migrasi Skema Kolom Enkripsi Rekening Bank
Sebuah fintech ingin memigrasikan kolom nomor rekening `account_number` menjadi terenkripsi `account_number_encrypted`:

1. **Step 1 (DDL Expand)**:
   ```sql
   ALTER TABLE bank_accounts ADD COLUMN account_number_encrypted TEXT;
   ```
2. **Step 2 (App Dual-Write)**:
   Aplikasi backend diperbarui. Saat menyimpan nomor rekening baru, enkripsi nilai tersebut dan tulis ke kedua kolom.
3. **Step 3 (Batch Backfill)**:
   Jalankan background worker yang memproses 1.000 akun per batch untuk membaca `account_number`, mengenkripsinya, dan mengisi `account_number_encrypted`.
4. **Step 4 (App Switch)**:
   Aplikasi dialihkan untuk membaca hanya dari `account_number_encrypted`.
5. **Step 5 (DDL Contract)**:
   ```sql
   ALTER TABLE bank_accounts DROP COLUMN account_number;
   ```
Seluruh proses berlangsung di jam kerja tanpa memutus satu pun transaksi pengguna!

---

## 12. Trade-offs: Serverless DB vs Dedicated Instance

| Fitur | Serverless Relational (Neon/PlanetScale) | Traditional Dedicated (AWS RDS/Postgres VM) |
| :--- | :--- | :--- |
| **Model Biaya** | Pay-as-you-go (per compute hour & storage) | Biaya tetap per jam 24/7 |
| **Scale-to-Zero** | **Mendukung** (Hemat biaya saat idle) | Tidak mendukung (Tetap bayar walau sepi) |
| **Koneksi Edge** | **Didukung via HTTP/WebSocket** | Terbatas (Memerlukan RDS Proxy) |
| **Database Branching** | **Instan (Copy-on-write)** | Lambat (Snapshot & Restore berjam-jam) |
| **Beban Kerja Monoton Berat** | Lebih mahal jika CPU 100% terus menerus | **Lebih hemat biaya untuk beban stabil tinggi** |

---

## 13. When To Use Serverless Database & Edge Caching
- Aplikasi Anda memiliki pola traffic yang fluktuatif (*spiky traffic*), seperti e-commerce, media berita, atau platform event.
- Anda membangun aplikasi modern dengan ribuan preview environment otomatis untuk tim developer.
- Pengguna Anda tersebar secara global di seluruh dunia dan membutuhkan kecepatan akses data di bawah 20ms via edge caching.

---

## 14. When NOT To Use
- Aplikasi analitikal big data internal yang melakukan query *heavy aggregation* selama berjam-jam tanpa henti (gunakan Data Warehouse seperti ClickHouse, Snowflake, atau BigQuery).
- Sistem legal/perbankan *on-premise* yang secara regulasi melarang penyimpanan data pada arsitektur cloud multi-tenant.

---

## 15. Common Mistakes
1. **Melakukan Migrasi Destruktif dalam Satu Transaksi**:
   - Menghapus kolom lama sebelum seluruh versi aplikasi baru ter-deploy secara merata. Ini adalah penyebab #1 insiden downtime rilis sistem!
2. **Menyimpan Data Terlalu Lama di Edge Cache Tanpa Mekanisme Purge**:
   - Menyimpan harga produk di cache selama 24 jam tanpa menghapus key saat admin mengubah harga di CMS. Pengguna akan checkout dengan harga kadaluwarsa!
3. **Lupa Menangani Replication Lag pada Read Replicas**:
   - Mengharapkan data yang baru di-insert di primary langsung terbaca di replika dalam milidetik yang sama tanpa mekanisme *pinning* atau *read-your-own-writes*.

---

## 16. Best Practices

### Must Have
- Selalu terapkan **Expand and Contract Pattern** untuk seluruh perubahan skema database produksi.
- Berikan batas waktu kadaluwarsa (**TTL**) pada setiap key di Redis untuk menghindari kebocoran memori (*memory leak*).

### Recommended
- Gunakan database branching di pipeline CI/CD untuk menjalankan migrasi uji coba pada Pull Request sebelum merge ke `main`.
- Gabungkan edge caching dengan Next.js `revalidateTag()` untuk *On-Demand Cache Invalidation*.

### Advanced
- Implementasikan Distributed Lock menggunakan Redis Redlock saat menjalankan batch backfill data agar tidak terjadi eksekusi ganda antar worker.

### Avoid
- Jangan menyimpan data sensitif (password hash plaintext, token otentikasi rahasia) di edge cache publik tanpa enkripsi lapis kedua.

---

## 17. Troubleshooting Guide

| Masalah | Analisis Akar Masalah | Solusi |
| :--- | :--- | :--- |
| Pengguna baru daftar tidak bisa login langsung (*User Not Found*). | Aplikasi membaca dari Read Replica yang masih mengalami lag sinkronisasi dari Primary. | Terapkan fallback read ke Primary atau pin sesi user ke Primary selama 10 detik pasca pendaftaran. |
| Tagihan Upstash Redis membengkak drastis. | Pola query N+1 pada pembacaan cache (misal membaca 100 item satu per satu dalam loop). | Gunakan batching query `redis.mget(keys)` untuk mengambil puluhan item dalam 1 request HTTP. |
| Migrasi DDL `ALTER TABLE` menggantung (*Lock Wait Timeout*). | Ada transaksi panjang yang sedang memegang lock tabel yang ingin dimodifikasi. | Gunakan opsi `SET lock_timeout = '5s';` dan hindari migrasi di jam sibuk transaksi. |

---

## 18. Exercise
- **Easy**: Tulis implementasi fungsi helper cache `getOrSet(key, ttlSeconds, fetcherFn)` menggunakan Redis.
- **Medium**: Rancang skema migrasi 4 langkah untuk membagi kolom `address` (teks tunggal) menjadi `street`, `city`, dan `postal_code` dengan zero downtime.
- **Hard**: Buat router database cerdas yang secara otomatis mengarahkan query `SELECT` ke read replica dengan latensi terendah, tetapi otomatis beralih ke primary jika mendeteksi adanya lag data di atas 100ms.

---

## 19. Challenge
Rancang arsitektur cache multi-tier untuk sistem tiket konser: L1 Memory Cache di Node.js instance, L2 Edge Redis di 3 benua, dan Serverless Database dengan connection pooling. Pastikan tidak ada tiket yang terjual dua kali (*overselling*) meskipun 100.000 pengguna mengklik tombol beli dalam detik yang sama.

---

## 20. Summary
- **Serverless Database** memisahkan komputasi dari penyimpanan, menghadirkan *autoscaling to zero*, efisiensi biaya, dan fitur canggih seperti *Database Branching*.
- **Upstash Redis** di Edge memangkas latensi dari ratusan milidetik menjadi hitungan milidetik tunggal, mendekatkan data ke pengguna akhir di seluruh dunia.
- **Expand-and-Contract Pattern** adalah standar emas rekayasa perangkat lunak untuk menjaga ketersediaan sistem 99.99% (*High Availability*) selama proses evolusi skema database berlangsung.

---

## Hands-on Practice: Simulasi Multi-Region Replica Router & Zero-Downtime Migration
Jalankan simulator replika database cerdas dan orkestrator migrasi expand-and-contract mandiri:

```bash
node Full-Stack/BAB-05-Data-Layer-ORMs-dan-Serverless-Databases/hands-on/m02/edge_db_replica_router_sim.js
```

---
[⬅️ Module 01: Modern ORMs & Pooling](./Module-01-Modern-ORMs-Drizzle-Prisma-Connection-Pooling.md) | [📋 Silabus Induk](../README.md) | [BAB 05 Quiz & Challenge ➡️](./BAB-05-Quiz-dan-Challenge.md)
---
