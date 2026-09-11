---
[⬅️ BAB 10 Quiz & Challenge](./BAB-10-Packaging-GitOps-dan-Troubleshooting/BAB-10-Quiz-dan-Challenge.md) | [📋 Silabus Induk](./README.md)
---

# CAPSTONE PROJECT: Enterprise Multi-Tenant Microservices Platform on Kubernetes

## 1. Project Overview & Business Context
Selamat datang di proyek akhir (*Capstone Project*) kurikulum **Kubernetes Mastery**.
Proyek ini mengintegrasikan seluruh konsep yang telah Anda pelajari dari **Bab 01 hingga Bab 10** ke dalam satu studi kasus arsitektur nyata berskala enterprise: **Bank Mandiri Digital Financial Platform (PayNusantara)**.

Sistem PayNusantara melayani jutaan transaksi keuangan harian yang menuntut standar ketersediaan tinggi (*High Availability 99.99%*), kepatuhan regulasi ketat (*PCI-DSS Level 1 & Zero-Trust Security*), isolasi multi-tenant antar divisi, skalabilitas elastis otomatis saat promo payday, serta alur rilis modern berbasis GitOps tanpa downtime.

```
+---------------------------------------------------------------------------------------------------+
|                        ENTERPRISE CLOUD ARCHITECTURE: AWS ap-southeast-1                         |
|                                                                                                   |
|                                [ Route53 & AWS WAF ]                                              |
|                                          |                                                        |
|                                          v                                                        |
|                             [ AWS Network Load Balancer ]                                         |
|                                          |                                                        |
|                   +----------------------+----------------------+                                 |
|                   |                      |                      |                                 |
|                   v                      v                      v                                 |
|             [ AZ: 1a ]             [ AZ: 1b ]             [ AZ: 1c ]                              |
|          Ingress NGINX          Ingress NGINX          Ingress NGINX (DaemonSet)                  |
|                   |                      |                      |                                 |
| ==================|======================|======================|================================ |
|                   v                      v                      v                                 |
|  [ NAMESPACE: payment-production ] (Pod Security Standard: Restricted)                            |
|                                                                                                   |
|    +------------------------+  (TopologySpread maxSkew:1)  +------------------------+             |
|    | Payment API Pod (AZ1a) | <--------------------------> | Payment API Pod (AZ1b) |             |
|    | CPU: 500m / RAM: 1Gi   |                              | CPU: 500m / RAM: 1Gi   |             |
|    +-----------+------------+                              +-----------+------------+             |
|                |                                                       |                          |
|                +---------------------------+---------------------------+                          |
|                                            |                                                      |
|                                            v (NetworkPolicy: Port 5432 Only)                      |
|  +---------------------------------------------------------------------------------------------+  |
|  | NAMESPACE: database-production ] (Taint: dedicated=db:NoSchedule)                           |  |
|  |                                                                                             |  |
|  |   StatefulSet PostgreSQL HA (pgpool-II + Patroni Leader Election)                           |  |
|  |   - Primary Pod (AZ 1a) <---- Async Stream Replicas ----> Standby Pod (AZ 1b)                |  |
|  |   - CSI EBS gp3 (WaitForFirstConsumer, Retain Policy, Online Volume Expansion)              |  |
|  |   - Automated VolumeSnapshot scheduled every 6 hours                                        |  |
|  +---------------------------------------------------------------------------------------------+  |
|                                                                                                   |
| ================================================================================================= |
|  [ AUTOSCALING & GITOPS CONTROL PLANE ]                                                           |
|                                                                                                   |
|  [ HPA v2 ] (CPU 65% + QPS 500) <---> [ Karpenter ] (Just-in-Time Spot/On-Demand Provisioning)    |
|  [ KEDA ] (Scale-to-Zero Queue Workers) <---> [ ArgoCD ] (GitOps Automated Self-Healing Engine)   |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Blueprint Spesifikasi Persyaratan Sistem

### A. Persyaratan Multi-Tenancy & Namespace Isolation
1. **`payment-production`**: Tempat berjalannya stateless microservices transaksi pembayaran.
2. **`database-production`**: Tempat berjalannya stateful datastore PostgreSQL berkecepatan tinggi.
3. **`gitops-system`**: Namespace khusus untuk controller ArgoCD.
4. **`security-monitoring`**: Tempat berjalannya Prometheus, Grafana, dan Kyverno/OPA Gatekeeper.

### B. Persyaratan Keamanan (Zero-Trust & PCI-DSS)
1. **Pod Security Admission (PSA)**:
   - Namespace `payment-production` WAJIB mengaktifkan profil `restricted` pada mode `enforce`, `audit`, dan `warn`.
2. **RBAC Least Privilege**:
   - ServiceAccount microservice tidak boleh memiliki akses write ke Kubernetes API Server (`automountServiceAccountToken: false`).
   - Developer dilarang memiliki akses `exec` di namespace produksi.
3. **Network Microsegmentation**:
   - Terapkan kebijakan **Default-Deny Ingress & Egress** di seluruh namespace aplikasi.
   - Microservice Payment hanya diizinkan berkomunikasi ke database PostgreSQL pada port `5432 TCP` dan ke CoreDNS pada port `53 UDP`.

### C. Persyaratan Storage & Persistensi
1. Buat `StorageClass` khusus database (`database-gp3-sc`):
   - Provisioner: `ebs.csi.aws.com`.
   - `volumeBindingMode: WaitForFirstConsumer` (mencegah salah alokasi Availability Zone).
   - `reclaimPolicy: Retain`.
   - `allowVolumeExpansion: true`.
2. Database dijalankan menggunakan `StatefulSet` dengan `volumeClaimTemplates` berkapasitas awal `50Gi`.

### D. Persyaratan High Availability & Scheduling
1. Terapkan `topologySpreadConstraints` dengan `maxSkew: 1` pada label zona `topology.kubernetes.io/zone` untuk Deployment Payment API.
2. Pasang `PodDisruptionBudget (PDB)` dengan `minAvailable: 2` untuk menjamin ketersediaan selama proses *node drain* atau *cluster upgrade*.
3. Worker node database diberi Taint `dedicated=database:NoSchedule` agar Pod aplikasi web tidak mengganggu performa IOPS database (*noisy neighbor protection*).

### E. Persyaratan Autoscaling Dinamis
1. **HPA v2**: Menargetkan utilisasi CPU 65% dengan jendela stabilisasi scale-down 300 detik (*anti-flapping*). Rentang replika: 3 hingga 30 Pod.
2. **Karpenter**: Dikonfigurasi dengan `NodePool` hibrida (mengutamakan Spot Instances untuk worker dan On-Demand untuk database). Mengaktifkan `consolidationPolicy: WhenUnderutilized`.

### F. Persyaratan GitOps Deployment
1. Struktur konfigurasi menggunakan **Kustomize** (`base/` dan `overlays/production/`).
2. Objek CRD ArgoCD `Application` dengan kebijakan `automated.selfHeal: true` dan `automated.prune: true`.
3. Menggunakan **Sync Waves**:
   - Wave 0: Namespace, Secrets, StorageClass, NetworkPolicies.
   - Wave 1: Database StatefulSet & Migration Jobs.
   - Wave 2: Payment API Deployment & Service.
   - Wave 3: Ingress Routes & HPA.

---

## 3. Implementasi Deklaratif: Paket Manifest Lengkap

### Milestone 1: Namespace Hardening & Pod Security Standards
```yaml
# 01-namespaces.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: payment-production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
---
apiVersion: v1
kind: Namespace
metadata:
  name: database-production
  labels:
    pod-security.kubernetes.io/enforce: baseline # Baseline mengizinkan kontainer database beroperasi optimal
```

### Milestone 2: StorageClass & Database StatefulSet
```yaml
# 02-storage-and-database.yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: database-gp3-sc
provisioner: ebs.csi.aws.com
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
reclaimPolicy: Retain
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
  encrypted: "true"
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres-primary
  namespace: database-production
spec:
  serviceName: postgres-headless
  replicas: 1
  selector:
    matchLabels:
      app: postgres-db
  template:
    metadata:
      labels:
        app: postgres-db
    spec:
      tolerations:
        - key: "dedicated"
          operator: "Equal"
          value: "database"
          effect: "NoSchedule"
      containers:
        - name: postgres
          image: postgres:16-alpine
          ports:
            - containerPort: 5432
          env:
            - name: POSTGRES_DB
              value: "paynusantara"
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: password
          volumeMounts:
            - name: pg-storage
              mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
    - metadata:
        name: pg-storage
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: database-gp3-sc
        resources:
          requests:
            storage: 50Gi
```

### Milestone 3: Zero-Trust Network Microsegmentation
```yaml
# 03-network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: payment-api-netpol
  namespace: payment-production
spec:
  podSelector:
    matchLabels:
      app: payment-api
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # 1. Hanya terima traffic HTTP dari Ingress NGINX Controller
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8080
  egress:
    # 2. Izinkan komunikasi ke Database PostgreSQL di namespace database-production
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: database-production
          podSelector:
            matchLabels:
              app: postgres-db
      ports:
        - protocol: TCP
          port: 5432
    # 3. WAJIB: Izinkan DNS Lookup ke CoreDNS
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
```

### Milestone 4: Payment Microservice Deployment (PSS Restricted Compliant)
```yaml
# 04-payment-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-api
  namespace: payment-production
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
      # PSS Restricted Hardening
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault
      automountServiceAccountToken: false # Anti-Privilege Escalation
      # High Availability Multi-AZ Distribution
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: payment-api
      containers:
        - name: payment-api
          image: myregistry.io/paynusantara/payment-api:v3.2.0
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 1000m
              memory: 2Gi
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

### Milestone 5: Autoscaling & Disruption Budget
```yaml
# 05-autoscaling-pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: payment-api-pdb
  namespace: payment-production
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: payment-api
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: payment-api-hpa
  namespace: payment-production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: payment-api
  minReplicas: 3
  maxReplicas: 30
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 65
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
```

### Milestone 6: GitOps Continuous Delivery via ArgoCD
```yaml
# 06-argocd-application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: paynusantara-enterprise
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "0"
spec:
  project: default
  source:
    repoURL: https://github.com/paynusantara-org/k8s-gitops.git
    targetRevision: main
    path: environments/production
  destination:
    server: https://kubernetes.default.svc
    namespace: payment-production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ApplyOutOfSyncOnly=true
```

---

## 4. Panduan Verifikasi & Validasi Produksi

Jalankan serangkaian uji coba operasional berikut untuk memvalidasi kesiapan platform:

| No | Uji Pengujian | Perintah Diagnostik / Verifikasi | Hasil yang Diharapkan |
|---|---|---|---|
| 1 | **Audit PSS Restricted** | `kubectl apply -f test-root-pod.yaml -n payment-production` | Ditolak seketika oleh API Server (*Forbidden: violates PodSecurity restricted*). |
| 2 | **Distribusi Multi-AZ** | `kubectl get pods -n payment-production -o wide` | 3 Pod tersebar di 3 zona yang berbeda (`ap-southeast-1a`, `1b`, `1c`). |
| 3 | **Isolasi NetworkPolicy** | `kubectl exec -it <payment-pod> -- nc -zvw3 8.8.8.8 443` | Koneksi timeout (*Egress blocked*). Akses ke port 5432 database berhasil (*Connected*). |
| 4 | **PDB & Graceful Drain** | `kubectl drain <worker-node> --ignore-daemonsets` | Minimal 2 Pod Payment API selalu aktif melayani traffic; tidak ada downtime. |
| 5 | **GitOps Self-Healing** | `kubectl scale deployment payment-api --replicas=10 -n payment-production` | Dalam waktu < 30 detik, ArgoCD mengembalikan jumlah replika menjadi 3 sesuai Git. |
| 6 | **Dynamic Storage Expansion** | Ubah `resources.requests.storage: 100Gi` pada PVC PostgreSQL | Disk EBS diperbesar di AWS dan filesystem Linux di-resize tanpa mematikan database. |

---

## 5. Kesimpulan & Kelulusan Kurikulum
Dengan merampungkan Capstone Project ini, Anda telah mendemonstrasikan penguasaan menyeluruh atas ekosistem **Kubernetes tingkat lanjut**:
- Arsitektur Control Plane & Worker Node internals.
- Desain Workload, Lifecycle, dan Multi-Container Patterns.
- Storage CSI dinamis dan persistensi database tingkat enterprise.
- Jaringan eBPF CNI modern, Ingress, dan Network Security mikrosegmentasi.
- Hardening keamanan RBAC, PSS Restricted, dan Admission Webhooks.
- Penjadwalan cerdas Multi-AZ, HPA v2, dan elastisitas cloud just-in-time via Karpenter.
- Manajemen paket Helm/Kustomize dan automasi GitOps ArgoCD.

**Selamat! Anda telah memiliki kompetensi level Senior Kubernetes Administrator / Lead Platform Engineer.**

---
[⬅️ BAB 10 Quiz & Challenge](./BAB-10-Packaging-GitOps-dan-Troubleshooting/BAB-10-Quiz-dan-Challenge.md) | [📋 Silabus Induk](./README.md)
---
