# Module 01: Arsitektur Control Plane Kubernetes (kube-apiserver, etcd Quorum, Controller Manager, Scheduler)

---
[⬅️ Kembali ke Silabus](../README.md) | **BAB 01: Arsitektur Internal & Control Plane** | [Module 02: Arsitektur Worker Node ➡️](./Module-02-Arsitektur-Worker-Node-kubelet-kube-proxy-CRI.md)
---

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Memahami peran arsitektural dan interaksi antar empat komponen inti **Kubernetes Control Plane**: `kube-apiserver`, `etcd`, `kube-controller-manager`, dan `kube-scheduler`.
2. Menjelaskan mekanisme penyimpanan konsistensi data terdistribusi pada `etcd` menggunakan algoritma konsensus **Raft** dan konsep **Quorum**.
3. Memahami siklus hidup penanganan request deklaratif API (Authentication -> Authorization -> Mutating Admission -> Schema Validation -> Validating Admission -> etcd Persistence).
4. Mengidentifikasi cara kerja rekonsiliasi kontroler loop (**Reconciliation Loop**) yang menjaga *Actual State* agar selalu sama dengan *Desired State*.
5. Menjelaskan algoritma 2-tahap `kube-scheduler`: **Filtering (Predicates)** dan **Scoring (Priorities)** dalam memilih worker node terbaik.

---

## 2. Prerequisite
- Memahami konsep dasar arsitektur container dan Docker Engine ([Docker BAB 01](../../Docker/BAB-01-Fondasi-dan-Arsitektur-Docker/)).
- Memahami konsep arsitektur sistem terdistribusi dan konsensus (System Design: Raft consensus, CAP Theorem).
- Pemahaman dasar protokol REST API dan format JSON/YAML.

---

## 3. Concept
Kubernetes adalah sistem orkestrasi kontainer terdistribusi yang dirancang untuk mengotomatisasi deployment, scaling, dan manajemen aplikasi terkontainerisasi. 

Jantung dari seluruh kecerdasan Kubernetes berada di dalam **Control Plane** (otak kluster). Control plane bertindak sebagai pembuat keputusan global: mendeteksi dan merespons event dalam kluster, menjadwalkan workload, dan menginisiasi pemulihan mandiri (*self-healing*) ketika sebuah node atau kontainer mengalami kegagalan.

Prinsip dasar arsitektur Kubernetes adalah **Declarative State Management**:
- Pengguna mendefinisikan keadaan yang diinginkan (**Desired State**) melalui file deklaratif YAML (misal: "Saya ingin 5 replika pod API").
- Control plane secara kontinu membandingkan *Desired State* tersebut dengan kondisi nyata di lapangan (**Actual State**), dan mengeksekusi aksi korektif jika terjadi penyimpangan (*Drift*).

---

## 4. Why?
Mengapa arsitektur Control Plane Kubernetes didesain secara modular dan terpisah?
1. **Pemisahan Peran (Decoupling & Single Responsibility)**: Komponen penyimpanan state (`etcd`) terpisah dari komponen penjadwalan (`scheduler`) dan logika bisnis kontroler (`controller-manager`), memungkinkan penskalaan dan pemulihan komponen secara independen.
2. **Ketiadaan Single Point of Failure (High Availability)**: Control plane dapat dijalankan dalam konfigurasi multi-master (biasanya 3 atau 5 node) dengan leader election untuk toleransi kegagalan server fisik.
3. **Stateless Logic dengan Single Source of Truth**: Seluruh komponen control plane (kecuali etcd) bersifat stateless. `kube-apiserver` adalah satu-satunya komponen yang memiliki akses baca-tulis langsung ke `etcd`.

---

## 5. What?
### Komponen Inti Control Plane:

| Komponen | Peran Utama | Pola Komunikasi |
|---|---|---|
| **`kube-apiserver`** | Front door / gateway utama kluster; mengekspos Kubernetes REST API; menangani AuthN, AuthZ, Admission, dan validasi skema. | Satu-satunya komponen yang berbicara langsung dengan `etcd`. Berkomunikasi via HTTPS gRPC/REST. |
| **`etcd`** | Database key-value terdistribusi yang konsisten dan berkonsensus kuat (Raft); menyimpan seluruh state dan konfigurasi kluster. | Akses privat hanya oleh `kube-apiserver` (port 2379/2380). |
| **`kube-controller-manager`** | Daemon yang menjalankan kumpulan rekonsiliasi kontroler internal (DeploymentController, ReplicaSetController, NodeController, dll.). | Melakukan watch event ke `kube-apiserver` dan memperbarui resource via API. |
| **`kube-scheduler`** | Komponen pencari jodoh (matchmaker); memantau pod yang baru dibuat tanpa penugasan node (`spec.nodeName == ""`) dan memilih node optimal. | Melakukan watch pod unassigned ke `kube-apiserver` lalu mengirim perintah `Binding`. |
| **`cloud-controller-manager`** | Menghubungkan kluster dengan API cloud provider eksternal (AWS, GCP, Azure) untuk mengelola LoadBalancer, Routes, dan Volume. | Terpisah di cloud-managed Kubernetes (EKS, GKE, AKS). |

---

## 6. How? Alur Eksekusi Permintaan Deklaratif (Lifecycle of a Request)

```text
[ Developer: kubectl apply -f deployment.yaml ]
                      |
                      v (HTTPS POST/PUT)
+-----------------------------------------------------------------------------------+
|                                 kube-apiserver                                    |
|                                                                                   |
|  1. Authentication (AuthN): Memvalidasi identitas (Client Cert, OIDC token, SA)  |
|  2. Authorization (AuthZ): Memvalidasi hak akses RBAC (Can user create pods?)     |
|  3. Mutating Admission Webhook: Mengubah/menyuntikkan default (Sidecar inject)    |
|  4. Object Schema Validation: Memvalidasi keabsahan struktur sintaksis YAML       |
|  5. Validating Admission Webhook: Validasi kebijakan ketat (Kyverno / OPA)       |
+-----------------------------------------------------------------------------------+
                                         |
                                         v (Commit transaction via gRPC)
+-----------------------------------------------------------------------------------+
|                                   etcd Cluster                                    |
|  6. Raft Consensus Commit: State tersimpan permanen di key:                       |
|     /registry/deployments/default/my-api                                          |
+-----------------------------------------------------------------------------------+
                                         |
                                         v (Watch Notification)
+-----------------------------------------------------------------------------------+
|                     kube-controller-manager (DeploymentController)                |
|  7. Mendeteksi Deployment baru -> Membuat resource ReplicaSet                     |
|  8. ReplicaSetController mendeteksi -> Membuat Pod-pod tanpa nama node           |
+-----------------------------------------------------------------------------------+
                                         |
                                         v (Watch Notification: Pods unassigned)
+-----------------------------------------------------------------------------------+
|                                  kube-scheduler                                   |
|  9. Filtering Phase: Mengeliminasi node yang kehabisan resource / ada taint      |
|  10. Scoring Phase: Menghitung skor node terbaik untuk balancing                   |
|  11. Binding: Menulis spec.nodeName ke kube-apiserver                             |
+-----------------------------------------------------------------------------------+
                                         |
                                         v (Watch Notification: Pod assigned to Node)
                                [ Kubelet di Worker Node ]
```

---

## 7. Analogy
Bayangkan Control Plane Kubernetes seperti manajemen sebuah bandara internasional:
- **`kube-apiserver`** adalah **Pintu Masuk & Meja Resepsionis Utama**. Siapa pun (pilot, kru darat, maskapai) harus melewati petugas keamanan dan resepsionis ini. Tidak ada yang boleh masuk ke ruang arsip langsung.
- **`etcd`** adalah **Buku Induk Logistik & Catatan Penerbangan Bandara**. Seluruh jadwal, status pesawat, dan manifes tercatat di buku ini secara permanen dengan penjaga brankas ketat.
- **`kube-controller-manager`** adalah **Manajer Operasional Penerbangan**. Jika ada laporan bahwa sebuah pesawat rusak (node crash), ia langsung memerintahkan armada cadangan untuk terbang agar jadwal penerbangan tetap sesuai komitmen.
- **`kube-scheduler`** adalah **Petugas Pengatur Alokasi Landasan & Gate**. Saat sebuah pesawat siap mendarat (pod unassigned), ia menganalisis landasan mana yang kosong, memiliki kapasitas bahan bakar cukup, dan cuaca yang aman, lalu mengarahkan pesawat ke gate tersebut.

---

## 8. Diagram: etcd Quorum & High Availability

Formula Quorum etcd berbasis algoritma konsensus Raft:
$$\text{Quorum} = \left\lfloor \frac{N}{2} \right\rfloor + 1$$

```text
Cluster 3-Node etcd (Toleransi 1 Node Mati):
Quorum = floor(3/2) + 1 = 2 Node Wajib Hidup
+----------+      +----------+      +----------+
|  etcd 1  |<---->|  etcd 2  |<---->|  etcd 3  |
| (Leader) |      | (Follower|      | (CRASH!) |
+----------+      +----------+      +----------+
     ^                 ^
     |                 |
     +-- Quorum = 2 ---+ ---> Cluster TETAP BISA MENERIMA TULIS/BACA!

Cluster 5-Node etcd (Toleransi 2 Node Mati):
Quorum = floor(5/2) + 1 = 3 Node Wajib Hidup (Standar Rekomendasi Enterprise Production)
```

---

## 9. Simple Example: Memeriksa Kesehatan Komponen Control Plane
Gunakan perintah `kubectl` untuk menginspeksi kesehatan control plane:

```bash
# 1. Periksa status komponen utama (apiserver, scheduler, controller-manager, etcd)
kubectl get componentstatuses
# Catatan: Perintah ini deprecated di K8s modern, gunakan get pods -n kube-system:
kubectl get pods -n kube-system -l tier=control-plane

# 2. Periksa endpoint etcd health secara langsung
etcdctl endpoint health \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  --endpoints=https://127.0.0.1:2379
```

---

## 10. Practical Example: Manifest Static Pod Control Plane
Pada kluster yang di-bootstrap menggunakan `kubeadm`, komponen control plane berjalan sebagai **Static Pods** yang dimanipulasi langsung oleh kubelet lokal melalui manifest di `/etc/kubernetes/manifests/`:

Contoh manifest `/etc/kubernetes/manifests/kube-apiserver.yaml`:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: kube-apiserver
  namespace: kube-system
spec:
  hostNetwork: true
  containers:
  - name: kube-apiserver
    image: registry.k8s.io/kube-apiserver:v1.29.2
    command:
    - kube-apiserver
    - --advertise-address=192.168.1.10
    - --allow-privileged=true
    - --authorization-mode=Node,RBAC
    - --client-ca-file=/etc/kubernetes/pki/ca.crt
    - --enable-admission-plugins=NodeRestriction
    - --etcd-servers=https://127.0.0.1:2379
    - --etcd-cafile=/etc/kubernetes/pki/etcd/ca.crt
    - --etcd-certfile=/etc/kubernetes/pki/apiserver-etcd-client.crt
    - --etcd-keyfile=/etc/kubernetes/pki/apiserver-etcd-client.key
    - --service-cluster-ip-range=10.96.0.0/12
    livenessProbe:
      httpGet:
        path: /livez
        port: 6443
        scheme: HTTPS
      initialDelaySeconds: 10
      periodSeconds: 10
```

---

## 11. Real World Example: Insiden Outage Split-Brain etcd di Fintech
Sebuah kluster Kubernetes on-premise mengalami *network partition* antar 3 rack server data center:
- Node etcd-1 terisolasi di Rack A.
- Node etcd-2 dan etcd-3 berada di Rack B.
- **Dampak**: Node etcd-1 mendeteksi kehilangan heartbeat dan mencoba memulai election, namun karena gagal mencapai quorum ($1 < 2$), node etcd-1 menolak seluruh request penulisan (`read-only`). Sementara itu, etcd-2 dan etcd-3 di Rack B berhasil mempertahankan quorum ($2 \ge 2$) dan memilih leader baru.
- **Hasil**: Kluster tidak mengalami korupsi data *split-brain* berkat algoritma Raft, dan aplikasi tetap berjalan normal melayani traffic pengguna.

---

## 12. Trade-offs: Arsitektur Control Plane

| Dimensi | Single Master Node | High Availability (3 Node) | High Availability (5 Node) |
|---|---|---|---|
| **Toleransi Kegagalan** | 0 Node (SPOF Fatal) | 1 Node Mati | 2 Node Mati |
| **Beban Latensi Write etcd** | Sangat Rendah | Sedang (Perlu ACK 2 node) | Lebih Tinggi (Perlu ACK 3 node) |
| **Biaya Komputasi Cloud** | Paling Murah | Sedang (3 VM Control Plane) | Paling Mahal (5 VM Control Plane) |
| **Target Lingkungan** | Homelab / Minikube / K3s lokal | Staging / Cluster Produksi Menengah | Cluster Enterprise Misi Kritis |

---

## 13. When To Use
- Gunakan arsitektur control plane minimal 3 node untuk semua kluster produksi perusahaan.
- Tempatkan storage disk `etcd` pada media dengan IOPS tinggi (**NVMe SSD**) karena latensi disk fsync etcd yang lambat dapat memicu timeout heartbeat Raft dan ketidakstabilan leader election.

---

## 14. When NOT To Use
- Jangan gunakan jumlah node etcd **genap** (seperti 2 atau 4 node). 4 node memiliki toleransi kegagalan yang sama dengan 3 node (hanya toleran 1 node mati), namun menambah beban latensi konsensus jaringan.

---

## 15. Common Mistakes
1. **Mengizinkan komponen lain berbicara langsung dengan etcd**: Tidak boleh ada pod atau aplikasi eksternal yang mengakses etcd selain `kube-apiserver`.
2. **Mengabaikan IOPS Disk etcd**: Menggunakan hard disk HDD mekanik atau EBS volume standar tanpa IOPS terjamin menyebabkan peringatan etcd: `took too long (150ms) to execute 1 write transaction`.
3. **Lupa melakukan backup snapshot etcd**: Jika seluruh node etcd hancur dan tidak ada snapshot biner (`etcdctl snapshot save`), seluruh definisi state kluster hilang permanen.

---

## 16. Best Practices
### Must Have
- Terapkan topologi ganjil (3 atau 5 node) untuk control plane produksi.
- Jalankan automated backup snapshot etcd berkala (misal setiap 4 jam) dan kirim snapshot ke cloud object storage terenkripsi (S3/GCS).
- Pisahkan traffic etcd peer-to-peer (port 2380) ke subnet jaringan internal berlatensi rendah.

### Recommended
- Aktifkan Admission Controller `NodeRestriction` untuk membatasi hak akses kubelet agar hanya bisa memodifikasi Pod miliknya sendiri.
- Gunakan metrik Prometheus untuk memantau `etcd_disk_wal_fsync_duration_seconds` (harus di bawah 10ms pada persentil p99).

### Advanced
- Pisahkan node etcd menjadi dedicated external etcd cluster terpisah dari node `kube-apiserver` pada kluster raksasa (> 1.000 node worker).

---

## 17. Troubleshooting Guide
### Problem 1: `kubectl` gagal dengan error `The connection to the server <ip>:6443 was refused`
- **Penyebab**: `kube-apiserver` container mati atau gagal start.
- **Diagnosa**:
  ```bash
  # Cek status containerd / docker runtime
  sudo crictl ps -a | grep apiserver
  sudo crictl logs <container-id-apiserver>
  ```
- **Penyebab Umum**: Sertifikat TLS expired di `/etc/kubernetes/pki/` atau etcd tidak merespons koneksi port 2379.

### Problem 2: Pod berstatus `Pending` secara permanen
- **Penyebab**: `kube-scheduler` tidak aktif, atau tidak ada node yang lolos tahap *Filtering (Predicates)*.
- **Diagnosa**:
  ```bash
  kubectl describe pod <nama-pod>
  # Periksa bagian Events di baris terbawah
  ```
  Jika pesan berbunyi `0/3 nodes are available: 3 Insufficient memory`, berarti worker node kehabisan RAM untuk memenuhi `spec.containers.resources.requests.memory`.

---

## 18. Exercises
### Level: Easy
1. Jalankan perintah `kubectl get nodes` dan identifikasi node mana yang memiliki role `control-plane` atau `master`.
2. Tampilkan seluruh pod sistem yang berjalan di namespace `kube-system`:
   `kubectl get pods -n kube-system`

### Level: Medium
1. Periksa log dari `kube-scheduler` untuk melihat event penjadwalan pod:
   `kubectl logs -n kube-system -l component=kube-scheduler --tail=50`
2. Periksa versi komponen kontrol plane menggunakan `kubectl version`.

### Level: Hard
1. Simulasikan pembuatan snapshot backup database etcd menggunakan perintah:
   `ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 snapshot save /tmp/etcd-backup.db`
2. Verifikasi status file snapshot backup dengan perintah:
   `ETCDCTL_API=3 etcdctl snapshot status /tmp/etcd-backup.db --write-out=table`

---

## 19. Challenge
Rancang arsitektur High Availability Control Plane multi-zona untuk perbankan di AWS EKS / Self-Managed:
- 3 Master Nodes tersebar di 3 Availability Zones (AZ-a, AZ-b, AZ-c).
- Load balancer eksternal (NLB) mendistribusikan traffic HTTPS port 6443 ke 3 instance `kube-apiserver`.
- Buat rencana disaster recovery jika 1 zona AZ mengalami pemadaman total (blackout), meliputi status quorum etcd dan kapasitas penjadwalan scheduler.

---

## 20. Summary
- **Control Plane** adalah otak terdistribusi Kubernetes yang mengelola dan menegakkan *Desired State*.
- **`kube-apiserver`** bertindak sebagai gerbang tunggal dengan pipeline AuthN, AuthZ, Mutating Webhook, dan Validasi Skema.
- **`etcd`** menggunakan konsensus Raft; membutuhkan Quorum $\lfloor N/2 \rfloor + 1$ untuk tetap melayani transaksi.
- **`kube-controller-manager`** menjalankan *Reconciliation Loops* berkelanjutan untuk mendeteksi dan memperbaiki drift.
- **`kube-scheduler`** menjalankan dua fase: Filtering (Predicates) dan Scoring (Priorities) untuk menempatkan pod pada worker node yang paling optimal.

---
[⬅️ Kembali ke Silabus](../README.md) | [Module 02: Arsitektur Worker Node ➡️](./Module-02-Arsitektur-Worker-Node-kubelet-kube-proxy-CRI.md)
---
