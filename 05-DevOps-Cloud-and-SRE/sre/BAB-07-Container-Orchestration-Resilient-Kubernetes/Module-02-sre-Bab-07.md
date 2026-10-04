# BAB 07: Container Orchestration & Resilient Kubernetes
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis siklus hidup kontainer tingkat rendah (*kernel level*) di dalam node Kubernetes, mencakup integrasi Kubelet, Container Runtime Interface (CRI), Linux cgroups v2, dan OOM Killer.
- Merancang dan mengonfigurasi strategi penjadwalan beban kerja tingkat lanjut (*advanced workload placement*) menggunakan Node Affinity, Taints/Tolerations, Pod Topology Spread Constraints, dan Pod Disruption Budgets (PDB).
- Mengonfigurasi kelas Quality of Service (QoS) pod secara presisi untuk mengeliminasi dampak *noisy neighbor* dan *CFS (Completely Fair Scheduler) quota throttling*.
- Mengimplementasikan mekanisme autoscaling multidimensi yang stabil (kombinasi Horizontal Pod Autoscaler dengan custom metrics dan Vertical Pod Autoscaler) untuk mencegah *flapping/oscillations*.
- Mendiagnosis dan memitigasi anomali orkestrasi skala besar seperti *cascade eviction*, *thundering herd*, dan node resource starvation di lingkungan produksi multi-zona.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Arsitektur Dasar Kubernetes**: Memahami peran API Server, Etcd, Controller Manager, Scheduler, Kubelet, dan Kube-proxy.
- **Konsep Inti Linux Kernel**: Namespace (PID, Mount, Net, IPC, UTS, User), cgroups (v1/v2), iptables/nftables, dan sinyal POSIX (SIGTERM, SIGKILL).
- **Networking & Storage Dasar**: Container Network Interface (CNI), Overlay Network (VXLAN/Geneve), Persistent Volumes, dan CSI.
- **Observabilitas Dasar**: PromQL (Prometheus Query Language) dan metrik komputasi Linux (`/proc/stat`, `/sys/fs/cgroup`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Node Architecture: Kubelet, CRI, dan Linux Kernel Isolation
Di balik abstraksi Pod, Kubernetes bergantung pada interaksi antara **Kubelet**, **Container Runtime (e.g., containerd / CRI-O)**, dan subsistem kernel Linux:

```
[ Kubelet ]
     │ (gRPC via UNIX Domain Socket: /run/containerd/containerd.sock)
     ▼
[ CRI Plugin (containerd) ]
     │
     ▼
[ OCI Runtime (runc / crun) ]
     │ (clone(), unshare(), pivot_root())
     ▼
[ Linux Kernel Subsystems ]
 ├── cgroups v2 (/sys/fs/cgroup/)
 │    ├── cpu.max & cpu.weight (CFS Quotas)
 │    ├── memory.max & memory.high (Page cache & RSS)
 │    └── memory.oom.group
 └── Namespaces (PID, Mount, Net, IPC, UTS)
```

1. **CPU Allocation**: Dikelola oleh CFS (*Completely Fair Scheduler*). Nilai `limits.cpu: 1000m` di-translate menjadi kuota bandwidth cgroup:
   - `cpu.cfs_period_us` (default: 100ms = 100000us)
   - `cpu.cfs_quota_us` (1000m = 100000us; 500m = 50000us)
   Jika pod melampaui kuota dalam periode tersebut, kernel mencekik (*throttles*) eksekusi thread pod tersebut tanpa membunuhnya.
2. **Memory Allocation**: Dikelola via cgroup memory controller.
   - `requests.memory` memetakan batas reservasi node dan skor `oom_score_adj`.
   - `limits.memory` memetakan batas mutlak `memory.max`. Jika *resident set size* (RSS) + *unreclaimable page cache* menyentuh limit ini, kernel memicu `OOM Killer` untuk menembak proses via sinyal `SIGKILL` (Exit Code 137).

#### B. Pod QoS Classes dan OOM Scoring Calculation
Kubernetes mengelompokkan Pod ke dalam 3 kelas QoS untuk menentukan prioritas eviksi saat node mengalami tekanan memori (*Node Memory Pressure*):

| QoS Class | Kondisi Spesifikasi Pod | Nilai `oom_score_adj` | Urutan Terminasi saat OOM |
| :--- | :--- | :--- | :--- |
| **Guaranteed** | CPU & Memory `requests == limits` untuk semua kontainer | -997 | Terakhir dibunuh |
| **Burstable** | `requests < limits` atau minimal 1 kontainer punya `requests` | `min(max(2, 1000 - (1000 * memoryRequestBytes) / nodeCapacityBytes), 999)` | Dibunuh setelah BestEffort |
| **BestEffort** | Tidak ada `requests` maupun `limits` sama sekali | 1000 | Pertama kali dibunuh |

> **Catatan Arsitektur**: Daemon Kubelet dan runtime container berjalan dengan `oom_score_adj: -998` atau `-1000` untuk mencegah sistem orkestrasi mati sebelum mematikan workload beban pengguna.

#### C. Advanced Pod Scheduling Lifecycle
Scheduler Kubernetes memilih node melalui dua fase utama:
1. **Filtering (Predicates)**: Memvalidasi kelaikan node (misalnya: ketersediaan resource, port conflict, taints/tolerations, node selectors).
2. **Scoring (Priorities)**: Menghitung bobot node berdasarkan `TopologySpreadConstraints` (distribusi zona seimbang), `NodeAffinity` preferensial, dan `ImageLocalityPriority` (apakah image sudah ter-cache di node).

---

### 4. Why & What
- **Why**: Dalam ekosistem multi-tenant berskala ribuan transaksi per detik, konkurensi tak terprediksi dapat memicu *cascading failures*. Node bisa kehabisan memori secara mendadak, CFS throttling dapat meningkatkan latensi P99 hingga 400%, dan rolling deployment tanpa koordinasi zona dapat meruntuhkan seluruh instance service di availability zone yang sama.
- **What**: Modul ini membahas arsitektur pertahanan pod (*pod resilience design patterns*), isolasi resource tingkat kernel, distribusi pod tahan kegagalan (*fault-domain aware placement*), dan koordinasi lifecycle pod terpadu untuk memastikan *Zero Downtime Deployment* dengan ketersediaan sistem $\ge 99.99\%$.

---

### 5. How (Workflow Detail)

```
[ Pod Deployment Triggered ]
             │
             ▼
[ Kube-Scheduler ] ─── Filters Node via Taints & Resources
             │
             ├── Evaluates TopologySpreadConstraints (Spread across AZs)
             ├── Evaluates PodAffinity / PodAntiAffinity
             ▼
[ Node Selected & Bound ]
             │
             ▼
[ Kubelet on Selected Node ]
             │
             ├── 1. Validates Admission (Limits vs Capacity)
             ├── 2. Configures cgroups v2 (CPU/Memory hierarchy)
             ├── 3. Computes oom_score_adj based on QoS
             ├── 4. CRI Plugin -> Creates Sandbox & Namespaces
             ├── 5. CNI Plugin -> Allocates IP & Setup veth pair
             ├── 6. Container Runtime -> Starts container processes
             ▼
[ Pod Running & Serving Traffic ]
```

1. **Pre-Stop Phase**: Ketika pod ditandai untuk dihapus (`kubectl delete` atau rolling update), Pod status diubah menjadi `Terminating`.
2. **Endpoint De-registration**: API Server menghapus IP Pod dari `Endpoints` / `EndpointSlice` terkait. Secara paralel, Kube-Proxy/CNI membersihkan jalur iptables/eBPF routing.
3. **Execution of PreStop Hook**: Kubelet mengeksekusi hook `preStop` (misal: `sleep 15` untuk menunggu drain koneksi inflight dari reverse proxy/ingress controller).
4. **POSIX SIGTERM**: Kubelet mengirim sinyal `SIGTERM` ke PID 1 di kontainer.
5. **Grace Period Countdown**: Kubelet menunggu hingga batas `terminationGracePeriodSeconds` tercapai.
6. **POSIX SIGKILL**: Jika proses kontainer belum berhenti setelah window grace period berakhir, kernel mematikan paksa via `SIGKILL`.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Zonasi Hotel Bintang Lima & Manajemen Darurat
- **Pod**: Rombongan tamu hotel.
- **Kubelet**: Manajer lantai yang mengatur katering dan keamanan kamar.
- **cgroups v2**: Meteran air dan listrik kamar hotel. Jika Anda menghabiskan jatah air (*CPU CFS Throttling*), alirannya dikecilkan, tetapi Anda tidak diusir. Jika Anda melebihi kapasitas tempat tidur ekstra (*Memory Limit*), satpam (*OOM Killer*) langsung mengeluarkan anggota rombongan tambahan.
- **Topology Spread Constraints**: Kebijakan hotel untuk membagi delegasi VIP ke gedung sayap Barat, Timur, dan Utara secara merata, sehingga jika sayap Barat mengalami mati listrik, operasi bisnis delegasi tetap berjalan 66%.

#### Diagram Distribusi Pod Multi-AZ
```
       [ Region: ap-southeast-1 ]
 ┌──────────────────────────────────────┐
 │             Kubernetes Cluster       │
 └───────────────────┬──────────────────┘
                     │
    ┌────────────────┼────────────────┐
    ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Zone: az-a  │ │  Zone: az-b  │ │  Zone: az-c  │
│ ┌──────────┐ │ │ ┌──────────┐ │ │ ┌──────────┐ │
│ │  Node 01 │ │ │ │  Node 02 │ │ │ │  Node 03 │ │
│ │ ┌──────┐ │ │ │ │ ┌──────┐ │ │ │ │ ┌──────┐ │ │
│ │ │Pod-01│ │ │ │ │ │Pod-02│ │ │ │ │ │Pod-03│ │ │
│ │ └──────┘ │ │ │ │ └──────┘ │ │ │ │ └──────┘ │ │
│ └──────────┘ │ │ └──────────┘ │ │ └──────────┘ │
└──────────────┘ └──────────────┘ └──────────────┘
    maxSkew: 1 (Toleransi selisih jumlah Pod antar-AZ <= 1)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Menghitung CFS Quota
Jika dideklarasikan:
```yaml
resources:
  limits:
    cpu: "250m"
```
Nilai internal kernel yang di-generate oleh container runtime pada `/sys/fs/cgroup/cpu.max`:
```text
25000 100000
```
Artinya: Thread kontainer diizinkan menggunakan CPU selama 25.000 mikrosekon (25ms) setiap window 100.000 mikrosekon (100ms).

---

#### B. Practical Example: Production-Grade Stateful/Stateless Microservice Manifest

File: `production-resilient-deployment.yaml`
```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: high-priority-tier1
value: 1000000
globalDefault: false
description: "Workload kritis tier-1 core banking payment engine."
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: payment-engine-pdb
  namespace: core-banking
spec:
  minAvailable: 75%
  selector:
    matchLabels:
      app.kubernetes.io/name: payment-engine
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-engine
  namespace: core-banking
  labels:
    app.kubernetes.io/name: payment-engine
    app.kubernetes.io/part-of: transaction-processing
spec:
  replicas: 6
  revisionHistoryLimit: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 0
  selector:
    matchLabels:
      app.kubernetes.io/name: payment-engine
  template:
    metadata:
      labels:
        app.kubernetes.io/name: payment-engine
    spec:
      priorityClassName: high-priority-tier1
      terminationGracePeriodSeconds: 45
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app.kubernetes.io/name: payment-engine
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app.kubernetes.io/name: payment-engine
      containers:
        - name: payment-api
          image: internal-registry.bank.com/bin/payment-api:v2.4.1
          imagePullPolicy: IfNotPresent
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 15"]
          ports:
            - containerPort: 8080
              name: http-api
              protocol: TCP
          resources:
            requests:
              cpu: "1000m"
              memory: "2Gi"
            limits:
              cpu: "1000m"      # Strict QoS Guaranteed (Anti CFS-Throttling)
              memory: "2Gi"     # requests == limits -> oom_score_adj: -997
          readinessProbe:
            httpGet:
              path: /actuator/health/readiness
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 2
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /actuator/health/liveness
              port: 8080
            initialDelaySeconds: 20
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            runAsNonRoot: true
            runAsUser: 10001
            capabilities:
              drop:
                - ALL
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: "The Black Friday AZ Partition" pada Platform E-Commerce Asia Tenggara
* **Skala Sistem**: 120 Node m5.4xlarge, 1.400 Pods, 75.000 Request per Detik (RPS).
* **Insiden**: Salah satu Availability Zone (`ap-southeast-1a`) mengalami kegagalan kabel fiber bawah laut yang memicu kenaikan packet-loss hingga 35%. Kubelet di zona tersebut gagal melaporkan status (*Node NotReady*) secara fluktuatif.
* **Gejala**:
  1. Pod-pod di `ap-southeast-1a` dieviksi secara agresif setelah `node-monitor-grace-period` habis (40 detik).
  2. Kube-scheduler mencoba menjadwalkan ulang seluruh pod yang hilang ke node yang tersisa di `ap-southeast-1b` dan `ap-southeast-1c`.
  3. Terjadi lonjakan beban tiba-tiba (*thundering herd*) pada pod di zona lain, menyebabkan memori menyentuh batas maksimum dan node mengalami OOM Cascade.
* **Akar Masalah (*Root Cause*)**:
  1. Default `eviction-hard` kubelet terlalu agresif, tidak memiliki rate limiting untuk eviksi massal.
  2. Deployment tidak memiliki `PodTopologySpreadConstraints` yang ketat dan tidak mengonfigurasi `terminationGracePeriodSeconds` dengan benar, sehingga pod lama dimatikan sebelum pod pengganti siap melayani traffic (traffic dropping).
* **Solusi Arsitektural**:
  1. Mengimplementasikan `TopologySpreadConstraints` dengan `whenUnsatisfiable: DoNotSchedule` pada skala AZ.
  2. Menyesuaikan Controller Manager `--node-eviction-rate=0.1` dan `--secondary-node-eviction-rate=0.01` saat zona bermasalah terisolasi.
  3. Memisahkan `requests` dan `limits` untuk traffic burstable, sembari menerapkan HPA berbasis custom metrics (P95 Latency + Nginx Request Queue Depth via Prometheus Adapter).

---

### 9. Trade-offs (Analisis Arsitektur)

| Dimensi | Opsi A: QoS Guaranteed (`req == limit`) | Opsi B: QoS Burstable (`req < limit`) |
| :--- | :--- | :--- |
| **Performance** | Bebas CFS Throttling; latency throughput sangat stabil pada load puncak. | Berpotensi terkena CPU Throttling saat thread melonjak melebihi target quota. |
| **Latency** | Sangat rendah dan konsisten (P99 jitter minimal). | Rentan jitter tinggi jika CPU tertekan oleh pod lain di node yang sama. |
| **Scalability (Density)** | Rendah; pemanfaatan node tidak efisien (*bin-packing* menyisakan ruang idle). | Tinggi; utilisasi node optimal (*overcommit* kapasitas mesin). |
| **Cost** | Tinggi (+30-50% operational cloud spend karena alokasi node lebih banyak). | Rendah hingga moderat (memaksimalkan setiap core CPU dan byte RAM). |
| **Risk profile** | Minim risiko OOM Killer tak terduga; predictable failure profile. | Risiko tinggi eviksi mendadak saat terjadi lonjakan traffic simultan. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum:
1. **Setting CPU Limits Terlalu Rendah**: Mengasumsikan CPU limit sama seperti batas virtual machine. Hal ini memicu *CFS Throttling* parah meski utilisasi rata-rata CPU node hanya 30%.
2. **Ketiadaan PodDisruptionBudget (PDB)**: Saat automated cluster upgrade (AMI patching oleh Karpenter atau Cluster Autoscaler), seluruh node di-drain bersamaan dan menyebabkan pemadaman layanan total (*total outage*).
3. **Mengabaikan Sinyal SIGTERM pada Kontainer**: Menjalankan aplikasi via shell wrapper (`ENTRYPOINT ["/bin/sh", "-c", "node server.js"]`) yang tidak mem-forward sinyal kernel ke child process. Akibatnya, pod menunggu 30 detik sebelum di-*hard kill* via SIGKILL, merusak transaksi database yang sedang berjalan (*in-flight*).

#### Panduan Troubleshooting Langkah-demi-Langkah:
```bash
# 1. Mendeteksi apakah Pod terkena OOMKilled
kubectl get pods -n core-banking -o json | jq '.items[] | select(.status.containerStatuses[].lastState.terminated.reason=="OOMKilled") | {pod: .metadata.name, exit_code: .status.containerStatuses[].lastState.terminated.exitCode}'

# 2. Memeriksa CFS Throttling pada Node via cgroup v2
# Masuk ke node via debug pod atau SSH
kubectl debug node/ip-10-0-12-45.ap-southeast-1.compute.internal -it --image=busybox
# Cek statistik throttling kontainer
cat /sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice/.../cpu.stat
# Perhatikan parameter: 'nr_throttled' dan 'throttled_usec'

# 3. Menganalisis Log Eviksi Node
kubectl describe node ip-10-0-12-45.ap-southeast-1.compute.internal | grep -A 5 "Conditions:"
```

---

### 11. Best Practices (Production Checklist)

- [ ] **QoS Guaranteed untuk Core Engine**: Pastikan aplikasi latency-sensitive (misalnya database internal, payment broker) menggunakan `requests == limits`.
- [ ] **PodDisruptionBudget Valid**: Setiap deployment produksi wajib memiliki PDB dengan `minAvailable` atau `maxUnavailable` yang terukur (maksimal `maxUnavailable: 25%`).
- [ ] **PreStop Hook dengan Graceful Drain**: Gunakan `preStop: exec: command: ["sleep", "15"]` guna memberi window waktu propagasi IP Pod dicabut dari seluruh Ingress/Load Balancer.
- [ ] **Topology Spread Terkonfigurasi**: Sebarkan replika minimal di 3 Availability Zone menggunakan `topology.kubernetes.io/zone`.
- [ ] **Liveness Probe Tidak Boleh Bergantung pada Downstream**: Liveness probe hanya boleh mengecek status internal server (memory leak/deadlock), bukan konektivitas DB atau downstream cache.
- [ ] **Explicit PriorityClass**: Pisahkan prioritas workload antara sistem platform (`system-cluster-critical`), core processing, dan asynchronous background workers.

---

### 12. Hands-on Practice

Simpan seluruh file berikut ke dalam direktori: `hands-on/m02/`

#### Langkah 1: Persiapan Environment
Pastikan Anda memiliki akses ke klaster Kubernetes lokal (Minikube / KinD / K3s) dengan minimal 3 worker nodes.

#### Langkah 2: Deploy Workload Uji CFS Throttling & OOM
Buat file `hands-on/m02/01-resilience-demo.yaml`:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: sre-advanced-lab
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: stress-workload
  namespace: sre-advanced-lab
spec:
  replicas: 3
  selector:
    matchLabels:
      app: stress-workload
  template:
    metadata:
      labels:
        app: stress-workload
    spec:
      containers:
        - name: stress-app
          image: vish/stress
          args: ["-cpus", "2", "-mem-total", "250M", "-mem-alloc-size", "10M", "-mem-alloc-freq", "100ms"]
          resources:
            requests:
              cpu: "200m"
              memory: "100Mi"
            limits:
              cpu: "500m"
              memory: "200Mi" # Akan dipaksa OOMKilled karena alokasi 250M
```

#### Langkah 3: Eksekusi dan Amati Kegagalan
```bash
# Buat resource
kubectl apply -f hands-on/m02/01-resilience-demo.yaml

# Monitor lifecycle pod
kubectl get pods -n sre-advanced-lab -w

# Investigasi OOM Kill
kubectl describe pod -l app=stress-workload -n sre-advanced-lab | grep -E "Terminated|OOMKilled|Exit Code"
```

#### Langkah 4: Terapkan Topology Spread Constraints
Buat file `hands-on/m02/02-spread-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: zone-aware-service
  namespace: sre-advanced-lab
spec:
  replicas: 6
  selector:
    matchLabels:
      app: zone-aware
  template:
    metadata:
      labels:
        app: zone-aware
    spec:
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: zone-aware
      containers:
        - name: nginx
          image: nginx:alpine
          resources:
            requests:
              cpu: "50m"
              memory: "64Mi"
            limits:
              cpu: "50m"
              memory: "64Mi"
```

Eksekusi:
```bash
kubectl apply -f hands-on/m02/02-spread-deployment.yaml
# Periksa persebaran node
kubectl get pods -n sre-advanced-lab -l app=zone-aware -o wide
```

---

### 13. Exercise

#### Level: Easy
- Ubah deployment `zone-aware-service` di atas agar masuk ke dalam kelas QoS **BestEffort**.
- Verifikasi kelas QoS pod yang terbentuk menggunakan perintah `kubectl get pod <pod_name> -n sre-advanced-lab -o jsonpath='{.status.qosClass}'`.

#### Level: Medium
- Buat manifest PodDisruptionBudget bernama `zone-aware-pdb` yang menjamin minimal 4 dari 6 pod tetap berstatus `Running` ketika node dilakukan *drain* secara berurutan.
- Simulasikan pemeliharaan node dengan menjalankan perintah `kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data` dan amati perilaku penolakan drain jika melanggar PDB.

#### Level: Hard
- Rancang konfigurasi Custom HPA menggunakan metrik CPU Throttling (`container_cpu_cfs_throttled_periods_total / container_cpu_cfs_periods_total`).
- Pasangkan manifest tersebut dengan Pod Affinity yang mengharuskan Pod API berada pada Node yang sama dengan In-Memory Cache (Redis Local Pod), tetapi melarang dua Pod API yang sama berada pada satu Node (Anti-Affinity).

---

### 14. Challenge (Tantangan Studi Kasus Arsitektural)

**Konteks**: Anda adalah Principal Platform SRE di bank digital tier-1. Sistem checkout pembayaran akan menghadapi lonjakan beban 15x lipat saat kampanye Flash Sale kuartalan. Infrastruktur berjalan di atas 3 Availability Zone pada AWS EKS.

**Kondisi Batasan & Masalah**:
1. Cluster mengalami skenario *Thundering Herd*: 500 kontainer baru di-spin up secara serentak oleh Karpenter/HPA dalam waktu < 90 detik.
2. Saat deployment terjadi, traffic downstream menuju database SQL mengalami saturasi connection pool jika pod baru langsung dihantam traffic sebelum memori JVM terkompilasi (JIT Warm-up).
3. Jika salah satu AZ mengalami *hard failure* (blackout total), platform tidak boleh mentoleransi kegagalan transaksi lebih dari 0.001% (error rate).

**Tugas Arsitektur Anda**:
- Rancang arsitektur deployment lengkap yang mengombinasikan:
  - Multi-tier autoscaling readiness (KEDA/HPA + Cluster Autoscaling).
  - Skema Startup/Readiness Probes bertahap untuk JVM JIT Warmup.
  - Pod Topology Spread & Descheduler rules agar klaster terhindar dari ketimpangan resource (*resource fragmentation*).
  - PDB, Overprovisioning Buffer Pods via negative priority classes, dan graceful termination timeouts.

*(Tuliskan arsitektur dan spesifikasi manifest deklaratif untuk menyelesaikan skenario tersebut).*

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa yang membedakan QoS kelas **Guaranteed** dan **Burstable** dalam penentuan alokasi resource kontainer?
2. Apa arti dari nilai exit code `137` pada kontainer yang mendadak mati (*Terminated*)?
3. Sinyal sistem operasi apa yang pertama kali dikirimkan Kubelet kepada kontainer saat Pod dihapus?
4. Apa fungsi utama dari objek `PodDisruptionBudget` (PDB)?
5. Pada direktori virtual `/sys/fs/cgroup/`, file manakah yang mencatat metrik frekuensi pemotongan eksekusi CPU akibat melebihi kuota CFS?

#### B. Pertanyaan Intermediate
1. Mengapa menyetel `limits.cpu` tanpa kalkulasi yang benar dapat menyebabkan latensi aplikasi melonjak drastis, meskipun metrik CPU utilization node masih berada di bawah 40%?
2. Bagaimana scheduler mengevaluasi parameter `maxSkew: 1` pada konfigurasi `topologySpreadConstraints`?
3. Jelaskan mengapa penambahan `lifecycle.preStop.exec` dengan perintah sleep singkat (misalnya 15 detik) dapat mencegah terjadinya *HTTP 502 Bad Gateway* selama proses Rolling Deployment!
4. Apa yang terjadi jika sebuah pod berstatus QoS `Guaranteed` dan pod berstatus QoS `BestEffort` berada pada satu worker node yang sama, lalu node tersebut mengalami kondisi *Kernel Memory Hard Pressure*?
5. Mengapa liveness probe berbasis dependensi eksternal (misal: query database atau ping redis) dikategorikan sebagai anti-pattern fatal dalam arsitektur Kubernetes?

#### C. Skenario Kasus Produksi
1. **Skenario 1**: Sebuah microservice Node.js yang menangani enkripsi token mengalami crash beruntun (*CrashLoopBackOff*). Monitoring menunjukkan CPU usage rata-rata 85%, namun exit code adalah 137, dan tidak ada jejak exception di stdout. Langkah diagnosis apa yang Anda ambil untuk membuktikan bahwa memory leak menjadi pemicu terminasi ini?
2. **Skenario 2**: Anda menjalankan perintah `kubectl drain node-worker-01` untuk upgrade kernel. Proses drain macet (*stuck*) tanpa batas waktu. Berdasarkan arsitektur Kubernetes, komponen dan konfigurasi apa saja yang berpotensi menahan proses drain tersebut?
3. **Skenario 3**: Tim developer melaporkan bahwa pod mereka sering dipindahkan (evicted) oleh scheduler, padahal resource request mereka sangat kecil. Setelah dicegah oleh admin menggunakan LimitRange, pod baru justru menolak untuk jalan (*Pending*). Bagaimana Anda mendiagnosis korelasi antara alokasi LimitRange, Quota, dan Node Resource Fragmentation?

---

### Jawaban Kuis Evaluasi

#### Jawaban Basic:
1. **Perbedaan QoS**: *Guaranteed* mewajibkan semua kontainer mendefinisikan CPU & Memory dengan nilai `requests == limits`. *Burstable* terjadi jika minimal satu kontainer memiliki `requests` yang nilainya lebih rendah dari `limits`.
2. **Exit Code 137**: Menandakan proses dimatikan paksa oleh sinyal fatal Linux kernel `SIGKILL` (Sinyal 9). $128 + 9 = 137$. Ini umumnya disebabkan oleh OOM (Out Of Memory) Killer atau eviksi Kubelet.
3. **Sinyal Awal Lifecycle**: Sinyal `SIGTERM` (Sinyal 15), memberi kesempatan proses aplikasi menutup koneksi, mengosongkan buffer, dan shutdown secara graceful.
4. **Fungsi PDB**: Membatasi jumlah pod replika yang boleh mati secara simultan selama operasi pemeliharaan terencana (*voluntary disruptions*), seperti drain node atau cluster upgrade.
5. **File CFS Throttling**: `/sys/fs/cgroup/cpu.stat` (cgroup v2) atau `/sys/fs/cgroup/cpu/cpu.stat` (cgroup v1), khususnya metrik `nr_throttled`.

#### Jawaban Intermediate:
1. **CPU Throttling**: CFS bekerja berdasarkan window interval (default: 100ms). Jika limit disetel terlalu ketat, kontainer yang menghabiskan jatah waktu 100ms dalam 10ms pertama akan dibekukan (dithrottle) selama 90ms berikutnya oleh scheduler kernel Linux, memicu latensi tinggi pada respons P99.
2. **Evaluasi maxSkew**: Menentukan toleransi perbedaan mutlak jumlah pod yang cocok dengan label selector antara dua domain topologi (misal antar-AZ). `maxSkew: 1` memastikan selisih jumlah pod antar-zona tidak pernah lebih dari 1 replika.
3. **Mencegah HTTP 502 via PreStop**: Pembaruan IP di iptables/IPVS/eBPF node Ingress butuh waktu beberapa detik setelah pod berstatus `Terminating`. Hook `preStop: sleep 15` menahan pod agar tetap hidup dan melayani koneksi yang sudah terlanjur dialihkan ke pod tersebut selama tabel routing ingress diperbarui.
4. **Dampak Memory Pressure**: Node akan memicu eviksi pod berdasarkan `oom_score_adj`. Pod QoS *BestEffort* (`oom_score_adj: 1000`) akan langsung dieviksi/dibunuh terlebih dahulu. Pod QoS *Guaranteed* (`oom_score_adj: -997`) diproteksi dan merupakan beban kerja terakhir yang disentuh kernel.
5. **Bahaya Liveness Eksternal**: Jika downstream database mengalami down atau overload sementara, semua pod upstream yang mengecek DB via liveness probe akan dianggap unhealthy oleh Kubelet. Kubelet akan me-restart seluruh pod secara serentak, mengubah insiden parsial menjadi *cascading outage* total di seluruh tier aplikasi.

#### Jawaban Skenario Kasus Produksi:
1. **Diagnosis Skenario 1**: Exit code 137 membuktikan pod dimatikan oleh OOM Killer. Eksekusi `kubectl describe pod <name>` untuk memvalidasi status `OOMKilled: true`. Karena CPU 85%, memory leak di V8 engine (heap memory) menyebabkan RSS menyentuh batas `limits.memory`, memicu kernel Linux menembak proses node tanpa sempat menangani uncaught exception. Solusinya: dump memory heap profile, evaluasi batas memory limit, dan naikkan target batas atas.
2. **Diagnosis Skenario 2**: Drain macet biasanya disebabkan oleh:
   - PodDisruptionBudget (PDB) yang terlalu ketat (misal: `minAvailable: 100%` atau replika tersisa sudah menyentuh batas minimum PDB).
   - Adanya Pod dengan konfigurasi `terminationGracePeriodSeconds` yang sangat panjang dan aplikasi stuck tidak mau merespon SIGTERM.
   - Pod yang mengakses Persistent Volume lokal tanpa izin override.
3. **Diagnosis Skenario 3**: LimitRange sering menetapkan nilai `defaultRequest` atau `defaultLimit` yang tidak disadari developer. Jika cluster mengalami *Node Resource Fragmentation* (banyak node memiliki sisa CPU/RAM kecil yang tersebar tapi tak ada satupun node yang memiliki kapasitas utuh untuk menampung pod baru), pod akan tertahan di status `Pending`. Scheduler filtering predicate `NodeResourcesFit` gagal menemukan node yang muat.

---

### 16. Summary
- Stabilitas arsitektur Kubernetes di tingkat enterprise sangat ditentukan oleh pemahaman mendalam atas interaksi Kubelet, Container Runtime, dan Linux cgroup v2.
- Mengandalkan konfigurasi default Kubernetes adalah risiko terbesar pada sistem berskala masif. Penggunaan kelas QoS (*Guaranteed* vs *Burstable*), isolasi CFS throttling, dan kontrol distribusi multi-AZ (*TopologySpreadConstraints*) mutlak diimplementasikan secara eksplisit.
- Rolling update zero-downtime bukan sekadar menaikkan versi image; ia membutuhkan harmonisasi antara *Termination Lifecycle* (`preStop hook`, grace period), konfigurasi abstraksi jaringan (*readiness probes*, kube-proxy propagation window), dan ketersediaan minimum via *PodDisruptionBudget*.