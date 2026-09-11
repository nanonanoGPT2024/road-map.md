# BAB 04: Quiz, Challenge, & Knowledge Check
**Orkestrasi Container dengan Kubernetes (K8s)**

---

## 1. Basic Questions (5 Soal)
1. Apa fungsi utama dari `kube-apiserver`, `etcd`, dan `kube-scheduler` pada Control Plane Kubernetes?
2. Mengapa unit deployment terkecil di Kubernetes adalah **Pod**, dan bukan langsung container individual?
3. Sebutkan perbedaan fungsi antara Service bertipe `ClusterIP` dan `NodePort`!
4. Apa peran dari **Ingress Controller** dibandingkan dengan Service bertipe `LoadBalancer` individual?
5. Mengapa nilai kredensial di dalam objek Kubernetes **Secret** bawaan tidak boleh dianggap sebagai data terenkripsi aman saat di-commit ke Git?

---

## 2. Intermediate Questions (5 Soal)
6. Bagaimana cara kerja *Reconciliation Loop* pada Kubernetes Controller saat kondisi aktual (*Current State*) berbeda dengan *Desired State*?
7. Jelaskan perbedaan mendasar antara parameter probe `livenessProbe` dan `readinessProbe`! Apa bahayanya jika liveness probe memeriksa konektivitas database eksternal?
8. Bagaimana strategi deployment `RollingUpdate` dengan parameter `maxSurge: 1` dan `maxUnavailable: 0` menjamin *zero downtime* selama proses rilis?
9. Apa fungsi dari file `values.yaml` dan direktori `templates/` pada sebuah **Helm Chart**?
10. Bagaimana perintah `helm rollback` bekerja ketika sebuah rilis versi baru mengalami bug fatal di production?

---

## 3. Scenario-Based Questions (3 Soal)

### Skenario A: The Cascading Restart Loop (Thundering Herd)
Sebuah microservice pembayaran memiliki `livenessProbe` yang melakukan query `SELECT 1` ke PostgreSQL setiap 5 detik. Saat database mengalami maintenance sesaat selama 15 detik, Kubernetes me-restart seluruh 30 replica Pod pembayaran secara bersamaan. Saat menyala kembali, ke-30 Pod serentak membanjiri database dengan ratusan koneksi baru, menyebabkan database mati permanen.
- *Pertanyaan:* Mengapa liveness probe tersebut keliru, dan bagaimana pemisahan probe antara liveness dan readiness yang tepat untuk mencegah fenomena thundering herd ini?

### Skenario B: The 50 Expensive Cloud Load Balancers
Sebuah startup memigrasikan 50 microservices ke AWS EKS. Untuk setiap service, engineer membuat manifest dengan `type: LoadBalancer`. Di akhir bulan, CFO terkejut melihat tagihan AWS Network Load Balancer membengkak ribuan dolar.
- *Pertanyaan:* Bagaimana rancangan arsitektur Ingress Controller (seperti AWS Load Balancer Controller atau Nginx Ingress) untuk mengonsolidasikan seluruh 50 service ke dalam 1 public Load Balancer tunggal?

### Skenario C: The Accidental Production Secret Leak
Seorang developer meng-commit file `k8s-secret.yaml` yang memuat password Redis produksi yang di-encode base64 ke GitHub public repository.
- *Pertanyaan:* Arsitektur manajemen secret apa (misal: External Secrets Operator, Sealed Secrets, atau HashiCorp Vault) yang seharusnya diterapkan agar file Git hanya memuat referensi aman tanpa pernah memuat nilai secret asli?

---

## 4. Chapter Challenge
**Tantangan Praktis: The Complete Zero-Downtime Helm Delivery**
Rancang sebuah paket Helm Chart microservice produksi yang memuat:
1. **Deployment Template**:
   - 3 replica dengan strategi `RollingUpdate (maxSurge=1, maxUnavailable=0)`.
   - `readinessProbe` dan `livenessProbe` independen.
   - Resource `requests` dan `limits` untuk CPU dan Memory.
2. **ConfigMap & Secret**: Menginjeksikan konfigurasi aplikasi via environment variable.
3. **ClusterIP Service**: Port 80 -> TargetPort 3000.
4. **Ingress Spec**: Mendefinisikan Host `api.corp.internal` dengan TLS cert reference.
5. Uji coba templating dan buktikan mekanisme rollback dapat mengembalikan konfigurasi ke versi stabil sebelumnya.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur Control Plane (apiserver, etcd, scheduler, controller-manager) dan Worker Nodes (kubelet, kube-proxy).
- [ ] Abstraksi Pod, ReplicaSet, Deployment, dan Service.
- [ ] Model perutean traffic Ingress Layer-7 dan integrasi TLS cert-manager.
- [ ] Konsep pemisahan konfigurasi via ConfigMaps dan Secrets.
- [ ] Package management dan parameterized templating menggunakan Helm.

### Saya tidak perlu menghafal:
- [ ] Ratusan parameter spesifikasi skema OpenAPI Kubernetes (cukup gunakan `kubectl explain <resource>`).
- [ ] Sintaks internal driver CNI iptables/eBPF tingkat rendah.

### Saya harus bisa melakukan:
- [ ] Menulis manifest Deployment dan Service yang siap produksi.
- [ ] Melakukan rilis rolling update dan rollback instan via `kubectl` atau `helm`.
- [ ] Mendiagnosis status Pod bermasalah (`CrashLoopBackOff`, `ImagePullBackOff`, `OOMKilled`).

---
*Ketik **LANJUT** untuk berpindah ke BAB 05: Infrastructure as Code (IaC) dengan Terraform & OpenTofu.*
