# BAB 06: Quiz, Challenge, & Knowledge Check
**Bab 06: Arsitektur Sistem I/O, Virtual File System (VFS), dan Mekanisme Penyimpanan Sekunder**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Evolusi Arsitektur Transfer I/O:**
   Jelaskan transisi komputasi dari *Programmed I/O (Polling)* ke *Interrupt-Driven I/O*, hingga *Direct Memory Access (DMA)*. Bagaimana *Scatter-Gather DMA* mengoptimalkan transfer memori non-kontigu, dan apa dampaknya terhadap overhead utilisasi CPU serta *bus contention* pada arsitektur modern?

2. **Topologi Abstraksi File System (Inodes vs. Extents):**
   Bandingkan arsitektur penyimpanan berbasis *indirect pointer block* (klasik Unix FFS) dengan arsitektur berbasis *extents* (misalnya pada Ext4 atau XFS). Mengapa arsitektur berbasis *extents* secara signifikan memitigasi fragmentasi metadata dan meningkatkan performa alokasi untuk berkas berukuran gigabyte hingga terabyte?

3. **Anatomi File Descriptors dan Tabel Kernel:**
   Uraikan hubungan struktural antara *Per-Process File Descriptor Table*, *System-Wide Open File Table*, dan *VFS Inode Table* di dalam kernel Linux. Apa yang terjadi pada ketiga tabel tersebut saat sebuah proses memanggil `fork()`, kemudian child process mengeksekusi `dup2()`, lalu membuka kembali file yang sama via `open()`?

4. **Kernel Page Cache vs. Direct I/O (`O_DIRECT`):**
   Jelaskan siklus hidup pembacaan data dari disk menuju *user-space buffer* melalui Linux Page Cache (termasuk *read-ahead* dan alokasi `struct page`). Dalam kondisi dan karakteristik beban kerja seperti apa *Page Cache* justru menjadi sumber degradasi latensi (*double buffering*, memory pressure), sehingga penggunaan `O_DIRECT` wajib diimplementasikan?

5. **Crash Consistency & Paradigma Journaling:**
   Jelaskan fenomena *Crash Consistency Problem* ketika sistem crash di tengah operasi penulisan data dan metadata. Bandingkan secara mekanis bagaimana *Write-Ahead Logging (Journaling)* pada mode **Journaled (Data + Metadata)**, **Ordered**, dan **Writeback** menyelesaikan masalah inkonsistensi tanpa harus menjalankan full storage scan (`fsck`).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Analisis Semantik Flushing: `fsync()` vs. `fdatasync()` vs. Directory Sync:**
   Jelaskan perbedaan mendasar operasi perangkat keras antara `fsync()` dan `fdatasync()`. Mengapa aplikasi yang melakukan pola penulisan *atomic file replace* (tulis ke `.tmp`, lalu eksekusi `rename()`) tetap berisiko kehilangan data atau mengalami *zero-length file* pasca power loss jika tidak memanggil `fsync()` secara eksplisit pada *parent directory descriptor*?

2. **NVMe, Flash Translation Layer (FTL), dan Write Amplification:**
   Pada Solid-State Drive (SSD), jelaskan interaksi antara *Out-of-Place Updates*, ukuran *Erase Block* vs. *Write Page*, dan proses *Garbage Collection* di level FTL. Bagaimana rumus matematis *Write Amplification Factor (WAF)* bekerja, dan mengapa *unaligned 4KB random writes* menghancurkan durabilitas serta memicu lonjakan latensi P99?

3. **Evolusi I/O Multiplexing: `epoll` vs. `io_uring`:**
   Meskipun `epoll` efisien untuk *network sockets*, mengapa `epoll` tidak dapat digunakan untuk *asynchronous disk I/O* di kernel Linux? Bedah bagaimana arsitektur *ring buffer* berbasis *lockless shared-memory* (Submission Queue & Completion Queue) pada `io_uring` mengeliminasi *system call overhead* dan *context switch* secara radikal.

4. **Investigasi Anomali Storage: `ENOSPC` pada Disk Berkapasitas Longgar:**
   Sebuah *production service* melempar galat `No space left on device` (POSIX error `ENOSPC`), padahal perintah `df -h` menunjukkan ruang kosong sebesar 45%. Rancang langkah analisis sistemik menggunakan utilitas Linux untuk mendiagnosis tiga penyebab berbeda: *inode exhaustion*, *deleted unlinked files yang masih di-hold oleh active process descriptors*, dan *reserved blocks* untuk superuser.

5. **Memory-Mapped I/O (`mmap`) Under the Hood:**
   Bedah alur eksekusi saat aplikasi membaca berkas via `mmap()`: mulai dari manipulasi *Virtual Memory Area (VMA)*, terjadinya *major page fault*, translasi page table, hingga interaksi dengan I/O scheduler. Apa risiko teknis dari *TLB shootdown* dalam arsitektur multi-threaded dan bagaimana kernel menangani sinyal `SIGBUS` jika file underlying dipotong (*truncated*) oleh proses lain secara konkuren?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spike Akibat Dirty Page Flushing Throttle
Sistem basis data transaksional relasional berskala besar (OLTP) berjalan di atas kernel Linux dengan penyimpanan NVMe berkecepatan tinggi. Pada jam sibuk, metrik aplikasi menunjukkan lonjakan latensi P99 dari 1.5 milidetik menjadi lebih dari 2.200 milidetik secara periodik (terjadi setiap ~30 detik). Analisis awal via `vmstat` dan `iostat` menunjukkan bahwa selama periode lonjakan, *I/O wait* melonjak tinggi dan ratusan *worker threads* masuk ke status `D` (*Uninterruptible Sleep*). Ditemukan bahwa nilai kernel parameter default:
- `vm.dirty_background_ratio = 10`
- `vm.dirty_ratio = 20`
*Physical Memory* server adalah 512 GB.

**Tugas Evaluasi & Remediasi:**
1. Jelaskan rantai kausalitas internal kernel Linux yang menyebabkan *worker threads* aplikasi terblokir ke status `D` akibat konfigurasi dirty ratio berbasis persentase tersebut.
2. Hitung berapa gigabyte data kotor (*dirty data*) yang harus diakumulasi sebelum kernel memaksa proses aplikasi melakukan *synchronous write-back* (flushing throttle).
3. Rancang rekonfigurasi kernel sysctl (`vm.dirty_*_bytes` vs `vm.dirty_*_ratio`, `dirty_expire_centisecs`) dan strategi I/O scheduler/cgroup v2 I/O throttling untuk meratakan kurva penulisan ke disk dan mengeliminasi fluktuasi latensi P99.

---

### Skenario B: Kerusakan Data Post-Crash dan Volatilitas Write Caching
Sebuah kluster terdistribusi berbasis consensus engine (Raft log) mengalami *hard power loss* mendadak di data center. Setelah server menyala kembali, salah satu node mengalami kegagalan inisialisasi state machine karena segmen log biner terakhir mengalami korupsi data (*torn write / partial block flush*), padahal implementasi software memanggil `fsync()` pada setiap commit dan menerima return code `0` (Success). Investigasi perangkat keras mengungkap bahwa media penyimpanan yang digunakan adalah Enterprise SATA SSD tanpa *Power Loss Protection (PLP)* kapasitor hardware, dan parameter filesystem di-mount dengan opsi default.

**Tugas Evaluasi & Remediasi:**
1. Bedah secara mendalam bagaimana disk internal *volatile write cache* dapat "membohongi" return status `fsync()` kernel jika *Write Barriers* atau perintah *SCSI SYNCHRONIZE CACHE / ATA FLUSH CACHE* dinonaktifkan atau diabaikan oleh disk controller.
2. Bagaimana mekanisme *Torn Write* terjadi di level physical sector (512e vs 4Kn), dan mengapa write barrier gagal melindungi integritas berkas jika filesystem di-mount dengan opsi semacam `barrier=0` (atau `nobarrier`)?
3. Rancang arsitektur verifikasi end-to-end: Konfigurasi mount flag filesystem apa yang wajib diterapkan, perintah kernel mana yang memverifikasi kapabilitas *Volatile Write Cache* (via `hdparm` atau `smartctl`), dan bagaimana desain software storage engine harus memanfaatkan teknik *checksumming + double-write buffer* untuk memulihkan diri dari *torn writes*?

---

### Skenario C: Trade-off Arsitektur Storage Engine: B+ Tree vs. LSM-Tree
Perusahaan teknologi IoT merancang platform ingest data telemetri yang harus menelan rata-rata 350.000 events/detik (tiap event berukuran 256 bytes) secara kontinu 24/7. Pola akses data didominasi oleh penulisan (*heavy sequential/random ingestion* 95%), sedangkan pembacaan data (*reads* 5%) hampir secara eksklusif merupakan *range query* untuk rentang waktu 15 menit terakhir. Tim infrastruktur memperdebatkan dua fondasi storage engine: Storage Engine A berbasis **In-Place Update B+ Tree** (seperti arsitektur WiredTiger/InnoDB) dan Storage Engine B berbasis **Log-Structured Merge (LSM) Tree** (seperti arsitektur RocksDB/Cassandra).

**Tugas Evaluasi & Remediasi:**
1. Bandingkan pola I/O fisik yang dihasilkan oleh B+ Tree versus LSM-Tree pada layer block storage. Mengapa pola *in-place update* pada B+ Tree menyebabkan degradasi throughput yang parah (*random I/O amplification*) pada skenario ini?
2. Analisis komparatif trade-off struktural antara kedua engine dengan meninjau empat parameter: **Write Amplification (WA)**, **Read Amplification (RA)**, **Space Amplification (SA)**, serta dampak proses **Compaction (LSM)** versus **Page Splits (B+ Tree)** terhadap keausan SSD.
3. Berikan rekomendasi arsitektur final: Pilih engine yang paling optimal untuk skenario ini, sertakan detail rancangan pendukung (seperti *MemTable*, *SSTable*, *Bloom Filter*, dan *Write-Ahead Log*) untuk menjamin data persistensi tanpa mengorbankan target throughput ingestion.

---

## 4. Chapter Challenge

**Tantangan Praktis: Membangun Crash-Consistent Append-Only Key-Value Storage Engine (Bitcask Architecture)**

### Deskripsi Masalah
Banyak sistem penyimpanan produksi modern menghindari kompleksitas B+ Tree dengan mengadopsi model *Log-Structured Append-Only Storage* yang dipadukan dengan *In-Memory Hash Index*. Anda ditugaskan untuk mengimplementasikan sebuah embedded Key-Value Store sederhana bernama **"MiniCask"** (terinspirasi dari model arsitektur Bitcask paper) dari level sistem menggunakan bahasa berorientasi performa (C, Rust, atau Go) tanpa menggunakan library storage pihak ketiga.

### Persyaratan Fungsional & Non-Fungsional
1. **Format File Biner Append-Only:**
   Setiap entri penulisan pada berkas data aktif (*Active Data File*) harus ditulis secara berurutan (*append-only*) dengan format struktur biner berekspresi ketat:
   `[CRC32: 4 bytes][Timestamp: 8 bytes][Key_Size: 4 bytes][Value_Size: 4 bytes][Key: Variable][Value: Variable]`
2. **In-Memory Index (KeyDir):**
   Bangun struktur data in-memory (misalnya hash table) yang memetakan setiap `Key` ke lokasi fisiknya pada disk:
   `Key -> {File_ID, Value_Size, Value_Offset, Timestamp}`
3. **Operasi API Inti:**
   - `Put(Key, Value) -> Status`: Menambahkan record ke Active Data File, memverifikasi penulisan, memperbarui KeyDir. Menyediakan flag opsional `sync: bool` (jika `true`, eksekusi `fsync()` wajib dijalankan).
   - `Get(Key) -> (Value, Status)`: Mengambil metadata dari KeyDir (zero disk seek overhead untuk pencarian lokasi), lalu membaca persis sejumlah `Value_Size` dari `Value_Offset` di file target menggunakan *positioned read* (`pread` / `read_at`).
   - `Delete(Key) -> Status`: Menulis record khusus (*Tombstone record* bernilai kosong atau flag khusus) ke berkas log append-only dan menghapus pointer dari KeyDir.
4. **Log Compaction & Merge Process:**
   Implementasikan fungsi `Compact()`: Membaca berkas log yang sudah *read-only*, merekonsiliasi data usang/terhapus, menuliskan representasi data paling mutakhir ke berkas log baru yang padat, menghapus log lama, dan memperbarui offset pada KeyDir secara atomik tanpa menghentikan operasi pembacaan konkuren.
5. **Crash Recovery Validation:**
   Sistem harus mampu membangun ulang (*rebuild*) KeyDir secara otomatis saat inisialisasi awal dengan membaca file log biner secara sekuensial dari awal hingga akhir. Jika ditemukan entri parsial/korup di ujung file akibat proses yang terbunuh (`SIGKILL`), sistem harus mendeteksi korupsi via CRC32, memotong (*truncate*) segmen korup tersebut, dan melanjutkan recovery dengan data valid yang tersisa.

### Batasan Sistem (Constraints)
- Menggunakan native system calls: `open()`, `pread()`, `pwrite()` / `write()`, `fsync()`, `ftruncate()`.
- Thread-safe: Mendukung *multiple concurrent readers* dan *single exclusive writer*.
- Nilai memori KeyDir harus efisien: dilarang menyimpan *Value* di dalam memori; hanya koordinat disk yang diizinkan.

### Expected Output
- Kode sumber lengkap dengan *automated test suite*.
- Skrip simulasi crash: Jalankan *writer loop*, bunuh proses secara paksa menggunakan `kill -9`, hidupkan kembali proses, dan verifikasi integritas data via assertion test bahwa semua commit yang sukses sebelum crash dapat terbaca utuh tanpa inkonsistensi.
- Benchmark metrik performa: Tampilkan throughput (ops/sec) dan latensi rata-rata untuk pola *sequential write* vs *random read*.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Alur lengkap I/O traversal dari User Space Buffer $\rightarrow$ VFS $\rightarrow$ Page Cache $\rightarrow$ File System $\rightarrow$ Generic Block Layer $\rightarrow$ I/O Scheduler $\rightarrow$ Device Driver $\rightarrow$ Hardware Controller (NVMe/SATA).
- [ ] Perbedaan representasi file system struktural: Inode, Dentry, Superblock, dan Data Block.
- [ ] Mengapa *random write* pada media penyimpanan blok berbasis flash (SSD) memicu Write Amplification melalui proses read-modify-erase cycle pada Erase Block.
- [ ] Jaminan semantik POSIX I/O dan limitasi nyata durabilitas data pada level controller write caching.
- [ ] Trade-off fundamental antara *Page-based Storage Engines* (B-Trees) dan *Log-Structured Storage Engines* (LSM, Bitcask) terkait Space, Read, dan Write Amplification.
- [ ] Perbedaan mekanisme kerja synchronous blocking I/O, asynchronous non-blocking I/O multiplexing (`epoll`), dan asynchronous kernel completion queuing (`io_uring`).

### Saya tidak perlu menghafal:
- [ ] Nomor syscall spesifik untuk tiap arsitektur CPU (misalnya kode syscall assembly x86_64 untuk `sys_read`).
- [ ] Struktur byte internal biner dari inode table spesifik arsitektur file system Ext4/XFS (misalnya layout register spesifik superblock bit flags).
- [ ] Perintah kontrol register elektrik tingkat rendah (command register offsets) pada spesifikasi standar controller NVMe/AHCI.
- [ ] Seluruh flag bitmask konfigurasi `mount` Linux secara detail di luar flag inti integritas data (`sync`, `async`, `barrier`, `noatime`).

### Saya harus bisa melakukan:
- [ ] Menggunakan utilitas diagnostik storage Linux (`iostat -x`, `iotop -o`, `vmstat`, `blktrace`) untuk mengisolasi storage saturation, disk service time, queue depth, dan bottleneck dirty page flush.
- [ ] Mengonfigurasi parameter kernel sysctl virtual memory (`vm.dirty_*`) untuk mencegah I/O stalls pada server dengan kapasitas RAM gigantik.
- [ ] Mengaudit status cache dan barrier storage controller via CLI (`smartctl`, `hdparm`, `nvme-cli`) guna menjamin integritas penulisan database.
- [ ] Mengimplementasikan *crash-safe file persistence logic* pada kode aplikasi melalui pola penulisan: write-temp $\rightarrow$ sync $\rightarrow$ close $\rightarrow$ atomic rename $\rightarrow$ parent directory sync.
- [ ] Menemukan dan membersihkan file descriptors yatim piatu (*orphaned open unlinked files*) yang menahan kapasitas storage menggunakan kombinasi `lsof` dan `procfs`.