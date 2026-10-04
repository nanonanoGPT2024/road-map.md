# Module 01: Arsitektur Control Plane, Pods, Deployments, & Service Networking

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Memahami arsitektur terdistribusi Kubernetes: **Control Plane** (`kube-apiserver`, `etcd`, `kube-scheduler`, `kube-controller-manager`) dan **Worker Nodes** (`kubelet`, `kube-proxy`, container runtime).
2. Memahami abstraksi unit komputasi terkecil: **Pods** vs **ReplicaSets** vs **Deployments** (Declarative State & Reconciliation Loop).
3. Menguasai model jaringan Kubernetes (**ClusterIP**, **NodePort**, **LoadBalancer**) dan mekanisme penemuan layanan (*Service Discovery via CoreDNS*).
4. Menganalisis strategi deployment modern: **RollingUpdate** (Zero Downtime), Recreate, dan penyesuaian parameter `maxSurge` serta `maxUnavailable`.

---

## 2. Prerequisite
- Memahami konsep dasar Docker image dan container dari [BAB 03](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-03-Containerization-Docker/Module-01-Arsitektur-Container-Namespaces-Cgroups-Runtime.md).
- Mengetahui konsep TCP socket, Reverse Proxy, dan DNS dari [BAB 02](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-02-Jaringan-Protokol-dan-Web-Servers/Module-01-Jaringan-Komputer-OSI-TCP-DNS-TLS.md).

---

## 3. Concept
Menjalankan 1 atau 2 container di 1 server menggunakan Docker Compose cukup sederhana. Namun, bagaimana jika Anda harus mengelola **500 container yang tersebar di 20 server fisik**?
- Bagaimana jika Server Node #4 tiba-tiba mati terbakar? Siapa yang memindahkan container ke server lain?
- Bagaimana jika traffic naik 10x lipat dalam 5 menit? Siapa yang men-scale jumlah replica?
- Bagaimana cara meng-update versi aplikasi tanpa memutus koneksi pengguna yang sedang aktif?

Inilah tugas **Kubernetes (K8s)**:
Sistem orkestrasi container open-source tingkat enterprise yang mengotomatiskan deployment, scaling, dan manajemen container secara terdistribusi.

Inti filosofi Kubernetes adalah **Declarative Management**:
Anda tidak memerintahkan K8s *"Jalankan container sekarang"*. Sebaliknya, Anda mendeklarasikan *Desired State* dalam file YAML:
> *"Saya ingin selalu ada 3 replica Pod aplikasi X yang berjalan sehat."*
Control Plane Kubernetes akan terus-menerus memantau kondisi nyata (*Current State*) dan melakukan tindakan perbaikan otomatis (*Reconciliation Loop*) agar kondisi nyata selalu sama dengan *Desired State*.

---

## 4. Why?
Mengapa Kubernetes menjadi standar de facto cloud computing?
1. **Self-Healing Otomatis**: Jika container crash, `kubelet` langsung me-restart. Jika suatu node server mati total, `kube-controller-manager` menjadwalkan ulang Pods ke node lain yang sehat.
2. **Horizontal Pod Autoscaler (HPA)**: Pod dapat bertambah secara otomatis dari 2 menjadi 50 instance saat metrik CPU/memori melonjak, dan mengecil kembali saat malam hari untuk menghemat biaya.
3. **Pemberhentian Zero-Downtime**: Strategi *Rolling Update* memastikan Pod versi baru sudah berstatus `Ready` sebelum Pod versi lama diterminasi.

---

## 5. What?
Komponen arsitektur Kubernetes:
- **Control Plane (Otak Cluster)**:
  - `kube-apiserver`: Pintu masuk tunggal (REST API) untuk semua perintah (`kubectl`, CI/CD).
  - `etcd`: Database terdistribusi key-value konsisten (Raft consensus) penyimpan seluruh state cluster.
  - `kube-scheduler`: Memilih worker node terbaik untuk menempatkan Pod baru berdasar ketersediaan CPU/RAM dan tolerations.
  - `kube-controller-manager`: Menjalankan loop kontrol (Node controller, Deployment controller, Endpoint controller).
- **Worker Node (Pekerja Lapangan)**:
  - `kubelet`: Agen di setiap node yang berkomunikasi dengan container runtime untuk memastikan Pod berjalan sesuai spesifikasi manifest.
  - `kube-proxy`: Mengelola aturan iptables/IPVS untuk perutean traffic Service networking.
  - `Container Runtime` (containerd / CRI-O): Menjalankan container fisik.
- **Abstraksi Objek K8s**:
  - `Pod`: Satu atau lebih container yang berbagi network namespace (IP sama) dan storage volume.
  - `Deployment`: Mengelola lifecycle ReplicaSet dan strategi update deklaratif.
  - `Service`: Abstraksi IP statis (*virtual stable IP*) di depan sekelompok Pods yang dinamis menggunakan label selector.

---

## 6. How?
Alur saat Anda menjalankan `kubectl apply -f deployment.yaml`:

```text
[ Developer: kubectl apply -f app-deployment.yaml (replicas: 3) ]
                              │
                              ▼
[ kube-apiserver ] ──(Simpan Desired State)──> [ etcd Database ]
                              │
                              ▼
[ Deployment Controller Mendeteksi: Butuh 3 Pods, ada 0 Pods ]
  -> Meminta apiserver membuat 3 Pod objects
                              │
                              ▼
[ kube-scheduler ]
  -> Mengevaluasi kapasitas Node 1, Node 2, Node 3
  -> Menetapkan: Pod-1 ke Node-1, Pod-2 ke Node-2, Pod-3 ke Node-2
                              │
                              ▼
[ kubelet di Node 1 & Node 2 ]
  -> Mendeteksi tugas penjadwalan via apiserver
  -> Memerintahkan containerd me-pull image dan menjalankan container
                              │
                              ▼
[ Pods Aktif & Mendaftarkan IP ke K8s Service Endpoints ]
```

---

## 7. Analogy
Bayangkan **Kubernetes** seperti **Manajemen Orkestra Simfoni Musik**:
- **Direktur Musik / Konduktor (Control Plane)**: Memegang partitur lagu lengkap (*Desired State* di etcd). Konduktor memberi isyarat dan membagi tugas kepada musisi.
- **Musisi / Pemain Biola (Worker Nodes)**: Memainkan instrumen musik secara nyata.
- **Pemain Cadangan (ReplicaSet)**: Jika satu pemain biola pingsan di panggung, konduktor seketika menunjuk pemain cadangan untuk menggantikannya tanpa menghentikan konser musik (*Self-Healing*).
- **Mikrofon Suara Bersama (Service)**: Penonton tidak perlu tahu nama masing-masing pemain biola; penonton hanya mendengar suara harmonis dari mikrofon terpusat (*Service IP*).

---

## 8. Diagram
```text
+-------------------------------------------------------------------------+
|                          KUBERNETES CONTROL PLANE                       |
|                                                                         |
|      +------------------+                    +---------------------+    |
|      |  kube-apiserver  | <================> |    etcd Database    |    |
|      +------------------+                    +---------------------+    |
|         ^            ^                                                  |
|         |            |                                                  |
|         v            v                                                  |
|  +--------------+  +-------------------------+                          |
|  |kube-scheduler|  | kube-controller-manager |                          |
|  +--------------+  +-------------------------+                          |
+---------|---------------------------------------------------------------+
          |
          +-------------------------------+
          |                               |
          v                               v
+-----------------------+       +-----------------------+
|     WORKER NODE 01    |       |     WORKER NODE 02    |
|  +-----------------+  |       |  +-----------------+  |
|  |     kubelet     |  |       |  |     kubelet     |  |
|  +-----------------+  |       |  +-----------------+  |
|  |   kube-proxy    |  |       |  |   kube-proxy    |  |
|  +-----------------+  |       |  +-----------------+  |
|  | Pod A   | Pod B |  |       |  | Pod C   | Pod D |  |
|  +-----------------+  |       |  +-----------------+  |
+-----------------------+       +-----------------------+
```

---

## 9. Simple Example
Manifest Kubernetes Deployment & Service (`app-deployment.yaml`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  labels:
    app: order-api
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: order-api
  template:
    metadata:
      labels:
        app: order-api
    spec:
      containers:
      - name: api
        image: acmecorp/order-api:v1.2.0
        ports:
        - containerPort: 3000
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "500m"
            memory: "256Mi"
        readinessProbe:
          httpGet:
            path: /healthz
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: order-service
spec:
  type: ClusterIP
  selector:
    app: order-api
  ports:
  - port: 80
    targetPort: 3000
```

---

## 10. Practical Example
Perintah `kubectl` esensial untuk inspeksi dan troubleshooting:

```bash
# 1. Melihat status Pods dan node penempatannya
kubectl get pods -o wide

# 2. Melihat riwayat revisi dan melakukan rollback instan
kubectl rollout history deployment/order-service
kubectl rollout undo deployment/order-service

# 3. Diagnostik mendalam jika Pod crash atau pending
kubectl describe pod order-service-7f89d-abc12

# 4. Membaca live stream log dari semua replica Pod
kubectl logs -l app=order-api -f --tail=100

# 5. Port-forwarding langsung ke local machine untuk debugging privat
kubectl port-forward svc/order-service 8080:80
```

---

## 11. Real World Example
### Kasus: Insiden 100% Downtime Akibat Liveness Probe yang Salah Arah
1. Developer mengonfigurasi `livenessProbe` di Kubernetes untuk mengecek database eksternal: `GET /health` yang melakukan ping ke database PostgreSQL.
2. Suatu hari, database PostgreSQL mengalami lonjakan koneksi selama 20 detik.
3. Endpoint `/health` mengembalikan HTTP 500.
4. `kubelet` menganggap aplikasi rusak dan me-restart semua 20 Pods secara bersamaan!
5. 20 Pod baru menyala dan secara bersamaan membanjiri database dengan ratusan koneksi baru (*thundering herd*), menyebabkan cluster mati total selama 45 menit.
6. **Solusi SRE**:
   - **Liveness Probe**: Hanya boleh memeriksa kesehatan internal proses aplikasi itu sendiri (apakah event loop macet).
   - **Readiness Probe**: Memeriksa apakah aplikasi siap menerima traffic (termasuk kesiapan database). Jika gagal, K8s hanya mencopot Pod dari Service routing tanpa me-restart proses!

---

## 12. Trade-offs
| Tipe Kubernetes Service | ClusterIP | NodePort | LoadBalancer |
|---|---|---|---|
| **Aksesibilitas** | Hanya di dalam cluster K8s internal | Port host node terbuka (range 30000-32767) | Eksternal publik via Cloud Provider (AWS ALB / GCP LB) |
| **Biaya** | Gratis ($0) | Gratis ($0) | Berbayar per Load Balancer cloud instance |
| **Keamanan** | Sangat aman (terisolasi) | Rentan jika port node terekspos | Terlindungi oleh firewall cloud provider |
| **Use Case** | Komunikasi antar microservices internal | Debugging lokal / Bare-metal on-premise | Traffic masuk internet publik utama |

---

## 13. When To Use
- Saat aplikasi Anda terdiri dari puluhan microservices yang membutuhkan auto-scaling, self-healing, dan deployment zero-downtime.
- Saat tim engineering ingin standarisasi deployment lintas cloud (AWS EKS, GCP GKE, Azure AKS, atau on-premise).

---

## 14. When NOT To Use
- Untuk aplikasi monolitik sederhana atau blog personal dengan traffic kecil; Kubernetes menambah *cognitive overhead* dan biaya operasional yang tidak sebanding. Cukup gunakan Docker Compose atau PaaS (Render/Fly.io).

---

## 15. Common Mistakes
1. **Tidak Menetapkan `resources.requests` dan `limits`**: Kube-scheduler tidak tahu berapa kebutuhan Pod, sehingga menempatkan terlalu banyak Pod di satu node hingga memicu OOM Killer massal.
2. **Menyamakan Liveness Probe dengan Readiness Probe**: Menggunakan endpoint yang sama sehingga kegagalan sementara upstream memicu restart loop tak berujung (*CrashLoopBackOff*).
3. **Menggunakan `type: LoadBalancer` untuk Setiap Service**: Membuat 20 Load Balancer cloud terpisah seharga $20/bulan per instance. **Solusi**: Gunakan 1 Ingress Controller untuk menangani ratusan Service.

---

## 16. Best Practices
### Must Have
- Selalu definisikan `resources.requests` dan `resources.limits` untuk CPU dan Memory.
- Definisikan `readinessProbe` dan `livenessProbe` secara independen.
- Pasang `podAntiAffinity` agar replica Pod disebar ke node server yang berbeda (mencegah single-point-of-failure jika 1 server mati).

### Recommended
- Gunakan `maxUnavailable: 0` dan `maxSurge: 1` pada strategi RollingUpdate untuk menjamin ketersediaan 100% saat rilis versi baru.
- Pasang `PodDisruptionBudget (PDB)` agar cluster maintenance tidak mematikan terlalu banyak Pod sekaligus.

### Avoid / Overengineering
- Jangan menyimpan data stateful langsung di Pod ephemeral; gunakan `StatefulSet` dengan `PersistentVolumeClaim (PVC)` dinamis.

---

## 17. Troubleshooting
| Status Pod | Kemungkinan Penyebab | Solusi |
|---|---|---|
| `CrashLoopBackOff` | Aplikasi melempar uncaught exception atau konfigurasi environment salah | Cek log container: `kubectl logs <pod-name> --previous` |
| `ImagePullBackOff` / `ErrImagePull` | Nama image salah, tag tidak ada, atau secret private registry hilang | Periksa nama image dan verifikasi `imagePullSecrets` di manifest |
| `Pending` | Tidak ada worker node yang memiliki sisa CPU/RAM sesuai `requests` | Periksa event via `kubectl describe pod <pod-name>` dan tambahkan worker node |

---

## 18. Exercise
1. Tulis manifest Kubernetes Deployment yang menjalankan 3 replica Nginx dengan port 80.
2. Terapkan service berjenis `ClusterIP` untuk mengekspos Deployment tersebut ke internal cluster.

---

## 19. Challenge
Rancang arsitektur simulasi **Kubernetes Reconciliation Loop & Rolling Update Engine**:
- Simulasikan Desired State (3 Pod v1).
- Saat spec diubah ke v2 dengan `maxSurge: 1` dan `maxUnavailable: 0`, engine membuat 1 Pod v2, menunggu probe berstatus `Ready`, lalu mematikan 1 Pod v1 secara bertahap hingga seluruh replica menjadi v2 tanpa penurunan kapasitas.

---

## 20. Summary
- Kubernetes mengelola infrastruktur secara deklaratif melalui siklus rekonsiliasi yang berkelanjutan.
- Control Plane merencanakan dan mengontrol, sementara Worker Node mengeksekusi beban kerja di dalam Pods.
- Service menyediakan abstraksi IP stabil untuk load balancing dan penemuan layanan antar Pods.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m01/k8s_scheduler_service_sim.js](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-04-Kubernetes-Orchestration/hands-on/m01/k8s_scheduler_service_sim.js).
