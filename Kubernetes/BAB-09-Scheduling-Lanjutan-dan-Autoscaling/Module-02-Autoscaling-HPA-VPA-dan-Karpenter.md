---
[⬅️ Module 01: Advanced Scheduling & Taints](./Module-01-Taints-Tolerations-NodeAffinity-dan-TopologySpread.md) | [📋 Silabus Induk](../README.md) | [BAB 09 Quiz & Challenge ➡️](./BAB-09-Quiz-dan-Challenge.md)
---

# Module 02: Autoscaling Ecosystem: Metrics Server, HPA v2, VPA, KEDA, & Karpenter

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Menguasai spektrum lengkap autoscaling Kubernetes: **Pod Horizontal (HPA)**, **Pod Vertical (VPA)**, **Event-Driven (KEDA)**, dan **Cluster Node (Cluster Autoscaler vs Karpenter)**.
- Menghitung target replika menggunakan rumus matematika HPA: $\lceil \text{currentReplicas} \times (\frac{\text{currentMetricValue}}{\text{desiredMetricValue}}) \rceil$.
- Mengonfigurasi `behavior.scaleDown.stabilizationWindowSeconds` guna mengeliminasi osilasi (*flapping / thrashing*).
- Menjelaskan arsitektur VPA (Recommender, Updater, Admission Webhook) dan memahami konflik fatal saat menggabungkan HPA dan VPA pada metrik yang sama.
- Mengimplementasikan skala menuju nol (*Scale-to-Zero*) berbasis antrean pesan (Kafka / SQS) menggunakan **KEDA**.
- Membandingkan arsitektur lambat berbasis Auto Scaling Group (*Cluster Autoscaler*) dengan arsitektur modern *Group-less Just-in-Time* (**Karpenter**).

---

## 2. Prerequisite
- Memahami Resource Requests dan Limits (Bab 02).
- Memahami Deployment and ReplicaSet controllers (Bab 03).
- Konsep dasar time-series metrics dan antrean pesan (Message Queues).

---

## 3. Concept
Autoscaling adalah mekanisme penyesuaian kapasitas komputasi secara otomatis berdasarkan fluktuasi beban nyata tanpa intervensi manusia.
Kubernetes membagi autoscaling ke dalam dua layer utama:
1. **Workload Layer (Pod Autoscaling)**: Menambah/mengurangi replika Pod (**HPA**), menaikkan/menurunkan alokasi CPU & RAM Pod (**VPA**), atau memicu komputasi berdasarkan event antrean (**KEDA**).
2. **Infrastructure Layer (Node Autoscaling)**: Menambah/mengurangi mesin virtual worker node ketika Pod tidak lagi muat di cluster (**Cluster Autoscaler** atau **Karpenter**).

```
+-----------------------------------------------------------------------------------+
|                        KUBERNETES AUTOSCALING SPECTRUM                            |
|                                                                                   |
|  [ Ingress Traffic / Message Queue ]                                              |
|            |                                                                      |
|            v                                                                      |
|  +-----------------------------------------------------------------------------+  |
|  | 1. WORKLOAD LAYER (Pod Level)                                               |  |
|  |                                                                             |  |
|  |   [ HPA v2 ]              [ KEDA ]                     [ VPA ]              |  |
|  |   CPU/RAM %              Kafka/SQS Lag               Right-sizing           |  |
|  |   QPS / Latency          Scale-to-Zero               CPU & Memory           |  |
|  |         |                      |                           |                |  |
|  |         +----------+-----------+                           |                |  |
|  |                    |                                       |                |  |
|  |                    v (Increases Replicas)                  v (Bigger Pods)  |  |
|  |            [ Pod 1 ] [ Pod 2 ] [ Pod 3 ] [ Pod N ] (Pending: Out of RAM!)   |  |
|  +------------------------------------------------------------|----------------+  |
|                                                               |                   |
|                                                               v                   |
|  +-----------------------------------------------------------------------------+  |
|  | 2. INFRASTRUCTURE LAYER (Node Level)                                        |  |
|  |                                                                             |  |
|  |   [ Karpenter Node Autoscaler ] (Direct Cloud API in 40s)                   |  |
|  |   - Observes Unschedulable Pending Pods                                     |  |
|  |   - Group-less bin-packing: Launches exact EC2 instance (c6i.2xlarge / Spot)|  |
|  |   - Automated consolidation & cost optimization                             |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 4. Why?
Mengapa autoscaling sangat krusial bagi arsitektur cloud-native modern?
1. **Efisiensi Biaya (*Cost Optimization*)**: Menghindari alokasi berlebih (*over-provisioning*) server yang menganggur di malam hari. Cluster menyusut saat traffic sepi dan hanya membayar apa yang dipakai (*pay-as-you-go*).
2. **Resiliensi Lonjakan Traffic (*Surge Resilience*)**: Menghadapi lonjakan flash sale atau kampanye pemasaran tanpa menyebabkan timeout HTTP 504 Gateway.
3. **Mencegah Out-of-Memory (OOM) Crash**: Pod secara otomatis diperbesar kapasitasnya atau ditambah jumlahnya sebelum penggunaan memory mencapai batas limit 100%.

---

## 5. What?

### A. Horizontal Pod Autoscaler (HPA v2)
Controller di `kube-controller-manager` yang secara berkala (default tiap 15 detik) mengevaluasi metrik dari Metrics Server atau Prometheus Adapter.

**Rumus Matematis HPA**:
$$\text{Desired Replicas} = \left\lceil \text{Current Replicas} \times \left( \frac{\text{Current Metric Value}}{\text{Target Metric Value}} \right) \right\rceil$$

*Contoh Kasus*:
- Current Replicas = 3
- Target CPU Utilization = 50%
- Current CPU Utilization = 85%
$$\text{Desired Replicas} = \left\lceil 3 \times \left( \frac{85}{50} \right) \right\rceil = \lceil 3 \times 1.7 \rceil = \lceil 5.1 \rceil = 6 \text{ Replika}$$

### B. Vertical Pod Autoscaler (VPA)
Mengubah ukuran CPU dan Memory request/limits container secara dinamis.
- **Komponen VPA**:
  1. `VPA Recommender`: Mempelajari konsumsi historis resource dan menghasilkan rekomendasi.
  2. `VPA Updater`: Mematikan Pod lama yang ukurannya tidak sesuai.
  3. `VPA Admission Controller`: Menginjeksi CPU/Memory baru saat Pod dibuat ulang oleh Deployment controller.
- **Mode VPA**: `Off` (hanya saran), `Initial` (hanya saat Pod pertama kali dibuat), `Recreate` (evict pod dan update).

> [!WARNING]
> **ATURAN EMAS**: Jangan gunakan HPA dan VPA secara bersamaan pada metrik CPU atau Memory yang sama! Keduanya akan bertarung (*race condition*): VPA akan menaikkan alokasi resource pod, sementara HPA akan menambah jumlah pod, menyebabkan cluster berputar dalam loop eskalasi tanpa henti.

### C. Event-Driven Autoscaling (KEDA)
HPA standar tidak bisa melakukan *Scale-to-Zero* (0 ke 1 replika) dan kesulitan merespons metrik eksternal antrean. KEDA mengisi celah ini:
- Mengaktifkan Pod dari 0 replika ketika ada pesan masuk ke Kafka Topic, RabbitMQ Queue, atau AWS SQS.
- Menyerahkan pengelolaan skala ke HPA saat replika $\ge 1$.
- Menurunkan replika kembali ke 0 saat antrean kosong selama periode pendinginan (*cooldown*).

### D. Node Autoscaler: Cluster Autoscaler (CAS) vs Karpenter

| Aspek | Cluster Autoscaler (CAS Legacy) | Karpenter (Modern Standard) |
|---|---|---|
| **Mekanisme** | Terikat pada AWS Auto Scaling Groups (ASG) | **Group-less** (Memanggil langsung EC2 CreateFleet API) |
| **Kecepatan Provisioning** | Lambat (3 - 8 menit) | **Sangat Cepat (30 - 45 detik)** |
| **Pilihan Instance Type** | Kaku (Hanya instance type yang didefinisikan di ASG) | **Dinamis & Cerdas** (Menganalisis CPU/RAM/Spot Pod dan memilih dari ribuan SKU instance) |
| **Konsolidasi / Bin-Packing** | Terbatas pada penghapusan node kosong | **Agresif**: Menggabungkan pod ke instance lebih murah secara otomatis |
| **Manajemen Spot** | Rumit (Butuh banyak ASG terpisah per AZ dan tipe) | Native & terintegrasi dengan Spot Interruption Handler |

---

## 6. How?

### A. Manifest HPA v2 dengan Advanced Scaling Behavior
Mencegah osilasi dengan jendela stabilisasi (*stabilizationWindowSeconds*):

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: payment-api-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: payment-api
  minReplicas: 2
  maxReplicas: 20
  metrics:
    # 1. Metrik Resource Standar: CPU 70%
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    # 2. Metrik Resource: Memory 80%
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0 # Langsung scale up tanpa jeda saat ada lonjakan
      policies:
        - type: Percent
          value: 100 # Maksimal melipatgandakan replika per 15 detik
          periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300 # Tahan selama 5 menit sebelum menurunkan pod (anti-flapping!)
      policies:
        - type: Percent
          value: 10 # Turunkan maksimal 10% replika per menit
          periodSeconds: 60
```

### B. Manifest Karpenter NodePool & EC2NodeClass (Karpenter v1.0+)

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: general-compute-pool
spec:
  template:
    spec:
      requirements:
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64", "arm64"]
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"] # Utamakan Spot, fallback ke On-Demand
        - key: node.kubernetes.io/instance-category
          operator: In
          values: ["c", "m", "r"]
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: default-ec2-class
  limits:
    cpu: 1000 # Batas maksimal seluruh cluster
    memory: 4000Gi
  disruption:
    consolidationPolicy: WhenUnderutilized # Otomatis matikan node yang sepi
    consolidateAfter: 30s
---
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: default-ec2-class
spec:
  amiFamily: AL2023
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: "production-cluster"
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: "production-cluster"
```

---

## 7. Analogy
Bayangkan **Armada Taksi Online Bandara**:
- **HPA**: Menambah jumlah mobil taksi saat antrean penumpang bertambah panjang.
- **VPA**: Mengganti mobil sedan kecil menjadi minivan berkapasitas besar jika penumpang membawa koper raksasa.
- **KEDA**: Sopir taksi mulai dipanggil dari pangkalan ketika sistem mendeteksi jadwal mendaratnya 5 pesawat jumbo (**Event-driven anticipatory scaling**).
- **Cluster Autoscaler**: Menelepon dealer mobil untuk merakit mobil baru dari katalog standar (butuh waktu lama).
- **Karpenter**: Algoritma cerdas yang langsung menyewa mobil paling pas di sekitar bandara (sedan, SUV, atau bus Spot murah) dalam 30 detik sesuai jumlah penumpang yang terlantar di lobi.

---

## 8. Diagram

```
+---------------------------------------------------------------------------------+
|                   KARPENTER JUST-IN-TIME PROVISIONING FLOW                      |
+---------------------------------------------------------------------------------+

User Traffic Spike ---> HPA scales Deployment from 2 to 20 Pods
                                 |
                                 v
                 10 Pods Scheduled on existing nodes
                 10 Pods PENDING (Insufficient CPU & Memory)
                                 |
                                 v
       +---------------------------------------------------+
       | Karpenter Controller (Watches Pending Pods)       |
       |                                                   |
       | 1. Evaluates Pending Pod requirements:            |
       |    - Total CPU: 18 Cores, Total RAM: 36 GiB       |
       |    - Topology: Zone ap-southeast-1a & 1b          |
       |    - Architecture: arm64 preferred                |
       |                                                   |
       | 2. Bin-Packing Optimization:                      |
       |    Best match: 1x c7g.4xlarge (Spot Instance)     |
       |    (Cheaper by 65% than 5x small instances)       |
       |                                                   |
       | 3. Calls AWS EC2 API: CreateFleet()               |
       +---------------------------------------------------+
                                 | (Takes ~35 seconds)
                                 v
           New Worker Node Joined Cluster & Ready!
                                 |
                                 v
           kube-scheduler binds all 10 Pending Pods!
```

---

## 9. Simple Example: KEDA ScaledObject (Scale-to-Zero SQS Queue)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: sqs-worker-scaler
  namespace: background-jobs
spec:
  scaleTargetRef:
    name: image-processing-worker
  minReplicaCount: 0 # SCALE TO ZERO saat queue kosong!
  maxReplicaCount: 30
  cooldownPeriod: 300
  triggers:
    - type: aws-sqs-queue
      metadata:
        queueURL: https://sqs.ap-southeast-1.amazonaws.com/123456789012/task-queue
        queueLength: "5" # Tambah 1 pod setiap ada kelipatan 5 pesan antrean
        awsRegion: "ap-southeast-1"
```

---

## 10. Practical Example: Mencegah Flapping (*Anti-Thrashing*)
Flapping terjadi saat traffic naik-turun cepat: HPA men-scale up ke 10 pod, 1 menit kemudian traffic turun sedikit sehingga HPA langsung men-scale down ke 2 pod, lalu traffic naik lagi. Siklus bunuh-hidup container ini membebani database dan menghabiskan CPU.

**Solusi**:
1. Pasang `stabilizationWindowSeconds: 300` pada `scaleDown`.
2. HPA akan mengamati metrik selama 5 menit terakhir dan **hanya mengambil nilai tertinggi** yang tercatat selama jendela waktu tersebut sebelum memutuskan untuk mematikan Pod.

---

## 11. Real World Example: E-Commerce Black Friday Auto-Architecture
Sebuah platform e-commerce menghadapi lonjakan traffic 15x lipat dalam waktu 10 menit saat tengah malam promosi 11.11:
1. **Pod Layer**: HPA dikonfigurasi menggunakan metrik ganda: target CPU 65% dan target kustom HTTP Request Rate (`requests-per-second: 200` via Prometheus Adapter).
2. **Cluster Layer**: Karpenter dikonfigurasi dengan fallback Spot ke On-Demand. Ketika stok Spot instance di region cloud habis (*Spot capacity pool exhausted*), Karpenter otomatis beralih memesan On-Demand instance dalam 40 detik.
3. **Graceful Shutdown**: Pod dilengkapi dengan `preStop` hook sleep 15 detik dan `terminationGracePeriodSeconds: 45` agar transaksi in-flight checkout tidak terputus saat scale-down terjadi.

---

## 12. Trade-offs

| Teknologi | Keunggulan Utama | Pertimbangan / Risiko |
|---|---|---|
| **HPA** | Standar Kubernetes bawaan, sangat stabil | Terbatas pada metrik time-series, tidak bisa scale-to-zero |
| **VPA** | Memperbaiki alokasi request/limits yang ngawur | Mode `Recreate` mematikan Pod untuk mengubah ukuran RAM |
| **KEDA** | Sangat reaktif terhadap antrean, scale-to-zero | Membutuhkan CRD dan operator tambahan di cluster |
| **Karpenter** | Kecepatan provision ekstrim, efisiensi bin-packing | Memerlukan setup IAM Role/IRSA yang tepat di cloud provider |

---

## 13. When To Use
- Gunakan **HPA v2** untuk seluruh stateless REST API, gRPC service, dan web frontend.
- Gunakan **KEDA** untuk async worker yang memproses pesan dari Kafka, RabbitMQ, Redis Streams, atau AWS SQS.
- Gunakan **Karpenter** untuk cluster Kubernetes skala menengah hingga enterprise (menggantikan Cluster Autoscaler) untuk memangkas tagihan cloud dan mempercepat elastisitas.

---

## 14. When NOT To Use
- **JANGAN** menggunakan HPA pada StatefulSet database master-slave (seperti single-primary MySQL atau PostgreSQL) tanpa custom controller operator, karena menambah replika secara acak akan merusak replikasi data transaksi.
- Jangan menggunakan `stabilizationWindowSeconds: 0` pada konfigurasi `scaleDown`.

---

## 15. Common Mistakes
1. **Lupa Menentukan `resources.requests` pada Container**: Jika sebuah Pod tidak memiliki `resources.requests.cpu`, HPA **TIDAK AKAN BISA** menghitung persentase utilisasi CPU, dan status HPA akan selalu menampilkan `unknown/70%`.
2. **Menyetel Target Utilisasi Terlalu Tinggi (misal 95%)**: Jika target CPU diset 95%, saat traffic melonjak tiba-tiba, container akan mengalami CPU throttling atau crash sebelum Pod replika baru selesai booting (*cold-start latency*). Target yang ideal adalah 60-75%.
3. **Mengabaikan Node Quota di Cloud Provider**: Karpenter mencoba membuat 50 instance baru, tetapi akun AWS Anda mencapai batas `vCPU service quota limit`, menyebabkan seluruh Pod pending selamanya.

---

## 16. Best Practices
- **Must Have**: Selalu tetapkan `resources.requests` dan `resources.limits` pada semua container yang ditargetkan oleh HPA.
- **Recommended**: Tetapkan `minReplicas` minimal bernilai `2` (jangan `1`) pada Deployment produksi demi ketersediaan High Availability selama proses rolling update.
- **Advanced**: Implementasikan `consolidationPolicy: WhenUnderutilized` pada Karpenter untuk menghemat biaya cloud hingga 40% di luar jam kerja.
- **Avoid**: Menentukan `maxReplicas` tanpa batas pada HPA, yang dapat menguras kuota IP subnet VPC atau membengkakkan tagihan cloud tanpa kendali.

---

## 17. Troubleshooting Guide
```
Masalah: HPA TARGETS bernilai "<unknown>/70%".
Penyebab 1: Pod tidak memiliki spesifikasi resources.requests.cpu.
Penyebab 2: Metrics Server belum terpasang di cluster atau crash.
Diagnosa : kubectl top pods
           kubectl describe hpa <hpa-name>
Solusi   : Tambahkan blok resources.requests pada manifest Deployment dan pastikan 'kubectl top pods' mengembalikan angka konsumsi CPU.

Masalah: Karpenter tidak membuat node baru padahal ada banyak Pod Pending.
Penyebab : Pod memiliki toleration atau nodeSelector yang tidak didukung oleh NodePool Karpenter, atau izin IAM Role Karpenter ditolak.
Diagnosa : kubectl logs -n karpenter -l app.kubernetes.io/name=karpenter --tail=100
Solusi   : Periksa field requirements di NodePool agar mencakup arsitektur dan zona yang diminta Pod.
```

---

## 18. Exercise
1. Deploy aplikasi web sederhana dengan Deployment dan Service.
2. Buat HPA v2 dengan target CPU 50%, minReplicas 2, maxReplicas 6.
3. Jalankan load testing menggunakan container generator load (`busybox` looping HTTP GET) dan amati proses scaling via `kubectl get hpa -w`.

---

## 19. Challenge
Rancang pipeline arsitektur pemrosesan video di mana:
1. Video yang diunggah masuk ke AWS SQS queue.
2. KEDA men-scale worker transcode dari 0 hingga 50 replika berdasarkan kedalaman antrean.
3. Karpenter secara otomatis memesan EC2 GPU Spot Instances hanya saat antrean terisi, dan otomatis menghapus seluruh instance GPU ketika antrean kembali 0 selama 2 menit. Tulis seluruh spesifikasi manifest deklaratifnya!

---

## 20. Summary
Ekosistem autoscaling Kubernetes modern menyelaraskan kebutuhan komputasi dari level request aplikasi hingga level penyediaan mesin fisik IaaS. Kombinasi HPA v2 untuk workload stateless, KEDA untuk pola arsitektur event-driven, dan Karpenter untuk penyediaan node just-in-time menghadirkan ketahanan sistem yang elastis, adaptif, dan memiliki efisiensi biaya kelas enterprise.

---
[⬅️ Module 01: Advanced Scheduling & Taints](./Module-01-Taints-Tolerations-NodeAffinity-dan-TopologySpread.md) | [📋 Silabus Induk](../README.md) | [BAB 09 Quiz & Challenge ➡️](./BAB-09-Quiz-dan-Challenge.md)
---
