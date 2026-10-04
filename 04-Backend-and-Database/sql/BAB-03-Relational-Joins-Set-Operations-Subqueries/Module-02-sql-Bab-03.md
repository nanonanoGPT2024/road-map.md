# Kurikulum Enterprise: Relational Joins, Set Operations, & Subqueries
## Bab 03 - Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Internal Engine Operator**: Menguraikan algoritma eksekusi relasional internal (*Nested Loop Join*, *Sort-Merge Join*, *Hash Join*) beserta mekanika alokasi memori internal database (*Build Phase*, *Probe Phase*, *Disk Spill*).
- **Mendiagnosis Rencana Eksekusi (Query Plan)**: Menginterpretasikan metrik komputasi `EXPLAIN (ANALYZE, BUFFERS)` untuk mengidentifikasi anomali estimasi kardinalitas (*cardinality misestimation*), *accidental cartesian products*, dan I/O bottleneck.
- **Mengimplementasikan Pola Join Kompleks Tingkat Lanjut**: Merancang query menggunakan *Correlated Lateral Joins* (`LATERAL`), optimalisasi relasional *Anti-Join* (`NOT EXISTS` vs `LEFT JOIN / IS NULL`), dan rekonsiliasi dataset masif berbasis *Set Operations* terindeks.
- **Mencegah Masalah Kinerja Subquery**: Mengatasi kegagalan optimasi *subquery unnesting*/*decorrelation* yang dipicu oleh subquery non-teroptimasi pada engine RDBMS modern.
- **Mendesain Arsitektur Join Terdistribusi**: Mengonfigurasi strategi mitigasi query data terdistribusi (*Broadcast Join* vs *Hash Partitioned/Shuffle Join*) untuk mencegah masalah *data skew* dan saturasi jaringan.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, Anda wajib menguasai:
- Sintaksis dasar SQL ANSI: `INNER JOIN`, `LEFT/RIGHT OUTER JOIN`, `FULL JOIN`, `CROSS JOIN`, `UNION [ALL]`, `INTERSECT`, `EXCEPT`.
- Struktur data dasar: B-Tree Index, Hash Table, Direct Addressing, Inverted Index.
- Konsep ACID transaksi, isolasi transaksi (*MVCC*), dan representasi data pada *heap pages*.
- Pengetahuan operasional dasar membaca `EXPLAIN` format teks standar pada PostgreSQL atau MySQL 8.x.

---

### 3. Concept & Internal Architecture

Dalam arsitektur basis data relasional enterprise (seperti PostgreSQL, Oracle, atau Microsoft SQL Server), SQL adalah bahasa deklaratif. Anda tidak menentukan *bagaimana* data diambil, melainkan *apa* yang dibutuhkan. Tanggung jawab pemilihan algoritma eksekusi diserahkan sepenuhnya kepada **Cost-Based Optimizer (CBO)**.

```
                    +---------------------------+
                    | SQL Query (AST / Logical) |
                    +---------------------------+
                                  |
                                  v
                    +---------------------------+
                    | Query Rewriter / Flattener|
                    | (Decorrelation, Flatten)  |
                    +---------------------------+
                                  |
                                  v
                    +---------------------------+
                    |   Cost-Based Optimizer    |
                    | (Catalog Stats, Heuristics)|
                    +---------------------------+
                                  |
       +--------------------------+--------------------------+
       |                          |                          |
       v                          v                          v
+---------------+          +---------------+          +---------------+
|  Nested Loop  |          |   Hash Join   |          |  Merge Join   |
|     Join      |          | (Build/Probe) |          | (Sort/Merge)  |
+---------------+          +---------------+          +---------------+
       |                          |                          |
       +--------------------------+--------------------------+
                                  |
                                  v
                     +-------------------------+
                     | Storage Engine / Buffer |
                     | (RAM / Disk Temp File)  |
                     +-------------------------+
```

#### A. Tiga Algoritma Fisik Join Utama

##### 1. Nested Loop Join (NLJ)
- **Mekanisme**: Membaca baris satu per satu dari relasi luar (*outer table/driving table*), kemudian untuk setiap baris tersebut, memindai relasi dalam (*inner table*).
- **Variasi**:
  - *Standard NLJ*: Memindai seluruh inner relation secara sekuensial ($O(N \times M)$).
  - *Index Nested Loop Join (INLJ)*: Menggunakan indeks pada inner relation untuk mencari baris yang cocok ($O(N \log M)$).
  - *Block Nested Loop (BNL)*: Memuat batch baris outer relation ke dalam memori (*join buffer*) untuk mengurangi sweep I/O inner table.
- **Kondisi Optimal**: Outer table berukuran sangat kecil (setelah proses filtering), dan inner table memiliki indeks yang sangat selektif pada atribut predikat join.

##### 2. Hash Join
- **Mekanisme**:
  - **Build Phase**: Optimizer memilih relasi yang lebih kecil (*build input*), membaca seluruh baris yang lolos filter, membuat fungsi hash pada kolom predikat join, lalu memasukkannya ke dalam *in-memory hash table*.
  - **Probe Phase**: Optimizer membaca relasi yang lebih besar (*probe input*), menghitung hash pada kolom join dari setiap baris, lalu mencocokkannya ke dalam hash table.
- **Kondisi Khusus (Memory Spills)**: Jika hash table melebihi batas memori lokal per query (misal `work_mem` di PostgreSQL), hash table akan dipecah menjadi batch-batch partisi (*Grace Hash Join* atau *Hybrid Hash Join*). Partisi yang tidak muat di memori ditulis ke disk (*Temp Spill/TempDB*), menghasilkan lonjakan latency I/O.
- **Batasan**: Hanya bekerja pada predikat kesetaraan (*equi-joins*, operator `=`).

##### 3. Sort-Merge Join (SMJ)
- **Mekanisme**:
  - **Sort Phase**: Kedua relasi diurutkan berdasarkan kolom join jika belum terurut secara fisik (misal via B-Tree Index).
  - **Merge Phase**: Dua pointer berjalan beriringan membaca kedua relasi secara terurut. Nilai yang cocok dipancarkan (*emitted*). Jika terdapat duplikasi nilai pada kolom join, pointer inner table akan mundur (*mark and restore / backtrack*).
- **Kondisi Optimal**: Kedua dataset berukuran sangat besar, tidak muat di memori untuk Hash Join, dan predikat join mendukung pengurutan ($=, <, <=, >, >=$). Sangat murah jika data input sudah terurut dari index scan sebelumnya.

#### B. Subquery Unnesting, Flattening, & Decorrelation
Subquery sering ditulis dalam bentuk bersarang (*nested*). Mesin database enterprise modern berupaya melakukan dekonstruksi:
- **Correlated Subquery** dievaluasi berulang-ulang untuk setiap baris dari query luar jika tidak didekorelasi.
- **Query Decorrelation Engine** mengubah korelasi relasional menjadi operasi set/join (biasanya *Semi-Join* atau *Anti-Join*). 
- Jika subquery memuat fungsi non-deterministik, aggregation kompleks tanpa partisi, atau batasan sintaksis kaku, optimizer bisa gagal melakukan flattening, memaksa eksekutor jatuh ke *Subplan Execution* bertingkat (performa $O(N \times M)$).

#### C. Distributed Join Mechanics (Citus, CockroachDB, BigQuery, Snowflake)
- **Broadcast Join**: Node koordinator mereplikasi seluruh isi tabel dimensi (ukuran kecil) ke setiap node pekerja (*worker node*). Setiap worker melakukan local join dengan partisi data faktanya.
- **Hash Partitioned / Shuffle Join**: Ketika kedua tabel sama-sama besar, kedua tabel di-*re-hash* berdasarkan kolom join dan ditransmisikan melintasi jaringan (*network shuffle*) sehingga baris dengan hash join key yang sama mendarat di worker node yang sama. Trade-off: Menghasilkan utilisasi bandwidth jaringan yang tinggi.

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Naive SQL Developer) | Pendekatan Enterprise Engineer |
| :--- | :--- | :--- |
| **Pola Join** | Memakai kombinasi `LEFT JOIN` berganda dan filter `WHERE` implisit tanpa memperhatikan urutan kardinalitas data. | Menganalisis *Driving Table*, selektivitas indeks, dan mengontrol eksekusi via *Filter Pushdown* serta struktur kueri terisolasi. |
| **Kueri Negasi** | `WHERE id NOT IN (SELECT foreign_id FROM ...)` | Menggunakan `NOT EXISTS` atau *Anti-Join* formal (`LEFT JOIN ... WHERE right.pk IS NULL`) untuk menjamin optimasi engine dan penanganan nilai `NULL` yang deterministik. |
| **Data Pagination/N-Per-Group** | Window Function berulang `ROW_NUMBER() OVER (...)` di subquery luar tanpa *pushdown optimization*. | Memanfaatkan `CROSS JOIN LATERAL` / `CROSS APPLY` untuk mengeksekusi top-N retrieval secara efisien langsung pada index leaf pages. |
| **Pengelolaan Resource** | Membiarkan CBO melakukan spill ke disk tanpa mitigasi konfigurasi `work_mem` atau indexing strategi. | Mengalokasikan memori deterministik, meniadakan *Temp Spill*, dan memaksa eksekusi in-memory Hash Join / non-backtracking Merge Join. |

---

### 5. How (Workflow Detail)

Alur penulisan dan optimasi join di lingkungan produksi berlatensi rendah:

```
[Mulai: Desain Kueri Kompleks]
               |
               v
1. Identifikasi Cardinality & Volume Data
   - Identifikasi Small Relation (Dimensi/Filter) vs Large Relation (Fakta/Ledger).
               |
               v
2. Tentukan Hubungan & Predikat Join
   - Equi-join (=) atau Range-join (BETWEEN, >=)?
   - Mandatory (INNER) vs Optional (LEFT) vs Set Inversion (ANTI)?
               |
               v
3. Uji Indeksasi Inner Table
   - Apakah kolom target terindeks B-Tree?
   - Apakah tipe data kolom join presisi sama (identik collation, tipe int vs bigint)?
               |
               v
4. Jalankan EXPLAIN (ANALYZE, BUFFERS)
   - Bandingkan "Estimated Rows" vs "Actual Rows".
   - Verifikasi join operator: Hash Join, Merge Join, atau Nested Loop?
               |
               v
5. Deteksi Anomali
   - Terjadi Disk Spill? -> Evaluasi work_mem atau partisi join.
   - Terjadi Hash Join pada tabel masif tanpa filter? -> Tambahkan partition pruning / filter pushdown.
   - Terjadi Nested Loop pada jutaan row? -> Fix index atau run ANALYZE untuk update optimizer stats.
               |
               v
[Selesai: Kueri Optimal Terverifikasi]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Perpustakaan & Katalog
Bayangkan Anda memiliki dua tumpukan data: **Daftar Peminjam (100 orang)** dan **Gudang Buku (1.000.000 buku)**.

- **Nested Loop Join (INLJ)**: Anda membaca 1 nama peminjam, lalu langsung menggunakan sistem katalog komputer (Indeks B-Tree) untuk mengambil buku yang dipinjam. Cepat karena Anda hanya mencari data spesifik sebanyak 100 kali.
- **Hash Join**: Anda menyalin seluruh 100 nama peminjam ke sebuah papan tulis kecil di saku Anda (*Build Phase*). Lalu Anda berjalan menyusuri lorong rak buku satu per satu (*Probe Phase*). Setiap melihat buku, Anda melirik papan tulis saku: "Apakah ini milik salah satu dari 100 orang tersebut?".
- **Sort-Merge Join**: Anda menyuruh asisten perpustakaan mengurutkan seluruh 1.000.000 kartu buku berdasarkan ID anggota, dan 100 kartu peminjam diurutkan juga. Setelah keduanya rapi berurutan dari 1 sampai sekian, Anda tinggal menyejajarkan kedua tumpukan dan membacanya bersamaan dari atas ke bawah secara simultan tanpa bolak-balik.

#### Diagram Algoritma Fisik Hash Join vs Disk Spill

```
                       IN-MEMORY HASH JOIN
                      +-------------------+
                      |   Build Input     |
                      |  (Tabel Kecil)    |
                      +-------------------+
                                |
                         [Hash Function]
                                v
                      +-------------------+
                      | In-Memory Hash Tab|  <--- Muat di RAM (work_mem)
                      +-------------------+
                                ^
                         [Hash Function]
                                |
                      +-------------------+
                      |    Probe Input    |
                      |   (Tabel Besar)   |
                      +-------------------+

-----------------------------------------------------------------------

                 HASH JOIN WITH DISK SPILL (BATCHING)
                      +-------------------+
                      |   Build Input     |
                      +-------------------+
                                |
                         [Hash Function]
                                v
               +----------------------------------+
    RAM        | Batch 0 (RAM)                    |
               +----------------------------------+
    DISK       | Batch 1 (Disk)  | Batch 2 (Disk) |  <--- Melebihi work_mem!
    (I/O SLOW) +-----------------+----------------+       Pecah ke temporary file
```

---

### 7. Simple Example & Practical Example

#### A. Advanced Anti-Join Pattern
Kasus: Temukan data nasabah (*accounts*) yang **tidak pernah** melakukan transaksi dalam 90 hari terakhir. Jangan gunakan pola lambat `NOT IN` yang rentan terhadap masalah `NULL` semantics.

```sql
-- DDL & Data Setup
CREATE TABLE accounts (
    account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_number VARCHAR(32) NOT NULL UNIQUE,
    holder_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE account_transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(account_id),
    amount NUMERIC(15, 2) NOT NULL,
    transaction_date TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_transactions_acc_date 
ON account_transactions (account_id, transaction_date DESC);

-- PRODUCTION PATTERN 1: NOT EXISTS (Anti-Join Semantics)
-- Dianjurkan: Mengembalikan boolean langsung pada index traversal pertama
SELECT a.account_id, a.account_number, a.holder_name
FROM accounts a
WHERE NOT EXISTS (
    SELECT 1 
    FROM account_transactions t
    WHERE t.account_id = a.account_id
      AND t.transaction_date >= CURRENT_TIMESTAMP - INTERVAL '90 days'
);

-- PRODUCTION PATTERN 2: LEFT JOIN / IS NULL (Optimized Outer Join Anti-Join)
-- Optimizer modern kerap mengubah ini menjadi rencana eksekusi Hash/Merge Anti-Join yang identik
SELECT a.account_id, a.account_number, a.holder_name
FROM accounts a
LEFT JOIN account_transactions t 
  ON a.account_id = t.account_id 
 AND t.transaction_date >= CURRENT_TIMESTAMP - INTERVAL '90 days'
WHERE t.transaction_id IS NULL;
```

#### B. Lateral Join (Correlated Subquery Optimization)
Kasus: Untuk setiap nasabah, ambil **tepat 3 transaksi terakhir**. Pendekatan naif menggunakan window function `ROW_NUMBER()` memindai seluruh tabel transaksi (biaya komputasi $O(M)$), sedangkan `LATERAL` mengeksploitasi indeks komposit untuk melompat langsung ke leaf pages target ($O(N \times 3)$).

```sql
-- PRODUCTION PATTERN: Parameterized Top-N per Group via LATERAL
SELECT 
    a.account_id,
    a.account_number,
    latest_tx.transaction_id,
    latest_tx.amount,
    latest_tx.transaction_date
FROM accounts a
CROSS JOIN LATERAL (
    SELECT t.transaction_id, t.amount, t.transaction_date
    FROM account_transactions t
    WHERE t.account_id = a.account_id
    ORDER BY t.transaction_date DESC
    LIMIT 3
) latest_tx;
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Sistem**: Core Financial Clearing & Settlement Engine.
- **Skala Data**: 
  - Tabel `settlement_records`: 650.000.000 baris.
  - Tabel `payment_intents`: 45.000.000 baris (data harian).
- **Insiden Produksi**: Batch job rekonsiliasi harian mengalami degradasi performa: durasi eksekusi melonjak dari **15 menit** menjadi **4 jam 45 menit**, menyebabkan timeout pada antrean downstream Kafka consumer dan mengunci buffer pool storage engine secara masif.

#### Akar Permasalahan (Root Cause Analysis)
Kueri audit awal yang ditulis tim engineer:

```sql
-- KUERI BERMASALAH (SLOW PIPELINE)
SELECT 
    pi.intent_id,
    pi.merchant_id,
    pi.expected_amount,
    sr.settled_amount,
    (SELECT status FROM audit_logs al 
     WHERE al.entity_id = pi.intent_id 
     ORDER BY al.logged_at DESC LIMIT 1) as latest_audit_status
FROM payment_intents pi
JOIN settlement_records sr ON pi.reference_id = sr.reference_number
WHERE pi.created_at >= '2023-10-01 00:00:00+00' 
  AND pi.created_at < '2023-10-02 00:00:00+00';
```

Eksekusi `EXPLAIN (ANALYZE, BUFFERS)` mengungkap dua kegagalan struktural:
1. `pi.reference_id` bertipe data `VARCHAR(64)` sementara `sr.reference_number` bertipe data `VARCHAR(128) COLLATE "C"`. Perbedaan collation dan panjang alokasi menyebabkan optimizer menolak penggunaan B-Tree Index dan fallback ke **Parallel Seq Scan** dengan **Hash Join spill to disk** (mencapai 180 GB temporary files).
2. Subquery `audit_logs` dievaluasi sebagai **Correlated Subplan** sebanyak 45 juta kali, alih-alih di-flatten.

#### Solusi Arsitektur & Kueri Produksi
1. Standardisasi schema collation via migrasi DDL.
2. Penulisan ulang kueri memisahkan deduping fase audit log menggunakan CTE terkomputasi lokal dan optimasi `LATERAL` / Window Aggregate terisolasi.

```sql
-- KUERI SETELAH REMEDIASI
WITH target_intents AS MATERIALIZED (
    SELECT 
        pi.intent_id,
        pi.reference_id,
        pi.merchant_id,
        pi.expected_amount
    FROM payment_intents pi
    WHERE pi.created_at >= '2023-10-01 00:00:00+00' 
      AND pi.created_at < '2023-10-02 00:00:00+00'
),
reconciled_data AS (
    SELECT 
        ti.intent_id,
        ti.merchant_id,
        ti.expected_amount,
        sr.settled_amount
    FROM target_intents ti
    INNER JOIN settlement_records sr 
      ON ti.reference_id = sr.reference_number -- Index Hash Join terisolasi di RAM
)
SELECT 
    rd.*,
    al.status AS latest_audit_status
FROM reconciled_data rd
LEFT JOIN LATERAL (
    SELECT log.status
    FROM audit_logs log
    WHERE log.entity_id = rd.intent_id
    ORDER BY log.logged_at DESC
    LIMIT 1
) al ON TRUE;
```

#### Hasil Metrik Kinerja
- **Execution Time**: Turun dari 4 jam 45 menit menjadi **87 detik**.
- **Disk Spill (Temp Files)**: Turun dari 180 GB menjadi **0 MB** (eksekusi murni di RAM / `work_mem`).
- **Buffer Cache Hit Ratio**: Meningkat dari 42% menjadi 99.4%.

---

### 9. Trade-offs

| Algoritma / Pendekatan | Latency Impact | Throughput Impact | Memory / Resource Cost | Trade-Off Utama |
| :--- | :--- | :--- | :--- | :--- |
| **Nested Loop (INLJ)** | Sangat Rendah untuk dataset kecil/spesifik. | Tinggi jika konkurensi tinggi dan data terindeks. | Sangat Rendah (O(1) auxiliary memory). | Performa hancur ($O(N \times M)$) jika kardinalitas outer table meleset dari estimasi statistik katalog. |
| **Hash Join** | Sedang (ada fase *cold latency* untuk build table). | Sangat Tinggi untuk analitik volume besar. | Sangat Tinggi (kebutuhan RAM proporsional terhadap *build size*). | Terjadi I/O stall parah jika terjadi partisi *Spill to Disk* saat memori terlampaui. Hanya mendukung *equi-join*. |
| **Sort-Merge Join** | Tinggi jika harus melakukan fase Sort eksplisit. | Tinggi & Stabil pada data terurut masif. | Rendah ke Sedang (jika input data sudah terurut via B-Tree index). | Sensitif terhadap skenario data *many-to-many* (membutuhkan backtracking berulang pada inner table buffer). |
| **Lateral Subquery** | Sangat Rendah untuk top-N pagination per entitas. | Tinggi untuk batch operasional transaksional. | Minimal. | Menurun drastis performanya jika outer table memuat lebih dari puluhan ribu entitas tanpa limitasi selektif. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Masalah Semantik `NULL` pada Subquery `NOT IN`
- **Gejala**: Kueri `WHERE col NOT IN (SELECT other_col FROM ...)` mengembalikan 0 baris (*empty result set*), padahal data target jelas ada.
- **Penyebab**: Jika subquery menghasilkan setidaknya **satu nilai `NULL`**, evaluasi komparasi SQL ANSI menghasilkan status tri-state logic: `col = NULL` adalah `UNKNOWN`, dan negasinya `NOT (UNKNOWN)` tetap `UNKNOWN`. Seluruh predikat gagal dipenuhi.
- **Solusi**: Gunakan selalu `WHERE NOT EXISTS (...)` atau berikan filter eksplisit `WHERE other_col IS NOT NULL` di dalam subquery.

#### 2. Kardinalitas Meleset Mengakibatkan Eksekusi NLJ Brutal
- **Gejala**: Kueri join menggantung (*hang*) dengan penggunaan CPU 100% pada satu thread.
- **Penyebab**: Optimizer mengestimasi data outer hanya berjumlah 1 baris (sehingga memilih Nested Loop Join), namun pada realitas runtime terdapat 500.000 baris. 500.000 loop memicu scan inner table berulang kali.
- **Troubleshooting**:
  ```sql
  -- Periksa deviasi estimasi
  EXPLAIN (ANALYZE, BUFFERS) SELECT ...;
  -- Jika baris: "rows=1 width=..." namun "actual rows=500000":
  ANALYZE table_name; -- Update statistik CBO
  ```

#### 3. Ketidakcocokan Tipe Data pada Kolom Join (*Implicit Cast Invalidation*)
- **Gejala**: Engine melakukan `Seq Scan` lambat padahal indeks B-Tree telah dibuat pada kedua kolom join.
- **Penyebab**: Contoh: `table_a.id` adalah `INT` dan `table_b.a_id` adalah `BIGINT`, atau terdapat perbedaan string encoding (`UTF8` vs `LATIN1`). Optimizer menyuntikkan fungsi implisit: misal `CAST(a.id AS BIGINT) = b.a_id`, yang menganulir penggunaan indeks pohon (Sargability rusak).
- **Solusi**: Pastikan definisi skema DDL memiliki tipe data dan aturan collation yang identik secara fisik.

---

### 11. Best Practices (Production Checklist)

- [ ] **Symmetric Data Types**: Pastikan kolom foreign key memiliki tipe data, panjang bytes, dan aturan collation yang persis sama dengan referensi primary key-nya.
- [ ] **Hindari Implicit Cartesian**: Larang penggunaan sintaksis join gaya lama `FROM table_a, table_b` di mana lupa menuliskan klausul `WHERE` akan memicu *uncontrolled Cross Join*.
- [ ] **Gunakan `NOT EXISTS` Alih-alih `NOT IN`**: Lindungi aplikasi dari jebakan logic ANSI tri-state boolean `NULL`.
- [ ] **Alokasikan `work_mem` Per Query Secara Presisi**: Untuk pipeline ETL/batching kompleks, tingkatkan alokasi memori join hanya pada level session/transaksi untuk mencegah Disk Spill tanpa menguras memori server secara global:
  ```sql
  SET LOCAL work_mem = '256MB';
  -- Jalankan kueri join masif di sini
  ```
- [ ] **Monitor Cardinality Drift**: Jadwalkan proses pemeliharaan berkala `ANALYZE` otomatis setelah terjadi mutasi data masif (>10-20% perubahan data) untuk mencegah degradasi performa pemilihan operator oleh CBO.
- [ ] **Manfaatkan Cover Indexes**: Pada inner join berkecepatan tinggi, pastikan indeks B-Tree mengikutsertakan kolom yang di-proyeksikan via klausul `INCLUDE` (Index-Only Scan optimization).

---

### 12. Hands-on Practice

Siapkan berkas kerja Anda pada struktur direktori: `hands-on/m02/`.

#### Langkah 1: Siapkan Lingkungan Eksperimen
Simpan skrip berikut sebagai `hands-on/m02/01_setup_schema.sql`:

```sql
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
    customer_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    segment VARCHAR(20) NOT NULL,
    metadata JSONB
);

CREATE TABLE orders (
    order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id INT NOT NULL,
    order_date DATE NOT NULL,
    total_amount NUMERIC(12,2) NOT NULL
);

CREATE TABLE order_items (
    item_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id BIGINT NOT NULL,
    sku VARCHAR(50) NOT NULL,
    quantity INT NOT NULL,
    price NUMERIC(10,2) NOT NULL
);

-- Seed Dataset Sintetis Skala Terukur
INSERT INTO customers (segment)
SELECT (ARRAY['RETAIL', 'CORPORATE', 'VIP'])[floor(random() * 3 + 1)]
FROM generate_series(1, 10000);

INSERT INTO orders (customer_id, order_date, total_amount)
SELECT 
    floor(random() * 10000 + 1)::INT,
    CURRENT_DATE - (floor(random() * 365)::INT),
    (random() * 1000 + 10)::NUMERIC(12,2)
FROM generate_series(1, 200000);

INSERT INTO order_items (order_id, sku, quantity, price)
SELECT 
    floor(random() * 200000 + 1)::BIGINT,
    'SKU-' || floor(random() * 500 + 1)::TEXT,
    floor(random() * 5 + 1)::INT,
    (random() * 100 + 5)::NUMERIC(10,2)
FROM generate_series(1, 800000);

-- Verifikasi Analitik Katalog
ANALYZE customers;
ANALYZE orders;
ANALYZE order_items;
```

#### Langkah 2: Eksperimen Operator Join CBO
Simpan sebagai `hands-on/m02/02_operator_inspection.sql`:

```sql
-- 1. Evaluasi Default CBO Plan (Kemungkinan Hash Join)
EXPLAIN (ANALYZE, BUFFERS)
SELECT c.segment, COUNT(o.order_id), SUM(o.total_amount)
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.segment;

-- 2. Matikan Hash Join Secara Paksa untuk Mengamati Perilaku Engine Berpindah ke Merge Join / Nested Loop
SET LOCAL enable_hashjoin = off;

EXPLAIN (ANALYZE, BUFFERS)
SELECT c.segment, COUNT(o.order_id), SUM(o.total_amount)
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.segment;

RESET enable_hashjoin;
```

#### Langkah 3: Evaluasi Temp Spill Diagnostic
Simpan sebagai `hands-on/m02/03_temp_spill_tuning.sql`:

```sql
-- Minimalkan memori untuk memaksa terjadinya eksekusi disk spill
SET LOCAL work_mem = '64kB';

EXPLAIN (ANALYZE, BUFFERS)
SELECT o.order_id, oi.sku, oi.price
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
ORDER BY o.order_id;
-- Amati metrik: "Sort Method: external merge  Disk: ...kB" atau "Batches: ... Disk: ...kB"

-- Pulihkan memori ke rasio optimal
SET LOCAL work_mem = '64MB';

EXPLAIN (ANALYZE, BUFFERS)
SELECT o.order_id, oi.sku, oi.price
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
ORDER BY o.order_id;
-- Amati pemulihan ke memory operation: "Sort Method: quicksort  Memory: ...kB"
```

---

### 13. Exercise

#### Level Easy
Tuliskan kueri ANSI SQL yang mengembalikan seluruh data `customers` yang **belum pernah melakukan order sama sekali** (`orders`). Gunakan operator pembanding `NOT EXISTS`.
- *Input Schema*: Tabel `customers` dan `orders` dari skrip Hands-on.
- *Ekspektasi Output*: Kolom `customer_id`, `segment`.

```sql
-- Jawaban:
SELECT c.customer_id, c.segment
FROM customers c
WHERE NOT EXISTS (
    SELECT 1 
    FROM orders o 
    WHERE o.customer_id = c.customer_id
);
```

#### Level Medium
Tuliskan kueri set operation yang menghasilkan daftar seluruh `sku` unik yang terjual pada segmen pelanggan `'VIP'`, namun **tidak pernah** terjual sama sekali pada segmen pelanggan `'RETAIL'`. Gunakan operator `EXCEPT`.

```sql
-- Jawaban:
SELECT DISTINCT oi.sku
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN customers c ON o.customer_id = c.customer_id
WHERE c.segment = 'VIP'

EXCEPT

SELECT DISTINCT oi.sku
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN customers c ON o.customer_id = c.customer_id
WHERE c.segment = 'RETAIL';
```

#### Level Hard
Optimalkan kueri pagination berikut yang mengalami masalah timeout I/O. Kueri ditujukan untuk menampilkan data `customers` segmen `'CORPORATE'`, beserta **2 pesanan dengan nilai `total_amount` tertinggi** untuk masing-masing customer tersebut. Dilarang menggunakan fungsi window berulang tanpa isolasi scan data.

```sql
-- Jawaban Teroptimasi:
SELECT 
    c.customer_id,
    top_orders.order_id,
    top_orders.total_amount,
    top_orders.order_date
FROM customers c
CROSS JOIN LATERAL (
    SELECT o.order_id, o.total_amount, o.order_date
    FROM orders o
    WHERE o.customer_id = c.customer_id
    ORDER BY o.total_amount DESC
    LIMIT 2
) top_orders
WHERE c.segment = 'CORPORATE';
```

---

### 14. Challenge

#### Skenario Kasus Kompleks: Engine Rekonsiliasi Multi-Sistem FinTech
Anda ditugaskan mendesain sistem pelaporan dan rekonsiliasi data antara **Ledger Transaksi Internal Core Banking** (`core_ledger`) dan **Settlement File dari Bank Indonesia / Gateway Eksternal** (`gateway_settlement`).

Spesifikasi Data:
- `core_ledger`: ~120.000.000 baris data per bulan.
- `gateway_settlement`: ~119.500.000 baris data per bulan.
- Kolom kecocokan (*match criteria*): Tidak sesederhana ID tunggal. Transaksi dinyatakan cocok jika:
  1. `core_ledger.reference_code` = `gateway_settlement.external_ref`, ATAU
  2. (`core_ledger.sender_account` = `gateway_settlement.source_acc` AND `core_ledger.amount` = `gateway_settlement.trx_amount` AND `gateway_settlement.cleared_at` BETWEEN `core_ledger.created_at` AND `core_ledger.created_at + INTERVAL '10 minutes'`).

Tantangan Kinerja:
Jika dievaluasi menggunakan predikat `ON condition_1 OR condition_2`, query planner akan mematikan Hash Join / Index Scan dan melakukan unindexed Cartesian/Nested Loop Join yang tidak akan selesai dalam hitungan hari.

Tugas Anda:
1. Rancang arsitektur strategi SQL murni (atau kombinasi view, indeks fungsional, dan set operations: `UNION ALL`, `ANTI-JOIN`) tanpa bantuan tools eksternal (seperti Spark/Hadoop) untuk menghasilkan 3 dataset terpisah:
   - Rekonsiliasi Sukses (Matched).
   - Data Menggantung pada Core Ledger (Unmatched Internal).
   - Data Menggantung pada Gateway Eksternal (Unmatched Gateway).
2. Buktikan struktur kueri Anda tidak memicu *accidental cartesian explosion* dan dapat dieksekusi dengan predikat Sargable murni pada memori database standar server enterprise (RAM 64 GB).

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (5 Soal)

1. **Apa perbedaan teknis mendasar antara `UNION` dan `UNION ALL` di internal database engine?**
   - *Jawaban*: `UNION ALL` langsung memancarkan stream data gabungan tanpa validasi keunikan ($O(1)$ overhead memori). `UNION` mewajibkan langkah komputasi lanjutan untuk deduplikasi data (berupa in-memory/spill Hash Aggregate atau Unique Sort Merge), yang meningkatkan biaya CPU dan memori secara masif.

2. **Kapan Cost-Based Optimizer (CBO) cenderung memilih Nested Loop Join daripada Hash Join?**
   - *Jawaban*: Ketika outer relation menghasilkan set data yang sangat kecil setelah filter predikat (kardinalitas rendah), dan inner relation memiliki indeks B-Tree yang sangat selektif pada predikat join key.

3. **Mengapa kueri anti-join dengan klausa `NOT IN` dapat menghasilkan output salah ketika subquery mengandung nilai `NULL`?**
   - *Jawaban*: Berdasarkan standar ANSI SQL three-valued logic, evaluasi komparasi dengan `NULL` menghasilkan status `UNKNOWN`. Ekspresi `val NOT IN (1, 2, NULL)` dievaluasi menjadi `val != 1 AND val != 2 AND val != NULL`. Karena `val != NULL` bernilai `UNKNOWN`, seluruh konjungsi bernilai `UNKNOWN` (atau False), sehingga kueri membuang seluruh baris data output.

4. **Apa yang dimaksud dengan proses "Build Phase" dan "Probe Phase" dalam Hash Join?**
   - *Jawaban*: *Build Phase* adalah tahap di mana engine membaca relasi yang lebih kecil, memproses nilai join key melalui fungsi hash, dan menyusunnya ke dalam memori hash table. *Probe Phase* adalah tahap membaca relasi yang lebih besar baris demi baris, menghitung hash dari join key-nya, dan mencari kecocokan pada hash table yang telah dibangun.

5. **Apa fungsi utama dari sintaksis `CROSS JOIN LATERAL`?**
   - *Jawaban*: Memungkinkan subquery di sisi kanan mereferensikan kolom yang disediakan oleh baris di sisi kiri secara per-baris (correlated inline subquery execution), mirip dengan loop iteratif terkontrol yang dapat mengeksploitasi indeks target.

---

#### B. Pertanyaan Intermediate (5 Soal)

6. **Bagaimana mekanisme engine menangani "Hash Join Disk Spill" ketika alokasi memori query (`work_mem`) terlampaui?**
   - *Jawaban*: Engine menerapkan algoritma *Grace Hash Join* atau *Hybrid Hash Join*. Relasi dibagi menjadi beberapa bucket partisi menggunakan fungsi hash sekunder. Partisi yang muat dievaluasi langsung di memori, sedangkan sisa partisi yang meluap ditulis sementara ke disk (*temporary files*). Engine kemudian memproses partisi disk tersebut secara sekuensial secara bertahap.

7. **Mengapa predikat join non-equi (misal: `ON a.id BETWEEN b.low AND b.high` atau `ON a.ip >= b.start_ip AND a.ip <= b.end_ip`) mendegradasi performa Hash Join?**
   - *Jawaban*: Karena algoritma hashing mengandalkan direct addressing matematis dari nilai kesetaraan diskrit ($hash(K_1) == hash(K_2)$). Predikat rentang/inequality tidak menghasilkan nilai hash yang sama untuk nilai-nilai yang bertetangga, sehingga optimizer tidak dapat membangun hash table kesetaraan dan terpaksa fallback ke Nested Loop Scan atau Sort-Merge Join berbasis perbandingan nilai.

8. **Kapan Sort-Merge Join jauh lebih unggul dibandingkan Hash Join pada data berskala ratusan gigabyte?**
   - *Jawaban*: Ketika data dari kedua tabel yang di-join sudah tersimpan secara terurut secara fisik melalui pemindaian indeks B-Tree (*Index Scan*), atau ketika data melebihi kapasitas RAM sedemikian rupa sehingga hash table akan menyebabkan partisi disk spill multi-batch yang ekstrem, sementara merge join hanya memerlukan sedikit buffer memori untuk memindai dua stream yang telah terurut.

9. **Apa implikasi performa dari optimasi "Subquery Decorrelation / Unnesting" oleh CBO?**
   - *Jawaban*: Mengubah correlated subquery yang semula dieksekusi secara naif per-baris (kompleksitas waktu $O(N \times M)$) menjadi relasi setara *Semi-Join* atau *Anti-Join*, sehingga query planner bebas memilih algoritma eksekusi setara berskala paralel seperti Hash Join atau Merge Join ($O(N + M)$).

10. **Apa perbedaan antara *Semi-Join* dan *Inner Join* standar dalam representasi aljabar relasional?**
    - *Jawaban*: *Inner Join* menduplikasi baris dari relasi kiri sebanyak baris yang cocok ditemukan pada relasi kanan (potensi duplikasi data 1:N). *Semi-Join* hanya memvalidasi apakah ada **setidaknya satu** kecocokan di relasi kanan; segera setelah baris pertama yang cocok ditemukan pada inner table, baris dari relasi kiri langsung dipancarkan dan pemindaian dihentikan, menjamin tidak ada duplikasi data tanpa memerlukan `DISTINCT`.

---

#### C. Skenario Kasus Produksi (3 Kasus)

11. **Skenario 1**: Database PostgreSQL Anda mengalami peningkatan dramatis pada metrics *I/O Write Operations* dan latensi query melonjak dari 50ms ke 12.000ms saat menjalankan kueri pelaporan bulanan yang menggabungkan 4 tabel besar. Dari log `EXPLAIN (ANALYZE, BUFFERS)` terlihat teks: `Hash Join (cost=... rows=... actual rows=...); Batches: 64  Memory Usage: 4096kB  Disk: 512400kB`.
    - **Diagnosis**: Terjadi Hash Join Disk Spill masif akibat alokasi `work_mem` yang terlalu kecil (hanya 4MB teralokasi), memaksa pembagian 64 batch yang harus bolak-balik ditulis dan dibaca dari disk I/O.
    - **Solusi**: Tingkatkan batas parameter memori operasional khusus untuk sesi batch pelaporan tersebut: `SET LOCAL work_mem = '1GB';`. Jika memungkinkan, buat indeks B-Tree yang relevan untuk mengubah jalur eksekusi menjadi Index-backed Sort-Merge Join jika pemrosesan RAM massal tidak mencukupi untuk banyak konkurensi.

12. **Skenario 2**: Kueri Anda menggunakan sintaksis `LEFT JOIN tbl_b ON a.id = b.id WHERE b.status = 'ACTIVE'`. Namun hasil output kueri ternyata tidak menampilkan baris data dari `tbl_a` yang tidak memiliki pasangan di `tbl_b`, berperilaku seperti `INNER JOIN`.
    - **Diagnosis**: Terjadi pelanggaran aturan *Outer Join Preservation*. Menempatkan predikat filter kolom inner table (`b.status = 'ACTIVE'`) di dalam klausul `WHERE` akan memfilter nilai `NULL` yang dihasilkan oleh operasi outer join (karena `NULL = 'ACTIVE'` bernilai false/unknown), secara efektif menurunkan (*demoting*) status `LEFT JOIN` menjadi `INNER JOIN`.
    - **Solusi**: Pindahkan kondisi predikat filter inner table langsung ke dalam klausul join: `LEFT JOIN tbl_b ON a.id = b.id AND b.status = 'ACTIVE'`.

13. **Skenario 3**: Sebuah kueri analitik menggabungkan tabel `sales` (100 juta baris) dengan tabel referensi waktu kalender `dim_calendar` (3.650 baris). Optimizer memilih algoritma Nested Loop Join, menyebabkan kueri berjalan lebih dari 20 menit tanpa selesai.
    - **Diagnosis**: Terjadi *Cardinality Misestimation* yang parah. Kemungkinan besar statistik tabel `sales` pada katalog sistem database sudah usang (*stale statistics*), sehingga CBO mengira tabel `sales` yang lolos predikat tanggal hanya memiliki 2 baris, padahal kenyataannya ada 20 juta baris yang harus memindai inner table berulang kali.
    - **Solusi**: Jalankan perintah `ANALYZE sales;` untuk memperbarui data histogram dan frekuensi nilai katalog. Sebagai langkah defensif pada session level jika ANALYZE belum menyelesaikan distribusi data non-linear, berikan instruksi/hint optimizer atau nonaktifkan loop join sementara: `SET LOCAL enable_nestloop = off;` untuk memaksa eksekusi menggunakan Hash Join.

---

### 16. Summary

```
+-------------------------------------------------------------------------------+
|                       RINGKASAN ARSITEKTUR RELASIONAL                         |
+-------------------------------------------------------------------------------+
| 1. EKSEKUSI FISIK JOIN                                                        |
|    - Nested Loop Join : Ideal untuk outer selektif (kecil) + inner berindeks. |
|    - Hash Join        : Raja equi-join analitik. Butuh kontrol ketat work_mem |
|                         agar tidak terjadi degradasi performa I/O Disk Spill. |
|    - Sort-Merge Join  : Terbaik untuk tabel raksasa non-RAM yang sudah        |
|                         terurut dari B-Tree index scan.                       |
|                                                                               |
| 2. PENGGUNAAN OPERATOR & SUBQUERY                                             |
|    - Gunakan NOT EXISTS atau Anti-Join ANSI alih-alih NOT IN untuk            |
|      menghindari jebakan semantik ANSI NULL three-valued logic.               |
|    - LATERAL JOIN adalah solusi de facto untuk komputasi terisolasi Top-N     |
|      per group tanpa memindai seluruh data partisi.                           |
|                                                                               |
| 3. TATA KELOLA OPTIMIZER PRODUKSI                                             |
|    - Perbedaan tipe data / collation pada kolom join mematikan indeks B-Tree. |
|    - Selalu verifikasi deviasi Cardinality Estimate vs Actual Rows via        |
|      EXPLAIN (ANALYZE, BUFFERS) untuk mencegah bencana algoritma eksekusi CBO.|
+-------------------------------------------------------------------------------+
```