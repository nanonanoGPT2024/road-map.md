# BAB 03: Advanced SQL & Data Modeling
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai arsitektur internal penyimpanan tuple PostgreSQL (*heap layout*, *alignment padding*, *TOAST mechanics*) untuk mendesain skema relasional dengan efisiensi *cache* dan disk optimal.
- Mengimplementasikan partisi deklaratif tingkat lanjut (*Range*, *List*, *Hash*, dan *Multi-level Sub-partitioning*) dengan verifikasi *static* dan *dynamic partition pruning*.
- Menerapkan *Advanced Integrity Constraints*, termasuk *Exclusion Constraints* berbasis ekstensi `btree_gist` untuk penyelesaian anomali temporal/reservasi spasial, serta *Domain Types* dengan validasi regex/aturan bisnis.
- Membangun model data temporal (*Bi-temporal Modeling*: *system period* dan *application period*) guna mendukung audit trail kelas perbankan tanpa merusak performa *point-in-time lookup*.
- Mengoptimalkan struktur data semi-terstruktur (`JSONB`) menggunakan `jsonpath`, teknik indeks `GIN` (`jsonb_ops` vs `jsonb_path_ops`), dan memadukannya dengan *Generated Columns* (Stored).
- Menganalisis dan merekayasa query analitis/rekursif kompleks menggunakan *Common Table Expressions* (CTE) dengan *cycle detection*, serta *Window Functions* dengan *frame specification* tingkat lanjut (`RANGE BETWEEN ...`).

---

### 2. Prerequisite

Peserta wajib memahami materi fondasi berikut:
- Pemahaman solid mengenai arsitektur PostgreSQL: *shared memory*, *process architecture* (*backend*, *wal writer*, *checkpointer*).
- Teori normalisasi database relasional (1NF hingga 3NF/BCNF) dan denormalisasi pragmatis.
- Dasar-dasar SQL DDL, DML, penguncian dasar (*row-level locks*), serta transaksi ACID dan isolasi transaksi (*MVCC*).
- Kemampuan membaca *output* dasar `EXPLAIN ANALYZE` (Seq Scan, Index Scan, Index Only Scan, Nested Loop, Hash Join).

---

### 3. Concept & Internal Architecture

#### 3.1. Heap Tuple Layout, Data Alignment, and Padding
Setiap baris (tuple) dalam PostgreSQL disimpan dalam *heap page* berukuran default 8 KB (`BLCKSZ`). Struktur internal satu tuple terdiri dari:
1. **`HeapTupleHeaderData` (23 bytes minimum, dibulatkan ke 24 bytes)**:
   - `t_xmin` (4 bytes): XID dari transaksi pembuat (*inserting transaction*).
   - `t_xmax` (4 bytes): XID dari transaksi penghapus/pengubah (*deleting/updating transaction*), atau informasi *row-level lock*.
   - `t_cid` / `t_xvac` (4 bytes): *Command Identifier* di dalam transaksi.
   - `t_ctid` (6 bytes, format `ItemPointerData` `[BlockNumber, OffsetNumber]`): Menunjuk ke lokasi fisik tuple terbaru jika baris ini diupdate.
   - `t_infomask2` (2 bytes): Jumlah atribut dan *bit flags* (seperti `HEAP_HOT_UPDATED`).
   - `t_infomask` (2 bytes): Status commit transaksi (`HEAP_XMIN_COMMITTED`, `HEAP_XMAX_INVALID`, dll).
   - `t_hoff` (1 byte): Offset aktual ke awal user data (payload). Minimum 24 bytes, membesar jika ada `NULL` bitmap.
2. **Null Bitmap (Opsional)**:
   - Hadir hanya jika `HEAP_HASNULL` aktif di `infomask`. Ukurannya `CEIL(jumlah_kolom / 8)` byte.
3. **User Data Payload & Data Alignment Padding**:
   - Kompiler C dan CPU modern mewajibkan tipe data tertentu dialokasikan pada alamat memori yang merupakan kelipatan dari ukurannya (*boundary alignment*). PostgreSQL menerapkan arsitektur alignment berikut:
     - `char`: 1-byte alignment.
     - `smallint` (int2): 2-byte alignment.
     - `integer` (int4), `float4`, `date`: 4-byte alignment.
     - `bigint` (int8), `float8`, `timestamp`, `timestamptz`, tipe pointer: 8-byte alignment (pada arsitektur CPU 64-bit).
   - **Padding Waste**: Jika kolom didefinisikan dengan urutan tipe data acak, misalnya `smallint` diikuti `bigint` lalu `smallint`, engine PostgreSQL menyisipkan *padding byte* kosong (overhead 6 bytes setelah `smallint` pertama dan 6 bytes setelah `smallint` kedua). Desain skema yang buruk dapat memboroskan 20% - 40% kapasitas disk dan memori *shared buffers*.

#### 3.2. TOAST (The Oversized-Attribute Storage Technique)
PostgreSQL tidak mengizinkan baris melompati batas blok 8 KB. Jika satu baris melebihi ambang batas `TOAST_TUPLE_THRESHOLD` (default: 2 KB), PostgreSQL mengaktifkan sub-sistem TOAST dengan strategi berikut:
1. **Storage Strategies**:
   - `PLAIN`: Tidak boleh dikompresi, tidak boleh di-out-of-line (misal: tipe numerik primitif).
   - `EXTENDED`: Boleh dikompresi dan boleh dipindahkan ke *out-of-line TOAST table* (default untuk `TEXT`, `BYTEA`, `JSONB`).
   - `EXTERNAL`: Boleh dipindahkan ke luar (*out-of-line*), tetapi dilarang dikompresi (bagus untuk data terkompresi seperti JPEG/PNG atau teks terenkripsi).
   - `MAIN`: Boleh dikompresi di dalam *heap tuple* utama terlebih dahulu; hanya dipindah ke tabel TOAST jika ruang tetap tidak mencukupi.
2. **Chunking Mechanism**:
   - Tabel TOAST membagi data panjang menjadi *chunks* berukuran rata-rata ~2 KB (ditentukan oleh konstanta `TOAST_MAX_CHUNK_SIZE`).
   - *Pointer TOAST* 18-byte disimpan di dalam baris *heap* utama, merujuk ke record-record di tabel TOAST via `toast_relid` dan `chunk_id`.

#### 3.3. Declarative Partitioning & Routing Internals
Partisi PostgreSQL bukan tabel terpisah yang dipersatukan via VIEW, melainkan struktur hierarkis internal:
1. **Partition Root & Partition Descriptors**:
   - Tabel induk (*root*) tidak menyimpan data fisik (`relfilenode` bernilai 0). Ia hanya memiliki definisi metadata dan objek *Partition Descriptor* yang di-cache di shared catalog cache (*relcache*).
2. **Tuple Routing**:
   - Saat DML `INSERT` dieksekusi terhadap tabel induk, PostgreSQL mengevaluasi *Partition Key* terhadap *Partition Bounds* menggunakan *binary search* (pada Partisi Range/List) atau *hashing function* internal `hash_any()` (pada Partisi Hash).
   - Tuple langsung diarahkan dan ditulis ke *leaf partition* yang bersangkutan.
3. **Partition Pruning Engine**:
   - **Static/Compile-time Pruning**: Dilakukan pada fase optimasi query (planning) jika klausa `WHERE` mengandung nilai konstan (misal: `WHERE created_at >= '2025-01-01'`).
   - **Dynamic/Run-time Pruning**: Dilakukan pada fase eksekusi query jika *filter* bergantung pada subquery terparameterisasi, variabel bind (`$1`), atau hasil *Hash Join*.

#### 3.4. Exclusion Constraints Mechanics (`btree_gist`)
- *Unique Constraint* standar hanya mendukung operator kesetaraan (`=`) menggunakan indeks B-Tree standar.
- *Exclusion Constraint* memanfaatkan Generalized Search Tree (GiST). Ekstensi `btree_gist` memungkinkan operator skalar (`=`, `<>`, `<`, `<=`, `>`, `>=`) disandingkan dengan operator range overlaps (`&&`), containment (`@>`), atau adjacency (`-|-`).
- **Mekanisme**: Setiap baris baru diuji terhadap R-Tree/GiST index. Jika ada tuple terindeks lain yang mengevaluasi ekspresi predikat bernilai `TRUE` untuk seluruh operator yang didefinisikan, PostgreSQL membangkitkan exception `exclusion_violation` (SQLSTATE `23P01`) pada level storage engine dengan atomisitas transaksi penuh.

---

### 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan (Business/Engineering Driver) | Apa Risikonya Jika Diabaikan |
| :--- | :--- | :--- |
| **Column Ordering Optimization** | Mengurangi jejak I/O disk dan konsumsi RAM *shared_buffers* secara drastis melalui minimisasi *alignment padding*. | Pemborosan 15-30% kapasitas disk/RAM, throughput I/O turun, buffer cache miss meningkat. |
| **Declarative Partitioning** | Skalabilitas tabel terabyte; memungkinkan penghapusan data instan (`DROP TABLE partisi`) tanpa overhead `VACUUM` dan *table bloat*. | Operasi `DELETE` massal memicu *autovacuum lag*, *transaction ID wraparound risk*, dan degradasi query scan scan secara global. |
| **Exclusion Constraints** | Menjamin integritas absolut untuk domain reservasi, penjadwalan, dan rentang waktu valid tanpa *race condition*. | Kerentanan *double-booking* atau tumpang-tindih data historis; validasi via layer aplikasi pasti jebol saat *concurrency* tinggi. |
| **Bi-temporal Modeling** | Melacak kebenaran faktual (*application time*) bersamaan dengan jejak audit waktu pencatatan sistem (*system time*). | Gagal dalam audit regulasi finansial (SOX, IFRS), hilangnya histori koreksi data retrospektif. |
| **JSONB Path Ops vs Ops** | Menghindari overhead indeks JSONB yang membengkak di tabel bervolume puluhan juta baris. | Ukuran indeks GIN melebihi kapasitas memori; lonjakan latensi DML akibat pembaruan indeks lambat. |

---

### 5. How (Workflow Detail)

```
[Inbound Write Request]
         │
         ▼
[Column Layout Validation & Alignment Packing]
         │ (Mengurangi padding via reorder)
         ▼
[Check Constraint & Domain Validation]
         │
         ▼
[Partition Tuple Routing]
         ├─ Evaluasi Partition Key terhadap Bounds
         └─ Identifikasi Leaf Partition Target
         │
         ▼
[Exclusion Constraint Validation (GiST Lock)]
         ├─ Lookup R-Tree / GiST index
         ├─ Cek tumpang tindih (Overlaps '&&' / Equal '=')
         └─ Conflict Detection:
              ├── Conflict -> Abort (23P01 exclusion_violation)
              └── Safe     -> Lanjut ke Storage Engine
         │
         ▼
[TOAST Subsystem Evaluation]
         ├─ Tuple Size <= 2KB -> Simpan langsung di Heap Page
         └─ Tuple Size > 2KB  -> Compress (lz4/pglz) 
                                   └─ Jika masih > 2KB -> Split & Write ke TOAST Relation
         │
         ▼
[Physical Page Append & WAL Logging]
```

---

### 6. Analogy & Diagram ASCII

#### 6.1. Heap Tuple Memory Layout & Alignment Waste

**Struktur Buruk (Unoptimized Ordering):**
```
Offset: 0B         24B       26B                  32B       36B                  44B
        ┌──────────┬─────────┬────────────────────┬─────────┬────────────────────┐
        │  Header  │ smallint│   PADDING (6B)     │ integer │   PADDING (4B)     │ ...
        │ (24 B)   │ (2 B)   │  [TERBUANG SIA2]   │ (4 B)   │  [TERBUANG SIA2]   │
        └──────────┴─────────┴────────────────────┴─────────┴────────────────────┘
```

**Struktur Baik (Optimized Ordering: 8-byte, 4-byte, 2-byte, 1-byte, varlena):**
```
Offset: 0B         24B                  32B       36B        38B       40B
        ┌──────────┬────────────────────┬─────────┬──────────┬─────────┬─────────┐
        │  Header  │      bigint        │ integer │ smallint │ boolean │  text   │
        │ (24 B)   │      (8 B)         │ (4 B)   │  (2 B)   │  (1 B)  │ (var)   │
        └──────────┴────────────────────┴─────────┴──────────┴─────────┴─────────┘
        *Zero alignment padding bytes wasted!*
```

#### 6.2. Declarative Dynamic Partition Pruning

```
QUERY: SELECT * FROM ledger WHERE tenant_id = 'T001' AND tx_date = CURRENT_DATE;

                [ ledger (Root Table - Relcache) ]
                               │
               ┌───────────────┴───────────────┐
      [ Hash: T001 ]                   [ Hash: T002 ]  <-- Static Pruning: Pruned!
               │
     ┌─────────┴─────────┐
 [ Range: 2025-01 ]  [ Range: 2025-02 ]                <-- Dynamic Pruning: Evaluasi Run-time
         │                   │
      [ SKIP ]          [ SCAN LEAF ] (Hanya 1 leaf partisi yang diakses)
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Efek Column Alignment terhadap Ukuran Disk
Perhatikan perbandingan dua tabel identik yang hanya berbeda urutan deklarasi kolom:

```sql
-- Tabel 1: Urutan Acak / Naif (Banyak Padding)
CREATE TABLE bad_layout (
    col_smallint_1 SMALLINT,    -- 2 bytes
    col_bigint_1   BIGINT,      -- 8 bytes (butuh padding 6 bytes sebelumnya)
    col_smallint_2 SMALLINT,    -- 2 bytes
    col_bigint_2   BIGINT,      -- 8 bytes (butuh padding 6 bytes sebelumnya)
    col_boolean    BOOLEAN      -- 1 byte  (butuh padding 7 bytes di akhir tuple)
);

-- Tabel 2: Urutan Teroptimasi (Desc Size: 8 -> 4 -> 2 -> 1)
CREATE TABLE good_layout (
    col_bigint_1   BIGINT,      -- 8 bytes
    col_bigint_2   BIGINT,      -- 8 bytes
    col_smallint_1 SMALLINT,    -- 2 bytes
    col_smallint_2 SMALLINT,    -- 2 bytes
    col_boolean    BOOLEAN      -- 1 byte (padding minimal di batas 8-byte akhir)
);

-- Insert 1.000.000 data dummy ke masing-masing tabel
INSERT INTO bad_layout 
SELECT 1, 10000000000, 2, 20000000000, true 
FROM generate_series(1, 1000000);

INSERT INTO good_layout 
SELECT 10000000000, 20000000000, 1, 2, true 
FROM generate_series(1, 1000000);

-- Verifikasi Perbedaan Kapasitas Disk
SELECT 
    relname,
    pg_size_pretty(pg_relation_size(relid)) AS data_size,
    pg_relation_size(relid) AS bytes_exact
FROM pg_catalog.pg_statio_user_tables
WHERE relname IN ('bad_layout', 'good_layout');
```
*Hasil di lapangan*: `bad_layout` memakan alokasi ~57 MB, sedangkan `good_layout` hanya memakan ~42 MB. Penghematan ~26% murni dari penataan ulang kolom tanpa kompromi fungsi aplikasi.

#### 7.2. Practical Example: Multi-Level Sub-partitioning & Exclusion Constraints
Implementasi sistem booking perhotelan berskala enterprise dengan partisi berdasarkan wilayah (*List*) lalu kuartal tanggal (*Range*), dilengkapi proteksi *double-booking* menggunakan `EXCLUDE USING gist`.

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Root Table: Multi-level Declarative Partitioning
CREATE TABLE room_reservations (
    reservation_id   BIGINT GENERATED ALWAYS AS IDENTITY,
    region_code      VARCHAR(10) NOT NULL,
    room_id          INTEGER NOT NULL,
    stay_period      DATERANGE NOT NULL,
    tenant_id        UUID NOT NULL,
    guest_meta       JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_cancelled     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (region_code, reservation_id, stay_period)
) PARTITION BY LIST (region_code);

-- Partisi Tingkat 1 (List): Wilayah APAC
CREATE TABLE reservations_apac PARTITION OF room_reservations
    FOR VALUES IN ('APAC-SG', 'APAC-ID', 'APAC-JP')
    PARTITION BY RANGE (stay_period);

-- Partisi Tingkat 2 (Range): Sub-partisi Kuartal 1 Tahun 2025
CREATE TABLE reservations_apac_2025_q1 PARTITION OF reservations_apac
    FOR VALUES FROM ('[2025-01-01, 2025-04-01)')
    TO ('[2025-04-01, 2025-07-01)');

-- Exclusion Constraint: Mencegah overlapping reservation di kamar yang sama
-- Hanya berlaku untuk reservasi aktif (partial index constraint)
ALTER TABLE reservations_apac_2025_q1
ADD CONSTRAINT exclude_overlapping_active_bookings
EXCLUDE USING gist (
    room_id WITH =,
    stay_period WITH &&
) WHERE (is_cancelled IS FALSE);

-- Test Intervensi Integritas Data
-- Entry 1: Sukses
INSERT INTO room_reservations (region_code, room_id, stay_period, tenant_id)
VALUES ('APAC-ID', 101, daterange('2025-01-10', '2025-01-15', '[)'), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11');

-- Entry 2: Konflik tumpang tindih (Harus Ditolak oleh Engine Database)
-- Error: conflicting key value violates exclusion constraint "exclude_overlapping_active_bookings"
INSERT INTO room_reservations (region_code, room_id, stay_period, tenant_id)
VALUES ('APAC-ID', 101, daterange('2025-01-12', '2025-01-18', '[)'), 'b1ffcd88-8d0a-3ef7-aa5c-5aa8bc270a22');
```

---

### 8. Real World Case Study: Financial Multi-Tenant Bi-temporal Ledger

#### 8.1. Problem Statement
Bank digital memproses 40 juta transaksi buku besar (*ledger*) per hari. Mereka menghadapi 3 masalah kritis:
1. **Regulasi Perbankan**: Wajib melacak kapan suatu transaksi berlaku efektif secara finansial (*valid time*) dan kapan transaksi tersebut dicatat/diubah ke dalam sistem komputer (*system/transaction time*). Koreksi retrospektif tidak boleh menimpa data lama.
2. **Kueri Agregasi Real-Time**: Laporan rekonsiliasi harus memindai data hari berjalan secara instan tanpa terhambat oleh data riwayat 5 tahun terakhir.
3. **Pencarian Metadata Fleksibel**: Transaksi membawa metadata JSONB dinamis (kanal pembayaran, rincian chargeback, kode promosi) yang harus dapat dicari secara cepat tanpa degradasi performa I/O.

#### 8.2. Arsitektur Solusi
- **Bi-temporal Structure**: Menggunakan PostgreSQL native *Range Types* (`tstzrange`) dengan *System Period* dan *Application Period*.
- **Declarative Hash + Range Partitioning**: Partisi tingkat pertama menggunakan *Hash* (berdasarkan `tenant_id`) untuk mendistribusikan I/O secara merata, kemudian tingkat kedua menggunakan *Range* (bulanan berbasis `sys_period`).
- **GIN Indexing Khusus**: Menggunakan `jsonb_path_ops` untuk metadata payload JSONB guna menekan ukuran indeks hingga 60% dibanding default `jsonb_ops`.

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Tabel Master Bi-temporal Ledger
CREATE TABLE corporate_ledger (
    ledger_id        UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id        INT NOT NULL,
    account_number   VARCHAR(34) NOT NULL,
    amount           NUMERIC(18, 4) NOT NULL,
    currency         CHAR(3) NOT NULL,
    -- Bi-temporal columns
    valid_period     TSTZRANGE NOT NULL, -- Application time (kapan dana efektif berpindah)
    system_period    TSTZRANGE NOT NULL, -- Transaction time (kapan tercatat di database)
    tx_payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload_hash     TEXT GENERATED ALWAYS AS (tx_payload->>'signature') STORED,
    PRIMARY KEY (tenant_id, ledger_id, system_period)
) PARTITION BY RANGE (system_period);

-- Partisi Bulanan
CREATE TABLE corporate_ledger_2025_m01 PARTITION OF corporate_ledger
    FOR VALUES FROM ('["2025-01-01 00:00:00+00", "2025-02-01 00:00:00+00")');

CREATE TABLE corporate_ledger_2025_m02 PARTITION OF corporate_ledger
    FOR VALUES FROM ('["2025-02-01 00:00:00+00", "2025-03-01 00:00:00+00")');

-- Indeks GIN Optimal untuk Payload JSONB
CREATE INDEX idx_ledger_payload_path_ops ON corporate_ledger_2025_m01 
USING gin (tx_payload jsonb_path_ops);

-- Indeks Bi-temporal GiST untuk query point-in-time
CREATE INDEX idx_ledger_temporal_lookup ON corporate_ledger_2025_m01 
USING gist (account_number, valid_period, system_period);

-- Skenario Koreksi Retrospektif (Audit Trail Bi-temporal Immutability)
-- 1. Transaksi awal masuk
INSERT INTO corporate_ledger (tenant_id, account_number, amount, currency, valid_period, system_period, tx_payload)
VALUES (
    1001, 
    'ACC-ID-9921', 
    1500000.0000, 
    'IDR', 
    tstzrange('2025-01-10 10:00:00+00', 'infinity', '[)'),
    tstzrange('2025-01-10 10:00:02+00', 'infinity', '[)'),
    '{"signature": "a1b2c3d4", "channel": "OPEN_API", "risk_score": 12}'::jsonb
);

-- 2. Ada koreksi nominal transaksi pada 15 Januari untuk pembukuan tgl 10:
-- Alih-alih UPDATE in-place, tutup rentang system_period data lama dan masukkan tuple baru
BEGIN;
  -- Tutup system_period baris lama
  UPDATE corporate_ledger 
  SET system_period = tstzrange(lower(system_period), '2025-01-15 08:30:00+00', '[)')
  WHERE account_number = 'ACC-ID-9921' 
    AND upper_inf(system_period);

  -- Masukkan koreksi dengan system_period aktif baru
  INSERT INTO corporate_ledger (tenant_id, account_number, amount, currency, valid_period, system_period, tx_payload)
  VALUES (
      1001, 
      'ACC-ID-9921', 
      1450000.0000, -- Nilai koreksi
      'IDR', 
      tstzrange('2025-01-10 10:00:00+00', 'infinity', '[)'), -- Tetap berlaku sejak tgl 10
      tstzrange('2025-01-15 08:30:00+00', 'infinity', '[)'), -- Tercatat tgl 15
      '{"signature": "e5f6g7h8", "channel": "MANUAL_ADJUSTMENT", "adjuster": "USR-ADM-01"}'::jsonb
  );
COMMIT;
```

---

### 9. Trade-offs

| Parameter Desain | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Partition Granularity** | Harian (Fine-grained) | Bulanan (Coarse-grained) | Harian: *Pruning* sangat tajam, namun jika partisi > 10.000, konsumsi memory `relcache` membengkak dan waktu planning query melonjak tajam (*catcache overhead*). Bulanan: Manajemen objek database lebih aman, namun *scan* per partisi lebih besar. |
| **GIN Index Format** | `jsonb_ops` | `jsonb_path_ops` | `jsonb_ops` mendukung semua operator (`?`, `?\|`, `?&`, `@>`), namun ukuran indeks 2x-3x lebih besar. `jsonb_path_ops` hanya mendukung operator containment (`@>`), namun indeks jauh lebih kecil dan *build/insert* lebih cepat. |
| **Generated Columns** | `STORED` | Dynamic Expression (View) | `STORED` mempercepat pembacaan data (bisa diindeks B-Tree langsung), namun memakan kapasitas disk dan memperlambat throughput `INSERT`/`UPDATE` karena dihitung saat penulisan. |
| **Integrity Enforcement** | Database Exclusion Constraint | Application-Level Validation Lock | Exclusion Constraint via GiST mutlak aman secara serializable, namun write overhead lebih tinggi karena *tree evaluation*. Application locks (Redis/Distributed) rawan *failure point* terpisah dan inkonsistensi saat *failover*. |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Dynamic Pruning Gagal Akibat Tipe Data Mismatch
*Masalah*: Kolom partisi bertipe `timestamptz`, namun aplikasi memfilter menggunakan fungsi `now()::date` atau variabel string tanpa explicit casting yang konsisten.
*Analisis*: Engine tidak dapat membuktikan kesetaraan range saat compile time, memicu evaluasi fallback ke `Seq Scan` di seluruh partisi.
*Troubleshooting*:
```sql
-- SALAH: Menyebabkan dynamic pruning gagal
EXPLAIN ANALYZE 
SELECT * FROM corporate_ledger WHERE system_period @> now()::text; -- Casting ke text merusak operator containment range

-- BENAR: Explicit typing mempertahankan pruning
EXPLAIN ANALYZE 
SELECT * FROM corporate_ledger WHERE system_period @> CURRENT_TIMESTAMP;
```

#### Mistake 2: Membengkaknya TOAST Akibat Update Kolom Non-TOAST
*Masalah*: Memperbarui kolom kecil (misal: flag `status = 'COMPLETED'`) pada baris yang memiliki kolom JSONB besar (50 KB).
*Analisis*: Secara default, jika tuple baru muat di heap page bersama data terkompresi, *in-line compressed TOAST value* diduplikasi ke baris MVCC baru.
*Troubleshooting*: Atur storage ke `EXTERNAL` atau pecah tabel metadata ke relasi 1:1 terpisah jika kolom status sangat sering berubah dibanding metadatanya.

#### Mistake 3: Deadlock pada Index GiST / Exclusion Constraints
*Masalah*: Aplikasi menembakkan concurrent `INSERT` ke partisi dengan `EXCLUDE USING gist` menggunakan urutan data acak.
*Troubleshooting*:
- Sortir entri di layer aplikasi sebelum melakukan `batch insert`.
- Aktifkan parameter `deadlock_timeout = '100ms'` untuk investigasi di `pg_stat_activity` dan baca log PostgreSQL dengan pattern: `deadlock detected: Process X waits for ExclusiveLock on extension/page`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Data Alignment Structuring**: Susun kolom tabel dari byte terbesar ke terkecil: `UUID`/`bigint`/`timestamptz` (8B) $\to$ `integer`/`date` (4B) $\to$ `smallint` (2B) $\to$ `boolean`/`char` (1B) $\to$ Varlena (`text`/`varchar`/`jsonb`).
- [ ] **Partition Maintenance Strategy**: Pastikan *daemon job* (seperti `pg_partman`) berjalan untuk membuat partisi baru secara otomatis minimal 30 hari ke depan; jangan pernah biarkan partisi default menampung data tak terduga.
- [ ] **Partition Key Stability**: Jangan pernah mengubah (*UPDATE*) kolom yang menjadi `PARTITION KEY` kecuali benar-benar diperlukan, karena PostgreSQL akan mengeksekusi `DELETE` fisik dari satu partisi dan `INSERT` ke partisi lain di balik layar.
- [ ] **B-Tree Gist Extensions**: Pastikan ekstensi `btree_gist` di-deploy di schema `pg_catalog` atau schema ekstensi terdedikasi, bukan schema aplikasi liar.
- [ ] **JSONB Indexing Choice**: Gunakan `USING gin (col jsonb_path_ops)` secara default, kecuali jika membutuhkan pencarian eksistensi key independen (`?`, `?|`).
- [ ] **Constraint Naming Convention**: Berikan nama deterministik pada semua constraint, contoh: `chk_<table>_<kolom>`, `excl_<table>_<deskripsi>`.
- [ ] **Table Bloat Mitigation**: Setel parameter `autovacuum_vacuum_scale_factor = 0.05` dan `autovacuum_vacuum_cost_limit = 2000` untuk partisi-partisi yang menerima write throughput tinggi.

---

### 12. Hands-on Practice

Simpan seluruh skrip praktikum ini di direktori: `hands-on/m02/production_data_modeling.sql`.

```sql
-- ============================================================================
-- HANDS-ON MODULE 02: ADVANCED DATA MODELING & INTERNAL ARCHITECTURE
-- ============================================================================

-- Langkah 1: Eksperimen Data Alignment Internal
CREATE EXTENSION IF NOT EXISTS "pageinspect";

DROP TABLE IF EXISTS layout_unpacked;
DROP TABLE IF EXISTS layout_packed;

CREATE TABLE layout_unpacked (
    c1 SMALLINT,
    c2 BIGINT,
    c3 SMALLINT,
    c4 BIGINT
);

CREATE TABLE layout_packed (
    c2 BIGINT,
    c4 BIGINT,
    c1 SMALLINT,
    c3 SMALLINT
);

INSERT INTO layout_unpacked VALUES (1, 100, 2, 200);
INSERT INTO layout_packed VALUES (100, 200, 1, 2);

-- Inspeksi byte size pada heap
SELECT lp, t_len, t_data 
FROM heap_page_items(get_raw_page('layout_unpacked', 0));

SELECT lp, t_len, t_data 
FROM heap_page_items(get_raw_page('layout_packed', 0));

-- Langkah 2: Declarative Hash + Range Sub-Partitioning
DROP TABLE IF EXISTS telemetry_events CASCADE;

CREATE TABLE telemetry_events (
    device_id   UUID NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    payload     JSONB NOT NULL,
    severity    VARCHAR(10) NOT NULL,
    PRIMARY KEY (device_id, recorded_at)
) PARTITION BY HASH (device_id);

-- 2 Hash Partitions
CREATE TABLE telemetry_events_h1 PARTITION OF telemetry_events
    FOR VALUES WITH (MODULUS 2, REMAINDER 0)
    PARTITION BY RANGE (recorded_at);

CREATE TABLE telemetry_events_h2 PARTITION OF telemetry_events
    FOR VALUES WITH (MODULUS 2, REMAINDER 1)
    PARTITION BY RANGE (recorded_at);

-- Leaf Range Partitions untuk H1
CREATE TABLE telemetry_events_h1_2025_01 PARTITION OF telemetry_events_h1
    FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2025-02-01 00:00:00+00');

CREATE TABLE telemetry_events_h1_2025_02 PARTITION OF telemetry_events_h1
    FOR VALUES FROM ('2025-02-01 00:00:00+00') TO ('2025-03-01 00:00:00+00');

-- Leaf Range Partitions untuk H2
CREATE TABLE telemetry_events_h2_2025_01 PARTITION OF telemetry_events_h2
    FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2025-02-01 00:00:00+00');

CREATE TABLE telemetry_events_h2_2025_02 PARTITION OF telemetry_events_h2
    FOR VALUES FROM ('2025-02-01 00:00:00+00') TO ('2025-03-01 00:00:00+00');

-- Langkah 3: Pengujian Partition Pruning
SET enable_partition_pruning = on;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM telemetry_events
WHERE device_id = 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'
  AND recorded_at >= '2025-01-10 00:00:00+00' 
  AND recorded_at < '2025-01-15 00:00:00+00';

-- Amati bahwa hanya SATU tabel fisik (antara telemetry_events_h1_2025_01 atau h2_2025_01) yang discan!
```

---

### 13. Exercise

#### Level Easy
Terdapat tabel warisan dengan skema:
```sql
CREATE TABLE legacy_customers (
    is_active BOOLEAN,
    customer_id BIGINT,
    postal_code VARCHAR(5),
    updated_at TIMESTAMPTZ,
    balance NUMERIC(15,2),
    flag_char CHAR(1)
);
```
Susun ulang (*re-order*) struktur kolom tabel tersebut berdasarkan prinsip *data alignment* PostgreSQL untuk meminimalkan *padding byte*. Buktikan menggunakan skrip SQL dan hitung byte yang dihemat per 1.000.000 tuple.

#### Level Medium
Buat skema rental mobil di mana satu armada (`car_id`) tidak boleh disewakan kepada penyewa yang berbeda pada rentang waktu yang bertabrakan. Skema harus mengizinkan status mobil yang sama berada dalam status 'MAINTENANCE' di rentang waktu berbeda. Gunakan tipe data `TSTZRANGE` dan `EXCLUDE USING gist`.

#### Level Hard
Rancang arsitektur kueri *Recursive CTE* yang memproses data tagihan bersarang (*Hierarchical Bill of Materials - BOM*). Data terdiri dari 10 level komponen perakitan mesin. Implementasikan mekanik *cycle detection* menggunakan tipe data array `path` agar kueri tidak terjebak dalam *infinite loop* jika seorang analis keliru menginput referensi hierarki yang melingkar (*circular dependency*).

---

### 14. Challenge

**Skenario**: Sistem *Multi-Cloud Inventory Allocation Engine* mengalami kegagalan konkurensi fatal.
- Beban puncak: 50.000 transaksi alokasi stok per detik.
- Terdapat aturan bisnis: Setiap SKU pada Gudang tertentu (`warehouse_id`) dialokasikan dengan kuota waktu tertentu. Alokasi ini memiliki *soft-reservation expiry* (15 menit).
- Masalah: Jika menggunakan skema row locking tradisional (`SELECT FOR UPDATE`), terjadi deadlock masif di bawah konkurensi tinggi. Jika menggunakan isolasi *Serializable*, transaksi sering di-abort (*40001 serialization_failure*).
- **Tugas Anda**: Rancang skema database murni di PostgreSQL (tanpa bantuan Redis) menggunakan kombinasi *Declarative Hash Partitioning*, *Bi-temporal / TSTZRANGE Exclusion Constraints*, dan *Advisory Locks* / *Skip Locked patterns* untuk mencapai throughput maksimum tanpa ada alokasi ganda (*zero over-allocation*) dan tanpa *abort exception*. Susun DDL lengkap, fungsi PL/pgSQL eksekutor alokasi, serta bukti rencana eksekusi menggunakan `EXPLAIN`.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Berapa ukuran header standar satu tuple di heap page PostgreSQL sebelum memperhitungkan NULL bitmap?
   - A. 8 bytes
   - B. 16 bytes
   - C. 23 (dibulatkan menjadi 24) bytes
   - D. 32 bytes

2. Tipe data manakah yang memerlukan 8-byte boundary memory alignment pada sistem arsitektur x86_64?
   - A. `INTEGER`
   - B. `VARCHAR`
   - C. `TIMESTAMPTZ`
   - D. `BOOLEAN`

3. Ambang batas ukuran default suatu baris sebelum PostgreSQL mulai mengaktifkan mekanisme kompresi TOAST adalah:
   - A. 8 KB
   - B. 4 KB
   - C. 2 KB
   - D. 1 KB

4. Ekstensi apa yang wajib diaktifkan jika Anda ingin menggunakan operator skalar seperti `=` bersamaan dengan operator rentang `&&` di dalam klausa `EXCLUDE USING gist`?
   - A. `pg_stat_statements`
   - B. `btree_gist`
   - C. `uuid-ossp`
   - D. `hstore`

5. Jenis pruning yang terjadi ketika planner PostgreSQL mengeliminasi partisi berdasarkan nilai konstan di klausa `WHERE` pada fase penyusunan execution plan disebut:
   - A. Dynamic Pruning
   - B. Static Pruning
   - C. Run-time Pruning
   - D. Deferred Pruning

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Pendek)
6. Apa keunggulan teknis menggunakan indeks `USING gin (col jsonb_path_ops)` dibandingkan `USING gin (col jsonb_ops)`?
   - A. Mendukung pencarian regex.
   - B. Ukuran indeks jauh lebih kecil dan lookup operator `@>` lebih cepat karena melakukan hash pada path & value secara terpadu.
   - C. Memungkinkan indexing kolom non-JSONB.
   - D. Mendukung operator eksistensi `?` secara langsung.

7. Jika Anda menjalankan perintah `UPDATE` pada kolom `PARTITION KEY` yang menyebabkan baris berpindah dari `partition_A` ke `partition_B`, apa yang sebenarnya dilakukan engine PostgreSQL?
   - A. Memindahkan pointer tuple secara atomic di dalam root table catalog.
   - B. Mengubah metadata boundary pada `partition_A`.
   - C. Melakukan `DELETE` fisik tuple dari `partition_A` dan melakukan `INSERT` tuple baru ke `partition_B`.
   - D. Operasi tersebut selalu ditolak dan melempar error `cannot_modify_partition_key`.

8. Mengapa composite type `(a, b)` kadang lebih disukai daripada tipe data `JSONB` untuk payload data terstruktur tetap?
   - A. Composite type tidak memerlukan alokasi disk.
   - B. Composite type memiliki type safety ketat, alignment yang deterministik, dan bebas overhead serialization JSON.
   - C. Composite type otomatis terenkripsi.
   - D. JSONB tidak mendukung index B-tree.

9. Pada partisi deklaratif, apa dampak membuat terlalu banyak partisi leaf (misalnya > 50.000 partisi dalam satu database instance)?
   - A. Storage hard disk otomatis terfragmentasi menjadi 64 KB block.
   - B. Konsumsi memori per connection membengkak drastis akibat lock table dan cache metadata partisi (`relcache`), serta query planning time melonjak lambat.
   - C. Fitur parallel scan otomatis dimatikan permanen.
   - D. PostgreSQL berhenti menerima koneksi port 5432.

10. Apa kegunaan utama dari strategi penyimpanan TOAST berlabel `EXTERNAL`?
    - A. Menyimpan payload data di AWS S3 di luar filesystem PostgreSQL.
    - B. Memindahkan data panjang ke relasi TOAST tanpa mengeluarkan siklus CPU untuk kompresi data.
    - C. Mencegah data di-backup oleh tool `pg_dump`.
    - D. Mengubah format teks menjadi binary otomatis.

#### Bagian 3: Skenario Kasus Produksi
11. **Kasus Bloat Partisi**: Sebuah tabel transaksi keuangan dipartisi harian. Mengapa operasi `TRUNCATE` pada partisi 90 hari lalu berjalan dalam beberapa milidetik tanpa memicu I/O disk tinggi, sedangkan eksekusi `DELETE FROM transactions WHERE tx_date = CURRENT_DATE - 90;` dapat melumpuhkan I/O server selama 30 menit?
12. **Kasus Anomali Timezone Temporal**: Seorang software engineer mendesain tabel reservasi menggunakan tipe data `DATERANGE` untuk kamar hotel di Tokyo (UTC+9) dan London (UTC+0). Mengapa menyimpan tanggal lokal sebagai `DATERANGE` murni tanpa menyertakan zona waktu dapat memicu konflik booking di perbatasan jam malam? Bagaimana skema yang seharusnya?
13. **Kasus GIN Expansion Failure**: Sebuah sistem logging mencatat jutaan payload JSONB ke satu partisi bulanan. Database tiba-tiba mengalami *freeze* penulisan selama 15 detik setiap beberapa menit. Metrik menunjukkan utilisasi CPU 100% pada satu backend process saat eksekusi DML `INSERT`. Parameter sistem apa yang perlu dianalisis terkait proses pembersihan GIN index (*fastupdate* buffer cleaning)?

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **C** (23 bytes, dibulatkan / aligned menjadi 24 bytes pada platform arsitektur 64-bit).
2. **C** (`TIMESTAMPTZ` berukuran 8 bytes dan memerlukan 8-byte memory boundary).
3. **C** (`TOAST_TUPLE_THRESHOLD` default adalah ~2 KB / seperempat block size 8 KB).
4. **B** (`btree_gist` mengizinkan tipe data standar B-Tree dievaluasi menggunakan interface operator class GiST).
5. **B** (Static / Compile-time Pruning).

#### Bagian 2: Intermediate
6. **B** (`jsonb_path_ops` hanya menyimpan 32-bit hash dari node-path dan value gabungan, menghasilkan ukuran indeks drastis lebih kecil dibanding `jsonb_ops` yang mengindeks setiap key dan value secara terpisah).
7. **C** (PostgreSQL mengeksekusi *cross-partition row routing* dengan menghapus tuple dari partisi asal dan menyisipkan baris baru ke partisi tujuan di dalam konteks transaksi yang sama).
8. **B** (Type-safety, alignment deterministik, dan zero parsing parsing overhead saat evaluasi data).
9. **B** (Konsumsi shared memory dan overhead planning time membesar secara eksponensial karena engine harus mengunci dan menginspeksi ribuan partisi saat query planner berjalan).
10. **B** (Menonaktifkan kompresi, memindahkan data secara mentah ke tabel TOAST, sangat ideal untuk data yang sudah terkompresi secara native seperti file PDF/JPEG atau ciphertext).

#### Bagian 3: Analisis Kasus Produksi
11. **Analisis**: `TRUNCATE` merupakan operasi DDL yang memutus relasi file secara langsung pada filesystem (*unlink* `relfilenode`), membebaskan alokasi disk secara instan tanpa memproses tuple individual dan mencatat aktivitas minimal di WAL. Sebaliknya, `DELETE` harus memindai setiap baris, menulis tombstone markers ke dalam MVCC page (*t_xmax* logging), menghasilkan WAL record dalam jumlah gigabyte, serta meninggalkan *dead tuples* masif yang memicu beban kerja berat pada *autovacuum daemon*.
12. **Analisis**: `DATERANGE` tidak membawa konteks waktu absolut (jam, menit, offset offset timezone). Tamu yang memesan pada tgl 10 di Tokyo check-in ketika di London masih tgl 9. Sistem integrasi API multi-wilayah akan menghasilkan interpretasi ambigu terkait kapan hak sewa fisik kamar dimulai. Solusi: Gunakan tipe data `TSTZRANGE` dengan timestamp absolut berbasis UTC, atau sertakan kolom eksplisit `timezone` dan gunakan fungsi domain untuk memvalidasi batas check-in jam 14:00 lokal secara presisi.
13. **Analisis**: Indeks GIN secara default mengaktifkan parameter `fastupdate = on`, yang menampung *insert payload* di buffer sementara (*pending list*). Saat pending list melampaui ambang batas `gin_pending_list_limit` (default: 4MB), satu proses backend yang sedang meng-insert terpaksa berhenti dan membersihkan serta memindahkan entri ke struktur B-Tree/GIN utama (*work-absorbing cleanup*). Solusi: Naikkan `gin_pending_list_limit` ke ukuran yang lebih memadai (misal: 64MB - 128MB) dan jalankan fungsi pembersihan manual via `gin_clean_pending_list(index_name)` secara asinkron via cron/pg_cron di jam non-peak, atau matikan `fastupdate` jika I/O storage SSD enterprise Anda cukup kencang.

---

### 16. Summary

1. **Storage Optimization**: Menata urutan kolom tabel dari ukuran terbesar ke terkecil (*8-byte $\to$ 4-byte $\to$ 2-byte $\to$ 1-byte*) secara fisik melenyapkan *alignment padding bytes*, menghemat ruang disk dan penggunaan RAM buffer cache hingga ~30%.
2. **Advanced Partitioning**: Partisi deklaratif modern mengisolasi data dalam volume terabyte. *Dynamic Pruning* harus dijaga dengan memastikan kesesuaian tipe data dan parameterisasi filter query.
3. **Data Integrity via Exclusion Constraints**: Mengombinasikan `GiST` dengan ekstensi `btree_gist` menyelesaikan permasalahan validasi bisnis kompleks (seperti pencegahan *overlapping time intervals*) langsung pada engine data dengan jaminan konsistensi ACID 100%.
4. **Bi-temporal Ledger Architecture**: Arsitektur data masa kini wajib membedakan *System Period* (fakta audit pencatatan) dan *Application Period* (fakta domain bisnis) menggunakan tipe data rentang (`TSTZRANGE`) untuk menjamin riwayat data tidak pernah terhapus (*immutable compliance*).
5. **Specialized Indexing**: Pemanfaatan `jsonb_path_ops` vs `jsonb_ops` harus didasarkan pada tipe kueri yang digunakan; perancangan indeks yang keliru pada kolom JSONB bervolume tinggi berisiko memicu ledakan kapasitas disk dan degradasi write throughput server database.