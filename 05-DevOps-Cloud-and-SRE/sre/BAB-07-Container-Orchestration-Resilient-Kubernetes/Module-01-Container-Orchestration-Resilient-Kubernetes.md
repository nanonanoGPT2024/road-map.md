# Modul 01: Container Orchestration & Resilient Kubernetes Operations

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonfigurasi dan memvalidasi **Pod Disruption Budgets (PDB)** untuk menjaga ketersediaan layanan selama *voluntary disruptions* (misal: node drain, cluster upgrade).
- Menjalankan prosedur **Node Drain & Graceful Eviction** tanpa *downtime* dengan mengintegrasikan *preStop lifecycle hooks* dan `terminationGracePeriodSeconds`.
- Mengonfigurasi dan melakukan *fine-tuning* pada **Startup, Liveness, dan Readiness Probes** guna mencegah insiden *cascading restart* dan *premature traffic routing*.
- Melakukan investigasi, mitigasi, dan remediasi insiden **OOMKilled (Exit Code 137)** serta *CPU Throttling* melalui *sizing* **Resource Requests & Limits** yang presisi berdasarkan kelas *Quality of Service* (QoS).
- Mengelola ketahanan *Control Plane* Kubernetes melalui mekanisme *quorum calculation*, backup, dan prosedur pemulihan bencana (**etcd snapshot & restore**).
- Mengimplementasikan **Taints, Tolerations, dan PriorityClasses** untuk melindungi *node* kritis dan memastikan beban kerja infrastruktur terisolasi dengan aman.

---

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Konsep dasar Linux namespaces, cgroups (v1 dan v2), dan container runtime (containerd/CRI-O).
- Arsitektur dasar Kubernetes: peran kube-apiserver, kube-scheduler, kube-controller-manager, kubelet, dan etcd.
- Penggunaan dasar `kubectl` (apply, get, describe, logs, exec).
- Dasar-dasar protokol jaringan TCP/HTTP dan mekanisme penanganan sinyal UNIX (`SIGTERM`, `SIGKILL`).
- Teorema CAP dan konsep dasar konsensus Raft terdistribusi.

---

## 3. Concept
Kubernetes bukan sekadar platform orkestrasi kontainer, melainkan sebuah mesin *declarative reconciliation loop* terdistribusi. Keandalan (*resiliency*) di dalam Kubernetes tidak terjadi secara otomatis. Sistem ini mengabstraksi perangkat keras fisik menjadi kumpulan sumber daya logis, tetapi tetap tunduk pada batasan fisik: memori dapat habis, thread CPU dapat tercekik (*throttled*), node komputasi dapat gagal secara tiba-tiba (*involuntary disruption*), atau harus dimatikan untuk pemeliharaan rutin (*voluntary disruption*).

Resiliensi operasional Kubernetes adalah kemampuan klaster untuk mempertahankan *Service Level Objectives* (SLO) ketersediaan dan latensi meskipun terjadi degradasi parsial pada level komputasi, jaringan, penyimpanan, atau komponen *control plane*.

---

## 4. Why
Dalam skala produksi:
- **Kegagalan Pemeliharaan**: Mengeksekusi `kubectl drain` pada node tanpa konfigurasi Pod Disruption Budget (PDB) dapat langsung menurunkan seluruh replika aplikasi stateless/stateful, memicu insiden downtime P1.
- **Micro-cascading Outages**: Konfigurasi *Liveness Probe* yang terlalu agresif (misal: timeout 1 detik dengan threshold kegagalan 3 kali pada endpoint yang bergantung pada database) akan membunuh kontainer yang sedang mengalami lonjakan beban (*traffic spike*), memperparah degradasi menjadi pemadaman total (*thundering herd*).
- **Silent Degradation**: Kesalahan estimasi CPU Limits memicu *Completely Fair Scheduler (CFS) quota throttling*, membuat latensi P99 melesat dari 50ms ke 3.000ms tanpa adanya error eksplisit di log aplikasi.
- **Bencana Katastropik State**: Kehilangan korum etcd pada multi-master control plane menghentikan operasi read/write API server, melumpuhkan orkestrasi, dan membuat status klaster membeku. Tanpa snapshot teruji, klaster harus dibangun ulang secara manual dari nol.

---

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 Pod Disruption Budgets (PDB)
PDB membatasi jumlah Pod yang boleh nonaktif secara bersamaan selama *voluntary disruptions* (misal: `kubectl drain`, eskalasi node oleh Cluster Autoscaler, atau upgrade AMI/OS node).
- **`minAvailable`**: Jumlah minimum Pod yang harus tetap berstatus `Ready`. Bisa berupa angka absolut (misal: `2`) atau persentase (misal: `"60%"`).
- **`maxUnavailable`**: Jumlah maksimum Pod yang boleh tidak tersedia dari total replika target.
- **Mekanisme Kerja**: Kube-apiserver menggunakan sub-resource `/eviction`. Ketika proses drain memanggil eviction API, API server memeriksa PDB. Jika penggusuran pod melanggar batasan `minAvailable` atau `maxUnavailable`, API server menolak panggilan dengan status HTTP `429 Too Many Requests`.
- PDB **tidak melindungi** dari *involuntary disruptions* (kernel panic, hardware failure, VM preemption oleh cloud provider).

### 5.2 Node Drain & Graceful Eviction Lifecycle
Ketika proses `kubectl drain <node-name>` dipanggil:
1. Node ditandai sebagai `Unschedulable` (*cordoned*).
2. Controller Eviction mengirim sinyal penggusuran ke pod target.
3. Kubelet pada node menerima perintah terminasi dan mengeksekusi tahapan berikut:
   - Pod dihapus dari endpoint service/Ingress (Readiness gate bernilai false).
   - Eksekusi lifecycle hook `preStop` (jika didefinisikan). Eksekusi bersifat sinkron dan memblokir pengiriman sinyal berikutnya.
   - Sinyal `SIGTERM` dikirim ke PID 1 kontainer.
   - Kubelet menunggu hingga pod berhenti atau durasi `terminationGracePeriodSeconds` (default: 30 detik) habis.
   - Jika durasi habis dan pod belum keluar, kubelet mengirim sinyal `SIGKILL` paksa.

### 5.3 Probes Fine-Tuning
Kubernetes menyediakan tiga tipe probe yang dijalankan kubelet secara periodik:
- **Startup Probe**: Menentukan apakah aplikasi di dalam kontainer sudah selesai diinisialisasi. Selama startup probe belum sukses, liveness dan readiness probe dinonaktifkan. Sangat krusial untuk aplikasi legacy atau JVM yang membutuhkan waktu bootstrapping lama (30–120 detik).
- **Readiness Probe**: Menentukan apakah pod siap menerima lalu lintas jaringan. Jika gagal, pod tidak dibunuh, melainkan IP pod dicabut dari endpoint Service.
- **Liveness Probe**: Menentukan apakah kontainer perlu direstart. Jika gagal sebanyak `failureThreshold`, kubelet langsung menghentikan kontainer dan mengeksekusi restart policy.
- **Parameter Kritis**:
  - `initialDelaySeconds`: Penundaan sebelum probe pertama dieksekusi.
  - `periodSeconds`: Frekuensi eksekusi probe.
  - `timeoutSeconds`: Batas waktu respon probe dianggap gagal (default 1 detik; harus dinaikkan jika jaringan node padat).
  - `failureThreshold`: Toleransi jumlah kegagalan berturut-turut sebelum aksi diambil.
  - `successThreshold`: Jumlah keberhasilan berturut-turut agar probe dianggap sehat kembali.

### 5.4 OOMKilled Remediation & Resource Sizing
Ketika kontainer melebihi alokasi memorinya, kernel Linux memicu *Out of Memory (OOM) Killer*. Kubelet mendeteksi status exit code `137` (`128 + SIGKILL (9)`).
- **cgroups v1 vs cgroups v2**: Pada cgroups v1, OOM Killer mengeksekusi proses berdasarkan perhitungan `oom_score_adj`. Pada cgroups v2, kontrol memori jauh lebih halus melalui interface `memory.high` (throttling/reclaim) dan `memory.max` (hard limit pemicu OOM).
- **Runtime Sizing (JVM & Go)**:
  - Go runtime: Wajib menetapkan `GOMEMLIMIT` (umumnya 85-90% dari container memory limit) dan `GOMAXPROCS` agar garbage collector dan runtime scheduler tidak membaca kapasitas memori/CPU fisik node host.
  - JVM: Gunakan flag `-XX:MaxRAMPercentage=75.0` dan `-XX:InitialRAMPercentage=75.0` untuk mencegah JVM heap meluap keluar dari batas cgroup.
- **QoS Classes**:
  - **Guaranteed**: `requests == limits` untuk semua kontainer (CPU dan Memory). Pod ini memiliki prioritas tertinggi dan `oom_score_adj = -997`. Terakhir digusur saat node kehabisan memori.
  - **Burstable**: `requests < limits`. Pod memiliki prioritas menengah (`oom_score_adj` dihitung proporsional terhadap penggunaan memori).
  - **BestEffort**: Tidak mendefinisikan requests dan limits sama sekali. Memiliki prioritas terendah (`oom_score_adj = 1000`). Menjadi korban pertama penggusuran (*eviction*) ketika node mengalami *node-pressure*.

### 5.5 Control Plane Resiliency (etcd Quorum & Recovery)
etcd adalah *distributed consistent key-value store* yang menggunakan algoritma konsensus Raft.
- **Korum ($Q$)**: Dihitung dengan rumus:
  $$Q = \left\lfloor \frac{N}{2} \right\rfloor + 1$$
  Untuk $N = 3$, $Q = 2$ (toleransi 1 node mati).
  Untuk $N = 5$, $Q = 3$ (toleransi 2 node mati).
  Jumlah ganjil wajib dipertahankan untuk menghindari skenario *split-brain*.
- **Snapshot & Restore**: Pemulihan etcd bersifat destruktif. Semua anggota klaster harus dihentikan, direktori data etcd lama harus dikosongkan, lalu snapshot di-*restore* secara konsisten dengan konfigurasi inisialisasi klaster baru (`--initial-cluster`, `--initial-cluster-token`).

### 5.6 Critical Node Taint Management
Taints diterapkan pada Node untuk mencegah Pod yang tidak memiliki Toleration dijadwalkan pada node tersebut.
- **Taint Effects**:
  - `NoSchedule`: Pod baru tanpa toleration tidak akan dijadwalkan. Pod lama tetap berjalan.
  - `PreferNoSchedule`: Scheduler berusaha menghindari penempatan pod, tetapi tidak absolut.
  - `NoExecute`: Pod baru ditolak, dan Pod lama yang sudah berjalan di node akan langsung diusir (*evicted*) jika tidak memiliki toleration yang cocok.
- **PriorityClass**: Pod dengan PriorityClass bernilai tinggi (misal: `system-node-critical` atau `system-cluster-critical`) dapat melakukan *preemption* terhadap pod bernilai lebih rendah saat sumber daya node habis.

---

## 6. How
1. **Penerapan PDB**: Tetapkan PDB pada setiap deployment produksi berbasis ketersediaan quorum.
2. **Pola Graceful Eviction**:
   - Pasang hook `preStop` dengan sleep 5–15 detik untuk membiarkan kube-proxy/Ingress controller mencabut IP Pod dari tabel routing sebelum kontainer menerima `SIGTERM`.
   - Pastikan aplikasi menangani `SIGTERM` dengan menyelesaikan request aktif (*in-flight requests*).
3. **Konfigurasi Probes Bertingkat**:
   - Gunakan *Startup Probe* dengan `failureThreshold` tinggi untuk fase bootstrap lambat.
   - Konfigurasi *Readiness Probe* yang mengecek dependensi lokal internal, bukan external database yang dapat memicu kegagalan berantai.
   - Konfigurasi *Liveness Probe* yang hanya mengecek kondisi deadlock atau thread starvation.
4. **Alokasi Sumber Daya Rasional**:
   - Hilangkan CPU Limit untuk aplikasi latency-sensitive (gunakan hanya CPU Request) atau gunakan automated throttling remediation untuk menghindari penalti CFS Quota.
   - Pasang Memory Request sama dengan Memory Limit jika aplikasi dialokasikan untuk QoS `Guaranteed`.
5. **Manajemen etcd**:
   - Jadwalkan cronjob `etcdctl snapshot save` per jam yang diunggah ke object storage terpisah (misal: S3 / GCS).
   - Pasang monitoring latency disk write (`backend_commit_duration_seconds`) pada etcd.

---

## 7. Analogy
Bayangkan sebuah bandara internasional:
- **Node Drain**: Penutupan salah satu landasan pacu untuk pengaspalan ulang.
- **Pod Disruption Budget (PDB)**: Regulasi otoritas penerbangan yang menyatakan minimal 3 landasan pacu harus tetap beroperasi setiap saat. Jika kontraktor mencoba menutup landasan ke-4, sistem melarang penutupan tersebut secara hukum.
- **preStop & Graceful Termination**: Peringatan ATC kepada pesawat yang sedang dalam pendekatan akhir (*final approach*) untuk mendarat dan menurunkan penumpang sebelum gerbang boarding dikunci total.
- **Liveness vs Readiness Probe**:
  - *Readiness Probe*: Pemeriksaan apakah pintu gerbang siap menerima antrean penumpang baru. Jika petugas belum siap, boarding ditunda sementara tanpa membakar terminal.
  - *Liveness Probe*: Pemeriksaan apakah terjadi kebakaran di menara ATC. Jika ya, evakuasi dan bangun ulang operasi (*restart*).
- **OOMKilled**: Pelanggaran batas muatan bagasi pesawat. Sistem tidak membuang sebagian muatan; sistem langsung membatalkan seluruh penerbangan dan menyita pesawat karena membahayakan integritas bandara.

---

## 8. Diagram (ASCII)

```
Proses Graceful Termination & Drain Lifecycle
=============================================

Operator CLI              Control Plane              Kubelet (Node A)             Container Pod
    |                           |                           |                           |
    |--- kubectl drain NodeA -->|                           |                           |
    |                           |-- Check PDB Constraints   |                           |
    |                           |   [Status: Allowed]       |                           |
    |                           |-- Evict Pod ------------->|                           |
    |                           |                           |                           |
    |                           |<-- Remove from Endpoints -|                           |
    |                           |    (Traffic stops)        |                           |
    |                           |                           |--- Exec preStop Hook ---->|
    |                           |                           |    (e.g., sleep 10s)      | [In-flight reqs]
    |                           |                           |                           | [finishing...]
    |                           |                           |<-- Hook Finished ---------|
    |                           |                           |                           |
    |                           |                           |--- SIGTERM (PID 1) ------>|
    |                           |                           |                           | [Graceful shutdown]
    |                           |                           |   terminationGracePeriod  |
    |                           |                           |   Countdown Running...    |
    |                           |                           |                           |
    |                           |                           |   [If process exits]      |
    |                           |                           |<-- Container Exit 0 ------|
    |                           |                           |                           |
    |                           |                           |   [If timeout expires]    |
    |                           |                           |--- SIGKILL --------------->
    |                           |                           |                           |
    |                           |<-- Node Drain Finished ---|                           |
    |<-- Drain Complete --------|                           |                           |
```

---

## 9. Simple Example
Sebuah konfigurasi Pod Disruption Budget minimal untuk menjamin setidaknya 2 replika dari Deployment `payment-service` selalu berstatus `Ready`:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: payment-service-pdb
  namespace: core-banking
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: payment-service
```

Jika deployment memiliki 3 replika, operasi `kubectl drain` hanya diperbolehkan menggusur 1 pod dalam satu waktu. Pod kedua tidak akan digusur sebelum pod pengganti di node lain mencapai status `Ready`.

---

## 10. Practical Example (Konfigurasi CLI / YAML Production-Ready)

### 10.1 Resilient Microservice Deployment Specification
Manifest berikut mengimplementasikan `preStop`, Probe bertingkat, penyesuaian runtime Go, dan QoS `Guaranteed`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: checkout-api
  namespace: production
  labels:
    app.kubernetes.io/name: checkout-api
spec:
  replicas: 4
  selector:
    matchLabels:
      app.kubernetes.io/name: checkout-api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: checkout-api
    spec:
      terminationGracePeriodSeconds: 45
      containers:
      - name: checkout-api
        image: internal-registry.company.io/checkout-api:v2.4.1
        env:
        - name: GOMEMLIMIT
          value: "420MiB" # 85% dari memory limit 500Mi
        - name: GOMAXPROCS
          value: "1"
        resources:
          requests:
            cpu: "1000m"
            memory: "500Mi"
          limits:
            cpu: "1000m"
            memory: "500Mi"
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 10"]
        startupProbe:
          httpGet:
            path: /healthz/startup
            port: 8080
          initialDelaySeconds: 2
          periodSeconds: 3
          failureThreshold: 20 # Toleransi inisialisasi hingga 60s
          timeoutSeconds: 2
        readinessProbe:
          httpGet:
            path: /healthz/ready
            port: 8080
          periodSeconds: 5
          failureThreshold: 2
          timeoutSeconds: 2
        livenessProbe:
          httpGet:
            path: /healthz/live
            port: 8080
          periodSeconds: 10
          failureThreshold: 3
          timeoutSeconds: 2
```

### 10.2 Control Plane: etcd Snapshot & Taint Management CLI Commands

```bash
# 1. Mengambil Snapshot etcd dari node Control Plane yang aktif
ETCDCTL_API=3 etcdctl snapshot save /var/backups/etcd-snapshot-$(date +%Y%m%d_%H%M%S).db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

# 2. Verifikasi Integritas Snapshot
ETCDCTL_API=3 etcdctl --write-out=table snapshot status /var/backups/etcd-snapshot-*.db

# 3. Taint Node Khusus Workload Pembayaran (Hanya Pod toleran yang boleh dijadwalkan)
kubectl taint nodes worker-node-pci-01 dedicated=pci-workload:NoSchedule

# 4. Melakukan Cordon dan Graceful Drain pada Node Maintenance
kubectl cordon worker-node-04
kubectl drain worker-node-04 --ignore-daemonsets --delete-emptydir-data --pod-selector='app!=critical-state'
```

---

## 11. Real World Example
Pada sebuah perusahaan payment gateway dengan throughput 4.500 TPS, tim SRE menjadwalkan OS Kernel Patching di seluruh node worker klaster EKS. 

**Insiden Awal**: Tim langsung mengeksekusi `kubectl drain` otomatis via skrip pipeline parallel. Deployment API utama kehilangan 60% pod secara bersamaan karena ketiadaan PDB. Endpoint service mengalami banjir request pada pod yang tersisa, memicu *OOMKilled cascade*. Ketersediaan sistem turun menjadi 88% selama 14 menit (SLA breached).

**Solusi & Implementasi Pasca-Insiden**:
1. Mengunci ketersediaan dengan PDB: `maxUnavailable: 20%`.
2. Menambahkan `preStop` hook `sleep 15` untuk mengatasi *iptables sync propagation delay* pada kube-proxy.
3. Mengganti Liveness Probe yang sebelumnya memeriksa query `SELECT 1` ke PostgreSQL menjadi hanya memeriksa *in-memory health status* internal. Database connection pool drop tidak lagi membunuh kontainer.
4. Menambahkan script rolling-drain orchestration yang mengecek kesehatan PDB sebelum berpindah ke node berikutnya.

Hasil: Upgrade klaster berikutnya berjalan mulus dengan 0 kegagalan transaksi dan latensi P99 tetap stabil di bawah 45ms.

---

## 12. Trade-offs
| Pendekatan | Keuntungan | Kerugian / Risiko |
| :--- | :--- | :--- |
| **Strict PDB (`minAvailable: 100%`)** | Menjamin tidak ada penurunan kapasitas layanan akibat aktivitas maintenance. | Operasi `drain` akan **macet total (stuck)** jika ada 1 saja pod yang unready. Autoscaling node terhambat. |
| **QoS Guaranteed (`limits == requests`)** | Pod paling aman dari OOM Killer (`oom_score_adj = -997`); performa deterministik. | Pemborosan sumber daya komputasi (*resource stranded*) jika beban kerja memiliki pola traffic spike musiman. |
| **Peniadaan CPU Limits** | Menghilangkan CPU CFS Quota Throttling; latensi P99 sangat stabil. | Risiko pod nakal (*noisy neighbor*) memonopoli resource CPU node, mendegradasi pod lain di node yang sama. |
| **Aggressive Probes (`periodSeconds: 1`)** | Deteksi kegagalan sangat cepat (hitungan detik). | Membebani kubelet dan runtime aplikasi; risiko *false-positive alerts* tinggi saat ada jitter jaringan lokal. |

---

## 13. When To Use
- Terapkan **Pod Disruption Budget** pada seluruh aplikasi stateless multi-replika dan stateful clustering (misal: Redis, Kafka, Cassandra, Elasticsearch).
- Terapkan **preStop Hook** pada seluruh pod yang menerima traffic dari Service atau Ingress Controller.
- Terapkan **Startup Probe** jika aplikasi memerlukan waktu kompilasi JIT, warm-up cache, atau loading dataset machine learning ke memori sebelum melayani trafik.
- Terapkan **Node Taints** pada node khusus (GPU nodes, PCI-DSS compliant nodes, high-memory database worker).

---

## 14. When NOT To Use
- Jangan gunakan PDB dengan `minAvailable: 1` pada Deployment yang hanya memiliki `replicas: 1` (akan memblokir proses node drain secara permanen).
- Jangan arahkan endpoint Liveness Probe ke dependensi eksternal (database, cache Redis, atau downstream 3rd party API). Liveness probe **hanya** boleh memvalidasi status proses internal kontainer itu sendiri.
- Hindari menyetel `terminationGracePeriodSeconds` terlalu besar (>300 detik) untuk aplikasi stateless generik karena memperlambat siklus deployment CI/CD dan rolling update.

---

## 15. Common Mistakes
1. **PDB Deadlock**: Menyetel `minAvailable` sama dengan jumlah replika saat ini pada klaster tanpa kapasitas node tambahan untuk melakukan penyesuaian replikasi.
2. **Zombie Process pada PID 1**: Kontainer yang menggunakan shell script (`ENTRYPOINT ["/entrypoint.sh"]`) tanpa utility pengoper sinyal (`exec` atau `tini`), mengakibatkan `SIGTERM` tidak pernah sampai ke proses aplikasi, sehingga pod selalu mati via `SIGKILL` paksa setelah 30 detik.
3. **Miskonsepsi OOMKilled**: Mengira OOMKilled disebabkan oleh kebocoran memori aplikasi saja, padahal sering kali disebabkan oleh buffer kernel I/O atau limit heap runtime yang tidak memperhitungkan memory overhead non-heap (thread stack, metapool, native libraries).
4. **Single-Node etcd Disaster**: Membangun klaster Kubernetes multi-master tetapi seluruh control plane menunjuk ke 1 instans etcd yang sama.

---

## 16. Best Practices
1. **GOMEMLIMIT & JVM MaxRAMPercentage**: Selalu set konfigurasi memori runtime sebesar 75%–85% dari batas `resources.limits.memory`.
2. **Kombinasi Graceful Shutdown**:
   ```yaml
   lifecycle:
     preStop:
       exec:
         command: ["/bin/sh", "-c", "sleep 15"]
   ```
   Pastikan `terminationGracePeriodSeconds` disetel minimal 15–30 detik lebih lama dari durasi preStop sleep ditambah durasi internal application drain.
3. **Readiness vs Liveness Isolation**:
   - `/healthz/live` = Cek deadlock internal runtime / event loop.
   - `/healthz/ready` = Cek dependensi esensial lokal (local socket, warmup state).
4. **etcd Quorum Protection**: Gunakan topologi etcd eksternal atau stacked etcd dengan minimal 3 node master, dilengkapi automasi snapshot terenkripsi ke storage terpisah setiap interval waktu tetap.

---

## 17. Troubleshooting

### 17.1 Mendiagnosis Pod Terjebak OOMKilled (Exit Code 137)
Langkah inspeksi deterministik:
```bash
# 1. Cek Last State Pod
kubectl get pod checkout-api-798b6f5cb-x8z9l -n production -o jsonpath='{.status.containerStatuses[*].lastState.terminated}'

# 2. Analisis Kernel Ring Buffer pada Node tempat Pod berjalan
kubectl debug node/worker-node-02 -it --image=busybox -- dmesg -T | grep -E -i "oom[-_]killer|killed process"

# 3. Pantau Memory Usage vs Working Set secara Real-time
kubectl top pod checkout-api-798b6f5cb-x8z9l -n production --containers
```

### 17.2 Investigasi Node Drain Hang / Macet
Jika perintah `kubectl drain <node>` tidak kunjung selesai:
```bash
# 1. Cek Pod Disruption Budget yang memblokir
kubectl get pdb -A

# 2. Inspeksi Events pada namespace terkait
kubectl get events -n production --field-selector reason=FailedDrain
kubectl describe pdb payment-service-pdb -n production
```

### 17.3 Debugging CFS CPU Throttling
Mendeteksi apakah pod dicekik oleh scheduler Linux meskipun utilisasi CPU terlihat rendah:
```bash
# Eksekusi pada host node atau debug container
cat /sys/fs/cgroup/cpu,cpuacct/kubepods.slice/.../cpu.stat
# Perhatikan metrik:
# nr_periods (total period)
# nr_throttled (berapa periode yang terkena throttle)
# throttled_time (akumulasi waktu terbuang dalam nanodetik)
```

---

## 18. Exercise
1. Buat Deployment Nginx dengan 3 replika dan pasangkan konfigurasi PDB dengan batasan `minAvailable: 2`.
2. Terapkan hook `preStop` yang mencetak log timestamp lalu melakukan `sleep 10`.
3. Jalankan `kubectl drain` pada salah satu node dan amati log pod via streaming terminal untuk memvalidasi urutan penerimaan traffic, eksekusi hook, dan sinyal pemutusan.
4. Lakukan modifikasi memory limit kontainer menjadi `50Mi`, lalu paksa aplikasi mengalokasikan 100Mi via dummy script untuk memverifikasi munculnya status `OOMKilled` dan exit code `137`.

---

## 19. Challenge
Rancang arsitektur ketahanan klaster untuk aplikasi perbankan kritis:
- Bangun klaster multi-worker lokal (menggunakan Kind atau Minikube multi-node).
- Terapkan PriorityClass khusus `critical-banking` dengan value `1000000`.
- Konfigurasikan Custom Taint pada worker pool bertipe compute: `workload=highperf:NoSchedule`.
- Tulis manifest deployment yang memiliki Pod Anti-Affinity (mencegah 2 pod berjalan di node yang sama), Toleration terhadap taint di atas, Guaranteed QoS, Readiness Gate kustom, dan PDB dengan `maxUnavailable: 1`.
- Lakukan simulasi skenario kegagalan: lakukan hard drain secara simultan pada 50% node worker dan buktikan secara matematis serta operasional bahwa tidak ada request HTTP yang mengalami response 502/503/504.

---

## 20. Summary
Resiliensi Kubernetes operasional bertumpu pada kolaborasi harmonis antara konfigurasi deklaratif aplikasi dan parameter kontrol klaster:
- **PDB** menjaga batas operasional saat pemeliharaan terjadwal.
- **Graceful termination (`preStop` + `terminationGracePeriodSeconds`)** menyelaraskan delay propagasi jaringan dengan pembersihan proses internal.
- **Probes** yang tepat mencegah pod terjebak restart loop tanpa akhir.
- **QoS dan Sizing** yang tepat melindungi pod kritis dari eksekusi mati mendadak oleh kernel Linux OOM Killer.
- **etcd snapshot & quorum management** adalah jaring pengaman terakhir yang menjamin kelangsungan hidup klaster dari bencana infrastruktur.