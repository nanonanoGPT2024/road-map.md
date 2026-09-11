# MODULE 02: Latency, Throughput, dan Trade-off Kinerja

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Membedakan secara presisi antara **Latency**, **Response Time**, **Throughput**, dan **Bandwidth**.
2. Menganalisis metrik performa menggunakan **Percentiles (p50, p90, p95, p99, p99.9)** daripada sekadar rata-rata (*average/mean*).
3. Menerapkan **Hukum Little (*Little's Law*)** untuk menghitung kapasitas antrean sistem terdistribusi.
4. Menganalisis trade-off mendasar antara optimasi Latensi Rendah (*Low Latency*) vs Throughput Tinggi (*High Throughput*) seperti pada teknik *Batching*.
5. Melakukan pengukuran langsung latensi p95/p99 dan throughput menggunakan script hands-on di komputer Anda.

---

## 2. Prerequisite
- Telah menyelesaikan [Module 01: Skalabilitas Vertikal vs Horizontal & Bottleneck Sistem](./Module-01-Skalabilitas-Vertikal-vs-Horizontal.md).
- Memahami konsep dasar HTTP request dan waktu eksekusi program.

---

## 3. Concept
Dalam arsitektur sistem, performa tidak diukur dengan satu angka tunggal seperti "cepat" atau "lambat". Performa dievaluasi menggunakan dua dimensi komplementer yang sering kali saling bertentangan:
1. **Latency:** Seberapa cepat sebuah operasi individu diselesaikan (diukur dalam milidetik atau mikrodetik).
2. **Throughput:** Berapa banyak operasi yang dapat diselesaikan oleh sistem dalam satu satuan waktu (misal: RPS, QPS, atau Mbps).

Upaya meningkatkan throughput sering kali menaikkan latensi per-request (misalnya karena teknik buffering/batching). Sebaliknya, meminimalkan latensi per-request hingga ekstrem sering kali membatasi throughput maksimal sistem.

---

## 4. Why? (Mengapa Memahami Ini Wajib?)

### Bahaya Ilusi "Rata-rata" (*The Flaw of Averages*)
Banyak tim engineer pemula memantau dashboard server dan melihat:
> *"Rata-rata response time API kita 45 ms. Sangat cepat!"*

Namun pengguna di media sosial komplain: *"Aplikasi sering loading berputar sampai 4 detik saat checkout!"*

Mengapa ini terjadi?
Jika 95 dari 100 pengguna mendapatkan respon 20 ms, tetapi 5 pengguna mengalami *timeout* 4.000 ms:
$$\text{Average} = \frac{(95 \times 20) + (5 \times 4000)}{100} = \frac{1900 + 20000}{100} = 219 \text{ ms}$$
Angka 219 ms terlihat wajar di laporan manajerial, padahal **5% pengguna (1 dari 20 orang) mengalami bencana performa 4 detik!** Dalam sistem e-commerce bernilai jutaan transaksi, 5% pembeli yang frustrasi berarti kehilangan omset miliaran rupiah.

---

## 5. What? (Definisi Metrik Kinerja Sistem)

### A. Latency vs Response Time
- **Latency (Waktu Tunggu Murni):** Waktu yang dihabiskan sebuah request menunggu dalam antrean sebelum mulai diproses, ditambah waktu transfer paket data di jaringan kabel/fiber optik.
- **Service Time (Waktu Pemrosesan):** Waktu aktual yang dihabiskan server untuk mengeksekusi komputasi atau query.
- **Response Time (Total Waktu Respon):** 
  $$\text{Response Time} = \text{Network Latency} + \text{Queue Wait Time} + \text{Service Time}$$

### B. Throughput vs Bandwidth
- **Bandwidth:** Kapasitas pipa transmisi teoritis maksimum (misal: kabel internet 1 Gbps).
- **Throughput:** Jumlah aktual data atau transaksi bermanfaat (*payload*) yang berhasil ditransfer dan diproses per detik (misal: 8.500 HTTP requests/detik atau 350 Mbps file transfer).

### C. Percentiles (Kuartil & Tail Latency)
- **p50 (Median):** 50% pengguna mengalami waktu respon lebih cepat atau sama dengan nilai ini. Menggambarkan pengalaman pengguna tipikal.
- **p90 / p95:** 90% atau 95% pengguna lebih cepat dari nilai ini.
- **p99 (99th Percentile):** Menunjukkan pengalaman 1% pengguna paling lambat (*Tail Latency*). Di sinilah masalah arsitektur tersembunyi (misal: garbage collection pauses, disk lock, connection retry) terungkap.
- **p99.9:** Digunakan oleh perusahaan skala raksasa (Amazon, Google) karena dengan 1 miliar request/hari, p99.9 mewakili 1 juta request yang lambat setiap harinya!

---

## 6. How? (Hukum Matematika & Mekanisme Sistem)

### A. Little's Law (Hukum Little)
Dalam teori antrean (*queuing theory*), Hukum Little menyatakan:
$$L = \lambda \times W$$
- $L$ = Rata-rata jumlah request dalam sistem yang sedang berjalan bersamaan (*concurrency*).
- $\lambda$ (Lambda) = Throughput kedatangan request per detik (RPS).
- $W$ = Rata-rata waktu tunggu/response time per request (detik).

#### Contoh Perhitungan Praktis Arsitektur:
Jika API Anda melayani **2.000 RPS** ($\lambda = 2000$) dan rata-rata response time database query adalah **200 ms** ($W = 0.2 \text{ detik}$):
$$L = 2000 \times 0.2 = 400 \text{ concurrent connections}$$
Artinya, backend dan database Anda **wajib sanggup menampung minimal 400 koneksi aktif secara simultan** setiap detiknya tanpa putus!

---

## 7. Analogy

```text
               ANALOGI PIPA AIR & RESTORAN

+-------------------------------------------------------------+
| LATENCY: Waktu yang dibutuhkan satu tetes air dari keran   |
|          hingga jatuh menyentuh ember di bawahnya.          |
|                                                             |
| BANDWIDTH: Lebar diameter pipa air tersebut.                |
|                                                             |
| THROUGHPUT: Total liter air yang berhasil tertampung di     |
|             dalam ember setiap menitnya.                    |
+-------------------------------------------------------------+
```

### Analogi Restoran (Low Latency vs High Throughput):
- **Pendekatan Low Latency:** Setiap ada pesanan 1 burger dari meja mana pun, koki langsung memasak 1 patty daging tersebut di wajan besar. Burger selesai dalam 3 menit (latensi sangat cepat). Namun dalam 1 jam, koki hanya bisa menyelesaikan 15 burger (throughput rendah).
- **Pendekatan High Throughput (Batching):** Koki menunggu pesanan terkumpul hingga ada 10 burger, lalu memasak 10 patty sekaligus di wajan. Pelanggan pertama mungkin harus menunggu 6 menit (latensi naik), tetapi dalam 1 jam koki berhasil memproduksi 80 burger (throughput naik 5x lipat).

---

## 8. Diagram: Fenomena Amplifikasi Tail Latency pada Microservices

Dalam arsitektur microservices, satu halaman web sering memanggil 20 service independen secara paralel.

```text
[ Browser Client ]
        │
        ▼ (Request Homepage)
[ API Gateway ]
        ├───▶ Service User       (Latency p99: 100ms)
        ├───▶ Service Product    (Latency p99: 100ms)
        ├───▶ Service Recommendation (Latency p99: 100ms)
        ├───▶ Service Pricing    (Latency p99: 100ms)
        └───▶ ... (16 services lainnya)
```

Jika setiap service memiliki probabilitas 99% cepat (p99 = 100ms, p99.9 = 2.000ms):
Probabilitas seluruh 20 service selesai cepat:
$$P(\text{semua cepat}) = 0.99^{20} \approx 0.8179 \ (81.8\%)$$
Artinya, **hampir 20% pengguna akhir akan merasakan halaman utama lambat**, padahal setiap tim service mengklaim metrik mereka 99% hijau! Ini disebut **Tail Latency Amplification**.

---

## 9. Simple Example

Mengapa menulis data ke disk 1 per 1 lambat:
- Menulis 1.000 record ke database satu per satu secara individual: Butuh 1.000 round-trip network + 1.000 disk fsync = **10.000 ms (10 detik)**.
- Menggabungkannya ke dalam 1 batch insert (`INSERT INTO ... VALUES (...), (...), ...`): Hanya butuh 1 round-trip network + 1 disk fsync = **80 ms**!

---

## 10. Practical Code Example
Lihat demonstrasi perbedaan antara eksekusi non-batched vs batched pada hands-on lab:
`System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m02/latency_benchmark.js`

---

## 11. Real World Example

### 1. Dampak Latensi Google & Amazon
- Studi legendaris Google menunjukkan bahwa penambahan latensi **hanya 400 milidetik** pada hasil pencarian menyebabkan penurunan volume pencarian sebesar **0.59%**.
- Amazon menemukan bahwa setiap **100 milidetik latensi tambahan** menurunkan total penjualan sebesar **1%**.

### 2. High-Frequency Trading (HFT) vs Video Streaming
- **HFT (Wall Street):** Mengorbankan throughput demi latensi ultra-rendah (< 1 mikrodetik). Mereka menggunakan jaringan serat optik khusus dan kartu jaringan kernel-bypass (DPDK).
- **Netflix / YouTube Video Streaming:** Mengorbankan latensi demi throughput raksasa. Video di-buffer terlebih dahulu selama 5-10 detik (latensi awal tinggi), namun setelah berjalan, throughput stabil mengalirkan jutaan megabit data video 4K tanpa buffering putus-putus.

---

## 12. Trade-offs (Low Latency vs High Throughput)

| Karakteristik | Fokus Low Latency | Fokus High Throughput |
|---|---|---|
| **Mekanisme Utama** | Langsung kirim seketika (*immediate processing*) | Penampungan sementara (*batching / buffering*) |
| **Pemanfaatan Resource** | Efisiensi CPU rendah (banyak idle / context switch) | Efisiensi CPU sangat tinggi (saturasi optimal) |
| **Ukuran Kompresi** | Kompresi ringan atau tanpa kompresi | Kompresi tinggi (Gzip/Brotli/Zstandard) |
| **Protokol Jaringan** | UDP, WebSockets, gRPC streaming langsung | HTTP bulk transfer, Kafka batch producer |
| **Biaya Infrastruktur** | Sangat mahal (butuh over-provisioning kapasitas) | Hemat (memaksimalkan kapasitas mesin yang ada) |

---

## 13. When To Optimize What

### Prioritaskan Optimasi LATENCY Jika:
- Aplikasi interaktif real-time: Game multiplayer online, voice/video call, collaborative doc editing (Google Docs).
- Sistem pembayaran atau transaksi checkout real-time.
- API Gateway yang berada di jalur kritis (*critical path*) yang dipanggil berulang kali oleh sub-komponen lain.

### Prioritaskan Optimasi THROUGHPUT Jika:
- Pemrosesan data analitik batch (ETL pipeline, machine learning model training).
- Backup data dan sinkronisasi log terdistribusi (Elasticsearch / ClickHouse ingestion).
- Sistem video rendering atau pengiriman email massal (newsletter broadcast).

---

## 14. When NOT To Optimize
- Jangan melakukan optimasi latensi mikro (seperti mengganti library JSON parser atau menulis assembly/C++) jika 90% waktu respon dihabiskan menunggu round-trip jaringan antar-region (misal dari server Jakarta ke database di Virginia, USA: jarak fisik optik memakan ~200ms round-trip!).

---

## 15. Common Mistakes
1. **Menggunakan Rata-Rata (*Arithmetic Mean*) sebagai KPI:** Rata-rata menyembunyikan masalah tail latency p99. Selalu gunakan grafik percentiles (p50, p95, p99).
2. **Buffer Bloat:** Menyetel buffer antrean terlalu besar. Ketika sistem macet, jutaan request tertahan di antrean memori. Pengguna sudah menekan tombol refresh atau menutup browser, tetapi server tetap membuang energi memproses request yang sudah ditinggalkan tersebut!
3. **Mengabaikan Network Round-Trip Time (RTT):** Melakukan "Chatty API calls" (misal memanggil 50 query database berurutan dalam loop `for` alih-alih 1 query dengan `IN (...)`).

---

## 16. Best Practices

- **Must Have:**
  - Monitoring metrik latensi berbasis percentiles (**p50, p95, p99**) menggunakan Prometheus/Grafana atau APM.
  - Terapkan **Timeout ketat** pada setiap HTTP client dan database connection.
- **Recommended:**
  - Gunakan teknik **Connection Pooling** untuk menghindari overhead TCP 3-way handshake + TLS handshake di setiap query.
  - Terapkan **Keep-Alive (HTTP persistent connections)**.
- **Advanced:**
  - Terapkan **Hedged Requests**: Jika request p99 ke replica backend tidak menjawab dalam 100ms, kirimkan request duplikat ke replica lain secara paralel dan gunakan respon yang datang pertama kali (pola yang digunakan Google untuk memangkas tail latency).
- **Avoid / Overengineering:**
  - Menghabiskan waktu berminggu-minggu mengoptimalkan algoritma CPU saat bottleneck sebenarnya adalah latensi jaringan database.

---

## 17. Troubleshooting Guide
```text
Gejala: Metrik p99 melonjak tinggi secara periodik setiap 60 detik sekali
-------------------------------------------------------------------------
Kemungkinan Akar Masalah:
1. Stop-the-World Garbage Collection (GC Pause) pada runtime Java/Go/Node.js karena memori penuh.
2. Database Flush Buffer: Database sedang mem-flush dirty pages dari RAM ke disk (checkpointing).
3. Cron Job Lokal: Ada background script cron yang berjalan di server yang sama menyedot CPU.

Cara Diagnosa:
- Aktifkan GC logging pada runtime aplikasi (misal: node --trace-gc).
- Korelasikan waktu lonjakan p99 dengan jadwal cron job sistem.

Solusi:
- Pisahkan worker cron job ke server/container terpisah.
- Lakukan tuning batas memory heap atau alokasi buffer pool database.
```

---

## 18. Hands-on Lab: Mengukur Percentiles & Trade-off Batching

File lab sudah disiapkan di:
`System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m02/latency_benchmark.js`

### Jalankan Uji Coba:
Buka terminal Anda dan jalankan:
```bash
node System-Design/BAB-01-Fondasi-Skalabilitas/hands-on/m02/latency_benchmark.js
```

### Yang Akan Anda Amati:
Script akan membandingkan dua skenario nyata:
1. **Skenario A (Non-Batched / Immediate):** Memproses 1.000 event log satu per satu ke database simulasi.
2. **Skenario B (Micro-Batching):** Memproses 1.000 event log dengan teknik micro-batching (dikumpulkan setiap 50 item).
Script akan menghitung secara otomatis:
- Waktu total
- Throughput (events/detik)
- Nilai latensi: **Min, Mean, p50 (Median), p95, p99, Max**.

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan perbedaan mendasar antara p50 dan p99! Mengapa p99 lebih krusial untuk mengevaluasi kualitas arsitektur sistem?

### Level 2 (Medium):
Sebuah sistem backend menangani 1.500 requests per detik. Rata-rata waktu pemrosesan (response time) adalah 120 milidetik. Berdasarkan **Hukum Little (Little's Law)**:
1. Berapa rata-rata request yang sedang aktif diproses dalam sistem secara simultan?
2. Jika response time tiba-tiba naik menjadi 800 ms karena database melambat, berapa jumlah koneksi simultan yang harus ditampung sistem agar tidak menolak request?

### Level 3 (Hard):
Jelaskan fenomena **Tail Latency Amplification** pada arsitektur yang memiliki 30 microservices di belakang API Gateway. Jika setiap service memiliki ketersediaan/kecepatan p99 = 99%, hitung probabilitas satu request halaman utama pengguna akan mengalami kelambatan!

---

## 20. Summary & Knowledge Check
- [ ] Mampu membedakan Latency vs Response Time vs Throughput vs Bandwidth.
- [ ] Memahami bahaya menggunakan rata-rata (*mean*) dan menguasai interpretasi percentiles (**p50, p95, p99**).
- [ ] Memahami hubungan matematis **Hukum Little ($L = \lambda \times W$)**.
- [ ] Memahami kapan harus memilih optimasi Latency vs Throughput (prinsip *Batching*).
- [ ] Mampu menjalankan benchmark komparasi latensi dan throughput di lingkungan lokal.
