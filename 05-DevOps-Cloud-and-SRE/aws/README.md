# Cloud Enterprise Architecture: Amazon Web Services (AWS)
### Kurikulum Standar Industri Rekayasa Infrastruktur Skala Global

---

## 1. Course Overview & Mindset

Selamat datang di kurikulum rekayasa infrastruktur **Amazon Web Services (AWS)** enterprise-grade. Silabus ini dirancang bukan sekadar untuk menghafal layanan AWS melalui web console (*ClickOps*), melainkan untuk membentuk kompetensi level Senior Cloud Architect dan Platform/DevOps Engineer yang mampu merancang, membangun, dan mengoperasikan sistem terdistribusi berskala masif, berketahanan tinggi (*highly available*), dan hemat biaya.

### Prinsip Fondasi Kurikulum:
1. **The AWS Well-Architected Framework**: Setiap arsitektur diukur berdasarkan 6 pilar utama: *Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization,* dan *Sustainability*.
2. **Infrastructure as Code (IaC) & Immutable Infrastructure**: Segala bentuk konfigurasi divalidasi via kode deklaratif (Terraform & AWS CDK). Tidak ada modifikasi manual di *production*.
3. **Defense-in-Depth & Zero Trust**: Implementasi isolasi akun multi-tier (*AWS Organizations*), segregasi jaringan ketat (*VPC microsegmentation*), rotasi kredensial otomatis, dan enkripsi *in-transit* maupun *at-rest* secara non-negosiasi.
4. **Resiliency by Design**: Asumsi kegagalan (*everything fails all the time*). Desain sistem wajib toleran terhadap *Availability Zone (AZ) failure* hingga *Region-level outage*.

---

## 2. Learning Roadmap

```plaintext
AWS Cloud Enterprise Engineering Roadmap
│
├── [Bab 01] Fondasi Cloud, Akun Enterprise & IAM Governance
│   ├── AWS Organizations, SCP, & IAM Identity Center
│   └── Least Privilege IAM Policy Engineering & Permission Boundaries
│
├── [Bab 02] Arsitektur Jaringan Skala Enterprise
│   ├── VPC Advanced Topology, Multi-Tier Subnetting & NAT Gateways
│   └── AWS Transit Gateway, VPC Peering & PrivateLink Architecture
│
├── [Bab 03] Compute Architecture & Elastic Scaling
│   ├── Amazon EC2 Deep-Dive, Graviton, & Launch Templates
│   └── Advanced Auto Scaling, Spot Fleet Strategy, & AWS Systems Manager
│
├── [Bab 04] Storage Subsystems & Data Lifecycle Management
│   ├── Amazon S3 Security, Bucket Policies, Lifecycle & Replication
│   └── Block & File Systems: EBS Tuning, EFS Elastic, & FSx for Lustre
│
├── [Bab 05] Distributed Databases & Caching Layer
│   ├── Amazon RDS Multi-AZ, Read Replicas & Aurora Global Database
│   └── NoSQL Deep-Dive: DynamoDB Single-Table Design & ElastiCache Redis
│
├── [Bab 06] Serverless Architecture & Event-Driven Systems
│   ├── AWS Lambda Internals, Execution Environments & Performance Tuning
│   └── Event-Driven Core: API Gateway, SQS, SNS, & EventBridge Decoupling
│
├── [Bab 07] Enterprise Container Orchestration
│   ├── Elastic Container Service (ECS) with AWS Fargate
│   └── Elastic Kubernetes Service (EKS) Production Hardening
│
├── [Bab 08] Cloud Security, Governance & Regulatory Compliance
│   ├── Cryptography: AWS KMS, CloudHSM & Secrets Manager
│   └── Perimeter Protection: AWS WAF, Shield, GuardDuty, & Security Hub
│
├── [Bab 09] Telemetry, Observability & Cloud Financial Ops (FinOps)
│   ├── Centralized Observability: CloudWatch, Container Insights, & X-Ray
│   └── FinOps: Cost Allocation Tags, Compute Optimizer, & Savings Plans
│
└── [Bab 10] Continuous Delivery & Infrastructure as Code (IaC)
    ├── Production Infrastructure via Terraform & AWS CDK
    └── Multi-Account Deployment Pipelines & GitOps Workflows
```

---

## 3. Navigasi Detail Kurikulum

### [Bab 01: Fondasi Cloud, Akun Enterprise & IAM Governance](./bab-01-fondasi-iam/)
Arsitektur multi-akun modern, tata kelola identitas terpusat, dan pembatasan radius ledakan (*blast radius*).
* [Modul 01: AWS Organizations, Control Tower, dan Service Control Policies (SCP)](./bab-01-fondasi-iam/01-aws-organizations-control-tower.md)
  * Struktur OU (Core, Security, Workloads), SCP hierarkis, deteksi deviasi kepatuhan via AWS Control Tower.
* [Modul 02: IAM Identity Center (SSO), Permission Boundaries, dan Zero Trust IAM](./bab-01-fondasi-iam/02-iam-zero-trust-policies.md)
  * Integrasi IdP eksternal (OIDC/SAML), penulisan *policy* JSON kompleks, *Condition Keys* lanjutan (`aws:PrincipalArn`, `aws:SourceVpce`), dan *Permission Boundaries*.

---

### [Bab 02: Arsitektur Jaringan Skala Enterprise](./bab-02-jaringan-enterprise/)
Perancangan topologi jaringan privat, interkoneksi hybrid, dan isolasi lalu lintas data.
* [Modul 01: Arsitektur Virtual Private Cloud (VPC) & Multi-AZ Routing Topology](./bab-02-jaringan-enterprise/01-vpc-advanced-routing.md)
  * Subnetting CIDR calculation, Route Tables, NAT Gateway HA, Network ACLs vs Security Groups stateful inspection.
* [Modul 02: Interkonektivitas Lanjutan: Transit Gateway, Direct Connect, & AWS PrivateLink](./bab-02-jaringan-enterprise/02-transit-gateway-privatelink.md)
  * Hub-and-spoke networking dengan AWS Transit Gateway, koneksi hybrid via DX dan IPsec VPN, serta konsumsi layanan SaaS via VPC Endpoints/PrivateLink.

---

### [Bab 03: Compute Architecture & Elastic Scaling](./bab-03-compute-scaling/)
Optimasi beban kerja komputasi berbasis *virtual machine*, ARM architecture, dan orkestrasi armada.
* [Modul 01: Deep-Dive Amazon EC2, Nitro System, dan Arsitektur AWS Graviton](./bab-03-compute-scaling/01-ec2-nitro-graviton.md)
  * Pemilihan *family instance*, optimasi performa I/O via AWS Nitro, migrasi ke arsitektur ARM berbasis Graviton untuk *cost-performance*.
* [Modul 02: Fleet Management: Auto Scaling Groups, Spot Instances, & Systems Manager](./bab-03-compute-scaling/02-asg-spot-ssm.md)
  * *Dynamic and predictive scaling policies*, diversifikasi Spot Fleet untuk efisiensi biaya 70%+, manajemen tanpa SSH via AWS Systems Manager (SSM) Session Manager.

---

### [Bab 04: Storage Subsystems & Data Lifecycle Management](./bab-04-storage-data/)
Penyimpanan objek, blok, dan sistem file terdistribusi untuk beban kerja performa tinggi.
* [Modul 01: Amazon S3 Security, Access Points, Cross-Region Replication & Lifecycle](./bab-04-storage-data/01-s3-deep-dive.md)
  * S3 Bucket Policies, Block Public Access, S3 Object Lock (WORM), Multi-Region Access Points, dan transisi kelas penyimpanan otomatis.
* [Modul 02: Block & File Storage: EBS Tuning, Elastic EFS, & High-Performance FSx](./bab-04-storage-data/02-ebs-efs-fsx.md)
  * EBS Volume types (gp3 vs io2 Block Express), tuning IOPS/Throughput, Shared File Storage dengan EFS, dan sistem file terdistribusi FSx for Lustre.

---

### [Bab 05: Distributed Databases & Caching Layer](./bab-05-database-caching/)
Manajemen database relasional tervirtualisasi, NoSQL terdistribusi, dan layer akselerasi *in-memory*.
* [Modul 01: Amazon RDS Multi-AZ, Aurora Architecture, & Global Databases](./bab-05-database-caching/01-rds-aurora-global.md)
  * Desain RDS Multi-AZ vs Aurora cluster storage engine, implementasi Read Replicas dengan *failover automated*, dan latensi lintas-benua via Aurora Global Database.
* [Modul 02: DynamoDB Single-Table Design & ElastiCache Caching Strategies](./bab-05-database-caching/02-dynamodb-elasticache.md)
  * Partisi data DynamoDB, GSI/LSI, Single-Table design pattern, serta strategi *write-through* dan *cache-aside* menggunakan Redis/Memcached.

---

### [Bab 06: Serverless Architecture & Event-Driven Systems](./bab-06-serverless-event-driven/)
Pembangunan aplikasi modern *loosely-coupled* tanpa manajemen server langsung.
* [Modul 01: AWS Lambda Internals, Concurrency, and API Gateway Integration](./bab-06-serverless-event-driven/01-lambda-apigateway-core.md)
  * Lambda execution lifecycle, cold start mitigations, Provisioned Concurrency, REST vs HTTP APIs, dan throttling controls.
* [Modul 02: Asynchronous Decoupling: SQS, SNS, EventBridge, & Step Functions](./bab-06-serverless-event-driven/02-event-driven-orchestration.md)
  * Pola arsitektur *Publish/Subscribe*, message queuing dengan FIFO deduplication, *event routing* terpusat dengan Amazon EventBridge, dan *stateful workflows* via Step Functions.

---

### [Bab 07: Enterprise Container Orchestration](./bab-07-container-orchestration/)
Deployment dan manajemen siklus hidup kontainer berbasis ECS dan standardisasi industri Kubernetes (EKS).
* [Modul 01: Amazon Elastic Container Service (ECS) Serverless with AWS Fargate](./bab-07-container-orchestration/01-ecs-fargate-deployments.md)
  * Definisi Task & Service, integrasi ALB, Service Connect untuk *service mesh* ringan, serta deployment *blue/green* via AWS CodeDeploy.
* [Modul 02: Amazon Elastic Kubernetes Service (EKS) Production Hardening](./bab-07-container-orchestration/02-eks-production-hardening.md)
  * EKS control plane architecture, IRSA (IAM Roles for Service Accounts), autoscaling via Karpenter, dan integrasi AWS VPC CNI.

---

### [Bab 08: Cloud Security, Governance & Regulatory Compliance](./bab-08-security-compliance/)
Kriptografi, mitigasi serangan siber pada perimeter, dan auditing kepatuhan otomatis.
* [Modul 01: Data Encryption & Secrets: AWS KMS, Secrets Manager, and Certificate Manager](./bab-08-security-compliance/01-kms-secrets-acm.md)
  * Desain Customer Managed Keys (CMK), rotasi otomatis rahasia aplikasi, dan manajemen sertifikat TLS/SSL via ACM.
* [Modul 02: Threat Detection & Edge Security: WAF, Shield, GuardDuty, & Security Hub](./bab-08-security-compliance/02-edge-security-threat-detection.md)
  * Mitigasi DDoS skala besar via AWS Shield, rule engine pada AWS WAF, deteksi ancaman berbasis ML via GuardDuty, dan agregasi temuan via AWS Security Hub.

---

### [Bab 09: Telemetry, Observability & Cloud Financial Ops (FinOps)](./bab-09-observability-finops/)
Monitoring komprehensif, pelacakan terdistribusi (*distributed tracing*), dan tata kelola anggaran awan.
* [Modul 01: Unified Telemetry: CloudWatch, Container Insights, & AWS X-Ray](./bab-09-observability-finops/01-cloudwatch-xray-observability.md)
  * Metrik kustom, log aggregation via CloudWatch Logs Insights, *profiling* kontainer, dan analisis *bottleneck* microservices via AWS X-Ray.
* [Modul 02: FinOps Engineering: Cost Allocation, Budgets, and Compute Optimizer](./bab-09-observability-finops/02-finops-cost-optimization.md)
  * Penerapan tag keuangan konsisten, AWS Budgets alert system, optimalisasi hak ukuran (*right-sizing*) dengan AWS Compute Optimizer, dan strategi komitmen Savings Plans.

---

### [Bab 10: Continuous Delivery & Infrastructure as Code (IaC)](./bab-10-iac-cicd/)
Standardisasi provisioning infrastruktur berbasis perangkat lunak dan deployment pipa multi-akun.
* [Modul 01: Infrastructure Provisioning: Terraform Enterprise Patterns & AWS CDK](./bab-10-iac-cicd/01-iac-terraform-cdk.md)
  * Modularisasi Terraform, remote state management dengan S3/DynamoDB locking, dan alternatif deklaratif berbasis bahasa pemrograman imperatif via AWS CDK.
* [Modul 02: Cross-Account CI/CD Pipelines & Immutable Delivery Workflows](./bab-10-iac-cicd/02-cicd-cross-account-deployment.md)
  * Desain pipeline multi-tahap (Dev, Staging, Prod) dengan AWS CodePipeline / GitHub Actions, integrasi *security scanning* (Checkov/Trivy), dan *automated rollback*.

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title:
**Multi-Region Mission-Critical Financial Core Banking & Clearing System**

### Skenario & Persyaratan Bisnis:
Sebuah institusi teknologi finansial (*FinTech*) multinasional memerlukan modernisasi platform perbankan intinya. Sistem harus memproses transaksi kartu debit dan transfer dana real-time dengan spesifikasi ketat:
* **Availability**: 99.999% uptime target.
* **RTO (Recovery Time Objective)**: < 1 menit untuk regional failover.
* **RPO (Recovery Point Objective)**: Hampir 0 (RPO < 1 detik) untuk data finansial.
* **Kepatuhan**: PCI-DSS Tier 1 & ISO/IEC 27001 compliant.

### Arsitektur Teknis yang Wajib Diimplementasikan:
1. **Multi-Account Governance**:
   * Setup minimum 4 akun AWS terpisah via AWS Organizations: `Management/Billing`, `Security & Log Archive`, `Shared Services/CI-CD`, dan `Workload Production`.
   * Delegated Administrator untuk GuardDuty dan Security Hub di akun Keamanan.
2. **Resilient Network Layer**:
   * Implementasi dua AWS Region (Primary: `ap-southeast-1`, Secondary: `ap-southeast-3` / `us-east-1`).
   * Desain VPC 3-tier (Public Web Tier, Private App Tier, Isolated Database Tier).
   * Cross-region connectivity via Transit Gateway Peering yang terenkripsi.
3. **Core Processing Engine**:
   * Cluster Amazon EKS terdistribusi di seluruh Availability Zones dengan autoscaling Karpenter.
   * Microservices di-deploy secara immutable via container image tersertifikasi dari Amazon ECR.
4. **Resilient Data Plane**:
   * Amazon Aurora Global Database (PostgreSQL-compatible) dengan *cross-region read replicas* dan *storage replication* berkecepatan tinggi.
   * Layer caching transaksi cepat menggunakan Amazon ElastiCache for Redis Cluster (Multi-AZ with Auto-Failover).
5. **Event-Driven Reconciliation**:
   * Arsitektur asinkron untuk audit transaksi menggunakan Amazon SQS FIFO, AWS SNS, dan EventBridge.
6. **Perimeter & Zero-Trust Security**:
   * Integrasi AWS WAF di CloudFront dan ALB dengan Rate Limiting, OWASP Top 10 rules, dan Geo-blocking.
   * AWS KMS Multi-Region Customer Managed Keys untuk enkripsi field-level data finansial.
7. **Full IaC Delivery**:
   * Seluruh infrastruktur wajib disediakan murni via Terraform Modules atau AWS CDK Typescript.
   * Modul mencakup *state locking*, *automated drift detection*, dan eksekusi via CI/CD Pipeline terisolasi dengan asumsi *cross-account IAM role*.

### Standar Kelulusan Proyek:
* Pengujian simulasi pemadaman zona (*Availability Zone injection outage*) tanpa kehilangan data (*zero data corruption*).
* Laporan hasil pemindaian keamanan (*Security Benchmark*) menggunakan AWS Security Hub mencapai skor minimal **90% compliance** terhadap CIS AWS Foundations Benchmark v1.4.
* Seluruh arsitektur terbukti tervendorisasi 100% via kode IaC tanpa modifikasi web console manual.