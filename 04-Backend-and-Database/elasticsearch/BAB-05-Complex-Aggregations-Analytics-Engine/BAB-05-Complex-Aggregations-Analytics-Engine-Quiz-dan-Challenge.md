# BAB-05-Complex-Aggregations-Analytics-Engine: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi teknis, validasi pemahaman arsitektur, dan uji implementasi analitik berbasis Elasticsearch Aggregation Framework. Materi mencakup metrik lanjutan, bucket nesting, pipeline aggregations, optimasi performa memori (heap & doc values), penanganan high cardinality, hingga mitigasi circuit breaker pada skala produksi.

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1.1: Perbedaan Utama Metrics vs Bucket Aggregations
**Pertanyaan:**  
Jelaskan perbedaan mendasar antara *Metrics Aggregations* dan *Bucket Aggregations* pada Elasticsearch dalam hal struktur eksekusi dan output yang dihasilkan.

**Kunci Jawaban & Pembahasan:**
- **Bucket Aggregations:** Mengelompokkan dokumen ke dalam himpunan-himpunan (*buckets*) berdasarkan kriteria tertentu (misal nilai term, rentang angka, rentang waktu, atau query filter). Setiap bucket mempertahankan himpunan dokumen yang cocok dan memungkinkan sub-agregasi dieksekusi secara rekursif di dalamnya. Output berupa daftar bucket beserta `doc_count`.
- **Metrics Aggregations:** Melakukan kalkulasi matematis terhadap sekumpulan dokumen (bisa dokumen level root atau dokumen di dalam sub-bucket) dan menghasilkan nilai numerik tunggal (*single-value* seperti `avg`, `min`, `max`, `sum`, `cardinality`) atau nilai majemuk (*multi-value* seperti `stats`, `extended_stats`, `percentiles`).
- **Hubungan Hirarkis:** Bucket aggregations membangun dimensi analitik (struktur multidimensi), sedangkan metrics aggregations menghitung fakta numerik di dalam dimensi tersebut.

---

### Soal 1.2: Perilaku `size: 0` pada Request Aggregation
**Pertanyaan:**  
Mengapa parameter `"size": 0` sering disertakan pada root request Elasticsearch saat menjalankan query analitik agregasi murni? Apa dampak internalnya terhadap search phase?

**Kunci Jawaban & Pembahasan:**
- Parameter `"size": 0` menginstruksikan Elasticsearch untuk tidak mengembalikan dokumen hits individu (`hits.hits: []`).
- Pada tahap eksekusi terdistribusi (*Query Phase* vs *Fetch Phase*):
  1. *Query Phase:* Setiap shard mengeksekusi filter query dan mengumpulkan data agregasi.
  2. *Fetch Phase:* Shard mengambil source dokumen (`_source`) dari disk/Lucence index untuk ID yang masuk top-N ranking.
- Dengan `size: 0`, fase *Fetch Phase* sepenuhnya dilewati (*bypassed*), menghemat alokasi I/O disk, transfer network payload dokumen, dan alokasi heap untuk de-serialisasi `_source`.

---

### Soal 1.3: Mekanisme Estimasi HyperLogLog++ pada Cardinality Aggregation
**Pertanyaan:**  
Bagaimana Elasticsearch menghitung `cardinality` untuk field dengan variasi nilai masif tanpa menyimpan seluruh raw string di dalam memory heap, dan apa fungsi parameter `precision_threshold`?

**Kunci Jawaban & Pembahasan:**
- Elasticsearch mengimplementasikan algoritma **HyperLogLog++ (HLL++)**, yaitu algoritma probabilistik yang memperkirakan jumlah elemen unik (distinct values) dengan menggunakan hashing 64-bit dan mencatat pola bit (trailing zeroes) dari hash tersebut.
- Parameter `precision_threshold` (default 3000, maksimum 40000):
  - Mengontrol trade-off antara akurasi dan penggunaan memory.
  - Untuk cardinality di bawah nilai threshold, akurasi mendekati 100%.
  - Konsumsi memori per bucket dibatasi sekitar `precision_threshold * 8 bytes`. Dengan threshold 3000, memori yang terpakai hanya sekitar 24 KB per bucket, mencegah terjadinya `OutOfMemoryError` pada aggregasi unik berskala jutaan record.

---

### Soal 1.4: Perbedaan Sibling Pipeline vs Parent Pipeline Aggregation
**Pertanyaan:**  
Jelaskan perbedaan arsitektural antara *Sibling Pipeline Aggregation* dan *Parent Pipeline Aggregation*, serta berikan masing-masing 1 contoh implementasinya.

**Kunci Jawaban & Pembahasan:**
- **Sibling Pipeline Aggregation:** Bekerja pada level saudara (*sibling*) dari bucket yang dievaluasi. Pipeline ini mengonsumsi metrik dari seluruh bucket yang sejajar lalu menghasilkan metrik komputasi baru di luar bucket tersebut.
  - *Contoh:* `max_bucket`, `avg_bucket`, `min_bucket`, `stats_bucket`. Menghitung rata-rata penjualan bulanan dari seluruh bucket bulan.
- **Parent Pipeline Aggregation:** Bekerja langsung di dalam konteks bucket induk (*parent bucket*) dan memperkaya data bucket tersebut dengan metrik kalkulasi baru berdasarkan urutan bucket sebelumnya atau operasi antar metrik di bucket yang sama.
  - *Contoh:* `derivative` (menghitung laju perubahan/pertumbuhan per interval), `cumulative_sum` (running total), `bucket_script` (kalkulasi rasio metrik internal bucket), `bucket_selector` (filtering bucket pasca-agregasi).

---

### Soal 1.5: Fungsi Parameter `shard_size` pada Terms Aggregation
**Pertanyaan:**  
Mengapa hasil `terms` aggregation top-N pada indeks multi-shard dapat mengalami ketidakakuratan (*inaccuracy*), dan bagaimana parameter `shard_size` mengatasi masalah tersebut?

**Kunci Jawaban & Pembahasan:**
- Elasticsearch mendistribusikan data ke beberapa shard. Setiap shard hanya menghitung top-N lokal (`size`) dan mengirimkannya ke coordinating node.
- Jika sebuah term memiliki frekuensi tinggi secara global namun tersebar merata di ranking menengah pada setiap shard individual, term tersebut berisiko tereliminasi di level shard dan tidak pernah sampai ke coordinating node, menyebabkan kesalahan hitung (*doc_count error*).
- Parameter `shard_size` menentukan berapa banyak bucket yang dievaluasi dan dikembalikan oleh masing-masing shard ke coordinating node sebelum coordinating node melakukan reduksi final ke ukuran `size`.
- Secara default, `shard_size = (size * 1.5) + 10`. Meningkatkan nilai `shard_size` memperbesar akurasi top-N global dengan konsekuensi peningkatan konsumsi bandwidth antar node dan alokasi heap di coordinating node.

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 2.1: Analisis `doc_count_error_upper_bound`
**Pertanyaan:**  
Pada response query `terms` aggregation berikut, jelaskan makna metrik `"doc_count_error_upper_bound": 45` dan kapan angka ini dianggap berbahaya bagi integritas laporan analitik:

```json
{
  "aggregations": {
    "top_merchants": {
      "doc_count_error_upper_bound": 45,
      "sum_other_doc_count": 128450,
      "buckets": [
        { "key": "merchant_alpha", "doc_count": 15000 },
        { "key": "merchant_beta", "doc_count": 12400 }
      ]
    }
  }
}
```

**Kunci Jawaban & Pembahasan:**
- `doc_count_error_upper_bound` adalah batas atas matematis estimasi dokumen yang mungkin tidak terhitung untuk term yang masuk ke dalam list bucket hasil. Angka 45 berarti nilai riil `merchant_alpha` secara global bisa saja berada di rentang 15000 hingga 15045.
- Kondisi berbahaya:
  1. Jika margin selisih antar ranking (`bucket[0].doc_count - bucket[1].doc_count`) lebih kecil daripada `doc_count_error_upper_bound`, maka urutan peringkat ranking dapat salah (*ranking inversion*).
  2. Pada sistem finansial atau audit presisi tinggi di mana exact match diwajibkan.
- Solusi: Tingkatkan parameter `shard_size` mendekati total distinct keys atau gunakan `composite aggregation` untuk ekstraksi data tanpa sampling error.

---

### Soal 2.2: Pagination Menggunakan Composite Aggregation
**Pertanyaan:**  
Mengapa pagination analitik multi-dimensi menggunakan `terms` bersarang (*nested terms*) sangat rentan menyebabkan OutOfMemory (OOM), dan bagaimana `composite` aggregation memitigasi hal tersebut?

**Kunci Jawaban & Pembahasan:**
- **Kelemahan Nested Terms:** Jika melakukan nesting 3 level (misal: `country` [100] -> `category` [500] -> `brand` [1,000]), Elasticsearch harus menginstansiasi pohon kombinasi Cartesian bucket secara in-memory (`100 * 500 * 1,000 = 50,000,000 buckets`). Hal ini seketika memicu GC pause parah atau Node OOM.
- **Mekanisme Composite Aggregation:**
  - `composite` aggregation mendesain streaming pagination melintasi kombinasi multi-source menggunakan kursor deterministik (`after_key`).
  - Elasticsearch hanya memuat sejumlah bucket sesuai ukuran parameter `size` (misal 50 atau 100 item) per request.
  - State pagination disimpan dan dilanjutkan oleh client melalui `after` key tanpa perlu membangun complete combinatorial tree di JVM heap.

---

### Soal 2.3: Date Histogram vs Auto Date Histogram
**Pertanyaan:**  
Bandingkan penggunaan `date_histogram` dengan `auto_date_histogram`. Kapan arsitek sistem analitik harus memilih salah satu dari keduanya untuk dashboard visualisasi time-series dinamis?

**Kunci Jawaban & Pembahasan:**
- `date_histogram`:
  - Interval waktu didefinisikan secara statis dan kaku oleh pengguna (contoh: `calendar_interval: "1d"` atau `fixed_interval: "3h"`).
  - Jika rentang waktu filter query diubah dari 1 hari menjadi 5 tahun, jumlah bucket yang dihasilkan meledak dari puluhan menjadi ribuan bucket, membebani browser client dan cluster Elasticsearch.
- `auto_date_histogram`:
  - Pengguna hanya menentukan target jumlah bucket yang diinginkan melalui parameter `buckets` (misal `buckets: 30`).
  - Elasticsearch secara otomatis memilih interval waktu optimal (detik, menit, jam, hari, bulan, tahun) tergantung rentang `range` query pada data.
  - **Rekomendasi Arsitektur:** Gunakan `auto_date_histogram` pada UI dashboard publik atau eksploratif yang rentang waktunya dinamis (zoom-in/zoom-out), dan gunakan `date_histogram` untuk export batch reporting terstruktur (laporan bulanan, pembukuan harian).

---

### Soal 2.4: Pipeline Aggregation dengan `bucket_selector` dan `bucket_script`
**Pertanyaan:**  
Tuliskan struktur query aggregasi yang mengelompokkan data penjualan bulanan, menghitung rasio konversi (`total_checkout / total_visit`), lalu hanya menampilkan bulan yang memiliki rasio konversi lebih dari 0.15 (15%).

**Kunci Jawaban & Pembahasan:**
Query menggunakan kombinasi `date_histogram`, dua metric `sum`/`filter`, `bucket_script` untuk menghitung rasio, dan `bucket_selector` untuk memotong bucket hasil:

```json
POST /sales_analytics/_search
{
  "size": 0,
  "aggs": {
    "sales_per_month": {
      "date_histogram": {
        "field": "timestamp",
        "calendar_interval": "month"
      },
      "aggs": {
        "total_visits": {
          "sum": { "field": "visit_count" }
        },
        "total_checkouts": {
          "sum": { "field": "checkout_count" }
        },
        "conversion_rate": {
          "bucket_script": {
            "buckets_path": {
              "visits": "total_visits",
              "checkouts": "total_checkouts"
            },
            "script": "params.visits > 0 ? (params.checkouts / params.visits) : 0"
          }
        },
        "high_conversion_filter": {
          "bucket_selector": {
            "buckets_path": {
              "convRate": "conversion_rate"
            },
            "script": "params.convRate > 0.15"
          }
        }
      }
    }
  }
}
```

---

### Soal 2.5: Optimasi Doc Values dan Global Ordinals
**Pertanyaan:**  
Apa peran Lucene *Doc Values* dan Elasticsearch *Global Ordinals* dalam mempercepat eksekusi Terms Aggregation, dan apa strategi untuk menghindari latency spike pada first-query execution?

**Kunci Jawaban & Pembahasan:**
- **Doc Values:** Struktur data column-oriented on-disk (dibuat saat indexing) yang memetakan Document ID ke Field Values. Memungkinkan eksekusi agregasi membaca nilai secara sekuensial tanpa mengekstrak dokumen mentah dari inverted index.
- **Global Ordinals:** Struktur data in-memory yang memetakan term string unik di seluruh shard segment ke representasi integer 0..N. Dengan global ordinals, operasi agregasi bucket hanya melakukan komputasi array increment integer primitif, bukan kompresi dan perbandingan string berulang.
- **Penyebab Latency Spike:** Global ordinals dibangun secara lazy (*on-demand*) saat query agregasi pertama kali datang setelah segment merger/refresh.
- **Strategi Mitigasi:** Konfigurasikan `eager_global_ordinals: true` pada mapping field keyword. Pembuatan mapping ordinal dipindahkan ke background thread saat index refresh/merge terjadi, sehingga pengguna tidak mengalami spike latensi pada first search.

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 3.1: CircuitBreakerException pada Aggregasi High-Cardinality
**Deskripsi Masalah:**  
Sebuah platform AdTech mengumpulkan 200 juta event log impresi per hari pada Elasticsearch cluster 5-node (masing-masing node 32 GB RAM, 16 GB JVM Heap). Ketika dashboard analytics mengeksekusi aggregasi:
```json
{
  "aggs": {
    "by_user": {
      "terms": { "field": "user_uuid", "size": 1000 },
      "aggs": {
        "by_campaign": { "terms": { "field": "campaign_id", "size": 50 } }
      }
    }
  }
}
```
Query langsung gagal dengan error:
`circuit_breaking_exception: [parent] Data too large, data for [<reused_arrays>] would be [1234567890] which is larger than the limit of [10307921510]`.

**Analisis Akar Masalah:**
1. Field `user_uuid` memiliki kardinalitas ekstrem (> 50 juta nilai unik per hari).
2. Coordinating node dan data node mengalokasikan hash bucket in-memory untuk puluhan juta ordinal unik saat menyusun sub-agregasi nested.
3. Alokasi memori array melebihi threshold `indices.breaker.total.use_real_memory` (default 95% dari heap) atau `indices.breaker.request.limit` (default 60% heap), sehingga parent breaker aktif memutus query agar node JVM tidak crash dengan OOM.

**Solusi Arsitektur & Query:**
1. **Gunakan Composite Aggregation dengan Ukuran Terkontrol:** Hindari combinatorial tree. Gunakan streaming composite aggregation dengan pagination `after`.
2. **Pre-aggregation / Rollup Indexing:** Gunakan Elasticsearch Transform atau Rollup Job untuk meng-agregasi data raw per jam ke index ringkasan harian.
3. **Execution Hint & Breadth-First:** Jika tetap membutuhkan terms aggregation hirarkis, aktifkan `"collect_mode": "breadth_first"` pada sub-aggregation sehingga bucket level atas di-pruning terlebih dahulu sebelum sub-bucket dibuat:
```json
POST /ad_events-*/_search
{
  "size": 0,
  "aggs": {
    "by_campaign": {
      "terms": {
        "field": "campaign_id",
        "size": 10
      },
      "aggs": {
        "unique_users": {
          "cardinality": {
            "field": "user_uuid",
            "precision_threshold": 4000
          }
        }
      }
    }
  }
}
```
*Pelajaran Produksi:* Jangan pernah meletakkan field berkardinalitas jutaan (seperti `user_uuid` atau `ip_address`) sebagai outer bucket pada terms aggregation bertingkat. Balikkan relasi atau gunakan metrik cardinality.

---

### Skenario 3.2: Deteksi Anomali Finansial Menggunakan Moving Function Aggregation
**Deskripsi Masalah:**  
Sebuah payment gateway perlu memonitor anomali lonjakan transaksi fraud secara real-time. Tim operasional membutuhkan query Elasticsearch yang mengevaluasi rata-rata volume transaksi per 5 menit, menghitung moving average dari 6 bucket terakhir (window 30 menit), dan mendeteksi deviasi volume transaksi saat ini yang melonjak 3x lipat dibanding rata-rata pergerakan tersebut.

**Solusi Arsitektur & Implementasi Query:**
Gunakan `date_histogram` dengan sub-agregasi metrik `sum`, dipadukan dengan `moving_fn` pipeline aggregation (yang fleksibel menjalankan script model statistik) dan `bucket_selector` untuk memicu alert.

```json
POST /transactions/_search
{
  "size": 0,
  "query": {
    "range": {
      "transaction_time": {
        "gte": "now-6h",
        "lte": "now"
      }
    }
  },
  "aggs": {
    "txn_over_time": {
      "date_histogram": {
        "field": "transaction_time",
        "fixed_interval": "5m"
      },
      "aggs": {
        "tx_count": { "value_count": { "field": "transaction_id" } },
        "moving_avg_30m": {
          "moving_fn": {
            "buckets_path": "tx_count",
            "window": 6,
            "script": "MovingFunctions.unweightedAvg(values)"
          }
        },
        "ratio_to_moving": {
          "bucket_script": {
            "buckets_path": {
              "current": "tx_count",
              "movAvg": "moving_avg_30m"
            },
            "script": "params.movAvg > 0 ? (params.current / params.movAvg) : 1"
          }
        },
        "anomaly_detector": {
          "bucket_selector": {
            "buckets_path": {
              "ratio": "ratio_to_moving",
              "current": "tx_count"
            },
            "script": "params.current > 50 && params.ratio >= 3.0"
          }
        }
      }
    }
  }
}
```

**Evaluasi Teknis:**
- Pipeline `moving_fn` mengeksekusi fungsi statistik murni in-memory secara berurutan (*stream single-pass*), overhead CPU minimal.
- `bucket_selector` mengeliminasi bucket normal sehingga response payload hanya berisi titik waktu anomali spesifik yang siap dikonsumsi alert engine/Slack webhook.

---

### Skenario 3.3: Perhitungan Percentile Latency SLA Multi-Regional Tanpa Memory Leak
**Deskripsi Masalah:**  
Sistem APM (Application Performance Monitoring) memproses 1 miliar HTTP span per minggu. Tim SRE membutuhkan dashboard yang menampilkan latency P50, P95, dan P99 per endpoint API dan region. Namun saat menggunakan default `percentiles` aggregation pada dataset besar, penggunaan memory cluster melonjak dan nilai P99 berubah-ubah saat cluster di-scale (menambah data node).

**Analisis Penyebab:**
1. Default algoritma percentile Elasticsearch menggunakan **T-Digest**, yang mengelompokkan data point ke dalam sentroid probabilistik.
2. Pengaturan parameter `compression` default (100) memerlukan hingga `100 * 32 bytes` per bucket. Jika di-nesting dengan `region` (10) * `endpoint` (1,000) * `timestamp` (288 interval), jumlah sentroid in-memory mencapai jutaan objek, memicu heap pressure.
3. Ketidakstabilan nilai P99 disebabkan oleh variasi segment distribution antar node dan nilai `compression` yang terlalu rendah untuk ekor distribusi ekstrim (tail latencies).

**Solusi & Optimasi:**
1. Gunakan algoritma alternatif **HDR (High Dynamic Range) Histogram** jika rentang latency sudah diketahui (misal 1 ms hingga 60,000 ms) dengan batasan memori pasti dan tingkat presisi seragam di seluruh rentang.
2. Jika tetap menggunakan T-Digest, naikkan parameter `compression` hanya pada metrik kritis dan gunakan filter context ketat:

```json
POST /apm_spans/_search
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        { "range": { "@timestamp": { "gte": "now-1h" } } },
        { "term": { "service.name": "checkout-gateway" } }
      ]
    }
  },
  "aggs": {
    "by_region": {
      "terms": {
        "field": "geo.region_iso",
        "size": 10
      },
      "aggs": {
        "latency_percentiles": {
          "percentiles": {
            "field": "http.response_time_ms",
            "percents": [50.0, 95.0, 99.0],
            "hdr": {
              "number_of_significant_value_digits": 3
            }
          }
        }
      }
    }
  }
}
```

*Keuntungan Arsitektural:* HDR Histogram menjamin bounded memory footprint yang tidak bergantung pada jumlah record dokumen, menghilangkan fluktuasi estimasi tail latencies P99 pada koordinasi antar-shard.

---

## Bagian 4: Practical Chapter Challenge (1 Tantangan Hands-on)

### Judul Challenge: Engine Analitik Penjualan Multi-Dimensi & Deteksi Churn
**Tujuan:**  
Mengonfigurasi skema indeks dan merancang satu query agregasi komprehensif untuk mengekstrak metrik performa sales representative, pertumbuhan bulanan, dan kontribusi omzet tanpa menarik satupun source dokumen ke client.

### Persiapan Data & Mapping

Eksekusi perintah berikut untuk mempersiapkan index dan dataset pengujian:

```json
PUT /sales_pipeline
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 0
  },
  "mappings": {
    "properties": {
      "order_id": { "type": "keyword" },
      "sales_rep": { "type": "keyword", "eager_global_ordinals": true },
      "category": { "type": "keyword" },
      "amount": { "type": "double" },
      "order_date": { "type": "date" },
      "status": { "type": "keyword" }
    }
  }
}
```

```json
POST /sales_pipeline/_bulk
{ "index": {} }
{ "order_id": "ORD-001", "sales_rep": "Budi", "category": "Enterprise", "amount": 150000000, "order_date": "2026-01-10T10:00:00Z", "status": "COMPLETED" }
{ "index": {} }
{ "order_id": "ORD-002", "sales_rep": "Budi", "category": "Retail", "amount": 25000000, "order_date": "2026-01-22T14:30:00Z", "status": "COMPLETED" }
{ "index": {} }
{ "order_id": "ORD-003", "sales_rep": "Siti", "category": "Enterprise", "amount": 320000000, "order_date": "2026-01-15T09:15:00Z", "status": "COMPLETED" }
{ "index": {} }
{ "order_id": "ORD-004", "sales_rep": "Siti", "category": "Retail", "amount": 40000000, "order_date": "2026-02-05T11:00:00Z", "status": "COMPLETED" }
{ "index": {} }
{ "order_id": "ORD-005", "sales_rep": "Budi", "category": "Enterprise", "amount": 180000000, "order_date": "2026-02-18T16:00:00Z", "status": "COMPLETED" }
{ "index": {} }
{ "order_id": "ORD-006", "sales_rep": "Budi", "category": "SMB", "amount": 50000000, "order_date": "2026-02-25T13:00:00Z", "status": "CANCELLED" }
{ "index": {} }
{ "order_id": "ORD-007", "sales_rep": "Andi", "category": "Retail", "amount": 30000000, "order_date": "2026-02-28T08:30:00Z", "status": "COMPLETED" }
{ "index": {} }
{ "order_id": "ORD-008", "sales_rep": "Siti", "category": "Enterprise", "amount": 450000000, "order_date": "2026-03-02T10:00:00Z", "status": "COMPLETED" }
{ "index": {} }
{ "order_id": "ORD-009", "sales_rep": "Budi", "category": "Enterprise", "amount": 210000000, "order_date": "2026-03-15T15:20:00Z", "status": "COMPLETED" }
{ "index": {} }
{ "order_id": "ORD-010", "sales_rep": "Andi", "category": "Enterprise", "amount": 120000000, "order_date": "2026-03-20T17:00:00Z", "status": "COMPLETED" }
```

### Instruksi Tugas
Buatlah query single-search ke index `sales_pipeline` yang memenuhi seluruh syarat analitik berikut:
1. **Scope:** Hanya sertakan transaksi dengan `status: "COMPLETED"`.
2. **Payload:** Pastikan `size: 0` agar tidak ada dokumen hits yang dikembalikan.
3. **Agregasi Waktu:** Kelompokkan data per bulan (`order_date`) dari Januari 2026 sampai Maret 2026.
4. **Metrik Finansial:**
   - Hitung total pendapatan per bulan (`monthly_revenue`).
   - Hitung running total revenue kumulatif bulan ke bulan (`cumulative_revenue`) menggunakan Parent Pipeline.
   - Hitung persentase laju pertumbuhan pendapatan bulanan (`monthly_growth_rate`) menggunakan `derivative` atau `bucket_script`.
5. **Sub-Analitik Sales Rep:** Di dalam tiap bulan, kelompokkan top 2 sales rep dengan revenue tertinggi, hitung total penjualan dan nilai rata-rata per transaksi per rep.

### Solusi Query & Verifikasi

```json
POST /sales_pipeline/_search
{
  "size": 0,
  "query": {
    "term": {
      "status": "COMPLETED"
    }
  },
  "aggs": {
    "monthly_sales": {
      "date_histogram": {
        "field": "order_date",
        "calendar_interval": "month",
        "format": "yyyy-MM"
      },
      "aggs": {
        "monthly_revenue": {
          "sum": {
            "field": "amount"
          }
        },
        "cumulative_revenue": {
          "cumulative_sum": {
            "buckets_path": "monthly_revenue"
          }
        },
        "revenue_derivative": {
          "derivative": {
            "buckets_path": "monthly_revenue"
          }
        },
        "monthly_growth_rate": {
          "bucket_script": {
            "buckets_path": {
              "derivative": "revenue_derivative",
              "current": "monthly_revenue"
            },
            "script": "params.current != 0 && params.derivative != null ? (params.derivative / (params.current - params.derivative)) * 100 : 0"
          }
        },
        "top_sales_reps": {
          "terms": {
            "field": "sales_rep",
            "size": 2,
            "order": {
              "rep_revenue": "desc"
            }
          },
          "aggs": {
            "rep_revenue": {
              "sum": {
                "field": "amount"
              }
            },
            "avg_deal_size": {
              "avg": {
                "field": "amount"
              }
            }
          }
        }
      }
    }
  }
}
```

### Kriteria Kelulusan Challenge:
- [x] Query valid JSON dan lolos eksekusi di Elasticsearch 8.x/9.x tanpa script error.
- [x] Nilai `cumulative_revenue` pada bulan Maret mencerminkan total agregat seluruh order `COMPLETED` dari Januari hingga Maret (Total Rp 1.505.000.000).
- [x] Nilai `monthly_growth_rate` pada bulan pertama (Januari) bernilai 0 atau `null` dengan aman tanpa melempar divide-by-zero exception.
- [x] Sub-bucket `top_sales_reps` diurutkan secara benar berdasarkan metrik `rep_revenue` desc, bukan default `_count`.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan daftar periksa berikut untuk mengukur kesiapan teknis Anda dalam arsitektur analitik Elasticsearch:

- [ ] **Dasar Framework Aggregation:**
  - [ ] Memahami siklus eksekusi query aggregation terdistribusi (Scatter-Gather Phase).
  - [ ] Mampu membedakan kapan menggunakan `filter` aggregation di dalam `aggs` vs `filter` query di root level.
  - [ ] Memahami implikasi resource dari parameter `"size": 0`.

- [ ] **Kardinalitas & Manajemen Memori:**
  - [ ] Memahami cara kerja algoritma HyperLogLog++ dan dampak parameter `precision_threshold` terhadap heap usage.
  - [ ] Mengetahui penyebab `CircuitBreakerException` dan cara membaca log breaker memory limit.
  - [ ] Memahami peran `doc_values` dan kapan mengaktifkan `eager_global_ordinals`.

- [ ] **Komputasi Tingkat Lanjut & Pipeline:**
  - [ ] Mampu membedakan secara arsitektural antara Sibling Pipeline dan Parent Pipeline.
  - [ ] Menguasai penulisan sintaks `buckets_path` untuk metrik bersarang (misal: `"parent_agg>child_agg.metric"`).
  - [ ] Mampu menggunakan `bucket_selector` untuk filtering analitik pasca-agregasi tanpa mengubah kumpulan data dokumen dasar.

- [ ] **Skalabilitas Produksi:**
  - [ ] Mampu mengimplementasikan `composite` aggregation untuk streaming export data analitik multi-dimensi.
  - [ ] Mengetahui trade-off penggunaan algoritma T-Digest vs HDR Histogram pada perhitungan percentile latency.
  - [ ] Menguasai optimasi `shard_size` untuk menekan `doc_count_error_upper_bound` pada terms aggregation berdistribusi multi-shard.
