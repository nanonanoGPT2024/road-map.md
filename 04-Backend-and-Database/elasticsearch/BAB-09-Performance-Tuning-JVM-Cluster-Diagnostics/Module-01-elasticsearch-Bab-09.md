# Bab 09 Module 01: Performance Tuning, JVM & Cluster Diagnostics

---

## 01. Identitas Modul
* **Mata Kuliah**: Production Elasticsearch Engineering & Architecture
* **Kategori**: `04-Backend-and-Database`
* **Kode Modul**: `ES-ENG-B09-M01`
* **Judul Modul**: Performance Tuning, JVM & Cluster Diagnostics
* **Tingkat Kesulitan**: Advanced / Principal Level
* **Prasyarat**: Pemahaman mendalam arsitektur node Elasticsearch, Lucene Segment Architecture, Linux System Internals (VFS, swap, page cache), dan Java Garbage Collection (G1GC).

---

## 02. Learning Objectives
1. Mendiagnosis dan mengeliminasi bottleneck performa pada layer I/O, JVM Memory, dan Network Stack.
2. Mengonfigurasi JVM Heap, Compressed OOPs, Direct Memory, dan Garbage Collector (G1GC/ZGC) secara deterministik untuk beban kerja baca/tulis masif.
3. Menganalisis *thread pool queues*, *circuit breakers*, dan *hot threads* menggunakan API diagnostik tingkat rendah.
4. Menerapkan optimasi indeks tingkat lanjut: dynamic segment merging, refresh interval tuning, translog durability, dan search cache management.
5. Membangun pipeline diagnostik otomatis berbasis metric/telemetry untuk mencegah kondisi *cluster freeze* dan *OutOfMemory (OOM)*.

---

## 03. Concept Map Diagram ASCII

```
+-------------------------------------------------------------------------------+
|                       LINUX OPERATING SYSTEM LAYER                            |
|  [sysctl: vm.max_map_count=262144] [swap: vm.swappiness=1] [limits: nofile=65535] |
+---------------------------------------+---------------------------------------+
                                        |
+---------------------------------------v---------------------------------------+
|                    JAVA VIRTUAL MACHINE (JVM) LAYER                           |
|  +---------------------------------+  +------------------------------------+  |
|  |       ON-HEAP MEMORY (<=31GB)   |  |        OFF-HEAP / DIRECT MEMORY    |  |
|  | - Filter Cache / Index Buffers  |  | - Lucene Inverted Index (FST)      |  |
|  | - Request Cache                 |  | - OS Page Cache (Fast Disk I/O)    |  |
|  | - Circuit Breakers (Parent 95%) |  | - Compressed Ordinary Object Ptrs  |  |
|  +---------------------------------+  +------------------------------------+  |
|               | (G1GC / ZGC Cycles)                  |                        |
+---------------+--------------------------------------+------------------------+
                |                                      |
+---------------v--------------------------------------v------------------------+
|                     ELASTICSEARCH CLUSTER RUNTIME                             |
|  +----------------------------------+  +-----------------------------------+  |
|  |      WRITE / INGEST PATH         |  |        SEARCH / READ PATH         |  |
|  | - Bulk Queue -> Indexing Buffer  |  | - Search Queue -> Coordinate Node |  |
|  | - Translog Flush Policy (Async)  |  | - Query & Fetch Phases            |  |
|  | - Dynamic Segment Merge Policy   |  | - Node Query Cache & Field Data   |  |
|  +----------------------------------+  +-----------------------------------+  |
+-------------------------------------------------------------------------------+
```

---

## 04. Mengapa Relevan?
Pada skala *petabyte-scale* dan puluhan ribu *operations per second* (OPS), Elasticsearch default tidak dirancang untuk efisiensi puncak. Kegagalan konfigurasi memori dapat memicu *Garbage Collection (GC) pauses* yang menyebabkan node *timeout*, pemisahan cluster (*split-brain/master disconnect*), atau kehabisan memori (*OOM Killers*). 

Penguasaan tuning JVM, diagnostik thread pool, dan orkestrasi I/O Lucene adalah pembeda fundamental antara cluster yang sering mengalami *degradasi status RED* dan infrastruktur enterprise yang mampu menyajikan SLA *zero-downtime latency* sub-100ms.

---

## 05. Anatomi Konsep Inti

### 5.1 Alokasi Memori: Aturan 50% Heap & Lucene Page Cache
Elasticsearch tidak hanya hidup di dalam JVM Heap. Mesin pencari Lucene memanfaatkan *OS Page Cache* (Off-Heap) secara ekstensif untuk menyimpan FST (*Finite State Transducers*), BKD-Trees, dan *Doc Values*.
* **Batas Maksimum Heap**: Jangan alokasikan Heap lebih dari 31 GB (biasanya 30.5 GB atau `31744m`) untuk mempertahankan *Compressed Ordinary Object Pointers* (Compressed OOPs). Jika Heap melampaui batas ambang (~32 GB), pointer beralih dari 32-bit relatif ke 64-bit absolut, yang membuang kapasitas 1.5x lebih besar untuk overhead memori yang sama.
* **Pembagian 50/50**: 50% total RAM untuk JVM Heap, 50% sisanya dibiarkan bebas untuk OS Page Cache.

### 5.2 Thread Pools & Queue Management
* **Write Thread Pool**: Bertanggung jawab atas pengindeksan dokumen. Karakteristik: `fixed`, kapasitas queue default `10000`. Jika penuh, melempar HTTP 429 (`EsRejectedExecutionException`).
* **Search Thread Pool**: Menangani kueri data. Karakteristik: `auto-adjusted` berdasarkan jumlah logical/physical cores.
* **Hot Threads Profiling**: Mekanisme inspeksi stack trace internal Java untuk melihat thread mana yang mengonsumsi CPU paling tinggi pada interval sampel tertentu.

### 5.3 Circuit Breakers
Mekanisme proteksi internal untuk mencegah JVM crash karena OOM:
* **Parent Circuit Breaker**: Mengontrol batas total penggunaan memori oleh seluruh sirkuit (default: `95%` heap).
* **Fielddata Circuit Breaker**: Mencegah pemuatan fielddata yang berlebihan ke memori (default: `40%` heap).
* **Request Circuit Breaker**: Membatasi ukuran struktur data aggregasi search request (default: `60%` heap).

---

## 06. Panduan Implementasi Step-by-Step

### Langkah 1: Konfigurasi Kernel dan OS Linux Host
Terapkan parameter kernel berikut pada `/etc/sysctl.d/99-elasticsearch.conf`:

```ini
# Memastikan Lucene memiliki batasan virtual memory mmap yang cukup
vm.max_map_count=262144

# Mengurangi kecenderungan kernel melakukan swapping memory JVM ke disk
vm.swappiness=1

# Mengoptimalkan buffer TCP
net.core.somaxconn=65535
net.ipv4.tcp_max_syn_backlog=65535
```

Jalankan perintah untuk menerapkan perubahan:
```bash
sudo sysctl --system
```

Konfigurasi Limit Sistem di `/etc/security/limits.d/99-elasticsearch.conf`:
```ini
elasticsearch soft nofile 65535
elasticsearch hard nofile 65535
elasticsearch soft nproc 4096
elasticsearch hard nproc 4096
elasticsearch soft memlock unlimited
elasticsearch hard memlock unlimited
```

### Langkah 2: Konfigurasi JVM Flags (`jvm.options`)
Konfigurasikan alokasi heap dan flag GC di `/etc/elasticsearch/jvm.options.d/heap.options`:

```jvmoptions
# Set Min dan Max Heap identik untuk mencegah runtime heap resizing penalty
-Xms30g
-Xmx30g

# Optimasi G1 Garbage Collector untuk low latency
-XX:+UseG1GC
-XX:InitiatingHeapOccupancyPercent=45
-XX:G1ReservePercent=15
-XX:MaxGCPauseMillis=50
-XX:+ParallelRefProcEnabled

# Nonaktifkan Explicit GC
-XX:+DisableExplicitGC

# Dump heap jika terjadi OutOfMemoryError
-XX:+HeapDumpOnOutOfMemoryError
-XX:HeapDumpPath=/var/log/elasticsearch/oom-dump.hprof
```

### Langkah 3: Konfigurasi Core Engine (`elasticsearch.yml`)
Tambahkan parameter runtime berikut di `/etc/elasticsearch/elasticsearch.yml`:

```yaml
cluster.name: enterprise-core-cluster
node.name: es-hot-data-01
bootstrap.memory_lock: true

# Thread pool tuning
thread_pool:
  write:
    size: 16
    queue_size: 10000
  search:
    size: 24
    queue_size: 1000

# Circuit breaker settings
indices.breaker.total.use_real_memory: true
indices.breaker.total.limit: 95%
indices.breaker.fielddata.limit: 30%
```

---

## 07. Contoh Kasus Sederhana: Optimasi Indeks Time-Series

Berikut adalah implementasi pengaturan indeks log throughput tinggi (*Write-Heavy Index*):

```http
PUT /telemetry-logs-2026.03.30
{
  "settings": {
    "index": {
      "number_of_shards": 3,
      "number_of_replicas": 0,
      "refresh_interval": "30s",
      "translog": {
        "durability": "async",
        "sync_interval": "10s",
        "flush_threshold_size": "1gb"
      },
      "merge": {
        "scheduler": {
          "max_thread_count": "1"
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "@timestamp": { "type": "date" },
      "node_id": { "type": "keyword" },
      "metrics": {
        "properties": {
          "cpu_usage": { "type": "float" },
          "mem_usage": { "type": "float" }
        }
      }
    }
  }
}
```

---

## 08. Implementasi Production-Grade: Skrip Diagnostik Otomatis & Tuning

Berikut adalah skrip Python produksi menggunakan library resmi `elasticsearch` untuk memonitor metrik JVM, melacak bottleneck thread pool, dan mendeteksi segment throttling secara real-time.

```python
#!/usr/bin/env python3
"""
Production Elasticsearch Diagnostic and Auto-Tuner Engine
File: es_cluster_diagnostics.py
"""

import sys
import time
from typing import Dict, Any, List
from elasticsearch import Elasticsearch, TransportError

class ElasticsearchDiagnosticEngine:
    def __init__(self, es_client: Elasticsearch):
        self.es = es_client

    def check_compressed_oops(self, node_id: str) -> bool:
        """Memvalidasi apakah JVM menggunakan 32-bit Compressed OOPs."""
        try:
            jvm_info = self.es.nodes.info(node_id=node_id, metric="jvm")
            nodes_data = jvm_info.get("nodes", {})
            for _, info in nodes_data.items():
                vm_options = info.get("jvm", {}).get("vm_options", [])
                for opt in vm_options:
                    if "UseCompressedOops" in opt:
                        return True
            return False
        except TransportError as err:
            print(f"[ERROR] Gagal membaca metadata JVM: {err}")
            return False

    def inspect_cluster_health_and_breakers(self) -> Dict[str, Any]:
        """Memeriksa status health, circuit breakers, dan rejected execution."""
        stats = self.es.nodes.stats(metric=["breakers", "thread_pool", "indices", "jvm"])
        nodes = stats.get("nodes", {})
        
        diagnostics = {
            "timestamp": time.time(),
            "nodes_checked": len(nodes),
            "unhealthy_nodes": []
        }

        for node_id, data in nodes.items():
            node_name = data.get("name", "unknown")
            jvm_stats = data.get("jvm", {}).get("mem", {})
            heap_used_percent = jvm_stats.get("heap_used_percent", 0)
            
            # Breakers
            parent_breaker = data.get("breakers", {}).get("parent", {})
            tripped_count = parent_breaker.get("tripped", 0)
            
            # Write ThreadPool Drops
            thread_pool = data.get("thread_pool", {})
            write_rejected = thread_pool.get("write", {}).get("rejected", 0)
            search_rejected = thread_pool.get("search", {}).get("rejected", 0)

            node_status = {
                "node_id": node_id,
                "node_name": node_name,
                "heap_percent": heap_used_percent,
                "parent_breaker_tripped": tripped_count,
                "write_rejected_count": write_rejected,
                "search_rejected_count": search_rejected,
                "critical": False
            }

            if heap_used_percent > 85 or write_rejected > 0 or tripped_count > 0:
                node_status["critical"] = True
                diagnostics["unhealthy_nodes"].append(node_status)

        return diagnostics

    def fetch_hot_threads(self, node_id: str = None) -> str:
        """Mengambil thread yang membebani CPU secara internal."""
        try:
            return self.es.nodes.hot_threads(node_id=node_id, threads=5, type_="cpu")
        except TransportError as err:
            return f"[ERROR] Gagal mengeksekusi hot_threads: {err}"

    def optimize_heavy_index(self, index_pattern: str):
        """Menerapkan dynamic index tuning saat cluster berada dalam write load ekstrem."""
        print(f"[*] Menyesuaikan setting untuk pattern: {index_pattern}")
        tuning_payload = {
            "index": {
                "refresh_interval": "60s",
                "translog.durability": "async",
                "translog.flush_threshold_size": "2gb"
            }
        }
        response = self.es.indices.put_settings(index=index_pattern, body=tuning_payload)
        return response

if __name__ == "__main__":
    # Konfigurasi koneksi dengan HTTPS & API Key
    ES_HOST = "https://127.0.0.1:9200"
    API_KEY = "VGhpcy1pcy1hLWZha2UtYXBpLWtleS1mb3ItZGVtby1vbmx5"

    client = Elasticsearch(
        [ES_HOST],
        api_key=API_KEY,
        verify_certs=False  # Ganti True di production dengan custom CA cert
    )

    engine = ElasticsearchDiagnosticEngine(client)
    
    print("[+] Menjalankan Diagnostik Cluster...")
    diag_result = engine.inspect_cluster_health_and_breakers()
    
    print(f"[i] Total Nodes: {diag_result['nodes_checked']}")
    if diag_result["unhealthy_nodes"]:
        print("[!] PERINGATAN: Ditemukan node kritis:")
        for unh in diag_result["unhealthy_nodes"]:
            print(f"    - {unh['node_name']} (Heap: {unh['heap_percent']}%, Write Rejects: {unh['write_rejected_count']})")
            print("[+] Mengambil Hot Threads untuk mitigasi...")
            hot_threads = engine.fetch_hot_threads(node_id=unh['node_id'])
            print(hot_threads[:500] + "\n...[truncated]")
    else:
        print("[v] Semua Node beroperasi dalam batas parameter optimal.")
```

---

## 09. Diagram Alur Kerja Diagnostik

```
                          +------------------------+
                          |   Trigger Diagnostik   |
                          | (Cron / PagerDuty / APM)|
                          +-----------+------------+
                                      |
                                      v
                       +-------------------------------+
                       | Periksa Status Heap JVM & GC  |
                       +---------------+---------------+
                                       |
                +----------------------+----------------------+
                |                                             |
       Heap > 85% / GC > 100ms                       Heap < 75% / GC Normal
                |                                             |
                v                                             v
+-------------------------------+             +-------------------------------+
| Check Breakers & Memory Leaks |             |  Periksa Thread Pool Queues   |
+---------------+---------------+             +---------------+---------------+
                |                                             |
    Tripped > 0 |                                Rejected > 0 |
                v                                             v
+-------------------------------+             +-------------------------------+
| 1. Capture jstack / Heap Dump |             | 1. Tangkap Node Hot Threads   |
| 2. Identifikasi High Aggs/Docs|             | 2. Naikan Ingest Batching     |
| 3. Tingkatkan Shard Partition |             | 3. Set Dynamic Throttle Write |
+-------------------------------+             +-------------------------------+
```

---

## 10. Analisis Trade-offs

| Parameter | Setting Agresif | Setting Konservatif | Konsekuensi / Trade-off |
| :--- | :--- | :--- | :--- |
| `refresh_interval` | `60s` / `-1` | `1s` (Default) | Throughput ingest naik masif, namun latensi kueri realtime (*search visibility*) menurun drastis. |
| `translog.durability` | `async` | `request` | Meminimalisir I/O Disk bottlenecks, namun terdapat potensi kehilangan data hingga rentang `sync_interval` jika node crash/power outage. |
| Heap Size | `31GB` | `16GB` | Kapasitas filter cache dan in-flight aggregations lebih besar, namun durasi cycle G1GC Mark-Sweep bisa meningkat jika memory leaks terjadi. |
| `bootstrap.memory_lock` | `true` | `false` | Menjamin JVM tidak terlempar ke swap space disk, namun proses Elasticsearch gagal *startup* jika limit `memlock` OS tidak dikonfigurasi `unlimited`. |

---

## 11. Best Practices & Antipatterns

### Best Practices
* **Pertahankan Shard Size**: Ukuran shard ideal time-series logs adalah 30 GB - 50 GB. Shard terlalu kecil memicu alokasi overhead FST berlebih pada Heap; shard terlalu besar mempersulit proses *relocation/recovery*.
* **Gunakan Explicit Mapping**: Hindari dynamic mapping untuk mencegah mapping explosion yang membebani *Cluster State* di master node.
* **Bulk Ingestion Optimizations**: Kirim data menggunakan `_bulk` API dengan payload sizing 5 MB hingga 15 MB per batch, bukan mengirim satu dokumen per satu HTTP POST.

### Antipatterns
* **Over-sharding**: Membuat ratusan shard per index kecil. Menyebabkan alokasi heap memori habis hanya untuk memegang metadata shard.
* **Heap > 32 GB**: Mengalokasikan 40 GB - 64 GB heap karena mengira "makin besar makin baik", yang justru menonaktifkan *Compressed OOPs* dan menurunkan performa pointer.
* **Menggunakan Wildcard Aggregation Pada Text Unindexed**: Memicu pembacaan direct memory masif yang mengaktifkan *Circuit Breakers*.

---

## 12. Security Hardening
* **Restrict Admin APIs**: Blokir akses publik ke endpoint kritis (`/_nodes/hot_threads`, `/_cluster/settings`, `/_cat/*`) menggunakan Reverse Proxy atau Layer 7 Security Rules.
* **Node-to-Node TLS Encryption**: Pastikan `xpack.security.transport.ssl.enabled: true` dengan TLS minimal versi 1.3 menggunakan Cipher Suite: `TLS_AES_256_GCM_SHA384`.
* **Resource Quota Enforcement**: Terapkan Role-Based Access Control (RBAC) dengan limit search profile untuk mencegah user non-admin mengeksekusi aggregasi global tanpa batasan size.

---

## 13. Observabilitas & Debugging

Gunakan native REST endpoint untuk investigasi mendalam:

1. **Investigasi JVM GC dan Memory Pool**:
   ```http
   GET /_nodes/stats/jvm?filter_path=nodes.*.jvm.mem,nodes.*.jvm.gc
   ```

2. **Deteksi Thread Pool Rejection**:
   ```http
   GET /_cat/thread_pool/write,search?v=true&h=node_name,name,active,queue,rejected,completed
   ```

3. **Diagnosa Hot Threads (Analisis Stack Trace On-the-Fly)**:
   ```http
   GET /_nodes/hot_threads?threads=3&interval=500ms&type=cpu
   ```

---

## 14. Benchmarking & Performance

Jalankan pengujian benchmarking deterministik menggunakan `esrally` untuk mengukur dampak konfigurasi heap dan disk merge policy:

```bash
# Instalasi esrally
pip3 install esrally

# Jalankan benchmark pada cluster lokal (track default: nyc_taxis)
esrally race \
  --pipeline=benchmark-only \
  --target-hosts=127.0.0.1:9200 \
  --client-options="basic_auth_user:'elastic',basic_auth_password:'YourSecurePassword',use_ssl:false" \
  --track=nyc_taxis \
  --challenge=append-no-conflicts
```

### Metrik Evaluasi:
* **Throughput Target**: Minimal 50.000 docs/sec per ingest data node (SSD NVMe).
* **Search Latency (99th Percentile)**: Di bawah 120ms pada aggregate analytics queries.
* **GC Pause Time**: Rata-rata GC Mark-Sweep di bawah 50ms per siklus.

---

## 15. Hands-on Lab Mini-Project

### Skenario:
Cluster 3-node mengalami *Indexing Bottleneck* dan sering melempar status HTTP 429 pada log collector. Anda ditugaskan mengidentifikasi akar masalah, mengubah konfigurasi I/O indeks secara dinamis, dan memverifikasi bahwa rejection kembali ke angka nol.

### Instruksi Kerja:
1. Simulasikan traffic tinggi dan inspeksi antrian rejection:
   ```bash
   curl -s -X GET "http://localhost:9200/_cat/thread_pool/write?v&h=node_name,queue,rejected"
   ```
2. Temukan indeks yang terdampak dan lakukan dynamic update settings:
   ```bash
   curl -X PUT "http://localhost:9200/*/_settings" -H 'Content-Type: application/json' -d'
   {
     "index" : {
       "refresh_interval" : "30s",
       "translog.flush_threshold_size" : "1gb",
       "translog.durability" : "async"
     }
   }'
   ```
3. Lakukan profiling threads untuk memastikan tidak ada disk lock I/O yang tertahan:
   ```bash
   curl -X GET "http://localhost:9200/_nodes/hot_threads"
   ```

---

## 16. Automated Testing & Verification

Skrip Bash di bawah ini dapat diintegrasikan pada CI/CD pipeline untuk memverifikasi kesiapan operasional konfigurasi node:

```bash
#!/usr/bin/env bash
set -euo pipefail

ES_HOST="http://localhost:9200"

echo "[TEST 1] Memeriksa status bootstrap memory_lock..."
MEM_LOCK=$(curl -s "${ES_HOST}/_nodes/stats/process" | jq '.nodes[].process.mlockall')
if [[ "${MEM_LOCK}" != "true" ]]; then
    echo "FAILED: memory_lock bernilai false! Periksa vm.swappiness dan limits.conf."
    exit 1
fi
echo "PASSED: memory_lock aktif."

echo "[TEST 2] Memeriksa heap limit safety threshold..."
HEAP_USAGE=$(curl -s "${ES_HOST}/_cat/nodes?h=heap.percent" | head -n 1 | tr -d ' ')
if [ "${HEAP_USAGE}" -gt 85 ]; then
    echo "FAILED: Heap utilization terlalu tinggi: ${HEAP_USAGE}%"
    exit 1
fi
echo "PASSED: Heap utilization aman (${HEAP_USAGE}%)."

echo "[TEST 3] Memeriksa status write rejection pool..."
REJECTED=$(curl -s "${ES_HOST}/_cat/thread_pool/write?h=rejected" | awk '{s+=$1} END {print s}')
if [ "${REJECTED}" -gt 0 ]; then
    echo "WARNING: Ditemukan rejection sebanyak ${REJECTED} operasi."
else
    echo "PASSED: Rejection pool bernilai 0."
fi

echo "Semua uji diagnostik dasar lolos validasi!"
```

---

## 17. Troubleshooting Guide

| Gejala Masalah | Indikasi Metrik | Potensi Penyebab | Tindakan Remediasi |
| :--- | :--- | :--- | :--- |
| **HTTP 429 Too Many Requests** | `thread_pool.write.rejected > 0` | Buffer write queue terlampaui karena ingest load lebih cepat daripada disk merge IOPS. | 1. Naikkan `refresh_interval` menjadi `30s`.<br>2. Perbesar batch `_bulk` sizing.<br>3. Migrasi shard data ke SSD NVMe. |
| **Cluster State: Node Disconnected** | Hot threads menunjukkan `G1 ConcurrentGC` memakan CPU 100% | GC Pause masif (>30 detik) menyebabkan node gagal merespon heartbeat master. | 1. Turunkan heap jika > 31GB.<br>2. Tambahkan node ingest/data baru.<br>3. Ubah `InitiatingHeapOccupancyPercent` ke 40. |
| **CircuitBreakingException** | `parent.tripped > 0` | Memory usage gabungan query data & request context melampaui 95% heap. | 1. Batasi ukuran agregasi (`size: 0` jika memungkinkan).<br>2. Hindari `fielddata: true` pada tipe field `text`. |

---

## 18. Checklist Produksi

- [ ] Nilai `vm.max_map_count` terkonfigurasi minimal `262144` di `/etc/sysctl.conf`.
- [ ] `vm.swappiness` diatur ke `1` untuk memprioritaskan page cache tanpa hard disable swap kernel.
- [ ] JVM Heap dialokasikan tepat $\le$ 50% dari total sistem memori (maksimum 30.5 GB).
- [ ] `bootstrap.memory_lock: true` aktif dan terkonfirmasi `true` via `_nodes/stats/process`.
- [ ] Limit OS `nofile` (file descriptors) diset ke `65535` atau lebih tinggi.
- [ ] Garbage collector dikonfigurasi menggunakan G1GC dengan tuning `MaxGCPauseMillis=50`.
- [ ] Konfigurasi `index.refresh_interval` pada log ingest time-series diset minimal `30s`.
- [ ] Mekanisme pemantauan alert otomatis disiapkan untuk `thread_pool.write.rejected` dan `jvm.gc.collectors.young/old.collection_time_in_millis`.

---

## 19. Ringkasan Eksekutif
Performa optimal Elasticsearch bergantung pada keseimbangan antara alokasi JVM On-Heap dan pemanfaatan OS Page Cache Off-Heap untuk Lucene. 

Kunci stabilitas kluster skala besar berada pada:
1. Alokasi heap di bawah 31 GB untuk mempertahankan *Compressed OOPs*.
2. Penguncian memori proses (`mlockall`) guna mencegah paging disk latency.
3. Penyesuaian I/O Lucene (refresh interval, translog durability, dynamic segment merges).
4. Pemantauan proaktif terhadap *thread pool queues* dan *circuit breakers* menggunakan diagnostic API (`_nodes/hot_threads`, `_cat/thread_pool`).

Penerapan tuning yang tepat mencegah *Garbage Collection pause spikes* dan mengoptimalkan latensi kueri secara konsisten pada infrastruktur backend berskala tinggi.

---

## 20. Referensi & Bacaan Lanjutan
1. Elasticsearch Official Reference: *Tuning for indexing speed & search performance*.
2. Lucene Documentation: *IndexWriter, ConcurrentMergeScheduler, and Segment Merging Internals*.
3. Hunt, P., & O'Hanlon, M. (Java Performance Tuning): *Optimizing G1GC for low latency low pause footprints*.
4. Elasticsearch Diagnostics: Node Stats, Hot Threads, and Monitoring APIs.