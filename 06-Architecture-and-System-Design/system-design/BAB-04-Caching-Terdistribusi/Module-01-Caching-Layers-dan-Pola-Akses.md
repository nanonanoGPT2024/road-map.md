# MODULE 01: Caching Layer & Pola Akses Data

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Mengidentifikasi penempatan **Lapisan Caching (Caching Layers)** di sepanjang jalur request: Browser Cache, CDN Edge, API Gateway Cache, Application In-Memory, Distributed Cache (Redis), dan Database Buffer Pool.
2. Menguasai 4 pola akses caching fundamental: **Cache-Aside (Lazy Loading)**, **Read-Through**, **Write-Through**, dan **Write-Behind (Write-Back)**.
3. Menganalisis trade-off antara kesegaran data (*data freshness*), latensi penulisan, dan risiko kehilangan data (*data loss window*).
4. Mengimplementasikan dan membandingkan secara nyata pola Cache-Aside, Write-Through, dan Write-Behind menggunakan hands-on script.

---

## 2. Prerequisite
- Telah menyelesaikan [BAB 03: Traffic Management, Load Balancing, & Gateway](../BAB-03-Traffic-Management-Load-Balancing/).
- Memahami konsep latensi pembacaan data dari RAM (< 100 ns) vs Disk SSD (> 100 μs) vs Jaringan Network (> 1 ms).

---

## 3. Concept
Dalam rekayasa sistem terdistribusi, **Caching** adalah teknik menyimpan salinan data yang sering diakses atau membutuhkan komputasi mahal ke dalam media penyimpanan berkecepatan tinggi (biasanya RAM / memori utama) agar request berikutnya dapat dilayani jauh lebih cepat daripada mengambil dari media penyimpanan asli (*Origin Datastore / Database*).

Prinsip dasar caching berakar pada **Prinsip Lokalitas (*Locality of Reference*)**:
- **Temporal Locality:** Data yang baru saja diakses memiliki probabilitas sangat tinggi untuk diakses kembali dalam waktu dekat (misal: postingan viral di media sosial).
- **Spatial Locality:** Data yang berada di dekat alamat data yang baru saja diakses kemungkinan besar akan segera diakses (misal: membaca halaman berikutnya dari sebuah buku).

---

## 4. Why? (Mengapa Caching Menjadi Tulang Punggung Skalabilitas?)

### Perbedaan Kecepatan Akses Komponen Komputer (Latency Numbers Every Programmer Should Know)
Perhatikan hirarki kecepatan akses perangkat keras:

```text
+------------------------------------+-------------------------+
| Operasi                            | Waktu Nyata             |
+------------------------------------+-------------------------+
| L1 Cache CPU Read                  | 0.5 nanodetik           |
| L2 / L3 Cache CPU Read             | 7 nanodetik             |
| Main Memory (RAM) Read             | 100 nanodetik           |
| Solid State Drive (NVMe SSD) Read  | 150.000 nanodetik (150 μs)|
| Hard Disk Magnetik (HDD) Read      | 10.000.000 nanodetik(10 ms)|
| Network Round-Trip (Antar-DC)      | 30.000.000 nanodetik(30 ms)|
+------------------------------------+-------------------------+
```

> **Kesimpulan Kritis:** Membaca data dari **RAM** (seperti Redis) adalah **1.500x lebih cepat** daripada membaca dari SSD, dan **100.000x lebih cepat** daripada membaca dari Hard Disk! Database relasional (PostgreSQL/MySQL) yang harus mengecek integritas ACID ke disk akan selalu menjadi bottleneck jika setiap request dibiarkan menembus database secara langsung.

---

## 5. What? (Peta Lapisan Caching & 4 Pola Akses Utama)

### A. Peta 6 Lapisan Caching End-to-End

```text
[ 1. Client / Browser Cache ]  (HTTP Cache, Service Worker, LocalStorage)
              │
              ▼
[ 2. CDN Edge Cache ]          (Cloudflare, CloudFront: Aset statis & Micro-cache)
              │
              ▼
[ 3. API Gateway Cache ]       (Kong, Nginx: Cache respon endpoint publik)
              │
              ▼
[ 4. Application Local Cache ] (In-Memory Go/Node.js/Java: Guava, lru-cache)
              │
              ▼
[ 5. Distributed Cache ]       (Redis, Memcached: Shared cache untuk ratusan pods)
              │
              ▼
[ 6. Database Buffer Pool ]    (Postgres Shared Buffers, InnoDB Buffer Pool)
              │
              ▼
      [ Disk Storage ]         (NVMe SSD Database Persistence)
```

---

### B. 4 Pola Akses Caching Utama

#### 1. Cache-Aside (Lazy Loading)
Aplikasi bertanggung jawab penuh mengelola alur baca dan tulis antara Cache dan Database.

```text
   BACA DATA:                                   TULIS / UPDATE DATA:
   [ Aplikasi ]                                 [ Aplikasi ]
        │                                            │
        ├── 1. Cek ke [ Cache ]                      ├── 1. Tulis ke [ Database ]
        │      (Hit? Selesai!)                       │
        │      (Miss?)                               └── 2. Hapus (Invalidate) di [ Cache ]
        ├── 2. Ambil dari [ Database ]
        │
        └── 3. Simpan ke [ Cache ] (TTL)
```
- **Kelebihan:** Hanya data yang benar-benar diminta yang masuk ke cache (hemat memori). Jika cache node mati, sistem tetap berjalan normal (langsung fallback ke database).
- **Kekurangan:** Request pertama selalu mengalami *cache miss penalty*. Risiko inkonsistensi data jika write ke database berhasil tetapi proses invalidasi cache gagal.

#### 2. Read-Through Cache
Aplikasi hanya berurusan dengan Cache Library/Provider. Cache bertindak sebagai proxy transparan yang secara otomatis mengambil data dari database jika terjadi cache miss.

#### 3. Write-Through Cache
Aplikasi menulis data ke Cache, dan Cache secara **sinkron (synchronous)** menulis data tersebut ke Database sebelum mengembalikan respon sukses ke aplikasi.
- **Kelebihan:** Data di cache selalu 100% konsisten dengan database. Tidak ada data usang.
- **Kekurangan:** Latensi penulisan (*write latency*) lebih tinggi karena harus menunggu dua kali penulisan sukses (Cache + Database).

#### 4. Write-Behind (Write-Back) Cache
Aplikasi menulis data ke Cache, dan Cache langsung mengembalikan respon sukses seketika. Di background, Cache secara **asinkron (asynchronous batch)** menuliskan kumpulan data tersebut ke database.
- **Kelebihan:** Performa penulisan (*write throughput*) super cepat! Mengurangi beban IOPS database secara masif melalui teknik batching.
- **Kekurangan:** **Risiko Kehilangan Data (*Data Loss*)!** Jika server cache mati mendadak (misal listrik padam) sebelum data asinkron sempat di-flush ke database, data transaksi tersebut hilang permanen!

---

## 6. How? (Tabel Perbandingan 4 Pola Akses)

| Pola Caching | Read Latency | Write Latency | Konsistensi Data | Risiko Kehilangan Data | Use Case Ideal |
|---|---|---|---|---|---|
| **Cache-Aside** | Cepat (setelah hit) | Menengah | Eventual | Nol (DB source of truth) | Profil pengguna, Katalog produk |
| **Read-Through** | Cepat (setelah hit) | Menengah | Eventual | Nol | Abstraksi ORM / Read-heavy API |
| **Write-Through** | Sangat Cepat | Lambat (2x write) | Kuat / Tinggi | Nol | Data Finansial, Audit Log |
| **Write-Behind** | Sangat Cepat | Ekstrem Cepat | Lemah sementara | Ada (selama buffer time) | Like counter, View count, Telemetri IoT |

---

## 7. Analogy: Meja Belajar vs Lemari Arsip
- **Database:** Lemari arsip besar di gudang bawah tanah kantor Anda. Setiap ingin mengambil berkas, Anda harus turun tangga, membuka gembok, dan mencari di rak (butuh 5 menit).
- **Cache-Aside:** Meja kerja di samping Anda. Anda memeriksa meja kerja dulu. Jika ada, langsung baca. Jika tidak ada, Anda turun ke gudang, mengambil berkas, memfotokopi, dan menaruh satu salinan di meja kerja Anda untuk nanti.
- **Write-Behind:** Saat bos memberikan 100 memo tanda terima, Anda menumpuknya di meja kerja dan langsung berkata: *"Beres, Bos!"* Nanti saat sore hari sebelum pulang kerja, Anda sekaligus membawa tumpukan 100 memo itu ke gudang arsip dalam satu kali jalan (*batch update*).

---

## 8. Diagram: Alur Penulisan Aman pada Cache-Aside (Cache Invalidation)

Pertanyaan klasik arsitek: *Saat data diubah, apakah kita harus MENG-UPDATE isi cache, atau MENGHAPUS (IN彌ALIDATE) cache?*

```text
           [ ALUR YANG BENAR: WRITE DB -> DELETE CACHE ]

     1. TULIS PERUBAHAN KE DATABASE UTAMA
     [ Client ] ─────────────────────────▶ [ PostgreSQL DB ]
                                                  │
                                                  │ 2. Update Berhasil
                                                  ▼
     3. HAPUS KUNCI TERKAIT DARI CACHE
     [ Client ] ─────────────────────────▶ [ Redis Cache ] (DEL product:123)
```

> **Aturan Emas Arsitek:** **SELALU DELETE CACHE, JANGAN PERNAH OVERWRITE CACHE PADA PROSES WRITE!**  
> Jika Anda mencoba meng-update cache (`SET product:123 {new_val}`), race condition antara dua thread konkuren yang menulis secara bersamaan dapat menyebabkan cache menyimpan nilai lama secara permanen (*stale value overwrite*). Menghapus cache memaksa request pembacaan berikutnya mengambil data teranyar secara atomik dari database.

---

## 9. Simple Example: Implementasi Cache-Aside di Backend
```javascript
async function getProduct(productId) {
  const cacheKey = `product:${productId}`;

  // 1. Cek Redis Cache
  const cachedData = await redis.get(cacheKey);
  if (cachedData) {
    return JSON.parse(cachedData); // Cache HIT! (~1ms)
  }

  // 2. Cache MISS: Ambil dari Database
  const product = await db.query('SELECT * FROM products WHERE id = $1', [productId]);
  if (!product) return null;

  // 3. Simpan ke Redis dengan TTL 1 jam (3600 detik)
  await redis.set(cacheKey, JSON.stringify(product), 'EX', 3600);

  return product;
}
```

---

## 10. Practical Code Example
Lihat simulasi komparasi performa dan perilaku data antara Cache-Aside, Write-Through, dan Write-Behind pada:
`System-Design/BAB-04-Caching-Terdistribusi/hands-on/m01/cache_patterns_demo.js`

---

## 11. Real World Example: Counter Like Instagram & Tweet View Count Twitter
- **Masalah:** Ketika selebriti dengan 100 juta pengikut memposting video, tombol "Like" ditekan 50.000 kali per detik.
- **Pendekatan Tanpa Caching (Fatal):** 50.000 query `UPDATE posts SET likes = likes + 1 WHERE id = 123` langsung membunuh database relasional dalam hitungan detik karena disk lock.
- **Solusi Arsitektur (Write-Behind Cache):**
  1. Aplikasi mengeksekusi operasi atomik di Redis: `INCR post:likes:123` (menghabiskan waktu < 0.2 ms di memori).
  2. Sebuah background worker (setiap 10 detik sekali) membaca total angka like dari Redis dan melakukan 1 kali batch update ke database: `UPDATE posts SET likes = 500000 WHERE id = 123`.
  3. Database aman, user merasakan feedback antarmuka yang instan!

---

## 12. Trade-offs (Cache Invalidation: Update vs Delete)

| Strategi | Kelebihan | Risiko / Kekurangan | Rekomendasi |
|---|---|---|---|
| **Delete Cache on Write** | Bebas race-condition data usang | Request baca berikutnya mengalami cold miss | **Sangat Direkomendasikan** |
| **Update Cache on Write** | Read berikutnya tetap instan | Rentan race condition jika ada 2 write simultan | Hindari untuk data kritis |
| **Set TTL Only (No Invalidation)** | Kode sangat sederhana | User melihat data lama sampai TTL expired | Cocok untuk berita / tren |

---

## 13. When To Use What
- **Gunakan Cache-Aside:** Untuk 90% aplikasi web standar (e-commerce, social media profile, blog, settings).
- **Gunakan Write-Through:** Untuk data finansial, sistem inventory kuota terbatas di mana konsistensi mutlak dibutuhkan.
- **Gunakan Write-Behind:** Untuk sistem audit logging, analytics tracking, view counter, like counter, sensor data IoT.

---

## 14. When NOT To Use Caching
- **Dilarang keras mencache data yang:**
  1. Frekuensi pembacaannya sangat rendah (hanya diakses 1 kali setahun).
  2. Datanya berubah setiap milidetik secara konstan (seperti pergerakan harga saham live tick-by-tick).
  3. Memiliki volume data yang jauh lebih besar daripada kapasitas RAM server Anda tanpa strategi eviction yang ketat.

---

## 15. Common Mistakes
1. **Caching Tanpa Batas TTL (Time-To-Live):** Menyimpan kunci ke Redis tanpa parameter masa berlaku. Setelah 6 bulan, RAM server Redis penuh 100% (*Out of Memory*) dengan data sampah yang tidak pernah dibuka lagi.
2. **Tidak Menangani Nilai Kosong (Null Value):** Jika data produk #9999 tidak ada di database, aplikasi tidak mencache-nya. Akibatnya, bot penyerang membombardir request id acak dan seluruh request tembus menghantam database (*Cache Penetration*).
3. **Mencache Objek yang Terlalu Besar:** Menyimpan seluruh baris tabel pengguna termasuk riwayat transaksi 5 tahun ke dalam 1 kunci cache tunggal sebesar 10 MB. Serialisasi dan deserialisasi JSON 10 MB akan memblokir single-thread event loop Redis!

---

## 16. Best Practices

- **Must Have:**
  - Selalu sematkan **TTL (Masa Berlaku)** pada setiap item yang disimpan ke cache.
  - Terapkan pola **Delete on Write** untuk menjaga konsistensi data.
- **Recommended:**
  - Tambahkan jitter/variasi acak pada TTL (misal: `TTL = 3600 + random(0, 300)`) agar ribuan kunci tidak kadaluwarsa pada detik yang sama (*Cache Expiration Jitter*).
- **Advanced:**
  - Gunakan protokol biner berkinerja tinggi (seperti MessagePack atau Protobuf) alih-alih JSON string jika payload data cache sangat padat.
- **Avoid / Overengineering:**
  - Memasang Redis cluster 6 node untuk aplikasi internal perusahaan yang penggunanya hanya 50 karyawan kantor. Cukup gunakan in-memory LRU cache lokal di dalam aplikasi!

---

## 17. Troubleshooting Guide
```text
Gejala: Data di aplikasi tidak kunjung berubah meskipun admin sudah mengupdate database.
---------------------------------------------------------------------------------------
Kemungkinan Akar Masalah:
1. Admin mengupdate database langsung via SQL client (DBeaver / DataGrip) sehingga event invalidasi cache di aplikasi tidak terpanggil.
2. TTL disetel terlalu lama (misal 30 hari) tanpa webhook invalidasi.

Solusi:
- Hapus kunci cache manual via redis-cli: DEL product:123
- Bangun mekanisme CDC (Change Data Capture) menggunakan Debezium / Kafka:
  Setiap ada perubahan row di Postgres WAL (Write-Ahead Log), event otomatis memicu invalidasi di Redis secara transparan!
```

---

## 18. Hands-on Lab: Komparasi Cache-Aside vs Write-Through vs Write-Behind

File lab sudah disiapkan di:
`System-Design/BAB-04-Caching-Terdistribusi/hands-on/m01/cache_patterns_demo.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-04-Caching-Terdistribusi/hands-on/m01/cache_patterns_demo.js
```

### Yang Ditampilkan Script Ini:
1. Menguji pola **Cache-Aside**: Menunjukkan transisi dari Cache Miss (lambat) menjadi Cache Hit (instan), serta efek invalidasi saat data di-update.
2. Menguji pola **Write-Through**: Menghitung penalti latensi ganda (Cache + Database ditulis sinkron).
3. Menguji pola **Write-Behind**: Menunjukkan penulisan ultra-cepat ke memori, diikuti flush asinkron ke database secara bergelombang.

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan perbedaan mendasar antara pola *Cache-Aside* dan *Write-Through* dalam hal siapa yang bertanggung jawab menulis data ke database!

### Level 2 (Medium):
Sebuah artikel berita viral di-cache dengan TTL 1 jam. Wartawan mengoreksi kesalahan ketik (*typo*) pada paragraf pertama artikel tersebut.
1. Jika sistem menggunakan strategi "Update Cache on Write", apa risiko arsitektural yang bisa terjadi jika 2 redaktur mengedit artikel secara simultan?
2. Mengapa strategi "Delete Cache on Write" jauh lebih aman untuk integritas data?

### Level 3 (Hard):
Jelaskan arsitektur penanganan lonjakan penulisan like video live streaming sebesar 100.000 likes/detik menggunakan pola **Write-Behind Cache**! Bagaimana Anda merancang mekanisme pemulihan data (*data recovery*) jika server Redis crash di tengah jalan sebelum antrean asinkron sempat di-flush ke PostgreSQL?

---

## 20. Summary & Knowledge Check
- [ ] Memahami disparitas kecepatan hardware antara RAM (100 ns) vs Disk (150 μs - 10 ms).
- [ ] Menguasai 4 pola akses: Cache-Aside, Read-Through, Write-Through, Write-Behind.
- [ ] Menguasai aturan emas invalidasi: *Write to DB first, then Delete from Cache*.
- [ ] Memahami risiko kehilangan data pada Write-Behind dan cara mitigasinya.
- [ ] Mampu menghindari jebakan cache tanpa TTL dan data berukuran raksasa.
