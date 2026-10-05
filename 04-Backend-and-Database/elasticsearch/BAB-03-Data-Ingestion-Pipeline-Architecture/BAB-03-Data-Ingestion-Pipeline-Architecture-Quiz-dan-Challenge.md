# BAB-03-Data-Ingestion-Pipeline-Architecture: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi komprehensif untuk menguji pemahaman arsitektural dan implementasi praktis terkait **Data Ingestion Pipeline Architecture** pada Elasticsearch. Fokus materi mencakup perancangan pipeline ingest (Ingest Node & Processors), integrasi Beats/Logstash/Kafka, optimasi Bulk API, mitigasi backpressure (HTTP 429), dead-letter handling, hingga strategi data streaming berskala enterprise.

---

## Bagian 1: Basic Questions (5 Soal Konseptual Dasar)

### Pertanyaan 1: Perbedaan Arsitektur Ingest Node vs Logstash
**Pertanyaan:** Jelaskan perbedaan mendasar antara melakukan pemrosesan data menggunakan Ingest Node bawaan Elasticsearch dibandingkan menggunakan external processing cluster seperti Logstash. Kapan masing-masing pendekatan harus dipilih?

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

* **Ingest Node (Built-in Elasticsearch):**
  - Pemrosesan dilakukan langsung di dalam JVM cluster Elasticsearch sebelum dokumen diindeks ke Lucene shard.
  - Ringan, stateless dari perspektif antrean, tidak membutuhkan infrastruktur tambahan (tanpa server Logstash terpisah).
  - Terbatas pada proses transformasi in-place (grok, dissect, set, geoip, date). Tidak memiliki buffer persisten disk internal bawaan jika cluster mengalami overload.
  - Tepat digunakan untuk pipeline transformasi log/event standar, latensi rendah, deployment sederhana, atau ketika beban parsing CPU tidak mengganggu proses search/query cluster.
* **Logstash (External ETL):**
  - Beroperasi di luar cluster Elasticsearch sebagai layer pipeline terisolasi.
  - Mendukung ratusan input/output plugin (JDBC, Kafka, S3, syslog, Webhook) serta routing kompleks antar berbagai storage destination.
  - Memiliki fitur *Persistent Queues* (PQ) berbasis disk untuk mencegah data loss saat upstream/downstream bottleneck.
  - Tepat digunakan untuk multi-source aggregation, sinkronisasi DB relasional periodik, enrich data eksternal kompleks, atau ketika load parsing CPU sangat masif sehingga harus diisolasi total dari cluster Elasticsearch.
</details>

---

### Pertanyaan 2: Karakteristik dan Semantik Eksekusi Bulk API
**Pertanyaan:** Mengapa pengiriman dokumen satu per satu menggunakan endpoint `POST /<index>/_doc` sangat tidak disarankan untuk throughput tinggi, dan bagaimana mekanisme internal Bulk API (`_bulk`) meminimalkan overhead jaringan dan I/O?

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

* **Overhead Single Document Ingestion:**
  - Setiap request HTTP individual memicu TCP round-trip, parsing HTTP header, alokasi thread pada pool HTTP server, autentikasi/otorisasi ulang, resolusi routing shard, write lock, dan lucene indexing synchronization. Hal ini menyebabkan IOPS disk dan CPU thrashing pada koneksi jaringan.
* **Optimasi Bulk API:**
  - Format payload NDJSON (Newline Delimited JSON) memungkinkan node koordinator Elasticsearch membaca metadata baris pertama (`action_and_meta_data`), menentukan shard target tanpa perlu mem-parsing seluruh isi body dokumen di memory sekaligus.
  - Koordinator mengelompokkan (bucket) payload berdasarkan primary shard pemilik data, lalu meneruskan batch request tersebut secara paralel via TCP inter-node internal (port 9300) ke masing-masing data node target.
  - Mengurangi latency per-dokumen secara eksponensial, meningkatkan IO utilization, dan memungkinkan flush segmen disk yang jauh lebih efisien.
</details>

---

### Pertanyaan 3: Grok vs Dissect Processor
**Pertanyaan:** Pada Ingest Pipeline Elasticsearch, apa perbedaan performa dan cara kerja antara `grok` processor dan `dissect` processor saat mem-parsing log semi-terstruktur? Kapan kita wajib beralih ke `grok`?

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

* **Dissect Processor:**
  - Menggunakan pencocokan string berbasis delimitasi/pola pemisah tetap (pattern matching by delimiters), tanpa menggunakan Regular Expression engine.
  - Karakteristik performa: Sangat cepat (mendekati zero CPU overhead overhead dibandingkan Regex), deterministik, dan hemat memori.
  - Keterbatasan: Pola log harus memiliki struktur posisi yang konsisten dan pemisah delimiter yang stabil.
* **Grok Processor:**
  - Berbasis regular expression library (Oniguruma Regex) yang mencocokkan pattern kompleks (`%{IP}`, `%{TIMESTAMP_ISO8601}`, dll.).
  - Menggunakan komputasi CPU intensif dan berisiko mengalami *catastrophic backtracking* jika regex tidak dioptimasi dengan anchor (`^` dan `$`).
* **Kapan Wajib Grok:**
  - Ketika log memiliki struktur tidak seragam (misal variasi format stacktrace, opsional token di tengah string log, multi-format timestamp dalam satu jenis file log) yang tidak dapat dipisahkan secara kaku dengan delimiter statis.
</details>

---

### Pertanyaan 4: Peran Setting `refresh_interval` Selama Bulk Indexing
**Pertanyaan:** Mengapa mengubah parameter index `refresh_interval` menjadi `-1` atau durasi panjang (misal `30s` atau `60s`) dapat meningkatkan throughput ingestion secara dramatis?

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

* **Mekanisme Refresh:**
  - Secara default, Elasticsearch menjalankan proses `refresh` setiap `1s` (`index.refresh_interval: "1s"`). Refresh memindahkan data dari in-memory buffer indexing ke OS page cache untuk menghasilkan immutable Lucene segment baru agar dokumen berstatus *searchable* (near real-time search).
  - Segment yang dibuat tiap detik berukuran sangat kecil, memicu disk I/O konstan dan memaksa background Lucene segment merge bekerja tanpa henti.
* **Dampak `refresh_interval: -1`:**
  - Menghentikan pembentukan Lucene segment periodik. Data tetap berada di memory buffer dan translog menjamin durabilitas (crash recovery).
  - Pembentukan segmen hanya terjadi saat buffer memori penuh (`indices.memory.index_buffer_size`) atau saat di-flush eksplisit. Hal ini menghasilkan segmen besar yang terorganisir rapi, meminimalkan frekuensi merge, dan mengalokasikan siklus CPU/Disk I/O murni untuk penulisan throughput data mentah.
</details>

---

### Pertanyaan 5: Error HTTP 429 (Too Many Requests) dan Thread Pool Rejection
**Pertanyaan:** Apa penyebab teknis utama munculnya response HTTP `429 Too Many Requests` (`es_rejected_execution_exception`) saat proses ingestion, dan bagaimana client application harus menanganinya?

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

* **Penyebab Teknis:**
  - Pada node Elasticsearch, operasi indexing dialokasikan ke `write` thread pool. Thread pool ini memiliki kapasitas worker thread tetap (umumnya sejumlah core CPU) dan dibackup oleh sebuah memory queue (default: 10.000 tasks).
  - Jika downstream data node tidak sanggup menulis ke disk/Lucene secepat data yang dikirim client (disk saturation atau CPU throttling), antrean `write` thread pool akan penuh. Begitu antrean mencapai batas maksimum, Elasticsearch menolak task baru dengan error `429` / `es_rejected_execution_exception`.
* **Strategi Penanganan Client:**
  - Client dilarang menghentikan total pipeline atau sebaliknya melakukan retry agresif tanpa jeda (thundering herd problem).
  - Wajib menerapkan algoritma **Exponential Backoff with Jitter** (misal delay 200ms, 400ms, 800ms + random offset).
  - Menurunkan konkurensi producer worker thread atau memperkecil ukuran batch Bulk payload (misalnya dari 15MB ke 5MB per batch).
</details>

---

## Bagian 2: Intermediate Questions (5 Soal Arsitektur & Analisis)

### Pertanyaan 6: Mekanisme Failover dan `on_failure` dalam Ingest Pipeline
**Pertanyaan:** Sebuah Ingest Pipeline gagal mem-parsing dokumen karena field `timestamp` memiliki format korup atau field `ip_address` tidak valid. Bagaimana arsitektur penanganan error tingkat pipeline agar dokumen tidak langsung dibuang (*dropped*) dan cluster tidak menolak seluruh batch bulk request?

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

* **Konfigurasi `on_failure` pada Pipeline/Processor Level:**
  Ingest node menyediakan handler `on_failure` yang dapat disematkan pada masing-masing processor ataupun di root pipeline level.
* **Arsitektur Fallback & Tagging:**
  1. Jangan biarkan pipeline melempar unhandled exception yang akan menggagalkan status indexing dokumen pada response Bulk item.
  2. Gunakan `on_failure` block untuk:
     - Mengisi field penanda, misalnya `error.message: "{{_ingest.on_failure_message}}"`.
     - Menyimpan processor yang gagal: `error.processor_type: "{{_ingest.on_failure_processor_type}}"`.
     - Mengalihkan target penulisan ke dead-letter index khusus menggunakan processor `set` pada field metadata `_index` (contoh: `_index: "dead-letter-logs"`).
     - Menyimpan payload asli tanpa transformasi ke dalam field `raw_payload`.
  3. Dengan pola ini, batch indexing tetap mengembalikan HTTP 200/partial success, dokumen gagal tetap terarsip untuk audit/reprocessing, dan monitoring pipeline dapat mendeteksi spike pada field `error.message`.
</details>

---

### Pertanyaan 7: Balancing Batch Size vs Concurrent Clients pada Bulk API
**Pertanyaan:** Mengapa menentukan batch size Bulk API berdasarkan jumlah dokumen (misal 5.000 dokumen) sering kali berisiko di lingkungan heterogen, dan mengapa metrik ukuran payload byte (misal 5MB - 15MB) serta konkurensi thread client menjadi parameter yang jauh lebih terukur?

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

* **Risiko Penghitungan Berbasis Jumlah Dokumen:**
  - Dokumen heterogen memiliki variasi ukuran ekstrem. 5.000 dokumen log akses mikro (100 byte/dokumen) setara dengan ~500 KB, sedangkan 5.000 dokumen payload e-commerce atau audit trace lengkap (50 KB/dokumen) setara dengan ~250 MB.
  - Batch 250 MB dalam satu HTTP request akan memicu spike alokasi memory heap JVM, socket timeout, dan berpotensi memicu Circuit Breaker exception (`parent` atau `request` breaker).
* **Standar Berbasis Byte Payload:**
  - Praktik standar industri mengunci bulk payload pada rentang **5 MB hingga 15 MB per request**, terlepas dari apakah itu berisi 100 dokumen atau 10.000 dokumen.
* **Konkurensi Thread:**
  - Jumlah koneksi paralel client idealnya disesuaikan dengan formula: `2 * jumlah_primary_shards` atau proporsional dengan alokasi CPU core target data node. Melebihi batas konkurensi hanya akan membebani context switching pada kernel OS dan memicu penolakan antrean thread pool.
</details>

---

### Pertanyaan 8: Arsitektur Message Broker Buffer (Kafka) vs Direct Beats-to-Elasticsearch
**Pertanyaan:** Jelaskan kegagalan arsitektural (single point of contention) yang dapat terjadi jika 10.000 agent Beats mengirim log langsung ke cluster Elasticsearch tanpa perantara message broker seperti Apache Kafka. Analisis alur data dan mekanisme proteksinya!

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

* **Kegagalan Direct Ingestion (10.000 Beats -> Elasticsearch):**
  - **Connection Overload:** Membuka 10.000 koneksi TCP simultan langsung ke node HTTP Elasticsearch menguras file descriptors, socket buffer memory, dan worker HTTP network threads.
  - **Uncontrolled Spikes:** Ketika terjadi lonjakan traffic (traffic surge atau downtime pemulihan aplikasi), seluruh agent akan membanjiri cluster serentak. Elasticsearch tidak memiliki native persistent buffer; akibatnya node mengalami resource starvation, garbadge collection pause panjang, dan response 429 massal yang menyebabkan hilangnya log pada edge agent yang kehabisan local disk spooling.
* **Arsitektur Message Broker (Beats -> Kafka -> Logstash/Consumer -> Elasticsearch):**
  - **Decoupling Rate:** Kafka bertindak sebagai resilient persistent shock absorber (buffer). Edge client menulis ke Kafka secara append-only dengan throughput disk linear.
  - **Controlled Pull Mechanism:** Consumer (Logstash atau Ingest Worker) menarik data dari Kafka menggunakan model pull sesuai kapasitas pemrosesan real-time cluster Elasticsearch.
  - **Zero Data Loss:** Jika Elasticsearch mengalami maintenance, rolling upgrade, atau rebalancing shard, Kafka menahan pesan selama rentang retention time tanpa membebani memori Elasticsearch.
</details>

---

### Pertanyaan 9: Pipeline Execution Overhead & Script Processor Pitfalls
**Pertanyaan:** Mengapa penggunaan `script` processor (Painless) di dalam Ingest Pipeline harus diminimalkan, dan bagaimana optimasi pemrosesan field string sebaiknya didelegasikan ke native processor atau Logstash?

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

* **Overhead Painless Script Processor:**
  - Meskipun Painless dikompilasi secara dinamis menjadi bytecode Java, eksekusi script untuk setiap dokumen menambahkan instruksi interpreter layer dan overhead CPU cycle signifikan.
  - Script processor yang mengakses konteks `ctx` secara dinamis mencegah optimasi memory allocation native C++/Java yang ada pada dedicated processors (seperti `split`, `join`, `rename`, `convert`).
* **Best Practice:**
  - Selalu gunakan native processor jika fiturnya tersedia (misal: gunakan processor `date` untuk manipulasi waktu, `convert` untuk type-casting, `gsub` untuk replace string sederhana).
  - Jika logika transformasi melibatkan loop branching nested, lookup tabel kompleks, atau validasi matematika rumit, delegasikan pekerjaan tersebut ke ETL eksternal (Logstash / Kafka Streams / Apache Flink) sebelum payload mencapai pintu masuk Elasticsearch Ingest Node.
</details>

---

### Pertanyaan 10: Routing Key dan Dampaknya pada Ingest Throughput
**Pertanyaan:** Bagaimana penentuan Custom Routing (`_routing`) mempengaruhi throughput ingestion pada cluster dengan multi-shard? Apa trade-off antara indexing throughput dan search performance?

<details>
<summary><b>Jawaban & Pembahasan Teknis</b></summary>

* **Dampak terhadap Ingestion Throughput:**
  - Tanpa custom routing, Elasticsearch menggunakan hash dari `_id` (`murmur3(_id) % number_of_shards`), sehingga dokumen dari bulk request terdistribusi secara seragam (*uniform balance*) ke seluruh primary shard dan data node di cluster. Seluruh node berkontribusi memproses IOPS disk secara merata.
  - Dengan custom routing (misal berdasarkan `tenant_id` atau `user_id`), semua dokumen dengan routing key yang sama akan dipaksa masuk ke satu shard spesifik. Jika terjadi bulk injection besar untuk satu tenant, satu data node akan mengalami *hotspotting* (CPU & disk IO 100%), sementara node lain menganggur (*idle*). Ini menurunkan total cluster write throughput.
* **Trade-off Search Performance:**
  - Custom routing mempercepat query secara dramatis karena pencarian cukup diarahkan ke 1 shard target (single-shard execution), mengeliminasi scatter-gather query overhead.
  - Kesimpulan: Gunakan custom routing hanya jika kebutuhan query concurrency ultra-tinggi menuntut eliminasi scatter-gather, dan pastikan cardinalitas key cukup tinggi untuk mencegah unbalance shard distribution.
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Real-World Case Studies)

---

### Skenario 1: Incident Respon - Bad Grok Pattern Membakar CPU Cluster Ingest
**Konteks Lingkungan:**
Sebuah cluster log analytics memproses 40.000 log events/detik dari ribuan microservice. Tim DevOps baru saja merilis Ingest Pipeline baru untuk parsing log HTTP gateway menggunakan pattern grok khusus:
`%{GREEDYDATA:client_ip} \[%{DATA:timestamp}\] "%{WORD:method} %{GREEDYDATA:endpoint}" %{NUMBER:status}`

**Gejala Masalah:**
1. CPU utilization pada seluruh Ingest Nodes melonjak ke 100% seketika setelah pipeline diaktifkan.
2. HTTP Bulk indexing latency melonjak dari 50ms menjadi 18.000ms.
3. Client microservice mengalami connection timeout dan cascade crash akibat socket backlog.

**Analisis Akar Masalah:**
- Pattern Grok menggunakan quantifier `%{GREEDYDATA}` (yang merupakan alias regex `.*`) secara berulang di awal dan di tengah pola string tanpa pembatas yang kaku.
- Ketika ada request masuk dengan format log malformed (misalnya request URL abnormal yang terpotong tanpa status code), regex engine Oniguruma mengalami **Catastrophic Backtracking**.
- Algoritma mencoba jutaan permutasi kombinasi karakter mundur (backtracking) untuk mencocokkan pattern dengan string, mengonsumsi seluruh siklus CPU core untuk satu dokumen log.

**Solusi & Remediasi Arsitektur:**
1. **Immediate Action:** Nonaktifkan sementara pipeline via update API atau ubah pipeline default index ke `noop` pipeline.
2. **Refactoring Pattern:**
   - Ubah ke `dissect` processor jika format delimiter statis:
     `pattern: "%{client_ip} [%{timestamp}] \"%{method} %{endpoint}\" %{status}"`
   - Jika tetap memerlukan grok, pasang anchor regex (`^` di awal dan `$` di akhir) serta ganti token general `GREEDYDATA` dengan pattern spesifik:
     `^%{IP:client_ip} \[%{DATA:timestamp}\] "%{WORD:method} %{NOTSPACE:endpoint} HTTP/%{NUMBER:http_version}" %{INT:status:int}`
3. Tambahkan setting `timeout: 100ms` pada grok processor agar jika terjadi backtracking, eksekusi diputus paksa dan dokumen dialihkan ke handler `on_failure`.

---

### Skenario 2: Bulk Throttling & 429 Storm Pasca Maintenance Network
**Konteks Lingkungan:**
Sebuah platform perbankan menggunakan Kafka dengan 3 broker dan Logstash consumer cluster yang mengalirkan data transaksi ke Elasticsearch cluster (6 Data Nodes, NVMe SSD). Setelah maintenance jaringan internal selama 2 jam, konektivitas pulih.

**Gejala Masalah:**
1. Logstash log dipenuhi error:
   `[ERROR][logstash.outputs.elasticsearch] Retrying failed action [status: 429, action: ["index", ...]] es_rejected_execution_exception[rejected execution on coordinator]`
2. Data lag pada Kafka consumer group membengkak hingga puluhan juta pesan dan tidak berkurang selama berjam-jam.
3. CPU Elasticsearch data node fluktuatif antara 90-100%, disk write IOPS jenuh.

**Analisis Akar Masalah:**
- Selama jeda 2 jam, data tertumpuk di Kafka topic. Begitu jaringan online, Logstash secara serentak membuka ratusan worker thread dan menyemburkan batch bulk data tanpa batas kecepatan (*burst rate*).
- Elasticsearch data node mengalami double bottleneck:
  1. Primary shard sedang melakukan heavy Lucene indexing.
  2. Index replica diatur ke `number_of_replicas: 2`, sehingga setiap write harus di-replikasi via jaringan internal ke dua node lain secara sinkron sebelum mengembalikan status ACK.
  3. `refresh_interval` aktif di default `1s`, memicu segment merge storm secara terus-menerus.
  4. Antrean `write` thread pool (10.000) meluap, memicu reject 429. Logstash default retry membanjiri request baru yang memperparah congestion collapse.

**Solusi & Remediasi Arsitektur:**
1. **Peredaman Logstash Ingestion Rate:**
   Turunkan parameter Logstash output batch size dan worker:
   - Atur `pipeline.batch.size: 2500` (atau setara ~8-10MB).
   - Batasi `pipeline.workers` agar sesuai kapasitas write thread target cluster.
2. **Tuning Parameter Index Elasticsearch Selama Catch-Up Phase:**
   Eksekusi update dynamic settings pada indeks aktif:
   ```json
   PUT /transaksi-active/_settings
   {
     "index": {
       "refresh_interval": "-1",
       "number_of_replicas": 0
     }
   }
   ```
3. **Hasil:** Throughput melonjak hingga 4x lipat. Lag Kafka berkurang dari 30 juta menjadi 0 dalam waktu 40 menit.
4. **Post-Remediasi:** Kembalikan konfigurasi normal saat lag sudah tuntas:
   ```json
   PUT /transaksi-active/_settings
   {
     "index": {
       "refresh_interval": "10s",
       "number_of_replicas": 1
     }
   }
   ```
   Lakukan force merge jika indeks beralih menjadi read-only.

---

### Skenario 3: Data Loss Akibat Dynamic Mapping Explosion pada Payload Unsanitized
**Konteks Lingkungan:**
Perusahaan aggregator log mengumpulkan error trace dari aplikasi JavaScript frontend menggunakan Filebeat dan Ingest Pipeline ke dalam index harian `frontend-logs-YYYY.MM.DD`. Dynamic mapping dibiarkan aktif secara default (`dynamic: true`).

**Gejala Masalah:**
1. Pengiriman data log berhenti total pada jam 14:00.
2. Master node Elasticsearch memancarkan warning:
   `Limit of total fields [1000] in index [frontend-logs-2026.10.05] has been exceeded`
3. Seluruh payload baru yang memuat field belum terdaftar ditolak mentah-mentah dengan status HTTP 400 Bad Request, menyebabkan ribuan client mendrop log penting.

**Analisis Akar Masalah:**
- Tim pengembang aplikasi frontend merilis update yang memasukkan raw JavaScript user-session context ke dalam body log. Context ini berisi dynamic JSON key berupa query parameter URL acak dan dynamic key-value pairs (misal: `param_session_id_xyz`, `uuid_12345`).
- Elasticsearch secara otomatis memetakan setiap key baru sebagai field tersendiri di cluster metadata (*Mapping Explosion*). Begitu jumlah field mencapai limit default 1000 field (`index.mapping.total_fields.limit`), cluster menolak pembuatan field baru untuk mencegah kehabisan heap memory pada master node.

**Solusi & Remediasi Arsitektur:**
1. **Proteksi Mapping Dinamis:**
   Ubah template index untuk menetapkan `dynamic: false` atau `dynamic: runtime` pada nested parameter konteks yang rawan variasi key dinamis.
2. **Sanitasi di Layer Ingest Pipeline:**
   Pasang Ingest Pipeline yang mengekstrak metadata arbitrary ke format tipe data `flattened`:
   - Tipe data `flattened` memperlakukan seluruh pohon JSON leaf nodes sebagai string flat tunggal tanpa mengurai masing-masing field menjadi Lucene inverted index independen.
3. **Simulasi Konfigurasi Pipeline Sanitisasi:**
   Gunakan script/set processor untuk memindahkan objek dinamis ke parent `context_attributes` yang sudah dimapping sebagai type `flattened` di index template, atau hapus field bertipe noise menggunakan processor `remove` dengan pattern regex ignore.

---

## Bagian 4: Practical Chapter Challenge

### Judul Challenge: Production Ingest Pipeline & Resilient Bulk Ingestion Engine
**Tujuan:**
Membangun pipeline ingestion terintegrasi di Elasticsearch yang mencakup:
1. Ingest Pipeline dengan parsing multi-kondisi, error handling, metadata enrichment, dan fallback mechanism.
2. Index Template yang dioptimalkan untuk performa write tinggi.
3. Simulasi pengiriman data bulk batch via NDJSON.

---

### Langkah 1: Buat Index Template dengan Setting High-Throughput Write

Buat index template untuk menangani indeks berseri `app-events-*` dengan tuning buffer write optimal:

```http
PUT _index_template/app_events_template
{
  "index_patterns": ["app-events-*"],
  "template": {
    "settings": {
      "number_of_shards": 2,
      "number_of_replicas": 0,
      "index.refresh_interval": "30s",
      "index.translog.durability": "async",
      "index.translog.sync_interval": "15s",
      "index.translog.flush_threshold_size": "512mb"
    },
    "mappings": {
      "dynamic": "strict",
      "properties": {
        "@timestamp": { "type": "date" },
        "service": {
          "properties": {
            "name": { "type": "keyword" },
            "version": { "type": "keyword" }
          }
        },
        "http": {
          "properties": {
            "method": { "type": "keyword" },
            "status_code": { "type": "short" },
            "path": { "type": "keyword" },
            "duration_ms": { "type": "float" }
          }
        },
        "client": {
          "properties": {
            "ip": { "type": "ip" }
          }
        },
        "error": {
          "properties": {
            "message": { "type": "text" },
            "failed_processor": { "type": "keyword" },
            "raw_payload": { "type": "text", "index": false }
          }
        },
        "ingest_timestamp": { "type": "date" }
      }
    }
  }
}
```

---

### Langkah 2: Buat Ingest Pipeline dengan Fallback & Enrichment

Pipeline ini harus:
1. Menambahkan timestamp saat dokumen masuk cluster (`ingest_timestamp`).
2. Mem-parsing string log mentah (`raw_message`) menggunakan `dissect` processor.
3. Melakukan type conversion (`status_code` ke short, `duration_ms` ke float).
4. Menghapus field `raw_message` setelah parsing sukses untuk menghemat storage.
5. Menampung error jika format `raw_message` cacat ke dalam object `error` tanpa membatalkan indexing.

```http
PUT _ingest/pipeline/app_events_pipeline
{
  "description": "Pipeline tangguh untuk parsing HTTP access events dengan error capture",
  "processors": [
    {
      "set": {
        "field": "ingest_timestamp",
        "value": "{{{_ingest.timestamp}}}"
      }
    },
    {
      "dissect": {
        "field": "raw_message",
        "pattern": "%{client.ip} [%{service.name}:%{service.version}] \"%{http.method} %{http.path}\" %{http.status_code} %{http.duration_ms}",
        "ignore_missing": false
      }
    },
    {
      "convert": {
        "field": "http.status_code",
        "type": "short"
      }
    },
    {
      "convert": {
        "field": "http.duration_ms",
        "type": "float"
      }
    },
    {
      "remove": {
        "field": "raw_message"
      }
    }
  ],
  "on_failure": [
    {
      "set": {
        "field": "error.message",
        "value": "{{_ingest.on_failure_message}}"
      }
    },
    {
      "set": {
        "field": "error.failed_processor",
        "value": "{{_ingest.on_failure_processor_type}}"
      }
    },
    {
      "set": {
        "field": "error.raw_payload",
        "value": "{{raw_message}}"
      }
    },
    {
      "remove": {
        "field": "raw_message",
        "ignore_missing": true
      }
    }
  ]
}
```

---

### Langkah 3: Eksekusi Ingestion Menggunakan Bulk API (Simulasi NDJSON)

Kirimkan batch berikut ke endpoint `POST /app-events-2026.10.05/_bulk?pipeline=app_events_pipeline`:

```http
POST /app-events-2026.10.05/_bulk?pipeline=app_events_pipeline
{ "index": { "_id": "evt-001" } }
{ "@timestamp": "2026-10-05T14:30:00Z", "raw_message": "192.168.1.50 [payment-service:v2.1.0] \"POST /api/v1/charge\" 201 145.2" }
{ "index": { "_id": "evt-002" } }
{ "@timestamp": "2026-10-05T14:30:01Z", "raw_message": "10.0.0.12 [auth-service:v1.0.4] \"GET /api/v1/verify\" 200 12.8" }
{ "index": { "_id": "evt-003" } }
{ "@timestamp": "2026-10-05T14:30:02Z", "raw_message": "MALFORMED_LOG_STRING_WITHOUT_PROPER_DELIMITERS" }
```

---

### Langkah 4: Verifikasi Hasil Evaluasi

1. **Cek Dokumen Sukses:**
   Pastikan `evt-001` memiliki field `http.status_code: 201`, `client.ip: "192.168.1.50"`, dan tidak memiliki field `raw_message`.
2. **Cek Dokumen Fallback (Failure Handling):**
   Pastikan `evt-003` tetap terindeks, dengan atribut:
   - `error.failed_processor`: `"dissect"`
   - `error.raw_payload`: `"MALFORMED_LOG_STRING_WITHOUT_PROPER_DELIMITERS"`
   - Status indexing tidak menghasilkan error fatal pada sisi cluster.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan daftar periksa ini untuk mengevaluasi kesiapan arsitektural pipeline Anda sebelum melangkah ke bab berikutnya:

- [ ] **Karakteristik Node Ingest:** Memahami bahwa node dengan role `ingest` membutuhkan alokasi CPU yang memadai dan tidak boleh mengorbankan memory heap master node.
- [ ] **Proses Parsing Optimal:** Mampu memutuskan kapan harus menggunakan `dissect` vs `grok`, serta memahami bahaya regex backtracking tak berbatas.
- [ ] **Pola Error Resiliency:** Selalu memasang blok `on_failure` di level pipeline atau processor agar tidak terjadi silent drop atau unhandled reject pada payload.
- [ ] **Manajemen Batching:** Mengerti parameter batching Bulk API berdasarkan payload volume (5MB - 15MB) daripada sekadar kuantitas dokumen mentah.
- [ ] **Mitigasi 429 & Backpressure:** Memahami fungsi exponential backoff pada client application dan pengaruh `refresh_interval`, `number_of_replicas`, serta `translog` durability terhadap write throughput.
- [ ] **Isolasi Buffer (Broker):** Mampu mengidentifikasi skenario di mana message broker (Kafka/RabbitMQ) wajib diletakkan sebelum Elasticsearch untuk meredam surge traffic.
- [ ] **Mapping Discipline:** Memahami proteksi index mapping dari *dynamic field explosion* menggunakan `dynamic: strict`, `dynamic: false`, atau tipe data `flattened`.
