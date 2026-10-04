# Hands-On Lab: Multi-Provider Aliasing, Dynamic External IPC & Remote State Simulation

## 1. Ringkasan Lab
Lab ini memberikan pengalaman langsung (*hands-on*) dalam merancang infrastruktur enterprise multi-region dengan data sourcing eksternal. Anda akan:
- Menjalankan IPC (Inter-Process Communication) eksternal berbasis Python yang mematuhi protokol Terraform data source `external`.
- Mengorkestrasi resource multi-region (Singapore `ap-southeast-1` dan Jakarta `ap-southeast-3`) dalam satu root module menggunakan Provider Aliasing.
- Menerapkan *state validation* dan pencegahan konflik *overlapping CIDR* secara deklaratif.

---

## 2. Struktur Direktori Lab
Pastikan susunan file di direktori Anda terlihat seperti berikut:
```text
hands-on/m01/
├── README.md
├── multi_provider_alias_sim.py
├── providers.tf
├── main.tf
└── outputs.tf
```

---

## 3. Persiapan Lingkungan (Prerequisites)
1. **Terraform CLI**: Versi `>= 1.5.0` terpasang di sistem (`terraform version`).
2. **Python 3**: Versi `>= 3.8` terpasang di sistem (`python3 --version`).
3. Berikan izin eksekusi (*executable permission*) pada skrip simulator:
   ```bash
   chmod +x hands-on/m01/multi_provider_alias_sim.py
   ```

---

## 4. Langkah Implementasi Step-by-Step

### Langkah 1: Uji Skrip Python Secara Terisolasi (IPC Protocol Check)
Uji apakah skrip mematuhi protokol stdin/stdout Terraform:
```bash
# Simulasi input query JSON via Stdin
echo '{"environment": "production"}' | python3 hands-on/m01/multi_provider_alias_sim.py
```
**Ekspektasi Output di Terminal**:
- Diagnostic log muncul di `stderr` (ditandai `[EXTERNAL-IPC-SIMULATOR]`).
- Valid flat JSON map string muncul di `stdout`:
  ```json
  {"environment": "production", "primary_region": "ap-southeast-1", "primary_cidr": "10.100.0.0/16", "dr_region": "ap-southeast-3", "dr_cidr": "10.200.0.0/16", "compliance_tier": "tier-1-pci-dss", "status_code": "200", "ipc_signature": "sha256-verified-sim-engine"}
  ```

---

### Langkah 2: Buat File `providers.tf`
Tuliskan konfigurasi provider dengan alias:
```hcl
# hands-on/m01/providers.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3"
    }
  }
}

# Provider Default (Primary - Singapore)
provider "aws" {
  region                      = "ap-southeast-1"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
}

# Provider Alias (Disaster Recovery - Jakarta)
provider "aws" {
  alias                       = "dr"
  region                      = "ap-southeast-3"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
}
```

---

### Langkah 3: Buat File `main.tf`
Implementasikan pembacaan data eksternal dan provisi VPC multi-region:
```hcl
# hands-on/m01/main.tf

# 1. Panggil Skrip External IPC Simulator
data "external" "ipam_matrix" {
  program = ["python3", "${path.module}/multi_provider_alias_sim.py"]

  query = {
    environment = "production"
  }
}

# 2. VPC Primary di Region Singapore (Default Provider)
resource "aws_vpc" "primary_network" {
  cidr_block           = data.external.ipam_matrix.result.primary_cidr
  enable_dns_hostnames = true

  tags = {
    Name           = "vpc-primary-${data.external.ipam_matrix.result.primary_region}"
    Environment    = data.external.ipam_matrix.result.environment
    ComplianceTier = data.external.ipam_matrix.result.compliance_tier
  }

  lifecycle {
    precondition {
      condition     = data.external.ipam_matrix.result.status_code == "200"
      error_message = "IPAM Matrix status code is not healthy."
    }
  }
}

# 3. VPC Disaster Recovery di Region Jakarta (Provider Alias aws.dr)
resource "aws_vpc" "dr_network" {
  provider             = aws.dr
  cidr_block           = data.external.ipam_matrix.result.dr_cidr
  enable_dns_hostnames = true

  tags = {
    Name           = "vpc-dr-${data.external.ipam_matrix.result.dr_region}"
    Environment    = data.external.ipam_matrix.result.environment
    ComplianceTier = data.external.ipam_matrix.result.compliance_tier
  }

  lifecycle {
    precondition {
      condition     = data.external.ipam_matrix.result.primary_cidr != data.external.ipam_matrix.result.dr_cidr
      error_message = "Primary and DR CIDR cannot be identical (Overlapping Hazard)."
    }
  }
}
```

---

### Langkah 4: Buat File `outputs.tf`
Ekskspos metadata hasil provisioning:
```hcl
# hands-on/m01/outputs.tf
output "network_topology_summary" {
  description = "Pemetaan topologi multi-region hasil orkestrasi external data source"
  value = {
    environment     = data.external.ipam_matrix.result.environment
    primary_vpc_arn = aws_vpc.primary_network.arn
    primary_cidr    = aws_vpc.primary_network.cidr_block
    primary_region  = data.external.ipam_matrix.result.primary_region
    dr_vpc_arn      = aws_vpc.dr_network.arn
    dr_cidr         = aws_vpc.dr_network.cidr_block
    dr_region       = data.external.ipam_matrix.result.dr_region
    ipc_signature   = data.external.ipam_matrix.result.ipc_signature
  }
}
```

---

### Langkah 5: Eksekusi dan Verifikasi

1. **Inisialisasi Terraform**:
   ```bash
   cd hands-on/m01
   terraform init
   ```

2. **Jalankan Validasi & Plan**:
   ```bash
   terraform plan
   ```
   *Amati output plan:* Anda akan melihat dua VPC direncanakan untuk dibuat pada dua region berbeda (`ap-southeast-1` dan `ap-southeast-3`), dengan data CIDR yang di-resolve secara dinamis dari eksekusi skrip Python.

3. **Tinjau Diagnostic IPC**:
   Perhatikan pesan diagnostik `[EXTERNAL-IPC-SIMULATOR]` yang tampil di console tanpa merusak schema parsing Terraform plan.

---

## 5. Eksperimen Pengujian Kegagalan (Failure Injection Test)

Untuk membuktikan keandalan *guardrail*:
1. Ubah query pada `main.tf` menjadi environment yang tidak valid:
   ```hcl
   query = {
     environment = "illegal-environment"
   }
   ```
2. Jalankan kembali `terraform plan`.
3. **Hasil Analisis**: Skrip Python akan melakukan exit dengan code 1, dan Terraform akan langsung membatalkan proses kompilasi plan secara fail-fast dengan error pesan yang jelas.

---

## 6. Cleanup
Hapus local state setelah lab selesai:
```bash
rm -rf .terraform .terraform.lock.hcl terraform.tfstate terraform.tfstate.backup
```