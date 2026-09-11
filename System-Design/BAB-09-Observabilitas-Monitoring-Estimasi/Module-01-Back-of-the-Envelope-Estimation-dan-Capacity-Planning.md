# Module 01: Back-of-the-Envelope Estimation & Capacity Planning

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Melakukan estimasi cepat (*Back-of-the-Envelope Calculation*) untuk menentukan kapasitas infrastruktur sistem berskala besar sebelum menulis sebaris kode pun.
- Menguasai metrik esensial: **QPS (Queries Per Second)**, **Peak QPS**, **Storage Capacity (5-year growth)**, **Bandwidth Ingress/Egress**, dan **Memory/Cache Capacity**.
- Menghafal angka-angka latensi kritis (*Latency Numbers Every Programmer Should Know*) karya Jeff Dean.
- Menggunakan pendekatan Powers of Two dan konversi praktis (detik per hari, byte multipliers).

## 2. Prerequisite
- Memahami dasar satuan biner (KB, MB, GB, TB, PB).
- Konsep dasar throughput vs latency dari BAB 01.

## 3. Concept
Dalam wawancara arsitektur sistem maupun perencanaan proyek nyata di industri, seorang Software Architect tidak bisa hanya mengatakan: *"Kita butuh banyak server"*. Anda harus mampu menghitung perkiraan matematis kasar:
- Berapa jumlah server yang harus disewa?
- Berapa kapasitas disk database untuk 5 tahun ke depan?
- Berapa Gigabyte RAM Redis yang dibutuhkan untuk menyimpan 20% data teratas (Pareto Principle)?
- Berapa bandwidth internet yang keluar dari CDN tiap detik?

Estimasi ini disebut **Back-of-the-Envelope Estimation** (perhitungan di balik amplop/kertas coretan) — sebuah metode estimasi cepat untuk memvalidasi kelayakan desain arsitektur.

## 4. Why?
- **Mencegah Over-Engineering & Pemborosan Biaya Cloud**: Jangan menyewa kluster Cassandra senilai \$50.000/bulan jika setelah dihitung data Anda hanya 500 MB dan muat di satu database PostgreSQL kecil.
- **Mencegah Under-Provisioning & Insiden Down**: Mengetahui apakah bottleneck pertama Anda akan berada di IOPS disk, bandwidth jaringan, atau kapasitas RAM.
- **Menguji Kelayakan Solusi Desain**: Jika solusi Anda membutuhkan 50 Terabyte RAM untuk in-memory hash table, Anda tahu desain tersebut secara finansial tidak masuk akal dan harus diganti dengan SSD berbasis LSM-Tree.

## 5. What?
### Angka Sakti yang Wajib Diingat:
1. **Jumlah Detik dalam Satu Hari**:
   $$1 \text{ hari} = 24 \times 60 \times 60 = 86.400 \text{ detik} \approx 100.000 \text{ detik (untuk kemudahan kalkulasi mental)}$$
2. **Kaidah Powers of Two (Satuan Data)**:
   - $2^{10} \approx 10^3 = 1\text{ Thousand} = 1\text{ KB}$
   - $2^{20} \approx 10^6 = 1\text{ Million} = 1\text{ MB}$
   - $2^{30} \approx 10^9 = 1\text{ Billion} = 1\text{ GB}$
   - $2^{40} \approx 10^{12} = 1\text{ Trillion} = 1\text{ TB}$
   - $2^{50} \approx 10^{15} = 1\text{ Petabyte (PB)}$
3. **Latency Numbers Every Programmer Should Know (Jeff Dean)**:
   - L1 Cache Reference: **0.5 ns**
   - L2 Cache Reference: **7 ns**
   - Main Memory (RAM) Reference: **100 ns**
   - Read 1 MB sequentially from RAM: **250,000 ns (0.25 ms)**
   - Read 1 MB sequentially from NVMe SSD: **1,000,000 ns (1 ms)**
   - Disk Seek (HDD tradisional): **10,000,000 ns (10 ms)**
   - Send packet CA to Netherlands & back (RTT Trans-Atlantik): **150,000,000 ns (150 ms)**
   *(Pelajaran: Membaca dari RAM adalah ~1000x lebih cepat daripada SSD, dan jaringan antar-benua adalah jurang latensi terbesar).*

## 6. How?
### Template 5 Langkah Estimasi Kapasitas:
Misalkan kita merancang sistem seperti **Twitter / X**:
- Pengguna Aktif Harian (DAU): **300 Juta Pengguna**.
- Setiap pengguna rata-rata membuat 2 tweet per hari.
- 10% tweet menyertakan media foto (ukuran rata-rata: 200 KB).
- Setiap pengguna rata-rata membaca feed 20 kali per hari (1 feed memuat 20 tweet).

#### 1. Estimasi QPS (Queries Per Second):
- **Write QPS (Post Tweet)**:
  $$\text{Total Tweets per hari} = 300.000.000 \times 2 = 600.000.000 \text{ tweets/hari}$$
  $$\text{Average Write QPS} = \frac{600.000.000}{86.400} \approx 7.000 \text{ QPS}$$
  $$\text{Peak Write QPS} = \text{Average QPS} \times 2 \approx 14.000 \text{ QPS}$$
- **Read QPS (View Timeline)**:
  $$\text{Total Feed Views per hari} = 300.000.000 \times 20 = 6.000.000.000 \text{ views/hari}$$
  $$\text{Average Read QPS} = \frac{6.000.000.000}{86.400} \approx 70.000 \text{ QPS}$$
  $$\text{Peak Read QPS} = \text{Average QPS} \times 2 \approx 140.000 \text{ QPS}$$
- **Rasio Read-to-Write**: $70.000 : 7.000 = 10 : 1$ *(Read-heavy system! Wajib caching).*

#### 2. Estimasi Storage Capacity (5 Tahun):
- Data Teks Tweet (ID, UserID, Text, Timestamp, Metadata): $\approx 300 \text{ bytes}$.
- Daily Text Storage: $600.000.000 \times 300 \text{ bytes} = 180 \text{ GB/hari}$.
- Daily Media Storage (10% ada foto):
  $$60.000.000 \text{ foto} \times 200 \text{ KB} = 12.000.000.000 \text{ KB} = 12 \text{ TB/hari}$$.
- **Total Storage per Hari**: $\approx 12.2 \text{ TB/hari}$.
- **Storage 5 Tahun**:
  $$12.2 \text{ TB} \times 365 \times 5 \approx 22.265 \text{ TB} \approx 22.3 \text{ Petabyte!}$$

#### 3. Estimasi Bandwidth (Jaringan Ingress & Egress):
- **Ingress (Write)**: $12.2 \text{ TB per hari} \rightarrow \frac{12.2 \times 10^{12} \times 8 \text{ bits}}{86.400 \text{ detik}} \approx 1.13 \text{ Gbps}$ masuk.
- **Egress (Read)**: Dengan rasio read 10x, bandwidth keluar bisa mencapai $> 10 \text{ Gbps}$ (Wajib CDN untuk menyerap bandwidth media!).

#### 4. Estimasi Memory Caching (Prinsip Pareto 80/20):
- 20% tweet harian menghasilkan 80% trafik baca.
- Cache RAM 20% data harian:
  $$\text{Daily Text Cache} = 20\% \times 180 \text{ GB} = 36 \text{ GB RAM}$$
  Sangat realistis! Satu server Redis 64 GB RAM mampu menampung seluruh teks tweet terpopuler dalam 1 hari!

## 7. Analogy
- **Insinyur Sipil Jembatan**: Sebelum membangun jembatan gantung, insinyur tidak langsung membeli semen; mereka menghitung beban maksimum: berapa mobil per jam, berat rata-rata truk, dan kekuatan angin badai.
- **Back-of-the-Envelope**: Menghitung beban jembatan digital Anda agar sistem tidak roboh saat jutaan pengguna melintas bersamaan.

## 8. Diagram

```text
================ PIPELINE ESTIMASI KAPASITAS SISTEM ================
   [Pengguna Aktif: DAU / MAU]
                 │
                 ├──> [Throughput: Read QPS vs Write QPS] ──> [Jumlah Node Server / Pod]
                 │
                 ├──> [Storage Growth: Data Harian x 365 x 5] ──> [Kebutuhan Disk / S3]
                 │
                 ├──> [Bandwidth Ingress & Egress] ───────> [Kapasitas Pipa ISP / CDN]
                 │
                 └──> [Cache RAM (Pareto 80/20 Rule)] ────> [Ukuran Kluster Redis]
```

## 9. Simple Example
Aturan Pembulatan Cepat untuk Mental Math:
Jika Anda ingin menghitung QPS dari 100 juta request per hari:
$$\frac{100.000.000}{100.000} = 1.000 \text{ QPS (Perkiraan kasar, deviasi hanya ~15% dari } 1.157 \text{ QPS nyata)}$$
Dalam diskusi arsitektur, perbedaan antara 1.000 QPS dan 1.157 QPS tidak merubah keputusan desain (keduanya membutuhkan skala puluhan pod/server). Kecepatan estimasi jauh lebih berharga daripada presisi desimal!

## 10. Practical Example: Menghitung Kebutuhan Server Web
Sebuah server web modern (8 vCPU, 16 GB RAM) dengan stack Node.js/Go rata-rata mampu menangani **1.000 hingga 2.000 QPS** (non-blocking I/O).
Jika sistem Anda memiliki Peak Read QPS sebesar **140.000 QPS**:
- Jumlah instance server yang dibutuhkan: $\frac{140.000}{1.500} \approx 94 \text{ server web}$.
- Tambahkan buffer redundansi 30% (N+1 / multi-AZ): $\approx 120 \text{ server web}$.

## 11. Real World Example
- **YouTube**: Mengunggah > 500 jam video setiap menit. Perhitungan kapasitas storage video YouTube per hari:
  $$500 \text{ menit video} \times 60 \times 24 = 720.000 \text{ jam video/hari}$$.
  Dengan ukuran bitrate rata-rata (1080p @ 3 GB/jam), YouTube harus menambah minimal **2.16 Petabyte storage baru setiap 24 jam**!

## 12. Trade-offs

| Pendekatan Perencanaan | Keuntungan | Risiko / Kerugian |
|---|---|---|
| **Back-of-the-Envelope Calculation** | Cepat (5 menit), mengeliminasi ide mustahil, menentukan orientasi arsitektur | Angka adalah estimasi, bukan pengukuran empiris akurat |
| **Simulasi Beban Nyata (Load Testing k6/JMeter)**| 100% presisi mengukur bottleneck kode nyata | Membutuhkan kode aplikasi dan infrastruktur yang sudah selesai dibangun |
| **Tanpa Estimasi Sama Sekali (Tebak-tebakan)** | Nol waktu persiapan di awal | Resiko tagihan cloud bengkak atau sistem tumbang saat launch |

## 13. When To Use
- Pada fase inisiasi arsitektur sebelum memilih database dan platform cloud.
- Menjelang event besar (Flash Sale 12.12, Pemilu, Konser).
- Menentukan anggaran belanja infrastruktur (*Cloud Budget Forecasting*).

## 14. When NOT To Use
- Optimasi kode level mikro (algoritma loop in-memory) — gunakan profiler CPU.

## 15. Common Mistakes
1. **Lupa Memperhitungkan Peak Multiplier**: Mengukur sistem hanya berdasarkan rata-rata QPS harian. Trafik nyata memiliki jam sibuk (jam 19:00 - 21:00) yang bisa mencapai **3x hingga 5x lipat** dari rata-rata!
2. **Mengabaikan Overhead Metadata & Replikasi Database**: Jika data mentah 1 TB, dengan replikasi 3x (Master + 2 Replicas) + B-Tree Indexes (biasanya 50% ukuran tabel), kebutuhan storage nyata adalah:
   $$1 \text{ TB} \times 1.5 \text{ (Index)} \times 3 \text{ (Replikasi)} = 4.5 \text{ TB}!$$
3. **Lupa Perbedaan Bit vs Byte**: Bandwidth jaringan dihitung dalam **bit** (Gbps, Mbps), sedangkan file storage dihitung dalam **Byte** (GB, MB). $1\text{ Byte} = 8\text{ bit}$. Jangan salah membagi angka bandwidth!

## 16. Best Practices
- **Gunakan Prinsip Pareto (80/20 Rule)**: 20% data menyumbang 80% trafik. Jadikan ini acuan ukuran cache memory.
- **Selalu Rencanakan untuk 3 hingga 5 Tahun**: Kapasitas storage harus mampu menampung pertumbuhan organik data tanpa perlu migrasi darurat tahun depan.
- **Sertakan Redundansi & Safety Margin**: Kalikan hasil estimasi kapasitas dengan $1.3$ hingga $1.5$ (safety factor 30-50%).

## 17. Troubleshooting
- **Masalah: Estimasi di atas kertas menunjukkan 10.000 QPS aman, tapi di uji beban server tumbang di 2.000 QPS**.
  - *Sebab*: Estimasi kertas mengasumsikan resource sempurna. Bottleneck tersembunyi biasanya terjadi pada: Connection Pool limit database, Garbage Collection pause di Java/NodeJS, atau Conntrack table Linux penuh.
  - *Solusi*: Lakukan benchmark empiris bertahap (*load testing*) untuk memvalidasi angka estimasi teoritis.

## 18. Hands-on Practice
Mari kita jalankan aplikasi kalkulator kapasitas otomatis (*Automated Capacity Planner CLI*) yang menghitung QPS, Peak QPS, Disk 5 Tahun, Bandwidth Ingress/Egress, dan Ukuran Cache RAM di `hands-on/m01/capacity_calculator.js`.

## 19. Exercises & Challenge
- **Exercise**: Sebuah aplikasi video streaming memiliki 10 juta DAU. Setiap pengguna menonton rata-rata 3 video per hari (ukuran 100 MB per video). Hitung:
  1. Berapa Read QPS rata-rata? (Jawaban: $\frac{30.000.000}{86.400} \approx 347$ video streams/detik).
  2. Berapa total bandwidth egress rata-rata dalam Gbps? (Jawaban: $347 \times 100\text{ MB} \times 8 \approx 277.6\text{ Gbps}$!).
- **Challenge**: Rancang estimasi biaya bulanan di AWS (S3 Storage, EC2 Compute, CloudFront CDN Bandwidth) untuk platform video di atas.

## 20. Summary
Back-of-the-Envelope Estimation adalah keterampilan fundamental seorang Software Architect. Dengan menguasai konversi angka sakti, kaidah Powers of Two, dan latency numbers, Anda dapat menentukan skala sistem, memilih teknologi yang masuk akal, dan mengantisipasi kebutuhan infrastruktur dengan percaya diri.
