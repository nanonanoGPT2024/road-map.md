# BAB-09-Performance-Tuning-JVM-Cluster-Diagnostics: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang untuk menguji, memvalidasi, dan mengukur pemahaman mendalam Anda mengenai performa runtime Elasticsearch, tuning Java Virtual Machine (JVM), pengelolaan OS kernel, mitigasi circuit breaker, serta investigasi cluster diagnostics di lingkungan beban tinggi (high-throughput production).

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1.1: Aturan Alokasi JVM Heap Size (50% RAM Rule)
Mengapa Elasticsearch merekomendasikan alokasi heap maksimum (`-Xmx`) tidak melebihi 50% dari total RAM fisik host?
- **A.** JVM membutuhkan sisa RAM untuk alokasi thread stack dan direct buffer.
- **B.** Setengah sisa RAM fisik dialokasikan khusus untuk Linux Page Cache (OS file system cache) agar Lucene dapat membaca data segment file langsung dari memori tanpa disk I/O.
- **C.** Mencegah Out-Of-Memory (OOM) error saat JVM Garbage Collector melakukan heap compaction.
- **D.** JVM Elasticsearch tidak mendukung pengalamatan memori 64-bit jika heap melebihi 32 GB.

> **Kunci Jawaban:** **B**  
> **Pembahasan Mendalam:** Arsitektur Lucene sangat bergantung pada OS filesystem cache (Page Cache). Ketika query dieksekusi, Lucene membaca inverted index, doc values, dan term dictionaries dari Page Cache. Jika JVM heap dialokasikan terlalu besar (misal 80-90% RAM), OS cache akan tercekik, memaksa query melakukan disk access (seek/read latency tinggi).

---

### Soal 1.2: Batas Compressed Ordinary Object Pointers (Compressed OOPs)
Berapa batas teoritis dan praktis alokasi heap JVM agar Java HotSpot VM tetap dapat mengaktifkan fitur Compressed OOPs (Zero-based / Shifted)?
- **A.** Tepat 16 GB.
- **B.** Sedikit di bawah ambang batas ~31-32 GB (umumnya disarankan ~30.5 GB atau 31 GB).
- **C.** Tepat 64 GB.
- **D.** Tidak ada batasan asalkan RAM fisik mencukupi.

> **Kunci Jawaban:** **B**  
> **Pembahasan Mendalam:** Di arsitektur 64-bit, Compressed OOPs merepresentasikan pointer memori 64-bit menggunakan 32-bit integer dengan melakukan 3-bit left shift (kelipatan 8 byte). Begitu heap melampaui batas ~31.8 GB hingga 32 GB, JVM terpaksa beralih ke 64-bit uncompressed pointers. Ini menyebabkan overhead memori melonjak 1.5x lipat, sehingga alokasi heap 33-35 GB justru memiliki usable object memory yang lebih kecil daripada heap 31 GB dengan Compressed OOPs aktif.

---

### Soal 1.3: Konfigurasi Memory Paging & Swapping
Parameter OS kernel apa yang wajib disetel ke nilai `1` (atau dinonaktifkan via swapoff) dan properti `elasticsearch.yml` apa yang mengunci proses memory agar tidak terlempar ke swap space?
- **A.** `vm.max_map_count=1` dan `cluster.routing.allocation.enable: none`
- **B.** `vm.swappiness=1` (atau `swapoff -a`) dan `bootstrap.memory_lock: true`
- **C.** `fs.file-max=65536` dan `indices.breaker.total.use_real_memory: false`
- **D.** `vm.overcommit_memory=2` dan `node.attr.box_type: hot`

> **Kunci Jawaban:** **B**  
> **Pembahasan Mendalam:** Jika OS melakukan paging pada memori heap JVM ke swap space (disk), operasi Garbage Collection dan traversal query akan memicu synchronous page faults yang membekukan (freeze) node. Elasticsearch mewajibkan swap dinonaktifkan atau diminimalkan (`vm.swappiness=1`) serta mengunci virtual address space proses ke physical RAM menggunakan system call `mlockall` via `bootstrap.memory_lock: true`.

---

### Soal 1.4: Diagnosis Pending Tasks
API mana yang digunakan untuk memeriksa task cluster metadata yang sedang mengantre di Master Node?
- **A.** `GET /_nodes/stats/jvm`
- **B.** `GET /_cluster/pending_tasks`
- **C.** `GET /_cat/thread_pool`
- **D.** `GET /_cluster/allocation/explain`

> **Kunci Jawaban:** **B**  
> **Pembahasan Mendalam:** `GET /_cluster/pending_tasks` menampilkan task tingkat cluster (seperti pembaruan mapping, pembuatan index, shard allocation, re-routing) yang sedang menunggu giliran diproses secara serial oleh dedicated master thread. Penumpukan pending tasks dengan status `URGENT` atau `HIGH` mengindikasikan Master Node mengalami bottleneck atau starvation.

---

### Soal 1.5: Hot Threads Profiling
Kapan engineer harus mengeksekusi `GET /_nodes/hot_threads`?
- **A.** Hanya ketika cluster dalam keadaan `red` untuk melihat corrupt file.
- **B.** Ketika terjadi lonjakan CPU usage mendekati 100% pada satu atau beberapa node, untuk menganalisis stack trace thread mana yang memonopoli CPU cycles.
- **C.** Saat disk space penuh untuk melihat fragmentasi B-Tree.
- **D.** Saat mendeteksi network packet drop antar-node.

> **Kunci Jawaban:** **B**  
> **Pembahasan Mendalam:** API `/_nodes/hot_threads` mengambil snapshot berulang (misal interval 500ms) dari CPU-bound threads dan menampilkan Java stack trace dari thread yang menghabiskan CPU cycles paling banyak. Ini alat diagnostik tercepat untuk membedakan apakah CPU terpakai oleh regex search, aggregasi berat, background merge Lucene, atau GC marking thread.

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 2.1: Analisis Thread Pool Rejections
Output dari `GET /_cat/thread_pool/write,search?v&h=node_name,name,active,queue,rejected` menunjukkan:
```text
node_name   name   active queue rejected
data-hot-01 write  16     1000  48291
data-hot-01 search 12     0     0
```
Tindakan penanganan teknis yang paling tepat dan aman adalah:
- **A.** Menaikkan `thread_pool.write.queue_size` dari default 1000 menjadi 50000 di runtime settings.
- **B.** Menambah ukuran JVM Heap dari 31 GB menjadi 64 GB tanpa memperhatikan Compressed OOPs.
- **C.** Mengaktifkan exponential backoff retry di sisi application ingest client, menaikkan bulk request size (MB/batch) dengan frekuensi request lebih rendah, dan menambah node ingest/data.
- **D.** Mematikan replica shard secara permanen di seluruh index.

> **Kunci Jawaban:** **C**  
> **Pembahasan Mendalam:** Menaikkan `queue_size` adalah antipattern fatal (memperparah OOM dan heap exhaustion karena jutaan document byte tertahan di memori queue). Jawaban benar adalah mengendalikan ingest pressure dari upstream: client wajib menangani response HTTP 429 (`TOO_MANY_REQUESTS` / `EsRejectedExecutionException`) menggunakan exponential backoff, mengoptimasi payload batching (5-15MB per bulk), dan melakukan scale-out data nodes jika kapasitas write hardware memang jenuh.

---

### Soal 2.2: Mekanisme Real Memory Circuit Breaker
Apa perbedaan mendasar antara Parent Circuit Breaker konvensional (`indices.breaker.total.limit`) dengan Real Memory Circuit Breaker (`indices.breaker.total.use_real_memory: true`)?
- **A.** Konvensional hanya mengukur alokasi heap child breaker (misal request + fielddata), sedangkan Real Memory Breaker mengukur konsumsi actual heap total JVM secara real-time termasuk memory yang belum ditagih oleh child breakers.
- **B.** Real Memory Breaker menggunakan disk NVMe swap sebagai fallback memori.
- **C.** Konvensional otomatis memicu heap dump saat menyentuh limit 95%.
- **D.** Real Memory Breaker menolak query search tetapi mengizinkan write unthrottled.

> **Kunci Jawaban:** **A**  
> **Pembahasan Mendalam:** Secara historis, child breakers (fielddata, request, inflight) memperkirakan konsumsi memori secara teoritis per payload. Jika ada object JVM liar di luar kalkulator breaker (seperti internal Lucene object atau temporary collections), node bisa crash terkena OOM JVM murni. Real Memory Circuit Breaker (default aktif sejak ES 7.0) membaca metrik heap nyata dari runtime JVM; jika actual heap melampaui limit (default 95%), breaker langsung memotong query baru sebelum OOM Killer OS menembak proses.

---

### Soal 2.3: Tuning JVM Garbage Collector: G1GC vs ZGC
Pada Elasticsearch 8.x modern dengan beban mixed workload (high indexing + deeply nested aggregations), flag JVM apa yang paling krusial untuk mengendalikan latency GC Stop-The-World (STW) saat menggunakan default Garbage-First (G1GC)?
- **A.** `-XX:+UseSerialGC -XX:MaxGCPauseMillis=1`
- **B.** `-XX:InitiatingHeapOccupancyPercent=45` dan `-XX:MaxGCPauseMillis=200`
- **C.** `-XX:+UseParallelGC -XX:NewRatio=2`
- **D.** `-XX:G1ReservePercent=90`

> **Kunci Jawaban:** **B**  
> **Pembahasan Mendalam:** G1GC membagi heap ke dalam region-region independen. Parameter `-XX:InitiatingHeapOccupancyPercent` (IHOP, default 45%) menentukan ambang batas total heap occupancy untuk memicu concurrent marking cycle. Jika indexing rate sangat tinggi dan allocation rate melampaui kemampuan G1GC melakukan concurrent cleanup, IHOP dapat diturunkan (misal ke 35-40%) agar cycle marking dimulai lebih awal, menghindari terjadinya "to-space exhausted" atau fallback ke Full GC STW yang merusak latency SLA.

---

### Soal 2.4: Investigasi `cluster/allocation/explain`
Ketika sebuah shard berada dalam status `UNASSIGNED`, Anda menjalankan perintah:
```json
POST /_cluster/allocation/explain
{
  "index": "telemetry-prod-2026.10.05",
  "shard": 0,
  "primary": true
}
```
Hasil response menunjukkan:
`"deciders": [ { "decider": "disk_threshold", "decision": "NO", "explanation": "the node is above the high watermark cluster setting [cluster.routing.allocation.disk.watermark.high=90%]" } ]`
Apa urutan tindakan remedi yang tepat tanpa menyebabkan data loss?
- **A.** Setel `cluster.routing.allocation.enable: none` lalu restart master node.
- **B.** Hapus replica shards atau naikkan storage disk node, atau sesuaikan sementara watermark via cluster settings jika disk physical expansion sedang disiapkan.
- **C.** Jalankan `POST /_cluster/reroute` dengan flag `allocate_empty_primary`.
- **D.** Turunkan refresh interval menjadi `1ms`.

> **Kunci Jawaban:** **B**  
> **Pembahasan Mendalam:** `allocate_empty_primary` pada pilihan C akan menghapus data lama shard tersebut secara permanen (data loss fatal). Shard gagal di-assign murni karena proteksi storage safety decider (high watermark disk > 90%). Solusinya adalah menambah kapasitas storage disk, melakukan rollover & kurasi index lama ke cold/frozen tier via ILM, atau menghapus index yang tidak dibutuhkan.

---

### Soal 2.5: Deep Paging Heap Trap (`search.max_result_window`)
Mengapa Elasticsearch membatasi `index.max_result_window` ke default 10,000 document, dan apa implikasi tuning memori jika engineer sembarangan menaikkannya ke 10,000,000?
- **A.** Karena Lucene segment tidak bisa menampung lebih dari 10.000 doc ID.
- **B.** Coordinator node wajib mengumpulkan dan menyortir $(from + size) \times N$ shards document score dan field data di dalam coordinator heap memori sebelum melakukan slicing return pagination.
- **C.** Karena REST serializer tidak dapat mengirim JSON berukuran lebih dari 10 MB.
- **D.** Karena network MTU membatasi packet transfer hingga 10.000 bytes.

> **Kunci Jawaban:** **B**  
> **Pembahasan Mendalam:** Pada distributed search (Query-Then-Fetch), jika client meminta page `from: 9000000, size: 10` pada index dengan 5 primary shards, setiap shard harus menghasilkan 9.000.010 top hit candidates dan mengirimkannya ke coordinator node. Coordinator node harus menampung $5 \times 9.000.010 \approx 45.000.050$ hits di priority queue heap memory untuk melakukan global sort. Ini langsung meledakkan heap memory coordinator node dan memicu circuit breaking atau OOM crash. Solusi paging skala masif yang tepat adalah `search_after` dengan `point_in_time` (PIT).

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 1: Badai Query Aggregation dan CircuitBreakingException
* **Konteks:** Cluster monitoring e-commerce (12 data nodes, masing-masing 64 GB RAM, 31 GB Heap). Pukul 14:00 saat flash sale, aplikasi analytics melempar ribuan error:
  ```text
  org.elasticsearch.common.breaker.CircuitBreakingException: [parent] Data too large, 
  data for [<transport_request>] would be [31885408256/29.6gb], which is larger than 
  the limit of [30601641984/28.5gb], real usage: [31885408256/29.6gb], new bytes reserved: [0/0b]
  ```
* **Dampak:** Node tidak crash, tetapi semua query search baru ditolak dengan HTTP 503 / 429.
* **Analisis & Investigasi:**
  1. Jalankan `GET /_nodes/stats/indices/fielddata,query_cache,request_cache?human` untuk melihat cache pool mana yang mengonsumsi heap terbesar.
  2. Periksa slow logs (`elasticsearch_index_search_slowlog.log`). Ditemukan query dashboard yang melakukan high-cardinality `terms` aggregation pada field `user_session_id` (tipe `text` tanpa `keyword` optimize, memicu runtime fielddata un-inverting di heap).
* **Solusi & Remediasi:**
  - **Tindakan Cepat (Mitigasi Immediate):** Evict fielddata cache via API:
    ```bash
    POST /*/_cache/clear?fielddata=true
    ```
  - **Tindakan Struktural:**
    - Larang runtime fielddata pada field tipe `text` (`indices.fielddata.cache.size` diberi batas pengaman, misal `10%`).
    - Ubah mapping `user_session_id` menjadi tipe `keyword` agar memanfaatkan **Doc Values** (disk-based columnar storage yang hidup di OS Page Cache di luar JVM Heap).
    - Batasi query aggregasi client agar menggunakan filter rentang waktu ketat dan hindari global aggregation tanpa composite pagination.

---

### Skenario 2: Stop-The-World (STW) GC Pause & False Node Dropouts
* **Konteks:** Cluster logging logistik terdiri dari 5 Master Nodes dan 20 Data Nodes. Setiap hari pukul 00:00 (saat batch compaction dan indexing harian berganti), Master Node log mencatat peringatan:
  ```text
  [master-01] node [data-node-14] left the cluster, reason: failed to ping, 
  [transport] master fault detection failed within [30s]
  ```
  Namun setelah 40 detik, `data-node-14` bergabung kembali (`node joined`), memicu shard rebalancing masif yang melumpuhkan network I/O cluster.
* **Akar Masalah (Root Cause):**
  - Pada `data-node-14`, log GC (`gc.log`) memperlihatkan:
    ```text
    GC(1842) Pause Full (Allocation Failure) 30890M->12400M(31744M) 34210.120ms
    ```
  - Full GC memakan waktu **34.2 detik** (Stop-The-World total freeze).
  - Timeout fault detection cluster diatur default: ping timeout 30 detik (`cluster.fault_detection.follower_check.timeout: 30s`). Karena JVM `data-node-14` freeze total selama 34.2 detik, ia tidak merespons heartbeat dari Master Node, sehingga dinyatakan *dead/left*.
* **Solusi & Remediasi:**
  1. **Investigasi Alokasi Heap:** Allocation failure terjadi karena batch ingest pukul 00:00 mengirimkan dokumen berukuran raksasa (>50 MB per bulk batch) secara paralel ke 16 thread.
  2. **Tuning JVM G1GC Flags:** Tambahkan optimasi G1GC pada `jvm.options`:
     ```text
     -XX:InitiatingHeapOccupancyPercent=35
     -XX:G1ReservePercent=15
     -XX:G1RegionSize=32m
     ```
  3. **Tuning Fault Detection Safety:**
     Tingkatkan toleransi temporary pause jika hardware disk/network memang membutuhkan grace period saat maintenance, namun prioritas utama tetap meniadakan Full GC dengan menurunkan bulk size upstream (maksimal 5-10 MB per chunk).

---

### Skenario 3: Disk Watermark Flood Stage Lockdown (Index Read-Only)
* **Konteks:** Sebuah data node berkapasitas 2 TB SSD mengalami lonjakan log mendadak. Pagi hari, seluruh pipeline indexing Kafka-Logstash gagal total dengan pesan error:
  ```text
  403 Forbidden: cluster_block_exception: [FORBIDDEN/12/index read-only / allow delete (api)];
  ```
* **Akar Masalah:** Disk usage node menyentuh 95.2%, melewati batas **Flood Stage Watermark** (`cluster.routing.allocation.disk.watermark.flood_stage` default 95%). Elasticsearch secara otomatis mengunci seluruh index di node tersebut ke mode `read-only` (`read_only_allow_delete: true`) untuk mencegah korupsi database internal Lucene.
* **Langkah Pemulihan Standar Produksi:**
  1. Bersihkan disk space (hapus index kadaluwarsa atau kurangi retention policy ILM).
  2. Setelah disk berada di bawah 85% (Low Watermark), buka kunci read-only secara eksplisit pada index:
     ```bash
     PUT /*/_settings
     {
       "index.blocks.read_only_allow_delete": null
     }
     ```
  3. Pastikan setting cluster tidak dimatikan fiturnya, melainkan pertahankan auto-protection watermark:
     ```bash
     PUT /_cluster/settings
     {
       "persistent": {
         "cluster.routing.allocation.disk.watermark.low": "85%",
         "cluster.routing.allocation.disk.watermark.high": "90%",
         "cluster.routing.allocation.disk.watermark.flood_stage": "95%",
         "cluster.info.update.interval": "1m"
       }
     }
     ```

---

## Bagian 4: Practical Chapter Challenge (Hands-on Performance Audit & Diagnostic CLI)

### Deskripsi Tugas
Anda ditugaskan sebagai Lead Performance Engineer untuk melakukan audit kesehatan dan diagnostik performa pada cluster Elasticsearch. Buat sebuah automated diagnostic check suite menggunakan script shell/cURL komprehensif yang mampu mendeteksi tanda-tanda degradasi performa sebelum insiden fatal terjadi.

### Kriteria & Metrik yang Wajib Divalidasi:
1. **Cluster Health & Unassigned Shards Audit:** Memeriksa health status dan mengekstrak alasan shard unassigned bila ada via `_cluster/allocation/explain`.
2. **JVM Heap & Compressed OOPs Check:** Memeriksa apakah node menggunakan heap <= 31GB dan rasio heap usage terhadap max limit.
3. **Thread Pool Rejection Monitor:** Mengidentifikasi apakah ada thread rejection pada pool `write`, `search`, atau `management`.
4. **Circuit Breaker Trip Monitor:** Memeriksa counter `tripped` pada seluruh circuit breakers (`parent`, `fielddata`, `request`, `in_flight`).
5. **Slow Query & Heavy Merge Diagnostic:** Memeriksa hot threads node untuk mendeteksi CPU bottlenecks.

### Skrip Referensi Implementasi:
```bash
#!/usr/bin/env bash
set -euo pipefail

ES_HOST="${ES_HOST:-http://localhost:9200}"

echo "================================================================="
echo "   ELASTICSEARCH PRODUCTION CLUSTER PERFORMANCE DIAGNOSTIC RUN   "
echo "================================================================="
echo "Target Endpoint: ${ES_HOST}"
echo ""

# 1. Cluster Health Check
echo "[+] Step 1: Memeriksa Status Cluster Health..."
HEALTH_JSON=$(curl -s "${ES_HOST}/_cluster/health")
STATUS=$(echo "${HEALTH_JSON}" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
UNASSIGNED=$(echo "${HEALTH_JSON}" | grep -o '"unassigned_shards":[0-9]*' | cut -d':' -f2)

echo "    -> Cluster Status    : ${STATUS}"
echo "    -> Unassigned Shards : ${UNASSIGNED}"

if [ "${UNASSIGNED}" -gt 0 ]; then
  echo "    [WARN] Terdeteksi unassigned shards! Menjalankan allocation explain..."
  curl -s "${ES_HOST}/_cluster/allocation/explain?pretty" | head -n 30
fi
echo ""

# 2. JVM Heap Usage & Compressed OOPs Check
echo "[+] Step 2: Audit Alokasi JVM Heap per Data Node..."
curl -s "${ES_HOST}/_cat/nodes?v&h=name,role,heap.current,heap.percent,heap.max,ram.current,ram.percent,ram.max"
echo ""

# 3. Thread Pool Rejection Audit
echo "[+] Step 3: Memeriksa Rejections pada Thread Pools (Write & Search)..."
REJECTIONS=$(curl -s "${ES_HOST}/_cat/thread_pool/write,search?v&h=node_name,name,active,queue,rejected")
echo "${REJECTIONS}"

REJECTED_COUNT=$(echo "${REJECTIONS}" | awk 'NR>1 {sum += $5} END {print sum}')
if [ "${REJECTED_COUNT:-0}" -gt 0 ]; then
  echo "    [ALERT] Terdeteksi akumulasi task rejection sebesar: ${REJECTED_COUNT} requests!"
else
  echo "    [OK] Tidak ada thread rejection pada pool write & search."
fi
echo ""

# 4. Circuit Breaker Audit
echo "[+] Step 4: Memeriksa Metrik Circuit Breakers..."
curl -s "${ES_HOST}/_nodes/stats/breaker?pretty" | grep -E '"name"|"tripped"|"limit_size_in_bytes"|"estimated_size_in_bytes"' | head -n 25
echo ""

# 5. Hot Threads Diagnostic Sample
echo "[+] Step 5: Pengambilan Sampel Hot Threads (Top CPU Consumers)..."
curl -s "${ES_HOST}/_nodes/hot_threads?threads=3" | head -n 35
echo ""

echo "================================================================="
echo "                 DIAGNOSTIC SUITE RUN COMPLETED                  "
echo "================================================================="
```

---

## Bagian 5: Checklist Pemahaman Evaluasi Mandiri

Gunakan checklist evaluasi ini untuk memastikan kesiapan produksi Anda sebelum mengelola cluster enterprise tier:

- [ ] **JVM Heap Discipline:** Saya memahami mengapa heap tidak boleh dialokasikan lebih dari 31 GB (Compressed OOPs) dan tidak boleh melebihi 50% RAM fisik host.
- [ ] **Operating System Safety:** Saya memahami cara kerja `bootstrap.memory_lock: true`, `vm.max_map_count=262144`, dan pengaturan `vm.swappiness=1` untuk stabilitas kernel.
- [ ] **Circuit Breaker Mastery:** Saya dapat membedakan peran Parent Breaker, Fielddata Breaker, Request Breaker, dan In-Flight Breaker, serta cara membaca exception `CircuitBreakingException`.
- [ ] **Thread Pool Diagnostics:** Saya dapat mengidentifikasi penumpukan queue dan task rejection pada thread pool `write` dan `search`, serta tahu kapan harus mengimplementasikan backoff client vs cluster horizontal scale-out.
- [ ] **Disk Watermarks Handling:** Saya memahami mekanisme transisi Low (85%), High (90%), hingga Flood Stage (95%), serta langkah pemulihan index dari status `read_only_allow_delete`.
- [ ] **Advanced Troubleshooting Tools:** Saya fasih mengeksekusi dan membaca output dari `_nodes/hot_threads`, `_cluster/allocation/explain`, `_cluster/pending_tasks`, dan Garbage Collection slow logs.
