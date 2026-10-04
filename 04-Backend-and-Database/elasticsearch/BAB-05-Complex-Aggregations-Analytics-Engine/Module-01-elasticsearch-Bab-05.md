# Bab 05 Module 01: Complex Aggregations & Analytics Engine

---

## Seksi 01: Identitas Modul
* **Mata Pelajaran:** Elasticsearch Architecture & Engineering
* **Kategori:** 04-Backend-and-Database
* **Nomor Modul:** Bab 05 Module 01
* **Judul Modul:** Complex Aggregations & Analytics Engine
* **Tingkat Kesulitan:** Advanced / Principal Engineer
* **Prasyarat:** Pemahaman mendalam tentang Inverted Index, Doc Values, Segment Architecture, Dasar Query DSL (Term, Range, Bool), dan Pengaturan Sharding.

---

## Seksi 02: Learning Objectives
Setelah menyelesaikan modul ini, Anda akan mampu:
1. **Menganalisis & Mendesain Arsitektur Analitik:** Membedakan eksekusi internal antara Metric, Bucket, Matrix, dan Pipeline Aggregations pada level Lucene Segment dan Off-Heap memory.
2. **Mengoptimalkan Pipeline Aggregations:** Mengimplementasikan kalkulasi multi-tier (Sibling vs. Parent) seperti *Moving Average*, *Derivative*, dan *Serial Differencing* pada dataset bervolume tinggi.
3. **Mencegah Memory Bloat & Circuit Breaking:** Mengontrol alokasi memori heap, string deduplication (Global Ordinals), dan sizing execution memory menggunakan `breadth_first` vs `depth_first` collection modes.
4. **Menerapkan Composite & Matrix Aggregations:** Merancang analitik berskala masif dengan pagination yang aman dari *OOM (Out Of Memory)* via `composite` aggregation.

---

## Seksi 03: Concept Map Diagram ASCII
```
+-------------------------------------------------------------------------------+
|                      ELASTICSEARCH ANALYTICS ENGINE                           |
+-------------------------------------------------------------------------------+
                                      |
         +----------------------------+----------------------------+
         |                                                         |
         v                                                         v
+-------------------------------+                         +---------------------+
|      BUCKET AGGREGATIONS      |                         | METRIC AGGREGATIONS |
| (Partisi Dokumen ke Kumpulan) |                         | (Kalkulasi Nilai)   |
+-------------------------------+                         +---------------------+
  |-- Terms (Global Ordinals)                               |-- Min / Max / Avg
  |-- Date Histogram                                        |-- Extended Stats
  |-- Composite (Pagination/Stream)                         |-- Cardinality (HLL)
  |-- Filter / Nested / Children                            |-- Top Metrics
         \                                                         /
          \                                                       /
           +--------------------------+--------------------------+
                                      |
                                      v
                       +-----------------------------+
                       |    PIPELINE AGGREGATIONS    |
                       | (Analisis Hasil Aggregasi)  |
                       +-----------------------------+
                                      |
                     +----------------+----------------+
                     |                                 |
                     v                                 v
        +-------------------------+       +--------------------------+
        |   PARENT PIPELINE AGGS  |       |   SIBLING PIPELINE AGGS  |
        | (Transformasi Internal) |       | (Perhitungan Antar-Tier) |
        +-------------------------+       +--------------------------+
        |-- Derivative            |       |-- Min/Max/Avg Bucket     |
        |-- Moving Function (Avg) |       |-- Stats / Extended Stats |
        |-- Cumulative Sum        |       |-- Percentiles Bucket     |
        |-- Bucket Script         |       +--------------------------+
        +-------------------------+
```

---

## Seksi 04: Mengapa Relevan
Dalam komputasi analitik backend skala terdistribusi, kebutuhan untuk menghasilkan business intelligence, deteksi anomali finansial, dan visualisasi metrik secara real-time tidak dapat lagi dipenuhi oleh relational database (RDBMS) standar atau batch-processing engines (seperti Hadoop) yang memiliki latency tinggi.

Elasticsearch menyediakan mesin analitik hybrid yang menggabungkan:
1. **Kecepatan Mesin Pencari:** Menggunakan struktur data kolumnar (*Doc Values*) yang di-*memory-map* (mmap) langsung ke file system cache.
2. **Kapasitas Analitik Kompleks Multi-Tier:** Mengeksekusi jutaan kalkulasi statistik terdistribusi langsung di tingkat shard (*scatter-gather phase*) tanpa perlu memindahkan raw data melintasi network fabric.
3. **Optimasi Penggunaan Memori:** Kemampuan untuk beralih antara algoritma exact dan probabilistik (seperti HyperLogLog++ untuk kardinalitas tinggi dan T-Digest untuk estimasi persentil).

---

## Seksi 05: Anatomi Konsep Inti

### 1. Struktur Data Kolumnar: Doc Values vs. Fielddata
* **Doc Values:** Struktur data *on-disk* berbasis kolom yang dibuat saat proses indexing dan di-mmap ke OS Page Cache. Digunakan untuk semua aggregasi numerik, date, geo, dan `keyword`.
* **Fielddata:** Struktur data in-memory (JVM Heap) yang dibangun secara dinamis saat runtime hanya untuk field bertipe `text`. *Sangat berbahaya di level produksi karena memicu garbage collection thrashing dan OOM.*

### 2. Global Ordinals & Execution Modes
Pada field `keyword`, Elasticsearch menggunakan *Ordinals* (pemetaan integer lokal terhadap string pada level segment). Ketika melakukan aggregation lintas-segment, dibentuk **Global Ordinals**.
* `collect_mode: depth_first` (Default): Menelusuri seluruh cabang pohon agregasi secara mendalam. Efektif jika kardinalitas cabang kecil.
* `collect_mode: breadth_first`: Memotong cabang (*pruning*) pada bucket tingkat atas sebelum menghitung sub-agregasi. Wajib digunakan jika sub-agregasi memiliki kardinalitas tinggi.

### 3. Pipeline Aggregations: Parent vs. Sibling
* **Parent Pipeline:** Menerima input dari bucket induknya dan menghasilkan metrik baru di dalam bucket yang sama (misal: menghitung turunan / *derivative* atau *cumulative sum* per bulan).
* **Sibling Pipeline:** Menerima input dari semua bucket yang setara (*sibling*) dan menghasilkan metrik di luar bucket tersebut (misal: mencari rata-rata penjualan bulanan tertinggi).

---

## Seksi 06: Panduan Implementasi Step-by-Step

### Tahap 1: Persiapan Index dengan Pemetaan Kolumnar yang Tepat
Pastikan field yang akan di-aggregasi bertipe numeric, date, atau `keyword` (doc_values enabled). Hindari aggregasi pada tipe `text`.

### Tahap 2: Menentukan Strategi Bucketing
Gunakan `date_histogram` untuk analisis berbasis rentang waktu, dikombinasikan dengan `terms` untuk kategorisasi. Terapkan `execution_hint` atau `collect_mode: breadth_first` jika data memiliki kardinalitas tinggi.

### Tahap 3: Konstruksi Metrik & Sibling/Parent Pipelines
Tentukan jalur metrik menggunakan format *Buckets Path Syntax*:
`"buckets_path": "parent_bucket>sub_bucket>metric_target"`

---

## Seksi 07: Contoh Kasus Sederhana

Berikut adalah contoh aggregasi `date_histogram` bulanan dengan kalkulasi `derivative` untuk memantau fluktuasi *Month-over-Month (MoM) Transaction Growth*:

```json
POST /ecommerce-orders/_search
{
  "size": 0,
  "aggs": {
    "orders_over_time": {
      "date_histogram": {
        "field": "transaction_date",
        "calendar_interval": "month"
      },
      "aggs": {
        "total_sales": {
          "sum": {
            "field": "amount"
          }
        },
        "sales_derivative": {
          "derivative": {
            "buckets_path": "total_sales"
          }
        }
      }
    }
  }
}
```

---

## Seksi 08: Implementasi Production-Grade Lengkap Kode

Studi Kasus: Sistem Financial Trading & Fraud Detection Engine.
Kebutuhan:
1. Analisis volume transaksi bulanan berdasarkan *merchant tier*.
2. Estimasi persentil latensi pemrosesan (T-Digest Algorithm).
3. Deteksi deviasi transaksi menggunakan `moving_fn` (Exponential Moving Average).
4. Sibling pipeline untuk mencari varians nilai transaksi maksimum antar merchant.

### 1. Index Template & Mappings

```json
PUT /_index_template/financial_tx_template
{
  "index_patterns": ["financial-transactions-*"],
  "template": {
    "settings": {
      "number_of_shards": 3,
      "number_of_replicas": 1,
      "index.mapping.total_fields.limit": 2000,
      "index.queries.cache.enabled": true
    },
    "mappings": {
      "dynamic": "strict",
      "properties": {
        "transaction_id": { "type": "keyword", "doc_values": true },
        "merchant_id": { "type": "keyword", "eager_global_ordinals": true },
        "merchant_tier": { "type": "keyword" },
        "amount": { "type": "scaled_float", "scaling_factor": 100 },
        "processing_latency_ms": { "type": "integer" },
        "timestamp": { "type": "date" },
        "risk_score": { "type": "half_float" }
      }
    }
  }
}
```

### 2. Complex Multi-Tier Aggregation Script

```json
POST /financial-transactions-*/_search
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        {
          "range": {
            "timestamp": {
              "gte": "now-6M/M",
              "lte": "now"
            }
          }
        }
      ]
    }
  },
  "aggs": {
    "merchant_tier_partition": {
      "terms": {
        "field": "merchant_tier",
        "size": 5,
        "collect_mode": "breadth_first",
        "order": { "total_tier_revenue": "desc" }
      },
      "aggs": {
        "total_tier_revenue": {
          "sum": { "field": "amount" }
        },
        "monthly_trend": {
          "date_histogram": {
            "field": "timestamp",
            "calendar_interval": "month",
            "extended_bounds": {
              "min": "now-6M/M",
              "max": "now"
            },
            "min_doc_count": 0
          },
          "aggs": {
            "monthly_revenue": {
              "sum": { "field": "amount" }
            },
            "latency_percentiles": {
              "percentiles": {
                "field": "processing_latency_ms",
                "percents": [50.0, 95.0, 99.0],
                "tdigest": { "compression": 200 }
              }
            },
            "revenue_moving_avg": {
              "moving_fn": {
                "buckets_path": "monthly_revenue",
                "window": 3,
                "script": "MovingFunctions.unweightedAvg(values)"
              }
            },
            "revenue_anomaly_deviation": {
              "bucket_script": {
                "buckets_path": {
                  "actual": "monthly_revenue",
                  "predicted": "revenue_moving_avg"
                },
                "script": "params.predicted != null && params.predicted > 0 ? ((params.actual - params.predicted) / params.predicted) * 100 : 0"
              }
            }
          }
        },
        "max_monthly_revenue_in_tier": {
          "max_bucket": {
            "buckets_path": "monthly_trend>monthly_revenue"
          }
        }
      }
    },
    "global_highest_tier_peak": {
      "max_bucket": {
        "buckets_path": "merchant_tier_partition>max_monthly_revenue_in_tier"
      }
    }
  }
}
```

---

## Seksi 09: Diagram Alur Kerja ASCII

```
QUERY EXECUTION (Scatter-Gather Phase)
=====================================

  Client Request (Aggregations)
         |
         v
+------------------+
| Coordinator Node |
+------------------+
         |
         |-- Dispatch Sub-Requests ke Data Shards
         |
         +-----------------------+-----------------------+
         |                       |                       |
         v                       v                       v
  +--------------+        +--------------+        +--------------+
  | Data Shard 1 |        | Data Shard 2 |        | Data Shard 3 |
  +--------------+        +--------------+        +--------------+
  | Read DocVals |        | Read DocVals |        | Read DocVals |
  | Local Buckets|        | Local Buckets|        | Local Buckets|
  | Partial Aggs |        | Partial Aggs |        | Partial Aggs |
  +--------------+        +--------------+        +--------------+
         \                       |                       /
          \                      |                      /
           +---------------------+---------------------+
                                 | (Collect Partial Results)
                                 v
                     +------------------------+
                     | Coordinator Node       |
                     | (Reduce Phase)         |
                     | - Merge Bucket Trees   |
                     | - Execute Pipelines:   |
                     |   * Moving Average     |
                     |   * Bucket Scripts     |
                     |   * Sibling Reductions |
                     +------------------------+
                                 |
                                 v
                       Final JSON to Client
```

---

## Seksi 10: Analisis Trade-offs

| Pendekatan / Fitur | Keuntungan | Kompensasi / Kelemahan | Kasus Penggunaan Ideal |
| :--- | :--- | :--- | :--- |
| **`collect_mode: breadth_first`** | Mencegah ledakan memori kombinatorial pada nested aggregations. | Membutuhkan buffering per level; sedikit penalti CPU saat pruning. | Terms aggregation dengan sub-agregasi ber-kardinalitas tinggi. |
| **`eager_global_ordinals: true`** | Memangkas latensi query pertama setelah indexing/refresh. | Menambah waktu dan beban memori saat refresh/flush segment. | Dashboard agregasi intensif dengan SLA latensi ketat. |
| **HyperLogLog++ (Cardinality)** | Penggunaan memori konstan ($O(1)$) untuk miliaran dokumen unik. | Hasil bersifat aproksimasi (ada margin of error, default ~1-5%). | Analisis *Unique Visitors* harian/bulanan dalam skala besar. |
| **T-Digest Compression** | Akurasi persentil ekstrem ($p99$, $p99.9$) dapat dikontrol via setting. | Nilai `compression` yang tinggi mengonsumsi lebih banyak JVM heap. | Monitoring SLA latensi jaringan dan audit transaksi keuangan. |

---

## Seksi 11: Best Practices & Antipatterns

### Best Practices:
1. **Gunakan Filter Context Sebelum Aggs:** Selalu persempit dokumen setara mungkin menggunakan blok `query.bool.filter` agar Doc Values evaluation hanya berjalan pada subset dokumen.
2. **Kendalikan Shard Request Size:** Jangan set `size: 0` pada Terms aggregation di multi-shard tanpa memperhitungkan `shard_size` untuk menghindari distorsi perankingan data terdistribusi.
3. **Partitioning Large Datasets:** Gunakan `composite` aggregation jika client membutuhkan paging pada jutaan bucket analitik.

### Antipatterns yang Dilarang:
* **Mengeksekusi Aggregation pada Field `text`:** Memicu pembangunan Fielddata pada JVM heap yang dapat memicu crash cluster seketika.
* **Over-allocation pada Terms Sizing:** Meminta `size: 10000` pada Terms aggregation bertingkat tanpa `breadth_first`.
* **Deep Nesting Pipeline Aggregations:** Membuat chain lebih dari 5 tingkat pipeline aggs yang menyebabkan coordinator node kehabisan alokasi thread pool per request.

---

## Seksi 12: Security Hardening

```json
# Role definition dengan batasan pembacaan field dan eksekusi query script analitik
POST /_security/role/analytics_auditor_role
{
  "indices": [
    {
      "names": [ "financial-transactions-*" ],
      "privileges": [ "read", "view_index_metadata" ],
      "field_security": {
        "grant": [
          "merchant_tier",
          "amount",
          "processing_latency_ms",
          "timestamp"
        ],
        "except": [ "merchant_id", "transaction_id" ]
      },
      "query": "{\"term\": {\"merchant_tier\": \"TIER_1\"}}"
    }
  ],
  "applications": [],
  "run_as": [],
  "metadata": {
    "environment": "production"
  }
}
```

Pastikan script analitik inline (`Painless`) dibatasi melalui alokasi resource context di `elasticsearch.yml`:
```yaml
script.painless.regex.enabled: false
script.max_compilations_rate: 150/1m
```

---

## Seksi 13: Observabilitas & Debugging

Gunakan Profile API untuk mendeteksi *bottleneck* shard execution time:

```json
POST /financial-transactions-*/_search
{
  "profile": true,
  "size": 0,
  "aggs": {
    "merchant_tier_partition": {
      "terms": { "field": "merchant_tier" },
      "aggs": {
        "revenue": { "sum": { "field": "amount" } }
      }
    }
  }
}
```

Analisis output profile:
* `build_aggregation`: Waktu yang dihabiskan untuk membaca Doc Values dari disk cache.
* `collect`: Waktu yang digunakan untuk memasukkan nilai ke dalam struktur bucket Lucene.
* `reduce`: Waktu penggabungan data pada level coordinator.

Monitoring JVM Memory Circuit Breaker:
```bash
GET /_nodes/stats/breaker
```
Pantau metrik `parent.tripped` dan `fielddata.tripped` untuk memastikan aggregasi tidak menyentuh limit proteksi memori.

---

## Seksi 14: Benchmarking & Performance

Jalankan pengujian konkurensi analitik menggunakan `esrally`:

```bash
esrally race \
  --track=eventdata \
  --challenge=append-no-conflicts-index-only \
  --target-hosts=127.0.0.1:9200 \
  --pipeline=benchmark-only \
  --track-params="bulk_size:5000"
```

Konfigurasi pengujian Aggregation Latency:
```json
{
  "name": "complex-monthly-agg",
  "operation-type": "search",
  "index": "financial-transactions-*",
  "body": {
    "size": 0,
    "aggs": {
      "tiers": {
        "terms": { "field": "merchant_tier", "collect_mode": "breadth_first" },
        "aggs": {
          "monthly": {
            "date_histogram": { "field": "timestamp", "calendar_interval": "month" },
            "aggs": { "sum_amount": { "sum": { "field": "amount" } } }
          }
        }
      }
    }
  },
  "clients": 16,
  "warmup-iterations": 500,
  "iterations": 2000
}
```

---

## Seksi 15: Hands-on Lab Mini-Project

### Skenario:
Implementasikan pipeline deteksi anomali pada log HTTP gateway untuk menemukan request spikes dan menghitung 99th latency anomaly ratio.

```bash
# 1. Setup Data Mocking
POST /gateway-access-logs/_bulk
{"index":{}}
{"timestamp":"2026-03-30T01:00:00Z","service":"auth-svc","response_time_ms":45,"status":200}
{"index":{}}
{"timestamp":"2026-03-30T01:05:00Z","service":"auth-svc","response_time_ms":55,"status":200}
{"index":{}}
{"timestamp":"2026-03-30T01:10:00Z","service":"auth-svc","response_time_ms":450,"status":500}
{"index":{}}
{"timestamp":"2026-03-30T01:15:00Z","service":"auth-svc","response_time_ms":60,"status":200}
{"index":{}}
{"timestamp":"2026-03-30T01:20:00Z","service":"auth-svc","response_time_ms":500,"status":504}
```

### Script Aggregasi untuk Mini-Project:
```json
POST /gateway-access-logs/_search
{
  "size": 0,
  "aggs": {
    "services": {
      "terms": { "field": "service.keyword" },
      "aggs": {
        "interval_metrics": {
          "date_histogram": {
            "field": "timestamp",
            "fixed_interval": "5m"
          },
          "aggs": {
            "p99_latency": {
              "percentiles": {
                "field": "response_time_ms",
                "percents": [99.0]
              }
            },
            "p99_derivative": {
              "derivative": {
                "buckets_path": "p99_latency.99.0"
              }
            }
          }
        }
      }
    }
  }
}
```

---

## Seksi 16: Automated Testing & Verification

Gunakan Python test suite berikut untuk memvalidasi eksekusi aggregation:

```python
import unittest
from elasticsearch import Elasticsearch

class TestAnalyticsEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.es = Elasticsearch("http://localhost:9200")
        cls.index_name = "test-analytics-verification"
        cls.es.indices.create(
            index=cls.index_name,
            body={
                "mappings": {
                    "properties": {
                        "category": {"type": "keyword"},
                        "value": {"type": "double"},
                        "date": {"type": "date"}
                    }
                }
            },
            ignore=400
        )
        # Bulk Insert Data
        actions = [
            {"index": {"_index": cls.index_name}},
            {"category": "A", "value": 100.0, "date": "2026-01-01T00:00:00Z"},
            {"index": {"_index": cls.index_name}},
            {"category": "A", "value": 200.0, "date": "2026-02-01T00:00:00Z"},
            {"index": {"_index": cls.index_name}},
            {"category": "B", "value": 500.0, "date": "2026-01-01T00:00:00Z"}
        ]
        cls.es.bulk(operations=actions, refresh=True)

    def test_pipeline_derivative_aggregation(self):
        query = {
            "size": 0,
            "aggs": {
                "by_date": {
                    "date_histogram": {
                        "field": "date",
                        "calendar_interval": "month"
                    },
                    "aggs": {
                        "sum_val": {"sum": {"field": "value"}},
                        "val_derivative": {"derivative": {"buckets_path": "sum_val"}}
                    }
                }
            }
        }
        res = self.es.search(index=self.index_name, body=query)
        buckets = res["aggregations"]["by_date"]["buckets"]
        
        self.assertEqual(len(buckets), 2)
        self.assertIn("val_derivative", buckets[1])
        # Month 1 sum = 600, Month 2 sum = 200. Derivative = -400.0
        self.assertEqual(buckets[1]["val_derivative"]["value"], -400.0)

    @classmethod
    def tearDownClass(cls):
        cls.es.indices.delete(index=cls.index_name, ignore=[400, 404])

if __name__ == "__main__":
    unittest.main()
```

---

## Seksi 17: Troubleshooting Guide

| Gejala Masalah | Potensi Root Cause | Tindakan Resolusi |
| :--- | :--- | :--- |
| `CircuitBreakingException: [parent] Data too large` | Penggunaan memori agregasi melebihi batas heap threshold (`indices.breaker.total.use_real_memory`). | Persempit scope query dengan `filter`, gunakan `breadth_first`, atau naikkan alokasi RAM node. |
| Perbedaan akurasi nilai `terms` antar node | Nilai `size` terlalu kecil; data shard lokal membuang entri relevan sebelum proses merge coordinator. | Tingkatkan parameter `shard_size` menjadi minimal $(2 \times \text{size}) + 10$. |
| NullPointerException pada Pipeline Aggregation | `buckets_path` menunjuk ke bucket yang tidak terbuat karena `min_doc_count: 0` tidak diaktifkan. | Aktifkan `min_doc_count: 0` pada `date_histogram` atau tambahkan penanganan `gap_policy: "insert_zeros"`. |

---

## Seksi 18: Checklist Produksi

- [ ] Seluruh field yang digunakan pada aggregasi dikonfigurasi dengan `doc_values: true` (default untuk tipe numerik, boolean, date, keyword).
- [ ] Tidak ada aggregasi yang diarahkan ke field bertipe `text` tanpa validasi arsitektural.
- [ ] Sub-aggregasi bersarang (nested terms) telah dilengkapi dengan `collect_mode: breadth_first`.
- [ ] `eager_global_ordinals` diaktifkan hanya pada index dengan low-write/high-read aggregations traffic.
- [ ] Pipeline aggregations memiliki fallback policy (`gap_policy: insert_zeros` atau `skip`).
- [ ] Pagination analitik skala besar telah dialihkan dari Terms Aggregation ke `Composite Aggregation`.
- [ ] Parameter `shard_size` telah dikalibrasi untuk mencegah deviasi statistik pada distributed top-N queries.

---

## Seksi 19: Ringkasan Eksekutif
Complex Aggregations Engine pada Elasticsearch adalah komputasi analitik terdistribusi berkinerja tinggi yang beroperasi langsung di atas Lucene Doc Values tanpa overhead Java Garbage Collection. 

Melalui kombinasi strategi:
1. **Bucketing Tepat Guna:** Memanfaatkan `date_histogram`, `composite`, dan `terms` dengan pengaturan `collect_mode`.
2. **Kalkulasi Metrik Probabilistik:** Menggunakan HLL++ dan T-Digest untuk efisiensi resource.
3. **Multi-Tier Execution Pipeline:** Memanfaatkan *Parent* dan *Sibling Pipeline Aggregations* untuk komputasi lanjutan seperti *derivatives*, *moving statistics*, dan *anomaly detection*.

Sistem backend dapat mencapai pemrosesan analitik mendekati *real-time* dalam dataset berskala miliaran dokumen tanpa membebani heap memory coordinator node.

---

## Seksi 20: Referensi & Bacaan Lanjutan
* Elasticsearch Reference Guide: *Aggregations & Analytics Core Concepts*
* Lucene Technical Notes: *DocValues Architecture and Columnar Formats*
* Ted Dunning & Otmar Ertl: *Computing Extremely Accurate Quantiles Using T-Digests*
* Flajolet et al.: *HyperLogLog: The Analysis of a Near-Optimal Cardinality Estimation Algorithm*
* Elasticsearch Engineering Blog: *Preventing Memory Bloat with Breadth-First Aggregations*