# BAB 10: MATERI LANJUTAN
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang & Mengimplementasikan Arsitektur Produksi Zero-Downtime**: Mengonfigurasi strategi deployment mutakhir (*Canary Releases* dan *Blue/Green*) menggunakan *Traffic Splitting*, *Service Mesh*, atau *Advanced Ingress Controller* dengan verifikasi otomatis berbasis metrik.
2. **Mengamankan Secret Management Tingkat Enterprise**: Menerapkan *Zero-Trust Secret Injection* berbasis *Envelope Encryption*, integrasi Identity Provider (OIDC/IAM), dan *Dynamic Secret Generation* (HashiCorp Vault / AWS Secrets Manager) menggantikan *hardcoded credentials* dan Kubernetes Secret standar.
3. **Membangun Resilient & Self-Healing Platform**: Mengatur toleransi kegagalan (*fault-tolerance*) infrastruktur melalui konfigurasi *Pod Disruption Budgets* (PDB), *Horizontal Pod Autoscaler* (HPA) berbasis metrik kustom (KEDA), *Cluster Autoscaler*, dan *Multi-AZ high availability*.
4. **Menganalisis Telemetri Produksi (Observability Engineering)**: Merumuskan metrik SLI/SLO (*Service Level Indicators* / *Service Level Objectives*), menetapkan *Error Budgets*, serta melacak insiden menggunakan *distributed tracing* (OpenTelemetry), log terstruktur, dan alerting proaktif.
5. **Mengaudit & Mengatasi Insiden Sistemik (Troubleshooting Lanjutan)**: Menemukan akar permasalahan (*Root Cause Analysis* / RCA) pada level kernel, jaringan, dan alokasi sumber daya (*OOMKilled*, *DNS Throttling*, *Thread Starvation*, dan *Cascading Failures*).

---

### 2. Prerequisite

Untuk mencerna materi ini secara optimal, peserta wajib menguasai:
* **Linux Kernel Basics**: Pemahaman *namespaces*, *cgroups*, signal termination (`SIGTERM`, `SIGKILL`), dan layer jaringan Linux (*iptables*, *eBPF*).
* **Containerization**: OCI runtime specifications, multi-stage builds, rootless container security context, serta image provenance & signing.
* **Kubernetes Core**: Lifecycle Pod, Controller runtime (*Reconciliation Loop*), Service mesh fundamentals, CNI (*Container Network Interface*), dan CSI (*Container Storage Interface*).
* **Networking Protocol**: TCP/IP stack, TLS 1.3 handshake, HTTP/2 multiplexing, gRPC, keep-alive timeouts, serta reverse proxy mechanics.
* **Kakas yang Digunakan**: Kubernetes v1.28+, Terraform v1.6+, Argo Rollouts / ArgoCD, Helm v3, Prometheus stack, dan HashiCorp Vault.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Reconciliation Loop & Declarative State Machine
Pada arsitektur cloud-native modern, sistem beroperasi berdasarkan prinsip deklaratif. Di dalam Kubernetes Controller Manager dan GitOps engine (seperti ArgoCD), terdapat komponen kritis bernama **Reconciliation Loop**:

$$\text{Reconciliation Loop}: \text{Diff}(\text{Desired State}, \text{Observed State}) \to \text{Action Plan} \to \text{Execution}$$

1. **Observe**: Kubelet dan Custom Controller memantau status terkini (*Observed State*) dari etcd dan API server.
2. **Analyze**: Mesin membandingkan *Observed State* terhadap konfigurasi yang dideklarasikan di Git repository (*Desired State*).
3. **Act**: Apabila terdapat deviasi (*drift* atau kegagalan node), *Action Loop* mengeksekusi instruksi rekonsiliasi (misalnya: menjadwalkan ulang pod, membuat rute jaringan baru, memicu eviksi).

```
+------------------------------------------------------------------------------------+
|                               KUBERNETES CONTROL PLANE                              |
|                                                                                    |
|  +--------------+        gRPC        +------------------+       +---------------+  |
|  |  Git / CI    | -----------------> |  k8s API Server  | <---> |     etcd      |  |
|  +--------------+                    +------------------+       +---------------+  |
|                                         ^        ^                                 |
|                  +----------------------+        +--------------------+            |
|                  | Watch / Event Sync                                 |            |
|                  v                                                    v            |
|        +--------------------+                               +--------------------+ |
|        | Deployment/Rollout |                               | Kube-Scheduler     | |
|        | Controller         |                               |                    | |
|        +--------------------+                               +--------------------+ |
+------------------|----------------------------------------------------|------------+
                   | Reconciliation (CRUD Pods)                         | Bind Nodes
                   v                                                    v
+------------------------------------------------------------------------------------+
|                                  WORKER NODE (DATA PLANE)                          |
|                                                                                    |
|  +--------------------+     CRI (containerd)     +-------------------------------+ |
|  |      Kubelet       | -----------------------> | Pod Sandbox (Pause Container) | |
|  +--------------------+                          |   ├── Network Namespace       | |
|            |                                     |   ├── Cgroup Limits (Memory)  | |
|            v                                     |   └── Application Container   | |
|  +--------------------+                          +-------------------------------+ |
|  |     kube-proxy     | ---> iptables / IPVS / eBPF rules                          |
|  +--------------------+                                                            |
+------------------------------------------------------------------------------------+
```

#### 3.2. Lifecycle Pod: Graceful Termination vs Hard Kill
Kegagalan memahami alur pemutusan koneksi (*pod termination lifecycle*) adalah penyebab utama lonjakan HTTP 502/504 saat proses *rolling update*. Alur internal terminasi pod:

```
[Event: Pod Deletion Triggered via Deployment/Rollout Update]
                          |
        +-----------------+-----------------+
        |                                   |
        v                                   v
[1. Pod Status set to 'Terminating']   [2. Endpoint Controller removes Pod IP]
        |                                   |
        v                                   v
[preStop Hook executed]               [Endpoints update propagated to kube-proxy,
        |                              Ingress, CoreDNS, & Service Mesh (takes ~2-5s)]
        v                                   |
[SIGTERM sent to PID 1]                     |
        |                                   |
[App stops accepting new conns,             |
 finishes in-flight requests]               |
        |                                   v
        +-----------------+-----------------+
                          |
                          v
         [Connection draining complete?]
              /                       \
           Yes                         No (Timeout reached)
            /                             \
           v                               v
[Container exits normally]        [SIGKILL sent forcefully]
```
> **Konsekuensi Arsitektur**: Tanpa eksekusi `preStop: sleep 10` dan pengelolaan *graceful shutdown* di kode aplikasi, *kube-proxy* atau *Ingress Controller* masih berpotensi merutekan traffic baru ke Pod yang sudah menghentikan *thread pool*-nya.

#### 3.3. Envelope Encryption & Dynamic Secret Injection
Menyimpan secret sebagai *Base64* di Kubernetes `Secret` melanggar standar kepatuhan regulasi (PCI-DSS, SOC2, ISO27001). Model arsitektur enterprise menggunakan **Envelope Encryption** dan **Mutating Admission Webhooks**:

1. **Master Key (KEK - Key Encryption Key)**: Disimpan di Hardware Security Module (HSM) atau Cloud KMS (AWS/GCP/Azure).
2. **Data Key (DEK - Data Encryption Key)**: Dihasilkan secara dinamis untuk mengenkripsi payload data. DEK kemudian dienkripsi oleh KEK dan disimpan berdampingan dengan ciphertext.
3. **Secret Injection via Webhook**: Agen Vault tidak menyimpan kredensial permanen di disk. Menggunakan *In-Memory Shared Volume* (`tmpfs`), mutating webhook menyuntikkan token dinamis dengan TTL singkat langsung ke memory space container aplikasi.

---

### 4. Why & What

| Dimensi Arsitektur | Pola Konvensional (Naive / Non-Production) | Pola Modern Enterprise Production |
| :--- | :--- | :--- |
| **Deployment Strategy** | *Recreate* (downtime total) atau *RollingUpdate* standar tanpa verifikasi metrik. | *Canary Release* berbasis *Service Mesh* (Istio/Linkerd) atau Argo Rollouts dengan *Automated Rollback* jika error rate > 0.5%. |
| **Konfigurasi Secret** | Environment variables statis yang ditarik dari Git atau Kubernetes Secret *base64-encoded*. | *External Secrets Operator* / *Vault Agent Injector* dengan *short-lived credentials* dan auto-rotation via mTLS. |
| **Scaling & Resource** | Fixed replica count, alokasi `resources.limits` serampangan, scaling reaktif via VM autoscaler. | Predictive autoscaling dengan KEDA (berdasarkan metrik queue/Kafka lag), PDB untuk garansi quorum, dan *cgroup v2 awareness*. |
| **Jaringan & Akses** | Flat network, public subnet exposed, pod-to-pod communication sepenuhnya terbuka. | *Micro-segmentation* menggunakan Kubernetes NetworkPolicy default-deny, mTLS otomatis, and explicit egress routing. |
| **Observability** | Log manual di file lokal, monitoring CPU/RAM standar, debugging insiden pasca-kegagalan. | *OpenTelemetry distributed tracing*, SLI/SLO dashboarding, *continuous profiling*, dan *synthetic canary probing*. |

---

### 5. How (Workflow Detail)

Alur kerja implementasi arsitektur produksi berfokus pada siklus rilis berbasis GitOps dan validasi progresif:

```
[Developer Push Code]
         |
         v
[CI: Build & Security Audit]
   - SAST (SonarQube)
   - Dependency Vulnerability Scan (Trivy)
   - OCI Image Build & Sign (Cosign)
         |
         v
[Update Helm Chart / Manifest Repo (GitOps)]
         |
         v
[GitOps Controller (ArgoCD) Reconciliation]
   - Detects state drift
   - Synchronizes manifests to Staging/Production Cluster
         |
         v
[Argo Rollouts Engine - Canary Lifecycle Initiated]
   ├── Step 1: Route 5% traffic to Canary Pods
   ├── Step 2: Prometheus Analysis Run (Query: HTTP 5xx rate < 0.1%, P99 Latency < 200ms)
   │     ├── Pass: Route 20% traffic -> Re-evaluate metrics
   │     └── Fail: Trigger Instant Automated Rollback (< 5 detik)
   ├── Step 3: Route 50% traffic -> Re-evaluate metrics
   └── Step 4: Promote Canary to Stable (100% traffic)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengujian Bahan Bakar Pesawat Komersial
Bayangkan sebuah pesawat berbadan ganda yang sedang terbang ribuan kilometer. Jika Anda ingin mengganti formulasi bahan bakar baru yang lebih efisien (Deployment Baru), Anda tidak langsung mematikan semua mesin dan mengisi tangki utama secara serentak. 

Sebaliknya, Anda mengalirkan 5% formula baru ke salah satu mesin sekunder sembari mengamati ratusan sensor vibrasi, suhu turbin, dan tekanan oli secara *real-time* (Canary Analysis). Jika sensor mendeteksi anomali 0.01% saja di atas batas toleransi, katup bahan bakar baru ditutup seketika, dan suplai dikembalikan penuh ke formula lama tanpa penumpang menyadari adanya transisi (Automated Rollback).

```
                      INTERNET TRAFFIC (Inbound 10,000 RPS)
                                       |
                                       v
                    +------------------------------------+
                    |     Enterprise Ingress Gateway     |
                    +------------------------------------+
                                       |
                     [Traffic Weight Split Controller]
                               /                \
                       90%    /                  \   10%
                             v                    v
              +-----------------------+  +-----------------------+
              |   STABLE REPLICA SET  |  |   CANARY REPLICA SET  |
              |     (Image: v1.4.0)   |  |     (Image: v1.5.0)   |
              |                       |  |                       |
              |  [Pod] [Pod] [Pod]    |  |        [Pod]          |
              +-----------------------+  +-----------------------+
                          |                          |
                          +------------+-------------+
                                       |
                                       v (Emit Real-time Telemetry)
                           +------------------------+
                           |  Prometheus / Datadog  |
                           +------------------------+
                                       |
                          (Query: error_rate > 0.01)
                                       |
                                       v
                         +---------------------------+
                         | Argo Rollout Controller   |
                         | Decision:                 |
                         |   -> Healthy: +10% step   |
                         |   -> Unhealthy: ABORT     |
                         +---------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Graceful Termination Pod Configuration
Konfigurasi dasar pod untuk mencegah *connection dropping* saat proses deployment bergulir:

```yaml
# simple-resilient-pod.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-api
  namespace: core-banking
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payment-api
  template:
    metadata:
      labels:
        app: payment-api
    spec:
      containers:
      - name: payment-service
        image: internal-registry.enterprise.io/banking/payment:1.2.0
        lifecycle:
          preStop:
            exec:
              # Berikan jeda waktu agar kube-proxy/ingress mencabut IP pod dari routing table
              command: ["/bin/sh", "-c", "sleep 15"]
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: "250m"
            memory: "512Mi"
          limits:
            cpu: "1000m"
            memory: "1Gi"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

#### 7.2. Practical Example: Enterprise Canary Deployment dengan Argo Rollouts & Prometheus Metrics
Konfigurasi kelas produksi yang mengombinasikan *Rollout*, *PodDisruptionBudget*, *NetworkPolicy*, dan analisis performa otomatis.

```yaml
# production-rollout.yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: order-processing-service
  namespace: ecommerce-production
  labels:
    app.kubernetes.io/name: order-processing
    app.kubernetes.io/part-of: checkout-engine
spec:
  replicas: 10
  revisionHistoryLimit: 5
  strategy:
    canary:
      analysis:
        templates:
        - templateName: success-rate-check
        args:
        - name: service-name
          value: order-processing-canary
      steps:
      - setWeight: 5
      - pause: { duration: 3m }
      - setWeight: 20
      - pause: { duration: 5m }
      - setWeight: 50
      - pause: { duration: 5m }
  selector:
    matchLabels:
      app: order-processing
  template:
    metadata:
      labels:
        app: order-processing
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/path: "/metrics"
        prometheus.io/port: "9090"
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "order-processor-role"
        vault.hashicorp.com/agent-inject-secret-db-creds: "database/creds/order-db-app"
        vault.hashicorp.com/agent-inject-template-db-creds: |
          {{- with secret "database/creds/order-db-app" -}}
          export DB_USER="{{ .Data.username }}"
          export DB_PASSWORD="{{ .Data.password }}"
          {{- end }}
    spec:
      terminationGracePeriodSeconds: 60
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - order-processing
              topologyKey: "topology.kubernetes.io/zone"
      containers:
      - name: engine
        image: internal-registry.enterprise.io/ecommerce/order-engine:v2.4.1
        imagePullPolicy: IfNotPresent
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          runAsNonRoot: true
          runAsUser: 10001
          capabilities:
            drop:
            - ALL
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 20"]
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP
        - name: metrics
          containerPort: 9090
          protocol: TCP
        resources:
          requests:
            cpu: "500m"
            memory: "1Gi"
          limits:
            cpu: "2000m"
            memory: "2Gi"
---
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate-check
  namespace: ecommerce-production
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
          sum(rate(http_requests_total{service="{{args.service-name}}",status=~"2..|3.."}[1m]))
          /
          sum(rate(http_requests_total{service="{{args.service-name}}"}[1m]))
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: order-processing-pdb
  namespace: ecommerce-production
spec:
  minAvailable: 80%
  selector:
    matchLabels:
      app: order-processing
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: order-processing-netpol
  namespace: ecommerce-production
spec:
  podSelector:
    matchLabels:
      app: order-processing
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-controllers
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - ipBlock:
        cidr: 10.200.0.0/16 # Database Subnet
    ports:
    - protocol: TCP
      port: 5432
  - to: # CoreDNS
    - namespaceSelector: {}
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario Kasus
* **Entitas**: Platform E-Commerce Tier-1 Nasional.
* **Skala Sistem**: 350.000 Request Per Second (RPS) pada event Flash Sale Harbolnas, didistribusikan ke 450 worker nodes pada multi-AZ Kubernetes cluster.
* **Insiden**: Saat rilis darurat (*hotfix*) versi checkout engine bergulir, terjadi lonjakan *HTTP 502 Bad Gateway* (mencapai 18% dari total traffic) selama 8 menit. Nilai kerugian diperkirakan mencapai USD 250,000 per menit kegagalan.

#### Analisis Akar Masalah (Root Cause Analysis - RCA)
1. **Race Condition pada Pod Deregistration**: Deployment menggunakan `RollingUpdate` default tanpa `preStop` hook. Kubelet langsung mengirimkan `SIGTERM` ke pod lama, sementara Ingress Controller (Nginx) masih menyimpan alamat IP pod lama di memori proxy upstream karena propagasi *Endpoints* memakan waktu rata-rata 3,2 detik. Nginx tetap merutekan paket SYN ke pod yang socket-nya sudah tertutup.
2. **Koneksi Database Habis (Connection Pool Exhaustion)**: Versi aplikasi baru menginisiasi pool koneksi DB (`max_connections`) terlalu agresif saat start-up. Ketika 50 pod baru menyala simultan, database PostgreSQL utama mengalami kegagalan *connection starvation*, menolak koneksi dari pod yang sudah berjalan (*cascading failure*).
3. **CoreDNS Throttling**: Ratusan pod baru yang menyala bersamaan memicu lonjakan query DNS UDP per detik ke CoreDNS, melampaui batas *conntrack* Linux pada worker node, menyebabkan resolusi DNS database gagal (*timeout*).

#### Solusi Remediasi Komprehensif
1. **Implementasi PreStop Hooks & Graceful Draining**: Menambahkan `sleep 20` pada seluruh manifest aplikasi agar Ingress Controller menyelesaikan pembaruan tabel rute upstream sebelum container menerima `SIGTERM`.
2. **Adopsi Argo Rollouts (Progressive Delivery)**: Mengganti strategi *RollingUpdate* dengan *Canary Release* berbasis evaluasi otomatis metrik Prometheus (Error rate < 0.1%, P99 Latency < 150ms).
3. **Optimasi Layer DNS & Database**: 
   * Mengaktifkan `NodeLocal DNSCache` pada setiap node untuk memotong lonjakan query DNS langsung ke CoreDNS.
   * Mengintegrasikan PgBouncer di layer tengah untuk multiplexing koneksi database, membatasi konsumsi resource koneksi DB oleh pod baru.

---

### 9. Trade-offs

| Pendekatan / Teknologi | Keuntungan (Pros) | Biaya / Kerugian (Cons) | Dampak Latensi & Performa | Konsekuensi Biaya Finansial |
| :--- | :--- | :--- | :--- | :--- |
| **Canary Deployment via Service Mesh** | *Zero impact* blast radius; visualisasi traffic per-route; rollback otomatis tanpa downtime. | Kompleksitas operasional sangat tinggi; konsumsi CPU/Memory tambahan untuk sidecar proxy (Envoy). | Menambahkan latensi proxy traversal (~1.5ms - 3ms per hop). | Meningkatkan kebutuhan resource node cluster sebesar 15-25%. |
| **Dynamic Secrets via Vault Webhook** | Tidak ada credential bocor di Git; rotasi otomatis; enkripsi *in-memory* (`tmpfs`). | Ketergantungan kritis pada ketersediaan cluster Vault; latensi tambahan saat startup Pod baru. | Latensi pod initialization bertambah 2 hingga 8 detik saat injeksi. | Membutuhkan infrastruktur HA Vault (minimal 3-5 node dedicated). |
| **Multi-AZ Pod Anti-Affinity** | Ketahanan bencana level infrastruktur (*zone outage tolerance*). | Penjadwalan (*scheduling*) menjadi kaku; potensi pod macet (*Pending*) jika kapasitas AZ tidak seimbang. | Nol latensi tambahan pada level aplikasi (latensi transit cross-AZ network berlaku). | Biaya transfer data cross-AZ pada cloud provider bertambah secara signifikan. |
| **Single Cluster vs Multi-Cluster Federation** | Manajemen terpusat; setup tooling CI/CD lebih sederhana. | Blast radius besar (kegagalan control plane berdampak ke seluruh sistem global). | Tidak ada overhead sinkronisasi lintas region. | Biaya lisensi/infrastruktur lebih murah dibanding memelihara multiple clusters. |

---

### 10. Common Mistakes & Troubleshooting

#### Failure Mode 1: OOMKilled (Exit Code 137) Akibat Silent Memory Leaks
* **Gejala**: Pod tiba-tiba menghilang atau restart secara berulang dengan status `OOMKilled`.
* **Mekanisme**: Penggunaan memory melebihi nilai `resources.limits.memory` yang dideklarasikan. Linux Kernel memicu *Out of Memory Killer* untuk mematikan proses dengan badness score tertinggi di cgroup tersebut.
* **Penyelidikan CLI**:
  ```bash
  kubectl describe pod <pod-name> -n <namespace> | grep -E "Exit Code|Last State|OOMKilled"
  kubectl top pod <pod-name> -n <namespace> --containers
  ```
* **Solusi**: Pisahkan profiling memory aplikasi menggunakan heap dump analysis (misal: pprof untuk Go, JXRay untuk Java). Tetapkan batas `requests.memory` sama dengan `limits.memory` untuk mengalokasikan QoS Class `Guaranteed` pada pod kelas tier-1.

#### Failure Mode 2: CrashLoopBackOff Akibat Race Condition Mount Secret/ConfigMap
* **Gejala**: Pod baru gagal start dan beralih ke status `CrashLoopBackOff` dengan interval restart eksponensial.
* **Mekanisme**: Aplikasi mengeksekusi inisialisasi runtime sebelum file secret yang disuntikkan via agent (Vault/CSI Driver) selesai terpasang di filesystem target.
* **Penyelidikan CLI**:
  ```bash
  kubectl logs <pod-name> -n <namespace> --previous
  kubectl get events -n <namespace> --field-selector involvedObject.name=<pod-name> --sort-by='.metadata.creationTimestamp'
  ```
* **Solusi**: Tambahkan *initContainer* untuk memverifikasi eksistensi file kredensial sebelum container utama dieksekusi, atau implementasikan *retry mechanism* di level koneksi database kode aplikasi.

#### Failure Mode 3: DNS Query Drop & Throttling
* **Gejala**: Latensi HTTP melonjak intermiten, log aplikasi menunjukkan kegagalan `getaddrinfo: Temporary failure in name resolution` atau `dial tcp: lookup timeout`.
* **Mekanisme**: Jumlah request DNS melebihi kapasitas thread CoreDNS atau terjadi race condition penulisan tabel Linux kernel `conntrack` via socket UDP port 53.
* **Penyelidikan CLI**:
  ```bash
  kubectl get ep kube-dns -n kube-system
  kubectl top pods -l k8s-app=kube-dns -n kube-system
  # Cek conntrack drops di level worker node
  conntrack -S
  ```
* **Solusi**: Terapkan `NodeLocal DNSCache` sebagai daemonset untuk mengubah komunikasi UDP DNS remote menjadi loopback lokal, serta ubah konfigurasi resolusi `/etc/resolv.conf` menggunakan `options single-request-reopen ndots:2`.

---

### 11. Best Practices (Production Checklist)

#### Pre-Flight Checklist
- [ ] **Image Provenance**: Setiap container image wajib diverifikasi menggunakan tanda tangan digital kriptografis (Cosign / Sigstore) dan bebas dari celah kritis (CVE Critical: 0).
- [ ] **QoS Tier Alignment**: Pod tier-1 wajib memiliki konfigurasi memory `request == limit` untuk mencegah penghentian mendadak oleh kernel (*Guaranteed QoS*).
- [ ] **Security Context Compliance**: `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, dan `capabilities.drop: ["ALL"]` aktif pada seluruh deployment produksi.

#### In-Flight Lifecycle Checklist
- [ ] **Graceful Shutdown**: Implementasi termination handler aplikasi untuk menangkap `SIGTERM`, menyelesaikan in-flight requests, dan menutup resource pools secara bersih.
- [ ] **Lifecycle PreStop Hook**: Menambahkan delay (`sleep 10-20 detik`) di hook lifecycle container untuk sinkronisasi penghapusan Endpoint di Ingress proxy.
- [ ] **Readiness Probe Tuning**: Konfigurasi `failureThreshold` dan `periodSeconds` yang realistis agar pod tidak menerima traffic saat sedang *heavy loading* atau inisialisasi awal.

#### Post-Flight Operational Checklist
- [ ] **Pod Disruption Budget (PDB)**: Didefinisikan pada seluruh microservice penting untuk menjaga quorum saat *drain* node atau *rolling upgrade* cluster.
- [ ] **Affinity & Anti-Affinity**: Konfigurasi `podAntiAffinity` aktif lintas Availability Zone guna memitigasi risiko *zone failure*.
- [ ] **Network Isolation**: Namespace produksi wajib menerapkan NetworkPolicy `default-deny-all` untuk Ingress dan Egress.

---

### 12. Hands-on Practice

Buat seluruh struktur direktori dan file berikut di bawah folder direktori proyek Anda: `hands-on/m02/`.

#### Langkah 1: Setup Lingkungan Kerja
Siapkan struktur direktori lokal Anda:
```bash
mkdir -p hands-on/m02/manifests
cd hands-on/m02
```

#### Langkah 2: Buat Analisis Metrik Rollout
Tuliskan konfigurasi analisis Prometheus untuk memantau performa HTTP request selama fase canary deployment:

```yaml
# hands-on/m02/manifests/analysis-template.yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: latency-and-error-analysis
  namespace: default
spec:
  metrics:
  - name: error-rate
    interval: 15s
    count: 3
    successCondition: result[0] <= 0.01
    failureLimit: 1
    provider:
      prometheus:
        address: http://prometheus-server.monitoring.svc.cluster.local:9090
        query: |
          sum(rate(http_requests_total{status=~"5.*",app="demo-app"}[30s])) 
          / 
          sum(rate(http_requests_total{app="demo-app"}[30s])) or on() vector(0)
```

#### Langkah 3: Buat Rollout Manifest
Buat arsitektur deployment Canary dengan langkah bertahap:

```yaml
# hands-on/m02/manifests/rollout.yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: demo-app
  namespace: default
spec:
  replicas: 4
  revisionHistoryLimit: 3
  strategy:
    canary:
      analysis:
        templates:
        - templateName: latency-and-error-analysis
      steps:
      - setWeight: 25
      - pause: { duration: 30s }
      - setWeight: 50
      - pause: { duration: 30s }
  selector:
    matchLabels:
      app: demo-app
  template:
    metadata:
      labels:
        app: demo-app
    spec:
      terminationGracePeriodSeconds: 30
      containers:
      - name: web
        image: argoproj/rollouts-demo:blue
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 5"]
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 200m
            memory: 256Mi
```

#### Langkah 4: Buat Service & Pod Disruption Budget
Definisikan kestabilan perutean traffic dan kuorum pod:

```yaml
# hands-on/m02/manifests/service-pdb.yaml
apiVersion: v1
kind: Service
metadata:
  name: demo-app
  namespace: default
spec:
  ports:
  - port: 80
    targetPort: 8080
  selector:
    app: demo-app
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: demo-app-pdb
  namespace: default
spec:
  minAvailable: 75%
  selector:
    matchLabels:
      app: demo-app
```

#### Langkah 5: Eksekusi dan Verifikasi Deployment
Jalankan perintah-perintah berikut untuk mengeksekusi dan mengamati canary progression:
```bash
# 1. Apply semua manifest
kubectl apply -f manifests/

# 2. Pantau status rollout secara interaktif (perlu instalasi kubectl argo rollouts plugin)
kubectl argo rollouts get rollout demo-app --watch

# 3. Picu update ke image 'yellow' (kondisi normal)
kubectl argo rollouts set image demo-app web=argoproj/rollouts-demo:yellow

# 4. Picu rilis rusak (image yang memancarkan error rate tinggi) untuk menguji Automated Rollback
kubectl argo rollouts set image demo-app web=argoproj/rollouts-demo:bad-red
```

---

### 13. Exercise

#### Level Easy
Konfigurasikan manifest `PodDisruptionBudget` (PDB) untuk sistem pembayaran bernama `payment-gateway` yang memiliki total 6 replika. Tetapkan batasan bahwa sistem tidak boleh mentoleransi kehilangan lebih dari 2 pod aktif secara bersamaan selama maintenance node cluster (`drain`).

#### Level Medium
Buatlah konfigurasi `NetworkPolicy` bernama `secure-vault-access` di namespace `backend` yang memberlakukan aturan berikut:
1. Menolak seluruh traffic ingress dan egress secara default (*default-deny*).
2. Hanya mengizinkan ingress ke port HTTP `8080` dari pod yang memiliki label `role: frontend`.
3. Mengizinkan egress hanya ke HashiCorp Vault server pada namespace `vault-system` di port TCP `8200`, serta DNS port `53` (UDP).

#### Level Hard
Rancang arsitektur deployment Canary bertingkat (5%, 25%, 50%, 100%) menggunakan **Argo Rollouts** yang terintegrasi dengan **Prometheus Analysis**. Persyaratan sistem:
* Metrik evaluasi mengukur HTTP P99 Latency: jika latensi di atas 250ms selama 2 kali interval pengecekan berturut-turut, proses rilis wajib dibatalkan (*aborted*) dan sistem harus melakukan rollback instan ke versi stabil.
* Pasang `initContainer` yang menguji keterhubungan socket database PostgreSQL sebelum container utama dijalankan.
* Pastikan container utama berjalan dengan filesystem *read-only* murni dan non-root user (UID 10005).

---

### 14. Challenge

**Studi Kasus: Insiden "Cascading Brownout" Sistem Perbankan**

Sebuah platform *digital banking* mengalami insiden besar saat jam sibuk:
* Setiap kali cluster worker nodes berskala naik (*scale-out*) via Cluster Autoscaler dari 100 node menjadi 180 node akibat lonjakan transaksi, 30% dari pod yang sudah berjalan mengalami *readiness probe failure*, memicu siklus pemusnahan (*termination*) dan pembuatan (*re-creation*) massal yang tak berkesudahan (*cascading restart*).
* Tim aplikasi bersikeras bahwa kode microservice mereka bersih dan tidak mengalami memory leak.
* Tim cloud platform mencatat adanya packet drop yang parah di antarmuka virtual worker node, sementara utilitas CPU dan RAM node baru masih berada di bawah 25%.

**Tugas Anda:**
1. Formulasikan hipotesis teknis di level kernel OS dan Kubernetes networking yang mendasari fenomena tersebut.
2. Identifikasi 3 metrik spesifik Linux kernel subsystem (`/proc/sys/net/...`) dan Kubernetes components yang wajib diperiksa secara forensik.
3. Rancang arsitektur penanganan komprehensif yang mencakup optimasi sysctl node, penjadwalan pod, dan isolasi jaringan untuk mencegah terulangnya insiden brownout tersebut secara permanen. *(Kerjakan tanpa bantuan solusi otomatis; dokumentasikan langkah troubleshooting Anda secara terstruktur).*

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic (Pilihan Ganda)
1. Apa fungsi utama dari deklarasi lifecycle `preStop: exec: command: ["sleep", "15"]` pada sebuah manifest deployment Kubernetes?
   * A. Menunda inisialisasi aplikasi sampai database siap menerima query.
   * B. Memberi waktu bagi ingress controller dan proxy jaringan untuk menghapus IP pod dari daftar endpoint aktif sebelum aplikasi berhenti.
   * C. Mencegah kernel Linux memicu signal SIGKILL saat timeout terlewati.
   * D. Mengurangi konsumsi memori container sesaat sebelum dimatikan.

2. Mekanisme cgroup v2 Linux memberlakukan batas alokasi memori container. Apa yang terjadi jika proses di dalam container melampaui deklarasi `resources.limits.memory`?
   * A. CPU akan otomatis di-*throttle* ke batas minimum.
   * B. Proses akan mengalami crash dengan exit code 0.
   * C. Linux OOM Killer mengirim sinyal SIGKILL (Exit Code 137) ke proses di container tersebut.
   * D. Pod otomatis dialihkan ke status Evicted dan dipindahkan ke node lain.

3. Apa perbedaan mendasar antara *RollingUpdate* standar Kubernetes dengan *Progressive Delivery (Canary)* via Argo Rollouts?
   * A. RollingUpdate berjalan tanpa downtime sama sekali, sedangkan Canary memerlukan maintenance window.
   * B. Canary Deployment dapat mengalokasikan pecahan traffic tertentu berdasarkan routing rules dan menganalisis metrik real-time sebelum melanjutkan promosi rilis.
   * C. RollingUpdate membutuhkan minimal 2 cluster fisik terpisah.
   * D. Argo Rollouts tidak menggunakan replika pod tambahan selama proses deployment.

4. Manakah komponen Kubernetes yang bertugas menjaga kesesuaian antara *Desired State* di etcd dan *Observed State* di cluster melalui reconciliation loop?
   * A. Kube-Scheduler
   * B. Kube-Proxy
   * C. Kube-Controller-Manager
   * D. Container Network Interface (CNI)

5. Mengapa menyimpan secret di Kubernetes manifest dalam format base64 murni dianggap sebagai pelanggaran keamanan standar enterprise?
   * A. Format Base64 rentan terhadap serangan SQL Injection.
   * B. Base64 hanyalah metode *encoding*, bukan mekanisme enkripsi; siapa pun yang memiliki akses baca dapat mendekripsinya secara instan tanpa kunci.
   * C. Kubelet tidak dapat membaca secret jika string base64 memiliki panjang lebih dari 256 karakter.
   * D. Base64 memperlambat parsing API Server Kubernetes hingga 50%.

---

#### Soal Intermediate (Pilihan Ganda & Analisis)
6. Sebuah cluster Kubernetes menjalankan CoreDNS. Saat terjadi lonjakan pembuatan ribuan pod serentak, resolusi DNS mulai mengalami kegagalan *timeout* 5 detik secara acak. Solusi arsitektural yang paling tepat untuk mengatasi masalah ini adalah:
   * A. Mengganti semua nama domain Service di aplikasi menggunakan alamat IP statis.
   * B. Mengimplementasikan `NodeLocal DNSCache` pada setiap node untuk melayani query DNS dari cache lokal node via loopback interface.
   * C. Meningkatkan alokasi `limits.cpu` pada pod aplikasi menjadi 4x lipat.
   * D. Menghapus ConfigMap CoreDNS agar resolusi kembali langsung ke DNS upstream cloud.

7. Perhatikan konfigurasi PodDisruptionBudget berikut:
   ```yaml
   apiVersion: policy/v1
   kind: PodDisruptionBudget
   metadata:
     name: auth-pdb
   spec:
     maxUnavailable: 0
     selector:
       matchLabels:
         app: auth-service
   ```
   Apa dampak arsitektural dari konfigurasi di atas jika seorang Site Reliability Engineer (SRE) menjalankan perintah `kubectl drain <node-name>` untuk maintenance OS?
   * A. Seluruh pod `auth-service` akan langsung dihapus tanpa menunggu.
   * B. Perintah `kubectl drain` akan macet (*blocked* tanpa batas waktu) karena cluster tidak diizinkan memiliki 0 pod yang *unavailable*.
   * C. Node maintenance berjalan normal karena PDB hanya berlaku untuk kejadian tidak terduga (*unvoluntary disruptions*).
   * D. Kubelet akan menggandakan replika pod di node lain secara otomatis dalam hitungan milidetik.

8. Dalam envelope encryption yang diterapkan oleh cloud KMS atau HashiCorp Vault, peran dari Data Encryption Key (DEK) adalah:
   * A. Mengenkripsi master key yang tersimpan di Hardware Security Module (HSM).
   * B. Mengenkripsi payload data sensitif secara lokal, di mana DEK itu sendiri kemudian dienkripsi oleh Key Encryption Key (KEK).
   * C. Menghubungkan kube-apiserver dengan etcd melalui mTLS handshake.
   * D. Mengamankan file `/etc/shadow` pada host OS worker node.

9. Jika pod aplikasi Anda sering mengalami restart dengan exit code 143, apa arti dari kondisi tersebut secara internal sistem?
   * A. Aplikasi Anda mengalami segmentasi memori (*Segmentation Fault*).
   * B. Aplikasi dihentikan secara graceful oleh sinyal `SIGTERM` (128 + 15), namun memakan waktu lebih lambat dari `terminationGracePeriodSeconds` sehingga akhirnya dipaksa berhenti.
   * C. Container dibunuh karena kegagalan pada Liveness Probe secara berulang-ulang.
   * D. Terjadi kegagalan I/O pada CSI persistent storage yang terpasang.

10. Manakah dari parameter `sysctl` Linux berikut yang jika nilainya terlalu rendah dapat menyebabkan drop paket TCP secara masif saat traffic HTTP masuk melonjak drastis pada worker node Kubernetes berkapasitas besar?
    * A. `fs.file-max`
    * B. `net.core.somaxconn`
    * C. `kernel.pid_max`
    * D. `vm.swappiness`

---

#### Soal Kasus Produksi (Analisis & Esai Teknis)
11. **Kasus A: Broken Pipe saat Rolling Deployment**
    * **Kondisi**: Sebuah layanan API FinTech menggunakan Kubernetes Deployment standar dengan `strategy: RollingUpdate` (`maxSurge: 25%`, `maxUnavailable: 0`). Selama rilis pipeline CI/CD berlangsung pada siang hari, sistem monitoring mencatat peningkatan drastis error rate `502 Bad Gateway` dan client melaporkan *connection reset by peer* (`ECONNRESET`).
    * **Pertanyaan**: Jelaskan secara mendalam interaksi antara iptables/IPVS routing, kube-proxy, Ingress controller, dan proses aplikasi yang menyebabkan error tersebut, serta tuliskan perbaikan konfigurasi manifest yang wajib ditambahkan untuk mengeliminasi error 502 tersebut secara tuntas!

12. **Kasus B: Deadlock pada Horizontal Pod Autoscaler (HPA)**
    * **Kondisi**: Layanan analitik streaming diskalakan menggunakan HPA berbasis metrik utilisasi CPU rata-rata (target: 70%). Saat traffic streaming Kafka melonjak tajam, pod mengalami *CPU throttling* parah, tetapi HPA tidak kunjung menambahkan replika baru meskipun metrik CPU pod mencapai 95%.
    * **Pertanyaan**: Apa yang menyebabkan HPA gagal mengambil keputusan scaling (*lagging*) dalam kondisi tersebut? Analisis hubungan antara `resources.requests.cpu`, `resources.limits.cpu`, interval evaluasi `--horizontal-pod-autoscaler-sync-period`, dan metrik KEDA. Solusi arsitektur apa yang wajib diimplementasikan?

13. **Kasus C: Secret Leak Pasca-Insiden**
    * **Kondisi**: Tim audit menemukan kredensial database produksi tercantum dalam plain-text di dalam crash logs sistem observabilitas (Elasticsearch). Investigasi mengungkap bahwa kredensial tersebut disuntikkan ke container sebagai *environment variables* biasa (`envFrom: secretRef`), dan framework aplikasi mencetak seluruh variabel *environment* ke standard error ketika terjadi exception crash.
    * **Pertanyaan**: Evaluasi kelemahan pola *injection via environment variables* dari perspektif post-exploitation and container internals. Rancang arsitektur alternatif penyuntikan secret tanpa menggunakan environment variables atau plain Kubernetes Secret!

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Jawaban Soal Basic
1. **B** — Memberi window jeda waktu eksekusi agar propagasi perubahan status endpoint Pod terdistribusi ke seluruh Ingress/Kube-proxy sebelum socket aplikasi diputus.
2. **C** — Linux cgroup memory subsystem akan langsung menembak proses via OOM Killer dengan sinyal SIGKILL (Exit code 137 = 128 + 9).
3. **B** — Argo Rollouts mendukung *progressive traffic routing* dan integrasi metrik observabilitas otomatis untuk keputusan promosi/rollback rilis secara mandiri.
4. **C** — Kube-Controller-Manager menjalankan loop rekonsiliasi terus-menerus untuk menjaga konsistensi state.
5. **B** — Base64 hanyalah algoritma encoding representasi biner-ke-teks biasa tanpa elemen kunci rahasia (*cryptographic secret*), sehingga tidak memberikan proteksi kerahasiaan (*confidentiality*).

#### Jawaban Soal Intermediate
6. **B** — `NodeLocal DNSCache` memotong overhead jaringan UDP cluster-wide dan meminimalisasi pembentukan entri conntrack yang rentan mengalami race condition saat traffic tinggi.
7. **B** — Menetapkan `maxUnavailable: 0` berarti cluster menolak kondisi di mana replika pod berkurang meski hanya 1 pod. Perintah `drain` akan ditahan selamanya karena penggusuran pod akan melanggar aturan PDB tersebut.
8. **B** — Pola Envelope Encryption: Data dienkripsi oleh DEK lokal berkinerja tinggi, lalu DEK dienkripsi secara asimetris oleh KEK di HSM/KMS.
9. **B** — Exit code 143 mengindikasikan pod menerima sinyal SIGTERM (128 + 15) dan keluar karena siklus graceful shutdown diputus paksa setelah melewati grace period.
10. **B** — `net.core.somaxconn` mengatur panjang antrean *listen backlog* socket TCP. Jika nilai ini terlalu rendah, koneksi SYN baru yang meluap akan di-drop oleh OS.

#### Panduan Jawaban Soal Kasus Produksi
11. **Kasus A**:
    * *Akar Masalah*: Ketika pod lama dimatikan, API server mencabut pod dari status *Ready*. Endpoint controller mulai menghapus IP pod dari tabel Endpoint, lalu kube-proxy/Ingress controller menyinkronkan perubahan iptables/IPVS. Proses sinkronisasi ini membutuhkan waktu (1-5 detik). Tanpa `preStop` hook dan graceful drain, container langsung mematikan socket aplikasi. Akibatnya, paket HTTP yang masih dirutekan oleh Ingress proxy membentur socket yang telah tertutup, menimbulkan `ECONNRESET` dan `502 Bad Gateway`.
    * *Solusi Manifest*:
      1. Tambahkan `lifecycle.preStop.exec.command: ["sleep", "15"]` agar container tetap hidup selama proses pembersihan rute jaringan berlangsung.
      2. Tangani `SIGTERM` di level aplikasi untuk menuntaskan transaksi yang sedang berjalan (*drain connection pool*).
      3. Atur `readinessProbe` yang akurat dan pasang `terminationGracePeriodSeconds` yang memadai (misal: 45 detik).
12. **Kasus B**:
    * *Akar Masalah*: HPA standar menghitung persentase CPU berdasarkan `resources.requests.cpu`, bukan `limits`. Jika `requests.cpu` disetel terlalu tinggi secara tidak proporsional, persentase utilisasi relatif terlihat rendah. Selain itu, jika pod mengalami CPU throttling parah akibat `limits.cpu` yang terlalu ketat, proses aplikasi melambat sehingga metrik server Prometheus/Metrics Server tidak terlaporkan tepat waktu (*stale metric*). Periode sync HPA bawaan (15s) juga tidak cukup responsif menahan lonjakan mendadak antrean Kafka.
    * *Solusi Arsitektur*: 
      1. Ganti basis autoscaling dari metrik CPU infrastruktur ke metrik bisnis langsung via **KEDA (Kubernetes Event-driven Autoscaling)**, yaitu mengukur jumlah antrean *Kafka consumer group lag*.
      2. Hilangkan batas kaku `limits.cpu` (atau naikkan signifikan) untuk menghindari thread throttling, dan kalibrasi `requests.cpu` sesuai pemakaian baseline sebenarnya.
13. **Kasus C**:
    * *Kelemahan Environment Variables*: Env vars dapat diakses melalui pembacaan `/proc/<PID>/environ`, diwariskan ke proses *child*, terbaca oleh library logging pihak ketiga saat dump context, dan sering bocor saat sistem menghasilkan *core dump* atau stacktrace exception.
    * *Solusi Arsitektur Alternatif*:
      1. Gunakan **Vault CSI Provider** atau **Vault Agent Sidecar Injection** untuk menulis kredensial ke filesystem memori sementara berjenis `tmpfs` (in-memory, volume tidak pernah menyentuh hard disk fisik host).
      2. Aplikasi membaca kredensial langsung dari file di path `/vault/secrets/db-creds` secara periodik atau inisialisasi runtime.
      3. Terapkan rotasi kredensial dinamis (Dynamic Database Credentials) dengan TTL singkat (misal: 1 jam), sehingga jikapun kredensial terekspos, nilainya sudah kedaluwarsa secara otomatis.

---

### 16. Summary

Modul ini telah menguraikan transformasi fundamental dari pengelolaan deployment sederhana menuju implementasi **Arsitektur Produksi Skala Enterprise**:

```
+-----------------------------------------------------------------------------------+
|                         ENTERPRISE PRODUCTION MATURITY                            |
+-----------------------------------------------------------------------------------+
|  1. DEPLOYMENT    : Progressive Delivery (Argo Rollouts, Canary Metrics Analysis) |
|  2. SECURITY      : Zero-Trust Envelope Encryption (Vault Agent, tmpfs Injection)  |
|  3. RELIABILITY   : Pod Disruption Budgets, Anti-Affinity Multi-AZ, PreStop Hooks |
|  4. NETWORKING    : Default-Deny NetworkPolicy, NodeLocal DNSCache Optimization   |
|  5. OBSERVABILITY : OpenTelemetry Tracing, Prometheus Custom Metric Scaling (KEDA)|
+-----------------------------------------------------------------------------------+
```

Pondasi utama sistem produksi enterprise bukan sekadar menjaga aplikasi agar "berjalan", melainkan membangun platform yang **mampu mendeteksi anomali secara otonom, mengisolasi dampak kerusakan (*blast radius*), memitigasi kegagalan tanpa campur tangan manual (*self-healing*), serta mempertahankan integritas data dan ketersediaan layanan pada kondisi beban kerja ekstrem**. Penguasaan terhadap internal container lifecycle, interaksi kernel OS, serta pola arsitektur deklaratif adalah prasyarat mutlak bagi insinyur DevOps/SRE tingkat mahir.