# BAB 08: Quiz, Challenge, & Knowledge Check
**Infrastructure as Code (IaC) Menggunakan Terraform**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Paradigma Deklaratif vs Imperatif dan Jaminan Idempotensi
Jelaskan secara matematis dan arsitektural bagaimana Terraform mengimplementasikan paradigma *deklaratif* untuk mencapai sifat *idempotent*. Apa yang terjadi di balik layar ketika perintah `terraform apply` dieksekusi berturut-turut sebanyak tiga kali tanpa adanya modifikasi pada kode HCL (*HashiCorp Configuration Language*) maupun infrastruktur aktual di sisi *Cloud Provider*?

### Soal 1.2: Anatomi dan Esensi Kritis `terraform.tfstate`
Mengapa Terraform membutuhkan *State File* (`terraform.tfstate`), sementara beberapa alat orkestrasi lain mengklaim bersifat *stateless*? Analisis metadata apa saja yang tersimpan di dalam *state file* yang secara teknis mustahil diperoleh hanya dengan melakukan *querying* langsung ke *Cloud Provider API* secara *real-time*.

### Soal 1.3: Dekonstruksi Siklus Hidup Eksekusi (*Core Workflow*)
Uraikan secara mendalam operasi internal yang dijalankan oleh Terraform Core pada fase:
1. `terraform init`
2. `terraform plan`
3. `terraform apply`

Fokuskan penjelasan Anda pada bagaimana *Dependency Graph* disusun, kapan *Provider Plugin* dipanggil melalui RPC (*gRPC*), dan bagaimana kalkulasi perbedaan (*diff calculation*) antara *Desired State*, *Prior State*, dan *Observed/Actual State* dilakukan.

### Soal 1.4: Directed Acyclic Graph (DAG) dan Resolusi Dependensi
Bagaimana Terraform Engine membangun *Directed Acyclic Graph* (DAG) untuk menentukan urutan pembuatan resource? Jelaskan perbedaan mendasar antara *Implicit Dependency* (lewat referensi atribut) dan *Explicit Dependency* (menggunakan blok `depends_on`). Sebutkan satu skenario spesifik di mana penyalahgunaan `depends_on` dapat merusak paralelisasi atau menyembunyikan *anti-pattern* perancangan modul.

### Soal 1.5: Skema Variabel, Local Values, dan Tata Kelola Sensitivitas
Bandingkan fungsi arsitektural antara `variable`, `locals`, dan `output`. Kapan seorang *infrastructure engineer* wajib menggunakan `locals` alih-alih mendefinisikan *input variable* baru? Selanjutnya, jelaskan batasan teknis dari atribut `sensitive = true`: apakah penanda ini mengenkripsi data secara kriptografis di dalam file `terraform.tfstate`? Jelaskan implikasi keamanannya.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Protokol State Locking dan Penanganan Lock Abort
Jelaskan mekanisme kerja *Distributed State Locking* (misalnya menggunakan AWS S3 + DynamoDB atau Terraform Cloud). Apa yang terjadi pada atribut `LockID` dan *checksum* MD5 ketika proses eksekusi `terraform apply` terputus secara abnormal (misalnya akibat *SIGKILL* atau *kernel panic* pada *runner* CI/CD)? Kapan penggunaan `terraform force-unlock <LOCK-ID>` diperbolehkan, dan risiko fatal apa yang harus dimitigasi sebelum perintah tersebut dieksekusi?

### Soal 2.2: Deteksi dan Rekonsiliasi Configuration Drift
Sebuah resource Security Group dimodifikasi secara manual melalui Cloud Console (penambahan port 22 dari `0.0.0.0/0`) oleh tim operasional darurat. Bagaimana algoritma `terraform plan -refresh-only` mendeteksi anomali ini (*Configuration Drift*)? Jelaskan komparasi 3 arah (*three-way merge*) antara konfigurasi HCL, *Current State*, dan *Actual Remote Object*.

### Soal 2.3: Refaktorisasi Kode Zero-Downtime via Blok `moved` vs CLI State Surgery
Anda melakukan *refactoring* kode dengan memindahkan resource `aws_instance.web` ke dalam child module `module.compute.aws_instance.web`. Jika Anda langsung menjalankan `terraform apply`, Terraform akan menghancurkan (*destroy*) instance lama dan membuat (*create*) instance baru. Jelaskan bagaimana Anda mencegah destruksi tersebut menggunakan:
1. Blok deklaratif `moved` (Terraform 1.1+)
2. Perintah imperatif `terraform state mv`

Bandingkan trade-off auditabilitas dan reliabilitas tim dari kedua pendekatan tersebut.

### Soal 2.4: Mitigasi Blast Radius: Monolithic vs Decoupled State
Mengapa arsitektur *Monolithic State* (menggabungkan VPC, EKS/GKE Cluster, RDS, dan Route53 dalam satu direktori/root module) dikategorikan sebagai *high-risk anti-pattern* pada skala enterprise? Analisis dua metode arsitektur untuk memisahkan *state* (*Layered State Architecture*) dan bagaimana data antar-layer dihubungkan secara *loose-coupling* (misal: `terraform_remote_state` vs *SSM Parameter Store/Consul/Cloud Native Data Sources*).

### Soal 2.5: Lifecycle Meta-Arguments: `create_before_destroy` vs Race Condition
Analisis kegunaan meta-argument `lifecycle { create_before_destroy = true }`. Pada resource apa saja fitur ini mutlak diperlukan, dan skenario kegagalan apa yang muncul jika resource tersebut memiliki *hard constraint* pada *unique naming* (misal: AWS IAM Role name atau S3 Bucket name) saat proses penggantian (*replacement*) berlangsung?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Skala Besar — Partial Apply Failure & State Desynchronization
* **Konteks:** Tim DevOps menjalankan pipeline deployment Terraform untuk membuat arsitektur multi-AZ database (RDS Primary + Read Replica), Security Groups, dan Subnet Groups. Di tengah proses pembuatan Read Replica, *Cloud Provider* mengalami *API throttling/outage* parsial, menyebabkan koneksi TCP timeout. Pipeline CI/CD mati dengan status `Error: Provider produced inconsistent final plan` dan keluar dengan exit code 1.
* **Kondisi Aktual:** Resource Primary DB berhasil dibuat dan dialokasikan IP oleh cloud provider, namun metadata status penulisan ke remote state S3 terputus sebelum sinkronisasi final selesai. Security Group tercipta, tetapi DB Subnet Group berada dalam status `partially configured`.
* **Pertanyaan Diagnostik:**
  1. Langkah investigasi sistematis apa yang harus dilakukan sebelum mengeksekusi perintah Terraform lainnya untuk memastikan kondisi *in-memory* vs *remote state*?
  2. Bagaimana cara memverifikasi apakah Primary DB sudah tercatat di remote state tanpa memicu destruksi pada apply berikutnya?
  3. Tuliskan urutan mitigasi langkah demi langkah (termasuk penggunaan perintah `terraform refresh`, `terraform state list`, atau `terraform import`) untuk memulihkan state agar pipeline CI/CD dapat melanjutkan eksekusi secara idempotent tanpa memicu eror duplicate resource.

---

### Skenario B: Race Condition dan State Lock Starvation pada CI/CD Terdistribusi
* **Konteks:** Perusahaan menerapkan skema GitOps dengan multi-branch deployment. Dua engineer secara simultan melakukan *merge* Pull Request ke branch `main`. Runner CI/CD Pipeline A (PR #101) dan Runner Pipeline B (PR #102) terpicu pada detik yang hampir sama.
* **Gejala:** Runner A berhasil mengakuisisi lock pada DynamoDB, tetapi eksekusi mengalami degradasi performa karena provisioner eksternal memakan waktu 25 menit. Runner B mencoba mengeksekusi `terraform plan` dan langsung gagal dengan:
  ```text
  Error: Error acquiring the state lock: ConditionalCheckFailedException:
  The conditional request failed
  Lock Info:
    ID:        a1b2c3d4-xxxx-yyyy-zzzz
    Path:      terraform-production/terraform.tfstate-md5
    Operation: OperationTypeApply
    Who:       runner@ci-agent-04
    Created:   2026-03-30 02:14:02 UTC
  ```
  Salah satu engineer secara impulsif masuk ke AWS Console dan menghapus item LockID di tabel DynamoDB secara manual saat Runner A masih melakukan penulisan resource.
* **Pertanyaan Diagnostik:**
  1. Dampak destruktif apa yang secara riil dapat terjadi pada `terraform.tfstate` ketika LockID dihapus paksa saat sebuah proses apply masih berlangsung aktif?
  2. Bagaimana arsitektur antrean CI/CD seharusnya dirancang untuk menangani konkurensi apply pada level pipeline sebelum perintah Terraform di-invoke?
  3. Jika terdeteksi bahwa *remote state* korup (*corrupted JSON* atau *mismatched serial number*), bagaimana protokol Disaster Recovery untuk mengembalikan state ke titik konsisten terakhir?

---

### Skenario C: Architectural Trade-off — Monorepo Module Explosion vs Versioned Registry
* **Konteks:** Sebuah institusi finansial memiliki 40 tim microservice yang semuanya menggunakan Terraform untuk mendefinisikan infrastruktur aplikasinya. Saat ini seluruh tim mereferensikan modul dasar (Base Module VPC, Security Group, IAM, Database) langsung menggunakan jalur lokal relatif atau Git subpath:
  ```hcl
  source = "git::https://github.com/enterprise/terraform-modules.git//modules/microservice-stack?ref=main"
  ```
* **Permasalahan:** Tim Core Infrastructure merilis update breaking change pada modul `microservice-stack` untuk menambal celah keamanan (menghapus parameter lama dan menambahkan validasi ketat). Dalam hitungan jam, puluhan pipeline microservice gagal eksekusi (`terraform plan` broken), dan beberapa tim tidak dapat melakukan hotfix deployment darurat.
* **Pertanyaan Diagnostik:**
  1. Bedah kelemahan arsitektur dari pola referensi modul di atas (`?ref=main`).
  2. Rancang arsitektur distribusi modul enterprise yang ideal menggunakan Semantic Versioning (SemVer) dan Terraform Registry (Private Registry/Git Tagging).
  3. Bagaimana strategi migrasi backward-compatibility yang harus diterapkan tim Core Infrastructure agar pembaruan modul tidak merusak (*breaking*) ratusan *root modules* yang bergantung padanya?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade HA Base Infrastructure with Remote Backend, State Locking, and Strict Guardrails

#### 1. Problem Statement
Anda ditugaskan oleh Head of Infrastructure untuk membangun fondasi IaC bagi sebuah platform perbankan digital. Seluruh proses provisioner lokal dilarang keras menggunakan *local state*. Modul harus memiliki isolasi lingkungan (*environment separation*), mematuhi prinsip *least-privilege blast radius*, dan menerapkan *lifecycle guardrails* agar database operasional tidak dapat terhapus secara tidak sengaja oleh kesalahan manusia maupun pipeline script.

#### 2. Technical Requirements
1. **Remote Backend & Distributed Locking:**
   - Konfigurasikan Terraform Backend menggunakan AWS S3 (atau GCP Cloud Storage / Azure Blob) dengan enkripsi sisi server (SSE-KMS/AES256) dan TLS enforced.
   - Konfigurasikan tabel DynamoDB untuk mekanisme *State Locking* terdistribusi.
   - Buat file `backend.tf` yang bersih dan modular (dapat menerima backend-config via file atau parameter CLI tanpa hardcoded credentials).
2. **Modular Architecture:**
   Bangun struktur direktori enterprise berikut:
   ```text
   ├── environments/
   │   ├── staging/
   │   │   ├── main.tf
   │   │   ├── variables.tf
   │   │   ├── terraform.tfvars
   │   │   └── backend.hcl
   │   └── production/
   │       ├── main.tf
   │       ├── variables.tf
   │       ├── terraform.tfvars
   │       └── backend.hcl
   └── modules/
       ├── networking/
       │   ├── main.tf
       │   ├── variables.tf
       │   └── outputs.tf
       └── database/
           ├── main.tf
           ├── variables.tf
           └── outputs.tf
   ```
3. **Guardrails & Lifecycle Constraints:**
   - Pada modul database, implementasikan *lifecycle block* `prevent_destroy = true`.
   - Implementasikan `create_before_destroy = true` pada komponen security group yang terhubung ke database.
   - Variabel kredensial master database (`db_password`) harus ditandai sebagai `sensitive = true`, divalidasi panjang karakternya menggunakan blok `validation` bawaan HCL (minimal 16 karakter, mengandung kombinasi alfanumerik), dan nilainya di-inject via environment variable `TF_VAR_db_password` (bukan di dalam file `.tfvars`).
4. **Outputs Management:**
   - Module `networking` harus mengekspor `vpc_id` dan `subnet_ids` yang secara aman dikonsumsi oleh module `database`.
   - Modul root hanya boleh mengekspos endpoint database dan identifier non-sensitif. Output sensitif (seperti connection string lengkap) wajib diberi flag `sensitive = true`.

#### 3. Constraints & Edge Cases
- Tidak boleh ada hardcoded secret/credentials (AWS Access Key / Secret Key) di dalam kode.
- Modul database tidak boleh memiliki ketergantungan eksplisit `depends_on` ke modul networking; gunakan *implicit dependency* melalui atribut referensi.
- Harus menyertakan file validasi format dan static code analysis check menggunakan `terraform fmt -check` dan `terraform validate`.

#### 4. Expected Output & Deliverables
Kandidat/Siswa harus mengumpulkan artefak kode yang terdiri dari:
1. Kode lengkap HCL (`backend.tf`, `modules/`, dan `environments/production/`).
2. Script/Instruksi shell eksekusi deployment awal menggunakan argumen `-backend-config`.
3. Output terminal dari simulasi validasi eksekusi:
   - Bukti log terminal eksekusi `terraform plan -detailed-exitcode`.
   - Bukti pengujian keamanan ketika seseorang mencoba mengeksekusi `terraform destroy` pada database (membuktikan aktivasi `prevent_destroy`).
   - Bukti log eksekusi saat input password tidak memenuhi kriteria validasi regex.

---

## 5. Knowledge Check & Checklist

Pastikan Anda menguasai seluruh poin di bawah ini secara konseptual dan praktis sebelum melanjutkan ke materi berikutnya.

### Saya harus memahami:
- [ ] Logika rekonsiliasi antara *Desired State* (kode HCL), *Prior State* (file `.tfstate`), dan *Observed State* (infrastruktur nyata) beserta mekanisme pembuatan *Execution Plan*.
- [ ] Arsitektur internal Terraform Engine vs Provider Plugins yang berkomunikasi melalui RPC (*Remote Procedure Call*).
- [ ] Implikasi keamanan dari file `terraform.tfstate` yang menyimpan nilai *plaintext* dari seluruh resource, termasuk variabel yang ditandai `sensitive = true`.
- [ ] Perbedaan fungsional dan batasan teknis antara Terraform Workspaces vs Directory-based Environment Separation (Production vs Staging).
- [ ] Mekanisme kerja Distributed State Locking dan siklus hidup metadata lock pada backend storage (misal: S3/DynamoDB).
- [ ] Teori Directed Acyclic Graph (DAG), deteksi *cyclic dependency error*, serta optimalisasi kalkulasi konkurensi (flag `-parallelism`).

### Saya tidak perlu menghafal:
- [ ] Seluruh argumen dan skema atribut dari ratusan resource provider (misal: argumen spesifik dari `aws_db_instance` atau `azurerm_kubernetes_cluster`); gunakan dokumentasi resmi Terraform Registry sebagai referensi runtime.
- [ ] Sintaks JSON schema internal dari file `.tfstate` tingkat rendah secara mutlak.
- [ ] Nilai spesifik *exit code* numerik internal selain return standard (`0` = no diff/success, `1` = error, `2` = success with diff pada `-detailed-exitcode`).

### Saya harus bisa melakukan:
- [ ] Menginisialisasi, mengonfigurasi, dan memigrasikan backend lokal ke remote backend (S3/DynamoDB, GCS, atau Terraform Cloud) dengan aman tanpa kehilangan data state.
- [ ] Mengisolasi lingkungan infrastruktur menggunakan pemisahan direktori berbasis best practices enterprise.
- [ ] Melakukan operasi bedah state kritis menggunakan CLI: `terraform state list`, `terraform state show`, `terraform state mv`, dan `terraform state rm`.
- [ ] Mengadopsi resource yang sudah ada (*existing legacy infrastructure*) ke dalam pengelolaan Terraform menggunakan perintah `terraform import` dan blok `import` (Terraform 1.5+).
- [ ] Mengimplementasikan *HCL conditional expressions*, *for expressions*, *dynamic blocks*, dan *input validations* tingkat lanjut.
- [ ] Melakukan refaktor modul menggunakan blok deklaratif `moved` tanpa menimbulkan efek destruksi (*destroy-and-recreate*) pada sistem produksi.
- [ ] Menjalankan diagnosis error dan troubleshooting mendalam menggunakan variabel sistem `TF_LOG=DEBUG` atau `TF_LOG_CORE=TRACE`.