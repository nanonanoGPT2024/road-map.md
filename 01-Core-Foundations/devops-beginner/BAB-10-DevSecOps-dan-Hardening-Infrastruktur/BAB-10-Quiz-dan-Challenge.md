# BAB 10: Quiz, Challenge, & Knowledge Check
**DevSecOps & Hardening Infrastruktur Pemula**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Paradigma *Shift-Left Security*:** Jelaskan apa yang dimaksud dengan *Shift-Left Security* dalam siklus hidup CI/CD modern. Mengapa mendeteksi kerentanan (vulnerability) pada fase penulisan kode atau commit jauh lebih efisien secara biaya dan operasional dibandingkan mendeteksinya pada fase *runtime* produksi?
2. **Prinsip *Least Privilege* (PoLP) & *Blast Radius*:** Definisikan konsep *Principle of Least Privilege* dan hubungannya dengan mitigasi *blast radius* pada infrastruktur Linux dan Cloud. Berikan contoh konkret pelanggaran PoLP yang umum dilakukan oleh pemula saat mengonfigurasi user di sistem Linux.
3. **Taksonomi Pemindaian Keamanan (SAST vs. DAST vs. SCA):** Uraikan perbedaan mendasar antara *Static Application Security Testing* (SAST), *Dynamic Application Security Testing* (DAST), dan *Software Composition Analysis* (SCA). Di tahap pipeline mana masing-masing metode tersebut paling optimal diintegrasikan?
4. **Fundamen OS Hardening:** Mengapa mematikan layanan/daemon yang tidak digunakan, menutup port jaringan yang tidak perlu, dan menonaktifkan autentikasi berbasis *password* pada SSH merupakan langkah wajib (*baseline*) dalam pengerasan server, bukan sekadar opsi tambahan?
5. **Anti-Pattern Manajemen Rahasia (*Secrets Management*):** Mengapa menyimpan kredensial atau *private key* dalam bentuk *plain-text* di dalam *environment variables* container atau repositori Git dianggap sebagai celah keamanan kritis? Bagaimana mekanisme alternatif yang aman untuk menginjeksi rahasia ke aplikasi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mekanisme Isolasi Kernel & *Container Breakout*:** Secara internal, Docker container berbagi kernel dengan host OS. Jelaskan bagaimana eksekusi proses container sebagai user `root` (UID 0) tanpa *User Namespaces* (`userns-remap`) dapat memicu risiko eskalasi hak akses (*privilege escalation*) ke host OS. Apa fungsi instruksi `USER` di Dockerfile atau konfigurasi `securityContext.runAsNonRoot`?
2. **Remediasi Kebocoran Kredensial pada Git:** Seorang teknisi tidak sengaja melakukan commit file `.env` yang berisi token produksi, lalu melakukan commit perbaikan berupa penghapusan file tersebut. Mengapa token tersebut tetap terekspos secara kritis? Uraikan langkah teknis tuntas untuk membersihkan riwayat Git dan tindakan mitigasi wajib apa yang harus segera dilakukan terhadap kredensial tersebut.
3. **Analisis Log Hardening Linux (`auditd` / AVC Denial):** Aplikasi backend yang berjalan di server Linux (CentOS/RHEL) gagal melakukan *binding* ke port non-standar (misalnya port 8088), padahal firewall sudah dibuka dan port tidak digunakan oleh proses lain. Jelaskan bagaimana Anda memverifikasi apakah Security-Enhanced Linux (SELinux) atau AppArmor yang memblokir akses tersebut menggunakan file log audit sistem.
4. **Mitigasi *Supply Chain Attack* via Docker Digests:** Mengapa instruksi `FROM node:18-alpine` di Dockerfile masih memiliki celah keamanan rantai pasok (*supply chain risk*) meskipun versi mayornya telah ditentukan? Bagaimana penggunaan *immutable cryptographic digest* (`image@sha256:...`) menyelesaikan masalah integritas ini?
5. **Manajemen *False Positive* pada Pipeline CI/CD:** Ketika integrasi pemindai keamanan otomatis (misal: Trivy atau Grype) disetel dengan aturan `fail-on: HIGH,CRITICAL`, pipeline sering kali terblokir oleh kerentanan yang belum memiliki patch resmi vendor (*unfixed/vendor-ignored*). Bagaimana merancang strategi *triage* dan *exception handling* yang aman tanpa mengorbankan postur keamanan sistem?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Kompromi Container Socket & Eskalasi Host
Sebuah tim internal membuat container utilitas untuk memantau performa sistem dengan me-mount Docker socket host (`-v /var/run/docker.sock:/var/run/docker.sock`). Dua minggu kemudian, server mendadak mengalami lonjakan penggunaan CPU hingga 100% akibat proses miner tak dikenal yang berjalan langsung di level host Linux, bukan di dalam container.
* **Pertanyaan Diagnostik:**
  1. Bagaimana penyerang yang berhasil mengeksploitasi celah aplikasi web di dalam container utilitas tersebut dapat melompat keluar dan menguasai host OS menggunakan Docker socket?
  2. Perubahan arsitektur apa yang wajib diimplementasikan untuk fungsi monitoring tanpa mengekspos Docker socket host?

### Skenario B: Kebocoran Ephemeral Token via CI Runner Log
Sebuah pipeline CI/CD otomatis mengonfigurasi infrastruktur menggunakan Terraform. Pada suatu hari, seorang penyerang berhasil mencuri session token AWS berdurasi 1 jam dari log publik build runner. Penyerang langsung membuat lusinan instance GPU berbiaya tinggi sebelum token kedaluwarsa.
* **Pertanyaan Diagnostik:**
  1. Analisis bagaimana proses *command echoing* (seperti `set -x` pada bash) atau output verbose alat automasi dapat membocorkan kredensial ke stdout runner.
  2. Mekanisme keamanan apa (seperti OpenID Connect / OIDC, secret masking, dan restrict IAM permissions) yang seharusnya diterapkan agar kebocoran kredensial statis tidak terjadi lagi?

### Skenario C: Bottleneck Keamanan vs. Kecepatan Deployment (Developer Friction)
Manajemen keamanan mewajibkan pemindaian DAST mendalam dan full OS hardening compliance check pada setiap Pull Request (PR) ke branch `main`. Akibatnya, durasi pipeline CI meningkat drastis dari 4 menit menjadi 55 menit per commit. Developer mulai mengeluh, produktivitas tim menurun, dan beberapa tim mulai mencoba mencari jalan pintas (*bypass pipeline*).
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda merestrukturisasi tahapan pengujian keamanan di pipeline agar tidak menghambat *developer feedback loop* yang cepat, namun tetap menjaga kontrol rilis produksi?
  2. Pemindaian mana yang harus dijalankan di level pre-commit/PR, dan pemindaian mana yang dialihkan ke level *nightly build* atau *staging gate*?

---

## 4. Chapter Challenge

**Tantangan Praktis: Hardening Container Baseline & Implementasi CI Security Gate**

### Deskripsi Masalah:
Tim aplikasi Anda memiliki aplikasi Node.js sederhana yang saat ini dideploy menggunakan container dengan status tidak aman: berjalan sebagai `root`, base image yang membengkak (`node:latest`), paket OS yang rentan, serta tidak ada pemeriksaan otomatis terhadap rahasia atau kerentanan dalam pipeline Git.

### Kebutuhan & Spesifikasi:
1. **Dockerfile Hardening:**
   - Gunakan pendekatan *Multi-Stage Build* untuk meminimalkan ukuran image.
   - Gunakan base image minimal (misal: Alpine Linux atau Distroless).
   - Terapkan konfigurasi agar container berjalan dengan user non-root khusus (misal: `UID/GID 10001`).
   - Buat sistem berkas utama berstatus *read-only* jika memungkinkan, atau definisikan izin file/direktori secara ketat (`chown`/`chmod`).
2. **Automated Secret Linting:**
   - Siapkan konfigurasi alat pendeteksi rahasia (seperti `gitleaks` atau `trufflehog`) yang dapat dijalankan secara lokal atau di pipeline.
3. **CI Pipeline Vulnerability Gate (GitHub Actions / GitLab CI):**
   - Integrasikan pemindai keamanan container (misal: Trivy).
   - Konfigurasikan ambang batas (*threshold*): Gagalkan (*exit code 1*) pipeline jika ditemukan CVE dengan severity level **CRITICAL**.
   - Berikan pengecualian (*allowlist/ignore*) yang terdokumentasi untuk kerentanan yang belum tersedia perbaikannya (*unfixed*).

### Batasan (Constraints):
- Dilarang keras menggunakan flag `--privileged` saat menjalankan container hasil build.
- Dilarang menaruh *dummy credentials* (seperti API key palsu) di dalam repositori tanpa konfigurasi pengabaian (.gitleaksignore).
- Waktu eksekusi security scanning di pipeline tidak boleh melebihi 3 menit.

### Output yang Diharapkan:
1. File `Dockerfile` yang telah memenuhi seluruh standar hardening non-root.
2. File definisi pipeline (`.github/workflows/security.yml` atau `.gitlab-ci.yml`) yang memuat step pendeteksian rahasia dan scanning image container.
3. Ringkasan output log pemindaian yang menunjukkan image bersih dari CVE Critical yang dapat diperbaiki (*fixed*).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Prinsip dasar *Defense-in-Depth* dan *Shift-Left Security*.
- [ ] Perbedaan antara kerentanan dependensi aplikasi (SCA), kode sumber (SAST), dan konfigurasi runtime/OS.
- [ ] Bahaya inheren dari menjalankan proses container sebagai user `root`.
- [ ] Dampak keamanan dari mengekspos UNIX socket sistem (seperti Docker socket) ke dalam aplikasi.
- [ ] Konsep *Least Privilege* pada sistem operasi (Linux file permissions, sudoers) dan Cloud IAM.

### Saya tidak perlu menghafal:
- [ ] Setiap nomor registri CVE spesifik dan detail payload eksploitasinya.
- [ ] Seluruh sintaks reguler ekspresi untuk mendeteksi berbagai jenis format secret key penyedia pihak ketiga.
- [ ] Seluruh daftar aturan benchmark Center for Internet Security (CIS) di luar kepala.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi Dockerfile aman dengan user non-root dan base image minimal.
- [ ] Menggunakan CLI scanner keamanan (seperti `trivy image` atau `gitleaks detect`) secara lokal untuk audit mandiri.
- [ ] Melakukan investigasi dasar terhadap akses yang diblokir oleh sistem keamanan OS (SELinux/AppArmor/UFW).
- [ ] Mengonfigurasi pipeline CI/CD agar otomatis menolak (*fail-fast*) build yang mengandung secret bocor atau kerentanan kritis.
- [ ] Melakukan rotasi dan pencabutan (*revocation*) darurat saat terjadi insiden kebocoran kredensial di repositori.