# Kurikulum Enterprise Elasticsearch: Rekayasa Data & Arsitektur Mesin Pencari
## BAB 03: Data Ingestion Pipeline Architecture
### MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang dan mengimplementasikan** arsitektur *ingest node* terdedikasi (*dedicated ingest nodes*) untuk mengisolasi beban komputasi ETL dari operasi *indexing* dan *search*.
- **Mengembangkan** *ingest pipeline* kompleks dengan *processors* tingkat lanjut (`enrich`, `script`/Painless, `dissect`, `grok`, `pipeline`) dilengkapi penanganan kesalahan (*error handling*) dan percabangan kondisional yang tangguh (*robust*).
- **Mengoptimalkan** performa *enrichment engine* in-memory Elasticsearch menggunakan *enrich policy* (`match`, `range`, `geo_match`) untuk deduplikasi dan agregasi data saat *ingestion*.
- **Menganalisis dan memitigasi** *backpressure* data pipeline menggunakan konfigurasi buffer eksternal (Apache Kafka/Logstash) serta tuning ukuran *bulk request*, *write thread pool*, dan *circuit breakers*.
- **Mendiagnosis dan mengurai** kegagalan pipeline produksi secara langsung menggunakan *Simulate Pipeline API*, *Node Ingest Statistics*, dan *Dead Letter Queue* (DLQ) pattern.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Bab 01 & 02**: Arsitektur internal Elasticsearch (Node Roles, Index Sharding, Lucene Segment, Translog, Refresh & Flush lifecycle).
- **Pemahaman Protokol HTTP & REST API**: Penggunaan cURL, payload JSON, dan HTTP status codes (khususnya penanganan `429 Too Many Requests`).
- **Sistem Operasi & JVM**: Manajemen alokasi JVM Heap (`Xmx`, `Xms`), swap behavior, dan File Descriptors pada Linux.
- **Konsep Dasar Streaming/Pipelining**: Memahami konsep *producers*, *consumers*, *at-least-once delivery*, dan *idempotency*.

---

### 3. Concept & Internal Architecture

#### Ingest Node Execution Model
Secara default, setiap node Elasticsearch memiliki role `ingest` aktif (`node.roles: [ ingest ]`). Namun, pada lingkungan skala enterprise, membiarkan node data (*data nodes*) mengeksekusi pipeline merupakan anti-pattern fatal.

Ketika sebuah dokumen masuk melalui REST API via endpoint `/_bulk` atau `/<index>/_doc` yang mengarah ke sebuah pipeline:
1. **HTTP Layer Demuxing**: REST handler mendeteksi query parameter `pipeline=my-pipeline`. Dokumen didekodekan dari JSON mentah ke representasi memori (`Map<String, Object>`).
2. **Ingest Thread Pool Dispatching**: Tugas transformasi diserahkan ke *Ingest Thread Pool*. Thread pool ini bertipe `fixed`, dengan ukuran default sama dengan jumlah `available_processors`.
3. **Sequential Processor Pipeline**: Dokumen melewati rantai prosesor secara berurutan. Setiap prosesor memodifikasi peta memori dokumen (*in-place mutation*).
4. **Target Shard Routing**: Setelah lolos prosesor terakhir, dokumen diproses oleh komponen *index routing* (menghitung `hash(_routing) % number_of_primary_shards`).
5. **Write Thread Pool Offloading**: Ingest node bertindak sebagai *coordinating node*, meneruskan dokumen yang sudah tertransformasi ke *Data Node* pemegang *Primary Shard* terkait, menggunakan internal Transport Client (port 9300). Pada node data, dokumen masuk ke *Write Thread Pool*.

```
[Client App]
     │
     ▼ HTTP POST /_bulk?pipeline=telemetry-pipeline
┌────────────────────────────────────────────────────────┐
│ Dedicated Ingest Node (node.roles: [ingest])          │
│                                                        │
│  [HTTP Thread Pool]                                    │
│        │                                               │
│        ▼                                               │
│  [Ingest Thread Pool]                                  │
│        │                                               │
│   ┌────┴─────────────────────────────────────────┐     │
│   │ Pipeline: telemetry-pipeline                 │     │
│   │ ├─ Process 1: Dissect / Grok                 │     │
│   │ ├─ Process 2: Enrich Policy (Cache Lookup)   │     │
│   │ ├─ Process 3: Script (Painless Context)      │     │
│   │ └─ Process 4: Drop / Tag Condition           │     │
│   └────┬─────────────────────────────────────────┘     │
│        │ Document Mutated In-Memory                    │
│        ▼                                               │
│  [Routing Engine] ──(Transport Port 9300)──────┐       │
└────────────────────────────────────────────────┼───────┘
                                                 │
          ┌──────────────────────────────────────┴───────────────────────────────────┐
          │                                                                          │
          ▼                                                                          ▼
┌─────────────────────────────────────────┐                ┌─────────────────────────────────────────┐
│ Data Node 01 (node.roles: [data_hot])   │                │ Data Node 02 (node.roles: [data_hot])   │
│                                         │                │                                         │
│  [Write Thread Pool]                    │                │  [Write Thread Pool]                    │
│        │                                │                │        │                                │
│        ▼                                │                │        ▼                                │
│   Primary Shard [idx-0]                 │                │   Primary Shard [idx-1]                 │
│   (Indexing Buffer -> Translog)         │                │   (Indexing Buffer -> Translog)         │
└─────────────────────────────────────────┘                └─────────────────────────────────────────┘
```

#### Enrich Processor Architecture
*Enrich Processor* menyelesaikan masalah klasik distributed search: ketiadaan operasi *SQL-like join* yang cepat pada saat *write*. Mekanisme internalnya adalah:
- **Source Indexing**: Data master (misal: data identitas pelanggan, master IP CIDR, fraud blacklist) dimasukkan ke sebuah *source index*.
- **Enrich Policy Execution**: Saat dieksekusi via `_enrich/policy/<name>/_execute`, Elasticsearch membuat sistem indeks read-only yang sangat teroptimasi (`.enrich-*`).
- **In-Memory Shard Cache**: Indeks sistem `.enrich-*` didesain untuk pencarian berbasis *exact-match* atau *range* berkecepatan tinggi, memanfaatkan filesystem cache OS dan off-heap segment memory.
- **Pipeline Interception**: Saat dokumen mengalir melalui pipeline, Enrich Processor mengambil field kunci (misal: `account_id`), melakukan pencarian internal ke `.enrich-*`, dan menggabungkan (*merge*) field referensi ke dokumen utama secara atomik.

#### Painless Script Compilation & Security Sandbox
Setiap blok script dalam processor `script` dikompilasi menggunakan engine **Painless**:
- **Stateless Compilation**: Painless dikompilasi langsung ke Java bytecode runtime untuk performa eksekusi mendekati kode native Java.
- **Compilation Limit**: Elasticsearch menerapkan sirkuit batas kompilasi script (default: `script.max_compilations_rate = 150/5m`). Menggunakan script dengan string concatenation yang dinamis akan memicu *compilation circuit breaker* dan menolak request. Anda **wajib** menggunakan parameter `params` terpisah agar skrip terkompilasi satu kali dan digunakan berulang (*cached AST*).
- **Whitelisted API**: Painless dieksekusi di dalam Java Security Manager (JSM) sandbox ketat. Operasi I/O, network socket, class-loading arbitrari, dan threading diblokir sepenuhnya pada level kernel JVM.

---

### 4. Why & What

| Fitur / Arsitektur | What (Definisi & Karakteristik) | Why (Alasan Rekayasa & Justifikasi) |
| :--- | :--- | :--- |
| **Dedicated Ingest Node** | Node cluster dengan konfigurasi `node.roles: [ ingest ]` tanpa role `data` atau `master`. | Memisahkan beban CPU-heavy (ekspresi reguler Grok, serialisasi/deserialisasi JSON, Painless) agar tidak mencuri alokasi CPU dan JVM heap milik *Data Nodes* yang melayani I/O disk dan komputasi search query. |
| **Ingest Pipeline** | Rangkaian task transformasi data deklaratif yang berjalan *natively* di dalam core Elasticsearch. | Menghilangkan kompleksitas deployment dan pemeliharaan kluster eksternal (seperti armada server Logstash) jika transformasi yang dibutuhkan berada pada kategori ringan hingga moderat. |
| **Enrich Processor** | Mekanisme *join-at-ingest-time* untuk denormalisasi dokumen secara otomatis. | Pencarian Elasticsearch sangat cepat pada data terdenormalisasi. Melakukan operasi *lookup* saat ingest menjamin latensi pencarian (*read query*) tetap deterministik di angka milidetik rendah. |
| **Painless Scripting** | Bahasa skrip internal Elasticsearch berbasis subset sintaksis Java/Groovy. | Memberikan fleksibilitas logika mutasi data kustom (kalkulasi bisnis tingkat lanjut, regex custom, manipulation of deep nested JSON) tanpa perlu mengompilasi plugin Java kustom. |
| **Fail-on-Error Isolation** | Blok `on_failure` pada level pipeline dan level per-processor. | Mencegah sebuah payload bulk multi-megabyte ditolak sepenuhnya hanya karena terdapat satu dokumen anomali dengan tipe data rusak (*poison pill*). |

---

### 5. How (Workflow Detail)

Alur kerja arsitektur pemrosesan data pipeline tingkat enterprise:

```
[Client / Log Producer]
       │
       ▼
[Kafka Queue / Buffer]
       │
       ▼
[Consumer / Ingestion Worker]
       │
       │ HTTP POST /_bulk?pipeline=enterprise_events_v1
       ▼
[Ingest Node Pool]
       │
       ├─► 1. Pipeline Router: Evaluasi pipeline parameter
       │
       ├─► 2. Ingest Processor Execution:
       │      a. Dissect / Grok (Parsing string mentah ke JSON terstruktur)
       │      b. GeoIP & User-Agent (Enrichment metadata jaringan)
       │      c. Enrich Policy Lookup (Match target index `.enrich-customer-data`)
       │      d. Painless Script (Kalkulasi metrik, array mutation, sanitasi PII)
       │
       ├─► 3. Exception Handling:
       │      - Apakah terjadi kegagalan (misal: Grok failure / Type mismatch)?
       │      ├─ [Ya] ──► Lempar ke blok `on_failure` ──► Tagging `_error` & reroute ke index DLQ
       │      └─ [Tidak] ──► Lanjutkan alur normal
       │
       ├─► 4. Index Shard Routing: Evaluasi routing key & hashing shard target
       │
       ▼
[Data Node: Hot Shard]
       │
       ├─► JVM Indexing Buffer ──► Segment Flushing (.cfs, .si)
       └─► Sequential Append to Translog (fsync sesuai durability policy)
```

1. **Ingest Phase Interception**: Request tiba di Ingest Node. Pipeline memvalidasi integritas dokumen dasar.
2. **Structural Normalization**: Processor `dissect` atau `grok` memecah *unstructured string* menjadi field-field bertipe data standar (IP, Timestamp, Float, String).
3. **Contextual Enrichment**: Processor `enrich` menginjeksi konteks bisnis sekunder langsung dari indeks master berbasis memori.
4. **Sanitization & Logic Execution**: Processor `script` menjalankan kode Painless untuk mengaburkan data sensitif (*PII Masking*) dan menghitung field turunan.
5. **Dead-Letter Routing (*Fallback*)**: Jika processor melempar exception (misal: JSON parsing error), execution trap menangkap error tersebut melalui `on_failure`, menyematkan trace error ke dalam dokumen, dan mengarahkan metadata `_index` ke indeks penampung kegagalan (*Dead Letter Index*).
6. **Physical Indexing**: Data yang valid diteruskan ke node data pemegang shard primary dan dituliskan ke memory index buffer serta Translog.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pabrik Perakitan Otomotif Berteknologi Tinggi
Bayangkan proses ingestion ini seperti lini perakitan mobil:
- **Client Producer**: Truk kontainer pengirim material mentah yang tiba di gerbang pabrik.
- **Kafka**: Gudang drop-off sementara yang menampung ribuan komponen agar truk tidak memblokir pintu pabrik ketika lini perakitan sedang padat (*backpressure decoupling*).
- **Dedicated Ingest Node**: Meja perakitan khusus. Di sini, sasis diperiksa, nomor rangka diketok (*grok/dissect*), fitur tambahan dipasang (*enrich processor*), dan cat anti-karat disemprotkan (*Painless script*).
- **On-Failure Processor**: Rel pembelok darurat. Jika sebuah pintu mobil cacat dan tidak pas, mobil tidak merusak konveyor utama; rel darurat membelokkannya ke area karantina (*Dead Letter Queue*) untuk diperiksa inspektur mekanik tanpa menghentikan jalur perakitan utama.
- **Data Nodes**: Gudang penyimpanan akhir beriklim khusus dengan rak baja (*Lucene Segments*) tempat mobil yang sudah jadi diparkir rapi secara permanen.

```
       INGEST PIPELINE COMPONENT ANATOMY
┌─────────────────────────────────────────────────────────────┐
│ Pipeline: "prod-payment-pipeline"                           │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Processors List (Sequential Array)                      │ │
│ │                                                         │ │
│ │ [Processor 1: Set]                                      │ │
│ │   field: "metadata.received_at" = "{{{_ingest.timestamp}}}"│
│ │                                                         │ │
│ │ [Processor 2: Dissect]                                  │ │
│ │   pattern: "%{client_ip} %{http_verb} %{endpoint}"      │ │
│ │                                                         │ │
│ │ [Processor 3: Enrich (Policy: "merchant-enrich-policy")]│ │
│ │   match_field: "merchant_id" -> inject "merchant_profile"│
│ │                                                         │ │
│ │ [Processor 4: Script (Painless Engine)]                 │ │
│ │   logic: if ctx.amount > 10000000 -> ctx.flag = 'HIGH'  │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Error Handling Trap:                                        │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ on_failure:                                             │ │
│ │  ├─ Set: "_index" = "dead-letter-payment-failures"      │ │
│ │  └─ Set: "error.reason" = "{{_ingest.on_failure_message}}"│
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Standard Logging Pipeline
Pipeline dasar yang melakukan parsing string log Nginx, menyematkan IP geolokasi, dan menghapus field sumber.

```json
PUT _ingest/pipeline/nginx_access_simple
{
  "description": "Nginx standard access log parsing",
  "processors": [
    {
      "grok": {
        "field": "message",
        "patterns": ["%{IPORHOST:client_ip} - %{DATA:user_name} \\[%{HTTPDATE:access_time}\\] \"%{WORD:http_method} %{DATA:url} HTTP/%{NUMBER:http_version}\" %{NUMBER:response_code} %{NUMBER:body_sent_bytes}"]
      }
    },
    {
      "date": {
        "field": "access_time",
        "target_field": "@timestamp",
        "formats": ["dd/MMM/yyyy:HH:mm:ss Z"]
      }
    },
    {
      "remove": {
        "field": "message"
      }
    }
  ]
}
```

#### Practical Example: Production-Grade Multi-Tenant Financial Pipeline
Pipeline ini menangani enrichment data transaksi, masking data PII sensitif via Painless, conditional tagging, dan mekanisme `on_failure` routing yang komprehensif.

##### Langkah 1: Setup Master Data & Enrich Policy
```json
// 1. Buat index master merchant
PUT /merchants_master
{
  "mappings": {
    "properties": {
      "merchant_id": { "type": "keyword" },
      "merchant_name": { "type": "keyword" },
      "risk_tier": { "type": "keyword" },
      "settlement_currency": { "type": "keyword" }
    }
  }
}

// 2. Isi master data
POST /merchants_master/_doc/M-001
{
  "merchant_id": "M-001",
  "merchant_name": "Mega Retail Corp",
  "risk_tier": "LOW",
  "settlement_currency": "IDR"
}

// 3. Konfigurasi Enrich Policy
PUT /_enrich/policy/merchant_enrich_policy
{
  "match": {
    "indices": "merchants_master",
    "match_field": "merchant_id",
    "enrich_fields": ["merchant_name", "risk_tier", "settlement_currency"]
  }
}

// 4. Eksekusi Enrich Policy untuk kompilasi index internal .enrich-*
POST /_enrich/policy/merchant_enrich_policy/_execute
```

##### Langkah 2: Pipeline Lanjutan dengan Painless Scripting dan Fail Handler
```json
PUT /_ingest/pipeline/fintech_transaction_v1
{
  "description": "Enterprise-grade financial transactions pipeline with enrichment and PII sanitization",
  "processors": [
    {
      "set": {
        "field": "_source.pipeline_metadata.ingested_at",
        "value": "{{{_ingest.timestamp}}}"
      }
    },
    {
      "enrich": {
        "policy_name": "merchant_enrich_policy",
        "field": "merchant_id",
        "target_field": "merchant_info",
        "ignore_missing": false
      }
    },
    {
      "script": {
        "description": "Sanitize CC Number and Calculate Risk Factor via Painless",
        "lang": "painless",
        "source": """
          // 1. PII Masking: Redact card number leaving last 4 digits
          if (ctx.containsKey('card_number') && ctx.card_number != null) {
            String cc = ctx.card_number.toString();
            if (cc.length() >= 16) {
              ctx.card_masked = '****-****-****-' + cc.substring(cc.length() - 4);
              ctx.remove('card_number');
            }
          }

          // 2. High-value Fraud Detection Tagging
          if (ctx.containsKey('amount_cents') && ctx.amount_cents != null) {
            long amount = ctx.amount_cents;
            // Lookup risk tier from enriched object
            String riskTier = 'UNKNOWN';
            if (ctx.containsKey('merchant_info') && ctx.merchant_info.containsKey('risk_tier')) {
              riskTier = ctx.merchant_info.risk_tier;
            }
            
            if (amount > params.threshold_cents && riskTier == 'HIGH') {
              ctx.fraud_review_required = true;
              ctx.tags.add('HIGH_RISK_TX');
            } else {
              ctx.fraud_review_required = false;
            }
          }
        """,
        "params": {
          "threshold_cents": 500000000
        }
      }
    },
    {
      "drop": {
        "description": "Drop heartbeat synthetic health checks",
        "if": "ctx.containsKey('transaction_type') && ctx.transaction_type == 'HEALTH_CHECK'"
      }
    }
  ],
  "on_failure": [
    {
      "set": {
        "description": "Tag failed documents",
        "field": "processing_error.status",
        "value": "FAILED"
      }
    },
    {
      "set": {
        "field": "processing_error.message",
        "value": "{{_ingest.on_failure_message}}"
      }
    },
    {
      "set": {
        "field": "processing_error.processor_type",
        "value": "{{_ingest.on_failure_processor_type}}"
      }
    },
    {
      "set": {
        "description": "Reroute invalid payload to dead letter index",
        "field": "_index",
        "value": "failed-transactions-dlq"
      }
    }
  ]
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario Kasus
- **Perusahaan**: Payment Gateway Nasional (PT Finansial Transaksi Aman).
- **Throughput**: Normal: 25.000 Events Per Second (EPS), Peak: 85.000 EPS.
- **Masalah Produksi**:
  Kluster awal mengalami *catastrophic cluster instability* saat kampanye promo nasional (Payday Sale). Query latensi melonjak dari 50ms ke >8 detik. Node mengalami *garbage collection pause* panjang (Stop-The-World hingga 12 detik), dan banyak request ingestion gagal dengan HTTP response `429 Too Many Requests`.
- **Root Cause Analysis (RCA)**:
  Ingestion diarahkan langsung ke Data Nodes (`node.roles: [data, master]`). Pipeline menggunakan processor `grok` yang sangat kompleks dengan ekspresi regex yang tidak efisien (*catastrophic backtracking*). Komputasi regex membebani CPU Data Node hingga 100%, sehingga Data Node kehabisan thread pool untuk melayani segment merging dan search retrieval.

#### Solusi Arsitektur Enterprise

```
                           ARSITEKTUR SEBELUM RE-ENGINEERING
                     ┌──────────────────────────────────────────────┐
                     │            All-In-One Data Nodes             │
[Clients] ──Bulk───► │ - Ingest Pipeline (Heavy Grok) [CPU 100%]    │
                     │ - Lucene Indexing & Segment Merge            │
                     │ - Search Engine Query Service (TIMEOUT)      │
                     └──────────────────────────────────────────────┘

                          ARSITEKTUR SETELAH RE-ENGINEERING
                                                                 ┌───────────────────────────┐
                                                            ┌───►│ Data Node Hot 01 (Data)   │
                                                            │    │ - Write Thread Pool       │
                                                            │    │ - Fast NVMe Disks         │
[Producers] ──► [Kafka Cluster] ──► [Consumer Groups]       │    └───────────────────────────┘
                                           │                │
                                           ▼ (Bulk Request) │    ┌───────────────────────────┐
                                 ┌───────────────────┐      ├───►│ Data Node Hot 02 (Data)   │
                                 │ Dedicated Ingest  │──────┤    │ - Write Thread Pool       │
                                 │ Cluster (3 Nodes) │      │    │ - Fast NVMe Disks         │
                                 │ node.roles:       │      │    └───────────────────────────┘
                                 │   [ ingest ]      │      │
                                 │ - Dissect Only    │      │    ┌───────────────────────────┐
                                 │ - Ingest Cache    │      └───►│ Dedicated Master (3 Nodes)│
                                 │ - Painless Sandbox│           │ node.roles: [ master ]    │
                                 └───────────────────┘           └───────────────────────────┘
```

1. **Pemisahan Peran Node (Topology Redesign)**:
   - Dibuat pool baru berupa 3 dedicated ingest nodes (`c6i.4xlarge`, 16 vCPU, 32GB RAM, JVM Heap 16GB). Node data dikonfigurasi murni `node.roles: [ data_hot, data_content ]`.
2. **Buffer Decoupling**:
   - Memasang layer Apache Kafka 3-broker cluster di depan Ingest Nodes. Consumer pool menggunakan Elasticsearch Bulk API dengan dynamic batch sizing (5MB - 10MB per batch, concurrent bulk requests diatur ke 8 thread paralel per worker).
3. **Optimasi Pipeline Engine**:
   - Mengganti seluruh pola `grok` dengan `dissect`. Untuk kasus parsing log berstruktur separator pasti (misal: JSON atau tab-delimited), `dissect` tidak menggunakan engine regex dan 4x lebih efisien dalam siklus CPU dibanding `grok`.
4. **Hasil Implementasi**:
   - CPU utilization pada Data Nodes turun drastis dari rata-rata 98% ke angka stabil 35%.
   - Ingest latency rata-rata cluster turun dari 450ms menjadi 18ms.
   - P99 Search Latency kembali normal ke 42ms tanpa terpengaruh fluktuasi volume data masuk.

---

### 9. Trade-offs

| Pendekatan Rekayasa | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Elasticsearch Ingest Pipeline** (Native) | Zero-infrastructure tambahan; konfigurasi declarative JSON yang disimpan di cluster state; tidak ada serialized network hop tambahan. | Mengonsumsi CPU cluster Elasticsearch; kemampuan routing/sink eksternal terbatas; skrip transformasi kompleks dibatasi oleh Painless sandbox. |
| **Eksternal ETL (Logstash / Apache Flink / Kafka Streams)** | Sangat scalable secara independen; fleksibilitas transformasi tak terbatas; integrasi multi-sink (Elasticsearch, S3, HDFS, PostgreSQL). | Biaya operasional tinggi; latency bertambah akibat network serialization antar hops; kompleksitas deployment, maintenance, dan monitoring bertambah. |
| **Dissect Processor vs Grok Processor** | `dissect` memiliki performa sangat tinggi dan zero-backtracking regex CPU spike. | `dissect` hanya dapat membedah pola string dengan delimiter statis yang kaku; tidak mampu memvalidasi format IP atau regex alternatif seperti `grok`. |
| **Enrich Processor vs Join Field Type (Parent-Child)** | Kecepatan search berada pada skala $O(1)$ per dokumen (denormalized flat model). | Storage disk bertambah akibat duplikasi data; memperbarui master data mewajibkan eksekusi ulang policy (`_execute`) dan *reindexing* data historis. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Anti-Patterns)
1. **Painless String Concatenation In Script**:
   *Anti-pattern*:
   ```painless
   // JANGAN LAKUKAN INI: Kompilasi ulang terjadi pada setiap loop/dokumen
   ctx.custom_id = ctx.source_system + "_" + ctx.user_id;
   ```
   *Mitigasi*: Gunakan static pattern atau method native:
   ```painless
   // BENAR: JVM menggunakan String builder internal tanpa trigger dynamic compilation
   ctx.custom_id = ctx.source_system.concat('_').concat(ctx.user_id);
   ```
2. **Mengabaikan Karakteristik Enrich Index Refresh**:
   Data di master index telah diupdate, namun dokumen baru tidak mendapatkan data terbaru. Hal ini terjadi karena Ingest Node mencari ke index snapshot `.enrich-*`. Anda **harus** menjalankan `POST /_enrich/policy/<policy_name>/_execute` agar snapshot diperbarui secara atomik.
3. **Bulk Ingestion Tanpa Handle HTTP 429**:
   Client HTTP menganggap kegagalan bulk menandakan seluruh request gagal, lalu mengirim ulang seluruh batch secara utuh (*retry storm*). Ini memperparah antrean write thread pool. Client **wajib** memeriksa array `items` pada response JSON dan hanya melakukan retry pada item dengan status code `429` menggunakan strategi *Exponential Backoff with Full Jitter*.

#### Panduan Troubleshooting

##### 1. Pipeline Debugging Menggunakan Simulate API
Jangan pernah mengetes pipeline langsung di live index. Gunakan `_simulate` API untuk melihat mutasi data per-step:

```json
POST /_ingest/pipeline/fintech_transaction_v1/_simulate
{
  "docs": [
    {
      "_index": "transactions-2026",
      "_id": "tx_test_01",
      "_source": {
        "merchant_id": "M-001",
        "card_number": "4111222233334444",
        "amount_cents": 7500000000,
        "tags": []
      }
    }
  ]
}
```

##### 2. Mendeteksi Bottleneck Ingest Node
Periksa node mana yang mengalami saturation pada prosesor tertentu menggunakan command:

```bash
GET /_nodes/stats/ingest?filter_path=nodes.*.ingest.pipelines.fintech_transaction_v1
```

Perhatikan metrik:
- `count`: Jumlah total dokumen yang diproses.
- `time_in_millis`: Total waktu pemrosesan dokumen.
- `failed`: Jumlah kegagalan pemrosesan.
Jika nilai `processors.*.time_in_millis` didominasi oleh satu processor tertentu (misal: Grok atau Script), lakukan refactoring pada processor tersebut.

---

### 11. Best Practices (Production Checklist)

- [ ] **Dedicated Ingest Nodes**: Pastikan cluster produksi memiliki minimal 2 node dengan konfigurasi eksklusif `node.roles: [ ingest ]`.
- [ ] **Grok Optimization**: Jika terpaksa menggunakan Grok, pasang anchor regex (`^` di awal dan `$` di akhir) untuk mencegah regular expression engine melakukan scan backtracking tak terbatas.
- [ ] **Always Use Dissect First**: Gunakan `dissect` untuk memecah envelope awal log, lalu gunakan `grok` hanya pada pecahan substring yang membutuhkan parsing dinamis.
- [ ] **Fail-Safe Mechanism**: Selalu sertakan blok array `on_failure` pada level root pipeline yang mengubah `_index` ke Dead Letter Queue (DLQ).
- [ ] **Index Template Binding**: Pasang pipeline default langsung pada Index Template melalui setting `"index.default_pipeline": "my_pipeline"` atau `"index.final_pipeline": "security_audit_pipeline"`.
- [ ] **Bulk Request Sizing**: Jangan mengirimkan request dokumen satu per satu. Kelompokkan dalam batch Bulk API berukuran antara 5MB hingga 15MB per payload.
- [ ] **Cache Pre-warming**: Jalankan eksekusi enrich policy pada saat low-traffic window atau integrasikan ke deployment automation pipeline.
- [ ] **Enrich Field Scoping**: Jangan masukkan seluruh field source index ke dalam `enrich_fields`. Hanya proyeksikan field-field yang absolut dibutuhkan oleh downstream query untuk menghemat memory footprint JVM.

---

### 12. Hands-on Practice: Membangun Resilient Production Pipeline

Simpan seluruh file praktikum ini ke dalam direktori: `hands-on/m02/`

#### File: `hands-on/m02/01-enrich-setup.json`
Setup indeks referensi user profile dan build enrich policy.

```bash
# 1. Buat index master database blocklist
curl -X PUT "http://localhost:9200/identity_blacklist" -H 'Content-Type: application/json' -d'
{
  "settings": { "number_of_shards": 1, "number_of_replicas": 0 },
  "mappings": {
    "properties": {
      "ip_address": { "type": "ip" },
      "threat_score": { "type": "integer" },
      "category": { "type": "keyword" }
    }
  }
}'

# 2. Ingest data threat intelligence
curl -X POST "http://localhost:9200/identity_blacklist/_bulk?refresh=true" -H 'Content-Type: application/x-ndjson' -d'
{"index":{"_id":"1"}}
{"ip_address":"198.51.100.45","threat_score":95,"category":"BOTNET_C2"}
{"index":{"_id":"2"}}
{"ip_address":"203.0.113.19","threat_score":80,"category":"TOR_EXIT_NODE"}
'

# 3. Definisikan Enrich Policy
curl -X PUT "http://localhost:9200/_enrich/policy/threat_ip_policy" -H 'Content-Type: application/json' -d'
{
  "match": {
    "indices": "identity_blacklist",
    "match_field": "ip_address",
    "enrich_fields": ["threat_score", "category"]
  }
}'

# 4. Compile policy
curl -X POST "http://localhost:9200/_enrich/policy/threat_ip_policy/_execute"
```

#### File: `hands-on/m02/02-production-pipeline.json`
Pipeline dengan dissect, enrich, script sanitasi, dan dynamic rerouting untuk error handling.

```bash
curl -X PUT "http://localhost:9200/_ingest/pipeline/edge_security_pipeline" -H 'Content-Type: application/json' -d'
{
  "description": "Production Edge Security Ingestion Pipeline",
  "processors": [
    {
      "dissect": {
        "field": "raw_payload",
        "pattern": "%{event_timestamp}|%{client_ip}|%{user_id}|%{http_status}|%{endpoint}",
        "ignore_failure": false
      }
    },
    {
      "convert": {
        "field": "http_status",
        "type": "integer"
      }
    },
    {
      "enrich": {
        "policy_name": "threat_ip_policy",
        "field": "client_ip",
        "target_field": "threat_intelligence",
        "ignore_missing": true
      }
    },
    {
      "script": {
        "lang": "painless",
        "source": """
          if (ctx.containsKey("threat_intelligence") && ctx.threat_intelligence != null) {
            int score = ctx.threat_intelligence.threat_score;
            if (score >= params.quarantine_limit) {
              ctx.security_alert = "CRITICAL_THREAT_BLOCKED";
              ctx._index = "security-quarantine-events";
            }
          }
        """,
        "params": {
          "quarantine_limit": 85
        }
      }
    },
    {
      "remove": {
        "field": "raw_payload"
      }
    }
  ],
  "on_failure": [
    {
      "set": {
        "field": "_index",
        "value": "security-pipeline-dlq"
      }
    },
    {
      "set": {
        "field": "error_detail",
        "value": "{{_ingest.on_failure_message}}"
      }
    }
  ]
}'
```

#### File: `hands-on/m02/03-verify-pipeline.json`
Uji berbagai kondisi data: (1) Normal traffic, (2) Malicious IP traffic, dan (3) Malformed string payload.

```bash
# Skenario 1: Normal Ingestion
curl -X POST "http://localhost:9200/security-access-logs/_doc?pipeline=edge_security_pipeline&refresh=true" -H 'Content-Type: application/json' -d'
{
  "raw_payload": "2026-03-30T10:00:00Z|192.168.1.1|USR-881|200|/api/v1/checkout"
}'

# Skenario 2: Malicious Traffic (Threat Score: 95 -> Ter-reroute ke security-quarantine-events)
curl -X POST "http://localhost:9200/security-access-logs/_doc?pipeline=edge_security_pipeline&refresh=true" -H 'Content-Type: application/json' -d'
{
  "raw_payload": "2026-03-30T10:00:05Z|198.51.100.45|USR-999|403|/admin/login"
}'

# Skenario 3: Malformed Payload (Dissect mismatch -> Masuk ke security-pipeline-dlq via on_failure)
curl -X POST "http://localhost:9200/security-access-logs/_doc?pipeline=edge_security_pipeline&refresh=true" -H 'Content-Type: application/json' -d'
{
  "raw_payload": "BROKEN_STRING_WITHOUT_DELIMITERS"
}'

# Verifikasi Routing
curl -s "http://localhost:9200/security-access-logs/_search" | jq .hits.hits
curl -s "http://localhost:9200/security-quarantine-events/_search" | jq .hits.hits
curl -s "http://localhost:9200/security-pipeline-dlq/_search" | jq .hits.hits
```

---

### 13. Exercise

#### Level: Easy
1. Buat pipeline bernama `add_metadata_pipeline` yang menyematkan metadata field `cluster_region: "ap-southeast-3"` dan mengonversi field `email` menjadi *lowercase*.
2. Uji pipeline tersebut menggunakan `_simulate` API dengan dokumen uji yang berisi alamat email bertulisan huruf besar (`JOHN.DOE@EXAMPLE.COM`).

#### Level: Medium
1. Buat sebuah pipeline yang menerima dokumen log dengan field `user_agent`.
2. Gunakan `user_agent` processor untuk mengekstrak sistem operasi dan browser name.
3. Tambahkan processor `script` (Painless) yang memeriksa: jika `user_agent.os.name` sama dengan "Unknown" ATAU bernilai null, sematkan tag `"LEGACY_CLIENT"` ke dalam array `tags`. Pastikan operasi array aman dari `NullPointerException`.

#### Level: Hard
1. Buat arsitektur data pipeline yang mengimplementasikan **Nested Ingest Pipelines**:
   - Pipeline utama (`root_audit_pipeline`) memproses autentikasi dasar.
   - Jika dokumen memiliki field `service_type == "KUBERNETES"`, pipeline utama menggunakan `pipeline` processor untuk memanggil `k8s_sub_pipeline`.
   - Jika `service_type == "DATABASE"`, pipeline utama memanggil `db_sub_pipeline`.
   - Setiap sub-pipeline memiliki struktur `on_failure` masing-masing yang menyematkan metadata spesifik layer tersebut, sebelum meneruskannya ke index fallback pusat.

---

### 14. Challenge

#### Deskripsi Skenario Tantangan
Anda bekerja sebagai Lead Platform Engineer di sebuah bursa perdagangan aset digital (Crypto Exchange). Sistem mencatat transaksi perdagangan ke dalam format CSV ringkas melalui antrean pesan berkecepatan tinggi (30.000 batch/detik).
Struktur payload mentah:
`"tx_id,timestamp,user_id,crypto_pair,fiat_amount,client_ip,device_id"`

#### Syarat & Batasan Implementasi
1. **Dynamic Zero-Downtime Currency Enrichment**: Nilai tukar mata uang fiat berfluktuasi setiap 1 menit. Pipeline harus mampu memperkaya dokumen dengan data kurs terkini tanpa me-restart node, tanpa menghentikan pipeline ingestion, dan tanpa menurunkan indexing throughput di bawah 25.000 EPS.
2. **Deterministic Fraud Interception**:
   Jika field `fiat_amount` bernilai lebih besar dari Rp 500.000.000 (lima ratus juta rupiah) DAN `client_ip` terdeteksi berasal dari luar yurisdiksi Indonesia (gunakan GeoIP processor), dokumen secara runtime dialihkan ke indeks isolasi `compliance-urgent-audit` dengan status audit `FLAGGED`.
3. **Strict Zero-Loss Guarantee**:
   Tidak boleh ada satu pun dokumen yang dibatalkan (*dropped*) akibat kegagalan parsing tanggal, konversi string ke double, atau kegagalan look-up IP. Jika terjadi anomali parser apapun, dokumen asli beserta raw stack trace Elasticsearch harus tersimpan di index `crypto-ingest-dlq`.
4. **Deliverables**:
   Tuliskan seluruh deklarasi Index Template, Enrich Policy Script Lifecycle, dan Ingest Pipeline JSON definisi secara modular, lengkap dengan skenario demonstrasi zero-downtime execution saat update kurs berjalan.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa peran utama dari node yang hanya memiliki setting `node.roles: [ ingest ]`?
   - A. Menampung primary shard dan replica shard.
   - B. Bertindak sebagai cluster manager dan memelihara cluster state.
   - C. Melakukan intercept, transformasi, dan sanitasi dokumen sebelum dialokasikan ke data nodes.
   - D. Menjalankan query Lucene search dengan alokasi disk cache yang besar.

2. Mengapa processor `dissect` secara umum direkomendasikan daripada `grok` untuk format log terstruktur?
   - A. Karena `dissect` mendukung distributed multi-threading sedangkan `grok` tidak.
   - B. Karena `dissect` tidak menggunakan pattern matching regex berbasis komputasi CPU berat, melainkan pencocokan string langsung.
   - C. Karena `grok` hanya mendukung format bahasa pemrograman Python.
   - D. Karena `dissect` mampu menyimpan master data secara native di dalam memori heap.

3. Parameter apa pada Ingest Processor `script` yang **wajib** digunakan untuk meneruskan variabel dinamis guna menghindari kompilasi skrip berulang kali di memory JVM?
   - A. `context`
   - B. `variables`
   - C. `source`
   - D. `params`

4. Operasi API apa yang wajib dipanggil setelah melakukan perubahan data pada master index yang digunakan oleh sebuah Enrich Policy?
   - A. `POST /_enrich/policy/<policy_name>/_refresh`
   - B. `POST /_enrich/policy/<policy_name>/_execute`
   - C. `PUT /_ingest/pipeline/_reload`
   - D. `POST /_cluster/nodes/reload_enrich`

5. Dimana dokumen akan dialihkan secara otomatis jika sebuah prosesor gagal mengeksekusi data dan pipeline memiliki konfigurasi `on_failure` di tingkat global?
   - A. Dokumen secara permanen dibuang dari pipeline tanpa notifikasi.
   - B. Dokumen dialihkan ke blok log elasticsearch server (`elasticsearch.log`).
   - C. Dokumen dieksekusi oleh rangkaian processor alternatif yang didefinisikan pada blok `on_failure`.
   - D. Seluruh batch Bulk API langsung dibatalkan (*rollbacked*) ke state semula.

---

#### Bagian 2: Intermediate (Pilihan Ganda)
6. Apa dampak arsitektural yang terjadi jika Anda membiarkan `node.roles: [ data, ingest ]` pada kluster dengan beban ingestion 50.000 EPS?
   - A. Segment merge Lucene otomatis dialihkan ke file system swap.
   - B. Operasi write thread pool dan ingest thread pool akan bersaing memperebutkan thread CPU cores yang sama, mengakibatkan lonjakan latency pada read search requests.
   - C. Tidak ada dampak sama sekali karena Elasticsearch secara default memiliki isolasi CPU core di level kernel Linux.
   - D. Ingest pipeline secara otomatis dinonaktifkan jika data node kehabisan memori.

7. Perhatikan potongan script Painless berikut:
   ```painless
   ctx.final_price = ctx.base_price - (ctx.base_price * ctx.discount);
   ```
   Apa resiko runtime kegagalan paling sering terjadi pada potongan skrip di atas jika diterapkan pada data ingestion skala besar?
   - A. StackOverflowException akibat rekursi mendalam.
   - B. NullPointerException jika salah satu field `base_price` atau `discount` tidak ada atau bernilai `null`.
   - C. JVM Heap Exhaustion akibat alokasi memori double-precision float.
   - D. Security Exception karena operasi aritmatika dilarang di Painless context.

8. Bagaimana cara kerja internal indeks `.enrich-*` yang dihasilkan oleh Enrich Policy?
   - A. Berupa database SQLite terdistribusi yang ditempelkan ke setiap data shard.
   - B. Merupakan file teks flat di dalam direktori sistem operasi `/tmp`.
   - C. Merupakan sistem indeks read-only teroptimasi yang didistribusikan ke node-node yang menjalankan fungsi ingestion untuk lookup memory berkecepatan tinggi.
   - D. Menghubungi data master eksternal secara asinkron menggunakan koneksi JDBC socket port 3306.

9. Manakah pernyataan yang **salah** mengenai penanganan *backpressure* (HTTP 429) pada Bulk API?
   - A. Status code 429 menandakan `write` atau `ingest` thread pool queue telah mencapai batas alokasi kapasitas (`queue_size`).
   - B. Client harus mengulang seluruh isi batch request awal secara bersamaan tanpa jeda waktu agar tidak kehilangan data.
   - C. Client idealnya menerapkan arsitektur *exponential backoff* dengan penambahan *random jitter*.
   - D. Penggunaan message broker seperti Apache Kafka di depan Ingest Nodes dapat mengeliminasi kegagalan 429 langsung ke producer aplikasi.

10. Kapan Anda sebaiknya menggunakan `final_pipeline` dibandingkan `default_pipeline` pada setting Index Template?
    - A. Ketika Anda ingin mengizinkan client mengabaikan seluruh proses transformasi.
    - B. Ketika Anda membutuhkan prosesor sanitasi keamanan atau penambahan audit metadata yang **tidak boleh digantikan atau dilewati** oleh pipeline yang ditentukan secara dinamis oleh client request.
    - C. Ketika data yang diproses memiliki volume lebih besar dari 10GB per hari.
    - D. `final_pipeline` hanya dapat digunakan untuk menghapus segmen Lucene yang korup saat shutdown.

---

#### Bagian 3: Skenario Kasus Produksi

##### Kasus 1: Out of Memory Spike Pasca Deploy Skrip Baru
Sebuah tim baru saja mendeploy pipeline yang menggunakan processor `script` (Painless) untuk membuat tracking ID unik dengan kode:
`ctx.tracking_hash = ctx.region + "-" + ctx.customer_id + "-" + UUID.randomUUID().toString();`
Dalam waktu 20 menit pasca deployment ke live traffic (40.000 EPS), seluruh Ingest Node mengalami JVM Crash (Out of Memory: Java heap space) dan cluster log dipenuhi oleh pesan error `circuit_breaking_exception: [script] Too many dynamic script compilations`.
- **Pertanyaan**: Jelaskan secara mendalam akar penyebab (*root cause*) teknis dari kegagalan ini dan bagaimana kode script tersebut harus diperbaiki agar stabil di tingkat produksi!

##### Kasus 2: Data Loss Siluman Pasca Reindexing
Sebuah e-commerce menerapkan enrich policy untuk memasukkan data nama kategori produk dari indeks master `categories`. Saat terjadi promosi besar, data master `categories` diperbarui secara massal di database Elasticsearch. Namun, semua transaksi baru yang di-ingest tetap menampilkan nama kategori lama. Mengira pipeline bermasalah, engineer me-restart seluruh cluster, tetapi data yang masuk tetap tidak terupdate.
- **Pertanyaan**: Mengapa restart kluster tidak menyelesaikan masalah tersebut? Langkah spesifik apa yang dilewati oleh tim engineer dalam lifecycle enrich policy Elasticsearch?

##### Kasus 3: Cascade Failure Akibat Poison Pill
Sebuah producer IoT mengirim batch bulk yang terdiri dari 5.000 log events per batch HTTP POST. Di antara 5.000 event tersebut, terdapat 1 event anomali di mana field `latitude` berisi string mentah acak `"N/A"`, padahal mapping target index mendefinisikan field `latitude` sebagai tipe data `geo_point` / `float`. Akibatnya, seluruh 5.000 data dalam batch tersebut ditolak oleh cluster dan log producer mencoba mengirim ulang batch yang sama terus menerus (*infinite loop*), mengakibatkan network pipe jenuh.
- **Pertanyaan**: Rancang strategi isolasi pipeline komprehensif menggunakan kombinasi processor konversi, routing metadata `_index`, dan blok `on_failure` pada Ingest Pipeline untuk mengeliminasi dampak *poison pill* ini tanpa menggagalkan 4.999 data valid lainnya!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian 1: Basic
1. **C** — Dedicated Ingest Node bertugas mengeksekusi task transformasi dokumen sebelum diteruskan ke data nodes pemegang shard.
2. **B** — `dissect` bekerja dengan pencocokan delimiter statis tanpa kompilasi regular expression yang memakan resource CPU intensif.
3. **D** — `params` memisahkan data runtime dari AST skrip yang sudah terkompilasi, sehingga skrip dapat di-cache secara permanen.
4. **B** — Eksekusi `POST /_enrich/policy/<policy_name>/_execute` mutlak dibutuhkan untuk merakit ulang indeks internal `.enrich-*`.
5. **C** — Blok `on_failure` menangkap exception processor dan mengalihkan alur ke processor fallback yang didefinisikan di dalamnya.

#### Bagian 2: Intermediate
6. **B** — Shared node memicu perebutan resource antara serialisasi ingest pipeline dan indexing Lucene disk I/O / segment merge.
7. **B** — Painless strongly typed; mengakses properti dari object yang bernilai `null` seketika melempar NullPointerException dan menggagalkan eksekusi dokumen.
8. **C** — Indeks `.enrich-*` didesain read-only, terkompresi, dan optimal untuk point-in-time in-memory lookups.
9. **B** — Mengulang batch secara penuh tanpa memfilter item yang sukses akan menimbulkan duplikasi dan memperparah load bottleneck cluster (*retry storm*).
10. **B** — `final_pipeline` selalu dieksekusi setelah `default_pipeline` atau request pipeline selesai, menjamin aturan compliance/audit tidak dapat dimanipulasi client.

#### Bagian 3: Solusi Skenario Kasus Produksi

##### Jawaban Kasus 1:
- **Root Cause**:
  1. Penggunaan `UUID.randomUUID().toString()` di dalam inline Painless script menghasilkan script token dinamis jika dikombinasikan dengan string concatenation tanpa sanitasi.
  2. Penggabungan string langsung (`+`) menyebabkan pembuatan object String baru terus-menerus di Eden Space memory.
  3. Namun yang paling kritikal, pemanggilan class method yang menghasilkan variasi dynamic parameter tanpa passing via map `params` memicu JVM menganggap skrip tersebut merupakan skrip baru dan berupaya mengompilasinya ulang. Begitu limit `script.max_compilations_rate` terlewati, JVM mengalami context switching ekstrem, memicu heap saturation, dan crashing.
- **Solusi**:
  Gunakan processor bawaan Elasticsearch untuk UUID atau hashing daripada mengeksekusinya di Painless:
  ```json
  {
    "set": {
      "field": "uuid_token",
      "value": "{{_ingest.timestamp}}"
    }
  }
  ```
  Jika tetap membutuhkan Painless, generate UUID di layer *log producer* (sebelum dikirim ke ES) lalu teruskan ke pipeline sebagai value murni melalui `ctx.tracking_id = params.prefix + ctx.source_uuid`.

##### Jawaban Kasus 2:
- **Root Cause**:
  Enrich processor **tidak** melakukan query langsung ke source index asli pada saat runtime ingestion, melainkan membaca data dari internal system index snapshot berformat `.enrich-*`.
- **Langkah yang Terlewat**:
  Ketika data source index diupdate, snapshot `.enrich-*` tidak otomatis sinkron. Restart cluster tidak mengubah state indeks Lucene `.enrich-*` yang sudah terkompilasi.
- **Solusi**:
  Engineer wajib mengeksekusi perintah:
  `POST /_enrich/policy/<nama_policy>/_execute`
  secara berkala (misal via cron/automation CI-CD) agar Elasticsearch membaca ulang data master dan mengompilasi ulang indeks internal read-only `.enrich-*`.

##### Jawaban Kasus 3:
- **Solusi Arsitektural Resilient Pipeline**:
  Gunakan nested conditional validation dengan safe casting dan DLQ routing:
  ```json
  PUT _ingest/pipeline/iot_telemetry_resilient
  {
    "processors": [
      {
        "convert": {
          "field": "latitude",
          "type": "float",
          "ignore_missing": true,
          "on_failure": [
            {
              "set": {
                "field": "error_reason",
                "value": "Field latitude non-numeric: {{latitude}}"
              }
            },
            {
              "set": {
                "field": "_index",
                "value": "poison-pills-telemetry-dlq"
              }
            }
          ]
        }
      }
    ]
  }
  ```
  Dengan konfigurasi di atas:
  1. Dokumen yang memiliki nilai latitude valid akan dikonversi ke float dan dilanjutkan ke target index normal.
  2. Dokumen yang memiliki nilai `"N/A"` akan gagal pada processor `convert`, namun tertangkap oleh `on_failure` lokal processor tersebut.
  3. Dokumen anomali dipindahkan target index-nya ke `poison-pills-telemetry-dlq` dan tidak menggagalkan 4.999 dokumen valid lainnya di dalam payload `_bulk` tersebut.

---

### 16. Summary
- **Dedicated Topology**: Mengisolasi role node ingest (`node.roles: [ingest]`) adalah pondasi wajib pada sistem berskala jutaan event agar pemrosesan ETL dokumen tidak mengorbankan performa indexing dan latency pencarian data nodes.
- **Engine Optimization**: Utamakan processor `dissect` dibanding `grok` di jalur data bertrafik tinggi untuk mengeliminasi utilisasi CPU berlebih akibat regex catastrophic backtracking.
- **In-Memory Enrichment**: Enrich Policies merealisasikan kemampuan denormalisasi dokumen berkecepatan tinggi tanpa search-time join, dengan konsekuensi wajib mengeksekusi ulang kompilasi policy (`_execute`) ketika master data berubah.
- **Sandbox Security & Performance**: Hindari logika bisnis rumit yang memicu dynamic compilation di Painless script. Gunakan dictionary `params` untuk variabel dinamis dan selalu implementasikan pengecekan `null` secara defensif.
- **Resiliency-First**: Selalu desain Ingest Pipeline dengan pendekatan *defensive programming*: manfaatkan `ignore_missing`, tangani failure parsing di level lokal processor, dan sediakan *Dead Letter Queue* rerouting di level global `on_failure` untuk menjamin operasi ingestion tanpa data loss (*zero-loss guarantees*).