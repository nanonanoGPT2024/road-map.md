# BAB 06: Data Mutations, Upserts & Recursive CTEs
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai mekanika internal *Write Path*, *Multi-Version Concurrency Control* (MVCC), *Write Amplification*, dan *Tuple Locking* pada operasi mutasi skala besar (`INSERT`, `UPDATE`, `DELETE`).
- Merancang dan mengeksekusi strategi mutasi idempoten menggunakan primitive `ON CONFLICT` (*Upsert*) dan klausa `MERGE`, serta memahami implikasi *concurrency race condition* (*unique constraint violation under high contention*).
- Mengimplementasikan pola pemrosesan berbasis antrean (*queue-like processing*) berkinerja tinggi menggunakan `SELECT ... FOR UPDATE SKIP LOCKED` dan mutasi atomik terdistribusi via klausa `RETURNING`.
- Mengonstruksi kueri hierarkis dan graf kompleks menggunakan *Recursive Common Table Expressions* (CTE) dengan mekanisme kontrol terminasi, deteksi siklus (*cycle detection*), dan optimasi kedalaman traversing (*depth/breadth-first traversal*).
- Menghitung dampak operasional *table bloat*, *HOT (Heap-Only Tuples) updates*, serta merancang arsitektur mutasi batch untuk memitigasi latensi replikasi dan *lock escalation*.

---

### 2. Prerequisite
Untuk menyerap materi ini secara optimal, peserta wajib memahami:
- **Relational Foundations**: Teori himpunan, ACID (*Atomicity, Consistency, Isolation, Durability*), dan level isolasi transaksi (*Read Committed*, *Repeatable Read*, *Serializable*).
- **Index Structures**: B-Tree mechanics, *Composite Indexes*, serta perbedaan antara *Index Scan*, *Index Only Scan*, dan *Bitmap Heap Scan*.
- **PostgreSQL / ANSI SQL Basics**: Sintaks dasar DML, klausa `JOIN`, CTE standar non-rekursif (`WITH`), dan penggunaan *constraints* (`PRIMARY KEY`, `UNIQUE`, `CHECK`, `FOREIGN KEY`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. MVCC Write Path, Tuple Headers, dan HOT (Heap-Only Tuples)
Pada sistem basis data relasional berbasis MVCC seperti PostgreSQL, baris data (*tuple*) bersifat *immutable*. Operasi `UPDATE` secara fisik tidak memodifikasi baris yang ada di tempat (*in-place*), melainkan mengeksekusi dua langkah atomik:
1. Menandai tuple lama sebagai kedaluwarsa dengan mengisi field `t_xmax` pada *tuple header* dengan ID transaksi saat ini (`XID`).
2. Menyisipkan tuple baru pada *data page* (baik di halaman yang sama atau halaman baru) dengan mengisi `t_xmin` baris baru dengan `XID` transaksi saat ini.

```
+--------------------------------------------------------------------------+
| Page Offset Table                                                        |
| [LinePointer 1] -------------> [Tuple Header: t_xmin=100, t_xmax=101]    |
| [LinePointer 2] ----+          (Old Row Data)                            |
|                     |                                                    |
|                     +--------> [Tuple Header: t_xmin=101, t_xmax=0]      |
|                                (New Row Data - HOT Update)               |
+--------------------------------------------------------------------------+
```

Jika kolom yang diubah diindeks oleh B-Tree, setiap `UPDATE` memaksa penyisipan pointer baru ke dalam indeks untuk setiap perubahan baris, memicu fenomena **Write Amplification**. 

PostgreSQL mengoptimalkan skenario ini dengan **HOT (Heap-Only Tuples)**:
- Syarat 1: Kolom yang diperbarui bukan merupakan bagian dari indeks mana pun (*no indexed column changed*).
- Syarat 2: Masih terdapat ruang kosong yang memadai (*free space*) di dalam *data page* yang sama untuk menyimpan tuple baru.
Jika kedua syarat terpenuhi, indeks tetap menunjuk ke *LinePointer* lama, dan pointer internal menghubungkan baris lama langsung ke baris baru (*root-to-chain link*), mengeliminasi *overhead write* pada indeks.

#### 3.2. Primitive Upsert: Spekulatif Insertion dan Deadlock Contention
Sintaks `INSERT ... ON CONFLICT (target) DO UPDATE / DO NOTHING` bekerja dengan mekanisme **Speculative Insertion**:
1. Transaksi mencoba memasukkan baris baru ke *heap* secara spekulatif (*speculative token* terpasang).
2. Transaksi memvalidasi apakah ada *unique index violation*.
3. **Kasus A (Tidak Ada Konflik)**: Tuple dikonfirmasi, *speculative token* dilepas, tuple menjadi terlihat (*visible*).
4. **Kasus B (Konflik Terdeteksi)**:
   - Jika baris konflik dimasukkan oleh transaksi konkuren yang **belum selesai** (*in-flight*), transaksi saat ini tidur (*wait*) pada `XID` transaksi tersebut.
   - Jika transaksi lawan melakukan `COMMIT`, transaksi saat ini membatalkan penyisipan spekulatif, beralih ke jalur `DO UPDATE` (mengunci tuple target dengan `FOR KEY SHARE` atau `FOR UPDATE`), atau mengabaikan operasi jika `DO NOTHING`.
   - Jika transaksi lawan melakukan `ROLLBACK`, baris spekulatif kembali divalidasi dan penyisipan dilanjutkan.

*Resiko Tersembunyi*: Ketika ribuan transaksi melakukan `ON CONFLICT DO UPDATE` pada set kunci unik yang sama dalam urutan yang berbeda (*un-ordered batching*), sistem akan mengalami **Deadlock Engine Exception** pada level *row-locking*.

#### 3.3. Recursive CTE Execution Pipeline
Klausa `WITH RECURSIVE` dievaluasi menggunakan *Iterative Processing Loop* dengan dua komponen memori kerja internal:
1. **Working Table**: Buffer sementara yang menyimpan data hasil iterasi *step* sebelumnya.
2. **Intermediate Table**: Buffer akumulator tempat data dari langkah rekursif disatukan.

```
       [Anchor Query]
              |
              v
   +----------------------+
   | Insert to Work Table |
   +----------------------+
              |
              +----------------------------+
              v                            |
    Is Work Table Empty?                   |
      /                \                   |
    (Yes)              (No)                |
     /                    \                |
[Terminate & Return]   [Execute Recursive Step]
                         (Joins with Work Table)
                                   |
                                   v
                       [Populate Intermediate]
                                   |
                                   v
                       [Swap: Intermediate -> Work]
                                   |
                                   v
                         [Flush Intermediate]
                                   |
                                   +------- Loop Back
```

Mekanisme internal ini tidak menggunakan *call stack* konvensional seperti rekursi bahasa prosedural (C, Rust, Go), melainkan pendekatan set-based berbasis *queue-like looping*. Kueri berhenti saat *working table* menghasilkan nol baris data.

---

### 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan (Why) | Apa Itu (What) |
| :--- | :--- | :--- |
| **ON CONFLICT (Upsert)** | Menghindari anomali `SELECT then INSERT/UPDATE` (Race Condition) di aplikasi terdistribusi tanpa memerlukan isolasi `SERIALIZABLE` penuh. | Mekanisme atomik level *engine* untuk menyisipkan baris atau memperbarui baris target jika melanggar *unique constraint*. |
| **FOR UPDATE SKIP LOCKED** | Mencegah *thread contention* dan *lock queues* saat membangun pola antrean (*Job Queue*) di atas database relasional. | Mekanisme penguncian baris yang secara diam-diam melewati baris-baris yang telah dikunci transaksi lain, memfasilitasi throughput tinggi bagi banyak *worker*. |
| **RETURNING / OUTPUT** | Mengurangi *network round-trip* dari 2 RTT (Mutasi lalu Query) menjadi 1 RTT, dan menjamin pembacaan data state pasca-mutasi secara deterministik. | Klausa DML untuk memproyeksikan kembali data tuple yang baru saja di-*insert*, di-*update*, atau di-*delete*. |
| **Recursive CTE** | Memodelkan struktur non-linier (pohon hierarki, graf dependensi, ACL, BOM) tanpa mengeksekusi banyak kueri iteratif dari *application layer*. | Struktur SQL deklaratif yang memungkinkan kueri merujuk pada namanya sendiri untuk mengevaluasi relasi parent-child secara berulang hingga kondisi batas tercapai. |

---

### 5. How (Workflow Detail)

#### Workflow: Zero-Downtime High-Throughput Safe Mutasi (Batch Processing)
Saat memutasi jutaan baris data di lingkungan produksi dengan beban baca tinggi, *direct update* (`UPDATE orders SET status = 'EXPIRED' WHERE ...`) akan memblokir *autovacuum*, memicu *lock escalation*, menyebabkan replikasi *lag*, dan memenuhi *write-ahead log* (WAL).

Tahapan standar mutasi batch skala enterprise:

```
[1. Segmentasi Range Data]
        │
        ▼
[2. Open Explicit Transaction Block]
        │
        ▼
[3. Lock Acquisition (FOR UPDATE with Chunk Limit)]
        │
        ▼
[4. Apply Mutation via RETURNING]
        │
        ▼
[5. Commit Transaction]
        │
        ▼
[6. Sleep Engine Throttle (e.g., 50ms - Prevent WAL Saturation)]
        │
        ▼
[7. Loop Next Chunk until Rows Processed = 0]
```

1. **Segmentasi Range**: Hindari `OFFSET`. Gunakan *Keyset Pagination* berbasis `PRIMARY KEY` (cth. `WHERE id > last_seen_id ORDER BY id ASC LIMIT 5000`).
2. **Explicit Lock Chunk**: Kunci baris spesifik per batch untuk menghindari *exclusive table lock*.
3. **Execute Mutation**: Terapkan modifikasi data.
4. **Commit & Throttle**: Lepaskan kunci segera dan berikan jeda waktu (*sleep*) agar proses *replication stream* dan *autovacuum daemon* dapat mengejar ketertinggalan.

---

### 6. Analogy & Diagram ASCII

#### Analogi Recursive CTE: Jalur Konveyor Perakitan Mobil (Bill of Materials)
Bayangkan sebuah pabrik mobil:
- **Anchor**: Anda meletakkan sasis utama di atas konveyor pertama (*Working Table*).
- **Recursive Step**: Lengan robot melihat komponen yang ada di konveyor, lalu mencari sub-komponennya dari rak gudang (cth. sasis membutuhkan as roda dan pintu). Sub-komponen ini diletakkan di konveyor berikutnya.
- **Looping**: Siklus berulang, memeriksa sub-sub komponen (cth. pintu butuh handle, kaca, dinamo).
- **Terminasi**: Ketika rak gudang menyatakan komponen terkecil (baut, lembaran kaca) tidak memiliki sub-komponen lagi, konveyor berhenti. Semua part yang tercatat dari awal hingga akhir dikemas menjadi daftar utuh.

#### Diagram: Lock Contention pada Mutasi
```
Worker A (Txn 1): UPDATE orders WHERE id = 100 ────[LOCK HELD]───────► (Processing...)
                                                          │
Worker B (Txn 2): UPDATE orders WHERE id = 100 ───────[BLOCKED]──────► (Waiting on Txn 1)
                                                          │
Worker C (Txn 3): SELECT id FROM orders                   │
                  WHERE id = 100                          │
                  FOR UPDATE SKIP LOCKED ────────────────[SKIPPED]────► (Evaluates id = 101)
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Mutasi Idempoten (Upsert) & RETURNING
Menyimpan state telemetri *device* terakhir, memperbarui metrik jika ID sudah ada, dan langsung mengambil *generated ID* atau status terkini.

```sql
CREATE TABLE device_telemetry (
    device_id VARCHAR(64) PRIMARY KEY,
    last_ping TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    retry_count INT DEFAULT 0
);

-- Eksekusi Upsert
INSERT INTO device_telemetry (device_id, last_ping, payload, retry_count)
VALUES ('DEV-NODE-99X', CLOCK_TIMESTAMP(), '{"temp": 42.5, "status": "WARN"}', 1)
ON CONFLICT (device_id) 
DO UPDATE SET
    last_ping = EXCLUDED.last_ping,
    payload = EXCLUDED.payload,
    retry_count = device_telemetry.retry_count + 1
RETURNING device_id, last_ping, retry_count, (XMAX = 0) AS is_inserted;
```
*Catatan Teknis*: Ekspresi `(XMAX = 0)` adalah trik internal PostgreSQL; jika `XMAX` bernilai `0`, baris tersebut baru di-*insert*, jika bernilai selain `0`, baris tersebut di-*update*.

#### 7.2. Practical Example: Pola Antrean Transaksional (Skip Locked Worker)
Implementasi *Distributed Task Outbox* yang aman dari *race conditions* dan *deadlock*.

```sql
CREATE TABLE transaction_outbox (
    outbox_id BIGSERIAL PRIMARY KEY,
    aggregate_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_outbox_processing 
ON transaction_outbox (created_at ASC) 
WHERE status = 'PENDING';

-- Eksekusi oleh Worker (Thread-Safe Task Dispatcher)
WITH claimable_tasks AS (
    SELECT outbox_id
    FROM transaction_outbox
    WHERE status = 'PENDING'
      AND (locked_until IS NULL OR locked_until < NOW())
    ORDER BY created_at ASC
    LIMIT 10
    FOR UPDATE SKIP LOCKED
)
UPDATE transaction_outbox t
SET 
    status = 'PROCESSING',
    locked_until = NOW() + INTERVAL '2 minutes'
FROM claimable_tasks c
WHERE t.outbox_id = c.outbox_id
RETURNING t.outbox_id, t.aggregate_type, t.payload;
```

#### 7.3. Practical Example: Recursive CTE dengan Cycle Detection & Path Tracking
Menelusuri struktur kategori multi-level atau pohon hierarki organisasi perusahaan, mendeteksi jika terjadi kesalahan data yang menyebabkan siklus rekursi tak berhingga (*infinite loop*).

```sql
CREATE TABLE organizational_units (
    unit_id INT PRIMARY KEY,
    unit_name VARCHAR(100) NOT NULL,
    parent_unit_id INT REFERENCES organizational_units(unit_id)
);

-- Recursive CTE: Mengambil seluruh pohon bawahan beserta path lengkap & cycle protection
WITH RECURSIVE org_tree AS (
    -- Anchor Member: Root node (Direksi Utama)
    SELECT 
        unit_id,
        unit_name,
        parent_unit_id,
        1 AS depth_level,
        ARRAY[unit_id] AS path_trace,
        FALSE AS is_cycle
    FROM organizational_units
    WHERE parent_unit_id IS NULL

    UNION ALL

    -- Recursive Member: Sub-unit
    SELECT 
        child.unit_id,
        child.unit_name,
        child.parent_unit_id,
        parent.depth_level + 1,
        parent.path_trace || child.unit_id,
        child.unit_id = ANY(parent.path_trace) AS is_cycle
    FROM organizational_units child
    JOIN org_tree parent ON child.parent_unit_id = parent.unit_id
    WHERE NOT parent.is_cycle
)
SELECT 
    depth_level,
    REPEAT('  ', depth_level - 1) || unit_name AS visual_hierarchy,
    path_trace,
    is_cycle
FROM org_tree
ORDER BY path_trace;
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Ledakan Mutasi FinTech Ledger & Graph Multi-Tier Referral Fraud Detection

**Konteks Arsitektur:**
Sebuah platform perbankan digital skala enterprise memproses 15.000 mutasi transaksi per detik (TPS). Di saat bersamaan, sistem mendeteksi fraud jaringan sindikat rujukan (*referral network ring*) hingga kedalaman 12 level relasi akun pengguna.

**Problem Statement:**
1. Mutasi saldo rekening via `UPDATE balance = balance + :amount WHERE id = :user_id` memicu *row lock contention* brutal, mengakibatkan lonjakan *connection pool saturation* dan *thread starvation*.
2. Akun-akun fraud membuat jaringan referal melingkar (*A mereferensikan B, B mereferensikan C, C mereferensikan A*) untuk membobol sistem pembagian reward signup. Kueri rekursif standar memicu *Out-Of-Memory* (OOM) dan *Statement Timeout* pada node analitik database.

**Solusi Arsitektural Terintegrasi:**
1. **Ledger Mutation Engine**:
   - Menghilangkan mutasi langsung pada *row* akun balance. Menggantinya dengan arsitektur *Immutable Append-Only Balance Log*.
   - Konsolidasi saldo menggunakan *Micro-Batching Upsert Worker* dengan segmentasi penguncian deterministik berurutan (mencegah *deadlock* dengan mengurutkan ID secara ascending sebelum mutasi).
2. **Fraud Cycle Detection Recursive Query**:
   - Membatasi eksekusi rekursi menggunakan array akumulator path traversal.
   - Menghentikan traversal secara instan (*circuit-breaker*) saat ambang batas kedalaman (*depth limit*) terlampaui atau terjadi circular dependency.

```sql
-- DDL Desain Akun & Referral
CREATE TABLE accounts (
    account_id BIGINT PRIMARY KEY,
    referred_by_id BIGINT REFERENCES accounts(account_id),
    current_balance NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE account_balance_delta_buffer (
    delta_id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL,
    amount NUMERIC(18, 4) NOT NULL,
    processed BOOLEAN NOT NULL DEFAULT FALSE
);

-- 1. Micro-Batch Balance Flush: Mengonsolidasi jutaan delta menjadi 1 batch aman
WITH batch_deltas AS (
    SELECT 
        account_id, 
        SUM(amount) AS total_delta
    FROM (
        SELECT delta_id, account_id, amount
        FROM account_balance_delta_buffer
        WHERE processed = FALSE
        ORDER BY account_id ASC -- Kritis: Mengurutkan ID mengeliminasi deadlock
        LIMIT 5000
        FOR UPDATE SKIP LOCKED
    ) locked_batch
    GROUP BY account_id
),
updated_accounts AS (
    UPDATE accounts a
    SET current_balance = a.current_balance + b.total_delta
    FROM batch_deltas b
    WHERE a.account_id = b.account_id
    RETURNING a.account_id
)
UPDATE account_balance_delta_buffer
SET processed = TRUE
WHERE delta_id IN (
    SELECT delta_id FROM account_balance_delta_buffer
    WHERE account_id IN (SELECT account_id FROM updated_accounts)
      AND processed = FALSE
);

-- 2. Anti-Fraud Recursive Query: Deteksi Jaringan Referral & Loop
WITH RECURSIVE referral_network AS (
    -- Anchor: Akun yang dicurigai
    SELECT 
        account_id AS root_suspect,
        account_id AS current_member,
        referred_by_id,
        1 AS traversal_depth,
        ARRAY[account_id] AS traversal_chain,
        FALSE AS loop_detected
    FROM accounts
    WHERE account_id = 987654

    UNION ALL

    -- Recursive Step: Lacak upline
    SELECT 
        net.root_suspect,
        acc.account_id,
        acc.referred_by_id,
        net.traversal_depth + 1,
        net.traversal_chain || acc.account_id,
        acc.account_id = ANY(net.traversal_chain) AS loop_detected
    FROM accounts acc
    JOIN referral_network net ON acc.account_id = net.referred_by_id
    WHERE NOT net.loop_detected 
      AND net.traversal_depth < 12 -- Circuit Breaker kedalaman
)
SELECT 
    root_suspect,
    current_member,
    traversal_depth,
    traversal_chain,
    loop_detected
FROM referral_network
WHERE loop_detected = TRUE;
```

---

### 9. Trade-offs

```
                                  TRADE-OFF MATRIX
        +-------------------------------------------------------------------+
        | [Strategy A: In-Place UPDATE]                                     |
        | - Latensi Rendah                                                  |
        | - Resiko: Table Bloat, Lock Contention, Index Maintenance Overhead |
        +-------------------------------------------------------------------+
                                         ▲
                                         │ (Alternative)
                                         ▼
        +-------------------------------------------------------------------+
        | [Strategy B: Append-Only Delta Log + Batch Aggregation]           |
        | + High-Throughput Ingestion (No Lock Waits), Zero Bloat           |
        | - Kompleksitas Operasional, Eventual Consistency pada Read State  |
        +-------------------------------------------------------------------+
```

| Parameter Arsitektur | Single-Statement Mutasi Langsung | Batch Mutasi via Keyset (`SKIP LOCKED`) |
| :--- | :--- | :--- |
| **Write Latency** | Instan (mikrodetik) untuk single-row; eksponensial di bawah beban tinggi. | Terkelompokkan (*batched*), memperkenalkan latensi agregasi milidetik. |
| **Throughput (TPS)** | Degradasi tajam saat terjadi *row contention* (*lock waits*). | Tetap stabil pada kapasitas *saturation point* disk I/O. |
| **Replication Lag** | Mengirim gelombang WAL raksasa yang memblokir engine replika. | Aliran WAL linear, ramah terhadap *logical decoding* streaming. |
| **Memory Footprint** | Rendah, namun dapat membengkakkan *Lock Table* OS/Database. | Terkendali sesuai ukuran batch (`LIMIT`). |
| **Recursive CTE Depth** | N/A | Konsumsi RAM sebanding dengan ukuran *Working Table* di *work_mem*. |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Deadlock Tersembunyi pada `ON CONFLICT DO UPDATE`
*Penyebab*: Aplikasi memicu batch `INSERT ... ON CONFLICT` di mana Transaksi 1 memasukkan ID `[A, B]` dan Transaksi 2 memasukkan ID `[B, A]` pada waktu yang bersamaan.
*Solusi*: Wajib mengurutkan array entitas pada sisi kode aplikasi (*e.g., Go, Java, Python*) sebelum dialirkan ke kueri SQL.

#### Mistake 2: Ledakan Recursive CTE Tak Berhingga (*Infinite Loop*)
*Penyebab*: Terjadinya siklus data struktural (Node 1 -> Node 2 -> Node 1) pada tabel relasional tanpa kondisi penghenti atau deteksi array cycle.
*Solusi*: Jangan pernah menjalankan `WITH RECURSIVE` di lingkungan produksi tanpa salah satu dari batasan berikut:
1. `WHERE depth < MAX_LIMIT`
2. `WHERE NOT child_id = ANY(path_array)`
3. Menggunakan klausa ANSI: `CYCLE id SET is_cycle USING path` (PostgreSQL 14+).

#### Mistake 3: Table Bloat Akibat Non-HOT Updates
*Gejala*: Database membesar 5x lipat meskipun jumlah baris stabil. Disk I/O melonjak drastis.
*Troubleshooting*: Periksa status HOT Update via metrik internal:
```sql
SELECT 
    relname, 
    n_tup_upd, 
    n_tup_hot_upd, 
    ROUND((n_tup_hot_upd::numeric / NULLIF(n_tup_upd, 0)::numeric) * 100, 2) AS hot_ratio
FROM pg_stat_user_tables
WHERE relname = 'target_table_name';
```
Jika `hot_ratio` berada di bawah 80%, periksa indeks pada tabel tersebut. Lepaskan indeks yang tidak perlu atau sesuaikan parameter `fillfactor` (misal diubah dari 100 ke 85) untuk memberikan ruang lokal bagi tuple baru pada halaman yang sama:
```sql
ALTER TABLE target_table_name SET (fillfactor = 85);
VACUUM FULL target_table_name; -- Reorganize physical pages
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Deterministic Lock Ordering**: Selalu urutkan rekaman input (`ORDER BY primary_key ASC`) sebelum menjalankan batch mutasi.
- [ ] **Cap Your Chunks**: Jangan mengeksekusi mutasi batch lebih dari 5.000–10.000 baris dalam satu blok transaksi ACID.
- [ ] **Guard Recursive CTEs**: Pastikan setiap Recursive CTE memiliki *depth limit breaker* (`WHERE depth < 50`) dan mekanisme *Cycle Detection*.
- [ ] **Leverage HOT Updates**: Hindari menaruh indeks pada kolom status yang sering bermutasi tinggi (seperti `status`, `updated_at`, `attempts`) jika tidak krusial untuk kueri filter utama.
- [ ] **Use Partial Indexes for Outbox**: Bila membangun antrean berbasis tabel, selalu gunakan partial index: `CREATE INDEX ... WHERE status = 'PENDING'`.
- [ ] **Throttling After Chunking**: Berikan waktu istirahat mikro (`pg_sleep(0.05)`) di antara siklus batch mutasi untuk memberikan ruang bagi *autovacuum daemon* dan *WAL archiving*.
- [ ] **Explicit Isolation Constraints**: Gunakan `READ COMMITTED` untuk pola *Skip Locked*. Hindari `REPEATABLE READ` atau `SERIALIZABLE` saat memproses antrean konkuren karena akan memicu banjir error `40001 (serialization_failure)`.

---

### 12. Hands-on Practice

Simpan seluruh skrip latihan ini ke dalam direktori lokal: `hands-on/m02/production_mutations.sql`.

```sql
-- hands-on/m02/production_mutations.sql
-- Setup Environment Praktikum Enterprise

BEGIN;

CREATE SCHEMA IF NOT EXISTS lab_m02;
SET search_path TO lab_m02, public;

-- Drop jika sudah ada
DROP TABLE IF EXISTS task_queue CASCADE;
DROP TABLE IF EXISTS inventory_nodes CASCADE;

-- 1. Setup Skema Job Queue Berkinerja Tinggi
CREATE TABLE task_queue (
    task_id BIGSERIAL PRIMARY KEY,
    payload TEXT NOT NULL,
    priority INT NOT NULL DEFAULT 5,
    status VARCHAR(20) NOT NULL DEFAULT 'READY',
    retry_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_task_queue_ready 
ON task_queue (priority DESC, created_at ASC) 
WHERE status = 'READY';

-- 2. Setup Skema Hierarki Graf (Bill of Materials Komponen Mesin)
CREATE TABLE inventory_nodes (
    part_id INT PRIMARY KEY,
    part_name VARCHAR(100) NOT NULL,
    parent_part_id INT REFERENCES inventory_nodes(part_id),
    quantity_required INT NOT NULL DEFAULT 1
);

-- Seed Data Antrean
INSERT INTO task_queue (payload, priority)
SELECT 
    'TASK-PAYLOAD-' || gen.id, 
    (random() * 10)::int
FROM generate_series(1, 1000) AS gen(id);

-- Seed Data Graf Komponen (Ada Siklus Palsu untuk Uji Proteksi)
INSERT INTO inventory_nodes (part_id, part_name, parent_part_id, quantity_required) VALUES
(1, 'Pesawat Terbang', NULL, 1),
(2, 'Sayap Kiri', 1, 1),
(3, 'Sayap Kanan', 1, 1),
(4, 'Mesin Turbin A', 2, 2),
(5, 'Bilah Turbin Titanium', 4, 64),
(6, 'Baut Hexa High-Tensile', 5, 8),
(7, 'Komputer Navigasi', 1, 1);

COMMIT;

-- =======================================================================
-- PRAKTIKUM 1: Konsumsi 5 Task Teratas secara Konkuren (Worker Simulation)
-- =======================================================================
BEGIN;

WITH claimed_jobs AS (
    SELECT task_id
    FROM task_queue
    WHERE status = 'READY'
    ORDER BY priority DESC, created_at ASC
    LIMIT 5
    FOR UPDATE SKIP LOCKED
)
UPDATE task_queue t
SET 
    status = 'PROCESSING',
    retry_count = t.retry_count + 1
FROM claimed_jobs c
WHERE t.task_id = c.task_id
RETURNING t.task_id, t.payload, t.priority, t.status;

COMMIT;

-- =======================================================================
-- PRAKTIKUM 2: Hitung Total Kebutuhan Unit Bagian 'Baut' untuk 1 Pesawat
--               menggunakan Recursive CTE dengan Multiplied Aggregation
-- =======================================================================
WITH RECURSIVE bom_explosion AS (
    -- Anchor: Komponen Puncak
    SELECT 
        part_id,
        part_name,
        parent_part_id,
        quantity_required AS multiplier_path,
        1 AS level
    FROM inventory_nodes
    WHERE part_id = 1

    UNION ALL

    -- Recursive: Kalikan multiplier secara berantai ke bawah
    SELECT 
        child.part_id,
        child.part_name,
        child.parent_part_id,
        (parent.multiplier_path * child.quantity_required) AS multiplier_path,
        parent.level + 1
    FROM inventory_nodes child
    JOIN bom_explosion parent ON child.parent_part_id = parent.part_id
)
SELECT 
    part_id,
    part_name,
    level,
    multiplier_path AS total_units_needed_per_aircraft
FROM bom_explosion
ORDER BY level ASC, part_id ASC;
```

---

### 13. Exercise

#### Level Easy
Tuliskan kueri `INSERT ... ON CONFLICT` untuk tabel `user_login_tracker (user_id INT PRIMARY KEY, login_count INT, last_login TIMESTAMPTZ)`. Jika `user_id` sudah ada, inkremen nilai `login_count` sebanyak 1 dan perbarui `last_login` ke waktu sekarang. Dapatkan nilai akhir `login_count` pasca operasi menggunakan `RETURNING`.

```sql
-- Solusi:
INSERT INTO user_login_tracker (user_id, login_count, last_login)
VALUES (101, 1, NOW())
ON CONFLICT (user_id) 
DO UPDATE SET 
    login_count = user_login_tracker.login_count + 1,
    last_login = EXCLUDED.last_login
RETURNING user_id, login_count, last_login;
```

#### Level Medium
Buat kueri penghapusan data kedaluwarsa (*Data Purge*) pada tabel log raksasa `system_events (event_id BIGINT PRIMARY KEY, created_at TIMESTAMPTZ)`. Hapus 10.000 data terlama (lebih dari 90 hari lalu) secara aman tanpa menyebabkan *long-table locking* menggunakan pendekatan subquery `FOR UPDATE SKIP LOCKED`.

```sql
-- Solusi:
WITH targeted_rows AS (
    SELECT event_id
    FROM system_events
    WHERE created_at < NOW() - INTERVAL '90 days'
    ORDER BY created_at ASC
    LIMIT 10000
    FOR UPDATE SKIP LOCKED
)
DELETE FROM system_events s
USING targeted_rows t
WHERE s.event_id = t.event_id;
```

#### Level Hard
Diberikan tabel transit logistik: `shipment_hops (hop_id INT, from_city VARCHAR, to_city VARCHAR, cost NUMERIC)`. Tuliskan Recursive CTE untuk mencari **rute termurah** (*Shortest Path / Lowest Cost Algorithm*) dari kota `'JAKARTA'` menuju kota `'SURABAYA'`. Pastikan traversal berhenti jika rute berputar kembali ke kota yang sama (*loop prevention*).

```sql
-- Solusi:
WITH RECURSIVE flight_paths AS (
    -- Anchor: Mulai dari JAKARTA
    SELECT 
        to_city,
        cost AS total_cost,
        ARRAY['JAKARTA', to_city]::VARCHAR[] AS full_route,
        FALSE AS is_cycle
    FROM shipment_hops
    WHERE from_city = 'JAKARTA'

    UNION ALL

    -- Recursive step
    SELECT 
        next_hop.to_city,
        fp.total_cost + next_hop.cost,
        fp.full_route || next_hop.to_city,
        next_hop.to_city = ANY(fp.full_route)
    FROM shipment_hops next_hop
    JOIN flight_paths fp ON next_hop.from_city = fp.to_city
    WHERE NOT fp.is_cycle 
      AND NOT (next_hop.to_city = ANY(fp.full_route))
      AND array_length(fp.full_route, 1) < 8 -- Safeguard kedalaman
)
SELECT 
    full_route, 
    total_cost
FROM flight_paths
WHERE to_city = 'SURABAYA'
ORDER BY total_cost ASC
LIMIT 1;
```

---

### 14. Challenge

**Skenario Sistem: Distributed Financial Settlement & Ledger Reconciliation**

Sebuah core system e-commerce memiliki skema tabel ledger internal sebagai berikut:
- `accounts (id BIGINT PRIMARY KEY, balance NUMERIC, status VARCHAR)`
- `settlement_batch (id BIGINT, from_id BIGINT, to_id BIGINT, amount NUMERIC, state VARCHAR)`

Sistem menerima injeksi 50.000 record per menit ke dalam `settlement_batch` dengan status `'UNPROCESSED'`. Transaksi mutasi harus mengurangkan saldo `from_id` dan menambahkan saldo `to_id` secara atomik per entri batch.

**Objektif Arsitektur:**
1. Desain skrip SQL procedural/batching yang mampu memproses antrean `settlement_batch` per 2.500 data.
2. Anda **dilarang keras** memicu *Deadlock Error (Code 40P01)* meskipun akun yang sama muncul puluhan kali secara silang (cth. baris A mentransfer ke B, namun baris B mentransfer ke A di batch yang sama).
3. Saldo akun tidak boleh menjadi negatif (`CHECK balance >= 0`). Jika satu transfer dalam pasangan akun gagal karena saldo tidak cukup, state batch tersebut harus diubah menjadi `'REJECTED_INSUFFICIENT_FUNDS'` tanpa membatalkan transaksi mutasi akun-akun lain yang valid di batch tersebut.
4. Rancang solusi tanpa mengeksekusi *Single Row Iteration Loop* (*Cursor/RBAR - Row By Agonizing Row*). Solusi harus berbasis *Pure Set-Based SQL*.

*Petunjuk Teknis Arsitek*: Evaluasi penggunaan teknik *Global Resource Level Ordering via Row Locking*, pemisahan mutasi debit dan kredit menggunakan gabungan *CTE Unnest*, serta evaluasi saldo baru secara kondisional sebelum *applying updates*.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa operasi `UPDATE` pada PostgreSQL meningkatkan penggunaan ruang penyimpanan disk meskipun ukuran data teks yang disimpan tetap sama?
2. Apa perbedaan mendasar dalam penanganan baris target antara klausa `ON CONFLICT DO NOTHING` dengan `ON CONFLICT DO UPDATE`?
3. Pada kondisi fisik tabel seperti apa optimasi **HOT (Heap-Only Tuple)** gagal bekerja?
4. Apa fungsi dari klausa `RETURNING` pada operasi `DELETE`?
5. Komponen memori apa yang menjadi tumpuan *Recursive CTE* untuk menentukan apakah rekursi harus berlanjut atau berhenti?

#### B. Pertanyaan Intermediate
6. Mengapa penggunaan `SELECT ... FOR UPDATE` tanpa `SKIP LOCKED` dapat melumpuhkan skalabilitas aplikasi worker antrean horizontal (*horizontal worker scaling*)?
7. Pada isolasi transaksi `READ COMMITTED`, apa yang terjadi pada *subsequent evaluation* kueri `UPDATE` jika baris yang dituju sedang dikunci oleh transaksi konkuren lain yang kemudian melakukan `COMMIT` perubahan data?
8. Bagaimana cara mendeteksi bahwa *Recursive CTE* sedang terjebak dalam *infinite circular loop* tanpa harus menunggu query dibatalkan oleh *statement_timeout*?
9. Jelaskan mengapa mengurutkan record data sebelum eksekusi `INSERT ... ON CONFLICT` dapat mencegah terjadinya *Deadlock*!
10. Apa kelemahan performa terbesar dari klausa ANSI standard `MERGE` dibandingkan dengan native `ON CONFLICT` di PostgreSQL pada sistem konkurensi tingkat tinggi?

#### C. Skenario Kasus Produksi
11. **Kasus Replikasi**: Database Replica Anda mengalami *Replication Lag* yang meningkat signifikan dari 0 detik menjadi 45 menit sesaat setelah tim data mengeksekusi query:
    ```sql
    UPDATE user_profiles SET is_verified = FALSE WHERE last_active < '2023-01-01';
    ```
    Jelaskan secara struktural apa yang terjadi pada *Primary WAL Sender* dan *Replica WAL Receiver*, serta bagaimana memodifikasi operasi mutasi tersebut agar lag tetap mendekati 0!
12. **Kasus Deadlock Lock Escalation**: Pada beban mutasi 8.000 TPS, aplikasi sering melempar exception:
    `ERROR: deadlock detected - Process 2911 waits for ShareLock on transaction 8812...`
    Setelah dianalisis, query pemicunya adalah operasi `ON CONFLICT (email) DO UPDATE`. Indeks unik tersedia pada kolom `email`. Mengapa deadlock ini bisa terjadi padahal indeks unik sudah didefinisikan?
13. **Kasus Memory Saturation**: Sebuah Recursive CTE dijalankan untuk memetakan *Social Follower Graph* dengan total 10 juta baris data. Tiba-tiba mesin database utama mengalami *Linux OOM Killer* yang mematikan proses PostgreSQL engine (`postmaster terminated`). Parameter engine apa yang dilanggar, dan restrukturisasi kueri apa yang wajib diaplikasikan?

---

### 16. Summary

1. **MVCC Mutation Costs**: Pada engine database modern, mutasi data adalah operasi *write-heavy* yang kompleks. `UPDATE` dan `DELETE` meninggalkan jejak *dead tuples* yang memicu *table bloat* dan membebani I/O *autovacuum*. Memahami *HOT updates* dan konfigurasi *fillfactor* adalah kunci menjaga kecepatan engine.
2. **Idempotency & Concurrency**: Mempertahankan integritas data pada *high-concurrency writes* menuntut penggunaan primitive level engine seperti `ON CONFLICT`. Pengurutan masukan (*Deterministic Key Ordering*) mutlak diperlukan untuk mengeliminasi bahaya *deadlock*.
3. **Queue Pattern Optimization**: Menggunakan database relasional sebagai *message/job queue* hanya valid dan scalable di level produksi jika dieksekusi menggunakan kombinasi `SELECT ... FOR UPDATE SKIP LOCKED` dengan kueri mutasi berbasis klausa `RETURNING`.
4. **Hierarchical Graph Navigation**: *Recursive CTEs* menawarkan abstraksi manipulasi struktur data non-linear (pohon, jaringan, BOM) langsung pada sisi database. Namun, implementasinya di lingkungan produksi wajib disertai mekanisme pengaman: *Depth Limit Safeguards* dan *Array Path Cycle Detection* guna mencegah degradasi sumber daya komputasi.