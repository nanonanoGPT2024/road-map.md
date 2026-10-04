# Kurikulum Rekayasa DevOps Enterprise
## Kategori: 01-Core-Foundations | Bab 07: Materi Lanjutan
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis dan Merancang** arsitektur delivery sistem tingkat enterprise dengan pendekatan *Immutable Infrastructure* dan pola *Zero-Downtime Deployment* (Canary & Blue/Green).
2. **Mengimplementasikan** orkestrasi beban kerja produksi menggunakan kontrol deklaratif, *Pod Disruption Budgets* (PDB), *Topology Spread Constraints*, serta *Health Probes* deterministik pada Kubernetes.
3. **Mengotomatisasi** *Progressive Delivery* terintegrasi dengan analisis metrik berbasis SLA/SLO secara *closed-loop* melalui GitOps.
4. **Mengevaluasi dan Memitigasi** titik kegagalan tunggal (*Single Point of Failure*), degradasi kaskade (*cascading failures*), dan fenomena *thundering herd* melalui penerapan *Rate Limiting*, *Circuit Breaking*, dan isolasi *Blast Radius*.
5. **Menjalankan** audit keandalan sistem produksi berdasarkan *Production Readiness Review* (PRR) lintas 5 pilar arsitektur cloud.

---

### 2. Prerequisite
Peserta wajib memiliki pemahaman operasional dan penguasaan praktis pada domain berikut:
- **Sistem Operasi & Jaringan**: Linux Internals (namespaces, cgroups, signal handling SIGTERM/SIGKILL), TCP/IP handshake, TLS termination, DNS resolution latency.
- **Containerization**: OCI runtime specs, multi-stage builds, rootless container security boundary.
- **Dasar CI/CD**: Pipeline linier (lint, build, unit test, artifact push), semantic versioning, Git branching models (Trunk-based vs GitFlow).
- **Infrastruktur Dasar**: Perintah dasar Kubernetes (`kubectl apply`, `get`, `describe`, `logs`), Terraform/OpenTofu syntax primitif, konfigurasi reverse proxy (Nginx/HAProxy).

---

### 3. Concept & Internal Architecture

Dalam lanskap enterprise, transisi dari pipeline DevOps pemula menuju arsitektur produksi berpusat pada pergeseran paradigma dari *Imperative Manual Operations* menuju **Autonomous Declarative Reconciliation**.

```
+---------------------------------------------------------------------------------------+
|                               CONTROL PLANE (ETCD + KUBE-APISERVER)                   |
|  Desired State: [Replicas: 5, Image: v2.1.0, MaxUnavailable: 0, Latency SLO: <100ms]  |
+-------------------------------------------+-------------------------------------------+
                                            |
                                            | Watch & Reconcile Loop
                                            v
+---------------------------------------------------------------------------------------+
|                                  DATA PLANE (WORKER NODES)                            |
|                                                                                       |
|   +-----------------------+   +-----------------------+   +-----------------------+   |
|   | Pod v1 (Draining...)  |   | Pod v2 (Serving...)   |   | Pod v2 (Serving...)   |   |
|   | Traffic Weight: 0%    |   | Traffic Weight: 50%   |   | Traffic Weight: 50%   |   |
|   +-----------------------+   +-----------------------+   +-----------------------+   |
|               ^                           ^                           ^               |
|               |                           |                           |               |
+---------------+---------------------------+---------------------------+---------------+
                                            ^
                                            | (eBPF / IPVS Routing)
                                            |
                                 [ Ingress Controller / Mesh ]
                                 (Envoy Gateway - Traffic Split)
```

#### Komponen Internal Inti:
1. **Reconciliation Loop Engine**: Kontroler internal terus-menerus membandingkan *Desired State* (didefinisikan via VCS/Git) dengan *Observed State* (keadaan runtime aktual). Selisih status memicu mutasi status via API Server untuk konvergensi otomatis.
2. **Graceful Degradation & Termination Lifecycle**: 
   - Penerimaan sinyal `SIGTERM` oleh proses aplikasi.
   - Deregistrasi endpoint secara asinkron dari Service Mesh/Ingress Controller.
   - Pemanfaatan `preStop` hook untuk menahan penghentian proses sebelum penyesuaian tabel routing selesai disinkronkan ke seluruh node.
3. **Topology-Aware Scheduling**: Algoritma penjadwalan pod yang mendistribusikan beban kerja melintasi *failure domains* (region, availability zone, host rack) secara matematis guna mengeliminasi korelasi kegagalan infrastruktur fisik.
4. **Automated Rollback Loop**: Sistem telemetri (*Prometheus engine*) mengevaluasi metrik SLI (*Service Level Indicator*) secara real-time. Jika batas ambang SLO (*Service Level Objective*) terlanggar selama deployment, kontroler delivery secara otonom membatalkan alur rilis tanpa intervensi manusia.

---

### 4. Why & What

#### Why: Keterbatasan Arsitektur Tradisional
- **Downtime Tersembunyi**: *Rolling updates* standar sering memicu HTTP 502/504 errors jika container baru belum siap melayani traffic atau proses lama dihentikan sebelum koneksi *in-flight* selesai.
- **Blast Radius Tidak Terkontrol**: Rilis biner langsung ke 100% armada server mengekspos seluruh basis pengguna terhadap *latent runtime bugs*.
- **Config Drift**: Perubahan manual pada cluster produksi mengakibatkan hilangnya reproduktibilitas infrastruktur.

#### What: Karakteristik Arsitektur Produksi Tingkat Enterprise
- **Zero-Trust Network Architecture**: Tidak ada trust implisit antar-service; autentikasi mTLS mutual diwajibkan via *service-to-service communication*.
- **Resilience Engineering**: Sistem dirancang untuk pulih secara mandiri (*self-healing*) dari kegagalan infrastruktur dasar, termasuk kegagalan satu Availability Zone (AZ) penuh.
- **Immutable Infrastructure**: Server dan container tidak pernah dimodifikasi saat runtime. Pembaruan dilakukan dengan membuat resource baru dan menghancurkan resource lama.

---

### 5. How (Workflow Detail)

Alur kerja implementasi *Progressive Delivery* tingkat lanjut:

1. **Commit & Attestation Phase**:
   - Pengembang melakukan `git push` ke trunk repository.
   - Pipeline CI memvalidasi kode, menjalankan SAST, menghasilkan *Software Bill of Materials* (SBOM), dan menandatangani OCI image menggunakan *Cosign* (Sigstore).
2. **GitOps State Declaration**:
   - Pipeline memperbarui manifest deklaratif pada repository konfigurasi target.
   - ArgoCD mendeteksi perubahan commit dan memverifikasi kriptografi integritas manifest.
3. **Canary Orchestration Phase**:
   - Argo Rollouts membuat replica set baru (`canary`) berdampingan dengan versi `stable`.
   - Ingress controller (Envoy) membagi traffic masuk: 5% ke Canary, 95% ke Stable.
4. **Telemetry Analysis Loop**:
   - *Prometheus* mengukur *Error Rate* (HTTP status code 5xx) dan *P99 Latency* pada armada Canary selama periode analisis (5 menit).
   - Analisis sukses: Bobot traffic dinaikkan secara bertahap (10% -> 25% -> 50% -> 100%).
   - Analisis gagal: Algoritma memicu *abort condition*, mengembalikan bobot routing 100% ke `stable`, dan mematikan pod canary seketika.
5. **Final Cutover & Garbage Collection**:
   - Armada pod versi lama memasuki siklus *graceful termination* setelah traffic 100% dialihkan ke versi baru.

---

### 6. Analogy & Diagram ASCII

#### Analogi Rekayasa Sipil: Sistem Distribusi Air Kota
Bayangkan sistem pipa air utama kota metropolitan. Anda tidak bisa mematikan air ke 2 juta warga untuk mengganti material pipa yang usang (Pola Tradisional = Downtime). Anda juga tidak bisa langsung memompa air dari instalasi pengolahan baru dengan debit penuh karena jika air tersebut tercemar, seluruh kota keracunan (Rolling Update tanpa Observabilitas = Blast Radius 100%).

Arsitektur produksi modern bekerja seperti katup bypass otomatis yang terpasang paralel:
1. Katup membuka 1% aliran air baru ke laboratorium uji kualitas (*Canary Analysis*).
2. Sensor menguji pH dan kontaminan secara terus-menerus (*Prometheus SLI/SLO*).
3. Jika sensor mendeteksi anomali sekecil apa pun, katup darurat otomatis tertutup dalam hitungan milidetik (*Rollback Loop*).
4. Jika air terbukti steril, katup dibuka bertahap hingga pipa lama dinonaktifkan tanpa penurunan tekanan air di rumah warga (*Zero Downtime*).

#### Diagram Alur Produksi:

```
[ Developer ] ---> [ Git Repository ]
                         |
                 (Webhook Trigger)
                         v
              [ Enterprise CI Pipeline ]
              - Unit / Integration Test
              - SAST / Container Vulnerability Scan
              - OCI Build & Cosign Sign
                         |
                         v
              [ Artifact Registry (Harbor) ]
                         |
    +--------------------+--------------------+
    | (State Mutation via Git PR)             |
    v                                         v
[ GitOps Repo ]                        [ ArgoCD Operator ]
                                              |
                                     (Sync Reconciliation)
                                              v
                              +-------------------------------+
                              |    Kubernetes Cluster (EKS)   |
                              |                               |
                              |   +-----------------------+   |
                              |   |    Argo Rollouts      |   |
                              |   |      Controller       |   |
                              |   +-----------+-----------+   |
                              |               |               |
                              |       (Traffic Split)         |
                              |               v               |
[ User Traffic ] ------------>|-----> [ Ingress Controller ]  |
                              |             /    \            |
                              |       95%  /      \  5%       |
                              |           v        v          |
                              |     [Stable]      [Canary]    |
                              |        |              |       |
                              +--------+--------------+-------+
                                       |              |
                                  (Telemetri)    (Telemetri)
                                       \              /
                                        v            v
                                   [ Prometheus / Datadog ]
                                              |
                                     (SLO Validation Engine)
                                              |
                              (Healthy: Promote | Unhealthy: Abort)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Hardened OCI Dockerfile
File: `src/Dockerfile`
Penerapan multi-stage, non-root user, dan penanganan sinyal UNIX yang presisi.

```dockerfile
# Stage 1: Build binary
FROM golang:1.22-alpine AS builder

WORKDIR /app

# Menghindari re-download dependensi pada layer build
COPY go.mod go.sum ./
RUN go mod download

COPY . .

# Static compilation tanpa dependensi CGO, strip binary debug info
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-w -s" -o /bin/api-server .

# Stage 2: Distroless Minimal Runtime Environment
FROM gcr.io/distroless/static:nonroot

WORKDIR /
COPY --from=builder /bin/api-server /api-server

# Non-root UID untuk mencegah container breakout privilege escalation
USER 65532:65532

EXPOSE 8080

ENTRYPOINT ["/api-server"]
```

#### B. Practical Example: Production-Ready Workload & Rollout Engine

File: `deploy/production-rollout.yaml`
Implementasi Kubernetes Manifest komprehensif mencakup *Argo Rollout*, *AnalysisTemplate*, *PodDisruptionBudget*, dan *TopologySpreadConstraints*.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate-check
  namespace: production
spec:
  metrics:
  - name: success-rate
    interval: 30s
    successCondition: result[0] >= 0.9995
    failureLimit: 3
    provider:
      prometheus:
        address: http://prometheus-k8s.monitoring.svc.cluster.local:9090
        query: |
          sum(rate(http_requests_total{app="core-api",status!~"5.*"}[1m]))
          /
          sum(rate(http_requests_total{app="core-api"}[1m]))
---
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: core-api-rollout
  namespace: production
  labels:
    app: core-api
spec:
  replicas: 10
  strategy:
    canary:
      analysis:
        templates:
        - templateName: success-rate-check
        args:
        - name: service-name
          value: core-api
      steps:
      - setWeight: 5
      - pause: { duration: 3m }
      - setWeight: 20
      - pause: { duration: 5m }
      - setWeight: 50
      - pause: { duration: 5m }
  revisionHistoryLimit: 5
  selector:
    matchLabels:
      app: core-api
  template:
    metadata:
      labels:
        app: core-api
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values: ["core-api"]
              topologyKey: kubernetes.io/hostname
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: DoNotSchedule
        labelSelector:
          matchLabels:
            app: core-api
      terminationGracePeriodSeconds: 60
      containers:
      - name: server
        image: internal-registry.enterprise.io/apps/core-api:v2.1.0@sha256:d8c544d93b3f2b6b5d9be253d865c3de0a4547900b65f0e9b9ff1a8c62c2f42a
        command: ["/api-server"]
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sleep", "15"]
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "2000m"
            memory: "2Gi"
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop: ["ALL"]
        ports:
        - containerPort: 8080
          name: http
        startupProbe:
          httpGet:
            path: /healthz/startup
            port: 8080
          failureThreshold: 30
          periodSeconds: 2
        livenessProbe:
          httpGet:
            path: /healthz/liveness
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 2
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /healthz/readiness
            port: 8080
          periodSeconds: 5
          timeoutSeconds: 2
          failureThreshold: 2
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: core-api-pdb
  namespace: production
spec:
  minAvailable: 80%
  selector:
    matchLabels:
      app: core-api
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Entitas**: Platform Transaksi Finansial (Sistem Pemrosesan Pembayaran Dompet Digital).
- **Skala Beban**: 18.000 Transaksi Per Detik (TPS) pada jam sibuk; Basis armada backend terdiri dari 450 worker nodes pada Amazon EKS.
- **Kondisi Insiden Lalu**: Selama rilis patch database-connection pooling, *standard rolling update* menyebabkan lonjakan koneksi instan ke PostgreSQL Aurora (*thundering herd*), mengakibatkan kehabisan koneksi pool database secara global, lonjakan P99 latency dari 45ms ke 12.000ms, dan penurunan pendapatan senilai jutaan dolar dalam 8 menit *outage*.

#### Arsitektur Transformasi & Remediasi
1. **Pemisahan Traffic Lapis Ganda Menggunakan Service Mesh (Istio)**: 
   Alih-alih mengandalkan pembagian DNS/Round Robin dasar, tim menerapkan *virtual service dynamic weight routing* dengan *header-based canary testing* terbatas pada traffic pegawai internal sebelum eksposur publik.
2. **Koneksi Laten Menggunakan Proxy Sidecar & Connection Pooling**:
   Implementasi AWS RDS Proxy diintegrasikan dengan *warmup probes*. Aplikasi tidak dapat menerima traffic sebelum pool koneksi internal terisi secara bertahap tanpa lonjakan tajam.
3. **Penerapan Analysis Metric SLI Ekstrem**:
   Pipeline Argo Rollouts membaca metrik dari Prometheus:
   - SLI 1: Database active connection headroom (> 20%).
   - SLI 2: HTTP 5xx error rate (< 0.01%).
   - SLI 3: Latency 99th percentile (< 85ms).
4. **Hasil**:
   Rilis berikutnya menghadapi *code regression* (memory leak pada modul enkripsi token baru). Metrik otomatis mendeteksi anomali pada fase alokasi traffic 5%. Sistem membatalkan (*rollback*) canary dalam waktu **34 detik**. Nol pengguna akhir terdampak, dan database utama tetap mempertahankan ketersediaan 100%.

---

### 9. Trade-offs

Setiap keputusan arsitektur produksi membawa konsekuensi engineering yang harus diseimbangkan:

| Parameter Arsitektur | Pilihan A: Blue/Green Deployment | Pilihan B: Canary Progressive Delivery | Pilihan C: Standard Rolling Update |
| :--- | :--- | :--- | :--- |
| **Footprint Biaya Infrastruktur** | **Sangat Tinggi** (+100% kapasitas resource cadangan selama deployment). | **Rendah - Sedang** (Hanya memerlukan +5% s/d +20% resource tambahan). | **Paling Rendah** (Resource disesuaikan dengan toleransi `maxSurge`). |
| **Blast Radius Mitigation** | **Biner (All-or-Nothing)**: Jika cutover dilakukan tanpa pengujian traffic riil bertahap, seluruh user terdampak. | **Sangat Terisolasi**: Error hanya dialami oleh persentase kecil traffic pengguna target. | **Moderat**: Dampak meluas seiring bertambahnya persentase pod yang berganti. |
| **Kompleksitas Observabilitas** | **Rendah**: Membutuhkan switch routing DNS/Load Balancer tunggal. | **Tinggi**: Wajib memiliki telemetri instan, metrik granular, dan evaluasi SLO dinamis. | **Rendah**: Cukup mengandalkan built-in Kubernetes Deployment controller. |
| **Waktu Eksekusi Delivery** | **Cepat**: Pengalihan traffic instan setelah lingkungan Green dinyatakan sehat. | **Lambat**: Membutuhkan jendela observasi metrik (*baking periods*) antar-tahap. | **Moderat**: Bergantung pada durasi readiness pod dan batas waktu termination. |
| **Stateful DB Synchronization** | **Sangat Rumit**: Skema database wajib backward- dan forward-compatible (*Dual-write*). | **Terkontrol**: Skema database diisolasi dengan migrasi *expand-and-contract*. | **Rumit**: Butuh kompatibilitas multi-versi sementara saat proses roll berlangsung. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum Produksi:
1. **Liveness Probe Menguji Dependensi Eksternal**:
   - *Anti-pattern*: Menempatkan query database atau panggilan API payment gateway di dalam endpoint `/healthz/liveness`.
   - *Dampak*: Ketika database mengalami perlambatan sesaat, seluruh pod backend dianggap rusak oleh kubelet dan di-restart massal secara serentak. Ini menciptakan *cascading collapse* yang melumpuhkan total cluster.
2. **Tidak Adanya Sinkronisasi `preStop` Hook dengan Routing Ingress**:
   - *Anti-pattern*: Membiarkan container langsung mati saat menerima sinyal `SIGTERM`.
   - *Dampak*: Terjadi *race condition* di mana kubelet menghentikan pod lebih cepat daripada waktu yang dibutuhkan Ingress Controller untuk memperbarui daftar endpoint. User mengalami error HTTP 502 Bad Gateway.
3. **Mengabaikan PodDisruptionBudget (PDB) pada Cluster Autoscaling**:
   - *Anti-pattern*: Melakukan upgrade worker node tanpa PDB.
   - *Dampak*: Kubelet melakukan *drain* terhadap semua pod aplikasi kritis secara simultan, melenyapkan ketersediaan sistem selama periode *cluster maintenance*.

#### Panduan Troubleshooting Langkah-demi-Langkah:
Kasus: Pod Terjebak dalam status `CrashLoopBackOff` atau Mengalami Penghentian Tak Terduga saat Beban Puncak.

```bash
# 1. Periksa event cluster secara kronologis untuk namespace terkait
kubectl get events -n production --sort-by='.metadata.creationTimestamp' | tail -n 25

# 2. Periksa termination code spesifik pada container
kubectl get pod <pod-name> -n production -o jsonpath='{range .status.containerStatuses[*]}{.name}{"\tExitCode: "}{.state.terminated.exitCode}{"\tReason: "}{.state.terminated.reason}{"\n"}{end}'
# OOMKilled (Exit Code 137): Container melanggar memory limits.
# Exit Code 143: Container dimatikan oleh SIGTERM eksternal.

# 3. Analisis logs dari instance container sebelumnya yang mengalami crash
kubectl logs <pod-name> -n production --previous --tail=100

# 4. Verifikasi alokasi komparasi Resource Requests vs Node Allocation
kubectl describe node <node-name> | grep -A 8 "Allocated resources"
```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum mengizinkan beban kerja masuk ke lingkungan produksi Tier-1:

#### Keandalan & Penjadwalan (Reliability)
- [ ] Container mendefinisikan `requests` dan `limits` (Resource CPU & Memory) secara eksplisit.
- [ ] `requests.cpu` sama dengan `limits.cpu` untuk beban kerja latensi rendah (mencegah CPU throttling).
- [ ] `readinessProbe` dan `livenessProbe` terkonfigurasi secara terpisah dengan path evaluasi yang ringan.
- [ ] `startupProbe` digunakan khusus untuk aplikasi monolit/JVM yang lambat memulai service.
- [ ] Lifecycle hook `preStop` diset minimal 10-15 detik untuk memuluskan pelepasan koneksi jaringan.
- [ ] `PodDisruptionBudget` terdefinisi untuk menjamin ambang batas *high availability* minimum saat draining.
- [ ] `TopologySpreadConstraints` dikonfigurasi untuk distribusi multi-AZ merata.

#### Keamanan (Security Hardening)
- [ ] Container berjalan sebagai Non-Root user (UID >= 10000).
- [ ] Root filesystem diset ke status Read-Only (`readOnlyRootFilesystem: true`).
- [ ] Linux capabilities dijatuhkan seluruhnya (`drop: ["ALL"]`).
- [ ] Tidak ada token akun layanan (`automountServiceAccountToken: false`) yang terpasang jika aplikasi tidak berkomunikasi langsung dengan Kubernetes API.
- [ ] Image OCI ditandatangani via Cosign dan diverifikasi di admission controller.

---

### 12. Hands-on Practice

Implementasikan simulasi skenario *Progressive Delivery Rollout* di lingkungan lokal (Minikube / Kind / K3s) dalam direktori `hands-on/m02/`.

#### Langkah 1: Persiapan Lingkungan & Instalasi Operator
```bash
mkdir -p hands-on/m02 && cd hands-on/m02

# Buat namespace terisolasi
kubectl create namespace advanced-rollout

# Pasang Argo Rollouts Controller
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# Tunggu pod controller berjalan
kubectl wait --namespace argo-rollouts \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=argo-rollouts \
  --timeout=90s
```

#### Langkah 2: Buat Mock Microservice Manifest
Simpan file berikut sebagai `hands-on/m02/app-rollout.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: edge-auth-service
  namespace: advanced-rollout
spec:
  replicas: 4
  revisionHistoryLimit: 2
  selector:
    matchLabels:
      app: edge-auth
  strategy:
    canary:
      steps:
      - setWeight: 25
      - pause: { duration: 15s }
      - setWeight: 50
      - pause: { duration: 15s }
  template:
    metadata:
      labels:
        app: edge-auth
    spec:
      containers:
      - name: auth-node
        image: nginxdemos/hello:plain-text
        ports:
        - containerPort: 80
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
  name: edge-auth-service
  namespace: advanced-rollout
spec:
  ports:
  - port: 80
    targetPort: 80
  selector:
    app: edge-auth
```

#### Langkah 3: Deploy dan Pantau Siklus Hidup Peluncuran
```bash
# Terapkan manifest ke dalam cluster
kubectl apply -f app-rollout.yaml

# Pantau status rollout secara dinamis menggunakan kubectl plugin atau describe command
# (Jika kubectl argo-rollouts plugin terpasang: kubectl argo rollouts get rollout edge-auth-service -n advanced-rollout --watch)
kubectl describe rollout edge-auth-service -n advanced-rollout

# Jalankan update citra container untuk memicu proses Canary
kubectl set image rollout/edge-auth-service auth-node=nginxdemos/hello:latest -n advanced-rollout

# Amati perubahan alokasi pod secara progresif
kubectl get pods -n advanced-rollout -l app=edge-auth -w
```

#### Langkah 4: Uji Pembersihan & Simulasi Abort/Rollback
```bash
# Pemicuan rollback seketika
kubectl argo rollouts undo edge-auth-service -n advanced-rollout || kubectl rollout undo rollout/edge-auth-service -n advanced-rollout

# Cleanup environment
kubectl delete namespace advanced-rollout
```

---

### 13. Exercise

#### Level 1 - Easy: Optimasi Health Checks
- **Instruksi**: Diberikan deployment aplikasi Spring Boot yang membutuhkan waktu inisialisasi modul selama 45 detik. Modifikasi konfigurasi deployment agar *liveness probe* tidak membunuh aplikasi sebelum inisialisasi selesai, tanpa memperpanjang interval deteksi kegagalan normal aplikasi saat runtime.
- **Batasan**: Gunakan integrasi `startupProbe` spesifik.

#### Level 2 - Medium: Konfigurasi Zero-Downtime High-Load Scenarios
- **Instruksi**: Buat manifest Kubernetes yang memuat:
  1. `HorizontalPodAutoscaler` (HPA) dengan metrik utilitas CPU 70% dan target kustom 500 requests per second.
  2. `PodDisruptionBudget` yang mewajibkan minimal 3 replica tetap aktif setiap saat di atas skala total 5 pod.
  3. Konfigurasi `preStop` hook yang menjamin koneksi TCP yang tertunda tetap dieksekusi secara tuntas sebelum shutdown.

#### Level 3 - Hard: Cross-Zone Failure Self-Healing
- **Instruksi**: Simulasikan skenario 3 Availability Zone pada klaster Kubernetes lokal menggunakan Kind (*multi-worker nodes with labels*). Buat arsitektur deployment berdaya tampung 6 pod yang secara paksa menjamin:
  1. Jika salah satu AZ mati total, beban kerja pod mendistribusikan diri secara instan dan simetris ke 2 AZ yang tersisa tanpa melanggar kuota CPU node.
  2. Terapkan batasan `podAntiAffinity` keras (*requiredDuringSchedulingIgnoredDuringExecution*) untuk mencegah 2 pod yang sama tinggal pada host fisik yang identik.

---

### 14. Challenge

#### Skenario Studi Kasus Arsitektur Tanpa Solusi Instan

Sebuah bank sentral nasional menugaskan Anda untuk merancang sistem *Core Switching Transaksi Antar Bank*. Sistem ini beroperasi di bawah mandat regulasi berikut:
1. **Zero External Access**: Lingkungan cluster berstatus *Air-Gapped* murni tanpa akses ke internet publik. Seluruh dependencies, images, dan base OS harus ditampung dalam distributed registry lokal yang terverifikasi keasliannya.
2. **Sub-Second Failover Target**: Jika terjadi anomali transmisi data biner pada versi rilis baru, sistem dituntut melakukan rollback ke versi biner stabil dalam waktu **kurang dari 2 detik** tanpa memutuskan lebih dari 0.001% koneksi soket TCP yang sedang berjalan.
3. **Database Schema Mutation Boundary**: Pembaruan sistem menyertakan mutasi tabel relasional dari tipe integer standar ke tipe `UUIDv4` pada kolom kunci utama yang menampung 400 juta data aktif.

**Misi Anda**:
Susun dokumen arsitektur dan spesifikasi strategi rilis yang mencakup:
- Pola delivery sistem mana yang Anda pilih (Blue/Green vs Canary) beserta kalkulasi justifikasi teknisnya.
- Penanganan skema database menggunakan teknik *Expand and Contract Pattern*.
- Strategi orkestrasi routing jaringan di tingkat *Kernel Network Layer (eBPF/XDP)* untuk memenuhi ambang batas waktu failover sub-detik.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Pertanyaan Konseptual Dasar
1. Apa perbedaan arsitektural utama antara `startupProbe` dan `livenessProbe` di Kubernetes?
   - **Jawaban**: `startupProbe` menonaktifkan semua probe lain (`liveness` dan `readiness`) hingga probe tersebut berhasil dieksekusi pertama kali. Tujuannya adalah mengamankan aplikasi dengan waktu *cold-start* lambat agar tidak dibunuh secara keliru oleh `livenessProbe`.
2. Mengapa instruksi `USER nonroot` sangat krusial dalam Dockerfile enterprise?
   - **Jawaban**: Untuk menerapkan prinsip hak akses terkecil (*least privilege*). Jika terjadi eksploitasi eksekusi kode atau *container breakout*, penyerang hanya memiliki akses setara pengguna non-root pada kernel host dan tidak dapat langsung menguasai host node.
3. Apa fungsi struktural dari parameter `maxSkew` pada `TopologySpreadConstraints`?
   - **Jawaban**: `maxSkew` mendefinisikan derajat perbedaan maksimum yang diizinkan dalam jumlah pod aplikasi yang berjalan di antara dua domain topologi (misalnya antar Availability Zone).
4. Bagaimana peran sinyal sistemik `SIGTERM` dalam proses siklus hidup pod?
   - **Jawaban**: `SIGTERM` adalah sinyal pemberitahuan awal dari sistem operasi ke proses aplikasi untuk menghentikan penerimaan transaksi baru, membersihkan koneksi atau file sementara, dan menyelesaikan koneksi yang sedang aktif secara damai (*graceful shutdown*).
5. Apa kegunaan utama dari *Software Bill of Materials* (SBOM) dalam supply chain security pipeline DevOps modern?
   - **Jawaban**: SBOM berfungsi sebagai inventaris komprehensif komponen dependensi pihak ketiga, library, dan modul dari sebuah software artifact. SBOM memungkinkan audit kerentanan seketika jika ditemukan CVE baru pada salah satu paket open-source terkait.

#### Bagian B: Analisis Menengah
6. Mengapa menempatkan `limits.cpu` yang terlalu ketat dapat menurunkan performa aplikasi latensi rendah secara signifikan, meskipun penggunaan memori normal?
   - **Jawaban**: Kubernetes mengelola batas CPU menggunakan *CFS (Completely Fair Scheduler) Bandwidth Control* di Linux kernel. Ketika sebuah thread melampaui kuota waktu eksekusi CPU dalam satuan periode slice (biasanya per 100ms), thread tersebut akan di-*throttle* (dibekukan secara paksa), menghasilkan lonjakan tail latency secara ekstrem.
7. Jelaskan bagaimana *preStop hook* mencegah error HTTP 502 selama proses terminasi pod di balik reverse proxy atau Ingress Controller!
   - **Jawaban**: Deregistrasi pod dari endpoint load balancer dan propagasi tabel routing membutuhkan waktu beberapa detik. `preStop` hook menunda pengiriman `SIGTERM` ke proses aplikasi selama durasi tertentu (misal 15 detik), memastikan aplikasi tetap merespons koneksi yang masih melintasi rute lama hingga routing baru aktif sepenuhnya.
8. Dalam konteks Progressive Delivery, apa perbedaan mendasar antara metrik berbasis *Counter* dan *Gauge* saat menyusun *AnalysisTemplate* evaluasi error?
   - **Jawaban**: Counter adalah nilai yang selalu naik secara monoton (misalnya total request, total error), sehingga harus dievaluasi menggunakan laju perubahan via fungsi turunan waktu seperti `rate()` atau `irate()`. Gauge adalah nilai fluktuatif sesaat (misalnya penggunaan memori, jumlah koneksi aktif) yang dapat langsung dievaluasi nilainya pada titik waktu tertentu.
9. Apa ancaman keamanan arsitektural jika file manifest deployment menetapkan `privileged: true` pada `securityContext` container?
   - **Jawaban**: Akses `privileged: true` menonaktifkan seluruh mekanisme isolasi container di Linux. Container tersebut mendapatkan kapabilitas root absolut setara host fisik, akses penuh ke `/dev`, kemampuan memodifikasi aturan IPTables/eBPF, dan kemampuan keluar dari kontainer (*container breakout*) untuk mengambil alih seluruh simpul node.
10. Mengapa integrasi *Database Migration* tidak boleh diletakkan di dalam container aplikasi yang berskala multi-replica?
    - **Jawaban**: Jika multi-replica pod melakukan migrasi DDL/DML secara bersamaan saat startup, dapat terjadi *deadlock* pada schema catalog database, eksekusi migrasi yang parsial atau inkonsisten, serta lonjakan latensi fatal pada cluster database.

#### Bagian C: Skenario Kasus Produksi
11. **Kasus 1**: Pada cluster produksi, terjadi insiden di mana semua node pada satu zona (Zone-A) kehilangan daya secara mendadak. Sebanyak 50% aplikasi backend gagal pulih di Zona-B dan Zona-C, meskipun kapasitas memori dan vCPU pada kedua zona tersebut masih tersisa 40%. Log sistem menunjukkan error scheduling `0/6 nodes available: 3 Insufficient memory, 3 PodTopologySpreadFilter failure`. Apa analisis Anda terhadap insiden ini dan bagaimana cara memperbaikinya?
    - **Analisis & Solusi**: Kegagalan disebabkan oleh penerapan `whenUnsatisfiable: DoNotSchedule` pada konfigurasi `TopologySpreadConstraints` yang terlalu kaku. Ketika satu zona mati total, scheduler menolak menaruh pod di zona lain karena pelanggaran aturan distribusi seimbang (`maxSkew`). Solusinya adalah mengubah konfigurasi menjadi `whenUnsatisfiable: ScheduleAnyway` agar kluster memprioritaskan pemulihan ketersediaan aplikasi daripada kepatuhan kaku topologi saat terjadi bencana regional.
12. **Kasus 2**: Sebuah microservice otentikasi baru saja dinaikkan versinya menggunakan Argo Rollouts. Analisis Prometheus diset memonitor HTTP status 5xx. Setelah canary mencapai 50%, sistem pembayaran downstream melaporkan bahwa jutaan transaksi dinyatakan tidak valid karena format JWT payload berubah secara diam-diam. Akan tetapi, Argo Rollouts tidak mendeteksi anomali dan terus menaikkan traffic hingga 100%. Jelaskan kegagalan metrik apa yang terjadi dan bagaimana perbaikan desain evaluasinya!
    - **Analisis & Solusi**: Evaluasi Canary menderita bias metrik teknis (*blind spot*). Aplikasi merespons token invalid dengan kode HTTP 200 atau 400 (bukan HTTP 5xx), sehingga query error Prometheus tidak mencatat kegagalan teknis server. Metrik SLO harus diperbaiki tidak hanya mengevaluasi status code `5.*`, namun juga menyertakan *Business Performance Indicator* (SLI Bisnis), seperti: rasio otentikasi sukses terhadap total upaya login, dan jumlah transmisi kode `401 Unauthorized` / `400 Bad Request` yang melampaui batas ambang normal.
13. **Kasus 3**: Seorang engineer DevOps senior mengeksekusi perintah `kubectl drain <node-name> --delete-emptydir-data --ignore-daemonsets` untuk pemeliharaan kernel host. Perintah tersebut menggantung (*hang*) selama lebih dari 30 menit, dan beberapa layanan microservice penting tidak berhasil dipindahkan ke node lain, sehingga memicu eskalasi status darurat. Di manakah letak akar masalah konfigurasi manifest pada sistem?
    - **Analisis & Solusi**: Akar masalah berada pada konfigurasi `PodDisruptionBudget` (PDB) yang salah rancang, kemungkinan besar menggunakan konfigurasi kaku seperti `minAvailable: 100%` atau `maxUnavailable: 0` pada armada aplikasi yang hanya memiliki sedikit replika. Akibatnya, API Server menolak eviksi pod secara permanen untuk mematuhi aturan PDB tersebut. Solusinya adalah mendefinisikan PDB dengan rasio persentase yang longgar (misalnya `maxUnavailable: 1` atau `minAvailable: 80%`) dan memastikan jumlah replica dasar mencukupi untuk mentoleransi kehilangan sementara 1 unit pod selama proses rolling maintenance.

---

### 16. Summary

1. Arsitektur produksi modern mensyaratkan pergeseran dari proses rilis imperatif menuju **reconciliation loop deklaratif** yang berjalan secara mandiri dan mengisolasi potensi kegagalan manusia.
2. Pengendalian *Blast Radius* secara deterministik hanya dapat dicapai melalui kombinasi penerapan **Progressive Delivery (Canary)** dan integrasi **evaluasi metrik SLO berbasis telemetri tertutup** (*closed-loop automated rollbacks*).
3. Ketahanan sistem (*Resilience*) tidak bertumpu pada pencegahan kegagalan infrastruktur secara mutlak, melainkan pada **perancangan toleransi kegagalan**: pemisahan *failure domains* melalui *Topology Spread Constraints*, perlindungan ketersediaan melalui *Pod Disruption Budgets*, serta penghentian beban kerja yang tertib menggunakan penanganan sinyal UNIX dan *lifecycle hooks*.
4. Keamanan kontainer tingkat produksi wajib menganut prinsip **Zero-Trust & Least Privilege**: implementasi basis *Distroless Minimal Images*, peniadaan izin akses root secara absolut, serta pembatasan kapabilitas kernel di seluruh lapisan eksekusi.