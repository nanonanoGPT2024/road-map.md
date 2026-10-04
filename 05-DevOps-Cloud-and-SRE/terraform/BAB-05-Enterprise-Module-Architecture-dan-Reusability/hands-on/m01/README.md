# Hands-On Lab: Enterprise Module Architecture & Linter Validation

Selamat datang di Hands-on Lab Bab 05. Dalam lab ini, Anda akan mempraktikkan bagaimana merancang modul Terraform kelas enterprise yang memenuhi kaidah:
1. *Input Validation & Defensive Guardrails*
2. *Output Sensitivity & Encapsulation*
3. *Zero Provider Leakage* di tingkat Child Module
4. Validasi statik otomatis menggunakan skrip audit `enterprise_module_linter.py`

---

## 1. Topologi Direktori Laboratorium
Pastikan Anda memiliki struktur direktori berikut di komputer lokal Anda:

```
hands-on/m01/
├── enterprise_module_linter.py     # Skrip validator arsitektur otomatis
├── README.md                       # File panduan ini
└── sample_module/                  # Modul uji coba yang akan divalidasi
    ├── README.md
    ├── versions.tf
    ├── variables.tf
    ├── main.tf
    └── outputs.tf
```

---

## 2. Langkah Demi Langkah Hands-On

### Langkah 1: Buat Folder Modul Uji Coba
Buka terminal Anda dan navigasikan ke direktori `hands-on/m01`:
```bash
cd hands-on/m01
mkdir -p sample_module
cd sample_module
```

### Langkah 2: Buat File `README.md` pada Modul
Buat file `sample_module/README.md`:
```markdown
# AWS Secure Bucket Child Module

Modul enterprise ini mengabstraksi pembuatan S3 bucket terenkripsi dengan enforced HTTPS dan pembatasan akses privat.
```

### Langkah 3: Buat File `versions.tf`
Buat file `sample_module/versions.tf`:
```hcl
terraform {
  required_version = ">= 1.5.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0.0"
    }
  }
}
```

### Langkah 4: Buat File `variables.tf` dengan Validasi Ketat
Buat file `sample_module/variables.tf`:
```hcl
variable "storage_account_name" {
  type        = string
  description = "Nama akun storage yang wajib diawali dengan prefix 'entcorp' dan menggunakan format lowercase."

  validation {
    condition     = can(regex("^entcorp[a-z0-9]{3,20}$", var.storage_account_name))
    error_message = "Nama storage_account_name harus diawali 'entcorp', hanya alfanumerik huruf kecil, panjang 10-27 karakter."
  }
}

variable "environment" {
  type        = string
  description = "Target deployment environment."

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment yang diizinkan hanya: development, staging, atau production."
  }
}

variable "enable_versioning" {
  type        = bool
  default     = true
  description = "Flag untuk mengaktifkan S3 bucket object versioning."
}
```

### Langkah 5: Buat File `main.tf`
Buat file `sample_module/main.tf`:
```hcl
resource "aws_s3_bucket" "this" {
  bucket = var.storage_account_name

  tags = {
    Environment = var.environment
    ManagedBy   = "EnterpriseTerraform"
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}
```

### Langkah 6: Buat File `outputs.tf` (Menguji Sensitive Exposure)
Buat file `sample_module/outputs.tf`:
```hcl
output "bucket_id" {
  value       = aws_s3_bucket.this.id
  description = "ID bucket S3 yang telah dibuat."
}

output "bucket_arn" {
  value       = aws_s3_bucket.this.arn
  description = "Amazon Resource Name dari bucket S3."
}

# Contoh pengujian output berlabel sensitive
output "db_admin_password" {
  value       = "super-secret-temporary-token"
  description = "Master token sementara untuk bootstrap database."
  sensitive   = true # Coba ubah menjadi false atau hapus baris ini saat pengujian
}
```

---

## 3. Eksekusi Enterprise Linter

Kembali ke folder `hands-on/m01/`:
```bash
cd ..
chmod +x enterprise_module_linter.py
python3 enterprise_module_linter.py sample_module/
```

### Hasil yang Diharapkan:
```text
[*] Menjalankan Enterprise Module Linter pada: .../hands-on/m01/sample_module...

======================================================================
HASIL PEMERIKSAAN KEPATUHAN ARSITEKTUR MODUL:
======================================================================

[OK] SELURUH PEMERIKSAAN LULUS (Modul memenuhi standar arsitektur enterprise).
```

---

## 4. Eksperimen Kegagalan (Chaos Testing Governance)

Untuk melihat bagaimana linter enterprise menangkap pelanggaran arsitektur:
1. **Pelanggaran 1 (Provider Hardcoding)**:
   Tambahkan baris berikut ke dalam `sample_module/main.tf`:
   ```hcl
   provider "aws" {
     region = "us-east-1"
   }
   ```
2. **Pelanggaran 2 (Sensitive Leak)**:
   Buka `sample_module/outputs.tf`, lalu hapus baris `sensitive = true` pada output `db_admin_password`.
3. **Jalankan Kembali Linter**:
   ```bash
   python3 enterprise_module_linter.py sample_module/
   ```
4. **Analisis Output**:
   Linter akan menghentikan proses (*exit code 1*) dan mengeluarkan log kesalahan:
   - `[ENT-MOD-04] Child module dilarang mengonfigurasi blok 'provider'.`
   - `[ENT-MOD-09] Output 'db_admin_password' berpotensi membawa data rahasia tetapi belum diset 'sensitive = true'.`

Perbaiki kembali pelanggaran di atas dan pastikan modul Anda kembali berstatus hijau (*Compliant*).