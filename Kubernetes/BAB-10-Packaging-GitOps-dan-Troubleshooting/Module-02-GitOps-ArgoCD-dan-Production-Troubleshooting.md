---
[⬅️ Module 01: Helm v3 vs Kustomize](./Module-01-Helm-v3-vs-Kustomize-Package-Management.md) | [📋 Silabus Induk](../README.md) | [BAB 10 Quiz & Challenge ➡️](./BAB-10-Quiz-dan-Challenge.md)
---

# Module 02: GitOps with ArgoCD & Production Troubleshooting Runbook

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Menguasai 4 prinsip fundamental **GitOps** (*OpenGitOps Standard*) dan membedakan model *Push-based CI/CD* vs *Pull-based Continuous Reconciliation*.
- Menjelaskan arsitektur internal **ArgoCD**: API Server, Repository Server, Application Controller, serta Custom Resource Definition (CRD) `Application` dan `ApplicationSet`.
- Mengonfigurasi kebijakan sinkronisasi otomatis (`automated`, `prune`, `selfHeal`) guna mengeliminasi *manual cluster drift*.
- Menggunakan *Sync Waves* dan *Resource Hooks* untuk mengatur urutan deployment bertingkat (Database migration $\rightarrow$ Backend $\rightarrow$ Frontend).
- Menjalankan **SRE Systematic Troubleshooting Runbook** untuk mendiagnosa dan memulihkan insiden produksi: `CrashLoopBackOff`, `OOMKilled` (Exit code 137), `ImagePullBackOff`, `CreateContainerConfigError`, dan *Selector Mismatch Service Endpoints*.
- Mendiagnosa degradasi performa DNS akibat latensi `ndots:5` pada CoreDNS.

---

## 2. Prerequisite
- Memahami Packaging Helm v3 dan Kustomize (Modul 01).
- Memahami konsep Git: commit, branch, merge request, tag.
- Konsep dasar sinyal Linux kernel (SIGTERM, SIGKILL 137, SIGSEGV 139).

---

## 3. Concept
Pada pipeline CI/CD tradisional (*Push-based*), server CI (seperti Jenkins atau GitHub Actions) memegang kredensial `kubeconfig` cluster produksi dan menjalankan perintah `kubectl apply` secara langsung dari luar firewall.
Pendekatan ini memiliki kelemahan fatal:
1. Kredensial cluster admin tersebar di banyak pipeline runner eksternal (resiko keamanan tinggi).
2. Jika ada engineer yang melakukan `kubectl edit` manual di cluster saat insiden darurat, konfigurasi live cluster tidak lagi sinkron dengan apa yang tertulis di repositori Git (*Configuration Drift*).
3. Tidak ada single source of truth yang transparan untuk audit compliance.

**GitOps** membalik paradigma ini menjadi **Pull-based Reconciliation**:
Repositori Git adalah **Satu-satunya Sumber Kebenaran (Single Source of Truth)**. Operator agen yang berjalan di dalam cluster (**ArgoCD**) secara terus-menerus membandingkan keadaan nyata (*Live State*) di Kubernetes dengan keadaan yang diinginkan (*Desired State*) di Git. Jika terjadi perbedaan (*Drift*), ArgoCD otomatis mengoreksi (*Self-Heal*) cluster agar kembali persis sesuai kode di Git.

```
+-----------------------------------------------------------------------------------+
|                        GITOPS CONTINUOUS RECONCILIATION                           |
|                                                                                   |
|   [ Git Repository ] <----------------------------------------+                   |
|   (Desired State: Replicas=5, Tag=v2.0)                       |                   |
|            |                                                  |                   |
|            | Pulls every 3 minutes                            |                   |
|            v                                                  |                   |
|   +---------------------------------------+                   |                   |
|   | ARGOCD CONTROLLER (Inside Cluster)    |                   |                   |
|   |                                       |                   |                   |
|   | 1. Compares Desired State (Git)       |                   |                   |
|   |    vs Live State (Cluster etcd)       |                   |                   |
|   |                                       |                   |                   |
|   | 2. Detects DRIFT:                     |                   |                   |
|   |    Live State was modified to 2 Pods! |                   |                   |
|   |                                       |                   |                   |
|   | 3. SELF-HEAL TRIGGERED:               |                   |                   |
|   |    Overwrites cluster back to 5 Pods! |                   |                   |
|   +-------------------+-------------------+                   |                   |
|                       |                                       |                   |
|                       v kubectl apply (Local API)             |                   |
|   +---------------------------------------+                   |                   |
|   | LIVE KUBERNETES CLUSTER               |                   |                   |
|   | [Pod 1] [Pod 2] [Pod 3] [Pod 4] [Pod 5]                   |                   |
|   +---------------------------------------+                   |                   |
|                       ^                                       |                   |
|                       | Unauthorized `kubectl edit` (Rejected)|                   |
|                 [ Rogue User ] -------------------------------+                   |
+-----------------------------------------------------------------------------------+
```

---

## 4. Why?
Mengapa GitOps dan sistematika troubleshooting merupakan keahlian wajib insinyur Kubernetes?
1. **Zero-Access Production Clusters**: Tidak ada manusia atau server eksternal yang memiliki akses port 443 ke API Server produksi. Semua perubahan infrastruktur harus melalui Pull Request (PR) yang ditinjau oleh rekan sejawat (*Peer Review*).
2. **Instant Disaster Recovery**: Jika satu datacenter musnah total, cluster baru dapat dibangun dan seluruh 200 microservice dapat di-deploy ulang dalam hitungan menit hanya dengan menghubungkan ArgoCD ke repositori Git.
3. **Mengurangi Mean Time To Recovery (MTTR)**: Dengan runbook troubleshooting terstruktur, tim on-call dapat mengidentifikasi akar masalah (apakah OOMKilled, konfigurasi environment, atau Service selector) dalam waktu kurang dari 5 menit.

---

## 5. What?

### A. Komponen Inti ArgoCD
1. **`argocd-server`**: Layanan web API dan dashboard UI grafis.
2. **`argocd-repo-server`**: Meng-clone repositori Git lokal, menjalankan `helm template` atau `kustomize build` untuk menghasilkan manifest YAML murni.
3. **`argocd-application-controller`**: Mesin rekonsiliasi utama yang membandingkan live object di Kube-APIServer dengan manifest hasil render, serta menjalankan aksi Sync, Prune, dan Health Checks.

### B. Objek Deklaratif ArgoCD: `Application`
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: payment-service-prod
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io # Hapus seluruh resource jika App dihapus
spec:
  project: default
  source:
    repoURL: https://github.com/my-org/k8s-gitops-manifests.git
    targetRevision: main
    path: apps/payment/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: payment-production
  syncPolicy:
    automated:
      prune: true # Hapus objek K8s yang sudah dihapus dari Git
      selfHeal: true # Kembalikan perubahan manual liar ke state Git
    syncOptions:
      - CreateNamespace=true
```

### C. Sync Waves: Orkestrasi Deployment Terurut
Dengan anotasi `argocd.argoproj.io/sync-wave`, ArgoCD mengeksekusi deployment secara berurutan:
- `Wave -1`: Menjalankan Database Migration Job (`batch/v1`).
- `Wave 0`: Men-deploy Backend Core Services (`apps/v1`).
- `Wave 1`: Men-deploy Frontend & Ingress Routes.

---

## 6. How: Production Troubleshooting Runbook

Ketika pager on-call berbunyi di tengah malam, ikuti pohon keputusan diagnostik terstruktur berikut:

```
                              POD TIDAK BERJALAN?
                                       |
                   +-------------------+-------------------+
                   |                                       |
            Status: Pending                 Status: Waiting / Crash
                   |                                       |
         kubectl describe pod                    kubectl describe pod
                   |                                       |
    +--------------+--------------+             +----------+----------+
    |                             |             |                     |
Insufficient CPU/RAM       Taint/Affinity  CrashLoopBackOff       OOMKilled
(Scale node/Karpenter)     (Fix toleration)     |                     |
                                          kubectl logs --previous  (Exit code 137)
                                                |                     |
                                          App logic error      Naikkan memory limit
```

---

## 7. Analogy
Bayangkan **Orkestra Musik Simfoni (GitOps)**:
- **Partitur Musik (Git Repo)**: Desired State. Semua nada, birama, dan instrumen tertulis di sana secara baku.
- **Konduktor Orkestra (ArgoCD)**: Secara konstan mendengarkan suara pemain biola dan trompet (**Live State**). Jika pemain biola bermain di luar nada partitur (**Configuration Drift**), konduktor langsung mengisyaratkan pemulihan nada (**Self-Healing**).
- **Troubleshooting Runbook**: Seperti **Buku Panduan Dokter IGD**. Dokter tidak menebak-nebak penyakit pasien secara acak, melainkan memeriksa tanda vital secara berurutan: Jalan napas (CPU/RAM Pending), Detak jantung (Probes), dan Tes darah (Logs / Exit Codes).

---

## 8. Diagram: Diagnostic Flowchart Kasus Populer

```
+---------------------------------------------------------------------------------+
|                       KUBERNETES SRE DIAGNOSTIC MATRIX                          |
+---------------------------------------------------------------------------------+

Error Pattern               Probable Root Cause             Diagnostic Command
---------------------------------------------------------------------------------
CrashLoopBackOff            App panic, wrong DB password,   kubectl logs <pod> --previous
                            syntax error in config file

OOMKilled (Exit Code 137)   Memory leak, JVM heap > limit,  kubectl describe pod <pod>
                            Linux kernel killed process     | grep -A 3 "Last State"

ImagePullBackOff            Typo in tag, private registry   kubectl describe pod <pod>
                            needs imagePullSecrets          | grep -A 5 "Events:"

CreateContainerConfigError  ConfigMap / Secret referenced   kubectl get configmaps,secrets
                            in envFrom does not exist       -n <namespace>

Service 0 Endpoints         Pod labels don't match          kubectl get endpoints <svc>
(HTTP 502/503 Bad Gateway)  spec.selector in Service        kubectl get pods --show-labels
```

---

## 9. Simple Example: Debugging Exit Code 137 (OOMKilled)

Jika container mati mendadak dan `kubectl describe pod` menampilkan:
```text
Last State:     Terminated
  Reason:       OOMKilled
  Exit Code:    137
```
**Mengapa 137?**
Dalam standar POSIX Linux: Exit code > 128 berarti proses dimatikan oleh sinyal kernel:
$$\text{Exit Code} = 128 + \text{Signal Number}$$
Sinyal nomor 9 adalah `SIGKILL` ($128 + 9 = 137$). Kernel Linux OOM-Killer mematikan proses paksa karena proses melebihi `resources.limits.memory`.

**Solusi**:
1. Analisis profile memori aplikasi (misal pprof untuk Go, memory heap dump untuk Java/Node.js).
2. Naikkan `resources.limits.memory` di manifest Deployment dan commit ke Git.

---

## 10. Practical Example: Mengatasi "Zero Endpoints" pada Service
Aplikasi web tidak bisa diakses dan Ingress melempar `HTTP 503 Service Temporarily Unavailable`.

```bash
# 1. Cek endpoints pada Service
kubectl get endpoints web-service -n production
# Output:
# NAME          ENDPOINTS   AGE
# web-service   <none>      2m   <--- TIDAK ADA POD TERIKAT!

# 2. Periksa selector pada Service
kubectl get service web-service -n production -o jsonpath='{.spec.selector}'
# Output: {"app":"my-web","tier":"frontend"}

# 3. Periksa labels pada Pod
kubectl get pods -n production --show-labels
# Output:
# NAME             READY   STATUS    LABELS
# my-web-pod-xxx   1/1     Running   app=my-web,environment=prod  <--- LABEL 'tier=frontend' HILANG!

# 4. Solusi: Sesuaikan label di Deployment template agar cocok persis dengan selector Service.
```

---

## 11. Real World Example: DNS Latency Masalah `ndots:5`
Pada cluster berskala besar, developer sering mengeluhkan panggilan HTTP ke database eksternal (`db.cloud.internal`) sangat lambat dan CoreDNS mengalami spike CPU.

**Akar Masalah Teknis**:
Secara default, file `/etc/resolv.conf` di dalam container Kubernetes memiliki konfigurasi:
`options ndots:5`.
Artinya, jika domain memiliki kurang dari 5 titik (seperti `api.stripe.com` yang hanya memiliki 2 titik), Linux resolver akan **mencoba mencari domain internal cluster terlebih dahulu** sebelum bertanya ke internet:
1. `api.stripe.com.production.svc.cluster.local` (CoreDNS -> NXDOMAIN)
2. `api.stripe.com.svc.cluster.local` (CoreDNS -> NXDOMAIN)
3. `api.stripe.com.cluster.local` (CoreDNS -> NXDOMAIN)
4. `api.stripe.com` (Baru berhasil!)
Setiap panggilan HTTP menghasilkan 3 query DNS sampah ke CoreDNS!

**Solusi Arsitektur**:
1. Gunakan titik di akhir FQDN: `api.stripe.com.` (trailing dot mencegah pencarian search domain).
2. Atau modifikasi `dnsConfig` pada Pod:
```yaml
spec:
  dnsConfig:
    options:
      - name: ndots
        value: "2"
```

---

## 12. Trade-offs

| Aspek | Push-based CI/CD (Pipeline Biasa) | GitOps Pull-based (ArgoCD) |
|---|---|---|
| **Keamanan Kredensial** | Buruk (Kredensial cluster disimpan di runner CI eksternal) | Sempurna (Kredensial tetap berada di dalam firewall cluster) |
| **Pencegahan Drift** | Nol (Perubahan manual di cluster tidak terdeteksi) | Otomatis (Self-Heal menimpa drift seketika) |
| **Kurva Belajar** | Mudah (Hanya menjalankan script shell) | Menengah (Memerlukan pemahaman CRD, Git workflow, & RBAC) |
| **Auditability** | Tersebar di log jobs berbagai pipeline | Terpusat pada Git commit history |

---

## 13. When To Use
- Selalu terapkan **GitOps (ArgoCD)** untuk seluruh cluster staging dan produksi modern.
- Aktifkan `selfHeal: true` dan `prune: true` pada seluruh lingkungan yang sudah matang.
- Gunakan checklist troubleshooting di runbook ini sebagai panduan resmi tim on-call SRE.

---

## 14. When NOT To Use
- **JANGAN** menyalakan `selfHeal: true` pada cluster sandbox atau environment debugging sementara saat developer sedang melakukan live-debugging menggunakan `telepresence` atau `kubectl port-forward`.
- Jangan menggunakan `kubectl apply` manual pada cluster yang sudah dikelola oleh ArgoCD.

---

## 15. Common Mistakes
1. **Melakukan Perubahan Langsung di Cluster**: Menjalankan `kubectl scale deployment --replicas=5`. 3 menit kemudian, ArgoCD melihat Git masih tertulis `replicas=2`, dan ArgoCD langsung membunuh 3 Pod tersebut! Semua perubahan WAJIB via commit Git.
2. **Lupa Anotasi Prune**: Saat developer menghapus manifest Service dari Git, jika `prune: true` tidak diaktifkan, Service tersebut akan menjadi "zombie resource" yang tertinggal selamanya di cluster.
3. **Mengabaikan Log `--previous`**: Menjalankan `kubectl logs <crashed-pod>` dan mendapatkan pesan `container not found`. Karena container sudah me-restart, tambahkan flag `--previous` untuk melihat log sesaat sebelum crash terjadi.

---

## 16. Best Practices
- **Must Have**: Pasang `resources-finalizer.argocd.argoproj.io` pada setiap manifest Application ArgoCD agar penghapusan aplikasi membersihkan seluruh child resources secara tuntas.
- **Recommended**: Pisahkan repositori kode aplikasi (*Application Source Code Repo*) dengan repositori konfigurasi GitOps (*Config / Environment Repo*).
- **Advanced**: Implementasikan **Argo Rollouts** untuk deployment berbasis *Canary Release* dan *Blue-Green* dengan analisis metrik otomatis (Prometheus p99 latency & error rate).
- **Avoid**: Memberikan akses `kubectl write` kepada personil manusia di cluster produksi.

---

## 17. Troubleshooting Guide
```
Masalah: ArgoCD menampilkan status Application "OutOfSync".
Penyebab : Ada perbedaan antara manifest di Git dan objek live di cluster (bisa karena mutasi webhook, field k8s bawaan, atau editan manual).
Diagnosa : Buka UI ArgoCD -> Klik tombol "Diff" untuk melihat baris YAML yang tidak sinkron.
Solusi   : Tambahkan 'ignoreDifferences' pada spesifikasi Application jika perbedaan disebabkan oleh mutating webhook controller pihak ketiga.

Masalah: Pod stuck di "ImagePullBackOff".
Penyebab : Tag container salah ketik, atau image berada di private registry dan Pod belum dikonfigurasi dengan 'imagePullSecrets'.
Diagnosa : kubectl describe pod <pod-name> | grep -E "(Failed|BackOff)"
Solusi   : Buat Secret tipe docker-registry dan sematkan 'imagePullSecrets' pada spec Pod.
```

---

## 18. Exercise
1. Buat repositori Git baru berisi manifest Deployment NGINX sederhana.
2. Tulis manifest CRD ArgoCD `Application` yang menunjuk ke repositori tersebut dengan `automated.selfHeal: true`.
3. Setelah dideploy oleh ArgoCD, lakukan manipulasi manual di cluster: ubah replika dari 1 menjadi 4 menggunakan `kubectl scale`.
4. Amati dashboard ArgoCD mengembalikan replika menjadi 1 secara otomatis dalam beberapa saat.

---

## 19. Challenge
Simulasikan insiden produksi terpadu:
1. Deploy sebuah Pod yang sengaja mengalami kebocoran memori (memory leak script) dengan `resources.limits.memory: 64Mi`.
2. Amati Pod mengalami `OOMKilled` (Exit Code 137) dan masuk ke `CrashLoopBackOff`.
3. Gunakan perintah diagnostik (`kubectl describe`, `kubectl get events`, `kubectl logs --previous`) untuk membuktikan akar masalah.
4. Perbaiki spesifikasi manifest melalui commit Git dan biarkan ArgoCD melakukan rekonsiliasi hingga status aplikasi kembali `Healthy`.

---

## 20. Summary
GitOps mengubah paradigma pengelolaan kluster Kubernetes menjadi deterministik, aman, dan dapat diaudit secara transparan dengan menjadikan Git sebagai satu-satunya jangkar kebenaran. Didampingi dengan kemampuan diagnostik yang tajam terhadap anomali runtime container, seorang insinyur sistem dapat menjaga stabilitas dan keandalan sistem produksi dalam skala enterprise.

---
[⬅️ Module 01: Helm v3 vs Kustomize](./Module-01-Helm-v3-vs-Kustomize-Package-Management.md) | [📋 Silabus Induk](../README.md) | [BAB 10 Quiz & Challenge ➡️](./BAB-10-Quiz-dan-Challenge.md)
---
