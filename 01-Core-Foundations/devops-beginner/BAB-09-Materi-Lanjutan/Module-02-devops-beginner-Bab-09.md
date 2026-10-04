# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Mengimplementasikan Strategi Deployment Zero-Downtime**: Membedakan dan mengeksekusi pola rilis *Blue-Green*, *Canary*, dan *Rolling Update* menggunakan service mesh dan ingress controller tingkat produksi.
2. **Merancang Topologi Infrastructure as Code (IaC) Modular & Aman**: Membangun modul Terraform yang *reusable*, mengisolasi *state file* berbasis environment, dan mengintegrasikan enkripsi data serta *state locking* terdistribusi.
3. **Mengoperasikan Rekonsiliasi Berbasis GitOps**: Mengonfigurasi arsitektur GitOps dengan *pull-based deployment engine* (ArgoCD), memahami mekanisme *drift detection*, dan siklus rekonsiliasi state cluster.
4. **Mengintegrasikan Observabilitas Terpadu (Telemetry Triad)**: Menyusun instrumen metrik, log terstruktur, dan *distributed tracing* menggunakan OpenTelemetry dan Prometheus Operator.
5. **Menerapkan Hardening Keamanan Berkelanjutan (DevSecOps)**: Mengotomatisasi pemindaian kerentanan *container image*, *static application security testing* (SAST), dan manajemen kredensial dinamis (*ephemeral secrets*) menggunakan HashiCorp Vault.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai kompetensi dasar berikut:
* **Linux System Administration**: Pemahaman mendalam terkait Linux Kernel namespaces, cgroups, `systemd`, TCP/IP networking, socket routing, dan POSIX signal handling (`SIGTERM`, `SIGKILL`).
* **Container Fundamentals**: Mahir menulis *multi-stage build* Dockerfile, memahami OCI runtime specs, overlay filesystem, dan manipulasi *non-root container execution*.
* **Kubernetes Core Concepts**: Memahami siklus hidup `Pod`, `Deployment`, `Service`, `Ingress`, `ConfigMap`, dan `Secret`.
* **CI/CD Foundations**: Menguasai pipeline deklaratif dasar (GitHub Actions/GitLab CI) yang mencakup tahap build, unit test, dan push artifact ke registry.
* **Dasar Jaringan Komputer**: Memahami layer 4 vs layer 7 proxying, DNS resolution, TLS termination, dan HTTP/2 / gRPC semantics.

---

## 3. Concept & Internal Architecture

### 3.1 Siklus Hidup Container & Pod Termination Grace Period
Dalam arsitektur produksi, zero-downtime bukan sekadar konsep routing; melainkan orkestrasi terminasi proses pada tingkat sistem operasi dan penundaan pencabutan endpoint dari service mesh.

```
+-----------------------------------------------------------------------------------+
| 1. API Server menerima 'Delete Pod'                                                |
+-----------------------------------------+-----------------------------------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                                                   |
        v                                                                   v
+------------------------------------+             +------------------------------------+
| Pod Status -> Terminating          |             | Endpoint controller mencabut IP    |
| (Kubelet menghentikan liveness)    |             | dari Endpoints / EndpointSlice     |
+-----------------+------------------+             +-----------------+------------------+
                  |                                                  |
                  v                                                  v
+------------------------------------+             +------------------------------------+
| Eksekusi 'preStop' Hook            |             | iptables/IPVS/CoreDNS diperbarui   |
| (sleep 10-15s untuk propagasi DNS) |             | (Perlu waktu propagasi lintas node)|
+-----------------+------------------+             +-----------------+------------------+
                  |                                                  |
                  +-----------------------+--------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| Mengirimkan SIGTERM ke PID 1 di container                                         |
| Container berhenti menerima koneksi baru, menyelesaikan in-flight requests       |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| Batas waktu 'terminationGracePeriodSeconds' berakhir?                             |
| Jika Ya: Kubelet mengirimkan SIGKILL (Force Kill)                                 |
+-----------------------------------------------------------------------------------+
```

1. **Endpoint Deregistration**: Ketika pod masuk status `Terminating`, Endpoint Controller menghapus IP Pod dari `EndpointSlice`. Namun, pembaruan aturan `iptables`/`IPVS` pada seluruh kube-proxy di cluster membutuhkan waktu beberapa detik (propagasi terdistribusi).
2. **PreStop Hook**: Diperlukan untuk menahan pengiriman `SIGTERM` secara instan. Memberikan jeda waktu (misal: 15 detik) agar seluruh Ingress Controller dan Load Balancer menerima update routing dan berhenti mengarahkan traffic baru ke Pod tersebut.
3. **Application Graceful Shutdown Handling**: Aplikasi menangkap sinyal `SIGTERM`, berhenti menerima koneksi TCP baru pada listener socket, namun tetap memproses request yang sedang berjalan (*in-flight*) hingga selesai atau hingga timeout internal tercapai.

---

### 3.2 GitOps Pull-Based Reconciliation Engine
Pendekatan push-based konvensional menuntut CI server memiliki akses langsung (*elevated privileges*) ke dalam cluster produksi, yang membuka celah keamanan signifikan. GitOps membalik paradigma ini menjadi *pull-based*.

```
+---------------+        +----------------------+
| Git Repository| <----+ | ArgoCD Repo Server   | (Manifest Parsing & Templating:
| (Source of    |        +----------+-----------+  Helm / Kustomize)
|  Truth)       |                   |
+---------------+                   v
                        +-----------------------+
                        | ArgoCD Application    |
                        | Controller            |
                        +-----------+-----------+
                                    |
                 Reconciliation Loop| (Compare Desired vs Live State)
                                    v
                        +-----------------------+
                        | Kubernetes API Server |
                        | (Live State Cluster)  |
                        +-----------------------+
```

* **Desired State vs. Live State**: GitOps controller secara periodik (polling atau webhook) membaca spesifikasi deklaratif dari Git (*Desired State*) dan membandingkannya dengan kondisi riil di cluster (*Live State*).
* **Self-Healing & Out-of-Sync Detection**: Jika ada engineer mengubah resource Kubernetes secara manual via `kubectl`, GitOps controller mendeteksi *drift* ini dan secara otomatis menimpa kembali kondisi cluster agar identik dengan apa yang tertulis di Git (*Auto-Remediation*).

---

## 4. Why & What

| Dimensi | Paradigma Konvensional (Beginner / Ad-hoc) | Paradigma Rekayasa Produksi (Enterprise DevOps) |
| :--- | :--- | :--- |
| **Deployment Strategy** | **Recreate / Big Bang**: Aplikasi dimatikan total lalu versi baru dinyalakan. Terjadi *downtime* terencana. | **Canary / Progressive Traffic Splitting**: Rilis bertahap (1%, 5%, 25%, 100%) berdasarkan analisis error rate dan latency otomatis. |
| **Konfigurasi Server** | **Snowflake Servers**: Konfigurasi manual melalui SSH, instalasi dependensi langsung di OS. | **Immutable Infrastructure**: Server dan container di-provisioning ulang secara penuh tanpa modifikasi langsung saat runtime. |
| **Security Handling** | **Static Secrets**: Database password dan API token disimpan di file `.env` atau Kubernetes Secret plain base64. | **Dynamic & Ephemeral Secrets**: Kredensial di-generate on-the-fly dengan Time-to-Live (TTL) pendek menggunakan Vault. |
| **Delivery Model** | **Push-Based CI/CD**: Runner CI memegang sertifikat admin kubeconfig untuk eksekusi deployment. | **Pull-Based GitOps**: Operator internal cluster menarik konfigurasi; batas jaringan tertutup rapat dari luar. |
| **Observability** | **Siloed Logging**: Log SSH manual menggunakan `tail -f /var/log/app.log`, metrik terpisah tanpa relasi. | **Unified Telemetry**: Korelasi trace ID lintas microservices dengan metrik latensi dan log terstruktur. |

---

## 5. How (Workflow Detail)

### 5.1 Canary Deployment Menggunakan Ingress Traffic Splitting

Workflow eksekusi deployment canary berbasis layer 7 proxy:

```
[ Ingress Controller (e.g., NGINX / Envoy) ]
             |
             +--- (90% Traffic) ---> [ Service: app-production ] ---> Pods v1.0.0
             |
             +--- (10% Traffic) ---> [ Service: app-canary ]     ---> Pods v1.1.0
```

1. **Deploy Versi Baru (Canary)**: Deploy deployment baru (`app-canary`) dengan replica minimum dan service yang terisolasi.
2. **Split Traffic**: Konfigurasikan ingress controller untuk mengalihkan persentase kecil traffic (misal: 10%) ke `app-canary` menggunakan header atau weight-based splitting.
3. **Analyze Metric**: Pantau metrik spesifik selama interval observasi:
   * HTTP 5xx error rate canary $\le$ baseline.
   * Latency p95/p99 canary $\le$ baseline.
4. **Promotion atau Rollback**:
   * Jika parameter lolos uji: Tingkatkan bobot traffic ke 50%, lalu 100%. Update deployment utama ke versi baru, kemudian matikan deployment canary.
   * Jika terjadi anomali: Kembalikan bobot ingress ke 0% secara instan. Tidak ada downtime pada pengguna umum.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Pemeliharaan Kereta Cepat
Bayangkan sebuah jalur kereta api ekspres (traffic produksi) yang tidak boleh berhenti beroperasi sama sekali:
* **Pola Recreate**: Anda menghentikan seluruh kereta, membongkar stasiun, membangunnya kembali, lalu menyuruh penumpang masuk. Seluruh operasional lumpuh total selama perombakan.
* **Pola Blue-Green**: Anda membangun stasiun paralel yang identik (Green) di sebelah stasiun lama (Blue). Saat stasiun baru selesai 100% dan teruji sempurna, Anda memindahkan wesel rel kereta (DNS/Load Balancer) ke stasiun baru. Jika stasiun baru bermasalah, wesel dipindahkan kembali seketika.
* **Pola Canary**: Anda membuka satu gerbang kecil di stasiun baru untuk 5% penumpang. Jika mereka sampai ke tujuan dengan selamat dan puas (observabilitas lolos), Anda secara perlahan mengarahkan 95% sisa penumpang lainnya ke stasiun baru.

```
        TRAFFIC MASUK
              │
              ▼
      ┌───────────────┐
      │ Load Balancer │
      └───────┬───────┘
              │
      ┌───────┴────────────────────────┐
      │ Wesel Routing (Canary Split)   │
      └───────┬────────────────┬───────┘
              │ (90%)          │ (10%)
              ▼                ▼
     ┌────────────────┐ ┌────────────────┐
     │ Stasiun Blue   │ │ Stasiun Canary │
     │ (Versi Stabil) │ │ (Versi Baru)   │
     └────────────────┘ └────────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Graceful Shutdown Implementation (Go)

Aplikasi harus menangani sinyal sistem operasi agar koneksi klien tidak terputus secara sepihak saat container dimatikan oleh orkestrator.

```go
package main

import (
	"context"
	"errors"
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
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("OK"))
	})
	mux.HandleFunc("/api/work", func(w http.ResponseWriter, r *http.Request) {
		// Simulasi proses komputasi 2 detik
		time.Sleep(2 * time.Second)
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"completed"}`))
	})

	server := &http.Server{
		Addr:         ":8080",
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  15 * time.Second,
	}

	// Channel untuk menangkap sinyal terminasi OS
	shutdownChan := make(chan os.Signal, 1)
	signal.Notify(shutdownChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		log.Printf("Server listening on %s\n", server.Addr)
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("Fatal error starting server: %v\n", err)
		}
	}()

	// Menunggu sinyal SIGTERM dari orkestrator
	sig := <-shutdownChan
	log.Printf("Sinyal terminasi diterima: %v. Memulai proses graceful shutdown...", sig)

	// Berikan batas waktu maksimum bagi in-flight request untuk selesai
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		log.Printf("Graceful shutdown gagal, memaksa proses berhenti: %v\n", err)
		os.Exit(1)
	}

	log.Println("Seluruh in-flight request telah selesai diproses. Server keluar secara bersih.")
}
```

---

### 7.2 Practical Example: Production-Grade Kubernetes Manifest dengan PreStop & Canary Traffic Splitting

#### 1. Baseline Deployment (`production-app.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service-stable
  namespace: production
  labels:
    app: order-service
    variant: stable
spec:
  replicas: 3
  selector:
    matchLabels:
      app: order-service
      variant: stable
  template:
    metadata:
      labels:
        app: order-service
        variant: stable
    spec:
      terminationGracePeriodSeconds: 45
      containers:
      - name: order-service
        image: registry.enterprise.internal/core/order-service:1.0.0
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8080
          name: http
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 15"]
        resources:
          requests:
            cpu: "250m"
            memory: "256Mi"
          limits:
            cpu: "1000m"
            memory: "512Mi"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: order-service-stable
  namespace: production
spec:
  type: ClusterIP
  selector:
    app: order-service
    variant: stable
  ports:
  - name: http
    port: 80
    targetPort: 8080
```

#### 2. Canary Deployment (`canary-app.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service-canary
  namespace: production
  labels:
    app: order-service
    variant: canary
spec:
  replicas: 1
  selector:
    matchLabels:
      app: order-service
      variant: canary
  template:
    metadata:
      labels:
        app: order-service
        variant: canary
    spec:
      terminationGracePeriodSeconds: 45
      containers:
      - name: order-service
        image: registry.enterprise.internal/core/order-service:1.1.0
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8080
          name: http
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 15"]
        resources:
          requests:
            cpu: "250m"
            memory: "256Mi"
          limits:
            cpu: "1000m"
            memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: order-service-canary
  namespace: production
spec:
  type: ClusterIP
  selector:
    app: order-service
    variant: canary
  ports:
  - name: http
    port: 80
    targetPort: 8080
```

#### 3. Ingress Route dengan Traffic Weighting (NGINX Ingress Controller)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: order-service-primary-ingress
  namespace: production
  annotations:
    kubernetes.io/ingress.class: nginx
spec:
  rules:
  - host: orders.enterprise.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: order-service-stable
            port:
              number: 80
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: order-service-canary-ingress
  namespace: production
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "10"
spec:
  rules:
  - host: orders.enterprise.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: order-service-canary
            port:
              number: 80
```

---

## 8. Real World Case Study (Enterprise Scale)

### Bank Neo-Fintech: Penanganan Kegagalan Rilis Core Banking Gateway

* **Konteks**: Layanan transaksi pembayaran memproses rata-rata 3.500 transaksi per detik (TPS). Rilis versi baru dilakukan setiap Kamis malam menggunakan mekanisme konvensional rolling update bawaan Kubernetes.
* **Insiden (Severity-1)**:
  * Pada rilis v2.4.0, aplikasi mengandung regresi algoritma enkripsi payload yang menyebabkan timeout ke sistem kliring Bank Sentral.
  * Rolling update Kubernetes mengganti pod secara linear. Karena health check `/healthz` hanya mengecek koneksi HTTP sederhana dan database ping (keduanya lolos), Kubernetes menganggap aplikasi sehat.
  * Dalam kurun waktu 4 menit, seluruh pod v2.3.0 musnah digantikan v2.4.0. Transaksi nasabah drop hingga 87%, memicu alarm critical di payment settlement.
  * Upaya perbaikan terhambat: Rollback manual melalui CI pipeline memakan waktu 11 menit (waktu antrean pipeline, image pull, initialization).
* **Akar Masalah Arsitektur**:
  1. Health check tidak mencakup fungsionalitas end-to-end (hanya basic ping).
  2. Ketiadaan *automated canary analysis* yang mengevaluasi metrik bisnis (success rate) sebelum mempromosikan replika baru.
  3. CI/CD terikat erat pada proses build manual untuk rollback alih-alih declarative state revert di GitOps.
* **Solusi Rekayasa Berkelanjutan**:
  1. Mengadopsi **Argo Rollouts** dengan analisis metrik Prometheus terintegrasi secara otomatis (*Automated Canary Analysis*).
  2. Implementasi **MetricTemplate** yang mengevaluasi error rate HTTP 5xx dan response time p99:
     ```yaml
     apiVersion: argoproj.io/v1alpha1
     kind: Rollout
     metadata:
       name: payment-gateway
       namespace: core-banking
     spec:
       strategy:
         canary:
           steps:
           - setWeight: 5
           - pause: { duration: 10m }
           - analysis:
               templates:
               - templateName: success-rate-check
           - setWeight: 20
           - pause: { duration: 15m }
     ```
  3. Konfigurasi `failureLimit: 1` pada analysis check. Jika success rate transaksi payment turun di bawah 99.95% selama fase canary 5%, sistem routing memotong traffic canary kembali ke versi stabil secara seketika (< 3 detik) tanpa intervensi manusia.
* **Hasil**: Durasi dampak insiden pada deployment berikutnya terpangkas dari rata-rata 15 menit menjadi di bawah 10 detik, menyelamatkan perkiraan potensi kerugian transaksi finansial miliaran rupiah.

---

## 9. Trade-offs

| Pendekatan / Pola | Parameter Kinerja | Latensi & Dampak | Biaya Infrastruktur (Cost) | Kompleksitas Operasional |
| :--- | :--- | :--- | :--- | :--- |
| **Rolling Update** | Resource footprint tetap flat (hanya butuh buffer surge +25%). | Potensi request drop jika `preStop` tidak dipasang. Masalah kompatibilitas API backward/forward jika versi lama dan baru aktif bersamaan. | Sangat Rendah (Optimal). | Rendah. Native Kubernetes mechanism. |
| **Blue-Green** | Alih traffic instan via DNS/Load Balancer switch. Rollback zero-downtime seketika. | Membutuhkan waktu sinkronisasi state/session caching. | Sangat Tinggi (Membutuhkan kapasitas infrastruktur 200% selama proses rilis). | Menengah. Memerlukan manajemen environment ganda dan database schema lock consideration. |
| **Canary (Traffic Splitting)** | Risiko eksposur bug dibatasi ke populasi user yang sangat kecil. | Terdapat tambahan overhead perutean proxy layer 7 (evaluasi header/cookie/weight). | Menengah (Memerlukan buffer replica tambahan sesuai persentase split). | Tinggi. Memerlukan service mesh atau ingress advanced, integrasi observabilitas real-time, dan automation engine. |
| **GitOps Pull Model** | Keamanan cluster tertutup rapat (tidak ada port inbound/SSH). Drift detection permanen. | Latensi sinkronisasi (ada jeda polling Git 1-3 menit kecuali di-trigger via webhook). | Rendah (Hanya resource pods engine GitOps). | Menengah ke Tinggi. Memerlukan disiplin Git strict, review branching strategy, dan secret management terpisah. |

---

## 10. Common Mistakes & Troubleshooting

### Skenario 1: HTTP 502 Bad Gateway Muncul Saat Rolling Deployment
* **Gejala**: Ketika Pod versi baru di-deploy dan Pod versi lama dihentikan, pengguna mengalami lonjakan response `502 Bad Gateway` selama beberapa detik.
* **Akar Masalah**: Kubelet mengirim `SIGTERM` secara instan bersamaan dengan dikirimkannya sinyal update ke Endpoint controller. Ingress controller masih menyimpan IP Pod lama di memori internalnya dan terus mengirim request sementara proses aplikasi sudah mati.
* **Solusi & Troubleshooting**:
  1. Periksa event Pod: `kubectl describe pod <pod-name>`.
  2. Tambahkan `lifecycle.preStop` hook dengan perintah sleep:
     ```yaml
     lifecycle:
       preStop:
         exec:
           command: ["/bin/sh", "-c", "sleep 15"]
     ```
  3. Pastikan `terminationGracePeriodSeconds` diatur lebih tinggi dari durasi `preStop` + waktu internal graceful shutdown aplikasi (misal: 15s + 20s = minimum 35-45s).

---

### Skenario 2: State Lock Terkunci Permanen pada Terraform (Crash CI/CD)
* **Gejala**: Pipeline deployment gagal dengan error: `Error acquiring the state lock: ConditionalCheckFailedException`.
* **Akar Masalah**: Runner CI/CD dihentikan paksa (killed/timeout) di tengah operasi `terraform apply`, meninggalkan ID lock pada backend penyimpanan terdistribusi (seperti DynamoDB atau Consul).
* **Solusi**:
  1. Identifikasi Lock ID dari output error log:
     ```
     Lock Info:
       ID:        3d7e8b61-9c6a-4d44-938a-028a3f81e3a4
       Path:      terraform-production/terraform.tfstate
       Who:       runner@ci-agent-04
     ```
  2. Validasi dengan tim bahwa tidak ada eksekusi Terraform yang sedang aktif berjalan.
  3. Buka lock secara aman menggunakan instruksi CLI:
     ```bash
     terraform force-unlock 3d7e8b61-9c6a-4d44-938a-028a3f81e3a4
     ```

---

### Skenario 3: GitOps Out-of-Sync Loop Akibat Mutating Webhook
* **Gejala**: ArgoCD menunjukkan status aplikasi berkedip bergantian antara `Synced` dan `OutOfSync` secara kontinu.
* **Akar Masalah**: Git repository mendefinisikan manifest pod tanpa resource field tertentu, tetapi sebuah Admission Mutating Webhook di cluster (misalnya Istio sidecar injector atau security policy) secara otomatis menginjeksi anotasi atau field baru ke dalam live object. ArgoCD mendeteksi hal ini sebagai perubahan konfigurasi (*drift*) dan mencoba menimpanya kembali.
* **Solusi**:
  Konfigurasikan blok `ignoreDifferences` pada resource `Application` ArgoCD:
  ```yaml
  spec:
    ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
      - /spec/template/metadata/annotations/sidecar.istio.io~1status
  ```

---

## 11. Best Practices (Production Checklist)

### Arsitektur Pipeline & Deployment
- [ ] Terapkan prinsip **Single Artifact**: Build container image satu kali di pipeline CI, uji di staging, lalu promosikan image tag yang identik ke production. Hindari re-build antar environment.
- [ ] Jangan pernah menggunakan tag mutable seperti `:latest` di production. Gunakan Immutable Commit SHA atau Semantic Versioning (`:v1.2.3-a8f3c91`).
- [ ] Pisahkan repositori kode aplikasi (*Source Code Repo*) dengan repositori deklarasi infrastruktur/manifest (*Config/GitOps Repo*).

### Pod Resilience & Container Security
- [ ] Set resource `requests` dan `limits` secara eksplisit untuk mencegah OOM (Out Of Memory) cascading failure.
- [ ] Terapkan `readinessProbe` dan `livenessProbe` dengan endpoint fungsional yang akurat.
- [ ] Hindari eksekusi container sebagai user `root`. Gunakan security context non-root:
  ```yaml
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    allowPrivilegeEscalation: false
    readOnlyRootFilesystem: true
  ```
- [ ] Atur `preStop` hook dengan interval delay minimal 10-15 detik untuk stabilisasi sinkronisasi Load Balancer.

### IaC & Secret Governance
- [ ] State file Terraform wajib disimpan di remote backend dengan enkripsi sisi server (*server-side encryption at rest*) dan *state locking* terdistribusi.
- [ ] Tidak ada plain credentials di Git. Gunakan Secret Manager (HashiCorp Vault, AWS Secrets Manager) yang diintegrasikan via External Secrets Operator (ESO) atau SealedSecrets.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum ini ke dalam direktori: `hands-on/m02/`.

### Langkah 1: Inisialisasi Workspace
```bash
mkdir -p hands-on/m02/terraform hands-on/m02/k8s
cd hands-on/m02
```

### Langkah 2: Mengonfigurasi Modul Terraform untuk Production State Locking

Buat file `hands-on/m02/terraform/main.tf`:
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4.0"
    }
  }
}

variable "environment" {
  type        = string
  description = "Target deployment environment"
  default     = "production"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment harus staging atau production."
  }
}

locals {
  app_name = "payment-gateway"
  config_metadata = {
    env        = var.environment
    managed_by = "terraform"
    created_at = timestamp()
  }
}

resource "local_file" "environment_config" {
  filename = "${path.module}/build/${var.environment}-runtime.json"
  content  = jsonencode({
    application = local.app_name
    metadata    = local.config_metadata
    features = {
      enable_high_throughput = var.environment == "production" ? true : false
      trace_sampling_ratio   = var.environment == "production" ? 0.1 : 1.0
    }
  })
}

output "generated_config_path" {
  value       = local_file.environment_config.filename
  description = "Path lokasi file konfigurasi hasil render."
}
```

Jalankan eksekusi Terraform:
```bash
cd hands-on/m02/terraform
terraform init
terraform plan -var="environment=production" -out=tfplan
terraform apply tfplan
cat build/production-runtime.json
cd ../..
```

### Langkah 3: Menjalankan Simulasi Zero-Downtime Deployment Menggunakan Minikube/Kind

Buat file spesifikasi `hands-on/m02/k8s/zero-downtime.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: resilient-web
  namespace: default
  labels:
    app: resilient-web
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: resilient-web
  template:
    metadata:
      labels:
        app: resilient-web
    spec:
      terminationGracePeriodSeconds: 30
      containers:
      - name: nginx
        image: nginx:1.24-alpine
        ports:
        - containerPort: 80
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 10"]
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            cpu: 100m
            memory: 128Mi
        readinessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 2
          periodSeconds: 3
---
apiVersion: v1
kind: Service
metadata:
  name: resilient-web-svc
  namespace: default
spec:
  type: ClusterIP
  selector:
    app: resilient-web
  ports:
  - port: 80
    targetPort: 80
```

Terapkan manifest dan amati siklus transisi pod:
```bash
kubectl apply -f hands-on/m02/k8s/zero-downtime.yaml

# Buka terminal kedua untuk memicu continuous traffic:
kubectl run traffic-generator --rm -i --tty --image=busybox -- /bin/sh -c \
  "while true; do wget -q -O- http://resilient-web-svc.default.svc.cluster.local > /dev/null && echo 'SUCCESS 200' || echo 'FAIL 50X'; sleep 0.1; done"

# Kembali ke terminal utama, lakukan update image secara seamless:
kubectl set image deployment/resilient-web nginx=nginx:1.25-alpine

# Pantau rollout secara real-time tanpa ada satu pun error 'FAIL 50X' pada terminal traffic generator:
kubectl rollout status deployment/resilient-web
```

---

## 13. Exercise

### Level Easy
Modifikasi file `zero-downtime.yaml`. Tambahkan konfigurasi `livenessProbe` berbasis HTTP request ke path `/` dengan `failureThreshold: 3` dan evaluasi perilakunya saat `initialDelaySeconds` sengaja diatur ke `0`. Catat hasil restart loop yang terjadi.

### Level Medium
Susun file pipeline CI/CD deklaratif (GitHub Actions workflow syntax) di direktori `hands-on/m02/k8s/ci-pipeline.yaml` yang melakukan langkah:
1. Linting manifest Kubernetes menggunakan `kube-linter` atau `kubeval`.
2. Static Security Scan pada manifest untuk mendeteksi container yang berjalan dengan flag `privileged: true`.
3. Validasi skema kustom kustomize build tanpa melakukan eksekusi push ke cluster.

### Level Hard
Buat arsitektur deployment Canary bertingkat menggunakan Terraform Kubernetes Provider. Tulislah modul Terraform yang menghasilkan dua Deployment berbeda (`stable` dan `canary`), satu Service untuk masing-masing, dan satu resource Kubernetes Ingress NGINX yang mendefinisikan *canary-by-header* (hanya traffic dengan header `X-Beta-Tester: true` yang diarahkan ke canary, sementara traffic publik umum tetap 100% berada di stable).

---

## 14. Challenge

### Skenario Insiden: "The Ghost Memory Leak & Thundering Herd"
Sebuah sistem backend e-commerce berskala besar mengalami crash berkala setiap kali dilakukan deployment versi baru di bawah beban tinggi (peak traffic: 12.000 RPS). 

**Kondisi Lingkungan**:
* Node pool Kubernetes autoscaling berbasis CPU utilization.
* Pod versi baru langsung menerima traffic sesaat setelah container status berubah menjadi `Running`.
* Proses inisialisasi aplikasi membutuhkan waktu 25 detik untuk memuat model machine learning dan membangun koneksi cache pool ke Redis cluster.
* Ketika pod baru menerima traffic sebelum cache terisi (*cold-cache*), ribuan koneksi langsung menghantam database PostgreSQL primer secara bersamaan (*thundering herd problem*), menyebabkan koneksi pool database habis dan load balancer mengembalikan status HTTP 503 secara masif ke pengguna.
* Setelah pod mengalami crash, Kubernetes meluncurkan pod baru lagi, mengulang siklus petaka yang sama.

**Tugas Arsitektur Anda**:
Rancang blueprint perbaikan arsitektur end-to-end tanpa mengubah kode inti aplikasi. Rencana harus mencakup:
1. Rekayasa parameter probe (`readinessProbe`, `startupProbe`, `livenessProbe`) secara presisi beserta dependensi interaksinya.
2. Mekanisme pemanasan cache (*cache warming*) terisolasi sebelum pod dinyatakan siap menerima traffic publik.
3. Strategi traffic rate ramping menggunakan Ingress controller atau Service Mesh.
4. Tuliskan manifest Kubernetes lengkap yang mengimplementasikan mitigasi komprehensif tersebut.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Pemahaman Konseptual (Basic)
1. Apa fungsi mendasar dari eksekusi perintah `sleep` di dalam `lifecycle.preStop` hook pada pod Kubernetes?
   * A. Menunda inisialisasi container agar proses CPU stabil.
   * B. Memberikan waktu bagi ingress/load balancer untuk mencabut IP pod dari tabel routing sebelum container menerima SIGTERM.
   * C. Mencegah Docker daemon kehabisan memori saat menghapus layer container.
   * D. Menunggu pod baru selesai di-download sebelum pod lama dihapus.

2. Mengapa tag `:latest` sangat dihindari dalam spesifikasi manifest container produksi?
   * A. Tag `:latest` menyebabkan ukuran image menjadi dua kali lipat lebih besar.
   * B. Kubernetes melarang deployment pod yang menggunakan tag selain angka.
   * C. Menghilangkan sifat deterministik dan idempotensi deployment; sulit mendeteksi versi kode yang sebenarnya berjalan serta merusak proses rollback.
   * D. Tag `:latest` tidak didukung oleh container runtime seperti Containerd.

3. Di mana letak perbedaan mendasar antara model GitOps (Pull-Based) dan CI/CD tradisional (Push-Based)?
   * A. GitOps hanya dapat berjalan di cloud provider AWS.
   * B. CI/CD tradisional tidak memerlukan Git repository sebagai source code management.
   * C. Model GitOps mengeksekusi operator agen di dalam cluster yang secara aktif menarik manifest dari Git, menghindari pembukaan akses port cluster ke runner CI eksternal.
   * D. Model GitOps mengeksekusi deployment langsung dari terminal lokal developer.

4. Manakah status probe Kubernetes yang bertanggung jawab menghentikan pengiriman traffic load balancer ke pod tanpa mematikan container tersebut?
   * A. Startup Probe
   * B. Liveness Probe
   * C. Readiness Probe
   * D. Memory Probe

5. Pada arsitektur Terraform produksi, apa tujuan utama mengonfigurasi distributed state locking (seperti DynamoDB pada AWS S3 backend)?
   * A. Mempercepat proses kompresi file terraform.tfstate.
   * B. Mencegah dua eksekusi deployment berjalan bersamaan yang dapat merusak atau menimpa isi state file secara korup.
   * C. Mengenkripsi isi konfigurasi agar tidak bisa dibaca tim lain.
   * D. Menghapus resource secara otomatis jika plan dibatalkan.

---

### Bagian B: Analisis & Sintesis (Intermediate)
6. Sebuah deployment memiliki konfigurasi: `replicas: 4`, `maxSurge: 50%`, `maxUnavailable: 25%`. Berapa jumlah pod maksimum yang dapat berjalan secara simultan dan berapa jumlah pod minimum yang harus selalu dalam kondisi aktif selama rolling update?
   * A. Maksimum 6 pod, minimum 3 pod.
   * B. Maksimum 5 pod, minimum 2 pod.
   * C. Maksimum 8 pod, minimum 4 pod.
   * D. Maksimum 6 pod, minimum 4 pod.

7. Jika aplikasi backend Anda memerlukan waktu inisialisasi awal selama 60 detik untuk sinkronisasi konfigurasi sebelum siap melayani request, kombinasi konfigurasi probe manakah yang paling ideal agar pod tidak mati mendadak saat startup?
   * A. Mengatur `livenessProbe` dengan `periodSeconds: 2` tanpa parameter lain.
   * B. Memasang `startupProbe` dengan `failureThreshold: 30` dan `periodSeconds: 2`, yang menahan evaluasi `livenessProbe` hingga proses selesai.
   * C. Menggunakan `preStop` hook dengan perintah `sleep 60`.
   * D. Menonaktifkan seluruh probe dan mengandalkan restart policy container saja.

8. Perhatikan potongan anotasi Ingress NGINX berikut:
   ```yaml
   nginx.ingress.kubernetes.io/canary: "true"
   nginx.ingress.kubernetes.io/canary-by-header: "X-Features"
   nginx.ingress.kubernetes.io/canary-by-header-value: "Experimental"
   nginx.ingress.kubernetes.io/canary-weight: "20"
   ```
   Bagaimana ingress controller akan merutekan request HTTP yang membawa header `X-Features: Standard`?
   * A. Request dialihkan 20% ke service canary.
   * B. Request langsung diarahkan 100% ke service canary karena memiliki header `X-Features`.
   * C. Request diarahkan 100% ke service utama (stable) karena nilainya tidak cocok dengan `Experimental`, mengabaikan aturan canary-weight.
   * D. Request ditolak dengan respon HTTP 403 Forbidden.

9. Apa implikasi arsitektur jika `allowPrivilegeEscalation: true` diaktifkan pada container di lingkungan produksi?
   * A. Container akan otomatis memiliki resource CPU tak terbatas.
   * B. Proses child di dalam container dapat memperoleh privilege lebih tinggi daripada proses parent-nya (misalnya melalui binary `setuid`), membuka potensi celah eskalasi hak akses host.
   * C. Load balancer dapat menembus port internal pod tanpa autentikasi.
   * D. Kubelet akan memprioritaskan pod tersebut saat terjadi resource starvation.

10. Ketika melakukan investigasi deployment yang macet (*stuck*) dengan status `ImagePullBackOff`, urutan diagnosa level rendah yang paling logis adalah:
    * A. Restart node host -> Hapus namespace -> Ubah permission kube-apiserver.
    * B. `kubectl describe pod` untuk cek log event kegagalan otentikasi/DNS -> Verifikasi `imagePullSecrets` -> Coba pull manual image menggunakan CLI runtime (`crictl pull`) di node target.
    * C. Naikkan batas memory limit pod -> Jalankan command `terraform refresh`.
    * D. Lakukan rolling rollback tanpa mengecek konfigurasi credential.

---

### Bagian C: Kasus Troubleshooting & Evaluasi Desain (Skenario Produksi)
11. **Skenario Kasus 1**:
    Tim Anda melakukan rilis canary 10% untuk microservice autentikasi. Lima menit setelah rilis, metrik agregat global cluster menunjukkan error rate transaksi masih di batas toleransi aman (0.8%). Namun, channel bantuan nasabah menerima komplain dari segmen pengguna tertentu yang tidak dapat login.
    * Pertanyaan Analisis:
      1. Mengapa metrik global menyamarkan kegagalan fatal pada tahap canary ini?
      2. Metrik spesifik apa yang seharusnya diisolasi dan dianalisis selama fase canary berjalan?

12. **Skenario Kasus 2**:
    Sebuah aplikasi monolitik warisan (*legacy*) di-containerisasi dan di-deploy ke Kubernetes. Aplikasi ini menangani terminasi secara buruk: jika menerima sinyal `SIGTERM`, aplikasi langsung melakukan `exit(0)` seketika dan memutus ratusan transaksi database yang sedang menulis data, menyebabkan korupsi state data transaksi.
    * Pertanyaan Solusi:
      Tanpa izin untuk mengubah source code aplikasi dalam jangka pendek, konfigurasi pod lifecycle apa yang bisa dipasang sebagai solusi perantara (*workaround*) agar database client socket ditutup secara aman sebelum proses mati?

13. **Skenario Kasus 3**:
    Sebuah cluster production multi-tenant mengalami degradasi performa drastis pada Node Worker. Satu pod developer pemula mengalami kebocoran memori (*memory leak*) tak terkontrol. Pod tersebut tidak memiliki konfigurasi `resources.limits`. Akibatnya, Linux Kernel Out-Of-Memory Killer (OOM Killer) pada node tersebut terbangun dan mematikan pod CoreDNS dan Kube-Proxy yang berada pada node yang sama.
    * Pertanyaan Rekayasa:
      Kebijakan tata kelola cluster (*governance policy*) tingkat cluster apa yang wajib diterapkan di level namespace untuk mengamankan infrastruktur dari pod tanpa batasan resource?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian A (Basic)
1. **B** — `sleep` di preStop hook menunda matinya aplikasi sehingga kube-proxy dan ingress controller punya cukup waktu untuk memperbarui routing table mereka dan berhenti mengarahkan traffic baru ke pod tersebut.
2. **C** — `:latest` bersifat mutable. Tidak ada jaminan image yang ditarik hari ini sama dengan kemarin, sehingga proses auditabilitas dan rollback yang presisi menjadi mustahil.
3. **C** — GitOps menarik state dari dalam (*pull-based*), meniadakan keharusan mengekspos API Kubernetes keluar cluster demi kebutuhan runner CI.
4. **C** — `readinessProbe` mengontrol apakah pod masuk ke dalam daftar endpoint service aktif. Jika gagal, pod tidak menerima traffic tetapi proses tetap dibiarkan hidup.
5. **B** — State lock mencegah *race condition* dan korupsi state file jika dua eksekusi apply dijalankan bersamaan.

#### Bagian B (Intermediate)
6. **A** — `maxSurge: 50%` dari 4 pod = +2 pod (Maksimum 4 + 2 = 6 pod). `maxUnavailable: 25%` dari 4 pod = 1 pod boleh mati (Minimum yang harus tetap hidup = 4 - 1 = 3 pod).
7. **B** — `startupProbe` mengalokasikan waktu polling awal (30 * 2s = 60s). Selama startupProbe belum lolos, livenessProbe tidak akan membunuh container tersebut.
8. **C** — Karena header value tidak cocok dengan `Experimental`, aturan `canary-by-header` menolak rute canary dan langsung mengarahkannya kembali ke baseline deployment (weight tidak dievaluasi jika header rule gagal match).
9. **B** — `allowPrivilegeEscalation` memungkinkan binary setuid mengubah UID runtime ke root, sebuah risiko keamanan eskalasi privilege di dalam node.
10. **B** — Menginspeksi pod event via describe memberikan akar masalah pasti (apakah DNS lookup registry gagal atau autentikasi `ImagePullBackOff`), lalu diverifikasi langsung di container runtime node.

#### Bagian C (Kasus Troubleshooting)
11. **Analisis Skenario 1**:
    * Metrik global mengagregasikan 100% traffic (90% stable + 10% canary). Error 8% pada traffic canary yang hanya memegang 10% traffic total hanya akan terlihat seperti error $0.8\%$ pada metrik agregat global (tersamarkan oleh dominasi traffic sukses).
    * Solusi: Observabilitas canary wajib mengisolasi metrik slice khusus instance canary secara terpisah: `sum(rate(http_requests_total{variant="canary",status=~"5.*"}[1m])) / sum(rate(http_requests_total{variant="canary"}[1m]))`.
12. **Analisis Skenario 2**:
    * Pasang container lifecycle handler `preStop` yang mengeksekusi shell script custom untuk menutup port koneksi atau memanggil command internal graceful via CLI/socket lokal sebelum sinyal `SIGTERM` akhirnya dikirim ke proses utama. Alternatif lain: jalankan aplikasi menggunakan init wrapper script yang bertindak sebagai PID 1 yang menahan sinyal dan memicu shutdown database client secara prosedural.
13. **Analisis Skenario 3**:
    * Menerapkan **LimitRange** pada namespace untuk menetapkan default request dan limit pada setiap pod yang dibuat tanpa deklarasi resource.
    * Menerapkan **ResourceQuota** untuk membatasi konsumsi agregat namespace.
    * Mengaktifkan admission controller (seperti Kyverno atau OPA Gatekeeper) yang otomatis menolak (*reject*) deployment pod jika tidak menyertakan blok konfigurasi `resources.limits.memory` dan `resources.limits.cpu`.

---

## 16. Summary

Implementasi DevOps tingkat produksi membutuhkan pergeseran paradigma dari sekadar "otomasi deployment" menuju **keandalan sistem holistik (*systemic reliability*)**.

1. **Zero-Downtime bukan kebetulan**: Tercipta melalui koordinasi presisi antara penanganan sinyal kernel OS (`SIGTERM`), siklus terminasi pod (`preStop hook`), propagasi jaringan service mesh/ingress, dan desain aplikasi yang stateless serta graceful.
2. **Deployment Progresif adalah Standar Enterprise**: Menggantikan rolling update buta dengan *Canary Deployments* berbasis metrik verifikasi real-time (SLO/SLA) untuk memitigasi *blast radius* kegagalan rilis secara instan dan otomatis.
3. **Integritas Konfigurasi Berkelanjutan**: GitOps bertindak sebagai mekanisme rekonsiliasi yang menjaga *cluster state* tetap konvergen dengan repositori deklaratif, meniadakan deviasi konfigurasi liar (*configuration drift*), dan memperketat postur keamanan cluster melalui isolasi hak akses push.
4. **Pertahanan Berlapis (Defense-in-Depth)**: Keamanan produksi menuntut integrasi proaktif: isolasi state IaC, pod security standards non-root, pemindaian kerentanan kontinu, dan pembatasan konsumsi resource mutlak guna menghindari kegagalan cascading di lingkungan multi-tenant.