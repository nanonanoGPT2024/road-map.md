---
[⬅️ Module 02: Autoscaling HPA, VPA, & Karpenter](./Module-02-Autoscaling-HPA-VPA-dan-Karpenter.md) | [📋 Silabus Induk](../README.md) | [BAB 10 Module 01: Helm v3 vs Kustomize ➡️](../BAB-10-Packaging-GitOps-dan-Troubleshooting/Module-01-Helm-v3-vs-Kustomize-Package-Management.md)
---

# BAB 09: Scheduling Lanjutan & Autoscaling (HPA, VPA, Karpenter) — Quiz & Chapter Challenge

Dokumen ini berisi pengujian pemahaman konseptual, analisis skenario penjadwalan komputasi dan elastisitas cloud, serta tantangan implementasi sistematis untuk BAB 09.

---

## Bagian 1: Quiz Konseptual Dasar (5 Soal)

### Soal 1
Dalam dua fase utama algoritma `kube-scheduler`, apa yang dilakukan oleh fase *Filtering (Predicates)*?
- A. Memberikan nilai peringkat 0 - 100 pada setiap node.
- B. Menyaring dan mengeliminasi seluruh node yang tidak memenuhi kriteria minimal Pod (seperti kapasitas CPU/RAM yang kurang, atau Taint yang tidak ditoleransi).
- C. Memanggil API cloud provider untuk memesan virtual machine baru.
- D. Mengubah ukuran partisi disk filesystem Linux.

### Soal 2
Jika sebuah Node diberi Taint dengan efek `NoExecute`, apa yang terjadi pada Pod yang SUDAH berjalan di Node tersebut jika Pod tersebut tidak memiliki toleration yang cocok?
- A. Pod tetap berjalan sampai selesai, namun tidak ada pod baru yang dijadwalkan.
- B. Pod akan langsung di-evict (diusir/dihapus) dari node tersebut oleh node lifecycle controller.
- C. Pod diturunkan alokasi CPU-nya menjadi 0.
- D. Pod otomatis dipindahkan ke namespace `kube-system`.

### Soal 3
Apa arti dari parameter `maxSkew: 1` dalam spesifikasi `topologySpreadConstraints`?
- A. Jumlah Pod maksimal yang boleh dibuat adalah 1 replika.
- B. Selisih absolut jumlah Pod yang cocok antara domain topologi (misal: Availability Zone) yang memiliki Pod terbanyak dan domain yang memiliki Pod paling sedikit tidak boleh lebih dari 1.
- C. Kubelet hanya boleh menggunakan 1 core CPU.
- D. Pod hanya boleh mengalami restart maksimal 1 kali dalam 24 jam.

### Soal 4
Jika Deployment Anda saat ini memiliki 4 replika dengan rata-rata konsumsi CPU 80%, dan Anda mengonfigurasi HPA dengan target utilisasi CPU 50%, berapakah jumlah desired replika yang dihitung oleh formula HPA?
- A. 5 replika
- B. 6 replika
- C. 7 replika
- D. 8 replika

### Soal 5
Mengapa arsitektur Karpenter jauh lebih cepat dan hemat biaya dibandingkan Cluster Autoscaler (CAS) tradisional pada cloud seperti AWS?
- A. Karpenter tidak memerlukan instalasi di cluster.
- B. Karpenter bekerja secara *Group-less*, mengamati langsung Pod Pending, dan memanggil EC2 API untuk meluncurkan tipe instance yang pas (*just-in-time bin-packing*) dalam hitungan 30-45 detik tanpa terikat Auto Scaling Group (ASG).
- C. Karpenter hanya bisa dijalankan di komputer lokal developer.
- D. Karpenter menonaktifkan pemeriksaan etcd.

---

## Bagian 2: Quiz Skenario & Troubleshooting Tingkat Menengah (5 Soal)

### Soal 6
Sebuah tim SRE mengonfigurasi HPA dan VPA secara simultan pada Deployment yang sama, keduanya menargetkan metrik pemakaian CPU. Apa yang akan terjadi pada cluster saat traffic mulai meningkat?
- A. Sistem akan berjalan dua kali lebih cepat.
- B. Terjadi kondisi *race condition* (konflik fatal): VPA akan menaikkan alokasi CPU Pod, sedangkan HPA akan menambah jumlah Pod, memicu eskalasi resource tak terkendali (*flapping & over-provisioning*).
- C. Kube-apiserver akan otomatis menonaktifkan VPA.
- D. Tidak ada dampak apapun.

### Soal 7
Workload background consumer membaca pesan dari antrean Kafka. Pada malam hari antrean benar-benar kosong (0 pesan). SRE ingin agar jumlah Pod consumer menjadi 0 replika (*Scale-to-Zero*) dan otomatis naik ke 10 replika saat ada pesan masuk. Komponen apa yang harus diimplementasikan?
- A. DaemonSet standar
- B. KEDA (Kubernetes Event-driven Autoscaling) dengan trigger Kafka ScaledObject
- C. Static Pods
- D. NodeAffinity soft

### Soal 8
Setelah terjadi lonjakan traffic sesaat selama 1 menit, HPA men-scale up dari 2 ke 15 Pod. Dua menit kemudian traffic normal kembali, dan HPA langsung mematikan 13 Pod. Sesaat kemudian traffic melonjak lagi. Fenomena osilasi ini disebut *thrashing/flapping*. Bagaimana cara mencegahnya secara elegan?
- A. Menghapus objek HPA.
- B. Menambahkan konfigurasi `behavior.scaleDown.stabilizationWindowSeconds: 300` agar HPA menahan keputusan penurunan pod selama minimal 5 menit.
- C. Mengurangi RAM worker node.
- D. Mengubah Ingress timeout menjadi 1 detik.

### Soal 9
Pod Machine Learning memiliki konfigurasi NodeAffinity berikut:
```yaml
nodeAffinity:
  requiredDuringSchedulingIgnoredDuringExecution:
    nodeSelectorTerms:
      - matchExpressions:
          - key: accelerator
            operator: In
            values: ["nvidia-a100"]
```
Namun, seluruh worker node dengan label `accelerator=nvidia-a100` memiliki taint:
`dedicated=gpu:NoSchedule`.
Pod tersebut tidak memiliki blok `tolerations`. Apa status Pod setelah di-apply?
- A. `Running` di node A100.
- B. `Pending`, karena meskipun lolos NodeAffinity, Pod gagal di tahap pemeriksaan Taints & Tolerations pada fase Filtering.
- C. `CrashLoopBackOff`.
- D. `Completed`.

### Soal 10
SRE menjalankan `kubectl drain worker-01`. Perintah tersebut terhenti (*blocked*) dan menampilkan error:
`cannot delete Pods with local storage: ... (use --delete-emptydir-data to override)`.
Mengapa Kubernetes menahan proses drain tersebut secara default?
- A. Menjaga keselamatan data pada volume `emptyDir` agar operator sadar bahwa data lokal di node tersebut akan terhapus permanen saat pod di-evict.
- B. Node hard drive sedang mengalami bad sector.
- C. Kubelet menolak perintah shutdown.
- D. ServiceAccount drain tidak memiliki wewenang cluster-admin.

---

## Bagian 3: Skenario Kasus Arsitektur Tingkat Lanjut (3 Soal)

### Skenario 1: Multi-AZ Disaster Recovery & High Availability Distribution
Aplikasi Core Banking memiliki 12 replika microservice yang tersebar di 3 Availability Zone AWS (`ap-southeast-1a`, `ap-southeast-1b`, `ap-southeast-1c`).
Rancang konfigurasi spesifikasi Pod yang memastikan:
1. Pod tersebar merata di 3 zona dengan `maxSkew: 1`.
2. Tidak boleh ada 2 replika Pod yang berjalan di server fisik (*hostname*) yang sama jika kapasitas node masih mencukupi (*Soft PodAntiAffinity*).
3. Pod tidak boleh dijadwalkan di Spot Instances (*Hard NodeAffinity* On-Demand).

### Skenario 2: Optimasi Biaya Ekstrim via Karpenter Spot Consolidation
Perusahaan Anda menghabiskan biaya $30,000/bulan untuk cluster EKS batch computing. Sebagian besar worker node berjalan dengan utilisasi CPU di bawah 25% di luar jam kerja.
Jelaskan bagaimana konfigurasi Karpenter NodePool (`consolidationPolicy: WhenUnderutilized` dan `consolidateAfter: 30s`) bekerja sama dengan AWS Spot Instances untuk memangkas tagihan cloud hingga 60% tanpa mengganggu workload transaksi primer!

### Skenario 3: Scale-to-Zero Video Transcoding Pipeline
Sebuah aplikasi SaaS memproses encoding video pengguna. Kadang ada 50 video masuk serentak, kadang tidak ada video selama berjam-jam.
Rancang arsitektur end-to-end yang menggabungkan:
- AWS SQS Queue
- KEDA ScaledJob / ScaledObject
- Karpenter GPU NodePool
Jelaskan alur transisi dari 0 Pod & 0 Node GPU $\rightarrow$ lonjakan 50 GPU Pods & 5 Node GPU $\rightarrow$ kembali ke 0 Node & 0 Pod secara otomatis!

---

## Bagian 4: Chapter Challenge — Production HPA v2 with Karpenter Autoscaling Fleet

### Deskripsi Tantangan
Anda diminta merancang arsitektur autoscaling enterprise untuk microservice Checkout:
1. **Deployment Manifest**:
   - Replika awal: 2.
   - Resource requests: CPU 500m, Memory 1Gi.
   - Resource limits: CPU 1000m, Memory 2Gi.
   - Topology spread constraints: `maxSkew: 1` pada `topology.kubernetes.io/zone`.
2. **HPA v2 Manifest**:
   - Target CPU: 60%.
   - Target Memory: 75%.
   - Min Replicas: 2, Max Replicas: 15.
   - Scale-up policy: Langsung lipatgandakan pod saat lonjakan (`value: 100%`).
   - Scale-down policy: Jendela stabilisasi 300 detik dengan penurunan bertahap maksimal 10% per menit.
3. **Karpenter NodePool Manifest**:
   - Mengizinkan arsitektur AMD64 dan ARM64 (Graviton).
   - Mengutamakan Spot Instances dengan fallback ke On-Demand.
   - Kebijakan konsolidasi aktif saat kapasitas menganggur.

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Dua fase `kube-scheduler`: Filtering (Predicates) dan Scoring (Priorities).
- [ ] Tiga efek Taints: `NoSchedule`, `PreferNoSchedule`, dan `NoExecute`.
- [ ] Perbedaan NodeAffinity Hard (`required`) vs Soft (`preferred`).
- [ ] Konsep perhitungan `maxSkew` pada Topology Spread Constraints.
- [ ] Rumus matematika perhitungan replika HPA.
- [ ] Mengapa HPA dan VPA tidak boleh digunakan bersamaan pada CPU/Memory.
- [ ] Kemampuan Scale-to-Zero pada KEDA.
- [ ] Keunggulan arsitektur group-less Karpenter dibandingkan Cluster Autoscaler berbasis ASG.

### Saya Tidak Perlu Menghafal:
- [ ] Nama seluruh kode produk instance EC2 AWS (r7iz, c7g, m6i-metal).
- [ ] Algoritma float point assembly internal dari kernel Linux CFS scheduler.

### Saya Harus Bisa Melakukan:
- [ ] Memasang dan melepas Taints pada Worker Node via CLI.
- [ ] Mengonfigurasi Topology Spread Constraints untuk cluster multi-AZ.
- [ ] Menulis manifest HPA v2 dengan aturan `behavior` anti-flapping.
- [ ] Mengonfigurasi ScaledObject KEDA untuk antrean pesan.
- [ ] Mengoperasikan `kubectl cordon` dan `kubectl drain` untuk pemeliharaan node tanpa downtime.

---
[⬅️ Module 02: Autoscaling HPA, VPA, & Karpenter](./Module-02-Autoscaling-HPA-VPA-dan-Karpenter.md) | [📋 Silabus Induk](../README.md) | [BAB 10 Module 01: Helm v3 vs Kustomize ➡️](../BAB-10-Packaging-GitOps-dan-Troubleshooting/Module-01-Helm-v3-vs-Kustomize-Package-Management.md)
---
