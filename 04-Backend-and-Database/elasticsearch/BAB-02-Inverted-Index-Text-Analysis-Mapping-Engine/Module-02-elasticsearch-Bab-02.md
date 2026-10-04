# Kurikulum Enterprise Elasticsearch: Rekayasa Backend & Basis Data

* **Topik:** Elasticsearch
* **Kategori:** 04-Backend-and-Database
* **Bab 02:** Inverted Index, Text Analysis, & Mapping Engine
* **Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan memiliki kompetensi tingkat lanjut untuk:
1. **Menganalisis dan Membedah Internal Lucene Segments:** Mengidentifikasi representasi biner dari *Inverted Index*, *Term Dictionary*, *Term Index (FST)*, *Posting Lists*, serta *Columnar Store (Doc Values)* pada level file storage sistem.
2. **Merancang Pipeline Text Analysis Kompleks Berbasis Graf:** Mengembangkan analyzer tingkat produksi yang menggabungkan custom char filters, tokenizers, edge n-grams, decompounder, dan `synonym_graph` untuk menangani multi-word query tanpa desinkronisasi *slop/phrase matching*.
3. **Membangun Skema Explicit Mapping Anti-Explosion:** Mengeliminasi risiko *mapping explosion* pada kluster throughput tinggi menggunakan `dynamic: strict`, dynamic templates bersyarat, serta optimasi bitwise field index options (`norms: false`, `index_options: docs`, `doc_values: false`).
4. **Mengevaluasi dan Menyesuaikan Karakteristik I/O & Memory:** Mengatur *Segment Merging*, *TieredMergePolicy*, *Frame of Reference (FoR)*, dan *Roaring Bitmaps* untuk menekan latensi Search P99 di bawah 15ms pada katalog berskala 100+ juta dokumen.

---

## 2. Prerequisite

Peserta pelatihan diwajibkan telah menguasai:
* Fundamental Elasticsearch: Arsitektur Node (Master, Data, Ingest, Coordinating), operasi CRUD via REST API, dan konsep Sharding.
* Sistem Operasi & I/O Storage: Mekanisme Linux OS Page Cache, Virtual Memory, file descriptor, serta perbedaan karakteristik *sequential read/write* vs *random read/write* pada media NVMe.
* Fundamental Teori Basis Data: Struktur data B-Tree, Inverted Index dasar, dan Columnar Storage.
* Pemrograman Representasi Data: Format JSON, pemahaman UTF-8 encoding, serta manipulasi string level byte.

---

## 3. Concept & Internal Architecture

Elasticsearch bertindak sebagai abstraksi terdistribusi di atas Apache Lucene. Untuk memahami perilaku latensi, jejak memori (*memory footprint*), dan throughput penulisan (*indexing throughput*), engineer harus memahami representasi internal segmen Lucene.

```
                    STRUKTUR SEGMEN LUCENE DI DISK & MEMORI
+-------------------------------------------------------------------------------+
| RAM / Linux OS Page Cache                                                     |
|                                                                               |
|  Term Index (.tip)                                                            |
|  [ Finite State Transducer (FST) ] -> Memetakan prefix term ke offset .tim    |
+---------------------------------------|---------------------------------------+
                                        | (Disk Seek ke Block Terkait)
+---------------------------------------v---------------------------------------+
| DISK (Segmen Lucene)                                                          |
|                                                                               |
|  Term Dictionary (.tim)                                                       |
|  +-------------------------------------------------------------------------+  |
|  | Block: "kucing" -> DocFreq: 3, TotalTermFreq: 4, SkipOffset: 0x1A       |  |
|  | Block: "kuda"   -> DocFreq: 1, TotalTermFreq: 1, SkipOffset: 0x2E       |  |
|  +-------------------|-----------------------------------------------------+  |
|                      | (Pointer ke Posting List)                              |
|                      v                                                        |
|  Posting Lists (.doc, .pos, .pay)                                             |
|  +-------------------------------------------------------------------------+  |
|  | .doc (Doc IDs & Freqs via PFOR/FoR):                                    |  |
|  |   DocID Delta: [4, 8, 15] -> Absolut: Doc_4, Doc_12, Doc_27             |  |
|  |   Freqs:       [1, 2,  1]                                               |  |
|  | .pos (Positions via VInt):                                              |  |
|  |   Doc_4: pos [2] | Doc_12: pos [0, 4] | Doc_27: pos [7]                 |  |
|  | .pay (Payloads & Offsets untuk Highlighting):                           |  |
|  |   Start/End Character Offsets                                           |  |
|  +-------------------------------------------------------------------------+  |
|                                                                               |
|  Doc Values (.dvd, .dvm)                                                      |
|  +-------------------------------------------------------------------------+  |
|  | Columnar Storage (Sorted Set / Numeric via Bit-Packing):                |  |
|  |   Doc_0: 199000 | Doc_1: 450000 | Doc_2: 199000 | Doc_4: 120000         |  |
|  +-------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------+
```

### 3.1. Anatomi Segmen Lucene
Segmen adalah unit penyimpanan data *immutable* (tidak dapat diubah) yang ditulis ke disk secara periodik. Sebuah indeks Elasticsearch tersusun atas beberapa shard, dan setiap shard tersusun atas $N$ buah segmen Lucene.

File-file utama penyusun segmen mencakup:
* **`.tip` (Term Index):** Representasi *Finite State Transducer* (FST) yang sangat terkompresi. FST bertindak sebagai indeks bagi *Term Dictionary*. FST dimuat seluruhnya ke dalam *OS Page Cache* atau off-heap memory untuk meminimalisasi I/O disk saat mencari suatu kata.
* **`.tim` (Term Dictionary):** Menyimpan semua term hasil tokenisasi yang diurutkan secara leksikografis dalam format blok (umumnya 25–48 term per blok). Berisi metadata seperti *Document Frequency* ($DF$) dan pointer ke file `.doc`.
* **`.doc` (Frequencies & Skip Lists):** Berisi *Posting List* (daftar Document ID yang mengandung term tersebut) beserta frekuensi kemunculannya. Dikompresi menggunakan algoritma *Frame of Reference* (FoR) untuk delta Document ID.
* **`.pos` (Positions):** Menyimpan informasi posisi setiap term di dalam field dokumen untuk mendukung *phrase queries* (`match_phrase`) dan *proximity queries*.
* **`.pay` (Payloads):** Menyimpan metadata tambahan tingkat token seperti offset karakter (untuk highlighting presisi) dan payloads arbitrer.
* **`.dvd` & `.dvm` (Doc Values Data & Metadata):** Struktur data berorientasi kolom (*column-oriented storage*) yang dioptimalkan untuk pengurutan (*sorting*), agregasi (*aggregations*), dan eksekusi script. Kebalikan dari Inverted Index, Doc Values memetakan `DocID -> Field Value`.
* **`.nvd` & `.nvm` (Norms):** Menyimpan faktor normalisasi panjang field (*field length normalization*) dan *index-time boost* yang dikompresi menjadi representasi 1-byte per dokumen untuk kalkulasi relevansi skor BM25.

### 3.2. Kompresi Posting Lists: Frame of Reference (FoR) & Roaring Bitmaps
Elasticsearch tidak menyimpan DocID secara absolut, melainkan menyimpan selisih antar DocID (*delta encoding* / *d-gaps*). 

Misalkan Posting List absolut: `[10004, 10009, 10015, 10022]`  
Dikonversi menjadi *delta*: `[10004, 5, 6, 7]`

1. **Frame of Reference (FoR):** Digunakan untuk mengompresi blok delta DocID (standar 128 integer per blok). Mesin mencari nilai delta terbesar di dalam blok, menghitung jumlah bit minimum yang dibutuhkan untuk menampung angka tersebut (misal bit terkecil adalah 3 bit untuk angka 7), lalu mengemas seluruh 128 integer tersebut ke dalam bit-stream yang seragam. Ini memungkinkan operasi dekompresi dilakukan secara paralel menggunakan instruksi CPU SIMD.
2. **Roaring Bitmaps:** Digunakan terutama pada caching eksekusi filter (*Node Query Cache*). Bit-vector dipecah menjadi *chunks* berukuran $2^{16}$ (65.536 bit). Jika dalam satu *chunk* terdapat kurang dari 4.096 bit aktif, disimpan sebagai array integer 16-bit (`short[]`). Jika lebih dari 4.096 bit aktif, disimpan sebagai bitset (bitmap klasik). Jika terdapat rentang bit aktif yang masif berurutan, disimpan sebagai *run-length encoding* (RLE).

### 3.3. Siklus Hidup Eksekusi Pipeline Analisis Teks
Text Analysis memproses payload JSON string mentah menjadi sekumpulan *tokens* terstruktur di dalam Inverted Index.

Pipeline ini berjalan melalui tiga fase berurutan:
1. **Character Filters:** Menerima raw string dan memanipulasinya sebelum tokenisasi (misal: strip tag HTML, konversi karakter khusus regex, transliterasi mapping). Mengubah teks, namun mempertahankan kalkulasi *character offsets*.
2. **Tokenizer:** Menerima stream karakter dari Char Filter dan memecahnya menjadi token-token diskrit berdasarkan aturan pembatas (delimiter, whitespace, pola regex, atau n-gram).
3. **Token Filters:** Menerima token stream dari Tokenizer dan memodifikasi token secara berurutan (lowercase, stemming, stop words removal, synonym expansion). Token filter dapat memodifikasi, menambah, atau menghapus token, serta memanipulasi atribut seperti `positionIncrement` dan `positionLength`.

```
                    ALUR PIPELINE EKSEKUSI TEXT ANALYSIS
+---------------------------------------------------------------------------------+
| Input Raw Text: "<b>Sepatu Pria & Wanita</b>"                                  |
+---------------------------------------------------------------------------------+
                                      |
                                      v
| 1. Character Filter: html_strip & mapping ("&" -> "dan")                        |
|    Output: "Sepatu Pria dan Wanita"                                             |
+---------------------------------------------------------------------------------+
                                      |
                                      v
| 2. Tokenizer: standard (whitespace & punctuation boundary)                      |
|    Output Token Stream: ["Sepatu", "Pria", "dan", "Wanita"]                     |
+---------------------------------------------------------------------------------+
                                      |
                                      v
| 3. Token Filters:                                                               |
|    a. lowercase      -> ["sepatu", "pria", "dan", "wanita"]                     |
|    b. stop ("dan")   -> ["sepatu", "pria", (gap), "wanita"]                     |
|    c. synonym_graph  -> ["sepatu", "cowok"/"pria", (gap), "cewek"/"wanita"]     |
+---------------------------------------------------------------------------------+
                                      |
                                      v
| Hasil Akhir Term: [sepatu (pos 1), cowok/pria (pos 2), cewek/wanita (pos 4)]    |
+---------------------------------------------------------------------------------+
```

---

## 4. Why & What

| Pendekatan / Fitur | What (Mekanisme Kerja) | Why (Kapan Harus Dipilih) | Konsekuensi / Risiko Jika Salah Pilih |
| :--- | :--- | :--- | :--- |
| **Inverted Index** | Memetakan kata/term ke ID dokumen tempat kata tersebut muncul. Menggunakan FST + FoR. | Wajib untuk pencarian teks penuh (*full-text search*), fuzzy search, wildcard, dan BM25 relevance matching. | Buruk untuk aggregasi & sorting; akan memicu OOM jika dipaksa via *fielddata*. |
| **Doc Values** | Struktur data columnar tersimpan di disk (OS Page Cache), memetakan DocID ke nilai field. | Digunakan untuk aggregasi (*terms, histogram*), sorting, dan script fields. | Memperbesar ukuran disk per dokumen. Harus dinonaktifkan (`doc_values: false`) jika field tidak pernah disort/diagregasi. |
| **Search-time Synonyms** | Graph Token Filter diterapkan pada fase query (`search_analyzer`), bukan fase index. | Memungkinkan update kamus sinonim secara instan tanpa perlu re-indexing puluhan juta dokumen. | Sedikit menambah latensi kompilasi Lucene Query Parser pada tahap coordinating node. |
| **Dynamic Mapping: Strict** | Menolak (*reject/throw error*) dokumen yang memiliki field baru di luar skema terdaftar. | Skema produksi mission-critical untuk mencegah polusi tipe data dan *cluster mapping explosion*. | Aplikasi produser data akan mengalami write failure jika mengirim payload yang belum di-declare. |
| **Runtime Fields** | Menghitung nilai field saat query dijalankan (*schema on read*) menggunakan engine script Painless. | Eksplorasi log baru tanpa re-index, atau parsing field sekunder dengan frekuensi baca rendah. | Menghabiskan siklus CPU data node; latensi query melonjak signifikan jika dataset membesar. |

---

## 5. How (Workflow Detail)

Alur internal penulisan data dan pembuatan Inverted Index secara end-to-end:

```
[Client] 
   |
   | (1) POST /catalog/_doc/101 (HTTP Payload)
   v
[Coordinating Node]
   |
   | (2) Hash Routing: Murmur3Hash(routing_id) % num_primary_shards
   v
[Data Node: Primary Shard]
   |
   |---> (3) Parsing & Text Analysis Pipeline (Char Filter -> Tokenizer -> Token Filters)
   |---> (4) Tulis ke Translog (.tlog) di disk (jaminan durabilitas/crash recovery)
   |---> (5) Tulis ke Indexing Memory Buffer (JVM Heap)
   |
   +---[ Background Process: REFRESH (default: 1 detik) ]
   |         |
   |         +--> In-memory buffer di-parse menjadi Lucene In-Memory Segment
   |         +--> Segmen baru dibuka ke OS Page Cache (Searchable, belum fsync)
   |
   +---[ Background Process: FLUSH (setiap 30 menit atau Translog > 512MB) ]
   |         |
   |         +--> Lucene Commit: Semua segmen di Page Cache di-fsync permanen ke Storage
   |         +--> Translog lama dipotong (*truncated*)
   |
   +---[ Background Process: TIERED SEGMENT MERGE ]
             |
             +--> Segmen-segmen kecil digabung menjadi segmen besar
             +--> Dokumen bertanda *deleted* (tombstone) dibuang secara fisik
             +--> Doc Values & Inverted Index dihitung ulang dan dipadatkan
```

1. **Routing:** Client mengirim dokumen ke *Coordinating Node*. Node ini menentukan node tujuan menggunakan algoritma routing:
   $$\text{shard\_id} = |\text{Murmur3Hash}(\text{routing\_value})| \pmod{\text{number\_of\_primary\_shards}}$$
2. **Analysis Execution:** Primary Shard memproses field bertipe `text` melalui analyzer yang didefinisikan pada mapping. Menghasilkan *Token Stream* dengan atribut token, frekuensi, posisi, dan payload.
3. **Write to Buffer & Translog:** Dokumen ditulis simultan ke:
   * **Indexing Memory Buffer** (area JVM heap yang dialokasikan oleh setting `indices.memory.index_buffer_size`).
   * **Translog (Transaction Log):** Append-only log di disk untuk mengantisipasi *node crash* sebelum data di-fsync ke segmen Lucene.
4. **Segment Creation via Refresh:**
   * Siklus *refresh* (standar interval 1s, dapat dikonfigurasi) mengonversi isi Indexing Memory Buffer menjadi segmen Lucene baru di OS Page Cache.
   * Pada titik ini, dokumen berstatus **searchable** (dapat ditemukan melalui query), meskipun belum sepenuhnya persisten di disk fisik (*fsync*).
5. **Durability via Flush:**
   * Siklus *flush* mengeksekusi operasi `fsync()` pada semua segmen di OS Page Cache, menulis marker commit ke disk, dan memotong log Translog yang sudah persisten.
6. **Tiered Segment Merge:**
   * Di latar belakang, *TieredMergePolicy* Lucene mendeteksi segmen-segmen kecil dengan tier ukuran setara dan menggabungkannya ke dalam segmen yang lebih besar. Dokumen yang telah di-update atau didelete hanya diberi tanda bendera bit (*tombstone* deletion array) pada segmen aslinya, dan baru benar-benar dieksekusi pembersihan fisiknya saat proses merge ini berlangsung.

---

## 6. Analogy & Diagram ASCII

### Analogi Perpustakaan & Kartu Katalog Index
Bayangkan sebuah perpustakaan raksasa:
* **Pencarian Linear (Full Table Scan):** Pustakawan harus membuka dan membaca setiap lembar halaman dari jutaan buku satu per satu hanya untuk mencari kata "Semikonduktor".
* **Inverted Index:** Di bagian belakang perpustakaan, terdapat lemari kartu indeks alfabetis (*Term Index / FST*). Kartu huruf "S" mengarahkan pustakawan ke laci bertuliskan "Semikonduktor" (*Term Dictionary*). Di dalam laci tersebut, terdapat daftar nomor inventaris buku beserta nomor halamannya (*Posting List*). Pustakawan langsung menuju ke 5 buku spesifik tersebut.
* **Doc Values:** Di dinding perpustakaan terdapat daftar seluruh buku yang diurutkan berdasarkan ID buku, dan di sebelahnya tertulis tahun terbit serta harga buku. Jika pengunjung meminta "Tolong hitung rata-rata harga buku di perpustakaan ini", pustakawan cukup membaca kolom harga pada daftar dinding ini secara berurutan (*Columnar Scan*), tanpa perlu membuka isi buku sama sekali.

### Diagram Representasi Penyimpanan Segmen
```
DOKUMEN INPUT:
Doc 1: "jual laptop rog"
Doc 2: "beli laptop gaming"
Doc 3: "jual mouse gaming rog"

INVERTED INDEX (Disimpan di .tip, .tim, .doc, .pos):
+---------+----------+-----------------------------+
| Term    | Doc Freq | Postings [DocID: [Positions]]|
+---------+----------+-----------------------------+
| beli    |    1     | Doc 2: [1]                  |
| gaming  |    2     | Doc 2: [2], Doc 3: [2]      |
| jual    |    2     | Doc 1: [0], Doc 3: [0]      |
| laptop  |    2     | Doc 1: [1], Doc 2: [1]      |
| mouse   |    1     | Doc 3: [1]                  |
| rog     |    2     | Doc 1: [2], Doc 3: [3]      |
+---------+----------+-----------------------------+

DOC VALUES (Disimpan di .dvd, .dvm untuk field tipe 'keyword' / 'numeric', misal: 'brand'):
+--------+------------------+
| Doc ID | Brand (Columnar) |
+--------+------------------+
| Doc 1  | ASUS             |
| Doc 2  | LENOVO           |
| Doc 3  | ASUS             |
+--------+------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Mapping Dasar dengan Optimasi Resource Level Ekstrem
Mapping untuk data audit log transaksi. Menghilangkan overhead BM25 norms, positioning, dan doc values untuk menghemat storage hingga 60%.

```json
PUT /audit_logs
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "index.mapping.total_fields.limit": 50
  },
  "mappings": {
    "dynamic": "strict",
    "properties": {
      "timestamp": {
        "type": "date"
      },
      "actor_id": {
        "type": "keyword",
        "doc_values": true,
        "norms": false
      },
      "action": {
        "type": "keyword",
        "index": true,
        "norms": false
      },
      "payload_message": {
        "type": "text",
        "index_options": "docs",
        "norms": false
      }
    }
  }
}
```
*Penjelasan optimasi:* `index_options: "docs"` mengabaikan penyimpanan frekuensi term dan posisi kata di file `.pos`, menghemat byte I/O karena log hanya dicari berbasis terminologi eksak tanpa scoring relevansi. `norms: false` memangkas file memory cache panjang field.

### 7.2. Practical Example: Arsitektur E-Commerce Search Engine Kelas Produksi
Implementasi kustom analyzer untuk menangani:
1. Strip karakter non-alfanumerik kotor.
2. Pemrosesan Edge N-Gram untuk autocomplete instan.
3. Multi-field indexing (analisis penuh vs keyword matching).
4. Penanganan sinonim berbasis graf runtime multi-word (`synonym_graph`).
5. Proteksi *dynamic templates*.

```json
PUT /ecommerce_catalog_v1
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "index.refresh_interval": "5s",
    "analysis": {
      "filter": {
        "catalog_synonyms": {
          "type": "synonym_graph",
          "synonyms": [
            "laptop, notebook, portable pc",
            "hp, smartphone, handphone, ponsel",
            "earphone, tws, headset, earbud"
          ]
        },
        "edge_ngram_filter": {
          "type": "edge_ngram",
          "min_gram": 2,
          "max_gram": 15
        },
        "indonesian_stemmer": {
          "type": "stemmer",
          "language": "indonesian"
        }
      },
      "analyzer": {
        "catalog_index_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "char_filter": ["html_strip"],
          "filter": [
            "lowercase",
            "indonesian_stemmer",
            "edge_ngram_filter"
          ]
        },
        "catalog_search_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "char_filter": ["html_strip"],
          "filter": [
            "lowercase",
            "indonesian_stemmer",
            "catalog_synonyms"
          ]
        },
        "catalog_exact_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase"]
        }
      }
    }
  },
  "mappings": {
    "dynamic": "strict",
    "dynamic_templates": [
      {
        "strings_as_keywords_only": {
          "match_mapping_type": "string",
          "match": "*_code",
          "mapping": {
            "type": "keyword",
            "norms": false
          }
        }
      }
    ],
    "properties": {
      "product_id": {
        "type": "keyword"
      },
      "sku": {
        "type": "keyword",
        "norms": false
      },
      "title": {
        "type": "text",
        "analyzer": "catalog_index_analyzer",
        "search_analyzer": "catalog_search_analyzer",
        "fields": {
          "raw": {
            "type": "keyword",
            "ignore_above": 256
          },
          "stemmed": {
            "type": "text",
            "analyzer": "catalog_exact_analyzer"
          }
        }
      },
      "category_path": {
        "type": "keyword"
      },
      "price": {
        "type": "scaled_float",
        "scaling_factor": 100
      },
      "stock": {
        "type": "integer"
      },
      "is_active": {
        "type": "boolean"
      },
      "attributes": {
        "type": "nested",
        "properties": {
          "name": { "type": "keyword" },
          "value": { "type": "keyword" }
        }
      },
      "created_at": {
        "type": "date"
      }
    }
  }
}
```

---

## 8. Real World Case Study: E-Commerce Marketplace Scale

### Konteks Skenario
Sebuah platform marketplace multi-kategori di Asia Tenggara memiliki:
* **Volume Data:** 65 juta dokumen SKU aktif.
* **Trafik:** 18.000 Search QPS (Queries Per Second) saat *Peak Flash Sale*.
* **Write Ingestion:** Rata-rata 4.500 document update/detik (fluktuasi inventaris & harga real-time).

### Masalah Produksi Teridentifikasi
1. **Cluster Instability & Crash OOM (Out Of Memory):** Node data secara berkala mengalami JVM Garbage Collection pauses hingga 20 detik, disusul keluarnya *OutOfMemoryError*.
2. **Disk Usage Bloat:** Kapasitas disk habis secara tidak wajar pada cluster berukuran 12 TB.
3. **P99 Search Latency Spike:** Latensi melonjak dari normal 35ms menjadi 3.200ms.

### Investigasi Root Cause
1. **Mapping Explosion:** Penggunaan `dynamic: true` pada atribut merchant menyebabkan terbentuknya lebih dari 14.000 dynamic field unik (`attributes.warna_baju`, `attributes.warna_sepatu`, dst.) di dalam cluster cluster-state Lucene.
2. **Abuse Fielddata pada Analisis Teks:** Tim frontend mengeksekusi aggregasi pada field `text` (`title`) untuk menampilkan filter produk, memicu Elasticsearch mengalokasikan ratusan gigabyte heap memory untuk membangun in-memory fielddata structure.
3. **Index-Time Synonym Bloat:** Kamus sinonim multi-word diterapkan pada fase *indexing*. Setiap kata bertransformasi menjadi puluhan variasi n-gram dan sinonim, melipatgandakan ukuran Posting List segmen Lucene sebesar 400%.

### Solusi Arsitektural dan Hasil Implementasi

```
SEBELUM OPTIMASI:
Client Update ---> Ingest -> Dynamic Mapping (14.000 fields) ---> Segmen Lucene Bengkak
Client Query  ---> Agregasi pada 'text' field (Heap Fielddata OOM) ---> Latensi P99 > 3200ms

SETELAH OPTIMASI:
Client Update ---> Ingest -> Dynamic: Strict + Nested Key-Value
                                   |
                                   v
                             Segmen Terkompresi (Doc Values Aktif, Norms Terpilih)
Client Query  ---> Search-Time Synonyms (Graph) + Agregasi pada 'keyword' (Doc Values Off-Heap)
                   ---> Latensi P99: 12ms | Zero Heap Choke
```

1. **Restrukturisasi Skema ke Model Flat/Nested Key-Value:**
   Atribut dinamis dimigrasikan dari dynamic key menjadi struktur formal berulang:
   ```json
   "attributes": [
     {"name": "color", "value": "black"},
     {"name": "size", "value": "XL"}
   ]
   ```
2. **Pemisahan Index Analyzer vs Search Analyzer:**
   Kamus sinonim diisolasi secara eksklusif ke dalam `search_analyzer` dengan token filter `synonym_graph`. Ukuran Inverted Index disk seketika tereduksi sebesar 62%.
3. **Hard Disabling Fielddata & Norms:**
   Mengunci mapping secara ketat. Mematikan `fielddata` pada seluruh field `text`. Agregasi diarahkan mutlak ke sub-field berorientasi columnar (`title.raw` yang bertipe `keyword` dengan *Doc Values* tersimpan rapi pada OS Page Cache off-heap).
4. **Hasil Kuantitatif Pasca Rilis:**
   * **JVM Heap Usage Rata-Rata:** Turun drastis dari 92% menjadi stabil di 45-55%.
   * **P99 Search Latency:** Terpangkas dari 3.200ms ke 12ms konstan pada 18.000 QPS.
   * **Kapasitas Disk:** Menghemat 7,4 TB storage di seluruh kluster.

---

## 9. Trade-offs Architecture Matrix

| Strategi / Pilihan | Metrik Latensi Baca | Throughput Penulisan | Jejak Disk Storage | Konsumsi RAM / Cache |
| :--- | :--- | :--- | :--- | :--- |
| **Edge N-Gram (Index Time)** | Sangat Rendah (1-5ms untuk prefix queries) | Rendah (Penulisan lambat karena token berlipat ganda) | Sangat Tinggi (Posting lists membesar signifikan) | Moderat (Ukuran FST membesar di RAM) |
| **Prefix / Wildcard Query (Tanpa N-Gram)** | Ekstrem Lambat (Scan FST leksikografis besar) | Sangat Tinggi (Hanya 1 token terindeks per kata) | Minimal (Ukuran index dasar) | Rendah saat indexing, Tinggi saat query berjalan |
| **Multi-field (Text + Keyword)** | Sangat Fleksibel (Search relevan + aggregasi cepat) | Sedang (Dua struktur data dibangun bersamaan) | Tinggi (~1.8x - 2.5x lipat per field) | Seimbang (Inverted index + Doc values di page cache) |
| **Disabling Norms (`norms: false`)** | Identik (Tidak mempengaruhi lookup speed) | Sedikit Lebih Tinggi | Menghemat 1 byte per doc per field | MenghilangkanNorms Cache dari memory |
| **Disabling Doc Values (`doc_values: false`)** | Lambat jika diagregasi (Gagal kecuali via fielddata) | Tinggi (Mengeliminasi I/O columnar) | Reduksi disk drastis (Bisa hemat 20-40%) | Menghilangkan pembacaan file `.dvd` ke Page Cache |
| **Runtime Fields (Schema-on-read)** | Sangat Tinggi/Lambat (CPU script execution loop) | Maksimal (Nol overhead I/O saat indexing) | Nol overhead storage fisik | Membebani Heap CPU saat runtime execution |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Mapping Explosion Melalui Key JSON Dinamis
* **Gejala:** Coordinating node lambat mendistribusikan metadata. Log cluster menampilkan `Cluster state size is too large` atau node tiba-tiba drop dari cluster.
* **Akar Masalah:** Log/dokumen memasukkan objek JSON dinamis, seperti ID user atau UUID dijadikan key: `{"user_clicks": {"1029384": 1}}`. Setiap key unik didaftarkan ke mapping global cluster state Lucene.
* **Deteksi:**
  ```bash
  GET /_cat/indices?v&s=pri.store.size:desc
  GET /nama_index/_mapping
  ```
  Hitung jumlah field melalui:
  ```bash
  curl -s -X GET "localhost:9200/nama_index/_mapping" | jq '.. | .properties? | objects | keys | length'
  ```
* **Solusi Perbaikan:** Pasang limit pengaman ketat dan terapkan `dynamic: strict`:
  ```json
  PUT /nama_index/_settings
  {
    "index.mapping.total_fields.limit": 1000
  }
  ```

### Mistake 2: Penggunaan Token Filter `synonym` Standar pada Multi-Word di Tahap Index
* **Gejala:** Query `match_phrase` menghasilkan dokumen yang tidak relevan atau token position mismatch.
* **Akar Masalah:** Token filter `synonym` standar tidak memanipulasi rentang posisi token (`positionLength`) dengan benar pada term multi-kata (seperti "air conditioner" -> "ac"). Ini menyebabkan frase tumpang tindih secara destruktif di dalam Inverted Index.
* **Solusi Perbaikan:** Gunakan token filter `synonym_graph` dan **hanya** terapkan di `search_analyzer`, bukan di `analyzer` index-time.

### Mistake 3: Heap Crash karena Fielddata Diaktifkan pada Field `text`
* **Gejala:** Log Elasticsearch menampilkan:
  `CircuitBreakingException: [parent] Data too large, data for [<fielddata>] would be [...]`
* **Akar Masalah:** Seseorang menjalankan query aggregasi atau sorting pada field tipe `text`. Karena `text` tidak memiliki Doc Values, sistem memuat semua uncompressed postings list ke dalam JVM Heap memory via *fielddata cache*.
* **Solusi Perbaikan:** Matikan izin fielddata pada mapping, gunakan multi-field sub-type `keyword`:
  ```json
  PUT /nama_index/_mapping
  {
    "properties": {
      "product_name": {
        "type": "text",
        "fielddata": false,
        "fields": {
          "keyword": {
            "type": "keyword"
          }
        }
      }
    }
  }
  ```

---

## 11. Best Practices (Production Checklist)

### 11.1. Konfigurasi Mapping & Analisis
- [ ] Ubah secara global `"dynamic": "strict"` di seluruh mapping index produksi. Tidak ada field tak terdefinisi yang boleh lolos.
- [ ] Tentukan `ignore_above: 256` (atau nilai lebih rendah) pada semua tipe data `keyword` agar string payload raksasa (misal: token JWT atau error trace) tidak masuk ke Term Dictionary FST.
- [ ] Nonaktifkan `norms` (`"norms": false`) pada semua field text yang tidak memerlukan relevansi kalkulasi BM25 (misalnya string kategori, SKU, identifier status).
- [ ] Atur `"index_options": "docs"` untuk field text log/deskripsi yang hanya dicari menggunakan exact match term tanpa operator frasa (`match_phrase`).
- [ ] Jangan pernah gunakan `synonym` pada Index-Time Analyzer. Gunakan `synonym_graph` pada `search_analyzer`.

### 11.2. Optimasi Throughput Penulisan (Indexing Throughput)
- [ ] Ubah interval refresh: `"index.refresh_interval": "30s"` atau `"60s"` untuk index ingestion masif (mengurangi pembentukan segmen-segmen mini).
- [ ] Atur durabilitas translog untuk non-financial ingestion: `"index.translog.durability": "async"` dengan `"index.translog.sync_interval": "10s"`.
- [ ] Alokasikan JVM Heap Memory minimal $10\%$ untuk indexing buffer:
  `indices.memory.index_buffer_size: 15%` di file konfigurasi `elasticsearch.yml`.
- [ ] Jalankan Force Merge (`_forcemerge?max_num_segments=1`) secara berkala hanya untuk index read-only/historical time-series agar Doc Values dan Inverted Index terkonsolidasi sempurna dan tombstone doc terhapus.

---

## 12. Hands-on Practice

Buat direktori baru untuk modul ini:
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

### Langkah 1: Eksperimen Token Stream Internal Lucene
Simulasikan bagaimana analyzer memanipulasi token stream secara mendalam menggunakan API `_analyze`.

Simpan file `01_test_analyzers.sh`:
```bash
#!/usr/bin/env bash

ES_HOST="http://localhost:9200"

echo "=== MENGUJI TOKEN GENERATION DENGAN STANDAR ANALYZER ==="
curl -s -X POST "$ES_HOST/_analyze" -H "Content-Type: application/json" -d'
{
  "tokenizer": "standard",
  "text": "Pemberian Makan Bergizi Gratis 2024!"
}' | jq .

echo "=== MENGUJI INDONESIAN STEMMER DENGAN POSITION ATTRIBUTES ==="
curl -s -X POST "$ES_HOST/_analyze" -H "Content-Type: application/json" -d'
{
  "tokenizer": "standard",
  "filter": ["lowercase", "indonesian_stemmer"],
  "text": "Pemberian makanan yang termurah"
}' | jq .
```
Jalankan file:
```bash
chmod +x 01_test_analyzers.sh
./01_test_analyzers.sh
```

### Langkah 2: Mengonfigurasi Index Produksi Lengkap
Simpan file `02_create_production_index.sh`:
```bash
#!/usr/bin/env bash

ES_HOST="http://localhost:9200"
INDEX_NAME="enterprise_catalog"

# Hapus index lama jika ada
curl -s -X DELETE "$ES_HOST/$INDEX_NAME" > /dev/null

echo "=== MEMBUAT INDEX DENGAN ADVANCED MAPPING & ANALYZER ==="
curl -s -X PUT "$ES_HOST/$INDEX_NAME" -H "Content-Type: application/json" -d'
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 0,
    "index.refresh_interval": "1s",
    "analysis": {
      "filter": {
        "tech_synonyms": {
          "type": "synonym_graph",
          "synonyms": [
            "ps5, playstation 5, sony playstation 5",
            "vga, kartu grafis, graphic card"
          ]
        },
        "edge_ngram_custom": {
          "type": "edge_ngram",
          "min_gram": 2,
          "max_gram": 10
        }
      },
      "analyzer": {
        "index_search_autocomplete": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "edge_ngram_custom"]
        },
        "query_synonym_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "tech_synonyms"]
        }
      }
    }
  },
  "mappings": {
    "dynamic": "strict",
    "properties": {
      "sku": {
        "type": "keyword",
        "norms": false
      },
      "name": {
        "type": "text",
        "analyzer": "index_search_autocomplete",
        "search_analyzer": "standard",
        "fields": {
          "synonymized": {
            "type": "text",
            "analyzer": "standard",
            "search_analyzer": "query_synonym_analyzer"
          },
          "raw": {
            "type": "keyword"
          }
        }
      },
      "price": {
        "type": "long",
        "doc_values": true
      },
      "tags": {
        "type": "keyword",
        "norms": false
      }
    }
  }
}' | jq .
```
Jalankan file:
```bash
chmod +x 02_create_production_index.sh
./02_create_production_index.sh
```

### Langkah 3: Ingest Data Uji dan Uji Segmen
Simpan file `03_test_queries.sh`:
```bash
#!/usr/bin/env bash

ES_HOST="http://localhost:9200"
INDEX_NAME="enterprise_catalog"

echo "=== MENGISI DATA PRODUK ==="
curl -s -X POST "$ES_HOST/$INDEX_NAME/_bulk?refresh=true" -H "Content-Type: application/x-ndjson" -d'
{"index":{"_id":"1"}}
{"sku":"SKU-001","name":"Sony PlayStation 5 Disc Edition","price":8500000,"tags":["gaming","console"]}
{"index":{"_id":"2"}}
{"sku":"SKU-002","name":"Kartu Grafis Nvidia RTX 4090","price":32000000,"tags":["hardware","pc"]}
{"index":{"_id":"3"}}
{"sku":"SKU-003","name":"Nintendo Switch OLED","price":4200000,"tags":["gaming","portable"]}
' | jq '{errors: .errors, took: .took}'

echo "=== TEST 1: MATCH EDGE N-GRAM AUTOCOMPLETE (Input: 'nvi') ==="
curl -s -X POST "$ES_HOST/$INDEX_NAME/_search" -H "Content-Type: application/json" -d'
{
  "query": {
    "match": {
      "name": "nvi"
    }
  }
}' | jq '.hits.hits[] | {_id, score: ._score, name: ._source.name}'

echo "=== TEST 2: MATCH SYNONYM GRAPH (Input: 'ps5' mencari 'PlayStation 5') ==="
curl -s -X POST "$ES_HOST/$INDEX_NAME/_search" -H "Content-Type: application/json" -d'
{
  "query": {
    "match": {
      "name.synonymized": {
        "query": "ps5",
        "auto_generate_synonyms_phrase_query": true
      }
    }
  }
}' | jq '.hits.hits[] | {_id, score: ._score, name: ._source.name}'
```
Jalankan file:
```bash
chmod +x 03_test_queries.sh
./03_test_queries.sh
```

---

## 13. Exercise

### Level Easy
1. **Inspeksi Mapping dan Segment Memory:**
   Gunakan Elasticsearch Cat API untuk memeriksa alokasi memory segmen pada index `enterprise_catalog`. Identifikasi file segmen mana yang memakan heap memory dan off-heap page cache paling besar.
   *Ekspektasi Output:* Tampilkan metrik `segments.count`, `segments.memory`, `terms.memory`, dan `stored_fields.memory`.

### Level Medium
2. **Kustomisasi Decompounder Tokenizer:**
   Di negara dengan bahasa majemuk seperti Jerman atau istilah teknis kedokteran/IT (misalnya: *databaseadministrator* atau *antivirussoftware*), Inverted Index standar gagal mencocokkan kata dasar.
   *Tugas:* Buat mapping analyzer baru menggunakan `hyphenation_decompounder` atau `dictionary_decompounder` dengan kamus kata dasar `["data", "base", "admin", "software"]`. Pastikan input `"databaseadmin"` dapat dicari secara independen menggunakan term `"data"` maupun `"admin"`.

### Level Hard
3. **Painless Inverted-Index Script Reconstruction:**
   Tulis kueri Search menggunakan script Painless yang mengeksekusi inspeksi langsung ke struktur tingkat rendah Lucene via Java class `DocValues` vs Inverted Index Term Frequency API (`_index['field'].get('term')`).
   *Tugas:* Hitung skor relevansi khusus secara on-the-fly yang membagi Term Frequency suatu kata di dalam dokumen dengan nilai absolut kolom numeric `price`. Buktikan bahwa script tersebut tidak memicu alokasi fielddata heap.

---

## 14. Challenge

### Arsitektur Zero-Downtime Re-indexing pada Katalog Legal Multi-Tenant
Sebuah platform manajemen dokumen hukum (*LegalTech*) memproses 120 juta pasal perundang-undangan dan putusan pengadilan. Karakteristik sistem meliputi:
* Setiap tenant memiliki daftar terminologi *jargon hukum* privat yang tidak boleh tercampur antar tenant.
* Sistem saat ini menggunakan analyzer statis tanpa tokenisasi posisi yang tepat, sehingga *phrase query* tingkat lanjut (`"tindak pidana pencucian uang"~2`) sering mengembalikan zero-hits atau false-positive.
* SLA operasi: Zero downtime indexing, zero data loss, dan P99 search latency wajib berada di bawah 25ms.

**Rancang arsitektur menyeluruh:**
1. Desain skema mapping final (termasuk pemilihan analyzer, char_filter, token_filter, index_options, serta struktur multi-tenant identifier).
2. Tentukan strategi penerapan sinonim dinamis per-tenant tanpa melakukan re-index global seluruh cluster.
3. Rancang strategi migrasi data dari skema lama ke skema baru (*Blue/Green Index Aliasing*) dengan meminimalkan beban I/O agar kluster live tidak mengalami degradasi performa selama proses re-indexing berlangsung.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Di manakah Finite State Transducer (FST / `.tip`) disimpan dan apa peran utamanya?**
   * *Jawaban:* FST disimpan di level RAM/OS Page Cache (off-heap memory). Peran utamanya adalah sebagai indeks penunjuk (*term index*) di memori untuk melacak blok lokasi term yang tepat di dalam file disk *Term Dictionary* (`.tim`) tanpa perlu membaca seluruh disk dictionary secara sequential.
2. **Apa dampak langsung terhadap fungsionalitas pencarian jika field text dikonfigurasi dengan `"index_options": "docs"`?**
   * *Jawaban:* Field tersebut hanya menyimpan referensi Document ID. Akibatnya, frekuensi kemunculan term ($TF$) diabaikan (kalkulasi relevansi BM25 menjadi flat/tidak presisi), dan query pencarian frasa bertingkat (`match_phrase`, span queries, phrase slop) tidak dapat berfungsi karena informasi posisi token diabaikan.
3. **Mengapa `doc_values` secara default diaktifkan pada tipe data numeric dan keyword, tetapi dinonaktifkan secara permanen pada tipe data `text`?**
   * *Jawaban:* Karena Doc Values adalah struktur data berbasis kolom yang didesain untuk pengurutan dan agregasi data diskrit/atomik. Teks bebas (*analyzed text*) menghasilkan banyak token per dokumen yang membuat arsitektur columnar biasa tidak efisien; pencarian teks membutuhkan Inverted Index, bukan Columnar Store.
4. **Apa fungsi dari file segmen `.nvd` / `.nvm` (Norms)?**
   * *Jawaban:* Menyimpan faktor normalisasi panjang dokumen (*field length normalization*). Memastikan bahwa kemunculan sebuah kata di dalam dokumen yang sangat pendek bernilai skor relevansi lebih tinggi dibandingkan kemunculan kata yang sama di dalam dokumen yang berisi ribuan kata.
5. **Kapan sebuah dokumen yang di-delete benar-benar dihapus secara fisik dari media storage disk?**
   * *Jawaban:* Dokumen yang dihapus awalnya hanya diberi tanda penanda (*bit tombstone deletion array*). Dokumen tersebut baru benar-benar dimusnahkan secara fisik dari blok storage ketika proses *Tiered Segment Merging* terjadi di latar belakang.

### Bagian 2: Intermediate (5 Pertanyaan)
6. **Jelaskan perbedaan mendasar antara kompresi posting lists menggunakan *Frame of Reference (FoR)* dan *Roaring Bitmaps*!**
   * *Jawaban:* FoR digunakan untuk memadatkan daftar delta Doc ID integer secara terurut dalam blok konstan (biasanya 128 integer) dengan teknik bit-packing seragam terindeks SIMD. Sementara Roaring Bitmaps memecah set data ke dalam bucket 16-bit dan dinamis memilih antara array short, bitset klasik, atau Run-Length Encoding tergantung pada kerapatan (*density*) data. Roaring Bitmaps utamanya digunakan pada *filter bitset caching*.
7. **Mengapa penerapan token filter `synonym` standar pada saat indexing (*index-time*) sangat tidak dianjurkan untuk sistem produksi?**
   * *Jawaban:* Karena tiga alasan utama: (1) Setiap pembaruan kamus sinonim mewajibkan re-indexing seluruh data dari nol, (2) Ukuran Inverted Index membengkak drastis karena replikasi term, (3) Statistik BM25 DocFreq menjadi bias dan menghasilkan skoring relevansi yang terdistorsi.
8. **Bagaimana cara kerja token filter `synonym_graph` memecahkan masalah multi-word synonyms dibanding `synonym` biasa?**
   * *Jawaban:* `synonym_graph` membangun struktur token stream berbasis *Directed Acyclic Graph* (DAG). Token multi-kata diberikan nilai atribut `positionLength` $> 1$. Hal ini menjaga kesinambungan posisi token alternatif sehingga query frasa berurutan (`match_phrase`) tidak pecah atau tumpang tindih dengan urutan kata berikutnya.
9. **Apa perbedaan perilaku pencarian antara analyzer yang menggunakan `edge_ngram` dengan query berbasis wildcard `prefix` (misal: `"query*"` )?**
   * *Jawaban:* `edge_ngram` melakukan pre-computing token prefix pada saat ingestion ke dalam Inverted Index, sehingga eksekusi baca beroperasi via binary lookup biasa yang sangat cepat ($O(1)$ disk/memory seek). Sedangkan wildcard `prefix` melakukan scan dinamis terhadap Term Dictionary di dalam FST yang lambat dan memakan siklus CPU signifikan jika jumlah term unik masif.
10. **Apa yang terjadi pada memori ketika parameter `indices.fielddata.cache.size` terlampaui saat eksekusi query berlangsung?**
    * *Jawaban:* Elasticsearch akan mengeksekusi eviksi data fielddata tertua dari JVM Heap, yang memicu lonjakan degradasi CPU dan disk I/O. Jika batas sirkuit pelindung (*Circuit Breaker*) tercapai sebelum alokasi rampung, Elasticsearch membatalkan eksekusi kueri dan melempar *CircuitBreakingException* agar node tidak mati karena JVM OutOfMemoryError.

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan Analitis)
11. **Skenario A:** Sebuah cluster Elasticsearch mengalami lonjakan latensi penulisan (*indexing latency*) yang ekstrem. Setelah dicek, utilitas disk I/O mencapai 100% dan ditemukan ribuan segmen berukuran di bawah 1 MB pada shard. Pengaturan apa yang salah dan bagaimana cara memperbaikinya tanpa menambah kapasitas hardware?
    * *Analisis & Solusi:* Akar masalahnya adalah interval refresh yang terlalu agresif (misal: refresh bawaan 1 detik, atau aplikasi pemanggil memanggil explicit `?refresh=true` pada setiap request API). Setiap refresh memaksa Index Memory Buffer dikonversi menjadi segmen fisik di disk, memicu badai I/O merge. Solusi: Ubah setting index menjadi `"index.refresh_interval": "30s"`, hapus parameter `refresh=true` dari pipeline ingestion, dan pastikan `indices.memory.index_buffer_size` disetel minimal 10-15%.
12. **Skenario B:** Tim engineering melaporkan bahwa pencarian kata `"buku"` berhasil menemukan dokumen, namun pencarian frasa `"buku tulis gambar"` mengembalikan nol hasil (zero-hits), padahal dokumen dengan kalimat tepat tersebut ada. Analisis pipeline mapping menunjukkan field tersebut diproses dengan tokenizer `standard` dan `edge_ngram_filter` (min_gram: 2, max_gram: 5) pada index analyzer dan search analyzer. Di manakah letak kerusakannya?
    * *Analisis & Solusi:* Penggunaan analyzer yang sama untuk indexing dan search pada edge n-gram. Saat user mencari `"buku tulis gambar"`, search analyzer memecah query tersebut menjadi token n-gram mini (`"bu"`, `"buk"`, `"buku"`, dst.). Lucene Search Parser menginterpretasikan potongan-potongan token n-gram pendek tersebut sebagai deretan posisi frasa yang saling berhimpitan secara kaku. Solusinya: Pisahkan analyzer. Gunakan `edge_ngram` **hanya** pada `analyzer` (index time), dan gunakan `standard` atau analyzer non-ngram pada `search_analyzer` (query time).
13. **Skenario C:** Anda mewarisi cluster Elasticsearch dengan satu index berukuran 8 TB yang performa aggregasinya sangat lambat. Hasil investigasi menemukan bahwa developer sebelumnya mengaktifkan field text biasa dan menyalakan `"fielddata": true` pada 15 field untuk kebutuhan reporting dashboard. Bagaimana rencana mitigasi arsitektur Anda tanpa menimbulkan downtime pada aplikasi klien?
    * *Analisis & Solusi:* 
      1. Rancang mapping baru (v2) dengan mematikan seluruh flag `fielddata: true` dan menambahkan sub-field bertipe `keyword` (yang menggunakan *Doc Values* disk-backed off-heap).
      2. Buat index baru `index_v2` dengan setting shard dan mapping yang sudah dioptimasi.
      3. Jalankan Elasticsearch `_reindex` API di latar belakang dari index lama ke `index_v2` (gunakan batch size terukur, misal: `scroll=10m`, `slices=auto`).
      4. Gunakan Index Aliases. Arahkan alias kueri dashboard secara instan (*atomic alias swap*) ke index baru.
      5. Bersihkan heap cache menggunakan `POST /_cache/clear?fielddata=true` dan hapus index lama untuk mengembalikan stabilitas JVM.

---

## 16. Summary

1. **Efisiensi Lucene Segments:** Kecepatan Elasticsearch dibangun di atas struktur data immutable yang sangat terspesialisasi: Finite State Transducers (`.tip`) sebagai penunjuk memori berkecepatan tinggi, Block Term Index (`.tim`), Posting Lists terkompresi SIMD FoR (`.doc`, `.pos`), dan Columnar Store Doc Values (`.dvd`).
2. **Text Analysis Berbasis Konteks:** Kunci arsitektur pencarian teks terletak pada separasi yang jelas antara proses *indexing* dan proses *querying*. Penggunaan tokenizer yang agresif seperti Edge N-Gram dan Synonym Graph wajib diisolasi pada domain eksekusi yang tepat untuk mencegah pembengkakan index dan malafungsi *phrase query*.
3. **Pemberantasan Mapping Inefisien:** Mapping produksi harus bersifat deterministik dan terkendali. Hindari dynamic mapping tak terbatas yang memicu *cluster state crash*. Selalu nonaktifkan metadata yang tidak dievaluasi oleh use-case aplikasi (`norms`, `index_options`, `doc_values`).
4. **Stabilitas Throughput vs Latensi:** Skalabilitas Elasticsearch skala enterprise bergantung pada pemahaman trade-off perangkat keras: menyeimbangkan JVM Heap untuk write buffer dan Term FST, sembari menyisakan minimal 50% memori fisik untuk Linux OS Page Cache demi menjamin keandalan akses Doc Values dan Search Posting Lists.