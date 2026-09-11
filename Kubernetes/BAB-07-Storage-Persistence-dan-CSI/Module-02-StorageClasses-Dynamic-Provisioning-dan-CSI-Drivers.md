---
[⬅️ Module 01: PV, PVC, & Storage Lifecycle](./Module-01-PV-PVC-Lifecycle-dan-Reclaim-Policies.md) | [📋 Silabus Induk](../README.md) | [BAB 07 Quiz & Challenge ➡️](./BAB-07-Quiz-dan-Challenge.md)
---

# Module 02: StorageClasses, Dynamic Provisioning, & Container Storage Interface (CSI) Architecture

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Mengidentifikasi evolusi arsitektur penyimpanan Kubernetes dari *In-Tree Volume Plugins* menuju *Out-of-Tree Container Storage Interface (CSI)*.
- Mendesain objek `StorageClass` produksi dengan parameter cloud-native (`provisioner`, `volumeBindingMode`, `allowVolumeExpansion`, `reclaimPolicy`, `mountOptions`).
- Membedakan alur kerja Controller Plane vs Node Plane pada CSI.
- Menjelaskan fungsi 5 sidecar container resmi Kubernetes CSI (`csi-provisioner`, `csi-attacher`, `csi-resizer`, `csi-snapshotter`, `node-driver-registrar`).
- Memahami urutan pemanggilan gRPC CSI: `CreateVolume` $\rightarrow$ `ControllerPublishVolume` $\rightarrow$ `NodeStageVolume` $\rightarrow$ `NodePublishVolume`.
- Melakukan ekspansi volume secara dinamis (*Dynamic Volume Expansion*) dan pencadangan berbasis *VolumeSnapshot*.

---

## 2. Prerequisite
- Memahami siklus hidup PV dan PVC (Modul 01).
- Memahami gRPC dan komunikasi Unix Domain Socket (UDS).
- Konsep dasar Linux storage: block device attaching (`/dev/xvdX`), formatting filesystem (`mkfs.ext4`), dan bind mounting.

---

## 3. Concept
Pada masa awal Kubernetes, driver penyimpanan untuk AWS EBS, GCE PD, Azure Disk, Ceph, dan Cinder ditanamkan langsung ke dalam codebase biner inti `kube-controller-manager` dan `kubelet` (*In-Tree Plugins*).
Pendekatan ini menimbulkan masalah besar:
1. Vendor storage harus menunggu jadwal rilis kuartalan Kubernetes hanya untuk memperbaiki bug kecil driver storage mereka.
2. Kerentanan keamanan atau memory leak pada kode vendor storage pihak ketiga dapat meruntuhkan proses inti `kubelet`.
3. Codebase Kubernetes membengkak drastis (*dependency bloat*).

Untuk mengatasinya, CNCF mengadopsi standar industri terbuka: **Container Storage Interface (CSI)**. Vendor storage kini mengembangkan driver mereka di luar Kubernetes (*Out-of-Tree*), yang berkomunikasi dengan Kubernetes melalui protokol RPC terstandar (**gRPC**) via Unix Domain Socket.

```
                    +------------------------------------------+
                    |           KUBERNETES CONTROL PLANE       |
                    |                                          |
                    |      [ kube-controller-manager ]         |
                    |                    |                     |
                    |                    v watches             |
                    |       [ PersistentVolumeClaim ]          |
                    +--------------------+---------------------+
                                         |
                       k8s API events    v
+-----------------------------------------------------------------------------------+
| CSI CONTROLLER POD (Deployment - Out-of-tree)                                     |
|                                                                                   |
|  +---------------------+   gRPC (UDS)    +-------------------------------------+  |
|  | csi-provisioner     | --------------> |                                     |  |
|  +---------------------+                 |                                     |  |
|  +---------------------+   gRPC (UDS)    |         Vendor CSI Plugin           |  |
|  | csi-attacher        | --------------> |        (Controller Service)         |  |
|  +---------------------+                 |  (AWS EBS / Ceph / Portworx Driver) |  |
|  +---------------------+   gRPC (UDS)    |                                     |  |
|  | csi-resizer         | --------------> |                                     |  |
|  +---------------------+                 +------------------+------------------+  |
+-------------------------------------------------------------|---------------------+
                                                              | Cloud API Call
                                                              v (Create/Attach Disk)
                                                   [ Cloud / SAN Storage IaaS ]
                                                              |
                                                              v Attached Block Dev
+-------------------------------------------------------------|---------------------+
| KUBERNETES WORKER NODE (Node Plane)                         |                     |
|                                                             v                     |
|  [ Linux Kernel: Block Device /dev/nvme1n1 ] <--------------+                     |
|                                                                                   |
|  [ kubelet ] <--- gRPC UDS ---> [ Vendor CSI Node Plugin (DaemonSet) ]            |
|       |                                 |                                         |
|       v                                 v                                         |
|   Format Filesystem (ext4/xfs) ---> NodeStageVolume (/var/lib/kubelet/plugins/..) |
|   Bind Mount ke Container      ---> NodePublishVolume (/var/lib/kubelet/pods/..)  |
|                                                                                   |
|  [ Pod Container /data mount point ]                                              |
+-----------------------------------------------------------------------------------+
```

---

## 4. Why?
Mengapa sistem *Dynamic Provisioning* via StorageClass menjadi standar de facto?
1. **Zero Human Intervention**: Developer hanya perlu mendefinisikan PVC, dan sistem cloud (AWS, GCP, Azure, OpenStack) akan otomatis membuat disk fisik, meng-attach disk ke VM node yang tepat, memformat partisi, dan me-mount disk ke Pod dalam hitungan detik.
2. **Quality of Service (QoS) Tiering**: Administrator dapat mendefinisikan kelas-kelas penyimpanan yang berbeda (misal: `fast-ssd-gp3`, `cheap-cold-hdd`, `replicated-ceph`) dengan konfigurasi IOPS dan throughput terpisah.
3. **Automated Volume Resizing**: Kapasitas disk dapat diperbesar secara online tanpa mematikan aplikasi dengan mengubah angka di PVC.

---

## 5. What?

### A. Anatomi Objek StorageClass
Objek `StorageClass` mendefinisikan "cetak biru" pembuatan volume secara dinamis:
- **`provisioner`**: Nama unik driver CSI yang bertanggung jawab (contoh: `ebs.csi.aws.com`, `pd.csi.storage.gke.io`).
- **`volumeBindingMode`**:
  - `Immediate`: PV langsung dibuat saat PVC dibuat. **BAHAYA** untuk cluster multi-AZ, karena disk bisa saja dibuat di zona A, sementara Pod dijadwalkan di zona B.
  - `WaitForFirstConsumer`: Pembuatan PV ditunda sampai ada Pod yang menggunakan PVC tersebut dan scheduler telah menentukan di Node/Zona mana Pod akan berjalan. **(SANGAT DIREKOMENDASIKAN)**.
- **`allowVolumeExpansion`**: `true` jika storage backend mendukung pembesaran ukuran disk secara dinamis.
- **`reclaimPolicy`**: `Delete` (default) atau `Retain`.
- **`parameters`**: Key-value spesifik vendor driver (misal: tipe disk `gp3`, IOPS, enkripsi KMS).
- **`mountOptions`**: Parameter mount Linux (misal: `noatime`, `nodiratime`, `barrier=0`).

### B. Komponen CSI Sidecar
Kubernetes SIG Storage menyediakan sekumpulan *sidecar container* generik yang dipaketkan bersama driver vendor:
1. **`csi-provisioner`**: Memantau pembuatan PVC, memanggil RPC `CreateVolume` ke driver vendor, dan membuat objek PV di etcd.
2. **`csi-attacher`**: Memantau objek `VolumeAttachment`, memanggil RPC `ControllerPublishVolume` untuk meng-attach block device fisik ke Virtual Machine worker node.
3. **`csi-resizer`**: Memantau peningkatan `.spec.resources.requests.storage` pada PVC, memanggil RPC `ControllerExpandVolume`.
4. **`csi-snapshotter`**: Memantau objek `VolumeSnapshot`, memanggil RPC `CreateSnapshot` ke API storage backend.
5. **`node-driver-registrar`**: Berjalan di setiap Node (DaemonSet), mendaftarkan driver node CSI ke `kubelet` plugin registration directory (`/var/lib/kubelet/plugins_registry/`).

---

## 6. How?

### Alur Kerja Lengkap Dynamic Provisioning (Step-by-Step)
1. **User membuat PVC**: Menentukan `storageClassName: fast-ebs` dan `requests.storage: 100Gi`.
2. **Scheduling**: Karena `volumeBindingMode: WaitForFirstConsumer`, scheduler menunggu hingga Pod dibuat, lalu memilih `Node-03` di AZ `us-east-1a`.
3. **Provisioning**: `csi-provisioner` melihat PVC dan node terpilih, lalu memanggil gRPC `CreateVolume` ke driver vendor. Driver membuat disk EBS 100Gi di `us-east-1a`. Objek PV dibuat otomatis dan ter-bind ke PVC.
4. **Attaching**: Objek `VolumeAttachment` dibuat oleh `attach-detach-controller`. `csi-attacher` memanggil gRPC `ControllerPublishVolume` ke AWS API: `AttachVolume(vol-xxx, Node-03)`.
5. **Staging (Node Plane)**: Disk muncul di Linux kernel `Node-03` sebagai block device `/dev/nvme1n1`. `kubelet` memanggil gRPC `NodeStageVolume` ke CSI Node DaemonSet. Driver memformat disk dengan filesystem (`mkfs.ext4`) dan me-mount ke staging directory global: `/var/lib/kubelet/plugins/kubernetes.io/csi/.../globalmount`.
6. **Publishing (Bind Mount)**: `kubelet` memanggil gRPC `NodePublishVolume`. Driver me-mount direktori staging ke direktori privat Pod: `/var/lib/kubelet/pods/<Pod-UID>/volumes/kubernetes.io~csi/.../mount`.
7. **Container Start**: Kubelet memerintahkan container runtime (containerd) me-mount bind path tersebut ke rootfs container (`/var/lib/mysql`).

---

## 7. Analogy
Bayangkan memesan **Meja Restoran Custom (StorageClass)**:
- **Pelanggan (Developer)** memesan meja VIP kapasitas 4 orang lewat aplikasi (**PVC**).
- **Maitre d' (Kube-Scheduler)** menunggu pelanggan tiba di depan pintu gedung (**WaitForFirstConsumer**), lalu mencarikan lantai yang masih ada kursi kosong (**Node Selection**).
- Setelah tahu lantai yang dituju, **Staf Logistik (`csi-provisioner` & `csi-attacher`)** menelepon gudang logistik untuk mengirimkan meja ke lantai tersebut (**ControllerPublish**).
- **Pelayan Lantai (`kubelet` & CSI Node Plugin)** membersihkan meja, memasang taplak piring (**NodeStageVolume / mkfs.ext4**), dan menggeser kursi tepat di hadapan tamu (**NodePublishVolume / bind-mount**).

---

## 8. Diagram

```
+-----------------------------------------------------------------------------+
|               CSI MOUNTING PIPELINE (gRPC SEQUENCE)                         |
+-----------------------------------------------------------------------------+

Developer           k8s API Server       CSI Controller         kubelet / Node Plugin
    |                     |                    |                         |
    | 1. Create PVC/Pod   |                    |                         |
    |-------------------->|                    |                         |
    |                     | 2. Trigger Event   |                         |
    |                     |------------------->|                         |
    |                     |                    | 3. CreateVolume()       |
    |                     |                    |    (Allocates cloud LUN)|
    |                     |                    | 4. ControllerPublish()  |
    |                     |                    |    (Attach to Node VM)  |
    |                     |                    |------------------------>|
    |                     |                    |                         | 5. Linux detects
    |                     |                    |                         |    /dev/nvmeXn1
    |                     |                    |                         |
    |                     |                    |                         | 6. NodeStageVolume()
    |                     |                    |                         |    (mkfs.ext4 global)
    |                     |                    |                         |
    |                     |                    |                         | 7. NodePublishVolume()
    |                     |                    |                         |    (bind-mount to Pod)
    |                     |                    |                         |
    |                     |<-------------------|-------------------------|
    |                     | 8. Status: Volume Mounted & Container Running!
```

---

## 9. Simple Example (StorageClass Manifest Produksi)

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: enterprise-ssd-gp3
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: ebs.csi.aws.com
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
reclaimPolicy: Delete
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
  encrypted: "true"
  kmsKeyId: "arn:aws:kms:ap-southeast-1:123456789012:key/custom-storage-key"
mountOptions:
  - noatime
  - nodiratime
```

---

## 10. Practical Example: Dynamic Volume Expansion & VolumeSnapshot

### A. Memperbesar Kapasitas Volume (Resize) Secara Dinamis
Developer ingin menambah ukuran volume dari `50Gi` menjadi `100Gi` tanpa me-restart Pod:

```yaml
# pvc-database.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: db-data-pvc
  namespace: database
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: enterprise-ssd-gp3
  resources:
    requests:
      storage: 100Gi # Diubah dari 50Gi -> 100Gi
```

*Langkah Eksekusi:*
1. Jalankan `kubectl apply -f pvc-database.yaml`.
2. `csi-resizer` mendeteksi perubahan kapasitas dan memanggil `ControllerExpandVolume` ke AWS EBS.
3. Kubelet memanggil `NodeExpandVolume` untuk menjalankan `resize2fs` atau `xfs_growfs` secara otomatis di filesystem Linux tanpa downtime.
4. Periksa status via: `kubectl describe pvc db-data-pvc` (Lihat kondisi `FileSystemResizePending` $\rightarrow$ Sukses).

### B. VolumeSnapshot Manifest
```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: db-snapshot-before-migration
  namespace: database
spec:
  volumeSnapshotClassName: ebs-csi-snapshot-class
  source:
    persistentVolumeClaimName: db-data-pvc
```

Untuk me-restore snapshot ini menjadi PVC baru:
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: db-restored-pvc
  namespace: database
spec:
  storageClassName: enterprise-ssd-gp3
  dataSource:
    name: db-snapshot-before-migration
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
```

---

## 11. Real World Example: High IOPS Database (Kafka / Cassandra) on Local NVMe CSI
Untuk workload analitik atau streaming data berkecepatan tinggi (seperti Apache Kafka, Elasticsearch, ScyllaDB), latency jaringan EBS/SAN cloud terlalu tinggi (1-3ms latency). Diperlukan latency sub-millisecond (< 100 mikrodetik) menggunakan local NVMe SSD yang terpasang fisik di motherboard bare-metal server.

**Arsitektur Solusi**:
Menggunakan **Topolvm** atau **Rancher Local Path Provisioner / OpenEBS LVM CSI**:
- Driver CSI mengelola Logical Volume Manager (LVM) di filesystem lokal host Linux.
- StorageClass dikonfigurasi dengan `volumeBindingMode: WaitForFirstConsumer`.
- Ketika Pod Kafka dibuat, driver memotong partisi LVM VG sebesar kuota PVC secara instan di host fisik lokal.
- Pod mendapatkan throughput disk mentah (raw device/native NVMe) tanpa overhead jaringan cloud controller.

---

## 12. Trade-offs

| Parameter | In-Tree Volume Plugin (Legacy) | Out-of-Tree CSI Driver (Modern) |
|---|---|---|
| **Siklus Rilis Driver** | Terikat dengan rilis Kubernetes Core | Independen (Vendor bisa rilis update kapan saja) |
| **Stabilitas Kubelet** | Rawan crash jika plugin error | Aman (Crash driver terisolasi di Pod DaemonSet terpisah) |
| **Fitur Lanjutan** | Terbatas pada attach/mount | Snapshots, Cloning, Online Resizing, Dynamic Ephemeral |
| **Konsumsi Resource** | Sedikit lebih ringan (tanpa sidecar Pod) | Membutuhkan beberapa pod controller & sidecar container |

---

## 13. When To Use
- Selalu gunakan **CSI Driver resmi** vendor infrastruktur Anda (AWS EBS CSI, GCP PD CSI, Azure Disk CSI, Ceph CSI, Longhorn, Rook).
- Selalu aktifkan `allowVolumeExpansion: true` pada seluruh StorageClass produksi untuk mengantisipasi database kehabisan disk space (*disk full outage*).
- Gunakan **VolumeSnapshot** untuk backup stateful database sebelum melakukan deployment migrasi skema database berbahaya.

---

## 14. When NOT To Use
- **JANGAN** gunakan `volumeBindingMode: Immediate` pada cluster multi-zona, karena probabilitas tinggi terjadinya kegagalan binding volume zona salah.
- Jangan mengaktifkan `allowVolumeExpansion` jika sistem berkas lawas Anda tidak mendukung online resizing (seperti partisi tertentu pada sistem non-Linux).

---

## 15. Common Mistakes
1. **Lupa Memberikan IAM Role / Permission ke CSI Controller**: Menginstall AWS EBS CSI driver tetapi lupa menyematkan IAM Role via IRSA (`eks.amazonaws.com/role-arn`). Driver akan melempar log error: `AccessDenied: User is not authorized to perform ec2:CreateVolume`.
2. **Menghapus Snapshot Class Saat Restore**: Jika objek `VolumeSnapshotClass` dihapus, objek snapshot akan berstatus `Error` dan tidak dapat di-restore ke PVC baru.
3. **Mencoba Mengecilkan Ukuran Volume (Volume Shrink)**: Kubernetes dan mayoritas filesystem Linux (seperti ext4/xfs) **TIDAK MENDUKUNG** pengecilan ukuran volume. Mengubah ukuran PVC dari 100Gi menjadi 50Gi akan ditolak oleh admission validation API Server.

---

## 16. Best Practices
- **Must Have**: Pasang satu StorageClass sebagai default cluster dengan anotasi `storageclass.kubernetes.io/is-default-class: "true"`.
- **Recommended**: Terapkan parameter enkripsi disk secara default pada StorageClass (`encrypted: "true"`) untuk kepatuhan SOC2/ISO27001.
- **Advanced**: Implementasikan *CSI Storage Capacity Tracking* (`CSIDriver.spec.storageCapacity: true`) agar scheduler mengetahui sisa kapasitas disk lokal sebelum menjadwalkan Pod.
- **Avoid**: Menjalankan CSI Controller Pod tanpa konfigurasi High Availability (Replicas minimal 2 dengan leader election aktif).

---

## 17. Troubleshooting Guide
```
Masalah: VolumeAttachment stuck selamanya di status attaching.
Penyebab : Node VM telah mencapai batas maksimal disk attachment (misal instance AWS nitro hanya mendukung hingga N volume EBS).
Diagnosa : kubectl describe volumeattachment <attachment-id>
           Periksa log csi-attacher: "AttachmentLimitExceeded: The maximum number of volumes has been reached."
Solusi   : Naikkan tipe instance worker node, atau gunakan shared storage / konsolidasikan PV.

Masalah: Pod stuck di "ContainerCreating", event: "NodeStageVolume failed: exit status 32: mount: wrong fs type, bad option".
Penyebab : Format filesystem gagal atau mount options yang didefinisikan di StorageClass tidak didukung oleh kernel host Linux.
Diagnosa : ssh ke worker node, periksa dmesg | tail -n 50.
Solusi   : Hapus mountOptions yang tidak kompatibel (misal parameter XFS pada partisi EXT4).
```

---

## 18. Exercise
1. Buat manifest `StorageClass` bernama `fast-cloud-ssd` dengan provisioner `ebs.csi.aws.com`, `volumeBindingMode: WaitForFirstConsumer`, dan `allowVolumeExpansion: true`.
2. Buat PVC yang meminta 15Gi dari StorageClass tersebut.
3. Tulis Pod dummy yang me-mount PVC ke `/opt/data`. Amati log siklus pembuatan disk melalui command `kubectl get events --sort-by='.metadata.creationTimestamp'`.

---

## 19. Challenge
Implementasikan pipeline pencadangan StatefulSet PostgreSQL menggunakan objek `VolumeSnapshot`. Simulasikan skenario di mana data korup terjadi pada database primer, lalu restore snapshot tersebut ke PVC baru dan hubungkan ke Pod recovery untuk memastikan integritas data.

---

## 20. Summary
Arsitektur Container Storage Interface (CSI) merevolusi ekosistem penyimpanan di Kubernetes dengan memisahkan kode vendor storage dari biner core Kubernetes. Melalui kolaborasi rapi antara sidecar controller (`csi-provisioner`, `csi-attacher`, `csi-resizer`) dan node plugin gRPC (`NodeStageVolume`, `NodePublishVolume`), Kubernetes menghadirkan otomatisasi lifecycle storage kelas enterprise yang fleksibel, aman, dan dapat diskalakan.

---
[⬅️ Module 01: PV, PVC, & Storage Lifecycle](./Module-01-PV-PVC-Lifecycle-dan-Reclaim-Policies.md) | [📋 Silabus Induk](../README.md) | [BAB 07 Quiz & Challenge ➡️](./BAB-07-Quiz-dan-Challenge.md)
---
