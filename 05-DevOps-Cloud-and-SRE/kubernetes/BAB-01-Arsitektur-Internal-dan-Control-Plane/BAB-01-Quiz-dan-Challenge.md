# BAB 01 — Quiz & Chapter Challenge: Arsitektur Internal & Control Plane Kubernetes

---
[⬅️ Module 02: Arsitektur Worker Node](./Module-02-Arsitektur-Worker-Node-kubelet-kube-proxy-CRI.md) | [📋 Silabus Induk](../README.md) | [BAB 02 Module 01: Anatomi Pod & Lifecycle ➡️](../BAB-02-Pod-Lifecycle-dan-Multi-Container-Patterns/Module-01-Anatomi-Pod-Lifecycle-Probes-dan-Termination.md)
---

Dokumen ini dirancang untuk menguji pemahaman arsitektural dan kesiapan operasional Anda terkait cara kerja komponen inti **Control Plane** (`kube-apiserver`, `etcd`, `kube-controller-manager`, `kube-scheduler`) dan **Worker Node** (`kubelet`, CRI `containerd`, `kube-proxy`, `cgroups v2`).

---

## Bagian 1: Basic Quiz (5 Pertanyaan)

### Soal 1
Komponen Kubernetes manakah yang merupakan satu-satunya komponen yang memiliki hak akses komunikasi langsung untuk membaca dan menulis data ke database `etcd`?
- A. `kubelet`
- B. `kube-scheduler`
- C. `kube-apiserver`
- D. `kube-controller-manager`

### Soal 2
Berapa jumlah minimum node yang wajib tetap aktif agar kluster `etcd` yang beranggotakan 5 node dapat mempertahankan konsensus Raft dan melayani transaksi penulisan (Quorum)?
- A. 2 node
- B. 3 node
- C. 4 node
- D. 5 node

### Soal 3
Apa tugas utama dari `kube-scheduler` dalam siklus hidup sebuah Pod?
- A. Menarik image dari Docker Hub ke disk lokal.
- B. Memantau Pod baru yang belum memiliki penugasan node (`spec.nodeName == ""`), lalu memilih worker node terbaik melalui fase Filtering dan Scoring.
- C. Memperbaiki bug kode di dalam aplikasi.
- D. Mengalokasikan IP address publik ke Ingress Controller.

### Soal 4
Mengapa ketidakcocokan (mismatch) cgroup driver (misal: Kubelet disetel ke `systemd`, sedangkan containerd disetel ke `cgroupfs`) dapat memicu kegagalan fatal pada Worker Node?
- A. Karena port jaringan container akan otomatis terblokir.
- B. Karena terjadi perebutan otoritas antara dua sistem manajer cgroup yang berbeda di kernel Linux host, memicu instabilitas alokasi kuota resource dan crash loop pada Kubelet.
- C. Karena format file YAML tidak bisa dibaca oleh Kubelet.
- D. Karena Docker Hub menolak koneksi gRPC.

### Soal 5
Apa perbedaan mendasar antara Kubelet dengan komponen Kubernetes lainnya seperti Kube-Proxy atau CoreDNS?
- A. Kubelet ditulis dalam bahasa Python, sedangkan komponen lain ditulis dalam Go.
- B. Kubelet berjalan langsung sebagai service daemon native di sistem operasi Linux host (dikelola via `systemd`), sedangkan Kube-Proxy dan CoreDNS biasanya berjalan sebagai Pod/DaemonSet di dalam Kubernetes.
- C. Kubelet hanya bisa berjalan di macOS.
- D. Kubelet tidak membutuhkan sertifikat TLS.

---

## Bagian 2: Intermediate Quiz (5 Pertanyaan)

### Soal 6
Dalam pipeline pemrosesan request pada `kube-apiserver`, urutan eksekusi manakah yang benar setelah request lolos tahap Autentikasi (AuthN) dan Otorisasi (AuthZ)?
- A. etcd Commit -> Validating Webhook -> Mutating Webhook.
- B. Mutating Admission Webhook -> Schema Validation -> Validating Admission Webhook -> etcd Persistence.
- C. Validating Admission Webhook -> Mutating Admission Webhook -> Schema Validation.
- D. Scheduler -> Controller Manager -> Mutating Webhook.

### Soal 7
Apa fungsi dari objek `NodeLease` di namespace `kube-node-lease` yang diperbarui oleh Kubelet setiap 10 detik?
- A. Menyimpan tagihan biaya cloud instance worker node.
- B. Sebagai mekanisme heartbeat ringan dengan overhead rendah untuk memberitahu Control Plane bahwa node tersebut masih hidup dan sehat (`Ready`), mengurangi beban transaksi pada etcd.
- C. Menyimpan sertifikat SSL publik milik Ingress.
- D. Mengunci IP address worker node agar tidak berganti.

### Soal 8
Mengapa mode `kube-proxy: ipvs` jauh lebih unggul dibandingkan mode `kube-proxy: iptables` pada kluster dengan puluhan ribu Service?
- A. Karena IPVS berjalan di browser client.
- B. Karena IPVS menggunakan struktur data Hash Table dengan kompleksitas pencarian $O(1)$ konstan, sedangkan iptables mengevaluasi rantai rule secara sekuensial dengan kompleksitas $O(N)$ yang membebani CPU kernel Linux saat jumlah rule membengkak.
- C. Karena iptables tidak mendukung protokol HTTPS.
- D. Karena IPVS gratis sedangkan iptables berbayar.

### Soal 9
Apa peran dari **Pause Container** (Infra Container) yang dibuat oleh CRI saat tahapan `RunPodSandbox` dieksekusi?
- A. Menyimpan file cache download package aplikasi.
- B. Berfungsi sebagai jangkar (anchor) untuk menahan dan mempertahankan Linux Network Namespace, IPC Namespace, dan Pod IP bersama, sehingga kontainer aplikasi di dalam Pod yang sama dapat saling berkomunikasi via `localhost`.
- C. Mematikan Pod saat jam kerja selesai.
- D. Membatasi pemakaian bandwidth internet Pod.

### Soal 10
Jika Anda menjalankan perintah `kubectl get nodes` dan salah satu worker node berstatus `NotReady` dengan pesan event:
`PLEG is not healthy: pleg was last seen active 3m30s ago`
Di manakah letak akar permasalahan yang paling mungkin terjadi di node tersebut?
- A. Developer salah menulis sintaks di file Dockerfile.
- B. Subsistem PLEG Kubelet mengalami hang atau timeout saat berkomunikasi via gRPC dengan Container Runtime (`containerd`), yang umumnya dipicu oleh bottleneck I/O disk host atau kebuntuan proses runtime.
- C. Kuota internet kantor habis.
- D. Node scheduler dinonaktifkan oleh admin.

---

## Bagian 3: Scenario-Based Questions (3 Skenario)

### Skenario 1: Bencana Split-Brain pada etcd Cluster
Sebuah kluster Kubernetes on-premise dibangun dengan 4 master node etcd di dua data center:
- DC-1 (2 Node Master)
- DC-2 (2 Node Master)
Kabel fiber optik bawah tanah yang menghubungkan DC-1 dan DC-2 terputus akibat galian konstruksi jalan.
- **Pertanyaan**: Berapa kuorum yang dibutuhkan oleh etcd cluster beranggotakan 4 node ini? Apakah DC-1 atau DC-2 masih dapat memproses penulisan state baru? Jelaskan mengapa topologi 4 node adalah anti-pattern yang buruk dan rekomendasikan topologi yang benar!

### Skenario 2: Misteri Pod Pending Padahal Total RAM Kluster Cukup
Sebuah tim data science men-deploy Pod pelatihan model yang membutuhkan `requests.memory: 16Gi`.
Di kluster terdapat 4 worker node dengan total sisa RAM sebesar 32GB:
- Node 1: Sisa RAM 6GB
- Node 2: Sisa RAM 10GB
- Node 3: Sisa RAM 8GB
- Node 4: Sisa RAM 8GB
Pod tersebut berstatus `Pending` selamanya.
- **Pertanyaan**: Jelaskan mengapa `kube-scheduler` gagal menjadwalkan Pod tersebut meskipun total kapasitas RAM kluster (32GB) jauh melampaui kebutuhan Pod (16GB), dan sebutkan nama fase scheduler yang menolak Pod ini!

### Skenario 3: Kubelet Crash-Loop Usai Upgrade OS Ubuntu
Seorang sysadmin melakukan upgrade OS worker node dari Ubuntu 20.04 ke Ubuntu 22.04. Sesaat setelah node di-reboot, service Kubelet langsung gagal start (`CrashLoopBackOff`) dengan pesan log:
`failed to run Kubelet: misconfigured cgroup driver: expected systemd but got cgroupfs`.
- **Pertanyaan**: Tuliskan langkah perbaikan konkret pada file konfigurasi `/etc/containerd/config.toml` dan `/var/lib/kubelet/config.yaml` agar Kubelet dapat kembali berjalan normal!

---

## Bagian 4: Chapter Challenge

### Tantangan Praktis: Control Plane & Worker Node Diagnostics Architect
1. **Skenario**:
   Anda ditugaskan merancang prosedur audit kepatuhan (compliance checklist) untuk cluster Kubernetes v1.29 baru sebelum diserahkan ke tim security:
   - Memastikan etcd terisolasi, terenkripsi via TLS, dan memiliki jadwal backup snapshot otomatis.
   - Memastikan `cgroupDriver: systemd` seragam di seluruh node control-plane dan worker.
   - Memastikan `kube-proxy` dikonfigurasi menggunakan mode `ipvs`.
2. **Deliverables**:
   - Tuliskan skrip bash audit otomatis `k8s_node_audit.sh` yang memeriksa konfigurasi cgroups dan status service kubelet di worker node.
   - Tuliskan perintah CLI `etcdctl` untuk memvalidasi kesehatan cluster etcd dan membuat snapshot database ke direktori backup lokal.

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Empat komponen inti Control Plane: `kube-apiserver`, `etcd`, `kube-controller-manager`, `kube-scheduler`.
- [ ] Formula Quorum etcd ($\lfloor N/2 \rfloor + 1$) dan mengapa jumlah node ganjil wajib digunakan.
- [ ] Pipeline 6 tahap pemrosesan request di `kube-apiserver`.
- [ ] Cara kerja dua fase scheduler: Filtering (Predicates) dan Scoring (Priorities).
- [ ] Peran Kubelet sebagai agen OS Linux host dan komunikasinya via CRI gRPC.
- [ ] Fungsi Pause container dalam mempertahankan Network Namespace Pod.
- [ ] Mengapa `systemd` cgroup driver wajib diselaraskan antara Kubelet dan Containerd.
- [ ] Perbedaan performa antara `kube-proxy` iptables ($O(N)$) vs IPVS ($O(1)$).

### Saya Tidak Perlu Menghafal:
- Seluruh daftar ratusan bendera flag CLI kubelet (cukup pahami konfigurasi deklaratif di `/var/lib/kubelet/config.yaml`).
- Format biner internal WAL (Write-Ahead Log) etcd.

### Saya Harus Bisa Melakukan:
- [ ] Memeriksa kesehatan pod control plane di namespace `kube-system`.
- [ ] Memeriksa cgroup driver Kubelet dan Containerd di host Linux.
- [ ] Mengambil snapshot backup etcd menggunakan `etcdctl`.
- [ ] Mendiagnosa penyebab Pod berstatus `Pending` dari pesan event scheduler.
- [ ] Mengidentifikasi masalah Node `NotReady` melalui log journalctl Kubelet.

---
[⬅️ Module 02: Arsitektur Worker Node](./Module-02-Arsitektur-Worker-Node-kubelet-kube-proxy-CRI.md) | [📋 Silabus Induk](../README.md) | [BAB 02 Module 01: Anatomi Pod & Lifecycle ➡️](../BAB-02-Pod-Lifecycle-dan-Multi-Container-Patterns/Module-01-Anatomi-Pod-Lifecycle-Probes-dan-Termination.md)
---
