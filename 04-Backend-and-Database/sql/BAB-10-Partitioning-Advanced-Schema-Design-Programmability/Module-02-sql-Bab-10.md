# Kurikulum Rekayasa Basis Data Enterprise: SQL
## BAB 10: Partitioning, Advanced Schema Design & Programmability
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Principal/Staff Database Architect & Senior Backend Engineer ditargetkan mampu:
- **Menganalisis Internal Partitioning Engine:** Menguasai mekanisme *partition pruning* (compile-time vs. run-time) dan implikasi struktur b-tree, storage allocation, serta lock escalation pada level *catalog metadata*.
- **Merancang Arsitektur Skema Lanjutan:** Mengimplementasikan pola pemodelan heterogen (*JSONB/Schemaless hybrid*, *Temporal Tables* berbasis ISO/IEC 9075:2011, serta *Single-Table Inheritance* vs *Concrete Table Inheritance*) dengan isolasi konkurensi tinggi.
- **Mengoptimalkan Programmability di Level Engine:** Membangun *Stored Procedures* dan *User-Defined Functions* (UDF) teroptimasi dengan mengontrol atribut volatilitas (`IMMUTABLE`, `STABLE`, `VOLATILE`), meminimalkan *context switching* engine, serta mencegah overhead *procedural memory bloat*.
- **Membangun Sistem Data Lifecycle Management (DLM) Otomatis:** Mengotomatisasi siklus partisi (pre-creation, detach, freeze, data tiering ke cold storage/S3 via FDW) tanpa down-time dan tanpa mengorbankan integritas referensial.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib memiliki pemahaman mendalam tentang:
- **Internal Storage Engine:** Pemahaman mendalam terkait Page/Block layouts (8KB page pada PostgreSQL atau 16KB InnoDB page), Write-Ahead Logging (WAL/Redo Log), MVCC snapshot isolation, dan Tuple visibility.
- **Query Optimization:** Kemampuan membaca output `EXPLAIN (ANALYZE, BUFFERS, SETTINGS, WAL)` secara presisi.
- **Concurrency Control:** Memahami jenis-jenis lock relasional (misal: `RowExclusiveLock`, `AccessExclusiveLock`, `Metadata Locks / MDL`).
- **Sistem Operasi & Storage:** I/O subsystem mechanics, kernel page cache, dirty page flush, dan asynchronous I/O (AIO).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Internal Table Partitioning Engine & Pruning Mechanics

Partitioning secara logis membagi tabel tunggal menjadi beberapa tabel fisik (sub-tabel) di storage layer. Pada PostgreSQL (declarative partitioning) dan MySQL (InnoDB partitioning), tabel partisi induk hanyalah sebuah *routing proxy* virtual tanpa data fisik langsung pada `relfilenode` induknya.

```
                    Query: WHERE created_at >= '2025-02-01'
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Query Optimizer   │
                         └──────────┬──────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
        [Static Pruning]                    [Dynamic Pruning]
     (Parse / Plan Time)                  (Executor Init / Run)
  Const expression evaluated              Subquery / Parameter eval
                  │                                   │
                  ▼                                   ▼
      Eliminates non-matching              Eliminates partitions
      partitions from plan tree            per executor step
                  │                                   │
                  └─────────────────┬─────────────────┘
                                    ▼
                 ┌──────────────────────────────────────┐
                 │          Executor Engine             │
                 └──────────────────┬───────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │ (Pruned/Skipped)        │ (Scanned)               │ (Pruned/Skipped)
          ▼                         ▼                         ▼
   ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
   │ Part_2025_01 │          │ Part_2025_02 │          │ Part_2025_03 │
   │ (0 IO Reads) │          │ (Index/Heap) │          │ (0 IO Reads) │
   └──────────────┘          └──────────────┘          └──────────────┘
```

1. **Static vs. Dynamic Partition Pruning:**
   - **Static Pruning (Compile/Plan-time):** Optimizer mendeteksi predicate dengan nilai konstan literal (misal: `WHERE created_at >= '2025-02-01'`). Optimizer memotong relasi tabel anak sebelum path generation, sehingga metadata node partisi lain langsung diabaikan.
   - **Dynamic Pruning (Run-time / Execution-time):** Terjadi saat klausa bergantung pada parameter eksternal (Prepared Statements, PL/pgSQL variable, atau subquery skalar seperti `WHERE created_at >= (SELECT now() - interval '1 day')`). Pada fase `ExecutorEngine`, engine memanggil evaluation gatekeeper untuk melompati scanning scan node pada partisi yang tidak valid.

2. **Dampak Metrik Locking Metadata:**
   Pada declarative partitioning, mengeksekusi DDL seperti `ALTER TABLE ... ATTACH/DETACH PARTITION` memerlukan `AccessExclusiveLock` pada tabel induk. Jika query panjang sedang berjalan (meskipun hanya memegang `AccessShareLock`), modifikasi struktur skema partisi akan mengalami lock-queue starvation, yang dapat memicu *connection pool exhaustion*.

#### B. Advanced Schema Design: Pola Hybrid Dokumen & Temporal

1. **Hybrid Relational-JSONB Storage Mechanics:**
   PostgreSQL menyimpan `JSONB` dalam format binari terdekomposisi (keys sorted, alignment padding, length-prefixed values). Berbeda dengan tipe teks murni, JSONB mendukung pengindeksan parsial dan ekspresi via GIN (Generalized Inverted Index) yang memanfaatkan data structure *B-Tree of postings lists/trees*.

2. **Temporal Tables (System-Versioned Data):**
   Sesuai standar SQL:2011, temporal table melacak rentang validitas tuple menggunakan interval waktu tertutup-terbuka: `[t_start, t_end)`.
   Tuple yang di-*update* tidak langsung dimutasi secara fisik murni via MVCC; sistem menutup interval record lama (`SET t_end = CURRENT_TIMESTAMP`) dan menyisipkan record baru (`t_start = CURRENT_TIMESTAMP, t_end = 'infinity'`), mengizinkan query point-in-time auditing (Time-Travel SQL) dengan performa deterministik.

#### C. Programmability Engine: Function Memory Context & Volatility Category

PostgreSQL membagi siklus hidup eksekusi fungsi ke dalam tiga klasifikasi volatilitas:
- **`IMMUTABLE`:** Fungsi murni (*pure function*), tidak membaca/mengubah database, hasil identik jika argumen sama. Optimizer dapat melakukan *constant folding* saat compile time.
- **`STABLE`:** Menjamin hasil sama untuk argumen yang sama *dalam satu pemindaian/transaksi tunggal*, membaca data tabel tetapi tidak memodifikasinya (misal: fungsi yang menggunakan `CURRENT_TIMESTAMP`).
- **`VOLATILE`:** Dapat menghasilkan nilai berbeda di setiap eksekusi baris (misal: `random()`, pemanggilan sequence) atau melakukan DML/DCL. Optimizer **dilarang keras** meng-inline atau mengoptimalkan fungsi ini melintasi perulangan baris.

---

### 4. Why & What

| Dimensi | Pendekatan Monolitik / Skema Standar | Arsitektur Partitioning & Advanced Schema |
| :--- | :--- | :--- |
| **Data Locality & Cache** | Satu tabel masif (100M+ baris) membuat Working Set Size melampaui RAM (`shared_buffers`). Buffer pool terpolusi. | Partisi membatasi active index tree & data blocks pada RAM, menghasilkan Cache Hit Ratio > 99%. |
| **Lifecycle & Purging** | `DELETE FROM table WHERE created_at < NOW() - INTERVAL '6 months'` memicu *vacuum overhead*, *WAL write storm*, dan *table bloat*. | `ALTER TABLE table DETACH PARTITION` dilanjutkan dengan `DROP TABLE` bekerja secara instan (O(1) operation metadata-only), membebaskan block storage seketika tanpa WAL bloat. |
| **Skema Heterogen** | Pemaksaan normalisasi 3NF untuk data dinamis memicu JOIN masif (>10 tabel) atau anti-pattern EAV (*Entity-Attribute-Value*) yang menghancurkan query optimizer cost estimation. | Desain Hybrid Relational-JSONB terindeks secara fungsional, memisahkan core transactional invariant ke kolom flat dan extensibility metadata ke JSONB. |
| **Auditability** | Implementasi audit manual menggunakan trigger DML berbasis insert log table terpisah sering mengalami serialization failure dan lock contention tinggi. | Native Temporal System Versioning menjamin record *point-in-time* tanpa risiko drift antara transaction log dan audit log. |

---

### 5. How (Workflow Detail)

Alur perancangan dan operasional partisi enterprise meliputi fase berikut:

1. **Penetapan Partition Key:** Tentukan kunci partisi berdasarkan query access pattern mayoritas (biasanya temporal/range `created_at`, atau tenant isolator via hash `tenant_id`). Kunci ini wajib menjadi bagian dari Primary Key / Unique Constraints.
2. **Sub-Partitioning Strategy:** Terapkan teknik *Composite Partitioning* (contoh: Range Partition per Bulan, di dalamnya dipecah Hash Partition 8-bucket) jika satu partisi bulanan masih melebihi batas ideal (umumnya > 50-100 GB per partisi).
3. **Penyusunan Guardrail Pruning:** Pastikan parameter optimizer berikut aktif pada konfigurasi database:
   - PostgreSQL: `enable_partition_pruning = on`
   - MySQL: Periksa `explain format=tree` atau baris `partitions` pada `EXPLAIN`.
4. **Maintenance Task Integration:** Implementasikan worker terjadwal untuk *pre-allocating* partisi masa depan (misal $H-7$ hari sebelum pergantian bulan) dan migrasi cold partitions ke storage class tiering via FDW atau archival engine.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Lemari Arsip Ruang Operasional Medis

Mencari riwayat pasien berumur 10 tahun di dalam satu tumpukan dokumen raksasa setinggi 100 meter (*Single Monolithic Table*) mengharuskan perawat membolak-balik lembar demi lembar indeks global yang tebal. 

Dengan **Partitioning**, kita menyusun lemari arsip dengan label laci per tahun (*Range Partitioning*). Saat dokter meminta berkas "Tahun 2024", perawat **langsung berjalan ke laci tahun 2024 dan sama sekali mengabaikan laci tahun lainnya** (*Partition Pruning*). Menghapus data kedaluwarsa 10 tahun lalu cukup dengan mencopot laci lama dan membawanya ke gudang (*Drop Partition Metadata*), tanpa perlu menyortir dan mencabut selembar demi selembar (*No DML Delete Bloat*).

#### Architectural Flow: Automated Partition Lifecycle & Data Tiering

```
                     Incoming Transaction (Writes)
                                  │
                                  ▼
                ┌───────────────────────────────────┐
                │   orders (Partition Root Proxy)   │
                └─────────────────┬─────────────────┘
                                  │ Hash/Range Routing
       ┌──────────────────────────┼──────────────────────────┐
       ▼                          ▼                          ▼
┌──────────────┐           ┌──────────────┐           ┌──────────────┐
│ orders_202501│           │ orders_202502│           │ orders_202503│
│ (Read/Write) │           │ (Hot Storage)│           │ (Pre-Created)│
└──────┬───────┘           └──────────────┘           └──────────────┘
       │ Age > 90 Days
       ▼
 1. DETACH CONCURRENTLY
 2. CREATE FOREIGN TABLE (postgres_fdw)
 3. ATTACH TO orders_archive
       │
       ▼
┌───────────────────────────────────────────────┐
│              S3 / Cold Cluster                │
│       orders_archive_2024_cold (Parquet/FDW)  │
└───────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Declarative Hash Partitioning untuk Mitigasi Hot-Spot Disk I/O

```sql
-- 1. Setup Master Virtual Partition Table
CREATE TABLE telemetry_streams (
    device_id UUID NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    payload NUMERIC(10, 4) NOT NULL,
    PRIMARY KEY (device_id, recorded_at)
) PARTITION BY HASH (device_id);

-- 2. Setup 4 Hash Bucket Partitions
CREATE TABLE telemetry_streams_h1 PARTITION OF telemetry_streams
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE telemetry_streams_h2 PARTITION OF telemetry_streams
    FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE telemetry_streams_h3 PARTITION OF telemetry_streams
    FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE telemetry_streams_h4 PARTITION OF telemetry_streams
    FOR VALUES WITH (MODULUS 4, REMAINDER 3);

-- 3. Verify Pruning
EXPLAIN ANALYZE
SELECT * FROM telemetry_streams 
WHERE device_id = 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11';
-- Hasil: Hanya memindai 1 partition target (misal: telemetry_streams_h3)
```

#### B. Practical Enterprise Example: Hybrid Temporal Partitioning + JSONB Indexing & UDF

Skenario: Sistem Core Banking Transaction Log dengan volume 500 juta row/kuartal.

```sql
-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Schema Master (Range Partitioning bulanan)
CREATE TABLE core_ledger_entries (
    entry_id UUID NOT NULL DEFAULT uuid_generate_v4(),
    account_id BIGINT NOT NULL,
    amount NUMERIC(18, 4) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    sys_period TSTZRANGE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT pk_core_ledger PRIMARY KEY (entry_id, created_at)
) PARTITION BY RANGE (created_at);

-- Partisi Aktif Bulan Februari 2025
CREATE TABLE core_ledger_entries_2025_02 PARTITION OF core_ledger_entries
    FOR VALUES FROM ('2025-02-01 00:00:00+00') TO ('2025-03-01 00:00:00+00');

-- Functional Indexing GIN untuk Metadata JSONB pada partisi
CREATE INDEX idx_ledger_2025_02_metadata_gin 
    ON core_ledger_entries_2025_02 USING GIN (metadata jsonb_path_ops);

-- B-Tree Index untuk range temporal query
CREATE INDEX idx_ledger_2025_02_account_period 
    ON core_ledger_entries_2025_02 (account_id, sys_period);

-- Enterprise Optimized IMMUTABLE Function untuk audit signature
CREATE OR REPLACE FUNCTION fn_generate_entry_signature(
    p_account_id BIGINT,
    p_amount NUMERIC,
    p_timestamp TIMESTAMPTZ
) RETURNS TEXT AS $$
BEGIN
    RETURN encode(
        sha256(
            (p_account_id::text || ':' || p_amount::text || ':' || p_timestamp::text)::bytea
        ), 
        'hex'
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE;

-- Enterprise Stored Procedure untuk Batch Settlement dengan autonomous snapshot isolation
CREATE OR REPLACE PROCEDURE sp_process_settlement_batch(
    p_account_id BIGINT,
    p_credit_delta NUMERIC,
    p_metadata JSONB
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_now TIMESTAMPTZ := clock_timestamp();
BEGIN
    -- Validasi payload JSONB
    IF NOT (p_metadata ? 'channel') THEN
        RAISE EXCEPTION 'Metadata invalid: key "channel" wajib disertakan.'
            USING ERRCODE = 'data_exception';
    END IF;

    -- Insert tuple ledger
    INSERT INTO core_ledger_entries (
        account_id,
        amount,
        currency,
        metadata,
        sys_period,
        created_at
    ) VALUES (
        p_account_id,
        p_credit_delta,
        'IDR',
        p_metadata || jsonb_build_object('signature', fn_generate_entry_signature(p_account_id, p_credit_delta, v_now)),
        tstzrange(v_now, 'infinity', '[)'),
        v_now
    );

    COMMIT;
END;
$$;
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Platform:** E-Commerce Payment Gateway Unicorn.
- **Beban Kerja:** 12.000 Write QPS, memproses 1,5 Miliar row data settlement log per tahun.
- **Insiden:** Terjadi connection pool freeze (300 client pooled connection hang) setiap jam 00:00 UTC saat cron job mengeksekusi `CREATE TABLE ... PARTITION OF` dan membersihkan data 90 hari ke belakang via `DELETE`.

#### Akar Masalah (Root Cause Analysis)
1. Perintah `DELETE FROM ...` memicu lonjakan I/O write IOPS hingga 100% saturation (Disk Queue Depth > 64) akibat proses WAL logging dan cascading index b-tree reorganization.
2. DDL `CREATE TABLE ... PARTITION OF` dijalankan tanpa isolasi lock timeout, mengantre di belakang query reporting berdurasi panjang (`AccessShareLock`). Ini menyebabkan DDL menahan antrean `AccessExclusiveLock`, memblokir seluruh transaksi DML yang masuk secara berantai (*lock queue pileup*).

#### Solusi Arsitektural & Implementasi
1. Mengubah mekanisme purge DML menjadi `DETACH CONCURRENTLY` (PostgreSQL 12+) lalu menghapus sub-tabel secara terisolasi.
2. Mengimplementasikan guardrail `lock_timeout` pada DDL migrasi dan partition manager.

```sql
-- Automation worker script: Dynamic Detach without system-wide lock locking
DO $$
DECLARE
    v_old_partition TEXT := 'settlement_logs_2024_10';
BEGIN
    -- Set lock timeout agresif untuk mencegah starvation pada antrean lock
    SET LOCAL lock_timeout = '2s';

    -- Lepaskan partisi secara non-blocking terhadap pembacaan tabel induk
    EXECUTE format('ALTER TABLE settlement_logs DETACH PARTITION %I CONCURRENTLY;', v_old_partition);
    
    -- Drop tabel fisik partisi secara terpisah di luar hierarki partisi
    EXECUTE format('DROP TABLE %I;', v_old_partition);
EXCEPTION
    WHEN lock_not_available THEN
        RAISE WARNING 'Gagal mendapatkan lock eksklusif untuk detach partisi, coba lagi pada interval berikutnya.';
END;
$$;
```

---

### 9. Trade-offs

```
                       ┌────────────────────────────────┐
                       │ Advanced Partitioning Strategy │
                       └───────────────┬────────────────┘
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
┌───────────────────────┐                             ┌───────────────────────┐
│       ADVANTAGES      │                             │     DISADVANTAGES     │
├───────────────────────┤                             ├───────────────────────┤
│ • Bound Buffer Pool   │                             │ • High Memory (Planner│
│   (Predictable Cache) │                             │   overhead > 1000 sub)│
│ • O(1) Instant Drop   │                             │ • FK Cross-Partition  │
│   (Zero Bloat Purge)  │                             │   Limitations         │
│ • Linear Scalability  │                             │ • Connection Starve   │
│   (Hot/Cold Split)    │                             │   (DDL Lock Pitfalls) │
└───────────────────────┘                             └───────────────────────┘
```

- **Performa & Latensi:**
  - *Gain:* Query yang memicu pruning hanya menyentuh subset partition leaf pages, memotong I/O Latency dari $O(\log N_{\text{total}})$ menjadi $O(\log N_{\text{partition}})$.
  - *Risk:* Jika query tidak menyertakan Partition Key, query planner harus memindai **seluruh** partisi secara serial/paralel (*Scatter-Gather Scan*). Latensi melonjak hingga 400% lebih lambat dibanding query pada tabel reguler tak berpartisi karena overhead overhead *open relfilenode* dan memory tracking.
- **Beban Memory Optimizer:**
  Menciptakan partisi terlalu granular (misal: 10.000 partisi harian) menyebabkan query planner kehabisan memory (`max_locks_per_transaction` limit terlampaui) dan waktu parse query melonjak drastis.
- **Biaya & Skalabilitas:**
  - Implementasi *Cold Partitioning* via FDW (Foreign Data Wrapper) ke AWS S3/Object Storage memangkas biaya penyimpanan NVMe/EBS hingga 80%, namun menambahkan *network boundary latency* pada pembacaan historical analytics.

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Fatal 1: Mengabaikan Partition Key pada Unique Key / Foreign Key Constraints
- **Gejala:** Database engine melempar error: `ERROR: unique constraint on partitioned table must include all partitioning columns`.
- **Root Cause:** Mesin basis data relasional mendistribusikan index B-Tree secara lokal per partisi (*Local Index*). Basis data tidak mampu menegakkan keunikan secara global melintasi beberapa partisi tanpa memindai seluruh tree secara lintas partisi, yang mana akan merusak performa.
- **Solusi:** Selalu buat Composite Natural Primary Key yang mencakup partition key: `PRIMARY KEY (id, partition_key)`.

#### Kesalahan Fatal 2: Menghalangi Run-time Pruning Akibat Implicit Type Casting
- **Gejala:** `EXPLAIN` menunjukkan `Seq Scan` pada seluruh partisi padahal parameter pencarian partisi disertakan.
- **Akar Masalah:**
  ```sql
  -- Tipe kolom created_at: TIMESTAMPTZ
  -- Parameter input aplikasi: VARCHAR / DATE tanpa time zone
  EXPLAIN SELECT * FROM telemetry_streams WHERE created_at = '2025-02-10';
  ```
  Tipe data string memicu casting implisit internal `created_at::text = '...'` atau evaluasi ekspresi dinamis yang tidak dapat diselesaikan pada fase compile/plan, melumpuhkan static pruning.
- **Solusi:** Selalu bind parameter query dengan explicit casting:
  ```sql
  SELECT * FROM telemetry_streams WHERE created_at = '2025-02-10 00:00:00+00'::timestamptz;
  ```

#### Panduan Troubleshooting Eksekusi

```bash
# Debug: Identifikasi apakah query mengeksekusi Partition Pruning atau Full Scatter Scan
# 1. Jalankan explain analyze dengan buffers
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT * FROM core_ledger_entries 
WHERE created_at >= '2025-02-15 00:00:00+00' AND created_at < '2025-02-16 00:00:00+00';

# Indikator Sukses Pruning:
# -> Output hanya menunjukkan Append/Seq Scan/Index Scan pada 1 node tabel anak: core_ledger_entries_2025_02
# Jika muncul "Partitions removed: 0" atau seluruh list partisi dieksekusi, evaluasi kembali tipe data kolom dan klausa WHERE!
```

---

### 11. Best Practices (Production Checklist)

| Area | Langkah Kerja Rekayasa | Status |
| :--- | :--- | :--- |
| **Sizing** | Batasi ukuran fisik tiap partisi maksimal 20 GB – 50 GB atau sekitar 50-100 juta baris per sub-tabel untuk menjaga B-Tree traversal tetap berada di dalam L3 Cache/RAM. | [ ] |
| **Lifecycle** | Buat partisi baru secara otomatis (automated daemon) minimal $N+2$ periode ke depan (misal: 2 bulan sebelum tanggal jatuh tempo) untuk mencegah error missing partition `no partition of relation found for row`. | [ ] |
| **Locking DDL** | Atur `SET LOCAL lock_timeout = '3s'` dan `SET LOCAL statement_timeout = '10s'` sebelum mengeksekusi DDL maintenance skema partisi guna mencegah *starvation cascade*. | [ ] |
| **Indexes** | Jangan gunakan indeks global jika mesin tidak mendukungnya; gunakan *sparse index* atau *partial index* pada partisi aktif untuk memangkas konsumsi write IOPS. | [ ] |
| **Functions** | Deklarasikan volatilitas fungsi (`IMMUTABLE`, `STABLE`, `VOLATILE`) secara jujur dan presisi untuk memungkinkan compiler melakukan optimasi *inlining* dan *subquery flattening*. | [ ] |
| **Default Partition** | Hindari penggunaan `DEFAULT` partition jika Anda berniat membagi partisi baru di kemudian hari menggunakan range tertentu, karena `ATTACH PARTITION` baru akan gagal jika `DEFAULT` partisi sudah terisi data yang masuk ke range tersebut. | [ ] |

---

### 12. Hands-on Practice

Buat skrip pengujian arsitektur database produksi berikut pada direktori lokal Anda: `hands-on/m02/partition_architecture.sql`.

#### Langkah 1: Inisialisasi Environment & Skema Partisi Gabungan (Range + Subpartition List)
```sql
-- File: hands-on/m02/partition_architecture.sql

DROP TABLE IF EXISTS orders CASCADE;

-- Root partitioned table
CREATE TABLE orders (
    order_id BIGINT GENERATED ALWAYS AS IDENTITY,
    region VARCHAR(10) NOT NULL,
    order_date DATE NOT NULL,
    total_amount NUMERIC(12,2) NOT NULL,
    payload JSONB DEFAULT '{}',
    PRIMARY KEY (order_id, region, order_date)
) PARTITION BY RANGE (order_date);

-- Sub-partition Level: Q1 2025 Partition (Bulan 1 - 3)
CREATE TABLE orders_2025_q1 PARTITION OF orders
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01')
    PARTITION BY LIST (region);

-- Leaf Partitions
CREATE TABLE orders_2025_q1_apac PARTITION OF orders_2025_q1
    FOR VALUES IN ('APAC');

CREATE TABLE orders_2025_q1_emea PARTITION OF orders_2025_q1
    FOR VALUES IN ('EMEA');
```

#### Langkah 2: Populasikan Dataset Simulasi Skala Besar
```sql
-- Injeksi data 100.000 baris acak ke partisi APAC
INSERT INTO orders (region, order_date, total_amount, payload)
SELECT 
    'APAC',
    '2025-01-01'::date + (trunc(random() * 85)::int),
    (random() * 5000)::numeric(12,2),
    jsonb_build_object('client', 'enterprise_' || (1 + trunc(random() * 500))::text, 'verified', true)
FROM generate_series(1, 100000);

-- Injeksi data 10.000 baris ke partisi EMEA
INSERT INTO orders (region, order_date, total_amount, payload)
SELECT 
    'EMEA',
    '2025-01-01'::date + (trunc(random() * 85)::int),
    (random() * 5000)::numeric(12,2),
    jsonb_build_object('client', 'sme_' || (1 + trunc(random() * 100))::text, 'verified', false)
FROM generate_series(1, 10000);
```

#### Langkah 3: Evaluasi Execution Plan & Verifikasi Pruning
```sql
-- Analisis verifikasi Pruning di 2 level (Range Date & List Region)
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    region, 
    COUNT(*), 
    AVG(total_amount) 
FROM orders
WHERE order_date BETWEEN '2025-01-15' AND '2025-02-15'
  AND region = 'APAC'
GROUP BY region;

-- Ekspektasi Output:
-- HANYA orders_2025_q1_apac yang di-scan. orders_2025_q1_emea ter-prune total.
```

---

### 13. Exercise

#### Level Easy
Buat sebuah tabel bernama `system_logs` yang dipartisi berdasarkan **HASH** pada kolom `service_id` (UUID) menjadi 3 partisi. Pastikan primary key mencakup kolom yang valid. Tuliskan query insert dan query `EXPLAIN` untuk membuktikan data ter-routing ke partisi yang tepat.

#### Level Medium
Buat sebuah skema **Temporal Table** untuk data entitas `customer_wallets` (`wallet_id`, `balance`, `sys_period`). Buat sebuah Trigger Function yang secara otomatis melakukan *interception* pada operasi `UPDATE`:
- Record lama di-update interval akhirnya menjadi `CURRENT_TIMESTAMP`.
- Snapshot baru disisipkan secara transparan tanpa mengubah query update standar dari sisi aplikasi.

#### Level Hard
Rancang arsitektur **Automated Partition Creator**. Buat sebuah Stored Procedure `sp_maintain_monthly_partitions(p_table_name TEXT, p_months_ahead INT)`:
- Menghitung rentang tanggal secara dinamis untuk $N$ bulan ke depan.
- Memeriksa ke sistem katalog `pg_class` dan `pg_inherits` apakah partisi untuk bulan tersebut sudah ada.
- Jika belum, buat partisi baru secara dinamis menggunakan DDL string execution (`EXECUTE format(...)`) lengkap dengan penamaan konvensional (`_YYYY_MM`), dan otomatis membangun GIN Index pada kolom JSONB-nya jika root table memiliki kolom berjenis JSONB.

---

### 14. Challenge

**Studi Kasus: Zero-Downtime Data Re-architecting pada Skala 10 TB**

Anda masuk ke dalam perusahaan FinTech yang memiliki tabel monolitik `audit_trails` berukuran fisik 8 TB (12 Miliar baris data non-partitioned). Tabel ini mengalami degradasi performa akut:
1. Operasi query analytics bulanan memicu I/O saturation tinggi, melumpuhkan operational microservices.
2. Kebijakan compliance mewajibkan retensi data 7 tahun, namun data berumur lebih dari 1 tahun harus dipindahkan ke storage dingin (archival) dan data berumur lebih dari 7 tahun harus dihapus secara otomatis setiap kuartal.
3. Database utama tidak boleh mengalami down-time atau locking eksklusif lebih dari 2 detik karena SLA sistem transaksi adalah 99.99%.

**Tugas Arsitektur:**
Susun *Technical Blueprint Runbook* lengkap dengan mitigasi teknis dan skrip SQL deklaratif:
- Bagaimana cara memindahkan data dari tabel monolitik ke skema declarative partition baru tanpa locking tabel monolitik secara berkepanjangan?
- Bagaimana Anda menangani sinkronisasi data yang sedang aktif ditulis (CDC / Trigger Based Re-route / Logical Replication)?
- Bagaimana rancangan arsitektur pemindahan data historis ke *Cold Tier* (misalnya memanfaatkan Foreign Data Wrapper / `postgres_fdw` yang terhubung ke instance database storage arsip berbiaya rendah) dan bagaimana query layer aplikasi tetap dapat mengakses data dingin tersebut secara transparan?

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (5 Soal)
1. **Mengapa kolom yang dijadikan Partition Key wajib ada dalam setiap Unique Index dan Primary Key dari tabel yang dipartisi?**
   - *Jawaban:* Engine relational basis data mengevaluasi unique index secara lokal di level masing-masing partisi fisik demi menjaga performa tinggi. Agar keunikan data global dapat dijamin tanpa perlu mengunci atau memindai seluruh partisi lain di setiap operasi `INSERT`/`UPDATE`, partition key harus menjadi bagian dari key constraint tersebut.

2. **Apa yang dimaksud dengan Dynamic Partition Pruning dan apa perbedaannya dengan Static Partition Pruning?**
   - *Jawaban:* Static Pruning terjadi pada fase kompilasi/perencanaan query (plan-time) saat predikat bernilai literal konstan. Dynamic Pruning terjadi saat execution-time ketika predikat bergantung pada variabel eksternal, subquery skalar, atau prepared statements yang nilainya baru diketahui saat eksekutor berjalan.

3. **Sebutkan tiga klasifikasi volatilitas fungsi pada PostgreSQL dan jelaskan fungsi paling optimal untuk optimizer.**
   - *Jawaban:* `IMMUTABLE`, `STABLE`, dan `VOLATILE`. Yang paling optimal adalah `IMMUTABLE` karena optimizer dapat mengevaluasi hasilnya satu kali di muka (constant folding) dan menggunakannya kembali di sepanjang siklus query tree.

4. **Operasi manajemen partisi mana yang lebih hemat resource I/O dan WAL: Menjalankan `DELETE FROM table WHERE date < '2024-01-01'` atau menggunakan `ALTER TABLE ... DETACH PARTITION`? Mengapa?**
   - *Jawaban:* `ALTER TABLE ... DETACH PARTITION` jauh lebih hemat karena merupakan operasi metadata-only ($O(1)$) tanpa penulisan WAL logging untuk baris-baris data individual, tanpa mengaktifkan vacuum engine, dan tidak memicu table bloat.

5. **Apa risiko arsitektur jika menggunakan sub-partitioning yang terlalu dalam dan granular (misal: membagi data menjadi ribuan partisi kecil)?**
   - *Jawaban:* Performa optimizer akan terdegradasi drastis (overhead waktu planning yang tinggi), penggunaan memori per query melonjak akibat konsumsi lock cache metadata ribuan partisi (`max_locks_per_transaction`), dan overhead context-switch saat mengeksekusi multi-partition scanning.

#### B. Pertanyaan Intermediate (5 Soal)
6. **Perhatikan query berikut:**
   ```sql
   SELECT * FROM sensor_readings WHERE date_trunc('month', recorded_at) = '2025-02-01'::date;
   ```
   **Jika `sensor_readings` dipartisi berdasarkan range pada kolom `recorded_at`, apakah engine akan melakukan partition pruning? Jelaskan mekanismenya!**
   - *Jawaban:* Tidak akan terjadi static pruning (terjadi Full Partition Scan). Penerapan fungsi (`date_trunc`) pada kolom partisi menyembunyikan nilai asli kolom dari optimizer, sehingga optimizer tidak dapat memetakan predikat ke batas-batas interval partisi. Solusinya adalah mengubah klausa WHERE menjadi bentuk sargable: `WHERE recorded_at >= '2025-02-01'::date AND recorded_at < '2025-03-01'::date`.

7. **Kapan Anda sebaiknya memilih indexing `jsonb_path_ops` dibandingkan operator kelas default `jsonb_ops` pada GIN index kolom JSONB?**
   - *Jawaban:* Gunakan `jsonb_path_ops` saat query dominan menggunakan operator matching `@>` (containment). Index ini menghasilkan ukuran disk space yang jauh lebih kecil (hanya menyimpan hash path dan value) serta pencarian containment yang lebih cepat, namun tidak mendukung query eksistensi key tunggal seperti operator `?`, `?|`, atau `?&`.

8. **Bagaimana mekanisme `DETACH PARTITION ... CONCURRENTLY` bekerja di PostgreSQL 12+ untuk mencegah sistem freeze?**
   - *Jawaban:* Mekanisme ini memecah pelepasan partisi menjadi dua transaksi internal terpisah dengan hanya memegang lock level rendah (`ShareUpdateExclusiveLock`) yang tidak memblokir pembacaan (`SELECT`) maupun penulisan (`INSERT/UPDATE/DELETE`). Sistem menunggu seluruh transaksi yang sedang membaca partisi tersebut selesai, lalu mereset pointer inheritance metadata secara aman.

9. **Apa perbedaan mendasar antara System-Versioned Temporal Data dan skema audit berbasis Change Log Table biasa?**
   - *Jawaban:* Temporal Data mengintegrasikan histori status entitas langsung ke dalam representasi record (menggunakan interval validitas temporal multi-dimensi `sys_period`), mendukung *Point-in-Time queries* deklaratif (`AS OF SYSTEM TIME`), dan menjamin konsistensi ACID secara atomik bersamaan dengan mutasi record induk tanpa lag asinkron atau duplikasi row id audit.

10. **Mengapa pemanggilan fungsi yang berstatus `VOLATILE` di dalam klausa `WHERE` dapat melumpuhkan kinerja pengindeksan partisi?**
    - *Jawaban:* Optimizer mengasumsikan fungsi `VOLATILE` dapat memberikan hasil yang berbeda pada setiap baris evaluasi. Akibatnya, optimizer dilarang mengasumsikan batasan konstan untuk pruning partisi dan terpaksa memindai semua partisi secara sekuensial serta mengevaluasi fungsi tersebut baris demi baris (*row-by-row re-evaluation*).

#### C. Skenario Kasus Produksi (3 Kasus)

11. **Kasus 1: Partition Lock Exhaustion saat High Traffic**
    - *Konteks:* Sistem pembayaran Anda memproses 5.000 TPS. Tim DevOps menjalankan skrip migration partisi bulanan baru pada jam sibuk:
      ```sql
      ALTER TABLE payment_transactions ATTACH PARTITION payment_transactions_2025_03
      FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
      ```
      Tiba-tiba seluruh sistem mengalami connection pool exhaustion dan request timeout massal, meskipun partisi yang di-*attach* kosong.
    - *Identifikasi & Resolusi:* DDL `ATTACH PARTITION` memerlukan validasi integritas data pada partisi yang ditempelkan untuk memastikan tidak ada data di luar batas jangkauan (range). Selama proses verifikasi scanning, engine memegang `AccessExclusiveLock` pada root table.
    - *Solusi Enterprise:* Sebelum melakukan `ATTACH`, buat partisi baru dengan CHECK CONSTRAINT eksplisit: `CHECK (created_at >= '2025-03-01' AND created_at < '2025-04-01')`. Saat proses `ATTACH PARTITION` dieksekusi, database akan memvalidasi metadata constraint yang sudah ada secara instan ($O(1)$) tanpa melakukan full scan, dan kunci `AccessExclusiveLock` hanya ditahan dalam hitungan milidetik. Setelah itu, drop check constraint yang redundan tersebut.

12. **Kasus 2: Missing Indexing Bloat pada Sub-Partitioning**
    - *Konteks:* Seorang developer membuat range partitioned table `deliveries` dengan 48 partisi bulanan. Kemudian, ia mengeksekusi pembuatan index pada tabel induk:
      ```sql
      CREATE INDEX idx_deliveries_tracking_id ON deliveries(tracking_id);
      ```
      Operasi ini membuat database I/O IOPS naik hingga 100% dan latency melonjak selama 45 menit.
    - *Identifikasi & Resolusi:* Perintah pembuatan index pada partitioned parent table secara otomatis membuat index pada **seluruh 48 sub-tabel secara sekuensial dan blocking** dalam satu transaksi raksasa.
    - *Solusi Enterprise:* Buat index menggunakan pendekatan `CREATE INDEX ONLY ON deliveries` (menciptakan index invalid di tingkat induk), lalu iterasi setiap partisi anak untuk membuat index secara paralel dengan instruksi non-blocking: `CREATE INDEX CONCURRENTLY idx_deliveries_part_... ON deliveries_part_...`. Setelah seluruh partisi anak memiliki index, gabungkan index anak ke index induk melalui `ALTER INDEX idx_deliveries_tracking_id ATTACH PARTITION ...`.

13. **Kasus 3: JSONB Data Skewness dan Query Optimizer Degradation**
    - *Konteks:* Tabel partisi `events` memiliki kolom `payload JSONB`. Tim data menjalankan query:
      ```sql
      SELECT * FROM events WHERE payload->>'status' = 'FAILED' AND event_date = '2025-02-10';
      ```
      Sebagian besar status bernilai 'SUCCESS' (99.9%), dan hanya 0.1% bernilai 'FAILED'. Optimizer memilih `Seq Scan` pada partisi tersebut alih-alih menggunakan GIN Index yang tersedia.
    - *Identifikasi & Resolusi:* Default statistics target PostgreSQL tidak menyimpan frekuensi distribusi elemen internal di dalam object JSONB, sehingga optimizer memperkirakan selektivitas yang salah (*poor selectivity estimation*).
    - *Solusi Enterprise:* Jangan hanya mengandalkan GIN index generik. Buat **Partial Functional Index B-Tree** khusus untuk kasus skewness tersebut pada masing-masing partisi:
      ```sql
      CREATE INDEX idx_events_failed_status 
      ON events_2025_02 ((payload->>'status')) 
      WHERE (payload->>'status' = 'FAILED');
      ```
      Hal ini menghasilkan index yang sangat kecil, super cepat, dan langsung dipilih oleh planner tanpa memerlukan pembacaan GIN tree yang kompleks.

---

### 16. Summary

Implementasi lanjutan partisi database dan skema enterprise bukan sekadar memecah baris data ke dalam beberapa sub-tabel, melainkan rekayasa mekanik di tingkat penyimpanan dan pemrosesan query:
- **Pruning Efficiency:** Efektivitas performa partisi ditentukan oleh kemampuan Query Optimizer mengeksekusi *Static & Dynamic Pruning*. Selalu lindungi kueri Anda agar tetap *Sargable* dan hindari *implicit casting*.
- **Contention-Free Maintenance:** Perubahan metadata tabel partisi menuntut tingkat lock tertinggi (`AccessExclusiveLock`). Seluruh alur kerja maintenance produksi wajib diproteksi dengan guardrail `lock_timeout`, teknik `CONCURRENTLY`, dan validasi check constraint sebelum *attaching*.
- **Heterogeneous Architecture:** Mengombinasikan model relasional formal, *Temporal Versioning*, dan *JSONB/Document Store* dengan fungsional indexing parsial memberikan fleksibilitas tanpa mengorbankan performa ataupun integritas ACID.
- **Engine-Level Programmability:** Kontrol ketat atas volatilitas fungsi (`IMMUTABLE`, `STABLE`, `VOLATILE`) adalah kunci untuk memampukan engine melakukan optimasi eksekusi query internal secara paralel dan deterministik.