# Module 01: Enterprise Container Orchestration (AWS ECS, EKS, ECR, App Mesh, Service Connect, IRSA)

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis perbedaan arsitektur, operasional, dan finansial antara Amazon ECS (Fargate vs EC2) dan Amazon EKS (Managed Node Groups vs Karpenter).
- Mengonfigurasi dan mengamankan image registry enterprise menggunakan Amazon Elastic Container Registry (ECR) dengan automated image scanning, lifecycle policy, dan cross-region/cross-account replication.
- Mengimplementasikan konsep Least Privilege pada Pod/Task level menggunakan IAM Roles for Service Accounts (IRSA) dan ECS Task Execution/Task Roles.
- Merancang dan mengeksekusi arsitektur service-to-service communication berlatensi rendah menggunakan AWS Service Connect dan AWS App Mesh (Envoy proxy-based).
- Mengintegrasikan Karpenter v1.x+ sebagai high-performance cluster autoscaler untuk EKS guna memotong waktu provisioning node dari menit ke detik berbasis native EC2 Fleet API.

---

## 2. Prerequisite
- **Networking**: Pemahaman mendalam tentang AWS VPC, Subnet (Public/Private), Route Tables, NAT Gateways, VPC Endpoints (Privatelink), dan Security Groups.
- **Containerization**: Penguasaan Docker/OCI container runtime (Dockerfile, multi-stage builds, namespaces, cgroups, Layer caching).
- **Kubernetes Core**: Pemahaman objek Pod, Deployment, Service, ConfigMap, Secret, Mutating/Validating Admission Controllers.
- **IAM**: Penguasaan IAM Policies, AssumeRole, OIDC (OpenID Connect) Federation, dan Resource-based vs Identity-based policies.
- **CLI Tools**: AWS CLI v2 terinstal, `kubectl`, `eksctl`, `docker`, dan Terraform/OpenTofu versi >= 1.5.0.

---

## 3. Concept
Container Orchestration pada enterprise cloud environment bukan sekadar menjalankan container di atas mesin virtual; ini adalah sistem terdistribusi yang bertanggung jawab atas lifecycle, service discovery, zero-downtime deployment, traffic routing, security posture isolation, dan dynamic resource allocation.

AWS menyediakan dua platform utama:
1. **Amazon Elastic Container Service (ECS)**: Orchestrator opini AWS (opinionated) yang terintegrasi secara mendalam (*tightly coupled*) dengan layanan native AWS (IAM, CloudWatch, VPC, ALB).
2. **Amazon Elastic Kubernetes Service (EKS)**: Implementasi CNCF-conformant Kubernetes terkelola (*upstream-compatible*) yang memisahkan control plane availability SLA dari data plane worker nodes.

Keduanya didukung oleh:
- **Data Plane Abstraction**: Virtual Machine (EC2 Data Plane) vs Serverless Container Engine (AWS Fargate).
- **Identity Federation**: IRSA (IAM Roles for Service Accounts) yang memproyeksikan token OIDC jangka pendek berotasi otomatis ke dalam container untuk menghindari credential hardcoding.
- **Dynamic Autoscaling**: Karpenter yang menggantikan legacy Kubernetes Cluster Autoscaler dengan bypass ASG langsung ke EC2 Fleet API.
- **Service Mesh & Connect**: Layer 7 application networking melalui proxy terdistribusi (Envoy/App Mesh) atau agentless/managed agent consul-free abstraction (ECS Service Connect).

---

## 4. Why
Menjalankan container skala enterprise tanpa managed orchestrator atau menggunakan konfigurasi default menghasilkan tiga risiko sistemik utama:
1. **Security Blast Radius yang Masif**: Berbagi instance IAM Profile ke seluruh container di atas host yang sama memungkinkan container yang terkompromi mengakses metadata API host (`169.254.169.254`) dan mengambil hak akses seluruh aplikasi di VM tersebut.
2. **Scaling Bottleneck & Over-provisioning**: Kubernetes Cluster Autoscaler (CAS) terikat pada AWS Auto Scaling Groups (ASG). CAS membutuhkan waktu 3–8 menit untuk rebalancing ASG, memicu pod pending yang lama saat lonjakan traffic (*traffic spikes*).
3. **Network Complexity & MTTR Tinggi**: Service discovery berbasis DNS murni (CoreDNS/AWS Cloud Map) sering mengalami masalah caching stale records, time-out pada failover, dan hilangnya visibilitas L7 metrics (request latency, 5xx errors per route).

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1. Amazon ECS: Fargate vs EC2 Launch Type
| Dimensi | ECS di AWS Fargate | ECS di EC2 Data Plane |
| :--- | :--- | :--- |
| **Model Operasional** | Serverless (AWS mengelola patch OS, kernel, scaling host) | Infrastructure-as-a-Service (Pengguna mengelola AMI, agent, OS patching) |
| **Isolasi Keamanan** | Kernel-level isolation per Pod/Task (Hypervisor/Firecracker microVM) | Shared Kernel antar container dalam satu EC2 Host |
| **Networking** | Wajib `awsvpc` network mode (ENI dialokasikan per Task) | Pilihan: `host`, `bridge`, `none`, atau `awsvpc` |
| **Start-up Latency** | ~30 - 60 detik (Provisioning dynamic ENI + container pull) | ~2 - 10 detik (Image pre-cached pada persistent host) |
| **Storage Persistence** | Ephemeral storage (up to 200 GiB) atau mount Amazon EFS | EFS, EBS (via ECS managed volume mounting), local ephemeral NVMe |
| **Biaya** | Pay-per-vCPU & memory per detik (Premium unit cost) | Pay-per-EC2-instance terlepas dari utilizasi (Savings via Spot/RI) |

### 5.2. Amazon EKS Architecture
Control plane EKS bersifat *single-tenant*, dijalankan di VPC khusus yang dikelola AWS, terdiri dari minimal 2 API Server instances dan 3 etcd instances yang tersebar di 3 Availability Zones. EKS terhubung ke Data Plane customer melalui cross-account Elastic Network Interfaces (ENI).
- **Managed Node Groups (MNG)**: AWS mengotomatisasi lifecycle provisioning, graceful draining via Node Problem Detector, dan rolling update AMI. Namun, MNG tetap terikat pada AWS EC2 Auto Scaling Groups (ASG).
- **Karpenter**: Autoscaler generasi baru yang mengeliminasi abstraksi ASG. Karpenter mengamati Pods yang berstatus `Pending`, menghitung kebutuhan vCPU, memori, architecture (ARM64/AMD64), GPU, dan topology-spread constraint secara instan, lalu memanggil `ec2:CreateFleet` API secara langsung. Karpenter dapat memprovisioning instance optimal dalam waktu < 45 detik serta memiliki kapabilitas native node consolidation/bin-packing.

### 5.3. IAM Roles for Service Accounts (IRSA) Deep-Dive
IRSA menggabungkan Kubernetes Service Accounts dengan AWS IAM menggunakan OpenID Connect (OIDC) Identity Federation.
1. Cluster EKS mengekspos public OIDC discovery endpoint (`https://oidc.eks.<region>.amazonaws.com/id/<OIDC_ID>`).
2. IAM Trust Policy dikonfigurasi untuk mempercayai OIDC Provider ini dengan action `sts:AssumeRoleWithWebIdentity`, dibatasi oleh condition `StringEquals` pada ServiceAccount Name dan Namespace.
3. EKS Pod Identity Webhook menyuntikkan token JWT OIDC ke dalam pod di path `/var/run/secrets/eks.amazonaws.com/serviceaccount/token` dan mengeset environment variables:
   - `AWS_ROLE_ARN`
   - `AWS_WEB_IDENTITY_TOKEN_FILE`
4. AWS SDK di dalam aplikasi membaca variabel ini dan secara otomatis memanggil AWS STS via `AssumeRoleWithWebIdentity` untuk mendapatkan temporary credentials (AccessKeyId, SecretAccessKey, SessionToken).

### 5.4. ECR Enterprise Hardening
- **Image Scanning**: Basic Scanning (Clair-based) vs Enhanced Scanning (didukung oleh AWS Inspector yang mendeteksi CVE real-time hingga OS level dan programming language packages).
- **Lifecycle Policies**: Rule engine untuk membersihkan untagged images, membatasi retention N image terakhir, atau memindahkan image kadaluarsa ke archive untuk mencegah pembengkakan biaya S3 storage under the hood.
- **Cross-Region & Cross-Account Replication**: Sinkronisasi image otomatis antar Region (untuk latency reduction dan Disaster Recovery) dengan KMS CMK encryption per target.

### 5.5. Microservices Networking: AWS App Mesh vs AWS Service Connect
- **AWS Service Connect (ECS)**: Lapisan jaringan terkelola tanpa instalasi CRD kompleks. Menggunakan lightweight sidecar proxy berbasis Envoy yang terintegrasi langsung dengan AWS Cloud Map namespace, menyediakan DNS resolusi internal, request retry, L7 metrics, dan outlier detection tanpa perlu mengatur mesh control plane mandiri.
- **AWS App Mesh (EKS & ECS)**: Implementasi service mesh terstandarisasi berbasis Envoy Proxy enterprise. Membutuhkan control plane App Mesh, CRD controller (pada Kubernetes), Virtual Nodes, Virtual Routers, Virtual Services, dan sidecar injection otomatis. Memberikan kontrol penuh atas mTLS (Mutual TLS via AWS Private CA), distributed tracing (X-Ray/Jaeger), dynamic traffic shifting (Canary / Blue-Green), dan cross-cluster routing.

---

## 6. How
1. **Membangun ECR Registry**: Konfigurasi private repository terenkripsi KMS dengan Enhanced Scanning dan Cross-Region Replication.
2. **Menyiapkan EKS Cluster dengan OIDC**: Deploy cluster EKS, asosiasikan OIDC issuer URL ke AWS IAM.
3. **Mengonfigurasi IRSA**: Buat IAM Role dengan trust relationship OIDC, petakan ke Kubernetes ServiceAccount spesifik.
4. **Deploy Karpenter v1**: Buat EC2NodeClass dan NodePool CRD untuk menangani node provisioning cerdas.
5. **Implementasi ECS Service Connect**: Konfigurasi Task Definition dan Service di ECS dengan opsi `serviceConnectConfiguration` aktif.

---

## 7. Analogy
Bayangkan **Amazon ECR** adalah gudang logistik berstandar militer tempat kontainer barang diverifikasi bebas dari kontaminasi zat berbahaya (Image Scanning) dan disegel gembok kriptografi (KMS).

**ECS** ibarat layanan taksi korporat terpusat: Anda memesan mobil (Task), armada ditentukan oleh sistem (Fargate/EC2), perjalanannya kaku mengikuti rute jalan tol korporat (Native AWS integration). Sangat efisien, minim perawatan.

**EKS** adalah sistem jaringan kereta api rel listrik multinasional (Kubernetes): Anda memiliki kontrol penuh atas jenis gerbong, persimpangan rel, sinyal blok otomatis, dan standarisasi global.

**Karpenter** bertindak sebagai dispatcher logistik real-time otomatis: Ketika ada 100 koli barang menumpuk di stasiun, daripada memesan 10 kereta berukuran seragam yang butuh waktu 15 menit pemanasan mesin (ASG/CAS), Karpenter langsung mendeteksi dimensi koli tersebut, merakit gerbong berukuran pas (EC2 Fleet bin-packing), dan langsung meluncur dalam hitungan detik.

**IRSA** adalah kartu akses identitas digital sementara per karyawan (Pod): Daripada memberikan master key gedung kepada supir truk kontainer (Node IAM Instance Profile), setiap kurir di dalam kontainer diberikan pass badge digital RFID berotasi per 60 menit yang hanya membuka pintu gudang yang menjadi haknya.

---

## 8. Diagram (ASCII)

### 8.1. EKS IRSA Architecture Flow
```
+-----------------------------------------------------------------------------------------+
|                                    AWS EKS Cluster                                      |
|                                                                                         |
|  +--------------------+         Injects Token & Env Vars       +---------------------+  |
|  | Pod Identity       | -------------------------------------> | Application Pod     |  |
|  | Mutating Webhook   |                                        |                     |  |
|  +--------------------+                                        | - /var/run/secrets/ |  |
|                                                                |   .../token         |  |
|  +-----------------------------------------------------------+ | - AWS_ROLE_ARN      |  |
|  | Kubernetes ServiceAccount: "orders-sa"                    | +----------|----------+  |
|  | Annotation: eks.amazonaws.com/role-arn: arn:aws:iam:...   |            |             |
|  +-----------------------------------------------------------+            |             |
+---------------------------------------------------------------------------|-------------+
                                                                            |
                   (1) Presents Web Identity Token (JWT)                    |
                   + Calls AssumeRoleWithWebIdentity                        v
+-----------------------------------------------------------------------------------------+
|                                  AWS Security Token Service (STS)                       |
+-----------------------------------------------------------------------------------------+
       |                                                                    ^
       | (2) Validates Signature & Claims                                   |
       v     against Cluster OIDC Issuer                                    |
+--------------------------------------------------------------------+      |
| AWS IAM & OIDC Provider Endpoint                                   |      |
| Issuer: https://oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE123456 |      |
| Audience: sts.amazonaws.com                                        |      |
| Condition: "system:serviceaccount:production:orders-sa"            |      |
+--------------------------------------------------------------------+      |
       |                                                                    |
       | (3) Generates Temporary AWS Credentials                            |
       +--------------------------------------------------------------------+
       | (AccessKeyId, SecretAccessKey, SessionToken)
       v
+-----------------------------------------------------------------------------------------+
| Application Pod (Uses temporary credentials to interact with AWS APIs)                  |
| -> Amazon DynamoDB / S3 / SQS (Strictly isolated by IAM Role scope)                     |
+-----------------------------------------------------------------------------------------+
```

### 8.2. Karpenter vs Cluster Autoscaler Mechanism
```
[ Kubernetes Workload: Pods in "Pending" State ]
                      |
        +-------------+-------------+
        |                           |
        v                           v
+-----------------------+   +---------------------------------------------+
| Cluster Autoscaler    |   | Karpenter Autoscaler                        |
+-----------------------+   +---------------------------------------------+
| 1. Evaluates Pods     |   | 1. Evaluates Pod requirements directly      |
| 2. Increments ASG Des |   |    (vCPU, RAM, Architecture, AZ constraints)|
| 3. ASG triggers Launch|   | 2. Bypasses ASG completely                  |
| 4. CloudInit / EC2 init   | 3. Calls Amazon EC2 Fleet API directly       |
| Latency: ~3 - 8 mins  |   | 4. Fast custom-built micro-OS / Bottlerocket|
| Granularity: Rigid    |   | Latency: ~30 - 45 seconds                   |
+-----------------------+   | Granularity: Exact fit bin-packing          |
                            +---------------------------------------------+
```

---

## 9. Simple Example
Mendefinisikan Kubernetes ServiceAccount dengan IRSA untuk mengakses bucket Amazon S3:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: s3-reader-sa
  namespace: data-processing
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/DataProcessingS3ReaderRole
```

Pod Definition yang menggunakan ServiceAccount tersebut:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: data-worker
  namespace: data-processing
spec:
  serviceAccountName: s3-reader-sa
  containers:
    - name: worker
      image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/worker:v1.0.0
      command: ["aws", "s3", "ls", "s3://corp-analytics-lake/"]
```

---

## 10. Practical Example (Konfigurasi CLI / Terraform Hands-on)

### 10.1. Terraform: ECR dengan KMS Encryption & Scanning
```hcl
resource "aws_kms_key" "ecr_key" {
  description             = "KMS Key for ECR Repository Encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_ecr_repository" "enterprise_app" {
  name                 = "production/payment-gateway"
  image_tag_mutability = "IMMUTABLE"

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.ecr_key.arn
  }

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "cleanup_policy" {
  repository = aws_ecr_repository.enterprise_app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 30 release images, expire older"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v", "release-"]
          countType     = "imageCountMoreThan"
          countNumber   = 30
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Expire untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
```

### 10.2. IAM Trust Policy untuk IRSA
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/4A8B9C0D1E2F3A4B5C6D7E8F9A0B1C2D"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.us-east-1.amazonaws.com/id/4A8B9C0D1E2F3A4B5C6D7E8F9A0B1C2D:sub": "system:serviceaccount:production:payment-processor-sa",
          "oidc.eks.us-east-1.amazonaws.com/id/4A8B9C0D1E2F3A4B5C6D7E8F9A0B1C2D:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
```

### 10.3. Karpenter NodePool & EC2NodeClass Specification (Karpenter v1 API)
```yaml
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
        - key: "karpenter.k8s.aws/instance-category"
          operator: In
          values: ["c", "m", "r"]
        - key: "karpenter.k8s.aws/instance-generation"
          operator: Gt
          values: ["4"]
        - key: "karpenter.sh/capacity-type"
          operator: In
          values: ["spot", "on-demand"]
        - key: "kubernetes.io/arch"
          operator: In
          values: ["amd64", "arm64"]
  limits:
    cpu: 1000
    memory: 4000Gi
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 1m
---
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: default
spec:
  amiFamily: Bottlerocket
  role: "KarpenterNodeRole-production-cluster"
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: "production-cluster"
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: "production-cluster"
  blockDeviceMappings:
    - deviceName: /dev/xvda
      ebs:
        volumeSize: 20Gi
        volumeType: gp3
        encrypted: true
    - deviceName: /dev/xvdb
      ebs:
        volumeSize: 100Gi
        volumeType: gp3
        encrypted: true
```

### 10.4. ECS Service Connect Task Definition (JSON Snippet)
```json
{
  "family": "order-service",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "order-api",
      "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/order-api:1.2.0",
      "essential": true,
      "portMappings": [
        {
          "name": "http-api",
          "containerPort": 8080,
          "hostPort": 8080,
          "protocol": "tcp",
          "appProtocol": "http"
        }
      ]
    }
  ]
}
```

---

## 11. Real World Example
Sebuah institusi perbankan tier-1 memigrasikan backend core payment dari monolitik on-premise ke AWS.
- **Problem**: Sistem pemrosesan transaksi mengalami kegagalan sertifikasi PCI-DSS karena container worker berbagi instance role EC2. Selain itu, lonjakan transaksi setiap tanggal 25 (Payday) gagal ditangani tepat waktu karena scaling node EKS via standard Cluster Autoscaler memakan waktu 8 menit, mengakibatkan 504 Gateway Timeouts pada payment gateway.
- **Solusi Arsitektur**:
  1. Mengisolasi hak akses database transaksi per microservice menggunakan **EKS IRSA**. Setiap pod `payment-authorizer` hanya mendapatkan token STS untuk menulis ke tabel DynamoDB terkait, tanpa hak akses ke logging bucket atau database microservice lain.
  2. Mengimplementasikan **Karpenter v1** dengan policy `Spot` + `On-Demand` fallback. Instance baru berbasis Graviton3 (`c7g.xlarge`) aktif dalam 42 detik saat antrean SQS menumpuk.
  3. Mengaktifkan **ECR Tag Immutability** dan **Enhanced Scanning** dengan AWS Inspector untuk memastikan tidak ada image bertag `latest` yang bisa di-overwrite di environment produksi dan mendeteksi dependensi open-source rentan secara preventif.
- **Hasil**: Zero unauthorized privilege escalation incidents, latensi autoscaling berkurang 88%, dan penghematan biaya compute sebesar 43% melalui konsolidasi otomatis Karpenter dan adopsi Graviton Spot instances.

---

## 12. Trade-offs
1. **ECS Fargate vs EKS Karpenter**:
   - *Fargate*: Zero operational burden pada server patching, isolasi level microVM per task, namun cold-start provisioning latency (~30-60 detik) dan limitasi kontrol kernel (tidak bisa custom sysctl / eBPF tooling).
   - *Karpenter on EKS*: Scaling instan (~30-45 detik untuk node siap pakai), biaya compute jauh lebih efisien melalui instance packing yang rapat, dukungan eBPF/custom daemonsets, namun memerlukan manajemen siklus hidup cluster Kubernetes dan konfigurasi IAM trust yang kompleks.
2. **AWS App Mesh vs AWS Service Connect**:
   - *App Mesh*: Kapabilitas L7 traffic shifting, distributed tracing end-to-end, dynamic fault injection, dan mTLS formal, tetapi overhead memori tinggi (Envoy sidecar proxy per pod/task memakan 50-128MB RAM) dan setup CRD rumit.
   - *Service Connect*: Sangat mudah dikonfigurasi di ECS, tanpa setup control plane tambahan, performa sangat baik untuk HTTP/gRPC discovery internal, tetapi tidak memiliki fleksibilitas mutasi routing secanggih Istio/App Mesh.
3. **ECR Immutable vs Mutable Tags**:
   - *Immutable Tags*: Mencegah security tampering dan cache inconsistency bugs di production, tetapi sistem CI/CD harus selalu menghasilkan tag unik (misal: Semantic Versioning atau Git Commit SHA) dan tidak bisa menimpa tag jika build gagal di tengah jalan.

---

## 13. When To Use
- Gunakan **Amazon ECS + Fargate** saat: Tim Anda didominasi engineer aplikasi murni tanpa dedicated Platform/SRE team yang menguasai ekosistem Kubernetes, dan arsitektur workload berupa microservices standar berbasis HTTP/SQS.
- Gunakan **Amazon EKS + Karpenter** saat: Perusahaan Anda menjalankan hybrid cloud/multi-cloud, memerlukan ekosistem CNCF (ArgoCD, Prometheus Operator, Cilium, Istio), membutuhkan GPU workloads, atau memiliki ribuan container dengan dynamic resource consumption tinggi.
- Gunakan **IRSA** wajib pada: Semua cluster EKS produksi untuk mencegah credential leakage dan mengisolasi role blasting radius.
- Gunakan **ECS Service Connect** saat: Menggunakan Amazon ECS dan membutuhkan service-to-service communication yang stabil tanpa harus mengelola custom ALB/NLB internal untuk setiap pasang service.

---

## 14. When NOT To Use
- Jangan gunakan **EKS** jika: Workload Anda hanya terdiri dari 2–5 container sederhana dengan traffic statis. Biaya control plane ($72/bulan per cluster) dan operational complexity maintenance version upgrade (setiap 4 bulan) tidak sebanding dengan manfaatnya.
- Jangan gunakan **AWS Fargate** jika: Workload Anda membutuhkan latency startup super rendah (< 1 detik seperti real-time function), memerlukan akses direct hardware accelerator (GPU/Neuron), atau membutuhkan network mode khusus selain `awsvpc`.
- Jangan gunakan **App Mesh** jika: Anda hanya memerlukan simple point-to-point private DNS resolution antar kontainer (cukup gunakan ECS Service Connect atau Kubernetes ClusterIP + CoreDNS).

---

## 15. Common Mistakes
1. **Mengabaikan IAM Metadata Service Protection (IMDSv1)**: Tidak menonaktifkan IMDSv1 atau tidak membatasi hop-limit (`http-put-response-hop-limit=1`) pada worker nodes, sehingga pod non-IRSA dapat mencuri instance profile node host.
2. **Menggunakan Tag `latest` di ECR**: Menyebabkan silent drift antar worker node karena satu node menggunakan layer lama yang ter-cache, sementara node lain mendownload layer baru di bawah tag yang sama.
3. **Salah Mengonfigurasi Trust Policy IRSA**: Kesalahan penulisan nama namespace, typo pada ServiceAccount name, atau penggunaan wildcard berlebihan (`*`) pada `StringEquals` sub-claim OIDC, yang berakibat pod gagal meng-assume role STS atau terjadi privilege escalation lintas namespace.
4. **Alokasi Karpenter NodePool Tanpa Limits**: Tidak memberikan batas `spec.limits.cpu` dan `spec.limits.memory` pada NodePool Karpenter, sehingga runaway deployment dapat mem-provisioning ratusan instance EC2 berukuran besar yang berujung pada AWS cloud billing explosion.
5. **Kekurangan IP Address VPC Subnet**: Menggunakan CIDR subnet kecil (/24) pada cluster EKS dengan AWS VPC CNI. Setiap Pod mendapatkan direct IP dari subnet, sehingga IP pool habis cepat dan memicu error `FailedCreatePodSandBox`.

---

## 16. Best Practices
1. **ECR Immutability & Scanning**: Aktifkan tag immutability pada ECR production. Terapkan AWS Inspector continuous scanning untuk proactive vulnerability alerts.
2. **IRSA Least Privilege**: Buat satu IAM Role spesifik untuk setiap Kubernetes ServiceAccount. Jangan pernah menggunakan satu IAM Role raksasa untuk seluruh Pod di satu cluster.
3. **Karpenter Consolidation**: Terapkan `consolidationPolicy: WhenEmptyOrUnderutilized` agar Karpenter secara otomatis men-terminate node yang kurang termanfaatkan dan memindahkan pod ke node yang lebih efisien secara matematis.
4. **Graceful Termination Handlers**: Gunakan lifecycle hooks dan tolerations pada node Karpenter Spot untuk menangani interupsi EC2 Spot notice 2 menit sebelum instance ditarik kembali oleh AWS.
5. **Service Connect Resiliency**: Konfigurasikan client-side timeout dan outlier detection pada ECS Service Connect configuration untuk mencegah cascading failure saat salah satu downstream microservice melambat.

---

## 17. Troubleshooting
- **Error: `WebIdentityErr: failed to retrieve credentials` pada EKS Pod**:
  - *Root Cause*: OIDC Provider belum diasosiasikan dengan IAM, IAM trust relationship memiliki typo pada sub-claim, atau token mount path tidak dapat dibaca oleh runtime user aplikasi (permission non-root issue).
  - *Fix*: Jalankan `aws iam get-open-id-connect-provider` untuk memverifikasi thumbprint. Pastikan `securityContext.fsGroup` pada Pod diatur agar user non-root dapat membaca token file di `/var/run/secrets/eks.amazonaws.com/serviceaccount/token`.
- **Karpenter Tidak Mem-provisioning Node Baru (Pods Stuck Pending)**:
  - *Root Cause*: Subnet atau Security Group tidak diberi tag discovery yang sesuai dengan `subnetSelectorTerms` dan `securityGroupSelectorTerms` pada `EC2NodeClass`.
  - *Fix*: Pastikan resource subnet dan security group memiliki tag `karpenter.sh/discovery: <cluster-name>`. Cek log controller: `kubectl logs -l app.kubernetes.io/name=karpenter -n kube-system -f`.
- **ECS Service Connect: Request Timeout ke Target Service**:
  - *Root Cause*: Security Group target service tidak mengizinkan inbound traffic dari Security Group source client pada port aplikasi, atau port name di task definition tidak cocok dengan client alias.
  - *Fix*: Pastikan Security Group downstream menerima ingress TCP port dari ECS proxy sidecar security group. Verifikasi status endpoint di AWS Cloud Map console.

---

## 18. Exercise
1. **Latihan 1 (ECR Lifecycle Calculation)**: Tuliskan JSON Lifecycle Policy untuk ECR repository yang menjaga maksimal 15 image bertag `prod-*`, menghapus image bertag `dev-*` yang lebih tua dari 14 hari, dan menghapus image `untagged` dalam waktu 48 jam.
2. **Latihan 2 (IRSA Trust Relationship Audit)**: Buat dokumen IAM Trust Relationship yang hanya mengizinkan ServiceAccount `billing-service` di namespace `finance` pada EKS Cluster dengan OIDC `EXAMPLED1234567890` untuk melakukan AssumeRole.

---

## 19. Challenge
Rancang arsitektur Terraform lengkap yang mem-provisioning EKS Multi-AZ Cluster (Private Control Plane), Karpenter v1 terkonfigurasi untuk menyeimbangkan spot dan on-demand instances lintas 3 AZ, integrasi IRSA untuk deployment backend microservice yang membutuhkan akses ke Amazon DynamoDB terenkripsi KMS, serta implementasi ECR repository private dengan replication cross-region ke secondary disaster recovery site. Workload harus mampu bertahan terhadap simulasi sudden EC2 spot termination tanpa downtime bagi end-user.

---

## 20. Summary
- **Amazon ECS** menawarkan simplicitas integrasi AWS native dengan operational overhead minimal, sangat ideal dikombinasikan dengan **AWS Fargate** untuk operational hygiene tanpa server maintenance.
- **Amazon EKS** menghadirkan fleksibilitas standardisasi Kubernetes CNCF; performa autoscaling-nya dioptimalkan secara radikal oleh **Karpenter** yang berinteraksi langsung dengan EC2 Fleet API.
- **Security Isolation** pada enterprise container dijamin melalui **IRSA** (EKS) dan ECS Task Roles, menghilangkan dependensi terhadap node-level permissions.
- **ECR Enterprise Hardening** menjamin integritas rantai pasok software (supply chain security) dengan KMS encryption, Tag Immutability, dan Automated Inspector Scanning.
- **Service Mesh & Connect** mentransformasi networking container dari dependensi fragile static DNS ke Layer 7 dynamic routing, outlier detection, dan low-latency local proxies.

---