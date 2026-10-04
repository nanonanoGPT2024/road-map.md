# BAB 01: Quiz, Challenge, & Knowledge Check
**Arsitektur Kernel, Bootstrapping, dan Inisialisasi Sistem**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Transisi Privilege Rings dan Hardware Context Switch
Jelaskan secara presisi arsitektur pemisahan *Ring 0 (Supervisor Mode)* dan *Ring 3 (User Mode)* pada arsitektur x86_64. Apa yang terjadi pada level CPU register (`MSR_LSTAR`, `RSP`, `SS`, dan `RIP`) saat sebuah proses mengeksekusi instruksi `syscall` untuk membaca I/O? Mengapa transisi ini memiliki penalti performa (*overhead*), dan bagaimana kernel Linux memitigasinya menggunakan mekanisme seperti *Virtual Dynamic Shared Object* (vDSO)?

### Soal 1.2: Monolithic Modular vs. Microkernel Trade-off
Secara taksonomi, Linux adalah *Monolithic Kernel*, namun menggunakan mekanisme *Loadable Kernel Modules* (LKM). Analisis perbedaan mendasar antara model ini dengan *Microkernel* (misalnya seL4 atau Mach) dalam hal:
1. *Memory address space isolation* antar subsistem (VFS, Network Stack, IPC).
2. Mekanisme penanganan kegagalan (*fault tolerance*) jika driver controller NVMe mengalami *null pointer dereference*.
3. Latensi pertukaran pesan antarkomponen (*context switching* vs *direct function calling*).

### Soal 1.3: Dekompresi Kernel dan Transisi CPU Execution Modes
Uraikan fase bootstrapping awal sejak *bootloader* menyerahkan kontrol eksekusi ke artefak biner kernel (`vmlinuz`). Bagaimana CPU bertransisi dari *Real Mode* (16-bit) atau *Protected Mode* (32-bit) menuju *Long Mode* (64-bit), kapan kode *in-place decompression* (`piggy.o` via decompressor stub) dieksekusi, dan pada titik mana *page table paging* (level-4 atau level-5) diaktifkan sebelum fungsi `start_kernel()` diinisialisasi?

### Soal 1.4: Justifikasi Arsitektural Initramfs/Early Userspace
Mengapa arsitektur modern Linux tidak lagi membiarkan kernel langsung me-*mount* *root filesystem* (`/dev/sda1` atau `/dev/nvme0n1p1`) secara statis via parameter `root=` tanpa perantara *initial ramdisk/ramfs* (`initramfs`)? Sebutkan minimal tiga kasus kompleks pada *enterprise storage* (misalnya DM-Crypt/LUKS, Software RAID/MDADM, Multi-path SAN, atau Network Boot iSCSI) yang secara deterministik mewajibkan keberadaan fase *early userspace* berbasis `tmpfs` dan instruksi `switch_root`.

### Soal 1.5: Paradigma PID 1: SysVinit vs. Systemd Architecture
Bandingkan arsitektur eksekusi `sysvinit` (berbasis sequential shell scripts) dengan `systemd` (berbasis declarative dependency graph dan socket-based activation). Bagaimana `systemd` memanfaatkan fitur kernel modern Linux—khususnya Control Groups (cgroups v2), `epoll`, autofs, dan file descriptor passing—untuk mencapai paralelisasi booting tanpa memicu *race condition* antar dependensi service?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Akar Masalah Kernel Panic "VFS: Unable to mount root fs"
Sebuah server bare-metal mengalami *kernel panic* sesaat setelah *upgrade* kernel dengan pesan kesalahan:
```text
[    2.104512] Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)
[    2.105891] CPU: 0 PID: 1 Comm: swapper/0 Not tainted 6.6.0-enterprise #1
[    2.106720] Call Trace:
[    2.107115]  dump_stack_lvl+0x48/0x70
[    2.107621]  panic+0x328/0x360
[    2.108032]  mount_block_root+0x1a4/0x230
[    2.108571]  mount_root+0x108/0x140
```
Tuliskan metodologi diagnostik terstruktur untuk membedakan apakah anomali ini disebabkan oleh:
1. Driver controller disk (misal: `megaraid_sas` atau `nvme`) terkompilasi sebagai modul (`M`) tetapi hilang dari `initramfs`.
2. Mismatch parameter `root=UUID=...` pada konfigurasi GRUB akibat perubahan skema partisi/UUID.
3. Kerusakan *initramfs image* itu sendiri atau kegagalan parsing parameter `initrd`.
Sertakan perintah penyelamatan yang dapat diinjeksikan melalui *GRUB interactive prompt*.

### Soal 2.2: Mekanisme System Crash Dump (Kdump/Kexec)
Jelaskan alur teknis ketika terjadi kondisi fatal pada kernel hingga mekanisme `kdump` berhasil mengamankan artefak memori:
1. Bagaimana kernel primer memesan sebagian memori fisik saat boot (`crashkernel=X` parameter)?
2. Bagaimana instruksi `kexec` mem-booting kernel sekunder (*capture kernel*) tanpa melalui reset hardware BIOS/UEFI?
3. Mengapa *capture kernel* wajib menggunakan driver perangkat I/O yang terisolasi dan tidak boleh bergantung pada *state* driver kernel yang mengalami crash?

### Soal 2.3: Dependency Deadlock & Race Condition pada Systemd Units
Perhatikan skenario definisi unit systemd berikut:
* `storage-sync.service` memiliki konfigurasi: `Requires=network-online.target` dan `After=network.target`.
* `custom-network.service` (penyedia koneksi) memiliki konfigurasi: `Before=network-online.target` dan `Requires=storage-sync.service`.

Identifikasi apa yang terjadi pada *dependency solver* `systemd` saat kompilasi *Directed Acyclic Graph* (DAG). Bagaimana `systemd` mendeteksi *circular dependency*, unit mana yang kemungkinan besar akan di-*drop* secara otomatis, dan bagaimana parameter `Wants=`, `Requires=`, `BindsTo=`, serta `After=` seharusnya dikonstruksi secara atomik untuk mencegah *ordering cycle*?

### Soal 2.4: Dynamic Kernel Tainting dan Module Signature Enforcement
Jelaskan arti dari flag `Tainted: P           OE` pada kernel stack trace. Jika sebuah enterprise policy mewajibkan penolakan terhadap module kernel yang tidak terverifikasi:
1. Fitur kernel apa (`CONFIG_MODULE_SIG_*`) yang harus diaktifkan?
2. Bagaimana mekanisme interaksi antara UEFI *Secure Boot*, *Machine Owner Key* (MOK), dan *kernel keyring* (`.builtin_trusted_keys`) dalam memverifikasi tanda tangan kriptografis modul `.ko` sebelum fungsi `init_module()` dieksekusi?

### Soal 2.5: Isolasi Booting Menggunakan Target States dan Emergency Recovery
Jelaskan perbedaan deterministik antara modifikasi kernel command line:
* `systemd.unit=rescue.target`
* `systemd.unit=emergency.target`
* `init=/bin/bash` (atau `init=/bin/sh`)

Analisis kondisi status *virtual filesystem* (`/proc`, `/sys`, `/dev`), status mount `/` (*Read-Only* vs *Read-Write*), ketersediaan interaksi *daemon* PID 1, dan risiko keamanan/integritas data untuk masing-masing opsi saat melakukan perbaikan sistem.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Large-Scale Bare-Metal Fleet Reboot Freeze (Production Blackout)
* **Konteks:** Setelah pemadaman listrik total pada data center, 800 node bare-metal hypervisor yang menjalankan OpenStack/Ceph dinyalakan serentak via IPMI. Sebanyak 35% dari server tersebut gagal masuk ke sistem operasi dan berhenti pada *dracut emergency shell* dengan pesan *timeout waiting for device node*. Storage lokal menggunakan dual-NVMe hardware RAID controller.
* **Gejala Teknis:**
  * Konsol serial menampilkan: `dracut-initqueue[421]: Warning: dracut-initqueue timeout - starting timeout scripts`.
  * Saat masuk ke rescue shell, perintah `ls /dev/mapper/` hanya menunjukkan node loopback, namun setelah menunggu 3 menit dan menjalankan `udevadm trigger && udevadm settle`, device node array `/dev/mapper/rootvg-rootlv` langsung terdeteksi dan dapat di-mount manual.
* **Pertanyaan Diagnostik & Solusi:**
  1. Apa akar penyebab *asynchronous race condition* antara inisialisasi hardware controller NVMe yang lambat dan *default timeout* pada udev/dracut di fase early userspace?
  2. Parameter kernel dan konfigurasi `dracut` apa yang harus diubah pada template image deployment PXE/Golden Image untuk mengatasi latensi inisialisasi controller tersebut secara deterministik?
  3. Bagaimana strategi mitigasi penumpukan storm I/O ke metadata NVMe saat boot massal?

### Skenario B: Kernel Space Deadlock & Unkillable Process (State 'D') pasca Patching
* **Konteks:** Server database PostgreSQL mission-critical mengalami lonjakan *Load Average* mencapai 128 (pada server 32-core), namun pemakaian CPU utilitas berada di bawah 5%. Puluhan process PostgreSQL tidak dapat dimatikan bahkan dengan `kill -9`.
* **Gejala Teknis:**
  * Output `ps aux | grep ' D '` menunjukkan proses tertahan pada fungsi kernel.
  * Hasil `cat /proc/<PID>/stack` menampilkan:
    ```text
    [<0>] call_rwsem_down_read_failed+0x18/0x30
    [<0>] down_read+0x85/0x90
    [<0>] lookup_fast+0x62/0x240
    [<0>] path_openat+0x185/0x1030
    [<0>] do_filp_open+0xb2/0x160
    ...
    ```
  * Sistem baru saja diperbarui menggunakan modul pihak ketiga (misal: anti-virus/monitoring file integrity berbasis eBPF/LSM module lama yang di-compile via DKMS).
* **Pertanyaan Diagnostik & Solusi:**
  1. Jelaskan mengapa proses dalam state *Uninterruptible Sleep* (`D`) kebal terhadap sinyal `SIGKILL` (signal 9) dan bagaimana kaitannya dengan primitive locking kernel (`rwsem`, `mutex`) pada subsistem VFS.
  2. Bagaimana cara membuktikan secara pasti modul/driver mana yang memegang lock dan tidak pernah melepaskannya tanpa harus me-reboot mesin seketika?
  3. Rancang prosedur mitigasi untuk mengeluarkan sistem dari kondisi tersebut secara terkendali tanpa merusak konsistensi tabel database PostgreSQL yang belum tersinkronisasi (*dirty pages* di page cache).

### Skenario C: MicroVM Low-Latency Bootstrapping Optimization
* **Konteks:** Tim infrastruktur Cloud Native sedang merancang platform *Serverless Functions* menggunakan *microVM* (berbasis Firecracker / QEMU-KVM) yang ditargetkan memiliki cold-start latency < 15 milidetik dari inisiasi hingga *guest function* dieksekusi.
* **Gejala Teknis/Constraint:**
  * Penggunaan kernel standar enterprise distribution (misal: generic cloud kernel Ubuntu/RHEL) menghasilkan boot time rata-rata 1.2 detik.
  * Initramfs bawaan memakan waktu ~800ms hanya untuk parsing modul, udev settled, dan mounting root.
* **Pertanyaan Diagnostik & Solusi:**
  1. Arsitektur kernel stripping apa yang harus diterapkan? (Evaluasi: uncompressed binarized `vmlinux` vs compressed `vmlinuz`, monolitik *built-in drivers* vs loadable modules).
  2. Apakah `initramfs` masih dibutuhkan dalam arsitektur ini? Jika ditiadakan, bagaimana konfigurasi kernel command line (`root=/dev/vda`, `rootflags=...`, virtio-blk driver compile) disusun agar kernel langsung me-mount *rootfs* secara atomik?
  3. Bagaimana merancang *userspace init* (PID 1) khusus (misal berbasis biner tunggal Go/Rust/C) untuk menggantikan `systemd` guna memangkas *userspace initialization time* hingga mendekati target < 5 milidetik? Sebutkan *syscall* yang wajib dipanggil secara minimal oleh init pengganti tersebut.

---

## 4. Chapter Challenge
**Tantangan Praktis: Rekayasa Minimalist Bootstrapping Pipeline dari Kernel Mentah ke Isolated Shell**

### Deskripsi Masalah
Sebagai Principal Systems Architect, Anda diminta membuktikan pemahaman absolut mengenai batas pemisah (*boundary*) antara *Kernel Space* dan *User Space*. Anda harus membangun lingkungan boot minimalis yang dapat diverifikasi pada mesin virtual (menggunakan QEMU/KVM) tanpa menggunakan distribusi Linux yang ada, tanpa `systemd`, dan tanpa package manager.

### Kebutuhan & Spesifikasi Implementasi (Requirements)
1. **Kernel Compilation:**
   * Ambil *vanilla kernel source* (versi LTS terbaru).
   * Konfigurasi kernel (`make defconfig` atau `make menuconfig`) dengan menonaktifkan seluruh modul eksternal dan mengompilasi driver penting secara built-in (`CONFIG_DEVTMPFS=y`, `CONFIG_DEVTMPFS_MOUNT=y`, `CONFIG_BINFMT_ELF=y`, `CONFIG_VIRTIO_PCI=y`, `CONFIG_VIRTIO_BLK=y`, `CONFIG_EXT4_FS=y`).
   * Hasilkan biner kernel bootable (`arch/x86/boot/bzImage`).
2. **Minimalist PID 1 Init Binary:**
   * Tulis program C sederhana bernama `init.c` yang:
     1. Menampilkan teks: `[ENTERPRISE CORE] Userspace initialization successfully reached PID 1`.
     2. Men-setup *virtual filesystems* mendasar: me-mount `/proc` (procfs) dan `/sys` (sysfs).
     3. Mengimplementasikan loop penanganan sinyal (`sigaction`) dan fungsi `waitpid(-1, ...)` agar tidak menciptakan *zombie process* saat proses *child* terminasi.
     4. Menjalankan *interactive shell* (Busybox) yang terpasang pada serial terminal `/dev/console`.
   * Kompilasi program tersebut secara statis menggunakan `gcc -static -nostartfiles` atau `musl-gcc` untuk memastikan tidak ada dependensi terhadap dynamic linker/shared libraries (`ld-linux.so`).
3. **Initramfs Packaging:**
   * Konstruksikan struktur direktori: `/bin`, `/dev`, `/proc`, `/sys`, `/mnt`, `/etc`.
   * Integrasikan biner bidi-kompatibel (Busybox statik) dan file biner `init` yang telah Anda kompilasi pada root struktur initramfs (`/init`).
   * Bungkus struktur direktori tersebut menjadi arsip initramfs menggunakan format `cpio` yang dikompresi dengan `gzip`.
4. **Boot Execution & Verification:**
   * Jalankan lingkungan virtual via QEMU dengan mode *headless serial console* (`-nographic` / `-append "console=ttyS0"`).
   * Verifikasi bahwa eksekusi berlangsung mulus dari bootloader stub langsung menuju PID 1 tanpa terjadi *kernel panic*.

### Batasan (Constraints)
* Dilarang menggunakan utilitas pembantu distribusi otomatis seperti `dracut`, `mkinitcpio`, atau `update-initramfs`. Seluruh proses pack/unpack initramfs wajib menggunakan `cpio` dan `find`.
* Total ukuran image kernel + initramfs tidak boleh melebihi 15 MB.
* Sistem harus dapat dimatikan secara bersih (*clean shutdown*) menggunakan syscall `reboot(RB_POWER_OFF)` saat user mengetikkan `exit` pada shell tanpa memicu kernel panic: `Attempted to kill init!`.

### Expected Output
1. Log eksekusi booting lengkap yang ditangkap dari *serial port* console (`ttyS0`).
2. Output command `ps aux` dari dalam lingkungan QEMU yang membuktikan biner `init` berjalan tepat pada `PID 1`.
3. Validasi mount point dari `/proc/mounts` yang menunjukkan `devtmpfs`, `proc`, dan `sysfs` ter-mount dengan flags yang benar.
4. Total durasi boot dari eksekusi QEMU hingga prompt shell siap interaksi diukur menggunakan parameter `-enable-kvm` dengan waktu < 500 milidetik.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme pemisahan privilege x86_64: Ring 0 (Kernel Space) vs Ring 3 (User Space), fungsi instruksi `syscall`/`sysret`, dan pemanfaatan register `MSR_LSTAR`.
- [ ] Siklus hidup lengkap boot Linux: Firmware (UEFI/BIOS) $\rightarrow$ Bootloader (GRUB) $\rightarrow$ Kernel Setup Code $\rightarrow$ Protected/Long Mode Switch $\rightarrow$ `start_kernel()` $\rightarrow$ Early Userspace (`initramfs`) $\rightarrow$ Real Root Pivot (`pivot_root`/`switch_root`) $\rightarrow$ System Init (PID 1).
- [ ] Peran dan anatomi `initramfs`: Mengapa menggunakan `tmpfs` dan bukan `ramfs` lama/loop device, serta mengapa kernel modern menyerahkan discovery storage kompleks ke userspace.
- [ ] Logika Directed Acyclic Graph (DAG) pada systemd: Perbedaan mendasar blok dependensi `Requires=`, `Wants=`, `BindsTo=` dan blok ordering `Before=`, `After=`.
- [ ] Mekanisme kernel panic, oops, dan penanganan kernel taint: Membaca Call Trace, menafsirkan stack pointer, dan mengidentifikasi faulting instruction register.
- [ ] Konsep Memory Management Initialization: Transisi dari temporary page tables (fase dekompresi) ke paging definitif arsitektur kernel 64-bit.
- [ ] Penanganan sinyal khusus PID 1: Mengapa sinyal default seperti `SIGTERM` dan `SIGKILL` diabaikan oleh PID 1 kecuali jika explicit handler didefinisikan dalam kode sumber init.

### Saya tidak perlu menghafal:
- [ ] Nilai *hexadecimal offset* spesifik pada *Model-Specific Registers* (MSR) prosesor (misalnya nilai pasti register MSR hex untuk setiap varian CPU).
- [ ] Sintaks baris-per-baris dari script internal pembangun initramfs bawaan vendor (seperti `/usr/lib/dracut/modules.d/*`).
- [ ] Seluruh flag bitwise pada struktur kernel `tainted_mask` (cukup memahami flag kritikal seperti `P`, `F`, `O`, `E`).
- [ ] Seluruh variasi parameter kernel command line yang didefinisikan di `Documentation/admin-guide/kernel-parameters.txt`.

### Saya harus bisa melakukan:
- [ ] Mengonstruksi, membongkar (*unpack*), memodifikasi, dan mengemas ulang (*repack*) arsip `initramfs` berbasis `cpio` manual untuk debugging lingkungan *pre-mount*.
- [ ] Mengintervensi *bootloader* GRUB secara interaktif untuk memulihkan sistem yang rusak via parameter kernel command line (`init=/bin/sh`, `systemd.debug_shell=1`, `nomodeset`, `fsck.mode=force`).
- [ ] Menganalisis dan membaca stack trace dari log `dmesg` atau `/var/log/messages` saat terjadi *Kernel Oops* atau *Deadlock* (State `D`) untuk menentukan subsistem yang mengalami crash.
- [ ] Memetakan dependensi boot systemd menggunakan utilitas analisis: `systemd-analyze blame`, `systemd-analyze critical-chain`, dan `systemd-analyze plot`.
- [ ] Melakukan isolasi dan memecahkan loop dependensi sirkular (*circular dependency*) antar unit service pada systemd.
- [ ] Mengonfigurasi dan mengaktifkan konsol serial debugging (`console=ttyS0,115200n8`) untuk menangkap log sistem yang mengalami freeze sebelum sistem logging userspace (`systemd-journald`) aktif.