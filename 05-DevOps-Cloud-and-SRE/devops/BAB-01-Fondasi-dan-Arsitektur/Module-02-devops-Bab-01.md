# Kategori: 05-DevOps-Cloud-and-SRE
## Bab 01: Fondasi dan Arsitektur
### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Mengimplementasikan Arsitektur GitOps Berbasis Operator**: Memahami siklus rekonsiliasi (*reconciliation loop*), *drift detection*, dan mitigasi divergensi konfigurasi antara *declared state* di Git repository dan *runtime state* di Kubernetes cluster menggunakan ArgoCD.
- **Membangun Pipeline Progressive Delivery Tingkat Lanjut**: Mengonfigurasi pola rilis Canary terotomasi berbasis metrik real-time (Latency p99, HTTP Error Rate 5xx) menggunakan Argo Rollouts, Prometheus Analysis, dan Traffic Management (Service Mesh/Ingress Controller).
- **Menerapkan Policy-as-Code (PaC) & Supply Chain Security**: Menegakkan *governance* konfigurasi pra-deployment dan saat runtime melalui Open Policy Agent (OPA/Gatekeeper) serta memverifikasi integritas artefak kontainer via cryptographic attestation (Cosign & SLSA Framework).
- **Merancang Topologi Multi-Environment State Management**: Mengelola dependensi kompleks Infrastructure-as-Code (IaC) dengan Terraform/Terragrunt dengan *state isolation*, *distributed state locking*, dan *least-privilege service boundary*.

---

### 2. Prerequisite
Peserta wajib memiliki pemahaman mendalam dan pengalaman praktis terhadap:
- **Arsitektur Internal Kubernetes**: Mekanisme kerja API Server, etcd, Custom Resource Definitions (CRDs), Custom Controllers, dan Kubelet.
- **Dasar CI/CD & Linux Primitives**: Namespace, Cgroups, POSIX signals (SIGTERM/SIGKILL), process lifecycle, dan container runtime interface (CRI).
- **Networking Enterprise**: Layer 4 vs Layer 7 routing, TCP handshake, TLS termination, mTLS, dan service discovery via CoreDNS.
- **Kriptografi Dasar**: Public-Key Cryptography (asymmetric encryption), digital signatures, dan x509 certificate management.

---

### 3. Concept & Internal Architecture

Implementasi arsitektur DevOps enterprise modern membuang paradigma CI push-based konvensional (di mana runner CI memegang kredensial cluster dengan privilege tinggi) dan beralih ke arsitektur **Declarative Pull-based Reconciliation** yang dipadukan dengan **Cryptographically Verifiable Supply Chain**.

```
+-------------------------------------------------------------------------------------------------------+
|                                    SOFTWARE SUPPLY CHAIN CONTROL PLANE                                 |
+-------------------------------------------------------------------------------------------------------+
 [Developer] 
      │
      ▼ (Signed Commit via GPG)
 [Git Repository (App Code)]
      │
      ▼ (Event: Webhook)
 [CI Engine (Isolated Runner)] ──> [Build OCI Container]
      │                                    │
      │                                    ▼
      │                             [Vulnerability Scan (Trivy/Grype)]
      │                                    │
      │                                    ▼
      │                             [Generate SBOM (Syft / SPDX)]
      │                                    │
      │                                    ▼
      │                             [Sign Image & Attestation (Cosign)] ──> [OCI Registry]
      │                                                                           ▲
      ▼ (Automated PR: Bump Image Digest)                                         │
 [Git Repository (Config / Infra)]                                                │
      ▲                                                                           │
      │ (Continuous Polling / Webhook)                                            │
+─────┼───────────────────────────────────────────────────────────────────────────┼─────────────────────+
|     │                                     KUBERNETES RUNTIME                    │                     |
|     ▼                                                                           │                     |
| [GitOps Controller (ArgoCD)]                                                    │                     |
|     │                                                                           │                     |
|     ├── 1. Fetch Desired State                                                  │                     |
|     ├── 2. Query In-Cluster State via Kube-API                                  │                     |
|     ├── 3. Compute Diff (Three-way merge patch)                                 │                     |
|     └── 4. Apply Changes to Cluster                                             │                     |
|                                                                                 │                     |
| [Admission Controller Phase]                                                    │                     |
|     ├── [Validating Webhook (OPA Gatekeeper)] <── Verifies Cosign Signature ────┘                     |
|     └── [Mutating Webhook]                                                                            |
|                                                                                                       |
| [Progressive Delivery (Argo Rollouts Engine)]                                                         |
|     ├── Split Traffic via Ingress/Service Mesh (e.g., 90% Stable / 10% Canary)                         |
|     ├── Query Prometheus Metrics (Canary Success Rate, Latency p99)                                   |
|     └── Decision: Promote Step-by-Step OR Automatic Fast-Rollback                                     |
+-------------------------------------------------------------------------------------------------------+
```

#### Komponen Kunci Arsitektur:
1. **The Three-Way Merge Engine**: Controller GitOps tidak sekadar mengeksekusi `kubectl apply`. ArgoCD memanfaatkan *three-way merge patch* antara:
   - **Target Manifest** (apa yang tertulis di branch target Git).
   - **Live State** (objek aktual yang tersimpan di etcd Kubernetes).
   - **Last Applied Configuration** (catatan yang tersimpan pada metadata anotasi objek).
   Mekanisme ini memungkinkan controller mendeteksi apakah perbedaan (*drift*) terjadi akibat modifikasi manual oleh admin, proses mutasi runtime (misalnya Horizontal Pod Autoscaler yang merubah `replicas`), atau murni perubahan dari source code.

2. **Admission Webhook Execution Chain**: Sebelum resource tersimpan di etcd, Kubernetes API Server mengeksekusi webhook eksternal:
   - **Mutating Webhook**: Menginjeksi konfigurasi standar (seperti sidecar proxy Envoy atau node affinity enterprise).
   - **Validating Webhook**: Memvalidasi kepatuhan terhadap policy keamanan (contoh: memblokir container yang berjalan sebagai root atau image tanpa tanda tangan Cosign yang valid).

3. **Analysis & Dynamic Metric Gathering**: Deployment progresif mengabstraksi rollback manual menjadi evaluasi telemetri deterministik. Controller secara periodik melakukan eksekusi kueri PromQL langsung ke Time Series Database (TSDB). Jika nilai ambang batas (*threshold*) terlampaui selama $N$ interval berturut-turut, controller memotong rute trafik canary secara instan dan mengembalikan (*weight-shift*) routing 100% ke pod stable tanpa memicu downtime.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (CI/CD Push-Based) | Pendekatan Enterprise Modern (GitOps & Progressive) |
| :--- | :--- | :--- |
| **Credential Management** | Runner CI memegang token `cluster-admin` permanen. Resiko eskalasi hak akses (*blast radius*) jika runner terkompromi sangat fatal. | Pola Pull-based via In-cluster Agent. Tidak ada kredensial cluster yang terekspos ke luar perimeter jaringan cluster. |
| **State Drift Handling** | Jika teknisi mengubah manifest langsung via `kubectl edit`, sistem CI tidak mengetahui dan konfigurasi melenceng secara permanen (*configuration drift*). | GitOps reconciliation loop mendeteksi *drift* dalam hitungan detik dan melakukan koreksi otomatis (*self-healing*) kembali ke *state* Git. |
| **Deployment Strategy** | RollingUpdate standar Kubernetes (menggantikan pod $1$ per $1$). Jika terjadi memory leak atau error pada runtime logika, 100% user langsung terdampak. | Canary via Progressive Delivery (Argo Rollouts). Trafik dilepas bertahap (misal 5% -> 20% -> 50% -> 100%) dengan verifikasi metrik otomatis. |
| **Auditability & Traceability**| Audit trail tersebar di log eksekusi runner CI yang mudah hilang atau dimanipulasi. | Setiap perubahan status infrastruktur dan aplikasi terikat secara kriptografis pada Git Commit SHA dan immutable container digest. |

---

### 5. How (Workflow Detail)

Alur eksekusi end-to-end produksi dari commit hingga zero-downtime canary release:

```
[Commit Code] 
      │
      ▼
[CI: Build & Sign] ──> [CI: Publish OCI Image with SHA256 Digest]
                              │
                              ▼
                       [CI: Update GitOps Repository Manifest]
                              │
                              ▼
                       [ArgoCD Sync Event]
                              │
                              ▼
                       [OPA Validating Webhook Evaluation]
                         ├─ Non-compliant: REJECT (Pipeline Failed)
                         └─ Compliant: ACCEPT (Persist to etcd)
                              │
                              ▼
                       [Argo Rollouts Controller Triggered]
                         │
                         ├── Phase 1: Deploy Canary Pods (Weight: 10%)
                         ├── Phase 2: Start AnalysisTemplate (PromQL Validation)
                         │     ├── Condition 1: Error Rate < 0.5%
                         │     └── Condition 2: Latency p99 < 200ms
                         │
                         ├── Phase 3: Evaluate Result
                         │     ├─ Success: Shift Traffic (25% -> 50% -> 100%) -> Promote Stable
                         │     └─ Failure: Abort -> Instant Route 100% Traffic to Old ReplicaSet
                         │
                         └── Phase 4: Scale Down Old ReplicaSet
```

#### Langkah-langkah Detail:
1. **Image Digest Immutability**: CI tidak pernah menggunakan tag yang bisa berubah (*mutable*) seperti `:latest` atau `:v1.0.0`. CI mengekstrak hash kriptografis unik image (`sha256:7f...`) dan menandatanganinya dengan private key menggunakan Cosign.
2. **Configuration Pinning**: Script otomatisasi CI melakukan pull request ke repositori konfigurasi GitOps untuk memperbarui field `image.digest`.
3. **Cluster Sync & Admission Verification**:
   - ArgoCD mendeteksi commit baru pada repositori konfigurasi dan menerapkannya ke cluster API.
   - Admission controller memverifikasi tanda tangan image OCI via Cosign public key. Jika digest tidak valid atau tidak terdaftar, deployment ditolak di tingkat API Server.
4. **Traffic Splitting & Progressive Metric Analysis**:
   - Argo Rollouts membuat ReplicaSet baru (*canary*) dan mengonfigurasi Ingress/Service Mesh untuk mengarahkan 10% trafik pengguna.
   - AnalysisTemplate mengeksekusi kueri Prometheus setiap 30 detik selama 5 menit.
   - Jika metrik memenuhi SLA/SLO, bobot dinaikkan secara bertahap hingga 100%. Pod stable lama dihentikan secara graceful melalui handling sinyal `SIGTERM`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengujian Kualitas Air Kota Modern
Bayangkan sistem pipa air minum kota metropolitan:
- **Konvensional (RollingUpdate)**: Pipa baru dipasang langsung ke seluruh rumah warga. Jika air baru tersebut ternyata beracun (bug fungsional), seluruh warga kota keracunan sebelum laboratorium mendeteksi masalahnya.
- **Enterprise Modern (Progressive Delivery dengan Analysis)**:
  1. Air dari sumber baru dialirkan hanya ke **10% saluran pipa uji coba khusus**.
  2. **Sensor otomatis (Prometheus)** di pipa uji coba secara kontinu menganalisis partikel racun dan kejernihan air (p99 latency & error rate).
  3. Jika sensor mendeteksi anomali sekecil apa pun, **katup otomatis langsung menutup pipa uji coba** dan mengalirkan kembali 100% air dari sumber lama yang stabil tanpa ada warga yang sempat meminum air beracun.
  4. Hanya jika sensor menyatakan air 100% murni, katup ke seluruh kota dibuka perlahan-lahan.

#### Topologi Routing & Validasi Metrik:
```
                              [USER TRAFFIC]
                                    │
                                    ▼
                      +───────────────────────────+
                      |   Ingress / Service Mesh  |
                      +───────────────────────────+
                                    │
                  ┌─────────────────┴─────────────────┐
     Weight: 90%  │                                   │ Weight: 10%
                  ▼                                   ▼
        +───────────────────+               +───────────────────+
        |   Stable Pods     |               |    Canary Pods    |
        |  (Version: v1.0)  |               |   (Version: v1.1) |
        +───────────────────+               +───────────────────+
                  │                                   │
                  └─────────────────┬─────────────────┘
                                    │ (Emit Metrics: Status Codes, Duration)
                                    ▼
                          +───────────────────+
                          | Prometheus Server |
                          +───────────────────+
                                    │
                                    │ (Query: PromQL every 30s)
                                    ▼
                        +───────────────────────+
                        | Argo Rollout Operator |
                        +───────────────────────+
                          [DECISION ENGINE]
                           ├─ p99 < 200ms?  --> YES: Scale Up
                           └─ Error < 0.5%? --> NO:  ABORT & ROLLBACK
```

---

### 7. Simple Example & Practical Example

Berikut adalah artefak implementasi standar industri yang siap digunakan di environment production.

#### A. Policy-as-Code Menggunakan Open Policy Agent (Rego)
File ini memastikan tidak ada resource workload yang dideploy tanpa isolasi keamanan dan resource limits.

`hands-on/m02/policies/container_security.rego`:
```rego
package kubernetes.admission

import future.keywords.in

default allow = false

# Whitelist registry yang diizinkan oleh enterprise
allowed_registries := ["registry.enterprise.internal/", "ghcr.io/enterprise/"]

# Aturan Utama: Izinkan hanya jika tidak ada pelanggaran
allow {
    count(violations) == 0
}

# Pelanggaran 1: Container berjalan sebagai root
violations[sprintf("Container '%v' must not run as root (set runAsNonRoot to true)", [container.name])] {
    container := input.request.object.spec.template.spec.containers[_]
    not container.securityContext.runAsNonRoot == true
}

# Pelanggaran 2: Menggunakan image dari public/untrusted registry
violations[sprintf("Container '%v' uses unauthorized image '%v'", [container.name, container.image])] {
    container := input.request.object.spec.template.spec.containers[_]
    registry_valid := [valid | reg := allowed_registries[_]; startswith(container.image, reg)]
    not any(registry_valid)
}

# Pelanggaran 3: Tidak mendefinisikan CPU/Memory Limit (mencegah noisy neighbor)
violations[sprintf("Container '%v' has no memory limit specified", [container.name])] {
    container := input.request.object.spec.template.spec.containers[_]
    not container.resources.limits.memory
}
```

#### B. Argo Rollout dengan Automated Canary Analysis via Prometheus
Argo Rollout Custom Resource menggantikan manifest `Deployment` standar, dilengkapi deklarasi metrik Prometheus untuk automated verification.

`hands-on/m02/manifests/rollout.yaml`:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: payment-processing-engine
  namespace: core-finance
  labels:
    app.kubernetes.io/name: payment-engine
spec:
  replicas: 10
  revisionHistoryLimit: 5
  selector:
    matchLabels:
      app.kubernetes.io/name: payment-engine
  strategy:
    canary:
      canaryService: payment-engine-canary
      stableService: payment-engine-stable
      trafficRouting:
        nginx:
          stableIngress: payment-engine-ingress
      analysis:
        templates:
          - templateName: telemetry-success-rate
        args:
          - name: service-name
            value: payment-engine-canary
      steps:
        - setWeight: 10
        - pause: { duration: 2m }
        - setWeight: 25
        - pause: { duration: 5m }
        - setWeight: 50
        - pause: { duration: 5m }
  template:
    metadata:
      labels:
        app.kubernetes.io/name: payment-engine
    spec:
      containers:
        - name: core-api
          image: registry.enterprise.internal/payment/api@sha256:4d60c410be280dffbf2e99d4586d34b3f0ecfb8bbcf9f6c0ebcb47e9ff2e9b0d
          ports:
            - containerPort: 8080
              name: http
          securityContext:
            runAsNonRoot: true
            runAsUser: 10001
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2000m"
              memory: "1Gi"
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
```

`hands-on/m02/manifests/analysis-template.yaml`:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: telemetry-success-rate
  namespace: core-finance
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
            sum(rate(http_requests_total{service="{{args.service-name}}", status!~"5.*"}[1m]))
            /
            sum(rate(http_requests_total{service="{{args.service-name}}"}[1m]))
    - name: latency-p99
      interval: 30s
      successCondition: result[0] <= 0.200
      failureLimit: 2
      provider:
        prometheus:
          address: http://prometheus-k8s.monitoring.svc.cluster.local:9090
          query: |
            histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service="{{args.service-name}}"}[1m])) by (le))
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Platform**: Core Banking Ledger Service pada Bank Digital Tier-1.
- **Beban Trafik**: 65.000 Requests Per Second (RPS) pada peak hours.
- **SLA**: 99.999% availability (maksimum total downtime gabungan ~5.26 menit dalam satu tahun).

#### Masalah Produksi
Pada update versi aplikasi v2.14.0, terdapat subtle memory leak pada connection pool library gRPC baru yang hanya memicu crash pod setelah 7 menit menangani konkurensi di atas 2.000 request per pod. Menggunakan strategi standar `RollingUpdate`:
- Semua pod v2.13.0 digantikan secara bertahap selama 4 menit.
- Pada menit ke-8, seluruh cluster baru kehabisan memory (*OOMKilled* massal secara simultan).
- Terjadi pemadaman total sistem (*full outage*) selama 18 menit sebelum rollback manual selesai dieksekusi, menyebabkan kerugian finansial langsung dan pelanggaran regulasi perbankan.

#### Implementasi Solusi Arsitektural Baru
Arsitek DevOps merancang pipeline automated validation progresif:
1. **Canary Baseline**: Rilis dibatasi pada bobot 5% trafik selama 15 menit dengan routing header HTTP eksplisit untuk data-plane sampling.
2. **Multi-Variate Analysis**:
   - Prometheus mengevaluasi metrik *Resident Set Size* (RSS) memory consumption slope via operator regresi linear: `deriv(container_memory_working_set_bytes[5m]) > 0`.
   - Error rate 5xx dipantau secara simultan dengan SLA ketat (maksimum 0.01% dari total request canary).
3. **Automated Fast-Abort via Service Mesh**:
   - Jika `deriv` konsumsi memori terdeteksi terus menanjak tajam secara abnormal selama 3 menit pengujian, Istio VirtualService langsung mengembalikan weight ke `0` untuk canary pod.
   - Argo Rollout menandai rilis sebagai `Degraded` dan mematikan pod canary secara aman tanpa intervensi manusia sama sekali.

#### Hasil
Saat library buggy tersebut diuji kembali di rilis berikutnya (v2.14.1 patch test):
- Sistem mendeteksi memory leak pada menit ke-6 saat bobot masih berada pada 5%.
- Traffic dibalikkan ke stable dalam waktu 850 milidetik.
- 95% nasabah tidak mengalami anomali transaksi sama sekali. Outage 18 menit dapat dieliminasi secara total menjadi nol downtime impact.

---

### 9. Trade-offs

Setiap keputusan arsitektur tingkat enterprise memiliki kompromi desain yang fundamental:

```
+----------------------------------------------------------------------------------------------------+
|                                    ARCHITECTURAL TRADE-OFF MATRIX                                   |
+---------------------------+-----------------------------------+------------------------------------+
| PENDEKATAN                | KEUNTUNGAN                        | KONSEKUENSI / TRADE-OFF            |
+---------------------------+-----------------------------------+------------------------------------+
| Progressive Delivery      | - Zero blast radius               | - Konsumsi resource komputasi      |
| (Argo Rollouts + Mesh)    | - Perlindungan mutlak SLA user    |   ganda selama proses canary       |
|                           | - Automated instant rollback      | - Waktu rilis deployment menjadi   |
|                           |                                   |   lebih lama (15-30 menit)         |
+---------------------------+-----------------------------------+------------------------------------+
| Strict Policy-as-Code     | - Keamanan supply chain terjamin  | - Latensi API Server bertambah     |
| (OPA Validating Webhook)  | - Eliminasi miskonfigurasi human  |   pada setiap operasi create/apply |
|                           |   secara deterministik            | - Resiko failure jika webhook      |
|                           |                                   |   controller timeout/down          |
+---------------------------+-----------------------------------+------------------------------------+
| GitOps In-Cluster Pull    | - Perimeter security sangat aman  | - Kompleksitas debugging tracing   |
| (ArgoCD Operator Engine)  | - Rekonsiliasi state konsisten    | - Eventual consistency: ada delay  |
|                           | - Audit trail berbasis Git commit |   antara push commit hingga sinkron|
+---------------------------+-----------------------------------+------------------------------------+
```

---

### 10. Common Mistakes & Troubleshooting

#### Skenario 1: ArgoCD Out-of-Sync Loop Akibat Mutating Controller
- **Gejala**: ArgoCD terus-menerus menampilkan status `OutOfSync` walau tidak ada commit baru di Git.
- **Penyebab**: Deployment manifest di Git mendefinisikan field tertentu (misal: `spec.replicas: 3`), namun di cluster terpasang Horizontal Pod Autoscaler (HPA) yang secara dinamis mengubah nilai `replicas` menjadi `12`. Terjadi *race condition* antara rekonsiliasi GitOps dan loop kontrol HPA.
- **Solusi**: Tambahkan konfigurasi `ignoreDifferences` pada resource Application ArgoCD:
```yaml
spec:
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas
```

#### Skenario 2: Webhook Failure Loop (API Server Deadlock)
- **Gejala**: Seluruh operasi `kubectl apply` di cluster berhenti merespons atau mengembalikan error `Internal error occurred: failed calling webhook`.
- **Penyebab**: Validating Webhook milik OPA Gatekeeper dikonfigurasi dengan mode `failurePolicy: Fail`, namun pod Gatekeeper itu sendiri mengalami crash atau tidak dapat diakses via network mesh internal.
- **Solusi Troubleshooting**:
  1. Akses control plane node dan bypass API Server webhook sementara:
     ```bash
     kubectl delete validatingwebhookconfiguration gatekeeper-validating-webhook-configuration --ignore-not-found
     ```
  2. Ubah konfigurasi kritis sistem menjadi `failurePolicy: Ignore` untuk namespace `kube-system`, atau atur `namespaceSelector` agar admission webhook tidak memvalidasi resource internal miliknya sendiri.

#### Skenario 3: False-Positive Canary Abort Akibat "Cold Start" Latency
- **Gejala**: Argo Rollouts langsung membatalkan deployment canary beberapa detik setelah trafik dialihkan, padahal aplikasi tidak memiliki error kode.
- **Penyebab**: Aplikasi Java/Go runtime memerlukan inisialisasi koneksi DB dan kompilasi JIT (cold start) sehingga latency request pertama melompat tinggi. AnalysisTemplate Prometheus langsung menganggap p99 latency gagal (*exceeded*).
- **Solusi**: Gunakan properti `initialDelay` pada metric check dan tambahkan warm-up phase sebelum evaluasi telemetri dijalankan.

---

### 11. Best Practices (Production Checklist)

Gunakan daftar checklist ini sebagai audit gate sebelum mengeksekusi pipeline produksi:

#### Pipeline & Supply Chain Security
- [ ] **Immutable Tags**: Semua manifest pod wajib merujuk ke kontainer menggunakan digest `image@sha256:...`, bukan image tag biasa.
- [ ] **Cryptographic Signing**: Container image divalidasi via Cosign/Notary pada tahap admission control.
- [ ] **Rootless Execution**: Konteks keamanan seluruh Pod di-set ke `runAsNonRoot: true` dan filesystem root bersifat *read-only* (`readOnlyRootFilesystem: true`).

#### GitOps & Deployment State
- [ ] **Target Repo Separation**: Repositori kode aplikasi harus terpisah secara fisik dari repositori konfigurasi manifest GitOps (*separation of concerns*).
- [ ] **Anti-Snowflake Configuration**: Tidak boleh ada modifikasi manual di cluster via `kubectl`. Seluruh akses modifikasi di-revoke via IAM/RBAC selain privilege milik ServiceAccount ArgoCD.
- [ ] **Sync Windows**: Menentukan blokade waktu sinkronisasi otomatis (*ArgoCD SyncWindows*) di luar jam kerja operasional kritis untuk mencegah automated deployment saat peak load.

#### Telemetry & Progressive Rollouts
- [ ] **Statistically Significant Traffic**: Pastikan sampling metrik canary memiliki volume minimum request (misal: `count(http_requests_total) > 100`) sebelum menarik kesimpulan analisis sukses/gagal.
- [ ] **Graceful Termination Handlers**: Aplikasi wajib menangkap sinyal `SIGTERM` dan menyelesaikan inflight HTTP requests dalam batas `terminationGracePeriodSeconds`.

---

### 12. Hands-on Practice

Struktur direktori kerja:
```
hands-on/m02/
├── manifests/
│   ├── analysis-template.yaml
│   ├── rollout.yaml
│   └── service.yaml
└── policies/
    ├── container_security.rego
    └── container_security_test.rego
```

#### Langkah 1: Persiapan Workspace
Jalankan di terminal lokal Anda:
```bash
mkdir -p hands-on/m02/manifests hands-on/m02/policies
cd hands-on/m02
```

#### Langkah 2: Menulis Unit Test Policy OPA
Buat file `policies/container_security_test.rego` untuk memverifikasi rule sebelum diterapkan:
```rego
package kubernetes.admission

test_block_root_container {
    input := {
        "request": {
            "object": {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "malicious-app",
                                    "image": "registry.enterprise.internal/app:v1",
                                    "securityContext": {"runAsNonRoot": false},
                                    "resources": {"limits": {"memory": "256Mi"}}
                                }
                            ]
                        }
                    }
                }
            }
        }
    }
    count(violations) > 0
}

test_allow_valid_container {
    input := {
        "request": {
            "object": {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "safe-app",
                                    "image": "registry.enterprise.internal/app:v1",
                                    "securityContext": {"runAsNonRoot": true},
                                    "resources": {"limits": {"memory": "256Mi"}}
                                }
                            ]
                        }
                    }
                }
            }
        }
    }
    allow
}
```

#### Langkah 3: Eksekusi Validasi Policy Lokal Menggunakan OPA CLI
```bash
# Unduh binary OPA jika belum tersedia
curl -L -o opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64
chmod +x ./opa

# Jalankan unit testing suite
./opa test policies/ -v
```
*Ekspektasi Output*:
```
data.kubernetes.admission.test_block_root_container: PASS (0.8ms)
data.kubernetes.admission.test_allow_valid_container: PASS (0.3ms)
-------------------------------------------------------------------
PASS: 2/2
```

#### Langkah 4: Terapkan Service Manifest ke Kubernetes Cluster
Tulis file `manifests/service.yaml`:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: payment-engine-stable
  namespace: core-finance
spec:
  ports:
    - port: 80
      targetPort: 8080
      name: http
  selector:
    app.kubernetes.io/name: payment-engine
---
apiVersion: v1
kind: Service
metadata:
  name: payment-engine-canary
  namespace: core-finance
spec:
  ports:
    - port: 80
      targetPort: 8080
      name: http
  selector:
    app.kubernetes.io/name: payment-engine
```

Deploy komponen dependency:
```bash
kubectl create namespace core-finance --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f manifests/service.yaml
kubectl apply -f manifests/analysis-template.yaml
kubectl apply -f manifests/rollout.yaml
```

#### Langkah 5: Pantau Eksekusi Rollout Secara Real-Time
Gunakan plugin Argo Rollouts untuk melihat visualisasi status pergeseran trafik:
```bash
# Menonton siklus hidup pod dan traffic weight
kubectl argo rollouts get rollout payment-processing-engine -n core-finance --watch
```

---

### 13. Exercise

#### Level: Easy
- **Tugas**: Tambahkan validasi ke file Rego `container_security.rego` yang memvalidasi bahwa tidak ada container yang berjalan dengan flag `privileged: true`.
- **Kriteria Keberhasilan**: Test case OPA mendeteksi pod dengan security context `privileged: true` dan menghasilkan pesan: `"Privileged containers are strictly forbidden"`.

#### Level: Medium
- **Tugas**: Modifikasi `manifests/analysis-template.yaml` untuk menyertakan metrik ketiga: memvalidasi bahwa persentase HTTP 4xx tidak melebihi 5% dari keseluruhan traffic transaksi.
- **Kriteria Keberhasilan**: Manifest AnalysisTemplate valid secara sintaks dan dapat dievaluasi terhadap query Prometheus `status=~"4.*"`.

#### Level: Hard
- **Tugas**: Rancang deklarasi Terragrunt modular multi-region yang mengabstraksi pembuatan Amazon EKS Cluster. Modul harus memastikan state tersimpan secara terisolasi pada backend S3 yang terenkripsi SSE-KMS, dengan DynamoDB lock table di Region `ap-southeast-1` dan `ap-southeast-3`. Cegah penghapusan resource kritis dengan memanfaatkan dependensi eksplisit `prevent_destroy`.
- **Kriteria Keberhasilan**: Validasi `terragrunt run-all plan` mengeksekusi dependensi hierarki tanpa error state race-condition.

---

### 14. Challenge

#### Skenario Kasus Kompleks: "The Zero-Trust Financial Reconciliation Disaster"
Sebuah konglomerat fintech internasional mengalami kegagalan deployment intermiten yang parah di seluruh environment production mereka. 
- **Arsitektur Saat Ini**: 
  - Mereka memiliki 8 Kubernetes Cluster yang tersebar di AWS, GCP, dan On-Premises bare-metal.
  - Menggunakan arsitektur multi-tenancy dengan Istio Service Mesh, HashiCorp Vault via Agent Injector untuk dynamic secrets, dan ArgoCD untuk manajemen GitOps terpusat (*Control-Plane Cluster memanage Managed-Data-Plane Clusters*).
- **Insiden Runtime**:
  Setiap kali deployment skala besar (lebih dari 10 microservices secara simultan) dieksekusi melalui GitOps:
  1. Koneksi API Server pada cluster target mengalami lonjakan *throttling* ekstrem (HTTP 429 Too Many Requests).
  2. HashiCorp Vault Agent Injector gagal me-render database credentials ke sidecar container tepat waktu, memicu cascade failure `CrashLoopBackOff`.
  3. Argo Rollouts salah menginterpretasikan `CrashLoopBackOff` sebagai kegagalan aplikasi murni dan meluncurkan abort command, yang ironisnya membanjiri API Server lebih parah lagi dengan ribuan event pembersihan pod per detik.
  4. Dalam 4 menit, Ingress Gateway cluster target kolaps sepenuhnya.

#### Ekspektasi Tugas Pemecahan Masalah Arsitektur:
Sebagai Principal DevOps & Platform Architect, sajikan dokumen perancangan arsitektur mitigasi (*Architectural Remediation Proposal*) tanpa menggunakan solusi instan "restart cluster" atau "naikkan spesifikasi node". Rancangan Anda harus menguraikan:
1. **Flow Control & API Protection**: Restrukturisasi topologi ArgoCD untuk mengeliminasi centralized API bottlenecks (apakah beralih ke Autonomous GitOps Agents di setiap cluster? Bagaimana sinkronisasi state konsisten tetap terjaga?).
2. **Secret Lifecycle Re-architecture**: Solusi penggantian dynamic secret injection on-pod initialization untuk menghindari ketergantungan fatal antara cold startup pod dan response rate API Vault.
3. **Rollout Failure Circuit Breakers**: Desain pengkondisian *AnalysisTemplate* agar mampu membedakan anomali kegagalan *infrastruktur dependensi* (seperti gagal inject secret) dengan anomali *kegagalan logic kode aplikasi* agar tidak memicu badai pembatalan (*rollback storms*).

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa perbedaan mendasar antara mekanisme rekonsiliasi berbasis *Pull* (GitOps) dibandingkan dengan pendekatan pipeline *Push* konvensional?
2. Mengapa penggunaan tag mutable seperti `:latest` pada manifest Kubernetes dianggap sebagai anti-pattern fatal pada lingkungan enterprise?
3. Pada siklus Kubernetes Admission Controller, fase mana yang dieksekusi terlebih dahulu: Mutating Admission Webhook atau Validating Admission Webhook? Mengapa urutannya demikian?
4. Apa fungsi dari anotasi `Last Applied Configuration` dalam proses three-way merge patch Kubernetes?
5. Mengapa penyimpanan file state Terraform (*.tfstate*) pada Git repository lokal dilarang keras, dan mekanisme apa yang mutlak digunakan di production?

#### B. Pertanyaan Intermediate
6. Jelaskan bagaimana ArgoCD menangani konflik ketika controller Horizontal Pod Autoscaler (HPA) memodifikasi `replicas` aplikasi secara independen dari nilai yang dideklarasikan di Git repository!
7. Dalam progressive delivery menggunakan Canary deployment, mengapa metrik `p99 latency` jauh lebih esensial untuk dievaluasi dibandingkan `average latency`?
8. Bagaimana cryptographic image attestation menggunakan Cosign bekerja sama dengan Validating Webhook OPA Gatekeeper untuk menghentikan ancaman supply chain attack (*tampering*)?
9. Jelaskan skenario di mana konfigurasi OPA `failurePolicy: Fail` dapat melumpuhkan seluruh cluster Kubernetes Anda secara sistemik!
10. Bagaimana Anda mengonfigurasi `AnalysisTemplate` pada Argo Rollouts agar pod canary tidak langsung dibatalkan (*aborted*) hanya karena menerima *traffic spike* sesaat yang bersifat non-persistent?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Cluster Kubernetes Anda menerapkan ArgoCD untuk GitOps. Seorang teknisi on-call yang panik karena adanya insiden darurat tengah malam menggunakan akses admin darurat untuk mengubah image Deployment secara langsung via command `kubectl set image deployment/core-service app=bugfix:v2`. Deskripsikan secara akurat apa yang akan dilakukan oleh controller ArgoCD dalam default behavior-nya, dan bagaimana seharusnya workflow darurat (*hotfix protocol*) dieksekusi secara benar di GitOps!
12. **Skenario 2**: Anda menjalankan Canary deployment menggunakan Argo Rollouts. Analisis metrik Prometheus Anda menggunakan kueri rate HTTP error 5xx. Namun, saat canary pod baru diluncurkan dan hanya menerima 5% traffic, Prometheus query mengembalikan nilai `NaN` atau `no data`, yang menyebabkan AnalysisRun langsung berstatus `Error` dan membatalkan deployment. Apa akar masalah query PromQL tersebut, dan bagaimana cara menulis query yang resilient terhadap volume traffic rendah?
13. **Skenario 3**: Sebuah aplikasi perbankan modern membutuhkan zero connection drop selama rilis canary. Namun, klien eksternal melaporkan adanya error `HTTP 502 Bad Gateway` secara berkala selama beberapa detik tepat saat pod canary versi lama dimatikan oleh Argo Rollouts. Analisis rangkaian peristiwa teknis pada networking Kubernetes yang menyebabkan masalah ini, dan bagaimana kombinasi `preStop hook`, `readinessProbe`, dan konfigurasi `terminationGracePeriodSeconds` menyelesaikannya secara tuntas!

---

### 16. Summary

1. **Paradigma GitOps Enterprise** mentransformasi Git menjadi *single source of truth* absolut. Operasi kluster tidak lagi bergantung pada kredensial administratif yang tersebar di runner CI eksternal, melainkan dieksekusi oleh operator internal yang menjaga *convergence* antara desired state dan runtime state via *three-way merge loops*.
2. **Progressive Delivery** mengabstraksi proses deployment dari "peristiwa berisiko tinggi" menjadi eksperimen telemetri terkontrol. Mengintegrasikan Argo Rollouts dengan Prometheus memungkinkan verifikasi algoritma kesehatan perangkat lunak secara kuantitatif sebelum beban dialihkan penuh.
3. **Supply Chain Security & Policy-as-Code** adalah fondasi tata kelola modern. Penggunaan OPA/Gatekeeper dan Cosign menjamin bahwa hanya artefak yang terverifikasi, terisolasi secara sandboxing (*rootless*), dan bebas dari eskalasi hak akses yang diizinkan melintasi batas admission cluster produksi.
4. **Resiliensi Deployment** ditentukan oleh penanganan detail level sistem: mitigasi *race condition* antara HPA dan GitOps, penerapan *graceful connection draining* pada TCP lifecycle pod, dan pembuatan metrik evaluasi yang kebal terhadap *cold-start noise*.