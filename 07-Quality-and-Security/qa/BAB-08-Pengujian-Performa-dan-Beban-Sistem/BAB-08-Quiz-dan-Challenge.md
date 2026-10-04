---
[⬅️ Module 02: k6 Scripting & Stress Testing](./Module-02-Load-Testing-Scripting-k6-Stress-Spike-Soak.md) | [📋 Silabus Induk](../README.md) | [BAB 09: BDD & Mobile Testing ➡️](../BAB-09-Pengujian-Berbasis-Perilaku-BDD-dan-Mobile/Module-01-Behavior-Driven-Development-BDD-Gherkin-Cucumber.md)
---

# BAB 08: Quiz, Evaluasi, & Practical Challenge

## 1. Chapter Summary & Evaluasi Pemahaman
Pada BAB 08, Anda telah menguasai rekayasa pengujian beban dan performa sistem modern:
1. **Taksonomi Uji Performa**: Membedakan tujuan operasional antara Load Test (beban normal), Stress Test (mencari batas hancur), Spike Test (lonjakan instan), Soak Test (uji kebocoran memori 24 jam), dan Scalability Test.
2. **Kritik Statistik Rata-rata (*The Flaw of Averages*)**: Memahami mengapa rata-rata menipu pengembang dan wajib digantikan oleh persentil ($p50, p90, p95, p99$) untuk mendeteksi latensi ekor panjang (*long-tail latency*).
3. **Hukum Little ($L = \lambda \times W$)**: Menghitung secara eksak korelasi antara konkurensi Virtual Users, throughput target, dan waktu respon sistem.
4. **Karakteristik Kurva Performa**: Mengidentifikasi titik belok kapasitas maksimal (*Knee Point*) sebelum terjadinya jurang saturasi (*Saturation Cliff*).
5. **Otomasi Grafana k6**: Menulis pengujian beban modern berbasis kode JavaScript dengan Virtual Users hemat memori, pentahapan beban (*Stages*), dan penegakan Quality Gates otomatis (*Thresholds*).
6. **Root Cause Analysis (RCA)**: Menemukan kemacetan arsitektur seperti *Database Connection Pool Exhaustion* dan *Row-Level Locking Contention*.

---

## 2. Interactive Quiz

### Bagian A: Basic Questions (Konseptual Fundamental)
1. **Pertanyaan 1**: Mengapa nilai rata-rata (*Average / Mean*) waktu respon dianggap sebagai metrik yang menyesatkan dalam pengujian performa sistem terdistribusi?
2. **Pertanyaan 2**: Apa perbedaan tujuan pengujian antara **Spike Testing** dan **Soak / Endurance Testing**?
3. **Pertanyaan 3**: Apa arti dari metrik **$p95 = 250 \text{ ms}$** dalam laporan hasil uji beban API?
4. **Pertanyaan 4**: Mengapa Grafana k6 jauh lebih hemat memori dibandingkan Apache JMeter saat mensimulasikan 10.000 Virtual Users?
5. **Pertanyaan 5**: Apa fungsi dari blok **`thresholds`** di dalam skrip konfigurasi k6 dan bagaimana perannya dalam pipeline CI/CD?

### Bagian B: Intermediate Questions (Analisis & Perhitungan)
6. **Pertanyaan 6**: Berdasarkan **Hukum Little ($L = \lambda \times W$)**: Jika sebuah API memiliki kapasitas throughput maksimal $1.200 \text{ RPS}$ dan rata-rata waktu respon adalah $50 \text{ ms}$ ($0,05 \text{ detik}$), berapakah jumlah pengguna konkuren aktif ($L$) yang sedang diproses di dalam sistem pada detik tersebut?
7. **Pertanyaan 7**: Jelaskan apa yang terjadi pada sistem ketika penambahan jumlah pengguna melewati titik **Knee Point** dan memasuki fase **Saturation Cliff**!
8. **Pertanyaan 8**: Saat uji beban berjalan dengan 1.000 VU, CPU server backend hanya tercatat 20%, namun latensi membengkak dari 50 ms menjadi 4.000 ms. Sebutkan 2 kemungkinan kemacetan arsitektur (*bottlenecks*) di lapisan database yang menyebabkan fenomena ini!
9. **Pertanyaan 9**: Mengapa menambahkan jeda waktu manusia (*Think Time* / `sleep()`) sangat penting dalam skrip uji beban, dan apa dampaknya jika think time dihilangkan?
10. **Pertanyaan 10**: Apa perbedaan antara metrik kustom bertipe **Counter** dan **Trend** di Grafana k6?

### Bagian C: Scenario-Based Questions (Problem Solving Dunia Nyata)
11. **Skenario 1**: Sebuah platform pendaftaran beasiswa nasional mengalami crash total 3 menit setelah formulir pendaftaran dibuka. Database mencatat error: `FATAL: remaining connection slots are reserved for non-replication superuser connections`. Sebagai QA Performance Engineer, pengujian beban tipe apa yang gagal dijalankan oleh tim sebelum peluncuran, dan konfigurasi apa yang harus diperbaiki?
12. **Skenario 2**: Anda menjalankan Soak Test selama 24 jam dengan beban konstan 100 VU. Di 6 jam pertama, latensi p95 stabil di 80 ms dan memori server berada di 1,5 GB. Namun pada jam ke-18, latensi naik menjadi 800 ms dan memori mencapai 7,8 GB hingga akhirnya pod mengalami crash *OOMKilled*. Cacat arsitektur apa yang berhasil Anda temukan dan apa langkah investigasi developer yang harus disarankan?
13. **Skenario 3**: Tim DevOps menolak mengizinkan pengujian beban 50.000 VU dijalankan dari laptop tester di kantor karena alasan keterbatasan bandwidth WiFi. Bagaimana solusi arsitektur pengujian beban terdistribusi (*Distributed Load Testing*) yang modern untuk memecahkan kendala ini?

---

## 3. Chapter Challenge: Perancangan Uji Beban Promo Kilat (Flash Sale 12.12) dengan k6

### Deskripsi Skenario
Sebuah aplikasi e-commerce bernama **"BeliCepat"** akan mengadakan event promo diskon 90% pukul 12:00 WIB:
- **Target Beban**: Diperkirakan 5.000 pengguna akan masuk dalam rentang 30 detik pertama.
- **Endpoint Kritis**: `POST /api/v1/orders/checkout`
- **SLA Performa yang Disepakati**:
  - 95% request wajib selesai di bawah 350 ms ($p95 < 350 \text{ ms}$).
  - 99% request wajib selesai di bawah 800 ms ($p99 < 800 \text{ ms}$).
  - Angka kegagalan request (*Error Rate*) wajib di bawah 1% (`rate < 0.01`).

### Tugas Anda (Deliverables):
1. **Perhitungan Kapasitas Menggunakan Hukum Little**:
   Jika target throughput adalah 2.500 RPS dengan toleransi waktu respon rata-rata 100 ms (0,1 detik), hitung jumlah Virtual Users (VU) yang wajib dikonfigurasi di k6.
2. **Skrip Lengkap Grafana k6 (`flash_sale_spike.js`)**:
   - Tuliskan skrip k6 lengkap dengan 4 stages (Warm-up 100 VU, Spike 2.500 VU, Sustained Load, Cooldown).
   - Tuliskan blok `thresholds` untuk $p95$, $p99$, dan `http_req_failed`.
   - Tambahkan verifikasi `check(res, { 'status 201 Created': (r) => r.status === 201 })`.
   - Tambahkan think time acak antara 1 hingga 2 detik per iterasi.
3. **Panduan Root Cause Analysis (RCA)**:
   Susun dokumen panduan langkah demi langkah jika ambang batas p95 terlanggar di CI/CD (pemeriksaan CPU, memory leak, pool database, dan lock contention).

---

## 4. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] 5 tipe pengujian performa (Load, Stress, Spike, Soak, Scalability).
- [ ] Bahaya menggunakan rata-rata (*Mean*) dan pentingnya persentil ($p50, p90, p95, p99$).
- [ ] Rumus dan penerapan Hukum Little ($L = \lambda \times W$).
- [ ] Titik Knee Point dan fase keruntuhan Saturation Cliff.
- [ ] Arsitektur Grafana k6 berbasis kode JavaScript dan Go Goroutines.
- [ ] Cara mendefinisikan Thresholds sebagai gerbang kualitas (Quality Gates).

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh formula integral matematika distribusi Poisson antrean M/M/1.
- [ ] Sintaks konfigurasi XML Apache JMeter lawas.

### Saya Harus Bisa Melakukan:
- [ ] Menulis skrip k6 dengan tahapan beban bertahap (Stages).
- [ ] Mengonfigurasi quality gates untuk memblokir deployment di CI/CD saat performa turun.
- [ ] Menganalisis grafik metrik sistem server saat latensi membengkak.

---
[⬅️ Module 02: k6 Scripting & Stress Testing](./Module-02-Load-Testing-Scripting-k6-Stress-Spike-Soak.md) | [📋 Silabus Induk](../README.md) | [BAB 09: BDD & Mobile Testing ➡️](../BAB-09-Pengujian-Berbasis-Perilaku-BDD-dan-Mobile/Module-01-Behavior-Driven-Development-BDD-Gherkin-Cucumber.md)
---
