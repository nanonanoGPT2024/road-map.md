---
[⬅️ BAB 08 Quiz & Challenge](../BAB-08-Keamanan-Cluster-RBAC-dan-Admission-Controllers/BAB-08-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Autoscaling HPA, VPA, & Karpenter ➡️](./Module-02-Autoscaling-HPA-VPA-dan-Karpenter.md)
---

# Module 01: Advanced Scheduling: Taints, Tolerations, Node/Pod Affinity, & Topology Spread Constraints

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Menguasai alur kerja internal dua fase `kube-scheduler`: *Filtering (Predicates)* $\rightarrow$ *Scoring (Priorities)* $\rightarrow$ *Reserve* $\rightarrow$ *Bind*.
- Mengimplementasikan konsep repulsi (penolakan) menggunakan **Taints & Tolerations** dengan efek `NoSchedule`, `PreferNoSchedule`, dan `NoExecute` (beserta `tolerationSeconds`).
- Mengarahkan penempatan workload ke hardware spesifik (GPU, high-memory, ARM64) menggunakan **NodeAffinity** (*Hard* vs *Soft*).
- Mengatur ko-lokasi dan isolasi antar microservice menggunakan **PodAffinity** dan **PodAntiAffinity**.
- Mencegah kegagalan datacenter tunggal dengan mendistribusikan Pod secara merata lintas Availability Zone menggunakan **Topology Spread Constraints** (`maxSkew`).
- Melakukan operasi pemeliharaan node secara aman via `kubectl cordon` dan `kubectl drain`.

---

## 2. Prerequisite
- Memahami arsitektur internal Kubernetes Control Plane (Bab 01).
- Memahami siklus hidup Pod dan Workload Controllers (Bab 02 & Bab 03).
- Konsep dasar topologi datacenter: Hostname, Rack, Availability Zone, dan Region.

---

## 3. Concept
Secara default, `kube-scheduler` bertindak sebagai "makelar komputasi" yang adil. Scheduler mencari Node mana pun yang memiliki kapasitas CPU dan Memory yang mencukupi untuk menampung Pod.
Namun, pada lingkungan enterprise skala besar, penempatan acak ini memicu masalah serius:
- Workload analitik GPU terjadwal di node standar tanpa kartu grafis.
- Semua 5 replika database berada di 1 mesin fisik yang sama; jika mesin tersebut terbakar, seluruh sistem down total (*Single Point of Failure*).
- Pod batch CPU-intensive menguras resource tetangganya yang melayani transaksi HTTP perbankan (*noisy neighbor*).

Kubernetes menyediakan serangkaian fitur penjadwalan tingkat lanjut (*Advanced Scheduling Primitives*) untuk mengontrol secara presisi di mana Pod boleh atau tidak boleh dijalankan.

```
                      KUBE-SCHEDULER PIPELINE
                                 |
                          [ Pending Pod ]
                                 |
                                 v
        ====================================================
        | FASE 1: FILTERING (Predicates)                   |
        | - Check CPU / Memory capacity                    |
        | - Evaluate Taints vs Tolerations                 |
        | - Check NodeAffinity (requiredDuringScheduling)  |
        | - Eliminate unviable nodes                       |
        ====================================================
                                 | (Survivors)
                                 v
        ====================================================
        | FASE 2: SCORING (Priorities)                     |
        | - Evaluate NodeAffinity (preferred weights)      |
        | - Evaluate PodAntiAffinity spread                |
        | - Evaluate TopologySpread (maxSkew calculation)  |
        | - Calculate Rank 0 - 100 per Node                |
        ====================================================
                                 | (Winner: Highest Score)
                                 v
        ====================================================
        | FASE 3: BINDING                                  |
        | - Write spec.nodeName to etcd                    |
        | - Kubelet on target node starts the Pod          |
        ====================================================
```

---

## 4. Why?
Mengapa penjadwalan lanjutan sangat penting?
1. **High Availability & Fault Tolerance**: Menjamin bahwa ketika satu Availability Zone (AZ) di AWS/GCP padam, replika aplikasi di 2 AZ lainnya tetap melayani traffic tanpa interupsi.
2. **Dedicated / Isolated Compute Pools**: Menyisihkan kumpulan server khusus (misal: node bersertifikasi PCI-DSS untuk modul pembayaran, atau node berharga murah Spot Instances untuk background batch worker).
3. **Optimasi Latency Jaringan**: Mendekatkan microservice yang berkomunikasi intensif (misal API gateway dan Redis cache lokal) di node fisik atau rack yang sama (*co-location*).

---

## 5. What?

### A. Taints & Tolerations (Node Repulsion)
Taint dipasang pada **Node** untuk menolak Pod. Toleration dipasang pada **Pod** agar diizinkan berjalan di Node yang memiliki Taint.
*Analogi: Taint adalah racun serangga pada tanaman, Toleration adalah gen kekebalan pada serangga tertentu.*

Tiga Efek Taint:
1. **`NoSchedule`**: Jika Pod tidak memiliki toleration yang cocok, Pod TIDAK AKAN dijadwalkan ke node ini. (Pod yang sudah terlanjur jalan tidak diusik).
2. **`PreferNoSchedule`**: Scheduler akan berusaha keras menghindari penempatan Pod ke node ini, kecuali jika tidak ada alternatif node lain di cluster (*soft repulsion*).
3. **`NoExecute`**: Jika Pod tidak memiliki toleration, Pod dilarang dijadwalkan. Jika Pod SUDAH berjalan di node tersebut saat taint dipasang, Pod akan **langsung di-evict (diusir/dihapus)** dari node.
   - `tolerationSeconds`: Menentukan durasi penundaan eviksi saat node bermasalah (misal: tolerir selama 300 detik saat node `NotReady` sebelum memindahkan Pod).

### B. NodeAffinity (Node Attraction)
Mengikat Pod ke Node berdasarkan label Node.
- **`requiredDuringSchedulingIgnoredDuringExecution`** (*Hard Affinity*): Syarat mutlak. Jika tidak ada node yang cocok dengan label, Pod akan berstatus `Pending`.
- **`preferredDuringSchedulingIgnoredDuringExecution`** (*Soft Affinity*): Preferensi dengan bobot (*weight 1-100*). Scheduler memprioritaskan node yang cocok, namun jika penuh, Pod tetap dijadwalkan di node lain.

### C. PodAffinity & PodAntiAffinity
- **`PodAffinity`**: Menjadwalkan Pod dekat dengan Pod lain (misal di Hostname atau AZ yang sama).
- **`PodAntiAffinity`**: Menjauhkan Pod dari Pod lain yang memiliki label serupa guna mencegah SPOF.

### D. Topology Spread Constraints
Fitur modern standar emas untuk High Availability. Mengontrol distribusi Pod agar selisih jumlah Pod antar domain kegagalan (*skew*) tidak melebihi batas:
$$\text{Skew} = (\text{Jumlah Pod di Domain Terbanyak}) - (\text{Jumlah Pod di Domain Terendah})$$
- `maxSkew`: Batas maksimal selisih yang diizinkan (biasanya bernilai `1`).
- `topologyKey`: Label pembagi domain (contoh: `topology.kubernetes.io/zone` untuk lintas AZ, atau `kubernetes.io/hostname` untuk lintas server fisik).
- `whenUnsatisfiable`: `DoNotSchedule` (Hard) atau `ScheduleAnyway` (Soft).

---

## 6. How?

### A. Konfigurasi Taints & Tolerations
Memasang taint khusus GPU pada worker node:
```bash
kubectl taint nodes node-gpu-01 dedicated=gpu-workload:NoSchedule
```

Pod yang ingin menggunakan node tersebut wajib mendefinisikan `tolerations`:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: ml-training-pod
spec:
  tolerations:
    - key: "dedicated"
      operator: "Equal"
      value: "gpu-workload"
      effect: "NoSchedule"
  containers:
    - name: pytorch
      image: pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime
```

### B. Konfigurasi Topology Spread Constraints (Penyebaran Lintas Multi-AZ)
Mendistribusikan 6 replika Pod microservice secara seimbang di 3 Availability Zone:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: production
spec:
  replicas: 6
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
    spec:
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: order-service
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app: order-service
      containers:
        - name: web
          image: order-service:v1.2.0
```

---

## 7. Analogy
Bayangkan **Asrama Mahasiswa & Pembagian Kamar**:
- **Taint `NoSchedule`**: Kamar Khusus Dosen. Mahasiswa biasa ditolak masuk, kecuali memegang surat izin asisten dosen (**Toleration**).
- **NodeAffinity Hard**: Mahasiswa jurusan Teknik Kimia diwajibkan tinggal di Gedung B yang dekat dengan laboratorium bahan berbahaya.
- **PodAntiAffinity**: Dua mahasiswa yang bermusuhan (**PodAntiAffinity**) tidak boleh ditempatkan di kamar yang sama.
- **Topology Spread Constraints (`maxSkew: 1`)**: Panitia asrama membagi 6 delegasi mahasiswa baru secara adil: Lantai 1 dapat 2 orang, Lantai 2 dapat 2 orang, Lantai 3 dapat 2 orang. Dilarang menumpuk 5 orang di Lantai 1 sementara Lantai 3 kosong.

---

## 8. Diagram

```
+---------------------------------------------------------------------------------+
|               TOPOLOGY SPREAD CONSTRAINTS (maxSkew: 1 across AZs)               |
+---------------------------------------------------------------------------------+

                      KUBERNETES REGION: ap-southeast-1
                                      |
         +----------------------------+----------------------------+
         |                            |                            |
         v                            v                            v
  [ AZ: zone-a ]               [ AZ: zone-b ]               [ AZ: zone-c ]
  +------------------+         +------------------+         +------------------+
  | Node: node-1     |         | Node: node-2     |         | Node: node-3     |
  | [Pod-1]  [Pod-2] |         | [Pod-3]  [Pod-4] |         | [Pod-5]  [Pod-6] |
  +------------------+         +------------------+         +------------------+
    Total Pods: 2                Total Pods: 2                Total Pods: 2

  Formula Check:
  Max Pods in any Zone = 2
  Min Pods in any Zone = 2
  Skew = 2 - 2 = 0 <= maxSkew (1) ---> [ PASS: HIGHLY RESILIENT & BALANCED ]
```

---

## 9. Simple Example: NodeAffinity Hard & Soft Combination

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: payment-backend
spec:
  affinity:
    nodeAffinity:
      # WAJIB: Node harus memiliki arsitektur AMD64
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: kubernetes.io/arch
                operator: In
                values:
                  - amd64
      # PREFERENSI: Prioritaskan node dengan tipe instance compute-optimized (c6i)
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 80
          preference:
            matchExpressions:
              - key: node.kubernetes.io/instance-type
                operator: In
                values:
                  - c6i.2xlarge
                  - c6i.4xlarge
  containers:
    - name: app
      image: payment-api:v1.0
```

---

## 10. Practical Example: Pemeliharaan Node (Cordon & Drain)
Ketika seorang System Administrator perlu melakukan upgrade kernel Linux atau security patch pada worker node:

```bash
# 1. Cordon: Tandai node sebagai 'SchedulingDisabled'.
# Tidak ada pod baru yang akan dijadwalkan ke node ini.
kubectl cordon worker-node-03

# 2. Drain: Evict (usir) semua Pod aktif secara aman ke node lain.
# Hormati PodDisruptionBudget, abaikan daemonset, hapus emptyDir storage lokal jika ada.
kubectl drain worker-node-03 --ignore-daemonsets --delete-emptydir-data --force

# 3. Lakukan maintenance / OS reboot di server fisik worker-node-03...

# 4. Uncordon: Aktifkan kembali node setelah selesai maintenance.
kubectl uncordon worker-node-03
```

---

## 11. Real World Example: Spot Instances vs On-Demand Hybrid Fleet
Pada arsitektur cloud AWS/GCP, **Spot Instances** menawarkan diskon biaya hingga 70-90%, namun dapat dimatikan oleh cloud provider dengan peringatan 2 menit (*interruption notice*).

**Strategi Scheduling Produksi**:
1. Pasang Taint pada seluruh worker node Spot: `node.kubernetes.io/instance-type=spot:PreferNoSchedule`.
2. Statefull database (Postgres, Redis) dan critical core service berjalan di On-Demand nodes (tanpa toleration spot).
3. Background async worker (RabbitMQ consumers, batch data processors) menyertakan toleration terhadap Taint Spot dan NodeAffinity Soft ke Spot nodes.
4. Hasil: Penghematan biaya cloud puluhan ribu dollar per bulan tanpa membahayakan ketersediaan database primer.

---

## 12. Trade-offs

| Fitur | Kelebihan | Risiko / Kelemahan |
|---|---|---|
| **Taints & Tolerations** | Isolasi pool node fisik sangat tegas | Jika salah konfigurasi toleration, Pod non-spesifik bisa menyusup |
| **PodAntiAffinity Hard (`required`)** | Jaminan zero co-location pada level host | Pod akan terjebak `Pending` jika jumlah replika > jumlah worker node |
| **TopologySpreadConstraints** | Penyeimbangan fault domain sempurna | Algoritma scoring scheduler menjadi lebih lambat pada cluster > 5.000 node |
| **NodeSelector Sederhana** | Sangat mudah dibaca | Kurang fleksibel (tidak ada operator `NotIn`, `Exists`, atau weighting) |

---

## 13. When To Use
- Gunakan **Topology Spread Constraints (`maxSkew: 1`)** pada seluruh Deployment HTTP/gRPC microservice produksi yang berjalan di cloud multi-AZ.
- Gunakan **Taints `NoExecute`** untuk mengisolasi node yang sedang mengalami degradasi hardware atau pemeliharaan berkala.
- Gunakan **PodAntiAffinity Soft (`preferred`)** untuk mendistribusikan replika Pod ke server fisik yang berbeda tanpa resiko Pod menjadi `Pending` jika node terbatas.

---

## 14. When NOT To Use
- **JANGAN** menggunakan `PodAntiAffinity Hard` (`requiredDuringScheduling...`) dengan `topologyKey: kubernetes.io/hostname` jika jumlah replika Deployment Anda (misal: 20) melebihi jumlah total worker node di cluster Anda (misal: 5). Pod ke-6 dan seterusnya tidak akan pernah bisa dijadwalkan.
- Hindari memasang terlalu banyak aturan Soft Affinity yang saling bertentangan, karena akan memperlambat throughput penjadwalan (*scheduling throughput latency*).

---

## 15. Common Mistakes
1. **Lupa `tolerationSeconds` pada Taint `NoExecute`**: Jika toleration tidak menyertakan `tolerationSeconds`, Pod akan bertahan selamanya di node yang bermasalah.
2. **Typo pada `topologyKey`**: Menulis `topology.kubernetes.io/zones` (kelebihan huruf 's') alih-alih `topology.kubernetes.io/zone`. Scheduler akan gagal mengenali domain kegagalan.
3. **Mengabaikan DaemonSets saat Drain Node**: Menjalankan `kubectl drain` tanpa flag `--ignore-daemonsets` akan menyebabkan command langsung error dan membatalkan pengusiran Pod.

---

## 16. Best Practices
- **Must Have**: Pasang `PodDisruptionBudget (PDB)` sebelum melakukan `kubectl drain` untuk memastikan minimal kuota Pod selalu online saat proses eviksi.
- **Recommended**: Gabungkan `TopologySpreadConstraints` dengan `PodAntiAffinity` soft untuk ketahanan ganda (lintas AZ dan lintas Host).
- **Advanced**: Manfaatkan `nodeAffinity` berbasis arsitektur CPU (`kubernetes.io/arch: arm64` vs `amd64`) untuk memanfaatkan efisiensi prosesor AWS Graviton.
- **Avoid**: Menghapus taint bawaan Kubernetes pada Control Plane (`node-role.kubernetes.io/control-plane:NoSchedule`) kecuali pada kluster single-node pengujian.

---

## 17. Troubleshooting Guide
```
Masalah: Pod berstatus "Pending", kubectl describe menampilkan event: "0/6 nodes are available: 3 node(s) had untolerated taint, 3 node(s) didn't match PodTopologySpread".
Penyebab 1: 3 node memiliki Taint khusus yang tidak dimiliki oleh Pod.
Penyebab 2: 3 node sisanya akan melanggar aturan maxSkew jika Pod baru ditempatkan di sana.
Diagnosa : Evaluasi sebaran pod di setiap node:
           kubectl get pods -o wide --selector app=my-app
           kubectl get nodes --show-labels
Solusi   : Naikkan batas maxSkew menjadi 2, atau ubah whenUnsatisfiable menjadi ScheduleAnyway, atau tambah worker node baru di zona yang kekurangan Pod.
```

---

## 18. Exercise
1. Pasang label topologi `zone=datacenter-west-1` pada 2 node, dan `zone=datacenter-west-2` pada 2 node lainnya.
2. Tulis manifest Deployment dengan 4 replika yang memiliki `topologySpreadConstraints` dengan `maxSkew: 1` pada key `zone`.
3. Validasi dengan `kubectl get pods -o wide` bahwa masing-masing zona mendapatkan tepat 2 replika Pod.

---

## 19. Challenge
Rancang arsitektur penjadwalan hybrid di mana:
1. Workload Machine Learning hanya boleh dijadwalkan di node bertanda GPU (`gpu=nvidia:NoSchedule`).
2. Namun, jika node GPU penuh, workload boleh dialihkan ke node compute-optimized CPU sebagai fallback darurat (*Soft NodeAffinity*).
3. Buktikan cara kerja aturan tersebut menggunakan pengujian simulasi scheduler!

---

## 20. Summary
Penjadwalan tingkat lanjut di Kubernetes memindahkan kendali penempatan komputasi dari tebak-tebakan acak menjadi rekayasa deterministik. Dengan menguasai Taints & Tolerations, Node/Pod Affinity, dan Topology Spread Constraints, insinyur sistem dapat membangun cluster yang tahan gempa, efisien biaya, dan memiliki ketersediaan tinggi (*high availability*).

---
[⬅️ BAB 08 Quiz & Challenge](../BAB-08-Keamanan-Cluster-RBAC-dan-Admission-Controllers/BAB-08-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Autoscaling HPA, VPA, & Karpenter ➡️](./Module-02-Autoscaling-HPA-VPA-dan-Karpenter.md)
---
