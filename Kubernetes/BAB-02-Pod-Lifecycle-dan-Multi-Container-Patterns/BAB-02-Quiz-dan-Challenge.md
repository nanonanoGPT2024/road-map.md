# BAB 02 — Quiz & Chapter Challenge: Pod Lifecycle & Multi-Container Patterns

---
[⬅️ Module 02: Multi-Container Patterns](./Module-02-Multi-Container-Patterns-Sidecar-Init-dan-Ephemeral.md) | [📋 Silabus Induk](../README.md) | [BAB 03 Module 01: Deployments & Rollbacks ➡️](../BAB-03-Workload-Controllers/Module-01-Deployments-RollingUpdate-Strategies-dan-Rollbacks.md)
---

Dokumen ini menguji pemahaman Anda terhadap arsitektur siklus hidup Pod, konfigurasi ketiga tipe health probes (`startupProbe`, `livenessProbe`, `readinessProbe`), mekanisme zero-downtime graceful termination, serta implementasi pola multi-kontainer (Init Containers, Sidecars, Ambassador, Adapter, dan Ephemeral Debugging).

---

## Bagian 1: Basic Quiz (5 Pertanyaan)

### Soal 1
Apa perbedaan mendasar antara aksi yang diambil Kubernetes saat `livenessProbe` gagal dibandingkan saat `readinessProbe` gagal?
- A. Liveness probe menghapus Pod secara permanen, sedangkan readiness probe mematikan seluruh node.
- B. Liveness probe yang gagal menyebabkan kontainer di-**restart** paksa oleh Kubelet, sedangkan readiness probe yang gagal hanya **mencabut IP Pod dari Service Endpoints** (menghentikan pengiriman traffic) tanpa me-restart kontainer.
- C. Keduanya melakukan restart kontainer secara bersamaan.
- D. Tidak ada perbedaan aksi sama sekali.

### Soal 2
Mengapa aplikasi yang membutuhkan waktu bootstrapping lambat (seperti Java Spring Boot yang memakan waktu 45 detik) membutuhkan `startupProbe`?
- A. Agar Kubelet otomatis mengalokasikan RAM 16GB.
- B. Agar `livenessProbe` dan `readinessProbe` dinonaktifkan sementara waktu selama inisialisasi awal, sehingga kontainer tidak terbunuh secara prematur akibat timeout liveness probe.
- C. Agar compiler otomatis mengompilasi biner ke C++.
- D. Karena startupProbe wajib ada di semua manifest Pod Kubernetes.

### Soal 3
Bagaimana dua kontainer yang berbeda di dalam satu Pod yang sama dapat saling bertukar data atau mengirim HTTP request secara langsung?
- A. Melalui koneksi internet publik.
- B. Melalui alamat loopback `localhost` (karena berbagi Linux Network Namespace yang sama) atau melalui shared volume `emptyDir`.
- C. Melalui Bluetooth.
- D. Kontainer di dalam satu Pod dilarang berkomunikasi.

### Soal 4
Apa yang terjadi pada kontainer aplikasi utama jika salah satu Init Container mengalami kegagalan (keluar dengan Exit Code 1)?
- A. Kontainer utama tetap dijalankan tanpa mempedulikan Init Container.
- B. Kubelet akan menahan Pod pada status `Init:CrashLoopBackOff` dan kontainer aplikasi utama **TIDAK AKAN PERNAH DIJALANKAN** hingga Init Container berhasil selesai dengan Exit Code 0.
- C. Node worker akan otomatis me-reboot dirinya sendiri.
- D. Kubernetes menghapus namespace tempat Pod berada.

### Soal 5
Bagaimana perintah CLI yang tepat untuk menyuntikkan kontainer sementara (**Ephemeral Container**) ke dalam Pod produksi minimal yang tidak memiliki shell untuk keperluan troubleshooting jaringan?
- A. `kubectl ssh pod-name`
- B. `kubectl run debug-pod --image=busybox`
- C. `kubectl debug -it <nama-pod> --image=nicolaka/netshoot --target=<nama-container>`
- D. `docker attach <pod-id>`

---

## Bagian 2: Intermediate Quiz (5 Pertanyaan)

### Soal 6
Mengapa menyematkan pengecekan koneksi database eksternal (misal `SELECT 1 FROM postgres`) ke dalam `livenessProbe` dianggap sebagai **Anti-Pattern fatal** di lingkungan microservices?
- A. Karena query SQL membutuhkan biaya lisensi tambahan.
- B. Karena jika database mengalami overload sementara atau restart singkat, seluruh Pod microservices di kluster akan serempak gagal liveness probe dan me-restart diri bersamaan (*cascading failure*), yang saat hidup kembali akan membanjiri database dengan ratusan koneksi baru (*thundering herd problem*).
- C. Karena liveness probe hanya mendukung protokol UDP.
- D. Karena Kubelet menolak string query SQL.

### Soal 7
Pada siklus hidup Graceful Termination, mengapa disarankan menyematkan hook `lifecycle.preStop: exec: command: ["/bin/sh", "-c", "sleep 5"]` pada aplikasi web yang melayani traffic produksi?
- A. Untuk membuang waktu agar tagihan cloud membengkak.
- B. Untuk memberikan jeda waktu propagasi bagi Kube-Proxy, Ingress Controller, dan CoreDNS di seluruh node kluster agar sempat mencabut IP Pod tersebut dari routing table sebelum proses aplikasi utama menerima `SIGTERM`.
- C. Agar kernel Linux sempat melakukan defragmentasi hard disk.
- D. Karena perintah sleep wajib menurut standar POSIX.

### Soal 8
Apa keunggulan utama dari fitur **Native Sidecar Containers** (Kubernetes v1.28+) yang dideklarasikan di `initContainers` dengan `restartPolicy: Always` dibandingkan pola sidecar konvensional pada workload Kubernetes Job?
- A. Mengurangi pemakaian memori hingga 90%.
- B. Menyelesaikan masalah "Job tidak pernah selesai": Native sidecar akan start sebelum kontainer aplikasi, tetap hidup selama batch job bekerja, dan secara otomatis dimatikan oleh Kubelet saat kontainer utama menyelesaikan tugasnya (Exit 0).
- C. Memungkinkan sidecar berjalan tanpa kernel Linux.
- D. Mengubah Pod menjadi VM.

### Soal 9
Manakah pernyataan yang paling tepat mengenai alokasi resource (`requests` dan `limits`) pada Pod yang memiliki Init Containers dan App Containers?
- A. Effective resource request Pod adalah penjumlahan alokasi seluruh init container ditambah seluruh app container.
- B. Effective resource request Pod adalah nilai **tertinggi** antara alokasi Init Container individual terbesar ATAU jumlah total alokasi seluruh App Containers.
- C. Init container tidak mengonsumsi resource CPU sama sekali.
- D. Resource limit Pod hanya dihitung dari kontainer pertama.

### Soal 10
Pola multi-kontainer manakah yang bertindak sebagai proxy outbound lokal yang menyederhanakan koneksi aplikasi ke kluster eksternal yang kompleks (misal aplikasi hanya menghubungi `localhost:6379`, lalu proxy yang menangani sharding dan routing ke Redis cluster)?
- A. Pola Adapter.
- B. Pola Ambassador.
- C. Pola ReplicaSet.
- D. Pola DaemonSet.

---

## Bagian 3: Scenario-Based Questions (3 Skenario)

### Skenario 1: Bencana Flapping Pods saat Flash Sale
Sebuah e-commerce mengalami lonjakan traffic 10x lipat saat kampanye diskon jam 12 malam:
- Service API memiliki 30 replika Pod.
- `livenessProbe` dikonfigurasi dengan `timeoutSeconds: 1` dan `failureThreshold: 2`.
- Karena beban CPU aplikasi naik menjadi 90%, endpoint aplikasi membutuhkan waktu 1.4 detik untuk merespons probe HTTP.
- Akibatnya, seluruh 30 Pod secara acak dibunuh dan di-restart oleh Kubelet setiap 2 menit, memicu error 502 massal bagi ribuan pembeli.
- **Pertanyaan**: Jelaskan 3 kesalahan konfigurasi probe pada skenario di atas, dan tuliskan perbaikan parameter probe (`timeoutSeconds`, `periodSeconds`, `failureThreshold`, serta pemisahan shallow vs deep healthcheck) untuk menstabilkan sistem!

### Skenario 2: Migrasi Skema Database Gagal Memblokir Rilis Baru
Sebuah tim men-deploy versi baru aplikasi akuntansi. Di dalam PodSpec, mereka menaruh perintah migrasi database (`npm run db:migrate`) di dalam kontainer aplikasi utama (`containers[0]`).
Karena terdapat 10 replika Pod yang di-deploy serempak oleh Deployment, kesepuluh kontainer tersebut serentak mengeksekusi perintah migrasi tabel yang sama, menyebabkan database terkunci (*table lock deadlock*) dan korupsi skema.
- **Pertanyaan**: Mengapa menjalankan migrasi di dalam kontainer aplikasi utama adalah kesalahan fatal, dan bagaimana pola Init Container atau Kubernetes One-Off Job menyelesaikan masalah ini dengan aman?

### Skenario 3: Forensik Runtime pada Pod Distroless yang Terkena Hack
Sebuah Pod API di lingkungan staging yang dibangun menggunakan image Google Distroless (tanpa package manager, tanpa curl, tanpa shell) dicurigai sedang melakukan koneksi outbound mencurigakan ke alamat IP mining crypto.
Developer tidak bisa masuk menggunakan `kubectl exec` karena tidak ada `/bin/sh`.
- **Pertanyaan**: Tuliskan perintah `kubectl debug` lengkap untuk menyuntikkan kontainer toolbox keamanan (`nicolaka/netshoot`) ke dalam Pod tersebut dengan process sharing aktif (`--target`), dan sebutkan utilitas jaringan apa saja yang dapat digunakan untuk menganalisis koneksi tersebut!

---

## Bagian 4: Chapter Challenge

### Tantangan Praktis: Hardened Production Microservice Pod Architect
1. **Skenario**:
   Anda diminta merancang manifest Pod produksi untuk service transfer bank:
   - Aplikasi utama berbasis Java yang membutuhkan bootstrap 30 detik.
   - Init Container 1: Memverifikasi database PostgreSQL siap (`pg_isready`).
   - Init Container 2 (Native Sidecar): Vault Agent yang terus menyegarkan token JWT ke volume in-memory `emptyDir`.
   - Konfigurasi `startupProbe`, `livenessProbe`, dan `readinessProbe` yang robust.
   - Konfigurasi Graceful Termination dengan `preStop` hook untuk menjamin zero dropped requests.
2. **Deliverables**:
   - Manifest YAML Pod lengkap (`production-bank-pod.yaml`) yang memenuhi seluruh persyaratan di atas.
   - Penjelasan teknis mengenai trade-off parameter probe yang Anda pilih.

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Mengapa Kubernetes mengelompokkan kontainer ke dalam abstraksi Pod.
- [ ] Empat Pod Phases: `Pending`, `Running`, `Succeeded`, `Failed`.
- [ ] Perbedaan esensial fungsi dan dampak kegagalan antara `startupProbe`, `livenessProbe`, dan `readinessProbe`.
- [ ] Alur Graceful Termination: `preStop` -> `SIGTERM` -> `terminationGracePeriodSeconds` -> `SIGKILL`.
- [ ] Siklus hidup dan sifat blocking dari Init Containers.
- [ ] Pola Sidecar, Ambassador, dan Adapter.
- [ ] Fitur Native Sidecars di Kubernetes v1.28+.
- [ ] Cara kerja Ephemeral Containers untuk live debugging container distroless.

### Saya Tidak Perlu Menghafal:
- Seluruh ratusan opsi field OpenAPI pada PodSpec (cukup pahami hierarki spec containers, probes, dan lifecycle).
- Struktur internal kernel Linux IPC shared memory segment ID.

### Saya Harus Bisa Melakukan:
- [ ] Menulis konfigurasi `startupProbe`, `livenessProbe`, dan `readinessProbe` yang tepat.
- [ ] Mengonfigurasi `preStop` hook untuk eliminasi error HTTP 502 saat rolling update.
- [ ] Menulis manifest Pod dengan Init Containers yang menggunakan volume `emptyDir`.
- [ ] Menggunakan `kubectl debug` untuk menyelidiki Pod produksi minimal.
- [ ] Mendiagnosa insiden `CrashLoopBackOff` menggunakan `kubectl logs --previous`.

---
[⬅️ Module 02: Multi-Container Patterns](./Module-02-Multi-Container-Patterns-Sidecar-Init-dan-Ephemeral.md) | [📋 Silabus Induk](../README.md) | [BAB 03 Module 01: Deployments & Rollbacks ➡️](../BAB-03-Workload-Controllers/Module-01-Deployments-RollingUpdate-Strategies-dan-Rollbacks.md)
---
