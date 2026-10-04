# Evaluasi Bab 09: Telemetry, Observability & Cloud Financial Ops (FinOps)

---

## 1. Basic Questions (Pilihan Ganda & Konseptual Singkat)

### Soal 1
Fitur apa pada Amazon CloudWatch yang memungkinkan penggabungan beberapa ekspresi matematika terhadap time-series metrik untuk menghitung rasio seperti *Error Budget Consumption*?
- A. CloudWatch Logs Insights
- B. CloudWatch Metric Math
- C. CloudWatch ServiceLens
- D. CloudWatch Container Insights

### Soal 2
Bagaimana AWS X-Ray membedakan batas-batas layanan komputasi eksternal (misal: panggilan database DynamoDB atau downstream HTTP API pihak ketiga) di dalam trace request yang sama?
- A. Segments
- B. Sampling Rules
- C. Subsegments
- D. Trace Annotations

### Soal 3
Mekanisme keamanan apa yang digunakan oleh AWS CloudTrail untuk membuktikan bahwa sebuah file log audit tidak mengalami manipulasi, penghapusan, atau modifikasi ilegal setelah ditulis ke bucket S3?
- A. S3 Server-Side Encryption (SSE-S3)
- B. Log File Validation menggunakan digest files berbasis hashing SHA-256
- C. AWS Shield Advanced
- D. CloudTrail Insights anomaly tracking

### Soal 4
Tipe Savings Plans manakah yang memberikan diskon hingga 66% dan secara otomatis berlaku untuk penggunaan EC2 di sembarang famili, tipe sistem operasi, tenancy, Region, serta berlaku juga untuk AWS Fargate dan AWS Lambda?
- A. EC2 Instance Savings Plans
- B. Amazon SageMaker Savings Plans
- C. Compute Savings Plans
- D. Convertible Reserved Instances

### Soal 5
Pada tools FinOps *Infracost*, kapan estimasi delta biaya infrastruktur dievaluasi dalam alur siklus hidup rekayasa perangkat lunak modern?
- A. Setelah `terraform apply` selesai dijalankan di cluster production.
- B. Secara berkala tiap akhir bulan saat tagihan AWS keluar.
- C. Sebelum deployment, langsung pada pull request code review saat evaluasi IaC Terraform.
- D. Saat audit laporan keuangan tahunan oleh tim Finance.

---

### Kunci Jawaban & Penjelasan Bagian 1:
1. **B. CloudWatch Metric Math** — Metric Math menyediakan kemampuan kalkulasi numerik dan formula matematika dinamis lintas metrik tanpa memerlukan custom data ingestion pipeline.
2. **C. Subsegments** — Segments mewakili komponen penyedia komputasi utama, sedangkan subsegments menyediakan rincian granular mengenai pemanggilan downstream remote dependencies, SQL queries, atau remote HTTP APIs.
3. **B. Log File Validation menggunakan digest files berbasis hashing SHA-256** — CloudTrail menerbitkan digest files yang memuat tanda tangan kriptografis dan hash dari file log yang baru disimpan ke S3.
4. **C. Compute Savings Plans** — Memberikan fleksibilitas tertinggi lintas famili komputasi (EC2, Fargate, Lambda) serta lokasi Region.
5. **C. Sebelum deployment, langsung pada pull request code review saat evaluasi IaC Terraform** — Infracost mengimplementasikan prinsip *shift-left FinOps* dengan mem-parsing kode Terraform untuk memperlihatkan implikasi biaya sebelum resource di-provision.

---

## 2. Intermediate Questions (Analisis Kasus & Algoritma)

### Soal 1: CloudWatch Insights Aggregation
Sebuah aplikasi web memancarkan log terstruktur dengan field: `statusCode`, `latencyMs`, dan `path`. Tuliskan query CloudWatch Logs Insights untuk menemukan 5 path API yang memiliki latensi p99 terburuk untuk response code 200, beserta jumlah request-nya, selama 1 jam terakhir.

### Soal 2: Composite Alarms vs Single Alarms
Jelaskan kelemahan menggunakan satu alarm statis berbasis batas memori (`MemoryUtilization > 85%`) pada auto-scaling group container ECS, dan bagaimana Composite Alarm dapat mencegah alarm palsu saat proses deployment bergulir (*rolling deployment*).

### Soal 3: X-Ray Sampling Rules Configuration
Diberikan konfigurasi JSON rule AWS X-Ray berikut:
```json
{
  "RuleName": "PaymentServiceRule",
  "Priority": 10,
  "ReservoirSize": 50,
  "FixedRate": 0.05,
  "Host": "*",
  "HTTPMethod": "POST",
  "URLPath": "/api/v1/checkout"
}
```
Jika endpoint `/api/v1/checkout` menerima rata-rata 200 request per detik secara stabil, berapa banyak request yang akan di-sample dan dikirimkan ke AWS X-Ray setiap detiknya?

### Soal 4: FinOps Commitment Coverage Analysis
Sebuah perusahaan menggunakan komputasi EC2 dengan pengeluaran eceran On-Demand stabil sebesar $100/jam selama 24 jam sehari, 7 hari seminggu. Mereka memutuskan membeli Compute Savings Plans dengan komitmen sebesar $50/jam. Jika diskon komitmen rata-rata adalah 40% (artinya $1 pengeluaran On-Demand setara dengan $0.60 pada rate Savings Plans):
- Berapa nilai equivalent On-Demand usage yang diserap oleh komitmen $50/jam tersebut?
- Berapa sisa penggunaan On-Demand yang masih harus dibayar dengan tarif eceran penuh setiap jamnya?

### Soal 5: CloudTrail Log Data Exclusions
Mengapa praktik logging semua event `s3:GetObject` pada bucket media publik yang melayani jutaan hit harian dianggap sebagai kesalahan arsitektural fatal baik dari sisi performa maupun FinOps? Solusi arsitektur apa yang lebih efisien?

---

### Kunci Jawaban & Penjelasan Bagian 2:

#### Solusi 1:
```sql
fields path, latencyMs, statusCode
| filter statusCode = 200
| stats count(*) as TotalRequests, pct(latencyMs, 99) as p99Latency by path
| sort p99Latency desc
| limit 5
```

#### Solusi 2:
Memory utilization container sering kali meningkat secara normal karena alokasi runtime heap (misal JVM atau NodeJS) atau saat container baru diinisialisasi bersamaan selama rolling deployment. Menggunakan satu alarm statis memori akan memicu notifikasi palsu (*false positive*). Dengan Composite Alarm, aturan disetel menjadi:
`ALARM(HighMemoryUtilization) AND ALARM(HighResponseLatency) AND NOT ALARM(DeploymentInProgress)`. Ini menjamin SRE hanya dihubungi jika lonjakan konsumsi memori memang berkorelasi dengan degradasi performa nyata dan bukan akibat aktivitas deployment rutin.

#### Solusi 3:
- Reservoir menjamin 50 request pertama per detik pasti di-sample tanpa memandang persentase rate: `50 request`.
- Sisa request yang belum di-sample: `200 - 50 = 150 request/detik`.
- Dari sisa 150 request tersebut, diaplikasikan `FixedRate` sebesar 5% (0.05): `150 * 0.05 = 7.5 request/detik`.
- Total trace yang di-sample: `50 + 7.5 = 57.5 request/detik` (dibulatkan menjadi 57 atau 58 request/detik).

#### Solusi 4:
- Komitmen: $50/jam. Rasio penghematan: setiap $1 pengeluaran On-Demand dibayar $0.60.
- Nilai On-Demand yang dicakup: `$50 / 0.60 = $83.33` nilai ekuivalen On-Demand per jam.
- Total pengeluaran aktual sebelumnya: $100/jam.
- Sisa penggunaan On-Demand yang tidak ter-cover diskon dan dibayar dengan tarif penuh: `$100 - $83.33 = $16.67/jam`.
- Pengeluaran total baru: `$50 (komitmen) + $16.67 (On-Demand) = $66.67/jam` (menghemat $33.33/jam atau 33.3% dari total biaya komputasi).

#### Solusi 5:
- Mengaktifkan S3 Data Events tanpa filter memicu penulisan event untuk setiap `GetObject`. Pada jutaan hit harian, volume log yang masuk ke CloudTrail dan S3 akan memicu lonjakan biaya ekstrem ($0.10 per 100.000 data event) serta pembengkakan storage CloudWatch Logs / S3.
- Solusi efisien: Gunakan S3 Server Access Logging standar yang dialihkan langsung ke S3 untuk analisis asinkron via Athena, atau pasang CloudFront di depan bucket dan analisis CloudFront Standard/Real-Time Access Logs dengan retention policy agresif.

---

## 3. Scenario-Based Questions (Studi Kasus Nyata)

### Skenario 1: The Cascading Timeout Outage
Sebuah platform perbankan digital mengalami cascading failure saat jam puncak transfer gaji. Pengguna melaporkan bahwa aplikasi mobile mereka stuck pada loading spinner dan menampilkan pesan generic "Network Error 504".
- **Kondisi Observabilitas Eksisting**:
  - CloudWatch Alarm CPU dan Memory pada armada ECS cluster target grup pembayaran berada pada angka 30%.
  - Alarm batas koneksi RDS Aurora PostgreSQL berada pada status OK.
  - Logging aplikasi di-output ke file log lokal di dalam container container filesystem tanpa persistensi.
- **Tugas Arsitek**:
  1. Identifikasi kecacatan desain observabilitas di atas.
  2. Rancang strategi integrasi AWS X-Ray dan CloudWatch Logs Insights untuk menemukan titik bottleneck cascading dalam waktu kurang dari 5 menit.
  3. Konfigurasi Metric Math alarm yang seharusnya memperingatkan tim sebelum insiden ini berdampak luas ke seluruh customer.

### Skenario 2: The $45,000 Surprise Cloud Bill
Sebuah tim pengembang meluncurkan mikroservis analitik data baru berbasis event-driven architecture yang menggunakan AWS Lambda, Amazon DynamoDB, dan Amazon S3. Di akhir bulan, tagihan cloud departemen membengkak dari $2,000 menjadi $47,000.
- **Investigasi Cost Explorer menunjukkan**:
  - 85% biaya dikontribusikan oleh AWS Lambda Invocations dan CloudWatch Ingestion.
  - Terdapat recursive loop di mana Lambda dipicu oleh object creation S3, kemudian menulis output log ekstensif dan menulis file derivatif kecil kembali ke bucket yang sama.
- **Tugas FinOps Engineer**:
  1. Rancang arsitektur AWS Budgets terotomatisasi yang tidak hanya mengirim email peringatan, melainkan mengeksekusi remediator otomatis (*kill switch*) untuk mencabut izin eksekusi Lambda jika forecasted cost melampaui batas $5,000.
  2. Implementasikan pipeline gatekeeper menggunakan Infracost dan Terraform untuk mendeteksi ketiadaan arsitektur sirkuit pemutus (*circuit breaker*) dan tagging FinOps.

### Skenario 3: Cross-Account Multi-Region Security Forensics
Perusahaan holding multi-nasional memiliki 150 akun AWS di bawah AWS Organizations. Tim Incident Response mendeteksi adanya access key IAM developer senior yang bocor di public repository GitHub.
- **Tugas SRE / Cloud Security Architect**:
  1. Bagaimana Anda merancang arsitektur agregasi log CloudTrail terpusat (*Log Archive Account*) yang menjamin akun-akun anak (*member accounts*) tidak dapat menonaktifkan trail atau menghapus jejak log?
  2. Tuliskan query Athena atau CloudWatch Logs Insights untuk melacak setiap API invocation yang dilakukan oleh Access Key ID yang terkompromi (`AKIAIOSFODNN7EXAMPLE`) di seluruh Region dalam rentang waktu 48 jam terakhir.

---

### Solusi Studi Kasus

#### Solusi Skenario 1:
1. **Kecacatan Desain**:
   - Logging lokal ke container filesystem bersifat ephemeral; data log hilang seketika container di-restart oleh orchestrator saat crash.
   - Metrik resource mentah (CPU/Memory/DB Connections) tidak mencerminkan application-level latency atau thread starvation (misal: koneksi pool HTTP client habis sementara CPU tetap idle menunggu I/O timeout).
2. **Strategi Integrasi**:
   - Pasang AWS Distro for OpenTelemetry (ADOT) ke task ECS untuk menginjeksi correlation ID ke semua distributed spans.
   - Konfigurasi interceptor pada HTTP client antar service untuk propagasi header tracing `X-Amzn-Trace-Id`.
   - Buka X-Ray Service Map; filter berdasarkan HTTP status `504` dan `Fault = true` untuk mengidentifikasi node service yang mengalami delay latensi p99 ekstrem.
3. **Metric Math Alert**:
   - Hitung rasio Latensi p99 atau Error Rate:
     `Expression: (m1 / m2) * 100` (di mana `m1` = Target 5xx/504 errors, `m2` = Total request).
   - Set threshold alarm pada nilai 1.5% selama 2 periode evaluasi (2 menit).

#### Solusi Skenario 2:
1. **AWS Budgets Auto-Remediation Architecture**:
   - Buat AWS Budget tipe COST dengan target $5,000.
   - Buat Budget Action: Tipe `IAM Policy` atau `SSM Automation Document`. Targetkan execution role Lambda aplikasi tersebut.
   - Konfigurasi action threshold pada 100% *Forecasted Cost*. Saat mesin analitik AWS mendeteksi proyeksi spending akhir bulan akan menembus $5,000, Budget Action otomatis meng-attach IAM policy restrictive (`Deny` action `lambda:InvokeFunction`) atau menyetel concurrency limit fungsi Lambda menjadi 0 (*throttling* total), menghentikan loop rekursif secara seketika.
2. **Shift-Left Prevention**:
   - Konfigurasi CI/CD check menggunakan Infracost CLI. Jika PR menambahkan resource Lambda tanpa menyertakan atribut `reserved_concurrent_executions` atau tidak menyertakan tag wajib FinOps, pipeline dihentikan (*exit code 1*).

#### Solusi Skenario 3:
1. **Arsitektur Centralized Trail Immutable**:
   - Terapkan **Organization Trail** dari *Management Account* atau *Delegated Administrator Account*.
   - Konfigurasi trail untuk mengirim log ke S3 bucket khusus yang berada di akun terisolasi (*Security Log Archive Account*).
   - Pasang Service Control Policy (SCP) di level root AWS Organizations untuk melarang aksi `cloudtrail:StopLogging`, `cloudtrail:DeleteTrail`, `cloudtrail:UpdateTrail`, serta pembatasan akses bucket S3 log bagi semua principal kecuali CloudTrail service principal.
   - Aktifkan S3 Object Lock dalam mode `Compliance Mode` dengan periode retensi (misal: 365 hari) sehingga log tidak dapat dihapus bahkan oleh akun root AWS.
2. **Query Forensik CloudWatch Logs Insights**:
   ```sql
   fields @timestamp, eventTime, awsRegion, eventSource, eventName, sourceIPAddress, userAgent
   | filter userIdentity.accessKeyId = "AKIAIOSFODNN7EXAMPLE"
   | sort @timestamp desc
   | limit 1000
   ```

---

## 4. Practical Chapter Challenge: Resilient Multi-Tier Observability & Cost Guardrails Engine

### Sasaran Tantangan:
Anda ditugaskan sebagai Principal Cloud Platform Architect untuk membangun arsitektur observabilitas dan FinOps end-to-end yang tangguh, reproducible, dan siap produksi menggunakan Terraform.

### Spesifikasi Kebutuhan Arsitektur:
1. **Infrastruktur Log & Audit**:
   - S3 Bucket audit terpusat dengan SSE-KMS, enkripsi enforced TLS 1.2+, memblokir semua akses publik, dan mengaktifkan Log File Validation.
   - CloudTrail Multi-Region yang mencatat seluruh management events.
   - CloudWatch Log Group terpusat untuk aplikasi dengan retention policy 30 hari.
2. **SLO Alerting Engine**:
   - Buat CloudWatch Metric Alarm yang memantau performa backend menggunakan formula Metric Math gabungan:
     $$\text{Breach} = \left(\frac{\text{HTTPCode\_Target\_5XX\_Count}}{\text{RequestCount}}\right) > 0.02 \quad \text{DAN} \quad \text{TargetResponseTime (p95)} > 1.5\,\text{detik}$$
   - Konfigurasi SNS topic yang dihubungkan ke alarm tersebut.
3. **FinOps Guardrails**:
   - AWS Budget berbasis tag `CostCenter = FinOps-Core` dengan limitasi $1,500/bulan.
   - Notifikasi multi-ambang-batas:
     - 70% Actual Spending (Email Peringatan Tim Operasional).
     - 100% Forecasted Spending (Email Kritis Tim Engineering Lead & FinOps).

### Tolok Ukur Keberhasilan:
- Kode Terraform lolos validasi `terraform validate`.
- Tidak ada resource audit logging yang terekspos ke publik atau mengizinkan modifikasi plaintext unencrypted.
- Alarm Metric Math mengevaluasi minimal dua metrik secara simultan dalam satu alarm definition.