# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengimplementasikan Arsitektur Produksi Skala Enterprise**: Memahami dan mengonfigurasi topologi *High Availability* (HA), *failover* multi-zona, dan *zero-downtime deployment* menggunakan strategi Canary dan Blue/Green.
2. **Mengotomatisasi Infrastruktur dengan Prinsip Immutability**: Menguasai siklus hidup *Infrastructure as Code* (IaC) dengan pencegahan *state drift*, penguncian state jarak jauh (*remote state locking*), dan isolasi lingkungan (*environment parity*).
3. **Menerapkan GitOps & Continuous Delivery Tingkat Lanjut**: Mengonfigurasi *declarative deployment* terotomatisasi berbasis kontrol rekonsiliasi (*reconciliation loop*) menggunakan ArgoCD/Flux serta strategi rollback otomatis saat metrik performa memburuk.
4. **Mengintegrasikan Enterprise Secret Management & Security Governance**: Mengeliminasi *hardcoded secrets* dengan mengintegrasikan HashiCorp Vault atau Kubernetes External Secrets Operator menggunakan autentikasi berbasis identitas mesin (OIDC/Workload Identity).
5. **Mengorelasikan Telemetri Observabilitas Multi-Dimensi**: Menghubungkan *distributed tracing* (OpenTelemetry), metrik (Prometheus), dan log agregat (Loki/Fluentd) untuk analisis *root cause* secara deterministik.

---

## 2. Prerequisite

Sebelum memulai modul ini, peserta wajib memahami:
* Konsep dasar Linux System Administration (POSIX signals, systemd, networking namespaces, TCP/IP stack).
* Dasar kontainerisasi menggunakan Docker (Dockerfile multi-stage, container runtime, OCI specs).
* Pengetahuan dasar Git workflow (Trunk-based development, semantic versioning).
* Konsep fundamental CI/CD (GitHub Actions / GitLab CI pipelines dasar).
* Konsep dasar Kubernetes (Pods, Deployments, Services, ConfigMaps).
* Pemahaman dasar sintaks HCL (Terraform) dan YAML.

---

## 3. Concept & Internal Architecture

Dalam lanskap enterprise, operasi produksi tidak lagi hanya tentang "menjalankan kode di server". Arsitektur produksi modern bertumpu pada **Distributed Systems Control Theory**, **Declarative State Machines**, dan **Zero Trust Security Model**.

```
+----------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE ARCHITECTURE OVERVIEW                                |
+----------------------------------------------------------------------------------------------------+
                                      [ Developer Workspace ]
                                                 |
                                     (Git Push / Pull Request)
                                                 v
+----------------------------------------------------------------------------------------------------+
| CI LAYER (Artifact Generation & Static Security Analysis)                                          |
|                                                                                                    |
| +-------------------+      +-------------------+      +-------------------+      +---------------+ |
| | Linter & SAST     | ---> | Unit/Integ Test   | ---> | Container Build   | ---> | Image Sign    | |
| | (SonarQube/Trivy) |      | (Jest/PyTest)     |      | (Multi-stage)     |      | (Cosign)      | |
| +-------------------+      +-------------------+      +-------------------+      +---------------+ |
+----------------------------------------------------------------------------------------------------+
                                                 |
                                     (Publish Signed Artifact)
                                                 v
                                   [ OCI Registry / Harbor ]
                                                 |
                       +-------------------------+-------------------------+
                       |                                                   |
                       v                                                   v
+-----------------------------------------------+   +-----------------------------------------------+
| GITOPS ENGINE (Control Plane)                 |   | SECURITY & SECRET CONTROL                     |
|                                               |   |                                               |
| +-------------------------------------------+ |   | +-------------------------------------------+ |
| | ArgoCD Application Controller             | |   | | HashiCorp Vault / External Secrets Operator| |
| |  - Watch Git Spec vs Cluster State        | |   | |  - Short-lived Dynamic Secrets            | |
| |  - Automated Drift Detection              | |   | |  - Mutual TLS (mTLS) Authentication        | |
| +-------------------------------------------+ |   | +-------------------------------------------+ |
+-----------------------------------------------+   +-----------------------------------------------+
                       |                                                   |
      (Reconciliation via Kube-API)                         (Inject In-Memory Tokens)
                       v                                                   v
+----------------------------------------------------------------------------------------------------+
| PRODUCTION CLUSTER (Kubernetes High Availability Topology)                                         |
|                                                                                                    |
|  [ Cloud Edge / L4/L7 Load Balancer ]                                                              |
|                     |                                                                              |
|                     v                                                                              |
|  [ Ingress Controller (Traefik/NGINX) with WAF ]                                                   |
|                     |                                                                              |
|        +------------+------------+ (Traffic Splitting: Canary 90/10)                               |
|        |                         |                                                                 |
|        v                         v                                                                 |
|  +------------------+   +------------------+                                                       |
|  | Stable Pods (v1) |   | Canary Pods (v2) |                                                       |
|  +------------------+   +------------------+                                                       |
|        |                         |                                                                 |
|        +------------+------------+                                                                 |
|                     |                                                                              |
|                     v                                                                              |
|  +-----------------------------------------------------------------------------------------------+ |
|  | OBSERVABILITY & AUTOMATED ANALYSIS                                                             | |
|  | - Prometheus Metrik: Error Rate (5xx), Latency P99, Saturation                                | |
|  | - OpenTelemetry Collector -> Distributed Tracing (Jaeger/Tempo)                               | |
|  | - Automated Rollback Controller (Flagger / Argo Rollouts)                                      | |
|  +-----------------------------------------------------------------------------------------------+ |
+----------------------------------------------------------------------------------------------------+
```

### 3.1. The Reconciliation Loop (Loop Rekonsiliasi)
Arsitektur produksi berbasis Kubernetes dan GitOps bekerja menggunakan pola matematika *Reconciliation Loop*:
$$\text{Drift} = \text{Desired State (Git)} - \text{Actual State (Cluster)}$$
Ketika $\text{Drift} \neq 0$, kontroler secara periodik mengeksekusi operasi mutasi infrastruktur (CRUD via Kube-API) hingga $\text{Drift} = 0$. Model ini menghilangkan intervensi manual (akses SSH atau `kubectl apply` langsung ke cluster) yang menjadi penyebab utama kegagalan audit dan *configuration drift*.

### 3.2. Immutable Infrastructure & Zero-Drift IaC
Dalam model infrastruktur *immutable*, server atau kontainer tidak pernah diperbarui (*patched/updated*) saat sedang berjalan (*in-place*). Jika terjadi perubahan kode, konfigurasi, atau sistem operasi:
1. *Base image* atau *manifest* baru dibangun.
2. Lingkungan baru di-deploy berdampingan dengan lingkungan lama.
3. Beban kerja dialihkan melalui perutean jaringan (*traffic routing*).
4. Lingkungan lama dimatikan (*decommissioned*).

State dikontrol melalui Terraform dengan *Distributed Locking* (misal: AWS S3 + DynamoDB) untuk mencegah eksekusi paralel yang merusak status state file.

### 3.3. Advanced Deployment Topology: Progressive Traffic Shifting
Alih-alih melakukan *Rolling Update* biasa yang dapat meloloskan *bug runtime* kritis ke seluruh basis pengguna, arsitektur enterprise menggunakan **Progressive Delivery (Canary Deployment)**:
* Sebanyak $N\%$ (misalnya 10%) lalu lintas diarahkan ke versi baru (Canary).
* Metrik kunci (HTTP 5xx rate, P99 Latency, Error logs) dievaluasi selama rentang waktu $T$.
* Jika kondisi metrik berada di bawah ambang batas (*threshold*), persentase dinaikkan secara bertahap ($10\% \to 25\% \to 50\% \to 100\%$).
* Jika metrik melanggar SLA (misalnya Error rate $> 1\%$), router mengembalikan trafik $100\%$ ke versi lama secara instan tanpa *downtime*.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Traditional Ops) | Pendekatan Enterprise Modern (Cloud-Native DevOps) |
| :--- | :--- | :--- |
| **Penyebaran (*Deployment*)** | Skrip Bash, SSH manual, mutasi server *in-place*. | Deklaratif, GitOps, *Progressive Canary / Blue-Green*. |
| **Manajemen Konfigurasi** | Dikelola manual di server (`/etc/config`), rawan hilang. | *Immutable ConfigMaps*, Secrets terenkripsi via KMS/Vault. |
| **Secret Management** | `.env` file statis tersimpan di server atau repositori. | *Dynamic short-lived tokens*, *zero-footprint secret engine*. |
| **State Drift** | Mengabaikan perbedaan konfigurasi antara dev dan prod. | *Automated reconciliation*, *self-healing cluster*. |
| **Respon Insiden** | Manual debugging via log file SSH setelah sistem down. | *Automated Canary Rollback* berdasarkan metrik observabilitas. |

### Mengapa Pendekatan Enterprise Diperlukan?
1. **Mengurangi MTTR (*Mean Time to Recovery*)**: Dengan deployment berbasis GitOps dan *immutable infrastructure*, jika sistem mengalami kegagalan, *rollback* dilakukan hanya dengan mengembalikan Git commit (`git revert`), mengembalikan infrastruktur ke kondisi stabil dalam hitungan detik.
2. **Kepatuhan Kriptografis dan Audit (*Compliance & Provenance*)**: Setiap baris kode, image container, dan perubahan infrastruktur diverifikasi secara kriptografis (*Signed Commits*, *Cosign Image Signatures*).
3. **Mencegah "Works on My Machine"**: Menjamin *Environment Parity* mutlak antara lingkungan Development, Staging, dan Production.

---

## 5. How (Workflow Detail)

Alur kerja penyebaran produksi enterprise dari kode sumber hingga runtime produksi:

```
[Developer] 
    | 
    +--> Push branch feature
    +--> Open PR to `main`
          |
          v
[GitHub Actions CI]
    +--> Step 1: Linting, Unit Testing, Secret Scanning (Gitleaks)
    +--> Step 2: SAST (SonarQube) & Dependency Scanning (Trivy)
    +--> Step 3: Build Multi-stage Minimal Container (Distroless)
    +--> Step 4: Sign Image using Sigstore/Cosign with KMS
    +--> Step 5: Push Image to Enterprise Registry
    +--> Step 6: Clone GitOps Repo -> Update Helm/Kustomize Image Tag via PR
          |
          v
[GitOps Controller (ArgoCD)]
    +--> Step 1: Detect commit on GitOps repo (Desired State)
    +--> Step 2: Pull cryptographic keys, authenticate to Vault
    +--> Step 3: Generate and validate Kubernetes manifests
    +--> Step 4: Initialize Argo Rollouts Canary Strategy:
         |-- Route 10% traffic to new ReplicaSet
         |-- Monitor Prometheus metrics for 5 minutes
         |-- IF (Metric == Healthy): Shift to 50% -> 100%
         \-- ELSE: Instantly abort, route 100% traffic back to Stable ReplicaSet
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Menara Pengawas Bandara Internasional
Sistem produksi enterprise seperti manajemen lalu lintas udara di bandara internasional:
* **Infrastruktur Tradisional**: Pilot mendarat manual di landasan yang tidak teratur, mengandalkan insting tanpa komunikasi radio terpusat.
* **Modern Production Architecture**:
  * **GitOps (Flight Plan)**: Rencana penerbangan yang terdokumentasi dan tidak boleh diubah tanpa persetujuan resmi.
  * **Kubernetes Control Plane (Air Traffic Controller)**: Menjaga jarak antar pesawat secara otomatis (*reconciliation loop*).
  * **Canary Deployment (Test Flight)**: Mengirimkan satu pesawat uji coba dengan instrumen diagnostik canggih sebelum membuka landasan pacu baru untuk ribuan penumpang umum.
  * **Observability (Radar & Sensor Telemetri)**: Mengetahui secara presisi koordinat, kecepatan, dan tekanan kabin tanpa harus menebak.

```
                  +-----------------------------------+
                  |           Ingress Gateway         |
                  |     (L7 Envoy Traffic Router)     |
                  +-----------------------------------+
                                    |
                 +------------------+------------------+
                 | (90% Traffic)                       | (10% Traffic)
                 v                                     v
     +-----------------------+             +-----------------------+
     |   STABLE POOL (v1.0)  |             |   CANARY POOL (v2.0)  |
     |  +--------+ +-------+ |             |  +--------+           |
     |  | Pod 01 | | Pod 02| |             |  | Pod C1 |           |
     |  +--------+ +-------+ |             |  +--------+           |
     +-----------------------+             +-----------------------+
                 |                                     |
                 \------------------+------------------/
                                    |
                                    v
                     +-----------------------------+
                     |    Prometheus Metrics Scrape|
                     |  - Rate HTTP 5xx: 0.01%     |
                     |  - Latency P99: 45ms        |
                     +-----------------------------+
                                    |
                          (Metrics within SLA)
                                    v
                  [Promote Canary to 100% Traffic]
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Zero-Downtime Multi-Stage Dockerfile (Enterprise Node.js/Go)
Praktik produksi mewajibkan ukuran kontainer sekecil mungkin (*minimal attack surface*) dan berjalan sebagai *non-root user*.

```dockerfile
# syntax=docker/dockerfile:1.4
# Stage 1: Build & Dependencies
FROM node:20-alpine AS builder
WORKDIR /usr/src/app

# Pasang package files untuk memaksimalkan layer caching
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

COPY . .
RUN npm run build && npm prune --production

# Stage 2: Runtime Minimalis dengan Non-Root Execution
FROM gcr.io/distroless/nodejs20-debian12:nonroot
WORKDIR /app

# Ambil hanya artefak yang siap dieksekusi dari builder
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY --from=builder /usr/src/app/dist ./dist
COPY --from=builder /usr/src/app/package.json ./package.json

# Jalankan sebagai non-root (UID 65532 disediakan distroless)
USER 65532:65532
EXPOSE 8080

ENV NODE_ENV=production
ENTRYPOINT ["/nodejs/bin/node", "dist/index.js"]
```

### 7.2. Practical Example: Production-Grade IaC & Canary Manifests

#### 7.2.1. Terraform State Locking (AWS S3 + DynamoDB)
File: `main.tf`
```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend jarak jauh aman dengan State Locking pencegah korupsi konkurensi
  backend "s3" {
    bucket         = "enterprise-tfstate-production-secure"
    key            = "core-infra/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "terraform-state-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = "ap-southeast-1"
  default_tags {
    tags = {
      Environment = "Production"
      ManagedBy   = "Terraform"
      Owner       = "CoreSRE"
    }
  }
}

resource "aws_dynamodb_table" "tf_locks" {
  name         = "terraform-state-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}
```

#### 7.2.2. Argo Rollouts Canary Strategy Manifest
File: `rollout.yaml`
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: payments-microservice
  namespace: core-banking
spec:
  replicas: 10
  revisionHistoryLimit: 5
  selector:
    matchLabels:
      app: payments-microservice
  template:
    metadata:
      labels:
        app: payments-microservice
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 65532
        fsGroup: 65532
      containers:
      - name: payments
        image: harbor.internal.net/banking/payments:v2.1.0
        ports:
        - containerPort: 8080
          name: http
        resources:
          limits:
            cpu: "1000m"
            memory: "1024Mi"
          requests:
            cpu: "200m"
            memory: "256Mi"
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
  strategy:
    canary:
      # Analisis metrik otomatis selama deployment
      analysis:
        templates:
        - templateName: success-rate-check
        args:
        - name: service-name
          value: payments-microservice
      steps:
      - setWeight: 10
      - pause: { duration: 5m }
      - setWeight: 30
      - pause: { duration: 10m }
      - setWeight: 60
      - pause: { duration: 10m }
```

#### 7.2.3. AnalysisTemplate untuk Canary Metric Verification
File: `analysistemplate.yaml`
```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate-check
  namespace: core-banking
spec:
  args:
  - name: service-name
  metrics:
  - name: success-rate
    interval: 30s
    successCondition: result[0] >= 0.999
    failureLimit: 3
    provider:
      prometheus:
        address: http://prometheus-k8s.monitoring.svc.cluster.local:9090
        query: |
          sum(rate(http_requests_total{service="payments-microservice",status!~"5.*"}[2m]))
          /
          sum(rate(http_requests_total{service="payments-microservice"}[2m]))
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Platform E-Commerce "MegaMart" (Flash Sale 11.11)
* **Konteks**: Layanan Checkout MegaMart menangani 150.000 Request Per Second (RPS) saat event belanja tahunan.
* **Insiden Lama**: Pembaruan kode via *rolling update* standar Kubernetes menyebabkan crash berantai (*cascading failure*). Pod baru lulus readiness probe (HTTP 200 sederhana), tetapi mengalami dead-lock database ketika menerima query produksi intensif. Seluruh pod berganti ke pod yang rusak; downtime 42 menit dengan taksiran kerugian $1.2M.

### Arsitektur Rekayasa Solusi Baru:
1. **Pemisahan Trafik melalui Service Mesh (Istio) & Argo Rollouts**:
   * Pembaruan dialihkan melalui canary split: 2% trafik dialihkan ke pods versi baru.
2. **Prometheus Latency & DB Saturation Analysis**:
   * Metric AnalysisTemplate mengukur rasio error HTTP 5xx dan *Database Connection Pool Saturation*.
   * Jika saturasi pool DB canary melonjak di atas 85% dalam jendela waktu 3 menit, rollout langsung dibatalkan secara otomatis (*automated abort*).
3. **Hasil**:
   * Pada rilis berikutnya, sebuah kebocoran koneksi (connection leak) terdeteksi saat bobot trafik baru mencapai 2%. Sistem membatalkan deployment otomatis dalam waktu 90 detik.
   * Hanya 0,004% pengguna yang terdampak kegagalan sementara sebelum circuit breaker aktif; 99,996% transaksi berjalan normal di versi stabil tanpa keterlibatan manual SRE di malam hari.

---

## 9. Trade-offs

Setiap keputusan arsitektur tingkat produksi memiliki konsekuensi teknis dan operasional:

```
+----------------------------------------------------------------------------------------------------+
|                                    ARCHITECTURAL TRADE-OFFS                                        |
+--------------------------+----------------------------+--------------------------------------------+
| Strategi                 | Keuntungan (+)             | Kerugian / Tantangan (-)                   |
+--------------------------+----------------------------+--------------------------------------------+
| Canary Deployment        | Blast radius kecil.        | Biaya komputasi meningkat (menjalankan     |
| Berbasis Metrik          | Pembatalan terotomatisasi. | 2 versi paralel); penanganan skema         |
|                          | Zero-downtime teruji.      | migrasi DB kompleks (harus backward-compat)|
+--------------------------+----------------------------+--------------------------------------------+
| GitOps                   | Audit trail sempurna.      | Latensi sinkronisasi (sync loop delay).    |
| (Pull-based)             | Single source of truth.    | Kompleksitas troubleshooting rekonsiliasi. |
|                          | Drift otomatis terkoreksi. | Membutuhkan repositori kontrol terpisah.   |
+--------------------------+----------------------------+--------------------------------------------+
| Multi-Cloud /            | Ketahanan bencana (DR)     | Biaya jaringan egress tinggi.              |
| Multi-Region Active-Act  | tinggi. RPO/RTO mendekati  | Kompleksitas replikasi stateful database   |
|                          | nol. Resonansi latensi geo.| (CAP Theorem: Latensi vs Konsistensi).     |
+--------------------------+----------------------------+--------------------------------------------+
```

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan 1: Readiness Probe Terlalu Dangkal (False Positive Ready)
* **Penyebab**: Probe hanya mengembalikan status `200 OK` statis tanpa memverifikasi fungsionalitas esensial sistem (misal: koneksi database atau message broker).
* **Dampak**: Kubelet menganggap Pod sudah sehat dan mengalirkan trafik, padahal aplikasi mengalami *crash loop* saat mengeksekusi koneksi riil.
* **Solusi**: Pisahkan Liveness (`/healthz` - cek dead-lock thread internal) dan Readiness (`/ready` - cek dependensi vital downstream).

### Kesalahan 2: Tidak Menetapkan Resource Limits atau Memory Overcommit
* **Gejala Log**: Pod mati secara mendadak dengan status exit code 137.
* **Diagnosa Error**:
  ```bash
  $ kubectl describe pod payments-microservice-7bb8c-x8qzp
  Last State:     Terminated
    Reason:       OOMKilled
    Exit Code:    137
  ```
* **Penyebab**: Aplikasi melampaui alokasi memori yang diizinkan, sehingga Linux Kernel OOM Killer mematikan proses container.
* **Mitigasi**: Selalu definisikan `resources.requests` dan `resources.limits` secara terukur berdasarkan profiling beban uji (load testing), bukan tebakan.

### Kesalahan 3: Terraform State Inconsistency (Lock Timeout)
* **Diagnosa Error**:
  ```text
  Error: Error acquiring the state lock: ConditionalCheckFailedException:
  The conditional request failed. Lock Info: ID: 3b14... Info: Operation: Apply
  ```
* **Troubleshooting Step**:
  1. Pastikan tidak ada pipeline CI/CD lain yang sedang berjalan secara simultan pada state yang sama.
  2. Jika proses sebelumnya mati mendadak (abrupt exit/terminated worker):
     ```bash
     terraform force-unlock <LOCK-ID>
     ```
  3. Konfigurasikan `lock_timeout = "5m"` pada konfigurasi provider agar pipeline menunggu antrean proses selesai.

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum mengizinkan aplikasi berjalan di klaster produksi:

### Keamanan & Runtime
- [ ] Container berjalan sebagai **Non-Root** user (UID $\neq$ 0).
- [ ] Root filesystem diset ke kondisi `readOnlyRootFilesystem: true`.
- [ ] Capabilities Linux yang berbahaya (`CAP_SYS_ADMIN`, `CAP_NET_ADMIN`) dinonaktifkan (`drop: ["ALL"]`).
- [ ] Image dipindai dari celah keamanan CVE kritis (Trivy/Clair: Zero Critical/High severity).

### Ketersediaan & Resilience
- [ ] `PodDisruptionBudget` (PDB) terkonfigurasi (minimal `minAvailable: 50%` atau `maxUnavailable: 1`).
- [ ] Aturan `topologySpreadConstraints` atau `podAntiAffinity` aktif agar Pod tersebar di lintas Availability Zone (AZ).
- [ ] Menetapkan `terminationGracePeriodSeconds` yang memadai (misal: 30-60 detik) untuk membiarkan koneksi in-flight selesai sebelum Pod di-SIGKILL.

### Observabilitas & Konfigurasi
- [ ] Log ditulis secara terstruktur dalam format JSON ke `stdout`/`stderr`.
- [ ] Trace Context W3C (`traceparent`) dipropagasikan di setiap panggilan antar-layanan.
- [ ] Metrik aplikasi diekspos dengan endpoint standar `/metrics` untuk Prometheus.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun pipeline simulasi produksi lengkap dengan GitOps & Automated Rollback lokal menggunakan K3d/Kind dan Argo Rollouts. Seluruh artefak disimpan di: `hands-on/m02/`.

### Struktur Direktori:
```text
hands-on/m02/
├── app/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── manifests/
│   ├── namespace.yaml
│   ├── rollout.yaml
│   ├── service.yaml
│   └── analysis.yaml
└── test-deployment.sh
```

### Langkah 1: Persiapan Aplikasi & Kontainer
Buat file `hands-on/m02/app/app.py`:
```python
import os
from flask import Flask, Response

app = Flask(__name__)
# Ambil versi dari environment variable
APP_VERSION = os.getenv("APP_VERSION", "v1.0.0")
FAIL_FLAG = os.getenv("FAIL_MODE", "false")

@app.route("/")
def index():
    if FAIL_FLAG == "true":
        return Response("Internal Server Error (Simulated)", status=500)
    return Response(f"Hello from Production API - Version: {APP_VERSION}\n", status=200)

@app.route("/healthz")
def health():
    return Response("OK", status=200)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
```

Buat file `hands-on/m02/app/Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
USER 10001:10001
EXPOSE 8080
CMD ["python", "app.py"]
```

Buat `hands-on/m02/app/requirements.txt`:
```text
flask==3.0.0
```

### Langkah 2: Build Image Lokal
```bash
cd hands-on/m02/app
docker build -t local-api:v1.0.0 --build-arg APP_VERSION=v1.0.0 .
docker build -t local-api:v2.0.0-bad --build-arg APP_VERSION=v2.0.0-bad .
```

### Langkah 3: Konfigurasi Klaster & Argo Rollouts
Jalankan cluster pengujian lokal (contoh menggunakan `minikube` atau `k3d`):
```bash
# Menggunakan k3d
k3d cluster create prod-simulation --servers 1 --agents 2

# Impor image lokal ke klaster k3d
k3d image import local-api:v1.0.0 local-api:v2.0.0-bad -c prod-simulation

# Install Argo Rollouts
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml
```

### Langkah 4: Terapkan Manifests
File `hands-on/m02/manifests/rollout.yaml`:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: demo-api-rollout
  namespace: default
spec:
  replicas: 5
  strategy:
    canary:
      steps:
      - setWeight: 20
      - pause: { duration: 30s }
      - setWeight: 50
      - pause: { duration: 30s }
  selector:
    matchLabels:
      app: demo-api
  template:
    metadata:
      labels:
        app: demo-api
    spec:
      containers:
      - name: api
        image: local-api:v1.0.0
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8080
        env:
        - name: APP_VERSION
          value: "v1.0.0"
        - name: FAIL_MODE
          value: "false"
```

Terapkan manifest:
```bash
kubectl apply -f hands-on/m02/manifests/rollout.yaml
```

### Langkah 5: Simulasikan Pembaruan Gagal & Verifikasi Rollback
Uji pembaruan aplikasi dengan image yang rusak:
```bash
# Update rollout menggunakan image v2.0.0-bad dengan FAIL_MODE=true
kubectl argo rollouts set image demo-api-rollout api=local-api:v2.0.0-bad
kubectl set env rollout/demo-api-rollout FAIL_MODE="true"

# Amati perpindahan traffic dan eksekusi rollback manual/otomatis
kubectl argo rollouts get rollout demo-api-rollout --watch
```

---

## 13. Exercise

### Tingkat Easy
1. Ubah konfigurasi Dockerfile pada sub-bab 7.1 dengan menambahkan flag `HEALTHCHECK` native Docker yang memeriksa status `/healthz` setiap 10 detik.
2. Tuliskan manifest Kubernetes `HorizontalPodAutoscaler` (HPA) yang melakukan scaling horizontal pada `demo-api` jika rata-rata pemakaian CPU melewati ambang 75%.

### Tingkat Medium
1. Konfigurasikan `AnalysisTemplate` Prometheus untuk membaca metrik HTTP rate dan secara otomatis memerintahkan Argo Rollouts membatalkan deployment jika rasio HTTP 5xx melebihi 2% dalam durasi observasi 60 detik.
2. Buat script Terraform modular untuk membuat arsitektur VPC multi-AZ (3 Availability Zones) lengkap dengan Private Subnets, Public Subnets, dan NAT Gateway terisolasi.

### Tingkat Hard
1. Buat pipeline GitOps end-to-end yang mengintegrasikan verifikasi tanda tangan kriptografis Cosign. Deployment di cluster Kubernetes harus diblokir secara otomatis oleh Admission Controller (seperti Kyverno atau OPA Gatekeeper) jika container image yang digunakan belum ditandatangani oleh sertifikat KMS perusahaan.

---

## 14. Challenge

### Studi Kasus Produksi Kompleks: Zero-Downtime Database Schema Migration

**Latar Belakang:**
Sistem pembayaran legacy enterprise memiliki tabel transaksi monolith bernama `orders` dengan volume data > 80 juta baris di PostgreSQL. Tim pengembangan perlu memecah kolom `customer_name` menjadi dua kolom baru: `first_name` dan `last_name` tanpa menghentikan sistem (*zero-downtime*), tanpa memutus ketersediaan penulisan (*read/write lock timeout*), dan mendukung strategi Canary deployment di mana Pod versi lama (v1) dan Pod versi baru (v2) akan beroperasi berdampingan selama minimal 24 jam.

**Tugas Arsitektur:**
1. Rancang arsitektur siklus migrasi database menggunakan pola **Expand and Contract (Parallel Run Pattern)**.
2. Dokumentasikan seluruh fase transisi (Fase 1: Expand, Fase 2: Double Write, Fase 3: Backfill, Fase 4: Contract) beserta skrip SQL DDL/DML non-blocking (gunakan `CONCURRENTLY` dan mitigasi table lock).
3. Buat rancangan penanganan kegagalan (*contingency rollback plan*) jika proses canary rilis v2 dibatalkan secara mendadak oleh sistem metrik saat Fase Double-Write sedang berlangsung, dengan jaminan tidak ada integritas data yang hilang (*zero data loss*).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic
1. Mengapa pendekatan *immutable infrastructure* lebih dipilih pada arsitektur produksi modern dibandingkan konfigurasi *in-place* menggunakan skrip automation seperti Ansible?
2. Apa fungsi mendasar dari *Reconciliation Loop* dalam arsitektur Kubernetes control plane?
3. Sebutkan perbedaan utama antara probe `readinessProbe` dan `livenessProbe` di Kubernetes!
4. Mengapa file `.tfstate` pada Terraform wajib disimpan pada *Remote Backend* dengan *Locking Mechanism* ketika dikerjakan dalam tim enterprise?
5. Mengapa container produksi dilarang keras dijalankan menggunakan user `root` (UID 0)?

### 15.2. Pertanyaan Intermediate
1. Bagaimana cara service mesh (seperti Istio/Envoy) membagi trafik persentase canary secara presisi tanpa bergantung pada jumlah replika Pod Kubernetes?
2. Dalam pipeline CI/CD modern, apa yang dimaksud dengan proses *Cryptographic Image Signing* (misal menggunakan Sigstore/Cosign), dan celah keamanan apa yang dimitigasi oleh metode ini?
3. Jelaskan risiko arsitektur yang dikenal sebagai *Split-Brain Syndrome* pada cluster High Availability (HA) dan bagaimana algoritma quorum (misal Raft/etcd) mencegah hal tersebut!
4. Mengapa penggunaan GitOps *pull-based deployment* (ArgoCD) dinilai lebih aman dibandingkan metode *push-based deployment* (CI server mengeksekusi `kubectl` via service account credentials)?
5. Bagaimana cara kerja mekanisme *Graceful Shutdown* di Kubernetes ketika sebuah Pod menerima sinyal `SIGTERM`, dan mengapa `sleep` singkat sebelum terminasi sering ditambahkan dalam hook `preStop`?

### 15.3. Skenario Kasus Produksi

#### Skenario 1: The Cascading Connection Storm
*Kasus:* Pada saat peak load, salah satu instans microservice mengalami crash karena kehabisan alokasi memori. Kubernetes mendeteksi kegagalan tersebut dan segera menjadwalkan ulang pod pengganti. Namun, begitu pod baru aktif, pod tersebut langsung mati lagi secara beruntun (*crash looping*), menyebabkan pod-pod lain di klaster ikut tumbang secara bergantian (cascading failure).
*Tugas:* Identifikasi kemungkinan akar masalah arsitektur ini dan susun solusi mitigasinya (pertimbangkan aspek circuit breaker, connection pooling, dan liveness probe probe configuration).

#### Skenario 2: Asymmetric GitOps Drift
*Kasus:* Seorang teknisi senior SRE melakukan modifikasi langsung pada konfigurasi ConfigMap di klaster produksi menggunakan `kubectl edit` untuk mengatasi insiden darurat tengah malam. Dua hari kemudian, sebuah commit merge biasa yang tidak berhubungan dilakukan di Git repository. Tiba-tiba perbaikan darurat yang dibuat oleh SRE tersebut hilang dan insiden lama terulang kembali.
*Tugas:* Jelaskan mekanisme apa yang menyebabkan konfigurasi tersebut tertimpa secara otomatis, dan tentukan alur operasional standar (SOP) yang seharusnya diterapkan oleh tim SRE tersebut.

#### Skenario 3: The Ghost Canary Leak
*Kasus:* Tim platform merilis Canary deployment untuk modul penagihan (billing) dengan rasio 5% trafik selama 1 jam. Evaluasi metrik menunjukkan HTTP status code sukses 99.99%. Namun, setelah 30 menit berjalan, tim akuntansi melaporkan terdapat transaksi duplikat pada sejumlah pengguna yang masuk ke dalam pool canary.
*Tugas:* Analisis di mana kegagalan perancangan sistem terjadi (khususnya relasi antara antrean worker/asynchronous processing dan arsitektur deployment paralel dua versi).

---

## 16. Summary

1. **Prinsip Immutability**: Di lingkungan produksi modern, server dan kontainer adalah komponen sekali pakai (*ephemeral*). Semua mutasi dilakukan dengan merilis artefak baru secara deklaratif, bukan mengubah konfigurasi runtime yang sedang aktif.
2. **GitOps sebagai Sumber Kebenaran (*Single Source of Truth*)**: GitOps memformalkan status sistem secara deklaratif di mana loop rekonsiliasi terus-menerus membandingkan dan memperbaiki *drift* antara definisi Git dan implementasi nyata di cluster.
3. **Penyebaran Berbasis Risiko (*Risk-Mitigated Deployments*)**: Pola Canary dan Blue/Green deployment dengan analisis metrik telemetri otomatis menjamin bahwa *blast radius* dari kode yang cacat dapat diisolasi dan dihentikan sebelum menimbulkan dampak meluas pada pengguna.
4. **Keamanan Berlapis (*Zero Trust Security*)**: Mengamankan siklus pengiriman perangkat lunak memerlukan pembuktian kriptografis pada setiap rantai pasok: mulai dari kode yang ditandatangani, pemindaian vulnerabilitas otomatis, artefak kontainer tanpa root (*distroless*), hingga secret dinamis tanpa persistensi statis di file konfigurasi.