# BAB 10: Quiz, Challenge, & Knowledge Check
**Otomasi Bare-Metal, Hardening Standar CIS, dan Disaster Recovery**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Bootstrapping Bare-Metal & Network Boot Flow
Jelaskan urutan deterministik dari proses PXE boot standar saat sebuah server fisik pertama kali dinyalakan (POST) hingga kernel Linux mengambil alih eksekusi sistem. Uraikan peran dari DHCP Options 66 (`Next-Server`) dan 67 (`Bootfile-Name`), mekanisme transisi dari TFTP ke HTTP (pada iPXE), dan mengapa TFTP dianggap sebagai bottleneck performa mendasar pada deployment paralel ratusan node.

### Soal 1.2: Unattended Installation: Imperative Scripting vs Declarative Metadata
Bandingkan arsitektur dan siklus hidup provisioning antara installer OS tradisional berbasis template (seperti RHEL Kickstart atau Debian Preseed) dengan tool declarative instance initialization (seperti `cloud-init` via Cloud-Init NoCloud datasource). Kapan instruksi partitioning, pre-install, dan post-install dieksekusi oleh masing-masing pendekatan terhadap disk lokal?

### Soal 1.3: Filosofi Hardening CIS Benchmark & Filesystem Layouting
Standar *Center for Internet Security* (CIS) mensyaratkan partisi terpisah untuk mount point direktori `/tmp`, `/var`, `/var/tmp`, `/var/log`, dan `/var/log/audit`. Jelaskan alasan arsitektural dan keamanan di balik pemisahan ini. Sertakan analisis mendalam mengapa mount options `nodev`, `nosuid`, dan `noexec` wajib diterapkan pada `/tmp` dan `/dev/shm`, serta ancaman apa yang dimitigasi secara langsung oleh konfigurasi ini.

### Soal 1.4: Arsitektur Kernel Auditing (`kauditd`) dan Netlink Interface
Bagaimana subsistem Linux Audit (`auditd`) beroperasi di dalam kernel space? Jelaskan aliran data ketika sebuah system call (misal: `execve` atau `openat`) dipanggil oleh unprivileged process: bagaimana kernel matching filter mengevaluasi rule, bagaimana `kauditd` menggunakan asynchronous Netlink socket untuk mengirimkan event ke userspace daemon, dan apa implikasi performa terhadap I/O throughput jika diterapkan audit rule yang terlalu granular?

### Soal 1.5: Taksonomi Disaster Recovery: RPO/RTO vs Metodologi Backup State
Ditinjau dari *Recovery Point Objective* (RPO) dan *Recovery Time Objective* (RTO), bedakan trade-off teknis antara:
1. File-level backup inkremental terdeduplikasi (contoh: Borg, Restic).
2. Block-level live copy/snapshot (contoh: LVM Snapshot, ZFS send/receive, Ceph RBD mirror).
3. Image-based bare-metal recovery (contoh: ReaR - Relax-and-Recover).
Bagaimana penanganan integritas data (*application-consistent* vs *crash-consistent*) pada masing-masing metode tersebut?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Secure Boot, Shim Loader, dan MOK Management pada Custom Kernel
Sebuah node bare-metal di-provisioning otomatis menggunakan PXE dengan UEFI Secure Boot aktif. Saat boot, node berhasil memuat `shimx64.efi` yang ditandatangani oleh Microsoft 3rd Party UEFI CA, namun gagal memuat custom kernel enterprise yang telah di-patch:
```
error: /vmlinuz-6.6.0-custom has invalid signature.
Loading initial ramdisk ...
error: you need to load the kernel first.
```
Jelaskan alur verifikasi kriptografis dari UEFI NVRAM variables (`PK`, `KEK`, `db`) ke Shim, Grub2, hingga Kernel. Bagaimana cara merancang otomasi injeksi *Machine Owner Key* (MOK) atau signing pipeline internal (menggunakan OpenSSL dan `sbsign`) agar custom kernel dan driver out-of-tree (seperti driver storage RAID proprietary) lolos verifikasi tanpa menonaktifkan Secure Boot di level hardware?

### Soal 2.2: Initramfs Debugging dan Network Storage Bring-Up
Ketika mengotomasi deployment diskless node atau root filesystem berbasis iSCSI/NFS, server berhenti pada emergency shell `dracut` dengan pesan:
```
dracut-initqueue[421]: Warning: dracut-initqueue: timeout, still waiting for following initqueue hooks:
dracut-initqueue[421]: Warning: /lib/dracut/hooks/initqueue/finished/devexists-\x2fdev\x2froot.sh
Entering emergency mode. Exit the shell to continue.
```
Bagaimana metodologi Anda melakukan root-cause analysis di dalam environment minimal initramfs? Sebutkan parameter kernel command-line (seperti `rd.break`, `rd.net.timeout.carrier`, atau `rd.shell`) yang harus di-inject pada GRUB, dan jelaskan potensi race condition antara waktu inisialisasi driver NIC (firmware loading), DHCP acquisition, dan penataan target disk via udev.

### Soal 2.3: Analisis AVC Denial Pasca-CIS Hardening
Setelah script CIS Level 2 hardening dijalankan pada server database RHEL/Rocky Linux, service PostgreSQL menolak untuk start dengan exit status error I/O, padahal permission direktori data sudah di-set ke `0700` milik user `postgres:postgres`:
```
systemd[1]: postgresql-16.service: Main process exited, code=exited, status=1/FAILURE
FATAL: could not open file "/var/lib/pgsql/16/data/global/pg_control": Permission denied
```
Bagaimana Anda memanfaatkan toolchain SELinux (`ausearch`, `audit2why`, `sealert`) untuk membuktikan bahwa masalah ini disebabkan oleh context label atau transisi domain yang keliru akibat restrukturisasi partisi `/var`? Tuliskan langkah presisi untuk me-relabel filesystem tanpa menurunkan enforcement mode (`setenforce 0`).

### Soal 2.4: Bottleneck `kauditd` dan Kernel Panic pada High-Throughput System
Pada node worker Kubernetes bare-metal dengan beban ratusan container yang melakukan spawn process sangat cepat, sistem tiba-tiba mengalami soft-lockup/kernel panic. Konfigurasi auditd terakhir mengaktifkan CIS Level 2 rule dengan opsi:
```
-f 2
-b 8192
--backlog_wait_time 60000
```
Analisis apa yang terjadi pada antrean ring buffer kernel `kauditd` ketika userspace daemon `auditd` tersaturasi. Jelaskan makna fatal dari flag `-f 2` (panic flag) vs `-f 1` (printk flag), dan bagaimana Anda merancang *audit filter exclusion* (misalnya bypass system call audit untuk ephemeral processes milik konteks container runc/containerd) guna menstabilkan sistem.

### Soal 2.5: Disaster Recovery: Kloning UUID, Filesystem Superblock, dan Re-attaching GRUB
Anda melakukan bare-metal restore dari file arsip tar/raw image ke sebuah server target dengan model controller NVMe yang berbeda dari server sumber (migrasi dari `/dev/sda` bertipe SAS ke `/dev/nvme0n1`). Setelah restore selesai, sistem stuck di `grub rescue>`.
Uraikan langkah rekonstruksi sistem menggunakan live rescue USB/ISO:
1. Perbaikan mapping disk dan update `/etc/fstab` (relasi antara UUID filesystem, LVM VG/LV, dan WWID).
2. Mount bind pseudofilesystem (`/dev`, `/proc`, `/sys`, `/run`) ke dalam chroot target.
3. Regenerasi initramfs (Dracut/Update-Initramfs) agar memasukkan driver storage NVMe.
4. Re-install GRUB EFI bootloader via `grub2-install` dan pembaruan NVRAM boot entry via `efibootmgr`.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Skala Besar – "PXE Storm" & Network Exhaustion
* **Konteks:** Perusahaan Anda melakukan ekspansi data center dengan menyalakan 400 unit rack-mount server secara bersamaan. Arsitektur provisioning mengandalkan satu server TFTP sentral yang melayani boot image (`pxelinux.0` + initramfs 1.2 GB per node).
* **Masalah:** Dalam waktu 3 menit sejak seluruh server dinyalakan, switch Top-of-Rack (ToR) mengalami packet drops masif, CPU switch sentral melonjak ke 100%, 75% server mengalami timeout PXE boot (`TFTP open timeout`), dan server TFTP sentral crash akibat UDP socket buffer overflow. Lebih buruk lagi, proses DHCP lease di segmen tersebut menjadi tidak responsif untuk node lain yang sedang running.
* **Pertanyaan Diagnostik & Arsitektural:**
  1. Identifikasi secara teknis 3 kelemahan mendasar protokol TFTP (UDP lockstep acknowledgment, packet size limitation, statelessness) yang menjadi akar kegagalan skenario di atas.
  2. Rancang arsitektur baru yang skalabel untuk menangani 1.000 concurrent bare-metal provisioning tanpa membebani network layer. Jelaskan integrasi antara iPXE, DHCP Option 175 (iPXE detection), web server HTTP (seperti Nginx dengan caching dan HTTP/2), serta pemanfaatan multicast/BitTorrent atau P2P bootstrap layer jika diperlukan.

### Skenario B: Integritas Data & Concurrency – "Torn Snapshot" pada Async Storage Mirroring
* **Konteks:** Sebuah sistem Financial Core menggunakan database bare-metal Linux dengan transactional volume di atas LVM Thin Pools. Untuk memenuhi RPO < 5 menit, tim infrastruktur membuat cron job setiap 5 menit yang mengeksekusi LVM snapshot:
  ```bash
  lvcreate -s --name db_snap /dev/vg_data/lv_db
  dd if=/dev/vg_data/db_snap bs=16M | zstd | ssh backup-node "cat > /dr_storage/snap.raw.zst"
  lvremove -y /dev/vg_data/db_snap
  ```
* **Masalah:** Data center utama mengalami blackout mendadak akibat kegagalan UPS saat transfer snapshot ke-87 sedang berjalan. Tim DR mengalihkan traffic ke DR site dan mengekstrak snapshot ke-86 (yang sukses ditransfer). Namun, saat database engine di-start di node DR, database gagal start dengan error: `PANIC: could not locate a valid checkpoint record` dan `Corruption in block 48921: bad page header`.
* **Pertanyaan Diagnostik & Arsitektural:**
  1. Mengapa pembuatan LVM snapshot secara native tanpa interaksi dengan kernel filesystem layer (`fsfreeze`) dan database buffer pool menghasilkan state *inconsistent* atau *torn page*, bukan *application-consistent*?
  2. Rekonstruksi skrip backup DR tersebut agar bersifat *application-consistent* (menggunakan locking/quiesce mechanism seperti PostgreSQL `pg_backup_start()`, `sync`, dan `fsfreeze -f`).
  3. Jelaskan risiko read/write load yang timbul pada metadata LVM saat volume target sedang menerima disk I/O tinggi, dan mengapa `dd` secara langsung dari live logical volume berisiko tinggi terhadap race condition.

### Skenario C: Trade-off Arsitektur – Compliance Hardening vs Ultra Low-Latency Production
* **Konteks:** Perusahaan fintech mengharuskan seluruh sistem di bawah naungannya meraih kepatuhan **CIS Linux Level 2 Benchmark** demi memenuhi regulasi PCI-DSS dan ISO 27001. Tim SecOps menerapkan Ansible CIS Role secara seragam pada seluruh cluster, termasuk pada cluster transaksi berkecepatan tinggi (*Ultra Low-Latency Trading Platform* berbasis C++ dan Kafka).
* **Masalah:** Sesaat setelah playbook selesai:
  1. Latency p99 transaksi melonjak dari 15 mikrodetik menjadi 450 mikrodetik.
  2. Throughput Kafka broker anjlok hingga 50%.
  3. Compiler build internal dan beberapa daemon terhenti karena `/tmp` dipasang flag `noexec`, `/dev/shm` dipasang `noexec`, dan CPU governor di-force ke parameter default tertentu.
  4. Aturan auditd CIS L2 yang memonitor semua system call eksekusi file (`-S execve,execveat`) dan access control (`-S chmod,chown`) membuat load CPU sistem melonjak padahal utilization aplikasi rendah.
* **Pertanyaan Diagnostik & Arsitektural:**
  1. Bedah trade-off keamanan vs performa pada konfigurasi auditd, SELinux enforcing, dan mitigasi kernel (seperti `spectre_v2`, `pti`, `spec_store_bypass_disable` yang dipaksa aktif oleh hardening baseline).
  2. Rancang strategi exception handling dan segregasi level compliance: Komponen CIS L2 mana yang harus di-tuning atau digantikan (misal: beralih dari traditional `auditd` syscall trapping ke eBPF-based low-overhead auditing seperti Tetragon atau Tracee) agar SLA latency mikrodetik tetap terpenuhi tanpa melanggar prinsip fundamental compliance?

---

## 4. Chapter Challenge

### Tantangan Praktis: Zero-Touch Automated Bare-Metal Provisioning Pipeline dengan CIS Level 1 Baseline & Crash-Consistent DR Automation

#### A. Deskripsi Masalah
Organisasi Anda membutuhkan pipeline provisioning bare-metal yang sepenuhnya otomatis (*Zero-Touch*). Server baru yang dihubungkan ke kabel power dan LAN data center harus dapat mem-boot dirinya sendiri, mempartisi storage sesuai standar CIS, menginstal OS Linux enterprise (AlmaLinux/Rocky Linux 9 atau Ubuntu 22.04 LTS), menerapkan profil CIS Level 1 Benchmark secara otomatis, dan mendaftarkan dirinya ke cluster backup DR tanpa ada intervensi manusia (keyboard/monitor manual).

#### B. Spesifikasi Kebutuhan Teknis

1. **Network Boot Infrastructure (PXE/iPXE Stage):**
   * Konfigurasikan DHCP server (dnsmasq atau ISC-DHCP) yang mampu mendeteksi arsitektur client (UEFI x86_64 via DHCP Option 93/Client System Architecture).
   * Implementasikan chainloading dari PXE bawaan firmware ke **iPXE**, yang kemudian mengambil kernel (`vmlinuz`) dan `initrd.img` melalui protokol **HTTP** (bukan TFTP) untuk kecepatan loading.

2. **Automated Kickstart / Declarative Installer:**
   * Susun file konfigurasi otomatis (Kickstart `.ks` atau Cloud-init / Ubuntu Autoinstall `user-data`).
   * Skema partisi wajib menggunakan LVM dan memenuhi kriteria CIS Benchmark:
     * `/boot` (Minimal 1GB, non-LVM, flag `nodev,nosuid`)
     * `/` (Root LVM)
     * `/home` (LVM, mount option: `nodev,nosuid`)
     * `/tmp` (LVM terpisah, mount option: `nodev,nosuid,noexec`)
     * `/var` (LVM)
     * `/var/tmp` (LVM terpisah atau bind mount ke `/tmp`, mount option: `nodev,nosuid,noexec`)
     * `/var/log` (LVM terpisah, mount option: `nodev,nosuid,noexec`)
     * `/var/log/audit` (LVM terpisah, mount option: `nodev,nosuid,noexec`)
     * `/dev/shm` (tmpfs, mount option: `nodev,nosuid,noexec`)

3. **CIS Level 1 Post-Install Hardening Layer:**
   * Script post-installation harus mengotomasi minimal hal berikut secara idempoten:
     * Disable filesystem legacy (`cramfs`, `freevxfs`, `jffs2`, `hfs`, `hfsplus`, `squashfs`, `udf`) via `/etc/modprobe.d/`.
     * Kernel network parameters via `/etc/sysctl.d/99-cis.conf` (disable IP forwarding, ICMP redirects, source routing, enable reverse path filtering/rp_filter, TCP SYN cookies).
     * SSH Hardening (`PermitRootLogin no`, `Protocol 2`, `ClientAliveInterval 300`, `MaxAuthTries 3`, disabling weak ciphers).
     * Rule auditd komprehensif pada `/etc/audit/rules.d/audit.rules` untuk monitoring perubahan waktu sistem, modifikasi user/group identity, perubahan konfigurasi jaringan, dan MAC policy SELinux/AppArmor.

4. **Automated Bare-Metal Recovery Hook:**
   * Rancang sebuah script disaster recovery terintegrasi (`/usr/local/sbin/bm-dr-backup.sh`) yang dijalankan terjadwal:
     * Menggunakan snapshot level block/filesystem yang atomik.
     * Meng-export partition table (`sfdisk -d` atau `sgdisk --backup`).
     * Menyimpan LVM metadata archive (`vgcfgbackup`).
     * Mentransfer backup metadata dan payload yang terenkripsi dan terkompresi ke remote storage node.

#### C. Batasan Implementasi (Constraints)
* **Zero Intervention:** Proses instalasi dari cold power-on hingga OS boot pertama harus 100% tanpa menekan tombol keyboard apapun di host target.
* **Boot Time:** Tahap loading kernel dan initramfs dari network ke target RAM via iPXE HTTP tidak boleh lebih dari 30 detik pada network 1Gbps.
* **Compliance Verification:** Skor verifikasi post-install menggunakan tool audit otomatis (OpenSCAP / `oscap eval`) harus mencapai nilai minimal **90% compliance** untuk profil CIS Level 1 OS terkait.
* **Safety Lockout:** Hardening SSH dan user permissions tidak boleh mengunci akses remote berbasis SSH Public Key yang telah ditentukan di pipeline.

#### D. Expected Output & Deliverables
1. **Repository Kode:**
   * File konfigurasi DHCP/iPXE bootstrap (`ipxe.efi`, boot script embedded).
   * File installer otomatis (`kickstart.ks` atau `user-data`).
   * File konfigurasi sysctl, auditd rules, dan modprobe disablement.
   * Bash script `/usr/local/sbin/bm-dr-backup.sh`.
2. **Execution Log & Validation Report:**
   * Log proses PXE network fetch yang menunjukkan HTTP transfer.
   * Screenshot/Log `lsblk` dan `findmnt` yang membuktikan pemisahan mount point dan implementasi mount options (`noexec,nodev,nosuid`).
   * Laporan HTML/XML hasil evaluasi OpenSCAP (`oscap xccdf eval --profile ...`) yang membuktikan compliance score >= 90%.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis Anda dalam mengelola infrastruktur bare-metal, kepatuhan keamanan enterprise, dan arsitektur pemulihan bencana.

### Saya harus memahami:
- [ ] State machine dari Network Boot: UEFI -> PXE -> DHCP Handshake -> TFTP stage-1 -> iPXE stage-2 -> HTTP payload retrieval -> Kernel exec.
- [ ] Mekanisme kerja declarative bare-metal provisioning (Anaconda Kickstart, Cloud-init NoCloud/Metal-as-a-Service architecture).
- [ ] Perbedaan fundamental arsitektur dan ancaman antara CIS Benchmark Level 1 (operational security baseline) dan Level 2 (high-security defense-in-depth).
- [ ] Dampak kernel parameters `sysctl` terhadap performa network stack (misal: syncookies, rp_filter, tcp_timestamps, somaxconn).
- [ ] Mekanisme kernel audit logging (`kauditd`, Netlink protocol) dan penanganan audit queue buffer exhaustion.
- [ ] Prinsip *Crash Consistency* vs *Application Consistency* dalam konteks block-level storage snapshot dan filesystem journal integrity.
- [ ] Struktur direktori UEFI NVRAM boot variables (`efibootmgr`) dan hubungannya dengan EFI System Partition (ESP).

### Saya tidak perlu menghafal:
- [ ] Ratusan baris aturan syntax unik dari modul file `/etc/audit/rules.d/audit.rules` secara persis (Anda cukup memahami format filtering: arch, syscall name, action, list, filter flag `-F`, dan audit key `-k`).
- [ ] Daftar kode integer untuk seluruh DHCP Options dari RFC (cukup pahami fungsi Options 66, 67, dan 175).
- [ ] Nilai hash OID kriptografi pada x509 certificates yang digunakan oleh UEFI Secure Boot database.

### Saya harus bisa melakukan:
- [ ] Membangun dan mengonfigurasi TFTP, iPXE, dan HTTP server terintegrasi untuk melayani netboot Linux secara reliabel.
- [ ] Menulis Kickstart atau Cloud-init declarative recipe yang mempartisi LVM secara dinamis dan sesuai standar CIS.
- [ ] Mengonfigurasi dan memvalidasi mount options (`noexec`, `nosuid`, `nodev`) pada direktori volatile dan shared memory tanpa merusak runtime environment (systemd, JVM, Python).
- [ ] Mengoperasikan `ausearch` dan `aureport` untuk mendeteksi anomali akses sistem serta melakukan troubleshooting AVC Denials SELinux.
- [ ] Melakukan profiling dan audit compliance otomatis menggunakan OpenSCAP CLI (`oscap`).
- [ ] Melakukan prosedur Disaster Recovery "bare-metal rescue": Boot ke live environment, mount rootfs rusak, chroot, install bootloader ulang, fix `/etc/fstab`, dan regenerasi dynamic initramfs.