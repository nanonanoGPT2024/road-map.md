# Panduan Hands-On: Policy-as-Code & Security Scanning Simulation

Lab praktikum ini mendemonstrasikan bagaimana siklus audit keamanan dan tata kelola *Policy-as-Code* (PaC) dieksekusi terhadap artefak kompilasi Terraform (`tfplan.json`) sebelum infrastruktur dibuat pada penyedia cloud.

---

## 1. Prasyarat Sistem
- Python 3.8+ terpasang pada terminal Anda.
- Terraform CLI v1.6+ (Opsional, jika Anda ingin menghasilkan `tfplan.json` nyata sendiri).

---

## 2. Struktur File Lab
```
hands-on/m01/
├── README.md                       # Petunjuk instruksional praktikum
└── opa_policy_enforcement_sim.py   # Engine simulator OPA & Compliance Checker
```

---

## 3. Langkah 1: Menjalankan Simulator dengan Mock Data Bawaan
Skrip Python telah dilengkapi dengan generator data sintetis (*mock plan*) yang merekayasa situasi di mana developer mengajukan perubahan berbahaya (port SSH 22 terbuka ke publik, S3 bucket tidak terenkripsi, dan format tag yang melanggar aturan korporat).

Jalankan perintah berikut pada terminal Anda:

```bash
cd hands-on/m01
python3 opa_policy_enforcement_sim.py
```

### Hasil yang Diharapkan:
- Terminal akan mencetak laporan komprehensif berisi daftar pelanggaran:
  - `[CRITICAL] SEC-001` (S3 Public Access Block)
  - `[CRITICAL] SEC-002` (Port 22 SSH terbuka ke `0.0.0.0/0`)
  - `[HIGH] GOV-001` (Missing required tags)
  - `[MEDIUM] GOV-001` (Regex email/cost-center tidak valid)
  - `[HIGH] SEC-003` (S3 tidak memiliki enkripsi SSE)
- Skrip mengembalikan status keluar (*Exit Code 1*), yang merepresentasikan mekanisme gerbang kegagalan otomatis pada pipeline CI/CD (GitHub Actions / GitLab CI).

Periksa kode keluar terminal:
```bash
echo $?
# Output harus bernilai: 1
```

---

## 4. Langkah 2: Menguji File Plan Nyata dari Modul Terraform (Opsional)
Jika Anda memiliki instalasi Terraform lokal, Anda dapat menghasilkan file rencana eksekusi asli dan mengevaluasinya dengan simulator ini:

1. Buat file `main.tf` pengujian di direktori sementara:
   ```hcl
   terraform {
     required_providers {
       aws = {
         source  = "hashicorp/aws"
         version = "~> 5.0"
       }
     }
   }

   provider "aws" {
     region                      = "ap-southeast-1"
     skip_credentials_validation = true
     skip_requesting_account_id  = true
   }

   resource "aws_security_group" "web" {
     name = "insecure-web"
     ingress {
       from_port   = 22
       to_port     = 22
       protocol    = "tcp"
       cidr_blocks = ["0.0.0.0/0"]
     }
   }
   ```

2. Jalankan perintah kompilasi plan ke JSON:
   ```bash
   terraform init
   terraform plan -out=myplan.binary
   terraform show -json myplan.binary > myplan.json
   ```

3. Uji file hasil export menggunakan simulator:
   ```bash
   python3 opa_policy_enforcement_sim.py --plan myplan.json
   ```

---

## 5. Eksperimen Remediasi Mandiri
1. Buka file `opa_policy_enforcement_sim.py`.
2. Telusuri fungsi `generate_mock_plan()`.
3. Perbaiki data konfigurasi di dalam dictionary `generate_mock_plan()`:
   - Ubah `0.0.0.0/0` pada port 22 menjadi `10.0.0.0/8`.
   - Ubah `block_public_acls` menjadi `True`.
   - Perbaiki email agar menggunakan domain `@fintech-corp.com`.
   - Perbaiki format CostCenter menjadi `CC-1234`.
4. Jalankan kembali simulator:
   ```bash
   python3 opa_policy_enforcement_sim.py
   ```
5. Pastikan output terminal berubah menjadi:
   ```
   [PASSED] Seluruh guardrails terpenuhi! Tidak ada pelanggaran kebijakan terdeteksi.
   ```
   Dan periksa bahwa exit code bernilai `0`.