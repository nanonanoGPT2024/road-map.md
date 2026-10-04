# Kurikulum Enterprise: Elasticsearch
## Kategori: 04-Backend-and-Database
### BAB 06: Vector Search, Semantic Search & Machine Learning
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Mengonfigurasi Algoritma HNSW Internal**: Membedah cara kerja internal *Hierarchical Navigable Small World* (HNSW) pada Apache Lucene di bawah engine Elasticsearch, serta melakukan *tuning* parameter graf (`m`, `ef_construction`, `ef_search`) untuk menyeimbangkan *Recall@K* terhadap *query latency*.
2. **Mengimplementasikan Strategi Kompresi Vektor Tingkat Lanjut**: Mengonfigurasi dan mengukur efisiensi *Scalar Quantization* (SQ/int8) dan *Product Quantization* (PQ) untuk mereduksi *memory footprint* graf vektor hingga 75% tanpa degradasi signifikan pada akurasi pencarian.
3. **Membangun Arsitektur Hybrid Search dengan Reciprocal Rank Fusion (RRF)**: Merancang pipeline pencarian yang menggabungkan *sparse retrieval* (BM25 / ELSER) dengan *dense retrieval* (kNN) menggunakan fungsi penskoran RRF yang terdistribusi.
4. **Mengisolasi dan Menskalakan Node Kluster untuk ML & Vektor**: Mendesain topologi kluster *production-ready* yang memisahkan node komputasi inferensi (ML Nodes), node indexing graf vektor berorientasi memori *off-heap*, dan node data standar.
5. **Mengatasi Bottleneck Produksi**: Melakukan diagnostik *memory saturation*, *segment merging storms*, dan *long GC pauses* yang diakibatkan oleh alokasi off-heap berlebih pada *Lucene DirectByteBuffer*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Konsep internal Elasticsearch: Segment Lucene, Translog, Flush, Refresh, dan *Inverted Index*.
* Aljabar linier dasar: Perkalian matriks, *Euclidean Distance* ($L_2$), *Cosine Similarity*, dan *Dot Product*.
* Representasi teks modern: Perbedaan tokenisasi leksikal vs *dense embeddings* (Transformer, BERT, MiniLM).
* Arsitektur sistem operasi: Manajemen memori Linux, *Virtual Memory*, *Page Cache*, dan *mmap* (`vm.max_map_count`).

---

### 3. Concept & Internal Architecture

#### 3.1 Anatomi HNSW pada Apache Lucene
Elasticsearch mengabstraksikan modul vektornya melalui implementasi HNSW di Apache Lucene (`KnnFloatVectorField` / `KnnByteVectorField`). 

Graf HNSW mengadopsi struktur data probabilistik berlapis multi-skala (mirip konsep *Skip-List*, namun diproyeksikan ke graf multidimensi):

```
Layer 2 (Sparsest)   [Entry Node] -----------------------------> [Node E]
                          |                                          |
Layer 1                   v                                          v
                     [Node A] -------------> [Node C] ---------> [Node E]
                          |                     |                    |
Layer 0 (Densest)         v                     v                    v
  (All Vectors)      [Node A] -> [Node B] -> [Node C] -> [Node D] -> [Node E]
```

1. **Layer Hierarchy**:
   * *Layer 0* menyimpan seluruh vektor yang terindeks dalam satu segment Lucene.
   * Setiap layer di atasnya ($Layer_1, Layer_2, \dots, Layer_L$) menyimpan subset probabilitas dari vektor layer di bawahnya dengan faktor peluruhan $1/\ln(m)$.
2. **Search Routing Mechanics**:
   * Pencarian dimulai dari *Entry Node* di layer tertinggi ($Layer_L$).
   * Algoritma mengeksekusi navigasi *greedy* di layer tersebut hingga mencapai *local minimum* (tidak ada tetangga yang lebih dekat ke vektor kueri).
   * Algoritma kemudian melompat turun ke layer di bawahnya pada node posisi terakhir dan mengulangi proses hingga mencapai *Layer 0*.
   * Di *Layer 0*, algoritma mengeksekusi penelusuran balok prioritasi (*beam search*) menggunakan antrean prioritas (*priority queue*) berukuran `num_candidates` (atau `ef_search`) untuk mengekstrak $K$ tetangga terdekat definitif.
3. **Graph Construction Parameters**:
   * `m` (Maksimum edge per node): Menentukan derajat konektivitas setiap simpul. Nilai `m` tinggi meningkatkan akurasi kueri pada data berdimensi tinggi, tetapi menaikkan ukuran memori graf secara linear dan memperlambat *indexing throughput*.
   * `ef_construction` (Ukuran dynamic candidate list saat build): Menentukan luasnya eksplorasi graf saat node baru disisipkan. Nilai yang besar menghasilkan graf dengan keterhubungan global yang lebih optimal (*high recall*), namun meningkatkan latensi kompilasi segment secara eksponensial.

#### 3.2 Alokasi Memori: Heap vs Off-Heap (Native Memory)
Struktur data graf HNSW **tidak disimpan di dalam Java Heap JVM**, melainkan dipetakan langsung ke *virtual memory* proses Elasticsearch menggunakan panggilan sistem `mmap` (`MappedByteBuffer` di Java/Lucene).

```
+--------------------------------------------------------------------------+
| Total Server RAM (e.g., 64 GB)                                           |
+------------------------------------+-------------------------------------+
| JVM Heap (Max 31 GB - CompressedOOP)| Lucene Memory / OS Page Cache (33 GB) |
|                                    |                                     |
|  - Indexing Buffers                |  - Lucene Inverted Index Cache      |
|  - Cluster State & Metadata        |  - HNSW Vectors & Graphs (mmap)     |
|  - Aggregation Buckets             |  - Quantized Vectors (Off-heap)     |
|  - Open Search Contexts            |  - OS File System Cache             |
+------------------------------------+-------------------------------------+
```

*Aturan Arsitektur Kritis:* Jika heap dialokasikan terlalu besar (misal: 58 GB pada host 64 GB), Lucene HNSW graf akan berebut ruang dengan OS Page Cache. Hal ini memicu *disk thrashing* saat traversi graf, menyebabkan latensi kueri melonjak dari milidetik ke detik (*thrashing cliff*).

#### 3.3 Kompresi Vektor: Scalar Quantization (SQ)
Vektor berdimensi tinggi tipikal berpresisi `float32` membutuhkan 4 byte per dimensi. Vektor berukuran 1536 dimensi (OpenAI embedding) membutuhkan:
$$\text{Ukuran} = 1536 \times 4\text{ byte} = 6.144\text{ KB per dokumen}$$

Untuk $10.000.000$ dokumen, murni representasi vektornya (tanpa graf HNSW) membutuhkan:
$$10.000.000 \times 6.144\text{ KB} \approx 57,22\text{ GB RAM Off-Heap}$$

*Scalar Quantization* (SQ8) mentransformasi nilai floating point 32-bit $[-\infty, +\infty]$ menjadi integer 8-bit $[ -128, 127 ]$ atau $[0, 255]$:
$$q_i = \text{round}\left( \frac{v_i - \min}{\max - \min} \times 255 \right)$$

Keuntungan SQ8:
* Reduksi penggunaan memori vektor mentah sebesar 75% (dari 4 byte menjadi 1 byte per dimensi).
* Memungkinkan pemanfaatan instruksi CPU SIMD (AVX-512 / NEON) untuk kalkulasi *dot product* integer berkecepatan tinggi.

#### 3.4 Hybrid Search: Reciprocal Rank Fusion (RRF)
Pendekatan pencarian hybrid modern menghindari *score normalisation* linear manual (yang rentan terhadap instabilitas magnitudo BM25 vs skor Cosine). Elasticsearch mengimplementasikan RRF secara *native* pada level *shard collector*.

Formula RRF:
$$RRF(d \in D) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
Di mana:
* $M$ adalah himpunan sistem retrieval (misal: $M = \{\text{BM25}, \text{Dense Vector}\}$).
* $r_m(d)$ adalah *rank* (peringkat posisi, dimulai dari $1$) dari dokumen $d$ dalam sistem retrieval $m$.
* $k$ adalah konstanta perataan (*smoothing constant*), secara default bernilai $60$. Parameter ini mengontrol dampak dokumen yang berada di peringkat atas dibandingkan peringkat menengah.

---

### 4. Why & What

| Dimensi Evaluasi | Lexical Search (BM25) | Dense Vector Search (kNN) | Learned Sparse (ELSER) | Hybrid Search (RRF) |
| :--- | :--- | :--- | :--- | :--- |
| **Prinsip Dasar** | Exact word match, TF-IDF, Term Proximity | Semantic projection ke latent multidimensional space | Pseudo-token expansion dengan ML context | Penggabungan peringkat non-parametrik (Lexical + Vector) |
| **Kelemahan Utama** | *Vocabulary Mismatch Problem* (gagal memahami sinonim) | *Out-of-Domain Failure*, buruk pada pencarian SKU/Spesifik | Menghabiskan resource inferensi tinggi pada teks masif | Kompleksitas komputasi bertambah (double collection phase) |
| **Kebutuhan Resource**| Sangat rendah, efisien di CPU & RAM | Tinggi di Off-heap Memory (RAM) & Komputasi FP32/INT8 | Tinggi di CPU ML Inference (token expansion) | Seimbang, butuh alokasi CPU query phase & Off-heap |
| **Kasus Penggunaan Optimal** | Pencarian kode produk, nomor pesanan, log machine | Q&A konseptual, temu balik gambar/audio, sinonimitas | Dokumen teks panjang domain ambigu tanpa training embedding | Enterprise Search, Catalog Marketplace, Legal/Regulatory |

---

### 5. How (Workflow Detail)

Alur kerja end-to-end pemrosesan vektor, inferensi model, indexing segment, dan *retrieval execution* tingkat lanjut:

```
[Ingestion Phase]
Dokumen Mentah (JSON)
       │
       ▼
[Elasticsearch Ingest Pipeline]
       │
       ├─► [Inference Processor: Text Embeddings Model]
       │         (Eland / Uploaded PyTorch Model on ML Node)
       │         Input: "database latency high" ──► Output: [0.021, -0.441, ...] (384-dim)
       ▼
[Lucene Indexing Core]
       │
       ├─► 1. Tulis ke Inverted Index (Tokens)
       ├─► 2. Kalkulasi Quantile SQ8 (Float32 -> Int8)
       ├─► 3. Konstruksi HNSW Graph (Iterative insertion via ef_construction & m)
       └─► 4. Flush ke Lucene Segments (.vec, .vex, .vem files via mmap)

─────────────────────────────────────────────────────────────────────────────────────────

[Query Execution Phase (Hybrid RRF)]
Kueri Pengguna: "lambat koneksi postgres"
       │
       ├── Parallel Branch A ────────────────────────┐
       │                                             │
       ▼                                             ▼
[Lexical Inverted Index]                     [Inference Phase]
  - BM25 match text: "lambat koneksi"           - Convert to query embedding
  - Generate ranked list:                       - Lucene HNSW Traversal:
    1. Doc #42 (Score: 8.5)                       Beam search via ef_search
    2. Doc #10 (Score: 7.2)                     - Generate ranked list:
    3. Doc #88 (Score: 6.1)                       1. Doc #99 (Sim: 0.92)
                                                  2. Doc #42 (Sim: 0.89)
                                                  3. Doc #12 (Sim: 0.81)
       │                                             │
       └──────────────────────┬──────────────────────┘
                              │
                              ▼
           [Reciprocal Rank Fusion Collector]
             Doc #42: RRF = 1/(60+1) + 1/(60+2) = 0.01639 + 0.01612 = 0.03251
             Doc #99: RRF = 0        + 1/(60+1) = 0.01639
             Doc #10: RRF = 1/(60+2) + 0        = 0.01612
                              │
                              ▼
                 Urutan Akhir Terdistribusi:
                 1. Doc #42 (Pemenang Konsensus)
                 2. Doc #99
                 3. Doc #10
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Navigasi Graf HNSW
Bayangkan Anda ingin mencari rumah seseorang di wilayah geografis yang luas tanpa GPS detail:
* **Layer 2 (Pesawat Udara):** Anda terbang di atas peta nasional. Dari Jakarta, Anda langsung melompat jauh ke Surabaya karena jarak Euclidean geografisnya paling mendekati target di Jawa Timur. Anda mendarat di bandara Surabaya.
* **Layer 1 (Mobil di Jalan Tol):** Dari bandara Surabaya, Anda menggunakan jalan tol antar kota untuk melompat ke pinggiran kota Malang.
* **Layer 0 (Jalan Perumahan):** Anda menelusuri jalan-jalan kecil di perumahan target, memeriksa tetangga-tetangga sekitar secara sistematis hingga menemukan nomor rumah yang tepat.

Struktur multi-layer ini memangkas kompleksitas komparasi vektor dari $O(N)$ (brute-force scan ke seluruh database) menjadi $O(\log N)$.

#### Diagram Struktur Segment Lucene untuk Vektor
```
Segment Lucene Directory (Disk / Off-Heap OS Page Cache)
├── _0.doc, _0.pos, _0.tim  --> Inverted Index (BM25 Engine)
├── _0.kdd                  --> Metadata Vektor (Dimensi, tipe metrik, kuantisasi)
├── _0.kdi                  --> Data Index Graf HNSW (Struktur graf layer & edges)
└── _0.kdm                  --> Vektor Numerik Mentah / Quantized Payload Array
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Basic Dense Vector Mapping & Exact Query
Mapping sederhana tanpa ingest pipeline (vektor disediakan langsung oleh klien) dengan algoritma kNN standar:

```json
// PUT /knowledge-base-simple
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0
  },
  "mappings": {
    "properties": {
      "title": { "type": "text" },
      "title_vector": {
        "type": "dense_vector",
        "dims": 3,
        "index": true,
        "similarity": "cosine"
      }
    }
  }
}

// POST /knowledge-base-simple/_doc/1
{
  "title": "Konfigurasi Database Connection Pool",
  "title_vector": [0.12, 0.89, -0.44]
}

// POST /knowledge-base-simple/_search
{
  "knn": {
    "field": "title_vector",
    "query_vector": [0.10, 0.85, -0.40],
    "k": 1,
    "num_candidates": 10
  }
}
```

#### 7.2 Practical Example: Enterprise-Grade Production Configuration
Berikut adalah implementasi skala enterprise menggunakan:
1. `dense_vector` terkuantisasi (int8 scalar quantization via `index_options`).
2. Parameter HNSW (`m=16`, `ef_construction=100`).
3. Ingest Pipeline dengan local ML inference processor.
4. Hybrid Search Query mengeksekusi BM25 + kNN terintegrasi menggunakan Reciprocal Rank Fusion (RRF) dan *Hard Filtering*.

##### Langkah A: Definisikan Index Template Produksi
```json
PUT /_index_template/enterprise_knowledge_template
{
  "index_patterns": ["kb-v1-*"],
  "template": {
    "settings": {
      "number_of_shards": 3,
      "number_of_replicas": 1,
      "index.routing.allocation.include._tier_preference": "data_hot",
      "index.mapping.total_fields.limit": 2000,
      "index.refresh_interval": "10s",
      "index.translog.durability": "async",
      "index.translog.sync_interval": "30s"
    },
    "mappings": {
      "_source": { "enabled": true },
      "properties": {
        "document_id": { "type": "keyword" },
        "tenant_id": { "type": "keyword" },
        "is_active": { "type": "boolean" },
        "content": {
          "type": "text",
          "analyzer": "standard"
        },
        "content_embedding": {
          "type": "dense_vector",
          "dims": 768,
          "index": true,
          "similarity": "dot_product",
          "index_options": {
            "type": "int8_hnsw",
            "m": 16,
            "ef_construction": 100
          }
        },
        "created_at": { "type": "date" }
      }
    }
  }
}
```

##### Langkah B: Buat Ingest Pipeline dengan ML Inference
```json
PUT /_ingest/pipeline/nlp_embedding_pipeline
{
  "description": "Transform text ke embedding secara in-cluster",
  "processors": [
    {
      "inference": {
        "model_id": "sentence-transformers__all-minilm-l6-v2",
        "target_field": "inferred_data",
        "field_map": {
          "content": "text_field"
        }
      }
    },
    {
      "set": {
        "field": "content_embedding",
        "value": "{{{inferred_data.predicted_value}}}"
      }
    },
    {
      "remove": {
        "field": "inferred_data"
      }
    }
  ]
}
```

##### Langkah C: Eksekusi Advanced Hybrid Retrieval dengan RRF
```json
POST /kb-v1-production/_search
{
  "retrievers": [
    {
      "rrf": {
        "retrievers": [
          {
            "standard": {
              "query": {
                "bool": {
                  "must": [
                    {
                      "multi_match": {
                        "query": "kebocoran memori pada thread pool",
                        "fields": ["content"]
                      }
                    }
                  ],
                  "filter": [
                    { "term": { "tenant_id": "enterprise-corp" } },
                    { "term": { "is_active": true } }
                  ]
                }
              }
            }
          },
          {
            "knn": {
              "field": "content_embedding",
              "query_vector_builder": {
                "text_embedding": {
                  "model_id": "sentence-transformers__all-minilm-l6-v2",
                  "model_text": "kebocoran memori pada thread pool"
                }
              },
              "k": 20,
              "num_candidates": 100,
              "filter": [
                { "term": { "tenant_id": "enterprise-corp" } },
                { "term": { "is_active": true } }
              ]
            }
          }
        ],
        "rank_constant": 60,
        "rank_window_size": 20
      }
    }
  ],
  "_source": ["document_id", "content", "created_at"]
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
* **Domain:** Enterprise Customer Support Search Platform.
* **Volume Data:** 50.000.000 dokumen tiket dukungan teknis dengan akumulasi pertumbuhan 100.000 tiket/hari.
* **Dimensi Model:** 768 dimensi (*all-mpnet-base-v2*).
* **Beban Kueri:** 1.500 QPS (Queries Per Second) pada jam sibuk.
* **SLA:** Latensi p99 $\le 45\text{ ms}$, Recall@10 $\ge 92\%$.

#### Akar Masalah Awal (Baseline Failure)
Arsitektur awal menggunakan Float32 HNSW mentah pada node data Elasticsearch generik:
1. **OOM / Swapping:** Kebutuhan memori vektor:
   $$50.000.000 \times (768 \times 4 + (2 \times 16 \times 4))\text{ bytes} \approx 150\text{ GB per replica}$$
   Total kebutuhan untuk 1 primary + 1 replica = $300\text{ GB Off-Heap RAM}$.
2. Data node mengalami tabrakan alokasi: Java Heap diset 31 GB pada host 64 GB RAM, hanya menyisakan ~30 GB untuk Page Cache. Terjadi *high disk I/O thrashing*, mendorong latensi p99 hingga $2.400\text{ ms}$.
3. Single pipeline bottleneck: Kluster indexing lag hingga 14 jam.

#### Transformasi Arsitektur Produksi

```
[External Traffic / API Gateway]
                │
                ▼
[Dedicated Elasticsearch ML/Coordinating Nodes] (2x Nodes, 32 CPU, 64 GB RAM)
  - Melakukan Embedding Inference & Ingest Routing
  - Menerima Search Query & Mengonsolidasikan RRF
                │
                ├─── Internally Dispatched via Cluster Transport ───┐
                ▼                                                   ▼
[Hot Vector Data Node 1]                             [Hot Vector Data Node 2]
Host: 128 GB RAM, 32 Cores                           Host: 128 GB RAM, 32 Cores
JVM Heap: 31 GB                                      JVM Heap: 31 GB
OS Page Cache (Off-Heap): ~92 GB                     OS Page Cache (Off-Heap): ~92 GB
Storage: NVMe Gen4 (RAID 0)                          Storage: NVMe Gen4 (RAID 0)
Indices: int8_hnsw Quantized Vectors                 Indices: int8_hnsw Quantized Vectors
```

#### Langkah Remediasi
1. **Penerapan Scalar Quantization (int8):** Mengurangi alokasi buffer vektor per dokumen dari 3.072 byte ke 768 byte. Total kebutuhan memori per node anjlok dari 150 GB menjadi ~48 GB, muat sepenuhnya dalam Page Cache 92 GB.
2. **Penyetelan `ef_construction` dan `m`:**
   * Diturunkan dari default yang tidak terkendali ke `m=16`, `ef_construction=100`.
   * Pembangunan graf menjadi 2,8 kali lebih cepat tanpa degradasi skor *Mean Reciprocal Rank* (MRR).
3. **Pemberian Prefilter Vektor Terindeks:**
   Memaksa eksekusi query embedding menyertakan filter metadata (`tenant_id`) langsung di dalam parameter block `knn.filter` (mengaktifkan *Lucene BitSet Pre-Filtering* alih-alih *post-filtering*).

#### Hasil Pasca-Implementasi
* Latensi pencarian p99 turun stabil ke **28 ms** di bawah beban 1.500 QPS.
* Reduksi biaya infrastruktur sebesar 60% karena jumlah data node berkurang dari 12 node menjadi 4 node berefisiensi tinggi.

---

### 9. Trade-offs

| Parameter / Opsi | Pilihan A | Pilihan B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Precision Model** | `float32` (Uncompressed) | `int8_hnsw` (Quantized) | `float32` memberikan Recall absolut tertinggi (100% baseline) namun butuh 4x konsumsi memori. `int8` mengorbankan Recall 1-2%, tetapi menghemat 75% memory footprint dan 2x lebih cepat via instruksi CPU SIMD. |
| **Graph Density (`m`)** | `m = 64` | `m = 16` | Nilai 64 memberikan akurasi navigasi graf superior pada data audio/gambar resolusi sangat tinggi, namun ukuran file graf (.vex) melonjak 4x, menurunkan throughput indexing hingga 65%. Nilai 16 adalah batas *sweet spot* optimal untuk representasi teks. |
| **Search Parameter (`ef_search`)** | `ef_search = 500` | `ef_search = 50` | Nilai 500 menggaransi pencarian graf mendekati brute-force scan (*exhaustive*), namun meningkatkan *latency floor* per kueri dari sub-10ms menjadi >60ms. |
| **Filter Integration Strategy** | Post-filtering (Filter di query parent) | Pre-filtering (Filter di blok `knn.filter`) | Post-filtering dapat menghasilkan kurang dari $K$ hasil jika banyak vektor tereliminasi setelah traversal graf. Pre-filtering membangun `RoaringBitSet` sebelum graf dieksplorasi, menjamin tepat $K$ dokumen ditemukan tetapi menambah overhead bitset scan. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Alokasi JVM Heap Melampaui 32 GB
* **Kesalahan Fatal:** Mengalokasikan heap JVM sebesar 48 GB pada node Elasticsearch 64 GB dengan asumsi "semakin besar memori untuk Java, semakin cepat performanya".
* **Dampak Sistemik:**
  1. Fitur JVM *Compressed Object Pointers* (CompressedOops) nonaktif. Penunjuk memori membengkak dari 32-bit ke 64-bit, secara riil memotong efisiensi heap sebesar 20-30%.
  2. Menyisakan hanya 16 GB untuk *Off-Heap OS Page Cache*. Karena graf HNSW hidup di off-heap, segmen file graf dipaksa dibaca ulang terus-menerus dari disk I/O (*Disk Bottleneck*).
* **Solusi Perbaikan:** Pasang JVM Heap maksimal di **30 GB atau 31 GB** (verifikasi log: pastikan `Compressed Oops: enabled`). Sisakan sisa 50-60% RAM sistem host untuk Lucene *Off-Heap memory*.

#### 10.2 Dimensionality Mismatch Saat Model Update
* **Gejala:** Muncul galat eksplisit dari engine segment:
  `IllegalArgumentException: vector has 384 dimensions, but field requires 768`.
* **Akar Masalah:** Developer mengganti model teks embedding pada Ingest Pipeline tanpa melakukan reindex ke index baru yang memiliki pemetaan `dims` terpisah.
* **Solusi Perbaikan:** Vektor dimension bersifat *immutable* dalam mapping segment Lucene. Terapkan strategi **Blue/Green Indexing**:
  1. Buat index baru `target-v2` dengan `dims` yang disesuaikan.
  2. Hubungkan pipeline ke model baru.
  3. Lakukan `_reindex` async.
  4. Switch mapping melalui Elasticsearch Alias.

#### 10.3 Segment Merging Storm Mengakibatkan Spike Latensi Query
* **Gejala:** Latensi pencarian kNN mendadak melonjak hingga >5000ms secara intermiten setiap beberapa puluh menit.
* **Akar Masalah:** Lucene mengeksekusi merge background multi-segment besar secara simultan. Membangun ulang graf HNSW untuk segment baru hasil merge merupakan operasi yang sangat intensif CPU.
* **Mitigasi Produksi:**
  1. Batasi alokasi thread merge di setting cluster:
     ```json
     PUT /_cluster/settings
     {
       "transient": {
         "indices.store.throttle.type": "merge",
         "indices.store.throttle.max_bytes_per_sec": "50mb"
       }
     }
     ```
  2. Nonaktifkan refresh interval pendek pada proses bulk-indexing berat (`"refresh_interval": "-1"`).
  3. Jalankan `_forcemerge?max_num_segments=1` secara terjadwal di jam *off-peak*.

---

### 11. Best Practices (Production Checklist)

| Tahapan | Checklist Item | Standar Validasi |
| :--- | :--- | :--- |
| **Kapasitas** | Formula RAM Off-Heap | Sediakan minimal: $(N \times (\text{dims} \times \text{bytes} + 2 \times m \times 4\text{ bytes})) \times 1.25$ di luar batas Heap JVM. |
| **Mapping** | Scalar Quantization Enabled | Pastikan menggunakan `"type": "int8_hnsw"` untuk data teks umum berdimensi $>256$. |
| **Mapping** | Fungsi Kesamaan Matriks | Gunakan `dot_product` jika vektor embeddings sudah dinormalisasi ke *unit length* ($L_2$ norm = 1). Ini 2-3x lebih cepat dibanding `cosine` karena memangkas kalkulasi akar pembagi. |
| **Topologi** | Node Role Isolation | Jangan jalankan model inference berat di Node Data Vektor. Buat dedicated node dengan role: `["ml", "coordinating_only"]`. |
| **OS Tuning** | Virtual Memory Max Map Count | Jalankan `sysctl -w vm.max_map_count=262144` (atau lebih tinggi) untuk menampung mmap segment Lucene yang masif. |
| **Indexing** | Segment Merge Optimization | Eksekusi `POST /my-index/_forcemerge?max_num_segments=1` pada index read-only untuk memadatkan graf HNSW ke satu lapisan utuh tanpa overhead multi-segment searching. |
| **Querying** | Batas Konservatif `num_candidates` | Tetapkan `num_candidates` di kisaran $1.5 \times K$ hingga $3 \times K$ untuk keseimbangan latensi vs akurasi. Menyetel di atas $10 \times K$ memberikan diminishing return. |

---

### 12. Hands-on Practice

Panduan praktikum langkah demi langkah untuk mengonfigurasi kluster, membuat pipeline, dan menguji retrieval hybrid. Seluruh artefak praktikum ini dapat disimpan pada folder direktori: `hands-on/m02/`.

#### Langkah 1: Siapkan Lingkungan Pengujian via Docker Compose
Simpan file berikut di `hands-on/m02/docker-compose.yml`:

```yaml
version: '3.8'
services:
  es-vector:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    container_name: es-vector-node
    environment:
      - node.name=es-vector-node
      - cluster.name=vector-cluster
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms2g -Xmx2g"
      - xpack.security.enabled=false
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    ports:
      - "9200:9200"
    healthcheck:
      test: ["CMD-SHELL", "curl -s http://localhost:9200/_cat/health | grep -q green || exit 1"]
      interval: 10s
      timeout: 10s
      retries: 5
```
Jalankan kluster:
```bash
docker compose -f hands-on/m02/docker-compose.yml up -d
```

#### Langkah 2: Buat Skema Index dengan int8 Quantization
Simpan script di `hands-on/m02/setup_index.sh`:

```bash
#!/bin/bash

curl -X PUT "http://localhost:9200/products-semantic" \
     -H 'Content-Type: application/json' \
     -d '{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "index.refresh_interval": "1s"
  },
  "mappings": {
    "properties": {
      "product_id": { "type": "keyword" },
      "category": { "type": "keyword" },
      "sku_code": { "type": "keyword" },
      "description": { "type": "text" },
      "description_vector": {
        "type": "dense_vector",
        "dims": 4,
        "index": true,
        "similarity": "dot_product",
        "index_options": {
          "type": "int8_hnsw",
          "m": 16,
          "ef_construction": 100
        }
      }
    }
  }
}'
```
Eksekusi:
```bash
bash hands-on/m02/setup_index.sh
```

#### Langkah 3: Ingest Data Vektor (Unit Length Normalized)
Simpan file data di `hands-on/m02/bulk_insert.sh`:

```bash
#!/bin/bash

# Vektor 4-dimensi dinormalisasi (|v| = 1.0) untuk fungsi dot_product
curl -X POST "http://localhost:9200/products-semantic/_bulk?refresh=true" \
     -H 'Content-Type: application/x-ndjson' \
     -d '
{"index":{"_id":"1"}}
{"product_id":"PROD-A","category":"electronics","sku_code":"EL-001","description":"Mechanical Wireless Keyboard RGB Switches","description_vector":[0.5, 0.5, 0.5, 0.5]}
{"index":{"_id":"2"}}
{"product_id":"PROD-B","category":"electronics","sku_code":"EL-002","description":"Ergonomic Mouse Bluetooth Silent Clicks","description_vector":[0.5, 0.5, -0.5, -0.5]}
{"index":{"_id":"3"}}
{"product_id":"PROD-C","category":"office","sku_code":"OF-101","description":"Standing Desk Dual Motor Anti-Collision","description_vector":[-0.5, -0.5, 0.5, 0.5]}
{"index":{"_id":"4"}}
{"product_id":"PROD-D","category":"office","sku_code":"OF-102","description":"Steelcase Ergonomic Mesh High Back Chair","description_vector":[-0.5, -0.5, -0.5, -0.5]}
'
```
Eksekusi:
```bash
bash hands-on/m02/bulk_insert.sh
```

#### Langkah 4: Eksekusi Hybrid Retrieval (RRF) dengan Pre-Filtering
Simpan file query di `hands-on/m02/search_hybrid.sh`:

```bash
#!/bin/bash

curl -X POST "http://localhost:9200/products-semantic/_search" \
     -H 'Content-Type: application/json' \
     -d '{
  "retrievers": [
    {
      "rrf": {
        "retrievers": [
          {
            "standard": {
              "query": {
                "bool": {
                  "must": [
                    { "match": { "description": "Ergonomic" } }
                  ],
                  "filter": [
                    { "term": { "category": "electronics" } }
                  ]
                }
              }
            }
          },
          {
            "knn": {
              "field": "description_vector",
              "query_vector": [0.48, 0.52, -0.49, -0.51],
              "k": 5,
              "num_candidates": 10,
              "filter": [
                { "term": { "category": "electronics" } }
              ]
            }
          }
        ],
        "rank_constant": 60,
        "rank_window_size": 10
      }
    }
  ]
}'
```
Eksekusi:
```bash
bash hands-on/m02/search_hybrid.sh
```
*Hasil Verifikasi:* Dokumen `PROD-B` akan menempati urutan teratas karena memenangkan konsensus tertinggi antara kecocokan leksikal term "Ergonomic" dan kedekatan sudut kosinus vektor pada filter kategori "electronics".

---

### 13. Exercise

#### Level 1 - Easy
Tulis skrip pemetaan Elasticsearch untuk indeks `article-embeddings` yang memuat field `vector_data` berukuran 512 dimensi. Gunakan metrik kedekatan Euclidean (`l2_norm`). Konfigurasi parameter HNSW `m` ke angka 32 dan `ef_construction` ke 64.

#### Level 2 - Medium
Diberikan indeks e-commerce dengan mapping sebagai berikut:
* `name` (text)
* `brand` (keyword)
* `price` (float)
* `image_embedding` (dense_vector, 128 dims)

Buat satu kueri kNN murni yang mencari 10 produk dengan `image_embedding` terdekat terhadap kueri vektor, dengan batasan keras (*hard constraint*): hanya memproses produk dengan `brand: "Logitech"` dan rentang `price` antara 200 hingga 800. Pastikan pemfilteran diterapkan pada level graf HNSW (*pre-filtering*).

#### Level 3 - Hard
Rancang arsitektur segment dan tulis kueri Elasticsearch yang mengombinasikan tiga sistem penelusuran secara paralel menggunakan skema penskoran kustom / multi-retriever:
1. Lexical BM25 match pada kolom `title`.
2. Dense Vector kNN search pada kolom `dense_emb` (384-dim).
3. Sparse Vector retrieval pada kolom `sparse_tokens` (ELSER).

Integrasikan ketiganya ke dalam `rrf` pipeline dengan nilai smoothing rank konstan $k = 40$. Tambahkan parameter fallback jika dokumen tidak memiliki representasi sparse vector.

---

### 14. Challenge

**Skenario Kasus Kompleks:**
Sebuah platform media berita nasional memiliki volume 20 juta artikel berita. Redaksi membutuhkan fitur *Real-Time Duplicate Detection* dan *Related Story Recommendations*.
* **Beban Ingest:** Rata-rata 50 artikel baru per menit, dengan lonjakan hingga 500 artikel per menit pada kejadian insidental penting.
* **Beban Pembaca:** 3.000 QPS penelusuran rekomendasi relevan.
* **Kendala:** Latensi kueri pencarian rekomendasi tidak boleh melampaui 20 ms pada persentil p99. Tim DevOps melaporkan bahwa saat lonjakan ingest terjadi, latensi kueri rekomendasi melonjak hingga 450 ms akibat fragmentasi segment Lucene dan penulisan graf HNSW yang agresif.

**Instruksi Tantangan:**
1. Desain arsitektur cluster Elasticsearch tanpa downtime (*zero-downtime*) yang menyelesaikan konflik isolasi resource antara proses indexing graf HNSW ber-throughput tinggi vs kueri pembaca bervolume 3.000 QPS.
2. Tentukan konfigurasi engine index (`refresh_interval`, `translog`, merge policy, segment size bounds).
3. Definisikan strategi shard allocation dan node routing agar segment-segment HNSW yang baru dibentuk tidak mengganggu segment lama yang sudah ter-cache optimal di memory Page Cache.

*(Peserta diminta menyusun arsitektur sistem tertulis, skema index, parameter sistem operasi, dan file konfigurasi kluster lengkap).*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda & Konseptual)
1. **Di manakah graf HNSW dialokasikan di dalam hierarki memori host Elasticsearch?**
   * A. Java Heap Space
   * B. PermGen / Metaspace
   * C. Off-Heap Virtual Memory via Lucene DirectByteBuffer / mmap
   * D. Translog Buffer
   * *Jawaban:* **C**. Vektor dan struktur graf HNSW dipetakan secara native ke memori virtual menggunakan Lucene `mmapDirectory` untuk mencegah GC pause dan memanfaatkan OS Page Cache.

2. **Apa dampak utama dari meningkatkan parameter `ef_construction` saat pembuatan index dense_vector?**
   * A. Mengurangi latensi kueri saat pencarian runtime.
   * B. Meningkatkan akurasi konektivitas graf (kualitas recall) tetapi memperlambat proses indexing secara drastis.
   * C. Mengurangi penggunaan memori disk sebesar 50%.
   * D. Mengotomatisasi proses down-sampling dimensi vektor.
   * *Jawaban:* **B**. `ef_construction` mendefinisikan seberapa dalam eksplorasi graf saat menyisipkan simpul baru. Angka yang lebih besar menghasilkan graf yang lebih terstruktur dengan komparasi edge yang jauh lebih intensif, meningkatkan waktu kompilasi segment.

3. **Berapa byte memori mentah yang dihemat per dimensi jika beralih dari representasi default `float32` ke `int8_hnsw` (Scalar Quantization)?**
   * A. 1 Byte
   * B. 2 Byte
   * C. 3 Byte
   * D. 4 Byte
   * *Jawaban:* **C**. Float32 menggunakan 4 byte per dimensi, sedangkan int8 menggunakan 1 byte per dimensi. Dengan demikian, terjadi penghematan sebesar 3 byte (75%) per dimensi.

4. **Metrik kesamaan (`similarity`) mana yang paling optimal secara komputasi jika semua vektor embedding masukan telah dinormalisasi ke panjang magnitudo 1.0 (Unit Length)?**
   * A. `l2_norm`
   * B. `cosine`
   * C. `dot_product`
   * D. `manhattan`
   * *Jawaban:* **C**. Jika panjang vektor sudah 1.0, formula Cosine identik dengan Dot Product. Pilihan `dot_product` menghindari kalkulasi pembagian terhadap magnitudo vektor ($\sqrt{\sum x^2}$), sehingga membutuhkan siklus CPU yang jauh lebih rendah.

5. **Apa fungsi konstanta `rank_constant` ($k$) pada algoritma Reciprocal Rank Fusion (RRF)?**
   * A. Menghapus dokumen yang berada di bawah peringkat $k$.
   * B. Mengontrol bobot pengaruh dokumen pada peringkat teratas agar tidak memonopoli perolehan skor akhir dibanding peringkat menengah.
   * C. Mengalikan skor BM25 dengan skor Cosine.
   * D. Menentukan batas jumlah dokumen maksimal yang dikembalikan shard.
   * *Jawaban:* **B**. Konstanta $k$ (default 60) menstabilkan denominator penskoran sehingga margin skor antara peringkat 1 dan 2 tidak mendominasi dokumen yang konsisten muncul di peringkat menengah pada berbagai retriever.

#### Bagian 2: Intermediate (Analisis Sistem & Konfigurasi)
6. **Jika Anda memiliki indeks dengan 5 shard dan menjalankan pencarian kNN dengan `num_candidates: 50`, berapa total kandidat maksimal yang dievaluasi di seluruh kluster sebelum mengembalikan top-k?**
   * A. 50 kandidat.
   * B. 10 kandidat per shard.
   * C. 250 kandidat (50 kandidat per shard).
   * D. Tergantung jumlah core CPU node koordinasi.
   * *Jawaban:* **C**. Parameter `num_candidates` dieksekusi secara independen pada level lokal tiap segment/shard. Node koordinasi nantinya akan menggabungkan ($5 \times 50 = 250$) hasil lokal tersebut untuk disaring menjadi peringkat $K$ teratas secara global.

7. **Mengapa menempatkan klausa filter di luar blok `knn` (Post-Filtering) dapat menyebabkan penurunan akurasi jumlah hasil pencarian ($K$) yang diinginkan?**
   * *Jawaban Singkat:* Pada post-filtering, kNN collector terlebih dahulu mengumpulkan $K$ tetangga terdekat dari graf HNSW tanpa melihat filter. Jika dokumen-dokumen yang didapat tersebut kemudian didiskualifikasi oleh query filter luar, jumlah dokumen final yang dikembalikan bisa kurang dari $K$, bahkan dapat bernilai kosong.

8. **Apa konsekuensi teknis dari menjalankan `_forcemerge?max_num_segments=1` pada indeks yang masih menerima beban penulisan (indexing) aktif secara terus-menerus?**
   * *Jawaban Singkat:* Force merge ke 1 segment menguras I/O disk dan komputasi CPU untuk menyusun ulang seluruh graf HNSW ke satu segmen monolitik raksasa. Jika penulisan baru masuk, segmen-segmen kecil baru akan tetap tercipta, membatalkan tujuan konsolidasi tunggal tersebut dan mengakibatkan degradasi performa (*I/O bandwidth starvation*).

9. **Sebutkan peran direktori file `.kdm`, `.kdd`, dan `.kdi` di dalam segment Lucene.**
   * *Jawaban Singkat:* File `.kdm` menyimpan metadata kuantisasi dan parameter graf; file `.kdd` menyimpan nilai data vektor numerik; dan file `.kdi` menyimpan relasi struktural simpul serta pointer layer pada graf HNSW.

10. **Bagaimana parameter kernel Linux `vm.max_map_count` mempengaruhi stabilitas node vector Elasticsearch berkapasitas besar?**
    * *Jawaban Singkat:* Lucene menggunakan `mmap` untuk memetakan setiap segment file graf vektor ke virtual memory table OS. Jika nilai `vm.max_map_count` terlalu rendah (misal default kernel 65530), Elasticsearch akan mengalami crash dengan error `OutOfMemoryError: Map failed` begitu jumlah segment membesar melampaui limit mapping OS.

#### Bagian 3: Production Scenario Cases
11. **Skenario Kasus A:**
    Sebuah kluster Elasticsearch dengan 3 Node Data (masing-masing 32 GB RAM, 16 GB JVM Heap) menampung index vektor dengan total 15 juta dokumen (768 dimensi, `float32`). Utilisasi CPU stabil di angka 15%, namun latensi penelusuran melonjak dari 15ms menjadi 2.800ms per kueri. Disk I/O Utilization mencapai angka 99% *continuous read*. Diagnosa apa yang terjadi dan bagaimana perbaikan permanennya?
    * *Analisa Solusi:*
      Vektor 15 juta dokumen berdimensi 768 float32 membutuhkan memori graf off-heap sekitar:
      $$15.000.000 \times (768 \times 4 + 128)\text{ bytes} \approx 48\text{ GB RAM}$$
      Dengan alokasi 3 node, masing-masing menyisakan $32 - 16 = 16\text{ GB}$ untuk OS Cache (total cluster OS memory = 48 GB, pas-pasan tanpa menyisakan ruang inverted index dan I/O page swapping). Terjadi **Page Cache Thrashing**: node membaca ulang segmen graf HNSW dari disk secara terus-menerus karena data tergeser dari RAM.
      *Solusi Permanen:* Aktifkan `int8_hnsw` (Scalar Quantization) untuk memangkas ukuran data graf menjadi $\approx 15\text{ GB}$ (atau tambahkan RAM fisik host ke 64 GB per node).

12. **Skenario Kasus B:**
    Tim machine learning memodifikasi mapping field `vector_field` dengan mengubah parameter `m: 16` menjadi `m: 64` untuk meningkatkan recall. Setelah perubahan diterapkan via PUT mapping pada indeks yang sudah berjalan, tidak ada perubahan performa indexing maupun peningkatan skor recall sama sekali. Mengapa hal ini terjadi?
    * *Analisa Solusi:*
      Parameter internal HNSW (`m` dan `ef_construction`) bersifat *immutable* untuk segment yang sudah tertulis di disk. Mengubah parameter tersebut pada mapping index yang sudah ada tidak akan merekonstruksi segment lama secara otomatis. Pengaturan baru hanya akan berlaku pada segment-segment yang dibentuk setelah modifikasi terjadi.
      *Solusi Permanen:* Jalankan API `_reindex` ke index baru dengan mapping yang sudah diperbarui, atau eksekusi `_forcemerge` penuh untuk memaksa pembentukan ulang graf dari keseluruhan segment.

13. **Skenario Kasus C:**
    Sebuah aplikasi marketplace menggunakan model kueri gabungan:
    `{ "query": { "match": { "tags": "sale" } }, "knn": { "field": "vec", "query_vector": [...] } }`
    Pengguna mengeluh bahwa skor pencarian sering kali didominasi secara liar oleh dokumen yang memiliki skor TF-IDF ekstrem pada pencocokan teks, menenggelamkan relevansi kesamaan vektor semantik. Bagaimana Anda merestrukturisasi kueri tersebut di tingkat produksi untuk normalisasi yang deterministik?
    * *Analisa Solusi:*
      Pendekatan query di atas menjumlahkan skor mentah BM25 (skala unbounded, $[0, \infty)$) dengan skor kemiripan vektor (skala bounded, misal Cosine $[0, 1]$). Normalisasi linear manual tidak deterministik lintas shard.
      *Solusi Permanen:* Restrukturisasi kueri menggunakan **Reciprocal Rank Fusion (RRF)** via `retrievers` block API di Elasticsearch. RRF membuang skor metrik mentah dan murni mengombinasikan urutan posisi ordinal rank ($1/ (k + \text{rank})$), memastikan kontribusi peringkat yang seimbang dan bebas bias magnitudo skor BM25.

---

### 16. Summary

Implementasi penelusuran vektor tingkat lanjut (*Dense Vector Search*) pada Apache Lucene dan Elasticsearch memerlukan pemahaman mendalam melampaui paradigma tradisional inverted index:

1. **Efisiensi Memori Graf:** Struktur data HNSW hidup di memori *Off-Heap (Native Memory)* yang dipetakan melalui panggilan sistem kernel OS (`mmap`). Mengatur ukuran Java Heap JVM secara konservatif (maksimal 50% dari total RAM, tidak melampaui 31 GB) adalah syarat mutlak guna menyediakan ruang yang memadai bagi OS Page Cache untuk menahan graf vektor di RAM.
2. **Kuantisasi Vektor (Scalar Quantization):** Penggunaan format `int8_hnsw` merupakan standar industri enterprise untuk menekan memory footprint sebesar 75% dengan dampak penurunan akurasi recall yang hampir dapat diabaikan ($\le 1-2\%$).
3. **Retrieval Hibrida Deterministik:** Mengandalkan skor gabungan manual antara BM25 dan Cosine menyebabkan anomali relevansi. Standar pencarian modern mengadopsi Reciprocal Rank Fusion (RRF) yang mengevaluasi performa sistem multi-retriever berdasarkan konsensus ordinal peringkat.
4. **Isolasi Beban Kerja (Topology):** Komputasi inferensi model transformer harus dipisahkan ke Dedicated ML Nodes guna melindungi Data Nodes yang bertugas mengelola traversal segment Lucene, mempertahankan latensi query p99 tetap berada di rentang sub-30 milidetik.