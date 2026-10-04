# Evaluasi Pemahaman & Tantangan Bab 03: Compute Architecture & Elastic Scaling

## Bagian 1: Basic Questions (Pilihan Ganda & Konseptual Singkat)

### Soal 1
Komponen arsitektur dari AWS Nitro System yang bertanggung jawab untuk memvalidasi integritas firmware host saat hardware pertama kali dinyalakan (Hardware Root of Trust) adalah:
- [A] Nitro Card for VPC
- [B] Nitro Hypervisor
- [C] Nitro Security Chip
- [D] ENA Controller Engine

### Soal 2
Manakah pernyataan yang **BENAR** mengenai alokasi vCPU pada prosesor AWS Graviton (Graviton2, Graviton3, Graviton4)?
- [A] 1 vCPU setara dengan 1 SMT (Simultaneous Multi-Threading) logical thread pada 1 physical core.
- [B] 1 vCPU setara dengan 1 physical core ARM khusus tanpa resource sharing cache L1/L2 dengan thread lain.
- [C] 1 vCPU membagi alokasi time-slice dengan 4 vCPU lainnya di level Nitro Hypervisor.
- [D] Graviton menggunakan Hyper-Threading dinamis tergantung pada beban CPU yang diberikan.

### Soal 3
Konfigurasi metadata service manakah yang wajib diterapkan pada Launch Template untuk memitigasi serangan Server-Side Request Forgery (SSRF) yang mencoba mengekstraksi kredensial IAM Instance Profile?
- [A] `HttpEndpoint = disabled`
- [B] `HttpTokens = required` dan `HttpPutResponseHopLimit = 1`
- [C] `HttpTokens = optional` dan `HttpPutResponseHopLimit = 2`
- [D] `InstanceMetadataTags = disabled`

### Soal 4
Berapa lama durasi waktu maksimum yang diberikan oleh AWS melalui notifikasi Spot Interruption Warning sebelum instans Spot dihentikan secara paksa?
- [A] 30 detik
- [B] 2 menit
- [C] 5 menit
- [D] 15 menit

### Soal 5
Port firewall inbound manakah yang wajib dibuka pada Security Group sebuah EC2 Instance agar engineer dapat mengakses terminal instance menggunakan AWS Systems Manager (SSM) Session Manager?
- [A] Port TCP 22 (SSH)
- [B] Port TCP 443 (HTTPS)
- [C] Port TCP 8080 (SSM Agent Webhook)
- [D] Tidak ada port inbound yang perlu dibuka (Zero Inbound Ports)

---

## Bagian 2: Intermediate Questions (Analisis & Desain Mekanisme)

### Soal 6
Jelaskan perbedaan mendasar antara strategi alokasi Spot `lowest-price` dan `price-capacity-optimized` pada Auto Scaling Group. Mengapa industri mengadopsi `price-capacity-optimized` sebagai standar de facto untuk beban kerja produksi?

### Soal 7
Sebuah armada ASG memiliki Target Tracking Scaling Policy terpasang pada metrik `ASGAverageCPUUtilization` dengan target value 50%. Saat terjadi lonjakan trafik mendadak, utilisasi CPU melonjak dari 40% menjadi 90%. 
Jelaskan perhitungan kalkulasi kapasitas yang dieksekusi ASG untuk menentukan jumlah penambahan instans dan mengapa algoritma ASG tidak langsung melakukan scaling ke `MaxSize` secara membabi buta.

### Soal 8
Jelaskan urutan transisi status (*state machine*) ketika sebuah EC2 Instance di dalam ASG memasuki proses scale-in, dan bagaimana sebuah `EC2_INSTANCE_TERMINATING` Lifecycle Hook dapat mencegah pemutusan koneksi klien database yang sedang aktif berjalan.

### Soal 9
Apa implikasi arsitektur dari parameter `HttpPutResponseHopLimit = 1` pada IMDSv2 ketika aplikasi Anda berjalan di dalam container Docker yang menggunakan mode jaringan bridge (`bridge network`) pada instans EC2 tersebut? Solusi apa yang harus diterapkan jika container tersebut butuh membaca IMDS?

### Soal 10
Bandingkan karakteristik penggunaan **EBS GP3** vs **EBS IO2 Block Express**. Kapan seorang SRE harus merekomendasikan transisi dari GP3 ke IO2 Block Express, dan apa trade-off biaya serta batasan arsitekturalnya?

---

## Bagian 3: Scenario-Based Questions (Studi Kasus Industri Nyata)

### Skenario 1: The Cascading 502 Outage
**Konteks**: 
Sebuah startup fintech mengoperasikan backend microservices Java Spring Boot di atas EC2 ASG di belakang Application Load Balancer (ALB). Selama proses deployment versi baru menggunakan rolling update ASG, monitoring SRE mendeteksi lonjakan error `HTTP 502 Bad Gateway` sebesar 12% selama rentang waktu 10 menit.
Setelah diinvestigasi:
- Java Spring Boot membutuhkan waktu 45 detik untuk melakukan startup konteks dan membuka socket.
- Graceful shutdown Spring Boot membutuhkan waktu 20 detik untuk menguras connection pool ke PostgreSQL.
- Konfigurasi ASG saat ini tidak memiliki Lifecycle Hook.
- Konfigurasi Target Group ALB memiliki:
  - `HealthCheckIntervalSeconds`: 30
  - `HealthyThresholdCount`: 2
  - `DeregistrationDelayTimeout`: 300 detik

**Tugas Analisis**:
1. Bedah secara kronologis mengapa lonjakan HTTP 502 terjadi baik pada saat penambahan instans baru (*scale-out*) maupun pengurangan instans lama (*scale-in*).
2. Tuliskan blueprint konfigurasi perbaikan yang mencakup Launch Template, ALB Target Group health check parameters, dan ASG Lifecycle Hooks untuk memastikan *zero-downtime* rolling update.

---

### Skenario 2: Spot Armada & The "Insufficient Capacity" Disaster
**Konteks**:
Platform ad-tech memproses streaming data bid menggunakan 150 node EC2 Spot. Seluruh node dikonfigurasi menggunakan 1 tipe instans: `c6i.4xlarge` di Region `us-east-1` dengan strategi `lowest-price`.
Pada saat event *Black Friday*, AWS Region `us-east-1` mengalami lonjakan permintaan global untuk tipe `c6i.4xlarge`. 
Secara mendadak, AWS merebut kembali 80% instans Spot milik platform ini dalam waktu 10 menit. Permintaan peluncuran instans baru ditolak dengan pesan: `InsufficientInstanceCapacity`. 
Armada runtuh, pemrosesan bid berhenti total, dan perusahaan kehilangan pendapatan ribuan dolar per menit.

**Tugas Rekayasa Sistem**:
Rancang ulang arsitektur compute fleet ini secara menyeluruh agar tahan terhadap kegagalan pool kapasitas di masa depan:
1. Rekonfigurasi Mixed Instances Policy mencakup diversifikasi arsitektur silikon (Graviton + Intel + AMD) dan ukuran family.
2. Terapkan strategi alokasi yang tepat dan jelaskan alasan matematisnya.
3. Rancang failover mechanism menggunakan Base On-Demand capacity untuk mempertahankan Service Level Objective (SLO).

---

### Skenario 3: High-Security Compliance & Bastionless Fleet Management
**Konteks**:
Perusahaan perbankan sedang diaudit untuk sertifikasi PCI-DSS 4.0 dan SOC 2 Tipe II. Auditor menemukan bahwa para engineer masih mengakses server di private subnet menggunakan SSH Keypair bersama (*shared .pem file*) melalui sebuah EC2 Bastion Host yang diletakkan di public subnet dengan port 22 terbuka ke IP kantor VPN.
Temuan auditor:
1. Tidak ada rekaman audit command-level individual (siapa mengetik apa di shell Linux).
2. Bastion host menjadi single point of failure dan target scanning brute-force port 22.
3. Kunci privat SSH berpotensi bocor dari laptop engineer.

**Tugas Solusi Arsitektur**:
Rancang arsitektur modern tanpa bastion (*bastionless*) menggunakan AWS Systems Manager Fleet & Session Manager:
1. Gambarkan diagram arsitektur komunikasi jaringan (termasuk VPC Endpoints untuk lingkungan tanpa akses internet langsung).
2. Rancang IAM Policy dengan prinsip *Least Privilege* yang membatasi akses Session Manager hanya untuk instans bertag `Environment=Staging` dan mewajibkan sesi dienkripsi dengan customer-managed AWS KMS Key.
3. Jelaskan bagaimana log shell session dikirimkan secara *tamper-proof* ke Amazon CloudWatch Logs dan S3 Bucket untuk memenuhi kepatuhan auditor.

---

## Bagian 4: Practical Chapter Challenge (Tantangan Implementasi Komprehensif)

### Judul Tantangan:
**Membangun Resilient & Self-Healing Compute Fabric Berbasis Graviton, Spot Allocation, dan Automated Lifecycle Draining**

### Objektif:
Anda ditugaskan membangun infrastruktur komputasi untuk backend API berkinerja tinggi yang memiliki toleransi tinggi terhadap interupsi, efisien secara biaya, dan dapat menguras koneksi secara anggun (*graceful drain*).

### Spesifikasi Teknis Wajib:
1. **Launch Template**:
   - Tipe arsitektur target: **AWS Graviton (arm64)**.
   - Penegakan ketat **IMDSv2** (`HttpTokens=required`, `HopLimit=1`).
   - Root disk: GP3 terenkripsi KMS, 30 GiB, 3000 IOPS, 125 MB/s.
   - IAM Role: Terpasang SSM Core policy.
2. **Auto Scaling Group**:
   - Minimum: 2, Maximum: 10, Desired: 4.
   - Mixed Instances Policy:
     - Base On-Demand: 2 instans.
     - Persentase On-Demand di atas base: 25% (sisanya 75% Spot).
     - Spot Allocation Strategy: `price-capacity-optimized`.
     - Varian Pool: `c7g.medium`, `c6g.medium`, `m7g.medium`, `t4g.medium`.
   - Capacity Rebalance: Aktif.
3. **Automated Lifecycle Drainer**:
   - Terapkan sebuah ASG Lifecycle Hook untuk fase terminasi (`autoscaling:EC2_INSTANCE_TERMINATING`).
   - Buat skrip simulasi penanganan sinyal terminasi (`asg_lifecycle_simulation.py`) yang berjalan sebagai background daemon / mock worker di dalam instans.
   - Skrip harus:
     1. Melakukan polling ke metadata spot interruption atau menangani sinyal OS (`SIGTERM`).
     2. Memulai proses draining (simulasikan penghentian accept request baru, tunggu pemrosesan tugas aktif selama 15 detik).
     3. Mengirimkan notifikasi penyelesaian via AWS CLI/Boto3 API: `CompleteLifecycleAction` dengan status `CONTINUE`.

---

## Kunci Jawaban & Panduan Evaluasi (Bagian 1)
1. **[C] Nitro Security Chip** - Hardware independen yang menahan firmware dan memvalidasi integrity bootloader.
2. **[B] 1 vCPU setara dengan 1 physical core ARM khusus** - Desain Neoverse Graviton meniadakan SMT/Hyper-threading.
3. **[B] `HttpTokens = required` dan `HttpPutResponseHopLimit = 1`** - Mencegah paket traversal melewati reverse proxy container/web server lokal.
4. **[B] 2 menit** - Notifikasi interupsi EC2 Spot dikirimkan 120 detik sebelum penghentian fisik.
5. **[D] Tidak ada port inbound yang perlu dibuka** - SSM Agent menginisiasi outbound HTTPS polling ke SSM Endpoints via TCP 443.