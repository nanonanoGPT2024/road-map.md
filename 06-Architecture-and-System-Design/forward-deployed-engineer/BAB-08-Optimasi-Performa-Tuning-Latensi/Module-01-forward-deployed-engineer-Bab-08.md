## SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran:** Forward Deployed Engineer (FDE)
* **Kategori:** 06-Architecture-and-System-Design
* **Bab:** 08 — Optimasi Performa, Tuning Latensi & Skalabilitas Sistem
* **Modul:** 01 — Kernel Parameter Tuning, JVM/Go Runtime Profiling, Database Query & Disk I/O Optimization pada Hardware Klien
* **Tingkat Kesulitan:** Advanced / Production-Grade
* **Prasyarat Teknis:** Pemahaman mendalam tentang Linux OS Internals (VFS, IPC, TCP/IP stack), arsitektur runtime Go (scheduler, memory allocator) atau JVM (Garbage Collection mechanics), operasi dasar Relational Database Management System (PostgreSQL/MySQL), serta arsitektur storage (NVMe, SSD, block device caching).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Mendiagnosis Bottleneck Kernel Linux:** Mengidentifikasi dan memitigasi saturasi TCP stack, page cache thrashing, context switching berlebih, dan I/O starvation pada sistem operasi Linux di lingkungan on-premise klien menggunakan *sysctl*, *procfs*, dan *eBPF tools*.
2. **Melakukan Runtime Profiling Tingkat Lanjut:** Mengisolasi lock contention, memory leak, alokasi heap berlebih, dan GC pause p99 pada runtime Go (`pprof`, trace) dan JVM (`async-profiler`, GC logging, JFR) secara non-intrusif di lingkungan produksi terbatas.
3. **Mengoptimalkan Jalur Disk I/O & Database Engine:** Mengonfigurasi parameter write-ahead logging (WAL), dirty pages flush, Direct I/O, serta menelaah eksekusi query SQL melalui `EXPLAIN (ANALYZE, BUFFERS)` untuk mengatasi limitasi hardware I/O klien yang terdegradasi.
4. **Menerapkan Tuning End-to-End Berbasis Karakteristik Hardware:** Mengimplementasikan konfigurasi terpadu yang memadukan optimasi kernel, alokasi thread runtime, dan storage scheduler yang disesuaikan secara spesifik untuk hardware legacy atau non-cloud-native pada perimeter klien.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       +---------------------------------------------------+
                       |       CLIENT-SIDE RUNTIME INFRASTRUCTURE          |
                       +---------------------------------------------------+
                                                 |
         +---------------------------------------+---------------------------------------+
         |                                       |                                       |
+------------------+                   +--------------------+                  +--------------------+
|  LINUX KERNEL    |                   | APPLICATION RUNTIME|                  | STORAGE & DATABASE |
|  SUBSYSTEMS      |                   | (Go / JVM Engines) |                  | (I/O & Persistence)|
+------------------+                   +--------------------+                  +--------------------+
         |                                       |                                       |
         +--> TCP / Net Stack                    +--> Go Execution Tracer                +--> Page Cache vs Direct I/O
         |    - SOMAXCONN & syn_backlog          |    - pprof CPU/Mem/Mutex              |    - vm.dirty_background_ratio
         |    - TCP buffer autotuning            |    - Go scheduler (GOMAXPROCS)        |    - vm.dirty_ratio / flusher
         |                                       |                                       |
         +--> Virtual Memory                     +--> JVM Performance                    +--> Block Device Scheduler
         |    - vm.swappiness & overcommit       |    - G1GC / ZGC low latency           |    - none (NVMe) vs mq-deadline
         |    - Transparent Huge Pages (THP)     |    - async-profiler execution         |    - Storage I/O queues (iostat)
         |                                       |                                       |
         +--> Task Scheduling                    +--> Concurrency Bottlenecks            +--> Database Query Engine
              - sysctl context switch                 - Thread contention / park              - EXPLAIN (ANALYZE, BUFFERS)
              - File descriptors (nofile)             - Memory allocation hotspots            - WAL sync vs Write amplification
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sebagai seorang Forward Deployed Engineer (FDE), Anda jarang mendistribusikan software ke lingkungan cloud hyperscaler yang bersih, homogen, dan terukur secara elastis. Lingkungan on-premise klien sering kali menyajikan realitas yang kontras:
* Mesin virtual terfragmentasi dengan alokasi CPU overcommitted dari hypervisor pihak ketiga.
* Storage Area Network (SAN) yang lambat dengan latency jitter tinggi.
* Sistem operasi turunan enterprise (RHEL, Rocky, Ubuntu LTS) dengan parameter kernel *default* yang didesain untuk workstation desktop atau web server monolitik tahun 2010.
* Restriksi keamanan ketat yang melarang ekspansi resource vertikal maupun horizontal secara instan.

Ketika sistem enterprise yang Anda deploy mengalami spike latensi pada p99 atau crash mendadak akibat *Out-Of-Memory (OOM) killer*, Anda tidak bisa sekadar menaikkan spek cluster. Anda dituntut masuk ke lapisan terdalam sistem: mengaudit alokasi memori runtime, melacak bottleneck syscall kernel, dan menata ulang pola read/write database secara presisi di atas infrastruktur bare-metal/on-premise yang tersedia.

---

## SEKSI 05 — APA ITU (WHAT)

Optimasi performa pada ranah Forward Deployed Engineering adalah serangkaian metodologi sistematis untuk menyelaraskan tiga lapisan eksekusi utama:

1. **Kernel Linux Tuning:** Penyetelan variabel subsistem kernel melalui `/etc/sysctl.conf`, `limits.conf`, dan subsistem storage block device guna memaksimalkan throughput data dan meminimalkan context switching serta latency I/O wait.
2. **Application Runtime Profiling:** Pengambilan profil state internal aplikasi saat runtime (alokasi memori heap/stack, thread switching, goroutine blocking, lock serialization, dan waktu interupsi Garbage Collection) untuk mengeliminasi inefisiensi komputasi mikro.
3. **Database Engine & Disk I/O Alignment:** Konfigurasi caching, engine buffering, log synchronization, serta restrukturisasi indeks query yang diselaraskan dengan batas IOPS (Input/Output Operations Per Second) dan throughput bus disk fisik pada mesin klien.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### 1. Lapisan Kernel: Network & Virtual Memory Subsystem

Secara default, parameter kernel Linux diatur konservatif. Pada lalu lintas throughput tinggi:
* **TCP Listen Backlog:** Koneksi masuk yang belum selesai di-handshake (`TCP SYN`) akan dibuang jika `tcp_max_syn_backlog` dan `somaxconn` terlalu rendah, menyebabkan latensi koneksi ulang (retransmission timeout/RTO).
* **TCP Buffer Memory:** Variabel `net.ipv4.tcp_rmem` dan `tcp_wmem` mengontrol ukuran buffer minimum, default, dan maksimum per socket. Tanpa TCP buffer autotuning yang memadai, throughput jaringan via bandwidth-delay product (BDP) tinggi akan tercekik.
* **Dirty Pages & Swap Memory:** Ketika aplikasi menulis data ke disk, Linux menuliskannya ke Page Cache terlebih dahulu (*dirty pages*). Jika dirty memory mencapai batas `vm.dirty_ratio`, kernel memblokir proses yang sedang menulis (*write throttling*) sampai data dipaksa ke storage fisik. Jika `vm.swappiness` disetel terlalu tinggi, Linux akan menukar halaman memori anonim aktif ke partisi swap disk, memicu latensi eksekusi aplikasi secara masif.

### 2. Lapisan Runtime Profiling (Go & JVM)

* **Go Runtime:** Go mengimplementasikan scheduler M:N (`G`oroutine, `M`achine OS thread, `P`rocessor context). Profiling Go (`pprof`, trace) menggunakan teknik sampling berbasis interupsi timer (SIGPROF) untuk mencatat program counter. Mutex/block profiling mengukur waktu yang dihabiskan goroutine menunggu channel operations atau lock contention. Memory profiling melacak alokasi heap melalui stack trace sampling berbasis byte size.
* **JVM Runtime:** Eksekusi bytecode JVM dikompilasi Just-In-Time (JIT) ke assembly native. Hotspot/contention analysis via Java Flight Recorder (JFR) atau `async-profiler` membaca call stack tanpa terpengaruh "safepoint bias" (kondisi sampling hanya terjadi saat semua thread berada di safepoint JVM). Garbage Collector (G1GC, ZGC) membagi memory pool (Eden, Survivor, Tenured/Old) dan memicu pause time (STW - Stop-The-World) jika laju alokasi mengalahkan laju siklus pembersihan konkuren.

### 3. Lapisan Disk I/O & Engine Database

* **Page Cache Bypass (Direct I/O):** Database transaksional mengelola cache memory internal mereka sendiri (misalnya, `shared_buffers` di PostgreSQL, `innodb_buffer_pool_size` di MySQL). Jika storage engine menulis melalui file system standar tanpa Direct I/O (`O_DIRECT`), terjadi fenomena *double buffering* (duplikasi data di memory database dan Linux page cache), yang menghabiskan memori fisik dan memicu OOM killer.
* **Write-Ahead Log (WAL) Flush:** Database ACID memanggil `fdatasync()` atau `fsync()` pada interval transaksi untuk menjamin integritas persistensi. Jika antrean hardware queue disk jenuh (utilisasi disk 100%), panggilan `fsync()` akan memblokir thread database, memicu penumpukan connection pool.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Arsitektur Aliran I/O dari Runtime hingga Disk Driver

```
+-------------------------------------------------------------------------+
|                          APPLICATION RUNTIME                            |
|                                                                         |
|  [ Go Goroutine Pool / JVM Threads ]                                    |
|              |                                                          |
|              v                                                          |
|  [ Internal Buffers ] (PostgreSQL shared_buffers / In-Memory Queue)      |
+-------------------------------------------------------------------------+
       |                                              |
       | Standard POSIX write()                       | Direct I/O (O_DIRECT)
       v                                              |
+--------------------------------------------------+  |
|                  LINUX KERNEL                    |  |
|                                                  |  |
|   +------------------------------------------+   |  |
|   |            Virtual File System           |   |  |
|   +------------------------------------------+   |  |
|        |                                         |  |
|        v                                         |  |
|   +------------------------------------------+   |  |
|   |         Linux Page Cache (Dirty)         |   |  |
|   |                                          |   |  |
|   |   Thresholds:                            |   |  |
|   |   vm.dirty_background_ratio (Async flush)|   |  |
|   |   vm.dirty_ratio (Block caller write!)   |   |  |
|   +------------------------------------------+   |  |
|        |                                         |  |
|        v (flusher threads: kworker/flush)        |  |
|   +------------------------------------------+   |  |
|   |         I/O Scheduler / Block Layer      | <-+  |
|   |                                          |      |
|   |   Schedulers: [none/kyber for NVMe]      |      |
|   |               [mq-deadline for SATA/SAS] |      |
|   +------------------------------------------+      |
+-----------------------------------------------------+
       |
       v (Device Driver Submission Queue)
+-------------------------------------------------------------------------+
|                        STORAGE HARDWARE                                 |
|                                                                         |
|   +-----------------------------------------------------------------+   |
|   | Physical Disk Controller Cache (NVMe On-board RAM / Battery BBU)|   |
|   +-----------------------------------------------------------------+   |
|        |                                                                |
|        v (Non-Volatile Persistence)                                     |
|   [ NAND Flash Memory Arrays / Magnetic Platters ]                      |
+-------------------------------------------------------------------------+
```

### Siklus Profiling CPU & Profil Alokasi Runtime

```
[ Application Process ]
       |
       |  (Koleksi Sampling Profiler)
       +--------------------------------------------+
       |                                            |
       v                                            v
[ Go: runtime/pprof ]                     [ JVM: async-profiler ]
 - Sampling: SIGPROF Timer                 - Sampling: Perf Events + AsyncGetCallTrace
 - Call Stack Unwinding                    - Non-safepoint intrusive traces
 - Memory: mcache/mcentral capture         - Lock: Java Monitors & Park Wait
       |                                            |
       +--------------------+-----------------------+
                            |
                            v
               [ Output Format: FlameGraph ]
    +-------------------------------------------------------+
    |           runtime.systemstack (15%)                   |
    |-------------------------------------------------------|
    |       runtime.gcDrain (25%)                           |
    |-------------------------------------------------------|
    |  main.ProcessBatch (55%)                              |
    |-------------------------------------------------------|
    |  json.Marshal (30%)     |  db.(*Rows).Scan (25%)      |
    +-------------------------------------------------------+
    0%                                                    100%
    Lebar balok = Total CPU time yang dikonsumsi stack frame
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah contoh audit cepat parameter kernel Linux menggunakan bash script langsung di server target untuk mengidentifikasi apakah mesin siap menahan beban traffic tinggi tanpa network packet drop atau I/O lockup:

```bash
#!/usr/bin/env bash
# audit_kernel.sh - Evaluasi Konfigurasi Dasar Mesin Klien
set -euo pipefail

echo "=== MEMORY SUBSYSTEM ==="
echo -n "Swappiness (Rekomendasi server database <= 10): "
sysctl -n vm.swappiness

echo -n "Dirty Background Ratio (Rekomendasi 5-10%): "
sysctl -n vm.dirty_background_ratio

echo -n "Dirty Ratio (Rekomendasi 10-20%): "
sysctl -n vm.dirty_ratio

echo -n "Transparent Huge Pages (Rekomendasi [madvise] atau [never]): "
cat /sys/kernel/mm/transparent_hugepage/enabled

echo ""
echo "=== NETWORK SUBSYSTEM ==="
echo -n "Somaxconn (Socket listen backlog, min 4096): "
sysctl -n net.core.somaxconn

echo -n "TCP Max SYN Backlog (min 4096): "
sysctl -n net.ipv4.tcp_max_syn_backlog

echo -n "File Descriptors Limit (sys-wide): "
sysctl -n fs.file-max

echo ""
echo "=== STORAGE SCHEDULER ==="
for disk in $(lsblk -d -n -o NAME | grep -E '^sd|^nvme|^vd'); do
    sched_path="/sys/block/${disk}/queue/scheduler"
    if [ -f "$sched_path" ]; then
        echo "Disk ${disk} scheduler: $(cat "$sched_path")"
    fi
done
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus Produksi Nyata: Sebuah microservice data ingestion berbasis Go yang terhubung ke PostgreSQL on-premise klien mengalami *p99 latency degradation* dari 15ms melesat hingga 3500ms saat traffic mencapai 8.000 RPS. Terjadi peningkatan drastis pada status iowait kernel (`%iowait` melonjak ke 48%).

Berikut adalah alur resolusi end-to-end yang dilakukan FDE.

### 1. File Konfigurasi Tuning Kernel Linux (`/etc/sysctl.d/99-latency-tuning.conf`)

Terapkan parameter berikut untuk mengatasi kernel TCP drops, memory lockup, dan socket starvation:

```ini
# Meningkatkan batas backlog antrean koneksi socket
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 32768
net.core.netdev_max_backlog = 16384

# Mengaktifkan buffer TCP autotuning dengan alokasi maksimum 16MB per socket
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# Port range dinamis diperluas untuk menghindari ephemeral port exhaustion
net.ipv4.ip_local_port_range = 10240 65535

# Menghindari swap memory berlebih yang memicu latency spike pada JVM/Go/DB
vm.swappiness = 1

# Mencegah kernel menahan terlalu banyak dirty pages sebelum di-flush ke storage fisik
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10

# Meningkatkan limit resource file descriptors per sistem
fs.file-max = 2097152
```

Terapkan segera tanpa reboot:
```bash
sudo sysctl -p /etc/sysctl.d/99-latency-tuning.conf
```

### 2. Go Runtime Profiling Setup & Code Optimization

Berikut kode pipeline ingestion Go sebelum dan sesudah profiling via `pprof`. Profiling mengungkap bahwa pipeline memicu alokasi heap berulang secara masif (`runtime.mallocgc`) di dalam loop pemrosesan string dan decoding JSON, serta lock contention tinggi akibat global mutex.

#### Implementasi Sebelum Tuning (Lambat & Boros Alokasi Memori):

```go
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	_ "net/http/pprof" // Digunakan untuk pprof endpoint
	"sync"
)

type EventPayload struct {
	ID        string `json:"id"`
	ClientID  string `json:"client_id"`
	Timestamp int64  `json:"timestamp"`
	Payload   string `json:"payload"`
}

type IngestionService struct {
	mu    sync.Mutex
	cache map[string]EventPayload
}

// IngestionHandler menimbulkan lock contention dan heap allocation tinggi
func (s *IngestionService) IngestionHandler(w http.ResponseWriter, r *http.Request) {
	var payload EventPayload
	// Decode langsung dari HTTP stream tanpa reuse buffer
	err := json.NewDecoder(r.Body).Decode(&payload)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// Alokasi memori berlebih untuk hashing ID
	hasher := sha256.New()
	hasher.Write([]byte(payload.ID + payload.ClientID))
	hashKey := hex.EncodeToString(hasher.Sum(nil))

	s.mu.Lock() // Bottleneck: single mutex melumpuhkan concurrency seluruh goroutine
	s.cache[hashKey] = payload
	s.mu.Unlock()

	w.WriteHeader(http.StatusAccepted)
}
```

#### Implementasi Setelah Profiling & Tuning (Zero Allocation Pattern & Sharded Locks):

```go
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"io"
	"net/http"
	_ "net/http/pprof"
	"sync"

	jsoniter "github.com/json-iterator/go"
)

var (
	jsonFast = jsoniter.ConfigCompatibleWithStandardLibrary
	// Object pooling untuk mengurangi alokasi memori heap (GC pressure)
	hasherPool = sync.Pool{
		New: func() interface{} {
			return sha256.New()
		},
	}
	bufferPool = sync.Pool{
		New: func() interface{} {
			b := make([]byte, 4096)
			return &b
		},
	}
)

const ShardCount = 256

type ShardedMap struct {
	shards []*MapShard
}

type MapShard struct {
	sync.RWMutex
	items map[string]EventPayload
}

func NewShardedMap() *ShardedMap {
	m := &ShardedMap{shards: make([]*MapShard, ShardCount)}
	for i := 0; i < ShardCount; i++ {
		m.shards[i] = &MapShard{items: make(map[string]EventPayload)}
	}
	return m
}

func (m *ShardedMap) getShard(key string) *MapShard {
	var hash uint32 = 2166136261
	for i := 0; i < len(key); i++ {
		hash = (hash ^ uint32(key[i])) * 16777619
	}
	return m.shards[hash%ShardCount]
}

type OptimizedIngestionService struct {
	shardedCache *ShardedMap
}

func (s *OptimizedIngestionService) IngestionHandler(w http.ResponseWriter, r *http.Request) {
	// Ambil buffer dari sync.Pool
	bufPtr := bufferPool.Get().(*[]byte)
	defer bufferPool.Put(bufPtr)

	// Baca body langsung ke buffer pool
	n, err := io.ReadFull(r.Body, *bufPtr)
	if err != nil && err != io.ErrUnexpectedEOF && err != io.EOF {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	var payload EventPayload
	if err := jsonFast.Unmarshal((*bufPtr)[:n], &payload); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// Gunakan hasher dari sync.Pool
	h := hasherPool.Get().(javaLikeHasher)
	h.Reset()
	defer hasherPool.Put(h)

	h.Write([]byte(payload.ID))
	h.Write([]byte(payload.ClientID))
	
	// Gunakan byte array lokal di stack untuk menampung checksum digest
	var sumBuf [32]byte
	digest := h.Sum(sumBuf[:0])
	
	var hexBuf [64]byte
	hex.Encode(hexBuf[:], digest)
	hashKey := string(hexBuf[:])

	// Eksekusi mutasi pada shard tertentu, meminimalisir thread contention
	shard := s.shardedCache.getShard(hashKey)
	shard.Lock()
	shard.items[hashKey] = payload
	shard.Unlock()

	w.WriteHeader(http.StatusAccepted)
}

type javaLikeHasher interface {
	Write(p []byte) (n int, err error)
	Sum(b []byte) []byte
	Reset()
}
```

### 3. Profiling Eksekusi via Terminal Linux

Mengambil profil CPU dan Block Profile saat traffic memuncak:
```bash
# 1. Capture CPU profile selama 30 detik
go tool pprof -proto http://localhost:6060/debug/pprof/profile?seconds=30 > cpu.pb.gz

# 2. Capture Contention Block Profile
go tool pprof -proto http://localhost:6060/debug/pprof/block?seconds=30 > block.pb.gz

# 3. Tampilkan stack trace penyebab alokasi terbesar langsung di konsol
go tool pprof -top -cum cpu.pb.gz
```

### 4. Database Query & Disk I/O Alignment (PostgreSQL)

Analisis query bottleneck yang menyebabkan storage starvation:

```sql
-- Evaluasi eksekusi query ingestion check
EXPLAIN (ANALYZE, BUFFERS, SETTINGS)
SELECT id, client_id, timestamp, payload 
FROM client_events 
WHERE client_id = 'CL-88219' 
  AND timestamp >= 1709251200 
ORDER BY timestamp DESC 
LIMIT 50;
```

#### Hasil EXPLAIN sebelum Optimasi:
```
Gather Merge  (cost=125432.12..129841.54 rows=37790 width=84) (actual time=845.210..892.430 rows=50 loops=1)
  Workers Planned: 4
  Workers Launched: 4
  Buffers: shared hit=412 read=85942 written=120
  I/O Timings: read=682.112
  ->  Sort  (cost=124432.06..124455.68 rows=9448 width=84) (actual time=839.112..839.120 rows=50 loops=4)
        Sort Key: timestamp DESC
        Sort Method: top-N heapsort  Memory: 42kB
        Buffers: shared hit=1648 read=343768
        ->  Parallel Seq Scan on client_events  (cost=0.00..122394.00 rows=9448 width=84) (actual time=0.082..742.110 rows=8912 loops=4)
              Filter: ((timestamp >= 1709251200) AND (client_id = 'CL-88219'::text))
              Rows Removed by Filter: 1250000
              Buffers: shared hit=1648 read=343768
Planning Time: 0.154 ms
Execution Time: 893.102 ms
```

**Diagnosa Masalah:**
`Parallel Seq Scan` memaksa PostgreSQL membaca 343.768 block memory (`shared read`), memicu I/O disk sebesar ~2.7 GB langsung dari disk fisik yang lambat (`read=682.112ms`).

#### Remediasi: DDL Indexing + Postgres Buffer Tuning

Buat composite covering index untuk memindahkan eksekusi dari disk sequential scan ke direct index-only lookups:

```sql
-- Pembuatan composite index terurut
CREATE INDEX CONCURRENTLY idx_client_events_lookup 
ON client_events (client_id, timestamp DESC) 
INCLUDE (payload);
```

Perubahan parameter konfigurasi PostgreSQL (`postgresql.conf`):
```ini
# Menyesuaikan cache size dengan kapasitas RAM klien (contoh RAM 64GB)
shared_buffers = 16GB
effective_cache_size = 48GB

# Optimasi penulisan WAL agar disk controller tidak terbebani commit sinkron
wal_buffers = 64MB
checkpoint_completion_target = 0.9
max_wal_size = 16GB
min_wal_size = 2GB

# Menyelaraskan random cost dengan kapabilitas SSD / NVMe on-premise
random_page_cost = 1.1
effective_io_concurrency = 200
```

#### Hasil EXPLAIN setelah Optimasi:
```
Limit  (cost=0.56..12.34 rows=50 width=84) (actual time=0.045..0.120 rows=50 loops=1)
  Buffers: shared hit=52
  ->  Index Only Scan using idx_client_events_lookup on client_events  (cost=0.56..8912.45 rows=37790 width=84) (actual time=0.043..0.110 rows=50 loops=1)
        Index Cond: ((client_id = 'CL-88219'::text) AND (timestamp >= 1709251200))
        Heap Fetches: 0
        Buffers: shared hit=52
Planning Time: 0.098 ms
Execution Time: 0.145 ms
```

*Dampak:* Waktu eksekusi terpangkas dari **893.102 ms** menjadi **0.145 ms** (penurunan latensi sebesar 99.98%), dan I/O disk turun ke nol karena buffer terpenuhi langsung di RAM (`shared hit=52`).

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Strategi Tuning | Keuntungan (Pros) | Biaya / Konsekuensi (Cons) | Rekomendasi Kontekstual |
| :--- | :--- | :--- | :--- |
| **Penurunan `vm.swappiness` (misal: 0 atau 1)** | Menghindari latensi spike aplikasi; heap memory terlindungi dari swap-out ke storage fisik. | Risiko *Out-of-Memory (OOM) Killer* mengeksekusi proses utama secara agresif saat memori fisik benar-benar habis. | Terapkan pada sistem dedicated database atau core JVM services. Jangan gunakan jika host berbagi resource dengan daemon lain. |
| **Agresifitas Dirty Background Ratio Rendah (5%)** | Disk I/O writes disebar secara halus (*steady stream*), mencegah I/O freeze mendadak akibat mass-flush. | Meningkatkan frekuensi background write kernel, mengurangi throughput maksimal sequential storage streaming. | Wajib untuk database OLTP transaksi tinggi di mana stabilitas p99/p999 latency lebih diprioritaskan daripada throughput agregat. |
| **Object Pooling (`sync.Pool` / JVM Object Recyclers)** | Mengeliminasi beban garbage collection secara drastis, mengurangi durasi Stop-The-World (STW). | Kompleksitas kode bertambah signifikan; potensi memory leak jika objek gagal dibersihkan sebelum dikembalikan ke pool. | Hanya gunakan pada hot-path alokasi internal tingkat tinggi (>10.000 alokasi objek/detik). |
| **Direct I/O (`O_DIRECT`)** | Mencegah fenomena *double buffering* antara aplikasi engine dan Linux Page Cache, menghemat RAM. | Menghilangkan keuntungan filesystem readahead otomatis kernel; engine database harus mengelola read cache internal mandiri. | Gunakan pada software database khusus (Cassandra, PostgreSQL, ScyllaDB) yang didukung hardware NVMe berkecepatan tinggi. |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Metodologi USE (Utilization, Saturation, Errors) karya Brendan Gregg:** 
   Sebelum mengubah konfigurasi apapun, ukur sistem secara hierarkis:
   * *Utilization:* Berapa persen rata-rata komponen (CPU core, disk queue, NIC) sibuk?
   * *Saturation:* Berapa kedalaman antrean (task wait queue, backlog drops)?
   * *Errors:* Apakah ada frame drop di interface, disk read timeout, atau TCP reset?
2. **Ubah Satu Variabel dalam Satu Waktu:** 
   Jangan pernah menggabungkan penyesuaian parameter kernel, JVM flags, dan query refactoring sekaligus dalam satu deployment rilis performa. Terapkan satu perubahan, validasi metrik menggunakan load test, konfirmasi hipotesis, lalu lanjutkan.
3. **Persistensikan Konfigurasi Kernel Secara Modular:**
   Hindari modifikasi manual langsung pada file `/etc/sysctl.conf`. Gunakan direktori terisolasi seperti `/etc/sysctl.d/60-fde-app-tuning.conf` dan integrasikan ke dalam infrastructure-as-code automation (Ansible/Puppet) agar tidak tertimpa saat update OS klien.
4. **Alokasikan Cgroup Resource Quota Secara Defensif:**
   Jika aplikasi dideploy di host multi-tenant klien, bungkus binary Anda dalam systemd slice atau runtime container dengan isolasi memory limit dan cpu limit (`systemd-cgtop`) untuk mencegah kernel panik global.
5. **Simpan Dump Profile Secara Kontinu (Continuous Profiling):**
   Deploy agent profiling berbiaya rendah (seperti Grafana Pyroscope atau pprof trigger berkala) untuk menangkap anomali *sebelum* insiden performa di mesin klien mereda dengan sendirinya.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Menonaktifkan Swap Secara Buta Tanpa Memahami Pola Memori:**
   Banyak engineer langsung mengeksekusi `swapoff -a` karena rekomendasi Kubernetes. Pada hardware on-premise dengan footprint RAM terbatas, ketiadaan swap menyebabkan kernel kehilangan ruang darurat untuk melempar halaman memori anonim dorman, mempercepat pembunuhan proses utama oleh OOM-Killer saat terjadi lonjakan traffic mikro. *Solusi:* Tetapkan `vm.swappiness = 1` untuk mencegah swap reguler namun mempertahankan ruang darurat OS.
2. **Mengabaikan Dampak Transparent Huge Pages (THP) pada Database:**
   THP aktif secara *default* (`always`) di banyak distribusi Linux enterprise. Alih-alih meningkatkan performa lewat page table cache (TLB) hit, THP menyebabkan defragmentasi memori internal kernel dinamis yang memicu *latency freeze* pada PostgreSQL, MySQL, dan Redis. *Solusi:* Set `echo madvise > /sys/kernel/mm/transparent_hugepage/enabled`.
3. **Mengasumsikan Ukuran Heap JVM Harus Mengambil 90% RAM Host:**
   Mengalokasikan JVM `-Xmx` sebesar 28GB pada mesin 32GB sering memicu OOM host. Ruang tersisa (4GB) sering kali tidak memadai untuk JVM Native Memory (Metaspace, thread stack, code cache) dan kebutuhan fundamental I/O page cache kernel OS. *Solusi:* Sisakan minimal 25-30% memori fisik untuk OS dan file cache I/O jika aplikasi melakukan manipulasi file intensif.
4. **Relying Solely on Wall-Clock Time Saat Profiling:**
   Melihat latensi profiling hanya berdasarkan wall-time tanpa menganalisis status lock contention sering menipu engineer. Contoh: fungsi terlihat lambat bukan karena CPU-bound, melainkan thread sedang disuspensi oleh thread pool wait atau channel synchronization starvation.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Latihan
Anda diberikan akses SSH ke sebuah node VM on-premise CentOS/Rocky Linux 9 (`user@client-vm-01`) dengan spesifikasi: 4 vCPU, 8GB RAM, and Virtual Disk storage. Host ini menjalankan aplikasi backend pemrosesan log yang mengalami bottleneck transaksi disk dan TCP connection drop.

### Tugas:
1. **Diagnosis Kernel Saturation:**
   * Ambil data utilizasi disk real-time menggunakan `iostat -xz 1 10`. Identifikasi parameter `%util` dan `await`.
   * Periksa apakah terjadi drop TCP SYN queue menggunakan command:
     ```bash
     netstat -s | grep -i "listen"
     ```
2. **Remediasi Konfigurasi Kernel:**
   * Buat file konfigurasi `/etc/sysctl.d/98-custom-tuning.conf` yang mengaktifkan:
     - `net.core.somaxconn = 32768`
     - `vm.dirty_background_ratio = 5`
     - `vm.dirty_ratio = 10`
   * Load konfigurasi tersebut ke kernel yang sedang berjalan.
3. **Profiling Aplikasi:**
   * Gunakan perintah profiling CPU pada binary lokal yang disertakan di direktori lab:
     ```bash
     go tool pprof http://localhost:6060/debug/pprof/profile?seconds=20
     ```
   * Dari shell interactive pprof, jalankan perintah `top20 -cum` dan identifikasi nama fungsi internal yang paling banyak memakan CPU cycles.
4. **Analisis Database Buffers:**
   * Masuk ke engine database PostgreSQL lab. Jalankan `EXPLAIN (ANALYZE, BUFFERS)` untuk query pencarian transaksi log. Catat rasio `shared hit` berbanding `shared read`. Rancang satu indeks yang menaikkan `shared hit` menjadi 100%.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa bahaya mengeset parameter kernel `vm.dirty_ratio` ke angka yang sangat tinggi (misal: 80%) pada mesin yang menjalankan database OLTP dengan disk write throughput rendah?**
   * A. Query select akan gagal akibat lock table timeout.
   * B. Kernel akan menumpuk dirty memory sangat banyak di Page Cache; saat threshold tercapai, proses penulisan akan diblokir (*I/O stall*) selama berdetik-detik sementara kernel membersihkan dirty pages ke disk secara sinkron.
   * C. Seluruh koneksi TCP akan di-reset paksa oleh subsistem networking.
   * D. Kapasitas RAM akan dialokasikan permanen dan tidak dapat dikembalikan meski aplikasi di-restart.

2. **Pada runtime Go, profil apa yang paling tepat digunakan untuk menginvestigasi sebuah thread goroutine yang memakan waktu lama menunggu sinkronisasi channel atau sync.Mutex?**
   * A. Heap Profile (`/debug/pprof/heap`)
   * B. Goroutine Profile (`/debug/pprof/goroutine`)
   * C. Block/Mutex Profile (`/debug/pprof/block` atau `/debug/pprof/mutex`)
   * D. CPU Profile (`/debug/pprof/profile`)

3. **Mengapa indeks database bertipe B-Tree yang mencakup semua kolom target (Covering Index / Index-Only Scan) jauh lebih efisien pada disk storage klien yang memiliki IOPS terbatas?**
   * A. Indeks database mengekstrak file langsung dari L1/L2 cache CPU.
   * B. PostgreSQL/MySQL tidak perlu melakukan retrieval baris data fisik tambahan ke Heap Table file (meniadakan disk read amplification).
   * C. Menghilangkan kebutuhan ACID engine untuk menulis data ke Write-Ahead Log (WAL).
   * D. Mengubah format penulisan file table menjadi in-memory bitset.

4. **Kapan teknik `sync.Pool` dalam Go justru menurunkan performa aplikasi atau menyebabkan memory leak terselubung?**
   * A. Saat objek yang dimasukkan ke dalam pool memiliki ukuran memori bervariasi sangat ekstrem (misal slice dinamis dari 64 byte hingga 50MB) yang tidak pernah dilepas kembali ke OS.
   * B. Saat aplikasi berjalan di atas CPU dengan arsitektur multicore (lebih dari 16 vCPU).
   * C. Saat garbage collection Go berjalan setiap 2 menit sekali.
   * D. Saat tipe data yang dipooling adalah tipe data primitif seperti integer.

5. **Apa indikasi utama bahwa konfigurasi parameter `shared_buffers` di PostgreSQL disetel terlalu kecil untuk beban kerja transaksi baca-tulis aktif?**
   * A. Metrik `Buffers: shared hit` bernilai jauh lebih besar daripada `shared read` pada execution plan query.
   * B. Query plan sering beralih secara dinamis ke sequential scan.
   * C. Tingkat metrik read latency pada execution plan tinggi disertai dominasi nilai `Buffers: shared read` berulang kali untuk query yang sama.
   * D. Postgres crash dengan error *segmentation fault*.

---

### Kunci Jawaban & Logika Penilaian

* **1: B** — Ketika dirty buffer mencapai `vm.dirty_ratio`, kernel Linux mengeksekusi *synchronous write flushing*. Semua syscall `write()` berikutnya akan tertahan di status D-state (Uninterruptible Sleep), melumpuhkan responsivitas aplikasi.
* **2: C** — Block dan Mutex profiling didesain spesifik untuk melacak durasi waktu tunggu Goroutine ketika memperebutkan primitive synchronization (lock acquisition wait, channel send/receive wait).
* **3: B** — Dengan Covering Index, semua field yang diminta query tersedia langsung di struktur daun (leaf pages) B-Tree index, sehingga database tidak perlu membaca blok data tabel asli (*heap fetches = 0*), mereduksi random disk reads drastis.
* **4: A** — Mengembalikan buffer/slice berukuran sangat besar (misal puluhan megabyte) ke `sync.Pool` akan menahan memori tersebut di heap selama siklus GC belum menyapu pool, memicu pemborosan memori gigabyte jika pool terus menyimpan objek terbesar.
* **5: C** — Jika `shared_buffers` terlalu kecil, data yang sering diakses terus-menerus terlempar dari database cache, memaksa database memintanya ke OS Page Cache atau langsung membaca dari physical disk, yang terlihat dari metrik `shared read` yang konsisten tinggi.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Panduan Teknis Utama:**
  * Gregg, Brendan (2020). *Systems Performance: Enterprise and the Cloud, 2nd Edition*. Addison-Wesley Professional.
  * Love, Robert (2010). *Linux Kernel Development, 3rd Edition*. Novell.
  * Kleppmann, Martin (2017). *Designing Data-Intensive Applications*. O'Reilly Media.
* **Dokumentasi Profiling & Runtime Internals:**
  * Go Runtime Profiler Engine Source: `runtime/pprof` & `src/runtime/mgc.go`.
  * async-profiler Project Repository & Mechanics: `https://github.com/async-profiler/async-profiler`.
  * PostgreSQL Global Development Group. *Chapter: Monitoring Database Activity & Performance Tuning*. `https://www.postgresql.org/docs/current/performance-tips.html`.
* **Kernel Specifications:**
  * The Linux Kernel Organization. *Documentation for /proc/sys/vm/ and /proc/sys/net/*: `https://www.kernel.org/doc/Documentation/`.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

```
================================================================================
                          PERFORMANCE TUNING RUNBOOK
================================================================================

1. SUBSISTEM KERNEL LINUX
   |-- Network : Set somaxconn & tcp_max_syn_backlog >= 32768 (hindari SYN drops).
   |-- Memory  : Set vm.swappiness = 1 (cegah swap storm; pertahankan safety margin).
   |-- Storage : Atur vm.dirty_ratio (10%) & dirty_background_ratio (5%) (hindari I/O stall).
   +-- Sched   : Matikan THP (Transparent Huge Pages) untuk database OLTP.

2. RUNTIME OPTIMIZATION (Go / JVM)
   |-- Sampling: Gunakan async-profiler / pprof untuk melacak CPU hotspot non-safepoint.
   |-- Locking : Hindari global mutex lock; implementasikan sharded lock patterns.
   |-- Mem Alloc: Kurangi GC pressure via sync.Pool / allocation reuse pada pipeline panas.
   +-- Scheduler: Pastikan thread count tidak memicu excessive context switching.

3. PERSISTENCE & DATABASE ENGINE
   |-- Indexing: Buat Composite / Covering Index untuk memotong Disk Read Amplification.
   |-- Buffering: Set shared_buffers / innodb_buffer_pool memadai (25-50% Total RAM).
   |-- I/O Path: Pisahkan mount disk transaksi log (WAL) dengan main data directories.
   +-- Scheduler: Gunakan block scheduler 'none' (NVMe) atau 'mq-deadline' (SATA SSD).
================================================================================
```

---

## SEKSI 17 — GLOSARIUM

* **Bandwidth-Delay Product (BDP):** Volume data yang dapat berada dalam pipa transit jaringan pada satu waktu (Throughput × Round Trip Delay). Menentukan batas ukuran TCP buffer yang optimal.
* **Covering Index:** Indeks sekunder yang mencakup semua kolom yang dibutuhkan oleh query, menghilangkan kebutuhan untuk membaca tabel fisik (*heap table access*).
* **Direct I/O (`O_DIRECT`):** Flag operasi I/O file di Linux yang menginstruksikan kernel untuk langsung membaca atau menulis data dari memori aplikasi ke device penyimpanan tanpa menyalinnya ke Linux Page Cache.
* **FlameGraph:** Representasi grafis dari profil hierarki call stack program, di mana sumbu X menunjukkan persentase waktu CPU/alokasi memori yang dihabiskan, dan sumbu Y menampilkan kedalaman stack trace.
* **Page Cache:** Mekanisme kernel Linux untuk menyimpan salinan halaman data storage fisik ke dalam RAM utama guna mempercepat operasi baca dan tulis berikutnya.
* **Stop-The-World (STW):** Fase eksekusi internal Garbage Collector di mana seluruh thread komputasi aplikasi dihentikan sementara agar GC dapat memutakhirkan graph referensi objek memori tanpa konkurensi liar.
* **Uninterruptible Sleep (D-State):** Kondisi proses di Linux yang sedang menunggu respon langsung dari subsistem hardware (biasanya disk storage). Proses dalam state ini tidak dapat diinterupsi oleh signal (termasuk `kill -9`).

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Fokus Pembelajaran:** Arahkan peserta agar tidak menghafal angka konfigurasi sysctl secara mentah. Tekankan *prinsip relasi*: "Mengapa nilai X harus diturunkan jika nilai Y dinaikkan?". Hardware klien sangat bervariasi; menghafal nilai tetap akan berakibat fatal di lapangan.
* **Tipikal Troubleshooting di Lapangan:** Dalam lingkungan on-premise klien yang heavily virtualized (contoh: VMware ESXi overcommitted), ingatkan peserta bahwa latency spike sering kali berasal dari *CPU Steal Time* (`%st` pada command `top`). Sebelum melakukan tuning internal kernel atau query, pastikan bahwa hypervisor host fisik klien tidak sedang mencekik resource virtual VM yang bersangkutan.
* **Keamanan:** Pertegas kepada engineer untuk selalu memvalidasi file descriptor limits (`limits.conf`) bersamaan dengan penyesuaian `sysctl fs.file-max`, karena kesalahan pengaturan dapat mengunci user non-root keluar dari sistem setelah logout.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Maret 2025):**
  * Rilis inisial materi komprehensif Bab 08 Modul 01.
  * Standardisasi format silabus enterprise Forward Deployed Engineer (FDE).
  * Penambahan skenario kasus optimasi Go memory pooling dan PostgreSQL execution buffer tuning.
  * Penyusunan modul arsitektur ASCII diagram and comprehensive performance runbook.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** Kategori 06 — Bab 07: High Availability, Fault Tolerance, Disaster Recovery & Chaos Engineering di Infrastruktur Terisolasi.
* **Modul Berikutnya:** Kategori 06 — Bab 08 / Modul 02: Network Performance Tuning, Edge Proxy Latency & Data Plane Acceleration (eBPF, DPDK, Envoy Routing).