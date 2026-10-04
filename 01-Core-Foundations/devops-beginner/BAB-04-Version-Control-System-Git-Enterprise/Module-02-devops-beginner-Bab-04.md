# Kurikulum DevOps Foundations: Modul 02 — Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Merancang dan mengeksekusi arsitektur pipeline CI/CD produksi dengan pola rilis mutakhir (*Canary* dan *Blue/Green Deployment*) menggunakan GitOps engine.
- Mengelola status infrastruktur deklaratif (*Infrastructure as Code*) skala enterprise menggunakan remote backend terenkripsi, distributed state locking, dan strategi isolasi lingkungan (*environment blast radius mitigation*).
- Mengonfigurasi arsitektur orkestrasi kontainer dengan kapabilitas *self-healing*, *predictive horizontal auto-scaling*, *graceful shutdown*, serta penegakan kebijakan keamanan berbasis *Kubernetes Admission Controllers* dan *Network Policies*.
- Membangun pipeline observabilitas terpadu (Metrics, Logs, Traces) berbasis OpenTelemetry dan Prometheus, serta merumuskan Service Level Indicators (SLI) dan Service Level Objectives (SLO) yang dapat ditindaklanjuti secara matematis.

---

## 2. Prerequisite

Peserta wajib memahami materi sebelumnya:
- **Core OS & Networking**: Linux Kernel fundamentals (namespaces, cgroups), TCP/IP stack, TLS termination, DNS routing.
- **Fundamental DevOps**: Penggunaan dasar Git, Docker (Dockerfile multi-stage, container lifecycle), dasar-dasar CI/CD GitHub Actions/GitLab CI, serta pemahaman sintaks deklaratif YAML & HashiCorp Configuration Language (HCL).
- **Akses Lingkungan**: Mesin lokal atau cloud VM dengan hak akses root/sudo, Docker Engine terpasang, `kubectl`, `terraform` CLI (>= 1.5.x), dan kluster Kubernetes (Minikube, Kind, atau cloud provider managed Kube seperti EKS/GKE).

---

## 3. Concept & Internal Architecture (Mendalam)

### A. Rekonsiliasi Status Deklaratif (The Control Loop Model)
Sistem orkestrasi modern (seperti Kubernetes dan GitOps controller) beroperasi bukan secara imperatif (menjalankan instruksi sekuensial), melainkan menggunakan model matematika *Closed-Loop Control System* (sering disebut *Reconciliation Loop*).

```
          +-------------------------------------------------+
          |                                                 |
          v                                                 |
   [ Target State ] ---> [ Compare (Diff) ] ---> [ Actuate (Mutate) ]
          ^                      |
          |                      v
   (Git / IaC Repo)      [ Actual State ]
                         (Live Cluster/Cloud)
```

1. **Observe**: Controller membaca *Actual State* dari API Server (status riil pod, node, atau resource cloud).
2. **Compare**: Controller membandingkan *Actual State* dengan *Desired/Target State* yang didefinisikan dalam Git (GitOps source of truth).
3. **Actuate**: Jika terjadi *drift* ($\Delta = \text{Desired} - \text{Actual} \neq 0$), controller menginstruksikan driver sistem untuk melakukan mutasi hingga $\Delta = 0$.

### B. Arsitektur Progressive Delivery (Canary via Service Mesh / Ingress Controller)
Pada Canary Deployment tingkat lanjut, pemisahan lalu lintas (traffic splitting) tidak lagi bergantung pada jumlah replika Pod (rasio pod count), melainkan diarahkan pada layer 7 (HTTP Request Layer) menggunakan manipulasi bobot (*weight-based routing*) atau HTTP header matching.

```
Incoming Request ---> [ Ingress / Service Mesh Data Plane (Envoy) ]
                                /              \
                   (Weight: 90%)                (Weight: 10%)
                               v                  v
                   [ Stable Service v1.0 ]      [ Canary Service v1.1 ]
                               |                  |
                   [ Deployment: v1.0 Pods ]    [ Deployment: v1.1 Pods ]
```

Arsitektur ini membutuhkan metrik analitik real-time. Jika metrik Canary (misal: HTTP 5xx error rate > 0.5% atau latency P99 > 200ms) melampaui batas toleransi SLO, *Automated Rollback Engine* langsung mengembalikan routing ke stable service tanpa campur tangan manusia.

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal di Skala Enterprise?
1. **ClickOps & Script Imperatif**: Membangun cloud via UI konsol atau shell script linear rentan terhadap *configuration drift*, ketiadaan audit trail, dan ketidakmampuan mereproduksi lingkungan (*unreproducible environments*).
2. **Big-Bang Deployment**: Merilis versi perangkat lunak secara langsung memutus koneksi aktif, menimbulkan downtime, dan meningkatkan Mean Time to Recovery (MTTR) saat insiden terjadi.
3. **Siloed Observability**: Monitoring reaktif berbasis pemeriksaan log manual pasca-insiden menyebabkan pelanggaran SLA finansial. Observabilitas modern harus bersifat proaktif dan berbasis instrumentasi metrik kuantitatif.

### Apa yang Dibangun dalam Arsitektur Ini?
Kita membangun sistem rilis berbasis **GitOps Continuous Delivery** terotomasi penuh dengan:
- **State Store Engine**: Terraform State pada Object Storage dengan DynamoDB/Consul distributed locking.
- **Application Orchestration**: Kubernetes Pod Lifecycle Management yang kebal terhadap *node eviction*, *graceful termination*, dan zero-downtime rolling/canary.
- **Telemetry Mesh**: Agregasi metrik golden signals (Latency, Traffic, Errors, Saturation) yang memicu mitigasi otomatis.

---

## 5. How (Workflow Detail)

Alur kerja implementasi arsitektur produksi:

```
[ Developer ]
      |
      | 1. Git Push (Feature Branch)
      v
[ Git Repository ] ---> 2. Webhook trigger
      |
      v
[ CI Pipeline (Test & Build) ]
      |
      | 3. Lint, Unit Test, SAST, Multi-arch Build, Trivy Image Scan
      | 4. Sign Container Image (Cosign) & Push to Registry
      v
[ Container Registry (OCI) ]
      ^
      |
[ CD GitOps Pipeline ] <--- 5. PR Merged to Main (Update K8s Manifests Tag)
      |
      | 6. ArgoCD / Flux Engine mendeteksi drift
      v
[ Target Kubernetes Production Cluster ]
      |
      +---> 7. Admission Controller validasi manifest (OPA Gatekeeper/Kyverno)
      +---> 8. Flagger/Argo Rollouts menginisiasi Canary Deployment
      +---> 9. Traffic Router membagi beban (90/10 -> 80/20 -> 0/100)
      +---> 10. Prometheus scrape SLI -> Prometheus Alertmanager
```

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem
Bayangkan memindahkan lalu lintas kereta api supercepat dari rel lama ke rel baru tanpa menghentikan satu pun kereta:
- **Big-Bang**: Menghentikan seluruh jadwal kereta, membongkar rel lama, memasang rel baru, lalu berharap tidak ada baut yang terlepas.
- **Canary GitOps**: Memasang wesel otomatis. Awalnya, kirim satu gerbong uji kosong (Canary). Pantau getaran rel dengan sensor seismik (Prometheus). Jika stabil, alihkan 10% gerbong penumpang, lalu bertahap hingga 100%. Jika sensor mendeteksi anomali pada sambungan rel, wesel otomatis berbalik seketika ke rel lama.

### Diagram Topologi Arsitektur Produksi

```
+-----------------------------------------------------------------------------------+
| VPC / Production Network                                                          |
|                                                                                   |
|  [ Ingress Gateway (ALB / NGINX / Traefik) ] (TLS Offloading & WAF)              |
|                         |                                                         |
|         +---------------+---------------+                                         |
|         | Weight: 90%                   | Weight: 10%                             |
|         v                               v                                         |
|  +---------------------------+   +---------------------------+                    |
|  | K8s Cluster: Stable Pool  |   | K8s Cluster: Canary Pool  |                    |
|  | [Pod v1] [Pod v1] [Pod v1]|   | [Pod v2 (Candidate)]      |                    |
|  +---------------------------+   +---------------------------+                    |
|         |                               |                                         |
|         +---------------+---------------+                                         |
|                         |                                                         |
|                         v                                                         |
|  [ Internal Mesh / Private Network ]                                              |
|         |                                                                         |
|         v                                                                         |
|  [ Cloud Managed Database Cluster ] <--- State Management Lock (Terraform/IaC)    |
|    (Primary-Replica, Multi-AZ)                                                    |
+-----------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### A. Terraform Enterprise Pattern (Infrastructure as Code)
Contoh definisi modul Terraform produksi dengan isolasi remote state, enkripsi, dan penegakan dependensi.

```hcl
# backend.tf
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket         = "corp-production-tfstate-secure"
    key            = "core-infrastructure/vpc/terraform.tfstate"
    region         = "ap-southeast-1"
    encrypt        = true
    dynamodb_table = "corp-production-tflocks"
  }
}

# main.tf
module "secure_vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.1.2"

  name = "production-vpc"
  cidr = "10.100.0.0/16"

  azs             = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"]
  private_subnets = ["10.100.1.0/24", "10.100.2.0/24", "10.100.3.0/24"]
  public_subnets  = ["10.100.101.0/24", "10.100.102.0/24", "10.100.103.0/24"]

  enable_nat_gateway     = true
  single_nat_gateway     = false # High Availability: 1 NAT Gateway per AZ
  one_nat_gateway_per_az = true
  enable_vpn_gateway     = false

  enable_dns_hostnames = true
  enable_dns_support   = true

  manage_default_security_group = true
  default_security_group_ingress = [] # Deny-all inbound default
  default_security_group_egress  = [] # Deny-all outbound default

  tags = {
    Environment = "production"
    ManagedBy   = "Terraform"
    Compliance  = "PCI-DSS"
  }
}
```

### B. Production-Grade Kubernetes Manifest (Deployment, PDB & HPA)
Manifest aplikasi microservice yang kebal terhadap kegagalan infrastruktur, dilengkapi penanganan sinyal SIGTERM (*graceful shutdown*), health checks, dan Pod Disruption Budget (PDB).

```yaml
# app-production.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-processor
  namespace: finance
  labels:
    app.kubernetes.io/name: payment-processor
    app.kubernetes.io/part-of: core-banking
spec:
  replicas: 3
  revisionHistoryLimit: 10
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 0
  selector:
    matchLabels:
      app: payment-processor
  template:
    metadata:
      labels:
        app: payment-processor
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      terminationGracePeriodSeconds: 60
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: payment-api
          image: internal-registry.corp.net/finance/payment-processor:v2.4.1
          imagePullPolicy: IfNotPresent
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          ports:
            - containerPort: 8080
              name: http
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "1Gi"
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 15"] # Graceful drainage window
          livenessProbe:
            httpGet:
              path: /healthz/live
              port: http
            initialDelaySeconds: 15
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /healthz/ready
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 2
            failureThreshold: 2
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: payment-processor-pdb
  namespace: finance
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: payment-processor
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: payment-processor-hpa
  namespace: finance
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: payment-processor
  minReplicas: 3
  maxReplicas: 15
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Arsitektur Transaksi Finansial Tier-1
- **Profil Perusahaan**: Platform E-Commerce Pembayaran Terintegrasi.
- **Beban Kerja**: 45.000 Request Per Second (RPS) pada peak hours.
- **Kondisi Awal**: Tim engineering melakukan deployment manual berbasis kubectl apply via CI runners langsung ke cluster production. 
- **Insiden Kritis**: Sebuah konfigurasi environment variable database connection pool typo ter-deploy langsung ke 100% replika pod, mengakibatkan database pool starvation seketika, pemadaman sistem (outage) selama 47 menit, dan kerugian transaksi senilai USD 1.2M.

### Solusi Arsitektural yang Diterapkan
1. **Pemisahan Kontrol Bidang (GitOps)**: Menghapus hak akses write ke Kubernetes API dari sistem CI eksternal. Menggunakan ArgoCD yang berjalan di dalam cluster isolated control plane.
2. **Implementasi Progressive Delivery**: Mengintegrasikan Argo Rollouts dengan analisis canary otomatis berbasis metrik P99 Latency dan HTTP error rates dari Prometheus.
3. **Formulasi Validasi Canary**:
   $$\text{Error Rate} = \frac{\sum \text{rate}(\text{http\_requests\_total}\{status=\sim"5.."\}[\text{2m}])}{\sum \text{rate}(\text{http\_requests\_total}[\text{2m}])} \times 100$$
   Jika Error Rate $\ge 0.1\%$ selama fase analisis 5 menit, rilis otomatis di-abort, lalu routing dialihkan instan 100% kembali ke baseline stable revision.
4. **Hasil**: MTTR terpangkas dari 47 menit menjadi 12 detik (waktu deteksi + shifting trafik otomatis). Frekuensi deployment meningkat dari 1 kali per minggu menjadi 14 kali per hari tanpa degradasi ketersediaan (Availability tetap di angka 99.995%).

---

## 9. Trade-offs

| Dimensi Arsitektural | Pendekatan A (Simpel / Dasar) | Pendekatan B (Advanced Enterprise) | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Pola Rilis** | *Rolling Update* bawaan K8s | *Canary / Blue-Green via Service Mesh* | **Latency & Kompleksitas**: Canary memerlukan konfigurasi ingress controller/service mesh yang kompleks dan duplikasi resource komputasi sementara, namun menjamin 0% blast radius saat rilis cacat. |
| **State Management** | Terraform Local State / Single S3 | Multi-Account S3 Remote State + KMS + DynamoDB | **Biaya & Kecepatan**: Multi-account menambah overhead manajemen IAM policy dan latensi eksekusi terraform plan, tetapi mengeliminasi risiko race-condition dan state corruption antar tim. |
| **Pod Resource Alloc** | Resource Request/Limit Longgar / Ketiadaan Limit | Rigid CPU/Memory Requests & Limits (Guaranteed QoS) | **Pemanfaatan vs Stabilitas**: Limit ketat mencegah *Noisy Neighbor* dan *Out-Of-Memory (OOM) Kills* pada node, namun jika estimasi salah, CPU throttling dapat menaikkan latency P99 aplikasi secara dramatis. |
| **Observabilitas** | Stdout logging agregat via cloud | Distributed Tracing (OTel) + Metrics High-Cardinality | **Cost vs Troubleshooting**: Biaya penyimpanan tracing & indexing metrik sangat tinggi (cost storage), namun mempercepat Root Cause Analysis (RCA) dari hitungan jam ke hitungan menit. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Pod Terjebak dalam Status `CrashLoopBackOff` Pasca-Deployment
- **Penyebab**: Aplikasi gagal melewati health check (`livenessProbe` gagal) sebelum inisialisasi tuntas, atau kegagalan membaca konfigurasi terenkripsi (*Secret* missing).
- **Investigasi Sistematis**:
  ```bash
  kubectl describe pod <pod-name> -n <namespace>
  # Cek bagian 'Last State', 'Exit Code', dan 'Events'
  kubectl logs <pod-name> -n <namespace> --previous
  # Melihat log kontainer sebelum mengalami crash crash terakhir
  ```

### 2. State Lock Terkunci Permanen pada Terraform (`Error acquiring the state lock`)
- **Penyebab**: Proses CI/CD terputus tiba-tiba (misal runner di-kill out-of-memory) sebelum sempat melepaskan lock DynamoDB.
- **Solusi Korektif**:
  ```bash
  # Verifikasi lock ID dari log error
  terraform force-unlock <LOCK-ID>
  # PERINGATAN: Hanya lakukan jika dipastikan TIDAK ADA pipeline lain yang berjalan paralel!
  ```

### 3. CPU Throttling Akibat Definisi Resource Limit yang Tidak Presisi
- **Gejala**: Response time aplikasi melambat drastis padahal pemanfaatan CPU node belum mencapai 100%.
- **Deteksi**: Periksa metrik `container_cpu_cfs_throttled_periods_total` pada Prometheus.
- **Solusi**: Tingkatkan CPU limit atau hilangkan limit CPU (hanya pasang request) jika kernel CFS quota scheduler membatasi thread pemrosesan runtime (misalnya runtime JVM atau Go multi-threading).

---

## 11. Best Practices (Production Checklist)

### Security & Governance
- [ ] Container image dibangun dari base image minimal (Distroless atau Alpine) dan telah dipindai kerentanannya (zero Critical and High CVEs).
- [ ] Pod tidak berjalan sebagai user root (`runAsNonRoot: true`, non-zero UID/GID).
- [ ] Read-only root filesystem diterapkan pada container, write operations hanya diarahkan ke ephemeral `emptyDir` mount.
- [ ] Rahasia aplikasi (*secrets*) tidak disimpan plain-text di Git; integrasikan dengan External Secrets Operator yang terhubung ke AWS Secrets Manager atau HashiCorp Vault.

### Reliability & Resiliency
- [ ] Semua Pod deployment mendefinisikan CPU & Memory *Requests* dan *Limits*.
- [ ] Menetapkan `PodDisruptionBudget` untuk mencegah penghentian seluruh replika saat node upgrade/draining.
- [ ] Mengonfigurasi `lifecycle.preStop` hook dengan jeda waktu tidur (`sleep`) untuk memberi waktu Service Ingress menghapus endpoint sebelum kontainer menerima `SIGTERM`.
- [ ] Readiness probe tidak boleh mengakses dependensi transien (database/downstream API); hanya verifikasi kesiapan internal pod.

### Scalability & Infrastructure
- [ ] Terraform state terisolasi per environment (`dev`, `staging`, `production`) dan per domain fungsi (network, cluster, storage).
- [ ] Horizontal Pod Autoscaler (HPA) aktif dengan skala metrik seimbang (bukan hanya CPU, kombinasikan dengan throughput metrik kustom).

---

## 12. Hands-on Practice

Simpan seluruh file praktikum ini ke dalam direktori lokal: `hands-on/m02/`.

### Struktur File Praktikum
```
hands-on/m02/
├── app/
│   ├── main.go
│   └── Dockerfile
├── terraform/
│   ├── main.tf
│   └── variables.tf
└── k8s/
    ├── base-deployment.yaml
    └── network-policy.yaml
```

### Langkah 1: Siapkan Server Aplikasi (Go HTTP Graceful Server)
Buat file `hands-on/m02/app/main.go`:
```go
package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz/live", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("ALIVE"))
	})
	mux.HandleFunc("/healthz/ready", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("READY"))
	})
	mux.HandleFunc("/api/v1/resource", func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(50 * time.Millisecond) // Simulasi I/O
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"success","data":"enterprise-payload"}`))
	})

	srv := &http.Server{
		Addr:         ":8080",
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)

	go func() {
		log.Println("Server running on port 8080...")
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Fatal: %v\n", err)
		}
	}()

	<-stop
	log.Println("SIGTERM received, draining connections...")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}
	log.Println("Server exiting properly.")
}
```

### Langkah 2: Bangun Image Multi-Stage Distroless
Buat file `hands-on/m02/app/Dockerfile`:
```dockerfile
# Stage 1: Build binary
FROM golang:1.22-alpine AS builder
WORKDIR /workspace
COPY main.go .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-w -s" -o server main.go

# Stage 2: Minimal non-root runtime image
FROM gcr.io/distroless/static:nonroot
WORKDIR /
COPY --from=builder /workspace/server /server
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/server"]
```

### Langkah 3: Deploy Isolasi Keamanan Jaringan
Buat file `hands-on/m02/k8s/network-policy.yaml`:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: isolate-app-traffic
  namespace: default
spec:
  podSelector:
    matchLabels:
      app: resilient-api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - namespaceSelector: {}
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
```

### Langkah 4: Eksekusi Praktikum
Jalankan perintah berikut di terminal:
```bash
cd hands-on/m02/app
docker build -t local/resilient-api:v1 .

# Jalankan pada kluster Kubernetes lokal
kubectl apply -f ../k8s/network-policy.yaml
kubectl create deployment resilient-api --image=local/resilient-api:v1 --port=8080
kubectl set resources deployment resilient-api --requests=cpu=100m,memory=128Mi --limits=cpu=500m,memory=256Mi

# Verifikasi status pods dan isolasi jaringan
kubectl get pods -l app=resilient-api
```

---

## 13. Exercise

### Level Easy
1. Dari file `hands-on/m02/app/Dockerfile`, periksa ukuran binary yang dihasilkan menggunakan perintah `docker images`. Analisis mengapa stage distroless menghasilkan attack surface yang jauh lebih kecil dibandingkan image berbasis `ubuntu` atau `golang:latest`.
2. Ubah `terminationGracePeriodSeconds` pada manifest deployment menjadi 10 detik, lalu lakukan rolling update. Amati output pod logs saat proses SIGTERM berlangsung.

### Level Medium
1. Tulis sebuah file deklaratif Terraform (`hands-on/m02/terraform/s3_storage.tf`) untuk membuat S3 bucket yang mewajibkan penolakan unencrypted payload (`aws:SecureTransport`), mengaktifkan bucket versioning, dan mematikan seluruh public access block secara eksplisit.
2. Konfigurasi `app-production.yaml` pada bab 7 untuk menggunakan `affinity` (khususnya `podAntiAffinity`) sehingga pod tidak akan dijadwalkan pada compute node fisik yang sama (High Availability zone distribution).

### Level Hard
1. Buat skrip automasi bash yang melakukan testing beban (*load test*) lokal via `curl` atau `hey`, serentak memicu rolling restart deployment. Pastikan tidak ada kegagalan koneksi sama sekali (HTTP error 0, status 200 = 100%) dengan menyetel konfigurasi kombinasi `preStop` sleep hook, readiness probe yang akurat, dan ingress routing. Dokumentasikan rasio error rate jika terjadi kegagalan.

---

## 14. Challenge

### Studi Kasus: "The Zero-Downtime Database Migration Dilemma"
**Deskripsi Skenario**:
Anda ditugaskan merilis microservice versi baru (v2.0) yang memodifikasi skema database transaksional (contoh: kolom `full_name` dipecah menjadi `first_name` dan `last_name`). Database memiliki volume data 10 TB dengan write rate 3.000 TPS. Tim tidak diberikan izin untuk mengambil window maintenance (zero downtime).

**Instruksi Penugasan**:
1. Rancang arsitektur pipeline deployment dan strategi migrasi database menggunakan pola **Expand/Contract (Parallel Run Pattern)**.
2. Buat sequence diagram berbasis teks/ASCII yang memetakan tahapan integrasi:
   - Kapan skema DB baru ditambahkan.
   - Kapan dual-write diberlakukan.
   - Bagaimana microservice v1.0 dan v2.0 beroperasi berdampingan dalam kluster.
   - Kapan data lama di-backfill.
   - Kapan skema database lama di-*deprecate* dan dihapus sepenuhnya.
3. Definisikan fail-safe plan: Bagaimana jika terjadi kegagalan data integrity pada 50% proses backfill ketika aplikasi v2.0 sudah mulai melayani 20% traffic Canary?

*(Tantangan ini menuntut integrasi antara arsitektur software, IaC, dan progressive deployment pipeline).*

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic Knowledge
1. Mengapa direktori `.terraform/` dan file `.tfstate` tidak boleh dimasukkan (*committed*) ke dalam version control system publik/Git?
2. Apa perbedaan fungsional utama antara `livenessProbe` dan `readinessProbe` pada Kubernetes?
3. Sebutkan tujuan utama penetapan `maxUnavailable: 0` pada konfigurasi rolling update deployment Kubernetes.
4. Apa fungsi dari resource `PodDisruptionBudget` (PDB) dalam pemeliharaan node kluster?
5. Mengapa format image berbasis distroless atau scratch lebih disukai untuk image produksi dibanding alpine/debian?

### Bagian B: Intermediate Engineering
1. Bagaimana cara Terraform mengatasi potensi tabrakan eksekusi (`race condition`) saat dua engineer/pipeline menjalankan `terraform apply` secara bersamaan?
2. Pada skenario apa penambahan metrik Memory Utilization pada HPA gagal memicu scale-out yang efisien pada aplikasi berbasis Garbage Collected runtime (misal: Java VM)?
3. Jelaskan konsep Network Policy `Deny-All` (default deny) dan mengapa hal ini menjadi standar kepatuhan sistem keamanan enterprise.
4. Apa peran `terminationGracePeriodSeconds` dan kaitannya dengan eksekusi `preStop hook` ketika sebuah Pod menerima sinyal terminasi?
5. Mengapa GitOps engine seperti ArgoCD beroperasi dengan model pull-based daripada push-based dari CI server tradisional? Jelaskan dari perspektif keamanan perimeter jaringan kluster.

### Bagian C: Production Scenarios & Analysis
1. **Skenario 1**: Sebuah microservice mengalami peningkatan latency P99 drastis dari 80ms ke 2.500ms seketika setelah HPA melipatgandakan jumlah Pod dari 5 menjadi 25. Database CPU utilization langsung menyentuh 100%. Jelaskan root cause dan mekanisme pencegahan arsitektural yang harus diterapkan!
2. **Skenario 2**: Pipeline CI/CD Anda memicu Canary deployment. Pada tahapan canary weight 10%, sistem monitoring mendeteksi kenaikan HTTP 500 error rate sebesar 0.8% yang hanya mengenai pengguna platform mobile tertentu. Apa tahapan otomatisasi yang harus dilakukan oleh Ingress controller dan metrics analyzer, dan bagaimana cara tim mencegah false positive rollback?
3. **Skenario 3**: Tim developer melaporkan bahwa pod mereka sering ter-evict dengan status `OOMKilled` (Exit Code 137). Namun dashboard monitoring memperlihatkan rata-rata memori aplikasi hanya 60% dari limit yang ditetapkan. Analisis penyebab diskrepansi data metrik ini dan tentukan langkah perbaikannya!

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Kunci Bagian A (Basic)
1. Karena file `.tfstate` sering kali menyimpan nilai sensitif (plain text passwords, private keys, connection strings) dan menyimpannya di Git dapat menimbulkan race condition serta kebocoran data credential fatal.
2. `livenessProbe` digunakan untuk menentukan kapan pod harus di-*restart* karena kondisi unrecoverable / deadlock; `readinessProbe` digunakan untuk menentukan apakah pod siap menerima traffic incoming request. Pod yang gagal readiness probe tidak akan menerima lalu lintas dari Service endpoint, tetapi tidak di-restart.
3. Menjamin bahwa kapasitas kluster tidak pernah berada di bawah target jumlah replika yang didefinisikan selama proses pembaruan pod berlangsung, menjaga ketersediaan 100% throughput.
4. PDB memastikan batas minimum jumlah pod yang harus tetap beroperasi (*available*) selama proses voluntary disruptions (seperti `kubectl drain` saat node upgrade atau patching OS).
5. Karena meminimalisir attack surface: tidak menyertakan shell package manager (`apt`, `apk`), libaries yang tidak dibutuhkan, dan utilitas eksekusi arbitrary binary (`sh`, `bash`), sehingga membatasi gerak lateral penyerang saat kontainer tertembus.

#### Kunci Bagian B (Intermediate)
1. Terraform menggunakan mekanisme state locking terdistribusi (misal melalui tabel status DynamoDB pada AWS atau Consul session lock). Ketika sebuah proses `apply` berjalan, ID lock unik didaftarkan; eksekusi paralel lain yang membaca lock tersebut akan ditolak (throw exit error) sampai proses pertama tuntas dan lock dirilis.
2. Karena Garbage Collector pada JVM sering kali tidak langsung mengembalikan memori yang tidak terpakai ke OS (*heap memory allocation footprint* tetap tertahan di ambang batas atas). Akibatnya, penggunaan memori tampak selalu tinggi di level container cgroups, memicu HPA untuk terus melakukan scale-out hingga batas `maxReplicas` meskipun volume transaksi sebenarnya rendah.
3. Default Deny memblokir seluruh lalu lintas ingress dan egress antar pod secara default, mengimplementasikan postur Zero Trust. Komunikasi hanya diizinkan jika didefinisikan secara eksplisit via Network Policy whitelist, mencegah *lateral movement* penyerang jika salah satu pod berhasil dikompromikan.
4. Kubelet akan mengirimkan sinyal `SIGTERM`, menjalankan script pada `preStop hook`, lalu menunggu selama durasi `terminationGracePeriodSeconds`. Jika kontainer belum keluar (*exit*) secara mandiri setelah durasi tersebut habis, sinyal `SIGKILL` (force termination) akan dikirimkan. `preStop hook` krusial untuk menyelesaikan request in-flight dan memberi jeda propagasi penghapusan IP pod dari IPTables/IPVS service proxy.
5. Model pull-based (ArgoCD/Flux) tidak mengharuskan kluster produksi membuka port inbound API atau mengekspos credential cluster admin ke runner CI eksternal. Agen penarik berada di dalam boundary keamanan private subnet kluster dan hanya membutuhkan akses keluar (outbound) ke Git repository.

#### Kunci Bagian C (Production Scenarios)
1. **Root Cause**: Fenomena *Connection Exhaustion* / *Thundering Herd* pada Database. Saat pod bertambah 5x lipat, batas koneksi maksimum (*max_connections*) pool database terlampaui seketika, menyebabkan database overload dan latensi seluruh query melonjak tinggi.  
   **Solusi**: Terapkan Database Connection Pooler perantara (misal: PgBouncer untuk PostgreSQL), pasang rate limiting pada Ingress, dan atur HPA behavior scaling policy agar proses scale-up berjalan landai (`stabilizationWindowSeconds` dan batasan limit step-up pods).
2. **Analisis Solusi**: Traffic controller harus secara otomatis memutus routing weight canary menjadi 0% dan mengembalikan alokasi 100% ke stable target. Untuk mencegah false positive: Analisis canary metrik harus menggunakan interval moving average (misalnya window 3-5 menit) dan menetapkan ambang minimum sample size (misal: evaluasi baru valid jika pod canary sudah menerima minimal 1.000 requests), serta memeriksa korelasi silang dengan traffic mobile app version tags via header inspection.
3. **Analisis Solusi**: Monitoring dashboard biasanya menyajikan metrik rata-rata teragregasi (misal scrape interval per 30 atau 60 detik via Prometheus). Jika aplikasi mengalami lonjakan alokasi memori tajam (*spike*) yang berlangsung cepat (dalam hitungan milidetik, misal memproses upload file besar ke heap), kernel Linux cgroup OOM-killer akan langsung membunuh proses kontainer sebelum Prometheus sempat mencatat puncak lonjakan tersebut.  
   **Perbaikan**: Konfigurasi memory profiling (pprof/heap dump analysis), evaluasi batas ukuran request payload di level Ingress gateway, dan naikkan memory limit kontainer atau gunakan buffer berbasis persistent/ephemeral storage offloading.

---

## 16. Summary

Pada tingkatan enterprise, DevOps berevolusi dari sekadar penulisan skrip otomasi sederhana menjadi disiplin rekayasa stabilitas, keandalan (*reliability engineering*), dan keamanan sistem. Tiga pilar utama arsitektur tingkat lanjut ini mencakup:

1. **Deklarasi Status Absolut (Declarative State Control)**: Mengeliminasi intervensi manual dengan memusatkan seluruh konfigurasi infrastruktur dan kluster pada Git (*Single Source of Truth*), didukung mekanisme distributed lock engine yang solid.
2. **Sistem Rilis Progresif Beresiliensi Tinggi**: Zero-downtime deployment bukan lagi pilihan, melainkan keharusan. Implementasi *Canary Analysis* berbasis telemetri otomatis menjamin bahwa cacat kode produksi dimitigasi secara sistemik dalam hitungan detik tanpa memengaruhi sebagian besar pengguna akhir.
3. **Defense in Depth pada Runtime**: Keamanan dan stabilitas kontainer dicapai melalui pembatasan kapabilitas OS kernel, penegakan kontrol isolasi jaringan via Network Policy, penanganan lifecycle sinyal terminasi yang mulus, serta perumusan metrik berbasis SLI/SLO terukur. Pengetahuan ini adalah batas pemisah tegas antara infrastruktur hobi dan sistem berskala misi kritis (*mission-critical systems*).