# Bab 06: Data Sources, External State & Multi-Provider Architecture - Evaluasi

## 1. Basic Questions (5 Soal)

### Soal 1
Kapan evaluasi pembacaan data dari sebuah Data Source (`data "..."`) secara teknis dilakukan oleh Terraform engine jika seluruh argumen query-nya bernilai statis dan diketahui sebelum eksekusi?
- A. Hanya saat `terraform apply` berjalan.
- B. Saat fase `terraform refresh` dan `terraform plan`.
- C. Pada saat inisialisasi modul (`terraform init`).
- D. Hanya jika didefinisikan secara eksplisit menggunakan argumen `depends_on`.

### Soal 2
Apa fungsi utama dari meta-argumen `alias` di dalam blok `provider`?
- A. Mengganti nama binary provider yang diunduh di `.terraform/providers`.
- B. Mempercepat proses compile DAG dependency graph.
- C. Mengizinkan multipel instansiasi konfigurasi provider yang sama (misal: beda region atau beda kredensial akun) dalam satu modul Terraform.
- D. Mengubah format enkripsi backend state file secara runtime.

### Soal 3
Apa batasan format output yang wajib dipenuhi oleh skrip eksternal saat dipanggil menggunakan data source `data "external"`?
- A. Array JSON bertingkat (`array of objects`).
- B. Flat JSON object di mana semua keys dan values bertipe string (`map[string]string`).
- C. YAML string sederhana dengan format key: value.
- D. Plain text output yang dipisahkan oleh karakter newline (`\n`).

### Soal 4
Data source `terraform_remote_state` dapat mengakses informasi apa saja dari state file target?
- A. Seluruh resources internal, local values, dan variabel input dari state target.
- B. Hanya resource yang memiliki tags `Public = true`.
- C. Hanya atribut yang secara eksplisit diekspos melalui blok `output` pada root module state target.
- D. Seluruh metadata provider target secara raw.

### Soal 5
Bagaimana cara meneruskan provider dengan alias spesifik dari root module ke dalam child module yang memiliki deklarasi `configuration_aliases`?
- A. Menggunakan environment variable `TF_VAR_provider`.
- B. Child module otomatis mewarisi seluruh alias tanpa deklarasi tambahan.
- C. Menggunakan blok `providers = { ... }` pada blok pemanggilan modul `module "..."`.
- D. Memasukkan alias ke dalam parameter `variables.tf`.

---

## 2. Intermediate Questions (5 Soal)

### Soal 6
Perhatikan kode berikut:
```hcl
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

data "aws_subnet" "selected" {
  vpc_id = aws_vpc.main.id
  filter {
    name   = "tag:Tier"
    values = ["Private"]
  }
}
```
Apa yang akan terjadi pada siklus eksekusi `terraform plan` pertama kali pada lingkungan kosong?
- A. Terraform plan gagal seketika dengan error `SubnetNotFound`.
- B. Nilai data source `data.aws_subnet.selected` ditunda evaluasinya (*deferred*) hingga fase `apply` karena `aws_vpc.main.id` bernilai `(known after apply)`.
- C. Terraform otomatis membatalkan pembuatan `aws_vpc.main`.
- D. Terraform langsung membuat subnet baru secara otomatis.

### Soal 7
Mengapa penggunaan `terraform_remote_state` dianggap berisiko tinggi (*high security risk*) dari perspektif arsitektur keamanan Zero Trust?
- A. Protokol koneksi `terraform_remote_state` tidak mendukung TLS/HTTPS.
- B. State target akan otomatis terhapus jika modul pemanggil mengalami *crash*.
- C. Membaca remote state membutuhkan izin akses langsung ke backend storage (misal: S3), yang membuka akses terhadap seluruh isi state file target, termasuk plain-text secrets dari resource lain.
- D. Remote state tidak mendukung locking engine seperti DynamoDB.

### Soal 8
Bagaimana cara terbaik mendeklarasikan child module agar dapat menerima provider AWS region sekunder tanpa mengunci provider tersebut secara kaku (*hardcoded*) di dalam modul itu sendiri?
- A. Menggunakan blok `provider "aws"` langsung di dalam child module.
- B. Mendefinisikan `configuration_aliases = [aws.secondary]` di blok `terraform.required_providers` child module, lalu memetakannya saat pemanggilan module di root.
- C. Menggunakan function `provider::aws::set_region()`.
- D. Mengubah AWS_DEFAULT_REGION melalui local-exec provisioner.

### Soal 9
Jika Anda mengonfigurasi `data "vault_generic_secret"` untuk mengambil password database dinamis, mengapa secret tersebut tetap memiliki jejak audit risiko pada Terraform?
- A. Nilai secret tersebut di-enkripsi ulang menggunakan enkripsi non-standar.
- B. Nilai secret tersebut disimpan secara plain-text di dalam file `terraform.tfstate` lokal maupun remote backend.
- C. Vault akan otomatis mencabut secret tersebut sebelum `terraform apply` selesai.
- D. Data source Vault mematikan fitur state locking secara global.

### Soal 10
Pada data source `http`, apa langkah yang harus diambil jika API target mengembalikan respons JSON berupa struktur hierarkis objek yang kompleks?
- A. Data source HTTP otomatis memetakan respons ke HCL object tanpa fungsi tambahan.
- B. Gunakan fungsi `jsondecode(data.http.<name>.response_body)` untuk mengonversi string JSON menjadi struktur map/object Terraform yang valid.
- C. Gunakan fungsi `regex()` manual untuk mengekstrak setiap baris.
- D. Gunakan `data "external"` karena data source `http` hanya menerima plain-text biasa.

---

## 3. Scenario-Based Questions (3 Soal Kasus Nyata Industri)

### Skenario 1: The Broken State Decoupling Catastrophe
Perusahaan e-commerce skala besar memiliki modul `network-core` yang mengelola AWS Transit Gateway. Tim Platform menambahkan output baru `tgw_route_table_id` dan secara tidak sengaja mengubah nama output lama `tgw_id` menjadi `transit_gateway_arn`.
Keesokan harinya, tim aplikasi mikroservis yang menggunakan `data.terraform_remote_state.network.outputs.tgw_id` mengalami kegagalan deployment CI/CD total (*blocking pipeline*).
**Pertanyaan**: Bagaimana Anda merancang ulang arsitektur kontrak data antar-stack ini untuk mencegah terjadinya kegagalan berantai (*cascading failure*) yang merusak pipeline tim lain di masa depan?

### Skenario 2: Cross-Account Multi-Region DR Outage
Sebuah institusi perbankan mengimplementasikan Active-Active Disaster Recovery di AWS antara region Singapore (`ap-southeast-1`) dan Jakarta (`ap-southeast-3`). Akun AWS Production Singapore dikelola di bawah ID Akun `111111111111`, sedangkan akun Jakarta dikelola di bawah ID Akun `222222222222`.
Insinyur SRE mencoba mengonfigurasi provider aliasing pada satu root module untuk membuat VPC Peering cross-account dan cross-region, namun proses `terraform apply` selalu gagal pada resource accepter dengan error `AccessDenied / UnauthorizedOperation`.
**Pertanyaan**: Identifikasi titik kegagalan arsitektur autentikasi provider ini dan tuliskan struktur konfigurasi IAM Role Assumption pada provider alias yang tepat untuk mengatasinya.

### Skenario 3: Rogue External Data Source Subprocess Freeze
Tim DevOps membuat `data "external"` yang memanggil skrip Python untuk memeriksa alokasi IP pada sistem IPAM on-premise sebelum membuat subnet AWS. Namun, saat pipeline CI/CD berjalan, proses Terraform menggantung (*hang*) selama berjam-jam hingga runner mencapai timeout dan mati.
Saat diinvestigasi secara lokal, skrip Python tersebut mencoba meminta interaksi input pengguna (*interactive prompt*) karena token autentikasi IPAM telah kedaluwarsa.
**Pertanyaan**: Dari sudut pandang SRE dan Unix Process Lifecycle, tindakan mitigasi teknis apa saja yang wajib ditambahkan pada skrip Python dan definisi blok Terraform untuk menjamin fail-fast behavior?

---

## 4. Practical Chapter Challenge

### Judul Tantangan
**"Multi-Tier Hybrid Interconnect Engine with Dynamic Secrets & Fallback Telemetry"**

### Konteks Kasus
Anda adalah Principal Infrastructure Architect. Anda diminta membangun fondasi deployment multi-wilayah dan multi-sumber data yang aman untuk aplikasi pembayaran digital berlatensi rendah.

### Kriteria Keberhasilan & Batasan Arsitektur
1. **Root Configuration**:
   - Provider default AWS di region `ap-southeast-1`.
   - Provider alias AWS bernama `dr` di region `ap-southeast-3`.
2. **Dynamic External Integration**:
   - Gunakan `data "external"` yang mengeksekusi skrip Python (`hands-on/m01/multi_provider_alias_sim.py`).
   - Skrip harus menerima input environment (`production` atau `staging`), melakukan validasi logika, dan menghasilkan map flat string yang berisi CIDR range dan Region metadata.
3. **Vault Mock Injection**:
   - Simulasikan pembacaan credential atau token rahasia dari endpoint metadata HTTP / Vault Mock.
4. **Multi-Region Provisioning**:
   - Buat satu VPC di Singapore (`aws`) dan satu VPC di Jakarta (`aws.dr`) menggunakan data alokasi CIDR yang didapatkan dari data source external.
   - Resource di kedua region harus diberi tag otomatis yang berisi checksum/token dari data source eksternal tanpa mengekspos token rahasia ke stdout terminal console (`sensitive = true`).
5. **Fail-Safe Mechanism**:
   - Implementasikan *precondition* atau validasi ekspresi (`lifecycle { precondition { ... } }`) yang memastikan bahwa CIDR primer dan sekunder tidak boleh bertabrakan (*overlap*).

---

## Jawaban & Panduan Evaluasi Quiz

### Kunci Jawaban Basic
1. **B** - Jika argumen statis/diketahui, Data Source dievaluasi saat refresh/plan.
2. **C** - Mengizinkan multipel konfigurasi berbeda untuk provider yang sama.
3. **B** - Kontrak `data "external"` mewajibkan flat map JSON string (`map[string]string`).
4. **C** - Hanya output root yang diekspos yang dapat dibaca oleh `terraform_remote_state`.
5. **C** - Menggunakan blok pemetaan eksplisit `providers = { aws.alias = aws.source }`.

### Kunci Jawaban Intermediate
6. **B** - Karena parameter referensi `aws_vpc.main.id` belum terbentuk di fase plan, Terraform menunda (*defer*) eksekusi data source ke fase apply.
7. **C** - Izin baca remote state memberikan eksposur ke seluruh data state, memotong batas isolasi data rahasia (*privilege escalation*).
8. **B** - Menggunakan `configuration_aliases` di modul anak dan menyuntikkannya dari root module menjaga modularitas dan portabilitas.
9. **B** - Seluruh respons data source yang disimpan dalam state tetap berbentuk plain text di dalam `.tfstate`.
10. **B** - Output `response_body` bertipe string mentah sehingga harus didecode menggunakan `jsondecode()`.

### Panduan Solusi Skenario
- **Skenario 1**: Jangan gunakan `terraform_remote_state` langsung antar-tim. Migrasikan interface kontrak ke AWS SSM Parameter Store atau Consul KV. Terapkan Semantic Versioning pada key path (misal: `/network/v1/tgw_id`) dan tetapkan *deprecation policy* sebelum menghapus key lama.
- **Skenario 2**: Provider primer dan sekunder harus mengasumsikan IAM role yang berbeda. Provider alias Jakarta (`dr`) harus menyertakan blok `assume_role` yang merujuk pada ARN Role di Akun B (`222222222222`) yang telah memberikan kepercayaan (*trust relationship*) ke Akun A (`111111111111`).
- **Skenario 3**: 
  1. Pastikan skrip mendeteksi mode non-interaktif (`sys.stdin.isatty()`).
  2. Implementasikan strict socket/HTTP timeout di dalam skrip (misal: timeout 5 detik).
  3. Tangkap semua exception dan cetak error terstruktur ke `sys.stderr`, lalu keluar dengan kode `sys.exit(1)` agar pipeline Terraform langsung *fail-fast*.

---