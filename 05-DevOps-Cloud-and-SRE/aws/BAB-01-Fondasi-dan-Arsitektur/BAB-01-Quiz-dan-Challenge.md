# BAB 01: Quiz, Challenge, & Knowledge Check

Dokumen evaluasi ini dirancang untuk menguji pemahaman konseptual, kemampuan analisis arsitektur, dan keterampilan pemecahan masalah (*troubleshooting*) tingkat lanjut terkait **AWS Global Infrastructure, Shared Responsibility Model, AWS Organizations, Service Control Policies (SCP), dan AWS IAM Core Mechanics**.

---

## A. Basic Questions (5 Soal)

### Soal 1
Perusahaan Anda memiliki dua akun AWS dalam satu organisasi: Akun A dan Akun B. Tim rekayasa mengamati bahwa subnet yang dibuat di `ap-southeast-1a` pada Akun A tidak dapat berkomunikasi dengan latensi sub-milidetik ke instans di `ap-southeast-1a` pada Akun B, meskipun dihubungkan melalui VPC Peering. Mengapa hal ini dapat terjadi?
- [A] AWS Route Table tidak mendukung perutean antar-AZ yang berbeda akun.
- [B] Penamaan huruf Availability Zone (misal: `ap-southeast-1a`) dipetakan secara independen dan acak (*AZ mapping randomization*) ke data center fisik yang berbeda untuk setiap akun AWS.
- [C] VPC Peering secara default membatasi bandwidth sebesar 1 Gbps antar-akun yang berbeda.
- [D] Akun AWS yang berbeda wajib menggunakan AWS Direct Connect untuk mencapai latensi sub-milidetik.

### Soal 2
Dalam konteks **AWS Shared Responsibility Model**, manakah batasan operasional berikut yang sepenuhnya menjadi tanggung jawab pelanggan (*Security IN the Cloud*) saat menggunakan layanan terkelola **Amazon RDS for PostgreSQL**?
- [A] Instalasi patch keamanan pada sistem operasi host Linux yang mendasari instans basis data.
- [B] Penggantian modul hardware disk NVMe yang mengalami degradasi fisik pada storage cluster AWS.
- [C] Konfigurasi otentikasi basis data, pengelolaan database users, Network Security Groups, serta otorisasi otentikasi IAM database.
- [D] Pengelolaan hypervisor, firmware server fisik, dan isolasi multi-tenant komputasi.

### Soal 3
Bagaimana urutan prioritas evaluasi logika deterministik pada mesin evaluasi otorisasi AWS IAM (*Policy Evaluation Engine*) saat memproses suatu request API masuk?
- [A] Default Allow $\rightarrow$ Permission Boundary $\rightarrow$ Explicit Deny $\rightarrow$ Final Allow.
- [B] Explicit Deny $\rightarrow$ Organizations SCP $\rightarrow$ Resource-based Policy $\rightarrow$ Identity-based Policy $\rightarrow$ Permissions Boundary $\rightarrow$ Session Policy.
- [C] Explicit Allow $\rightarrow$ Explicit Deny $\rightarrow$ Default Deny.
- [D] Identity-based Policy $\rightarrow$ Role Trust Policy $\rightarrow$ Default Allow.

### Soal 4
Sebuah IAM Role pada Akun 111122223333 memiliki Permissions Boundary bernama `DeveloperBoundary` yang hanya mengizinkan aksi pada layanan Amazon S3 dan Amazon DynamoDB (`s3:*`, `dynamodb:*`). Jika ke dalam IAM Role tersebut di-attach sebuah Identity-based Policy dengan hak akses `AdministratorAccess` (`"Action": "*", "Resource": "*"`), tindakan apa yang secara efektif dapat dieksekusi oleh entitas yang mengasumsikan role tersebut?
- [A] Akses penuh ke seluruh layanan AWS karena `AdministratorAccess` meng-override boundary.
- [B] Tidak dapat mengakses layanan apapun karena terjadi konflik kebijakan (*policy conflict error*).
- [C] Hanya aksi yang diizinkan oleh kedua kebijakan secara bersamaan (interseksi), yaitu operasi pada Amazon S3 dan DynamoDB saja.
- [D] Akses administratif penuh ke S3 dan DynamoDB serta akses read-only ke layanan EC2.

### Soal 5
Manakah pernyataan yang **BENAR** mengenai sifat operasional Service Control Policy (SCP) pada AWS Organizations?
- [A] SCP memberikan izin (*grants permission*) langsung kepada user atau role di dalam akun anggota.
- [B] SCP bertindak sebagai guardrail penyaring (*filter boundary*) yang membatasi hak akses maksimum bagi seluruh entitas IAM di akun target, termasuk AWS Account Root User akun anak.
- [C] SCP yang di-attach pada Root OU tidak akan diwariskan (*inherited*) ke Organizational Unit (OU) di level bawahnya.
- [D] Jika sebuah akun keluar (*leave*) dari AWS Organization, semua SCP yang terpasang tetap melekat secara lokal di akun tersebut.

---

## B. Intermediate Questions (5 Soal)

### Soal 6
Jelaskan perbedaan mendasar antara **Identity-based Policy** dan **Resource-based Policy** saat mengevaluasi otorisasi akses lintas akun (*cross-account access*). Mengapa pada akses sesama akun (*same-account*) hanya membutuhkan izin pada salah satu policy, sedangkan pada akses lintas akun mutlak membutuhkan izin eksplisit pada kedua sisi?

### Soal 7
Sebuah bucket Amazon S3 di Akun A (`111111111111`) memiliki Bucket Policy berikut:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAppRole",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::222222222222:role/AppProcessingRole"
      },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::corporate-data-lake/*"
    },
    {
      "Sid": "DenyNonVPCAccess",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": "arn:aws:s3:::corporate-data-lake/*",
      "Condition": {
        "StringNotEquals": {
          "aws:sourceVpce": "vpce-0123456789abcdef0"
        }
      }
    }
  ]
}
```
Jika `AppProcessingRole` di Akun B (`222222222222`) telah memiliki policy `s3:GetObject` pada bucket tersebut dan mengirimkan request melalui internet gateway tanpa melewati VPC Endpoint `vpce-0123456789abcdef0`, apakah request tersebut diizinkan atau ditolak? Jelaskan secara presisi mekanisme evaluasi kondisionalnya!

### Soal 8
Bagaimana cara kerja condition key `aws:PrincipalOrgID` dalam arsitektur multi-account enterprise? Bandingkan tingkat efisiensi operasional dan skalabilitas keamanan penggunaan `aws:PrincipalOrgID` terhadap pendaftaran manual ratusan Akun ID pada Resource-based Policy (seperti S3 Bucket Policy, KMS Key Policy, atau ECR Repository Policy).

### Soal 9
Dalam strategi pertahanan *defense-in-depth*, jelaskan bagaimana integrasi antara **AWS STS AssumeRole**, **IAM Session Policies**, dan **Role Chaining** mempengaruhi *effective permission* dari sebuah sesi kredensial sementara (*ephemeral credential*). Mengapa batas waktu durasi sesi (*session duration limit*) berkurang menjadi 1 jam ketika terjadi role chaining?

### Soal 10
Bandingkan arsitektur ketahanan bencana (*Disaster Recovery*) berbasis **Multi-Region Active-Active** dengan **Multi-AZ High Availability**. Tinjau dari aspek:
1. *Fault domain isolation* (apakah kegagalan control plane regional dapat menjalar?).
2. Mekanisme replikasi data (sinkron vs. asinkron) serta pengaruhnya terhadap RPO (*Recovery Point Objective*) dan RTO (*Recovery Time Objective*).
3. Hambatan konsistensi data (*CAP Theorem trade-offs*).

---

## C. Skenario Kasus Produksi (3 Masalah Nyata)

### Skenario 1: Insiden Kebocoran Token Developer & Lateral Movement di Lingkungan Multi-Account
**Latar Belakang:**
Sebuah perusahaan e-commerce skala unicorn mengalami insiden keamanan kritis. Kredensial statis (*Long-lived AWS Access Key & Secret Key*) milik seorang developer junior bocor di repository publik GitHub. Kredensial tersebut terikat pada user IAM di akun `Sandbox-Dev` (`123456789012`).

**Anomali & Eskalasi:**
1. Penyerang (*adversary*) menggunakan token tersebut untuk melakukan enumerasi IAM, kemudian menemukan bahwa user tersebut memiliki izin `sts:AssumeRole` ke role bernama `OrganizationDeploymentRole` di akun `Production-Core` (`987654321098`).
2. Begitu berpindah (*pivot*) ke akun produksi, penyerang mencoba memodifikasi Security Group, menghapus bucket cadangan S3, dan mematikan Amazon GuardDuty serta AWS CloudTrail untuk menghapus jejak forensik.
3. Beruntung, sebagian aksi destruktif penyerang gagal dieksekusi dengan error: `AccessDenied: User is not authorized to perform action because of an explicit deny in a Service Control Policy`.

**Tugas Rekayasa Anda:**
1. **Analisis Akar Masalah (Root Cause)**: Identifikasi 3 celah arsitektur keamanan mendasar pada rantai kepercayaan (*trust relationship*) dan manajemen kredensial di atas.
2. **Desain Remediasi Arsitektur**:
   - Susun sebuah **Service Control Policy (SCP)** ketat di level AWS Organizations yang mengunci akun produksi dari penonaktifan CloudTrail, GuardDuty, dan pencegahan modifikasi rute jaringan kritis.
   - Rancang mekanisme penegakan *Least Privilege* menggunakan **IAM Permissions Boundary** dan **ABAC (Attribute-Based Access Control)** agar akun `Sandbox-Dev` tidak pernah dapat mengasumsikan role administratif di lingkungan `Production`.

---

### Skenario 2: Anomali Data Transfer Cross-AZ & Latensi Tinggi pada Microservices Cluster
**Latar Belakang:**
Sebuah platform fintech perbankan menjalankan kluster microservices terdistribusi di Amazon EKS (Elastic Kubernetes Service) pada Region `ap-southeast-3` (Jakarta). Arsitektur menggunakan 3 Availability Zone.

**Gejala Masalah:**
1. FinOps mendeteksi lonjakan biaya tidak wajar pada tagihan bulanan kategori *DataTransfer-Regional-Bytes* (biaya transfer data antar-AZ mencapai puluhan ribu dolar).
2. SRE mengamati latensi P99 internal pada komunikasi antar-service (Service A memanggil Service B via internal gRPC) melonjak fluktuatif antara 4 ms hingga 12 ms, padahal benchmark dalam satu rack fisik berada di bawah 0.8 ms.
3. Setelah diaudit, Service A berada di Akun Workload-1 (`ap-southeast-3a`), sedangkan Service B berada di Akun Workload-2 (`ap-southeast-3a`). Namun saat dicek menggunakan AWS CLI:
   - Akun Workload-1: AZ Code `ap-southeast-3a` memiliki AZ ID `apse3-az1`.
   - Akun Workload-2: AZ Code `ap-southeast-3a` memiliki AZ ID `apse3-az3`.

**Tugas Rekayasa Anda:**
1. **Analisis Teknis**: Jelaskan secara mendalam mengapa perbedaan pemetaan antara *AZ Name* dan *AZ ID* tersebut memicu degradasi performa dan pembengkakan biaya transfer data cross-AZ!
2. **Solusi Arsitektur**:
   - Bagaimana strategi standardisasi provisioning subnet berbasis Terraform dengan memanfaatkan AWS RAM (*Resource Access Manager*) atau data source AWS provider untuk menyelaraskan AZ ID secara seragam di seluruh akun organisasi?
   - Rancang topologi penempatan workload menggunakan Kubernetes Topology Spread Constraints / Node Affinity berbasis AZ ID fisik (`topology.kubernetes.io/zone`).

---

### Skenario 3: Krisis Kepatuhan Regulasi Finansial & Data Sovereignty Lockdown
**Latar Belakang:**
Otoritas Jasa Keuangan (OJK) dan regulator privasi data nasional mewajibkan institusi perbankan untuk mematuhi regulasi kedaulatan data:
1. Seluruh data nasabah, beban kerja komputasi, dan enkripsi data (*data-at-rest* maupun *data-in-transit*) tidak boleh meninggalkan yurisdiksi Republik Indonesia (Region AWS Jakarta `ap-southeast-3`).
2. Penggunaan Region di luar `ap-southeast-3` dilarang keras, kecuali untuk layanan global tertentu yang tidak menyimpan data transaksi (misal: AWS IAM, Amazon CloudFront, AWS Route 53, AWS WAF global).
3. Seluruh bucket S3 yang dibuat di seluruh unit organisasi wajib menggunakan enkripsi Customer Managed Keys (AWS KMS CMK) dengan penegakan protokol TLS minimal v1.2.

**Tugas Rekayasa Anda:**
1. Rancang arsitektur tata kelola organisasi (*Governance Guardrail*) menggunakan **Service Control Policies (SCP)** multi-tier yang:
   - Membatasi eksekusi seluruh API AWS hanya di Region `ap-southeast-3`, dengan pengecualian (*exception list*) eksplisit yang tepat untuk layanan global AWS (*control plane operations*).
   - Menolak secara eksplisit pembuatan bucket S3 tanpa enkripsi KMS yang diwajibkan.
2. Tuliskan kode JSON SCP deklaratif yang siap di-deploy pada level Root Organizational Unit (OU) untuk menegakkan batasan wilayah geografis (*Region Restriction Policy*) tersebut secara komprehensif.

---

## D. Practical Chapter Challenge: Enterprise Multi-Account Baseline Architecture

### Judul Challenge:
**Membangun Fondasi Enterprise Multi-Account Governance, Zero-Trust IAM Policy, dan Region-Restriction Guardrails**

### Objektif:
Anda ditugaskan bertindak sebagai *Lead Cloud Architect & SRE* untuk membangun cetak biru (*blueprint*) fondasi AWS Organizations dan tata kelola keamanan IAM untuk institusi enterprise.

### Spesifikasi Kebutuhan Teknis:

#### 1. Arsitektur Struktur Organisasi (AWS Organizations Structure)
Rancang struktur hierarki OU (*Organizational Units*) berikut:
- **Root OU**
  - **Core OU**:
    - `Security-Tooling-Account` (GuardDuty Delegated Admin, Security Hub, CloudTrail Aggregator).
    - `Log-Archive-Account` (Penyimpanan terpusat seluruh log akses dan S3 object audit yang terkunci Object Lock).
    - `Shared-Network-Account` (Transit Gateway, Network Firewall, VPC Endpoints terpusat).
  - **Workloads OU**:
    - `Staging-Account`
    - `Production-Account`
  - **Sandbox OU**:
    - `Dev-Exploration-Account`

#### 2. Penegakan Service Control Policies (SCP)
Buat dan dokumentasikan 3 Service Control Policy:
1. **SCP-Region-Lockdown**: Mengunci seluruh aksi API ke luar dari Region yang ditentukan, kecuali layanan global.
2. **SCP-Security-Services-Protection**: Mencegah entitas manapun (termasuk root di akun anak) mematikan CloudTrail, GuardDuty, AWS Config, dan menghapus bucket log audit.
3. **SCP-Root-User-Restriction**: Memblokir seluruh pemanggilan API yang dilakukan langsung oleh kredensial AWS Account Root User di seluruh akun anggota.

#### 3. Zero-Trust Cross-Account IAM Architecture
Rancang spesifikasi IAM Policy:
1. **Trust Policy pada Production Account**:
   - Role `SREEmergencyAccessRole` di akun produksi hanya dapat diasumsikan oleh identitas dari `Security-Tooling-Account`.
   - Wajib menyertakan proteksi MFA (`aws:MultiFactorAuthPresent: true`).
   - Wajib membatasi pemanggilan dari CIDR IP publik kantor korporat (`aws:SourceIp`).
2. **Permissions Boundary**:
   - Buat boundary policy untuk developer di akun Staging yang mencegah eskalasi hak istimewa (*privilege escalation*), melarang modifikasi IAM Policy, dan melarang pembuatan resource di luar tagging standardisasi biaya (`CostCenter`, `Environment`).

---

## E. Checklist Pemahaman

Gunakan daftar periksa berikut untuk memvalidasi kesiapan pemahaman Anda sebelum melangkah ke Bab 02:

### Fondasi Konseptual:
- [ ] Saya memahami perbedaan fisik dan logis antara AWS Region, Availability Zone (AZ), Local Zones, Wavelength, dan Edge Points of Presence (PoP).
- [ ] Saya memahami mengapa penamaan AZ (misal: `us-east-1a`) dapat berbeda secara fisik antar-akun AWS dan bagaimana cara memetakan kesesuaian menggunakan *AZ ID* (misal: `use1-az1`).
- [ ] Saya dapat mengklasifikasikan pembagian tanggung jawab keamanan antara AWS dan Pelanggan pada model IaaS, PaaS, dan Serverless/SaaS tanpa keraguan.
- [ ] Saya menguasai alur kerja evaluasi kebijakan IAM: *Deny Evaluation* $\rightarrow$ *SCP Check* $\rightarrow$ *Resource-based Policy* $\rightarrow$ *Identity-based Policy* $\rightarrow$ *Permissions Boundary* $\rightarrow$ *Session Policy*.

### Arsitektur & Tata Kelola:
- [ ] Saya memahami bahwa SCP tidak memberikan hak akses, melainkan membatasi batas otorisasi maksimum (*permission ceiling*).
- [ ] Saya tahu cara mengisolasi *blast radius* insiden keamanan menggunakan arsitektur AWS Multi-Account berbasis AWS Organizations.
- [ ] Saya memahami cara kerja STS AssumeRole, Session Policies, dan bagaimana kredensial sementara (*ephemeral tokens*) dievaluasi.
- [ ] Saya memahami kegunaan condition keys global seperti `aws:PrincipalOrgID`, `aws:PrincipalArn`, `aws:sourceVpce`, `aws:RequestedRegion`, dan `aws:MultiFactorAuthPresent`.

### Praktik & Troubleshooting:
- [ ] Saya mampu mendiagnosis insiden *privilege escalation* dan mencegahnya menggunakan *IAM Permissions Boundary*.
- [ ] Saya mampu menganalisis akar penyebab lonjakan latensi dan biaya cross-AZ data transfer akibat misaligning AZ ID.
- [ ] Saya mampu menuliskan sintaks kebijakan JSON yang valid untuk Service Control Policies, IAM Identity Policies, dan Resource-based Policies.

---

## Kunci Jawaban & Pembahasan Teknis

### A. Pembahasan Basic Questions

#### Soal 1: Jawaban [B]
**Pembahasan:**
AWS menerapkan mekanisme *AZ mapping randomization* untuk mendistribusikan konsumsi resource secara seimbang di seluruh pusat data fisik dalam satu Region. Nama kode `ap-southeast-1a` pada Akun A belum tentu merujuk pada gedung fisik data center yang sama dengan `ap-southeast-1a` pada Akun B. Untuk memastikan dua instans berada pada cluster fisik yang sama, engineer harus mencocokkan **AZ ID** (misal: keduanya berada di `apse1-az1`). Ketidakcocokan AZ ID menyebabkan trafik melintasi kabel antar-gedung/antar-zona yang menambah latensi jaringan dan memicu biaya *Inter-AZ Data Transfer*.

#### Soal 2: Jawaban [C]
**Pembahasan:**
Pada model PaaS seperti Amazon RDS, AWS bertanggung jawab atas provisioning hardware, sistem operasi host, instalasi engine basis data, dan patch keamanan OS (*Security OF the Cloud*). Namun, pelanggan bertanggung jawab penuh atas manajemen akun database internal, pengelolaan password, aturan firewall/Security Groups yang membatasi akses port, otorisasi koneksi aplikasi, serta enkripsi data aplikasi (*Security IN the Cloud*).

#### Soal 3: Jawaban [B]
**Pembahasan:**
Mesin evaluasi AWS IAM bekerja secara deterministik dengan urutan prioritas:
1. Dimulai dengan status **Default Deny**.
2. Mengevaluasi seluruh kebijakan yang relevan untuk mencari **Explicit Deny**. Jika ada satu saja *Explicit Deny*, evaluasi langsung berhenti dengan keputusan **DENY**.
3. Jika dieksekusi dalam konteks organisasi, **SCP** dievaluasi. Jika aksi tidak diizinkan di SCP, hasil akhir **DENY**.
4. Mengevaluasi **Resource-based Policy** dan/atau **Identity-based Policy**.
5. Jika ada **Permissions Boundary**, hak akses dipotong (interseksi) oleh boundary tersebut.
6. Jika request menggunakan STS AssumeRole dengan **Session Policy**, hak akses kembali dipotong oleh session policy.
7. Jika ditemukan setidaknya satu **Explicit Allow** dan tidak ada deny di sepanjang rantai, hasil akhir adalah **ALLOW**.

#### Soal 4: Jawaban [C]
**Pembahasan:**
*Permissions Boundary* menetapkan batas otorisasi maksimum (*maximum permissions boundary*) bagi entitas IAM. Prinsip kerjanya adalah operasi irisan (*intersection* / AND logic):
$$\text{Effective Permission} = \text{Identity-based Policy} \cap \text{Permissions Boundary}$$
Meskipun identity-based policy memiliki `AdministratorAccess` (`*`), entitas hanya dapat melakukan aksi yang diizinkan oleh boundary (`s3:*` dan `dynamodb:*`).

#### Soal 5: Jawaban [B]
**Pembahasan:**
SCP tidak pernah memberikan hak akses (*never grants permission*). SCP menetapkan *guardrails* yang membatasi izin maksimum bagi seluruh akun di bawah hierarki OU tempat SCP tersebut di-attach. Yang terpenting, SCP berlaku untuk seluruh entitas di dalam akun anggota, termasuk pengguna Root (`root user`) dari akun anggota tersebut (namun tidak membatasi root di Management Account).

---

### B. Pembahasan Intermediate Questions

#### Soal 6: Evaluasi Cross-Account vs Same-Account
- **Same-Account Access**: Mesin evaluasi IAM mengevaluasi Identity-based policy dan Resource-based policy sebagai operasi gabungan (*union* / OR logic). Jika identitas memiliki allow pada identity policy **ATAU** resource memiliki allow pada resource policy (tanpa adanya explicit deny), akses langsung diberikan.
- **Cross-Account Access**: Batas kepemilikan akun (*Account boundary*) memberlakukan prinsip *dual-authorization* (operasi irisan / AND logic). Akses lintas akun **wajib** diizinkan oleh kedua belah pihak:
  1. Akun pemilik identitas (Akun Pengakses) harus memberikan izin via Identity-based policy (atau delegasi assume role).
  2. Akun pemilik resource (Akun Sasaran) harus memberikan izin eksplisit via Resource-based policy (misal: S3 Bucket Policy atau KMS Key Policy) yang menyebutkan Principal dari akun pengakses.
  Jika salah satu pihak tidak memberikan izin, evaluasi menghasilkan *Implicit Deny*.

#### Soal 7: Analisis Evaluasi Kondisional S3 Bucket Policy
Request dari `AppProcessingRole` akan **DITOLAK (DENIED)**.
**Penjelasan Logika:**
Statement 1 memberikan `Allow` untuk `AppProcessingRole`. Namun, Statement 2 adalah **Explicit Deny** pada `s3:*` dengan kondisi `StringNotEquals` untuk `aws:sourceVpce`.
Karena request dikirim melalui internet publik tanpa melewati VPC Endpoint `vpce-0123456789abcdef0`, kondisi `StringNotEquals` terpenuhi bernilai `true`. Hal ini memicu klausul `Explicit Deny` pada Statement 2. Berdasarkan prinsip evaluasi IAM, *Explicit Deny selalu menganulir Explicit Allow*, sehingga request dibatalkan dengan error `HTTP 403 Forbidden`.

#### Soal 8: Efisiensi `aws:PrincipalOrgID`
Condition key `aws:PrincipalOrgID` memungkinkan Resource-based Policy untuk memvalidasi apakah principal yang membuat request berasal dari salah satu akun di dalam organisasi AWS tertentu (misal: `o-a1b2c3d4e5`).
- **Skalabilitas**: Tanpa key ini, jika sebuah enterprise memiliki 200 akun AWS yang membutuhkan akses ke bucket data lake terpusat, administrator harus mencantumkan 200 Account ID di blok `Principal`. Hal ini rentan menabrak batasan ukuran karakter maksimum policy (20 KB pada S3 bucket policy) dan membutuhkan update manual setiap kali ada penambahan akun baru.
- **Operasional**: Dengan `aws:PrincipalOrgID`, policy cukup ditulis satu kali. Setiap akun baru yang bergabung ke dalam AWS Organizations secara otomatis memperoleh hak akses tanpa perlu memodifikasi Resource Policy.

#### Soal 9: STS AssumeRole, Session Policies, dan Role Chaining
- Saat identitas melakukan `sts:AssumeRole`, STS menerbitkan kredensial sementara (*AccessKeyId*, *SecretAccessKey*, dan *SessionToken*).
- Jika pemanggil menyertakan argumen **Session Policy** saat pemanggilan API, hak akses sesi sementara tersebut merupakan irisan (*intersection*) antara permissions milik Role target dengan Session Policy yang diberikan.
- **Role Chaining** terjadi saat Sesi A (hasil assume role) memanggil `sts:AssumeRole` kembali untuk mengasumsikan Sesi B. AWS membatasi durasi sesi maksimum role chaining menjadi **maksimal 1 jam** (*hard limit*), terlepas dari apakah konfigurasi `MaxSessionDuration` pada role target diset hingga 12 jam. Hal ini dirancang untuk membatasi *blast radius* masa aktif token yang melompat antar-identitas.

#### Soal 10: Multi-Region Active-Active vs. Multi-AZ High Availability
1. **Fault Domain**:
   - *Multi-AZ*: Berada di dalam satu Region. Meskipun data center fisik terisolasi, AZ berbagi control plane regional yang sama (misal: IAM endpoint regional, S3 regional control plane, STS regional endpoint). Jika terjadi insiden regional control plane degradation, seluruh AZ dapat terpengaruh.
   - *Multi-Region*: Benar-benar terisolasi secara control plane dan data plane fisik. Masalah di Region A tidak memiliki korelasi fisik atau logis dengan Region B.
2. **Replikasi Data & RPO/RTO**:
   - *Multi-AZ*: Menggunakan replikasi sinkron (*synchronous replication*) berkat latensi ultra-rendah (<1-2 ms). RPO = 0 (zero data loss), RTO dalam hitungan detik/menit (failover otomatis).
   - *Multi-Region*: Dibatasi oleh kecepatan cahaya pada kabel fiber optik jarak jauh (latensi puluhan hingga ratusan milidetik). Replikasi data wajib asinkron (*asynchronous*), sehingga RPO > 0 (potensi data loss pada transaksi in-flight). RTO bergantung pada mekanisme DNS routing failover (Route 53 ARC / Health Checks).
3. **CAP Theorem**: Multi-Region Active-Active harus mengorbankan *Strong Consistency* demi *Availability* dan *Partition Tolerance* (menerapkan model *Eventual Consistency* dan mitigasi *conflict resolution*).

---

### C. Pembahasan Skenario Kasus Produksi

#### Skenario 1: Kebocoran Token Developer & Lateral Movement
1. **Root Cause**:
   - **Long-lived Static Credentials**: Kredensial statis developer disimpan secara lokal tanpa penegakan rotasi atau penggunaan IAM Identity Center (SSO) berbasis kredensial sementara.
   - **Overly Permissive Trust Policy**: Role `OrganizationDeploymentRole` di akun produksi memiliki trust policy yang mempercayai seluruh akun `Sandbox-Dev` (`root` trust) tanpa batasan spesifik identitas, MFA, atau condition tag.
   - **Ketiadaan Guardrail Lingkungan Sandbox**: Akun sandbox seharusnya tidak memiliki jalur jaringan atau IAM trust langsung ke akun produksi.
2. **Arsitektur Solusi & Remediasi**:
   - **Service Control Policy (SCP)**: Pasang SCP pada Production OU untuk menolak penghapusan audit logging:
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [
         {
           "Sid": "PreventDisablingSecurityServices",
           "Effect": "Deny",
           "Action": [
             "cloudtrail:StopLogging",
             "cloudtrail:DeleteTrail",
             "guardduty:DeleteDetector",
             "guardduty:DisassociateFromMasterAccount"
           ],
           "Resource": "*"
         }
       ]
     }
     ```
   - **Pemberian Permissions Boundary**: Wajibkan setiap role yang dibuat di akun non-produksi memiliki permissions boundary yang melarang aksi `sts:AssumeRole` ke ARN yang berawalan `arn:aws:iam::987654321098:*` (Akun Produksi).

#### Skenario 2: Anomali Data Transfer Cross-AZ & Latensi Tinggi EKS
1. **Analisis Teknis**:
   - Worker node EKS di Akun 1 dideploy pada AZ bernilai nama `ap-southeast-3a` (yang secara fisik adalah `apse3-az1`).
   - Pod database atau backend target di Akun 2 dideploy pada AZ bernilai nama `ap-southeast-3a` (yang secara fisik adalah `apse3-az3`).
   - Karena kedua layanan berada pada AZ fisik yang berbeda, paket data melintasi inter-AZ fiber backbone AWS. Hal ini menimbulkan biaya data transfer dua arah ($0.01 per GB per arah) dan menambahkan latensi propagasi TCP round-trip.
2. **Solusi Arsitektur**:
   - **Standardisasi Terraform dengan AZ ID**: Hindari pengacuan subnet berbasis `availability_zone = "ap-southeast-3a"`. Gunakan atribut `availability_zone_id` secara konsisten pada resource `aws_subnet`:
     ```hcl
     data "aws_availability_zones" "available" {
       state = "available"
     }

     resource "aws_subnet" "app_subnet" {
       vpc_id               = aws_vpc.main.id
       cidr_block           = "10.0.1.0/24"
       availability_zone_id = "apse3-az1" # Menjamin zona fisik seragam
     }
     ```
   - **Kubernetes Topology Spread**: Pasang node label berbasis `topology.k8s.aws/zone-id` dan konfigurasikan `topologySpreadConstraints` pada manifest pod dengan `topologyKey: topology.k8s.aws/zone-id` untuk memastikan komunikasi in-AZ lokal terjaga.

#### Skenario 3: Krisis Kepatuhan Kedaulatan Data Finansial
1. **Arsitektur Tata Kelola**:
   - Pasang SCP penegak batas wilayah (*Region Restriction*) pada Root OU.
   - Pengecualian wajib diberikan kepada *Global Services* yang control plane-nya beroperasi secara terpusat di `us-east-1` (seperti IAM, Organizations, Route 53, CloudFront, WAF Global, dan Support API).
2. **Kode JSON Service Control Policy (SCP)**:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "EnforceJakartaRegionOnly",
         "Effect": "Deny",
         "NotAction": [
           "iam:*",
           "organizations:*",
           "route53:*",
           "budgets:*",
           "waf:*",
           "cloudfront:*",
           "globalaccelerator:*",
           "shield:*",
           "sts:*",
           "support:*",
           "health:*"
         ],
         "Resource": "*",
         "Condition": {
           "StringNotEquals": {
             "aws:RequestedRegion": [
               "ap-southeast-3"
             ]
           },
           "ArnNotLike": {
             "aws:PrincipalARN": [
               "arn:aws:iam::*:role/OrganizationAccountAccessRole",
               "arn:aws:iam::*:role/AWSControlTowerExecution"
             ]
           }
         }
       },
       {
         "Sid": "DenyUnencryptedS3Buckets",
         "Effect": "Deny",
         "Action": [
           "s3:PutObject"
         ],
         "Resource": "arn:aws:s3:::*/*",
         "Condition": {
           "StringNotEquals": {
             "s3:x-amz-server-side-encryption": "aws:kms"
           }
         }
       }
     ]
   }
   ```
