# BAB 05: Quiz, Challenge, & Knowledge Check
**Memori Virtual, Alokasi Halaman, dan Analisis Subsistem RAM**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Siklus Hidup Translasi Alamat Virtual ke Fisik (Page Fault & MMU Walk)**
   Jelaskan secara mendalam alur mikro-arsitektur dan interaksi kernel saat CPU mengeksekusi instruksi pembacaan alamat virtual yang belum dipetakan ke memori fisik (minor vs major page fault). Apa peran spesifik dari *Translation Lookaside Buffer* (TLB), *Page Table Entries* (PTE), register kontrol (seperti `CR3` pada x86_64), dan bagaimana kernel menentukan apakah operasi tersebut valid atau harus mengirimkan sinyal `SIGSEGV`?

2. **Dekomposisi Metrik Memori: VSS, RSS, PSS, dan USS**
   Dalam konteks optimasi memori dan profiling container, jelaskan perbedaan mendasar antara *Virtual Set Size* (VSS), *Resident Set Size* (RSS), *Proportional Set Size* (PSS), dan *Unique Set Size* (USS). Mengapa mengandalkan metrik RSS semata dapat menghasilkan estimasi kebutuhan RAM yang salah (*overestimation* atau *underestimation*) pada proses yang melakukan banyak operasi `fork()` dengan *Copy-on-Write* (CoW) serta memuat *shared libraries*?

3. **Arsitektur Dual Alokator: Buddy System vs. SLUB Allocator**
   Kernel Linux membagi manajemen memori fisik ke dalam dua lapis utama: *Buddy Allocator* dan *Slab/SLUB Allocator*. Jelaskan batas tanggung jawab teknis antara keduanya. Mengapa alokasi objek kecil (misalnya `struct task_struct` atau `inode`) tidak dialokasikan langsung melalui *Buddy System*, dan bagaimana *SLUB allocator* mengeliminasi *internal fragmentation* serta mengurangi *cache thrashing*?

4. **Karakteristik Anonymous Memory vs. File-Backed Memory**
   Bedakan siklus hidup dan strategi eviksi antara *Anonymous Memory* (heap, stack) dan *File-backed Memory* (page cache, mapped executables). Bagaimana kernel menangani persistensi *dirty pages* ke disk melalui *writeback mechanism* (flusher threads), dan apa bedanya dengan eviksi halaman anonim saat subsistem memori berada di bawah tekanan (*memory pressure*)?

5. **Mekanisme Reclaim dan Filosofi `vm.swappiness`**
   Jelaskan secara matematis/algoritmik apa yang sebenarnya diatur oleh parameter `vm.swappiness` di kernel Linux. Koreksi miskonsepsi umum bahwa "swappiness 0 mematikan swap sepenuhnya", dan jelaskan bagaimana rasio pemindaian (*scan ratio*) antara *anon list* dan *file list* dievaluasi oleh `kswapd` berdasarkan nilai parameter ini serta status *reclaimable memory*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Anatomi OOM Killer: Scoring, Heuristik, dan Mitigasi**
   Analisis bagaimana kernel Linux menghitung `oom_badness()`. Apa saja variabel pembobotan yang digunakan oleh algoritma untuk menentukan target terminasi proses? Jelaskan fungsi `oom_score_adj`, mengapa proses dengan RSS besar tidak selalu menjadi korban pertama jika ada hierarki cgroup yang terisolasi, dan bagaimana mendesain proteksi terhadap proses kritis seperti *database master engine* atau *agent orchestrator*.

2. **Transparent Huge Pages (THP): Latency Spikes vs. Memory Compaction**
   Meskipun THP dirancang untuk mereduksi TLB *misses* pada alokasi memori besar, fitur ini kerap di-nonaktifkan pada sistem database transaksional (seperti Redis, MongoDB, PostgreSQL). Bedakan mode `always`, `madvise`, dan `never`. Jelaskan secara internal bagaimana proses background `khugepaged` serta *synchronous memory compaction* dapat memicu *latency spike* ekstrem (*stall*) saat aplikasi meminta alokasi memori baru.

3. **Topologi NUMA: Node Imbalance, Remote Allocation, dan `zone_reclaim_mode`**
   Pada server multi-socket dengan arsitektur *Non-Uniform Memory Access* (NUMA), bagaimana kernel menangani alokasi memori lokal vs *foreign/remote* node? Analisis dampak performa dari *inter-connect latency* (UPI/QPI) ketika terjadi ketidakseimbangan alokasi. Kapan `zone_reclaim_mode` harus bernilai `0` versus `1`, dan apa implikasi sistem jika kernel memaksakan *local node page reclaim* alih-alih mengambil memori kosong di remote node?

4. **Direct Reclaim vs. Background Reclaim (`kswapd`) dan Analisis Watermark**
   Kernel mendefinisikan tiga tingkatan watermark per memory zone: `WMARK_MIN`, `WMARK_LOW`, dan `WMARK_HIGH`. Jelaskan kondisi batas pemicu aktifnya background daemon `kswapd` dan transisi menuju *Direct Reclaim*. Mengapa status *Direct Reclaim* pada tracepoint kernel (`mm_page_alloc_slowpath`) menjadi sinyal utama degradasi performa I/O sistem, dan bagaimana parameter `vm.min_free_kbytes` dapat disetel untuk mencegah hal tersebut?

5. **Deep-Dive `mmap`: Semantik `MAP_SHARED` vs. `MAP_PRIVATE` dan CoW Footprint**
   Saat sebuah aplikasi memanggil `mmap()` pada sebuah file berkas 10 GB:
   - Bagaimana kernel mengalokasikan memori tersebut secara *lazy*?
   - Apa yang terjadi di tingkat PTE ketika flag `MAP_SHARED` digunakan dan beberapa thread melakukan modifikasi serentak?
   - Bagaimana kernel mengisolasi perubahan saat `MAP_PRIVATE` digunakan, kapan alokasi fisik riil terjadi, dan bagaimana dampaknya terhadap *dirty page tracking* di `/proc/meminfo`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Latency Spikes Periodik pada Database In-Memory Berskala Besar
Sebuah cluster Redis berukuran 128 GB pada server bare-metal multi-socket (2x AMD EPYC, 512 GB RAM) mengalami lonjakan latensi p99 dari 200 mikrodetik menjadi 4.5 detik setiap 15 menit. Dari pemantauan CPU dasar, utilitas hanya 35%, swap dinonaktifkan (`swapoff -a`), dan kapasitas RAM fisik yang bebas (*free*) tercatat masih lebih dari 200 GB. Namun, grafik *Pressure Stall Information* (PSI) pada resource `memory` menunjukkan metrik `some avg10=42.15`.
- **Tugas Diagnostik:**
  1. Perintah dan instrumen kernel apa saja yang harus Anda gunakan untuk membuktikan apakah insiden ini disebabkan oleh *NUMA node saturation*, alokasi *Transparent Huge Pages* (THP), atau *memory compaction stall*?
  2. Bagaimana korelasi antara alokasi memori lokal per NUMA node dengan ketersediaan RAM fisik total sistem? Tunjukkan cara membaca metrik dari `/sys/devices/system/node/node*/meminfo`.
  3. Berikan playbook resolusi komprehensif, mencakup konfigurasi kernel runtime (`sysctl`), THP runtime toggles, dan strategi eksekusi proses melalui `numactl`.

### Skenario B: Silent Memory Exhaustion Akibat Unreclaimable Slab Cache
Sebuah cluster node Kubernetes (worker node) mendadak mengalami *kernel panic* / OOM death pada *system-critical daemons* (seperti `containerd` dan `kubelet`), meskipun metrik agregat memory limit cgroup dari seluruh Pod yang berjalan baru mencapai 50% dari kapasitas node. Output `free -m` menunjukkan sisa memori hanya 500 MB dari 64 GB, namun akumulasi RSS dari seluruh proses pengguna di `ps aux` hanya berjumlah 18 GB.
- **Tugas Diagnostik:**
  1. Tentukan subsistem memori kernel mana yang paling berpotensi "menyembunyikan" konsumsi RAM ini (Page Cache, Kernel Stacks, vmalloc, atau Slab Allocator).
  2. Tuliskan investigasi step-by-step menggunakan `/proc/meminfo`, `slabtop`, dan `vmstat -m` untuk mengidentifikasi apakah kebocoran terjadi pada *dentry cache*, *inode_cache*, atau struktur jaringan (`buffer_head`, `skbuff`).
  3. Jika ditemukan bahwa `dentry` memakan 40 GB memori yang *unreclaimable*, jelaskan akar masalah aplikasi (misal: jutaan file temporer yang dibuka/dihapus secara agresif oleh aplikasi batch) dan bagaimana cara mengonfigurasi `vfs_cache_pressure` serta membersihkan cache secara terukur tanpa memicu *I/O freezing*.

### Skenario C: Data Integrity, Writeback Stalls, dan Tuning Buffer I/O pada Node Storage
Sebuah instance basis data PostgreSQL dengan intensitas tulis tinggi (*heavy write-load*) mengalami kondisi di mana seluruh query baca mengalami *stall* (I/O hang) selama beberapa detik setiap kali kernel melakukan flushing data ke drive NVMe. Metrik `/proc/meminfo` menunjukkan nilai `Dirty` melonjak hingga puluhan gigabyte sebelum anjlok secara drastis bersamaan dengan lonjakan tajam pada latensi disk write (`await`).
- **Tugas Diagnostik:**
  1. Analisis arsitektur *writeback subsystem* Linux yang menyebabkan fenomena *bursty flushing* tersebut. Mengapa konfigurasi default kernel (`vm.dirty_ratio` dan `vm.dirty_background_ratio`) berbahaya pada server dengan RAM ratusan gigabyte?
  2. Jelaskan perbedaan mendasar antara menyetel batas writeback menggunakan persentase (`dirty_ratio`) vs batas absolut berbasis byte (`dirty_bytes`, `dirty_background_bytes`).
  3. Rancang konfigurasi arsitektur subsistem I/O dan memori yang seimbang untuk server dengan 256 GB RAM agar kernel memicu *asynchronous background flush* secara konstan dan halus tanpa memblokir thread aplikasi (*preventing direct sync write stalls*).

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Engine Diagnostik Memory Pressure & Early-Warning Sentinel

#### Problem Statement
Metrik konvensional seperti persentase *RAM Used* dari `free` atau `node_exporter` bersifat reaktif dan sering kali gagal memberikan peringatan dini sebelum sebuah host mengalami kelumpuhan akibat *Direct Reclaim latency* atau eksekusi *OOM Killer*. Tim *Site Reliability Engineering* (SRE) membutuhkan sebuah *daemon* inspeksi cerdas berskala mikro yang mampu memantau saturasi memori pada level kernel, mendeteksi fragmentasi, melacak pemborosan memori via *slab*, dan membaca *kernel stall metrics* secara akurat sebelum degradasi layanan terjadi.

#### Requirements
Anda diminta membangun tool diagnostik tingkat lanjut bernama `mem-sentinel` (menggunakan Bash shell scripting tingkat lanjut atau Python standar tanpa modul pihak ketiga/no external dependencies, murni membaca interface `/proc`, `/sys`, dan subsistem kernel):

1. **PSI Engine Integration:**
   - Membaca dan memparsing data dari `/proc/pressure/memory`.
   - Mengeluarkan peringatan bertingkat (*Warning* / *Critical*) jika nilai `some avg10` melampaui `10.0` atau `full avg10` melampaui `5.0`.

2. **Proportional & True Cost Calculator:**
   - Mengambil 5 proses teratas yang mengonsumsi memori terbesar dan menghitung nilai PSS (*Proportional Set Size*) serta USS (*Unique Set Size*) riil dari masing-masing proses dengan membedah `/proc/[pid]/smaps_rollup` atau `/proc/[pid]/smaps`.
   - Menghitung rasio fragmentasi memori Buddy System dengan memparsing `/proc/buddyinfo` (hitung rasio ketersediaan blok order rendah [0-3] terhadap order tinggi [8-10] di zona `Normal`).

3. **Slab & Kernel Memory Auditor:**
   - Mengekstrak konsumsi memori kernel non-proses dari `/proc/meminfo`: memvalidasi apakah `SUnreclaim` + `VmallocUsed` + `PageTables` melebihi ambang batas aman (misal: > 20% dari total RAM fisik).

4. **Automated Incident Snapshot:**
   - Jika kondisi *pressure* terpenuhi (kondisi kritis), tool harus melakukan *snapshot* atomik ke direktori `/var/log/mem-sentinel/` yang berisi:
     - Dump `/proc/vmstat` (khusus metrik `pgscan_*`, `pgsteal_*`, `allocstall_*`, `compact_*`).
     - Alokasi node NUMA (`numastat -m` atau via `/sys/devices/system/node/`).
     - Pemetaan *OOM scores* dari seluruh proses yang ada di sistem (`/proc/[pid]/oom_score`).

#### Constraints
- Script/tool tidak boleh menimbulkan *overhead* CPU lebih dari 1.5% pada satu core.
- Pengambilan data smaps tidak boleh memicu kernel lockup pada proses dengan jutaan VMA (Virtual Memory Areas); manfaatkan `smaps_rollup` jika didukung oleh kernel target (Linux 4.14+).
- Harus kompatibel dengan sistem cgroups v1 maupun cgroups v2.

#### Expected Output
Script yang dapat dieksekusi dengan *flag* `--audit` (menampilkan laporan komprehensif saat ini dalam format teks terstruktur atau JSON) dan flag `--daemon` (berjalan secara periodik setiap N detik, mengevaluasi *threshold*, serta mencatat log insiden jika terdeteksi anomali saturasi).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur hirarki page table multi-level (x86_64 4-level/5-level paging: PGD, P4D, PUD, PMD, PTE) dan overhead memori untuk page tables.
- [ ] Alur transisi dari Virtual Memory Address ke Physical Frame via Hardware MMU & Software Page Fault Handler.
- [ ] Perbedaan matematis dan teknis antara Virtual (VSS), Resident (RSS), Shared/Proportional (PSS), dan Private Unique (USS) memory.
- [ ] Prinsip kerja *Buddy Allocator* dalam mengelola blok memori $2^n$ order dan mitigasi fragmentasi eksternal.
- [ ] Peran dan cara kerja *SLAB/SLUB/SLOB Allocator* untuk alokasi internal objek kernel berukuran kecil.
- [ ] Perbedaan fungsional antara `kswapd` (asynchronous reclaim) dan *Direct Reclaim* (synchronous latency-inducing reclaim).
- [ ] Arti dari ketiga batas watermark zona memori: `watermark[WMARK_MIN]`, `watermark[WMARK_LOW]`, dan `watermark[WMARK_HIGH]`.
- [ ] Pengaruh topologi NUMA, remote node allocation penalties, serta konfigurasi `numactl` dan CPU node binding.
- [ ] Metrik Pressure Stall Information (PSI) pada subsistem memori (`some` vs `full`) dan signifikansinya dibanding utilitas memori klasik.
- [ ] Algoritma evaluasi OOM Killer (`oom_badness`), perhitungan *badness score*, dan interface isolasi `/proc/[pid]/oom_score_adj`.
- [ ] Cara kerja *Dirty Page Writeback Engine*, flusher threads, dan parameter pengendali I/O sync (`dirty_ratio` vs `dirty_bytes`).

### Saya tidak perlu menghafal:
- [ ] Offset bitfield spesifik dari register arsitektur hardware non-standar (misalnya bitmask kontroler IOMMU tertentu di luar flag dasar PTE).
- [ ] Struktur data internal C lengkap (`struct page`, `struct mm_struct`) hingga ke urutan field-nya di source code kernel Linux.
- [ ] Nomor syscall spesifik untuk memori (`brk`, `mmap`, `madvise`, `process_madvise`) dalam format desimal/heksadesimal.
- [ ] Nilai eksak `oom_score` sebuah proses tanpa melihat kalkulasi runtime dari `/proc/[pid]/oom_score`.

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi akar masalah *high system memory pressure* menggunakan kombinasi `/proc/meminfo`, `/proc/vmstat`, dan tracing via `perf` / `bpftrace`.
- [ ] Memisahkan konsumsi memori aplikasi pengguna dengan alokasi kernel tersembunyi (seperti *unreclaimable slab*, socket buffers, atau page tables).
- [ ] Melakukan profiling dan parsing penggunaan PSS/USS per proses secara langsung dari file status subsistem `/proc/[pid]/smaps_rollup`.
- [ ] Menemukan dan menyelesaikan masalah *NUMA imbalance* dengan melacak *NUMA hits*, *misses*, dan *foreign allocation* melalui `numastat`.
- [ ] Mengonfigurasi parameter kernel runtime (`sysctl`) untuk memory writeback (`vm.dirty_*`), swap responsiveness (`vm.swappiness`), dan reclaim thresholds (`vm.vfs_cache_pressure`, `vm.min_free_kbytes`) sesuai karakteristik beban kerja (OLTP, OLAP, High-Throughput Streaming).
- [ ] Memetakan mitigasi THP (*Transparent Huge Pages*) untuk aplikasi bertipe latency-sensitive guna mencegah *direct compaction stalls*.
- [ ] Mengatur limitasi hierarkis memori menggunakan cgroups v2 (`memory.min`, `memory.low`, `memory.high`, `memory.max`) untuk mencegah OOM cascade pada multi-tenant environment.