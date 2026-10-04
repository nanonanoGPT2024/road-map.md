# Modul 01: Otomasi, Infrastructure as Code, & GitOps Engineering

## 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Mengidentifikasi, mengukur, dan membatasi operational toil di bawah ambang batas ketat Google SRE (maksimal 50% kapasitas kerja) melalui rekayasa perangkat lunak sistemik.
- Merancang dan mengimplementasikan sistem *automated remediation* (runbook otomatis) berbasis event bus yang aman, idempoten, dan dilengkapi dengan circuit breaker serta fallback manual.
- Mengonfigurasi arsitektur GitOps end-to-end yang mendeteksi konfigurasi *drift* secara real-time dan melakukan rekonsiliasi otomatis menggunakan engine deklaratif.
- Merancang pipeline deployment zero-downtime berbasis *Canary Rollouts* dan *Blue/Green Deployments* yang terintegrasi langsung dengan verifikasi Service Level Objectives (SLO) via automated metric analysis.

---

## 2. Prerequisite
Untuk memahami modul ini secara komprehensif, Anda wajib menguasai:
- **Operating Systems & Networking**: Linux internals (systemd, namespaces, cgroups, signals SIGTERM/SIGKILL), TCP/IP, DNS, HTTP/2, TLS termination.
- **Containerization & Orchestration**: Kubernetes core primitives (Pod, Deployment, Service, ConfigMap, CRDs, Controllers, Admission Webhooks).
- **Infrastructure as Code (IaC)**: Konsep state management, dependency graph resolution, dan declarative syntax (Terraform/OpenTofu).
- **Monitoring & Telemetry**: Prometheus Query Language (PromQL), metrics instrumentation (Counter, Gauge, Histogram), alerting rule evaluation.

---

## 3. Concept
Pilar fundamental Site Reliability Engineering menetapkan bahwa operasi sistem skala besar harus diperlakukan sebagai problem software engineering. Otomasi dalam ranah SRE bukan sekadar menulis skrip shell adhok untuk tugas berulang, melainkan mendirikan loop kendali tertutup (*closed-loop control system*) di mana:
1. **Desired State** diekspresikan secara deklaratif, terversi dalam Git (*Single Source of Truth*).
2. **Actual State** diobservasi secara kontinyu oleh agen orkestrasi runtime.
3. **Reconciliation Loop** secara otomatis merekayasa transisi sistem dari *actual state* menuju *desired state* tanpa intervensi manusia, termasuk mitigasi degradasi fungsional (self-healing) dan progressive traffic routing.

---

## 4. Why
Pendekatan operasional tradisional (*SysAdmin mindset*) bertumpu pada manual runbooks, SSH jump-host, dan perubahan mutabel langsung pada server. Model ini runtuh saat skala infrastruktur melesat secara eksponensial karena:
- **Toil Trap**: Volume tiket operasional tumbuh linear terhadap jumlah server/layanan, menguras waktu engineer dari aktivitas rekayasa strategis.
- **Configuration Drift**: Ketidaksesuaian antara konfigurasi yang terdokumentasi dan kondisi riil mesin, memicu *outage* yang sulit didiagnosis saat disaster recovery.
- **High Blast Radius Deployments**: Deployment all-at-once (*in-place*) memperbesar kemungkinan insiden fatal menjangkau 100% pengguna secara serentak.
- **Mean Time to Mitigate (MTTM) yang Lambat**: Bergantung pada manusia untuk bangun di malam hari, membaca dokumen wiki yang usang, dan mengeksekusi CLI manual menghasilkan durasi down yang tinggi.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Toil Identification and Elimination (The 50% Rule)
Google SRE mendefinisikan **Toil** sebagai pekerjaan operasional yang terkait langsung dengan menjalankan layanan produksi yang memiliki karakteristik: manual, repetitif, dapat diotomatisasi, tidak menghasilkan nilai jangka panjang permanen, serta berskala linear seiring pertumbuhan volume traffic/layanan.

#### Formula Toil Budget:
$$\text{Kapasitas Kerja SRE} = \text{Engineering Work} (\ge 50\%) + \text{Toil \& Operational Work} (\le 50\%)$$

Jika operational work melebihi 50%, surplus tugas harus dikembalikan (*pushed back*) ke tim development perangkat lunak terkait, atau proyek dihentikan hingga toil dieliminasi melalui rekayasa sistem.

```
+-------------------------------------------------------------+
|                     Toil Taxonomy                           |
+-------------------------------------------------------------+
| Karakteristik           | Contoh Toil      | Contoh Engineering     |
+-------------------------+------------------+------------------------+
| Intervensi Manual       | Restart pod/VM   | Menulis Kube Controller|
| Nilai Jangka Panjang    | Nol (akan reset) | Permanen (arsitektur)  |
| Skalabilitas            | $O(N)$ traffic   | $O(1)$ sub-linear      |
| Sifat Tugas             | Reaktif-prosedural| Desain sistemik       |
+-------------------------+------------------+------------------------+
```

### 5.2 Automated Remediation Runbooks & Self-Healing Architecture
Self-healing adalah kemampuan sistem untuk mendeteksi deviasi internal dan menerapkan langkah pemulihan deterministik tanpa kehadiran operator manusia.
Arsitektur remediator modern tersusun atas tiga subsistem:
1. **Detection Engine**: Prometheus Alertmanager / CloudWatch Events mengirimkan payload webhook terstruktur saat ambang batas SLO/anomali terlampaui.
2. **Safety Broker (Circuit Breaker & Rate Limiter)**: Mencegah remediator mengeksekusi loop destruktif jika terjadi *cascading failure* (misalnya: merestart 1.000 instans sekaligus dalam hitungan detik).
3. **Execution Runtime**: Micro-controller atau worker (misal: AWS Lambda, StackStorm, Temporal worker) yang mengimplementasikan idempotensi mutlak via *conditional execution tokens*.

### 5.3 GitOps Drift Detection and Reconciliation Mechanics
GitOps mentranslasikan konsep core Git (commit, pull request, sha-history) sebagai mekanisme operasional infrastruktur. Komponen utama GitOps engine (seperti ArgoCD / Flux):
- **Source Controller**: Mengawasi Git repository secara polling atau webhook-driven.
- **State Comparer**: Membandingkan AST (*Abstract Syntax Tree*) dari manifes di Git dengan data representasi JSON aktual dari Kubernetes API Server via algoritma **Three-Way Merge Patch**:
  $$\text{Patch} = f(\text{Original Desired State}, \text{Modified Actual State}, \text{New Desired State})$$
- **Sync/Reconciliation Controller**: Mengeluarkan instruksi mutasi via kube-apiserver untuk mereparasi *drift* yang terdeteksi.

```
       [ Git Repository ]
               |
     (1) Pull Desired State
               v
    +----------------------+       (2) Query
    | GitOps Controller    | ---------------------> [ Kube API Server ]
    | (State Comparer Engine)                      |    (Actual State)
    +----------------------+ <--------------------- +
               |
       (3) Diff Evaluation (Drift?)
               |
       [ Drift Detected! ]
               |
       (4) Three-Way Merge & Sync
               v
      [ Reconciled State ]
```

### 5.4 Progressive Traffic Delivery: Blue/Green vs Canary

#### Blue/Green Strategy
Menyediakan dua environment identik:
- **Blue (Active)**: Menangani 100% traffic produksi.
- **Green (Idle/Staging)**: Menerima rilis software versi baru.
- **Switching Mechanism**: Pengalihan layer-4/layer-7 routing (Load Balancer target group / Service selector) secara atomik dari Blue ke Green setelah lolos smoke testing.

#### Canary Strategy with Automated Metric Analysis
Mengarahkan fraksi kecil traffic (misal: 1%, 5%, 25%, 50%) ke instans versi baru (*Canary*) berdampingan dengan versi stabil (*Baseline*).
Selama fase Canary, controller mengevaluasi metrik real-time:
$$\text{Canary Health} = (\text{Error Rate}_{\text{canary}} \le \text{Threshold}) \land (\text{P99 Latency}_{\text{canary}} \le \text{Baseline} \times 1.1)$$
Jika formula evaluasi gagal pada interval evaluasi tertentu, sistem memicu *automated rollback* instan dengan menggeser traffic kembali 100% ke Baseline.

---

## 6. How

### Alur Implementasi GitOps & Automated Rollout:
1. **Definisikan Kontrak Infrastruktur**: Semua konfigurasi didefinisikan secara deklaratif menggunakan Kustomize atau Helm Charts dan disimpan dalam repository Git khusus konfigurasi (*config-repo* terpisah dari *app-repo*).
2. **Pasang GitOps Operator**: Deploy ArgoCD atau Flux ke cluster management. Nonaktifkan akses tulis manual (`kubectl edit`, `kubectl apply`) pada cluster target untuk mencegah mutasi out-of-band.
3. **Konfigurasi Drift Auto-Heal**: Set synchronization policy ke mode `Automated` dengan flag `selfHeal: true` dan `prune: true`.
4. **Implementasikan Canary Engine**: Gunakan Argo Rollouts atau Flagger yang mengendalikan Service Mesh (Istio/Linkerd) atau Ingress Controller (NGINX/Traefik).
5. **Konstruksi AnalysisTemplate**: Sambungkan evaluasi metrik rollout langsung ke Prometheus queries yang mengukur Error Rate HTTP 5xx dan Latency P99.

---

## 7. Analogy
Bayangkan sistem autopilot pesawat komersial modern:
- **Traditional SysAdmin**: Pilot harus terus-menerus memegang tuas kemudi, memeriksa kompas manual setiap 10 detik, dan menekan pedal kemudi jika angin samping bertiup (Toil).
- **GitOps**: Rencana penerbangan digital diunggah ke komputer navigasi sebelum lepas landas (*Desired State di Git*). Pilot tidak dapat mengubah rute secara sembarangan tanpa mencatatnya di sistem navigasi.
- **Drift Detection & Reconciliation**: Jika turbulensi mendorong pesawat 50 meter ke kiri (*Actual Drift*), sensor gyroscopic mendeteksi deviasi tersebut dan sistem servo menggerakkan *aileron* untuk mengembalikan pesawat tepat ke koordinat target (*Reconciliation*).
- **Canary Deployment**: Ketika mencoba bahan bakar formulasi baru di ketinggian jelajah, autopilot mengalirkannya hanya ke 5% silinder di satu mesin terlebih dahulu. Jika temperatur silinder tersebut melonjak abnormal, katup ditutup seketika dan bahan bakar standar dialirkan kembali sebelum seluruh mesin rusak.

---

## 8. Diagram (ASCII)

### End-to-End GitOps, Progressive Rollout, & Self-Healing Loop

```
+---------------------------------------------------------------------------------------------------+
| SRE / DEVELOPER                                                                                   |
|  git push commit ---------------------------------------+                                         |
+---------------------------------------------------------|-----------------------------------------+
                                                          |
                                                          v
+---------------------------------------------------------------------------------------------------+
| GITHUB / GITLAB REPOSITORY (Source of Truth)                                                      |
|  - manifests/base/deployment.yaml                                                                 |
|  - manifests/overlays/prod/rollout.yaml                                                           |
+---------------------------------------------------------------------------------------------------+
       |                                                 ^
       | Webhook Trigger                                 | Drift Alert
       v                                                 |
+---------------------------------------------------------------------------------------------------+
| GITOPS ENGINE (ArgoCD / Flux)                                                                     |
|                                                                                                   |
|   +-------------------+    Compare AST     +------------------+    Reconcile Apply                |
|   | Git Desired State | -----------------> | Drift Detector   | --------------------+             |
|   +-------------------+                    +------------------+                     |             |
+-------------------------------------------------------------------------------------|-------------+
                                                                                      |
                                                                                      v
+---------------------------------------------------------------------------------------------------+
| KUBERNETES PRODUCTION CLUSTER                                                       |             |
|                                                                                     |             |
|      +------------------------------------------------------------------------------+             |
|      |                                                                                            |
|      v                                                                                            |
|   +-----------------------------------------------------------------------+                       |
|   | Progressive Delivery Controller (Argo Rollouts / Flagger)             |                       |
|   |                                                                       |                       |
|   |   Traffic Splitting (Ingress / Service Mesh)                          |                       |
|   |          |                                                            |                       |
|   |          +-----> [ 90% Stable (Baseline) Pods ]                       |                       |
|   |          |                                                            |                       |
|   |          +-----> [ 10% Canary (Target) Pods ]                         |                       |
|   +-----------------------------------------------------------------------+                       |
|                              |                                                                    |
|                              | Scrapes SLI Metrics                                                |
|                              v                                                                    |
|                  +-----------------------+                                                        |
|                  | Prometheus Engine     |                                                        |
|                  +-----------------------+                                                        |
|                              |                                                                    |
|            Threshold Breach? | Analysis Template Evaluation                                        |
|                              v                                                                    |
|                  +-----------------------+    Trigger Webhook     +--------------------------+    |
|                  | Alertmanager Engine   | ---------------------> | Auto-Remediation Broker  |    |
|                  +-----------------------+                        | (Lambda / Event Handler) |    |
|                                                                   +--------------------------+    |
|                                                                                 |                 |
|                                         Execute Idempotent Patch                |                 |
|                                         (Drain Node / Restart / Rollback)       v                 |
|                                         +---------------------------------------------------+     |
+---------------------------------------------------------------------------------------------------+
```

---

## 9. Simple Example

Implementasi deklaratif GitOps Application pada ArgoCD untuk microservice dengan kapabilitas auto-sync dan self-healing aktif:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: order-service-prod
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: 'https://github.com/enterprise/sre-infra-gitops.git'
    targetRevision: HEAD
    path: environments/production/order-service
  destination:
    server: 'https://kubernetes.default.svc'
    namespace: core-banking
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=false
      - ApplyOutOfSyncOnly=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

---

## 10. Practical Example (Konfigurasi CLI / Terraform / Kode Hands-on)

### 10.1 Manifes Argo Rollouts dengan Analisis Metrik Canary Terotomatisasi

File: `canary-rollout.yaml`
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: payments-engine
  namespace: transaction-system
spec:
  replicas: 10
  strategy:
    canary:
      analysis:
        templates:
          - templateName: payments-success-rate
        args:
          - name: service-name
            value: payments-engine-canary
      steps:
        - setWeight: 5
        - pause: { duration: 5m }
        - setWeight: 20
        - pause: { duration: 10m }
        - setWeight: 50
        - pause: { duration: 10m }
  revisionHistoryLimit: 5
  selector:
    matchLabels:
      app: payments-engine
  template:
    metadata:
      labels:
        app: payments-engine
    spec:
      containers:
        - name: core
          image: internal-registry.enterprise.io/banking/payments:v2.4.1
          ports:
            - name: http
              containerPort: 8080
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2"
              memory: "2Gi"
          readinessProbe:
            httpGet:
              path: /healthz
              port: http
            initialDelaySeconds: 5
            periodSeconds: 3
```

File: `analysis-template.yaml`
```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: payments-success-rate
  namespace: transaction-system
spec:
  args:
    - name: service-name
  metrics:
    - name: success-rate
      interval: 1m
      successCondition: result[0] >= 0.9995
      failureLimit: 2
      provider:
        prometheus:
          address: http://prometheus-k8s.monitoring.svc.cluster.local:9090
          query: |
            sum(rate(http_requests_total{service="{{args.service-name}}",status=~"2..|3.."}[1m]))
            /
            sum(rate(http_requests_total{service="{{args.service-name}}"}[1m]))
```

---

## 11. Real World Example

**Kasus**: Sistem Core Payment Bank Gateway memproses ~15.000 TPS (*transactions per second*). 

**Insiden Lampau**: Engineer melakukan deployment manual jam 02:00 pagi menggunakan command `kubectl set image`. Bug kebocoran thread-pool yang hanya muncul di bawah traffic masif menyebabkan crash pada 100% pod dalam waktu 90 detik. MTTD: 8 menit, MTTR: 22 menit, kerugian finansial diestimasi $420.000 akibat transaksi gagal.

**Solusi Arsitektur Baru**:
1. Implementasi GitOps melalui ArgoCD. Hak akses langsung port 6443 (API server) dicabut total dari developer dan SRE; hanya pipeline CI yang dapat membuat Pull Request ke `prod-manifests` repository.
2. Argo Rollouts dikonfigurasi dengan langkah traffic splitting: 2% $\to$ 10% $\to$ 25% $\to$ 100%.
3. `AnalysisTemplate` PromQL mengevaluasi error rate (HTTP 5xx) dan P99 Transaction Latency tiap 60 detik.
4. Ketika v2.4.2 di-deploy dan menyebabkan P99 latency naik dari 120ms ke 850ms pada alokasi traffic 2%, `payments-success-rate` gagal 2 kali berturut-turut.
5. Controller secara otomatis memutus traffic Canary, menurunkan replicas instans baru ke 0, dan mengembalikan 100% traffic ke v2.4.1 dalam durasi **14 detik**. 
6. Nol intervensi manusia, blast radius hanya berdampak pada 0.04% transaksi yang langsung di-retry otomatis oleh edge gateway.

---

## 12. Trade-offs

| Aspek | Blue/Green Deployment | Canary with Automated Analysis |
| :--- | :--- | :--- |
| **Konsumsi Resource Infrastruktur** | **Sangat Boros (Tinggi)**: Membutuhkan 2x kapasitas compute cluster (200%) selama transisi. | **Sangat Hemat (Rendah)**: Hanya memerlukan compute tambahan sebanding dengan persentase langkah canary (misal: +5-10%). |
| **Waktu Deployment / Total Duration** | **Cepat**: Pengalihan traffic instan (flip DNS/LB target). | **Lambat**: Memerlukan waktu observasi statistik metrik yang cukup (misal: 15-45 menit). |
| **Blast Radius Mitigation** | **Medium**: Sekali switch, 100% user langsung terpapar bug jika lolos smoke test. | **Minimal**: Hanya sebagian kecil user (1-5%) yang terdampak saat anomali terjadi. |
| **Stateful Data / Schema Migration** | Sangat kompleks; membutuhkan backward-compatible schema (Expand/Contract pattern). | Sangat kompleks; membutuhkan backward-compatible schema (Expand/Contract pattern). |
| **Kompleksitas Tooling** | Sederhana; cukup konfigurasi Service selector atau Load Balancer routing. | Tinggi; membutuhkan Service Mesh/Ingress Traffic Splitter dan Prometheus query integration. |

---

## 13. When To Use
- **GitOps Drift Correction**: Gunakan pada seluruh sistem berbasis cloud-native Kubernetes untuk menegakkan single source of truth dan mencegah unauthorized out-of-band updates.
- **Automated Remediation**: Gunakan untuk kegagalan yang memiliki akar penyebab jelas (*well-understood failure modes*), seperti: node disk full akibat journal logs, unhandled deadlock pod hang, atau pod eviction pada OOM cluster.
- **Canary Deployments**: Wajib digunakan pada high-throughput business-critical systems (fintech, streaming, e-commerce) di mana downtime beberapa detik membawa kerugian finansial atau reputasi langsung.

---

## 14. When NOT To Use
- **Automated Remediation**: JANGAN gunakan pada sistem database stateful (*split-brain risk*) ketika mekanisme konsensus terganggu. Merestart node master database secara otomatis saat partisi jaringan terjadi dapat merusak integritas data ACID secara permanen.
- **Aggressive Canary Analysis**: JANGAN gunakan pada layanan dengan throughput sangat rendah (< 1 request per menit). Prometheus tidak akan mengumpulkan sampel data yang signifikan secara statistik untuk mengevaluasi status kesehatan rilis baru secara akurat (*law of small numbers*).
- **Auto-Sync Hard GitOps Reconciliation**: JANGAN aktifkan `selfHeal: true` saat proses Disaster Recovery kritis yang membutuhkan *surgical live debugging* di mana manifes Git sedang tidak dapat diakses (misal: GitHub/GitLab global outage).

---

## 15. Common Mistakes
1. **Flapping Automated Remediation Loop**: Remediator me-restart container yang mengalami crash loop akibat konfigurasi database invalid; loop restart berjalan 10.000 kali per jam hingga membebani etcd dan CPU cluster (*storm effect*).
2. **Ketiadaan Circuit Breaker pada Auto-Healing**: Remediator menghapus node yang dianggap unhealthy secara serentak, yang memicu penghancuran seluruh cluster secara cascade.
3. **Mengabaikan Idempotensi**: Menulis remediation script yang tidak aman jika dieksekusi 2 kali berturut-turut (misal: appending duplicate lines ke konfigurasi atau double-charging transaksi saat me-replay dead-letter queue).
4. **GitOps Drift Reconcile Loop War**: Menggunakan tools IaC eksternal yang berebut mengupdate atribut yang sama dengan Kubernetes HPA (Horizontal Pod Autoscaler) atau dynamic mutation mutating webhooks, menyebabkan CPU spike konstan akibat write-amplification tak berkesudahan.
5. **Short Canary Analysis Duration**: Memberikan durasi observasi hanya 30 detik pada canary step; memory leaks baru termanifestasi setelah 15 menit traffic continuous load.

---

## 16. Best Practices
1. **Terapkan Batasan Toil Maksimal 50%**: Audit aktivitas on-call mingguan. Kategorisasikan tugas on-call ke dalam Toil vs Engineering. Bila Toil > 50%, prioritaskan sprint pembersihan teknis (*Toil Sprint*).
2. **Exponential Backoff & Jitter pada Remediator**: Setiap aksi pemulihan wajib memiliki limit maksimal percobaan dan interval acak (*jitter*) untuk menghindari sinkronisasi spike beban.
3. **Immutability First**: Jangan pernah mengupdate patch in-place. Rilis versi software baru harus menghasilkan image container baru dan immutable tag, didorong melalui commit Git hash.
4. **Strict Safety Gates**: Sertakan *cooldown period* dan manual gate approval sebelum canary deployment dinaikkan dari 50% ke 100% traffic pada layanan tier-1.
5. **Decouple Code from Environment Manifests**: Pisahkan repositori kode aplikasi dari repositori konfigurasi infrastruktur k8s untuk mempermudah audit trails, RBAC, dan CI/CD automation.

---

## 17. Troubleshooting

### Problem: GitOps Engine Terkunci pada Loop "OutOfSync" dan "SyncFailed"
- **Penyebab**: Terjadi pertentangan antara manifes di Git dan Mutating Webhook di cluster yang menambahkan metadata/labels default secara persisten, atau dynamic fields (seperti `resources.limits` yang diinjeksi VPA).
- **Langkah Diagnosa**:
  1. Jalankan `argocd app diff <app-name>` untuk melihat exact field yang terus bermutasi.
  2. Periksa apakah ada Controller/Webhook ketiga yang memutasi field tersebut:
     ```bash
     kubectl get mutatingwebhookconfigurations -A
     ```
- **Solusi**: Tambahkan ignore configuration pada konfigurasi GitOps Application:
  ```yaml
  spec:
    ignoreDifferences:
      - group: apps
        kind: Deployment
        jsonPointers:
          - /spec/template/metadata/annotations/sidecar.istio.io~1status
  ```

### Problem: Canary Rollout Tidak Pernah Rollback Padahal Aplikasi Melemparkan Error 500
- **Penyebab**: Prometheus query salah mengevaluasi denominator metrik (membagi dengan 0 atau mengarahkan ke service name yang salah sehingga query menghasilkan `No Data / NaN`).
- **Langkah Diagnosa**:
  1. Verifikasi manual query di Prometheus UI dengan label Pod canary aktif:
     ```promql
     sum(rate(http_requests_total{pod=~"payments-engine.*",status=~"5.."}[1m]))
     ```
  2. Periksa status resource analysis:
     ```bash
     kubectl describe analysissrun -n <namespace> <analysis-run-name>
     ```
- **Solusi**: Pastikan `AnalysisTemplate` menangani kasus data kosong dengan menambahkan konfigurasi `failureCondition` yang eksplisit dan `count` threshold yang sesuai.

---

## 18. Exercise
1. Tulis sebuah kalkulator Toil sederhana berbasis script shell atau Python yang memproses sheet/CSV aktivitas tim SRE bulanan, menghitung persentase operational work terhadap total working hours, dan me-reject sprint backlog jika persentase toil > 50%.
2. Konfigurasikan manifes `AnalysisTemplate` yang mengevaluasi dua metrik secara paralel:
   - Error rate HTTP 5xx harus $\le 0.1\%$.
   - Latency P99 harus $\le 200\text{ms}$.
   Jika salah satu metrik gagal 3 kali dalam durasi 10 menit, eksekusi automated abort rollout.

---

## 19. Challenge
Rancang arsitektur sistem self-healing berskala enterprise untuk layanan stateful Elasticsearch di Kubernetes:
- Buat sebuah micro-remediator yang mendeteksi pod Elasticsearch berstatus `CrashLoopBackOff` akibat disk failure / corrupt lock file.
- Remediator harus memverifikasi bahwa cluster status tetap `Green` atau `Yellow` sebelum mengambil tindakan.
- Sistem harus menolak aksi jika node yang crash adalah master node terakhir yang aktif.
- Remediator harus mengeksekusi volume detachment, node drain secara aman, membuat tiket insiden retrospektif via API, dan membatasi frekuensi aksi per cluster maksimal 1 kali dalam 60 menit (Rate-limited Circuit Breaker).

---

## 20. Summary
- **SRE Toil Philosophy**: Pembatasan toil maksimum 50% adalah komitmen matematis organisasi SRE untuk memastikan engineer memiliki ruang waktu merancang otomasi dan sistem berskala besar.
- **GitOps Mechanics**: Mengubah model deployment dari *imperative push* menjadi *declarative pull reconciliation*, menutup celah ketidakkonsistenan konfigurasi (*drift*) dan memusatkan audit trail ke git commits.
- **Self-Healing Dynamics**: Harus dilindungi oleh batas keamanan (*rate limiting, circuit breaker, exponential backoff*) untuk menghindari amplifikasi kerusakan sistem saat terjadi kegagalan katastropik.
- **Safe Rollouts**: Menggunakan Canary Rollouts yang dipandu oleh automated PromQL analysis memitigasi blast radius secara otomatis, mentranslasikan SLO teknis menjadi gerbang rilis produksi tanpa campur tangan manusia.