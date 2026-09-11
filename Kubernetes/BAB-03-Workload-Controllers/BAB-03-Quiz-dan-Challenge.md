# BAB 03 — Quiz & Chapter Challenge: Workload Controllers (Deployments, StatefulSets, DaemonSets, Jobs)

---
[⬅️ Module 02: StatefulSets & DaemonSets](./Module-02-StatefulSets-DaemonSets-Jobs-dan-CronJobs.md) | [📋 Silabus Induk](../README.md) | [BAB 04 Module 01: ConfigMaps & Downward API ➡️](../BAB-04-Konfigurasi-Secrets-dan-Decoupled-Architecture/Module-01-ConfigMaps-Downward-API-dan-Hot-Reload.md)
---

Dokumen ini dirancang untuk menguji keahlian Anda dalam memilih, mengonfigurasi, dan mengoperasikan kontroler beban kerja Kubernetes tingkat lanjut: Deployment RollingUpdate & Rollbacks, StatefulSets & Headless Services, DaemonSets per-node scheduling, serta Jobs/CronJobs batch policies.

---

## Bagian 1: Basic Quiz (5 Pertanyaan)

### Soal 1
Apa peran dari ReplicaSet di dalam hierarki Kubernetes Deployment?
- A. Mengompresi file log container.
- B. Menjaga jumlah replika Pod yang berjalan agar selalu sesuai dengan deklarasi `spec.replicas` berdasarkan pencocokan label selector (`matchLabels`).
- C. Menyediakan storage cloud untuk Pod.
- D. Menggantikan peran DNS server.

### Soal 2
Apa arti dari konfigurasi strategi Deployment berikut:
`maxSurge: 1` dan `maxUnavailable: 0` pada Deployment dengan 4 replika?
- A. Selama rolling update, kapasitas Pod sehat tidak boleh pernah turun di bawah 4, dan jumlah Pod total di kluster maksimal 5 Pod (4 + 1).
- B. Seluruh 4 Pod lama dimatikan serentak sebelum Pod baru dibuat.
- C. Update hanya berjalan pada 1 Pod saja, 3 Pod lainnya dibiarkan versi lama selamanya.
- D. Deployment akan otomatis dibatalkan jika melebihi 1 detik.

### Soal 3
Mengapa database relasional terdistribusi (seperti PostgreSQL Primary-Replica atau MongoDB) wajib menggunakan **StatefulSet** alih-alih `Deployment` biasa?
- A. Karena Deployment dilarang me-mount volume hard disk.
- B. Karena StatefulSet memberikan penamaan hostname deterministik yang stabil (`db-0`, `db-1`), bootstrapping berurutan, dan volume storage khusus per-Pod (`volumeClaimTemplates`) yang tidak saling menimpa data.
- C. Karena StatefulSet otomatis menggratiskan lisensi database.
- D. Karena Deployment hanya bisa berjalan di bahasa pemrograman PHP.

### Soal 4
Workload Controller manakah yang menjamin bahwa tepat SATU replika Pod akan dijalankan pada setiap worker node yang memenuhi syarat di dalam kluster Kubernetes (sangat cocok untuk agen pemantau atau log collector)?
- A. ReplicaSet
- B. Deployment
- C. DaemonSet
- D. CronJob

### Soal 5
Perintah CLI manakah yang digunakan untuk membatalkan proses deployment yang bermasalah dan mengembalikan sistem secara instan ke revisi ReplicaSet sebelumnya?
- A. `kubectl delete deployment --force`
- B. `kubectl rollout undo deployment/<nama-deployment>`
- C. `kubectl restart deployment`
- D. `kubectl rollback pod`

---

## Bagian 2: Intermediate Quiz (5 Pertanyaan)

### Soal 6
Apa fungsi utama dari **Headless Service** (`clusterIP: None`) saat dipasangkan dengan StatefulSet?
- A. Menghapus nama domain DNS kluster.
- B. Menginstruksikan CoreDNS untuk tidak mengembalikan satu Virtual IP tunggal, melainkan mengembalikan A Record langsung ke alamat IP individual masing-masing Pod (`pod-name.service-name`), memungkinkan komunikasi langsung antar-peer database.
- C. Menutup seluruh port jaringan eksternal.
- D. Mengubah alamat IP worker node menjadi statis.

### Soal 7
Jika Anda menghapus sebuah StatefulSet menggunakan perintah `kubectl delete statefulset my-db`, apa yang terjadi pada PersistentVolumeClaims (PVC) yang dibuat oleh `volumeClaimTemplates`?
- A. Seluruh PVC dan data di dalamnya otomatis terhapus seketika.
- B. Demi melindungi keselamatan data dari kehilangan yang tidak disengaja, Kubernetes **SENGAJA TIDAK MENGHAPUS PVC**; PVC tetap tersimpan dan harus dihapus secara eksplisit manual oleh administrator.
- C. PVC otomatis dipindahkan ke namespace `kube-system`.
- D. Hard disk cloud otomatis diformat ulang.

### Soal 8
Pada CronJob, apa yang terjadi jika Anda mengatur `concurrencyPolicy: Forbid` dan jadwal Cron berikutnya tiba saat eksekusi Job sebelumnya belum selesai?
- A. CronJob akan mematikan paksa Job yang lama.
- B. Eksekusi Job baru yang terjadwal akan dilewati (*skipped* / tidak dijalankan) demi mencegah dua proses batch memodifikasi data yang sama secara bersamaan.
- C. Kedua Job akan dijalankan secara paralel.
- D. Kluster Kubernetes akan me-reboot diri.

### Soal 9
Apa peran dari label internal **`pod-template-hash`** yang otomatis disematkan oleh Deployment Controller pada ReplicaSet dan Pod?
- A. Mengenkripsi password pengguna di database.
- B. Berfungsi sebagai hash sidik jari dari blok `spec.template` Pod untuk membedakan ReplicaSet versi lama dengan ReplicaSet versi baru selama proses rolling update.
- C. Menghitung penggunaan memori Pod dalam format megabyte.
- D. Menandai arsitektur CPU worker node (ARM64 vs AMD64).

### Soal 10
Mengapa DaemonSet pemantauan sistem (seperti Prometheus Node Exporter) membutuhkan deklarasi `tolerations` untuk taint `node-role.kubernetes.io/control-plane:NoSchedule`?
- A. Agar metrik CPU/RAM dari server master (control plane) juga dapat dikumpulkan dan dipantau, karena secara default node master menolak penempatan Pod biasa.
- B. Agar agent dapat mengubah password root Linux.
- C. Untuk mengizinkan pod berjalan tanpa limit memori.
- D. Karena daemonset menolak berjalan di worker node.

---

## Bagian 3: Scenario-Based Questions (3 Skenario)

### Skenario 1: Hung Rollout Menyelamatkan Platform E-Commerce
Sebuah tim frontend merilis image web `v4.0.0` dengan konfigurasi Deployment:
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```
Developer lupa menyertakan file binary di image `v4.0.0`, menyebabkan kontainer baru exit dengan kode error 127 (`CrashLoopBackOff`).
- **Pertanyaan**: Jelaskan mengapa seluruh pengguna toko online masih tetap bisa berbelanja secara normal tanpa ada downtime atau error 502 sama sekali, dan tuliskan perintah perbaikan cepat yang harus dieksekusi on-call engineer!

### Skenario 2: Bencana Split-Brain Database Akibat Menggunakan Deployment
Sebuah tim backend men-deploy database MySQL 2-replika menggunakan `kind: Deployment` dan volume mount AWS EBS yang sama (`pvc-mysql-shared`).
Dalam waktu 1 jam, data tabel transaksi perbankan menjadi korup dan server MySQL crash dengan pesan error disk locking.
- **Pertanyaan**: Jelaskan mengapa `Deployment` dilarang keras untuk database clustering, dan bagaimana arsitektur `StatefulSet` bersama `volumeClaimTemplates` dan `Headless Service` menyelesaikan masalah isolasi disk dan identitas replika secara tuntas!

### Skenario 3: Overlapping Backup CronJob Menghancurkan Kinerja Database
Sebuah perusahaan finansial memiliki CronJob backup harian yang dijadwalkan setiap hari pukul 02:00 pagi. Karena ukuran database bertambah menjadi 2 TB, proses backup memakan waktu 26 jam (melebihi 1 hari).
Pada pukul 02:00 pagi di hari kedua, proses backup kedua dijalankan secara paralel karena `concurrencyPolicy` dibiarkan default (`Allow`). Dua proses backup raksasa yang berjalan bersamaan menghabiskan 100% disk I/O, melumpuhkan transaksi bisnis perusahaan.
- **Pertanyaan**: Analisis kegagalan operasional ini dan tuliskan perbaikan konfigurasi pada manifest CronJob (`concurrencyPolicy`, `startingDeadlineSeconds`, `successfulJobsHistoryLimit`) untuk mencegah bencana ini terulang kembali!

---

## Bagian 4: Chapter Challenge

### Tantangan Praktis: High-Availability Distributed Kafka & DaemonSet Platform
1. **Skenario**:
   Anda diminta merancang infrastruktur orkestrasi untuk cluster Apache Kafka di Kubernetes:
   - 3 Broker Kafka dikelola menggunakan **StatefulSet** dengan **Headless Service** (`kafka-hs`).
   - Setiap broker dialokasikan storage NVMe dedicated 100GB via `volumeClaimTemplates`.
   - Menyiapkan satu **DaemonSet** `promtail` untuk membaca log dari seluruh host node.
   - Menyiapkan satu **CronJob** mingguan untuk membersihkan log lama dengan `concurrencyPolicy: Forbid`.
2. **Deliverables**:
   - File manifest lengkap `kafka-statefulset.yaml` (Headless Service + StatefulSet).
   - File manifest `logging-daemonset.yaml`.
   - File manifest `cleaner-cronjob.yaml`.

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Alur orkestrasi: Deployment mengontrol ReplicaSets, ReplicaSets mengontrol Pods.
- [ ] Mekanisme kerja `maxSurge` dan `maxUnavailable` pada RollingUpdate.
- [ ] Kapan memilih StatefulSet vs Deployment vs DaemonSet vs Job/CronJob.
- [ ] Fungsi Headless Service (`clusterIP: None`) dalam Service Discovery FQDN StatefulSet.
- [ ] Alasan mengapa PVC StatefulSet tidak dihapus otomatis saat Pod dihapus.
- [ ] Tiga mode `concurrencyPolicy` pada CronJob: `Allow`, `Forbid`, `Replace`.
- [ ] Mekanisme rollback instan menggunakan `kubectl rollout undo`.

### Saya Tidak Perlu Menghafal:
- Rumus kriptografi internal pembuatan hash `pod-template-hash`.
- Daftar seluruh opsi flag daemonset scheduler kernel.

### Saya Harus Bisa Melakukan:
- [ ] Mengonfigurasi Deployment dengan zero-downtime rolling update parameters.
- [ ] Melacak riwayat revisi dan melakukan rollback instan dengan `kubectl rollout undo`.
- [ ] Menulis manifest StatefulSet lengkap dengan Headless Service dan `volumeClaimTemplates`.
- [ ] Menulis manifest DaemonSet dengan tolerations untuk kontrol plane node.
- [ ] Menulis CronJob dengan batas percobaan `backoffLimit` dan kebijakan konkurensi `Forbid`.

---
[⬅️ Module 02: StatefulSets & DaemonSets](./Module-02-StatefulSets-DaemonSets-Jobs-dan-CronJobs.md) | [📋 Silabus Induk](../README.md) | [BAB 04 Module 01: ConfigMaps & Downward API ➡️](../BAB-04-Konfigurasi-Secrets-dan-Decoupled-Architecture/Module-01-ConfigMaps-Downward-API-dan-Hot-Reload.md)
---
