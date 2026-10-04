# Kurikulum Linux: 01-Core-Foundations
## Bab 09 Module 01: Arsitektur Virtual File System (VFS) dan Metadata Inode

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
* Membedah arsitektur internal Linux Virtual File System (VFS) dan mengidentifikasi siklus hidup empat objek kunci kernel: `superblock`, `inode`, `dentry`, dan `file`.
* Mendiagnosis dan menyelesaikan insiden disk exhaustion yang disebabkan oleh kehabisan metadata (*inode starvation*) terlepas dari kapasitas penyimpanan fisik (*byte space*) yang masih tersedia.
* Mengaudit dan mereklamasi kapasitas media penyimpanan yang tertahan akibat *unlinked open file descriptors* menggunakan inspeksi subsistem `/proc`.
* Menganalisis alokasi blok data, *extents*, dan fragmentasi metadata pada filesystem Ext4/XFS menggunakan perangkat investigasi tingkat rendah (*low-level inspection tools*) seperti `debugfs` dan `xfs_db`.

---

### 2. Prerequisite
* Pemahaman fundamental mengenai Linux System Calls (`open()`, `read()`, `write()`, `close()`, `stat()`, `unlink()`).
* Kemampuan navigasi CLI dan manipulasi berkas dasar.
* Pemahaman dasar tentang struktur data kernel C (pointers, structs, double-linked lists).
* Hak akses root atau sudoers pada environment Linux berbasis kernel modern (>= 5.4).

---

### 3. Concept
Linux mengimplementasikan paradigma *"Everything is a file"*. Untuk memfasilitasi integrasi transparan dari berbagai format sistem berkas (misalnya Ext4, XFS, Btrfs, NFS, hingga sistem berkas pseudo seperti `/proc` dan `/sys`), kernel Linux menyediakan lapisan abstraksi yang disebut **Virtual File System (VFS)**.

```
+-------------------------------------------------------------------+
|                        User Space Application                     |
|            (glibc open(), read(), write(), close())               |
+-------------------------------------------------------------------+
                                  | System Call Interface
+-------------------------------------------------------------------+
|                       Virtual File System (VFS)                   |
|   +-------------------+  +-----------------+  +---------------+   |
|   | struct super_block|  |  struct dentry  |  |  struct inode |   |
|   +-------------------+  +-----------------+  +---------------+   |
|                           +---------------+                       |
|                           |  struct file  |                       |
|                           +---------------+                       |
+-------------------------------------------------------------------+
             |                              |                |
             v                              v                v
+------------------------+      +------------------+   +------------+
| Ext4 Filesystem Driver |      |   XFS Driver     |   | NFS Driver |
+------------------------+      +------------------+   +------------+
             |                              |                |
             +------------------------------+----------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                           Block Layer                             |
|          (I/O Scheduler, Request Queue, bio structures)           |
+-------------------------------------------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|               Device Drivers & Physical Media (NVMe/SATA)         |
+-------------------------------------------------------------------+
```

VFS mendefinisikan interface generik standar yang wajib diimplementasikan oleh setiap driver sistem berkas. Ada empat struktur data utama dalam memori kernel:

1. **`super_block`**: Merepresentasikan filesystem yang ter-mount secara utuh. Menyimpan metadata global sistem berkas (ukuran blok, status *read-only*/*read-write*, magic number, dan pointer ke operasi sistem berkas).
2. **`inode` (Index Node)**: Merepresentasikan objek berkas fisik tertentu secara independen dari namanya. Menyimpan ukuran berkas, user ID (UID), group ID (GID), izin akses, *timestamps* (ctime, atime, mtime), pointer ke blok data fisik, dan referensi link count. Inode **tidak** menyimpan nama berkas atau data aktual berkas.
3. **`dentry` (Directory Entry)**: Menghubungkan nama jalur (*path*) dengan nomor inode. Dentry memfasilitasi resolusi jalur berkas secara cepat melalui *dentry cache* (`dcache`) di memori utama, menghindari pembacaan berulang ke media penyimpanan.
4. **`file`**: Merepresentasikan instance berkas yang sedang dibuka oleh suatu proses. Dibuat di memori saat system call `open()` berhasil dan dimusnahkan saat `close()`. Berisi posisi pembacaan saat ini (*file offset*), flags status (*read/write*), dan relasi ke dentry terkait.

---

### 4. Why
Memahami VFS dan Inode bukan sekadar kebutuhan teoritis kernel programming, melainkan persyaratan fundamental dalam rekayasa keandalan sistem (*Site Reliability Engineering*):
* **Disk Space Paradox**: Sistem operasi dapat melempar galat `ENOSPC: No space left on device` padahal kapasitas penyimpanan tersisa puluhan gigabyte jika inode tabel terisi penuh (100% inode saturation).
* **Phantom Disk Usage**: Menghapus berkas (`rm -f payload.log`) saat proses (seperti daemon database atau reverse proxy) masih menahan berkas tersebut terbuka (*open file descriptor*) tidak akan membebaskan blok data fisik pada filesystem. Storage tetap terpakai, memicu *disk alerting trigger* tak kasat mata.
* **I/O Bottlenecks**: Pembuatan jutaan direktori flat berdampak langsung pada latensi traversal jalur berkas akibat degradasi performa dcache/hash bucket lookup.
* **Disaster Recovery**: Memahami struktur alokasi inode dan *extents* memungkinkan proses forensik dan *carving* pemulihan data ketika superblock atau partition table mengalami kerusakan parah.

---

### 5. What
Komponen dan metadata esensial dalam arsitektur VFS:

* **Inode Number**: Identifier integer unik dalam batasan suatu filesystem. Di luar batasan filesystem tersebut, inode number yang sama bisa merepresentasikan entitas yang sama sekali berbeda.
* **Hard Link**: Entri dentry baru yang menunjuk langsung ke nomor inode yang sudah ada. Menginkrementasi `i_nlink` pada inode. Penghapusan hardlink hanya memutus nama dentry; data tetap ada selama `i_nlink > 0`.
* **Symbolic Link (Soft Link)**: Berkas khusus yang memiliki inode independen, dengan blok data yang berisi string berupa path menuju berkas target.
* **Extents**: Mekanisme pemetaan blok modern (standar pada Ext4 dan XFS) yang menggantikan *indirect block pointers*. Extent merepresentasikan rentang blok logis ke blok fisik secara kontigu (misalnya: "mulai dari blok logis 0, petakan ke 1024 blok fisik berurutan"), mereduksi jejak metadata secara masif.
* **File Descriptor Table**: Struktur per-proses di user-kernel boundary yang memetakan integer non-negatif (*file descriptor*) ke `struct file` kernel.

---

### 6. How
Alur kerja komprehensif penanganan I/O saat sebuah proses memanggil `open("/var/log/app.log", O_RDWR)`:

```
[ User Application ] -> sys_open("/var/log/app.log", O_RDWR)
         |
         v
[ VFS Path Resolution ]
   |
   +--> Periksa VFS Path Lookup: Root '/' (dentry root)
   |
   +--> Cek 'dcache' untuk entri 'var' -> resolve Inode 'var'
   |        |
   |        +--> Cek dcache 'log' -> resolve Inode 'log'
   |                 |
   |                 +--> Cek dcache 'app.log' -> resolve Inode 'app.log'
   |                      (Jika dentry cache miss: Baca blok direktori dari disk,
   |                       populate dentry ke RAM dcache)
   v
[ I/O Permission Check ]
   Kernel memvalidasi izin akses DAC (Discretionary Access Control: UID/GID)
   dan MAC (SELinux/AppArmor) terhadap struct inode milik 'app.log'.
   |
   v
[ Objek Kernel Dibangun ]
   Kernel mengalokasikan 'struct file' di memori:
   - Inisialisasi file offset = 0
   - Kaitkan f_ops (fungsi operasi driver filesystem: ext4_file_operations)
   - Kaitkan pointer f_path.dentry ke dentry 'app.log'
   |
   v
[ File Descriptor Mapping ]
   Kernel mencari slot kosong terendah pada tabel berkas proses (process fdtable),
   misal slot index '3', dan mengarahkannya ke 'struct file'.
   |
   v
[ Return ] -> Mengembalikan integer '3' ke User Space.
```

---

### 7. Analogy
Bayangkan sebuah arsip nasional raksasa:
* **Storage Device**: Gedung arsip fisik berisi jutaan rak kontainer (*data blocks*).
* **Superblock**: Denah utama gedung di pintu masuk yang mencatat luas total, jumlah kapasitas rak, dan lokasi rak yang rusak.
* **Inode**: Buku induk arsip. Setiap halaman bernomor unik (*inode number*), mencatat siapa yang memasukkan arsip, izin akses, tebal berkas, serta daftar nomor rak fisik tempat dokumen disimpan. Halaman ini **tidak mencatat nama judul dokumen**.
* **Dentry**: Label kartu gantung indeks katalog. Label menuliskan "Akta Perusahaan X" (*filename*) dan mencatat nomor halaman buku induk (*inode*). Anda bisa membuat dua label berbeda (Hardlink) yang mengarah ke nomor halaman buku induk yang persis sama.
* **File Struct & Descriptor**: Formulir peminjaman aktif yang dipegang staf saat membaca dokumen. Formulir mencatat di baris mana staf sedang membaca (*file offset*), bukan dokumen itu sendiri.

---

### 8. Diagram

```
+---------------------------------------------------------------------------------+
|                               Process Memory Space                              |
|                                                                                 |
|  +--------------------+                                                         |
|  | File Descriptor    |                                                         |
|  | Table              |                                                         |
|  | [0] stdin          |                                                         |
|  | [1] stdout         |                                                         |
|  | [2] stderr         |                                                         |
|  | [3] ----------+    |                                                         |
|  +---------------+----+---------------------------------------------------------+
|                  |
|                  v (Kernel Space)
|  +-----------------------------------+
|  | struct file                       |
|  |   f_pos: 4096 (Current Offset)    |
|  |   f_flags: O_RDONLY               |
|  |   f_dentry -----------------------+
|  +-----------------------------------+
|                                      |
|                                      v
|  +---------------------------------------------------------------------------+
|  | struct dentry (Directory Cache)                                           |
|  |   d_name: "app.log"                                                       |
|  |   d_parent: -> dentry("log")                                              |
|  |   d_inode ------------------------+                                       |
|  +-----------------------------------+---------------------------------------+
|                                      |
|                                      v
|  +---------------------------------------------------------------------------+
|  | struct inode (Ext4/XFS Metadata)                                          |
|  |   i_ino: 1441852                                                          |
|  |   i_size: 1048576 Bytes                                                   |
|  |   i_links_count: 1                                                        |
|  |   i_blocks: 2048                                                          |
|  |   i_data_extents -----------------+                                       |
|  +-----------------------------------+---------------------------------------+
|                                      |
|                                      v
|  +---------------------------------------------------------------------------+
|  | Physical Storage Block Layer                                              |
|  | [Block 0x9AF0] -> [Block 0x9AF1] -> [Block 0x9AF2] -> [Block 0x9AF3] ...  |
|  +---------------------------------------------------------------------------+
```

---

### 9. Simple Example
Eksplorasi nomor inode, hardlink, dan penanganan struktur berkas menggunakan utilitas inti Linux.

```bash
# Buat direktori pengujian terisolasi
mkdir -p /tmp/vfs-lab && cd /tmp/vfs-lab

# 1. Buat berkas baru dan inspeksi atribut metadata
echo "System Engineering Linux Foundation" > origin.txt
stat origin.txt
```
Output mencakup data:
* `File`: origin.txt
* `Size`: 36
* `Blocks`: 8
* `IO Block`: 4096 (regular file)
* `Device`: 259/2 (Device major/minor)
* `Inode`: 3934521
* `Links`: 1

```bash
# 2. Buat hardlink dan buktikan nomor inode serta referensi count
ln origin.txt hardlink.txt
ls -li origin.txt hardlink.txt
```
Hasil:
* Kedua berkas menunjukkan inode yang **identik** (misal: `3934521`).
* Kolom link count melonjak dari `1` menjadi `2`.

```bash
# 3. Buat symlink (softlink)
ln -s origin.txt symlink.txt
ls -li origin.txt symlink.txt
```
Hasil:
* `symlink.txt` memiliki nomor inode yang **berbeda**.
* Link count pada `origin.txt` tetap `2`. Inode symlink hanya menyimpan string rujukan `"origin.txt"`.

---

### 10. Practical Example
Investigasi *unlinked open file descriptors* yang mengonsumsi kapasitas disk tanpa terdeteksi oleh `du`, serta mekanisme pemulihannya.

#### Skenario Masalah:
Sebuah daemon menulis log berukuran masif. Seorang operator mengeksekusi `rm -f app.log`. Perintah `df -h` menunjukkan filesystem penuh (100%), namun perintah `du -sh /var/log` menunjukkan penggunaan ruang yang kecil.

#### Eksekusi Lab:

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Buat proses latar belakang yang menahan file descriptor terbuka
python3 -c '
import time, os
with open("/tmp/leaked_resource.bin", "wb") as f:
    f.write(b"\x00" * 1024 * 1024 * 200) # Alokasi 200MB dummy payload
    f.flush()
    print("Process PID running:", os.getpid())
    while True:
        time.sleep(1)
' &
PID=$!
sleep 2

# 2. Hapus referensi dentry dari filesystem namespace
rm -f /tmp/leaked_resource.bin

# 3. Validasi status menggunakan du vs lsof
echo "=== Pengecekan dengan du ==="
du -sh /tmp/leaked_resource.bin 2>/dev/null || echo "File tidak ditemukan via du traversal!"

echo "=== Pengecekan melalui VFS open descriptor leaks ==="
lsof +L1 | grep "/tmp" || true
```

#### Pemulihan Data Langsung dari Inode Descriptor (Tanpa Mematikan Proses):
Meskipun dentry telah terhapus, VFS mempertahankan struktur `inode` dan data blocks selama *reference count* pada `struct file` di proses aktif masih ada.

```bash
# Identifikasi file descriptor indeks dari proses
ls -l /proc/${PID}/fd/

# Output menunjukkan symbolic link yang mengarah ke berkas bertanda (deleted)
# misal: 3 -> /tmp/leaked_resource.bin (deleted)

# Lakukan recovery data mentah secara deterministik langsung via procfs
cat /proc/${PID}/fd/3 > /tmp/recovered_payload.bin

# Verifikasi integritas ukuran pemulihan
ls -lh /tmp/recovered_payload.bin

# Terminasi proses untuk melepaskan inode & mengembalikan blok disk ke free pool
kill -9 "${PID}"
wait "${PID}" 2>/dev/null || true
```

---

### 11. Real World Example
**Insiden Post-Mortem: "Ghost Outage" pada Klaster Node Kubernetes**

* **Konteks**: Node pekerja (*worker node*) Kubernetes berbasis Ubuntu LTS pada sebuah platform e-commerce skala besar mendadak berubah status menjadi `NotReady` dengan kondisi `DiskPressure: True`.
* **Anomali**: Observabilitas host via Prometheus Node Exporter melaporkan penggunaan media penyimpanan NVMe pada root partition `/` mencapai 100%. Namun saat tim SRE mengeksekusi `du -xsh /*` untuk mencari direktori dengan footprint terbesar, agregasi direktori hanya menghasilkan total 42 GB dari total kapasitas 200 GB.
* **Investigasi Mendalam**:
  1. Pemeriksaan metadata inode via `df -i /` membuktikan bahwa penggunaan inode berada pada kisaran wajar (14%). Kegagalan murni terjadi pada blok data.
  2. Eksekusi analisis referensi kernel descriptor:
     ```bash
     lsof -nP +L1 | grep deleted | sort -nr -k 7 | head -n 10
     ```
  3. Ditemukan bahwa engine rotasi log bawaan aplikasi backend (Node.js engine) memicu `fs.unlink()` terhadap file log aktif, namun daemon runtime aplikasi tersebut tidak pernah menutup file descriptor (`close()`). 
  4. Aplikasi terus memuntahkan payload log ke fd 14 hingga mencapai 150 GB data fisik. Blok fisik tidak direklamasi oleh sistem operasi karena VFS menjaga status inode tetap hidup selama pointer fd aktif di tabel `fdtable`.
* **Resolusi & Mitigasi Arsitektural**:
  * Mengirim sinyal peredaan descriptor ke PID aplikasi via mekanisme logrotate menggunakan opsi `copytruncate` atau memastikan implementasi *signal-driven re-opening* (SIGHUP handler).
  * Menambahkan monitor proaktif Prometheus terhadap metrik `node_filesystem_files_free` dan `node_filefd_allocated`.

---

### 12. Trade-offs

| Aspek | Dentry Caching (In-Memory Lookup) | Direct Inode Traversal (No Cache) |
|---|---|---|
| **Advantages** | Kecepatan lookup mendekati latensi memori (nanodetik). Menghilangkan I/O disk untuk resolusi path. | Mengurangi jejak alokasi kernel slab RAM (`dentry` & `inode_cache`). Bebas dari resiko *stale cache*. |
| **Disadvantages** | Mengonsumsi RAM kernel. Pada struktur direktori masif, dapat memicu alokasi memori slab tak terkendali. | Latensi sistem meningkat drastis. Beban I/O baca meningkat pada storage layer per system call traversal. |
| **Complexity** | Sangat tinggi; kernel harus menjaga sinkronisasi status dcache dengan RCU locks. | Sangat rendah; pembacaan berulang secara linear/b-tree dari disk. |
| **Performance** | Tingkat operasi read/write throughput tinggi (ratusan ribu ops/detik). | Tercekik oleh limit IOPS media penyimpanan underlying. |
| **Cost** | Footprint konsumsi memori fisik (RAM) server lebih tinggi. | Biaya komputasi dan wear-out hardware disk lebih tinggi. |

---

### 13. When To Use
* **Penyelidikan Ketidaksesuaian Disk Space**: Gunakan abstraksi VFS dan inode (`lsof +L1`) ketika metrik `df` dan `du` bertolak belakang.
* **Filesystem Format Sizing**: Tentukan perbandingan inode vs blok data secara eksplisit menggunakan `mkfs -i` (bytes-per-inode ratio) jika sistem akan menangani use case spesifik seperti *small-files micro-storage* (contoh: image thumbnail storage atau maildir format).
* **High-Throughput IO Tuning**: Terapkan opsi mount `noatime` atau `relatime` untuk menghentikan write amplification ke inode metadata setiap kali file diakses (`read`).

---

### 14. When NOT To Use
* **Object Storage Pure Systems**: Jangan memaksakan struktur berkas posix hierarkis standar (VFS Ext4/XFS lokal) untuk melayani ratusan juta objek berkas tak terstruktur. Gunakan arsitektur penyimpanan berbasis objek (S3 API, MinIO, Ceph RADOS) yang mengeliminasi konsep inode bottleneck secara terdistribusi.
* **In-Memory Volatile Key-Value**: Jangan mengandalkan penulisan file fisik dengan VFS overhead untuk data transien yang membutuhkan sub-millisecond roundtrip; gunakan subsistem in-memory murni (Redis/Memcached) atau `tmpfs` jika mutlak butuh mount namespace.

---

### 15. Common Mistakes
* **Salah Kaprah Menghapus File Aktif**: Menghapus file log yang sedang ditulis oleh proses aktif (`rm database.log`) dengan asumsi ruang disk akan bebas. Cara benar adalah mengosongkan entitas via truncate: `truncate -s 0 database.log` atau `: > database.log`.
* **Mengabaikan Inode Exhaustion**: Hanya membuat monitoring peringatan untuk kapasitas persentase ukuran disk (`df -h`), tanpa memonitor kuota inode (`df -i`). Banyak aplikasi crash dengan status *disk full* padahal kapasitas blok masih tersisa 80%.
* **Asumsi Hard Link Lintas Device**: Mencoba membuat hardlink antara dua mount point atau partisi yang berbeda (`ln /mnt/vol1/a /mnt/vol2/b`). VFS melarang hal ini dan melempar `EXDEV: Invalid cross-device link` karena inode number terikat pada filesystem unik lokal.

---

### 16. Best Practices (Production Checklist)

1. [ ] **Mount with `noatime`**: Pasang filesystem database/aplikasi dengan flag `noatime` pada `/etc/fstab` guna mengeliminasi modifikasi metadata inode secara konstan pada operasi baca.
2. [ ] **Monitor Inode Saturation**: Setel alert threshold monitoring (Prometheus/Datadog) untuk batas penggunaan inode pada 80%.
3. [ ] **Validasi Unlinked Files**: Rutin audit zombie file descriptors menggunakan automasi script berbasis `lsof +L1` atau pengecekan `/proc/*/fd/`.
4. [ ] **Atur Dentry Cache Pressure**: Lakukan evaluasi nilai kernel `/proc/sys/vm/vfs_cache_pressure` (default: 100). Naikkan ke 150-200 jika sistem kehabisan memori akibat slab dentry cache yang tidak mau lepas, atau pertahankan 100 jika kinerja lookup direktori diprioritaskan.
5. [ ] **Karantina Direktori Datar Ekstrem**: Batasi jumlah entri file dalam satu direktori tunggal maksimal < 100.000 file untuk mencegah degradasi performa dentry hash table lookup, sekalipun filesystem modern mendukung *dir_index* (HTree).

---

### 17. Troubleshooting

#### Masalah 1: `No space left on device`, tetapi `df -h` menunjukkan sisa ruang puluhan GB.
* **Diagnosis**:
  ```bash
  df -i /
  ```
* **Hasil**: Inode usage 100% (IFree = 0).
* **Solusi**: Cari direktori dengan konsentrasi file terbanyak menggunakan traversal script:
  ```bash
  find / -xdev -printf '%h\n' | sort | uniq -c | sort -k 1 -nr | head -n 20
  ```
  Hapus jutaan berkas kecil tak berguna (misalnya tumpukan PHP session tokens atau spooling mails):
  ```bash
  find /var/spool/clientmqueue -type f -delete
  ```

#### Masalah 2: `df -h` terus 100% setelah penghapusan berkas log besar.
* **Diagnosis**:
  ```bash
  lsof +L1 /var
  ```
* **Hasil**: Ditemukan entry bertanda `(deleted)` dengan size kolom signifikan dan referensi PID aktif.
* **Solusi**: Kosongkan file descriptor target secara dinamis tanpa me-restart service:
  ```bash
  # Truncate langsung ke alamat file descriptor di procfs
  : > /proc/<PID>/fd/<FD_NUM>
  ```

---

### 18. Exercise
1. **Inspeksi Metadata Extents Rendah**:
   Buat file berukuran 10MB berisi karakter acak pada filesystem Ext4, lalu gunakan perintah `debugfs` (mode interaktif atau `-R`) untuk memeriksa nomor inode, mode, serta struktur pemetaan alokasi *extents* fisiknya.
2. **Rekayasa Inode Starvation Terkendali**:
   Gunakan partisi *loopback device* berukuran kecil (misal 50MB) yang di-format dengan Ext4. Buat script loop yang meng-generate ribuan berkas kosong ukuran 0 byte hingga operasi melempar error `No space left on device`. Buktikan statusnya menggunakan `df -h` versus `df -i`.
3. **Simulasi Reklamasi Broken Hardlink**:
   Buat sebuah file dengan dua hardlink. Hapus file sumber pertama. Tunjukkan bahwa data tetap dapat diakses via hardlink kedua. Verifikasi transisi nilai `Links` pada `stat` dari 2 menjadi 1.

---

### 19. Challenge
**Mission: Zero-Downtime Data Resurrect from a Compromised Daemon**

* **Kondisi**:
  Sebuah microservice kritis penanganan pembayaran (`PID 4082`) memiliki bug memori: service tidak boleh di-restart selama jam bursa operasional. Microservice ini secara tidak sengaja memicu operasi penghapusan berkas transaksi krusial `/data/tx_payload.dat` yang belum sempat direplikasi ke database utama.
* **Instruksi Eksekusi**:
  1. Buktikan secara empiris bahwa data masih ada di level block storage meskipun dentry terhapus menggunakan interface `/proc`.
  2. Ekstrak data mentah tersebut ke partisi cadangan yang aman `/mnt/backup/rescued_tx.dat`.
  3. Hitung dan cocokkan checksum SHA256 dari payload hasil recovery terhadap stream descriptor yang sedang dibuka di memori proses, buktikan keidentikan tanpa menghentikan thread eksekusi proses utama sedikit pun.

---

### 20. Summary
* **Abstraksi VFS** memungkinkan Linux memperlakukan sistem penyimpanan apa pun secara seragam di user space melalui serangkaian objek memori internal: `super_block`, `inode`, `dentry`, dan `file`.
* **Inode** adalah inti dari metadata objek berkas; ia mengisolasi identitas dan pemetaan blok fisik berkas dari representasi nama tekstualnya.
* **Dentry** adalah tautan nama-ke-inode yang dicache dalam RAM untuk mereduksi latensi resolusi direktori.
* **Kapasitas Penyimpanan** terdiri dari dua dimensi independen: ruang blok byte fisik (*block allocation*) dan ruang metadata (*inode allocation*). Defisit pada salah satu dimensi akan melumpuhkan fungsionalitas I/O penyimpanan.
* Operasi penghapusan berkas di Linux (`unlink`) tidak secara otomatis memusnahkan data; alokasi blok fisik hanya akan dibebaskan kembali ke pool kernel apabila `i_nlink == 0` **dan** seluruh *open file descriptors* yang merujuk pada `inode` tersebut telah ditutup secara sempurna.