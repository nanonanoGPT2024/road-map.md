# Bab 05 Module 01: Pengenalan Database dan SQL Dasar

## Kurikulum: Backend Beginner | Kategori: 01-Core-Foundations

---

## SECTION 01 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik akan mampu:

1. **Menjelaskan** konsep database relasional dan peran pentingnya dalam arsitektur backend modern
2. **Membedakan** jenis-jenis database (relasional vs non-relasional) beserta kasus penggunaan yang tepat
3. **Memahami** struktur fundamental database: tabel, baris, kolom, dan tipe data
4. **Menulis** pernyataan SQL dasar: `SELECT`, `INSERT`, `UPDATE`, `DELETE` (CRUD operations)
5. **Menerapkan** klausa filtering (`WHERE`), pengurutan (`ORDER BY`), dan pembatasan (`LIMIT`)
6. **Merancang** skema tabel sederhana dengan mempertimbangkan tipe data yang tepat
7. **Menggunakan** Primary Key dan Foreign Key untuk menjaga integritas data
8. **Menjalankan** query SQL menggunakan PostgreSQL atau MySQL dalam lingkungan lokal

---

## SECTION 02 — CONCEPT OVERVIEW

### Apa Itu Database?

Database adalah **sistem terorganisir untuk menyimpan, mengelola, dan mengambil data secara efisien dan persisten**. Dalam konteks backend engineering, database adalah komponen yang memastikan data aplikasi tetap ada (persisten) meskipun server dimatikan atau di-restart.

### Hierarki Konsep Database Relasional

```
Database System (DBMS)
    └── Database (Schema)
            └── Table (Relasi)
                    ├── Column (Atribut/Field)
                    └── Row (Record/Tuple)
```

### Komponen Utama

| Komponen | Definisi | Analogi Dunia Nyata |
|----------|----------|---------------------|
| **Database** | Wadah utama yang menampung semua data | Lemari arsip |
| **Table** | Kumpulan data bertopik sama | Laci dalam lemari |
| **Column** | Kategori data dalam tabel | Label pada laci |
| **Row** | Satu entri/record data | Satu dokumen dalam laci |
| **Primary Key** | Identifikasi unik setiap baris | Nomor seri dokumen |
| **Foreign Key** | Referensi ke tabel lain | Nomor referensi silang |

### Database Management System (DBMS)

DBMS adalah perangkat lunak yang mengelola database. DBMS bertindak sebagai **perantara** antara aplikasi dan data yang tersimpan di disk.

```
Aplikasi Backend
      │
      ▼
   DBMS (PostgreSQL / MySQL / SQLite)
      │
      ▼
   Storage (Disk / SSD)
```

---

## SECTION 03 — WHY THIS MATTERS

### Mengapa Database Adalah Fondasi Backend?

Hampir **setiap aplikasi backend yang nyata** membutuhkan mekanisme penyimpanan data yang andal. Berikut alasan mengapa pemahaman database adalah keterampilan wajib:

#### 1. Persistensi Data
Variabel dalam memori (RAM) hilang ketika program berhenti. Database menyimpan data **secara permanen** di disk.

```
Tanpa Database:
  User mendaftar → data di RAM → server restart → DATA HILANG ❌

Dengan Database:
  User mendaftar → data di DB → server restart → data tetap ada ✅
```

#### 2. Konsistensi dan Integritas Data
Database relasional memiliki mekanisme **ACID** (Atomicity, Consistency, Isolation, Durability) yang memastikan data selalu dalam keadaan valid, bahkan saat terjadi kegagalan sistem.

#### 3. Efisiensi Pencarian
Database dioptimalkan untuk pencarian data dalam jumlah besar. Mencari 1 record dari 10 juta record dalam milidetik adalah hal yang normal dengan indexing yang tepat.

#### 4. Keamanan dan Akses Kontrol
DBMS menyediakan sistem autentikasi dan otorisasi bawaan untuk mengontrol siapa yang dapat membaca atau memodifikasi data.

#### 5. Standar Industri
SQL adalah bahasa standar yang digunakan di hampir semua perusahaan teknologi. Kemampuan SQL adalah **prerequisite** untuk posisi backend developer, data engineer, dan bahkan full-stack developer.

---

## SECTION 04 — WHAT YOU NEED TO KNOW

### Jenis-Jenis Database

#### A. Relational Database (SQL)
Menyimpan data dalam **tabel terstruktur** dengan relasi antar tabel.

- **Contoh**: PostgreSQL, MySQL, SQLite, Microsoft SQL Server, Oracle
- **Kasus Penggunaan**: Sistem e-commerce, perbankan, manajemen pengguna, aplikasi dengan data terstruktur

#### B. Non-Relational Database (NoSQL)
Menyimpan data dalam format fleksibel: dokumen, key-value, graph, atau column-family.

- **Contoh**: MongoDB (dokumen), Redis (key-value), Cassandra (column), Neo4j (graph)
- **Kasus Penggunaan**: Cache, real-time analytics, data tidak terstruktur, skala sangat besar

#### Perbandingan SQL vs NoSQL

| Aspek | SQL (Relasional) | NoSQL |
|-------|-----------------|-------|
| Struktur | Skema tetap (rigid) | Skema fleksibel |
| Query | SQL standar | Bervariasi per DB |
| Relasi | Sangat kuat | Terbatas |
| Skalabilitas | Vertikal (scale-up) | Horizontal (scale-out) |
| Konsistensi | ACID | Eventual consistency |
| Cocok untuk | Data terstruktur, transaksi | Data tidak terstruktur, volume besar |

> **Fokus Modul Ini**: Kita akan fokus pada **database relasional** karena merupakan fondasi yang paling penting untuk backend beginner.

### Tipe Data SQL yang Umum

| Kategori | Tipe Data | Deskripsi | Contoh |
|----------|-----------|-----------|--------|
| **Integer** | `INT`, `BIGINT`, `SMALLINT` | Bilangan bulat | `42`, `1000000` |
| **Desimal** | `DECIMAL(p,s)`, `FLOAT`, `NUMERIC` | Bilangan desimal | `99.99`, `3.14` |
| **Teks** | `VARCHAR(n)`, `TEXT`, `CHAR(n)` | String karakter | `'Hello'`, `'user@email.com'` |
| **Boolean** | `BOOLEAN` | Nilai benar/salah | `TRUE`, `FALSE` |
| **Tanggal/Waktu** | `DATE`, `TIME`, `TIMESTAMP` | Waktu | `'2024-01-15'` |
| **UUID** | `UUID` | Identifier unik universal | `'550e8400-e29b-41d4-a716-446655440000'` |

---

## SECTION 05 — HOW IT WORKS

### Alur Kerja Database dalam Aplikasi Backend

```
1. Aplikasi mengirim SQL Query
         │
         ▼
2. DBMS menerima dan mem-parse query
         │
         ▼
3. Query Optimizer menentukan execution plan terbaik
         │
         ▼
4. Storage Engine membaca/menulis data dari disk
         │
         ▼
5. DBMS mengembalikan hasil (Result Set)
         │
         ▼
6. Aplikasi memproses dan menampilkan data
```

### Anatomi SQL Query

SQL (Structured Query Language) adalah bahasa deklaratif — kita mendeskripsikan **apa** yang kita inginkan, bukan **bagaimana** cara mendapatkannya.

```sql
SELECT   kolom_yang_diinginkan      -- Apa yang ingin ditampilkan
FROM     nama_tabel                 -- Dari mana datanya
WHERE    kondisi_filter             -- Filter data
ORDER BY kolom_pengurutan           -- Urutan tampilan
LIMIT    jumlah_baris;              -- Batasi jumlah hasil
```

### Urutan Eksekusi SQL (Logical Order)

Penting dipahami: urutan **penulisan** SQL berbeda dengan urutan **eksekusi**-nya.

```
Urutan Penulisan:        Urutan Eksekusi:
1. SELECT           →    1. FROM
2. FROM             →    2. WHERE
3. WHERE            →    3. GROUP BY
4. GROUP BY         →    4. HAVING
5. HAVING           →    5. SELECT
6. ORDER BY         →    6. ORDER BY
7. LIMIT            →    7. LIMIT
```

### Operasi CRUD dalam SQL

| Operasi | SQL Statement | Deskripsi |
|---------|--------------|-----------|
| **Create** | `INSERT INTO` | Menambah data baru |
| **Read** | `SELECT` | Membaca/mengambil data |
| **Update** | `UPDATE SET` | Mengubah data yang ada |
| **Delete** | `DELETE FROM` | Menghapus data |

---

## SECTION 06 — ASCII DIAGRAM

### Diagram 1: Arsitektur Sistem Database

```
┌─────────────────────────────────────────────────────────────┐
│                    APLIKASI BACKEND                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  API Layer  │  │  Business   │  │   Data Access Layer │ │
│  │  (Routes)   │→ │   Logic     │→ │   (Repository)      │ │
│  └─────────────┘  └─────────────┘  └──────────┬──────────┘ │
└─────────────────────────────────────────────────┼───────────┘
                                                  │ SQL Query
                                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    DBMS (PostgreSQL)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Query Parser │→ │   Optimizer  │→ │  Execution Engine│  │
│  └──────────────┘  └──────────────┘  └────────┬─────────┘  │
└───────────────────────────────────────────────┼────────────┘
                                                 │
                                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    STORAGE LAYER                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Database: "toko_online"                             │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │   │
│  │  │ Table: users │  │Table: orders │  │Table:     │  │   │
│  │  │              │  │              │  │products   │  │   │
│  │  │ id │ name    │  │ id │user_id  │  │           │  │   │
│  │  │ 1  │ Alice   │  │ 1  │  1      │  │ id │ name │  │   │
│  │  │ 2  │ Bob     │  │ 2  │  1      │  │ 1  │ Baju │  │   │
│  │  └──────────────┘  └──────────────┘  └───────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Diagram 2: Relasi Antar Tabel

```
┌─────────────────────┐          ┌──────────────────────────┐
│    TABLE: users     │          │      TABLE: orders       │
├──────┬──────────────┤          ├──────┬─────────┬─────────┤
│  id  │    name      │          │  id  │ user_id │  total  │
│ (PK) │              │          │ (PK) │  (FK)   │         │
├──────┼──────────────┤    ┌────►├──────┼─────────┼─────────┤
│  1   │  Alice       │────┘     │  1   │    1    │ 150.000 │
│  2   │  Bob         │────┐     │  2   │    1    │  75.000 │
│  3   │  Charlie     │    └────►│  3   │    2    │ 200.000 │
└──────┴──────────────┘          └──────┴─────────┴─────────┘
         │                                    │
         │ PK = Primary Key                   │
         │ FK = Foreign Key                   │
         │                                    │
         └────────── Relasi 1 ke Banyak ──────┘
              (1 user bisa punya banyak order)
```

### Diagram 3: Siklus CRUD

```
         ┌─────────────────────────────────┐
         │         DATABASE TABLE          │
         │                                 │
    ┌────┴────┐                       ┌────┴────┐
    │ INSERT  │                       │ SELECT  │
    │ (Create)│                       │  (Read) │
    └────┬────┘                       └────┬────┘
         │    ┌─────────────────────┐      │
         └───►│   Data tersimpan    │◄─────┘
              │   di tabel          │
         ┌───►│                     │◄─────┐
         │    └─────────────────────┘      │
    ┌────┴────┐                       ┌────┴────┐
    │ UPDATE  │                       │ DELETE  │
    │(Update) │                       │(Delete) │
    └─────────┘                       └─────────┘
```

---

## SECTION 07 — SIMPLE EXAMPLE

### Setup: Membuat Database dan Tabel Pertama

Mari kita mulai dengan contoh paling sederhana — sistem manajemen buku perpustakaan mini.

```sql
-- ============================================
-- LANGKAH 1: Membuat Database
-- ============================================
CREATE DATABASE perpustakaan;

-- Pilih database yang akan digunakan
\c perpustakaan  -- Perintah khusus PostgreSQL
-- USE perpustakaan;  -- Untuk MySQL

-- ============================================
-- LANGKAH 2: Membuat Tabel
-- ============================================
CREATE TABLE buku (
    id          SERIAL PRIMARY KEY,    -- Auto-increment ID
    judul       VARCHAR(200) NOT NULL, -- Judul wajib diisi
    penulis     VARCHAR(100) NOT NULL, -- Penulis wajib diisi
    tahun_terbit INT,                  -- Tahun boleh kosong
    stok        INT DEFAULT 0,         -- Default stok = 0
    harga       DECIMAL(10, 2)         -- Harga dengan 2 desimal
);

-- ============================================
-- LANGKAH 3: INSERT - Menambah Data
-- ============================================
INSERT INTO buku (judul, penulis, tahun_terbit, stok, harga)
VALUES ('Laskar Pelangi', 'Andrea Hirata', 2005, 10, 85000.00);

INSERT INTO buku (judul, penulis, tahun_terbit, stok, harga)
VALUES ('Bumi Manusia', 'Pramoedya Ananta Toer', 1980, 5, 95000.00);

INSERT INTO buku (judul, penulis, tahun_terbit, stok, harga)
VALUES ('Negeri 5 Menara', 'Ahmad Fuadi', 2009, 8, 79000.00);

-- ============================================
-- LANGKAH 4: SELECT - Membaca Data
-- ============================================

-- Ambil semua data
SELECT * FROM buku;

-- Ambil kolom tertentu saja
SELECT judul, penulis, harga FROM buku;

-- Filter dengan WHERE
SELECT judul, stok 
FROM buku 
WHERE stok > 5;

-- Urutkan berdasarkan harga
SELECT judul, harga 
FROM buku 
ORDER BY harga ASC;  -- ASC = ascending (kecil ke besar)

-- ============================================
-- LANGKAH 5: UPDATE - Mengubah Data
-- ============================================

-- Update stok buku dengan id = 1
UPDATE buku 
SET stok = 15 
WHERE id = 1;

-- Update beberapa kolom sekaligus
UPDATE buku 
SET stok = 3, harga = 90000.00 
WHERE judul = 'Bumi Manusia';

-- ============================================
-- LANGKAH 6: DELETE - Menghapus Data
-- ============================================

-- Hapus buku berdasarkan id
DELETE FROM buku 
WHERE id = 3;

-- PERINGATAN: DELETE tanpa WHERE akan menghapus SEMUA data!
-- DELETE FROM buku;  ← JANGAN lakukan ini tanpa WHERE!
```

### Hasil Query SELECT

```
Output: SELECT * FROM buku;

 id |         judul          |         penulis          | tahun_terbit | stok |  harga   
----+------------------------+--------------------------+--------------+------+----------
  1 | Laskar Pelangi         | Andrea Hirata            |         2005 |   15 | 85000.00
  2 | Bumi Manusia           | Pramoedya Ananta Toer    |         1980 |    3 | 90000.00
(2 rows)
```

---

## SECTION 08 — PRACTICAL EXAMPLE

### Studi Kasus: Sistem Database E-Commerce Sederhana

Kita akan membangun skema database untuk toko online sederhana dengan tiga entitas: **users**, **products**, dan **orders**.

```sql
-- ============================================
-- SCHEMA: Toko Online Sederhana
-- ============================================

-- Tabel Users (Pengguna)
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    nama        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) UNIQUE NOT NULL,  -- Email harus unik
    password    VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active   BOOLEAN DEFAULT TRUE
);

-- Tabel Products (Produk)
CREATE TABLE products (
    id          SERIAL PRIMARY KEY,
    nama        VARCHAR(200) NOT NULL,
    deskripsi   TEXT,
    harga       DECIMAL(12, 2) NOT NULL CHECK (harga > 0),  -- Harga harus positif
    stok        INT NOT NULL DEFAULT 0 CHECK (stok >= 0),   -- Stok tidak boleh negatif
    kategori    VARCHAR(50),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabel Orders (Pesanan)
CREATE TABLE orders (
    id          SERIAL PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES users(id),      -- Foreign Key ke users
    total       DECIMAL(12, 2) NOT NULL,
    status      VARCHAR(20) DEFAULT 'pending'
                CHECK (status IN ('pending', 'paid', 'shipped', 'delivered', 'cancelled')),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabel Order Items (Detail Item dalam Pesanan)
CREATE TABLE order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INT NOT NULL REFERENCES orders(id),     -- FK ke orders
    product_id  INT NOT NULL REFERENCES products(id),   -- FK ke products
    quantity    INT NOT NULL CHECK (quantity > 0),
    harga_saat_beli DECIMAL(12, 2) NOT NULL             -- Simpan harga saat transaksi
);

-- ============================================
-- INSERT: Mengisi Data Sample
-- ============================================

-- Tambah users
INSERT INTO users (nama, email, password) VALUES
    ('Budi Santoso', 'budi@email.com', 'hashed_password_1'),
    ('Siti Rahayu', 'siti@email.com', 'hashed_password_2'),
    ('Ahmad Fauzi', 'ahmad@email.com', 'hashed_password_3');

-- Tambah products
INSERT INTO products (nama, deskripsi, harga, stok, kategori) VALUES
    ('Laptop ASUS VivoBook', 'Laptop 14 inch, RAM 8GB, SSD 512GB', 8500000.00, 15, 'Elektronik'),
    ('Mouse Wireless Logitech', 'Mouse wireless ergonomis', 350000.00, 50, 'Aksesoris'),
    ('Keyboard Mechanical', 'Keyboard gaming RGB', 750000.00, 30, 'Aksesoris'),
    ('Monitor 24 inch', 'Monitor Full HD IPS', 2800000.00, 10, 'Elektronik');

-- Tambah order
INSERT INTO orders (user_id, total, status) VALUES
    (1, 8850000.00, 'paid'),
    (2, 3550000.00, 'pending'),
    (1, 750000.00, 'delivered');

-- Tambah order items
INSERT INTO order_items (order_id, product_id, quantity, harga_saat_beli) VALUES
    (1, 1, 1, 8500000.00),  -- Order 1: 1 Laptop
    (1, 2, 1, 350000.00),   -- Order 1: 1 Mouse
    (2, 4, 1, 2800000.00),  -- Order 2: 1 Monitor
    (2, 2, 2, 350000.00),   -- Order 2: 2 Mouse
    (3, 3, 1, 750000.00);   -- Order 3: 1 Keyboard

-- ============================================
-- QUERY PRAKTIS: Berbagai Skenario Bisnis
-- ============================================

-- Query 1: Lihat semua produk yang stoknya menipis (< 20)
SELECT 
    nama,
    kategori,
    stok,
    harga
FROM products
WHERE stok < 20
ORDER BY stok ASC;

-- Output:
-- nama                  | kategori   | stok | harga
-- Monitor 24 inch       | Elektronik |   10 | 2800000.00
-- Laptop ASUS VivoBook  | Elektronik |   15 | 8500000.00

-- ============================================
-- Query 2: Lihat semua pesanan beserta nama user
-- (Menggunakan JOIN - preview konsep lanjutan)
SELECT 
    o.id AS order_id,
    u.nama AS nama_user,
    o.total,
    o.status,
    o.created_at
FROM orders o
JOIN users u ON o.user_id = u.id
ORDER BY o.created_at DESC;

-- ============================================
-- Query 3: Hitung total belanja per user
SELECT 
    u.nama,
    COUNT(o.id) AS jumlah_order,
    SUM(o.total) AS total_belanja
FROM users u
JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.nama
ORDER BY total_belanja DESC;

-- Output:
-- nama          | jumlah_order | total_belanja
-- Budi Santoso  |      2       | 9600000.00
-- Siti Rahayu   |      1       | 3550000.00

-- ============================================
-- Query 4: Produk terlaris berdasarkan quantity terjual
SELECT 
    p.nama AS produk,
    SUM(oi.quantity) AS total_terjual,
    SUM(oi.quantity * oi.harga_saat_beli) AS total_pendapatan
FROM products p
JOIN order_items oi ON p.id = oi.product_id
GROUP BY p.id, p.nama
ORDER BY total_terjual DESC
LIMIT 5;

-- ============================================
-- Query 5: Update stok setelah penjualan
-- (Simulasi: Order 3 baru saja diproses)
UPDATE products 
SET stok = stok - 1 
WHERE id = 3;  -- Kurangi stok Keyboard sebanyak 1

-- Verifikasi perubahan
SELECT nama, stok FROM products WHERE id = 3;

-- ============================================
-- Query 6: Batalkan order yang sudah lama pending
-- (Lebih dari 7 hari dan masih pending)
UPDATE orders 
SET status = 'cancelled'
WHERE status = 'pending' 
  AND created_at < CURRENT_TIMESTAMP - INTERVAL '7 days';
```

---

## SECTION 09 — TRADE-OFFS & CONSIDERATIONS

### Trade-off 1: SQL vs NoSQL

```
SQL (Relasional)
✅ Keunggulan:
   - Konsistensi data sangat kuat (ACID)
   - Relasi antar data mudah dikelola
   - Query kompleks dengan JOIN
   - Standar industri yang matang
   - Cocok untuk data terstruktur

❌ Kelemahan:
   - Skema kaku, sulit diubah di production
   - Skalabilitas horizontal lebih kompleks
   - Performa bisa turun pada data sangat besar tanpa optimasi

NoSQL
✅ Keunggulan:
   - Skema fleksibel
   - Skalabilitas horizontal mudah
   - Performa tinggi untuk operasi sederhana
   - Cocok untuk data tidak terstruktur

❌ Kelemahan:
   - Konsistensi data lebih lemah
   - Query kompleks lebih sulit
   - Tidak ada standar query universal
```

### Trade-off 2: VARCHAR vs TEXT

| Aspek | VARCHAR(n) | TEXT |
|-------|-----------|------|
| Panjang | Dibatasi n karakter | Tidak terbatas |
| Performa | Sedikit lebih cepat | Sedikit lebih lambat |
| Validasi | Ada batas otomatis | Tidak ada batas |
| Penggunaan | Email, nama, kode | Deskripsi panjang, artikel |

**Rekomendasi**: Gunakan `VARCHAR(n)` ketika Anda tahu batas maksimum panjang data. Gunakan `TEXT` untuk konten yang panjangnya tidak dapat diprediksi.

### Trade-off 3: INT vs BIGINT untuk Primary Key

```
INT:
- Range: -2,147,483,648 hingga 2,147,483,647
- Ukuran: 4 bytes
- Cocok untuk: Tabel dengan < 2 miliar baris

BIGINT:
- Range: -9,223,372,036,854,775,808 hingga 9,223,372,036,854,775,807
- Ukuran: 8 bytes
- Cocok untuk: Tabel yang akan tumbuh sangat besar

Rekomendasi: Gunakan BIGINT atau UUID untuk production
karena lebih aman dari overflow di masa depan.
```

### Trade-off 4: NULL vs NOT NULL

```sql
-- Kolom dengan NULL: Fleksibel tapi berisiko
ALTER TABLE users ADD COLUMN phone VARCHAR(20);  -- Boleh NULL

-- Masalah: NULL bisa menyebabkan bug yang sulit dilacak
SELECT * FROM users WHERE phone = '';    -- Tidak menemukan NULL
SELECT * FROM users WHERE phone IS NULL; -- Cara yang benar

-- Kolom NOT NULL: Lebih ketat tapi lebih aman
ALTER TABLE users ADD COLUMN phone VARCHAR(20) NOT NULL DEFAULT '';
```

**Prinsip**: Gunakan `NOT NULL` sebisa mungkin. Hanya izinkan `NULL` jika data memang benar-benar opsional secara bisnis.

---

## SECTION 10 — BEST PRACTICES

### 1. Penamaan yang Konsisten dan Deskriptif

```sql
-- ❌ Buruk: Nama tidak jelas dan tidak konsisten
CREATE TABLE tbl1 (
    ID int,
    nm varchar(50),
    TglDibuat timestamp
);

-- ✅ Baik: Nama jelas, snake_case, konsisten
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    full_name   VARCHAR(100) NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. Selalu Gunakan WHERE pada UPDATE dan DELETE

```sql
-- ❌ BERBAHAYA: Menghapus SEMUA data!
DELETE FROM orders;
UPDATE products SET stok = 0;

-- ✅ AMAN: Selalu spesifik dengan WHERE
DELETE FROM orders WHERE id = 5;
UPDATE products SET stok = 0 WHERE id = 3;

-- ✅ LEBIH AMAN: Cek dulu dengan SELECT sebelum DELETE/UPDATE
SELECT * FROM orders WHERE id = 5;  -- Verifikasi dulu
DELETE FROM orders WHERE id = 5;    -- Baru hapus
```

### 3. Pilih Tipe Data yang Tepat

```sql
-- ❌ Buruk: Tipe data tidak sesuai
CREATE TABLE products (
    harga   VARCHAR(50),    -- Harga sebagai string?
    stok    FLOAT,          -- Stok sebagai float?
    aktif   INT             -- Status sebagai integer?
);

-- ✅ Baik: Tipe data sesuai kebutuhan
CREATE TABLE products (
    harga   DECIMAL(12, 2) NOT NULL,  -- Presisi untuk uang
    stok    INT NOT NULL DEFAULT 0,   -- Bilangan bulat untuk stok
    aktif   BOOLEAN DEFAULT TRUE      -- Boolean untuk status
);
```

### 4. Gunakan Constraint untuk Validasi Data

```sql
CREATE TABLE products (
    id      SERIAL PRIMARY KEY,
    nama    VARCHAR(200) NOT NULL,
    harga   DECIMAL(12, 2) NOT NULL CHECK (harga > 0),
    stok    INT NOT NULL CHECK (stok >= 0),
    rating  DECIMAL(2, 1) CHECK (rating BETWEEN 0 AND 5),
    email   VARCHAR(150) UNIQUE
);
```

### 5. Hindari SELECT * di Production Code

```sql
-- ❌ Buruk: Mengambil semua kolom (termasuk yang tidak perlu)
SELECT * FROM users;

-- ✅ Baik: Ambil hanya kolom yang dibutuhkan
SELECT id, nama, email FROM users;

-- Alasan:
-- 1. Lebih efisien (transfer data lebih sedikit)
-- 2. Lebih aman (tidak expose data sensitif seperti password)
-- 3. Lebih mudah di-maintain
```

### 6. Gunakan Transaksi untuk Operasi Kritis

```sql
-- Contoh: Transfer stok antar gudang
BEGIN;  -- Mulai transaksi

UPDATE gudang_a SET stok = stok - 10 WHERE product_id = 1;
UPDATE gudang_b SET stok = stok + 10 WHERE product_id = 1;

-- Jika semua berhasil
COMMIT;

-- Jika ada error, batalkan semua perubahan
-- ROLLBACK;
```

### 7. Dokumentasikan Skema dengan Komentar

```sql
-- Tabel untuk menyimpan data pengguna aplikasi
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    email       VARCHAR(150) UNIQUE NOT NULL,  -- Digunakan untuk login
    password    VARCHAR(255) NOT NULL,          -- Harus di-hash (bcrypt)
    role        VARCHAR(20) DEFAULT 'customer', -- 'customer', 'admin', 'seller'
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## SECTION 11 — COMMON MISTAKES & HOW TO AVOID THEM

### Kesalahan 1: Lupa WHERE pada UPDATE/DELETE

```sql
-- ❌ FATAL: Mengubah SEMUA harga produk!
UPDATE products SET harga = 100000;

-- ✅ Benar
UPDATE products SET harga = 100000 WHERE id = 5;

-- 💡 Tip: Aktifkan safe mode di MySQL
SET SQL_SAFE_UPDATES = 1;
```

### Kesalahan 2: Menyimpan Password Plaintext

```sql
-- ❌ SANGAT BERBAHAYA
INSERT INTO users (email, password) 
VALUES ('user@email.com', 'password123');

-- ✅ Selalu hash password sebelum disimpan
-- (Dilakukan di aplikasi, bukan di SQL)
-- password = bcrypt.hash('password123', 10)
INSERT INTO users (email, password) 
VALUES ('user@email.com', '$2b$10$hashedPasswordHere...');
```

### Kesalahan 3: Tidak Menggunakan Constraint

```sql
-- ❌ Buruk: Tidak ada validasi
CREATE TABLE orders (
    id      SERIAL PRIMARY KEY,
    user_id INT,    -- Bisa diisi sembarang angka
    total   DECIMAL -- Bisa negatif
);

-- ✅ Baik: Dengan constraint
CREATE TABLE orders (
    id      SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id),  -- Harus ada di tabel users
    total   DECIMAL(12,2) NOT NULL CHECK (total > 0)  -- Harus positif
);
```

### Kesalahan 4: Menggunakan Nama Kolom yang Sama dengan Reserved Words

```sql
-- ❌ Buruk: 'order', 'user', 'select' adalah reserved words SQL
CREATE TABLE order (  -- ERROR!
    user INT,         -- Berpotensi konflik
    select VARCHAR    -- ERROR!
);

-- ✅ Baik: Gunakan nama yang tidak konflik
CREATE TABLE orders (
    user_id INT,
    selected_option VARCHAR
);
```

### Kesalahan 5: Tidak Memahami NULL

```sql
-- ❌ Bug: NULL tidak sama dengan string kosong atau 0
SELECT * FROM users WHERE phone = NULL;     -- Selalu kosong!
SELECT * FROM users WHERE phone != NULL;    -- Selalu kosong!

-- ✅ Benar: Gunakan IS NULL atau IS NOT NULL
SELECT * FROM users WHERE phone IS NULL;
SELECT * FROM users WHERE phone IS NOT NULL;

-- Contoh lain yang membingungkan:
SELECT NULL = NULL;   -- Hasilnya: NULL (bukan TRUE!)
SELECT NULL IS NULL;  -- Hasilnya: TRUE
```

---

## SECTION 12 — HANDS-ON EXERCISE

### Exercise 1: Membuat Skema Database Perpustakaan

**Tugas**: Buat skema database untuk sistem perpustakaan dengan ketentuan berikut:

```
Entitas yang diperlukan:
1. anggota (id, nama, email, nomor_ktp, tanggal_daftar)
2. buku (id, judul, isbn, penulis, penerbit, tahun, stok)
3. peminjaman (id, anggota_id, buku_id, tanggal_pinjam, tanggal_kembali, status)
```

**Jawaban**:

```sql
-- Buat database
CREATE DATABASE perpustakaan_db;

-- Tabel anggota
CREATE TABLE anggota (
    id              SERIAL PRIMARY KEY,
    nama            VARCHAR(100) NOT NULL,
    email           VARCHAR(150) UNIQUE NOT NULL,
    nomor_ktp       CHAR(16) UNIQUE NOT NULL,
    tanggal_daftar  DATE DEFAULT CURRENT_DATE,
    aktif           BOOLEAN DEFAULT TRUE
);

-- Tabel buku
CREATE TABLE buku (
    id          SERIAL PRIMARY KEY,
    judul       VARCHAR(300) NOT NULL,
    isbn        VARCHAR(20) UNIQUE,
    penulis     VARCHAR(100) NOT NULL,
    penerbit    VARCHAR(100),
    tahun       SMALLINT CHECK (tahun BETWEEN 1800 AND 2100),
    stok        INT NOT NULL DEFAULT 0 CHECK (stok >= 0)
);

-- Tabel peminjaman
CREATE TABLE peminjaman (
    id              SERIAL PRIMARY KEY,
    anggota_id      INT NOT NULL REFERENCES anggota(id),
    buku_id         INT NOT NULL REFERENCES buku(id),
    tanggal_pinjam  DATE NOT NULL DEFAULT CURRENT_DATE,
    tanggal_kembali DATE,
    status          VARCHAR(20) DEFAULT 'dipinjam'
                    CHECK (status IN ('dipinjam', 'dikembalikan', 'terlambat'))
);
```

### Exercise 2: Query CRUD Lengkap

```sql
-- 1. Tambahkan 3 anggota
INSERT INTO anggota (nama, email, nomor_ktp) VALUES
    ('Dewi Lestari', 'dewi@email.com', '3201234567890001'),
    ('Reza Pratama', 'reza@email.com', '3201234567890002'),
    ('Maya Sari', 'maya@email.com', '3201234567890003');

-- 2. Tambahkan 3 buku
INSERT INTO buku (judul, isbn, penulis, penerbit, tahun, stok) VALUES
    ('Clean Code', '978-0132350884', 'Robert C. Martin', 'Prentice Hall', 2008, 5),
    ('The Pragmatic Programmer', '978-0201616224', 'Andrew Hunt', 'Addison-Wesley', 1999, 3),
    ('Design Patterns', '978-0201633610', 'Gang of Four', 'Addison-Wesley', 1994, 2);

-- 3. Catat peminjaman
INSERT INTO peminjaman (anggota_id, buku_id, tanggal_pinjam) VALUES
    (1, 1, '2024-01-10'),
    (2, 2, '2024-01-12'),
    (1, 3, '2024-01-15');

-- 4. Kembalikan buku (update status)
UPDATE peminjaman 
SET status = 'dikembalikan', tanggal_kembali = CURRENT_DATE
WHERE anggota_id = 1 AND buku_id = 1;

-- 5. Lihat buku yang sedang dipinjam
SELECT 
    a.nama AS nama_anggota,
    b.judul AS judul_buku,
    p.tanggal_pinjam,
    p.status
FROM peminjaman p
JOIN anggota a ON p.anggota_id = a.id
JOIN buku b ON p.buku_id = b.id
WHERE p.status = 'dipinjam';
```

### Exercise 3: Challenge Query

```sql
-- Tantangan: Temukan anggota yang meminjam lebih dari 1 buku
SELECT 
    a.nama,
    COUNT(p.id) AS jumlah_pinjaman
FROM anggota a
JOIN peminjaman p ON a.id = p.anggota_id
WHERE p.status = 'dipinjam'
GROUP BY a.id, a.nama
HAVING COUNT(p.id) > 1;
```

---

## SECTION 13 — ENVIRONMENT SETUP

### Instalasi PostgreSQL (Rekomendasi untuk Pemula)

#### Opsi A: Instalasi Lokal

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# Verifikasi instalasi
psql --version
# Output: psql (PostgreSQL) 15.x

# Start service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Login sebagai user postgres
sudo -u postgres psql

# macOS dengan Homebrew
brew install postgresql@15
brew services start postgresql@15
```

#### Opsi B: Docker (Direkomendasikan untuk Development)

```bash
# Pull dan jalankan PostgreSQL dengan Docker
docker run --name postgres-dev \
  -e POSTGRES_PASSWORD=password123 \
  -e POSTGRES_USER=developer \
  -e POSTGRES_DB=belajar_db \
  -p 5432:5432 \
  -d postgres:15

# Verifikasi container berjalan
docker ps

# Masuk ke PostgreSQL
docker exec -it postgres-dev psql -U developer -d belajar_db
```

#### Opsi C: Online (Tanpa Instalasi)

- **db-fiddle.com** — SQL playground online
- **sqlfiddle.com** — Mendukung berbagai DBMS
- **supabase.com** — PostgreSQL gratis di cloud

### GUI Tools (Opsional tapi Sangat Membantu)

```
1. DBeaver (Gratis, Multi-database)
   Download: https://dbeaver.io/

2. TablePlus (Berbayar, UI sangat bersih)
   Download: https://tableplus.com/

3. pgAdmin (Gratis, Khusus PostgreSQL)
   Download: https://www.pgadmin.org/

4. VS Code Extension: SQLTools
   Install: code --install-extension mtxr.sqltools
```

### Konfigurasi Koneksi

```
Host:     localhost
Port:     5432 (PostgreSQL default)
Database: belajar_db
Username: developer
Password: password123
```

---

## SECTION 14 — INTEGRATION WITH BACKEND CODE

### Menghubungkan Database dengan Node.js

```javascript
// File: database.js
// Menggunakan library 'pg' (node-postgres)

const { Pool } = require('pg');

// Konfigurasi koneksi
const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: process.env.DB_PORT || 5432,
  database: process.env.DB_NAME || 'toko_online',
  user: process.env.DB_USER || 'developer',
  password: process.env.DB_PASSWORD || 'password123',
  max: 10,              // Maksimum koneksi dalam pool
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// Test koneksi
pool.connect((err, client, done) => {
  if (err) {
    console.error('❌ Gagal terhubung ke database:', err.message);
  } else {
    console.log('✅ Berhasil terhubung ke database');
    done();
  }
});

module.exports = pool;
```

```javascript
// File: userRepository.js
// Contoh penggunaan query dalam aplikasi

const pool = require('./database');

// Fungsi untuk mendapatkan semua user
async function getAllUsers() {
  const query = 'SELECT id, nama, email, created_at FROM users WHERE is_active = TRUE';
  
  try {
    const result = await pool.query(query);
    return result.rows;  // Array of user objects
  } catch (error) {
    throw new Error(`Gagal mengambil data user: ${error.message}`);
  }
}

// Fungsi untuk mendapatkan user berdasarkan ID
async function getUserById(userId) {
  const query = 'SELECT id, nama, email FROM users WHERE id = $1';
  const values = [userId];  // Parameterized query (mencegah SQL Injection)
  
  try {
    const result = await pool.query(query, values);
    return result.rows[0] || null;  // Return null jika tidak ditemukan
  } catch (error) {
    throw new Error(`Gagal mengambil user: ${error.message}`);
  }
}

// Fungsi untuk membuat user baru
async function createUser(nama, email, hashedPassword) {
  const query = `
    INSERT INTO users (nama, email, password) 
    VALUES ($1, $2, $3) 
    RETURNING id, nama, email, created_at
  `;
  const values = [nama, email, hashedPassword];
  
  try {
    const result = await pool.query(query, values);
    return result.rows[0];  // Return user yang baru dibuat
  } catch (error) {
    if (error.code === '23505') {  // Unique violation
      throw new Error('Email sudah terdaftar');
    }
    throw new Error(`Gagal membuat user: ${error.message}`);
  }
}

module.exports = { getAllUsers, getUserById, createUser };
```

```javascript
// File: userController.js
// Menggunakan repository dalam Express route handler

const { getAllUsers, getUserById, createUser } = require('./userRepository');
const bcrypt = require('bcrypt');

// GET /api/users
async function getUsers(req, res) {
  try {
    const users = await getAllUsers();
    res.json({
      success: true,
      data: users,
      count: users.length
    });
  } catch (error) {
    res.status(500).json({ success: false, message: error.message });
  }
}

// POST /api/users
async function registerUser(req, res) {
  const { nama, email, password } = req.body;
  
  // Validasi input
  if (!nama || !email || !password) {
    return res.status(400).json({ 
      success: false, 
      message: 'Nama, email, dan password wajib diisi' 
    });
  }
  
  try {
    // Hash password sebelum disimpan
    const hashedPassword = await bcrypt.hash(password, 10);
    
    // Simpan ke database
    const newUser = await createUser(nama, email, hashedPassword);
    
    res.status(201).json({
      success: true,
      message: 'User berhasil didaftarkan',
      data: newUser
    });
  } catch (error) {
    res.status(400).json({ success: false, message: error.message });
  }
}

module.exports = { getUsers, registerUser };
```

---

## SECTION 15 — SECURITY CONSIDERATIONS

### SQL Injection: Ancaman Terbesar

SQL Injection adalah serangan di mana penyerang menyisipkan kode SQL berbahaya melalui input pengguna.

```sql
-- Skenario Serangan SQL Injection
-- Input dari user: email = "' OR '1'='1"

-- ❌ Query yang rentan (string concatenation)
-- Di kode aplikasi:
-- query = "SELECT * FROM users WHERE email = '" + userInput + "'"

-- Hasil query yang terbentuk:
SELECT * FROM users WHERE email = '' OR '1'='1'
-- Ini akan mengembalikan SEMUA user! 🚨

-- Input lebih berbahaya: "'; DROP TABLE users; --"
-- Hasil:
SELECT * FROM users WHERE email = ''; DROP TABLE users; --'
-- Ini akan MENGHAPUS tabel users! 🚨🚨🚨
```

```javascript
// ✅ SOLUSI: Selalu gunakan Parameterized Query

// ❌ BERBAHAYA: String concatenation
const query = `SELECT * FROM users WHERE email = '${userEmail}'`;

// ✅ AMAN: Parameterized query
const query = 'SELECT * FROM users WHERE email = $1';
const values = [userEmail];
const result = await pool.query(query, values);

// Library database akan secara otomatis escape karakter berbahaya
// Input: "' OR '1'='1" akan diperlakukan sebagai string literal
// bukan sebagai kode SQL
```

### Prinsip Keamanan Database

```sql
-- 1. Principle of Least Privilege
-- Buat user database dengan hak akses minimal

-- User untuk aplikasi (hanya SELECT, INSERT, UPDATE, DELETE)
CREATE USER app_user WITH PASSWORD 'strong_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;

-- User untuk backup (hanya SELECT)
CREATE USER backup_user WITH PASSWORD 'another_strong_password';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO backup_user;

-- 2. Jangan simpan data sensitif dalam plaintext
-- ❌ Buruk
INSERT INTO users (password) VALUES ('mypassword');

-- ✅ Baik (hash di aplikasi)
INSERT INTO users (password) VALUES ('$2b$10$...');  -- bcrypt hash

-- 3. Enkripsi data sangat sensitif
-- Nomor kartu kredit, NIK, dll harus dienkripsi
```

---

## SECTION 16 — PERFORMANCE BASICS

### Memahami Index

Index adalah struktur data yang mempercepat pencarian, mirip seperti indeks di buku.

```sql
-- Tanpa index: Database scan SEMUA baris (Full Table Scan)
-- Dengan 1 juta baris, ini sangat lambat!
SELECT * FROM users WHERE email = 'budi@email.com';

-- Membuat index pada kolom email
CREATE INDEX idx_users_email ON users(email);

-- Sekarang query di atas jauh lebih cepat!
-- Database langsung melompat ke lokasi data yang tepat

-- Index otomatis dibuat untuk PRIMARY KEY dan UNIQUE constraint
-- Kolom yang sering digunakan dalam WHERE, JOIN, ORDER BY
-- adalah kandidat yang baik untuk di-index

-- Melihat query plan (apakah menggunakan index?)
EXPLAIN SELECT * FROM users WHERE email = 'budi@email.com';
```

### Kapan Menggunakan Index

```
✅ Buat index pada:
   - Kolom yang sering digunakan dalam WHERE
   - Kolom yang digunakan dalam JOIN (Foreign Key)
   - Kolom yang sering di-ORDER BY
   - Kolom dengan nilai yang banyak variasinya (high cardinality)

❌ Hindari index berlebihan pada:
   - Kolom yang jarang diquery
   - Tabel yang sangat sering di-INSERT/UPDATE (index memperlambat write)
   - Kolom dengan sedikit variasi nilai (misal: kolom boolean)
```

---

## SECTION 17 — COMPARISON TABLE

### Perbandingan DBMS Populer untuk Backend Beginner

| Fitur | PostgreSQL | MySQL | SQLite | MongoDB |
|-------|-----------|-------|--------|---------|
| **Tipe** | Relasional | Relasional | Relasional | Non-relasional |
| **Lisensi** | Open Source | Open Source | Public Domain | SSPL |
| **Kemudahan Setup** | Sedang | Mudah | Sangat Mudah | Mudah |
| **Performa** | Sangat Baik | Baik | Baik (kecil) | Sangat Baik |
| **Fitur SQL** | Sangat Lengkap | Lengkap | Terbatas | N/A |
| **ACID** | ✅ Penuh | ✅ (InnoDB) | ✅ | ⚠️ Partial |
| **JSON Support** | ✅ Native | ✅ | ❌ | ✅ Native |
| **Cocok untuk** | Production, Kompleks | Web Apps | Development, Mobile | Dokumen, Fleksibel |
| **Digunakan oleh** | Instagram, Spotify | WordPress, Airbnb | iOS, Android | Uber, eBay |

### Rekomendasi untuk Pemula

```
Untuk Belajar:     SQLite (tidak perlu instalasi server)
Untuk Development: PostgreSQL dengan Docker
Untuk Production:  PostgreSQL atau MySQL (tergantung kebutuhan)
```

---

## SECTION 18 — GLOSSARY

| Istilah | Definisi |
|---------|----------|
| **ACID** | Atomicity, Consistency, Isolation, Durability — properti transaksi database |
| **Constraint** | Aturan yang membatasi nilai yang dapat disimpan dalam kolom |
| **CRUD** | Create, Read, Update, Delete — empat operasi dasar database |
| **DBMS** | Database Management System — perangkat lunak pengelola database |
| **DDL** | Data Definition Language — SQL untuk mendefinisikan struktur (CREATE, ALTER, DROP) |
| **DML** | Data Manipulation Language — SQL untuk memanipulasi data (SELECT, INSERT, UPDATE, DELETE) |
| **Foreign Key** | Kolom yang mereferensikan Primary Key di tabel lain |
| **Index** | Struktur data untuk mempercepat pencarian |
| **JOIN** | Operasi menggabungkan data dari dua atau lebih tabel |
| **NULL** | Nilai yang merepresentasikan "tidak ada data" |
| **Primary Key** | Kolom (atau kombinasi kolom) yang secara unik mengidentifikasi setiap baris |
| **Query** | Perintah SQL untuk berinteraksi dengan database |
| **Schema** | Struktur atau blueprint database (kumpulan tabel dan relasinya) |
| **SQL** | Structured Query Language — bahasa standar untuk database relasional |
| **Transaction** | Sekelompok operasi yang dieksekusi sebagai satu unit atomik |
| **UUID** | Universally Unique Identifier — ID unik 128-bit |
| **VARCHAR** | Variable Character — tipe data string dengan panjang variabel |
| **View** | Tabel virtual berdasarkan hasil query |

---

## SECTION 19 — FURTHER READING & RESOURCES

### Dokumentasi Resmi

```
PostgreSQL:
  https://www.postgresql.org/docs/current/

MySQL:
  https://dev.mysql.com/doc/

SQLite:
  https://www.sqlite.org/docs.html
```

### Tutorial Interaktif

```
1. SQLZoo (https://sqlzoo.net/)
   - Tutorial SQL interaktif dengan latihan langsung
   - Gratis, berbasis browser

2. Mode SQL Tutorial (https://mode.com/sql-tutorial/)
   - Tutorial komprehensif dari dasar hingga advanced
   - Gratis

3. Khan Academy - SQL (https://www.khanacademy.org/computing/computer-programming/sql)
   - Video + latihan interaktif
   - Gratis

4. LeetCode Database Problems (https://leetcode.com/problemset/database/)
   - Latihan SQL dengan problem nyata
   - Gratis (sebagian)
```

### Buku Referensi

```
1. "Learning SQL" - Alan Beaulieu (O'Reilly)
   Level: Pemula hingga Menengah

2. "SQL Antipatterns" - Bill Karwin (Pragmatic Bookshelf)
   Level: Menengah (kesalahan umum dan cara menghindarinya)

3. "Database Design for Mere Mortals" - Michael J. Hernandez
   Level: Pemula (fokus pada desain skema)
```

### Tools yang Direkomendasikan

```
Query Builder/ORM (untuk integrasi dengan kode):
  - Knex.js (Node.js Query Builder)
  - Sequelize (Node.js ORM)
  - Prisma (Modern ORM untuk Node.js/TypeScript)
  - SQLAlchemy (Python ORM)

Database GUI:
  - DBeaver (Gratis, semua platform)
  - TablePlus (Berbayar, UI terbaik)
  - pgAdmin (Gratis, khusus PostgreSQL)
```

---

## SECTION 20 — SUMMARY & NEXT STEPS

### Ringkasan Materi

Dalam modul ini, kita telah mempelajari:

```
✅ Konsep Fundamental Database
   ├── Apa itu database dan DBMS
   ├── Struktur: Database → Table → Column → Row
   └── Perbedaan SQL vs NoSQL

✅ SQL Dasar (CRUD)
   ├── CREATE TABLE dengan tipe data dan constraint
   ├── INSERT INTO untuk menambah data
   ├── SELECT dengan WHERE, ORDER BY, LIMIT
   ├── UPDATE SET untuk mengubah data
   └── DELETE FROM untuk menghapus data

✅ Desain Skema
   ├── Primary Key dan Foreign Key
   ├── Constraint (NOT NULL, UNIQUE, CHECK)
   └── Pemilihan tipe data yang tepat

✅ Praktik Terbaik
   ├── Selalu gunakan WHERE pada UPDATE/DELETE
   ├── Gunakan parameterized query (anti SQL Injection)
   ├── Pilih tipe data yang sesuai
   └── Dokumentasikan skema

✅ Integrasi Backend
   └── Menghubungkan database dengan Node.js
```

### Peta Perjalanan Belajar

```
SEKARANG (Bab 05 Modul 01)
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│  ✅ Database Fundamentals & SQL Dasar                     │
│     - CRUD Operations                                     │
│     - Tipe Data & Constraint                              │
│     - Primary Key & Foreign Key                           │
└───────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│  📌 BERIKUTNYA (Bab 05 Modul 02)                         │
│     - SQL Lanjutan: JOIN (INNER, LEFT, RIGHT, FULL)       │
│     - Aggregate Functions (COUNT, SUM, AVG, MIN, MAX)     │
│     - GROUP BY dan HAVING                                 │
│     - Subquery                                            │
└───────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│  📌 BERIKUTNYA (Bab 05 Modul 03)                         │
│     - Database Design & Normalisasi (1NF, 2NF, 3NF)      │
│     - Indexing Strategy                                   │
│     - Transactions & ACID                                 │
└───────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│  📌 BERIKUTNYA (Bab 05 Modul 04)                         │
│     - ORM (Object-Relational Mapping)                     │
│     - Database Migration                                  │
│     - Connection Pooling                                  │
└───────────────────────────────────────────────────────────┘
```

### Checklist Kompetensi Modul Ini

Sebelum melanjutkan ke modul berikutnya, pastikan Anda dapat:

```
□ Menjelaskan perbedaan antara database, tabel, kolom, dan baris
□ Membuat tabel dengan tipe data dan constraint yang tepat
□ Menulis query INSERT untuk menambah satu atau beberapa baris
□ Menulis query SELECT dengan WHERE, ORDER BY, dan LIMIT
□ Menulis query UPDATE dengan kondisi WHERE yang spesifik
□ Menulis query DELETE dengan kondisi WHERE yang spesifik
□ Menjelaskan apa itu Primary Key dan Foreign Key
□ Menjalankan query SQL di PostgreSQL atau MySQL
□ Menghubungkan database ke aplikasi Node.js sederhana
□ Menjelaskan mengapa parameterized query penting untuk keamanan
```

### Mini Project: Sistem Manajemen Kontak

Sebagai latihan akhir modul, bangun sistem manajemen kontak sederhana:

```sql
-- Spesifikasi:
-- 1. Tabel 'kontak' dengan field: id, nama, email, telepon, kategori, created_at
-- 2. Tabel 'catatan' dengan field: id, kontak_id, isi_catatan, created_at
-- 3. Constraint yang tepat (NOT NULL, UNIQUE, FK, CHECK)
-- 4. Insert minimal 5 kontak dan 3 catatan
-- 5. Query: tampilkan semua kontak beserta jumlah catatannya
-- 6. Query: cari kontak berdasarkan nama (LIKE)
-- 7. Update: ubah nomor telepon kontak tertentu
-- 8. Delete: hapus kontak yang tidak aktif

-- Selamat mencoba! 🚀
```

---

*Modul ini adalah bagian dari kurikulum **Backend Beginner** — Kategori **01-Core-Foundations**.*
*Versi: 1.0 | Estimasi Waktu Belajar: 6-8 jam | Tingkat Kesulitan: ⭐⭐☆☆☆*