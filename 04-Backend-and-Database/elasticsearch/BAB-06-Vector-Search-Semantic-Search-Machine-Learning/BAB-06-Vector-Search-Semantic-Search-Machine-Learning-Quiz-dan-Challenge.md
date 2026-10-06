# BAB-06-Vector-Search-Semantic-Search-Machine-Learning: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi mandiri, verifikasi pemahaman konseptual, dan latihan implementasi praktis terkait pencarian vektor (*dense vector search*), pencarian semantik (*semantic search*), integrasi model *Machine Learning* (NLP/E5/ELSER), serta teknik *Hybrid Search* dengan *Reciprocal Rank Fusion* (RRF) pada Elasticsearch.

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1.1: Dense Vector vs Sparse Vector
**Pertanyaan:**  
Jelaskan perbedaan mendasar antara *dense vector* dan *sparse vector* dalam konteks representasi teks di Elasticsearch. Berikan contoh kasus penggunaan untuk masing-masing tipe vector tersebut.

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
- **Dense Vector:** Representasi numerik terkompresi di mana sebagian besar elemen dalam vektor memiliki nilai tidak nol (*non-zero values*). Dimensi vektor bersifat tetap (*fixed dimensions*, misal 384, 768, atau 1536) yang dihasilkan oleh model Transformer (misal BERT, RoBERTa, OpenAI embeddings). Setiap dimensi mewakili konsep semantik abstrak dalam ruang laten.
  - *Use Case:* Pencarian kemiripan makna lintas kosakata (*semantic search*), deteksi parafrase, pencarian gambar berbasis teks (*multimodal search*).
- **Sparse Vector:** Representasi numerik berdimensi sangat besar (seringkali sebesar ukuran *vocabulary*, puluhan ribu hingga ratusan ribu dimensi), di mana hampir seluruh elemen bernilai nol kecuali beberapa token yang ada pada dokumen/kueri. Contoh model: BM25 (token frequencies) atau learned sparse representation seperti SPLADE dan ELSER.
  - *Use Case:* Pencarian kata kunci presisi dengan pemahaman semantik terarah (*lexical-semantic hybrid*), penanganan *out-of-vocabulary* (OOV) terms, kode produk atau ID khusus.
</details>

---

### Soal 1.2: Algoritma HNSW dan Parameter `m` serta `ef_construction`
**Pertanyaan:**  
Elasticsearch menggunakan struktur graf *Hierarchical Navigable Small World* (HNSW) untuk indexing k-Nearest Neighbors (*approximate kNN*). Apa fungsi dari parameter `m` dan `ef_construction` pada konfigurasi field `dense_vector`?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
- **`m` (Number of bidirectional links):** Menentukan jumlah koneksi maksimum per node pada graf HNSW. Rentang tipikal bernilai 4 hingga 64 (default umumnya 16).
  - Nilai `m` lebih tinggi meningkatkan recall kNN pada dataset yang kompleks, namun meningkatkan ukuran memori graf (RAM) serta memperlambat durasi pengindeksan.
- **`ef_construction` (Size of dynamic candidate list):** Menentukan kedalaman pencarian kandidat tetangga terdekat saat node baru dimasukkan ke dalam graf pada fase indexing. Default umumnya 100.
  - Nilai `ef_construction` lebih tinggi menghasilkan struktur graf yang lebih optimal (meningkatkan kualitas/akurasi saat pencarian), namun membutuhkan *indexing time* dan CPU yang lebih besar saat proses ingest dokumen.
</details>

---

### Soal 1.3: Metrik Kesamaan Jarak Vektor (*Similarity Metrics*)
**Pertanyaan:**  
Sebutkan tiga jenis *similarity metric* yang didukung pada field `dense_vector` di Elasticsearch (`l2_norm`, `dot_product`, `cosine`), serta kapan Anda wajib menormalisasi vektor sebelum melakukan indexing?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
1. **`l2_norm` (Euclidean distance):** Menghitung jarak geometris lurus antar dua titik di ruang Euclidean. Nilai skor Elasticsearch dihitung sebagai `1 / (1 + distance^2)`.
2. **`cosine`:** Mengukur sudut kosinus antara dua vektor tanpa memedulikan panjang magnitudo. Nilai skor `(1 + cosine) / 2`. Elasticsearch melakukan normalisasi vektor secara otomatis saat indexing jika metrik ini dipilih.
3. **`dot_product`:** Menghitung perkalian titik (*inner product*). Menghasilkan performa komputasi paling cepat.
- **Kondisi Wajib Normalisasi:** Parameter `dot_product` **wajib** menggunakan vektor satuan (*unit length* / Euclidean norm = 1.0). Jika model embedding menghasilkan vektor yang belum dinormalisasi L2, Anda harus menormalisasikannya sebelum pengindeksan. Memasukkan vektor non-unit ke field `dot_product` akan memicu pengecualian validasi (*exception*).
</details>

---

### Soal 1.4: Peran Ingest Pipeline dan Inference Processor
**Pertanyaan:**  
Bagaimana arsitektur *Ingest Pipeline* bekerja bersama *Inference Processor* untuk melakukan otomatisasi ekstraksi vektor pada saat dokumen masuk ke Elasticsearch?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
Alur kerja Ingest Pipeline dengan Inference Processor:
1. **Model Deployment:** Model ML (misal HuggingFace transformer atau ELSER) diunggah dan diaktifkan di Elasticsearch via *Eland* atau *ML Trained Model API*. Model dialokasikan ke *ML nodes*.
2. **Pipeline Configuration:** Dibuat Ingest Pipeline yang memuat processor bertipe `inference`. Processor ini merujuk ke `model_id` yang aktif dan memetakan field teks input (misal `content`) ke target field (misal `content_vector`).
3. **Document Ingestion:** Klien mengirimkan dokumen teks biasa ke endpoint index dengan parameter `?pipeline=nama-pipeline`.
4. **Execution:** Node Elasticsearch memproses teks melalui model ML secara lokal atau terdistribusi, menghasilkan array float vektor, menyematkannya ke dalam dokumen, lalu menulis dokumen lengkap ke primary shard.
</details>

---

### Soal 1.5: Konsep Reciprocal Rank Fusion (RRF)
**Pertanyaan:**  
Apa itu *Reciprocal Rank Fusion* (RRF) dan mengapa RRF lebih disukai daripada normalisasi skor linear ketika menggabungkan hasil pencarian BM25 dan kNN vector search?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
- **RRF** adalah algoritma pemeringkatan berbasis peringkat (*rank-based ensemble*) yang menggabungkan daftar hasil terurut dari berbagai metode pengambilan dokumen independen.
- Formula skor RRF untuk dokumen $d$:
  $$RRF(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
  di mana $r_m(d)$ adalah posisi peringkat dokumen $d$ pada query $m$, dan $k$ adalah konstanta perataan (biasanya bernilai 60).
- **Alasan Penggunaan dibanding Normalisasi Skor Linear:**
  - Skor BM25 (skor tak berbatas atas) dan skor kemiripan vektor (berbatas 0..1 atau metrik jarak) memiliki skala distribusi dan magnitudo yang sama sekali berbeda.
  - Normalisasi linear (min-max) rentan terhadap *outlier* dan membutuhkan perhitungan mahal lintas shard.
  - RRF hanya bergantung pada nomor peringkat (*rank order*), sehingga kebal terhadap perbedaan skala distribusi skor mentah dan menghasilkan kombinasi peringkat yang konsisten tanpa kalibrasi skor manual.
</details>

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 2.1: Approximate kNN vs Exact kNN (Script Score)
**Pertanyaan:**  
Jelaskan perbedaan mendasar antara klausa *top-level* `knn` (*approximate kNN* via HNSW) dan query `script_score` dengan fungsi `cosineSimilarity` (*exact kNN* / brute-force). Kapan Anda wajib memilih salah satunya?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
- **Approximate kNN (`knn` clause):**
  - Menggunakan struktur indeks HNSW yang dipertahankan di RAM.
  - Kompleksitas waktu: sub-linear $\mathcal{O}(\log N)$. Sangat cepat untuk dataset jutaan dokumen.
  - Recall: Bersifat aproksimasi (~95-99%), bukan jaminan 100% tetangga absolut terdekat.
- **Exact kNN (`script_score` + `cosineSimilarity`):**
  - Melakukan perbandingan jarak satu per satu secara linear (*brute force scan*) $\mathcal{O}(N)$ pada dokumen yang lolos filter awal.
  - Recall: 100% akurat.
  - Konsumsi resource: Komputasi CPU intensif, lambat untuk dataset besar.
- **Kapan Memilih:**
  - Pilih **Approximate kNN** untuk pencarian umum skala besar (*corpus wide retrieval*) dengan latensi rendah (<50ms).
  - Pilih **Exact kNN** jika pencarian dilakukan setelah filter ketat yang mereduksi ruang pencarian menjadi subset kecil (misal `< 5.000` dokumen terseleksi berdasarkan `tenant_id` atau `user_id`), atau saat akurasi 100% mutlak diperlukan.
</details>

---

### Soal 2.2: Pre-filtering vs Post-filtering pada kNN Search
**Pertanyaan:**  
Dalam implementasi HNSW di Elasticsearch, mengapa parameter `filter` di dalam blok klausa `knn` dikategorikan sebagai *pre-filter*, dan apa perbedaannya secara mekanis dibandingkan jika filter diletakkan di luar blok `knn`?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
- **Pre-filtering (di dalam blok `knn`):**
  - Elasticsearch memanfaatkan bitset dari Lucene index filter sebelum traversal graf kNN dimulai.
  - Penelusuran graf HNSW dibatasi hanya mengevaluasi node-node dokumen yang memenuhi kriteria filter tersebut hingga menemukan $k$ dokumen terdekat yang valid.
  - Menjamin bahwa respons query akan selalu mengembalikan tepat $k$ hasil (selama total dokumen yang cocok dengan filter $\ge k$).
- **Post-filtering (filter di luar blok `knn`, misal via boolean query/post_filter):**
  - Algoritma kNN mengambil $k$ dokumen teratas dari keseluruhan dataset tanpa memedulikan metadata filter.
  - Dokumen non-relevan kemudian dibuang di layer luar.
  - Risiko: Jika dari $k$ kandidat yang diambil hanya ada 1 dokumen yang lolos filter metadata, pengguna hanya menerima 1 dokumen (terjadi fenomena *undersupply of results*).
</details>

---

### Soal 2.3: Kuantisasi Vektor (*Scalar Quantization* / `int8`)
**Pertanyaan:**  
Bagaimana fitur *Scalar Quantization* (SQ / `index_options` bertipe `int8_hnsw`) membantu efisiensi penggunaan RAM pada cluster Elasticsearch berskala multi-juta vektor, dan apa kompensasi (*trade-off*) yang dihadapi?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
- **Mekanisme:** Secara default, setiap elemen float pada dense vector berukuran 4 byte (FP32). Vektor 768 dimensi membutuhkan $\approx 3 \text{ KB}$ per dokumen hanya untuk raw array. Dengan Scalar Quantization (1-byte int8), nilai float 32-bit dipetakan ke dalam interval integer 8-bit (-128 s.d. 127).
- **Keuntungan:**
  - Reduksi ukuran memori RAM dan disk hingga $\approx 75\%$ untuk graf HNSW.
  - Memungkinkan penyimpanan lebih banyak vektor di OS page cache dan heap buffer.
  - Peningkatan *throughput* query per detik (QPS) karena transfer memori lebih hemat.
- **Trade-off:**
  - Terjadi sedikit penurunan presisi metrik jarak (*lossy compression*), yang biasanya menurunkan nilai *recall* sekitar 1% s.d. 2%.
  - Fase re-scoring opsional (*rescore*) dengan full precision diperlukan jika menginginkan peringkat akhir tetap 100% presisi.
</details>

---

### Soal 2.4: Limitasi dan Strategi *Chunking* Dokumen Panjang
**Pertanyaan:**  
Sebagian besar model embedding Transformer (seperti `text-embedding-ada-002` atau model BERT) memiliki batas token maksimum (misal 512 atau 8192 token). Jika sebuah dokumen memiliki panjang 15.000 kata, bagaimana strategi arsitektur data (*chunking*) yang benar di Elasticsearch?

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
Strategi arsitektur data yang direkomendasikan:
1. **Passage/Chunk Splitting:** Dokumen dipecah menjadi beberapa potongan (*chunks/passages*) berukuran 200–500 token dengan *sliding window overlap* (misal 50 token) agar konteks semantik tidak terputus di batas potongan.
2. **Desain Indexing:**
   - **Metode A (Parent-Child atau Nested Document):** Setiap chunk disimpan sebagai inner nested document dengan field vektornya masing-masing. Query kNN dijalankan pada level nested passage, lalu di-aggregate ke parent doc.
   - **Metode B (Dokumen Terdenormalisasi - Recommended):** Setiap chunk disimpan sebagai dokumen Elasticsearch independen dengan metadata parent (`parent_doc_id`, `chunk_index`, `total_chunks`, `text_chunk`, `vector`).
3. **Retrieval & Deduplication:** Pada saat query, kNN dijalankan pada level chunk. Hasil pencarian kemudian dikelompokkan (*collapse* atau *top-hits aggregation*) berdasarkan `parent_doc_id` untuk menghindari duplikasi dokumen induk pada halaman pencarian.
</details>

---

### Soal 2.5: Mengelola Model Machine Learning dengan Eland
**Pertanyaan:**  
Jelaskan alur teknis penggunaan tool resmi `eland_import_hub_model` dalam memuat model dari Hugging Face ke dalam Elasticsearch cluster berlisensi Platinum/Enterprise.

<details>
<summary>Jawaban & Pembahasan</summary>

**Jawaban:**
Alur teknis Eland:
1. **Instalasi:** Menggunakan container Docker `docker run --rm -it elastic/eland` atau package python `pip install eland`.
2. **Koneksi dan Upload:** Menjalankan perintah impor dengan kredensial Elasticsearch yang memiliki hak akses role `machine_learning_admin`:
   ```bash
   eland_import_hub_model \
     --url https://elastic:password@es-cluster:9200 \
     --hub-model-id intfloat/multilingual-e5-base \
     --task-type text_embedding \
     --start
   ```
3. **Proses Internal:**
   - Eland mengunduh arsitektur model dan bobot PyTorch dari Hugging Face.
   - Model dikonversi ke format TorchScript.
   - Model dipecah ke dalam chunk dokumen dan disimpan ke dalam system index ML di Elasticsearch (`.ml-models*`).
4. **Deploy & Scaling:** Parameter `--start` mengirimkan instruksi ke Elasticsearch ML node untuk memuat model ke memori worker thread dan siap melayani permintaan API `_inference`.
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 3.1: Zero-Result Problem pada Sistem Katalog E-Commerce

#### Latar Belakang Masalah
Platform e-commerce *fashion* multinasional memiliki katalog dengan 5 juta SKU produk. Tim produk mendeteksi 18% dari total query pencarian menghasilkan *zero results* (halaman kosong). Contoh query bermasalah:
- Pengguna mencari: *"baju dingin untuk liburan salju"*.
- Data produk di database: *"Thermal Down Jacket Men Puffer Coat Windproof"*.
Pencarian BM25 gagal karena kata *"baju"*, *"dingin"*, *"liburan"*, dan *"salju"* sama sekali tidak terdapat pada judul atau deskripsi produk berbahasa Inggris campuran.

#### Analisis Akar Masalah
Mesin pencari mengandalkan *lexical inverted index* murni. Kurangnya kesamaan token (*lexical mismatch*) menyebabkan dokumen relevan tidak terambil meskipun secara fungsional jaket termal tersebut sangat tepat.

#### Solusi Arsitektur & Query
1. Gunakan model *multilingual text embedding* (seperti `multilingual-e5-base`) untuk mengonversi kueri dan dokumen ke ruang vektor 768 dimensi.
2. Terapkan strategi **Hybrid Search** menggabungkan:
   - Match query pada judul/merek (untuk presisi brand dan model spesifik).
   - kNN vector search pada field `description_vector` (untuk menangkap intensi semantik lintas bahasa).
   - Gabungkan keduanya dengan **Reciprocal Rank Fusion (RRF)**.

#### Implementasi Query Solusi:
```json
POST /ecommerce_catalog/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        {
          "standard": {
            "query": {
              "multi_match": {
                "query": "baju dingin untuk liburan salju",
                "fields": ["title^3", "brand^2", "category", "description"]
              }
            }
          }
        },
        {
          "knn": {
            "field": "product_vector",
            "query_vector_builder": {
              "text_embedding": {
                "model_id": "multilingual-e5-base",
                "model_text": "baju dingin untuk liburan salju"
              }
            },
            "k": 50,
            "num_candidates": 200,
            "filter": {
              "term": {
                "status": "active"
              }
            }
          }
        }
      ],
      "rank_window_size": 50,
      "rank_constant": 60
    }
  }
}
```

---

### Skenario 3.2: Latensi P99 Membengkak dan OOM pada Kluster kNN Multi-Tenant

#### Latar Belakang Masalah
Perusahaan SaaS LegalTech menyimpan 20 juta dokumen hukum dari 500 perusahaan klien (*tenants*) dalam satu index besar `legal_documents`. Setiap dokumen memiliki field dense vector 1536 dimensi (OpenAI embedding).
Ketika traffic mencapai 150 QPS, terjadi lonjakan latensi P99 dari 40ms melonjak menjadi 3.800ms, diiringi peristiwa JVM Out-Of-Memory (OOM) dan *node drop* beruntun.

#### Analisis Akar Masalah
1. **Konsumsi Memori Vektor Mentah:** 20 juta dokumen $\times$ 1536 dimensi $\times$ 4 byte $\approx 122 \text{ GB}$ data murni di luar overhead graf HNSW. Memori HNSW meluap melampaui off-heap RAM yang tersedia, memaksa sistem melakukan swaping disk yang lambat.
2. **Kueri kNN Global:** Kueri kNN dijalankan tanpa *pre-filter* `tenant_id` pada level graf Lucene, sehingga penelusuran HNSW menjelajahi seluruh 20 juta dokumen di seluruh node padahal pengguna hanya memiliki hak akses pada $\pm 40.000$ dokumen milik perusahaannya sendiri.

#### Solusi Arsitektur
1. **Scalar Quantization:** Aktifkan kompresi `int8_hnsw` pada mapping `dense_vector` untuk memangkas konsumsi RAM sebesar 75%.
2. **Routing Berbasis Tenant:** Tambahkan custom routing parameter `_routing: tenant_id` agar data masing-masing tenant terkonsentrasi pada shard tertentu, menghindari scatter-gather ke seluruh node cluster.
3. **Mandatory Pre-Filter kNN:** Wajibkan klausa `filter: { "term": { "tenant_id": "XYZ" } }` di dalam blok `knn`. Jika ukuran dokumen tenant $< 10.000$, alihkan dari HNSW ke `exact kNN` (script_score) untuk menghemat RAM cluster.

---

### Skenario 3.3: Degradasi Hasil Search Akibat Keyword Nomor Seri & Kode Produk

#### Latar Belakang Masalah
Sebuah platform penjualan suku cadang mesin otomotif mengganti mesin pencari klasiknya secara penuh (*pure semantic search*) menggunakan dense vector 768 dimensi.
Setelah peluncuran, tingkat komplain pelanggan meroket tajam: ketika teknisi mencari nomor seri baut presisi seperti `"HEX-BOLT-M8-304SS"` atau kode sparepart `"BOSCH-0445120236"`, sistem justru mengembalikan daftar pompa injeksi diesel secara umum atau baut dengan ukuran berbeda (misal M10 atau M6) karena representasi embedding menganggap semua baut/injektor berada dalam klaster semantik yang berdekatan.

#### Analisis Akar Masalah
Dense vector embeddings dilatih untuk menggeneralisasi makna kata, bukan mencocokkan karakter unik atau urutan serial secara deterministik (*lexical exact match*). Model embedding sering kali memetakan token alfanumerik langka ke token `<UNK>` atau menenggelamkan informasi numerik spesifik (8 vs 10).

#### Solusi Arsitektur
1. **Dilarang Menggunakan Pure Semantic untuk E-Commerce Teknikal:** Kembalikan struktur hibrida.
2. **Implementasi Sub-Fields:**
   - Field `part_number`: type `keyword` (exact match) dan `text` dengan `whitespace`/`pattern analyzer`.
   - Field `description`: type `text` (BM25) dan `dense_vector` (Semantic).
3. **Penyusunan Retrieval Pipeline:**
   Gunakan query gabungan di mana match exact terhadap `part_number` diberikan *boost* signifikan melalui BM25/filter, didampingi kNN untuk deskripsi fungsi umum, digabungkan dengan RRF.

---

## Bagian 4: Practical Chapter Challenge (Hands-on)

### Judul Challenge: Membangun Hybrid Search Engine Multi-Kategori dengan RRF dan Dense Vector

#### Objektif
Anda diminta membuat indeks bernama `knowledge_base`, mengonfigurasi mapping dense vector berukuran 384 dimensi dengan HNSW + int8 quantization, melakukan ingest dokumen pengetahuan teknologi, dan mengeksekusi *Hybrid Search* menggunakan *Reciprocal Rank Fusion*.

---

### Langkah 1: Pembuatan Index dan Mapping Khusus
Jalankan pembuatan indeks dengan konfigurasi:
- Field `title`: teks dan keyword.
- Field `category`: keyword (untuk pre-filtering).
- Field `content`: teks biasa.
- Field `content_vector`: `dense_vector` dengan 384 dimensi, metrik `cosine`, HNSW index, dan kompresi `int8_hnsw`.

```json
PUT /knowledge_base
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 1,
    "index": {
      "refresh_interval": "1s"
    }
  },
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword"
          }
        }
      },
      "category": {
        "type": "keyword"
      },
      "content": {
        "type": "text"
      },
      "content_vector": {
        "type": "dense_vector",
        "dims": 384,
        "index": true,
        "similarity": "cosine",
        "index_options": {
          "type": "int8_hnsw",
          "m": 16,
          "ef_construction": 100
        }
      }
    }
  }
}
```

---

### Langkah 2: Ingestion Data Sampel dengan Dummy 384-Dimensional Vectors
*(Catatan: Vektor di bawah ini disederhanakan untuk keperluan uji coba format payload).*

```json
POST /knowledge_base/_bulk
{ "index": { "_id": "doc1" } }
{ "title": "Optimasi Database PostgreSQL", "category": "database", "content": "Tuning vacuum parameter dan shared buffer untuk high concurrency workload.", "content_vector": [0.05, 0.12, -0.08, /* ... 381 float values lainnya ... */ 0.02] }
{ "index": { "_id": "doc2" } }
{ "title": "Elasticsearch Vector Search Architecture", "category": "search", "content": "Implementasi HNSW dan RRF untuk arsitektur pencarian semantik perusahaan.", "content_vector": [0.31, -0.15, 0.42, /* ... 381 float values lainnya ... */ 0.11] }
{ "index": { "_id": "doc3" } }
{ "title": "Dasar Kubernetes Cluster Networking", "category": "devops", "content": "Konfigurasi CNI plugin, CoreDNS, dan Ingress controller pada Kubernetes bare metal.", "content_vector": [-0.22, 0.01, 0.18, /* ... 381 float values lainnya ... */ -0.34] }
```

---

### Langkah 3: Eksekusi Hybrid Search dengan RRF & Pre-Filter Kategori
Tuliskan kueri pencarian yang mencari dokumen dengan kata kunci *"arsitektur pencarian data"* pada kategori `"search"`, menggabungkan BM25 score dan kNN score:

```json
POST /knowledge_base/_search
{
  "retriever": {
    "rrf": {
      "retrievers": [
        {
          "standard": {
            "query": {
              "bool": {
                "must": [
                  {
                    "multi_match": {
                      "query": "arsitektur pencarian data",
                      "fields": ["title^2", "content"]
                    }
                  }
                ],
                "filter": [
                  {
                    "term": { "category": "search" }
                  }
                ]
              }
            }
          }
        },
        {
          "knn": {
            "field": "content_vector",
            "query_vector": [0.28, -0.11, 0.39, /* ... 381 float values ... */ 0.09],
            "k": 10,
            "num_candidates": 50,
            "filter": {
              "term": { "category": "search" }
            }
          }
        }
      ],
      "rank_window_size": 10,
      "rank_constant": 60
    }
  }
}
```

#### Validasi Hasil
1. Periksa bagian header respons: nilai `_score` pada `hits.hits` akan bernilai desimal kecil (misal `0.01639...`) yang merefleksikan hasil formula RRF $\frac{1}{60 + \text{rank}}$.
2. Pastikan dokumen dengan ID `doc2` muncul di posisi teratas (`rank: 1`) karena berhasil mendapatkan skor relevansi tinggi baik dari sisi leksikal BM25 maupun kedekatan kosinus pada kNN.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan daftar periksa berikut untuk mengonfirmasi penguasaan Anda pada materi Bab 06:

- [ ] **Konseptual Embedding:** Saya memahami perbedaan mendasar antara *token-based inverted index* (BM25), *dense embeddings*, dan *learned sparse embeddings* (ELSER).
- [ ] **HNSW Tuning:** Saya memahami fungsi parameter `m`, `ef_construction`, serta parameter runtime `num_candidates` dalam menyeimbangkan recall vs latency.
- [ ] **Alokasi Resource Memori:** Saya mampu menghitung estimasi kebutuhan RAM untuk penyimpanan graf HNSW berdasarkan formula: $\text{Docs} \times \text{Dims} \times 4 \text{ bytes} \times 1.1$.
- [ ] **Vector Quantization:** Saya mampu mengonfigurasi `index_options: { "type": "int8_hnsw" }` untuk menghemat memori hingga 75% di lingkungan produksi.
- [ ] **Filter Optimization:** Saya memahami mengapa filter kategori atau tenant harus selalu diletakkan di dalam blok parameter `knn` (*pre-filtering*) bukan di luar.
- [ ] **Reciprocal Rank Fusion (RRF):** Saya mampu menyusun kueri `retriever` yang menggabungkan hasil pencarian leksikal dan kNN tanpa memerlukan normalisasi skor manual.
- [ ] **Machine Learning Workflow:** Saya mengerti siklus deployment model NLP ke Elasticsearch via Eland dan pemanfaatannya di Ingest Pipeline menggunakan Inference Processor.
- [ ] **Penanganan Kasus Spesifik:** Saya memahami kapan pencarian semantik murni berbahaya (kasus part number / serial code) dan mengapa arsitektur Hybrid Search adalah standar industri terbaik.
