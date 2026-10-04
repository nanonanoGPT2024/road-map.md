# BAB 09: Quiz, Challenge, & Knowledge Check
**Manajemen Paket, Kompilasi Kernel, dan Pustaka Dinamis**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi Linking: Statis vs Dinamis dan Struktur ELF
Jelaskan perbedaan mendasar antara *static linking* dan *dynamic linking* dalam konteks struktur biner ELF (*Executable and Linkable Format*). Analisis secara mendalam peran seksi `.dynamic`, *Global Offset Table* (GOT), dan *Procedure Linkage Table* (PLT) dalam memfasilitasi *lazy binding* pada pustaka dinamis, serta jelaskan perbandingan *memory overhead* (*dirty pages* vs *shared clean pages*) ketika ribuan proses memuat pustaka yang sama.

### Soal 1.2: Siklus dan Hierarki Resolusi Dynamic Linker (`ld.so`)
Ketika sebuah program ELF dieksekusi melalui *system call* `execve()`, bagaimana kernel mentransfer kontrol ke *runtime dynamic linker* (`ld-linux.so`)? Uraikan hierarki preseden pencarian pustaka (*library search order*) yang digunakan oleh `ld.so`, mulai dari variabel *environment*, atribut biner (*hardcoded paths*), hingga konfigurasi sistem global dan direktori *fallback*.

### Soal 1.3: Mekanisme Transaksional dan Integritasi Manajer Paket
Bandingkan arsitektur tingkat rendah antara sistem manajemen paket berbasis Debian (`dpkg`/`APT`) dan Red Hat (`rpm`/`DNF`). Bagaimana manajer paket level rendah menjamin atomisitas dan konsistensi status (*state machine*) saat proses instalasi terinterupsi tiba-tiba (*power failure*)? Jelaskan peran basis data status (`/var/lib/dpkg/status` vs database SQLite/BDB RPM), *advisory locks*, dan mekanisme *rollback* scriptlet (`preinst`, `postinst`, `prerm`, `postrm`).

### Soal 1.4: Monolithic Kernel vs Loadable Kernel Modules (LKM)
Linux secara fundamental adalah *monolithic kernel*, namun mendukung *Loadable Kernel Modules* (LKM). Jelaskan bagaimana LKM dieksekusi dalam *address space* kernel tanpa isolasi memori (*ring 0*), bagaimana resolusi simbol kernel dilakukan via `EXPORT_SYMBOL()` dan `/proc/kallsyms`, serta apa risiko fatalitas sistem (*kernel panic*, *tainting*) jika modul yang dimuat mengalami *null pointer dereference* dibandingkan kegagalan pada proses *userspace*.

### Soal 1.5: Dekonstruksi Boot Stage: vmlinuz, initramfs, dan Transisi Rootfs
Jelaskan struktur fisik dan fungsi dari `vmlinuz` (arsitektur *self-extracting bzImage*) dan `initramfs` (arsitektur *cpio archive compressed*). Mengapa `initramfs` mutlak diperlukan pada sistem modern yang mengompilasi *storage controller* (NVMe/SATA/SCSI) dan *filesystem driver* (ext4/XFS) sebagai modul (`CONFIG_...=m`), dan bagaimana mekanisme *pivot root* (`switch_root`) menyerahkan kontrol ke *real root filesystem*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Resolusi Soname, ABI Incompatibility, dan Symbol Versioning
Sebuah aplikasi C++ dikompilasi menggunakan dependensi `libcrypto.so.1.1`. Saat di-*deploy* ke mesin target yang hanya memiliki `libcrypto.so.3`, aplikasi menolak berjalan dengan galat *relocation error*. Jelaskan konsep `SONAME`, *real name*, dan *linker name* dalam sistem penamaan symlink pustaka Linux. Bagaimana mekanisme *GNU Symbol Versioning* (misal: `memcpy@@GLIBC_2.14`) mencegah situasi *silent memory corruption* akibat ketidakcocokan ABI (*Application Binary Interface*)?

### Soal 2.2: Reduksi Attack Surface & Optimasi Kompilasi Kernel Kustom
Analisis perbedaan fungsional dan operasional antara target pembuatan konfigurasi kernel: `make defconfig`, `make allmodconfig`, `make allyesconfig`, dan `make localmodconfig`. Jika Anda bertugas menyusun kernel minimalis untuk infrastruktur *container host* atau *microVM* (misal: Firecracker), opsi subsistem kernel apa saja yang wajib dipangkas untuk meminimalkan *attack surface* dan waktu *boot*, serta apa konsekuensinya terhadap portabilitas perangkat keras?

### Soal 2.3: Metodologi Diagnostik Dependency Breakage
Sebuah biner kritis di lingkungan produksi gagal dieksekusi dan melempar pesan galat:
`error while loading shared libraries: libcustom_engine.so: cannot open shared object file: No such file or directory`.
Rancang alur kerja diagnostik sistematis menggunakan utilitas:
1. `ldd`
2. `readelf -d` (khususnya tag `RPATH` dan `RUNPATH`)
3. `strace` (fokus pada penelusuran *system call* `openat` pustaka)
4. Variabel lingkungan `LD_DEBUG=libs,bindings`
Jelaskan mengapa `ldd` berisiko dijalankan pada biner yang tidak dipercaya (*untrusted binary*) dan bagaimana `readelf` memitigasi risiko tersebut.

### Soal 2.4: Kerusakan Kritis /var/lib/dpkg dan Penanganan "Half-Installed"
Jelaskan skenario kegagalan saat sebuah paket sistem berada pada status `half-configured` atau `unpacked` akibat *scriptlet* `postinst` mengalami *infinite loop* atau *deadlock* saat *upgrade* massal. Bagaimana kernel/sistem operasi menangani *lock file* (`/var/lib/dpkg/lock-frontend`) jika proses induknya dihentikan dengan `SIGKILL`? Uraikan langkah recovery manual menggunakan kombinasi `dpkg --configure -a`, modifikasi berkas info skrip di `/var/lib/dpkg/info/`, dan manipulasi direktori status.

### Soal 2.5: Runtime Kernel Patching (Livepatching)
Jelaskan arsitektur teknis di balik Linux Kernel Livepatching (`CONFIG_LIVEPATCH`, misal: implementasi Ksplice, Kpatch, atau Canonical Livepatch). Bagaimana subsistem `ftrace` dan mekanisme *Reliable Stack Trace* dialokasikan untuk mengalihkan instruksi fungsi lama ke fungsi baru yang telah ditambal secara atomik tanpa memerlukan *reboot* sistem dan tanpa memicu inkonsistensi status eksekusi CPU (*semantic patching consistency*)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Fatal Upgrade glibc dan Kegagalan Shared Library di Ribuan Server
Sebuah skrip otomatisasi melakukan pembaruan dependensi dasar pada 5.000 instans server produksi secara *in-place*. Di tengah proses instalasi pustaka inti `glibc` (`libc6`), koneksi jaringan terputus dan proses pembaruan terhenti setelah berkas biner pustaka baru tersalin, tetapi sebelum *symlink* vital `/lib64/libc.so.6` diperbarui ke versi baru. Akibatnya:
- Hampir seluruh perintah sistem (`ls`, `cp`, `bash`, `ssh`, `python`, `apt`, `yum`) langsung mengalami kegagalan eksekusi dengan pesan:
  `libc.so.6: cannot open shared object file: No such file or directory`.
- Sesi SSH yang ada saat ini masih aktif, tetapi tidak dapat memanggil *binary fork* baru.

**Tugas Diagnostik & Mitigasi:**
1. Mengapa perintah bawaan *shell* seperti `echo` masih dapat berfungsi dalam sesi yang aktif, sedangkan utilitas umum langsung gagal?
2. Bagaimana Anda memulihkan *symlink* `/lib64/libc.so.6` secara deterministik jika perintah `ln` atau `sln` tidak bisa dieksekusi akibat hilangnya referensi `libc`? Tuliskan pemanfaatan mekanisme *direct dynamic linker execution* atau fitur internal shell (*built-in*) untuk mengatasi masalah ini.

### Skenario B: Race Condition dan Deadlock Database RPM pada Host Skala Besar
Di sebuah klaster komputasi performa tinggi, dua agen orkestrasi yang berjalan secara paralel (*Agent A* mengurus *vulnerability remediation*, *Agent B* mengurus *monitoring metric deployment*) mencoba mengeksekusi instalasi paket RPM secara bersamaan. Terjadi *race condition* yang memicu *hard deadlock* pada backend database Berkeley DB/SQLite (`/var/lib/rpm`). Operator lokal mencoba mengatasi masalah dengan mengeksekusi `kill -9` pada seluruh proses DNF/RPM yang sedang aktif. Dampaknya, setiap perintah `rpm` atau `dnf` berikutnya mengalami *hanging* permanen pada status I/O lock.

**Tugas Diagnostik & Mitigasi:**
1. Analisis mengapa `SIGKILL` pada proses manajer paket yang sedang memodifikasi backend database RPM menyebabkan kerusakan status *concurrency lock* (analisis *stale locks* dan *futex* status).
2. Tuliskan prosedur bedah pemulihan database RPM langkah-demi-langkah tanpa kehilangan metadata paket yang telah terpasang, termasuk verifikasi integritas paket (`rpm --rebuilddb`, verifikasi berkas `__db.00*`, dan manajemen POSIX mutex locks).

### Skenario C: Trade-off Arsitektur Kernel untuk Ultra-Low Latency Trading Engine
Tim infrastruktur ditugaskan mendesain sistem operasi untuk mesin eksekusi *Algorithmic High-Frequency Trading* (HFT). Latensi *network-to-userspace* harus berada di bawah sub-mikrodetik (*deterministic tail latency*). Tim terbelah menjadi dua pandangan:
- **Pendekatan 1:** Menggunakan *Generic Enterprise Distribution Kernel* bawaan vendor dengan tuning *runtime parameters* via `sysctl`, `tuned`, dan modul pihak ketiga.
- **Pendekatan 2:** Mengompilasi *Custom Monolithic Kernel* dari *vanilla source*, mematikan *modular driver support* (`CONFIG_MODULES=n`), menerapkan *Real-Time Preemption Patch* (`PREEMPT_RT`), dan melakukan *stripping* agresif terhadap subsistem kernel yang tidak digunakan.

**Tugas Evaluasi & Desain Arsitektur:**
1. Evaluasi *trade-off* mendalam dari kedua pendekatan tersebut dari perspektif:
   - *Deterministic Latency & Jitter* (interupsi CPU, *scheduler latency*, *timer granularity*).
   - *Attack Surface & Memory Footprint*.
   - *Operational Overhead* (pembaruan keamanan CVE, pemeliharaan jangka panjang, manajemen siklus hidup sistem operasi).
2. Parameter kompilasi kernel spesifik apa saja (misal: `CONFIG_HZ`, `CONFIG_PREEMPT_NONE`/`CONFIG_PREEMPT_RT`, `CONFIG_NO_HZ_FULL`, isolasi CPU) yang wajib diaktifkan atau dinonaktifkan pada Pendekatan 2 untuk meminimalkan *scheduling jitter* dan *cache eviction*?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Custom Kernel Minimalis, Debugging Library Hijacking, dan Automated System Recovery

#### Problem Statement
Anda berperan sebagai Lead Infrastructure Security Engineer. Anda menerima mandat untuk memvalidasi keamanan dan ketahanan layer fondasi Linux:
1. Mengompilasi kernel kustom yang terisolasi dan deterministik di dalam QEMU.
2. Melakukan audit dan intersepsi sistem terhadap panggilan pustaka dinamis menggunakan *shared library injection*.
3. Mensimulasikan dan menyelesaikan insiden bencana sistem (*broken runtime environment*) akibat manipulasi tautan pustaka dinamis level inti.

#### Requirements

1. **Kernel Compilation & Bootstrapping (Minimalist Appliance):**
   - Unduh kode sumber Linux Kernel LTS resmi terbaru.
   - Konfigurasi kernel dengan footprint minimal:
     - Aktifkan driver yang hanya dibutuhkan untuk *virtual machine* QEMU (`virtio`, `virtio_net`, `virtio_blk`, `serial console`).
     - Nonaktifkan seluruh dukungan *wireless*, *sound*, Bluetooth, dan arsitektur CPU selain x86_64.
     - Kompilasi menggunakan multi-threading optimal (`make -j$(nproc)`).
   - Buat `initramfs` berbasis BusyBox statis yang secara otomatis melakukan *mount* terhadap `/proc`, `/sys`, `/dev` dan menampilkan *custom prompt*.
   - Jalankan kernel dan initramfs tersebut menggunakan QEMU (`qemu-system-x86_64`) tanpa menggunakan virtual disk tambahan (gunakan *kernel direct boot*). Buktikan waktu *boot to prompt* di bawah 2 detik.

2. **Shared Library Security Auditing & Interception:**
   - Tulis sebuah pustaka bersama C kustom: `libaudit_intercept.so`.
   - Implementasikan fungsi intersepsi terhadap fungsi standar C `fopen()` atau `open()` menggunakan mekanisme `dlsym(RTLD_NEXT, "open")`.
   - Setiap kali biner sistem memanggil operasi pembukaan berkas, pustaka Anda harus mencatat (*logging*) jalur berkas yang diakses beserta UID proses pemanggil ke berkas `/tmp/secure_audit.log`.
   - Uji pustaka Anda menggunakan mekanisme `LD_PRELOAD` terhadap perintah dasar seperti `cat` atau `head`.
   - Konfigurasikan sistem agar pustaka ini dimuat secara global melalui file `/etc/ld.so.preload` dan buktikan bahwa seluruh proses *userspace* non-SUID terpantau. Jelaskan mengapa proteksi AT_SECURE menonaktifkan mekanisme ini pada biner SUID seperti `passwd` atau `sudo`.

3. **Disaster Recovery Simulation (Severed Dynamic Linker):**
   - Pada lingkungan pengujian terisolasi (VM/Container), simulasikan bencana dengan menghapus atau merusak symlink dynamic linker utama:
     ```bash
     rm /lib64/ld-linux-x86-64.so.2
     ```
   - Dalam kondisi di mana semua biner dinamis tidak dapat berjalan, pulihkan sistem menggunakan perintah kernel dynamic loader secara langsung atau pemanggilan biner statis alternatif. Tuliskan dokumentasi teknis langkah pemulihannya.

#### Constraints
- Semua kompilasi C harus menggunakan flag proteksi memori ketat: `-fstack-protector-strong -D_FORTIFY_SOURCE=2 -O2 -Wall -Werror -fPIC`.
- Kernel kompilasi kustom tidak boleh menghasilkan ukuran `bzImage` lebih besar dari 15 MB.
- Dilarang melakukan *hard reboot* VM saat melakukan tahapan pemulihan bencana dynamic linker.

#### Expected Output
1. Berkas artefak konfigurasi kernel: `.config` minimalis yang terverifikasi.
2. Skrip otomatisasi pembuatan initramfs berbasis BusyBox (`build_initramfs.sh`).
3. Berkas kode sumber C (`libaudit_intercept.c`) dan instruksi kompilasi Makefile.
4. Log output verifikasi QEMU yang membuktikan kernel kustom berhasil melakukan *handover* ke initramfs Busybox.
5. Log output `/tmp/secure_audit.log` yang merekam aktivitas sistem secara transparan.
6. Panduan runbook satu halaman untuk penanganan darurat hilangnya `/lib64/ld-linux-x86-64.so.2`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup lengkap eksekusi biner ELF, mulai dari pemanggilan `execve()`, pemuatan *dynamic linker* (`/lib64/ld-linux-x86-64.so.2`), alokasi memori segmen via `mmap()`, hingga penyerahan kendali ke fungsi `main()`.
- [ ] Peran dan mekanisme kerja internal *Global Offset Table* (GOT) dan *Procedure Linkage Table* (PLT) dalam memproses relokasi kode *Position Independent Code* (PIC).
- [ ] Algoritma dan hierarki pencarian pustaka dinamis oleh `ld.so`: `LD_PRELOAD` $\to$ `DT_RPATH` $\to$ `LD_LIBRARY_PATH` $\to$ `DT_RUNPATH` $\to$ `/etc/ld.so.cache` $\to$ *Trusted Default Paths* (`/lib64`, `/usr/lib64`).
- [ ] Implikasi keamanan dari flag `AT_SECURE` dan mekanisme pembatasan variabel lingkungan (`LD_PRELOAD`, `LD_LIBRARY_PATH`) pada biner berizin SUID/SGID.
- [ ] Struktur internal paket Debian (`.deb`: *ar archive* berisi `debian-binary`, `control.tar.gz`, `data.tar.gz`) dan paket RPM (`.rpm`: *lead*, *signature*, *header*, *cpio payload*).
- [ ] Perbedaan fundamental arsitektur kernel *Monolithic*, *Microkernel*, dan model *Loadable Kernel Modules* (LKM) pada Linux.
- [ ] Proses inisialisasi boot sistem Linux: integrasi antara Bootloader (GRUB), image kernel (`bzImage`), *initial ramdisk* (`initramfs`), dan transisi menuju `systemd` / PID 1 via `switch_root`.
- [ ] Tata kelola versi pustaka (Library ABI Versioning) melalui *Soname* dan *Symbol Versioning* untuk mencegah kerusakan dependensi antargenerasi pustaka.

### Saya tidak perlu menghafal:
- [ ] Seluruh opsi kompilasi konfigurasi kernel (ribuan parameter `CONFIG_*` pada file `.config`). Parameter ini cukup dicari menggunakan fitur penelusuran pada antarmuka `make menuconfig` (`/`).
- [ ] Nilai numerik konstan pada struktur header file ELF (seperti magic number hexadesimal `0x7f 'E' 'L' 'F'`) atau opcode x86 spesifik dari instruksi PLT stub.
- [ ] Format biner internal tingkat rendah dari database Berkeley DB atau SQLite yang digunakan oleh pustaka manajer paket.
- [ ] Flag baris perintah yang jarang digunakan pada utilitas `readelf`, `objdump`, atau `nm` (cukup menguasai flag fundamental seperti `-d`, `-h`, `-s`, `-t`).

### Saya harus bisa melakukan:
- [ ] Memeriksa dan memecah struktur dependensi biner ELF secara aman menggunakan `readelf -d` dan `objdump -p` tanpa risiko eksekusi kode acak.
- [ ] Mengonfigurasi, mengompilasi, dan memvalidasi Linux Kernel kustom dari sumber resmi (*mainline/stable*) yang siap di-boot menggunakan hypervisor QEMU atau perangkat keras fisik.
- [ ] Menginspeksi kegagalan resolusi pustaka dinamis pada aplikasi pihak ketiga dengan mengeksploitasi variabel lingkungan `LD_DEBUG`.
- [ ] Membangun dan mengonfigurasi pustaka bersama (*shared library*) menggunakan GNU Toolchain (`gcc`, `ld`) dengan parameter `-fPIC`, `-shared`, dan atribut `-Wl,-soname`.
- [ ] Mengaudit serta mengintersepsi sistem panggilan antarmuka C standar menggunakan teknik injeksi `LD_PRELOAD`.
- [ ] Melakukan troubleshooting dan perbaikan basis data manajer paket yang rusak atau terkunci secara deterministik tanpa merusak integritas sistem operasi.
- [ ] Memulihkan sistem Linux yang mengalami kerusakan pustaka krusial (seperti hilangnya symlink dynamic linker atau `libc`) menggunakan pemanggilan manual loader atau *statically linked recovery tools*.