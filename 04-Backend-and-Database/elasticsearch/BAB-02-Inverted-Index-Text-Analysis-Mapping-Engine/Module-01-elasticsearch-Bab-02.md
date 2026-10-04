# Bab 02 Module 01: Inverted Index, Text Analysis & Mapping Engine

---

## 01: Identitas Modul
* **Mata Kuliah/Modul:** Elasticsearch Architecture & Engineering
* **Kategori:** 04-Backend-and-Database
* **Kode Modul:** ES-ARCH-0201
* **Tingkat Kesulitan:** Advanced / Principal Engineer Level
* **Prasyarat:** Pemahaman HTTP REST APIs, Data Modeling Relasional/NoSQL, Dasar Teori Graph & Hash Maps, Familiaritas dengan Java Runtime Environment (JVM).
* **Target Pembaca:** Backend Engineers, Database Engineers, Search Specialists, Distributed Systems Architects.

---

## 02: Learning Objectives
Setelah menyelesaikan modul ini, peserta didik mampu:
1. Menjelaskan struktur internal Apache Lucene Segment, Term Dictionary, Frequency-Distance Array, dan Posting Lists yang membentuk Inverted Index.
2. Membedakan secara mekanistik eksekusi pipeline Text Analysis: Character Filters, Tokenizers, dan Token Filters.
3. Merancang mapping Elasticsearch secara deterministik (`dynamic: strict`), mengisolasi tipe data `text` dan `keyword`, serta mengoptimalkan *doc_values* versus *fielddata*.
4. Mengimplementasikan custom analyzer multi-bahasa dengan edge-ngram, normalization filter, dan token de-duplication.
5. Menghindari lonjakan memori Heap JVM akibat *Mapping Explosion* dan unconstrained field creation pada production scale.

---

## 03: Concept Map Diagram ASCII

```
                                [ INCOMING DOCUMENT ]
                                          |
                                   [ JSON Parser ]
                                          |
                       +------------------+------------------+
                       |                                     |
              (Field: text)                                (Field: keyword)
                       |                                     |
             [ Text Analysis Pipeline ]                      v
                       |                         [ Exact Value Storage ]
    +------------------+------------------+                  |
    |                  |                  |                  |
    v                  v                  v                  |
[Char Filter] -> [ Tokenizer ] -> [Token Filters]            |
 (HTML Strip)    (Standard/IK)    (Lower/Synonym)            |
    |                  |                  |                  |
    +------------------+------------------+                  |
                       |                                     |
                       v                                     v
         [ Terms: ["search", "engine"] ]               [ Term: "PROD-99" ]
                       |                                     |
                       +------------------+------------------+
                                          |
                                          v
                              [ APACHE LUCENE SEGMENT ]
         +--------------------------------+--------------------------------+
         | INVERTED INDEX (Terms -> Docs) | COLUMNAR STORE (Doc Values)    |
         |  Term Dictionary (.tim/.tip)   |  Sorted Doc-to-Value (.dvd/.dvm)|
         |  Posting List & Freq (.doc)    |  Fast Aggregations & Sort      |
         |  Positions/Offsets (.pos/.pay) |                                |
         +--------------------------------+--------------------------------+
```

---

## 04: Mengapa Relevan
Pencarian teks pada database tradisional (relasional B-Tree atau NoSQL document store) bekerja menggunakan forward index scan ($O(N)$) atau pattern matching regex yang menolak skalabilitas horizontal saat volume data menembus jutaan dokumen. 

Elasticsearch mentransformasikan paradigma ini dengan memecah dokumen menjadi atom-atom token leksikal dan menyusunnya ke dalam **Inverted Index**. Pemahaman yang keliru terhadap mekanisme Text Analysis dan Mapping Engine memicu konsekuensi fatal di produksi:
1. **Mapping Explosion:** Indeks crash ke status *Red* akibat jutaan dynamic fields yang menghancurkan cluster state metadata.
2. **Kueri Lambat (OOM):** Penggunaan `fielddata: true` pada unstructured text fields yang melahap batas 70% JVM heap.
3. **Pencarian Tidak Relevan/Tidak Presisi:** Kegagalan memisahkan analisis *indexing-time* dan *search-time*.

---

## 05: Anatomi Konsep Inti

### 1. Struktur Data Apache Lucene Inverted Index
Inverted Index memetakan setiap term/token unik ke daftar integer penunjuk Document ID (Posting List):
* **Term Dictionary (`.tim`):** Menyimpan semua term leksikal secara terurut. Menggunakan struktur Finite State Transducer (FST) pada RAM (`.tip`) untuk pencarian term dalam kompleksitas $O(\text{length of term})$.
* **Posting List (`.doc`):** Menyimpan list Doc ID di mana term muncul, dikompresi menggunakan algoritma *SIMD-PForDelta* atau *Frame of Reference (FoR)*.
* **Positions & Offsets (`.pos`, `.pay`):** Metadata posisi token untuk kueri frasa (`match_phrase`) dan highlighting.

### 2. Text Analysis Engine Pipeline
Setiap data bertipe `text` dialirkan melalui pipeline tiga tahap:
1. **Character Filters:** Memproses raw text stream sebelum tokenisasi (e.g., `html_strip`, `mapping_char_filter`).
2. **Tokenizer:** Memecah stream karakter menjadi token individual berdasarkan batas pembatas (e.g., whitespace, punctuation, edge-ngram).
3. **Token Filters:** Memanipulasi token yang dihasilkan (e.g., lowercase, stemming `porter_stem`, stopword removal, synonym injection).

### 3. Mapping Engine: `text` vs `keyword` & Dynamic Strategies
* **`text`:** Memicu proses analyzer, diindeks ke dalam Inverted Index. Tidak mengaktifkan `doc_values` secara default.
* **`keyword`:** Tidak melalui analyzer (disimpan verbatim), mendukung pencarian exact match, sorting, aggregations via **`doc_values`** (struktur data kolumnar disk-backed yang memanfaatkan Linux page cache).
* **Dynamic Mapping Strategy:** `dynamic: "strict"` mencegah pembuatan field otomatis yang tidak terkontrol, melindungi Cluster State.

---

## 06: Panduan Implementasi Step-by-Step

### Step 1: Uji Pipeline Text Analysis via REST API
Gunakan endpoint `_analyze` untuk memvalidasi tokenization behavior:

```http
POST /_analyze
Content-Type: application/json

{
  "tokenizer": "standard",
  "filter": ["lowercase", "stop"],
  "text": "Elasticsearch Engineering Architecture: Step-by-Step 101!"
}
```

### Step 2: Konfigurasi Index Template dengan Custom Analyzers
Bangun template yang mengombinasikan `char_filter`, custom `edge_ngram` tokenizer, dan language token filter.

```http
PUT /_index_template/ecommerce_v1_template
Content-Type: application/json

{
  "index_patterns": ["ecommerce-products-*"],
  "template": {
    "settings": {
      "number_of_shards": 3,
      "number_of_replicas": 1,
      "analysis": {
        "char_filter": {
          "clean_html_and_special": {
            "type": "html_strip",
            "escaped_tags": []
          }
        },
        "tokenizer": {
          "edge_ngram_tokenizer": {
            "type": "edge_ngram",
            "min_gram": 2,
            "max_gram": 15,
            "token_chars": ["letter", "digit"]
          }
        },
        "analyzer": {
          "product_search_analyzer": {
            "type": "custom",
            "char_filter": ["clean_html_and_special"],
            "tokenizer": "edge_ngram_tokenizer",
            "filter": ["lowercase", "asciifolding"]
          },
          "product_exact_analyzer": {
            "type": "custom",
            "tokenizer": "standard",
            "filter": ["lowercase", "asciifolding"]
          }
        }
      }
    },
    "mappings": {
      "dynamic": "strict",
      "properties": {
        "id": { "type": "keyword" },
        "sku": { 
          "type": "keyword",
          "ignore_above": 32
        },
        "title": {
          "type": "text",
          "analyzer": "product_search_analyzer",
          "search_analyzer": "product_exact_analyzer",
          "fields": {
            "raw": {
              "type": "keyword",
              "ignore_above": 256
            }
          }
        },
        "price": { "type": "scaled_float", "scaling_factor": 100 },
        "created_at": { "type": "date" }
      }
    }
  }
}
```

---

## 07: Contoh Kasus Sederhana

Skenario: Membangun indeks katalog sederhana dengan field `sku` (exact match) dan `description` (full-text search).

```http
# 1. Buat Indeks dengan Mapping Explisit
PUT /simple_catalog
{
  "mappings": {
    "dynamic": "strict",
    "properties": {
      "sku": { "type": "keyword" },
      "description": { "type": "text" }
    }
  }
}

# 2. Ingest Sample Document
POST /simple_catalog/_doc/1
{
  "sku": "LAP-MBP-16",
  "description": "Apple MacBook Pro 16 inch with M3 Max Chip"
}

# 3. Kueri Term (Exact) vs Match (Full-Text)
GET /simple_catalog/_search
{
  "query": {
    "bool": {
      "must": [
        { "match": { "description": "macbook pro" } }
      ],
      "filter": [
        { "term": { "sku": "LAP-MBP-16" } }
      ]
    }
  }
}
```

---

## 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi automated provisioning dan document ingestion engine menggunakan Python dengan client resmi `elasticsearch-py`. Skrip menangani dynamic backoff, index schema creation, dan bulk indexing.

```python
#!/usr/bin/env python3
"""
Production-Grade Elasticsearch Mapping and Ingestion Engine
Requirements: elasticsearch>=8.11.0, urllib3
"""

import sys
import logging
from typing import Dict, Any, List
from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import ApiError, ConnectionError

# Konfigurasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ES-Engine")

ES_HOST = "http://localhost:9200"
INDEX_NAME = "enterprise-catalog-v1"

INDEX_SCHEMA: Dict[str, Any] = {
    "settings": {
        "number_of_shards": 2,
        "number_of_replicas": 1,
        "refresh_interval": "5s",
        "analysis": {
            "filter": {
                "id_stemmer": {
                    "type": "stemmer",
                    "language": "indonesian"
                }
            },
            "analyzer": {
                "enterprise_text_analyzer": {
                    "type": "custom",
                    "char_filter": ["html_strip"],
                    "tokenizer": "standard",
                    "filter": ["lowercase", "id_stemmer", "asciifolding"]
                }
            }
        }
    },
    "mappings": {
        "dynamic": "strict",
        "_source": { "enabled": True },
        "properties": {
            "item_id": { "type": "keyword" },
            "upc": { "type": "keyword", "ignore_above": 64 },
            "name": {
                "type": "text",
                "analyzer": "enterprise_text_analyzer",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "metadata": {
                "type": "object",
                "properties": {
                    "category": { "type": "keyword" },
                    "tags": { "type": "keyword" },
                    "rating": { "type": "half_float" }
                }
            },
            "inventory_count": { "type": "integer" },
            "price": { 
                "type": "scaled_float", 
                "scaling_factor": 100 
            },
            "published_at": { 
                "type": "date",
                "format": "strict_date_optional_time||epoch_millis"
            }
        }
    }
}

def create_index_if_not_exists(client: Elasticsearch, index_name: str, schema: Dict[str, Any]) -> None:
    try:
        if not client.indices.exists(index=index_name):
            logger.info(f"Creating index: '{index_name}' with optimized mappings.")
            client.indices.create(index=index_name, body=schema)
            logger.info(f"Index '{index_name}' successfully created.")
        else:
            logger.warning(f"Index '{index_name}' already exists. Skipping creation.")
    except ApiError as e:
        logger.error(f"API Error during index initialization: {e.meta.status} - {e.message}")
        raise

def bulk_ingest_documents(client: Elasticsearch, index_name: str, documents: List[Dict[str, Any]]) -> None:
    actions = [
        {
            "_index": index_name,
            "_id": doc["item_id"],
            "_source": doc
        }
        for doc in documents
    ]
    
    try:
        success, failed = helpers.bulk(client, actions, stats_only=False, raise_on_error=False)
        logger.info(f"Bulk ingestion complete. Success: {len(success) if isinstance(success, list) else success}, Failed: {len(failed)}")
        if failed:
            for item in failed:
                logger.error(f"Failed document ingestion: {item}")
    except ConnectionError as ce:
        logger.error(f"Network error during ingestion: {str(ce)}")
        raise

if __name__ == "__main__":
    es_client = Elasticsearch(
        [ES_HOST],
        request_timeout=30,
        max_retries=3,
        retry_on_timeout=True
    )
    
    # 1. Inisialisasi Schema
    create_index_if_not_exists(es_client, INDEX_NAME, INDEX_SCHEMA)
    
    # 2. Ingest Sample Production Records
    mock_payload = [
        {
            "item_id": "ITEM-1001",
            "upc": "880912345678",
            "name": "Mechanical Keyboard Switch Brown (Hot-Swap)",
            "metadata": {
                "category": "Peripherals",
                "tags": ["hardware", "keyboard", "gaming"],
                "rating": 4.8
            },
            "inventory_count": 150,
            "price": 89.50,
            "published_at": "2026-03-30T10:00:00Z"
        },
        {
            "item_id": "ITEM-1002",
            "upc": "880912345679",
            "name": "Wireless Gaming Mouse with Ergonomic Grip",
            "metadata": {
                "category": "Peripherals",
                "tags": ["mouse", "wireless", "gaming"],
                "rating": 4.5
            },
            "inventory_count": 45,
            "price": 55.00,
            "published_at": "2026-03-30T11:30:00Z"
        }
    ]
    
    bulk_ingest_documents(es_client, INDEX_NAME, mock_payload)
```

---

## 09: Diagram Alur Kerja ASCII

### Alur Kerja Search Execution Engine vs Inverted Index

```
   [ Client Query: match "brown keyboard" ]
                      |
                      v
      [ Query Search Analyzer Pipeline ]
    (standard tokenization + lowercase)
                      |
           +----------+----------+
           |                     |
     Term: "brown"         Term: "keyboard"
           |                     |
           v                     v
   [ FST Term Dict ]     [ FST Term Dict ]  (RAM-cached FST)
           |                     |
           v                     v
   [ Postings: #1001 ]   [ Postings: #1001, #1004 ]
           \                     /
            \                   /
             v                 v
        [ Lucene SIMD Intersect Algorithm ]
                         |
                         v
          Doc ID Matched: [#1001]
                         |
                         v
             [ Scoring: BM25 Algorithm ]
                         |
                         v
               [ Output Result Set ]
```

---

## 10: Analisis Trade-offs

| Parameter Desain | Opsi A | Opsi B | Trade-off / Implikasi Teknis |
| :--- | :--- | :--- | :--- |
| **Penyimpanan String** | `text` | `keyword` | `text` menggunakan Term Dictionary + Posting Lists, membutuhkan memori CPU lebih tinggi untuk tokenisasi. `keyword` langsung mengindeks nilai exact ke `doc_values`, menghemat CPU dan optimal untuk sort/aggregations. |
| **Dynamic Mapping** | `dynamic: true` | `dynamic: "strict"` | `dynamic: true` mempercepat prototyping namun berisiko memicu *Mapping Explosion* dan korupsi metadata cluster. `"strict"` menuntut disiplin skema via CI/CD. |
| **N-gram Strategy** | Standard Tokenizer | `edge_ngram` Tokenizer | `edge_ngram` memberikan query autocomplete berlatensi rendah, namun memicu ukuran Inverted Index membengkak hingga 3x-10x lipat di disk. |
| **Doc Values** | Enabled (`doc_values: true`) | Disabled (`doc_values: false`) | Menonaktifkan `doc_values` menghemat ruang disk jika field tidak pernah di-sort atau di-aggregasi, namun mengeksekusi aggregasi pada field tersebut akan melempar error. |

---

## 11: Best Practices & Antipatterns

### Best Practices
1. **Gunakan Multi-Fields:** Simpan field teks dengan tipe `text` untuk full-text search sekaligus `keyword` sub-field untuk sorting dan exact aggregations.
2. **Set `ignore_above` pada Keyword:** Batasi string keyword maksimum (e.g., 256 karakter) untuk mencegah term raksasa merusak performa Term Dictionary Lucene.
3. **Pilih Tipe Numerik Optimal:** Gunakan `scaled_float` atau `integer`/`short` dibanding `float`/`double` jika tingkat presisi dapat diprediksi.

### Antipatterns
* **Mengaktifkan `fielddata: true` pada field `text`:** Memuat seluruh Inverted Index ke dalam JVM Heap memory untuk agregasi. Memicu OOM dan GC Pause parah.
* **Wildcard Queries Prefix-unbounded:** Query seperti `*term` memicu full scan pada Term Dictionary, mematikan FST caching.

---

## 12: Security Hardening
1. **Mapping Defense In Depth:** Gunakan parameter `index.mapping.total_fields.limit: 1000` dan `index.mapping.depth.limit: 5` di cluster settings untuk mencegah serangan Denial-of-Service via payload JSON bertingkat (Deeply Nested Poison Payloads).
2. **Field Level Security (FLS):** Isolasi field sensitif (seperti `ssn`, `credit_card`) di level role-based access Elasticsearch security agar tidak terindeks atau terbaca oleh analyzer publik.

---

## 13: Observabilitas & Debugging

Gunakan API internal Elasticsearch untuk menginspeksi segment dan execution vector analyzer.

```http
# 1. Memeriksa detail token hasil analyzer kustom
POST /enterprise-catalog-v1/_analyze
{
  "analyzer": "enterprise_text_analyzer",
  "text": "Sepatu Lari & Gym 100% Original!"
}

# 2. Investigasi Term Vector pada dokumen tertentu
GET /enterprise-catalog-v1/_termvectors/ITEM-1001?fields=name

# 3. Observasi Segment Allocation dan Memory Footprint
GET /_cat/segments/enterprise-catalog-v1?v&h=index,shard,segment,docs.count,size,memory
```

---

## 14: Benchmarking & Performance

Gunakan tool benchmarking **Rally** atau eksekusi warm-up queries menggunakan Track Total Hits disable untuk mengukur latensi Inverted Index traversal:

```http
GET /enterprise-catalog-v1/_search
{
  "track_total_hits": false,
  "query": {
    "match": {
      "name": "keyboard switch"
    }
  }
}
```

*Metrik Target:*
* P99 Latency: $< 15\text{ ms}$ untuk boolean match query pada segment scale 50 juta dokumen.
* Inverted Index Memory Heap overhead: $< 10\%$ dari total Lucene Segment RAM overhead berkat FST compression.

---

## 15: Hands-on Lab Mini-Project

### Skenario Lab: "Real-Time Auto-Suggest Search Index"
**Objektif:** Bangun index engine untuk menangani fitur autosuggest artikel teknik dengan toleransi typo dan case-insensitive.

**Instruksi Eksekusi:**
1. Buat index `tech-articles` dengan custom edge-ngram analyzer (min 3, max 10).
2. Terapkan pemetaan `dynamic: strict`.
3. Ingest minimal 3 dokumen artikel.
4. Lakukan kueri pencarian parsial ("dock" mencocokkan "Docker Container").

```http
PUT /tech-articles
{
  "settings": {
    "analysis": {
      "tokenizer": {
        "autocomplete_tokenizer": {
          "type": "edge_ngram",
          "min_gram": 3,
          "max_gram": 10,
          "token_chars": ["letter", "digit"]
        }
      },
      "analyzer": {
        "autocomplete": {
          "type": "custom",
          "tokenizer": "autocomplete_tokenizer",
          "filter": ["lowercase"]
        },
        "autocomplete_search": {
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
      "title": {
        "type": "text",
        "analyzer": "autocomplete",
        "search_analyzer": "autocomplete_search"
      },
      "read_count": { "type": "integer" }
    }
  }
}

POST /tech-articles/_doc/1
{ "title": "Docker Container Fundamentals", "read_count": 1200 }

# Verifikasi Search
POST /tech-articles/_search
{
  "query": {
    "match": {
      "title": "dock"
    }
  }
}
```

---

## 16: Automated Testing & Verification

Gunakan suite pengujian otomatis berbasis pytest untuk memvalidasi analyzer pipeline:

```python
import pytest
from elasticsearch import Elasticsearch

@pytest.fixture(scope="module")
def es_client():
    client = Elasticsearch(["http://localhost:9200"])
    yield client
    client.close()

def test_custom_analyzer_tokens(es_client):
    response = es_client.indices.analyze(
        index="tech-articles",
        body={
            "analyzer": "autocomplete",
            "text": "Docker"
        }
    )
    tokens = [t["token"] for t in response["tokens"]]
    # Min gram = 3, maka 'doc', 'dock', 'docke', 'docker'
    assert "doc" in tokens
    assert "dock" in tokens
    assert "docker" in tokens
    assert "d" not in tokens  # Karena min_gram = 3
```

---

## 17: Troubleshooting Guide

| Gejala Masalah | Akar Penyebab (Root Cause) | Solusi Perbaikan |
| :--- | :--- | :--- |
| `IllegalArgumentException[mapper_parsing_exception]` | Mapping strict aktif, dokumen memuat field yang belum terdefinisi. | Perbarui schema mapping via Index Template atau sesuaikan payload data producer. |
| Node Cluster OOM (`OutOfMemoryError: Java heap space`) | Penggunaan `fielddata: true` pada `text` field untuk aggregasi besar. | Hapus `fielddata: true`. Buat multi-field `.keyword` dan lakukan agregasi via `doc_values`. |
| Kueri tidak menghasilkan hit meski kata tampak cocok | *Analyzer Mismatch* antara indexing analyzer dan search analyzer. | Periksa token output menggunakan endpoint `_analyze` dan tentukan `search_analyzer` secara eksplisit. |

---

## 18: Checklist Produksi
- [ ] Pengaturan `dynamic` diset ke `"strict"` pada semua level mapping.
- [ ] Field bertipe string telah dialokasikan dengan presisi (`text` vs `keyword`).
- [ ] Parameter `ignore_above` telah ditentukan pada seluruh sub-field `keyword`.
- [ ] `index.mapping.total_fields.limit` dikonfigurasi aman ($\le 1000$).
- [ ] Setting analyzers memisahkan `index-time` dan `search-time` requirements.
- [ ] Pipeline tokenisasi telah divalidasi menggunakan automated tests (`_analyze` endpoint).

---

## 19: Ringkasan Eksekutif
Inverted Index Apache Lucene bekerja dengan memisahkan dokumen ke dalam struktur leksikal Term Dictionary dan Posting List. Text Analysis Pipeline (Char Filters, Tokenizer, Token Filters) menentukan token yang diindeks ke Term Dictionary. 

Untuk performa andal pada skala produksi, pisahkan full-text search (`text`) dari exact-matching/agregasi (`keyword` yang didukung `doc_values`). Penggunaan skema eksplisit `dynamic: "strict"` adalah standar wajib enterprise guna mencegah Mapping Explosion dan degradasi performa pada JVM Heap memory.

---

## 20: Referensi & Bacaan Lanjutan
* Apache Lucene Core Documentation: *Module lucene-core Index File Formats*
* Elastic Guides: *Text Analysis and Inverted Index Deep Dive*
* Tim Kuipers (2020), *Inside Lucene: Finite State Transducers for Fast Term Lookups*
* RFC 3986: *Uniform Resource Identifier (URI): Generic Syntax* (Standard Tokenization Base)