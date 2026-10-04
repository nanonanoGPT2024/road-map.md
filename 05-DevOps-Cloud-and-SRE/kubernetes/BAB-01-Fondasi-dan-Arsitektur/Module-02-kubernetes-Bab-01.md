# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI
**Kategori:** 05-DevOps-Cloud-and-SRE  
**Bab 01:** BAB-01-Fondasi-dan-Arsitektur  
**Topik:** Kubernetes Enterprise Architecture

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Membedah Siklus Hidup Request API:** Mengurai alur request pada `kube-apiserver` dari terminasi TLS, Authn, Authz, Admission Control (Mutating & Validating), hingga persistensi pada `etcd` via Raft Consensus engine.
- **Mengonfigurasi dan Mengoptimasi Control Plane High Availability (HA):** Mendesain topologi *stacked* vs *external etcd*, memitigasi *split-brain*, dan menyetel parameter performa (Fsync, snapshotting, compaction).
- **Menguasai Mekanisme Internal Node Engine:** Membedah interaksi antara `kubelet`, *Pod Lifecycle Event Generator* (PLEG), Container Runtime Interface (CRI via containerd/CRI-O), CNI, dan CSI.
- **Mengimplementasikan Scheduling Pipeline Lanjutan:** Membangun konfigurasi kustom berbasis *Scheduling Framework* (Filter, Score, Reserve, Permit, Bind) serta *Node Affinity/Anti-Affinity*, *Taints/Tolerations*, dan *Topology Spread Constraints*.
- **Membangun Arsitektur Produksi Skala Besar:** Mengimplementasikan pola ketahanan operasional enterprise menggunakan *API Priority and Fairness* (APF), *Pod Disruption Budgets* (PDB), *ResourceQuotas*, dan mitigasi *kernel conntrack starvation*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
1. **Konsep Fondasi Kubernetes (Modul 01):** Pod, Service, Deployment, ReplicaSet, Namespace, dan arsitektur dasar Master-Worker.
2. **Sistem Linux Tingkat Lanjut:** Linux Namespaces (Net, Mnt, PID, IPC, UTS, User), Cgroups v2, IPTables/NFTables, sistem I/O storage, dan socket IPC/gRPC.
3. **Jaringan Komputer Enterprise:** TCP/IP stack, model OSI layer 4 dan 7, TLS mutual authentication (mTLS), DNS resolution workflow, dan software-defined networking (overlay/underlay).
4. **Dasar Sistem Terdistribusi:** Teorema CAP, algoritma konsensus Paxos/Raft, dan konsep eventual consistency.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Siklus Hidup Eksekusi `kube-apiserver`
`kube-apiserver` bersifat stateless dan bertindak sebagai satu-satunya gerbang komunikasi menuju cluster data store (`etcd`).

```
[HTTP Request via TLS]
         │
         ▼
┌────────────────────────────────────────────────────────┐
│ 1. Authentication (Authn)                              │
│    - X.509 Client Certs, Webhook Token, OIDC, Bearer   │
└────────────────────────┬───────────────────────────────┘
                         │ (User/Group Identity established)
                         ▼
┌────────────────────────────────────────────────────────┐
│ 2. Authorization (Authz)                               │
│    - Node, RBAC, ABAC, Webhook Engine                  │
└────────────────────────┬───────────────────────────────┘
                         │ (Allowed)
                         ▼
┌────────────────────────────────────────────────────────┐
│ 3. Mutating Admission Controllers                      │
│    - Built-in (e.g., DefaultStorageClass)              │
│    - MutatingWebhookConfiguration (e.g., Sidecar Inj.) │
└────────────────────────┬───────────────────────────────┘
                         │ (Object Mutated)
                         ▼
┌────────────────────────────────────────────────────────┐
│ 4. Schema Validation (OpenAPI v3 Validation)           │
│    - Type checking, required fields, immutable fields  │
└────────────────────────┬───────────────────────────────┘
                         │ (Valid)
                         ▼
┌────────────────────────────────────────────────────────┐
│ 5. Validating Admission Controllers                    │
│    - Built-in (e.g., LimitRanger, PodSecurity)         │
│    - ValidatingWebhookConfiguration (OPA Gatekeeper)   │
└────────────────────────┬───────────────────────────────┘
                         │ (Approved)
                         ▼
┌────────────────────────────────────────────────────────┐
│ 6. Storage Layer Serialization & Persistence           │
│    - Transform to Internal Object Type                 │
│    - Write to /registry/<resource>/... via etcd3 API   │
└────────────────────────────────────────────────────────┘
```

1. **Authentication:** Handler memverifikasi identitas penyeru request. Jika satu autentikator sukses mengekstrak informasi subjek (`x509.CommonName`, `sub` pada JWT), rantai autentikasi dihentikan dan context dialihkan ke fase Authorization.
2. **Authorization:** Engine mengevaluasi apakah subjek memiliki hak cipta/baca/modifikasi terhadap resource (Verb: `create`, `get`, `list`, `patch`; Resource: `pods`, `deployments`; Namespace: target).
3. **Mutating Admission Webhooks:** Mengubah spec payload sebelum divalidasi. Urutannya krusial karena perubahan satu webhook dapat memicu kebutuhan mutasi lanjutan.
4. **Object Schema Validation:** Verifikasi tipe data JSON/YAML sesuai definisi native Kubernetes API schema.
5. **Validating Admission Webhooks:** Melakukan inspeksi ketat (read-only enforcement). Apabila salah satu validating webhook mengembalikan status *Deny*, request langsung ditolak (HTTP 403/400) dan transaksi dibatalkan sebelum menyentuh storage layer.
6. **etcd Linearizable Write:** Object diserialisasi ke protocol buffers dan ditulis ke `etcd` menggunakan quorum-based commit.

### 3.2 etcd Quorum dan Raft State Machine
`etcd` adalah distributed consistent key-value store berbasis Raft.
- **Formula Quorum:** 
  $$\text{Quorum} = \left\lfloor \frac{N}{2} \right\rfloor + 1$$
  Untuk $N = 3$, Quorum adalah 2. Toleransi kegagalan node: 1 node.
  Untuk $N = 5$, Quorum adalah 3. Toleransi kegagalan node: 2 node.
- **Fsync & I/O Latency:** WAL (*Write-Ahead Log*) harus di-flush ke disk menggunakan syscall `fsync`. Jika latency disk `fdatasync` melebihi $10\text{ ms}$, heartbeat Raft akan timeout, memicu *leader election* ulang terus-menerus (*flapping*), menyebabkan cluster degradation.
- **Compaction & Defragmentation:** `etcd` menggunakan sistem MVCC (Multi-Version Concurrency Control). Setiap update/delete membuat versi revisi baru. Tanpa periodic compaction, memory space dan file `db` akan mengalami fragmentasi sehingga memicu `etcdserver: mvcc: database space exceeded`.

### 3.3 Scheduling Framework Deep Dive
Scheduling pipeline pada `kube-scheduler` dibagi menjadi dua fase: **Scheduling Cycle** (berjalan single-threaded per Pod untuk konsistensi) dan **Binding Cycle** (berjalan asinkron multithreaded).

```
Pod Baru (Pending)
   │
   ▼
[Scheduling Queue: PriorityQueue (ActiveQ, BackoffQ, UnschedulableQ)]
   │
   ▼
┌── Scheduling Cycle (Synchronous) ──────────────────────────────┐
│  1. PreFilter   : Ekstraksi data Pod & validasi prasyarat      │
│  2. Filter      : Eliminasi Node yang tidak memenuhi kriteria  │
│                   (NodeResourcesFit, NodeName, Taints)         │
│  3. PreScore    : Normalisasi data state scoring               │
│  4. Score       : Kalkulasi bobot node (NodeAffinity, Spread)  │
│  5. Reserve     : Cadangkan resource node sebelum bind fisik   │
│  6. Permit      : Eksekusi tracking status (Delay, Approve)    │
└──┬─────────────────────────────────────────────────────────────┘
   │ (Reserve Success & Permit Approved)
   ▼
┌── Binding Cycle (Asynchronous) ────────────────────────────────┐
│  7. PreBind     : Mounting network attachment/volume stage     │
│  8. Bind        : Update .spec.nodeName via APIServer PATCH    │
│  9. PostBind    : Notifikasi metrik & telemetry execution      │
└────────────────────────────────────────────────────────────────┘
```

### 3.4 Kubelet Architecture: PLEG, CRI, CNI, dan CSI
Di dalam worker node:
1. **SyncLoop:** `kubelet` menjalankan loop monitoring yang membaca event dari API Server (Informer), local file (`/etc/kubernetes/manifests`), dan HTTP endpoints.
2. **PLEG (Pod Lifecycle Event Generator):** Bertugas melakukan relisting runtime container secara berkala (default 1 detik) melalui CRI, mendeteksi state transitions (misal: running ke dead), menerjemahkannya ke Pod Lifecycle Event, dan memasukannya ke `eventChannel` syncLoop. Jika runtime IO terhambat, PLEG akan degraded (`PLEG is not healthy`), memicu node berubah status menjadi `NotReady`.
3. **CRI (Container Runtime Interface):** Komunikasi via Unix Domain Socket gRPC (`runtime.v1`) menuju Container Runtime (seperti containerd). Runtime memanggil OCI (`runc`) untuk membuat Linux namespaces dan cgroups.
4. **CNI (Container Network Interface):** Runtime mengeksekusi binary plugin CNI (misal: Cilium, Calico) untuk mengonfigurasi `veth pair`, route table, IP allocation via IPAM, dan eBPF programs atau IPTables rules.
5. **CSI (Container Storage Interface):** Mengatur `ControllerPublishVolume` (Attach disk ke VM/Server), `NodeStageVolume` (Format dan mount filesystem ke global directory node), dan `NodePublishVolume` (Bind mount direktori host ke isolated rootfs container).

---

## 4. Why & What

| Dimensi | Pendekatan Monolitik / Basic Kubernetes | Arsitektur Enterprise Kubernetes Lanjutan |
| :--- | :--- | :--- |
| **Control Plane Topology** | Single master node, etcd co-located tanpa isolasi I/O, berisiko single point of failure (SPOF). | Multi-master HA (minimal 3 node), dedicated NVMe array untuk etcd WAL logs, dynamic load balancer untuk APIServer. |
| **Traffic Prioritization** | FIFO request queue pada APIServer; request berskala masif dapat menenggelamkan system components. | **API Priority and Fairness (APF)** aktif. Request diisolasi ke flow-schemas dan priority-levels terpisah. |
| **Resource Isolation** | CPU limit berbasis CFS quota tanpa pinning; scheduling tanpa mempertimbangkan NUMA nodes. | CPU Manager Policy `static` untuk zero-context switching pada workload latensi rendah, memory manager terikat NUMA. |
| **Disruption Management** | Rolling upgrade tanpa batasan; pod dapat mati bersamaan saat drain node. | **PodDisruptionBudget (PDB)** wajib pada semua layer, integrated dengan graceful termination hooks & lifecycle delays. |
| **Network Fabric** | Standard Linux Bridge / Overlay VXLAN dengan IPTables $O(n)$ latency scaling. | **eBPF-based CNI** (e.g., Cilium) bypass kube-proxy, $O(1)$ routing lookups via direct socket delivery (sockops). |

---

## 5. How (Workflow Detail)

### Alur Kerja Deklarasi hingga Pod Berstatus Running
1. **Operator Menjalankan `kubectl apply -f deployment.yaml`:**
   Client melakukan serialisasi manifest, memvalidasi schema lokal, dan mengirim request HTTP `POST/PUT` ke endpoint `/apis/apps/v1/namespaces/{ns}/deployments`.
2. **Kube-apiserver Execution Path:**
   Request melewati TLS termination -> Authn -> Authz (RBAC check) -> Mutating Webhooks (misal: injeksi Istio proxy) -> Validation -> Serialisasi ke etcd internal representation -> Commit ke Raft log etcd -> Respon HTTP 200/201 dikirim kembali ke client.
3. **Deployment Controller Reconciliation Loop:**
   `DeploymentController` mendeteksi create/update event via Informer Cache. Controller membaca spec, menghitung `Replicas`, dan menghasilkan resource `ReplicaSet` melalui panggilan API.
4. **ReplicaSet Controller Action:**
   `ReplicaSetController` menerima object baru, mendeteksi ketiadaan Pod yang cocok dengan label selector, lalu mengeksekusi request batch `POST /api/v1/namespaces/{ns}/pods` dengan field `spec.nodeName` kosong. Status Pod adalah `Pending`.
5. **Kube-Scheduler Scheduling Framework:**
   Informer pada scheduler menangkap Pod unassigned. Scheduler memasukkan Pod ke `ActiveQ`. Pod melalui fase:
   - *Filter*: Cek resource request (CPU/Memory) vs allocatable node, taints/tolerations, affinity rules.
   - *Score*: Pembobotan node terbaik (least requested, balanced resource allocation, image locality).
   - *Reserve & Bind*: Scheduler mengirim request subresource `POST /api/v1/namespaces/{ns}/pods/{name}/binding` untuk mengisi `spec.nodeName: "node-worker-01"`.
6. **Kubelet Execution Loop:**
   Informer `kubelet` pada `node-worker-01` mendeteksi bahwa Pod telah diasosiasikan dengannya.
   - Panggilan CSI: Mengeksekusi mount disk jika Pod membutuhkan volume persistence.
   - Panggilan CRI: Mengirim gRPC command `RunPodSandbox` ke Containerd. Containerd membuat Linux network namespace.
   - Panggilan CNI: Mengirim command `ADD` ke binary CNI untuk mengalokasikan IP dan merutekan gateway.
   - Container Initialization: Mengirim gRPC command `CreateContainer` dan `StartContainer` ke CRI untuk container `pause`, `initContainers`, dan `app containers`.
   - Cgroups V2 configuration: Mengikat CPU/Memory subsystem batas allocatable.
7. **Status Reporting:**
   PLEG menangkap status container yang berubah menjadi `Running`. `kubelet` mengirimkan PATCH update status Pod ke APIServer. APIServer menyimpan status ke `etcd`.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Pemerintahan Enterprise
- **`etcd`:** **Buku Besar Tanah Nasional (BPN)**. Satu-satunya sumber kebenaran mutlak. Hanya notaris resmi yang boleh mencatat, dan setiap perubahan halaman harus disepakati oleh mayoritas dewan konsensus (*Quorum*).
- **`kube-apiserver`:** **Gerbang Terpadu Satu Pintu**. Setiap orang yang masuk harus menunjukkan identitas (*Authn*), dicek izinnya (*Authz*), diperiksa apakah dokumennya perlu stempel khusus (*Mutating Webhook*), diverifikasi format dokumennya (*Validation*), baru diteruskan ke Buku Besar.
- **`kube-scheduler`:** **Biro Penempatan Tenaga Kerja**. Menganalisis kualifikasi pekerja (Pod requirements) dan mencari fasilitas cabang (Node) yang masih memiliki meja kerja kosong, listrik cukup, dan lingkungan yang sesuai (*Filtering & Scoring*).
- **`kube-controller-manager`:** **Auditor Kepatuhan Internal**. Mengawasi 24/7 apakah jumlah pekerja di lapangan sesuai dengan target instruksi dewan direksi (*Reconciliation Loop*).
- **`kubelet`:** **Mandor Pabrik Lapangan**. Menerima cetak biru dari gerbang utama, lalu memerintahkan kontraktor mesin (*CRI*), teknisi kabel/pipa (*CNI*), dan teknisi gudang logistik (*CSI*) untuk mendirikan unit kerja secara nyata.

### Topologi Arsitektur Control Plane High Availability (External etcd)

```
                    ┌────────────────────────┐
                    │ External Load Balancer │
                    │ (HAProxy / Keepalived) │
                    └───────────┬────────────┘
                                │ :6443
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ Control Plane 01 │   │ Control Plane 02 │   │ Control Plane 03 │
│                  │   │                  │   │                  │
│ ┌──────────────┐ │   │ ┌──────────────┐ │   │ ┌──────────────┐ │
│ │apiserver     │ │   │ │apiserver     │ │   │ │apiserver     │ │
│ └──────┬───────┘ │   │ └──────┬───────┘ │   │ └──────┬───────┘ │
│ ┌──────┴───────┐ │   │ ┌──────┴───────┐ │   │ ┌──────┴───────┐ │
│ │controller-mgr│ │   │ │controller-mgr│ │   │ │controller-mgr│ │
│ └──────────────┘ │   │ └──────────────┘ │   │ └──────────────┘ │
│ ┌──────────────┐ │   │ ┌──────────────┐ │   │ ┌──────────────┐ │
│ │scheduler     │ │   │ │scheduler     │ │   │ │scheduler     │ │
│ └──────────────┘ │   │ └──────────────┘ │   │ └──────────────┘ │
└────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                │ mTLS (TCP :2379)
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  etcd Node 01    │   │  etcd Node 02    │   │  etcd Node 03    │
│  (NVMe Disk)     │◄──┼─ (NVMe Disk)     │◄──┼─ (NVMe Disk)     │
│  Raft Peer :2380 ├───┘  Raft Peer :2380 ├───┘  Raft Peer :2380 │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Dynamic Scheduling via NodeAffinity & TopologySpreadConstraints

File: `simple-workload.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-processor
  namespace: core-banking
  labels:
    app.kubernetes.io/name: payment-processor
    tier: backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app.kubernetes.io/name: payment-processor
  template:
    metadata:
      labels:
        app.kubernetes.io/name: payment-processor
        tier: backend
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
            - matchExpressions:
              - key: topology.kubernetes.io/zone
                operator: In
                values:
                - ap-southeast-1a
                - ap-southeast-1b
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: DoNotSchedule
        labelSelector:
          matchLabels:
            app.kubernetes.io/name: payment-processor
      containers:
      - name: processor
        image: internal-registry.bank.co.id/fintech/payment:v2.1.0
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "1000m"
            memory: "1Gi"
```

### 7.2 Practical Example: Enterprise Production-Ready Pod Configuration

Konfigurasi menyeluruh mencakup APF (*API Priority and Fairness*), Lifecycle Hooks, Zero-Downtime Signal Handling, PDB, dan Kubelet QoS Class (Guaranteed).

File: `enterprise-apf-configuration.yaml`
```yaml
apiVersion: flowcontrol.apiserver.k8s.io/v1
kind: PriorityLevelConfiguration
metadata:
  name: critical-workload-priority
spec:
  type: Limited
  limited:
    nominalConcurrencyShares: 50
    limitResponse:
      type: Queue
      queuing:
        queues: 64
        handShakeLength: 10
        queueLengthLimit: 100
---
apiVersion: flowcontrol.apiserver.k8s.io/v1
kind: FlowSchema
metadata:
  name: payment-engine-schema
spec:
  priorityLevelConfiguration:
    name: critical-workload-priority
  matchingPrecedence: 500
  distinguisherMethod:
    type: ByUser
  rules:
  - subjects:
    - kind: ServiceAccount
      serviceAccount:
        name: payment-engine-sa
        namespace: core-banking
    resourceRules:
    - verbs: ["get", "list", "watch", "create", "update", "patch"]
      apiGroups: ["*"]
      resources: ["*"]
```

File: `enterprise-payment-core.yaml`
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: payment-core-pdb
  namespace: core-banking
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: payment-core
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-core
  namespace: core-banking
  labels:
    app.kubernetes.io/name: payment-core
    app.kubernetes.io/part-of: transaction-engine
spec:
  replicas: 4
  revisionHistoryLimit: 10
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 0
  selector:
    matchLabels:
      app.kubernetes.io/name: payment-core
  template:
    metadata:
      labels:
        app.kubernetes.io/name: payment-core
    spec:
      serviceAccountName: payment-engine-sa
      terminationGracePeriodSeconds: 60
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchLabels:
                  app.kubernetes.io/name: payment-core
              topologyKey: kubernetes.io/hostname
      containers:
      - name: engine
        image: internal-registry.bank.co.id/fintech/payment-core:v4.18.2
        imagePullPolicy: IfNotPresent
        # Guaranteed QoS Class: Request == Limit
        resources:
          requests:
            cpu: "2000m"
            memory: "4Gi"
          limits:
            cpu: "2000m"
            memory: "4Gi"
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 15; /usr/local/bin/drain-in-flight-tx.sh"]
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 10
          timeoutSeconds: 3
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 2
          successThreshold: 1
          failureThreshold: 2
        securityContext:
          readOnlyRootFilesystem: true
          allowPrivilegeEscalation: false
          runAsNonRoot: true
          runAsUser: 10001
          capabilities:
            drop:
            - ALL
        volumeMounts:
        - name: ephemeral-tmp
          mountPath: /tmp
      volumes:
      - name: ephemeral-tmp
        emptyDir:
          medium: Memory
          sizeLimit: 512Mi
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Arsitektur Transaksi Core Banking (150.000 RPS, Max Latency 50ms)
- **Konteks:** Sebuah bank multinasional melakukan migrasi platform transaksi dari mainframe ke On-Premises bare-metal Kubernetes Cluster (1.200 Worker Nodes, spread across 3 physical Datacenters berjarak 15 km dengan Dark Fiber connection rtt < 1.5ms).
- **Insiden pada Uji Beban Puncak (Stress Test):**
  1. Pada traffic 80.000 RPS, `etcd` mengalami disk write stalls sebesar 120ms. Hal ini memicu hilangnya heartbeat antar node etcd, memicu mass leader election, sehingga cluster API tidak merespon (*freeze*).
  2. Latensi antar-pod melompat dari 3ms ke 400ms karena *IPTables conntrack table exhaustion* di level kernel Linux worker node.
  3. Aplikasi backend diterminasi paksa dengan status `OOMKilled` dan `SIGKILL` tanpa sempat mengalirkan transaksi in-flight ke fallback message broker.
- **Root Cause Analysis (RCA):**
  - **Storage:** `etcd` di-deploy pada storage SAN multi-tenant yang menggunakan sharing I/O dengan platform database analitik, menghasilkan I/O spikes dan IOPS throttle.
  - **Jaringan:** Implementasi standar `kube-proxy` berbasis IPTables memuat lebih dari 120.000 Service rules. Kernel harus melakukan traversal linear untuk packet routing. Table `nf_conntrack` melebihi default limit 262.144.
  - **Scheduling:** Pod transaksi terakumulasi pada satu Datacenter akibat ketiadaan hard anti-affinity rules, menyebabkan saturasi bandwidth interface 25GbE pada top-of-rack switch zone tersebut.
- **Solusi Arsitektural Enterprise:**
  1. **Isolasi Total Control Plane:** Memindahkan etcd ke server bare-metal terpisah menggunakan dual NVMe disk PCI-e Gen 4 raid 1 terdedikasi, diformat menggunakan filesystem `ext4` dengan mount options `data=ordered,commit=1,barrier=1`.
  2. **Migrasi Datapath ke eBPF:** Mengganti `kube-proxy` IPTables dengan Cilium CNI native-eBPF Host Routing mode. Mematikan conntrack table di kernel worker node untuk pod-to-pod traffic, mengeliminasi iptables traversal latency ($O(1)$ algorithmic access).
  3. **Penyesuaian Kernel Parameter Worker Node:**
     ```bash
     sysctl -w net.netfilter.nf_conntrack_max=2097152
     sysctl -w net.core.somaxconn=32768
     sysctl -w net.ipv4.tcp_max_syn_backlog=16384
     ```
  4. **QoS Guaranteed & Zero Downtime Hooks:** Menerapkan PDB (`minAvailable: 75%`), `preStop` hook dengan sleep duration 15 detik untuk mengakomodasi de-registrasi IP dari Ingress controller sebelum SIGTERM dieksekusi, serta alokasi Guaranteed QoS (`requests.cpu == limits.cpu`).
- **Hasil:** Latensi p99 transaksi stabil pada angka 18ms di 150.000 RPS tanpa kegagalan koneksi atau `etcd` latency warning.

---

## 9. Trade-offs

| Aspek Arsitektur | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Topologi etcd** | **Stacked etcd** (Co-located dengan control plane node). | **External etcd** (Node fisik/VM khusus terpisah). | **Resource vs Resilience:** Stacked memangkas biaya infrastruktur dan kompleksitas setup. Namun, stacked berisiko mengalami *resource starvation* saat `kube-apiserver` menembak CPU/Memory tinggi. External memberikan proteksi fault-domain murni dan I/O throughput tinggi, namun menambah beban operational maintenance (sertifikat, OS patch). |
| **QoS Class Workload** | **Burstable** (`requests < limits`). | **Guaranteed** (`requests == limits`). | **Density vs Predictability:** Burstable meningkatkan rasio utilitas server (*overcommit* compute density tinggi), namun rentan mengalami throttling CPU atau dibunuh oleh OOM Killer saat memori host menipis. Guaranteed menjamin zero noisy-neighbor, isolasi mutlak, tetapi membutuhkan alokasi budget server jauh lebih mahal. |
| **API Admission Strategy** | **Fail-Closed** (`failurePolicy: Fail`). | **Fail-Open** (`failurePolicy: Ignore`). | **Security vs Availability:** Webhook `Fail-Closed` menjamin integritas keamanan cluster; jika webhook controller down, tidak ada object ilegal yang dapat dibuat. Namun hal ini dapat melumpuhkan seluruh operasional rilis pipeline (*denial of service self-inflicted*). Sebaliknya, `Fail-Open` mendahulukan availability namun membuka celah compliance breach. |
| **Container Networking** | **Overlay (e.g., VXLAN/Geneve)** | **Underlay / Direct Routing (e.g., BGP / Flat Route)** | **Portability vs Performance:** Overlay tidak membutuhkan koordinasi dengan tim network data center, berjalan di atas network apapun. Namun terdapat degradasi MTU header overhead (~50 byte) dan kalkulasi enkapsulasi CPU. Underlay menawarkan zero-overhead native line-rate speed, tetapi membutuhkan switch enterprise yang mendukung dynamic routing protocol (BGP). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Split-Brain and etcd Database Space Exceeded
- **Gejala:** APIServer mengembalikan response `500 Internal Server Error` saat penulisan manifest. Log APIServer: `etcdserver: mvcc: database space exceeded`.
- **Mitigasi Operasional:**
  ```bash
  # 1. Cek status ukuran endpoint etcd
  ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 \
    --cacert=/etc/kubernetes/pki/etcd/ca.crt \
    --cert=/etc/kubernetes/pki/etcd/server.crt \
    --key=/etc/kubernetes/pki/etcd/server.key \
    endpoint status --write-out=table

  # 2. Ambil snapshot revision terbaru
  REV=$(ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 \
    --cacert=/etc/kubernetes/pki/etcd/ca.crt \
    --cert=/etc/kubernetes/pki/etcd/server.crt \
    --key=/etc/kubernetes/pki/etcd/server.key \
    endpoint status --write-out="json" | jq -r '.[0].Status.header.revision')

  # 3. Eksekusi manual compaction
  ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 \
    --cacert=/etc/kubernetes/pki/etcd/ca.crt \
    --cert=/etc/kubernetes/pki/etcd/server.crt \
    --key=/etc/kubernetes/pki/etcd/server.key \
    compact $REV

  # 4. Defragmentasi database storage pada semua member
  ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 \
    --cacert=/etc/kubernetes/pki/etcd/ca.crt \
    --cert=/etc/kubernetes/pki/etcd/server.crt \
    --key=/etc/kubernetes/pki/etcd/server.key \
    defrag

  # 5. Clear alarm
  ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 \
    --cacert=/etc/kubernetes/pki/etcd/ca.crt \
    --cert=/etc/kubernetes/pki/etcd/server.crt \
    --key=/etc/kubernetes/pki/etcd/server.key \
    alarm disarm
  ```

### 10.2 Broken Mutating/Validating Webhook (Control Plane Deadlock)
- **Gejala:** Seluruh instruksi `kubectl apply` atau delete hang tanpa respons, hingga timeout 30 detik.
- **Root Cause:** Webhook service yang ditunjuk mati atau pod webhook pod tidak bisa running (misalnya terblokir oleh webhook itu sendiri: *Chicken-Egg problem*).
- **Langkah Pemulihan:**
  Akses langsung control plane via SSH, bypass APIServer client layer dengan menghapus konfigurasi webhook secara paksa:
  ```bash
  # Cek konfigurasi webhook yang aktif
  kubectl get validatingwebhookconfigurations.admissionregistration.k8s.io
  kubectl get mutatingwebhookconfigurations.admissionregistration.k8s.io

  # Hapus webhook yang menghalangi
  kubectl delete validatingwebhookconfiguration enterprise-gatekeeper-webhook --timeout=5s
  ```
  *Rekomendasi Best Practice:* Selalu tambahkan pengecualian namespace `kube-system` pada webhook konfigurasi:
  ```yaml
  namespaceSelector:
    matchExpressions:
    - key: kubernetes.io/metadata.name
      operator: NotIn
      values: ["kube-system", "kube-node-lease"]
  ```

### 10.3 OOMKilled Container Exit Code 137
- **Identifikasi:**
  ```bash
  kubectl get pod backend-api-6b7d488b8-x9p2z -o jsonpath='{range .status.containerStatuses[*]}{.name}{"\t"}{.lastState.terminated.reason}{"\tExitCode:"}{.lastState.terminated.exitCode}{"\n"}{end}'
  ```
  Jika keluar `ExitCode: 137` dengan reason `OOMKilled`, container melewati ambang batas Cgroup `memory.max`.
- **Tindakan Korektif:** Analisis profil memory leak menggunakan tool pprof atau dump JVM heap. Naikkan parameter `resources.limits.memory` sesuai profil workload nyata, dan pisahkan buffer `requests.memory` minimal 20% di bawah limit untuk beban lonjakan tak terduga jika tidak menggunakan QoS Guaranteed.

---

## 11. Best Practices (Production Checklist)

### Control Plane Readiness Checklist
- [ ] Minimal 3 Node Control Plane terdistribusi di physical rack/availability zone terpisah.
- [ ] Disk etcd berjalan pada SSD/NVMe dengan sequential I/O fdatasync latency di bawah $10\text{ ms}$ (Verifikasi via `fio`).
- [ ] Backup otomatis etcd via cron job terenkripsi, tersimpan di external S3 storage bucket.
- [ ] Validasi retensi snapshot etcd teruji minimal 1 kali per bulan via disaster recovery test.
- [ ] Audit Logging APIServer aktif dengan retensi minimal 90 hari, terintegrasi ke SIEM.
- [ ] Dynamic admission webhook memiliki `timeoutSeconds` maksimal 5 detik dan `failurePolicy: Ignore` untuk namespace non-kritis.

### Worker Node & Operating System Checklist
- [ ] Aktifkan `cgroups v2` untuk manajemen resource berbasis *memory.high* dan isolasi I/O proporsional.
- [ ] Nonaktifkan swap pada sistem operasi, atau gunakan `NodeSwap` Kubelet Feature Gate jika swap memory benar-benar dibutuhkan.
- [ ] Pastikan ephemeral storage diset limits untuk mencegah pod menghabiskan partisi host root `/`.
- [ ] Reserve OS memory & CPU melalui flag Kubelet `--kube-reserved` dan `--system-reserved`.

### Workload Reliability Checklist
- [ ] Seluruh Deployment wajib memiliki label standar enterprise: `app.kubernetes.io/name`, `app.kubernetes.io/version`, `app.kubernetes.io/part-of`.
- [ ] Setiap pod multi-replica wajib didefinisikan bersama `PodDisruptionBudget`.
- [ ] Inisialisasi probes (`readinessProbe`, `livenessProbe`, `startupProbe`) dengan parameter timeout dan interval yang rasional.
- [ ] Workload critical wajib mengimplementasikan `preStop` hook dengan grace period shutdown terkoordinasi.
- [ ] Pastikan tidak ada container yang berjalan dengan flag `securityContext.privileged: true` kecuali CNI atau storage agent sistem.

---

## 12. Hands-on Practice

Buat seluruh file dan jalankan praktikum berikut pada direktori lokal: `hands-on/m02/`.

### Langkah 1: Setup Workspace & Namespace Isolasi
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/

kubectl create namespace production-platform
kubectl create namespace production-secops
```

### Langkah 2: Mengonfigurasi APF (API Priority & Fairness)
Buat file `hands-on/m02/01-apf-workload.yaml`:
```yaml
apiVersion: flowcontrol.apiserver.k8s.io/v1
kind: PriorityLevelConfiguration
metadata:
  name: batch-workload-level
spec:
  type: Limited
  limited:
    nominalConcurrencyShares: 20
    limitResponse:
      type: Queue
      queuing:
        queues: 16
        handShakeLength: 5
        queueLengthLimit: 50
---
apiVersion: flowcontrol.apiserver.k8s.io/v1
kind: FlowSchema
metadata:
  name: batch-workload-schema
spec:
  priorityLevelConfiguration:
    name: batch-workload-level
  matchingPrecedence: 800
  distinguisherMethod:
    type: ByUser
  rules:
  - subjects:
    - kind: Group
      group:
        name: "system:authenticated"
    resourceRules:
    - verbs: ["get", "list"]
      apiGroups: ["batch"]
      resources: ["jobs", "cronjobs"]
      namespaces: ["production-platform"]
```
Terapkan:
```bash
kubectl apply -f 01-apf-workload.yaml
```

### Langkah 3: Mengonfigurasi Validating Webhook Simulator
Buat file `hands-on/m02/02-security-policy.yaml` untuk memblokir container yang berjalan tanpa label kepemilikan yang valid. Kita manfaatkan K8s Native Pod Security Standard (Namespace labels).
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production-platform
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/warn-version: latest
```
Terapkan:
```bash
kubectl apply -f 02-security-policy.yaml
```

### Langkah 4: Implementasi Workload Guaranteed QoS dengan PreStop Hook & PDB
Buat file `hands-on/m02/03-resilient-microservice.yaml`:
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: auth-service-pdb
  namespace: production-platform
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: auth-service
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
  namespace: production-platform
  labels:
    app: auth-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: auth-service
  template:
    metadata:
      labels:
        app: auth-service
    spec:
      terminationGracePeriodSeconds: 45
      containers:
      - name: auth-engine
        image: registry.k8s.io/e2e-test-images/agnhost:2.43
        command: ["/agnhost", "netexec", "--http-port=8080"]
        resources:
          requests:
            cpu: "250m"
            memory: "256Mi"
          limits:
            cpu: "250m"
            memory: "256Mi"
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "echo Inform Ingress Controller... && sleep 10"]
        livenessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          runAsNonRoot: true
          runAsUser: 1000
          capabilities:
            drop:
            - ALL
```
Terapkan:
```bash
kubectl apply -f 03-resilient-microservice.yaml
```

### Langkah 5: Pengujian Drain Node & PDB Enforcement
Uji ketahanan pod disruption budget:
```bash
# Cek alokasi pod pada node
kubectl get pods -n production-platform -o wide

# Coba simulasi drain node (Ganti <TARGET_NODE_NAME> sesuai environment)
TARGET_NODE=$(kubectl get pods -n production-platform -o jsonpath='{.items[0].spec.nodeName}')
kubectl drain $TARGET_NODE --ignore-daemonsets --delete-emptydir-data --dry-run=server
```
Perhatikan bagaimana eviction engine mengevaluasi PDB sebelum memberikan izin terminasi.

---

## 13. Exercise

### Tingkat: Easy
1. Ubah konfigurasi `auth-service` pada bab hands-on agar memiliki environment variable `ENVIRONMENT=production` menggunakan `ConfigMapKeyRef` terpisah.
2. Buat Pod baru pada namespace `production-platform` yang sengaja melanggar Pod Security Standard `restricted` (misalnya menambahkan `securityContext.privileged: true`), dan amati error yang dihasilkan oleh API Server.

### Tingkat: Medium
1. Konfigurasikan Deployment `order-service` dengan 4 replicas yang memiliki aturan `podAntiAffinity` level **hard** (`requiredDuringSchedulingIgnoredDuringExecution`). Sebarkan pod tersebut di level hostname. Uji apa yang terjadi jika replika dinaikkan menjadi angka yang melebihi jumlah ketersediaan Worker Node di cluster Anda.
2. Simulasikan skenario `CrashLoopBackOff` dan kaji keluaran log container menggunakan perintah `kubectl logs --previous` serta inspeksi exit status code-nya via JSON formatting.

### Tingkat: Hard
1. Buat custom Admission Webhook menggunakan Go atau Python yang bertugas menginjeksi anotasi tanggal deployment `bank.co.id/deploy-timestamp` secara dinamis ke setiap Pod yang masuk ke namespace `production-platform`. Buat TLS certificate CA mandiri, simpan sebagai Kubernetes Secret, dan daftarkan melalui `MutatingWebhookConfiguration`. Pastikan webhook tersebut memiliki konfigurasi `reinvocationPolicy: IfNeeded`.

---

## 14. Challenge

**Studi Kasus Penyelamatan Cluster Produksi (Tantangan Tak Terstruktur):**

Sebuah cluster Kubernetes produksi berskala 800 node mengalami insiden kegagalan kaskade (*cascading failure*). 
- Tim Security baru saja merilis sebuah controller policy enforcement pihak ketiga dengan konfigurasi `ValidatingWebhookConfiguration` global (`failurePolicy: Fail`, `timeoutSeconds: 30`, intercepting `*` API Groups).
- Controller policy tersebut dideploy sebagai Deployment di dalam cluster pada namespace `secops`.
- Secara tidak terduga, node fisik tempat controller tersebut berjalan mengalami *kernel panic* dan mati mendadak. 
- Akibatnya, `kube-apiserver` tidak lagi bisa melakukan validasi webhook ke pod security controller. Karena webhook diset `Fail`, seluruh API request pembuatan pod baru di seluruh cluster tertolak, termasuk pod controller itu sendiri yang mencoba di-reschedule oleh scheduler ke node yang sehat! 
- Di saat yang sama, monitoring menunjukkan etcd mengalami *read-amplification* drastis karena ratusan CronJob internal mencoba melakukan retry request secara eksponensial.

**Tugas Anda:**  
Rancang rencana mitigasi kedaruratan (Runbook P1 Disaster Recovery) langkah demi langkah untuk memulihkan API Server tanpa menghancurkan data etcd, memulihkan operasional cluster, dan desain post-mortem policy agar arsitektur cluster Anda kebal terhadap jebakan dependensi sirkular ini di masa mendatang!

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic
1. Apa fungsi mendasar dari modul `PLEG` di dalam Kubelet?
2. Mengapa etcd merekomendasikan jumlah anggota cluster bernilai ganjil (odd number)?
3. Pada fase Admission Webhook, manakah yang dieksekusi lebih dulu antara Mutating Webhook dan Validating Webhook?
4. Subresource apa pada Kubernetes Pod yang diubah oleh `kube-scheduler` untuk menetapkan Pod ke Worker Node fisik?
5. Apa indikasi utama jika sebuah Pod dihentikan dengan status `OOMKilled` dan exit code 137?

### Bagian B: Intermediate
6. Bagaimana cara algoritma konsensus Raft pada etcd menangani situasi jaringan terisolasi (*Network Partition*) sehingga data tidak mengalami *split-brain*?
7. Apa perbedaan mendasar dalam alokasi resource CPU antara QoS Class `Burstable` dan QoS Class `Guaranteed` pada level Linux Kernel Cgroups?
8. Mengapa operasi `etcd compaction` secara berkala tidak langsung mengurangi ukuran file fisik database (`etcd.db`) di dalam media penyimpanan?
9. Jelaskan bagaimana `API Priority and Fairness` (APF) mencegah request bertaraf rendah (misal: list pods oleh monitoring agent) menenggelamkan request kritis (misal: leader election lease updates)!
10. Apa risiko fatal membiarkan `terminationGracePeriodSeconds` default (30s) pada pod tanpa menggunakan `preStop` hook saat berada di belakang Ingress Controller throughput tinggi?

### Bagian C: Skenario Kasus Produksi
11. **Kasus 1:** Setelah melakukan upgrade cluster control plane, Anda menemukan log Kubelet dipenuhi error `failed to reserve pod: NodeResourcesFit failed`. Namun, ketika dicek dengan `kubectl top node`, utilitas CPU real-time hanya 15%. Mengapa scheduler menolak menempatkan Pod pada node tersebut?
12. **Kasus 2:** Sebuah aplikasi e-commerce sering mengalami request dropped (koneksi HTTP 502 Bad Gateway) selama proses Rolling Update Deployment berlangsung, meskipun status pod baru sudah berstatus `Running`. Komponen apa yang belum disinkronkan secara benar dalam manifest?
13. **Kasus 3:** Node worker Anda mendadak berstatus `NotReady`. Saat diperiksa, proses containerd masih hidup, namun log Kubelet menunjukkan pesan error `PLEG is not healthy: skipping pod synchronization`. Analisis faktor utama penyebab kegagalan ini di level low-level Linux IO/Kernel!

---

### Kunci Jawaban & Pembahasan Quiz

#### Bagian A: Basic
1. **PLEG (Pod Lifecycle Event Generator):** Komponen internal Kubelet yang memeriksa status runtime container secara periodik, mendeteksi perubahan state (create, running, exit), dan menerjemahkannya ke lifecycle events agar thread worker Kubelet tidak perlu melakukan polling status secara intensif.
2. **Ganjil pada etcd:** Nilai ganjil ($2n+1$) memberikan toleransi kesalahan yang sama dengan nilai genap berikutnya ($2n+2$) tanpa menambah overhead latency write quorum. Contoh: 3 node toleransi 1 kegagalan (Quorum 2). 4 node toleransi tetap 1 kegagalan (Quorum 3). Penambahan node ke-4 hanya membuang resource dan menambah latency sinkronisasi.
3. **Urutan Admission:** Mutating Webhook dieksekusi **sebelum** Validating Webhook. Hal ini memastikan bahwa setiap modifikasi nilai default atau injeksi konfigurasi selesai dilakukan sebelum validasi akhir memberlakukan invariant aturan bisnis.
4. **Subresource Penjadwalan:** Subresource `/binding`. Scheduler mengirim object `Binding` yang memetakan pod ke node via HTTP request, mengisi field metadata `spec.nodeName`.
5. **Exit Code 137:** Mengindikasikan container dihentikan paksa oleh sistem operasi melalui sinyal `SIGKILL` (sinyal 9) yang dipicu oleh Linux Kernel OOM Killer karena pemakaian memory melewati batas limit cgroup (`128 + 9 = 137`).

#### Bagian B: Intermediate
6. **Mitigasi Split-brain pada Raft:** Raft mensyaratkan setiap penulisan log diverifikasi oleh Quorum $\lfloor N/2 \rfloor + 1$. Jika terjadi partisi jaringan, hanya partisi yang menguasai mayoritas node yang dapat mencapai quorum dan menerima penulisan data. Partisi minoritas akan menolak commit dan berada pada state candidate/follower, sehingga integritas data terlindungi.
7. **QoS Guaranteed vs Burstable:** Guaranteed menetapkan `requests == limits`. Pada cgroups v1/v2, nilai `cpu.shares` (atau `cpu.weight`) diset maksimal dan `cpu.cfs_quota_us` diatur pas dengan request, mencegah *CPU throttling* tak terduga. Burstable membiarkan request lebih rendah dari limit, sehingga jika host padat, Linux kernel CFS scheduler akan mencekik (throttle) alokasi jatah clock CPU container tersebut.
8. **Compaction vs Defrag:** Compaction hanya menandai data revisi lama sebagai *tombstone/free space* secara logis di internal B-Tree storage engine (`bbolt`). Alokasi blok file storage fisik OS tidak berkurang. Diperlukan perintah `defrag` untuk mengatur ulang fragmentasi halaman dan melepaskan physical space kembali ke sistem operasi host.
9. **Mekanisme APF:** APF memecah pool thread eksekusi APIServer menjadi sub-queues menggunakan algoritma *Fair Queuing* (shuffle-sharding). Request dikelompokkan berdasarkan identitas/kategori. Jika flow monitoring membanjiri request, queue miliknya yang akan penuh dan ditolak (HTTP 429), sementara queue terpisah milik sistem kritis tetap memiliki jatah eksekusi independen.
10. **PreStop Hook vs Ingress Race Condition:** Saat pod diterminasi, Kubelet mengirim `SIGTERM` ke container bersamaan dengan APIServer menghapus IP pod dari Endpoints/EndpointSlice. Ingress controller membutuhkan waktu propagasi network table beberapa detik. Tanpa `preStop: sleep`, container aplikasi akan mati duluan saat Ingress masih meneruskan incoming traffic baru ke IP pod lama, memicu paket TCP `RST` (connection dropped).

#### Bagian C: Skenario Kasus Produksi
11. **Analisis Kasus 1:** `kube-scheduler` mengambil keputusan berbasis **Resource Requests** (reservasi kapasitas), bukan berdasarkan pemakaian real-time metrics (`kubectl top`). Meskipun utilitas riil 15%, jika akumulasi nilai `spec.containers[*].resources.requests.cpu` pada seluruh pod yang sudah terjadwal di node tersebut telah menyentuh batas kapasitas allocatable node, scheduler wajib menolak pod baru untuk menghindari resiko kelebihan beban komputasi.
12. **Analisis Kasus 2:** Masalah timbul karena dua kelalaian konfigurasi:
    - Tidak ada `readinessProbe` yang akurat, sehingga pod dianggap siap melayani traffic sesaat setelah proses engine start, padahal inisialisasi internal framework/koneksi database belum tuntas.
    - Tidak ada implementasi `lifecycle.preStop` script (`sleep`), menyebabkan container yang sedang di-rolling update langsung mati seketika saat menerima SIGTERM, padahal load balancer ingress masih memproses routing transaksi in-flight ke IP container tersebut.
13. **Analisis Kasus 3:** Pesan `PLEG is not healthy` mengindikasikan worker thread Kubelet gagal melakukan relist status container via CRI gRPC socket dalam jendela timeout tertentu. Pada level low-level Linux, ini umumnya diakibatkan oleh:
    - **Disk I/O Hang:** Partisi tempat runtime state berada (`/var/lib/containerd`) terblokir akibat saturated I/O queue (disk latency tembus ribuan milidetik), sehingga I/O syscall context switch macet.
    - **Kernel D-State:** Container process terjebak dalam Linux Uninterruptible Sleep state (State `D`) akibat problem NFS/CSI stale volume lock atau network storage timeout, sehingga runtime CRI tidak dapat mengembalikan status thread ke Kubelet.

---

## 16. Summary

1. Arsitektur Kubernetes tingkat lanjut bertumpu pada integritas konsistensi **etcd** melalui algoritma Raft dan determinasi **kube-apiserver** sebagai single stateless coordinator engine.
2. Setiap transaksi API melewati pipeline berurutan: **TLS Termination -> Authn -> Authz -> Mutating Admission -> Schema Validation -> Validating Admission -> etcd storage**.
3. **Kube-scheduler** memisahkan siklusnya menjadi *Scheduling Cycle* sinkronus (*Filtering, Scoring, Reserving*) dan *Binding Cycle* asinkronus untuk menjamin efisiensi performa alokasi pod.
4. **Kubelet** beroperasi mengorkestrasi low-level engine melalui abstraksi standar: **PLEG** (monitoring state), **CRI** (lifecycle container), **CNI** (network datapath dan IPAM), dan **CSI** (storage mounting pipeline).
5. Keandalan produksi skala enterprise menuntut isolasi storage data path (NVMe dedicated untuk etcd), proteksi availability (*Pod Disruption Budget, Zero-downtime Lifecycle Hooks*), prioritisasi beban kerja (*API Priority and Fairness*), serta adopsi teknologi jaringan modern berbasis eBPF guna memangkas overhead kernel.