# BAB 07: Enterprise Container Orchestration - Quiz & Challenge

---

## 1. Basic Questions (Pilihan Ganda)

### Q1. Manakah pernyataan yang paling akurat mengenai model keamanan kredensial IAM pada Amazon ECS launch type EC2?
- A. Seluruh container di dalam satu host EC2 wajib menggunakan IAM role yang sama dengan EC2 Instance Profile host tersebut.
- B. Container dapat memiliki IAM role independen melalui ECS Task Role, yang mengisolasi kredensial per Task tanpa memberikan akses ke EC2 Instance Profile host jika IMDSv1 dimitigasi.
- C. ECS Task Execution Role digunakan oleh kode aplikasi di dalam container untuk memanggil AWS S3 dan DynamoDB API.
- D. Container pada launch type EC2 tidak dapat mengakses AWS STS untuk melakukan assume role.

### Q2. Bagaimana mekanisme Karpenter dalam mem-provisioning instance baru di Amazon EKS dibandingkan Kubernetes Cluster Autoscaler (CAS) tradisional?
- A. Karpenter menaikkan kapasitas yang diinginkan (Desired Capacity) pada AWS Auto Scaling Group (ASG) yang bersangkutan.
- B. Karpenter mengevaluasi manifest pod yang pending dan langsung memanggil AWS EC2 Fleet API tanpa melalui abstraksi Auto Scaling Group.
- C. Karpenter hanya mendukung instance tipe On-Demand dan tidak dapat memanfaatkan instance Spot.
- D. Karpenter memerlukan deployment Node Group terpisah untuk setiap variasi instance type yang ingin digunakan.

### Q3. Komponen apa yang menyuntikkan token OIDC dan environment variable `AWS_ROLE_ARN` ke dalam Pod saat mengimplementasikan IAM Roles for Service Accounts (IRSA)?
- A. Karpenter Controller
- B. AWS Cloud Map discovery agent
- C. Amazon EKS Pod Identity Mutating Admission Webhook
- D. CoreDNS Kubernetes Cluster Plugin

### Q4. Apa fungsi dari mengaktifkan "Image Tag Immutability" pada Amazon Elastic Container Registry (ECR)?
- A. Mencegah repository dari penghapusan image oleh ECR Lifecycle Policy.
- B. Memastikan scanning kerentanan CVE selalu dijalankan ulang setiap 24 jam.
- C. Mencegah penimpaan (overwrite) image tag yang sudah ada, sehingga menjamin konsistensi versi artefak deployment di seluruh environment.
- D. Mengubah format container image dari Docker V2 manifest ke OCI image specification secara otomatis.

### Q5. Kapan sebaiknya AWS Service Connect dipilih dibandingkan deployment AWS App Mesh penuh pada arsitektur microservices Amazon ECS?
- A. Ketika aplikasi memerlukan Mutual TLS (mTLS) berbasis private CA pihak ketiga yang rumit.
- B. Ketika tim menginginkan service discovery Layer 7, traffic metrics, dan automatic retries tanpa beban operasional mengelola CRD dan control plane mesh yang kompleks.
- C. Ketika microservices berjalan di luar AWS (on-premises hybrid datacenter).
- D. Ketika aplikasi hanya menggunakan protokol UDP murni tanpa HTTP/gRPC.

---

## 2. Intermediate Questions (Jawaban Esai Singkat)

### Q1. Jelaskan perbedaan mendasar antara ECS Task Execution Role dan ECS Task Role! Kapan masing-masing role tersebut digunakan?
*Panduan Jawaban Teknis*:
- **ECS Task Execution Role**: Digunakan oleh AWS ECS Container Agent dan Docker daemon host sebelum container aplikasi dijalankan. Tujuannya adalah mengizinkan agent untuk menarik private image dari ECR (`ecr:GetAuthorizationToken`, `ecr:BatchGetImage`), mengirimkan stdout/stderr logs ke CloudWatch Logs (`logs:CreateLogStream`, `logs:PutLogEvents`), dan mengambil secrets/parameter dari AWS Secrets Manager atau SSM Parameter Store.
- **ECS Task Role**: Digunakan langsung oleh kode/aplikasi di dalam container saat container sudah berjalan. Role ini menentukan hak akses bisnis aplikasi terhadap layanan AWS lain (seperti read/write ke S3, query ke DynamoDB, publish message ke SQS).

### Q2. Analisis bagaimana IRSA memvalidasi keaslian token request dari Pod ke AWS STS! Parameter dan field apa saja yang diverifikasi dalam trust relationship?
*Panduan Jawaban Teknis*:
IRSA menggunakan mekanisme OIDC Federation. Alurnya:
1. Pod membawa OpenID Connect JSON Web Token (JWT) yang diterbitkan oleh cluster EKS OIDC issuer endpoint dan ditandatangani secara kriptografis menggunakan private key cluster.
2. Saat aplikasi melakukan request API AWS, AWS SDK menukarkan token tersebut ke AWS STS via API `AssumeRoleWithWebIdentity`.
3. STS mengambil public keys dari EKS OIDC Discovery Endpoint (`https://oidc.eks.<region>.amazonaws.com/id/<ID>/.well-known/openid-configuration`) untuk memverifikasi validitas tanda tangan kriptografis token.
4. STS memvalidasi field klaim di dalam token terhadap IAM Trust Policy:
   - `iss` (Issuer): Harus sama dengan URL OIDC cluster.
   - `aud` (Audience): Harus bernilai `sts.amazonaws.com`.
   - `sub` (Subject): Harus sama persis dengan `system:serviceaccount:<namespace>:<service-account-name>`.

### Q3. Dalam skenario migrasi dari Cluster Autoscaler ke Karpenter, apa keuntungan penggunaan Bottlerocket OS dibanding Amazon Linux 2 sebagai basis node worker EKS?
*Panduan Jawaban Teknis*:
- Bottlerocket adalah OS open-source berbasis Linux yang dibangun khusus oleh AWS murni untuk menjalankan container.
- **Waktu Booting Ekstrem Cepat**: Menghilangkan utilitas OS tradisional yang tidak diperlukan; boot time jauh lebih singkat (~15-20 detik), melengkapi kapabilitas fast provisioning Karpenter.
- **Security Posture Tinggi**: Read-only root filesystem yang dilindungi dm-verity, tidak memiliki interpreter package bawaan seperti Python atau shell umum, meminimalisir attack vector.
- **Atomic Updates**: Mendukung patch dan update OS secara transparan berbasis dual-partition A/B scheme, mengurangi downtime dan node update failures.

---

## 3. Scenario-Based Questions (Kasus Nyata Industri)

### Skenario 1: The "Runaway Pod Billing" & Spot Eviction Incident
Perusahaan fintech Anda menjalankan 400 microservices di atas Amazon EKS. Untuk menghemat biaya, tim platform mengonfigurasi Karpenter untuk mem-provisioning 100% EC2 Spot Instances pada NodePool production.
Pada hari Senin pukul 14:00, AWS mereklamasi sejumlah besar EC2 Spot instances di availability zone `us-east-1a` karena lonjakan permintaan global. Ratusan pod terminated mendadak, transaksi pembayaran gagal massal, dan pod replika mengalami error `Pending` terus-menerus selama 10 menit karena Karpenter gagal mendapatkan Spot instance baru di AZ tersebut.

*Pertanyaan*:
1. Analisis kesalahan fatal pada konfigurasi Karpenter NodePool di atas!
2. Rancang strategi arsitektur NodePool Karpenter yang resilient (resilience architecture) yang mampu menggabungkan Spot dan On-Demand, multi-AZ distribution, serta graceful eviction handling!

*Kunci Solusi*:
1. **Kesalahan Fatal**:
   - Menggunakan 100% Spot instances untuk critical state/production transactions tanpa On-Demand fallback.
   - Mengunci capacity type hanya pada satu Availability Zone atau tanpa diversifikasi tipe instance yang luas.
   - Kurangnya toleransi dan penanganan interupsi Spot (AWS Node Termination Handler / Karpenter native interruption queue).
2. **Solusi Perbaikan**:
   - Konfigurasikan NodePool requirements untuk mendukung instance types yang terdiversifikasi luas: `instance-category: ["c", "m", "r"]`, `generation: [">4"]`.
   - Pisahkan workload: Pod critical (payment engine) dialokasikan ke NodePool bertipe On-Demand (atau 80% On-Demand, 20% Spot) menggunakan nodeAffinity/tolerations.
   - Aktifkan native interruption handling di Karpenter dengan menghubungkan Amazon EventBridge rules (untuk Spot Interruption Warnings, EC2 Rebalance Recommendations) ke SQS queue yang dipantau oleh controller Karpenter.
   - Terapkan `topologySpreadConstraints` pada Deployment Pod agar terdistribusi merata di 3 AZ (`topology.kubernetes.io/zone`).

---

### Skenario 2: The ECR Vulnerability Blocker & Deploy Deadlock
Pipeline CI/CD tim engineering mempublikasikan container image ke Amazon ECR dengan tag `release-latest`. ECR dikonfigurasi dengan Enhanced Scanning (AWS Inspector) dan pipeline memiliki rule untuk memblokir deployment jika ditemukan kerentanan dengan severity "CRITICAL".
Suatu malam, deployment hotfix darurat gagal rilis ke ECS Fargate karena ECR menolak image baru atau pipeline gagal membaca manifest. Saat diperiksa, repository ECR ternyata telah diaktifkan fitur `Tag Immutability` oleh tim compliance tanpa sosialisasi. Di saat yang sama, image lama tetap running di cluster tetapi task baru terus crash-looping saat scaling out.

*Pertanyaan*:
1. Mengapa kombinasi tag `release-latest` dan `Tag Immutability` menyebabkan kegagalan deployment hotfix?
2. Bagaimana arsitektur tagging strategy dan CI/CD pipeline yang seharusnya diterapkan untuk mengakomodasi Tag Immutability, zero-downtime rolling update, dan ECR image scanning?

*Kunci Solusi*:
1. **Penyebab Kegagalan**:
   - Tag Immutability secara ketat melarang client me-push image dengan tag yang sudah ada di repository. Pipeline yang mem-build hotfix mencoba menimpa tag `release-latest`, sehingga ditolak oleh API ECR (`ImageAlreadyExistsException`).
   - Task baru yang scale-out di Fargate mungkin mencoba mendownload image lama yang terkompromi atau mengalami mismatch manifest jika task definition merujuk tag yang gagal diupdate.
2. **Solusi Arsitektur**:
   - **Unique Immutable Tagging**: Ubah strategi tagging pada CI/CD menjadi immutable identifiers berbasis Git commit SHA dan semantic versioning (`v2.4.1-build.58a1b2c`).
   - **Continuous Vulnerability Gate**: Pipeline mem-push image dengan tag unik -> Inspector melakukan scanning sinkron/asinkron -> CI/CD menanyakan API `DescribeImageScanFindings`. Jika lolos batas toleransi CVE, update ECS Task Definition via JSON payload baru yang menunjuk SHA tag spesifik tersebut.
   - **Automated Rollback**: Jika scan gagal, image di-quarantine via lifecycle policy dan pipeline membatalkan update task definition secara otomatis tanpa mempengaruhi task yang sedang live.

---

### Skenario 3: Cross-Account EKS IRSA Security Leak
Sebuah konglomerat memiliki Account AWS Production (ID: `111111111111`) dan Account AWS Data Analytics (ID: `222222222222`). Cluster EKS berada di Account Production.
Tim Data Analytics ingin pod `spark-worker` di cluster EKS Production membaca data lake di S3 bucket yang berada di Account Data Analytics. Seorang junior engineer membuat IAM Role di Account Data Analytics dan mengarahkan trust policy langsung ke ARN instance worker node cluster EKS Production.
Akibatnya, audit keamanan menemukan bahwa pod non-analytics (termasuk public-facing nginx web server) di cluster tersebut secara teknis dapat mencuri kredensial dari host node metadata dan mengakses data analytics sensitif.

*Pertanyaan*:
1. Di mana letak lubang keamanan arsitektur di atas?
2. Buat skema dan trust policy cross-account yang benar menggunakan IRSA sehingga HANYA pod `spark-worker` di namespace `analytics` yang memiliki akses ke S3 bucket tersebut!

*Kunci Solusi*:
1. **Lubang Keamanan**:
   - Mempercayai Node Instance Profile EKS berarti seluruh workload di cluster tersebut (karena berbagi host VM yang sama) dapat memanggil instance metadata service (`169.254.169.254`) untuk mengambil credential node dan melakukan AssumeRole ke Account Data Analytics. Ini melanggar isolasi multitenant.
2. **Skema & Trust Policy yang Benar**:
   - Hubungkan OIDC issuer EKS Production ke IAM Identity Provider di Account Data Analytics (`222222222222`).
   - Buat IAM Role di Account `222222222222` dengan trust relationship eksklusif:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::222222222222:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/PROD-EKS-OIDC-ID"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.us-east-1.amazonaws.com/id/PROD-EKS-OIDC-ID:sub": "system:serviceaccount:analytics:spark-worker-sa",
          "oidc.eks.us-east-1.amazonaws.com/id/PROD-EKS-OIDC-ID:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
```

---

## 4. Practical Chapter Challenge: High-Resilience EKS Platform Engine

### Deskripsi Masalah:
Rancang dan simulasikan arsitektur container orchestration mission-critical untuk platform e-commerce enterprise dengan kriteria berikut:
1. **Auto-provisioning & Scaling**:
   - Workload pemrosesan order (`checkout-service`) harus mampu menangani lonjakan traffic dari 10 pod menjadi 300 pod dalam waktu < 2 menit.
   - Menggunakan Karpenter dengan kombinasi instance tipe Spot untuk worker pod dan On-Demand untuk Redis caching pod.
2. **Identity & Security Posture**:
   - `checkout-service` wajib menggunakan IRSA untuk memanggil Amazon DynamoDB dan AWS SQS. Tidak boleh ada pod lain yang memiliki akses ke role tersebut.
   - Seluruh image wajib ditarik dari Amazon ECR private terenkripsi KMS dengan tag immutability.
3. **Networking Resiliency**:
   - Service discovery internal antar microservice menggunakan service-mesh/service-connect proxy dengan outlier detection (ejection bila terjadi 3 kali 5xx error berturut-turut).

### Deliverables Tantangan:
Tuliskan spesifikasi file implementasi:
1. Kubernetes Karpenter `NodePool` & `EC2NodeClass` definition manifest.
2. IAM Trust Relationship JSON Policy untuk ServiceAccount `checkout-service-sa`.
3. Kubernetes Deployment manifest lengkap yang mencakup tolerations, topology-spread, resource requests/limits, dan ServiceAccount binding.

---