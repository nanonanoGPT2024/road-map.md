# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 10: State Refactoring, Brownfield Migration, & Custom Provider Development**
**Kategori: 05-DevOps-Cloud-and-SRE**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Engineer/Lead DevOps Architect diharapkan mampu:
- **Menganalisis dan Membedah Internal State Engine**: Memahami struktur data internal Terraform State (Schema v4), mekanisme *state locking*, *lineage tracking*, dan kalkulasi *cryptographic checksum* resource.
- **Mengeksekusi State Refactoring Tingkat Lanjut**: Melakukan restrukturisasi arsitektur Terraform secara deklaratif via `moved` blocks dan imperatif via CLI manipulation tanpa menyebabkan destruksi fisik infrastruktur (*zero downtime, zero-drift*).
- **Mendesain Strategi Brownfield Migration Terukur**: Mengimpor ratusan resource infrastruktur warisan (*unmanaged*) ke dalam declarative IaC menggunakan engine `import` blocks (Terraform 1.5+) dan reverse-engineering framework.
- **Mengarsitekturi State Splitting (Monolith to Micro-States)**: Memecah *monolithic state file* berukuran puluhan megabyte menjadi arsitektur *layered/isolated states* untuk memperkecil *blast radius* dan memangkas durasi CI/CD plan/apply.
- **Mengembangkan Custom Terraform Provider Berbasis Go**: Memahami arsitektur Terraform Plugin Framework, protokol gRPC RPC v6, skema CRUD, dan manajemen *state reconciliation* untuk API privat/internal enterprise.

---

## 2. Prerequisite

Peserta pelatihan wajib memiliki kompetensi prasyarat:
- **Tingkat Mahir HCL2**: Dynamic blocks, structural typing, conditional evaluations, dan fungsi built-in engine Terraform.
- **Pemahaman Cloud Networking & Compute**: VPC, Subnetting, Security Groups, IAM Role assumption, Cloud Storage, dan Managed RDBMS (AWS/GCP/Azure).
- **Penguasaan Linux & CLI Tooling**: Eksekusi perintah Shell/Bash tingkat lanjut, manipulasi JSON via `jq`, dan manajemen Git VCS.
- **Dasar Pemrograman Go (Golang)**: Structs, interfaces, pointers, error handling idiomatik, dan Go Modules (untuk materi Custom Provider).
- **Akses Lingkungan Eksekusi**: Terraform CLI binary >= v1.7.0, Go binary >= v1.21, AWS CLI v2 terkonfigurasi, dan editor teks berkemampuan LSP (VS Code/GoLand).

---

## 3. Concept & Internal Architecture

### 3.1 Anatomi Mendalam State File (Schema v4)
Terraform State bukan sekadar cache, melainkan *single source of truth* relasional yang memetakan deklarasi konfigurasi HCL ke identitas fisik *real-world resource* pada API target.

```json
{
  "version": 4,
  "terraform_version": "1.7.5",
  "serial": 42,
  "lineage": "c8b417ef-3f2d-74d1-8b21-42358891d09e",
  "meta": {
    "hash": "d5f6e8..."
  },
  "resources": [
    {
      "mode": "managed",
      "type": "aws_instance",
      "name": "api_gateway",
      "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
      "instances": [
        {
          "schema_version": 1,
          "attributes": {
            "id": "i-0abcd1234ef567890",
            "ami": "ami-0c55b159cbfafe1f0",
            "instance_type": "c6i.xlarge"
          },
          "private": "eyJlMmJmYjczMC1lY2FhLTExZTYtOGY4OC0zNDM2M2JjN2M0YzAiOnsiY3JlYXRlIjo2MDAwMDAwMDAwMDB9fQ=="
        }
      ]
    }
  ]
}
```

- **`serial`**: Integer monotonik meningkat. Setiap operasi penulisan state yang berhasil menaikkan nilai ini sebesar 1. Mekanisme ini mencegah kondisi *split-brain* dan *concurrency race condition*.
- **`lineage`**: UUID acak v4 yang diinisiasi saat pembuatan state pertama kali. Jika Terraform mendeteksi lineage yang berbeda pada remote backend, proses operasi dibatalkan guna mencegah penimpaan state milik environment/stack lain.
- **`schema_version`**: Versi internal skema resource yang didefinisikan oleh provider. Digunakan oleh fungsi internal provider untuk menjalankan prosedur migrasi skema (*state upgrade*) dari versi API lama ke versi API baru.
- **`private`**: Blob terenkripsi Base64 yang berisi metadata internal provider (misalnya status timeouts, dependencies, atau payload response spesifik yang tidak diekspos ke skema HCL pengguna).

### 3.2 Terraform Plugin Protocol & gRPC Engine
Terraform Core tidak berinteraksi langsung dengan SDK Cloud (misal: AWS SDK for Go). Hubungan antara Terraform Core dan Provider dibangun di atas arsitektur Client-Server multiproses via IPC (Inter-Process Communication) menggunakan **gRPC melalui Unix Domain Sockets** (atau Named Pipes pada platform Windows).

```
+-------------------------------------------------------------+
|                       Terraform Core                        |
|   (Graph Walker, HCL Parser, State Store, DAG Evaluator)    |
+-------------------------------------------------------------+
                             |
         gRPC Protocol (Proto3 / RPC Over IPC)
                             |
+-------------------------------------------------------------+
|               Custom / Community Provider Plugin            |
|       (Terraform Plugin Framework / SDKv2 in Go)            |
|                                                             |
|  - ValidateResourceConfig()                                 |
|  - ReadResource()        <-->  Transform to/from State      |
|  - PlanResourceChange()                                     |
|  - ApplyResourceChange() <-->  Execute External REST/gRPC   |
+-------------------------------------------------------------+
                             |
                   HTTPS / Mutual TLS
                             |
+-------------------------------------------------------------+
|                 Cloud Provider / Enterprise API             |
|              (AWS, GCP, Vault, Internal Custom API)         |
+-------------------------------------------------------------+
```

1. **Discovery & Handshake**: Terraform Core membaca binary provider dari `.terraform/providers/`, mengeksekusi binary sebagai sub-proses terpisah, dan menerima *handshake certificate* serta socket port via `stdout`.
2. **Schema Exchange**: Provider mengirimkan spesifikasi skema tipe data, atribut wajib, opsional, *computed*, dan *sensitive*.
3. **Lifecycle RPC**:
   - `ReadResource`: Menarik data aktual dari remote target, melakukan pemetaan terhadap state lokal.
   - `PlanResourceChange`: Mengkalkulasi mutasi state (Create, Read, Update, Delete) berdasarkan konfigurasi HCL baru versus data hasil `ReadResource`.
   - `ApplyResourceChange`: Melakukan eksekusi pemanggilan REST/gRPC ke cloud endpoint secara definitif dan mengembalikan status objek yang termutasi ke Terraform Core untuk disimpan ke remote backend.

---

## 4. Why & What

### Mengapa State Refactoring Harus Menjadi Prosedur Baku?
Dalam siklus hidup arsitektur enterprise:
1. **Pencegahan Penghancuran Tidak Sengaja (*Accidental Deletion*)**: Mengubah nama resource atau memindahkannya ke dalam module turunan (`child module`) pada Terraform versi lama (<1.1) dianggap sebagai tindakan destruksi objek lama dan pembuatan objek baru (`destroy-then-create`), yang dapat mematikan database atau memutus koneksi jaringan di lingkungan produksi.
2. **Eliminasi Monolithic Blast Radius**: State file yang mengelola ribuan resource menyebabkan `terraform plan` memakan waktu 45-90 menit akibat ribuan API call (*rate-limiting/throttling*). Jika state ini korup, seluruh infrastruktur perusahaan terkunci.
3. **Konsolidasi Infrastruktur Brownfield**: Adopsi cloud sering kali diawali dengan pembuatan manual via Cloud Console (*ClickOps*). Mengimpor aset tersebut secara terstruktur membawa infrastruktur yang tidak terkelola ke dalam pipeline audit, *drift detection*, dan kepatuhan regulasi.

---

## 5. How (Workflow Detail)

### 5.1 Siklus Hidup Refactoring Deklaratif via `moved` Blocks
Mulai Terraform v1.1+, migrasi penamaan atau modularisasi resource diwajibkan menggunakan deklarasi kode, bukan CLI imperatif manual yang rawan *human error*.

```
[ Developer HCL Edit ] 
       |
       v
[ Tambah 'moved' block ] 
       |
       v
[ Execution: terraform plan ] 
       |
       +---> Engine mencocokkan AST: Old Address -> New Address
       +---> Terraform mendeteksi relokasi state tanpa merencanakan mutasi fisik (0 to add, 0 to change, 0 to destroy)
       |
       v
[ Execution: terraform apply ]
       |
       +---> Engine memperbarui address index pada State File (Serial bertambah)
       +---> Remote resource TIDAK tersentuh sama sekali
```

### 5.2 Deklaratif State Import Workflow (Terraform 1.5+)
Menggantikan perintah tradisional imperatif `terraform import` yang tidak menghasilkan deklarasi kode secara otomatis.

1. **Definisikan Blok `import`**: Tentukan alamat target (`to`) dan ID resource cloud yang ada (`id`).
2. **Generasi Konfigurasi**: Jalankan `terraform plan -generate-config-out=generated_resources.tf`.
3. **Review & Hardening**: Sesuaikan variabel, hilangkan atribut default yang tidak perlu, standarisasi tag.
4. **Finalisasi Eksekusi**: Jalankan `terraform apply` untuk merekonsiliasi state tanpa memicu perubahan fisik infrastruktur.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Medis: Rekam Medis (State) vs Pasien Fisik (Infrastructure)

```
[ ID Pasien: MED-99214 ] <========================> [ Pasien Nyata di Rumah Sakit ]
 (Data State: Alamat Kamar, Diagnosa)               (Fisik: Organ, Tubuh, Denyut Nadi)
        |
        |--- DOKTER INGIN PINDAHKAN RUANGAN (Refactoring)
        |
        +-- METODE KELIRU (Hapus HCL lama, tulis HCL baru tanpa refactoring):
        |   Sistem membaca: Pasien Lama Dinyatakan Keluar/Mati (DESTROY) -> Pasien Baru Dibuat (CREATE).
        |   Akibat: Bencana fatal (Downtime/Data Loss).
        |
        +-- METODE BENAR (Gunakan 'moved' block / State Surgery):
            Sistem membaca: Pasien fisik tetap sama, hanya ID registrasi kamar yang diubah pada dokumen.
            Akibat: Pasien tidak mengalami interupsi sama sekali.
```

### Arsitektur Split State (Monolith ke Multi-Layered Isolated State)

```
SEBELUM: Monolithic State (Blast Radius: FATAL, Execution: 55 Menit)
+---------------------------------------------------------------------------------+
|                                 root.tfstate                                    |
|  [VPC] <---> [Subnets] <---> [RDS Database] <---> [EKS Cluster] <---> [Ingress] |
+---------------------------------------------------------------------------------+

SESUDAH: Decoupled Multi-State (Blast Radius: Minimal, Execution: 2-3 Menit)
+----------------------------------+          +----------------------------------+
|      01-networking.tfstate       |          |         02-data.tfstate          |
|  [VPC, Subnets, Transit Gateway] |          |    [RDS Aurora, Redis ElastiCache] |
+----------------------------------+          +----------------------------------+
                 |                                              |
                 +-----------------------+----------------------+
                                         |
                                         v (Cross-State via Data/Remote State/SSM)
                              +----------------------------------+
                              |        03-compute.tfstate        |
                              |   [EKS Node Groups, App ALB]     |
                              +----------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Refactoring Komponen Tunggal ke Sub-Module (`moved` block)

#### Kode Awal (Sebelum Refactoring):
```hcl
# main.tf
resource "aws_security_group" "web_sg" {
  name        = "web-tier-sg"
  description = "Allow inbound HTTP/HTTPS"
  vpc_id      = "vpc-0987654321fedcba0"

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

#### Perubahan Arsitektur:
Developer membuat modul modular `modules/security` dan memindahkan resource ke dalamnya.

```hcl
# main.tf
module "network_security" {
  source = "./modules/security"
  vpc_id = "vpc-0987654321fedcba0"
}

# Declarative Refactoring Address Mapping
moved {
  from = aws_security_group.web_sg
  to   = module.network_security.aws_security_group.this
}
```

```hcl
# modules/security/main.tf
variable "vpc_id" {
  type = string
}

resource "aws_security_group" "this" {
  name        = "web-tier-sg"
  description = "Allow inbound HTTP/HTTPS"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

### 7.2 Practical Example: Deklaratif Import Brownfield AWS CloudFront & S3

Skenario: CloudFront Distribution dan S3 bucket dibuat via Web UI AWS. Kita harus membawanya ke dalam kontrol Terraform v1.5+ secara terstruktur.

```hcl
# imports.tf
import {
  to = module.cdn.aws_s3_bucket.origin_bucket
  id = "enterprise-production-assets-2024"
}

import {
  to = module.cdn.aws_cloudfront_distribution.cdn_distribution
  id = "EDFDVBD632BHDS5"
}
```

Perintah eksekusi untuk auto-generate HCL:
```bash
terraform plan -generate-config-out=modules/cdn/generated_cdn.tf
```

Hasil sanitasi file yang dihasilkan (`modules/cdn/generated_cdn.tf`):
```hcl
# modules/cdn/generated_cdn.tf
resource "aws_s3_bucket" "origin_bucket" {
  bucket        = "enterprise-production-assets-2024"
  force_destroy = false
}

resource "aws_cloudfront_distribution" "cdn_distribution" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"

  origin {
    domain_name = aws_s3_bucket.origin_bucket.bucket_regional_domain_name
    origin_id   = "S3-enterprise-production-assets-2024"
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-enterprise-production-assets-2024"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 86400
    max_ttl                = 31536000
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
```

### 7.3 Practical Example: Custom Provider Implementation Menggunakan Plugin Framework (Golang)

Contoh skeleton provider internal untuk berinteraksi dengan Internal Feature Flag / Custom Configuration API via HTTP REST.

```go
// internal/provider/feature_flag_resource.go
package provider

import (
	"context"
	"fmt"
	"net/http"

	"github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/planmodifier"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/stringplanmodifier"
	"github.com/hashicorp/terraform-plugin-framework/types"
)

var _ resource.Resource = &FeatureFlagResource{}
var _ resource.ResourceWithConfigure = &FeatureFlagResource{}

type FeatureFlagResource struct {
	client *http.Client
}

type FeatureFlagResourceModel struct {
	ID          types.String `tfsdk:"id"`
	Name        types.String `tfsdk:"name"`
	Description types.String `tfsdk:"description"`
	Enabled     types.Bool   `tfsdk:"enabled"`
}

func NewFeatureFlagResource() resource.Resource {
	return &FeatureFlagResource{}
}

func (r *FeatureFlagResource) Metadata(ctx context.Context, req resource.MetadataRequest, resp *resource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_feature_flag"
}

func (r *FeatureFlagResource) Schema(ctx context.Context, req resource.SchemaRequest, resp *resource.SchemaResponse) {
	resp.Schema = schema.Schema{
		Description: "Mengelola status lifecycle internal feature flag enterprise.",
		Attributes: map[string]schema.Attribute{
			"id": schema.StringAttribute{
				Computed:            true,
				Description:         "ID unik dari Feature Flag.",
				PlanModifiers: []planmodifier.String{
					stringplanmodifier.UseStateForUnknown(),
				},
			},
			"name": schema.StringAttribute{
				Required:    true,
				Description: "Nama unik flag yang dapat dibaca manusia.",
			},
			"description": schema.StringAttribute{
				Optional:    true,
				Description: "Penjelasan fungsi fungsional feature flag.",
			},
			"enabled": schema.BoolAttribute{
				Required:    true,
				Description: "Status aktivasi feature flag.",
			},
		},
	}
}

func (r *FeatureFlagResource) Configure(ctx context.Context, req resource.ConfigureRequest, resp *resource.ConfigureResponse) {
	if req.ProviderData == nil {
		return
	}
	client, ok := req.ProviderData.(*http.Client)
	if !ok {
		resp.Diagnostics.AddError(
			"Unexpected Provider Data Type",
			fmt.Sprintf("Expected *http.Client, got: %T.", req.ProviderData),
		)
		return
	}
	r.client = client
}

func (r *FeatureFlagResource) Create(ctx context.Context, req resource.CreateRequest, resp *resource.CreateResponse) {
	var data FeatureFlagResourceModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	// Simulasi panggilan eksternal API Create
	// POST /api/v1/flags -> ID dihasilkan oleh backend API
	data.ID = types.StringValue("flg-" + data.Name.ValueString())

	resp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}

func (r *FeatureFlagResource) Read(ctx context.Context, req resource.ReadRequest, resp *resource.ReadResponse) {
	var data FeatureFlagResourceModel
	resp.Diagnostics.Append(req.State.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	// Panggilan API eksternal GET /api/v1/flags/{id}
	// Jika status 404, hapus dari state via resp.State.RemoveResource(ctx)

	resp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}

func (r *FeatureFlagResource) Update(ctx context.Context, req resource.UpdateRequest, resp *resource.UpdateResponse) {
	var plan FeatureFlagResourceModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &plan)...)
	if resp.Diagnostics.HasError() {
		return
	}

	// Panggilan API eksternal PUT /api/v1/flags/{id}

	resp.Diagnostics.Append(resp.State.Set(ctx, &plan)...)
}

func (r *FeatureFlagResource) Delete(ctx context.Context, req resource.DeleteRequest, resp *resource.DeleteResponse) {
	var data FeatureFlagResourceModel
	resp.Diagnostics.Append(req.State.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	// Panggilan API eksternal DELETE /api/v1/flags/{id}
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario:
Platform FinTech Tier-1 "NusantaraPay" memiliki satu monolithic state file di AWS berukuran **68 MB** (`root.tfstate`) yang mencakup **1.850 resources**. 

### Masalah Akut:
1. `terraform plan` memakan waktu **52 menit** karena harus me-refresh seluruh resource.
2. Setiap deploy berisiko tinggi. Terjadi 2 kali insiden *outage* besar karena kesalahan modifikasi Security Group merusak instance Aurora DB utama.
3. Terjadi *state locking contention* terus-menerus: tim Data Platform, Core Banking, dan SRE saling mengunci execution pipeline di CI/CD.

### Rencana Migrasi (Zero-Downtime State Decomposition):
Pecah monolith state menjadi 3 state terpisah:
1. `01-networking-state` (VPC, Subnets, IGW, NAT GW, DirectConnect)
2. `02-database-state` (Aurora PostgreSQL, DynamoDB, Parameter Groups)
3. `03-apps-compute-state` (EKS, Auto Scaling Groups, Load Balancers)

### Prosedur Bedah State Produksi:
Eksekusi menggunakan kombinasi Remote State Pull, Manipulasi Manual State List, State Splitting, dan State Push dengan verifikasi integritas hash.

```bash
#!/usr/bin/env bash
set -euo pipefail

ENV="production"
MONOLITH_DIR="./monolith-state"
DB_TARGET_DIR="./database-state"

echo "=== LANGKAH 1: ACQUIRE LOCK DAN DOWNLOAD MONOLITH STATE ==="
cd "$MONOLITH_DIR"
terraform init
# Pull state aktual ke file lokal terenkripsi
terraform state pull > /tmp/monolith_prod.json
cp /tmp/monolith_prod.json /tmp/monolith_backup.json

echo "=== LANGKAH 2: EKSTRAKSI RESOURCE DATABASE KE TARGET BARU ==="
cd "../$DB_TARGET_DIR"
terraform init

# Melakukan migrasi resource spesifik antar state file secara aman
# Format: terraform state mv -state=/tmp/monolith_prod.json -state-out=./terraform.tfstate <source> <target>
terraform state mv -state=/tmp/monolith_prod.json -state-out=./target_db.tfstate \
  aws_rds_cluster.aurora_cluster \
  aws_rds_cluster.aurora_cluster

terraform state mv -state=/tmp/monolith_prod.json -state-out=./target_db.tfstate \
  'aws_rds_cluster_instance.cluster_instances["node-1"]' \
  'aws_rds_cluster_instance.cluster_instances["node-1"]'

terraform state mv -state=/tmp/monolith_prod.json -state-out=./target_db.tfstate \
  'aws_rds_cluster_instance.cluster_instances["node-2"]' \
  'aws_rds_cluster_instance.cluster_instances["node-2"]'

echo "=== LANGKAH 3: PUSH STATE KE REMOTE BACKEND TARGET MASING-MASING ==="
# Push state baru database
terraform state push ./target_db.tfstate
rm ./target_db.tfstate

# Push sisa monolith yang sudah berkurang resourcenya kembali ke backend lama
cd "../$MONOLITH_DIR"
terraform state push /tmp/monolith_prod.json

echo "=== LANGKAH 4: VERIFIKASI PERUBAHAN ==="
# Eksekusi plan untuk memastikan TIDAK ADA destruksi fisik
terraform plan -detailed-exitcode || exit_code=$?

if [ ${exit_code} -eq 0 ]; then
  echo "SUKSES: Monolith state terverifikasi sinkron (0 changes)."
elif [ ${exit_code} -eq 2 ]; then
  echo "PERINGATAN: Deteksi plan changes! Periksa declarative address Anda!"
  exit 1
fi
```

### Hasil Pasca Migrasi:
- Waktu eksekusi `terraform plan` pada layer database turun dari **52 menit** menjadi **40 detik**.
- *Blast radius* terkunci secara isolatif via policy IAM AWS S3 backend yang membatasi hak akses Developer hanya pada `03-apps-compute-state`.
- Insiden *state lock contention* tereduksi sebesar 100%.

---

## 9. Trade-offs

| Parameter | Monolithic State File | Decoupled Multi-State (Layered) | Declarative Refactoring (`moved`) | Imperative CLI Surgery (`state mv`) |
| :--- | :--- | :--- | :--- | :--- |
| **Kecepatan Plan/Apply** | Sangat Lambat (O(N) API calls tinggi) | Cepat (Terisolasi per domain layanan) | Netral terhadap kecepatan run | Netral terhadap kecepatan run |
| **Kompleksitas Koordinasi** | Rendah (Semua output dapat direferensi langsung) | Tinggi (Butuh remote state data sources/SSM) | Sangat Terstruktur (Tercatat dalam VCS commit) | Rendah jejak audit (Manual operator action) |
| **Risiko Blast Radius** | **Kritis/Katastropik** (Outage total jika korup) | **Minimal** (Hanya berdampak pada 1 domain) | Rendah (Diverifikasi oleh `terraform plan`) | Sangat Tinggi (Jika salah mengetik identifier) |
| **Maintenance Burden** | Rendah di awal, mustahil dikelola di skala besar | Butuh standardisasi pipeline CI/CD per layer | Blok `moved` harus dibersihkan berkala | Tidak meninggalkan residu kode konfigurasi |
| **Kebutuhan Hak Akses IAM** | Luas (*Broad Permission* untuk seluruh resource) | granular (*Least Privilege* per stack/tim) | Sama dengan eksekusi terraform reguler | Memerlukan izin Write langsung ke State S3 |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Ghost Resources Pasca Refactoring
- **Gejala**: Muncul rencana `aws_instance.worker will be destroyed` dan `module.compute.aws_instance.worker will be created`.
- **Root Cause**: Penulisan blok `moved` salah mereferensikan address index (misal: lupa index array `[0]` atau key map `["primary"]`).
- **Solusi**:
```hcl
# SALAH:
moved {
  from = aws_instance.worker
  to   = module.compute.aws_instance.worker
}

# BENAR (Jika resource awal menggunakan count/for_each):
moved {
  from = aws_instance.worker[0]
  to   = module.compute.aws_instance.worker["0"]
}
```

### 10.2 State Lock Stale Deadlock
- **Gejala**: `Error: Error acquiring the state lock: ConditionalCheckFailedException`.
- **Root Cause**: Proses eksekusi CI/CD terputus tiba-tiba (misal: Pod Runner di-kill OOM) sebelum sempat merilis kunci lock di DynamoDB.
- **Troubleshooting Runbook**:
  1. Pastikan tidak ada worker lain yang sedang aktif berjalan.
  2. Dapatkan `Lock Info: ID: e8e65f32-72c1-d28f-7c49-2e06915b81a7`.
  3. Lepas kunci secara aman:
     ```bash
     terraform force-unlock e8e65f32-72c1-d28f-7c49-2e06915b81a7
     ```

### 10.3 State Lineage/Serial Mismatch Exception
- **Gejala**: `Error: State snapshot was created by a different invocation... serial mismatch`.
- **Root Cause**: Dua anggota tim melakukan operasi `terraform state push` secara paralel atau memulihkan state dari backup yang salah tanpa menaikkan serial.
- **Solusi**: Tarik remote state terbaru, lakukan rekonsiliasi manual serial menggunakan `jq`:
```bash
jq '.serial += 1' local_state.json > reconciled_state.json
terraform state push reconciled_state.json
```

---

## 11. Best Practices (Production Checklist)

- [ ] **State Versioning**: Aktifkan fitur AWS S3 Bucket Versioning dan MFA Delete pada bucket penyimpanan state.
- [ ] **Pre-Surgery Cold Backup**: Selalu buat salinan fisik lokal sebelum melakukan manipulasi state (`terraform state pull > state_backup_$(date +%s).json`).
- [ ] **Immutable Locking**: Pastikan backend state menggunakan locking mekanik absolut (DynamoDB Table dengan Partition Key `LockID`).
- [ ] **Cleanup Declarative Moved Blocks**: Bersihkan blok `moved` setelah kode refactoring tersebut berhasil di-apply di seluruh stage (Dev, Staging, Prod). Pertahankan blok `moved` minimal selama satu siklus rilis penuh.
- [ ] **Strict Blast Radius Boundaries**: Batasi satu state file maksimal mengelola tidak lebih dari **100-150 resource fisik**.
- [ ] **Dry-run CI Validations**: Terapkan rule CI yang menolak merge request apabila mendeteksi aksi `destroy` tanpa approval eksplisit dari Tech Lead saat refactoring berlangsung.
- [ ] **State Encryption at Rest & In-Transit**: Enkripsi bucket state menggunakan Customer Managed Keys (AWS KMS CMK) dan enforce `aws:SecureTransport` (TLS 1.2+).

---

## 12. Hands-on Practice

Target Direktori Latihan: `hands-on/m02/`

### Skenario Praktikum:
Anda memiliki sebuah resource Security Group mandiri. Anda ditugaskan untuk:
1. Memindahkan Security Group tersebut ke dalam sub-module menggunakan `moved` block secara aman.
2. Mengimpor satu resource AWS IAM Role *unmanaged* menggunakan declarative `import` block.

```
hands-on/m02/
├── backend.tf
├── main.tf
├── imports.tf
├── modules/
│   └── networking/
│       ├── main.tf
│       └── outputs.tf
```

### Langkah 1: Setup Lingkungan & Baseline Resource
Buat file `backend.tf`:
```hcl
terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}
```

Buat file `main.tf`:
```hcl
resource "aws_security_group" "legacy_sg" {
  name        = "hands-on-m02-sg"
  description = "Managed manually originally"
  vpc_id      = "vpc-default" # Ganti dengan vpc-id asli di environment sandbox Anda

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }
}
```
Inisialisasi dan deploy baseline:
```bash
terraform init
terraform apply -auto-approve
```

### Langkah 2: Modularisasi Resource Menggunakan `moved` Block
Buat modul di `modules/networking/main.tf`:
```hcl
variable "vpc_id" {
  type = string
}

resource "aws_security_group" "modular_sg" {
  name        = "hands-on-m02-sg"
  description = "Managed manually originally"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }
}

output "sg_id" {
  value = aws_security_group.modular_sg.id
}
```

Modifikasi `main.tf` dengan menghapus deklarasi `aws_security_group.legacy_sg` lama, memanggil modul baru, dan menautkan blok `moved`:
```hcl
module "networking" {
  source = "./modules/networking"
  vpc_id = "vpc-default"
}

moved {
  from = aws_security_group.legacy_sg
  to   = module.networking.aws_security_group.modular_sg
}
```

Jalankan verifikasi plan:
```bash
terraform plan
```
*Pastikan output konsol menampilkan: `1 to move, 0 to add, 0 to change, 0 to destroy`.*
Terapkan perubahan state:
```bash
terraform apply -auto-approve
```

### Langkah 3: Mengimpor Brownfield IAM Role Menggunakan Declarative Import Block
Buat AWS IAM Role manual menggunakan AWS CLI untuk mensimulasikan resource brownfield:
```bash
aws iam create-role \
  --role-name EnterpriseDummyLegacyRole \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
```

Tambahkan deklarasi import pada file baru `imports.tf`:
```hcl
import {
  to = aws_iam_role.imported_role
  id = "EnterpriseDummyLegacyRole"
}
```

Jalankan engine auto-generation:
```bash
terraform plan -generate-config-out=generated_iam.tf
```

Periksa file `generated_iam.tf`. Sesuaikan deklarasi HCL, lalu sinkronkan:
```bash
terraform apply -auto-approve
```
Verifikasi bahwa IAM Role telah resmi masuk ke dalam daftar state:
```bash
terraform state list
```

---

## 13. Exercise

### Level Easy:
Ubahlah resource `aws_s3_bucket.app_data` yang didefinisikan secara flat menjadi sebuah resource di dalam module `module.storage.aws_s3_bucket.this` murni menggunakan perintah CLI `terraform state mv`. Buktikan melalui `terraform plan` bahwa tidak terjadi pergantian fisik resource.

### Level Medium:
Buatlah skrip otomasi Bash yang membaca daftar 20 tag VPC Subnet AWS, lalu secara otomatis membuat file `import.tf` yang berisi pemetaan deklaratif `import { to = ... id = ... }` untuk setiap subnet tersebut, dilanjutkan dengan eksekusi `terraform plan -generate-config-out` yang bersih tanpa error skema.

### Level Hard:
Rancang dan simulasikan migrasi refactoring dari konfigurasi resource yang menggunakan meta-argumen `count` ke `for_each`:
- Resource Awal: `aws_sqs_queue.app_queue[0]`, `aws_sqs_queue.app_queue[1]`
- Target Akhir: `aws_sqs_queue.app_queue["billing"]`, `aws_sqs_queue.app_queue["orders"]`
Gunakan blok deklaratif `moved` berantai (*chained*) untuk mentransformasikan indeks integer menjadi map key berbasis string tanpa memicu penghancuran antrean SQS fisik yang berisi pesan aktif.

---

## 14. Challenge

### Studi Kasus: Konsolidasi Multi-Account Enterprise Pasca Merger

Perusahaan Anda baru saja mengakuisisi entitas startup yang memiliki **400+ aset cloud unmanaged di AWS** (termasuk RDS Multi-AZ, VPC Peering, Route53 Private Zones, dan KMS Keys). 
Tantangan arsitektur yang wajib diselesaikan:

1. **Persyaratan Zero Downtime**: Tidak boleh ada interupsi jaringan atau restrukturisasi database pada layanan production pelanggan selama adopsi IaC berlangsung.
2. **KMS State Encryption Risk**: Beberapa resource EBS volume terenkripsi menggunakan KMS custom key yang belum masuk dalam state.
3. **Kompleksitas State**: Anda dilarang keras membuat satu monolithic state. Anda harus langsung mengimpor aset-aset tersebut ke dalam format terpisah: `network-layer`, `security-layer`, dan `persistence-layer`.
4. **Tugas Anda**:
   - Susun **Engineering Architecture Runbook** tertulis yang merinci urutan dependency import graf (DAG).
   - Tuliskan algoritma/scripting pipeline untuk validasi otomatis parameter konfigurasi (*drift detection engine*) sebelum dan sesudah deklarasi `import` di-apply.
   - Mitigasi skenario jika terjadi *drift* pada properti `computed` yang tidak dapat dimodifikasi (*immutable arguments* seperti KMS Key Rotation Policy atau DB Instance Storage Type).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Konsep Dasar (Basic)
1. **Apa yang terjadi jika Anda memodifikasi isi file `.tfstate` secara manual menggunakan text editor dan menaikkan versinya secara sembarangan?**
   - *Jawaban*: Menyebabkan korupsi state, checksum hash mismatch, rusaknya tracking serial, dan berisiko memicu panic error pada Terraform Core graph walker.
2. **Kapan blok deklaratif `moved` dievaluasi oleh engine Terraform?**
   - *Jawaban*: Dievaluasi pada fase *Syntactic & Graph Construction* sebelum pembentukan *Execution Plan*, memungkinkan Terraform Core menulis ulang rute alamat resource dalam memori state sebelum melakukan refresh ke API cloud.
3. **Apa perbedaan mendasar antara perintah tradisional `terraform import` dengan blok `import` yang diperkenalkan pada Terraform 1.5+?**
   - *Jawaban*: Perintah CLI tradisional hanya menyisipkan objek ke state lokal tanpa memvalidasi atau membuat kode HCL (mengharuskan penulisan HCL manual secara paralel). Blok `import` bersifat deklaratif, terdokumentasi dalam VCS, dan mendukung parameter `-generate-config-out` untuk menghasilkan HCL secara otomatis.
4. **Apa fungsi dari atribut `lineage` pada header skema JSON state Terraform?**
   - *Jawaban*: Berperan sebagai Global Unique Identifier (UUID) yang mengikat state file dengan infrastruktur deployment spesifik, mencegah penimpaan state secara tidak sengaja oleh stack atau project lain.
5. **Bagaimana cara protokol plugin gRPC menghubungkan Terraform Core dengan executable binary Provider?**
   - *Jawaban*: Melalui subprocess IPC via Unix Domain Sockets (atau local named pipes) yang diawali dengan pertukaran magic string handshake untuk otentikasi.

### Bagian 2: Konsep Menengah (Intermediate)
6. **Jika resource memiliki tag yang berbeda antara konfigurasi Terraform HCL dengan cloud aktual saat proses import dijalankan, aksi apa yang akan diajukan oleh `terraform plan`?**
   - *Jawaban*: Terraform akan mengimpor kondisi aktual terlebih dahulu ke state, kemudian execution plan akan menjadwalkan tindakan *in-place update* untuk menyesuaikan tag aktual agar identik dengan yang tertulis di deklarasi HCL.
7. **Mengapa penggunaan `terraform_remote_state` data source kini mulai ditinggalkan dan digantikan dengan integrasi via AWS SSM Parameter Store / HashiCorp Consul?**
   - *Jawaban*: Karena `terraform_remote_state` memerlukan akses baca tingkat state (`read-entire-state-file`) yang mengekspos seluruh data rahasia (*sensitive values*) di seluruh layer, menciptakan *tight-coupling* antar state, dan meningkatkan resiko kegagalan build jika backend remote berpindah.
8. **Jelaskan mekanisme kerja `schema_version` internal pada skema resource Terraform Provider!**
   - *Jawaban*: Menandai versi layout atribut internal resource. Ketika provider di-upgrade dan memiliki perubahan skema non-backward-compatible, provider mengeksekusi fungsi `StateUpgrader` untuk mentransformasikan JSON lama ke struktur yang baru secara transparan sebelum plan dibuat.
9. **Apa konsekuensi teknis jika blok `moved` dibiarkan selamanya di dalam repository produksi?**
   - *Jawaban*: Secara teknis eksekusi tetap aman, namun akan menambah waktu kalkulasi *graph traversal AST parsing* dan mengotori kerapian basis kode (*code hygiene*). Praktik terbaik adalah menghapusnya setelah dipastikan berjalan di semua environment.
10. **Bagaimana cara mendeteksi bahwa remote backend terkunci (*locked*) oleh proses lain yang sudah mati tanpa merusak integritas data?**
    - *Jawaban*: Memeriksa lock creation timestamp pada DynamoDB/Backend metadata, memvalidasi apakah PID atau mesin runner yang tertera masih hidup di sistem monitoring/CI, dan jika terbukti mati, melakukan `terraform force-unlock <LOCK-ID>`.

### Bagian 3: Skenario Kasus Produksi
11. **Skenario A**: Tim Anda memindahkan database RDS Aurora production dari root config ke sebuah module. Operator mengeksekusi apply tanpa blok `moved`. Terraform menampilkan pesan `aws_rds_cluster.aurora will be destroyed`. Operator segera menekan `Ctrl+C`. Namun, state telah memasuki tahap `Apply partially`. Bagaimana langkah darurat untuk memulihkan kontrol state tanpa merusak klaster RDS fisik?
    - *Solusi Penanganan*:
      1. Buka AWS Console untuk mengaktifkan *Deletion Protection* pada klaster Aurora guna mencegah terminasi fisik jika ada apply susulan yang keliru.
      2. Jangan jalankan `terraform destroy` atau `terraform apply`.
      3. Unduh state versi terakhir yang valid dari S3 bucket versioning (`aws s3api get-object --version-id ...`).
      4. Periksa apakah cluster masih tercatat di state atau sudah terhapus (*orphan*).
      5. Jika terhapus dari state tapi fisik masih ada: gunakan deklaratif `import` block untuk mengaitkan kembali klaster fisik ke alamat module yang baru.
      6. Tambahkan blok `moved` atau sesuaikan konfigurasi modul hingga `terraform plan` menghasilkan status bersih: `No changes. Your infrastructure matches the configuration`.

12. **Skenario B**: Perusahaan ingin membangun Custom Provider untuk berinteraksi dengan API internal Kubernetes Admission Controller kustom. API ini bersifat asynchronous (mengembalikan status HTTP 202 Accepted dengan Job ID). Bagaimana implementasi `CreateContext` di Provider Go agar Terraform client tidak *timeout*?
    - *Solusi Penanganan*:
      Di dalam method `Create()` pada Go Plugin Framework:
      1. Kirim HTTP POST request awal untuk memicu job pembuatan. Ambil `Job ID` dari body response HTTP 202.
      2. Implementasikan mekanisme *polling loop* dengan library pembantu (misal: `retry.StateChangeConf` dari Terraform Plugin SDK/Framework).
      3. Lakukan query periodik ke endpoint `/api/v1/jobs/{job_id}` setiap interval beberapa detik.
      4. Hormati konteks timeout yang didefinisikan pengguna via `ctx.Done()` atau konfigurasi `timeouts { create = "30m" }`.
      5. Setelah status job menjadi `COMPLETED`, lakukan pemanggilan API GET untuk mendapatkan detail resource final, lalu petakan atribut ke `resp.State.Set()`.

13. **Skenario C**: Pada saat memecah monolithic state menjadi 2 layer terpisah (`network.tfstate` dan `apps.tfstate`), Anda tidak sengaja memindahkan resource `aws_eip` (Elastic IP) ke kedua state file tersebut (*dual-ownership state*). Apa dampak yang akan terjadi jika kedua state ini dijalankan di pipeline CI/CD yang berbeda, dan bagaimana cara memulihkannya?
    - *Solusi Penanganan*:
      - **Dampak**: Terjadi perebutan kontrol kepemilikan (*split-brain*). State file pertama yang melakukan `apply` atau `destroy` dapat memutus atau mengubah konfigurasi EIP tanpa disadari oleh state file kedua. Jika salah satu state menghapus resource tersebut, state yang lain akan mengalami kegagalan (*drift/crash*) saat refresh.
      - **Pemulihan**:
        1. Tentukan secara arsitektur state mana yang merupakan pemilik sah dari resource EIP (biasanya `network.tfstate`).
        2. Pada state kedua (`apps.tfstate`), hapus referensi EIP murni dari state internal tanpa menyentuh fisik cloud:
           ```bash
           terraform state rm aws_eip.nat_gateway_ip
           ```
        3. Pada `apps.tfstate`, ubah deklarasi yang membutuhkan IP tersebut menjadi skema referensi via `data.aws_eip.nat` atau konsumsi via SSM Parameter / output remote state.
        4. Jalankan `terraform plan` pada kedua root module untuk memastikan hanya ada satu state yang memegang manajemen lifecycle resource tersebut.

---

## 16. Summary

- **State File Integritas Tinggi**: Terraform State bukan artefak pasif, melainkan representasi relasional bervolume dinamis yang dikendalikan oleh protokol sinkronisasi internal monotonik (`serial` dan `lineage`).
- **Refactoring Deklaratif**: Era manipulasi berbahaya menggunakan CLI imperatif `state mv` telah digantikan secara elegan dan aman oleh `moved` blocks (v1.1+) dan `import` blocks (v1.5+), yang memastikan seluruh perubahan struktural terdokumentasi dan ter-review dalam Git VCS.
- **Dekomposisi Arsitektur**: Memecah arsitektur monolithic state file ke dalam *layered micro-states* merupakan langkah wajib bagi enterprise guna mereduksi *blast radius*, mempercepat siklus validasi CI/CD, dan menegakkan prinsip *least privilege* hak akses IAM.
- **Provider Extensibility**: Platform Terraform dibangun di atas arsitektur terdistribusi multiproses RPC via IPC gRPC, memungkinkan organisasi memperluas kemampuan engine orkestrasi ke API privat internal menggunakan Go Plugin Framework tanpa harus mengubah *core engine* Terraform.