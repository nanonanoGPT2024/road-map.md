# MODULE 03: Ketersediaan Tinggi (High Availability), SLA, SLO, & SLI

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Menghitung durasi toleransi downtime berdasarkan aturan angka sembilan (*Nines of Availability*: 99% hingga 99.999%).
2. Membedakan secara presisi dan merancang kontrak keandalan menggunakan **SLI** (*Service Level Indicator*), **SLO** (*Service Level Objective*), dan **SLA** (*Service Level Agreement*).
3. Mengelola **Error Budget** untuk menyeimbangkan kecepatan rilis fitur baru (*innovation velocity*) dengan stabilitas sistem.
4. Menghitung **MTTF** (*Mean Time to Failure*), **MTTR** (*Mean Time to Repair*), dan **MTBF** (*Mean Time Between Failures*).
5. Membandingkan arsitektur redundansi: **Active-Passive (Cold/Warm/Hot Standby)** vs **Active-Active (Multi-Region / Multi-Zone)**.

---

## 2. Prerequisite
- Telah menyelesaikan [Module 01: Skalabilitas Vertikal vs Horizontal](./Module-01-Skalabilitas-Vertikal-vs-Horizontal.md).
- Telah menyelesaikan [Module 02: Latency, Throughput, & Trade-off Kinerja](./Module-02-Latency-Throughput-Tradeoff.md).

---

## 3. Concept
Dalam arsitektur sistem berskala besar, kegagalan (*failure*) adalah keniscayaan perangkat keras dan jaringan. Komputer akan mati, kabel fiber bawah laut akan putus, dan memori server akan mengalami *bit flip*.

**High Availability (HA)** adalah karakteristik desain sistem yang bertujuan memastikan operasional berjalan terus-menerus tanpa gangguan (*downtime*) selama periode waktu tertentu, melalui eliminasi *Single Point of Failure (SPOF)*, deteksi kegagalan otomatis, dan pengalihan beban (*automatic failover*).

---

## 4. Why? (Mengapa Memahami Ini Wajib?)

### Konsekuensi Finansial Downtime
Tingkat ketersediaan bukan sekadar angka teknis, melainkan perjanjian bisnis yang mengikat secara hukum:
- Bagi sistem perbankan atau pembayaran (seperti Stripe, Visa, atau BCA), 1 jam downtime dapat mengakibatkan denda regulasi moneter jutaan dolar dan hilangnya kepercayaan nasabah.
- Bagi AWS atau Google Cloud, melanggar batas SLA berarti harus memberikan kompensasi pengembalian dana (*service credits*) kepada ribuan pelanggan enterprise.

Namun, menaikkan ketersediaan dari 99.9% ke 99.99% atau 99.999% membutuhkan biaya infrastruktur yang naik secara eksponensial. Sebagai arsitek, Anda wajib tahu **kapan "cukup andal" itu tercapai**.

---

## 5. What? (Tabel Nines of Availability & Metrik Keandalan)

### A. The "Nines" of Availability (Tabel Downtime Maksimal)

| Nilai Availability | Deskripsi | Downtime per Tahun | Downtime per Bulan | Downtime per Hari |
|---|---|---|---|---|
| **99%** ("Two Nines") | Tidak dapat diterima untuk produksi | 3 hari, 15 jam | 7 jam, 18 menit | 14.4 menit |
| **99.9%** ("Three Nines") | Standar aplikasi web komersial umum | 8 jam, 45 menit | 43.8 menit | 1.44 menit |
| **99.95%** | Standar database production cloud | 4 jam, 22 menit | 21.9 menit | 43.2 detik |
| **99.99%** ("Four Nines") | Standar sistem finansial & enterprise | 52.6 menit | 4.38 menit | 8.64 detik |
| **99.999%** ("Five Nines") | Standar telekomunikasi & infrastruktur kritis | 5.26 menit | 26.3 detik | 0.86 detik |

### B. Segitiga Keandalan: SLI, SLO, SLA & Error Budget

```text
       +-------------------------------------------------------+
       |   SLA  (Service Level Agreement)                      |
       |   "Jika ketersediaan < 99.5%, kami mengembalikan 20%" |
       |   (Konsekuensi Legal & Finansial ke Klien Eksternal)  |
       +---------------------------+---------------------------+
                                   ▲
                                   │  Target Internal Lebih Ketat
       +---------------------------+---------------------------+
       |   SLO  (Service Level Objective)                      |
       |   "Target tim: 99.9% request sukses dalam 30 hari"    |
       |   (Tujuan Internal Engineering)                       |
       +---------------------------+---------------------------+
                                   ▲
                                   │  Metrik Riil yang Diukur
       +---------------------------+---------------------------+
       |   SLI  (Service Level Indicator)                      |
       |   SLI = (Request Sukses 2xx/3xx / Total Request) * 100|
       |   (Metrik Real-time dari Telemetri Monitoring)        |
       +-------------------------------------------------------+
```

### C. Error Budget
- **Definisi:** Ruang toleransi kegagalan yang diperbolehkan sebelum melanggar SLO.
  $$\text{Error Budget} = 100\% - \text{SLO}$$
- Jika SLO = 99.9%, maka Error Budget Anda adalah **0.1%**.
- **Prinsip Operasional SRE (Site Reliability Engineering):**
  - Selama Error Budget masih tersisa banyak: Tim developer bebas melakukan rilis fitur baru dan deployment cepat.
  - Jika Error Budget habis (terbakar akibat insiden/bug): **Rilis fitur baru dibekukan (*Feature Freeze*)**. Seluruh tim wajib fokus memperbaiki stabilitas, pengujian, dan arsitektur resiliensi.

### D. Metrik Siklus Hidup Insiden: MTTF, MTTR, MTBF

```text
|------------- MTBF (Mean Time Between Failures) -------------|
|----- MTTF (Mean Time To Failure) -----|-- MTTR (Repair) --|
[ Sistem Normal / Up ]                 [ Insiden ]         [ Recovered ]
```
$$\text{MTBF} = \text{MTTF} + \text{MTTR}$$
$$\text{Availability} = \frac{\text{MTTF}}{\text{MTTF} + \text{MTTR}} = \frac{\text{MTTF}}{\text{MTBF}}$$

> **Pelajaran Kunci Arsitek:** Untuk menaikkan availability, Anda bisa memilih: memperpanjang waktu sebelum rusak (menaikkan MTTF), ATAU **mempercepat waktu pemulihan otomatis (memangkas MTTR sekecil mungkin)**. Memangkas MTTR dengan automated health check dan failover jauh lebih murah daripada membangun hardware yang mustahil rusak!

---

## 6. How? (Pola Redundansi & Failover)

### 1. Active-Passive (Master-Standby)
Hanya satu node yang melayani traffic secara aktif. Node kedua siaga menunggu jika node pertama mengalami kegagalan.

```text
               POLA ACTIVE-PASSIVE FAILOVER

                    [ Load Balancer / DNS ]
                              │
                  ┌───────────┴───────────┐
                  ▼ (Traffic Normal)      ▼ (Siaga)
          +---------------+       +---------------+
          |  Node ACTIVE  | ~ ~ ~ |  Node PASSIVE |
          |   (Primary)   | Repl. |   (Standby)   |
          +---------------+       +---------------+
                 ▲                       │ (Heartbeat Check)
                 └────── Health Ping ────┘
```

- **Cold Standby:** Mesin cadangan dalam keadaan mati. Jika master crash, mesin baru dinyalakan dan script dijalankan (RTO lambat: 10-30 menit, biaya paling murah).
- **Warm Standby:** Mesin menyala, database tersinkronisasi berkala, namun service belum menerima traffic (RTO sedang: 1-5 menit).
- **Hot Standby:** Mesin menyala penuh, data tereplikasi secara real-time. Pengalihan switchover terjadi otomatis dalam hitungan detik (*Automatic Failover*).

### 2. Active-Active (Multi-Master / Multi-Zone)
Seluruh node secara bersamaan melayani traffic produksi.

```text
               POLA ACTIVE-ACTIVE (MULTI-ZONE)

                    [ Global Load Balancer ]
                              │
                  ┌───────────┴───────────┐
                  ▼ (50% Traffic)         ▼ (50% Traffic)
          +---------------+       +---------------+
          |  Zone A Node  | ◄───► |  Zone B Node  |
          |   (Active)    | Repl. |   (Active)    |
          +---------------+       +---------------+
```
- **Kelebihan:** Tidak ada resource yang menganggur; jika Zone A mati, Zone B langsung menyerap 100% traffic tanpa jeda.
- **Tantangan:** Membutuhkan sinkronisasi data dua arah (*bidirectional replication*) yang rentan terhadap konflik penulisan data (*write conflicts*).

---

## 7. Analogy
- **Active-Passive:** Seperti ban serep di bagasi mobil Anda. Ban serep tidak berputar saat mobil berjalan normal (pasif). Saat ban utama bocor (insiden), Anda berhenti, mengganti ban, dan mobil bisa berjalan kembali (failover).
- **Active-Active:** Seperti pesawat komersial bermesin ganda (Boeing/Airbus). Kedua mesin menyala aktif bersamaan mendorong pesawat. Jika satu mesin tiba-tiba mati di udara, satu mesin yang tersisa tetap mampu menerbangkan pesawat dengan aman sampai mendarat darurat.

---

## 8. Diagram: Fenomena Split-Brain pada Failover Otomatis

Salah satu bahaya terbesar dalam sistem High Availability adalah **Split-Brain**:

```text
    +-------------+      Kabel Jaringan Putus      +-------------+
    | Node A (DC 1| < - - - - - X - - - - - - - - >| Node B (DC 2|
    | (Primary)   |                                | (Standby)   |
    +-------------+                                +-------------+
          │                                               │
    "Saya masih hidup!                              "Node A tidak merespon!
     Saya adalah Master"                             Saya angkat diri jadi Master!"
          │                                               │
          ▼                                               ▼
   [ Menerima Write A ]                            [ Menerima Write B ]
```
**Dampak Fatal:** Terjadi inkonsistensi data parah karena kedua node bertindak sebagai Master independen yang menerima penulisan data yang saling bertentangan!  
**Solusi Arsitektural:** Membutuhkan mekanisme **Quorum (Consensus)** dengan minimal 3 node ganjil (seperti Raft/Paxos/ZooKeeper) atau STONITH (*Shoot The Other Node In The Head*).

---

## 9. Simple Example: Menghitung Downtime Bulanan
Jika aplikasi Anda memiliki target SLO **99.95%**:
1. Total menit dalam 1 bulan (30 hari) = $30 \times 24 \times 60 = 43.200 \text{ menit}$.
2. Maksimal downtime yang diperbolehkan:
   $$\text{Downtime} = 43.200 \times (1 - 0.9995) = 43.200 \times 0.0005 = 21.6 \text{ menit/bulan}$$
Jika deploy versi baru membutuhkan waktu 30 menit downtime, maka target SLO bulan tersebut langsung gagal!

---

## 10. Practical Example
Lihat script simulator kalkulator availability, SLA, dan penjejak konsumsi Error Budget pada:
`System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m03/sla_calculator.js`

---

## 11. Real World Example: Arsitektur Multi-AZ AWS & Kasus GitHub Down
- **AWS Availability Zones (AZ):** Dalam 1 region (misal: Singapore `ap-southeast-1`), AWS memiliki minimal 3 data center terpisah (AZ-a, AZ-b, AZ-c) yang berjarak puluhan kilometer tetapi terhubung dengan fiber optik latensi < 1ms. Arsitektur produksi wajib menyebarkan instance minimal di 2 AZ berbeda untuk menjamin 99.99% availability.
- **Kasus Pemadaman GitHub (2018):** Kabel optik antara data center US East dan US West putus selama 43 detik. Automated failover mencoba mempromosikan replica database di West menjadi Primary, namun sebelum transaksi selesai, kabel tersambung kembali. Hasilnya terjadi data desynchronization yang membutuhkan waktu 24 jam pemulihan manual.

---

## 12. Trade-offs (Active-Passive vs Active-Active)

| Aspek | Active-Passive (Hot Standby) | Active-Active (Multi-Zone) |
|---|---|---|
| **Pemanfaatan Resource** | Boros (50% resource idle hanya menunggu) | 100% Efisien (semua node melayani traffic) |
| **Kompleksitas Data** | Sederhana (replikasi satu arah) | Sangat Kompleks (konflik write, latensi sinkronisasi) |
| **Recovery Time (RTO)** | Ada jeda 5 - 60 detik saat failover | 0 detik (Seamless failover seketika) |
| **Risiko Split-Brain** | Rendah jika quorum diatur dengan benar | Tinggi tanpa arsitektur konsensus terdistribusi |
| **Biaya Lisensi / Cloud** | Menengah | Tinggi |

---

## 13. When To Use What
- **Gunakan Active-Passive Hot Standby:** Untuk Database Utama (PostgreSQL / MySQL). Replikasi satu arah jauh lebih aman dari risiko korupsi data transaksi keuangan.
- **Gunakan Active-Active:** Untuk Stateless Application Server, CDN Edge Server, dan NoSQL database terdistribusi multi-region (seperti Cassandra atau DynamoDB).

---

## 14. When NOT To Use
- Jangan menjanjikan **SLA 99.99%** kepada klien jika arsitektur database Anda masih berupa single-instance tanpa automated replica failover. Satu reboot maintenance OS cloud provider akan langsung melanggar batas 52 menit downtime per tahun!

---

## 15. Common Mistakes
1. **Menetapkan SLO 100%:** Kemustahilan fisik. Menetapkan ketersediaan 100% akan menghentikan seluruh rilis produk karena tim tidak berani menyentuh sistem.
2. **Tidak Menguji Skenario Failover (Chaos Engineering):** Banyak tim mengira sistem mereka High Availability, namun saat primary server benar-benar crash, script auto-failover gagal bekerja karena bug konfigurasi yang tidak pernah diuji!
3. **Mengabaikan Cascading Failure saat Failover:** Jika Node A mati dan Node B menerima 100% beban kerja secara mendadak, Node B juga akan overload dan mati, memicu pemadaman berantai total (*cascading outage*).

---

## 16. Best Practices

- **Must Have:**
  - Tetapkan SLO internal yang lebih ketat dari SLA eksternal (misal: Target internal SLO 99.95%, janji SLA ke user 99.9%).
  - Terapkan **Health Check endpoint** yang cerdas (memeriksa konektivitas database & disk, bukan hanya me-return HTTP 200 statis).
- **Recommended:**
  - Jalankan pengujian *Chaos Engineering* berkala (simulasi pemutusan node secara acak di staging/production).
  - Terapkan konsep **Graceful Degradation** (jika sistem rekomendasi mati, halaman katalog produk tetap tampil tanpa rekomendasi).
- **Advanced:**
  - Otomasi pembekuan deployment (*deployment freeze*) jika Error Budget bulan berjalan tersisa < 10%.
- **Avoid / Overengineering:**
  - Membangun arsitektur multi-cloud active-active (AWS + GCP) untuk startup tahap awal dengan beban pengguna kecil. Biaya dan kompleksitas jaringan antar-cloud akan melumpuhkan tim Anda.

---

## 17. Troubleshooting Guide
```text
Gejala: Primary Database down, tetapi Standby Node tidak otomatis naik jadi Master.
---------------------------------------------------------------------------------
Penyebab:
1. Health check timeout terlalu lama (misal 5 menit).
2. Quorum gagal tercapai (jaringan terisolasi, voting node tidak mencukupi > 50%).
3. Masalah permission/credentials replikasi pada standby node.

Solusi:
- Tuning batas ambang failover: 3 kegagalan berturut-turut dengan interval 5 detik = 15 detik trigger.
- Gunakan dedicated witness node / tie-breaker di zona ketiga.
```

---

## 18. Hands-on Lab: Menghitung Availability, Nines, & Error Budget Simulator

File lab sudah disiapkan di:
`System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m03/sla_calculator.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m03/sla_calculator.js
```

### Yang Dijalankan Script Ini:
1. Menghitung jatah toleransi downtime untuk berbagai tingkat *Nines* (99%, 99.9%, 99.95%, 99.99%).
2. Melakukan simulasi pemantauan 10.000 request dengan insiden buatan, lalu menghitung:
   - Nilai riil SLI
   - Status keberhasilan terhadap target SLO
   - Sisa persentase Error Budget yang dapat digunakan tim produk.

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Jika SLA perusahaan Anda menjanjikan 99.9% availability per bulan (30 hari):
1. Berapa menit maksimal downtime yang diperbolehkan sebelum melanggar SLA?
2. Jika server mengalami downtime 60 menit karena kegagalan jaringan, apakah SLA terlanggar?

### Level 2 (Medium):
Sebuah sistem memiliki MTTF = 720 jam (30 hari) dan MTTR = 30 menit (0.5 jam). Hitung persentase Availability sistem tersebut! Apakah sistem ini memenuhi standar "Three Nines" (99.9%)?

### Level 3 (Hard):
Jelaskan bagaimana konsep **Quorum Consensus** (formula $Q > N/2$) dapat mencegah bencana **Split-Brain** ketika sebuah cluster 3 node mengalami partisi jaringan yang memisahkan Node 1 di Zona A dengan Node 2 & 3 di Zona B!

---

## 20. Summary & Knowledge Check
- [ ] Memahami tabel toleransi waktu downtime untuk 99%, 99.9%, 99.99%, dan 99.999%.
- [ ] Memahami hierarki hubungan antara **SLI**, **SLO**, **SLA**, dan **Error Budget**.
- [ ] Memahami formula ketersediaan berbasis **MTTF** dan **MTTR**.
- [ ] Mampu membedakan strategi redundansi Active-Passive vs Active-Active beserta risiko bahaya Split-Brain.
