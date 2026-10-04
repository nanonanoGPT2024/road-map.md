# Bab 03: Compute Architecture & Elastic Scaling

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengartikulasikan arsitektur internal **AWS Nitro System** (Nitro Card, Nitro Security Chip, Nitro Hypervisor) serta implikasinya terhadap performa I/O, latensi, dan isolasi keamanan komputasi.
- Memilih instance family (General Purpose, Compute Optimized, Memory Optimized, Storage Optimized, Accelerated Computing) dan mikroarsitektur (x86_64 vs. AWS Graviton ARM Neoverse) berdasarkan profil beban kerja secara matematis dan analitis.
- Mengonfigurasi dan mengoperasikan **Auto Scaling Groups (ASG)** menggunakan **Launch Templates** dengan strategi **Mixed Instances Policy** yang memadukan On-Demand dan Spot Instances berbasis strategi alokasi modern (`price-capacity-optimized`).
- Mengotomatisasi penanganan transisi siklus hidup komputasi menggunakan **ASG Lifecycle Hooks** dan EventBridge untuk graceful shutdown/draining koneksi.
- Mengelola armada instans tanpa SSH terbuka via **AWS Systems Manager (SSM) Fleet Manager** dan **Session Manager**.
- Menghitung Trade-off biaya vs. ketersediaan dan merancang arsitektur komputasi nir-downtime yang elastis terhadap lonjakan lalu lintas ekstrem maupun interupsi Spot.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Fondasi Jaringan AWS: VPC, Subnetting (Public vs. Private), Route Tables, Security Groups, dan Network ACLs.
- Dasar Linux System Administration: POSIX signals (`SIGTERM`, `SIGKILL`), systemd service management, arsitektur CPU (registers, cache line, threads/cores), serta manajemen memori Linux (page cache, swap, OOM killer).
- Konsep dasar IaC (Infrastructure as Code) menggunakan Terraform (HCL) atau AWS CLI v2.
- Teori dasar containerization (OCI standards, Docker runtime) dan interaksi kernel namespaces/cgroups.

---

## 3. Concept
Komputasi awan modern telah bergeser dari sekadar "penyewaan virtual machine konvensional" menjadi orkestrasi kapasitas elastis berskala terdistribusi. Fondasi komputasi Amazon Elastic Compute Cloud (EC2) bertumpu pada dekonstruksi virtualisasi tradisional menggunakan perangkat keras terakselerasi (**AWS Nitro System**) dan diversifikasi arsitektur silikon (**AWS Graviton**).

Di atas fondasi perangkat keras ini, elastisitas komputasi dikelola melalui abstraksi deklaratif:
1. **Launch Template**: Blueprint spesifikasi instans (AMI, instance type, storage volume mapping, IAM role, network interface, bootstrap user data).
2. **Auto Scaling Group (ASG)**: Pengendali status armada komputasi (target capacity, minimum/maximum size, AZ balance, dynamic/target tracking scaling policies, lifecycle state transitions).
3. **Fleet Allocation Policy**: Algoritma cerdas alokasi Spot dan On-Demand pools untuk meminimalkan risiko interupsi kapasitas sekaligus mengoptimalkan efisiensi biaya (*unit economics*).
4. **Agent-driven Management**: Pengelolaan operasional instans secara headless melalui AWS Systems Manager (SSM) Agent, mengeliminasi kebutuhan bastion host dan inbound port 22.

---

## 4. Why
Virtualisasi generasi lawas (berbasis software hipervisor Xen murni) memotong 10% hingga 30% performa CPU dan I/O host fisik untuk overhead emulasi perangkat keras (dom0). Ketika aplikasi terdistribusi menuntut ratusan ribu IOPS, latensi jaringan sub-milidetik, dan scaling seketika saat lonjakan trafik, virtualisasi tradisional mengalami bottleneck performa dan biaya.

Dengan mengadopsi Nitro System, Graviton ARM, dan elastisitas terorkestrasikan:
- **Zero Hypervisor Jitter**: Beban I/O (jaringan, disk NVMe, sistem keamanan) didelegasikan sepenuhnya ke ASIC Nitro Cards khusus; 100% core CPU dan RAM server fisik didedikasikan untuk beban kerja pengguna.
- **Superior Price-Performance**: Prosesor Graviton3/Graviton4 berbasis ARM64 menawarkan efisiensi energi tinggi dan rasio performa-ke-biaya hingga 40% lebih baik dibanding prosesor x86-64 setara untuk beban kerja web, database, dan container.
- **Cost Reduction Hingga 90%**: Pemanfaatan EC2 Spot Instances melalui strategi diversifikasi pool otomatis memungkinkan running batch processing, stateless web services, dan worker nodes Kubernetes dengan biaya fraksional tanpa mengorbankan Service Level Objective (SLO).
- **Hardened Security Posture**: Isolasi fisik mutlak melalui Nitro Security Chip, tidak ada akses root/operator AWS ke memori instans, serta manajemen remote terenkripsi via IAM-controlled SSM.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Arsitektur AWS Nitro System
Nitro System memecah fungsi hipervisor monolitik menjadi modul-modul modular berbasis perangkat keras PCI-e:

```
+-----------------------------------------------------------------------+
|                             EC2 Host Server                           |
|  +-----------------------------------------------------------------+  |
|  |                 Core Compute (x86_64 / Graviton)                |  |
|  |   Instance A (vCPU, RAM)              Instance B (vCPU, RAM)    |  |
|  +-----------------------------------------------------------------+  |
|  +-----------------------------------------------------------------+  |
|  |                      Nitro Hypervisor (KVM-based)               |  |
|  |          (Hanya alokasi core & memori, zero I/O interception)   |  |
|  +-----------------------------------------------------------------+  |
|          | PCIe                     | PCIe                 | PCIe     |
+----------|--------------------------|----------------------|----------+
           v                          v                      v
   +---------------+          +---------------+      +---------------+
   |  Nitro Card   |          |  Nitro Card   |      |  Nitro Card   |
   |   for VPC     |          |   for EBS     |      |  for Storage  |
   | (ENA Engine,  |          | (NVMe Engine, |      | (Local NVMe   |
   | Encrypt/Flow) |          | Hardware Enc) |      | Controller)   |
   +---------------+          +---------------+      +---------------+
           |                          |                      |
           +--------------------------+----------------------+
                                      v
                      +-------------------------------+
                      |      Nitro Security Chip      |
                      | (Hardware Root of Trust, TPM) |
                      +-------------------------------+
```

1. **Nitro Card for VPC**: Menyediakan Elastic Network Adapter (ENA) controller, pemrosesan enkripsi jaringan IPsec/TLS hardware, dan penegakan Security Group secara kawat (wire-speed).
2. **Nitro Card for EBS**: Controller NVMe berbasis ASIC hardware yang menghubungkan instance ke volume Amazon EBS via jaringan terisolasi berkecepatan tinggi.
3. **Nitro Card for Storage**: Menangani SSD NVMe lokal instance store dengan enkripsi hardware transparan.
4. **Nitro Security Chip**: Mengontrol firmware flash, memvalidasi integritas bootloader hardware (Root of Trust), dan mematikan fungsi tulis ke firmware saat CPU utama aktif.
5. **Nitro Hypervisor**: Hipervisor minimalis berbasis KVM (Kernel-based Virtual Machine) yang tugasnya terbatas pada isolasi partisi memori dan alokasi vCPU thread.

### 5.2 Taksonomi Instance Families
AWS mengelompokkan EC2 berdasarkan rasio vCPU-ke-Memory:

| Family | Huruf | Rasio Mem:vCPU | Target Karakteristik Beban Kerja |
| :--- | :--- | :--- | :--- |
| **General Purpose** | `M`, `T` | 4:1 (GiB per vCPU) | Web server, dev env, low-to-medium relational DB. T-series memiliki burst credit mechanism. |
| **Compute Optimized** | `C` | 2:1 | High-performance web servers, batch processing, video encoding, microservices compute-heavy. |
| **Memory Optimized** | `R`, `X`, `z` | 8:1 hingga 32:1 | In-memory cache (Redis), High-performance RDBMS, distributed analytics (Apache Spark). |
| **Storage Optimized** | `I`, `D`, `H` | Bervariasi + high NVMe IOPS/density | NoSQL distributed datastores (Cassandra, ScyllaDB), ElasticSearch, Hadoop HDFS. |
| **Accelerated Computing**| `P`, `G`, `Trn`, `Inf` | GPU/ASIC specialized | Deep Learning training/inference, 3D graphics rendering, computer vision. |

*Suffix Nomenklatur*: 
- `c` = Graviton (ARM)
- `i` = Intel Xeon
- `a` = AMD EPYC
- `n` = Network optimized (hingga 100Gbps+)
- `e` = Extra storage/memory
- `d` = Direct-attached local NVMe SSD

### 5.3 AWS Graviton Architecture & Neoverse Core
AWS Graviton dirancang menggunakan arsitektur ARM 64-bit (ARMv8.5-A pada Graviton3, ARMv9 pada Graviton4). 
Perbedaan arsitektur fundamental dengan x86:
- **vCPU = 1 Physical Core**: Pada x86 (Intel/AMD), 1 vCPU adalah 1 Simultaneous Multi-Threading (SMT / Hyperthread) logical core. Pada Graviton, **1 vCPU adalah 1 dedicated physical core penuh** dengan L1/L2 cache privat. Tidak ada resource-sharing antar-thread pada core yang sama, memusnahkan vulnerability kelas *side-channel cache attack* (Spectre/Meltdown) dan fluktuasi performa (noisy neighbor).
- **DDR5 Memory Channels**: Graviton3/4 mendukung arsitektur multi-channel DDR5 dengan bandwidth memori 50% lebih tinggi dibandingkan sistem DDR4 konvensional.
- **Instruksi Khusus Vector/ML**: Bfloat16, SVE (Scalable Vector Extension), int8 dot-product acceleration.

### 5.4 Auto Scaling Group (ASG) Mechanics
ASG mempertahankan ketersediaan armada instans melalui konsep kontrol closed-loop:
1. **Capacity Boundaries**: `MinSize <= DesiredCapacity <= MaxSize`.
2. **Availability Zone Rebalancing**: ASG secara proaktif mempertahankan sebaran instans yang merata di seluruh subnet/AZ yang didaftarkan.
3. **Scaling Policies**:
   - **Target Tracking Scaling**: Menjaga metrik tertentu tetap konstan (misal: `ASGAverageCPUUtilization` pada 60% atau `ALBRequestCountPerTarget` pada 1000).
   - **Step Scaling**: Merespons breach CloudWatch alarms dalam beberapa threshold berundak (misal: jika CPU > 70% tambah 2 instans; jika CPU > 85% tambah 5 instans).
   - **Predictive Scaling**: Machine learning menganalisis pola historis metrik selama minimal 14 hari dan merencanakan scaling kapasitas 24-48 jam ke depan.

### 5.5 Mixed Instances Policy & Spot Allocation Strategies
Dalam production scale, ASG tidak boleh bergantung pada 1 jenis instance type atau 1 pricing model:
- **Base On-Demand Capacity**: Menjamin ketersediaan baseline instans non-preemptible.
- **Spot Allocation Strategy**:
  - `capacity-optimized`: Memilih pool instans yang memiliki ketersediaan kapasitas cadangan paling berlimpah di AWS backbone, meminimalkan frekuensi interupsi Spot.
  - `price-capacity-optimized` (*Recommended Best Practice*): Menyeimbangkan antara pool yang memiliki risiko interupsi rendah dengan harga paling optimal.
- **Spot Interruption Notice**: AWS memberikan notifikasi 2 menit via EventBridge / Instance Metadata Service (IMDS) `GET /latest/meta-data/spot/instance-action` sebelum instans dimatikan paksa.

### 5.6 ASG Lifecycle Hooks
Memungkinkan intervensi manual atau terprogram saat instans berpindah status:

```
[Pending] ------------> [Pending:Wait] ------------> [Pending:Proceed] ------------> [InService]
                              |                                  ^
                              +--- (Custom User Script/SSM) -----+
                                   (Kirim Heartbeat/Complete)

[InService] ----------> [Terminating:Wait] --------> [Terminating:Proceed] --------> [Terminated]
                              |                                  ^
                              +--- (Graceful Connection Drain) --+
                                   (Flush log, unregister target)
```

Jika timeout tercapai sebelum sinyal `CONTINUE` atau `ABANDON` dikirimkan, ASG mengeksekusi `DefaultResult`.

### 5.7 AWS Systems Manager (SSM) Fleet & Session Manager
Menggantikan kebutuhan Jumpbox / Bastion Host:
- SSM Agent berkomunikasi keluar (*outbound-only*) ke endpoint HTTPS SSM (TCP port 443). Tidak ada port inbound (port 22) yang dibuka pada Security Group.
- Autentikasi dan otorisasi menggunakan AWS IAM policies, terintegrasi penuh dengan log audit AWS CloudTrail.
- Session Manager mem-pipe I/O terminal secara end-to-end terenkripsi menggunakan TLS 1.3 dan AWS KMS Key.

---

## 6. How

### Alur Implementasi Compute Fleet Berkinerja Tinggi:
1. **Pembuatan Launch Template Modern**:
   - Tentukan AMI multi-arch (Graviton/x86).
   - Aktifkan IMDSv2 (*Instance Metadata Service Version 2*) dengan `HttpTokens=required` dan `HttpPutResponseHopLimit=1` untuk mitigasi SSRF.
   - Attach IAM Instance Profile dengan permission `AmazonSSMManagedInstanceCore`.
   - Konfigurasi EBS GP3 volume dengan throughput dan IOPS yang disesuaikan (independen dari ukuran kapasitas storage).
2. **Konfigurasi Auto Scaling Group**:
   - Definisikan Mixed Instances Policy: Kombinasi `c7g.large`, `c6g.large`, `c7a.large`, `c6i.large`.
   - Konfigurasi alokasi Spot: `price-capacity-optimized`.
   - Setup Target Tracking Scaling Policy terikat pada Custom Metric atau ALB Request Count.
3. **Pemasangan Lifecycle Hook Terminating**:
   - Terapkan hook untuk menangkap sinyal terminasi.
   - Jalankan script draining koneksi container, flushing database connections, dan eksekusi upload log sisa ke Amazon S3 atau CloudWatch Logs.

---

## 7. Analogy
Bayangkan Anda mengelola armada taksi logistik kota:
- **Xen Virtualization**: Sebuah truk besar yang disewa, namun 25% bak truk dihabiskan untuk tempat duduk dan perlengkapan mandor (software hypervisor) yang ikut mengawasi perjalanan.
- **AWS Nitro**: Truk modern di mana mandor dan seluruh alat navigasinya dipindahkan ke sepeda motor terpisah yang mendampingi truk (Nitro Cards). 100% bak truk kini bersih untuk muatan kargo Anda.
- **x86 Hyperthreading vs Graviton Physical Core**: Hyperthreading x86 ibarat 1 supir truk yang memegang 2 setir bergantian (jika salah satu tangan sibuk, tangan lain menunggu). Graviton ARM ibarat memberikan 2 supir independen di kabin ganda dengan kemudi masing-masing secara berdedikasi.
- **ASG with Spot & Mixed Instances**: Menyewa armada mobil tetap (On-Demand) untuk rute vital tak boleh putus, ditambah menyewa armada cadangan dengan tarif diskon 80% (Spot) dari sisa rental tak terpakai. Jika salah satu mobil rental diskon ditarik sewaktu-waktu oleh pemiliknya, sistem dispatched otomatis Anda (ASG) langsung menggantinya dengan jenis mobil terdekat yang masih tersedia di garasi lain.

---

## 8. Diagram (ASCII)

### Siklus Hidup Transisi Status ASG & Handling Interupsi Spot

```
                             +------------------------+
                             |  Scale-Out Triggered   |
                             |  (CloudWatch / Target) |
                             +------------------------+
                                         |
                                         v
                             +------------------------+
                             |     Pending State      |
                             +------------------------+
                                         |
                                         v
                         +-------------------------------+
                         | Lifecycle: EC2_INSTANCE_      |
                         | LAUNCHING (Pending:Wait)      |
                         +-------------------------------+
                                         |
                       +-----------------+-----------------+
                       | (Install deps / fetch secrets)    |
                       v                                   v
             [Timeout / ABANDON]                 [Complete: CONTINUE]
                       |                                   |
                       v                                   v
             [Terminate Instance]                 +-----------------+
                                                  |    InService    | <----+
                                                  +-----------------+      |
                                                           |               |
                         +---------------------------------+               |
                         |                                                 |
                         v                                                 |
         +--------------------------------+                                |
         | Scale-In / Spot Rebalance /    |                                |
         | Instance Health Check Failure  |                                |
         +--------------------------------+                                |
                         |                                                 |
                         v                                                 |
         +--------------------------------+                                |
         | Lifecycle: EC2_INSTANCE_       |                                |
         | TERMINATING (Terminating:Wait) |                                |
         +--------------------------------+                                |
                         |                                                 |
        +----------------+----------------+                                |
        |                                 |                                |
        v                                 v                                |
  [Heartbeat sent:                  [Graceful Drain:                       |
   Extend wait time]                - Sigterm app                          |
                                    - Deregister ALB target                |
                                    - Dump remaining metrics]              |
                                                  |                        |
                                                  v                        |
                                        [Complete: CONTINUE]               |
                                                  |                        |
                                                  v                        |
                                        +-------------------+              |
                                        |    Terminated     |              |
                                        +-------------------+              |
```

---

## 9. Simple Example
Contoh skrip bash sederhana untuk query Instance Metadata Service Version 2 (IMDSv2) secara aman guna memeriksa apakah instans ini sedang menerima notifikasi interupsi Spot (polling 5 detik):

```bash
#!/usr/bin/env bash
set -euo pipefail

# Ambil token IMDSv2 dengan TTL 60 detik
TOKEN=$(curl -sS -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60")

# Ambil instance-id saat ini
INSTANCE_ID=$(curl -sS -H "X-aws-ec2-metadata-token: $TOKEN" "http://169.254.169.254/latest/meta-data/instance-id")
echo "Monitoring Spot Action for Instance: ${INSTANCE_ID}"

# Polling spot action endpoint
HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" -H "X-aws-ec2-metadata-token: $TOKEN" "http://169.254.169.254/latest/meta-data/spot/instance-action")

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "[CRITICAL] Spot Interruption Notice Diterima! Memulai Graceful Shutdown..."
    ACTION_DETAILS=$(curl -sS -H "X-aws-ec2-metadata-token: $TOKEN" "http://169.254.169.254/latest/meta-data/spot/instance-action")
    echo "Detail Interupsi: ${ACTION_DETAILS}"
    # Trigger aplikasi untuk berhenti menerima trafik baru
    exit 0
else
    echo "[OK] Tidak ada interupsi Spot. Status komputasi stabil."
fi
```

---

## 10. Practical Example (Konfigurasi Terraform Komprehensif)

Arsitektur komputasi produksi: Auto Scaling Group berbasis AWS Graviton3 dengan Mixed Instances Policy, alokasi `price-capacity-optimized`, IAM Role untuk AWS Systems Manager, dan Terminating Lifecycle Hook.

```hcl
# --- compute_infrastructure.tf ---
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }
}

provider "aws" {
  region = "ap-southeast-1"
}

# 1. IAM Role untuk SSM Agent (Tanpa SSH Bastion)
resource "aws_iam_role" "ssm_instance_role" {
  name = "production-compute-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ssm_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "compute_profile" {
  name = "production-compute-instance-profile"
  role = aws_iam_role.ssm_instance_role.name
}

# 2. Security Group yang Sangat Ketat (Zero Inbound, Outbound Only ke VPC/SSM)
resource "aws_security_group" "compute_sg" {
  name        = "production-compute-sg"
  description = "No inbound SSH; egress only for SSM and application traffic"
  vpc_id      = "vpc-0123456789abcdef0" # Ganti dengan ID VPC Anda

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Environment = "production"
    Tier        = "compute"
  }
}

# 3. Launch Template dengan Graviton ARM AMI & Hardened IMDSv2
resource "aws_launch_template" "compute_lt" {
  name_prefix   = "prod-graviton-template-"
  image_id      = "ami-0c8a6669910d5ac91" # Amazon Linux 2023 ARM64 (ap-southeast-1)
  instance_type = "c7g.large"

  iam_instance_profile {
    arn = aws_iam_instance_profile.compute_profile.arn
  }

  network_interfaces {
    associate_public_ip_address = false
    security_groups             = [aws_security_group.compute_sg.id]
    delete_on_termination       = true
  }

  # Penegakan IMDSv2 Wajib (Cegah SSRF)
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  # Storage Configuration (EBS GP3 Modern)
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 30
      volume_type           = "gp3"
      iops                  = 3000
      throughput            = 125
      encrypted             = true
      delete_on_termination = true
    }
  }

  user_data = base64encode(<<-EOF
              #!/bin/bash
              echo "Bootstrapping Instance with Nitro & Graviton Optimization..."
              yum update -y
              # Konfigurasi worker atau aplikasi di sini
              EOF
  )

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name        = "prod-worker-node"
      Arch        = "arm64"
      Provisioner = "terraform"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

# 4. Auto Scaling Group dengan Mixed Instances Policy (Graviton Diversification)
resource "aws_autoscaling_group" "production_asg" {
  name_prefix         = "prod-compute-asg-"
  vpc_zone_identifier = ["subnet-0a1b2c3d4e5f67890", "subnet-0fedcba9876543210"] # Multi-AZ Subnets

  min_size         = 2
  max_size         = 20
  desired_capacity = 4

  capacity_rebalance = true # Proactive Spot replacement sebelum interupsi fisik

  mixed_instances_policy {
    instances_distribution {
      on_demand_base_capacity                  = 2
      on_demand_percentage_above_base_capacity = 20 # 80% sisanya menggunakan Spot
      spot_allocation_strategy                 = "price-capacity-optimized"
    }

    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.compute_lt.id
        version            = "$Latest"
      }

      # Diversifikasi Family Graviton untuk toleransi pool exhaustion
      override {
        instance_type     = "c7g.large"
        weighted_capacity = "1"
      }
      override {
        instance_type     = "c6g.large"
        weighted_capacity = "1"
      }
      override {
        instance_type     = "m7g.large"
        weighted_capacity = "1"
      }
      override {
        instance_type     = "m6g.large"
        weighted_capacity = "1"
      }
    }
  }

  lifecycle {
    create_before_destroy = true
    ignore_changes        = [desired_capacity] # Delegasikan ke scaling policy
  }
}

# 5. ASG Terminating Lifecycle Hook
resource "aws_autoscaling_lifecycle_hook" "terminating_hook" {
  name                   = "graceful-shutdown-hook"
  autoscaling_group_name = aws_autoscaling_group.production_asg.name
  default_result         = "CONTINUE"
  heartbeat_timeout      = 300 # 5 menit waktu draining
  lifecycle_transition   = "autoscaling:EC2_INSTANCE_TERMINATING"
}

# 6. Target Tracking Scaling Policy (CPU Utilization)
resource "aws_autoscaling_policy" "cpu_target_tracking" {
  name                   = "target-tracking-cpu-60"
  autoscaling_group_name = aws_autoscaling_group.production_asg.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = 60.0
  }
}
```

---

## 11. Real World Example
Sebuah marketplace e-commerce multinasional menangani lonjakan harian selama "Flash Sale" pukul 12.00 dan 00.00. Arsitektur lama mereka menggunakan instance x86 (`c5.2xlarge`) On-Demand statis sebanyak 100 instans dengan total pengeluaran komputasi harian mencapai $816/hari.

**Transformasi Arsitektur SRE**:
1. Migrasi runtime microservices (Go dan NodeJS OCI Containers) dari x86-64 ke AWS Graviton3 (`c7g.2xlarge`), menghasilkan peningkatan throughput sebesar 28% dan penurunan biaya instans per-jam sebesar 19%.
2. Implementasi Mixed Instances ASG dengan rasio:
   - On-Demand Base: 10 instans (menjaga ketersediaan core).
   - Dynamic Capacity: Spot Instances dengan alokasi `price-capacity-optimized` mendistribusikan node pada 4 varian tipe (`c7g.2xlarge`, `c6g.2xlarge`, `m7g.2xlarge`, `r7g.2xlarge`).
3. Integrasi Target Tracking Scaling (`ALBRequestCountPerTarget = 1200`) dan Predictive Scaling yang mem-pre-warm armada 30 menit sebelum event jam 12.00 dimulai.
4. Implementasi Lifecycle Hook dan Spot Rebalance Recommendation listener yang menguras status node (drain 30 detik) saat AWS memicu rebalance event.

**Hasil**:
- Pengeluaran berkurang dari $816/hari menjadi $228/hari (**penghematan 72%**).
- Zero packet loss atau 502 Bad Gateway selama event flash sale karena predictive pre-warming dan connection draining teruji.

---

## 12. Trade-offs

| Dimensi Arsitektur | Pilihan A | Pilihan B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Arsitektur Silikon** | x86_64 (Intel / AMD) | ARM64 (AWS Graviton) | x86 menawarkan kompatibilitas legacy mutlak (proprietary pre-compiled binaries tanpa source code). Graviton unggul 20-40% price-performance, namun menuntut cross-compilation pipeline OCI image (`linux/arm64`) dan validasi library C/assembly native. |
| **Pricing Model** | 100% On-Demand / Savings Plans | Mixed Instances (Spot + On-Demand) | 100% On-Demand sangat stabil dan bebas interupsi, namun biaya maksimal. Mixed Spot memotong biaya hingga 90%, tetapi arsitektur aplikasi wajib stateless, fault-tolerant, dan memiliki graceful termination lifecycle. |
| **Alokasi Spot** | `lowest-price` | `price-capacity-optimized` | `lowest-price` menghemat fraksi sen lebih banyak, tetapi rawan terkena interupsi massal serentak karena memilih pool terpadat. `price-capacity-optimized` sedikit lebih mahal (+2-5% dibanding lowest), namun menurunkan frekuensi interupsi Spot hingga >70%. |
| **Manajemen Akses** | Direct SSH (Port 22 + Bastion) | AWS Systems Manager (SSM) Session Manager | Direct SSH familiar bagi engineer lama, namun menciptakan single point of attack, pengelolaan SSH key pair yang kompleks, dan audit log manual. SSM berbasis HTTPS outbound, audit CloudTrail granular, namun memerlukan agen aktif dan koneksi ke endpoint SSM. |

---

## 13. When To Use
- **AWS Graviton**: Semua aplikasi berbasis open-source runtime modern (Java 11+, Go, Python, Node.js, Ruby, Rust, PHP), containerized microservices (EKS/ECS), distributed databases (MySQL, PostgreSQL, Redis, ScyllaDB).
- **Mixed Instances ASG**: Stateless web backend, queue consumer workers (SQS/Kafka consumers), background image/video renderers, AI model inference batch.
- **SSM Session Manager**: Seluruh armada VM di private subnet tanpa IP publik dan tanpa port inbound 22 terbuka ke internet maupun internal corporate network.

---

## 14. When NOT To Use
- **AWS Graviton**: Legacy third-party commercial enterprise software tertutup (COTS) yang hanya dikompilasi untuk target `x86_64` tanpa dukungan vendor untuk ARM.
- **Spot Instances**: Stateful single-node databases (Oracle Database, Microsoft SQL Server konvensional non-clustered), sistem legacy yang memerlukan waktu boot-up > 15 menit, aplikasi monolitik yang tidak dapat menangani interupsi mendadak dalam 2 menit.
- **EC2 Instance Store (Ephemeral)**: Penyimpanan database utama yang memerlukan persistensi absolut data saat instans di-stop atau di-reboot secara reguler.

---

## 15. Common Mistakes
1. **Mengabaikan IMDSv2**: Menggunakan IMDSv1 default yang rentan terhadap ekfiltrasi IAM instance role credential via celah Server-Side Request Forgery (SSRF) web application.
2. **Hardcoding 1 Instance Type pada Spot**: Mengonfigurasi ASG Spot hanya dengan 1 tipe instans (misal: hanya `c7g.large`). Saat pool `c7g.large` di AZ tersebut mengalami lonjakan permintaan internal AWS, ASG gagal meluncurkan kapasitas baru (*InsufficientInstanceCapacity*).
3. **Mengabaikan Draining pada Load Balancer**: Mengabaikan deregistrasi target group dan ASG Lifecycle Hook. Ketika instans dimatikan, koneksi TCP klien yang sedang berjalan diputus paksa (`TCP RST`), menyebabkan lonjakan HTTP 502/504 errors.
4. **Menggunakan Burstable Instance (T-series) untuk Heavy Production Workload**: Menjalankan database transaksional berat di atas `t3/t4g` tanpa memahami habisnya CPU Credit, berujung pada CPU throttled di level 10-20% kapasitas saat credit habis (*baseline performance clamp*).
5. **Membuka Port 22 ke 0.0.0.0/0**: Mengizinkan SSH publik ke server produksi alih-alih menggunakan AWS Systems Manager Session Manager yang diamankan dengan IAM.

---

## 16. Best Practices

### Komputasi dan Arsitektur
- Aktifkan **IMDSv2** dengan hop limit = 1 pada seluruh Launch Templates (`HttpTokens=required`).
- Manfaatkan **Amazon EBS GP3** sebagai pengganti GP2. GP3 memisahkan performa IOPS (mulai dari 3,000 IOPS gratis) dan Throughput (125 MB/s gratis) terlepas dari ukuran disk.
- Selalu sediakan minimal 3 hingga 5 instance types variatif di dalam ASG Mixed Instances Policy (contoh: `c6g.xlarge`, `c7g.xlarge`, `m6g.xlarge`, `m7g.xlarge`).

### Reliability dan Keamanan
- Aktifkan fitur `capacity_rebalance = true` pada ASG. Fitur ini membaca notifikasi *EC2 Instance Rebalance Recommendation* (yang datang sebelum notifikasi 2 menit Spot Interruption) untuk meluncurkan pengganti instans sebelum instans lama dimatikan.
- Gunakan **AWS Systems Manager Session Manager** dikombinasikan dengan logging sesi ke CloudWatch Logs / S3 Bucket terenkripsi KMS untuk audit trail forensik penuh.
- Definisikan graceful termination script yang menangani sinyal `SIGTERM`, menghentikan polling tugas baru, menyelesaikan tugas yang sedang berjalan (*in-flight requests*), dan mengirim sinyal *CONTINUE* via AWS CLI/SDK.

---

## 17. Troubleshooting

### Problem 1: ASG Gagal Meluncurkan Instans Spot (*Capacity Exhaustion*)
- **Gejala**: CloudWatch Events memunculkan error `EC2 Spot Instance Request Failed` atau status ASG `InsufficientInstanceCapacity`.
- **Root Cause**: ASG hanya dikonfigurasi dengan 1 tipe instans pada pool yang ketersediaannya sedang kritis di Region/AZ tersebut.
- **Resolusi**: Ubah konfigurasi Mixed Instances Policy pada ASG. Tambahkan minimal 4 alternatif ukuran dan keluarga instans (misal gabungkan varian C, M, dan R) dan gunakan alokasi `price-capacity-optimized`.

### Problem 2: Session Manager Gagal Connect (*TargetNotConnected*)
- **Gejala**: Perintah `aws ssm start-session --target <instance-id>` gagal dengan error `TargetNotConnected`.
- **Root Cause**:
  1. Instans berada di private subnet tanpa rute keluar (NAT Gateway) atau tanpa VPC Endpoints untuk SSM (`ssm`, `ssmmessages`, `ec2messages`).
  2. IAM Instance Profile tidak memiliki managed policy `AmazonSSMManagedInstanceCore`.
  3. SSM Agent pada OS mati atau belum terinstall.
- **Resolusi**: Pasang VPC Interface Endpoints jika VPC terisolasi murni, atau pastikan Route Table private subnet mengarah ke NAT Gateway yang fungsional. Pastikan policy IAM sudah di-attach.

### Problem 3: HTTP 502 Spike Saat ASG Scale-In
- **Gejala**: Saat trafik menurun dan ASG mematikan instans, monitoring ALB menangkap lonjakan respons HTTP 502 Bad Gateway.
- **Root Cause**: Instans dihentikan sebelum Application Load Balancer selesai menguras koneksi aktif (*connection draining*), atau durasi deregistrasi target group lebih panjang daripada `heartbeat_timeout` Lifecycle Hook.
- **Resolusi**:
  1. Setel nilai `deregistration_delay.timeout_seconds` pada ALB Target Group (misal: 60 detik).
  2. Konfigurasi ASG Terminating Lifecycle Hook dengan durasi timeout minimal 2x dari durasi deregistrasi ALB (misal: 180 detik).
  3. Pastikan aplikasi merespons `SIGTERM` dengan menutup listener dan membiarkan request yang sudah masuk selesai diproses.

---

## 18. Exercise
Instruksikan diri Anda untuk menyelesaikan skenario berikut:
1. Bangun sebuah VPC dengan 2 Private Subnets dan 2 Public Subnets (dilengkapi NAT Gateway).
2. Buat sebuah Launch Template dengan spesifikasi:
   - OS: Amazon Linux 2023 ARM64.
   - Instance Type: `c7g.medium`.
   - Metadata Options: `HttpTokens=required`, `HttpPutResponseHopLimit=1`.
   - IAM Role: `AmazonSSMManagedInstanceCore`.
3. Buat Auto Scaling Group dengan Mixed Instances Policy:
   - Minimum: 2, Desired: 2, Maximum: 6.
   - On-Demand Base: 1, sisanya Spot (`price-capacity-optimized`).
   - Instance Overrides: `c7g.medium`, `t4g.medium`, `c6g.medium`.
4. Masuk ke salah satu instans yang tercipta menggunakan AWS CLI Session Manager:
   `aws ssm start-session --target <instance-id>`
5. Verifikasi informasi arsitektur kernel di dalam instans:
   `uname -m` (harus menghasilkan `aarch64`)
   `lscpu` (periksa arsitektur core dan flags Graviton).

---

## 19. Challenge
Rancang arsitektur komputasi untuk pipeline pemrosesan video skala besar:
- Beban kerja bersifat asynchronous berbasis antrean Amazon SQS.
- Setiap video membutuhkan waktu rendering 3 hingga 5 menit menggunakan CPU.
- Anda diminta menekan biaya komputasi hingga 80% menggunakan Spot Instances.
- **Tantangan**: Karena Spot Instance dapat diinterupsi dengan pemberitahuan 2 menit, video yang sedang diproses di menit ke-4 berisiko gagal dan harus diulang dari awal jika instans mati mendadak.
- **Tugas Arsitektur**:
  1. Rancang alur deteksi interupsi Spot menggunakan EventBridge dan SQS.
  2. Implementasikan teknik *state checkpointing* di mana status rendering disimpan secara terfragmentasi ke EBS atau S3.
  3. Rancang ASG Scaling Policy berbasis metrik kustom *Backlog Per Instance* ($S / N$, di mana $S$ adalah kedalaman antrean SQS dan $N$ adalah kapasitas instans aktif saat ini).

---

## 20. Summary
- **AWS Nitro System** merevolusi arsitektur cloud compute dengan memisahkan beban hypervisor dan I/O ke perangkat keras ASIC terdedikasi (Nitro Cards), mengeliminasi hypervisor overhead dan menghadirkan keamanan fisik tak tertembus (Nitro Security Chip).
- **AWS Graviton** menghadirkan efisiensi komputasi generasi baru berbasis instruksi ARM64 Neoverse, memberikan dedicated physical core per vCPU tanpa hyperthreading jitter dengan penghematan biaya signifikan.
- **Modern Auto Scaling Groups** memadukan Launch Templates, diversifikasi armada komputasi (Mixed Instances), dan strategi alokasi Spot cerdas (`price-capacity-optimized`) yang diperkuat oleh **Lifecycle Hooks** untuk memastikan elastisitas tanpa gangguan transaksi aktif.
- **AWS Systems Manager (SSM)** mengeliminasi seluruh paradigma pengelolaan server via port 22 / bastion host lawas, memusatkan kontrol akses via IAM dan enkripsi session TLS outbound-only.