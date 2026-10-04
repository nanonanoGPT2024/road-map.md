---
[⬅️ Module 02: Static Analysis, CI/CD, & Load Testing](./Module-02-Static-Analysis-CICD-Automation-dan-Load-Testing.md) | [📋 Silabus Induk](../README.md) | [BAB 10: Arsitektur Backend Lanjutan ➡️](../BAB-10-Arsitektur-Backend-Lanjutan-dan-Skalabilitas-Sistem/Module-01-Monolith-Modular-Microservices-dan-DDD.md)
---

# BAB 09: Evaluasi Pemahaman, Quiz, & Tantangan Kualitas Kode, Testing, & CI/CD

Selamat! Anda telah menuntaskan **BAB 09: Pengujian Backend, Kualitas Kode, & CI/CD Automation**. Dokumen evaluasi ini menguji kompetensi Anda dalam menerapkan strategi piramida pengujian, mengoperasikan Testcontainers, merancang pipeline DevSecOps otomatis, serta menganalisis metrik beban skala tinggi.

---

## 1. Pertanyaan Konseptual Fundamental (Basic)

1. **Jelaskan proporsi ideal Piramida Pengujian (Test Pyramid)!** Mengapa memiliki 90% E2E test dan hanya 10% unit test (antipattern "Ice Cream Cone") dianggap sebagai malapetaka bagi produktivitas tim pengembang?
2. **Apa perbedaan mendasar antara Stub, Mock, dan Spy dalam taksonomi Test Doubles menurut Martin Fowler?**
3. **Mengapa nilai rata-rata (Average / Mean Latency) disebut sebagai "Metrik Paling Menipu" dalam pengujian beban?** Apa keunggulan analisis persentil **p95** dan **p99 (Tail Latency)**?
4. **Apa yang membedakan SAST (Static Application Security Testing) dan SCA (Software Composition Analysis)?** Berikan contoh tool open-source untuk masing-masing kategori tersebut!
5. **Mengapa pendekatan Testcontainers jauh lebih unggul dibandingkan melakukan mock pada client database SQL (`db.query.mockResolvedValue`) saat menguji Repository Layer?**

---

## 2. Pertanyaan Analisis & Rekayasa Sistem (Intermediate)

6. **Consumer-Driven Contract Testing dengan Pact:**
   Bagaimana alur kerja Pact mencegah *Breaking Changes* antar microservices tanpa mengharuskan kedua service berjalan bersamaan di lingkungan pengujian?
7. **Isolasi Database pada Pengujian Paralel:**
   Jika Anda menjalankan 50 integration test case secara bersamaan di CI/CD, bagaimana Anda memastikan tidak terjadi bentrokan data (*State Pollution*) antar test yang mengakses tabel yang sama? Bandingkan pendekatan *Database Transactions with Auto-Rollback* vs *Database-per-Worker*!
8. **Analisis Spike Testing vs Soak Testing:**
   - Skenario apa dalam bisnis e-commerce yang paling tepat diuji dengan **Spike Testing**?
   - Mengapa **Soak Testing (Endurance Testing)** selama 24 jam adalah satu-satunya cara efektif untuk mendeteksi *Slow Memory Leaks* dan *Connection Pool Starvation*?
9. **DevSecOps Secret Scanning:**
   Jika sebuah tool scanner seperti Gitleaks mendeteksi API Key yang ter-commit ke dalam repositori git privat perusahaan, tindakan pencegahan darurat apa yang harus dilakukan além dari sekadar menghapus baris commit dari riwayat git?
10. **Branch Protection & Quality Gates:**
    Rancang aturan Quality Gate pada GitHub Actions yang memblokir proses penggabungan kode (*Merging Pull Request*) jika salah satu dari 4 kondisi ini dilanggar: linter error, secret bocor, branch coverage di bawah 80%, atau ada pengujian yang gagal!

---

## 3. Studi Kasus Skenario Produksi (Scenario-Based)

### Skenario A: "Semua Test Hijau, Tapi Produksi Crash!"
Sebuah tim backend merilis fitur baru kalkulasi pajak transaksi. Di pipeline CI/CD, 200 unit test lulus 100% (*All Green*). Namun begitu di-deploy ke server produksi, aplikasi langsung melempar error 500 fatal:
`PostgresError: column "tax_exemption_code" does not exist in table "invoices"`.
- **Analisis Akar Masalah:** Mengapa unit test tidak mampu mendeteksi ketiadaan kolom database ini?
- **Remediasi:** Bagaimana integrasi **Testcontainers** pada lapisan repository test dapat mendeteksi ketidakcocokan skema migrasi database ini sebelum kode di-deploy?

### Skenario B: Misteri Kelambatan p99 saat Flash Sale
Platform streaming video mengadakan acara konser virtual. Metrik monitoring Datadog menunjukkan rata-rata latensi API adalah 45 ms. Namun, ada 5.000 pengguna premium yang membanjiri call center komplain karena video mereka macet selama 6 detik saat proses otorisasi tiket masuk.
- **Investigasi:** Metrik persentil apa yang harus diperiksa tim SRE untuk mengungkap kasus ini?
- **Penyebab:** Jelaskan bagaimana *Garbage Collection Full STW Pause* atau antrean *Database Connection Pool* dapat menciptakan jurang pemisah raksasa antara latensi p50 (45 ms) dan p99 (6.000 ms)!

### Skenario C: Pipeline CI/CD yang Terlalu Lambat
Waktu eksekusi pipeline CI/CD GitHub Actions melonjak dari 4 menit menjadi 38 menit setelah tim menambahkan 500 integration test dan E2E test. Para developer mulai malas membuat Pull Request kecil dan menggabungkan banyak fitur sekaligus (*Giant Pull Requests*), menurunkan kualitas kode secara drastis.
- **Strategi Optimasi Pipeline:** Rancang 4 langkah konkret untuk memangkas durasi pipeline kembali ke $< 6 \text{ menit}$ (petunjuk: caching dependensi, docker layer caching, test sharding/parallelization, dan pemisahan nightly test suites)!

---

## 4. Chapter Challenge: Desain Enterprise DevSecOps & Automated Performance Pipeline

### Deskripsi Masalah
Sebagai Principal Quality & Platform Architect, Anda diminta menyusun cetak biru (*Blueprint*) pipeline kualitas untuk aplikasi Payment Gateway:
1. **Fase 1 - Pre-Merge Validation (PR Gate):**
   - Linting & Code Formatter (ESLint / Biome).
   - Secret Detection (Gitleaks).
   - SAST Security Scan (Semgrep).
   - Unit Testing dengan ambang batas minimal 80% Branch Coverage.
   - Integration Testing menggunakan Testcontainers (PostgreSQL 16 & Redis 7).
   - Durasi total fase ini wajib $< 5 \text{ menit}$.
2. **Fase 2 - Post-Merge & Artifact Creation:**
   - Multi-stage Docker Build (Distroless minimal image).
   - Container Vulnerability Scan (Trivy) yang memblokir build jika ada CVE bernilai Critical.
   - Signing container image menggunakan Cosign.
3. **Fase 3 - Staging Performance Benchmark:**
   - Menjalankan skrip k6 Load Test otomatis untuk memvalidasi SLA: Throughput $\ge 2.000 \text{ RPS}$, Latensi $p(99) < 150 \text{ ms}$, dan Error Rate $< 0.05\%$.

### Instruksi Pengerjaan
Buat laporan arsitektur pengujian yang memuat:
1. Diagram alur pipeline CI/CD dari Pull Request hingga Staging Canary.
2. File konfigurasi GitHub Actions `.github/workflows/ci.yml` lengkap.
3. Skrip konfigurasi k6 load test yang memvalidasi ambang batas SLA persentil di atas.

---

## 5. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Proporsi ideal Piramida Pengujian dan bahaya ilusi keamanan dari over-mocking.
- [ ] Perbedaan fungsi Dummy, Stub, Spy, Mock, dan Fake dalam penulisan test.
- [ ] Prinsip kerja Testcontainers dalam mengotomatisasi siklus hidup container Docker saat pengujian.
- [ ] Konsep Consumer-Driven Contract Testing (Pact) untuk keharmonisan antar-microservices.
- [ ] Mengapa analisis persentil (p50, p95, p99) wajib digunakan menggantikan rata-rata dalam evaluasi performa.
- [ ] Tahapan otomatisasi DevSecOps: SAST, SCA, Secret Scanning, dan DAST.

### Saya Tidak Perlu Menghafal:
- Seluruh ratusan opsi flag baris perintah CLI Trivy atau k6.
- Rincian format biner file dump V8 profiler.

### Saya Harus Bisa Melakukan:
- [ ] Menulis unit test dengan assertion yang menguji perilaku sistem (*behavior*), bukan detail implementasi.
- [ ] Menjalankan pengujian integrasi database riil menggunakan Testcontainers.
- [ ] Membaca laporan distribusi persentil latensi dan mengidentifikasi anomali *Tail Latency*.
- [ ] Merancang workflow GitHub Actions multi-tahap dengan caching dependensi dan quality gates.

---
[⬅️ Module 02: Static Analysis, CI/CD, & Load Testing](./Module-02-Static-Analysis-CICD-Automation-dan-Load-Testing.md) | [📋 Silabus Induk](../README.md) | [BAB 10: Arsitektur Backend Lanjutan ➡️](../BAB-10-Arsitektur-Backend-Lanjutan-dan-Skalabilitas-Sistem/Module-01-Monolith-Modular-Microservices-dan-DDD.md)
---
