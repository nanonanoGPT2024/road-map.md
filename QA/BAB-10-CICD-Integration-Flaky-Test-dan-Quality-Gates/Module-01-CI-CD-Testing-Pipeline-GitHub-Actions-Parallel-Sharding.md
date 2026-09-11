---
[⬅️ BAB 09: Quiz & Challenge](../BAB-09-Pengujian-Berbasis-Perilaku-BDD-dan-Mobile/BAB-09-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Flaky Tests & Quality Gates ➡️](./Module-02-Flaky-Test-Mitigation-Allure-Reporting-Quality-Gates.md)
---

# Module 01: Integrasi CI/CD: Pipeline GitHub Actions, Eksekusi Paralel, & Test Sharding

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Memahami peran **Continuous Integration & Continuous Delivery (CI/CD)** sebagai tulang punggung otomasi kualitas (*Automated Quality Assurance*) dalam siklus DevOps modern.
- Merancang alur kerja pengujian otomatis menggunakan **GitHub Actions Workflow YAML**: memicu pengujian pada event `pull_request`, `push: main`, atau `schedule` (Nightly Cron).
- Mengatasi masalah waktu eksekusi yang lambat (*Slow Pipeline Bottlenecks*) menggunakan teknik **Test Sharding & Matrix Strategy**: membagi ratusan skenario pengujian ke dalam beberapa mesin runner paralel secara simultan (misal: pecahan `--shard=1/4`, `--shard=2/4`).
- Mengoptimalkan efisiensi pipeline melalui **Dependency Caching** (npm/yarn/pip cache) dan containerized runner execution.
- Mengonfigurasi penyimpanan artefak kegagalan (**Failure Artifacts Upload**): merekam dan menyimpan screenshot layar, video rekaman browser, dan file Playwright Trace Viewer secara otomatis saat terjadi test failure di CI.

---

## 2. Prerequisite
- Memahami konsep dasar Git (commit, push, branch, pull request).
- Pemahaman eksekusi Playwright / API test runner dari BAB 04, 05, dan 06.

---

## 3. Concept
Menulis ribuan skenario pengujian otomasi tidak akan memberikan nilai bisnis jika skrip tersebut hanya tersimpan di komputer laptop seorang tester dan hanya dijalankan secara manual seminggu sekali. Dalam era pengiriman perangkat lunak cepat (*Continuous Delivery*), kode baru di-merge dan dideploy puluhan kali dalam sehari oleh puluhan developer berbeda.

**CI/CD Testing Integration** adalah proses di mana setiap baris kode baru yang diajukan dalam Pull Request (PR) secara otomatis memicu server build independen di awan (*Cloud Runner*) untuk menjalankan seluruh suite pengujian tanpa campur tangan manusia. Melalui teknik canggih **Parallel Test Sharding**, rangkaian pengujian yang sebelumnya membutuhkan waktu 60 menit dapat dipotong menjadi hanya 15 menit dengan mendistribusikan beban ke 4 mesin runner paralel secara bersamaan.

---

## 4. Why?
Mengapa integrasi CI/CD dan Test Sharding sangat krusial bagi QA?
1. **Umpan Balik Instan (Fast Feedback Loop)**: Developer mengetahui dalam waktu kurang dari 10 menit apakah kode barunya merusak fitur lain, sebelum kode tersebut di-merge ke branch utama (*Shift-Left Verification*).
2. **Menghilangkan Budaya "Bypass Testing"**: Jika pipeline CI membutuhkan waktu 2 jam, developer akan tergoda untuk melewati (*skip*) proses pengujian demi mengejar deadline. Sharding menjaga durasi pipeline tetap singkat ($< 15$ menit).
3. **Bukti Debugging Objektif**: Jika pengujian gagal di server CI tanpa monitor (*Headless Cloud*), artefak otomatis (Screenshot, Trace Viewer, dan Video) memungkinkan QA dan Developer memutar ulang detik-detik terjadinya kegagalan secara visual.

---

## 5. What?

### A. Anatomi Pipeline Pengujian CI/CD (GitHub Actions)

```text
========================================================================================
                          CI/CD AUTOMATED TESTING PIPELINE
========================================================================================

  [ DEVELOPER: Git Push / Pull Request ]
                    |
                    v
       [ TRIGGER: GitHub Actions Workflow ]
                    |
  +-----------------+-----------------+
  | STAGE 1: LINT & STATIC ANALYSIS   |  (ESLint, TypeScript Compiler: tsc --noEmit)
  +-----------------+-----------------+
                    | (Lolos: < 1 Menit)
                    v
  +-----------------+-----------------+
  | STAGE 2: FAST UNIT TESTS          |  (500 Unit Tests terisolasi: < 2 Menit)
  +-----------------+-----------------+
                    | (Lolos)
                    v
  +-----------------+-----------------+
  | STAGE 3: SHARDED E2E & API TESTS  |  (Parallel Matrix: 4 Shards x 5 Menit)
  |   - Shard 1/4: Auth & User Profile|
  |   - Shard 2/4: Catalog & Search   |
  |   - Shard 3/4: Cart & Checkout    |
  |   - Shard 4/4: Payment & Receipt  |
  +-----------------+-----------------+
                    |
         +----------+----------+
         |                     |
   (Semua Shard Pass)     (Ada Shard Gagal)
         |                     |
         v                     v
  [ STAGE 4: DEPLOY ]   [ BLOCK MERGE & UPLOAD ARTIFACTS ]
  (Deploy ke Staging)   (Upload: traces.zip, failure-screenshot.png)
```

---

### B. Konsep Test Sharding (Pecahan Mesin Paralel)
Alih-alih 1 mesin menjalankan 400 test case berurutan:
- Mesin Runner 1 (`shard 1/4`): Menjalankan test case nomor 1–100.
- Mesin Runner 2 (`shard 2/4`): Menjalankan test case nomor 101–200.
- Mesin Runner 3 (`shard 3/4`): Menjalankan test case nomor 201–300.
- Mesin Runner 4 (`shard 4/4`): Menjalankan test case nomor 301–400.

Keempat mesin berjalan **secara paralel pada waktu yang sama di cloud**. Total waktu eksekusi dipangkas hingga mendekati $\frac{1}{4}$ dari durasi aslinya!

---

## 6. How? Menulis File Konfigurasi GitHub Actions (`.github/workflows/e2e-tests.yml`)

```yaml
name: Automated E2E & Regression Suite

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 20 * * *' # Menjalankan Nightly Regression jam 03.00 WIB setiap hari

jobs:
  test:
    name: Run Tests (Shard ${{ matrix.shardIndex }}/${{ matrix.totalShards }})
    runs-on: ubuntu-latest
    timeout-minutes: 30

    # Strategi Matriks: Menjalankan 4 runner paralel secara bersamaan
    strategy:
      fail-fast: false # Biarkan shard lain tetap berjalan meskipun 1 shard gagal
      matrix:
        shardIndex: [1, 2, 3, 4]
        totalShards: [4]

    steps:
      # 1. Checkout kode sumber repository
      - name: Checkout Code
        uses: actions/checkout@v4

      # 2. Setup Node.js Environment
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm' # Caching node_modules otomatis

      # 3. Instal dependensi
      - name: Install Dependencies
        run: npm ci

      # 4. Instal binary browser Playwright (dengan caching)
      - name: Install Playwright Browsers
        run: npx playwright install --with-deps chromium

      # 5. Jalankan Pengujian dengan Sharding
      - name: Execute Sharded Playwright Tests
        run: npx playwright test --shard=${{ matrix.shardIndex }}/${{ matrix.totalShards }}

      # 6. Upload Artefak jika Terjadi Kegagalan
      - name: Upload Test Traces & Artifacts on Failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-failure-shard-${{ matrix.shardIndex }}
          path: |
            test-results/
            playwright-report/
          retention-days: 7
```

---

## 7. Analogy
Bayangkan proses pemanenan padi di ladang seluas 100 hektar:
- **Tanpa CI/CD (Manual)**: Satu orang petani memanen seluruh 100 hektar sendirian menggunakan arit manual. Pemanenan membutuhkan waktu 3 bulan (Lambat, melelahkan, rentan kesalahan manusia).
- **Dengan CI/CD & Sharding**: Anda membagi ladang menjadi 4 kuadran dan mengerahkan 4 mobil mesin pemanen otomatis secara serentak di masing-masing kuadran (*Sharding Matrix*). Seluruh 100 hektar selesai dipanen dalam waktu 1 hari.

---

## 8. Diagram

```text
========================================================================================
                          GITHUB ACTIONS SHARDING IN ACTION
========================================================================================

 [ GITHUB ACTIONS ORCHESTRATOR ]
                |
                | Membuka 4 Virtual Machine Runner Ubuntu Bersamaan di Cloud
                v
  +-------------+-------------+-------------+-------------+
  |             |             |             |             |
  v             v             v             v             v
[ RUNNER 1 ]  [ RUNNER 2 ]  [ RUNNER 3 ]  [ RUNNER 4 ]
 (Shard 1/4)   (Shard 2/4)   (Shard 3/4)   (Shard 4/4)
  100 Tests     100 Tests     100 Tests     100 Tests
  Durasi: 5m    Durasi: 5m    Durasi: 5m    Durasi: 5m
  |             |             |             |
  +-------------+-------------+-------------+
                |
                v
   [ MERGE REPORT & SUMMARY ]
  (Total Waktu Pipeline: Hanya 5 Menit! Bukan 20 Menit!)
```

---

## 9. Simple Example: Skrip Pembagian Shard Matematika Mandiri

Bagaimana Playwright atau test runner membagi daftar file test ke dalam beberapa shard?

```javascript
function getShardedFiles(allTestFiles, currentShard, totalShards) {
  // Urutkan file agar deterministik di seluruh runner
  const sortedFiles = [...allTestFiles].sort();
  
  // Ambil hanya file yang indeksnya sesuai dengan rumus modulo pecahan shard
  return sortedFiles.filter((file, index) => {
    return (index % totalShards) === (currentShard - 1);
  });
}

// Demonstrasi: 8 File Test dibagi ke 4 Shard
const files = [
  "auth.spec.js", "cart.spec.js", "checkout.spec.js", "dashboard.spec.js",
  "inventory.spec.js", "payment.spec.js", "profile.spec.js", "search.spec.js"
];

console.log("Shard 1/4:", getShardedFiles(files, 1, 4)); // ["auth.spec.js", "inventory.spec.js"]
console.log("Shard 2/4:", getShardedFiles(files, 2, 4)); // ["cart.spec.js", "payment.spec.js"]
console.log("Shard 3/4:", getShardedFiles(files, 3, 4)); // ["checkout.spec.js", "profile.spec.js"]
console.log("Shard 4/4:", getShardedFiles(files, 4, 4)); // ["dashboard.spec.js", "search.spec.js"]
```

---

## 10. Practical Example: Membuka dan Mendiagnosis Artefak Playwright Trace Viewer

Ketika sebuah shard gagal di server GitHub Actions:
1. Masuk ke halaman summary run GitHub Actions.
2. Unduh file zip dari bagian **Artifacts**: `playwright-failure-shard-2.zip`.
3. Ekstrak file dan jalankan tool penampil jejak rekaman lokal:
   ```bash
   npx playwright show-trace test-results/checkout-failure/trace.zip
   ```
4. **Antarmuka Trace Viewer akan memutar**:
   - Screenshot layar tepat pada milidetik sebelum tombol diklik.
   - Snapshot DOM HTML yang dapat diinspeksi elemennya.
   - Riwayat Network HTTP requests dan response status.
   - Log konsol browser (`console.log` dan console error).
   - Diagram timeline eksekusi aksi.

---

## 11. Real World Example: Optimalisasi Waktu Pipeline E-Commerce dari 75 Menit Menjadi 11 Menit
Sebuah unicorn e-commerce memiliki 1.400 skenario automated test:
- Pengujian berjalan sekuensial di 1 runner Jenkins, membutuhkan waktu 1 jam 15 menit di setiap Pull Request.
- Developer frustrasi dan sering menggabungkan 5 fitur sekaligus dalam 1 PR raksasa untuk menghindari antrean pipeline (*Batched PR Anti-Pattern*).
- **Transformasi QA**: Tim mengadopsi Playwright Test Sharding dengan matriks 8 runner di GitHub Actions:
  - Total waktu terpangkas dari 75 menit menjadi **11 menit**.
  - Angka commit per hari naik 300%.
  - Regresi terdeteksi seketika pada commit kecil terisolasi.

---

## 12. Trade-offs

| Pendekatan Eksekusi CI/CD | Keuntungan | Kelemahan |
|---|---|---|
| **Single Runner Sekuensial** | Gratis / Biaya cloud minimal, mudah disetup. | Sangat lambat; menjadi bottleneck utama rilis tim. |
| **Multi-Threading Lokal di 1 Runner (`workers: 4`)** | Cepat tanpa biaya mesin tambahan. | Terbatas oleh kapasitas CPU/RAM mesin runner tunggal. |
| **Multi-Machine Sharding Matrix (`--shard=1/8`)** | Paling cepat; skalabilitas waktu pengujian hampir tak terbatas. | Mengonsumsi kuota menit build cloud (GitHub Actions Minutes) lebih banyak. |

---

## 13. When To Use
- Gunakan **GitHub Actions / GitLab CI** untuk menguji setiap Pull Request secara otomatis.
- Terapkan **Test Sharding** jika durasi eksekusi seluruh automated test suite melebihi **15 menit**.
- Aktifkan **Nightly Regression Run** (jadwal cron harian) untuk menjalankan pengujian penuh termasuk skenario lambat yang tidak dijalankan pada PR harian.

## 14. When NOT To Use
- Jangan menggunakan Test Sharding jika suite Anda hanya memiliki 10 test case yang selesai dalam 30 detik (overhead membuka mesin virtual cloud justru lebih lama daripada waktu pengujiannya!).
- Jangan menjalankan pengujian yang bergantung pada state berurutan (*Order-dependent tests*) pada runner sharded; setiap shard harus berisi test yang 100% independen.

---

## 15. Common Mistakes

```text
1. MISTAKE: Opsi "fail-fast" dibiarkan bernilai true pada matrix sharding (default GitHub Actions).
   WHY IT HAPPENS: Default setting matrix mematikan seluruh job jika ada 1 job yang gagal.
   WHY IT IS BAD: Jika Shard 1 gagal di menit pertama, Shard 2, 3, dan 4 langsung dibatalkan darurat. Anda tidak tahu apakah shard lain sebenarnya aman atau memiliki bug lain.
   CORRECT APPROACH: Wajib setel "strategy: { fail-fast: false }" agar seluruh shard selesai dieksekusi dan laporan kerusakan komprehensif.

2. MISTAKE: Tidak menyimpan rekaman Trace Viewer saat test gagal di CI.
   WHY IT HAPPENS: Hanya mencetak error teks di console terminal runner.
   WHY IT IS BAD: Developer tidak bisa mereproduksi apa yang sebenarnya terlihat di layar browser cloud saat crash.
   CORRECT APPROACH: Konfigurasikan "trace: 'retain-on-failure'" dan upload folder test-results sebagai artefak.
```

---

## 16. Best Practices

### Must Have
- Melindungi branch utama (`main`) menggunakan **GitHub Branch Protection Rules**: PR wajib lulus pengujian CI (*Required Status Checks*) sebelum diizinkan di-merge.
- Memasang timeout eksplisit di setiap job GitHub Actions (`timeout-minutes: 20`) untuk mencegah tagihan cloud membengkak jika ada skrip yang mengalami loop tanpa henti.

### Recommended
- Memanfaatkan **npm cache** dan **Playwright browser cache** agar waktu booting runner berkurang dari 3 menit menjadi 30 detik.
- Menggabungkan laporan dari seluruh shard terpisah ke dalam satu dashboard HTML tunggal (*Merge HTML Reports step*).

### Advanced
- Menerapkan *Dynamic Test Sharding based on Execution Time*: Alih-alih pembagian file statis, tool otomatis membagi file berdasarkan riwayat durasi eksekusi sebelumnya sehingga setiap shard selesai pada detik yang persis sama (*Perfect Load Balancing*).

### Avoid / Overengineering
- Membuka 64 mesin shard untuk sekadar menguji 50 skenario test.

---

## 17. Troubleshooting: Gagal Menginstal Dependensi Sistem Browser di Linux Runner
Jika runner GitHub Actions Ubuntu menampilkan:
`Host system is missing dependencies to run browsers. Please run: npx playwright install-deps`
1. **Penyebab**: Browser Chromium/WebKit membutuhkan library grafik Linux native (seperti `libasound2`, `libgbm1`).
2. **Solusi**: Tambahkan flag `--with-deps` pada langkah instalasi di workflow YAML:
   `run: npx playwright install --with-deps`

---

## 18. Exercise
1. Tinjau alur kerja tim berikut: Sebuah repository memiliki 200 skenario test Playwright yang membutuhkan total waktu 40 menit jika dijalankan pada 1 mesin.
   - Jika Anda mengonfigurasi GitHub Actions Matrix Sharding dengan `totalShards: 5`, perkirakan berapa estimasi durasi waktu tunggu pipeline hingga selesai!
2. Tuliskan potongan konfigurasi GitHub Actions `steps` untuk mengunggah folder `playwright-report` sebagai artefak yang hanya dieksekusi jika pengujian berstatus gagal (`if: failure()`).

---

## 19. Challenge
Rancang sebuah dokumen **Arsitektur CI/CD Pipeline Enterprise (GitHub Actions Workflow)**:
1. Definisikan 3 jobs berurutan:
   - Job 1: `lint_and_unit` (ESLint & Jest Unit Test)
   - Job 2: `api_contract_tests` (Pact & API Integration)
   - Job 3: `e2e_sharded_web` (Playwright E2E dengan matrix 4 shards)
2. Tentukan dependency chaining: Job 3 hanya boleh berjalan jika Job 1 dan Job 2 lulus 100% (`needs: [lint_and_unit, api_contract_tests]`).
3. Tuliskan mekanisme penggabungan laporan hasil uji dari ke-4 shard menjadi satu laporan terpadu (*Summary Report Step*).

---

## 20. Summary
- Integrasi CI/CD mengotomasi eksekusi pengujian pada setiap Pull Request, memberikan umpan balik cepat dan mencegah integrasi kode rusak ke produksi.
- Test Sharding membagi beban ratusan skenario pengujian ke dalam beberapa mesin runner paralel di cloud, memangkas waktu tunggu pipeline secara drastis.
- Caching dependensi dan download browser meminimalkan overhead booting virtual machine runner.
- Penyimpanan artefak otomatis (Screenshot, Traces, Videos) saat terjadi kegagalan adalah kunci debugging instan pada lingkungan headless.

---

## Hands-on Practice: Simulator Matriks Sharding & Orkestrasi Pipeline CI/CD
Jalankan script simulator yang mendemonstrasikan algoritma pembagian shard matematis, eksekusi paralel antar-runner buatan, dan agregasi laporan hasil uji:

```bash
node QA/BAB-10-CICD-Integration-Flaky-Test-dan-Quality-Gates/hands-on/m01/cicd_test_sharding_matrix_sim.js
```

---
[⬅️ BAB 09: Quiz & Challenge](../BAB-09-Pengujian-Berbasis-Perilaku-BDD-dan-Mobile/BAB-09-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Flaky Tests & Quality Gates ➡️](./Module-02-Flaky-Test-Mitigation-Allure-Reporting-Quality-Gates.md)
---
