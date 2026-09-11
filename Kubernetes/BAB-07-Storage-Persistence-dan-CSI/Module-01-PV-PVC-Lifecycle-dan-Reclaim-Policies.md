---
[⬅️ BAB 06 Quiz & Challenge](../BAB-06-Network-Security-CNI-dan-NetworkPolicies/BAB-06-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: StorageClasses & CSI Drivers ➡️](./Module-02-StorageClasses-Dynamic-Provisioning-dan-CSI-Drivers.md)
---

# Module 01: PersistentVolume (PV), PersistentVolumeClaim (PVC), Lifecycle, & Reclaim Policies

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Mengartikulasikan perbedaan fundamental antara abstraksi komputasi ephemeral (`emptyDir`, `hostPath`) dengan abstraksi persistensi decoupled (`PersistentVolume` dan `PersistentVolumeClaim`).
- Menguasai *lifecycle state machine* dari volume (`Available` $\rightarrow$ `Bound` $\rightarrow$ `Released` $\rightarrow$ `Failed`).
- Menjelaskan implementasi teknis `AccessModes` (`ReadWriteOnce`, `ReadOnlyMany`, `ReadWriteMany`, `ReadWriteOncePod`) dan batasan infrastruktur cloud block storage vs network filesystem (NFS/Ceph).
- Mengonfigurasi `ReclaimPolicy` (`Retain`, `Delete`) dan memahami mekanisme pembersihan disk fisik di level IaaS/SAN.
- Mengidentifikasi peran `VolumeBindingMode` (`Immediate` vs `WaitForFirstConsumer`) guna mencegah kegagalan scheduling lintas Availability Zone (Multi-AZ topology).
- Memahami *storage safety guarantees* seperti finalizer `kubernetes.io/pvc-protection` dan `kubernetes.io/pv-protection`.

---

## 2. Prerequisite
- Memahami Pod Lifecycle, Spec Container, dan Volume Mounts (Bab 02).
- Memahami StatefulSets dan pola `volumeClaimTemplates` (Bab 03).
- Konsep dasar block storage (AWS EBS, GCP Persistent Disk) vs shared file storage (NFS, AWS EFS).

---

## 3. Concept
Secara default, container dalam Kubernetes bersifat *ephemeral*. Jika container crash dan kubelet me-restart container tersebut, seluruh modifikasi data di layer container writable (*overlayfs*) akan terhapus.

Kubernetes memisahkan tanggung jawab penyedia infrastruktur (*Cluster Administrator*) dan pengguna resource (*Application Developer*) melalui dua sumber daya deklaratif:
1. **PersistentVolume (PV)**: Objek level cluster yang merepresentasikan alokasi penyimpanan riil (misal: SAN LUN, AWS EBS Volume, NFS Share, Ceph RBD). Objek ini dibuat oleh Administrator (secara statis) atau oleh CSI provisioner (secara dinamis). PV tidak terikat pada namespace (`Non-Namespaced`).
2. **PersistentVolumeClaim (PVC)**: Permintaan penyimpanan oleh developer (misal: "Saya butuh 50Gi storage dengan akses ReadWriteOnce"). PVC bersifat `Namespaced`.

```
+-------------------------------------------------------------+
|                     KUBERNETES CLUSTER                      |
|                                                             |
|  [ Developer Namespace ]                                    |
|         |                                                   |
|    +----+-----+       claims       +-------------------+    |
|    |   Pod    | --------------->  |        PVC        |    |
|    | (Mount)  |                    | (Size, AccessMode)|    |
|    +----+-----+                    +---------+---------+    |
|                                              |              |
| ================= pv-controller =============|============== |
|                                              v binds        |
|  [ Cluster Scope ]                 +-------------------+    |
|                                    |        PV         |    |
|                                    | (Capacity, Driver)|    |
|                                    +---------+---------+    |
|                                              | manages      |
|                                              v              |
|                                    [ Physical / Cloud LUN]  |
|                                    (EBS / Ceph / Local NVMe)|
+-------------------------------------------------------------+
```

---

## 4. Why?
Mengapa Pod tidak langsung menyematkan detail block device cloud (seperti `awsElasticBlockStore` atau `gcePersistentDisk`) langsung di dalam Pod spec?
1. **Tight Coupling & Vendor Lock-in**: Jika developer mendefinisikan ID EBS AWS langsung di Pod manifest, manifest tersebut tidak bisa di-deploy di on-premise datacenter, GCP, atau Azure tanpa mengubah source code YAML.
2. **Security & Privileged Separation**: Developer aplikasi tidak boleh memiliki wewenang membuat, menghapus, atau mengakses ID disk fisik penyimpanan storage array enterprise secara langsung.
3. **Multi-Tenancy**: Administrator dapat membatasi kuota volume (via ResourceQuota) per namespace tanpa perlu melacak setiap Pod individual.

---

## 5. What?

### A. Phase Lifecycle PV & PVC
Hubungan binding antara PV dan PVC memiliki siklus hidup 4 tahap (*two-way binding*):
```
  [ Provisioning ]
         |
         v
   +-----------+         match PVC criteria
   | Available | ----------------------------------> [ Bound ]
   +-----------+                                         |
                                                         | Pod deleted &
                                                         | PVC deleted
                                                         v
   +-----------+           admin manual clean      +-----------+
   |  Failed   | <-------------------------------- | Released  |
   +-----------+      (ReclaimPolicy: Retain)      +-----------+
                                                         |
                                                         | (ReclaimPolicy: Delete)
                                                         v
                                                    [ Deleted ]
```

1. **Available**: PV telah dialokasikan dan bebas, belum terikat pada PVC manapun.
2. **Bound**: `pv-controller` di `kube-controller-manager` mencocokkan PVC dengan PV yang sesuai, menyematkan `.spec.claimRef` pada PV dan `.spec.volumeName` pada PVC.
3. **Released**: PVC dihapus oleh user, namun resource fisik PV masih berisi data lama. Status PV menjadi `Released`. PV tidak bisa langsung di-bind oleh PVC baru sebelum data lama dibersihkan.
4. **Failed**: Proses pembersihan otomatis gagal, memerlukan intervensi administrator manual.

### B. Access Modes
- **ReadWriteOnce (RWO)**: Volume dapat di-mount sebagai Read-Write oleh **satu Node tunggal**. Cocok untuk block storage standar (AWS EBS gp3, Azure Disk) di mana disk fisik hanya bisa di-attach ke satu VM hypervisor pada satu waktu. Beberapa Pod di Node yang *sama* dapat membaca/menulis ke PV ini.
- **ReadOnlyMany (ROX)**: Volume dapat di-mount sebagai Read-Only oleh **banyak Node secara serentak**. Berguna untuk dataset referensi statis, model machine learning read-only, atau static web asset.
- **ReadWriteMany (RWX)**: Volume dapat di-mount sebagai Read-Write oleh **banyak Node secara bersamaan**. Membutuhkan sistem berkas terdistribusi jaringan (Network File System seperti NFS, AWS EFS, CephFS, GlusterFS).
- **ReadWriteOncePod (RWOP)** *(K8s v1.22+)*: Volume hanya dapat di-mount sebagai Read-Write oleh **tepat satu Pod** di seluruh cluster. Ini mencegah race condition ketika dua Pod di Node yang sama mencoba memodifikasi database engine single-process (misal embedded SQLite atau RocksDB).

### C. Reclaim Policies
- **Retain**: Ketika PVC dihapus, PV fisik dan data di dalamnya TIDAK dihapus. Status berubah menjadi `Released`. Administrator harus mencadangkan data, menghapus disk fisik secara manual, lalu menghapus objek PV.
- **Delete**: Ketika PVC dihapus, controller otomatis menghapus objek PV di Kubernetes DAN menghapus storage backend fisik (misal: API call `DeleteVolume` ke AWS EBS).
- **Recycle** *(DEPRECATED)*: Melakukan `rm -rf /volume/*` secara sederhana. Sudah digantikan oleh Dynamic Provisioning modern.

---

## 6. How?

### A. Binding Logic pada `pv-controller`
`pv-controller` secara berkala menjalankan loop rekonsiliasi:
1. Mencari PVC berstatus `Pending`.
2. Mencari PV berstatus `Available` yang memiliki:
   - `storageClassName` yang identik.
   - `accessModes` yang kompatibel (PV mendukung subset atau superset mode PVC).
   - Kapasitas PV $\ge$ Kapasitas yang diminta PVC (PV 100Gi dapat di-bind oleh PVC 20Gi jika tidak ada PV yang lebih kecil, menyebabkan *storage waste* 80Gi).
   - `selector` match label (jika didefinisikan).
3. Melakukan mutual pointer injection:
   - `PV.spec.claimRef = { namespace: pvc.namespace, name: pvc.name, uid: pvc.uid }`
   - `PVC.spec.volumeName = pv.name`
   - Mengubah status keduanya menjadi `Bound`.

### B. Finalizer Safety Guarantee
Jika user menjalankan `kubectl delete pvc my-pvc` saat Pod masih berjalan dan me-mount volume tersebut, penghapusan instan akan menyebabkan filesystem unmount mendadak dan *data corruption*.
Kubernetes mengamankan ini dengan finalizer:
- **`kubernetes.io/pvc-protection`**: Menunda penghapusan PVC hingga tidak ada Pod aktif yang me-mount PVC tersebut. PVC berstatus `Terminating`.
- **`kubernetes.io/pv-protection`**: Menunda penghapusan PV selama PV masih terikat pada PVC yang aktif.

---

## 7. Analogy
Bayangkan **PersistentVolume (PV)** seperti **Kamar Apartemen Kosong** berkapasitas 2 orang dengan fasilitas lengkap yang dimiliki oleh pengelola gedung.
**PersistentVolumeClaim (PVC)** adalah **Surat Kontrak Sewa** yang diajukan oleh calon penyewa: "Saya mencari kamar berkapasitas minimal 1 orang dengan fasilitas balkon".
Gedung (*kube-controller-manager*) mencocokkan kontrak dengan kamar yang cocok. Begitu kontrak ditandatangani, kamar tersebut berstatus `Bound` (disewa). Ketika penyewa pindah dan merobek kontrak sewa (`PVC Deleted`), status kamar menjadi `Released`. Jika aturan gedung adalah `Retain`, pengelola harus memeriksa kamar secara manual sebelum kamar bisa disewakan kembali ke orang lain.

---

## 8. Diagram

```
[ Developer ] ---> Membuat PersistentVolumeClaim (PVC)
                         |
                         v
       +------------------------------------+
       | PVC: app-data-pvc                  |
       | - Request: 10Gi                    |
       | - AccessMode: ReadWriteOnce        |
       | - StorageClass: "" (Static)        |
       +------------------------------------+
                         |
                         v (Matching Engine)
       +------------------------------------+
       | PV: manual-ebs-pv-01               |
       | - Capacity: 10Gi                   |
       | - AccessMode: ReadWriteOnce        |
       | - ReclaimPolicy: Retain            |
       | - ClaimRef: app-data-pvc           |
       +------------------------------------+
                         |
                         | Assigned to Pod
                         v
       +------------------------------------+
       | Pod: database-pod                  |
       | spec.volumes[0].persistentVolume-  |
       |   Claim.claimName: app-data-pvc    |
       | spec.containers[0].volumeMounts:   |
       |   - mountPath: /var/lib/mysql      |
       +------------------------------------+
                         |
     +-------------------+-------------------+
     | Mounted to Linux Node via Kubelet     |
     | Target Host Path:                     |
     | /var/lib/kubelet/pods/<UID>/volumes/  |
     | kubernetes.io~csi/manual-ebs-pv-01    |
     +---------------------------------------+
```

---

## 9. Simple Example (Static PV & PVC Manifest)

### Static PersistentVolume Manifest (`pv-manual.yaml`)
```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-analytics-storage-01
  labels:
    tier: high-speed
    storage-tier: nvme
spec:
  capacity:
    storage: 50Gi
  volumeMode: Filesystem
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: manual
  hostPath:
    path: /mnt/disks/nvme-pool-1
    type: DirectoryOrCreate
```

### PersistentVolumeClaim Manifest (`pvc-analytics.yaml`)
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pvc-analytics-data
  namespace: analytics
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: manual
  resources:
    requests:
      storage: 50Gi
  selector:
    matchLabels:
      tier: high-speed
```

---

## 10. Practical Example (Pod Menggunakan Volume dengan subPath)

Seringkali satu Persistent Volume besar ingin dibagi untuk beberapa folder aplikasi tanpa perlu membuat banyak PV terpisah. Fitur `subPath` memetakan sub-direktori di dalam PV ke container path.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: multi-service-db
  namespace: analytics
spec:
  volumes:
    - name: shared-analytics-volume
      persistentVolumeClaim:
        claimName: pvc-analytics-data
  containers:
    - name: mysql-engine
      image: mysql:8.0
      env:
        - name: MYSQL_ROOT_PASSWORD
          value: "SecretK8sStorage2026!"
      volumeMounts:
        - name: shared-analytics-volume
          mountPath: /var/lib/mysql
          subPath: mysql-data # Menyimpan data ke folder /mnt/disks/nvme-pool-1/mysql-data
    - name: redis-cache
      image: redis:7.2-alpine
      command: ["redis-server", "--appendonly", "yes", "--dir", "/data"]
      volumeMounts:
        - name: shared-analytics-volume
          mountPath: /data
          subPath: redis-data # Menyimpan data ke folder /mnt/disks/nvme-pool-1/redis-data
```

---

## 11. Real World Example: Multi-AZ Disaster Recovery Dilemma
Pada cluster EKS di AWS dengan 3 Availability Zone (`ap-southeast-1a`, `ap-southeast-1b`, `ap-southeast-1c`), block storage AWS EBS **hanya terikat pada satu AZ fisik spesifik**.

Jika PV statis dialokasikan di AZ `ap-southeast-1a`, dan Node di AZ `ap-southeast-1a` mengalami kehabisan resource CPU/Memory, kube-scheduler akan mencoba menjadwalkan Pod ke Node di `ap-southeast-1b`.
Hasilnya: Pod terjebak dalam kondisi `ContainerCreating` selamanya dengan event error:
`FailedAttachVolume: VolumeAttachment failed: Volume ebs-vol-xxx is in ap-southeast-1a, node is in ap-southeast-1b`.

**Solusi Arsitektur Real-World**:
1. Menggunakan `volumeBindingMode: WaitForFirstConsumer` pada StorageClass. PV tidak dibuat sebelum Pod dijadwalkan, sehingga storage otomatis dibuat di AZ yang sama dengan Node tempat Pod terpilih.
2. Menggunakan `nodeAffinity` pada objek PV statis untuk memandu scheduler:
```yaml
spec:
  nodeAffinity:
    required:
      nodeSelectorTerms:
        - matchExpressions:
            - key: topology.kubernetes.io/zone
              operator: In
              values:
                - ap-southeast-1a
```

---

## 12. Trade-offs

| Aspek | Static Provisioning (PV Manual) | Dynamic Provisioning (StorageClass) |
|---|---|---|
| **Effort Operasional** | Sangat tinggi (Admin membuat disk manual & manifest PV) | Nol (Otomatis via CSI driver) |
| **Kapasitas Pemborosan** | Sering terjadi (PVC 10Gi bind ke PV 100Gi yang ada) | Minimal (PV dibuat persis sesuai ukuran PVC) |
| **Kontrol Keamanan** | Penuh (Admin tahu persis disk mana yang dipakai) | Didelegasikan ke konfigurasi StorageClass |
| **Volume Reclaim** | Biasanya `Retain` untuk audit data perbankan | Biasanya `Delete` untuk efisiensi biaya cloud |
| **Multi-Tenancy** | Sulit di-scale untuk ratusan developer | Standar industri modern |

---

## 13. When To Use
- Gunakan **Static PV (`Retain`)** saat Anda memiliki LUN SAN enterprise lama, partisi database bare-metal yang sudah terisi terabyte data, atau compliance finansial ketat yang melarang disk dihapus otomatis oleh software.
- Gunakan **`ReadWriteOncePod`** jika Anda menjalankan single-instance stateful app yang sangat rawan terhadap *file lock corruption* saat proses rolling update berlangsung.
- Gunakan **`subPath`** untuk berbagi satu shared PV berukuran besar ke beberapa container di dalam satu Pod.

---

## 14. When NOT To Use
- **JANGAN** gunakan `hostPath` di cluster production multi-node tanpa node-affinity ketat, karena jika Pod dipindah ke node lain, data tidak akan terbawa.
- **JANGAN** menggunakan `ReadWriteMany (RWX)` dengan cara memaksakan mounting EBS/GCP-PD block disk ke multi-node secara simultan (kecuali menggunakan filesystem cluster seperti OCFS2/GFS2), karena akan merusak partition table dan filesystem superblock.

---

## 15. Common Mistakes
1. **Mengabaikan ReclaimPolicy Default**: Mengira bahwa menghapus PVC akan menyimpan disk, padahal StorageClass default cloud seringkali diset ke `Delete`, melenyapkan database produksi secara permanen.
2. **Kapasitas PV Lebih Besar dari Permintaan PVC**: PVC meminta 10Gi, tapi di cluster hanya ada PV statis 500Gi. Kubernetes akan mengikat PVC tersebut ke PV 500Gi! 490Gi sisanya hangus terbuang dan tidak bisa digunakan oleh PVC lain.
3. **Mencoba Mengubah Ukuran PV Tanpa Expand PVC**: Mengubah file YAML PV langsung di cluster tidak akan me-resize block storage atau filesystem di node Linux. Perubahan harus melalui PVC (`resources.requests.storage`).

---

## 16. Best Practices
- **Must Have**: Pasang `storageClassName: ""` pada PV/PVC statis jika Anda tidak ingin storage class default cluster menimpa proses binding statis Anda.
- **Recommended**: Pasang `volumeBindingMode: WaitForFirstConsumer` pada storage multi-AZ untuk mencegah mismatch node zone.
- **Advanced**: Implementasikan *VolumeSnapshot* terjadwal sebelum proses penghapusan PVC di environment staging/production.
- **Avoid**: Menghapus flag finalizer `kubernetes.io/pvc-protection` secara paksa (`kubectl patch ... --type merge -p '{"metadata":{"finalizers":null}}'`) saat Pod masih running, karena akan meninggalkan zombie mount di worker node Linux.

---

## 17. Troubleshooting Guide
```
Masalah: PVC berstatus "Pending" terus menerus.
Penyebab 1: Tidak ada PV yang cocok (kapasitas kurang, StorageClass beda, AccessMode tidak sesuai).
Diagnosa : kubectl describe pvc <pvc-name>
           Periksa bagian Events: "matching PV not found" atau "waiting for first consumer to be created".
Solusi   : Buat PV dengan label/StorageClass yang sesuai, atau deploy Pod konsumen jika modenya WaitForFirstConsumer.

Masalah: PV berstatus "Released" tetapi tidak mau bind ke PVC baru yang meminta nama yang sama.
Penyebab : PV masih menyimpan spesifikasi `claimRef.uid` dari PVC lama yang sudah dihapus (Retain Policy).
Diagnosa : kubectl get pv <pv-name> -o yaml | grep claimRef -A 5
Solusi   : Hapus blok `.spec.claimRef` pada PV via `kubectl edit pv <pv-name>`, status akan kembali menjadi `Available`.
```

---

## 18. Exercise
1. Buat manifest PV statis berkapasitas 25Gi, access mode `ReadWriteOnce`, reclaim policy `Retain`, dan StorageClass `database-storage`.
2. Buat PVC di namespace `finance` yang meminta 20Gi dengan StorageClass `database-storage`.
3. Validasi status binding keduanya dan amati perubahan field `claimRef` pada PV.

---

## 19. Challenge
Tulis skrip atau skenario demonstrasi di mana PVC dihapus sementara Pod konsumen masih berjalan. Amati bahwa PVC masuk ke status `Terminating` karena proteksi finalizer. Kemudian hapus Pod dan buktikan bahwa PVC baru benar-benar terhapus setelah Pod lenyap.

---

## 20. Summary
PersistentVolume (PV) dan PersistentVolumeClaim (PVC) mengabstraksi penyimpanan fisik dari siklus hidup Pod komputasi yang fana. Memahami siklus hidup (`Available`, `Bound`, `Released`), jenis akses (`RWO`, `ROX`, `RWX`, `RWOP`), dan kebijakan pengembalian (`Retain` vs `Delete`) adalah pondasi wajib sebelum mengelola sistem database skala enterprise di Kubernetes.

---
[⬅️ BAB 06 Quiz & Challenge](../BAB-06-Network-Security-CNI-dan-NetworkPolicies/BAB-06-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: StorageClasses & CSI Drivers ➡️](./Module-02-StorageClasses-Dynamic-Provisioning-dan-CSI-Drivers.md)
---
