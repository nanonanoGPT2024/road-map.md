# BAB 04 — Quiz & Chapter Challenge: Konfigurasi, Secrets, & Decoupled Architecture

---
[⬅️ Module 02: Secrets & External Secrets Operator](./Module-02-Secrets-External-Secrets-Operator-dan-Encryption.md) | [📋 Silabus Induk](../README.md) | [BAB 05 Module 01: Service Types & CoreDNS ➡️](../BAB-05-Networking-Service-Discovery-dan-Ingress/Module-01-Service-Types-kube-proxy-IPVS-dan-CoreDNS.md)
---

Dokumen ini menguji pemahaman Anda mengenai decoupling konfigurasi aplikasi (ConfigMaps, Downward API, Hot-Reload, Symlinks) serta arsitektur pengelolaan kredensial sensitif di Kubernetes (Secrets, Encryption at Rest, External Secrets Operator).

---

## Bagian 1: Basic Quiz (5 Pertanyaan)

### Soal 1
Mengapa menyimpan password database di dalam Kubernetes Secret dengan format Base64 TIDAK DAPAT dianggap sebagai sistem yang aman terenkripsi?
- A. Karena Base64 hanya bisa dibaca oleh komputer Windows.
- B. Karena Base64 hanyalah algoritma encoding ASCII dua arah tanpa kunci kriptografi, sehingga siapa pun yang bisa membaca Secret dapat men-decode nilainya secara instan dengan perintah `base64 -d`.
- C. Karena format Base64 membatasi panjang password maksimal 8 karakter.
- D. Karena Base64 otomatis menghapus data setiap 24 jam.

### Soal 2
Apa yang terjadi jika Anda memperbarui data di dalam ConfigMap yang di-mount sebagai **Environment Variables** (`envFrom`) pada sebuah Pod yang sedang berjalan?
- A. Nilai environment variable di dalam kontainer langsung berubah secara otomatis dalam 1 detik.
- B. Nilai environment variable di dalam kontainer **TIDAK AKAN BERUBAH** sama sekali karena variabel lingkungan di-snapshot hanya saat proses pertama kali dibuat (membutuhkan restart Pod untuk membaca nilai baru).
- C. Kontainer akan otomatis me-reboot seluruh node fisik.
- D. Pod akan masuk status CrashLoopBackOff.

### Soal 3
Fitur Kubernetes manakah yang memungkinkan kontainer aplikasi membaca nama Pod-nya sendiri (`metadata.name`), alamat IP Pod (`status.podIP`), atau nama node tempat ia berjalan (`spec.nodeName`) tanpa perlu memanggil Kubernetes API secara langsung?
- A. Downward API
- B. Ingress API
- C. CNI Gateway
- D. StorageClass API

### Soal 4
Tipe Kubernetes Secret standar manakah yang wajib memiliki key `tls.crt` dan `tls.key` untuk keperluan terminasi SSL/TLS pada Ingress Controller?
- A. `Opaque`
- B. `kubernetes.io/tls`
- C. `kubernetes.io/dockerconfigjson`
- D. `kubernetes.io/service-account-token`

### Soal 5
Apa fungsi dari flag `immutable: true` pada objek ConfigMap atau Secret di Kubernetes?
- A. Mencegah objek tersebut diubah setelah dibuat, menghentikan watch polling Kubelet, dan menghemat beban CPU/memori apiserver secara signifikan pada kluster besar.
- B. Mengunci password agar tidak bisa di-reset selamanya.
- C. Mencegah penghapusan namespace.
- D. Mengubah format file menjadi file PDF.

---

## Bagian 2: Intermediate Quiz (5 Pertanyaan)

### Soal 6
Bagaimana cara kerja Kubelet dalam memperbarui file konfigurasi di dalam kontainer saat ConfigMap di-mount sebagai direktori volume tanpa menggunakan `subPath`?
- A. Kubelet mematikan kontainer dan menyalakannya kembali.
- B. Kubelet menulis data baru ke direktori timestamp baru, lalu memutar pointer symbolic link `..data` secara atomik menggunakan syscall `rename()`, sehingga aplikasi membaca konten baru tanpa risiko file terpotong.
- C. Kubelet mengirim email ke admin kluster.
- D. Kubelet memprogram ulang tabel iptables host.

### Soal 7
Mengapa penggunaan opsi `subPath` pada `volumeMounts` ConfigMap menyebabkan fitur pembaruan otomatis (live reload) Kubelet berhenti berfungsi?
- A. Karena subPath dilarang oleh lisensi Linux.
- B. Karena subPath menggunakan mekanisme Linux *bind mount* langsung ke inode file tunggal, yang mem-bypass seluruh hierarki symlink rotasi `..data` Kubelet.
- C. Karena subPath mengubah file menjadi read-only.
- D. Karena subPath hanya bekerja di macOS.

### Soal 8
Bagaimana cara kerja **External Secrets Operator (ESO)** dalam memecahkan masalah keamanan GitOps (mencegah file rahasia tersimpan di repositori Git)?
- A. ESO menghapus akun GitHub developer yang meng-commit password.
- B. Developer hanya men-commit deklarasi metadata `ExternalSecret` ke Git, lalu controller ESO di kluster yang mengambil password aktual dari Cloud Vault (AWS Secrets Manager / HashiCorp Vault) dan otomatis membuat objek Secret asli di kluster.
- C. ESO mengenkripsi seluruh internet.
- D. ESO menggantikan peran etcd.

### Soal 9
Jika database `etcd` di Control Plane tidak dikonfigurasi dengan `EncryptionConfiguration` (Encryption at Rest), dalam format apakah data password di dalam Kubernetes Secret disimpan di hard disk host master?
- A. Plaintext biner yang dapat dibaca langsung oleh siapa pun yang mengakses file database etcd atau file snapshot backup.
- B. Terenkripsi AES-256 otomatis oleh kernel Linux.
- C. Terenkripsi SHA-512.
- D. Disimpan di RAM BIOS.

### Soal 10
Mengapa kita sangat disarankan menyetel `defaultMode: 0400` (atau desimal 256) saat me-mount Secret sebagai volume file ke dalam Pod?
- A. Agar file berukuran lebih kecil.
- B. Agar file rahasia tersebut memiliki izin akses ketat: hanya bisa dibaca (Read-Only) oleh pemilik UID proses aplikasi dan tidak bisa diintip atau dimodifikasi oleh user proses lain di dalam kontainer.
- C. Agar file bisa dieksekusi sebagai script biner.
- D. Agar file tidak terdeteksi oleh antivirus.

---

## Bagian 3: Scenario-Based Questions (3 Skenario)

### Skenario 1: Insiden Kebocoran Kredensial Database di Git Publik
Sebuah tim pengembang mengadopsi ArgoCD untuk otomatisasi deployment. Karena terbiasa di lingkungan lokal, seorang developer membuat file `secret.yaml` berisi password database PostgreSQL (di-encode base64) dan men-commit-nya ke repositori GitHub publik perusahaan.
Dalam waktu 15 menit, bot peretas berhasil mengambil password tersebut dan mengenkripsi database perusahaan untuk meminta tebusan (ransomware).
- **Pertanyaan**: Jelaskan mengapa insiden ini terjadi, dan rancang arsitektur **External Secrets Operator (ESO)** bersama AWS Secrets Manager / Vault agar tim developer tidak akan pernah lagi menaruh satu karakter pun password rahasia di repositori Git!

### Skenario 2: Fitur Flag Tidak Berubah Padahal ConfigMap Sudah Diedit
Seorang product manager meminta on-call engineer mengaktifkan feature flag `ENABLE_NEW_PAYMENT=true` di produksi.
Engineer menjalankan `kubectl edit configmap app-config` dan mengubah nilai dari `false` menjadi `true`.
Namun setelah 30 menit, pengguna masih tetap melihat tampilan lama dan komplain mulai berdatangan. Setelah diperiksa, PodSpec mengonsumsi ConfigMap via blok `envFrom: configMapRef`.
- **Pertanyaan**: Jelaskan mengapa aplikasi tidak mendeteksi perubahan tersebut, dan berikan 2 solusi konkret (solusi darurat cepat dan solusi arsitektur jangka panjang menggunakan volume mount atau config hash annotation trick)!

### Skenario 3: Audit Kepatuhan Perbankan Menemukan Backup etcd Plaintext
Auditor keamanan ISO 27001 menguji integritas disaster recovery kluster Kubernetes sebuah fintech. Auditor berhasil mengunduh file backup `etcd-snapshot.db` dari bucket storage dan menjalankan perintah `strings etcd-snapshot.db | grep -i password`.
Seluruh password nasabah dan API key pembayaran ditemukan dalam bentuk teks polos terbuka.
- **Pertanyaan**: Jelaskan konfigurasi `EncryptionConfiguration` apa yang harus dipasang pada `kube-apiserver`, provider enkripsi apa yang direkomendasikan, dan langkah migrasi apa yang wajib dijalankan agar seluruh data lama di etcd terenkripsi ulang!

---

## Bagian 4: Chapter Challenge

### Tantangan Praktis: Enterprise Decoupled Config & Secret Pipeline
1. **Skenario**:
   Anda diminta merancang arsitektur konfigurasi dan secret untuk payment microservice:
   - Konfigurasi non-sensitif (`app.properties`, port, log level) disimpan di **ConfigMap** dan di-mount sebagai volume direktori dengan hot-reload aktif.
   - Metadata Pod (IP, Nama Pod, Alokasi CPU Limit) disuntikkan via **Downward API**.
   - Password database dan secret token dimuat via **External Secrets Operator** yang mengambil data dari AWS Secrets Manager.
   - Seluruh volume secret wajib memiliki izin ketat `defaultMode: 0400`.
2. **Deliverables**:
   - File manifest `configmap-app.yaml`.
   - File manifest `externalsecret-vault.yaml`.
   - File manifest Deployment `payment-deployment.yaml` yang mengintegrasikan ConfigMap volume, Downward API env vars, dan Secret volume permission `0400`.

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Prinsip *Decoupled Configuration* sesuai Twelve-Factor App.
- [ ] Perbedaan esensial pembaruan ConfigMap via Environment Variables (statis) vs Volume Mounts (dinamis via symlink).
- [ ] Cara kerja rotasi symlink atomik Kubelet (`..data`).
- [ ] Mengapa Base64 bukan enkripsi dan risiko plaintext etcd.
- [ ] Arsitektur External Secrets Operator (SecretStore dan ExternalSecret).
- [ ] Cara kerja Downward API untuk ekstraksi metadata Pod.
- [ ] Trik Checksum Hash Annotation untuk auto-trigger rollout update.

### Saya Tidak Perlu Menghafal:
- Rincian tabel ASCII Base64 padding algorithm.
- Format ASN.1 biner pada sertifikat x509 TLS.

### Saya Harus Bisa Melakukan:
- [ ] Membuat dan mengupdate ConfigMap serta Secret via CLI dan YAML.
- [ ] Mengonfigurasi Downward API pada manifest PodSpec.
- [ ] Mengamankan izin file secret dengan `defaultMode: 0400`.
- [ ] Menulis manifest ExternalSecret untuk integrasi Cloud Vault.
- [ ] Menerapkan `checksum/config` hash annotation pada template Deployment.

---
[⬅️ Module 02: Secrets & External Secrets Operator](./Module-02-Secrets-External-Secrets-Operator-dan-Encryption.md) | [📋 Silabus Induk](../README.md) | [BAB 05 Module 01: Service Types & CoreDNS ➡️](../BAB-05-Networking-Service-Discovery-dan-Ingress/Module-01-Service-Types-kube-proxy-IPVS-dan-CoreDNS.md)
---
