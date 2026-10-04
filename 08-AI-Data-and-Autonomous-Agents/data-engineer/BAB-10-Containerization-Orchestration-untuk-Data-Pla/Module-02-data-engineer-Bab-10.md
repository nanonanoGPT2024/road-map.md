# Kurikulum Enterprise Data Engineering
## Kategori: 08-AI-Data-and-Autonomous-Agents
### BAB 10: Containerization & Orchestration untuk Data Platform
#### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Data Platform Engineer mampu:
1. **Merancang dan Mengonfigurasi Kubernetes Custom Schedulers** (seperti Volcano atau Apache YuniKorn) untuk beban kerja analitik terdistribusi skala besar guna mengeliminasi kondisi *scheduling deadlock* melalui mekanisme *Gang Scheduling*.
2. **Mengimplementasikan Operator Pattern Produksi** (khususnya Apache Spark on K8s Operator) dengan konfigurasi *Dynamic Resource Allocation*, *Remote Shuffle Service* (RSS), dan isolasi *multi-tenancy*.
3. **Mengoptimalkan Kinerja I/O dan Memori Container** pada level Linux kernel (*cgroups v2*, NUMA *pinning*, *ephemeral local NVMe*, dan JVM *off-heap headroom management*) untuk mencegah terminasi paksa akibat *OOMKilled* (Exit Code 137).
4. **Menerapkan Arsitektur Compute Elastis Berbasis Spot Instances** menggunakan toleransi kegagalan tingkat lanjut, *graceful decommissioning*, dan integrasi Karpenter/Cluster Autoscaler untuk menghemat biaya operasional klaster data hingga 70%.
5. **Mengintegrasikan Observabilitas Mendalam Tingkat Kernel** (eBPF, Prometheus Operator, Vector) guna memantau *network throughput*, *disk spill*, dan latensi shuffle secara *real-time*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
* **Linux Kernel Primitives:** Memahami namespaces (`net`, `mnt`, `pid`, `ipc`), `cgroups` (v1 vs v2), *page cache*, *swappiness*, serta mekanisme kerja Linux OOM Killer.
* **Dasar Kubernetes:** Mahir mengoperasikan Pods, Deployments, DaemonSets, StatefulSets, PVC/PV, StorageClass, serta arsitektur dasar Control Plane (`kube-apiserver`, `etcd`, `kube-scheduler`, `kubelet`).
* **Komputasi Data Terdistribusi:** Memahami arsitektur *Master-Worker* (Driver-Executor) pada Apache Spark atau Flink, siklus hidup *shuffle*, *partitioning*, dan alokasi memori JVM (*heap* vs *off-heap*).
* **Networking & Security:** Memahami *Container Network Interface* (CNI), overlay network overhead (misal: Calico, Cilium), Kubernetes RBAC, ServiceAccount, dan konsep IAM Roles for Service Accounts (IRSA/Workload Identity).

---

### 3. Concept & Internal Architecture (Mendalam)

#### Kube-Scheduler Default vs. Advanced Batch Schedulers (Volcano & YuniKorn)
Secara *default*, `kube-scheduler` dirancang untuk beban kerja *microservices* berbasis kriteria *pod-by-pod scheduling*. Model ini memiliki kelemahan struktural ketika diterapkan pada pemrosesan data terdistribusi:

1. **Deadlock / Resource Starvation:** Jika dua pekerjaan Spark berskala besar dikirimkan bersamaan dan klaster kekurangan kapasitas, `kube-scheduler` dapat menjadwalkan 50% *pod* dari Pekerjaan A dan 50% *pod* dari Pekerjaan B. Kedua pekerjaan tidak memiliki sumber daya yang cukup untuk memulai proses komputasi (*min-member requirements* tidak terpenuhi), sehingga keduanya terkunci (*deadlock*).
2. **Ketiadaan Gang Scheduling:** Pekerjaan data membutuhkan seluruh topologi komputasi (1 Driver + N Executor) untuk aktif secara sinkron atau tidak sama sekali (*all-or-nothing*).

```
Default Kube-Scheduler (Deadlock Risk):
Job 1 Pods: [P1] [P2] (Pending: P3, P4)  --> Cluster Full!
Job 2 Pods: [P1] [P2] (Pending: P3, P4)  --> Cluster Full!
Hasil: Keduanya stuck, tidak ada job yang bisa progress.

Batch Gang Scheduling (Volcano/YuniKorn):
Queue evaluates Job 1 (MinMember: 4) -> Insufficient Capacity -> Enqueue
Queue evaluates Job 2 (MinMember: 4) -> Insufficient Capacity -> Enqueue
Capacity freed up -> Job 1 (P1, P2, P3, P4) allocated atomic-ally!
```

#### Operator Pattern & Control Loop Lifecycle
Operator mengekstensi Kubernetes API menggunakan *Custom Resource Definitions* (CRD). Operator mengeksekusi *control loop* (Reconciliation Phase) tanpa henti:

$$\text{Reconcile}(Context, Request) \implies \text{Observe State} \to \text{Analyze Diff} \to \text{Actuate Reality to Desired State}$$

Pada pemrosesan data:
* **Spark Operator:** Memantau `SparkApplication`. Ketika CRD diterapkan, ia memvalidasi konfigurasi, membuat Spark Driver Pod, memantau *event stream* dari API Server, mengotomatisasi injeksi ConfigMap, melacak alokasi Executor secara dinamis, dan menangani pembersihan (*clean-up*) saat eksekusi selesai.

#### Dynamic Resource Allocation (DRA) & Remote Shuffle Service (RSS)
Pada arsitektur tradisional, *dynamic allocation* pada Spark membutuhkan *NodeManager* (YARN) atau *External Shuffle Service* (ESS) yang berjalan sebagai DaemonSet. Namun, implementasi ESS sebagai DaemonSet di Kubernetes memiliki kelemahan: *upgrade* DaemonSet akan menghapus *shuffle data* yang disimpan secara lokal, menyebabkan kegagalan bertingkat (*cascading failure*).

Solusi arsitektur modern adalah mengadopsi **Remote Shuffle Service (RSS)** (misalnya: Apache Celeborn atau Apache Uniffle):
* Executor mengirimkan partisi *shuffle* langsung ke klaster RSS terpisah melalui jaringan berkecepatan tinggi.
* Node komputasi (Spot Instances) menjadi sepenuhnya *stateless*. Jika sebuah node komputasi dihentikan (*preempted*), data *shuffle* tetap aman di RSS, meniadakan perlunya kalkulasi ulang (*recomputation*) tahapan RDD/DataFrame sebelumnya.

```
+-----------------------------------------------------------------------+
|                            KUBERNETES NODE                            |
|                                                                       |
|  +--------------------+        eBPF / CNI Data Path                   |
|  | Spark Executor Pod | -----------------------------------+          |
|  |  +--------------+  |                                    |          |
|  |  | JVM Heap     |  |                                    v          |
|  |  +--------------+  |                            +---------------+  |
|  |  | Off-Heap Mem |  |                            | Local NVMe    |  |
|  |  +--------------+  |                            | Scratch Disk  |  |
|  +---------+----------+                            | (Spill only)  |  |
|            |                                       +---------------+  |
|            | TCP Stream (Shuffle Write)                               |
+------------|----------------------------------------------------------+
             |
             v
+-----------------------------+       +-----------------------------+
| Remote Shuffle Service (RSS)| ----> | Object Storage (S3/GCS)     |
| (Apache Celeborn Cluster)   |       | Parquet / Delta / Iceberg   |
+-----------------------------+       +-----------------------------+
```

#### Kernel & Cgroups v2 Memory Management
Pada *cgroups v2*, tata kelola memori diperketat melalui kontrol `memory.min`, `memory.low`, `memory.high`, dan `memory.max`. 
Untuk beban kerja JVM di Kubernetes:
$$\text{Total Pod Memory Limit} = \text{Spark Heap} + \text{Off-Heap} + \text{PySpark Overhead} + \text{OS Buffer Overhead}$$
Jika `JVM Max RAM Fraction` diatur tanpa memperhitungkan *off-heap memory* (digunakan oleh *memory-mapped files*, PyArrow, JNI C-libraries, atau thread stacks), penggunaan memori akan menyentuh `memory.max`, memicu Linux Kernel OOM Killer mengirimkan sinyal `SIGKILL` (Exit Code 137).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (YARN / VM Statis) | Pendekatan Cloud-Native Modern (K8s Data Platform) |
| :--- | :--- | :--- |
| **Penyediaan Sumber Daya** | Klaster statis berskala tetap (*fixed-size cluster*). Skala naik/turun lambat (5-15 menit). | *Just-In-Time Autoscaling* via Karpenter/KEDA (penambahan kapasitas dalam < 60 detik). |
| **Isolasi Multi-Tenancy** | Tingkat antrean (*Queue-level* via YARN Capacity Scheduler). Risiko kebocoran dependensi Python/Jar. | Isolasi penuh tingkat *kernel namespace*, *network policies*, dan *container images* independen per pipeline. |
| **Biaya Infrastruktur** | Bergantung pada *On-Demand* atau *Reserved Instances* karena *failover* node yang lambat. | Pemanfaatan *Spot/Preemptible Instances* hingga 80% dengan kombinasi RSS dan *Gang Scheduling*. |
| **Manajemen Dependensi** | Harus menginstal paket sistem/Python di seluruh *worker nodes* (ancaman *dependency hell*). | Dependensi dienkapsulasi rapat di dalam OCI-compliant Container Image (`Containerfile`). |

---

### 5. How (Workflow Detail)

Alur kerja eksekusi beban kerja komputasi analitik terdistribusi di Kubernetes:

```
[Data Engineer]
       │  (1) kubectl apply -f spark-app.yaml
       ▼
[Kube-API Server]
       │  (2) Persist to etcd & Trigger Watcher
       ▼
[Spark Operator Controller]
       │  (3) Generate Driver Pod Manifest + PodGroup CRD
       ▼
[Advanced Scheduler (Volcano/YuniKorn)]
       │  (4) Evaluasi Min-Member & Queue Quotas
       │      Gang Scheduling check: Kapasitas klaster >= Min-Member?
       ├───────────────────────────────┬───────────────────────────────┐
      [No]                            [Yes]                            │
       │ Enqueue / Panggil Autoscaler  │ Alokasikan Driver & Executors │
       │ (Karpenter provision nodes)   │ secara atomik                 │
       ▼                               ▼                               ▼
[Driver Pod Initiated] ────────> [CSI Driver Mounts] ─────────> [Executors Spawned]
       │                          Local NVMe via Direct          │
       │                          Path / Fast Storage            │
       │                                                         │
       ├─────────────────────────────────────────────────────────┘
       │  (5) Task Processing & Remote Shuffle Streaming
       ▼
[Apache Celeborn / RSS Node Pool]
       │  (6) Spill data shuffle dipusatkan ke remote layer
       ▼
[Write Final Datasets]
       │  (7) Tulis hasil komputasi ke Object Storage (S3/Iceberg)
       ▼
[Driver Termination]
       │  (8) Operator mendeteksi status 'Completed', membersihkan Executors,
       ▼      mengubah status CRD menjadi Succeeded.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan **Default Kube-Scheduler** seperti *restoran cepat saji individual*: Jika sebuah tim berjumlah 10 orang datang, pelayan akan mendudukkan anggota tim satu per satu di kursi mana pun yang kosong. Jika restoran penuh setelah 4 orang duduk, 4 orang tersebut hanya duduk diam menunggu 6 sisanya masuk, memblokir meja untuk pelanggan lain tanpa bisa mulai makan.

Sebaliknya, **Batch Scheduler (Volcano/YuniKorn)** bekerja seperti *reservasi ruang VIP perjamuan resmi*: Restoran memastikan seluruh 10 kursi tersedia sekaligus sebelum mempersilakan tim masuk (*Gang Scheduling*). Jika kapasitas belum cukup, tim menunggu di lobi tanpa memakan kapasitas meja. Saat meja siap, seluruh anggota tim masuk serentak, menyelesaikan hidangan bersama-sama, lalu mengosongkan seluruh ruangan seketika.

#### Diagram Arsitektur Terperinci

```
+-----------------------------------------------------------------------------------+
|                           KUBERNETES CONTROL PLANE                                |
|                                                                                   |
|   +-----------------------+     +-----------------------+     +---------------+   |
|   | Kube-APIServer        |<--->| Custom Resource Defs  |<--->| etcd Database |   |
|   |                       |     | (SparkApp, PodGroup)  |     |               |   |
|   +-----------------------+     +-----------------------+     +---------------+   |
|               ^                             ^                                     |
+---------------|-----------------------------|-------------------------------------+
                v                             v
+-------------------------------+ +-------------------------------------------------+
| SPARK OPERATOR (Controller)   | | ADVANCED SCHEDULER (Volcano Engine)             |
| - Watches SparkApplications   | | - PodGroup Queue Evaluation                     |
| - Creates Driver/Exec Specs   | | - DRF (Dominant Resource Fairness) Engine       |
| - Orchestrates Lifecycle      | | - Gang Scheduling: All-or-Nothing Resolution    |
+-------------------------------+ +-------------------------------------------------+
                │                                     │
                └──────────────────┬──────────────────┘
                                   │ Schedules Pods
                                   v
+-----------------------------------------------------------------------------------+
| WORKER NODE POOL: ON-DEMAND (Driver Pool)                                         |
| +-------------------------------------------------------------------------------+ |
| | Spark Driver Pod: my-etl-job-driver                                           | |
| | - Resources: Requests = Limits (Guaranteed QoS)                               | |
| | - Network: AWS VPC-CNI with Direct Pod IP                                     | |
| | - Role: Menjadwalkan Tasks, Koordinasi Stage, Handshake dengan API Server     | |
| +-------------------------------------------------------------------------------+ |
+-----------------------------------------------------------------------------------+
                                   │ Triggers Worker Nodes
                                   v
+-----------------------------------------------------------------------------------+
| WORKER NODE POOL: SPOT INSTANCES (Executor Pool via Karpenter)                    |
|                                                                                   |
| +-------------------------------+       +-------------------------------+         |
| | Node: spot-node-1             |       | Node: spot-node-2             |         |
| |                               |       |                               |         |
| | +---------------------------+ |       | +---------------------------+ |         |
| | | Spark Executor Pod 1      | |       | | Spark Executor Pod 2      | |         |
| | | - Local NVMe Scratch Mount| |       | | - Local NVMe Scratch Mount| |         |
| | | - Graceful Shutdown Hook  | |       | | - Graceful Shutdown Hook  | |         |
| | +---------------------------+ |       | +---------------------------+ |         |
| +-------------------------------+       +-------------------------------+         |
+-----------------------------------------------------------------------------------+
                                   │ Flush Shuffle Blocks
                                   v
+-----------------------------------------------------------------------------------+
| STORAGE & TELEMETRY SUBSYSTEMS                                                    |
|                                                                                   |
| +-------------------------------+       +---------------------------------------+ |
| | Remote Shuffle Cluster        |       | Observability DaemonSet (Vector/eBPF) | |
| | (Apache Celeborn on SSDs)     |       | - Tracks Kernel Drop Packets          | |
| | - Zero shuffle lost on spot   |       | - Scrapes Driver & Executor JMX       | |
| |   node preemption             |       | - Reports memory.current vs limits    | |
| +-------------------------------+       +---------------------------------------+ |
+-----------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengonfigurasi Pod Komputasi Analitik dengan Proteksi Kernel
Manifest pod berikut mengonfigurasi alokasi *cgroups v2*, *memory overhead*, dan *ephemeral scratch disk* lokal:

```yaml
# analytic-worker-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: analytic-worker-primitive
  namespace: data-workloads
  labels:
    tier: compute
spec:
  restartPolicy: Never
  containers:
    - name: data-processor
      image: apache/spark:3.5.0-python3
      command: ["/opt/spark/bin/spark-class"]
      args: ["org.apache.spark.deploy.SparkSubmit", "--master", "local[4]", "/opt/spark/examples/src/main/python/pi.py"]
      resources:
        requests:
          cpu: "4000m"
          memory: "8Gi"
          ephemeral-storage: "20Gi"
        limits:
          cpu: "4000m"
          memory: "8Gi"          # Requests == Limits -> Menghasilkan Guaranteed QoS Class
          ephemeral-storage: "20Gi"
      env:
        - name: MALLOC_ARENA_MAX
          value: "2"             # Mengurangi fragmentasi memori glibc off-heap
        - name: SPARK_JAVA_OPTS
          value: "-XX:+UnlockDiagnosticVMOptions -XX:+UseG1GC -XX:InitiatingHeapOccupancyPercent=45 -XX:G1ReservePercent=15"
      volumeMounts:
        - name: scratch-space
          mountPath: /tmp/scratch
  volumes:
    - name: scratch-space
      emptyDir:
        medium: ""               # Dipetakan ke disk lokal berkecepatan tinggi
        sizeLimit: 20Gi
```

#### Practical Example: Production Enterprise SparkApplication dengan PodGroup Gang Scheduling (Volcano) & Dynamic Allocation

```yaml
# production-spark-application.yaml
apiVersion: "sparkoperator.k8s.io/v1beta2"
kind: SparkApplication
metadata:
  name: telemetry-lakehouse-ingest
  namespace: data-platform-prod
spec:
  type: Python
  pythonVersion: "3"
  mode: cluster
  image: "registry.enterprise.io/data-engineers/spark-py-runtime:3.5.0-v4.2"
  imagePullPolicy: IfNotPresent
  mainApplicationFile: "local:///app/telemetry_aggregation.py"
  sparkVersion: "3.5.0"
  restartPolicy:
    type: OnFailure
    onFailureRetries: 3
    onFailureRetryInterval: 15
    onSubmissionFailureRetries: 5
    onSubmissionFailureRetryInterval: 20
  batchScheduler: "volcano"
  batchSchedulerOptions:
    queue: "production-high-priority"
    priorityClassName: "prod-mission-critical"
  
  sparkConf:
    # Optimasi Dynamic Resource Allocation & Shuffle
    "spark.dynamicAllocation.enabled": "true"
    "spark.dynamicAllocation.minExecutors": "5"
    "spark.dynamicAllocation.maxExecutors": "100"
    "spark.dynamicAllocation.initialExecutors": "10"
    "spark.dynamicAllocation.executorIdleTimeout": "60s"
    "spark.shuffle.service.enabled": "false" # Nonaktifkan legacy ESS
    
    # Remote Shuffle Service Integration (Apache Celeborn)
    "spark.shuffle.manager": "org.apache.spark.shuffle.celeborn.SparkShuffleManager"
    "spark.celeborn.master.endpoints": "celeborn-master-0.celeborn.storage.svc:9097,celeborn-master-1.celeborn.storage.svc:9097"
    "spark.celeborn.client.push.replicate.enabled": "true"
    "spark.serializer": "org.apache.spark.serializer.KryoSerializer"
    "spark.sql.adaptive.enabled": "true"
    "spark.sql.adaptive.coalescePartitions.enabled": "true"

  # Driver Configuration (On-Demand Instances)
  driver:
    cores: 2
    coreRequest: "1800m"
    coreLimit: "2000m"
    memory: "4096m"
    memoryOverhead: "1024m" # Off-heap & Python overhead (20%)
    labels:
      version: 3.5.0
      role: spark-driver
    serviceAccount: spark-operator-controller-sa
    nodeSelector:
      node.kubernetes.io/capacity-type: "on-demand"
      workload.enterprise.io/tier: "orchestration"
    tolerations:
      - key: "workload/orchestration"
        operator: "Exists"
        effect: "NoSchedule"

  # Executor Configuration (Spot Instances dengan graceful handling)
  executor:
    cores: 4
    coreRequest: "3800m"
    coreLimit: "4000m"
    memory: "14336m"
    memoryOverhead: "2048m" # Mencegah Pod OOMKilled akibat PyArrow/Vectorized Parquet
    labels:
      version: 3.5.0
      role: spark-executor
    nodeSelector:
      node.kubernetes.io/capacity-type: "spot"
      workload.enterprise.io/tier: "compute-heavy"
    tolerations:
      - key: "workload/compute-heavy"
        operator: "Exists"
        effect: "NoSchedule"
    volumeMounts:
      - name: fast-nvme-scratch
        mountPath: /mnt/spark/scratch
  
  volumes:
    - name: fast-nvme-scratch
      emptyDir:
        medium: Memory # Opsi: Mount RAM disk / local hostpath NVMe
        sizeLimit: 4Gi
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Studi Kasus: Arsitektur Pemrosesan Data Transaksi Finansial Skala Petabyte
* **Organisasi:** Institusi Finansial Tier-1 (100+ Juta Transaksi Harian).
* **Skala Sistem:** 4.500 Core vCPU, 28 TB RAM terdistribusi dalam 450 worker nodes pada AWS EKS.

#### Permasalahan (Root Cause Analysis):
1. **Biaya Infrastruktur Eksorbitan:** Seluruh klaster berjalan pada On-Demand Instances tipe `r5d.4xlarge`. Upaya beralih ke Spot Instances menyebabkan kegagalan 42% pekerjaan harian karena *node termination* mendadak memutus proses kalkulasi *shuffle stage*, mengakibatkan *cascading task failure* dan *shuffle fetch timeout*.
2. **Cluster Deadlock:** Pada jam sibuk (02:00 Pagi - Waktu Batch Ledger), 30 pekerjaan Spark berebut resource secara simultan. *Default scheduler* membagi sumber daya secara merata namun tanggung, membuat semua pekerjaan kekurangan alokasi executor minimum (`min-executors`). Klaster mengalami utilisasi 100% tanpa ada satu pun job yang selesai (*deadlock*).
3. **OOM Killer (SIGKILL 137):** Alokasi JVM Heap 90% dari batas memori Pod memicu terminasi paksa oleh Kernel Linux saat pemrosesan *large-scale window functions* yang memuat data terdekompresi ke memori native C via PySpark.

#### Solusi Rekayasa Terpadu:
1. **Penerapan Gang Scheduling via Apache YuniKorn:**
   * Diterapkan *Hierarchical Resource Queues* dengan alokasi kuota berdasarkan unit bisnis (*Risk Engineering*, *Payment Ledger*, *Ad-hoc Analytics*).
   * Menetapkan batasan `minMember` pada alokasi Pod. Setiap pekerjaan Spark dijamin mendapatkan alokasi executor minimum sebelum proses inisiasi dijalankan.
2. **Pemisahan Layer Compute & Shuffle Storage (Decoupling):**
   * Mengimplementasikan **Apache Celeborn** sebagai Remote Shuffle Service di atas node pool terpisah berbasis On-Demand berkapasitas kecil yang terpasang NVMe.
   * Node Executor Spark dialihkan 100% ke **Spot Instances** menggunakan Karpenter. Ketika AWS mengirimkan sinyal terminasi Spot (pemberitahuan 2 menit), executor berhenti menerima task baru, namun *shuffle data* yang telah diproses tidak hilang karena tersimpan di Celeborn.
3. **Kernel Memory Headroom Restructuring:**
   * Merestrukturisasi alokasi memori container:
     $$\text{Container Limit}: 16\,\text{GiB} \implies \text{Heap}: 10\,\text{GiB} \; (62.5\%), \; \text{Off-Heap}: 4\,\text{GiB} \; (25\%), \; \text{cgroup buffer}: 2\,\text{GiB} \; (12.5\%)$$
   * Mengaktifkan konfigurasi `MALLOC_ARENA_MAX=2` untuk menstabilkan konsumsi *native memory*.

#### Hasil Metrik Produksi:
* **Penghematan Biaya:** Penurunan biaya komputasi sebesar **64.8%** per bulan.
* **Stabilitas Sistem:** Angka keberhasilan penyelesaian job (*Job Success Rate*) naik dari 88.2% ke **99.94%**.
* **Throughput Pipeline:** Durasi penyelesaian pemrosesan berkurang dari rata-rata 4.5 jam menjadi **2.8 jam** berkat hilangnya *recomputation penalty* pada stage shuffle.

---

### 9. Trade-offs (Analisis Kompromi Teknis)

```
                            PENDEKATAN INFRASTRUKTUR
                                       |
        +------------------------------+------------------------------+
        |                                                             |
        v                                                             v
[LOCAL NVMe SHUFFLE]                                      [REMOTE SHUFFLE SERVICE (RSS)]
  + Latensi baca/tulis shuffle minimal                      + Node komputasi stateless murni
  - Data shuffle hilang jika Spot diputus                   + Eksekusi pada Spot aman tanpa fail
  - Membutuhkan instance storage mahal                      - Menambah 1-3ms latensi jaringan
  - Resiko disk exhaustion mengganggu Kubelet               - Beban operasional maintenance RSS cluster
```

| Komponen Arsitektur | Opsi A | Opsi B | Analisis Kompromi (*Performance, Latency, Scalability, Cost*) |
| :--- | :--- | :--- | :--- |
| **Batch Scheduling Engine** | **Default Kube-Scheduler** | **Volcano / YuniKorn Scheduler** | *Default* menghemat resource kontrol plane (ringan), tetapi rentan *deadlock* pada konkurensi tinggi. Volcano membutuhkan CRD tambahan dan overhead memori kontrol plane, tetapi menyediakan *gang scheduling* dan *dynamic fair-share*. |
| **QoS Class Pod** | **Burstable QoS** (`requests < limits`) | **Guaranteed QoS** (`requests == limits`) | *Burstable* meningkatkan densitas pod per node (efisiensi biaya), tetapi rentan terkena terminasi Linux OOM Killer jika node mengalami tekanan memori. *Guaranteed* menjamin stabilitas pipeline misi kritis dengan biaya alokasi resource yang lebih kaku. |
| **Shuffle Topology** | **Local EBS / PV Dynamic** | **Remote Shuffle Service (Celeborn)** | EBS Storage IOPS terbatas dan biaya membengkak karena volume detachment/attachment yang lambat saat scaling. RSS mengonsumsi bandwidth internal VPC yang tinggi namun memberikan skalabilitas tak terbatas dan pemisahan komputasi-penyimpanan yang optimal. |
| **Jaringan Container (CNI)** | **Overlay Network (VXLAN/Geneve)** | **Host-Routing / Native VPC CNI** | *Overlay* mengabstraksi jaringan namun memberikan penalti CPU 10-15% dan peningkatan latensi *packet serialization*. *Native VPC CNI* mengeksploitasi performa perangkat keras secara penuh (*line-rate speed*), namun cepat menghabiskan kuota IP subnet VPC Anda. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum Produksi (Anti-Patterns)
1. **Mengabaikan Overhead Non-Heap Memory JVM:** Menetapkan JVM heap `-Xmx` sama dengan memory limit pod di Kubernetes. Hasilnya, saat driver/executor mengalokasikan memori native (*NIO Direct Buffer*, *garbage collection metadata*, thread stacks), penggunaan memori melampaui batas cgroup dan pod seketika di-terminate oleh kernel dengan status code `OOMKilled` (Exit Code 137).
2. **Ketiadaan Pod Disruption Budgets (PDB) untuk Driver Pod:** Mengizinkan Kubernetes Autoscaler mengevakuasi Node tempat Spark Driver berjalan saat proses *node consolidation*. Matinya Driver Pod menggugurkan seluruh eksekutor yang sedang bekerja, membuang komputasi yang telah berlangsung berjam-jam.
3. **I/O Starvation pada Direktori Kubelet Root:** Menulis data temporer/spill Spark ke direktori root container tanpa memisahkannya ke volume `emptyDir` independen. Jika disk root penuh, `kubelet` mengalami *NodePressure: DiskPressure* dan mulai mengevakuasi (*evict*) pod penting lainnya secara masif.

#### Panduan Troubleshooting Sistematis

```
                  POD OOMKILLED / EXIT CODE 137
                                │
             Apakah OOM disebabkan oleh Linux Kernel 
                    atau JVM Internal Limits?
                                │
       ┌────────────────────────┴────────────────────────┐
       ▼                                                 ▼
[Linux Kernel cgroup OOM]                       [JVM Internal OOM]
(dmesg | grep -i oom-killer)                    (java.lang.OutOfMemoryError: Java heap space)
       │                                                 │
       ├─► Analisis cgroup limit vs actual usage         ├─► Periksa alokasi data skew di Spark UI
       │   `kubectl describe pod <pod-name>`             │   (Task memproses 100x partisi normal)
       │   Cari: "Last State: Terminated, Reason:        │
       │          OOMKilled, Exit Code: 137"             ├─► Tingkatkan: spark.executor.memory
       │                                                 │
       └─► Solusi:                                       └─► Solusi:
           Naikkan: spark.executor.memoryOverhead            Gunakan adaptive query execution (AQE)
           Batas: Naikkan memory limits pod                  `spark.sql.adaptive.skewJoin.enabled=true`
```

#### Diagnostic Commands Checklist
```bash
# 1. Periksa apakah kernel cgroup yang memutus pod secara paksa
kubectl get pods -n data-platform-prod -o wide | grep Error
kubectl describe pod <executor-pod-name> -n data-platform-prod | grep -E "Exit Code|Reason|Limits"

# 2. Cek apakah terjadi resource contention pada tingkat kernel node
kubectl debug node/<node-name> -it --image=busybox
# Jalankan di dalam container debug:
chroot /host
dmesg -T | grep -E -i "oom_reaper|invoked oom-killer"

# 3. Verifikasi ketersediaan antrean pada Volcano Scheduler
kubectl describe queue production-high-priority -n volcano-system

# 4. Validasi latency konektivitas shuffle ke RSS Engine
kubectl exec -it <spark-driver-pod> -n data-platform-prod -- nc -zv celeborn-master.storage.svc 9097
```

---

### 11. Best Practices (Production Checklist)

#### Perencanaan Infrastruktur & Node Management
- [ ] Pisahkan Node Pool secara fisik atau logis: Node On-Demand dialokasikan khusus untuk Driver Pods dan RSS; Node Spot Instances dialokasikan khusus untuk Worker/Executor Pods.
- [ ] Implementasikan DaemonSet Node Termination Handler untuk menangkap sinyal *AWS/GCP Preemption Notice* dan memicu *Graceful Decommissioning* pada executor.
- [ ] Gunakan SSD NVMe lokal berkecepatan tinggi yang dipasang langsung (*Instance Store*) menggunakan RAID-0 untuk target direktori `spark.local.dir`.

#### Pengaturan Container Runtime & Resource Pod
- [ ] Terapkan konfigurasi **Guaranteed QoS** untuk Driver Pod (`resources.requests == resources.limits`) guna menghindari evakuasi saat klaster tertekan.
- [ ] Alokasikan rasio Memori Overhead minimum 20% dari total memori container untuk PySpark/JNI native buffer:
  ```
  spark.executor.memoryOverhead = max(384MB, 0.20 * spark.executor.memory)
  ```
- [ ] Pastikan limit `ephemeral-storage` didefinisikan secara eksplisit untuk mencegah kerusakan partisi root node OS.

#### Konfigurasi Scheduler & Multi-Tenancy
- [ ] Terapkan *Gang Scheduling* (Volcano / Apache YuniKorn) pada semua batch job terdistribusi. Nilai `minMember` wajib diatur minimal $\text{Total Expected Executors} \times 0.7 + 1\text{ (Driver)}$.
- [ ] Definisikan `NetworkPolicy` ketat yang mengisolasi namespace beban kerja analitik untuk mencegah eksfiltrasi data antar tenant.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun arsitektur komputasi analitik terdistribusi menggunakan Kubernetes RBAC, Volcano Scheduler Gang Queue, dan mengeksekusi Spark Application dengan isolasi sumber daya ketat.

Simpan seluruh file manifest berikut ke dalam direktori: `hands-on/m02/`

#### File 1: `hands-on/m02/01-rbac-setup.yaml`
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: data-platform-lab
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: spark-compute-sa
  namespace: data-platform-lab
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: data-platform-lab
  name: spark-compute-role
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps", "persistentvolumeclaims"]
  verbs: ["*"]
- apiGroups: ["apps"]
  resources: ["statefulsets", "deployments"]
  verbs: ["*"]
- apiGroups: ["batch", "scheduling.volcano.sh"]
  resources: ["podgroups"]
  verbs: ["*"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: spark-compute-rb
  namespace: data-platform-lab
subjects:
- kind: ServiceAccount
  name: spark-compute-sa
  namespace: data-platform-lab
roleRef:
  kind: Role
  name: spark-compute-role
  apiGroup: rbac.authorization.k8s.io
```

#### File 2: `hands-on/m02/02-volcano-queue.yaml`
```yaml
apiVersion: scheduling.volcano.sh/v1beta1
kind: Queue
metadata:
  name: batch-analytics-queue
spec:
  weight: 100
  capability:
    cpu: "16"
    memory: "64Gi"
  reclaimable: true
---
apiVersion: scheduling.volcano.sh/v1beta1
kind: PodGroup
metadata:
  name: spark-workload-pg
  namespace: data-platform-lab
spec:
  minMember: 3 # 1 Driver + 2 Executors (All-or-Nothing Gang Criteria)
  queue: batch-analytics-queue
  minResources:
    cpu: "3000m"
    memory: "6Gi"
```

#### File 3: `hands-on/m02/03-spark-distributed-job.yaml`
```yaml
apiVersion: "sparkoperator.k8s.io/v1beta2"
kind: SparkApplication
metadata:
  name: enterprise-pi-computation
  namespace: data-platform-lab
spec:
  type: Scala
  mode: cluster
  image: "gcr.io/spark-operator/spark:v3.5.0"
  imagePullPolicy: IfNotPresent
  mainClass: org.apache.spark.examples.SparkPi
  mainApplicationFile: "local:///opt/spark/examples/jars/spark-examples_2.12-3.5.0.jar"
  arguments: ["50000"]
  sparkVersion: "3.5.0"
  restartPolicy:
    type: Never
  batchScheduler: "volcano"
  batchSchedulerOptions:
    queue: "batch-analytics-queue"
    priorityClassName: "normal"
  driver:
    cores: 1
    coreRequest: "500m"
    coreLimit: "1000m"
    memory: "1024m"
    memoryOverhead: "512m"
    serviceAccount: spark-compute-sa
    labels:
      volcano.sh/podgroup-name: "spark-workload-pg"
  executor:
    cores: 1
    coreRequest: "1000m"
    coreLimit: "1000m"
    instances: 2
    memory: "2048m"
    memoryOverhead: "512m"
    labels:
      volcano.sh/podgroup-name: "spark-workload-pg"
```

#### Step-by-Step Execution Guide

Jalankan perintah berikut pada terminal Anda:

```bash
# Langkah 1: Buat Namespace dan Konfigurasi RBAC
kubectl apply -f hands-on/m02/01-rbac-setup.yaml

# Validasi pembuatan RBAC
kubectl get serviceaccount,role,rolebinding -n data-platform-lab

# Langkah 2: Daftarkan Antrean Penjadwalan Volcano (Queue) & PodGroup
kubectl apply -f hands-on/m02/02-volcano-queue.yaml

# Verifikasi status Volcano Queue
kubectl describe queue batch-analytics-queue

# Langkah 3: Deploy Beban Kerja Analisis Spark Terdistribusi
kubectl apply -f hands-on/m02/03-spark-distributed-job.yaml

# Langkah 4: Amati Siklus Gang Scheduling secara Real-time
# Amati bahwa Driver dan 2 Executor harus dibuat bersamaan (tidak boleh ada executor tunggal yang berjalan sendirian)
watch -n 1 "kubectl get pods -n data-platform-lab -o wide"

# Langkah 5: Inspeksi Log Driver untuk Memvalidasi Hasil Kalkulasi
kubectl logs -f enterprise-pi-computation-driver -n data-platform-lab

# Langkah 6: Validasi Status Eksekusi SparkApplication CRD
kubectl get sparkapplication enterprise-pi-computation -n data-platform-lab -o jsonpath='{.status.applicationState.state}'
```

---

### 13. Exercise

#### Tingkat: Easy
* **Tugas:** Ubah alokasi memori pada file `hands-on/m02/03-spark-distributed-job.yaml` untuk mengimplementasikan *Guaranteed Quality of Service (QoS)* pada Executor Pods.
* **Instruksi:** Pastikan konfigurasi `requests.cpu == limits.cpu` dan `requests.memory == limits.memory`.
* **Kriteria Keberhasilan:** Eksekusi `kubectl get pod <executor-pod-id> -n data-platform-lab -o jsonpath='{.status.qosClass}'` mengembalikan output: `Guaranteed`.

#### Tingkat: Medium
* **Tugas:** Simulasikan insiden kegagalan memori *cgroup OOMKilled* (Exit code 137) pada pod data processing.
* **Instruksi:** Buat file `hands-on/m02/memory-bomb-job.yaml`. Tulis script Python sederhana yang mengalokasikan array NumPy berukuran 2 GB ke dalam RAM, namun berikan limitasi Kubernetes Pod `resources.limits.memory: "512Mi"`. Terapkan ke klaster dan tangkap kejadian evakuasi pada sistem.
* **Kriteria Keberhasilan:** Gunakan perintah `kubectl describe` atau skrip ekstraksi JSONPath untuk mendeteksi event dengan alasan: `OOMKilled` dan status kode `137`. Berikan argumen mengapa *swapping* Linux kernel tidak mencegah hal tersebut di Kubernetes.

#### Tingkat: Hard
* **Tugas:** Konfigurasikan integrasi *Graceful Node Decommissioning* menggunakan pod life-cycle hooks untuk Spark Executor di Kubernetes.
* **Instruksi:** Tambahkan lifecycle hook `preStop` pada pod template spec executor yang menjalankan script shell `/opt/spark/sbin/decommission-executor.sh`. Uji konfigurasi ini dengan cara melakukan *drain* paksa pada salah satu worker node (`kubectl drain <node> --ignore-daemonsets --delete-emptydir-data`) di tengah-tengah kalkulasi beban kerja analitik berskala besar tanpa menggagalkan status Spark Application utama.
* **Kriteria Keberhasilan:** Seluruh state yang sedang dihitung pada node yang di-*drain* dialihkan secara dinamis ke executor yang tersisa tanpa terjadi *Stage Failure* pada Spark UI.

---

### 14. Challenge (Tantangan Desain Enterprise)

#### Latar Belakang Skenario:
Sebuah perusahaan Autonomous Vehicle mengumpulkan data telemetri LiDAR dan sensor radar dari 20.000 armada mobil. Sistem ingest memproduksi *data stream* dengan *throughput* **4 GB/detik (peak)** ke Apache Kafka.
Anda ditugaskan mendesain platform komputasi analitik terdistribusi menggunakan **Apache Flink on Kubernetes** yang mengeksekusi *stateful stream processing* dengan window tumbling 10 menit.

#### Persyaratan & Kendala Sistem:
1. **Zero Data Loss & Strict Low-Latency:** *End-to-End Latency* pemrosesan tidak boleh melampaui **800 milidetik**.
2. **State Management:** *State size* aplikasi mencapai **6 Terabyte** (menggunakan RocksDB State Backend).
3. **Fluktuasi Biaya Infrastruktur:** Manajemen mewajibkan 80% node Flink TaskManager berjalan pada **Spot Instances**.
4. **Resiliensi Zona:** Klaster Kubernetes terdistribusi di 3 Availability Zone (AZ). Biaya *cross-AZ network transfer* harus ditekan hingga level minimal.

#### Instruksi Pengerjaan (Arsitektur Desain Dokumen):
Rancang dokumen arsitektur komprehensif tanpa menggunakan template generik. Dokumen wajib membedah:
* Topologi deployment Flink (Application Mode vs Flink K8s Operator).
* Mekanisme alokasi *Stateful Volume* untuk RocksDB: Mengapa PV berbasis EBS GP3 akan gagal menangani I/O *compaction* pada skala ini, dan bagaimana arsitektur NVMe lokal + Asynchronous Incremental Checkpoint ke Ceph/S3 mengatasinya?
* Strategi penanganan *Spot Interruption* agar Flink tidak mengalami *Full Graph Restart* berulang kali (kaji pemanfaatan Flink Reactive Mode vs Adaptive Scheduler).
* Strategi *Topology Spread Constraints* dan affinity untuk mencegah *cross-AZ network egress billing spike* antar TaskManager pods.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Pertanyaan Dasar (Basic)
1. **Mengapa `kube-scheduler` bawaan Kubernetes kurang optimal untuk menjalankan framework pemrosesan batch terdistribusi seperti Apache Spark?**
   * *Jawaban:* Karena `kube-scheduler` menggunakan pendekatan *pod-by-pod scheduling*, bukan *gang scheduling*. Hal ini berisiko memicu *resource deadlock* ketika beberapa beban kerja terdistribusi bersaing memperebutkan alokasi sumber daya yang tidak mencukupi untuk memenuhi batas minimum pod aktif (*min-member*) secara simultan.
2. **Apa fungsi dari nilai `spark.executor.memoryOverhead` dalam konfigurasi Spark on Kubernetes?**
   * *Jawaban:* Mengalokasikan ruang memori non-heap (off-heap) di dalam container untuk mengakomodasi alokasi memori internal OS, overhead thread VM, PySpark/PyArrow native runtime buffers, serta metadata JVM, agar konsumsi memori total container tidak melampaui batas *cgroup limit* (`memory.max`).
3. **Apa arti status terminasi container dengan Exit Code 137?**
   * *Jawaban:* Container menerima sinyal `SIGKILL` (sinyal 9) dari sistem operasi, yang secara umum dipicu oleh Linux Kernel OOM (Out-of-Memory) Killer akibat penggunaan memori container melampaui limitasi `cgroup` yang didefinisikan. (Perhitungan: $128 + 9 = 137$).
4. **Apa keuntungan menggunakan StorageClass dengan atribut `volumeBindingMode: WaitForFirstConsumer` pada lingkungan analitik data terdistribusi?**
   * *Jawaban:* Menunda proses provisi dan pengikatan (*binding*) Persistent Volume hingga Pod yang mengonsumsinya telah dijadwalkan pada node tertentu oleh scheduler. Hal ini mencegah volume dialokasikan di Availability Zone yang berbeda dengan node tempat pod komputasi dijalankan.
5. **Mengapa Remote Shuffle Service (RSS) sangat direkomendasikan saat menjalankan Spark pada Spot/Preemptible Instances di Kubernetes?**
   * *Jawaban:* RSS memisahkan penyimpanan data intermediet *shuffle* dari siklus hidup node komputasi lokal. Jika sebuah Spot Instance dihentikan mendadak, data shuffle yang dihasilkan tetap tersimpan aman di RSS node lain, sehingga mencegah *shuffle fetch failure* dan *cascading stage recomputation*.

#### Bagian B: Pertanyaan Menengah (Intermediate)
6. **Jelaskan perbedaan mendasar mekanisme kerja isolasi memori antara Linux `cgroups v1` (`memory.limit_in_bytes`) dan `cgroups v2` (`memory.max` & `memory.high`)!**
   * *Jawaban:* Pada *cgroups v1*, ketika proses menyentuh batas `memory.limit_in_bytes`, Kernel OOM Killer akan langsung aktif secara agresif menghentikan proses. Pada *cgroups v2*, `memory.high` bertindak sebagai batas lunak (*throttling threshold*) yang memperlambat laju alokasi proses dan memicu *page cache reclamation* secara agresif tanpa langsung mematikan proses, sedangkan `memory.max` bertindak sebagai *hard boundary* pemanggilan OOM Killer.
7. **Bagaimana cara kerja reconcilation loop pada Custom Controller di Spark Operator ketika mendeteksi Executor Pod berada dalam status `Failed`?**
   * *Jawaban:* Controller memvalidasi status aktual Pod via Kube-APIServer event channel, membandingkannya dengan state pada CRD `SparkApplication`. Jika statusnya failed, Controller membaca *policy restart* dan konfigurasi toleransi kegagalan task; jika kegagalan masih dalam ambang batas toleransi, Controller memicu pembuatan manifest Pod Executor pengganti ke APIServer.
8. **Apa dampak performa dari penggunaan Network CNI berbasis Overlay Network (contoh: VXLAN encapsulation) terhadap stage Spark Shuffle?**
   * *Jawaban:* Overlay network melakukan enkapsulasi paket IP layer 3/4 ke dalam format paket baru, meningkatkan beban pemrosesan CPU untuk enkapsulasi/dekapsulasi, menambah latensi transfer paket beberapa milidetik, serta menurunkan *Maximum Transmission Unit* (MTU) efektif. Hal ini secara signifikan mereduksi throughput transfer data pada tahap Spark Shuffle yang sangat membebani I/O jaringan.
9. **Mengapa penempatan Spark Driver Pod pada Spot Instances dikategorikan sebagai *Anti-Pattern* yang kritikal?**
   * *Jawaban:* Spark Driver bertindak sebagai koordinator state terpusat (*DAG Scheduler*, *Task Scheduler*, *Block Manager Master*). Jika Spot Instance yang menampung Driver Pod dihentikan, seluruh context aplikasi hilang seketika, menyebabkan kegagalan total (*abrupt termination*) pada seluruh armada Executor Pod dan membatalkan keseluruhan pipeline.
10. **Bagaimana cara kerja integrasi Karpenter dalam mempercepat alokasi node komputasi untuk beban kerja data analitik dibandingkan Cluster Autoscaler tradisional?**
    * *Jawaban:* Karpenter berkomunikasi langsung dengan armada cloud provider API tanpa melalui kelompok abstraksi kaku (seperti AWS Auto Scaling Groups). Karpenter mengevaluasi karakteristik spesifik *resource requests* dari Pod yang berstatus pending (CPU, RAM, arsitektur chip, preferensi disk) dan secara dinamis langsung memilih jenis instance compute yang paling presisi (*right-sized*) serta menyediakannya dalam hitungan detik.

#### Bagian C: Skenario Kasus Produksi (Troubleshooting & Architecture)
11. **Skenario 1:** Klaster Kubernetes produksi Anda mengalami kegagalan pada pipeline Spark harian berulang kali tepat pada fase `Shuffle Read`. Log executor menunjukkan:
    `org.apache.spark.shuffle.FetchFailedException: Failed to connect to /10.244.15.22:7337`.
    Setelah diselidiki, IP `10.244.15.22` adalah pod executor yang mati 2 menit sebelumnya karena status *Node Eviction* (DiskPressure pada disk root node host). Bagaimana Anda menyelesaikan masalah struktural ini secara permanen?
    * *Jawaban Solusi:* 
      1. Petakan alokasi storage sementara Spark (`spark.local.dir`) ke volume khusus menggunakan `emptyDir` yang di-mount pada block store terpisah (misalnya NVMe Instance Store), bukan menggunakan disk root host Kubernetes (`/var/lib/kubelet`).
      2. Terapkan *Remote Shuffle Service* (Apache Celeborn) sehingga pembacaan shuffle terisolasi dari ketersediaan Pod executor produsen.
      3. Atur parameter *node eviction threshold* pada kubelet dan tetapkan alokasi disk minimum via *hard eviction limits* (`imagefs.available<15%`, `nodefs.available<10%`).
12. **Skenario 2:** Anda mengamati bahwa utilizasi CPU pada Spark Executor hanya mencapai 35%, meskipun resource allocation telah diatur pada `cores: 8`. Data pipeline membaca ribuan file JSON kecil berukuran 2 MB dari S3. Analisis metrik menunjukkan pod menghabiskan 60% waktu komputasi dalam status *I/O Wait* dan garbage collection pause. Langkah optimasi arsitektural apa yang wajib dilakukan?
    * *Jawaban Solusi:*
      1. **Atasi Masalah Small Files:** Gunakan Apache Iceberg / Delta Lake compaction (*bin-packing*) untuk menggabungkan file kecil menjadi file berukuran 128 MB / 512 MB sebelum komputasi dijalankan.
      2. **Vectorized IO Engine:** Ubah format data dari JSON berbasis *row-oriented text* menjadi *columnar binary format* seperti Apache Parquet.
      3. **Tuning Garbage Collector:** Ganti JVM Garbage Collector ke Garbage-First (G1GC) dengan alokasi *Region Size* yang sesuai:
         `-XX:+UseG1GC -XX:G1ReservePercent=15 -XX:InitiatingHeapOccupancyPercent=45`.
      4. Aktifkan Spark SQL Adaptive Query Execution (AQE) untuk menggabungkan partisi kecil secara otomatis saat runtime:
         `spark.sql.adaptive.coalescePartitions.enabled=true`.
13. **Skenario 3:** Tim Data Platform melaporkan bahwa aplikasi Flink streaming berstatus misi kritis sering mengalami penurunan metrik *processing throughput* secara periodik setiap 15 menit, disertai lonjakan drastis pada metrik checkpoint duration (dari 5 detik membengkak ke 180 detik). Hal ini memicu *backpressure* masif ke Kafka. Sistem menggunakan RocksDB state backend yang dipasang di EBS GP3. Di mana letak bottleneck sistem dan bagaimana remediasinya?
    * *Jawaban Solusi:*
      1. **Identifikasi Bottleneck:** RocksDB melakukan *LSM-Tree compaction* yang membutuhkan performa I/O baca/tulis acak tinggi. Volume AWS EBS GP3 standar memiliki limitasi baseline 3000 IOPS dan 125 MB/s throughput; saat *checkpointing* dan *compaction* berjalan paralel, batas burst I/O habis (*IOPS exhaustion*), memicu latensi I/O disk yang ekstrem.
      2. **Remediasi:**
         - Alihkan penyimpanan lokal RocksDB dari EBS GP3 ke volume SSD NVMe lokal (*Instance Store*) dengan konfigurasi `StorageClass` berbasis local-storage operator.
         - Aktifkan fitur *incremental checkpointing* pada konfigurasi Flink: `state.backend.incremental: true`.
         - Konfigurasikan RocksDB tuning flags di Flink: Naikkan write-buffer-size, gunakan direct I/O untuk melewati OS page cache overhead, dan pisahkan thread checkpointing dari thread pemrosesan stream utama.

---

### 16. Summary

Modul ini telah mengupas tuntas orkestrasi platform data modern tingkat enterprise pada Kubernetes:
* **Pergeseran Paradigma:** Dari scheduler microservices konvensional ke arsitektur *batch-aware* menggunakan **Volcano / YuniKorn** dengan keunggulan mekanisme *Gang Scheduling*, mencegah kondisi deadlock pada klaster multi-tenant.
* **Dekopel Komputasi & Stateful Data:** Transformasi eksekutor komputasi menjadi komponen *stateless* murni melalui adopsi **Remote Shuffle Service (RSS)**, memungkinkan pemanfaatan **Spot Instances** secara agresif (hingga 70-80% penghematan biaya) tanpa ancaman kegagalan bertingkat akibat preemption node.
* **Ketepatan Tata Kelola Sumber Daya Kernel:** Pemahaman interaksi JVM terhadap **cgroups v2** dan Linux OOM Killer, alokasi *memory overhead* yang tepat, eliminasi fragmentasi native buffer, dan optimalisasi storage lokal berkecepatan tinggi merupakan syarat mutlak dalam membangun platform data kelas enterprise yang tangguh, elastis, dan hemat biaya.