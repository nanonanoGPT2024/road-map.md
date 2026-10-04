# Evaluasi Bab 09: Capacity Planning, Performance Engineering, & Chaos Testing

---

## Bagian 1: Basic Questions (5 Soal Pilihan Ganda)

### Soal 1
Berdasarkan Little's Law ($L = \lambda \times W$), jika sebuah sistem menerima rata-rata 2.500 requests per second ($\lambda$) dan rata-rata waktu pemrosesan request adalah 80 milidetik ($W$), berapa rata-rata request yang sedang diproses secara bersamaan ($L$) di dalam sistem tersebut?
- A. 20 request
- B. 200 request
- C. 312 request
- D. 2.000 request

### Soal 2
Menurut Amdahl's Law, jika sebuah program memiliki porsi serial (tidak dapat diparalelkan) sebesar 25%, berapa batas teoritis percepatan performa maksimal (*maximum speedup*) yang dapat dicapai program tersebut sekalipun dialokasikan core CPU tak terbatas?
- A. 2.5x
- B. 4x
- C. 10x
- D. Tidak terbatas

### Soal 3
Apa yang dimaksud dengan fenomena *Coordinated Omission* dalam metodologi load testing?
- A. Tool load testing sengaja mengabaikan response error HTTP 500 dari laporan ringkasan metrik.
- B. Injector pengujian menjeda pengiriman request berikutnya saat sistem downstream melambat, sehingga pengukuran latensi antrean menjadi jauh lebih rendah dari kondisi riil.
- C. Service mesh membagi beban secara tidak seimbang ke pods yang baru dibuat.
- D. Database mengabaikan perintah query commit secara sepihak akibat transaksi paralel yang terlalu tinggi.

### Soal 4
Tujuan utama dari mendefinisikan *Steady State Hypothesis* sebelum menjalankan eksperimen Chaos Engineering adalah:
- A. Memastikan CPU usage dari target pod selalu berada pada level 100%.
- B. Menetapkan baseline indikator kesehatan sistem (SLI/SLO) yang dapat diverifikasi selama dan setelah kegagalan diinjeksi.
- C. Menjamin bahwa cluster Kubernetes tidak akan pernah mengalami crash.
- D. Mengubah konfigurasi production deployment secara permanen menjadi konfigurasi staging.

### Soal 5
Pada Linux kernel level, tool standar yang sering dimanipulasi oleh agent chaos daemon (seperti Chaos Mesh atau Pumba) untuk menginjeksi latensi dan packet drop pada traffic jaringan pod adalah:
- A. `systemd-resolved`
- B. `tc` (Traffic Control) dengan modul `netem`
- C. `modprobe`
- D. `cron`

---

## Bagian 2: Intermediate Questions (5 Soal Analisis Singkat)

### Soal 1
Jelaskan perbedaan mendasar antara Universal Scalability Law (USL) Dr. Neil Gunther dengan Amdahl's Law, khususnya terkait fenomena *retrograde scalability*!

### Soal 2
Mengapa metrik CPU Utilization rata-rata 70% pada kluster Kubernetes microservice terkadang dapat menyembunyikan terjadinya *CPU Throttling* yang parah pada pod aplikasi? Hubungkan jawaban Anda dengan mekanisme Linux CFS (Completely Fair Scheduler) Bandwidth Quota!

### Soal 3
Dalam pengujian beban menggunakan k6, mengapa skenario `constant-arrival-rate` lebih disarankan dibandingkan konfigurasi standar berbasis jumlah Virtual Users (`vus`) untuk menguji ketaatan terhadap SLO?

### Soal 4
Sebutkan tiga guardrail keselamatan (*safety guardrails*) yang mutlak harus dipersiapkan sebelum mengeksekusi injeksi chaos di cluster lingkungan produksi!

### Soal 5
Sebuah pod memiliki Resource Limit CPU: 2 Core dan Memory: 4 GiB. Jika terjadi kebocoran memori (*memory leak*) hingga aplikasi mencoba mengalokasikan 4.2 GiB, apa respon kernel Linux terhadap kontainer tersebut, dan apa bedanya dengan kondisi jika CPU melampaui limit 2 Core?

---

## Bagian 3: Scenario-Based Questions (3 Studi Kasus Industri)

### Kasus 1: The Cascading Connection Collapse
**Kondisi**:
Platform e-commerce Payment Gateway memiliki microservice `order-processor` yang berkomunikasi via HTTP/REST ke `payment-engine`. 
- Saat *flash sale*, `payment-engine` mengalami peningkatan waktu pemrosesan database p99 dari 50ms menjadi 1.200ms karena tingginya disk IOPS lock contention.
- Seketika seluruh pod `order-processor` kehabisan memory, mengalami crash berkali-kali (*OOMKilled*), dan gateway mengembalikan status HTTP 504 Gateway Timeout secara massal ke end-user.

**Pertanyaan Analisis**:
1. Gunakan kalkulasi **Little's Law** untuk menjelaskan mengapa penundaan respon di `payment-engine` secara langsung mematikan `order-processor`!
2. Rancang strategi arsitektural dan konfigurasi timeout/pooling yang dapat mencegah kegagalan cascading ini tanpa perlu menambah kapasitas hardware database!

---

### Kasus 2: Retrograde Scalability pada Database Cluster
**Kondisi**:
Sebuah tim SRE mengamati bahwa kluster basis data terdistribusi multi-master mereka menghasilkan throughput 50.000 QPS dengan 8 node worker. Ketika kluster diperbesar (*scaled out*) menjadi 16 node worker dengan harapan mencapai 100.000 QPS, throughput riil justru turun drastis menjadi 32.000 QPS dan p99 latency melonjak 400%.

**Pertanyaan Analisis**:
1. Jelaskan fenomena di atas dengan menggunakan variabel kontensi ($\sigma$) dan koherensi ($\kappa$) pada **Universal Scalability Law (USL)**!
2. Eksperimen performance engineering apa yang harus dilakukan untuk mengidentifikasi apakah akar masalah terletak pada *network cross-talk synchronization* atau *lock serialization*?

---

### Kasus 3: Game Day Gone Wrong
**Kondisi**:
Tim SRE merencanakan Game Day pertama di staging untuk menguji ketahanan layanan inventaris terhadap pemadaman zona (*Availability Zone failure*). Tim menggunakan Chaos Mesh untuk menginjeksi partisi jaringan (`NetworkChaos` action: `partition`) pada semua node di Zona AZ-a. 
Namun, saat injeksi dimulai, seluruh sistem staging kolaps secara global karena service Discovery (Consul) kehilangan quorum dan gagal memilih master baru (*split-brain*).

**Pertanyaan Analisis**:
1. Mengapa desain eksperimen tersebut melanggar prinsip *Blast Radius Control*?
2. Bagaimana semestinya rancangan *Hypothesis*, *Execution Step*, dan *Emergency Rollback Mechanism* disusun untuk menguji AZ failover secara bertahap dan aman?

---

## Bagian 4: Practical Chapter Challenge

### Judul: End-to-End Resilience Verification Pipeline
Rancang spesifikasi arsitektur dan berkas konfigurasi komprehensif untuk memvalidasi ketahanan microservice `transaction-service`:

**Persyaratan Teknis**:
1. **Target Arsitektur**:
   - `transaction-service` memproses HTTP POST `/transact` dengan target SLO: Error rate < 1%, p95 Latency < 300ms pada beban 2.000 RPS.
   - Bergantung pada Redis Cache (In-cluster) dan PostgreSQL (StatefulSet).

2. **Load Testing Harness**:
   - Buat skrip **k6** yang mengeksekusi *ramping arrival rate* dari 500 RPS hingga 2.500 RPS selama durasi 8 menit.

3. **Chaos Injection Scenario**:
   - Tepat di menit ke-3 (saat RPS mencapai 2.000 RPS), injeksikan degradasi performa menggunakan manifest **Chaos Mesh**:
     - Pod Redis Cache mengalami **network latency 150ms $\pm$ 30ms** dan **packet loss 5%**.
     - Salah satu pod PostgreSQL read-replica dimatikan paksa (*PodChaos* action `pod-kill`).
   - Durasi injeksi berlangsung selama 2 menit.

4. **Deliverables yang Harus Disusun**:
   - Kalkulasi matematis kebutuhan konkurensi normal vs terdegradasi.
   - Skrip `load-test.js` k6 yang menangani coordinated omission.
   - File manifest `chaos-experiment.yaml` (Chaos Mesh CRDs).
   - *Game Day Runbook* ringkas (Rollback trigger condition & verification metric query Prometheus).

---

## Kunci Jawaban & Panduan Penilaian

### Kunci Bagian 1: Basic Questions
1. **B. 200 request** ($L = 2.500 \times 0{,}08 = 200$).
2. **B. 4x** ($S_{max} = \frac{1}{1 - 0{,}75} = \frac{1}{0{,}25} = 4$).
3. **B**. Tool load test menunggu respon sebelum memicu request baru, menyembunyikan efek akumulasi antrean dunia nyata.
4. **B**. Baseline SLI/SLO kondisi normal sebagai acuan mutlak untuk mengukur penyimpangan selama eksperimen.
5. **B**. `tc` (Traffic Control) dengan ekstensi `netem` (network emulator).

### Panduan Solusi Bagian 2 & 3
- **Kasus 1**: Peningkatan latensi downstream dari 0.05s ke 1.2s meningkatkan kebutuhan konkurensi upstream sebesar 24x lipat. Solusi: Circuit Breaker agresif, finite bounded worker queue, HTTP connection pooling dengan fail-fast timeouts.
- **Kasus 2**: Nilai koherensi ($\kappa$) tinggi memicu *crosstalk penalty* kuadratik ($N(N-1)$). Komunikasi antar-node untuk menjaga konsistensi state master mengonsumsi bandwidth dan CPU melebihi kapasitas kerja produktif. Solusi: Sharding partition, Read/Write splitting, atau transisi arsitektur ke leaderless consensus (Dynamo-style) jika relevan.
- **Kasus 3**: Melanggar quorum minimum cluster (N/2 + 1). AZ partition tidak boleh dilakukan langsung 50% jika node berjumlah genap atau tidak tersebar di minimal 3 AZ independen.