# BAB 09: Transactions, Concurrency, Locking, & MVCC
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis dan Membedah Arsitektur Internal MVCC**: Memahami perbedaan fundamental implementasi Multi-Version Concurrency Control (MVCC) antara Append-only storage engine (PostgreSQL: `xmin`, `xmax`, Vacuuming, Heap-Only Tuples) dan Rollback/Undo-Log engine (MySQL InnoDB: Rollback Segments, Read View, Undo Logs).
2. **Menguasai Hierarki Locking & Concurrency Control**: Mengimplementasikan dan mengontrol row-level locks, table-level locks, gap locks, next-key locks, intent locks, advisory locks, serta predicate locks (Serializable Snapshot Isolation).
3. **Mendiagnosis dan Mengeliminasi Anomali Transaksi Tingkat Lanjut**: Mengidentifikasi serta merekayasa mitigasi terhadap *Write Skew*, *Read Skew*, *Lost Updates*, dan *Phantom Reads* pada sistem transaksional throughput tinggi.
4. **Membangun Sistem Deteksi & Penanganan Deadlock**: Mengonfigurasi dan menganalisis *Wait-For Graph* engine, mengevaluasi transaction abort cost, serta mengotomatisasi mekanisme *exponential backoff retry* pada layer aplikasi.
5. **Mengarsiteksi Pola Transaksi Terdistribusi**: Mendesain arsitektur *Transactional Outbox Pattern* dan *Optimistic Concurrency Control (OCC)* berbasis kolom versi untuk integrasi microservices yang decoupled.
6. **Melakukan Profiling dan Observabilitas Lock Engine Produksi**: Menggunakan katalog internal (`pg_locks`, `pg_stat_activity`, `sys.innodb_lock_waits`) untuk mengidentifikasi bottleneck konkurensi dan mencegah insiden *transaction ID wraparound*.

---

### 2. Prerequisite

Sebelum mendalami modul ini, Anda wajib menguasai:
*   Prinsip dasar ACID (Atomicity, Consistency, Isolation, Durability).
*   Sintaks DML dasar (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) dan transaksi (`BEGIN`, `COMMIT`, `ROLLBACK`).
*   Konsep 4 standar Transaction Isolation Level menurut ANSI/ISO SQL-92 (Read Uncommitted, Read Committed, Repeatable Read, Serializable).
*   Dasar-dasar indeks database (B-Tree index structure).
*   Koneksi client-server database menggunakan terminal psql atau mysql CLI.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Internal MVCC: PostgreSQL (Append-Only) vs. MySQL InnoDB (Undo Log)

MVCC memungkinkan database engine untuk melayani operasi pembacaan (*readers*) dan penulisan (*writers*) secara simultan tanpa saling memblokir (*readers do not block writers, writers do not block readers*). Namun, pendekatan arsitektur penyimpanan versinya sangat berbeda di level disk:

```
[PostgreSQL Heap-based MVCC]
Heap Page
+-------------------------------------------------------------+
| Tuple v1: [xmin: 100, xmax: 101, data: "Balance: 1000"]    | <-- Dead Tuple (setelah TX 101)
| Tuple v2: [xmin: 101, xmax: 0,   data: "Balance: 1500"]    | <-- Live Tuple
+-------------------------------------------------------------+
* UPDATE = INSERT tuple baru di Heap + UPDATE xmax tuple lama.
* Membutuhkan autovacuum untuk mereklamasi ruang dead tuple.

[MySQL InnoDB Undo-Log MVCC]
Clustered Index Leaf Page (IBD)          Undo Tablespace
+--------------------------------+       +-----------------------------+
| Row: [data: "Balance: 1500"]   | ----> | Undo Record (v1):           |
| DB_TRX_ID: 101                 |       | [data: "Balance: 1000",     |
| DB_ROLL_PTR: 0x7f01a --------+ |       |  DB_TRX_ID: 100, ROLL_PTR]  |
+------------------------------|-+       +-----------------------------+
                               +---------^
* UPDATE = In-place update di Clustered Index + Tulis data lama ke Undo Log.
* Membutuhkan Purge Threads untuk membersihkan Undo Pages ketika tidak lagi dibutuhkan Read View.
```

##### 1. PostgreSQL (Append-Only Page Model)
*   **Header Tuple**: Setiap tuple memiliki header metadata tersembunyi:
    *   `xmin`: Transaction ID (XID) pembuat tuple.
    *   `xmax`: XID transaksi yang memperbarui atau menghapus tuple. Jika bernilai `0`, tuple masih aktif (live).
    *   `t_ctid`: Pointer fisik `(block, offset)` ke versi tuple terbaru.
*   **Visibilitas Snapshot**: Snapshot direpresentasikan oleh array XID: `xmin:xmax:xip_list`. XID sebelum `xmin` terlihat; XID setelah `xmax` tidak terlihat; XID di dalam `xip_list` (transaksi aktif/in-flight) tidak terlihat.
*   **HOT (Heap-Only Tuples)**: Optimasi di mana update tuple baru ditempatkan di blok yang sama tanpa mengubah pointer index eksternal, memotong beban I/O indeks.
*   **Vacuuming & Transaction Wraparound**: XID PostgreSQL adalah bilangan unsigned 32-bit (~4,2 miliar). Vacuuming bertugas menandai tuple lama sebagai "frozen" (`FrozenXID`) untuk mencegah bencana *transaction ID wraparound* yang menyebabkan data lama tak terlihat.

##### 2. MySQL InnoDB (Undo Log & Rollback Segment Model)
*   **Clustered Index**: Data tabel selalu disimpan dalam leaf node B+Tree primary key.
*   Setiap record memiliki system columns tersembunyi:
    *   `DB_TRX_ID` (6 byte): Menyimpan ID transaksi terakhir yang menyisipkan/memperbarui record.
    *   `DB_ROLL_PTR` (7 byte): Menyimpan pointer yang merujuk ke Undo Log record di rollback segment.
*   **Read View Engine**: Saat transaksi membuat snapshot pembacaan, InnoDB membuat struktur data `Read View` yang berisi rentang `low_limit_id`, `up_limit_id`, dan array transaksi aktif (`m_ids`).
*   Jika `DB_TRX_ID` pada leaf node lebih besar atau sama dengan batas visibilitas Read View, engine akan menelusuri rantai `DB_ROLL_PTR` ke belakang (secara sekuensial) hingga menemukan versi data yang memenuhi visibilitas.

---

#### B. Anatomi Locking Engine

Database modern menggunakan hirarki lock engine berlapis untuk menjamin integritas data:

```
                  +----------------------------------+
                  |         DATABASE / TABLE         |
                  |     (IS, IX, S, X Lock Level)    |
                  +-----------------+----------------+
                                    |
                                    v
       +---------------------------------------------------------+
       |                        ROW LEVEL                        |
       +----------------------------+----------------------------+
       | PostgreSQL                 | MySQL InnoDB               |
       | - FOR UPDATE (Exclusive)   | - Record Lock (Posisional) |
       | - FOR NO KEY UPDATE        | - Gap Lock (Rentang)       |
       | - FOR SHARE (Shared)       | - Next-Key Lock (Record    |
       | - FOR KEY SHARE            |     + Gap sebelumnya)      |
       | - Predicate Lock (SSI)     |                            |
       +----------------------------+----------------------------+
```

##### 1. Intent Locks (Table Level)
Sebelum transaksi diizinkan mengunci baris spesifik (*row-level*), database engine harus memperoleh *Intent Lock* pada level tabel untuk mencegah transaksi lain mengeksekusi operasi DDL atau lock eksklusif tabel penuh:
*   **Intent Shared (IS)**: Mengindikasikan transaksi berniat mengunci baris secara eksplisit dengan Shared Lock.
*   **Intent Exclusive (IX)**: Mengindikasikan transaksi berniat mengunci baris secara eksklusif (misal: `SELECT ... FOR UPDATE`, `UPDATE`).

##### 2. InnoDB Specific: Gap Locks & Next-Key Locks
Untuk mencegah anomali *Phantom Read* pada level isolasi `REPEATABLE READ`, InnoDB tidak hanya mengunci baris fisik, tetapi juga ruang kosong (*gap*) di antara nilai index:
*   **Record Lock**: Mengunci record index yang dituju.
*   **Gap Lock**: Mengunci interval index sebelum, di antara, atau sesudah nilai index yang ada (misal: antara id 5 dan id 10). Mencegah transaksi lain melakukan `INSERT` ke dalam rentang tersebut.
*   **Next-Key Lock**: Kombinasi Record Lock pada index record bersangkutan ditambah Gap Lock pada rentang sebelum record tersebut: `(previous_key, current_key]`.

##### 3. Serializable Snapshot Isolation (SSI) & Predicate Locking
Alih-alih mengunci rentang data secara fisik yang menghambat konkurensi (seperti Gap Lock), PostgreSQL Serializable mengimplementasikan *SIREAD Locks* (Predicate Locks). Lock ini adalah metadata non-blocking di memori. Engine memonitor *rw-antidependency cycles* (situasi di mana satu transaksi membaca data yang diubah transaksi lain, dan keduanya saling bergantung). Jika terjadi siklus (pemicu *Write Skew*), engine membatalkan salah satu transaksi dengan error `40001 (serialization_failure)`.

---

#### C. Matriks Kompatibilitas Lock

| Lock Type yang Diminta \ Lock yang Sedang Berjalan | Intent Shared (IS) | Intent Exclusive (IX) | Shared (S) | Exclusive (X) |
| :--- | :--- | :--- | :--- | :--- |
| **Intent Shared (IS)** | Kompatibel | Kompatibel | Kompatibel | Konflik |
| **Intent Exclusive (IX)**| Kompatibel | Kompatibel | Konflik | Konflik |
| **Shared (S)** | Kompatibel | Konflik | Kompatibel | Konflik |
| **Exclusive (X)** | Konflik | Konflik | Konflik | Konflik |

---

### 4. Why & What

#### Mengapa Concurrency Control Penting?
Tanpa kontrol konkurensi lanjutan, peningkatan throughput sistem (ribuan transaksi per detik) berbanding lurus dengan timbulnya degradasi konsistensi data:
*   **Double Spending Bug**: Saldo berkurang dua kali lipat atau tidak sama sekali akibat transaksi konkuren membaca status yang sama.
*   **Write Skew**: Dua transaksi memeriksa integritas batasan bisnis yang sama, kemudian keduanya memodifikasi data yang berbeda secara terpisah, menghasilkan keadaan inkonsisten global yang melanggar batasan bisnis.
*   **System Hang / Cascading Rollbacks**: Deadlock yang lambat dideteksi menyebabkan pool koneksi kehabisan worker thread (*thread starvation*), yang berakibat pada kegagalan kaskade (*cascading failure*) di seluruh sistem backend.

#### Apa yang Harus Dihindari?
*   Menggunakan `SELECT ... FOR UPDATE` membabi buta tanpa klausa `NOWAIT` atau `SKIP LOCKED` pada high-throughput job queue.
*   Mengandalkan level isolasi default (seperti `READ COMMITTED`) untuk transaksi inventaris/keuangan tanpa validasi kontrol optimistik atau locking eksplisit.
*   Menjalankan transaksi long-running (seperti batch reporting) di dalam transaksi write interaktif OLTP, yang memicu bloat table di PostgreSQL atau Undo retention spike di InnoDB.

---

### 5. How: Workflow Detail

#### A. Alur Kerja Deteksi Deadlock (Wait-For Graph)
1. **Lock Request**: Transaksi A meminta lock eksklusif pada Baris X yang sedang dipegang oleh Transaksi B.
2. **Edge Creation**: Engine mendeteksi konflik dan menambahkan directed edge: `Tx_A -> Tx_B` (A menunggu B).
3. **Circular Wait Detection**: Background thread (misal setiap `deadlock_timeout` di Postgres, default 1 detik, atau internal thread di InnoDB) menelusuri graf dependensi.
4. **Victim Selection**: Jika ditemukan dependensi siklis (`Tx_A -> Tx_B -> Tx_A`), engine memilih "victim" berdasarkan metrik tertentu (biaya rollback terkecil atau transaksi yang memegang lock paling sedikit).
5. **Abort & Error Propagation**: Transaksi victim dibatalkan secara paksa dengan sinyal rollback dan error dikirim ke layer aplikasi client.

```
       [Tx A memegang Lock-1] <-------- Menunggu Lock-1 --------- [Tx B]
                 |                                                 ^
                 |                                                 |
                 +---- Menunggu Lock-2 ----> [Tx B memegang Lock-2]-+
                          *** SIKLUS DEADLOCK TERBENTUK ***
                                    |
                     Engine Engine Wait-For Graph
                                    v
                     Tx B Dipilih Menjadi Korban (Aborted)
```

#### B. Alur Eksekusi Optimistic Concurrency Control (OCC)
1. **Read Phase**: Ambil record beserta atribut versi (`version = N`).
2. **Application Processing**: Lakukan kalkulasi bisnis di luar transaksi database.
3. **Write Phase**: Eksekusi update bersyarat atomik:
   ```sql
   UPDATE accounts 
   SET balance = balance - 100, version = version + 1 
   WHERE id = 42 AND version = N;
   ```
4. **Validation Phase**:
   *   Jika *row count affected* = 1: Transaksi sukses.
   *   Jika *row count affected* = 0: Terjadi tabrakan konkurensi (*stale read*). Aplikasi melakukan rollback dan mengeksekusi *retry strategy*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Berkas & Notaris Perubahan
*   **PostgreSQL MVCC**: Seperti menduplikasi berkas fisik secara utuh setiap kali ada kata yang dicoret (*Append-Only*). Berkas lama tetap ada di laci dengan stempel "Kedaluwarsa oleh Akta No. 101". Ketika laci penuh, petugas arsip (*Vacuum*) datang membuang berkas-berkas kedaluwarsa tersebut.
*   **InnoDB MVCC**: Berkas asli diubah langsung di tempat (*In-Place*), namun sebelum mencoret tulisan lama, notaris menyalin tulisan lama tersebut ke lembaran kertas tempel (*Undo Log*) yang dihubungkan dengan benang merah (*Rollback Pointer*) ke berkas asli. Jika ada pengunjung yang datang membaca dengan kartu izin lama, ia membaca berkas asli sembari membaca benang merah kertas tempel untuk melihat isi dokumen sebelum direvisi.

```
[VISUALISASI ANOMALI: WRITE SKEW]
Kondisi Awal: Alice dan Bob adalah dokter jaga. Syarat: Minimal 1 dokter aktif.

Trans. 1 (Alice)                              Trans. 2 (Bob)
|                                             |
|-- SELECT count(*) FROM on_call; (hasil: 2)  |
|                                             |-- SELECT count(*) FROM on_call; (hasil: 2)
|-- Validasi: 2 >= 2 -> Boleh Nonaktif       |
|                                             |-- Validasi: 2 >= 2 -> Boleh Nonaktif
|-- UPDATE doctors SET on_call = false        |
|   WHERE name = 'Alice';                     |
|                                             |-- UPDATE doctors SET on_call = false
|-- COMMIT;                                   |   WHERE name = 'Bob';
|                                             |-- COMMIT;
v                                             v
Status Akhir: count(*) = 0! (PELANGGARAN INVARIAN BISNIS)
*Catatan: READ COMMITTED dan REPEATABLE READ snapshot isolation mengizinkan anomali ini.*
*Hanya SERIALIZABLE atau locking eksklusif yang mampu mencegahnya.*
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Explicit Row-Level Locking Anti-Race Condition
Pencegahan Race Condition pada sistem reservasi tiket kursi sederhana:

```sql
-- DDL
CREATE TABLE seats (
    seat_id VARCHAR(10) PRIMARY KEY,
    status VARCHAR(20) NOT NULL, -- 'AVAILABLE', 'RESERVED'
    locked_by VARCHAR(50),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO seats (seat_id, status) VALUES ('A1', 'AVAILABLE');

-- Skenario: User mencoba memesan kursi A1
BEGIN;
SELECT seat_id, status 
FROM seats 
WHERE seat_id = 'A1' AND status = 'AVAILABLE'
FOR UPDATE; -- Mengunci baris secara eksklusif

-- Logika aplikasi memvalidasi ketersediaan
UPDATE seats 
SET status = 'RESERVED', locked_by = 'USR-9921', updated_at = NOW()
WHERE seat_id = 'A1';

COMMIT;
```

#### Practical Example: High-Throughput Job Queue (Worker Pattern) Menggunakan PostgreSQL `SKIP LOCKED`
Mekanisme worker queue tanpa lock contention:

```sql
-- DDL
CREATE TABLE transactional_jobs (
    id BIGSERIAL PRIMARY KEY,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    retry_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_jobs_pending ON transactional_jobs (id) WHERE status = 'PENDING';

-- WORKER QUERY: Mengambil batch 5 job tanpa diblokir oleh worker lain
BEGIN;

WITH selected_jobs AS (
    SELECT id 
    FROM transactional_jobs
    WHERE status = 'PENDING'
    ORDER BY id ASC
    LIMIT 5
    FOR UPDATE SKIP LOCKED -- Baris yang di-lock oleh worker lain dilewati seketika
)
UPDATE transactional_jobs j
SET status = 'PROCESSING',
    updated_at = CLOCK_TIMESTAMP()
FROM selected_jobs sj
WHERE j.id = sj.id
RETURNING j.id, j.payload;

-- Eksekusi logic payload di layer aplikasi...
-- Selesai:
-- UPDATE transactional_jobs SET status = 'COMPLETED' WHERE id IN (...);
COMMIT;
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Flash Sale E-Commerce Skala Enterprise (Inventaris Minus & Deadlock Spike)
*   **Konteks**: Sebuah platform retail skala besar menghadapi lonjakan trafik 120.000 request per detik saat *Flash Sale* smartphone edisi terbatas.
*   **Masalah**: 
    1. Ribuan database threads mencoba melakukan update inventaris baris yang sama: `UPDATE inventory SET stock = stock - 1 WHERE item_id = 9982`.
    2. Menghasilkan lonjakan konkurensi thread yang ekstrem (thread pool saturation) pada database, CPU tembus 100%, ribuan deadlock terdeteksi per detik.
    3. Akibat *Read Committed Isolation*, terjadi anomali *Lost Updates* dan inventaris over-sold (stok tercatat `-42`).

#### Arsitektur Solusi Terintegrasi

```
           [100,000 TPS Flash Sale Request]
                         |
                         v
       [Layer Aplikasi: Redis Sharded Atomic Counter]
                         |
                         v
         (Async Ingestion via Apache Kafka)
                         |
                         v
     [Database Worker Cluster: Inventory Decoupling]
                         |
             +-----------+-----------+
             |                       |
             v                       v
      PostgreSQL Shards        Inventory Aggregation
  (Advisory Lock Bucket)    (Transactional Outbox Pattern)
```

1. **Inventory Sharding di Level Database**:
   Alih-alih mengunci 1 baris stok utama, stok 10.000 unit dipecah menjadi 20 *bucket* baris terpisah di database:
   ```sql
   CREATE TABLE inventory_buckets (
       item_id BIGINT NOT NULL,
       bucket_id INT NOT NULL,
       stock_count INT NOT NULL,
       PRIMARY KEY (item_id, bucket_id),
       CHECK (stock_count >= 0) -- Menjamin secara fisik stok tidak pernah minus
   );
   ```
2. **Kueri Pengurangan Stok Cerdas**:
   Aplikasi mendistribusikan request update ke bucket random secara acak, dan jika bucket kosong, melompat ke bucket lain tanpa memblokir seluruh sistem:
   ```sql
   UPDATE inventory_buckets
   SET stock_count = stock_count - 1
   WHERE item_id = 9982 
     AND bucket_id = floor(random() * 20)::int
     AND stock_count > 0;
   ```
3. **PostgreSQL Session-Level Advisory Lock untuk Idempotency**:
   Mencegah double-order pembayaran pada level gateway menggunakan hashing deterministik:
   ```sql
   -- Mengunci token pembayaran transaksi unik sebelum mutasi
   SELECT pg_try_advisory_xact_lock(hashtext('ORDER_TX_KEY_99281729'));
   -- Mengembalikan true jika lock didapatkan, false jika sedang diproses instance lain
   ```

*   **Hasil Evaluasi**: Transaksi deadlock turun 99.98%, Database load CPU turun dari 100% ke 32%, throughput pemrosesan order stabil di 45.000 checkout/detik tanpa insiden stok minus.

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan Utama | Kerugian / Konsekuensi (*Trade-offs*) | Konteks Ideal Penggunaan |
| :--- | :--- | :--- | :--- |
| **Pessimistic Locking** (`FOR UPDATE`) | Menjamin integritas absolut; mencegah serializability anomalies secara deterministik. | Menahan lock fisik, mengurangi throughput; potensi deadlock tinggi jika urutan lock inkonsisten. | Sistem perbankan, mutasi ledger akuntansi, checkout finite stock. |
| **Optimistic Concurrency Control** (OCC) | Non-blocking readers & writers; skalabilitas tinggi pada skenario *read-heavy*. | Abort rate tinggi saat skenario *high contention*; biaya latency retry di level aplikasi. | Profil pengguna, entri katalog, CMS, low-frequency update entities. |
| **Pessimistic: `SKIP LOCKED`** | Latency nol untuk task-claiming; mengeliminasi lock wait queue. | Urutan prioritas tidak dijamin seratus persen strict; hanya cocok untuk decoupling batch. | Message queues, background workers, scheduled job dispatching. |
| **Serializable Isolation (SSI)** | Menjamin keamanan transaksi tanpa perlu manajemen locking manual yang rawan human error. | Tingginya tingkat abort (`40001 serialization_failure`); membutuhkan arsitektur retry di client. | Analisis finansial kompleks, pergeseran shift kerja medis, audit kepatuhan. |
| **Append-Only MVCC (PG)** | Write pipeline cepat; rollback hampir instan (*free cost*). | Bloat table fisik; CPU/IO overhead untuk autovacuum process; risiko freeze storm. | OLTP dinamis dengan disk I/O bertaraf enterprise (NVMe SSD). |
| **Undo-Log MVCC (InnoDB)** | Ukuran file tabel stabil; update in-place mengurangi write amplifikasi indeks. | Rollback lambat pada long transactions; Undo Log bloat menurunkan throughput read jika purge terhambat. | Sistem dengan rasio write-to-read homogen yang menuntut space management ketat. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan: Blind Updates yang Memicu Deadlock
*   *Pola Buruk*: Transaksi A mengupdate Tabel 1 lalu Tabel 2. Transaksi B mengupdate Tabel 2 lalu Tabel 1 secara konkuren.
*   *Solusi*: Terapkan **Resource Ordering Contract** secara ketat di seluruh tim engineering. Akses tabel dan pemesanan baris (`ORDER BY id`) harus selalu deterministik dan seragam di semua endpoint.

#### 2. Insiden: PostgreSQL Table Bloat Akibat Long-Running Transactions
*   *Penyebab*: Transaksi analitik yang berjalan berjam-jam menahan `xmin` visibilitas, mencegah Autovacuum mereklamasi dead tuples pada tabel transaksional yang aktif.
*   *Diagnosa*:
    ```sql
    -- Mendeteksi transaksi aktif yang menahan vacuum tertua
    SELECT pid, now() - xact_start AS duration, query, state
    FROM pg_stat_activity
    WHERE state != 'idle'
    ORDER BY duration DESC
    LIMIT 5;
    ```
*   *Mitigasi*: Set `idle_in_transaction_session_timeout = '15s'` dan gunakan replica analitik terpisah dengan `hot_standby_feedback = off` (atau toleransi replication delay).

#### 3. Diagnosa Mutlak Lock Contention
Untuk mendeteksi transaksi mana yang memblokir transaksi mana:

##### PostgreSQL:
```sql
SELECT
    blocked_locks.pid     AS blocked_pid,
    blocked_activity.usename  AS blocked_user,
    blocking_locks.pid    AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query    AS blocked_statement,
    blocking_activity.query   AS current_statement_in_blocking_process
FROM  pg_catalog.pg_locks         blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks         blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND