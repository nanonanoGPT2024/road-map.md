---
[⬅️ Module 02: Test Data Management & PII Masking](./Module-02-Test-Data-Management-Seeding-Masking-Fixtures.md) | [📋 Silabus Induk](../README.md) | [BAB 08: Pengujian Performa ➡️](../BAB-08-Pengujian-Performa-dan-Beban-Sistem/Module-01-Fondasi-Performance-Testing-Throughput-Latency-Percentiles.md)
---

# BAB 07: Quiz, Evaluasi, & Practical Challenge

## 1. Chapter Summary & Evaluasi Pemahaman
Pada BAB 07, Anda telah mendalami lapisan paling dalam dari sistem software:
1. **Ruang Lingkup Database Testing**: Menguji skema, konstrain relasional, stored procedures, indeks, dan integritas data fisik sebagai sumber kebenaran mutlak (*Ground Truth*).
2. **Transaksi ACID**: Memverifikasi Atomicity (Rollback saat kegagalan), Consistency (Kepatuhan aturan konstrain bisnis), Isolation (Perlindungan race condition), dan Durability (Penyimpanan permanen).
3. **Integritas Relasional**: Menegakkan proteksi Primary Key unik, Foreign Key referensial (`ON DELETE RESTRICT` vs `CASCADE`), serta penolakan *Orphaned Records*.
4. **Pengujian Migrasi Skema**: Memvalidasi skrip migrasi naik (*Up*) dan skrip pembatalan darurat (*Down Rollback*) tanpa kehilangan data historis.
5. **Test Data Management (TDM)**: Siklus hidup penyediaan data (Seeding, Teardown, Isolation).
6. **Kepatuhan Hukum Privasi Data (UU PDP No. 27/2022 & GDPR)**: Menerapkan teknik *Data Masking, Anonymization,* dan *Tokenization* untuk melindungi data pribadi di lingkungan staging.

---

## 2. Interactive Quiz

### Bagian A: Basic Questions (Konseptual Fundamental)
1. **Pertanyaan 1**: Apa yang dimaksud dengan sifat **Atomicity** dalam transaksi database ACID, dan apa yang terjadi jika salah satu query di tengah transaksi mengalami kegagalan?
2. **Pertanyaan 2**: Mengapa kolom saldo rekening perbankan dilarang keras menggunakan tipe data `FLOAT` atau `DOUBLE`, dan tipe data apa yang wajib digunakan?
3. **Pertanyaan 3**: Apa perbedaan konsekuensi penghapusan data master jika Foreign Key disetel ke **`ON DELETE RESTRICT`** dibandingkan **`ON DELETE CASCADE`**?
4. **Pertanyaan 4**: Mengapa menyalin (*dumping*) database produksi mentah secara langsung ke server staging tanpa proses masking merupakan pelanggaran hukum berat menurut UU PDP No. 27 Tahun 2022?
5. **Pertanyaan 5**: Apa keuntungan utama menjalankan database pengujian di dalam **Docker Ephemeral Container** dibandingkan menggunakan satu database staging terpusat bersama?

### Bagian B: Intermediate Questions (Analisis & Teknik Pengujian)
6. **Pertanyaan 6**: Jelaskan skenario uji *Failure Injection* yang dapat dirancang oleh QA untuk membuktikan bahwa mekanisme Rollback transaksi transfer uang antar-rekening bekerja 100% tanpa kebocoran saldo!
7. **Pertanyaan 7**: Tuliskan kueri SQL diagnostik untuk mendeteksi keberadaan *Orphaned Records* pada tabel pesanan (`orders`) yang kolom `customer_id`-nya tidak lagi terdaftar di tabel pelanggan (`customers`)!
8. **Pertanyaan 8**: Jelaskan teknik **Format Preserving Masking** pada nomor kartu kredit (16 digit) dan berikan contoh hasil samarannya yang memenuhi standar keamanan PCI-DSS!
9. **Pertanyaan 9**: Mengapa pengujian migrasi database wajib memverifikasi skrip *Rollback (Down Migration)* dan bukan hanya skrip *Up Migration*?
10. **Pertanyaan 10**: Apa urutan tingkatan tabel yang benar saat menyusun skrip *Database Seeding* multi-tabel agar tidak terbentur error *Foreign Key Constraint Violation*?

### Bagian C: Scenario-Based Questions (Problem Solving Dunia Nyata)
11. **Skenario 1**: Sebuah startup fintech mengalami insiden saldo ganda: nasabah menekan tombol transfer cepat dua kali dan kedua transaksi berhasil tercatat. Di sisi database, tabel transaksi tidak memiliki indeks `UNIQUE` pada kolom `idempotency_reference`. Sebagai QA Engineer, bagaimana Anda merancang skenario pengujian konkurensi database untuk membuktikan celah ini?
12. **Skenario 2**: Seorang developer mengajukan skrip migrasi database: `ALTER TABLE users DROP COLUMN phone_number;`. Di lingkungan produksi terdapat 2.000.000 data pengguna historis. Dari sudut pandang QA dan keselamatan data, mengapa Anda wajib memblokir PR ini dan alternatif migrasi bertahap apa yang harus disarankan?
13. **Skenario 3**: Sebuah rumah sakit digital ingin menguji fitur analitik rekam medis di staging menggunakan data pasien nyata. Jelaskan pipeline anonimisasi data (PII Masking) apa saja yang wajib Anda terapkan pada tabel pasien sebelum data tersebut boleh disentuh oleh tim QA dan Data Science!

---

## 3. Chapter Challenge: Perancangan Strategi TDM & Integritas Data Core Banking

### Deskripsi Skenario
Sebuah bank digital bernama **"BankNusantara"** sedang membangun modul baru: **"Pinjaman Kilat Tanpa Agunan (KTA Digital)"**.
Tabel Utama:
1. `customers` (`id` PK, `nik` UNIQUE, `full_name`, `phone`, `email`, `monthly_income`)
2. `loans` (`id` PK, `customer_id` FK, `principal_amount`, `interest_rate`, `status`, `disbursed_at`)
3. `repayments` (`id` PK, `loan_id` FK, `installment_no`, `amount_paid`, `paid_at`)

### Tugas Anda (Deliverables):
1. **Rencana Verifikasi Integritas Relasional & ACID**:
   - Susun 3 skenario pengujian konstrain SQL (Primary Key duplicate check, Foreign Key restrict delete, dan CHECK constraint `principal_amount > 0`).
   - Rancang skenario pengujian transaksi pencairan pinjaman (`status: ACTIVE` $\to$ Tambah saldo akun) dengan failure injection tepat sebelum commit.
2. **Spesifikasi Aturan Data Masking (Kepatuhan UU PDP)**:
   - Susun tabel aturan masking untuk kolom `nik`, `full_name`, `phone`, dan `email` pada tabel `customers`.
   - Tuliskan algoritma atau regex pengganti untuk masing-masing field agar format data tetap valid saat diuji oleh aplikasi frontend.
3. **Arsitektur Ephemeral Test Data Pipeline**:
   - Tuliskan alur kerja Dockerfile / docker-compose sederhana yang membuat instance PostgreSQL pengujian terisolasi, mengeksekusi migrasi skema, memasukkan 50 baris data sintetis, menjalankan test suite, dan menghancurkan container setelahnya.

---

## 4. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] 4 pilar transaksi ACID dan teknik pembuktian rollback di database.
- [ ] Integritas data relasional (PK, FK, Check, Not Null) sebagai benteng pertahanan terakhir.
- [ ] Resiko migrasi skema database dan pentingnya menguji skrip Down Rollback.
- [ ] Perbedaan data statis (fixtures) vs data sintetis dinamis (factories).
- [ ] Kepatuhan UU PDP No. 27/2022 dan teknik masking PII (Substitution, Masking-out, Shuffling).
- [ ] Keunggulan database container ephemeral untuk eksekusi pengujian paralel.

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh kueri syntax internal Postgres pg_catalog atau MySQL information_schema.
- [ ] Detail rumus kriptografi algoritma hashing argon2/bcrypt.

### Saya Harus Bisa Melakukan:
- [ ] Menulis kueri SQL untuk mendeteksi orphaned data relasional.
- [ ] Memvalidasi integritas data fisik setelah transaksi E2E selesai.
- [ ] Merancang pipeline penyamaran data PII yang aman sebelum database staging digunakan.

---
[⬅️ Module 02: Test Data Management & PII Masking](./Module-02-Test-Data-Management-Seeding-Masking-Fixtures.md) | [📋 Silabus Induk](../README.md) | [BAB 08: Pengujian Performa ➡️](../BAB-08-Pengujian-Performa-dan-Beban-Sistem/Module-01-Fondasi-Performance-Testing-Throughput-Latency-Percentiles.md)
---
