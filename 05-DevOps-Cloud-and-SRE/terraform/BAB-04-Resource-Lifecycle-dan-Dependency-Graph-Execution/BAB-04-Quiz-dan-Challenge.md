# Kuis & Tantangan Praktik Bab 04: Resource Lifecycle & Dependency Graph Execution

## 1. Basic Questions (5 Soal)

### Soal 1
Mengapa Directed Acyclic Graph (DAG) pada Terraform tidak boleh memiliki siklus (*cycle*)?
- A. Siklus menyebabkan ukuran berkas `terraform.tfstate` melebihi limit 50MB.
- B. Siklus membuat algoritma Topological Sort mengalami infinite recursion/deadlock karena tidak ada node dengan *in-degree* awal yang valid untuk dieksekusi.
- C. Siklus melanggar aturan REST API yang diterapkan oleh cloud provider.
- D. Siklus menyebabkan Terraform CLI secara otomatis beralih ke mode imperative.

### Soal 2
Perhatikan potongan kode berikut:
```hcl
resource "aws_instance" "web" {
  ami           = "ami-01234567"
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.public.id
}
```
Dependensi apa yang terbentuk antara `aws_instance.web` dan `aws_subnet.public`?
- A. Dependensi Eksplisit.
- B. Dependensi Siklik.
- C. Dependensi Implisit.
- D. Dependensi Terbalik (*Inverted Dependency*).

### Soal 3
Apa konsekuensi arsitektural jika Anda menambahkan `create_before_destroy = true` pada resource yang memiliki atribut nama statis (misal: `name = "main-production-db"`)?
- A. Terraform akan otomatis menambahkan UUID acak di belakang nama tersebut.
- B. Eksekusi `terraform apply` akan gagal saat terjadi replacement karena nama tersebut masih dipakai oleh resource lama yang belum di-destroy.
- C. Resource lama akan langsung di-rename oleh cloud provider.
- D. Flag `create_before_destroy` akan diabaikan secara diam-diam oleh Terraform engine.

### Soal 4
Meta-argument lifecycle manakah yang paling tepat digunakan untuk mencegah drift notification pada atribut `desired_capacity` di AWS Auto Scaling Group yang dikontrol oleh Dynamic Scaling Policy?
- A. `replace_triggered_by`
- B. `create_before_destroy`
- C. `ignore_changes`
- D. `prevent_destroy`

### Soal 5
Perintah CLI manakah yang benar untuk mengekspor dependency graph Terraform ke dalam format grafik Graphviz?
- A. `terraform graph --render | dot -Tpng -o graph.png`
- B. `terraform graph | dot -Tpng -o graph.png`
- C. `terraform plan --export-graph=graph.png`
- D. `terraform dag export --format=dot | dot -Tpng`

---

## 2. Intermediate Questions (5 Soal)

### Soal 1
Sebuah resource memiliki konfigurasi:
```hcl
resource "aws_rds_cluster" "primary" {
  cluster_identifier = "aurora-prod-cluster"
  # Konfigurasi database lainnya...
  lifecycle {
    prevent_destroy = true
  }
}
```
Seorang DevOps Engineer menghapus seluruh blok kode `aws_rds_cluster.primary` dari file `.tf` lalu menjalankan `terraform apply`. Apa yang akan terjadi?
- A. Terraform memblokir eksekusi apply dan memunculkan error: `Resource has lifecycle.prevent_destroy set`.
- B. Terraform mengabaikan file `.tf` dan mempertahankan konfigurasi database di cloud.
- C. Terraform berhasil mengeksekusi apply dan **menghancurkan** RDS cluster tersebut karena blok kodenya sudah tidak ada di *Desired State*.
- D. Terraform memindahkan resource database ke status *orphaned state* tanpa menghancurkannya.

### Soal 2
Kapan penggunaan meta-argument `replace_triggered_by` lebih superior dibandingkan dengan penggunaan `null_resource` dengan blok `triggers` konvensional?
- A. Saat resource tidak membutuhkan provider eksternal dan ingin menghindari overhead plugin `null_resource`, serta terintegrasi langsung dengan tipe native `terraform_data`.
- B. Hanya saat mengelola container Docker di lingkungan lokal.
- C. Ketika resource target berada di AWS dan resource pemantau berada di Google Cloud.
- D. `replace_triggered_by` hanya berfungsi untuk menghapus resource tanpa membuat ulang.

### Soal 3
Anda menjalankan perintah:
```bash
terraform apply -target=aws_instance.bastion -auto-approve
```
Dua hari kemudian, pipeline reguler (`terraform apply`) gagal secara misterius. Apa risiko teknis terbesar dari eksekusi `-target` di lingkungan produksi?
- A. Berkas `terraform.tfstate` terenkripsi dan tidak bisa dibuka lagi.
- B. Muncul *State Drift* laten di mana dependensi hilir (*downstream dependencies*) tidak diperbarui, sehingga output variabel menjadi usang (*stale*) dan merusak konsistensi konfigurasi global.
- C. Flag `-target` menghapus semua resource di luar target yang dipilih.
- D. Provider cloud mencabut kredensial IAM karena terdeteksi aksi ilegal.

### Soal 4
Terdapat dua resource security group rule yang saling mereferensikan Security Group ID satu sama lain. Mengapa pemisahan rule menjadi resource `aws_security_group_rule` independen dapat menyelesaikan `Cycle Error` pada Terraform DAG?
- A. Karena `aws_security_group_rule` tidak dicatat di dalam berkas state.
- B. Karena memisahkan container Security Group dari aturan internalnya mengubah simpul graf menjadi hirarki linear: `SG Creation -> Rule Creation`, memutus *circular dependency edge*.
- C. Karena Terraform mengubah eksekusi rule menjadi single-thread secara otomatis.
- D. Karena `aws_security_group_rule` memaksa penghapusan dependensi eksplisit.

### Soal 5
Di bawah kondisi apa penurunan flag konkurensi (misal: `terraform apply -parallelism=2`) sangat disarankan?
- A. Saat mengelola arsitektur multi-region berkecepatan tinggi.
- B. Saat berhadapan dengan Cloud Provider API yang menerapkan rate-limiting ketat (HTTP 429) atau resource yang memerlukan *distributed locking* eksklusif.
- C. Saat ukuran konfigurasi Terraform melebihi 10.000 baris kode.
- D. Saat ingin mengaktifkan fitur `create_before_destroy` secara serentak.

---

## 3. Scenario-Based Questions (3 Kasus Nyata)

### Skenario 1: The Broken Certificate Replacement Disaster
Sebuah platform E-Commerce FinTech memperbarui sertifikat SSL/TLS di AWS Application Load Balancer. Konfigurasi lama:
```hcl
resource "aws_acm_certificate" "cert" {
  domain_name       = "api.fintech.internal"
  validation_method = "DNS"
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = aws_acm_certificate.cert.arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
```
Ketika engineer mengganti nama domain atau parameter sertifikat yang membutuhkan *replacement*, Terraform merencanakan untuk menghapus sertifikat lama terlebih dahulu (*destroy-then-create*). Namun, AWS API menolak penghapusan sertifikat lama dengan error: `ResourceInUse: Certificate is currently in use by Listener arn:...`. Sesi apply langsung terhenti (*crash*).

**Tugas Anda**: Identifikasi akar kegagalan graph Terraform ini dan susun strategi perbaikan deklaratif lengkap menggunakan lifecycle meta-arguments!

### Skenario 2: The Multi-Tenant Mutual Dependency Deadlock
Sebuah platform SaaS mengonfigurasi VPC Peering antar dua VPC di region yang sama:
- VPC Core (Mengelola logging terpusat dan auth)
- VPC Tenant (Mengelola beban kerja tenant)

Engineer menuliskan:
```hcl
resource "aws_route" "core_to_tenant" {
  route_table_id            = aws_route_table.core.id
  destination_cidr_block    = aws_vpc.tenant.cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.peer.id
}

resource "aws_route" "tenant_to_core" {
  route_table_id            = aws_route_table.tenant.id
  destination_cidr_block    = aws_vpc.core.cidr_block
  vpc_peering_connection_id = aws_vpc_peering_connection.peer.id
}

resource "aws_vpc_peering_connection" "peer" {
  peer_vpc_id = aws_vpc.tenant.id
  vpc_id      = aws_vpc.core.id
  auto_accept = true
  depends_on = [
    aws_route.core_to_tenant,
    aws_route.tenant_to_core
  ]
}
```
Saat `terraform apply` dijalankan, Terraform berhenti seketika dengan error:
`Error: Cycle: aws_vpc_peering_connection.peer, aws_route.core_to_tenant, aws_route.tenant_to_core`.

**Tugas Anda**: Jelaskan mengapa graf mendeteksi cycle pada deklarasi di atas dan perbaiki konfigurasinya menjadi DAG yang valid dan stabil!

### Skenario 3: The Ghost Drift Conflict in High-Scale Kubernetes Cluster
Di sebuah cluster Elastic Kubernetes Service (EKS), tim infrastruktur mengelola Node Group via Terraform:
```hcl
resource "aws_eks_node_group" "workers" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "general-workers"
  scaling_config {
    desired_size = 5
    max_size     = 20
    min_size     = 3
  }
  # ...
}
```
Di dalam cluster, Kubernetes Cluster Autoscaler (KCA) diinstal untuk menaikkan/menurunkan jumlah node sesuai beban pod. Setiap kali pipeline CI/CD Terraform dijalankan di malam hari, Terraform mendeteksi *drift* karena `desired_size` telah diubah oleh KCA menjadi 14. Terraform mereset kapasitas worker node kembali ke 5, menyebabkan puluhan Pod aplikasi terlempar ke status `Pending` (*Eviction Storm*).

**Tugas Anda**: Rancang solusi lifecycle definitif untuk mencegah Terraform merekonsiliasi mutasi dinamis dari Kubernetes Cluster Autoscaler tanpa kehilangan kemampuan mengelola `min_size` dan `max_size`.

---

## 4. Practical Chapter Challenge: Resilient Immutable Microservice Rollout
Rancang dan bangun satu set arsitektur Terraform lengkap yang memenuhi seluruh spesifikasi ketat berikut:

1. **Simulasi Node Tanpa AWS Provider Riil**:
   Gunakan kombinasi provider `local` dan `terraform_data` agar dapat dijalankan secara portabel di lingkungan manapun tanpa cloud credential.
2. **Komponen Arsitektur**:
   - Resource A: `local_file.service_binary`: Menampung binary versi aplikasi (konten: string hash).
   - Resource B: `local_file.database_config`: Menampung kredensial DB. Berikan proteksi agar file ini tidak boleh terhapus secara accidental.
   - Resource C: `local_file.app_instance`: Menampung metadata instans aktif (berisi path ke binary dan konfigurasi DB).
3. **Persyaratan Lifecycle & Graph**:
   - Jika `local_file.service_binary` diperbarui, `local_file.app_instance` harus dibuat terlebih dahulu sebelum instance lama dihapus (`create_before_destroy = true`).
   - Gunakan mekanisme `replace_triggered_by` pada `local_file.app_instance` yang mengikat langsung ke perubahan checksum hash `local_file.service_binary`.
   - Gunakan `name_prefix` atau timestamping hashing logic agar tidak terjadi bentrok nama file saat proses penggantian instance.
   - Resource `database_config` harus dilindungi dengan `prevent_destroy = true` (berikan penjelasan cara bypass terkontrol jika migrasi besar dilakukan).
4. **Analisis Visualisasi**:
   Sediakan skrip shell atau instruksi konkret untuk menghasilkan `dag.dot` dan ubah menjadi `dag.png` menggunakan tool Graphviz.

---

## Kunci Jawaban & Panduan Evaluasi

### Kunci Jawaban 1: Basic Questions
1. **B** - Siklus (*cycle*) menghancurkan properti dasar DAG, mengakibatkan topological sort gagal menentukan simpul mana yang harus diproses pertama.
2. **C** - Dependensi implisit terbentuk secara alamiah melalui ekspresi evaluasi atribut `aws_subnet.public.id`.
3. **B** - Terjadi tabrakan nama (*name collision*) pada level API cloud provider karena nama unik statis masih dikuasai oleh resource lama.
4. **C** - `ignore_changes` mengabaikan drift spesifik atribut tertentu tanpa mengabaikan pengelolaan atribut lainnya.
5. **B** - Perintah resminya adalah piping dari `terraform graph` ke utilitas `dot -Tpng -o graph.png`.

### Kunci Jawaban 2: Intermediate Questions
1. **C** - `prevent_destroy` adalah *parser-level guard* yang hanya aktif jika blok deklarasi ada di dalam file `.tf`. Jika blok kodenya dihapus total, Terraform menganggap resource tersebut sengaja dipensiunkan dari desired state dan akan menghancurkannya.
2. **A** - `replace_triggered_by` terintegrasi secara native di engine modern Terraform (>= 1.2) dan bekerja mulus dengan `terraform_data` tanpa memerlukan overhead provider eksternal.
3. **B** - `-target` mengecualikan simpul-simpul di luar subgraph yang ditargetkan, berisiko mengunci state pada kondisi parsial dan menghasilkan *configuration drift* laten pada dependensi turunan.
4. **B** - Pemisahan menjadi `aws_security_group_rule` mengurai dependensi melingkar: Security Group diinstansiasi terlebih dahulu sebagai node kosong, kemudian edge aturan ditambahkan setelah kedua SG terbentuk.
5. **B** - Penurunan paralelisme mengurangi *concurrency burst* yang mencegah pemblokiran akibat API rate limiting (HTTP 429).

### Panduan Jawaban 3: Scenario-Based Questions
- **Skenario 1**: Tambahkan `lifecycle { create_before_destroy = true }` pada blok `aws_acm_certificate.cert`. Selain itu, decoupling resource listener menggunakan `aws_lb_listener_certificate` terpisah untuk mengizinkan attachment sertifikat baru sebelum sertifikat lama dilepas dari load balancer.
- **Skenario 2**: Terjadi loop fatal karena `aws_vpc_peering_connection.peer` membutuhkan routes (`depends_on`), padahal routes membutuhkan `aws_vpc_peering_connection.peer.id`. Solusi: Hapus blok `depends_on` dari `aws_vpc_peering_connection.peer`. Peering connection harus dibuat lebih dulu, lalu route mereferensikan ID-nya secara implisit.
- **Skenario 3**: Terapkan lifecycle meta-argument `ignore_changes`:
  ```hcl
  lifecycle {
    ignore_changes = [
      scaling_config[0].desired_size
    ]
  }
  ```
  Ini mengizinkan KCA mengatur kapasitas aktual tanpa memicu koreksi dari Terraform pada sesi deployment berikutnya.