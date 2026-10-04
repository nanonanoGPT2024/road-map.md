# Modul 01: Resource Lifecycle & Dependency Graph Execution

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonstruksi dan menganalisis mekanisme Directed Acyclic Graph (DAG) yang digunakan oleh Terraform Core untuk kalkulasi State dan eksekusi resource.
- Membedakan secara presisi antara dependensi implisit (*implicit dependency*) dan dependensi eksplisit (`depends_on`), serta mengeliminasi antipattern dependensi buatan.
- Mengontrol perilaku State Machine Terraform menggunakan lifecycle meta-arguments: `create_before_destroy`, `prevent_destroy`, `ignore_changes`, dan `replace_triggered_by`.
- Mengevaluasi risiko operasional, *state divergence*, dan dampak konkurensi dari penggunaan *targeted operations* (`-target`) dan kontrol konkurensi (`-parallelism=n`).
- Menghasilkan visualisasi topologi dependensi Terraform menggunakan CLI graph generator terintegrasi dengan Graphviz (`dot`).

---

## 2. Prerequisite
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Terraform State Architecture**: Pemahaman tentang `terraform.tfstate`, manipulasi blok provider, blok resource, dan data sources.
- **Teori Graf Dasar**: Pemahaman konsep Graph Theory (Node, Edge, Directed Acyclic Graph, Cycle Detection, Topological Sort).
- **Infrastruktur Cloud Dasar (AWS/GCP/Azure)**: Pemahaman siklus hidup VPC, Subnet, Route Table, Compute Instances, Security Groups, dan IAM roles.
- **Terraform CLI CLI Dasar**: Terbiasa dengan workflow `terraform init`, `terraform plan`, dan `terraform apply`.

---

## 3. Concept
Terraform adalah mesin *declarative state reconciliation* yang bersifat *graph-driven*. Konfigurasi Infrastructure as Code (IaC) yang Anda tuliskan tidak dieksekusi secara linear (baris demi baris), melainkan dikompilasi menjadi sebuah **Directed Acyclic Graph (DAG)**. 

Di dalam DAG ini:
- **Node (Simpul)** merepresentasikan resources, providers, data sources, atau module outputs.
- **Edge (Sisi terarah)** merepresentasikan dependensi antar simpul: simpul hulu (*upstream*) harus selesai dievaluasi atau dibuat sebelum simpul hilir (*downstream*) dapat diproses.
- **Acyclic** menandakan bahwa graf tidak boleh memiliki siklus (*circular reference*). Keberadaan loop dependensi (misal: A membutuhkan B, B membutuhkan A) akan menyebabkan kompilasi graf gagal seketika.

Secara bersamaan, **Resource Lifecycle** mengatur state transition dari resource:
1. *Create*: Inisialisasi resource baru di cloud provider.
2. *Read/Refresh*: Penarikan konfigurasi riil ke Terraform state.
3. *Update*: Modifikasi in-place parameter yang didukung provider API tanpa destroy.
4. *Destroy*: Penghapusan resource lama.

Meta-argument `lifecycle` mengintervensi algoritma standar pembaruan Terraform (yang secara default melakukan operasi *Destroy-then-Create* untuk resource yang membutuhkan replacement), mengubah topologi graf dan urutan eksekusi transisi state.

---

## 4. Why
Mengapa arsitektur DAG dan pemahaman Lifecycle sangat krusial bagi Principal Cloud & SRE Architect?
1. **Zero-Downtime Migration**: Mengganti compute template, SSL/TLS certificate, atau Auto Scaling Launch Configuration secara default akan memicu *downtime* jika resource lama dihancurkan sebelum resource baru siap melayani trafik (*destroy-before-create*).
2. **Conformity & Mutasi Eksternal**: Di lingkungan produksi, autoscaling groups secara otomatis memodifikasi atribut `desired_capacity`, atau Kubernetes memutasi label node pool. Tanpa meta-argument `ignore_changes`, Terraform akan terus-menerus mendeteksi *drift* dan berupaya mengembalikan State, menyebabkan *configuration drift thrashing*.
3. **Pencegahan Human Error & Catastrophic Data Loss**: Tanpa proteksi struktural `prevent_destroy`, operasi `terraform destroy` yang tidak disengaja oleh deployment pipeline pada database produksi (misal: RDS, Cloud SQL) akan mengakibatkan penghapusan instan data bisnis.
4. **Deadlock & Bottleneck Execution**: Eksekusi graf yang buruk dapat menghasilkan *false cycle* yang menghentikan deployment pipeline, atau sebaliknya, konkurensi liar (`-parallelism`) yang melebihi batas *Rate Limiting / Quota API* provider cloud.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Directed Acyclic Graph (DAG) Construction
Terraform Core mengoperasikan pemrosesan konfigurasi melalui dua fase graf utama:
1. **Configuration Graph**: Graf abstrak yang dihasilkan langsung dari *parsing* berkas `.tf`.
2. **Apply Graph (Diff/Plan Graph)**: Graf konkret yang memetakan aksi CRUD (Create, Read, Update, Destroy) dengan membandingkan *Desired State* (konfigurasi), *Prior State* (`terraform.tfstate`), dan *Actual Infrastructure* (hasil refresh).

Proses pembentukan DAG:
1. **Node Construction**: Setiap blok `resource`, `data`, `provider`, `module`, dan `variable` dijadikan simpul independen.
2. **Reference Resolution**: Parser mengidentifikasi referensi HCL (contoh: `aws_subnet.main.id`) untuk menarik *Directed Edge* dari resource dependen ke dependency provider.
3. **Cycle Checking**: Terraform mengimplementasikan algoritma DFS (Depth-First Search) atau Tarjan's strongly connected components algorithm untuk memvalidasi ketiadaan loop. Jika terdeteksi siklus, Terraform melempar error: `Cycle: aws_security_group_rule.a, aws_security_group_rule.b`.
4. **Topological Sort**: Node diurutkan secara parsial. Node dengan derajat masuk (*in-degree*) nol dieksekusi terlebih dahulu menggunakan pool worker berbasis *goroutines*.

```
   (In-degree = 0)
   aws_vpc.main
        │
        ▼
   aws_subnet.public
        │
        ▼
   aws_instance.web (In-degree = 1)
```

### 5.2 Implicit vs Explicit Dependencies
* **Implicit Dependencies**: Terbentuk otomatis saat atribut suatu resource merujuk output atribut dari resource lain via ekspresi HCL (contoh: `subnet_id = aws_subnet.public.id`). Terraform Core mengurai ekspresi ini, mengekstrak identitas resource hulu, dan secara implisit menyusun edge DAG. Ini adalah cara yang paling direkomendasikan karena merefleksikan alur data yang riil.
* **Explicit Dependencies (`depends_on`)**: Didefinisikan secara manual via meta-argument `depends_on = [resource_type.name]`. Edge ditambahkan secara artifisial ke DAG tanpa adanya transfer data antar variabel.

*Kapan `depends_on` wajib digunakan?*
Ketika dependensi terjadi di level logika infrastruktur/aksesibilitas, bukan level data schema. Contoh: Resource EC2 instance memerlukan IAM Role Policy selesai dieksekusi agar aplikasi di dalam instance dapat mengakses S3 saat fase *bootstrapping* / *user_data*, meskipun ID IAM Policy tidak dipassing langsung ke argumen `aws_instance`.

### 5.3 Lifecycle Meta-Arguments
Meta-argument `lifecycle` diletakkan di dalam blok resource untuk mengontrol perilaku state engine:

#### A. `create_before_destroy` (boolean)
Secara default, jika sebuah perubahan memerlukan penggantian resource (*forces replacement*), Terraform akan menjalankan:
`Destroy(Node_A) -> Wait -> Create(Node_A_new)`
Dengan `create_before_destroy = true`:
`Create(Node_A_new) -> Wait -> Destroy(Node_A_old)`

*Peringatan Arsitektural*: Jika resource memiliki atribut yang membutuhkan nilai unik secara global (seperti `bucket_name` pada AWS S3 atau `name` pada Security Group), `create_before_destroy` akan gagal karena nama tersebut masih dipakai oleh resource lama yang belum di-*destroy*. Solusi: gunakan `name_prefix` alih-alih `name`.

#### B. `prevent_destroy` (boolean)
Mencegah eksekusi plan yang akan mengakibatkan resource terhapus:
- Jika plan mengindikasikan aksi `destroy` atau `replace` (destroy and re-create), Terraform akan langsung menolak menjalankan plan tersebut dan mengembalikan error exit code 1.
- *Catatan*: Ini tidak melindungi resource jika konfigurasi resource dihapus sepenuhnya dari berkas `.tf`. Jika Anda menghapus blok kodenya, Terraform menganggap resource tersebut tidak lagi terkelola dan merencanakan penghapusan pada state apply.

#### C. `ignore_changes` (list of attribute names or `all`)
Menginstruksikan Terraform engine untuk mengabaikan perbedaan atribut antara *Actual State* dan *Desired State* selama fase `refresh` dan `plan`.
- Berguna untuk: tag yang disuntikkan secara dinamis oleh mutation controller eksternal, `desired_capacity` pada Auto Scaling Groups, atau password/secret yang dirotasi out-of-band.

#### D. `replace_triggered_by` (list of resource/attribute references)
Diperkenalkan pada Terraform v1.2. Memaksa penggantian (*replacement*) resource jika resource target yang direferensikan mengalami modifikasi atau penggantian, meskipun atribut internal resource itu sendiri tidak berubah sama sekali.
- Contoh: VM Worker harus di-*recreate* secara otomatis setiap kali resource `terraform_data` atau konfigurasi `cloud-init` berubah.

### 5.4 Targeted Operations (`-target`)
Flag `-target=resource_type.name` mengisolasi subgraph tertentu dari keseluruhan DAG Terraform:
- Terraform memangkas (*prunes*) semua node yang tidak memiliki hubungan langsung (leluhur maupun keturunan) dengan target yang ditentukan.
- **Bahaya Utama**: Menyebabkan State Drifting struktural. Ketika subgraph diisolasi, *output variable* yang dibutuhkan bagian infrastruktur lain tidak ter-refresh, dan *side-effects* dari dependensi silang dapat merusak dependensi implicit secara laten.

### 5.5 Parallelism Controls (`-parallelism=n`)
Secara default, Terraform Core mengeksekusi DAG dengan konkurensi maksimum `n = 10` goroutines simultan.
- **Dampak Kenaikan (`-parallelism=50`)**: Mengurangi durasi provisioning pada topologi skala masif, namun berisiko memicu API rate-limiting / throttling (HTTP 429 Too Many Requests) dari Cloud Provider API.
- **Dampak Penurunan (`-parallelism=1` atau `2`)**: Berguna untuk debugging race conditions, deployment serial pada resource yang membagi lock eksklusif global, atau provider yang memiliki keterbatasan sesi konkuren.

### 5.6 Graph Visualization
Terraform dapat mengekspor Apply Graph atau Plan Graph dalam format visual DOT language menggunakan perintah:
```bash
terraform graph -type=plan | dot -Tpng -o tf_dag.png
```
Visualisasi ini memetakan seluruh simpul dependensi, simpul ekspansi modul, dan simpul provider, memudahkan verifikasi apakah terjadi *dependency inversion* atau simpul bottleneck.

---

## 6. How
Berikut tata cara implementasi manipulasi lifecycle dan kontrol DAG secara runtut:

1. **Definisikan Dependensi Implisit secara Primer**:
   Selalu sambungkan referensi atribut lintas blok daripada menggunakan hardcoded string.
2. **Terapkan `name_prefix` sebelum menggunakan `create_before_destroy`**:
   Pastikan cloud resource tidak mengalami kendala penamaan tabrakan (*name collision*).
3. **Kombinasikan `ignore_changes` pada Resource Dinamis**:
   Isolasi atribut yang dikendalikan oleh autoscaler atau sistem eksternal.
4. **Validasi Ketiadaan Cycle**:
   Jalankan `terraform validate` dan `terraform test` secara periodik di CI pipeline.
5. **Ekspor Graf dependensi secara berkala**:
   Gunakan Graphviz untuk meninjau *depth* dan *width* dari DAG arsitektur Anda sebelum memproduksi modul berskala enterprise.

---

## 7. Analogy
Bayangkan perakitan gedung bertingkat:
- **DAG**: Anda tidak bisa mengecor lantai 3 sebelum pilar lantai 2 selesai dibuat. Pilar lantai 2 adalah *upstream node*, dan lantai 3 adalah *downstream node*. Pekerjaan instalasi listrik dan pengecatan dinding di lantai yang sama bisa dikerjakan serentak secara paralel karena keduanya tidak memiliki dependensi langsung satu sama lain (*parallelism*).
- **Implicit Dependency**: Tukang ledeng menunggu pipa air utama terpasang karena dia harus menyambungkan keran ke pipa tersebut (transfer data/atribut nyata).
- **Explicit Dependency (`depends_on`)**: Pengecat dinding harus menunggu alarm kebakaran diuji dulu, bukan karena cat butuh kabel alarm, melainkan karena suara bising alarm bisa mengganggu keselamatan kerja pengecat (dependensi logika prosedural).
- **create_before_destroy**: Mengganti jembatan penyeberangan lama. Alih-alih merobohkan jembatan lama terlebih dahulu yang membuat lalu lintas macet total, Anda membangun jembatan baru di sebelahnya sampai selesai dibuka, barulah jembatan lama dibongkar.

---

## 8. Diagram (ASCII)

### DAG Execution Flow & Lifecycle Shift

```
[DEFAULT BEHAVIOR: DESTROY-THEN-CREATE]
  Configuration Change (Requires New Resource)
              │
              ▼
       ┌──────────────┐
       │ Destroy Old  │  <─── Downtime Window Dimulai
       └──────┬───────┘
              │ (Tunggu selesai)
              ▼
       ┌──────────────┐
       │  Create New  │  <─── Downtime Window Selesai
       └──────────────┘

────────────────────────────────────────────────────────────

[LIFECYCLE BEHAVIOR: CREATE-BEFORE-DESTROY]
  Configuration Change (Requires New Resource)
              │
              ▼
       ┌──────────────┐
       │  Create New  │  <─── Berjalan di samping resource lama
       └──────┬───────┘
              │ (Sukses & Aktif)
              ▼
       ┌──────────────┐
       │ Destroy Old  │  <─── Zero Downtime
       └──────────────┘

────────────────────────────────────────────────────────────

[TERRAFORM CORE DAG COMPILATION ENGINE]

        Root Module Configuration (.tf)
                      │
                      ▼
            HCL AST Parser Engine
                      │
                      ▼
           Reference Extraction Pass
     (Mengidentifikasi resource.attribute references)
                      │
                      ▼
         Cycle Detection (Tarjan DFS)
       ┌──────────────┴──────────────┐
       │                             │
[Cycle Detected]              [Acyclic Verified]
       │                             │
 Terpental Error:                    ▼
 "Cycle in Graph"         Topological Sorting
                                     │
                                     ▼
                          Worker Pool Concurrency
                            (-parallelism=n)
                               ┌─────┴─────┐
                               ▼           ▼
                            Worker 1    Worker 2 ...
```

---

## 9. Simple Example
Contoh dasar penggunaan dependensi implisit vs eksplisit, dan proteksi database dengan `prevent_destroy`:

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }
}

# Node 1: Root Node
resource "local_file" "network_config" {
  filename = "${path.module}/network.cfg"
  content  = "ip_range=10.0.0.0/16\ngateway=10.0.0.1"

  lifecycle {
    # Mencegah penghapusan resource secara sengaja maupun tidak sengaja
    prevent_destroy = false # Set ke true untuk mode proteksi ketat
  }
}

# Node 2: Implicit Dependency (Membaca file_permission dari local_file.network_config)
resource "local_file" "app_config" {
  filename = "${path.module}/app.cfg"
  content  = "network_ref=${local_file.network_config.id}\napp_port=8080"
}

# Node 3: Explicit Dependency
resource "local_file" "audit_log" {
  filename = "${path.module}/audit.log"
  content  = "Audit initialised at deployment time."

  # Explicit dependency: Dijalankan HANYA setelah app_config selesai dibuat
  depends_on = [
    local_file.app_config
  ]
}
```

---

## 10. Practical Example (Konfigurasi Zero-Downtime AWS ASG & Target Tracking)

Konfigurasi berikut mendemonstrasikan orkestrasi `create_before_destroy`, `ignore_changes`, dan `replace_triggered_by` pada arsitektur AWS Auto Scaling Group terdistribusi:

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "ap-southeast-1"
}

# Data source untuk AMI Ubuntu LTS terbaru
data "aws_ami" "ubuntu" {
  most_recent = true
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  owners = ["099720109477"] # Canonical
}

# Node 1: Security Group menggunakan name_prefix agar aman terhadap create_before_destroy
resource "aws_security_group" "web_sg" {
  name_prefix = "web-sg-"
  description = "Cluster HTTP inbound traffic"
  vpc_id      = "vpc-0123456789abcdef0" # Placeholder ID

  ingress {
    description = "Allow HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Node 2: Resource Arbitrary Triggers untuk memaksa instance replacement
resource "terraform_data" "bootstrap_checksum" {
  input = filesha256("${path.module}/scripts/userdata.sh")
}

# Node 3: Launch Template dengan replacement trigger
resource "aws_launch_template" "web_template" {
  name_prefix   = "web-tpl-"
  image_id      = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"

  vpc_security_group_ids = [aws_security_group.web_sg.id]

  user_data = filebase64("${path.module}/scripts/userdata.sh")

  lifecycle {
    create_before_destroy = true
    # Launch template otomatis di-replace bila isi user_data script berubah
    replace_triggered_by = [
      terraform_data.bootstrap_checksum
    ]
  }
}

# Node 4: Auto Scaling Group dengan ignore_changes untuk kapasitas dinamis
resource "aws_autoscaling_group" "web_asg" {
  name_prefix         = "web-asg-"
  vpc_zone_identifier = ["subnet-01234567", "subnet-89abcdef"]
  desired_capacity    = 2
  max_size            = 10
  min_size            = 2

  target_group_arns = []

  launch_template {
    id      = aws_launch_template.web_template.id
    version = "$Latest"
  }

  lifecycle {
    create_before_destroy = true
    # Abaikan perubahan pada desired_capacity karena diatur oleh Dynamic Scaling Policy eksternal
    ignore_changes = [
      desired_capacity,
      load_balancers,
      target_group_arns
    ]
  }
}
```

---

## 11. Real World Example
**Skenario**: Migrasi SSL/TLS Certificate Authority pada Enterprise Application Gateway / ALB di FinTech.
- **Masalah**: Mengganti sertifikat SSL yang kedaluwarsa pada load balancer yang aktif. Jika menggunakan lifecycle standar, perubahan ARN sertifikat pada Listener akan memodifikasi in-place atau memicu recreate listener, memutus transaksi ribuan user secara tiba-tiba (*connection drop*).
- **Solusi Rekayasa Lifecycle**:
  1. Buat sertifikat baru di ACM menggunakan `create_before_destroy = true`.
  2. Gunakan `aws_lb_listener_certificate` terpisah alih-alih me-replace listener utama.
  3. Terapkan `replace_triggered_by` pada resource validation untuk memastikan validasi domain DNS selesai secara atomic sebelum sertifikat dipasang ke load balancer.
  4. Eksekusi `terraform apply -parallelism=5` untuk mencegah AWS ACM Certificate Request API memicu rate limit.

---

## 12. Trade-offs

| Aspek | Pilihan A | Pilihan B | Trade-off Analisis |
| :--- | :--- | :--- | :--- |
| **Pembaruan Resource** | `create_before_destroy = true` | Default (*destroy-then-create*) | *Create-before-destroy* mencegah downtime tetapi membutuhkan kapasitas kuota ganda (IP, vCPU, resource limit) secara sementara selama proses migrasi. |
| **Penanganan Drift** | `ignore_changes` | Pure Declarative Enforcement | Menggunakan `ignore_changes` mengizinkan orkestrasi dinamis (Autoscaler/Kubelet), namun mengaburkan visibilitas *real state* dari source code (meningkatkan State Drift). |
| **Kecepatan Apply** | High Concurrency (`-parallelism=50`) | Low Concurrency (`-parallelism=10`) | Waktu apply drastis lebih cepat, namun probabilitas terkena Cloud Provider API Rate Limiting (HTTP 429) meningkat pesat. |
| **Eksekusi Parsial** | `-target` | Full Graph Execution | Memungkinkan mitigasi insiden gawat darurat (*hotfix*), tetapi mengabaikan cascading output dan menghasilkan state inconsistent antar resource. |

---

## 13. When To Use
- Gunakan `create_before_destroy` secara wajib pada:
  - Security Groups yang terikat pada instans compute yang sedang aktif.
  - Compute Launch Templates / Configurations.
  - Database Subnet Groups.
- Gunakan `ignore_changes` untuk:
  - Atribut resource yang dikelola oleh Cloud Provider System (contoh: AMI ID yang otomatis di-patch, autoscaling min/max/desired).
  - Kubernetes cluster dynamic nodes atau storage volumes yang di-resize oleh Kubelet.
- Gunakan `replace_triggered_by` saat:
  - VM harus di-deploy ulang ketika berkas startup/userdata di disk mengalami perubahan *checksum*.
  - Instance compute harus di-reboot/re-create saat sertifikat SSL privat lokal di-*rotate*.

---

## 14. When NOT To Use
- **JANGAN gunakan `create_before_destroy`**:
  - Pada resource yang memiliki *Strict Unique Global Namespace* tanpa dukungan parameter prefix (misal: penamaan statis bucket S3 tertentu, domain names registrar). Pembuatan resource baru akan gagal karena nama lama masih eksis.
- **JANGAN gunakan `ignore_changes = all`**:
  - Ini adalah *architectural antipattern*. Mengabaikan seluruh perubahan mengubah Terraform menjadi penyedia provisioning satu kali (*imperative provisioner*) alih-alih declarative management tool.
- **HINDARI `depends_on` jika implicit data reference sudah tersedia**:
  - Menambahkan `depends_on` saat Anda sudah mereferensikan `aws_subnet.main.id` ke dalam `aws_instance` adalah tindakan *redundant* yang memperlambat Terraform dalam mengeksplorasi paralelisme DAG yang optimal.
- **HINDARI `-target` pada pipeline CI/CD reguler**:
  - Penggunaan `-target` hanya boleh diizinkan pada saat perbaikan *broken state* darurat di production. Jangan pernah memasukkannya ke dalam workflow continuous delivery standar.

---

## 15. Common Mistakes
1. **Name Collision pada `create_before_destroy`**:
   Mendefinisikan `name = "production-alb"` pada Security Group bersamaan dengan `create_before_destroy = true`. Terraform akan mencoba membuat `production-alb` kedua sebelum yang pertama dihapus. AWS API akan menolak karena nama duplikat.
   *Solusi*: Gunakan `name_prefix = "production-alb-"`.
2. **Circular Dependencies (DAG Cycles)**:
   Mengarahkan Security Group A mengizinkan inbound dari Security Group B, sementara Security Group B mengizinkan inbound dari Security Group A langsung di dalam deklarasi blok masing-masing.
   *Solusi*: Pecah dependensi menggunakan resource independen `aws_security_group_rule`.
3. **Mengabaikan Dampak Cascade Destroy**:
   Menghapus resource modul upstream dan mengeksekusi apply tanpa menyadari bahwa dependensi eksplisit (`depends_on`) akan memicu penghapusan massal seluruh downstream resources secara beruntun.
4. **Mengubah `prevent_destroy` menjadi true lalu menghapus blok kode dari berkas `.tf`**:
   Terraform **hanya** mengevaluasi meta-argument `prevent_destroy` jika blok resource tersebut masih ada dalam konfigurasi. Jika Anda menghapus seluruh blok kodenya dari file, Terraform menganggap deklarasi tersebut dihapus dari *Desired State* dan akan menghancurkan resource tersebut di cloud saat apply!

---

## 16. Best Practices
1. **Always Use `name_prefix` for Ephemeral/Mutable Resources**: Pasangan sejati dari `create_before_destroy` adalah konfigurasi parameter `name_prefix`.
2. **Decouple Mutual References with Standalone Binding Resources**:
   Pisahkan relasi dua arah menjadi:
   - Resource Node A
   - Resource Node B
   - Binding Node (A to B)
   - Binding Node (B to A)
3. **Audit Target Usage**: Terapkan rule policy engine (seperti OPA Conftest atau Sentinel) di CI/CD yang memblokir pipeline jika terdeteksi parameter `-target` dijalankan tanpa otorisasi SRE Principal.
4. **Terapkan `replace_triggered_by` dengan `terraform_data`**: Hindari *workaround* kuno yang memanfaatkan `null_resource` dengan triggers map. Gunakan `terraform_data` bawaan Terraform >= 1.4 untuk efisiensi komputasi graph.

---

## 17. Troubleshooting

| Gejala Masalah | Akar Masalah | Solusi Penanganan |
| :--- | :--- | :--- |
| `Error: Cycle: aws_instance.web, aws_security_group.sg` | Adanya dependensi timbal-balik yang mengunci evaluasi node (Node A butuh Node B, Node B butuh Node A). | Ekstrak aturan relasi dari dalam blok resource utama ke sub-resource terpisah (misal: `aws_security_group_rule`). |
| `Error: Resource already exists` saat menerapkan `create_before_destroy` | Nama resource bentrok di API provider cloud karena nama identik masih dipegang instance lama. | Hapus atribut statis `name = "..."`, ganti menjadi `name_prefix = "..."` untuk memberikan sufiks acak otomatis. |
| `Error: Instance cannot be destroyed: Resource has lifecycle.prevent_destroy set` | Seseorang atau pipeline mencoba menghancurkan resource yang diproteksi. | Jika penghapusan disengaja: ubah manual `prevent_destroy = false` di berkas `.tf`, jalankan `terraform apply`, lalu hapus resource secara legal. |
| Pipeline gagal akibat HTTP 429 Too Many Requests (Rate Throttled) | Default concurrency (`-parallelism=10`) membanjiri API endpoint provider cloud. | Turunkan derajat konkurensi DAG dengan flag `-parallelism=3` atau `-parallelism=5` pada CLI runner. |

---

## 18. Exercise
1. Tulis sebuah konfigurasi Terraform yang menghasilkan 3 berkas lokal: `node1.txt`, `node2.txt`, dan `node3.txt`.
2. Konfigurasikan agar `node2` bergantung secara eksplisit (`depends_on`) ke `node1`, dan `node3` bergantung secara implisit ke konten dari `node2`.
3. Gunakan `terraform graph` dan ubah hasilnya menjadi format SVG atau PNG menggunakan Graphviz CLI.
4. Tambahkan `lifecycle { create_before_destroy = true }` ke `node1.txt` dan modifikasi konfigurasinya. Amati urutan eksekusi pada log CLI.

---

## 19. Challenge
Rancang arsitektur Terraform untuk skenario berikut:
- Terdapat Security Group Database (`sg_db`) dan Security Group Application (`sg_app`).
- `sg_db` hanya menerima port 5432 dari `sg_app`.
- `sg_app` hanya menerima port 8080 dari `sg_db` (untuk health metrics callback).
- Jika keduanya dideklarasikan secara in-line, graf akan mengalami siklus (*Cycle Error*).
- **Instruksi**: Buat konfigurasi HCL yang memutus siklus DAG tersebut dengan decoupled resources, lengkapi dengan `lifecycle` protection agar `sg_db` tidak bisa dihancurkan secara tidak sengaja, dan pastikan setiap perubahan template app memicu reload instans secara terkontrol menggunakan `replace_triggered_by`.

---

## 20. Summary
- **DAG Execution Engine**: Jantung dari Terraform adalah representasi topologis dependensi (Directed Acyclic Graph). Terraform mengevaluasi dependency edges untuk memaksimalkan paralelisasi goroutine tanpa melanggar urutan dependensi.
- **Implicit over Explicit**: Dependensi implisit terbentuk natural via referensi atribut HCL; dependensi eksplisit (`depends_on`) adalah jalan keluar darurat untuk mengunci relasi logika prosedural non-atribut.
- **Lifecycle Alteration**:
  - `create_before_destroy`: Membalik urutan destroy-then-create demi zero downtime (wajib didukung `name_prefix`).
  - `prevent_destroy`: Kunci pengaman state engine terhadap penghapusan database/data-bearing resource.
  - `ignore_changes`: Perlindungan terhadap drift thrashing yang disebabkan oleh sistem orkestrasi eksternal.
  - `replace_triggered_by`: Mekanisme modern pengikat lifecycle antar-resource independen.
- **Operational Discipline**: Penggunaan `-target` memecah keutuhan graf dan harus dihindari di automation pipeline, sedangkan `-parallelism` adalah pengatur kecepatan dan beban API cloud provider.