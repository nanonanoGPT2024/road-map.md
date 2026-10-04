# Bab 01: Fondasi Orkestrasi & Arsitektur Sistem
## Module 01: Arsitektur Inti Kubernetes & Control Plane Mechanics

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** siklus hidup objek Kubernetes mulai dari interaksi CLI/API hingga eksekusi kontainer di node pekerja.
- **Mengidentifikasi** komponen kritis *Control Plane* (`kube-apiserver`, `etcd`, `kube-scheduler`, `kube-controller-manager`) dan *Worker Node* (`kubelet`, `kube-proxy`, *Container Runtime*).
- **Mengevaluasi** status konsistensi klaster menggunakan mekanisme *reconciliation loop* dan *Optimistic Concurrency Control* (OCC) berbasis `etcd`.
- **Mendiagnosis** kegagalan sistematis pada layer orkestrasi seperti kegagalan konsensus `etcd`, *node unschedulable*, dan desinkronisasi status pod.
- **Mengimplementasikan** konfigurasi Pod minimalis yang tangguh dengan isolasi proses, alokasi batas sumber daya, dan *readiness/liveness probes* sesuai standar produksi.

---

### 2. Concept
Kubernetes adalah sistem orkestrasi kontainer terdistribusi yang mengadopsi paradigma **sistem kontrol deklaratif** (*declarative control system*). Alih-alih mengeksekusi urutan perintah imperatif, operator mendefinisikan *desired state* (keadaan yang diinginkan) dari infrastruktur dan aplikasi dalam format terstruktur (YAML/JSON). 

Sistem secara terus-menerus membaca *current state* (keadaan aktual) infrastruktur melalui sensor/metrik dari node, membandingkannya dengan *desired state* yang tersimpan di *distributed key-value store*, dan mengeksekusi operasi konvergensial melalui sekumpulan *control loops* (disebut juga *controllers*) untuk mengeliminasi deviasi (*state drift*).

```
        +-----------------------------------------+
        |              Desired State              |
        |      (Spesifikasi Objek di etcd)        |
        +--------------------+--------------------+
                             |
                             v
                     +---------------+
                     |  Reconcile /  | <---+
                     | Control Loop  |     |
                     +-------+-------+     | Aktualisasi
                             |             | Status
                             v             |
        +--------------------+--------------------+
        |              Current State              |
        |        (Realitas di Worker Nodes)       |
        +-----------------------------------------+
```

Fondasi matematika dan desain sistemnya bersandar pada teori kontrol umpan balik (*feedback control theory*) dan algoritma konsensus Raft untuk toleransi kesalahan terdistribusi (*distributed fault tolerance*).

---

### 3. Why It Matters
Dalam arsitektur *bare-metal* atau *virtual machine* statis, kegagalan proses aplikasi, kehabisan memori (*OOM*), atau kerusakan kernel node memerlukan intervensi manual dari tim Site Reliability Engineering (SRE). Skalabilitas horizontal memerlukan konfigurasi terpisah pada *load balancer*, pendaftaran DNS, pembuatan sertifikat, dan orkestrasi jaringan.

Tanpa Kubernetes:
- *Downtime* meningkat drastis saat proses mati (*unhandled exceptions*).
- Pemanfaatan sumber daya komputasi (*bin-packing*) sangat tidak efisien (sering kali utilisasi CPU server < 15%).
- *Release engineering* berisiko tinggi; *rollback* membutuhkan eksekusi skrip Bash imperatif yang rawan gagal parsial (*half-configured state*).

Dengan memahami arsitektur internal Kubernetes, kegagalan infrastruktur diperlakukan sebagai kondisi normal (*ephemeral failure*). Kubernetes mengotomatisasi pemulihan diri (*self-healing*), penyeimbangan beban (*traffic routing*), serta isolasi kegagalan (*blast radius mitigation*) pada skala puluhan ribu kontainer.

---

### 4. What It Is
Secara teknis, Kubernetes adalah implementasi platform komputasi klaster terdistribusi yang memisahkan tanggung jawab menjadi dua lapisan (*planes*):

```
+---------------------------------------------------------------------------------+
|                                  CONTROL PLANE                                  |
|  +-------------------+  +--------------------+  +----------------------------+  |
|  |    kube-apiserver |  |   kube-scheduler   |  |  kube-controller-manager   |  |
|  +---------+---------+  +---------+----------+  +-------------+--------------+  |
|            ^                      ^                           ^                 |
|            |                      v                           |                 |
|            |            +---------+----------+                |                 |
|            +----------->|        etcd        |<---------------+                 |
|                         +--------------------+                                  |
+-----------------------------------+---------------------------------------------+
                                    | Network Fabric (mTLS)
+-----------------------------------v---------------------------------------------+
|                                  WORKER NODE                                    |
|  +--------------------+  +-------------------+  +----------------------------+  |
|  |      kubelet       |  |    kube-proxy     |  |  Container Runtime (CRI)   |  |
|  +--------------------+  +-------------------+  +----------------------------+  |
+---------------------------------------------------------------------------------+
```

#### Komponen Control Plane:
1. **`kube-apiserver`**: Titik masuk tunggal (REST interface) untuk klaster. Komponen stateless yang memvalidasi, mengonfigurasi skema, memproses autentikasi/otorisasi, dan menulis ke `etcd`.
2. **`etcd`**: Basis data key-value konsisten dan terdistribusi tinggi yang mengimplementasikan protokol konsensus Raft. Bertindak sebagai *single source of truth* untuk seluruh state klaster.
3. **`kube-scheduler`**: Menugaskan Pod baru yang belum dialokasikan ke Node yang memenuhi syarat berdasarkan filter (predikat) dan skor (prioritas).
4. **`kube-controller-manager`**: Menjalankan proses pengontrol inti (Node Controller, ReplicaSet Controller, EndpointSlice Controller, dll.) dalam satu biner multi-threaded.

#### Komponen Worker Node:
1. **`kubelet`**: Agen lokal pada setiap node yang memastikan kontainer yang didefinisikan dalam `PodSpec` berjalan dan sehat melalui API Container Runtime Interface (CRI).
2. **`kube-proxy`**: Pengelola aturan jaringan (*iptables* atau *IPVS*) pada setiap node untuk mengabstraksikan akses ke Pod di balik *Service*.
3. **`Container Runtime`** (misal: `containerd`, `CRI-O`): Biner tingkat rendah yang bertugas mengunduh image kontainer, membuat cgroups, namespaces, dan mengeksekusi kontainer.

---

### 5. How It Works
Siklus pembuatan objek (contoh: pembuatan Pod) mendemonstrasikan bagaimana komponen-komponen ini saling berinteraksi secara asinkron tanpa komunikasi langsung antarkomponen *slave-to-master*, melainkan murni terkoordinasi melalui `kube-apiserver`.

```
[Operator]  [kube-apiserver]    [etcd]    [kube-scheduler]  [kubelet]     [CRI]
    |              |              |              |              |           |
    | 1. POST pod  |              |              |              |           |
    |------------->|              |              |              |           |
    |              | 2. Commit    |              |              |           |
    |              |------------->|              |              |           |
    |              |<-------------|              |              |           |
    |<-------------| 201 Created  |              |              |           |
    |              |              |              |              |           |
    |              | 3. Watch Event (Pod Unscheduled)           |           |
    |              |---------------------------->|              |           |
    |              |              |              | 4. Filter    |           |
    |              |              |              |    & Score   |           |
    |              | 5. Bind Pod to Node         |              |           |
    |              |<----------------------------|              |           |
    |              | 6. Update NodeAssignment    |              |           |
    |              |------------->|              |              |           |
    |              |              |              |              |           |
    |              | 7. Watch Event (Pod Scheduled to this Node)|           |
    |              |------------------------------------------->|           |
    |              |              |              |              | 8. Exec   |
    |              |              |              |              | CRI Call  |
    |              |              |              |              |---------->|
    |              |              |              |              | 9. Status |
    |              | 10. Update Pod Status       |              |<----------|
    |              |<-------------------------------------------|           |
    |              | 11. Write Status            |              |           |
    |              |------------->|              |              |           |
```

1. **Autentikasi & Autorisasi**: Operator mengirim manifest Pod via `kubectl`. `kube-apiserver` memvalidasi identitas (TLS Cert / Token) dan hak akses (RBAC).
2. **Mutating & Validating Admission Control**: Mutating webhooks mengubah payload jika perlu (misal: injeksi sidecar); Validating webhooks memverifikasi integritas konfigurasi.
3. **Persistensi etcd**: Objek Pod ditulis ke `/registry/pods/<namespace>/<name>`. `kube-apiserver` menggunakan mekanisme Optimistic Concurrency Control (OCC) melalui field `metadata.resourceVersion`.
4. **Scheduling Queue**: `kube-scheduler` yang mengawasi (*watch*) stream API mendeteksi adanya Pod dengan field `nodeName` kosong.
5. **Filtering & Scoring**: Scheduler menyaring node yang tidak valid (kekurangan memori/CPU, *taints*, dll.), lalu memberi bobot pada node yang lolos. Node dengan nilai tertinggi dipilih.
6. **Binding**: Scheduler mengirim objek `Binding` ke `kube-apiserver` untuk memperbarui atribut `nodeName` pada Pod.
7. **Node Execution**: `kubelet` pada node terpilih (yang melakukan polling asinkron via HTTP/2 streaming *watch*) mendeteksi Pod baru yang ditugaskan padanya.
8. **Runtime Invocation**: `kubelet` mengeksekusi pemanggilan gRPC via CRI (Container Runtime Interface) ke `containerd`/`CRI-O` untuk:
   - Mengalokasikan cgroups (pembatasan CPU/memori).
   - Memasang kernel namespaces (Network, Mount, PID, UTS, IPC).
   - Menghubungkan CNI (Container Network Interface) untuk penyediaan IP lokal.
   - Menjalankan kontainer aplikasi.
9. **Status Reporting**: `kubelet` memantau eksekusi kontainer dan mengirim laporan status Pod (`ContainerCreating`, `Running`, dll.) kembali ke `kube-apiserver` secara berkala.

---

### 6. Architecture & Data Flow Diagram

```
+---------------------------------------------------------------------------------------------------+
| CONTROL PLANE NODE                                                                                |
|                                                                                                   |
|  +--------------------+                                                                           |
|  | Admin CLI / CI/CD  |                                                                           |
|  +---------+----------+                                                                           |
|            | HTTPS / JSON (Port 6443)                                                             |
|            v                                                                                      |
|  +---------------------------------------------------------------------------------------------+  |
|  | kube-apiserver                                                                              |  |
|  |                                                                                             |  |
|  | +------------------+   +-------------------+   +--------------------+   +-----------------+ |  |
|  | | Authentication   |-->| Authorization     |-->| Mutating Admission |-->| Validating      | |  |
|  | | (x509, Webhook)  |   | (RBAC, ABAC)      |   | Webhook Engine     |   | Admission Webhk | |  |
|  | +------------------+   +-------------------+   +--------------------+   +--------+--------+ |  |
|  +----------------------------------------------------------------------------------|----------+  |
|            ^                                                                        |             |
|            | Watch Stream (HTTP/2 Chunked)                     Write State (mTLS)   v             |
|            |                                                         +-------------------------+  |
|            |                                                         | etcd Cluster (Raft)     |  |
|            |                                                         | (Port 2379/2380)        |  |
|            |                                                         +-------------------------+  |
|            +---------------------------------+                                      ^             |
|            |                                 |                                      | Quorum      |
|            v                                 v                                      v (2n+1)      |
|  +-----------------------+     +-------------------------------+     +-------------------------+  |
|  | kube-scheduler        |     | kube-controller-manager       |     | etcd Peer Replica       |  |
|  | - Node Filtering      |     | - ReplicaSet Controller       |     +-------------------------+  |
|  | - Priority Scoring    |     | - Node Lifecycle Controller   |                                  |
|  +-----------------------+     | - EndpointSlice Controller    |                                  |
|                                +-------------------------------+                                  |
+---------------------------------------------------------------------------------------------------+
                                               |
                                               | TLS Network Boundary
                                               v
+---------------------------------------------------------------------------------------------------+
| WORKER NODE                                                                                       |
|                                                                                                   |
|  +-----------------------------------------------------+   +-----------------------------------+  |
|  | kubelet                                             |   | kube-proxy                        |  |
|  |                                                     |   |                                   |  |
|  |  +----------------------+  +---------------------+  |   |  Reads Services & Endpoints via   |  |
|  |  | Pod Lifecycle Event  |  | Volume / Secret     |  |   |  kube-apiserver watch             |  |
|  |  | Generator (PLEG)     |  | Manager             |  |   |                                   |  |
|  |  +----------+-----------+  +----------+----------+  |   |  Manipulasi Kernel:               |  |
|  |             |                         |             |   |  - Linux iptables/IPVS Rules      |  |
|  +-------------|-------------------------|-------------+   +-----------------+-----------------+  |
|                | gRPC (Unix Domain Sock) |                                   |                    |
|                v                         v                                   v                    |
|  +-----------------------------------------------------+   +-----------------------------------+  |
|  | Container Runtime (CRI: containerd / CRI-O)         |   | Linux Kernel Packet Filter        |  |
|  |                                                     |   | (Netfilter / eBPF Datapath)       |  |
|  |  +---------------------+   +---------------------+  |   +-----------------+-----------------+  |
|  |  | OCI Engine (runc)   |   | CNI Plugin (Network)|  |                     ^                    |
|  |  +----------+----------+   +----------+----------+  |                     |                    |
|  +-------------|-------------------------|-------------+                     |                    |
|                |                         |                                   |                    |
|                v                         v                                   |                    |
|  +-----------------------------------------------------+                     |                    |
|  | POD ISOLATION BOUNDARY                              |                     |                    |
|  |                                                     |                     |                    |
|  |  [cgroups: cpu, memory, blkio]                      |                     |                    |
|  |  [namespaces: net, mnt, pid, ipc, uts]              |                     |                    |
|  |                                                     |                     |                    |
|  |  +------------------------+  +-------------------+  |                     |                    |
|  |  | Container: App Process |  | Pause Container   |--+---------------------+                    |
|  |  +------------------------+  +-------------------+  |      (veth pair to bridge)               |
|  +-----------------------------------------------------+                                          |
+---------------------------------------------------------------------------------------------------+
```

---

### 7. Simple Example
Manifest deklaratif Pod paling mendasar yang valid dan dapat dieksekusi secara instan:

```yaml
# pod-simple.yaml
apiVersion: v1
kind: Pod
metadata:
  name: alpine-heartbeat
  namespace: default
  labels:
    app.kubernetes.io/name: heartbeat
spec:
  containers:
  - name: sleeper
    image: alpine:3.19.1
    command: ["/bin/sh", "-c", "while true; do echo 'alive'; sleep 5; done"]
```

Perintah eksekusi dan validasi:
```bash
# 1. Terapkan state ke API server
kubectl apply -f pod-simple.yaml

# 2. Pantau transisi state secara real-time
kubectl get pods alpine-heartbeat -o wide --watch

# 3. Inspeksi log keluaran standard
kubectl logs alpine-heartbeat -c sleeper
```

---

### 8. Practical Example
Berikut adalah konfigurasi Pod level produksi (*production-grade*) yang mencakup:
1. Batasan isolasi komputasi eksplit (`resources`).
2. Manajemen siklus hidup melalui `startupProbe`, `livenessProbe`, dan `readinessProbe`.
3. Penguatan keamanan kontainer (*security context* non-root, *drop all capabilities*).
4. Penanganan terminasi anggun (*graceful shutdown*).

```yaml
# pod-production.yaml
apiVersion: v1
kind: Pod
metadata:
  name: payment-processor-api
  namespace: core-banking
  labels:
    app.kubernetes.io/name: payment-processor
    app.kubernetes.io/part-of: transaction-engine
    app.kubernetes.io/version: "2.4.1"
spec:
  terminationGracePeriodSeconds: 60
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    runAsGroup: 10001
    fsGroup: 10001
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: api-server
    image: payment-registry.internal/finance/api:v2.4.1
    imagePullPolicy: IfNotPresent
    ports:
    - containerPort: 8080
      name: http-traffic
      protocol: TCP
    resources:
      requests:
        cpu: "500m"        # 0.5 vCPU reserved
        memory: "512Mi"    # 512 Megabytes reserved
      limits:
        cpu: "1000m"       # Max 1 vCPU (throttled beyond this)
        memory: "1024Mi"   # Max 1024 MiB (OOMKilled beyond this)
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
        - ALL
    # Validasi bahwa aplikasi selesai bootstrapping sebelum probe lain aktif
    startupProbe:
      httpGet:
        path: /healthz/startup
        port: 8080
      failureThreshold: 30
      periodSeconds: 2
    # Memverifikasi apakah kontainer masih responsif; jika gagal -> restart kontainer
    livenessProbe:
      httpGet:
        path: /healthz/liveness
        port: 8080
      initialDelaySeconds: 0
      periodSeconds: 10
      timeoutSeconds: 2
      failureThreshold: 3
    # Menentukan apakah kontainer siap menerima traffic; jika gagal -> copot dari routing IP
    readinessProbe:
      httpGet:
        path: /healthz/readiness
        port: 8080
      initialDelaySeconds: 0
      periodSeconds: 5
      timeoutSeconds: 2
      failureThreshold: 2
    volumeMounts:
    - name: ephemeral-storage
      mountPath: /tmp
  volumes:
  - name: ephemeral-storage
    emptyDir:
      sizeLimit: 128Mi
```

---

### 9. Edge Cases & Failure Modes

#### A. Split-Brain pada etcd Cluster
- **Penyebab**: Partisi jaringan memutus komunikasi antar node `etcd`.
- **Dampak**: Jika kuorum ($N/2 + 1$) tidak terpenuhi pada partisi minoritas, penulisan state baru akan diblokir total (mode *read-only* atau error `etcdserver: request timed out`). Control plane lumpuh untuk mutasi sumber daya.
- **Mitigasi**: Pastikan jumlah instance `etcd` selalu ganjil ($3, 5$) dan distribusikan melintasi *availability zones* (AZ) yang berbeda dengan latensi $\le 10\text{ ms}$.

#### B. PLEG (Pod Lifecycle Event Generator) Is Not Healthy
- **Penyebab**: `kubelet` menggunakan PLEG untuk memeriksa status runtime via RPC secara berkala. Jika runtime kontainer memblokir I/O disk (misal: Docker/containerd hang karena I/O deadlock atau CPU node 100%), PLEG akan *timeout*.
- **Dampak**: Node ditandai `NotReady`. Pod mulai dievakuasi oleh controller manager setelah `node-monitor-grace-period` (default 40 detik), memicu efek domino *thundering herd* pada node lain.
- **Mitigasi**: Pisahkan partisi I/O disk root sistem dengan direktori kerja runtime (`/var/lib/containerd`), atur `system-reserved` dan `kube-reserved`.

#### C. Scheduler Thundering Herd & Node Affinity Deadlock
- **Penyebab**: Serentetan Pod dalam jumlah ribuan di-deploy bersamaan dengan aturan hard anti-affinity (`topologyKey: kubernetes.io/hostname`).
- **Dampak**: `kube-scheduler` mengalami lonjakan siklus komputasi O($N \times P$) di mana $N$=nodes, $P$=pods. Tidak ada pod yang dapat ditempatkan jika jumlah node < replika pod, menghasilkan kondisi pods tersangkut permanen di state `Pending`.

---

### 10. Performance & Resource Considerations

#### Latensi Skalabilitas API Server
Komunikasi Kubernetes mengandalkan HTTP/2 Streams. Ketika ribuan komponen melakukan `WATCH` secara serentak tanpa proteksi, memory footprint `kube-apiserver` meningkat tajam.
- Gunakan **API Priority and Fairness (APF)** untuk mengisolasi traffic administratif penting dari traffic batch monitoring.
- Hindari listing objek tanpa pembatasan ukuran:
  ```bash
  # BURUK: Mengambil 50,000 pod sekaligus akan membekukan garbage collector APIServer
  kubectl get pods --all-namespaces

  # LEBIH BAIK: Gunakan limit chunks
  kubectl get pods --all-namespaces --chunk-size=500
  ```

#### Algoritma Evaluasi Sumber Daya (CFS Bandwidth & OOM)
- **CPU**: Merupakan *compressible resource*. Jika limit CPU terlampaui, Linux Kernel CFS (*Completely Fair Scheduler*) akan memangkas (*throttle*) alokasi waktu eksekusi CPU kontainer melalui cgroup `cpu.cfs_quota_us`. Hal ini memicu lonjakan p99 latency secara dramatis.
- **Memory**: Merupakan *uncompressible resource*. Jika memori Pod melampaui `limits.memory`, Linux Kernel OOM Killer akan langsung mematikan proses utama kontainer dengan exit code `137` (`SIGKILL`).

---

### 11. Security Implications

```
+---------------------------------------------------------------------------------+
| STRUKTUR PERTAHANAN MENDALAM KUBERNETES (4C SECURITY)                           |
|                                                                                 |
| 1. Cloud / Hardware : Hardware isolation, IAM, Private VPC                      |
| 2. Cluster          : API Server Authentication, RBAC, etcd Encryption at Rest  |
| 3. Container        : Read-only FS, RunAsNonRoot, Drop Capabilities, Seccomp    |
| 4. Code             : SAST/DAST, Vulnerability Scanning, Memory-safe coding     |
+---------------------------------------------------------------------------------+
```

#### Vektor Serangan & Eskalasi:
1. **Unauthenticated API Access / Insecure Port (Legacy 8080)**:
   - *Vektor*: Konfigurasi salah yang membuka port insecure pada `kube-apiserver`.
   - *Dampak*: Penyerang mendapatkan kontrol penuh klaster (*Cluster-Admin*) tanpa audit log.
   - *Pencegahan*: Hapus total parameter `--insecure-port` (secara default dinonaktifkan pada versi modern).

2. **Privileged Container Escape**:
   - *Vektor*: Menjalankan pod dengan `securityContext.privileged: true` atau men-share host namespace (`hostPID: true`, `hostIPC: true`).
   - *Dampak*: Kontainer dapat melihat proses host OS, keluar dari cgroups via manipulasi file `/sys` atau `/dev`, mengakses memori proses lain, dan mengambil alih node sepenuhnya.
   - *Pencegahan*: Terapkan Admission Controller standar **Pod Security Admission (PSA)** dengan profil `restricted`.

3. **Kompromi etcd Unencrypted**:
   - *Vektor*: Komunikasi etcd tanpa mTLS atau media penyimpanan etcd tanpa enkripsi (*unencrypted volume*).
   - *Dampak*: Secret klaster (termasuk private key, database passwords) disimpan secara default dalam bentuk plain Base64 di etcd.
   - *Pencegahan*: Aktifkan `EncryptionConfiguration` pada `kube-apiserver` menggunakan provider `aescbc` atau KMS External Plugin.

---

### 12. Trade-offs & Alternatives

| Dimensi | Kubernetes Asli | HashiCorp Nomad | Docker Swarm |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Operasional** | **Sangat Tinggi**. Memerlukan pengelolaan 7+ microservices internal, sertifikat PKI berlapis, etcd tuning. | **Rendah-Sedang**. Berupa biner tunggal (single binary) untuk master/client, konsensus terpadu. | **Sangat Rendah**. Terintegrasi langsung dalam Docker engine daemon. |
| **Batas Skalabilitas** | **Tinggi**. Diuji hingga 5.000 Node dan 150.000 Pod per klaster tunggal. | **Sangat Tinggi**. Terbukti dapat diskalakan hingga 10.000+ Node dalam klaster tunggal secara efisien. | **Rendah**. Degradasi performa drastis ketika mendekati skala 1.000 Node. |
| **Ekosistem & Extensibility**| **Standar De Facto**. Dukungan CNI, CSI, CRI ekstensif; ekosistem Operator, Helm, dan GitOps masif. | **Sedang**. Sangat baik untuk non-kontainer (legacy binary), tetapi ekosistem add-on terbatas. | **Minimal**. Pengembangan fitur resmi telah stagnan; variasi integrasi pihak ketiga rendah. |
| **Konsumsi Resource Idle** | ~2–4 GB RAM per instance Control Plane dasar. | ~100–300 MB RAM untuk proses server. | < 100 MB RAM tambahan di atas Docker. |

---

### 13. Best Practices (DOs and DON'Ts)

#### DOs:
- **Eksplisit Menentukan Requests & Limits**: Tetapkan alokasi sumber daya untuk CPU dan Memori pada setiap manifest kontainer guna menghindari skenario *noisy-neighbor*.
- **Konfigurasikan Probes dengan Toleransi Tinggi**: Hindari probe agresif (`failureThreshold: 1`, `timeoutSeconds: 1`). Berikan jeda startup yang cukup via `startupProbe` untuk mencegah *crash-looping* prematur saat sistem sibuk.
- **Pisahkan Failure Domains**: Jalankan node worker pada minimal 3 Availability Zones (*multi-AZ*) dengan topologi toleran: `topologySpreadConstraints`.
- **Gunakan Read-Only Root Filesystem**: Amankan kontainer dengan `readOnlyRootFilesystem: true`, dan arahkan operasi penulisan sementara secara eksklusif ke `emptyDir`.

#### DON'Ts:
- **Jangan Menggunakan Tag `:latest`**: Tag mutable merusak determinisme deployment, membuat verifikasi audit mustahil, dan mempersulit proses rollback. Selalu kunci dengan semantic versioning (`:v1.2.3`) atau digest SHA-256 (`@sha256:...`).
- **Jangan Menjalankan Pod Standalone di Produksi**: Jangan mendefinisikan Pod telanjang (*naked pod*) tanpa controller (seperti `Deployment` atau `StatefulSet`). Pod standalone tidak akan dijadwalkan ulang (*auto-rescheduled*) saat terjadi crash fisik pada node host.
- **Jangan Memberikan Akses Root**: Hindari `runAsUser: 0`. Pengambilalihan proses di dalam kontainer yang berjalan sebagai root berpotensi mengeksploitasi celah kernel untuk menembus isolasi node host.

---

### 14. Common Anti-Patterns

#### Anti-Pattern: Menggunakan `livenessProbe` yang Menghubungi Dependensi Eksternal
- **Bentuk Salah**:
  Sebuah endpoint `/healthz` yang digunakan oleh `livenessProbe` menguji koneksi langsung ke PostgreSQL database atau Redis cache.
- **Mengapa ini Terjadi**:
  Kesalahpahaman bahwa healthcheck harus mengukur fungsionalitas end-to-end secara menyeluruh.
- **Dampak Buruk**:
  Ketika database mengalami degradasi atau overload sementara, *seluruh* pod aplikasi serentak gagal pada probe-nya. `kubelet` merestart semua kontainer di seluruh klaster sekaligus. Hal ini menghasilkan badai koneksi baru (*cascading failure / retry storm*) yang memperparah kegagalan database.
- **Solusi Benar**:
  Gunakan `livenessProbe` hanya untuk menguji integritas internal proses Pod itu sendiri (apakah runtime hang/deadlock). Gunakan `readinessProbe` untuk menguji ketergantungan downstream jika routing traffic memang harus dihentikan saat database tak terjangkau.

---

### 15. Troubleshooting & Debugging Guide

```
+-----------------------------------------------------------------------------------+
| ALUR PENGAMBILAN KEPUTUSAN DIAGNOSTIK POD (TRIAGE HEURISTIC)                      |
+-----------------------------------------------------------------------------------+
                               |
                               v
                     [Status Pod: Pending?]
                         /         \
                 (YA)   /           \  (TIDAK)
                       v             v
       [kubectl describe pod]    [Status: CrashLoopBackOff?]
        Periksa Events:                 /           \
        - Insufficient cpu      (YA)   /             \  (TIDAK)
        - Insufficient memory         v               v
        - FailedScheduling    [kubectl logs --previous]   [Status: Evicted / OOMKilled?]
                               Periksa stack trace          /            \
                               & konfigurasi runtime (YA)  /              \
                                                          v                v
                                              [Cek exit code 137]   [Cek Readiness Probe]
                                              Naikkan limits memory Periksa target port
```

#### Perintah-Perintah Investigasi Kritis:
```bash
# 1. Mendapatkan event berurutan secara kronologis di namespace target
kubectl get events --sort-by='.metadata.creationTimestamp' -n <namespace>

# 2. Memeriksa detail manifest state, konfigurasi kontroler, dan kegagalan probe
kubectl describe pod <pod-name> -n <namespace>

# 3. Membaca log dari kontainer yang mengalami crash pada iterasi sebelumnya
kubectl logs <pod-name> -c <container-name> --previous

# 4. Membuka sesi shell interaktif di dalam cgroup namespace kontainer yang berjalan
kubectl exec -it <pod-name> -c <container-name> -- /bin/sh

# 5. Menjalankan debug container temporer yang menempel pada network/process namespace pod target
kubectl debug -it pod/<pod-name> --image=nicolaka/netshoot --target=<container-name>
```

---

### 16. Real-World Case Study

#### Skenario Insiden:
Pada periode *flash sale* Black Friday, sebuah platform e-commerce mengalami pemadaman total (*total outage*) pada klaster Kubernetes produksi (300 node, 4.000 pod) selama 42 menit. 

#### Gejala Awal:
`kubectl` mengembalikan respons `Error from server (Timeout)`. Metrik monitoring menunjukkan node-node bergantian berubah status antara `Ready` dan `NotReady`.

#### Proses Triage & Investigasi:
1. SRE memeriksa log master node: CPU pada node yang menjalankan `kube-apiserver` berada pada utilisasi 100%.
2. Log `kube-apiserver` mencatat ribuan HTTP 429 (Too Many Requests) dan koneksi terputus ke `etcd`.
3. Metrik latensi commit `etcd` melonjak dari $2\text{ ms}$ menjadi $1.800\text{ ms}$. Disk *fdatasync* latensi mencapai tingkat yang sangat lambat.
4. Akar masalah (*Root Cause Analysis*): 
   - Sebuah mikroservis analitik yang baru di-deploy menjalankan skrip penyesuaian skala internal kustom yang mengeksekusi `kubectl get pods --all-namespaces` setiap 2 detik tanpa batas limit atau cache.
   - Pada saat bersamaan, `etcd` berbagi volume blok storage IOPS-rendah yang sama dengan direktori logging host. Beban serialisasi JSON masif dari query controller kustom tersebut melumpuhkan IOPS disk etcd. Hal ini memicu hilangnya *heartbeat* Raft antar peer etcd, menyebabkan proses pemilihan *leader* (leader election) berulang-ulang yang menghentikan pemrosesan klaster secara total.

#### Solusi & Remediasi:
1. **Tindakan Darurat**: Mengisolasi *firewall* untuk memblokir IP controller kustom analitik, merestart proses biner `etcd`, dan membatasi traffic ingress API.
2. **Perbaikan Jangka Panjang**:
   - Memindahkan data direktori `etcd` (`/var/lib/etcd`) ke disk fisik dedicated berbasis NVMe SSD lokal dengan IOPS terisolasi.
   - Menerapkan arsitektur **API Priority and Fairness (APF)** dengan konfigurasi *FlowSchema* ketat guna membatasi jumlah *concurrent requests* untuk `list` operasi berskala besar.
   - Menghapus izin RBAC `list` pods secara klaster-wide untuk service account non-esensial.

---

### 17. Verification & Testing
Gunakan skrip validasi Bash berikut untuk memverifikasi fungsionalitas dan ketahanan klaster Kubernetes secara otomatis:

```bash
#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="cluster-verification-test"

echo "=== [1/4] Menginisialisasi Namespace Pengujian ==="
kubectl create namespace "${NAMESPACE}" || true

echo "=== [2/4] Menerapkan Pod Uji Validasi ==="
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: validation-agent
  namespace: ${NAMESPACE}
spec:
  containers:
  - name: tester
    image: busybox:1.36.1
    command: ["sh", "-c", "sleep 3600"]
    resources:
      limits:
        memory: "64Mi"
        cpu: "100m"
      requests:
        memory: "32Mi"
        cpu: "50m"
EOF

echo "=== [3/4] Menunggu Status Running (Timeout 60s) ==="
kubectl wait --namespace="${NAMESPACE}" \
  --for=condition=Ready pod/validation-agent \
  --timeout=60s

echo "=== [4/4] Memverifikasi Isolasi Namespace & DNS Resolution ==="
RESOLVE_OUT=$(kubectl exec -n "${NAMESPACE}" validation-agent -- nslookup kubernetes.default.svc.cluster.local)

if echo "${RESOLVE_OUT}" | grep -q "Address"; then
  echo ">> SUCCESS: Komponen Kubelet, Container Runtime, CNI, dan CoreDNS Berfungsi Optimal."
else
  echo ">> FAILURE: CoreDNS atau CNI Datapath Mengalami Anomali."
  exit 1
fi

echo "=== Pembersihan Sumber Daya Pengujian ==="
kubectl delete namespace "${NAMESPACE}" --grace-period=0 --force
```

---

### 18. Enterprise Integration Patterns
Dalam topologi berskala perusahaan (*enterprise scale*), klaster tidak beroperasi secara terisolasi, melainkan terhubung ke ekosistem operasional terpusat:

```
                                          +---------------------------------------+
                                          | Enterprise Identity (Okta/Active Dir) |
                                          +-------------------+-------------------+
                                                              |
                                                              v (OIDC Tokens)
+------------------------+  Signed Manifests  +---------------+-------------------+
| GitOps Engine (ArgoCD) |------------------->|       kube-apiserver              |
+------------------------+                    +---------------+-------------------+
                                                              |
                              +-------------------------------+-------------------------------+
                              v (Audit Webhook Logs)                                          v (OpenTelemetry)
               +--------------+--------------+                                 +--------------+--------------+
               | SIEM Engine (Splunk / ELK)  |                                 | Observability (Prometheus)  |
               +-----------------------------+                                 +-----------------------------+
```

1. **Authentication Interceptor Pattern (OIDC/LDAP)**:
   `kube-apiserver` dikonfigurasi menggunakan flag `--oidc-issuer-url` dan `--oidc-client-id` untuk mengalihkan validasi identitas ke Enterprise Identity Provider (seperti Okta, Keycloak, atau Azure Active Directory). Akses tidak pernah diberikan melalui sertifikat x509 statis untuk pengguna personal.
2. **Continuous Audit Streaming**:
   Setiap mutasi (POST/PUT/PATCH/DELETE) di-stream melalui audit webhook berformat JSON secara asinkron ke SIEM terpusat (Splunk, Elastic) untuk memenuhi standar kepatuhan regulasi industri finansial (misal: PCI-DSS, SOC2 Type II).
3. **Declarative State Synchronization (GitOps)**:
   Akses langsung manusia (`kubectl`) ke lingkungan produksi dinonaktifkan total. GitOps Operator (seperti ArgoCD atau Flux) menjadi satu-satunya entitas mesin yang memiliki akses tulis ke klaster, menarik representasi state deklaratif yang telah diaudit langsung dari repositori Git.

---

### 19. Key Takeaways
- **Reconciliation Engine**: Kubernetes bukanlah eksekutor imperatif statis; sistem ini adalah *reconciliation engine* yang terus-menerus mencocokkan *current state* dengan *desired state*.
- **etcd sebagai Single Source of Truth**: Seluruh operasi orkestrasi bersifat *stateless* di level controller dan *stateful* hanya di level `etcd`. Kehilangan konsensus Raft pada `etcd` berarti melumpuhkan fungsi manajemen seluruh klaster.
- **Independence & Decoupling**: Komponen inti Kubernetes tidak saling memanggil secara langsung; seluruh koordinasi terjadi melalui event-stream deklaratif via `kube-apiserver`.
- **Enforcement Boundaries**: Pod adalah unit eksekusi terkecil, namun pod hanyalah abstraksi logical untuk sekumpulan *Linux cgroups* dan *namespaces* yang dikontrol melalui interaksi antara `kubelet`, `CRI`, dan kernel.
- **Fail-Safe Design**: Kegagalan perangkat keras dan perangkat lunak adalah sebuah keniscayaan. Sistem orkestrasi dirancang untuk menangani kegagalan tersebut melalui isolasi ketat, probes, deklarasi sumber daya, dan strategi mitigasi cascade failure.

---

### 20. Next Steps & References
Untuk memperdalam pemahaman mengenai siklus lanjutan pada kurikulum ini:
- **Modul Berikutnya**: Lanjutkan ke **Bab 01 Module 02: "Model Objek Kubernetes, Workload Controllers, & Advanced Scheduling"** untuk membedah controller internal (`Deployment`, `DaemonSet`, `StatefulSet`) dan algoritma *taints-tolerations*.
- **Spesifikasi & Rujukan Inti**:
  - [Kubernetes Documentation: Cluster Architecture](https://kubernetes.io/docs/concepts/architecture/)
  - [The Raft Consensus Algorithm (Ongaro & Ousterhout)](https://raft.github.io/raft.pdf)
  - [Linux Kernel Documentation: Control Groups v2 (cgroupv2)](https://docs.kernel.org/admin-guide/cgroup-v2.html)
  - [OCI Runtime Specification (Open Container Initiative)](https://github.com/opencontainers/runtime-spec)