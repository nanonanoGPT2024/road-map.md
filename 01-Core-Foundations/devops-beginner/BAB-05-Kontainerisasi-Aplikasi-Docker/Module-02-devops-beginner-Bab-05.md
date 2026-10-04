# BAB 05: Materi Lanjutan
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Merancang** arsitektur *Continuous Delivery* tingkat lanjut berbasis GitOps dengan pemisahan *state engine* dan *orchestration pipeline*.
2. **Mengimplementasikan** strategi *Zero-Downtime Deployment* (Advanced Canary & Blue-Green) yang dikendalikan oleh metrik analisis otomatis (*Automated Canary Analysis* / ACA).
3. **Mengintegrasikan** tata kelola rahasia enterprise (*Enterprise Secrets Management*) menggunakan HashiCorp Vault dengan prinsip *dynamic short-lived credentials* dan *envelope encryption*.
4. **Membangun** sistem observabilitas terdistribusi (Metrics, Logs, Traces) berbasis OpenTelemetry dan Prometheus untuk mendeteksi degradasi performa mikro (*micro-outages*) pada skala produksi.
5. **Mengevaluasi dan Memitigasi** kegagalan sistem terdistribusi melalui *chaos engineering*, *circuit breaking*, dan konfigurasi ketahanan kernel/kontainer tingkat lanjut.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
*   **Linux System Administration**: Pemahaman mendalam mengenai Linux Namespaces, Cgroups v2, Signals (`SIGTERM`, `SIGKILL`), iptables/eBPF, dan debugging level kernel (`strace`, `lsof`, `tcpdump`).
*   **Container Internals**: Anatomi OCI (Open Container Initiative), multi-stage builds, non-root execution, dan layer caching mechanisms.
*   **Networking L4/L7**: OSI Layer, TCP Handshake/Termination, TLS 1.3 Termination, HTTP/2, gRPC multiplexing, DNS resolution lifecycles (`/etc/resolv.conf`, `ndots:5`).
*   **Dasar CI/CD & Kubernetes**: Konsep dasar Pod, Deployment, Service, Ingress, serta eksekusi pipeline CI (seperti GitHub Actions atau GitLab CI) yang telah dipelajari pada bab sebelumnya.

---

### 3. Concept & Internal Architecture

Pada tingkat enterprise, DevOps bertransformasi dari sekadar otomasi skrip bash menjadi rekayasa keandalan perangkat lunak (*Reliability Engineering*) dan penyediaan platform (*Platform Engineering*).

```
+---------------------------------------------------------------------------------------------------+
|                                  ENTERPRISE CONTROL PLANE                                         |
|                                                                                                   |
|  +--------------------+      Webhook      +----------------------+   Pull Loop   +-------------+  |
|  | Git Repository     | ----------------> | GitOps Engine        | <===========> | Kubernetes  |  |
|  | (Desired State)    |                   | (ArgoCD / Flux)      | (Reconcile)   | API Server  |  |
|  +--------------------+                   +----------------------+               +------+------+  |
|            |                                         |                                  |         |
|            | Trigger CI                              v Audit & Verification             v Mutate  |
|            v                              +----------------------+               +-------------+  |
|  +--------------------+                   | HashiCorp Vault      |               | Admission   |  |
|  | Build & Security   |                   | (Dynamic Secret Eng) |               | Controller  |  |
|  | Pipeline (Trivy,   |                   +----------------------+               | (Opa/Kyverno|  |
|  | Cosign Sign Engine)|                                                          +-------------+  |
+------------+----------------------------------------------------------------------------+--------+
             | Push Image (Digest-pinned)                                                 |
             v                                                                            v
+-------------------------+      Service Mesh / Envoy L7 Dynamic Routing         +------------------+
| Secure OCI Registry     | ===================================================> | Microservices    |
| (Harbor / ECR Immutab.) |   Traffic Split: 90% Stable (v1) | 10% Canary (v2)  | Data Plane       |
+-------------------------+                                                      +------------------+
                                                                                          |
                                  Telemetry Loop: Traces, Logs, Metrics                   v
+---------------------------------------------------------------------------------------------------+
|  OpenTelemetry Collector ---> Prometheus/Thanos ---> Argo Rollouts (Metric Analyzer Engine)      |
|  * Rule: P99 Latency < 120ms AND HTTP 5xx Error Rate < 0.1% -> Promote / Auto-Rollback           |
+---------------------------------------------------------------------------------------------------+
```

#### A. The GitOps Reconciliation Loop
Arsitektur GitOps modern tidak menggunakan pendekatan *push* dari CI server menuju cluster. Pendekatan *push* membuka celah keamanan karena menuntut CI server memiliki akses langsung (`cluster-admin`) ke API Server Kubernetes. Sebaliknya, GitOps menggunakan model *pull-based reconciliation*:
1. State yang diinginkan (*Desired State*) disimpan secara deklaratif di repositori Git (terenkripsi via SOPS atau SealedSecrets jika terdapat data sensitif).
2. Sebuah agen di dalam kluster (*In-Cluster Agent*, misal: ArgoCD Application Controller) secara periodik membandingkan *Desired State* di Git dengan *Live State* di Kubernetes API Server via mekanisme polling dan Webhook.
3. Jika terdeteksi *out-of-sync* (drift), GitOps Controller mengeksekusi rekonsiliasi melalui API Server:
   $$\text{Drift} = \text{Desired State} \setminus \text{Live State}$$
4. Jika terjadi modifikasi manual di dalam kluster (kebijakan anti-drift diaktifkan), controller akan menimpa perubahan tersebut kembali ke state yang tercatat di Git.

#### B. Dynamic Traffic Routing & Automated Canary Analysis (ACA)
Canary deployment tradisional yang mengandalkan replika Pod (misal: 1 Pod Canary dari total 10 Pod = 10% trafik) memiliki kelemahan mendasar: rasio trafik terikat mati dengan penggunaan kapasitas komputasi (*resource allocation*). 

Arsitektur produksi modern memisahkan routing trafik L7 dari alokasi replika pods:
1. **Envoy/Service Mesh Layer**: Ingress Controller atau Service Mesh membagi trafik HTTP/gRPC menggunakan *header routing*, *cookie matching*, atau *weight-based distribution* murni pada layer 7 tanpa mempedulikan rasio jumlah pod.
2. **Analysis Loop**: Deployment Controller (misal: Argo Rollouts) menjalankan *Canary Step*. Setiap fase (misal: injeksi trafik 5%, 20%, 50%), *Background Analysis* mengirim kueri PromQL ke Prometheus:
   $$\text{Error Rate} = \frac{\sum(\text{rate}(\text{http\_requests\_total}\{\text{status}=\sim"5.."\}[\text{2m}]))}{\sum(\text{rate}(\text{http\_requests\_total}[\text{2m}]))} \times 100$$
3. Jika metrik berada di bawah ambang batas (*threshold*), deployment dinaikkan (*promoted*). Jika terjadi anomali (misal: P99 latency melonjak > 200ms atau Error Rate > 0.5%), sistem secara otonom membatalkan deployment (*instant rollback*), mengembalikan bobot trafik 100% ke versi stabil dalam hitungan milidetik.

#### C. Envelope Encryption & Dynamic Secrets Injection
Pada kluster enterprise, *Kubernetes Secrets* standar base64 dianggap tidak aman secara *default* karena hanya tersimpan di etcd (meskipun telah dienkripsi pada rest level). Modul ini menerapkan **Zero-Trust Secret Injection**:
1. Pod dideklarasikan tanpa menyimpan rahasia apa pun (bahkan nilai terenkripsi sekalipun).
2. HashiCorp Vault Agent Injector mendeteksi anotasi Pod via *Mutating Admission Webhook*.
3. Vault Injector memodifikasi spesifikasi Pod secara transparan dengan menyisipkan *sidecar/init-container* berbasis *In-Memory volume* (`emptyDir: medium: Memory`).
4. Kontainer init berkomunikasi dengan Vault API menggunakan ServiceAccount Token k8s bawaan via Vault Kubernetes Auth Method.
5. Vault memvalidasi token, mengevaluasi kebijakan IAM, dan menghasilkan kredensial dinamis (*dynamic short-lived credentials*) yang kedaluwarsa via TTL (misal: koneksi database PostgreSQL yang dibuat *on-the-fly* dengan waktu hidup 1 jam).
6. Kredensial ditulis langsung ke `/vault/secrets/` di dalam memory disk (RAM) dan dikonsumsi oleh aplikasi tanpa menyentuh *block storage* fisik kluster.

---

### 4. Why & What

| Dimensi | Pola Tradisional / Pemula | Pola Enterprise Lanjutan |
| :--- | :--- | :--- |
| **CI/CD Security Boundary** | CI Runner memiliki hak akses `cluster-admin` via file `kubeconfig`. Sangat rentan jika runner terkompromi. | CI Runner hanya membangun OCI image, menandatangani image dengan Cosign, dan memodifikasi commit Git. Pull-based agent menjalankan deployment dengan batasan RBAC ketat. |
| **Deployment Strategy** | Rolling Updates standard k8s. Masalah: Jika versi baru lolos health check sederhana tetapi melempar error saat menerima trafik riil, kegagalan meluas ke 100% pengguna. | Automated Canary Analysis (ACA) terintegrasi dengan metrik performa L7 (Envoy + Prometheus). Rollback otomatis saat latensi melonjak atau SLA terlanggar. |
| **Secrets Management** | Kredensial statis, disimpan lama, di-commit ke Git secara tidak sengaja atau manual di-*apply* sebagai K8s Secret polos. | *Zero-standing privileges*, *dynamic lease*, *auto-rotation*, dan injeksi in-memory via Vault Agent. Token berumur pendek (short TTL). |
| **Drift Detection** | Dibiarkan terjadi. Tim melakukan `kubectl edit` manual di produksi saat insiden, menyebabkan repositori Git tertinggal dan tidak sinkron. | Anti-drift engine aktif secara periodik. Modifikasi manual di luar Git akan langsung di-rollback ke spesifikasi Git secara otomatis. |
| **Audit & Compliance** | Audit log manual di tingkat server CI, sulit ditelusuri siapa merilis artefak apa ke pod mana. | *Cryptographic Supply Chain Security*. Setiap image ditandatangani (*SLSA provenance*), diverifikasi oleh Admission Webhook sebelum diizinkan masuk kluster. |

---

### 5. How (Workflow Detail)

Alur produksi end-to-end dari commit kode hingga traffic shifting L7:

```
[Developer]
    │  1. Git Push (Signed Commit)
    ▼
[GitHub / GitLab Repo: Application Code]
    │  2. Webhook Event
    ▼
[CI Pipeline (GitHub Actions / GitLab CI)]
    │  3. Run Unit & Integration Tests
    │  4. Build OCI Compliant Image
    │  5. Security Static Analysis (SAST) & Container Vulnerability Scan (Trivy)
    │  6. Sign Image with Cosign (Keyless via Sigstore OIDC)
    │  7. Push to OCI Registry (Harbor/ECR) using Immutable Digest (sha256:...)
    │  8. Checkout "Config / Manifests" Git Repository
    │  9. Update target image digest in Helm values / Kustomize overlay
    │ 10. Commit & Push to Config Repo (GitOps Source of Truth)
    ▼
[GitOps Repository: Infrastructure Desired State]
    │ 11. ArgoCD detects commit via Webhook or Polling
    ▼
[ArgoCD In-Cluster Controller]
    │ 12. Compare Git (Desired) vs K8s API (Live)
    │ 13. Apply CRD: Argo Rollouts Custom Resource
    ▼
[Kubernetes API & Admission Controller]
    │ 14. Kyverno/OPA verifies Cosign Signature against Public Key/Fulcio CA
    │ 15. Signature Valid -> Manifest Accepted. Vault Mutating Webhook injects Secret Sidecar
    ▼
[Argo Rollouts Engine & Service Mesh (Envoy/Istio/Traefik)]
    │ 16. Deploy Canary Pods (v2.0.0) alongside Stable Pods (v1.0.0)
    │ 17. Configure Ingress to route 10% of production traffic to Canary
    │ 18. Trigger Canary Metric Analysis Loop (PromQL)
    ├─── Metrik Normal (Error Rate < 0.1%, P99 < 100ms) ──────────┐
    │    │ 19. Naikkan trafik bertahap: 25% -> 50% -> 100%       │
    │    │ 20. Alihkan seluruh traffic ke v2, destroy v1 Pods    │
    │    ▼                                                       │
    │   [Deployment SUCCESS]                                     │
    └─── Metrik Anomali (Error Rate > 0.5% OR P99 > 250ms) ───────┤
         │ 19. Abort Rollout langsung via Controller             │
         │ 20. Kembalikan 100% trafik ke v1 dalam hitungan ms    │
         │ 21. Isolasi pod v2 untuk keperluan post-mortem logging│
         ▼                                                       │
        [Rollback EXECUTED & Alert PagerDuty Triggered] ─────────┘
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengujian Kualitas Air Kota Otomatis
Bayangkan sebuah instalasi pengolahan air minum metropolitan (Sistem Produksi):
*   **Traditional Rolling Update**: Tim mengganti pipa saluran air lama dengan pipa baru langsung ke semua perumahan warga secara serentak. Jika pipa baru beracun atau bocor, ribuan warga langsung terdampak sebelum tim sempat memutar balik valve utama.
*   **Advanced Canary GitOps**:
    1. Tim memasang sambungan pipa baru (Versi 2) namun hanya mengalirkan 5% debit air ke sebuah bilik pengujian laboratorium (*Canary Pod*).
    2. Sistem sensor spektrometer optik otomatis (*Prometheus Metrics Analysis*) memantau kejernihan dan kemurnian air setiap detik.
    3. Jika sensor mendeteksi penurunan kualitas air sedikit saja (ambang batas batas error terlampaui), sebuah katup otomatis (*Envoy Traffic Splitter*) langsung menutup aliran ke pipa baru dan mengembalikan 100% aliran ke pipa lama (Versi 1) tanpa ada satu pun warga yang meminum air tercemar.
    4. Seluruh desain cetak biru pipa tersimpan dalam brankas terpusat (*GitOps Repository*). Tidak ada teknisi yang diizinkan memotong atau menyambung pipa di lapangan secara manual tanpa cetak biru yang sah.

#### Diagram Arsitektur Traffic Splitting & Metric Feedback

```
                         [ USER TRAFFIC ]
                                │
                                ▼
                   [ Ingress / L7 Reverse Proxy ]
                   [ (Traefik / Envoy / Nginx)  ]
                                │
               ┌────────────────┴────────────────┐
               │ Route Weight:                   │ Route Weight:
               │ 90%                             │ 10%
               ▼                                 ▼
       +---------------+                 +---------------+
       | Stable Service|                 | Canary Service|
       +---------------+                 +---------------+
               │                                 │
               ▼                                 ▼
      [ Stable Pods v1 ]                [ Canary Pods v2 ]
      (Running Base App)                (Running New Release)
               │                                 │
               └────────────────┬────────────────┘
                                │ Expose Prometheus Metrics (/metrics)
                                ▼
                    +-----------------------+
                    | Prometheus Scrape Eng |
                    +-----------------------+
                                │
                                │ PromQL Query Evaluation
                                ▼
                    +-----------------------+
                    | Argo Rollouts Engine  |
                    | (Evaluasi Step Status)|
                    +-----------------------+
                      │                   │
      Success Metric  │                   │ Breached Threshold
      ────────────────┘                   └──────────────────
      Action: Set Weight 25%              Action: Set Weight 0%
      (Lanjut ke tahapan berikutnya)      (Auto-Rollback & Terminate)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Graceful Handling & Probes Configuration
Aplikasi yang tidak mengimplementasikan penanganan sinyal OS dengan benar akan menyebabkan kegagalan koneksi L7 (HTTP 502/504) saat proses rolling deployment berjalan.

```yaml
# simple-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: resilient-microservice
  namespace: production
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # Maksimal pod tambahan selama proses update
      maxUnavailable: 0  # Nol toleransi pod mati saat transisi
  selector:
    matchLabels:
      app: resilient-microservice
  template:
    metadata:
      labels:
        app: resilient-microservice
    spec:
      containers:
      - name: core-api
        image: internal-registry.enterprise.io/apps/core-api:1.2.4
        lifecycle:
          preStop:
            exec:
              # Berikan jeda agar kube-proxy/endpoints controller sempat menghapus IP pod dari iptables
              command: ["/bin/sh", "-c", "sleep 15"]
        ports:
        - containerPort: 8080
        resources:
          limits:
            cpu: "500m"
            memory: "512Mi"
          requests:
            cpu: "100m"
            memory: "128Mi"
        livenessProbe:
          httpGet:
            path: /healthz/liveness
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /healthz/readiness
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 3
          failureThreshold: 2
```

#### B. Practical Enterprise Example: Argo Rollout dengan Dynamic Secrets & Prometheus Automated Analysis

Konfigurasi berikut mendefinisikan strategi deployment canary tingkat lanjut dengan integrasi HashiCorp Vault Agent Injector dan metrik analisis otomatis untuk mengevaluasi error rate.

```yaml
# production-rollout.yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: payment-processor
  namespace: payment-engine
spec:
  replicas: 10
  revisionHistoryLimit: 5
  selector:
    matchLabels:
      app.kubernetes.io/name: payment-processor
  strategy:
    canary:
      # Analisis dijalankan di latar belakang selama masa promosi canary
      analysis:
        templates:
          - templateName: error-rate-analysis
        args:
          - name: service-name
            value: payment-processor-canary
      steps:
        # Step 1: Alirkan 10% trafik ke canary, tunggu validasi selama 10 menit
        - setWeight: 10
        - pause: { duration: 10m }
        # Step 2: Alirkan 30% trafik, pause manual menunggu sanity check tambahan
        - setWeight: 30
        - pause: { duration: 15m }
        # Step 3: Alirkan 60% trafik
        - setWeight: 60
        - pause: { duration: 5m }
  template:
    metadata:
      labels:
        app.kubernetes.io/name: payment-processor
      annotations:
        # Vault Agent Injector Annotations
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "payment-processor-role"
        vault.hashicorp.com/agent-inject-secret-db-creds.txt: "database/creds/payment-service-role"
        vault.hashicorp.com/agent-inject-template-db-creds.txt: |
          {{- with secret "database/creds/payment-service-role" -}}
          POSTGRES_USER="{{ .Data.username }}"
          POSTGRES_PASSWORD="{{ .Data.password }}"
          {{- end -}}
    spec:
      serviceAccountName: payment-processor-sa
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
      containers:
      - name: payment-app
        image: harbor.enterprise.internal/fintech/payment-processor:v2.4.0@sha256:7c8b2c4e2098d5f3d4ef8d1d3dfc7e7b5f1345d944c6883f3d7d0a2f483c79a1
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP
        env:
        - name: CONFIG_DIR
          value: "/vault/secrets"
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 2Gi
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
              - ALL
---
# analysis-template.yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: error-rate-analysis
  namespace: payment-engine
spec:
  args:
  - name: service-name
  metrics:
  - name: success-rate
    interval: 30s
    successCondition: result[0] <= 0.001 # Error rate wajib <= 0.1%
    failureLimit: 3                       # 3 kali pelanggaran berturut-turut memicu Auto-Rollback
    provider:
      prometheus:
        address: http://prometheus-k8s.monitoring.svc.cluster.local:9090
        query: |
          sum(rate(http_requests_total{service="{{args.service-name}}",status=~"5.*"}[2m]))
          /
          sum(rate(http_requests_total{service="{{args.service-name}}"}[2m]))
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
*   **Perusahaan**: Bank Digital Nasional (Transaksi Finansial Skala Besar).
*   **Skala Beban**: 35.000 Transaksi Per Detik (TPS) pada jam sibuk; sistem terdistribusi di 3 Region (Multi-Cluster, 1.200 Nodes Kubernetes).
*   **Masalah Arsitektur Awal**: Menggunakan *Push-based CI/CD* via Jenkins yang memegang sertifikat admin kluster. Rilis dilakukan pada malam hari menggunakan strategi default *RollingUpdate*.
*   **Insiden Kritis**: 
    Pada rilis versi `v3.12.0`, terdapat kebocoran koneksi pool database (leaked connection pool) yang hanya terjadi ketika konkurensi melampaui 10.000 TPS. Karena *RollingUpdate* hanya mengevaluasi *Liveness probe* HTTP 200 sederhana, Kubernetes mengganti seluruh Pod lama dalam 4 menit. Saat beban penuh dialihkan, koneksi database utama exhausted (mencapai batas 5.000 koneksi), menyebabkan seluruh kluster cascade-crash. Downtime berlangsung selama 42 menit dengan estimasi kerugian transaksi mencapai Rp 14 Miliar.

#### Transformasi Arsitektur
1. **Adopsi GitOps Pull-Model**: Memutus hak akses Jenkins ke kluster. Jenkins hanya bertugas menguji, memindai, membangun container image, dan membuat Pull Request ke repositori GitOps. ArgoCD mengelola proses sinkronisasi manifest.
2. **Implementasi Traffic Shadowing & Dynamic Canary**:
   * Argo Rollouts dikombinasikan dengan Envoy Ingress Gateway.
   * Fase 1 rilis menggunakan *Traffic Mirroring*: 10% trafik nyata di-mirroring ke pod canary tanpa mengirim respons kembali ke klien untuk memverifikasi konkurensi database tanpa risiko.
   * Fase 2 rilis: Canary traffic dibuka bertahap: 2% $\to$ 10% $\to$ 25% $\to$ 50% $\to$ 100%.
3. **Automated Canary Analysis (ACA)**:
   * Metrik evaluasi tidak hanya status kode HTTP, namun juga latensi P99 (`histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[1m]))`) dan metrik internal aplikasi: *HikariCP Active Database Connection Pool Rate*.
4. **Hasil**:
   * Saat rilis berikutnya (`v3.13.0`) mengalami regresi memori serupa, sistem ACA mendeteksi anomali pada fase rilis 2% dalam waktu 90 detik.
   * Argo Rollouts langsung memutus rilis, menurunkan traffic canary ke 0%, dan mengembalikan seluruh routing ke versi stabil secara otomatis.
   * Tidak ada kegagalan transaksi yang dialami nasabah (*zero customer impact*), SLA ketersediaan 99.99% tercapai.

---

### 9. Trade-offs & Deep Comparison

#### A. Strategi Rilis

| Parameter | Rolling Update Standar | Blue/Green Deployment | Canary Deployment Lanjutan |
| :--- | :--- | :--- | :--- |
| **Kebutuhan Resource (Cost)** | **Rendah**: Membutuhkan alokasi tambahan hanya sebatas nilai `maxSurge` (misal 25%). | **Sangat Tinggi**: Membutuhkan minimal 200% kapasitas resource (lingkungan kembar identik). | **Moderat**: Alokasi tambahan terikat pada langkah canary (misal +10% hingga +20%). |
| **Downtime / Latensi Transisi** | Minimal, namun berisiko memaparkan error ke sebagian user jika app lolos probe. | Nol downtime saat cutover switch L4/L7 DNS/Service. | Nol downtime, kontrol presisi pemaparan risiko ke sekumpulan kecil user. |
| **Kecepatan Rollback** | **Lambat**: Harus me-rollout ulang pod lama dari awal (terkena cold-start). | **Sangat Cepat**: Cukup alihkan kembali pointer switch router/load balancer. | **Cepat**: Turunkan weight traffic canary ke 0 via dynamic Envoy/Mesh config. |
| **Kompleksitas Operasional** | Nol tooling tambahan (fitur native Kubernetes Engine). | Sedang; Memerlukan pipeline pengelola dua environment terpisah. | Tinggi; Memerlukan Service Mesh/Ingress Controller canggih dan metrics scraper (Prometheus). |

#### B. Pola CI/CD: Push vs Pull Model

```
+--------------------------------------------------------------------------------------------------+
| Push-based (CI drives Cluster)                                                                   |
| [CI Server] ──(Kubeconfig / Port 6443 Exposed)──> [Kubernetes API]                              |
| * Trade-off: Mengharuskan CI runner memegang kunci kluster terkuat; risiko eskalasi hak istimewa.|
+--------------------------------------------------------------------------------------------------+
| Pull-based (GitOps Engine inside Cluster)                                                        |
| [GitOps Agent] ──(Outbound HTTPS / Read-Only)──> [Git Repo]                                      |
| * Trade-off: Menghilangkan paparan port cluster ke publik, namun meningkatkan latensi penerapan |
|   (bergantung pada polling interval / webhooks) dan butuh resource agent di dalam kluster.       |
+--------------------------------------------------------------------------------------------------+
```

---

### 10. Common Mistakes & Troubleshooting Guide

#### 1. Masalah: Pod Termination Hang & HTTP 502/504 Bad Gateway Saat Rilis
*   **Akar Masalah**: Aplikasi menerima sinyal `SIGTERM` dari kubelet dan langsung menutup listener socket HTTP secara instan, sementara iptables kluster atau IPVS proxy belum selesai menghapus IP pod tersebut dari load balancer *Endpoints*. Klien yang dialihkan ke IP tersebut menerima penolakan koneksi (*connection reset by peer*).
*   **Solusi**:
    *   Implementasikan `preStop` hook dengan delay sleep (5 - 15 detik) untuk memberikan ruang propagasi iptables.
    *   Terapkan *Graceful Shutdown* di layer kode aplikasi: Berhenti menerima koneksi baru, tunggu *in-flight requests* selesai diproses (misal timeout 30 detik), baru tutup koneksi basis data.

```yaml
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 15"]
```

#### 2. Masalah: CrashLoopBackOff Akibat Race Condition Secret Injection
*   **Akar Masalah**: Aplikasi container utama start lebih cepat daripada Vault Agent Init-Container yang bertugas mengunduh rahasia dari Vault Server, menyebabkan file konfigurasi `/vault/secrets/db-creds.txt` belum terbentuk saat aplikasi membaca sistem file.
*   **Diagnostik**:
    ```bash
    kubectl describe pod <pod-name> -n <namespace>
    kubectl logs <pod-name> -c vault-agent-init -n <namespace>
    ```
*   **Solusi**: Konfigurasikan container aplikasi utama agar tidak langsung panik (*panic crash*) saat membaca file konfigurasi yang belum siap, atau gunakan mekanik blocking script pada wrapper entrypoint kontainer:
    ```sh
    #!/usr/bin/env sh
    while [ ! -f /vault/secrets/db-creds.txt ]; do
      echo "Waiting for dynamic secrets injection..."
      sleep 1
    done
    exec "$@"
    ```

#### 3. Masalah: Flapping Canary Akibat Ambang Metrik Terlalu Agresif
*   **Akar Masalah**: Kueri PromQL pada `AnalysisTemplate` mengevaluasi metrik dalam rentang waktu yang terlalu pendek (misal: `[30s]`) pada kondisi throughput rendah. Fluktuasi 1 error request tunggal langsung menyebabkan tingkat kegagalan melonjak di atas 5%, memicu rollback palsu (*false-positive rollback*).
*   **Solusi**: Gunakan rentang waktu minimal 2 hingga 5 menit (`[2m]` atau `[5m]`) dan sertakan batas absolut volume minimum request (*traffic floor*) sebelum mengevaluasi error rate:
    ```promql
    (
      sum(rate(http_requests_total{status=~"5.*"}[2m]))
      /
      sum(rate(http_requests_total[2m]))
    ) > 0.01 and (sum(rate(http_requests_total[2m])) > 50)
    ```

---

### 11. Best Practices (Production Checklist)

#### Security & Supply Chain Hardening
- [ ] **Image Digest Immutability**: Jangan pernah menggunakan tag mutable seperti `:latest` atau `:v1.0.0`. Selalu kunci image menggunakan SHA256 digest: `image@sha256:...`.
- [ ] **Distroless / Minimal Base**: Gunakan Google Container Tools Distroless atau Alpine minimalis untuk meminimalkan permukaan serangan (tidak ada package manager, tidak ada bash shell di image runtime produksi).
- [ ] **Rootless Enforcement**: Paksa kontainer berjalan sebagai non-root melalui Pod Security Context (`runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `drop: ["ALL"]`).
- [ ] **Binary Cryptographic Attestation**: Verifikasi tanda tangan digital image via Cosign/Kyverno sebelum pod dijadwalkan oleh API Server.

#### Resiliency & Availability
- [ ] **Pod Disruption Budget (PDB)**: Konfigurasikan `minAvailable` atau `maxUnavailable` untuk mencegah maintenance node (draining) mematikan seluruh instans layanan.
- [ ] **Topology Spread Constraints**: Distribusikan Pod melintasi Failure Zones/Availability Zones yang berbeda secara merata (`topology.kubernetes.io/zone`).
- [ ] **Resource Requests == Limits untuk QoS Guaranteed**: Pada microservice berlatensi kritis, samakan nilai *request* dan *limit* CPU dan Memori untuk mencegah noisy-neighbor throttling dan OOM-Kill acak.

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: payment-processor-pdb
  namespace: payment-engine
spec:
  minAvailable: 80%
  selector:
    matchLabels:
      app.kubernetes.io/name: payment-processor
```

---

### 12. Hands-on Practice

Struktur direktori praktikum yang akan kita bangun:

```
hands-on/m02/
├── 01-prerequisites/
│   └── namespace-rbac.yaml
├── 02-vault/
│   └── dynamic-secret-role.sql
├── 03-app/
│   ├── main.go
│   └── Dockerfile
├── 04-manifests/
│   ├── rollout.yaml
│   ├── service.yaml
│   └── analysis-template.yaml
└── 05-chaos/
    └── inject-error-traffic.sh
```

#### Langkah 1: Siapkan Namespace dan RBAC
Simpan file berikut di `hands-on/m02/01-prerequisites/namespace-rbac.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: advanced-platform
  labels:
    pod-security.kubernetes.io/enforce: restricted
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: advanced-app-sa
  namespace: advanced-platform
```

Eksekusi:
```bash
kubectl apply -f hands-on/m02/01-prerequisites/namespace-rbac.yaml
```

#### Langkah 2: Buat Kode Aplikasi Go yang Tahan Uji
Simpan di `hands-on/m02/03-app/main.go`. Aplikasi ini menyimulasikan endpoint bisnis dengan kemampuan injeksi error terkontrol untuk menguji sistem Canary Rollout.

```go
package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"
)

var (
	healthy      int32 = 1
	failureRatio int32 = 0 // Persentase kegagalan terinjeksi (0-100)
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	mux := http.NewServeMux()
	
	// Endpoint Bisnis
	mux.HandleFunc("/api/v1/transaction", func(w http.ResponseWriter, r *http.Request) {
		val := atomic.LoadInt32(&failureRatio)
		if val > 0 && (time.Now().UnixNano()%100) < int64(val) {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"status":"error","code":500,"msg":"Database connection failed"}`))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"success","version":"v2.0.0"}`))
	})

	// Health Checks
	mux.HandleFunc("/healthz/liveness", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("UP"))
	})
	
	mux.HandleFunc("/healthz/readiness", func(w http.ResponseWriter, r *http.Request) {
		if atomic.LoadInt32(&healthy) == 1 {
			w.WriteHeader(http.StatusOK)
			w.Write([]byte("READY"))
			return
		}
		w.WriteHeader(http.StatusServiceUnavailable)
	})

	// Endpoint Simulasi Kegagalan (Chaos)
	mux.HandleFunc("/chaos/inject", func(w http.ResponseWriter, r *http.Request) {
		atomic.StoreInt32(&failureRatio, 30) // Injeksi 30% HTTP 500
		w.Write([]byte("Chaos injected: 30% error rate active"))
	})

	server := &http.Server{
		Addr:    ":" + port,
		Handler: mux,
	}

	go func() {
		fmt.Printf("Server running on port %s\n", port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			fmt.Printf("Listen error: %s\n", err)
		}
	}()

	// Menangkap sinyal OS untuk Graceful Shutdown
	stopChan := make(chan os.Signal, 1)
	signal.Notify(stopChan, syscall.SIGINT, syscall.SIGTERM)
	<-stopChan

	fmt.Println("Server is shutting down gracefully...")
	atomic.StoreInt32(&healthy, 0) // Tandai pod not ready

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		fmt.Printf("Server graceful shutdown failed: %v\n", err)
	} else {
		fmt.Println("Server exited properly.")
	}
}
```

Simpan di `hands-on/m02/03-app/Dockerfile`:
```dockerfile
# Multi-stage secure build
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY main.go .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o enterprise-app .

FROM gcr.io/distroless/static-debian12:nonroot
WORKDIR /
COPY --from=builder /app/enterprise-app .
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/enterprise-app"]
```

#### Langkah 3: Siapkan Manifest Argo Rollouts & Analysis Template
Simpan di `hands-on/m02/04-manifests/analysis-template.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: advanced-http-analysis
  namespace: advanced-platform
spec:
  metrics:
  - name: error-rate
    interval: 15s
    count: 5
    successCondition: result[0] <= 0.05 # Maksimal toleransi error 5%
    failureLimit: 1
    provider:
      prometheus:
        address: http://prometheus-operated.monitoring.svc.cluster.local:9090
        query: |
          sum(rate(http_requests_total{namespace="advanced-platform",status=~"5.*"}[1m]))
          /
          sum(rate(http_requests_total{namespace="advanced-platform"}[1m]))
```

Simpan di `hands-on/m02/04-manifests/rollout.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: transaction-core
  namespace: advanced-platform
spec:
  replicas: 4
  revisionHistoryLimit: 3
  selector:
    matchLabels:
      app: transaction-core
  strategy:
    canary:
      canaryService: transaction-core-canary
      stableService: transaction-core-stable
      trafficRouting:
        nginx:
          stableIngress: transaction-ingress
      steps:
      - setWeight: 25
      - pause: { duration: 30s }
      - analysis:
          templates:
          - templateName: advanced-http-analysis
      - setWeight: 50
      - pause: { duration: 30s }
  template:
    metadata:
      labels:
        app: transaction-core
    spec:
      serviceAccountName: advanced-app-sa
      containers:
      - name: core
        image: local-registry/transaction-core:v1.0.0
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 200m
            memory: 256Mi
        readinessProbe:
          httpGet:
            path: /healthz/readiness
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 3
```

#### Langkah 4: Jalankan Skenario Eksperimen
1. Deploy v1.0.0 ke cluster:
   ```bash
   kubectl apply -f hands-on/m02/04-manifests/analysis-template.yaml
   kubectl apply -f hands-on/m02/04-manifests/rollout.yaml
   ```
2. Validasi status deployment:
   ```bash
   kubectl argo rollouts get rollout transaction-core -n advanced-platform
   ```
3. Update image ke `v2.0.0` (yang sengaja dipicu chaos endpoint-nya):
   ```bash
   kubectl argo rollouts set image transaction-core core=local-registry/transaction-core:v2.0.0 -n advanced-platform
   ```
4. Jalankan skrip `hands-on/m02/05-chaos/inject-error-traffic.sh` untuk memanggil `/chaos/inject` pada Canary Pod.
5. Pantau Argo Rollouts Dashboard/CLI: Amati bagaimana `AnalysisRun` mendeteksi metrik error melebihi 5%, menandai langkah gagal, dan membatalkan rollout (*auto-aborting*) serta mengembalikan status weight routing ke 0% secara instan.

---

### 13. Exercise

#### Level: Easy
1. Modifikasi file `hands-on/m02/04-manifests/rollout.yaml` agar memiliki tahapan rilis (*canary steps*) 4 fase: `10%`, `25%`, `50%`, `75%` dengan waktu tunda masing-masing `45s`.
2. Validasi sintaks manifest tersebut menggunakan command line `kubectl apply --dry-run=client -f <file>`.

#### Level: Medium
1. Konfigurasikan `AnalysisTemplate` Prometheus tambahan yang mengukur **P95 Latency** aplikasi.
2. Aturan metrik: Nilai kuantil 0.95 dari durasi request HTTP tidak boleh melebihi 150ms (`0.150s`) selama observasi window `1m`.
3. Pasang kedua metrik tersebut (Error Rate dan P95 Latency) secara bersamaan pada langkah Rollout spec.

#### Level: Hard
1. Buat arsitektur GitOps menggunakan Kustomize yang membagi konfigurasi menjadi `base/` dan `overlays/production`.
2. Implementasikan HashiCorp Vault Agent Sidecar injection yang merotasi token rahasia setiap 5 menit.
3. Simulasikan kegagalan koneksi Vault (misal: Vault dinonaktifkan/unreachable). Pastikan aplikasi mengimplementasikan circuit-breaker sehingga tetap melayani trafik pembacaan memori (*stale cache*) tanpa mengalami crash loop.

---

### 14. Challenge

**Skenario**:
Anda adalah Principal Platform Engineer di unicorn penyedia layanan ride-hailing. Sistem inti dispatching order (`dispatch-service`) menangani 60.000 request per detik pada database relasional terdistribusi. Tim developer merilis arsitektur baru yang menyertakan **perubahan skema database (Database Schema Migration) yang merusak (breaking changes)**, yaitu penghapusan kolom legasi `legacy_user_token` menjadi sistem multi-auth table baru.

**Tantangan**:
1. Rancang arsitektur pipeline CI/CD dan strategi deployment zero-downtime yang mampu menangani *backward and forward schema compatibility* (Expand-Contract / Parallel-Change Pattern) menggunakan GitOps.
2. Canary deployment harus mendistribusikan trafik berdasarkan Header HTTP (`X-Beta-Tester: true`) untuk 1.000 driver internal terlebih dahulu, sebelum membuka trafik publik berbasis bobot (weight).
3. Buat rancangan dokumentasi arsitektur dan manifest teknis (Argo Rollouts + Vault + Service Mesh EnvoyFilter/VirtualService) yang menjamin:
   * Jika database migration gagal di tengah jalan, state data tidak korup.
   * Rollback aplikasi ke versi sebelumnya tidak crash akibat modifikasi skema database baru.
   * Tidak ada hardcoded credentials yang disimpan di GitOps repository.

*(Deliverable: Dokumen arsitektur teknis dan set manifest deklaratif lengkap tanpa implementasi instan manual).*

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic (5 Pertanyaan)

1. **Mengapa model CI/CD berbasis *Pull* (GitOps) dinilai lebih aman secara fundamental dibandingkan model *Push*?**
   * *Jawaban*: Model Pull tidak mengharuskan kluster Kubernetes membuka port API Server atau memberikan kredensial istimewa (`kubeconfig cluster-admin`) ke sistem CI eksternal. Agen penarik (*pull agent*) berada di dalam perimeter keamanan jaringan privat kluster dan hanya membutuhkan akses keluar (outbound) ke repositori Git.

2. **Apa fungsi utama dari konfigurasi `preStop` hook dengan perintah `sleep` pada container pod Kubernetes?**
   * *Jawaban*: Memberikan jeda waktu bagi sistem kontrol jaringan Kubernetes (kube-proxy, Endpoints Controller, Ingress Controller) untuk menghapus IP Pod yang akan dimatikan dari daftar routing (iptables/IPVS) sebelum kontainer benar-benar berhenti menerima request, sehingga mencegah terjadinya koneksi HTTP 502/504 Bad Gateway.

3. **Apa perbedaan fungsional antara `livenessProbe` dan `readinessProbe`?**
   * *Jawaban*: `livenessProbe` menentukan apakah kontainer harus di-restart oleh kubelet ketika mengalami *deadlock* atau freeze. `readinessProbe` menentukan apakah kontainer sudah siap menerima trafik; jika gagal, IP Pod dihapus sementara dari beban Service endpoints tanpa mematikan proses kontainer.

4. **Mengapa image tag `:latest` dilarang keras digunakan pada lingkungan produksi enterprise?**
   * *Jawaban*: Tag `:latest` bersifat mutable (nilainya dapat berubah sewaktu-waktu). Hal ini merusak prinsip *Deterministic Deployment* dan *Reproducibility*. Jika terjadi rollback, kluster tidak dapat memastikan versi binary mana yang diunduh kembali, serta menyulitkan audit keamanan forensik (*provenance tracking*).

5. **Apa yang dimaksud dengan *Configuration Drift* dalam konteks infrastruktur modern?**
   * *Jawaban*: Kondisi inkonsistensi ketika konfigurasi aktual yang berjalan di lingkungan live produksi berbeda dengan konfigurasi deklaratif yang terdokumentasi di repositori kontrol versi (Git), umumnya disebabkan oleh intervensi modifikasi manual langsung (`ad-hoc changes`).

---

#### B. Intermediate (5 Pertanyaan)

1. **Bagaimana cara kerja HashiCorp Vault Agent Injector menyuntikkan kredensial rahasia ke dalam Pod tanpa perlu mengintegrasikan SDK Vault ke dalam source code aplikasi?**
   * *Jawaban*: Melalui Kubernetes *Mutating Admission Webhook*. Saat Pod dibuat, Webhook mendeteksi anotasi khusus, lalu memodifikasi spesifikasi Pod secara transparan dengan menyisipkan container init dan container sidecar. Kontainer ini bertugas mengautentikasi ke Vault, mengambil rahasia, lalu menyimpannya di shared memory volume (`emptyDir: medium: Memory`) yang dipetakan langsung ke direktori filesystem kontainer aplikasi.

2. **Pada arsitektur Canary Deployment, mengapa pemisahan alokasi pod (*pod replica count*) dan alokasi trafik L7 (*traffic routing*) sangat esensial?**
   * *Jawaban*: Jika alokasi trafik dihitung berdasarkan rasio jumlah pod (misal: 1 Pod Canary dari 10 Pod = 10%), kita tidak bisa mengalirkan fraksi trafik yang sangat kecil (misal: 0.1% atau 1%) tanpa harus melipatgandakan jumlah pod stabil menjadi ratusan pod (inefisiensi biaya). Pemisahan via L7 proxy (seperti Envoy) memungkinkan pengalihan 1% trafik hanya ke 1 Pod Canary secara presisi.

3. **Jelaskan risiko penggunaan CPU Limit (`resources.limits.cpu`) yang terlalu ketat pada runtime yang menggunakan garbage collector seperti Go atau Java!**
   * *Jawaban*: Linux CFS (Completely Fair Scheduler) Kernel akan melakukan *CPU Throttling* jika penggunaan thread aplikasi melebihi kuota kuantum waktu yang ditentukan dalam satu periode CFS (biasanya 100ms). Pada bahasa berbasis GC, ketika proses Garbage Collection terhenti di tengah jalan (*stop-the-world* yang tercekik throttling), latensi P99 aplikasi akan melonjak drastis, memicu *timeout cascade* meskipun CPU utilization agregat terlihat rendah.

4. **Bagaimana peran *Cosign* dan *Kyverno/OPA Gatekeeper* dalam mengamankan alur pasokan perangkat lunak (*software supply chain*)?**
   * *Jawaban*: Cosign menandatangani OCI image secara kriptografis menggunakan kunci privat atau keyless OIDC saat pipeline CI selesai dibangun. Di sisi kluster, Kyverno/OPA bertindak sebagai *Validating Admission Controller* yang mengintersepsi setiap perintah pembuatan Pod; jika image tidak memiliki tanda tangan digital valid dari otoritas yang diakui, permintaan deployment langsung ditolak di gerbang API kluster.

5. **Apa parameter metrik PromQL utama yang digunakan dalam Automated Canary Analysis untuk membedakan antara *infrastructure fault* dan *application bug*?**
   * *Jawaban*: Membandingkan rasio error aplikasi (`HTTP 5xx` non-network vs `HTTP 502/503/504` edge proxy), serta memantau metrik saturasi sistem secara simultan (node CPU/Memory pressure, network drop packets, disk I/O wait) terhadap Pod Canary versus Pod Stable. Jika error hanya terjadi pada Canary dengan penggunaan resource stabil, dapat disimpulkan kegagalan berasal dari *application bug* versi baru.

---

#### C. Skenario Kasus Produksi (3 Pertanyaan Kasus Kompleks)

1. **Skenario 1**: 
   Sebuah kluster Kubernetes produksi mengalami insiden berulang: Setiap kali proses rilis Canary versi baru dimulai, metrik Prometheus langsung mendeteksi lonjakan HTTP 500 pada Pod Canary, memicu Auto-Rollback. Namun ketika image versi baru yang sama dijalankan di lingkungan Staging dengan traffic generator, aplikasi berfungsi 100% normal tanpa error sama sekali.
   * **Pertanyaan**: Apa langkah analisis investigasi Anda, dan apa saja hipotesis akar masalah sistem terdistribusi yang paling memungkinkan?
   * **Analisis & Resolusi**:
     1. *Network Policy & Service Mesh mTLS*: Verifikasi apakah Pod Canary diizinkan berkomunikasi dengan database atau dependensi backend internal. Di Staging, NetworkPolicy seringkali terlalu permisif (`allow-all`), sedangkan di Produksi dibatasi oleh label namespace/pod. Jika label Canary tidak cocok dengan ingress rule dependensi, koneksi ditolak.
     2. *Identity & Access Management (IAM/Vault RBAC)*: ServiceAccount Pod di Staging mungkin memiliki permission yang berbeda dengan ServiceAccount di Produksi. Pod Canary gagal melakukan otentikasi ke Vault untuk mengambil kredensial database riil, menyebabkan query aplikasi throw exception (HTTP 500).
     3. *Database Connection Pool Saturation*: Versi baru mungkin mencoba mengalokasikan koneksi minimal (`minIdle=20`) ke pool database produksi yang statusnya sudah berada di batas kapasitas maksimum (`max_connections`), sehingga inisialisasi koneksi canary ditolak oleh PostgreSQL/MySQL.

2. **Skenario 2**:
   ArgoCD diset untuk melakukan auto-sync terhadap repositori Git. Seorang developer secara tidak sengaja melakukan force-push commit yang menghapus seluruh manifest namespace inti `core-infra`. Dalam 3 detik, ArgoCD mendeteksi drift dan mulai menghapus *live resources* (Deployments, StatefulSets, Services) di kluster produksi.
   * **Pertanyaan**: Mekanisme defensif arsitektural apa yang wajib dipasang pada ArgoCD dan Kubernetes untuk mencegah malapetaka ini terjadi secara otomatis?
   * **Analisis & Resolusi**:
     1. *ArgoCD Sync Windows & Self-Heal Controls*: Nonaktifkan flag `prune: true` pada konfigurasi auto-sync otomatis untuk resource-resource mission-critical.
     2. *Finalizers & Deletion Protection*: Terapkan resource finalizer buatan sendiri atau flag `spec.preventDeletion: true` pada Custom Resource Definitions.
     3. *ArgoCD Resource Exclusion*: Konfigurasikan file manifest ArgoCD `argocd-cm` (`resource.exclusions`) untuk melarang controller menyentuh atau menghapus object `Namespace` atau `CRD` secara deklaratif.
     4. *Admission Controller Webhook (Kyverno/OPA)*: Pasang webhook validasi yang memvalidasi operasi `DELETE` terhadap namespace inti; jika requestor adalah service account otomatis tanpa token bypass darurat, tolak operasi tersebut seketika.

3. **Skenario 3**:
   Aplikasi mikroservis finansial telah menerapkan zero-downtime Canary Rollout. Namun, ketika proses pengalihan trafik mencapai 50%, sistem database mengalami kebuntuan (*Deadlock*) parah dan latensi API melonjak dari 40ms menjadi 8.000ms. Ditemukan bahwa Pod versi v1 (stable) dan v2 (canary) berjalan secara simultan membaca dan menulis pada tabel transaksi yang sama dengan cara penguncian (*locking mechanism*) baris database yang berbeda.
   * **Pertanyaan**: Bagaimana Anda merestrukturisasi strategi rekayasa software dan deployment pipeline untuk memecahkan persoalan ini tanpa downtime?
   * **Analisis & Resolusi**:
     1. *Penerapan Pola Expand-Contract*: Jangan pernah mengubah logika konkurensi/locking langsung pada tabel yang sama secara paralel antar dua versi.
     2. *Langkah Expand*: Tambahkan abstraksi layer baru (tabel staging baru atau kolom lock versi baru) yang kompatibel dengan versi v1 maupun v2. Versi v1 tetap menggunakan mekanisme lama, versi v2 membaca mekanisme lama dan menulis ke mekanisme baru.
     3. *Data Synchronization*: Gunakan asynchronous data reconciliation (misal: Change Data Capture / Debezium Kafka) untuk menjaga sinkronisasi dua arah selama periode rilis transisi.
     4. *Langkah Contract*: Setelah Canary mencapai 100% dan pod versi lama v1 seluruhnya dihancurkan, hapus table/locking pattern lama pada migration pipeline berikutnya.

---

### 16. Summary

Implementasi DevOps tingkat enterprise pada bab lanjutan ini mengubah paradigma automasi dasar menjadi sistem rekayasa perangkat lunak terintegrasi yang tangguh (*High Availability & Fault Tolerant*):

1. **Deklaratif & Otonom**: GitOps memindahkan kendali deployment dari pipeline eksternal yang rentan (*push model*) ke pengendali berbasis rekonsiliasi internal (*pull model*), menjamin auditabilitas kriptografis, deteksi konfigurasi drift instan, dan peniadaan kredensial berbahaya di server CI.
2. **Zero-Trust Telemetry Deployment**: Rilis aplikasi tidak lagi bergantung pada harapan atau pengecekan manual manusia. Menggunakan *Automated Canary Analysis*, Service Mesh, dan Prometheus, sistem secara dinamis menguji perangkat lunak langsung pada trafik produksi nyata, mengevaluasi latensi serta error rate secara mikroskopis, dan secara otonom melakukan isolasi atau rollback instan jika SLA sistem terancam.
3. **Keamanan Tanpa Kompromi**: Pengelolaan rahasia beralih dari Kubernetes Secrets statis menuju kredensial dinamis berumur pendek (*ephemeral dynamic secrets*) via HashiCorp Vault dengan isolasi memori lokal, dikombinasikan dengan pembuktian integritas supply-chain (Cosign, Distroless images, dan Pod Security Standards).

Dengan memadukan ketahanan level kernel/OS, observabilitas L7 terdistribusi, dan otomasi deklaratif, platform rekayasa mampu menjamin siklus rilis yang sangat cepat tanpa sedikit pun mengorbankan stabilitas, performa, dan integritas data enterprise.