# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Bab 06:** Materi Lanjutan

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Menganalisis dan Merancang** arsitektur *Continuous Delivery* berstandar enterprise yang menerapkan prinsip *Zero-Trust*, *Immutability*, dan *Automated Progressive Delivery* (Canary/Blue-Green).
2. **Mengimplementasikan** *Pipeline-as-Code* yang mengintegrasikan autentikasi nir-kredensial (*Keyless/OIDC*), *software supply chain security* (penandatanganan *image* via Sigstore Cosign, SBOM generation, *vulnerability gating*), dan manajemen rahasia dinamis (*dynamic secrets* via HashiCorp Vault).
3. **Membangun** mekanisme verifikasi otomatis pasca-rilis (*Automated Metric Verification/Canary Analysis*) menggunakan Prometheus Service Level Indicators (SLI) untuk memicu *automated self-healing/rollback* tanpa intervensi manual.
4. **Mengevaluasi dan Menangani** kegagalan sistem terdistribusi pada tahap deployment (seperti *split-brain deployments*, *cascading rollback failures*, *configuration drift*, dan *resource starvation*).

---

## 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut:
* **Linux System Internals:** Pemahaman mendalam tentang *cgroups*, *namespaces*, signal handling (`SIGTERM`, `SIGKILL`), systemd, dan analisis performa jaringan via CLI (`tcpdump`, `ss`, `ip`).
* **Container Fundamentals:** Memahami arsitektur OCI (*Open Container Initiative*), *multi-stage builds*, image layering, dan container runtimes (containerd/runc).
* **Git & Version Control:** Penguasaan *Trunk-Based Development*, Git commit signing (GPG/SSH), *rebasing*, dan struktur repositori terdistribusi.
* **Networking & Security:** Pemahaman tentang layer OSI, TCP handshake, TLS 1.3 termination, DNS resolution patterns pada container, serta konsep dasar IAM dan OIDC (*OpenID Connect*).

---

## 3. Concept & Internal Architecture

Dalam lanskap produksi modern, siklus hidup deployment tidak lagi sekadar memindahkan artefak biner ke server tujuan. Arsitektur produksi menuntut pemisahan mutlak antara **Control Plane** (orkestrator dan perencana release) dan **Data Plane** (runtime aplikasi), dengan penegakan integritas data rantai pasok software (*Software Supply Chain Security*).

```
+---------------------------------------------------------------------------------------------------+
|                                     ENTERPRISE CONTROL PLANE                                      |
|                                                                                                   |
|  +-------------------+       +----------------------+       +----------------------------------+  |
|  | GitHub Actions    | OIDC  | HashiCorp Vault      | Token | Cloud Container Registry (OCI)   |  |
|  | (Ephemeral Runner)|------>| (Dynamic Credentials)|------>| (Attested Image + Cosign + SBOM) |  |
|  +---------+---------+       +----------------------+       +-----------------+----------------+  |
|            |                                                                  ^                   |
|            | Git Commit Hash / Semantic Version Tag                           | Pull              |
|            v                                                                  | Image             |
|  +---------+---------+       +----------------------+                         |                   |
|  | GitOps Engine     | Sync  | Kyverno / OPA        | Verification            |                   |
|  | (Argo CD / Flux)  |------>| (Policy Enforcement) |-------------------------+                   |
|  +---------+---------+       +----------------------+                                             |
+------------|--------------------------------------------------------------------------------------+
             | Sync Manifests (Declarative State)
             v
+---------------------------------------------------------------------------------------------------+
|                                      KUBERNETES DATA PLANE                                        |
|                                                                                                   |
|           +-------------------------------------------------------------------+                   |
|           | Service Mesh / Ingress Controller (Envoy / Traefik / NGINX)       |                   |
|           +---------------------------------+---------------------------------+                   |
|                                             |                                                     |
|                      Traffic Splitting      | (e.g., 90% Baseline / 10% Canary)                   |
|                                             v                                                     |
|                   +-------------------------+-------------------------+                           |
|                   |                                                   |                           |
|                   v                                                   v                           |
|       +-----------------------+                           +-----------------------+               |
|       | Baseline / Stable Pod |                           | Canary Pod (Target)   |               |
|       | [v1.4.2]              |                           | [v1.5.0]              |               |
|       +-----------+-----------+                           +-----------+-----------+               |
|                   |                                                   |                           |
|                   +-------------------------+-------------------------+                           |
|                                             | Emits Latency, 5xx Rate, Saturation                 |
|                                             v                                                     |
|                            +---------------------------------+                                    |
|                            | Prometheus / OpenTelemetry      |                                    |
|                            +----------------+----------------+                                    |
|                                             | Pull SLI Metrics                                    |
|                                             v                                                     |
|                            +---------------------------------+                                    |
|                            | Progressive Delivery Controller |                                    |
|                            | (Argo Rollouts Analysis Engine) |                                    |
|                            +----------------+----------------+                                    |
|                                             |                                                     |
|                         Decision Gate       | Pass: Increment Traffic %                           |
|                                             +--------------------------------                     |
|                                             | Fail: Instant 0% Traffic & Rollback                 |
+---------------------------------------------------------------------------------------------------+
```

### Mekanisme Internal Komponen:

1. **Ephemeral OIDC Workflows:** Runner CI tidak menyimpan *static credentials* (API Key/Service Account token). Runner menggunakan token identitas sementara (JWT) dari penyedia Git untuk meminta token jangka pendek ke HashiCorp Vault atau Cloud Provider melalui pertukaran OIDC STS (*Security Token Service*).
2. **Cryptographic Attestation:** Build pipeline mengompilasi biner, menghasilkan OCI image, mengekstrak SBOM (*Software Bill of Materials* dengan Syft), dan menandatanganinya menggunakan Cosign dengan teknik *keyless signing* (berbasis Fulcio CA dan Rekor transparency log).
3. **Continuous Reconciliation Loop:** GitOps Controller (seperti Argo CD) membandingkan deklarasi Git (*Desired State*) dengan klaster k8s (*Actual State*). Jika terjadi perbedaan (*drift*), controller menerapkan rekonsiliasi otomatis sesuai kebijakan yang ditetapkan.
4. **Metric-Driven Progressive Delivery:** Controller deployment (misalnya Argo Rollouts) memanipulasi ingress atau service mesh API untuk membagi trafik HTTP secara presisi. Secara paralel, *Analysis Engine* mengeksekusi kueri PromQL secara berkala (misal: tiap 30 detik). Jika SLI melanggar batas ambang Service Level Objective (SLO), controller secara deterministik menurunkan bobot trafik canary menjadi 0% dan mengembalikan pod ke versi stabil.

---

## 4. Why & What

### Mengapa Paradigma Tradisional Gagal di Skala Enterprise?
* **Snowflake Servers & Drift:** Mengubah konfigurasi langsung di server melalui skrip ad-hoc (SSH/Bash) menyebabkan server kehilangan determinisme. Konfigurasi tidak dapat direproduksi saat bencana (*Disaster Recovery*).
* **Static Long-Lived Credentials:** Menyimpan *secret* jangka panjang di CI platform menciptakan target dengan dampak kompromi tinggi. Sekali token tersebut bocor, penyerang memiliki akses penuh ke klaster produksi.
* **All-at-Once (Big Bang) Deployments:** Mengganti 100% instans aplikasi secara simultan menyebabkan waktu henti layanan (*downtime*), membebani database dengan koneksi mendadak (*thundering herd problem*), dan jika terdapat bug fungsional, seluruh basis pengguna langsung terdampak.

### Apa Solusinya?
* **Arsitektur Imutabel & Deklaratif:** Segala konfigurasi disimpan dalam Git. Tidak ada akses SSH langsung ke sistem produksi. Node dan container bersifat sekali pakai (*ephemeral*).
* **Dynamic, Secretless CI/CD:** Kredensial di-generate secara just-in-time dengan masa berlaku hitungan menit via Vault atau Cloud IAM Workload Identity.
* **Progressive Delivery Terotomatisasi:** Rilis dilakukan secara bertahap (10% $\to$ 25% $\to$ 50% $\to$ 100%). Komputer, bukan manusia, yang menganalisis telemetri produksi (p99 latency, HTTP status rate) untuk memutuskan promosi atau rollback otomatis.

---

## 5. How (Workflow Detail)

Alur kerja enterprise terbagi ke dalam 6 tahapan yang tereksekusi tanpa cela:

```
[ Developer ]
      │ (git push signed commit)
      ▼
[ Git Repository (GitHub Enterprise) ]
      │ (trigger webhook)
      ▼
[ Stage 1: Build & Security Scanning ]
      ├─ Build Container (Multi-stage Distroless)
      ├─ Vulnerability Scan (Trivy: Fail on CRITICAL)
      ├─ Generate SBOM (Syft in CycloneDX/SPDX format)
      └─ Keyless Sign (Cosign + OIDC Issuer)
      │
      ▼
[ Stage 2: Artifact Publishing ]
      ├─ Push Image + Signatures + SBOM to Secure Registry
      └─ Dynamic Auth to Vault via OIDC
      │
      ▼
[ Stage 3: GitOps Declarative Update ]
      ├─ Update image tag in Kustomize/Helm Git repo
      └─ Automatic Pull Request or Direct Push to infra repo
      │
      ▼
[ Stage 4: Orchestration Reconciliation ]
      ├─ Argo CD detects revision change via Webhook
      ├─ Validates manifests against Cluster Admission Policies (Kyverno)
      └─ Triggers Progressive Delivery (Argo Rollouts)
      │
      ▼
[ Stage 5: Automated Progressive Verification ]
      ├─ Route 10% traffic to Canary pods
      ├─ Wait for Prometheus Metrics (Evaluation Period: 5m)
      ├─ PromQL Check 1: Error rate < 0.1% ?
      ├─ PromQL Check 2: p99 Latency < 200ms ?
      │
      ├───[ BREACH DETECTED ]───► Set Weight = 0% ──► Terminate Canary ──► Alert PagerDuty
      │
      └───[ ALL METRICS PASS ]──► Increment Weight to 50% ──► Repeat Analysis ──► 100%
```

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem: Sistem Penyelenggaraan Uji Coba Minuman Pabrik Skala Besar
Bayangkan sebuah pabrik minuman terpadu memproduksi formula rasa baru (*v2.0.0*):
* **Traditional Deployment:** Pabrik langsung menghentikan pasokan formula lama (*v1.0.0*) ke seluruh toko di negara tersebut dan langsung menjual formula baru. Jika formula baru tersebut menyebabkan sakit perut (bug sistem), seluruh negara keracunan bersamaan (total pemadaman sistem/outage).
* **Enterprise Canary Deployment:** Pabrik membuka satu keran khusus di satu toko kecil yang hanya melayani 5% konsumen terpilih. Di samping toko tersebut, laboratorium medis (Prometheus) memantau detak jantung dan reaksi konsumen (latensi dan error rate) secara seketika (*real-time*). Jika ditemukan 1 dari 100 konsumen mual, komputer pengontrol otomatis menutup keran khusus tersebut seketika (Rollback), membuang sisa batch (Pod Termination), dan hanya mengalirkan formula lama yang sudah terbukti aman.

### Diagram Arsitektur Jaringan Canary Deployment:

```
                          EXTERNAL INTERNET
                                 │
                                 ▼
                     [ Layer 4 Cloud Load Balancer ]
                                 │
                                 ▼
                     [ Ingress Controller (Envoy) ]
                                 │
                     +-----------┴-----------+
                     │ Traffic Router Module │
                     +-----------┬-----------+
                                 │
         ┌───────────────────────┴───────────────────────┐
         │ (Weight: 90%)                                 │ (Weight: 10%)
         ▼                                               ▼
[ Stable Kubernetes Service ]               [ Canary Kubernetes Service ]
         │                                               │
    +----+----+                                          │
    │         │                                          ▼
    ▼         ▼                                 +-----------------+
[ Pod A ] [ Pod B ]                             |  Canary Pod C   |
(App Image: v1.4.2)                             | (App Image: v1.5.0)
                                                +--------┬--------+
                                                         │
                                                         ▼
                                                Scraped by Prometheus
                                                Metric: http_request_duration_seconds
```

---

## 7. Simple Example & Practical Example

### A. Simple Example: Canary Routing Primitif Menggunakan NGINX Ingress
Konfigurasi sederhana ini membagi 10% trafik ke upstream baru berbasis header dan weight tanpa automasi metrik eksternal.

```yaml
# stable-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: core-api-stable
  namespace: production
  annotations:
    kubernetes.io/ingress.class: nginx
spec:
  rules:
  - host: api.enterprise.internal
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: core-api-stable-svc
            port:
              number: 80
---
# canary-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: core-api-canary
  namespace: production
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "10"
spec:
  rules:
  - host: api.enterprise.internal
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: core-api-canary-svc
            port:
              number: 80
```

---

### B. Practical Example (Production-Ready Architecture)

Berikut adalah konfigurasi kelas enterprise lengkap menggunakan **Argo Rollouts**, terintegrasi dengan **Prometheus Metric Analysis Template**, dan dilengkapi skrip **GitHub Actions OIDC Workflow**.

#### 1. Argo Rollouts Configuration (`rollout.yaml`)
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: payment-processor
  namespace: payment-system
  labels:
    app.kubernetes.io/name: payment-processor
    app.kubernetes.io/part-of: core-banking
spec:
  replicas: 10
  revisionHistoryLimit: 5
  selector:
    matchLabels:
      app: payment-processor
  strategy:
    canary:
      canaryService: payment-processor-canary
      stableService: payment-processor-stable
      trafficRouting:
        nginx:
          stableIngress: payment-processor-ingress
      analysis:
        templates:
          - templateName: telemetry-sli-check
        args:
          - name: service-name
            value: payment-processor-canary
      steps:
        - setWeight: 5
        - pause: { duration: 3m }
        - setWeight: 20
        - pause: { duration: 5m }
        - setWeight: 50
        - pause: { duration: 5m }
  template:
    metadata:
      labels:
        app: payment-processor
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: payment-api
          image: ghcr.io/enterprise-org/payment-processor:v2.1.0
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
              protocol: TCP
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              cpu: 2000m
              memory: 2Gi
          livenessProbe:
            httpGet:
              path: /healthz/live
              port: 8080
            initialDelaySeconds: 15
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /healthz/ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 2
            failureThreshold: 2
```

#### 2. Prometheus Metric Verification Template (`analysis-template.yaml`)
```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: telemetry-sli-check
  namespace: payment-system
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
            sum(rate(http_requests_total{service="{{args.service-name}}",status=~"2.."}[1m]))
            /
            sum(rate(http_requests_total{service="{{args.service-name}}"}[1m]))
    - name: p99-latency
      interval: 30s
      successCondition: result[0] <= 0.200
      failureLimit: 2
      provider:
        prometheus:
          address: http://prometheus-k8s.monitoring.svc.cluster.local:9090
          query: |
            histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service="{{args.service-name}}"}[1m])) by (le))
```

#### 3. Keyless GitHub Actions CI/CD with Cosign & OIDC (`.github/workflows/deploy.yaml`)
```yaml
name: Production Supply Chain Pipeline

on:
  push:
    tags:
      - 'v*.*.*'

permissions:
  id-token: write
  contents: read
  packages: write

jobs:
  build-and-sign:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Install Cosign
        uses: sigstore/cosign-installer@v3.5.0

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract Metadata (tags, labels)
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}

      - name: Build and Push Docker Image
        id: build-push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Sign Image with OIDC (Keyless)
        env:
          IMAGE_DIGEST: ${{ steps.build-push.outputs.digest }}
          IMAGE_NAME: ghcr.io/${{ github.repository }}
        run: |
          cosign sign --yes "${IMAGE_NAME}@${IMAGE_DIGEST}"
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Tier-1 Payment Gateway Outage Prevention
* **Organisasi:** Institusi Finansial FinTech dengan volume transaksi rata-rata \$120M per hari.
* **Insiden:** Pada kuartal sebelumnya, rilis rute microservice "Forex Settlement" mengalami kebocoran memori (*memory leak*) lambat yang hanya terpicu saat menerima traffic konkuren di atas 3.000 RPS. Model deployment lama (*Rolling Update*) menggantikan semua pod dalam 3 menit. Akibatnya, dalam waktu 12 menit klaster kehabisan RAM, memicu OOM-Killed massal pada pod node-worker, melumpuhkan seluruh transaksi selama 47 menit dengan taksiran kerugian komersial sebesar \$1.2M.

### Arsitektur Rekayasa Solusi:
Tim Core Infrastructure merombak rantai perilisan dengan menerapkan Canary Analysis terintegrasi:

```
[ Git Push Release Tag ]
           │
           ▼
[ OIDC Authenticated CI / Cosign Sign ]
           │
           ▼
[ Argo CD Sync Manifests ]
           │
           ▼
[ Canary Stage 1: 5% Routing ] 
           │
   Prometheus Monitoring (3 Menit)
   - Heap Alloc Rate (PromQL)
   - Connection Pool Exhaustion (PromQL)
   - Latency Percentile 99 (p99)
           │
      ┌────┴────────────────────────┐
      │ Kondisi:                    │ Kondisi:
      │ Memory growth rate abnormal │ Metric stabil
      ▼                             ▼
[ Argo Rollouts AUTO-ABORT ]   [ Increment Canary -> 20% ]
      │
      ├─ NGINX Canary Weight: 0%
      ├─ Evict Canary Pods
      └─ Trigger Alert: PagerDuty On-Call (P2)
         (Waktu pemulihan / MTTR: 18 Detik,
          Dampak User: 0.04% transaksi, 0% crash sistem)
```

Dengan mengotomatisasi evaluasi metrik, regresi alokasi memori terdeteksi pada *weight* 5%. Sistem secara otomatis memutus rute trafik canary dalam 18 detik tanpa campur tangan manusia (*zero engineer involvement*).

---

## 9. Trade-offs

| Aspek | Rolling Update | Blue/Green Deployment | Telemetry-Driven Canary |
| :--- | :--- | :--- | :--- |
| **Biaya Infrastruktur** | **Sangat Rendah:** Menggunakan kapasitas compute yang ada. | **Sangat Tinggi:** Membutuhkan duplikasi kapasitas klaster 100% (+100% CPU/RAM). | **Rendah - Sedang:** Hanya membutuhkan ekstra pod sesuai persentase canary (5-10%). |
| **Kecepatan Deployment** | Sedang. Bergantung pada `maxSurge` dan `maxUnavailable`. | **Sangat Cepat:** Pengalihan instan melalui switch router/DNS. | **Lambat:** Membutuhkan periode evaluasi bertingkat (*baking period*). |
| **Mitigasi Ledakan Dampak (Blast Radius)** | Buruk. Kerusakan menyebar bertahap ke seluruh pengguna. | Sedang. Seluruh pengguna dialihkan langsung ke versi baru. | **Sangat Unggul:** Hanya sebagian kecil sampel trafik terisolasi yang terdampak bug. |
| **Kompleksitas Operasional** | **Minimal:** Fitur bawaan k8s Deployment engine. | Menengah: Membutuhkan orkestrasi routing tingkat DNS atau Ingress. | **Tinggi:** Memerlukan konfigurasi Service Mesh/Ingress Controller + Prometheus SLI metrics yang akurat. |
| **Risiko Database Drift** | Tinggi: Versi lama dan baru membaca skema secara bersamaan. | Sangat Tinggi: Migrasi DB wajib kompatibel mundur (*backward compatible*) secara ketat. | Tinggi: Wajib mengadopsi pola *Expand/Contract* (*Parallel Change*) pada skema DB. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Metric Flapping Akibat Evaluasi Cold-Start
* **Gejala:** Rollout Canary selalu gagal secara otomatis (*aborted*) dalam 30 detik pertama rilis, padahal aplikasi sehat.
* **Akar Masalah:** Metrik p99 latency melonjak sesaat saat JVM/Node runtime melakukan JIT compilation atau saat pod memuat cache koneksi awal. Query PromQL yang mengukur interval terlalu pendek (misal: `[30s]`) langsung mendeteksi lonjakan sesaat tersebut sebagai breach.
* **Solusi/Remediasi:** Implementasikan parameter `initialDelay` pada step analisis metrik atau gunakan query yang mengecualikan jendela inisialisasi pod:
  ```yaml
  metrics:
    - name: p99-latency
      initialDelay: 1m # Berikan waktu warm-up sebelum evaluasi dimulai
      interval: 30s
  ```

### Mistake 2: Missing Termination Handling (`SIGTERM` Ignored)
* **Gejala:** Koneksi pengguna terputus tiba-tiba dengan error HTTP 502 Bad Gateway saat proses scale down canary atau rollback terjadi.
* **Akar Masalah:** Aplikasi di-containerized dengan node/python yang dijalankan tanpa wrapper atau PID 1 tidak merespons `SIGTERM`, sehingga kubelet langsung mengirim `SIGKILL` setelah grace period habis.
* **Solusi/Remediasi:** Tangani sinyal OS secara eksplisit di aplikasi atau tambahkan `preStop` hook sleep agar ingress berhenti mengirim trafik baru sebelum pod dimatikan:
  ```yaml
  lifecycle:
    preStop:
      exec:
        command: ["/bin/sh", "-c", "sleep 15"]
  ```

### Mistake 3: Dynamic Secrets Token Expiration During Long Execution
* **Gejala:** Pipeline CI/CD gagal di tengah jalan saat upload artefak/deploy dengan error `Vault Token Expired (403 Permission Denied)`.
* **Akar Masalah:** TTL (Time-To-Live) token Vault yang dihasilkan via OIDC di-set terlalu singkat (misal 5 menit), sementara proses build docker multi-arsitektur memakan waktu 8 menit.
* **Solusi/Remediasi:** Sesuaikan TTL token Vault secara presisi atau terapkan auto-renew background process di CI job runner.

---

## 11. Best Practices (Production Checklist)

Gunakan daftar periksa operasional ini sebelum menaikkan pipeline ke klaster produksi:

- [ ] **Kredensial:** Nol static token tersimpan di GitHub Secrets/GitLab CI. Semua autentikasi wajib OIDC federation.
- [ ] **Validasi Integritas:** Image OCI harus ditandatangani secara kriptografis (*Cosign keyless*) dan diverifikasi oleh klaster via Admission Controller (Kyverno/OPA Gatekeeper).
- [ ] **Rootless Container:** Aplikasi dilarang keras berjalan sebagai root (`runAsNonRoot: true`, `readOnlyRootFilesystem: true`, capabilities: `DROP ALL`).
- [ ] **Siklus Hidup Pod:** Definisikan probe secara eksplisit (`livenessProbe`, `readinessProbe`, dan `startupProbe`).
- [ ] **Alokasi Sumber Daya:** Setiap container wajib memiliki `resources.requests` dan `resources.limits` untuk CPU dan Memory agar tidak memicu *resource contention*.
- [ ] **Database Migration Safety:** Skema database harus mematuhi paradigma *Parallel Change* (tambahkan kolom/tabel baru lebih dahulu tanpa mengubah/menghapus kolom lama sebelum deployment tuntas).
- [ ] **Prometheus SLI Thresholds:** Pastikan margin metrik analisis memiliki batas toleransi kegagalan berturut-turut minimal `consecutiveFailures: 3` guna menghindari *false positive* akibat *network jitter*.
- [ ] **Graceful Termination:** Tetapkan `terminationGracePeriodSeconds` yang proporsional (default 30-60 detik) dan implementasikan penanganan `SIGTERM` di level runtime aplikasi.
- [ ] **Log Format:** Standardisasi stdout/stderr ke format JSON terstruktur yang memuat metadata trace konteks (TraceID, SpanID) untuk integrasi OpenTelemetry.
- [ ] **Reconciliation Drift Guard:** Konfigurasikan GitOps tool (Argo CD) dalam mode *Self-Healing* dan *Prune: true* untuk mencegah modifikasi manual di luar Git.

---

## 12. Hands-on Practice

Dalam praktikum ini, Anda akan membangun pipeline simulasi Canary Analysis secara lokal menggunakan K3d (k3s dalam Docker) dan mengevaluasi status rollback otomatis saat terjadi degradasi latensi.

### Persiapan Direktori:
Simpan semua file praktikum ini di: `hands-on/m02/`

```bash
mkdir -p hands-on/m02 && cd hands-on/m02
```

### Langkah 1: Inisialisasi Klaster K3d Lokal dengan Port Forward Ingress
```bash
cat <<EOF > cluster-config.yaml
apiVersion: k3d.io/v1alpha5
kind: Simple
metadata:
  name: canary-lab
servers: 1
agents: 2
ports:
  - port: 8080:80
    nodeFilters:
      - loadbalancer
EOF

k3d cluster create --config cluster-config.yaml
```

### Langkah 2: Install Argo Rollouts Controller
```bash
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml
```

### Langkah 3: Deploy Mock Prometheus Server
```bash
cat <<EOF > mock-prometheus.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus-mock
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: mock-api
        image: hashicorp/http-echo:latest
        args:
          # Simulasi return nilai p99 latency 0.350 detik (melebihi SLO 0.200 detik)
          - "-text={\"status\":\"success\",\"data\":{\"resultType\":\"vector\",\"result\":[{\"metric\":{},\"value\":[1600000000,\"0.350\"]}]}}"
          - "-listen=:9090"
        ports:
        - containerPort: 9090
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus-mock
  namespace: default
spec:
  ports:
  - port: 9090
    targetPort: 9090
  selector:
    app: prometheus
EOF

kubectl apply -f mock-prometheus.yaml
```

### Langkah 4: Terapkan AnalysisTemplate dan Rollout Manifest
```bash
cat <<EOF > canary-system.yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: latency-gate
  namespace: default
spec:
  metrics:
  - name: p99-response-time
    interval: 10s
    count: 3
    successCondition: result[0] <= 0.200
    failureLimit: 1
    provider:
      prometheus:
        address: http://prometheus-mock.default.svc.cluster.local:9090
        query: "histogram_quantile_p99"
---
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: core-api-service
  namespace: default
spec:
  replicas: 4
  strategy:
    canary:
      analysis:
        templates:
        - templateName: latency-gate
      steps:
      - setWeight: 25
      - pause: { duration: 30s }
  selector:
    matchLabels:
      app: core-api
  template:
    metadata:
      labels:
        app: core-api
    spec:
      containers:
      - name: api
        image: nginx:alpine
        ports:
        - containerPort: 80
EOF

kubectl apply -f canary-system.yaml
```

### Langkah 5: Evaluasi Status Rollout & Rollback Otomatis
Jalankan command watcher Argo Rollouts untuk melihat controller secara otomatis menggagalkan release karena latency 0.350s melanggar SLO $\le$ 0.200s:
```bash
# Unduh plugin kubectl argo-rollouts jika belum tersedia
curl -LO https://github.com/argoproj/argo-rollouts/releases/latest/download/kubectl-argo-rollouts-linux-amd64
chmod +x kubectl-argo-rollouts-linux-amd64
sudo mv kubectl-argo-rollouts-linux-amd64 /usr/local/bin/kubectl-argo-rollouts

# Pantau eksekusi rollout
kubectl argo-rollouts get rollout core-api-service --watch
```

**Output Terminal yang Diharapkan:**
```text
NAME                                         KIND         STATUS        AGE  INFO
⟳ core-api-service                           Rollout      Degraded      1m   
├──# revision:1                                                               
│  └──○ core-api-service-745585b796          ReplicaSet   Default       1m   4 desired, 4 updated, 4 total, 4 available
└──# revision:2 (Canary failed)                                               
   ├──× core-api-service-58f6bb69cd          ReplicaSet   Canary        30s  0 desired, 0 updated, 0 total, 0 available
   └──α core-api-service-58f6bb69cd-1        AnalysisRun  Failed        20s  failed:1
```

*Analisis:* Pod revisi 2 otomatis ditarik mundur (`Failed/Degraded`) setelah query Prometheus mengembalikan angka `0.350` yang melanggar `successCondition: result[0] <= 0.200`.

---

## 13. Exercise

### Level Easy
Ubah konfigurasi file `rollout.yaml` pada bagian *Practical Example* agar canary membagi trafik menjadi 4 fase bertahap: 10% (selama 2 menit), 25% (selama 3 menit), 50% (selama 5 menit), lalu promosi penuh 100%. Tuliskan struktur deklaratif `steps`-nya.

### Level Medium
Buat sebuah file deklarasi `AnalysisTemplate` Prometheus yang memantau Service Level Indicator (SLI) untuk persentase crash/restart pod via metrik k8s cAdvisor:
* Nama Metrik: `container-restart-rate`
* Ambang batas: Rata-rata restart rate container dalam namespace `production` tidak boleh lebih besar dari `0` dalam kurun waktu 5 menit.

### Level Hard
Rancang arsitektur pipeline GitHub Actions yang mengonstruksi build multi-stage Docker untuk microservice Golang, memproduksi SBOM dengan format CycloneDX JSON via `syft`, memindai SBOM via `grype`, mengunggah image ke GHCR, dan menandatangani image beserta file attestasi SBOM menggunakan `cosign` dengan metode autentikasi OIDC GitHub Actions tanpa file kunci private (`keyless`).

---

## 14. Challenge

### Studi Kasus: Chaos Engineering Injected Deployment Degradation
Sebuah bank digital meluncurkan microservice pembayaran lintas batas terbaru. Namun, tim QA menginjeksi sebuah latency spike acak yang hanya muncul jika microservice memproses transaksi pada database replica sekunder (terjadi split-second network drop).

* **Tantangan:**
  1. Rancang arsitektur pipeline terpadu yang memadukan **Chaos Mesh** atau **LitmusChaos** dalam siklus Progressive Delivery.
  2. Susun manifes `AnalysisTemplate` kustom yang menghitung kombinasi dua metrik kritis secara simultan (*multi-vector verification*):
     * Metrik A: Latency 99th percentile (Prometheus PromQL) wajib $\le$ 150ms.
     * Metrik B: Error log severity count ("CRITICAL" atau "FATAL") dari Log Engine (misal: ElasticSearch/Loki API) wajib bernilai `0` selama pengujian berlangsung.
  3. Konfigurasikan skema failure handling sehingga jika salah satu metrik gagal, sistem mengeksekusi webhook ke bot Slack Engineering, mengisolasi pod canary ke namespace forensik terisolasi (bukan langsung dihapus) untuk proses *post-mortem triage* memory dump, baru kemudian me-reset traffic ke stable pod.

*Deliverable yang diharapkan:* Seluruh set manifes Kubernetes deklaratif beserta arsitektur diagram interaksinya tanpa panduan parsial.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)

1. **Apa perbedaan mendasar antara model deployment Rolling Update konvensional dengan Canary Deployment?**
   * A. Rolling Update membutuhkan Service Mesh, Canary tidak.
   * B. Rolling update membatalkan deployment otomatis secara pintar jika ada error HTTP 500, Canary tidak.
   * C. Rolling Update menggantikan seluruh instance secara bergantian tanpa validasi metrik telemetri tingkat lanjut; Canary mengisolasi sebagian kecil trafik pengguna ke versi baru dan mengukur SLI/SLO sebelum promosi.
   * D. Canary deployment membutuhkan downtime total, Rolling Update zero-downtime.

2. **Mengapa penggunaan *Long-Lived Static Credentials* (misal: AWS Access Key / Service Account JSON) di dalam CI/CD runner dilarang keras pada standar keamanan modern?**
   * A. Karena membuat proses eksekusi pipeline menjadi lambat.
   * B. Karena memperbesar risiko kompromi jangka panjang jika credential bocor dari build logs atau runner terinfeksi (*lateral movement*).
   * C. Karena API provider cloud membatasi durasi token statis maksimal 1 hari.
   * D. Karena Kubernetes tidak menerima static credentials.

3. **Komponen apa dalam Sigstore Cosign yang memungkinkan penandatanganan container image secara *keyless*?**
   * A. GPG Private Key dan YubiKey.
   * B. OpenID Connect (OIDC) identity provider, Fulcio (Certificate Authority), dan Rekor (Transparency Log).
   * C. Docker Content Trust dan Notary v1.
   * D. Kubernetes Secrets Controller.

4. **Apa fungsi utama dari implementasi Software Bill of Materials (SBOM) dalam supply chain security pipeline?**
   * A. Mengurangi ukuran image Docker secara drastis.
   * B. Menghasilkan daftar inventaris terstruktur seluruh dependency pustaka, lisensi, dan modul biner dari software untuk deteksi dini kerentanan (CVE).
   * C. Mempercepat proses compile code pada ephemeral runner.
   * D. Mengamankan runtime container dari privilege escalation.

5. **Apa yang terjadi secara default jika sebuah pod menerima sinyal kernel `SIGTERM` di lingkungan Kubernetes?**
   * A. Pod langsung dimatikan paksa dalam 0 detik tanpa menyelesaikan transaksi terbuka.
   * B. Pod dialihkan ke status crash-loop.
   * C. Proses aplikasi diberikan waktu tenggang (*termination grace period*) untuk menutup koneksi database, membersihkan state, dan menyelesaikan request aktif sebelum dimatikan paksa oleh `SIGKILL`.
   * D. Pod otomatis di-clone ke node lain.

---

### Bagian 2: Intermediate (5 Soal)

6. **Dalam integrasi Prometheus Analysis pada Argo Rollouts, apa fungsi konfigurasi parameter `failureLimit: 3`?**
   * A. Menjalankan query Prometheus sebanyak 3 kali secara bersamaan.
   * B. Mentoleransi kegagalan evaluasi query metrik maksimal 3 kali sebelum Rollout Controller memutuskan untuk melakukan *abort* dan *rollback*.
   * C. Menunggu selama 3 menit sebelum memulai evaluasi metrik pertama.
   * D. Merestart pod canary sebanyak 3 kali jika terjadi crash.

7. **Bagaimana arsitektur GitOps (misal: Argo CD) mengatasi masalah "Configuration Drift" pada klaster Kubernetes?**
   * A. Mematikan akses API server klaster secara permanen.
   * B. Mengirim email ke administrator setiap kali terjadi perubahan.
   * C. Secara periodik membandingkan *Desired State* (Git) dengan *Live State* (Klaster) dan secara otomatis menimpa kembali perubahan manual jika fitur *Auto-Sync/Self-Healing* diaktifkan.
   * D. Membuat branch baru di Git saat pod diubah secara manual via `kubectl edit`.

8. **Saat melakukan traffic splitting menggunakan NGINX Ingress Controller untuk Canary release, mengapa metrik latensi p99 awal sering kali menunjukkan lonjakan palsu (*false positive*)?**
   * A. NGINX Ingress Controller tidak mendukung penanganan protokol HTTP/2.
   * B. Pod aplikasi Canary mengalami fase inisialisasi runtime (*cold start*), seperti kompilasi Just-In-Time (JIT) dan koneksi *pooling* database awal.
   * C. Prometheus gagal mengidentifikasi port pod secara acak.
   * D. Memory node worker langsung penuh saat canary aktif.

9. **Jika sebuah aplikasi memiliki migrasi database yang menghapus kolom lama (*DROP COLUMN*), strategi apa yang WAJIB diterapkan agar Canary Deployment tidak mengalami kegagalan sistem?**
   * A. Menghapus database dan melakukan restore backup data terbaru.
   * B. Menerapkan pola *Expand and Contract* (Parallel Change): jangan hapus kolom lama secara langsung; buat kolom baru, sinkronisasi data antar kolom, rilis canary hingga 100%, baru buat release terpisah untuk menghapus kolom lama.
   * C. Melakukan deployment pada jam operasional terendah saja.
   * D. Menonaktifkan read/write ke database selama 1 jam.

10. **Apa implikasi konfigurasi `readOnlyRootFilesystem: true` pada konteks keamanan container runtime aplikasi?**
    * A. Pod tidak dapat menerima request dari jaringan internet.
    * B. Hacker atau malware yang berhasil mengeksploitasi remote code execution (RCE) tidak dapat mengunduh dan mengeksekusi payload biner berbahaya ke disk lokal container.
    * C. Memory pod tidak dapat bertambah melampaui batas requests.
    * D. Container dilarang membaca data ConfigMap.

---

### Bagian 3: Production Scenario Analysis (3 Skenario)

11. **Skenario Kasus 1: The Cascading Connection Spike**
    * *Kasus:* Anda meluncurkan canary deployment untuk service API dengan bobot 10%. Setelah 2 menit, database backend PostgreSQL mengalami lonjakan koneksi drastis yang memicu `FATAL: remaining connection slots are reserved for non-replication superuser connections`. Baik pod stable maupun canary mulai mengembalikan HTTP 500.
    * *Analisis Diagnostik:* Apa akar masalah operasional yang terjadi dan apa langkah remediasi pada level konfigurasi arsitektur?
      * A. Ingress controller rusak; restart ingress controller segera.
      * B. Tiap pod canary menginisialisasi ukuran connection pool database maksimal secara independen saat booting tanpa memperhitungkan jumlah total replica gabungan pod stable + canary; Solusi: Terapkan connection pooling terpusat di sisi infrastruktur (seperti PgBouncer) dan batasi `max_connections` per pod container.
      * C. Prometheus menarik scrape metrics terlalu sering; ubah interval scrape ke 1 jam.
      * D. Kapasitas RAM pod canary terlalu kecil; naikkan memory limit 10 kali lipat.

12. **Skenario Kasus 2: The Failed Keyless Attestation Gate**
    * *Kasus:* Tim platform security menerapkan policy Kyverno di klaster k8s produksi: `check-image-signatures`. Semua manifest pod yang menggunakan image tanpa validasi penandatanganan Cosign akan ditolak oleh *Admission Webhook*. Pada rilis v3.4.0, pipeline build GitHub Actions berhasil sukses, namun Argo CD gagal melakukan sync dan mengeluarkan log error: `admission webhook "validate.kyverno.svc" denied the request: image verification failed: no valid signatures found`.
    * *Analisis Diagnostik:* Di mana titik kegagalan pada rantai supply chain pipeline tersebut?
      * A. Klaster kehabisan CPU sehingga webhook lambat merespons.
      * B. Docker image belum di-push ke registry publik.
      * C. Pipeline menandatangani image menggunakan *Image Tag* yang bersifat *mutable* alih-alih menggunakan *Immutable Digest (SHA256)*, atau token JWT GitHub OIDC mengalami invalidasi subjek issuer saat memvalidasi sertifikat di Fulcio/Rekor transparency log.
      * D. Node worker k8s tidak memiliki koneksi SSH ke GitHub.

13. **Skenario Kasus 3: Flapping Rollout Triggered by OpenTelemetry Discrepancy**
    * *Kasus:* Sebuah Canary Rollout dikonfigurasi untuk mengevaluasi p99 error rate menggunakan PromQL. Setiap kali deployment dijalankan, status canary selalu berfluktuasi: 1 menit pertama status PASS, 1 menit berikutnya FAILED, lalu rollback terpicu. Ketika tim memeriksa log aplikasi secara manual, tidak ditemukan satu pun request berstatus HTTP 5xx.
    * *Analisis Diagnostik:* Mengapa evaluasi PromQL mengembalikan metrik kegagalan palsu padahal log aplikasi bersih?
      * A. Label selector metrik PromQL pada template evaluasi tidak menyertakan filter service pod yang spesifik (`app: my-service-canary`), sehingga metrik secara tidak sengaja menggabungkan traffic dari health probe Kubernetes liveness/readiness yang mengembalikan kode status 404/503 saat inisialisasi awal.
      * B. Service Mesh memutus seluruh koneksi setiap 30 detik.
      * C. Prometheus tidak mendukung format log JSON.
      * D. Versi kernel Linux node worker terlalu usang untuk memproses histogram.

---

### Kunci Jawaban Evaluasi:

#### Bagian 1: Basic
1. **C** — Canary deployment secara deterministik memvalidasi metrik telemetri pada subset traffic terisolasi sebelum memutuskan ekspansi rilis.
2. **B** — Kredensial jangka panjang memiliki risiko eskalasi hak akses (*blast radius*) masif jika bocor dari pipeline environment atau log runner.
3. **B** — Pendekatan keyless Sigstore mengandalkan pertukaran identitas OIDC, penerbitan sertifikat singkat oleh Fulcio CA, dan pencatatan audit immutable di Rekor transparency log.
4. **B** — SBOM mengkatalogkan seluruh pustaka secara detail untuk mendeteksi kerentanan supply chain (CVE).
5. **C** — `SIGTERM` memberi kesempatan aplikasi melakukan graceful shutdown sebelum dipaksa mati oleh `SIGKILL`.

#### Bagian 2: Intermediate
6. **B** — `failureLimit: 3` mengizinkan metrik melanggar SLO sebanyak 3 kali berturut-turut untuk mengakomodasi jitter jaringan sebelum melakukan pembatalan rilis.
7. **C** — GitOps engine secara deterministik merekonsiliasi perbedaan antara live cluster dengan Git repository secara otomatis (*self-healing*).
8. **B** — Fenomena cold start runtime menyebabkan latency melonjak di awal booting sebelum JIT compiler dan connection pooling stabil.
9. **B** — Pola Expand/Contract memastikan skema database tetap kompatibel baik untuk pod versi lama maupun versi baru yang berjalan berdampingan selama fase canary.
10. **B** — Menolak hak tulis filesystem container secara drastis memitigasi eksekusi malware/exploit biner baru di root folder runtime.

#### Bagian 3: Production Scenario Analysis
11. **B** — Penambahan pod tanpa batas connection pool database independen akan memicu saturasi connection exhaustion. Solusi: Gunakan PgBouncer sebagai connection proxy layer.
12. **C** — Verifikasi signature cryptographics wajib mengikat pada *Digest SHA256* immutable; jika tag ditimpa atau klaim OIDC mismatch, admission controller wajib menolak admission request.
13. **A** — Query telemetri yang tidak presisi sering kali mengagregasikan kegagalan dari health check endpoint liveness/readiness alih-alih mengukur real-user business traffic.

---

## 16. Summary

Implementasi continuous delivery di tingkat enterprise memerlukan pergeseran paradigma dari *manual script execution* menjadi **Automated, Policy-Driven Progressive Delivery**.

Tiga pilar fundamental yang menopang arsitektur ini adalah:
1. **Supply Chain Integrity (Zero-Trust):** Membangun biner yang dapat diaudit, terikat identitas ephemeral OIDC, ditandatangani via Cosign, dan dieksekusi dalam runtime yang diperketat (*read-only, non-root*).
2. **Declarative Reconciliation (GitOps):** Menghilangkan *snowflake servers* dan *human drift* dengan menjadikan repositori Git sebagai *Single Source of Truth* absolut untuk seluruh status infrastruktur.
3. **Telemetry-Driven Decisions:** Mengeliminasi proses release berbasis asumsi. Metrik produksi (p99 latency, failure percentage) bertindak sebagai gerbang otomasi (*automated circuit breakers*) yang secara proaktif melindungi stabilitas sistem, membatasi dampak insiden (*blast radius*), dan memicu *self-healing rollback* dalam hitungan detik.