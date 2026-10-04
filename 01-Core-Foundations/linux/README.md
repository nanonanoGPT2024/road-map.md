# Linux Systems Engineering & Kernel Internals: Enterprise Architecture Manual

Selamat datang di silabus kurikulum komprehensif **Linux Systems Engineering & Kernel Internals**. Kurikulum ini dirancang berdasarkan standar industri kelas enterprise dan peta jalan resmi [roadmap.sh/linux](https://roadmap.sh/linux), mentransformasikan pemahaman konseptual dasar menjadi keahlian rekayasa sistem Linux tingkat lanjut (*production-grade*).

---

## 1. Course Overview & Mindset

### Filosofi Rekayasa Sistem
Dalam lanskap infrastruktur modern, Linux bukan sekadar sistem operasi; Linux adalah substrat fundamental tempat seluruh ekosistem komputasi awan (*cloud*), kontainerisasi, database berskala masif, dan sistem terdistribusi dijalankan. Menguasai Linux di tingkat *production-grade* menuntut pergeseran paradigma dari "pengguna utilitas baris perintah" menjadi "rekayasawan yang memahami interaksi perangkat keras, kernel, dan ruang pengguna (*user space*)".

```
+-----------------------------------------------------------------------+
| User Space: Applications, CLI Tools, Daemons, Shared Libraries (glibc)|
+-----------------------------------------------------------------------+
                                  |
               System Call Interface (syscalls: POSIX)
                                  v
+-----------------------------------------------------------------------+
| Linux Kernel: Process Management, Memory (VMM), VFS, Network Stack    |
+-----------------------------------------------------------------------+
                                  |
                      Hardware Abstraction Layer
                                  v
+-----------------------------------------------------------------------+
| Hardware: CPU, RAM, Block Devices (NVMe/SSD), NIC, Peripherals        |
+-----------------------------------------------------------------------+
```

### Mental Model & Engineering Rigor
1. **Tidak Ada "Magic" di Ruang Pengguna**: Setiap operasi I/O, pembentukan koneksi soket, isolasi proses kontainer, hingga eksekusi thread berujung pada interupsi dan *system call* ke kernel. Anda harus mampu melacak setiap anomali hingga ke level abstraksi terdalam menggunakan alat observabilitas sistem (*profiling*, *tracing*, dan eBPF).
2. **Deterministic Over Convenience**: Otomasi dan administrasi Linux di lingkungan mission-critical mengutamakan prediktabilitas, idempotenitas, kontrol alokasi sumber daya (*cgroups v2*), dan prinsip hak akses minimal (*least privilege*).
3. **Observabilitas Berbasis Data, Bukan Spekulasi**: Mendiagnosis degradasi performa sistem (*I/O wait*, saturasi memori, TCP connection drops) dilakukan dengan metrik empiris kuantitatif (`/proc`, `/sys`, `perf`, `bcc/bpftrace`), bukan dengan *trial-and-error*.

---

## 2. Learning Roadmap

```
ROADMAP REKAYASA SISTEM LINUX ENTERPRISE
│
├── BAB 01: Arsitektur Kernel, Bootstrapping, dan Inisialisasi Sistem
│   ├── Kernel vs User Space, Monolithic vs Microkernel, dan VFS
│   ├── Siklus Booting: Dari UEFI/BIOS, GRUB2, Initramfs, hingga PID 1
│   └── Arsitektur Inisialisasi Modern: systemd Units, Targets, dan Cgroups
│
├── BAB 02: Manajemen Shell, Stream I/O, dan Otomasi Bash Lanjutan
│   ├── Manipulasi File Descriptor, POSIX Streams (0/1/2), dan IPC Pipe/FIFO
│   ├── Pemrosesan Teks Skala Besar: Regex, Sed, Awk, dan Utilitas Inti
│   └── Bash Scripting Defensive: Idempotenitas, Subshell, dan Error Trap
│
├── BAB 03: Virtual File System (VFS), Storage, dan Blok I/O
│   ├── Abstraksi VFS, Struktur Inode, Superblock, dan Dentry Cache
│   ├── Partisi, LVM (Logical Volume Manager), dan Thin-Provisioning
│   └── Performa File System Enterprise: Ext4, XFS, Btrfs, dan ZFS
│
├── BAB 04: Manajemen Proses, Penjadwalan (Scheduling), dan Threading
│   ├── Siklus Hidup Proses, Fork-Exec, Signal Handling, dan State Machine
│   ├── Penjadwal Kernel: Completely Fair Scheduler (CFS), Nice, dan RT
│   └── Isolasi Primitif: Namespaces (PID, Mount, Network) & Cgroups v2
│
├── BAB 05: Memori Virtual, Alokasi Halaman, dan Analisis Subsistem RAM
│   ├── Virtual Memory Architecture, MMU, Page Tables, dan TLB
│   ├── Manajemen Memori Kernel: Slab Allocator, Buddy System, dan Swap
│   └── Analisis OOM-Killer, Vmstat, Page Faults, dan Transparent HugePages
│
├── BAB 06: Jaringan Sistem Operasi, Arsitektur Socket, dan TCP/IP Stack
│   ├── Aliran Paket Kernel: Socket Buffer (sk_buff), Ring Buffer, dan NAPI
│   ├── Manajemen Rute, Network Namespaces, dan Utilitas iproute2 Lanjutan
│   └── Firewalling Tingkat Rendah: Transisi Iptables ke Nftables dan Conntrack
│
├── BAB 07: Tata Kelola Izin, Autentikasi PAM, dan Pengerasan Keamanan
│   ├── Model Akses POSIX DAC vs Linux Capabilities (CAP_SYS_ADMIN, dll.)
│   ├── Pluggable Authentication Modules (PAM) dan Integrasi SSSD
│   └── Mandatory Access Control (MAC): Arsitektur SELinux dan AppArmor
│
├── BAB 08: Logging Terpusat, Tracing Kernel, dan Observabilitas (eBPF)
│   ├── Arsitektur Logging: systemd-journald, rsyslog, dan Log Rotation
│   ├── Tracing Sistem Tradisional: strace, ltrace, lsof, dan Antarmuka /proc
│   └── Dynamic Tracing Modern: Linux perf, eBPF, BCC Tools, dan bpftrace
│
├── BAB 09: Manajemen Paket, Kompilasi Kernel, dan Pustaka Dinamis
│   ├── Packaging Internals: Ekosistem Dpkg/Apt dan RPM/Yum/Dnf
│   ├── Pustaka Bersama (Shared Libraries), glibc, Dynamic Linker (ld.so)
│   └── Kompilasi Kernel Kustom: Kconfig, DKMS, dan Modul Kernel (LKM)
│
└── BAB 10: Otomasi Bare-Metal, Hardening Standar CIS, dan Disaster Recovery
    ├── Otomasi Provisioning: Cloud-init, Preseed/Kickstart, dan PXE Booting
    ├── Sistem Pengerasan Produksi: CIS Linux Benchmark dan Auditd
    └── Backup Konsisten, Recovery Snapshot LVM, dan Prosedur Bencana
```

---

## 3. Navigasi Detail Kurikulum

### [BAB 01: Arsitektur Kernel, Bootstrapping, dan Inisialisasi Sistem](./bab-01-arsitektur-dan-bootstrapping/)
Menelusuri batasan arsitektur sistem operasi dari saat tegangan listrik mencapai motherboard hingga kontrol diserahkan sepenuhnya ke sistem manajemen layanan.
* [01. Arsitektur Kernel, System Calls, dan Ring Privilege](./bab-01-arsitektur-dan-bootstrapping/01-arsitektur-kernel-dan-ring-privilege.md)
* [02. Anatomi Bootstrapping: UEFI/BIOS, GRUB2, Initramfs, dan Kernel Handover](./bab-01-arsitektur-dan-bootstrapping/02-anatomi-bootstrapping-uefi-grub2-initramfs.md)
* [03. Manajemen Inisialisasi PID 1: systemd Units, Targets, dan Service Tracing](./bab-01-arsitektur-dan-bootstrapping/03-manajemen-inisialisasi-systemd.md)

### [BAB 02: Manajemen Shell, Stream I/O, dan Otomasi Bash Lanjutan](./bab-02-shell-io-dan-bash-lanjutan/)
Membangun fondasi otomasi deterministik tingkat tinggi menggunakan antarmuka shell dan manipulasi stream data Linux.
* [01. File Descriptors, Redirection, Named Pipes (FIFO), dan Sinyal IPC](./bab-02-shell-io-dan-bash-lanjutan/01-file-descriptors-piping-ipc.md)
* [02. Manipulasi Stream Berkecepatan Tinggi: Regex, AWK, dan Sed Internals](./bab-02-shell-io-dan-bash-lanjutan/02-manipulasi-stream-awk-sed.md)
* [03. Defensive Bash Architecture: Error Handling, Traps, Subshells, dan Profiling](./bab-02-shell-io-dan-bash-lanjutan/03-defensive-bash-architecture.md)

### [BAB 03: Virtual File System (VFS), Storage, dan Blok I/O](./bab-03-vfs-storage-dan-blok-io/)
Menelusuri bagaimana kernel merepresentasikan media fisik sebagai pohon direktori terpadu, mekanisme caching blok, dan manajemen volume elastis.
* [01. Anatomi VFS: Superblocks, Inodes, Dentries, dan I/O Schedulers](./bab-03-vfs-storage-dan-blok-io/01-anatomi-vfs-inode-dentry.md)
* [02. Manajemen Volume Logis: LVM Architecture, Thin Provisioning, dan Snapshotting](./bab-03-vfs-storage-dan-blok-io/02-manajemen-volume-logis-lvm.md)
* [03. Evaluasi Sistem Berkas Produksi: Ext4, XFS, Btrfs, dan ZFS Optimization](./bab-03-vfs-storage-dan-blok-io/03-evaluasi-sistem-berkas-enterprise.md)

### [BAB 04: Manajemen Proses, Penjadwalan (Scheduling), dan Threading](./bab-04-manajemen-proses-dan-penjadwalan/)
Memahami unit eksekusi terkecil sistem operasi, bagaimana waktu CPU dialokasikan, dan bagaimana isolasi proses dibangun.
* [01. Anatomi Proses: Process Control Block (task_struct), Fork-Exec, dan Threading](./bab-04-manajemen-proses-dan-penjadwalan/01-anatomi-proses-dan-lifecycle.md)
* [02. CPU Scheduling Deep-Dive: Completely Fair Scheduler (CFS), Nice, dan RT Priority](./bab-04-manajemen-proses-dan-penjadwalan/02-cfs-scheduler-dan-prioritas.md)
* [03. Pondasi Kontainerisasi: Linux Namespaces dan Control Groups (cgroups v2)](./bab-04-manajemen-proses-dan-penjadwalan/03-namespaces-dan-cgroups-v2.md)

### [BAB 05: Memori Virtual, Alokasi Halaman, dan Analisis Subsistem RAM](./bab-05-memori-virtual-dan-alokasi-ram/)
Mengeksplorasi virtual memory, paginasi hierarkis, subsistem kernel slab, dan penanganan kondisi kehabisan memori.
* [01. Virtual Memory Architecture: Paging, TLB, Page Faults, dan MMU](./bab-05-memori-virtual-dan-alokasi-ram/01-virtual-memory-dan-mmu.md)
* [02. Kernel Allocators: Buddy Allocator, Slab/Slub/Slob, dan Caching Engine](./bab-05-memori-virtual-dan-alokasi-ram/02-kernel-allocator-dan-caching.md)
* [03. Analisis Performa Memori: Swap Management, vmstat, dan OOM-Killer Tuning](./bab-05-memori-virtual-dan-alokasi-ram/03-swap-tuning-dan-oom-killer.md)

### [BAB 06: Jaringan Sistem Operasi, Arsitektur Socket, dan TCP/IP Stack](./bab-06-jaringan-socket-dan-tcp-stack/)
Menganalisis siklus hidup paket jaringan dari Network Interface Card (NIC), alur kernel TCP/IP, hingga ruang soket aplikasi.
* [01. Anatomi Perjalanan Paket Jaringan: Ring Buffer, sk_buff, NAPI, dan Driver Queue](./bab-06-jaringan-socket-dan-tcp-stack/01-anatomi-perjalanan-paket-dan-skbuff.md)
* [02. Manajemen Routing Enterprise: iproute2, Netfilter Framework, dan nftables](./bab-06-jaringan-socket-dan-tcp-stack/02-iproute2-netfilter-dan-nftables.md)
* [03. Kernel TCP Tuning: TCP Buffers, Congestion Control (BBR/Cubic), dan Sysctl Profiling](./bab-06-jaringan-socket-dan-tcp-stack/03-kernel-tcp-tuning-dan-sysctl.md)

### [BAB 07: Tata Kelola Izin, Autentikasi PAM, dan Pengerasan Keamanan](./bab-07-keamanan-pam-dan-mac/)
Membangun benteng pertahanan berbasis kernel yang ketat melalui perizinan diskresioner, kapabilitas modular, dan kontrol akses wajib.
* [01. Hak Akses Lanjutan: POSIX ACLs, SUID/SGID/Sticky, dan Linux Capabilities](./bab-07-keamanan-pam-dan-mac/01-posix-acls-dan-linux-capabilities.md)
* [02. Ekosistem Autentikasi: PAM (Pluggable Authentication Modules) dan SSSD](./bab-07-keamanan-pam-dan-mac/02-pam-architecture-dan-sssd.md)
* [03. Mandatory Access Control (MAC): Implementasi Kebijakan SELinux dan AppArmor](./bab-07-keamanan-pam-dan-mac/03-selinux-dan-apparmor-enforcement.md)

### [BAB 08: Logging Terpusat, Tracing Kernel, dan Observabilitas (eBPF)](./bab-08-logging-tracing-dan-ebpf/)
Mendiagnosis kendala performa sistem secara non-invasif menggunakan alat diagnostik sistem generasi terbaru.
* [01. Logging Subsystem: systemd-journald, Rsyslog Pipeline, dan Logrotate](./bab-08-logging-tracing-dan-ebpf/01-journald-rsyslog-dan-logrotate.md)
* [02. Tracing Tradisional: strace, ltrace, ftrace, dan Ekstraksi Metrik /proc & /sys](./bab-08-logging-tracing-dan-ebpf/02-strace-ftrace-dan-pseudo-filesystems.md)
* [03. Observabilitas Modern: Linux perf Subsystem, BCC Tools, dan bpftrace](./bab-08-logging-tracing-dan-ebpf/03-perf-bcc-tools-dan-ebpf.md)

### [BAB 09: Manajemen Paket, Kompilasi Kernel, dan Pustaka Dinamis](./bab-09-package-management-dan-kernel-compilation/)
Mengelola siklus hidup perangkat lunak dari biner sistem, manajemen pustaka dinamis, hingga kompilasi kernel kustom dari kode sumber.
* [01. Manajemen Paket Tingkat Rendah: Arsitektur Internal DEB (dpkg) dan RPM (rpmdb)](./bab-09-package-management-dan-kernel-compilation/01-manajemen-paket-deb-dan-rpm.md)
* [02. Pustaka Dinamis: Shared Objects (.so), Dynamic Linker (ld.so), dan ABI Compatibility](./bab-09-package-management-dan-kernel-compilation/02-shared-libraries-ld-dan-glibc.md)
* [03. Kompilasi Kernel Kustom: Analisis Kconfig, Modul Kernel (LKM), dan DKMS](./bab-09-package-management-dan-kernel-compilation/03-kompilasi-kernel-dan-dkms.md)

### [BAB 10: Otomasi Bare-Metal, Hardening Standar CIS, dan Disaster Recovery](./bab-10-otomasi-hardening-dan-dr/)
Menghubungkan seluruh domain keahlian untuk mengelola armada server Linux bare-metal secara otomatis, aman, dan tahan bencana.
* [01. Unattended Bare-Metal Bootstrapping: PXE, iPXE, DHCP/TFTP, dan Cloud-init](./bab-10-otomasi-hardening-dan-dr/01-unattended-bootstrapping-pxe-cloudinit.md)
* [02. Enterprise Hardening: Auditd Subsystem dan Implementasi CIS Benchmark Level 2](./bab-10-otomasi-hardening-dan-dr/02-hardening-cis-benchmark-dan-auditd.md)
* [03. Strategi Disaster Recovery: Snapshot Orquestration, Disaster Recovery Backup, dan Kexec](./bab-10-otomasi-hardening-dan-dr/03-disaster-recovery-dan-kexec.md)

---

## 4. Spesifikasi Capstone Project Enterprise

### Project Title:
**Mission-Critical High-Availability Storage & Application Node: Hardened Bare-Metal Deployment Berbasis eBPF Observability, LVM Thin-Pool, dan CIS Benchmark Compliance**

```
+-----------------------------------------------------------------------------------+
|                           EDGE FIREWALL & INGRESS                                 |
|          nftables Stateful Filtering + Rate Limiting via SYN-Cookies              |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                        BARE-METAL HOST LINUX INSTANCE                             |
|  +-----------------------------------------------------------------------------+  |
|  | KERNEL LAYER (Custom 6.x Tuning via sysctl):                                |  |
|  | - TCP BBR Congestion Control, Buffer Tuning                                 |  |
|  | - eBPF Tracing Agents (BCC/bpftrace) monitoring I/O Latency                 |  |
|  | - Lockdown Mode Active, SELinux Enforcing (Targeted Policy)                 |  |
|  +-----------------------------------------------------------------------------+  |
|                                        │                                          |
|  +-------------------------------------+-------------------------------------+    |
|  | STORAGE SUBSYSTEM                   | RUNTIME SUBSYSTEM (cgroups v2)      |    |
|  | - NVMe Device (/dev/nvme0n1)        | - Microservice Daemons (systemd)    |    |
|  | - LVM Thin-Pool (Overprovisioned)   | - Non-root privileged capabilities  |    |
|  | - Encrypted LUKS Volume             | - Memory/CPU Quota Isolation        |    |
|  | - XFS File System (d_type enabled)  | - Custom PAM Authentication Module  |    |
|  +-------------------------------------+-------------------------------------+    |
|                                        │                                          |
|  +-----------------------------------------------------------------------------+  |
|  | SECURITY & AUDIT LOGGING ENGINE                                             |  |
|  | - Auditd Rules (Tracking syscall: execve, openat, ptrace)                   |  |
|  | - systemd-journald -> Persistent Forwarding -> Rsyslog Encryption           |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### Objektif Proyek
Membangun, mengamankan, mengonfigurasi, dan memvalidasi satu set sistem Linux *bare-metal* yang dipersiapkan untuk beban kerja kritis berkinerja tinggi. Anda akan bertindak sebagai *Principal Systems Architect* yang bertanggung jawab penuh terhadap integritas *operating system layer*.

### Ruang Lingkup Deliverable
1. **Automated Provisioning & Filesystem Architecture**:
   * Konfigurasi sistem penyimpanan menggunakan **LVM Thin-Provisioning** dengan alokasi *auto-extend* untuk mencegah *disk exhaustion*.
   * Partisi data diformat menggunakan file system **XFS** dengan opsi mount performa (`noatime`, `nodiratime`, `logbufs=8`) dan kuota proyek diaktifkan.
2. **Kernel Parameter Tuning & Network Optimization**:
   * Tuning stack jaringan TCP/IP via `/etc/sysctl.d/99-latency-tuning.conf`:
     * Algoritma *congestion control* diubah ke **BBR**.
     * Peningkatan alokasi memori buffer soket TCP (`rmem_max`, `wmem_max`).
     * Proteksi DoS (*SYN cookies*, penonaktifan *ICMP redirects*).
3. **Keamanan Berlapis (Defense-in-Depth)**:
   * Penegakan konfigurasi **SELinux** ke tingkat `Enforcing` dengan kebijakan kustom (*custom policy module*) untuk daemon internal.
   * Implementasi **Linux Capabilities**: Memangkas penggunaan *superuser* (`root`) pada aplikasi latar belakang, hanya menyematkan `CAP_NET_BIND_SERVICE` dan `CAP_SYS_RESOURCE`.
   * Penulisan rule **Auditd** kustom untuk mencatat eksekusi biner mencurigakan dan perubahan pada file konfigurasi `/etc/pam.d/` dan `/etc/sudoers`.
   * Penguatan sistem pertahanan menggunakan **nftables** dengan arsitektur *stateful firewall*.
4. **Sub-sistem Observabilitas & Deteksi Masalah (eBPF)**:
   * Skrip otomatisasi berbasis **bpftrace** atau pustaka **BCC** untuk melacak latensi *Block I/O* per volume logis secara *real-time*.
   * Skrip deteksi anomali kegagalan koneksi TCP (*dropped syn packets*) langsung pada level antarmuka soket kernel.
5. **Rencana Pemulihan Bencana & Validasi**:
   * Skrip otomasi snapshot volume LVM sebelum patching sistem secara terpadu.
   * Laporan validasi kepatuhan sistem terhadap benchmark **CIS Linux Level 2** dengan skor kepatuhan minimal 90%.

### Kriteria Kelulusan Capstone
* Kernel Linux beroperasi stabil tanpa ada *kernel panic* atau *soft-lockup warnings* pada `dmesg`.
* Auditd berhasil merekam dan mengelompokkan setiap perubahan konfigurasi sensitif.
* Seluruh kustomisasi parameter kernel diterapkan secara deterministik dan bertahan setelah reboot (*persistent across reboots*).
* Skrip tracing eBPF dapat mengekstraksi metrik sistem tanpa menyebabkan lonjakan penggunaan CPU di atas 1%.