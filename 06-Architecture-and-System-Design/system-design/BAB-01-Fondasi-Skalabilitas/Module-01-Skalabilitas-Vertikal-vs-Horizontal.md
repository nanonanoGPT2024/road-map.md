# MODULE 01: Skalabilitas Vertikal vs Horizontal & Bottleneck Sistem

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Membedakan secara arsitektural dan ekonomis antara Vertical Scaling (*Scale Up*) dan Horizontal Scaling (*Scale Out*).
2. Mengidentifikasi titik jenuh (*bottleneck*) sistem pada 4 pilar sumber daya: CPU, Memory, Disk I/O, dan Network.
3. Menjelaskan hukum Amdahl (*Amdahl's Law*) dan dampaknya terhadap penambahan resource komputasi.
4. Menerapkan transisi dari aplikasi single-instance menjadi multi-process terdistribusi menggunakan lab praktis langsung di komputer Anda.

---

## 2. Prerequisite
- Memahami konsep dasar proses (*process*) dan thread pada sistem operasi.
- Memahami konsep dasar web server HTTP request-response.

---

## 3. Concept
Dalam rekayasa perangkat lunak, **Skalabilitas (*Scalability*)** adalah kapabilitas sebuah sistem untuk menangani pertambahan beban kerja (*workload*) yang meningkat tanpa menurunkan rasio performa dan ketersediaan layanan, dengan cara menambahkan sumber daya komputasi.

Ketika traffic meningkat dari 100 RPS (*requests per second*) menjadi 50.000 RPS, arsitek sistem memiliki dua strategi fundamental:
1. **Vertical Scaling (Scale Up):** Mengganti mesin fisik/virtual yang ada dengan mesin yang memiliki spesifikasi CPU, RAM, dan disk yang jauh lebih besar.
2. **Horizontal Scaling (Scale Out):** Menambahkan lebih banyak unit mesin mandiri yang berjalan secara paralel di balik sebuah perute (*Load Balancer*).

---

## 4. Why? (Mengapa Memahami Ini Wajib?)
Aplikasi pemula biasanya di-deploy pada satu server tunggal (*single server setup*). Seiring naiknya jumlah pengguna:
- Response time melonjak dari 50ms menjadi 5.000ms (*latency spike*).
- CPU usage menyentuh 100% atau RAM habis (*Out of Memory / OOM Crash*).
- **Kesalahan Fatal Pemula:**
  - Terus menaikkan ukuran mesin virtual ke spesifikasi tertinggi (misal AWS `x1e.32xlarge` seharga ribuan dolar/bulan) padahal aplikasi dibatasi oleh lock database atau single-thread loop.
  - Memecah aplikasi menjadi puluhan microservices tanpa membuat backend stateless terlebih dahulu, sehingga session user hilang saat request berpindah server.

---

## 5. What? (Apa itu Bottleneck & Skalabilitas?)

### A. Bottleneck
Bottleneck adalah titik tersempit atau komponen terlemah dalam alur sistem yang membatasi kapasitas throughput total.

| Pilar Resource | Indikator Gejala | Contoh Penyebab |
|---|---|---|
| **CPU Bound** | CPU 100%, queue request menumpuk | Hashing password berat (bcrypt), manipulasi gambar, serialisasi payload JSON raksasa |
| **Memory Bound** | RAM penuh, swap aktif, OOM crash | In-memory cache tidak terbatas, memory leaks (unclosed event listeners) |
| **Disk I/O Bound** | %iowait tinggi, IOPS jenuh | Query database tanpa index (*table scan*), log sinkron ke file |
| **Network Bound** | Socket timeout, packet drop | Bandwidth limit, ephemeral port exhaustion, slow third-party API |

### B. Karakteristik Skalabilitas
- **Scale Up:** Cepat dan mudah di awal, tidak butuh refactor kode, namun memiliki *hardware ceiling* (batas hardware fisik termahal) dan merupakan *Single Point of Failure (SPOF)*.
- **Scale Out:** Menawarkan elastisitas tak terbatas dan resiliensi tinggi, namun menuntut arsitektur aplikasi menjadi **Stateless**.

---

## 6. How? (Cara Kerja & Arsitektur)

```text
               SKENARIO PERTAMBAHAN BEBAN

 [VERTICAL SCALING / SCALE UP]          [HORIZONTAL SCALING / SCALE OUT]
 
        +---------------+                      +---------------+
        |  SERVER BESAR |                      | Load Balancer |
        |  64 CPU Core  |                      +-------+-------+
        |  256 GB RAM   |                              |
        +-------+-------+             +----------------+----------------+
                |                     |                |                |
             Clients            +-----+------+   +-----+------+   +-----+------+
                                |  Server 1  |   |  Server 2  |   |  Server 3  |
                                | 4 Core,8GB |   | 4 Core,8GB |   | 4 Core,8GB |
                                +------------+   +------------+   +------------+
```

### Syarat Mutlak Horizontal Scaling: Stateless Backend
Agar request pengguna dapat diarahkan ke server mana pun secara acak tanpa merusak data:
1. **No In-Memory Session:** Jangan simpan session di variabel global memori server. Gunakan Redis atau JWT.
2. **No Local File Storage:** Jangan simpan file upload pengguna di folder lokal server (`/uploads`). Gunakan Object Storage terpusat (AWS S3 / MinIO).
3. **Externalized Database:** Database tidak boleh berjalan di server aplikasi yang sama.

---

## 7. Analogy
- **Vertical Scaling:** Anda memiliki seorang kurir bersepeda motor. Saat pesanan barang melonjak, Anda mengganti motornya dengan truk gandeng. Truk tersebut memuat banyak barang, namun jika ban truk pecah, semua kiriman hari itu gagal total. Truk juga tidak bisa membesar tanpa batas jalan raya.
- **Horizontal Scaling:** Alih-alih membeli truk raksasa, Anda merekrut 10 kurir motor tambahan. Jika kurir nomor 3 bannya kempes, 9 kurir lainnya tetap bisa mengantar barang. Anda bisa menambah atau mengurangi kurir kapan saja sesuai pesanan harian.

---

## 8. Diagram: Alur Deteksi Bottleneck

```text
[HTTP Request Masuk]
        │
        ▼
APLIKASI / SERVER ───▶ [Cek CPU Usage > 85%?] ──▶ YA ──▶ Komputasi Berat / Kurang Worker Core
        │
        ├──▶ [Cek RAM Usage Mendekati Batas?] ──▶ YA ──▶ Memory Leak / Caching Lokal Berlebih
        │
        ├──▶ [Cek Disk IOPS Tinggi?] ────────────▶ YA ──▶ Database Tanpa Index / Logging Sinkron
        │
        └──▶ [Cek Network Latency / Queue?] ────▶ YA ──▶ Database Connection Pool Exhausted
```

---

## 9. Simple Example
Sebuah fungsi komputasi faktorial atau pencarian regex kompleks di backend Node.js. Karena Node.js secara default berjalan pada *single-thread event loop*, satu komputasi berat selama 3 detik akan memblokir (*block*) seluruh pengguna lain yang hanya ingin mengakses halaman "About Us".

---

## 10. Practical Example
Perhatikan perbedaan antara server single-thread yang rentan bottleneck dengan server multi-core cluster pada folder hands-on:
- `hands-on/m01/lab-single.js`
- `hands-on/m01/lab-cluster.js`

---

## 11. Real World Example: Lonjakan Flash Sale E-Commerce
Pada momen Flash Sale 12.12:
- **Pendekatan Scale Up:** Membeli instance terbesar cloud provider (misal: 128 vCPU). Begitu traffic mencapai 500.000 concurrent request, instance tersebut mencapai limit hardware maksimumnya dan sistem *down*.
- **Pendekatan Scale Out:** Backend dibuat stateless dan di-package ke container Docker di Kubernetes. Kubernetes *Horizontal Pod Autoscaler (HPA)* memonitor CPU utilization; saat mencapai 70%, pod otomatis bertambah dari 20 instance menjadi 400 instance secara dinamis dalam waktu 90 detik.

---

## 12. Trade-offs (Perbandingan Lengkap)

| Aspek | Vertical Scaling (*Scale Up*) | Horizontal Scaling (*Scale Out*) |
|---|---|---|
| **Kompleksitas Kode** | Sangat Rendah (kode tidak perlu diubah) | Tinggi (aplikasi wajib stateless, butuh Load Balancer) |
| **Batas Maksimal (*Limit*)** | Terbatas oleh teknologi hardware tertinggi | Hampir tidak terbatas (*elastic scaling*) |
| **Downtime saat Upgrade** | Butuh downtime/restart mesin | Nol (*Zero Downtime* via rolling deployment) |
| **Biaya (*Cost*)** | Eksponensial (mesin tier tertinggi sangat mahal) | Linear (menggunakan banyak mesin komoditas standar) |
| **Resiliensi & SPOF** | Sangat rentan (1 mesin mati = sistem mati) | Sangat tinggi (jika 1 node mati, node lain mengambil alih) |
| **Konsistensi Data** | Sederhana (semua proses berbagi resource memori/disk yang sama) | Menantang (memerlukan konsistensi data terdistribusi) |

---

## 13. When To Use

### Gunakan Vertical Scaling Jika:
- Proyek tahap awal (MVP/Startup baru) yang butuh delivery cepat tanpa kompleksitas DevOps.
- Database relasional (PostgreSQL/MySQL) yang ukuran data dan koneksinya masih muat dalam satu server performa tinggi.
- Tim engineer masih sangat kecil (< 3 orang) dan belum ada personel yang menguasai orchestration (Kubernetes/ECS).

### Gunakan Horizontal Scaling Jika:
- Pola traffic fluktuatif atau sering terjadi lonjakan (*spiky traffic*).
- Sistem menuntut *High Availability* 99.99% tanpa toleransi downtime perangkat keras.
- Kapasitas mesin single terbesar di pasar sudah tidak sanggup lagi menampung beban kerja.

---

## 14. When NOT To Use
- Jangan gunakan Horizontal Scaling jika aplikasi masih menyimpan session login di memori lokal server (`express-session` memory store default). User akan tiba-tiba logout ketika request berikutnya mendarat di node server yang berbeda.
- Jangan gunakan Horizontal Scaling jika masalah utamanya adalah query database yang lambat (*missing index*). Menambah server aplikasi justru akan membunuh database lebih cepat karena koneksi yang masuk berlipat ganda!

---

## 15. Common Mistakes
1. **Premature Distributed System:** Terburu-buru membuat puluhan microservices padahal traffic harian hanya ratusan request.
2. **Mengabaikan Hukum Amdahl (Amdahl's Law):** Mengira bahwa menambah 10 mesin akan mempercepat pemrosesan 10x lipat. Jika 40% dari pekerjaan tersebut bersifat serial (misal: harus menunggu lock database transaksi berurutan), percepatan maksimal sistem tidak akan pernah melebihi 2.5x lipat berapapun mesin yang Anda tambahkan!
3. **Mengabaikan Connection Pool Database:** Menggandakan server backend dari 2 menjadi 50 tanpa mengatur connection pool database, sehingga database crash karena kehabisan koneksi (*connection exhaustion*).

---

## 16. Best Practices
- **Must Have:**
  - Buat seluruh backend API bersifat **Stateless**.
  - Pasang pemantauan metrik (*CPU, RAM, Disk I/O, Network*) sebelum menentukan keputusan scaling.
- **Recommended:**
  - Letakkan Load Balancer / Reverse Proxy (seperti Nginx atau cloud load balancer) di depan cluster instance.
  - Pisahkan penyimpanan file media ke Object Storage (S3-compatible).
- **Advanced:**
  - Konfigurasikan *Autoscaling Policy* berbasis metrik gabungan (CPU > 75% ATAU P99 Latency > 300ms).
- **Avoid / Overengineering:**
  - Menyiapkan arsitektur sharding database sebelum mengoptimalkan database index dan query caching.

---

## 17. Troubleshooting Guide
```text
Gejala: Response API sangat lambat saat traffic naik, padahal CPU server hanya 15%.
-----------------------------------------------------------------------------------
Penyebab Utama:
1. Database Connection Pool Habis: Worker thread tertahan mengantre koneksi database.
2. I/O Disk Bottleneck: Database kehabisan buffer pool memori dan membaca data dari disk.
3. Slow Third-Party API: Backend memanggil external payment gateway secara sinkron tanpa timeout.

Cara Diagnosa:
- Cek koneksi aktif database: 
  - PostgreSQL: SELECT count(*) FROM pg_stat_activity WHERE state = 'active';
- Cek utilisasi disk: iostat -xz 1 (perhatikan kolom %util).

Solusi:
- Pasang connection pooler (misal: PgBouncer) atau naikkan pool size aplikasi secara proporsional.
- Tambahkan index pada kolom filter query.
```

---

## 18. Hands-on Lab: Menguji Bottleneck & Skalabilitas Multi-Core
File kode lab sudah tersedia di:
- `System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m01/lab-single.js`
- `System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m01/lab-cluster.js`
- `System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m01/benchmark.js`

### Jalankan Uji Coba:
1. Buka terminal, jalankan server single process:
   ```bash
   node System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m01/lab-single.js
   ```
2. Buka terminal kedua, jalankan benchmark:
   ```bash
   node System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m01/benchmark.js
   ```
   *(Perhatikan total waktu penyelesaian request saat 1 CPU core melayani semua antrean).*
3. Hentikan server pertama (`Ctrl+C`), lalu jalankan server cluster multi-core:
   ```bash
   node System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m01/lab-cluster.js
   ```
4. Jalankan kembali benchmark di terminal kedua:
   ```bash
   node System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m01/benchmark.js
   ```
   *(Bandingkan waktu penyelesaian yang turun drastis karena komputasi diproses secara paralel oleh worker yang berbeda).*

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan 3 masalah yang terjadi jika kita melakukan horizontal scaling pada aplikasi yang menyimpan session login di memori lokal (`req.session`)!

### Level 2 (Medium):
Sebuah aplikasi monolithic media-processing sering mengalami CPU spike hingga 100% setiap kali pengguna mengunggah video. Jika Anda ditugaskan memperbaikinya dengan prinsip modularitas, bagaimana Anda memisahkan modul video processing tersebut agar tidak memengaruhi API utama?

### Level 3 (Hard):
Jelaskan kaitan antara **Hukum Amdahl (Amdahl's Law)** dengan batas efisiensi penambahan server pada sistem yang memiliki ketergantungan transaksi database serial (ACID Transaction)!

---

## 20. Summary & Knowledge Check
- [ ] Mampu membedakan karakteristik Vertical vs Horizontal Scaling.
- [ ] Memahami 4 titik jenuh sumber daya: CPU, Memory, Disk, Network.
- [ ] Memahami bahwa backend **Stateless** adalah fondasi mutlak sebelum melakukan Scale-Out.
- [ ] Mampu menjalankan dan membuktikan pembagian beban multi-core di komputer lokal.
