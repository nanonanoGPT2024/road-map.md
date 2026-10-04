# Bab 06: Vector Search, Semantic Search & Machine Learning
## Module 01: Arsitektur Vector Search, Semantic Search, dan Integrasi Machine Learning di Elasticsearch

---

### 01. Identitas Modul
* **Track:** Backend & Database Engineering
* **Course:** Elasticsearch Engineering & Distributed Search Systems
* **Module Code:** `ES-VEC-06-01`
* **Module Title:** Vector Search, Semantic Search, dan Machine Learning Inference Engine
* **Prerequisites:** 
  * Elasticsearch Core Engine Architecture (Inverted Index, Segment Merging, Translog)
  * Pemahaman Linear Algebra dasar (Dot Product, Cosine Similarity, L2 Euclidean Distance)
  * REST API dan Python Async Runtime
* **Target Audience:** Principal Systems Engineer, Lead Search Architect, Advanced Backend Engineer, Machine Learning Platform Engineer
* **Estimated Completion Time:** 180 Menit

---

### 02. Learning Objectives
Setelah menyelesaikan modul ini, engineer memiliki kapabilitas untuk:
1. Membedakan secara mendalam mekanisme internal Inverted Index (BM25) vs Hierarchical Navigable Small World (HNSW) vector graphs.
2. Mendesain skema indeks Elasticsearch untuk tipe data `dense_vector` berdimensi tinggi dengan optimasi memori dan komputasi (*quantization*, *similarity metrics*).
3. Mengonfigurasi, mengunggah, dan mengorkestrasi model NLP Transformer (e.g., HuggingFace BERT/E5/MiniLM) langsung ke dalam Elasticsearch Machine Learning Node.
4. Mengimplementasikan pipeline ingest dengan `inference` processor untuk menghasilkan vector embeddings secara *real-time* saat indexing.
5. Membangun sistem hybrid search production-grade yang menggabungkan Lexical Search (BM25) dan Approximate Nearest Neighbor (ANN) menggunakan Reciprocal Rank Fusion (RRF).
6. Mengamankan, memantau, dan melakukan troubleshooting latensi komputasi HNSW serta *inference model drift*.

---

### 03. Concept Map Diagram ASCII

```
+---------------------------------------------------------------------------------------------------------+
|                                    ELASTICSEARCH VECTOR ENGINE                                          |
+---------------------------------------------------------------------------------------------------------+
                                                     |
             +---------------------------------------+---------------------------------------+
             |                                                                               |
             v                                                                               v
+--------------------------+                                                    +--------------------------+
|      INGESTION FLOW      |                                                    |       QUERY ENGINE       |
+--------------------------+                                                    +--------------------------+
| Raw JSON Document        |                                                    | User Query String        |
|            |             |                                                    |            |             |
|            v             |                                                    |            v             |
| [Ingest Pipeline]        |                                                    | [ML Inference Node]      |
|  - Text Processing       |                                                    |  - Query to Vector       |
|  - Inference Processor   |                                                    |    Transformation        |
|    (HuggingFace Model)   |                                                    |            |             |
|            |             |                                                    +------------+-------------+
|            v             |                                                                 |
| Extracted Vector Embed   |                                                                 |
|            |             |                                                                 |
|            v             |                                                                 v
| [Index Engine]           |                                                    +--------------------------+
|  +---------------------+ |                                                    | [Hybrid Query Execution] |
|  | Lucene Inverted Idx | |                                                    |  +--------------------+  |
|  | (Lexical BM25)      | |                                                    |  | KNN Search Branch  |  |
|  +---------------------+ |                                                    |  | (HNSW ANN Search)  |  |
|  +---------------------+ |                                                    |  +--------------------+  |
|  | HNSW Vector Graph   | |<------------------- Traversal & Scoring ---------->|  +--------------------+  |
|  | (Dense Vectors)     | |                                                    |  | Lexical Branch     |  |
|  +---------------------+ |                                                    |  | (Match BM25)       |  |
|            |             |                                                    |  +--------------------+  |
|            v             |                                                    +------------+-------------+
| [Quantization Engine]    |                                                                 |
|  - INT8 / 1-bit SQ/PQ    |                                                                 v
+--------------------------+                                                    +--------------------------+
                                                                                | Reciprocal Rank Fusion   |
                                                                                | (RRF) Ranking Algorithm  |
                                                                                +------------+-------------+
                                                                                             |
                                                                                             v
                                                                                +--------------------------+
                                                                                | Final Hybrid Result Set  |
                                                                                +--------------------------+
```

---

### 04. Mengapa Relevan

Sistem pencarian berbasis kata kunci murni (*lexical search*) mengandalkan frekuensi kecocokan term (algoritma BM25). Pendekatan ini memiliki limitasi fundamental:
1. **Vocabulary Mismatch Problem:** Pengguna mencari "kendaraan roda dua mogok", namun dokumen menggunakan terminologi "sepeda motor mengalami kerusakan mesin". BM25 gagal mengidentifikasi relevansi.
2. **Contextual Ambiguity:** Kata "apple" dapat merujuk pada buah atau entitas korporasi teknologi tergantung konteks kalimat.
3. **Multimodal Disconnect:** Tidak mampu melakukan pencarian lintas modal (teks ke gambar, audio ke teks).

Vector search menyelesaikan masalah ini dengan memproyeksikan data tak terstruktur ke dalam ruang vektor berdimensi tinggi (*latent space*). Jarak spasial antar vektor merefleksikan kedekatan semantik. 

Namun, Vector Search murni memiliki kelemahan: tidak optimal untuk pencarian kata kunci eksak, kode SKU, serial number, atau nama entitas langka (*out-of-vocabulary*). 

Elasticsearch mengintegrasikan kapabilitas **Hybrid Search (BM25 + HNSW kNN via Reciprocal Rank Fusion)**, memungkinkan eksekusi inferensi machine learning langsung di level data-tier, mengeliminasi kebutuhan arsitektur terpisah antara database vektor dan search engine tradisional.

---

### 05. Anatomi Konsep Inti

#### 1. Dense Vector & Storage Engine
`dense_vector` adalah tipe data Elasticsearch yang menyimpan array numerik bertipe float (`float32`), half-float (`float16`), atau byte (`int8`). Panjang array merepresentasikan dimensi model embedding (misalnya 384 untuk `all-MiniLM-L6-v2`, 768 untuk `BERT-base`, 1536 untuk `OpenAI text-embedding-ada-002`).

#### 2. Vector Similarity Metrics
Elasticsearch mendukung metrik kalkulasi jarak:
* **Cosine Similarity (`cosine`):** Mengukur sudut antar dua vektor, mengabaikan magnitudo. Nilai: $[-1, 1]$ yang dinormalisasi menjadi $[0, 1]$ via formula:
  $$\text{score} = \frac{1 + \cos(\theta)}{2}$$
* **Dot Product (`dot_product`):** Menghitung hasil kali dot. Membutuhkan vektor yang telah dinormalisasi secara unit-length ($\|v\| = 1$). Menawarkan kecepatan eksekusi tertinggi:
  $$\text{score} = \frac{1 + (\vec{u} \cdot \vec{v})}{2}$$
* **L2 Norm Euclidean Distance (`l2_norm`):** Mengukur jarak geometris langsung antar titik:
  $$\text{score} = \frac{1}{1 + \|\vec{u} - \vec{v}\|^2}$$
* **Max Inner Product (`max_inner_product`):** Digunakan pada skenario vektor un-normalized di mana magnitudo merepresentasikan signifikansi.

#### 3. Algoritma HNSW (Hierarchical Navigable Small World)
HNSW membangun graf multi-layer hierarkis:
* **Layer Atas (Sparse):** Menavigasi lompatan jauh untuk lokalisasi klaster umum secara cepat.
* **Layer Bawah (Dense):** Melakukan navigasi granular untuk mengidentifikasi $k$-tetangga terdekat.
* **Parameter Kunci:**
  * `m`: Jumlah koneksi dua arah maksimum per node. Nilai tinggi = recall lebih baik, memori & build index lebih tinggi.
  * `ef_construction`: Ukuran dynamic candidate list saat index build. Nilai tinggi = kualitas graph lebih baik, index time lebih lambat.
  * `num_candidates` / `ef_search`: Ukuran antrean evaluasi saat runtime query.

#### 4. Vector Quantization (Scalar Quantization - SQ8)
Teknik kompresi yang mengonversi vektor `float32` (4 byte per dimensi) menjadi `int8` (1 byte per dimensi). Kompresi ini memangkas jejak RAM Lucene Vector Segment hingga ~75% dengan degradasi recall yang minimal (<1-2%).

#### 5. Reciprocal Rank Fusion (RRF)
Algoritma deterministik tanpa parameter skor mentah untuk menggabungkan hasil peringkat pencarian dari berbagai metode:
$$RRF(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
* $M$: Set metode retrieval (misal: BM25 score rank, HNSW kNN rank).
* $r_m(d)$: Peringkat (*rank*) dokumen $d$ dalam metode $m$ (dimulai dari 1).
* $k$: Konstanta penyeimbang (default Elasticsearch: 60).

---

### 06. Panduan Implementasi Step-by-Step

#### Step 1: Alokasi Node Khusus Machine Learning
Pastikan node Elasticsearch dialokasikan dengan peran `ml` untuk mengisolasi beban komputasi inference CPU/GPU dari node ingest dan node data.

Konfigurasi `elasticsearch.yml`:
```yaml
node.roles: [ data, ingest, ml ]
xpack.ml.use_auto_machine_memory_percent: true
xpack.ml.max_machine_memory_percent: 50
```

#### Step 2: Konfigurasi Index Mapping dengan HNSW Indexing
Definisikan schema index dengan dense vector terindeks HNSW dan scalar quantization.

```json
PUT /enterprise_knowledge_base
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 1,
    "index": {
      "knn": true
    }
  },
  "mappings": {
    "properties": {
      "doc_id": { "type": "keyword" },
      "title": { 
        "type": "text",
        "analyzer": "standard",
        "fields": {
          "keyword": { "type": "keyword" }
        }
      },
      "content": { 
        "type": "text",
        "analyzer": "standard"
      },
      "category": { "type": "keyword" },
      "tenant_id": { "type": "keyword" },
      "created_at": { "type": "date" },
      "content_vector": {
        "type": "dense_vector",
        "dims": 384,
        "index": true,
        "similarity": "cosine",
        "index_options": {
          "type": "hnsw",
          "m": 16,
          "ef_construction": 100
        }
      }
    }
  }
}
```

#### Step 3: Setup Model Inference Ingest Pipeline
Gunakan model NLP terlatih yang sudah di-deploy pada ML node untuk menghasilkan vektor secara otomatis saat data dimasukkan.

```json
PUT /_ingest/pipeline/nlp_embedding_pipeline
{
  "description": "Pipeline to transform content to dense vector embeddings via local ML model",
  "processors": [
    {
      "inference": {
        "model_id": "sentence-transformers__all-minilm-l6-v2",
        "input_output": [
          {
            "input_field": "content",
            "output_field": "content_vector"
          }
        ]
      }
    }
  ]
}
```

---

### 07. Contoh Kasus Sederhana

Berikut adalah verifikasi alur kerja dasar menggunakan Developer Console (Kibana REST API):

#### Indexing Data Manual
```json
POST /enterprise_knowledge_base/_doc/1?pipeline=nlp_embedding_pipeline
{
  "doc_id": "DOC-001",
  "title": "Optimasi Garbage Collection Java di Container",
  "content": "Penggunaan flag -XX:+UseG1GC dan alokasi memory limit container yang tepat dapat mencegah OOMKilled di Kubernetes.",
  "category": "DevOps",
  "tenant_id": "T-100",
  "created_at": "2024-01-15T08:00:00Z"
}
```

#### Eksekusi kNN Vector Search (Exact / Approximate)
```json
POST /enterprise_knowledge_base/_search
{
  "knn": {
    "field": "content_vector",
    "query_vector_builder": {
      "text_embedding": {
        "model_id": "sentence-transformers__all-minilm-l6-v2",
        "model_text": "mengatasi pod java crash out of memory kubernetes"
      }
    },
    "k": 5,
    "num_candidates": 50,
    "filter": {
      "term": {
        "tenant_id": "T-100"
      }
    }
  },
  "fields": ["doc_id", "title", "category"],
  "_source": false
}
```

---

### 08. Implementasi Production-Grade Lengkap Kode

Berikut adalah arsitektur mikroservis Python Async tingkat produksi menggunakan library resmi `@elastic/elasticsearch` dan `pydantic-settings` untuk mengeksekusi operasi Hybrid Search (Lexical + Vector + RRF) secara tangguh, modular, dan idempotent.

#### `config.py`
```python
from pydantic_settings import BaseSettings
from pydantic import Field

class SearchServiceConfig(BaseSettings):
    ELASTICSEARCH_HOST: str = Field(default="https://localhost:9200", env="ES_HOST")
    ELASTICSEARCH_USER: str = Field(default="elastic", env="ES_USER")
    ELASTICSEARCH_PASSWORD: str = Field(..., env="ES_PASSWORD")
    ELASTICSEARCH_CA_CERT_PATH: str = Field(..., env="ES_CA_CERT_PATH")
    MODEL_ID: str = Field(default="sentence-transformers__all-minilm-l6-v2", env="ML_MODEL_ID")
    INDEX_NAME: str = Field(default="enterprise_knowledge_base", env="ES_INDEX_NAME")
    MAX_CONNECTIONS: int = Field(default=50, env="ES_MAX_CONN")

    class Config:
        env_file = ".env"
        case_sensitive = True

config = SearchServiceConfig()
```

#### `hybrid_search_engine.py`
```python
import asyncio
import logging
from typing import List, Dict, Any, Optional
from elasticsearch import AsyncElasticsearch, ApiError, TransportError
from config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("SearchEngine")

class EnterpriseSearchClient:
    def __init__(self):
        self.es = AsyncElasticsearch(
            config.ELASTICSEARCH_HOST,
            basic_auth=(config.ELASTICSEARCH_USER, config.ELASTICSEARCH_PASSWORD),
            ca_certs=config.ELASTICSEARCH_CA_CERT_PATH,
            max_retries=3,
            retry_on_timeout=True,
            request_timeout=10.0,
            max_connections=config.MAX_CONNECTIONS
        )

    async def close(self):
        await self.es.close()

    async def initialize_schema(self):
        """Membuat index dan ingest pipeline secara idempotent."""
        try:
            # 1. Pipeline Definition
            pipeline_body = {
                "description": "Pipeline for auto vectorization via internal ML node",
                "processors": [
                    {
                        "inference": {
                            "model_id": config.MODEL_ID,
                            "input_output": [
                                {
                                    "input_field": "content",
                                    "output_field": "content_vector"
                                }
                            ]
                        }
                    }
                ]
            }
            await self.es.ingest.put_pipeline(
                id="nlp_embedding_pipeline",
                body=pipeline_body
            )
            logger.info("Ingest pipeline 'nlp_embedding_pipeline' validated.")

            # 2. Index Mapping Definition
            index_body = {
                "settings": {
                    "number_of_shards": 2,
                    "number_of_replicas": 1,
                    "index.codec": "best_compression"
                },
                "mappings": {
                    "properties": {
                        "doc_id": {"type": "keyword"},
                        "title": {
                            "type": "text",
                            "fields": {"keyword": {"type": "keyword"}}
                        },
                        "content": {"type": "text"},
                        "category": {"type": "keyword"},
                        "tenant_id": {"type": "keyword"},
                        "created_at": {"type": "date"},
                        "content_vector": {
                            "type": "dense_vector",
                            "dims": 384,
                            "index": True,
                            "similarity": "cosine",
                            "index_options": {
                                "type": "hnsw",
                                "m": 16,
                                "ef_construction": 100
                            }
                        }
                    }
                }
            }
            
            exists = await self.es.indices.exists(index=config.INDEX_NAME)
            if not exists:
                await self.es.indices.create(index=config.INDEX_NAME, body=index_body)
                logger.info(f"Index '{config.INDEX_NAME}' successfully initialized.")
            else:
                logger.info(f"Index '{config.INDEX_NAME}' already exists.")

        except ApiError as e:
            logger.error(f"Failed to initialize cluster schema: {e.meta.status} - {e.message}")
            raise

    async def execute_hybrid_search(
        self,
        query_text: str,
        tenant_id: str,
        category: Optional[str] = None,
        top_k: int = 10,
        rrf_rank_constant: int = 60,
        rrf_window_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Mengeksekusi Hybrid Search (BM25 + HNSW kNN) dengan Reciprocal Rank Fusion.
        """
        # Menyiapkan filter kontekstual multi-tenant
        filters = [{"term": {"tenant_id": tenant_id}}]
        if category:
            filters.append({"term": {"category": category}})

        search_query = {
            # Jalur 1: Lexical Query (BM25)
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query_text,
                                "fields": ["title^2", "content"],
                                "fuzziness": "AUTO"
                            }
                        }
                    ],
                    "filter": filters
                }
            },
            # Jalur 2: Vector Query (HNSW kNN)
            "knn": {
                "field": "content_vector",
                "query_vector_builder": {
                    "text_embedding": {
                        "model_id": config.MODEL_ID,
                        "model_text": query_text
                    }
                },
                "k": rrf_window_size,
                "num_candidates": rrf_window_size * 2,
                "filter": filters
            },
            # Penggabungan Skor menggunakan Reciprocal Rank Fusion
            "rank": {
                "rrf": {
                    "window_size": rrf_window_size,
                    "rank_constant": rrf_rank_constant
                }
            },
            "size": top_k,
            "_source": ["doc_id", "title", "category", "created_at", "content"]
        }

        try:
            response = await self.es.search(
                index=config.INDEX_NAME,
                body=search_query
            )

            results = []
            hits = response["hits"]["hits"]
            for hit in hits:
                results.append({
                    "id": hit["_id"],
                    "rrf_score": hit["_score"],
                    "document": hit["_source"]
                })

            return results

        except ApiError as e:
            logger.error(f"Elasticsearch API error on hybrid search: {e.message}")
            raise
        except TransportError as e:
            logger.error(f"Network transport level error: {str(e)}")
            raise

async def main():
    client = EnterpriseSearchClient()
    try:
        await client.initialize_schema()

        # Simulasi Query
        query = "strategi memory dump analysis kubernetes"
        tenant = "T-100"
        
        logger.info(f"Executing hybrid search for: '{query}' [Tenant: {tenant}]")
        results = await client.execute_hybrid_search(
            query_text=query,
            tenant_id=tenant,
            top_k=3
        )

        for rank, res in enumerate(results, 1):
            print(f"Rank {rank} | RRF Score: {res['rrf_score']:.6f} | ID: {res['document']['doc_id']} | Title: {res['document']['title']}")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 09. Diagram Alur Kerja ASCII

```
[Inference Ingestion Flow]
+----------------------+     +----------------------+     +------------------------+
| Client Ingest (JSON) | --> | Elasticsearch Ingest | --> | Inference Processor    |
| Document Content     |     | Pipeline Interceptor |     | (Local PyTorch Model)  |
+----------------------+     +----------------------+     +------------------------+
                                                                      |
                                                              Generates [dims: 384]
                                                                      |
+---------------------------------------------------------------------+
|
v
+-------------------------------+     +--------------------------------+
| Write to Index Engine         |     | HNSW Graph Construction        |
| - Lucene Inverted Index (Text)| --> | - Build Multi-layer Skip List  |
| - Scalar Quantization (8-bit) |     | - Link Nearest Neighbors       |
+-------------------------------+     +--------------------------------+

[Hybrid Query Orchestration]
             +-------------------------+
             | User Query via REST API |
             +-------------------------+
                          |
             +------------+------------+
             |                         |
             v                         v
+-------------------------+  +-------------------------+
| Lexical Branch (BM25)   |  | Vector Inference Branch |
| - Tokenizer / Analyzer  |  | - Query to Embedding    |
| - Match Multi-Fields    |  | - HNSW Graph Traversal  |
| - Apply Pre-Filter      |  | - Apply Pre-Filter      |
+-------------------------+  +-------------------------+
             |                         |
             v                         v
   [Ranked List: BM25]       [Ranked List: kNN]
             |                         |
             +------------+------------+
                          |
                          v
             +-------------------------+
             | Reciprocal Rank Fusion  |
             | Score = 1/(60+R_bm25)   |
             |       + 1/(60+R_knn)    |
             +-------------------------+
                          |
                          v
             +-------------------------+
             | Top-K Ranked Payload    |
             +-------------------------+
```

---

### 10. Analisis Trade-offs

| Parameter/Arsitektur | Pendekatan A | Pendekatan B | Analisis Komparasi Arsitektural |
| :--- | :--- | :--- | :--- |
| **Indexing Strategy** | *Exact kNN* (`script_score`) | *Approximate kNN* (`HNSW`) | Exact kNN memiliki 100% recall tetapi melakukan exhaustive search $O(N)$ (latensi meledak pada dataset >100k dokumen). HNSW beroperasi pada $O(\log N)$ dengan latensi sub-10ms namun membutuhkan alokasi RAM signifikan. |
| **Ranking Methodology** | Linear Score Combination | Reciprocal Rank Fusion (RRF) | Linear Score mengharuskan normalisasi manual skor BM25 (rentang tak terbatas $[0, \infty)$) dan kNN ($[0, 1]$) yang sangat rapuh terhadap skew. RRF menyelaraskan skor berdasarkan relative ordinal rank tanpa dependensi magnitudo skor. |
| **Vector Storage Format** | Uncompressed `float32` | `int8` Scalar Quantization | `float32` menjaga representasi floating point murni tanpa kehilangan presisi, tetapi butuh 4 byte/dimensi. `int8` (SQ) mengompresi footprint memori hingga 75% dengan dampak penurunan recall marginal (<1.5%). |
| **Embedding Location** | External Inference (App Tier) | Native Ingestion Pipeline (ML Node)| External inference memisahkan komputasi berat dari data cluster tapi menambah network latency antar-hop. Native ML node memusatkan pipeline data, menyederhanakan arsitektur, dan memangkas latency overhead jaringan. |

---

### 11. Best Practices & Antipatterns

#### Best Practices
1. **Gunakan Pre-Filtering pada kNN:** Selalu sertakan blok `filter` di dalam objek `knn` (bukan query `post_filter`). Lucene akan membatasi graf penelusuran HNSW hanya pada dokumen yang lolos filter, meningkatkan query throughput.
2. **Normalisasi Vektor di Awal:** Jika menggunakan metrik `dot_product`, pastikan vektor dinormalisasi ($\|v\|=1$) saat preprocessing untuk memangkas latensi komputasi *square root* di runtime Lucene.
3. **Konfigurasi `ef_search` yang Tepat:** Atur rasio $num\_candidates = 2 \times k$ hingga $5 \times k$ untuk menjaga keseimbangan optimal antara Recall (>95%) dan P99 latency (<20ms).
4. **Isolasi ML Node:** Tetapkan node khusus dengan role `ml` pada kluster production untuk mencegah inference load mengganggu stabilitas CPU pada `data_hot` node.

#### Antipatterns
* **Anti-Pattern 1: Menyimpan Vektor Berdimensi Tinggi Tanpa Kompresi pada Skala Puluhan Juta Baris.**
  * *Dampak:* Out-Of-Memory (OOM) pada Lucene off-heap storage.
  * *Solusi:* Terapkan 8-bit Scalar Quantization atau 1-bit quantization jika didukung, dan gunakan hardware dengan RAM yang memadai untuk memory mapping.
* **Anti-Pattern 2: Menggunakan `script_score` Brute-Force Vector Query di Lingkungan Production Real-time.**
  * *Dampak:* CPU spiking 100% dan P99 latency melonjak drastis seiring bertambahnya data.
  * *Solusi:* Gunakan HNSW indexing (`"index": true`).
* **Anti-Pattern 3: Menjalankan Text Embeddings di Application Tier Tanpa Asynchronous Batching.**
  * *Dampak:* Network socket exhaustion dan blocking I/O pada thread worker aplikasi.

---

### 12. Security Hardening

```
                SECURE BOUNDARY (VPC / PRIVATE SUBNET)
+--------------------------------------------------------------------+
|                                                                    |
|  App Container           TLS 1.3 + RBAC Token                      |
|  [Search Service] ----------------------------------+              |
|                                                     |              |
|                                                     v              |
|                               +---------------------------------+  |
|                               |  Elasticsearch ML / Data Node   |  |
|                               |  +---------------------------+  |  |
|                               |  | Native ML Sandbox (Seccomp|  |  |
|                               |  | & Namespace Isolation)    |  |  |
|                               |  | [PyTorch Inference Engine]|  |  |
|                               |  +---------------------------+  |  |
|                               |  +---------------------------+  |  |
|                               |  | Document-Level Security   |  |  |
|                               |  | Tenant Isolation (Field:  |  |  |
|                               |  | "tenant_id")              |  |  |
|                               |  +---------------------------+  |  |
|                               +---------------------------------+  |
|                                                                    |
+--------------------------------------------------------------------+
```

1. **Native ML Model Sandboxing:** Model Transformer yang dieksekusi di node Elasticsearch berjalan di dalam process isolation (*native ML controller sandboxing*) untuk mencegah arbitrary code execution melalui model binary.
2. **Document & Field Level Security (DLS/FLS):** Pasang policy DLS berbasis role untuk membatasi search access vektor antar-tenant:
```json
POST /_security/role/tenant_isolated_search_role
{
  "indices": [
    {
      "names": [ "enterprise_knowledge_base" ],
      "privileges": [ "read" ],
      "query": {
        "template": {
          "source": {
            "term": { "tenant_id": "${_user.metadata.tenant_id}" }
          }
        }
      },
      "field_security": {
        "grant": [ "doc_id", "title", "content", "category", "created_at" ],
        "except": [ "content_vector" ]
      }
    }
  ]
}
```
3. **Memory Limits & Resource Isolation:** Lindungi JVM Heap dengan membatasi native memory ML inference via `xpack.ml.max_machine_memory_percent: 40`.

---

### 13. Observabilitas & Debugging

#### 1. Metric Penting Monitoring
* **ML Native Memory Usage:** Pantau via `GET /_nodes/stats/ml` untuk mencegah OOM killer pada level OS.
* **HNSW Vector Index Segment Size:** Pantau jejak memori vector graph menggunakan `GET /enterprise_knowledge_base/_stats/segments`.
* **Inference Pipeline Latency:** Pantau metrik `ingest_pipeline_time_in_millis` pada node ingest.

#### 2. Vector Search Profiling via Kibana DevTools
Gunakan parameter `profile` untuk membongkar detail eksekusi Lucene Graph traversal vs Scorer execution time:

```json
POST /enterprise_knowledge_base/_search
{
  "profile": true,
  "knn": {
    "field": "content_vector",
    "query_vector_builder": {
      "text_embedding": {
        "model_id": "sentence-transformers__all-minilm-l6-v2",
        "model_text": "debugging vector index latency"
      }
    },
    "k": 5,
    "num_candidates": 50
  }
}
```

Analisis output profile: periksa `graph_search` execution count, total visited nodes, dan waktu perbandingan metrik kalkulasi vektor.

---

### 14. Benchmarking & Performance

Gunakan **Rally (Elasticsearch Official Benchmarking Tool)** untuk mengukur Recall vs Latensi:

Contoh konfigurasi track Rally custom (`vector-benchmark-track.json` snippet):
```json
{
  "name": "knn-search-query",
  "operation": {
    "operation-type": "search",
    "index": "enterprise_knowledge_base",
    "body": {
      "knn": {
        "field": "content_vector",
        "query_vector": [0.034, -0.056, 0.122, "/* ... 384 dims ... */"],
        "k": 10,
        "num_candidates": 100
      }
    }
  },
  "iterations": 10000,
  "target-throughput": 250
}
```

#### Formula Penilaian Performa
* **Recall@K Metric:**
  $$\text{Recall}@K = \frac{|\text{Top } K \text{ ANN Hasil HNSW} \cap \text{Top } K \text{ Exact Exhaustive Search}|}{K}$$
* **Memory Requirement Estimation (HNSW Unquantized):**
  $$\text{RAM Bytes} \approx \text{Doc Count} \times \left( (\text{dims} \times 4) + (m \times 2 \times 8) \right)$$
  *Untuk 1,000,000 dokumen, 384 dimensi, $m=16$:*
  $$1{,}000{,}000 \times ((384 \times 4) + (16 \times 16)) \approx 1{,}000{,}000 \times (1536 + 256) \approx 1.79 \text{ GB (Off-Heap)}$$

---

### 15. Hands-on Lab Mini-Project

#### Objective
Membangun Semantic Search Engine untuk Artikel Teknis Berbasis Hybrid Search & Model Transformer.

#### File: `docker-compose.yml`
```yaml
version: '3.8'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.12.0
    container_name: es-vector-lab
    environment:
      - node.name=es01
      - cluster.name=vector-cluster
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms2g -Xmx2g"
      - xpack.security.enabled=false
      - xpack.ml.use_auto_machine_memory_percent=true
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
      test: ["CMD-SHELL", "curl -s http://localhost:9200/_cluster/health | grep -q '\"status\":\"green\"\\|\"status\":\"yellow\"'"]
      interval: 10s
      timeout: 10s
      retries: 20
```

#### Script Eksekusi Lab: `lab_runner.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "==> 1. Memulai Infrastructure Container"
docker compose up -d

echo "==> 2. Menunggu Elasticsearch Siap..."
until curl -s http://localhost:9200/_cluster/health | grep -q 'status'; do
    sleep 2
done

echo "==> 3. Memasang Model NLP Transformer via Eland Client (Mock Model Setup)"
# Simpan index definition
curl -s -X