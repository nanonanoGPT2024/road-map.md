# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 07: Search Intent & Semantic Keyword Architecture**
**Kategori: 08-AI-Data-and-Autonomous-Agents / SEO Engineering**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Memetakan Search Intent Multi-Dimensi**: Mengklasifikasikan intent pencarian (Informational, Navigational, Commercial, Transactional, serta micro-intents) menggunakan model Bi-Encoder dan Cross-Encoder terdistribusi dengan akurasi precision/recall $> 92\%$.
2. **Membangun Topic Authority Cluster berbasis Graph & Vektor**: Mengimplementasikan algoritma clustering graf (*Louvain* / *Leiden*) di atas ruang embedding vektor untuk mengeliminasi kanibalisasi kata kunci (*keyword cannibalization*) pada skala jutaan URL.
3. **Merancang Pipeline Hybrid Retrieval Terdistribusi**: Mengombinasikan sparse retrieval (BM25/SPLADE) dan dense retrieval (HNSW/Vector Index) menggunakan teknik *Reciprocal Rank Fusion* (RRF) untuk penemuan entitas target SEO.
4. **Menerapkan Schema Graph Generator Otomatis**: Membangun agen otonom (*autonomous agent*) yang mengekstrak entitas web, melakukan *entity resolution* ke Wikidata/Google Knowledge Graph API, dan menghasilkan JSON-LD terstruktur secara dinamis di edge (Cloudflare Workers/Vercel Edge).
5. **Mengaudit & Memitigasi Semantic Drift**: Memonitor degradasi relevansi semantik halaman web terhadap SERP intent shifts secara otomatis menggunakan metrik *Wasserstein Distance* dan *Cosine Drift Analysis*.

---

## 2. Prerequisites

Peserta wajib menguasai kompetensi dasar berikut:
* **Pemrograman Backend Tingkat Lanjut**: Python 3.11+ (Asyncio, Pydantic v2, FastAPI) dan TypeScript/Node.js.
* **Dasar NLP & Vektor**: Mekanisme transformer (*self-attention*), dense embeddings (`text-embedding-3-large`, `bge-large-en-v1.5`), tokenizers, dan metrik similaritas (Cosine, Dot Product, Euclidean).
* **Database & Vector Engines**: Pengalaman operasional dengan Vector Database (Qdrant, Milvus, atau pgvector) serta Distributed Cache (Redis).
* **Information Retrieval (IR)**: Pemahaman metrik evaluasi IR (MRR, NDCG@k, MAP, Precision@k).
* **Infrastruktur Modern**: Docker, Kubernetes, Apache Kafka/Redpanda untuk data streaming, dan Edge Compute (Workers/Lambdas).

---

## 3. Concept & Internal Architecture

Dalam ekosistem pencarian modern yang ditenagai oleh Google MUM, Gemini, dan RankBrain, kata kunci tidak lagi diperlakukan sebagai string leksikal (*strings*), melainkan sebagai entitas dan konsep semantik (*things*). Arsitektur semantik enterprise memisahkan representasi query ke dalam tiga lapisan: **Leksikal (Lexical)**, **Semantik Vektor (Dense Embedding)**, dan **Relasional Graf (Knowledge Graph)**.

```
       +-------------------------------------------------------------+
       |               Raw Keyword / Query Stream                    |
       +-------------------------------------------------------------+
                                      |
                                      v
       +-------------------------------------------------------------+
       |          Preprocessing & Normalization Pipeline             |
       |  (Lemmatization, Stopwords, Regex Cleaning, Normalization)   |
       +-------------------------------------------------------------+
                         |                           |
                         v                           v
          +-------------------------------+  +-----------------------------+
          | Sparse Tokenizer & Expansion  |  | Dense Vector Embedding Gen  |
          |  (SPLADE / BM25 Inverted)     |  | (Bi-Encoder: BGE / OpenAI)  |
          +-------------------------------+  +-----------------------------+
                         |                           |
                         +-------------+-------------+
                                       |
                                       v
          +----------------------------------------------------------+
          |             Hybrid Retrieval Engine (Qdrant)             |
          |    Dense Search (HNSW) <--- RRF ---> Sparse Search       |
          +----------------------------------------------------------+
                                       |
                                       v
          +----------------------------------------------------------+
          |       Cross-Encoder Reranker & Intent Classifier         |
          |   (Query-to-Document Cross-Attention / Zero-Shot NLI)    |
          +----------------------------------------------------------+
                                       |
                                       v
          +----------------------------------------------------------+
          |           Knowledge Graph Entity Resolution              |
          |          (Wikidata QID, Schema.org Generator)            |
          +----------------------------------------------------------+
                                       |
                                       v
          +----------------------------------------------------------+
          |       Topical Authority & Cannibalization Engine         |
          |   (Louvain Graph Clustering + Cosine Distance Thresh)    |
          +----------------------------------------------------------+
```

### Mekanisme Internal:
1. **Bi-Encoder vs Cross-Encoder**: Bi-Encoder mengompresi query dan dokumen ke dalam vektor berdimensi tetap secara independen ($E_q = f(q)$, $E_d = g(d)$) untuk komputasi cepat via HNSW ($O(\log N)$). Cross-Encoder mengalirkan query dan dokumen secara bersamaan ke dalam self-attention layer ($S = \text{Transformer}([q; [SEP]; d])$) untuk menangkap interaksi penuh antar-token, menghasilkan akurasi intent relevansi tinggi dengan biaya latensi lebih besar ($O(N)$).
2. **Hybrid Search via Reciprocal Rank Fusion (RRF)**:
   $$RRF\_Score(d \in D) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
   Di mana $M$ adalah sistem retrieval (BM25 dan Dense HNSW), $r_m(d)$ adalah ranking dokumen $d$ pada sistem $m$, dan $k$ adalah konstanta perataan (biasanya $k=60$).
3. **Graph-based Topic Clustering**: Mengonstruksi adjacency matrix $A$ berdasarkan *cosine similarity* antar-vektor keyword. Bobot edge $w_{ij}$ hanya dipertahankan jika $w_{ij} > \tau$ (threshold semantik, misal 0.78). Algoritma Louvain kemudian memaksimalkan fungsi *modularity* $Q$:
   $$Q = \frac{1}{2m} \sum_{i,j} \left[ w_{ij} - \frac{k_i k_j}{2m} \right] \delta(c_i, c_j)$$
   Langkah ini membagi keyword universe ke dalam *Topical Hubs* dan *Spoke Pages* secara matematis tanpa campur tangan manual.

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal?
* **Lexical Mismatch Problem**: Mesin pencari memahami sinonim dan relasi kontekstual. Halaman yang menargetkan "cara memperbaiki mobil mogok" tidak akan muncul jika mesin pencari mendeteksi intent pengguna lebih cocok dengan entitas "jasa derek darurat terdekat", meskipun kepadatan kata kunci (*keyword density*) tinggi.
* **Keyword Cannibalization**: Ketika sebuah domain memiliki puluhan artikel dengan kemiripan semantik tinggi, otoritas halaman terfragmentasi. Google membagi skor sinyal relevansi ke banyak URL, menyebabkan anjloknya posisi ranking untuk semua halaman terkait.
* **Search Intent Shift**: Intent query dapat bergeser dari Informasional ke Transaksional secara musiman atau akibat tren makro. Arsitektur statis gagal merespons perubahan SERP layout (misal: kemunculan Google SGE / AI Overviews).

### Solusi Arsitektur Modern
Membangun platform autonomous yang secara berkelanjutan:
* Mengelompokkan kata kunci ke dalam topik entitas terpadu.
* Menetapkan satu URL kanonikal otoritatif untuk setiap cluster semantik.
* Mengotomatisasi injeksi struktur semantik (*JSON-LD Knowledge Graphs*) untuk memvalidasi pemahaman web crawler terhadap entitas halaman.

---

## 5. How: Workflow Detail

```
+---------------------------------------------------------------------------------------+
| PHASE 1: INGESTION & ENRICHMENT                                                       |
| 1. Stream query log & Google Search Console API via Apache Kafka.                    |
| 2. Ekstrak metadata: Clicks, Impressions, CTR, Current Average Position.             |
| 3. Normalisasi teks & deduplikasi leksikal (MinHash LSH).                            |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| PHASE 2: VECTORIZATION & INTENT CLASSIFICATION                                        |
| 1. Generate dense vectors menggunakan model Embedding bertenaga GPU.                  |
| 2. Inferensi multi-intent: Transactional, Commercial, Informational, Navigational.    |
| 3. Simpan payload vektor & intent ke Qdrant Vector DB dengan payload indexing.       |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| PHASE 3: GRAPH CLUSTERING & CANNIBALIZATION DETECTION                                 |
| 1. Query k-NN graph dari ruang vektor (threshold similarity >= 0.80).                  |
| 2. Jalankan Louvain Community Detection untuk membentuk Parent Clusters (Hubs).       |
| 3. Evaluasi konflik URL: Jika 2+ URL bersaing dalam 1 cluster dengan intent sama,     |
|    tandai sebagai CANNIBALIZATION_ALERT.                                              |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| PHASE 4: SCHEMA GRAPH SYNTHESIS & EDGE DELIVERY                                       |
| 1. Ekstrak named entities (NER) & sambungkan ke Wikidata Entity IDs (QIDs).          |
| 2. Susun JSON-LD `@graph` hierarkis (WebSite -> WebPage -> About -> Mentions).       |
| 3. Cache payload schema di Redis; distribusikan ke Edge CDN via Edge Workers.         |
+---------------------------------------------------------------------------------------+
```

---

## 6. Analogy & Diagram ASCII

### Analogi
Bayangkan perpustakaan konvensional yang menyusun buku berdasarkan urutan abjad judul (Leksikal). Jika Anda mencari "buku tentang metode menyembuhkan sakit kepala", Anda harus memeriksa rak "B", "C", "M", dan "S". 

Arsitektur Semantik modern adalah **Kepala Kurator Bertenaga AI**:
1. Menaruh semua buku di ruang multidimensi berdasarkan makna konseptualnya (Vektor).
2. Menghubungkan buku dengan tali tak terlihat ke topik induk, penulis, dan bidang studi terkait (Knowledge Graph).
3. Mengarahkan Anda ke satu bagian khusus di mana semua buku saling melengkapi tanpa duplikasi isi (Louvain Topic Clusters).

### Diagram Alur Data Engine Semantik

```
               [ User Search Queries / GSC Data ]
                               |
                               v
                     [ Fast Ingest API ]
                               |
            +------------------+------------------+
            |                                     |
            v                                     v
   [ Sparse Processing ]                [ Dense Embedding ]
   (BM25 / SPLADE Terms)               (bge-large / 1024-dim)
            |                                     |
            +------------------+------------------+
                               |
                               v
                  [ Qdrant Hybrid Storage ]
                               |
             +-----------------+-----------------+
             |                                   |
             v                                   v
  [ Graph Community Module ]           [ Intent Analysis Module ]
   - K-NN Graph Builder                 - Zero-Shot Classifier
   - Louvain Clustering                 - Intent Classifier Matrix
             |                                   |
             +-----------------+-----------------+
                               |
                               v
             [ Semantic Architecture Controller ]
                               |
       +-----------------------+-----------------------+
       |                                               |
       v                                               v
[ 301 Redirect / Canonical Engine ]         [ Dynamic JSON-LD Graph ]
(Resolusi Kanibalisasi Otomatis)           (Edge Injection Engine)
```

---

## 7. Implementation: Practical Examples

Berikut adalah pipeline produksi Python modular untuk Intent Scoring, Semantic Clustering, Deteksi Kanibalisasi, dan Dynamic Schema Generation.

### 7.1 Setup Dependencies

```bash
pip install pydantic sentence-transformers qdrant-client networkx scikit-learn numpy torch
```

### 7.2 Core Production Code

```python
"""
production_semantic_seo_engine.py
Arsitektur Produksi untuk Search Intent Classification, Semantic Clustering,
dan Resolusi Kanibalisasi Kata Kunci.
"""

from typing import List, Dict, Any, Tuple
import numpy as np
import networkx as nx
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer, util
from sklearn.metrics.pairwise import cosine_similarity
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SemanticSEOEngine")


class KeywordNode(BaseModel):
    keyword: str
    target_url: str
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    current_position: float = Field(ge=1.0)


class IntentScore(BaseModel):
    informational: float
    commercial: float
    transactional: float
    navigational: float
    primary_intent: str


class ClusterResult(BaseModel):
    cluster_id: int
    hub_keyword: str
    spokes: List[str]
    urls_involved: List[str]
    has_cannibalization: bool


class SemanticEngine:
    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5"):
        logger.info(f"Menginisialisasi model transformer: {model_name}")
        self.encoder = SentenceTransformer(model_name)
        
        # Candidate labels untuk Zero-Shot Intent Classification
        self.intent_labels = [
            "how to guide information explanation tutorial",       # Informational
            "best top review compare vs evaluation",               # Commercial
            "buy order price discount shop checkout coupon",       # Transactional
            "login official site portal brand website home page"  # Navigational
        ]
        self.intent_keys = ["informational", "commercial", "transactional", "navigational"]
        self.intent_vectors = self.encoder.encode(self.intent_labels, normalize_embeddings=True)

    def classify_intent(self, keywords: List[str]) -> List[IntentScore]:
        """
        Klasifikasi Search Intent menggunakan cosine similarity terakselerasi vektor.
        """
        kw_embeddings = self.encoder.encode(keywords, normalize_embeddings=True)
        similarity_matrix = np.dot(kw_embeddings, self.intent_vectors.T)
        
        results = []
        for i, row in enumerate(similarity_matrix):
            # Softmax normalization untuk distribusi probabilitas
            exp_scores = np.exp(row - np.max(row))
            probs = exp_scores / exp_scores.sum()
            
            best_idx = int(np.argmax(probs))
            results.append(
                IntentScore(
                    informational=float(probs[0]),
                    commercial=float(probs[1]),
                    transactional=float(probs[2]),
                    navigational=float(probs[3]),
                    primary_intent=self.intent_keys[best_idx]
                )
            )
        return results

    def build_topic_clusters(
        self, nodes: List[KeywordNode], similarity_threshold: float = 0.78
    ) -> List[ClusterResult]:
        """
        Membangun Topic Clusters menggunakan K-NN Semantic Graph dan Louvain Community Detection.
        Mendeteksi kanibalisasi jika satu cluster memiliki multi-URL aktif.
        """
        keywords = [node.keyword for node in nodes]
        embeddings = self.encoder.encode(keywords, normalize_embeddings=True)
        
        # Hitung pairwise cosine similarity
        sim_matrix = cosine_similarity(embeddings)
        
        # Bangun graf tak berarah
        G = nx.Graph()
        for idx, node in enumerate(nodes):
            G.add_node(idx, data=node)

        num_nodes = len(nodes)
        for i in range(num_nodes):
            for j in range(i + 1, num_nodes):
                sim = sim_matrix[i][j]
                if sim >= similarity_threshold:
                    G.add_edge(i, j, weight=sim)

        # Louvain Community Detection
        communities = nx.community.louvain_communities(G, weight="weight", seed=42)
        
        clusters: List[ClusterResult] = []
        for c_id, community in enumerate(communities):
            indices = list(community)
            community_nodes = [nodes[i] for i in indices]
            
            # Tentukan Hub Keyword (node dengan bobot impresi tertinggi)
            hub_node = max(community_nodes, key=lambda x: x.impressions)
            spoke_kws = [node.keyword for node in community_nodes if node.keyword != hub_node.keyword]
            
            unique_urls = list(set(node.target_url for node in community_nodes))
            is_cannibalized = len(unique_urls) > 1

            clusters.append(
                ClusterResult(
                    cluster_id=c_id,
                    hub_keyword=hub_node.keyword,
                    spokes=spoke_kws,
                    urls_involved=unique_urls,
                    has_cannibalization=is_cannibalized
                )
            )
        
        return clusters

    @staticmethod
    def generate_schema_graph(
        page_url: str,
        page_title: str,
        about_entities: List[Dict[str, str]]
    ) -> str:
        """
        Menghasilkan dynamic connected JSON-LD Schema Graph.
        """
        schema_graph = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebSite",
                    "@id": f"{page_url}#website",
                    "url": page_url.split("/")[0] + "//" + page_url.split("/")[2],
                    "name": "Enterprise SEO Engine"
                },
                {
                    "@type": "WebPage",
                    "@id": f"{page_url}#webpage",
                    "url": page_url,
                    "name": page_title,
                    "isPartOf": {"@id": f"{page_url}#website"},
                    "about": [
                        {
                            "@type": "Thing",
                            "name": entity["name"],
                            "sameAs": entity["wikidata_url"]
                        } for entity in about_entities
                    ]
                }
            ]
        }
        return json.dumps(schema_graph, indent=2)


if __name__ == "__main__":
    # Inisialisasi Engine
    engine = SemanticEngine()

    # Data masukan simulasi dari Google Search Console API
    sample_nodes = [
        KeywordNode(keyword="best enterprise crm software", target_url="https://domain.com/crm", impressions=5000, clicks=120, current_position=4.2),
        KeywordNode(keyword="enterprise crm solutions comparison", target_url="https://domain.com/crm-tools", impressions=2400, clicks=45, current_position=8.1),
        KeywordNode(keyword="how to install open source crm", target_url="https://domain.com/blog/install-crm", impressions=1500, clicks=200, current_position=2.0),
        KeywordNode(keyword="crm pricing plans enterprise", target_url="https://domain.com/crm", impressions=3100, clicks=90, current_position=5.0),
        KeywordNode(keyword="what is a crm system guide", target_url="https://domain.com/blog/crm-guide", impressions=8000, clicks=650, current_position=1.5),
    ]

    # Eksekusi Klasifikasi Intent
    keywords = [n.keyword for n in sample_nodes]
    logger.info("Menjalankan Klasifikasi Intent...")
    intents = engine.classify_intent(keywords)
    for kw, intent in zip(keywords, intents):
        print(f"Keyword: '{kw}' | Primary: {intent.primary_intent.upper()} (Scores: I={intent.informational:.2f}, C={intent.commercial:.2f}, T={intent.transactional:.2f})")

    # Eksekusi Topic Clustering & Deteksi Kanibalisasi
    logger.info("Menjalankan Topic Clustering & Cannibalization Analysis...")
    clusters = engine.build_topic_clusters(sample_nodes, similarity_threshold=0.72)
    for c in clusters:
        print(f"\n--- Cluster ID: {c.cluster_id} ---")
        print(f"Hub Keyword: {c.hub_keyword}")
        print(f"Spokes: {c.spokes}")
        print(f"Involved URLs: {c.urls_involved}")
        print(f"Cannibalization Alert: {'[!] YA (Potensi Kanibalisasi)' if c.has_cannibalization else '[OK] Tidak Ada'}")

    # Eksekusi Dynamic Schema JSON-LD Generation
    logger.info("Menghasilkan Entity-Connected JSON-LD Schema...")
    schema = engine.generate_schema_graph(
        page_url="https://domain.com/crm",
        page_title="Enterprise CRM Software Solutions",
        about_entities=[
            {"name": "Customer Relationship Management", "wikidata_url": "https://www.wikidata.org/wiki/Q176046"},
            {"name": "Enterprise Software", "wikidata_url": "https://www.wikidata.org/wiki/Q1144415"}
        ]
    )
    print("\nGenerated Schema.org Graph:\n", schema)
```

---

## 8. Real World Case Study: E-Commerce Multinasional (Skala Enterprise)

### Profil Kasus
* **Entitas**: Platform E-Commerce Fashion & Elektronik (12 Juta SKU, 1.8 Juta Kategori Halaman).
* **Kendala**: Mengalami penurunan impresi organik sebesar 38% setelah rilis sistem dynamic taxonomy. Terjadi kanibalisasi masif: ratusan tag pages, filter pages, dan halaman kategori berebut 1 target SERP yang sama (contoh: `/shoes/running`, `/men/running-shoes`, `/tag/marathon-shoes`).

### Solusi Arsitektur
1. **Pipeline Ekstraksi & Clustering Batch**:
   * Dijalankan pada Apache Spark cluster untuk menghitung dense embeddings dari 20 juta query/keyword Search Console.
   * Vektor dipetakan ke Qdrant menggunakan HNSW index (`m=32, ef_construct=256`).
2. **Dynamic Semantic Canonical Controller**:
   * Menghitung nilai *Page Semantic Rank* $PSR = \text{Clicks} \times \text{CTR} \times (1 / \text{Position})$.
   * URL dengan PSR tertinggi dalam cluster semantik langsung ditetapkan sebagai master kanonikal.
   * Sisanya secara otomatis di-injeksi HTTP header `Link: <...>; rel="canonical"` atau dialihkan via edge redirect HTTP 301.
3. **Hasil Metrik Produksi (Setelah 90 Hari)**:
   * **Crawl Efficiency**: Penghematan Googlebot Crawl Budget sebesar 47% (menghilangkan crawl loop pada varian halaman redundan).
   * **SERP Positions**: 74% halaman kategori naik ke posisi Top 3 (sebelumnya terdistribusi di peringkat 11–25).
   * **Organic Revenue**: Peningkatan Gross Merchandise Value (GMV) dari trafik organik sebesar 26.4%.

---

## 9. Trade-offs: Architectural Decision Matrix

| Dimensi Arsitektur | Pendekatan A: Sparse / Rule-Based (BM25 + RegEx) | Pendekatan B: Pure Dense Vectors (Bi-Encoder HNSW) | Pendekatan C: Hybrid + Cross-Encoder Rerank (Pilihan Arsitektur Modul) |
| :--- | :--- | :--- | :--- |
| **Latensi Query** | **Ultra Rendah** ($< 5\text{ ms}$) | **Rendah** ($15 - 30\text{ ms}$) | **Tinggi - Menengah** ($80 - 150\text{ ms}$) |
| **Biaya Komputasi (Hardware)** | **Sangat Murah** (CPU based, RAM rendah) | **Sedang** (Memori besar untuk RAM HNSW) | **Tinggi** (GPU untuk batch inference reranking) |
| **Akurasi Intent Retrieval** | **Rendah** (Rentan *vocabulary mismatch*) | **Tinggi** (Menangkap makna abstrak) | **Sangat Tinggi** (Memadukan presisi leksikal + konteks dalam) |
| **Skalabilitas Graph Clustering** | Tidak Aplikabel | Cepat ($O(N \log N)$), risiko over-clustering | Terkontrol via dynamic similarity thresholding |
| **Risiko Halusinasi Entitas** | 0% | Sedang (Embedding drift) | Minimal (Diverifikasi Knowledge Graph QID) |

---

## 10. Common Mistakes & Troubleshooting

### 1. Semantic Drift pada Dynamic Thresholding
* **Gejala**: Cluster menggabungkan konsep yang berbeda (contoh: "apple watch straps" digabung ke "apple macbook pro" hanya karena sama-sama mengandung brand "apple").
* **Penyebab**: Menggunakan fixed threshold cosine similarity pada seluruh domain tanpa memperhitungkan magnitudo bobot token (IDF).
* **Solusi**: Terapkan *Normalized Discounted Cumulative Gain* pada bobot edge graf atau gunakan representasi multi-vektor (ColBERT) untuk query yang memiliki multi-entitas dominan.

### 2. Cannibalization False Positives
* **Gejala**: Halaman panduan produk (*Informational*) diidentifikasi kanibal dengan halaman checkout/katalog (*Transactional*) dan diarahkan secara keliru menggunakan redirect 301.
* **Penyebab**: Hanya menghitung similaritas teks tanpa memisahkan vektor intent.
* **Solusi**: Pisahkan matrix klasifikasi intent terlebih dahulu. Halaman hanya boleh dinyatakan kanibal jika:
  $$\text{CosineSimilarity}(E_{url1}, E_{url2}) > 0.85 \quad \land \quad \text{PrimaryIntent}(url_1) == \text{PrimaryIntent}(url_2)$$

### 3. Edge Latency Overhead saat Dynamic Injection
* **Gejala**: Time to First Byte (TTFB) meningkat $> 300\text{ ms}$ saat merender JSON-LD di Cloudflare Workers.
* **Penyebab**: Edge Worker memanggil database semantik terpusat secara sinkronus pada setiap request crawl.
* **Solusi**: Implementasikan asynchronous write dengan Redis Edge Cache (KV storage) dengan pola *stale-while-revalidate*. Payload JSON-LD disiapkan secara offline saat proses clustering.

---

## 11. Best Practices & Production Checklist

- [ ] **Embedding Cache**: Selalu simpan hash SHA-256 dari string query sebagai key di cache sebelum komputasi model dense embedding.
- [ ] **Dynamic Intent Matrix Validation**: Update berkala anchor training intent set minimal 1 bulan sekali untuk mengadaptasi perubahan intent SERP global.
- [ ] **Cross-Encoder Pruning**: Jangan pernah melakukan rerank ke seluruh database vektor ($N > 1000$). Gunakan Bi-Encoder HNSW untuk mengambil top-50 candidates, lalu gunakan Cross-Encoder hanya pada top-50 tersebut.
- [ ] **Wikidata QID Resolution**: Validasi status entitas melalui Wikidata SPARQL API guna memastikan URL entity reference tetap valid (*non-deprecated*).
- [ ] **Edge Fallback**: Jika worker semantik gagal merespons dalam batas SLA ($< 50\text{ ms}$), layani halaman web standar tanpa injeksi dinamis (*fail-open mechanism*).
- [ ] **Crawl Velocity Monitoring**: Pantau 5xx status code pada edge router setiap kali automasi redirect kanibalisasi dieksekusi secara massal.

---

## 12. Hands-on Practice

Simpan seluruh hasil latihan praktikum di direktori: `hands-on/m02/`

### File Structure:
```
hands-on/m02/
├── requirements.txt
├── config.py
├── core/
│   ├── __init__.py
│   ├── classifier.py
│   └── clustering.py
└── main.py
```

### Langkah-langkah Praktikum:
1. **Setup Environment**:
   ```bash
   mkdir -p hands-on/m02/core
   cd hands-on/m02
   python3 -m venv venv
   source venv/bin/activate
   pip install sentence-transformers networkx scikit-learn pydantic
   ```
2. **Implementasi `hands-on/m02/core/classifier.py`**:
   Tulis kelas klasifikasi intent berbasis Zero-Shot dengan model `all-MiniLM-L6-v2` untuk konsumsi memori rendah pada workstation lokal.
3. **Implementasi `hands-on/m02/core/clustering.py`**:
   Tulis modul pembentukan graf keterhubungan kata kunci dengan output matrix cannibalization alert berbasis threshold input CLI.
4. **Jalankan Verifikasi Pipeline**:
   Eksekusi `main.py` dengan memasukkan 20 dataset keyword nyata dari industri Anda dan ekspor hasilnya ke format `output_clusters.json`.

---

## 13. Exercises

### Level Easy
Modifikasi fungsi `classify_intent` pada kode Python di Section 7 agar mampu mendeteksi intent kelima: `"Navigational - Local"` (misal: query yang mengandung "near me", nama kota, atau kode pos).

### Level Medium
Buat script integrasi async menggunakan `httpx` yang membaca 100 baris keyword dari file CSV secara concurrent (batch size = 16), memproses clustering, dan menghasilkan visualisasi graf menggunakan `matplotlib` yang disimpan ke format `.png`.

### Level Hard
Implementasikan skema optimasi memori: Ubah kalkulasi graf clustering Louvain dari representasi dense `numpy` matrix menjadi sparse CSR matrix (`scipy.sparse.csr_matrix`). Algoritma harus mampu memproses graf berisi minimal $100.000$ kata kunci tanpa melebihi batas memori 4 GB RAM.

---

## 14. Enterprise Challenge (Production Scenario)

### Skenario:
Sistem multi-brand e-commerce Anda memiliki 5 sub-domain regional (ID, SG, MY, TH, VN). Database Search Console mencatat 1.200.000 kombinasi query pencarian yang tumpang tindih secara lintas bahasa (Cross-Lingual Cannibalization).

### Spesifikasi Kebutuhan:
1. Rancang arsitektur sistem (dalam bentuk dokumen arsitektur dan spesifikasi modul teknis) yang memanfaatkan model embedding multi-bahasa (`paraphrase-multilingual-mpnet-base-v2` atau setara).
2. Sistem harus mendeteksi secara otomatis ketika konten bahasa Inggris di domain SG mengkanibal intent lokal domain ID untuk query berbahasa Inggris.
3. Rancang protokol orkestrasi HTTP Hreflang Tags dinamis yang diinjeksi via edge CDN untuk memetakan otoritas bahasa dan region secara presisi.
4. Latensi maksimal pipeline pemrosesan batch mingguan untuk 1.2M keywords adalah 4 jam menggunakan single multi-GPU instance (Nvidia A10G/T4).

---

## 15. Evaluasi Pemahaman

### 15.1 Basic (Pilihan Ganda / Konseptual)
1. Apa perbedaan mendasar antara model retrieval sparse (BM25) dan dense vector dalam konteks search intent?
2. Mengapa metrik Cosine Similarity lebih disukai dibanding Euclidean Distance saat membandingkan dense text embeddings?
3. Sebutkan 4 kategori utama Google Search Intent beserta karakteristik umumnya!
4. Apa fungsi konstanta $k$ pada formula Reciprocal Rank Fusion (RRF)?
5. Mengapa tag `canonical` lebih direkomendasikan daripada redirect 301 untuk varian produk e-commerce dengan perbedaan atribut minor?

### 15.2 Intermediate (Teknis & Algoritma)
6. Bagaimana algoritma Louvain Community Detection menentukan batas sebuah cluster topik tanpa parameter jumlah cluster ($K$) yang ditentukan di awal?
7. Mengapa Cross-Encoder tidak praktis digunakan untuk tahap initial retrieval pada korpus 10 juta URL?
8. Bagaimana cara memitigasi risiko kanibalisasi semantik tanpa menghapus halaman konten lama yang masih menghasilkan revenue sekunder?
9. Jelaskan peran JSON-LD property `sameAs` dalam entity disambiguation di Google Knowledge Graph!
10. Pada metrik evaluasi IR, apa arti penurunan nilai NDCG@10 sementara nilai Precision@10 tetap konstan?

### 15.3 Skenario Kasus Produksi
11. **Skenario A**: Tim editorial mempublikasikan 50 artikel baru per minggu. Dalam 3 bulan, performa organik URL utama anjlok drastis. Setelah dicek, tim editorial menulis artikel dengan variasi keyword yang secara semantik 90% identik dengan URL utama. Rancang *Pre-Publish Semantic Gate API* untuk memblokir CMS mempublikasikan konten yang kanibal!
12. **Skenario B**: Sistem vector cluster Anda mengelompokkan query "beli iphone 15" dan "review kelemahan baterai iphone 15" ke dalam 1 cluster yang sama karena similarity-nya mencapai 0.88. Hal ini membuat halaman transaksional dioptimasi untuk query komparasi. Bagaimana formula filtering matematika Anda untuk memecah cluster ini?
13. **Skenario C**: Edge Worker yang menyuntikkan schema JSON-LD ke Googlebot mengalami lonjakan latensi menjadi 1200 ms karena overload pada redis backend cluster. Googlebot mulai meninggalkan antrian crawling (penurunan crawl rate drastis). Tuliskan pseudocode *fail-open circuit breaker pattern* pada edge runtime untuk mengatasi krisis ini!

---

## 16. Summary

* **Semantik vs Leksikal**: Arsitektur modern beroperasi di ruang pemahaman konsep dan entitas, bukan pencocokan string statis.
* **Hybrid Retrieval**: Kombinasi Dense Search (konseptual) dan Sparse Search (kata kunci spesifik/brand) yang disatukan via RRF adalah standar emas retrieval industri modern.
* **Topic Graph Clustered Architecture**: Mengelompokkan kata kunci menggunakan algoritma Louvain memastikan setiap halaman web bertindak sebagai otoritas independen (*Hub-and-Spoke model*), menghapus risiko fragmentasi peringkat (*cannibalization*).
* **Automasi Edge & Graph Schema**: Validasi identitas halaman web ke Knowledge Graph eksternal (Wikidata/Google KG) melalui dynamic JSON-LD injection di Edge CDN memberikan kepastian interpretasi bagi search engine bot dengan performa latensi tinggi.