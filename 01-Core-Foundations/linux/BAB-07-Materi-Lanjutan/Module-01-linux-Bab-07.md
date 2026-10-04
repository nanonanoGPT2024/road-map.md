## SEKSI 01 — IDENTITAS MODUL

* **Modul ID:** LIN-01-07-01
* **Track:** Linux Engineering & System Administration
* **Kategori:** 01-Core-Foundations
* **Bab:** 07 — Tata Kelola Izin, Autentikasi PAM, dan Pengerasan Keamanan
* **Nama Modul:** Tata Kelola Izin Lanjutan, Arsitektur PAM, dan Hardening Kernel/Sistem
* **Tingkat Kesulitan:** Intermediate ke Advanced
* **Prasyarat:** 
  * Pemahaman struktur direktori Linux (FHS)
  * Manajemen pengguna dan grup lokal (`/etc/passwd`, `/etc/group`, `/etc/shadow`)
  * Navigasi shell Bash dan eksekusi perintah dasar (`chmod`, `chown`, `chgrp`)
  * Konsep dasar proses Linux (PID, UID, GID, EUID)
* **Estimasi Waktu Belajar:** 6 Jam (2.5 Jam Teori Mendalam, 3.5 Jam Praktik Lab Mandiri)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik ditargetkan mampu:

1. **Menganalisis dan Mengonfigurasi Atribut Izin Khusus Linux:** Menjelaskan dan mengimplementasikan bit izin tradisional (rwx), octal representation, serta Special Bits: SUID (*Set User ID*), SGID (*Set Group ID*), dan Sticky Bit untuk tata kelola kolaboratif dan proteksi berkas biner.
2. **Mengelola POSIX Access Control Lists (ACL):** Mengoperasikan utilitas `getfacl` dan `setfacl` untuk membuat kebijakan hak akses multi-entitas yang melampaui batasan model *Owner-Group-Others* (UGO) standar.
3. **Membongkar dan Menyusun Konfigurasi PAM (*Pluggable Authentication Modules*):** Membedah alur tumpukan (*stack*) otentikasi di direktori `/etc/pam.d/`, memahami manajemen tipe modul (`auth`, `account`, `password`, `session`), serta mengontrol evaluasi alur kerja menggunakan *control flags* (`required`, `requisite`, `sufficient`, `optional`).
4. **Menerapkan Modul PAM Spesifik Produksi:** Mengintegrasikan modul keamanan seperti `pam_faillock` (mitigasi serangan *brute force*), `pam_pwquality` (enforcement kompleksitas sandi), dan `pam_wheel` (restriksi su/sudo).
5. **Mengeksekusi Pengerasan (*Hardening*) Kernel dan Sistem Berkas:** Mengonfigurasi parameter *runtime* kernel via `/etc/sysctl.d/` untuk mencegah serangan umum (*spoofing*, *SYN flood*, *pings*, *core dumps*), serta menerapkan atribut berkas tidak dapat diubah (*immutable*) menggunakan `chattr` dan `lsattr`.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            [LINUX SECURITY CORE]
                                      |
         +----------------------------+----------------------------+
         |                                                         |
 [SISTEM BERKAS & IZIN]                                    [SUBSISTEM OTENTIKASI]
         |                                                         |
         +--> Standard UGO (rwx, octal mask)                       +--> PAM (/etc/pam.d/)
         |                                                         |      |
         +--> Special Bits                                         |      +--> Management Groups
         |      +--> SUID (Execution as Owner)                     |      |      (auth, account,
         |      +--> SGID (Group inheritance / Execution)          |      |       password, session)
         |      +--> Sticky Bit (Deletion restriction)             |      |
         |                                                         |      +--> Control Flags
         +--> POSIX ACLs                                           |      |      (required, requisite,
         |      +--> Explicit user/group grants                    |      |       sufficient, optional)
         |      +--> Masking & Default ACLs                        |      |
         |                                                         |      +--> Modules
         +--> File Attributes (Ext4/XFS)                           |             (pam_faillock, pam_pwquality,
                +--> Immutable (+i), Append-only (+a)              |              pam_unix, pam_wheel)
                                                                   |
                                                      [PENGURASAN SISTEM (HARDENING)]
                                                                   |
                                                                   +--> Kernel Parameters (sysctl)
                                                                   +--> Restricted Environment (umask, limits)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sistem operasi Linux dirancang secara inheren sebagai sistem *multi-user* dan *pre-emptive multitasking*. Karakteristik ini membuka celah eskalasi hak istimewa (*privilege escalation*), akses data tidak sah lintas pengguna, dan eksploitasi proses jika tata kelola izin hanya mengandalkan model perizinan UGO (*User-Group-Other*) tradisional.

Dalam arsitektur *enterprise*, skenario perizinan sering kali membutuhkan fleksibilitas tinggi yang aman. Misalnya, beberapa departemen (Keuangan, Audit, dan Teknis) memerlukan tingkat akses yang berbeda-beda terhadap berkas log yang sama tanpa harus menambahkan mereka ke dalam satu grup raksasa yang melanggar prinsip *Least Privilege*. POSIX ACL memecahkan masalah fragmentasi ini.

Selain itu, pertahanan lapis pertama server terhadap intrusi terletak pada autentikasi. Tanpa arsitektur fleksibel seperti PAM (*Pluggable Authentication Modules*), setiap aplikasi (seperti OpenSSH, sudo, vsftpd, login lokal) harus mengimplementasikan logika autentikasi, enkripsi, dan pembatasan serangannya sendiri. PAM memusatkan otentikasi, memungkinkan administrator menerapkan proteksi brute-force, *two-factor authentication* (2FA), dan kebijakan kata sandi secara global tanpa perlu mengompilasi ulang kode sumber aplikasi individual. Mengombinasikan ini dengan pengerasan parameter kernel via `sysctl` mencegah sistem menjadi target empuk eksploitasi berbasis jaringan dan memori.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Model Izin Standar (UGO) dan Bit Khusus (*Special Bits*)
Izin berkas Linux dasar dipetakan ke tiga entitas: **User/Owner (u)**, **Group (g)**, dan **Others (o)** dengan tiga mode operasi: **Read (r=4)**, **Write (w=2)**, dan **Execute (x=1)**.

Untuk kebutuhan transisi hak akses dan kolaborasi, Linux menyediakan tiga *Special Bits*:
* **SUID (Set User ID, oktal 4000):** Diterapkan pada berkas biner tereksekusi. Saat berkas dijalankan, proses berjalan dengan hak akses (EUID - *Effective User ID*) dari pemilik berkas tersebut, bukan pengguna yang mengeksekusinya (contoh klasik: `/usr/bin/passwd` berjalan sebagai root).
* **SGID (Set Group ID, oktal 2000):**
  * Pada berkas biner: Proses berjalan dengan hak akses grup (EGID - *Effective Group ID*) dari berkas tersebut.
  * Pada direktori: Berkas atau sub-direktori baru yang dibuat di dalamnya akan mewarisi *ownership group* dari direktori induk, bukan *primary group* dari pengguna pembuat.
* **Sticky Bit (oktal 1000):** Diterapkan pada direktori bersama (misalnya `/tmp`). Mencegah pengguna menghapus atau mengubah nama berkas milik pengguna lain, meskipun mereka memiliki hak tulis (`w`) di direktori tersebut. Hanya pemilik berkas, pemilik direktori, dan root yang berhak menghapus.

### 2. POSIX Access Control Lists (ACL)
ACL adalah mekanisme perizinan yang memperluas batasan skema UGO tradisional. ACL memungkinkan penetapan hak akses (`rwx`) secara eksplisit kepada pengguna majemuk (*multiple users*) atau grup majemuk (*multiple groups*) pada satu objek *inode*, serta menyertakan *default ACL* yang dapat diwariskan ke objek anak.

### 3. PAM (Pluggable Authentication Modules)
PAM adalah infrastruktur modular tingkat sistem yang memisahkan aplikasi pengguna tingkat tinggi dari mekanisme autentikasi mendasar. Dengan PAM, administrator dapat mengubah mekanisme autentikasi (seperti integrasi LDAP, Active Directory, YubiKey, atau proteksi *failed login*) tanpa memodifikasi kode program aplikasi pemanggil.

### 4. Atribut Berkas dan Pengerasan Kernel
* **Extended Attributes (`chattr`):** Melampaui model izin POSIX standar pada sistem berkas (misal Ext4, XFS). Berkas dengan flag `+i` (*immutable*) tidak dapat dimodifikasi, dihapus, ditautkan (*symlink*/*hardlink*), maupun diganti namanya, bahkan oleh *superuser* (root), sampai atribut tersebut dilepas secara eksplisit.
* **Kernel Tuning (`sysctl`):** Mekanisme manipulasi parameter kernel Linux secara *real-time* via berkas virtual di `/proc/sys/`.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Evaluasi Izin Berkas oleh Kernel
Saat sebuah proses berupaya mengakses berkas, VFS (*Virtual File System*) kernel mengevaluasi hak akses menggunakan *Effective UID/GID* dari proses tersebut dengan urutan ketat:
1. Jika proses dimiliki oleh *Owner* berkas: Kernel memeriksa bit izin *User*. Jika diizinkan, akses diberikan. Jika ditolak, akses langsung dihentikan (**tidak** beralih ke pengecekan grup).
2. Jika proses bukan milik *Owner*, tetapi anggota dari *Group* berkas: Kernel memeriksa bit izin *Group*.
3. Jika terdapat *ACL*: Kernel memeriksa apakah proses cocok dengan salah satu entri *Named User* atau *Named Group* yang diatur di ACL berkas tersebut, kemudian dievaluasi terhadap entri `mask`.
4. Jika tidak cocok dengan *Owner* maupun *Group*: Kernel mengevaluasi bit izin *Others*.

```
Bitmask Izin 12-Bit:
+---+---+---+---+---+---+---+---+---+---+---+---+
| S | S | T | r | w | x | r | w | x | r | w | x |
+---+---+---+---+---+---+---+---+---+---+---+---+
| SUID|SGID|Sticky|   User   |   Group  |  Others  |
| 4000|2000|1000  | 0400/200/100 | 0040/020/010 | 0004/0002/0001 |
```

### 2. Arsitektur dan Alur Evaluasi Tumpukan PAM
Ketika aplikasi seperti OpenSSH menerima upaya login, aplikasi memanggil pustaka PAM (`libpam`). PAM membaca berkas konfigurasi di `/etc/pam.d/<nama_layanan>` (atau `/etc/pam.conf`). 

Setiap baris diatur berdasarkan format:
`<management_group> <control_flag> <module_path> <module_arguments>`

#### Empat Grup Manajemen PAM:
* `auth`: Memvalidasi identitas pengguna (meminta dan memeriksa sandi, token OTP, dsb.) dan mengonfigurasi kredensial grup.
* `account`: Memeriksa validitas akun non-autentikasi (apakah akun kedaluwarsa, pembatasan waktu login, ketersediaan shell).
* `password`: Menangani proses pengubahan kredensial/sandi (mencegah reuse sandi, enforcing kompleksitas).
* `session`: Mengonfigurasi dan menutup lingkungan sesi pengguna (me-mount direktori home, mengatur resource limits via `pam_limits.so`, mencatat audit log).

#### Logika Evaluasi *Control Flags*:

| Control Flag | Jika Modul Berhasil (Success) | Jika Modul Gagal (Failure) | Keterangan Eksekusi Tumpukan |
| :--- | :--- | :--- | :--- |
| **required** | Lanjut ke modul berikutnya. Status akhir sukses tercatat sementara. | Lanjut ke modul berikutnya. Status akhir gagal **pasti** dikembalikan di akhir tumpukan. | Seluruh tumpukan tetap dieksekusi untuk mencegah *timing attack*. |
| **requisite** | Lanjut ke modul berikutnya. | Eksekusi tumpukan **langsung dihentikan saat itu juga**. Status gagal dikembalikan ke aplikasi. | Berguna untuk membatalkan proses otentikasi segera jika syarat kritis gagal. |
| **sufficient** | Jika belum ada kegagalan sebelumnya, tumpukan **langsung berhenti** dan mengembalikan status **sukses**. | Kegagalan diabaikan, eksekusi lanjut ke modul berikutnya dalam tumpukan. | Kerap digunakan untuk alur alternatif (misal: sukses via hardware token). |
| **optional** | Lanjut ke modul berikutnya. Sukses/gagal dicatat, tetapi hanya menentukan hasil jika modul lain tidak deterministik. | Lanjut ke modul berikutnya. | Biasanya digunakan untuk *housekeeping* atau modul pelaporan. |

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Diagram 1: Alur Penilaian Evaluasi Tumpukan PAM (Auth Stack)

```
[Aplikasi Login / SSH]
         |
         v
[Inisiasi PAM Context: pam_start()]
         |
         v
    +--------------------------------------------------------+
    | Membaca /etc/pam.d/<service> (misal: sshd)            |
    +--------------------------------------------------------+
         |
         |---> [ Modul 1: required pam_env.so ]
         |         |--> Evaluasi: Sukses
         |         +--> Status Global: OK -> Lanjut
         |
         |---> [ Modul 2: requisite pam_faillock.so preauth ]
         |         |--> Apakah akun terkunci?
         |         +--[YA]--------> [TERMINASI CEPAT (FAIL)] -> Akses Ditolak
         |         +--[TIDAK]-----> Lanjut
         |
         |---> [ Modul 3: sufficient pam_unix.so try_first_pass ]
         |         |--> Apakah Password Lokal Cocok?
         |         +--[YA]--------> [TERMINASI CEPAT (SUCCESS)] -> Akses Diterima
         |         +--[TIDAK]-----> Lanjut ke modul berikutnya (Abaikan failure)
         |
         |---> [ Modul 4: required pam_deny.so ]
         |         |--> Mengembalikan Status: Gagal
         |         +--> Status Global: FAIL -> Lanjut (karena flag 'required')
         |
         v
    +--------------------------------------------------------+
    | Akhir Tumpukan (End of Stack)                          |
    | Evaluasi Seluruh Status Penilaian                      |
    +--------------------------------------------------------+
         |
         +--> [Apakah ada status FAIL?]
                   |--[YA]-----> Return PAM_AUTH_ERR (Akses Ditolak)
                   |--[TIDAK]--> Return PAM_SUCCESS (Akses Diberikan)
```

### Diagram 2: Skema Hak Akses Linux — POSIX ACL vs Standard UGO

```
  +---------------------------------------------------------------+
  |                     INODE PERMISSION CHECK                    |
  +---------------------------------------------------------------+
                                 |
                     [Apakah UID == File Owner?]
                                / \
                         YA    /   \  TIDAK
                              /     \
    +-----------------------+v       v+---------------------------+
    | Evaluasi Bit UGO Owner |        | Apakah POSIX ACL Aktif?   |
    |  (rwx------)          |        +---------------------------+
    +-----------------------+                     / \
                                           YA    /   \  TIDAK
                                                /     \
  +-------------------------------------------+v       v+------------------------+
  | Evaluasi ACL:                             |         | Evaluasi Group Standar |
  | 1. Cocok Named User (user:alice:r-x)?     |         |  (---rwx---)           |
  |    -> Bandingkan dengan ACL Mask          |         +------------------------+
  | 2. Cocok Group Utama/Named Group?         |                     |
  |    -> Bandingkan dengan ACL Mask          |                     v
  +-------------------------------------------+         [Evaluasi Bit Others]
                        |                               |  (------rwx)           |
                        +------------------------------>+------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut demonstrasi cara kerja SUID, SGID, dan Sticky Bit menggunakan shell dasar Linux.

### 1. Eksperimen SUID dan Risiko Eskalasi
```bash
# 1. Salin biner pembaca berkas ke direktori kerja
cp /usr/bin/cat /tmp/custom_cat

# 2. Periksa izin dasar
ls -l /tmp/custom_cat
# Output: -rwxr-xr-x 1 user user 43440 Jan 15 10:00 /tmp/custom_cat

# 3. Ubah kepemilikan menjadi root dan terapkan SUID (bit 4000)
sudo chown root:root /tmp/custom_cat
sudo chmod 4755 /tmp/custom_cat

# 4. Verifikasi bit izin (perhatikan huruf 's' pada segmen user)
ls -l /tmp/custom_cat
# Output: -rwsr-xr-x 1 root root 43440 Jan 15 10:00 /tmp/custom_cat

# 5. Uji membaca berkas rahasia sebagai pengguna reguler
/tmp/custom_cat /etc/shadow | head -n 2
# Berhasil membaca baris pertama /etc/shadow karena proses berjalan sebagai EUID=0 (root)

# 6. Pembersihan
rm -f /tmp/custom_cat
```

### 2. Eksperimen Direktori Kolaborasi Menggunakan SGID
```bash
# 1. Buat direktori bersama dan grup pengembang
sudo groupadd devs
sudo mkdir /srv/project_alpha
sudo chown root:devs /srv/project_alpha

# 2. Terapkan izin rwxrws--- (2770)
sudo chmod 2770 /srv/project_alpha
ls -ld /srv/project_alpha
# Output: drwxrws--- 2 root devs 4096 Jan 15 10:05 /srv/project_alpha

# 3. Setiap berkas yang dibuat di dalam /srv/project_alpha oleh anggota grup
# secara otomatis mewarisi grup 'devs', bukan primary group dari pembuat berkas.
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut skenario komprehensif implementasi pengerasan lingkungan produksi: Konfigurasi POSIX ACL untuk auditor, pengetatan tumpukan PAM terhadap serangan *brute force*, dan pengerasan parameter kernel via sysctl.

### Skenario:
Sistem mengharuskan direktori log aplikasi `/var/log/app_prod` dapat ditulis oleh service user `apprunner`, hanya dapat dibaca oleh grup `auditors` tanpa memberi mereka akses sudo/root, aman dari modifikasi tak sengaja, serta sistem terlindungi dari serangan SSH brute force menggunakan `pam_faillock`.

### Langkah 1: Konfigurasi POSIX ACL Direktori Produksi
```bash
# Persiapan path
sudo mkdir -p /var/log/app_prod
sudo chown apprunner:apprunner /var/log/app_prod
sudo chmod 700 /var/log/app_prod

# Berikan hak baca dan eksekusi (r-x) eksplisit ke grup 'auditors'
sudo setfacl -m g:auditors:rx /var/log/app_prod

# Terapkan Default ACL agar seluruh berkas baru otomatis mewarisi izin yang sama
sudo setfacl -d -m g:auditors:r /var/log/app_prod
sudo setfacl -d -m u:apprunner:rwx /var/log/app_prod

# Validasi implementasi ACL
getfacl /var/log/app_prod
```
*Output Representatif:*
```text
# file: var/log/app_prod
# owner: apprunner
# group: apprunner
user::rwx
group::---
group:auditors:r-x
mask::r-x
other::---
default:user::rwx
default:user:apprunner:rwx
default:group::---
default:group:auditors:r--
default:mask::rwx
default:other::---
```

### Langkah 2: Pengerasan PAM Menggunakan pam_faillock (Mencegah Serangan Brute-Force)
Konfigurasikan pembatasan autentikasi pada berkas `/etc/pam.d/password-auth` (RHEL/Rocky/Alma) atau `/etc/pam.d/common-auth` (Debian/Ubuntu):

Edit berkas konfigurasi PAM:
```pam
# /etc/pam.d/system-auth (Contoh tumpukan RHEL/CentOS/Rocky)
auth        required      pam_env.so
auth        required      pam_faillock.so preauth silent audit deny=3 unlock_time=900 even_deny_root
auth        sufficient    pam_unix.so nullok try_first_pass
auth        [default=die] pam_faillock.so authfail audit deny=3 unlock_time=900 even_deny_root
auth        required      pam_deny.so

account     required      pam_faillock.so
account     required      pam_unix.so
```
*Analisis Alur Kerja:*
* `preauth`: Memeriksa apakah akun sedang dalam masa penguncian (*locked*) sebelum mengevaluasi sandi. Jika gagal, proses ditolak tanpa memperingatkan penyerang (`silent`).
* `deny=3`: Mengunci akun setelah 3 kali upaya autentikasi salah.
* `unlock_time=900`: Durasi penguncian berlangsung selama 900 detik (15 menit).
* `even_deny_root`: Menetapkan aturan penguncian yang sama untuk akun `root` (opsional, gunakan dengan hati-hati).

Operasional Pemantauan & Unlocking:
```bash
# Menampilkan status percobaan gagal per pengguna
sudo faillock --user alice

# Membuka status kunci pengguna secara manual
sudo faillock --user alice --reset
```

### Langkah 3: Pengerasan Parameter Kernel Produksi via sysctl
Buat berkas konfigurasi `/etc/sysctl.d/99-security-hardening.conf`:

```ini
# Proteksi TCP/IP Stack terhadap Network Attacks
# Nonaktifkan IP Packet Forwarding (kecuali mesin bertindak sebagai router/gateway)
net.ipv4.ip_forward = 0

# Proteksi terhadap IP Spoofing menggunakan Reverse Path Filtering
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# Nonaktifkan respon terhadap ICMP Broadcast (Smurf attack mitigation)
net.ipv4.icmp_echo_ignore_broadcasts = 1

# Tolak semua ICMP Source Routed Packets
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0

# Proteksi terhadap SYN Flood attacks
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.tcp_synack_retries = 2

# Proteksi Terhadap Man-in-the-Middle via ICMP Redirect
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0

# Pengerasan Kernel Memory & Pointers
# Membatasi dmesg hanya untuk user dengan CAP_SYSLOG
kernel.dmesg_restrict = 1

# Sembunyikan alamat pointer kernel (/proc/kallsyms) dari unprivileged users
kernel.kptr_restrict = 2

# Cegah eksploitasi hardlink dan symlink (mencegah arbitrary file writes di /tmp)
fs.protected_hardlinks = 1
fs.protected_symlinks = 1
```

Terapkan parameter tanpa *reboot*:
```bash
sudo sysctl --system
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan / Fitur | Keuntungan | Kerugian / Risiko | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **SUID Bit** | Kemudahan eksekusi biner administratif oleh pengguna reguler tanpa integrasi `sudo`. | Risiko eskalasi hak istimewa paling berbahaya jika biner memiliki celah (*shell injection*, buffer overflow). | Sangat terbatas. Lebih baik digantikan dengan konfigurasi aturan granular pada `/etc/sudoers`. |
| **POSIX ACL** | Kontrol granular per pengguna/grup tanpa perlu merekayasa ulang struktur grup Linux global. | Kompleksitas tinggi saat troubleshooting, tidak semua alat cadangan (*backup/tar*) mempertahankan metadata ACL secara default. | Direktori bersama (*shared directories*), integrasi multi-departemen, aplikasi enterprise multi-tenant. |
| **PAM `pam_faillock` (even_deny_root)** | Menghentikan serangan kamus (*dictionary*) dan *brute force* pada kredensial root via SSH/konsol. | Berpotensi menimbulkan insiden *Denial of Service (DoS)*; penyerang sengaja mengirim request salah untuk mengunci akun root dan admin. | Wajib pada sistem publik, dengan syarat akses *out-of-band* (IPMI/Serial Console) atau key-based SSH tetap tersedia. |
| **Immutable Bit (`chattr +i`)** | Mencegah modifikasi berkas bahkan oleh root; sangat ampuh melindungi log historis dan `/etc/resolv.conf`. | Mengganggu proses pembaruan otomatis (*patching*) dan otomatisasi Ansible/Puppet jika berkas konfigurasi terkunci. | Berkas statis kritis, arsitektur *golden-image*, log historis pengawasan kepatuhan forensik. |

---

## SEKSI 11 — BEST PRACTICES

1. **Prinsip Least Privilege pada File Masking (Umask System-wide):**
   * Pastikan berkas `/etc/login.defs` atau `/etc/profile` memiliki konfigurasi `umask 027` (berkas: 640, direktori: 750) atau `umask 077` untuk server berkeamanan tinggi.
2. **Audit Periodik SUID/SGID Binary:**
   * Lakukan inspeksi biner berizin SUID secara otomatis untuk mendeteksi *backdoor*:
   ```bash
   find / -perm -4000 -type f -exec ls -ld {} \; 2>/dev/null
   ```
3. **Pemisahan Partisi Berdasarkan Mount Options:**
   * Jangan izinkan eksekusi SUID dan biner di direktori yang dapat ditulis oleh publik. Gunakan *mount flags* `noexec`, `nosuid`, dan `nodev` pada `/tmp`, `/var/tmp`, dan `/dev/shm` di `/etc/fstab`.
4. **Validasi Default ACL Saat Pembuatan Direktori Shared:**
   * Saat menggunakan `setfacl`, selalu sertakan flag `-d` (*default*) agar direktori dan berkas anak yang dibuat di masa mendatang tetap konsisten mewarisi izin yang sama.
5. **Gunakan `pam_wheel.so` untuk Mengunci Komando `su`:**
   * Pastikan hanya anggota grup administratif (`wheel`) yang dapat menjalankan biner `su -`:
   ```pam
   # /etc/pam.d/su
   auth required pam_wheel.so use_uid
   ```
6. **Cadangkan Konfigurasi PAM Sebelum Melakukan Modifikasi:**
   * Kesalahan sintaks satu karakter saja pada berkas `/etc/pam.d/` dapat mengakibatkan kegagalan login secara total (*lockout* total). Selalu buka satu sesi SSH cadangan (*active terminal*) sebelum menyimpan konfigurasi PAM baru.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Penggunaan `chmod 777` Sebagai "Jalan Pintas" Masalah Akses
* **Kesalahan:** Memberikan hak akses penuh kepada siapa saja untuk mengatasi masalah "Permission Denied" pada aplikasi.
* **Dampak:** Siapa pun pengguna lokal atau proses yang terkompromi dapat menginjeksikan kode jahat, menghapus berkas, atau memodifikasi biner kritis.
* **Solusi:** Analisis pengguna yang menjalankan layanan menggunakan `ps aux`, kemudian gunakan grup bersama yang spesifik atau pasang POSIX ACL menggunakan `setfacl`.

### 2. Mengabaikan Nilai ACL Mask
* **Kesalahan:** Menetapkan hak akses baca dan tulis (`rw-`) pada user melalui ACL, namun izin yang berlaku efektif tetap hanya baca (`r--`).
* **Penyebab:** Nilai `mask` pada ACL membatasi batas atas hak akses maksimum yang dapat diberikan kepada semua named users dan named groups.
* **Solusi:** Periksa dan sesuaikan mask menggunakan `setfacl -m m:rwx <target_file>`.

### 3. Mengubah Konfigurasi PAM Tanpa Sesi Alternatif Terbuka
* **Kesalahan:** Mengedit `/etc/pam.d/sshd` lalu keluar (*exit*) dari sesi terminal saat itu juga.
* **Dampak:** Terjadi kesalahan parsing modul; SSH daemon menolak semua upaya koneksi baru. Server terkunci dan harus ditangani melalui mode pemulihan (*single-user mode/GRUB*).
* **Solusi:** Selalu pertahankan sesi root aktif di satu terminal untuk keperluan *rollback*, dan uji konfigurasi menggunakan terminal terpisah: `ssh user@localhost`.

### 4. Menempatkan Modul PAM `sufficient` di Bawah Modul yang Mengalami Kegagalan
* **Kesalahan:** Menyusun tumpukan di mana pemeriksaan autentikasi alternatif diposisikan setelah modul dengan flag `requisite` yang telah memutus aliran (*early termination*).
* **Solusi:** Pahami alur eksekusi PAM secara linear: letakkan modul penentu kondisi awal di atas, diikuti dengan modul otentikasi utama dan modul fallback.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Audit dan Remediasi SUID/SGID (Level: Pemula)
1. Cari seluruh berkas di sistem Anda yang memiliki bit SUID aktif dan simpan daftarnya ke `/tmp/suid_audit.txt`:
   ```bash
   find / -perm /4000 -type f 2>/dev/null > /tmp/suid_audit.txt
   ```
2. Buat sebuah berkas uji: `/usr/local/bin/test_bin`. Berikan hak eksekusi dan pasang bit SUID.
3. Lepaskan bit SUID tersebut tanpa menghapus hak izin eksekusi (`x`) bagi owner.

### Latihan 2: Membangun Struktur Kolaboratif Proyek Lintas Departemen (Level: Menengah)
1. Buat direktori `/srv/data_bi`.
2. Buat dua pengguna baru: `analyst_john` dan `dev_sarah`. Buat grup: `bi_team`.
3. Tambahkan kedua pengguna ke dalam grup `bi_team`.
4. Konfigurasikan hak akses direktori tersebut sehingga:
   * Kepemilikan berkas dimiliki oleh `root:bi_team`.
   * Hanya anggota `bi_team` yang dapat membaca, menulis, dan membuat berkas di dalamnya.
   * Setiap berkas baru yang dibuat di dalam direktori secara otomatis dimiliki oleh grup `bi_team` (gunakan SGID).
   * Pengguna tidak dapat menghapus berkas milik rekannya sendiri (gunakan Sticky Bit).
   * Tambahkan entri ACL khusus untuk pengguna auditor eksternal `guest_auditor` dengan hak akses baca-saja (*read-only*) tanpa memasukkannya ke dalam grup `bi_team`.

### Latihan 3: Implementasi Password Aging dan Lockout System PAM (Level: Mahir)
1. Konfigurasikan modul `pam_faillock` di `/etc/pam.d/password-auth` (atau file padanannya di distribusi Anda).
2. Tentukan ambang batas: Akun akan terkunci selama 10 menit setelah 4 kali kegagalan input sandi berturut-turut.
3. Simulasikan kegagalan autentikasi pengguna dari terminal virtual menggunakan perintah `su - <user>`.
4. Jalankan perintah `faillock` untuk memverifikasi penambahan counter kegagalan.
5. Jalankan perintah reset `faillock` untuk memulihkan akses pengguna sebelum waktu 10 menit berakhir.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

**1. Jika sebuah direktori memiliki izin octal `1777`, apa arti fungsional dari angka '1' di posisi pertama?**
* A. Berkas di dalamnya hanya dapat dieksekusi oleh root.
* B. Direktori tersebut mewarisi grup induk ke seluruh berkas barunya (SGID).
* C. Berkas di dalam direktori hanya dapat dihapus oleh pemilik berkas, pemilik direktori, atau root (Sticky Bit).
* D. Direktori tersebut terkunci secara *immutable*.

**2. Dalam tumpukan evaluasi PAM, apa perbedaan mendasar antara control flag `required` dan `requisite`?**
* A. `required` langsung menghentikan tumpukan jika gagal, sedangkan `requisite` tetap mengeksekusi sisa tumpukan.
* B. `requisite` langsung menghentikan tumpukan jika gagal tanpa mengeksekusi modul berikutnya, sedangkan `required` tetap melanjutkan eksekusi tumpukan meskipun sudah mencatat kegagalan.
* C. `required` tidak memengaruhi hasil akhir autentikasi, sedangkan `requisite` mutlak menentukan.
* D. `requisite` digunakan untuk otentikasi biometrik, sedangkan `required` hanya untuk sandi.

**3. Output perintah `ls -l` pada sebuah berkas menampilkan `-rwxr-xr-x+`. Apa indikasi dari tanda plus `(+)` di akhir string izin tersebut?**
* A. Berkas memiliki atribut SELinux khusus.
* B. Berkas memiliki extended attribute `chattr +i`.
* C. Berkas memiliki konfigurasi POSIX ACL aktif yang dikelola via `setfacl`.
* D. Berkas tersebut adalah *hardlink* majemuk.

**4. Jika sebuah berkas memiliki hak akses standar `chmod 644` dan ACL mask diatur ke `r--`, hak akses maksimum apakah yang dapat dieksekusi oleh pengguna yang terdaftar di *named ACL* `user:bob:rw-`?**
* A. Read and Write (`rw-`).
* B. Read Only (`r--`).
* C. No Access (`---`).
* D. Full Access (`rwx`).

**5. Parameter sysctl manakah yang secara efektif mencegah serangan eksploitasi berbasis symlink di direktori publik yang dapat ditulis oleh semua orang (seperti `/tmp`)?**
* A. `kernel.kptr_restrict`
* B. `net.ipv4.tcp_syncookies`
* C. `fs.protected_symlinks`
* D. `kernel.dmesg_restrict`

---

### Kunci Jawaban & Pembahasan

1. **Jawaban: C.** Angka 1 pada digit pertama representasi 4-digit oktal merepresentasikan *Sticky Bit*. Fungsinya adalah membatasi wewenang penghapusan dan pengubahan nama berkas di direktori *shared* hanya kepada pemilik berkas (*owner*), pemilik direktori, atau *superuser*.
2. **Jawaban: B.** Modul dengan flag `requisite` akan langsung memutus (*abort*) alur eksekusi tumpukan PAM saat terjadi kegagalan dan mengembalikan pesan error seketika. Sebaliknya, flag `required` akan melanjutkan eksekusi modul-modul di bawahnya untuk mencegah potensi *timing attacks* dari pihak penyerang.
3. **Jawaban: C.** Tanda plus `(+)` pada utilitas coreutils `ls` menandakan bahwa berkas tersebut memiliki entri *POSIX Access Control List (ACL)* eksplisit di luar skema UGO standar. Entri tersebut dapat dilihat menggunakan utilitas `getfacl`.
4. **Jawaban: B.** Nilai ACL `mask` berfungsi sebagai filter batas atas (*ceiling*). Walaupun pengguna Bob diberikan izin `rw-`, operasi logika AND antara izin Bob (`rw-` = 110) dan Mask (`r--` = 100) menghasilkan izin efektif `r--` (Read Only).
5. **Jawaban: C.** Parameter `fs.protected_symlinks = 1` memastikan symlink hanya diikuti (*traversed*) jika berada di luar direktori *world-writable sticky*, atau jika pemilik symlink cocok dengan pemilik berkas target/pemilik direktori induk.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi & Standar:**
  * Linux PAM System Administrator's Guide: `https://www.linux-pam.org/Linux-PAM-html/Linux-PAM_SAG.html`
  * POSIX.1e Draft Standard 17 (Access Control Lists on POSIX): RFC/IEEE Working Group Documentation.
  * The Linux Kernel Documentation: *Sysctl Documentation* (`/Documentation/admin-guide/sysctl/`)
* **Buku Rekomendasi:**
  * Michael Kerrisk, *The Linux Programming Interface* (No Starch Press) — Bab 8 (Users and Groups), Bab 15 (File Attributes), Bab 23 (PAM).
  * Evi Nemeth et al., *UNIX and Linux System Administration Handbook* (Addison-Wesley).
* **Manual Pages Resmi:**
  * `man 5 pam.conf` / `man 8 pam`
  * `man 1 setfacl` / `man 1 getfacl` / `man 5 acl`
  * `man 1 chattr` / `man 1 lsattr`
  * `man 8 sysctl` / `man 5 sysctl.conf`
  * `man 8 pam_faillock`

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* Keamanan berkas dasar Linux diatur melalui model izin oktal UGO (User, Group, Other) dan dilengkapi tiga **Special Bits**: **SUID** (eksekusi biner sebagai pemilik berkas), **SGID** (pewarisan grup pada direktori atau eksekusi proses sebagai grup berkas), dan **Sticky Bit** (restriksi penghapusan berkas pada direktori bersama).
* **POSIX ACL** mengisi keterbatasan model UGO dengan menyediakan mekanisme untuk menetapkan izin spesifik pada banyak pengguna (*named users*) dan grup (*named groups*), yang dibatasi oleh nilai batas atas yang disebut **mask**.
* **PAM (*Pluggable Authentication Modules*)** memisahkan arsitektur otentikasi dari aplikasi. Tumpukan modul PAM dibagi ke dalam empat grup manajemen (`auth`, `account`, `password`, `session`) dan perilakunya dikendalikan oleh *control flags* (`required`, `requisite`, `sufficient`, `optional`).
* Pengerasan tumpukan PAM produksi dapat secara signifikan mengurangi risiko serangan berbasis identitas melalui modul mitigasi brute-force (`pam_faillock`) dan pembatasan eskalasi wewenang (`pam_wheel`).
* Pengerasan berkas dan kernel tingkat lanjut disempurnakan dengan menerapkan **extended file attributes** (seperti flag *immutable* via `chattr`) untuk mencegah modifikasi tidak sah, serta optimasi parameter runtime kernel melalui `/etc/sysctl.d/` untuk menutup celah serangan berbasis jaringan (*network spoofing*, SYN floods) dan memori.

---

## SEKSI 17 — GLOSARIUM

* **DAC (Discretionary Access Control):** Model pembatasan akses di mana pemilik objek menentukan hak izin akses kepada entitas lain (fondasi sistem perizinan standar Linux).
* **EUID (Effective User ID):** Identitas pengguna yang secara aktual digunakan oleh kernel Linux untuk menentukan hak akses proses terhadap operasi berkas dan sistem.
* **SUID (Set User ID):** Atribut izin berkas yang memerintahkan kernel untuk menetapkan EUID proses eksekusi sesuai dengan pemilik berkas biner tersebut.
* **POSIX ACL:** Ekstensi standar POSIX yang memungkinkan pemetaan hak akses berkas secara lebih fleksibel terhadap beberapa entitas pengguna maupun grup.
* **ACL Mask:** Nilai pembatas pada POSIX ACL yang mendefinisikan batas hak akses maksimum (*maximum effective rights*) untuk semua *named user*, *file group*, dan *named group*.
* **PAM (Pluggable Authentication Modules):** Kerangka kerja modular di Linux yang mengelola proses autentikasi, verifikasi akun, kebijakan kata sandi, dan pemeliharaan sesi aplikasi.
* **Control Flag (PAM):** Instruksi evaluasi logis yang menentukan respons PAM terhadap keberhasilan atau kegagalan modul tertentu dalam sebuah tumpukan otentikasi.
* **pam_faillock:** Modul PAM modern yang melacak dan membatasi upaya autentikasi yang gagal per pengguna untuk menangkal serangan brute-force.
* **Immutable Flag (`+i`):** Atribut sistem berkas khusus pada sistem Linux yang membuat sebuah berkas sepenuhnya read-only dan kebal dari modifikasi, penghapusan, atau penautan, bahkan oleh pengguna root.
* **sysctl:** Utilitas Linux yang digunakan untuk memeriksa dan mengubah parameter konfigurasi kernel Linux secara dinamis saat sistem beroperasi (*runtime*).

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Poin Pedagogis Utama:
* **Visualisasi Alur Kontrol PAM:** Peserta didik sering kali keliru memahami perbedaan antara `required` dan `requisite`. Tekankan perbedaan konsep "langsung berhenti saat gagal (*fail early*)" pada `requisite` versus "lanjutkan eksekusi hingga akhir tumpukan (*silent tally*)" pada `required`.
* **Korelasi Masking ACL:** Selalu ingatkan siswa bahwa penambahan hak akses melalui `setfacl -m u:alice:rwx` tidak akan bekerja efektif jika `mask` pada berkas tersebut dibatasi, misalnya menjadi `r--`. Gunakan demonstrasi langsung menggunakan `getfacl` untuk memperlihatkan baris output `#effective:`.
* **Potensi Bahaya Penggunaan `even_deny_root`:** Berikan peringatan keras mengenai parameter `even_deny_root` pada `pam_faillock`. Tunjukkan skenario di mana seorang penyerang dapat melumpuhkan server produksi secara remote hanya dengan mengirimkan ribuan percobaan SSH login gagal dengan user target `root`.

### Jebakan Umum dalam Laboratorium:
* Pastikan partisi pengujian yang digunakan siswa mendukung ACL. Jika menggunakan sistem berkas lawas yang di-mount manual tanpa opsi `acl`, perintah `setfacl` akan menghasilkan pesan error `Operation not supported`.
* Siswa sering kali terjebak dalam kondisi terkunci saat menguji modul PAM. **Wajibkan** siswa membuka minimal dua terminal root aktif sebelum memodifikasi berkas apa pun di `/etc/pam.d/`.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Januari 2025):**
  * Rilis modul kurikulum komprehensif standar format 20 Seksi GEMINI.md.
  * Integrasi modul modern `pam_faillock` (menggantikan `pam_tally2` yang telah di-deprecate pada distribusi Linux modern).
  * Penambahan konfigurasi pengerasan *runtime* parameter kernel via `sysctl`.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** 
  * [LIN-01-06-02] Manajemen Pengguna, Grup, dan Shadow File System
* **Modul Saat Ini:**
  * [LIN-01-07-01] Tata Kelola Izin Lanjutan, Arsitektur PAM, dan Hardening Kernel/Sistem
* **Modul Berikutnya:** 
  * [LIN-01-07-02] Mandatory Access Control (MAC): Fondasi SELinux dan AppArmor Dasar