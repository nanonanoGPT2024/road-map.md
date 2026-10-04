# BAB 06: Ketahanan Data (Mekanisme Persistence RDB & AOF)
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis (Analyze)** interaksi internal antara engine Redis dan Linux Kernel subsystem (Virtual Memory, Copy-on-Write, Page Cache, dan VFS) saat proses persistensi berlangsung.
- **Mendiagnosis (Evaluate)** akar penyebab bottleneck performa seperti *latency spike* akibat `fork()`, *fsync queue stalling*, dan *memory bloat* yang dipicu oleh Transparent Huge Pages (THP).
- **Merancang & Mengonfigurasi (Create)** arsitektur persistensi hibrida enterprise dan Multi-Part AOF (Redis 7.x+) dengan zero-unintended-data-loss dan SLA latensi sub-milidetik.
- **Mengotomatisasi (Apply)** mitigasi kegagalan disk I/O, replikasi data ke object storage secara asinkron, dan pemulihan bencana (*Disaster Recovery*) terukur dengan metrik RPO (*Recovery Point Objective*) dan RTO (*Recovery Time Objective*).

---

### 2. Prerequisites

Sebelum mempelajari modul ini, Anda harus memahami:
1. **Internal Redis Fundamental**: Pemahaman tentang Redis Single-Threaded Event Loop (aeEventLoop/epoll), struktur memori jemalloc, dan lifecycle command execution.
2. **Linux OS Internals**: Konsep POSIX system calls (`fork()`, `write()`, `fsync()`, `fdatasync()`), virtual memory management, page tables (PTE), dan state buffer kernel.
3. **Storage Subsystems**: Karakteristik performa NVMe SSD vs Block Storage Cloud (AWS EBS/GCP Persistent Disk), IOPS, write amplification, dan throughput latency.

---

### 3. Concept & Internal Architecture (Mendalam)

Persistensi data pada in-memory database merupakan kompromi antara kecepatan akses RAM dan keandalan non-volatile media. Redis memecahkan masalah ini bukan dengan mengubah arsitektur in-memory-nya, melainkan dengan mendelegasikan snapshotting dan append logging ke kernel Linux.

```
+-------------------------------------------------------------------------------+
|                                  REDIS PROCESS                                |
|                                                                               |
|  +------------------------+                     +--------------------------+  |
|  |   Main Event Loop      |                     |  AOF Buffer (Userspace)  |  |
|  |  (Process Client Cmd)  |-- (Every Mutation)->|  sdscatlen(server.aof_buf|  |
|  +------------------------+                     +--------------------------+  |
|              |                                                |               |
|      fork()  | (Copy Page Table)                              | flush / write()
|              v                                                v               |
|  +------------------------+                     +--------------------------+  |
|  |  Child Process (BGSAVE/|                     |   Linux Page Cache (OS)  |  |
|  |    BGREWRITEAOF)       |                     +--------------------------+  |
|  +------------------------+                                   |               |
|              |                                                | fsync()       |
|    Read via  | Write to temp file                             | (BIO Thread)  |
|       COW    v                                                v               |
|  +------------------------+                     +--------------------------+  |
|  | .rdb / .aof base file  |                     |  Non-Volatile Disk (SSD) |  |
|  +------------------------+                     +--------------------------+  |
+-------------------------------------------------------------------------------+
```

#### 3.1. Mekanisme Virtual Memory & Copy-on-Write (COW)
Ketika perintah `BGSAVE` atau `BGREWRITEAOF` dipicu, Redis mengeksekusi system call `fork()`. 
1. **Page Table Duplication**: Kernel tidak menyalin seluruh data Redis di RAM, melainkan menduplikasi *Page Table Reference* dari parent process ke child process.
2. **Page Protection Marking**: Semua page yang dipetakan ditandai sebagai *Read-Only*.
3. **Fault & Duplicate**: Jika Redis main thread menerima mutasi data (`SET`, `HSET`, dsb.) pada page tertentu:
   - CPU memicu Hardware Page Fault (`MMU Exception`).
   - Linux kernel menginterupsi eksekusi, mengalokasikan page fisik baru (umumnya berukuran 4 KB).
   - Kernel menyalin konten lama ke page baru, memperbarui entri Page Table milik parent process menjadi *Read-Write*, lalu mengeksekusi mutasi.
   - Child process tetap membaca page fisik asli yang tidak termutasi (*isolated point-in-time snapshot*).

#### 3.2. Bahaya Transparent Huge Pages (THP)
Secara default, Linux modern dapat mengaktifkan THP untuk mengelompokkan memory page menjadi blok 2 MB (mengurangi overhead TLB lookup). Namun, pada Redis:
- Jika 1 byte di dalam blok 2 MB tersebut dimutasi saat proses background save berjalan, kernel dipaksa menyalin **seluruh blok 2 MB** via Copy-on-Write, bukan 4 KB standar.
- Hal ini menyebabkan fenomena **COW Amplification** (512x write inflation), menghasilkan *memory exhaustion* (OOM Killer terpanggil) dan *extreme latency spikes* (puluhan milidetik) pada thread utama.

#### 3.3. Multi-Part AOF (Redis 7.0+)
Pada versi sebelum Redis 7, `BGREWRITEAOF` menghasilkan satu file log baru yang menyalin seluruh state database, sementara file lama terus menampung data baru. Setelah selesai, file ditukar secara atomik. Pendekatan ini menghasilkan overhead disk I/O ganda.

Redis 7.0 memperkenalkan arsitektur **Multi-Part AOF**:
- **Base File**: Snapshot point-in-time (berupa format RDB atau AOF native) saat rewrite terakhir.
- **Incremental Files**: File log kecil yang menampung mutasi data baru yang terus bertambah selama rewrite berlangsung dan setelahnya.
- **Manifest File**: State metadata (`appendonly.aof.manifest`) yang melacak file Base dan Incremental mana yang aktif beserta urutan sekuensialnya.

```
/var/lib/redis/appendonlydir/
├── appendonly.aof.manifest
├── appendonly.aof.1.base.rdb
├── appendonly.aof.1.incr.aof
└── appendonly.aof.2.incr.aof
```

#### 3.4. Background I/O (BIO) Threads & fsync Stalling
Redis memisahkan eksekusi `fsync()` dari event loop utama menggunakan dedicated pthread workers yang disebut **BIO (Background I/O) Threads**:
- `BIO_CLOSE_FILE`: Menutup file descriptor tanpa memblokir thread utama.
- `BIO_AOF_FSYNC`: Mengeksekusi system call `fsync()` atau `fdatasync()` ke disk.

**Edge Case Kegagalan**: Pada konfigurasi `appendfsync everysec`, BIO thread mengeksekusi `fsync()` setiap detik. Jika sub-sistem I/O disk sedang jenuh (*saturation*), pemanggilan `fsync()` oleh BIO thread akan memblokir (*disk wait*). Jika `fsync()` sebelumnya belum selesai dan sudah berjalan lebih dari 2 detik, **Main Event Loop Redis akan menolak mengeksekusi write command** untuk mencegah disk buffer desynchronization. Redis mengalami latency spike sekunder bukan karena CPU, melainkan karena *disk-induced main thread stalls*.

---

### 4. Why & What

| Dimensi | RDB (Redis Database) | AOF (Append Only File) | Hybrid (RDB + AOF) |
| :--- | :--- | :--- | :--- |
| **Definisi** | Serialisasi snapshot point-in-time biner terkompresi dari seluruh database. | Log linier yang merekam setiap operasi tulis (*write-command*) dalam format RESP. | Preamble RDB di dalam file log AOF, diikuti oleh delta perintah AOF baru. |
| **RPO (Data Loss)** | Tinggi (Kehilangan data sejak snapshot terakhir, misal: 5-15 menit). | Sangat Rendah (0 hingga maksimal 1-2 detik tergantung kebijakan `appendfsync`). | Sangat Rendah (Sama dengan AOF `everysec` / `always`). |
| **RTO (Recovery)** | Sangat Cepat (Parsing direct payload binary murni ke struktur memori). | Lambat (Harus memutar ulang seluruh query command via parser engine). | Cepat (Memuat data dasar via snapshot, lalu me-replay sisa log kecil). |
| **Dampak CPU/RAM** | Lonjakan memory overhead saat `fork()` dan saturasi CPU via LZF/ZSTD compression. | Penggunaan I/O bandwidth konstan; rewrite butuh overhead CPU moderat. | Optimal: Mengurangi beban rewrite I/O berlebih via snapshot chunking. |
| **Ukuran File** | Sangat Ringkas (Binary compaction, deduplikasi key internal). | Besar (Setiap operasi dicatat teks, rawan *bloat* tanpa rewrite). | Kompak (Hanya delta pasca-snapshot yang berupa teks instruksi). |

---

### 5. How (Workflow Detail)

#### 5.1. Alur Eksekusi Hybrid Multi-Part AOF + fsync everysec
```
Client Send: SET user:101 "active"
   │
   ▼
[1] Main Thread: Parsing RESP Command & Mutasi In-Memory Keyspace
   │
   ├─► Update Memory Hash Table (dict)
   │
   ▼
[2] Main Thread: Append ke server.aof_buf (Sds buffer di RAM)
   │
   ▼
[3] Main Thread: Flusing buffer via write() ke Linux Kernel Page Cache
   │ (Non-blocking, data masih berada di RAM kernel)
   │
   ▼
[4] Background Thread (BIO): Polling Job Queue setiap detik
   │
   ├─► Menjalankan fdatasync(fd)
   │
   ▼
[5] Storage Controller: Mengosongkan volatile disk cache ke non-volatile media (NAND Flash)
```

#### 5.2. Alur State Machine: Multi-Part AOF Rewrite
1. Main thread memeriksa kondisi auto-rewrite (`aof_current_size` vs `aof_base_size`).
2. Main thread membuka file inkremental baru (`appendonly.aof.(N+1).incr.aof`).
3. Seluruh mutasi baru **seketika dialihkan** ke file inkremental baru tersebut.
4. Main thread memanggil `fork()` untuk melahirkan background child process.
5. Child process menulis snapshot seluruh keyspace saat `fork()` ke file base sementara (`appendonly.aof.temp`).
6. Child process selesai dan keluar (*exit 0*).
7. Main thread mendeteksi selesainya child process via signal handler (`wait3()` / `waitpid()`).
8. Main thread memperbarui file `appendonly.aof.manifest` secara atomik, mendaftarkan Base File baru dan menghapus referensi Base File lama.
9. BIO thread menghapus file base dan file incremental yang sudah usang di latar belakang.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Akuntansi Keuangan (Buku Besar vs Catatan Bon)
- **RDB**: Foto buku kas neraca keuangan yang diambil oleh akuntan setiap hari Jumat sore. Anda melihat posisi kas akhir secara cepat, tetapi Anda buta terhadap mutasi transaksi yang terjadi pada hari Rabu jika buku kas hari Jumat terbakar.
- **AOF**: Rekaman pita struk kasir (*receipt log*) yang mencatat setiap kali kas keluar/masuk seketika. Buku kas dapat direkonstruksi dari nol dengan menghitung ulang dari struk pertama, tetapi proses auditnya memakan waktu berminggu-minggu jika struk menumpuk jutaan lembar.
- **Hybrid Multi-Part AOF**: Buku neraca resmi mingguan (Base RDB) yang langsung disambung dengan tumpukan bon transaksi sejak Jumat sore hingga hari ini (Incremental AOF). Audit cepat, data mutakhir tetap aman.

```
       SNAPSHOT vs JOURNALING DYNAMICS

   Time: T0       T1       T2       T3       T4 (Crash!)
   ------+--------+--------+--------+--------+-------->
   RDB:  [Dump]                            (Data T1-T4 Hilang)
   AOF:  [cmd1]--[cmd2]---[cmd3]---[cmd4]---[Data Selamat s/d T4-1s]
   
   COW MEMORY SPLIT (VIRTUAL MEMORY PAGES)
   Parent Memory: [Page 1 (Dirty)] [Page 2 (Clean)] [Page 3 (Dirty)]
                        |                 |                 |
                   (Page Fault)           |            (Page Fault)
                        v                 |                 v
   New Physical:  [Page 1' (Parent)]      |           [Page 3' (Parent)]
   Original Phys: [Page 1  (Child) ] [Page 2 (Shared)] [Page 3 (Child) ]
```

---

### 7. Simple Example & Practical Example

#### 7.1. Konfigurasi Produksi: Hybrid Persistence (redis.conf)
```conf
# Direktori penyimpanan data
dir /var/lib/redis
appenddirname "appendonlydir"

# RDB Configuration (Safe Defaults)
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb

# AOF Configuration (Redis 7.x Native Multi-Part)
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
no-appendfsync-on-rewrite yes
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 1gb

# Hybrid Persistence Enablement
aof-use-rdb-preamble yes
```

#### 7.2. Production Automation Script: Dynamic Persistence Sentinel (Python)
Script ini mengevaluasi health status persistensi, memantau *fork execution time*, mendeteksi anomali latensi, dan memicu BGSAVE terjadwal di luar jam sibuk untuk menghindari *uncontrolled rewrites*.

```python
#!/usr/bin/env python3
"""
Redis Production Persistence Sentinel & Auto-Tuner
Requirement: redis >= 4.5.0
"""
import sys
import time
import logging
import redis

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

class RedisPersistenceMonitor:
    def __init__(self, host: str = '127.0.0.1', port: int = 6379, auth: str = None):
        self.client = redis.Redis(
            host=host, 
            port=port, 
            password=auth, 
            decode_responses=True,
            socket_timeout=5
        )

    def verify_node_health(self):
        try:
            info_persistence = self.client.info('persistence')
            info_memory = self.client.info('memory')
            
            # 1. Periksa Status Terakhir BGSAVE
            if info_persistence.get('rdb_last_bgsave_status') != 'ok':
                logging.critical("CRITICAL: rdb_last_bgsave_status IS FAILING!")
                
            # 2. Periksa Status Terakhir Write AOF
            if info_persistence.get('aof_last_write_status') != 'ok':
                logging.critical("CRITICAL: aof_last_write_status IS FAILING!")

            # 3. Analisis Fork Execution Latency (dalam microsecond)
            last_fork_usec = info_persistence.get('latest_fork_usec', 0)
            logging.info(f"Metrik Fork Terakhir: {last_fork_usec} µs")
            if last_fork_usec > 100000:  # > 100ms
                logging.warning(f"PERINGATAN: Fork time melewati ambang batas SLA (>100ms): {last_fork_usec} µs")

            # 4. Monitor COW Memory Footprint
            cow_size = info_persistence.get('aof_last_cow_size', 0) or info_persistence.get('rdb_last_cow_size', 0)
            used_memory = info_memory.get('used_memory', 1)
            cow_ratio = (cow_size / used_memory) * 100
            logging.info(f"COW Overhead Terakhir: {cow_size} bytes ({cow_ratio:.2f}% dari total memory)")

            if cow_ratio > 30.0:
                logging.warning("High COW detected! Pastikan Linux Transparent Huge Pages dinonaktifkan.")

        except redis.RedisError as exc:
            logging.error(f"Gagal mengeksekusi health-check: {exc}")

    def safe_manual_rewrite(self):
        """Memicu BGREWRITEAOF jika tidak ada child process lain yang aktif."""
        info = self.client.info('persistence')
        if info.get('aof_rewrite_in_progress') == 1 or info.get('rdb_bgsave_in_progress') == 1:
            logging.info("Operasi persistence lain sedang berjalan. Eksekusi dibatalkan.")
            return False

        logging.info("Memulai manual BGREWRITEAOF terpantau...")
        start_time = time.time()
        self.client.bgrewriteaof()

        while True:
            time.sleep(2)
            current_info = self.client.info('persistence')
            if current_info.get('aof_rewrite_in_progress') == 0:
                break

        duration = time.time() - start_time
        logging.info(f"BGREWRITEAOF sukses diselesaikan dalam {duration:.2f} detik.")
        return True

if __name__ == '__main__':
    monitor = RedisPersistenceMonitor()
    monitor.verify_node_health()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: FinTech Core Banking Payment Switch
- **Beban Kerja**: 85.000 mutasi transaksi akun saldo ledger per detik pada peak time.
- **Infrastruktur**: Dedicated Bare-Metal, 64 Core AMD EPYC, 256 GB RAM, 2x NVMe U.2 Enterprise SSD RAID 1.
- **Target SLA**: Latensi pemrosesan p99 < 3ms, Strict Maximum Data Loss Tolerance (RPO) < 1 detik.

#### Gejala Masalah (Incident Report P0)
Pada pukul 14:00 saat *flash sale*, p99 latensi API melonjak drastis dari 1.8ms ke 2.400ms (2.4 detik). Ratusan thread koneksi upstream payment gateway mengalami *timeout*.
Metrics memaparkan:
- `rdb_bgsave_in_progress`: 1
- `latest_fork_usec`: 1.200.000 µs (1.2 detik blocking main thread).
- `allocator_frag_ratio`: Melonjak menjadi 2.1.
- Memori membengkak hingga menyentuh batas OS OOM Killer (230 GB / 256 GB terpakai).

#### Root Cause Analysis (RCA)
1. **THP Enabled**: Kernel Linux host mengaktifkan `transparent_hugepage=always`. Saat `BGSAVE` berjalan, mutasi 85.000 req/sec menyebabkan fragmentasi masif dan alokasi COW melipatgandakan duplikasi page 4 KB menjadi 2 MB secara terus menerus.
2. **Page Table Allocation Delay**: Alokasi tabel memori untuk pemetaan 180 GB keyspace Redis saat `fork()` membutuhkan waktu alokasi kernel murni sebesar 1.2 detik.
3. **Fsync Disk Saturation**: Konfigurasi `appendfsync everysec` bertabrakan dengan snapshotting `BGSAVE` yang membanjiri I/O controller, memicu kondisi *Fsync Stalling* (BIO memblokir Main Thread).

#### Solusi Arsitektural & Mitigasi Permanen
1. **Host-Level Kernel Tuning**:
   ```bash
   # Nonaktifkan Transparent Huge Pages secara runtime & persistent
   echo never > /sys/kernel/mm/transparent_hugepage/enabled
   echo never > /sys/kernel/mm/transparent_hugepage/defrag
   
   # Berikan otorisasi alokasi overcommit virtual memory
   sysctl vm.overcommit_memory=1
   ```
2. **Redis Isolation Architecture**:
   - Menghapus snapshotting `BGSAVE` sepenuhnya dari node Master (`save ""` di nonaktifkan total).
   - Master hanya mengaktifkan `appendonly yes` dengan `appendfsync everysec` dan `no-appendfsync-on-rewrite yes` (menghindari write collision antara rewriting dan main thread flushes).
   - Membangun **Dedicated Backup Replica Node**: Snapshotting RDB biner murni dialihkan ke replica read-only offsite.
   - Peningkatan Redis ke versi 7.2 untuk memanfaatkan Multi-Part AOF, membagi beban rewrite file menjadi delta chunk kecil.

---

### 9. Trade-offs

```
                  DURABILITY (Zero Data Loss)
                            /\
                           /  \
                          /    \
                         /      \
    appendfsync always  /        \  Multi-Part AOF + fsync everysec
                       /          \
                      /   TRADE-   \
                     /     OFF      \
                    /                \
                   /                  \
  LOW LATENCY / ----------------------- \ HIGH THROUGHPUT /
  LOW DISK WEAR    save "" (Pure RAM)     COST EFFICIENCY (RDB Snapshotting)
```

| Parameter | appendfsync always | appendfsync everysec | appendfsync no | Pure In-Memory (No Persistence) |
| :--- | :--- | :--- | :--- | :--- |
| **Write Latency (p99)** | **> 10-30 ms** (Disk Bound) | **< 1 ms** (Memory Bound) | **< 0.5 ms** (Pure OS Page Cache) | **< 0.2 ms** (Zero I/O overhead) |
| **RPO (Worst-Case Loss)** | **0 Byte** | **1-2 Detik** | **Tergantung OS buffer** (hingga puluhan detik) | **Total Data Loss** jika node mati |
| **Throughput (IOPS/sec)**| Sangat Rendah (Limit SSD) | Sangat Tinggi (Chunked) | Maksimum Engine Capacity | Maksimum Engine Capacity |
| **Storage Media Wear** | Ekstrem (Terus memicu sync) | Terkontrol | Sangat Rendah | Nol |
| **Biaya Hardware Disk** | Enterprise NVMe Read/Write| Mid-range NVMe / Fast EBS| General Purpose SSD | Basic Ephemeral Storage |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Fatal Konfigurasi

1. **Membiarkan `vm.overcommit_memory = 0`**:
   - *Bahaya*: Jika Redis menggunakan 60% dari kapasitas RAM, pemanggilan `fork()` ditolak oleh Linux Kernel dengan pesan error `Cannot allocate memory`, karena kernel berasumsi alokasi butuh RAM dua kali lipat secara statis.
   - *Solusi*: Setel `sysctl vm.overcommit_memory = 1`.
2. **Penggunaan `no-appendfsync-on-rewrite no` pada Disk Berkecepatan Rendah**:
   - *Bahaya*: Selama proses rewrite AOF memakan I/O disk, thread BIO yang mengeksekusi fsync harian akan terblokir total, menyebabkan event loop utama Redis terkunci.
   - *Solusi*: Ubah menjadi `no-appendfsync-on-rewrite yes` untuk menghentikan fsync berkala sementara rewrite berlangsung (Trade-off: RPO bertambah selebar durasi rewrite jika crash tepat saat itu).

#### 10.2. Troubleshooting Flowchart: Main Thread Latency Spikes
```
[Deteksi: Latency Spike pada Redis CLI (--latency-history)]
                           │
                           ▼
          Apakah spike bertepatan dengan BGSAVE/AOF?
                     ┌─────┴─────┐
                 YES │           │ NO
                     ▼           ▼
        Periksa metrik OS:     Periksa Network, Slowlog,
        "latest_fork_usec"     atau Komplesitas O(N) Command
                     │
         > 100,000 µs?
         ┌───┴───┐
     YES │       │ NO
         ▼       ▼
   Memory Page Table Size     Periksa BIO Thread Fsync Stalling:
   Besar (Kurangi Memori Node/   Metrik: "aof_delayed_fsync" > 0?
   Pecah ke Cluster Sharding)          ┌───┴───┐
                                   YES │       │ NO
                                       ▼       ▼
                             I/O Disk Jenuh.  Periksa Transparent Huge
                             Upgrade IOPS/    Pages (THP) Memory
                             Gunakan NVMe.    Allocation Overhead.
```

---

### 11. Best Practices (Production Checklist)

#### OS-Level Preparation:
- [ ] Nonaktifkan THP secara permanen via Kernel Boot Option: `transparent_hugepage=never`.
- [ ] Ubah konfigurasi memori overcommit: `vm.overcommit_memory = 1` pada `/etc/sysctl.conf`.
- [ ] Atur swap space: Jangan pernah mematikan swap sepenuhnya (Swap = 0 beresiko langsung memicu OOM Killer instan); gunakan swap file kecil dengan `vm.swappiness = 1` atau `10`.
- [ ] Mount disk data Redis dengan parameter `noatime` pada `/etc/fstab` untuk mengeliminasi pembaruan metadata waktu baca file.

#### Redis Configuration Tuning:
- [ ] Pisahkan partisi fisik data Redis dengan system root partition (`/var/lib/redis` berada pada dedicated high-IOPS NVMe).
- [ ] Aktifkan `aof-use-rdb-preamble yes` untuk waktu recovery (RTO) optimal.
- [ ] Tetapkan batas `auto-aof-rewrite-percentage 100` dan `auto-aof-rewrite-min-size 1gb` ke atas (mencegah loop rewrite terus menerus pada dataset berukuran kecil).
- [ ] Pada arsitektur Master-Replica, **nonaktifkan persistensi di Master node**, aktifkan Hybrid AOF di Replica node, dan pastikan Master tidak melakukan auto-restart tanpa data orchestration untuk menghindari *empty-flush replication loop*.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum ini pada direktori: `hands-on/m02/`

#### Langkah 1: Persiapan Environment dan Pengujian Kernel Overcommit
Buat file `hands-on/m02/docker-compose.yml`:
```yaml
version: '3.8'
services:
  redis-enterprise:
    image: redis:7.2-alpine
    container_name: redis-persistence-lab
    command: ["redis-server", "/usr/local/etc/redis/redis.conf"]
    ports:
      - "6379:6379"
    volumes:
      - ./redis.conf:/usr/local/etc/redis/redis.conf
      - ./data:/data
    sysctls:
      - net.core.somaxconn=1024
```

Buat konfigurasi file `hands-on/m02/redis.conf`:
```conf
dir /data
port 6379
protected-mode no

# Setup Persistence Hybrid
appendonly yes
appendfsync everysec
aof-use-rdb-preamble yes
appenddirname "appendonlydir"

# Logging & Monitoring
loglevel notice
logfile ""
```

Jalankan container:
```bash
docker compose up -d
```

#### Langkah 2: Simulasi Beban Data Tinggi dan Pemicuan Forking
Jalankan benchmark untuk mengisi dataset hingga beberapa ratus ribu keys:
```bash
docker exec -it redis-persistence-lab redis-benchmark -t set,get -n 500000 -r 1000000 -q
```

#### Langkah 3: Eksekusi Manual Rewrite dan Inspeksi Multi-Part AOF
Eksekusi inspeksi file sistem direktori data:
```bash
docker exec -it redis-persistence-lab redis-cli BGREWRITEAOF
docker exec -it redis-persistence-lab ls -la /data/appendonlydir/
```

Output yang diharapkan:
```text
appendonly.aof.1.base.rdb
appendonly.aof.1.incr.aof
appendonly.aof.manifest
```

Periksa isi file manifest:
```bash
docker exec -it redis-persistence-lab cat /data/appendonlydir/appendonly.aof.manifest
```
Anda akan melihat format deklaratif:
```text
file appendonly.aof.1.base.rdb seq 1 type b
file appendonly.aof.1.incr.aof seq 1 type i
```

---

### 13. Exercise

#### Level: Easy
1. Ubah konfigurasi persistensi node Redis dari mode default menjadi mode hybrid (RDB preamble + AOF) secara dinamis via terminal `redis-cli` tanpa me-restart service Redis! Tuliskan perintah-perintah tersebut.

#### Level: Medium
2. Sebuah instans Redis dengan kapasitas data 30 GB di RAM diset dengan `save 60 10000`. Jika server mati mendadak pada detik ke-59 setelah 9.999 data dimutasi, berapa banyak data yang hilang? Analisis parameter apa saja yang harus diubah jika Anda ingin RPO maksimal tidak lebih dari 2 detik dengan impact performa I/O serendah mungkin.

#### Level: Hard
3. Tulis script shell/Bash yang melakukan auto-backup data:
   - Memastikan snapshot terisolasi tanpa memicu interupsi I/O.
   - Mengambil artefak Base dan Incremental AOF beserta Manifest secara atomik.
   - Menghitung checksum SHA256 dari seluruh file tersebut.
   - Mengompresi seluruh artefak ke direktori isolasi `/backup/redis/` menggunakan `zstd` multi-threaded.

---

### 14. Challenge

**Skenario Sistem Terdistribusi Skala Ultra-Tinggi**:
Anda adalah Principal Infrastructure Architect pada platform ride-hailing berskala global. Sistem Anda memproses pelacakan GPS *driver* yang melakukan update lokasi real-time dengan volume 400.000 mutasi/detik pada klaster Redis Master tunggal dengan RAM 128 GB (sebelum dipecah menjadi Cluster). 

**Kondisi Batasan & Masalah**:
1. Menjalankan `BGREWRITEAOF` atau `BGSAVE` mengakibatkan memory usage melompat hingga 210 GB akibat fluktuasi COW masif, memicu Linux OOM-Killer mematikan proses Redis.
2. Menggunakan `appendfsync always` menjatuhkan throughput hingga 98% karena batasan IOPS disk.
3. Master node tidak boleh kehilangan data transaksi order lebih dari 1 detik (RPO <= 1s), namun data history jejak koordinat GPS (ping data) diperbolehkan memiliki RPO hingga 1 jam.

**Tugas Arsitektur Anda**:
Rancang blueprint konfigurasi data-flow, perombakan partisi keyspace (database segmentation/topology), dan arsitektur disk persistensi yang memecahkan masalah degradasi memori dan IOPS di atas tanpa mematikan real-time write pipeline! Sajikan breakdown rancangan Anda secara sistematis, mencakup topologi replikasi, isolasi hardware disk, konfigurasi kernel Linux, dan strategi segmentasi persistensi Redis.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. System call Linux apa yang digunakan oleh engine Redis untuk menginisialisasi proses background saving (BGSAVE)?
   - a) `clone()` dengan thread flag
   - b) `fork()`
   - c) `vfork()`
   - d) `execve()`

2. Format file apa yang digunakan secara default pada Base file Multi-Part AOF di Redis 7 jika opsi `aof-use-rdb-preamble` aktif?
   - a) Plain Text RESP commands
   - b) CSV format
   - c) RDB Binary Format
   - d) JSON Encoded State

3. Berapa kerugian data (RPO) terburuk jika Anda menggunakan konfigurasi `appendfsync everysec`?
   - a) Tepat 0 byte
   - b) Maksimal 1 detik saja dalam segala kondisi
   - c) Hingga 2 detik (jika background fsync thread sedang mengalami disk blocking)
   - d) Sama dengan nilai `save` RDB

4. Apa dampak utama membiarkan Transparent Huge Pages (THP) aktif di server Redis?
   - a) Mengurangi utilisasi CPU Redis
   - b) Mempercepat proses replikasi Master-Replica
   - c) Meningkatkan alokasi memori Copy-on-Write (COW) secara masif hingga 2MB per write mutation
   - d) Mencegah error `Out of Memory` pada Linux

5. Di mana letak penyimpanan log Multi-Part AOF pada Redis versi 7 ke atas?
   - a) Di satu file tunggal `/var/lib/redis/dump.aof`
   - b) Di dalam direktori terpisah yang dikonfigurasi via direktif `appenddirname`
   - c) Langsung disimpan ke dalam shared RAM `/dev/shm`
   - d) Di dalam struktur metadata Linux swap

#### Bagian 2: Intermediate (Pilihan Ganda / Analisis Singkat)
6. Mengapa Redis thread utama (*event loop*) bisa terblokir (stalled) meskipun `appendfsync` diatur ke `everysec`?
   - a) Karena Redis kehabisan thread worker BIO.
   - b) Karena `write()` POSIX call selalu sinkron ke piringan disk fisik.
   - c) Karena jika BIO fsync thread sebelumnya tertahan > 2 detik akibat I/O disk penuh, thread utama menolak eksekusi `write()` baru untuk keamanan integritas data.
   - d) Karena Linux kernel mematikan CPU affinity secara paksa.

7. Mengapa RTO (Recovery Time Objective) dari AOF native murni lebih lambat dibandingkan pemulihan via RDB snapshot?
   - a) AOF terenkripsi secara default sedangkan RDB tidak.
   - b) Redis harus mem-parsing string RESP dan mengeksekusi ulang jutaan state mutasi satu per satu via in-memory execution engine.
   - c) Ukuran blok disk AOF dibatasi sebesar 4 KB.
   - d) Parser RDB berjalan secara multi-thread sedangkan AOF single-thread.

8. Apa fungsi dari system call `fdatasync()` dibandingkan `fsync()` pada pipeline pembaruan persistensi Redis?
   - a) `fdatasync()` hanya mem-flush data payload file tanpa memaksakan sinkronisasi pembaruan metadata (seperti timestamp atribut file) jika tidak diperlukan, mengurangi latency seek disk.
   - b) `fdatasync()` tidak memblokir process caller sama sekali.
   - c) `fdatasync()` mengompresi payload secara langsung di level hardware cache.
   - d) `fdatasync()` memaksa disk controller mengabaikan checksum verification.

9. Apa fungsi dari file `appendonly.aof.manifest` di Redis 7.x?
   - a) Menyimpan data key-value yang dihapus.
   - b) Mengidentifikasi urutan sekuensial serta status aktif/inaktif dari file Base dan file-file Incremental AOF.
   - c) Bertindak sebagai buffer data yang belum masuk ke Page Cache.
   - d) Mengatur alokasi memori jemalloc untuk child process.

10. Jika parameter `vm.overcommit_memory` diatur ke nilai `0`, apa yang akan terjadi saat Redis dengan penggunaan RAM 70% memanggil fungsi `BGSAVE` pada server Linux dengan kapasitas RAM terpasang 100%?
    - a) Snapshot berhasil tanpa masalah dengan COW.
    - b) Pemanggilan `fork()` gagal dan memicu error `Cannot allocate memory` karena kernel menolak alokasi heuristik virtual memory.
    - c) Redis otomatis menghapus dataset menggunakan eviction policy.
    - d) Kernel otomatis membunuh aplikasi lain via OOM killer seketika.

#### Bagian 3: Kasus Produksi Nyata
11. **Skenario Disk Write Bottleneck**: Pada sebuah database server Redis, metrik `aof_delayed_fsync` pada command `INFO persistence` terus meningkat secara drastis setiap beberapa menit. Disk I/O utilization menyentuh 100% (terpantau via `iostat -xz 1`). Langkah mitigasi sementara apa yang dapat diambil dari sisi konfigurasi Redis tanpa me-restart database, dan apa konsekuensi/trade-off dari langkah tersebut?
12. **Skenario Disaster Recovery Failure**: Administrator sistem mencoba merestart Redis setelah server mati mendadak. Redis gagal menyala (*crash on startup*) dengan error `Bad file format reading the append only file: make a backup of your AOF file, then use ./redis-check-aof --fix <filename>`. Apa yang sebenarnya terjadi pada tingkat disk saat server mati mendadak, dan apa dampak data yang terjadi jika perintah perbaikan `--fix` dijalankan?
13. **Skenario Master-Replica Asymmetric Persistence Crash**: Sebuah cluster menggunakan skema: Master (RAM murni, `save ""` dan `appendonly no`) dan Replica (Persistensi AOF `everysec`). Server Master mati listrik, lalu sistem operasi me-reboot mesin Master. Service Redis di Master diatur *auto-start via systemd*. Saat Master menyala kembali, seluruh data di Replica ikut hilang total. Mengapa bencana ini bisa terjadi?

---

### Jawaban dan Pembahasan Kuis

#### Kunci Jawaban Bagian 1
1. **b) `fork()`** - Redis menduplikasi proses menggunakan Linux `fork()` POSIX system call untuk memanfaatkan Virtual Memory Page Table copying.
2. **c) RDB Binary Format** - Dengan `aof-use-rdb-preamble yes`, Base file ditulis dalam binary snapshot RDB untuk kecepatan parsing loading, sedangkan data delta ditulis dalam RESP AOF.
3. **c) Hingga 2 detik** - Meskipun dijadwalkan setiap 1 detik, jika disk I/O sedang sibuk, Redis membiarkan BIO thread berjalan toleran hingga detik ke-2 sebelum menahan/memblokir eksekusi write.
4. **c) Meningkatkan alokasi memori Copy-on-Write (COW)** - THP memaksa alokasi minimum 2 MB per dirty page fault, menyebabkan ledakan pemakaian RAM saat snapshotting berjalan.
5. **b) Di dalam direktori terpisah** - Redis 7 Multi-Part AOF menyimpan base, incremental, dan manifest files di dalam direktori `appenddirname` (default: "appendonlydir").

#### Kunci Jawaban Bagian 2
6. **c)** - Redis memproteksi disk queue buffer agar tidak meluap tak terkendali. Jika fsync tertahan > 2 detik, thread utama menolak eksekusi `write()` ke page cache demi mencegah hilangnya data di buffer OS yang membengkak tak tentu arah.
7. **b)** - Loading RDB membaca representasi langsung serialisasi struktur data ke memori secara linear, sedangkan AOF native memutar ulang seluruh siklus eksekusi parser perintah Redis.
8. **a)** - `fdatasync()` memangkas operasi write disk I/O yang tidak penting (seperti disk inode access time metadata), hanya memastikan block raw data yang masuk ke media fisik.
9. **b)** - Manifest file adalah file kontrol deklaratif yang memberi tahu Redis urutan tracking file Base dan delta Incremental yang valid pasca rewrite.
10. **b)** - Kernel Linux dengan mode heuristik (`overcommit_memory=0`) akan menghitung kebutuhan memory seolah-olah proses child akan mengonsumsi RAM persis sebesar parent process (70% + 70% = 140%), sehingga menolak pemanggilan `fork()` meskipun memori riil via COW mencukupi.

#### Pembahasan Kasus Produksi
11. **Analisis**: Mitigasi instan adalah menyalakan parameter `no-appendfsync-on-rewrite yes` via command `CONFIG SET no-appendfsync-on-rewrite yes` dan mengubah sementara `CONFIG SET appendfsync no` jika disk benar-benar failure total. 
    *Konsekuensi*: Durabilitas data turun drastis. Jika server mati saat setting `appendfsync no` aktif, RPO data loss bergantung penuh pada interval flush dirty page cache kernel Linux (secara default hingga 30 detik).
12. **Analisis**: Server mati mendadak saat operasi penulisan disk sedang berlangsung di tengah-tengah paket RESP buffer. Hal ini mengakibatkan byte tail file menjadi terpotong (*corrupted/half-written command*). 
    *Dampak Tool Fix*: Utility `redis-check-aof --fix` akan memindai pointer file hingga byte error terakhir, lalu **memotong/menghapus (truncate) seluruh byte yang invalid** dari titik tersebut ke bawah. Seluruh transaksi data yang berada pada akhir file log yang terpotong tersebut dipastikan musnah demi validitas sintaks format startup engine.
13. **Analisis**: Karena Master tidak memiliki persistensi data sama sekali, saat service Redis Master menyala secara otomatis, database Master dalam status **kosong murni (0 keys)**. Replica yang terhubung kembali ke Master akan menganggap kondisi database Master saat ini adalah *truth state*. Master akan mengirimkan snapshot kosong (Full Synchronization), dan Replica secara patuh akan **menghapus seluruh dataset lokalnya** (`FLUSHALL` implisit) untuk mencocokkan kondisi dengan Master. 
    *Pencegahan*: Matikan auto-restart Redis service pada Master jika persistensi dimatikan, atau gunakan orkestrator seperti Redis Sentinel/Cluster Failover agar Replica dipromosikan menjadi Master sebelum instance yang mati kembali online.

---

### 16. Summary

1. **Mekanisme Persistensi Redis Beroperasi pada Level Kernel**: Persistensi Redis bukanlah sekadar penulisan file reguler, melainkan orkestrasi erat antara POSIX system call (`fork()`, `write()`, `fdatasync()`), virtual memory Copy-on-Write (COW), dan Page Cache.
2. **Karakteristik Format Data**:
   - **RDB**: Format biner terkompresi, zero-load penalty, RTO sangat cepat, RPO tinggi.
   - **Native AOF**: Append-only command log format RESP, RPO rendah (1-2s), pemulihan data lambat (RTO panjang).
   - **Hybrid Multi-Part AOF (Redis 7+)**: Arsitektur standar industri terbaik saat ini yang menggabungkan base snapshot RDB dan incremental command logs AOF yang dimanipulasi via file manifest deklaratif tanpa bottleneck double-write.
3. **Optimasi Sistem Operasi adalah Prasyarat Mutlak**: Membiarkan Transparent Huge Pages (THP) menyala atau mengunci alokasi virtual memory via `vm.overcommit_memory = 0` dapat memicu *instant catastrophic degradation* (latensi melompat detik demi detik hingga OOM death) saat Redis menampung beban penulisan berskala enterprise.
4. **Pemisahan Peran Arsitektur**: Pada throughput ultra-tinggi, node Master tidak boleh dibebani oleh *disk sync lockups*. Konfigurasi enterprise memisahkan persistensi disk ke read-replica khusus, mengisolasi storage drive (NVMe berkecepatan tinggi dengan `noatime`), dan menyinkronkan snapshot secara terjadwal di luar jam sibuk operasional.