# Modul 01: Transactions, Concurrency, Locking, & MVCC

---

## 01: IDENTITAS MODUL

*   **Track:** Backend & Database Engineering
*   **Kategori:** 04-Backend-and-Database
*   **Topik:** SQL (Structured Query Language)
*   **Bab:** 09 (Data Integrity, Concurrency, & Performance Internals)
*   **Modul:** 01 (Transactions, Concurrency, Locking, & Multi-Version Concurrency Control)
*   **Tingkat Kesulitan:** Advanced / Production-Grade
*   **Prasyarat:** Pemahaman DDL/DML, Relational Schema Design, Dasar Indeks Relasional (B-Tree), Relational Algebra.
*   **Target Engine:** PostgreSQL 15+ (dengan komparasi arsitektural ke MySQL 8.0/InnoDB).

---

## 02: LEARNING OBJECTIVES

1.  **Menguasai Sifat ACID Relasional:** Menganalisis dan membuktikan sifat *Atomicity, Consistency, Isolation,* dan *Durability* hingga ke level mekanika Write-Ahead Logging (WAL) dan buffer pool manager.
2.  **Mendiagnosis Anomali Konkurensi ANSI SQL:** Mereproduksi dan memitigasi anomali *Dirty Read*, *Non-repeatable Read*, *Phantom Read*, *Serialization Anomaly*, dan *Write Skew*.
3.  **Membedah Engine MVCC Internals:** Memahami arsitektur *tuple versioning* (`xmin`, `xmax`, `cmin`, `cmax`, *vacuuming/bloat* di PostgreSQL vs *undo logs/rollback segments* di InnoDB).
4.  **Menerapkan Strategi Locking Granular:** Mengimplementasikan *Pessimistic Locking* (`SELECT FOR UPDATE`, `FOR SHARE`, `NOWAIT`, `SKIP LOCKED`) dan *Optimistic Concurrency Control* (OCC) dengan verifikasi berbasis versi/token.
5.  **Mencegah dan Menangani Deadlock:** Mengidentifikasi pola siklus *lock dependency graph* dan merancang skema transaksi deterministik untuk meminimalkan *deadlock frequency*.

---

## 03: CONCEPT MAP DIAGRAM

```
                       [CLIENT TRANSACTIONS]
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
          [Pessimistic Locks]       [Optimistic Concurrency]
         (FOR UPDATE / SHARE)       (Version Check/CAS)
                    │                         │
                    └────────────┬────────────┘
                                 ▼
                     [TRANSACTION MANAGER]
           (Coordinates Isolation & Snapshot Metadata)
                                 │
       ┌─────────────────────────┼─────────────────────────┐
       ▼                         ▼                         ▼
[ISOLATION LEVELS]       [CONCURRENCY CONTROL]       [RECOVERY SYSTEM]
  ├─ Read Uncommitted      ├─ MVCC Engine             ├─ WAL Engine
  ├─ Read Committed        │   ├─ Tuple Headers       │   └─ Append-Only Log
  ├─ Repeatable Read       │   │  (xmin, xmax)        │
  └─ Serializable          │   ├─ Undo Logs (InnoDB)  └─ Buffer Pool
                           │   └─ VACUUM (PG)             └─ Dirty Pages
                           └─ Lock Manager
                               ├─ Row Locks
                               ├─ Table Locks
                               └─ Predicate Locks
```

---

## 04: MENGAPA RELEVAN

Dalam sistem monolitik maupun *microservices distributed data stores*, konkurensi adalah akar dari *race conditions*, inkonsistensi finansial (*double-spending*), dan degradasi latensi akibat *lock contention*.

*   **Penyebab Kegagalan Finansial:** Kesalahan isolasi transaksi dapat mengakibatkan saldo akun berkurang secara tidak akurat saat dieksekusi secara simultan.
*   **Degradasi Throughput:** Pemilihan isolasi `SERIALIZABLE` atau *pessimistic lock* yang ceroboh pada entitas dengan lalu lintas tinggi (*hot-spot rows*) dapat mengunci *worker threads*, menyebabkan antrean koneksi penuh (*connection pool exhaustion*).
*   **Data Corruption Silang Read-Write:** Kegagalan memahami MVCC menyebabkan *table bloat* masif, *sub-optimal query execution plans*, serta kesalahan logika akibat *phantom reads* dan *write-skew anomalies*.

---

## 05: ANATOMI KONSEP INTI

### 1. Prinsip Dasar ACID & Engine Internals

*   **Atomicity:** Transaksi dieksekusi dengan prinsip *all-or-nothing*. Dikelola menggunakan *Write-Ahead Logging* (WAL) atau *Undo Logging*. Jika transaksi *aborted*, mesin database memutar balik (*rollback*) modifikasi menggunakan log tersebut.
*   **Consistency:** Memastikan integritas data tetap valid sesuai *constraints* (`CHECK`, `FOREIGN KEY`, `UNIQUE`), *triggers*, dan *schema invariants* sebelum dan sesudah transaksi.
*   **Isolation:** Mengatur bagaimana perubahan parsial dari transaksi yang berjalan bersamaan terlihat oleh transaksi lain.
*   **Durability:** Data yang telah di-*commit* dijamin tetap tersimpan secara permanen, bahkan jika terjadi *system crash*, melalui mekanisme `fsync()` WAL ke media penyimpanan non-volatile sebelum transaksi dinyatakan sukses ke klien.

### 2. ANSI Isolation Levels vs. Real-World Anomalies

| Isolation Level | Dirty Read | Non-Repeatable Read | Phantom Read | Serialization Anomaly / Write Skew |
| :--- | :--- | :--- | :--- | :--- |
| **Read Uncommitted** | Ya | Ya | Ya | Ya |
| **Read Committed** | Tidak | Ya | Ya | Ya |
| **Repeatable Read** | Tidak | Tidak | Tidak (di PG MVCC) / Ya (ANSI) | Ya |
| **Serializable** | Tidak | Tidak | Tidak | Tidak |

*   **Dirty Read ($G_1$):** Membaca mutasi data yang belum di-*commit* oleh transaksi lain yang kemudian melakukan *rollback*.
*   **Non-Repeatable Read ($G_{2a}$):** Transaksi membaca ulang baris yang sama dan menemukan modifikasi nilai yang telah di-*commit* oleh transaksi lain.
*   **Phantom Read ($A3$):** Transaksi mengeksekusi *range query* berulang, namun jumlah baris bertambah/berkurang karena ada transaksi lain yang melakukan `INSERT`/`DELETE` dan *commit*.
*   **Write Skew ($A5B$):** Terjadi ketika dua transaksi membaca set data overlapping yang sama, lalu masing-masing memodifikasi data terpisah yang saling bergantung, melanggar *invariant* global secara bersamaan.

### 3. MVCC Internals: PostgreSQL vs MySQL InnoDB

```
PostgreSQL (Append-Only Tuples):
[Heap Page] ──────> [Tuple v1 (xmin: 100, xmax: 101)] -> Outdated
                    [Tuple v2 (xmin: 101, xmax: 0)]   -> Current Active

MySQL InnoDB (In-Place + Undo Space):
[Clustered Index] -> [Row Current Data] ──ptr──> [Undo Segment] -> [v1 Data]
```

*   **PostgreSQL:** Setiap `UPDATE` menulis *tuple* baru (*dead tuple* lama tetap berada di disk). Kolom metadata tersembunyi `xmin` (ID transaksi pembuat) dan `xmax` (ID transaksi penghapus/pembaru) menentukan visibilitas baris melalui *Active Transaction Snapshot*. Diperlukan proses `VACUUM` untuk mereklamasi ruang penyimpanan.
*   **MySQL (InnoDB):** Modifikasi dilakukan langsung di tempat (*in-place update* pada *clustered index*). Versi baris lama dipindahkan ke struktur *Rollback Segment / Undo Log*. *Garbage collection* dilakukan oleh proses *Purge Threads*.

### 4. Locking Hierarchy & Modes

*   **Row-Level Locks:**
    *   `FOR UPDATE` (Exclusive): Mencegah pembacaan dengan *lock* dan modifikasi dari transaksi lain.
    *   `FOR NO KEY UPDATE`: Mencegah modifikasi data baris, tetapi mengizinkan *lock* lain yang tidak mengubah *foreign key*.
    *   `FOR SHARE` (Shared): Mengizinkan pembacaan bersama, tetapi memblokir eksklusivitas modifikasi.
    *   `FOR KEY SHARE`: Mengizinkan modifikasi non-kunci primer/unik.
*   **Table-Level Intent Locks:** `ACCESS SHARE`, `ROW SHARE`, `ROW EXCLUSIVE`, `SHARE UPDATE EXCLUSIVE`, `SHARE`, `SHARE ROW EXCLUSIVE`, `EXCLUSIVE`, `ACCESS EXCLUSIVE`.
*   **Lock Options:**
    *   `NOWAIT`: Gagal seketika (*fail-fast*) dengan *error code* `55P03` jika baris sedang terkunci.
    *   `SKIP LOCKED`: Melewati baris yang terkunci, ideal untuk *high-throughput distributed work queues*.

---

## 06: PANDUAN IMPLEMENTASI STEP-BY-STEP

### Skenario: Menghindari Double-Spending pada Dompet Digital

```
Session A (Transfer $50)                  Session B (Transfer $70)
        │                                         │
        ├─ BEGIN                                  ├─ BEGIN
        │                                         │
        ├─ SELECT balance FROM wallet             │
        │  WHERE id = 1 FOR UPDATE;               │
        │  (Acquires Row Exclusive Lock)          │
        │                                         ├─ SELECT balance FROM wallet
        │                                         │  WHERE id = 1 FOR UPDATE;
        │                                         │  (BLOCKED - Waiting for A)
        ├─ UPDATE wallet SET balance = balance-50 │
        │  WHERE id = 1;                          │
        │                                         │
        ├─ COMMIT; ───────────────────────────────┼─> (Unblocked)
        │  (Releases Lock)                        ├─ Reads updated balance ($50)
        │                                         ├─ Evaluate: ($50 < $70) -> Insufficient
        │                                         ├─ ROLLBACK;
```

#### Langkah 1: Inisialisasi Skema Isolasi Kuat

```sql
CREATE TABLE accounts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id UUID NOT NULL,
    balance NUMERIC(14, 4) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_non_negative_balance CHECK (balance >= 0)
);

CREATE TABLE ledger_entries (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(id),
    amount NUMERIC(14, 4) NOT NULL,
    entry_type VARCHAR(10) NOT NULL CHECK (entry_type IN ('DEBIT', 'CREDIT')),
    reference_id UUID NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### Langkah 2: Eksekusi Transaksi dengan Pessimistic Concurrency

```sql
-- Dijalankan pada Connection 1
BEGIN ISOLATION LEVEL READ COMMITTED;

-- Ambil baris dengan Exclusive Row Lock
SELECT id, balance 
FROM accounts 
WHERE id = 101 
FOR UPDATE;

-- Validasi pada level aplikasi: Pastikan (balance - 500.00) >= 0

INSERT INTO ledger_entries (account_id, amount, entry_type, reference_id)
VALUES (101, 500.00, 'DEBIT', 'e0c4b267-33ee-40ef-8e8f-4aa719b02bb1');

UPDATE accounts 
SET balance = balance - 500.00, 
    updated_at = NOW() 
WHERE id = 101;

COMMIT;
```

---

## 07: CONTOH KASUS SEDERHANA

### Optimistic Concurrency Control (OCC) Menggunakan Conditional Check

OCC tidak mengunci baris saat proses pembacaan data, melainkan memvalidasi status versi baris pada tahap mutasi akhir (*Compare-and-Swap pattern*).

```sql
-- Client membaca data awal
-- State: id = 101, balance = 1000.00, version = 4
SELECT id, balance, version 
FROM accounts 
WHERE id = 101;

-- Client memproses kalkulasi lokal (1000.00 - 200.00 = 800.00)

-- Client mengeksekusi mutasi bersyarat
UPDATE accounts
SET balance = 800.00,
    version = version + 1,
    updated_at = NOW()
WHERE id = 101 
  AND version = 4;

-- Verifikasi output execution metadata:
-- Jika Rows Affected == 1: Mutasi Berhasil (Atomic Swap Berhasil)
-- Jika Rows Affected == 0: Konflik Konkurensi (Data telah diubah oleh transaksi lain). Aplikasi wajib Rollback & Retry.
```

---

## 08: IMPLEMENTASI PRODUCTION-GRADE

Berikut adalah implementasi fungsi transfer saldo antar akun perbankan yang aman dari *deadlock* (*deterministic lock sorting*), kebal terhadap anomali konkurensi, dan memiliki idempotensi transaksi.

```sql
CREATE OR REPLACE FUNCTION transfer_funds_atomic(
    p_sender_id BIGINT,
    p_receiver_id BIGINT,
    p_amount NUMERIC(14, 4),
    p_reference_id UUID
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_first_lock BIGINT;
    v_second_lock BIGINT;
    v_sender_balance NUMERIC(14, 4);
    v_receiver_balance NUMERIC(14, 4);
    v_audit_id BIGINT;
BEGIN
    -- Validasi Input Invarian
    IF p_sender_id = p_receiver_id THEN
        RAISE EXCEPTION 'Sender and Receiver must be distinct accounts' 
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    IF p_amount <= 0 THEN
        RAISE EXCEPTION 'Transfer amount must be strictly positive' 
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    -- PENCEGAHAN DEADLOCK: Kunci baris dengan urutan ID yang terurut secara deterministik
    IF p_sender_id < p_receiver_id THEN
        v_first_lock  := p_sender_id;
        v_second_lock := p_receiver_id;
    ELSE
        v_first_lock  := p_receiver_id;
        v_second_lock := p_sender_id;
    END IF;

    -- Akuisisi Kunci Deterministik
    PERFORM 1 FROM accounts WHERE id = v_first_lock FOR UPDATE;
    PERFORM 1 FROM accounts WHERE id = v_second_lock FOR UPDATE;

    -- Periksa Saldo Pengirim
    SELECT balance INTO v_sender_balance
    FROM accounts
    WHERE id = p_sender_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Sender account does not exist' USING ERRCODE = 'data_exception';
    END IF;

    IF v_sender_balance < p_amount THEN
        RAISE EXCEPTION 'Insufficient balance: available %, requested %', v_sender_balance, p_amount
            USING ERRCODE = 'check_violation';
    END IF;

    -- Eksekusi Debet Pengirim
    UPDATE accounts 
    SET balance = balance - p_amount,
        version = version + 1,
        updated_at = NOW()
    WHERE id = p_sender_id;

    -- Eksekusi Kredit Penerima
    UPDATE accounts 
    SET balance = balance + p_amount,
        version = version + 1,
        updated_at = NOW()
    WHERE id = p_receiver_id;

    -- Catat Ledger Entries Idempoten
    INSERT INTO ledger_entries (account_id, amount, entry_type, reference_id)
    VALUES 
        (p_sender_id, -p_amount, 'DEBIT', p_reference_id),
        (p_receiver_id, p_amount, 'CREDIT', p_reference_id);

    RETURN jsonb_build_object(
        'status', 'SUCCESS',
        'reference_id', p_reference_id,
        'sender_id', p_sender_id,
        'receiver_id', p_receiver_id,
        'transferred_amount', p_amount
    );
END;
$$;
```

---

## 09: DIAGRAM ALUR KERJA

```
                          [Mulai: transfer_funds_atomic]
                                         │
                         [Validasi Invarian Nilai Argumen]
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
            (Argumen Valid)                          (Argumen Tidak Valid)
                    │                                         │
         [Urutkan Kunci Mutex]                                ▼
      (First: Min, Second: Max)                       [Raise Exception]
                    │                                         │
         [Akuisisi FOR UPDATE]                                ▼
        (Secara Deterministik)                            [Aborted]
                    │
         [Evaluasi Kecukupan Saldo]
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
    (Saldo Cukup)     (Saldo Tidak Cukup)
         │                     │
  [Update Balances]            ▼
  [Insert Ledger]      [Raise Exception]
         │                     │
         ▼                     ▼
     [COMMIT]              [Aborted]
```

---

## 10: ANALISIS TRADE-OFFS

| Strategi | Keuntungan | Kerugian | Skenario Penggunaan |
| :--- | :--- | :--- | :--- |
| **Pessimistic Locking (`FOR UPDATE`)** | Menjamin integritas data secara absolut; tidak membuang komputasi akibat retry loop. | Berisiko menurunkan konkurensi; rentan *deadlock* jika urutan kunci tidak konsisten. | Sistem perbankan inti, manajemen inventaris stok terbatas (*flash sale*). |
| **Optimistic Concurrency (OCC)** | Non-blocking saat membaca; konkurensi throughput sangat tinggi pada rasio baca tinggi. | Overhead performa tinggi jika tingkat konflik tulis tinggi (*waste of CPU on retry*). | Sistem CMS, kolaborasi dokumen, profil pengguna. |
| **Serializable Isolation (SSI)** | Menghapus seluruh anomali logika tanpa perlu *locking* eksplisit secara manual. | Mengorbankan performa; aplikasi wajib menangani kegagalan commit (*serialization failures - 40001*). | Pelaporan keuangan agregat real-time, audit komputasi kompleks. |

---

## 11: BEST PRACTICES & ANTIPATTERNS

### Antipattern: Interaksi I/O Eksternal di Dalam Transaksi Database

```
❌ SALAH:
BEGIN;
SELECT for update...
HTTP POST /api/payment-gateway (Jaringan Lambat / Timeout)
UPDATE accounts ...
COMMIT;
-- Mengakibatkan Lock Contention masif dan kehabisan Connection Pool.
```

```
✅ BENAR:
HTTP POST /api/payment-gateway (Dapatkan Bukti Transaksi Eksternal)
BEGIN;
SELECT transfer_funds_atomic(...);
COMMIT;
-- Transaksi DB dieksekusi secara mikrodetik tanpa terikat latensi eksternal.
```

### Critical Rules
1.  **Jaga Transaksi Sesingkat Mungkin:** Transaksi terbuka memperlebar masa simpan *lock* dan menunda pembersihan *dead tuples* oleh autovacuum.
2.  **Kunci Selalu dalam Urutan yang Sama:** Selalu terapkan pengurutan kunci deterministik (misalnya, sorting berdasarkan ID asc/desc) untuk mencegah rantai *deadlock*.
3.  **Hindari Membaca Terlalu Banyak Baris dengan Exclusive Lock:** Jangan gunakan `FOR UPDATE` pada *query* pagination besar.

---

## 12: SECURITY HARDENING

1.  **Mitigasi Race-Condition Exploit:** Penyerang sering memanfaatkan konkurensi untuk *double-spend* saldo promo. Terapkan *Unique Constraints* dan isolasi `REPEATABLE READ` / *pessimistic lock* pada verifikasi kupon.
2.  **Batasi Durasi Eksekusi Lock:** Konfigurasikan batas timeout untuk mencegah transaksi menahan kunci selamanya saat koneksi aplikasi terputus:
    ```sql
    SET statement_timeout = '5000ms';
    SET lock_timeout = '2000ms';
    SET idle_in_transaction_session_timeout = '10000ms';
    ```
3.  **Role-Based Security untuk Administrative Locks:** Blokir akses ke fungsi *advisory locks* global atau penguncian tabel secara manual bagi pengguna aplikasi standar.

---

## 13: OBSERVABILITAS & DEBUGGING

### Menemukan Kueri yang Terkunci dan Penyebab Kuncinya (Lock Tree)

```sql
SELECT 
    blocked_locks.pid     AS blocked_pid,
    blocked_activity.usename  AS blocked_user,
    blocking_locks.pid    AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query    AS blocked_statement,
    blocking_activity.query   AS blocking_statement,
    NOW() - blocked_activity.query_start AS waiting_duration
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
    AND blocking_locks