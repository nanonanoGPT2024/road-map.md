---
[⬅️ BAB 07: Quiz & Challenge](../BAB-07-Pengujian-Database-dan-Test-Data-Management/BAB-07-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: k6 Scripting & Stress Testing ➡️](./Module-02-Load-Testing-Scripting-k6-Stress-Spike-Soak.md)
---

# Module 01: Fondasi Performance Testing: Throughput, Latency Percentiles (p95/p99), & Hukum Little (Little's Law)

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengidentifikasi taksonomi lengkap **Performance Testing**: *Load Testing, Stress Testing, Spike Testing, Soak/Endurance Testing,* dan *Scalability Testing*.
- Menguasai metrik performa inti: **Throughput (Requests Per Second / RPS / TPS)**, **Error Rate**, **Resource Saturation (CPU, Memory, I/O)**, dan **Latency**.
- Memahami secara mendalam mengapa **Rata-rata (Average / Mean Latency) adalah Kebohongan Statistik (*The Flaw of Averages*)** dalam rekayasa sistem, dan mengapa industri wajib mengadopsi **Percentiles ($p50, p90, p95, p99$)**.
- Menerapkan **Hukum Little (Little's Law: $L = \lambda \times W$)** untuk menghitung hubungan matematis antara jumlah pengguna aktif konkuren (*Concurrent Virtual Users*), kapasitas throughput sistem, dan waktu respon.
- Mengidentifikasi kurva **Knee Point & Saturation Cliff**: titik di mana latensi membengkak secara eksponensial saat kapasitas sistem terlampaui.

---

## 2. Prerequisite
- Memahami konsep dasar protokol HTTP, request-response cycle, dan status codes dari BAB 04.
- Pengetahuan dasar tentang konsep statistik (Rata-rata, Median, Persentil).

---

## 3. Concept
Aplikasi perangkat lunak dapat lulus 100% dari pengujian fungsional saat diuji oleh 1 orang QA di laptop lokal. Namun ketika aplikasi dirilis ke publik dan diakses oleh 50.000 pengguna secara serentak pada jam sibuk, sistem tiba-tiba melambat drastis, melempar error 504 Gateway Timeout, dan akhirnya mengalami crash total.

**Performance Testing** adalah disiplin pengujian non-fungsional yang mengukur kecepatan (*speed*), stabilitas (*stability*), skalabilitas (*scalability*), dan keandalan sistem di bawah berbagai variasi beban kerja (*workload*). Melalui matematika persentil dan hukum antrean (*queueing theory*), QA Performance Engineer bertugas menemukan batas hancur sistem (*breaking point*) dan kemacetan arsitektur (*bottlenecks*) sebelum bencana terjadi di lingkungan produksi.

---

## 4. Why?
Mengapa pemahaman metrik performa dan persentil sangat penting?
1. **Rata-rata Menyembunyikan Pengalaman Pengguna Buruk**: Jika 95 pengguna mendapatkan respon 100 ms dan 5 pengguna mengalami freeze selama 10.000 ms, nilai rata-rata adalah 595 ms (tampak "cukup baik"). Padahal bagi 5% pengguna tersebut (yang biasanya adalah pengguna VIP dengan keranjang belanja terbesar), sistem dianggap rusak total.
2. **Korelasi Finansial Langsung (Amazon Metric)**: Analisis Amazon membuktikan bahwa setiap penambahan latensi sebesar 100 milidetik menurunkan penjualan e-commerce sebesar 1%.
3. **Kapasitas Perencanaan Infrastruktur (Capacity Planning)**: Mengetahui dengan pasti berapa kapasitas maksimal server Anda sebelum harus melakukan *Auto-Scaling* mesin komputasi di cloud, sehingga menghemat anggaran infrastruktur perusahaan.

---

## 5. What?

### A. Taksonomi Tipe Pengujian Performa

```text
========================================================================================
                          PERFORMANCE TESTING TAXONOMY
========================================================================================

 1. LOAD TESTING       --> Menguji sistem di bawah beban normal yang diharapkan (Expected Peak).
                           Tujuan: Memverifikasi pemenuhan SLA waktu respon.

 2. STRESS TESTING     --> Menaikkan beban melebihi kapasitas puncak hingga sistem hancur.
                           Tujuan: Menemukan titik batas maksimal (Breaking Point) & recovery.

 3. SPIKE TESTING      --> Memberikan lonjakan traffic masif secara mendadak (0 -> 10.000 VU).
                           Tujuan: Menguji ketahanan terhadap Flash Sale atau Tiket Konser.

 4. SOAK / ENDURANCE   --> Menjalankan beban sedang dalam durasi panjang (12 - 48 jam nonstop).
                           Tujuan: Menemukan kebocoran memori (Memory Leaks) & degradasi disk.

 5. SCALABILITY        --> Menambah beban bertahap sambil menambah node server (Scale-Out).
                           Tujuan: Memverifikasi apakah penambahan server menambah throughput linier.
```

---

### B. Metrik Inti: Mengapa Rata-Rata Adalah Kebohongan (*The Flaw of Averages*)

Dalam performa sistem terdistribusi, distribusi waktu respon tidak pernah berbentuk kurva normal lonceng simetris (*Gaussian*), melainkan memiliki ekor panjang (*Long Tail Latency*).

```text
========================================================================================
                          LATENCY PERCENTILE DISTRIBUTION
========================================================================================

  Frekuensi
    ^
    |  ####  <-- p50 (Median): 50% pengguna mengalami latensi <= 80ms
    |  ######
    |  ########
    |  ##########
    |  ############       <-- Rata-rata (Mean): 240ms (Terdistorsi oleh ekor!)
    |  ##############           |
    |  ################         v
    |  ####################   [p95: 350ms]      [p99 (Long Tail): 2.500ms]
    +------------------------------------------------------------------------> Latensi
                                                                            (ms)
```

- **$p50$ (Median)**: 50% dari seluruh request selesai lebih cepat dari nilai ini. Merepresentasikan pengalaman pengguna pada umumnya.
- **$p90$ / $p95$**: 90% atau 95% request selesai lebih cepat dari nilai ini. Standar industri untuk Service Level Agreement (SLA).
- **$p99$ / $p99.9$**: Hanya 1 dari 100 (atau 1 dari 1.000) pengguna yang mengalami latensi lebih buruk dari nilai ini. Sangat krusial untuk arsitektur microservices di mana satu halaman memanggil 50 API di latar belakang (probabilitas pengguna terkena p99 menjadi sangat tinggi!).

---

### C. Hukum Little (Little's Law)
Teorema antrean matematika universal yang menghubungkan 3 variabel kapasitas sistem:

$$L = \lambda \times W$$

- $L$ (*Concurrency / In-flight Requests*): Jumlah rata-rata request atau pengguna yang sedang aktif diproses secara bersamaan di dalam sistem.
- $\lambda$ (*Throughput / Arrival Rate*): Jumlah request yang diselesaikan per detik (Requests Per Second / RPS).
- $W$ (*Latency / Response Time*): Rata-rata waktu tunggu yang dibutuhkan untuk menyelesaikan satu request (dalam satuan detik).

#### Rumus Turunan untuk Menghitung Kapasitas:
$$\text{Throughput (RPS)} = \frac{\text{Jumlah Virtual Users (Concurreny)}}{\text{Waktu Respon (Detik)}}$$

*Contoh*: Jika aplikasi Anda memiliki 1.000 Virtual Users aktif bersamaan dan setiap request membutuhkan waktu rata-rata 0,5 detik (500 ms), maka throughput sistem Anda adalah:
$$\lambda = \frac{1.000}{0,5} = 2.000 \text{ RPS}$$

---

## 6. How? Kurva Knee Point & Saturation Cliff

Saat Anda menaikkan beban pengguna bertahap dalam sebuah pengujian Stress Test, sistem akan melewati 3 fase karakteristik:

```text
========================================================================================
                 PERFORMANCE CURVE: THROUGHPUT VS LATENCY KNEE POINT
========================================================================================

  Throughput |                                       / Latency Eksponensial!
     (RPS)   |                                      / (Saturation Cliff)
      ^      |                                     /
      |      |                   [KNEE POINT]     /
      |      |                         *---------*  <-- Throughput Mendatar (Max Cap)
      |      |                       / |
      |      |                      /  |
      |      |  Fase 1: Linier     /   | Fase 2: Antrean  | Fase 3: Runtuh
      |      | (Sehat & Cepat)    /    | (Mulai Mengantre)| (Crash / Error 500)
      |      |                   /     |
      +------+------------------+------+----------------------------------------> Beban (VU)
```

1. **Fase Linier (Light Load)**: Throughput naik sebanding dengan penambahan pengguna, latensi stabil dan rendah.
2. **Knee Point (Kapasitas Optimal)**: Titik belok di mana CPU/Database mencapai utilitas 80–90%. Sistem mencapai throughput maksimal.
3. **Saturation Cliff (Overload / Queueing Collapse)**: Penambahan pengguna tidak lagi meningkatkan throughput, melainkan menyebabkan antrean koneksi menumpuk (*connection pool exhausted*). Latensi meledak naik vertikal dan error 504 bermunculan.

---

## 7. Analogy
Bayangkan sebuah loket pintu tol jalan raya:
- **Throughput (RPS)**: Berapa banyak mobil yang berhasil menempelkan kartu e-toll dan melewati gerbang per menit.
- **Latency (Waktu Respon)**: Berapa detik waktu yang dibutuhkan 1 mobil dari mulai mendekati gerbang tol hingga palang pintu terbuka.
- **Knee Point**: Gerbang tol mampu melayani maksimal 30 mobil per menit. Selama mobil yang datang $\le 30$ per menit, tidak ada antrean.
- **Saturation Cliff**: Tiba-tiba datang 200 mobil per menit. Palang pintu tetap hanya bisa meloloskan 30 mobil per menit. Akibatnya, antrean kendaraan mengular sejauh 5 kilometer ke belakang (Latensi membengkak dari 3 detik menjadi 45 menit).

---

## 8. Diagram

```text
========================================================================================
                      ERROR RATE VS SATURATION RELATIONSHIP
========================================================================================

  Beban (VUs) : [ 100 ] ------> [ 500 ] ------> [ 2.000 ] ------> [ 10.000 ]
  CPU Usage   :   20%             55%              88%              100% (Throttled)
  Memory      :   1.2 GB          2.1 GB           3.8 GB           OOM Killed!
  Throughput  :   200 RPS         950 RPS          2.100 RPS        400 RPS (Macet)
  p95 Latency :   45 ms           60 ms            180 ms           8.500 ms (Timeout)
  Error Rate  :   0.0%            0.0%             0.02%            42.8% (5xx Crash)
  Status      :  [ SEHAT ]       [ OPTIMAL ]     [ WASPADA ]       [ SYSTEM FAILURE ]
```

---

## 9. Simple Example: Perhitungan Matematika Persentil Manual

Diberikan 10 data waktu respon request (dalam milidetik) yang sudah diurutkan dari terkecil ke terbesar:
`[ 40, 45, 48, 50, 52, 55, 60, 65, 200, 1500 ]`

- **Jumlah Data ($N$)**: 10
- **Rata-rata (Mean)**: $(40 + 45 + \dots + 1500) / 10 = 206,5 \text{ ms}$ (Terdistorsi parah oleh angka 1.500 ms).
- **Median ($p50$)**: Nilai tengah data ke-5 dan ke-6: $(52 + 55) / 2 = 53,5 \text{ ms}$.
- **$p90$**: Nilai data ke-$0.9 \times 10 = 9$, yaitu **$200 \text{ ms}$**.
- **$p99$**: Nilai data paling ekstrem mendekati $100\%$, yaitu **$1.500 \text{ ms}$**.

*Kesimpulan QA*: 90% pengguna menikmati respon cepat $\le 200$ ms. Namun rata-rata 206,5 ms menipu persepsi tim pengembang.

---

## 10. Practical Example: Menentukan Service Level Agreement (SLA) & Performance Budgets

Sebagai QA Performance Engineer, Anda wajib mendefinisikan *Thresholds* kriteria kelulusan uji beban:

```markdown
# Performance Quality Gate: Checkout Service API

1. [ ] Throughput SLA:
   - Sistem wajib mampu melayani minimal 1.500 RPS pada jam puncak promosi.
2. [ ] Latency SLA (Thresholds):
   - Median (p50) wajib <= 80 ms.
   - 95th Percentile (p95) wajib <= 250 ms.
   - 99th Percentile (p99) wajib <= 800 ms.
3. [ ] Reliability SLA:
   - Error Rate (HTTP 5xx / Network Timeouts) wajib < 0.05% dari total request.
4. [ ] Resource Saturation Threshold:
   - Penggunaan CPU cluster Kubernetes tidak boleh melebihi 75%.
   - Tidak boleh ada restart pod akibat Out-of-Memory (OOMKilled).
```

---

## 11. Real World Example: Kegagalan Sistem Registrasi Tiket Konser Internasional
Sebuah platform penjualan tiket konser band ternama di Jakarta diserbu 500.000 calon pembeli pada pukul 10.00 WIB:
- Sistem sebelumnya hanya diuji menggunakan *Load Test* sederhana dengan 2.000 Virtual Users konstan.
- Tim QA tidak pernah menjalankan **Spike Test** (lonjakan instan dari 0 ke 100.000 VU dalam 10 detik).
- **Dampak di Hari H**: Begitu jam 10.00 tiba, antrean koneksi ke database pool langsung penuh (*Connection Pool Exhaustion*). Server Nginx melempar error `502 Bad Gateway` kepada 90% pengunjung selama 45 menit pertama.
- **Biaya Kerugian**: Reputasi platform hancur di media sosial dan pihak promotor memutus kontrak kerja sama.

---

## 12. Trade-offs

| Metrik Performa | Keuntungan Analisis | Kelemahan Jika Dipakai Sendirian |
|---|---|---|
| **Rata-rata (Average / Mean)** | Sangat mudah dihitung dan dipahami manajemen. | Menipu dan menyembunyikan masalah latensi ekstrem (*Outliers*). |
| **Persentil ($p95 / p99$)** | Menangkap pengalaman buruk pengguna riil di ekor distribusi. | Memerlukan komputasi memori lebih besar untuk pencatatan histogram. |
| **Throughput (RPS)** | Mengukur kapasitas volume murni sistem. | RPS tinggi tidak ada artinya jika 80% responnya adalah HTTP 500 Error. |
| **Error Rate** | Mengukur keandalan dan stabilitas sistem. | Error rate 0% tidak berguna jika waktu responnya 30 detik per request. |

---

## 13. When To Use
- Gunakan **Load Testing** rutin pada setiap siklus sprint rilis untuk memverifikasi tidak ada regresi performa.
- Gunakan **Spike Testing** sebelum event kampanye belanja besar (Promo Tanggal Kembar 11.11 / 12.12).
- Gunakan **Soak Testing (24 Jam)** pada modul baru yang menggunakan teknologi cache in-memory atau koneksi database persisten guna mendeteksi *Memory Leaks*.

## 14. When NOT To Use
- Jangan menjalankan pengujian beban skala besar (Stress/Spike Test) langsung ke server produksi tanpa koordinasi resmi dengan tim DevOps, System Architect, dan penyedia Cloud (dapat memicu tagihan cloud membengkak atau dianggap serangan DDoS oleh AWS/GCP).
- Jangan melakukan uji beban jika aplikasi masih memiliki bug fungsional kritis di mana alur dasarnya saja masih sering melempar error 400.

---

## 15. Common Mistakes

```text
1. MISTAKE: Melaporkan "Rata-rata waktu respon server adalah 150ms, jadi performa aman!".
   WHY IT HAPPENS: QA menggunakan metrik rata-rata bawaan spreadsheet.
   WHY IT IS BAD: Mengabaikan p99 yang bernilai 5.000ms. Pengguna dengan transaksi bernilai besar justru mengalami timeout.
   CORRECT APPROACH: Selalu sertakan metrik p50, p90, p95, dan p99 pada setiap laporan uji performa.

2. MISTAKE: Tidak memverifikasi Error Rate saat mengukur Throughput tinggi.
   WHY IT HAPPENS: Tool load test mencatat 5.000 RPS dan tester merasa sistem sangat kencang.
   WHY IT IS BAD: Ternyata server merespon 5.000 RPS karena server langsung menolak request dengan membalas HTTP 503 dalam 1 milidetik!
   CORRECT APPROACH: Throughput hanya sah jika dihitung dari request yang berhasil (HTTP 2xx).
```

---

## 16. Best Practices

### Must Have
- Menetapkan **Performance Thresholds** wajib (p95 latency $< X$ ms, Error rate $< 0.1\%$).
- Mengisolasi environment uji beban: server aplikasi, database, dan mesin load generator wajib berada di jaringan berkecepatan tinggi agar tidak terdistorsi latensi koneksi internet rumah penguji.

### Recommended
- Menerapkan **Hukum Little** untuk menghitung estimasi jumlah Virtual Users (VU) yang realistis sebelum pengujian dimulai.
- Memantau penggunaan sumber daya server (*Server-Side Monitoring: CPU, RAM, Disk I/O, DB Connections*) secara bersamaan menggunakan Grafana / Prometheus saat uji beban berjalan.

### Advanced
- Mengintegrasikan *Automated Performance Regression Gates* ke dalam pipeline CI/CD: build ditolak jika p95 latency naik lebih dari 10% dibandingkan build rilis sebelumnya.

### Avoid / Overengineering
- Menjalankan pengujian 1.000.000 Virtual Users untuk aplikasi portal internal kantor yang penggunanya hanya 50 karyawan.

---

## 17. Troubleshooting: Mendiagnosa Kemacetan Database Connection Pool
Jika throughput mendadak anjlok dan latensi naik drastis sementara CPU server backend masih rendah (hanya 25%):
1. **Penyebab**: *Connection Pool Saturation*. Backend kehabisan slot koneksi ke database, sehingga request tertahan mengantre (*Thread Starvation*).
2. **Langkah Diagnosa**:
   - Periksa konfigurasi pool database (misal `max_connections = 100`).
   - Periksa kueri lambat di database: `SELECT * FROM pg_stat_activity WHERE state = 'active'`.
   - Naikkan batas connection pool atau implementasikan connection pooling proxy seperti PgBouncer.

---

## 18. Exercise
1. Sebuah sistem checkout e-commerce mencatat 50 waktu respon berikut saat diuji:
   - 45 request selesai dalam 50 ms.
   - 4 request selesai dalam 150 ms.
   - 1 request selesai dalam 4.000 ms.
   Hitunglah nilai:
   - Rata-rata (Mean Latency)
   - Median ($p50$)
   - 90th Percentile ($p90$)
   - 99th Percentile ($p99$)
2. Berdasarkan Hukum Little ($L = \lambda \times W$): Jika sebuah API gateway dirancang untuk menampung throughput target sebesar $5.000 \text{ RPS}$ dan rata-rata waktu respon backend adalah $200 \text{ ms}$ ($0,2 \text{ detik}$), berapakah jumlah request konkuren ($L$) yang harus mampu ditangani oleh server secara simultan?

---

## 19. Challenge
Rancang sebuah **Performance Test Plan Document** untuk layanan reservasi tiket kereta api mudik lebaran:
1. Target Kebutuhan Bisnis: Mampu melayani 20.000 pengguna bersamaan yang melakukan pencarian rute kereta secara serentak di 5 menit pertama pembukaan tiket.
2. Tentukan model pengujian yang tepat (Load vs Stress vs Spike vs Soak).
3. Susun tabel Performance Thresholds yang mencakup Throughput target, toleransi p50/p95/p99 latency, batas error rate, dan ambang batas saturasi CPU database.

---

## 20. Summary
- Performance testing menguji kecepatan, kapasitas batas, dan stabilitas sistem di bawah beban kerja riil.
- Rata-rata waktu respon adalah metrik yang menyesatkan; selalu gunakan persentil ($p50, p90, p95, p99$) untuk menangkap pengalaman pengguna di ekor distribusi (*long-tail latency*).
- Hukum Little ($L = \lambda \times W$) mendefinisikan hubungan matematis antara konkurensi pengguna, kapasitas throughput, dan waktu respon.
- Mengidentifikasi Knee Point memungkinkan tim rekayasa menetapkan batas kapasitas infrastruktur yang aman sebelum terjadi keruntuhan sistem (*saturation cliff*).

---

## Hands-on Practice: Simulator Kalkulator Persentil Latensi & Hukum Little
Jalankan script simulator yang memproses distribusi ribuan sampel waktu respon, menghitung Mean vs Median vs p95 vs p99, membuktikan distorsi rata-rata, dan mengkalkulasi Hukum Little secara otomatis:

```bash
node QA/BAB-08-Pengujian-Performa-dan-Beban-Sistem/hands-on/m01/percentile_latency_calculator_sim.js
```

---
[⬅️ BAB 07: Quiz & Challenge](../BAB-07-Pengujian-Database-dan-Test-Data-Management/BAB-07-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: k6 Scripting & Stress Testing ➡️](./Module-02-Load-Testing-Scripting-k6-Stress-Spike-Soak.md)
---
