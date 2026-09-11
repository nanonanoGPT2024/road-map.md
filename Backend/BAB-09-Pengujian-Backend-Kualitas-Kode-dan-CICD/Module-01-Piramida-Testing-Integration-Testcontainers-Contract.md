---
[⬅️ BAB 08 Quiz & Challenge](../BAB-08-Autentikasi-Otorisasi-dan-Keamanan-Backend/BAB-08-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Static Analysis, CI/CD, & Load Testing ➡️](./Module-02-Static-Analysis-CICD-Automation-dan-Load-Testing.md)
---

# Module 01: Piramida Testing, Testcontainers, & Contract Testing (Pact)

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Menguasai konsep **Piramida Pengujian (Test Pyramid)**: porsi ideal antara **Unit Tests**, **Integration Tests**, dan **End-to-End (E2E) Tests**.
- Membedakan peran pengganti pengujian (*Test Doubles*): **Dummy**, **Stub**, **Spy**, **Mock**, dan **Fake**.
- Memahami bahaya *Over-Mocking* (mocking database query yang menyembunyikan bug sintaks SQL dan constraint integritas riil).
- Menguasai paradigma **Integration Testing berbasis Testcontainers**: menjalankan instance database (PostgreSQL, Redis, Kafka) asli dan temporer di dalam Docker saat pipeline pengujian berjalan.
- Mengimplementasikan **Consumer-Driven Contract Testing** menggunakan framework **Pact** untuk memvalidasi kompatibilitas API antar-microservices tanpa perlu menjalankan seluruh service secara bersamaan.

---

## 2. Prerequisite
- Pemahaman siklus hidup request-response API REST dan gRPC (BAB 03).
- Dasar transaksi database SQL dan constraint relasional (BAB 04).
- Dasar penggunaan Docker container (diasumsikan telah memahami konsep image & port binding).

---

## 3. Concept
Dalam rekayasa perangkat lunak profesional, kode yang tidak memiliki automated tests adalah liabilitas teknis (*Technical Debt*). Setiap perubahan fitur baru atau refaktorisasi berisiko merusak fungsionalitas yang sudah ada sebelumnya (*Regression Bug*).

Namun, tidak semua pengujian diciptakan setara:
- **Unit Testing:** Menguji satu fungsi atau method logika bisnis murni secara terisolasi tanpa I/O eksternal. Sangat cepat (milidetik) dan murah dijalankan.
- **Integration Testing:** Menguji interaksi komponen perangkat lunak dengan dependensi eksternal riil (Database, Cache, Message Broker). Memastikan query SQL, transaksi ACID, dan serialisasi data bekerja semestinya.
- **End-to-End (E2E) Testing:** Menguji alur pengguna lengkap dari awal hingga akhir melintasi seluruh ekosistem service dan gateway jaringan. Sangat andal, namun paling lambat, rapuh (*flaky*), dan mahal.

---

## 4. Why?
Tanpa strategi pengujian yang matang:
1. **The Inverted Test Pyramid (Ice Cream Cone Antipattern):** Tim hanya memiliki sedikit unit test dan mengandalkan pengujian manual atau E2E tests besar yang memakan waktu 4 jam per build pipeline, memperlambat kecepatan rilis produk.
2. **False Confidence Akibat Over-Mocking:** Unit test 100% lulus karena semua query DB di-mock (`db.query.mockResolvedValue([])`), tetapi saat kode di-deploy ke server produksi, aplikasi langsung crash karena kolom database yang dipanggil ternyata tidak ada (*typo* nama kolom SQL).
3. **Breaking Changes antar Microservices:** Service A (Consumer) mengubah ekspektasi response dari field `fullName` menjadi `name`, sementara Service B (Provider) tidak mengetahui perubahan tersebut hingga terjadi error 500 saat rilis produksi bersama.

---

## 5. What? (Taksonomi Test Doubles & Test Pyramid)

### A. Taksonomi Test Doubles (Martin Fowler)
| Tipe Double | Karakteristik Utama | Skenario Penggunaan |
|---|---|---|
| **Dummy** | Objek yang dioper hanya untuk mengisi parameter fungsi, tidak pernah dipanggil | Mengisi parameter `logger` atau `context` |
| **Stub** | Menyediakan jawaban siap saji (*Canned Answers*) terhadap panggilan pengujian | Mengembalikan data user statis saat `getUserById` dipanggil |
| **Spy** | Stub yang juga mencatat bagaimana dirinya dipanggil (berapa kali, argumen apa) | Memverifikasi apakah fungsi `sendEmail` dipanggil tepat 1 kali |
| **Mock** | Objek dengan ekspektasi perilaku yang telah diprogram sebelumnya; gagal jika ekspektasi tidak terpenuhi | Memastikan urutan pemanggilan `paymentGateway.charge()` |
| **Fake** | Memiliki implementasi fungsional nyata namun disederhanakan untuk lingkungan uji | Database in-memory SQLite untuk menggantikan PostgreSQL saat uji lokal |

### B. Distribusi Proporsi Piramida Testing Ideal
```
         / \
        / E2E \         ~10% (Alur kritis checkout/login end-to-end)
       /───────\
      / Integ-  \       ~20% - 30% (Testcontainers Postgres/Redis riil)
     /  ration   \
    /─────────────\
   /   Unit Tests  \    ~60% - 70% (Logika bisnis, validasi, kalkulasi)
  /─────────────────\
```

---

## 6. How? (Arsitektur Testcontainers & Contract Testing)

### A. Testcontainers Workflow
Testcontainers mengotomatisasi siklus hidup container Docker langsung dari kode pengujian:
```
[ Test Runner (Jest / JUnit / Go Test) ]
         │
 1. Startup Container ──▶ [ Docker Engine ] ──▶ [ Spin-up ephemeral PostgreSQL:16 ]
         │                                            │ (Alokasikan dynamic random port, misal: 32778)
 2. Jalankan Migrasi DB ──────────────────────────────▶ [ Terapkan Skema Tabel & Foreign Keys ]
         │
 3. Eksekusi Integration Tests ───────────────────────▶ [ Jalankan Query SQL Nyata & Assertion ]
         │
 4. Teardown / Cleanup ───────────────────────────────▶ [ Hancurkan Container Seketika ]
```
- Setiap test suite mendapatkan instance database murni yang terisolasi 100% tanpa risiko bentrok data dengan pengembang lain.

### B. Consumer-Driven Contract Testing dengan Pact
```
1. FASE KONSUMEN (Consumer):
   OrderService (Consumer) mendefinisikan ekspektasi terhadap PaymentService:
   "Jika saya mengirim POST /charges { amount: 500 }, saya mengharapkan status 201 { chargeId: string }."
   ==> Pact Framework men-generate file: 'OrderService-PaymentService.json' (Contract).

2. FASE PENYEDIA (Provider):
   PaymentService (Provider) memverifikasi file kontrak tersebut terhadap API aslinya:
   ==> Jika PaymentService mengubah response menjadi { id: string } alih-alih chargeId,
       build CI/CD Provider akan GAGAL seketika SEBELUM kode digabung ke branch utama!
```

---

## 7. Analogy
- **Unit Test ibarat Memeriksa Busi Sepeda Motor di Meja Kerja:** Anda menguji apakah busi memercikkan api dengan baterai saku. Cepat, presisi, namun tidak menjamin motor bisa berjalan.
- **Integration Test ibarat Menghubungkan Busi ke Blok Mesin & Karburator:** Anda menguji apakah busi mampu menyulut bensin di ruang bakar mesin yang sebenarnya.
- **Contract Test (Pact) ibarat Memastikan Ukuran Baut Cocok Sebelum Merakit:** Anda mengukur diameter ulir baut tanpa harus menyalakan seluruh sepeda motor. Anda tahu pasti bahwa bagian A dan bagian B akan pas saat disatukan.

---

## 8. Diagram: Masalah Over-Mocking vs Testcontainers

```
SKENARIO A: OVER-MOCKING (FALSE SENSE OF SECURITY)
[ Test Case ] ──▶ [ Mock DB Client ] ──(Selalu return { id: 1 })──▶ [ Assertion PASSED ✅ ]
Kenyataan di Produksi: Query SQL memiliki sintaks error `SELEC * FORM users`!
Hasil Produksi: CRASH ERROR 500! ❌

SKENARIO B: TESTCONTAINERS (REALISTIC VERIFICATION)
[ Test Case ] ──▶ [ Container Postgres Asli ] ──▶ [ Evaluasi Engine SQL & Index ]
Jika sintaks SQL salah, Foreign Key melanggar constraint, atau Transaction Rollback gagal,
maka TEST AKAN GAGAL SEKETIKA DI PIPELINE CI/CD! ✅
```

---

## 9. Simple Example: Unit Test dengan Mocking Logika Bisnis

```javascript
// Service Logika Bisnis: OrderService.js
class OrderService {
  constructor(taxCalculator, paymentGateway) {
    this.taxCalculator = taxCalculator;
    this.paymentGateway = paymentGateway;
  }

  async processOrder(amount, countryCode) {
    if (amount <= 0) throw new Error('Nilai pesanan tidak valid');

    const tax = this.taxCalculator.calculateTax(amount, countryCode);
    const total = amount + tax;

    const chargeResult = await this.paymentGateway.charge(total);
    return { success: true, chargeId: chargeResult.id, totalPaid: total };
  }
}

// Pengujian Unit Test (Menggunakan Spy & Stub):
async function testProcessOrderSuccess() {
  // Stub tax calculator (Jawaban statis)
  const fakeTaxCalculator = {
    calculateTax: (amt, code) => (code === 'ID' ? amt * 0.11 : 0)
  };

  // Mock / Spy payment gateway (Mencatat pemanggilan)
  let capturedTotal = null;
  const mockPaymentGateway = {
    charge: async (totalAmount) => {
      capturedTotal = totalAmount;
      return { id: 'CHG-9988' };
    }
  };

  const service = new OrderService(fakeTaxCalculator, mockPaymentGateway);
  const result = await service.processOrder(100000, 'ID');

  // Assertions
  console.assert(result.success === true, 'Harus sukses');
  console.assert(result.totalPaid === 110000, 'Total harus include PPN 11%');
  console.assert(capturedTotal === 110000, 'Gateway harus ditagih 110000');
  console.log('✅ testProcessOrderSuccess PASSED!');
}
```

---

## 10. Practical Example: Integration Test dengan Testcontainers (Node.js)

```javascript
const { GenericContainer } = require('testcontainers');
const { Client } = require('pg');

describe('UserRepository Integration Test with Real Postgres', () => {
  let container;
  let pgClient;

  beforeAll(async () => {
    // 1. Jalankan container Postgres ephemeral di Docker
    container = await new GenericContainer('postgres:16-alpine')
      .withEnvironment({ POSTGRES_DB: 'testdb', POSTGRES_PASSWORD: 'testpassword' })
      .withExposedPorts(5432)
      .start();

    // 2. Hubungkan client ke random port yang dipetakan
    pgClient = new Client({
      host: container.getHost(),
      port: container.getMappedPort(5432),
      database: 'testdb',
      user: 'postgres',
      password: 'testpassword'
    });
    await pgClient.connect();

    // 3. Terapkan DDL migration
    await pgClient.query(`
      CREATE TABLE users (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        balance INT DEFAULT 0
      );
    `);
  }, 30000);

  afterAll(async () => {
    await pgClient.end();
    await container.stop(); // Hancurkan container setelah test selesai
  });

  test('Harus menolak duplikasi email berdasarkan Database Constraint', async () => {
    await pgClient.query("INSERT INTO users (email, balance) VALUES ('test@corp.com', 50000)");

    // Uji constraint UNIQUE riil di level database engine
    await expect(
      pgClient.query("INSERT INTO users (email, balance) VALUES ('test@corp.com', 75000)")
    ).rejects.toThrow(/duplicate key value violates unique constraint/);
  });
});
```

---

## 11. Real World Example: Migrasi Microservices Tanpa Downtime dengan Contract Testing

Sebuah bank digital memisahkan Core Banking menjadi 30 microservices independen:
- Setiap kali tim *TransferService* ingin memodifikasi format payload API yang dikonsumsi oleh *MobileBFF*, mereka tidak perlu melakukan meeting koordinasi manual berhari-hari.
- Tim *MobileBFF* cukup memperbarui file spesifikasi **Pact Contract** dan mendorongnya ke **Pact Broker**.
- Pipeline CI/CD *TransferService* otomatis menjalankan pengujian verifikasi kontrak (`pact-provider-verifier`). Jika ada perubahan yang merusak (*Breaking Changes*), sistem CI/CD akan memblokir proses merging dengan peringatan:
  `CANNOT MERGE: Provider breaks contract with MobileBFF on endpoint POST /v1/transfers`.

Hasil: Nol insiden API breaking changes selama 2 tahun operasional perbankan live.

---

## 12. Trade-offs

| Strategi Pengujian | Kecepatan Eksekusi | Keandalan Deteksi Bug | Biaya Pemeliharaan | Kebutuhan Lingkungan |
|---|---|---|---|---|
| **Unit Testing murni** | Sangat Cepat (< 1 detik) | Rendah untuk integrasi sistem | Rendah | Hanya butuh runtime bahasa |
| **Integration Test (Mocked DB)**| Cepat (1 - 3 detik) | Menengah (Bisa menyembunyikan bug SQL) | Menengah | Hanya butuh runtime bahasa |
| **Integration Test (Testcontainers)**| Menengah (~10 - 30 detik) | **Sangat Tinggi** (Menguji engine DB asli) | Menengah | Butuh Docker Daemon aktif di mesin CI |
| **End-to-End (E2E Test)**| Sangat Lambat (5 - 30 menit)| Sangat Tinggi (namun rentan *flaky*)| Sangat Tinggi | Butuh seluruh kluster service aktif |
| **Contract Testing (Pact)**| Cepat (2 - 5 detik)| Sangat Tinggi untuk antarmuka API | Rendah ke Menengah | Butuh Pact Broker untuk sinkronisasi |

---

## 13. When To Use
- **Unit Testing:** Wajib untuk seluruh logika domain bisnis, kalkulasi finansial, validasi data, parsing format, dan transformasi data.
- **Testcontainers:** Wajib digunakan pada Repository Layer pengujian database (Postgres, MySQL, MongoDB), caching Redis, dan pub/sub message broker (Kafka, RabbitMQ) untuk memastikan query SQL dan transaksi berjalan semestinya.
- **Contract Testing:** Wajib digunakan dalam arsitektur microservices terdistribusi multi-tim di mana service penyedia (*Provider*) dan konsumen (*Consumer*) dikembangkan secara independen oleh tim yang berbeda.

---

## 14. When NOT To Use
- **Jangan Gunakan Testcontainers untuk Unit Testing Sederhana:** Menyalakan container database Docker hanya untuk menguji fungsi regex validasi email akan membuat test suite Anda menjadi sangat lambat tanpa manfaat yang sepadan.
- **Jangan Menggantungkan Kualitas Sistem Hanya pada E2E Testing:** Mengabaikan unit dan integration test lalu hanya mengandalkan 50 skenario Selenium/Playwright E2E akan membuat siklus deployment lambat dan tim frustrasi menghadapi kegagalan acak akibat network latency.

---

## 15. Common Mistakes
1. **Testing Implementation Details, Bukan Behavior:** Menulis unit test yang meng-assert berapa kali fungsi private internal dipanggil, alih-alih menguji output nilai akhir. Akibatnya, setiap kali kode di-refactor tanpa mengubah perilaku, seluruh unit test langsung rusak.
2. **Database Test yang Berbagi State (*Polluted State*):** Menjalankan integration test berurutan tanpa membersihkan data tabel antar test case. Test B gagal karena ada data sisa yang ditinggalkan oleh Test A.
3. **Flaky Tests Dibiarkan:** Membiarkan test yang kadang lulus dan kadang gagal karena race condition atau timer `setTimeout`. Tim akan mulai mengabaikan hasil test (*Alert Fatigue*) dan membiarkan bug nyata lolos ke produksi.
4. **Mocking Hal yang Bukan Milik Anda (*Mocking What You Don't Own*):** Menulis mock rumit untuk library eksternal pihak ketiga (seperti SDK Stripe atau AWS S3) tanpa pernah memvalidasi apakah perilaku mock tersebut masih sesuai dengan API asli vendor.

---

## 16. Best Practices

### Must Have
- Terapkan struktur pengujian standar: **Arrange-Act-Assert (AAA)** atau **Given-When-Then**.
- Jalankan test database dalam isolasi atomik: Bungkus setiap pengujian dalam transaksi SQL dan lakukan **Rollback** di akhir setiap test case, atau gunakan database baru di Testcontainers.
- Pastikan seluruh pengujian unit dapat berjalan secara **Deterministik & Paralel** tanpa ketergantungan urutan eksekusi (*Independent Test Cases*).

### Recommended
- Pantau metrik cakupan pengujian (**Code Coverage**), namun prioritaskan **Branch Coverage** dan **Mutation Testing** alih-alih sekadar mengejar angka 100% line coverage yang semu.
- Buat factory builder (*Test Data Builders / Fixtures*) untuk mempermudah pembuatan entitas data uji yang realistis.

### Advanced
- Integrasikan **Pact Contract Testing** ke dalam pipeline pull request (PR) GitHub Actions untuk menghentikan breaking changes secara otomatis.

---

## 17. Troubleshooting

| Gejala Masalah | Indikasi Akar Masalah | Langkah Investigasi | Tindakan Perbaikan |
|---|---|---|---|
| **Testcontainers Error: `Could not connect to Docker Daemon`** | Docker Desktop tidak berjalan di mesin developer atau Docker socket tidak dimount di runner CI | Periksa output `docker ps` di terminal | Jalankan Docker service atau mount `/var/run/docker.sock` pada container runner CI |
| **Integration Test Sangat Lambat (Menit ke Jam)** | Container Docker di-start ulang pada setiap satu test function (*Per-test container creation*) | Cek siklus `beforeEach` vs `beforeAll` | Gunakan pola *Shared Container Instance* (`beforeAll`) dan bersihkan data antar test dengan `TRUNCATE` |
| **Pact Verification Gagal di Provider** | Provider mengubah nama field JSON atau tipe data tanpa persetujuan consumer | Periksa file pact diff di Pact Broker dashboard | Selaraskan kontrak, buat versi API baru (v2) jika perlu perubahan format |

---

## 18. Exercise
1. Rancang unit test suite murni di Node.js untuk modul validasi dan otorisasi peran pengguna.
2. Implementasikan simulator Fake Database in-memory yang menguji operasi create, read, update, dan delete (CRUD).
3. Buat test case yang membuktikan kegagalan operasi jika saldo rekening bernilai negatif.

---

## 19. Challenge
Rancang arsitektur Consumer-Driven Contract Testing untuk ekosistem E-Commerce Microservices:
1. Konsumen: *OrderService* dan *MobileBFF*.
2. Penyedia: *PaymentService*.
3. Definisikan file kontrak Pact yang memuat skenario sukses (HTTP 201), saldo tidak cukup (HTTP 422), dan pemeliharaan gateway bank (HTTP 503).
4. Rancang alur verifikasi otomatis di pipeline CI/CD GitHub Actions menggunakan perintah `can-i-deploy`!

---

## 20. Summary
Pengujian bukanlah penghambat kecepatan pengembangan, melainkan sabuk pengaman yang memungkinkan tim bergerak secepat kilat. Dengan mematuhi proporsi Piramida Pengujian, memanfaatkan Testcontainers untuk validasi dependensi riil yang bebas dari ilusi over-mocking, serta menjaga keutuhan antarmuka microservices via Contract Testing, sistem backend Anda akan memiliki fondasi kualitas yang kokoh dan siap menghadapi evolusi jangka panjang.

---
[⬅️ BAB 08 Quiz & Challenge](../BAB-08-Autentikasi-Otorisasi-dan-Keamanan-Backend/BAB-08-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Static Analysis, CI/CD, & Load Testing ➡️](./Module-02-Static-Analysis-CICD-Automation-dan-Load-Testing.md)
---
