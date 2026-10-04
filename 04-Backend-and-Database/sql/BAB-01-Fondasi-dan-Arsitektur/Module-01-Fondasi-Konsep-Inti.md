# 📘 Bab 01 – Modul 01  
## **SQL (Structured Query Language)**  
*Standar GEMINI.md – 20 Seksi lengkap*  

> **Catatan:** Setiap seksi mengikuti pola **Learning Objective → Concept → Why → What → How → Diagram (ASCII) → Simple Example → Practical Example → Trade‑offs → Best Practices**.  
> Semua contoh menggunakan **SQL‑92** (ANSI) yang kompatibel dengan mayoritas RDBMS (MySQL, PostgreSQL, SQL‑Server, Oracle, SQLite).

---

## Seksi 1 – Pengenalan SQL  
### Learning Objective  
- Memahami apa itu SQL, sejarah singkat, dan peranannya dalam sistem basis data relasional.  

### Concept  
SQL adalah bahasa deklaratif standar untuk **mengelola** dan **mengambil** data pada Relational Database Management System (RDBMS).  

### Why  
Tanpa SQL, aplikasi tidak dapat berinteraksi secara konsisten dengan data yang terstruktur; SQL menyediakan satu antarmuka universal yang memisahkan logika bisnis dari penyimpanan fisik.  

### What  
- **DDL** – Data Definition Language (CREATE, ALTER, DROP)  
- **DML** – Data Manipulation Language (SELECT, INSERT, UPDATE, DELETE)  
- **DCL** – Data Control Language (GRANT, REVOKE)  
- **TCL** – Transaction Control Language (COMMIT, ROLLBACK, SAVEPOINT)  

### How  
1. **Koneksi** ke RDBMS menggunakan driver (ODBC/JDBC).  
2. **Kirim** pernyataan SQL dalam bentuk teks.  
3. **RDBMS** mem-parsing, meng‑optimasi, dan mengeksekusi.  

#### Diagram ASCII  
```
+-----------+      SQL Query      +-----------+
|  Aplikasi | ------------------> |   RDBMS   |
+-----------+   (text string)    +-----------+
        ^                               |
        |   Result Set (rows)           |
        +-------------------------------+
```

#### Simple Example  
```sql
SELECT 'Hello, SQL!' AS greeting;
```

#### Practical Example  
```sql
-- Membuat koneksi (MySQL CLI)
mysql -u root -p
-- Menjalankan query
SELECT version() AS db_version;
```

#### Trade‑offs  
- **Deklaratif vs. Imperatif** – SQL menyatakan *apa* yang diinginkan, bukan *bagaimana*; ini memudahkan pemeliharaan tetapi mengurangi kontrol mikro pada algoritma eksekusi.  

#### Best Practices  
- Selalu gunakan **uppercase** untuk kata kunci SQL.  
- Simpan query dalam **file .sql** terpisah untuk versioning.  

---

## Seksi 2 – Model Relasional & Skema  
### Learning Objective  
- Menjelaskan konsep tabel, baris, kolom, primary key, foreign key, dan normalisasi.  

### Concept  
Model relasional menyimpan data dalam **tabel** (relation) yang terhubung melalui **kunci**.  

### Why  
Normalisasi mengurangi redundansi, meningkatkan integritas, dan mempermudah pemeliharaan data.  

### What  
- **Entity** → Tabel  
- **Attribute** → Kolom  
- **Tuple** → Baris  
- **Primary Key (PK)** – unik per baris.  
- **Foreign Key (FK)** – referensi ke PK tabel lain.  

### How  
1. Identifikasi entitas bisnis.  
2. Tentukan atribut dan tipe data.  
3. Definisikan PK & FK.  
4. Terapkan aturan normalisasi (1NF‑3NF).  

#### Diagram ASCII  
```
+----------------+          +----------------+
|  Customer      |          |  Order         |
|----------------|          |----------------|
| PK cust_id     |<---FK--- | PK order_id    |
| name           |          | FK cust_id     |
| email          |          | order_date     |
+----------------+          +----------------+
```

#### Simple Example  
```sql
CREATE TABLE Customer (
    cust_id   INT PRIMARY KEY,
    name      VARCHAR(50) NOT NULL,
    email     VARCHAR(100)
);
```

#### Practical Example  
```sql
CREATE TABLE Order (
    order_id   INT PRIMARY KEY,
    cust_id    INT,
    order_date DATE,
    CONSTRAINT fk_cust FOREIGN KEY (cust_id) REFERENCES Customer(cust_id)
);
```

#### Trade‑offs  
- **Denormalisasi** (menyimpan data berulang) dapat meningkatkan performa baca pada skala besar, namun menambah beban pemeliharaan.  

#### Best Practices  
- Gunakan **surrogate key** (INTEGER AUTO_INCREMENT) bila natural key panjang atau kompleks.  
- Selalu beri nama constraint dengan prefiks (`pk_`, `fk_`, `uq_`, `ck_`).  

---

## Seksi 3 – Tipe Data SQL  
### Learning Objective  
- Mengidentifikasi tipe data standar SQL dan memilih yang tepat untuk tiap kolom.  

### Concept  
SQL menyediakan tipe data numerik, karakter, tanggal/waktu, dan tipe khusus (BLOB, JSON, ARRAY).  

### Why  
Pemilihan tipe data yang tepat mengoptimalkan penyimpanan, kecepatan pencarian, dan validasi data.  

### What  
| Kategori | Contoh Tipe | Keterangan |
|----------|-------------|------------|
| Numerik  | INT, BIGINT, DECIMAL(p,s) | Bilangan bulat & desimal |
| Karakter | CHAR(n), VARCHAR(n), TEXT | Fixed vs variable length |
| Tanggal/Waktu | DATE, TIME, TIMESTAMP | Penyimpanan zona waktu |
| Boolean  | BOOLEAN | TRUE/FALSE |
| Lainnya  | BLOB, CLOB, JSON, UUID | Data biner atau semi‑terstruktur |

### How  
```sql
CREATE TABLE Product (
    prod_id   INT PRIMARY KEY,
    name      VARCHAR(100) NOT NULL,
    price     DECIMAL(10,2) CHECK (price >= 0),
    in_stock  BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Diagram ASCII  
```
+-------------------------------+
|  Product                      |
|-------------------------------|
| prod_id   INT   PK            |
| name      VARCHAR(100)       |
| price     DECIMAL(10,2)      |
| in_stock  BOOLEAN            |
| created_at TIMESTAMP          |
+-------------------------------+
```

#### Simple Example  
```sql
SELECT CAST('2026-10-03' AS DATE) AS today;
```

#### Practical Example  
```sql
INSERT INTO Product (prod_id, name, price) VALUES (1, 'Keyboard', 49.99);
SELECT prod_id, name, price FROM Product WHERE price > 30;
```

#### Trade‑offs  
- **VARCHAR vs. CHAR** – CHAR lebih cepat pada panjang tetap, tetapi boros ruang bila data bervariasi.  
- **DECIMAL vs. FLOAT** – DECIMAL menjamin presisi (uang), FLOAT lebih cepat namun dapat menghasilkan rounding error.  

#### Best Practices  
- Hindari `TEXT` bila panjang maksimum dapat diprediksi (gunakan `VARCHAR`).  
- Selalu tentukan **precision** dan **scale** pada `DECIMAL`.  

---

## Seksi 4 – DDL: CREATE, ALTER, DROP  
### Learning Objective  
- Menggunakan perintah DDL untuk membuat, memodifikasi, dan menghapus objek basis data.  

### Concept  
DDL mengubah **struktur** skema, bukan data yang tersimpan.  

### Why  
Skema harus dapat berkembang seiring kebutuhan bisnis; DDL menyediakan cara terkontrol untuk melakukannya.  

### What  
- `CREATE TABLE`, `CREATE INDEX`, `CREATE VIEW`  
- `ALTER TABLE … ADD|DROP|MODIFY COLUMN`  
- `DROP TABLE`, `DROP INDEX`, `DROP VIEW`  

### How  
```sql
-- Membuat tabel
CREATE TABLE Employee (
    emp_id   INT PRIMARY KEY,
    name     VARCHAR(80) NOT NULL,
    dept_id  INT,
    salary   DECIMAL(12,2)
);

-- Menambah kolom
ALTER TABLE Employee ADD hire_date DATE;

-- Mengubah tipe kolom
ALTER TABLE Employee ALTER COLUMN salary TYPE NUMERIC(12,2);

-- Menghapus tabel
DROP TABLE Employee;
```

#### Diagram ASCII  
```
[CREATE] --> Table Definition --> [Catalog] --> Physical Files
[ALTER]  --> Metadata Update   --> [Catalog] --> Re‑compile
[DROP]   --> Remove Metadata   --> [Catalog] --> Delete Files
```

#### Simple Example  
```sql
CREATE TABLE Demo (id INT);
DROP TABLE Demo;
```

#### Practical Example  
```sql
-- Tambah index untuk pencarian cepat
CREATE INDEX idx_emp_dept ON Employee(dept_id);
```

#### Trade‑offs  
- **ALTER TABLE** pada tabel besar dapat memblokir akses (lock) dan memakan waktu.  
- **DROP** bersifat destruktif; gunakan `DROP IF EXISTS` atau backup terlebih dahulu.  

#### Best Practices  
- Selalu **versi** skrip DDL (git).  
- Gunakan **transaction** bila RDBMS mendukung DDL dalam transaksi (PostgreSQL).  
- Simulasikan perubahan di **environment staging** sebelum produksi.  

---

## Seksi 5 – DML: SELECT Dasar  
### Learning Objective  
- Menulis query SELECT untuk mengekstrak data dengan filter, urutan, dan alias.  

### Concept  
`SELECT` adalah inti DML; menghasilkan **result set** (tabel virtual).  

### Why  
Aplikasi biasanya memerlukan subset data; SELECT memungkinkan pengambilan yang efisien tanpa menyalin data.  

### What  
- **Projection** – kolom yang dipilih (`SELECT col1, col2`).  
- **Restriction** – baris yang dipilih (`WHERE`).  
- **Sorting** – urutan (`ORDER BY`).  
- **Alias** – nama sementara (`AS`).  

### How  
```sql
SELECT emp_id AS ID,
       name   AS EmployeeName,
       salary
FROM   Employee
WHERE  salary > 5000
ORDER BY salary DESC;
```

#### Diagram ASCII  
```
+-------------------+      SELECT      +-------------------+
|   Tabel Employee  | ---------------> |   Result Set      |
|-------------------|   (proj, filt)   |-------------------|
| emp_id | name ... |                  | ID | EmployeeName |
+-------------------+                  | ...             |
```

#### Simple Example  
```sql
SELECT 1+1 AS sum;
```

#### Practical Example  
```sql
-- Laporan gaji > 5k, urut menurun
SELECT emp_id, name, salary
FROM Employee
WHERE salary >= 5000
ORDER BY salary DESC;
```

#### Trade‑offs  
- **SELECT *** (semua kolom) mudah, tetapi dapat menurunkan performa bila tabel lebar.  
- **ORDER BY** memaksa sorting; gunakan indeks yang mendukung urutan bila memungkinkan.  

#### Best Practices  
- Selalu **spesifik** kolom yang dibutuhkan.  
- Hindari fungsi di kolom yang di‑`WHERE` kecuali indeks mendukung (misal `WHERE YEAR(date)=2023`).  

---

## Seksi 6 – Filter Lanjutan: WHERE, AND, OR, NOT, IN, BETWEEN, LIKE  
### Learning Objective  
- Menggunakan operator logika dan pencarian pola untuk filter kompleks.  

### Concept  
`WHERE` mengaplikasikan **predicate** pada setiap baris; kombinasi operator menghasilkan kondisi boolean.  

### Why  
Kondisi yang tepat mengurangi jumlah baris yang diproses, meningkatkan kecepatan query.  

### What  
| Operator | Contoh | Keterangan |
|----------|--------|------------|
| `=`      | `col = 5` | Sama dengan |
| `<>` / `!=` | `col <> 5` | Tidak sama |
| `>`, `<`, `>=`, `<=` | `col > 10` | Perbandingan |
| `AND` / `OR` / `NOT` | `col>5 AND col<10` | Logika |
| `IN` | `col IN (1,2,3)` | Daftar nilai |
| `BETWEEN` | `col BETWEEN 1 AND 5` | Rentang inklusif |
| `LIKE` | `col LIKE 'A%'` | Pola wildcard (`%`, `_`) |
| `IS NULL` | `col IS NULL` | Nilai null |

### How  
```sql
SELECT *
FROM   Employee
WHERE  dept_id IN (10,20,30)
  AND  salary BETWEEN 4000 AND 8000
  AND  name LIKE 'J%';
```

#### Diagram ASCII  
```
[Rows] --> Apply Predicate --> [Filtered Rows]
```

#### Simple Example  
```sql
SELECT 1 AS test WHERE 5 BETWEEN 1 AND 10;
```

#### Practical Example  
```sql
-- Cari karyawan yang tidak memiliki departemen
SELECT emp_id, name
FROM Employee
WHERE dept_id IS NULL;
```

#### Trade‑offs  
- `LIKE '%abc'` tidak dapat menggunakan indeks (full scan).  
- `IN` dengan banyak nilai (>1000) dapat memperlambat; pertimbangkan **temporary table** atau **JOIN**.  

#### Best Practices  
- Gunakan **parameterized queries** untuk menghindari SQL Injection.  
- Tempatkan kondisi paling selektif pertama (optimizer biasanya mengabaikan urutan, tetapi membantu pembacaan).  

---

## Seksi 7 – Agregasi: GROUP BY, HAVING, COUNT, SUM, AVG, MIN, MAX  
### Learning Objective  
- Mengelompokkan data dan menghitung nilai agregat.  

### Concept  
`GROUP BY` mengelompokkan baris berdasarkan satu atau lebih kolom; fungsi agregat menghitung nilai pada tiap grup.  

### Why  
Laporan statistik (total penjualan, rata‑rata gaji) memerlukan agregasi.  

### What  
- **Aggregates**: `COUNT()`, `SUM()`, `AVG()`, `MIN()`, `MAX()`  
- **HAVING** – filter setelah agregasi (mirip `WHERE` tapi pada grup).  

### How  
```sql
SELECT dept_id,
       COUNT(*)          AS total_emp,
       AVG(salary)       AS avg_salary,
       MAX(salary)       AS max_salary
FROM   Employee
GROUP BY dept_id
HAVING COUNT(*) > 5
ORDER BY avg_salary DESC;
```

#### Diagram ASCII  
```
[Table] --> GROUP BY key --> [Groups] --> AGG Functions --> [Result Set]
```

#### Simple Example  
```sql
SELECT COUNT(*) AS total_rows FROM Employee;
```

#### Practical Example  
```sql
-- Laporan penjualan per bulan
SELECT DATE_TRUNC('month', order_date) AS month,
       SUM(total_amount) AS revenue
FROM   Order
GROUP BY month
ORDER BY month;
```

#### Trade‑offs  
- `GROUP BY` pada kolom yang tidak di‑indeks dapat menyebabkan **hash aggregation** yang memakan memori.  
- `HAVING` mengeksekusi setelah `GROUP BY`; gunakan `WHERE` bila memungkinkan untuk filter lebih awal.  

#### Best Practices  
- Selalu **alias** kolom agregat untuk kejelasan.  
- Hindari `SELECT *` bersama `GROUP BY`; pilih hanya kolom yang diperlukan atau gunakan **functional dependency** (SQL‑99).  

---

## Seksi 8 – Join: INNER, LEFT, RIGHT, FULL, CROSS  
### Learning Objective  
- Menggabungkan data dari dua atau lebih tabel menggunakan berbagai tipe join.  

### Concept  
`JOIN` menghubungkan baris berdasarkan kondisi kunci, menghasilkan **result set** yang merupakan kombinasi baris.  

### Why  
Data terdistribusi di tabel terpisah (normalisasi) memerlukan join untuk menghasilkan tampilan logis yang lengkap.  

### What  
| Tipe Join | Hasil |
|-----------|-------|
| `INNER JOIN` | Baris yang cocok di **kedua** tabel |
| `LEFT OUTER JOIN` | Semua baris dari tabel kiri + cocok dari kanan (NULL bila tidak ada) |
| `RIGHT OUTER JOIN` | Semua baris dari tabel kanan + cocok dari kiri |
| `FULL OUTER JOIN` | Semua baris dari **keduanya**, NULL bila tidak cocok |
| `CROSS JOIN` | Produk kartesian (semua kombinasi) |

### How  
```sql
-- Inner Join (karyawan dengan departemen)
SELECT e.emp_id, e.name, d.dept_name
FROM   Employee e
INNER JOIN Department d
        ON e.dept_id = d.dept_id;

-- Left Join (karyawan + departemen, tetap tampil walau tanpa dept)
SELECT e.emp_id, e.name, d.dept_name
FROM   Employee e
LEFT JOIN Department d
       ON e.dept_id = d.dept_id;
```

#### Diagram ASCII  
```
Table A          Table B
  +---+            +---+
  |a1 |            |b1 |
  |a2 |            |b2 |
  +---+            +---+

INNER JOIN  -->  (a1,b1) (a2,b2)   (hanya yang cocok)
LEFT JOIN   -->  (a1,b1) (a2,NULL) (semua dari A)
```

#### Simple Example  
```sql
SELECT 1 AS a, 2 AS b;
```

#### Practical Example  
```sql
-- Laporan penjualan per karyawan (termasuk yang belum pernah jual)
SELECT e.emp_id, e.name, COALESCE(SUM(o.total_amount),0) AS sales
FROM   Employee e
LEFT JOIN Order o ON e.emp_id = o.emp_id
GROUP BY e.emp_id, e.name;
```

#### Trade‑offs  
- **LEFT/RIGHT/FULL** dapat menghasilkan **NULL** yang harus ditangani (`COALESCE`).  
- **CROSS JOIN** menghasilkan ukuran eksponensial; gunakan hanya bila memang diperlukan.  

#### Best Practices  
- Selalu gunakan **alias tabel** (e, d, o) untuk mempermudah pembacaan.  
- Pastikan **join condition** menggunakan indeks (FK → PK).  

---

## Seksi 9 – Subquery & Derived Table  
### Learning Objective  
- Memanfaatkan subquery dalam SELECT, FROM, dan WHERE untuk logika bertingkat.  

### Concept  
Subquery adalah query **di dalam query**; dapat bersifat **scalar**, **row**, atau **table**.  

### Why  
Beberapa perhitungan tidak dapat di‑ekspresikan dengan satu level SELECT; subquery memberikan fleksibilitas.  

### What  
- **Scalar Subquery** – mengembalikan satu nilai (digunakan di SELECT atau WHERE).  
- **Row Subquery** – mengembalikan satu baris (digunakan dengan `IN`, `EXISTS`).  
- **Derived Table** – subquery di clause `FROM` yang berperan sebagai tabel sementara.  

### How  
```sql
-- Scalar: ambil rata‑rata gaji departemen tertentu
SELECT name,
       salary,
       (SELECT AVG(salary) FROM Employee WHERE dept_id = e.dept_id) AS dept_avg
FROM   Employee e
WHERE  salary > 5000;

-- Derived Table: total penjualan per produk
SELECT p.prod_id, p.name, s.total_sales
FROM   Product p
JOIN  (SELECT prod_id, SUM(qty) AS total_sales
       FROM OrderItem
       GROUP BY prod_id) s
      ON p.prod_id = s.prod_id;
```

#### Diagram ASCII  
```
[Outer Query] <-- Subquery (inner) --> [Result]
```

#### Simple Example  
```sql
SELECT (SELECT 1+1) AS two;
```

#### Practical Example  
```sql
-- Karyawan yang gajinya di atas rata‑rata perusahaan
SELECT emp_id, name, salary
FROM   Employee
WHERE  salary > (SELECT AVG(salary) FROM Employee);
```

#### Trade‑offs  
- Subquery yang tidak ter‑optimasi dapat menjadi **nested loop** yang lambat.  
- `EXISTS` biasanya lebih efisien daripada `IN` bila subquery menghasilkan banyak baris.  

#### Best Practices  
- Ganti subquery dengan **JOIN** bila memungkinkan (lebih mudah di‑optimasi).  
- Gunakan **CTE (WITH clause)** untuk meningkatkan keterbacaan pada query kompleks.  

---

## Seksi 10 – Common Table Expressions (CTE) & Recursive Query  
### Learning Objective  
- Membuat CTE untuk query modular dan menulis query rekursif (mis. hierarki organisasi).  

### Concept  
CTE (`WITH` clause) mendefinisikan **temporary result set** yang dapat dipanggil berulang dalam query utama.  

### Why  
CTE meningkatkan **readability**, memungkinkan **self‑reference** (rekursif) tanpa subquery berulang.  

### What  
- **Non‑recursive CTE** – satu definisi, dipakai sekali atau lebih.  
- **Recursive CTE** – memiliki bagian **anchor** dan **recursive** yang dipanggil berulang hingga tidak ada baris baru.  

### How  
```sql
-- Non‑recursive CTE: daftar karyawan senior
WITH SeniorEmp AS (
    SELECT emp_id, name, salary
    FROM   Employee
    WHERE  salary > 8000
)
SELECT * FROM SeniorEmp WHERE name LIKE 'A%';

-- Recursive CTE: struktur organisasi (manager → sub‑ordinate)
WITH RECURSIVE OrgChart AS (
    SELECT emp_id, name, manager_id, 1 AS lvl
    FROM   Employee
    WHERE  manager_id IS NULL               -- anchor (CEO)

    UNION ALL

    SELECT e.emp_id, e.name, e.manager_id, oc.lvl + 1
    FROM   Employee e
    JOIN   OrgChart oc ON e.manager_id = oc.emp_id
)
SELECT * FROM OrgChart ORDER BY lvl;
```

#### Diagram ASCII  
```
WITH CTE AS ( ... )   -->   Main Query
   |                         |
   +--- Temporary Result ----+
```

#### Simple Example  
```sql
WITH X AS (SELECT 1 AS a) SELECT a FROM X;
```

#### Practical Example  
```sql
-- Hitung total biaya proyek termasuk sub‑task (rekursif)
WITH RECURSIVE TaskCost AS (
    SELECT task_id, parent_id, cost
    FROM   Task
    WHERE  parent_id IS NULL

    UNION ALL

    SELECT t.task_id, t.parent_id, t.cost + tc.cost
    FROM   Task t
    JOIN   TaskCost tc ON t.parent_id = tc.task_id
)
SELECT task_id, cost FROM TaskCost;
```

#### Trade‑offs  
- Recursive CTE dapat menghasilkan **infinite loop** bila tidak ada batas (gunakan `MAXRECURSION` atau `WHERE` yang membatasi).  
- Beberapa RDBMS (MySQL < 8) tidak mendukung recursive CTE.  

#### Best Practices  
- Selalu beri **alias** pada CTE (`WITH cte_name AS (...)`).  
- Batasi kedalaman rekursi dengan `WHERE lvl < 100` atau set konfigurasi `max_recursion_depth`.  

---

## Seksi 11 – Views (Virtual Table)  
### Learning Objective  
- Membuat dan menggunakan *view* untuk abstraksi logika query.  

### Concept  
`VIEW` adalah **virtual table** yang menyimpan definisi query; data di‑fetch secara dinamis saat view dipanggil.  

### Why  
- Menyederhanakan query kompleks bagi pengguna non‑teknis.  
- Menyembunyikan kolom sensitif (security).  
- Menjaga konsistensi logika bisnis (single source of truth).  

### What  
- **Simple View** – satu SELECT tanpa `WITH CHECK OPTION`.  
- **Updatable View** – dapat di‑INSERT/UPDATE/DELETE bila memenuhi aturan (single table, primary key, dll).  
- **Materialized View** – penyimpanan fisik (tersedia di beberapa RDBMS).  

### How  
```sql
-- View sederhana: karyawan aktif
CREATE VIEW ActiveEmployee AS
SELECT emp_id, name, dept_id, salary
FROM   Employee
WHERE  active = TRUE;

-- Menggunakan view
SELECT * FROM ActiveEmployee WHERE salary > 6000;
```

#### Diagram ASCII  
```
[View Definition] --> (Stored Query) --> Executed on demand --> Result Set
```

#### Simple Example  
```sql
CREATE VIEW v_one AS SELECT 1 AS col;
SELECT * FROM v_one;
```

#### Practical Example  
```sql
-- Laporan penjualan per wilayah (view)
CREATE VIEW SalesByRegion AS
SELECT r.region_name,
       SUM(o.total_amount) AS revenue
FROM   Order o
JOIN   Customer c ON o.cust_id = c.cust_id
JOIN   Region r   ON c.region_id = r.region_id
GROUP BY r.region_name;
```

#### Trade‑offs  
- View **non‑materialized** menambah overhead parsing setiap pemanggilan.  
- **Updatable view** terbatas; tidak semua view dapat di‑modify.  

#### Best Practices  
- Hindari `SELECT *` dalam definisi view; pilih kolom yang diperlukan.  
- Dokumentasikan view dengan komentar (`COMMENT ON VIEW …`).  
- Gunakan **schema** khusus (`analytics`, `reporting`) untuk mengelompokkan view.  

---

## Seksi 12 – Indexes: B‑Tree, Hash, GiST, GIN  
### Learning Objective  
- Memahami cara kerja indeks, tipe‑tipe utama, dan kapan menggunakannya.  

### Concept  
Indeks adalah struktur data tambahan yang mempercepat pencarian baris berdasarkan nilai kolom.  

### Why  
Tanpa indeks, RDBMS harus **full table scan** (O(N)). Indeks menurunkan kompleksitas menjadi **O(log N)** atau **O(1)** tergantung tipe.  

### What  
| Tipe Index | Struktur | Kelebihan | Kelemahan |
|------------|----------|-----------|-----------|
| **B‑Tree** | Balanced tree | Umum, mendukung range (`BETWEEN`, `LIKE 'abc%'`) | Tidak optimal untuk full‑text |
| **Hash**   | Hash table | Pencarian equality O(1) | Tidak mendukung range, tidak portable |
| **GiST**   | Generalized Search Tree | Spatial & custom operators | Lebih kompleks |
| **GIN**    | Inverted index | Full‑text, array, JSON | Insert lebih lambat |

### How  
```sql
-- B‑Tree (default)
CREATE INDEX idx_emp_dept ON Employee(dept_id);

-- Unique index (menjamin tidak duplikat)
CREATE UNIQUE INDEX uq_emp_email ON Employee(email);

-- Partial index (hanya baris aktif)
CREATE INDEX idx_emp_active ON Employee(salary) WHERE active = TRUE;
```

#### Diagram ASCII  
```
[Table] --(index)--> B-Tree
   |                     |
   +--- key --> leaf --> row pointer
```

#### Simple Example  
```sql
CREATE INDEX idx_demo ON Demo(col1);
```

#### Practical Example  
```sql
-- Optimasi query penjualan per tanggal
CREATE INDEX idx_order_date ON Order(order_date);
EXPLAIN ANALYZE
SELECT * FROM Order WHERE order_date BETWEEN '2026-01-01' AND '2026-01-31';
```

#### Trade‑offs  
- **Insert/Update** menjadi lebih lambat karena indeks harus diperbarui.  
- Setiap indeks menambah **space overhead** (biasanya 20‑30 % dari ukuran tabel).  

#### Best Practices  
- Index kolom yang sering dipakai di **WHERE**, **JOIN**, **ORDER BY**, **GROUP BY**.  
- Hindari **duplicate indexes** (same columns, different names).  
- Gunakan **partial index** bila hanya subset data yang sering di‑query.  

---

## Seksi 13 – Constraints (PK, FK, UNIQUE, CHECK, NOT NULL)  
### Learning Objective  
- Menetapkan aturan integritas data melalui constraint.  

### Concept  
Constraint adalah aturan yang **diperiksa** oleh RDBMS pada saat `INSERT` atau `UPDATE`.  

### Why  
Menjaga **konsistensi** data, mencegah duplikasi, dan memastikan nilai berada dalam rentang yang valid.  

### What  
| Constraint | Sintaks | Contoh |
|------------|---------|--------|
| `PRIMARY KEY` | `PRIMARY KEY (col)` | `emp_id INT PRIMARY KEY` |
| `FOREIGN KEY` | `FOREIGN KEY (col) REFERENCES other(col)` | `dept_id INT REFERENCES Department(dept_id)` |
| `UNIQUE` | `UNIQUE (col)` | `email VARCHAR(100) UNIQUE` |
| `CHECK` | `CHECK (condition)` | `salary CHECK (salary >= 0)` |
| `NOT NULL` | `col TYPE NOT NULL` | `name VARCHAR(50) NOT NULL` |

### How  
```sql
CREATE TABLE Department (
    dept_id   INT PRIMARY KEY,
    dept_name VARCHAR(80) NOT NULL,
    budget    DECIMAL(12,2) CHECK (budget >= 0)
);

ALTER TABLE Employee
ADD CONSTRAINT fk_emp_dept FOREIGN KEY (dept_id)
    REFERENCES Department(dept_id)
    ON DELETE SET NULL
    ON UPDATE CASCADE;
```

#### Diagram ASCII  
```
[Table] --FK--> [Parent Table]
   |                |
   +--- Constraint --+
```

#### Simple Example  
```sql
CREATE TABLE Demo (
    id INT PRIMARY KEY,
    val INT CHECK (val > 0)
);
```

#### Practical Example  
```sql
-- Pastikan tidak ada gaji negatif
ALTER TABLE Employee ADD CONSTRAINT ck_salary_nonneg CHECK (salary >= 0);
```

#### Trade‑offs  
- **CHECK** tidak selalu didukung pada semua RDBMS (MySQL < 8.0 mengabaikannya).  
- **FK** menambah overhead pada `DELETE`/`UPDATE` karena harus memeriksa referensi.  

#### Best Practices  
- Beri nama constraint dengan **prefix** (`pk_`, `fk_`, `uq_`, `ck_`).  
- Gunakan **ON DELETE/UPDATE** yang sesuai dengan kebijakan bisnis (CASCADE, RESTRICT, SET NULL).  

---

## Seksi 14 – Transaction & Concurrency Control  
### Learning Objective  
- Mengelola transaksi atomik, konsistensi, isolasi, dan durabilitas (ACID).  

### Concept  
Transaksi adalah unit kerja **all‑or‑nothing**; RDBMS menggunakan **locking** atau **MVCC** untuk mengatur konkurensi.  

### Why  
Tanpa kontrol transaksi, operasi paralel dapat menyebabkan **dirty reads**, **lost updates**, atau **inconsistent state**.  

### What  
- **BEGIN / START TRANSACTION** – memulai.  
- **COMMIT** – menyimpan perubahan.  
- **ROLLBACK** – membatalkan.  
- **SAVEPOINT** – titik pemulihan parsial.  
- **Isolation Levels** – `READ UNCOMMITTED`, `READ COMMITTED`, `REPEATABLE READ`, `SERIALIZABLE`.  

### How  
```sql
START TRANSACTION;

UPDATE Account SET balance = balance - 100 WHERE acc_id = 1;
UPDATE Account SET balance = balance + 100 WHERE acc_id = 2;

COMMIT;
```

#### Diagram ASCII  
```
[Client] --BEGIN--> [RDBMS] --(locks)--> [Data Pages]
   |                                   |
   +--- COMMIT ------------------------+
   |                                   |
   +--- ROLLBACK ----------------------+
```

#### Simple Example  
```sql
BEGIN;
INSERT INTO Demo (id) VALUES (1);
ROLLBACK;
```

#### Practical Example  
```sql
-- Transfer uang dengan savepoint
START TRANSACTION;
SAVEPOINT sp_before_debit;
UPDATE Account SET balance = balance - 250 WHERE acc_id = 10;
-- Jika saldo negatif, rollback ke savepoint
IF (SELECT balance FROM Account WHERE acc_id = 10) < 0 THEN
    ROLLBACK TO sp_before_debit;
END IF;
UPDATE Account SET balance = balance + 250 WHERE acc_id = 20;
COMMIT;
```

#### Trade‑offs  
- **Isolation level tinggi** (SERIALIZABLE) meningkatkan **blocking** dan menurunkan throughput.  
- **MVCC** (PostgreSQL, Oracle) mengurangi lock contention tetapi meningkatkan **bloat** (dead tuples).  

#### Best Practices  
- Pilih **isolasi minimal** yang masih menjamin kebutuhan bisnis.  
- Gunakan **explicit transaction** di kode aplikasi, jangan mengandalkan autocommit.  
- Pastikan **error handling** (try/catch) men‑rollback pada kegagalan.  

---

## Seksi 15 – Stored Procedures & Functions  
### Learning Objective  
- Membuat prosedur tersimpan (stored procedure) dan fungsi (function) untuk logika bisnis di sisi server.  

### Concept  
Procedures/Functions adalah **program** SQL yang dapat dipanggil dengan parameter, mengeksekusi serangkaian pernyataan.  

### Why  
- Mengurangi **network round‑trip** (logika dijalankan di server).  
- Menjamin **konsistensi** bila dipanggil oleh banyak aplikasi.  

### What  
- **Procedure** – tidak harus mengembalikan nilai, dapat mengubah data.  
- **Function** – mengembalikan nilai (scalar atau table) dan dapat dipanggil dalam SELECT.  

### How (PostgreSQL syntax)  
```sql
-- Function scalar
CREATE OR REPLACE FUNCTION get_employee_salary(p_emp_id INT)
RETURNS NUMERIC AS $$
DECLARE v_salary NUMERIC;
BEGIN
    SELECT salary INTO v_salary FROM Employee WHERE emp_id = p_emp_id;
    RETURN v_salary;
END;
$$ LANGUAGE plpgsql;

-- Procedure (transactional)
CREATE OR REPLACE PROCEDURE transfer_funds(p_from INT, p_to INT, p_amount NUMERIC)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE Account SET balance = balance - p_amount WHERE acc_id = p_from;
    UPDATE Account SET balance = balance + p_amount WHERE acc_id = p_to;
END;
$$;
```

#### Diagram ASCII  
```
[Client] --> CALL Procedure/Function --> [RDBMS Engine] --> (SQL statements)
```

#### Simple Example  
```sql
SELECT get_employee_salary(5);
```

#### Practical Example  
```sql
CALL transfer_funds(101, 202, 1500.00);
```

#### Trade‑offs  
- **Procedural code** (PL/pgSQL, T‑SQL) menambah kompleksitas debugging.  
- Portabilitas menurun karena tiap RDBMS memiliki bahasa prosedural berbeda.  

#### Best Practices  
- Batasi **logic** dalam prosedur; tetap gunakan **set‑based** SQL, hindari loop yang tidak perlu.  
- Dokumentasikan parameter (`IN`, `OUT`, `INOUT`).  
- Gunakan **schema** khusus (`proc`, `fn`) untuk memisahkan objek prosedural.  

---

## Seksi 16 – Security: Roles, Grants, Row‑Level Security (RLS)  
### Learning Objective  
- Mengatur hak akses (privilege) pada level database, schema, tabel, dan baris.  

### Concept  
RDBMS mengontrol siapa yang dapat **melihat** atau **memodifikasi** data melalui **role** dan **grant**.  

### Why  
Keamanan data penting untuk melindungi informasi sensitif dan mematuhi regulasi (GDPR, HIPAA).  

### What  
- **ROLE** – kumpulan privilege yang dapat diberikan ke user.  
- **GRANT / REVOKE** – memberi atau mencabut hak (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `EXECUTE`).  
- **Row‑Level Security** – filter baris berdasarkan kondisi (PostgreSQL).  

### How  
```sql
-- Membuat role
CREATE ROLE analyst NOLOGIN;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analyst;

-- Memberi role ke user
GRANT analyst TO alice;

-- Row‑Level Security (PostgreSQL)
ALTER TABLE Employee ENABLE ROW LEVEL SECURITY;
CREATE POLICY emp_dept_policy ON Employee
    USING (dept_id = current_setting('app.current_dept')::INT);
```

#### Diagram ASCII  
```
[User] --ROLE--> [Privileges] --> [Objects (tables, views, functions)]
```

#### Simple Example  
```sql
GRANT SELECT ON Demo TO public;
```

#### Practical Example  
```sql
-- Hanya user dengan role manager dapat meng‑UPDATE gaji
GRANT UPDATE(salary) ON Employee TO manager;
```

#### Trade‑offs  
- **Fine‑grained privileges** meningkatkan kompleksitas manajemen.  
- **RLS** dapat menurunkan performa karena filter tambahan pada setiap query.  

#### Best Practices  
- Terapkan prinsip **least privilege**.  
- Gunakan **role hierarchy** (role yang meng‑inherit privilege).  
- Audit secara periodik (`SELECT * FROM information_schema.role_table_grants`).  

---

## Seksi 17 – Performance Tuning: EXPLAIN, ANALYZE, Index Hints  
### Learning Objective  
- Menganalisis rencana eksekusi query dan mengoptimalkannya.  

### Concept  
`EXPLAIN` menampilkan **query plan** (tree) yang menunjukkan cara RDBMS akan mengeksekusi query. `ANALYZE` menambahkan **runtime statistics**.  

### Why  
Tanpa pemahaman rencana, optimasi menjadi trial‑and‑error; `EXPLAIN` memberi insight tentang **scan type**, **join method**, dan **cost**.  

### What  
- **Seq Scan** – full table scan.  
- **Index Scan** – menggunakan indeks.  
- **Hash Join**, **Merge Join**, **Nested Loop** – metode join.  
- **Cost** – perkiraan (startup + total).  

### How (PostgreSQL contoh)  
```sql
EXPLAIN SELECT * FROM Employee WHERE dept_id = 10;
EXPLAIN ANALYZE SELECT * FROM Employee WHERE dept_id = 10;
```

#### Diagram ASCII  
```
[Query] --> EXPLAIN --> [Plan Tree]
   |
   +-- Node: Seq Scan (cost=0..123 rows=1000)
   +-- Node: Index Scan (cost=0..45 rows=200)
```

#### Simple Example  
```sql
EXPLAIN SELECT 1;
```

#### Practical Example  
```sql
-- Identifikasi bottleneck pada join
EXPLAIN ANALYZE
SELECT e.name, d.dept_name
FROM Employee e
JOIN Department d ON e.dept_id = d.dept_id
WHERE e.salary > 5000;
```

#### Trade‑offs  
- `EXPLAIN` tidak mengeksekusi query, sehingga **runtime** tidak terukur; `ANALYZE` mengeksekusi (berpotensi memodifikasi data bila query non‑read).  
- **Index hints** (MySQL `USE INDEX`) dapat memaksa rencana, tetapi mengurangi fleksibilitas optimizer.  

#### Best Practices  
- Selalu periksa **actual rows** vs. **estimated rows**; perbedaan besar menandakan statistik usang.  
- Jalankan `ANALYZE` atau `VACUUM ANALYZE` secara periodik untuk memperbarui statistik.  
- Hindari `SELECT *` dalam query produksi.  

---

## Seksi 18 – Backup & Recovery (Logical vs Physical)  
### Learning Objective  
- Memahami strategi backup (dump, snapshot) dan proses pemulihan data.  

### Concept  
- **Logical Backup** – `mysqldump`, `pg_dump` menghasilkan skrip SQL.  
- **Physical Backup** – salinan file data (file system, storage snapshot).  

### Why  
Backup melindungi dari **kerusakan hardware**, **human error**, atau **serangan ransomware**.  

### What  
| Metode | Kelebihan | Kekurangan |
|--------|-----------|------------|
| `mysqldump` / `pg_dump` | Portabel, dapat restore ke versi berbeda | Lambat pada DB besar |
| **Binary Log** (MySQL) / **WAL** (PostgreSQL) | Point‑in‑time recovery | Memerlukan konfigurasi |
| **Filesystem Snapshot** (LVM, ZFS) | Cepat, konsisten | Tidak portable antar platform |
| **Cloud Backup** (RDS snapshots) | Managed, otomatis | Biaya tambahan |

### How (PostgreSQL contoh)  
```bash
# Logical backup
pg_dump -U postgres -Fc mydb > mydb.dump

# Physical backup (base backup)
pg_basebackup -D /var/lib/pgsql/backup -Fp -Xs -P -U replicator

# Recovery (replay WAL)
pg_ctl start -D /var/lib/pgsql/data -l logfile
```

#### Diagram ASCII  
```
[DB] --Backup--> [Storage (file / dump)] --Restore--> [DB]
```

#### Simple Example  
```bash
mysqldump -u root -p mydb > mydb.sql
```

#### Practical Example  
```bash
# Point-in-time recovery (MySQL)
mysqlbinlog --start-datetime="2026-09-30 00:00:00" \
           --stop-datetime="2026-10-02 23:59:59" \
           /var/log/mysql/mysql-bin.000123 | mysql -u root -p
```

#### Trade‑offs  
- **Logical** lebih fleksibel (cross‑version) tetapi memakan waktu dan ruang.  
- **Physical** cepat, tetapi memerlukan **identical binary version** untuk restore.  

#### Best Practices  
- Jadwalkan **full backup** mingguan + **incremental** harian.  
- Simpan backup **off‑site** (cloud atau tape).  
- Uji **restore** secara periodik (drill).  

---

## Seksi 19 – SQL Standards & Vendor Extensions  
### Learning Objective  
- Mengetahui perbedaan antara standar ANSI/ISO SQL dan fitur khusus vendor (MySQL, PostgreSQL, Oracle, SQL‑Server).  

### Concept  
SQL standar (SQL‑92, SQL‑99, SQL‑2003, …) mendefinisikan **syntax** dan **semantik** umum; masing‑masing RDBMS menambahkan **extensions** (procedural language, JSON, window functions).  

### Why  
Pemahaman standar membantu menulis **portable** SQL; mengetahui extensions memungkinkan memanfaatkan fitur khusus untuk performa atau fungsionalitas.  

### What  
| Fitur | Standar | MySQL | PostgreSQL | Oracle | SQL‑Server |
|-------|---------|-------|------------|--------|------------|
| **Window Functions** | SQL:2003 | ✅ (8.0+) | ✅ | ✅ | ✅ |
| **JSON** | – | ✅ (5.7+) | ✅ (9.2+) | ✅ (12c) | ✅ (2016) |
| **MERGE** | SQL:2003 | ❌ (use `INSERT ... ON DUPLICATE`) | ✅ | ✅ | ✅ |
| **CTE** | SQL:1999 | ✅ (8.0+) | ✅ | ✅ | ✅ |
| **Stored Procedure Language** | – | PL/SQL‑like | PL/pgSQL | PL/SQL | T‑SQL |
| **Full‑Text Search** | – | ✅ (FTS) | ✅ (tsvector) | ✅ (CONTEXT) | ✅ (Full‑Text) |

### How  
- **Portability tip:** Hindari `LIMIT`/`OFFSET` yang berbeda; gunakan `FETCH FIRST n ROWS ONLY` (SQL:2008).  
- **Feature detection:** `SELECT version();` atau `SELECT @@VERSION;`.  

#### Diagram ASCII  
```
[Standard SQL] <--common--> [Vendor Extensions]
```

#### Simple Example (Standard)  
```sql
SELECT employee_id,
       ROW_NUMBER() OVER (ORDER BY salary DESC) AS rank
FROM Employee;
```

#### Practical Example (Vendor‑specific)  
```sql
-- MySQL UPSERT
INSERT INTO Employee (emp_id, name, salary)
VALUES (10, 'Budi', 5000)
ON DUPLICATE KEY UPDATE salary = VALUES(salary);
```

#### Trade‑offs  
- **Vendor lock‑in**: Menggunakan fitur khusus meningkatkan performa tetapi mengurangi kemampuan migrasi.  
- **Standard compliance**: Membatasi penggunaan fitur canggih, tetapi memudahkan **cross‑platform** development.  

#### Best Practices  
- Tuliskan **core query** dengan standar, lalu **wrap** dengan conditional logic untuk extensions bila diperlukan.  
- Dokumentasikan **dialect** pada setiap skrip (mis. `-- @dialect:postgresql`).  

---

## Seksi 20 – Ringkasan & Checklist Implementasi  
### Learning Objective  
- Mengintegrasikan seluruh konsep menjadi checklist praktis untuk proyek SQL pertama.  

### Concept  
Checklist membantu tim memastikan **kualitas**, **keamanan**, dan **performansi** sebelum go‑live.  

### Why  
Mencegah **technical debt** dan **bug produksi** yang umum pada implementasi basis data.  

### What (Checklist)  
| No | Item | Keterangan | Status |
|----|------|------------|--------|
| 1 | **Skema Desain** | Tabel, PK, FK, normalisasi 3NF | ☐ |
| 2 | **Tipe Data** | Pilih tipe yang tepat, definisi `NOT NULL` | ☐ |
| 3 | **Constraint** | PK, FK, UNIQUE, CHECK, DEFAULT | ☐ |
| 4 | **Index** | B‑Tree pada kolom filter, partial index bila perlu | ☐ |
| 5 | **Views** | Buat view untuk laporan, hindari `SELECT *` | ☐ |
| 6 | **Stored Procedure** | Logika bisnis kritis, gunakan parameter | ☐ |
| 7 | **Security** | Role, GRANT, RLS (jika diperlukan) | ☐ |
| 8 | **Transaction** | Semua operasi multi‑step dalam transaksi | ☐ |
| 9 | **Performance Test** | EXPLAIN ANALYZE, benchmark, tuning | ☐ |
|10 | **Backup Plan** | Full + incremental, test restore | ☐ |
|11 | **Documentation** | ERD, data dictionary, comment pada objek | ☐ |
|12 | **Version Control** | Skrip DDL/DML di Git, tagging rilis | ☐ |
|13 | **Monitoring** | Log slow query, alert disk space | ☐ |
|14 | **Compliance** | Audit trail, enkripsi data sensitif | ☐ |
|15 | **Migration Strategy** | Script upgrade, rollback plan | ☐ |

### How (Implementasi)  
1. **Clone** repository `git clone repo-sql-schema`.  
2. **Run** `psql -f schema.sql` (atau `mysql < schema.sql`).  
3. **Execute** unit test dengan `pgTAP` / `tSQLt`.  
4. **Deploy** ke staging, lakukan **load test** (JMeter).  
5. **Promote** ke production setelah **approval**.  

#### Diagram ASCII (Workflow)  
```
[Design] -> [DDL Scripts] -> [Version Control] -> [CI/CD] -> [Staging] -> [Prod]
```

#### Simple Example (Checklist in SQL)  
```sql
-- Verifikasi semua constraint ada
SELECT conname, contype, conrelid::regclass
FROM   pg_constraint
WHERE  conrelid = 'employee'::regclass;
```

#### Practical Example (Automated Test)  
```sql
-- pgTAP test: pastikan tidak ada NULL pada kolom NOT NULL
SELECT has_not_null('employee', 'name', 'Kolom name tidak boleh NULL');
```

#### Trade‑offs  
- Checklist yang **terlalu detail** dapat memperlambat delivery; sesuaikan dengan **risk profile** proyek.  

#### Best Practices  
- Jadikan checklist **living document**; perbarui tiap sprint.  
- Integrasikan dengan **pipeline CI/CD** (lint, static analysis, security scan).  

---  

# 📚 Penutup  
Materi di atas mencakup **seluruh fondasi** yang diperlukan untuk menguasai SQL secara profesional, dari konsep dasar hingga praktik lanjutan seperti transaksi, keamanan, dan performa. Ikuti urutan seksi, kerjakan contoh, dan gunakan checklist pada Seksi 20 untuk memastikan implementasi yang solid. Selamat belajar!  