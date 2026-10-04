# BAB 03: Compute Architecture & Elastic Scaling
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis Arsitektur Internal AWS Nitro System**: Menjelaskan bagaimana offloading hypervisor ke hardware Nitro meningkatkan performa I/O, keamanan, dan alokasi resource komputasi secara near-bare-metal.
2. **Merancang Auto Scaling Group (ASG) Tingkat Lanjut**: Mengimplementasikan strategi *Mixed Instances Policy* (kombinasi On-Demand dan Spot), *Warm Pools*, serta *Capacity Rebalance* untuk optimasi biaya hingga 70% dengan ketersediaan 99.99%.
3. **Mengorkestrasi ASG Lifecycle Hooks Secara Determinostik**: Mengintegrasikan lifecycle hooks dengan AWS Systems Manager (SSM), EventBridge, dan Lambda untuk menangani proses inisialisasi aplikasi (*warm-up*) dan *graceful termination* tanpa *dropped connections*.
4. **Mengonfigurasi Dynamic & Predictive Scaling Berbasis Matematika Metrik**: Membangun kebijakan *Target Tracking* dan *Step Scaling* menggunakan CloudWatch Custom Metrics (seperti request per target backlog depth) untuk memitigasi latensi saat lonjakan trafik ekstrem.
5. **Mengotomasi Deployment Zero-Downtime pada EC2 Fleet**: Mengimplementasikan *Instance Refresh* dengan *Canary Deployments* dan *Rollback Alarms* menggunakan Terraform.

---

### 2. Prerequisite

Sebelum memulai modul ini, Anda wajib menguasai:
* Pemahaman fundamental Amazon EC2, VPC (Public/Private Subnets, NAT Gateway, Route Tables), dan Application Load Balancer (ALB).
* Konsep dasar Linux System Administration: `systemd`, penanganan sinyal UNIX (`SIGTERM`, `SIGINT`), POSIX shell scripting, dan *process lifecycle*.
* Pengetahuan mengenai IAM Roles, Policies (Least Privilege), dan EC2 Instance Metadata Service Version 2 (IMDSv2).
* Pengalaman praktis menggunakan HashiCorp Terraform (v1.5+) untuk provisioning infrastruktur berbasis Infrastructure as Code (IaC).

---

### 3. Concept & Internal Architecture

#### 3.1 AWS Nitro System: Arsitektur Hardware & Hypervisor
Sebelum Nitro, arsitektur virtualisasi berbasis Xen Hypervisor konvensional membagi CPU dan memori antara guest OS dan dom0/host OS untuk mengelola network, storage (EBS), dan sistem manajemen. Pendekatan ini menghasilkan variasi performa (I/O jitter) dan overhead komputasi.

```
Arsitektur Xen Legacy:
+-------------------------------------------------------------+
| EC2 Guest OS (vCPU / RAM) | Xen dom0 (Management & Drivers) |
+-------------------------------------------------------------+
| Xen Hypervisor (Software-based Scheduling & Isolation)      |
+-------------------------------------------------------------+
| Bare Metal Hardware (CPU, Memory, NIC, Storage Controller)  |
+-------------------------------------------------------------+

Arsitektur AWS Nitro:
+-------------------------------------------------------------+
| EC2 Guest OS (Akses Hampir 100% Core CPU & RAM Fisik)      |
+-------------------------------------------------------------+
| Lightweight Nitro Hypervisor (Core-based, Tanpa dom0)       |
+-------------------------------------------------------------+
| Nitro Cards Dedicated Hardware Offload:                     |
| [Nitro Card for VPC] [Nitro Card for EBS] [Nitro NVMe Card] |
| [Nitro Security Chip (Secure Boot & Hardware Root of Trust)]|
+-------------------------------------------------------------+
```

Komponen Inti Nitro System:
* **Nitro Card for VPC**: Dedicated PCIe ASIC yang memproses Software Defined Networking (VPC encapsulation, Security Groups, ENA/Enhanced Networking) tanpa membebani CPU instance.
* **Nitro Card for EBS**: Dedicated NVMe controller yang menangani enkripsi, kompresi, dan interkoneksi jaringan iSCSI/NVMe-oF ke EBS storage node.
* **Nitro Security Chip**: Mengunci sistem firmware flash controller dan mengimplementasikan Secure Boot, memvalidasi integritas bare-metal firmware secara kriptografis.
* **Nitro Hypervisor**: Hypervisor berbasis KVM yang sangat ramping, bertugas membagi core CPU dan alokasi memori fisik secara deterministik tanpa intervensi I/O management host OS.

#### 3.2 Finite State Machine (FSM) Lifecycle Hooks pada Auto Scaling Group
EC2 Auto Scaling Group mengelola state transisi instans dari peluncuran hingga terminasi. Lifecycle hooks mencegat state transition ini untuk mengeksekusi aksi kustom.

```
                    +-----------------------+
                    |        PENDING        |
                    +-----------------------+
                                |
                   (Launch Lifecycle Hook Triggered)
                                v
                    +-----------------------+
                    |     Pending:Wait      |<----+ (Heartbeat Extension)
                    +-----------------------+     |
                                |                 |
                    (Complete: CONTINUE / ABANDON)+
                                v
                    +-----------------------+
                    |    Pending:Proceed    |
                    +-----------------------+
                                |
                   (Target Group Registration)
                                v
                    +-----------------------+
                    |       InService       |  <=== Menerima Trafik Produksi
                    +-----------------------+
                                |
                  (Scale-In / Spot Interruption)
                                v
                    +-----------------------+
                    |      TERMINATING      |
                    +-----------------------+
                                |
                 (Terminate Lifecycle Hook Triggered)
                                v
                    +-----------------------+
                    |   Terminating:Wait    |<----+ (Heartbeat Extension)
                    +-----------------------+     |
                                |                 |
                    (Complete: CONTINUE / ABANDON)+
                                v
                    +-----------------------+
                    |  Terminating:Proceed  |
                    +-----------------------+
                                |
                    +-----------------------+
                    |      TERMINATED       |
                    +-----------------------+
```

Ketika hook berada pada state `Pending:Wait` atau `Terminating:Wait`:
* Instans diam di state tersebut hingga script menyelesaikan tugas dan mengirim API call `CompleteLifecycleAction`, atau timeout durasi tercapai (*HeartbeatTimeout*).
* Pada *Terminating:Wait*, instance dilepas dari ALB Target Group (memulai Connection Draining), lalu script lokal menjalankan proses flushing state, uploading log/dump metrics, dan menyelesaikan background worker threads.

#### 3.3 EC2 Fleet & Allocation Strategies (Spot + On-Demand)
Untuk aplikasi stateless berkinerja tinggi, memanfaatkan *Mixed Instances Policy* memungkinkan arsitektur tahan banting dengan biaya terendah.

1. **Spot Allocation Strategy**:
   * `price-capacity-optimized` (Recommended): Memilih pool instance yang memiliki ketersediaan kapasitas terdalam (*deepest capacity pool*) sekaligus memperhatikan efisiensi harga. Ini secara dramatis meminimalkan risiko terminasi Spot (*interruption rate* < 5%).
   * `capacity-optimized`: Memilih pool yang memiliki kapasitas terbesar tanpa memedulikan disparitas harga. Cocok untuk workload mission-critical.
2. **Capacity Rebalance**: Fitur proaktif ASG yang memanfaatkan sinyal *EC2 Instance Rebalance Recommendation* (diterbitkan beberapa menit sebelum sinyal terminasi 2-menit Spot Notification). ASG secara preventif meluncurkan pengganti baru sebelum instance lama dihapus.

#### 3.4 Scaling Policy Mathematics: Target Tracking vs Step Scaling
Target Tracking menggunakan proportional-integral-derivative (PID) control loop tertutup yang disediakan oleh CloudWatch dan EC2 Auto Scaling.

Perhitungan penambahan kapasitas pada Target Tracking:
$$\Delta \text{Capacity} = \text{Current Capacity} \times \left( \frac{\text{Actual Value} - \text{Target Value}}{\text{Target Value}} \right)$$

*Jika:*
* $\text{Current Capacity} = 10$
* $\text{Target Value} = 50\%$ CPU Utilization
* $\text{Actual Value} = 75\%$ CPU Utilization

Maka:
$$\Delta \text{Capacity} = 10 \times \left( \frac{75 - 50}{50} \right) = 10 \times 0.5 = +5 \text{ instances}$$

ASG akan langsung mengirim request peluncuran 5 instance baru untuk mengembalikan rata-rata metrik ke 50%.

---

### 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan (Problem Statement) | Apa Solusinya (Architectural Capability) |
| :--- | :--- | :--- |
| **AWS Nitro System** | Xen Hypervisor lama mengonsumsi hingga 10-15% CPU/RAM untuk I/O virtualization dan rentan terhadap noisy-neighbor effect. | Memindahkan network, storage, dan security management ke dedicated ASIC (Nitro Cards), memberikan near 100% resource untuk aplikasi. |
| **Lifecycle Hooks** | Instance baru langsung melayani trafik sebelum container/aplikasi selesai booting (mengakibatkan HTTP 502/504), dan instance mati mendadak saat scale-in memutus koneksi transaksi aktif. | Menghentikan FSM transition pada `Pending:Wait` dan `Terminating:Wait` guna memfasilitasi bootstrap validation dan graceful draining. |
| **ASG Warm Pools** | Inisialisasi aplikasi enterprise (Java/JVM, ML models, large container images) butuh 5-10 menit. Auto scaling reaktif menjadi terlalu lambat menghadapi lonjakan mendadak. | Menyimpan pool instance yang telah di-bootstrap pada state `Stopped` atau `Running-Hibernate`, memangkas durasi peluncuran menjadi < 30 detik. |
| **Mixed Instances Policy** | Bergantung hanya pada 1 tipe instance On-Demand sangat mahal; bergantung hanya pada 1 pool Spot rentan kehabisan kapasitas (*Spot Capacity Out of Stock*). | Melakukan diversifikasi deployment ke puluhan tipe instance (misal: `c6i.xlarge`, `c5.xlarge`, `m6i.xlarge`) dengan perpaduan On-Demand baseline dan Spot dynamic scale. |

---

### 5. How (Workflow Detail)

Alur Kerja Komprehensif Arsitektur Auto Scaling Produksi:

```
[Klien / Internet]
       |
       v
[Application Load Balancer (ALB)]
       |
       +---> [Target Group: Production EC2 Instances]
```

1. **Detection & Prediction**:
   * CloudWatch memonitor metrik kustom (misal: `ALBRequestCountPerTarget` atau `KafkaLagConsumerGroup`).
   * Predictive Scaling memproyeksikan kurva kebutuhan harian/mingguan via machine learning models dan memprogram kapasitas minimum sebelum lonjakan terjadi.
2. **Instance Launch & Nitro Provisioning**:
   * ASG mengevaluasi ketersediaan pool via `price-capacity-optimized`.
   * Hypervisor Nitro mengalokasikan PCIe devices untuk NVMe EBS volume dan ENA network interface secara hardware-accelerated.
3. **Execution of Launch Lifecycle Hook**:
   * Status instans masuk ke `Pending:Wait`.
   * Instance User Data memicu inisialisasi systemd, fetching runtime configuration dari Secrets Manager/Parameter Store, dan pulling image container.
   * Health check internal memverifikasi endpoint `http://127.0.0.1:8080/healthz`.
   * Shell script lokal mengeksekusi CLI command `aws autoscaling complete-lifecycle-action --lifecycle-action-result CONTINUE`.
4. **Registration to Target Group**:
   * Instans masuk ke `InService`.
   * ALB melakukan health check interval. Setelah melewati *HealthyThresholdCount*, instance aktif melayani trafik.
5. **Termination Lifecycle & Capacity Rebalancing**:
   * AWS mengirimkan sinyal *Spot Instance Interruption Notice* via CloudWatch EventBridge atau Instance Metadata (`/latest/meta-data/spot/instance-action`).
   * EventBridge Rule mengeksekusi SSM Automation / trigger script lokal.
   * ASG Lifecycle Hook memindahkan status ke `Terminating:Wait`.
   * ALB memicu proses *Deregistration Delay* (Connection Draining).
   * Aplikasi menerima `SIGTERM`, berhenti menerima koneksi baru, menyelesaikan pending transaksi, lalu keluar (*graceful shutdown*).
   * Script lifecycle mengirim sinyal penutupan aksi, ASG mematikan instans Nitro secara aman.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata: Dapur Restoran Bintang Lima Berkecepatan Tinggi
* **EC2 Bare Metal & Nitro Cards**: Dapur fisik di mana *Chef* (CPU Utama) hanya fokus memasak. Dapur tersebut memiliki asisten khusus berkecepatan tinggi: satu asisten khusus mencuci piring dan mengambil bahan dari gudang (*Nitro EBS Card*), satu kurir khusus mengantar makanan ke pelayan (*Nitro VPC Card*), dan petugas keamanan yang menjaga akses gudang (*Nitro Security Chip*). Chef tidak pernah menyapu lantai atau mencatat pesanan logistik.
* **Warm Pool**: Koki cadangan yang sudah mengenakan seragam, mencuci tangan, dan berdiri di ruang istirahat (*Stopped state*). Begitu lonjakan tamu datang, koki cadangan tidak perlu wawancara kerja atau ganti baju; mereka langsung melangkah ke meja masak dalam 5 detik.
* **Lifecycle Hooks**: Protokol di mana koki baru dicek standar higienitasnya sebelum boleh menyentuh kompor (*Pending:Wait*), dan saat shift selesai, mereka harus menghabiskan sisa piring yang sedang dimasak sebelum boleh *clock-out* (*Terminating:Wait*).

#### Diagram Arsitektur Produksi Lanjutan
```
+--------------------------------------------------------------------------------------------------+
| AWS Region: Multi-AZ Deployment (AZ-a, AZ-b, AZ-c)                                              |
|                                                                                                  |
|   +------------------------------------------------------------------------------------------+   |
|   |                        Application Load Balancer (Public Subnets)                        |   |
|   +------------------------------------------------------------------------------------------+   |
|                                       | Target Group Routing                                     |
|                                       v                                                          |
|   +------------------------------------------------------------------------------------------+   |
|   | Auto Scaling Group (Private Subnets)                                                     |   |
|   | Policy: Mixed Instances (On-Demand Base: 20%, Spot: 80% price-capacity-optimized)        |   |
|   | Instances: c6i.xlarge, c6a.xlarge, c5.xlarge, m6i.xlarge                                 |   |
|   |                                                                                          |   |
|   |   +-----------------------+  +-----------------------+  +-----------------------+        |   |
|   |   | AZ-a: EC2 (InService) |  | AZ-b: EC2 (InService) |  | AZ-c: EC2 (InService) |        |   |
|   |   | Nitro Hardware Accel  |  | Nitro Hardware Accel  |  | Nitro Hardware Accel  |        |   |
|   |   +-----------------------+  +-----------------------+  +-----------------------+        |   |
|   |                                                                                          |   |
|   |   +----------------------------------------------------------------------------------+   |   |
|   |   | ASG Warm Pool (State: Stopped, Min: 2, Max: 10)                                  |   |   |
|   |   | Pre-warmed instances with pre-baked AMIs and pulled application artifacts       |   |   |
|   |   +----------------------------------------------------------------------------------+   |   |
|   +------------------------------------------------------------------------------------------+   |
|          |                                                                   ^                   |
|          | Metric Breached                                                   | Rebalance / Scale |
|          v                                                                   |                   |
|   +--------------------+     CloudWatch Alarm     +----------------------------------+           |
|   | CloudWatch Metrics | -----------------------> | EventBridge / Scaling Policies   |           |
|   | - ALB Target Req   |                          | - Target Tracking (PID Loop)     |           |
|   | - Memory / Custom  |                          | - Capacity Rebalance Trigger     |           |
|   +--------------------+                          +----------------------------------+           |
|                                                            |                                     |
|          +-------------------------------------------------+                                     |
|          v                                                                                       |
|   +-------------------------------+                                                              |
|   | EventBridge: Lifecycle Hooks  | ---> [ SSM Run Command / Lambda / Local Systemd Agent ]     |
|   | - EC2_INSTANCE_TERMINATING    |      (Flushes queues, connection drain, sends heartbeat)     |
|   +-------------------------------+                                                              |
+--------------------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Graceful Shutdown Bash Script (POSIX & IMDSv2 Compliant)
Script ini diatur sebagai service systemd untuk mendengarkan shutdown sequence dan memberi tahu ASG Lifecycle Hook.

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

# Fetch IMDSv2 Token
IMDS_TOKEN=$(curl -sS -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 60")

# Fetch Identity Metadata
INSTANCE_ID=$(curl -sS -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" \
  http://169.254.169.254/latest/meta-data/instance-id)
REGION=$(curl -sS -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" \
  http://169.254.169.254/latest/meta-data/placement/region)

ASG_NAME="asg-production-payment-api"
HOOK_NAME="hook-instance-terminating"

echo "INFO: Inisiasi graceful shutdown untuk $INSTANCE_ID pada region $REGION"

# Fungsi untuk mengirim denyut jantung lifecycle hook agar tidak dihentikan paksa
send_heartbeat() {
  while true; do
    echo "INFO: Mengirim heartbeat action..."
    aws autoscaling record-lifecycle-action-heartbeat \
      --lifecycle-hook-name "$HOOK_NAME" \
      --auto-scaling-group-name "$ASG_NAME" \
      --instance-id "$INSTANCE_ID" \
      --region "$REGION" || true
    sleep 30
  done
}

# Jalankan heartbeat di background
send_heartbeat &
HEARTBEAT_PID=$!

# Trap untuk membersihkan subprocess jika script exit
cleanup() {
  kill "$HEARTBEAT_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Simulasi penyelesaian task/draining
echo "INFO: Menghentikan worker service dan menunggu drain koneksi..."
systemctl stop payment-worker.service

# Beri tahu ASG bahwa proses terminasi aman dilanjutkan
echo "INFO: Selesai. Melanjutkan terminasi via CompleteLifecycleAction."
aws autoscaling complete-lifecycle-action \
  --lifecycle-action-result CONTINUE \
  --lifecycle-hook-name "$HOOK_NAME" \
  --auto-scaling-group-name "$ASG_NAME" \
  --instance-id "$INSTANCE_ID" \
  --region "$REGION"

exit 0
```

#### 7.2 Practical Example: Enterprise Production Terraform Module
Konfigurasi komprehensif: Mixed Instances Policy, Warm Pool, Lifecycle Hooks, Target Tracking, dan IMDSv2 Enforcement.

```hcl
# File: compute_production.tf

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "vpc_id" {
  type        = string
  description = "Target VPC ID"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Subnet IDs for multi-AZ instance deployment"
}

# 1. Security Group - Zero Ingress from Public, Only from Internal ALB
resource "aws_security_group" "compute_sg" {
  name_prefix = "sg-production-compute-"
  vpc_id      = var.vpc_id
  description = "Restrictive security group for enterprise compute instances"

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

# 2. IAM Role for Instance with IMDSv2 & Lifecycle Management Permissions
resource "aws_iam_role" "instance_role" {
  name_prefix = "role-ec2-production-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
      }
    ]
  })
}

resource "aws_iam_role_policy" "asg_lifecycle_policy" {
  name_prefix = "policy-asg-lifecycle-"
  role        = aws_iam_role.instance_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "autoscaling:CompleteLifecycleAction",
          "autoscaling:RecordLifecycleActionHeartbeat"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "ec2:DescribeTags"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "instance_profile" {
  name_prefix = "profile-ec2-production-"
  role        = aws_iam_role.instance_role.name
}

# 3. Launch Template (Hardened with Nitro Optimizations & IMDSv2 Mandatory)
resource "aws_launch_template" "production_lt" {
  name_prefix   = "lt-production-api-"
  image_id      = "ami-0c7217cdde317cfec" # Canonical Ubuntu 22.04 LTS Nitro-Optimized
  instance_type = "c6i.xlarge"

  iam_instance_profile {
    arn = aws_iam_instance_profile.instance_profile.arn
  }

  vpc_security_group_ids = [aws_security_group.compute_sg.id]

  # Enforce IMDSv2 to prevent SSRF credential exfiltration
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  monitoring {
    enabled = true # Detail CloudWatch 1-minute metrics
  }

  ebs_optimized = true

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 50
      volume_type           = "gp3"
      iops                  = 3000
      throughput            = 125
      encrypted             = true
      delete_on_termination = true
    }
  }

  user_data = base64encode(<<-EOF
              #!/bin/bash
              set -ex
              echo "Starting initialization at $(date)"
              # Application startup simulation
              apt-get update && apt-get install -y awscli
              # Signal successful bootstrap to ASG
              INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $(curl -s -X PUT 'http://169.254.169.254/latest/api/token' -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')" http://169.254.169.254/latest/meta-data/instance-id)
              aws autoscaling complete-lifecycle-action \
                --lifecycle-action-result CONTINUE \
                --lifecycle-hook-name hook-instance-launching \
                --auto-scaling-group-name asg-production-enterprise \
                --instance-id "$INSTANCE_ID" \
                --region ap-southeast-1 || true
              EOF
  )

  lifecycle {
    create_before_destroy = true
  }
}

# 4. Auto Scaling Group with Mixed Instances & Capacity Rebalance
resource "aws_autoscaling_group" "production_asg" {
  name_prefix         = "asg-production-enterprise-"
  vpc_zone_identifier = var.private_subnet_ids

  min_size         = 3
  max_size         = 30
  desired_capacity = 6

  capacity_rebalance = true # Proactive Spot termination handling

  mixed_instances_policy {
    instances_distribution {
      on_demand_base_capacity                  = 2
      on_demand_percentage_above_base_capacity = 20
      spot_allocation_strategy                 = "price-capacity-optimized"
    }

    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.production_lt.id
        version            = "$Latest"
      }

      override {
        instance_type     = "c6i.xlarge"
        weighted_capacity = "1"
      }
      override {
        instance_type     = "c6a.xlarge"
        weighted_capacity = "1"
      }
      override {
        instance_type     = "c5.xlarge"
        weighted_capacity = "1"
      }
    }
  }

  # Zero Downtime Instance Refresh configuration
  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 90
      instance_warmup        = 300
    }
  }

  lifecycle {
    create_before_destroy = true
    ignore_changes        = [desired_capacity]
  }

  tag {
    key                 = "Name"
    value               = "prod-fleet-worker"
    propagate_at_launch = true
  }
}

# 5. Warm Pool Configuration
resource "aws_autoscaling_group_tag" "pool_tag" {
  autoscaling_group_name = aws_autoscaling_group.production_asg.name
  tag {
    key                 = "WarmPoolManaged"
    value               = "true"
    propagate_at_launch = true
  }
}

resource "aws_ec2_managed_prefix_list" "empty_example" {
  # Placeholder to indicate modularity
  name           = "pl-empty"
  address_family = "IPv4"
  max_entries    = 1
}

# 6. Lifecycle Hooks
resource "aws_autoscaling_lifecycle_hook" "launch_hook" {
  name                   = "hook-instance-launching"
  autoscaling_group_name = aws_autoscaling_group.production_asg.name
  default_result         = "ABANDON"
  heartbeat_timeout      = 300
  lifecycle_transition   = "autoscaling:EC2_INSTANCE_LAUNCHING"
}

resource "aws_autoscaling_lifecycle_hook" "terminate_hook" {
  name                   = "hook-instance-terminating"
  autoscaling_group_name = aws_autoscaling_group.production_asg.name
  default_result         = "CONTINUE"
  heartbeat_timeout      = 600
  lifecycle_transition   = "autoscaling:EC2_INSTANCE_TERMINATING"
}

# 7. Target Tracking Policy (Based on ALB Request Count Per Target)
resource "aws_autoscaling_policy" "target_tracking_cpu" {
  name                   = "policy-target-tracking-cpu"
  autoscaling_group_name = aws_autoscaling_group.production_asg.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value     = 60.0
    disable_scale_in = false
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: TokoMega - Flash Sale Engine E-Commerce Tier-1
* **Latar Belakang**: Platform e-commerce dengan trafik normal 20.000 RPS mengalami lonjakan hingga 180.000 RPS dalam 3 menit pertama saat flash sale tengah malam.
* **Insiden Masa Lalu**:
  1. Penggunaan Single Instance Type (`c5.2xlarge`) On-Demand menyebabkan limit regional AWS tercapai (*VcpuLimitExceeded*).
  2. Bootstrapping aplikasi Java Monolith memakan waktu 7 menit per instance. Akibatnya, latensi HTTP 504 membanjiri ALB sebelum instance baru berstatus `Healthy`.
  3. Instance Spot dimatikan secara mendadak oleh AWS tanpa graceful shutdown, memutus transaksi pengguna di tengah checkout database commit.
* **Solusi Arsitektur Baru yang Diterapkan**:
  1. **Mixed Instances Policy**: Membagi deployment ke 5 tipe Nitro (Intel: `c6i.2xlarge`, AMD: `c6a.2xlarge`, Graviton: `c7g.2xlarge` untuk container Go, serta `m6i.2xlarge` sebagai fallback). Mengonfigurasi `price-capacity-optimized` dengan 30% baseline On-Demand dan 70% Spot.
  2. **ASG Warm Pools**: Mengimplementasikan warm pool berstatus `Stopped` sebanyak 40 instances. Saat flash sale terdeteksi atau dijadwalkan, status instans berubah dari `Stopped` ke `InService` dalam 28 detik (hanya butuh kernel boot dan DNS handshake; dependencies aplikasi sudah pre-warmed).
  3. **Capacity Rebalancing & Dynamic Termination Draining**: Memasang EventBridge rule yang menangkap sinyal `EC2 Spot Instance Interruption Notice`. Ketika sinyal diterima, ALB Connection Draining menyetel durasi 90 detik, dan instance trigger script mengeksekusi commit penutupan sesi Redis/DB sebelum statusnya dibiarkan `TERMINATED`.
* **Hasil**:
  * Latensi P99 tetap terkontrol di bawah 120 ms sepanjang flash sale.
  * Zero dropped transactions selama spot preemption.
  * Efisiensi pengeluaran komputasi sebesar 62% dibandingkan penggunaan full On-Demand.

---

### 9. Trade-offs

| Dimensi | Pilihan A | Pilihan B | Analisis Trade-off Rekayasa |
| :--- | :--- | :--- | :--- |
| **Instance Purchasing** | **100% On-Demand Fleet** | **Mixed Instances (On-Demand Base + Spot)** | On-Demand menjamin ketersediaan deterministik tanpa interupsi, namun berbiaya hingga 3-4x lipat lebih mahal. Spot menawarkan efisiensi drastis namun membutuhkan arsitektur aplikasi stateless dan penanganan graceful draining otomatis. |
| **Scaling Policy** | **Target Tracking Scaling** | **Step Scaling** | Target tracking sangat cepat diatur dan menjaga metrik tetap stabil via continuous calculation. Namun, Step Scaling memberikan kontrol deterministik yang mutlak terhadap batasan step margin metrik CloudWatch untuk workload berkarakteristik agresif/bursty. |
| **Warm Pool State** | **Stopped Warm Pool** | **Running (Hiatus) Warm Pool** | `Stopped` menghemat biaya komputasi (hanya membayar storage volume EBS), tetapi butuh 20-30 detik untuk booting. `Running` memangkas waktu start menjadi sub-detik namun tetap dikenai biaya vCPU/Memory penuh. |
| **Deployment Strategy** | **Rolling (Min Healthy 100%)** | **Blue/Green via Dynamic ASG Swap** | Rolling deployment tidak memerlukan kuota kapasitas ganda di VPC, namun proses rilis berjalan lambat. Blue/Green instance swap membutuhkan alokasi IP dan limit vCPU 2x lipat, namun memungkinkan *instant rollback* via ALB target group switching. |

---

### 10. Common Mistakes & Troubleshooting

#### Skenario 1: Flapping / Thrashing pada Auto Scaling (Scale-out dan Scale-in Berulang-ulang)
* **Penyebab**: Nilai cooldown period terlalu singkat atau ambang batas scale-in terlalu dekat dengan scale-out. Misalnya: Target Tracking disetel pada 50% CPU. Penambahan 5 instance menurunkan beban secara dramatis ke 20%, memicu scale-in instan.
* **Deteksi**: Periksa timeline CloudWatch History pada ASG; temukan event berulang `Terminating EC2 instance...` diikuti `Launching EC2 instance...` dalam interval < 5 menit.
* **Solusi**: Aktifkan `disable_scale_in = true` pada kebijakan scale-out agresif dan gunakan scale-in policy terpisah dengan step scaling dan *Scale-In Cooldown* minimal 300 detik.

#### Skenario 2: Lifecycle Hook Hang & Timeout (Instance Tertahan di `Pending:Wait`)
* **Penyebab**: Script User Data mengalami kegagalan fatal (misal: gagal download package via internet karena private subnet tidak memiliki route ke NAT Gateway) atau tidak memiliki permissions IAM untuk memanggil CLI `autoscaling:CompleteLifecycleAction`.
* **Deteksi**:
  ```bash
  # Cek console log instance via AWS CLI
  aws ec2 get-console-output --instance-id i-0123456789abcdef0 --output text
  ```
* **Solusi**: Pastikan IAM instance role memuat izin `autoscaling:CompleteLifecycleAction`. Gunakan penanganan error POSIX `trap` pada User Data, dan pastikan route NAT Gateway serta Security Group egress outbound port 443 terbuka ke AWS STS/Auto Scaling endpoints.

#### Skenario 3: IMDSv2 SSRF Protection Menyebabkan Script/Agent Pihak Ketiga Gagal
* **Penyebab**: Menyetel `http_tokens = "required"` dengan `http_put_response_hop_limit = 1` saat aplikasi berjalan di dalam container Docker bridge network. Nilai hop limit `1` memblokir container mengakses metadata karena forwarding network layer Linux menghitung packet routing sebagai 1 hop tambahan.
* **Deteksi**: Log container menampilkan HTTP 403 Forbidden atau timeout saat menghubungi IP `169.254.169.254`.
* **Solusi**: Jika aplikasi berada di dalam container, ubah Launch Template metadata options:
  ```hcl
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2 # Izinkan traversal melalui interface container bridge
  }
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Enforce IMDSv2 Exclusively**: Matikan IMDSv1 pada semua Launch Templates (`http_tokens = "required"`).
- [ ] **Utilize Nitro Hardware**: Pastikan tipe instance yang dipilih bertipe generasi ke-5 ke atas (misal: `c6i`, `m6g`, `r6i`) untuk mendapatkan performa ENA networking hardware acceleration.
- [ ] **Diversify Spot Instances**: Daftarkan minimal 3-5 varian instance type dengan ukuran resource (vCPU & RAM) yang setara pada Mixed Instances Policy.
- [ ] **Enable Capacity Rebalance**: Pasang flag `capacity_rebalance = true` agar ASG merespons proaktif terhadap terminasi Spot.
- [ ] **Fine-tune Deregistration Delay**: Konfigurasikan durasi `deregistration_delay.timeout_seconds` pada ALB Target Group agar sinkron dengan Lifecycle Hook Terminating Heartbeat (rekomendasi: 30-90 detik).
- [ ] **Implement Graceful Termination Hooks**: Pasang lifecycle hook `autoscaling:EC2_INSTANCE_TERMINATING` untuk menuntaskan buffer log transaksi sebelum storage dimusnahkan.
- [ ] **Pre-bake AMIs (Golden Images)**: Jangan lakukan kompilasi kode atau instalasi package masif saat User Data berjalan. Gunakan HashiCorp Packer untuk membakar seluruh dependency ke dalam AMI dasar guna memangkas startup time ke < 60 detik.
- [ ] **Multi-AZ Subnet Distribution**: Sebarkan ASG minimal ke 3 Availability Zones independen di dalam satu Region.

---

### 12. Hands-on Practice

Buatlah struktur direktori lokal untuk hands-on ini:
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
```

Simpan file-file berikut ke dalam direktori tersebut:

#### Langkah 1: Buat file Terraform Provider dan VPC Dummy
```hcl
# hands-on/m02/network.tf
provider "aws" {
  region = "ap-southeast-1"
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "lab_vpc" {
  cidr_block           = "10.100.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "asg-deepdive-vpc" }
}

resource "aws_subnet" "lab_subnets" {
  count             = 2
  vpc_id            = aws_vpc.lab_vpc.id
  cidr_block        = cidrsubnet(aws_vpc.lab_vpc.cidr_block, 8, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags = { Name = "asg-deepdive-subnet-${count.index}" }
}
```

#### Langkah 2: Buat Script Worker dan Systemd Service
Buat file `worker.sh` untuk mensimulasikan background task:
```bash
# hands-on/m02/worker.sh
#!/bin/bash
trap "echo 'SIGTERM received, finishing pending jobs...'; sleep 5; exit 0" SIGTERM
echo "Worker started. Processing queue..."
while true; do
  sleep 1
done
```

#### Langkah 3: Konfigurasi Compute Terraform
Gunakan konfigurasi Terraform dari **Seksi 7.2** dan simpan sebagai `hands-on/m02/compute.tf`. Pastikan variabel `vpc_id` mengarah ke `aws_vpc.lab_vpc.id` dan `private_subnet_ids` mengarah ke `aws_subnet.lab_subnets[*].id`.

#### Langkah 4: Deployment dan Validasi Lifecycle Action
1. Jalankan inisialisasi dan provisioning:
   ```bash
   terraform init
   terraform apply -auto-approve
   ```
2. Ambil ID instance yang sedang berada di status `InService`:
   ```bash
   ASG_NAME=$(terraform output -raw asg_name) # Tambahkan output sesuai resource
   aws autoscaling describe-auto-scaling-groups \
     --auto-scaling-group-names "$ASG_NAME" \
     --query "AutoScalingGroups[0].Instances[*].[InstanceId,LifecycleState,HealthStatus]" \
     --output table
   ```
3. Uji Lifecycle Hook Termination secara manual dengan menghentikan salah satu instance:
   ```bash
   INSTANCE_TO_KILL="<INSTANCE_ID>"
   aws autoscaling terminate-instance-in-auto-scaling-group \
     --instance-id "$INSTANCE_TO_KILL" \
     --no-should-decrement-desired-capacity
   ```
4. Amati bahwa instance memasuki status `Terminating:Wait` selama waktu *HeartbeatTimeout* sebelum beralih ke `Terminated`.

---

### 13. Exercise

#### Tingkat Kesulitan: Easy
* **Soal**: Modifikasi Launch Template pada Terraform di Seksi 7.2 untuk menambahkan tag spesifik bernama `CostCenter = "Engineering-Alpha"` yang harus terpropagasi secara otomatis ke semua EBS Volume yang dibuat bersamaan dengan peluncuran instance.
* **Ekspektasi Output**: Konfigurasi `tag_specifications` dalam block `aws_launch_template` yang menargetkan resource type `instance` dan `volume`.

#### Tingkat Kesulitan: Medium
* **Soal**: Buat EventBridge Rule yang mendeteksi event `EC2 Instance Rebalance Recommendation` dan secara otomatis mengirim pesan notifikasi ke SNS Topic tim SRE.
* **Ekspektasi Output**: Kode Terraform yang mencakup resource `aws_cloudwatch_event_rule` (dengan event pattern `aws.ec2` dan event type `EC2 Instance Rebalance Recommendation`) beserta `aws_cloudwatch_event_target` yang terhubung ke AWS SNS.

#### Tingkat Kesulitan: Hard
* **Soal**: Susun arsitektur Custom Metric Scaling untuk sistem Kafka Consumer. Jika rata-rata consumer lag per instance melebihi 10.000 records, ASG harus melakukan scaling out. Hitung formula scale-out math yang dibutuhkan, dan tuliskan konfigurasi Terraform `aws_autoscaling_policy` menggunakan tipe `TargetTrackingScaling` dengan `customized_metric_specification`.
* **Ekspektasi Output**: File Terraform yang mendefinisikan metric math:
  $$\text{BacklogPerInstance} = \frac{\text{Sum}(\text{KafkaGroupLag})}{\text{ASGCurrentCapacity}}$$
  dan menargetkan angka stabil 10.000 records per instance.

---

### 14. Challenge

**Skenario**: Sistem Payment Gateway Bank Terbuka
* **Kebutuhan**:
  1. Waktu inisialisasi aplikasi (cold start) memakan waktu 4 menit karena validasi sertifikat mTLS dan caching ledger.
  2. SLA latensi checkout mewajibkan p99 < 80ms.
  3. Biaya infrastruktur wajib ditekan menggunakan Spot Instances, namun kegagalan pembayaran akibat spot termination mendadak adalah **Zero Tolerance** (denda audit compliance).
  4. Aplikasi harus mampu menangani lonjakan dari 5.000 RPS ke 80.000 RPS dalam waktu kurang dari 90 detik saat ada promo e-wallet nasional.
* **Tantangan Arsitektur**:
  Rancang desain arsitektur menyeluruh tanpa menggunakan solusi managed Kubernetes (EKS). Solusi harus berbasis native AWS EC2, ASG, EventBridge, Lambda, ALB, dan Parameter Store.
* **Pertanyaan yang Harus Dijawab dalam Desain Anda**:
  1. Bagaimana Anda merancang arsitektur Warm Pool (status apa yang dipilih: `Stopped` vs `Running`) untuk memangkas cold start 4 menit menjadi di bawah 40 detik tanpa memboroskan anggaran?
  2. Bagaimana workflow penanganan sinyal terminasi 2 menit EC2 Spot agar *in-flight transaction* yang sedang memproses transfer saldo perbankan di-flush dan dialihkan ke instance On-Demand baseline tanpa memicu kegagalan transaksi ganda (*double spending*)?
  3. Sajikan diagram urutan (Sequence Diagram) ASCII yang menguraikan interaksi antara: ALB, EC2 Spot Instance lama, AWS EventBridge, Lambda Orchestrator, Database Lock Manager, dan ASG Lifecycle Controller.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Apa perbedaan mendasar antara arsitektur Xen Hypervisor lama dengan AWS Nitro System?**
   * A. Xen memproses isolasi hardware via chip fisik, sedangkan Nitro berbasis software emulasi.
   * B. Nitro memindahkan proses I/O storage, networking, dan management ke dedicated ASIC PCIe cards, membebaskan hampir seluruh CPU/RAM host untuk guest OS.
   * C. Nitro hanya mendukung sistem operasi berbasis Linux kernel versi 2.6 ke bawah.
   * D. Xen tidak memerlukan driver jaringan, sedangkan Nitro wajib menggunakan realtek standard.

2. **Apa yang terjadi pada status instance di ASG saat memasuki lifecycle hook `Pending:Wait`?**
   * A. Instance langsung menerima trafik dari ALB Target Group.
   * B. Instance ditolak oleh AWS dan langsung dihancurkan.
   * C. Instance tertahan dalam proses transisi dan belum melayani trafik hingga menerima sinyal `CompleteLifecycleAction` atau timeout.
   * D. Instance dialihkan ke mode hibernasi secara otomatis.

3. **Mengapa IMDSv2 jauh lebih aman daripada IMDSv1?**
   * A. IMDSv2 mengenkripsi data menggunakan algoritma RSA 4096-bit pada storage internal.
   * B. IMDSv2 berbasis sesi yang mewajibkan header token HTTP `PUT` sebelum query data, memitigasi eksploitasi SSRF tipe open WAF bypass.
   * C. IMDSv2 hanya dapat diakses melalui public IP instance.
   * D. IMDSv2 menonaktifkan metadata role IAM secara permanen.

4. **Karakteristik strategi alokasi Spot `price-capacity-optimized` adalah...**
   * A. Memilih pool Spot dengan harga termahal agar kapasitas terjamin.
   * B. Memilih secara acak di seluruh region tanpa memedulikan ketersediaan.
   * C. Mengidentifikasi pool kapasitas terdalam terlebih dahulu, lalu memilih pool yang menawarkan harga terendah di antara pool yang stabil tersebut.
   * D. Hanya mengalokasikan satu jenis tipe instance dalam satu AZ.

5. **Apa fungsi dari parameter `heartbeat_timeout` pada ASG Lifecycle Hook?**
   * A. Mengatur interval health check ALB ke instance.
   * B. Batas waktu toleransi (dalam detik) di mana instance dibiarkan berada pada status `Wait` sebelum aksi default (`CONTINUE` atau `ABANDON`) dieksekusi.
   * C. Waktu yang dibutuhkan instance untuk reboot setelah crash.
   * D. Interval pengiriman metrik memori CloudWatch Agent.

#### Bagian 2: Intermediate (5 Soal)
6. **Jika Anda mengonfigurasi Target Tracking Scaling Policy berbasis CPU pada target 60%, apa yang terjadi jika metrik tiba-tiba melonjak dari 60% ke 90% pada fleet berukuran 10 instance?**
   * A. Kapasitas ASG dikurangi sebesar 50%.
   * B. ASG menunggu 1 jam sebelum mengambil tindakan apapun.
   * C. ASG secara proporsional menghitung kebutuhan penambahan kapasitas dan meluncurkan +5 instance secara instan.
   * D. ASG langsung melipatgandakan ukuran instance ke batas `max_size` tanpa kalkulasi.

7. **Pada situasi apa status Warm Pool `Stopped` lebih diutamakan dibandingkan status `Running`?**
   * A. Saat aplikasi membutuhkan waktu initialization 0 detik (instant sync).
   * B. Saat organisasi ingin menekan biaya server seminimal mungkin namun butuh waktu peluncuran yang lebih cepat daripada cold provisioning.
   * C. Saat aplikasi memegang database stateful lokal di ephemeral NVMe disks.
   * D. Saat instance tidak memiliki volume root EBS.

8. **Bagaimana fitur *Capacity Rebalance* pada ASG memitigasi risiko interupsi Spot?**
   * A. Memaksa AWS untuk tidak pernah mematikan Spot instance tersebut.
   * B. Secara otomatis mengubah Spot Instance menjadi Dedicated Bare Metal Host.
   * C. Mendeteksi sinyal *Rebalance Recommendation* lebih awal dan meluncurkan instance pengganti sebelum instance Spot lama ditarik oleh AWS.
   * D. Membatasi deployment hanya pada hari libur nasional.

9. **Ketika ALB Target Group menyetel `deregistration_delay.timeout_seconds = 60`, apa implikasinya terhadap koneksi yang sedang berlangsung?**
   * A. Seluruh koneksi TCP langsung diputus seketika melalui packet RST.
   * B. ALB tidak lagi mengirim request baru ke instance tersebut, dan memberikan tenggang waktu 60 detik bagi request lama untuk selesai diproses.
   * C. ALB menghapus instance dari DNS record Route 53 dalam 60 milidetik.
   * D. Target Group menolak traffic dari AZ yang bersangkutan.

10. **Apa kegunaan parameter `min_healthy_percentage` pada blok `instance_refresh` ASG?**
    * A. Menjamin batas minimal instance yang wajib tetap berstatus sehat dan melayani trafik selama proses rolling deployment versi AMI baru berlangsung.
    * B. Mengatur batas persentase minimal memory yang harus kosong pada instance.
    * C. Menolak instance yang memiliki efisiensi CPU di bawah angka tersebut.
    * D. Menentukan persentase spot instance yang boleh dialokasikan.

#### Bagian 3: Production Case Scenarios (3 Soal)
11. **Skenario A**: Tim Anda merilis versi Launch Template baru dengan binary Go yang salah dikompilasi (panic loop saat start). Instance refresh ASG dijalankan. Apa konfigurasi penyelamat pada ASG untuk memastikan downtime total tidak menimpa sistem produksi?
    * A. Menyalakan `capacity_rebalance = true`.
    * B. Menyetel `min_healthy_percentage = 100`, mengonfigurasi CloudWatch Rollback Alarms pada error rate ALB, dan menggunakan lifecycle launch hook yang memvalidasi healthz sebelum mengirim `CONTINUE`.
    * C. Mengubah spot allocation strategy menjadi `lowest-price`.
    * D. Mematikan fitur Target Tracking Scaling.

12. **Skenario B**: Di lingkungan mikroservis dengan ratusan interaksi service-to-service internal, latensi rata-rata jaringan antar instance Nitro meningkat tiba-tiba sebesar 20ms pada jam sibuk. Investigasi awal menunjukkan bandwidth jaringan fisik belum mencapai batas limit instance. Fitur arsitektur compute AWS apa yang harus diaktifkan untuk mengurangi tail-latency dan packet jitter secara signifikan?
    * A. Mengaktifkan Elastic Network Adapter (ENA) Express dengan Scalable Reliable Datagram (SRD).
    * B. Mengganti semua private subnet menjadi public subnet.
    * C. Mengurangi instance size menjadi `t4g.nano` untuk memperbanyak jumlah core logis.
    * D. Mematikan fitur EBS Optimized.

13. **Skenario C**: Sebuah batch processing worker pool berbasis Spot mengalami interupsi massal serentak di Availability Zone `ap-southeast-1a` karena lonjakan kebutuhan regional. Pekerjaan batch antrean RabbitMQ terhenti. Apa langkah mitigasi arsitektur terbaik pada level ASG?
    * A. Menghapus subnet AZ-a dan hanya menggunakan single AZ.
    * B. Mengonfigurasi Mixed Instances Policy multi-AZ dengan puluhan kombinasi family instance (Compute, Memory, General Purpose) dan menyetel strategi `price-capacity-optimized`.
    * C. Mengunci satu instance type saja (`c5.large`) agar pool pencarian konsisten.
    * D. Menyetel `heartbeat_timeout = 0`.

---

#### Kunci Jawaban & Pembahasan Quiz

##### Bagian 1: Basic
1. **B**: Arsitektur Nitro memindahkan fungsi storage, network, management, dan security ke hardware card independen (ASIC), meminimalkan jitter dan overhead hypervisor ke tingkat mendekati bare-metal.
2. **C**: Instance pada state `Pending:Wait` berhenti sementara dalam transisi state machine ASG dan belum dimasukkan ke load balancer hingga bootstrap selesai dan sinyal `CompleteLifecycleAction` dikirim.
3. **B**: IMDSv2 mewajibkan sesi via token berbasis metode HTTP PUT dengan batas hop limit, mencegah penyerang memanfaatkan kerentanan SSRF (Server-Side Request Forgery) untuk mencuri kredensial instance profile.
4. **C**: `price-capacity-optimized` menganalisis pool yang memiliki alokasi kapasitas terdalam terlebih dahulu untuk stabilitas, lalu memilih varian termurah di antara opsi stabil tersebut.
5. **B**: Heartbeat timeout adalah batas durasi aman sebelum ASG mengambil keputusan tindakan fallback (`default_result`) jika hook tidak kunjung merespons.

##### Bagian 2: Intermediate
6. **C**: Target Tracking mengimplementasikan kontrol umpan balik proporsional. Sesuai formula matematikanya: $\Delta = 10 \times ((90 - 60) / 60) = +5$ instans.
7. **B**: Status `Stopped` menghentikan tagihan komputasi vCPU/RAM dan hanya membebankan biaya root volume EBS, menjadikannya opsi ideal untuk efisiensi biaya dengan kecepatan start medium (puluhan detik).
8. **C**: *Capacity Rebalance* mendeteksi sinyal analitik AWS sebelum notifikasi interupsi final 2 menit keluar, memicu peluncuran instance baru secara seamless sebelum node lama mati.
9. **B**: ALB Connection Draining menjaga koneksi aktif yang ada tetap berjalan hingga batas waktu yang ditentukan tanpa menerima trafik baru, mencegah error HTTP drop pada klien.
10. **A**: `min_healthy_percentage` memastikan kapasitas operasional minimum tetap terpenuhi selama proses rolling replacement instans berlangsung.

##### Bagian 3: Production Scenarios
11. **B**: Mengamankan deployment wajib memadukan integritas kapasitas (`min_healthy_percentage`), lifecycle check internal, dan integrasi CloudWatch Rollback Alarm untuk rollback otomatis saat alarm threshold breached.
12. **A**: ENA Express memanfaatkan protokol Scalable Reliable Datagram (SRD) milik AWS untuk memecah paket jaringan melintasi multi-path fabric, meredam jitter dan tail latency (P99) secara signifikan.
13. **B**: Kunci elastisitas Spot adalah diversifikasi lintas AZ dan lintas tipe instance (*instance families*). Menggunakan `price-capacity-optimized` memastikan alokasi dialihkan ke pool berkapasitas besar lain saat salah satu AZ mengalami kekurangan resource.

---

### 16. Summary

1. **AWS Nitro System** merevolusi arsitektur compute cloud dengan memindahkan network (ENA), storage (EBS), dan sistem manajemen dari software hypervisor ke hardware offload ASIC Nitro Cards. Hal ini memberikan akses performa near-bare-metal, memangkas I/O jitter, serta mengoptimalkan penggunaan CPU/RAM untuk workload produksi.
2. **Auto Scaling Group Lanjutan** bukan sekadar peluncur server statis, melainkan sebuah Finite State Machine (FSM) terdistribusi. Penggunaan **Lifecycle Hooks** (`Pending:Wait` dan `Terminating:Wait`) wajib diterapkan pada sistem enterprise untuk memastikan validasi kesiapan instance sebelum menerima trafik dan *graceful connection draining* saat instans ditarik.
3. **Optimasi Biaya & Ketersediaan** dicapai melalui perpaduan **Mixed Instances Policy** dengan alokasi `price-capacity-optimized`, integrasi **Capacity Rebalance**, serta pemanfaatan **Warm Pools**. Pendekatan ini memungkinkan reduksi pengeluaran hingga 70% menggunakan Spot Instances dengan tingkat reliability setara On-Demand.
4. **Metrik dan Scaling Responsif** memerlukan pemahaman mendalam terhadap matematika kontrol loop: mengombinasikan Target Tracking untuk kurva beban umum, Step Scaling untuk lonjakan bursty, serta Predictive Scaling berbasis Machine Learning guna mengeliminasi latensi *cold-start* aplikasi.