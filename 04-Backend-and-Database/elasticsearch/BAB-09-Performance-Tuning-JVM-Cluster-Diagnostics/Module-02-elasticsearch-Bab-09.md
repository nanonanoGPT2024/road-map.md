# Kurikulum Enterprise Elasticsearch: Performance Tuning, JVM & Cluster Diagnostics

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Mengonfigurasi dan Menyetel JVM Runtime**: Mengatur ukuran heap secara presisi dengan mempertimbangkan batasan *Compressed Ordinary Object Pointers* (Compressed OOPs) serta mengalokasikan memori yang optimal untuk *OS Page Cache* (Lucene off-heap).
2. **Mengelola Kernel & Sub-sistem OS**: Mengonfigurasi parameter sistem operasi Linux (`sysctl`, `limits.conf`, `systemd`) untuk mencegah paging/swapping dan menangani konsumsi file descriptor serta *memory-mapped files* dalam skala masif.
3. **Mendiagnosis & Mengatasi Thread Pool Saturation**: Menganalisis metrik `write`, `search`, dan `management` thread pool, mendeteksi penolakan tugas (*rejections* dengan kode HTTP 429), dan memitigasi *backpressure*.
4. **Mencegah Out-of-Memory (OOM) via Circuit Breakers**: Mengelola batas *parent*, *fielddata*, dan *in-flight requests* circuit breakers untuk menjaga stabilitas node di bawah beban agregasi ekstrem.
5. **Menjalankan Investigasi Masalah Produksi**: Memanfaatkan profiling level rendah (`_nodes/hot_threads`), *Node Stats*, dan *Index/Search Slow Logs* untuk mengisolasi bottleneck CPU, memory leak, segment merging overhead, dan I/O blocking.
6. **Merancang Arsitektur Produksi Skala Multi-Petabyte**: Menerapkan arsitektur *Hot-Warm-Cold-Frozen* yang efisien, mengisolasi peran *Dedicated Master*, serta menentukan shard sizing policy guna meminimalkan overhead *Cluster State*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:
- **Arsitektur Internal Elasticsearch**: Shard, replica, index segment, dan proses translog commit.
- **Konsep JVM (Java Virtual Machine)**: Heap memory, non-heap memory, garbage collection (Generational GC, G1GC), dan thread lifecycle.
- **Administrasi Linux Tingkat Lanjut**: Virtual Memory Management (VMM), Page Cache, Swappiness, Signal Handling, dan Systemd unit overrides.
- **Jaringan & REST API**: HTTP status codes, latency profiling (p95, p99), dan protokol transport antar-node.

---

## 3. Concept & Internal Architecture

### 3.1 Dual-Memory Architecture: Heap vs. Lucene Off-Heap
Elasticsearch berjalan di atas JVM, namun memori sistem terbagi menjadi dua komponen utama:

```
+-----------------------------------------------------------------------+
|                              Total Physical RAM                       |
+-----------------------------------+-----------------------------------+
|          JVM Heap (<= 50%)        |      OS Page Cache (>= 50%)       |
|  - In-memory data structures      |  - Lucene immutable segments      |
|  - Indexing buffers               |  - Inverted index structures      |
|  - Query cache & Request cache    |  - Doc values & Term dictionaries |
|  - Cluster State & Node metadata  |  - BKD trees (Geospatial/Numeric) |
|  - Fielddata cache (if used)      |  - Stored fields                  |
+-----------------------------------+-----------------------------------+
```

- **JVM Heap**: Digunakan untuk state internal Elasticsearch, indexing buffer sementara sebelum di-flush menjadi segment, aggregation computation, transport layer framing, serta thread pool queues.
- **OS Page Cache (Lucene Off-Heap)**: Lucene mengandalkan kernel I/O cache secara langsung via memory-mapped files (`MMapDirectory`). Ketika segment telah ditulis ke disk, operasi pembacaan (seperti filtering, searching, dan sorting) tidak membaca langsung dari disk secara sinkron melainkan mengakses *Page Cache* di RAM. Jika JVM Heap mengambil terlalu banyak RAM fisik, *Page Cache* akan tereduksi, mengakibatkan *disk thrashing* dan penurunan performa drastis.

### 3.2 Compressed Ordinary Object Pointers (Compressed OOPs)
Dalam arsitektur 64-bit, penunjuk memori (*pointers*) membutuhkan 8 byte (64 bit). Namun, jika heap dibatasi di bawah ambang batas tertentu, JVM dapat menggunakan representasi 32-bit relatif terhadap basis pointer dengan melakukan *left-shift* sebesar 3 bit:

$$\text{Alamat Maksimum} = 2^{32} \times 2^3 \text{ bytes} = 4\text{ GB} \times 8 = 32\text{ GB}$$

- **Ambang Batas Nyata**: Dalam praktiknya, batas hilangnya Compressed OOPs berada di kisaran ~31 GB hingga ~31.8 GB tergantung arsitektur spesifik CPU dan JVM build.
- **Konsekuensi Pelanggaran**: Mengalokasikan heap sebesar 32.5 GB menyebabkan pointer membengkak menjadi 64 bit penuh. Akibatnya, overhead footprint pointer meningkat hingga ~40-50%, sehingga heap 33 GB sering kali memiliki kapasitas efektif *lebih kecil* daripada heap 31 GB, sembari membebani Garbage Collector secara signifikan.

### 3.3 Dynamic Circuit Breakers
Untuk mencegah JVM terhenti akibat `java.lang.OutOfMemoryError: Java heap space`, Elasticsearch mengimplementasikan lapisan *Circuit Breakers* internal yang melacak alokasi memori secara real-time sebelum mengeksekusi operasi:

- **Parent Circuit Breaker** (`indices.breaker.total.use_real_memory`): Menentukan batas absolut penggunaan memori heap gabungan (data real-time + alokasi baru). Defaultnya adalah 95% dari heap jika diset ke real memory, atau 70% jika fallback.
- **Fielddata Circuit Breaker** (`indices.breaker.fielddata.limit`): Menahan pemuatan struktur data teks agregasi tanpa perlakuan keyword ke heap. Default: 40%.
- **Request Circuit Breaker** (`indices.breaker.request.limit`): Menghitung batas memori untuk operasi query level node seperti agregasi bersarang (*nested aggregations*). Default: 60%.
- **In-Flight Requests Circuit Breaker** (`network.breaker.inflight_requests.limit`): Membatasi request transport/HTTP yang sedang aktif diproses. Default: 100%.

Jika estimasi alokasi request menyebabkan utilisasi melampaui batas ini, Elasticsearch langsung melempar exception `CircuitBreakingException` dan menolak request tersebut, menjaga node tetap hidup (*fail-fast*).

### 3.4 Thread Pools, Queues, and Rejection Mechanisms
Elasticsearch menggunakan model konkurensi berbasis thread pool terpisah untuk setiap kategori pekerjaan:

```
Request Inbound (HTTP/Transport)
                │
                ▼
     ┌───────────────────────┐
     │ Coordinating Node     │
     └──────────┬────────────┘
                │ Dispatched to target shard
                ▼
     ┌────────────────────────────────────────────────────────┐
     │ Data Node Thread Pool (e.g., 'write' or 'search')     │
     │                                                        │
     │ Active Threads (Fixed: Cores or Cores * 1.5)           │
     │   [T1] [T2] [T3] [T4] ... [Tn]                         │
     │     │    │    │    │                                   │
     │     ▼    ▼    ▼    ▼                                   │
     │ ┌──────────────────────────────────────────────────┐   │
     │ │ Internal Queue (Fixed capacity, e.g., 1000/10000)│   │
     │ │ [Req][Req][Req][Req]...                          │   │
     │ └──────────────────────────────────────────────────┘   │
     └──────────────────────────┬─────────────────────────────┘
                                │ Queue Full?
                                ├───────────────┐
                                │ YES           │ NO
                                ▼               ▼
                      HTTP 429 Rejected    Task Processed
                      (EsRejectedExecutionException)
```

- **Write Pool**: Thread pool berukuran tetap (`allocated_processors`). Digunakan untuk index, update, dan delete. Memiliki antrean default sebesar 10.000 task.
- **Search Pool**: Thread pool berukuran tetap (`(allocated_processors * 3) / 2 + 1`). Digunakan untuk query read dan scoring. Memiliki antrean default 1.000 task.
- **Mekanisme Rejection**: Jika antrean penuh, Elasticsearch menolak task baru dengan error `EsRejectedExecutionException` (HTTP status 429 - Too Many Requests). Menambah kapasitas antrean tanpa batasan bukan solusi yang tepat, karena antrean yang membengkak menahan objek di dalam heap, memicu GC pause yang panjang, dan memperparah latensi.

---

## 4. Why & What

### Mengapa Konfigurasi Standar Menjadi Kendala di Skala Enterprise?
1. **JVM Default Sizing**: Secara default, Elasticsearch mengalokasikan heap secara dinamis berdasarkan total RAM (sering kali 25% atau 50% hingga batas aman default 4 GB/8 GB). Di server enterprise dengan RAM 128 GB - 256 GB, konfigurasi default tidak memanfaatkan hardware secara optimal atau justru membuat alokasi heap terlalu besar (> 32 GB) jika diset manual secara keliru.
2. **Linux Swapping Hazards**: OS Linux cenderung memindahkan halaman memori yang jarang diakses ke swap space. Jika heap memory Elasticsearch terlempar ke swap disk, operasi GC yang melakukan traversal pointer akan mengalami page faults masif, mengubah GC pause milidetik menjadi *node unresponsiveness* berdurasi puluhan detik. Akibatnya, master node menganggap data node tersebut mati (*false node drop*).
3. **Lucene File Descriptors Exhaustion**: Lucene membagi index menjadi puluhan hingga ratusan ribu segment file. Tanpa penyesuaian limit kernel, sistem operasi akan menolak pembukaan file baru melalui `Too many open files`.

### Apa yang Harus Dilakukan?
Terapkan arsitektur deterministik:
- Alokasikan heap $\le 31\text{ GB}$ (pastikan Compressed OOPs tetap aktif).
- Matikan swapping secara permanen dan aktifkan memory locking (`mlockall`).
- Pastikan rasio alokasi $50\%$ Heap dan $50\%$ OS Cache.
- Naikkan batas *memory-mapped files* (`vm.max_map_count`) agar Lucene dapat memetakan ribuan segment secara langsung ke kernel space.

---

## 5. How (Workflow Detail)

### 5.1 Alur Diagnostik Insiden Performa Klaster

```
                    +------------------------------------+
                    | Insiden: Node Slow / HTTP 429 / GC |
                    +-----------------+------------------+
                                      |
                                      v
                    +------------------------------------+
                    | 1. Evaluasi Status Cluster Health  |
                    |    GET /_cluster/health            |
                    +-----------------+------------------+
                                      |
         +----------------------------+---------------------------+
         | Status: RED (Unassigned)                               | Status: YELLOW / GREEN (High Latency)
         v                                                        v
+------------------------------------+                  +------------------------------------+
| 2. Periksa Masalah Shard           |                  | 2. Periksa Thread Pool Rejections  |
| GET /_cluster/allocation/explain   |                  | GET /_cat/thread_pool?v&h=...      |
+------------------------------------+                  +-----------------+------------------+
                                                                          |
                                      +-----------------------------------+-----------------------------------+
                                      | Ada Rejections (Write/Search)                                     | Zero Rejections
                                      v                                                                   v
                    +------------------------------------+                              +------------------------------------+
                    | 3. Analisis Profil Hot Threads     |                              | 3. Analisis Garbage Collection &   |
                    | GET /_nodes/hot_threads            |                              |    Saturasi Memory/IO              |
                    +-----------------+------------------+                              | GET /_nodes/stats/jvm,os,fs        |
                                      |                                                 +-----------------+------------------+
              +-----------------------+-----------------------+                                           |
              | CPU Tinggi di Lucene                          | CPU Tinggi di Segment Merge               v
              v                                               v                         +------------------------------------+
+------------------------------------+         +------------------------------------+   | 4. Deteksi GC Stop-The-World       |
| 4. Analisis Search Slowlog         |         | 4. Throttle Max Merges atau atur   |   |    Tinjau JVM Logs & Circuit       |
|    Optimasi Query & Caching        |         |    Refresh Interval                |   |    Breaker Metrics                 |
+------------------------------------+         +------------------------------------+   +------------------------------------+
```

---

## 6. Analogy & Diagram ASCII

### Analogi Perpustakaan: Heap vs. Kernel Page Cache
Bayangkan node Elasticsearch sebagai sebuah perpustakaan riset:
- **JVM Heap (Meja Kerja Peneliti)**: Ukurannya terbatas. Di atas meja ini peneliti menaruh kertas coretan kalkulasi data (*aggregations*), daftar urutan peminjaman (*in-flight tasks*), dan buku referensi utama (*cluster state*). Jika meja ini dipenuhi tumpukan buku, peneliti kehilangan ruang gerak dan terpaksa membuang waktu menyingkirkan kertas (ini analogi dengan **Garbage Collection**).
- **Page Cache / Lucene Off-Heap (Rak Buku Terbuka)**: Buku-buku disusun rapi di rak menggunakan katalog indeks (Lucene Segments). Peneliti tidak perlu memindahkan seluruh isi buku ke atas mejanya; ia hanya berjalan ke rak, membaca paragraf yang dibutuhkan, dan langsung mencatat hasilnya. Jika ukuran meja diperbesar secara berlebihan hingga menghabiskan ruang rak buku, kapasitas penyimpanan buku di perpustakaan akan berkurang drastis. Akibatnya, pengunjung terpaksa bolak-balik mengambil buku dari gudang luar (Disk I/O), yang prosesnya jauh lebih lambat.

```
                          SERVER FISIK (RAM 64 GB)
┌────────────────────────────────────────────────────────────────────────────┐
│ JVM HEAP: 30 GB (Meja Kerja)         │ OS PAGE CACHE: 34 GB (Rak Buku)     │
│ [Compressed OOPs Aktif: Shift 3-bit] │ [Akses MMapDirectory Direct Kernel] │
│                                      │                                     │
│ ┌──────────────┐ ┌─────────────────┐ │ ┌──────────────┐ ┌────────────────┐ │
│ │ Query Buffer │ │ Aggregation Map │ │ │ Segment #1   │ │ Segment #2     │ │
│ └──────────────┘ └─────────────────┘ │ └──────────────┘ └────────────────┘ │
│ ┌──────────────┐ ┌─────────────────┐ │ ┌──────────────┐ ┌────────────────┐ │
│ │ Ingest Queue │ │ Request Cache   │ │ │ Doc Values   │ │ BKD Trees      │ │
│ └──────────────┘ └─────────────────┘ │ └──────────────┘ └────────────────┘ │
└──────────────────────────────────────┴─────────────────────────────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Konfigurasi Kernel Sistem Operasi Tingkat Rendah
Buka dan tambahkan parameter berikut pada `/etc/sysctl.d/99-elasticsearch.conf`:

```ini
# Menjamin Lucene dapat memetakan ribuan shard segment secara langsung
vm.max_map_count = 262144

# Mematikan swapping agresif tanpa menonaktifkan kernel swap memory management
vm.swappiness = 1

# Mencegah komitmen alokasi memori berlebih yang dapat memicu kernel OOM-killer
vm.overcommit_memory = 1

# Meningkatkan throughput jaringan untuk transfer segment antar node
net.core.somaxconn = 4096
net.ipv4.tcp_max_syn_backlog = 4096
```

Terapkan limitasi user pada `/etc/security/limits.d/99-elasticsearch.conf`:

```text
elasticsearch   soft   nofile    65535
elasticsearch   hard   nofile    65535
elasticsearch   soft   nproc     4096
elasticsearch   hard   nproc     4096
elasticsearch   soft   memlock   unlimited
elasticsearch   hard   memlock   unlimited
```

Konfigurasi Systemd Unit Override untuk memastikan `LimitMEMLOCK` dihormati (`systemctl edit elasticsearch`):

```ini
[Service]
LimitMEMLOCK=infinity
LimitNOFILE=65535
LimitNPROC=4096
```

### 7.2 Konfigurasi JVM (`jvm.options`)
Konfigurasi file `/etc/elasticsearch/jvm.options.d/heap.options` untuk server dengan RAM fisik 64 GB:

```text
# Pastikan nilai Xms dan Xmx identik guna mencegah alokasi ulang heap saat runtime
-Xms31g
-Xmx31g

# Gunakan Garbage First Garbage Collector (G1GC) untuk latensi yang lebih stabil
-XX:+UseG1GC
-XX:InitiatingHeapOccupancyPercent=45
-XX:G1ReservePercent=15
-XX:MaxGCPauseMillis=200

# Dumping memory saat OOM yang tidak dapat dihindari untuk post-mortem analysis
-XX:+HeapDumpOnOutOfMemoryError
-XX:HeapDumpPath=/var/log/elasticsearch/oom-dump.hprof

# Log detail garbage collection untuk keperluan profiling
-Xlog:gc*,gc+phases=debug:file=/var/log/elasticsearch/gc.log:time,uptime,pid:filecount=5,filesize=64m
```

### 7.3 Konfigurasi Node Elasticsearch (`elasticsearch.yml`)
Setelan produksi untuk node jenis *Hot Data Tier*:

```yaml
cluster.name: production-finance-data
node.name: node-hot-data-01
node.roles: [ data_hot, ingest ]

# Kunci heap memory di RAM fisik, mencegah penggunaan swap space
bootstrap.memory_lock: true

# Path data dan logs (Gunakan dedicated NVMe mount)
path.data: /mnt/nvme-pool/elasticsearch/data
path.logs: /var/log/elasticsearch

# Alokasi thread processors secara eksplisit jika berjalan di virtual machine/container
processors: 16

# Circuit Breakers Tuning
indices.breaker.total.use_real_memory: true
indices.breaker.total.limit: 95%
indices.breaker.fielddata.limit: 30%
indices.breaker.request.limit: 40%

# Network Settings
network.host: 10.200.10.15
http.port: 9200
transport.port: 9300
```

### 7.4 Skrip Diagnostik Otomatis (Bash)
Simpan sebagai `cluster_triage.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ES_ENDPOINT="http://localhost:9200"

echo "=== 1. CHECKING COMPRESSED OOPS STATUS ==="
curl -s "${ES_ENDPOINT}/_nodes/jvm?pretty" | grep -A 5 -B 2 "using_compressed_ordinary_object_pointers"

echo -e "\n=== 2. THREAD POOL QUEUES AND REJECTIONS ==="
curl -s "${ES_ENDPOINT}/_cat/thread_pool/write,search,generic?v&h=node_name,name,active,queue,rejected,completed"

echo -e "\n=== 3. CIRCUIT BREAKER UTILIZATION ==="
curl -s "${ES_ENDPOINT}/_nodes/stats/breaker?pretty" | jq '.nodes[] | {name: .name, breakers: .breakers}'

echo -e "\n=== 4. CAPTURING HOT THREADS (TOP 3 WORST) ==="
curl -s "${ES_ENDPOINT}/_nodes/hot_threads?threads=3&type=cpu"
```

---

## 8. Real World Case Study

### Kasus: Meltdown Klaster E-Commerce Global Saat Flash Sale
- **Skala Klaster**: 45 Data Nodes (masing-masing 32 Core vCPU, 128 GB RAM, Array NVMe SSD), 3 Dedicated Master Nodes, 4 Coordinating Nodes.
- **Gejala**: Saat event Flash Sale dimulai (traffic naik dari 15.000 req/sec menjadi 120.000 req/sec), klaster mengalami cascading failure:
  1. API Gateway mencatat error rate HTTP 429 (`EsRejectedExecutionException`) melonjak tajam hingga 78%.
  2. Latensi Search melonjak dari p95 45ms ke 18 detik.
  3. Tiga data node terputus dari klaster (*node disconnected*), disusul oleh proses *Master Node Election Flapping*.

### Investigasi Mendalam (Root Cause Analysis):
1. **Analisis JVM**: Tim operasional mengalokasikan `-Xms64g -Xmx64g` dengan asumsi "semakin besar memori, semakin cepat prosesnya". Akibatnya, JVM menonaktifkan *Compressed OOPs*, dan ukuran pointer membengkak menjadi 64-bit.
2. **Kondisi Page Cache Tertekan**: Karena heap memakan 64 GB dan JVM overhead memakai ~8 GB, sisa memori untuk Lucene Page Cache pada node berkapasitas 128 GB hanya tersisa ~56 GB. Lucene terpaksa membaca berkas segment dari disk secara intensif melalui NVMe read calls.
3. **Analisis Agregasi**: Query catalog frontend menggunakan teknik *Wildcard Search* dan *Heavy Multi-Bucket Aggregation* tanpa filter routing. Operasi ini mengeksploitasi memory heap data node secara agresif.
4. **Tragedi GC & Master Timeout**: Heap terisi jutaan temporary bucket objects. G1GC mencoba melakukan sweeping, memicu *Concurrent Mark-Sweep* yang gagal dan jatuh ke mode *Stop-The-World Full GC* selama **38 detik**. Heartbeat Transport antar-node (`cluster.follower_lag.timeout`, default 30s) terputus, sehingga master node menyatakan ketiga data node tersebut mati dan memulai proses alokasi ulang shard (*rebalancing*). Proses rebalancing ini membebani bandwidth jaringan antar-node, memicu lonjakan Full GC pada node-node lainnya (cascading failure).

### Solusi & Implementasi Perbaikan:
1. **Penurunan Alokasi Heap**: Heap diubah menjadi `-Xms31g -Xmx31g` untuk mengaktifkan kembali 32-bit *Compressed OOPs*. Sisa 97 GB RAM fisik dialokasikan penuh untuk kernel *OS Page Cache*.
2. **G1GC Tuning**:
   ```text
   -XX:InitiatingHeapOccupancyPercent=40
   -XX:G1ReservePercent=15
   -XX:InitiatingHeapOccupancyPercent=45
   -XX:G1MixedGCCountTarget=8
   ```
3. **Penyesuaian Transport Heartbeat**: Mencegah false drop akibat GC pause ringan:
   ```yaml
   transport.tcp.keep_alive: true
   cluster.follower_lag.timeout: 90s
   ```
4. **Isolasi Beban Koordinasi**: Memaksa API Gateway mengarahkan seluruh query masuk hanya ke 4 Dedicated Coordinating Nodes, sehingga node data terhindar dari beban agregasi respon HTTP raksasa.
5. **Slow Log & Query Guardrail**: Mengaktifkan search slow log dengan threshold 200ms dan menonaktifkan pencarian teks berbasis leading wildcard (`*term`).

**Hasil**: Latensi search p99 stabil kembali di 32ms pada beban 140.000 req/sec, penggunaan heap turun stabil di bawah 65%, dan zero rejections (HTTP 429 hilang sepenuhnya).

---

## 9. Trade-offs

| Parameter Desain | Opsi A | Opsi B | Trade-off Implication |
|---|---|---|---|
| **JVM Heap Sizing** | Heap Maksimal (64 GB) | Heap Kompak (31 GB, Compressed OOPs) | Opsi A memperbesar ruang temporary objects query, tetapi mematikan Compressed OOPs, meningkatkan GC pause, dan mengorbankan Lucene Page Cache. Opsi B memberikan efisiensi pointer dan read-caching lebih baik. |
| **Search Queue Size** | Queue Besar (10.000) | Queue Kecil Default (1.000) | Queue besar mencegah HTTP 429 sementara saat spike, namun mengonsumsi heap secara agresif. Jika backlog antrean menumpuk, latency request yang tertahan akan tetap melampaui timeout client, berisiko memicu OOM cascade. |
| **Refresh Interval** | Real-time (`1s`) | Batched Ingest (`30s` - `60s`) | Refresh interval 1s memungkinkan data langsung terbaca setelah ditulis, namun menciptakan ribuan segment kecil yang membebani IOPS disk (proses merge konstan) dan memicu CPU throttling. Interval 30s-60s meningkatkan write-throughput hingga 4x lipat. |
| **Shard Sizing** | Banyak Shard Kecil (< 10 GB) | Shard Skala Optimal (30 GB - 50 GB) | Shard kecil mempercepat pemulihan shard tunggal, tetapi membebani Master Node Cluster State dan overhead memori heap pada segment catalog. Shard optimal menjaga klaster tetap stabil pada skala petabyte. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Konfigurasi Kritis dan Solusinya

#### 1. Kesalahan Alokasi Heap 32 GB
- **Gejala**: Penggunaan heap melonjak tidak wajar dan throughput turun 30%.
- **Penyebab**: Menyetel heap tepat di angka `32g`. JVM menonaktifkan fitur Compressed OOPs.
- **Pemeriksaan**:
  ```bash
  curl -s "localhost:9200/_nodes/jvm?pretty" | jq '.. | .using_compressed_ordinary_object_pointers? // empty'
  ```
- **Solusi**: Turunkan nilai menjadi `31g` (atau evaluasi output JVM flag `-XX:+PrintFlagsFinal -version | grep UseCompressedOops`).

#### 2. Swap Space Masih Aktif
- **Gejala**: Node tiba-tiba freeze, lag inter-node melonjak acak, IOPS disk melonjak tinggi padahal traffic penulisan data normal.
- **Penyebab**: Memori heap dipindahkan ke disk virtual swap oleh kernel Linux.
- **Solusi**:
  ```bash
  sudo swapoff -a
  ```
  Hapus entri swap pada `/etc/fstab` dan aktifkan parameter Elasticsearch:
  ```yaml
  bootstrap.memory_lock: true
  ```
  Pastikan verifikasi berhasil melalui API:
  ```bash
  curl -s "localhost:9200/_nodes/process?pretty" | jq '.nodes[].process.mlockall'
  # Output HARUS bernilai 'true'
  ```

#### 3. Fielddata Memory Leak pada Agregasi Teks
- **Gejala**: Cluster breaker melemparkan `CircuitBreakingException: [parent] Data too large...`.
- **Penyebab**: Menjalankan query agregasi langsung pada field bertipe `text` tanpa `keyword` mapping sub-field. Elasticsearch memuat data string mentah ke heap memori (*Fielddata*).
- **Pemeriksaan**:
  ```bash
  curl -s "localhost:9200/_cat/indices?v&h=index,fielddata.memory_size"
  ```
- **Solusi**: Bersihkan cache fielddata yang aktif:
  ```bash
  curl -X POST "localhost:9200/_cache/clear?fielddata=true"
  ```
  Ubah mapping field target agar menggunakan sub-field `keyword` (`"field.keyword"`).

#### 4. Menafsirkan CPU Bottleneck Menggunakan Hot Threads API
Ketika sebuah node mengalami utilisasi CPU hingga 100%, jalankan pemeriksaan berikut:
```bash
curl -s "localhost:9200/_nodes/hot_threads?type=cpu&threads=5"
```
**Cara Membaca Output Diagnostik**:
- Jika terlihat stack trace: `org.apache.lucene.index.ConcurrentMergeScheduler`:
  Node terbebani oleh proses kompresi/merging segment berkas di disk. Hal ini lumrah terjadi selama ingestion data berskala masif. Mitigasi: Ubah refresh interval menjadi lebih jarang atau atur merge throttling.
- Jika terlihat stack trace: `org.elasticsearch.search.aggregations...`:
  Query dari pengguna terlalu boros komputasi CPU. Temukan IP pengirim melalui search slowlog dan terapkan query optimization.

---

## 11. Best Practices (Production Checklist)

### Checklist Sebelum Deployment Skala Produksi

- [ ] **Sistem Operasi**:
  - [ ] Nonaktifkan swap permanen (`swapoff -a` dan komentari entri swap di `/etc/fstab`).
  - [ ] Set `vm.max_map_count` minimal `262144`.
  - [ ] Set `LimitNOFILE` minimal `65535` pada systemd service configuration.
  - [ ] Filesystem diformat menggunakan `XFS` atau `ext4` dengan opsi mount `noatime`.
- [ ] **JVM**:
  - [ ] Set ukuran `-Xms` persis sama dengan `-Xmx`.
  - [ ] Ukuran heap maksimum $\le 31\text{ GB}$ (Validasi status `using_compressed_ordinary_object_pointers == true`).
  - [ ] Sisakan minimal 50% dari total RAM fisik server untuk alokasi *OS Page Cache*.
  - [ ] Konfigurasi path dump direktori jika terjadi insiden *OutOfMemoryError*.
- [ ] **Konfigurasi Node & Cluster**:
  - [ ] Set `bootstrap.memory_lock: true`.
  - [ ] Tentukan peran node (*roles*) secara terisolasi untuk klaster besar: Dedicated Master (`master`), Dedicated Ingest (`ingest`), Dedicated Coordinating (`[]`), dan Data Nodes (`data_hot`, `data_warm`, dll.).
  - [ ] Tetapkan shard target berukuran antara 20 GB sampai maksimal 50 GB per shard.
  - [ ] Batasi total shard aktif pada data node di kisaran 20 shard per 1 GB alokasi Heap (Contoh: Max 600 shard untuk node dengan heap 30 GB).
- [ ] **Logging & Observability**:
  - [ ] Aktifkan `index.search.slowlog` (warn: 2s, info: 800ms).
  - [ ] Aktifkan `index.indexing.slowlog` (warn: 1s, info: 500ms).
  - [ ] Ekspor metrik Node Stats secara berkala ke external TSDB (Prometheus / Elastic Agent).

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan menyiapkan lingkungan simulasi data-node, menguji batas konfigurasi JVM, memicu circuit breaker, dan menganalisis utilisasi memori serta thread saturation.

### Persiapan Direktori Kerja
```bash
mkdir -p hands-on/m02/config hands-on/m02/scripts
cd hands-on/m02
```

### Langkah 1: Siapkan `docker-compose.yml`
Kita menggunakan container Docker dengan alokasi resource terbatas untuk mereplikasi skenario lingkungan server produksi:

```yaml
version: '3.8'

services:
  es-perf-node:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: es-perf-node
    environment:
      - node.name=perf-data-node
      - cluster.name=perf-tuning-lab
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g -XX:+UseG1GC"
      - indices.breaker.total.use_real_memory=true
      - indices.breaker.total.limit=70%
      - indices.breaker.request.limit=20%
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    ports:
      - "9200:9200"
      - "9600:9600"
    deploy:
      resources:
        limits:
          memory: 2G
```

Jalankan container:
```bash
docker compose up -d
```

### Langkah 2: Verifikasi Alokasi Heap dan Status Compressed OOPs
Jalankan skrip berikut di host machine:

```bash
curl -s "http://localhost:9200/_nodes/jvm?pretty" | jq '{
  heap_init: .nodes[].jvm.mem.heap_init,
  heap_max: .nodes[].jvm.mem.heap_max,
  using_compressed_oops: .nodes[].jvm.using_compressed_ordinary_object_pointers
}'
```
*Pastikan output parameter `using_compressed_oops` bernilai `true`.*

### Langkah 3: Injeksi Skema dan Data Uji Beban
Buat index dengan pemetaan teks tanpa optimasi keyword (untuk memicu kebutuhan alokasi heap tinggi saat agregasi):

```bash
curl -X PUT "http://localhost:9200/telemetry-logs" -H 'Content-Type: application/json' -d'
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "index.search.slowlog.threshold.query.warn": "100ms",
    "index.search.slowlog.threshold.fetch.warn": "50ms"
  },
  "mappings": {
    "properties": {
      "raw_payload": { "type": "text", "fielddata": true },
      "metric_value": { "type": "double" },
      "timestamp": { "type": "date" }
    }
  }
}'
```

Jalankan skrip pengisian data sederhana menggunakan Bash:

```bash
cat << 'EOF' > scripts/ingest_data.sh
#!/usr/bin/env bash
for i in {1..2000}; do
  PAYLOAD="UUID-$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1) log entry line data stream validation text"
  METRIC=$((RANDOM % 100000))
  echo "{\"index\":{\"_index\":\"telemetry-logs\"}}"
  echo "{\"raw_payload\":\"$PAYLOAD\",\"metric_value\":$METRIC,\"timestamp\":\"2023-10-25T10:00:00Z\"}"
done | curl -s -X POST "http://localhost:9200/telemetry-logs/_bulk" -H "Content-Type: application/x-ndjson" --data-binary @- > /dev/null
echo "Ingestion bulk completed."
EOF

chmod +x scripts/ingest_data.sh
./scripts/ingest_data.sh
```

### Langkah 4: Uji Coba Pemicuan Circuit Breaker (Stress Memori Heap)
Jalankan agregasi kompleks berkedalaman tinggi (*high cardinality bucket terms*) untuk memaksa alokasi memori melebihi batas request circuit breaker (20% dari 1 GB heap):

```bash
curl -X POST "http://localhost:9200/telemetry-logs/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "size": 0,
  "aggs": {
    "exploding_buckets": {
      "terms": {
        "field": "raw_payload",
        "size": 100000
      }
    }
  }
}'
```
*Amati respon JSON yang dikembalikan oleh Elasticsearch. Klaster akan melempar pesan kesalahan HTTP 429 atau 500 dengan payload `CircuitBreakingException`.*

### Langkah 5: Inspeksi Diagnostik Real-Time
1. Amati breaker status:
   ```bash
   curl -s "http://localhost:9200/_nodes/stats/breaker?pretty" | jq '.nodes[].breakers.request'
   ```
2. Analisis performa eksekusi query pada search slow log di dalam container:
   ```bash
   docker exec -it es-perf-node tail -n 20 /usr/share/elasticsearch/logs/perf-tuning-lab_index_search_slowlog.json
   ```
3. Pantau jejak thread pemrosesan CPU:
   ```bash
   curl -s "http://localhost:9200/_nodes/hot_threads"
   ```

---

## 13. Exercise

### Level Easy
1. Jalankan kueri untuk memeriksa status parameter `bootstrap.memory_lock` di semua node yang terhubung pada klaster lokal Anda.
2. Gunakan `_cat/thread_pool` API untuk menampilkan metrik `active`, `queue`, dan `rejected` khusus untuk kelompok thread pool `write`.

### Level Medium
1. Konfigurasikan search slow log dinamis pada index `telemetry-logs` via Index Settings API agar merekam seluruh query yang membutuhkan durasi eksekusi lebih dari `50ms` ke level `INFO`.
2. Lakukan simulasi thread pool rejection: Tulis script generator paralel menggunakan tool benchmarking (misal: Apache Bench atau curl loop di background) yang menembakkan bulk insert ke index tunggal hingga counter `rejected` pada `_cat/thread_pool/write` bertambah $> 0$.

### Level Hard
1. Buat skrip simulasi pemulihan sistem ketika utilisasi Parent Breaker mencapai 95%:
   - Lakukan monitoring berkala setiap 5 detik terhadap endpoint `_nodes/stats/breaker`.
   - Jika `parent.tripped` $> 0$, picu pembersihan segment cache serta fielddata cache (`_cache/clear?fielddata=true`).
   - Turunkan alokasi batch size client ingestion secara dinamis (*backoff algorithm*) sampai utilisasi heap normal kembali di bawah 70%.

---

## 14. Challenge

### Studi Kasus: Diagnostik Degradasi Klaster FinTech Multi-Tenant
**Skenario**:
Anda ditunjuk sebagai Principal Infrastructure Architect di bank digital berskala regional. Klaster Elasticsearch audit log Anda memiliki footprint penyimpanan sebesar 1.2 Petabyte yang tersebar di 60 Node Data Tier. Klaster ini melayani ingest data transaksi keuangan secara realtime sekaligus query dashboard anti-fraud.

Setiap hari Senin pukul 09:00 WIB:
1. Master node klaster mulai mengalami keterlambatan merespons transport ping (`node-left` disusul `node-rejoined`).
2. Tim Anti-Fraud melaporkan dashboard Kibana mereka menampilkan pesan error `Gateway Timeout (504)` atau `503 Service Unavailable`.
3. Metrik CPU menunjukkan beberapa node data mengalami idle rendah (utilisasi 15%), namun load average sistem operasi tercatat sangat tinggi (mencapai `load average > 80` pada host 32 core).
4. Volume ingestion rate drop signifikan, dan sistem backpressure Kafka menahan antrean jutaan transaksi pending.

**Tugas Anda**:
Rancang dokumen arsitektur dan penanganan insiden (*Architecture Analysis & Mitigation Strategy*) yang merinci:
- **Analisis Akar Masalah**: Mengapa IO wait dapat menyebabkan master node terlepas dari klaster padahal utilisasi CPU tercatat rendah?
- **Perbaikan Arsitektur**: Bagaimana memisahkan jalur agregasi query tim Anti-Fraud dari jalur penulisan data transaksi berthroughput tinggi?
- **Desain Partisi Data**: Bagaimana skema Index Lifecycle Management (ILM) dan perancangan alokasi ukuran shard per node agar segment merge tidak memicu starvation pada disk subsystem?
- **Penyusunan Rencana Solusi**: Sediakan arsitektur topologi node final lengkap dengan penugasan node roles, JVM tuning values, dan setting kernel OS yang terstandardisasi.

*(Selesaikan analisis ini secara terstruktur dengan pendekatan mitigasi teknis level-kernel dan level-engine tanpa menggunakan perbaikan instan seperti sekadar melakukan restart berkala pada node).*

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Berapakah batas maksimum alokasi JVM Heap yang direkomendasikan agar fitur Compressed Ordinary Object Pointers (Compressed OOPs) tetap aktif di Elasticsearch?
   - A. 16 GB
   - B. Tepat 32 GB
   - C. Di bawah ~31 GB (umumnya disetel pada 30-31 GB)
   - D. 64 GB

2. Apa peran utama kernel OS Page Cache pada node Elasticsearch?
   - A. Menyimpan temporary query aggregation buffer.
   - B. Memetakan berkas segment Lucene secara efisien ke RAM fisik tanpa overhead JVM garbage collection.
   - C. Menggantikan peran write translog di media penyimpanan permanen.
   - D. Menyimpan log historis aplikasi Elasticsearch.

3. Apa status respons HTTP yang dikembalikan oleh Elasticsearch ketika request worker queue pada thread pool target telah penuh?
   - A. 500 Internal Server Error
   - B. 503 Service Unavailable
   - C. 408 Request Timeout
   - D. 429 Too Many Requests (`EsRejectedExecutionException`)

4. Parameter Linux kernel manakah yang wajib dinaikkan nilainya agar instance Elasticsearch terhindar dari error crash saat membaca file segment Lucene dalam jumlah besar?
   - A. `vm.swappiness`
   - B. `vm.max_map_count`
   - C. `net.ipv4.ip_forward`
   - D. `fs.epoll.max_user_watches`

5. Opsi konfigurasi manakah di `elasticsearch.yml` yang berfungsi mengunci alokasi memori Elasticsearch di RAM fisik agar tidak dipindahkan ke swap space?
   - A. `indices.memory.lock: true`
   - B. `bootstrap.memory_lock: true`
   - C. `node.lock_memory_allocation: true`
   - D. `system.swap.disabled: true`

---

### Bagian 2: Intermediate (Pilihan Ganda)
6. Manakah dari pernyataan berikut yang paling tepat mendeskripsikan Parent Circuit Breaker dengan pengaturan `indices.breaker.total.use_real_memory: true`?
   - A. Hanya membatasi konsumsi memori saat proses index mapping berlangsung.
   - B. Mengukur estimasi alokasi memori heap murni berdasarkan byte transaksi di memory buffer indexing.
   - C. Mengukur penggunaan total heap secara aktual/real-time dan membatalkan request baru jika batas utilisasi heap terlampaui.
   - D. Secara otomatis menghapus data shard terlama saat kapasitas RAM server menipis.

7. Jika hasil pembacaan profiling dari API `_nodes/hot_threads` didominasi oleh fungsi `org.apache.lucene.index.ConcurrentMergeScheduler`, hal ini mengindikasikan bahwa node sedang mengalami:
   - A. Kebocoran alokasi heap memori (*heap memory leak*).
   - B. Beban komputasi I/O dan CPU tinggi akibat proses penggabungan (*merging*) segment Lucene di background.
   - C. Serangan distributed denial of service pada transport API.
   - D. Kebuntuan alokasi thread (*deadlock*) pada subsistem networking.

8. Mengapa nilai parameter konfigurasi JVM `-Xms` dan `-Xmx` HARUS selalu dikonfigurasikan dengan besaran nilai yang sama pada server produksi?
   - A. Agar Garbage Collector tidak perlu membuang resource komputasi untuk meresize ukuran heap saat runtime.
   - B. Untuk memastikan alokasi Compressed OOPs otomatis dimatikan oleh kernel.
   - C. Karena modul Lucene membatasi alokasi heap hanya pada saat server pertama kali di-boot.
   - D. Agar Elasticsearch dapat memanfaatkan swap space secara elastis saat heap penuh.

9. Apa dampak langsung dari konfigurasi shard berukuran sangat kecil (contoh: 500MB per shard) dengan kuantitas ribuan shard pada sebuah cluster?
   - A. Kecepatan baca dan tulis meningkat secara linier seiring pertambahan shard.
   - B. Utilisasi memori heap membengkak drastis akibat metadata segment di cluster state, memicu tingginya beban sinkronisasi pada Master Node.
   - C. Garbage collection menjadi lebih jarang berjalan karena segment data berukuran kecil.
   - D. Fitur circuit breaker dinonaktifkan secara otomatis oleh cluster engine.

10. Kapan mekanisme Garbage Collection tipe G1GC berpotensi beralih (*fallback*) menjadi Stop-the-World Full GC yang membekukan respon Elasticsearch selama puluhan detik?
    - A. Saat laju alokasi objek temporary heap berjalan jauh lebih cepat daripada kemampuan G1GC concurrent phase menandai dan membersihkan memory region (*Allocation Rate Failure*).
    - B. Ketika OS Page Cache mencapai utilisasi di atas 50% dari total RAM fisik.
    - C. Setiap kali translog di-flush secara periodik ke disk oleh Elasticsearch engine.
    - D. Tepat saat parameter `bootstrap.memory_lock` diatur ke nilai `false`.

---

### Bagian 3: Skenario Kasus Produksi

#### Skenario 1: Diagnostik Degradasi Node Pasca Peningkatan Kapasitas Server
Sebuah tim data melakukan migrasi cluster dari mesin virtual lama (RAM 32 GB) ke bare-metal server baru (RAM 256 GB). Di server baru, teknisi menyetel konfigurasi `-Xms128g -Xmx128g` dengan tujuan memberikan resource seluas mungkin bagi agregasi Elasticsearch. Segera setelah traffic produksi dialihkan:
- Latensi query agregasi tercatat meningkat dua kali lipat lebih lambat.
- Node secara berkala mengalami jeda respons (*freeze*) selama 10 hingga 25 detik secara acak.
- Kapasitas disk I/O reads tercatat naik signifikan pada dashboard hardware.

**Pertanyaan Analisis**:
Jelaskan rantai kausalitas kegagalan arsitektur di atas berdasarkan interaksi antara Compressed OOPs, alokasi Lucene Page Cache, dan Garbage Collector! Langkah koreksi apa yang harus segera diterapkan pada konfigurasi JVM server tersebut?

#### Skenario 2: Analisis HTTP 429 Write Rejections Saat Event Peak
Dashboard metrik sistem monitoring mencatat lonjakan tajam penolakan request data indexing dengan respons HTTP 429 pada peak traffic harian. Tim pengembang menyarankan solusi instan dengan mengubah parameter konfigurasi klaster berikut:
```yaml
thread_pool.write.queue_size: 100000
```
(Dinaikkan dari batas default 10.000 menjadi 100.000 task).

**Pertanyaan Analisis**:
Sebagai Tech Lead, apakah Anda menyetujui perubahan tersebut? Jelaskan risiko fatal apa yang mengancam kestabilan heap Elasticsearch jika queue size diperbesar hingga 10x lipat di bawah kondisi traffic penulisan data yang saturasi! Solusi arsitektural apa yang semestinya diimplementasikan di sisi upstream?

#### Skenario 3: Penyelamatan Klaster Mengalami OutOfMemory Circuit Breaking Cascade
Sebuah klaster mengalami incident berantai: Salah satu data node utama terus menerus melempar exception `CircuitBreakingException: [parent] Data too large, data for [<transport_request>] would be [998244352/952mb], which is larger than the limit of [943718400/900mb]`. 
Akibat error ini, client application melakukan retry pengiriman query secara berulang tanpa backoff delay, yang segera merembet ke dua data node lainnya hingga seluruh data node klaster menolak eksekusi search request.

**Pertanyaan Analisis**:
Uraikan langkah-langkah mitigasi darurat (*emergency triage runbook*) yang harus diambil oleh DevOps on-call engineer untuk menghentikan cascade failure tersebut dan menstabilkan cluster tanpa menyebabkan data loss!

---

### Kunci Jawaban & Panduan Pembahasan Quiz

#### Kunci Jawaban Bagian 1:
1. **C** (Di bawah ~31 GB, agar representasi pointer 32-bit tetap dipertahankan oleh JVM).
2. **B** (OS Page cache digunakan langsung oleh Lucene via direct memory mapping untuk menyimpan immutable index segments tanpa membebani heap JVM).
3. **D** (HTTP 429 / `EsRejectedExecutionException`).
4. **B** (`vm.max_map_count` memastikan proses Lucene mmap tidak dibatasi oleh kernel saat membuka ribuan segment file).
5. **B** (`bootstrap.memory_lock: true` menginstruksikan modul Java untuk memanggil fungsi C-system call `mlockall()`).

#### Kunci Jawaban Bagian 2:
6. **C** (Pengaturan `indices.breaker.total.use_real_memory: true` melacak memory tracking langsung pada alokasi aktual heap JVM).
7. **B** (Stack trace `ConcurrentMergeScheduler` menunjukkan thread CPU sedang disibukkan oleh operasi kompresi segment merging Lucene).
8. **A** (Menyamakan Xms dan Xmx mencegah overhead pause sistem saat kernel/JVM harus meminta resize memory address range).
9. **B** (Overhead shard yang berlebihan menciptakan jutaan file pointer metadata yang menghabiskan heap memori dan membebani transfer cluster state master node).
10. **A** (Jika mutasi pembuatan objek data baru melampaui throughput pembersihan memory region G1GC, engine JVM terpaksa fallback ke Stop-The-World Full GC).

#### Panduan Jawaban Skenario Kasus Produksi:
* **Solusi Skenario 1**:
  - *Akar Masalah*: Alokasi heap 128 GB melampaui batas Compressed OOPs, menggandakan ukuran reference pointer menjadi 64-bit yang memboroskan utilisasi heap hingga 40-50%. Selain itu, heap 128 GB menyisakan porsi Page Cache yang tidak memadai untuk membaca segment Lucene secara direct memory, memicu lonjakan disk I/O reads fisik. Terakhir, memindai heap raksasa 128 GB menyebabkan durasi GC pause G1GC melonjak puluhan detik (*node freeze*).
  - *Tindakan Koreksi*: Turunkan ukuran JVM heap secara drastis ke `31 GB` (`-Xms31g -Xmx31g`). Sisakan ~220 GB RAM fisik server murni sebagai OS Page Cache agar performa baca Lucene segments berjalan 100% in-memory.
* **Solusi Skenario 2**:
  - *Keputusan*: Tolak perubahan kenaikan queue size tersebut.
  - *Alasan*: Setiap write task yang tertahan di antrean queue menahan payload JSON/binary data di dalam heap RAM. Meningkatkan antrean menjadi 100.000 akan mengunci gigabyte memori heap di memory queue. Jika kapasitas thread pekerja tidak mencukupi, antrean raksasa ini akan memicu GC thrashing, meledakkan latency, dan berakhir pada insiden OOM Crash Klaster.
  - *Solusi Benar*: Implementasikan buffering dan backpressure di layer upstream/arsitektur (misal: Kafka Queue atau Logstash Persistent Queue) dengan penerapan algoritma *Exponential Backoff with Jitter* di layer client application.
* **Solusi Skenario 3**:
  - *Tindakan 1 (Cut Traffic)*: Putus sementara koneksi query pembacaan ke klaster pada level Reverse Proxy/Load Balancer, atau batasi akses hanya untuk master/ingest.
  - *Tindakan 2 (Evict Cache)*: Bersihkan cache fielddata dan request cache menggunakan API: `POST /_cache/clear?fielddata=true&request=true`.
  - *Tindakan 3 (Isolasi Query)*: Identifikasi query pemicu lonjakan memory melalui search slow log atau profiling endpoint `GET /_nodes/hot_threads`, lalu batalkan kueri aktif menggunakan Task Management API (`POST /_tasks/<task_id>/_cancel`).
  - *Tindakan 4 (Normalisasi)*: Turunkan limit konkurensi query di aplikasi frontend anti-fraud dan pasang circuit breaker client-side sebelum membuka kembali routing traffic load balancer.

---

## 16. Summary

1. **Prinsip Alokasi Memori**: Jangan pernah mengalokasikan seluruh RAM fisik untuk JVM Heap. Alokasikan maksimum **50% RAM** dan **$\le 31\text{ GB}$** demi mempertahankan efisiensi pointer 32-bit (*Compressed OOPs*). Sisakan 50% atau lebih RAM server untuk *OS Page Cache* tempat segment-segment Lucene dieksekusi secara native.
2. **Resiliensi Sistem Operasi**: Klaster enterprise wajib mematikan *swap memory* secara absolut dan mengaktifkan fitur `bootstrap.memory_lock: true`. Setel nilai batas *kernel virtual memory* `vm.max_map_count` ke angka minimal `262144` dan alokasikan file descriptors tanpa batasan ketat.
3. **Mekanisme Proteksi Internal**: *Circuit Breakers* bertindak sebagai sekring pengaman node dari insiden fatal OutOfMemory. Jangan menonaktifkan atau menaikkan batasan breaker secara serampangan. Respons HTTP 429 adalah indikator *backpressure* sistem yang sehat dan harus ditangani di upstream via queuing (Kafka/RabbitMQ) dengan strategi exponential backoff.
4. **Alat Diagnostik Utama**: Kuasai penggunaan endpoint performa internal:
   - `_nodes/hot_threads` untuk mengidentifikasi utilisasi thread CPU,
   - `_cat/thread_pool` untuk mendeteksi rejections dan queue sizing,
   - `_nodes/stats/jvm,breaker` untuk memantau lifecycle GC dan ancaman lonjakan alokasi heap.