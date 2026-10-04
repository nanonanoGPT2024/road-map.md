# Bab 06 Module 01: Ketahanan Data: Mekanisme Persistence, RDB, & AOF

---

## 01. Identitas Modul
* **Track:** Backend and Database Infrastructure
* **Category:** 04-Backend-and-Database
* **Course:** Redis Production-Grade Architecture
* **Module:** Bab 06 Module 01: Ketahanan Data: Mekanisme Persistence, RDB, & AOF
* **Level:** Advanced (L4/Principal Track)
* **Estimated Time:** 180 Menit

---

## 02. Learning Objectives
1. Menganalisis cara kerja internal mekanisme persistensi Redis: RDB (Redis Database Snapshotting), AOF (Append Only File), dan Multi-Part/Hybrid Persistence.
2. Memahami mekanisme low-level OS kernel (`fork()`, *Copy-on-Write*, `fsync`, page cache eviction) yang memengaruhi latensi p99 dan konsumsi memori Redis.
3. Mengonfigurasi parameter persistensi deterministik untuk mengoptimalkan *Recovery Point Objective* (RPO) dan *Recovery Time Objective* (RTO) pada beban transaksi tinggi.
4. Mendiagnosis, memulihkan, dan memvalidasi file RDB/AOF yang mengalami *corruption* atau anomali IO boundary.

---

## 03. Concept Map Diagram ASCII

```
                                  +-----------------------+
                                  | Redis In-Memory State |
                                  |    (Main Process)     |
                                  +-----------+-----------+
                                              |
                     +------------------------+------------------------+
                     | fork() (Copy-on-Write)                          | AOF Buffer (append)
                     v                                                 v
        +-------------------------+                       +-------------------------+
        | Background Child (bgsave|                       |   aof_buf (RAM Chunk)   |
        +------------+------------+                       +------------+------------+
                     |                                                 |
            Raw Binary Serialize                                  write(2) to Page Cache
                     |                                                 |
                     v                                                 v
        +-------------------------+                       +-------------------------+
        |   Temporary .rdb File   |                       |    OS OS Page Cache     |
        +------------+------------+                       +------------+------------+
                     |                                                 |
            rename(2) [Atomic]                                    fsync(2) policy
                     |                                    (always | everysec | no)
                     v                                                 |
        +-------------------------+                                    v
        |    dump.rdb on Disk     |                       +-------------------------+
        +-------------------------+                       |    appendonly.aof       |
                                                          |  (Base + Incremental)   |
                                                          +-------------------------+
```

---

## 04. Mengapa Relevan
Redis dirancang fundamentally sebagai *in-memory data structure store*. Karakteristik volatil RAM menyebabkan data hilang seketika saat proses crash, OOM-killed, atau host failure. Pada skenario enterprise (misal: shopping cart, session broker, payment ledger, token cache berdurasi panjang), hilangnya data in-memory dapat memicu *cascading failures* pada database relasional hilir (misal: Postgres/MySQL) akibat *cache stampede*. 

Memahami trade-off mekanis antara RDB (snapshotting point-in-time) dan AOF (write-ahead transaction logging) memungkinkan Principal Engineer merancang sistem yang mencapai RPO mendekati 0 detik tanpa mendegradasi target latensi sub-milidetik throughput Redis.

---

## 05. Anatomi Konsep Inti

### 1. RDB (Redis Database) Internals
* **Mekanisme:** Point-in-time snapshotting. Redis mengompilasi seluruh dataset in-memory ke representasi biner terkompresi LZF pada disk (`dump.rdb`).
* **Kernel Level:** Redis mengeksekusi *system call* `fork()`. OS membuat child process yang membagi *virtual memory page table* parent via *Copy-on-Write* (CoW). Child membaca memory snapshot secara statis dan menulis ke disk tanpa memblokir thread eksekusi utama, kecuali saat alokasi CoW terjadi jika parent memodifikasi page yang sama.
* **Pro & Kontra:** Ukuran file kompak, proses *startup recovery* sangat cepat, namun RPO bergantung pada interval snapshot (potensi data loss dari interval snapshot terakhir).

### 2. AOF (Append Only File) Internals
* **Mekanisme:** Logging setiap operasi mutasi (*write command*) dalam format RESP (Redis Serialization Protocol) secara sekuensial.
* **Fsync Policies:**
  * `appendfsync always`: Mengeksekusi `fsync(2)` setelah setiap write. RPO paling aman (~0), throughput disk I/O terendah.
  * `appendfsync everysec`: Background thread mengeksekusi `fsync(2)` per detik secara asinkron. Standar industri: RPO $\le$ 2 detik jika thread terblokir.
  * `appendfsync no`: Menyerahkan flushing buffer disk ke OS kernel (umumnya 30 detik pada Linux).

### 3. AOF Rewrite Engine (Multi-Part AOF sejak Redis 7.0)
* **Kelemahan Legasi:** Single file AOF rentan race condition dan I/O heavy saat rewriting.
* **Multi-Part AOF:** Memecah AOF menjadi:
  * **Base File:** Snapshot data state (bisa berformat RDB atau AOF mentah) yang dibuat saat rewrite.
  * **Incremental Files:** Log mutasi yang dibuat selama base file sedang ditulis.
  * **Manifest File (`appendonly.aof.manifest`):** Melacak status, urutan, dan metadata file base & incremental secara atomik.

---

## 06. Panduan Implementasi Step-by-Step

### Step 1: Konfigurasi Memory Allocation Kernel (Host OS)
Redis membutuhkan overcommit memory aktif agar `fork()` tidak gagal saat penggunaan RAM parent mencapai >50%.

```bash
# Set overcommit memory secara realtime
sudo sysctl vm.overcommit_memory=1

# Persistensikan ke sysctl.conf
echo "vm.overcommit_memory = 1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### Step 2: Konfigurasi Hybrid Persistence pada `redis.conf`
Terapkan arsitektur hybrid di mana AOF memanfaatkan RDB preamble untuk recovery instan dengan durabilitas tinggi.

```text
# Lokasi direktori data
dir /var/lib/redis
dbfilename dump.rdb

# RDB Snapshots (Fallback backup)
# Format: save <seconds> <changes>
save 900 1
save 300 10
save 60 10000

# Kompresi dan Checksum
rdbcompression yes
rdbchecksum yes
stop-writes-on-bgsave-error yes

# AOF Setup
appendonly yes
appendfilename "appendonly.aof"
appenddirname "appendonlydir"
appendfsync everysec
no-appendfsync-on-rewrite yes

# AOF Rewrite Triggers
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Hybrid RDB-AOF Persistence
aof-use-rdb-preamble yes
```

### Step 3: Trigger Background Persistence Secara Programatik
Inisialisasi rewrite atau save manual saat proses deployment atau maintenance window via Redis CLI.

```bash
# Eksekusi RDB snapshotting asinkron
redis-cli -a "SecureAuthKeyToken123" BGSAVE

# Pantau status eksekusi hingga sukses
redis-cli -a "SecureAuthKeyToken123" INFO persistence | grep -E "rdb_bgsave_in_progress|aof_rewrite_in_progress"
```

---

## 07. Contoh Kasus Sederhana

Berikut adalah script shell interaktif untuk mengamati secara real-time bagaimana mutasi data diterjemahkan menjadi file RDB dan AOF di disk.

```bash
#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="/tmp/redis-persist-demo"
mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

echo "=== Menjalankan Redis Instance Sementara ==="
cat <<EOF > redis.conf
port 6399
dir ${DATA_DIR}
appendonly yes
appenddirname "appenddir"
appendfsync always
aof-use-rdb-preamble yes
save ""
EOF

redis-server redis.conf --daemonize yes

sleep 1

echo "=== Mengirim Mutasi Data ==="
redis-cli -p 6399 SET user:1001 "Alice Smith"
redis-cli -p 6399 INCR counter:pageviews
redis-cli -p 6399 RPUSH queue:events "INIT" "PROCESS"

echo "=== Memeriksa Log Direktori AOF ==="
ls -la ${DATA_DIR}/appenddir/

echo "=== Membaca Payload AOF Incremental Mentah ==="
# Menampilkan 20 baris pertama representasi RESP
head -n 20 ${DATA_DIR}/appenddir/appendonly.aof.*.incr.aof

echo "=== Mematikan Server Demo ==="
redis-cli -p 6399 SHUTDOWN NOSAVE
rm -rf "$DATA_DIR"
echo "Demo Selesai."
```

---

## 08. Implementasi Production-Grade Lengkap Kode

Berikut adalah production-grade maintenance toolkit berbasis Python menggunakan `redis-py` yang menangani triggered sync snapshotting, metric auditing, dan safe AOF background rewrite orchestration dengan circuit-breaker.

```python
#!/usr/bin/env python3
"""
Production-Grade Redis Persistence Orchestration & Health Audit Toolkit.
Dirancang untuk integrasi pipeline cron automasi backup enterprise.
"""

import sys
import time
import logging
from typing import Dict, Any
import redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("RedisPersistenceOrchestrator")

class RedisPersistenceManager:
    def __init__(self, host: str = "127.0.0.1", port: int = 6379, password: str = None, timeout: int = 10):
        self.client = redis.Redis(
            host=host,
            port=port,
            password=password,
            socket_timeout=timeout,
            decode_responses=True
        )

    def get_persistence_status(self) -> Dict[str, Any]:
        """Audit status persistensi internal Redis."""
        try:
            info = self.client.info("persistence")
            memory = self.client.info("memory")
            return {
                "rdb_last_bgsave_status": info.get("rdb_last_bgsave_status"),
                "rdb_bgsave_in_progress": bool(info.get("rdb_bgsave_in_progress")),
                "rdb_last_save_time": info.get("rdb_last_save_time"),
                "rdb_changes_since_last_save": info.get("rdb_changes_since_last_save"),
                "aof_enabled": bool(info.get("aof_enabled")),
                "aof_rewrite_in_progress": bool(info.get("aof_rewrite_in_progress")),
                "aof_current_size": info.get("aof_current_size", 0),
                "aof_base_size": info.get("aof_base_size", 0),
                "used_memory_human": memory.get("used_memory_human"),
                "used_memory_peak_human": memory.get("used_memory_peak_human"),
                "mem_fragmentation_ratio": memory.get("mem_fragmentation_ratio"),
            }
        except RedisError as e:
            logger.error(f"Gagal mengambil metadata Redis: {str(e)}")
            raise

    def trigger_safe_aof_rewrite(self, timeout_sec: int = 300) -> bool:
        """
        Menjalankan BGREWRITEAOF secara aman. Menunggu child process aktif
        dan memvalidasi integritas hingga proses terminasi sukses.
        """
        status = self.get_persistence_status()
        
        if status["rdb_bgsave_in_progress"] or status["aof_rewrite_in_progress"]:
            logger.warning("Operasi persistensi lain sedang berjalan. Abort trigger baru.")
            return False

        logger.info("Memulai Background AOF Rewrite...")
        try:
            response = self.client.bgrewriteaof()
            logger.info(f"Redis response: {response}")
        except RedisError as exc:
            logger.error(f"Gagal mengeksekusi BGREWRITEAOF: {str(exc)}")
            return False

        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            time.sleep(2)
            cur_status = self.get_persistence_status()
            if not cur_status["aof_rewrite_in_progress"]:
                logger.info("BGREWRITEAOF selesai dieksekusi dengan sukses.")
                return True
            logger.info("AOF rewrite sedang berjalan di background...")

        logger.error(f"Timeout ({timeout_sec}s) tercapai saat menunggu AOF rewrite.")
        return False

    def trigger_safe_bgsave(self, timeout_sec: int = 300) -> bool:
        """Menjalankan BGSAVE dan menunggu sinkronisasi atomic RDB selesai."""
        status = self.get_persistence_status()
        if status["rdb_bgsave_in_progress"]:
            logger.warning("BGSAVE sedang berjalan.")
            return False

        logger.info("Mengeksekusi BGSAVE...")
        try:
            self.client.bgsave()
        except RedisError as exc:
            logger.error(f"Gagal mengeksekusi BGSAVE: {str(exc)}")
            return False

        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            time.sleep(2)
            cur_status = self.get_persistence_status()
            if not cur_status["rdb_bgsave_in_progress"]:
                if cur_status["rdb_last_bgsave_status"] == "ok":
                    logger.info("BGSAVE berhasil diselesaikan dan diverifikasi.")
                    return True
                else:
                    logger.error(f"BGSAVE gagal dengan status: {cur_status['rdb_last_bgsave_status']}")
                    return False
        
        logger.error(f"Timeout ({timeout_sec}s) tercapai saat menunggu BGSAVE.")
        return False

if __name__ == "__main__":
    manager = RedisPersistenceManager(host="127.0.0.1", port=6379)
    try:
        logger.info("Audit Status Awal:")
        init_metrics = manager.get_persistence_status()
        for k, v in init_metrics.items():
            logger.info(f"  {k}: {v}")

        logger.info("Memulai Orkestrasi Snapshot RDB...")
        if manager.trigger_safe_bgsave():
            logger.info("Prosedur snapshot snapshot RDB sukses.")
        else:
            logger.critical("Prosedur snapshot RDB gagal.")
            sys.exit(1)

    except RedisConnectionError:
        logger.critical("Koneksi ke Redis Daemon gagal. Pastikan instance berjalan.")
        sys.exit(2)
```

---

## 09. Diagram Alur Kerja ASCII

```
[Klien Mengirim Write Command]
              |
              v
[Redis Event Loop Engine] -------------------------------------+
              |                                                |
    +---------+---------+                                      |
    |                   |                                      |
    v                   v                                      v
[Update RAM]    [Append to AOF Buffer]                 [Periksa Aturan SAVE]
                        |                                      |
                        v                                      v
               [appendfsync Policy]                 [Kriteria RDB Terpenuhi?]
              /         |          \                           |
        always       everysec       no                         v
          |             |            |               [fork() Child Process]
          v             v            v                         |
     [fsync(2)      [Thread Pool   [Biarkan OS                 v
     Sekejap]        fsync tiap     Flushing]        [Child Baca Memory Snapshot via CoW]
                     1 Detik]                                  |
                        |                                      v
                        v                            [Tulis ke dump.rdb.tmp]
               [appendonly.aof Disk]                           |
                                                               v
                                                    [Atomic rename(2) ke dump.rdb]
```

---

## 10. Analisis Trade-offs

| Parameter | RDB Only | AOF (`appendfsync everysec`) | Hybrid Persistence (RDB Preamble + AOF) |
| :--- | :--- | :--- | :--- |
| **RPO (Data Loss Potential)** | Tinggi (Sesuai interval: 5–15 menit data hilang) | Sangat Rendah ($\le 1-2$ detik) | Sangat Rendah ($\le 1-2$ detik) |
| **RTO (Recovery Speed)** | Sangat Cepat (Zero parsing overhead, raw biner) | Lambat (Harus merekonstruksi jutaan RESP lines) | Sangat Cepat (Load base RDB + replaying minimal AOF) |
| **CPU / System Load** | Fork spike periodik (Heavy memory overhead CoW) | Stabil, continuous background IO overhead | Moderat, rewrite engine periodik |
| **Disk Storage Footprint** | Minimal (Terkompresi LZF) | Sangat Besar jika log write throughput tinggi | Terkendali (Base terkompresi, incremental kecil) |
| **Dampak Latensi Write** | Minimal pada main thread | Sangat rendah (dikelola bio thread OS) | Sangat rendah |

---

## 11. Best Practices & Antipatterns

### Best Practices
* **Wajib Set `vm.overcommit_memory = 1`:** Mencegah Linux OOM Killer mengeksekusi child process saat redis mengalokasikan fork memory mapping.
* **Nonaktifkan Transparent Huge Pages (THP):** THP meningkatkan memory allocation latency dari $4\text{KB}$ page menjadi $2\text{MB}$ chunk, menyebabkan pembengkakan memori dramatis selama *Copy-on-Write*.
* **Gunakan Hybrid Mode (`aof-use-rdb-preamble yes`):** Standar de-facto untuk kombinasi RTO tercepat dan RPO terketat.
* **Gunakan Dedicated Block Storage (SSD/NVMe):** Hindari network storage (seperti NFS atau low-tier AWS EBS gp2 tanpa bursting) yang rentan disk stall.

### Antipatterns
* **Menjalankan `SAVE` (Synchronous Blocking Save):** Perintah `SAVE` mengeksekusi dumping pada main event-loop thread. Semua operasi klien lain akan diblokir hingga penulisan selesai. Gunakan selalu `BGSAVE`.
* **Setting `appendfsync always` pada High-Throughput System:** Menghancurkan performa Redis dari ratusan ribu IOPS menjadi setara throughput I/O piringan disk fisik (ratusan IOPS).
* **Mengabaikan Disk Space Monitoring untuk AOF Rewrite:** Proses rewriting membutuhkan kapasitas sisa disk minimal $1.5\times$ dari ukuran file AOF saat ini. Kehabisan disk space akan melumpuhkan engine database.

---

## 12. Security Hardening

* **Restriksi File System Permission:**
  File snapshot RDB dan append-only memuat data mentah (raw plain-text strings) tanpa enkripsi native pada versi open-source standar.
  ```bash
  sudo chown -R redis:redis /var/lib/redis
  sudo chmod 700 /var/lib/redis
  sudo chmod 600 /var/lib/redis/dump.rdb
  sudo chmod -R 600 /var/lib/redis/appendonlydir/ || true
  ```
* **Disk-Level Encryption (LUKS / dm-crypt):** Pastikan mount point `/var/lib/redis` berada di atas block device yang terenkripsi (*Encryption-at-Rest*), memitigasi pencurian disk fisik/snapshot VM.
* **Blokir Command Berbahaya:** Nonaktifkan akses langsung klien terhadap trigger persistensi manual menggunakan directive rename pada `redis.conf`:
  ```text
  rename-command BGREWRITEAOF ""
  rename-command BGSAVE ""
  rename-command SAVE ""
  rename-command CONFIG "ADMIN_SECRET_CONFIG_CMD"
  ```

---

## 13. Observabilitas & Debugging

### Metrik Kritis untuk Monitoring (Prometheus Redis Exporter)
1. `rdb_last_bgsave_status`: Harus selalu bernilai `ok`. Status `err` menandakan I/O failure atau OOM.
2. `rdb_last_bgsave_time_sec`: Durasi eksekusi background child. Jika durasi terus meningkat, waspadai saturasi I/O disk.
3. `aof_delayed_fsync`: Jumlah event di mana main thread menunda write karena background `fsync` memblokir I/O queue. Metrik ini harus bernilai **0**.
4. `mem_fragmentation_ratio`: Rasio alokasi kernel terhadap alokasi Redis. Pantau lonjakan saat proses `fork()` berlangsung.

### Diagnosis via Command-Line
```bash
# Cek apakah terjadi disk stall / fsync blocking
redis-cli INFO persistence | grep aof_delayed_fsync

# Monitor memory peak dan CoW memory footprint
redis-cli INFO memory | grep -E "used_memory_peak_human|mem_fragmentation_ratio"

# Memeriksa latency spike akibat fork OS system call
redis-cli --latency -h 127.0.0.1 -p 6379
```

---

## 14. Benchmarking & Performance

Mengukur dampak penulisan persistensi terhadap latensi operasi write menggunakan tool `redis-benchmark`.

```bash
# 1. Benchmark Baseline (In-Memory Only, Persistensi Dimatikan)
redis-benchmark -h 127.0.0.1 -p 6379 -t set,get -n 100000 -q

# 2. Benchmark AOF dengan appendfsync everysec
# Amati penurunan throughput dan pergeseran latensi p99
redis-benchmark -h 127.0.0.1 -p 6379 -t set -n 100000 -d 1024 -P 16 -q

# 3. Benchmark AOF dengan appendfsync always (Stress Test Disk I/O)
# Memperlihatkan degradasi ekstrem akibat disk queue bottleneck
redis-cli CONFIG SET appendfsync always
redis-benchmark -h 127.0.0.1 -p 6379 -t set -n 5000 -d 1024 -q
# Kembalikan ke everysec setelah selesai
redis-cli CONFIG SET appendfsync everysec
```

---

## 15. Hands-on Lab Mini-Project

### Skenario: Disaster Recovery & Corrupted AOF Repair
Sebuah crash keras (hard host crash) menyebabkan proses write AOF terpotong di tengah-tengah frame RESP. Redis menolak booting (`Bad file format reading the append only file`). 

### Langkah Eksekusi:

1. **Simulasikan Crash dan Korupsi File AOF:**
```bash
mkdir -p /tmp/redis-lab && cd /tmp/redis-lab
cat <<EOF > redis.conf
port 6400
dir /tmp/redis-lab
appendonly yes
appenddirname "appenddir"
appendfsync always
EOF

redis-server redis.conf --daemonize yes
redis-cli -p 6400 SET key1 "Data Valid 1"
redis-cli -p 6400 SET key2 "Data Valid 2"
redis-cli -p 6400 SHUTDOWN

# Korupsikan file incremental AOF secara sengaja
TARGET_AOF=$(ls /tmp/redis-lab/appenddir/*.incr.aof)
echo "CORRUPTED_GARBAGE_PAYLOAD_OFFSET_BROKEN_FRAME" >> "$TARGET_AOF"
```

2. **Verifikasi Kegagalan Booting:**
```bash
redis-server redis.conf
# Server akan crash/exit seketika dan menampilkan log error persistensi
```

3. **Gunakan Utility Perbaikan `redis-check-aof`:**
```bash
redis-check-aof --fix "$TARGET_AOF"
```
Konfirmasikan perbaikan dengan menekan `y`. Utility akan memotong (truncate) frame yang korup secara atomik.

4. **Validasi Pemulihan:**
```bash
redis-server redis.conf --daemonize yes
redis-cli -p 6400 GET key1
redis-cli -p 6400 GET key2
redis-cli -p 6400 SHUTDOWN
```

---

## 16. Automated Testing & Verification

Berikut test suite Python (`pytest`) untuk menguji persistensi data terhadap proses *simulated crash* (`SIGKILL`).

```python
# test_persistence.py
import os
import signal
import subprocess
import time
import pytest
import redis

REDIS_PORT = 6410
WORK_DIR = "/tmp/redis-test-persistence"

@pytest.fixture(scope="module", autouse=True)
def redis_instance():
    os.makedirs(WORK_DIR, exist_ok=True)
    conf_path = os.path.join(WORK_DIR, "redis.conf")
    with open(conf_path, "w") as f:
        f.write(f"""
        port {REDIS_PORT}
        dir {WORK_DIR}
        appendonly yes
        appenddirname "test_appenddir"
        appendfsync always
        save ""
        """)
    
    proc = subprocess.Popen(["redis-server", conf_path])
    time.sleep(1)
    yield proc
    
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except:
        proc.kill()
    subprocess.run(["rm", "-rf", WORK_DIR])

def test_data_persistence_across_hard_kill():
    r = redis.Redis(port=REDIS_PORT, decode_responses=True)
    
    # 1. Write Initial Data
    for i in range(100):
        r.set(f"test:key:{i}", f"val_{i}")
    
    # 2. Get PID Redis Server
    pid = None
    with open(os.path.join(WORK_DIR, "redis.conf"), "r") as f:
        pass
    # Mengambil PID melalui Redis INFO
    info = r.info("server")
    pid = info["process_id"]
    
    # 3. Kirim SIGKILL (-9) mensimulasikan mati lampu / kernel panic
    os.kill(pid, signal.SIGKILL)
    time.sleep(1)

    # 4. Restart Redis Server dari file persistence
    conf_path = os.path.join(WORK_DIR, "redis.conf")
    proc2 = subprocess.Popen(["redis-server", conf_path])
    time.sleep(1)

    try:
        r_restarted = redis.Redis(port=REDIS_PORT, decode_responses=True)
        # 5. Verifikasi Integritas Data
        for i in range(100):
            val = r_restarted.get(f"test:key:{i}")
            assert val == f"val_{i}", f"Data mismatch pada index {i}!"
        
        info_pers = r_restarted.info("persistence")
        assert info_pers["aof_enabled"] == 1
    finally:
        proc2.terminate()
        proc2.wait(timeout=2)
```

Untuk mengeksekusi test:
```bash
pytest test_persistence.py -v
```

---

## 17. Troubleshooting Guide

| Gejala Masalah | Akar Penyebab (*Root Cause*) | Prosedur Solusi Remediasi |
| :--- | :--- | :--- |
| `MISCONF Redis is configured to save RDB snapshots, but is currently not able to persist on disk.` | Ruang disk penuh, permission direktori ditolak, atau `vm.overcommit_memory = 0` saat data RAM besar. | 1. Cek disk space: `df -h`<br>2. Verifikasi permission direktori `dir`.<br>3. Set `sysctl vm.overcommit_memory=1`.<br>4. Untuk unblock darurat: `CONFIG SET stop-writes-on-bgsave-error no` *(Hanya sementara!)*. |
| Latensi aplikasi mengalami lonjakan tajam (Spike) periodik setiap beberapa menit. | `fork()` child process terlalu lama karena ukuran page table besar atau THP aktif. | 1. Nonaktifkan Transparent Huge Pages (`echo never > /sys/kernel/mm/transparent_hugepage/enabled`).<br>2. Jadwalkan `bgsave` / `bgrewriteaof` manual saat low-traffic via cron. |
| Redis menolak start setelah host failure dengan error corrupt AOF file. | Non-graceful shutdown meninggalkan partial RESP command di ujung file AOF. | Jalankan utility `redis-check-aof --fix <path_to_aof_file>`. Pastikan backup file dibuat sebelum eksekusi perbaikan. |
| Memory usage berlipat ganda tiba-tiba saat BGREWRITEAOF. | Beban mutasi write tinggi selama child process aktif memaksa CoW menduplikasi memory pages. | Sediakan RAM overhead minimal 30–50% di atas `maxmemory` jika sistem memiliki write-throughput sangat masif. |

---

## 18. Checklist Produksi

- [ ] **Kernel Overcommit:** `vm.overcommit_memory` diatur ke `1` di `/etc/sysctl.conf`.
- [ ] **Transparent Huge Pages (THP):** THP dinonaktifkan permanen pada `/etc/rc.local` atau tuned-profile.
- [ ] **AOF Configuration:** `appendonly yes` dan `appendfsync everysec` diaktifkan untuk instance transactional.
- [ ] **Hybrid Preamble:** `aof-use-rdb-preamble yes` aktif guna memangkas durasi recovery (RTO).
- [ ] **Write Blocking Threshold:** `stop-writes-on-bgsave-error yes` dipertahankan untuk menjamin integritas data bila disk down.
- [ ] **Dedicated Mount Point:** Direktori penyimpanan `/var/lib/redis` berada pada volume penyimpanan terpisah dengan alerting utilisasi disk (>80%).
- [ ] **Command Renaming:** Command berbahaya (`SAVE`, `BGREWRITEAOF`, `BGSAVE`) dibatasi dari akses klien publik.
- [ ] **Automated Off-site Backup:** Script automasi menyalin `dump.rdb` dan manifest AOF ke Cloud Storage (S3/GCS) secara berkala.

---

## 19. Ringkasan Eksekutif
Persistensi pada Redis bukanlah pendekatan *one-size-fits-all*, melainkan kompromi matematis antara durabilitas data (**RPO**), kecepatan restorasi sistem (**RTO**), dan alokasi sumber daya komputasi. 

Snapshotting **RDB** menghasilkan artefak data ringkas untuk disaster recovery cepat dan snapshot terjadwal, namun memiliki celah kehilangan data di antara interval. **AOF** menyediakan durabilitas hampir seketika per transaksi, dengan konsekuensi write I/O disk continuous. 

Standar arsitektur modern (Redis 7+) merekomendasikan **Multi-Part Hybrid Persistence** (`aof-use-rdb-preamble yes`), yang mengombinasikan keunggulan struktur RDB terkompresi sebagai base layer dengan ringannya file incremental AOF. Konfigurasi ini harus ditopang oleh isolasi OS kernel yang ketat (`vm.overcommit_memory = 1` dan disabled THP) demi menjamin stabilitas latensi p99 database.

---

## 20. Referensi & Bacaan Lanjutan
* **Redis Official Documentation:** *Redis Persistence Demystified* — [https://redis.io/docs/management/persistence/](https://redis.io/docs/management/persistence/)
* **Linux Kernel Documentation:** *Memory Overcommit & Virtual Memory Management* — [https://www.kernel.org/doc/Documentation/vm/overcommit-accounting](https://www.kernel.org/doc/Documentation/vm/overcommit-accounting)
* **Redis Source Code Internal:** `src/aof.c` dan `src/rdb.c` di Redis Engine Repository — [https://github.com/redis/redis](https://github.com/redis/redis)
* **Martin Kleppmann:** *Designing Data-Intensive Applications* (Chapter 3: Storage and Retrieval, Write-Ahead Logging & SSTables). O'Reilly Media.