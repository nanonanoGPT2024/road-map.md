# Module 02: StatefulSets, Headless Services, DaemonSets, Jobs, dan CronJobs

---
[⬅️ Module 01: Deployments & Rollbacks](./Module-01-Deployments-RollingUpdate-Strategies-dan-Rollbacks.md) | [📋 Silabus Induk](../README.md) | [Evaluasi & Quiz BAB 03 ➡️](./BAB-03-Quiz-dan-Challenge.md)
---

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Memahami arsitektur dan kapabilitas **StatefulSets** untuk mengelola aplikasi stateful terdistribusi (Database, Message Queue).
2. Mengonfigurasi **Headless Service** (`clusterIP: None`) untuk penemuan DNS antar-peer (*peer-to-peer discovery*).
3. Menerapkan **`volumeClaimTemplates`** guna menjamin bahwa setiap replika Pod memiliki PersistentVolume (PV) independen yang tidak tertukar saat Pod di-restart.
4. Mengoperasikan **DaemonSets** untuk menjamin berjalannya satu instance Pod di setiap worker node (log collector, monitoring agent, CNI network daemon).
5. Mengelola beban kerja batch terputus menggunakan **Jobs** dan penjadwalan berkala menggunakan **CronJobs** (beserta kebijakan `concurrencyPolicy`).

---

## 2. Prerequisite
- Memahami konsep Deployments dan ReplicaSets ([Module 01 BAB 03](Module-01-Deployments-RollingUpdate-Strategies-dan-Rollbacks.md)).
- Pemahaman dasar konsep Persistent Storage dan DNS jaringan ([Docker BAB 04 & 05](../../Docker/BAB-04-Docker-Storage-Volumes-dan-Persistence/)).
- Pemahaman arsitektur database terdistribusi (Primary-Replica, Quorum, Raft).

---

## 3. Concept
Tidak semua aplikasi di dunia ini bersifat *stateless* (bebas kondisi) yang dapat dipertukarkan secara acak seperti web server HTTP.

Aplikasi terdistribusi seperti PostgreSQL Primary-Replica, Apache Kafka, Elasticsearch, dan Redis Cluster menuntut tiga hal fundamental:
1. **Identitas Jaringan Stabil (Predictable Network Identity)**: Setiap node membutuhkan hostname tetap (misal `kafka-0`, `kafka-1`, `kafka-2`) yang tidak berubah meskipun Pod di-restart atau dipindahkan ke node fisik lain.
2. **Penyimpanan Khusus Terikat (Dedicated Stable Storage)**: Pod `kafka-1` harus selalu tersambung kembali ke partisi disk milik `kafka-1`, bukan disk milik `kafka-0`.
3. **Urutan Bootstrapping & Scaling Teratur**: Node master (0) harus hidup sebelum replica (1), dan saat scaling down, node terakhir harus dimatikan terlebih dahulu.

Untuk memenuhi kebutuhan inilah Kubernetes menyediakan pengontrol **StatefulSet**. Di sisi lain, untuk tugas pemantauan per-host fisik kita menggunakan **DaemonSet**, dan untuk tugas komputasi sekali jalan (*run-to-completion*) kita menggunakan **Jobs** dan **CronJobs**.

---

## 4. Why?
1. **Pencegahan Korupsi Data Database**: Mencoba menjalankan database kluster menggunakan `Deployment` standar akan menyebabkan bencana: seluruh replika akan berbagi volume yang sama (korupsi disk) dan nama hostname Pod yang acak (misal `postgres-7f8b9-x8j2`) membuat konfigurasi replikasi master-slave gagal.
2. **Observabilitas Host Merata (DaemonSet Guarantee)**: Anda ingin memastikan bahwa setiap kali sebuah worker node baru ditambahkan ke kluster (autoscaling), agen pengumpul log (Fluent Bit) dan Node Exporter otomatis berjalan di mesin tersebut tanpa konfigurasi manual.
3. **Penyelesaian Batch Job Deterministik (Jobs & CronJobs)**: Menjalankan migrasi database via Pod biasa berisiko: jika gagal, ia akan terus di-restart berulang-ulang tanpa henti. `Job` menyediakan batasan percobaan ulang (`backoffLimit`) dan mencatat status sukses definitif (`Completed`).

---

## 5. What?
### Matriks Workload Controllers Khusus:

| Controller | Karakteristik Nama Pod | Karakteristik Storage | Kasus Penggunaan Ideal |
|---|---|---|---|
| **StatefulSet** | Deterministik berurutan (`app-0`, `app-1`, `app-2`). | Unik per Pod via `volumeClaimTemplates` (menempel permanen). | PostgreSQL, MySQL Replication, Apache Kafka, ZooKeeper, Redis Cluster. |
| **DaemonSet** | Terikat satu per node (`app-node1`, `app-node2`). | Mengakses host filesystem (`hostPath`). | Log Collector (Promtail, Fluent Bit), Node Exporter, CNI Plugin (Cilium, Calico). |
| **Job** | Acak/ephemeral (`job-84k2-x91f`). | Bersifat sementara (*run-to-completion*). | Migrasi skema database, batch data processing, retraining model AI. |
| **CronJob** | Otomatis dibuat berkala oleh jadwal Cron. | Bergantung pada Job yang diproduksi. | Pembersihan database mingguan, backup snapshot etcd harian, email invoice. |

---

## 6. How? Arsitektur StatefulSet & Headless Service

```text
                  [ Client / Internal Microservices ]
                                   |
                                   v (Query DNS)
      +----------------------------------------------------------+
      |        Headless Service (clusterIP: None)                |
      |        Nama Service: "postgres-svc"                      |
      +----------------------------------------------------------+
                                   |
             +---------------------+---------------------+
             |                     |                     |
   DNS: postgres-0.postgres-svc    |        DNS: postgres-2.postgres-svc
             |                     |                     |
             v                     v                     v
   +-------------------+ +-------------------+ +-------------------+
   | Pod: postgres-0   | | Pod: postgres-1   | | Pod: postgres-2   |
   | Role: Primary     | | Role: Replica-1   | | Role: Replica-2   |
   +-------------------+ +-------------------+ +-------------------+
             |                     |                     |
             v                     v                     v
   +-------------------+ +-------------------+ +-------------------+
   | PVC: data-pg-0    | | PVC: data-pg-1    | | PVC: data-pg-2    |
   | (AWS EBS / SAN)   | | (AWS EBS / SAN)   | | (AWS EBS / SAN)   |
   +-------------------+ +-------------------+ +-------------------+
```

---

## 7. Analogy
Bayangkan perbedaan antara hewan ternak (cattle) dan hewan peliharaan (pets):
- **Deployment** adalah **Hewan Ternak**: Jika seekor domba hilang, Anda tidak memberinya nama individu; Anda hanya menggantinya dengan domba lain yang identik (stateless).
- **StatefulSet** adalah **Hewan Peliharaan**: Masing-masing memiliki nama unik (*Dog-0*, *Dog-1*), mangkuk makanan sendiri yang tidak boleh tertukar (*PVC Dedicated*), dan rutinitas makan yang berurutan.
- **DaemonSet** adalah **Satpam Kompleks Perumahan**: Anda mewajibkan setiap gerbang blok perumahan memiliki tepat 1 pos satpam. Jika ada blok baru dibangun, pos satpam otomatis didirikan di sana.
- **Job** adalah **Tukang Servis AC Panggilan**: Datang ke rumah, mencuci AC sampai bersih (selesai tugas), lalu pulang (exit 0) dan tidak pernah tinggal menetap di rumah Anda.

---

## 8. Diagram: Kebijakan Konkurensi CronJob (`concurrencyPolicy`)

```text
Kasus: CronJob dijadwalkan setiap 5 menit, tetapi tugas memakan waktu 8 menit.

Opsi 1: concurrencyPolicy: Allow (Default)
T=0m  : [ Job 1 Mulai ]=========================> (Selesai T=8m)
T=5m  :                  [ Job 2 Mulai ]=========================>
(Dua job berjalan tumpang tindih! Berbahaya untuk task yang memodifikasi data yang sama!)

Opsi 2: concurrencyPolicy: Forbid (Direkomendasikan untuk Batch)
T=0m  : [ Job 1 Mulai ]=========================> (Selesai T=8m)
T=5m  :                  [ Job 2 DILEWATI / SKIP! Karena Job 1 belum selesai ]
T=10m :                                           [ Job 3 Mulai ]===============>

Opsi 3: concurrencyPolicy: Replace
T=0m  : [ Job 1 Mulai ]=========> (DIBUNUH / CANCELLED pada T=5m!)
T=5m  :                           [ Job 2 Mulai menggantikan Job 1 ]============>
```

---

## 9. Simple Example: Headless Service dan StatefulSet PostgreSQL

```yaml
# 1. Headless Service (Wajib clusterIP: None)
apiVersion: v1
kind: Service
metadata:
  name: postgres-headless
  labels:
    app: postgres
spec:
  clusterIP: None # Kunci Headless: Mengembalikan record A langsung ke IP Pod!
  ports:
  - port: 5432
    name: db
  selector:
    app: postgres
---
# 2. StatefulSet Definition
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres-db
spec:
  serviceName: "postgres-headless" # Terikat ke Headless Service di atas
  replicas: 3
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        ports:
        - containerPort: 5432
          name: db
        volumeMounts:
        - name: db-storage
          mountPath: /var/lib/postgresql/data
  # Volume dinamis otomatis per-Pod
  volumeClaimTemplates:
  - metadata:
      name: db-storage
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 20Gi
```

---

## 10. Practical Example: DaemonSet Monitoring & Batch Job

### 1. DaemonSet: Node Exporter di Seluruh Node
```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-exporter
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: node-exporter
  template:
    metadata:
      labels:
        app: node-exporter
    spec:
      hostNetwork: true
      hostPID: true
      # Izinkan berjalan di node control-plane (master) juga!
      tolerations:
      - operator: "Exists"
        effect: "NoSchedule"
      containers:
      - name: node-exporter
        image: prom/node-exporter:v1.7.0
        ports:
        - containerPort: 9100
          hostPort: 9100
```

### 2. CronJob: Database Backup Otomatis Setiap Tengah Malam
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: nightly-db-backup
spec:
  schedule: "0 0 * * *" # Pukul 00:00 setiap hari
  concurrencyPolicy: Forbid # Jangan jalankan bersamaan jika backup lambat
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 5
  jobTemplate:
    spec:
      backoffLimit: 2 # Maksimal 2x retry jika gagal
      template:
        spec:
          restartPolicy: OnFailure # Wajib OnFailure atau Never untuk Job
          containers:
          - name: pg-dump
            image: postgres:16-alpine
            command: ["sh", "-c", "pg_dump -h postgres-db-0.postgres-headless -U admin my_db | gzip > /backup/backup-$(date +%F).sql.gz"]
```

---

## 11. Real World Example: Migrasi Cluster Kafka StatefulSet
Sebuah perusahaan logistik menjalankan kluster Apache Kafka dengan 5 broker menggunakan StatefulSet:
- Setiap broker Pod memiliki FQDN sendiri: `kafka-0.kafka-headless.prod.svc.cluster.local`, `kafka-1...`, dst.
- Ketika worker node fisik tempat `kafka-2` berjalan mengalami kegagalan hardware, Kubelet menjadwalkan ulang Pod `kafka-2` ke worker node lain.
- Storage cloud AWS EBS volume (`data-kafka-2`) otomatis di-*detach* dari node rusak dan di-*attach* kembali ke node baru.
- Nama pod tetap `kafka-2` dan IP-nya diperbarui di CoreDNS secara instan.
- **Hasil**: Kluster Kafka tetap sinkron tanpa perlu re-balancing partisi data bergiga-giga bytes karena disk dan identitas broker tidak pernah berubah!

---

## 12. Trade-offs: Workload Selection Matrix

| Kebutuhan Sistem | Gunakan Controller Ini | Alasan |
|---|---|---|
| REST API Stateless / Web Frontend | **Deployment** | Mudah di-scale, rolling update instan, tidak butuh disk persisten. |
| Database Primary-Replica / Kafka | **StatefulSet** | Membutuhkan urutan start/stop, volume dedicated per-pod, dan DNS FQDN stabil. |
| Pengumpulan Log / Firewall Host Node | **DaemonSet** | Menjamin tepat 1 Pod per node host (termasuk node baru hasil autoscaling). |
| Migrasi Database / Data Processing | **Job** | Berhenti saat tugas selesai (*run-to-completion*), memiliki batasan retry. |
| Backup Harian / Report Generator | **CronJob** | Penjadwalan berkala berbasis ekspresi cron standar. |

---

## 13. When To Use
- Gunakan **StatefulSets** hanya jika workload Anda benar-benar membutuhkan salah satu dari: identitas network teratur, storage persisten terikat, atau urutan deploy tertib.
- Selalu sandingkan StatefulSet dengan **Headless Service** (`clusterIP: None`) agar penemuan alamat IP individu Pod dapat diakses oleh pod lain di kluster.
- Selalu setel `concurrencyPolicy: Forbid` pada CronJob batch database agar proses transaksi tidak saling mengunci.

---

## 14. When NOT To Use
- Jangan gunakan StatefulSet untuk aplikasi stateless web murni (Node.js/Go API) karena proses rolling update-nya lambat (sekuensial $N-1$ ke $0$) dan membuang-buang alokasi PVC.
- Jangan gunakan `restartPolicy: Always` pada Job atau CronJob (Kubernetes akan menolak validasi skema).

---

## 15. Common Mistakes
1. **Menghapus StatefulSet dan mengira Storage PVC akan otomatis terhapus**: Demi keamanan data, Kubernetes **SENGAJA TIDAK MENGHAPUS PVC** ketika StatefulSet dihapus. PVC harus dihapus secara eksplisit manual jika memang ingin membuang data.
2. **Lupa membuat Headless Service untuk StatefulSet**: StatefulSet akan gagal membuat FQDN jaringan untuk masing-masing replika jika `spec.serviceName` tidak cocok dengan nama Service headless.
3. **Mengabaikan `podManagementPolicy: Parallel`**: Jika Anda membutuhkan StatefulSet hanya demi dedicated storage tanpa membutuhkan urutan start sekuensial (0 lalu 1 lalu 2), gunakan `podManagementPolicy: Parallel` agar proses deploy berjalan serentak.

---

## 16. Best Practices
### Must Have
- Terapkan `concurrencyPolicy: Forbid` pada semua CronJob yang mengakses database produksi.
- Selalu definisikan `backoffLimit` pada Job agar batch job yang error tidak me-restart ribuan kali dan menghabiskan CPU kluster.

### Recommended
- Konfigurasikan `tolerations` pada DaemonSet sistem (monitoring/logging) agar dapat dijadwalkan di node control-plane jika diperlukan visibilitas menyeluruh.
- Pasang label retensi storage pada PVC StatefulSet agar terhindar dari pembersihan disk yang tidak disengaja.

### Advanced
- Gabungkan StatefulSet dengan **Kube-Prometheus-Stack** dan custom metrics exporter untuk memonitor replikasi lag antar node primary dan replica.

---

## 17. Troubleshooting Guide
### Problem 1: Pod StatefulSet stuck di status `Pending` pada replika kedua (`db-1`)
- **Penyebab**: Replika sebelumnya (`db-0`) belum dalam kondisi `Ready` sehingga StatefulSet menahan deployment replika berikutnya, ATAU StorageClass kehabisan kuota volume cloud.
- **Diagnosa**:
  ```bash
  kubectl describe statefulset <nama-statefulset>
  kubectl get pvc
  kubectl describe pod <nama-pod-0-atau-1>
  ```
- **Solusi**: Periksa apakah probe `db-0` sudah lolos, atau periksa event claim storage PVC.

### Problem 2: CronJob tidak pernah mengeksekusi Job baru
- **Penyebab**: Job sebelumnya masih menggantung (hang) dan `concurrencyPolicy: Forbid` mencegah pembuatan job baru.
- **Diagnosa**:
  ```bash
  kubectl get jobs -l job-name
  kubectl describe cronjob <nama-cronjob>
  ```
- **Solusi**: Hapus Job lama yang menggantung atau setel `startingDeadlineSeconds` dan `activeDeadlineSeconds` pada template Job.

---

## 18. Exercises
### Level: Easy
1. Buat Headless Service sederhana untuk aplikasi Redis dengan nama `redis-headless` dan `clusterIP: None`.
2. Buat Kubernetes Job sederhana yang menghitung nilai Pi hingga 2000 digit menggunakan image `perl:5.34.0` dan verifikasi bahwa statusnya berubah menjadi `Completed`.

### Level: Medium
1. Buat StatefulSet dengan 2 replika menggunakan image `nginx:alpine` dan `volumeClaimTemplates` lokal `emptyDir` (atau storage default).
2. Periksa nama kedua Pod yang terbentuk (`nginx-stateful-0` dan `nginx-stateful-1`).
3. Lakukan resolusi DNS dari pod lain menggunakan `nslookup nginx-stateful-0.redis-headless`.

### Level: Hard
1. Buat CronJob yang berjalan setiap 2 menit dengan `concurrencyPolicy: Forbid`.
2. Masukkan perintah `sleep 180` di dalam Job kontainer.
3. Amati bagaimana CronJob melewatkan eksekusi pada menit ke-2 karena eksekusi menit ke-0 masih berjalan.

---

## 19. Challenge
Rancang arsitektur penyimpanan dan orkestrasi untuk cluster database NoSQL MongoDB 3-Node:
- 1 Primary, 2 Secondary Replicas.
- Menggunakan StatefulSet dengan Headless Service.
- Masing-masing Pod wajib memiliki volume persisten 50GB.
- Dilengkapi CronJob harian yang melakukan snapshot dump database ke folder backup, lengkap dengan `concurrencyPolicy: Forbid` dan alert email jika gagal (Exit 1).
Tuliskan seluruh konfigurasi manifest YAML terpadu.

---

## 20. Summary
- **StatefulSet** memberikan identitas unik deterministik (`name-0`, `name-1`), urutan operasional tertib, dan storage terikat permanen (`volumeClaimTemplates`).
- **Headless Service** (`clusterIP: None`) memungkinkan resolusi DNS langsung ke IP masing-masing replika Pod StatefulSet.
- **DaemonSet** menjamin tepat satu Pod berjalan di setiap node kluster (ideal untuk agent pemantauan dan log shipper).
- **Jobs & CronJobs** mengelola eksekusi tugas batch terputus dengan kontrol konkurensi dan batasan percobaan ulang.

---
[⬅️ Module 01: Deployments & Rollbacks](./Module-01-Deployments-RollingUpdate-Strategies-dan-Rollbacks.md) | [📋 Silabus Induk](../README.md) | [Evaluasi & Quiz BAB 03 ➡️](./BAB-03-Quiz-dan-Challenge.md)
---
