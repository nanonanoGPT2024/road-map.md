# BAB-02-Inverted-Index-Text-Analysis-Mapping-Engine: Quiz, Challenge, & Knowledge Check

Dokumen ini dirancang sebagai instrumen evaluasi mandiri dan pengujian pemahaman mendalam terkait arsitektur internal Apache Lucene dan Elasticsearch pada level mesin analisis teks, inverted index, serta strategi pemetaan tipe data (*mapping engine*).

---

## Bagian 1: Basic Questions (Pondasi Konseptual)

### Pertanyaan 1: Struktur & Komponen Inverted Index
**Pertanyaan:** Jelaskan apa itu Inverted Index pada Apache Lucene dan sebutkan komponen data minimal yang disimpan dalam struktur posting list untuk mendukung penelusuran kata kunci serta perhitungan *relevance scoring*!

**Kunci Jawaban & Pembahasan:**
Inverted Index adalah struktur data utama berorientasi term yang memetakan setiap term/token unik ke daftar dokumen tempat term tersebut ditemukan. Berbeda dengan forward index (dokumen $\rightarrow$ kata), inverted index membalik relasi tersebut (kata $\rightarrow$ dokumen).

Komponen data pada Inverted Index:
1. **Term Dictionary & Term Index (FST - Finite State Transducer):** Menyimpan daftar term terurut leksikografis beserta offset penunjuk posting list yang dikompresi di memori.
2. **Postings List:**
   - **Document ID (DocID):** Identitas numerik internal dokumen yang memuat term.
   - **Term Frequency (TF):** Jumlah kemunculan term dalam dokumen terkait (digunakan oleh algoritma skoring BM25).
   - **Positions:** Offset posisi token dalam kalimat/teks (wajib untuk operasi *phrase query* dan *proximity match*).
   - **Offsets (Start & End character):** Posisi karakter awal dan akhir pada teks mentah (digunakan untuk *search highlighting*).
   - **Payloads (Opsional):** Metadata biner level token tingkat rendah yang dapat disisipkan untuk scoring kustom.

---

### Pertanyaan 2: Perbedaan Fundamental Tipe Data `text` vs `keyword`
**Pertanyaan:** Dalam mapping engine Elasticsearch, apa perbedaan mendasar antara tipe data `text` dan `keyword` dalam hal proses analisis, struktur penyimpanan Lucene, dan skenario penggunaannya?

**Kunci Jawaban & Pembahasan:**
- **Tipe `text`:**
  - **Analisis:** Mengalami *text analysis pipeline* (char filter $\rightarrow$ tokenizer $\rightarrow$ token filter) saat indexing dan search time. Teks dipecah menjadi token-token individual (misalnya *lowercased*, *stemmed*).
  - **Struktur Lucene:** Diindeks ke dalam Inverted Index dengan positions dan offsets. Secara *default*, `fielddata` dinonaktifkan sehingga tidak efisien/dilarang untuk agregasi dan sorting.
  - **Skenario:** *Full-text search* (deskripsi artikel, judul konten, log message mentah).
- **Tipe `keyword`:**
  - **Analisis:** Tidak dianalisis (*not analyzed*). String diindeks utuh secara literal sebagai satu term tunggal.
  - **Struktur Lucene:** Disimpan di Inverted Index sebagai satu term, sekaligus secara otomatis disimpan dalam struktur kolom **Doc Values** (disk berbasis kolom terurut) untuk operasi cepat.
  - **Skenario:** Filter presisi (*exact match*), sorting, agregasi terms (*group by*), metrik, serta identifikasi unik (status transaksi, UUID, kode SKU, IP address).

---

### Pertanyaan 3: Tahapan Text Analysis Pipeline
**Pertanyaan:** Sebutkan 3 tahapan sekuensial dalam proses text analysis di Elasticsearch dan jelaskan tanggung jawab masing-masing tahapan!

**Kunci Jawaban & Pembahasan:**
1. **Character Filters (`char_filter`):** Menerima stream karakter mentah sebelum dipecah menjadi token. Berfungsi membersihkan atau mentransformasikan karakter (misal: membuang tag HTML dengan `html_strip`, memetakan simbol tertentu dengan `mapping`, atau substitusi regex dengan `pattern_replace`).
2. **Tokenizer (`tokenizer`):** Memecah stream karakter menjadi urutan token individual (*terms*) berdasarkan aturan tertentu (misal: `standard` berbasis batasan kata Unicode, `whitespace` memecah hanya pada spasi, atau `ngram`/`edge_ngram` untuk auto-complete). Tokenizer juga mencatat posisi (*position*) dan offset karakter token.
3. **Token Filters (`filter`):** Memproses stream token yang dihasilkan tokenizer secara sekuensial. Dapat memodifikasi token (misal: `lowercase`), menghapus token (misal: `stop` words), atau menambahkan token baru (misal: `synonym`, `stemmer`, `snowball`).

---

### Pertanyaan 4: Dynamic Mapping vs Strict Mapping
**Pertanyaan:** Mengapa penggunaan `dynamic: true` di lingkungan produksi berisiko tinggi terhadap stabilitas kluster Elasticsearch, dan bagaimana konfigurasi pemetaan yang aman?

**Kunci Jawaban & Pembahasan:**
Risiko utama `dynamic: true`:
- **Mapping Explosion:** Penambahan field baru tak terkontrol (misalnya akibat payload JSON dengan *key* arbitrary atau nested objek acak) dapat melampaui ambang batas default `index.mapping.total_fields.limit` (default: 1000). Hal ini menyebabkan ukuran metadata cluster state membengkak, memicu bottleneck pertukaran cluster state antar master nodes, dan berisiko fatal menyebabkan *Out of Memory (OOM)* pada node.
- **Type Guessing Inaccuracy:** Elasticsearch menebak tipe data berdasarkan dokumen pertama. Sebagai contoh, jika angka numerik masuk tanpa tanda kutip, field dipetakan ke `long`, menyebabkan dokumen berikutnya yang mengirimkan nilai alfanumerik ditolak dengan error `mapper_parsing_exception`.

Konfigurasi yang aman:
Menggunakan `dynamic: "strict"` pada index production, atau `dynamic: "runtime"` jika membutuhkan fleksibilitas query ad-hoc tanpa membebani disk index.

---

### Pertanyaan 5: Peran `doc_values` dan `fielddata`
**Pertanyaan:** Jelaskan perbedaan arsitektural antara `doc_values` dan `fielddata`. Mengapa pengaktifan `fielddata: true` pada tipe `text` sangat dihindari?

**Kunci Jawaban & Pembahasan:**
- **Doc Values:** Struktur data *columnar* (berorientasi kolom) yang dibangun saat dokumen diindeks dan disimpan di *disk* (dengan pemanfaatan agresif terhadap OS filesystem page cache). Doc values mendukung kompresi tinggi dan digunakan untuk sorting, aggregations, dan script access pada field non-`text`.
- **Fielddata:** Struktur in-memory heap yang memuat inverted index dari field `text` ke dalam JVM Heap saat query agregasi/sorting dieksekusi pertama kali.
- **Mengapa dihindari:** Fielddata mengkonsumsi memori JVM Heap dalam jumlah sangat besar. Proses *uninvert* inverted index ke dalam heap lambat, tidak terkompresi dengan baik, dan sangat rentan memicu JVM garbage collection pause panjang (Stop-the-World) atau `OutOfMemoryError (OOM)`.

---

## Bagian 2: Intermediate Questions (Deep Dive Teknis)

### Pertanyaan 6: Mekanisme Search Analyzer vs Index Analyzer
**Pertanyaan:** Dalam kondisi apa kita perlu mendefinisikan `search_analyzer` yang berbeda dari `analyzer` (index-time analyzer)? Berikan satu contoh konkret yang sering diimplementasikan pada production!

**Kunci Jawaban & Pembahasan:**
Secara default, Elasticsearch menggunakan analyzer yang sama untuk indexing dan searching agar term yang dicari cocok (*exact match*) dengan term yang tersimpan di inverted index.

Namun, `search_analyzer` perlu dibedakan saat transformasi indexing akan merusak akurasi atau menghasilkan *false positive* jika diaplikasikan pada kata kunci pencarian.

**Contoh Konkret (Edge N-gram untuk Autocomplete):**
- Pada **Index Analyzer**, kita menggunakan `edge_ngram` filter (min_gram: 2, max_gram: 10) sehingga kata `"bandung"` dipecah menjadi token: `["ba", "ban", "band", "bandu", "bandun", "bandung"]`.
- Jika analyzer yang sama digunakan saat **Search Time**, maka saat user mengetik query lengkap `"bandung"`, query tersebut akan dipecah lagi menjadi `["ba", "ban", ...]` dan mencocokkan dokumen yang hanya mengandung kata `"bali"` atau `"batik"` (false positive tinggi).
- **Solusi:** Gunakan `standard` analyzer sebagai `search_analyzer` (hanya menghasilkan token `["bandung"]`), yang langsung dicocokkan ke posting list edge n-gram tanpa memecah kata kunci pencarian.

---

### Pertanyaan 7: Implikasi `position_increment_gap` pada Array of Text
**Pertanyaan:** Apa fungsi parameter `position_increment_gap` pada field bertipe `text`, dan apa dampak teknisnya terhadap eksekusi *match_phrase query* pada array string?

**Kunci Jawaban & Pembahasan:**
Secara default, saat dokumen memiliki array string seperti:
`"sections": ["arsitektur microservices terdistribusi", "pemrograman golang performa tinggi"]`

Lucene menggabungkan elemen array ke dalam satu stream token. Jika tidak ada jeda posisi, token terakhir pada elemen pertama (`"terdistribusi"`, posisi N) dan token pertama pada elemen kedua (`"pemrograman"`, posisi N+1) dianggap bertetangga langsung.

Akibatnya, query:
`{"query": {"match_phrase": {"sections": "terdistribusi pemrograman"}}}`
akan mencocokkan dokumen tersebut (*false match* antar batasan kalimat/elemen).

`position_increment_gap` (default bernilai 100) menambahkan gap angka posisi token sebesar 100 antar elemen array yang bersebelahan. Dengan demikian, posisi token berubah dari N menjadi N + 101, sehingga `match_phrase` query dengan *slop* standar tidak akan terjadi *cross-element false match*.

---

### Pertanyaan 8: Perilaku `norms` dan Penghematan Disk
**Pertanyaan:** Apa itu metadata `norms` pada field `text`, bagaimana formulanya memengaruhi scoring BM25, dan kapan kita sebaiknya menyetel `"norms": false`?

**Kunci Jawaban & Pembahasan:**
- **Definisi:** `norms` menyimpan faktor normalisasi panjang dokumen (*field length normalization*) yang dikompresi menjadi 1 byte per dokumen per field.
- **Pengaruh BM25:** Formula BM25 memprioritaskan dokumen yang lebih ringkas jika memuat frekuensi term yang sama (dokumen pendek dengan term X dianggap lebih relevan daripada dokumen sepanjang 500 halaman yang hanya memuat term X sekali). `norms` menyediakan informasi panjang dokumen tersebut untuk perhitungan relevansi.
- **Kapan dimatikan (`"norms": false`):**
  1. Field `text` yang hanya digunakan untuk pencarian biner atau *filtering* tanpa memerlukan perangkingan skor relevansi (misal: field kode error, log level, tag pencarian tanpa bobot panjang teks).
  2. Menghemat alokasi disk dan page cache memori secara signifikan (menghemat 1 byte untuk setiap dokumen pada indeks dengan miliaran data).

---

### Pertanyaan 9: Token Filter `synonym_graph` vs `synonym`
**Pertanyaan:** Mengapa Elasticsearch merekomendasikan `synonym_graph` daripada `synonym` standar untuk sinonim multi-word (*multi-token synonyms*), dan mengapa `synonym_graph` hanya boleh diaplikasikan sebagai `search_analyzer`?

**Kunci Jawaban & Pembahasan:**
- **Problem dengan `synonym` standar:** Jika sebuah sinonim terdiri dari multi-word (misal: `"dns"` $\leftrightarrow$ `"domain name system"`), token filter `synonym` konvensional merusak urutan posisi token (*token position length*), sehingga pencarian frase (*phrase query*) menghasilkan token offset yang ambigu dan query scoring yang tidak akurat.
- **Solusi `synonym_graph`:** Membentuk struktur graf token (*directed acyclic graph / DAG*) yang merepresentasikan jalur paralel token alternatif dengan *position length* yang presisi.
- **Batasan Search-time:** Apache Lucene tidak mendukung pengindeksan graf token secara langsung ke inverted index statis saat indexing (`index_analyzer` akan melemparkan exception jika mendeteksi `synonym_graph`). Oleh karena itu, parsing graf wajib ditangani pada query parser saat fase query execution (`search_analyzer`).

---

### Pertanyaan 10: Multi-fields Pattern (`fields`)
**Pertanyaan:** Perhatikan konfigurasi mapping berikut:
```json
{
  "properties": {
    "title": {
      "type": "text",
      "analyzer": "indonesian",
      "fields": {
        "raw": {
          "type": "keyword",
          "ignore_above": 256
        }
      }
    }
  }
}
```
Jelaskan keunggulan arsitektural dari pola multi-fields di atas dan bagaimana cara melakukan query yang memanfaatkan kedua sub-field tersebut secara simultan!

**Kunci Jawaban & Pembahasan:**
- **Keunggulan:** Pola ini mengindeks data yang sama ke dalam dua struktur data Lucene yang berbeda tanpa menduplikasi transmisi payload dari aplikasi:
  1. `title`: Menggunakan Inverted Index dengan stemming bahasa Indonesia untuk *full-text search* fleksibel (mencocokkan variasi kata dasar seperti *"pelanggan"* dengan *"langganan"*).
  2. `title.raw`: Menggunakan Doc Values dan Inverted Index literal untuk sorting alfabetis akurat, agregasi terms (*aggregation buckets*), serta exact-match filtering.
- **Pemanfaatan Simultan dalam Query:**
```json
{
  "query": {
    "match": {
      "title": "rekening bank"
    }
  },
  "sort": [
    {
      "title.raw": {
        "order": "asc"
      }
    }
  ],
  "aggs": {
    "unique_titles": {
      "terms": {
        "field": "title.raw",
        "size": 10
      }
    }
  }
}
```

---

## Bagian 3: Skenario Kasus Nyata Produksi (Production Scenarios)

### Skenario 1: Mapping Explosion Akibat Logging JSON Mentah
**Konteks Masalah:**
Tim DevOps mengirimkan raw log aplikasi Kubernetes langsung ke Elasticsearch index `app-logs-2026.10` tanpa konfigurasi mapping template (`dynamic: true`). Pengembang aplikasi mencatat payload request HTTP pihak ketiga ke dalam field `http.payload`, di mana *key* JSON bersifat dinamis (mengandung token transaksi acak dan nomor identitas seperti `payload.trx_981273918273`). Setelah 7 hari, kluster mengalami degradasi drastis: query latency melonjak dari 15ms ke 12 detik, dan master node memicu alert `cluster_state update task took too long`.

**Diagnosis Masalah:**
1. Penambahan ribuan *key* JSON arbitrary menyebabkan *mapping explosion* yang melampaui limit field default index.
2. Setiap kali field baru terdeteksi, node pengindeks mengirimkan request `cluster:admin/indices/mapping/put` ke master node.
3. Master node terblokir memproses serialisasi dan sinkronisasi cluster state berukuran puluhan megabyte ke seluruh node cluster, menyebabkan latency cluster-wide freeze.

**Solusi & Konfigurasi Mapping:**
Ganti field dinamis dengan tipe data `flattened` atau terapkan template dengan `dynamic: "strict"`:
```json
PUT /app-logs-2026.10-reindexed
{
  "settings": {
    "index.mapping.total_fields.limit": 500
  },
  "mappings": {
    "dynamic": "strict",
    "properties": {
      "@timestamp": { "type": "date" },
      "service_name": { "type": "keyword" },
      "log_level": { "type": "keyword" },
      "message": { "type": "text" },
      "http": {
        "properties": {
          "status_code": { "type": "short" },
          "path": { "type": "keyword" },
          "payload": {
            "type": "flattened"
          }
        }
      }
    }
  }
}
```
*Tipe data `flattened` mengindeks seluruh nested key-value pairs ke dalam satu field indexed tanpa mendaftarkan setiap child key ke cluster state metadata.*

---

### Skenario 2: Anomali Full-Text Search pada Kata Bersimbol & Nomor Model
**Konteks Masalah:**
Sebuah platform e-commerce menjual perangkat elektronik. Pengguna mengeluhkan bahwa pencarian produk dengan kode model `"iPhone 14 Pro Max"` atau nomor part `"C-400/ZX"` menghasilkan hasil yang tidak relevan atau bahkan *zero hit*. Analisis menunjukkan bahwa indeks menggunakan analyzer `standard`. Karakter tanda hubung (`-`) dan garis miring (`/`) diperlakukan sebagai delimeter pemisah kata, dan tokenizer standard memecah `"C-400/ZX"` menjadi token terpisah `["c", "400", "zx"]`. Saat dicari dengan term presisi, skor relevansi terdistorsi atau bertabrakan dengan produk `"ZX-400"`.

**Diagnosis Masalah:**
`standard` analyzer membuang tanda baca dan memecah alfanumerik khusus, merusak identitas kode model barang (*part number / product code*).

**Solusi Teknis:**
Bangun custom analyzer dengan `word_delimiter_graph` filter yang mempertahankan token asli sekaligus menghasilkan token turunan, dikombinasikan dengan sub-field `keyword`:
```json
PUT /products-catalog
{
  "settings": {
    "analysis": {
      "filter": {
        "product_code_filter": {
          "type": "word_delimiter_graph",
          "generate_word_parts": true,
          "generate_number_parts": true,
          "catenate_words": true,
          "catenate_numbers": true,
          "catenate_all": true,
          "split_on_case_change": true,
          "preserve_original": true
        }
      },
      "analyzer": {
        "product_analyzer": {
          "type": "custom",
          "tokenizer": "whitespace",
          "filter": [
            "lowercase",
            "product_code_filter",
            "flatten_graph"
          ]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "model_number": {
        "type": "text",
        "analyzer": "product_analyzer",
        "fields": {
          "exact": {
            "type": "keyword"
          }
        }
      }
    }
  }
}
```

---

### Skenario 3: Skalabilitas Memory Leak Akibat Search Highlighting pada Field Berukuran Masif
**Konteks Masalah:**
Platform sistem arsip dokumen hukum mengindeks putusan pengadilan yang masing-masing berisi 200 hingga 1.000 halaman teks mentah ke dalam field `konten_putusan` bertipe `text`. Saat fitur *Search Highlighting* diaktifkan pada halaman penelusuran hasil:
```json
{
  "query": { "match": { "konten_putusan": "wanprestasi kontrak" } },
  "highlight": { "fields": { "konten_putusan": {} } }
}
```
Node Elasticsearch mengalami lonjakan penggunaan CPU hingga 100% dan JVM Garbage Collection thrashing berat saat 20 konkurensi query masuk secara simultan.

**Diagnosis Masalah:**
Secara default, jika tidak ada metadata offset yang disimpan di Inverted Index, Elasticsearch menggunakan highlighter tipe **Unified/Plain Highlighter** yang melakukan *re-analyzing* (analisis ulang seluruh isi teks dokumen dari field `_source` pada memori) untuk menghitung offset karakter setiap kali highlight dieksekusi. Membaca dan menganalisis dokumen berukuran puluhan megabyte secara dinamis untuk ratusan dokumen hit membebani CPU dan Heap secara ekstrim.

**Solusi Arsitektur:**
Aktifkan `term_vector` dengan konfigurasi `with_positions_offsets` pada field teks bervolume masif untuk memanfaatkan **Fast Vector Highlighter (FVH)**:
```json
PUT /putusan_hukum
{
  "mappings": {
    "properties": {
      "nomor_perkara": { "type": "keyword" },
      "konten_putusan": {
        "type": "text",
        "analyzer": "standard",
        "term_vector": "with_positions_offsets",
        "index_options": "offsets"
      }
    }
  }
}
```
*Dengan `term_vector: "with_positions_offsets"`, posisi dan offset karakter telah terkompresi di disk Lucene, sehingga engine dapat langsung mengekstrak fragmen highlight tanpa melakukan tokenisasi ulang teks mentah.*

---

## Bagian 4: Practical Chapter Challenge

### Tantangan: Merancang Index E-Catalog Multibahasa & Search Autocomplete

**Spesifikasi Kebutuhan:**
Buat konfigurasi indeks bernama `production-catalog-v1` yang memenuhi seluruh kriteria arsitektur berikut:

1. **Mapping Control:**
   - Larang penambahan field dinamis baru secara ketat (`dynamic: "strict"`).
2. **Text Analysis Pipeline:**
   - Buat custom analyzer `catalog_search_analyzer` dengan `char_filter` pembersih tag HTML.
   - Buat custom edge n-gram tokenizer/filter untuk mendukung pencarian instan prefix (minimal 3 karakter, maksimal 15 karakter).
3. **Fields Specification:**
   - `id`: Unique identifier (tipe `keyword`).
   - `sku`: Kode unik barang (tipe `keyword`).
   - `name`: Teks nama produk dengan dukungan *full-text search*, multi-field `prefix` (untuk autocomplete via edge n-gram), dan multi-field `keyword` untuk sorting.
   - `tags`: Array keyword untuk filtering produk.
   - `attributes`: Object arbitrer (misal `{"color": "navy", "size": "XL", "watt": 45}`) yang tidak boleh merusak mapping state (*hint: gunakan `flattened`*).
   - `created_at`: Tipe data `date`.
   - `price`: Numerik untuk komparasi range (tipe `scaled_float` dengan `scaling_factor: 100`).

#### Solusi Implementasi Lengkap (JSON Request Payload):
```json
PUT /production-catalog-v1
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 1,
    "analysis": {
      "char_filter": {
        "html_strip_filter": {
          "type": "html_strip"
        }
      },
      "filter": {
        "edge_ngram_filter": {
          "type": "edge_ngram",
          "min_gram": 3,
          "max_gram": 15
        }
      },
      "analyzer": {
        "catalog_text_analyzer": {
          "type": "custom",
          "char_filter": ["html_strip_filter"],
          "tokenizer": "standard",
          "filter": ["lowercase"]
        },
        "catalog_autocomplete_index_analyzer": {
          "type": "custom",
          "char_filter": ["html_strip_filter"],
          "tokenizer": "standard",
          "filter": ["lowercase", "edge_ngram_filter"]
        },
        "catalog_autocomplete_search_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase"]
        }
      }
    }
  },
  "mappings": {
    "dynamic": "strict",
    "properties": {
      "id": {
        "type": "keyword"
      },
      "sku": {
        "type": "keyword"
      },
      "name": {
        "type": "text",
        "analyzer": "catalog_text_analyzer",
        "fields": {
          "autocomplete": {
            "type": "text",
            "analyzer": "catalog_autocomplete_index_analyzer",
            "search_analyzer": "catalog_autocomplete_search_analyzer"
          },
          "sortable": {
            "type": "keyword",
            "ignore_above": 256
          }
        }
      },
      "tags": {
        "type": "keyword"
      },
      "attributes": {
        "type": "flattened"
      },
      "created_at": {
        "type": "date"
      },
      "price": {
        "type": "scaled_float",
        "scaling_factor": 100
      }
    }
  }
}
```

#### Verifikasi Analisis & Query Testing:
```bash
# 1. Menguji analyzer autocomplete tokenization
POST /production-catalog-v1/_analyze
{
  "analyzer": "catalog_autocomplete_index_analyzer",
  "text": "<b>Laptop</b> Gaming Ultra"
}

# 2. Ingest contoh dokumen valid
POST /production-catalog-v1/_doc/1001
{
  "id": "PROD-1001",
  "sku": "LPT-ASUS-001",
  "name": "Laptop Gaming ASUS ROG Zephyrus",
  "tags": ["elektronik", "komputer", "gaming"],
  "attributes": {
    "ram": "32GB",
    "processor": "AMD Ryzen 9",
    "display": "16 inch 240Hz"
  },
  "created_at": "2026-10-05T10:00:00Z",
  "price": 28999000.50
}

# 3. Query Autocomplete Prefix Search
GET /production-catalog-v1/_search
{
  "query": {
    "match": {
      "name.autocomplete": "zeph"
    }
  }
}
```

---

## Bagian 5: Checklist Pemahaman (Self-Assessment Checklist)

Beri tanda centang $(\checkmark)$ pada daftar keterampilan berikut setelah Anda menguasai materinya:

- [ ] **Konsep Inverted Index & Lucene Postings:**
  - [ ] Saya memahami struktur internal Term Dictionary, Term Index (FST), dan Postings List.
  - [ ] Saya dapat menjelaskan fungsi DocID, TF, Positions, dan Offsets pada posting list.
  - [ ] Saya memahami mengapa penghapusan dokumen (*deletion*) pada Lucene sebenarnya adalah operasi penandaan *soft-delete* (bitset) hingga merge segment terjadi.

- [ ] **Mekanisme Analysis Pipeline:**
  - [ ] Saya mampu merancang pipeline khusus yang memadukan `char_filter`, `tokenizer`, dan `token_filter`.
  - [ ] Saya mengerti perbedaan krusial antara `analyzer` (index-time) dan `search_analyzer` (query-time).
  - [ ] Saya memahami cara kerja `_analyze` API untuk debugging stream token internal.

- [ ] **Mapping Engine & Penghematan Resource:**
  - [ ] Saya mampu mencegah insiden *mapping explosion* dengan `dynamic: "strict"` atau tipe data `flattened`.
  - [ ] Saya dapat memilih secara presisi kapan menggunakan `text`, `keyword`, `scaled_float`, atau `date`.
  - [ ] Saya memahami kapan menonaktifkan `doc_values` atau `norms` untuk menghemat alokasi disk dan RAM.
  - [ ] Saya menguasai implementasi multi-fields (`fields`) untuk mendukung full-text search dan agregasi/sorting secara simultan.
