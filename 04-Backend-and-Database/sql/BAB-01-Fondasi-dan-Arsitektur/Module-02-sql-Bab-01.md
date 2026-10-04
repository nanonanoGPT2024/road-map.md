# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Mekanisme Internal Mesin Database**: Membedah struktur penyimpanan fisik (*page/block*, *tuple header*, *free space map*), siklus hidup transaksi (*WAL*, *Dirty Pages*, *Checkpointing*), dan konkurensi data (*MVCC*, *Lock Manager*).
2. **Mengoptimalkan Query Execution Pipeline**: Menganalisis *cost-based optimizer* (CBO), membaca *physical execution plan* (`EXPLAIN ANALYZE BUFFERS`), serta mengeliminasi bottleneck I/O dan memori.
3. **Mendesain Skema Skala Enterprise Berkinerja Tinggi**: Mengimplementasikan strategi partisi lanjutan (*declarative partitioning*), *composite indexing*, *covering index*, dan mitigasi tabel *bloat*.
4. **Mengonfigurasi Arsitektur High Availability (HA) & Concurrency**: Memitigasi *deadlock*, mengatur *transaction isolation levels* secara tepat, serta merancang topologi replikasi (*synchronous/asynchronous streaming replication*) dengan *connection pooling* tingkat produksi.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda harus memahami:
* Fondasi ANSI SQL: DDL, DML, DQL (JOIN, Aggregations, Subqueries).
* Konsep dasar transaksi ACID (*Atomicity, Consistency, Isolation, Durability*).
* Pemahaman dasar sistem operasi: POSIX system calls (`read`, `write`, `fsync`), manajemen memori virtual, dan thread/process concurrency.

---

## 3. Concept & Internal Architecture

Untuk menguasai SQL pada level enterprise, sistem basis data tidak boleh diperlakukan sebagai *black box*. Arsitektur mesin RDBMS modern (menggunakan PostgreSQL dan InnoDB/MySQL sebagai referensi standar) terbagi menjadi dua subsistem utama: **Compute/Query Engine** dan **Storage Engine**.

```
+-----------------------------------------------------------------------+
|                      CLIENT APPLICATIONS                              |
+-----------------------------------+-----------------------------------+
                                    | (TCP / Connection Pooler)
+-----------------------------------v-----------------------------------+
|                         COMPUTE ENGINE                                |
|  +-----------------------------------------------------------------+  |
|  | Parser & Rewriter: Syntax Parsing -> Abstract Syntax Tree (AST)  |  |
|  +--------------------------------+--------------------------------+  |
|                                   |                                   |
|  +--------------------------------v--------------------------------+  |
|  | Catalog / Metastore: Schema, Table, Index, Statistics Metadata  |  |
|  +--------------------------------+--------------------------------+  |
|                                   |                                   |
|  +--------------------------------v--------------------------------+  |
|  | Query Optimizer (CBO): Cost Calculation, Plan Tree Generation   |  |
|  +--------------------------------+--------------------------------+  |
|                                   |                                   |
|  +--------------------------------v--------------------------------+  |
|  | Query Executor: Sequential Scan, Index Scan, Hash/Merge Join     |  |
|  +--------------------------------+--------------------------------+  |
+-----------------------------------|-----------------------------------+
                                    | Read / Write Blocks
+-----------------------------------v-----------------------------------+
|                         STORAGE ENGINE                                |
|  +-----------------------------------------------------------------+  |
|  | Buffer Pool Manager (Shared Buffers)                            |  |
|  |   - Clock-Sweep / LRU Cache Algorithm                           |  |
|  |   - Dirty Page Tracking & Checkpointing                         |  |
|  +-----------------+-----------------------------+-----------------+  |
|                    |                             |                    |
|  +-----------------v---------------+   +---------v-----------------+  |
|  | Lock Manager & MVCC Engine      |   | Write-Ahead Log (WAL/Redo)|  |
|  |   - Tuple Visibility Check      |   |   - Sequential Log I/O    |  |
|  |   - Row / Table Latch & Lock    |   |   - Group Commit Engine   |  |
|  +-----------------+---------------+   +---------+-----------------+  |
+--------------------|-----------------------------|--------------------+
                     | fsync                       | fsync
+--------------------v-----------------------------v--------------------+
|                          STORAGE / DISK                               |
|       [Data Files (.db / heaps)]            [WAL / Redo Logs]         |
+-----------------------------------------------------------------------+
```

### 3.1. Struktur Penyimpanan Fisik: Slotted-Page Architecture
Data tidak disimpan sebagai baris teks mentah di disk. Database membagi berkas tabel menjadi unit-unit logis berukuran tetap yang disebut **Pages** (atau **Blocks**, default 8KB di PostgreSQL, 16KB di MySQL InnoDB).

Format internal sebuah 8KB Page:
1. **Page Header (24 bytes)**: Menyimpan metadata halaman, termasuk LSN (*Log Sequence Number*) terakhir yang mengubah halaman ini, pointer ke *free space*, serta *flags*.
2. **Line Pointer Array (ItemId Array)**: Larik pointer 4-byte yang menunjuk ke *offset byte* fisik dari tuple/baris di dalam halaman tersebut.
3. **Free Space**: Ruang kosong di tengah halaman yang tumbuh saling mendekat (pointer tumbuh ke bawah, tuple tumbuh ke atas).
4. **Tuple/Row Data**: Data baris aktual yang disusun dari bawah halaman (*bottom-up*). Berisi Tuple Header (`t_xmin`, `t_xmax`, `t_cid`, `t_infomask`) dan data kolom aktual.

```
+-------------------------------------------------------------------+
| Page Header (LSN, Checksum, lower/upper offsets) [24 bytes]       |
+-------------------------------------------------------------------+
| Line Pointer 1 -> Offset 8140                                     |
| Line Pointer 2 -> Offset 8080                                     |
| Line Pointer 3 -> Offset [Dead]                                   |
+-------------------------------------------------------------------+
|                     <--- FREE SPACE --->                          |
| (Tumbuh ke bawah saat pointer baru dibuat,                        |
|  mengecil saat tuple baru ditulis dari bawah ke atas)             |
+-------------------------------------------------------------------+
| Tuple 2 Data: [Header: xmin 1020, xmax 0 | Data: 'Bob', 25]       |
+-------------------------------------------------------------------+
| Tuple 1 Data: [Header: xmin 1019, xmax 1025 | Data: 'Alice', 30]  |
+-------------------------------------------------------------------+
```

### 3.2. ARIES, WAL (Write-Ahead Logging), dan Checkpointing
Prinsip dasar ketahanan data (*Durability*) tanpa mengorbankan performa: **Database tidak pernah menulis dirty page ke disk secara sinkron pada saat transaksi commit**. Penulisan acak (*random I/O*) ke tabel data terlalu lambat.
* **Protokol WAL**: Perubahan data harus dicatat secara berurutan (*sequential append-only I/O*) ke dalam berkas Write-Ahead Log di disk **sebelum** modifikasi halaman data di memori (*Buffer Pool*) diizinkan.
* **Commit**: Transaksi dianggap *committed* segera setelah entri WAL berhasil dieksekusi dengan system call `fsync()` ke storage disk. Halaman data di RAM tetap berstatus **Dirty Page**.
* **Checkpoint Process**: Background worker berkala membaca dirty pages dari Buffer Pool dan menyiramnya (*flush*) ke berkas tabel utama di disk. Tujuannya adalah mempercepat waktu *crash recovery* dengan membatasi seberapa jauh ke belakang mesin harus membaca WAL saat boot ulang.

### 3.3. MVCC (Multi-Version Concurrency Control) & Tuple Visibility
MVCC mengizinkan konkurensi tinggi dengan aturan emas: **"Readers do not block Writers, and Writers do not block Readers."**
* Setiap operasi `UPDATE` secara internal dieksekusi sebagai:
  1. `INSERT` baris versi baru dengan `t_xmin = Current_XID` (Transaction ID saat ini).
  2. `UPDATE` baris versi lama dengan mengisi `t_xmax = Current_XID`.
* Setiap operasi `DELETE` tidak langsung menghapus bit dari disk, melainkan hanya mengisi `t_xmax = Current_XID` pada tuple tersebut.
* **Snapshot Isolation Engine**: Saat sebuah query membaca tabel, ia menerima *Virtual Snapshot* yang berisi daftar XID yang sedang aktif (*in-progress*), sudah commit, atau belum dimulai. Baris hanya terlihat (*visible*) jika:
  * `t_xmin` sudah commit sebelum snapshot dibuat.
  * `t_xmax` kosong ATAU menunjuk ke transaksi yang belum commit atau dibatalkan (*aborted*).
* **Konsekuensi**: Operasi UPDATE dan DELETE meninggalkan *dead tuples*. Jika tidak dibersihkan oleh `VACUUM` (PostgreSQL) atau `Purge Threads` (InnoDB Undo Logs), tabel akan mengalami **Bloat**, yang memperlambat pemindaian sekuensial dan menghabiskan storage.

---

## 4. Why & What

### Mengapa Abstraksi Tingkat Tinggi (ORM) Gagal di Skala Enterprise?
Object-Relational Mapping (ORM) seperti Prisma, Hibernate, atau TypeORM menyembunyikan kompleksitas fisik database. Pada skala ribuan transaksi per detik (TPS), abstraksi ini menciptakan:
* **N+1 Query Problems**: Mengakibatkan latensi jaringan eksponensial.
* **Over-fetching**: Mengambil seluruh kolom (`SELECT *`) yang menghancurkan efisiensi memory bandwidth dan menggagalkan pemanfaatan *Index-Only Scan*.
* **Inefficient Lock Escalation**: Menahan transaksi terbuka terlalu lama saat thread aplikasi menunggu respon dari API eksternal, yang berujung pada *connection starvation* dan *deadlock*.

### Apa yang Harus Dibangun?
Arsitektur database enterprise membutuhkan:
* Pemahaman **Physical Execution Plan** untuk mengendalikan I/O.
* Skema terpartisi secara deklaratif untuk data berukuran gigabyte hingga terabyte.
* Pengaturan isolasi transaksi yang presisi untuk menjaga integritas neraca finansial tanpa menyebabkan degradasi throughput.

---

## 5. How: Workflow Detail Eksekusi Query

Berikut siklus hidup query DML/DQL dari saat dikirim oleh aplikasi hingga kembali sebagai result set:

```
[Client] ---> 1. SQL Text via TCP (Port 5432/3306)
                 |
[Compute]    ---> 2. Lexer & Parser (Syntactic Check -> Parse Tree)
                 |
             ---> 3. Analyzer / Semantic Check (Validasi Tabel/Kolom via System Catalog)
                 |
             ---> 4. Rewriter (Ekspansi Views & Rule System)
                 |
             ---> 5. Cost-Based Optimizer (CBO):
                 |    a. Evaluasi Restrukturisasi Aljabar Relasional
                 |    b. Akses Statistik Tabel (pg_statistic / histogram)
                 |    c. Kalkulasi Cost: CPU Cost + Disk I/O Cost
                 |    d. Hasilkan Execution Plan (Optimal Path)
                 |
[Storage]    ---> 6. Executor Engine:
                 |    a. Alokasi work_mem untuk Sort / Hash Table
                 |    b. Minta halaman data ke Buffer Pool Manager
                 |
[Buffer Pool]---> 7. Buffer Cache Check:
                      * Cache HIT: Baca langsung dari shared_buffers RAM
                      * Cache MISS: Kirim POSIX read() ke Kernel -> Disk I/O
                      * Latch page di shared memory (Read/Write mode)
                 |
[Lock/MVCC]  ---> 8. Evaluasi MVCC Visibility:
                      Filter baris berdasarkan snapshot transaksi aktif
                 |
[Network]    <--- 9. Streaming result set kembali ke Client buffer
```

---

## 6. Analogy & Diagram ASCII: Latency Numbers Every Database Engineer Must Know

Memahami arsitektur database adalah memahami hierarki latensi perangkat keras:

```
+------------------------------------------------------------------------+
| HIERARKI PENYIMPANAN DAN LATENSI DATABASE                             |
+------------------------------------------------------------------------+
| Lokasi                         Latensi Relatif       Analogi Manusia   |
+------------------------------------------------------------------------+
| CPU L1 Cache Reference         0.5 ns                1 detik           |
| CPU L2/L3 Cache                5 - 20 ns             10 - 40 detik     |
| RAM Main Memory (Buffer Pool)  100 ns                3.3 menit         |
| NVMe SSD I/O (Random Page Read)100,000 ns (100 us)   2.3 hari          |
| Rotational HDD I/O             10,000,000 ns (10 ms) 7.6 bulan         |
+------------------------------------------------------------------------+
```

Jika database Anda terpaksa melakukan **Disk I/O** alih-alih menemukan *block* di **Buffer Pool (RAM)**, sistem Anda berpindah dari skala perhitungan menit ke skala perhitungan hari. Inilah alasan mendasar mengapa desain indeks dan pemanfaatan memori menjadi penentu performa query.

---

## 7. Simple Example & Practical Example

### 7.1. Skenario: Implementasi Skema Finansial Mutasi Saldo (Production-Grade)

Contoh ini menunjukkan:
1. Pembuatan partisi deklaratif berbasis rentang waktu (*Range Partitioning*).
2. Mekanisme integritas data ketat via Constraints.
3. Optimasi indeks fungsional dan parsial.
4. Transaksi transfer saldo tahan-konkurensi dengan locking baris deterministik untuk mencegah *deadlock*.

#### Skema DDL & Partisi

```sql
-- Mengaktifkan ekstensi modul pemantauan
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Tabel Utama: Master Akun Ledger
CREATE TABLE accounts (
    account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_number VARCHAR(32) NOT NULL UNIQUE,
    current_balance NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    currency VARCHAR(3) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_positive_balance CHECK (current_balance >= 0.0000),
    CONSTRAINT chk_currency_iso CHECK (length(currency) = 3)
);

-- Tabel Transaksi: Terpartisi secara Deklaratif per Bulan (Range Partitioning)
CREATE TABLE account_transactions (
    transaction_id UUID NOT NULL DEFAULT uuid_generate_v4(),
    source_account_id UUID NOT NULL,
    destination_account_id UUID NOT NULL,
    amount NUMERIC(18, 4) NOT NULL,
    fee NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (transaction_id, created_at),
    CONSTRAINT chk_amount_positive CHECK (amount > 0)
) PARTITION BY RANGE (created_at);

-- Partisi Bulanan untuk Operasional Q1
CREATE TABLE account_transactions_2025_01 PARTITION OF account_transactions
    FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2025-02-01 00:00:00+00');

CREATE TABLE account_transactions_2025_02 PARTITION OF account_transactions
    FOR VALUES FROM ('2025-02-01 00:00:00+00') TO ('2025-03-01 00:00:00+00');

-- 1. Index Komposit untuk Analisis Mutasi per Rekening
CREATE INDEX idx_transactions_src_dest_created 
ON account_transactions (source_account_id, created_at DESC);

-- 2. Partial Index: Hanya mengindeks transaksi yang berstatus PENDING
-- Menghemat ruang disk dan RAM buffer pool secara masif
CREATE INDEX idx_transactions_pending_verification 
ON account_transactions (created_at) 
WHERE status = 'PENDING';
```

#### Stored Procedure / Logic: Transfer Dana Anti-Deadlock

Deadlock sering terjadi bila Thread A mentransfer dari Akun 1 ke Akun 2, sementara Thread B mentransfer dari Akun 2 ke Akun 1 pada saat yang bersamaan. **Solusi arsitektur**: Urutkan penguncian baris berdasarkan Resource ID (*Deterministic Locking Order*).

```sql
CREATE OR REPLACE PROCEDURE execute_fund_transfer(
    p_sender_id UUID,
    p_receiver_id UUID,
    p_amount NUMERIC(18, 4),
    p_fee NUMERIC(18, 4),
    OUT p_transaction_id UUID
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_first_lock_id UUID;
    v_second_lock_id UUID;
    v_sender_balance NUMERIC(18, 4);
BEGIN
    -- Validasi Input
    IF p_sender_id = p_receiver_id THEN
        RAISE EXCEPTION 'Sender and Receiver cannot be identical.';
    END IF;

    IF p_amount <= 0 THEN
        RAISE EXCEPTION 'Transfer amount must be greater than zero.';
    END IF;

    -- Urutkan UUID secara leksikografis untuk menghindari Deadlock ABBA
    IF p_sender_id < p_receiver_id THEN
        v_first_lock_id := p_sender_id;
        v_second_lock_id := p_receiver_id;
    ELSE
        v_first_lock_id := p_receiver_id;
        v_second_lock_id := p_sender_id;
    END IF;

    -- Lock baris pertama secara deterministik
    PERFORM 1 FROM accounts WHERE account_id = v_first_lock_id FOR NO KEY UPDATE;
    -- Lock baris kedua
    PERFORM 1 FROM accounts WHERE account_id = v_second_lock_id FOR NO KEY UPDATE;

    -- Periksa Saldo Pengirim
    SELECT current_balance INTO v_sender_balance 
    FROM accounts WHERE account_id = p_sender_id;

    IF v_sender_balance < (p_amount + p_fee) THEN
        RAISE EXCEPTION 'Insufficient funds: available %, required %', 
            v_sender_balance, (p_amount + p_fee);
    END IF;

    -- Potong saldo pengirim
    UPDATE accounts 
    SET current_balance = current_balance - (p_amount + p_fee),
        version = version + 1
    WHERE account_id = p_sender_id;

    -- Tambah saldo penerima
    UPDATE accounts 
    SET current_balance = current_balance + p_amount,
        version = version + 1
    WHERE account_id = p_receiver_id;

    -- Buat entri transaksi di tabel partisi
    p_transaction_id := uuid_generate_v4();
    INSERT INTO account_transactions (
        transaction_id, source_account_id, destination_account_id, amount, fee, status, created_at
    ) VALUES (
        p_transaction_id, p_sender_id, p_receiver_id, p_amount, p_fee, 'SETTLED', CURRENT_TIMESTAMP
    );

    -- Catatan: Commit dikendalikan oleh caller atau blok transaksi DB
END;
$$;
```

---

## 8. Real World Case Study: E-Commerce Flash Sale System (High Contention & Table Bloat)

### Kasus
Sebuah platform marketplace global menyelenggarakan Flash Sale konsol game. Stok fisik barang: 500 unit. Jumlah pengguna bersamaan (*concurrent users*) yang memicu *checkout*: 85.000 request/detik.

### Masalah Produksi yang Terjadi
1. **Row Contention & Serialization Failures**: Puluhan ribu worker thread mencoba mengeksekusi `UPDATE inventory SET stock = stock - 1 WHERE item_id = 999;`. Ini memicu antrean kunci (*exclusive lock wait-queue*) yang masif di storage engine.
2. **Connection Exhaustion**: Pool koneksi PostgreSQL (default max 100) habis dalam 400 milidetik. Aplikasi melempar exception `FATAL: remaining connection slots are reserved for non-replicated superuser connections`.
3. **Severe Table Bloat**: 85.000 percobaan update menciptakan ratusan ribu *dead tuples* per detik, melumpuhkan shared buffer cache dan membuat query pembacaan inventaris terhenti selama puluhan detik akibat disk read storm.

### Solusi Arsitektur Produksi

#### 1. Arsitektur Infrastruktur & Pooling Layer
Menempatkan **PgBouncer** dalam mode *Transaction Pooling* di depan instans basis data, membatasi koneksi aktif ke PostgreSQL maksimal 50 thread per Core CPU, mengeliminasi context switching OS.

#### 2. Dekonstruksi Row Lock: "Inventory Sharding / Reservation Slugs"
Daripada merepresentasikan stok dalam 1 baris tunggal, buat skema sub-alokasi (*Inventory Buckets*):

```sql
CREATE TABLE item_inventory_buckets (
    bucket_id INT NOT NULL,
    item_id BIGINT NOT NULL,
    available_stock INT NOT NULL,
    PRIMARY KEY (item_id, bucket_id),
    CONSTRAINT chk_stock_non_negative CHECK (available_stock >= 0)
);

-- Memecah stok 500 unit ke dalam 20 bucket terpisah (masing-masing 25 unit)
INSERT INTO item_inventory_buckets (bucket_id, item_id, available_stock)
SELECT s, 999, 25 FROM generate_series(1, 20) AS s;
```

#### 3. Checkout Menggunakan `SKIP LOCKED` Pattern
Worker tidak lagi berebut satu baris, melainkan melompati baris yang sedang dikunci transaksi lain:

```sql
CREATE OR REPLACE FUNCTION claim_stock(p_item_id BIGINT, p_qty INT) 
RETURNS BOOLEAN AS $$
DECLARE
    v_bucket_id INT;
BEGIN
    -- Temukan bucket yang memiliki stok cukup dan TIDAK SEDANG DIKUNCI oleh worker lain
    SELECT bucket_id INTO v_bucket_id
    FROM item_inventory_buckets
    WHERE item_id = p_item_id AND available_stock >= p_qty
    LIMIT 1
    FOR UPDATE SKIP LOCKED;

    IF v_bucket_id IS NULL THEN
        -- Semua bucket yang cukup sedang sibuk atau stok habis
        RETURN FALSE;
    END IF;

    -- Potong stok dari bucket yang berhasil dikunci eksklusif
    UPDATE item_inventory_buckets
    SET available_stock = available_stock - p_qty
    WHERE item_id = p_item_id AND bucket_id = v_bucket_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;
```

#### 4. Hasil Metrik Produksi
* **TPS throughput**: Naik dari 120 TPS (dengan 99.8% rollback akibat deadlock/lock timeout) menjadi **8.400 TPS sukses**.
* **P99 Latency**: Turun dari 14.200 ms menjadi **8.2 ms**.
* **Database CPU Utilization**: Stabil pada 65% tanpa thread thrashing.

---

## 9. Trade-Offs: Keseimbangan Rekayasa Sistem

Tidak ada arsitektur database yang sempurna secara absolut; seluruh keputusan arsitektural adalah kompromi (*trade-offs*):

```
+---------------------------+--------------------------------+--------------------------------+
| PARAMETER DESAIN          | KEUNTUNGAN                     | KONSEKUENSI / HARGA            |
+---------------------------+--------------------------------+--------------------------------+
| Normalisasi (3NF / BCNF)  | * Menghilangkan anomali update | * Butuh banyak relational JOIN |
|                           | * Integritas relasional ketat  | * Latensi read tinggi di skala |
|                           | * Penghematan disk storage     |   jutaan entitas               |
+---------------------------+--------------------------------+--------------------------------+
| Denormalisasi             | * Bacaan sangat cepat          | * Duplikasi data masif         |
| (Pre-aggregated / NoSQL)  | * Mengurangi JOIN I/O          | * Rawan inkonsistensi saat     |
|                           | * Optimasi akses API spesifik  |   kegagalan write parsial      |
+---------------------------+--------------------------------+--------------------------------+
| Penambahan Indeks         | * Mempercepat filter & join    | * Memperlambat INSERT/UPDATE   |
| (B-Tree, GIN, BRIN)       | * Mengurangi scan ke memori    | * Memperbesar ukuran disk      |
|                           | * Mengurangi penggunaan CPU    | * Write Amplification di WAL   |
+---------------------------+--------------------------------+--------------------------------+
| Isolasi Transaksi         | * Garansi kebenaran matematis  | * Concurrency anjlok           |
| (SERIALIZABLE)            | * Mencegah phantom & write skew| * Serialization failure tinggi |
|                           |                                | * Beban retry di app layer     |
+---------------------------+--------------------------------+--------------------------------+
| Isolasi Transaksi         | * Concurrency sangat tinggi    | * Mengharuskan developer       |
| (READ COMMITTED)          | * Tidak ada serialization lock |   menangani phantom reads      |
|                           | * Throughput I/O maksimal      |   dan race conditions manual   |
+---------------------------+--------------------------------+--------------------------------+
```

---

## 10. Common Mistakes & Troubleshooting

### Anti-Pattern 1: Menyandera Transaksi Database dengan Network I/O
```
[App Thread] ---> BEGIN TRANSACTION;
             ---> UPDATE users SET balance = balance - 100 WHERE id = 1; (Row Lock Dipegang!)
             ---> HTTP POST ke Payment Gateway (Menunggu 3 - 5 detik...)
             ---> INSERT INTO audit_logs ...;
             ---> COMMIT;
```
* **Dampak**: Selama 5 detik menunggu HTTP Response, baris `users` terkunci. Puluhan thread lain yang butuh baris tersebut akan antre. Buffer pool dan thread pool terkuras habis.
* **Solusi**: **Pisahkan interaksi eksternal keluar dari transaksi database.** Gunakan pola *Outbox Pattern* atau commit transaksi terlebih dahulu dengan status `PENDING`, jalankan network call, lalu mutasikan kembali di transaksi terpisah.

### Anti-Pattern 2: Implicit Type Coercion Membunuh Pemanfaatan Indeks
```sql
-- DDL: Kolom phone_number terindeks sebagai VARCHAR(32)
CREATE INDEX idx_users_phone ON users(phone_number);

-- BAD QUERY: Mengirim parameter angka/integer langsung
SELECT * FROM users WHERE phone_number = 08123456789;
```
* **Dampak**: Database akan menjalankan type casting implisit: `WHERE CAST(phone_number AS BIGINT) = 8123456789`. Ini memaksa **Sequential Full Table Scan** karena B-Tree index dibangun di atas nilai string mentah, bukan hasil casting fungsi.
* **Solusi**: Pastikan parameter query memiliki tipe data yang identik dengan definisi skema:
  ```sql
  -- GOOD QUERY: Parameter string yang konsisten
  SELECT * FROM users WHERE phone_number = '08123456789';
  ```

### Tooling Diagnostik Wajib di Linux/PostgreSQL

#### 1. Mengidentifikasi Transaksi Lambat dan Terkunci (*Lock Contention*)
```sql
SELECT 
    blocked_locks.pid     AS blocked_pid,
    blocked_activity.usename  AS blocked_user,
    blocking_locks.pid    AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query    AS blocked_statement,
    blocking_activity.query   AS blocking_statement
FROM  pg_catalog.pg_locks         blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks         blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND