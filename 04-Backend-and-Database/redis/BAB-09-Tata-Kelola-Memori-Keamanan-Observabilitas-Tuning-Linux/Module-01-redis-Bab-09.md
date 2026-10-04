# Modul 01 Bab 09: Tata Kelola Memori, Keamanan, Observabilitas, & Tuning Linux

---

## 01: Identitas Modul
* **Domain Kurikulum:** `04-Backend-and-Database`
* **Sub-Domain:** `redis`
* **Kode Modul:** `RED-SYS-0901`
* **Tingkat Kesulitan:** Advanced / Production Engineering
* **Prasyarat:** Pemahaman arsitektur dasar Redis, Linux CLI, Bash scripting, Python/Go runtime, serta konsep dasar jaringan TCP/IP.

---

## 02: Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. Mendiagnosis dan mengendalikan alokasi memori Redis menggunakan `jemalloc`, menganalisis rasio fragmentasi (`mem_fragmentation_ratio`), dan mengonfigurasi algoritma Active Memory Defragmentation serta Eviction Policies secara presisi.
2. Mengamankan kluster Redis end-to-end melalui isolasi jaringan, ACL (Access Control Lists) granular v2, TLSv1.3 mutual authentication (mTLS), dan penonaktifan perintah administratif berisiko tinggi.
3. Membangun pipeline observabilitas tingkat produksi dengan memanfaatkan Redis Engine Metrics, Prometheus Exporter, Grafana Dashboard, Slowlog profiling, serta integrasi Extended Berkeley Packet Filter (eBPF) untuk analisis latensi kernel.
4. Menerapkan optimasi kernel Linux untuk database in-memory performa tinggi, mencakup manajemen Virtual Memory (Overcommit, Swap), TCP Network Stack tuning, I/O Subsystem, dan mitigasi latensi Transparent Huge Pages (THP).

---

## 03: Concept Map Diagram ASCII

```
+---------------------------------------------------------------------------------------------------+
|                                PRODUCTION REDIS RUNTIME ECOSYSTEM                                 |
+---------------------------------------------------------------------------------------------------+
                                                  |
         +----------------------------------------+----------------------------------------+
         |                                        |                                        |
         v                                        v                                        v
+-----------------------+              +-----------------------+              +-----------------------+
|  LINUX KERNEL TUNING  |              |   REDIS ENGINE CORE   |              |  SECURITY & ACL CORE  |
+-----------------------+              +-----------------------+              +-----------------------+
| - vm.overcommit_memory|              | - jemalloc Allocator  |              | - TLS v1.3 Encryption |
| - Disable THP         |              | - Active Defrag Engine|              | - Granular ACL Rules  |
| - net.core.somaxconn  |              | - Eviction (LFU/LRU)  |              | - Command Renaming    |
| - TCP FastOpen / Reuse|              | - Memory Limits       |              | - Protected Mode      |
+-----------------------+              +-----------------------+              +-----------------------+
         |                                        |                                        |
         +----------------------------------------+----------------------------------------+
                                                  |
                                                  v
                               +-------------------------------------+
                               |     OBSERVABILITY & MONITORING      |
                               +-------------------------------------+
                               | - INFO Metrics (RSS, Alloc, Latency)|
                               | - Prometheus Exporter Integration   |
                               | - Slowlog & Latency Monitor Engine  |
                               | - eBPF Linux Kernel Tracepoints     |
                               +-------------------------------------+
```

---

## 04: Mengapa Relevan
Redis dirancang sebagai basis data in-memory dengan latensi sub-milidetik. Namun, mengeksekusi Redis pada beban jutaan Request Per Second (RPS) pada sistem Linux tanpa penyesuaian khusus memicu masalah kritis:

* **OOM Killer Termination:** Ketidaksesuaian alokasi memori dan konfigurasi *fork-safe overcommit* memicu Linux Kernel OOM Killer mematikan proses Redis secara instan saat sinkronisasi RDB atau rewrite AOF.
* **Latency Spikes akibat THP:** Fitur Transparent Huge Pages (THP) memicu latensi tinggi (hingga ratusan milidetik) saat mekanisme Copy-on-Write (CoW) mengalokasikan halaman 2MB alih-alih 4KB.
* **Eksploitasi Keamanan:** Konfigurasi bawaan yang tidak terproteksi dan kegagalan enkripsi in-transit membuka celah serangan RCE (Remote Code Execution) dan pencurian data langsung dari RAM.

---

## 05: Anatomi Konsep Inti

```
+---------------------------------------------------------------------------------------------+
|                                    REDIS MEMORY ANATOMY                                     |
+---------------------------------------------------------------------------------------------+
|  Physical RAM Allocated by jemalloc (Resident Set Size / RSS)                               |
|  +---------------------------------------------------------------------------------------+  |
|  | Used Memory (Data Structures, Keys, Values, Buffers)                                  |  |
|  | +------------------------------------+----------------------------------------------+ |  |
|  | | Dataset (Strings, Hashes, Sets)    | Overhead (dict metadata, jemalloc meta)      | |  |
|  | +------------------------------------+----------------------------------------------+ |  |
|  | | Client Buffers (In/Out)            | Replication Backlog Buffers                  | |  |
|  | +------------------------------------+----------------------------------------------+ |  |
|  +---------------------------------------------------------------------------------------+  |
|  | Fragmentation Space (Unused memory pages retained by jemalloc due to fragmentation)  |  |
|  +---------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------+
```

### 1. Memory Engine & Allocator
Redis menggunakan `jemalloc` secara default di Linux. `jemalloc` membagi alokasi memori ke dalam beberapa *arenas* dan *bins* (ukuran tetap) untuk meminimalkan *lock contention* dan fragmentasi.
* **Used Memory (`used_memory`):** Total byte yang dialokasikan oleh Redis untuk menyimpan data dan metadata.
* **RSS Memory (`used_memory_rss`):** Total byte yang dilihat oleh kernel Linux (Resident Set Size).
* **Fragmentation Ratio:** 
  $$\text{mem\_fragmentation\_ratio} = \frac{\text{used\_memory\_rss}}{\text{used\_memory}}$$
  * Ratio $> 1.5$: Terjadi fragmentasi tinggi (RAM terbuang).
  * Ratio $< 1.0$: Sistem mulai melakukan *swapping* ke disk (latensi anjlok drastis).

### 2. Linux OS Subsystem Tuning Parameters
* `vm.overcommit_memory = 1`: Mengizinkan alokasi memori melebihi kapasitas fisik (diperlukan saat operasi `fork()` untuk BGSAVE/AOF rewrite tanpa memicu kegagalan alokasi memori virtual).
* `vm.swappiness = 1` (atau `0`): Meminimalkan atau menonaktifkan kernel swap untuk proses Redis, menghindari I/O disk stall pada memori in-flight.
* **Transparent Huge Pages (THP):** Wajib dinonaktifkan (`never`). CoW pada halaman 2MB meningkatkan latensi dan menyebabkan degradasi alokasi memori hingga berkali-kali lipat selama proses *snapshot*.

### 3. ACL v2 & TLS Engine
Redis Engine menyediakan *role-based access control* per-perintah dan per-keypattern:
```text
user <username> on #<password_hash> ~<key_pattern> &<channel_pattern> +@<category> -<forbidden_command>
```
Proses TLSv1.3 menangani enkripsi data langsung di lapisan socket menggunakan OpenSSL, menghilangkan kebutuhan akan reverse proxy TLS lokal seperti Stunnel.

---

## 06: Panduan Implementasi Step-by-Step

### Langkah 1: Linux Kernel Parameter Hardening via Sysctl
Terapkan parameter kernel berikut ke `/etc/sysctl.d/99-redis-performance.conf`:

```ini
# Izinkan overcommit memori untuk mendukung snapshot BGSAVE fork
vm.overcommit_memory = 1

# Minimalisasi paging memory ke SWAP device
vm.swappiness = 1

# Maksimalkan socket listen backlog untuk koneksi concurrent tinggi
net.core.somaxconn = 65535

# Maksimalkan throughput TCP buffer
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# Aktifkan TCP FastOpen & reuse TIME_WAIT sockets
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15

# Tingkatkan batas file descriptor sistem
fs.file-max = 2097152
```

Terapkan parameter:
```bash
sudo sysctl --system
```

### Langkah 2: Nonaktifkan Transparent Huge Pages (THP)
Buat systemd service unit `/etc/systemd/system/disable-thp.service`:

```ini
[Unit]
Description=Disable Transparent Huge Pages (THP) for Redis
DefaultDependencies=no
After=sysinit.target local-fs.target
Before=redis.service

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo never > /sys/kernel/mm/transparent_hugepage/enabled && echo never > /sys/kernel/mm/transparent_hugepage/defrag'

[Install]
WantedBy=basic.target
```

Aktifkan service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now disable-thp.service
```

### Langkah 3: Konfigurasi Keamanan ACL & TLS Redis
Edit konfigurasi `/etc/redis/redis.conf`:

```conf
# Networking & Port Security
port 0
tls-port 6379
tls-cert-file /etc/redis/tls/redis.crt
tls-key-file /etc/redis/tls/redis.key
tls-ca-cert-file /etc/redis/tls/ca.crt
tls-auth-clients yes
tls-protocols "TLSv1.3"
tls-ciphersuites TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256
tls-prefer-server-ciphers yes

# Memory Management
maxmemory 8gb
maxmemory-policy allkeys-lfu
maxmemory-samples 10

# Active Defragmentation
activedefrag yes
active-defrag-ignore-bytes 100mb
active-defrag-threshold-lower 10
active-defrag-threshold-upper 30
active-defrag-cycle-min 5
active-defrag-cycle-max 50
active-defrag-max-scan-fields 1000

# Security Rules & ACL File
aclfile /etc/redis/users.acl

# Disable Dangerous Commands
rename-command FLUSHALL ""
rename-command FLUSHDB ""
rename-command DEBUG ""
rename-command KEYS ""
```

---

## 07: Contoh Kasus Sederhana

Penerapan simulasi pembersihan memori otomatis menggunakan Eviction Policy LFU (Least Frequently Used) vs LRU (Least Recently Used).

```bash
# Uji coba menggunakan redis-cli dengan TLS aktif
redis-cli --tls \
  --cert /etc/redis/tls/client.crt \
  --key /etc/redis/tls/client.key \
  --cacert /etc/redis/tls/ca.crt \
  -h 127.0.0.1 -p 6379

# Memeriksa utilisasi memori real-time
127.0.0.1:6379> INFO memory
# Output:
# used_memory:1073741824
# used_memory_human:1.00G
# used_memory_rss:1181116006
# mem_fragmentation_ratio:1.10
# mem_allocator:jemalloc-5.3.0

# Verifikasi parameter Defragmentasi Aktif
127.0.0.1:6379> CONFIG GET activedefrag
1) "activedefrag"
2) "yes"
```

---

## 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi automated provisioning dan observability stack untuk Redis menggunakan Python, `redis-py` (dengan connection pooling & TLS), serta custom Prometheus Exporter untuk metrik internal engine.

```python
#!/usr/bin/env python3
"""
Production Redis Client, Monitor, and Health Check Suite.
Engineered for High-Throughput and Observability.
"""

import os
import sys
import time
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional
import redis
from prometheus_client import start_http_server, Gauge, Counter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(process)d] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("redis-sentinel-monitor")

# Prometheus Metrics Definitions
METRIC_MEM_USED = Gauge("redis_mem_used_bytes", "Total used memory in bytes")
METRIC_MEM_RSS = Gauge("redis_mem_rss_bytes", "Resident Set Size memory in bytes")
METRIC_FRAG_RATIO = Gauge("redis_mem_fragmentation_ratio", "Memory fragmentation ratio")
METRIC_CONNECTED_CLIENTS = Gauge("redis_connected_clients", "Number of connected clients")
METRIC_OPS_PER_SEC = Gauge("redis_instantaneous_ops_per_sec", "Operations per second")
METRIC_EVICTED_KEYS = Counter("redis_evicted_keys_total", "Total number of evicted keys")
METRIC_SLOWLOG_ENTRIES = Counter("redis_slowlog_total", "Total slowlog events recorded")


@dataclass(frozen=True)
class RedisConfig:
    host: str
    port: int
    username: str
    password: str
    ca_cert: str
    client_cert: str
    client_key: str
    max_connections: int = 50
    socket_timeout: float = 2.0
    socket_connect_timeout: float = 2.0


class ProductionRedisManager:
    def __init__(self, config: RedisConfig):
        self.config = config
        self.pool: Optional[redis.ConnectionPool] = None
        self.client: Optional[redis.Redis] = None
        self._init_connection_pool()

    def _init_connection_pool(self) -> None:
        try:
            self.pool = redis.ConnectionPool(
                host=self.config.host,
                port=self.config.port,
                username=self.config.username,
                password=self.config.password,
                ssl=True,
                ssl_ca_certs=self.config.ca_cert,
                ssl_certfile=self.config.client_cert,
                ssl_keyfile=self.config.client_key,
                ssl_cert_reqs="required",
                max_connections=self.config.max_connections,
                socket_timeout=self.config.socket_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                retry_on_timeout=True,
                decode_responses=True
            )
            self.client = redis.Redis(connection_pool=self.pool)
            logger.info("Connection pool successfully initialized with mutual TLS.")
        except Exception as err:
            logger.critical(f"Fatal error initializing Redis Connection Pool: {err}")
            raise

    def get_client(self) -> redis.Redis:
        if not self.client:
            raise ConnectionError("Redis client is not initialized.")
        return self.client

    def collect_metrics(self) -> Dict[str, Any]:
        """Collect deep telemetry metrics directly from Redis INFO."""
        client = self.get_client()
        try:
            info_memory = client.info(section="memory")
            info_clients = client.info(section="clients")
            info_stats = client.info(section="stats")

            used_mem = int(info_memory.get("used_memory", 0))
            rss_mem = int(info_memory.get("used_memory_rss", 0))
            frag_ratio = float(info_memory.get("mem_fragmentation_ratio", 0.0))
            conn_clients = int(info_clients.get("connected_clients", 0))
            ops_sec = int(info_stats.get("instantaneous_ops_per_sec", 0))
            evicted_keys = int(info_stats.get("evicted_keys", 0))

            # Update Prometheus Gauges & Counters
            METRIC_MEM_USED.set(used_mem)
            METRIC_MEM_RSS.set(rss_mem)
            METRIC_FRAG_RATIO.set(frag_ratio)
            METRIC_CONNECTED_CLIENTS.set(conn_clients)
            METRIC_OPS_PER_SEC.set(ops_sec)
            METRIC_EVICTED_KEYS._value.set(evicted_keys)

            # Analyze Slowlog
            slowlog_len = client.slowlog_len()
            METRIC_SLOWLOG_ENTRIES._value.set(slowlog_len)

            return {
                "used_memory": used_mem,
                "used_memory_rss": rss_mem,
                "fragmentation_ratio": frag_ratio,
                "connected_clients": conn_clients,
                "ops_per_sec": ops_sec,
                "evicted_keys": evicted_keys,
                "slowlog_count": slowlog_len
            }
        except redis.RedisError as r_err:
            logger.error(f"Redis telemetry scrape failure: {r_err}")
            return {}


def main():
    config = RedisConfig(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        username=os.getenv("REDIS_USER", "app-telemetry"),
        password=os.getenv("REDIS_PASS", "SuperSecurePassword123!"),
        ca_cert="/etc/redis/tls/ca.crt",
        client_cert="/etc/redis/tls/client.crt",
        client_key="/etc/redis/tls/client.key"
    )

    manager = ProductionRedisManager(config)
    start_http_server(9121)
    logger.info("Prometheus telemetry exporter running on :9121/metrics")

    while True:
        telemetry = manager.collect_metrics()
        if telemetry:
            logger.info(
                f"[TELEMETRY] UsedMem: {telemetry['used_memory'] / (1024**2):.2f}MB | "
                f"RSS: {telemetry['used_memory_rss'] / (1024**2):.2f}MB | "
                f"FragRatio: {telemetry['fragmentation_ratio']} | "
                f"Clients: {telemetry['connected_clients']} | "
                f"Ops/s: {telemetry['ops_per_sec']}"
            )
        time.sleep(5)


if __name__ == "__main__":
    main()
```

---

## 09: Diagram Alur Kerja ASCII

### Alur Kerja Evaluasi Memori & Active Defragmentation Logic

```
   [ Incoming Data Insertion Request ]
                   |
                   v
   +-------------------------------+
   | Apakah used_memory > maxmemory?|
   +-------------------------------+
         |                   |
        YES                  NO
         |                   |
         v                   +------------------------------+
   +-------------------------------+                        |
   | Jalankan Eviction Policy       |                        |
   | (LFU/LRU/Random Eviction)     |                        |
   +-------------------------------+                        |
         |                                                  |
         v                                                  |
   +-------------------------------+                        |
   | Berhasil membebaskan memori?  |                        |
   +-------------------------------+                        |
      |                     |                               |
     NO                    YES                              |
      |                     |                               |
      v                     v                               v
[ Return Error: ]      [ Simpan Key-Value Memory di jemalloc Engine ]
[ -OOM command  ]                                   |
                                                    v
                                   +---------------------------------+
                                   | Evaluasi Defrag Engine:         |
                                   | 1. frag_ratio > threshold_lower |
                                   | 2. frag_bytes > ignore_bytes    |
                                   +---------------------------------+
                                             |              |
                                            YES             NO
                                             |              |
                                             v              v
                        +----------------------------+  [ Selesai ]
                        | Pindahkan alokasi memori   |
                        | aktif ke contiguous pages  |
                        +----------------------------+
```

---

## 10: Analisis Trade-offs

| Pendekatan / Fitur | Keuntungan (Pros) | Biaya / Limitasi (Cons) | Konsekuensi Kinerja |
|---|---|---|---|
| **Active Defrag = ON** | Mengurangi pemborosan RSS RAM secara dinamis tanpa perlu restart node. | Menggunakan CPU cycles tambahan dari main-thread atau background worker. | Peningkatan P99 latency hingga 5–15% saat proses defragmentasi intensif berjalan. |
| **maxmemory-policy: allkeys-lfu** | Mempertahankan data yang benar-benar aktif berdasarkan frekuensi akses (akurat). | Membutuhkan alokasi 24-bit LDT (Last Decrement Time) + Counter metadata per objek. | Sedikit peningkatan CPU overhead saat evaluasi sampling key dibandingkan Random Eviction. |
| **TLS v1.3 Enkripsi Native** | Keamanan data in-transit terlindungi penuh, mitigasi Man-in-the-Middle (MitM). | Enkripsi OpenSSL synchronous membebani CPU cycle. | Penurunan throughput Redis rata-rata 20% hingga 35% dibandingkan Plain TCP. |
| **Disable Swap (`swappiness=0`)** | Mencegah hard latency spike saat Linux menukar memori Redis ke disk. | Jika memori habis melampaui proteksi Redis, proses akan langsung dibunuh OOM Killer. | Fail-fast availability vs Degradasi performa ekstrim. |

---

## 11: Best Practices & Antipatterns

### Best Practices
* Gunakan **LFU (Least Frequently Used)** untuk cache dengan akses data yang tidak merata (*power-law distribution*).
* Konfigurasikan file descriptor minimal `65536` pada unit file systemd (`LimitNOFILE=65536`).
* Terapkan ACL berbasis *Principle of Least Privilege*: Pisahkan kredensial untuk writer, reader, dan monitoring/telemetry.
* Gunakan sampling default `maxmemory-samples 10` untuk mendekati algoritma LFU/LRU teoretis dengan efisiensi RAM optimal.

### Antipatterns
* **Menjalankan Redis dengan default `protected-mode no` tanpa firewall/ACL.** (Potensi eksploitasi instan).
* **Menggunakan `KEYS *` di production:** Memblokir seluruh eksekusi single-thread Redis; gunakan `SCAN` dengan `COUNT`.
* **Mengabaikan Fragmentasi Memori:** Menganggap used_memory rendah berarti aman, padahal RSS tinggi dan mendekati limit hardware Linux.
* **Membiarkan Transparent Huge Pages (THP) aktif:** Menyebabkan lonjakan latensi saat background snapshot (`fork()`).

---

## 12: Security Hardening

### 1. File ACL Granular (`/etc/redis/users.acl`)

```text
user default off
user admin on #c7ad44cbad762a5da0a452f9e854fdc1e0e7a52a38015f23f3eab1d80b931dd4 ~* &* +@all
user telemetry_exporter on #8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918 ~* +client +info +slowlog +latency -@dangerous
user app_worker on #482c811da5d5b4bc6d497ffa98491e38008a09b30b42f65a111a43a8ce799f92 ~app:cache:* ~session:* +@read +@write +@connection -@dangerous
```

### 2. Validasi Permisi File & Isolasi Jaringan
Pastikan izin file dan konfigurasi bind hanya dapat diakses oleh daemon internal:

```bash
# Pastikan kepemilikan direktori konfigurasi dan sertifikat TLS
sudo chown -R redis:redis /etc/redis
sudo chmod 700 /etc/redis/tls
sudo chmod 600 /etc/redis/tls/*
sudo chmod 640 /etc/redis/redis.conf
sudo chmod 640 /etc/redis/users.acl

# Bind eksplisit ke network interface privat saja (jika tanpa TLS)
# bind 10.240.0.15 127.0.0.1
```

---

## 13: Observabilitas & Debugging

### Profiling Latensi Internal
Redis menyediakan engine bawaan untuk mendeteksi *latency spikes*:

```bash
# Set threshold latensi dalam milidetik (misal 10ms)
CONFIG SET latency-monitor-threshold 10

# Ambil laporan latensi terburuk
LATENCY LATEST
LATENCY HISTORY command
LATENCY GRAPH command
LATENCY DOCTOR
```

### eBPF Latency Tracing pada Linux Subsystem
Gunakan eBPF `biolatency` dan `tcprtt` dari toolkit BCC untuk memeriksa apakah latensi disebabkan oleh Redis Engine atau OS Storage/Network:

```bash
# Periksa apakah ada disk write stalls (berdampak pada AOF fsync)
sudo biolatency-bpfcc -m 5

# Periksa Round-Trip-Time (RTT) network stack level kernel
sudo tcprtt-bpfcc -p 6379
```

---

## 14: Benchmarking & Performance

Jalankan pengujian baseline performa menggunakan utilitas bawaan `redis-benchmark` dengan TLS aktif:

```bash
# Benchmark throughput TLS Pipeline SET & GET
redis-benchmark --tls \
  --cert /etc/redis/tls/client.crt \
  --key /etc/redis/tls/client.key \
  --cacert /etc/redis/tls/ca.crt \
  -h 127.0.0.1 -p 6379 \
  -c 50 \
  -n 1000000 \
  -t set,get \
  -q \
  -P 16
```

### Target Evaluasi Throughput vs Latency Table:
* P50 Latency: $< 0.8\text{ ms}$
* P99 Latency: $< 2.5\text{ ms}$
* P99.9 Latency: $< 5.0\text{ ms}$
* Min Throughput: $> 100,000\text{ RPS}$ (pada CPU modern multi-core, non-blocking I/O threads aktif).

---

## 15: Hands-on Lab Mini-Project

### Skenario
Konfigurasikan instance Redis mandiri yang di-hardening secara penuh dengan pembatasan memori ketat (128MB), Active Defrag aktif, dan pengamanan ACL non-root.

### Step 1: Inisialisasi Lingkungan & TLS Keypairs
```bash
mkdir -p /tmp/redis-lab/tls && cd /tmp/redis-lab/tls

# Generate CA Key & Cert
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -sha256 -key ca.key -days 365 -subj "/CN=Redis-Lab-CA" -out ca.crt

# Generate Server Key & Cert
openssl genrsa -out redis.key 2048
openssl req -new -sha256 -key redis.key -subj "/CN=127.0.0.1" -out redis.csr
openssl x509 -req -in redis.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out redis.crt -days 365 -sha256
```

### Step 2: Konfigurasi Sandbox Redis (`/tmp/redis-lab/redis-test.conf`)
```conf
port 0
tls-port 7379
tls-cert-file /tmp/redis-lab/tls/redis.crt
tls-key-file /tmp/redis-lab/tls/redis.key
tls-ca-cert-file /tmp/redis-lab/tls/ca.crt
tls-auth-clients yes

maxmemory 128mb
maxmemory-policy allkeys-lfu
activedefrag yes
active-defrag-ignore-bytes 10mb
active-defrag-threshold-lower 5

protected-mode yes
user default off
user testadmin on >SecurePass789! ~* &* +@all
```

### Step 3: Eksekusi & Validasi
```bash
# Jalankan Redis instance
redis-server /tmp/redis-lab/redis-test.conf &

# Verifikasi koneksi berhasil menggunakan kredensial TLS & ACL
redis-cli --tls \
  --cert /tmp/redis-lab/tls/redis.crt \
  --key /tmp/redis-lab/tls/redis.key \
  --cacert /tmp/redis-lab/tls/ca.crt \
  -h 127.0.0.1 -p 7379 \
  --user testadmin \
  --pass SecurePass789! \
  PING
```

---

## 16: Automated Testing & Verification

Berikut skrip pengujian berbasis `pytest` untuk memverifikasi hardening parameter sistem dan Redis instance secara otomatis:

```python
import pytest
import redis
import os
import subprocess

@pytest.fixture(scope="module")
def redis_client():
    client = redis.Redis(
        host="127.0.0.1",
        port=7379,
        username="testadmin",
        password="SecurePass789!",
        ssl=True,
        ssl_ca_certs="/tmp/redis-lab/tls/ca.crt",
        ssl_certfile="/tmp/redis-lab/tls/redis.crt",
        ssl_keyfile="/tmp/redis-lab/tls/redis.key",
        ssl_cert_reqs="required",
        decode_responses=True
    )
    yield client
    client.close()

def test_overcommit_memory_sysctl():
    val = subprocess.check_output(["sysctl", "-n", "vm.overcommit_memory"]).decode().strip()
    assert val == "1", f"Expected vm.overcommit_memory=1, got {val}"

def test_thp_disabled():
    with open("/sys/kernel/mm/transparent_hugepage/enabled", "r") as f:
        content = f.read()
    assert "[never]" in content, f"THP is not disabled: {content}"

def test_redis_maxmemory_configuration(redis_client):
    max_mem = redis_client.config_get("maxmemory").get("maxmemory")
    assert int(max_mem) == 134217728, f"Maxmemory expected 128MB, got {max_mem}"

def test_redis_eviction_policy(redis_client):
    policy = redis_client.config_get("maxmemory-policy").get("maxmemory-policy")
    assert policy == "allkeys-lfu", f"Expected allkeys-lfu policy, got {policy}"

def test_activedefrag_enabled(redis_client):
    defrag = redis_client.config_get("activedefrag").get("activedefrag")
    assert defrag == "yes", f"Expected activedefrag=yes, got {defrag}"
```

---

## 17: Troubleshooting Guide

| Gejala Masalah (Symptom) | Akar Masalah (Root Cause) | Prosedur Diagnostik & Solusi |
|---|---|---|
| **OOM command not allowed when used memory > 'maxmemory'** | Memori Redis penuh dan Eviction Policy `noeviction` aktif, atau dataset tidak bisa dievicted. | 1. Cek policy: `CONFIG GET maxmemory-policy`<br>2. Ubah policy menjadi `allkeys-lfu` atau `volatile-lru`.<br>3. Tambahkan limit RAM. |
| **`mem_fragmentation_ratio` melonjak > 2.0** | Alokasi jemalloc menahan memori yang telah dihapus (*memory leakage / unaligned key sizes*). | 1. Verifikasi defrag: `CONFIG GET activedefrag`<br>2. Aktifkan on-the-fly: `CONFIG SET activedefrag yes`<br>3. Paksa defragmentasi via `MEMORY PURGE`. |
| **Slowlog mencatat latency spike tinggi pada background save** | Forking overhead tinggi akibat Transparent Huge Pages (THP) aktif atau `vm.overcommit_memory = 0`. | 1. Nonaktifkan THP: `echo never > /sys/kernel/mm/transparent_hugepage/enabled`<br>2. Set `sysctl vm.overcommit_memory=1`. |
| **Connection dropped / Connection reset by peer under load** | `net.core.somaxconn` OS terlalu rendah atau file descriptor jenuh. | 1. Cek `ulimit -n`<br>2. Cek `sysctl net.core.somaxconn`<br>3. Tingkatkan `somaxconn` ke `65535` dan update `redis.conf: tcp-backlog 65535`. |

---

## 18: Checklist Produksi

```
[ ] 1.  Kernel Param: vm.overcommit_memory di-set ke 1.
[ ] 2.  Kernel Param: Transparent Huge Pages (THP) dinonaktifkan secara permanen via systemd unit.
[ ] 3.  Kernel Param: net.core.somaxconn dan tcp_max_syn_backlog disesuaikan ke 65535.
[ ] 4.  Kernel Param: fs.file-max dan systemd LimitNOFILE minimal 65536.
[ ] 5.  Redis Config: maxmemory telah dispesifikasikan (75-80% dari total RAM fisik host).
[ ] 6.  Redis Config: maxmemory-policy telah ditentukan (misal: allkeys-lfu / volatile-lfu).
[ ] 7.  Redis Config: Active Defragmentation diaktifkan dan diuji.
[ ] 8.