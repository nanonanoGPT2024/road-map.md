---
[⬅️ BAB 03 Quiz & Challenge](../BAB-03-Arsitektur-API-REST-GraphQL-gRPC/BAB-03-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Indexing Internals & Query Planner ➡️](./Module-02-Indexing-Internals-BTree-Query-Planner-Partitioning.md)
---

# Module 01: Relational Modeling, Normalisasi, ACID Guarantees, & Isolation Levels

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Merancang skema basis data relasional (**RDBMS**) produksi: pemetaan entitas, relasi (1:1, 1:N, N:M via *junction table*), integritas referensial (*foreign keys*), dan pemilihan Primary Key modern (**UUIDv7 / ULID** vs **BigSerial**).
- Menerapkan metodologi **Normalisasi** (1NF, 2NF, 3NF, BCNF) dan memahami kapan harus melakukan **Denormalisasi Terencana** demi performa analitik.
- Menguasai 4 pilar jaminan transaksi **ACID**: *Atomicity* (Write-Ahead Logging / WAL), *Consistency* (Invarian integritas skema), *Isolation* (Isolasi konkurensi), dan *Durability* (*fsync* ke media fisik).
- Menganalisis 4 anomali konkurensi ANSI SQL: *Dirty Read*, *Non-Repeatable Read*, *Phantom Read*, dan *Serialization Anomaly*.
- Mengonfigurasi 4 tingkat isolasi transaksi (**Read Uncommitted**, **Read Committed**, **Repeatable Read**, **Serializable**) dan memahami arsitektur **MVCC (Multi-Version Concurrency Control)**.
- Mengimplementasikan penguncian konkuren: **Optimistic Concurrency Control (OCC)** vs **Pessimistic Concurrency Control (PCC / `SELECT FOR UPDATE`)**.

---

## 2. Prerequisite
- Memahami konsep dasar tabel, kolom, baris, dan tipe data SQL (INT, VARCHAR, TIMESTAMP, BOOLEAN).
- Pengalaman menulis query dasar SQL (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `JOIN`).
- Konsep dasar konkurensi dan race condition (Bab 02).

---

## 3. Concept
Dalam rekayasa perangkat lunak backend, **Basis Data Relasional (RDBMS)** seperti PostgreSQL dan MySQL adalah benteng pertahanan utama integritas data perusahaan. Kode aplikasi, kontainer, dan server dapat mati atau diganti kapan saja, namun data transaksi keuangan di database harus bertahan abadi tanpa cacat satu sen pun.

Kekuatan utama RDBMS terletak pada dua fondasi teoretis:
1. **Model Relasional (Edgar F. Codd, 1970)**: Data diorganisasi ke dalam tabel-tabel matematis (*relations*) yang dinormalisasi untuk mengeliminasi anomali data (anomali insert, update, dan delete).
2. **Jaminan Transaksi ACID**: Memastikan bahwa serangkaian operasi majemuk (misal: kurangi saldo Rekening A dan tambah saldo Rekening B) diperlakukan sebagai **satu unit kerja tunggal yang tidak dapat dipisahkan**.

```
+-----------------------------------------------------------------------------------+
|                        TRANSACTION EXECUTION UNDER ACID                           |
|                                                                                   |
|  [ BEGIN TRANSACTION ]                                                            |
|       |                                                                           |
|       | 1. ATOMICITY: Semuanya sukses atau semuanya gagal (All-or-Nothing)        |
|       |    Catat ke Write-Ahead Log (WAL) di disk sebelum menyentuh data page     |
|       |                                                                           |
|       | 2. CONSISTENCY: Menegakkan aturan CHECK (saldo >= 0), FOREIGN KEY, UNIQUE |
|       |                                                                           |
|       | 3. ISOLATION (via MVCC / Locks):                                          |
|       |    Transaksi lain tidak melihat data setengah-jadi sebelum commit         |
|       |                                                                           |
|       | 4. DURABILITY:                                                            |
|       |    Saat COMMIT sukses, kernel mengeksekusi fsync() ke NVMe/SSD permanen   |
|       v                                                                           |
|  [ COMMIT TRANSACTION ]                                                           |
+-----------------------------------------------------------------------------------+
```

---

## 4. Why?
Mengapa pemahaman mendalam tentang transaksi dan level isolasi sangat vital?
1. **Mencegah Kerugian Finansial Masif**: Tanpa isolasi yang tepat, dua transaksi penarikan saldo simultan sebesar Rp 1.000.000 dari rekening bersaldo Rp 1.000.000 dapat lolos keduanya (*Lost Update Anomaly*), merugikan bank.
2. **Menghindari Deadlock Sistemik**: Transaksi yang tidak dirancang dengan urutan penguncian konsisten akan memicu deadlock di tingkat database engine, menyebabkan ribuan worker backend macet (*connection pool exhaustion*).
3. **Efisiensi Throughput vs Konsistensi**: Memilih level isolasi `Serializable` untuk seluruh query akan membuat sistem sangat lambat karena lock contention tinggi, sementara level `Read Committed` terkadang terlalu longgar untuk mutasi saldo. Insinyur sistem harus tahu kapan harus menggunakan penguncian optimistis vs pesimistis.

---

## 5. What?

### A. Strategi Pemilihan Primary Key: Auto-Increment vs UUID vs ULID

| Tipe Primary Key | Karakteristik | Keuntungan | Kelemahan |
|---|---|---|---|
| **BigSerial / Auto-Increment** | Integer 64-bit berurutan (1, 2, 3...) | Ukuran kecil (8 byte), B-Tree indexing sangat efisien (*append-only clustering*) | Membocorkan metrik bisnis (kompetitor tahu jumlah transaksi harian via ID di URL), rawan enumerasi IDOR |
| **UUIDv4 (Random)** | 128-bit heksadesimal acak | Terdistribusi unik, aman dari tebakan IDOR | **Merusak Index B-Tree (Index Fragmentation)** karena penyisipan acak di tengah leaf node |
| **ULID / UUIDv7 (Time-Sorted)** | 128-bit terurut waktu (*Timestamp prefix + Random suffix*) | **Standar Emas Modern**: Unik global, aman, dan ramah B-Tree index (berurutan seperti integer) | Ukuran 16 byte (lebih besar 8 byte dari BigSerial) |

### B. Empat Tingkat Isolasi Transaksi (ANSI SQL-92) & Anomali

1. **Dirty Read**: Transaksi A membaca data yang diubah oleh Transaksi B yang **belum di-commit**. Jika Transaksi B kemudian melakukan `ROLLBACK`, Transaksi A memproses data palsu yang tidak pernah sah ada.
2. **Non-Repeatable Read (Fuzzy Read)**: Transaksi A membaca baris data X. Transaksi B memodifikasi baris data X dan `COMMIT`. Transaksi A membaca baris X kembali dan mendapati nilainya telah berubah.
3. **Phantom Read**: Transaksi A membaca sekumpulan baris data menggunakan kriteria rentang (`WHERE age > 30`, mendapatkan 5 baris). Transaksi B menambahkan baris baru (`INSERT`) yang memenuhi kriteria tersebut dan `COMMIT`. Transaksi A menjalankan query yang sama dan mendapati ada baris ke-6 muncul tiba-tiba (*phantom*).
4. **Serialization Anomaly (Write Skew)**: Dua transaksi secara independen membaca data yang sama dan membuat keputusan yang masing-masing sah, namun kombinasi dari kedua transaksi tersebut melanggar invarian bisnis sistem (contoh: dua dokter jaga mengajukan cuti bersamaan karena keduanya melihat ada dokter lain yang sedang aktif).

| Isolation Level | Dirty Read? | Non-Repeatable Read? | Phantom Read? | Serialization Anomaly? |
|---|---|---|---|---|
| **Read Uncommitted** | **Mungkin Terjadi** | **Mungkin Terjadi** | **Mungkin Terjadi** | **Mungkin Terjadi** |
| **Read Committed** *(Default PostgreSQL)* | Terlindungi | **Mungkin Terjadi** | **Mungkin Terjadi** | **Mungkin Terjadi** |
| **Repeatable Read** *(Default MySQL InnoDB)* | Terlindungi | Terlindungi | Terlindungi *(via MVCC)* | **Mungkin Terjadi (Write Skew)** |
| **Serializable** | Terlindungi | Terlindungi | Terlindungi | **Terlindungi Sepenuhnya** |

---

## 6. How?

### A. Cara Kerja MVCC (Multi-Version Concurrency Control)
PostgreSQL dan InnoDB tidak mengunci pembacaan data saat transaksi tulis sedang berlangsung (*"Readers never block writers, and writers never block readers"*).
Hal ini dimungkinkan melalui **MVCC**:
- Setiap baris tabel fisik (*tuple*) menyimpan metadata internal: `xmin` (ID transaksi pembuat baris) dan `xmax` (ID transaksi penghapus/pembaru baris).
- Ketika perintah `UPDATE` dieksekusi, database **tidak menimpa data di tempat**, melainkan menyisipkan baris versi baru di disk dan menandai `xmax` baris lama.
- Transaksi membaca (*SELECT*) hanya melihat versi baris (*snapshot*) yang dibuat sebelum transaksi baca tersebut dimulai.
- Proses background pembersihan (*Vacuuming* di PostgreSQL atau *Purge Threads* di MySQL) secara berkala membersihkan baris lama (*dead tuples*) yang sudah tidak dapat dilihat oleh transaksi aktif manapun.

### B. Optimistic Concurrency Control (OCC) vs Pessimistic Concurrency Control (PCC)

#### 1. Pessimistic Locking (`SELECT FOR UPDATE`)
Cocok untuk sistem dengan **probabilitas konflik tinggi** (misal: sistem flash sale tiket konser yang rebutan 1 kursi):
```sql
BEGIN;
-- Mengunci baris secara eksklusif. Transaksi lain yang mencoba membaca/menulis baris ini akan DITAHAN (WAIT).
SELECT balance FROM accounts WHERE id = 1001 FOR UPDATE;

UPDATE accounts SET balance = balance - 50000 WHERE id = 1001;
COMMIT;
```

#### 2. Optimistic Concurrency Control (OCC via Versioning)
Cocok untuk sistem dengan **probabilitas konflik rendah hingga sedang** (kebanyakan aplikasi SaaS atau edit profil pengguna):
```sql
-- Tidak ada penguncian saat membaca data! Sangat cepat dan scalable.
SELECT id, email, version FROM users WHERE id = 45; -- version = 3

-- Saat menulis, pastikan versi belum berubah
UPDATE users 
SET email = 'new@mail.com', version = version + 1 
WHERE id = 45 AND version = 3;

-- Kode backend memeriksa Rows Affected:
-- Jika Rows Affected == 1 -> Sukses!
-- Jika Rows Affected == 0 -> Terjadi tabrakan konkurensi! Tolak atau retry secara otomatis.
```

---

## 7. Analogy
Bayangkan **Pengelolaan Dokumen Kontrak Kerja Fisik**:
- **Pessimistic Locking (`FOR UPDATE`)**: Anda mengambil map dokumen kontrak dari lemari arsip, mengunci pintu ruangan kerja Anda, dan membaca dokumen tersebut. Rekan kerja lain yang ingin melihat map tersebut harus berdiri mengantre di depan pintu hingga Anda selesai dan keluar dari ruangan.
- **Optimistic Locking (OCC)**: Anda dan rekan kerja Anda memfotokopi dokumen kontrak yang sama (membaca versi 1). Anda berdua mengedit salinan masing-masing di meja kerja. Anda menyerahkan revisi ke arsiparis terlebih dahulu (menjadi versi 2). Saat rekan kerja Anda datang menyerahkan revisinya yang berbasis versi 1, arsiparis menolak: *"Maaf, dokumen aslinya sudah diperbarui oleh orang lain. Silakan fotokopi ulang versi terbaru!"*.
- **MVCC**: Seperti kamera time-lapse yang menyimpan seluruh foto riwayat perubahan dokumen dari masa ke masa. Anda membaca arsip foto keadaan jam 09:00 pagi, sementara atasan Anda sedang menulis revisi baru di jam 09:05 tanpa mengaburkan penglihatan Anda terhadap dokumen versi jam 09:00.

---

## 8. Diagram: MVCC Tuple Versioning di PostgreSQL

```
+---------------------------------------------------------------------------------+
|                       POSTGRESQL MVCC TUPLE INTERNALS                           |
+---------------------------------------------------------------------------------+

Table: accounts (Physical Heap Disk Block)

Tuple 1:
+--------+------------------+------------------+------------+--------------------+
|  id    | xmin (Created Tx)| xmax (Deleted Tx)|  balance   | Status             |
+--------+------------------+------------------+------------+--------------------+
| 1001   | Tx #500          | Tx #505          | 1000000    | Expired / Dead     |
+--------+------------------+------------------+------------+--------------------+
                              |
                              | (Updated by Tx #505)
                              v
Tuple 2:
+--------+------------------+------------------+------------+--------------------+
|  id    | xmin (Created Tx)| xmax (Deleted Tx)|  balance   | Status             |
+--------+------------------+------------------+------------+--------------------+
| 1001   | Tx #505          | 0 (Active)       | 1500000    | Visible to New Tx  |
+--------+------------------+------------------+------------+--------------------+

- Transaksi #502 yang masih berjalan hanya membaca Tuple 1 (karena xmax 505 > 502).
- Transaksi #506 membaca Tuple 2.
- Tidak ada transaksi yang saling mengunci pembacaan!
```

---

## 9. Simple Example: Demonstrasi Write-Ahead Log (WAL) & Atomicity

Contoh transfer dana bank multi-rekening yang aman dari pemadaman listrik di tengah jalan:

```sql
BEGIN TRANSACTION;

-- 1. Potong saldo Rekening Pengirim
UPDATE accounts 
SET balance = balance - 250000 
WHERE id = 'ACC-01' AND balance >= 250000;

-- Periksa apakah pemotongan valid
-- (Jika saldo kurang, backend mengeksekusi ROLLBACK)

-- 2. Tambah saldo Rekening Penerima
UPDATE accounts 
SET balance = balance + 250000 
WHERE id = 'ACC-02';

-- 3. Catat entri mutasi buku besar audit (Double-Entry Bookkeeping)
INSERT INTO ledger_entries (source_account, dest_account, amount, created_at)
VALUES ('ACC-01', 'ACC-02', 250000, NOW());

COMMIT;
```
Jika listrik datacenter padam tepat setelah langkah 1, saat database menyala kembali (*Crash Recovery*), engine database membaca **Write-Ahead Log (WAL)** dan otomatis me-rollback perubahan langkah 1, menjamin prinsip **All-or-Nothing**.

---

## 10. Practical Example: Implementasi Optimistic Concurrency Control di Node.js

```javascript
async function updateProductInventory(productId, decrementQty) {
  const maxRetries = 3;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    // 1. Baca data stok dan nomor versi saat ini
    const product = await db.query(
      'SELECT id, stock, version FROM products WHERE id = $1', 
      [productId]
    );

    if (product.stock < decrementQty) {
      throw new Error("Stok barang tidak mencukupi!");
    }

    const newStock = product.stock - decrementQty;
    const currentVersion = product.version;

    // 2. Lakukan update bersyarat berbasis nomor versi
    const result = await db.query(
      `UPDATE products 
       SET stock = $1, version = version + 1 
       WHERE id = $2 AND version = $3`,
      [newStock, productId, currentVersion]
    );

    // 3. Jika berhasil mengubah 1 baris, operasi sukses!
    if (result.rowCount === 1) {
      return { success: true, remainingStock: newStock };
    }

    // Jika rowCount === 0, berarti ada thread lain yang mengubah versi lebih dulu!
    console.warn(`[OCC Collision] Percobaan ke-${attempt} gagal akibat tabrakan versi. Mencoba ulang...`);
    await new Promise(r => setTimeout(r, Math.random() * 50)); // Jitter backoff
  }

  throw new Error("Gagal memperbarui inventaris setelah 3 kali percobaan konkurensi.");
}
```

---

## 11. Real World Example: Bug Double-Spending Senilai $1.2 Juta Akibat Isolation Level Salah
Sebuah bursa pertukaran mata uang kripto mengalami kerugian $1.200.000 akibat eksploitasi penarikan dana simultan:
- Sistem backend mereka menggunakan level isolasi default `Read Committed` tanpa penguncian baris (*No Lock*).
- Kode penarikan mereka:
  1. `balance = SELECT balance FROM user_wallet WHERE user_id = 123;`
  2. `if (balance >= withdraw_amount) { ... }`
  3. `UPDATE user_wallet SET balance = balance - withdraw_amount;`
- Penyerang mengirimkan 20 request penarikan HTTP simultan dalam milidetik yang sama.
- Pada level `Read Committed`, ke-20 transaksi membaca saldo awal Rp 10.000.000 secara bersamaan (karena belum ada yang commit). Ke-20 transaksi lolos validasi `balance >= 10.000.000` dan mentransfer total Rp 200.000.000 ke rekening penyerang!
- **Solusi Perbaikan Pasca-Insiden**:
  Mengubah query pembacaan menjadi `SELECT balance FROM user_wallet WHERE user_id = 123 FOR UPDATE;` (Pessimistic Row Lock). Transaksi ke-2 hingga ke-20 dipaksa mengantre dan membaca saldo yang telah terpotong oleh transaksi ke-1.

---

## 12. Trade-offs

| Pendekatan | Keunggulan Utama | Risiko / Kerugian |
|---|---|---|
| **Pessimistic Locking (`FOR UPDATE`)** | Keamanan data terjamin mutlak, zero race condition | Menurunkan throughput, memicu antrean koneksi, resiko Deadlock |
| **Optimistic Locking (OCC)** | Non-blocking, throughput sangat tinggi, zero deadlock | Gagal dan harus retry jika tingkat benturan tinggi (*high contention*) |
| **Level Isolasi Serializable** | Mencegah seluruh anomali ANSI SQL | Sering melempar error `40001: could not serialize access`, aplikasi wajib punya retry logic |
| **Denormalisasi Tabel** | Query `SELECT` analitik super cepat (tanpa multi-JOIN) | Rawan inkonsistensi data, duplikasi data di banyak tempat, update lebih rumit |

---

## 13. When To Use
- Gunakan **Pessimistic Locking (`SELECT FOR UPDATE`)** pada transaksi finansial mutasi saldo, pemesanan tiket kursi terbatas, atau inventaris flash sale barang langka.
- Gunakan **Optimistic Concurrency Control (OCC)** untuk formulir master data, konfigurasi CMS, atau alur kerja kolaboratif di mana konflik jarang terjadi.
- Gunakan **UUIDv7 / ULID** sebagai Primary Key untuk seluruh tabel baru di sistem backend terdistribusi.

---

## 14. When NOT To Use
- **JANGAN** membiarkan transaksi terbuka (*open transaction*) dalam durasi lama sambil menunggu panggilan HTTP API eksternal (seperti menunggu balasan payment gateway Midtrans/Stripe). Koneksi database akan tertahan dan menguras *database connection pool* (*Connection Pool Starvation*).
- Jangan menggunakan level isolasi `Read Uncommitted` di lingkungan produksi perbankan atau e-commerce.

---

## 15. Common Mistakes
1. **Lupa Klausa `ORDER BY` Saat Mengunci Banyak Baris (Deadlock Trap)**: Transaksi 1 mengunci Akun A lalu Akun B. Transaksi 2 mengunci Akun B lalu Akun A. Terjadi Deadlock! Solusi: Selalu urutkan ID baris sebelum mengunci: `SELECT * FROM accounts WHERE id IN (1, 2) ORDER BY id FOR UPDATE;`.
2. **Mengabaikan Dampak Table Bloat pada MVCC**: Sering melakukan jutaan `UPDATE` pada PostgreSQL tanpa tuning autovacuum, menyebabkan ukuran file tabel di hard disk membengkak 10x lipat dari data aslinya.
3. **Mengira Transaksi Database Mengisolasi Memori Kode Aplikasi**: Mengira bahwa `BEGIN TRANSACTION` otomatis mengamankan variabel in-memory JavaScript/Go. Isolasi transaksi hanya berlaku di layer database engine!

---

## 16. Best Practices
- **Must Have**: Pastikan seluruh transaksi database sesingkat mungkin (*keep transactions short*); jalankan seluruh validasi bisnis di memori sebelum membuka blok `BEGIN`.
- **Recommended**: Tetapkan parameter `statement_timeout` (misal 5.000ms) dan `lock_timeout` (misal 2.000ms) di level database untuk mencegah query macet menggantung selamanya.
- **Advanced**: Implementasikan **Advisory Locks** di PostgreSQL (`pg_advisory_xact_lock()`) untuk sinkronisasi mutex terdistribusi tingkat aplikasi menggunakan database.
- **Avoid**: Menggunakan tipe data `FLOAT` untuk nilai moneter mata uang. Selalu gunakan `NUMERIC / DECIMAL` atau integer (sen/rupiah terkecil).

---

## 17. Troubleshooting Guide
```
Masalah: Aplikasi menerima error "deadlock detected" (SQLState: 40P01).
Penyebab : Dua atau lebih transaksi mencoba mengunci sekumpulan baris yang sama dengan urutan berbeda secara bersamaan.
Diagnosa : Periksa log PostgreSQL: tail -f /var/log/postgresql/postgresql.log
           Log akan menampilkan: "Process 123 waits for ShareLock on transaction 456; Process 456 waits for ShareLock on transaction 123."
Solusi   : Pastikan seluruh kode backend mengunci baris data dengan urutan ID yang deterministik (ORDER BY id ASC).

Masalah: Database PostgreSQL kehabisan ruang disk padahal jumlah baris data tidak bertambah.
Penyebab : Table Bloat akibat jutaan dead tuples yang belum dibersihkan karena autovacuum tertahan oleh long-running transaction.
Diagnosa : SELECT schemaname, relname, n_dead_tup FROM pg_stat_user_tables ORDER BY n_dead_tup DESC;
Solusi   : Matikan transaksi menggantung (idle in transaction) dan jalankan VACUUM (VERBOSE, ANALYZE).
```

---

## 18. Exercise
1. Tulis skema tabel SQL untuk dompet digital (`wallets`: id, user_id, balance, currency, version, updated_at).
2. Tulis transaksi SQL transfer saldo aman dari Wallet A ke Wallet B dengan penanganan saldo minus menggunakan constraint `CHECK (balance >= 0)`.
3. Simulasikan penguncian baris menggunakan dua sesi terminal `psql` terpisah untuk membuktikan bahwa sesi kedua menunggu sesi pertama melakukan `COMMIT`.

---

## 19. Challenge
Rancang arsitektur buku besar akuntansi ganda (*Double-Entry General Ledger System*) berskala perbankan:
1. Skema tabel tidak boleh memperbolehkan mutasi saldo langsung via `UPDATE balance` (prinsip Append-Only Ledger).
2. Setiap transaksi harus terdiri dari minimal 2 entri jurnal (Debit dan Credit) di mana $\sum \text{Debit} = \sum \text{Credit}$.
3. Buktikan bagaimana integritas data saldo dapat dihitung ulang (*reconciliation audit*) secara deterministik dari riwayat jurnal transaksi tanpa ada celah manipulasi data!

---

## 20. Summary
Model relasional dan jaminan ACID adalah fondasi stabilitas dunia digital modern. Memahami mekanisme MVCC di balik layar, menguasai mitigasi anomali transaksi melalui level isolasi yang tepat, serta menerapkan teknik penguncian optimistis dan pesimistis secara proporsional adalah kompetensi inti yang membedakan engineer biasa dari pakar sistem backend enterprise.

---
[⬅️ BAB 03 Quiz & Challenge](../BAB-03-Arsitektur-API-REST-GraphQL-gRPC/BAB-03-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Indexing Internals & Query Planner ➡️](./Module-02-Indexing-Internals-BTree-Query-Planner-Partitioning.md)
---
