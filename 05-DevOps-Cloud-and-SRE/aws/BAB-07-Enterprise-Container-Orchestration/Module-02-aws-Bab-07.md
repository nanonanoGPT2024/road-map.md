# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 05-DevOps-Cloud-and-SRE  
**Bab 07:** Enterprise Container Orchestration (AWS EKS & ECS)

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedah (Analyze & Deconstruct)** arsitektur internal bidang kendali (*control plane*) dan bidang data (*data plane*) Amazon EKS pada level sistem operasi, runtime, dan jaringan AWS.
- **Mengimplementasikan Arsitektur Jaringan Tingkat Lanjut** menggunakan AWS VPC CNI dengan *Prefix Delegation*, *Custom Networking*, dan integrasi *Network Policy* bawaan guna mengatasi masalah *IP exhaustion*.
- **Mendesain Mekanisme Autoscaling Dinamis Berkinerja Tinggi** menggunakan Karpenter v1.x untuk menggantikan legacy Kubernetes Cluster Autoscaler (CAS), memangkas *node bootstrap latency* hingga di bawah 45 detik.
- **Mengamankan Akses Identitas Pod ke Layanan AWS** menggunakan *EKS Pod Identity* dan *IAM Roles for Service Accounts (IRSA)* dengan prinsip *Least Privilege* dan evaluasi berbasis atribut (*ABAC*).
- **Membangun Pipeline Observabilitas Terdistribusi dan GitOps Produksi** dengan OpenTelemetry, CloudWatch Container Insights with Enhanced Observability, dan ArgoCD.

---

## 2. Prerequisites
Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Networking AWS:** Konsep Subnet, VPC, Route Table, NAT Gateway, Security Group, serta alokasi CIDR blok IPv4/IPv6.
- **Fondasi Kubernetes:** Siklus hidup Pod, Deployment, DaemonSet, StatefulSet, CRD (*Custom Resource Definition*), serta primitives otorisasi RBAC Kubernetes.
- **Fondasi AWS IAM:** Policy evaluation logic, IAM Trust Relationships, OpenID Connect (OIDC) Federations, dan STS (*Security Token Service*).
- **Infrastruktur sebagai Kode (IaC):** Kemampuan membaca dan menyusun modul Terraform/OpenTofu tingkat menengah (*HCL syntax, state management, provider configuration*).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 EKS Control Plane Architecture & Cross-Account Elastic Network Interfaces (ENI)
Amazon EKS memisahkan bidang kendali (*control plane*) dan bidang data (*data plane*) ke dalam dua akun AWS yang berbeda:
1. **AWS Managed Account:** Menjalankan instance virtual machine khusus yang memuat instance `kube-apiserver`, `etcd` (dalam konfigurasi 3-node multi-AZ terdistribusi), `kube-controller-manager`, dan `cloud-controller-manager`.
2. **Customer AWS Account:** Menampung node worker (EC2 atau Fargate), Pod, serta VPC pengguna.

Koneksi antara kedua akun ini dijembatani oleh **Cross-Account Elastic Network Interfaces (X-Account ENI)**.

```
+-------------------------------------------------------------------------+
|                       AWS Managed Account (Control Plane)               |
|  +--------------------+   +--------------------+   +-----------------+  |
|  | kube-apiserver     |   | etcd cluster (HA)  |   | kube-controller |  |
|  | (Network Load Bal) |   | (Multi-AZ Encrypt) |   | manager         |  |
|  +---------+----------+   +--------------------+   +-----------------+  |
+------------|------------------------------------------------------------+
             | AWS Private Network link (TLS 1.3)
+------------|------------------------------------------------------------+
|            v                                                            |
|  +-------------------+  (Cross-Account ENI injected into Customer VPC)  |
|  | Control Plane ENI |  Subnet A, B, C                                  |
|  +---------+---------+                                                  |
|            |                                                            |
|  Customer VPC (Data Plane)                                              |
|            |                                                            |
|    +-------v-------------------------+      +-----------------------+   |
|    | Worker Node (EC2 / Bottlerocket)|      | Karpenter Provisioner |   |
|    | +-----------------------------+ |      | Controller            |   |
|    | | kubelet / containerd        | |      +-----------------------+   |
|    | +-----------------------------+ |                                  |
|    | | aws-k8s-cni (IPAM daemon)   | |                                  |
|    | +-----------------------------+ |                                  |
|    +---------------------------------+                                  |
+-------------------------------------------------------------------------+
```

Saat worker node atau operator internal berkomunikasi dengan `kube-apiserver`, paket dilewatkan melalui antarmuka ENI privat ini tanpa melintasi internet publik jika *EKS Endpoint Private Access* aktif. `etcd` dikelola secara otomatis oleh AWS dengan auto-compaction, periodik defragmentation, dan snapshot reguler ke S3 internal yang terisolasi.

### 3.2 AWS VPC CNI Internals & The Mechanics of Prefix Delegation
Secara default, plugin AWS VPC CNI (`amazon-k8s-cni`) menetapkan alamat IP sekunder privat dari subnet VPC langsung ke setiap Pod. Pendekatan ini memungkinkan Pod diperlakukan sebagai entitas kelas satu di jaringan AWS, namun memiliki kelemahan: batas jumlah Pod per node (*pod density*) dibatasi secara ketat oleh jumlah ENI dan batas IP sekunder per antarmuka instance EC2.

Untuk mengatasi ini, AWS VPC CNI mengimplementasikan **Prefix Delegation**.
- Alih-alih mengalokasikan satu IP `/32` per slot IP sekunder, EC2 runtime meminta alokasi blok prefiks IPv4 berukuran `/28` (16 alamat IP berurutan) ke ENI.
- **Kalkulasi Pod Density:**
  $$\text{Max Pods} = (\text{Number of ENIs} \times (\text{IPs per ENI} - 1) \times 16) + 2$$
  *(Konfigurasi aktual disesuaikan via batas default node atau flag `--max-pods` pada kubelet).*

Di balik layar, daemon `aws-node` (terdiri dari binary CNI dan L-IPAM daemon / `ipamd`):
1. Mengakses EC2 IMDSv2 (*Instance Metadata Service*) untuk mendeteksi tipe instance dan ENI.
2. Memanggil EC2 API `AssignIpv4Prefixes` via instance profile atau Pod Identity.
3. Mengelola *warm pool* prefiks lokal di memori node menggunakan parameter `WARM_PREFIX_TARGET`, `MINIMUM_IP_TARGET`, dan `WARM_IP_TARGET`.

### 3.3 EKS Pod Identity vs. IRSA (IAM Roles for Service Accounts)
Secara historis, IRSA bergantung pada OpenID Connect (OIDC) Identity Provider yang terdaftar di IAM:
1. `kube-apiserver` memproyeksikan token JWT bersandi RSA yang ditandatangani oleh EKS cluster OIDC issuer URL ke dalam Pod volume (`/var/run/secrets/eks.amazonaws.com/serviceaccount/token`).
2. AWS SDK pada pod membaca token dan memanggil `sts:AssumeRoleWithWebIdentity`.
3. AWS STS memvalidasi token terhadap EKS OIDC endpoint, lalu menerbitkan kredensial sementara (*AccessKeyId, SecretAccessKey, SessionToken*).

**EKS Pod Identity (Generasi Baru):**
Menghilangkan kompleksitas konfigurasi trust policy berbasis OIDC URL dan membatasi skalabilitas mutating webhook.
- Sebuah daemon agent (`eks-pod-identity-agent`) berjalan sebagai DaemonSet di setiap node.
- Agent mendengarkan permintaan otentikasi lokal pada endpoint link-local atau via socket.
- Pod Identity mengonfigurasi variabel lingkungan `AWS_CONTAINER_CREDENTIALS_FULL_URI` langsung ke Pod.
- SDK memanggil endpoint agent lokal; agent meneruskan permintaan ke EKS Auth API menggunakan kredensial instance host, yang kemudian mengembalikan kredensial peran IAM yang dialokasikan khusus untuk *ServiceAccount* tersebut melalui panggilan `sts:AssumeRole` terkontrol via EKS Service Principal (`pods.eks.amazonaws.com`).

### 3.4 Karpenter Architecture & Just-In-Time Provisioning
Berbeda dengan legacy Cluster Autoscaler yang memanipulasi AWS Auto Scaling Groups (ASG) secara reaktif dan lambat, Karpenter langsung berinteraksi dengan **AWS EC2 Fleet API**.

```
+--------------------------------------------------------------------------+
| Karpenter Controller Loop                                                |
|                                                                          |
| 1. Watch Pending Pods     --> Pod spec requirements:                     |
|                               (CPU, Mem, Arch, Topology, Zone, Spot/OD)  |
|                                         |                                |
| 2. Bin-Packing Simulation --> Calculates optimal EC2 instance types      |
|                               (e.g., 1x m6i.xlarge vs 2x c6i.large)      |
|                                         |                                |
| 3. EC2 Fleet API Call     --> Direct single-call batch launch            |
|                               Bypasses Auto Scaling Groups               |
|                                         |                                |
| 4. Node Join & Ready      --> Node boots via custom AMI (Bottlerocket)   |
|                               Joins cluster via EKS API within seconds   |
|                                         |                                |
| 5. Continuous Consolidation-> Evaluates underutilized nodes and          |
|                               reschedules pods to terminate waste.       |
+--------------------------------------------------------------------------+
```

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal di Skala Enterprise?
1. **IP Exhaustion (Kehabisan Alamat IP):** Pada arsitektur VPC enterprise standar, subnet `/20` atau `/19` dapat terkuras dalam hitungan hari jika setiap Pod mengonsumsi satu IP VPC utuh tanpa arsitektur Secondary CIDR atau Prefix Delegation.
2. **Autoscaling Sluggishness:** Cluster Autoscaler membutuhkan waktu 3-8 menit untuk mendeteksi *pending pods*, menaikkan kapasitas ASG, menunggu VM inisialisasi, dan menjalankan bootstrap script `bootstrap.sh`. Pada insiden lonjakan beban ekstrem (misal: *Flash Sale*), waktu ini menyebabkan lonjakan HTTP 503 dan degradasi SLA.
3. **IAM Management Overhead:** Mengelola OIDC provider untuk ratusan cluster EKS menciptakan duplikasi IAM Role Trust Relationship raksasa yang menabrak batas karakter dokumen IAM Policy (32 KB limit).

### Apa Solusi Arsitektur Modern Ini?
- **AWS VPC CNI + Secondary CIDR + Prefix Delegation:** Mengisolasi alamat IP Pod ke dalam blok RFC 6598 non-routable (`100.64.0.0/10`) di dalam cluster, menghemat IP korporat primer (`10.x.x.x`) sembari mempertahankan performa kecepatan kernel tanpa overhead NAT overlay.
- **Karpenter v1.x:** Provisioning berbasis model *group-less* yang langsung memilih instance EC2 termurah, tercepat, dan paling sesuai dari puluhan tipe instance yang tersedia dalam kurun waktu puluhan detik.
- **EKS Pod Identity:** Sentralisasi pemetaan IAM Role ke Kubernetes ServiceAccount tanpa mutasi trust policy berbasis OIDC yang rentan terhadap human error.

---

## 5. How (Workflow Detail)

Berikut adalah siklus hidup Pod mulai dari deployment hingga eksekusi dengan otentikasi IAM dan alokasi IP:

```
[Developer / ArgoCD]
        |
   Apply Deployment
        |
        v
[kube-apiserver] <---------------- Mutating Webhook (EKS Pod Identity)
        |                           Injects: AWS_CONTAINER_CREDENTIALS_FULL_URI
        |                                    AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE
   Pod Created (Status: Unschedulable)
        |
        +-----------------------------------+
        |                                   |
        v                                   v
[kube-scheduler]                    [Karpenter Controller]
(Fails: No node fits)               1. Detects unschedulable pod
                                    2. Evaluates NodePool constraints
                                    3. Invokes ec2:CreateFleet
                                    4. EC2 Instance boots (Bottlerocket)
                                            |
                                            v
                                    [Node Joins Cluster]
                                            |
                                            v
[kubelet on Node] <-------------------------+
1. Pulls container images
2. Triggers CNI plugin (aws-k8s-cni)
        |
        v
[L-IPAM Daemon (ipamd)]
Assigns IPv4 from pre-allocated /28 Prefix to Pod veth pair
        |
        v
[Pod Starts Container]
        |
        +---> Pod makes AWS SDK call (e.g., S3 PutObject)
                   |
                   v
              [HTTP Request to Local Pod Identity Agent via Link-Local]
                   |
                   v
              [Agent validates token with EKS Auth & STS]
                   |
                   v
              [Pod gets temporary AWS credentials -> S3 operation succeeds]
```

---

## 6. Analogy & Diagram ASCII

### Analogi Operasional:
Bayangkan EKS sebagai **Sistem Transportasi Taksi Perusahaan Korporat**:
- **Legacy Cluster Autoscaler & ASG:** Seperti memesan armada bus hanya dari satu tipe (misal: bus 50 kursi). Jika ada 3 orang pegawai lembur yang butuh tumpangan, Anda terpaksa menyewa 1 bus besar utuh dan menunggu 30 menit sopir datang dari pangkalan.
- **Karpenter:** Seperti sistem pemesanan armada cerdas instan. Jika ada 3 orang lembur, sistem langsung mendatangkan 1 sedan listrik dalam 45 detik. Jika ada 100 orang, sistem mendatangkan kombinasi 1 bus, 2 van, dan 1 sedan secara instan dengan harga termurah.
- **VPC CNI Prefix Delegation:** Daripada meminta izin 1 kartu akses gedung kantor untuk tiap individu penumpang (yang menghabiskan kuota kartu harian gedung), pimpinan regu meminta 1 bundel kartu berisi 16 akses sekaligus, lalu mendistribusikannya secara mandiri di lapangan.

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Karpenter NodePool Dasar (v1 API)
Manifest dasar Karpenter untuk provisioning instance spot komputasi umum:

```yaml
# karpenter-nodepool-simple.yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: general-compute
spec:
  template:
    spec:
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: default
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot"]
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64", "arm64"]
        - key: karpenter.k8s.aws/instance-category
          operator: In
          values: ["c", "m", "r"]
        - key: karpenter.k8s.aws/instance-generation
          operator: Gt
          values: ["5"]
  limits:
    cpu: 1000
    memory: 4000Gi
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 1m
```

---

### 7.2 Practical Example: Enterprise Infrastructure as Code (Terraform)
Konfigurasi terpadu untuk VPC CNI Prefix Delegation, EKS Pod Identity, dan Karpenter Infrastructure Setup.

```hcl
# main.tf
terraform {
  required_version = ">= 1.8.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# --- VPC CNI CONFIGURATION (ADDON) ---
resource "aws_eks_addon" "vpc_cni" {
  cluster_name                = aws_eks_cluster.enterprise.name
  addon_name                  = "vpc-cni"
  addon_version               = "v1.18.1-eksbuild.1"
  resolve_conflicts_on_update = "OVERWRITE"

  configuration_values = jsonencode({
    env = {
      # Enable Prefix Delegation to mitigate IP exhaustion
      ENABLE_PREFIX_DELEGATION = "true"
      WARM_PREFIX_TARGET       = "1"
      # Enforce secure metadata service
      POD_SECURITY_GROUP_ENFORCING_MODE = "standard"
    }
  })
}

# --- EKS POD IDENTITY AGENT ADDON ---
resource "aws_eks_addon" "pod_identity" {
  cluster_name                = aws_eks_cluster.enterprise.name
  addon_name                  = "eks-pod-identity-agent"
  addon_version               = "v1.3.0-eksbuild.1"
  resolve_conflicts_on_update = "OVERWRITE"
}

# --- IAM ROLE UNTUK WORKLOAD VIA POD IDENTITY ---
resource "aws_iam_role" "payment_processor_role" {
  name = "payment-processor-pod-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "pods.eks.amazonaws.com"
        }
        Action = [
          "sts:AssumeRole",
          "sts:TagSession"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "payment_processor_policy" {
  name = "DynamoDBReadWriteAccess"
  role = aws_iam_role.payment_processor_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/Payments"
      }
    ]
  })
}

# --- EKS POD IDENTITY ASSOCIATION ---
resource "aws_eks_pod_identity_association" "payment_processor" {
  cluster_name    = aws_eks_cluster.enterprise.name
  namespace       = "finance"
  service_account = "payment-processor-sa"
  role_arn        = aws_iam_role.payment_processor_role.arn
}

# --- KARPENTER EC2NODECLASS (CRD MANIFEST) ---
# Diterapkan via Terraform menggunakan kubectl/helm provider pada implementasi riil
```

Manifest EC2NodeClass pendamping untuk sistem berbasis sistem operasi aman **Bottlerocket**:

```yaml
# ec2nodeclass-production.yaml
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: secure-bottlerocket
spec:
  amiFamily: Bottlerocket
  role: "KarpenterNodeRole-EnterpriseEKS"
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: "enterprise-cluster"
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: "enterprise-cluster"
  blockDeviceMappings:
    - deviceName: /dev/xvda
      ebs:
        volumeSize: 4Gi
        volumeType: gp3
        encrypted: true
    - deviceName: /dev/xvdb
      ebs:
        volumeSize: 100Gi
        volumeType: gp3
        iops: 3000
        throughput: 125
        encrypted: true
        deleteOnTermination: true
  metadataOptions:
    httpEndpoint: enabled
    httpProtocolIPv6: disabled
    httpPutResponseHopLimit: 1
    httpTokens: required # Enforce IMDSv2 strictly
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Tier-1 FinTech Core Banking Platform (50,000 TPS Flash Transaction)
- **Kondisi Awal:**
  Platform pembayaran digital memproses transaksi dengan cluster EKS yang terdiri dari 350 worker node instance `m5.2xlarge` statis via Auto Scaling Groups. 
- **Bencana yang Muncul:**
  Saat kampanye tanggal kembar nasional, lonjakan transaksi memicu kebutuhan 6.000 Pod baru dalam 2 menit.
  1. *IP Exhaustion:* Subnet `/18` kehabisan alokasi IP lokal dalam 90 detik karena konfigurasi VPC CNI standard tanpa prefix delegation. Pod baru terperangkap di status `ContainerCreating` dengan error CNI `Address already in use`.
  2. *Autoscaling Bottleneck:* Cluster Autoscaler membutuhkan 6,5 menit untuk meluncurkan node baru. EC2 API terkena *rate-limiting* (`RequestLimitExceeded`).
  3. Transaksi gagal (*failed checkout*) mencapai 28,4%, dengan estimasi kerugian $1.2M per jam.

- **Solusi Arsitektural yang Diterapkan:**
  1. **Alokasi Secondary VPC CIDR:** Menambahkan blok non-routable `100.64.0.0/16` khusus untuk Pod. Subnet worker node tetap di CIDR primer `10.0.0.0/16`. Mengaktifkan `ENABLE_PREFIX_DELEGATION = true`.
  2. **Migrasi ke Karpenter v1.x:** Menghapus 8 Auto Scaling Groups statis. Mengonfigurasi satu `NodePool` yang mengizinkan variasi 40+ tipe instance keluarga compute dan memory-optimized (`c6i`, `c6a`, `m6i`, `m6a`, `c7g`, `m7g`), dengan pemanfaatan instance Graviton (ARM64) berbasis harga termurah.
  3. **Migrasi dari IRSA ke EKS Pod Identity:** Mengeliminasi latensi verifikasi token OIDC publik dan menghindari limit mutasi API STS.
  4. **Adopsi OS Bottlerocket:** Menggantikan standard Amazon Linux 2 dengan Bottlerocket OS untuk mempercepat waktu cold boot node dari 140 detik menjadi 35 detik.

- **Hasil/Dampak Bisnis:**
  - Waktu respons scaling turun drastis: Karpenter meluncurkan kapasitas 1.200 vCPU dalam 42 detik.
  - Alokasi IP per node naik dari 29 Pod menjadi 110 Pod per instance tanpa memakan IP routable internal korporat.
  - Biaya komputasi turun sebesar **43%** berkat konsolidasi otomatis Pod (*disruption/consolidation*) dan adopsi terukur EC2 Spot Instance untuk worker non-stateful.

---

## 9. Trade-offs & Architecture Decision Matrix

| Dimensi Arsitektur | Opsi A: EKS Pod Identity | Opsi B: IRSA (OIDC Based) | Analisis Trade-off & Latensi |
| :--- | :--- | :--- | :--- |
| **Arsitektur Otentikasi** | Daemon agent link-local lokal + EKS API | AWS STS + OIDC Web Identity Provider | Pod Identity memiliki dependensi pada daemon agent per node; IRSA tidak memerlukan daemon lokal. |
| **Batas Skalabilitas** | Skala tinggi; terisolasi per akun AWS & EKS auth service | Dibatasi oleh STS quota & ukuran OIDC policy trust statement | Pod Identity memecah IAM mapping keluar dari file dokumen IAM role trust boundary. |
| **Performa Latensi Token** | Rendah (<5ms via socket host) | Menengah (10-35ms panggilan web identity) | Pod Identity mengeliminasi lonjakan latensi otentikasi eksternal saat pod cold-start. |

| Dimensi Autoscaling | Opsi A: Karpenter | Opsi B: Cluster Autoscaler (CAS) | Analisis Trade-off & Latensi |
| :--- | :--- | :--- | :--- |
| **Mekanisme Provisioning** | Direct EC2 Fleet API (`ec2:CreateFleet`) | AWS EC2 Auto Scaling Groups (ASG) | Karpenter memotong *orchestration layer* ASG, langsung berinteraksi dengan hypervisor fleet AWS. |
| **Kecepatan Scale-Up** | Sangat Cepat (30-50 detik hingga Pod running) | Lambat (3-8 menit akibat ASG pooling loop) | CAS terikat pada evaluasi berkala ASG cooldown timers dan launch template abstraction. |
| **Bin-Packing & Efisiensi** | Otomatis & Terus-menerus (*Consolidation*) | Terbatas (hanya scale-down node kosong) | Karpenter secara aktif memindahkan pod untuk menukar instance besar yang boros dengan tipe lebih kecil/murah. |
| **Kompleksitas Manajemen** | Memerlukan instalasi controller & CRD baru | Bawaan ekosistem Kubernetes, sangat teruji | Karpenter menuntut pemahaman mendalam tentang *node disruption budget* agar tidak mengganggu aplikasi. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Karpenter Node Launch Loop (EC2 CreateFleet Failure)
- **Gejala:** Pod berstatus `Pending`, Karpenter log mencetak pesan: `ICE (Insufficient Capacity Error)` atau `UnauthorizedOperation: You are not authorized to perform this operation`.
- **Root Cause:** IAM Role milik Karpenter Controller kekurangan izin `iam:PassRole` untuk instance profile yang diteruskan ke EC2 instance, atau subnet tidak memiliki tag discovery Karpenter: `karpenter.sh/discovery: <cluster-name>`.
- **Solusi & Troubleshooting:**
  ```bash
  # Periksa log controller karpenter
  kubectl logs -n kube-system -l app.kubernetes.io/name=karpenter -c controller --tail=100 | jq .
  
  # Verifikasi tag pada subnet cluster
  aws ec2 describe-subnets --filters "Name=tag:karpenter.sh/discovery,Values=enterprise-cluster" \
    --query "Subnets[*].[SubnetId,CidrBlock,Tags]" --output table
  ```

### 2. VPC CNI Prefix Delegation / Pod IP Allocation Failure
- **Gejala:** Pod tertahan di status `ContainerCreating`. Deskripsi event menunjukkan: `Failed to create pod sandbox: rpc error: code = Unknown desc = failed to setup network for sandbox: failed to allocate for range 0: no IP addresses available in range`.
- **Root Cause:** Subnet kehabisan blok contiguous `/28` IPv4. Prefix delegation membutuhkan 16 alamat IP berturutan yang tidak terfragmentasi. Jika subnet sangat terfragmentasi oleh alokasi IP sekunder individual, alokasi prefiks gagal total.
- **Solusi:**
  Aktifkan subnet sekunder atau lakukan transisi ke IPv6 atau subnet baru khusus compute pod. Lakukan audit fragmentasi via AWS CLI:
  ```bash
  aws ec2 describe-subnets --subnet-ids subnet-0123456789abcdef0 \
    --query "Subnets[0].AvailableIpAddressCount"
  ```
  Set flag VPC CNI untuk membersihkan fragmentasi agresif:
  ```bash
  kubectl set env daemonset aws-node -n kube-system WARM_IP_TARGET=5
  kubectl set env daemonset aws-node -n kube-system MINIMUM_IP_TARGET=10
  ```

### 3. EKS Pod Identity Association Not Effective
- **Gejala:** Workload Pod mengembalikan pesan error `AccessDeniedException` saat mengakses DynamoDB/S3, padahal IAM Role dan Association sudah didefinisikan.
- **Root Cause:** 
  1. DaemonSet `eks-pod-identity-agent` belum berjalan atau diblokir oleh NetworkPolicy.
  2. Aplikasi menggunakan AWS SDK versi lama yang belum mendukung pemanggilan `AWS_CONTAINER_CREDENTIALS_FULL_URI`.
- **Solusi:**
  ```bash
  # 1. Pastikan agent pod running di node tempat pod berada
  kubectl get pods -n kube-system -l app.kubernetes.io/name=eks-pod-identity-agent -o wide

  # 2. Exec ke dalam pod untuk menguji konektivitas agent local
  kubectl exec -it <pod-name> -n <namespace> -- env | grep AWS_CONTAINER
  # Pastikan URI terisi: http://169.254.170.23/v1/credentials
  ```

---

## 11. Best Practices (Production Checklist)

### Bidang Kendali (Control Plane)
- [ ] Aktifkan **EKS Cluster Control Plane Logging** (minimal `api`, `audit`, dan `authenticator`) dan kirim ke Amazon CloudWatch Logs dengan retensi terdefinisi (misal: 90 hari) dengan enkripsi KMS.
- [ ] Nonaktifkan akses publik endpoint API EKS (`endpointPublicAccess: false`) atau gunakan restricted CIDR whitelist jika akses direct via bastion/VPN diwajibkan.
- [ ] Konfigurasikan minimal 3 Private Subnet pada 3 Availability Zone (AZ) berbeda untuk penempatan control plane ENI.

### Bidang Data (Data Plane & Worker Nodes)
- [ ] Terapkan sistem operasi minimalis yang tidak dapat diubah (*immutable*), seperti **Bottlerocket**, untuk mengurangi *attack surface* dan waktu inisialisasi node.
- [ ] Pastikan **IMDSv2** wajib diaktifkan (`httpTokens: required`) dan set `httpPutResponseHopLimit: 1` pada node yang menampung pod tanpa host networking untuk mencegah eksfiltrasi token IAM node oleh pod jahat.
- [ ] Atur batas *Pod Disruption Budget* (PDB) pada seluruh workload produksi agar mekanisme konsolidasi Karpenter tidak menyebabkan *downtime*.

### Jaringan (Networking)
- [ ] Aktifkan `ENABLE_PREFIX_DELEGATION=true` bersamaan dengan `WARM_PREFIX_TARGET=1`.
- [ ] Gunakan **Amazon VPC CNI Network Policy Engine** (berbasis eBPF) atau Cilium untuk menerapkan micro-segmentation Zero-Trust tanpa latency proxy `iptables`.

### Keamanan (Security & Identity)
- [ ] Hentikan penyematan (*hardcoding*) IAM policy pada level Node Instance Profile. Seluruh workload wajib menggunakan **EKS Pod Identity** atau **IRSA**.
- [ ] Terapkan validasi Kubernetes Admission Controller (Kyverno atau OPA Gatekeeper) untuk memblokir penempatan pod dengan `hostNetwork: true` atau akses ke direktori sensitif host (`/var/run/docker.sock`, `/etc/kubernetes`).

---

## 12. Hands-on Practice

Simpan seluruh file praktikum ini ke dalam direktori lokal: `hands-on/m02/`.

### Langkah 1: Persiapan Environment & File Struktur
```bash
mkdir -p hands-on/m02/{terraform,manifests}
cd hands-on/m02
```

### Langkah 2: Kode Terraform untuk Provisioning EKS, VPC CNI & Pod Identity
Tulis kode berikut ke dalam `terraform/eks-advanced.tf`:

```hcl
# hands-on/m02/terraform/eks-advanced.tf
variable "cluster_name" {
  default = "production-core-eks"
}

variable "region" {
  default = "us-east-1"
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# EKS Cluster IAM Role
resource "aws_iam_role" "cluster_role" {
  name = "${var.cluster_name}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster_role.name
}

# EKS Cluster Resource
resource "aws_eks_cluster" "main" {
  name     = var.cluster_name
  role_arn = aws_iam_role.cluster_role.arn
  version  = "1.30"

  vpc_config {
    subnet_ids              = data.aws_subnets.default.ids
    endpoint_private_access = true
    endpoint_public_access  = true
  }

  depends_on = [aws_iam_role_policy_attachment.cluster_policy]
}

# Base Node Group untuk Karpenter Controller
resource "aws_iam_role" "node_group_role" {
  name = "${var.cluster_name}-node-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "node_policies" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  ])
  policy_arn = each.value
  role       = aws_iam_role.node_group_role.name
}

resource "aws_eks_node_group" "system_nodes" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "system-critical"
  node_role_arn   = aws_iam_role.node_group_role.arn
  subnet_ids      = data.aws_subnets.default.ids

  scaling_config {
    desired_size = 2
    max_size     = 3
    min_size     = 2
  }

  instance_types = ["m6i.large"]

  labels = {
    "node.kubernetes.io/scope" = "system"
  }

  depends_on = [aws_iam_role_policy_attachment.node_policies]
}

# EKS Addons
resource "aws_eks_addon" "vpc_cni" {
  cluster_name  = aws_eks_cluster.main.name
  addon_name    = "vpc-cni"
  configuration_values = jsonencode({
    env = {
      ENABLE_PREFIX_DELEGATION = "true"
      WARM_PREFIX_TARGET       = "1"
    }
  })
}

resource "aws_eks_addon" "pod_identity" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "eks-pod-identity-agent"
}
```

### Langkah 3: Karpenter NodePool & EC2NodeClass Manifests
Tulis konfigurasi Karpenter ke `manifests/karpenter-rules.yaml`:

```yaml
# hands-on/m02/manifests/karpenter-rules.yaml
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: enterprise-nodeclass
spec:
  amiFamily: AL2023
  role: "KarpenterNodeRole-production-core-eks"
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: "production-core-eks"
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: "production-core-eks"
  metadataOptions:
    httpEndpoint: enabled
    httpTokens: required
    httpPutResponseHopLimit: 1
---
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: enterprise-workload-pool
spec:
  template:
    spec:
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: enterprise-nodeclass
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"]
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64", "arm64"]
        - key: karpenter.k8s.aws/instance-family
          operator: In
          values: ["c6i", "c7g", "m6i", "m7g"]
  limits:
    cpu: 200
    memory: 800Gi
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 30s
```

### Langkah 4: Workload Testing Deployment dengan High Replicas
Tulis manifest uji beban ke `manifests/load-workload.yaml`:

```yaml
# hands-on/m02/manifests/load-workload.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: high-density-processor
  namespace: default
spec:
  replicas: 80
  selector:
    matchLabels:
      app: processor
  template:
    metadata:
      labels:
        app: processor
    spec:
      containers:
      - name: worker
        image: public.ecr.aws/eks-distro/kubernetes/pause:3.9
        resources:
          requests:
            cpu: "200m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
```

### Langkah 5: Eksekusi & Validasi Lapangan
1. Terapkan Terraform:
   ```bash
   cd hands-on/m02/terraform
   terraform init
   terraform apply -auto-approve
   ```
2. Hubungkan context `kubectl` lokal:
   ```bash
   aws eks update-kubeconfig --region us-east-1 --name production-core-eks
   ```
3. Verifikasi ketersediaan Prefix Delegation pada daemonset AWS CNI:
   ```bash
   kubectl get daemonset aws-node -n kube-system -o yaml | grep ENABLE_PREFIX_DELEGATION -A 1
   ```
4. Deploy rules Karpenter dan beban pengujian:
   ```bash
   kubectl apply -f ../manifests/karpenter-rules.yaml
   kubectl apply -f ../manifests/load-workload.yaml
   ```
5. Pantau alokasi pod dan inisialisasi node instan:
   ```bash
   kubectl get pods -l app=processor -o wide --watch
   kubectl get nodes -l karpenter.sh/nodepool=enterprise-workload-pool -L node.kubernetes.io/instance-type,karpenter.sh/capacity-type
   ```

---

## 13. Exercises

### Level Easy (Mudah)
Modifikasi resource `aws_eks_addon` pada Terraform untuk mengubah nilai `WARM_PREFIX_TARGET` dari `1` menjadi `2`. Jalankan `terraform plan` dan jelaskan pengaruh parameter ini terhadap cadangan alokasi blok IP pada antarmuka jaringan instance EC2.

### Level Medium (Menengah)
Sebuah tim pengembang meluncurkan pod StatefulSet yang membutuhkan penyimpanan persisten berkecepatan tinggi di AWS. Buatlah manifest Kubernetes StorageClass menggunakan AWS EBS CSI Driver yang mengonfigurasi tipe volume `gp3`, enkripsi KMS dinamis, dan parameter `volumeBindingMode: WaitForFirstConsumer`. Hubungkan manifest ini dengan NodePool Karpenter yang membatasi provisioning node hanya pada Availability Zone `us-east-1a` dan `us-east-1b`.

### Level Hard (Mahir)
Rancang arsitektur ketersediaan tinggi multi-tenant di mana Pod dari Namespace `compliance-pci` dilarang keras dijadwalkan pada instance EC2 yang sama dengan Pod dari Namespace `general-workload`. Terapkan solusi ini menggunakan kombinasi Kubernetes Taints/Tolerations, Node Affinity, serta dua `NodePool` Karpenter terpisah yang memanfaatkan instance berlabel khusus dan terisolasi pada level subnet Security Group.

---

## 14. Challenge (Tantangan Kompleks Arsitektur)

### Konteks Skenario:
Sebuah platform streaming video global mengalami degradasi parah saat acara *World Championship Finale*. Sistem menerima lonjakan tiba-tiba sebesar 300.000 koneksi WebSocket konkuren. Tim infrastruktur mencoba melakukan scale-up pada node pool EKS, namun eksekusi terhenti akibat:
1. Limit kuota `vCPU Spot instances limit reached` pada region utama AWS.
2. Mekanisme autoscaling berbasis Auto Scaling Groups tidak dapat berpindah secara otomatis ke On-Demand instances tanpa intervensi manual.
3. Node yang ada mengalami *kernel network packet dropping* akibat antrian tabel conntrack Linux penuh (`nf_conntrack: table full, dropping packet`).

### Tugas Arsitek:
Rancang dokumen arsitektur dan spesifikasi konfigurasi (tanpa menggunakan solusi template statis standar) yang mencakup:
- Strategi failover *Fallback Prioritization* Karpenter dari Spot ke On-Demand secara instan tanpa menghentikan pod aktif yang sudah berjalan.
- Konfigurasi parameter sysctl kernel host tingkat lanjut pada Bottlerocket (`net.netfilter.nf_conntrack_max`, `net.core.somaxconn`) yang diinjeksi via konfigurasi bootstrap EC2NodeClass userdata.
- Desain arsitektur jaringan *EKS Multi-VPC / Mesh Topology* yang mendistribusikan beban Pod melintasi dua VPC terpisah menggunakan AWS VPC Lattice atau Transit Gateway untuk mengatasi keterbatasan kuota conntrack pada satu pasang ENI Gateway.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Apa fungsi utama dari alokasi *Prefix Delegation* pada AWS VPC CNI di Amazon EKS?
   - A. Mengganti protokol TCP menjadi UDP pada komunikasi antar-Pod.
   - B. Mengalokasikan blok prefiks `/28` IPv4 per slot IP ENI untuk meningkatkan densitas Pod per node dan mengatasi keterbatasan IP.
   - C. Mengenkripsi seluruh lalu lintas jaringan Pod menggunakan enkripsi hardware Nitro.
   - D. Menghubungkan EKS secara langsung ke AWS Direct Connect tanpa Virtual Private Gateway.

2. Komponen manakah yang diinjeksi oleh EKS ke dalam Customer VPC untuk menjembatani komunikasi privat antara bidang data dan bidang kendali?
   - A. Internet Gateway.
   - B. Transit Gateway Attachment.
   - C. Cross-Account Elastic Network Interface (X-Account ENI).
   - D. NAT Instance.

3. Pada arsitektur EKS Pod Identity, perantara lokal di node yang menerima request kredensial dari Pod adalah:
   - A. `aws-load-balancer-controller`
   - B. `eks-pod-identity-agent`
   - C. `kube-proxy`
   - D. `cluster-autoscaler`

4. Manakah versi IMDS yang diwajibkan untuk diimplementasikan secara ketat (`httpTokens: required`) pada sistem produksi enterprise?
   - A. IMDSv1
   - B. IMDSv2
   - C. IMDSv3
   - D. OIDC Metadata Provider

5. Di mana etcd database cluster EKS disimpan dan dikelola oleh AWS?
   - A. Di dalam EBS Volume yang terpasang pada Worker Node pertama.
   - B. Di dalam Customer Account terenkripsi S3.
   - C. Di AWS Managed Account yang terisolasi secara multi-AZ dan dikelola penuh oleh AWS.
   - D. Di dalam AWS DynamoDB table global.

---

### Bagian 2: Intermediate (Analisis Pilihan & Sebab-Akibat)
6. Mengapa Karpenter dianggap jauh lebih efisien dibanding Kubernetes Cluster Autoscaler (CAS) bawaan?
   - A. Karena Karpenter tidak menggunakan etcd untuk menyimpan state pod.
   - B. Karena Karpenter berinteraksi langsung dengan EC2 Fleet API tanpa abstraksi Auto Scaling Group dan dapat melakukan konsolidasi instance secara cerdas.
   - C. Karena Karpenter hanya mendukung instance tipe Spot yang berharga murah.
   - D. Karena Karpenter mematikan kubelet untuk mempercepat bootstrap instance.

7. Jika nilai `httpPutResponseHopLimit` disetel ke `1` pada EC2 Worker Node, apakah Pod yang berjalan dengan mode `hostNetwork: false` dapat mengakses IMDS host untuk mengambil peran instance?
   - A. Ya, karena Pod berbagi network namespace yang sama dengan host.
   - B. Tidak, karena paket melintasi batasan virtual bridge/veth interface (hop layer) sehingga TTL/Hop counter habis dan paket di-drop.
   - C. Ya, asalkan pod memiliki label `app: enterprise`.
   - D. Tidak, karena AWS memblokir semua panggilan IP `169.254.169.254` secara default.

8. Apa keuntungan utama arsitektur EKS Pod Identity dibandingkan IAM Roles for Service Accounts (IRSA)?
   - A. Pod Identity tidak membutuhkan IAM Role sama sekali di AWS IAM.
   - B. Pod Identity meniadakan kebutuhan konfigurasi manual Trust Policy berbasis OIDC URL dan mengatasi limitasi ukuran dokumen trust statement saat cluster diskalakan.
   - C. Pod Identity gratis, sedangkan IRSA memerlukan biaya langganan bulanan per role.
   - D. Pod Identity memungkinkan penugasan Root Access AWS langsung ke container.

9. Manakah parameter yang tepat pada AWS VPC CNI untuk memastikan ketersediaan alokasi alamat IP cadangan tanpa menguras subnet pool secara berlebihan?
   - A. `MINIMUM_IP_TARGET` dan `WARM_IP_TARGET`
   - B. `MAX_PODS_PER_NODE`
   - C. `AWS_VPC_K8S_CNI_LOGLEVEL=DEBUG`
   - D. `ENABLE_POD_ENI=false`

10. Sistem Operasi Bottlerocket memiliki karakteristik security boundary yang kuat untuk EKS worker node karena:
    - A. Memiliki package manager apt-get bawaan untuk update otomatis.
    - B. File system root bersifat read-only, tidak menyertakan SSH server default, dan update OS berjalan melalui skema partisi ganda (*A/B partition swap*).
    - C. Mengizinkan semua Pod berjalan dalam privilege mode.
    - D. Ditulis menggunakan bahasa Assembly tanpa kernel Linux.

---

### Bagian 3: Skenario Kasus Produksi
11. **Skenario Gangguan Skalabilitas:**
    Saat menguji beban 10.000 RPS, Karpenter berhasil meluncurkan 20 instance EC2 baru tipe `c6i.2xlarge`. Namun, separuh dari Pod aplikasi tetap tertahan pada status `Pending`. Saat diperiksa dengan `kubectl describe pod`, muncul pesan:
    `0/22 nodes are available: 20 node(s) had untolerated taint {karpenter.sh/unregistered: true}`.
    Tindakan mitigasi sistemik apa yang harus dievaluasi terlebih dahulu pada infrastruktur AWS?
    - A. Menghapus daemonset coreDNS dari cluster EKS.
    - B. Memeriksa izin instance IAM Role worker node untuk memvalidasi apakah node berhasil memanggil EKS API `DescribeCluster` dan melewati otentikasi bootstrap cluster.
    - C. Mengubah tipe instance menjadi `t3.micro`.
    - D. Merestart control plane EKS melalui AWS Management Console.

12. **Skenario Pelanggaran Enkripsi:**
    Sebuah audit keamanan FinTech mendapati bahwa lalu lintas antar-Pod di dalam node yang sama dan antar-node di subnet VPC yang sama terbaca sebagai plain text. Solusi modern native EKS apa yang paling tepat diimplementasikan tanpa memasang third-party service mesh berbobot berat (seperti Istio/Linkerd)?
    - A. Mengaktifkan fitur AWS VPC CNI Network Policy dengan WireGuard-based node-to-node Pod encryption atau enkripsi EC2 Nitro host-level encryption.
    - B. Mengganti semua pemanggilan HTTP menjadi format file Zip berpassword.
    - C. Menempatkan Classic Load Balancer di depan setiap Pod internal.
    - D. Menjalankan OpenVPN container di dalam setiap sidecar Pod.

13. **Skenario Interruption Termination Race Condition:**
    Aplikasi pemrosesan antrean batch berbasis AWS SQS dijalankan pada EC2 Spot Instances yang dikelola oleh Karpenter. Ketika AWS mengirimkan notifikasi *Spot Interruption Warning* (2 menit sebelum terminasi), pod langsung mati mendadak sebelum menyelesaikan pemrosesan data in-flight, mengakibatkan duplikasi data transaksi.
    Langkah arsitektur apa yang wajib dikonfigurasi untuk mencegah insiden ini?
    - A. Mematikan fitur Spot dan beralih permanen ke Dedicated Host.
    - B. Mengonfigurasi EventBridge rule untuk mendeteksi `EC2 Spot Instance Interruption Warning`, meneruskannya ke Karpenter Interruption SQS Queue, dan mengonfigurasi Pod spec dengan `terminationGracePeriodSeconds` serta handler sinyal `SIGTERM` yang elegan di kode aplikasi.
    - C. Menaikkan batas CPU memory request pod menjadi dua kali lipat.
    - D. Mengubah storage pod dari EmptyDir ke HostPath.

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **B** — Prefix Delegation mengalokasikan prefiks `/28` (16 IP per slot sekunder ENI), melipatgandakan batas densitas pod tanpa menguras alokasi alamat per individual IP.
2. **C** — Cross-Account ENI adalah jembatan virtual yang disuntikkan AWS ke subnet VPC pengguna untuk konektivitas dua arah control plane-data plane.
3. **B** — `eks-pod-identity-agent` adalah DaemonSet lokal yang menangani dan memvalidasi pertukaran token pod dengan STS.
4. **B** — IMDSv2 menggunakan session token berbasis HTTP PUT yang memblokir eksfiltrasi kredensial instance via SSRF vulnerabilities.
5. **C** — `etcd` berjalan di VPC terisolasi milik AWS (AWS Managed Account) dalam mode highly-available multi-AZ.

#### Bagian 2: Intermediate
6. **B** — Karpenter memotong layer Auto Scaling Groups, berinteraksi langsung dengan EC2 Fleet API, dan menghitung bin-packing secara instan berdasarkan kebutuhan komputasi pod yang tertunda.
7. **B** — Paket dari non-hostNetwork pod melewati bridge virtual (`veth`), menghabiskan batas 1 hop dari IMDSv2 response policy (`hopLimit: 1`), sehingga paket langsung ditolak oleh metadata service.
8. **B** — Pod Identity memisahkan relasi otorisasi dari dokumen policy trust OIDC raksasa, mengizinkan pengelolaan terpusat ribuan Pod-to-Role mappings langsung dari API EKS.
9. **A** — `WARM_IP_TARGET` dan `MINIMUM_IP_TARGET` membatasi agar ipamd daemon tidak mengambil terlalu banyak prefiks/IP yang tidak digunakan sekaligus dari VPC.
10. **B** — Bottlerocket dirancang khusus untuk container host: sistem berkas root bersifat immutable/read-only, tidak ada interpreter shell/SSH bawaan, dan pembaruan sistem berjalan via partisi A/B rollback otomatis.

#### Bagian 3: Skenario Kasus Produksi
11. **B** — Node baru yang baru diluncurkan oleh Karpenter diberi taint `unregistered` sampai node tersebut berhasil join ke cluster, terotentikasi via IAM auth/EKS access entry, dan statusnya dilaporkan `Ready` oleh kubelet ke kube-apiserver.
12. **A** — AWS Nitro Instance hardware encryption secara transparan mengenkripsi lalu lintas antar-Nitro instance, dan AWS VPC CNI eBPF/WireGuard engine menangani enkripsi overlay transit antar-pod.
13. **B** — Karpenter mengintegrasikan native SQS Interruption Queue yang menangkap pesan AWS Health & Spot Interruption 120 detik sebelumnya, memicu proses `kubectl drain` teratur dengan menghormati `terminationGracePeriodSeconds` dan siklus sinyal `SIGTERM`.

---

## 16. Summary
- **Arsitektur Produksi EKS Enterprise** bergantung pada pemisahan yang jelas antara bidang kendali terkelola AWS dan bidang data yang dioptimasi di dalam VPC pelanggan via Cross-Account ENI.
- **Efisiensi Jaringan:** Memaksimalkan utilitas jaringan AWS VPC CNI dengan **Prefix Delegation** dan isolasi CIDR Sekunder menyelesaikan limitasi mendasar keterbatasan alamat IPv4 korporat tanpa menurunkan performa kernel.
- **Skalabilitas Just-In-Time:** **Karpenter v1.x** mengubah paradigma autoscaling dari model statis berbasis kumpulan node (*node pool-centric / ASG*) menjadi provisioning dinamis berbasis kebutuhan pod (*workload-driven bin-packing*), mempercepat waktu inisialisasi node ke hitungan detik dan memangkas biaya infrastruktur via konsolidasi real-time.
- **Zero-Trust Identity:** Transisi dari IRSA tradisional ke **EKS Pod Identity** mempermudah tata kelola keamanan IAM skala besar, menyederhanakan penegakan prinsip *Least Privilege*, dan mengeliminasi overhead operasional pengelolaan OpenID Connect federation.