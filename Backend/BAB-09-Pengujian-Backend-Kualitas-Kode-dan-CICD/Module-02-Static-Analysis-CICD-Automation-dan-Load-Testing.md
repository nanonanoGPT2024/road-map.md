---
[⬅️ Module 01: Piramida Testing & Testcontainers](./Module-01-Piramida-Testing-Integration-Testcontainers-Contract.md) | [📋 Silabus Induk](../README.md) | [BAB 09 Quiz & Challenge ➡️](./BAB-09-Quiz-dan-Challenge.md)
---

# Module 02: Static Analysis, CI/CD Automation, & Load Testing (p99 Latency)

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Mengintegrasikan analisis kode statis (**Static Code Analysis**) dan linter untuk mengukur *Cyclomatic Complexity* dan mencegah *Technical Debt*.
- Menerapkan pemindaian keamanan otomatis dalam rantai pasok software (**DevSecOps**): **SAST** (Semgrep), **SCA / Dependency Check** (Trivy/Snyk), dan **Secret Scanning** (Gitleaks).
- Merancang pipeline **CI/CD Automation** menggunakan **GitHub Actions** dengan tahapan bertingkat (*Lint -> Test -> Build -> Scan -> Deploy*).
- Menguasai metodologi pengujian beban (**Load Testing**) menggunakan alat modern (**k6** / Locust).
- Memahami mengapa nilai rata-rata (*Average Latency*) adalah metrik yang menipu dan menganalisis distribusi persentil latensi: **p50 (Median)**, **p95**, dan **p99 (Tail Latency)**.
- Mengidentifikasi perbedaan pola uji: **Stress Testing**, **Spike Testing**, dan **Soak / Endurance Testing** (mendeteksi kebocoran memori).

---

## 2. Prerequisite
- Memahami konsep dasar Unit dan Integration Testing (Modul 01).
- Pemahaman siklus proses OS, Garbage Collection, dan memori leaks (BAB 02).
- Dasar sintaks YAML untuk konfigurasi pipeline automasi.

---

## 3. Concept
Menulis kode yang fungsional di laptop lokal pengembang hanyalah 20% dari siklus hidup rekayasa backend modern. 80% sisanya adalah memastikan kode tersebut:
1. Memenuhi standar kualitas dan bebas dari celah keamanan sebelum digabungkan ke branch utama (*Continuous Integration*).
2. Dapat dibangun dan dirilis secara otomatis tanpa campur tangan manusia yang rawan salah (*Continuous Delivery / Deployment*).
3. Terbukti mampu menahan beban ribuan pengguna simultan di bawah batas toleransi latensi yang ketat (**SLA / Service Level Agreement**).

Performa backend tidak dinilai saat sistem dalam kondisi santai (1 user), melainkan saat sistem berada di bawah tekanan puncak ratusan ribu request per detik.

---

## 4. Why?
Tanpa CI/CD terotomasi dan Load Testing:
1. **The Dangerous Average (Rata-rata Menipu):** Dashboard menampilkan rata-rata latensi API adalah 80 ms (terlihat hijau/bagus). Namun ternyata 1% pengguna terkaya (pembeli VIP yang memiliki ribuan item di keranjang belanja) mengalami latensi **12 detik** (**p99 Tail Latency**), memicu churn pelanggan bernilai tinggi.
2. **Memory Leak Lolos ke Produksi:** Service lulus semua unit test, namun saat dijalankan di produksi selama 3 hari berturut-turut, penggunaan RAM merayap naik perlahan hingga akhirnya crash (*Out-Of-Memory*). Ini hanya bisa terdeteksi via **Soak Testing**.
3. **Kredensial Rahasia Bocor ke Publik:** Pengembang secara tidak sengaja meng-commit API Key AWS atau private key ke GitHub public repository tanpa ada automated secret scanner yang mencegatnya.
4. **Deploy Manual yang Rawan Bencana:** Deployment dilakukan via SSH manual `git pull && npm restart` di server produksi jam 2 pagi. Satu kesalahan ketik perintah dapat mematikan seluruh sistem perbankan.

---

## 5. What? (Spektrum DevSecOps & Metrik Latensi)

### A. Triad Pemindaian Keamanan DevSecOps
- **SAST (Static Application Security Testing):** Memindai kode sumber mentah (Source Code) untuk menemukan pola kerentanan umum seperti SQL Injection, XSS, dan hardcoded secrets (contoh: Semgrep, SonarQube).
- **SCA (Software Composition Analysis):** Memeriksa pohon dependensi eksternal (libraries `package.json`, `pom.xml`, `go.mod`) terhadap database kerentanan publik CVE (contoh: Snyk, Trivy, Dependabot).
- **DAST (Dynamic Application Security Testing):** Menguji aplikasi yang sedang berjalan dari luar seperti peretas sungguhan tanpa mengetahui kode sumber internal (contoh: OWASP ZAP).

### B. Anatomi Metrik Latensi: Mengapa Rata-Rata Menipu?
Bayangkan 100 request diproses oleh sistem backend:
- 98 request selesai dalam **10 ms**.
- 2 request terhambat garbage collection dan memakan waktu **5.000 ms** (5 detik).
- **Rata-rata (Mean):** $\frac{(98 \times 10) + (2 \times 5000)}{100} = \frac{10980}{100} = \mathbf{109.8 \text{ ms}}$ (Tampak sangat wajar dan cepat!).
- **Kenyataan:**
  - **p50 (Median):** 10 ms (50% user merasakan 10 ms).
  - **p95:** 10 ms (95% user merasakan 10 ms).
  - **p99:** **5.000 ms** (1 dari 100 user menunggu 5 detik!).
Dalam arsitektur microservices dengan 20 panggilan service per halaman, probabilitas seorang pengguna terkena latensi p99 melonjak drastis hingga $> 18\%$!

---

## 6. How? (Arsitektur Pipeline CI/CD GitHub Actions)

```
[ Git Push / Pull Request ]
            │
            ▼
 ┌────────────────────────────────────────────────────────┐
 │ JOB 1: LINT & STATIC ANALYSIS (Fast Feedback ~1 min)   │
 │ - ESLint / Biome / SonarQube                           │
 │ - Gitleaks (Secret Scanning)                           │
 └──────────────────────────┬─────────────────────────────┘
                            │ (Lulus)
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │ JOB 2: SECURITY SCA & UNIT TESTS (~2 min)             │
 │ - Trivy / Snyk Dependency Vulnerability Scan           │
 │ - Jest / PyTest Unit Tests with Coverage Report        │
 └──────────────────────────┬─────────────────────────────┘
                            │ (Lulus)
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │ JOB 3: INTEGRATION TESTS WITH DOCKER (~4 min)          │
 │ - Testcontainers Postgres & Redis Spin-up              │
 │ - Pact Contract Verification                           │
 └──────────────────────────┬─────────────────────────────┘
                            │ (Lulus)
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │ JOB 4: BUILD, CONTAINERIZE & PUBLISH (~3 min)          │
 │ - Multi-stage Docker Build (Distroless Image)          │
 │ - Push to GitHub Container Registry (ghcr.io)          │
 └──────────────────────────┬─────────────────────────────┘
                            │ (Merge to main)
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │ JOB 5: CONTINUOUS DEPLOYMENT (GitOps)                  │
 │ - Update Kubernetes Manifests / ArgoCD Sync            │
 └────────────────────────────────────────────────────────┘
```

---

## 7. Analogy
- **Average Latency ibarat Kedalaman Rata-rata Sungai:** Rata-rata kedalaman sungai adalah 1 meter. Apakah Anda berani menyeberanginya jika Anda tidak bisa berenang? Tentu tidak! Di tengah sungai terdapat palung sedalam 10 meter (**p99 Tail Latency**). Anda akan tenggelam jika hanya mempercayai angka rata-rata!
- **CI/CD Pipeline ibarat Jalur Perakitan Pabrik Mobil:** Setiap mobil yang lewat harus lolos uji ketebalan plat baja (Linter), uji emisi gas buang (SAST), uji pengereman (Unit Test), uji tabrak (Integration Test), dan uji jalan raya di sirkuit ekstrem (**Load Testing**) sebelum mobil diizinkan keluar ke jalan raya untuk dibeli konsumen.

---

## 8. Diagram: 4 Pola Pengujian Beban (Load Testing Patterns)

```
1. LOAD TESTING REGULER (Baseline SLA Verification)
   Load: Normal expected traffic (misal: 5.000 RPS konstan selama 30 menit).

2. STRESS TESTING (Mencari Breaking Point Sistem)
   Load: Ditingkatkan bertahap 1.000 -> 5.000 -> 20.000 -> 50.000 RPS hingga sistem mulai throw HTTP 500.

3. SPIKE TESTING (Simulasi Flash Sale 11.11)
   Load: 500 RPS ───Melonjak Instan dalam 2 detik───▶ 50.000 RPS ───Turun kembali ke 500 RPS.

4. SOAK / ENDURANCE TESTING (Mendeteksi Memory Leaks)
   Load: Beban moderat 70% kapasitas dijalankan NON-STOP selama 24 - 72 jam terus menerus.
```

---

## 9. Simple Example: Skrip Load Test k6 (Modern JavaScript)

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

// Konfigurasi tahapan uji beban (Ramping VUs)
export const options = {
  stages: [
    { duration: '30s', target: 50 },  // Ramp-up ke 50 Virtual Users (VUs) dalam 30 detik
    { duration: '1m', target: 50 },   // Tahan beban 50 VUs selama 1 menit
    { duration: '20s', target: 0 },   // Ramp-down kembali ke 0
  ],
  thresholds: {
    // SLA Kualitas: 99% request harus selesai di bawah 200 ms!
    http_req_duration: ['p(99)<200'],
    // Tingkat kegagalan HTTP harus di bawah 1%
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const url = 'https://api.staging.enterprise.com/api/v1/products/top-rated';
  const res = http.get(url, {
    headers: { 'Accept': 'application/json' },
  });

  // Assertion fungsional
  check(res, {
    'status is 200': (r) => r.status === 200,
    'body is not empty': (r) => r.body.length > 0,
  });

  sleep(1); // Think-time user 1 detik antar request
}
```

---

## 10. Practical Example: Workflow GitHub Actions Pipeline Lengkap

```yaml
name: Production CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  quality-gate:
    name: Code Quality & Security Gate
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Setup Node.js Runtime
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Run Linter & Static Analysis
        run: npm run lint

      - name: Scan Secrets with Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Run SAST & Security Scan (Trivy)
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'CRITICAL,HIGH'

      - name: Execute Unit & Integration Tests
        run: npm test -- --coverage

      - name: Upload Coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
```

---

## 11. Real World Example: Optimalisasi p99 Latency di Sistem Pembayaran E-Commerce

Pada audit performa backend perbankan:
- Tim menemukan bahwa saat trafik mencapai 10.000 RPS, latensi p50 bernilai 15 ms, namun latensi **p99 melonjak ke 4.200 ms** (4,2 detik).
- Investigasi mendalam menemukan 2 akar masalah:
  1. **Garbage Collection Stop-The-World:** Aplikasi mengalokasikan ribuan objek JSON temporer berukuran besar pada setiap request, memicu Full GC pause setiap 30 detik.
  2. **Connection Pool Starvation:** Konfigurasi pool database dibatasi maksimal 20 koneksi, sehingga 1% request terakhir harus mengantre (*Queue Waiting Latency*) untuk mendapatkan koneksi DB kosong.
- Solusi:
  - Mengganti alokasi objek dinamis dengan *Object Pooling* / streaming parser.
  - Mengoptimalkan ukuran connection pool database ke angka ideal ($2 \times \text{CPU Core} + \text{Disk Spindle Count}$).
- Hasil: Latensi p99 terpangkas dari **4.200 ms menjadi 45 ms** (**penurunan 98.9%**).

---

## 12. Trade-offs

| Pendekatan Pipeline | Kecepatan Feedback | Biaya Komputasi CI | Tingkat Keyakinan Rilis |
|---|---|---|---|
| **Minimal (Hanya Lint + Unit Test)** | Super Cepat (< 2 menit) | Sangat Murah | Rendah (Banyak bug integrasi lolos) |
| **Comprehensive (Lint, SAST, SCA, Integration, Load Test)**| Sedang (8 - 15 menit) | Menengah | **Sangat Tinggi** (Hampir mustahil ada bug fatal lolos) |
| **Heavy E2E Testing di Setiap PR** | Sangat Lambat (> 45 menit) | Sangat Mahal | Menengah ke Tinggi (Sering terganggu tes *flaky*) |

---

## 13. When To Use
- **Automated Secret Scanning & SAST:** Wajib aktif pada **setiap repositori kode** sejak hari pertama proyek dimulai.
- **Percentile Latency Metrics (p95, p99):** Wajib digunakan sebagai metrik Service Level Objective (SLO) di seluruh dashboard monitoring produksi dan hasil load testing.
- **Soak Testing:** Wajib dijalankan sebelum peluncuran sistem versi besar (Major Release) untuk membuktikan tidak adanya memory leak jangka panjang.

---

## 14. When NOT To Use
- **Jangan Jalankan Load Testing Langsung ke Server Produksi Tanpa Perencanaan:** Menembakkan 50.000 RPS ke server produksi langsung tanpa isolasi dapat menghancurkan database operasional pelanggan riil dan memicu tagihan cloud raksasa. Gunakan lingkungan *Staging / Performance Sandbox* yang memiliki spesifikasi setara.
- **Jangan Block PR untuk Kerentanan Dependensi Tingkat Rendah (Low Severity):** Memblokir merger kode untuk peringatan library low severity yang tidak pernah dieksekusi di alur produksi hanya akan membuat frustrasi tim pengembang.

---

## 15. Common Mistakes
1. **Mengabaikan Persentil dan Hanya Melihat Average:** Bangga dengan rata-rata response time 50 ms padahal p99 mencapai 8 detik.
2. **Tidak Ada Caching Dependensi di CI:** Setiap kali pipeline berjalan, runner mengunduh 500 MB dependensi dari internet dari awal, membuang waktu 5 menit berharga di setiap push git.
3. **Hardcoding Kredensial di Pipeline CI:** Menulis password atau token deploy langsung di file YAML alih-alih menggunakan fitur *Encrypted Secrets* (GitHub Secrets).
4. **Load Testing dari Laptop Pengembang:** Menjalankan k6 dari satu laptop Wi-Fi untuk menguji server backend 8-core. Hasil uji menjadi tidak valid karena yang kehabisan resource dan bandwidth adalah laptop penguji, bukan server backend target!

---

## 16. Best Practices

### Must Have
- Tetapkan ambang batas kegagalan tegas (**Quality Gate**) di pipeline CI: PR tidak boleh di-merge jika linter gagal, secret ditemukan, atau unit test ada yang rusak.
- Definisikan kriteria SLA pengujian beban berdasarkan persentil: `p(99) < 200ms` dan `error_rate < 0.1%`.
- Buat file `.gitleaks.toml` untuk mencegah token API atau SSH key ter-commit secara lokal (*pre-commit hook*).

### Recommended
- Gunakan arsitektur **Branch Protection Rules** di GitHub: Wajibkan minimal 1 approval rekan tim dan kelulusan seluruh status check CI sebelum tombol merge aktif.
- Pisahkan load testing reguler (Smoke test cepat di CI) dengan load testing skala penuh (dijalankan terjadwal setiap malam).

### Advanced
- Terapkan **Canary Deployments** terotomasi: Sistem CI/CD merilis versi baru ke 5% trafik pengguna terlebih dahulu; jika metrik p99 atau error rate meningkat tajam, sistem otomatis melakukan **Rollback Instan** tanpa intervensi manusia.

---

## 17. Troubleshooting

| Gejala Masalah | Indikasi Akar Masalah | Langkah Investigasi | Tindakan Perbaikan |
|---|---|---|---|
| **Pipeline CI/CD Berjalan Sangat Lambat (> 20 Menit)** | Ketiadaan cache package manager atau docker layer caching | Periksa durasi tiap stage di log GitHub Actions | Aktifkan `actions/cache` untuk node_modules/.m2 dan gunakan Buildx layer cache |
| **Latensi p99 Melonjak Tajam di Menit ke-10 Load Test** | Memory leak atau penumpukan connection pool leak | Pantau grafik memory heap dan CPU server selama uji beban | Analisis heap memory dump dengan Chrome DevTools / v8-profiler |
| **Gitleaks Memblokir PR untuk File Dummy Test** | Secret scanner mendeteksi string acak di file unit test sebagai secret asli | Cek baris pelanggaran di laporan Gitleaks | Tambahkan path file test ke dalam file whitelist `.gitleaksignore` |

---

## 18. Exercise
1. Tulis skrip simulasi pemroses beban yang merekam latensi dari 1.000 request sintetis.
2. Hitung nilai Average (Mean), Median (p50), 95th Percentile (p95), dan 99th Percentile (p99).
3. Buktikan secara matematis bagaimana 10 request lambat di ujung spektrum dapat melipatgandakan nilai p99 tanpa banyak memengaruhi p50!

---

## 19. Challenge
Rancang arsitektur pipeline CI/CD DevSecOps komprehensif untuk aplikasi Core Banking:
1. Tahapan: Pre-commit Hook, Pull Request Quality Gate, Security Scanning (SAST + SCA + Secret Detection), Container Image Build & Cosign Digital Signing, dan Automated Canary Deployment.
2. Definisikan file konfigurasi GitHub Actions YAML lengkap dengan policy pemblokiran rilis jika ditemukan celah CVE Critical atau jika coverage branch di bawah 85%!

---

## 20. Summary
Kualitas dan keandalan sistem backend tidak tercipta secara kebetulan; keduanya adalah hasil rekayasa proses automasi yang disiplin. Dengan memadukan analisis statis, DevSecOps terotomasi, pipeline CI/CD yang cepat, serta evaluasi latensi berbasis persentil (p95/p99), seorang insinyur backend memastikan bahwa perangkat lunak yang dibangun siap melayani jutaan pengguna dengan standar keandalan tertinggi di dunia industri.

---
[⬅️ Module 01: Piramida Testing & Testcontainers](./Module-01-Piramida-Testing-Integration-Testcontainers-Contract.md) | [📋 Silabus Induk](../README.md) | [BAB 09 Quiz & Challenge ➡️](./BAB-09-Quiz-dan-Challenge.md)
---
