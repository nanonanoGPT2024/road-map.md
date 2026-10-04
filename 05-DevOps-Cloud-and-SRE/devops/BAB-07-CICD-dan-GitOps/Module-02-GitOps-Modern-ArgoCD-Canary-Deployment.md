# Module 02: GitOps Modern dengan ArgoCD, Flux, & Canary Deployment (Argo Rollouts)

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Memahami paradigma **GitOps** di mana Git bertindak sebagai *Single Source of Truth* untuk seluruh infrastruktur dan status aplikasi Kubernetes.
- Mengonfigurasi dan mengoperasikan **ArgoCD** untuk mengotomatisasi rekonsiliasi state (*desired state* vs *live cluster state*).
- Menjelaskan perbedaan pendekatan **Push-based CI/CD** (GitHub Actions runner mentransfer manifest via kubectl) vs **Pull-based GitOps** (ArgoCD agent di cluster menarik update dari Git repo).
- Mengimplementasikan strategi deployment progresif (**Canary Deployment** & **Blue/Green**) menggunakan **Argo Rollouts** dengan analisis metrik otomatis.
- Mengatasi *configuration drift* dan mengembalikan status cluster secara instan via `git revert`.

---

## 2. Prerequisite
- Memahami konsep dasar Kubernetes: Pods, Deployments, ReplicaSet, Services, dan Ingress (BAB 04).
- Memahami pipeline CI/CD dasar dan pembuatan container image (BAB 07 Module 01).
- Pemahaman dasar tentang Git branching, commit hashes, dan pull request workflows.

---

## 3. Concept
**GitOps** adalah model operasional untuk Kubernetes dan arsitektur cloud-native modern di mana repositori Git dijadikan sebagai *declarative single source of truth*. Setiap perubahan sistem (konfigurasi, penambahan pod replica, update image tag, limit memori) dilakukan melalui Pull Request ke repositori Git.

Alih-alih memberikan hak akses root/cluster-admin ke server CI eksternal untuk menembakkan `kubectl apply`, agen pengendali (seperti **ArgoCD** atau **Flux**) berjalan *di dalam* cluster Kubernetes, secara konstan memonitor repositori Git dan secara mandiri menyelaraskan (*reconcile*) kondisi cluster aktual dengan definisi di Git.

```
       Push-based CI/CD (Tradisional):
       [Dev] ──> [Git Repo] ──> [CI Runner: GitHub Actions] ──(Kubeconfig / Port 6443)──> [K8s Cluster]
                                (Risiko keamanan: Credential cluster bocor di CI)

       Pull-based GitOps (Modern):
       [Dev] ──> [Git Repo] <──(Poll / Webhook)── [ArgoCD Controller (Inside K8s)] ──> [K8s Resources]
                                                 (Zero external attack surface)
```

---

## 4. Why?
1. **Security & Zero-Credential Leak**: Dalam push-based CI, GitHub Actions runner harus memegang file `kubeconfig` atau AWS IAM role dengan hak write ke cluster. Jika runner CI terkompromi (misalnya via supply chain attack pada npm action), seluruh cluster produksi terancam. Dalam GitOps, tidak ada credential cluster yang pernah keluar dari jaringan cluster.
2. **Eliminasi Manual Configuration Drift**: Administrator sering tergoda melakukan `kubectl edit deployment` darurat di terminal produksi. Dalam GitOps, ArgoCD akan mendeteksi drift tersebut dalam hitungan detik dan secara otomatis menimpa kembali (*auto-heal*) sesuai isi Git.
3. **Auditability & Compliance**: Siapa yang mengubah replica dari 3 menjadi 50? Kapan image di-upgrade? Semuanya tercatat permanen di commit log Git (`git log`), ditandatangani dengan GPG key, dan di-review melalui Pull Request approval.
4. **Instant Disaster Recovery**: Jika cluster Kubernetes hancur terbakar, Anda cukup mendirikan cluster baru yang kosong, menginstall ArgoCD, dan mengarahkannya ke repositori Git. Seluruh workload aplikasi dan konfigurasi akan terpasang kembali secara identik dalam hitungan menit.

---

## 5. What?
Komponen inti ekosistem GitOps modern:
- **ArgoCD Application Controller**: Service Kubernetes yang memantau live state cluster dan membandingkannya dengan manifest target di Git. Menghitung *diff* dan memicu rekonsiliasi.
- **ArgoCD Repo Server**: Layanan internal yang meng-clone Git repo dan me-render template Helm, Kustomize, atau Plain Manifests menjadi JSON/YAML Kubernetes native.
- **ArgoCD API Server & Web UI**: Menyediakan dashboard visual real-time dari seluruh pohon dependensi object Kubernetes, riwayat sync, dan tombol manual sync.
- **Argo Rollouts**: Controller pengganti `Deployment` standar Kubernetes yang mendukung advanced deployment strategies: **Canary** (membagi traffic bertahap 5%, 20%, 50%, 100%) dan **Blue/Green** dengan rollback otomatis berbasis Prometheus metrics.

---

## 6. How?
Alur kerja standar GitOps Delivery:
1. **Developer Code**: Developer melakukan push kode ke repositori aplikasi `app-source-code`.
2. **CI Pipeline**: GitHub Actions menjalankan test, build container image, dan melakukan push image baru berlabel tag `v1.2.0` ke Container Registry.
3. **GitOps Manifest Update**: CI runner mengupdate tag image di repositori konfigurasi terpisah (`app-gitops-manifests/overlays/prod/kustomization.yaml`) melalui bot commit.
4. **ArgoCD Sync**: ArgoCD mendeteksi commit baru di repo manifest via webhook, mengubah status aplikasi menjadi `OutOfSync`, lalu mengeksekusi proses `Sync` (apply manifest baru ke cluster).
5. **Argo Rollout Canary**: Controller Argo Rollouts membuat replica baru untuk versi `v1.2.0`, mengarahkan 10% traffic via Ingress/Service Mesh, mengevaluasi error rate selama 5 menit, dan jika sehat, mempromosikan traffic hingga 100%.

---

## 7. Analogy
Bayangkan **ArgoCD** seperti seorang **Konduktor Orkestra Otomatis**:
- Repositori Git adalah **Buku Partitur Lagu**.
- Seluruh pemain musik dan alat instrumen adalah **Pod dan Service Kubernetes**.
- Jika ada pemain biola yang memainkan nada sumbang di luar partitur (manual `kubectl edit`), konduktor langsung menepuk pundaknya dan memaksanya kembali ke partitur tertulis (*auto-healing*).
- Jika komposer menulis nada baru di partitur (Git commit), konduktor segera menginstruksikan pemain untuk memainkan melodi baru tersebut secara serempak (*auto-sync*).

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|                            GITOPS OPERATIONAL ARCHITECTURE                        |
+-----------------------------------------------------------------------------------+

 [ Developer ] 
      │
      ▼  git commit / PR merge
 ┌──────────────────────────────────────┐
 │ Git Config Repo                      │
 │ (github.com/company/k8s-manifests)   │
 │   - overlays/production/             │
 │       - deployment.yaml (v2.1.0)     │
 └──────────────────┬───────────────────┘
                    │
                    │ Polling (3m) or Git Webhook
                    ▼
 ┌──────────────────┴───────────────────────────────────────────────────────────────┐
 │ Kubernetes Production Cluster                                                    │
 │                                                                                  │
 │  ┌───────────────────────────────────────────────────────────┐                   │
 │  │ ArgoCD Controller (Namespace: argocd)                     │                   │
 │  │  1. git fetch target manifest                             │                   │
 │  │  2. diff: Live State vs Desired State                     │                   │
 │  │  3. Reconcile Loop & Auto-Heal                            │                   │
 │  └───────────────────────────┬───────────────────────────────┘                   │
 │                              │                                                   │
 │             ┌────────────────┴────────────────┐                                  │
 │             ▼                                 ▼                                  │
 │  ┌───────────────────────┐         ┌────────────────────────┐                    │
 │  │ Argo Rollout Canary   │         │ Argo Rollout Stable    │                    │
 │  │ Pods v2.1.0 (10% Req) │         │ Pods v2.0.0 (90% Req)  │                    │
 │  └──────────▲────────────┘         └──────────▲─────────────┘                    │
 │             │                                 │                                  │
 │             └────────────────┬────────────────┘                                  │
 │                              │                                                   │
 │                   [ ALB / Nginx Ingress ]                                        │
 │                              ▲                                                   │
 └──────────────────────────────┼───────────────────────────────────────────────────┘
                                │
                          [ User Traffic ]
```

---

## 9. Simple Example: Definisi ArgoCD Application
File manifest deklaratif untuk mendaftarkan aplikasi ke dalam ArgoCD (`application.yaml`):

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: payment-service-production
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: 'https://github.com/myorg/k8s-manifests.git'
    targetRevision: main
    path: apps/payment-service/overlays/prod
  destination:
    server: 'https://kubernetes.default.svc'
    namespace: payments
  syncPolicy:
    automated:
      prune: true     # Hapus resource di K8s jika dihapus dari Git
      selfHeal: true  # Timpa paksa jika ada perubahan manual via kubectl
    syncOptions:
      - CreateNamespace=true
```

---

## 10. Practical Example: Argo Rollout Canary Definition
Menggantikan `kind: Deployment` standar dengan `kind: Rollout` untuk canary deployment dengan analisis otomatis:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: order-api-rollout
  namespace: production
spec:
  replicas: 10
  strategy:
    canary:
      # Analisis kesehatan via metrik sebelum promosi tahap lanjut
      analysis:
        templates:
          - templateName: success-rate-check
        args:
          - name: service-name
            value: order-api-canary
      steps:
        # Langkah 1: Kirim 10% traffic ke versi baru & pause manual/timer
        - setWeight: 10
        - pause: { duration: 5m }
        # Langkah 2: Naikkan ke 25% traffic
        - setWeight: 25
        - pause: { duration: 10m }
        # Langkah 3: Naikkan ke 50% traffic
        - setWeight: 50
        - pause: { duration: 10m }
        # Langkah 4: Promosikan penuh ke 100%
  revisionHistoryLimit: 5
  selector:
    matchLabels:
      app: order-api
  template:
    metadata:
      labels:
        app: order-api
    spec:
      containers:
        - name: order-api
          image: myregistry.io/order-api:v2.4.0
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: 250m
              memory: 256Mi
```

---

## 11. Real World Example: FinTech Multi-Cluster GitOps Architecture
Pada bank digital dengan puluhan microservices:
1. **Pemisahan Repositori**: Repositori kode bisnis (`fintech-core-src`) sepenuhnya terpisah dari repositori konfigurasi deployment (`fintech-gitops-infra`).
2. **Branch Environment Mapping**: 
   - Branch `staging` disinkronkan otomatis oleh ArgoCD ke staging cluster di AWS us-east-1.
   - Branch `main` disinkronkan ke multi-region production cluster (AWS ap-southeast-1 & GCP asia-southeast2).
3. **Automated Rollback via Rollouts Metric Analysis**:
   Saat versi baru microservice Transfer Dana dirilis:
   - Argo Rollout mengarahkan 5% pengguna ke versi baru.
   - Analisis metrik Prometheus memeriksa parameter HTTP 5xx error rate:
     $$\text{Error Rate} = \frac{\text{sum}(\text{rate}(\text{http\_requests\_total}\{\text{status}=\sim"5.."\}))}{\text{sum}(\text{rate}(\text{http\_requests\_total}))}$$
   - Jika error rate $> 0.5\%$ dalam jendela waktu 3 menit, rollout langsung dibatalkan secara otomatis (*automated abort*), traffic kembali 100% ke versi lama, dan insinyur on-call menerima notifikasi Slack tanpa ada nasabah yang dirugikan.

---

## 12. Trade-offs

| Aspek | Push CI/CD Tradisional | Pull GitOps (ArgoCD) |
|---|---|---|
| **Security Surface** | Tinggi (Kubeconfig tersimpan di CI Runner) | Sangat Rendah (Cluster agent menarik data) |
| **Drift Detection** | Lemah (Tidak tahu jika ada manual kubectl edit) | Instan & Otomatis (Reconciliation loop) |
| **Multi-Cluster Ops** | Rumit (CI harus mengelola credential N cluster) | Sangat Mudah (Hub-and-Spoke cluster target) |
| **Kurva Belajar** | Rendah (Hanya menjalankan script bash/CLI) | Menengah-Tinggi (Argo CRD, Kustomize/Helm structure) |
| **Kecepatan Feedback** | Cepat (Hasil CLI langsung muncul di pipeline log) | Asynchronous (Perlu menunggu sync poll / webhook) |

---

## 13. When To Use
- Lingkungan Kubernetes produksi skala menengah hingga enterprise dengan tim multi-engineer.
- Sistem yang mewajibkan kepatuhan audit ketat (PCI-DSS, HIPAA, ISO 27001) di mana akses SSH dan `kubectl` langsung ke production dilarang.
- Mengelola puluhan cluster Kubernetes di berbagai region/cloud dari satu dashboard terpusat.

---

## 14. When NOT To Use
- Tim kecil dengan 1 developer dan single server virtual machine sederhana tanpa Kubernetes (Gunakan CI/CD push Docker Compose biasa).
- Sistem dengan beban kerja ephemeral yang dibuat dan dihancurkan setiap jam tanpa konfigurasi status deklaratif jangka panjang.

---

## 15. Common Mistakes
1. **Menyatukan App Code dan Manifest Kubernetes dalam Satu Repositori**: Setiap commit code akan memicu loop rekonsiliasi yang tidak perlu dan membingungkan git history. Pisahkan repo aplikasi dan repo manifest GitOps.
2. **Menonaktifkan Self-Heal**: Jika `selfHeal: false`, seseorang yang sengaja atau tidak sengaja mengubah konfigurasi di cluster tidak akan diperbaiki oleh ArgoCD.
3. **Mengabaikan Sealed Secrets / External Secrets**: Menyimpan password plain text di repositori Git manifest publik/internal. GitOps mewajibkan enkripsi secret (misal dengan HashiCorp Vault atau SOPS).

---

## 16. Best Practices
### Must Have
- Pisahkan repositori GitOps (konfigurasi cluster) dari repositori kode aplikasi.
- Aktifkan `prune: true` dan `selfHeal: true` pada sync policy production.
- Gunakan Kustomize overlays atau Helm values per environment (`overlays/dev`, `overlays/staging`, `overlays/prod`).

### Recommended
- Pasang ArgoCD Image Updater untuk mengotomatisasi pembaruan tag container image di Git.
- Gunakan Slack/Teams notification plugin untuk alert sync failure dan degradation.

### Advanced
- Gabungkan Argo Rollouts dengan Istio Service Mesh atau AWS ALB Ingress Controller untuk pembagian bobot traffic level HTTP layer 7.

---

## 17. Troubleshooting
- **Masalah**: ArgoCD menampilkan status `OutOfSync` terus-menerus meskipun manifest sudah sesuai.
  - *Penyebab*: Mutating Webhook (seperti Istio Sidecar Injector atau Kyverno) menambahkan field default ke live pod yang tidak didefinisikan di Git manifest.
  - *Solusi*: Konfigurasikan `ignoreDifferences` pada manifest Application untuk mengabaikan field yang dihasilkan oleh webhook dinamis.
- **Masalah**: ArgoCD gagal melakukan clone private Git repository.
  - *Solusi*: Periksa konfigurasi SSH Known Hosts dan Deploy Key / GitHub App token di namespace `argocd`.

---

## 18. Exercise
1. Tuliskan manifest K8s Kustomization untuk environment `staging` dan `prod` yang mereferensikan direktori `base/` yang sama namun mengubah jumlah replica dan CPU limit.
2. Simulasikan skenario drift detection: ubah secara manual replica dari 2 menjadi 8 pada cluster simulator, dan amati bagaimana reconciler memulihkannya kembali ke 2.

---

## 19. Challenge
Rancang pipeline GitOps terpadu:
- Developer merge PR ke `main`.
- GitHub Actions CI membuat container image, melakukan security scanning dengan Trivy.
- Jika lolos, GitHub Actions membuat PR otomatis ke repositori `k8s-gitops-manifests` untuk mengupdate image SHA.
- ArgoCD mendeteksi update dan melakukan Canary Rollout dengan 3 tahapan (10%, 50%, 100%) dengan jeda verifikasi metrik 2 menit di setiap tahap.

---

## 20. Summary
- **GitOps** mengubah repositori Git menjadi *single source of truth* untuk seluruh state cluster.
- **ArgoCD** beroperasi dengan model pull-based, menghilangkan kebutuhan membeberkan kredensial cluster ke internet.
- **Auto-healing** dan **Pruning** memastikan cluster selalu selaras 100% dengan deklarasi kode di Git dan kebal terhadap drift manual.
- **Argo Rollouts** membawa kemampuan deployment enterprise (Canary dan Blue/Green) dengan mitigasi risiko otomatis.
