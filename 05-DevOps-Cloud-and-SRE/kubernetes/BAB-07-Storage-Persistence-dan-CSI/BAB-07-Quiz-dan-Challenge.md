---
[⬅️ Module 02: StorageClasses & CSI Drivers](./Module-02-StorageClasses-Dynamic-Provisioning-dan-CSI-Drivers.md) | [📋 Silabus Induk](../README.md) | [BAB 08 Module 01: RBAC & Least Privilege ➡️](../BAB-08-Keamanan-Cluster-RBAC-dan-Admission-Controllers/Module-01-RBAC-Roles-ClusterRoles-dan-Least-Privilege.md)
---

# BAB 07: Storage, Persistence, & Container Storage Interface (CSI) — Quiz & Chapter Challenge

Dokumen ini berisi pengujian pemahaman konseptual, analisis skenario arsitektur penyimpanan riil, dan tantangan implementasi sistematis untuk BAB 07.

---

## Bagian 1: Quiz Konseptual Dasar (5 Soal)

### Soal 1
Apa perbedaan mendasar antara objek `PersistentVolume` (PV) dan `PersistentVolumeClaim` (PVC) dalam model tata kelola Kubernetes?
- A. PV berakar pada level namespace, sedangkan PVC berakar pada level cluster.
- B. PV merepresentasikan alokasi resource storage fisik di level cluster (dikelola oleh Admin/CSI), sedangkan PVC merepresentasikan permintaan konsumsi kuota storage oleh developer di level namespace.
- C. PV hanya dapat digunakan untuk file ephemeral, sedangkan PVC khusus untuk database relational.
- D. PV dibuat otomatis oleh Kubelet, sedangkan PVC dibuat oleh Docker daemon.

### Soal 2
Jika sebuah PersistentVolume memiliki `persistentVolumeReclaimPolicy: Retain`, apa yang terjadi pada data fisik dan objek PV ketika PVC terkait dihapus oleh developer?
- A. Objek PV dan data fisik di cloud LUN langsung dihapus secara permanen.
- B. Objek PV berstatus `Released`, dan data fisik tetap tersimpan utuh di storage backend; volume tidak dapat diikat ulang oleh PVC lain sebelum dibersihkan manual oleh admin.
- C. Objek PV otomatis diformat ulang dengan perintah `rm -rf /` dan kembali berstatus `Available`.
- D. Kubelet akan me-restart node secara otomatis untuk melepaskan koneksi iSCSI.

### Soal 3
Mengapa mode `volumeBindingMode: WaitForFirstConsumer` sangat krusial pada cluster Kubernetes yang terdistribusi di beberapa Availability Zone (Multi-AZ)?
- A. Agar disk storage dibuat dengan kecepatan baca/tulis dua kali lebih tinggi.
- B. Mencegah pembuatan volume cloud di Availability Zone yang berbeda dengan Node tempat Pod akhirnya dijadwalkan oleh `kube-scheduler`.
- C. Memaksa container untuk mengunduh image container terlebih dahulu sebelum membuat disk.
- D. Mencegah developer mengubah ukuran volume secara dinamis.

### Soal 4
Urutan pemanggilan interface gRPC CSI yang benar saat sebuah Pod dijadwalkan ke suatu Node dan siap membaca data dari volume block storage adalah:
- A. `NodePublishVolume` $\rightarrow$ `NodeStageVolume` $\rightarrow$ `CreateVolume` $\rightarrow$ `ControllerPublishVolume`
- B. `CreateVolume` $\rightarrow$ `ControllerPublishVolume` $\rightarrow$ `NodeStageVolume` $\rightarrow$ `NodePublishVolume`
- C. `ControllerPublishVolume` $\rightarrow$ `CreateVolume` $\rightarrow$ `NodePublishVolume` $\rightarrow$ `NodeStageVolume`
- D. `NodeStageVolume` $\rightarrow$ `CreateVolume` $\rightarrow$ `ControllerPublishVolume` $\rightarrow$ `NodePublishVolume`

### Soal 5
Apa fungsi dari sidecar container `csi-resizer` dalam arsitektur driver CSI modern?
- A. Mengompresi file log di dalam container agar disk tidak cepat penuh.
- B. Memantau perubahan field `.spec.resources.requests.storage` pada PVC dan memanggil RPC `ControllerExpandVolume` ke storage provider.
- C. Menghapus snapshot lama yang sudah berumur lebih dari 30 hari.
- D. Mengubah format filesystem dari FAT32 menjadi NTFS.

---

## Bagian 2: Quiz Skenario & Troubleshooting Tingkat Menengah (5 Soal)

### Soal 6
Sebuah PVC PostgreSQL berstatus `Pending`. Perintah `kubectl describe pvc pg-data` menampilkan event:
`waiting for a volume to be created, either by external provisioner "ebs.csi.aws.com" or manually created by system administrator`.
Namun, tidak ada Pod yang dibuat untuk merujuk PVC tersebut, dan StorageClass memiliki `volumeBindingMode: WaitForFirstConsumer`.
Apakah status `Pending` ini merupakan sebuah kegagalan (error)?
- A. Ya, driver CSI EBS mengalami crash dan harus di-restart.
- B. Ya, kuota storage AWS EBS akun Anda telah habis.
- C. Tidak, ini adalah perilaku normal (by design). Volume baru akan dialokasikan setelah ada Pod konsumen yang dibuat dan dijadwalkan ke suatu Node.
- D. Tidak, tetapi developer harus mengubah reclaim policy menjadi `Recycle`.

### Soal 7
Sebuah StatefulSet MongoDB mengalami kegagalan saat proses rolling update. Pod `mongodb-0` terjebak dalam status `Terminating`, sedangkan Pod penggantinya gagal start dengan pesan error:
`Multi-Attach error for volume "pvc-xyz": Volume is already exclusively attached to one node and can't be attached to another`.
Apa akar masalah teknis dari kondisi ini?
- A. Volume menggunakan AccessMode `ReadWriteMany` yang dilarang di StatefulSet.
- B. Block storage cloud (seperti EBS) bersifat `ReadWriteOnce` (eksklusif ke 1 VM hypervisor). Pod lama belum melepaskan detaching di level IaaS sebelum Pod baru mencoba menempelkan volume ke worker node yang berbeda.
- C. StorageClass kehabisan IOPS credit burst.
- D. ServiceAccount StatefulSet tidak memiliki wewenang RBAC.

### Soal 8
Developer tidak sengaja menjalankan perintah `kubectl delete pvc critical-db-pvc` pada database yang sedang aktif melayani transaksi. Namun, database tetap berjalan normal dan PVC menunjukkan status `Terminating`.
Mekanisme Kubernetes apa yang mencegah terhapusnya disk tersebut secara mendadak?
- A. Admission Webhook OPA Gatekeeper.
- B. Finalizer `kubernetes.io/pvc-protection` yang menahan penghapusan PVC selama ada Pod aktif yang me-mount volume tersebut.
- C. Kernel Linux lock pada direktori `/var/lib/kubelet`.
- D. Kube-proxy memblokir port 443 API Server.

### Soal 9
Anda perlu membagikan direktori asset media WordPress yang dapat dibaca dan ditulis secara bersamaan oleh 10 replika Pod WordPress yang tersebar di 5 Worker Node yang berbeda. Jenis volume dan AccessMode apa yang wajib digunakan?
- A. AWS EBS gp3 dengan `ReadWriteOnce`.
- B. Network File System (NFS) atau AWS EFS dengan `ReadWriteMany` (RWX).
- C. `hostPath` dengan `ReadOnlyMany`.
- D. `emptyDir` dengan memory medium.

### Soal 10
Administrator memperbesar kuota PVC dari 50Gi menjadi 100Gi. `kubectl describe pvc` menampilkan kondisi:
`FileSystemResizePending: Waiting for user to (re-)start a pod to finish file system resize of volume on node`.
Mengapa kondisi ini muncul?
- A. Storage backend cloud sudah memperbesar ukuran LUN block device, tetapi filesystem Linux (`resize2fs`/`xfs_growfs`) memerlukan kubelet di worker node untuk memperluas partisi saat volume di-mount.
- B. Driver CSI crash saat mengeksekusi mkfs.
- C. Kuota etcd cluster tidak mencukupi untuk menyimpan metadata 100Gi.
- D. Disk harus diformat ulang dari awal dan data lama akan hilang.

---

## Bagian 3: Skenario Kasus Arsitektur Tingkat Lanjut (3 Soal)

### Skenario 1: Disaster Recovery & Data Corruption Recovery
Sebuah insiden terjadi pada aplikasi e-commerce: script migrasi database merusak tabel order pada pukul 14:15. Tim DevOps memiliki kebijakan pencadangan otomatis menggunakan `VolumeSnapshot` setiap jam (snapshot terakhir tercatat pukul 14:00 bernama `orders-db-snap-1400`).
Rancang langkah-langkah deklaratif yang presisi untuk me-restore database PostgreSQL StatefulSet dari snapshot tersebut tanpa kehilangan histori volume lama!

### Skenario 2: Migrasi Arsitektur Storage Heterogen
Sebuah cluster Kubernetes on-premise saat ini menggunakan LUN SAN statis lama (Fibre Channel) dengan PV manual. Perusahaan memutuskan untuk bermigrasi ke software-defined storage Ceph RBD menggunakan Ceph-CSI dengan dynamic provisioning.
Bagaimana Anda menyusun strategi migrasi data dari PV statis lama ke PVC Ceph dinamis baru dengan meminimalkan waktu downtime aplikasi?

### Skenario 3: Cross-AZ Failure & Force Detach Protection
Pada zona `ap-southeast-1a`, terjadi pemadaman listrik total pada rak server yang menyebabkan Worker Node `node-05` mati mendadak (*node hard crash*). Controller Plane Kubernetes mendeteksi node `NotReady`. Pod Kafka broker di node tersebut ingin dipindahkan oleh Kubernetes ke `node-06` di AZ `ap-southeast-1b`.
Jelaskan mengapa volume EBS Kafka broker tersebut tidak bisa langsung di-mount di `node-06`, dan langkah apa yang harus diambil oleh operator SRE!

---

## Bagian 4: Chapter Challenge — Dynamic StorageClass & StatefulSet Automated Backup

### Deskripsi Tantangan
Anda ditugaskan sebagai Lead Platform Engineer untuk merancang infrastruktur storage produksi untuk kluster MySQL 8.0:
1. Buat manifest `StorageClass` bernama `production-database-sc`:
   - Provisioner: CSI driver AWS EBS (`ebs.csi.aws.com`).
   - Tipe volume: `gp3`.
   - Mengaktifkan ekspansi volume dinamis.
   - Kebijakan reclaim: `Retain` (untuk proteksi data finansial).
   - Mode binding: `WaitForFirstConsumer`.
   - Mount options: `noatime`.
2. Buat manifest `StatefulSet` MySQL single-instance:
   - Menggunakan `volumeClaimTemplates` yang merujuk ke StorageClass di atas dengan permintaan awal `20Gi`.
   - Mount path: `/var/lib/mysql`.
3. Buat manifest `VolumeSnapshotClass` dan `VolumeSnapshot` untuk membuat point-in-time backup dari PVC yang dihasilkan StatefulSet.
4. Tulis skrip verifikasi otomatis untuk membuktikan bahwa data yang ditulis ke partisi tetap utuh setelah Pod di-delete (`kubectl delete pod mysql-0`).

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Perbedaan scope cluster (`PV`) vs scope namespace (`PVC`).
- [ ] Empat AccessModes: `ReadWriteOnce`, `ReadOnlyMany`, `ReadWriteMany`, `ReadWriteOncePod`.
- [ ] Tiga Reclaim Policies: `Retain`, `Delete`, dan depresiasi `Recycle`.
- [ ] Mengapa `WaitForFirstConsumer` wajib digunakan pada cluster multi-AZ.
- [ ] Cara kerja proteksi finalizer `kubernetes.io/pvc-protection`.
- [ ] Arsitektur Out-of-tree CSI: peranan sidecar (`csi-provisioner`, `csi-attacher`, `csi-resizer`, `csi-snapshotter`).
- [ ] Alur gRPC: `CreateVolume` $\rightarrow$ `ControllerPublish` $\rightarrow$ `NodeStage` $\rightarrow$ `NodePublish`.
- [ ] Mekanisme Dynamic Volume Expansion (LUN resize vs filesystem expansion).

### Saya Tidak Perlu Menghafal:
- [ ] Spesifikasi protobuf gRPC byte-by-byte dari repositori `container-storage-interface/spec`.
- [ ] Parameter hex internal dari perintah `resize2fs` atau `xfs_growfs`.

### Saya Harus Bisa Melakukan:
- [ ] Menulis manifest StorageClass produksi dengan parameter keamanan dan performa yang tepat.
- [ ] Melakukan troubleshooting PVC yang macet dalam status `Pending`.
- [ ] Mengatasi masalah `Multi-Attach error for volume`.
- [ ] Melakukan ekspansi volume PVC secara online tanpa mematikan aplikasi.
- [ ] Membuat snapshot volume menggunakan `VolumeSnapshot` dan me-restore snapshot ke PVC baru.

---
[⬅️ Module 02: StorageClasses & CSI Drivers](./Module-02-StorageClasses-Dynamic-Provisioning-dan-CSI-Drivers.md) | [📋 Silabus Induk](../README.md) | [BAB 08 Module 01: RBAC & Least Privilege ➡️](../BAB-08-Keamanan-Cluster-RBAC-dan-Admission-Controllers/Module-01-RBAC-Roles-ClusterRoles-dan-Least-Privilege.md)
---
