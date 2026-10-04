# Bab 06 Module 01: Transaction Management & Concurrency Control

---

## Seksi 01: Identitas Modul
* **Track:** Database Administrator & Infrastructure Engineering
* **Kategori:** 04-Backend-and-Database
* **Modul:** Bab 06 Module 01 — Transaction Management & Concurrency Control
* **Tingkat Kesulitan:** Advanced / Production-Grade
* **Prasyarat:** PostgreSQL Architecture, Storage Engine & Buffer Pool Internals, Basic SQL DDL/DML, Familiaritas CLI Bash & `psql`.

---

## Seksi 02: Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Mendiagnosis dan mengonfigurasi 4 level isolasi transaksi SQL standard pada PostgreSQL serta menganalisis anomali konkurensi (*Dirty Read, Non-Repeatable Read, Phantom Read, Serialization Anomaly*).
2. Membedah arsitektur internal *Multi-Version Concurrency Control* (MVCC), struktur *tuple header* (`xmin`, `xmax`, `t_infomask`, `ctid`), serta kalkulasi visibilitas via *Transaction Snapshots*.
3. Menerapkan matriks penguncian eksplisit (*Table Locks, Row Locks, Advisory Locks*) dan memitigasi risiko *Deadlock* pada sistem transaksi konkuren tinggi.
4. Membangun strategi mitigasi *Transaction ID (XID) Wraparound* dan mengoptimalkan parameter *Aggressive Autovacuum Freeze*.
5. Mengembangkan pipeline observabilitas real-time untuk mendeteksi *idle in transaction*, *lock contention tree*, dan *serialization failures* menggunakan `pg_stat_activity` dan `pg_locks`.

---

## Seksi 03: Concept Map Diagram ASCII
```
+-------------------------------------------------------------------------------------------------+
|                        POSTGRESQL TRANSACTION MANAGEMENT & CONCURRENCY                         |
+-------------------------------------------------------------------------------------------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    |                                                           |
                    v                                                           v
       +-------------------------+                                 +-------------------------+
       |   ISOLATION & ANOMALY   |                                 |     MVCC INTERNALS      |
       +-------------------------+                                 +-------------------------+
       | * Read Committed        |                                 | * Tuple Header          |
       | * Repeatable Read       |                                 |   (xmin, xmax, ctid)    |
       | * Serializable (SSI)    |                                 | * Snapshots (Xmin:Xmax) |
       | * Anomalies (P1-A5B)    |                                 | * Commit Log (pg_xact)  |
       +-------------------------+                                 +-------------------------+
                    |                                                           |
                    +-----------------------------+-----------------------------+
                                                  |
                                                  v
                                     +--------------------------+
                                     |   LOCKING MECHANISMS     |
                                     +--------------------------+
                                     | * Row Locks (FOR UPDATE) |
                                     | * Table Locks (8 Modes)  |
                                     | * Advisory Locks         |
                                     | * Deadlock Detection     |
                                     +--------------------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    |                                                           |
                    v                                                           v
       +-------------------------+                                 +-------------------------+
       |   STORAGE MAINTENANCE   |                                 | OBSERVABILITY & METRICS |
       +-------------------------+                                 +-------------------------+
       | * XID Wraparound Limit  |                                 | * pg_locks & Contention |
       | * Freeze Process        |                                 | * pg_stat_activity      |
       | * Autovacuum Tuning     |                                 | * Lock Tree Tracing     |
       +-------------------------+                                 +-------------------------+
```

---

## Seksi 04: Mengapa Relevan
Pada sistem *high-throughput OLTP* (perbankan, e-commerce, *payment gateway*), kegagalan memahami manajemen transaksi menyebabkan dua bencana besar:
1. **Data Corruption & Logical Anomalies:** *Double spending*, *negative inventory balance*, dan inkonsistensi pembukuan yang timbul akibat race condition dan kesalahan pemilihan level isolasi.
2. **Catastrophic Outages:** *Lock contention cascade* yang menghabiskan *connection pool*, *idle-in-transaction* yang menahan *dead tuples* sehingga memicu *table bloat*, hingga *emergency shutdown* akibat *Transaction ID Wraparound* ($2^{31}$ transaksi tanpa vacuum).

Penguasaan MVCC, Lock Hierarchy, dan SSI (*Serializable Snapshot Isolation*) membedakan Junior DBA dengan Principal Database Engineer yang mampu mengonfigurasi database untuk memproses ratusan ribu Transaksi per Detik (TPS) dengan jaminan ACID mutlak.

---

## Seksi 05: Anatomi Konsep Inti

### 1. Header Tuple dan MVCC Storage Engine
PostgreSQL tidak menimpa (*in-place update*) baris data lama saat operasi `UPDATE` atau `DELETE`. Baris baru dibuat, dan baris lama ditandai sebagai *dead tuple*. Setiap *physical tuple* pada *heap page* memuat metadata header 23-byte:
* **`xmin` (32-bit/64-bit):** Transaction ID (TXID) yang menyisipkan (*INSERT*) tuple.
* **`xmax` (32-bit/64-bit):** TXID yang menghapus (*DELETE*) atau memperbarui (*UPDATE*) tuple. Bernilai `0` jika tuple aktif dan belum dimodifikasi.
* **`t_ctid` (ItemPointerData - 6 byte):** Menunjuk ke lokasi fisik tuple saat ini (Block Number, Offset Number). Jika tuple di-update, `t_ctid` pada tuple lama akan menunjuk ke lokasi tuple versi baru.
* **`t_infomask` (16-bit):** Bit-flags status transaksi (`HEAP_XMIN_COMMITTED`, `HEAP_XMIN_INVALID`, `HEAP_XMAX_COMMITTED`, `HEAP_XMAX_IS_EXCL_LOCK`). Digunakan untuk *fast-path visibility checks* tanpa harus selalu membaca *Commit Log* (`pg_xact`).

### 2. Struktur Snapshot Visibilitas
Snapshot didefinisikan dalam format: `Xmin:Xmax:xip_list`
* **`Xmin`:** TXID aktif terendah saat snapshot diambil. Semua transaksi dengan $\text{TXID} < Xmin$ telah selesai (*committed*) dan terlihat oleh snapshot.
* **`Xmax`:** TXID pertama yang belum ditetapkan (*unassigned*). Semua transaksi dengan $\text{TXID} \ge Xmax$ tidak terlihat oleh snapshot.
* **`xip_list`:** Daftar TXID aktif yang sedang berjalan (*in-flight*) di antara $Xmin$ dan $Xmax$ saat snapshot dibentuk.

### 3. Matriks ANSI SQL Isolation Levels vs PostgreSQL Engine
PostgreSQL mengimplementasikan 3 level isolasi riil (Read Uncommitted diperlakukan sama dengan Read Committed):

| Isolation Level | Dirty Read ($P_1$) | Non-Repeatable Read ($P_2$) | Phantom Read ($P_3$) | Serialization Anomaly |
| :--- | :--- | :--- | :--- | :--- |
| **Read Committed** | Not Possible | **Possible** | **Possible** | **Possible** |
| **Repeatable Read** | Not Possible | Not Possible | Not Possible* | **Possible** |
| **Serializable** | Not Possible | Not Possible | Not Possible | Not Possible |

*\*PostgreSQL mengimplementasikan Snapshot Isolation untuk Repeatable Read sehingga mencegah Phantom Read standar.*

---

## Seksi 06: Panduan Implementasi Step-by-Step

### Skenario: Konfigurasi Parameter Runtime & Pengujian Isolasi Transaksi

#### Langkah 1: Optimasi Parameter Transaksi pada `postgresql.conf`
Atur parameter global untuk mencegah *hung locks* dan memitigasi kegagalan fatal:
```sql
-- Set timeout global untuk mendeteksi deadlock dan lock waiting
ALTER SYSTEM SET deadlock_timeout = '1s';
ALTER SYSTEM SET lock_timeout = '5s';
ALTER SYSTEM SET statement_timeout = '30s';
ALTER SYSTEM SET idle_in_transaction_session_timeout = '60s';

-- Muat ulang konfigurasi
SELECT pg_reload_conf();
```

#### Langkah 2: Inspeksi Tuple Header dengan Ekstensi `pageinspect`
Instal ekstensi sistem untuk melihat cara kerja `xmin` dan `xmax` langsung dari disk:
```sql
CREATE EXTENSION IF NOT EXISTS pageinspect;

CREATE TABLE accounts_demo (
    id SERIAL PRIMARY KEY,
    owner_name VARCHAR(50),
    balance NUMERIC(15,2)
);

INSERT INTO accounts_demo (owner_name, balance) VALUES ('Alice', 1000.00);
```

Periksa informasi *heap page*:
```sql
SELECT 
    lp as tuple_offset,
    t_xmin as xmin,
    t_xmax as xmax,
    t_field3 as xmin_epoch_or_status,
    t_ctid as ctid,
    t_data
FROM heap_page_items(get_raw_page('accounts_demo', 0));
```

#### Langkah 3: Eksekusi Update & Evaluasi Mutasi `t_ctid`
```sql
UPDATE accounts_demo SET balance = 1250.00 WHERE id = 1;

-- Cek kembali heap page:
SELECT 
    lp, t_xmin, t_xmax, t_ctid 
FROM heap_page_items(get_raw_page('accounts_demo', 0));
```
*Hasil:* Tuple offset 1 memiliki `t_xmax` terisi TXID update dan `t_ctid` menunjuk ke `(0,2)`. Tuple offset 2 adalah versi baru dengan `t_xmin` setara TXID update tersebut.

---

## Seksi 07: Contoh Kasus Sederhana

### Mengamati Write Skew pada Repeatable Read vs Serializable
*Write Skew* adalah anomali di mana dua transaksi membaca state yang sama, membuat keputusan independen yang valid secara lokal, namun melanggar batasan konsistensi global saat di-commit bersamaan.

```sql
-- Setup tabel on-call dokter
CREATE TABLE doctor_on_call (
    id SERIAL PRIMARY KEY,
    doctor_name TEXT NOT NULL,
    on_duty BOOLEAN NOT NULL
);

INSERT INTO doctor_on_call (doctor_name, on_duty) VALUES ('Dr. Bob', true), ('Dr. Carol', true);
```

#### Skenario Eksekusi Konkuren:
*Kondisi bisnis:* Minimal harus ada 1 dokter yang bertugas (`on_duty = true`).

```sql
-- Sesi 1 (Dr. Bob ingin cuti)
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT count(*) FROM doctor_on_call WHERE on_duty = true; -- Return 2
UPDATE doctor_on_call SET on_duty = false WHERE doctor_name = 'Dr. Bob';

-- Sesi 2 (Dr. Carol ingin cuti bersamaan)
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT count(*) FROM doctor_on_call WHERE on_duty = true; -- Return 2
UPDATE doctor_on_call SET on_duty = false WHERE doctor_name = 'Dr. Carol';

-- Sesi 1 Commit:
COMMIT; -- Berhasil

-- Sesi 2 Commit:
COMMIT; -- Berhasil!
```
*Hasil:* Total dokter aktif = 0. Inkonsistensi data terjadi di level `REPEATABLE READ`.

#### Solusi via SSI (Serializable Snapshot Isolation):
Ulangi skenario di atas dengan level isolasi `SERIALIZABLE`.
*Hasil:* Sesi 2 saat melakukan `COMMIT` akan di-abort secara otomatis oleh engine dengan error:
`ERROR: 40001: could not serialize access due to read/write dependencies among transactions`.

---

## Seksi 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah arsitektur *Double-Entry Ledger Engine* yang dirancang tahan terhadap *race conditions*, *deadlocks*, dan menjamin integritas finansial penuh menggunakan *Pessimistic Locking dengan Row-level Granularity*.

```sql
-- ============================================================================
-- PRODUCTION-GRADE FINANCLAL LEDGER DDL & CONCURRENCY SAFE TRANSFER ENGINE
-- ============================================================================

CREATE TABLE ledger_accounts (
    account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_number VARCHAR(32) NOT NULL UNIQUE,
    current_balance NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    currency VARCHAR(3) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ck_balance_non_negative CHECK (current_balance >= 0.0000)
);

CREATE TABLE ledger_journal_entries (
    journal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_account_id UUID NOT NULL REFERENCES ledger_accounts(account_id),
    destination_account_id UUID NOT NULL REFERENCES ledger_accounts(account_id),
    amount NUMERIC(18, 4) NOT NULL,
    idempotency_key VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT ck_positive_amount CHECK (amount > 0.0000),
    CONSTRAINT ck_different_accounts CHECK (source_account_id <> destination_account_id)
);

-- ============================================================================
-- STORED PROCEDURE: Thread-Safe Fund Transfer with Deterministic Lock Sorting
-- ============================================================================

CREATE OR REPLACE PROCEDURE sp_execute_transfer(
    p_source_id UUID,
    p_dest_id UUID,
    p_amount NUMERIC(18, 4),
    p_idempotency_key VARCHAR(64),
    INOUT p_journal_id UUID DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_first_id UUID;
    v_second_id UUID;
    v_src_bal NUMERIC(18, 4);
    v_dst_bal NUMERIC(18, 4);
BEGIN
    -- 1. Validasi Idempotensi Transaksi
    SELECT journal_id INTO p_journal_id
    FROM ledger_journal_entries
    WHERE idempotency_key = p_idempotency_key;

    IF FOUND THEN
        RAISE NOTICE 'Transkasi terdeteksi duplikat (idempotent replay): %', p_idempotency_key;
        RETURN;
    END IF;

    -- 2. Deadlock Avoidance: Urutkan Account ID secara Leksikografis
    -- Menjamin Resource Locking Hierarchy selalu identik di seluruh worker pool
    IF p_source_id < p_dest_id THEN
        v_first_id := p_source_id;
        v_second_id := p_dest_id;
    ELSE
        v_first_id := p_dest_id;
        v_second_id := p_source_id;
    END IF;

    -- 3. Eksplisit Row-Level Locking (Pessimistic Locking)
    PERFORM 1 FROM ledger_accounts 
    WHERE account_id = v_first_id 
    FOR UPDATE;

    PERFORM 1 FROM ledger_accounts 
    WHERE account_id = v_second_id 
    FOR UPDATE;

    -- 4. Verifikasi Status & Saldo Sumber
    SELECT current_balance INTO v_src_bal
    FROM ledger_accounts
    WHERE account_id = p_source_id AND is_active = true;

    IF v_src_bal IS NULL THEN
        RAISE EXCEPTION 'ERR_ACC_INVALID: Akun sumber tidak aktif atau tidak ditemukan'
            USING ERRCODE = 'P0002';
    END IF;

    IF v_src_bal < p_amount THEN
        RAISE EXCEPTION 'ERR_INSUFFICIENT_FUNDS: Saldo tidak mencukupi. Saldo saat ini: %', v_src_bal
            USING ERRCODE = '23514'; -- Check violation domain
    END IF;

    -- 5. Mutasi Saldo Atomik
    UPDATE ledger_accounts
    SET current_balance = current_balance - p_amount
    WHERE account_id = p_source_id;

    UPDATE ledger_accounts
    SET current_balance = current_balance + p_amount
    WHERE account_id = p_dest_id;

    -- 6. Insert Audit Journal Log
    p_journal_id := gen_random_uuid();
    INSERT INTO ledger_journal_entries (
        journal_id,
        source_account_id,
        destination_account_id,
        amount,
        idempotency_key,
        created_at
    ) VALUES (
        p_journal_id,
        p_source_id,
        p_dest_id,
        p_amount,
        p_idempotency_key,
        clock_timestamp()
    );

    -- Komit transaksi dilakukan oleh runtime caller atau dihandle atomik per scope block
END;
$$;
```

---

## Seksi 09: Diagram Alur Kerja ASCII

### Alur Resolusi Locking Deterministic pada `sp_execute_transfer`
```
   Transaction Worker 1 (A -> B)             Transaction Worker 2 (B -> A)
  +-------------------------------+         +-------------------------------+
  | Source: Acc A, Target: Acc B  |         | Source: Acc B, Target: Acc A  |
  +-------------------------------+         +-------------------------------+
                 |                                          |
                 v                                          v
  +-------------------------------+         +-------------------------------+
  |  Sort IDs: Min(A,B) -> Lock A |         |  Sort IDs: Min(A,B) -> Lock A |
  +-------------------------------+         +-------------------------------+
                 |                                          |
                 | Acquire Lock Acc A                      | Wait for Acc A
                 v                                          | (BLOCKED)
  +-------------------------------+                         |
  |  Lock Acc A ACQUIRED          |                         |
  |  Sort IDs: Max(A,B) -> Lock B |                         |
  +-------------------------------+                         |
                 |                                          |
                 | Acquire Lock Acc B                       |
                 v                                          |
  +-------------------------------+                         |
  |  Lock Acc B ACQUIRED          |                         |
  |  Mutasi Saldo A & B           |                         |
  |  COMMIT Transaksi             |                         |
  +-------------------------------+                         |
                 |                                          |
                 | Releases Lock A & B                      |
                 v                                          v
          [DONE SUCCESS]                     [Unblocked: Acquire Lock A]
                                                            |
                                                            v
                                             +-------------------------------+
                                             |  Lock Acc B ACQUIRED          |
                                             |  Mutasi Saldo B & A           |
                                             |  COMMIT Transaksi             |
                                             +-------------------------------+
                                                            |
                                                            v
                                                     [DONE SUCCESS]
```

---

## Seksi 10: Analisis Trade-offs

| Strategi Concurrency | Latency Impact | Concurrency / Scalability | Kompleksitas Implementasi | Failure Mode |
| :--- | :--- | :--- | :--- | :--- |
| **Optimistic (SSI)** | Rendah saat contention rendah; Sangat Tinggi saat contention tinggi. | Sangat Tinggi pada Read-Heavy, Rendah pada High-Write Conflict. | Rendah di SQL, Tinggi di App Layer (Harus ada retry loop logic). | `40001 (Serialization Failure)` - Transaksi dibatalkan massal. |
| **Pessimistic Locking (`FOR UPDATE`)** | Konstan; Tambahan *locking wait time* saat *row contention*. | Sedang. Terbatas pada throughput antrian baris yang sama. | Sedang. Membutuhkan sorting deterministik untuk anti-deadlock. | `55P03 (Lock Not Available)` atau `Deadlock Detected (40P01)`. |
| **Advisory Locks** | Sangat Rendah (operasi di memori hash table PG). | Tinggi (aplikasi mengontrol semantik penguncian). | Tinggi. Beban pengelolaan lock release manual berada di developer. | Resource leak jika koneksi tertahan di pool (*unreleased locks*). |

---

## Seksi 11: Best Practices & Antipatterns

### Best Practices
1. **Urutkan Mutasi Data Secara Deterministik:** Selalu lakukan penguncian baris (`FOR UPDATE`) atau `UPDATE` tabel jamak dengan urutan Primary Key yang terurut (`ORDER BY id ASC`).
2. **Kecilkan Transaction Boundaries:** Jangan lakukan pemanggilan API jaringan eksternal, hashing bcrypt yang berat, atau proses parsing file di dalam blok transaksi SQL `BEGIN ... COMMIT`.
3. **Konfigurasi Timeout Berlapis:** Selalu terapkan kombinasi `statement_timeout`, `lock_timeout`, dan `idle_in_transaction_session_timeout` untuk mematikan transaksi *zombie*.

### Antipatterns
1. **The "SELECT then UPDATE" Race:**
   * *Buruk:* `SELECT balance FROM acc WHERE id=1;` lalu di aplikasi dicek, kemudian `UPDATE acc SET balance = ...`. (Memicu *Lost Update*).
   * *Benar:* `UPDATE acc SET balance = balance - 100 WHERE id = 1 AND balance >= 100;` atau gunakan `SELECT FOR UPDATE`.
2. **Long-Running Transactions Over Analytic Queries in OLTP:**
   Menjalankan query laporan selama 4 jam di database produksi memblokir pembersihan vacuum untuk semua *dead tuples* yang dibuat setelah transaksi analitik tersebut dimulai.

---

## Seksi 12: Security Hardening

```sql
-- 1. Batasi privilege eksekusi prosedur transfer hanya untuk technical application role
REVOKE ALL ON PROCEDURE sp_execute_transfer(UUID, UUID, NUMERIC, VARCHAR, UUID) FROM PUBLIC;
GRANT EXECUTE ON PROCEDURE sp_execute_transfer(UUID, UUID, NUMERIC, VARCHAR, UUID) TO svc_payment_engine;

-- 2. Terapkan Row-Level Security (RLS) untuk isolasi penyewa (Multi-Tenant Lock Isolation)
ALTER TABLE ledger_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY account_tenant_isolation_policy ON ledger_accounts
    FOR ALL
    TO application_user
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

-- 3. Audit Log Trigger untuk memonitor perubahan state yang tidak diotorisasi
CREATE OR REPLACE FUNCTION trg_audit_critical_locks()
RETURNS event_trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE LOG 'DDL Lock Escalation Detected by Session %: Event %', pg_backend_pid(), tg_tag;
END;
$$;
```

---

## Seksi 13: Observabilitas & Debugging

### Query 1: Visualisasi Pohon Lock Contention (Lock Dependency Tree)
Mengidentifikasi *Root Blocker* yang menyebabkan antrian koneksi:

```sql
SELECT
    blocked_locks.pid     AS blocked_pid,
    blocked_activity.usename  AS blocked_user,
    blocking_locks.pid    AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query    AS blocked_statement,
    blocking_activity.query   AS blocking_statement,
    now() - blocked_activity.query_start AS waiting_duration
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
    AND blocking_locks.classid