---
[⬅️ Module 01: Database Testing & ACID](./Module-01-Database-Testing-ACID-SQL-Verification-Migrations.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 07 ➡️](./BAB-07-Quiz-dan-Challenge.md)
---

# Module 02: Manajemen Data Uji (Test Data Management), Masking Privasi (PII), & Database Ephemeral

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Menguasai siklus hidup **Test Data Management (TDM)**: *Data Generation, Seeding, Refreshing, Isolation,* dan *Teardown Cleanup*.
- Menerapkan prinsip kepatuhan hukum privasi data global dan nasional (**GDPR** dan **UU Pelindungan Data Pribadi / UU PDP No. 27 Tahun 2022**) dalam lingkungan pengujian QA.
- Menguasai teknik **Data Masking, Anonymization, & Pseudonymization** untuk menyamarkan data pribadi sensitif (*Personally Identifiable Information / PII*): Nama, NIK KTP, Nomor HP, Email, dan Nomor Rekening/Kartu Kredit pada dump database staging.
- Membedakan strategi data uji: **Static Hardcoded Fixtures** versus **Dynamic Synthetic Data Factories**.
- Membangun lingkungan pengujian database terisolasi menggunakan **Docker Ephemeral Containers** guna mengaktifkan eksekusi test suite secara paralel tanpa konflik data (*Zero Cross-Test Pollution*).

---

## 2. Prerequisite
- Memahami konsep pengujian database relasional dan konstrain SQL dari Module 01.
- Pemahaman dasar tentang format data JSON, CSV, atau SQL dumps.

---

## 3. Concept
Dalam dunia pengujian perangkat lunak, terdapat sebuah pepatah terkenal: *"Kualitas pengujian Anda hanya sebaik data uji yang Anda gunakan."* Jika Anda menguji sistem e-commerce hanya dengan 1 akun tester yang memiliki riwayat pesanan kosong, Anda tidak akan pernah menemukan bug performa query lambat (*slow queries*), kegagalan paginasi, atau kesalahan agregasi laporan bulanan.

Namun, menyalin (*dumping*) database produksi mentah ke lingkungan staging adalah pelanggaran hukum dan celah keamanan fatal. Server staging biasanya memiliki kontrol akses yang lebih longgar, sehingga rentan diretas dan membocorkan data asli nasabah ke publik.

Solusi profesionalnya adalah **Test Data Management (TDM)** terstruktur. TDM menggabungkan pembuatan **Data Sintetis (Synthetic Data)** berdimensi realistis dan proses **Penyamaran Data (Data Masking & PII Obfuscation)** yang mengubah data rahasia menjadi data acak yang tetap mempertahankan format dan karakteristik relasional aslinya.

---

## 4. Why?
Mengapa Test Data Management dan Masking PII sangat krusial?
1. **Kepatuhan Hukum Pidana & Denda Multimiliar (UU PDP & GDPR)**: Memindahkan data NIK KTP atau rekam medis asli pengguna ke server pengujian yang tidak terenkripsi melanggar UU PDP No. 27 Tahun 2022 dengan ancaman pidana penjara dan denda ganti rugi hingga miliaran rupiah.
2. **Mencegah "State Pollution" Antar-Test**: Jika Test Case A mengubah status kupon diskon menjadi "EXPIRED", maka Test Case B yang dijalankan setelahnya akan gagal (*flaky*) karena kupon sudah tidak aktif. TDM menjamin setiap test dimulai dari dataset yang bersih.
3. **Menguji Skala Volume Data Nyata (Volume & Stress Data)**: Data buatan tangan manual biasanya hanya terdiri dari 5–10 baris. TDM memungkinkan injeksi instan 500.000 baris data sintetis untuk menguji ketahanan indeks database.

---

## 5. What?

### A. Klasifikasi Data Sensitif (Personally Identifiable Information - PII)

```text
========================================================================================
                          PII CLASSIFICATION IN QA STAGING
========================================================================================

  KATEGORI 1: DATA IDENTITAS NASIONAL (Wajib Masking Total)
  - NIK KTP (16 Digit)       --> Ganti dengan Algoritma Sintetis 16 Digit Acak
  - Nomor Paspor / SIM       --> Ganti dengan Format Acak Prefiks Standar

  KATEGORI 2: DATA KONTAK PRIBADI (Wajib Anonymization)
  - Alamat Email Riil        --> user_*****@qa-sandbox.internal
  - Nomor Handphone          --> 0812-****-9901
  - Alamat Domisili          --> Nama Jalan & Kota Fiktif

  KATEGORI 3: DATA FINANSIAL & TRANSAKSI (Wajib Enkripsi / Masking)
  - Nomor Kartu Kredit (PAN) --> 4111-****-****-1234 (Format PCI-DSS)
  - Saldo & Gaji             --> Nilai Numerik Sintetis Terdistribusi
```

---

### B. Teknik-Teknik Data Masking
1. **Substitution (Penggantian)**: Mengganti nama asli dengan nama acak dari kamus sintetis (misal: "Budi Santoso" $\to$ "John Doe").
2. **Shuffling (Pengacakan Baris)**: Mengacak nilai dalam satu kolom antar-baris yang berbeda sehingga relasi antara nama asli dan nomor rekening terputus total.
3. **Number & Date Variance**: Mengubah tanggal lahir asli secara acak dalam rentang $\pm 30$ hari untuk menjaga distribusi usia tanpa membocorkan tanggal persis.
4. **Masking Out (Pengaburan Sebagian)**: Menimpa sebagian karakter dengan tanda bintang: `4512-****-****-8819`.
5. **Nulling Out / Deletion**: Menghapus total data yang tidak relevan untuk pengujian (misal: menghapus foto KTP fisik atau rekaman biometrik sidik jari).

---

### C. Siklus Hidup Data Uji (TDM Lifecycle)

```text
========================================================================================
                          TEST DATA MANAGEMENT LIFECYCLE
========================================================================================

 [ 1. SEED / PROVISION ]  --> Injeksi dataset awal (Baseline Fixtures) ke DB.
            |
            v
 [ 2. TEST EXECUTION ]   --> Test suite berjalan, membaca dan memutasi data.
            |
            v
 [ 3. ISOLATE / RESTORE ] --> Gunakan DB Transaction Rollback atau Docker Snapshot.
            |
            v
 [ 4. TEARDOWN / CLEANUP] --> Bersihkan file temporary & truncate tabel mutasi.
```

---

## 6. How? Arsitektur Database Ephemeral Menggunakan Docker

Salah satu terobosan terbesar dalam TDM modern adalah **Ephemeral Containerized Database**:

```text
========================================================================================
                     EPHEMERAL DOCKER DATABASE TESTING FLOW
========================================================================================

  [ CI/CD PIPELINE RUNNER (GitHub Actions / GitLab CI) ]
            |
            | 1. docker run -d -p 5432:5432 postgres:16-alpine
            v
  [ Fresh Isolated Postgres Container (DB Kosong Murni) ]
            |
            | 2. Jalankan Migrasi Skema (Flyway / Prisma Migrate)
            v
  [ Skema Terstruktur Lengkap ]
            |
            | 3. Jalankan Seeder Data Sintetis (Faker Factory)
            v
  [ Golden Baseline Dataset Siap Diuji ]
            |
            | 4. Jalankan 500 Automated Tests Secara Paralel!
            v
  [ 5. docker rm -f postgres-container (Hancurkan Container!) ]
  (Tidak ada sampah data yang tersisa, 100% Bersih untuk rilis berikutnya)
```

---

## 7. Analogy
Bayangkan sebuah panggung latihan teater aksi:
- **Menggunakan Data Produksi Asli**: Anda berlatih adegan perkelahian pedang menggunakan pedang samurai asli yang sangat tajam. Jika aktor melakukan satu kesalahan kecil, seseorang akan terluka parah atau tewas (Pelanggaran privasi / kebocoran data).
- **Menggunakan Data Masking / Sintetis**: Anda menggunakan pedang kayu imitasi yang memiliki bobot, ukuran, dan keseimbangan persis seperti pedang asli, tetapi tumpul dan aman. Aktor dapat berlatih jungkir balik 100 kali tanpa rasa takut terluka.
- **Ephemeral Database**: Anda memiliki tombol panggung yang dalam 1 detik dapat mereset seluruh properti panggung yang berantakan kembali ke posisi awal yang rapi sebelum adegan baru dimulai.

---

## 8. Diagram

```text
========================================================================================
                      DATA MASKING & ANONYMIZATION PIPELINE
========================================================================================

 [ PRODUCTION DATABASE ] (Data Asli Pengguna: PII Sensitif)
          |
          | 1. Ekspor Dump DB (Terenkripsi)
          v
 [ SECURE ETL MASKING WORKER ]
          |
          |-- Nama Asli    ====> Ganti Nama Fiktif (Substitution)
          |-- NIK KTP      ====> Generate NIK Sintetis Valid Checksum
          |-- Email Asli   ====> Obfuscate: anon_{hash}@staging.internal
          |-- Kartu Kredit ====> Format Preserving Tokenization
          |
          v
 [ SANITIZED STAGING DB ] (Aman Digunakan QA, Bebas Pelanggaran Hukum)
          |
          v
 [ QA Automated & Manual Testing ]
```

---

## 9. Simple Example: Algoritma Masking PII dalam JavaScript

```javascript
// Utilitas Masking Data Pribadi (PII) untuk Staging Sanitizer
class PiiMasker {
  static maskEmail(email) {
    const [name, domain] = email.split("@");
    if (!domain) return "invalid@masked.internal";
    const visibleChars = name.substring(0, 2);
    return `${visibleChars}***@${domain}`;
  }

  static maskPhoneNumber(phone) {
    // 081234567890 -> 0812****7890
    if (phone.length < 8) return "0800****0000";
    return phone.substring(0, 4) + "****" + phone.substring(phone.length - 4);
  }

  static maskCreditCard(pan) {
    // 4111 2222 3333 4444 -> **** **** **** 4444
    const cleanPan = pan.replace(/\s+/g, "");
    const last4 = cleanPan.substring(cleanPan.length - 4);
    return `****-****-****-${last4}`;
  }
}

// Demonstrasi:
console.log(PiiMasker.maskEmail("budi.santoso@perusahaan.co.id")); // bu***@perusahaan.co.id
console.log(PiiMasker.maskPhoneNumber("081298765432"));          // 0812****5432
console.log(PiiMasker.maskCreditCard("4111 2222 3333 9988"));     // ****-****-****-9988
```

---

## 10. Practical Example: Pembuat Data Sintetis Berdimensi Realistis (Synthetic Data Generator)

```javascript
class SyntheticUserSeeder {
  static generateBatch(count = 100) {
    const users = [];
    const firstNames = ["Ahmad", "Budi", "Citra", "Dewi", "Eko", "Fajar", "Gita", "Hendra"];
    const lastNames = ["Pratama", "Santoso", "Wijaya", "Kusuma", "Lestari", "Siregar"];

    for (let i = 1; i <= count; i++) {
      const first = firstNames[Math.floor(Math.random() * firstNames.length)];
      const last = lastNames[Math.floor(Math.random() * lastNames.length)];
      const timestamp = Date.now();

      users.push({
        id: `USR-${i.toString().padStart(6, "0")}`,
        fullName: `${first} ${last}`,
        email: `synth_${timestamp}_${i}@qa-sandbox.internal`,
        phone: `0812${Math.floor(10000000 + Math.random() * 90000000)}`,
        balance: Math.floor(Math.random() * 5000000), // Saldo 0 - 5 Juta
        isVerified: Math.random() > 0.2 // 80% akun terverifikasi
      });
    }
    return users;
  }
}
```

---

## 11. Real World Example: Kebocoran Data Pemilu Akibat Database Staging Tanpa Masking
Pada tahun 2020, data lebih dari 2,3 juta pemilih dalam format dump file database bocor di forum hacker:
- **Penyebab**: Tim pengembang pihak ketiga membuat replika data produksi untuk keperluan *testing* modul verifikasi data pemilih di server cloud staging.
- Server staging tersebut tidak memiliki password database yang kuat dan dapat diakses dari internet publik (*Public IP tanpa VPN*).
- Karena data tidak disamarkan (*unmasked*), seluruh NIK KTP, nama lengkap, tanggal lahir, dan alamat rumah asli warga negara terekspos bebas.
- **Pencegahan**: Penerapan pipeline *Data Masking Otomatis* pada proses backup-restore database mutlak diperlukan agar data yang keluar dari lingkungan produksi selalu dalam kondisi tersamarkan (*sanitized*).

---

## 12. Trade-offs

| Strategi Data Uji | Keuntungan | Kelemahan | Kapan Digunakan? |
|---|---|---|---|
| **Production Dump Mentah (Tanpa Masking)** | 100% riil dan akurat. | **PELANGGARAN HUKUM BERAT (UU PDP)**, risiko kebocoran data. | **DILARANG KERAS DIGUNAKAN DI QA!** |
| **Masked Production Data** | Struktur dan distribusi data nyata, aman dari pelanggaran hukum. | Memerlukan pipeline masking teratur, proses ETL memakan waktu. | Uji performa & regresi menyeluruh di pre-production. |
| **Synthetic Data Generator** | Murah, instan, bebas risiko kebocoran, dapat dibuat jutaan baris. | Kadang kurang menangkap anomali perilaku manusia yang tak terduga. | Unit testing, integration testing, CI/CD pipelines harian. |
| **Static Fixtures (JSON)** | Mudah dibuat, deterministik. | Cepat usang, rawan bentrok Primary Key saat dijalankan paralel. | Uji coba cepat pada modul mandiri kecil. |

---

## 13. When To Use
- Terapkan **Data Masking** setiap kali data dari database produksi disalin ke staging atau laboratorium pengujian.
- Terapkan **Synthetic Data Generator** pada seluruh skrip otomasi pengujian di pipeline CI/CD harian.
- Gunakan **Database Container Ephemeral** untuk menjalankan pengujian yang melakukan mutasi destruktif (*Delete / Update massal*).

## 14. When NOT To Use
- Jangan menggunakan data sintetis murni untuk pengujian kepatuhan audit perbankan resmi; gunakan *Sanitized Production Clone* yang mempertahankan integritas relasi historis.
- Jangan melakukan masking secara acak hingga merusak format validasi sistem (misal: mengganti nomor KTP 16 digit menjadi string teks biasa 5 huruf yang otomatis gagal di validasi regex frontend).

---

## 15. Common Mistakes

```text
1. MISTAKE: Developer menyalin database produksi langsung ke laptop lokal tester.
   WHY IT HAPPENS: Ingin data pengujian yang lengkap secara instan tanpa ribet.
   WHY IT IS BAD: Jika laptop tester hilang atau terkena malware, jutaan data pribadi nasabah bocor ke publik.
   CORRECT APPROACH: Wajibkan proses masking otomatis di server khusus terisolasi sebelum file dump dapat diunduh.

2. MISTAKE: Memakai data uji statis berulang-ulang tanpa proses teardown (Cleanup).
   WHY IT HAPPENS: Malas membuat skrip pembersihan database.
   WHY IT IS BAD: Test case kedua gagal karena kolom email berstatus UNIQUE sudah terisi oleh eksekusi test pertama.
   CORRECT APPROACH: Gunakan dynamic factory dengan timestamp unik atau jalankan database rollback di afterEach hook.
```

---

## 16. Best Practices

### Must Have
- Penyamaran data (*Anonymization*) mutlak pada seluruh field NIK, Email, No HP, Kata Sandi, dan Nomor Rekening sebelum memasuki staging.
- Menerapkan isolasi data pengujian antar-skenario: setiap test case wajib memiliki akun uji independen.

### Recommended
- Menggunakan library data generator berstandar internasional (seperti `@faker-js/faker`).
- Menyediakan perintah terminal satu baris untuk mereset database staging: `npm run db:reset:seed`.

### Advanced
- Membangun pipeline *Self-Service Test Data Portal*: QA dapat meminta dataset pengujian spesifik (misal: *"Akun nasabah VIP dengan 3 pinjaman aktif dan tunggakan 30 hari"*) melalui bot Slack/Discord secara otomatis dalam 10 detik.

### Avoid / Overengineering
- Membuat sistem masking berbasis Machine Learning yang terlalu rumit untuk sekadar menyamarkan tabel referensi kode pos statis.

---

## 17. Troubleshooting: Gagal Seeding Akibat Foreign Key Dependency Order
Jika skrip `db:seed` melempar error:
`QueryFailedError: insert or update on table "orders" violates foreign key constraint`
1. **Penyebab**: Urutan seeding salah! Anda mencoba memasukkan data pesanan (`orders`) sebelum data pelanggan (`users`) dibuat.
2. **Solusi Penataan Urutan Seeding Relasional**:
   - Level 1 (Tabel Master Independen): `roles`, `categories`, `geographies`.
   - Level 2 (Tabel Entitas Utama): `users`, `merchants`, `products`.
   - Level 3 (Tabel Transaksi & Relasi): `orders`, `order_items`, `payments`.
   - Selalu hapus data dalam urutan terbalik: Level 3 $\to$ Level 2 $\to$ Level 1.

---

## 18. Exercise
1. Tuliskan sebuah fungsi JavaScript sederhana `maskNikKtp(nik)` yang menerima string NIK KTP 16 digit (contoh: `"3171021508920003"`) dan mengembalikan string tersamar di mana 8 digit tengah disamarkan menjadi `"********"` (contoh keluaran: `"3171********0003"`).
2. Jelaskan mengapa menjalankan database pengujian di dalam kontainer Docker ephemeral lebih unggul dibandingkan menggunakan satu database staging terpusat yang dibagi bersama oleh 10 orang QA.

---

## 19. Challenge
Rancang sebuah **Test Data Management (TDM) Automation Strategy** untuk aplikasi dompet digital:
1. Rancang skema data masking untuk tabel `users` (nama, email, phone, nik, pin_hash, balance).
2. Tuliskan generator data sintetis yang memproduksi 100 akun dengan distribusi:
   - 70 akun saldo normal (Rp 50.000 - Rp 500.000)
   - 20 akun saldo tinggi (Rp 10.000.000+)
   - 10 akun saldo nol (Rp 0)
3. Rancang prosedur *Teardown Cleanup* otomatis yang membersihkan seluruh data mutasi setelah rangkaian test suite selesai dieksekusi.

---

## 20. Summary
- Test Data Management (TDM) menjamin data pengujian selalu siap, realistis, terisolasi, dan tidak saling mencemari.
- Penyamaran Data Pribadi (Data Masking & PII Obfuscation) adalah kewajiban hukum mutlak (UU PDP & GDPR) untuk mencegah bencana kebocoran data di lingkungan staging.
- Synthetic Data Generator memproduksi ribuan data realistis secara instan tanpa menggunakan data riil nasabah.
- Docker Ephemeral Database memungkinkan eksekusi pengujian paralel yang cepat, bersih, dan bebas dari ketergantungan database fisik bersama.

---

## Hands-on Practice: Simulator Generator Data Sintetis & Mesin Masking PII
Jalankan script simulator yang memproduksi dataset pengguna sintetis berdimensi realistis dan menerapkan algoritma penyamaran data pribadi (Email, HP, NIK, Kartu Kredit) sesuai kepatuhan hukum:

```bash
node QA/BAB-07-Pengujian-Database-dan-Test-Data-Management/hands-on/m02/synthetic_data_pii_masker_sim.js
```

---
[⬅️ Module 01: Database Testing & ACID](./Module-01-Database-Testing-ACID-SQL-Verification-Migrations.md) | [📋 Silabus Induk](../README.md) | [Quiz & Challenge BAB 07 ➡️](./BAB-07-Quiz-dan-Challenge.md)
---
