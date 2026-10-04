# BAB 01 — Arsitektur Internal PostgreSQL, Proses Engine, & Memory Management — Quiz & Chapter Challenge

---

## 📝 Bagian 1: Ujian Konsep & Pemahaman Teknis (10 Soal Pilihan Ganda)

---

### Soal 1

Seorang DBA mengamati bahwa server PostgreSQL dengan konfigurasi `shared_buffers = 8GB` dan `work_mem = 256MB` mengalami OOM (Out of Memory) killer dari kernel Linux saat menjalankan query analitik berat dengan banyak koneksi paralel. Server memiliki RAM fisik 32GB. Apa penyebab paling mungkin dari kondisi ini?

**A.** `shared_buffers` terlalu besar sehingga menyebabkan kernel tidak memiliki cukup ruang untuk proses OS lainnya.

**B.** `work_mem` dialokasikan per-operasi per-proses, sehingga dengan 50 koneksi yang masing-masing menjalankan query dengan 5 sort node, total konsumsi memori potensial bisa mencapai `50 × 5 × 256MB = 64GB`, melampaui RAM fisik.

**C.** PostgreSQL tidak mendukung alokasi memori dinamis sehingga seluruh `work_mem` dialokasikan sekaligus saat server startup.

**D.** `shared_buffers` dan `work_mem` menggunakan pool memori yang sama sehingga terjadi konflik alokasi internal.

**✅ Kunci Jawaban: B**

**📖 Penjelasan Mendalam:**

`work_mem` adalah parameter yang sangat sering disalahpahami. Nilainya **bukan** total memori untuk seluruh server — melainkan batas memori **per operasi sort/hash per backend process**. Setiap query plan node yang memerlukan pengurutan (ORDER BY, DISTINCT, merge join) atau hashing (hash join, hash aggregation) dapat mengalokasikan hingga `work_mem` secara independen.

Kalkulasi worst-case:
```
Total RAM potensial = jumlah_koneksi × rata_rata_node_per_query × work_mem
                    = 50 × 5 × 256MB
                    = 64GB
```

Ini melampaui RAM fisik 32GB, sehingga kernel Linux mengaktifkan OOM killer.

**Mengapa A salah:** `shared_buffers = 8GB` dari 32GB (25%) masih dalam rentang rekomendasi umum (20–40% RAM). Masalahnya bukan di sini.

**Mengapa C salah:** PostgreSQL menggunakan alokasi memori dinamis (`palloc`/`malloc`). `work_mem` adalah *batas atas*, bukan alokasi tetap saat startup.

**Mengapa D salah:** `shared_buffers` menggunakan shared memory (SHM) yang terpisah dari private heap memory yang digunakan `work_mem`. Keduanya adalah pool yang berbeda secara fundamental.

**Solusi yang tepat:** Turunkan `work_mem` (misalnya ke `32MB` atau `64MB`) dan gunakan `SET work_mem` per-session untuk query analitik yang memang membutuhkan lebih banyak memori, atau pertimbangkan connection pooling untuk membatasi koneksi aktif.

---

### Soal 2

Perhatikan output `ps aux` berikut pada server PostgreSQL yang sedang berjalan:

```
postgres  1234  0.0  0.1  postmaster -D /var/lib/postgresql/data
postgres  1235  0.0  0.0  postgres: checkpointer
postgres  1236  0.0  0.0  postgres: background writer
postgres  1237  0.0  0.0  postgres: walwriter
postgres  1238  0.0  0.0  postgres: autovacuum launcher
postgres  1239  0.0  0.0  postgres: stats collector
postgres  1240  0.0  0.0  postgres: logical replication launcher
postgres  1289  0.2  0.3  postgres: app_user mydb 192.168.1.5(54321) SELECT
```

Proses mana yang bertanggung jawab memastikan bahwa dirty pages di `shared_buffers` ditulis ke disk secara periodik untuk mengurangi beban I/O saat checkpoint, **tanpa** menunggu checkpoint terjadi?

**A.** `checkpointer` — karena ini adalah tugas utamanya untuk mengelola semua penulisan disk.

**B.** `walwriter` — karena WAL harus ditulis lebih dulu sebelum data pages.

**C.** `background writer` — karena ia secara proaktif menulis dirty pages ke disk menggunakan algoritma LRU-based scanning.

**D.** `autovacuum launcher` — karena proses ini mengelola lifecycle halaman termasuk penulisan ulang ke disk.

**✅ Kunci Jawaban: C**

**📖 Penjelasan Mendalam:**

**Background Writer (bgwriter)** memiliki peran spesifik: ia secara periodik melakukan scanning terhadap `shared_buffers` dan menuliskan *dirty pages* (halaman yang telah dimodifikasi) ke disk **di luar siklus checkpoint**. Tujuannya adalah:

1. **Mengurangi spike I/O saat checkpoint** — jika bgwriter sudah "pre-clean" banyak halaman, checkpoint tidak perlu menulis semuanya sekaligus.
2. **Memastikan buffer bersih tersedia** — sehingga backend process tidak perlu menunggu eviction saat membutuhkan buffer baru.

Parameter yang mengontrolnya:
```ini
bgwriter_delay = 200ms          # interval antar siklus scanning
bgwriter_lru_maxpages = 100     # max halaman per siklus
bgwriter_lru_multiplier = 2.0   # faktor prediksi kebutuhan buffer bersih
```

**Mengapa A salah:** `checkpointer` memang menulis dirty pages, tetapi hanya pada saat checkpoint terjadi (triggered by `checkpoint_timeout` atau `max_wal_size`). Ia tidak berjalan secara kontinyu di antara checkpoint.

**Mengapa B salah:** `walwriter` bertanggung jawab memflush WAL buffer ke WAL files (pg_wal/) secara periodik. Ia tidak menyentuh data pages di shared_buffers sama sekali. Ini mengimplementasikan prinsip WAL (Write-Ahead Logging) di mana log harus ditulis sebelum data.

**Mengapa D salah:** `autovacuum launcher` mengelola proses VACUUM dan ANALYZE untuk reclaim dead tuples dan update statistik. Ia tidak terlibat dalam penulisan buffer pages ke disk.

---

### Soal 3

Seorang developer menemukan bahwa query berikut berjalan sangat lambat meskipun tabel `orders` memiliki index pada kolom `customer_id`:

```sql
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM orders WHERE customer_id = 12345;
```

Output menunjukkan:
```
Seq Scan on orders  (cost=0.00..45000.00 rows=1 width=200)
                    (actual time=0.050..890.234 rows=1 loops=1)
  Filter: (customer_id = 12345)
  Rows Removed by Filter: 2999999
  Buffers: shared hit=0 read=16384
```

Kondisi `shared hit=0` dan `read=16384` mengindikasikan apa?

**A.** Index tidak digunakan karena query planner menemukan bug pada statistik tabel.

**B.** Seluruh 16.384 halaman data dibaca langsung dari disk (atau OS page cache) karena tidak ada satupun halaman yang ditemukan di `shared_buffers`, mengindikasikan buffer cache miss total.

**C.** PostgreSQL sengaja bypass `shared_buffers` untuk tabel besar menggunakan Direct I/O demi performa yang lebih baik.

**D.** `shared hit=0` berarti query berjalan dalam mode read-only sehingga tidak diizinkan menggunakan cache.

**✅ Kunci Jawaban: B**

**📖 Penjelasan Mendalam:**

Dalam output `EXPLAIN (BUFFERS)`, dua metrik kritis adalah:

| Metrik | Arti |
|--------|------|
| `shared hit=N` | N halaman ditemukan di `shared_buffers` (cache hit — sangat cepat) |
| `shared read=N` | N halaman harus dibaca dari luar `shared_buffers` (disk atau OS page cache) |

`shared hit=0, read=16384` berarti **100% cache miss** — seluruh 16.384 halaman (= 16.384 × 8KB = 128MB data) harus diambil dari luar shared_buffers. Ini bisa terjadi karena:

1. Query ini adalah yang pertama dijalankan setelah server restart (cold cache)
2. `shared_buffers` terlalu kecil sehingga data tabel ini sudah di-evict
3. Tabel baru saja di-load dan belum pernah di-query

**Mengapa Seq Scan dipilih alih-alih Index Scan?** Ini adalah masalah terpisah — planner memilih Seq Scan kemungkinan karena statistik (`pg_statistic`) tidak akurat (perlu `ANALYZE`), atau selectivity yang diestimasi terlalu rendah.

**Mengapa A salah:** Query planner tidak memiliki "bug" — ia membuat keputusan berdasarkan statistik. Jika statistik tidak akurat, jalankan `ANALYZE orders;`.

**Mengapa C salah:** PostgreSQL secara default **tidak** menggunakan Direct I/O. Semua I/O melewati OS page cache. Fitur Direct I/O baru diperkenalkan secara eksperimental di PostgreSQL 16 dengan parameter `io_method`.

**Mengapa D salah:** Mode read-only tidak mempengaruhi penggunaan shared_buffers. Cache digunakan untuk semua operasi baca terlepas dari jenis transaksi.

---

### Soal 4

Dalam konteks arsitektur multi-process PostgreSQL, apa yang terjadi secara internal ketika sebuah client application membuat koneksi TCP baru ke PostgreSQL?

**A.** Postmaster langsung menyerahkan koneksi ke salah satu backend process yang sudah ada di pool untuk efisiensi.

**B.** Postmaster menerima koneksi, melakukan autentikasi awal, kemudian memanggil `fork()` untuk membuat backend process baru yang mewarisi file descriptor dan akses ke shared memory, lalu postmaster kembali menunggu koneksi berikutnya.

**C.** PostgreSQL menggunakan thread baru (bukan process) untuk setiap koneksi demi efisiensi memori dan context switching yang lebih rendah.

**D.** Koneksi langsung ditangani oleh background writer process yang berfungsi ganda sebagai connection handler.

**✅ Kunci Jawaban: B**

**📖 Penjelasan Mendalam:**

PostgreSQL menggunakan model **process-per-connection** (bukan thread), yang merupakan salah satu karakteristik arsitektur paling fundamental-nya. Alur lengkapnya:

```
Client TCP Connect
        ↓
   Postmaster (PID 1234) — listen() pada port 5432
        ↓
   accept() koneksi masuk
        ↓
   Verifikasi pg_hba.conf (apakah koneksi diizinkan?)
        ↓
   fork() → Backend Process baru (PID 1289)
        ↓
   Backend melakukan:
   - Autentikasi (password, GSSAPI, SCRAM-SHA-256, dll)
   - Attach ke shared memory (shared_buffers, lock tables, dll)
   - Inisialisasi per-backend memory context
        ↓
   Postmaster kembali ke loop accept()
```

**Keunggulan model fork():**
- **Isolasi fault:** Jika satu backend crash, postmaster mendeteksi via `SIGCHLD` dan hanya me-restart komponen yang diperlukan tanpa mempengaruhi backend lain
- **Keamanan:** Setiap process memiliki address space terpisah
- **Simplicity:** Tidak ada race condition pada shared state per-connection

**Overhead fork():** Ini adalah alasan mengapa connection pooler (PgBouncer, pgpool-II) sangat direkomendasikan untuk aplikasi dengan banyak koneksi short-lived — karena setiap `fork()` memiliki overhead CPU dan memori.

**Mengapa A salah:** PostgreSQL tidak memiliki built-in connection pool di level postmaster. Setiap koneksi selalu menghasilkan `fork()` baru.

**Mengapa C salah:** PostgreSQL menggunakan **process**, bukan thread. Ini berbeda dengan MySQL/MariaDB yang menggunakan thread-per-connection. Proposal untuk migrasi ke threading model sudah lama didiskusikan di komunitas PostgreSQL tetapi belum diimplementasikan secara penuh (per PostgreSQL 16).

**Mengapa D salah:** Background writer adalah proses dedicated untuk I/O management dan tidak memiliki kemampuan untuk menangani koneksi client.

---

### Soal 5

Perhatikan konfigurasi PostgreSQL berikut dan skenario crash recovery:

```ini
# postgresql.conf
wal_level = replica
checkpoint_timeout = 15min
max_wal_size = 1GB
synchronous_commit = off
fsync = on
```

Server mengalami crash mendadak (power failure). Saat restart, PostgreSQL melakukan recovery. Pernyataan mana yang **paling akurat** menggambarkan proses recovery dalam konteks konfigurasi di atas?

**A.** Karena `synchronous_commit = off`, semua transaksi yang commit sebelum crash dianggap hilang dan database dikembalikan ke state checkpoint terakhir saja.

**B.** PostgreSQL membaca WAL dari titik checkpoint terakhir yang valid, me-replay semua WAL records hingga end of WAL, memastikan konsistensi data. Transaksi yang sudah commit tetapi WAL-nya belum di-fsync ke disk mungkin hilang karena `synchronous_commit = off`.

**C.** Karena `fsync = on`, semua data dijamin tidak hilang termasuk transaksi yang belum commit sekalipun.

**D.** `max_wal_size = 1GB` membatasi recovery hanya pada 1GB WAL terakhir, sehingga transaksi sebelum batas ini tidak dapat di-recover.

**✅ Kunci Jawaban: B**

**📖 Penjelasan Mendalam:**

Proses crash recovery PostgreSQL mengikuti protokol **ARIES (Algorithm for Recovery and Isolation Exploiting Semantics)**:

**Fase Recovery:**
```
1. ANALYSIS PHASE
   └─ Baca pg_control untuk menemukan checkpoint terakhir yang valid
   
2. REDO PHASE  
   └─ Replay semua WAL records dari last checkpoint → end of WAL
   └─ Ini memastikan semua perubahan yang sudah di-WAL di-apply ke data files
   
3. UNDO PHASE (implicit via MVCC
