## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: LIN-01-03-01
* **Nama Modul**: Virtual File System (VFS) Architecture & Abstraction
* **Track**: Linux Core Foundations
* **Kategori**: 01-Core-Foundations
* **Tingkat Kesulitan**: Intermediate to Advanced
* **Prasyarat**: 
  * Pemahaman mendasar terkait Linux System Calls (`open()`, `read()`, `write()`, `close()`).
  * Konsep struktur data dasar bahasa C (pointer, struct, array of function pointers).
  * Pengenalan partisi disk dan konsep filesystem dasar (ext4, POSIX).
* **Alokasi Waktu**: 
  * Teori: 90 Menit
  * Praktik & Hands-on: 120 Menit
  * Total: 210 Menit

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis (C4)** peranan arsitektur VFS sebagai *abstraction layer* universal yang menjembatani *userspace syscalls* dengan implementasi konkret filesystem heterogen (ext4, XFS, Btrfs, NFS, Procfs).
2. **Mendiferensiasikan (C4)** empat struktur data inti kernel Linux pada VFS: `struct super_block`, `struct inode`, `struct dentry`, dan `struct file`, serta siklus hidup dan dependensi relasional antar-objek tersebut.
3. **Mendemonstrasikan (C3)** proses resolusi *pathway* (*path resolution*) dari *root namespace* hingga manipulasi blok data, termasuk mekanisme kerja *Directory Cache* (`dcache`) dan *Inode Cache* (`icache`).
4. **Mengevaluasi (C5)** dampak alokasi memori kernel akibat *cache retention* struktur VFS menggunakan utilitas introspeksi kernel (`slabtop`, `/proc/slabinfo`) dan melakukan optimasi parameter kernel `vfs_cache_pressure`.
5. **Mengisolasi dan Mendiagnosis (C4)** anomali konsumsi *file descriptor*, penghapusan file yang masih terbuka (*unlinked open files*), dan *mount-point shadowing* pada lingkungan produksi Linux.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
[Userspace Applications]
         │
         │  (POSIX System Calls: open, read, write, stat, unlink)
         ▼
┌─────────────────────────────────────────────────────────────┐
│                 VFS (Virtual File System)                   │
│                                                             │
│  ┌─────────────────┐             ┌──────────────────────┐  │
│  │  struct file    │ ──references──▶ │    struct dentry     │  │
│  │ (Open Instance) │             │ (Directory Hierarchy)│  │
│  └─────────────────┘             └──────────┬───────────┘  │
│                                             │               │
│                                         references          │
│                                             ▼               │
│  ┌─────────────────┐             ┌──────────────────────┐  │
│  │struct super_block│ ◀──manages─- │    struct inode      │  │
│  │ (Mounted FS Meta│             │  (Metadata & Ops)    │  │
│  └─────────────────┘             └──────────┬───────────┘  │
└─────────────────────────────────────────────┼───────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
         [Disk-backed Filesystems]                       [Pseudo Filesystems]
         ┌──────────────┬──────────────┐                 ┌─────────────┬─────────────┐
         │     ext4     │     XFS      │                 │   procfs    │   sysfs     │
         └──────┬───────┴──────┬───────┘                 └─────────────┴─────────────┘
                ▼              ▼
         [Block I/O Layer (bio)]
                ▼
       [Physical Storage (NVMe/SSD/HDD)]
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sistem operasi modern dituntut untuk mengelola penyimpanan yang heterogen tanpa membebani pengembang aplikasi dengan kompleksitas internal masing-masing media. Tanpa layer abstraksi:
* Aplikasi harus ditulis ulang secara spesifik untuk membaca partisi disk ext4, array XFS, remote storage NFS, atau memori virtual kernel.
* Tidak ada paradigma seragam seperti prinsip Unix: *"Everything is a file"*.
* Portabilitas aplikasi *userspace* mustahil tercapai karena setiap vendor storage atau tipe filesystem memiliki antarmuka (API) yang berbeda.

VFS menyelesaikan masalah ini dengan menyediakan kontrak API/ABI berbasis POSIX seragam di sisi *userspace*, sementara di sisi kernel VFS menggunakan paradigma *object-oriented C* berbasis *function pointers* untuk memanggil fungsi *driver* filesystem konkret. Memahami VFS sangat krusial bagi Site Reliability Engineer (SRE), Kernel Developer, dan Systems Programmer untuk:
* Melakukan troubleshooting insiden kapasitas disk *ghost usage* (file dihapus tapi *space* tidak berkurang).
* Menganalisis *performance bottleneck* pada I/O disk yang terhambat oleh *lock contention* pada dcache.
* Menyetel performa alokasi memori sistem antara *Page Cache* vs *Dentry/Inode Cache*.

---

## SEKSI 05 — APA ITU (WHAT)

**Virtual File System (VFS)** adalah subsistem perangkat lunak di dalam kernel Linux yang bertindak sebagai antarmuka perantara antara program ruang pengguna (*userspace*) dan implementasi fisik/logis sistem berkas konkret. VFS mendefinisikan model sistem berkas abstrak yang mencakup seluruh konsep berkas, direktori, metadata, dan operasi I/O.

### Empat Objek Primer VFS

VFS diimplementasikan menggunakan paradigma berorientasi objek dalam bahasa C. Objek-objek ini memiliki representasi data struktur dan pointer ke kumpulan fungsi operasi (*operations vector*):

1. **Superblock Object (`struct super_block`)**:
   * Merepresentasikan keseluruhan sistem berkas yang sedang di-*mount*.
   * Menyimpan metadata global sistem berkas (ukuran blok, status *mount*, batas ukuran berkas, magic number).
   * Vektor operasi: `struct super_operations` (alokasi inode, sinkronisasi kuota, unmount).

2. **Inode Object (`struct inode`)**:
   * Merepresentasikan berkas spesifik atau objek metadata pada sistem berkas (regular file, directory, symlink, socket, FIFO, block/character device).
   * Menyimpan izin akses (`mode`), ukuran berkas, UID, GID, stempel waktu (*atime, mtime, ctime*), dan pointer ke blok data fisik disk. Inode **tidak** menyimpan nama berkas.
   * Vektor operasi: `struct inode_operations` (membuat link, lookup dentry, create file, mkdir).

3. **Dentry Object (`struct dentry`)**:
   * Kependekan dari *Directory Entry*.
   * Merepresentasikan komponen jalur berkas (*path component*) untuk merangkai hierarki direktori di memori (misal: `/`, `usr`, `bin`, `bash`).
   * Mengaitkan nama berkas (*string*) ke nomor inode tertentu. Dentry hanya berdiam di RAM (tidak pernah ditulis ke disk).
   * Vektor operasi: `struct dentry_operations` (perbandingan nama, validasi dentry cache).

4. **File Object (`struct file`)**:
   * Merepresentasikan berkas yang dibuka oleh suatu proses (*open file instance*).
   * Menyimpan *state* interaksi proses dengan berkas, mencakup posisi pembacaan saat ini (*file offset* / `f_pos`), flag pembukaan (`O_RDONLY`, `O_SYNC`), dan hak akses.
   * Dialokasikan saat `sys_open()` dan dihancurkan saat `sys_close()`.
   * Vektor operasi: `struct file_operations` (`read`, `write`, `mmap`, `ioctl`, `poll`, `fsync`).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Mekanisme Resolusi Path (*Path Resolution*)
Ketika sebuah proses memanggil `open("/var/log/syslog", O_RDONLY)`:

1. Kernel memulai resolusi dari `root` direktori (`/`) atau `current working directory` milik proses.
2. Kernel memeriksa komponen pertama (`var`) di dalam **Dentry Cache (dcache)**:
   * **Cache Hit**: Mengambil `struct dentry` yang telah terasosiasi dengan `struct inode` untuk `var`.
   * **Cache Miss**: Memanggil `inode_operations->lookup()` milik filesystem konkret dari partisi *root* untuk membaca blok direktori fisik, membangun `struct dentry` baru di memori, dan mengaitkannya ke `struct inode`.
3. Proses ini diulang secara sekuensial untuk `log`, kemudian `syslog`.
4. Jika salah satu dentry bertipe *symbolic link*, kernel mengeksekusi traversal link (dengan batas kedalaman loop, default 40 jumps) untuk mencegah *infinite recursion*.

### 2. Generasi `struct file` dan File Descriptor Table
1. Setelah dentry akhir (`syslog`) dan inode-nya ditemukan:
   * Kernel memvalidasi perizinan akses berkas (UID/GID vs flag pembukaan).
2. Kernel mengalokasikan satu instansiasi `struct file` baru pada *system-wide open file table*.
3. Field `f_op` pada `struct file` disalin dari field `i_fop` pada `struct inode` (menghubungkan operasi baca/tulis ke fungsi *driver* spesifik filesystem target).
4. Kernel mencari indeks terkecil yang belum terpakai pada array `fdtable` milik proses (`task_struct->files->fdt`), lalu menautkan indeks integer tersebut (File Descriptor / FD) ke pointer `struct file`.
5. Nilai integer FD dikembalikan ke *userspace*.

### 3. Operasi Baca/Tulis (Read/Write Execution)
Ketika proses mengeksekusi `read(fd, buf, count)`:
1. Kernel memetakan integer `fd` melalui `fdtable` proses untuk mendapatkan pointer `struct file`.
2. Kernel memanggil pointer fungsi: `file->f_op->read()` atau `file->f_op->read_iter()`.
3. Pada sistem berkas berbasis disk (misal ext4):
   * Fungsi akan memeriksa apakah data yang diminta berada di **Page Cache**.
   * Jika tidak ada (*cache miss*), dibentuk struktur `struct bio` untuk meminta pengiriman blok dari subsistem *Block I/O Layer*.
   * Offset `file->f_pos` dimutakhirkan sebesar jumlah byte yang berhasil dibaca.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

```
                   +-------------------------------------------------------+
                   |                 USERSPACE PROCESS                     |
                   | task_struct                                           |
                   |   └── files_struct *files                             |
                   |         └── fdtable *fdt                              |
                   |               └── struct file *fd[3] ──(FD = 3)───┐   |
                   +───────────────────────────────────────────────────┼───+
                                                                       │
┌──────────────────────────────── VFS LAYER ───────────────────────────┼──┐
│                                                                      ▼  │
│                                                            +------------+
│                                                            |struct file |
│                                                            |------------|
│                                                            |f_pos = 4096|
│                                                            |f_flags     |
│                                         ┌──────────────────|*f_dentry   |
│                                         │                  |*f_op       |──┐
│                                         │                  +------------+  │
│                                         ▼                                  │
│             +-------------------------------------------------------+      │
│             |                     struct dentry                     |      │
│             |-------------------------------------------------------|      │
│             | d_name   : "syslog"                                   |      │
│             | d_parent : pointer to "log/" dentry                   |      │
│             | d_op     : pointer to dentry_operations               |      │
│             | d_inode  : pointer to inode ──────────────────┐       |      │
│             +-----------------------------------------------┼-------+      │
│                                                             │              │
│                                                             ▼              │
│             +-------------------------------------------------------+      │
│             |                     struct inode                      |      │
│             |-------------------------------------------------------|      │
│             | i_ino     : 131074                                    |      │
│             | i_mode    : -rw-r-----                                |      │
│             | i_size    : 1048576 bytes                             |      │
│             | i_sb      : pointer to super_block ───────────┼──┐   |      │
│             | i_fop     : pointer to ext4_file_operations ──┼──┼───┘      │
│             | i_op      : pointer to ext4_file_inode_ops    │  │          │
│             +-----------------------------------------------┼──┼──────────┘
│                                                             │  │
│                   ┌─────────────────────────────────────────┘  │
│                   ▼                                            ▼
│  +---------------------------------+          +---------------------------------+
│  |       struct super_block        |          |      ext4_file_operations       |
│  |---------------------------------|          |---------------------------------|
│  | s_blocksize : 4096              |          | .read_iter = ext4_file_read_iter|
│  | s_type      : ext4_fs_type      |          | .write_iter= ext4_file_write_iter|
│  | s_op        : ext4_sops         |          | .mmap      = ext4_file_mmap     |
│  +---------------------------------+          +---------------------------------+
│                   │
└───────────────────┼─────────────────────────────────────────────────────────┘
                    ▼
       [Concrete Filesystem Driver: ext4]
                    │
                    ▼
          [Page Cache / Buffer]
                    │
                    ▼
         [Block Layer (Request Queue)]
                    │
                    ▼
          [Physical Storage Media]
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Menelusuri bagaimana pemanggilan sistem (*syscall*) berkas direfleksikan pada VFS dan informasi process table menggunakan `strace` dan `/proc`.

### 1. Eksekusi Script Pemantauan Syscall

Jalankan perintah berikut pada terminal:

```bash
strace -e trace=openat,read,close head -n 1 /etc/passwd
```

**Output Analisis:**
```text
openat(AT_FDCWD, "/etc/passwd", O_RDONLY) = 3
read(3, "root:x:0:0:root:/root:/bin/bash\n", 8192) = 32
close(3)                                = 0
root:x:0:0:root:/root:/bin/bash
```

### 2. Dekonstruksi Kejadian VFS

1. `openat(AT_FDCWD, "/etc/passwd", O_RDONLY) = 3`:
   * VFS menyelesaikan path `/etc/passwd`.
   * Membaca inode terkait (misal inode #262145 pada partisi root).
   * Mengalokasikan `struct file` di kernel memory.
   * Menugaskan indeks integer `3` pada *file descriptor table* proses `head`.
2. `read(3, ..., 8192) = 32`:
   * VFS mengambil `struct file` dari FD `3`.
   * Mengeksekusi pointer fungsi `.read_iter` yang diarahkan ke driver filesystem partisi tempat `/etc` berada.
   * Mengambil data sebanyak 32 byte dan menaikkan offset `f_pos` dari 0 menjadi 32.
3. `close(3)`:
   * Kernel memutus asosiasi indeks `3` dari proses.
   * Reference counter pada `struct file` diturunkan. Jika mencapai 0, memori struktur tersebut dibebaskan ke slab allocator.

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus Produksi: Mendeteksi lonjakan konsumsi memori akibat *Dentry/Inode Cache Bloat* dan menganalisis anomali berkas terhapus yang masih menahan kapasitas storage (*unlinked open files*).

### Investigasi Slab Memory untuk VFS Caches

Ketika jutaan berkas kecil diakses secara serentak (misal: *web server traversal* atau *find scans*), memori RAM server dapat berkurang drastis karena kernel mempertahankan dentry dan inode di memori.

```bash
# Periksa alokasi dentry dan inode cache pada Slab
sudo slabtop -o | head -n 20
```

Tampilan umum:
```text
  OBJS ACTIVE  USE OBJ SIZE  SLABS OBJ/SLAB CACHE SIZE NAME                   
489240 489110  99%    0.19K  11648       42     93184K dentry
340120 339890  99%    0.61K  13081       26    209296K ext4_inode_cache
```

Jika `dentry` dan `ext4_inode_cache` mengonsumsi sebagian besar RAM sistem saat *memory pressure*, perilaku ini dapat dipantau melalui `/proc/meminfo`:

```bash
grep -E "SReclaimable|SUnreclaim|Slab" /proc/meminfo
```

### Investigasi File Descriptor Bocor (Ghost Storage Usage)

Skrip demonstrasi: Membuat proses yang menahan file deskriptor setelah file fisiknya dihapus via `unlink()`.

Buat berkas reproduksi `leak_demo.py`:

```python
#!/usr/bin/env python3
import time
import os

def main():
    filename = "/tmp/vfs_ghost_test.dat"
    # Alokasi berkas sebesar 100MB
    with open(filename, "wb") as f:
        f.write(b"\0" * (100 * 1024 * 1024))
        f.flush()
        print(f"[+] Berkas {filename} berhasil dibuat (100MB).")
        print(f"[+] Membuka {filename} dalam mode read...")
        
        # Buka descriptor baru yang akan ditahan
        held_fd = open(filename, "rb")
        
        # Hapus berkas dari direktori (unlink dentry)
        os.unlink(filename)
        print(f"[!] Berkas {filename} di-unlink! Periksa kapasitas storage sekarang.")
        print(f"[PID]: {os.getpid()} - Berjalan selama 60 detik...")
        
        time.sleep(60)
        held_fd.close()
        print("[+] File descriptor ditutup. Inode dihapus sepenuhnya.")

if __name__ == "__main__":
    main()
```

Jalankan skrip di satu terminal:
```bash
python3 leak_demo.py
```

Di terminal kedua, lakukan investigasi status VFS:

```bash
# 1. Pastikan berkas sudah tidak muncul di filesystem tree
ls -lh /tmp/vfs_ghost_test.dat
# Output: ls: cannot access '/tmp/vfs_ghost_test.dat': No such file or directory

# 2. Cek apakah kapasitas storage masih tertahan menggunakan df vs du
df -h /tmp
# Kapasitas tetap terpakai 100MB!

# 3. Lacak dentry berstatus (deleted) melalui VFS proc abstraction
lsof | grep "vfs_ghost_test.dat"
# Output:
# python3   14523  user    4r   REG   259,2  104857600  1048580 /tmp/vfs_ghost_test.dat (deleted)

# 4. Bukti bahwa VFS mempertahankan Inode: periksa link procfd
ls -l /proc/14523/fd/
# lr-x------ 1 user user 64 May 12 10:00 4 -> /tmp/vfs_ghost_test.dat (deleted)
```

**Penjelasan Teknis VFS**:
Saat fungsi `unlink()` dipanggil, VFS memutus kaitan `dentry` dari tabel direktori dan menurunkan *hard link counter* (`i_nlink`) pada `struct inode` dari 1 menjadi 0. Namun, karena *open file reference count* pada `struct file` masih bernilai > 0 (dipegang oleh PID 14523, FD 4), VFS **menunda dealokasi blok data fisik disk** hingga FD ditutup.

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Aspek / Desain | Pilihan A | Pilihan B | Trade-off / Implikasi |
| :--- | :--- | :--- | :--- |
| **Abstraksi VFS vs Direct FS API** | Menggunakan VFS Abstraction (POSIX standard) | Bypass VFS (Raw block access/Direct User-space FS spt SPDK) | VFS memberikan portabilitas kode mutlak, konkurensi aman, dan page cache terpadu. Namun, memicu overhead *context switch*, isolasi memori kernel-user, serta *indirection cost* pada pointer fungsi. |
| **Dentry/Inode Cache Retention** | `vfs_cache_pressure = 50` (Konservatif) | `vfs_cache_pressure = 1000` (Agresif melepaskan) | Nilai rendah mempertahankan metadata di RAM; mempercepat *path traversal* pada database dan repositori Git besar, namun mengurangi kapasitas memori untuk *application runtime heap*. Nilai tinggi mencegah OOM akibat slab bloat, tetapi memperlambat proses I/O karena frekuensi *inode fetch* ke disk meningkat. |
| **Direct I/O (`O_DIRECT`)** | Melalui Page Cache VFS | Bypass Page Cache via `O_DIRECT` | Page cache mengoptimalkan throughput melalui read-ahead dan dirty write caching. Direct I/O menghindari duplikasi buffer di RAM dan latensi cache flush, ideal untuk Database Engines (misal: PostgreSQL/MySQL InnoDB) yang mengimplementasikan algoritma caching internal sendiri. |

---

## SEKSI 11 — BEST PRACTICES

### 1. Manajemen dan Tuning `vfs_cache_pressure`
Parameter `/proc/sys/vm/vfs_cache_pressure` mengontrol kecenderungan kernel dalam mengklaim kembali (*reclaim*) memori yang dialokasikan untuk dentry dan inode cache dibandingkan memori *pagecache* dan *swap*.

* **Nilai Default (100)**: Kernel mempertahankan keseimbangan proporsional antara reclaiming dentry/inode cache dan page cache.
* **Nilai < 100 (misal: 50)**: Menginstruksikan kernel untuk menahan dentry dan inode cache lebih lama di RAM. Direkomendasikan untuk workload yang melakukan lookup ribuan berkas secara berulang (misal: mail servers, code repositories).
* **Nilai > 100 (misal: 200)**: Menginstruksikan kernel untuk agresif melepaskan dentry dan inode cache dari memory. Berguna pada lingkungan *batch-processing* satu kali lewat (*stream processing*) di mana metadata file jarang diakses kembali.

```bash
# Runtime Tuning
sudo sysctl -w vm.vfs_cache_pressure=80

# Persistensi via sysctl.conf
echo "vm.vfs_cache_pressure = 80" | sudo tee -a /etc/sysctl.d/99-vfs-tuning.conf
```

### 2. Batasi Kedalaman dan Jumlah File dalam Satu Folder (Directory Bloat)
VFS melakukan lookup nama berkas melalui *directory dentry list*. Memiliki lebih dari 100.000 file dalam satu folder tunggal dapat menyebabkan:
* *Lock contention* pada inode direktori induk saat berkas baru dibuat (`mutex_lock(&inode->i_rwsem)`).
* Inefisiensi dcache invalidation. Selalu gunakan struktur direktori bertingkat (*sharded directory hierarchy*), misal: `hash[0:2]/hash[2:4]/hash[4:]`.

### 3. Pemantauan Batas Maksimal File Descriptor
Pastikan batas total file descriptor sistem di VFS dikonfigurasi cukup untuk beban produksi skala besar:

```bash
# Periksa alokasi global VFS file handles (allocated, unused, max)
cat /proc/sys/fs/file-nr
# Output: 2432    0    1048576

# Set nilai global baru jika mendekati kapasitas maksimal
sudo sysctl -w fs.file-max=2097152
```

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Menyamakan `Inode` dengan `Dentry`
* *Salah Konsep*: Mengira bahwa nama file tersimpan di dalam struktur inode.
* *Fakta Arsitektural*: Inode tidak memiliki atribut nama berkas. Nama berkas hanya eksis sebagai komponen teks di dalam direktori, yang direpresentasikan di memori oleh `struct dentry`. Dua dentry yang berbeda dapat merujuk ke inode yang sama persis (mekanisme *hard link*).

### 2. Mencoba Mengosongkan Disk yang Penuh Hanya dengan `rm`
* *Kesalahan fatal*: Disk berstatus 100% penuh akibat log file yang membengkak. Administrator menjalankan `rm /var/log/app.log`, namun `df -h` tetap menunjukkan 100% penuh.
* *Akar Masalah*: Aplikasi masih memegang `open file descriptor` ke berkas tersebut. VFS mempertahankan blok disk selama referensi `struct file` aktif.
* *Solusi yang Benar*: Truncate file tanpa menghancurkan dentry descriptor:
  ```bash
  # Kosongkan konten secara langsung via file descriptor/path
  : > /var/log/app.log
  # Atau jika sudah terlanjur di-rm:
  # Lacak PID via lsof, lalu truncate via /proc
  : > /proc/<PID>/fd/<FD_NUMBER>
  ```

### 3. Mengasumsikan `drop_caches` Merupakan Solusi Rutin Memory Leak
* *Kesalahan operasional*: Menjadwalkan cron job harian: `echo 3 > /proc/sys/vm/drop_caches`.
* *Dampak Buruk*: Mengosongkan dcache, icache, dan pagecache secara paksa menyebabkan sistem mengalami lonjakan I/O latency (*I/O spike/thrashing*) secara tiba-tiba karena semua traversal path harus kembali membaca storage fisik dari awal. Tindakan ini hanya boleh digunakan untuk proses pengujian performa (*benchmarking*).

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Guided - Menganalisis Struktur Dentry dan Inode Menggunakan `debugfs`
* **Instruksi**:
  1. Identifikasi partisi filesystem root Anda (`findmnt /`).
  2. Buka antarmuka `debugfs` dalam mode read-only terhadap partisi tersebut.
  3. Lacak nomor inode dari file `/etc/hosts`.
  4. Periksa struktur internal inode tersebut (link count, size, blocks).
* **Perintah Uji**:
  ```bash
  sudo debugfs -R 'stat /etc/hosts' /dev/mapper/root_device
  ```
* **Ekspektasi Output**: Informasi lengkap meliputi Mode, User ID, Group ID, Size, direct/indirect block pointers, dan `Links: 1`.

### Latihan 2: Intermediate - Menemukan Proses Penahan File Terhapus (*Orphan Inodes*)
* **Skenario**: Server staging mengalami penurunan kapasitas disk yang drastis, namun `du -sh /*` tidak menemukan direktori besar yang dicurigai.
* **Tugas**:
  1. Buat bash script satu baris (*one-liner*) yang secara otomatis memindai seluruh proses di `/proc` untuk mencari berkas bertanda `(deleted)`.
  2. Hitung total estimasi kapasitas memori/storage yang tertahan oleh file descriptor yatim (*unlinked open files*) tersebut.
* **Verifikasi**: Script menampilkan kolom PID, Nama Proses, Nama Berkas, dan Ukuran Berkas yang tertahan.

### Latihan 3: Advanced - Menulis Program C untuk Membuktikan Isolasi `struct file` pada Single Inode
* **Tugas**:
  1. Tulis kode program C (`vfs_share_test.c`).
  2. Buka satu berkas yang sama dua kali menggunakan pemanggilan `open()` terpisah guna menghasilkan dua `struct file` berbeda di kernel yang mereferensikan `struct inode` yang sama.
  3. Tunjukkan bahwa pembaruan `lseek()` pada FD pertama **tidak mengubah** posisi pembacaan offset pada FD kedua.
  4. Lakukan modifikasi dengan menggunakan `dup()`, dan tunjukkan bahwa duplikasi file descriptor **berbagi** `struct file` yang sama sehingga perubahan `lseek()` pada salah satu FD memengaruhi FD pasangannya.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

**Soal 1**: Struktur data VFS manakah yang bertanggung jawab mengikat nama file tekstual (*path component*) dengan metadata internal filesystem?
* A. `struct file`
* B. `struct super_block`
* C. `struct dentry`
* D. `struct inode`

**Soal 2**: Apa yang terjadi di layer VFS ketika sistem mengeksekusi syscall `close(fd)` pada berkas yang telah dihapus menggunakan `unlink()`, dan tidak ada lagi proses lain yang membuka berkas tersebut?
* A. Kernel mengembalikan dentry ke direktori induk.
* B. `i_nlink` bertambah menjadi 1 secara otomatis.
* C. VFS memicu penghapusan blok data fisik disk dan dealokasi `struct inode`.
* D. File dipindahkan secara otomatis ke folder `/tmp`.

**Soal 3**: Di manakah informasi mengenai *current file offset* (posisi pointer baca/tulis) disimpan dalam arsitektur VFS?
* A. Pada `struct inode`
* B. Pada `struct file`
* C. Pada `struct super_block`
* D. Pada blok fisik LBA hard disk

**Soal 4**: Parameter tuning kernel apa yang digunakan untuk mengatur agresivitas VFS dalam melepaskan Dentry dan Inode dari memory slab?
* A. `fs.file-max`
* B. `vm.dirty_background_ratio`
* C. `vm.vfs_cache_pressure`
* D. `fs.inotify.max_user_watches`

**Soal 5**: Mengapa pemanggilan `dup(oldfd)` menghasilkan dua descriptor yang saling berbagi offset pembacaan data, sedangkan pemanggilan dua kali `open()` pada file yang sama tidak?
* A. `dup()` menduplikasi `struct inode`, sedangkan `open()` tidak.
* B. `dup()` membuat entry baru di `fdtable` yang menunjuk ke instansi `struct file` yang sama; `open()` selalu mengalokasikan `struct file` baru.
* C. `dup()` melewati layer VFS langsung ke disk driver.
* D. `open()` memblokir konkurensi melalui mutex internal superblock.

---

### Kunci Jawaban
1. **C** — `struct dentry` memetakan nama file ke nomor inode terkait dan menyusun struktur hierarki path di RAM.
2. **C** — Saat reference counter pada `struct file` mencapai 0 dan `i_nlink` bernilai 0, VFS memerintahkan driver filesystem konkret untuk membebaskan blok data disk dan menghapus inode.
3. **B** — Posisi offset disimpan di `file->f_pos` pada `struct file`, memungkinkan multiple proses membaca berkas yang sama dengan offset yang independen.
4. **C** — `vm.vfs_cache_pressure` mengatur rasio reklamasi dcache dan icache terhadap page cache.
5. **B** — `dup()` hanya menambah slot pada tabel descriptor proses yang menunjuk ke instansi `struct file` yang sama di kernel space.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi Kernel Linux**:
  * [The Linux Virtual File System Core Documentation](https://docs.kernel.org/filesystems/vfs.html)
  * Linux Source Code: `include/linux/fs.h`, `include/linux/dcache.h`, `fs/open.c`
* **Buku Referensi Standar**:
  * Robert Love. *Linux Kernel Development (3rd Edition)*. Bab 13: "The Virtual Filesystem". Addison-Wesley Professional.
  * Daniel P. Bovet & Marco Cesati. *Understanding the Linux Kernel (3rd Edition)*. Bab 12: "The Virtual Filesystem". O'Reilly Media.
* **LXR / Source Code Cross-Reference**:
  * [Bootlin Elixir Cross Referencer](https://elixir.bootlin.com/linux/latest/source/include/linux/fs.h)

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Abstraksi Universal**: VFS adalah fondasi dari prinsip Unix *"Everything is a file"*, menyediakan API standar bagi userspace terlepas dari media penyimpanan konkret (disk, network, RAM pseudo-fs).
2. **Kuartet Struktur Data Kernel**:
   * `super_block`: Kontrak metadata filesystem level-mount.
   * `inode`: Kontrak metadata entitas berkas individual (ukuran, hak akses, block pointer).
   * `dentry`: Representasi jalur dan hierarki nama berkas di memori.
   * `file`: Representasi berkas aktif yang berinteraksi dengan proses spesifik.
3. **Pemisahan Jalur dan Metadata**: Nama berkas hidup pada `dentry`, bukan pada `inode`. Inode hanya merepresentasikan data fisik dan atribut berkas.
4. **Lifecycle Deletion**: Berkas baru benar-benar terhapus dari blok disk secara fisik jika dan hanya jika **kedua** kondisi ini terpenuhi: *link count* (`i_nlink`) inode bernilai 0 **DAN** semua *file descriptor reference count* pada `struct file` telah ditutup.
5. **Impact Memory**: Dentry dan Inode cache yang tidak dikontrol dapat menghabiskan memori slab kernel, yang dikelola melalui parameter kernel `vm.vfs_cache_pressure`.

---

## SEKSI 17 — GLOSARIUM

1. **VFS (Virtual File System)**: Layer perangkat lunak kernel yang mengabstraksikan fungsi berkas bagi aplikasi userspace.
2. **Superblock**: Struktur data kernel yang memuat metadata keseluruhan partisi/filesystem yang di-mount.
3. **Inode (Index Node)**: Struktur data yang mendefinisikan atribut dan lokasi blok data dari satu objek sistem berkas.
4. **Dentry (Directory Entry)**: Objek memori yang menghubungkan string nama direktori/file dengan inode terkait.
5. **Dcache (Dentry Cache)**: Kolam memori di RAM yang menyimpan struktur dentry aktif untuk mempercepat resolusi path.
6. **File Descriptor (FD)**: Indeks integer non-negatif per-proses yang berfungsi sebagai handle untuk mengakses `struct file`.
7. **Slab Allocator**: Mekanisme alokasi memori internal kernel Linux untuk struktur data yang sering digunakan berulang (seperti dentry dan inode).
8. **Link Count (`i_nlink`)**: Nilai integer pada inode yang menghitung jumlah hardlink (nama dentry) yang mereferensikannya.
9. **Operations Vector**: Tabel array berisi function pointers (`inode_operations`, `file_operations`) yang mengimplementasikan pemanggilan fungsi polymorphic dalam bahasa C.
10. **Path Resolution**: Proses traversal bertahap dari komponen string path (misal: `/a/b/c`) menjadi representasi objek dentry dan inode target.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan Materi**:
  * Sangat ditekankan untuk tidak membiarkan siswa membayangkan inode memiliki nama file. Gunakan analogi: Inode adalah *Rumah Fisik* (memiliki koordinat geolokasi, luas tanah, nomor sertifikat), sedangkan Dentry adalah *Kartu Nama/Buku Telepon* yang memetakan nama pemilik ke alamat rumah tersebut.
  * Tunjukkan secara visual skenario *ghost space usage* (Seksi 09) di sesi lab langsung. Ini adalah insiden produksi paling umum yang sering membingungkan SysAdmin pemula.
* **Perangkap Pedagogis (Common Pitfalls)**:
  * Siswa sering keliru mengira `lsof` membaca disk. Jelaskan bahwa `lsof` hanya membaca `/proc` yang merupakan proyeksi data VFS di memori.
  * Hati-hati saat menjelaskan kaitan `Page Cache` vs `Buffer Cache`. Pada kernel modern (>2.4), Buffer Cache telah terintegrasi ke dalam Page Cache VFS.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: 1.0.0
* **Tanggal**: 2026-05-12
* **Penyusun**: Senior Technical Curriculum Architect
* **Catatan Perubahan**:
  * Rilis modul inisial standar GEMINI.md 20 Seksi.
  * Penambahan diagram ASCII relasi proses ke VFS structs.
  * Penambahan skrip praktis Python untuk reproduksi penahanan file descriptor pasca-unlink.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `LIN-01-02-03` — Process Scheduling, CFS, & Real-Time Priorities
* **Modul Saat Ini**: `LIN-01-03-01` — Virtual File System (VFS) Architecture & Abstraction
* **Modul Berikutnya**: `LIN-01-03-02` — Concrete Filesystem Internals: ext4, XFS, and Block Allocation Mechanisms