# Kurikulum Enterprise: PostgreSQL Database Administration (DBA)
## Kategori: 04-Backend-and-Database
### BAB-04: Indexing Strategies & Storage Engine Internals
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada tingkat Staff/Principal DBA dan Enterprise Infrastructure Engineer diharapkan mampu:

1. **Menganalisis Anatomi Fisik Storage Engine**: Mengoperasikan ekstensi internal (`pageinspect`, `pgstattuple`) untuk membedah struktur *slotted page* 8KB, *tuple header*, *Line Pointer* (`lp`), *Visibility Map* (VM), *Free Space Map* (FSM), serta mekanisme kompresi dan *out-of-line storage* (TOAST).
2. **Menguasai Arsitektur dan Mekanika B-Tree Tingkat Lanjut**: Mengidentifikasi proses *page split* (50/50 vs right-split), struktur *High Key*, *B-Tree deduplication* (PostgreSQL 13+), serta pengaruh *fillfactor* terhadap Write Amplification.
3. **Mendesain Indeks Tersegmentasi & Fungsional**: Mengimplementasikan *Partial Index*, *Covering Index* (`INCLUDE` clause) untuk memicu *Index-Only Scan*, serta *Expression-based Index* yang memitigasi kalkulasi dinamis pada *runtime*.
4. **Mengevaluasi Access Methods Non-B-Tree**: Menentukan kapan dan bagaimana menerapkan GiST (R-Tree), GIN (*Inverted Index* untuk JSONB dan Full-Text Search), SP-GiST, BRIN (*Block Range Index* untuk time-series berskala multi-terabyte), dan Hash Index yang *crash-safe* (PostgreSQL 10+).
5. **Mengoptimalkan Mutasi Tuple Melalui HOT (Heap-Only Tuples)**: Mengonfigurasi parameter tabel guna memaksimalkan HOT-update rate, mengeliminasi indeks overhead saat operasi `UPDATE`, dan memotong jejak *fragmentasi dead tuple*.
6. **Membangun Prosedur Remediasi Bloat Tanpa Downtime**: Menjalankan strategi pemeliharaan skala enterprise menggunakan `REINDEX CONCURRENTLY`, mendeteksi *index bloat* melalui kalkulasi metrik leaf-page, serta melakukan audit integritas indeks menggunakan `pg_amcheck`.

---

### 2. Prerequisite

Sebelum menempuh modul ini, peserta wajib memiliki pemahaman mendalam terkait:
* Konsep dasar relasional dan ACID transaction isolation levels (khususnya *Read Committed* dan *Repeatable Read*).
* Arsitektur memori dasar PostgreSQL (`shared_buffers`, `work_mem`, `wal_buffers`).
* Perintah diagnostik query dasar (`EXPLAIN`, `EXPLAIN (ANALYZE, BUFFERS)`).
* Akses terminal ke *instance* PostgreSQL (versi 14, 15, atau 16) dengan hak akses `SUPERUSER` untuk memasang modul contrib engine.

---

### 3. Concept & Internal Architecture

#### 3.1 Anatomi Slotted Page Layout (Default 8192 Bytes)
PostgreSQL menyimpan relasi tabel (*heap*) dan indeks dalam blok berukuran tetap yang disebut **Page** (default `8192 bytes` atau 8 KB). Format biner sebuah page terdiri atas beberapa segmen terstruktur:

```
+-----------------------------------------------------------------------+
| PageHeaderData (24 bytes)                                             |
|  - pd_lsn (8B)       : Log Sequence Number untuk WAL tracking         |
|  - pd_checksum (2B)  : Algoritma CRC-16 verifikasi integritas data    |
|  - pd_flags (2B)     : Status flag (misal: PD_PAGE_FULL, PD_ALL_VISIBLE)|
|  - pd_lower (2B)     : Offset byte akhir dari Line Pointer array      |
|  - pd_upper (2B)     : Offset byte awal dari Tuple Data terendah      |
|  - pd_special (2B)   : Offset ke special space (indeks-spesifik)      |
|  - pd_pagesize_version: Versi layout halaman dan ukuran page          |
|  - pd_prune_xid (4B) : XID tertua yang memicu kandidat pruning        |
+-----------------------------------------------------------------------+
| Line Pointer Array / ItemIdData (Array of 4-byte scalar references)   |
|  [lp_1: (offset, flags, len)] [lp_2] [lp_3] ...                       |
|  --> Bertumbuh ke ARAH BAWAH (Downwards)                              |
+-----------------------------------------------------------------------+
|                       <--- UNALLOCATED FREE SPACE --->                |
+-----------------------------------------------------------------------+
| HeapTupleData / IndexTuples                                           |
|  Tuple_3 (Length: N bytes)                                            |
|  Tuple_2 (Length: M bytes)                                            |
|  Tuple_1 (Length: K bytes)                                            |
|  <-- Bertumbuh ke ARAH ATAS (Upwards)                                 |
+-----------------------------------------------------------------------+
| Special Space (Ukuran bervariasi, 0 bytes pada plain heap,            |
|                digunakan B-Tree untuk pointer sibling kiri/kanan)     |
+-----------------------------------------------------------------------+
```

* **Line Pointer (`ItemIdData`)**: Sebuah array 32-bit (4-byte) pointer. Line pointer menyimpan:
  * `lp_off` (15-bit): Offset riil dari awal page ke data tuple.
  * `lp_flags` (2-bit): Status line pointer (`00` = Unused, `01` = Used, `10` = HOT redirect, `11` = Dead).
  * `lp_len` (15-bit): Panjang byte dari tuple tersebut.
* **Tuple Addressing (`ItemPointerData` / `TID` / `ctid`)**: Dinyatakan dalam notasi `(BlockNumber, OffsetNumber)`. Sebagai contoh: `(42, 3)` menunjuk pada page ke-42 dan line pointer (offset) urutan ke-3.

#### 3.2 Heap Tuple Header & Atribut Internal
Setiap baris data fisik di-wrap oleh struktur `HeapTupleHeaderData` (minimal 23 bytes sebelum padding):
* `t_xmin`: XID (Transaction ID) dari transaksi yang melakukan `INSERT`.
* `t_xmax`: XID transaksi yang melakukan `DELETE` atau `UPDATE` (mengunci tuple). Bernilai `0` jika tuple aktif dan tidak terkunci.
* `t_cid`: Command Identifier di dalam transaksi yang sama.
* `t_ctid`: Fisik TID dari tuple ini sendiri, ATAU menunjuk ke tuple fisik baru jika baris telah di-`UPDATE`.
* `t_infomask` & `t_infomask2`: Bit flags penentu status visibilitas (contoh: `HEAP_XMIN_COMMITTED`, `HEAP_XMAX_INVALID`, `HEAP_HOT_UPDATED`, `HEAP_ONLY_TUPLE`).

#### 3.3 TOAST (The Oversized-Attribute Storage Technique)
PostgreSQL tidak mengizinkan baris data melompati batas page (8 KB). Jika sebuah tuple setelah dihitung melebihi ambang batas `TOAST_TUPLE_THRESHOLD` (secara default ~2 KB atau `PageSize / 4`), PostgreSQL mengaktifkan mekanisme TOAST dengan urutan prioritas:
1. **Compress**: Kompresi atribut *in-line* via PGLZ atau LZ4 (PostgreSQL 14+).
2. **Move out-of-line**: Jika masih terlalu besar, pindahkan chunk (masing-masing ~2 KB) ke tabel pendukung internal (`pg_toast_<reloid>`) dan gantikan nilai di tuple utama dengan pointer TOAST 18-byte (`varatt_external`).

Strategi kompresi per-kolom dikontrol via atribut:
* `PLAIN`: Tidak ada kompresi, tidak ada out-of-line storage (misal: tipe data numerik dasar).
* `EXTENDED`: Kompresi terlebih dahulu; jika masih melampaui batas, simpan *out-of-line* (default untuk `text`, `bytea`, `jsonb`).
* `EXTERNAL`: Simpan *out-of-line* tanpa kompresi (memotong latensi CPU dekompresi).
* `MAIN`: Kompresi *in-line*; simpan *out-of-line* hanya sebagai opsi pamungkas.

#### 3.4 B-Tree Deep Internals & Deduplication
Struktur B-Tree PostgreSQL adalah implementasi berbasis *Lehman & Yao High-Concurrency B-Tree*. 

```
                       +-------------------+
                       |    Root Page      |
                       +-------------------+
                             /        \
          +--------------------+    +--------------------+
          | Internal Page (L1) |    | Internal Page (L1) |
          +--------------------+    +--------------------+
                 /        \               /        \
        +------------+ +------------+ +------------+ +------------+
        | Leaf (P0)  |<-> Leaf (P1) |<-> Leaf (P2) |<-> Leaf (P3) |
        +------------+ +------------+ +------------+ +------------+
```

* **Lehman-Yao Invariant**: Setiap leaf page dan internal page memiliki pointer transversal kanan (*right-link*) dan nilai pemisah (*High Key*). Hal ini memungkinkan proses pencarian (search traversal) tetap berjalan secara *lock-free* terhadap pembaca tanpa tertahan oleh operasi *page split* konkuren.
* **B-Tree Page Split**: Terjadi saat sebuah leaf page kehabisan ruang untuk menampung index tuple baru. Engine mengalokasikan page baru, membagi separuh tuple ke page baru, memperbarui right-link, dan menyisipkan *downlink key* ke parent page.
* **B-Tree Deduplication (PostgreSQL 13+)**: Mengubah representasi tuple yang memiliki indeks duplikat. Daripada menyimpan:
  `{Key: "A", TID: (1,1)}, {Key: "A", TID: (1,2)}, {Key: "A", TID: (1,3)}`
  Engine mengompresinya menjadi satu posting list tuple:
  `{Key: "A", PostingList: [(1,1), (1,2), (1,3)]}`
  Fitur ini memangkas jejak fisik memori hingga 40-70% pada kolom dengan kardinalitas rendah-menengah.

#### 3.5 Heap-Only Tuples (HOT) Engine Optimization
Masalah performa terbesar pada PostgreSQL klasik adalah operasi `UPDATE` yang selalu membuat tuple baru di level Heap, yang mengharuskan setiap indeks pada tabel menyisipkan pointer fisik baru ke tuple tersebut. Dampaknya: *Write Amplification* dan *Index Bloat*.

HOT mengatasi hal ini jika dua kondisi terpenuhi:
1. Kolom yang di-`UPDATE` **bukan** merupakan bagian dari kolom pengindeksan mana pun pada tabel tersebut.
2. Tersedia kapasitas ruang kosong (*free space*) yang mencukupi di dalam **page heap yang sama** tempat baris lama berada.

Jika lolos, engine melakukan langkah berikut:
* Tuple baru ditulis pada page yang sama.
* Tuple baru ditandai sebagai `HEAP_ONLY_TUPLE`.
* Tuple lama ditandai sebagai `HEAP_HOT_UPDATED` dan pointer `t_ctid`-nya dialihkan secara langsung ke offset tuple baru di page yang sama.
* Line pointer lama bertindak sebagai titik perantara (*HOT redirect chain*). **Tidak ada penulisan indeks baru sama sekali.**

---

### 4. Why & What

| Engine / Index Type | Struktur Internal | Kompleksitas Waktu (Pencarian Rata-rata) | Penggunaan Utama Enterprise | Batasan & Kelemahan |
| :--- | :--- | :--- | :--- | :--- |
| **B-Tree** | Lehman-Yao B+ Tree | $O(\log N)$ | Primary Keys, Foreign Keys, Range/Equality queries standar | Menghasilkan bloat tinggi pada throughput update masif; ukuran fisik besar. |
| **BRIN** | Block Range Index (Menyimpan Min/Max per rentang block, cth: 128 page) | $O(N)$ terhadap block range + scan | Audit Logs, Event Stream, Time-Series Terabyte-scale | Hanya efisien jika data tersimpan terurut secara fisik (*physical correlation* mendekati 1.0 atau -1.0). |
| **GIN** | Generalized Inverted Index (B-Tree dari komponen kunci, menunjuk ke daftar posting TID) | $O(\log N)$ untuk pencarian term + bitmap intersection | JSONB (`@>`, `?`), Full-Text Search (`tsvector`), Array search (`&&`) | Biaya penulisan (write overhead) sangat tinggi; membutuhkan *pending list* dan background cleaning. |
| **GiST** | Generalized Search Tree (Hierarchical Balanced Tree) | $O(\log N)$ hingga $O(N)$ tergantung overlap | Spasial/GIS (PostGIS), Rentang Nilai (`tsrange`, `int4range`), Pencarian K-Nearest Neighbor (KNN) | Ukuran index besar; algoritma split lebih kompleks, latensi write lebih tinggi dibanding B-Tree. |
| **SP-GiST** | Space-Partitioned GiST (Quad-tree, k-d tree, Radix trie) | $O(\log N)$ | Data dengan distribusi tidak merata, prefix text parsing, representasi hierarki spasial tertentu | Penggunaan sangat spesifik; tidak mendukung multi-column. |
| **Hash** | On-disk Hash Table (Crash-safe via WAL sejak PG 10) | $O(1)$ | Exact match equality (`=`) murni pada tipe data string panjang tanpa operasi range | Tidak mendukung sorting (`ORDER BY`), range query, maupun index-only scans. |

---

### 5. How: Workflow Detail

#### 5.1 Siklus Hidup Eksekusi Pembacaan Index & Resolusi Heap Tuple
Diagram berikut menguraikan alur kerja ketika sebuah query pembacaan dijalankan:

```
[Query Engine: SELECT * FROM ledger WHERE account_id = 1001]
                             │
                             ▼
              [B-Tree Root & Internal Traversal]
                             │  Membaca Page B-Tree secara biner (Buffer Manager)
                             ▼
                    [B-Tree Leaf Page]
                             │  Pencarian biner di dalam page
                             ▼
              Ditemukan Leaf Index Tuple: 
                 Key: 1001 -> TID: (Block 450, Offset 4)
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [Non-Index-Only Scan]             [Index-Only Scan]
            │                                 │
            ▼                                 ▼
  [Akses Heap Page 450]              [Periksa Visibility Map (VM)]
            │                        Page 450 bit "all-visible" = 1?
            │                                ├── YA: Kembalikan data dari 
            │                                │       Index (Zero Heap Read)
            │                                └── TIDAK: Fallback baca Heap 
            │                                           Page 450 untuk MVCC check
            ▼
  [Baca Line Pointer Offset 4]
            │
            ├── Line pointer type: Normal -> Arahkan ke Header Tuple
            └── Line pointer type: Redirect (HOT) -> Telusuri Chain (Offset 4 -> Offset 6)
            │
            ▼
  [Evaluasi MVCC Visibility Tuple]
   Periksa t_xmin, t_xmax terhadap Snapshot Transaksi
            │
            ├── VISIBLE   : Serialisasikan atribut & kirim ke client
            └── INVISIBLE : Abaikan baris data (Dead Tuple)
```

#### 5.2 Mekanisme HOT Pruning & Defragmentasi Otomatis
Pembersihan baris usang (*dead tuple*) tidak selalu harus menunggu daemon background autovacuum berjalan. PostgreSQL melakukan *in-page line pruning* secara oportunistik:
1. Ketika transaksi backend membaca heap page untuk query apa pun, sistem memeriksa apakah page tersebut memiliki HOT-chain yang memuat dead tuple.
2. Jika ditemukan, backend mengunci buffer page secara eksklusif (buffer-level lock mikrodetik) dan memotong HOT redirect chain secara internal.
3. Offset line pointer yang usang diubah statusnya menjadi stub redirect atau dilepaskan.
4. Ruang kosong fisik (*fragmented space*) digabungkan kembali (*compacted*) dengan menggeser tuple data ke arah batas bawah (*upper boundary* page header), meningkatkan metrik `pd_upper - pd_lower`.
5. Semua operasi ini dicatat ke dalam Write-Ahead Logging (WAL) untuk menjamin durabilitas *crash-recovery*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Kota dan Sistem Pengarsipan
* **Heap Storage**: Lemari arsip berkas utama. Tiap laci adalah satu **Page (8KB)**. Dokumen di dalam laci dilempar begitu saja ke ruang kosong yang tersedia.
* **Line Pointer**: Daftar isi di bagian paling depan laci berkas yang mencatat: *"Berkas #3 berada 15 sentimeter dari bibir laci belakang"*.
* **B-Tree**: Buku indeks katalog di meja resepsionis yang mencatat nomor laci dan nomor slip berkas (`ctid`).
* **HOT Update**: Jika isi dokumen diperbarui tanpa mengganti nama subjeknya, arsiparis tidak pergi ke meja resepsionis untuk memperbarui katalog. Arsiparis cukup menaruh lembar baru tepat di belakang lembar lama di dalam laci yang sama, lalu menempelkan stiker di lembar lama: *"Baca versi revisi tepat di halaman belakang ini"*. Meja katalog tidak terganggu sama sekali.
* **TOAST**: Jika ada lampiran berkas setebal 2000 halaman yang tidak muat di laci biasa, arsiparis memindahkannya ke gudang khusus (Tabel TOAST) dan hanya meninggalkan secarik kupon barcode referensi di berkas utama.

#### Diagram: Perbandingan Normal Update vs. HOT Update
```
SKENARIO A: NORMAL UPDATE (Kolom berindeks diubah, misal: balance)
========================================================================================
[B-TREE INDEX PAGE]
  Index Entry 1: Key=100 -> TID (Page 1, lp 1)  (Dead Pointer)
  Index Entry 2: Key=150 -> TID (Page 1, lp 2)  <-- WRITE AMPLIFICATION DI LEVEL INDEKS!

[HEAP PAGE 1]
  +------------------------------------------------------------------------------------+
  | Line Pointer: [lp 1 -> Offset Tuple v1] [lp 2 -> Offset Tuple v2]                  |
  |                                                                                    |
  | Tuple v1: [xmin: 500, xmax: 501, ctid: (1,2), Val: 100] (DEAD TUPLE)               |
  | Tuple v2: [xmin: 501, xmax: 0,   ctid: (1,2), Val: 150] (ACTIVE TUPLE)             |
  +------------------------------------------------------------------------------------+


SKENARIO B: HOT UPDATE (Kolom non-indeks diubah, misal: note, fillfactor < 100)
========================================================================================
[B-TREE INDEX PAGE]
  Index Entry 1: Key=100 -> TID (Page 1, lp 1)  <-- TIDAK ADA PERUBAHAN PADA INDEKS!

[HEAP PAGE 1]
  +------------------------------------------------------------------------------------+
  | Line Pointer: [lp 1 (REDIRECT to lp 2)] [lp 2 (NORMAL -> Tuple v2)]                |
  |                                                                                    |
  | Tuple v1: [xmin: 500, xmax: 501, ctid: (1,2), HOT_UPDATED, Val: "Draft"] (DEAD)    |
  | Tuple v2: [xmin: 501, xmax: 0,   ctid: (1,2), HEAP_ONLY,   Val: "Final"] (ACTIVE)  |
  +------------------------------------------------------------------------------------+
```

---

### 7. Practical Implementation Code

Di bawah ini disajikan kode implementasi produksi untuk analisis storage, perancangan indeks tingkat lanjut, dan eliminasi bloat.

#### 7.1 Inspeksi Page Header dan Storage Internals (`pageinspect`)
```sql
-- Ekstensi wajib untuk DBA level internal
CREATE EXTENSION IF NOT EXISTS pageinspect;
CREATE EXTENSION IF NOT EXISTS pgstattuple;

-- Buat tabel simulasi dengan fillfactor non-default untuk memberikan ruang HOT
DROP TABLE IF EXISTS accounts_ledger CASCADE;
CREATE TABLE accounts_ledger (
    account_id BIGINT NOT NULL,
    account_uuid UUID NOT NULL,
    current_balance NUMERIC(15,2) NOT NULL,
    metadata JSONB,
    note TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
) WITH (fillfactor = 85);

-- Dummy data: 10.000 records
INSERT INTO accounts_ledger (account_id, account_uuid, current_balance, metadata, note)
SELECT 
    i,
    gen_random_uuid(),
    (random() * 100000)::NUMERIC(15,2),
    jsonb_build_object('tier', CASE WHEN i % 10 = 0 THEN 'enterprise' ELSE 'standard' END, 'verified', true),
    repeat('A', 150) -- Payload text untuk simulasi volume
FROM generate_series(1, 10000) AS i;

-- Query Diagnostik Page Header pada Block 0
SELECT 
    lower AS pd_lower,
    upper AS pd_upper,
    special AS pd_special,
    pagesize,
    ROUND(((upper - lower)::NUMERIC / pagesize) * 100, 2) AS free_space_percent
FROM page_header(get_raw_page('accounts_ledger', 0));

-- Membaca status array Line Pointer (ItemPointerData) pada Block 0
SELECT 
    lp,
    lp_off,
    lp_flags,
    lp_len,
    t_xmin,
    t_xmax,
    t_ctid,
    t_infomask::text,
    t_infomask2::text
FROM heap_page_items(get_raw_page('accounts_ledger', 0))
LIMIT 5;
```

#### 7.2 Implementasi Covering Index (`INCLUDE`) & Index-Only Scan
```sql
-- Skenario: Query point-lookup intensif pada endpoint API perbankan:
-- SELECT current_balance, updated_at FROM accounts_ledger WHERE account_id = ?;

-- STRATEGI SALAH: Membuat composite index konvensional (account_id, current_balance, updated_at)
-- Dampak negatif: Ukuran intermediate node membesar, depth tree meningkat, pemborosan RAM shared_buffers.

-- STRATEGI BENAR (PostgreSQL 11+): B-Tree Bounding Keys + Payload Columns
CREATE UNIQUE INDEX idx_accounts_ledger_covering 
ON accounts_ledger (account_id) 
INCLUDE (current_balance, updated_at);

-- Verifikasi implementasi: Memastikan eksekusi menggunakan "Index Only Scan" tanpa membaca heap block
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT account_id, current_balance, updated_at 
FROM accounts_ledger 
WHERE account_id = 4550;

-- Output yang diharapkan:
-- Index Only Scan using idx_accounts_ledger_covering on accounts_ledger
-- Buffers: shared hit=3 (Hanya menyentuh block B-Tree, tidak membaca heap page)
```

#### 7.3 Implementasi Index Non-B-Tree (GIN, Partial, dan BRIN)
```sql
-- A. GIN (Generalized Inverted Index) untuk Query Pencarian JSONB
-- Mengoptimalkan operator containment (@>)
CREATE INDEX idx_accounts_ledger_meta_gin 
ON accounts_ledger USING gin (metadata jsonb_path_ops);

-- B. Partial Index untuk Menghemat Ukuran dan Operasi Disk
-- Hanya mengindeks baris 'enterprise' (hanya 10% dari volume tabel)
CREATE INDEX idx_accounts_ledger_enterprise_only 
ON accounts_ledger (account_id) 
WHERE (metadata->>'tier' = 'enterprise');

-- C. BRIN (Block Range Index) untuk Arsitektur Time-Series Multigigabyte
-- Buat partisi log berukuran masif dengan physical ordering kuat
DROP TABLE IF EXISTS audit_transactions_stream;
CREATE TABLE audit_transactions_stream (
    tx_id BIGSERIAL,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    payload TEXT
);

-- Mengisi data secara berurutan sesuai timeline
INSERT INTO audit_transactions_stream (event_timestamp, payload)
SELECT 
    ts,
    'Audit trace payload #' || i
FROM generate_series(
    NOW() - INTERVAL '30 days',
    NOW(),
    INTERVAL '1 second'
) AS g(ts),
generate_series(1, 2) AS i;

-- Buat BRIN index dengan konfigurasi pages_per_range (default 128)
-- Tiap 1 entry indeks memetakan rentang Min/Max dari 128 heap block (1024 KB)
CREATE INDEX idx_audit_stream_brin 
ON audit_transactions_stream USING brin (event_timestamp) 
WITH (pages_per_range = 64);

-- Validasi efisiensi spasial:
SELECT 
    pg_size_pretty(pg_relation_size('audit_transactions_stream')) AS table_size,
    pg_size_pretty(pg_relation_size('idx_audit_stream_brin')) AS brin_index_size;
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Insiden Produksi
* **Domain**: Platform Financial Core Banking / Pembayaran Digital.
* **Volume Data**: Tabel `wallet_balances` (85 juta rows, ukuran dasar ~18 GB).
* **Throughput**: 4.500 transaksi pembaruan saldo (*update transactions*) per detik pada jam sibuk.
* **Gejala Masalah**:
  1. Ukuran tabel membengkak (*bloated*) dari 18 GB menjadi 112 GB dalam kurun waktu 7 hari.
  2. Latensi query P99 melonjak drastis dari 4ms menjadi 480ms.
  3. Disk I/O utilisation mencapai batas saturasi 100% (*IOPS starvation*), menyebabkan read replika mengalami *replication lag* hingga hitungan jam.

#### Investigasi Akar Masalah (*Root Cause Analysis*)
Pengecekan statistik operasional pada tabel dan indeks:
```sql
SELECT 
    relname, 
    n_tup_ins, 
    n_tup_upd, 
    n_tup_hot_upd,
    ROUND((n_tup_hot_upd::numeric / NULLIF(n_tup_upd, 0)::numeric) * 100, 2) AS hot_ratio
FROM pg_stat_user_tables 
WHERE relname = 'wallet_balances';
```
* **Temuan Investigasi**:
  1. Rasio `n_tup_hot_upd` hanya berada pada angka **2.1%**!
  2. Setiap update saldo mengeksekusi: `UPDATE wallet_balances SET balance = balance + $1, updated_at = NOW() WHERE wallet_id = $2;`.
  3. Ditemukan adanya redundansi indeks: tabel memiliki 6 buah indeks sekunder terpisah, di antaranya:
     * `idx_wallet_status ON wallet_balances(status);`
     * `idx_wallet_updated_at ON wallet_balances(updated_at);` <-- **Akar Masalah**
  4. Indeks pada kolom `updated_at` secara sistematis mematahkan kelayakan HOT (*HOT qualification*) pada setiap query update, memaksa engine menulis 6 pointer indeks baru untuk setiap mutasi baris data tunggal.
  5. Konfigurasi `fillfactor` tabel masih bernilai default `100`, sehingga tidak ada alokasi *free space* tersisa di dalam page untuk penulisan versi tuple baru secara lokal.

#### Desain Solusi Rekayasa & Eksekusi Perbaikan

##### Fase 1: Eliminasi Indeks yang Menjadi Hambatan HOT
Kolom `updated_at` tidak pernah di-filter langsung oleh query operasional OLTP, melainkan hanya digunakan oleh batch analitik tengah malam. Kami menghapus indeks individual tersebut dan membuat partial index jika benar-benar dibutuhkan.
```sql
-- Dijalankan secara online tanpa mengunci transaksi operasional
DROP INDEX CONCURRENTLY idx_wallet_updated_at;
```

##### Fase 2: Rekonfigurasi Tabel untuk HOT Space Provisioning
Kami mengubah parameter fisik tabel untuk menyisakan ruang sebesar 20% pada setiap heap block khusus untuk penulisan delta tuple lokal:
```sql
ALTER TABLE wallet_balances SET (fillfactor = 80);
```

##### Fase 3: Defragmentasi & Remediasi Bloat Tanpa Downtime
Untuk menulis ulang heap data dan indeks yang telah rusak parah akibat fragmentasi tanpa penguncian eksklusif (`AccessExclusiveLock` yang memicu pemadaman layanan):
```sql
-- Langkah 1: Reindex B-Tree secara konkuren di background
REINDEX TABLE CONCURRENTLY wallet_balances;

-- Langkah 2: Menggunakan utilitas open-source 'pg_repack' untuk menata ulang heap fisik
-- Bash execute:
-- pg_repack -h 127.0.0.1 -U postgres -d core_db -t wallet_balances --no-kill-backend
```

##### Hasil Akhir (Post-Mortem Metrics)
* Rasio efisiensi HOT melonjak dari **2.1%** ke **89.4%**.
* Ukuran fisik tabel turun dari **112 GB** ke **21 GB** (penghematan disk ~81%).
* I/O Writes terpotong hingga 68% pada storage array NVMe.
* Latensi pembaruan P99 stabil di angka **3.8 ms**.

---

### 9. Trade-offs Architecture Matrix

Setiap keputusan optimasi penyimpanan melibatkan konsekuensi arsitektural yang berlawanan (*two-edged sword*):

```
                        KOMPROMI DESAIN DB ENGINE
                        
           Throughput Tulis (Write TPS)
                    ▲
                   / \
                  /   \
                 /     \
   Fillfactor 70%       Indeks Ekstensif (Covering, GIN)
   HOT Optimal          Query Baca Sangat Cepat (Index-Only)
   Ukuran Heap +30%     Write Amplification Parah & Bloat
               /         \
              /           \
             ▼─────────────▼
    Efisiensi Ruang Disk  <---->  Latensi Baca Query Tunggal (P99)
     (Storage Footprint)
```

| Dimensi Rekayasa | Opsi A | Opsi B | Analisis Trade-off Enterprise |
| :--- | :--- | :--- | :--- |
| **Penyetelan Fillfactor** | `fillfactor = 100` (Default) | `fillfactor = 70 - 85` | Nilai `100` meminimalkan jejak disk untuk tabel append-only (*insert-only*). Mengurangi nilai ke `70-85` membuang 15-30% ruang disk secara sengaja, namun menghemat ribuan IOPS write amplification pada tabel dengan tingkat mutasi update tinggi berkat HOT optimization. |
| **Metode Akses JSONB** | `jsonb_ops` (GIN) | `jsonb_path_ops` (GIN) | `jsonb_ops` mendukung semua variasi operator (`?`, `?|`, `?&`, `@>`), namun menghasilkan footprint file index masif. `jsonb_path_ops` hanya mendukung operator `@>`, namun ukurannya 60% lebih kompak dan traversal pencarian jauh lebih cepat. |
| **Covering Index (`INCLUDE`)** | Tanpa Kolom `INCLUDE` (Heap Scan) | Dengan Kolom `INCLUDE` (Index-Only) | Menghilangkan beban akses pembacaan Heap Page secara total (mengurangi disk IO), namun menaikkan beban memori `shared_buffers` karena leaf node B-Tree menjadi lebih besar serta meniadakan HOT jika kolom non-key ikut di-update. |
| **Granularitas BRIN** | `pages_per_range = 16` | `pages_per_range = 128` | Semakin kecil nilai range, semakin presisi pemfilteran data dan semakin sedikit false-positive reads, namun ukuran file indeks membesar. Semakin besar nilai range, indeks semakin kecil namun beban filter CPU/IO saat scan meningkat. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Anti-Pattern: Melanggar Prinsip Left-Most Prefix B-Tree
* **Kesalahan**: Membuat composite index `(status, created_at, merchant_id)` tetapi query yang dijalankan adalah:
  ```sql
  SELECT * FROM transactions WHERE created_at >= NOW() - INTERVAL '1 day';
  ```
* **Dampak**: Engine tidak dapat melintasi B-tree secara langsung; terjadi `Index Skip Scan` yang lambat atau degradasi total ke `Seq Scan`.
* **Solusi**: Aturan kardinalitas: Letakkan kolom filter kesetaraan (*equality*) dengan selektivitas tertinggi di posisi paling kiri, diikuti kolom jangkauan (*range*).

#### 10.2 Anti-Pattern: Menggunakan Fungsi Non-Imutabel pada Expression Index
* **Kesalahan**: 
  ```sql
  CREATE INDEX idx_bad ON events ((created_at::date)); -- Gagal jika timezone dinamis
  -- Atau:
  CREATE INDEX idx_invalid_func ON orders (abs(total_amount)) WHERE status = 'PAID'; 
  -- Error: functions in index expression must be marked IMMUTABLE
  ```
* **Solusi**: Pastikan fungsi yang diindeks berstatus `IMMUTABLE` secara definitif di katalog sistem (bukan `STABLE` atau `VOLATILE`).

#### 10.3 Deteksi & Diagnostik Index Bloat
Query operasional DBA untuk menghitung estimasi pemborosan ruang (*index bloat*) tanpa mengunci tabel:
```sql
SELECT
    current_database(),
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(i.indexrelid)) AS index_size,
    ROUND(
        CASE WHEN s.leaf_pages > 0 THEN
            (1.0 - (s.leaf_fragmentation / 100.0)) * 
            (s.free_space::numeric / (s.leaf_pages * (current_setting('block_size')::numeric))) * 100
        ELSE 0 END, 2
    ) AS estimated_bloat_percent
FROM pg_stat_user_indexes u
JOIN pg_index i ON u.indexrelid = i.indexrelid
CROSS JOIN LATERAL pgstatindex(quote_ident(u.schemaname) || '.' || quote_ident(u.indexname)) s
WHERE i.indisvalid
  AND pg_relation_size(i.indexrelid) > 10 * 1024 * 1024 -- Hanya filter index > 10MB
ORDER BY pg_relation_size(i.indexrelid) DESC;
```

#### 10.4 Remediasi Indeks Tidak Valid (*Invalid Indexes*)
Operasi `CREATE INDEX CONCURRENTLY` yang dibatalkan paksa atau mengalami kegagalan akibat *deadlock* / pelanggaran *unique constraint* akan meninggalkan index stub berstatus **INVALID**. Index ini tidak pernah digunakan oleh query planner, namun **tetap mengonsumsi operasi write WAL pada setiap mutasi DML**.

* **Langkah Deteksi**:
  ```sql
  SELECT 
      schemaname, 
      relname AS table_name, 
      indexrelname AS index_name,
      pg_size_pretty(pg_relation_size(indexrelid)) AS wasted_size
  FROM pg_stat_user_indexes
  JOIN pg_index USING (indexrelid)
  WHERE indisvalid = false;
  ```
* **Langkah Perbaikan**:
  ```sql
  -- Jatuhkan index invalid dan ulangi pembuatan
  DROP INDEX CONCURRENTLY <index_name_invalid>;
  ```

---

### 11. Best Practices & Production Checklist

#### Checklist Perancangan & Pemeliharaan Indeks
- [ ] **Audit Rasio Pemanfaatan Indeks**: Jalankan audit triwulanan menggunakan metrik `pg_stat_user_indexes`. Jika `idx_scan = 0` pada tabel yang aktif berjalan lebih dari 30 hari, eliminasi indeks tersebut (kecuali indeks penegak *Unique Constraint*).
- [ ] **Alokasikan Fillfactor Secara Proaktif**: Terapkan `fillfactor = 80-90` secara eksplisit pada tabel yang memiliki rasio `UPDATE` melebihi 25% dari total beban transaksi DML.
- [ ] **Wajib Gunakan Klausa CONCURRENTLY**: Jangan pernah mengeksekusi `CREATE INDEX`, `DROP INDEX`, atau `REINDEX` di *environment* produksi tanpa parameter `CONCURRENTLY`, untuk menghindari antrean *exclusive lock starvation* yang berisiko menjatuhkan aplikasi.
- [ ] **Gunakan Kolom Dedikasi UUID v7 Daripada UUID v4**: Nilai acak murni dari UUID v4 menghancurkan struktur lokalisasi cache B-Tree (*cache locality degradation*) dan memicu *random page write*. UUID v7 memiliki pengurutan berbasis waktu (*time-ordered sequential component*) yang ramah B-tree traversal.
- [ ] **Gunakan Algoritma Kompresi LZ4 untuk TOAST (PG 14+)**: Ubah kompresi bawaan dari `pglz` ke `lz4` untuk memotong waktu latensi CPU dekompresi atribut besar:
  ```sql
  ALTER TABLE document_store ALTER COLUMN content_payload SET COMPRESSION lz4;
  ```
- [ ] **Jadwalkan Integritas Fisik Indeks via `pg_amcheck`**:
  ```bash
  # Eksekusi terjadwal mingguan via cron job
  amcheck -h 127.0.0.1 -U postgres -d enterprise_db --install-missing --verbose
  ```

---

### 12. Hands-on Practice

Simpan seluruh skrip latihan mandiri berikut ke dalam direktori: `hands-on/m02/`.

#### File: `hands-on/m02/01_inspect_storage.sql`
```sql
-- Latihan 1: Mengamati Anatomi Slotted Page dan HOT Chains Secara Langsung
CREATE EXTENSION IF NOT EXISTS pageinspect;

DROP TABLE IF EXISTS hot_demo;
CREATE TABLE hot_demo (
    id INT,
    payload TEXT,
    val INT
) WITH (fillfactor = 70);

-- Pasang indeks HANYA pada kolom 'id'
CREATE INDEX idx_hot_demo_id ON hot_demo (id);

-- Masukkan satu record data
INSERT INTO hot_demo VALUES (1, 'initial_state', 100);

-- Ambil koordinat TID data
SELECT ctid, xmin, xmax, * FROM hot_demo WHERE id = 1;

-- Update kolom non-indeks 2 kali berurutan
UPDATE hot_demo SET val = 101 WHERE id = 1;
UPDATE hot_demo SET val = 102 WHERE id = 1;

-- Amati page header dan pertambahan line pointer
SELECT 
    lp, 
    lp_off, 
    lp_flags, 
    lp_len,
    t_ctid,
    t_infomask::bit(16) AS infomask,
    t_infomask2::bit(16) AS infomask2
FROM heap_page_items(get_raw_page('hot_demo', 0));

-- Evaluasi isi leaf index: Perhatikan bahwa pointer B-Tree TETAP mengarah ke lp 1!
SELECT * FROM bt_page_items('idx_hot_demo_id', 1);
```

#### File: `hands-on/m02/02_toast_internals.sql`
```sql
-- Latihan 2: Investigasi Perilaku TOAST Threshold & Out-of-Line Slicing
DROP TABLE IF EXISTS toast_experiment;
CREATE TABLE toast_experiment (
    id INT,
    regular_data TEXT,
    large_data TEXT
);

-- Atur strategi penyimpanan secara eksplisit
ALTER TABLE toast_experiment ALTER COLUMN large_data SET STORAGE EXTENDED;

-- Masukkan record di bawah batas TOAST (~500 bytes)
INSERT INTO toast_experiment VALUES (1, 'small', repeat('A', 500));

-- Masukkan record di atas ambang batas TOAST (~200 KB string)
INSERT INTO toast_experiment VALUES (2, 'large', repeat('B', 200000));

-- Periksa ukuran penyimpanan tabel utama vs ukuran tabel TOAST
SELECT 
    relname,
    pg_size_pretty(pg_relation_size(oid)) AS main_storage,
    pg_size_pretty(pg_total_relation_size(reltoastrelid)) AS toast_storage
FROM pg_class 
WHERE relname = 'toast_experiment';

-- Membaca langsung potongan chunk dari tabel TOAST internal
DO $$
DECLARE
    toast_rel_name TEXT;
BEGIN
    SELECT relname INTO toast_rel_name 
    FROM pg_class 
    WHERE oid = (SELECT reltoastrelid FROM pg_class WHERE relname = 'toast_experiment');
    
    EXECUTE format('SELECT chunk_id, chunk_seq, length(chunk_data) FROM pg_toast.%I LIMIT 5', toast_rel_name);
END $$;
```

#### File: `hands-on/m02/03_advanced_indexing.sql`
```sql
-- Latihan 3: Pembuktian Efisiensi BRIN vs B-Tree pada Rangkaian Data Besar
DROP TABLE IF EXISTS telemetry_metrics;
CREATE TABLE telemetry_metrics (
    recorded_at TIMESTAMPTZ NOT NULL,
    device_id INT NOT NULL,
    cpu_usage NUMERIC(4,2)
);

-- Injeksi 1.000.000 data sequential timeseries
INSERT INTO telemetry_metrics (recorded_at, device_id, cpu_usage)
SELECT 
    ts,
    (random() * 500)::INT,
    (random() * 100)::NUMERIC(4,2)
FROM generate_series(
    '2024-01-01 00:00:00'::timestamptz,
    '2024-01-01 00:00:00'::timestamptz + INTERVAL '1000000 seconds',
    INTERVAL '1 second'
) AS ts;

-- Buat B-Tree Index dan BRIN Index pada target kolom yang sama
CREATE INDEX idx_telemetry_btree ON telemetry_metrics USING btree (recorded_at);
CREATE INDEX idx_telemetry_brin  ON telemetry_metrics USING brin (recorded_at) WITH (pages_per_range = 128);

-- Evaluasi Perbandingan Ukuran Fisik
SELECT 
    pg_size_pretty(pg_relation_size('idx_telemetry_btree')) AS btree_size,
    pg_size_pretty(pg_relation_size('idx_telemetry_brin'))  AS brin_size;

-- Uji Eksekusi Range Query Menggunakan BRIN
SET enable_seqscan = OFF;
SET enable_indexscan = OFF;
SET enable_bitmapscan = ON;

EXPLAIN (ANALYZE, BUFFERS)
SELECT AVG(cpu_usage) FROM telemetry_metrics 
WHERE recorded_at BETWEEN '2024-01-05' AND '2024-01-06';
```

---

### 13. Exercises

#### Level Easy
Terdapat tabel `customers` yang menyimpan 5 juta baris data dengan kolom `is_active` (boolean). Nilai `false` hanya mencakup 0,5% dari keseluruhan data tabel, sedangkan sisanya bernilai `true`. Aplikasi memiliki modul berkala yang memproses data non-aktif via:
`SELECT * FROM customers WHERE is_active = false;`
* **Tugas**: Buatlah rancangan indeks paling optimal yang meminimalkan penggunaan memori dan disk. Sertakan perintah DDL untuk mengujinya.
* **Kriteria Keberhasilan**: Ukuran fisik indeks tidak boleh melebihi 1 MB.

#### Level Medium
Diberikan query pemantauan transaksi e-commerce:
```sql
SELECT order_id, customer_id, total_amount 
FROM orders 
WHERE customer_id = 998822 AND order_status = 'SHIPPED';
```
Indeks yang saat ini aktif adalah `CREATE INDEX idx_orders_cust ON orders(customer_id);`. Query planner mengeksekusi `Bitmap Heap Scan` dan menyentuh ratusan heap blocks.
* **Tugas**: Modifikasi indeks tersebut menggunakan pendekatan *Covering Index* sehingga query beralih menjadi *Index-Only Scan* murni tanpa membaca heap block data tabel utama. Buktikan menggunakan output `EXPLAIN (ANALYZE, BUFFERS)`.

#### Level Hard
Sebuah tabel transaksi settlement finansial bernilai tinggi mengalami lonjakan fragmentasi dead tuple parah karena pembaruan status order:
`PENDING` -> `PROCESSING` -> `SETTLED`.
Sistem tidak dapat menoleransi penurunan performa write akibat pembaruan pointer B-Tree.
* **Tugas**: 
  1. Rancang arsitektur tabel yang menjamin rasio keberhasilan HOT update mencapai minimal 90%.
  2. Tuliskan query otomatisasi pemantauan kesehatan line pointer page (`ItemIdData`) yang memberi sinyal peringatan jika ada satu page heap yang memiliki HOT-chain lebih dari 5 turunan redirect.

---

### 14. Challenge

**Skenario Kasus**: Anda menjabat sebagai Principal Database Reliability Engineer pada unicorn logistik global. Sistem pelacakan armada armada truk mengirimkan koordinat dan telemetri status kargo berbentuk dokumen JSONB setiap 3 detik dari 50.000 unit kendaraan.
* Ukuran penambahan data per hari: 150 juta baris (~80 GB/hari).
* Seluruh kueri operasional armada menyaring data berdasarkan rentang waktu 3 jam terakhir, `truck_id`, dan memeriksa keberadaan bendera JSONB `metadata @> '{"alert": "ENGINE_OVERHEAT"}'`.
* Database mengalami masalah fatal: Autovacuum tidak mampu mengimbangi laju pembuatan dead tuple, B-Tree konvensional berukuran 400 GB sehingga melebihi kapasitas `shared_buffers` RAM (RAM total 256 GB), dan latensi `INSERT` terdegradasi parah akibat kompresi default TOAST.

**Persyaratan Tantangan**:
Rancang dokumen arsitektur dan skrip implementasi menyeluruh yang mencakup:
1. Skema partisi rentang harian yang dipadukan dengan strategi indeks komposit minimal.
2. Penentuan index non-B-Tree yang tepat untuk ekspresi JSONB dengan eliminasi memory pressure.
3. Konfigurasi penyimpanan fisik kolom (TOAST strategy & compression algorithms).
4. Formula maintenance daemon autovacuum per-tabel (*custom scale factors*) agar tidak terjadi starvation I/O.
5. Strategi verifikasi konsistensi indeks tanpa downtime menggunakan utilitas core database engine.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Berapa ukuran default satu block/page pada instalasi standar PostgreSQL?**
   * A. 4 KB
   * B. 8 KB
   * C. 16 KB
   * D. 64 KB
2. **Komponen apa di dalam header heap page yang bertumbuh dari arah atas ke bawah (downwards)?**
   * A. Special Space
   * B. HeapTupleHeaderData
   * C. Line Pointer Array (`ItemIdData`)
   * D. Free Space Map
3. **Kapan PostgreSQL memicu penyimpanan atribut menggunakan mekanisme TOAST?**
   * A. Ketika sebuah tuple melebihi `TOAST_TUPLE_THRESHOLD` (secara default ~2 KB).
   * B. Ketika tabel mencapai 1 juta baris.
   * C. Ketika query menggunakan klausa `ORDER BY` pada kolom text.
   * D. Hanya saat tipe data yang digunakan adalah `BLOB` biner murni.
4. **Apa tujuan utama penambahan klausa `INCLUDE` pada pembuatan B-Tree Index?**
   * A. Menjadikan kolom include sebagai predikat filter range pencarian B-Tree.
   * B. Memungkinkan *Index-Only Scan* dengan memuat muatan kolom tambahan pada leaf level tanpa memperbesar internal nodes.
   * C. Menjamin bahwa kolom include memiliki nilai constraint `UNIQUE`.
   * D. Mengaktifkan kompresi gzip pada file indeks.
5. **Kondisi manakah yang menyebabkan mutasi data `UPDATE` GAGAL memanfaatkan optimasi HOT (Heap-Only Tuples)?**
   * A. Nilai atribut yang diubah berukuran lebih kecil dari versi sebelumnya.
   * B. Update dilakukan di dalam blok transaksi eksplisit.
   * C. Kolom yang diperbarui terdaftar sebagai salah satu elemen kolom pada suatu index tabel tersebut.
   * D. Page target memiliki free space sebesar 40%.

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Pada arsitektur Lehman-Yao B-Tree yang digunakan PostgreSQL, apa peran dari *High Key* dan *Right-link Pointer* pada leaf page?**
   * A. Untuk mengenkripsi data indeks di media penyimpanan fisik.
   * B. Memungkinkan transversal pencarian pembaca berjalan secara konkuren tanpa harus memblokir atau diblokir oleh proses *page split*.
   * C. Menghubungkan langsung leaf node B-Tree ke katalog sistem `pg_class`.
   * D. Menggantikan peran transaksi Write-Ahead Logging (WAL).
7. **Bagaimana mekanisme fitur B-Tree Deduplication (PostgreSQL 13+) menghemat konsumsi media penyimpanan?**
   * A. Menghapus baris yang identik secara otomatis dari tabel utama.
   * B. Menggabungkan kunci indeks bernilai duplikat ke dalam format Posting List yang menampung multi-TID di dalam satu index tuple fisik.
   * C. Menjalankan kompresi algoritma Snappy di level sistem operasi.
   * D. Membatasi penulisan entri indeks hanya untuk transaksi yang sudah committed.
8. **Kapan tipe indeks BRIN (*Block Range Index*) jauh lebih unggul dibandingkan indeks B-Tree standar?**
   * A. Pada data dengan distribusi acak tinggi yang membutuhkan pencarian *exact match* P99 instan.
   * B. Pada tabel berukuran raksasa multi-gigabyte/terabyte yang nilai datanya memiliki korelasi fisik kuat terhadap urutan penulisan di storage (*physical clustering*).
   * C. Pada kolom teks yang memerlukan fitur *fuzzy string matching* dengan operator regex `~`.
   * D. Pada tabel yang menerima beban operasi `DELETE` acak secara terus-menerus.
9. **Apa fungsi informasi pada file *Visibility Map* (VM) dalam konteks optimasi eksekusi query *Index-Only Scan*?**
   * A. Menentukan apakah index tuple terkunci oleh transaksi aktif.
   * B. Menyimpan cadangan data kolom TOAST yang hilang.
   * C. Memberi tanda apakah seluruh tuple dalam sebuah heap page tertentu valid dan terlihat (*visible*) oleh semua transaksi aktif, sehingga pembacaan heap data fisik dapat diabaikan seutuhnya.
   * D. Memetakan lokasi penyimpanan replika data di standby server.
10. **Perbedaan struktural utama antara operator kelas GIN `jsonb_ops` dan `jsonb_path_ops` adalah:**
    * A. `jsonb_ops` tidak mendukung format data nested, sedangkan `jsonb_path_ops` mendukungnya.
    * B. `jsonb_path_ops` hanya membuat hash dari keseluruhan *path and value expression*, sehingga menghasilkan ukuran indeks jauh lebih kompak namun membatasi ragam operator kueri ke containment (`@>`).
    * C. `jsonb_ops` hanya dapat digunakan pada data bertipe XML.
    * D. `jsonb_path_ops` membutuhkan ekstensi pihak ketiga dan tidak kompatibel dengan PostgreSQL native.

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario Kasus 1**: Tim DBA mendeteksi indeks berukuran 45 GB pada kolom transaksi finansial. Setelah dicek menggunakan `pgstatindex`, nilai `leaf_fragmentation` tercatat sebesar 68% dan `free_space` pada leaf page mencapai 60%. Selama jam operasional bank, transaksi DML berjalan sangat intensif. Tindakan perbaikan apa yang paling presisi dan berisiko paling minimal terhadap operasional aplikasi?
    * A. Jalankan `VACUUM FULL` pada tabel transaksi secara langsung.
    * B. Jalankan `DROP INDEX` diikuti dengan `CREATE INDEX`.
    * C. Jalankan `REINDEX INDEX CONCURRENTLY` untuk membangun leaf pages baru yang terorganisir di latar belakang tanpa mengunci proses DML baca maupun tulis.
    * D. Turunkan kapasitas memori `shared_buffers` dan lakukan restart instance database.
12. **Skenario Kasus 2**: Anda menjalankan perintah `EXPLAIN (ANALYZE, BUFFERS)` untuk sebuah kueri yang memanfaatkan B-Tree Covering Index. Anda menemukan output: `Index Only Scan ... Heap Fetches: 423010`. Analisis teknis apa yang menjelaskan mengapa *Heap Fetches* bernilai sangat tinggi padahal mode eksekusi adalah *Index Only Scan*?
    * A. Indeks mengalami korupsi fisik dan memerlukan `amcheck`.
    * B. Bit status *all-visible* pada Visibility Map (VM) untuk blok-blok heap terkait belum terpasang atau usang karena daemon Autovacuum belum sempat memproses page tersebut pasca-mutasi masif.
    * C. Parameter `work_mem` dialokasikan terlalu kecil oleh optimizer.
    * D. Kolom pada klausa `INCLUDE` memiliki tipe data biner yang tidak didukung.
13. **Skenario Kasus 3**: Sebuah tabel audit event time-series bervolume 500 juta baris menggunakan BRIN index pada kolom `created_at`. Query pelaporan harian mendadak mengalami degradasi drastis menjadi lambat secara konsisten. Saat dicek, data baru dimasukkan tidak berurutan lagi karena sistem baru saja memulihkan batch data lampau (*backfill historical data*) yang disisipkan ke halaman heap paling akhir. Apa penyebab teknis degradasi ini dan bagaimana solusinya?
    * A. BRIN index rusak permanen; harus dikonversi menjadi GiST index.
    * B. Nilai Min/Max pada block range halaman baru menjadi sangat lebar dan overlapping akibat backfill data lampau, menghancurkan selektivitas filter range BRIN. Solusinya: Tata ulang susunan fisik tabel via `CLUSTER` atau partisi, lalu jalankan `brin_summarize_new_values()`.
    * C. Storage engine PostgreSQL menonaktifkan BRIN index secara otomatis jika baris melebihi 100 juta.
    * D. Fitur kompresi LZ4 mengalami failure pada kernel I/O layer.

---

### Kunci Jawaban & Rasional Evaluasi

#### Bagian 1
1. **B**: Ukuran blok page default kompilasi engine PostgreSQL adalah 8192 bytes (8 KB).
2. **C**: Line Pointer Array (`ItemIdData`) bertumbuh dari header ke arah bawah (*downward*), sedangkan tuple data diisi dari batas akhir page ke arah atas (*upward*).
3. **A**: Nilai ambang batas default adalah `TOAST_TUPLE_THRESHOLD`, yaitu sekitar seperempat dari ukuran page (kurang lebih 2 KB).
4. **B**: Klausa `INCLUDE` menyimpan data payload non-key hanya pada level leaf node B-Tree, memungkinkan *Index-Only Scan* tanpa menambah overhead pemilahan pada *internal branching pages*.
5. **C**: Prasyarat utama HOT adalah kolom yang di-update BUKAN merupakan bagian dari definisi indeks apa pun pada tabel tersebut.

#### Bagian 2
6. **B**: Struktur pohon Lehman-Yao B-Tree menyematkan right-link dan High Key pada setiap node untuk memastikan search scan reader dapat beralih ke node saudara (*sibling*) tanpa lock stall saat terjadi concurrent page split.
7. **B**: Deduplikasi pada B-Tree (PG 13+) memadatkan duplikat key yang sama ke dalam struktur posting list terintegrasi, menghemat konsumsi bytes leaf node secara drastis.
8. **B**: BRIN hanya menyimpan agregat batas bawah dan atas (Min/Max) per rentang blok heap (cth: 128 blok), sehingga sangat efisien dan berukuran mini khusus pada data terurut linier (*physically clustered*).
9. **C**: Index-Only Scan memverifikasi status *all-visible* pada Visibility Map (VM). Jika bit bernilai 1, tuple dipastikan visible untuk semua transaksi tanpa perlu menyentuh buffer heap page fisik.
10. **B**: Operator class `jsonb_path_ops` melakukan teknik hashing pada kombinasi path dan value, menghemat ukuran indeks secara drastis dibandingkan `jsonb_ops` namun terbatas pada kueri containment `@>`.

#### Bagian 3
11. **C**: `REINDEX TABLE/INDEX CONCURRENTLY` membangun salinan struktur biner indeks baru tanpa mengunci proses DML aplikasi, menyelesaikan masalah fragmentasi dan bloat secara online.
12. **B**: Jika Visibility Map (VM) belum dibersihkan dan ditandai *all-visible* oleh vacuum, engine wajib mengakses heap fisik (*Heap Fetches*) untuk memverifikasi MVCC visibility tuple tersebut via snapshot transaksi.
13. **B**: Nilai Min/Max pada BRIN range menjadi terdistorsi saat data lampau disisipkan di blok akhir, merusak akurasi pemilahan blok data. Restrukturisasi fisik diperlukan untuk mengembalikan korelasi sekuensial.

---

### 16. Summary

1. **Storage Subsystem Core**: Penyimpanan data PostgreSQL bertumpu pada **Slotted Page Architecture (8 KB)**. Hubungan antara indeks dan data fisik diikat oleh tuple pointer biner (`ctid`), di mana line pointer (`ItemIdData`) menjadi jembatan offset langsung ke baris data riil.
2. **Mekanisme Penanganan Data Ekstrem**: Kolom data yang melompat batas ukuran page ditangani via subsistem **TOAST** (Compress dan Chunk Out-of-Line). Sedangkan pertumbuhan beban pembaruan data (*write load*) diredam melalui optimasi **HOT (Heap-Only Tuples)** yang menghilangkan write amplification pada indeks sekunder dengan syarat ketersediaan *free space* lokal yang memadai (`fillfactor`).
3. **Spesialisasi Access Method**: Tidak ada satu indeks universal untuk seluruh domain masalah. **B-Tree** adalah standar umum transactional equality/range; **BRIN** menjadi pilihan optimal untuk data time-series terurut berukuran terabyte; sedangkan **GIN** merupakan fondasi pencarian containment array dan dokumen terstruktur JSONB.
4. **Operational Excellence**: Keandalan arsitektur database pada level enterprise diukur dari kemampuan pemeliharaan tanpa gangguan layanan (*zero downtime maintenance*). Penggunaan utilitas `pageinspect` untuk observasi internal, eliminasi *bloat* berkala via `REINDEX CONCURRENTLY`, dan penyelarasan siklus hidup tuple melalui parameter *vacuum tuning* adalah kompetensi mutlak bagi seorang Senior PostgreSQL DBA.