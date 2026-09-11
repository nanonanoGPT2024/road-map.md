# MODULE 03: Database Partitioning & Sharding

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Membedakan secara arsitektural antara **Vertical Partitioning** (pemisahan kolom) dan **Horizontal Partitioning / Sharding** (pemisahan baris).
2. Memilih **Sharding Key** yang optimal untuk mencegah ketimpangan beban (*Hot Shards*).
3. Membandingkan 3 arsitektur sharding utama: **Range-Based**, **Hash-Based**, dan **Directory-Based (Lookup Service)**.
4. Menganalisis dan mengatasi 3 konsekuensi berat sharding: **Cross-Shard Joins**, **Distributed Transactions (Two-Phase Commit)**, dan **Resharding / Data Migration**.
5. Mengimplementasikan Sharding Router dan query Scatter-Gather menggunakan hands-on script.

---

## 2. Prerequisite
- Telah menyelesaikan [BAB 05 — Module 01: RDBMS Scaling, Indexing, & ACID](./Module-01-RDBMS-Scaling-Indexing-dan-ACID.md).
- Telah menyelesaikan [BAB 05 — Module 02: Database Replication, Read Replicas, & Failover](./Module-02-Database-Replication-dan-Failover.md).

---

## 3. Concept
Ketika dataset aplikasi terus membengkak melampaui **5 Terabyte hingga puluhan Terabyte**, dan volume transaksi penulisan (*Write IOPS*) melampaui batas fisik mesin Primary Database terkuat di dunia cloud, strategi penambahan Read Replicas dan vertical scale-up tidak lagi mampu bertahan.

**Database Sharding (Horizontal Partitioning)** adalah pola arsitektur memecah satu tabel database raksasa menjadi potongan-potongan baris data yang lebih kecil (*shards*), dan mendistribusikan potongan-potongan tersebut ke **beberapa server database fisik mandiri yang terpisah**. Setiap shard menjalankan instance database sendiri dan hanya menyimpan subset data keseluruhan.

---

## 4. Why? (Kapan Waktu yang Tepat Melakukan Sharding?)

### Aturan Emas Arsitek: Sharding adalah Pilihan Terakhir!
Sharding membawa kompleksitas arsitektur yang sangat luar biasa. Anda kehilangan fitur bawaan ACID transactions, relational foreign key constraints, dan kemudahan query `JOIN`.

Sebelum memutuskan melakukan Sharding, pastikan Anda telah menempuh jalur optimasi berikut terlebih dahulu:
1. Optimasi B-Tree Indexing dan perbaikan query SQL lambat.
2. Memasang In-Memory Cache (Redis) untuk menyerap traffic pembacaan.
3. Menambahkan Read Replicas untuk membagi beban `SELECT`.
4. Melakukan Vertical Scaling (menaikkan RAM dan kapasitas IOPS NVMe SSD).
5. Memisahkan tabel besar ke database terpisah (*Vertical Partitioning*).

> **Kapan Wajib Sharding:** Hanya jika ukuran data disk database sudah > 5 TB, query penulisan write IOPS menyentuh 100% batas hardware, dan database server terbesar yang tersedia tidak lagi sanggup menampungnya.

---

## 5. What? (Vertical vs Horizontal Partitioning & Tipe Sharding)

### A. Vertical Partitioning vs Horizontal Sharding

```text
  [ TABEL ASLI: USERS (10 JUTA BARIS, 30 KOLOM) ]
  id | name | email | password_hash | bio | profile_picture_blob | address | preferences
  
  ---------------------------------------------------------------------------------------
  
  [ VERTICAL PARTITIONING: Memecah Berdasarkan Kolom ]
  DB 1 (Sering Diakses - Data Ringan):
  id | name | email | password_hash
  
  DB 2 (Jarang Diakses - Data Berat):
  user_id | bio | profile_picture_blob | address | preferences
  
  ---------------------------------------------------------------------------------------
  
  [ HORIZONTAL PARTITIONING / SHARDING: Memecah Berdasarkan Baris ]
  Server Shard 1: Baris User ID 1 s/d 5.000.000   (Seluruh 30 kolom lengkap)
  Server Shard 2: Baris User ID 5.000.001 s/d 10.000.000 (Seluruh 30 kolom lengkap)
```

---

### B. 3 Strategi Pemilihan Sharding Key

#### 1. Range-Based Sharding
Membagi data berdasarkan rentang nilai (misal rentang tanggal atau rentang ID integer):
- Shard 1: User ID `1 - 1.000.000`
- Shard 2: User ID `1.000.001 - 2.000.000`
- **Kelebihan:** Sangat mudah diimplementasikan; query rentang (*Range Query*) sangat efisien.
- **Kekurangan Fatal (Hot Shard):** Jika user baru mendaftar berurutan, **100% operasi penulisan user baru akan menghantam Shard terakhir**, sementara Shard 1 dan 2 menganggur!

#### 2. Hash-Based / Modulo Sharding
Menghitung nilai hash dari Sharding Key (misal: `hash(user_id) % Jumlah_Shard`):
- **Kelebihan:** Persebaran data sangat merata dan acak. Beban penulisan terbagi adil ke seluruh server.
- **Kekurangan:** Sangat sulit melakukan range query (misal mencari user umur 20-30 harus bertanya ke seluruh shard); dan menambah server baru membutuhkan proses *resharding* data massal.

#### 3. Directory-Based / Lookup Service Sharding
Menggunakan database mini terpusat yang menyimpan tabel pemetaan (*Lookup Table*): `User_ID -> Shard_ID`.
- **Kelebihan:** Sangat fleksibel; data sebuah akun perusahaan enterprise besar dapat dipindahkan ke shard terdedikasi tanpa memengaruhi akun lain.
- **Kekurangan:** Lookup Service menjadi *Single Point of Failure* dan menambah satu hop latensi ekstra pada setiap query.

---

## 6. How? (Tantangan Arsitektur Pasca Sharding)

```text
                          [ ARSITEKTUR SHARDING ROUTER ]
                          
                               [ Client Application ]
                                         │
                                         ▼
                             [ SHARDING ROUTER PROXY ]
                               (Vitess / Citus / Code)
                                         │
                 ┌───────────────────────┼───────────────────────┐
                 ▼ (Hash Slot 1)         ▼ (Hash Slot 2)         ▼ (Hash Slot 3)
         +---------------+       +---------------+       +---------------+
         |  SHARD NODE 1 |       |  SHARD NODE 2 |       |  SHARD NODE 3 |
         | (Users 0-33%) |       | (Users 34-66%)|       | (Users 67-100)|
         +---------------+       +---------------+       +---------------+
```

### 1. Masalah Cross-Shard Joins
Query SQL gabungan seperti:
```sql
SELECT users.name, orders.total FROM users JOIN orders ON users.id = orders.user_id;
```
Jika tabel `users` berada di Shard 1 dan tabel `orders` berada di Shard 2, database engine tidak bisa melakukan join di memori lokal disk!  
**Solusi:**
- **Co-location Sharding:** Shard tabel `orders` menggunakan `user_id` yang sama, sehingga seluruh pesanan milik Budi dijamin berada di mesin fisik yang sama dengan data akun Budi.
- **Denormalisasi Data:** Salin nama pengguna langsung ke dalam kolom tabel `orders`.

### 2. Scatter-Gather Query
Jika query tidak menyertakan Sharding Key (misal: `SELECT * FROM users WHERE email = 'budi@mail.com'` pada cluster yang di-shard menggunakan `user_id`):
- Sharding Router terpaksa mengirimkan query tersebut ke **SELURUH SHARD SECARA BERSAMAAN (*Scatter*)**.
- Router menunggu jawaban dari semua shard, menggabungkan hasilnya (*Gather*), baru mengembalikan ke client. Ini sangat lambat dan membebani seluruh server!

---

## 7. Analogy: Lemari Arsip Pasien Rumah Sakit
- **Tanpa Sharding:** Satu lemari arsip raksasa di lobi. Saat pasien rumah sakit mencapai 1 juta orang, lemari penuh dan 10 perawat berebut membuka laci yang sama.
- **Range Sharding (Abjad Nama):** Lemari A-G, H-N, O-Z. Masalahnya: Di Indonesia, nama berawalan huruf "M" (Muhammad) sangat banyak, sehingga lemari H-N penuh sesak (*Hot Shard*), sementara lemari Q-Z kosong.
- **Hash Sharding (Nomor Rekam Medis % 3):** Nomor ganjil/genap membagi map secara acak merata ke 3 ruangan terpisah.

---

## 8. Diagram: Alur Penanganan Scatter-Gather vs Targeted Query

```text
[ TARGETED QUERY (Ada Sharding Key): SELECT * FROM orders WHERE user_id = 101 ]
Router menghitung hash(101) % 3 = Shard 2 ──▶ Langsung ke Shard 2 (Cepat: 1ms)
                                                
---------------------------------------------------------------------------------

[ SCATTER-GATHER (Tanpa Sharding Key): SELECT * FROM orders WHERE status = 'PENDING' ]
Router tidak tahu data ada di mana:
  ├── Kirim ke Shard 1 ──▶ Hasil: 5 baris
  ├── Kirim ke Shard 2 ──▶ Hasil: 2 baris  ──▶ [ Gabungkan ] ──▶ Return 10 baris
  └── Kirim ke Shard 3 ──▶ Hasil: 3 baris
(Sangat mahal: Menyedot CPU seluruh cluster database!)
```

---

## 9. Simple Example: Implementasi Hash Sharding Router
```javascript
function getShardServer(userId, totalShards = 3) {
  // Gunakan hashing numerik sederhana
  const hash = Math.abs(hashCode(userId));
  const shardIndex = hash % totalShards;
  return `shard-db-${shardIndex + 1}.internal`;
}

// user_101 -> hash: 9912 -> Shard 1
// user_205 -> hash: 4821 -> Shard 2
```

---

## 10. Practical Code Example
Lihat simulasi routing Sharding (Range vs Hash), penanganan Scatter-Gather, dan fenomena Hot Shard pada:
`System-Design/BAB-05-Arsitektur-Basis-Data/hands-on/m03/database_sharding_router.js`

---

## 11. Real World Example: Migrasi Sharding Notion & Instagram Sharding IDs
- **Migrasi Sharding Notion (2021):** Notion awalnya berjalan pada 1 database monolitik PostgreSQL di AWS. Saat pengguna melonjak di masa pandemi, CPU database menyentuh 100% setiap hari. Tim engineer Notion melakukan sharding PostgreSQL menjadi **48 Shard database fisik**. Mereka memilih `space_id` (Workspace ID) sebagai Sharding Key, sehingga seluruh halaman dan blok di dalam satu workspace Notion selalu berada di shard yang sama.
- **Instagram ID Generator (Snowflake Variant):** Pada database yang di-shard, auto-increment integer ID bawaan database (`id SERIAL`) tidak bisa digunakan karena Shard 1 dan Shard 2 akan menghasilkan ID `1` yang bentrok! Instagram menciptakan algoritma ID 64-bit unik berbasis:
  $$\text{ID} = 41 \text{ bit timestamp} + 13 \text{ bit Shard ID} + 10 \text{ bit auto-increment sequence}$$
  Setiap ID secara bawaan sudah mencantumkan informasi shard pemiliknya!

---

## 12. Trade-offs (Range Sharding vs Hash Sharding)

| Parameter | Range-Based Sharding | Hash-Based Sharding |
|---|---|---|
| **Penyebaran Data** | Berpotensi tidak merata (*Hotspots*) | **Sangat Merata** |
| **Performa Range Query** | **Sangat Cepat** (Cukup 1 shard) | Lambat (Wajib Scatter-Gather ke semua shard) |
| **Resharding Saat Tambah Server** | Mudah (Cukup buat shard untuk range baru) | **Sulit** (Wajib migrasi data besar-besaran) |
| **Prediktabilitas Lokasi** | Alami (mudah dibaca manusia) | Acak (berbasis fungsi hash matematika) |

---

## 13. When To Use What
- **Pilih Sharding Key yang memiliki:**
  1. **Kardinalitas Tinggi:** Memiliki jutaan nilai unik (seperti `user_id` atau `tenant_id`).
  2. **Distribusi Merata:** Tidak ada satu ID yang menguasai 50% seluruh transaksi sistem.
  3. **Sering Muncul di Query Filter:** Hampir setiap query aplikasi menyertakan key ini (`WHERE user_id = ...`).

---

## 14. When NOT To Use Sharding
- Jangan pernah melakukan sharding pada database jika ukuran totalnya masih di bawah **1 Terabyte**. Mengelola sharding tanpa kebutuhan nyata akan melipatgandakan waktu kerja tim Anda hanya untuk urusan sinkronisasi infrastruktur!

---

## 15. Common Mistakes
1. **Memilih Sharding Key yang Menimbulkan Hot Shard:** Memilih `country` sebagai Sharding Key pada aplikasi di Indonesia. Shard Indonesia menampung 95% data, sementara Shard Malaysia dan Singapura hanya 5%. Shard Indonesia tetap jebol!
2. **Mengabaikan Distributed Unique ID:** Masih mengandalkan `AUTO_INCREMENT` database lokal pada tabel yang di-shard, menghasilkan benturan ID duplikat saat data digabungkan.
3. **Melakukan Cross-Shard Joins di Jam Kerja Sibuk:** Membiarkan backend mengeksekusi join antar-shard tanpa pagination yang mengunci ratusan koneksi di semua shard sekaligus.

---

## 16. Best Practices

- **Must Have:**
  - Gunakan algoritma ID global terdistribusi (seperti **UUIDv7**, **Twitter Snowflake**, atau **Sonyflake**).
  - Sertakan Sharding Key pada **SEMUA** query mutasi data `WHERE sharding_key = ...`.
- **Recommended:**
  - Gunakan middleware proxy sharding yang sudah terbukti di industri (seperti **Vitess** untuk MySQL, atau **Citus** untuk PostgreSQL).
  - Terapkan teknik **Virtual Shards (Consistent Hashing Sharding)** agar penambahan shard baru di masa depan tidak memerlukan migrasi 100% data.
- **Advanced:**
  - Terapkan pola **Two-Phase Commit (2PC)** atau **Saga Pattern** jika transaksi bisnis wajib memodifikasi data di 2 shard yang berbeda secara atomik.
- **Avoid / Overengineering:**
  - Menulis custom sharding logic rumit di dalam kode aplikasi backend sendiri jika bisa menggunakan sharding extension database.

---

## 17. Troubleshooting Guide
```text
Gejala: Shard Node 3 utilisasi CPU 95%, sementara Shard 1 dan 2 hanya 15%.
------------------------------------------------------------------------
Penyebab:
1. Fenomena "Celebrity / Hotspot Problem": Akun selebriti atau toko official store raksasa (misal: Toko Official Apple) berada di Shard 3 dan menerima jutaan transaksi.

Solusi:
- Pisahkan akun skala enterprise/selebriti ke "Dedicated Shard" tersendiri (menggunakan Directory-Based Lookup).
- Lakukan salt hashing pada key selebriti: key = `${user_id}_${random_int(1, 5)}` untuk membagi beban ke beberapa shard.
```

---

## 18. Hands-on Lab: Simulator Sharding Router, Hotspot, & Scatter-Gather

File lab sudah disiapkan di:
`System-Design/BAB-05-Arsitektur-Basis-Data/hands-on/m03/database_sharding_router.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-05-Arsitektur-Basis-Data/hands-on/m03/database_sharding_router.js
```

### Yang Ditampilkan Script Ini:
1. Membandingkan **Range Sharding** (yang memicu Hotspot pada data berurutan) vs **Hash Sharding** (yang menyebarkan beban secara seimbang).
2. Menyimulasikan query cepat bertarget (**Targeted Single-Shard Query**: 1 ms).
3. Menyimulasikan bahaya query tanpa sharding key (**Scatter-Gather Multi-Shard Query**: harus memeriksa seluruh shard dan menggabungkan hasil).

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Jelaskan perbedaan mendasar antara *Vertical Partitioning* dan *Horizontal Partitioning (Sharding)*!

### Level 2 (Medium):
Sebuah aplikasi ojek online ingin melakukan sharding pada tabel perjalanan (*rides*). Tim mengajukan dua opsi Sharding Key:
- Opsi A: `city_id` (ID Kota: Jakarta, Surabaya, Bandung, dll)
- Opsi B: `user_id` (ID Penumpang)  
Analisis trade-off dari kedua opsi tersebut! Opsi mana yang berisiko menciptakan *Hot Shard* dan mengapa?

### Level 3 (Hard):
Jelaskan mengapa transaksi ACID tradisional tidak bisa berjalan secara langsung ketika sebuah transaksi bisnis harus memperbarui saldo di Shard 1 dan memotong inventori di Shard 2! Jelaskan bagaimana pola **Saga Pattern (Choreography / Orchestration)** dengan transaksi kompensasi menyelesaikan tantangan ini!

---

## 20. Summary & Knowledge Check
- [ ] Memahami batasan fisik single database yang memicu kebutuhan Sharding.
- [ ] Membedakan arsitektur Range-Based, Hash-Based, dan Directory-Based Sharding.
- [ ] Menguasai cara memilih Sharding Key yang tepat dan mencegah Hotspots.
- [ ] Memahami bahaya performa Scatter-Gather Query dan hilangnya Join relasional.
- [ ] Menguasai pembuatan ID terdistribusi unik (Snowflake / UUIDv7).
