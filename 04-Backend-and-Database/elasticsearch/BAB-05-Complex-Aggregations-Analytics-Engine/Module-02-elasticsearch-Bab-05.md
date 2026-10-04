# BAB 05: Complex Aggregations & Analytics Engine
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menguasai arsitektur internal eksekusi agregasi pada Lucene dan Elasticsearch, termasuk struktur data *Doc Values*, *Global Ordinals*, serta memori manajemen pada JVM Heap.
- Mengimplementasikan agregasi metrik tingkat lanjut (*Percentiles* berbasis T-Digest/HDRHistogram dan *Cardinality* berbasis HyperLogLog++) dengan kontrol presisi memori yang optimal.
- Merancang arsitektur analitik bertingkat (*Multi-bucket nested aggregations*) yang dikombinasikan dengan *Pipeline Aggregations* (*Parent* dan *Sibling*) untuk kalkulasi komputasi derivatif, *moving function*, dan anomali data.
- Mengeliminasi bias kalkulasi terdistribusi (*distributed terms aggregation bias*) menggunakan parameter `shard_size` dan mitigasi *Circuit Breaker Exception*.
- Mengoperasikan *Composite Aggregation* untuk ekstraksi dataset analitik masif secara terpaginasi tanpa memicu degradasi performa klaster.

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib memahami:
- Arsitektur dasar Elasticsearch: Peran *Master Node*, *Data Node*, dan *Coordinating Node*.
- Struktur dasar *Inverted Index* vs *Columnar Store* (*Doc Values*).
- Syntax dasar agregasi Elasticsearch (`aggs`, `terms`, `sum`, `avg`, `range`).
- Model memori JVM (Heap, Young/Old Gen, Off-Heap) dan dasar *Garbage Collection* (G1GC/ZGC).
- Menguasai cURL, REST Client, atau Dev Tools Console di Kibana.

---

### 3. Concept & Internal Architecture (Mendalam)

Agregasi pada Elasticsearch bukan sekadar operasi `GROUP BY` SQL tradisional. Elasticsearch adalah mesin analitik terdistribusi *near-real-time* yang mengeksekusi komputasi analitik di atas Apache Lucene.

```
                    [ Distributed Query Execution Architecture ]

 Client
   │
   ▼ (Search Request with Aggregations)
[Coordinating Node]
   │
   ├── Scatter Phase ────────────────────────────────────────────────────────┐
   │   (Translates query AST, distributes shard search requests)             │
   │                                                                         ▼
   ▼                                                                    [Data Node 2]
[Data Node 1]                                                           ┌───────────┐
┌───────────────────────────────────────────────────────────────────┐   │ Shard 2   │
│ Shard 1 (Lucene Index)                                            │   │           │
│                                                                   │   │ Lucene DV │
│  Segment 1           Segment 2           Segment 3                │   │ Segments  │
│ ┌───────────────┐  ┌───────────────┐  ┌───────────────┐           │   │  ...      │
│ │ Doc Values    │  │ Doc Values    │  │ Doc Values    │           │   └─────┬─────┘
│ │ (Columnar)    │  │ (Columnar)    │  │ (Columnar)    │           │         │
│ └───────┬───────┘  └───────┬───────┘  └───────┬───────┘           │         │
│         │                  │                  │                   │         │
│         ▼                  ▼                  ▼                   │         │
│    Local Ordinals     Local Ordinals     Local Ordinals           │         │
│         └──────────────────┼──────────────────┘                   │         │
│                            ▼                                      │         │
│                 [ Global Ordinals Table ]                         │         │
│                            │                                      │         │
│                            ▼                                      │         │
│               [ Shard Aggregator: Top-K ]                         │         │
│             (Uses shard_size to reduce bias)                      │         │
└────────────────────────────┬──────────────────────────────────────┘         │
                             │                                                │
   ▲                         │ Local Aggregation Results                      │
   │                         ▼                                                │
   ├── Gather Phase ──────────────────────────────────────────────────────────┘
   │   (Merges shard buckets, executes Pipeline Aggregations)
   ▼
[Coordinating Node]
   │
   ▼ (Final Merged JSON Response)
 Client
```

#### A. Doc Values vs Fielddata
Lucene memisahkan struktur data untuk pencarian teks dan analitik:
- **Inverted Index**: Memetakan `Term -> Document IDs`. Sangat cepat untuk *full-text search*, tetapi sangat lambat dan memakan memori besar jika digunakan untuk agregasi (memerlukan rekonstruksi dokumen *on-the-fly*).
- **Doc Values**: Format penyimpanan *columnar* (berorientasi kolom) yang dibangun saat *indexing time* dan disimpan di disk (dengan pemanfaatan agresif terhadap OS *Filesystem Page Cache*). Memetakan `Document ID -> Terms/Values`. Digunakan untuk semua *field* bertipe numerik, *date*, *boolean*, dan *keyword*.
- **Fielddata**: Padanan *Doc Values* tetapi berada di JVM Heap dan dikonstruksi secara *in-memory* ketika field bertipe `text` dipaksa untuk diagregasi. **Sangat dihindari di skala produksi** karena menyebabkan *Garbage Collection pause* yang masif dan memicu *OutOfMemoryError*.

#### B. Global Ordinals Engine
Untuk *field* bertipe `keyword`, menyimpan string secara repetitif di setiap dokumen adalah inefisien. Lucene menggunakan representasi bilangan bulat yang disebut **Ordinal**:
1. **Local Ordinals**: Setiap segmen Lucene menetapkan integer unik berurutan untuk setiap string unik yang terdapat di dalam segmen tersebut. Masalahnya: Nilai ordinal `1` pada Segmen A belum tentu merepresentasikan string yang sama dengan ordinal `1` pada Segmen B.
2. **Global Ordinals**: Elasticsearch membangun struktur pemetaan global yang menyelaraskan seluruh *Local Ordinals* di semua segmen dalam sebuah *shard*.
3. **Execution Hint**: Agregasi `terms` dapat menggunakan `execution_hint: "global_ordinals"` (default) atau `execution_hint: "map"`. Mode `global_ordinals` memproses agregasi secara numerik menggunakan array primitif, menghasilkan throughput tinggi dan jejak memori yang sangat rendah. 
4. **Eager Global Ordinals**: Secara default, *Global Ordinals* dibangun saat *search request* pertama kali tiba (*lazy loading*), yang dapat menyebabkan *query latency spike*. Untuk analitik latensi-kritis, mapping dapat dikonfigurasi dengan `"eager_global_ordinals": true` agar struktur ini langsung dibangun saat *refresh* segmen terjadi.

#### C. Distribusi Komputasi: The Scatter-Gather & Shard Size Bias
Ketika *Coordinating Node* mengirimkan kueri agregasi `terms` ke beberapa shard:
1. Setiap shard mengeksekusi agregasi secara lokal dan mengembalikan hanya *top-K* bucket (ditentukan oleh parameter `shard_size`, secara default: `(size * 1.5) + 10`).
2. *Coordinating Node* menerima hasil dari seluruh shard dan menggabungkannya (*merge phase*) untuk memilih *top-K* global akhir.
3. **The Bias Problem**: Jika data terdistribusi tidak merata, dokumen yang memiliki frekuensi tinggi secara global bisa saja tereliminasi di tingkat lokal sebuah shard karena kalah peringkat di shard tersebut.
4. Elasticsearch mengekspos dua metrik integritas data:
   - `doc_count_error_upper_bound`: Batas atas teoritis dokumen yang mungkin terlewatkan untuk bucket yang dikembalikan.
   - `sum_other_doc_count`: Jumlah seluruh dokumen yang berada di luar bucket yang dikembalikan.

#### D. Algoritma Perkiraan (Approximate Algorithms)
Untuk dataset berskala miliaran dokumen, komputasi eksak memerlukan alokasi memori linear terhadap kardinalitas unik ($O(N)$). Elasticsearch mengimplementasikan algoritma aproksimasi probabilistik berkinerja tinggi:

1. **HyperLogLog++ (Cardinality Aggregation)**:
   - Menggunakan hashing 64-bit untuk mendistribusikan data secara merata.
   - Menghitung jumlah *leading zeros* dari hash dokumen untuk memperkirakan kardinalitas secara probabilistik.
   - Parameter `precision_threshold` (default `3000`, maksimum `40000`) mengontrol batas memori vs akurasi. Memori yang dialokasikan maksimal adalah $\approx \text{precision\_threshold} \times 8 \text{ bytes}$.
   - Memiliki varian representasi internal: *Sparse* (untuk himpunan data kecil, hemat memori) dan *Dense* (array tetap untuk himpunan data besar).

2. **T-Digest (Percentiles Aggregation)**:
   - Menghitung kuantil (seperti P50, P95, P99) tanpa harus mengurutkan seluruh kumpulan data.
   - Mengelompokkan titik data ke dalam sejumlah klaster yang disebut *Centroids*.
   - Parameter `compression` (default `100`) menentukan jumlah centroid maksimum ($q \times \text{compression}$). Peningkatan nilai `compression` menaikkan akurasi di area ekstrim (tail latency P99.9) dengan konsekuensi linear terhadap penggunaan JVM heap.

#### E. Pipeline Aggregations Architecture
Pipeline Aggregations beroperasi bukan di atas dokumen langsung, melainkan di atas output yang dihasilkan oleh agregasi lain:
- **Parent Pipeline Aggregation**: Mengonsumsi bucket induknya dan menambahkan metrik komputasi baru ke dalam bucket tersebut (contoh: `derivative`, `cumulative_sum`, `bucket_script`).
- **Sibling Pipeline Aggregation**: Beroperasi sejajar dengan bucket target untuk menghasilkan metrik ringkasan baru di luar struktur bucket (contoh: `stats_bucket`, `max_bucket`, `min_bucket`).

---

### 4. Why & What

| Dimensi | Operational Analytics di Elasticsearch | Traditional RDBMS / Data Warehouse (OLAP) |
| :--- | :--- | :--- |
| **Indexing Model** | Dokumen semi-terstruktur (JSON) dengan skema dinamis/fleksibel. | Skema relasional kaku (Star Schema / Snowflake Schema). |
| **Storage Structure** | Hybrid: *Inverted Index* (Search) + *Doc Values* (Analytics/Columnar). | Pure Columnar (misal Parquet, ClickHouse MergeTree). |
| **Latency Characteristic** | Near-Real-Time (NRT) dengan sub-second latensi agregasi di miliaran log. | Batch-oriented atau OLAP real-time berbasis vectorized execution. |
| **Skalabilitas** | Horisontal tak terbatas via partisi *sharding* dan replikasi otomatis. | Membutuhkan setup MPP (*Massively Parallel Processing*) kompleks. |
| **Kelemahan Utama** | *High memory footprint* jika kardinalitas tak terkontrol; bukan untuk join kompleks. | Kurang fleksibel untuk pencarian *unstructured text* simultan. |

**Kapan Menggunakan Aggregations di Elasticsearch?**
- Visualisasi dashboard metrik real-time (APM, Security Analytics/SIEM, Log Analytics).
- Deteksi anomali transaksional (misal: rasio *failure rate* per *gateway* dalam jendela waktu bergerak 5 menit).
- Ekstraksi analitik terindeks yang digabungkan secara instan dengan kueri teks (*hybrid query & analytics*).

---

### 5. How (Workflow Detail)

Alur komputasi analitik Elasticsearch dari *query parsing* hingga *serialization*:

```
[REST HTTP Client]
       │
       ▼
 1. [HTTP Parsing & Validation]
    Coordinator menerima REST payload JSON, memvalidasi sintaks AST agregasi.
       │
       ▼
 2. [Execution Planning]
    Coordinator mengecek Cluster State via Shard Routing Table untuk mendeteksi shard target.
       │
       ▼
 3. [Distributed Scatter Phase]
    Coordinator mendistribusikan Search Request via Transport Protocol ke setiap Data Node.
       │
       ▼
 4. [Segment-Level Execution (Data Node)]
    Lucene mengeksekusi kueri filter; mengumpulkan Document IDs yang lolos evaluasi.
    Doc Values Reader membaca data kolom secara sequential dari OS Page Cache.
    Pemeriksaan Circuit Breaker (`indices.breaker.request.limit`).
       │
       ▼
 5. [Global Ordinals Resolution & Hashing]
    Memetakan Local Ordinals ke Global Ordinals Table.
    Eksekusi algoritma aproksimasi (T-Digest untuk percentiles, HLL++ untuk cardinality).
       │
       ▼
 6. [Local Shard Reduction]
    Mengekstrak top `shard_size` bucket lokal dari masing-masing shard.
       │
       ▼
 7. [Gather Phase to Coordinator]
    Data nodes mengirimkan struktur serialisasi shard aggregations kembali ke Coordinator Node.
       │
       ▼
 8. [Global Coordinator Reduction & Pipeline Processing]
    Coordinator menggabungkan bucket seluruh shard, memotong ke `size` yang diminta.
    Pipeline Aggregations (derivative, moving_fn, bucket_script) dieksekusi di fase ini.
       │
       ▼
 9. [JSON Serialization]
    Hasil akhir diubah menjadi JSON response dan dikembalikan via HTTP stream.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sensus Kependudukan Multi-Wilayah Terdistribusi
Bayangkan sensus nasional untuk menemukan 10 profesi paling populer di Indonesia:
- **Shard** adalah **Petugas Kecamatan**.
- Jika setiap kecamatan hanya melaporkan 10 profesi teratas di daerahnya (*size = 10*): Di sebuah kecamatan pesisir, "Petani Rumput Laut" berada di peringkat 1, tetapi "Software Engineer" berada di peringkat 11 (tidak dilaporkan). Padahal di level nasional, jika akumulasi seluruh kecamatan dijumlahkan, "Software Engineer" seharusnya masuk peringkat 5 nasional.
- Solusi: **`shard_size`**. Kantor pusat (Coordinator) meminta setiap kecamatan melaporkan 50 profesi teratas (*shard_size = 50*), sehingga profesi berperingkat marginal lokal tetap terangkat ke agregasi global untuk akurasi mutlak.

```
SHARD 1 (Pesisir)                 SHARD 2 (Metropolitan)
┌───────────────────────┐         ┌───────────────────────┐
│ Top 3 (shard_size=3): │         │ Top 3 (shard_size=3): │
│ 1. Nelayan     (1000) │         │ 1. Engineer    (1200) │
│ 2. Petani      (800)  │         │ 2. Akuntan     (900)  │
│ 3. Pedagang    (300)  │         │ 3. Pedagang    (700)  │
│ [Excluded:            │         │ [Excluded:            │
│  Engineer (250)]      │         │  Nelayan (50)]        │
└───────────┬───────────┘         └───────────┬───────────┘
            │                                 │
            └───────────────┬─────────────────┘
                            ▼
            COORDINATING NODE (Gather Phase)
            ┌─────────────────────────────────────────┐
            │ Tanpa shard_size tuning:                │
            │ Nelayan: 1000 (missing 50 from Shard 2) │
            │ Engineer: 1200 (missing 250 from Shard1)│
            │ Akuntan: 900                            │
            │ Pedagang: 1000                          │
            │                                         │
            │ Error Margin tercatat di:               │
            │ `doc_count_error_upper_bound`           │
            └─────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Composite Aggregation dengan Pagination (`after_key`)
Berguna untuk mengekstraksi seluruh kombinasi bucket unik tanpa terkena batasan `max_buckets` (default 65.536):

```json
POST /ecommerce_orders/_search
{
  "size": 0,
  "aggs": {
    "paginated_sales": {
      "composite": {
        "size": 2,
        "sources": [
          { "order_date": { "date_histogram": { "field": "created_at", "calendar_interval": "month" } } },
          { "merchant_id": { "terms": { "field": "merchant_id.keyword" } } }
        ],
        "after": {
          "order_date": 1672531200000,
          "merchant_id": "MERC-9921"
        }
      }
    }
  }
}
```

#### B. Practical Example: Multi-Tier Advanced Financial Telemetry
Skenario analitik mendalam: Monitoring gateway transaksi keuangan. Kita akan mengelompokkan data per interval waktu 5 menit, menghitung percentile latensi, mengkalkulasi tingkat kegagalan (*failure rate*) dengan `bucket_script`, dan melacak laju akselerasi transaksi menggunakan `derivative`.

```json
POST /payment_transactions/_search
{
  "size": 0,
  "query": {
    "range": {
      "timestamp": {
        "gte": "now-6h"
      }
    }
  },
  "aggs": {
    "transactions_over_time": {
      "date_histogram": {
        "field": "timestamp",
        "fixed_interval": "5m"
      },
      "aggs": {
        "total_requests": {
          "value_count": {
            "field": "transaction_id.keyword"
          }
        },
        "latency_percentiles": {
          "percentiles": {
            "field": "latency_ms",
            "percents": [50.0, 95.0, 99.0],
            "tdigest": {
              "compression": 200
            }
          }
        },
        "failed_transactions": {
          "filter": {
            "term": { "status.keyword": "FAILED" }
          }
        },
        "failure_rate": {
          "bucket_script": {
            "buckets_path": {
              "failed": "failed_transactions._count",
              "total": "total_requests"
            },
            "script": "params.total > 0 ? (params.failed / params.total) * 100 : 0"
          }
        },
        "transaction_rate_acceleration": {
          "derivative": {
            "buckets_path": "total_requests"
          }
        }
      }
    },
    "max_failure_rate_window": {
      "max_bucket": {
        "buckets_path": "transactions_over_time>failure_rate"
      }
    }
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Tier-1 Payment Gateway (50.000 Transaksi / Detik)
**Kondisi Awal:**
Sistem pembayaran memproses 50.000 TPS. Tim SRE menjalankan dashboard analitik waktu nyata untuk memantau SLA latensi P99 dan rasio anomali penipuan (*fraud detection*) berdasarkan *gateway partner*.

**Gejala Masalah:**
1. Kluster sering melempar `CircuitBreakerException: [parent] Data too large, data for [<transport_request>] would be [...] which is larger than the limit of [...]`.
2. Node Elasticsearch mengalami *G1GC Allocation Stalls* selama 8-12 detik secara berkala.
3. Kueri agregasi `terms` pada `merchant_uuid` menghasilkan data tidak akurat karena `doc_count_error_upper_bound` mencapai angka ribuan.

**Akar Masalah (Root Cause Analysis):**
1. Agregasi dijalankan di atas field dengan kardinalitas tinggi (`merchant_uuid` mencapai 20 juta nilai unik) menggunakan *sub-aggregations* yang sangat dalam tanpa filter ketat.
2. Agregasi `percentiles` menggunakan konfigurasi default tanpa membatasi horizon waktu, menghabiskan alokasi memori heap untuk ribuan centroid T-Digest per bucket.
3. Parameter `shard_size` tidak ditentukan, memicu deviasi pembacaan top merchant antar-shard.
4. *Global Ordinals* dikonfigurasi secara *lazy loading*, sehingga setiap kali ada penulisan indeks baru (setiap 1 detik), kueri analitik berikutnya harus menanggung beban komputasi rekonsiliasi ordinals di JVM heap.

**Solusi Arsitektural:**

```
[Index Mapping Optimization]
  │── Set "eager_global_ordinals": true pada field merchant_uuid
  │── Pastikan routing key menggunakan tenant_id/partner_id
  │
[Query Optimization Strategy]
  │── Set "shard_size": 1000 untuk menekan doc_count_error_upper_bound mendekati 0
  │── Batasi persentil compression ke angka 100 (cukup akurat untuk 99th percentile)
  │── Terapkan index filtering awal (range timestamp ketat via cold/hot data tiering)
  │
[Cluster Protection Level]
  └── Atur indices.breaker.total.use_real_memory: true
  └── Aktifkan Request Cache untuk slice tanggal historis yang immutable
```

Konfigurasi Mapping Produksi Hasil Mitigasi:
```json
PUT /payment_transactions_v2
{
  "settings": {
    "index": {
      "number_of_shards": 6,
      "number_of_replicas": 1,
      "refresh_interval": "10s",
      "routing.allocation.total_shards_per_node": 2
    }
  },
  "mappings": {
    "properties": {
      "timestamp": { "type": "date" },
      "merchant_uuid": {
        "type": "keyword",
        "eager_global_ordinals": true
      },
      "gateway_id": { "type": "keyword" },
      "latency_ms": { "type": "double" },
      "status": { "type": "keyword" }
    }
  }
}
```

Hasil:
- Penurunan durasi GC Pause dari rata-rata 10 detik menjadi <250ms.
- Latensi kueri analitik P95 turun dari 4.8 detik menjadi 380 milidetik.
- Hilangnya insiden *Circuit Breaker Exception* secara permanen.

---

### 9. Trade-offs

```
                      [ ACCURACY ]
                          ▲
                         / \
                        /   \
                       /     \
  T-Digest Comp: 500  /       \  High shard_size
  High Precision HLL /         \ Exact Global Ordinals
                    /           \
                   /             \
 [ MEMORY COST ]  ◄───────────────► [ QUERY LATENCY ]
  High JVM Heap                     Slow Scatter-Gather
  Circuit Breaker Risk              Long GC Pauses
```

| Pendekatan | Parameter | Trade-off Positif | Trade-off Negatif / Risiko |
| :--- | :--- | :--- | :--- |
| **High Precision HLL++** | `precision_threshold: 40000` | Kesalahan estimasi kardinalitas mendekati <1%. | Menggunakan hingga 320 KB heap per bucket. Jika dikalikan 10.000 bucket = ~3.2 GB Heap teralokasi instan. |
| **High Compression T-Digest** | `compression: 400` | Estimasi tail latency (P99.9) sangat presisi. | Utilisasi CPU meningkat tajam pada proses *centroid clustering* saat merge. |
| **High Shard Size** | `shard_size: 5000` | Menghilangkan *terms aggregation bias* hampir 100%. | Beban payload jaringan (*network serialization*) antar shard dan coordinator melonjak drastis. |
| **Eager Global Ordinals** | `"eager_global_ordinals": true` | Latensi kueri agregasi instan tanpa ada *first-query penalty*. | Memperpanjang waktu *index refresh* dan membebani background write pipeline. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan: Menjalankan Agregasi pada Analysed `text`
- **Gejala**: Error `Fielddata is disabled on text fields by default` atau lonjakan JVM Heap hingga OOM jika `fielddata: true` dipaksa aktif.
- **Solusi**: Jangan pernah melakukan agregasi pada field `text`. Gunakan sub-field `keyword` dengan multi-fields mapping:
```json
"customer_name": {
  "type": "text",
  "fields": {
    "keyword": {
      "type": "keyword",
      "ignore_above": 256
    }
  }
}
```

#### 2. Kesalahan: Ledakan Kombinatorik Bucket (*Bucket Explosion*)
- **Gejala**: Query timeout atau klaster crash akibat agregasi berlapis dengan kardinalitas tinggi:
```json
// ANTI-PATTERN: Menghasilkan 10.000 * 10.000 = 100.000.000 bucket in-memory
"aggs": {
  "users": { "terms": { "field": "user_id.keyword", "size": 10000 },
    "aggs": {
      "ips": { "terms": { "field": "ip_address.keyword", "size": 10000 } }
    }
  }
}
```
- **Solusi**: Gunakan `composite` aggregation jika ingin memproses himpunan data utuh, atau persempit scope menggunakan filter kueri terindeks sebelum mengeksekusi agregasi.

#### 3. Circuit Breaker Trips
- **Error Log**: `org.elasticsearch.common.breaker.CircuitBreakingException: [parent] Data too large...`
- **Mitigasi Cepat di Produksi**:
  1. Hentikan eksekusi kueri agregasi yang sedang berjalan:
     ```json
     POST /_tasks/_cancel?actions=*search*
     ```
  2. Periksa limit memory breaker:
     ```json
     GET /_nodes/stats/breaker
     ```
  3. Pastikan `search.max_buckets` tidak ditingkatkan secara ceroboh (tetap di limit aman `65536`).

---

### 11. Best Practices (Production Checklist)

- [ ] **Data Model & Mapping**:
  - [ ] Nonaktifkan `doc_values: false` pada field yang dipastikan tidak akan pernah diagregasi atau disortir untuk menghemat ruang disk hingga 30%.
  - [ ] Gunakan tipe data numerik terkecil yang sesuai (misal: `short`, `byte`, `scaled_float` daripada selalu menggunakan `long` atau `double`).
  - [ ] Set `"eager_global_ordinals": true` khusus pada field yang sering menjadi target agregasi utama.
- [ ] **Query Construction**:
  - [ ] Selalu tempatkan kueri pembatas di blok `query` (bukan di dalam filter agregasi), agar Elasticsearch mengeksekusi *Index Query Pruning* sebelum mengevaluasi *Doc Values*.
  - [ ] Set `"size": 0` jika Anda hanya membutuhkan komputasi analitik, untuk menghindari overhead deserialisasi dan sorting dokumen hits.
  - [ ] Selalu pantau `doc_count_error_upper_bound` pada agregasi terms. Jika nilainya signifikan dibanding total dokumen, naikkan `shard_size`.
- [ ] **Cluster Optimization**:
  - [ ] Pastikan kapasitas JVM Heap tidak melebihi 31 GB (Compressed OOP limit).
  - [ ] Alokasikan minimal 50% RAM fisik untuk OS Page Cache agar pembacaan Lucene Doc Values tetap berjalan secara in-memory dari filesystem cache.
  - [ ] Gunakan *Index Lifecycle Management (ILM)* untuk melakukan *force merge* indeks historis ke 1 segmen per shard (`max_num_segments=1`), yang mengeliminasi kebutuhan komputasi *Global Ordinals* sama sekali.

---

### 12. Hands-on Practice

Buat seluruh file praktikum di direktori: `hands-on/m02/`

#### File 1: Inisialisasi Environment & Index Mapping (`hands-on/m02/01-setup.sh`)
```bash
#!/usr/bin/env bash
set -euo pipefail

ES_HOST="http://localhost:9200"

echo "=== 1. Menghapus Index Lama Jika Ada ==="
curl -s -X DELETE "$ES_HOST/ecommerce_analytics" || true

echo -e "\n=== 2. Membuat Index dengan Optimized Analytic Mapping ==="
curl -s -X PUT "$ES_HOST/ecommerce_analytics" -H 'Content-Type: application/json' -d'
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 0,
    "index.refresh_interval": "1s"
  },
  "mappings": {
    "properties": {
      "order_id": { "type": "keyword", "doc_values": false },
      "category": { 
        "type": "keyword",
        "eager_global_ordinals": true 
      },
      "payment_channel": { "type": "keyword" },
      "total_amount": { "type": "double" },
      "processing_fee": { "type": "double" },
      "order_timestamp": { "type": "date" }
    }
  }
}'
echo -e "\nIndex ecommerce_analytics berhasil dibuat."
```

#### File 2: Seeder Data Analitik Skala Batch (`hands-on/m02/02-seed.sh`)
```bash
#!/usr/bin/env bash
set -euo pipefail

ES_HOST="http://localhost:9200"

echo "=== Seeding 10 Batch Transaksi eCommerce ==="

cat << 'EOF' > /tmp/es_bulk_data.json
{ "index": { "_index": "ecommerce_analytics" } }
{ "order_id": "ORD-001", "category": "ELECTRONICS", "payment_channel": "CREDIT_CARD", "total_amount": 1250.00, "processing_fee": 25.0, "order_timestamp": "2023-10-01T10:00:00Z" }
{ "index": { "_index": "ecommerce_analytics" } }
{ "order_id": "ORD-002", "category": "ELECTRONICS", "payment_channel": "VA_TRANSFER", "total_amount": 850.00, "processing_fee": 2.0, "order_timestamp": "2023-10-01T10:05:00Z" }
{ "index": { "_index": "ecommerce_analytics" } }
{ "order_id": "ORD-003", "category": "FASHION", "payment_channel": "E_WALLET", "total_amount": 45.00, "processing_fee": 0.5, "order_timestamp": "2023-10-01T10:10:00Z" }
{ "index": { "_index": "ecommerce_analytics" } }
{ "order_id": "ORD-004", "category": "FASHION", "payment_channel": "CREDIT_CARD", "total_amount": 120.00, "processing_fee": 2.4, "order_timestamp": "2023-10-01T10:15:00Z" }
{ "index": { "_index": "ecommerce_analytics" } }
{ "order_id": "ORD-005", "category": "HOME", "payment_channel": "VA_TRANSFER", "total_amount": 310.00, "processing_fee": 2.0, "order_timestamp": "2023-10-01T10:20:00Z" }
{ "index": { "_index": "ecommerce_analytics" } }
{ "order_id": "ORD-006", "category": "ELECTRONICS", "payment_channel": "CREDIT_CARD", "total_amount": 3400.00, "processing_fee": 68.0, "order_timestamp": "2023-10-01T11:00:00Z" }
{ "index": { "_index": "ecommerce_analytics" } }
{ "order_id": "ORD-007", "category": "FASHION", "payment_channel": "E_WALLET", "total_amount": 65.00, "processing_fee": 0.7, "order_timestamp": "2023-10-01T11:15:00Z" }
{ "index": { "_index": "ecommerce_analytics" } }
{ "order_id": "ORD-008", "category": "GROCERIES", "payment_channel": "E_WALLET", "total_amount": 80.00, "processing_fee": 0.8, "order_timestamp": "2023-10-01T11:30:00Z" }
{ "index": { "_index": "ecommerce_analytics" } }
{ "order_id": "ORD-009", "category": "ELECTRONICS", "payment_channel": "VA_TRANSFER", "total_amount": 2100.00, "processing_fee": 2.0, "order_timestamp": "2023-10-01T12:00:00Z" }
{ "index": { "_index": "ecommerce_analytics" } }
{ "order_id": "ORD-010", "category": "GROCERIES", "payment_channel": "VA_TRANSFER", "total_amount": 150.00, "processing_fee": 2.0, "order_timestamp": "2023-10-01T12:30:00Z" }
EOF

curl -s -X POST "$ES_HOST/_bulk" -H 'Content-Type: application/x-ndjson' --data-binary @/tmp/es_bulk_data.json > /dev/null
rm -f /tmp/es_bulk_data.json
curl -s -X POST "$ES_HOST/ecommerce_analytics/_refresh"
echo "Seeding selesai. Dokumen telah siap diuji."
```

#### File 3: Kompleks Pipeline & Stats Analytics (`hands-on/m02/03-complex-agg.sh`)
```bash
#!/usr/bin/env bash
set -euo pipefail

ES_HOST="http://localhost:9200"

echo "=== Menjalankan Analisis Margin & Volume Transaksi Bertingkat ==="

curl -s -X POST "$ES_HOST/ecommerce_analytics/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "size": 0,
  "aggs": {
    "sales_per_hour": {
      "date_histogram": {
        "field": "order_timestamp",
        "fixed_interval": "1h"
      },
      "aggs": {
        "gross_sales": {
          "sum": { "field": "total_amount" }
        },
        "total_fee": {
          "sum": { "field": "processing_fee" }
        },
        "net_revenue": {
          "bucket_script": {
            "buckets_path": {
              "gross": "gross_sales",
              "fee": "total_fee"
            },
            "script": "params.gross - params.fee"
          }
        },
        "cumulative_gross": {
          "cumulative_sum": {
            "buckets_path": "gross_sales"
          }
        }
      }
    },
    "max_hourly_revenue": {
      "max_bucket": {
        "buckets_path": "sales_per_hour>net_revenue"
      }
    }
  }
}'
```

#### File 4: Python Composite Pagination Engine (`hands-on/m02/04-composite-exporter.py`)
```python
#!/usr/bin/env python3
import json
import urllib.request
import sys

ES_ENDPOINT = "http://localhost:9200/ecommerce_analytics/_search"

def run_composite_export():
    payload = {
        "size": 0,
        "aggs": {
            "paginate_categories": {
                "composite": {
                    "size": 2,
                    "sources": [
                        {"category": {"terms": {"field": "category"}}},
                        {"payment": {"terms": {"field": "payment_channel"}}}
                    ]
                },
                "aggs": {
                    "bucket_volume": {"sum": {"field": "total_amount"}}
                }
            }
        }
    }

    page = 1
    while True:
        req = urllib.request.Request(
            ES_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"Error fetching data: {e}", file=sys.stderr)
            break

        composite = data.get("aggregations", {}).get("paginate_categories", {})
        buckets = composite.get("buckets", [])
        
        if not buckets:
            print("Paginasi selesai: Seluruh kombinasi bucket telah terekstraksi.")
            break

        print(f"\n--- Halaman {page} ---")
        for b in buckets:
            print(f"Kombinasi: {b['key']} -> Volume: ${b['bucket_volume']['value']:,.2f}")

        after_key = composite.get("after_key")
        if not after_key:
            break
            
        payload["aggs"]["paginate_categories"]["composite"]["after"] = after_key
        page += 1

if __name__ == "__main__":
    run_composite_export()
```

---

### 13. Exercise

#### Level Easy
Eksekusi sebuah kueri agregasi metrik sederhana untuk mencari nilai rata-rata (`avg`), nilai minimum (`min`), dan nilai maksimum (`max`) dari `total_amount` pada indeks `ecommerce_analytics`.
- **Kriteria Keberhasilan**: Output JSON hanya menampilkan block metrik tanpa mengembalikan hit dokumen (`size: 0`).

#### Level Medium
Buat kueri agregasi `terms` pada field `category` yang mengurutkan kategori bukan berdasarkan jumlah dokumen (`_count`), melainkan berdasarkan metrik turunan: nilai rata-rata biaya proses transaksi (`avg_fee`).
- **Petunjuk**: Gunakan sub-aggregation metric bernama `avg_fee` dan sematkan parameter `"order": { "avg_fee": "desc" }` pada bucket `terms`.

#### Level Hard
Buat agregasi bertingkat:
1. Kelompokkan data per `category`.
2. Di dalam masing-masing kategori, kelompokkan kembali per `payment_channel`.
3. Hitung persentil latensi ke-95 (`P95`) serta *cardinality* unik dari `order_id`.
4. Tambahkan *Pipeline Aggregation* (`bucket_selector`) untuk membuang bucket yang memiliki total volume transaksi di bawah `$100.00`.
- **Kriteria Keberhasilan**: Bucket dengan volume rendah otomatis tereliminasi dari output respon.

---

### 14. Challenge

**Skenario**:
Anda adalah Principal Infrastructure Architect pada perusahaan *Cybersecurity Telemetry*. Anda memiliki indeks log koneksi firewall sebesar **2,5 Miliar dokumen per hari** yang terdistribusi ke dalam 12 shards.
Sistem membutuhkan deteksi *Data Exfiltration Anomaly*:
- Anda harus mengidentifikasi alamat IP pengirim (`src_ip`) unik yang mentransfer bytes (`bytes_sent`) di atas batas $3\sigma$ (tiga standar deviasi) dari rata-rata transfer IP lain dalam window 15 menit terakhir.
- Batasan Keras Produksi (*SLA*):
  1. Kueri harus dieksekusi di bawah **800ms**.
  2. Alokasi memori query dilarang memicu *Request Circuit Breaker* (batas heap aman klaster: 65%).
  3. Hindari *Terms Shard Bias* karena serangan sering tersembunyi di shard dengan volume traffic kecil.

**Tugas Anda**:
Rancang strategi end-to-end tanpa solusi instan:
1. Definisikan mapping indeks optimal (struktur tipe data, doc_values, sub-fields, routing key).
2. Tuliskan query DSL lengkap menggunakan kombinasi `extended_stats_bucket`, `bucket_script`, dan `bucket_selector`.
3. Tentukan parameter `shard_size` yang matematis dan berikan justifikasi teknis trade-off memori vs akurasi dari rancangan Anda.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (5 Soal)
1. **Mengapa agregasi pada field bertipe `text` dinonaktifkan secara default oleh Elasticsearch?**
   - *Jawaban*: Karena field `text` menggunakan *Inverted Index* yang dioptimasi untuk pencarian, bukan *Doc Values*. Mengaktifkannya memaksa penggunaan *Fielddata* di dalam JVM Heap yang dapat memicu *OutOfMemoryError* dan *Garbage Collection pause* yang masif.
2. **Apa fungsi utama dari parameter `"size": 0` dalam search request yang mengandung agregasi?**
   - *Jawaban*: Menginstruksikan Elasticsearch untuk tidak mengembalikan atau melakukan proses sorting/fetching terhadap hit dokumen individual, sehingga menghemat CPU, memori, dan bandwidth jaringan coordinator node.
3. **Struktur data internal apa yang digunakan secara default oleh Lucene untuk mengeksekusi agregasi pada field `keyword` dan numerik?**
   - *Jawaban*: *Doc Values* (format penyimpanan kolom yang disimpan di disk dan memanfaatkan OS Filesystem Page Cache).
4. **Apa perbedaan mendasar antara *Metric Aggregation* dan *Bucket Aggregation*?**
   - *Jawaban*: *Bucket Aggregation* mengelompokkan dokumen ke dalam himpunan-himpunan (koleksi) berdasarkan kriteria tertentu (mirip `GROUP BY`), sedangkan *Metric Aggregation* menghitung nilai matematika/statistik (seperti `sum`, `avg`, `percentiles`) dari dokumen-dokumen dalam suatu himpunan.
5. **Kapan *Global Ordinals* dibangun jika sebuah field tidak dikonfigurasi dengan `eager_global_ordinals`?**
   - *Jawaban*: Dibangun secara *on-demand* (*lazy loading*) saat kueri pencarian/agregasi pertama kali mengeksekusi field tersebut setelah terjadinya perubahan atau refresh segmen.

#### B. Pertanyaan Intermediate (5 Soal)
1. **Mengapa metrik `doc_count_error_upper_bound` bisa bernilai lebih dari 0 pada agregasi `terms` terdistribusi?**
   - *Jawaban*: Karena mekanisme *Scatter-Gather* hanya mengembalikan *top-K* dokumen lokal per shard (`shard_size`). Jika dokumen berada di luar batas *top-K* pada suatu shard namun memiliki frekuensi di shard lain, koordinator mengestimasikan batas maksimum dokumen yang berpotensi terlewatkan.
2. **Bagaimana algoritma HyperLogLog++ meminimalkan penggunaan memori saat menghitung kardinalitas untuk himpunan data kecil?**
   - *Jawaban*: Menggunakan representasi *Sparse* (himpunan dinamis hemat memori yang hanya mencatat indeks register bernilai) sebelum secara otomatis beralih ke representasi *Dense* (array bit tetap) ketika jumlah data mencapai ambang batas tertentu.
3. **Apa perbedaan antara *Parent Pipeline Aggregation* dan *Sibling Pipeline Aggregation*?**
   - *Jawaban*: *Parent Pipeline Aggregation* menambahkan metrik komputasi baru ke dalam struktur bucket tempat ia didefinisikan (mengubah atau melengkapi bucket induk), sedangkan *Sibling Pipeline Aggregation* mengonsumsi seluruh bucket target untuk menghasilkan output agregasi baru yang sejajar/independen dari bucket tersebut.
4. **Bagaimana parameter `compression` pada algoritma T-Digest mempengaruhi akurasi agregasi persentil?**
   - *Jawaban*: Menentukan rasio jumlah *Centroid*. Semakin tinggi nilai `compression`, semakin banyak centroid yang dialokasikan, meningkatkan akurasi estimasi kuantil (terutama pada *extreme tails* seperti P99.9) dengan konsekuensi kenaikan penggunaan memori JVM Heap secara proporsional.
5. **Mengapa `composite` aggregation lebih disarankan untuk ekstraksi data skala besar dibandingkan paginasi `terms` aggregation berbasis `size`?**
   - *Jawaban*: Karena `composite` aggregation memproses dataset menggunakan kursor pointer tetap (`after_key`) secara streaming dan efisien tanpa batas kedalaman memori (`max_buckets`), menghindari pemborosan alokasi memori heap yang dialami oleh `terms` aggregation bernilai `size` raksasa.

#### C. Skenario Kasus Produksi (3 Soal)

1. **Skenario 1**:
   *Sebuah cluster log APM Elasticsearch sering kali menolak query agregasi dengan status `CircuitBreakingException` pada jam sibuk. Parameter `indices.breaker.total.use_real_memory` bernilai `true`.*
   **Analisis**: Apa yang sebenarnya terjadi, dan langkah konfigurasi apa yang harus dievaluasi di tingkat mapping dan query?
   - *Jawaban*: Circuit Breaker mendeteksi bahwa total penggunaan memori heap fisik JVM (termasuk memori query dan background memory) telah melampaui batas ambang aman (biasanya 70-95% dari heap).
   *Solusi*: 
     1) Pastikan query tidak mengeksekusi agregasi *high-cardinality* tanpa batas atau nested buckets yang meledak;
     2) Gunakan `composite` aggregation atau batasi `max_buckets`;
     3) Ganti field pencarian string dari `text` ke `keyword`;
     4) Terapkan filter range tanggal yang lebih kecil untuk mengurangi populasi dokumen yang dipindai Doc Values.

2. **Skenario 2**:
   *Setelah melakukan reindex harian data analitik (500 juta dokumen), query agregasi analitik pertama selalu membutuhkan waktu 45 detik (timeout), namun query kedua dan seterusnya berjalan normal di bawah 500ms.*
   **Analisis**: Mekanisme internal apa yang menjadi penyebab *latency penalty* tersebut, dan bagaimana solusinya?
   - *Jawaban*: Penyebab utamanya adalah pembangunan *Global Ordinals* secara *lazy* pada field kategori/keyword saat query pertama kali dieksekusi di seluruh shard baru.
   *Solusi*: Tambahkan konfigurasikan `"eager_global_ordinals": true` pada field mapping terkait. Dengan begitu, Elasticsearch akan membangun struktur ordinals di latar belakang saat proses *refresh/indexing*, membebaskan kueri analitik dari beban pemetaan awal.

3. **Skenario 3**:
   *Dalam perhitungan rasio kegagalan transaksi menggunakan `bucket_script`, beberapa interval waktu menghasilkan error atau nilai bucket kosong (`null`) karena tidak ada transaksi yang tercatat pada rentang waktu tersebut (division by zero).*
   **Analisis**: Bagaimana cara menstabilkan pipeline script tersebut agar robust terhadap kondisi data kosong?
   - *Jawaban*: Menggunakan penanganan null-safe pada ekspresi script painless dan memanfaatkan parameter `gap_policy`. Contoh script: `params.total != null && params.total > 0 ? (params.failed / params.total) * 100 : 0`. Pada definisi agregasi pipeline, set `"gap_policy": "insert_zeros"` agar bucket yang hilang secara otomatis dianggap bernilai 0 dan tidak merusak rantai komputasi pipeline.

---

### 16. Summary

1. **Pondasi Arsitektur**: Komputasi analitik Elasticsearch bertumpu pada **Lucene Doc Values** (penyimpanan kolom berbasis disk dan OS page cache), menjauhkan JVM heap dari saturasi data dokumen mentah.
2. **Global Ordinals Optimization**: Merupakan kunci performa agregasi `keyword`. Gunakan `"eager_global_ordinals": true` pada field frekuensi tinggi untuk mengeliminasi lonjakan latensi kueri pertama (*first-query penalty*).
3. **Presisi Terdistribusi**: Pahami bias scatter-gather pada agregasi `terms`. Selalu pantau `doc_count_error_upper_bound` dan kalibrasi parameter `shard_size` untuk mencapai keseimbangan antara akurasi absolut dan overhead transmisi jaringan.
4. **Algoritma Aproksimasi**: HyperLogLog++ dan T-Digest memungkinkan kalkulasi kardinalitas dan persentil berskala raksasa dengan jejak memori terprediksi ($O(1)$ relatif terhadap total volume dokumen), asalkan parameter `precision_threshold` dan `compression` dikonfigurasi secara proporsional.
5. **Komputasi Berlapis**: Manfaatkan *Pipeline Aggregations* untuk menggeser beban logika analitik (seperti derivatif, standar deviasi, dan rasio antar metrik) langsung ke dalam engine Elasticsearch, menghilangkan kebutuhan post-processing berat di sisi aplikasi backend.