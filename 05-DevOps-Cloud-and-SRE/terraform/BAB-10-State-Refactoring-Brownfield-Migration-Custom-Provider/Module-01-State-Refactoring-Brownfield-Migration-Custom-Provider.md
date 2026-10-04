# Bab 10: State Refactoring, Brownfield Migration & Custom Provider

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menguasai migrasi infrastruktur *brownfield* (infrastruktur yang telah berjalan di cloud namun belum dikelola oleh Terraform) menggunakan CLI imperatif `terraform import` dan blok deklaratif `import` (Terraform 1.5+).
- Melakukan restrukturisasi kode Terraform secara masif (modulatisasi, pemindahan namespace, konversi `count` ke `for_each`) dengan *zero downtime* dan *zero destruction* menggunakan blok `moved`.
- Membedah dan memecah *monolithic state file* berukuran raksasa menjadi *micro-states* yang terisolasi secara modular untuk memangkas *blast radius* dan latensi eksekusi *plan/apply*.
- Memahami arsitektur internal Terraform Engine dan mekanisme gRPC RPC interface pada sistem plugin.
- Merancang, mengompilasi, dan menguji *Custom Terraform Provider* menggunakan Go dan modern `terraform-plugin-framework` lengkap dengan definisi skema dan handler CRUD (*Create, Read, Update, Delete*).

---

## 2. Prerequisite
Sebelum mempelajari modul ini, Anda wajib memahami:
- Arsitektur Terraform Core dan mekanisme `terraform.tfstate` (Bab 02 & Bab 04).
- Konstruksi Terraform Module, dynamic blocks, dan ekspresi meta-argument (`for_each`, `count`) (Bab 05 & Bab 06).
- Pemahaman mendalam tentang manajemen *state locks*, remote backend (S3/GCS/Consul), dan konkurensi (Bab 07).
- Bahasa pemrograman Go (Golang) tingkat dasar-menengah: *structs*, *interfaces*, *pointers*, *error handling*, serta *goroutine/context*.
- Lingkungan lokal: Terraform CLI v1.5+, Go v1.21+, dan Git.

---

## 3. Concept
Dalam siklus hidup infrastruktur berskala enterprise, Terraform jarang dimulai dari *greenfield* (proyek kosong). Anda akan berhadapan dengan infrastruktur historis (*brownfield*), kebutuhan refaktorisasi arsitektur modul tanpa mematikan layanan produksi, serta kebutuhan mengelola *internal proprietary platform APIs* yang tidak memiliki provider resmi di HashiCorp Registry. 

Tiga pilar utama modul ini adalah:
1. **Brownfield Migration Engine**: Mengikat resource cloud riil ke dalam deklarasi HCL dan state file tanpa memicu re-creation.
2. **State Graph Refactoring**: Memanipulasi *state addressing* via HCL deklaratif (`moved`) sehingga pointer alamat internal state bermutasi secara atomik tanpa merusak resource fisik.
3. **Terraform Plugin Extensibility**: Membangun *binary provider* mandiri berbasis gRPC menggunakan *Terraform Plugin Framework* untuk mengekspos API kustom Anda ke dalam ekosistem Terraform.

---

## 4. Why
Mengapa kapabilitas tingkat lanjut ini mutlak dibutuhkan oleh Principal DevOps & SRE?

1. **Eliminasi Downtime saat Refaktorisasi**: Mengubah nama resource atau memindahkannya ke dalam modul pada Terraform lawas akan mengeksekusi siklus *Destroy and Recreate*. Pada database produksi atau Kubernetes cluster, hal ini merupakan bencana ketersediaan (*availability incident*). Blok `moved` menjamin mutasi hanya terjadi pada metadata state secara zero-downtime.
2. **Mitigasi Blast Radius & State Bloat**: State file tunggal yang mengelola ribuan resource menyebabkan eksekusi `terraform plan` memakan waktu puluhan menit akibat throttling API provider, rentan *lock-timeout*, dan jika korup, melumpuhkan seluruh infrastruktur perusahaan. State splitting membagi sistem menjadi domain otonom (*Network, Identity, Compute, Database*).
3. **Standarisasi Tata Kelola Perusahaan**: Banyak organisasi memiliki API internal (misal: sistem otorisasi kustom, pendaftaran IPAM internal, provisioning tenant multi-datacenter). Menulis *Custom Provider* memungkinkan otomasi sistem internal tersebut menggunakan sintaks HCL yang deklaratif dan seragam.

---

## 5. What (Deep-Dive Teknis Lengkap)

### A. Brownfield Migration: Imperative vs Declarative
Sebelum Terraform 1.5, impor infrastruktur dilakukan secara imperatif melalui CLI:
```bash
terraform import aws_s3_bucket.legacy my-legacy-production-bucket
```
Pendekatan ini memiliki kelemahan fatal: Anda harus menulis blok kode HCL kosong terlebih dahulu, mengimpor ke state, menjalankan `terraform plan`, lalu menyesuaikan konfigurasi HCL secara coba-coba (*trial-and-error*) sampai *plan* menunjukkan status zero-diff.

Terraform 1.5+ memperkenalkan blok deklaratif `import`:
```hcl
import {
  to = aws_s3_bucket.legacy
  id = "my-legacy-production-bucket"
}
```
Fitur ini terintegrasi penuh ke dalam siklus *planning*. Terraform bahkan dapat men-generate konfigurasi HCL otomatis menggunakan flag:
```bash
terraform plan -generate-config-out=generated_resources.tf
```

### B. State Refactoring dengan Blok `moved`
State address pada Terraform mencerminkan hierarki resource:
`module.<module_name>.<resource_type>.<resource_name>[<index>]`

Ketika Anda memindahkan kode:
- Dari root ke modul: `aws_instance.web` -> `module.compute.aws_instance.web`
- Dari `count` ke `for_each`: `aws_instance.web[0]` -> `aws_instance.web["primary"]`
- Rename resource: `aws_security_group.old_name` -> `aws_security_group.new_name`

Blok `moved` menginstruksikan Terraform Core selama fase *Graph Building*:
```hcl
moved {
  from = aws_instance.web
  to   = module.compute.aws_instance.web
}
```
Saat `terraform plan` dijalankan, Terraform membaca blok ini, memperbarui pointer index di state file sebelum mengevaluasi diff cloud API. Hasilnya: `0 to add, 0 to change, 0 to destroy`.

### C. State Splitting Architecture
Memecah monolithic state file membutuhkan manipulasi state terisolasi:
1. Memeriksa daftar state: `terraform state list`
2. Menggunakan `terraform state mv` dengan flags `-state` dan `-state-out` (lokal) atau menarik state via `terraform state pull`, memodifikasi via tooling, dan mengunggah kembali via `terraform state push`.
3. Mengisolasi *dependency graph* antar-state baru menggunakan output variables dan `terraform_remote_state` data source atau SSM Parameter Store / Terraform Cloud Run Triggers.

### D. Custom Provider Architecture via Go
Terraform Provider berkomunikasi dengan Terraform Core via Unix Domain Socket atau Named Pipes melalui protokol gRPC berkecepatan tinggi.

```
+-------------------------------------------------------------+
|                       Terraform Core                        |
+-------------------------------------------------------------+
                              |
                              | gRPC over IPC / Localhost
                              v
+-------------------------------------------------------------+
|                  Custom Terraform Provider                  |
|  (github.com/hashicorp/terraform-plugin-framework)          |
|                                                             |
|  +--------------------+             +--------------------+  |
|  |   Provider Schema  |             |  Resource / Model  |  |
|  +--------------------+             +--------------------+  |
|  | Configure()        |             | Schema()           |  |
|  +--------------------+             | Create()           |  |
|                                     | Read()             |  |
|                                     | Update()           |  |
|                                     | Delete()           |  |
|                                     +--------------------+  |
+-------------------------------------------------------------+
                              |
                              | REST / SDK Network Calls
                              v
+-------------------------------------------------------------+
|                Target Custom API / Service                  |
+-------------------------------------------------------------+
```

Komponen utama `terraform-plugin-framework`:
1. `provider.Provider`: Antarmuka (*interface*) utama yang mendefinisikan konfigurasi provider (misal: API endpoint, API tokens).
2. `resource.Resource`: Antarmuka untuk resource mandiri yang mengelola siklus hidup CRUD.
3. `datasource.DataSource`: Komponen *read-only* untuk query data.
4. Schema Types: Tipe sistem Terraform seperti `types.String`, `types.Int64`, `types.Bool`, `types.List`, `types.Map`.

---

## 6. How
Prosedur operasional eksekusi:

### 1. Refaktorisasi Deklaratif Menggunakan `moved`
- Identifikasi blok kode yang akan dipindahkan ke modul baru.
- Buat file `migrations.tf` di root folder.
- Tambahkan blok `moved` yang memetakan alamat asal (`from`) ke alamat tujuan (`to`).
- Jalankan `terraform plan` untuk memastikan tidak ada resource yang dijadwalkan untuk dihapus atau dibuat ulang.
- Terapkan dengan `terraform apply`.

### 2. Brownfield Import Deklaratif
- Tulis blok `import` pada file `imports.tf`.
- Jalankan `terraform plan -generate-config-out=generated.tf`.
- Tinjau file `generated.tf`, hapus atribut read-only/komputasi internal cloud yang tidak diperlukan.
- Jalankan `terraform apply` untuk mendaftarkan state secara permanen.

### 3. Pembuatan Custom Provider
- Definisikan modul Go: `go mod init terraform-provider-mycorp`.
- Implementasikan `provider.go` yang mengimplementasikan `provider.Provider`.
- Implementasikan model dan resource CRUD pada `internal/provider/resource_*.go`.
- Jalankan unit & acceptance test.
- Konfigurasikan `.terraformrc` lokal menggunakan blok `development_overrides` untuk memetakan binary Go lokal langsung ke Terraform CLI saat testing.

---

## 7. Analogy
Bayangkan Anda memiliki sebuah apartemen bertingkat (Resource Cloud). 

- **Legacy Imperative Import**: Anda memindahkan perabot apartemen ke dalam pembukuan resmi dengan menulis formulir manual di kantor manajemen satu per satu tanpa ada salinan rancang bangun.
- **Declarative Import**: Anda memasang denah resmi di ruang tamu, menuliskan nomor sertifikat apartemen, dan juru taksir gedung datang menyesuaikan dokumen kepemilikan Anda secara otomatis.
- **Moved Block**: Anda merenovasi pembagian kamar dan mengganti nomor pintu dari "Kamar 01" menjadi "Suite Barat". Anda menempelkan papan nama transisi di pintu. Tukang pos (Terraform Core) tidak akan membuang dan membangun ulang kamar Anda; mereka hanya memperbarui catatan buku alamat logistik.
- **Custom Provider**: Anda mendesain perangkat elektronik cerdas sendiri di rumah yang tidak didukung oleh remote control universal standar. Anda membuat mikrokontroler adaptor khusus (Custom Provider) yang menerjemahkan bahasa remote universal (Terraform HCL) ke sinyal sirkuit proprietary Anda.

---

## 8. Diagram (ASCII)

### State Refactoring Flow (Moved Block Engine)
```
[ HCL Code Modified ]                  [ terraform.tfstate ]
aws_instance.app -> module.app.aws_instance.this
         |                                      |
         v                                      v
  [ Read moved {} ]                     [ Old State Graph ]
  from = aws_instance.app               Address: aws_instance.app
  to   = module.app.aws_instance.this   ID: i-0abc123def456
         |                                      |
         +------------------+-------------------+
                            |
                            v
               [ Terraform Core Evaluator ]
             Mutate State Address Pointer
                            |
                            v
             [ In-Memory Updated State Graph ]
             Address: module.app.aws_instance.this
             ID: i-0abc123def456
                            |
                            v
               [ Cloud Provider Refresh ]
             Check: Does i-0abc123def456 exist? -> YES
                            |
                            v
              PLAN: 0 to add, 0 to change, 0 to destroy.
```

---

## 9. Simple Example

### Contoh 1: Blok Deklaratif `import` dan `moved` (Terraform 1.5+)

#### File: `imports.tf`
```hcl
# Mengimpor VPC brownfield yang dibuat manual di AWS Web Console
import {
  to = aws_vpc.brownfield
  id = "vpc-0a1b2c3d4e5f67890"
}

resource "aws_vpc" "brownfield" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "migrated-production-vpc"
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}
```

#### File: `refactor.tf`
```hcl
# Mengubah resource mandiri menjadi resource di dalam modul tanpa downtime
moved {
  from = aws_vpc.brownfield
  to   = module.network.aws_vpc.this
}
```

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Kode Hands-on)

### A. Large State Splitting Prosedur Produksi
Misal kita memiliki file monolithic state `terraform.tfstate` yang berisi Network dan RDS Database:

```bash
# 1. Pull state terbaru dari backend remote
terraform state pull > monolithic.tfstate

# 2. Periksa resource yang ingin diekstrak ke state database
terraform state list | grep aws_db_instance
# Output:
# aws_db_instance.postgres_master
# aws_db_subnet_group.postgres_subnet

# 3. Buat direktori project baru untuk database
mkdir -p ../rds-microstate && cd ../rds-microstate

# 4. Inisialisasi konfigurasi backend baru untuk micro-state
# (Menyiapkan remote backend S3 rds-microstate/terraform.tfstate)
terraform init

# 5. Lakukan migrasi state addressing antar file state
terraform state mv \
  -state=../monolithic/monolithic.tfstate \
  -state-out=./rds.tfstate \
  aws_db_instance.postgres_master aws_db_instance.postgres_master

terraform state mv \
  -state=../monolithic/monolithic.tfstate \
  -state-out=./rds.tfstate \
  aws_db_subnet_group.postgres_subnet aws_db_subnet_group.postgres_subnet

# 6. Push state ke remote backend masing-masing
terraform state push rds.tfstate
cd ../monolithic && terraform state push monolithic.tfstate
```

---

### B. Membangun Custom Provider Lengkap Menggunakan Go

Berikut implementasi penuh Custom Provider untuk API internal kustom yang mengelola resource bernama `mycorp_application`.

#### File: `main.go`
```go
package main

import (
	"context"
	"flag"
	"log"

	"github.com/hashicorp/terraform-plugin-framework/providerserver"
	"terraform-provider-mycorp/internal/provider"
)

var (
	version string = "1.0.0"
)

func main() {
	var debug bool

	flag.BoolVar(&debug, "debug", false, "set to true to run the provider with support for debuggers")
	flag.Parse()

	opts := providerserver.ServeOpts{
		Address: "registry.terraform.io/mycorp/mycorp",
		Debug:   debug,
	}

	err := providerserver.Serve(context.Background(), provider.New(version), opts)
	if err != nil {
		log.Fatal(err.Error())
	}
}
```

#### File: `internal/provider/provider.go`
```go
package provider

import (
	"context"
	"os"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	"github.com/hashicorp/terraform-plugin-framework/provider"
	"github.com/hashicorp/terraform-plugin-framework/provider/schema"
	"github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/types"
)

var _ provider.Provider = &MyCorpProvider{}

type MyCorpProvider struct {
	version string
}

type MyCorpProviderModel struct {
	Endpoint types.String `tfsdk:"endpoint"`
	Token    types.String `tfsdk:"token"`
}

func New(version string) func() provider.Provider {
	return func() provider.Provider {
		return &MyCorpProvider{
			version: version,
		}
	}
}

func (p *MyCorpProvider) Metadata(ctx context.Context, req provider.MetadataRequest, resp *provider.MetadataResponse) {
	resp.TypeName = "mycorp"
	resp.Version = p.version
}

func (p *MyCorpProvider) Schema(ctx context.Context, req provider.SchemaRequest, resp *provider.SchemaResponse) {
	resp.Schema = schema.Schema{
		Description: "Provider untuk integrasi kontrol internal platform MyCorp.",
		Attributes: map[string]schema.Attribute{
			"endpoint": schema.StringAttribute{
				Description: "API URL untuk manajemen platform MyCorp.",
				Optional:    true,
			},
			"token": schema.StringAttribute{
				Description: "API Token otentikasi. Dapat dibaca dari env MYCORP_TOKEN.",
				Optional:    true,
				Sensitive:   true,
			},
		},
	}
}

func (p *MyCorpProvider) Configure(ctx context.Context, req provider.ConfigureRequest, resp *provider.ConfigureResponse) {
	var config MyCorpProviderModel
	diags := req.Config.Get(ctx, &config)
	resp.Diagnostics.Append(diags...)
	if resp.Diagnostics.HasError() {
		return
	}

	endpoint := os.Getenv("MYCORP_ENDPOINT")
	if !config.Endpoint.IsNull() {
		endpoint = config.Endpoint.ValueString()
	}

	token := os.Getenv("MYCORP_TOKEN")
	if !config.Token.IsNull() {
		token = config.Token.ValueString()
	}

	if endpoint == "" {
		endpoint = "https://api.internal.mycorp.net/v1"
	}

	client := NewClient(endpoint, token)
	resp.DataSourceData = client
	resp.ResourceData = client
}

func (p *MyCorpProvider) Resources(ctx context.Context) []func() resource.Resource {
	return []func() resource.Resource{
		NewApplicationResource,
	}
}

func (p *MyCorpProvider) DataSources(ctx context.Context) []func() datasource.DataSource {
	return []func() datasource.DataSource{}
}
```

#### File: `internal/provider/client.go`
```go
package provider

import (
	"fmt"
	"sync"
)

// In-Memory Client untuk simulasi downstream REST API
type APIClient struct {
	Endpoint string
	Token    string
	mu       sync.Mutex
	store    map[string]ApplicationPayload
}

type ApplicationPayload struct {
	ID          string
	Name        string
	Environment string
	Port        int64
}

func NewClient(endpoint, token string) *APIClient {
	return &APIClient{
		Endpoint: endpoint,
		Token:    token,
		store:    make(map[string]ApplicationPayload),
	}
}

func (c *APIClient) CreateApp(app ApplicationPayload) (*ApplicationPayload, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if _, exists := c.store[app.ID]; exists {
		return nil, fmt.Errorf("aplikasi dengan ID %s sudah terdaftar", app.ID)
	}
	c.store[app.ID] = app
	return &app, nil
}

func (c *APIClient) GetApp(id string) (*ApplicationPayload, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	app, exists := c.store[id]
	if !exists {
		return nil, fmt.Errorf("aplikasi tidak ditemukan")
	}
	return &app, nil
}

func (c *APIClient) UpdateApp(app ApplicationPayload) (*ApplicationPayload, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if _, exists := c.store[app.ID]; !exists {
		return nil, fmt.Errorf("aplikasi tidak ditemukan untuk diupdate")
	}
	c.store[app.ID] = app
	return &app, nil
}

func (c *APIClient) DeleteApp(id string) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.store, id)
	return nil
}
```

#### File: `internal/provider/resource_application.go`
```go
package provider

import (
	"context"
	"fmt"

	"github.com/hashicorp/terraform-plugin-framework/path"
	"github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/planmodifier"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/stringplanmodifier"
	"github.com/hashicorp/terraform-plugin-framework/types"
)

var _ resource.Resource = &ApplicationResource{}
var _ resource.ResourceWithConfigure = &ApplicationResource{}

type ApplicationResource struct {
	client *APIClient
}

type ApplicationResourceModel struct {
	ID          types.String `tfsdk:"id"`
	Name        types.String `tfsdk:"name"`
	Environment types.String `tfsdk:"environment"`
	Port        types.Int64  `tfsdk:"port"`
}

func NewApplicationResource() resource.Resource {
	return &ApplicationResource{}
}

func (r *ApplicationResource) Metadata(ctx context.Context, req resource.MetadataRequest, resp *resource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_application"
}

func (r *ApplicationResource) Schema(ctx context.Context, req resource.SchemaRequest, resp *resource.SchemaResponse) {
	resp.Schema = schema.Schema{
		Description: "Mengelola resource pendaftaran aplikasi internal di MyCorp Platform.",
		Attributes: map[string]schema.Attribute{
			"id": schema.StringAttribute{
				Computed:    true,
				Description: "Identifier unik internal aplikasi.",
				PlanModifiers: []planmodifier.String{
					stringplanmodifier.UseStateForUnknown(),
				},
			},
			"name": schema.StringAttribute{
				Required:    true,
				Description: "Nama layanan aplikasi microservice.",
			},
			"environment": schema.StringAttribute{
				Required:    true,
				Description: "Target environment (misal: staging, production).",
			},
			"port": schema.Int64Attribute{
				Required:    true,
				Description: "Port listening untuk traffic ingress.",
			},
		},
	}
}

func (r *ApplicationResource) Configure(ctx context.Context, req resource.ConfigureRequest, resp *resource.ConfigureResponse) {
	if req.ProviderData == nil {
		return
	}
	client, ok := req.ProviderData.(*APIClient)
	if !ok {
		resp.Diagnostics.AddError(
			"Unexpected Data Source Configure Type",
			fmt.Sprintf("Diharapkan *APIClient, didapatkan: %T", req.ProviderData),
		)
		return
	}
	r.client = client
}

func (r *ApplicationResource) Create(ctx context.Context, req resource.CreateRequest, resp *resource.CreateResponse) {
	var plan ApplicationResourceModel
	diags := req.Plan.Get(ctx, &plan)
	resp.Diagnostics.Append(diags...)
	if resp.Diagnostics.HasError() {
		return
	}

	appID := fmt.Sprintf("app-%s-%s", plan.Environment.ValueString(), plan.Name.ValueString())
	payload := ApplicationPayload{
		ID:          appID,
		Name:        plan.Name.ValueString(),
		Environment: plan.Environment.ValueString(),
		Port:        plan.Port.ValueInt64(),
	}

	created, err := r.client.CreateApp(payload)
	if err != nil {
		resp.Diagnostics.AddError("Gagal Membuat Resource Application", err.Error())
		return
	}

	plan.ID = types.StringValue(created.ID)
	diags = resp.State.Set(ctx, plan)
	resp.Diagnostics.Append(diags...)
}

func (r *ApplicationResource) Read(ctx context.Context, req resource.ReadRequest, resp *resource.ReadResponse) {
	var state ApplicationResourceModel
	diags := req.State.Get(ctx, &state)
	resp.Diagnostics.Append(diags...)
	if resp.Diagnostics.HasError() {
		return
	}

	app, err := r.client.GetApp(state.ID.ValueString())
	if err != nil {
		resp.State.RemoveResource(ctx)
		return
	}

	state.Name = types.StringValue(app.Name)
	state.Environment = types.StringValue(app.Environment)
	state.Port = types.Int64Value(app.Port)

	diags = resp.State.Set(ctx, &state)
	resp.Diagnostics.Append(diags...)
}

func (r *ApplicationResource) Update(ctx context.Context, req resource.UpdateRequest, resp *resource.UpdateResponse) {
	var plan ApplicationResourceModel
	diags := req.Plan.Get(ctx, &plan)
	resp.Diagnostics.Append(diags...)
	if resp.Diagnostics.HasError() {
		return
	}

	payload := ApplicationPayload{
		ID:          plan.ID.ValueString(),
		Name:        plan.Name.ValueString(),
		Environment: plan.Environment.ValueString(),
		Port:        plan.Port.ValueInt64(),
	}

	_, err := r.client.UpdateApp(payload)
	if err != nil {
		resp.Diagnostics.AddError("Gagal Mengupdate Application", err.Error())
		return
	}

	diags = resp.State.Set(ctx, plan)
	resp.Diagnostics.Append(diags...)
}

func (r *ApplicationResource) Delete(ctx context.Context, req resource.DeleteRequest, resp *resource.DeleteResponse) {
	var state ApplicationResourceModel
	diags := req.State.Get(ctx, &state)
	resp.Diagnostics.Append(diags...)
	if resp.Diagnostics.HasError() {
		return
	}

	err := r.client.DeleteApp(state.ID.ValueString())
	if err != nil {
		resp.Diagnostics.AddError("Gagal Menghapus Application", err.Error())
		return
	}
}
```

---

## 11. Real World Example

### Skenario Nyata: Migrasi E-Commerce Core & VPC Monolith Refactoring
Sebuah perusahaan Unicorn Fintech memiliki arsitektur awal di AWS di mana VPC, EKS Cluster, dan 14 database PostgreSQL RDS dideklarasikan dalam satu file `main.tf` raksasa dengan state tunggal sebesar 18 MB.

Setiap kali tim aplikasi ingin mengubah satu ingress rule, `terraform plan` memakan waktu 22 menit karena Terraform harus me-refresh ratusan subnet, NAT gateways, route tables, dan RDS metadata.

**Solusi Arsitektur SRE:**
1. **Pemisahan Domain State**: Memecah monolith menjadi 3 workspace terisolasi: `foundation-network`, `platform-k8s`, dan `database-storage`.
2. **Eksekusi Zero-Downtime State Partitioning**: Menggunakan `terraform state mv` untuk memindahkan resource keluar ke state modular masing-masing tanpa merusak instance RDS yang sedang melayani transaksi miliaran rupiah per detik.
3. **Modulatisasi via `moved`**: Mengorganisir kode jaringan flat menjadi modul `terraform-aws-modules/vpc/aws` dengan deklarasi:
```hcl
moved {
  from = aws_subnet.public_subnet_1
  to   = module.vpc.aws_subnet.public[0]
}

moved {
  from = aws_nat_gateway.nat_gw
  to   = module.vpc.aws_nat_gateway.this[0]
}
```
Hasil: Waktu eksekusi `terraform plan` anjlok dari 22 menit menjadi 14 detik. Tidak ada satu pun paket jaringan yang terputus (*zero downtime*).

---

## 12. Trade-offs

| Pendekatan | Keuntungan | Kerugian / Biaya Kompensasi |
| :--- | :--- | :--- |
| **Monolithic State** | Sangat mudah mereferensikan variabel langsung antar-resource (`aws_vpc.main.id`). | *Blast radius* sangat besar. Latensi API refresh tinggi. Risiko State Lock contention tinggi. |
| **Micro-States (Splitting)** | Isolasi kegagalan sempurna. Kecepatan eksekusi tinggi. RBAC granular per tim. | Butuh data sharing contract (`terraform_remote_state` atau SSM Store). Setup CI/CD pipeline lebih kompleks. |
| **CLI `terraform import`** | Cepat untuk satu atau dua resource sederhana. | Rawan *human-error*. Atribut HCL harus dikarang manual sampai zero-diff tercapai. |
| **Declarative `import {}`** | Terintegrasi di Plan/Apply pipeline. Kode HCL dapat di-generate otomatis oleh Terraform CLI. | Sintaks baru memerlukan Terraform versi 1.5+. |
| **Custom Provider (Golang)** | Kontrol mutlak atas API internal. HCL standar bagi seluruh developer internal. | Beban maintenance binary Go, rilis versi, kompatibilitas gRPC, dan testing overhead. |

---

## 13. When To Use
- Gunakan blok `moved` saat:
  - Melakukan refaktorisasi arsitektur kode (misal: ekstraksi ke reusable module).
  - Mengubah penamaan resource agar sesuai *naming convention*.
  - Mengubah implementasi resource dari `count` menjadi `for_each` atau sebaliknya.
- Gunakan blok `import` saat:
  - Memasukkan infrastruktur lama (*legacy*) atau infrastruktur yang dibuat via UI Console ke dalam Terraform.
  - Membutuhkan peninjauan PR (*Pull Request*) atas proses impor sebelum dieksekusi ke state.
- Gunakan *Custom Provider* saat:
  - Organisasi Anda memiliki REST/gRPC internal platform yang harus di-provisioning bersamaan dengan infrastruktur cloud public.

---

## 14. When NOT To Use
- **Jangan gunakan state refactoring** di environment produksi tanpa menguji skrip mutasi dan blok `moved` di *staging environment* terlebih dahulu.
- **Jangan gunakan Custom Provider** jika integrasi API tersebut cukup dieksekusi satu kali menggunakan blok `null_resource` atau `terraform-provider-http` untuk *payload call* ringan yang tidak membutuhkan siklus CRUD lengkap.
- **Jangan memecah state terlalu granular (Nano-states)**: Memisahkan 1 resource EC2 ke dalam state tersendiri akan menimbulkan overhead orkestrasi CI/CD yang berlebihan.

---

## 15. Common Mistakes
1. **Menghapus blok `moved` terlalu cepat**: Menghapus blok `moved` tepat setelah merge akan merusak *workspace* rekan tim lain atau pipeline CI/CD yang belum sempat menjalankan `apply`. Blok `moved` harus dipertahankan minimal selama 2-3 siklus rilis.
2. **Salah konfigurasi ID pada blok `import`**: Memasukkan ARN pada provider yang mengharapkan ID mentah (atau sebaliknya), menyebabkan error gRPC parsing dari cloud provider.
3. **Mengabaikan Drift pada Brownfield Import**: Mengimpor resource tanpa memeriksa *drift* konfigurasi asli, mengakibatkan nilai default provider menimpa konfigurasi live yang kritikal.
4. **State Desynchronization saat State Splitting**: Melakukan `state mv` tanpa mengunci akses (*state lock*) remote backend asli, berpotensi memicu race condition jika developer lain menjalankan `apply`.

---

## 16. Best Practices
1. **Lakukan Dry-Run dengan Plan**: Verifikasi selalu output CLI. Jika muncul indikator `destroy`, refaktorisasi Anda salah. Indikator harus bernilai `0 to add, 0 to change, 0 to destroy` atau perubahan metadata murni.
2. **Gunakan Branch Protection untuk File State**: Ambil salinan cadangan (*backup snapshot*) state file lokal secara offline sebelum mengeksekusi operasi `terraform state mv` atau `terraform state rm`.
3. **Simpan Blok `moved` di File Terdedikasi**: Letakkan seluruh riwayat migrasi pada file `migrations.tf` agar arsitektur kode utama tetap bersih dan mudah diaudit.
4. **Terapkan Semantic Versioning pada Custom Provider**: Saat mendistribusikan custom provider, patuhi semver untuk mencegah *breaking schema changes* merusak deklarasi state pengguna.

---

## 17. Troubleshooting

### Kasus 1: Warning/Error Cycle Detected pada Moved Block
- **Gejala**: Terraform melempar error `Cycle: module.a.aws_instance.x, module.b.aws_instance.y` saat mengevaluasi blok `moved`.
- **Akar Masalah**: Terdapat dependensi sirkular antara modul asal dan modul tujuan yang belum tuntas di-resolve pada dependency graph.
- **Solusi**: Pisahkan mutasi state menjadi 2 fase: rename resource terlebih dahulu, lalu isolasi modul pada tahap berikutnya.

### Kasus 2: Duplicate Resource State Pasca-Import
- **Gejala**: `Resource already managed by Terraform in state`.
- **Akar Masalah**: Resource sudah tercatat di state dengan address berbeda, namun blok `import` mencoba mengimpor ID cloud yang sama ke address baru.
- **Solusi**: Gunakan blok `moved` jika tujuannya memindahkan address, bukan blok `import`.

### Kasus 3: Provider Schema Drift Diagnostic Error pada Custom Provider
- **Gejala**: `Attribute value type does not match schema type`.
- **Akar Masalah**: Implementasi Go mengembalikan `types.StringNull()` padahal atribut skema didefinisikan sebagai `Required: true`.
- **Solusi**: Validasi payload di method `Create()` dan `Read()` sebelum memanggil `resp.State.Set(ctx, &state)`.

---

## 18. Exercise
1. Tulis sebuah file HCL yang memiliki sebuah resource `aws_security_group.legacy_sg`.
2. Tulis deklarasi blok `moved` untuk memindahkan security group tersebut ke dalam address `module.security.aws_security_group.web`.
3. Simulasikan skenario konversi sebuah resource yang menggunakan `count = 2` menjadi `for_each` menggunakan blok `moved` tanpa destruksi resource.

---

## 19. Challenge
Rancang arsitektur migrasi penuh untuk skenario brownfield enterprise:
Sebuah subnet dan route table dibuat secara manual melalui AWS Web Console. 
1. Tulis blok deklaratif `import` untuk mendaftarkan subnet tersebut ke address `aws_subnet.dmz`.
2. Refaktor subnet tersebut langsung ke dalam modul `module.networking.aws_subnet.subnets["dmz"]` menggunakan kombinasi blok `import` dan `moved`.
3. Pastikan eksekusi `terraform plan` menghasilkan status valid tanpa menghancurkan subnet fisik tersebut.

---

## 20. Summary
- Blok `import` (Terraform 1.5+) mengubah paradigma adopsi *brownfield* dari pendekatan imperatif CLI yang rentan error menjadi proses deklaratif yang aman, terencana, dan dapat diverifikasi via CI/CD.
- Blok `moved` menyelesaikan masalah *lifecycle re-creation* dengan memberikan instruksi penataan ulang graph address secara internal tanpa intervensi fisik terhadap infrastruktur cloud.
- Pemecahan *monolithic state* adalah teknik esensial SRE untuk membatasi *blast radius*, mengurangi latency execution, dan membagi kepemilikan infrastruktur per domain tim.
- Pengembangan *Custom Terraform Provider* menggunakan modern `terraform-plugin-framework` dalam Go memungkinkan tim platform mengekspos API internal ke format deklaratif HCL standar, menjamin konsistensi tata kelola di seluruh stack perusahaan.