# Bab 06 – Module 01: Pengantar Database dan SQL Fundamentals

## Kurikulum: Backend Beginner | Kategori: 01-Core-Foundations

---

## SECTION 01 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:

1. **Menjelaskan** konsep database relasional dan peran pentingnya dalam arsitektur backend modern
2. **Membedakan** jenis-jenis database (relasional vs non-relasional) beserta kasus penggunaan masing-masing
3. **Memahami** struktur fundamental: tabel, baris, kolom, primary key, dan foreign key
4. **Menulis** pernyataan SQL dasar: `SELECT`, `INSERT`, `UPDATE`, `DELETE` dengan benar
5. **Menerapkan** filter data menggunakan `WHERE`, `ORDER BY`, `LIMIT`, dan `GROUP BY`
6. **Menggunakan** `JOIN` untuk menggabungkan data dari beberapa tabel
7. **Merancang** skema database sederhana mengikuti prinsip normalisasi dasar
8. **Mengintegrasikan** database ke dalam aplikasi backend menggunakan koneksi dan query terparameterisasi
9. **Mengidentifikasi** risiko SQL Injection dan menerapkan pencegahannya
10. **Mengevaluasi** trade-off antara pendekatan SQL dan NoSQL untuk kebutuhan proyek nyata

---

## SECTION 02 — CONCEPT OVERVIEW

### Apa Itu Database?

**Database** adalah sistem terorganisir untuk menyimpan, mengelola, dan mengambil data secara efisien dan persisten. Dalam konteks backend development, database adalah **lapisan persistensi** — tempat data hidup melampaui siklus hidup satu request HTTP.

### Ekosistem Database dalam Arsitektur Backend

```
┌─────────────────────────────────────────────────┐
│              ARSITEKTUR BACKEND                  │
│                                                  │
│  Client → API Layer → Business Logic → Database  │
│                                        ↑         │
│                              (Modul ini fokus di sini)
└─────────────────────────────────────────────────┘
```

### Tiga Pilar Konsep Database

| Pilar | Deskripsi | Contoh |
|-------|-----------|--------|
| **Struktur** | Cara data diorganisir | Tabel, kolom, tipe data |
| **Integritas** | Aturan konsistensi data | Primary key, constraint |
| **Akses** | Cara data dibaca/ditulis | SQL query, index |

### Relational Database Management System (RDBMS)

RDBMS adalah implementasi database yang mengorganisir data dalam **tabel dua dimensi** (baris dan kolom) dengan hubungan antar tabel yang terdefinisi secara eksplisit. Contoh populer:

- **PostgreSQL** — Open source, fitur enterprise, sangat direkomendasikan untuk produksi
- **MySQL / MariaDB** — Populer di ekosistem web, performa tinggi untuk read-heavy
- **SQLite** — Embedded, file-based, ideal untuk development dan aplikasi kecil
- **Microsoft SQL Server** — Enterprise, ekosistem Microsoft
- **Oracle Database** — Enterprise skala besar

> **Fokus Modul Ini:** PostgreSQL sebagai representasi RDBMS modern dengan SQL standar.

---

## SECTION 03 — WHY THIS MATTERS

### Mengapa Database Adalah Kompetensi Inti Backend Developer?

#### 1. Semua Aplikasi Membutuhkan Persistensi Data

Tanpa database, data hilang setiap kali server restart. Bayangkan aplikasi e-commerce yang kehilangan semua order setiap malam — tidak ada aplikasi nyata yang bisa berjalan tanpa persistensi.

#### 2. Database Adalah Bottleneck Paling Umum

Dalam profiling performa aplikasi backend, **60-80% masalah performa** berasal dari query database yang tidak efisien. Memahami SQL dengan baik langsung berdampak pada kualitas sistem yang Anda bangun.

#### 3. SQL Adalah Bahasa Universal

SQL telah ada sejak 1974 dan masih menjadi standar industri. Skill SQL yang Anda pelajari hari ini berlaku di PostgreSQL, MySQL, SQLite, dan hampir semua sistem database enterprise.

#### 4. Keputusan Database Berdampak Jangka Panjang

Skema database yang buruk sangat mahal untuk diperbaiki setelah produksi. Migrasi data di sistem dengan jutaan record adalah operasi berisiko tinggi. **Merancang dengan benar dari awal** menghemat waktu dan uang.

#### 5. Relevansi Karir

Berdasarkan survei Stack Overflow Developer Survey 2023:
- **PostgreSQL** adalah database paling populer (49.1% penggunaan)
- **MySQL** di posisi kedua (40.8%)
- Hampir **100% posisi backend developer** mensyaratkan pemahaman SQL

---

## SECTION 04 — WHAT YOU NEED TO KNOW (Konsep Fundamental)

### 4.1 Anatomi Tabel Database

Tabel adalah unit penyimpanan fundamental dalam RDBMS:

```
TABEL: users
┌────┬──────────────┬───────────────────────┬─────────────┬────────────────────┐
│ id │ username     │ email                 │ age         │ created_at         │
│ PK │ VARCHAR(50)  │ VARCHAR(255)          │ INTEGER     │ TIMESTAMP          │
├────┼──────────────┼───────────────────────┼─────────────┼────────────────────┤
│  1 │ alice_dev    │ alice@example.com     │ 28          │ 2024-01-15 09:00   │
│  2 │ bob_coder    │ bob@example.com       │ 34          │ 2024-01-16 14:30   │
│  3 │ carol_eng    │ carol@example.com     │ 25          │ 2024-01-17 11:15   │
└────┴──────────────┴───────────────────────┴─────────────┴────────────────────┘
  ↑                                                                    ↑
Primary Key                                                      Metadata otomatis
(unik, tidak null)
```

**Terminologi Penting:**
- **Tabel (Table/Relation):** Kumpulan data bertopik sama, seperti spreadsheet
- **Baris (Row/Record/Tuple):** Satu entitas data lengkap
- **Kolom (Column/Field/Attribute):** Satu properti dari entitas
- **Primary Key (PK):** Identifier unik untuk setiap baris
- **Foreign Key (FK):** Referensi ke primary key tabel lain

### 4.2 Tipe Data SQL Fundamental

```
┌─────────────────┬──────────────────────────────────┬─────────────────────┐
│ Kategori        │ Tipe Data                        │ Contoh Nilai        │
├─────────────────┼──────────────────────────────────┼─────────────────────┤
│ Teks            │ VARCHAR(n), TEXT, CHAR(n)        │ 'Alice', 'Halo'     │
│ Angka Bulat     │ INTEGER, BIGINT, SMALLINT        │ 42, 1000000         │
│ Angka Desimal   │ DECIMAL(p,s), NUMERIC, FLOAT     │ 99.99, 3.14         │
│ Boolean         │ BOOLEAN                          │ TRUE, FALSE         │
│ Tanggal/Waktu   │ DATE, TIME, TIMESTAMP            │ '2024-01-15'        │
│ JSON            │ JSON, JSONB (PostgreSQL)         │ '{"key": "value"}'  │
│ UUID            │ UUID                             │ 'a1b2c3d4-...'      │
└─────────────────┴──────────────────────────────────┴─────────────────────┘
```

### 4.3 Hubungan Antar Tabel (Relationships)

**One-to-Many (1:N)** — Paling umum:
```
Satu USER memiliki banyak ORDERS
users.id ←── orders.user_id
```

**Many-to-Many (N:M)** — Memerlukan tabel junction:
```
STUDENTS ←── student_courses ──→ COURSES
```

**One-to-One (1:1)** — Jarang, biasanya untuk pemisahan data sensitif:
```
users.id ←── user_profiles.user_id (UNIQUE)
```

### 4.4 Struktur Perintah SQL

SQL dibagi menjadi sub-bahasa berdasarkan fungsinya:

```
┌─────────────────────────────────────────────────────────────┐
│                    KATEGORI SQL                              │
├──────────┬──────────────────────────────────────────────────┤
│ DDL      │ Data Definition Language                         │
│          │ CREATE, ALTER, DROP, TRUNCATE                    │
│          │ → Mendefinisikan struktur database               │
├──────────┼──────────────────────────────────────────────────┤
│ DML      │ Data Manipulation Language                       │
│          │ SELECT, INSERT, UPDATE, DELETE                   │
│          │ → Memanipulasi data dalam tabel                  │
├──────────┼──────────────────────────────────────────────────┤
│ DCL      │ Data Control Language                            │
│          │ GRANT, REVOKE                                    │
│          │ → Mengatur hak akses                             │
├──────────┼──────────────────────────────────────────────────┤
│ TCL      │ Transaction Control Language                     │
│          │ BEGIN, COMMIT, ROLLBACK                          │
│          │ → Mengelola transaksi                            │
└──────────┴──────────────────────────────────────────────────┘
```

---

## SECTION 05 — HOW IT WORKS (Mekanisme Internal)

### 5.1 Bagaimana Query SQL Diproses

Ketika Anda mengirim query SQL ke database, terjadi proses multi-tahap:

```
Query SQL dari Aplikasi
        │
        ▼
┌───────────────────┐
│   SQL Parser      │  ← Validasi sintaks, apakah SQL valid?
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Query Analyzer   │  ← Validasi semantik, apakah tabel/kolom ada?
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Query Optimizer  │  ← Pilih execution plan paling efisien
│  (Query Planner)  │    (gunakan index? full scan? join order?)
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Execution Engine │  ← Jalankan plan, akses storage
└───────────────────┘
        │
        ▼
┌───────────────────┐
│   Storage Layer   │  ← Baca/tulis data dari disk/memory
└───────────────────┘
        │
        ▼
   Result Set dikembalikan ke aplikasi
```

### 5.2 Konsep Index

**Index** adalah struktur data tambahan yang mempercepat pencarian, mirip indeks di buku:

```
TANPA INDEX (Full Table Scan):
Cari user dengan email 'alice@example.com'
→ Baca baris 1... bukan ini
→ Baca baris 2... bukan ini
→ Baca baris 3... KETEMU! (sudah baca 3 baris)
→ Untuk 1 juta baris: rata-rata 500.000 pembacaan

DENGAN INDEX pada kolom email (B-Tree):
→ Langsung ke posisi 'alice@...' di tree
→ Ketemu dalam O(log n) operasi
→ Untuk 1 juta baris: ~20 pembacaan
```

### 5.3 Siklus Koneksi Database

```
Aplikasi Backend
     │
     │ 1. Buka koneksi (TCP handshake + auth)
     ▼
Database Server
     │
     │ 2. Kirim query
     │ 3. Terima result
     │
     │ 4. Tutup koneksi (atau kembalikan ke pool)
     ▼
Connection Pool (untuk efisiensi)
```

**Connection Pool** adalah kumpulan koneksi yang sudah dibuka dan siap digunakan ulang, menghindari overhead membuka koneksi baru setiap request.

---

## SECTION 06 — ASCII DIAGRAM: Arsitektur Database Relasional

```
╔══════════════════════════════════════════════════════════════════════════╗
║              ARSITEKTUR DATABASE RELASIONAL - GAMBARAN LENGKAP          ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │                    APLIKASI BACKEND (Node.js)                    │    ║
║  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │    ║
║  │  │  Route Layer │───▶│ Business     │───▶│  Database Layer  │  │    ║
║  │  │  (Express)   │    │ Logic Layer  │    │  (Query Builder/ │  │    ║
║  │  └──────────────┘    └──────────────┘    │   Raw SQL/ORM)   │  │    ║
║  └────────────────────────────────────────────────────┬──────────┘    ║
║                                                        │               ║
║                                              SQL Query │               ║
║                                                        ▼               ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │                    CONNECTION POOL                               │    ║
║  │   [Conn 1] [Conn 2] [Conn 3] ... [Conn N]                      │    ║
║  │   (Koneksi siap pakai, menghindari overhead buka koneksi baru)  │    ║
║  └────────────────────────────────┬────────────────────────────────┘    ║
║                                   │                                      ║
║                                   ▼                                      ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │                   DATABASE SERVER (PostgreSQL)                   │    ║
║  │                                                                  │    ║
║  │  ┌──────────────────────────────────────────────────────────┐   │    ║
║  │  │                    DATABASE: myapp_db                     │   │    ║
║  │  │                                                           │   │    ║
║  │  │  ┌─────────────┐  FK   ┌─────────────┐                  │   │    ║
║  │  │  │   TABEL     │◀──────│   TABEL     │                  │   │    ║
║  │  │  │   users     │       │   orders    │                  │   │    ║
║  │  │  │─────────────│       │─────────────│                  │   │    ║
║  │  │  │ id (PK)     │       │ id (PK)     │                  │   │    ║
║  │  │  │ username    │       │ user_id(FK) │                  │   │    ║
║  │  │  │ email       │       │ total_price │                  │   │    ║
║  │  │  │ created_at  │       │ status      │                  │   │    ║
║  │  │  └─────────────┘       └──────┬──────┘                  │   │    ║
║  │  │                               │ FK                       │   │    ║
║  │  │                               ▼                          │   │    ║
║  │  │                        ┌─────────────┐                  │   │    ║
║  │  │                        │   TABEL     │                  │   │    ║
║  │  │                        │ order_items │                  │   │    ║
║  │  │                        │─────────────│                  │   │    ║
║  │  │                        │ id (PK)     │                  │   │    ║
║  │  │                        │ order_id(FK)│                  │   │    ║
║  │  │                        │ product_id  │                  │   │    ║
║  │  │                        │ quantity    │                  │   │    ║
║  │  │                        └─────────────┘                  │   │    ║
║  │  └──────────────────────────────────────────────────────────┘   │    ║
║  │                                                                  │    ║
║  │  ┌──────────────────────────────────────────────────────────┐   │    ║
║  │  │                    STORAGE ENGINE                         │   │    ║
║  │  │  [Buffer Pool/Cache] ←→ [Disk Storage / WAL Log]         │   │    ║
║  │  └──────────────────────────────────────────────────────────┘   │    ║
║  └─────────────────────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## SECTION 07 — SIMPLE EXAMPLE (Contoh Minimal)

### Setup: Membuat Database dan Tabel Pertama

```sql
-- ============================================================
-- LANGKAH 1: Buat database (jalankan sebagai superuser)
-- ============================================================
CREATE DATABASE bookstore_db;

-- ============================================================
-- LANGKAH 2: Buat tabel pertama
-- ============================================================
CREATE TABLE books (
    id          SERIAL PRIMARY KEY,        -- Auto-increment integer
    title       VARCHAR(255) NOT NULL,     -- Wajib diisi
    author      VARCHAR(100) NOT NULL,
    price       DECIMAL(10, 2) NOT NULL,   -- 10 digit total, 2 desimal
    stock       INTEGER DEFAULT 0,         -- Default 0 jika tidak diisi
    published_at DATE,                     -- Boleh NULL
    created_at  TIMESTAMP DEFAULT NOW()    -- Otomatis diisi waktu sekarang
);

-- ============================================================
-- LANGKAH 3: INSERT - Tambah data
-- ============================================================
INSERT INTO books (title, author, price, stock, published_at)
VALUES
    ('Clean Code', 'Robert C. Martin', 89000, 15, '2008-08-01'),
    ('The Pragmatic Programmer', 'David Thomas', 95000, 8, '1999-10-20'),
    ('Design Patterns', 'Gang of Four', 120000, 3, '1994-10-31');

-- ============================================================
-- LANGKAH 4: SELECT - Baca data
-- ============================================================
SELECT * FROM books;

-- Output:
-- id | title                    | author              | price  | stock | published_at | created_at
-- ---+--------------------------+---------------------+--------+-------+--------------+-------------------
--  1 | Clean Code               | Robert C. Martin    | 89000  |    15 | 2008-08-01   | 2024-01-15 10:00
--  2 | The Pragmatic Programmer | David Thomas        | 95000  |     8 | 1999-10-20   | 2024-01-15 10:00
--  3 | Design Patterns          | Gang of Four        | 120000 |     3 | 1994-10-31   | 2024-01-15 10:00

-- ============================================================
-- LANGKAH 5: UPDATE - Ubah data
-- ============================================================
UPDATE books
SET price = 92000, stock = 20
WHERE id = 1;

-- ============================================================
-- LANGKAH 6: DELETE - Hapus data
-- ============================================================
DELETE FROM books
WHERE id = 3;

-- ============================================================
-- LANGKAH 7: SELECT dengan filter
-- ============================================================
SELECT title, author, price
FROM books
WHERE price < 100000
ORDER BY price ASC;

-- Output:
-- title                    | author           | price
-- -------------------------+------------------+-------
-- Clean Code               | Robert C. Martin | 92000
-- The Pragmatic Programmer | David Thomas     | 95000
```

---

## SECTION 08 — PRACTICAL EXAMPLE (Contoh Nyata: Sistem E-Commerce Mini)

### Skenario: Backend untuk Toko Online Sederhana

Kita akan membangun skema database dan query untuk sistem e-commerce dengan fitur: manajemen produk, user, dan order.

#### 8.1 Skema Database Lengkap

```sql
-- ============================================================
-- FILE: schema.sql
-- Skema database untuk e-commerce mini
-- ============================================================

-- Tabel users: menyimpan data pelanggan
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    username    VARCHAR(50) UNIQUE NOT NULL,
    email       VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,    -- JANGAN simpan plain text!
    full_name   VARCHAR(100),
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- Tabel categories: kategori produk
CREATE TABLE categories (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE NOT NULL,
    slug        VARCHAR(100) UNIQUE NOT NULL,  -- URL-friendly: 'elektronik'
    description TEXT
);

-- Tabel products: katalog produk
CREATE TABLE products (
    id           SERIAL PRIMARY KEY,
    category_id  INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    name         VARCHAR(255) NOT NULL,
    description  TEXT,
    price        DECIMAL(12, 2) NOT NULL CHECK (price >= 0),
    stock        INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    sku          VARCHAR(100) UNIQUE,          -- Stock Keeping Unit
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMP DEFAULT NOW(),
    updated_at   TIMESTAMP DEFAULT NOW()
);

-- Tabel orders: header transaksi
CREATE TABLE orders (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status       VARCHAR(20) NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'paid', 'shipped', 'delivered', 'cancelled')),
    total_amount DECIMAL(12, 2) NOT NULL DEFAULT 0,
    shipping_address TEXT,
    notes        TEXT,
    created_at   TIMESTAMP DEFAULT NOW(),
    updated_at   TIMESTAMP DEFAULT NOW()
);

-- Tabel order_items: detail item dalam setiap order
CREATE TABLE order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    unit_price  DECIMAL(12, 2) NOT NULL,  -- Harga saat pembelian (snapshot)
    subtotal    DECIMAL(12, 2) GENERATED ALWAYS AS (quantity * unit_price) STORED
);

-- Index untuk performa query yang sering digunakan
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_order_items_order_id ON order_items(order_id);
```

#### 8.2 Data Seeding (Data Awal)

```sql
-- ============================================================
-- FILE: seed.sql
-- Data awal untuk development/testing
-- ============================================================

-- Insert categories
INSERT INTO categories (name, slug, description) VALUES
    ('Elektronik', 'elektronik', 'Gadget dan perangkat elektronik'),
    ('Buku', 'buku', 'Buku teknis dan non-teknis'),
    ('Pakaian', 'pakaian', 'Fashion pria dan wanita');

-- Insert products
INSERT INTO products (category_id, name, price, stock, sku) VALUES
    (1, 'Laptop Gaming ASUS ROG', 15000000, 10, 'ASUS-ROG-001'),
    (1, 'Mechanical Keyboard Keychron K2', 1200000, 25, 'KEY-K2-001'),
    (1, 'Monitor LG 27" 4K', 5500000, 8, 'LG-27-4K-001'),
    (2, 'Clean Code - Robert Martin', 89000, 50, 'BOOK-CC-001'),
    (2, 'System Design Interview', 150000, 30, 'BOOK-SDI-001');

-- Insert users (password_hash adalah bcrypt dari 'password123')
INSERT INTO users (username, email, password_hash, full_name) VALUES
    ('alice_dev', 'alice@example.com', '$2b$10$...hash...', 'Alice Pratiwi'),
    ('bob_coder', 'bob@example.com', '$2b$10$...hash...', 'Bob Santoso');
```

#### 8.3 Query Operasional Penting

```sql
-- ============================================================
-- QUERY 1: Tampilkan semua produk dengan nama kategori
-- (menggunakan JOIN)
-- ============================================================
SELECT
    p.id,
    p.name AS product_name,
    c.name AS category_name,
    p.price,
    p.stock,
    CASE
        WHEN p.stock = 0 THEN 'Habis'
        WHEN p.stock < 5 THEN 'Stok Menipis'
        ELSE 'Tersedia'
    END AS stock_status
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
WHERE p.is_active = TRUE
ORDER BY c.name, p.name;

-- Output:
-- id | product_name                    | category_name | price     | stock | stock_status
-- ---+---------------------------------+---------------+-----------+-------+--------------
--  4 | Clean Code - Robert Martin      | Buku          | 89000     |    50 | Tersedia
--  5 | System Design Interview         | Buku          | 150000    |    30 | Tersedia
--  2 | Mechanical Keyboard Keychron K2 | Elektronik    | 1200000   |    25 | Tersedia
--  3 | Monitor LG 27" 4K               | Elektronik    | 5500000   |     8 | Tersedia
--  1 | Laptop Gaming ASUS ROG          | Elektronik    | 15000000  |    10 | Tersedia


-- ============================================================
-- QUERY 2: Buat order baru (dalam transaksi)
-- ============================================================
BEGIN;

-- Buat header order
INSERT INTO orders (user_id, shipping_address, notes)
VALUES (1, 'Jl. Sudirman No. 123, Jakarta', 'Tolong dibungkus rapi')
RETURNING id;  -- Ambil ID order yang baru dibuat, misal: 1

-- Tambah item ke order
INSERT INTO order_items (order_id, product_id, quantity, unit_price)
VALUES
    (1, 1, 1, 15000000),  -- 1 Laptop
    (1, 2, 2, 1200000);   -- 2 Keyboard

-- Update total amount di order
UPDATE orders
SET total_amount = (
    SELECT SUM(subtotal) FROM order_items WHERE order_id = 1
)
WHERE id = 1;

-- Kurangi stok produk
UPDATE products SET stock = stock - 1 WHERE id = 1;
UPDATE products SET stock = stock - 2 WHERE id = 2;

COMMIT;


-- ============================================================
-- QUERY 3: Laporan order detail untuk user tertentu
-- ============================================================
SELECT
    o.id AS order_id,
    o.status,
    o.total_amount,
    o.created_at AS order_date,
    p.name AS product_name,
    oi.quantity,
    oi.unit_price,
    oi.subtotal
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
WHERE o.user_id = 1
ORDER BY o.created_at DESC, oi.id;


-- ============================================================
-- QUERY 4: Statistik penjualan per kategori (GROUP BY)
-- ============================================================
SELECT
    c.name AS category_name,
    COUNT(DISTINCT o.id) AS total_orders,
    SUM(oi.quantity) AS total_items_sold,
    SUM(oi.subtotal) AS total_revenue,
    AVG(oi.unit_price) AS avg_item_price
FROM categories c
JOIN products p ON c.id = p.category_id
JOIN order_items oi ON p.id = oi.product_id
JOIN orders o ON oi.order_id = o.id
WHERE o.status IN ('paid', 'shipped', 'delivered')
GROUP BY c.id, c.name
ORDER BY total_revenue DESC;


-- ============================================================
-- QUERY 5: Produk yang stoknya menipis (perlu restock)
-- ============================================================
SELECT
    p.sku,
    p.name,
    p.stock,
    c.name AS category
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
WHERE p.stock < 5 AND p.is_active = TRUE
ORDER BY p.stock ASC;
```

#### 8.4 Integrasi dengan Node.js (Backend Code)

```javascript
// ============================================================
// FILE: src/database/connection.js
// Setup koneksi database dengan connection pool
// ============================================================
const { Pool } = require('pg');

const pool = new Pool({
    host: process.env.DB_HOST || 'localhost',
    port: process.env.DB_PORT || 5432,
    database: process.env.DB_NAME || 'ecommerce_db',
    user: process.env.DB_USER || 'postgres',
    password: process.env.DB_PASSWORD,
    max: 20,                    // Maksimum 20 koneksi dalam pool
    idleTimeoutMillis: 30000,   // Tutup koneksi idle setelah 30 detik
    connectionTimeoutMillis: 2000, // Timeout jika tidak dapat koneksi dalam 2 detik
});

// Test koneksi saat startup
pool.on('connect', () => {
    console.log('✅ Database connection established');
});

pool.on('error', (err) => {
    console.error('❌ Unexpected database error:', err);
    process.exit(-1);
});

module.exports = pool;
```

```javascript
// ============================================================
// FILE: src/models/product.model.js
// Model untuk operasi CRUD produk
// ============================================================
const pool = require('../database/connection');

class ProductModel {

    // Ambil semua produk dengan filter opsional
    static async findAll({ categoryId, minPrice, maxPrice, search, limit = 20, offset = 0 } = {}) {
        // Parameterized query - AMAN dari SQL Injection
        const conditions = ['p.is_active = TRUE'];
        const params = [];
        let paramIndex = 1;

        if (categoryId) {
            conditions.push(`p.category_id = $${paramIndex++}`);
            params.push(categoryId);
        }

        if (minPrice !== undefined) {
            conditions.push(`p.price >= $${paramIndex++}`);
            params.push(minPrice);
        }

        if (maxPrice !== undefined) {
            conditions.push(`p.price <= $${paramIndex++}`);
            params.push(maxPrice);
        }

        if (search) {
            conditions.push(`p.name ILIKE $${paramIndex++}`);
            params.push(`%${search}%`);
        }

        params.push(limit, offset);

        const query = `
            SELECT
                p.id,
                p.name,
                p.price,
                p.stock,
                p.sku,
                c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE ${conditions.join(' AND ')}
            ORDER BY p.created_at DESC
            LIMIT $${paramIndex++} OFFSET $${paramIndex}
        `;

        const result = await pool.query(query, params);
        return result.rows;
    }

    // Ambil satu produk berdasarkan ID
    static async findById(id) {
        const query = `
            SELECT
                p.*,
                c.name AS category_name,
                c.slug AS category_slug
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.id = $1 AND p.is_active = TRUE
        `;

        const result = await pool.query(query, [id]);
        return result.rows[0] || null;
    }

    // Buat produk baru
    static async create({ categoryId, name, description, price, stock, sku }) {
        const query = `
            INSERT INTO products (category_id, name, description, price, stock, sku)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        `;

        const result = await pool.query(query, [
            categoryId, name, description, price, stock, sku
        ]);
        return result.rows[0];
    }

    // Update stok produk (dengan locking untuk concurrency)
    static async updateStock(client, productId, quantityChange) {
        // Gunakan SELECT FOR UPDATE untuk mencegah race condition
        const lockQuery = `
            SELECT stock FROM products
            WHERE id = $1
            FOR UPDATE
        `;
        const lockResult = await client.query(lockQuery, [productId]);

        if (!lockResult.rows[0]) {
            throw new Error(`Produk dengan ID ${productId} tidak ditemukan`);
        }

        const currentStock = lockResult.rows[0].stock;
        const newStock = currentStock + quantityChange;

        if (newStock < 0) {
            throw new Error(`Stok tidak mencukupi. Stok saat ini: ${currentStock}`);
        }

        const updateQuery = `
            UPDATE products
            SET stock = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING id, name, stock
        `;
        const result = await client.query(updateQuery, [newStock, productId]);
        return result.rows[0];
    }
}

module.exports = ProductModel;
```

```javascript
// ============================================================
// FILE: src/services/order.service.js
// Service untuk membuat order (menggunakan transaksi database)
// ============================================================
const pool = require('../database/connection');
const ProductModel = require('../models/product.model');

class OrderService {

    static async createOrder({ userId, items, shippingAddress, notes }) {
        // Dapatkan koneksi dari pool untuk transaksi
        const client = await pool.connect();

        try {
            // Mulai transaksi
            await client.query('BEGIN');

            // 1. Buat header order
            const orderResult = await client.query(
                `INSERT INTO orders (user_id, shipping_address, notes)
                 VALUES ($1, $2, $3)
                 RETURNING id`,
                [userId, shippingAddress, notes]
            );
            const orderId = orderResult.rows[0].id;

            let totalAmount = 0;

            // 2. Proses setiap item
            for (const item of items) {
                // Ambil harga terkini dan lock baris untuk update stok
                const productResult = await client.query(
                    `SELECT id, name, price, stock
                     FROM products
                     WHERE id = $1 AND is_active = TRUE
                     FOR UPDATE`,
                    [item.productId]
                );

                if (!productResult.rows[0]) {
                    throw new Error(`Produk ID ${item.productId} tidak ditemukan`);
                }

                const product = productResult.rows[0];

                if (product.stock < item.quantity) {
                    throw new Error(
                        `Stok ${product.name} tidak mencukupi. ` +
                        `Tersedia: ${product.stock}, diminta: ${item.quantity}`
                    );
                }

                // Insert order item dengan harga snapshot
                await client.query(
                    `INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                     VALUES ($1, $2, $3, $4)`,
                    [orderId, item.productId, item.quantity, product.price]
                );

                // Kurangi stok
                await client.query(
                    `UPDATE products SET stock = stock - $1, updated_at = NOW()
                     WHERE id = $2`,
                    [item.quantity, item.productId]
                );

                totalAmount += product.price * item.quantity;
            }

            // 3. Update total amount di order
            await client.query(
                `UPDATE orders SET total_amount = $1 WHERE id = $2`,
                [totalAmount, orderId]
            );

            // Commit transaksi - semua perubahan disimpan
            await client.query('COMMIT');

            return { orderId, totalAmount };

        } catch (error) {
            // Rollback - batalkan semua perubahan jika ada error
            await client.query('ROLLBACK');
            throw error;

        } finally {
            // Kembalikan koneksi ke pool
            client.release();
        }
    }
}

module.exports = OrderService;
```

```javascript
// ============================================================
// FILE: src/routes/product.routes.js
// Route handler untuk produk
// ============================================================
const express = require('express');
const router = express.Router();
const ProductModel = require('../models/product.model');

// GET /api/products?category=1&minPrice=100000&search=laptop
router.get('/', async (req, res) => {
    try {
        const {
            category: categoryId,
            minPrice,
            maxPrice,
            search,
            page = 1,
            limit = 20
        } = req.query;

        const offset = (page - 1) * limit;

        const products = await ProductModel.findAll({
            categoryId: categoryId ? parseInt(categoryId) : undefined,
            minPrice: minPrice ? parseFloat(minPrice) : undefined,
            maxPrice: maxPrice ? parseFloat(maxPrice) : undefined,
            search,
            limit: parseInt(limit),
            offset
        });

        res.json({
            success: true,
            data: products,
            pagination: {
                page: parseInt(page),
                limit: parseInt(limit),
                count: products.length
            }
        });

    } catch (error) {
        console.error('Error fetching products:', error);
        res.status(500).json({
            success: false,
            message: 'Gagal mengambil data produk'
        });
    }
});

// GET /api/products/:id
router.get('/:id', async (req, res) => {
    try {
        const product = await ProductModel.findById(req.params.id);

        if (!product) {
            return res.status(404).json({
                success: false,
                message: 'Produk tidak ditemukan'
            });
        }

        res.json({ success: true, data: product });

    } catch (error) {
        console.error('Error fetching product:', error);
        res.status(500).json({
            success: false,
            message: 'Gagal mengambil data produk'
        });
    }
});

module.exports = router;
```

---

## SECTION 09 — TRADE-OFFS & DECISION MATRIX

### 9.1 SQL vs NoSQL: Kapan Memilih Apa?

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DECISION MATRIX: SQL vs NoSQL                        │
├──────────────────────┬──────────────────────┬───────────────────────────┤
│ Kriteria             │ SQL (PostgreSQL)      │ NoSQL (MongoDB, Redis)    │
├──────────────────────┼──────────────────────┼───────────────────────────┤
│ Struktur Data        │ ✅ Terstruktur, skema │ ✅ Fleksibel, schema-less │
│                      │    tetap              │                           │
├──────────────────────┼──────────────────────┼───────────────────────────┤
│ Relasi Kompleks      │ ✅ JOIN native,       │ ❌ Sulit, perlu denorm    │
│                      │    foreign key        │                           │
├──────────────────────┼──────────────────────┼───────────────────────────┤
│ Konsistensi Data     │ ✅ ACID penuh         │ ⚠️ Eventual consistency   │
│                      │                      │    (tergantung DB)        │
├──────────────────────┼──────────────────────┼───────────────────────────┤
│ Skalabilitas         │ ⚠️ Vertikal lebih     │ ✅ Horizontal scaling     │
│                      │    mudah, horizontal  │    lebih mudah            │
│                      │    butuh usaha        │                           │
├──────────────────────┼──────────────────────┼───────────────────────────┤
│ Performa Read        │ ✅ Sangat baik dengan │ ✅ Sangat cepat untuk     │
│                      │    index              │    dokumen tunggal        │
├──────────────────────┼──────────────────────┼───────────────────────────┤
│ Performa Write       │ ⚠️ Lebih lambat       │ ✅ Sangat cepat           │
│                      │    (ACID overhead)    │                           │
├──────────────────────┼──────────────────────┼───────────────────────────┤
│ Query Kompleks       │ ✅ SQL sangat         │ ❌ Aggregation pipeline    │
│                      │    ekspresif          │    lebih rumit            │
├──────────────────────┼──────────────────────┼───────────────────────────┤
│ Cocok Untuk          │ E-commerce, Banking, │ Real-time analytics,      │
│                      │ ERP, CRM, Aplikasi   │ Caching, Katalog produk   │
│                      │ dengan relasi data   │ dengan variasi atribut,   │
│                      │ kompleks             │ Session storage           │
└──────────────────────┴──────────────────────┴───────────────────────────┘
```

### 9.2 Trade-off dalam Desain Skema

#### Normalisasi vs Denormalisasi

```
NORMALISASI TINGGI (3NF):
✅ Tidak ada duplikasi data
✅ Update mudah (satu tempat)
✅ Integritas data terjaga
❌ Query butuh banyak JOIN
❌ Performa read lebih lambat

DENORMALISASI:
✅ Query lebih cepat (data sudah di satu tempat)
✅ Lebih sedikit JOIN
❌ Duplikasi data
❌ Update harus di banyak tempat
❌ Risiko inkonsistensi data
```

**Rekomendasi:** Mulai dengan normalisasi penuh, denormalisasi hanya jika ada bukti performa yang membutuhkannya.

### 9.3 Index: Manfaat vs Biaya

```
DENGAN INDEX:
✅ SELECT lebih cepat (O(log n) vs O(n))
❌ INSERT/UPDATE/DELETE lebih lambat (index harus diupdate)
❌ Menggunakan storage tambahan
❌ Terlalu banyak index = overhead besar

ATURAN PRAKTIS:
→ Index pada kolom yang sering di-WHERE
→ Index pada foreign key
→ Index pada kolom yang sering di-ORDER BY
→ JANGAN index kolom dengan kardinalitas rendah (misal: boolean)
```

---

## SECTION 10 — BEST PRACTICES

### 10.1 Keamanan Database

```javascript
// ❌ BERBAHAYA: String concatenation - rentan SQL Injection
const userId = req.params.id; // Attacker bisa kirim: "1 OR 1=1"
const query = `SELECT * FROM users WHERE id = ${userId}`;
// Query menjadi: SELECT * FROM users WHERE id = 1 OR 1=1
// Mengembalikan SEMUA user!

// ✅ AMAN: Parameterized Query
const query = 'SELECT * FROM users WHERE id = $1';
const result = await pool.query(query, [userId]);
// Database memperlakukan $1 sebagai data, bukan SQL
```

### 10.2 Konvensi Penamaan

```sql
-- ✅ BAIK: snake_case, deskriptif, konsisten
CREATE TABLE order_items (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER REFERENCES orders(id),
    product_id      INTEGER REFERENCES products(id),
    unit_price      DECIMAL(12, 2),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ❌ BURUK: Tidak konsisten, ambigu
CREATE TABLE OrderItems (
    ID              SERIAL PRIMARY KEY,
    orderID         INTEGER,
    prod            INTEGER,
    price           DECIMAL(12, 2),
    date            TIMESTAMP DEFAULT NOW()
);
```

### 10.3 Selalu Gunakan Transaksi untuk Operasi Multi-Step

```javascript
// ✅ BENAR: Operasi terkait dibungkus dalam transaksi
const client = await pool.connect();
try {
    await client.query('BEGIN');
    // ... semua operasi terkait ...
    await client.query('COMMIT');
} catch (err) {
    await client.query('ROLLBACK');
    throw err;
} finally {
    client.release();
}
```

### 10.4 Hindari SELECT * di Produksi

```sql
-- ❌ BURUK: Mengambil semua kolom termasuk yang tidak perlu
SELECT * FROM users;

-- ✅ BAIK: Ambil hanya kolom yang dibutuhkan
SELECT id, username, email, full_name FROM users;
-- Alasan: Hemat bandwidth, lebih cepat, tidak expose data sensitif
```

### 10.5 Gunakan LIMIT untuk Query yang Berpotensi Besar

```sql
-- ❌ BERBAHAYA: Bisa mengembalikan jutaan baris
SELECT * FROM orders WHERE status = 'pending';

-- ✅ AMAN: Selalu paginate
SELECT * FROM orders
WHERE status = 'pending'
ORDER BY created_at DESC
LIMIT 50 OFFSET 0;
```

### 10.6 Simpan Timestamp di Setiap Tabel

```sql
-- ✅ PRAKTIK TERBAIK: Setiap tabel punya audit trail
CREATE TABLE any_table (
    id          SERIAL PRIMARY KEY,
    -- ... kolom lain ...
    created_at  TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at  TIMESTAMP DEFAULT NOW() NOT NULL
    -- Untuk soft delete, tambahkan:
    -- deleted_at TIMESTAMP  -- NULL = aktif, ada nilai = terhapus
);
```

### 10.7 Gunakan Environment Variables untuk Kredensial

```javascript
// ❌ JANGAN: Hardcode kredensial
const pool = new Pool({
    password: 'mySecretPassword123',
    database: 'production_db'
});

// ✅ BENAR: Gunakan environment variables
const pool = new Pool({
    password: process.env.DB_PASSWORD,
    database: process.env.DB_NAME
});
```

---

## SECTION 11 — COMMON MISTAKES & HOW TO AVOID THEM

### Kesalahan 11.1: N+1 Query Problem

```javascript
// ❌ BURUK: N+1 Query - 1 query untuk orders + N query untuk setiap user
const orders = await pool.query('SELECT * FROM orders');

for (const order of orders.rows) {
    // Ini menjalankan 1 query PER ORDER!
    const user = await pool.query(
        'SELECT * FROM users WHERE id = $1',
        [order.user_id]
    );
    order.user = user.rows[0];
}
// Jika ada 100 orders → 101 query ke database!

// ✅ BAIK: Satu query dengan JOIN
const result = await pool.query(`
    SELECT
        o.*,
        u.username,
        u.email,
        u.full_name
    FROM orders o
    JOIN users u ON o.user_id = u.id
`);
// Hanya 1 query untuk semua data!
```

### Kesalahan 11.2: Tidak Menangani Error Database

```javascript
// ❌ BURUK: Error tidak ditangani
router.get('/products', async (req, res) => {
    const result = await pool.query('SELECT * FROM products');
    res.json(result.rows);
    // Jika query gagal, server crash!
});

// ✅ BAIK: Error handling yang proper
router.get('/products', async (req, res) => {
    try {
        const result = await pool.query('SELECT * FROM products');
        res.json({ success: true, data: result.rows });
    } catch (error) {
        console.error('Database error:', error.message);

        // Jangan expose detail error ke client di produksi
        res.status(500).json({
            success: false,
            message: 'Terjadi kesalahan server'
        });
    }
});
```

### Kesalahan 11.3: Lupa Melepas Koneksi ke Pool

```javascript
// ❌ BURUK: Koneksi tidak dilepas jika terjadi error
async function badExample() {
    const client = await pool.connect();
    const result = await client.query('SELECT * FROM users'); // Jika ini error...
    client.release(); // ...baris ini tidak pernah dieksekusi!
    return result.rows;
}

// ✅ BAIK: Gunakan try/finally untuk memastikan release
async function goodExample() {
    const client = await pool.connect();
    try {
        const result = await client.query('SELECT * FROM users');
        return result.rows;
    } finally {
        client.release(); // SELALU dieksekusi, bahkan jika ada error
    }
}
```

### Kesalahan 11.4: Menyimpan Password Plain Text

```javascript
// ❌ SANGAT BERBAHAYA
await pool.query(
    'INSERT INTO users (email, password) VALUES ($1, $2)',
    [email, password] // Password tersimpan apa adanya!
);

// ✅ BENAR: Hash password sebelum disimpan
const bcrypt = require('bcrypt');
const SALT_ROUNDS = 12;

const passwordHash = await bcrypt.hash(password, SALT_ROUNDS);
await pool.query(
    'INSERT INTO users (email, password_hash) VALUES ($1, $2)',
    [email, passwordHash]
);
```

### Kesalahan 11.5: Skema Tanpa Constraint

```sql
-- ❌ BURUK: Tidak ada validasi di level database
CREATE TABLE products (
    id      SERIAL PRIMARY KEY,
    name    VARCHAR(255),  -- Bisa NULL!
    price   DECIMAL,       -- Bisa negatif!
    stock   INTEGER        -- Bisa negatif!
);

-- ✅ BAIK: Constraint melindungi integritas data
CREATE TABLE products (
    id      SERIAL PRIMARY KEY,
    name    VARCHAR(255) NOT NULL,
    price   DECIMAL(12,2) NOT NULL CHECK (price >= 0),
    stock   INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0)
);
```

---

## SECTION 12 — HANDS-ON EXERCISE

### Exercise 12.1: Setup Environment

```bash
# Instalasi PostgreSQL (Ubuntu/Debian)
sudo apt update
sudo apt install postgresql postgresql-contrib

# Mulai service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Masuk ke PostgreSQL CLI
sudo -u postgres psql

# Buat database dan user untuk latihan
CREATE DATABASE learning_db;
CREATE USER learner WITH PASSWORD 'learner123';
GRANT ALL PRIVILEGES ON DATABASE learning_db TO learner;
\q

# Koneksi ke database
psql -U learner -d learning_db -h localhost
```

### Exercise 12.2: Latihan SQL Dasar

```sql
-- ============================================================
-- LATIHAN 1: Buat tabel library sederhana
-- ============================================================

-- Buat tabel authors
CREATE TABLE authors (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    nationality VARCHAR(50),
    birth_year  INTEGER CHECK (birth_year > 1800 AND birth_year <= EXTRACT(YEAR FROM NOW()))
);

-- Buat tabel books
CREATE TABLE books (
    id          SERIAL PRIMARY KEY,
    author_id   INTEGER REFERENCES authors(id) ON DELETE CASCADE,
    title       VARCHAR(255) NOT NULL,
    isbn        VARCHAR(20) UNIQUE,
    genre       VARCHAR(50),
    price       DECIMAL(10,2) CHECK (price > 0),
    pages       INTEGER CHECK (pages > 0),
    published_year INTEGER
);

-- ============================================================
-- LATIHAN 2: Insert data
-- ============================================================
INSERT INTO authors (name, nationality, birth_year) VALUES
    ('Robert C. Martin', 'American', 1952),
    ('Martin Fowler', 'British', 1963),
    ('Donald Knuth', 'American', 1938);

INSERT INTO books (author_id, title, isbn, genre, price, pages, published_year) VALUES
    (1, 'Clean Code', '978-0132350884', 'Programming', 89000, 431, 2008),
    (1, 'Clean Architecture', '978-0134494166', 'Programming', 95000, 432, 2017),
    (2, 'Refactoring', '978-0201485677', 'Programming', 110000, 448, 1999),
    (2, 'Patterns of Enterprise Application Architecture', '978-0321127426', 'Architecture', 125000, 533, 2002),
    (3, 'The Art of Computer Programming Vol. 1', '978-0201896831', 'Computer Science', 200000, 672, 1968);

-- ============================================================
-- LATIHAN 3: Query dengan berbagai kondisi
-- ============================================================

-- 3a. Tampilkan semua buku dengan harga di atas 100.000
SELECT title, price FROM books WHERE price > 100000 ORDER BY price DESC;

-- 3b. Hitung jumlah buku per penulis
SELECT
    a.name AS author_name,
    COUNT(b.id) AS book_count,
    AVG(b.price) AS avg_price
FROM authors a
LEFT JOIN books b ON a.id = b.author_id
GROUP BY a.id, a.name
ORDER BY book_count DESC;

-- 3c. Tampilkan buku beserta nama penulisnya
SELECT
    b.title,
    a.name AS author,
    b.genre,
    b.price,
    b.published_year
FROM books b
JOIN authors a ON b.author_id = a.id
ORDER BY b.published_year;

-- 3d. Cari buku dengan kata kunci di judul
SELECT title, price FROM books
WHERE title ILIKE '%clean%'
ORDER BY title;

-- 3e. Statistik harga per genre
SELECT
    genre,
    COUNT(*) AS total_books,
    MIN(price) AS min_price,
    MAX(price) AS max_price,
    ROUND(AVG(price), 0) AS avg_price
FROM books
GROUP BY genre
HAVING COUNT(*) > 1
ORDER BY avg_price DESC;
```

### Exercise 12.3: Integrasi Node.js

```javascript
// ============================================================
// FILE: exercise/library-api.js
// Buat REST API sederhana untuk library
// ============================================================

const express = require('express');
const { Pool } = require('pg');

const app = express();
app.use(express.json());

const pool = new Pool({
    connectionString: process.env.DATABASE_URL ||
        'postgresql://learner:learner123@localhost:5432/learning_db'
});

// TODO: Implementasikan endpoint berikut sebagai latihan:

// GET /books - Ambil semua buku dengan nama penulis
app.get('/books', async (req, res) => {
    try {
        const { genre, search } = req.query;

        let query = `
            SELECT b.id, b.title, a.name AS author, b.genre, b.price
            FROM books b
            JOIN authors a ON b.author_id = a.id
            WHERE 1=1
        `;
        const params = [];

        if (genre) {
            params.push(genre);
            query += ` AND b.genre = $${params.length}`;
        }

        if (search) {
            params.push(`%${search}%`);
            query += ` AND b.title ILIKE $${params.length}`;
        }

        query += ' ORDER BY b.title';

        const result = await pool.query(query, params);
        res.json({ success: true, data: result.rows });

    } catch (error) {
        console.error(error);
        res.status(500).json({ success: false, message: 'Server error' });
    }
});

// GET /books/:id - Detail satu buku
app.get('/books/:id', async (req, res) => {
    try {
        const result = await pool.query(
            `SELECT b.*, a.name AS author_name, a.nationality
             FROM books b
             JOIN authors a ON b.author_id = a.id
             WHERE b.id = $1`,
            [req.params.id]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({ success: false, message: 'Buku tidak ditemukan' });
        }

        res.json({ success: true, data: result.rows[0] });
    } catch (error) {
        res.status(500).json({ success: false, message: 'Server error' });
    }
});

// POST /books - Tambah buku baru
app.post('/books', async (req, res) => {
    try {
        const { authorId, title, isbn, genre, price, pages, publishedYear } = req.body;

        // Validasi input dasar
        if (!authorId || !title || !price) {
            return res.status(400).json({
                success: false,
                message: 'authorId, title, dan price wajib diisi'
            });
        }

        const result = await pool.query(
            `INSERT INTO books (author_id, title, isbn, genre, price, pages, published_year)
             VALUES ($1, $2, $3, $4, $5, $6, $7)
             RETURNING *`,
            [authorId, title, isbn, genre, price, pages, publishedYear]
        );

        res.status(201).json({ success: true, data: result.rows[0] });

    } catch (error) {
        if (error.code === '23505') { // Unique violation
            return res.status(409).json({ success: false, message: 'ISBN sudah terdaftar' });
        }
        res.status(500).json({ success: false, message: 'Server error' });
    }
});

app.listen(3000, () => console.log('Library API running on port 3000'));
```

---

## SECTION 13 — NORMALISASI DATABASE

### Mengapa Normalisasi Penting?

Normalisasi adalah proses mengorganisir tabel database untuk mengurangi redundansi dan meningkatkan integritas data.

### Contoh Masalah Tanpa Normalisasi

```
TABEL TIDAK TERNORMALISASI: orders_bad
┌────┬──────────┬───────────────────┬──────────────┬──────────────────────────────────┐
│ id │ customer │ customer_email    │ product_name │ product_category                 │
├────┼──────────┼───────────────────┼──────────────┼──────────────────────────────────┤
│  1 │ Alice    │ alice@example.com │ Laptop ASUS  │ Elektronik                       │
│  2 │ Alice    │ alice@example.com │ Keyboard     │ Elektronik                       │
│  3 │ Bob      │ bob@example.com   │ Laptop ASUS  │ Elektronik                       │
└────┴──────────┴───────────────────┴──────────────┴──────────────────────────────────┘

MASALAH:
1. Update Anomaly: Jika email Alice berubah, harus update di banyak baris
2. Insert Anomaly: Tidak bisa simpan produk tanpa ada order
3. Delete Anomaly: Hapus order terakhir Bob → data Bob hilang
```

### Proses Normalisasi

```
SEBELUM (Unnormalized):
orders_bad(id, customer, customer_email, product_name, product_category)

SETELAH 1NF (First Normal Form):
→ Setiap kolom berisi nilai atomik (tidak ada repeating groups)
→ Sudah terpenuhi di contoh kita

SETELAH 2NF (Second Normal Form):
→ Tidak ada partial dependency (setiap non-key kolom bergantung pada seluruh PK)
→ Pisahkan: customers(id, name, email) dan products(id, name, category)

SETELAH 3NF (Third Normal Form):
→ Tidak ada transitive dependency (non-key kolom tidak bergantung pada non-key kolom lain)
→ Pisahkan: categories(id, name) dari products

HASIL AKHIR (3NF):
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  customers   │    │   products   │    │  categories  │
│──────────────│    │──────────────│    │──────────────│
│ id (PK)      │    │ id (PK)      │    │ id (PK)      │
│ name         │    │ category_id  │───▶│ name         │
│ email        │    │ name         │    └──────────────┘
└──────┬───────┘    │ price        │
       │            └──────┬───────┘
       │                   │
       ▼                   ▼
┌──────────────────────────────────┐
│            orders                │
│──────────────────────────────────│
│ id (PK)                          │
│ customer_id (FK) ────────────────┘
│ created_at                       │
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│          order_items             │
│──────────────────────────────────│
│ id (PK)                          │
│ order_id (FK)                    │
│ product_id (FK) ─────────────────┘
│ quantity                         │
│ unit_price                       │
└──────────────────────────────────┘
```

---

## SECTION 14 — SQL JOINS DEEP DIVE

### Visualisasi Semua Jenis JOIN

```
Tabel A (users):          Tabel B (orders):
┌────┬──────────┐         ┌────┬─────────┬──────────┐
│ id │ name     │         │ id │ user_id │ total    │
├────┼──────────┤         ├────┼─────────┼──────────┤
│  1 │ Alice    │         │  1 │    1    │ 150.000  │
│  2 │ Bob      │         │  2 │    1    │ 200.000  │
│  3 │ Carol    │         │  3 │    2    │  75.000  │
│  4 │ Dave     │         │  4 │    5    │  50.000  │ ← user_id 5 tidak ada!
└────┴──────────┘         └────┴─────────┴──────────┘

INNER JOIN (hanya baris yang cocok di kedua tabel):
SELECT u.name, o.total FROM users u INNER JOIN orders o ON u.id = o.user_id;
→ Alice | 150.000
→ Alice | 200.000
→ Bob   |  75.000
(Carol dan Dave tidak muncul, order dengan user_id=5 tidak muncul)

LEFT JOIN (semua dari kiri, cocok dari kanan):
SELECT u.name, o.total FROM users u LEFT JOIN orders o ON u.id = o.user_id;
→ Alice | 150.000
→ Alice | 200.000
→ Bob   |  75.000
→ Carol | NULL      ← Carol muncul meski tidak punya order
→ Dave  | NULL      ← Dave muncul meski tidak punya order

RIGHT JOIN (semua dari kanan, cocok dari kiri):
SELECT u.name, o.total FROM users u RIGHT JOIN orders o ON u.id = o.user_id;
→ Alice | 150.000
→ Alice | 200.000
→ Bob   |  75.000
→ NULL  |  50.000   ← Order user_id=5 muncul meski user tidak ada

FULL OUTER JOIN (semua dari kedua tabel):
→ Alice | 150.000
→ Alice | 200.000
→ Bob   |  75.000
→ Carol | NULL
→ Dave  | NULL
→ NULL  |  50.000
```

### Contoh Penggunaan JOIN dalam Konteks Nyata

```sql
-- Temukan user yang BELUM pernah melakukan order (LEFT JOIN + IS NULL)
SELECT u.id, u.username, u.email
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.id IS NULL;

-- Hitung total spending per user (termasuk yang belum pernah order)
SELECT
    u.username,
    COUNT(o.id) AS total_orders,
    COALESCE(SUM(o.total_amount), 0) AS total_spent
FROM users u
LEFT JOIN orders o ON u.id = o.user_id AND o.status = 'delivered'
GROUP BY u.id, u.username
ORDER BY total_spent DESC;
```

---

## SECTION 15 — TRANSACTIONS DAN ACID PROPERTIES

### ACID: Fondasi Keandalan Database

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ACID PROPERTIES                               │
├──────────────┬──────────────────────────────────────────────────────┤
│ A - Atomicity│ Semua operasi dalam transaksi berhasil SEMUA,        │
│              │ atau TIDAK SAMA SEKALI.                               │
│              │ Contoh: Transfer uang - debit DAN kredit harus       │
│              │ berhasil, atau keduanya dibatalkan.                   │
├──────────────┼──────────────────────────────────────────────────────┤
│ C - Consistency│ Transaksi membawa database dari satu state valid   │
│              │ ke state valid lainnya. Constraint tidak boleh        │
│              │ dilanggar.                                            │
│              │ Contoh: Saldo tidak boleh negatif setelah transfer.  │
├──────────────┼──────────────────────────────────────────────────────┤
│ I - Isolation│ Transaksi yang berjalan bersamaan tidak saling        │
│              │ mempengaruhi. Seolah berjalan secara serial.          │
│              │ Contoh: Dua user beli produk terakhir bersamaan -    │
│              │ hanya satu yang berhasil.                             │
├──────────────┼──────────────────────────────────────────────────────┤
│ D - Durability│ Setelah COMMIT, data tersimpan permanen meski       │
│              │ terjadi crash/power failure.                          │
│              │ Implementasi: Write-Ahead Log (WAL)                  │
└──────────────┴──────────────────────────────────────────────────────┘
```

### Contoh Transaksi: Transfer Saldo

```sql
-- Skenario: Transfer Rp 500.000 dari Alice (id=1) ke Bob (id=2)

BEGIN;

-- Cek saldo Alice cukup
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;
-- Hasil: 1.000.000 ✅ Cukup

-- Kurangi saldo Alice
UPDATE accounts SET balance = balance - 500000 WHERE id = 1;

-- Tambah saldo Bob
UPDATE accounts SET balance = balance + 500000 WHERE id = 2;

-- Catat transaksi
INSERT INTO transactions (from_account, to_account, amount, type)
VALUES (1, 2, 500000, 'transfer');

-- Jika semua berhasil, simpan permanen
COMMIT;

-- Jika ada error di tengah jalan:
-- ROLLBACK; ← Semua perubahan dibatalkan, saldo kembali ke semula
```

---

## SECTION 16 — DATABASE MIGRATIONS

### Mengapa Migrations Diperlukan?

Dalam pengembangan software, skema database berubah seiring waktu. **Migrations** adalah cara terstruktur untuk mengelola perubahan skema database secara terkontrol dan dapat direproduksi.

```
TANPA MIGRATIONS:
Developer A mengubah skema di laptop → "Eh, kenapa di server production error?"
Developer B tidak tahu ada perubahan skema → Konflik!
Tidak ada history perubahan → Sulit debug

DENGAN MIGRATIONS:
Setiap perubahan skema = satu file migration
File di-commit ke git → semua developer sinkron
Bisa rollback jika ada masalah
Deployment otomatis menjalankan migration yang belum dijalankan
```

### Struktur Migration File

```javascript
// ============================================================
// FILE: migrations/001_create_users_table.js
// ============================================================
exports.up = async (pool) => {
    await pool.query(`
        CREATE TABLE users (
            id          SERIAL PRIMARY KEY,
            username    VARCHAR(50) UNIQUE NOT NULL,
            email       VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at  TIMESTAMP DEFAULT NOW()
        )
    `);
    console.log('✅ Migration 001: users table created');
};

exports.down = async (pool) => {
    await pool.query('DROP TABLE IF EXISTS users CASCADE');
    console.log('↩️  Migration 001: users table dropped');
};

// ============================================================
// FILE: migrations/002_add_full_name_to_users.js
// ============================================================
exports.up = async (pool) => {
    await pool.query(`
        ALTER TABLE users
        ADD COLUMN full_name VARCHAR(100),
        ADD COLUMN is_active BOOLEAN DEFAULT TRUE
    `);
    console.log('✅ Migration 002: full_name and is_active added to users');
};

exports.down = async (pool) => {
    await pool.query(`
        ALTER TABLE users
        DROP COLUMN IF EXISTS full_name,
        DROP COLUMN IF EXISTS is_active
    `);
    console.log('↩️  Migration 002: columns removed from users');
};
```

```javascript
// ============================================================
// FILE: migrations/runner.js
// Simple migration runner
// ============================================================
const pool = require('../src/database/connection');
const fs = require('fs');
const path = require('path');

async function runMigrations() {
    // Buat tabel tracking migrations jika belum ada
    await pool.query(`
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id          SERIAL PRIMARY KEY,
            filename    VARCHAR(255) UNIQUE NOT NULL,
            executed_at TIMESTAMP DEFAULT NOW()
        )
    `);

    // Ambil migrations yang sudah dijalankan
    const executed = await pool.query(
        'SELECT filename FROM schema_migrations ORDER BY filename'
    );
    const executedFiles = new Set(executed.rows.map(r => r.filename));

    // Ambil semua file migration
    const migrationDir = path.join(__dirname, 'migrations');
    const files = fs.readdirSync(migrationDir)
        .filter(f => f.endsWith('.js'))
        .sort();

    // Jalankan migration yang belum dieksekusi
    for (const file of files) {
        if (!executedFiles.has(file)) {
            console.log(`Running migration: ${file}`);
            const migration = require(path.join(migrationDir, file));

            const client = await pool.connect();
            try {
                await client.query('BEGIN');
                await migration.up(client);
                await client.query(
                    'INSERT INTO schema_migrations (filename) VALUES ($1)',
                    [file]
                );
                await client.query('COMMIT');
                console.log(`✅ ${file} completed`);
            } catch (error) {
                await client.query('ROLLBACK');
                console.error(`❌ ${file} failed:`, error.message);
                throw error;
            } finally {
                client.release();
            }
        }
    }

    console.log('All migrations completed!');
}

runMigrations().catch(console.error).finally(() => pool.end());
```

---

## SECTION 17 — PERFORMANCE OPTIMIZATION BASICS

### 17.1 Menggunakan EXPLAIN untuk Analisis Query

```sql
-- EXPLAIN menunjukkan rencana eksekusi query
EXPLAIN SELECT * FROM products WHERE category_id = 1;

-- Output tanpa index:
-- Seq Scan on products  (cost=0.00..25.00 rows=5 width=100)
--   Filter: (category_id = 1)
-- → "Seq Scan" = Full table scan, baca semua baris!

-- Buat index
CREATE INDEX idx_products_category_id ON products(category_id);

-- Output dengan index:
-- Index Scan using idx_products_category_id on products
--   (cost=0.28..8.30 rows=5 width=100)
--   Index Cond: (category_id = 1)
-- → "Index Scan" = Menggunakan index, jauh lebih efisien!

-- EXPLAIN ANALYZE: Jalankan query dan tampilkan waktu aktual
EXPLAIN ANALYZE
SELECT p.name, c.name AS category
FROM products p
JOIN categories c ON p.category_id = c.id
WHERE p.price > 100000;
```

### 17.2 Strategi Index yang Efektif

```sql
-- Index sederhana (B-Tree, default)
CREATE INDEX idx_users_email ON users(email);

-- Index komposit (untuk query dengan multiple WHERE conditions)
CREATE INDEX idx_orders_user_status ON orders(user_id, status);
-- Berguna untuk: WHERE user_id = 1 AND status = 'pending'

-- Index parsial (hanya index subset data)
CREATE INDEX idx_active_products ON products(name)
WHERE is_active = TRUE;
-- Lebih kecil dan lebih cepat dari full index

-- Index untuk pencarian teks (LIKE '%keyword%')
CREATE INDEX idx_products_name_gin ON products
USING gin(to_tsvector('indonesian', name));
-- Untuk full-text search yang efisien
```

### 17.3 Query Optimization Checklist

```
CHECKLIST OPTIMASI QUERY:

□ Apakah kolom di WHERE sudah diindex?
□ Apakah menggunakan SELECT * padahal tidak perlu semua kolom?
□ Apakah ada N+1 query problem? (gunakan JOIN)
□ Apakah query di dalam loop? (batch jika memungkinkan)
□ Apakah LIMIT digunakan untuk query yang bisa mengembalikan banyak baris?
□ Apakah JOIN condition menggunakan kolom yang diindex?
□ Apakah ada subquery yang bisa diganti dengan JOIN?
□ Sudahkah dijalankan EXPLAIN ANALYZE untuk query lambat?
```

---

## SECTION 18 — ENVIRONMENT SETUP & TOOLING

### 18.1 Setup Lengkap untuk Development

```bash
# ============================================================
# SETUP POSTGRESQL DI LOKAL
# ============================================================

# Ubuntu/Debian
sudo apt update && sudo apt install postgresql postgresql-contrib

# macOS (dengan Homebrew)
brew install postgresql@15
brew services start postgresql@15

# Windows: Download installer dari postgresql.org

# ============================================================
# SETUP PROJECT NODE.JS
# ============================================================

mkdir ecommerce-backend && cd ecommerce-backend
npm init -y

# Install dependencies
npm install express pg dotenv
npm install --save-dev nodemon

# Struktur folder
mkdir -p src/{database,models,routes,services,middleware}
mkdir -p migrations tests

# ============================================================
# FILE: .env (JANGAN commit ke git!)
# ============================================================
cat > .env << 'EOF'
NODE_ENV=development
PORT=3000
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ecommerce_db
DB_USER=postgres
DB_PASSWORD=your_password_here
EOF

# ============================================================
# FILE: .gitignore
# ============================================================
cat > .gitignore << 'EOF'
node_modules/
.env
*.log
EOF

# ============================================================
# FILE: package.json scripts
# ============================================================
# Tambahkan ke package.json:
# "scripts": {
#   "start": "node src/index.js",
#   "dev": "nodemon src/index.js",
#   "migrate": "node migrations/runner.js",
#   "seed": "node migrations/seed.js"
# }
```

### 18.2 Tools yang Direkomendasikan

```
DATABASE GUI CLIENTS:
┌─────────────────────────────────────────────────────────────┐
│ Tool              │ Platform  │ Kelebihan                   │
├───────────────────┼───────────┼─────────────────────────────┤
│ pgAdmin 4         │ Web/App   │ Official, fitur lengkap     │
│ DBeaver           │ Desktop   │ Multi-database, gratis      │
│ TablePlus         │ Desktop   │ UI modern, cepat            │
│ DataGrip (JetBrains)│ Desktop │ Paling powerful, berbayar  │
│ psql (CLI)        │ Terminal  │ Built-in, selalu tersedia   │
└─────────────────────────────────────────────────────────────┘

PSQL COMMANDS PENTING:
\l          → List semua database
\c dbname   → Connect ke database
\dt         → List semua tabel
\d tablename → Describe struktur tabel
\di         → List semua index
\timing     → Toggle tampilan waktu eksekusi
\x          → Toggle expanded display (untuk baris panjang)
\q          → Keluar dari psql
```

### 18.3 Docker Setup (Alternatif)

```yaml
# FILE: docker-compose.yml
# Jalankan: docker-compose up -d

version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: ecommerce_postgres
    environment:
      POSTGRES_DB: ecommerce_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres123
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
      - ./migrations/seed.sql:/docker-entrypoint-initdb.d/02-seed.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: ecommerce_pgadmin
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@example.com
      PGADMIN_DEFAULT_PASSWORD: admin123
    ports:
      - "8080:80"
    depends_on:
      - postgres

volumes:
  postgres_data:
```

---

## SECTION 19 — SUMMARY & KEY TAKEAWAYS

### Ringkasan Konsep Utama

```
╔══════════════════════════════════════════════════════════════════════╗
║                    KEY TAKEAWAYS - BAB 06 MODULE 01                 ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  FUNDAMENTAL DATABASE                                                ║
║  ✅ Database adalah lapisan persistensi dalam arsitektur backend     ║
║  ✅ RDBMS mengorganisir data dalam tabel dengan relasi eksplisit    ║
║  ✅ Primary Key = identifier unik; Foreign Key = referensi antar    ║
║     tabel                                                            ║
║  ✅ Constraint (NOT NULL, UNIQUE, CHECK) melindungi integritas data ║
║                                                                      ║
║  SQL ESSENTIALS                                                      ║
║  ✅ DDL: CREATE, ALTER, DROP (struktur)                             ║
║  ✅ DML: SELECT, INSERT, UPDATE, DELETE (data)                      ║
║  ✅ WHERE, ORDER BY, LIMIT, GROUP BY, HAVING untuk filter/sort      ║
║  ✅ JOIN menggabungkan data dari beberapa tabel                     ║
║  ✅ Transaksi (BEGIN/COMMIT/ROLLBACK) untuk operasi atomik          ║
║                                                                      ║
║  KEAMANAN                                                            ║
║  ✅ SELALU gunakan parameterized query, JANGAN string concatenation ║
║  ✅ JANGAN simpan password plain text, gunakan bcrypt               ║
║  ✅ JANGAN expose detail error database ke client                   ║
║  ✅ Gunakan environment variables untuk kredensial                  ║
║                                                                      ║
║  PERFORMA                                                            ║
║  ✅ Index mempercepat SELECT tapi memperlambat INSERT/UPDATE        ║
║  ✅ Hindari N+1 query, gunakan JOIN                                 ║
║  ✅ Selalu LIMIT query yang berpotensi mengembalikan banyak baris   ║
║  ✅ Gunakan EXPLAIN ANALYZE untuk debug query lambat                ║
║                                                                      ║
║  ARSITEKTUR                                                          ║
║  ✅ Connection Pool menghindari overhead buka koneksi baru          ║
║  ✅ Migrations mengelola perubahan skema secara terkontrol          ║
║  ✅ Normalisasi mengurangi redundansi dan meningkatkan integritas   ║
║  ✅ Pilih SQL untuk data relasional, NoSQL untuk data fleksibel     ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
```

### Mental Model: Database dalam Konteks Backend

```
REQUEST MASUK
     │
     ▼
┌─────────────┐
│ Route Layer │ → Validasi input, routing ke handler
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Service    │ → Business logic, orchestrasi
│  Layer      │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Model      │ → Query database, mapping data
│  Layer      │
└──────┬──────┘
       │ Parameterized SQL Query
       ▼
┌─────────────┐
│  Database   │ → Simpan/ambil data persisten
│ (PostgreSQL)│
└─────────────┘
```

---

## SECTION 20 — FURTHER LEARNING & REFERENCES

### 20.1 Topik Lanjutan untuk Dipelajari Selanjutnya

```
LEVEL BERIKUTNYA (Bab 07+):

┌─────────────────────────────────────────────────────────────────┐
│ TOPIK                    │ RELEVANSI                            │
├──────────────────────────┼──────────────────────────────────────┤
│ ORM (Prisma, Sequelize,  │ Abstraksi SQL dengan type-safety    │
│ TypeORM)                 │ dan developer experience lebih baik  │
├──────────────────────────┼──────────────────────────────────────┤
│ Database Indexing        │ Optimasi performa query kompleks     │
│ Advanced                 │                                      │
├──────────────────────────┼──────────────────────────────────────┤
│ Query Optimization &     │ EXPLAIN ANALYZE, query planning,    │
│ EXPLAIN ANALYZE          │ statistik tabel                      │
├──────────────────────────┼──────────────────────────────────────┤
│ Database Transactions    │ Isolation levels, deadlock,          │
│ Advanced                 │ optimistic vs pessimistic locking    │
├──────────────────────────┼──────────────────────────────────────┤
│ NoSQL (MongoDB, Redis)   │ Document store, key-value store,    │
│                          │ caching strategies                   │
├──────────────────────────┼──────────────────────────────────────┤
│ Database Replication     │ Read replicas, high availability,   │
│ & Scaling                │ sharding                             │
├──────────────────────────┼──────────────────────────────────────┤
│ Full-Text Search         │ PostgreSQL FTS, Elasticsearch        │
│                          │ integration                          │
└──────────────────────────┴──────────────────────────────────────┘
```

### 20.2 Referensi Resmi dan Terpercaya

```
DOKUMENTASI RESMI:
→ PostgreSQL Documentation: https://www.postgresql.org/docs/
→ node-postgres (pg): https://node-postgres.com/
→ SQL Standard Reference: ISO/IEC 9075

BUKU YANG DIREKOMENDASIKAN:
→ "Learning SQL" - Alan Beaulieu (O'Reilly) - Untuk pemula
→ "PostgreSQL: Up and Running" - Regina Obe (O'Reilly)
→ "Database Design for Mere Mortals" - Michael Hernandez
→ "Designing Data-Intensive Applications" - Martin Kleppmann (Level lanjut)

PLATFORM LATIHAN INTERAKTIF:
→ SQLZoo: https://sqlzoo.net/ (latihan SQL interaktif)
→ Mode SQL Tutorial: https://mode.com/sql-tutorial/
→ PostgreSQL Exercises: https://pgexercises.com/

TOOLS ONLINE:
→ DB Fiddle: https://www.db-fiddle.com/ (test SQL online)
→ dbdiagram.io: https://dbdiagram.io/ (desain skema visual)
→ explain.depesz.com: Analisis EXPLAIN output
```

### 20.3 Checklist Kesiapan Modul

```
SELF-ASSESSMENT: Tandai jika sudah dikuasai

FUNDAMENTAL:
□ Saya bisa menjelaskan perbedaan tabel, baris, dan kolom
□ Saya memahami fungsi Primary Key dan Foreign Key
□ Saya bisa membedakan kapan menggunakan SQL vs NoSQL

SQL DASAR:
□ Saya bisa menulis CREATE TABLE dengan constraint yang tepat
□ Saya bisa melakukan INSERT, SELECT, UPDATE, DELETE
□ Saya bisa menggunakan WHERE, ORDER BY, LIMIT, GROUP BY
□ Saya bisa menulis INNER JOIN dan LEFT JOIN
□ Saya memahami kapan menggunakan transaksi

INTEGRASI BACKEND:
□ Saya bisa setup connection pool dengan node-postgres
□ Saya SELALU menggunakan parameterized query
□ Saya bisa menangani error database dengan benar
□ Saya bisa membuat migration file sederhana

KEAMANAN:
□ Saya memahami SQL Injection dan cara mencegahnya
□ Saya tidak pernah menyimpan password plain text
□ Saya menggunakan environment variables untuk kredensial

PERFORMA:
□ Saya memahami kapan dan mengapa membuat index
□ Saya bisa mengidentifikasi N+1 query problem
□ Saya selalu menggunakan LIMIT untuk query besar

JIKA SEMUA TERCENTANG → Siap lanjut ke Bab 07!
JIKA ADA YANG BELUM → Review section yang relevan
```

### 20.4 Mini Project: Capstone Modul Ini

```
PROYEK AKHIR MODUL: Blog API dengan Database

Bangun REST API untuk platform blog sederhana dengan fitur:

REQUIREMENTS:
1. Skema database dengan tabel: users, posts, categories, comments, tags
2. Relasi: posts belongs to users, posts has many comments, posts has many tags
3. CRUD endpoints untuk posts
4. Filter posts berdasarkan category, tag, dan author
5. Pagination untuk list posts
6. Statistik: post terpopuler berdasarkan jumlah komentar

BONUS CHALLENGE:
- Implementasi soft delete (deleted_at timestamp)
- Full-text search untuk konten post
- Rate limiting per user menggunakan database counter

DELIVERABLES:
□ schema.sql dengan semua tabel dan constraint
□ seed.sql dengan data sample
□ API endpoints yang berfungsi
□ Semua query menggunakan parameterized query
□ Error handling yang proper
□ README dengan instruksi setup
```

---

*Modul ini adalah bagian dari kurikulum **Backend Beginner** — Kategori **01-Core-Foundations**.*
*Versi: 1.0.0 | Estimasi waktu penyelesaian: 12-16 jam (termasuk latihan)*
*Prasyarat: Bab 01-05 (JavaScript Fundamentals, Node.js, Express.js)*
*Modul Berikutnya: Bab 06 Module 02 — ORM dengan Prisma*