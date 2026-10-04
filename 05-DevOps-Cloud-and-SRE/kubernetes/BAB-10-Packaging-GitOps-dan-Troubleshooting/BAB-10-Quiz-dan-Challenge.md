---
[⬅️ Module 02: GitOps & Troubleshooting](./Module-02-GitOps-ArgoCD-dan-Production-Troubleshooting.md) | [📋 Silabus Induk](../README.md) | [CAPSTONE PROJECT KUBERNETES ➡️](../CAPSTONE-PROJECT-Enterprise-MultiTenant-Microservices-K8s.md)
---

# BAB 10: Packaging (Helm/Kustomize), GitOps (ArgoCD), & Troubleshooting — Quiz & Chapter Challenge

Dokumen ini berisi pengujian pemahaman konseptual, analisis skenario insiden produksi riil, serta tantangan implementasi sistematis untuk BAB 10.

---

## Bagian 1: Quiz Konseptual Dasar (5 Soal)

### Soal 1
Apa perbedaan mendasar antara model pengelolaan manifest Helm v3 dan Kustomize?
- A. Helm menggunakan template engine berbasis parameterisasi kurung kurawal `{{ }}`, sedangkan Kustomize menggunakan deklarasi YAML murni tanpa template (*template-free*) dengan sistem pelapisan (*Base and Overlays*).
- B. Helm hanya berjalan di Windows, sedangkan Kustomize hanya berjalan di Linux.
- C. Helm tidak mendukung Rollback, sedangkan Kustomize memiliki rollback otomatis.
- D. Kustomize membutuhkan database MySQL eksternal.

### Soal 2
Di manakah Helm v3 menyimpan riwayat rilis (*release metadata*) dan state versi aplikasi di dalam cluster?
- A. Di dalam biner Tiller Pod di namespace `kube-system`.
- B. Di dalam file teks lokal di laptop developer.
- C. Di dalam objek `Secret` Kubernetes terenkripsi di namespace tempat rilis tersebut di-deploy (contoh: `sh.helm.release.v1.<nama-release>.v1`).
- D. Di dalam partisi swap Linux worker node.

### Soal 3
Bagaimana fitur `configMapGenerator` pada Kustomize memicu proses rolling restart secara otomatis pada Deployment ketika file konfigurasi diubah?
- A. Mengirimkan perintah kill SIGTERM langsung ke containerd daemon.
- B. Menghitung hash SHA-256 dari konten file dan menyematkannya pada nama ConfigMap (contoh: `app-config-g78hb4`), sehingga perubahan konfigurasi mengubah nama resource dan memaksa Deployment controller memperbarui Pod template.
- C. Me-reboot seluruh worker node.
- D. Mengubah izin chmod folder `/etc/config`.

### Soal 4
Dalam metodologi GitOps menggunakan ArgoCD, apa yang dilakukan oleh fitur `syncPolicy.automated.selfHeal: true`?
- A. Menghapus repositori Git jika terjadi conflict branch.
- B. Secara otomatis mendeteksi perubahan manual liar (*manual drift*) yang dilakukan langsung di live cluster (misal via `kubectl edit`) dan menimpa perubahan tersebut agar live cluster kembali persis seperti yang tertulis di repositori Git.
- C. Memperbaiki bug kode aplikasi di repositori GitHub menggunakan model AI.
- D. Membeli vCPU tambahan di AWS secara otomatis saat ada lonjakan traffic.

### Soal 5
Pada insiden container yang mati dengan status `OOMKilled` dan `Exit Code: 137`, apa arti matematis dari angka 137 dalam standar sistem operasi POSIX Linux?
- A. Port 137 NetBIOS diblokir oleh firewall.
- B. Nilai exit code 128 ditambah dengan nomor sinyal kernel `SIGKILL` (Sinyal 9): $128 + 9 = 137$, menandakan proses dimatikan paksa oleh Linux kernel OOM-Killer karena melebihi memory limit.
- C. Database PostgreSQL kehabisan koneksi pada port 137.
- D. Driver CSI mengalami disk failure pada sektor 137.

---

## Bagian 2: Quiz Skenario & Troubleshooting Tingkat Menengah (5 Soal)

### Soal 6
Sebuah Pod berstatus `CrashLoopBackOff` dan sudah me-restart sebanyak 12 kali. Engineer menjalankan perintah `kubectl logs my-pod-xyz` dan hanya melihat pesan kosong. Bagaimana cara melihat pesan error spesifik yang terjadi tepat sebelum container tersebut crash?
- A. Menjalankan `kubectl delete pod my-pod-xyz`.
- B. Menjalankan perintah `kubectl logs my-pod-xyz --previous` untuk membaca buffer log dari siklus kontainer yang mati sebelumnya.
- C. Memeriksa file `/var/log/messages` di laptop developer.
- D. Me-restart kube-apiserver.

### Soal 7
Aplikasi frontend melaporkan `HTTP 503 Service Unavailable`. Perintah `kubectl get endpoints my-service` menunjukkan hasil `<none>` (0 endpoints). Padahal ada 3 Pod backend yang berstatus `Running`. Apa penyebab paling umum dari masalah ini?
- A. Service tidak memiliki alamat ClusterIP.
- B. Ketidakcocokan antara label selector pada Service (`spec.selector`) dengan label yang terpasang pada metadata template Pod (`spec.template.metadata.labels`).
- C. Kube-proxy kehabisan IP pool iptables.
- D. Container backend belum mengaktifkan SSL/TLS.

### Soal 8
Developer mengeluhkan latensi tinggi (300-500ms) saat aplikasi memanggil API eksternal `payment.provider.com` dari dalam container Kubernetes, dan CoreDNS mengalami lonjakan beban. Diagnosa menunjukkan konfigurasi bawaan `/etc/resolv.conf` di container memiliki `options ndots:5`.
Mengapa `ndots:5` menyebabkan latensi tinggi pada pemanggilan domain eksternal tersebut?
- A. Container mencoba melakukan query DNS dengan menambahkan seluruh search domain lokal cluster (seperti `.production.svc.cluster.local`) secara berulang-ulang sebelum akhirnya mencoba resolve langsung ke internet, menghasilkan 3-4 query DNS NXDOMAIN yang sia-sia untuk setiap request.
- B. CoreDNS membatasi bandwidth jaringan hanya sebesar 5 Mbps.
- C. Port 53 UDP diblokir oleh AWS Security Group.
- D. Angka 5 berarti waktu timeout DNS diset ke 5 menit.

### Soal 9
Sebuah Deployment berhasil dibuat, namun Pod terjebak dalam status `CreateContainerConfigError`. Apa langkah diagnostik pertama yang harus dilakukan?
- A. Mengunduh ulang image Docker.
- B. Menjalankan `kubectl describe pod <pod-name>` untuk melihat nama ConfigMap atau Secret yang direferensikan dalam `env` atau `envFrom` yang ternyata belum dibuat atau typo namanya di namespace tersebut.
- C. Menghapus etcd cluster.
- D. Mengubah arsitektur node dari AMD64 ke ARM64.

### Soal 10
SRE ingin memastikan bahwa dalam pipeline GitOps ArgoCD, Database Migration Job harus dieksekusi hingga sukses tuntas sebelum Pod Backend di-deploy, dan Ingress baru dibuat setelah Backend siap. Fitur ArgoCD apa yang wajib digunakan?
- A. `argocd.argoproj.io/sync-wave` dengan bobot bertingkat (misal: Job di wave 0, Backend di wave 1, Ingress di wave 2).
- B. CronJob harian.
- C. Sleep 60 detik di script bash entrypoint container.
- D. Helm subcharts tanpa conditional check.

---

## Bagian 3: Skenario Kasus Arsitektur Tingkat Lanjut (3 Soal)

### Skenario 1: Zero-Trust Production GitOps Architecture
Rancang arsitektur pipeline deployment end-to-end untuk platform perbankan dengan persyaratan ketat:
1. Akses developer ke cluster produksi bersifat `Read-Only` (tanpa hak write/edit).
2. Setiap perubahan versi image atau environment harus melalui Pull Request di repositori `k8s-gitops-infra`.
3. Gunakan ArgoCD dengan mode `selfHeal: true` dan `prune: true`.
4. Rancang penanganan Secret sensitif agar password database tidak pernah di-commit dalam bentuk plaintext ke Git (menggunakan HashiCorp Vault / External Secrets Operator atau Bitnami Sealed Secrets).

### Skenario 2: Emergency Production Incident Runbook (OOM Spike)
Pada pukul 23:00 saat kampanye payday, service Catalog mengalami `CrashLoopBackOff` masif di 20 replika akibat `OOMKilled` (Exit Code 137). Traffic antrean checkout mulai menumpuk dan Ingress melempar error 504 Gateway Timeout.
Tuliskan urutan runbook langkah-langkah darurat (step-by-step triage, mitigasi kilat, verifikasi pemulihan, dan post-mortem permanent fix via GitOps) yang harus dijalankan oleh Incident Commander!

### Skenario 3: Helm Chart Reusability vs Kustomize Overlays Migration
Perusahaan Anda memiliki 60 microservices internal dengan struktur YAML yang mirip. Tim terbagi dua: Tim A menginginkan Helm Chart tunggal (*Generic Enterprise Chart*) yang dibagikan ke seluruh tim, sedangkan Tim B menginginkan Kustomize Base/Overlays.
Bandingkan trade-off mendalam dari kedua pendekatan tersebut dalam konteks maintainability, kemudahan onboarding developer baru, dan skalabilitas jangka panjang!

---

## Bagian 4: Chapter Challenge — GitOps Production Pipeline with Automated Rollback

### Deskripsi Tantangan
Anda diminta membangun sistem deployment GitOps lengkap untuk microservice Payment:
1. **Packaging**:
   - Buat manifest Kustomize dengan direktori `base/` (Deployment 2 replika, Service port 8080) dan `overlays/production/` (menimpa replika menjadi 5, menginjeksi ConfigMap via `configMapGenerator`).
2. **ArgoCD Manifest**:
   - Tulis manifest CRD `Application` bernama `payment-prod` dengan destinasi namespace `production`.
   - Konfigurasi `syncPolicy.automated.prune: true` dan `syncPolicy.automated.selfHeal: true`.
3. **Simulasi Insiden & Troubleshooting**:
   - Tulis skenario simulasi di mana terjadi *unauthorized configuration drift* di cluster, dan tunjukkan log rekonsiliasi ArgoCD yang memulihkan state dalam waktu kurang dari 30 detik.
   - Buat skrip verifikasi otomatis yang mendeteksi Service Zero Endpoints dan memberikan peringatan diagnostik presisi.

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Perbedaan fundamental paradigma Templating (Helm) vs Patching (Kustomize).
- [ ] Arsitektur Tiller-less Helm v3 dan penyimpanan state rilis di Secret.
- [ ] Cara kerja `configMapGenerator` Kustomize dalam memicu rolling restart otomatis.
- [ ] Empat pilar OpenGitOps dan arsitektur rekonsiliasi ArgoCD.
- [ ] Peran `syncPolicy.automated.selfHeal` dalam mengeliminasi configuration drift.
- [ ] Penggunaan Sync Waves untuk urutan deployment berfase.
- [ ] Analisis matematis Exit Code 137 (`SIGKILL` OOM-Killer).
- [ ] Dampak latensi performa `ndots:5` pada CoreDNS.

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh sintaks fungsi parser Go template di repositori Masterminds/sprig.
- [ ] Nomor commit hash biner internal dari rilis ArgoCD.

### Saya Harus Bisa Melakukan:
- [ ] Menulis Helm Chart fungsional dengan `values.yaml` dan helper templates.
- [ ] Membangun struktur Kustomize Base dan Overlays untuk multi-environment.
- [ ] Menulis manifest CRD `Application` ArgoCD dengan parameter self-healing.
- [ ] Menjalankan investigasi `kubectl logs --previous` pada container CrashLoopBackOff.
- [ ] Memecahkan masalah Service Zero Endpoints yang diakibatkan oleh label selector mismatch.

---
[⬅️ Module 02: GitOps & Troubleshooting](./Module-02-GitOps-ArgoCD-dan-Production-Troubleshooting.md) | [📋 Silabus Induk](../README.md) | [CAPSTONE PROJECT KUBERNETES ➡️](../CAPSTONE-PROJECT-Enterprise-MultiTenant-Microservices-K8s.md)
---
