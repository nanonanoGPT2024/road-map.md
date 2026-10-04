# Panduan Hands-On Lab Bab 02: HCL2 Deep Dive & Ekspresi Dinamis

---

## 1. Deskripsi Lab
Lab ini bertujuan untuk memberikan pengalaman langsung (*hands-on practice*) dalam mengoperasikan kapabilitas tingkat lanjut dari HCL2 engine pada Terraform. Anda akan memvalidasi tipe data struktural heterogen, memproyeksikan data array multi-dimensi bersarang (*nested hierarchies*) menjadi flat maps menggunakan `flatten` dan `for` expressions, serta menjalankan eksekusi provisioning yang kebal terhadap anomali *index-shifting*.

Pengujian lab ini didesain sepenuhnya mandiri (*self-contained*) menggunakan resource native `terraform_data` (tersedia sejak Terraform v1.4.0+), sehingga Anda tidak memerlukan kredensial akun cloud publik (AWS/GCP/Azure) aktif untuk mengeksekusi materi ini.

---

## 2. Struktur File Lab
```
hands-on/m01/
├── README.md                          # Panduan eksekusi step-by-step
├── dynamic_blocks_hcl_generator.py    # Python engine validator & HCL file generator
├── terraform.tfvars.json              # File input variabel dinamis (digenerate)
└── main.tf                            # Definisi HCL2, Dynamic Expressions, & Validations
```

---

## 3. Langkah-Langkah Eksekusi

### Langkah 1: Verifikasi Prasyarat Lingkungan
Pastikan workstation Anda telah terpasang:
- **Terraform CLI**: Versi `>= 1.5.0`
- **Python**: Versi `3.8+`

Jalankan perintah berikut di terminal:
```bash
terraform version
python3 --version
```

### Langkah 2: Eksekusi Python Generator & Validator
Masuk ke direktori lab dan jalankan script generator Python:
```bash
cd hands-on/m01
python3 dynamic_blocks_hcl_generator.py
```

*Output yang Diharapkan:*
```text
==================================================================
   HCL2 Dynamic Expression Matrix & Automation Lab Generator      
==================================================================
[*] Memulai validasi skema data HCL2 equivalent...
[+] Validasi integritas skema berhasil: Seluruh batasan terpenuhi.
[+] File variable definitions berhasil dibuat: .../terraform.tfvars.json
[+] File konfigurasi Terraform HCL2 berhasil digenerate: .../main.tf

[OK] Lab environment siap dieksekusi.
Silakan ikuti instruksi pada hands-on/m01/README.md.
```

### Langkah 3: Inisialisasi Terraform Environment
Inisialisasi direktori kerja Terraform:
```bash
terraform init
```

*Output yang Diharapkan:*
```text
Terraform initialized in an empty directory!
```

### Langkah 4: Uji Validasi Rencana Eksekusi (Plan)
Jalankan kompilasi plan untuk melihat bagaimana HCL2 engine mengubah konfigurasi bersarang menjadi resource flat secara deterministik:
```bash
terraform plan
```

Perhatikan:
1. Blok `terraform_data.simulated_subnets` menggunakan key string deterministik seperti `"finance#web"` dan `"finance#core-banking"`, bukan integer index numerik (`[0]`, `[1]`).
2. Indented Heredoc `<<-EOF` menghasilkan blok teks audit yang rapi tanpa indentasi berlebih.

### Langkah 5: Eksekusi Provisioning (Apply)
Terapkan konfigurasi ke dalam state lokal:
```bash
terraform apply -auto-approve
```

*Output yang Diharapkan:*
```text
Apply complete! Resources: 6 added, 0 changed, 0 destroyed.

Outputs:

audit_manifest = <<-EOT
    =======================================================
    NETWORK TOPOLOGY PROVISIONING REPORT
    =======================================================
    Total Active Subnets Created : 3
    Subnet Keys                  : finance#core-banking, finance#web, logistics#tracking-api
    Environment Distinct Tags    : production, staging
    =======================================================
EOT
subnets_summary = [
  {
    "cidr" = "10.10.2.0/24"
    "environment" = "production"
    "rule_checksum" = 2
    "tenant_name" = "finance"
    "tier" = "core-banking"
  },
  {
    "cidr" = "10.10.1.0/24"
    "environment" = "production"
    "rule_checksum" = 2
    "tenant_name" = "finance"
    "tier" = "web"
  },
  {
    "cidr" = "10.20.1.0/24"
    "environment" = "staging"
    "rule_checksum" = 2
    "tenant_name" = "logistics"
    "tier" = "tracking-api"
  },
]
```

### Langkah 6: Menguji Custom Validation Failure
Lakukan uji coba pembuktian bahwa blok `validation` bekerja dengan baik. Edit file `terraform.tfvars.json`, lalu ubah environment pada tenant `finance` menjadi `"testing"`:
```json
"environment": "testing"
```

Jalankan perintah:
```bash
terraform plan
```

*Error yang Diharapkan:*
```text
│ Error: Invalid value for variable
│ 
│   on main.tf line 10:
│   10: variable "tenants" {
│ 
│ Environment harus development/staging/production dan format CIDR harus valid.
```
Kembalikan nilai tersebut menjadi `"production"` setelah pengujian selesai.

---

## 4. Pembersihan Sumber Daya (Cleanup)
Setelah menyelesaikan seluruh modul hands-on, bersihkan seluruh resource state lokal yang terbentuk:
```bash
terraform destroy -auto-approve
rm -rf .terraform .terraform.lock.hcl terraform.tfstate terraform.tfstate.backup terraform.tfvars.json
```

---

## 5. Kesimpulan Hands-On
Melalui latihan praktis ini, Anda telah mengonfirmasi bahwa:
1. `flatten()` dikombinasikan dengan `for` expression secara efektif menghilangkan batasan struktur data bertingkat.
2. Penggunaan identifier berbasis `composite_key` pada `for_each` melindungi infrastruktur dari resiko *index-shifting*.
3. Blok `validation` menolak input yang melanggar aturan arsitektur di tingkat perencanaan (`plan`), menghemat waktu dan mencegah rusaknya integritas state infrastruktur cloud.