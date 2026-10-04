# BAB 03: Quiz, Challenge, & Knowledge Check
**Virtual File System (VFS), Storage, dan Blok I/O**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Dekopel Arsitektur Empat Objek Inti VFS
Jelaskan siklus hidup dan dependensi relasional antara empat objek inti VFS Linux: `struct super_block`, `struct inode`, `struct dentry`, dan `struct file`. Bagaimana VFS mendekomposisi sebuah panggilan sistem `open("/mnt/data/logs/app.log", O_RDWR)` ke dalam interaksi keempat struktur data tersebut di memori, dan bagaimana pemisahan ini memungkinkan Linux mengabstraksi filesystem disk (seperti ext4/XFS), filesystem jaringan (seperti NFS), dan pseudo-filesystem (seperti `sysfs`/`procfs`) di bawah satu antarmuka abstrak seragam?

### Soal 1.2: Dentry Cache (dcache) vs Page Cache
Analisis perbedaan fundamental antara *Dentry Cache* (dcache) dan *Page Cache* dari perspektif struktur data kernel, tujuan performa, dan unit alokasi memori. Mengapa *path resolution* (`filename_lookup` / `namei`) sangat bergantung pada dcache hash table dan list LRU? Apa yang terjadi pada level CPU dan I/O disk ketika sebuah sistem mengalami *dcache thrashing* akibat traversal miliaran file unik dalam waktu singkat?

### Soal 1.3: Mekanisme Hard Link vs Symbolic Link pada Level Inode
Secara struktural di tingkat filesystem, jelaskan perbedaan mutlak representasi *hard link* dan *symbolic link* (*symlink*). Mengapa *hard link* dibatasi secara ketat tidak dapat melintasi *mount point* (perangkat/filesystem yang berbeda) dan tidak diizinkan menunjuk ke direktori pada kebanyakan filesystem POSIX, sedangkan *symlink* dapat melakukannya? Uraikan apa yang terjadi pada *link count* (`i_nlink`) dan status blok data fisik ketika sebuah file yang memiliki 3 *hard link* dieksekusi perintah `unlink()` secara berurutan hingga link terakhir.

### Soal 1.4: Abstraksi Lapisan Blok: `struct bio` ke `struct request`
Lacak transformasi data I/O saat meninggalkan Page Cache menuju storage driver. Bagaimana sebuah halaman kotor (*dirty page*) diubah menjadi segmen-segmen di dalam `struct bio`? Jelaskan bagaimana *block layer* melakukan proses *merging* (front/back merge) dan *splitting* terhadap beberapa objek `bio` menjadi satu `struct request`, serta peran antrean *request queue* (`struct request_queue`) dalam menjamin efisiensi transfer data ke *device driver*.

### Soal 1.5: Semantik Ketahanan Data: `sync()`, `fsync()`, dan `fdatasync()`
Bandingkan semantik eksekusi dan biaya komputasi/I/O antara *system call* `sync()`, `fsync(int fd)`, dan `fdatasync(int fd)`. Spesifikasikan komponen metadata apa (misalnya `st_atime`, `st_mtime`, `st_size`, blok alokasi) yang dijamin atau tidak dijamin ditulis ke media non-volatile oleh `fdatasync()`. Mengapa *storage controller write cache* (volatile vs non-volatile battery-backed) dapat menggugurkan asumsi durabilitas ACID basis data meskipun panggilan `fsync()` mengembalikan nilai balik sukses (`0`)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Anomali Ruang Disk: Unlinked Open Files ("Ghost Files")
Sebuah server pelaporan mendadak memicu alarm kapasitas disk: `df -h /var/log` menunjukkan penggunaan 100% (0 byte free), namun investigasi menggunakan `du -sh /var/log/*` hanya menemukan akumulasi data sebesar 5 GB dari total partisi 200 GB. 
* Jelaskan secara teknis mekanisme VFS yang melandasi disparitas ini berdasarkan manipulasi dentry unhashing dan status `i_nlink` vs `i_count` pada `struct inode`.
* Tuliskan tahapan diagnostik deterministik untuk mengidentifikasi PID dan *File Descriptor* (FD) proses yang menahan file tersebut melalui pseudo-filesystem `/proc`.
* Tanpa melakukan terminasi proses (`kill -9`) yang sedang melayani transaksi aktif, bagaimana cara Anda mengosongkan ruang disk tersebut secara aman?

### Soal 2.2: Dentry Cache Memory Leak & Kernel Slab Shrinker
Server API dengan *throughput* tinggi mengalami penurunan performa sistemik. Metrik memori menunjukkan *anonymous memory* rendah, namun metrik `SUnreclaim` pada `/proc/meminfo` menghabiskan 85% total RAM fisik.
* Bagaimana Anda membuktikan bahwa degradasi ini disebabkan oleh akumulasi objek `dentry` dan `inode_cache` di SLAB/SLUB allocator?
* Jelaskan cara kerja subsistem *kernel memory shrinker* (`prune_dcache_sb`) saat menghadapi *memory pressure*.
* Evaluasi trade-off pengubahan kernel parameter `vm.vfs_cache_pressure` dari nilai default (100) ke nilai agresif (>1000) atau konservatif (<50) terhadap stabilitas Page Cache vs Latensi VFS path lookup.

### Soal 2.3: Direct I/O (`O_DIRECT`) vs Asynchronous I/O (`io_uring`) Batasan & Edge Cases
Mesin basis data modern sering kali membuka file data menggunakan flag `O_DIRECT`.
* Jelaskan batasan keras (*alignment constraints*) yang diwajibkan oleh lapisan blok dan VFS ketika aplikasi mengeksekusi I/O dengan flag `O_DIRECT` (kaitkan dengan *memory buffer address*, *file offset*, dan *transfer length*).
* Apa kegagalan sistemik (*performance penalty*) yang terjadi jika sebuah aplikasi menggunakan `O_DIRECT` untuk operasi *append write* dengan ukuran tidak teralokasi (*unaligned*) yang memicu pembaruan metadata ukuran file secara terus-menerus?
* Mengapa kombinasi `O_DIRECT` dengan `io_uring` secara arsitektural melampaui paradigma tradisional Linux AIO (`io_submit`) pada penyimpanan berbasis NVMe modern?

### Soal 2.4: Arsitektur Multi-Queue Blok I/O (`blk-mq`) & Scheduler Selection
Arsitektur subsistem blok Linux telah berevolusi dari *single-queue* menjadi *multi-queue block layer* (`blk-mq`) yang memetakan *software staging queues* ke *hardware dispatch queues*.
* Jelaskan mengapa algoritma scheduler I/O tradisional seperti CFQ (*Completely Fair Queuing*) dihapus dan tidak relevan pada media NVMe berperforma ratusan ribu IOPS.
* Bandingkan use-case optimal, kelemahan, dan mekanisme internal dari tiga I/O scheduler modern: `none` (tidak ada scheduler), `mq-deadline`, dan `bfq`.
* Dalam kondisi beban kerja saturasi I/O campuran (90% throughput streaming sequential write + 10% mission-critical low-latency random read), scheduler manakah yang menjamin p99 read latency paling stabil? Justifikasi jawaban Anda.

### Soal 2.5: Root Cause Analisis VFS: `ESTALE` (Stale File Handle)
Pada cluster komputasi terdistribusi berbasis NFSv4 atau shared storage POSIX, aplikasi kerap mengalami galat sistemik `ESTALE (Error 116: Stale file handle)`.
* Telusuri siklus hidup resolusi file pada lapisan VFS klien dan server yang menghasilkan error ini (`fh_to_dentry`, *file handle encoding*, dan *generation number* di dalam `struct inode`).
* Mengapa pergantian file secara atomik di sisi server menggunakan operasi `rename()` dapat memicu `ESTALE` pada klien yang masih mempertahankan *file descriptor* terbuka pada inode lama?
* Bagaimana mekanisme `d_invalidate` dan *attribute caching timeout* (`actimeo`) di sisi klien memperburuk atau memitigasi anomali ini?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Disk Saturation & P99 Latency Spikes Akibat Dirty Page Flushing Burst
Sebuah cluster database PostgreSQL berkapasitas 2 TB pada instance bare-metal dengan RAM 512 GB dan media penyimpanan array NVMe PCIe Gen4 mengalami degradasi berkala. Setiap 30–60 detik, latensi transaksi p99 melonjak dari 1.2 milidetik menjadi lebih dari 850 milidetik. Monitoring grafana menunjukkan bahwa utilisasi I/O disk melonjak ke 100%, dan proses flush kernel (`kworker/flush-*`) mendominasi penggunaan CPU I/O wait (`%iowait`).

```
--- /proc/vmstat snapshot saat insiden ---
nr_dirty: 13107200 (sekitar 50 GB data dirty di Page Cache)
nr_writeback: 10485760
nr_dirtied: 849302941
nr_written: 789230482
```

Konfigurasi kernel saat ini:
```ini
vm.dirty_background_ratio = 10
vm.dirty_ratio = 20
vm.dirty_expire_centisecs = 3000
vm.dirty_writeback_centisecs = 500
```

**Pertanyaan Diagnostik:**
1. Bedah secara matematis dan arsitektural bagaimana konfigurasi `vm.dirty_*` di atas menyebabkan fenomena *I/O flusher stall* ketika dirty pages di RAM mencapai ambang batas kritis.
2. Jelaskan bahaya dari mekanisme *throttling* bawaan kernel ketika batas `vm.dirty_ratio` terlampaui terhadap proses penulisan aplikasi (PostgreSQL backend process).
3. Rancang formula tuning kernel berbasis nilai absolut (`bytes`) bukan rasio (`ratio`) untuk memitigasi fluktuasi penulisan disk, meratakan beban I/O (*smooth continuous writeback*), dan mempertahankan performa p99 tanpa mengorbankan keamanan data secara ekstrem.

---

### Skenario B: Silent Filesystem Remount Read-Only pada Kubernetes Node
Sebuah node worker Kubernetes yang menjalankan 40 container StatefulSet mendadak mengalami kegagalan massal. Aplikasi mulai melaporkan `Read-only file system` (errno 30). Output dari perintah `mount` menunjukkan bahwa filesystem root/data lokal telah beralih status secara otomatis:

```text
/dev/mapper/vg_data-lv_storage on /var/lib/containerd/io.containerd.runtime.v1.linux/moby type ext4 (ro,relatime,errors=remount-ro,data=ordered)
```

Inspeksi `dmesg -T` mengungkap log berikut:
```text
[Tue May 14 03:14:22 2024] blk_update_request: I/O error, dev nvme0n1, sector 104857600 op 0x1:(WRITE) flags 0x800 phys_seg 12 prio class 0
[Tue May 14 03:14:22 2024] Aborting journal on device nvme0n1p2-8.
[Tue May 14 03:14:22 2024] EXT4-fs error (device nvme0n1p2): ext4_journal_check_start:83: Detected aborted journal
[Tue May 14 03:14:22 2024] EXT4-fs (device nvme0n1p2): Remounting filesystem read-only
```

**Pertanyaan Diagnostik:**
1. Uraikan rantai kausalitas dari tingkat *hardware/controller timeout*, penerjemahan error di *block layer* (`blk_update_request`), hingga reaksi defensif driver `ext4` yang memutuskan untuk mengaborsi JBD2 (*Journaling Block Device*) dan melakukan *remount ro*.
2. Mengapa filesystem default memilih strategi `remount-ro` daripada tetap melanjutkan penulisan atau sekadar mencatat peringatan? Apa risiko integritas data struktural (metadata corruption) jika kernel membiarkan filesystem tetap berstatus read-write dalam kondisi jurnal terputus?
3. Formulasikan SOP investigasi dan remediasi insiden langkah demi langkah:
   * Bagaimana memastikan integritas hardware NVMe vs soft-lockout kontroler?
   * Kapan safe unmount dan `fsck` manual harus dijalankan?
   * Bagaimana mengembalikan ketersediaan node tanpa merusak state container secara permanen?

---

### Skenario C: Inode Exhaustion dan Dentry Thrashing Akibat Session Files Leak
Sebuah server e-commerce berskala besar dengan kapasitas disk 1 TB berbasis filesystem XFS melaporkan kegagalan sistemik: tidak ada proses yang dapat menulis data baru, dengan error konsisten `No space left on device` (errno 28 / ENOSPC). Namun, perintah `df -h` menunjukkan bahwa ruang penyimpanan fisik baru terpakai 12% (tersedia 880 GB free space).

Hasil eksekusi diagnostik awal:
```bash
$ df -i /data
Filesystem      Inodes   IUsed   IFree IUse% Mounted on
/dev/sda1      65536000 65536000       0  100% /data

$ ls -1U /data/sessions | wc -l
ls: memory exhausted
```

Server juga mengalami *high load average* (didominasi kernel task) meskipun utilisasi CPU user-space rendah.

**Pertanyaan Diagnostik:**
1. Mengapa error yang dihasilkan adalah `ENOSPC` padahal ruang penyimpanan blok masih melimpah? Jelaskan korelasi statis vs dinamis alokasi inode pada ext4 vs XFS dan batas limitasi tabel metadata inode.
2. Analisis kegagalan perintah `ls -1U /data/sessions | wc -l` dan jelaskan bahaya eksekusi perintah pembersihan naif seperti `rm -rf /data/sessions/*` terhadap alokasi memori user-space (`ARG_MAX` / `E2BIG`) dan kestabilan kernel lock (seperti inode mutex/rwsem).
3. Rancang strategi restorasi data darurat untuk menghapus puluhan juta file tersebut dengan dampak minimal terhadap latensi I/O sistem yang masih berjalan, serta buat rekomendasi modifikasi arsitektur penyimpanan (di tingkat VFS/Mount options/Filesystem selection) agar insiden kehabisan alokasi penamaan file ini tidak dapat terulang kembali.

---

## 4. Chapter Challenge

### Tantangan Praktis: Deep-Dive Block I/O Profiling & Latency Tracer Engine
Sebagai Staff Infrastructure/Storage Engineer, Anda ditugaskan membangun toolkit diagnostik performa I/O deterministik untuk menganalisis dan membongkar jalur I/O di kernel Linux saat terjadi anomali latensi pada aplikasi basis data performa tinggi.

#### Problem Statement
Aplikasi mengalami anomali latensi *tail* (p999) yang tidak terdeteksi oleh monitoring tradisional (`iostat` per detik hanya menunjukkan metrik rata-rata). Anda diminta membuktikan secara empiris di titik mana latensi terbentuk:
1. **VFS Layer** (waktu tunggu inode mutex lock / Page Cache write contention),
2. **Block Layer Queue** (waktu antre request di I/O scheduler), atau
3. **Device Driver / Hardware** (waktu eksekusi riil kontroler disk).

#### Requirements
1. **Emulasi Lingkungan Uji:**
   * Buat loopback block device berbasis sparse-file sebesar 2 GB dengan partisi ext4.
   * Mount dengan opsi sinkronisasi data standar.
2. **Penyusunan Script Observabilitas Kernel:**
   * Gunakan `eBPF/bpftrace` (atau integrasi tracepoints Ftrace/kprobes murni jika eBPF tidak tersedia) untuk membuat script penjejak latensi end-to-end.
   * Lacak siklus hidup I/O dari fungsi `vfs_write` -> `submit_bio` -> `blk_mq_start_request` -> `blk_account_io_done`.
   * Klasifikasikan waktu tempuh menjadi 3 metrik independen:
     * *VFS-to-Bio Latency* (waktu persiapan Page Cache/VFS).
     * *Queue Latency* (waktu tunggu dalam scheduler queue sebelum dispatch ke device).
     * *Device Service Latency* (waktu eksekusi hardware aktual dari dispatch hingga completion interrupt).
3. **Injeksi Beban dan Chaos:**
   * Simulasikan beban I/O terisolasi menggunakan `fio` dengan profil beban: random write, block size 4k, queue depth 64, menggunakan direct I/O (`direct=1`) dan non-direct I/O (`direct=0`).
   * Buat kondisi buatan (*artificial pressure*) yang memicu antrean blok panjang menggunakan cgroups v2 I/O throttling (`io.max` / `io.weight`).
4. **Analisis Profiling:**
   * Sajikan visualisasi data distribusi latensi dalam bentuk histogram logaritmik (Power-of-2 histogram).

#### Constraints
* Tidak diperbolehkan menggunakan binary siap pakai tingkat tinggi seperti `iotop` standar atau monitoring berbasis scraping `/proc/diskstats` saja (wajib instrumentasi level kernel/eBPF/Tracepoints).
* Script profiling harus memiliki overhead CPU < 3% saat beban penulisan mencapai 10.000 IOPS.
* Seluruh operasi harus dapat direproduksi di Linux kernel >= 5.15.

#### Expected Output
1. File naskah skrip tracing (misal: `io_breakdown.bt` atau script shell berbasis `tracefs`).
2. Tabel log distribusi latensi tersegregasi: VFS Latency vs Queue Latency vs Device Latency.
3. Dokumen analisis akar masalah teknis: Bukti matematis dan instruksional yang menunjukkan kapan antrean scheduler I/O kolaps dan bagaimana pergeseran antrean tersebut memicu lonjakan latensi di sisi aplikasi pengguna.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Definisi, struktur internal, dan siklus hidup empat objek utama VFS (`super_block`, `inode`, `dentry`, `file`).
- [ ] Perbedaan fungsional, struktur data, dan mekanisme flushing antara Page Cache dan Dentry/Inode Cache.
- [ ] Implementasi internal hard link dan soft link serta interaksinya dengan `i_nlink`, `i_count`, dan isolasi *mount namespace/filesystem boundary*.
- [ ] Peran dan siklus transformasi data dari Page Cache dirty pages, struktur `struct bio`, penggabungan pada `struct request`, hingga alokasi antrean hardware melalui arsitektur `blk-mq`.
- [ ] Semantik sistem operasi dan implikasi integritas data dari panggilan `sync()`, `fsync()`, `fdatasync()`, dan flag file `O_SYNC` / `O_DSYNC`.
- [ ] Cara kerja memory writeback flusher kernel (`dirty_background_*` vs `dirty_*` threshold) dan dampaknya terhadap throughput vs tail-latency.
- [ ] Trade-off arsitektural I/O Schedulers di Linux modern (`none`, `mq-deadline`, `bfq`, `kyber`).
- [ ] Mekanisme proteksi filesystem saat mendeteksi kegagalan I/O pada JBD2/jurnal metadata (transisi `remount-ro`).

### Saya tidak perlu menghafal:
- [ ] Struktur byte-level offset biner dari *on-disk superblock* atau *inode table* spesifik ext4/XFS secara verbatim.
- [ ] Seluruh nomor integer errno POSIX di luar yang fundamental (seperti `ENOSPC`, `EIO`, `ESTALE`, `EBUSY`, `E2BIG`).
- [ ] Detail implementasi register level chip kontroler NVMe Command Set / AHCI FIS registers.
- [ ] Nama seluruh field internal pada `struct bio` atau `struct request` yang kerap berubah antar-versi minor kernel Linux.

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi dan memulihkan ruang penyimpanan disk dari file terhapus yang masih ditahan oleh *active process file descriptors* (`/proc/$PID/fd`) secara non-disruptif.
- [ ] Mengonfigurasi parameter kernel VM dirty memory (`/proc/sys/vm/dirty_*`) untuk mengeliminasi fenomena *I/O burst stalls* pada mesin basis data skala besar.
- [ ] Melakukan investigasi bottleneck blok I/O menggunakan kombinasi toolkit canggih (`iostat -xz`, `biolatency`, `biosnoop`, `blktrace`, atau script `bpftrace`).
- [ ] Mengidentifikasi dan mengatasi insiden kehabisan inode (*inode exhaustion*) secara efisien tanpa membuat sistem operasi mengalami out-of-memory atau shell-lockup.
- [ ] Melakukan benchmarking performa storage terisolasi menggunakan `fio` secara presisi untuk memverifikasi batas kemampuan IOPS, throughput bandwidth, dan latensi p99 hardware penyimpanan.