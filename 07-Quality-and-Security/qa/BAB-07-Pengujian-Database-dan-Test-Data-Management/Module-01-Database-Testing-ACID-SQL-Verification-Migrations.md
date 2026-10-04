---
[⬅️ BAB 06: Quiz & Challenge](../BAB-06-Otomasi-Pengujian-Web-UI-Modern/BAB-06-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Test Data Management & PII Masking ➡️](./Module-02-Test-Data-Management-Seeding-Masking-Fixtures.md)
---

# Module 01: Pengujian Database: Verifikasi Integritas Data, Transaksi ACID, & Migrasi Skema

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengidentifikasi ruang lingkup **Database Testing (Backend Data Layer Testing)**: integritas skema, konstrain relasional, trigger, stored procedures, view, dan indeks performa.
- Memverifikasi kepatuhan transaksi **ACID (Atomicity, Consistency, Isolation, Durability)** dari perspektif Quality Assurance untuk mencegah kerusakan data pada transaksi finansial.
- Melakukan audit **Integritas Data Relasional**: validasi *Primary Key uniqueness*, *Foreign Key Referential Integrity (Cascade Delete / Restrict)*, batasan `NOT NULL`, *Check Constraints*, dan batas kapasitas tipe data (*Data Type Overflow*).
- Menguji alur **Database Migration & Schema Evolution** (alat seperti Flyway, Liquibase, Prisma, Knex): memverifikasi skrip migrasi maju (*Up Migration*) dan skrip pembatalan darurat (*Rollback / Down Migration*) tanpa kehilangan data (*Zero Data Loss*).
- Menguji keamanan data layer terhadap ancaman **SQL Injection** dan *Data Tampering* langsung di level query basis data.

---

## 2. Prerequisite
- Memahami konsep dasar API Testing dan validasi respon dari BAB 04.
- Pengetahuan dasar tentang sintaks SQL standar (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `JOIN`, `TRANSACTION`).

---

## 3. Concept
Dalam banyak kasus kegagalan sistem perangkat lunak, antarmuka pengguna (UI) dan endpoint API tampak berjalan tanpa cela: UI menampilkan status *"Transaksi Sukses"* dan API mengembalikan `200 OK`. Namun di balik layar, basis data relasional mengalami anomali: saldo dompet digital terpotong di tabel akun, tetapi baris pesanan gagal tersimpan di tabel transaksi akibat *deadlock* atau *foreign key constraint violation*.

**Database Testing** adalah pengujian yang menembus lapisan tampilan dan API untuk memvalidasi kebenaran status data mentah di media penyimpanan permanen. QA memverifikasi bahwa aturan integritas data ditegakkan di level database engine (bukan hanya di kode aplikasi), transaksi multi-tabel berjalan atomik (*all-or-nothing*), dan migrasi struktur skema tidak merusak data historis pengguna.

---

## 4. Why?
Mengapa Database Testing menjadi pembeda utama antara QA pemula dan Senior SDET?
1. **Mencegah "Data Corruption" Permanen**: Bug di UI dapat diperbaiki dengan merilis patch frontend 5 menit kemudian. Namun jika data di database sudah rusak, terduplikasi, atau kehilangan relasi referensial (*orphaned records*), pemulihannya membutuhkan waktu berminggu-minggu dengan risiko kerugian hukum dan finansial yang sangat besar.
2. **Menjamin Pertahanan Berlapis (Defense in Depth)**: Jika hacker berhasil melewati validasi input di frontend dan API controller, konstrain database (`CHECK`, `FOREIGN KEY`, `UNIQUE`) adalah benteng pertahanan terakhir yang mencegah masuknya data sampah (*garbage data*).
3. **Memastikan Keamanan Rilis Migrasi Skema**: Setiap rilis fitur baru biasanya disertai perubahan tabel (*ALTER TABLE*). Pengujian migrasi menjamin bahwa skrip migrasi tidak mengunci tabel produksi secara destruktif (*table locking*) atau memotong data teks yang sudah ada (*data truncation*).

---

## 5. What?

### A. Verifikasi 4 Pilar Transaksi ACID untuk QA

| Pilar ACID | Definisi Teknis | Skenario Uji QA (Failure Injection) | Ekspektasi Verifikasi Data |
|---|---|---|---|
| **Atomicity** | Seluruh rangkaian operasi database berhasil semua, atau gagal semua (*All-or-Nothing*). | Simulasikan kegagalan jaringan atau crash server tepat setelah debit saldo dilakukan, namun sebelum tabel log audit terisi. | Database melakukan **ROLLBACK** penuh. Saldo kembali utuh, tidak ada uang yang hilang di awang-awang. |
| **Consistency** | Data wajib berpindah dari satu status valid ke status valid lainnya, mematuhi semua aturan integritas. | Mencoba memasukkan transaksi transfer dengan nominal yang melebihi batas saldo minimal akun. | Transaksi ditolak oleh *CHECK constraint* database; saldo total sistem tetap seimbang (*balanced*). |
| **Isolation** | Transaksi yang berjalan konkuren tidak boleh saling mengganggu atau melihat status sementara transaksi lain. | Jalankan 2 request penarikan dana serentak secara bersamaan dengan nominal saldo yang pas-pasan (*Race Condition Test*). | Database menggunakan locking/isolation level yang tepat (*Serializable/Repeatable Read*); hanya 1 penarikan yang berhasil, 1 ditolak. |
| **Durability** | Sekali transaksi di-`COMMIT`, data tersimpan permanen dan tidak boleh hilang meskipun server mati listrik. | Matikan container database tepat setelah transaksi berhasil dikonfirmasi (*Kill -9*). | Saat database dinyalakan kembali, record transaksi tetap utuh terbaca dari Write-Ahead Log (WAL). |

---

### B. Spektrum Integritas Data Relasional (Data Integrity Checks)
1. **Entity Integrity**: Setiap baris memiliki *Primary Key* unik dan tidak boleh `NULL`.
2. **Referential Integrity**: Nilai *Foreign Key* wajib merujuk ke record yang sah di tabel induk. Uji aturan `ON DELETE RESTRICT` (mencegah penghapusan data master pelanggan jika masih memiliki riwayat transaksi aktif) vs `ON DELETE CASCADE`.
3. **Domain Integrity**: Nilai kolom wajib mematuhi tipe data, panjang string, format tanggal, dan aturan rentang nilai (`CHECK (price >= 0)`).
4. **User-Defined Integrity**: Aturan bisnis khusus yang ditegakkan melalui Database Trigger atau Stored Procedure (misal: memotong kuota inventaris otomatis saat pesanan dibuat).

---

## 6. How? Strategi Menguji Migrasi Skema Database

Ketika tim developer merilis perubahan skema menggunakan migration tools (seperti Flyway, Liquibase, atau Prisma):

```text
========================================================================================
                          DATABASE MIGRATION TESTING LIFECYCLE
========================================================================================

 [ STEP 1: PRE-MIGRATION STATE ]
   - Buat snapshot data awal di DB staging (Golden Dataset).
   - Catat jumlah record: SELECT COUNT(*) FROM users;
              |
              v
 [ STEP 2: RUN UP MIGRATION (V2__add_phone_column.sql) ]
   - Eksekusi migrasi penambahan kolom baru.
   - Verifikasi kolom baru terisi nilai default aman tanpa mengunci tabel.
              |
              v
 [ STEP 3: DATA INTEGRITY & REGRESSION CHECK ]
   - Verifikasi data lama tidak terpotong (No data truncation).
   - Verifikasi aplikasi tetap bisa membaca record lama dan menulis record baru.
              |
              v
 [ STEP 4: RUN DOWN MIGRATION (ROLLBACK TEST) ]
   - Eksekusi skrip pembatalan darurat (Rollback ke V1).
   - Verifikasi database kembali ke struktur asal tanpa error skrip.
              |
              v
 [ STEP 5: VERIFIKASI POST-ROLLBACK ]
   - Data historis awal tetap utuh 100%.
```

---

## 7. Analogy
Bayangkan sebuah brankas bank raksasa:
- **Pengujian UI**: Memeriksa apakah pintu depan brankas berwarna mengkilap dan pegangan putarnya mudah diputar.
- **Pengujian Database (Integritas Data)**: Membuka laci-laci di dalam brankas, menghitung setiap lembar uang fisik secara matematis, mencocokkan buku besar mutasi debit dan kredit, dan memastikan tidak ada lembaran uang palsu yang terselip.
- **Transaksi ACID**: Jika Anda menyetor uang ke teller, uang tersebut tidak boleh masuk ke catatan komputer sebelum fisik uang masuk ke dalam laci laras brankas. Jika terjadi gempa bumi saat proses serah terima uang, transaksi dibatalkan sepenuhnya (*Rollback*).

---

## 8. Diagram

```text
========================================================================================
                      TRANSACTION ATOMICITY & ROLLBACK FLOW
========================================================================================

  [ BEGIN TRANSACTION ]
           |
           v
  [ 1. UPDATE accounts SET balance = balance - 50000 WHERE id = 'ACC-01' ]
           | (Sukses: Saldo Pengirim Terpotong)
           v
  [ 2. UPDATE accounts SET balance = balance + 50000 WHERE id = 'ACC-02' ]
           | (Sukses: Saldo Penerima Bertambah)
           v
  [ 3. INSERT INTO audit_logs (id, event, amount) VALUES (...) ]
           |
           +-----------------------+
           |                       |
     (Query Sukses)          (GAGAL! Misal: Disk Penuh / Constraint Error)
           |                       |
           v                       v
     [ COMMIT ]               [ ROLLBACK ]
  (Perubahan Permanen      (Kembalikan Seluruh Perubahan:
   Tersimpan ke Disk)       Saldo Pengirim Kembali Utuh!)
```

---

## 9. Simple Example: Pengujian Transaksi ACID dengan Rollback

```javascript
// Pengujian Otomasi ACID: Memverifikasi pembatalan saldo saat terjadi error di tengah jalan
async function testAtomicityRollback(dbPool) {
  const client = await dbPool.connect();

  try {
    // 1. Ambil saldo awal
    const initialSender = await client.query("SELECT balance FROM accounts WHERE id = 'A1'");
    const startBalance = initialSender.rows[0].balance;

    // 2. Mulai transaksi
    await client.query("BEGIN");

    // Operasi 1: Potong saldo pengirim
    await client.query("UPDATE accounts SET balance = balance - 100000 WHERE id = 'A1'");

    // Operasi 2: Sengaja injeksi kegagalan (Foreign Key constraint violation)
    // Mencoba transfer ke akun tujuan yang tidak pernah ada!
    await client.query(
      "INSERT INTO transfers (sender_id, recipient_id, amount) VALUES ('A1', 'AKUN_FIKTIF_99', 100000)"
    );

    // Jika baris di atas berhasil (seharusnya gagal), lakukan commit
    await client.query("COMMIT");
    throw new Error("TEST FAILED: Seharusnya transaksi gagal karena foreign key violation!");
  } catch (err) {
    // 3. Batalkan transaksi (Rollback)
    await client.query("ROLLBACK");

    // 4. Assertion Integritas: Saldo pengirim WAJIB tetap utuh sama seperti saldo awal!
    const postCheck = await client.query("SELECT balance FROM accounts WHERE id = 'A1'");
    const currentBalance = postCheck.rows[0].balance;

    if (currentBalance !== startBalance) {
      throw new Error(`ATOMICITY VIOLATION! Saldo bocor: Awal=${startBalance}, Akhir=${currentBalance}`);
    }

    console.log("✓ ACID Atomicity Verified: Transaksi berhasil di-rollback tanpa kebocoran saldo!");
  } finally {
    client.release();
  }
}
```

---

## 10. Practical Example: Checklist Validasi Foreign Key Integrity

Pengujian integritas relasional wajib mencakup 3 skenario kunci:

1. **Uji Penolakan Child Orphaned (Insert Violation)**:
   - Mencoba menambahkan pesanan di tabel `orders` dengan `customer_id = 99999` (ID pelanggan tidak ada di tabel `customers`).
   - **Ekspektasi QA**: Database menolak dengan error `FOREIGN KEY CONSTRAINT VIOLATION`.
2. **Uji Proteksi Penghapusan Induk (Delete Restrict)**:
   - Mencoba menghapus akun pelanggan di tabel `customers` yang masih memiliki riwayat transaksi di tabel `orders`.
   - **Ekspektasi QA**: Database menolak penghapusan karena foreign key berstatus `RESTRICT`.
3. **Uji Sinkronisasi Kaskade (Delete Cascade)**:
   - Jika skema disetel `ON DELETE CASCADE` pada tabel keranjang belanja `cart_items`: menghapus user otomatis membersihkan seluruh item keranjang miliknya tanpa meninggalkan data sampah (*no orphaned rows*).

---

## 11. Real World Example: Kerugian Finansial Bank Akibat Ketiadaan Konstrain Database Unik
Sebuah bank digital di Asia Selatan meluncurkan fitur top-up saldo via kartu debit:
- Aplikasi frontend dan backend memiliki bug konkurensi di mana double-click cepat mengirim 2 request bersamaan.
- Sayangnya, tabel transaksi `account_topups` tidak memiliki **Unique Constraint** pada kolom kombinasi `(reference_number, provider_id)`.
- Akibatnya, kedua transaksi lolos masuk ke database dan saldo nasabah bertambah dua kali lipat untuk 1 kali pembayaran.
- Audit bank menemukan kerugian modal sebesar $1,2 juta sebelum tim data engineer menambahkan indeks `UNIQUE (reference_number)` secara darurat di level database.

---

## 12. Trade-offs

| Pendekatan Pengujian Database | Kelebihan | Kelemahan |
|---|---|---|
| **Memeriksa UI Saja** | Sangat mudah, tidak perlu tahu SQL. | Buta terhadap data kotor, silent constraint failures, dan data leakage di database. |
| **Memeriksa API Response Saja** | Cepat, memeriksa payload JSON. | Backend bisa saja mengembalikan data palsu dari cache tanpa menyimpannya ke database fisik. |
| **Direct Database SQL Verification** | Membuktikan kebenaran mutlak pada media penyimpanan fisik (*Ground Truth*). | Memerlukan kredensial akses database pengujian dan keahlian menulis query SQL mendalam. |

---

## 13. When To Use
- Terapkan **Database Testing** pada seluruh sistem finansial, e-commerce, ERP, perbankan, dan sistem pencatatan medis.
- Jalankan verifikasi **ACID Atomicity** pada setiap penambahan alur transaksi multi-tabel baru.
- Lakukan pengujian migrasi database (Up dan Down rollback) di staging sebelum jadwal rilis produksi.

## 14. When NOT To Use
- Jangan menghubungkan test runner langsung ke database produksi (*Production DB*); selalu gunakan database staging atau container Docker lokal yang terisolasi.
- Jangan menjalankan kueri pengujian destruktif (`TRUNCATE / DROP TABLE`) di lingkungan bersama (*Shared Staging DB*) yang sedang digunakan oleh tim tester lain.

---

## 15. Common Mistakes

```text
1. MISTAKE: Mengandalkan validasi di aplikasi dan membiarkan kolom database tanpa konstrain.
   WHY IT HAPPENS: Developer beranggapan "validasi sudah dibuat di form React dan API backend, jadi kolom DB dibuat VARCHAR dan boleh NULL semua".
   WHY IT IS BAD: Jika ada proses batch ETL, script migrasi, atau hacker yang menembus API, database akan langsung kemasukan data korup.
   CORRECT APPROACH: Wajibkan konstrain ketat di database: NOT NULL, CHECK, UNIQUE, dan FOREIGN KEY.

2. MISTAKE: Hanya menguji migrasi "UP" dan lupa menguji migrasi "DOWN" (Rollback).
   WHY IT HAPPENS: Tim berasumsi rilis akan selalu berhasil 100%.
   WHY IT IS BAD: Ketika rilis di produksi gagal di tengah malam dan tim harus melakukan rollback darurat, skrip down migration melempar syntax error dan sistem macet total.
   CORRECT APPROACH: Uji skrip Rollback Down Migration secara berkala pada dataset replika staging.
```

---

## 16. Best Practices

### Must Have
- Melakukan verifikasi langsung ke database (*Direct DB Verification*) setelah menjalankan skenario E2E transaksi kritis.
- Memastikan kolom nominal uang tidak menggunakan tipe data `FLOAT` atau `DOUBLE` (yang rentan *floating-point precision loss*); wajib menggunakan `DECIMAL` atau `NUMERIC`.

### Recommended
- Menjalankan database pengujian di dalam container Docker ephemeral yang di-destroy dan dibuat ulang secara otomatis di setiap pipeline CI/CD (*Fresh Ephemeral DB*).
- Menghitung waktu eksekusi kueri kotor: memastikan query pencarian menggunakan indeks (*Index Scan*, bukan *Sequential Full Table Scan*).

### Advanced
- Menggunakan alat *Chaos Database Injection* untuk mensimulasikan kegagalan koneksi database di tengah-tengah eksekusi transaksi batch guna memverifikasi ketahanan *Deadlock Retry Mechanism*.

### Avoid / Overengineering
- Menulis test suite SQL manual untuk memverifikasi fitur bawaan DBMS komersial (misal menguji apakah Postgres benar-benar mengurutkan `ORDER BY ASC`). Uji integritas skema dan relasi bisnis Anda, bukan mesin DBMS vendor.

---

## 17. Troubleshooting: Mendeteksi Orphaned Records pada Relasi Database
Jika data laporan keuangan bulanan tidak sinkron dengan total pesanan:
1. **Penyebab**: Ada baris data anak yang kehilangan referensi ke data induk (*Orphaned Records*) akibat penghapusan langsung tanpa kaskade.
2. **Kueri Diagnostik QA**:
   ```sql
   -- Mencari data pesanan yang customer-nya sudah tidak ada di database
   SELECT o.id, o.customer_id 
   FROM orders o 
   LEFT JOIN customers c ON o.customer_id = c.id 
   WHERE c.id IS NULL;
   ```
3. Jika kueri mengembalikan data, telah terjadi pelanggaran referensial integritas kritis.

---

## 18. Exercise
1. Diberikan skema tabel perbankan berikut:
   ```sql
   CREATE TABLE wallets (
     user_id VARCHAR(50) PRIMARY KEY,
     balance DECIMAL(15, 2) CHECK (balance >= 0)
   );
   ```
   Rancang 2 skenario pengujian database untuk memverifikasi konstrain `CHECK (balance >= 0)` (1 skenario valid dan 1 skenario penolakan saat saldo dipaksa negatif).
2. Jelaskan perbedaan konsekuensi bisnis antara aturan Foreign Key `ON DELETE CASCADE` dan `ON DELETE RESTRICT` pada relasi antara tabel `Klinik` dan tabel `Data_Rekam_Medis_Pasien`. Manakah yang wajib dipilih demi kepatuhan hukum medis?

---

## 19. Challenge
Rancang sebuah **Database Test Plan & Migration Verification Document** untuk migrasi sistem e-commerce:
1. Skenario: Menambahkan kolom `status_pembayaran` dengan nilai default `'UNPAID'` pada tabel yang memiliki 5.000.000 baris data historis.
2. Rancang prosedur verifikasi bahwa migrasi tidak menyebabkan *table locking* berlebih dan tidak menghasilkan nilai `NULL` pada baris data lama.
3. Rancang pengujian transaksi ACID konkuren: 2 pengguna serentak membeli item inventaris terakhir yang stoknya tersisa 1 buah. Buktikan secara query SQL bahwa stok akhir tidak pernah bernilai minus.

---

## 20. Summary
- Database Testing memverifikasi integritas data mentah di media penyimpanan fisik sebagai sumber kebenaran mutlak (*Ground Truth*).
- Transaksi ACID (Atomicity, Consistency, Isolation, Durability) melindungi sistem dari kerusakan data saat terjadi kegagalan jaringan atau konkurensi.
- Konstrain database (Primary Key, Foreign Key, Not Null, Check) adalah benteng pertahanan terakhir terhadap data sampah dan injeksi.
- Pengujian migrasi skema wajib memvalidasi skrip Up dan skrip Rollback Down guna memastikan keselamatan data saat terjadi insiden deployment.

---

## Hands-on Practice: Simulator Auditor Integritas Database Relasional & ACID Runner
Jalankan script simulator yang mengimplementasikan virtual relasional database engine, memverifikasi aturan konstrain Primary/Foreign Key, mengeksekusi rollback transaksi ACID saat terjadi error, dan menguji migrasi skema:

```bash
node QA/BAB-07-Pengujian-Database-dan-Test-Data-Management/hands-on/m01/sql_data_integrity_validator_sim.js
```

---
[⬅️ BAB 06: Quiz & Challenge](../BAB-06-Otomasi-Pengujian-Web-UI-Modern/BAB-06-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Test Data Management & PII Masking ➡️](./Module-02-Test-Data-Management-Seeding-Masking-Fixtures.md)
---
