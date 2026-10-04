# BAB: Quiz, Challenge, & Knowledge Check
**Fondasi & Arsitektur Site Reliability Engineering (SRE)**

---

## 1. Basic Questions (5 Soal Konseptual & Fundamental)

### Soal 1.1: Dekonstruksi Paradigma SRE vs DevOps vs SysAdmin Tradisional & Manajemen Toil
Dalam dokumen pendirian SRE di Google, Ben Treynor Sloss menyatakan: *"class SRE implements DevOps"*.
1. Jelaskan perbedaan mendasar batas operasional, filosofi penanganan kegagalan (*failure management*), dan metrik keberhasilan antara Traditional Systems Administrator, DevOps Engineer, dan Site Reliability Engineer (SRE).
2. Definisikan secara formal apa yang dimaksud dengan **Toil** menurut standar Google SRE. Sebutkan minimal 4 karakteristik pembeda antara pekerjaan *Toil*, pekerjaan *Overhead Administratif*, dan pekerjaan *Engineering Project Work*.
3. Mengapa SRE menerapkan aturan ketat bahwa alokasi *Toil* maksimal dibatasi $50\%$ dari jam kerja seorang engineer? Jelaskan konsekuensi matematis dan psikologis terhadap tim jika rasio toil melampaui $50\%$ secara persisten (*toil trap*).

### Soal 1.2: Triad Reliabilitas: Anatomi Perbedaan Matematis SLI, SLO, dan SLA
Evaluasi reliabilitas sistem modern bertumpu pada tiga instrumen kuantitatif: Service Level Indicators (SLI), Service Level Objectives (SLO), dan Service Level Agreements (SLA).
1. Tuliskan formula matematika umum dari sebuah SLI berbasis rasio kejadian (*good events vs total valid events*). Mengapa SLI berbasis rasio kejadian (*event-based*) jauh lebih superior dibandingkan SLI berbasis durasi waktu (*time-based uptime/downtime*) pada sistem arsitektur microservices terdistribusi berkepadatan tinggi?
2. Jelaskan mengapa titik pengukuran (*measurement point*) SLI sangat krusial. Bandingkan reliabilitas metrik jika SLI latensi dan error diukur pada:
   - Sisi Klien / Mobile SDK.
   - Edge / Reverse Proxy / API Gateway.
   - Sisi Internal Pod / Container Aplikasi.
   - Log Basis Data / Database Engine.
3. Mengapa dalam perancangan sistem produksi nilai target harus selalu memenuhi hierarki $\text{SLA} < \text{SLO} < \text{SLI Internal}$? Jelaskan fungsi teknis dan bisnis dari selisih margin pengaman (*safety buffer*) antara SLO dan SLA.

### Soal 1.3: Filosofi Embracing Risk & Kegagalan Target Reliabilitas 100%
Dalam prinsip rekayasa keandalan sistem, mengejar reliabilitas $100\%$ dianggap sebagai anti-pattern fatal baik secara teknis maupun finansial.
1. Jelaskan kurva eksponensial *Cost of Reliability* ketika sebuah organisasi mencoba menaikkan ketersediaan sistem dari $99\%$ (Two Nines), $99.9\%$ (Three Nines), hingga $99.999\%$ (Five Nines). Faktor arsitektur apa yang membuat biaya melompat drastis (redundansi multi-region, quorum database, zero-downtime deployment, split-brain mitigation)?
2. Jelaskan konsep *The Law of Diminishing Returns* ditinjau dari sudut pandang *End-User Experience*. Mengapa keandalan backend sebesar $99.999\%$ menjadi sia-sia bagi pengguna aplikasi mobile yang terhubung melalui jaringan seluler atau ISP dengan tingkat reliabilitas $98.5\%$?
3. Bagaimana *Error Budget* mentransformasi ketidakandalan sistem (*unreliability*) dari suatu kegagalan memalukan menjadi sumber daya inovasi terukur (*acceptable budget of risk*)?

### Soal 1.4: Mekanisme Perhitungan Error Budget & Rolling Window vs Calendar Window
Diberikan sebuah layanan *Order Processing Service* yang memproses rata-rata $25.000.000$ transaksi HTTP per bulan dengan target SLO Ketersediaan (*Availability*) sebesar $99.95\%$ dan target SLO Latensi sebesar $99\%$ dari request sukses diselesaikan dalam waktu $\le 200\text{ms}$.
1. Hitung secara presisi kuota absolut *Error Budget* (dalam jumlah request gagal) yang diizinkan untuk ketersediaan layanan tersebut selama periode 30 hari.
2. Bandingkan kelebihan dan kelemahan operasional antara penggunaan **Rolling Window** (misalnya jendela geser 30 hari atau 720 jam) dibandingkan **Calendar-Aligned Window** (tanggal 1 hingga akhir bulan kalender).
3. Mengapa sistem evaluasi berbasis *Calendar Window* rentan menimbulkan perilaku disfungsional tim (*gaming the system*) di akhir bulan atau kepanikan rilis di awal bulan (*cliff-edge reset*)?

### Soal 1.5: Siklus Hidup Kebijakan Error Budget (Error Budget Policy) & Release Gating
Error Budget bukanlah sekadar metrik pelaporan pasif di dashboard, melainkan kontrak operasional yang mengendalikan siklus deployment.
1. Rancang sebuah *Error Budget Policy* berjenjang (misal: saat sisa budget $> 50\%$, $25\% - 50\%$, $0\% - 25\%$, dan $\le 0\%$). Tindakan konkret apa yang wajib dieksekusi oleh tim developer dan SRE pada masing-masing tingkatan tersebut?
2. Apa yang dimaksud dengan **Deployment Freeze** / **Reliability Sprint** saat Error Budget telah habis terpakai ($EB \le 0\%$)? Pekerjaan teknis apa saja yang secara sah diizinkan masuk ke dalam lingkungan produksi selama masa pembekuan rilis fitur?
3. Siapakah pihak yang memiliki otoritas untuk memberikan *Exception Waiver* (pemberian dispensasi rilis darurat di saat Error Budget negatif), dan apa kriteria ketat agar waiver tersebut dapat disetujui tanpa merusak budaya reliabilitas organisasi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Analisis Sistem)

### Soal 2.1: Matematika Multi-Window Multi-Burn-Rate Alerting (MWMRA) & Mitigasi Alert Fatigue
Pendekatan alerting tradisional berbasis ambang batas tunggal (misalnya: `alert jika error rate > 1% selama 5 menit`) terbukti gagal di lingkungan produksi berskala besar karena memicu badai *false positive* saat traffic rendah dan mengabaikan *slow burn* saat traffic tinggi.
1. Tuliskan formula matematika untuk menghitung *Burn Rate* ($BR$) berdasarkan nilai SLI aktual dan SLO target.
2. Jika sebuah layanan memiliki SLO ketersediaan 30 hari sebesar $99.9\%$, tentukan berapa lama waktu yang dibutuhkan hingga seluruh Error Budget habis jika sistem mengalami anomali dengan:
   - Burn Rate $BR = 1$
   - Burn Rate $BR = 14.4$
   - Burn Rate $BR = 36$
3. Bedah cara kerja algoritma **Multi-Window Multi-Burn-Rate Alerting (MWMRA)** Google SRE. Mengapa algoritma ini mewajibkan evaluasi simultan pada dua jendela waktu (*Long Window* dan *Short Window*, misal: 1 jam dan 5 menit) untuk memicu pager darurat (P1)? Bagaimana evaluasi dua jendela ini secara deterministik menyaring lonjakan error transien (*transient error spike*)?

### Soal 2.2: Fenomena Tail Latency Amplification pada Arsitektur Fan-Out Microservices
Dalam arsitektur microservices terdistribusi, satu request pengguna di API Gateway sering kali dipecah (*fan-out*) menjadi puluhan hingga ratusan sub-request ke microservice backend secara paralel.
1. Jika sebuah endpoint API Gateway melakukan *fan-out* ke $100$ layanan independen secara paralel, dan masing-masing layanan memiliki probabilitas $99\%$ menyajikan request dalam batas latensi normal (hanya $1\%$ sub-request mengalami lonjakan latensi / $p99$), hitunglah probabilitas bahwa request pengguna akhir di API Gateway akan terhambat oleh anomali latensi ekor (*tail latency*)!
2. Jelaskan mengapa optimasi rata-rata latensi (*mean/average latency*) tidak relevan dalam sistem terdistribusi skala besar, dan mengapa tim SRE selalu mewajibkan pengukuran menggunakan distribusi persentil tingkat tinggi ($p95$, $p99$, $p99.9$)?
3. Jelaskan dua mekanisme mitigasi latensi ekor berikut:
   - **Hedged Requests**: Cara kerja pengiriman request paralel kedua setelah melampaui persentil tertentu, serta bagaimana mekanisme pembatalan (*cancellation signal*) mencegah pemborosan resource downstream.
   - **Context Deadlines / Distributed Cancellation Propagation**: Bagaimana deadline ditransmisikan melintasi batas RPC (gRPC / HTTP tracing headers) sehingga downstream service tidak melanjutkan eksekusi komputasi yang hasilnya sudah tidak ditunggu oleh gateway pemanggil.

### Soal 2.3: State Machine Circuit Breaker & Adaptive Concurrency Limiting
Dua pola resiliensi krusial untuk mencegah degradasi layanan adalah *Circuit Breaker* dan *Adaptive Concurrency Limiting*.
1. Gambarkan diagram *State Machine* dari pola **Circuit Breaker** yang mencakup state: `CLOSED`, `OPEN`, dan `HALF-OPEN`. Jelaskan parameter transisi antar-state (Failure Rate Threshold, Slow Call Threshold, Wait Duration in Open State, dan Permitted Number of Calls in Half-Open State).
2. Apa perbedaan mendasar antara *Static Rate Limiting* (misal: membatasi hard limit 1000 RPS per instance) dengan **Adaptive Concurrency Limiting** berbasis algoritma adaptif (seperti TCP Vegas atau Netflix Concurrency Limits)?
3. Jelaskan penerapan **Hukum Little** (*Little's Law*):
   $$L = \lambda \times W$$
   di mana $L$ adalah *Concurrency/In-flight requests*, $\lambda$ adalah *Throughput*, dan $W$ adalah *Latency/Response Time*. Bagaimana penumpukan antrean (*bufferbloat*) di layer aplikasi menyebabkan latensi ($W$) meroket tanpa menambah throughput ($\lambda$), dan bagaimana pembatasan konkurensi adaptif mengembalikan sistem ke titik efisiensi optimal?

### Soal 2.4: Arsitektur Load Shedding & Request Prioritization di Edge Layer
Ketika sebuah sistem mengalami kelebihan beban ekstrem (*extreme overload*) yang melebihi batas elastisitas autoscaler, sistem harus mempertahankan ketersediaan parsial melalui *Load Shedding*.
1. Jelaskan prinsip kerja *Load Shedding*. Mengapa menolak sebagian request secara cepat dengan error code HTTP 503 / 429 jauh lebih baik bagi stabilitas sistem daripada membiarkan seluruh request masuk ke dalam antrean memory (*in-memory queue*)?
2. Bagaimana perancangan mekanisme klasifikasi request berbasis prioritas (*request prioritization*) di layer Ingress/Reverse Proxy? Kategorikan request ke dalam minimal 3 tier:
   - **Tier 1 (Critical):** Transaksi checkout, autentikasi sesi, verifikasi pembayaran.
   - **Tier 2 (High / Degraded):** Pencarian katalog, load dashboard profil.
   - **Tier 3 (Sheddable / Low):** Rekomendasi produk berbasis AI, analitik background sync, telemetry logging.
3. Bagaimana mekanisme *CoDel (Controlled Delay)* atau evaluasi *Queue Ingress Timestamp* digunakan untuk menjatuhkan (*drop*) request yang sudah kedaluwarsa di dalam antrean sebelum sempat diproses oleh worker thread?

### Soal 2.5: Automated Canary Analysis (ACA) Berbasis Evaluasi SLI/Error Budget
Dalam arsitektur Continuous Delivery modern, rilis canary tidak boleh lagi dievaluasi secara manual melalui inspeksi mata pada grafik dashboard.
1. Jelaskan alur kerja teknis **Automated Canary Analysis (ACA)** menggunakan platform seperti Argo Rollouts atau Spinnaker/Kayenta yang terintegrasi dengan Prometheus.
2. Mengapa pengujian statistik seperti **Mann-Whitney U Test** atau **Kolmogorov-Smirnov Test** digunakan dalam membandingkan distribusi performa metrik pod *Baseline* (versi lama) dan pod *Canary* (versi baru), alih-alih hanya membandingkan selisih nilai absolut rata-rata?
3. Rancang sebuah aturan kebijakan rilis canary: metrik SLI apa saja yang harus dijadikan parameter penentu kegagalan, berapa ambang batas deviasi yang memicu pembatalan otomatis (*auto-rollback*), dan bagaimana kegagalan canary dicatat ke dalam audit konsumsi Error Budget?

---

## 3. Production Scenario-Based Questions (3 Skenario Kasus Produksi Nyata)

### Skenario 3.1: Badai Retry, Kegagalan Kaskade (Cascading Failure), dan Thundering Herd pada Payment Gateway
**Latar Belakang Kasus:**
Pada saat kampanye diskon tanggal kembar (*Mega Flash Sale*), sebuah microservice `Checkout-Service` memanggil pihak ketiga `Vendor-Payment-API` secara sinkron melalui HTTP client. Tiba-tiba, `Vendor-Payment-API` mengalami degradasi internal: latensi respons meningkat dari rata-rata $120\text{ms}$ menjadi $5500\text{ms}$, dengan error rate HTTP 500 melonjak hingga $35\%$.
Implementasi HTTP client di `Checkout-Service` dikonfigurasi dengan:
- HTTP Timeout: $10\text{ detik}$.
- Retry Policy: $3\text{ kali retry berturut-turut}$ secara instan (tanpa backoff dan tanpa jitter) setiap kali menerima status selain 200 OK.
- Tomcat/Netty Worker Thread Pool: Maksimal $200\text{ worker threads}$ per instance.

**Dampak Lapangan:**
Dalam waktu 90 detik:
1. Seluruh 200 worker threads di setiap pod `Checkout-Service` terkunci (*exhausted*) menunggu respons lambat dari payment vendor.
2. Endpoint `/healthz` internal pod tidak lagi merespons dalam batas waktu liveness probe Kubernetes ($3\text{ detik}$).
3. Kubelet mendeteksi pod tidak sehat dan mematikan pod secara serentak (*restart storm*).
4. Saat pod baru menyala, ribuan antrean request yang menumpuk di Ingress langsung membanjiri instance baru (*Thundering Herd*), menyebabkan pod baru langsung mati kembali (*CrashLoopBackOff*).
5. Layanan upstream lain (`Cart-Service`, `Order-Service`) yang memanggil `Checkout-Service` ikut kehabisan koneksi soket, melumpuhkan seluruh platform e-commerce secara total.

**Tugas Evaluasi & Remediasi:**
1. **Analisis Akar Masalah (Root Cause Analysis):** Uraikan secara rinci 4 kesalahan arsitektural fatal pada konfigurasi timeout, retry, resource pooling, dan health check yang memicu amplifikasi kegagalan kaskade tersebut.
2. **Kalkulasi Amplifikasi Beban:** Jika terdapat $2.000\text{ RPS}$ request checkout awal, hitung berapa total beban request teoritis yang dikirimkan ke payment vendor per detik akibat kebijakan retry tanpa backoff tersebut!
3. **Desain Perbaikan Arsitektur Komprehensif:**
   - Rancang ulang mekanisme retry menggunakan **Exponential Backoff dengan Full Jitter**. Tuliskan formula matematis penentuan interval jedanya.
   - Konfigurasikan integrasi **Circuit Breaker** (State: Closed, Open, Half-Open) agar traffic ke vendor langsung diputus saat error rate melampaui $20\%$ dalam sliding window 10 detik.
   - Pisahkan thread/connection pool antara trafik checkout eksternal dan endpoint health check internal (**Bulkhead Pattern**).
   - Rancang mekanisme asinkron berbasis message broker (outbox pattern / transactional queue) sebagai fallback saat circuit breaker berstatus OPEN.

---

### Skenario 3.2: Kebocoran Lambat (Slow-Burn Leak) Akibat Regresi Alokasi Memori dan Kebutaan Alerting Statis
**Latar Belakang Kasus:**
Tim backend merilis patch v2.4.1 untuk layanan `Catalog-Search-Service` yang ditulis menggunakan Go. Patch tersebut menambahkan fitur caching internal di memory menggunakan `sync.Map` tanpa mekanisme batas entri maksimum (*unbounded cache*) dan time-to-live (TTL).
Kondisi operasional layanan:
- SLO Ketersediaan (30 hari rolling): $99.9\%$.
- Monitoring Alerting yang terpasang di Prometheus Alertmanager saat itu hanya satu aturan statis:
  ```yaml
  alert: HighHttpErrorRate
  expr: (sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))) > 0.02
  for: 5m
  labels:
    severity: page
  ```

**Dampak Lapangan:**
1. Karena memori bocor secara perlahan, latency p99 mulai merangkak naik dari $45\text{ms}$ menjadi $350\text{ms}$ akibat naiknya frekuensi dan durasi *Garbage Collection (GC) STW (Stop-The-World) pause*.
2. Sekitar $0.08\%$ dari total request mengalami error timeout (HTTP 504) karena jeda GC tersebut.
3. Karena rasio error ($0.08\%$) berada jauh di bawah ambang batas alert statis ($2\%$), **tidak ada pager alert yang berbunyi selama 12 hari berturut-turut**.
4. Namun, bagi SLO target $99.9\%$, toleransi error hanya $0.1\%$. Rasio error sebesar $0.08\%$ setara dengan **Burn Rate $BR = 0.8$**, yang mengonsumsi hampir $35\%$ dari total Error Budget bulanan secara diam-diam.
5. Pada hari ke-13, volume pencarian naik $3\times$ lipat pada awal gajian. Memory heap menabrak cgroup limit ($2\text{GB}$), memicu kernel Linux mengeksekusi `OOM Killer` (Exit Code 137) pada seluruh pod secara massal dan simultan. Error rate melonjak ke $100\%$ dan menghabiskan sisa Error Budget hingga minus $240\%$ dalam 45 menit.

**Tugas Evaluasi & Remediasi:**
1. **Analisis Kegagalan Observabilitas:** Jelaskan mengapa alert statis 5 menit mengalami *kebutaan observabilitas* (*blind spot*) terhadap regresi performa berbasis slow-burn.
2. **Implementasi MWMRA PromQL:** Rancang aturan alerting Prometheus berbasis **Multi-Window Multi-Burn-Rate Alerting (MWMRA)** untuk mendeteksi kondisi slow burn (misalnya: konsumsi $10\%$ budget dalam 3 hari, $BR \approx 1$) dan kondisi fast burn (konsumsi $2\%$ budget dalam 1 jam, $BR \approx 14.4$). Tuliskan ekspresi PromQL lengkap untuk jendela evaluasi long-window dan short-window!
3. **Eksekusi Error Budget Policy:** Karena Error Budget telah habis hingga minus $240\%$, susun rencana tata kelola rilis (*governance*) formal yang harus dipresentasikan kepada manajemen engineering, mencakup pembekuan rilis fitur, audit heap profiling (`pprof`), dan integrasi automated profiling ke dalam pipeline CI/CD.

---

### Skenario 3.3: Konflik Kepentingan Bisnis vs Stabilitas: Krisis Peluncuran Fitur Q4 pada Sisa Error Budget Negatif
**Latar Belakang Kasus:**
Layanan `Core-Banking-Ledger` merupakan tulang punggung platform fintech multi-nasional. Dalam 3 minggu pertama bulan Oktober, layanan tersebut mengalami 2 kali insiden degradasi performa berat yang disebabkan oleh dead-lock pada database cluster:
- Kuota Error Budget bulanan: $0.05\%$ (Target SLO Availability $99.95\%$).
- Error Budget aktual yang tersisa: **$-42\%$** (Budget telah habis terbakar dan berstatus defisit).
Sesuai dengan dokumen **Error Budget Policy** yang telah ditandatangani oleh CTO dan Head of Engineering:
> *"Apabila Error Budget mencapai $\le 0\%$, seluruh pipeline deployment fitur baru untuk layanan terkait wajib dibekukan (Feature Freeze), dan alokasi sprint engineering 100% dialihkan untuk perbaikan reliabilitas, technical debt, dan automated testing."*

**Dilema Bisnis & Konflik:**
Tiga hari sebelum akhir bulan, VP of Product dan Chief Commercial Officer (CCO) mengajukan permohonan darurat untuk merilis modul baru: `Auto-Invest-Recurring`.
Argumen dari pihak Bisnis/Produk:
- Modul ini telah dijanjikan kepada investor publik dan mitra perbankan dengan target peluncuran Q4.
- Keterlambatan peluncuran akan menimbulkan potensi kerugian komersial langsung sebesar $\$1.500.000$ dan penalti regulasi kepatuhan jadwal.
- Tim developer menjamin bahwa kode fitur baru telah diuji di lingkungan staging dengan test coverage $92\%$.
- CCO meminta SRE untuk mengabaikan aturan Error Budget Policy *"hanya untuk kali ini saja"* (*one-time exception*).

**Tugas Evaluasi & Arbitrasi SRE:**
1. **Posisi Prinsip SRE:** Sebagai Principal SRE / Head of Reliability, bagaimana Anda merespons tekanan bisnis tersebut secara objektif tanpa bersikap defensif, konfrontatif, atau sekadar menjadi *"tim penolak"* (*gatekeeper blocker*)?
2. **Kuantifikasi Risiko (Risk Quantification):** Rumuskan metode kuantifikasi risiko teknis ke dalam terminologi dampak finansial dan reputasi bisnis. Jika modul baru dirilis dan memicu insiden downtime sebesar 30 menit pada `Core-Banking-Ledger`, hitung estimasi kerugian transaksi, potensi denda SLA regulator, dan implikasinya terhadap reputasi brand.
3. **Rancangan Kerangka Kompensasi & Mitigasi (Compensating Controls):** Jika eksekutif level (CTO/CEO) tetap memutuskan untuk mengeksekusi *Executive Exception Waiver*, rancang arsitektur peluncuran bersyarat dengan risiko terkontrol (*controlled blast radius*):
   - Mekanisme **Dark Launching** dan evaluasi performa tanpa melayani transaksi riil.
   - Penerapan **Feature Flag Dinamis** dengan kemampuan *instant kill-switch* berbasis webhook alert Prometheus jika latensi naik $> 5\%$.
   - **Targeted Canary Cohort**: Membatasi rilis hanya untuk $1\%$ pengguna internal / beta tester selama 72 jam pertama.
   - Dokumen *Formal Accountability Sign-off* yang mencatat persetujuan risiko oleh stakeholder bisnis.

---

## 4. Practical Chapter Challenge: Membangun Resilience Engine & Error Budget Gatekeeper ("SRE-Sentinel")

### Deskripsi Proyek
Anda diminta merancang dan mengimplementasikan sebuah sistem supervisor keandalan mini bernama **`sre-sentinel`**. Sistem ini bertindak sebagai jembatan otomatis antara observabilitas metrik produksi dan pipeline deployment CI/CD untuk menegakkan *Error Budget Policy* dan *Resilience Control*.

```
+-----------------------------------------------------------------------------------+
|                              SRE-SENTINEL ARCHITECTURE                            |
|                                                                                   |
|  [Prometheus Metrics] --------> [Metrics Ingestion & SLI/MWMRA Calculator]       |
|                                                     |                             |
|                                                     v                             |
|  [CI/CD Deployment Request] ---> [Error Budget Gatekeeper Engine]                |
|                                         |                  |                      |
|                               [EB > 0: PASS]         [EB <= 0: REJECT]            |
|                                         |                  |                      |
|                                         v                  v                      |
|                                  [Deploy Canary]    [Block & Notify Slack]        |
|                                         |                                         |
|                                         v                                         |
|  [Incoming HTTP Traffic] ------> [Adaptive Concurrency Limiter & Circuit Breaker] |
|                                         |                                         |
|                                         v                                         |
|                               [Protected Backend Service]                         |
+-----------------------------------------------------------------------------------+
```

### Spesifikasi Kebutuhan & Deliverables

#### Modul 1: Mesin Kalkulator SLI, SLO, dan Multi-Burn-Rate (MWMRA)
Bangun modul logic (menggunakan Python, Go, atau shell script terstruktur) yang mampu:
1. Menerima data metrik deret waktu (*time-series*) yang berisi: `timestamp`, `http_status`, dan `latency_ms`.
2. Menghitung kriteria *Good Events*:
   $$\text{Good Event} = (\text{HTTP Status} < 500) \land (\text{Latency} \le 200\text{ms})$$
3. Menghitung persentase SLI aktual terhadap target SLO yang ditentukan (misal: $99.9\%$).
4. Menghitung sisa *Error Budget* dalam persen dan jumlah request.
5. Menghitung nilai *Burn Rate* pada dua jendela waktu:
   - Jendela Panjang (*Long Window*): 1 jam
   - Jendela Pendek (*Short Window*): 5 menit
6. Mengeluarkan status alert:
   - `HEALTHY`: Burn Rate normal ($BR < 1.0$)
   - `WARNING`: Konsumsi lambat terdeteksi ($1.0 \le BR < 6.0$)
   - `CRITICAL_P1`: Terjadi pembakaran cepat ($BR \ge 14.4$ pada *Long* DAN *Short Window* simultan)

#### Modul 2: CLI Release Gatekeeper untuk Pipeline CI/CD
Bangun sebuah utilitas baris perintah (`sentinel-gate`) yang diintegrasikan ke dalam pipeline GitHub Actions / GitLab CI:
1. **Input Flags:**
   - `--service-id=<name>`: Identitas microservice yang akan dideploy.
   - `--sli-endpoint=<url>`: Endpoint penyedia data metrik / Prometheus query.
   - `--slo-target=<float>`: Target SLO (misal: `0.999`).
   - `--allow-override`: Flag boolean untuk bypass darurat.
   - `--waiver-token=<hash>`: Token verifikasi jika override diaktifkan.
2. **Evaluasi Kebijakan (Policy Decision):**
   - Jika sisa *Error Budget* $> 0\%$ dan tidak ada alert `CRITICAL_P1`: Kembalikan `Exit Code 0` (Deploy Diizinkan).
   - Jika sisa *Error Budget* $\le 0\%$: Cetak laporan rincian defisit budget ke `stderr` dan kembalikan `Exit Code 1` (Pipeline Dibatalkan / Gated).
   - Jika `--allow-override` disertakan, verifikasi validitas `--waiver-token` terhadap format SHA-256 terdaftar; jika valid kembalikan `Exit Code 0` dengan log audit peringatan risiko ke standard output.

#### Modul 3: Simulator Adaptive Concurrency Limiter & Circuit Breaker
Buat sebuah middleware / interceptor proxy mandiri yang melindungi downstream service dari saturasi:
1. **Adaptive Concurrency Limit (Gradient / Vegas Algorithm):**
   - Hitung latensi dasar tanpa beban (*no-load latency* / $RTT_{\text{min}}$).
   - Ukur latensi aktual saat ini ($RTT_{\text{actual}}$).
   - Hitung rasio gradien:
     $$\text{Gradient} = \frac{RTT_{\text{min}}}{RTT_{\text{actual}}}$$
   - Sesuaikan batas konkurensi dinamis ($Limit_{\text{new}}$):
     $$Limit_{\text{new}} = Limit_{\text{old}} \times \text{Gradient} + \text{Headroom}$$
   - Jika jumlah in-flight request melebihi limit dinamis, tolak request secara instan (*shed load*) dengan status `HTTP 503 Service Unavailable`.
2. **Circuit Breaker State Engine:**
   - Implementasikan state `CLOSED`, `OPEN`, dan `HALF-OPEN`.
   - Buka sirkuit (`OPEN`) jika failure rate $> 30\%$ dalam 20 request terakhir.
   - Pada state `OPEN`, langsung kembalikan fallback respons dalam waktu $< 2\text{ms}$ tanpa menyentuh backend.
   - Masuk ke state `HALF-OPEN` setelah jeda cooldown 5 detik untuk menguji 3 request sampel.

### Format Pengujian & Bukti Eksekusi (Verification Criteria)
Implementasi sistem Anda harus dibuktikan dengan skenario pengujian terotomatisasi:
1. **Uji Simulasi Normal:** Alirkan 1.000 request dengan error rate $0.05\%$. Verifikasi gatekeeper meloloskan deployment (`Exit Code 0`).
2. **Uji Simulasi Defisit Error Budget:** Alirkan 1.000 request dengan error rate $5\%$. Verifikasi gatekeeper memblokir deployment (`Exit Code 1`) dan mencetak detail pembakaran error budget.
3. **Uji Beban Ekstrem & Load Shedding:** Alirkan traffic berlebih hingga latensi backend naik dari 20ms menjadi 500ms. Buktikan bahwa Adaptive Concurrency Limiter secara otomatis memangkas inflight requests dan menjaga pod backend agar tidak crash.
4. **Uji Circuit Breaker Tripping:** Suntikkan error 100% pada backend. Buktikan sirkuit berpindah ke state `OPEN` dan menghentikan pengiriman beban ke backend dalam waktu kurang dari 1 detik.

---

## 5. Knowledge Check & Mastery Checklist

Gunakan daftar periksa mandiri ini untuk mengaudit penguasaan Anda terhadap konsep inti, formulasi matematika, dan praktik arsitektur Site Reliability Engineering (SRE) pada Bab 01.

### Konsep Fundamental & Teoretis:
- [ ] Saya mampu menjelaskan perbedaan formal batasan peran, KPI/OKR, dan pendekatan operasional antara Traditional SysAdmin, DevOps, dan SRE.
- [ ] Saya memahami mengapa ketersediaan sistem $100\%$ adalah target yang salah dan merusak inovasi bisnis (*Embracing Risk*).
- [ ] Saya memahami definisi presisi dari *Toil*, batasan alokasi maksimal $50\%$, serta strategi sistematis mengeliminasinya melalui rekayasa perangkat lunak.
- [ ] Saya mampu membedakan SLI (indikator aktual), SLO (target internal), dan SLA (perjanjian hukum dengan penalti finansial).
- [ ] Saya memahami alasan mengapa SLI wajib diukur sedekat mungkin dengan pengguna akhir (*user-centric measurement*).
- [ ] Saya memahami konsep matematika *Error Budget* ($EB = 1 - \text{SLO}$) dan fungsinya sebagai penyeimbang antara kecepatan rilis fitur dan stabilitas.
- [ ] Saya memahami dampak perbedaan penggunaan *Rolling Window* versus *Calendar-Aligned Window* dalam evaluasi SLO.

### Mekanisme Internal & Arsitektur Resiliensi:
- [ ] Saya mampu menghitung *Burn Rate* ($BR$) secara matematis dan memahami implikasi kecepatan penghabisan kuota Error Budget.
- [ ] Saya memahami kelemahan fatal sistem alerting berbasis ambang batas tunggal statis (*Single Threshold Alerting*).
- [ ] Saya memahami prinsip kerja algoritma *Multi-Window Multi-Burn-Rate Alerting (MWMRA)* dan perannya dalam mengeliminasi false alarm sekaligus mendeteksi slow-burn leaks.
- [ ] Saya memahami fenomena *Tail Latency Amplification* pada arsitektur microservices terdistribusi dan cara mitigasinya menggunakan *Hedged Requests* serta *Context Deadlines*.
- [ ] Saya menguasai cara kerja pola *Circuit Breaker* (transisi state `CLOSED`, `OPEN`, `HALF-OPEN`) untuk memotong rantai kegagalan kaskade (*cascading failures*).
- [ ] Saya memahami formulasi Hukum Little ($L = \lambda W$) dan prinsip kerja *Adaptive Concurrency Limiting* untuk mencegah fenomena *bufferbloat*.
- [ ] Saya memahami strategi *Load Shedding* berbasis prioritas (Tier 1 vs Tier 2 vs Tier 3) saat sistem mengalami saturasi beban total.
- [ ] Saya memahami integrasi *Automated Canary Analysis (ACA)* ke dalam pipeline CI/CD berbasis uji statistik distribusi metrik.

### Keterampilan Praktis & Operasional Produksi:
- [ ] Saya mampu merumuskan spesifikasi dokumen SLI/SLO yang presisi untuk layanan berbasis API HTTP, gRPC, maupun Message Processing Queue.
- [ ] Saya mampu menuliskan query PromQL untuk menghitung ketersediaan SLI dan Multi-Burn-Rate Alerting di Prometheus.
- [ ] Saya mampu merancang dokumen *Error Budget Policy* formal yang mengatur aturan eskalasi, *Feature Freeze*, dan alokasi *Reliability Sprints*.
- [ ] Saya mampu merancang strategi retry yang aman menggunakan *Exponential Backoff* dan *Full Jitter* untuk mencegah badai trafik (*Thundering Herd*).
- [ ] Saya mampu bertindak sebagai *Incident Commander* atau memimpin sidang mediasi arbitrase teknis ketika terjadi benturan kepentingan antara *product velocity* dan stabilitas sistem.

```text
Checklist Kesiapan BAB 01 — Fondasi & Arsitektur SRE:
[ ] Modul 01: Memahami konsep fundamental SLI, SLO, SLA, Toil, dan Error Budget.
[ ] Modul 02: Menguasai MWMRA, arsitektur resiliensi terdistribusi, dan pola mitigasi kaskade.
[ ] Evaluasi: Menyelesaikan 5 Soal Basic dan 5 Soal Intermediate dengan pemahaman mendalam.
[ ] Studi Kasus: Menguasai analisis dan penyelesaian 3 Skenario Kasus Produksi Nyata.
[ ] Praktikum: Menyelesaikan dan menguji implementasi Chapter Challenge SRE-Sentinel.
```
