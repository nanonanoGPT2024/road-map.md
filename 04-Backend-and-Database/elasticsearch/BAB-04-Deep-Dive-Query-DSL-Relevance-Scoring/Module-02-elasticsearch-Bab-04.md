# Kurikulum Enterprise: Elasticsearch Deep Dive Query DSL & Relevance Scoring

**Kategori:** 04-Backend-and-Database  
**Bab 04:** BAB-04-Deep-Dive-Query-DSL-Relevance-Scoring  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi  

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Membedah Algoritma BM25 & Lucene Collector:** Menganalisis parameter $k_1$ dan $b$ pada Okapi BM25, serta memahami transisi internal Lucene dari TF-IDF ke BM25 termasuk kalkulasi saturasi term dan normalisasi panjang dokumen.
2. **Menguasai Arsitektur Distributed Search Phase:** Mengidentifikasi perbedaan mekanis mendalam antara `query_then_fetch` dan `dfs_query_then_fetch`, serta dampaknya terhadap koordinasi jaringan, latensi, dan akurasi Term Frequency (TF) / Inverse Document Frequency (IDF) pada cluster multi-shard.
3. **Mendesain Multi-Phase Scoring Pipeline:** Mengimplementasikan arsitektur relevansi tingkat lanjut menggunakan kombinasi `function_score`, `script_score` (Painless AST), decay functions (`gauss`, `exp`, `linear`), dan `rescore` window API untuk menyeimbangkan presisi relevansi dan konsumsi CPU.
4. **Menerapkan Optimasi Eksekusi Query Enterprise:** Mengoptimalkan throughput query dengan Block-Max WAND (Weak AND), *early termination* (`track_total_hits: false`), filter caching bitset, serta mitigasi GC pressure pada JVM heap saat beban mencapai puluhan ribu QPS.
5. **Menyelesaikan Kasus Relevansi Bisnis Kompleks:** Membangun ranking engine skala enterprise yang menggabungkan faktor tekstual, popularitas, margin bisnis, jarak geografis, dan *temporal decay* secara deterministik.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Arsitektur dasar Elasticsearch: Hubungan Node (Master, Data, Coordinating), Index, Shard (Primary & Replica), dan Lucene Segment.
* Pemahaman mendasar sintaks Query DSL: Boolean Query (`must`, `should`, `filter`, `must_not`), Match, Multi-match, Term-level queries.
* Konsep dasar struktur data penelusuran: *Inverted Index*, *Doc Values*, *Stored Fields*, dan BKD Tree (untuk numerik/geospatial).
* Dasar algoritma pemrosesan teks: Analyzer, Tokenizer, dan Token Filters.
* Familiaritas dengan REST API Elasticsearch, Dev Tools Console di Kibana, serta Docker/Docker Compose untuk simulasi multi-node cluster.

---

## 3. Concept & Internal Architecture

### 3.1 Mekanisme Internal Okapi BM25
Skor relevansi standar Lucene dihitung menggunakan formula Okapi BM25 yang menggantikan TF-IDF klasik sejak Elasticsearch 5.x:

$$\text{Score}(D, Q) = \sum_{i=1}^{N} \text{IDF}(q_i) \cdot \frac{f(q_i, D) \cdot (k_1 + 1)}{f(q_i, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$

Di mana komponen pembentuknya adalah:
* **$\text{IDF}(q_i)$ (Inverse Document Frequency):** Mengukur kelangkaan term dalam korpus:
  $$\text{IDF}(q_i) = \ln \left( 1 + \frac{N - n(q_i) + 0.5}{n(q_i) + 0.5} \right)$$
  *(N = total dokumen dalam shard, $n(q_i)$ = jumlah dokumen yang memuat term $q_i$)*.
* **$f(q_i, D)$ (Term Frequency):** Frekuensi kemunculan term $q_i$ dalam dokumen $D$.
* **$|D| / \text{avgdl}$ (Field-Length Normalization):** Rasio panjang field dokumen terhadap rata-rata panjang field serupa di seluruh shard.
* **$k_1$ (Term Saturation Parameter, default: `1.2`):** Mengontrol seberapa cepat skor mengalami saturasi ketika frekuensi term meningkat. Nilai $k_1$ yang lebih rendah membatasi dominasi keyword stuffing.
* **$b$ (Length Normalization Parameter, default: `0.75`):** Mengontrol seberapa kuat penalti yang diberikan pada dokumen dengan teks panjang. Nilai $b = 1.0$ memberikan penalti penuh berdasarkan panjang field, sementara $b = 0.0$ menonaktifkan normalisasi panjang.

```
       Score Contribution
              ^
              |               BM25 (k1=1.2) -> Saturasi Asimtotik
              |              /-------------------
              |             / 
              |            /  TF-IDF Klasik -> Tumbuh Tanpa Batas (sqrt)
              |           /  .
              |          / .
              |         /.
              |       /.
              +---------------------------------> Term Frequency (TF)
```

### 3.2 Block-Max WAND (Weak AND) & Early Termination
Elasticsearch menggunakan algoritma **Block-Max WAND** untuk mengeksekusi top-$k$ query secara efisien tanpa harus menghitung skor seluruh dokumen yang cocok:
1. Inverted index diorganisir dalam blok-blok dokumen (umumnya 128 doc ID per blok).
2. Setiap blok menyimpan metadata skor maksimum teoritis ($\text{max\_score}$) untuk setiap term.
3. Saat eksekusi query, Lucene mempertahankan ambang batas skor (*threshold*) dokumen ke-$k$ terbaik saat ini.
4. Jika jumlah skor maksimum blok yang dievaluasi berada di bawah ambang batas dokumen ke-$k$, Lucene akan **melewati (*skip*) seluruh blok dokumen tersebut** melalui pointer posting list tanpa membaca detail term frekuensinya.
5. Implikasi produksi: Ketika `track_total_hits` di-set ke `false` atau nilai integer tetap (misalnya 10.000), CPU tidak terbuang untuk menghitung skor ribuan dokumen yang tidak akan masuk ke halaman pertama hasil penelusuran.

### 3.3 Distributed Search Execution Phases
Elasticsearch adalah sistem terdistribusi. Eksekusi pencarian melintasi dua node level: **Coordinating Node** dan **Data Shard Nodes**.

```
[Client]
   |
   | 1. POST /index/_search
   v
[Coordinating Node]
   |
   +--- Broadcast Phase (Query/DFS) ---> [Data Node: Shard 1]
   +--- Broadcast Phase (Query/DFS) ---> [Data Node: Shard 2]
   +--- Broadcast Phase (Query/DFS) ---> [Data Node: Shard 3]
   |
   |<-- Return Priority Queue (DocIDs + Scores) --
   |
   | 2. Merge Priority Queues (Select Top-N globally)
   |
   +--- Fetch Phase (DocIDs only) -----> [Data Node: Shard X]
   +--- Fetch Phase (DocIDs only) -----> [Data Node: Shard Y]
   |
   |<-- Return Source Document Fields -------------
   |
   | 3. Assemble Response
   v
[Client]
```

Dua mode pencarian utama:
1. **`query_then_fetch` (Default):**
   * **Phase 1 (Query Phase):** Coordinating node meneruskan query ke shard terpilih (primary atau replica). Setiap shard mengeksekusi query secara lokal, membuat Lucene Priority Queue berukuran `from + size`, dan hanya mengembalikan metadata Doc ID serta Score numerik ke coordinating node.
   * **Reduce Phase:** Coordinating node menggabungkan (*merge-sort*) priority queue dari semua shard untuk menentukan Doc ID yang masuk ke peringkat top-N global.
   * **Phase 2 (Fetch Phase):** Coordinating node meminta dokumen penuh (`_source`, highlight, doc values) hanya untuk Doc ID yang lolos ke top-N global dari shard yang relevan.
   * *Problem:* Setiap shard menghitung IDF menggunakan statistik korpus lokalnya sendiri. Jika dokumen tidak terdistribusi secara homogen (*data skew*), skor dapat terdistorsi.

2. **`dfs_query_then_fetch` (Pre-flight Phase):**
   * Menambahkan fasa **DFS (Distributed Frequency Search)** sebelum Query Phase.
   * Coordinating node meminta statistik term frequency dan document frequency lokal dari setiap shard, mengagregasikannya menjadi statistik korpus global, lalu menyematkan statistik global ini ke dalam Query Phase.
   * *Trade-off:* Menghasilkan kalkulasi skor yang akurat secara teoritis, tetapi memperkenalkan *extra network round-trip* ke seluruh shard, yang meningkatkan latensi P99 sebesar 20-40%.

---

## 4. Why & What

### Mengapa Relevansi Bawaan (Default BM25) Sering Gagal di Skala Enterprise?
1. **Ketidaktahuan Terhadap Sinyal Bisnis (Business Agnostic):** BM25 hanya mengetahui statistik kata. Algoritma ini tidak mengetahui bahwa merchant A memiliki SLA pengiriman 99%, produk B memiliki rating bintang 4.8 dengan 10.000 ulasan, atau produk C memiliki margin profit 40% lebih tinggi.
2. **Freshness & Decay Problem:** Dokumen teknis, artikel berita, atau promo musiman yang relevan secara leksikal 2 tahun lalu akan mengalahkan dokumen baru jika repetisi keyword-nya lebih tinggi, kecuali jika diberi bobot waktu (*temporal decay*).
3. **Local Score Drift pada Cluster Baru:** Saat membuat index baru dengan multi-shard, volume data awal yang kecil menghasilkan statistik IDF lokal yang acak-acakan antar shard, membingungkan proses tuning ranking engine.

### Apa Solusinya?
Mengimplementasikan **Two-Phase Relevance Scoring Engine**:
* **Phase 1 - Candidate Retrieval (Recall Phase):** Menggunakan Boolean/DisMax Query standar dengan filter bitset teroptimasi dan algoritma WAND untuk menyaring kandidat terbaik (misal: 1.000 dokumen teratas) dengan biaya latensi rendah.
* **Phase 2 - Rescoring & Custom Business Boosting (Precision Phase):** Menerapkan `rescore` window menggunakan `script_score` (Painless) atau `function_score` (decay + field value factor) secara eksklusif hanya pada 100-500 kandidat teratas dari Phase 1. Hal ini mencegah kalkulasi skrip matematis yang berat dieksekusi pada jutaan dokumen yang tidak relevan.

---

## 5. How: Workflow Detail Rekayasa Relevansi

```
                   +---------------------------------------+
                   |  Incoming Query Request               |
                   +---------------------------------------+
                                       |
                                       v
                   +---------------------------------------+
                   | Phase 1: Boolean Retrieval & Match    |
                   | - Constant Score Filter (Category,    |
                   |   Status, Geo-bounding box)           |
                   | - BM25 Match on Title & Description   |
                   +---------------------------------------+
                                       |
                                       v
                   +---------------------------------------+
                   | Lucene Block-Max WAND                 |
                   | - Skip irrelevant posting blocks      |
                   | - Track top 1000 candidate Doc IDs   |
                   +---------------------------------------+
                                       |
                                       v
                   +---------------------------------------+
                   | Phase 2: Rescoring Window (Top-100)   |
                   | - Apply Gauss Temporal Decay          |
                   | - Apply Painless Script:              |
                   |   Score = BM25 * Log(CTR) * Margin    |
                   +---------------------------------------+
                                       |
                                       v
                   +---------------------------------------+
                   | Fetch Phase: Hydrate Top-20 hits      |
                   | - Fetch Source Fields & Highlighting  |
                   +---------------------------------------+
                                       |
                                       v
                   +---------------------------------------+
                   | Response to Client                    |
                   +---------------------------------------+
```

1. **Query Parsing & Optimization:** Coordinating node memvalidasi AST (*Abstract Syntax Tree*) query. Filter tanpa skor diekstrak ke dalam Lucene bitset query cache.
2. **Shard Routing:** Query didistribusikan ke shard menggunakan routing key deterministik (misalnya `user_id` atau `merchant_id`) jika ada, atau round-robin ke active shards/replicas.
3. **WAND Collection:** Shard mengeksekusi evaluasi candidate set. Dokumen yang tidak lolos filter dieliminasi di level posting list iterator.
4. **Primary Scoring:** BM25 dihitung secara vektor paralel untuk term-term yang tersisa.
5. **Secondary Rescoring Execution:** Jika blok `rescore` didefinisikan, Elasticsearch mengisolasi top-$N$ dokumen (window size), mengeksekusi script/decay function via Painless AST engine, lalu memadukan skor primer dan sekunder (`score_mode`: `total`, `multiply`, dsb.).
6. **Fetch & Serialization:** Data binary dari segment file `.fdt` dan `.fdx` diekstrak hanya untuk item halaman aktif (`size: 20`, `from: 0`).

---

## 6. Analogy & Diagram ASCII

### Analogi: Seleksi Berkas Masuk Karyawan Korporat
Bayangkan Anda menerima 100.000 berkas lamaran (dokumen di inverted index):
* **Default BM25:** Anda menyortir kandidat hanya berdasarkan berapa kali kata "Kubernetes" muncul di CV mereka. Hasilnya: CV dengan 50 kali pengulangan kata "Kubernetes" menang, meskipun kandidat tersebut baru lulus dan tidak memiliki pengalaman kerja riil.
* **Two-Phase Scoring (Arsitektur Produksi):**
  1. **Phase 1 (Filter & BM25 - Saringan Cepat):** Singkirkan CV yang tidak memiliki sertifikasi dasar (Filter). Ambil 100 kandidat terbaik yang memiliki penyebutan kompetensi yang seimbang (WAND candidate search).
  2. **Phase 2 (Rescore Window - Wawancara Mendalam):** Bawa hanya 100 kandidat terbaik ke meja dewan direksi. Evaluasi mereka menggunakan metrik kompleks: rekam jejak kepemimpinan, reputasi perusahaan sebelumnya, ekspektasi gaji vs *budget*, serta jarak tempat tinggal kandidat ke kantor (Decay & Painless Script Score).

### Perbandingan Karakteristik Algoritma Decay

```
Score Multiplier
  1.0 +-------------+                +
      |             \               / \
      |              \  (Exp)      /   \  (Gauss)
  0.5 |               \           /     \
      |                \         /       \
      |                 +-------+         +-------+
  0.0 +-------------------------------------------------> Value Offset
      |<-- Offset -->|<--------- Scale ---------->|
```

* **Gauss:** Penurunan landai di awal, jatuh drastis di tengah, lalu melandai di ujung (membentuk kurva lonceng). Ideal untuk penalti jarak geografis dan waktu perilisan konten yang memiliki *grace period*.
* **Exponential:** Penurunan sangat cepat di awal, cocok untuk memprioritaskan konten yang sangat sensitif terhadap kebaruan (*breaking news*).
* **Linear:** Penurunan bertahap secara konstan dengan batas absolut nol.

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Analisis Internal Skor Melalui Explain API
Melihat rincian matematis bagaimana BM25 dihitung oleh Lucene.

```json
// POST /catalog_sample/_explain/doc_101
{
  "query": {
    "match": {
      "product_name": "Mechanical Keyboard"
    }
  }
}
```

*Payload Cuplikan Respons Internal Lucene:*
```json
{
  "_index": "catalog_sample",
  "_id": "doc_101",
  "matched": true,
  "explanation": {
    "value": 4.1258917,
    "description": "sum of:",
    "details": [
      {
        "value": 2.012451,
        "description": "weight(product_name:mechanical in 101) [PerFieldSimilarity], result of:",
        "details": [
          {
            "value": 2.012451,
            "description": "score(freq=1.0), product of:",
            "details": [
              { "value": 1.4521, "description": "idf, computed as log(1 + (N - n + 0.5) / (n + 0.5))" },
              { "value": 1.3858, "description": "tf, computed as freq / (freq + k1 * (1 - b + b * dl / avgdl))" }
            ]
          }
        ]
      }
    ]
  }
}
```

### 7.2 Practical Example: Enterprise Multi-Factor Scoring Pipeline
Berikut adalah query produksi lengkap yang mengkombinasikan:
1. `bool` query untuk filter non-scoring (ketersediaan stok, status merchant aktif).
2. Multi-match teks dengan perlakuan field boosting (`^3` untuk title, `^1` untuk deskripsi).
3. Phase 2 Rescore Window menggunakan `script_score` (Painless) yang memperhitungkan Doc Values numerik: Margin Profit, Penjualan Historis, dan Decay Waktu (Gauss).

```json
POST /ecommerce_v1/_search
{
  "track_total_hits": 10000,
  "query": {
    "bool": {
      "filter": [
        { "term": { "status": "ACTIVE" } },
        { "range": { "stock": { "gt": 0 } } }
      ],
      "must": [
        {
          "multi_match": {
            "query": "mechanical wireless keyboard",
            "fields": [
              "product_name.analyzed^3",
              "product_name.synonyms^2",
              "description.analyzed^1"
            ],
            "type": "best_fields",
            "tie_breaker": 0.2,
            "fuzziness": "AUTO:4,7"
          }
        }
      ]
    }
  },
  "rescore": [
    {
      "window_size": 250,
      "query": {
        "rescore_query": {
          "function_score": {
            "gauss": {
              "created_at": {
                "origin": "now",
                "scale": "30d",
                "offset": "7d",
                "decay": 0.5
              }
            },
            "weight": 1.5
          }
        },
        "query_weight": 0.7,
        "rescore_query_weight": 0.3,
        "score_mode": "multiply"
      }
    },
    {
      "window_size": 100,
      "query": {
        "rescore_query": {
          "script_score": {
            "script": {
              "source": """
                double ctr = doc['ctr'].size() > 0 ? doc['ctr'].value : 0.01;
                double rating = doc['rating_avg'].size() > 0 ? doc['rating_avg'].value : 3.0;
                double margin = doc['profit_margin_pct'].size() > 0 ? doc['profit_margin_pct'].value : 0.05;
                
                // Menstabilkan skor menggunakan kurva logaritmik agar sinyal bisnis tidak mendistorsi relevansi teks secara liar
                double business_multiplier = 1.0 + Math.log10(1.0 + (ctr * 100.0)) * (rating / 5.0) * (1.0 + margin);
                
                return _score * business_multiplier;
              """
            }
          }
        },
        "query_weight": 1.0,
        "rescore_query_weight": 1.0,
        "score_mode": "total"
      }
    }
  ],
  "from": 0,
  "size": 20,
  "_source": ["product_id", "product_name", "price", "rating_avg", "ctr"]
}
```

---

## 8. Real World Case Study: E-Commerce Marketplace Tier-1

### Arsitektur Masalah
Marketplace "MegaStore" memproses **50 Juta SKU aktif** dengan throughput puncak **18.000 QPS**.
* **Keluhan Bisnis:** Produk baru yang relevan tenggelam di halaman 15. Produk lama yang memiliki stok habis sering muncul di halaman pertama karena manipulasi kata kunci berulang pada field `description`.
* **Keluhan Infrastruktur:** Latensi P99 melambung hingga **1.850 ms**, utilisasi CPU data node mencapai 95%, dan sering memicu *CircuitBreakingException* (`parent: [parent] Data too large, data for [<transport_request>]`).

### Akar Masalah (Root Cause Analysis)
1. Query lama mengeksekusi `function_score` dengan script Painless di layer query terluar. Hal ini memaksa Elasticsearch mengeksekusi kompilasi skrip dan eksekusi Doc Values pada **setiap dokumen** yang cocok (rata-rata 800.000 dokumen per penelusuran kata kunci populer).
2. Penggunaan `dfs_query_then_fetch` di seluruh request pencarian umum yang menambah *network overhead* masif pada cluster dengan 60 shard.
3. Tidak ada early termination: `track_total_hits` default bernilai `true`, menonaktifkan optimasi Block-Max WAND dari Lucene.

### Solusi Desain Arsitektur Produksi
```
[Client App]
     |
     v
[API Gateway: Edge Search Service]
     |
     | (Query Enrichment: User Lat/Long, A/B Test Bucket)
     v
[Elasticsearch Coordinating Tier]
     |
     +--> [Phase 1: Filter + BM25 with Block-Max WAND]
     |    - Indices: products_v4
     |    - Routing: category_group_id
     |    - track_total_hits: 5000
     |    - Execution: query_then_fetch (Standard)
     |
     +--> [Phase 2: Rescoring Window Pipeline]
     |    - Window: Top 500 items only
     |    - Execution: Native Caching Decay + Painless Business Scoring
     |
     +--> [Phase 3: Controlled Serialization]
          - Hydrate Top 20 results via docvalue_fields & stored _source
```

### Hasil Optimasi Setelah Deployment

| Metrik | Sebelum Implementasi | Sesudah Implementasi | Delta Perbaikan |
|---|---|---|---|
| Latensi P95 | 680 ms | 48 ms | **-92.9%** |
| Latensi P99 | 1.850 ms | 115 ms | **-93.7%** |
| Rata-rata CPU Data Node | 92% | 38% | **-58.6%** |
| Conversion Rate (CTR to Cart) | 3.12% | 4.87% | **+56.0%** |
| Out of Memory (OOM) Incidents | ~4 kali / minggu | 0 dalam 6 bulan | **100% Resolved** |

---

## 9. Trade-offs

Desain ranking search engine selalu merupakan kompromi antara parameter teknis dan fungsional:

```
                  Latensi Rendah / Throughput Tinggi
                            /        \
                           /          \
                          /            \
                         /   Trade-Off  \
                        /      Space     \
                       /                  \
   Skor Akurat / Eksak ------------------- Fleksibilitas Aturan Bisnis
   (DFS, Precision BM25)                  (Heavy Painless Scripting)
```

1. **`query_then_fetch` vs `dfs_query_then_fetch`:**
   * *Trade-off:* `dfs_query_then_fetch` memberikan IDF global yang presisi seragam di seluruh shard, namun menambah $O(2N)$ network trips antar node (di mana $N$ adalah jumlah shard).
   * *Rekomendasi Enterprise:* Gunakan routing shard yang baik atau konsolidasikan segment via `forcemerge` pada read-only indices, dan pertahankan default `query_then_fetch`. Hindari DFS kecuali untuk katalog kecil di bawah 100.000 dokumen dengan variansi shard tinggi.

2. **In-Query Function Score vs Two-Phase Rescoring:**
   * *Trade-off:* Menerapkan `function_score` di root query memproses seluruh subset pencarian (jutaan CPU cycles), sedangkan `rescore` window hanya memproses top-$k$ (misal 100-500 dokumen). Namun, dokumen yang memiliki skor teks buruk tetapi sinyal bisnis tinggi mungkin tidak masuk ke dalam window jika $k$ terlalu kecil.
   * *Rekomendasi Enterprise:* Set ukuran window rescore antara $k = 200$ hingga $k = 1.000$. Nilai ini mengisolasi dokumen potensial tanpa membebani thread pool pencarian.

3. **Block-Max WAND (`track_total_hits: false`) vs Exact Matching:**
   * *Trade-off:* `track_total_hits: false` memungkinkan Lucene melompati evaluasi skor pada jutaan dokumen (skalabilitas masif), tetapi UI aplikasi frontend kehilangan kemampuan untuk menampilkan jumlah total halaman/dokumen secara eksak ("1 dari 1.482.912 produk").
   * *Rekomendasi Enterprise:* Ubah UI aplikasi ke model "10.000+ produk ditemukan" atau infinite scroll, dan batasi `track_total_hits` ke angka 10.000.

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Painless Compilation Circuit Breaker Triggered
* **Gejala:** Muncul error `CircuitBreakingException: [script] Too many dynamic script compilations, limit: [75/5m]`.
* **Penyebab:** Menyematkan parameter dinamis langsung ke dalam string Painless script, bukan melalui blok `params`.
  ```json
  // SALAH (Memicu kompilasi ulang baru setiap query berbeda):
  "source": "return _score * " + userSuppliedBoostFactor + ";"
  
  // BENAR (Kompilasi sekali, eksekusi berulang kali dari cache AST):
  "source": "return _score * params.boost_factor;",
  "params": {
    "boost_factor": 1.45
  }
  ```

### Mistake 2: Score Drift Akibat Deep Pagination
* **Gejala:** Pengguna mengklik halaman 100 (`from: 2000, size: 20`) dan mengalami peningkatan latensi drastis (hingga timeout) serta urutan relevansi yang tampak tidak konsisten.
* **Penyebab:** Pada window `from: 2000, size: 20`, setiap shard harus mengekstrak dan mengurutkan 2.020 dokumen secara lokal ke Lucene priority queue, lalu coordinating node harus mengurutkan $2020 \times \text{Jumlah Shard}$ dokumen dalam memori.
* **Solusi:** Batasi pagination manual maksimal 1.000 dokumen. Untuk paginasi mendalam (*deep pagination*) sistem backend/crawler, gunakan API `search_after` dengan point-in-time (PIT).

### Mistake 3: Mengabaikan Type Mismatch pada Decay Functions
* **Gejala:** Muncul exception `IllegalArgumentException: Field [release_date] is not of type [date]`.
* **Solusi:** Pastikan mapping didefinisikan dengan tipe `date` untuk decay waktu, atau `geo_point` untuk decay jarak. Jika field tersebut bernilai null, pastikan query menangani nilai default menggunakan `missing` parameter di `field_value_factor` atau pengecekan `.size() > 0` di script Painless.

### Mistake 4: Shard Data Skew Merusak Nilai BM25
* **Gejala:** Dua dokumen identik di index yang sama mendapatkan skor relevansi yang berbeda signifikan ketika dicari dengan kata kunci yang sama.
* **Investigasi:**
  ```bash
  GET /catalog/_stats/shards
  ```
  Periksa jumlah dokumen per primary shard. Jika Shard 0 memiliki 500.000 dokumen dan Shard 1 memiliki 5.000 dokumen, skor IDF kata yang sama akan jauh lebih tinggi di Shard 1 dibanding Shard 0.
* **Solusi:** Gunakan shard routing yang mendistribusikan data secara merata, atau kurangi jumlah primary shard jika ukuran data tidak membenarkan penggunaan banyak shard.

---

## 11. Best Practices & Production Checklist

1. **Mapping Configuration:**
   * [ ] Nonaktifkan `norms` pada field teks yang hanya digunakan untuk filtering murni untuk menghemat RAM disk segment: `"norms": false`.
   * [ ] Konfigurasikan `similarity` kustom jika domain dokumen memiliki karakter spesifik (misal: deskripsi pendek buku membutuhkan parameter $b$ yang lebih rendah).

2. **Query Performance Optimization:**
   * [ ] Seluruh klausa query yang tidak membutuhkan perhitungan skor **wajib** diletakkan di dalam blok `bool.filter` atau `bool.must_not` agar dapat di-cache di Lucene Node Query Cache.
   * [ ] Tetapkan `track_total_hits: false` atau maksimal integer `10000` di tingkat produksi.
   * [ ] Selalu isolasi manipulasi matematika kompleks berbasis script ke dalam blok `rescore` window (`window_size` $\le 500$), bukan di root query `function_score`.

3. **Painless Scripting Standards:**
   * [ ] Jangan pernah menggabungkan string (*string concatenation*) ke dalam body skrip Painless. Selalu gunakan dictionary `params`.
   * [ ] Akses field numerik via `doc['field_name'].value` (Doc Values) yang aman dan berkinerja tinggi, bukan melalui `params['_source']['field_name']` yang memaksa dekompresi JSON mentah dari segment disk.
   * [ ] Selalu validasi ketiadaan nilai pada doc values dengan `doc['field_name'].size() > 0` sebelum memanggil `.value` guna mencegah *NullPointerExceptions*.

4. **Kapasitas & Scaling:**
   * [ ] Monitor *Search Thread Pool Queue*: Jika terjadi lonjakan antrean (`thread_pool.search.queue > 0`), segera scale-out replica shard atau optimasi window rescoring.
   * [ ] Hindari indeks dengan *over-sharding*. Ukuran shard target produksi yang optimal untuk read-heavy retrieval adalah antara **15 GB hingga 35 GB**.

---

## 12. Hands-on Practice: Membangun Production Relevance Engine

Semua file berikut diposisikan dalam direktori project: `hands-on/m02/`.

### 12.1 Environment Setup (`hands-on/m02/docker-compose.yml`)
Mempersiapkan multi-node Elasticsearch cluster dengan monitoring metrics:

```yaml
version: '3.8'
services:
  es01:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.3
    container_name: es01
    environment:
      - node.name=es01
      - cluster.name=es-relevance-cluster
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
      - xpack.security.enabled=false
    ulimits:
      memlock:
        soft: -1
        hard: -1
    ports:
      - "9200:9200"
    networks:
      - elastic_net

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.3
    container_name: kibana01
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://es01:9200
    networks:
      - elastic_net
    depends_on:
      - es01

networks:
  elastic_net:
    driver: bridge
```

Jalankan container:
```bash
docker-compose up -d
```

### 12.2 Inisialisasi Mapping Engine Teroptimasi (`hands-on/m02/01_init_schema.sh`)

```bash
#!/bin/bash

curl -X PUT "http://localhost:9200/marketplace_products" \
     -H 'Content-Type: application/json' \
     -d'
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 0,
    "index": {
      "similarity": {
        "custom_bm25": {
          "type": "BM25",
          "k1": 1.2,
          "b": 0.65
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "product_id": { "type": "keyword" },
      "title": {
        "type": "text",
        "similarity": "custom_bm25",
        "fields": {
          "raw": { "type": "keyword" }
        }
      },
      "category": { "type": "keyword" },
      "price": { "type": "double" },
      "stock": { "type": "integer" },
      "ctr": { "type": "double" },
      "sales_count": { "type": "integer" },
      "published_date": { "type": "date" },
      "merchant_location": { "type": "geo_point" }
    }
  }
}
'
echo "\nIndex marketplace_products created successfully."
```

### 12.3 Bulk Data Seeding (`hands-on/m02/02_bulk_seed.sh`)

```bash
#!/bin/bash

curl -X POST "http://localhost:9200/marketplace_products/_bulk" \
     -H 'Content-Type: application/x-ndjson' \
     -d'
{ "index": { "_id": "1" } }
{ "product_id": "P001", "title": "Wireless Gaming Mouse RGB Ultra Light", "category": "electronics", "price": 45.0, "stock": 120, "ctr": 0.08, "sales_count": 1500, "published_date": "2024-02-01T00:00:00Z", "merchant_location": { "lat": -6.175110, "lon": 106.865039 } }
{ "index": { "_id": "2" } }
{ "product_id": "P002", "title": "Ergonomic Vertical Mouse Wireless Office", "category": "electronics", "price": 35.0, "stock": 45, "ctr": 0.02, "sales_count": 200, "published_date": "2024-01-10T00:00:00Z", "merchant_location": { "lat": -6.208763, "lon": 106.845599 } }
{ "index": { "_id": "3" } }
{ "product_id": "P003", "title": "Wireless Mouse Silent Click Basic", "category": "electronics", "price": 15.0, "stock": 300, "ctr": 0.04, "sales_count": 5000, "published_date": "2023-06-01T00:00:00Z", "merchant_location": { "lat": -6.917464, "lon": 107.619123 } }
{ "index": { "_id": "4" } }
{ "product_id": "P004", "title": "Mouse Pad Gaming Extended Desk Mat", "category": "accessories", "price": 12.0, "stock": 500, "ctr": 0.01, "sales_count": 80, "published_date": "2024-02-15T00:00:00Z", "merchant_location": { "lat": -6.175110, "lon": 106.865039 } }
'
echo "\nBulk seeding completed."
```

### 12.4 Menjalankan Production Pipeline Query (`hands-on/m02/03_execute_search.sh`)

```bash
#!/bin/bash

# Target: Cari 'wireless mouse', dekat dengan Jakarta Pusat (-6.175, 106.865),
# bobotkan kebaruan (decay), dan dorong item dengan CTR dan sales_count tinggi via rescore.

curl -X POST "http://localhost:9200/marketplace_products/_search?pretty" \
     -H 'Content-Type: application/json' \
     -d'
{
  "track_total_hits": 5000,
  "query": {
    "bool": {
      "filter": [
        { "term": { "category": "electronics" } },
        { "range": { "stock": { "gt": 0 } } }
      ],
      "must": [
        {
          "match": {
            "title": {
              "query": "wireless mouse",
              "operator": "and"
            }
          }
        }
      ]
    }
  },
  "rescore": {
    "window_size": 50,
    "query": {
      "rescore_query": {
        "function_score": {
          "functions": [
            {
              "gauss": {
                "published_date": {
                  "origin": "now",
                  "scale": "60d",
                  "offset": "7d",
                  "decay": 0.5
                }
              },
              "weight": 1.2
            },
            {
              "gauss": {
                "merchant_location": {
                  "origin": { "lat": -6.175110, "lon": 106.865039 },
                  "scale": "20km",
                  "offset": "2km",
                  "decay": 0.3
                }
              },
              "weight": 1.5
            },
            {
              "script_score": {
                "script": {
                  "source": "double ctr = doc[\"ctr\"].size() > 0 ? doc[\"ctr\"].value : 0.0; double sales = doc[\"sales_count\"].size() > 0 ? doc[\"sales_count\"].value : 0.0; return Math.log10(sales + 1.0) * (1.0 + ctr);"
                }
              },
              "weight": 2.0
            }
          ],
          "score_mode": "sum",
          "boost_mode": "multiply"
        }
      },
      "query_weight": 0.5,
      "rescore_query_weight": 1.5,
      "score_mode": "total"
    }
  },
  "_source": ["product_id", "title", "price", "sales_count", "ctr"]
}
'
```

---

## 13. Exercise

### Level Easy
1. Ubah parameter BM25 ($k_1$ dan $b$) pada index `marketplace_products` melalui Index Template agar field `title` menonaktifkan sepenuhnya normalisasi panjang field ($b = 0.0$).
2. Validasi perubahannya menggunakan `_explain` API dan catat bagaimana skor TF berubah pada dokumen dengan variasi panjang judul yang berbeda.

### Level Medium
1. Tulis query pencarian dengan `function_score` yang menerapkan `exponential` decay pada harga (`price`), dengan asumsi harga target ideal pembeli adalah `$30.0`, skala `$10.0`, offset `$0.0`, dan decay `0.5`.
2. Pastikan produk yang berada di luar rentang harga ideal tetap muncul, namun skornya berkurang secara eksponensial seiring bertambahnya selisih harga dari `$30.0`.

### Level Hard
1. Buat pipeline scoring dua tahap (*two-phase*) lengkap:
   * **Phase 1:** Boolean query dengan `dis_max` (menggunakan `tie_breaker: 0.3`) pada field `title` (boost 3.0), `tags` (boost 1.5), dan `category` (boost 1.0).
   * **Phase 2:** Rescore window sebesar 100 dokumen yang mengeksekusi script Painless dengan parameter dinamis (`params.user_tier`).
   * **Logic Painless:** Jika `params.user_tier == 'VIP'`, dokumen dengan margin profit (`profit_margin_pct`) lebih dari 20% mendapatkan multiplier tambahan $1.5\times$, sedangkan user `REGULAR` diprioritaskan berdasarkan rating produk (`rating_avg`) dan volume diskon.
2. Analisis profil performa latensi query tersebut menggunakan Elasticsearch Profile API (`"profile": true`) dan identifikasi komponen breakdown waktu eksekusi pada Lucene Collector.

---

## 14. Challenge

### Skenario: Arsitektur Multi-Tenant Real-Time Relevance Balancing Engine

Anda adalah Lead Search Engineer di platform SaaS B2B yang melayani lebih dari **1.000 Tenant Perusahaan**. Masing-masing tenant memiliki konfigurasi bobot relevansi bisnis yang berbeda secara dinamis.
* **Tenant A (Fashion):** Membutuhkan bobot tinggi pada *freshness decay* (produk musim baru harus berada di posisi teratas) dan *visual match tags*.
* **Tenant B (Heavy Industrial Spare Parts):** Mengharuskan pencocokan kode SKU secara presisi (*exact match*), mengabaikan tanggal rilis sepenuhnya, namun mengutamakan ketersediaan stok lokal (`geo_distance`).
* **Tenant C (Flash Sale Platform):** Mengutamakan *velocity metric* (jumlah pesanan dalam 15 menit terakhir) yang di-stream secara berkala ke Elasticsearch setiap 30 detik.

### Persyaratan Tantangan:
1. Rancang arsitektur Search API terpadu yang dapat melayani ketiga pola kebutuhan bisnis di atas tanpa melakukan hardcoding query DSL di level backend aplikasi.
2. Desain strategi pembaruan data berkecepatan tinggi untuk *velocity metrics* (Tenant C) tanpa merusak cache Lucene segment (*segment thrashing*) dan tanpa memicu *compaction storm*.
3. Jelaskan mitigasi Anda terhadap risiko kompilasi script Painless yang berlebihan (*compilation limit blown*) saat ribuan tenant mengirimkan parameter bobot yang berubah setiap detik.
4. Buat skema pengujian beban (*load testing*) untuk memvalidasi bahwa P99 tetap berada di bawah 65 ms pada beban 12.000 QPS dalam kondisi index aktif diperbarui (*concurrent read-write*).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara parameter $k_1$ dan $b$ dalam rumus Okapi BM25?**
   * A. $k_1$ mengatur penalti panjang dokumen, $b$ mengatur saturasi frekuensi term.
   * B. $k_1$ mengatur saturasi frekuensi term, $b$ mengatur tingkat penalti normalisasi panjang dokumen.
   * C. $k_1$ adalah pengali skor global, $b$ adalah konstanta pembagi IDF.
   * D. $k_1$ dan $b$ hanya berlaku pada mesin pencari berbasis TF-IDF lama.

2. **Mengapa klausa query di dalam blok `bool.filter` lebih hemat CPU dibanding klausa di dalam `bool.must`?**
   * A. Karena blok `filter` membagi data ke shard cadangan secara paralel.
   * B. Karena blok `filter` mengabaikan kalkulasi relevansi skor BM25 dan hasilnya dapat di-cache ke dalam memory bitset Lucene.
   * C. Karena blok `filter` dijalankan di sisi client sebelum query dikirim ke cluster.
   * D. Karena blok `filter` secara otomatis menghapus dokumen yang memiliki nilai null.

3. **Mekanisme apa yang terjadi pada phase pertama pencarian default `query_then_fetch`?**
   * A. Koordinasi node meminta dokumen `_source` lengkap dari seluruh shard.
   * B. Seluruh shard mengembalikan daftar Doc ID beserta nilai skor relevansinya dalam priority queue lokal ke coordinating node.
   * C. Shard menghitung statistik DFS secara global lalu mengembalikannya ke client.
   * D. Coordinating node memetakan routing string ke primary shard secara eksklusif.

4. **Apa fungsi dari parameter `window_size` pada konfigurasi `rescore` Elasticsearch?**
   * A. Menentukan batas maksimal ukuran buffer network saat mengirim response JSON.
   * B. Membatasi jumlah dokumen teratas per shard yang akan dievaluasi ulang oleh model scoring kedua.
   * C. Mengatur batas waktu (timeout) dalam milidetik untuk query yang berjalan lambat.
   * D. Menentukan durasi persistensi cache hasil pencarian di JVM heap.

5. **Di mana Doc Values disimpan dalam struktur arsitektur Lucene, dan mengapa pembacaannya optimal untuk script Painless?**
   * A. Disimpan secara terkompresi di dalam file `.fdt` dokumen mentah.
   * B. Disimpan dalam format berorientasi kolom (*column-oriented on-disk structure*) yang di-load ke memory-mapped file (OS page cache).
   * C. Disimpan di dalam Zookeeper sebagai metadata cluster terdistribusi.
   * D. Disimpan secara acak di heap memory tanpa serialisasi disk.

### Bagian 2: Intermediate (5 Pertanyaan)
6. **Kapan Anda HARUS menggunakan `dfs_query_then_fetch` dibandingkan `query_then_fetch` standar?**
   * A. Setiap saat di cluster produksi untuk menjamin performa penelusuran tercepat.
   * B. Ketika cluster memiliki dataset kecil yang tersebar di banyak shard, dan disparitas statistik lokal shard menyebabkan ketidakkonsistenan skor yang tidak dapat diterima.
   * C. Hanya ketika Anda mengeksekusi aggregasi nested bersarang dengan volume data raksasa.
   * D. Saat Anda menggunakan kueri Painless script yang memerlukan akses ke dokumen stored fields.

7. **Apa dampak langsung terhadap internal Lucene jika query menyertakan `"track_total_hits": true` pada indeks berukuran 100 juta dokumen?**
   * A. Menonaktifkan optimasi Block-Max WAND, memaksa Lucene menghitung skor dan mengunjungi seluruh posting list yang cocok hingga akhir.
   * B. Mengurangi konsumsi heap memory coordinating node hingga 50%.
   * C. Mengalihkan eksekusi query dari Data Node langsung ke Dedicated Master Node.
   * D. Memaksa cluster melakukan garbage collection (Stop-The-World) sebelum mengembalikan hasil.

8. **Manakah dari fungsi decay berikut yang menghasilkan penurunan skor paling landai pada rentang nilai awal sebelum penalti diterapkan secara agresif?**
   * A. `linear`
   * B. `exp`
   * C. `gauss`
   * D. `step`

9. **Jika Anda melihat lonjakan drastis pada metrik `script_compilations` dan search latency meningkat tajam, tindakan manakah yang secara langsung memperbaiki akar masalah?**
   * A. Menambahkan node master baru ke dalam cluster.
   * B. Memindahkan parameter yang berubah-ubah dari script body string ke dalam objek `params`.
   * C. Meningkatkan nilai parameter `number_of_replicas` pada seluruh indeks.
   * D. Menghapus konfigurasi `similarity` kustom dari mapping indeks.

10. **Bagaimana cara kerja mode kombinasi `score_mode: "multiply"` pada `function_score` query?**
    * A. Menjumlahkan skor BM25 dengan hasil kalkulasi fungsi.
    * B. Mengalikan skor relevansi dasar (query match) dengan hasil kalkulasi dari fungsi-fungsi penilai.
    * C. Mengambil nilai tertinggi antara skor BM25 dan skor fungsi.
    * D. Mengalikan nomor segment Doc ID dengan skor akhir.

### Bagian 3: Skenario Kasus Produksi (3 Skenario)

11. **Skenario 1:**  
    Sebuah aplikasi direktori properti mengalami masalah di mana rumah-rumah dengan deskripsi teks sangat panjang (1.000 kata) selalu mendapatkan peringkat lebih rendah dibanding rumah dengan deskripsi singkat (20 kata), meskipun rumah dengan deskripsi panjang tersebut memuat kata kunci pencarian lebih banyak dan lebih relevan secara kontekstual.  
    *Tindakan arsitektural apa pada BM25 similarity yang paling tepat untuk menyeimbangkan penalti panjang dokumen ini tanpa merusak relevansi keseluruhan?*

12. **Skenario 2:**  
    Sistem monitoring cluster Elasticsearch Anda mengeluarkan peringatan: `Search phase execution failure: [parent] Data too large, data for [<transport_request>] would be [1048576000] which is larger than the limit of [1024000000]`. Setelah diinvestigasi, kueri pencarian ternyata menggunakan script Painless yang mengakses data melalui `params['_source']['merchant']['details']['tier']`.  
    *Apa perubahan teknis spesifik yang wajib diimplementasikan pada mapping dan script DSL untuk menghilangkan resiko kegagalan memori ini?*

13. **Skenario 3:**  
    Tim pemasaran Anda menuntut agar produk yang memiliki "Stok Promosi" selalu berada di 5 posisi teratas di halaman pencarian kategori, namun sisa hasil penelusuran lainnya (posisi 6 ke bawah) harus tetap terurut murni secara relevansi teks BM25 alami.  
    *Pendekatan query DSL kombinasi apa yang paling elegan dan deterministik untuk memenuhi SLA bisnis ini tanpa memicu drift pada algoritma rescore?*

---

### Kunci Jawaban Evaluasi

#### Bagian 1 & 2
1. **B** — $k_1$ mengatur saturasi frekuensi kata, $b$ memodulasi tingkat keparahan penalti panjang dokumen.
2. **B** — `filter` tidak menghitung skor dan hasilnya di-cache sebagai bitset yang dapat digunakan kembali secara instan antar thread.
3. **B** — Shard hanya mengembalikan pasangan Doc ID dan float score ke priority queue di coordinating node.
4. **B** — Window size membatasi scope rescoring Lucene hanya pada subset dokumen top-$k$ teratas lokal.
5. **B** — Doc Values adalah struktur on-disk berorientasi kolom yang dibaca secara cepat via memory-mapped file tanpa overhead heap berlebih.
6. **B** — DFS Query Then Fetch hanya dibenarkan jika terjadi dispersi korpus yang drastis antar shard pada indeks kecil.
7. **A** — `track_total_hits: true` menonaktifkan algoritma Block-Max WAND, memaksa traversal posting list secara menyeluruh.
8. **C** — Karakteristik kurva Gaussian memiliki transisi awal berbentuk lonceng datar (*bell curve*).
9. **B** — Parameterisasi script memanfaatkan AST cache dan mencegah lonjakan kompilasi dinamis yang membebani heap.
10. **B** — `multiply` mengalikan skor query dasar dengan faktor kalkulasi fungsi.

#### Bagian 3 (Skenario Kasus)
11. **Analisis Skenario 1:**  
    Masalah ini disebabkan oleh parameter normalisasi panjang ($b$) yang terlalu agresif pada konfigurasi default ($b = 0.75$). Solusinya adalah mendefinisikan *custom similarity* BM25 pada mapping field deskripsi dengan menurunkan nilai $b$ secara terukur (misal ke rentang $0.2 - 0.4$) atau mendekati $0.0$. Hal ini meminimalkan pembagi rasio $|D|/\text{avgdl}$ dalam penyebut formula BM25 sehingga panjang field tidak lagi mendiskon skor kecocokan kata secara eksesif.
12. **Analisis Skenario 2:**  
    Penyebab kegagalan heap adalah ekstraksi `_source` mentah di dalam runtime query Painless. Mengakses `params['_source']` memaksa Elasticsearch mengekstrak dan men-deserialize seluruh dokumen JSON yang terkompresi di segment disk ke dalam struktur memory JVM heap, yang seketika melampaui limit transport breaker. Solusinya: Ubah field target ke tipe data primitif berindeks (`keyword` atau `integer`) yang memiliki *doc_values enabled*, kemudian perbarui skrip Painless untuk membaca langsung melalui struktur kolom: `doc['merchant.details.tier.keyword'].value`.
13. **Analisis Skenario 3:**  
    Pendekatan paling elegan adalah menggunakan kombinasi **`pinned` query** atau konstruksi boolean bertingkat dengan penalti deterministik. `pinned` query secara native dirancang oleh Elasticsearch untuk menempatkan daftar Doc ID promosi spesifik secara mutlak pada peringkat teratas ($1 \dots N$), sementara sisa dokumen lainnya diisi oleh eksekusi sub-query reguler berbasis BM25. Alternatif lainnya adalah menggunakan multi-tier rescoring di mana skor dokumen promo diberikan boost artifisial masif ($+10.000$) yang dipisahkan secara strictly tiered dari skor relevansi reguler.

---

## 16. Summary

* **Okapi BM25** merupakan pondasi kalkulasi teks Lucene modern yang membatasi saturasi kemunculan kata kunci berlebih via parameter $k_1$ serta mengoreksi panjang teks via parameter $b$.
* Mengaktifkan kalkulasi DFS (`dfs_query_then_fetch`) membawa beban koordinasi jaringan ganda (*$2\times$ network round-trips*). Skala produksi enterprise harus memprioritaskan sharding yang homogen dan mengandalkan `query_then_fetch` standar.
* **Block-Max WAND** membawa peningkatan kinerja masif dengan melompati blok-blok posting list yang skor teoritisnya di bawah ambang batas dokumen ke-$k$. Manfaat ini hilang seketika apabila `track_total_hits` dipaksa ke `true`.
* **Arsitektur Scoring Dua Tahap (Two-Phase Retrieval)** adalah pola baku industri tier-1:
  1. *Candidate Retrieval:* Eksekusi cepat, memanfaatkan filter bitset cache dan teks match teroptimasi WAND.
  2. *Rescore Window:* Menerapkan manipulasi bisnis kompleks (jarak, waktu, popularitas, margin) secara efisien hanya pada 100-500 kandidat teratas.
* Penulisan skrip **Painless** di tingkat produksi wajib menerapkan Doc Values (`doc['field'].value`) dan pemisahan parameter dinamis melalui `params` guna mencegah kompilasi ulang yang berpotensi memicu lonjakan latensi atau *CircuitBreakerException*.