# Evaluasi Bab 07: Container Orchestration & Resilient Kubernetes Operations

---

## I. Basic Questions (Pilihan Ganda & Isian Singkat)

### Soal 1
Perhatikan skenario berikut: Sebuah Deployment memiliki `replicas: 3`. Dikonfigurasikan PodDisruptionBudget (PDB) dengan `minAvailable: 2`. Jika seorang engineer menjalankan perintah `kubectl drain` pada node yang menampung 2 pod dari deployment tersebut secara bersamaan, apa yang akan dilakukan oleh Kubernetes Eviction API?
- A. Menggusur kedua pod secara bersamaan untuk mempercepat proses drain node.
- B. Menolak penggusuran kedua pod secara permanen dan membatalkan status cordon node.
- C. Mengizinkan 1 pod digusur terlebih dahulu, dan menahan (delay/reject) penggusuran pod kedua sampai pod pengganti di node lain berada dalam status `Ready`.
- D. Mengubah status pod kedua menjadi `Terminating` seketika tanpa menunggu pod pengganti.

### Soal 2
Sebuah kontainer dihentikan oleh Kubernetes dengan exit code `137`. Apa penyebab pasti dari keluaran exit code ini pada sistem Linux?
- A. Aplikasi mengalami unhandled runtime exception di layer bahasa pemrograman (SIGSEGV).
- B. Proses dimatikan secara paksa oleh sinyal `SIGKILL` (sinyal 9) yang dipicu oleh cgroup kernel Out-of-Memory (OOM) Killer (`128 + 9 = 137`).
- C. Konfigurasi Liveness probe gagal berturut-turut melebihi failureThreshold.
- D. Proses berhasil keluar secara normal setelah menerima sinyal graceful termination (`SIGTERM`).

### Soal 3
Kapan *Readiness Probe* yang gagal menyebabkan sebuah Pod di-restart oleh kubelet?
- A. Ketika failureThreshold bernilai lebih dari 3.
- B. Ketika pod berada di dalam namespace `kube-system`.
- C. Kubelet **tidak pernah** merestart kontainer akibat kegagalan Readiness Probe; kubelet hanya mencabut IP Pod dari tabel Service Endpoints.
- D. Ketika Startup Probe belum dikonfigurasi pada pod tersebut.

### Soal 4
Berapa jumlah minimum node yang dibutuhkan pada klaster etcd multi-master untuk dapat menoleransi kegagalan simultan sebanyak 2 node tanpa kehilangan konsensus korum Raft?
- A. 3 node
- B. 4 node
- C. 5 node
- D. 7 node

### Soal 5
Manakah kombinasi konfigurasi resource di bawah ini yang menghasilkan status Quality of Service (QoS) **Guaranteed** pada sebuah Pod?
- A. `requests.cpu: 500m`, `limits.cpu: 1000m`, `requests.memory: 1Gi`, `limits.memory: 1Gi`
- B. Hanya mendefinisikan `requests.cpu` dan `requests.memory` tanpa mendefinisikan limits.
- C. Nilai `requests` sama persis dengan nilai `limits` untuk CPU dan Memory pada seluruh kontainer di dalam Pod.
- D. Menetapkan `priorityClassName: system-cluster-critical`.

---

## II. Intermediate Questions (Analisis Kasus & Troubleshooting)

### Soal 6
Jelaskan secara teknis mengapa menambahkan perintah `sleep 10` di dalam lifecycle hook `preStop` dapat mengeliminasi HTTP 502/504 Bad Gateway errors pada Ingress/Load Balancer selama proses rolling update berlangsung!

### Soal 7
Aplikasi backend berbasis Go mengalami degradasi latensi tinggi (P99 melesat ke 4.000ms), tetapi penggunaan CPU yang tertera di `kubectl top pod` hanya 65% dari resource limit yang dialokasikan. Setelah dicek di cgroup host, metrik `nr_throttled` bertambah ribuan setiap menit. Jelaskan mekanisme Linux Completely Fair Scheduler (CFS) quota yang menyebabkan insiden ini dan bagaimana solusinya!

### Soal 8
Sebuah Pod memiliki konfigurasi:
```yaml
initialDelaySeconds: 0
periodSeconds: 2
failureThreshold: 1
livenessProbe:
  httpGet:
    path: /health
    port: 8080
```
Aplikasi membutuhkan waktu 45 detik untuk melakukan koneksi ke database dan memuat cache lokal saat pertama kali menyala. Analisis apa yang akan terjadi pada pod tersebut ketika di-deploy ke klaster!

### Soal 9
Sebuah node worker mengalami kondisi `MemoryPressure`. Kubelet harus melakukan penggusuran (eviction) pod untuk menyelamatkan kestabilan kernel host. Di antara Pod A (QoS: Guaranteed, memori terpakai 900MB/1GB), Pod B (QoS: Burstable, memori terpakai 300MB/request 200MB/limit 500MB), dan Pod C (QoS: BestEffort, memori terpakai 50MB), tentukan urutan prioritas pod yang akan dieksekusi mati oleh kubelet beserta alasan teknisnya berdasarkan `oom_score_adj`!

### Soal 10
Jelaskan resiko arsitektural jika sebuah klaster etcd dikonfigurasi dengan 4 node kontrol plane dibandingkan jika hanya memiliki 3 node kontrol plane! Hubungkan jawaban Anda dengan formula korum Raft.

---

## III. Scenario-Based Questions (Kasus Arsitektur Skala Besar)

### Skenario 1: The Cascading Database Outage
**Konteks**: Platform e-commerce menerapkan Liveness Probe pada service katalog barang dengan endpoint `/healthz` yang melakukan query langsung: `SELECT * FROM categories LIMIT 1;`. Ketika terjadi lonjakan traffic Flash Sale, koneksi pool database utama penuh (100% capacity), menyebabkan query ke database mengalami timeout selama 3 detik.
- **Pertanyaan**:
  1. Uraikan rentetan peristiwa (*cascading failure chain*) yang terjadi pada klaster Kubernetes akibat konfigurasi probe ini.
  2. Rancang ulang arsitektur probing (Startup, Liveness, Readiness) yang tepat untuk mencegah bencana sistemik tersebut tanpa menurunkan observabilitas kesehatan aplikasi.

### Skenario 2: The Blocked Cordon & Drain
**Konteks**: Tim Platform Engineering menjalankan automasi upgrade EKS node group via tools automasi Terraform/Karpenter. Tiba-tiba proses upgrade macet (*stuck*) selama 4 jam pada tahap draining node `ip-10-0-45-12.internal`. Aplikasi internal mengeluhkan deployment pipeline mereka terblokir.
- **Pertanyaan**:
  1. Bagaimana urutan langkah investigasi terstruktur (menggunakan kubectl command) untuk mengidentifikasi penyebab pasti kemacetan drain tersebut?
  2. Jika ditemukan penyebabnya adalah PDB yang salah konfigurasi bersamaan dengan keberadaan Pod unready yang dibuat tanpa controller (naked pod) dan pod dengan `emptyDir`, tuliskan perintah intervensi darurat untuk menyelesaikan drain tanpa mematikan klaster!

### Skenario 3: Corrupted Control Plane Disaster Recovery
**Konteks**: Terjadi lonjakan listrik pada on-premise datacenter yang merusak storage pada 2 dari 3 node control plane etcd klaster produksi Kubernetes. Klaster kehilangan quorum ($1/3$ node tersisa). Kube-apiserver menolak seluruh koneksi (HTTP 500 Internal Server Error). Tim SRE memiliki file backup snapshot `snapshot-clean.db` yang diambil 30 menit sebelum insiden.
- **Pertanyaan**:
  Tuliskan langkah-langkah runbook recovery bencana secara kronologis dan tepat untuk merestorasi klaster tersebut menjadi multi-master yang sehat kembali menggunakan snapshot yang ada!

---

## IV. Practical Chapter Challenge: Resilient Multi-Tier Infrastructure

### Deskripsi Masalah
Anda ditugaskan merancang konfigurasi *resilient operational blueprint* untuk sistem core-banking transaksi moneter dengan SLA ketersediaan 99.99%.

### Ketentuan Implementasi
1. **Node Topology**:
   - Terdapat node pool reguler dan node pool terisolasi untuk transaksi keuangan. Node pool keuangan memiliki Taint: `tier=financial-core:NoSchedule`.
2. **Karakteristik Workload**:
   - Deployment `financial-engine` wajib berjalan hanya di node `tier=financial-core`.
   - Menggunakan QoS Class `Guaranteed` (CPU 2 Core, Memory 4Gi).
   - Mengalokasikan Go Runtime heap limit (`GOMEMLIMIT`) yang aman dari OOM Killer.
   - Wajib kebal terhadap rolling update downtime: tidak boleh ada waktu di mana replika aktif kurang dari 3 pod. Total replika = 5.
   - Pod tidak boleh dijadwalkan pada node fisik yang sama (Anti-Affinity Hard Requirement).
   - Menyediakan waktu toleransi drain 60 detik dengan penanganan `preStop` untuk flushing data transaksi aktif.
   - Probes yang dirancang tahan terhadap lonjakan beban (*traffic spike resilience*).

### Tugas Peserta
Tuliskan satu file manifest Kubernetes lengkap (`resilient-banking-blueprint.yaml`) yang menggabungkan:
1. `PodDisruptionBudget`
2. `PriorityClass`
3. `Deployment` dengan seluruh spesifikasi konfigurasi di atas.