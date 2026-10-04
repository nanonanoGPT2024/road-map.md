# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Resource Lifecycle dan Dependency Graph Execution**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan memiliki kompetensi mendalam untuk:

1. **Menganalisis dan Membedah Algoritma Dependency Graph:** Mengonseptualisasikan bagaimana Terraform Core menyusun *Directed Acyclic Graph* (DAG), melakukan *transitive reduction*, dan mengeksekusi *topological sorting* pada memori saat fase kompilasi konfigurasi.
2. **Menguasai Mekanika State Transition Lifecycle:** Mengimplementasikan dan memanipulasi direktif `create_before_destroy`, `prevent_destroy`, `ignore_changes`, dan `replace_triggered_by` pada arsitektur berdaya tahan tinggi (*high-availability*) tanpa menimbulkan *downtime* atau *state corruption*.
3. **Mengeliminasi Dependency Cycles & Propagation Deadlocks:** Mendiagnosis dan merekayasa balik siklus dependensi sirkular (*cyclic dependencies*) dan anomali propagasi *Create-Before-Destroy* (CBD inversion hell) pada topologi cloud skala enterprise.
4. **Mengoptimalkan Graph Walk Performance:** Mengonfigurasi worker parallelism, mengendalikan thread pools, dan memitigasi *rate limiting/API throttling* dari cloud provider saat mengeksekusi ribuan node resource secara paralel.
5. **Membangun Arsitektur Zero-Downtime Deployment:** Mendesain resource pattern yang mengisolasi *immutable infrastructure* dari kegagalan mutasi nama (*naming collision*) dan *in-place updates* yang bersifat destruktif.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:

* **Terraform Fundamental:** Deklarasi HCL tingkat lanjut, pemisahan modularisasi, dynamic blocks, serta manipulasi *terraform state* tingkat dasar (`terraform state mv`, `rm`, `pull`).
* **Struktur Data & Algoritma Dasar:** Konsep graf berarah (*directed graphs*), *Directed Acyclic Graph* (DAG), *topological sort*, dan *depth-first search* (DFS).
* **Cloud Architecture & Networking:** Pemahaman tentang siklus hidup resource cloud (AWS VPC, Subnets, Routing Tables, ENIs, Security Groups, IAM Policies, ALB Target Groups, dan Autoscaling Groups).
* **CLI & Diagnostic Tooling:** Penggunaan Linux shell (`bash`/`zsh`), visualisasi Graphviz (`dot`), dan parsing log runtime Terraform melalui variabel environment `TF_LOG`.

---

## 3. Concept & Internal Architecture

Terraform beroperasi sebagai sistem dua tingkat yang terdiri dari **Terraform Core** dan **Terraform Plugins (Providers)**. Resource Lifecycle dan Graph Execution sepenuhnya berada di bawah kendali Terraform Core, yang bertanggung jawab atas sintesis kode deklaratif menjadi sekumpulan instruksi mutasi infrastruktur imperatif yang aman.

```
+-----------------------------------------------------------------------+
|                            TERRAFORM CORE                             |
|                                                                       |
|  +--------------------+     +-------------------+     +------------+  |
|  | Configuration (HCL)| --> | AST Compilation   | --> | Raw Graph  |  |
|  +--------------------+     +-------------------+     +------------+  |
|                                                             |         |
|                                                             v         |
|  +--------------------+     +-------------------+     +------------+  |
|  | Fully Optimized DAG| <-- | Transitive Reduct.| <-- | Cycle Check|  |
|  +--------------------+     +-------------------+     +------------+  |
+-------------|---------------------------------------------------------+
              |
              | Concurrent Walk (Worker Pool: -parallelism=N)
              v
+-----------------------------------------------------------------------+
|                           GRAPH EVALUATOR                             |
|                                                                       |
|   Goroutine 1            Goroutine 2               Goroutine N        |
|   [Node A: Read]         [Node B: Plan]            [Node C: Apply]    |
+-------------|-------------------|-------------------------|-----------+
              |                   |                         |
              | RPC (gRPC)        | RPC (gRPC)              | RPC (gRPC)
              v                   v                         v
+-----------------------------------------------------------------------+
|                           PROVIDER PLUGINS                            |
|                                                                       |
|    aws_vpc                aws_subnet             aws_security_group   |
+-----------------------------------------------------------------------+
```

### Algoritma Directed Acyclic Graph (DAG)

Saat mengeksekusi perintah CLI (`plan`, `apply`, `destroy`), Terraform Core mengonversi file konfigurasi dan file state saat ini menjadi struktur DAG.
* **Nodes (Simpul):** Merepresentasikan resource, data sources, provider instances, modul, atau root outputs.
* **Edges (Busur Berarah):** Merepresentasikan relasi dependensi. Jika Resource B membutuhkan atribut dari Resource A (`Resource B -> Resource A`), maka secara komputasi, Terraform harus mengevaluasi Resource A sebelum Resource B.

Operasi graf ini melalui empat fase utama di Terraform Core:
1. **Construction:** Semua resource block, output, variable, dan provider ditransformasikan menjadi node. Referensi implisit (`aws_security_group.sg.id`) dan eksplisit (`depends_on = [aws_vpc.main]`) dipetakan menjadi directed edges.
2. **Cycle Detection (Deteksi Siklus):** Terraform menerapkan algoritma *Tarjan’s Strongly Connected Components* atau modifikasi DFS. Jika ditemukan path di mana $Node_A \to Node_B \to \dots \to Node_A$, Terraform membatalkan eksekusi dan melempar error `Cycle: ...`.
3. **Transitive Reduction (Reduksi Transitif):** Jika terdapat edge $A \to B$, $B \to C$, dan direct edge $A \to C$, Terraform Core akan memotong edge redundant $A \to C$. Langkah ini meminimalkan constraints sinkronisasi antar thread tanpa mengubah urutan topologis akhir.
4. **Topological Sorting:** Algoritma penyusunan linear dari node-node graf sedemikian rupa sehingga untuk setiap edge $u \to v$, node $v$ harus dievaluasi sebelum node $u$.

### Mekanika Lifecycle Meta-Arguments

Meta-argument dalam blok `lifecycle` bertindak sebagai *compiler directives* yang mengubah cara Terraform Core mengonstruksi graf atau menghasilkan plan diff:

```
  +-------------------------------------------------------------+
  |              LIFECYCLE MUTATION MECHANISMS                  |
  +-------------------------------------------------------------+

  1. create_before_destroy (CBD):
     Default:  [Destroy Old] ───────────────► [Create New]
     With CBD: [Create New]  ───────────────► [Update Reference] ──► [Destroy Old]

  2. prevent_destroy:
     [Plan Phase] ──► Inspect Diff ──► If Action == "delete" ──► PANIC / HALT

  3. ignore_changes:
     [State Diff] ──► Strip target attribute diffs ──► Action = "no-op"

  4. replace_triggered_by:
     [Source Resource Mutated] ──► Force Diff "replace" on Target Resource
```

* **`create_before_destroy = true` (CBD):** Secara default, jika resource harus diganti (*replaced*), urutan eksekusi adalah: *Destroy Node Lama* $\to$ *Create Node Baru*. CBD membalik relasi dependensi ini di dalam graf: Node Baru dibuat terlebih dahulu, dependensi diarahkan ke Node Baru, lalu Node Lama dimusnahkan. Hal ini membutuhkan teknik khusus pada resource yang mewajibkan atribut penamaan unik (`name` vs `name_prefix`).
* **`prevent_destroy = true`:** Validasi yang terjadi murni pada tahap compile/planning time. Jika *execution plan* mengindikasikan bahwa node tersebut akan mengalami aksi `Destroy` atau `Replace`, Terraform Core langsung menghentikan proses sebelum menyentuh cloud API.
* **`ignore_changes = [...]`:** Beroperasi saat fase *Plan Attribute Diffing*. Nilai state yang tersimpan di cloud provider dibandingkan dengan state lokal. Jika terdapat selisih (*drift*) pada atribut yang didefinisikan dalam `ignore_changes`, selisih tersebut dibersihkan dari *diff structural set*, mencegah Terraform melakukan update in-place atau replacement yang tidak diinginkan.
* **`replace_triggered_by = [...]`:** Diperkenalkan di Terraform 1.2+. Menginjeksikan dynamic synthetic edge ke dalam graf plan. Jika resource target yang direferensikan mengalami perubahan atribut atau replacement, resource deklarator akan secara otomatis diubah status perencanaannya menjadi *Must Replace* (`force replacement`).

---

## 4. Why & What

### Mengapa Perilaku Default Terraform Tidak Cukup untuk Enterprise?

1. **Downtime pada Mutasi In-place:** Banyak resource cloud mendasar—seperti `aws_autoscaling_group`, `aws_security_group_rule`, atau Database Subnet Group—memerlukan proses re-kreasi saat parameter non-updatable berubah. Pola destruksi default (*destroy-then-create*) memutus koneksi aplikasi selama beberapa detik hingga beberapa menit.
2. **Keterbatasan API Cloud (Immutable Names):** Layanan cloud modern menolak instansiasi dua resource dengan nama identik di region yang sama. Tanpa pemahaman mendalam tentang *Create-Before-Destroy* dan pemanfaatan `name_prefix`, eksekusi Terraform akan gagal dengan error seperti `ResourceAlreadyExistsException`.
3. **Konflik Kontrol Eksternal:** Pada platform enterprise, arsitektur sering diintegrasikan dengan orkestrator eksternal seperti Kubernetes HPA (Horizontal Pod Autoscaler) atau CloudWatch Autoscaling. Mengelola atribut dinamis seperti `desired_capacity` tanpa konfigurasi `ignore_changes` yang presisi akan memicu *configuration drift loop* (revert war antara Terraform dan autoscaler).

---

## 5. How (Workflow Detail)

Berikut adalah urutan internal Terraform Core saat memproses blok deklaratif hingga eksekusi thread:

```
[HCL Parsing & Validation]
           │
           ▼
[State Loading (Lock Acquisition)]
           │
           ▼
[Dynamic DAG Construction]
   - Parse direct references (Implicit)
   - Parse depends_on blocks (Explicit)
   - Parse replace_triggered_by (Injected Edges)
           │
           ▼
[Cycle Detection Engine] ─── (Cycle Found?) ──► YES ──► [HALT: Emit Cyclic Stack Trace]
           │
           NO
           ▼
[Lifecycle Transformation]
   - Invert edges for create_before_destroy nodes
   - Propagate CBD upward through dependent DAG paths
           │
           ▼
[Graph Walk (Execution Phase)]
   - Max workers determined by -parallelism flag (Default: 10)
   - Worker goroutines fetch unblocked nodes from channel
   - Evaluate Node:
       * Pre-condition check
       * Provider RPC Call (Diff/Apply)
       * prevent_destroy validation
       * State Update
   - Signal dependent nodes that prerequisite edge is resolved
           │
           ▼
[Release State Lock & Persist State]
```

### Mekanisme CBD Propagation (Create-Before-Destroy Hell)

Salah satu aspek arsitektural yang paling sering memicu kegagalan pipeline adalah **CBD Propagation**. Jika Resource $A$ memiliki `create_before_destroy = true`, dan Resource $B$ bergantung pada $A$ (`B -> A`), maka Resource $B$ **wajib** memiliki `create_before_destroy = true`.

Jika aturan ini dilanggar:
1. Graf mencoba membuat $A_{baru}$.
2. Graf harus menghancurkan $A_{lama}$.
3. Tetapi $B$ membutuhkan $A_{lama}$, sementara $B$ dikonfigurasi dengan siklus hidup *Destroy-Then-Create*.
4. Graf mendeteksi kebuntuan operasional (*deadlock*) dan memunculkan error:
   `Error: Invalid create_before_destroy cycle: aws_instance.b -> aws_security_group.a -> aws_instance.b`

---

## 6. Analogy & Diagram ASCII

### Analogi: Sistem Kontraktor Gedung vs Manufaktur Jalur Perakitan
Pikirkan eksekusi graf Terraform seperti manajemen proyek konstruksi skala besar:
* **Node Tanpa Dependensi:** Fondasi tanah, pengadaan baja, dan pemesanan semen. Semuanya dapat dikerjakan bersamaan oleh subkontraktor independen (Worker Goroutines).
* **Implicit Dependency:** Pengecoran lantai dua secara fisik tidak dapat dieksekusi sebelum pilar lantai satu selesai dicor, meski arsitek tidak menuliskan instruksi eksplisit "tunggu lantai satu".
* **`create_before_destroy`:** Seperti merelokasi gardu listrik utama rumah sakit. Anda tidak mematikan dan merobohkan gardu lama terlebih dahulu (akan membunuh pasien di ruang operasi). Sebaliknya, Anda membangun gardu baru di sebelahnya, menyambungkan kabel beban ke gardu baru, memastikan daya menyala, lalu merobohkan gardu lama.

### Diagram: Standard vs Create-Before-Destroy Lifecycle Graph

```
STANDARD REPLACEMENT (Downtime Exposed):
========================================
[Step 1: Destroy Existing Node]  ──►  Time Gap (Downtime)  ──►  [Step 2: Create New Node]
(Traffic dropping!)                                             (Traffic recovers)


CBD REPLACEMENT (Zero-Downtime Pipeline):
=========================================
Time Index:  T1                     T2                          T3
             [Deploy New Node] ──►  [Switch Traffic Pointer] ──► [Terminate Old Node]
             (Old node active)      (Both nodes active)         (New node handles 100%)
```

---

## 7. Simple Example & Practical Example

### Simple Example: Launch Template Replacement Menggunakan `replace_triggered_by`

Konfigurasi ini memastikan bahwa setiap pembaruan pada User Data Script (disimpan di file eksternal) akan memaksa instansiasi ulang Launch Template, yang selanjutnya secara otomatis memicu pembaruan bertahap pada VM.

```hcl
# File: simple_example/main.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }
}

resource "local_file" "bootstrap_script" {
  filename = "${path.module}/scripts/bootstrap.sh"
  content  = <<-EOT
    #!/usr/bin/env bash
    echo "Configuring node version 1.2.0..."
    apt-get update && apt-get install -y nginx
  EOT
}

resource "local_file" "machine_manifest" {
  filename = "${path.module}/output/machine_manifest.json"
  content  = jsonencode({
    instance_type = "c6i.xlarge"
    kernel        = "Linux 6.2"
    provisioned_at = timestamp()
  })

  lifecycle {
    # Memaksa pembacaan ulang dan instansiasi ulang manifest jika bootstrap script berubah
    replace_triggered_by = [
      local_file.bootstrap_script.content
    ]
    
    # Menghindari perubahan timestamp memicu drift terus menerus
    ignore_changes = [
      content
    ]
  }
}
```

### Practical Example: Production Zero-Downtime Rolling Update ALB Target Group & ASG

Arsitektur produksi ini memecahkan masalah pergantian AWS ALB Target Group dan Auto Scaling Group (ASG) secara mulus tanpa *downtime* dan tanpa konflik nama.

```hcl
# File: practical_infra/compute.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }
}

variable "environment" {
  type    = string
  default = "production"
}

variable "app_port" {
  type    = number
  default = 8080
}

# 1. Target Group dengan Naming Prefix dan CBD Lifecycle
resource "aws_lb_target_group" "api_tg" {
  name_prefix          = "api-"
  port                 = var.app_port
  protocol             = "HTTP"
  vpc_id               = "vpc-0123456789abcdef0"
  target_type          = "instance"
  deregistration_delay = 30

  health_check {
    enabled             = true
    path                = "/healthz"
    port                = var.app_port
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 10
  }

  lifecycle {
    create_before_destroy = true
  }
}

# 2. Launch Template dengan penanganan immutability
resource "aws_launch_template" "api_lt" {
  name_prefix   = "api-lt-"
  image_id      = "ami-0c55b159cbfafe1f0" # Golden AMI
  instance_type = "t3.medium"

  update_default_version = true

  monitoring {
    enabled = true
  }

  network_interfaces {
    associate_public_ip_address = false
    security_groups             = ["sg-0a1b2c3d4e5f67890"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

# 3. Autoscaling Group yang diikat secara presisi ke Target Group
resource "aws_autoscaling_group" "api_asg" {
  name_prefix         = "asg-api-${var.environment}-"
  vpc_zone_identifier = ["subnet-01234567", "subnet-89abcdef"]
  target_group_arns   = [aws_lb_target_group.api_tg.arn]

  min_size         = 2
  max_size         = 10
  desired_capacity = 4

  launch_template {
    id      = aws_launch_template.api_lt.id
    version = aws_launch_template.api_lt.latest_version_number
  }

  # Mengabaikan perubahan kapasitas jika Auto Scaling dinamis diatur oleh AWS In-guest/CloudWatch
  lifecycle {
    create_before_destroy = true
    ignore_changes = [
      desired_capacity,
      load_balancers,
      target_group_arns
    ]
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
      instance_warmup        = 300
    }
    triggers = ["tag"]
  }
}

# 4. Listener Rule Binding
resource "aws_lb_listener_rule" "routing_rule" {
  listener_arn = "arn:aws:elasticloadbalancing:ap-southeast-1:123456789012:listener/app/my-alb/12345/abcdef"
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api_tg.arn
  }

  condition {
    path_pattern {
      values = ["/v2/api/*"]
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Breaking Cyclic Dependency pada Migrasi Microservice Payment Gateway

**Profil Kasus:** Sistem Core Banking mengalami kegagalan deployment Terraform saat mencoba memigrasikan arsitektur jaringan lama ke arsitektur zero-trust menggunakan Security Group saling mengunci (*mutual reference*).

**Masalah:** Dua node Microservice ($Service_A$ dan $Service_B$) harus dapat saling berkomunikasi secara aman melalui port database. Insinyur mendefinisikan Security Group A yang merujuk pada Security Group B, dan Security Group B merujuk pada Security Group A langsung di dalam deklarasi utama masing-masing resource.

```hcl
# KODE BERMASALAH (ANTI-PATTERN):
resource "aws_security_group" "sg_a" {
  name = "sg_service_a"
  vpc_id = var.vpc_id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.sg_b.id] # Relasi ke B
  }
}

resource "aws_security_group" "sg_b" {
  name = "sg_service_b"
  vpc_id = var.vpc_id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.sg_a.id] # Relasi ke A -> CYCLIC DEPENDENCY!
  }
}
```

Saat dieksekusi, pipeline CI/CD langsung gagal pada fase kompilasi:
`Error: Cycle: aws_security_group.sg_a, aws_security_group.sg_b`

### Solusi Arsitektur Produksi (Edge Splitting Technique)

Untuk memecahkan dependency cycle tanpa mengorbankan standar keamanan, dependency graph harus didekonstruksi menggunakan teknik **Edge Splitting**. Resource Security Group dideklarasikan murni sebagai kontainer kosong (*skeleton nodes*), sementara aturan ingress dan egress dipisahkan menjadi *discrete edge nodes* menggunakan `aws_security_group_rule`.

```hcl
# KODE PERBAIKAN ENTERPRISE (EDGE SPLITTING):
# File: enterprise_fix/security_groups.tf

# 1. Deklarasi Container SG Murni (Tidak ada inter-dependency antar node SG)
resource "aws_security_group" "sg_a" {
  name_prefix = "payment-service-a-"
  description = "Security group for Payment Core Service A"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "sg_b" {
  name_prefix = "payment-service-b-"
  description = "Security group for Ledger Database Service B"
  vpc_id      = var.vpc_id

  lifecycle {
    create_before_destroy = true
  }
}

# 2. Pemisahan Edge Ingress A -> Membaca ID B (Terjadi setelah node SG A & B dibuat)
resource "aws_security_group_rule" "ingress_a_from_b" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.sg_a.id
  source_security_group_id = aws_security_group.sg_b.id
}

# 3. Pemisahan Edge Ingress B -> Membaca ID A
resource "aws_security_group_rule" "ingress_b_from_a" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.sg_b.id
  source_security_group_id = aws_security_group.sg_a.id
}
```

```
HASIL RESOLUSI GRAF SETELAH EDGE SPLITTING:
===========================================
    [aws_security_group.sg_a]       [aws_security_group.sg_b]
              │          ▲             │          ▲
              │          │             │          │
              │          └──────┐      │          │
              ▼                 │      ▼          │
    [rule: ingress_a_from_b]────┘   [rule: ingress_b_from_a]
```
Siklus diputus karena dependency diarahkan ke layer di bawah resource container utama. DAG dapat dieksekusi secara deterministik.

---

## 9. Trade-offs

Setiap perubahan konfigurasi lifecycle dan graph execution membawa konsekuensi teknis yang harus dievaluasi:

| Strategi / Konfigurasi | Keuntungan (Pros) | Biaya & Risiko (Cons / Trade-offs) | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- |
| **`create_before_destroy = true`** | Menghilangkan *application downtime* saat resource harus di-replace. | Mengharuskan penggunaan `name_prefix` (tidak bisa menggunakan fixed name); kuota resource di cloud berlipat ganda sementara waktu; risiko kegagalan propagasi (*CBD propagation error*). | Layer komputasi, Launch Template, Target Groups, SSL/TLS Certificates. |
| **`prevent_destroy = true`** | Proteksi mutlak terhadap *accidental deletion* pada resource stateful kritis. | Menghambat otomatisasi pipeline CI/CD saat resource benar-benar perlu diganti (*architectural change*); memerlukan modifikasi kode manual untuk melepas guard. | Production RDS, KMS Keys, S3 Data Lake, Stateful Storage. |
| **`ignore_changes = [...]`** | Mencegah konflik modifikasi (*drift wars*) antara Terraform dan kontrol bidang cloud eksternal (Autoscaler, Kube-controller). | Membutakan visibilitas Terraform terhadap *security drift* manual yang terjadi langsung di konsol cloud; konfigurasi state terancam usang. | HPA managed fields, Dynamic Tags, CloudWatch generated auto-scaling bounds. |
| **High Parallelism (`-parallelism=50`)** | Mengakselerasi eksekusi graf Terraform drastis pada arsitektur skala ribuan resource. | Mempercepat pencapaian kuota API rate limit (*429 Too Many Requests / ThrottlingException*); meningkatkan konsumsi CPU & memori sistem executor CI/CD. | Refresh-only jobs pada state masif tanpa batch API mutasi berat. |
| **Low Parallelism (`-parallelism=3`)** | Meredam *throttling API*, meminimalkan lonjakan resource execution engine. | Eksekusi pipeline sangat lambat, bottleneck durasi pipeline delivery produk. | Provider cloud dengan kuota API sangat restriktif (misal: VMware vSphere, Azure Classic). |

---

## 10. Common Mistakes & Troubleshooting

### 1. Naming Collision saat Menerapkan CBD
* **Symptom:** Eksekusi `terraform apply` gagal dengan pesan `BucketAlreadyExists` atau `ResourceAlreadyExistsException` saat me-replace resource.
* **Root Cause:** Resource menggunakan atribut `name = "static-api-resource"` bersamaan dengan `create_before_destroy = true`. Terraform Core mencoba membuat resource baru dengan nama statis yang sama **sebelum** menghancurkan resource lama.
* **Solusi Perbaikan:** Selalu ganti atribut `name` menjadi `name_prefix` jika CBD diaktifkan:
  ```hcl
  # SALAH
  name = "prod-elb"

  # BENAR
  name_prefix = "prod-elb-"
  ```

### 2. The Transitive CBD Violation (Propagasi CBD Terputus)
* **Symptom:** Pipeline crash dengan pesan:
  `Error: Invalid create_before_destroy cycle: aws_instance.worker -> aws_security_group.worker`
* **Root Cause:** Resource anak mengaktifkan `create_before_destroy = true`, namun resource induk yang direferensikannya masih menggunakan konfigurasi default (`destroy-then-create`).
* **Solusi Perbaikan:** Jalankan propagasi topologis CBD. Seluruh rantai dependensi yang mengarah ke resource yang dimutasi harus diberikan blok `create_before_destroy = true`.

### 3. False Dependency via Data Source Read
* **Symptom:** Rencana mutasi resource mengeksekusi refresh data source yang bergantung pada output resource yang sedang di-apply, menyebabkan status `computed attributes cannot be resolved during plan`.
* **Root Cause:** Mengambil atribut runtime resource melalui `data` source dalam workspace yang sama alih-alih mengonsumsi direct resource attributes.
* **Solusi Perbaikan:** Hindari anti-pattern membaca resource sendiri menggunakan blok `data`. Gunakan langsung `aws_resource_type.name.attribute`.

### Diagram Debugging Graf Alur Kerja
```
[Pipeline Failed: Cycle or CBD Error]
                  │
                  ▼
[Eksekusi Visualisasi Graf Lokal]
  $ terraform graph -type=plan | dot -Tpng > graph.png
                  │
                  ▼
[Pemeriksaan Trace Log Detail]
  $ export TF_LOG=TRACE
  $ export TF_LOG_PATH="tf-trace.log"
  $ terraform plan
                  │
                  ▼
[Analisis Pola Dependensi]
  1. Cari kata kunci: "Graph walk error"
  2. Cari entri mutasi: "transitive reduction"
  3. Identifikasi rantai dependensi sirkular (A -> B -> A)
                  │
                  ▼
[Resolusi Kode]
  - Terapkan Edge Splitting
  - Konfigurasi name_prefix
  - Harmonisasikan create_before_destroy pada rantai dependensi
```

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum melakukan merge Pull Request ke branch utama infrastruktur (`main`/`prod`):

- [ ] **Prefix Naming Standard:** Tidak ada resource dengan deklarasi nama statis (`name = "..."`) jika resource tersebut memiliki lifecycle `create_before_destroy = true`. Gunakan `name_prefix`.
- [ ] **CBD Chain Audit:** Setiap resource yang memiliki dependensi implisit/eksplisit terhadap resource ber-CBD juga harus mengaktifkan `create_before_destroy = true`.
- [ ] **Stateful Isolation:** Seluruh resource kritis penyimpanan data (RDS, DocumentDB, S3, Elasticache, EBS Volumes) memiliki proteksi `prevent_destroy = true`.
- [ ] **Drift Filtering:** Seluruh atribut yang dimodifikasi oleh sistem autonomus runtime (misal: Kubernetes HPA, AWS ASG auto-scaling target metric) didaftarkan ke dalam array `ignore_changes`.
- [ ] **No Deadlock Depends On:** Tidak ada penggunaan meta-argument `depends_on` untuk menyelesaikan isu keterlambatan propagasi runtime (misal: menunggu IAM role aktif). Gunakan mekanisme health checks, synthetic waiter resources, atau decoupling module.
- [ ] **Parallelism Baseline:** Pengujian beban pipeline produksi menggunakan default batasan `-parallelism=10` kecuali telah divalidasi tidak melanggar Cloud API Quota.
- [ ] **Graph Complexity Management:** Workspace tidak menampung lebih dari 500 node resource independen. Gunakan Terraform State Stacks atau arsitektur multi-state modular untuk mencegah penurunan performa kompilasi graf.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan mempraktikkan proses identifikasi cyclic dependency dan mengonversi arsitektur pembaruan instance berisiko downtime menjadi arsitektur rolling replacement berbasis CBD.

Simpan seluruh file praktik ini pada direktori: `hands-on/m02/`

### Task 1: Mereproduksi dan Mengatasi Cyclic Dependency

Buat direktori dan struktur file:
```bash
mkdir -p hands-on/m02/task1
cd hands-on/m02/task1
```

Tulis file `broken_graph.tf`:
```hcl
# hands-on/m02/task1/broken_graph.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

resource "null_resource" "service_mesh_controller" {
  triggers = {
    envoy_gateway_id = null_resource.envoy_gateway.id
  }
}

resource "null_resource" "envoy_gateway" {
  triggers = {
    controller_address = null_resource.service_mesh_controller.id
  }
}
```

Uji reproduksi error graf:
```bash
terraform init
terraform plan
```
*Output yang diharapkan:* Error: Cycle: `null_resource.service_mesh_controller, null_resource.envoy_gateway`

Buat file perbaikan `fixed_graph.tf`:
```hcl
# hands-on/m02/task1/fixed_graph.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

# Node Induk: Shared Configuration State
resource "null_resource" "mesh_cluster_config" {
  triggers = {
    cluster_version = "v1.30.0"
  }
}

# Node Anak 1: Bergantung pada Shared Config
resource "null_resource" "service_mesh_controller" {
  triggers = {
    cluster_id = null_resource.mesh_cluster_config.id
  }
}

# Node Anak 2: Bergantung pada Shared Config (Siklus Terputus)
resource "null_resource" "envoy_gateway" {
  triggers = {
    cluster_id = null_resource.mesh_cluster_config.id
  }
}
```

Jalankan validasi perbaikan:
```bash
rm broken_graph.tf
terraform plan
terraform apply --auto-approve
```

Visualisasikan DAG yang telah diperbaiki:
```bash
terraform graph | dot -Tsvg > fixed_graph.svg
```

### Task 2: Implementasi Zero-Downtime Dynamic Inversion (CBD Implementation)

Buat direktori baru:
```bash
mkdir -p ../task2
cd ../task2
```

Tulis file `rolling_deploy.tf`:
```hcl
# hands-on/m02/task2/rolling_deploy.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }
}

variable "application_payload" {
  type    = string
  default = "PAYLOAD_V1"
}

# Resource Storage yang mensimulasikan deployment aplikasi
resource "local_file" "release_artifact" {
  content  = var.application_payload
  # Penamaan unik untuk memfasilitasi CBD tanpa tumpang tindih file
  filename = "${path.module}/build/artifact_${var.application_payload}.bin"

  lifecycle {
    create_before_destroy = true
  }
}

# Router pointer: Bergantung pada artifact rilis
resource "local_file" "symlink_pointer" {
  content  = "ACTIVE_TARGET -> ${local_file.release_artifact.filename}"
  filename = "${path.module}/build/active_pointer.txt"

  lifecycle {
    create_before_destroy = true
    replace_triggered_by = [
      local_file.release_artifact.content
    ]
  }
}
```

Jalankan instansiasi V1:
```bash
terraform init
terraform apply -var="application_payload=PAYLOAD_V1" --auto-approve
cat build/active_pointer.txt
```

Lakukan rotasi zero-downtime ke V2:
```bash
terraform apply -var="application_payload=PAYLOAD_V2" --auto-approve
cat build/active_pointer.txt
```

Periksa log perubahan untuk mengonfirmasi bahwa artifact V2 dibuat **sebelum** artifact V1 dihapus:
```bash
ls -la build/
```

---

## 13. Exercise

### Level: Easy
Diberikan konfigurasi auto-scaling group yang sering ter-trigger update in-place akibat integrasi tool keamanan pihak ketiga yang menambahkan tag dinamis pada virtual machine secara otomatis:
* **Tugas:** Definisikan lifecycle argument agar perubahan tags dengan key `SecScanTimestamp` dan `SecScanStatus` diabaikan secara total oleh Terraform, tanpa mengabaikan penambahan tag manual dari engineer.

### Level: Medium
Diberikan dependency loop antara AWS Lambda Function dan S3 Bucket Notification:
* S3 Bucket memerlukan resource `aws_s3_bucket_notification` yang merujuk pada ARN AWS Lambda.
* Lambda Permission (`aws_lambda_permission`) membutuhkan ARN S3 Bucket sebagai `source_arn`.
* Pembuatan S3 Bucket utama membutuhkan deklarasi awal permission.
* **Tugas:** Rekonstruksi dependency graph tersebut ke dalam arsitektur yang valid menggunakan HCL murni, sehingga tidak memicu cycle error ataupun missing target ARN selama proses *first-time provisioning*.

### Level: Hard
Rancang deklarasi arsitektur multi-region mutual KMS Key replication policy:
* Region A memiliki Primary KMS Key, Region B memiliki Replica KMS Key.
* Primary Key Policy di Region A membutuhkan referensi ARN dari Replica Key di Region B untuk delegasi enkripsi silang.
* Replica Key di Region B membutuhkan Primary Key ARN saat inisialisasi awal.
* **Tugas:** Gunakan kombinasi `aws_kms_key`, pemisahan resource `aws_kms_key_policy`, direktif `create_before_destroy = true`, dan dynamic lifecycle triggers untuk memutus siklus enkripsi silang tanpa membiarkan key beroperasi tanpa policy akses yang aman dalam kondisi parsial.

---

## 14. Challenge

### Studi Kasus: High-Frequency Blue-Green VPC Peering Zero-Traffic Drop Challenge

**Konteks Arsitektural:**
Perusahaan perbankan Anda menggunakan strategi Blue-Green deployment pada tingkatan seluruh Core VPC Infrastruktur. Setiap 3 minggu, VPC baru di-deploy berdampingan dengan VPC lama. Seluruh traffic production dialihkan melalui inter-VPC Peering Connection yang terhubung ke Central Shared Services Transit VPC.

**Spesifikasi Persyaratan:**
1. State lama (`VPC_Blue`) dan State baru (`VPC_Green`) berada di bawah manajemen Terraform yang sama untuk proses orkestrasi transisi.
2. Proses pergantian VPC Peering Route Table Entries **tidak boleh** mengalami downtime atau rute terputus: Rute VPC Green harus online dan berstatus active di Peering Connection **sebelum** Rute VPC Blue dimatikan.
3. Terjadi naming conflict yang ketat pada Private DNS Namespace AWS Route53 Resolver (`corp.internal`), di mana hanya boleh ada satu VPC Association untuk namespace tersebut pada satu waktu, atau sistem harus melakukan swapping secara presisi dengan transisi CBD.
4. Anda dilarang membagi konfigurasi menjadi dua kali run pipeline terpisah. Semuanya harus dieksekusi dalam **satu kali invocation** `terraform apply`.

**Tantangan Eksekusi:**
* Susun kode arsitektur Terraform yang mengimplementasikan manipulasi graf penuh, CBD propagation, edge inversion, dan synthetic data barrier dependencies.
* Buktikan bahwa urutan topologis penghancuran VPC lama dieksekusi pada urutan paling akhir setelah verifikasi routing transit selesai dilakukan.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda & Konseptual Singkat)

1. Kapan tepatnya Terraform Core mendeteksi dependensi sirkular (Cycle Error)?
   * A. Saat membaca cloud API provider pada fase apply.
   * B. Saat fase runtime downloading provider plugins.
   * C. Saat kompilasi Abstract Syntax Tree (AST) dan topological sorting sebelum perutean RPC provider.
   * D. Setelah seluruh resource selesai di-destroy.

2. Apa yang terjadi jika resource dideklarasikan dengan `prevent_destroy = true`, namun rencana eksekusi menghasilkan aksi replacement (`-/+`)?
   * A. Terraform akan membuat resource baru, lalu mempertahankan resource lama tanpa menghapusnya.
   * B. Terraform Core membatalkan eksekusi pada planning stage dan melempar fatal error sebelum provider dipanggil.
   * C. Direktif `prevent_destroy` diabaikan jika aksinya adalah replacement bukan pure destroy.
   * D. Resource di-update secara in-place secara paksa.

3. Apa efek samping arsitektural jika Anda menambahkan `create_before_destroy = true` pada sebuah resource yang menggunakan atribut `name = "static-resource-production"`?
   * A. Resource lama otomatis di-rename menjadi `static-resource-production-old`.
   * B. Eksekusi apply gagal akibat naming collision karena resource baru mencoba mengambil nama yang masih aktif digunakan.
   * C. Terraform akan melakukan sleep selama 60 detik sebelum apply.
   * D. Cloud provider akan otomatis menghapus resource lama.

4. Flag CLI apa yang mengontrol jumlah maksimum goroutine worker yang mengeksekusi DAG secara serentak?
   * A. `-concurrency=N`
   * B. `-workers=N`
   * C. `-parallelism=N`
   * D. `-threads=N`

5. Fitur meta-argument lifecycle apa yang diperkenalkan pada Terraform v1.2 untuk memicu replacement otomatis saat resource lain mengalami update?
   * A. `triggered_by`
   * B. `replace_triggered_by`
   * C. `force_recreate_on`
   * D. `recreate_if_modified`

---

### Bagian 2: Intermediate (Analisis Kasus & Algoritma Graf)

6. Jelaskan apa yang dimaksud dengan proses *Transitive Reduction* pada DAG di Terraform Core dan mengapa proses ini penting bagi memori worker pool!
7. Analisis potongan kode berikut. Apakah blok ini valid atau akan melempar cycle error? Berikan alasan teknis berbasis graf:
   ```hcl
   resource "aws_subnet" "subnet_a" {
     vpc_id            = aws_vpc.main.id
     cidr_block        = "10.0.1.0/24"
     availability_zone = data.aws_availability_zones.available.names[0]
   }
   
   data "aws_availability_zones" "available" {
     state = "available"
     depends_on = [aws_vpc.main]
   }
   
   resource "aws_vpc" "main" {
     cidr_block = "10.0.0.0/16"
   }
   ```
8. Mengapa dependensi eksplisit (`depends_on`) yang merujuk pada keseluruhan modul (`module.network`) dianggap sebagai code smell / anti-pattern pada graf eksekusi skala besar?
9. Bagaimana Terraform Core menangani error partial failure (sebuah goroutine gagal di tengah eksekusi DAG, sementara goroutine paralel lainnya masih berjalan)?
10. Sebutkan aturan propagasi yang wajib dipenuhi ketika Resource X yang memiliki `create_before_destroy = true` menjadi dependensi bagi Resource Y!

---

### Bagian 3: Skenario Kasus Produksi

11. **Skenario Rate Limiting:**
    Sebuah tim platform merekayasa 1.200 microservice endpoints dalam satu file state. Saat `terraform apply` dijalankan, proses selalu crash di tengah jalan dengan error HTTP `429 Too Many Requests` dari AWS API Gateway, meskipun kuota soft limit akun cloud telah ditingkatkan.
    * *Pertanyaan:* Diagnosis kegagalan engine graf Terraform dalam konteks worker parallelism dan tentukan solusi arsitektur perbaikannya!

12. **Skenario Autoscaling Drift War:**
    Sebuah pipeline deployment web service selalu melakukan update pada resource `aws_ecs_service` dengan mengubah field `desired_count` kembali ke angka 3 setiap kali CI/CD jalan. Padahal, Application Auto Scaling (AAS) sedang menaikkan kapasitas instance menjadi 25 akibat lonjakan traffic kampanye promosi.
    * *Pertanyaan:* Konfigurasikan lifecycle argument yang menyelesaikan konflik state ini secara tepat tanpa menghilangkan kontrol Terraform terhadap konfigurasi container image!

13. **Skenario The Impossible Zero-Downtime Database Migration:**
    Database Subnet Group AWS RDS (`aws_db_subnet_group`) bersifat *immutable*. Mengubah daftar subnet di dalamnya akan memicu replacement wajib. Namun, database instance RDS yang aktif terikat langsung pada Subnet Group tersebut. Jika Anda mengaktifkan `create_before_destroy = true` pada DB Subnet Group, AWS melarang dua Subnet Group menggunakan kombinasi subnet yang saling tumpang tindih secara identik tanpa penamaan unik.
    * *Pertanyaan:* Bagaimana langkah-langkah dekonstruksi resource dan lifecycle manipulation untuk melakukan migrasi subnet RDS tanpa menghancurkan database engine utamanya?

---

### Kunci Jawaban & Panduan Evaluasi

#### Bagian 1: Basic
1. **C:** Deteksi dependensi sirkular dilakukan secara statis oleh Terraform Core saat fase pembentukan DAG sebelum eksekusi dimulai.
2. **B:** `prevent_destroy` bertindak sebagai guard rail di fase planning; jika aksi diff adalah replacement (yang melibatkan pemusnahan), Terraform melempar error fatal dan membatalkan plan.
3. **B:** Terjadi tabrakan penamaan (*naming collision*) di level provider karena resource baru diciptakan sebelum yang lama dimusnahkan.
4. **C:** Flag `-parallelism=N` mengontrol jumlah pekerja concurrent di engine graf (nilai default adalah 10).
5. **B:** `replace_triggered_by` adalah meta-argument resmi sejak Terraform v1.2+.

#### Bagian 2: Intermediate
6. **Transitive Reduction:** Algoritma yang memangkas direct edge yang redundan (misal: jika $A \to B$ dan $B \to C$, maka edge langsung $A \to C$ dihapus). Ini penting untuk mencegah thread pool mengalokasikan dependency lock ganda yang membebani sinkronisasi goroutine channel.
7. **Valid:** Konfigurasi tersebut valid dan tidak memiliki cycle. Rantai dependensinya linear: `aws_vpc.main` dievaluasi lebih dulu, diikuti oleh data source `aws_availability_zones`, dan terakhir `aws_subnet.subnet_a`.
8. **Anti-pattern `depends_on` Modul:** Menambahkan dependensi pada seluruh modul memaksa Terraform Core membuat edge dari **seluruh** resource di dalam modul target ke seluruh resource di modul pemanggil. Hal ini melumpuhkan konkurensi DAG dan menurunkan performa eksekusi secara drastis.
9. **Penanganan Partial Failure:** Terraform Core mengirimkan sinyal pembatalan konteks (`context.Cancel()`) ke seluruh goroutine yang masih berjalan. Resource yang sedang diproses oleh cloud API dibiarkan selesai, tetapi node turunan di graf ditandai sebagai *cancelled*. State yang telah sukses termutasi segera disimpan secara atomik ke state file.
10. **Aturan Propagasi CBD:** Jika Resource X mengaktifkan CBD, maka setiap Resource Y yang bergantung pada X (`Y -> X`) **harus** turut mengaktifkan `create_before_destroy = true` guna menghindari invalid dependency deadlocks.

#### Bagian 3: Skenario Kasus Produksi
11. **Solusi Rate Limiting:**
    * *Diagnosis:* DAG mengarahkan 1.200 node independen ke worker pool secara serentak. Dengan `-parallelism=10` atau lebih, burst request TCP membanjiri API endpoint hingga melampaui token bucket rate limit cloud provider.
    * *Perbaikan:* Turunkan konkurensi graf menggunakan parameter runtime execution `terraform apply -parallelism=3` secara sementara. Untuk jangka panjang, dekonstruksi file state raksasa tersebut menjadi multiple isolated workspace/state files menggunakan arsitektur Domain-Driven State (misal: terbagi per domain fungsional microservice).
12. **Solusi Autoscaling Drift War:**
    Tambahkan blok `lifecycle` pada resource `aws_ecs_service` yang berisi:
    ```hcl
    lifecycle {
      ignore_changes = [
        desired_count,
        task_definition # jika task definition dimutasi oleh continuous deployment tools eksternal
      ]
    }
    ```
    Ini memungkinkan orkestrator eksternal (AAS) mengendalikan kapasitas secara bebas tanpa ditimpa kembali oleh nilai HCL awal.
13. **Solusi Migrasi DB Subnet Group:**
    1. Tambahkan `name_prefix = "rds-sub-grp-"` dan `lifecycle { create_before_destroy = true }` pada deklarasi `aws_db_subnet_group`.
    2. Pisahkan keterikatan langsung instance RDS dengan mengizinkan pembuatan temporary Subnet Group baru yang mencakup subnet cadangan.
    3. Update resource `aws_db_instance` untuk menunjuk ke subnet group baru (ini merupakan operasi in-place update di AWS).
    4. Setelah pointing database berhasil dialihkan ke group baru, Terraform Core secara aman akan menghancurkan subnet group lama di ujung eksekusi DAG.

---

## 16. Summary

1. **Inti dari Terraform adalah Dependency Graph:** Setiap file konfigurasi HCL diterjemahkan menjadi *Directed Acyclic Graph* (DAG). Efisiensi, kecepatan, dan keberhasilan eksekusi infrastruktur sepenuhnya bergantung pada kebersihan topologi relasi antar node dalam graf ini.
2. **Kompilasi Graf Bersifat Multitahap:** Terraform Core melakukan validasi, cycle check (deteksi siklus), dan transitive reduction untuk merampingkan graf sebelum memecahnya ke dalam antrean eksekusi multi-threaded yang dikendalikan oleh worker pool concurrency (`-parallelism`).
3. **Lifecycle Directives adalah Compiler Interceptors:** Blok `lifecycle` bukan sekadar konfigurasi pasif, melainkan instruksi yang mengubah topologi graf itu sendiri:
   * `create_before_destroy` membalik urutan dependensi node pengganti.
   * `prevent_destroy` menyuntikkan pre-execution assertion di level graph planning.
   * `ignore_changes` memfilter data diff sebelum masuk ke tahap persetujuan eksekusi.
   * `replace_triggered_by` menyuntikkan synthetic edge yang merespons perubahan node eksternal secara reaktif.
4. **Resiliensi Tingkat Produksi Memerlukan Disiplin Graf:** Penggunaan `name_prefix`, pemecahan dependensi melingkar via *Edge Splitting*, isolasi arsitektural state berukuran besar, serta propagasi CBD yang disiplin merupakan fondasi wajib dalam membangun otomasi infrastruktur enterprise yang zero-downtime, deterministik, dan bebas kegagalan runtime.