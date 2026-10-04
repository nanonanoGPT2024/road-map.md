# Module 01: Konsep Declarative IaC, State Management, & Provider HCL

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Membedakan pendekatan provisioning infrastruktur **Imperatif** (CLI script step-by-step) vs **Deklaratif** (State-driven IaC).
2. Menguasai sintaks bahasa **HCL (HashiCorp Configuration Language)**: blocks, arguments, expressions, variables, dan outputs.
3. Memahami peran sentral **Terraform State (`terraform.tfstate`)** sebagai *single source of truth* pemetaan resource nyata di cloud.
4. Menjalankan siklus hidup perintah Terraform/OpenTofu: `init`, `plan`, `apply`, dan `destroy`.

---

## 2. Prerequisite
- Memahami konsep dasar resource cloud (VPC, Subnet, Virtual Machines / EC2, Security Groups).
- Mengetahui cara kerja format data JSON atau YAML.

---

## 3. Concept
Zaman mengklik konsol web cloud (AWS Management Console, GCP Console) secara manual untuk membuat server telah berakhir. Praktik manual (*ClickOps*) memiliki kelemahan fatal:
- Tidak ada riwayat perubahan (*no version control*).
- Tidak dapat diuji ulang secara identik (*not reproducible*).
- Rawan kesalahan manusia (salah pilih ukuran instance atau salah centang firewall).

**Infrastructure as Code (IaC)** memperlakukan infrastruktur selayaknya kode software aplikasi:
Ditulis dalam file teks (HCL), disimpan di Git, di-review via Pull Request, dan di-deploy secara otomatis.

**Terraform** (dan alternatif open-source-nya, **OpenTofu**) menggunakan pendekatan **Deklaratif**:
Anda hanya mendefinisikan *apa yang Anda inginkan* di akhir:
```hcl
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"
}
```
Terraform Engine akan membaca status cloud saat ini, membandingkannya dengan state file, lalu menghitung urutan tindakan penambahan, pengubahan, atau penghapusan resource secara matematis (*execution plan graph*).

---

## 4. Why?
Mengapa Terraform/OpenTofu menjadi standar industri?
1. **Multi-Cloud & Agnostik**: Menggunakan 1 sintaks bahasa HCL yang sama untuk mengelola AWS, Google Cloud, Azure, Cloudflare, Kubernetes, hingga GitHub.
2. **Execution Plan Safety (`terraform plan`)**: Anda dapat melihat simulasi detail perubahan sebelum dieksekusi secara nyata (tanda `+` untuk create, `~` untuk modify, `-` untuk destroy).
3. **Graph Dependency Engine**: Terraform secara otomatis membangun pohon ketergantungan (DAG - Directed Acyclic Graph) dan membuat resource yang tidak saling bergantung secara paralel untuk menghemat waktu.

---

## 5. What?
Komponen fundamental Terraform/OpenTofu:
- **Providers**: Plugin eksternal yang menerjemahkan kode HCL menjadi panggilan API spesifik vendor (contoh: `hashicorp/aws`, `digitalocean/digitalocean`).
- **Resources**: Komponen infrastruktur fisik/virtual yang dikelola (contoh: `aws_s3_bucket`, `google_compute_instance`).
- **Data Sources**: Membaca resource yang sudah ada di cloud tanpa mengelolanya (contoh: mencari AMI Linux terbaru).
- **Terraform State File (`terraform.tfstate`)**: File JSON yang mencatat ID nyata resource di cloud, atribut metadata, dan pemetaan ke blok kode HCL Anda.

---

## 6. How?
Siklus hidup operasional Terraform:

```text
[ 1. terraform init ]
  -> Download provider plugins (aws, gcp, random) ke folder .terraform/
  -> Konfigurasi backend penyimpanan state
              │
              ▼
[ 2. terraform plan ]
  -> Baca konfigurasi kode HCL lokal
  -> Baca file terraform.tfstate
  -> Lakukan API refresh ke Cloud Provider (Ambil status terkini)
  -> Tampilkan kalkulasi diff: Plan: 2 to add, 1 to change, 0 to destroy
              │
              ▼
[ 3. terraform apply ]
  -> Konfirmasi persetujuan manusia ("yes")
  -> Panggil API Cloud untuk mengeksekusi perubahan
  -> Simpan ID dan metadata baru ke dalam terraform.tfstate
              │
              ▼
[ 4. terraform destroy ] (Opsional)
  -> Menghapus seluruh resource yang terdaftar di state file secara bersih
```

---

## 7. Analogy
Bayangkan **Terraform** seperti **Arsitek & Kontraktor Gedung**:
- **Pendekatan Imperatif (Bash Script)**: Seperti memberi instruksi mandor per detik: *"Aduk semen 2 ember, taruh bata merah di pojok kiri, lalu paku kayu."* Jika semen habis di tengah jalan, Anda harus membongkar manual.
- **Pendekatan Deklaratif (Terraform)**: Anda menyerahkan denah cetak biru (*blueprint HCL*) gedung 3 lantai. Sang arsitek (Terraform) melihat kondisi tanah saat ini (*State*), lalu menyusun rencana kerja terstruktur untuk mewujudkan gedung persis seperti denah biru Anda.

---

## 8. Diagram
```text
+-------------------------------------------------------------+
|                     CODE FILES (*.tf)                       |
|  main.tf  |  variables.tf  |  outputs.tf  |  terraform.tfvars
+-------------------------------------------------------------+
                               │
                               ▼
+-------------------------------------------------------------+
|                      TERRAFORM ENGINE                       |
|                                                             |
|   +-----------------------+      +-----------------------+  |
|   | Dependency Graph DAG  | <==> | terraform.tfstate     |  |
|   | (Kalkulasi Plan Diff) |      | (State Source of Truth|  |
|   +-----------------------+      +-----------------------+  |
|                               │                             |
|             Panggilan API via Provider Plugins              |
+-------------------------------------------------------------+
                               │
                               ▼
+-------------------------------------------------------------+
|                      CLOUD INFRASTRUCTURE                   |
|       [ AWS VPC ]       [ EC2 Instances ]       [ S3 Bucket ]
+-------------------------------------------------------------+
```

---

## 9. Simple Example
Contoh konfigurasi HCL dasar (`main.tf`):

```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
}

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true

  tags = {
    Name        = "production-vpc"
    Environment = "prod"
  }
}

output "vpc_id" {
  description = "ID dari VPC yang berhasil dibuat"
  value       = aws_vpc.main.id
}
```

---

## 10. Practical Example
Perintah CLI Terraform esensial dalam workflow harian:

```bash
# 1. Format file HCL agar rapi sesuai style guide resmi
terraform fmt -recursive

# 2. Validasi sintaksis dan parameter konfigurasi tanpa memanggil cloud
terraform validate

# 3. Buat file rencana eksekusi biner yang terkunci
terraform plan -out=tfplan.binary

# 4. Terapkan rencana yang sudah di-plan secara presisi
terraform apply tfplan.binary

# 5. Menampilkan isi state file saat ini
terraform state list
terraform state show aws_vpc.main
```

---

## 11. Real World Example
### Kasus: Terhapusnya Database Production Akibat Salah Edit Resource Identifier
1. Seorang engineer ingin mengubah nama identifier database RDS di HCL:
   ```hcl
   # Sebelum:
   resource "aws_db_instance" "main" {
     identifier = "prod-db"
   }
   # Diubah menjadi:
   resource "aws_db_instance" "main" {
     identifier = "prod-database-primary"
   }
   ```
2. Pada AWS RDS, properti `identifier` bersifat *Forces Replacement* (tidak bisa di-rename langsung).
3. Engineer menjalankan `terraform apply` dengan flag `-auto-approve` tanpa membaca output plan.
4. Terraform menghancurkan (*Destroy*) database lama beserta seluruh datanya, lalu membuat database baru yang kosong!
5. **Solusi SRE**:
   - Pasang blok proteksi:
     ```hcl
     lifecycle {
       prevent_destroy = true
     }
     ```
   - Larang keras flag `-auto-approve` di pipeline produksi.
   - Wajibkan review output `terraform plan` oleh minimal 2 engineer senior sebelum apply.

---

## 12. Trade-offs
| Paradigma IaC | Declarative (Terraform / OpenTofu) | Imperative (Bash / AWS CLI / Python Boto3) |
|---|---|---|
| **Manajemen State** | Otomatis dilacak dalam state file | Manual (Script harus mengecek kondisi sebelum membuat) |
| **Idempotency** | Alami (Dijalankan 10x hasilnya tetap identik) | Sulit (Script rentan error `ResourceAlreadyExists`) |
| **Kurva Belajar** | Harus mempelajari sintaks HCL | Menggunakan bahasa pemrograman yang sudah dikuasai |
| **Destruction / Cleanup** | Sangat bersih (`terraform destroy`) | Rumit (Harus menulis script pembongkaran manual) |

---

## 13. When To Use
- Mengelola provisioning resource cloud skala menengah-besar (VPC, Subnet, Cluster K8s, RDS, IAM, S3).
- Membangun arsitektur multi-environment yang identik (Dev, Staging, Production).

---

## 14. When NOT To Use
- Untuk konfigurasi internal di dalam sistem operasi (seperti menginstal paket apt, mengatur konfigurasi nginx, atau mengelola user Linux); gunakan **Ansible** untuk configuration management di dalam OS.

---

## 15. Common Mistakes
1. **Meng-commit `terraform.tfstate` ke Git Repository**: File state sering memuat nilai sensitif (password database, private key) dalam bentuk plaintext! File state **wajib disimpan di Remote Backend terenkripsi** (seperti AWS S3 dengan SSE).
2. **Mengedit `terraform.tfstate` Secara Manual**: Mengubah JSON state file secara manual sering merusak checksum dan dependency graph, menyebabkan Terraform gagal membaca state. Gunakan perintah `terraform state mv` atau `terraform state rm`.
3. **Mengabaikan `lifecycle { prevent_destroy = true }`**: Lupa melindungi resource kritis (database, storage bucket) dari penghapusan tidak sengaja.

---

## 16. Best Practices
### Must Have
- Selalu tinjau baris diff pada `terraform plan` sebelum mengeksekusi `terraform apply`.
- Gunakan `lifecycle { prevent_destroy = true }` pada seluruh stateful database dan S3 bucket produksi.
- Selalu kunci versi provider di blok `required_providers` (`version = "~> 5.30"`).

### Recommended
- Jalankan `terraform fmt -check` dan `tflint` di pipeline CI untuk menjaga standarisasi kode.
- Buat tag standar pada setiap resource (`Owner`, `Environment`, `ManagedBy = "Terraform"`).

### Avoid / Overengineering
- Jangan membuat satu file `main.tf` raksasa dengan 3.000 baris kode; pecah menjadi komponen modular (`network.tf`, `security.tf`, `compute.tf`).

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| `Error: Resource already exists` | Resource sudah dibuat manual di Cloud Console dan belum diimpor ke state Terraform | Gunakan perintah `terraform import <resource_type>.<name> <cloud_id>` |
| `Error acquiring the state lock` | Eksekusi apply sebelumnya crash atau ada engineer lain yang sedang menjalankan plan/apply | Periksa siapa yang memegang lock; jika aman, jalankan `terraform force-unlock <LOCK-ID>` |
| `Provider produced inconsistent result` | Atribut yang dikembalikan API cloud berbeda dengan yang diprediksi saat plan | Perbarui versi provider atau tambahkan atribut yang berubah ke `ignore_changes` |

---

## 18. Exercise
1. Tulis konfigurasi HCL untuk membuat resource dummy local file menggunakan provider `hashicorp/local`.
2. Jalankan `terraform init`, `terraform plan`, dan amati isi file `terraform.tfstate` yang terbentuk.

---

## 19. Challenge
Rancang arsitektur simulasi **Terraform State & Execution Plan Engine**:
- Buat parser deklaratif yang membandingkan *Desired Config HCL*, *Current State JSON*, dan *Live Cloud API*.
- Hitung diff matematis: resource mana yang berstatus `CREATE (+)` (ada di HCL, belum ada di Cloud), `MODIFY (~)` (beda atribut), dan `DESTROY (-)` (ada di Cloud/State, dihapus dari HCL).

---

## 20. Summary
- Terraform & OpenTofu mengadopsi pendekatan deklaratif untuk mengotomatiskan provisioning infrastruktur cloud yang reproducible.
- State file adalah *single source of truth* pemetaan resource yang wajib dilindungi dari kebocoran dan konflik race condition.
- Siklus `plan` sebelum `apply` memberikan visibilitas penuh dan keselamatan operasional bagi tim SRE.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m01/terraform_state_engine_sim.js](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-05-Infrastructure-as-Code-Terraform/hands-on/m01/terraform_state_engine_sim.js).
