# Bab 05: Enterprise Module Architecture & Reusability - Quiz & Challenge

---

## 1. Basic Questions (5 Soal)

### Soal 1
Apa perbedaan utama antara *Root Module* dan *Child Module* dalam siklus eksekusi Terraform?
- A. Root module hanya berisi resource compute, sedangkan child module berisi resource storage.
- B. Root module adalah direktori kerja utama tempat perintah Terraform CLI dieksekusi, sedangkan child module dipanggil melalui blok `module` dari root module atau modul lain.
- C. Root module tidak boleh memiliki file `variables.tf`, sedangkan child module wajib memilikinya.
- D. Child module mengontrol backend remote state locking, sedangkan root module tidak memiliki backend.

### Soal 2
Manakah praktik penulisan konfigurasi provider yang benar pada sebuah *Child Module* yang dirancang untuk dibagikan secara luas di enterprise registry?
- A. Mendeklarasikan kredensial `access_key` dan `secret_key` secara eksplisit di dalam blok `provider "aws" {}`.
- B. Mendeklarasikan blok backend S3 di dalam file `main.tf` child module.
- C. Mendeklarasikan dependensi provider dan versinya di dalam blok `terraform.required_providers` tanpa mengonfigurasi credentials atau block provider konkret.
- D. Mengosongkan seluruh file `versions.tf`.

### Soal 3
Dalam semantic versioning (`vMAJOR.MINOR.PATCH`), situasi manakah yang **wajib** menaikkan nomor **MAJOR** version pada modul Terraform?
- A. Menambahkan parameter input baru bertipe string yang memiliki nilai `default = "standard"`.
- B. Menambahkan metadata tag baru pada resource EC2.
- C. Menghapus variabel input yang sebelumnya ada, atau mengubah tipe data variabel mandatory tanpa backward compatibility.
- D. Memperbaiki kesalahan ejaan (typo) pada blok `description` di dalam file `variables.tf`.

### Soal 4
Fungsi utama dari atribut `sensitive = true` pada blok `output` Terraform adalah:
- A. Mengenkripsi nilai output di dalam file `terraform.tfstate` menggunakan algoritma AES-256.
- B. Mencegah nilai output ditampilkan secara terang-terangan (plaintext) pada terminal console saat `terraform plan` dan `terraform apply`.
- C. Menghapus resource terkait secara otomatis jika terdeteksi kebocoran kredensial.
- D. Mengubah nilai output menjadi hash MD5 yang tidak dapat dibaca oleh downstream module.

### Soal 5
Manakah format sintaks pemanggilan modul dari remote Git repository yang mengunci rilis pada tag Git tertentu secara valid?
- A. `source = "github.com/corp/terraform-aws-vpc?branch=main"`
- B. `source = "git::https://github.com/corp/terraform-aws-vpc.git?ref=v1.2.0"`
- C. `source = "git::https://github.com/corp/terraform-aws-vpc.git#commit=latest"`
- D. `source = "registry://corp/terraform-aws-vpc@v1.2.0"`

---

## 2. Intermediate Questions (5 Soal)

### Soal 6
Diberikan konfigurasi variabel berikut:
```hcl
variable "environment_type" {
  type        = string
  description = "Tipe deployment target"

  validation {
    condition     = contains(["non-prod", "prod"], var.environment_type)
    error_message = "Tipe environment harus non-prod atau prod."
  }
}
```
Apa yang terjadi jika seorang engineer menjalankan `terraform plan -var="environment_type=staging"`?
- A. Terraform mengubah nilainya secara otomatis menjadi `non-prod`.
- B. Terraform mengabaikan variabel tersebut dan meminta input ulang secara interaktif.
- C. Terraform melempar eksepsi error validasi pada tahap pre-flight validation dan eksekusi langsung dihentikan sebelum menghubungi API cloud.
- D. Terraform tetap melanjutkan `plan`, namun akan memunculkan peringatan (warning) pada tahap `apply`.

### Soal 7
Apa yang dimaksud dengan fenomena *Leaky Abstraction* dalam konteks desain modul Terraform?
- A. State file bocor ke public internet melalui bucket S3 yang tidak dienkripsi.
- B. Modul mewajibkan pemanggil (*caller*) untuk memahami dan mengonfigurasi detail implementasi internal resource yang seharusnya disembunyikan oleh modul tersebut.
- C. Modul menggunakan memori RAM berlebih saat menghitung dependensi graf (*DAG memory leak*).
- D. Mengirimkan logs audit modul ke sistem monitoring eksternal yang tidak sah.

### Soal 8
Bagaimana cara terbaik menangani dependensi di mana *Modul A (Compute)* membutuhkan output dari *Modul B (Networking)*, namun *Modul B* juga membutuhkan data dari *Modul A*, yang menyebabkan siklus dependensi melingkar (*Cyclic Dependency Error*)?
- A. Menggabungkan kedua modul menjadi satu modul raksasa tanpa batasan layer.
- B. Menjalankan perintah `terraform apply -target=module.network` secara manual setiap kali pipeline berjalan.
- C. Melakukan refaktorisasi dengan memisahkan resource penghubung (*bridging resource*, misal: security group rule atau IAM binding) ke Root Module atau modul penengah tersendiri.
- D. Menonaktifkan dependensi graph Terraform menggunakan flag `--ignore-cycles`.

### Soal 9
Sebuah tim platform ingin memastikan bahwa jika modul mereka dipanggil di lingkungan production, flag `multi_az` pada database wajib bernilai `true`. Manakah blok validasi yang tepat untuk ditaruh di `variables.tf` modul komposit?
```hcl
# Opsi A
validation {
  condition     = var.environment == "production" ? var.multi_az == true : true
  error_message = "multi_az wajib bernilai true untuk lingkungan production."
}

# Opsi B
validation {
  condition     = var.multi_az == "production"
  error_message = "multi_az salah."
}

# Opsi C
validation {
  condition     = can(var.environment && var.multi_az)
  error_message = "Error environment."
}

# Opsi D
validation {
  condition     = var.environment != "production" && var.multi_az == false
  error_message = "Gagal validasi."
}
```
Pilihlah opsi sintaks yang benar secara logika dan semantik HCL.

### Soal 10
Mengapa penggunaan constraint versi seperti `version = "~> 2.1.0"` pada pemanggilan modul di Root Module lebih direkomendasikan daripada mengunci ke versi absolut `version = "2.1.0"` pada skala enterprise?
- A. Karena `~> 2.1.0` mengizinkan pembaruan otomatis ke versi `3.0.0` jika tersedia rilis baru.
- B. Karena `~> 2.1.0` mengizinkan penyerapan patch perbaikan bug dan celah keamanan otomatis (`2.1.1`, `2.1.2`) tanpa risiko merusak kompatibilitas akibat perubahan breaking change pada rilis mayor atau minor baru.
- C. Karena versi absolut akan menurunkan performa eksekusi `terraform init`.
- D. Karena Terraform Registry melarang penggunaan versi absolut pada level produksi.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Industri)

### Skenario 1: The Broken Enterprise CI/CD Pipeline
Tim DevOps di Bank Digital XYZ memiliki 25 microservices yang masing-masing memiliki repositori Terraform sendiri. Setiap repositori memanggil modul jaringan enterprise dengan konfigurasi:
```hcl
module "network" {
  source = "git::https://gitlab.internal.bankxyz.com/platform-infra/terraform-aws-network.git"
}
```
Suatu hari, tim Platform Infrastructure menambahkan parameter baru bernama `transit_gateway_id` yang bersifat mandatory (tanpa nilai `default`) pada branch `main` modul jaringan tersebut. Dua jam kemudian, seluruh pipeline deployment microservice hancur total (*failed plan/apply*).
1. Analisis akar penyebab (*root cause*) bencana arsitektur ini.
2. Jelaskan langkah remedi jangka pendek untuk memulihkan microservices.
3. Rancang strategi pencegahan jangka panjang menggunakan Semantic Versioning dan Private Module Registry.

### Skenario 2: Data Exfiltration via CI Logs
Sebuah platform e-commerce mengalami audit keamanan di mana auditor menemukan plaintext connection string database yang berisi kredensial master tertera jelas pada log GitLab CI/CD execution. Modul database ditulis sebagai berikut:
```hcl
# modules/rds/outputs.tf
output "connection_string" {
  value = "postgresql://${aws_db_instance.db.username}:${aws_db_instance.db.password}@${aws_db_instance.db.endpoint}/${aws_db_instance.db.db_name}"
}
```
1. Jelaskan mengapa Terraform mengekspos data ini ke terminal logs.
2. Bagaimana cara merevisi output tersebut agar Terraform memblokir pencetakan nilai ke stdout saat apply?
3. Sebutkan pola arsitektur yang lebih aman daripada meneruskan connection string master password melalui Terraform outputs antar-modul.

### Skenario 3: The Monolithic Module Decomposition
Sebuah tim platform memiliki modul monolitik `terraform-azure-all-in-one` sebesar 4.500 baris kode yang mencakup Resource Group, VNet, AKS, Azure SQL, Redis, dan KeyVault. Waktu eksekusi `terraform plan` memakan waktu 42 menit, dan sering terjadi API rate limiting dari Azure Resource Manager.
1. Rancang arsitektur dekomposisi modul baru berbasis prinsip *Single Responsibility* dan pembagian Layer (L1 vs L2).
2. Tentukan bagaimana alur data (*data flow*) antar modul baru tersebut.
3. Bagaimana strategi migrasi state file Terraform agar resource fisik di Azure tidak dihancurkan (*destroyed*) saat dipecah menjadi modul-modul kecil?

---

## 4. Practical Chapter Challenge
Anda ditugaskan sebagai Principal Infrastructure Architect untuk merancang dan memvalidasi fondasi modul Terraform enterprise di sebuah perusahaan logistik global.

### Target Spesifikasi Modul: `terraform-aws-secure-storage`
1. **Aturan Variabel**:
   - `storage_prefix`: Wajib bertipe string, diawali dengan `logistics-corp-`, hanya karakter huruf kecil dan tanda minus (`^[a-z0-9-]+$`).
   - `storage_tier`: Wajib dibatasi hanya menerima nilai: `STANDARD`, `INTELLIGENT_TIERING`, atau `GLACIER`.
   - `backup_retention_days`: Tipe number, wajib berada pada rentang `>= 7` dan `<= 365`.
2. **Aturan Enkapsulasi**:
   - Seluruh akses publik (`block_public_acls`, `block_public_policy`, `ignore_public_acls`, `restrict_public_buckets`) harus bernilai `true` dan **tidak boleh dibuka** sebagai variabel yang bisa dimodifikasi caller.
   - Enkripsi KMS wajib aktif secara default.
3. **Aturan Output**:
   - Keluarkan `bucket_arn` dan `kms_key_arn`.
   - Modul dilarang keras mengeluarkan atribut sensitif yang tidak terlindungi.
4. **Validasi Otomatis**:
   - Gunakan skrip Python linter terintegrasi (`enterprise_module_linter.py`) untuk memvalidasi bahwa seluruh aturan enterprise terpenuhi sebelum modul dipublikasikan ke git repository.

---

## Jawaban & Kunci Pembahasan

### 1. Basic Questions
- **Soal 1**: **B**. Root module adalah root directory eksekusi Terraform CLI, sedangkan child module dipanggil via blok `module`.
- **Soal 2**: **C**. Child module enterprise dilarang meng-hardcode provider credentials/backend; ia hanya mendeklarasikan dependensi di `required_providers`.
- **Soal 3**: **C**. Menghapus variabel input atau mengubah tipe/kompatibilitas adalah breaking change yang mewajibkan kenaikan versi MAJOR.
- **Soal 4**: **B**. `sensitive = true` menyembunyikan nilai output dari terminal output / console logs (namun tetap tersimpan plaintext di file `.tfstate`).
- **Soal 5**: **B**. Format Git URL Terraform menggunakan argumen query `?ref=vX.Y.Z` untuk menargetkan Git tag rilis tertentu.

### 2. Intermediate Questions
- **Soal 6**: **C**. Kondisi validasi dievaluasi sebelum interaksi API, sehingga CLI langsung mengembalikan pesan error yang didefinisikan di `error_message`.
- **Soal 7**: **B**. Leaky abstraction terjadi ketika detail implementasi internal terekspos keluar sehingga caller dipaksa memahami kompleksitas internal.
- **Soal 8**: **C**. Pisahkan dependensi melingkar dengan mengekstrak resource penghubung ke Root Module atau modul penengah agar graf eksekusi tetap Directed Acyclic Graph (DAG).
- **Soal 9**: **A**. Logika ternary conditional pada opsi A memvalidasi: jika environment == "production", maka periksa apakah `multi_az == true`. Jika bukan production, bernilai `true` (valid).
- **Soal 10**: **B**. Operator pessimistic constraint `~> 2.1.0` mengizinkan perbaikan bug minor/patch (`2.1.x`) tanpa mengambil risiko breaking change dari versi mayor baru.

### 3. Scenario-Based Questions
- **Skenario 1**:
  1. *Root cause*: Pemanggilan modul tidak di-pin pada versi/tag tertentu (`ref`), melainkan mengarah langsung ke branch default (`main`). Penambahan variabel mandatory tanpa default value merupakan breaking change yang merusak pemanggilan modul yang ada.
  2. *Remedi*: Di repositori modul jaringan, berikan nilai `default = null` atau rollback commit pada `main`, lalu rilis branch baru. Di microservices, segera kunci source URI ke commit hash atau rilis lama yang stabil.
  3. *Pencegahan*: Migrasikan modul ke Private Module Registry atau wajibkan penggunaan Git tag SemVer pada blok pemanggilan: `?ref=v1.0.0`. Terapkan aturan branching protection pada repositori modul jaringan di mana commit langsung ke `main` dilarang dan seluruh rilis wajib melalui tagging SemVer terencana.
- **Skenario 2**:
  1. *Penyebab*: Modul tidak menyertakan atribut `sensitive = true` pada blok output, sehingga Terraform mencetak nilai secara mentah saat execution summary.
  2. *Revisi*:
     ```hcl
     output "connection_string" {
       value     = "postgresql://${aws_db_instance.db.username}:${aws_db_instance.db.password}@${aws_db_instance.db.endpoint}/${aws_db_instance.db.db_name}"
       sensitive = true
     }
     ```
  3. *Arsitektur Lebih Aman*: Alih-alih merangkai connection string via output Terraform, modul harus membuat username dan password langsung di AWS Secrets Manager atau HashiCorp Vault. Modul downstream hanya menerima output berupa ARN Secrets Manager, lalu aplikasi mengambil kredensial secara dinamis saat runtime melalui SDK menggunakan IAM Authentication.
- **Skenario 3**:
  1. *Dekomposisi*: Pisahkan menjadi layer mandiri:
     - L1 Foundation: `network-module` (VNet, Subnet).
     - L1 Security: `keyvault-module` (KeyVault, Access Policies).
     - L2 Platform: `aks-module` (Cluster AKS, Node Pools).
     - L2 Data: `data-tier-module` (Azure SQL, Redis).
  2. *Alur Data*: Root module menginstansiasi L1 modules, lalu memasok output ID VNet/Subnet dari L1 sebagai input parameter ke L2 modules.
  3. *Migrasi State*: Gunakan blok deklarasi `moved` (Terraform 1.1+) di dalam Root Module untuk memindahkan resource address lama ke address modul baru:
     ```hcl
     moved {
       from = azurerm_virtual_network.vnet
       to   = module.network.azurerm_virtual_network.vnet
     }
     ```
     Atau gunakan perintah CLI `terraform state mv` agar resource cloud tidak dihapus dan dibuat ulang (*zero downtime migration*).