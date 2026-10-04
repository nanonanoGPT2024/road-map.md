## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `CF-DEV-10-01`
* **Nama Modul**: DevSecOps & Hardening Infrastruktur Pemula
* **Kategori**: `01-Core-Foundations`
* **Jalur Kurikulum**: `devops-beginner`
* **Level Keterampilan**: Beginner to Lower-Intermediate
* **Prasyarat**:
  * Penguasaan navigasi CLI Linux dasar (Bash scripting, permission, file editing).
  * Pemahaman model Client-Server dan dasar jaringan komputer (TCP/IP, Ports, Firewall).
  * Pemahaman dasar Git dan Continuous Integration (CI).
* **Estimasi Waktu Belajar**: 180 Menit (Teori: 60 Menit, Praktik Hands-On: 120 Menit)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Mengidentifikasi** vektor serangan dasar pada level host Linux dan pipeline CI/CD (C4 - Analysis).
2. **Menerapkan Prinsip *Shift-Left Security*** dalam alur rilis perangkat lunak modern untuk mendeteksi kerentanan sedini mungkin (C3 - Application).
3. **Mengonfigurasi dan Memperketat (Hardening)** sistem operasi Linux berbasis Debian/Ubuntu menggunakan baseline keamanan standar industri (SSH, UFW, non-root user privilege) (C3 - Application).
4. **Mengimplementasikan Pemindaian Otomatis** terhadap rahasia (*secret leak*) dan kerentanan dependensi (*vulnerability scanning*) menggunakan tools open-source seperti Gitleaks dan Trivy (C3 - Application).
5. **Mengevaluasi Tingkat Postur Kepatuhan Keamanan** host menggunakan automated auditing tool (*Lynis*) dan menyusun rencana remediasi terstruktur (C5 - Evaluation).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
                                [DevSecOps Foundations]
                                           |
         +---------------------------------+---------------------------------+
         |                                 |                                 |
[Filosofi Shift-Left]            [Host & Network Hardening]          [Pipeline Security Gates]
         |                                 |                                 |
         +--> Secure by Default            +--> Principle of Least Privilege +--> Secret Detection (Gitleaks)
         +--> Shared Responsibility        +--> SSH Hardening (Keys, PAM)    +--> Vulnerability Scan (Trivy)
         +--> Fast Feedback Loop           +--> Firewall (UFW/iptables)      +--> Static Analysis (SAST)
                                           +--> Lynis Audit & Benchmarking
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Secara historis, keamanan (*security*) diperlakukan sebagai gerbang isolasi (*gatekeeper*) di akhir siklus rilis perangkat lunak (Waterfall / traditional Agile). Tim Security melakukan uji penetrasi (*pentest*) beberapa hari sebelum aplikasi masuk ke *production*. Pola ini menghasilkan friksi tinggi:

1. **Biaya Remediasi Eksponensial**: Memperbaiki celah keamanan arsitektural atau dependensi rentan di fase *production* bisa memakan biaya hingga 30–100 kali lipat lebih mahal dibanding memperbaikinya saat fase penulisan kode atau pengujian lokal.
2. **Keterlambatan Rilis (*Bottleneck*)**: Tim pengembang terhenti karena temuan keamanan yang menumpuk di hilir, menyebabkan rilis tertunda dan kompromi kualitas.
3. **Ekspansi Attack Surface Modern**: Pada era infrastruktur berbasis cloud, kontainer, dan IaC (*Infrastructure as Code*), kesalahan konfigurasi satu baris (`0.0.0.0/0` pada Security Group atau hardcoded credential) langsung membuka akses global kepada penyerang otomatis (*bot scanner* internet).

DevSecOps mengubah paradigma ini menjadi **Shared Responsibility** (tanggung jawab bersama) di mana instrumen keamanan diintegrasikan secara transparan ke dalam setiap tahapan pipeline otomatis. Sementara itu, *Host Hardening* memastikan bahwa jika batas terluar bobol, penyerang menemui dinding pertahanan bertingkat (*Defense in Depth*) yang membatasi eskalasi hak akses (*privilege escalation*) dan pergerakan lateral (*lateral movement*).

---

## SEKSI 05 — APA ITU (WHAT)

### 1. DevSecOps
DevSecOps adalah integrasi berkelanjutan dari praktik, otomatisasi, dan budaya keamanan ke dalam seluruh siklus hidup DevOps (Plan, Code, Build, Test, Release, Deploy, Operate, Monitor). Inti DevSecOps bukan menambahkan *tooling* sebanyak mungkin, melainkan memberikan visibilitas instan kepada pengembang mengenai postur keamanan artefak yang mereka buat.

### 2. Shift-Left Security
Konsep memindahkan pengujian keamanan dari sisi kanan alur (operasi/produksi) sejauh mungkin ke sisi kiri alur (komit Git/lingkungan pengembang lokal). Deteksi bug keamanan terjadi seketika saat kode diketik (*pre-commit*) atau saat *pull request* diproses oleh CI.

### 3. Attack Surface Reduction (Reduksi Permukaan Serangan)
Praktik meminimalkan jumlah titik masuk (*entry points*) yang dapat dieksploitasi oleh penyerang. Ini mencakup penonaktifan port yang tidak terpakai, penghapusan perangkat lunak residual, penutupan protokol jadul (seperti Telnet/FTP), serta isolasi jaringan.

### 4. Principle of Least Privilege (PoLP)
Prinsip keamanan informasi di mana setiap entitas (pengguna, proses sistem, service account) hanya diberikan hak akses minimum absolut yang diperlukan untuk menjalankan fungsinya, dan tidak lebih.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

Implementasi pengamanan infrastruktur pemula dibagi ke dalam 3 lapisan bertahap:

```text
[Lapis 1: Secure Development & Secrets Management]
    ↓ (Mencegah kredensial bocor ke VCS publik/privat)
[Lapis 2: Host Operating System Hardening]
    ↓ (Membatasi akses SSH, isolasi user, penutupan port via firewall)
[Lapis 3: Continuous Auditing & Automated Scanning]
    ↓ (Verifikasi konfigurasi dan dependensi secara berulang)
```

### Mekanisme Lapis 1: Secret Scanning
Pendeteksi rahasia (seperti Gitleaks) bekerja dengan mencocokkan pola string terhadap aturan Regex terdefinisi (misal: format API Key AWS, Private Key RSA, token Slack) serta algoritma Shannon Entropy untuk mendeteksi string acak dengan tingkat entropi tinggi sebelum kode di-*push* ke repositori jarak jauh.

### Mekanisme Lapis 2: Host Hardening
1. **Pemisahan Hak Akses**: Menonaktifkan login langsung akun `root`. Menggantinya dengan pengguna reguler yang terikat grup `sudo` dengan pencatatan audit log sistem (`/var/log/auth.log`).
2. **Kriptografi SSH**: Menghentikan autentikasi berbasis kata sandi (`PasswordAuthentication no`) dan beralih sepenuhnya ke kunci kriptografi asimetris (minimal RSA 4096-bit atau Ed25519).
3. **Filter Jaringan Stateful (UFW)**: Firewall memblokir seluruh paket data masuk (*Default Deny Incoming*) dan mengizinkan hanya port esensial yang didefinisikan secara eksplisit (misal: TCP 22 untuk SSH, TCP 80/443 untuk Web).

### Mekanisme Lapis 3: Scanning & Auditing
1. **CIS Benchmarks**: Mengikuti panduan konfigurasi konsensus global dari Center for Internet Security (CIS).
2. **Lynis**: Tool audit sistem yang memindai parameter kernel (`sysctl`), izin berkas sensitif, paket kedaluwarsa, dan memberikan nilai indeks pengerasan (*Hardening Index*).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### DevSecOps Automated CI Pipeline Flow

```text
+-------------------+      Git Push      +-------------------------------------------+
| Developer Station | -----------------> |              CI/CD Platform               |
|                   |                    | (GitHub Actions / GitLab CI / Jenkins)     |
| [Pre-Commit Hook] |                    +-------------------------------------------+
|  - Gitleaks check |                                          |
+-------------------+                                          v
                                                +-----------------------------+
                                                | Stage 1: Secret Scanning    |
                                                | Tool: Gitleaks              |
                                                | Status: [Pass / Fail Build] |
                                                +-----------------------------+
                                                               |
                                                               v
                                                +-----------------------------+
                                                | Stage 2: SAST & Dependency  |
                                                | Tool: Trivy (Filesystem)    |
                                                | Output: CVE Report          |
                                                +-----------------------------+
                                                               |
                                                               v
                                                +-----------------------------+
                                                | Stage 3: Container Build    |
                                                | Tool: Trivy (Image Scan)    |
                                                | Gate: High/Crit CVE Block   |
                                                +-----------------------------+
                                                               |
                                                               v
                                                +-----------------------------+
                                                | Stage 4: Deploy Target      |
                                                | Hardened Linux Host         |
                                                |  - Non-root user            |
                                                |  - UFW Block Everything     |
                                                |  - SSH Ed25519 Only         |
                                                +-----------------------------+
```

### Defense in Depth Host Layering Model

```text
+-----------------------------------------------------------------------+
| Network Perimeter: Cloud Security Group / Edge Router                 |
|   +-----------------------------------------------------------------+ |
|   | Host Firewall (UFW / iptables): Default Drop Inbound            | |
|   |   +-----------------------------------------------------------+ | |
|   |   | Service Layer: SSH Hardened (Ed25519, No Root, Custom PAM)| | |
|   |   |   +-----------------------------------------------------+ | | |
|   |   |   | System Kernel: sysctl parameters, Least Privilege   | | | |
|   |   |   |   +-----------------------------------------------+ | | | |
|   |   |   |   | Application / Runtime: Non-Root Containerized | | | | |
|   |   |   |   +-----------------------------------------------+ | | | |
|   |   |   +-----------------------------------------------------+ | | |
|   |   +-----------------------------------------------------------+ | |
|   +-----------------------------------------------------------------+ |
+-----------------------------------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah konfigurasi minimal untuk mengamankan daemon SSH pada server Ubuntu baru.

### 1. Modifikasi File Konfigurasi SSH Daemon
Buka konfigurasi daemon SSH:
```bash
sudo nano /etc/ssh/sshd_config.d/99-hardened.conf
```
*Catatan: Menggunakan direktori `sshd_config.d/` adalah praktik terbaik modern daripada mengedit langsung file induk `/etc/ssh/sshd_config`.*

Masukkan konfigurasi pengerasan berikut:
```ini
# Menonaktifkan login root langsung
PermitRootLogin no

# Menonaktifkan autentikasi password (wajib SSH Key)
PasswordAuthentication no
PermitEmptyPasswords no

# Membatasi upaya autentikasi untuk memitigasi brute-force
MaxAuthTries 3

# Membatasi durasi login yang tidak selesai
LoginGraceTime 30

# Menonaktifkan forwarding yang tidak dibutuhkan pemula
X11Forwarding no

# Gunakan hanya algoritma enkripsi modern (hindari SHA1/MD5)
KbdInteractiveAuthentication no
```

### 2. Validasi Konfigurasi & Reload Service
Sebelum me-restart service, verifikasi sintaksis agar tidak terkunci keluar dari sistem (*lockout*):
```bash
# Validasi sintaks berkas konfigurasi
sudo sshd -t

# Jika tidak ada keluaran error, muat ulang service SSH
sudo systemctl reload ssh
```

### 3. Mengaktifkan Firewall Dasar (UFW)
```bash
# 1. Pastikan default policy adalah drop inbound, allow outbound
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 2. Buka port SSH (TCP 22) SEBELUM mengaktifkan firewall!
sudo ufw allow 22/tcp comment 'SSH Access'

# 3. Aktifkan UFW
sudo ufw enable

# 4. Verifikasi status
sudo ufw status verbose
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Skenario nyata: Mengotomatisasi pemindaian keamanan repositori menggunakan GitHub Actions, memblokir penggabungan kode (*merge*) jika terdapat kunci API yang bocor atau pustaka dengan kerentanan level *CRITICAL*.

### File Pipeline: `.github/workflows/security-gate.yml`

```yaml
name: DevSecOps Shift-Left Gatekeeper

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  secret-scan:
    name: Secrets Leak Detection
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0 # Ambil seluruh commit history untuk audit mendalam

      - name: Run Gitleaks Scanner
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        # Gitleaks akan mengembalikan exit-code non-zero jika mendeteksi private key, API token, dll.

  vulnerability-scan:
    name: Dependency & Filesystem CVE Scan
    runs-on: ubuntu-latest
    needs: secret-scan
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Run Trivy FS Scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'CRITICAL,HIGH'
          exit-code: '1' # Sengaja dibuat gagal jika ditemukan kerentanan level HIGH/CRITICAL
          ignore-unfixed: true
```

### Skrip Pengerasan Host Linux Mandiri (`host-hardening.sh`)

Gunakan skrip Bash idempoten ini untuk melakukan pengerasan sistem operasi otomatis:

```bash
#!/usr/bin/env bash
#
# host-hardening.sh
# Skrip otomatisasi hardening host level baseline (Debian/Ubuntu)
#
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
   echo "[ERROR] Skrip ini harus dijalankan sebagai root (gunakan sudo)." 
   exit 1
fi

echo "[1/5] Memperbarui indeks paket dan menginstal utilitas keamanan..."
apt-get update -qq && apt-get upgrade -y -qq
apt-get install -y -qq ufw fail2ban unattended-upgrades lynis

echo "[2/5] Mengaktifkan Automatic Security Updates..."
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "[3/5] Mengonfigurasi UFW (Uncomplicated Firewall)..."
ufw --force reset > /dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'Secure SSH Port'
ufw allow 80/tcp comment 'HTTP Web'
ufw allow 443/tcp comment 'HTTPS Web'
ufw --force enable

echo "[4/5] Mengonfigurasi Kernel Security Parameters (sysctl)..."
cat << 'EOF' > /etc/sysctl.d/99-security-hardening.conf
# Mitigasi SYN Flood Attack
net.ipv4.tcp_syncookies = 1

# Nonaktifkan ICMP Redirect Acceptance (Mencegah MiTM routing attacks)
net.ipv4.conf.all.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0

# Nonaktifkan IP Packet Forwarding jika server bukan router
net.ipv4.ip_forward = 0

# Abaikan respon ping broadcast
net.ipv4.icmp_echo_ignore_broadcasts = 1
EOF

sysctl --system > /dev/null

echo "[5/5] Memperketat Permission File Sensitif..."
chmod 600 /etc/shadow
chmod 600 /etc/gshadow
chmod 644 /etc/passwd
chmod 644 /etc/group

echo "[SUKSES] Hardening dasar berhasil diterapkan pada host!"
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi | Pendekatan Keamanan Rendah (Permisif) | Pendekatan Keamanan Tinggi (Over-Hardened) | Rekomendasi DevSecOps Pemula |
| :--- | :--- | :--- | :--- |
| **Autentikasi SSH** | Password sederhana diizinkan. Akses mudah dari mana saja. | Kunci SSH + Hardware Token (FIDO2) + IP Whitelist ketat. | Kunci SSH (Ed25519) wajib, password dinonaktifkan sepenuhnya. |
| **Pipeline Failure** | Scanning hanya menghasilkan log peringatan (*Warning*). | CI/CD gagal pada temuan *LOW* atau *MEDIUM* severity. | Block pipeline pada temuan *CRITICAL* dan deteksi kebocoran kredensial (*secrets*). |
| **Firewall (UFW)** | Buka semua port incoming untuk kemudahan debug. | Hanya buka port custom non-standar, blokir seluruh outbound kecuali proxy. | *Default deny incoming*, izinkan hanya port operasional (22, 80, 443). |
| **Kecepatan Deployment**| Sangat cepat karena tidak ada tahapan evaluasi security. | Sangat lambat karena pemindaian berat dan proses persetujuan manual. | Jalankan pemindaian otomatis asinkronus dan gunakan *caching engine* pada CI. |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Kunci SSH Modern (Ed25519)**: Hindari penggunaan kunci RSA 1024-bit atau 2048-bit. Ed25519 menawarkan performa lebih cepat dan resistensi kriptografis lebih baik dengan ukuran kunci kompak.
   ```bash
   ssh-keygen -t ed25519 -a 100 -C "admin@infrastructure"
   ```
2. **Jangan Pernah Mengabaikan `.gitignore`**: Buat template global untuk mengabaikan file rahasia seperti `.env`, `*.pem`, `id_rsa`, dan credential cloud secara permanen dari Git.
3. **Automasi Patching Sistem**: Selalu aktifkan paket `unattended-upgrades` pada Linux server agar pembaruan keamanan (*security patches*) terpasang secara terjadwal tanpa intervensi manual.
4. **Isolasi Service dengan Dedicated Users**: Jangan pernah menjalankan layanan aplikasi (misal: Node.js, Python, Nginx) menggunakan akun `root`. Buat system user khusus dengan opsi *system account* tanpa login shell:
   ```bash
   sudo adduser --system --no-create-home --group apprunner
   ```
5. **Jalankan Audit Berkala Menggunakan Lynis**:
   ```bash
   sudo lynis audit system --quick
   ```
   Tinjau skor *Hardening Index* dan implementasikan saran dari laporan yang dihasilkan pada `/var/log/lynis-report.dat`.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Terkunci Keluar dari Server Sendiri (*Lockout Issue*)**: Mengaktifkan firewall (`ufw enable`) atau mematikan `PasswordAuthentication` sebelum mengonfigurasi dan memvalidasi akses SSH Key di jendela terminal terpisah.
   * *Solusi*: Jangan pernah menutup sesi terminal saat ini sebelum berhasil login pada sesi terminal baru.
2. **Menyimpan Token Sementara di Kode Sumber**: Mengabaikan bahaya memasukkan token staging/testing ke dalam repositori dengan asumsi "nanti akan dihapus sebelum merge".
   * *Solusi*: Git mencatat riwayat permanen. Sekali di-*commit*, token dianggap telah terekspos dan harus di-*revoke* (ditarik/diganti) seketika.
3. **Penyalahgunaan Izin Berkas `chmod 777`**: Memberikan izin *read-write-execute* untuk semua entitas guna mengatasi *Permission Denied*.
   * *Solusi*: Identifikasi kepemilikan file (`chown`) dan berikan hak seminimal mungkin (misal: `chmod 755` untuk direktori, `chmod 644` untuk file web).
4. **Mematikan Security Control Demi Kemudahan Cepat**: Mengubah parameter kernel atau mematikan fitur seperti SELinux/AppArmor secara permanen demi mengatasi error instalasi.
   * *Solusi*: Baca audit log untuk memahami konteks izin yang ditolak daripada mematikan subsystem keamanan.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Lab 1: Linux Host Hardening & Firewall Isolation (Beginner)
* **Objektif**: Mengonfigurasi lingkungan Linux virtual/cloud baru agar tahan terhadap brute force dan penutupan port ekspos.
* **Instruksi**:
  1. Buat pengguna baru bernama `devopsadmin` dan tambahkan ke grup `sudo`.
  2. Salin *public key* mesin lokal Anda ke direktori `/home/devopsadmin/.ssh/authorized_keys`.
  3. Konfigurasi file `/etc/ssh/sshd_config.d/security.conf` untuk mematikan autentikasi password dan menonaktifkan root login.
  4. Konfigurasikan UFW agar hanya menerima traffic pada port `22` (SSH) dan port `8080` (App).
* **Verifikasi**: Jalankan `ssh -o PubkeyAuthentication=no devopsadmin@<IP-SERVER>` dan pastikan koneksi ditolak (*Permission denied (publickey)*).

### Lab 2: Implementasi Git Pre-Commit Hook Anti-Leak (Intermediate)
* **Objektif**: Menghentikan kebocoran secret lokal sebelum masuk ke Git commit.
* **Instruksi**:
  1. Unduh dan pasang binary `gitleaks` pada mesin lokal Anda.
  2. Buka repositori Git lokal dan buat berkas skrip hook pada `.git/hooks/pre-commit`:
     ```bash
     #!/usr/bin/env bash
     gitleaks protect --staged --verbose
     ```
  3. Berikan izin eksekusi: `chmod +x .git/hooks/pre-commit`.
  4. Lakukan pengujian dengan membuat file `.env` berisi `AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE123` lalu lakukan `git add .env && git commit -m "test leak"`.
* **Verifikasi**: Git harus membatalkan commit dengan pesan peringatan bahwa *leak* terdeteksi.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan-pertanyaan berikut untuk mengevaluasi pemahaman Anda:

1. **Apa perbedaan mendasar antara pendekatan keamanan tradisional dan DevSecOps?**
   * A. DevSecOps meniadakan penggunaan firewall pada level host.
   * B. DevSecOps mengintegrasikan pengujian keamanan otomatis di setiap tahap siklus pengembangan (Shift-Left), bukan hanya di akhir rilis.
   * C. DevSecOps melarang penggunaan akun non-root di lingkungan pengujian.
   * D. DevSecOps sepenuhnya menggantikan peran tim Security dengan kecerdasan buatan.

2. **Mengapa menonaktifkan autentikasi berbasis kata sandi (`PasswordAuthentication no`) pada SSH sangat dianjurkan?**
   * A. Karena SSH Key memerlukan memori RAM yang jauh lebih besar di server.
   * B. Untuk mencegah serangan *dictionary attack* dan *automated brute-force attacks* yang mengeksploitasi kata sandi lemah.
   * C. Kunci SSH secara otomatis mengenkripsi seluruh filesystem server.
   * D. Karena port 22 tidak dapat membaca karakter teks biasa.

3. **Perintah UFW manakah yang merefleksikan implementasi "Principle of Least Privilege" pada aspek lalu lintas jaringan masuk?**
   * A. `sudo ufw allow in proto tcp from any to any`
   * B. `sudo ufw default allow incoming`
   * C. `sudo ufw default deny incoming`
   * D. `sudo ufw disable`

4. **Jika Anda tidak sengaja mengunggah file berisi secret token ke commit GitHub publik, langkah pertama yang paling tepat dan aman adalah:**
   * A. Menghapus commit tersebut dengan perintah `git reset --hard HEAD~1` dan melakukan force push.
   * B. Mengedit file di GitHub web UI dan menimpa token tersebut dengan string kosong.
   * C. Mengubah visibility repositori dari publik menjadi privat.
   * D. Segera me-*revoke* (menonaktifkan) token tersebut pada penyedia layanan terkait, lalu menganggap token tersebut telah terkompromi.

5. **Apa fungsi utama dari tool open-source Lynis?**
   * A. Mengompilasi kode program C++ menjadi biner yang aman.
   * B. Memindai celah keamanan pada sistem operasi Linux dan memberikan skor audit kepatuhan (*hardening index*).
   * C. Menghubungkan server lokal ke jaringan VPN privat secara otomatis.
   * D. Menggantikan peran kernel Linux dalam mengelola alokasi memori.

### Kunci Jawaban
1. **B** — DevSecOps berfokus pada integrasi keamanan di seluruh siklus hidup melalui pendekatan Shift-Left.
2. **B** — Kunci SSH asimetris mengeliminasi kerentanan tebakan kata sandi akibat serangan brute-force global.
3. **C** — Menolak semua koneksi masuk secara default dan hanya membuka port yang esensial adalah manifestasi Least Privilege.
4. **D** — Sekali token terekspos ke repositori publik, bot internet dapat merekamnya dalam hitungan detik. Langkah remediasi wajib pertama adalah *revoke & rotate* token, bukan sekadar menghapus commit.
5. **B** — Lynis adalah tool audit keamanan sistem Linux yang komprehensif untuk mengevaluasi postur hardening.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi & Standar Industri**:
  * [CIS Benchmarks (Center for Internet Security) for Ubuntu Linux](https://www.cisecurity.org/cis-benchmarks/)
  * [OWASP DevSecOps Guideline](https://owasp.org/www-project-devsecops-guideline/)
  * [NIST Special Publication 800-190: Application Container Security Guide](https://csrc.nist.gov/publications/detail/sp/800-190/final)
* **Tools & Repositori Open Source**:
  * [Gitleaks Documentation & GitHub Repository](https://github.com/gitleaks/gitleaks)
  * [Aqua Security Trivy Vulnerability Scanner](https://aquasecurity.github.io/trivy/)
  * [CISOfy Lynis - Security Auditing Tool for Unix/Linux](https://cisofy.com/lynis/)
* **Buku Referensi**:
  * *DevSecOps: A Leader's Guide to Producing Secure Software Without Compromising Flow* oleh Glenn Wilson.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* **DevSecOps** memindahkan fokus keamanan ke arah hulu (*Shift-Left*), mengotomatisasi pengujian keamanan di dalam alur pipa integrasi, dan mengubah keamanan menjadi tanggung jawab bersama.
* **Host Hardening** bertujuan memperkecil *attack surface* dengan mengeliminasi komponen, port, dan hak akses yang tidak diperlukan.
* Konfigurasi **SSH yang aman** wajib menggunakan kunci asimetris modern (Ed25519), menolak login pengguna `root` secara langsung, serta membatasi upaya login yang gagal.
* Firewall host (**UFW**) harus selalu dikonfigurasi dengan aturan dasar **Default Deny Incoming**; hanya port yang secara eksplisit dibutuhkan yang boleh dibuka.
* Kebocoran kredensial (*secrets leak*) harus dicegah secara lokal menggunakan *pre-commit hooks* dan diverifikasi ulang pada pipeline CI sebelum artefak dideploy.

---

## SEKSI 17 — GLOSARIUM

1. **Attack Surface**: Total kombinasi dari semua titik kerentanan (*entry points*) yang dapat diakses oleh pengguna tidak sah untuk mengekstrak data atau mengeksekusi kode berbahaya.
2. **Brute-Force Attack**: Metode penyerangan dengan mencoba kombinasi password atau kunci secara berulang-ulang hingga menemukan kombinasi yang benar.
3. **CIS Benchmarks**: Standar konfigurasi konsensus industri yang diakui secara global untuk mengamankan sistem operasi dan komponen software.
4. **CVE (Common Vulnerabilities and Exposures)**: Basis data publik mengenai kerentanan keamanan siber yang telah diidentifikasi dan diberikan nomor referensi standar.
5. **Defense in Depth**: Strategi keamanan berlapis di mana kontrol keamanan ganda diterapkan di seluruh infrastruktur untuk mencegah kegagalan titik tunggal (*single point of failure*).
6. **Ed25519**: Skema tanda tangan digital menggunakan kurva eliptik Edwards yang menawarkan keamanan tingkat tinggi dengan kecepatan komputasi yang sangat efisien.
7. **Idempotent**: Karakteristik dari suatu operasi atau skrip di mana jika dieksekusi berkali-kali akan menghasilkan status sistem akhir yang sama tanpa menimbulkan efek samping yang tidak diinginkan.
8. **Least Privilege**: Prinsip membatasi hak akses pengguna atau sistem hanya sebatas apa yang esensial untuk menjalankan pekerjaannya.
9. **SAST (Static Application Security Testing)**: Pengujian keamanan aplikasi statis yang menganalisis kode sumber tanpa menjalankan program untuk mencari indikasi celah keamanan.
10. **Secret Leak**: Insiden ketidaksengajaan di mana kredensial sensitif (API key, password, private key) tersimpan dalam kode sumber dan terekspos ke repositori publik atau semi-publik.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Peringatan Lab Host SSH**: Ingatkan peserta berkali-kali untuk **tidak** menutup jendela terminal SSH aktif saat menguji konfigurasi baru. Selalu buka tab terminal kedua untuk mengetes login sebelum mengakhiri sesi yang sudah ada.
* **Penanganan False Positive**: Dalam latihan pemindaian Trivy atau Gitleaks, jelaskan kepada siswa bahwa tidak semua temuan adalah ancaman nyata (kadang ada *false positive*). Ajarkan cara mengevaluasi konteks kerentanan, bukan sekadar mematikan scanner.
* **Fasilitasi Lingkungan**: Hindari melakukan latihan host hardening langsung pada mesin sistem operasi utama siswa. Sediakan VM terisolasi (VirtualBox, Multipass, atau instance cloud VPS murah) agar kegagalan konfigurasi jaringan tidak melumpuhkan konektivitas komputer lokal mereka.

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal | Penulis | Deskripsi Perubahan |
| :--- | :--- | :--- | :--- |
| `v1.0.0` | 2025-03-30 | DevOps Curriculum Architect | Rilis kurikulum inisial modul DevSecOps & Hardening Infrastruktur Pemula. Standar format 20 seksi terpenuhi. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `CF-DEV-09-01` — Dasar-Dasar CI/CD Automation & Pipeline Integrasi
* **Modul Saat Ini**: `CF-DEV-10-01` — DevSecOps & Hardening Infrastruktur Pemula
* **Modul Berikutnya**: `CF-DEV-11-01` — Dasar Pemantauan Sistem (Monitoring & Observability: Prometheus & Grafana)