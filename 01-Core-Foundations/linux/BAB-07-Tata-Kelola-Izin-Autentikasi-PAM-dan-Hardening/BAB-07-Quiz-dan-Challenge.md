# BAB 07: Quiz, Challenge, & Knowledge Check
**Tata Kelola Izin, Autentikasi PAM, dan Pengerasan Keamanan**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Evaluasi Izin Discretionary Access Control (DAC) dan Operasi Umask
Jelaskan secara deterministik bagaimana kernel Linux mengevaluasi izin akses (Read, Write, Execute) ketika sebuah proses mencoba membuka inode berkas melalui system call `open()` atau `execve()`. Mengapa kernel **berhenti** mengevaluasi izin begitu menemukan kecocokan identitas (Owner -> Group -> Others), dan bagaimana operasi bitwise matematika `mode & ~umask` diaplikasikan saat proses pembuatan berkas baru dengan argumen `open(path, O_CREAT, 0666)`?

### Soal 1.2: Mekanisme Khusus: SUID, SGID, dan Sticky Bit
Uraikan perbedaan fungsional dan implikasi keamanan dari bit izin khusus berikut:
1. **SetUID (SUID)** pada file biner ELF vs script interpreter (seperti shell atau Python) di Linux modern. Mengapa kernel Linux secara eksplisit mengabaikan bit SUID pada script yang dieksekusi via `#!` (shebang)?
2. **SetGID (SGID)** pada direktori: Bagaimana mekanisme pewarisan *group ownership* bekerja untuk file/subdirektori baru yang dibuat di dalamnya?
3. **Sticky Bit (Restricted Deletion Flag)** pada direktori bersama (seperti `/tmp`): Kondisi logika apa yang harus dipenuhi agar sebuah proses diizinkan melakukan system call `unlink()` atau `rename()` terhadap file di dalam direktori ber-sticky bit?

### Soal 1.3: POSIX Access Control Lists (ACLs) dan Mask Field
Dalam model DAC tradisional, batasan `rwxrwxrwx` hanya mengizinkan 1 user pemilik dan 1 grup pemilik. POSIX ACL memecahkan keterbatasan ini. Jelaskan peran kritis dari entri `mask` (`ACL_MASK`) dalam POSIX ACL. Bagaimana interaksi antara `chmod` konvensional dengan entri `mask` yang telah dikonfigurasi pada suatu berkas, dan apa dampaknya terhadap *effective permissions* dari *named users* dan *named groups*?

### Soal 1.4: Arsitektur Pemisahan Tugas pada PAM (Pluggable Authentication Modules)
PAM memisahkan logika autentikasi dari *codebase* aplikasi (seperti OpenSSH, sudo, login). Jelaskan fungsi, siklus hidup, dan batasan tanggung jawab dari 4 tipe modul PAM (management groups):
1. `auth`
2. `account`
3. `password`
4. `session`

Berikan contoh konsekuensi keamanan jika administrator salah meletakkan modul pembatasan login berbasis waktu (seperti `pam_time.so`) di dalam grup `auth` alih-alih grup `account`.

### Soal 1.5: Linux Capabilities: Dekonstruksi Monolitik Privilege `root`
Secara historis, UNIX membagi dunia ke dalam UID `0` (super-user serba bisa) dan non-zero (unprivileged). Linux Capabilities (`capabilities(7)`) memecah privilese root menjadi lebih dari 40 bit independen. Jelaskan perbedaan mendasar antara set kapabilitas berikut pada sebuah proses:
- `CapEff` (Effective)
- `CapPrm` (Permitted)
- `CapInh` (Inheritable)
- `CapAmb` (Ambient)

Mengapa ketersediaan Ambient Capabilities sangat penting dalam orkestrasi container dan service daemon modern yang berjalan tanpa identitas root?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Eksekusi Stack PAM Tradisional vs Modern Control Syntax
Diberikan konfigurasi stack PAM `/etc/pam.d/custom-service` berikut:

```text
auth    requisite     pam_nologin.so
auth    sufficient    pam_ldap.so
auth    required      pam_unix.so try_first_pass
auth    required      pam_deny.so
```

1. Bedah alur eksekusi (*control flow*) jika `pam_ldap.so` menghasilkan status `PAM_AUTH_ERR` (autentikasi gagal), tetapi user memasukkan password lokal yang valid untuk `pam_unix.so`. Apakah user berhasil login?
2. Bagaimana alur eksekusinya jika `pam_ldap.so` menghasilkan `PAM_SUCCESS`? Jelaskan apakah `pam_unix.so` dan `pam_deny.so` tetap dieksekusi atau di-*short-circuit*.
3. Ubah stack di atas ke dalam sintaks modern array kontrol eksplisit:
   `[success=N new_authtok_reqd=N default=N]` untuk mengeliminasi ketergantungan pada modul `pam_deny.so`.

### Soal 2.2: Capability Dropping, Bounding Set, dan Eksekusi `execve()`
Sebuah daemon C beroperasi dengan UID 0 untuk mengikat port jaringan privileged (port 443 via `CAP_NET_BIND_SERVICE`). Setelah melakukan `bind()`, daemon melakukan *capability dropping* dan berpindah ke UID non-root (`www-data`, UID 33) menggunakan `setresuid()`.
1. Mengapa secara default, memanggil `setresuid()` dari UID 0 ke UID non-zero akan menghapus seluruh isi capability sets (`CapPrm`, `CapEff`)?
2. Flag prctl apa (`PR_SET_KEEPCAPS` / `SECBIT_KEEP_CAPS`) yang wajib dikonfigurasi sebelum `setresuid()` jika proses tersebut berniat mempertahankan kapabilitas tertentu?
3. Jika daemon tersebut kemudian memanggil fungsi `execve()` untuk menjalankan *worker subprocess*, kondisi apa yang harus dipenuhi agar biner worker non-root tersebut tetap mewarisi `CAP_NET_BIND_SERVICE` tanpa perlu memasang File Capabilities (`setcap`) pada binary disk?

### Soal 2.3: VFS Inode Immutability (`chattr`) vs DAC Permissions
Seorang administrator mengonfigurasi permission berkas `/var/log/secure_audit.log` menjadi `0777` (Full Access ke semua user), namun kemudian mengeksekusi:
```bash
chattr +a /var/log/secure_audit.log
```
1. Jelaskan bagaimana VFS (Virtual Filesystem Switch) dan filesystem driver (misalnya ext4 atau XFS) memvalidasi operasi `open(path, O_TRUNC | O_WRONLY)` yang dilakukan oleh user `root` sekalipun.
2. Flag apa yang dimutasi pada disk inode metadata (misalnya `ext4_inode->i_flags`), dan mengapa syscall seperti `truncate()` atau penyuntingan berkas via `vim` gagal dengan `EPERM` (Operation not permitted) padahal `echo "entry" >> /var/log/secure_audit.log` berhasil?
3. Bagaimana cara proses unprivileged mempertahankan data jika penyerang memiliki akses root namun tidak mengetahui mekanisme extended attributes yang terpasang?

### Soal 2.4: TOCTOU (Time-of-Check to Time-of-Use) Symlink Race Condition & Kernel Hardening
Perhatikan skenario eksploitasi klasik berikut pada skrip automasi yang berjalan sebagai root:
```bash
# Script berjalan berkala via cron sebagai root:
if [ ! -f /tmp/backup.lock ]; then
    # Window of vulnerability
    touch /tmp/backup.lock
    /usr/local/bin/run_backup
fi
```
1. Jelaskan bagaimana penyerang unprivileged lokal dapat memanfaatkan celah *TOCTOU* di atas dengan teknik symlink race condition untuk menimpa berkas kritis `/etc/shadow`.
2. Jelaskan peran perlindungan kernel parameter `fs.protected_symlinks` dan `fs.protected_hardlinks` (`sysctl(8)`). Kondisi spesifik apa yang dievaluasi kernel saat proses membuka symlink di direktori `world-writable sticky` (seperti `/tmp`) sehingga eksploitasi symlink tersebut diblokir dengan `EACCES`?
3. Bagaimana cara memprogram atomic file creation pada Linux untuk mengeliminasi TOCTOU secara absolut menggunakan flag `O_CREAT | O_EXCL` pada C atau `noclobber` pada shell?

### Soal 2.5: Metodologi Diagnostik Low-Level Autentikasi PAM & Audit Trail
Ketika pengguna sah melaporkan kegagalan login SSH secara acak tanpa adanya log deskriptif di `/var/log/auth.log` (karena modul PAM menyamarkan error demi mitigasi *user enumeration*):
1. Bagaimana Anda mengaktifkan *tracing* mendalam pada subsistem PAM menggunakan environment variables, flag konfigurasi pam (`pam_debug`), dan utilitas `auditd`?
2. Bagaimana cara menggunakan `strace` untuk melacak proses `sshd` saat menerima koneksi, mendeteksi syscall `openat()`, `connect()`, atau `read()` mana pada modul PAM (misalnya LDAP, Kerberos, atau SSSD) yang mengalami hang atau me-return exit code selain `0`?
3. Tuliskan satu aturan `auditctl` untuk memantau setiap modifikasi pada file database otentikasi `/etc/pam.d/` dan `/etc/shadow` secara *real-time* dengan menyertakan syscall, PID, AUID (Audit UID), dan nama biner yang mengeksekusi modifikasi tersebut.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Sistemik: PAM Stack Failure Mengakibatkan SSH Cascading Outage Skala Besar
**Konteks Lingkungan:**
Sebuah cluster production yang terdiri dari 500 server Linux (Ubuntu LTS) menggunakan SSSD (`pam_sss.so`) untuk integrasi autentikasi identitas terpusat (Active Directory / FreeIPA). Pada pukul 03.00, koneksi jaringan inter-VPC menuju cluster LDAP controller putus total akibat pemeliharaan firewall core.

**Masalah:**
1. Teknisi on-call mencoba mengakses node Linux melalui SSH menggunakan akun lokal `emergency_admin` yang terdaftar langsung di `/etc/passwd` dan `/etc/shadow`.
2. Koneksi SSH mengalami *hang* selama 60 detik sebelum akhirnya me-return error: `Connection closed by remote host` atau `Permission denied (publickey,password)`.
3. Akibat kegagalan SSH ini, insinyur tidak dapat masuk ke server untuk menangani masalah sistem yang bergantung pada VPC tersebut.

```text
# Konfigurasi /etc/pam.d/common-auth pada server:
auth    [success=2 default=ignore]    pam_sss.so
auth    [success=1 default=ignore]    pam_unix.so try_first_pass
auth    requisite                     pam_deny.so
auth    required                      pam_permit.so
```

**Tugas Diagnostik & Solusi Anda:**
1. Bedah secara mekanis mengapa akun lokal `/etc/passwd` gagal diautentikasi tepat waktu dan mengapa SSH mengalami timeout. Mengapa posisi dan konfigurasi control flag pada `pam_sss.so` menjadi *single point of failure*?
2. Parameter apa pada konfigurasi SSSD (`sssd.conf`) dan PAM (`pam_sss.so`) yang seharusnya mencegah modul menunggu response LDAP saat network unreachable (misal: timeout, offline caching, failover)?
3. Rekonstruksi arsitektur PAM stack di atas agar akun lokal (`pam_unix.so`) memiliki deterministik jalur otentikasi yang independen dan instan ketika layanan LDAP down, tanpa mengorbankan keamanan integritas domain directory di kondisi normal.

---

### Skenario B: Eksploitasi Hak Akses via Shared Build Environment (Race Condition & Privilege Escalation)
**Konteks Lingkungan:**
Sebuah server bare-metal multi-tenant digunakan bersama oleh 20 tim developer untuk proses integrasi CI/CD runner. Semua build jobs dieksekusi dengan akun non-root unik berdasarkan nama proyek (misal: `build_proj_a`, `build_proj_b`). Semua proyek tergabung dalam grup sekunder yang sama: `developers`.

Struktur direktori kerja bersama:
```bash
drwxrwxrwt 50 root developers 4096 Jun 10 10:00 /shared/artifacts/
```

**Masalah & Insiden:**
Tim Security mendeteksi bahwa artefak rilis biner milik `build_proj_a` disusupi oleh kode arbitrer berbahaya sebelum ditandatangani secara digital (digital signing). Pemeriksaan log membuktikan bahwa proses milik `build_proj_b` sempat memanipulasi file milik `build_proj_a` di `/shared/artifacts/proj_a/release.tar.gz`.

Investigasi izin menunjukkan:
```text
/shared/artifacts/proj_a:
drwxrwxr-x 2 build_proj_a developers 4096 Jun 10 10:05 .
-rw-rw-r-- 1 build_proj_a developers 1048576 Jun 10 10:06 release.tar.gz
```

**Tugas Diagnostik & Solusi Anda:**
1. Jelaskan bagaimana proses milik `build_proj_b` dapat memodifikasi, menimpa, atau menukar file `release.tar.gz` meskipun berkas tersebut dimiliki oleh `build_proj_a`. Analisis peran bit izin direktori parent dan interaksi grup `developers`.
2. Rancang skema perizinan POSIX standar dan ACL (`setfacl`) baru untuk `/shared/artifacts/` yang memastikan:
   - Setiap proyek hanya bisa membaca dan menulis direktori miliknya sendiri.
   - Tidak ada anggota grup `developers` yang bisa membaca artefak milik proyek lain (*isolation*).
   - Layanan automated signer (`user: release_signer`) dapat membaca semua artefak secara read-only tanpa memerlukan hak root.
3. Tuliskan command automasi `setfacl` (termasuk *default ACLs* untuk pewarisan berkas baru) yang menutup celah ini secara permanen.

---

### Skenario C: Dilema Arsitektur Keamanan: Micro-Privilege Escalation vs Container Confinement
**Konteks Lingkungan:**
Arsitektur aplikasi microservices finance memproses transaksi pembayaran. Layanan `payment-processor` berjalan sebagai service non-root (`payuser`, UID 1001) di dalam VM Linux. Aplikasi memerlukan wewenang operasional berikut:
1. Membaca TLS private keys yang hanya boleh diakses oleh root (`/etc/ssl/private/payment.key`, permission `0400 root:root`).
2. Melakukan *in-memory memory locking* (`mlock()`, `mlockall()`) untuk mencegah data nomor kartu kredit di-*swap* ke disk swap Linux.
3. Membuka raw socket untuk mengirim paket diagnostik ICMP/Health check jaringan khusus.

Developer mengusulkan solusi termudah:
"Tambahkan `payuser ALL=(ALL) NOPASSWD: ALL` di `/etc/sudoers` atau jalankan service sepenuhnya sebagai user `root`". Tim Compliance & Security menolak mentah-mentah usulan ini karena melanggar standar PCI-DSS dan prinsip *Least Privilege*.

**Tugas Diagnostik & Solusi Anda:**
1. Bedah risiko keamanan catastrophic jika aplikasi Node.js/Java tersebut berjalan dengan full `root` privilege atau memiliki akses `sudo NOPASSWD: ALL` terhadap ancaman Remote Code Execution (RCE).
2. Rancang solusi granular non-root berbasis **Linux Capabilities** dan **POSIX Group/ACLs** untuk memenuhi ketiga kebutuhan di atas secara terpisah tanpa memberikan akses root monolitik:
   - Bagaimana cara menangani pembacaan TLS private key secara aman?
   - Kapabilitas Linux apa yang dibutuhkan untuk operasi `mlock()`?
   - Kapabilitas Linux apa yang dibutuhkan untuk raw socket ICMP?
3. Tuliskan implementasi konkretnya dalam bentuk *Systemd Service Unit Override* (`/etc/systemd/system/payment-processor.service.d/override.conf`) menggunakan direktif:
   - `AmbientCapabilities=`
   - `CapabilityBoundingSet=`
   - `ProtectSystem=`
   - `NoNewPrivileges=`
   - `SupplementaryGroups=`

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Lingkungan Multi-Tenant Bastion Host Berkadar Militer

#### Deskripsi Masalah
Anda ditugaskan merancang arsitektur keamanan untuk sebuah Gateway/Bastion Server Linux (`bastion-core-01`) yang melayani akses insinyur internal, auditor eksternal, dan automasi CI/CD. Server ini merupakan target prioritas tinggi. 

Jika terjadi kompromi kredensial, sistem operasi harus menerapkan pertahanan mendalam (*defense-in-depth*) berbasis pam, ACL, capabilities, dan filesystem immutability sehingga penyerang tidak dapat melakukan eskalasi hak akses (privilege escalation), tidak dapat membaca log audit, dan tidak dapat memodifikasi file konfigurasi sistem.

#### Spesifikasi & Kebutuhan Teknis

1. **Grup Identitas & Partisi Hak Akses:**
   - Buat user `auditor_sec` (Group: `auditors`). User ini **hanya** boleh membaca direktori `/var/log/` dan file audit trail, termasuk membaca `/var/log/audit/audit.log` (yang default-nya `0600 root:root`), tetapi **dilarang keras** memiliki hak sudo dan dilarang mengubah file log apapun.
   - Buat direktori deployment `/srv/secure_apps/`. Konfigurasikan hak akses direktori sedemikian rupa sehingga user `deployer` dapat membuat, mengedit, dan menghapus file di dalamnya, sedangkan user `app_runner` hanya dapat membaca dan mengeksekusi file biner, tanpa bisa memodifikasi berkas baru yang dibuat oleh `deployer`.

2. **Pengerasan Autentikasi PAM (`/etc/pam.d/sshd`):**
   - Batasi login SSH: User root dilarang login via password sama sekali.
   - Integrasikan modul `pam_faillock.so` (atau `pam_tally2` tergantung distro) untuk mengunci akun selama 15 menit jika terjadi salah password sebanyak 3 kali berturut-turut dalam kurun waktu 5 menit.
   - Modul PAM harus memastikan bahwa user dalam grup `auditors` hanya diizinkan login pada jam kerja (Senin–Jumat, 08:00–18:00) menggunakan konfigurasi `pam_time.so`.

3. **Restriksi Privilese Biner Tanpa SUID:**
   - Aplikasi kustom `/opt/bin/netmonitor` membutuhkan kemampuan menangkap network traffic promiscuous mode (`libpcap`). Biner ini **tidak boleh** memiliki bit SUID root (`chmod u+s` dilarang).
   - Berikan izin pada binary file tersebut menggunakan Linux File Capabilities secara presisi.

4. **Integritas Konfigurasi Kritis via Filesystem Attributes:**
   - Amankan berkas `/etc/resolv.conf`, `/etc/hosts`, dan file PAM yang baru dibuat dari modifikasi tidak disengaja atau tampering oleh malware, bahkan jika malware tersebut berhasil mengelabui proses hingga menjadi root, menggunakan Extended Attributes (`chattr`).

#### Batasan Implementasi (Constraints)
- Tidak boleh menonaktifkan SELinux/AppArmor jika terpasang (harus berjalan di mode `Enforcing`).
- Tidak boleh menggunakan perintah blanket `chmod -R 777` atau `chown root:root` di mana-mana.
- Seluruh konfigurasi PAM harus *syntactically valid*. Kesalahan penulisan yang menyebabkan sistem terkunci permanen (*lockout*) berarti kegagalan fatal.

#### Output yang Diharapkan
1. **Shell Script Otomasi Setup (`harden_bastion.sh`):**
   Skrip idempoten yang mengonfigurasi user, grup, POSIX ACLs, dan atribut extended.
2. **File Snippet PAM (`/etc/security/time.conf` & `/etc/pam.d/sshd`):**
   Potongan konfigurasi PAM stack yang mengimplementasikan mitigasi brute-force dan time-restriction.
3. **Audit & Verification Script (`verify_security.sh`):**
   Skrip validasi yang menjalankan serangkaian pengujian:
   - Tes verifikasi akses `auditor_sec` ke `/var/log/audit/audit.log`.
   - Tes verifikasi eksekusi `/opt/bin/netmonitor` dari user biasa non-root via capabilities.
   - Uji penolakan modifikasi file ber-atribut immutable (`chattr +i`).

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk memverifikasi kesiapan operasional Anda dalam mengelola izin, otentikasi, dan pengerasan sistem Linux di tingkat Enterprise.

### Saya harus memahami:
- [ ] Logika pohon resolusi izin DAC kernel Linux (Owner -> Group -> Others) dan alasan mengapa user yang cocok dengan Owner tidak akan pernah dievaluasi terhadap Group permission.
- [ ] Aljabar Boolean antara mode permissions default kernel (`0666` untuk file, `0777` untuk direktori) terhadap bit inversi `umask`.
- [ ] Anatomi struktural POSIX ACLs, perbedaan antara Base ACL, Extended ACL, Default ACL, serta implikasi kalkulasi matematis `effective permission` melalui `ACL_MASK`.
- [ ] Perbedaan fundamental antara 4 control flags legasi PAM (`required`, `requisite`, `sufficient`, `optional`) dan bagaimana array sintaks modern `[value1=action1 ...]` memetakan alur eksekusi stack PAM.
- [ ] Bahaya keamanan dari SUID pada file biner kompilasi (misalnya buffer overflow leading to root shell) dan mekanisme pemblokiran eksekusi SUID interpreter script via kernel.
- [ ] Pembagian kapabilitas Linux (`CapEff`, `CapPrm`, `CapInh`, `CapAmb`, `CapBnd`) dan bagaimana model ini meniadakan kebutuhan SUID binary di infrastruktur cloud modern.
- [ ] VFS layer extended file attributes (`chattr` flag `+i` immutable dan `+a` append-only) serta pengaruhnya terhadap system call `unlink()`, `truncate()`, dan `open()` mode write.
- [ ] Mekanisme kerentanan TOCTOU (Time-of-Check to Time-of-Use), symlink traversal attacks di direktori bertipe `/tmp`, dan mitigasi kernel melalui `protected_symlinks` dan `protected_hardlinks`.

### Saya tidak perlu menghafal:
- [ ] Nilai integer heksadesimal atau oktal spesifik dari konstanta bitmask kapabilitas internal Linux kernel di header `capability.h` (cukup gunakan representasi string seperti `CAP_NET_ADMIN`, `CAP_SYS_PTRACE`).
- [ ] Seluruh nomor error code PAM (seperti `PAM_AUTH_ERR = 7`, `PAM_USER_UNKNOWN = 10`) di luar kepala; fokus pada pemahaman semantik fungsional modul dan pemetaan statusnya.
- [ ] Sintaks baris per baris konfigurasi library modul pihak ketiga PAM yang jarang digunakan (misal: `pam_pkcs11`), asalkan memahami dokumentasi `man` modul terkait dan arsitektur stack-nya.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan memperbaiki masalah *permission denied* pada aplikasi kompleks menggunakan kombinasi utilitas `namei -l`, `getfacl`, dan `ls -laZ`.
- [ ] Menerapkan POSIX ACL secara rekursif termasuk *Default Inheritance ACL* (`setfacl -d -m ...`) agar file baru mewarisi izin grup yang tepat secara otomatis.
- [ ] Membedah, merekonstruksi, dan men-debug file stack PAM di `/etc/pam.d/` tanpa menyebabkan insiden *SSH lock-out* pada server remote.
- [ ] Mengonfigurasi mitigasi proteksi brute-force SSH dan kebijakan penuaan/kompleksitas kata sandi menggunakan modul PAM terstandarisasi (`pam_faillock`, `pam_pwquality`).
- [ ] Memeriksa, memberikan, dan mencabut Linux File Capabilities pada binary menggunakan `getcap` dan `setcap`.
- [ ] Mengonfigurasi Systemd service unit untuk mengisolasi proses daemon menggunakan direktif hardening: `NoNewPrivileges=yes`, `CapabilityBoundingSet=`, `ProtectSystem=strict`, dan `ProtectHome=yes`.
- [ ] Melacak system call keamanan yang gagal secara real-time menggunakan `strace -e trace=file,desc,security` dan menganalisis log subsystem Linux Audit menggunakan `ausearch` dan `aureport`.