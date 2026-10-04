# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Topik: Redis (04-Backend-and-Database)
### Bab 10: Ekosistem Redis Modern (Probabilistik, Vector Search, & JSON)
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Principal Engineer/Lead Architect diharapkan mampu:
- **Menganalisis dan Memilih Struktur Probabilistik**: Menentukan kapan menggunakan Bloom Filter, Cuckoo Filter, Count-Min Sketch, Top-K, HyperLogLog, dan t-digest berdasarkan karakteristik *error rate*, mutabilitas data, dan batasan memori.
- **Mengarsiteki Mesin Pencarian Vektor Berlatensi Rendah**: Mengimplementasikan pengindeksan vektor HNSW (*Hierarchical Navigable Small World*) dan Flat Indexing pada RediSearch untuk kebutuhan *Retrieval-Augmented Generation* (RAG) dan *similarity search* skala miliaran item.
- **Mengoptimalkan Mutasi Dokumen JSON Kompleks**: Memanfaatkan RedisJSON v2.0+ untuk manipulasi granular (*in-place atomic mutations*) tanpa overhead serialisasi/deserialisasi penuh pada aplikasi.
- **Mendesain Arsitektur Hybrid Terdistribusi**: Mengonfigurasi topologi Redis Stack Enterprise/Cluster berdaya tahan tinggi dengan mempertimbangkan implikasi sharding lintas-node pada *multi-key commands* dan *secondary indexing*.
- **Mengeksekusi Diagnostic & Troubleshooting Tingkat Lanjut**: Mengatasi masalah fragmentasi memori, degradasi latensi HNSW graph build, serta saturasi thread I/O pada Redis Engine.

---

### 2. Prerequisite
Untuk menyerap materi ini secara optimal, peserta wajib memahami:
- Arsitektur Event-Loop Redis (Single-Threaded Command Execution Core vs Bio Threads & I/O Threads).
- Struktur data fundamental Redis (String, Hash, Set, Sorted Set, Bitmaps).
- Aljabar Linier Dasar (Metrik Jarak Vektor: Euclidean/L2, Inner Product/IP, Cosine Similarity).
- Teori Probabilitas Dasar (False Positive Probability, Hash Collision, Hashing Functions seperti MurmurHash3 dan xxHash).
- Bahasa Pemrograman: Python 3.11+ atau Go 1.22+ untuk implementasi client-side driver.

---

### 3. Concept & Internal Architecture (Mendalam)

```
+-------------------------------------------------------------------------------+
|                           REDIS CORE RUNTIME ENGINE                           |
|                                                                               |
|  +-------------------------------------------------------------------------+  |
|  |                        Redis Module System (RMS) API                    |  |
|  +-------------------+--------------------+-------------------+------------+  |
|                      |                    |                   |               |
|                      v                    v                   v               |
|            +-----------------+    +-----------------+  +-----------------+    |
|            |  RedisJSON v2+  |    |  RediSearch v2+ |  |  RedisBloom     |    |
|            +-----------------+    +-----------------+  +-----------------+    |
|            | V8-like JSON    |    | Inverted Index  |  | Bloom / Cuckoo  |    |
|            | Path Engine     |    | Vector Engines: |  | Count-Min Sketch|    |
|            |                 |    | - FLAT (Brute)  |  | Top-K / TDigest |    |
|            | Memory-Optimized|    | - HNSW (Graph)  |  | Bit-slicing     |    |
|            | Tree Node Alloc |    | Numeric/Tag Trie|  | Fingerprints    |    |
|            +--------+--------+    +--------+--------+  +--------+--------+    |
|                     |                      |                    |             |
|                     +----------------------+--------------------+             |
|                                            |                                  |
|                                            v                                  |
|                      +------------------------------------------+             |
|                      |    Jemalloc Unified Memory Allocator     |             |
|                      +------------------------------------------+             |
+-------------------------------------------------------------------------------+
```

#### A. RedisJSON Internals
RedisJSON tidak menyimpan data sebagai string JSON mentah. Di balik layar, modul ini mem-parsing payload JSON ke dalam struktur pohon *hierarchical typed node* menggunakan alokasi memori dinamis yang dikelola via custom allocator. 
- Setiap node menyimpan tipe data (`JSON_OBJECT`, `JSON_ARRAY`, `JSON_STRING`, `JSON_INTEGER`, dll.).
- Navigasi path dijalankan menggunakan parser JSONPath yang dikompilasi sebelumnya. Mutasi parsial melalui `JSON.SET key $.user.profile.age 30` hanya memodifikasi blok memori node integer target secara *in-place*, tanpa mengeksekusi *parse-and-serialize* keseluruhan objek. Ini mereduksi kompleksitas CPU dari $O(N)$ ukuran JSON menjadi $O(M)$ kedalaman path.

#### B. RediSearch & Vector Indexing Architecture
RediSearch memisahkan data aktual dari struktur indeks sekunder. Indeks vektor memanfaatkan modul memori native untuk membangun dua topologi:
1. **FLAT (Brute-Force Search)**: 
   - Menyimpan seluruh raw vector berdimensi $D$ dalam array contiguous memory.
   - Waktu komputasi pencarian bernilai $O(N \cdot D)$, di mana $N$ adalah jumlah dokumen.
   - Bersifat *lossless* (recall 100%), sangat cepat untuk dataset kecil ($N < 10.000$) atau ketika subset filtering menghasilkan kandidat yang sangat sempit.
2. **HNSW (Hierarchical Navigable Small World)**:
   - Membangun multi-layer graph di mana setiap layer beroperasi seperti *skip-list*.
   - Layer 0 berisi seluruh node; layer yang lebih tinggi memiliki node eksponensial lebih sedikit untuk *fast routing*.
   - Kompleksitas pencarian adalah $O(\log N \cdot D)$.
   - Parameter krusial internal:
     - `M`: Jumlah link/edge maksimum per node per layer. Nilai tinggi menaikkan recall dengan konsekuensi memori membesar.
     - `efConstruction`: Ukuran dynamic candidate list saat *index building*. Menentukan kualitas graf dengan trade-off durasi indexing.
     - `efRuntime`: Ukuran candidate list saat kueri pencarian. Memodulasi trade-off antara *latency* vs *recall*.

#### C. RedisBloom & Probabilistic Structures Internals
- **Bloom Filter**: Mengalokasikan array bit berukuran $m$ dan menggunakan $k$ fungsi hash independen. False Positive Probability ($p$) dirumuskan sebagai:
  $$p \approx \left(1 - e^{-kn/m}\right)^k$$
  RedisBloom mengimplementasikan *Scalable Bloom Filter*, yaitu menambah array bit baru berjenjang saat kapasitas $n$ terlampaui untuk mencegah degradasi nilai $p$. Operasi penghapusan (*deletion*) tidak didukung.
- **Cuckoo Filter**: Menggunakan tabel hash yang berisi *fingerprint* item (misal 1-2 byte). Memungkinkan operasi penghapusan item tanpa false negative. Menggunakan teknik *cuckoo hashing* dengan *partial-key cuckoo hashing* untuk relokasi elemen saat terjadi tabrakan (kicking).
- **Count-Min Sketch (CMS)**: Matriks 2D bertipe integer 32-bit ($d \times w$), di mana $w = \lceil e/\epsilon \rceil$ dan $d = \lceil \ln(1/\delta) \rceil$. Menyediakan estimasi frekuensi suatu event dengan jaminan batas error $\epsilon$ dan probabilitas kegagalan $\delta$.
- **t-digest**: Struktur data berbasis klaster dinamis untuk mengestimasi *quantile* (p95, p99, p99.9) secara akurat pada data stream berskala besar tanpa perlu menyimpan seluruh raw data points.

---

### 4. Why & What

| Modul / Struktur | Apa Masalah yang Diselesaikan? | Mengapa Tidak Menggunakan Struktur Tradisional? |
| :--- | :--- | :--- |
| **RedisJSON** | Kebutuhan manipulasi dokumen terstruktur dengan latensi sub-milidetik. | Hash konvensional tidak mendukung struktur bersarang (*nested arrays/objects*). Alternatif serialisasi string JSON via `SET` memboroskan CPU dan network I/O akibat full payload transfer. |
| **RediSearch (Vector)** | Kebutuhan retrieval semantik (*k-NN search*) real-time untuk RAG & RecSys. | Database relasional/NoSQL tradisional memerlukan serialisasi/deserialisasi lambat dan kueri eksternal ke dedicated vector DB menambah *network hop latency* (5-20ms vs <1ms di Redis). |
| **Bloom & Cuckoo Filter** | *Existence check* masif (URL blacklist, cache-penetration guard) dengan footprint memori sangat minim. | Menyimpan milyaran string ID di Redis `SET` membutuhkan puluhan gigabyte memori. Bloom/Cuckoo filter hanya memakan beberapa megabyte (penghematan >95%). |
| **Count-Min Sketch** | *Frequency tracking* aliran data masif (misal: rate limiting per IP). | Hash table konvensional (`HINCRBY`) mengalami *unbounded memory growth* saat cardinality jutaan keys unik. CMS memiliki ukuran memori konstan $O(1)$. |
| **t-digest** | Kalkulasi persentil latensi SLA secara streaming. | Menggunakan `ZSET` untuk tracking latensi memakan memori linear terhadap jumlah sample dan komputasi persentil berat ($O(\log N)$ memory ops). |

---

### 5. How (Workflow Detail)

#### Pipeline Arsitektur Integrasi Vektor & JSON
1. **Ingestion & Embedding Generation**:
   Aplikasi memproduksi teks, mengekstrak embedding via API model (misal: OpenAI `text-embedding-3-small` atau lokal HuggingFace), menghasilkan array `float32[]`.
2. **Atomic Ingestion to Redis**:
   Aplikasi mengeksekusi satu atomic command (atau pipeline):
   ```
   JSON.SET doc:1001 $ '{"title": "Arsitektur Enterprise", "embedding": [0.021, -0.432, ...], "tag": "database"}'
   ```
3. **Internal Indexing Pipeline**:
   Modul RediSearch secara asinkron (pada background indexer worker) mendeteksi mutasi pada key `doc:1001`, memvalidasi schema mapping, dan memperbarui:
   - Inverted index untuk field bertipe `TAG` atau `TEXT`.
   - Graf HNSW di mana vektor dinormalisasi dan disisipkan dengan mencari nearest neighbor di layer teratas hingga layer 0.
4. **Hybrid Query Resolution**:
   Saat mengeksekusi kueri `FT.SEARCH`:
   - RediSearch melakukan pre-filtering menggunakan Tag/Numeric index (menghasilkan bitmap ID).
   - Menjalankan HNSW vector traversal yang dibatasi hanya pada bitmap yang lolos pre-filter.
   - Mengembalikan dokumen JSON terproyeksi dalam sub-milidetik.

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
- **HNSW Vector Search vs FLAT**: FLAT seperti membaca setiap halaman buku di perpustakaan secara berurutan untuk mencari kata tertentu. HNSW seperti menggunakan indeks subjek hierarki (Lantai -> Lorong -> Rak -> Buku spesifik) yang langsung mengantarkan Anda ke target dengan probabilitas sangat tinggi.
- **Bloom Filter**: Seperti filter fisik penyaring kotoran. Jika batu besar lolos dari filter yang didesain untuk batu, sistem yakin 100% objek tersebut **bukan debu** (Zero False Negative). Namun, jika ada butiran kecil tertahan, ada kemungkinan kecil itu gumpalan debu yang menempel (False Positive).

#### Diagram Transisi Eksekusi Hybrid Vector Search

```
Incoming Request: Hybrid Vector Search (Filter: tag='fintech', Top-K: 3)
      |
      v
+---------------------------------------------------------------+
|                      RediSearch Engine                        |
|                                                               |
|  Step 1: Execute Tag Filtering (Bitmap Evaluation)            |
|  +---------------------------------------------------------+  |
|  | Inverted Index: tag == 'fintech'                        |  |
|  | Matched Document IDs: [doc:1, doc:4, doc:88, doc:104]   |  |
|  +----------------------------+----------------------------+  |
|                               |                               |
|                               v                               |
|  Step 2: Restricted HNSW Vector Traversal (Iterative Exploration)
|  +---------------------------------------------------------+  |
|  | Layer 2: Node 100 -----> Node 88 (Match filter!)        |  |
|  |                            |                               |
|  | Layer 1:                   v                               |
|  |                          Node 88 ---> Node 4 (Match!)      |
|  |                                         |                  |
|  | Layer 0:                                v                  |
|  |                                       Node 1 (Match!)      |
|  | Min-Heap Tracking: Closest Top 3 Candidates                |
|  +----------------------------+----------------------------+  |
|                               |                               |
|                               v                               |
|  Step 3: Document Retrieval via RedisJSON                     |
|  +---------------------------------------------------------+  |
|  | Extract JSON attributes from selected Keys                 |  |
|  +---------------------------------------------------------+  |
+-------------------------------+-------------------------------+
                                |
                                v
                Response Payload (Scores & Docs)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example (Redis CLI Scripting)
Menyiapkan Index JSON dan RediSearch HNSW:

```redis
-- 1. Membuat schema indeks pencarian untuk dokumen produk JSON
FT.CREATE idx:products ON JSON PREFIX 1 product: SCHEMA
  $.category AS category TAG
  $.price AS price NUMERIC
  $.description_vector AS vector VECTOR HNSW 6
    TYPE FLOAT32
    DIM 4
    DISTANCE_METRIC COSINE
    M 16
    EF_CONSTRUCTION 200

-- 2. Memasukkan dokumen JSON dengan embedded vector
JSON.SET product:101 $ '{"category":"hardware","price":150.50,"description_vector":[0.12, 0.88, -0.34, 0.45],"name":"Enterprise SSD"}'
JSON.SET product:102 $ '{"category":"hardware","price":89.99,"description_vector":[0.15, 0.85, -0.30, 0.40],"name":"Pro NVMe"}'

-- 3. Mengeksekusi pencarian kemiripan vektor dengan filter harga (Hybrid Query)
FT.SEARCH idx:products "(@category:{hardware} @price:[50 200])=>[KNN 2 @vector $query_vec AS score]" PARAMS 2 query_vec "\x71\x3d\x0a\x3e\xcd\xcc\x5c\x3f\x9a\x99\xae\xbe\xcd\xcc\xe6\x3e" SORTBY score ASC RETURN 2 name score DIALECT 2
```

#### B. Practical Example (Production-Ready Python Client)
Implementasi service terenkapsulasi menggunakan `redis-py` modern:

```python
import numpy as np
import redis
from redis.commands.search.field import NumericField, TagField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from typing import List, Dict, Any

class EnterpriseKnowledgeBase:
    INDEX_NAME = "idx:kb_v2"
    DOC_PREFIX = "kb:"
    VECTOR_DIM = 1536  # Standard text-embedding-3-small dim

    def __init__(self, host: str = "localhost", port: int = 6379, password: str = None):
        self.client = redis.Redis(
            host=host,
            port=port,
            password=password,
            decode_responses=False  # Required binary-safe for raw vector ingestion
        )
        self._ensure_index_exists()

    def _ensure_index_exists(self) -> None:
        try:
            self.client.ft(self.INDEX_NAME).info()
        except redis.ResponseError:
            # Definisi Skema HNSW Optimized for High Accuracy
            schema = (
                TagField("$.tenant_id", as_name="tenant_id"),
                TagField("$.classification", as_name="classification"),
                NumericField("$.created_at", as_name="created_at"),
                VectorField(
                    "$.embedding",
                    "HNSW",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.VECTOR_DIM,
                        "DISTANCE_METRIC": "COSINE",
                        "M": 40,
                        "EF_CONSTRUCTION": 250,
                        "EF_RUNTIME": 50,
                    },
                    as_name="vector"
                )
            )
            definition = IndexDefinition(prefix=[self.DOC_PREFIX], index_type=IndexType.JSON)
            self.client.ft(self.INDEX_NAME).create_index(schema, definition=definition)

    def insert_document(self, doc_id: str, tenant_id: str, classification: str, 
                        created_at: int, content: str, embedding: List[float]) -> None:
        key = f"{self.DOC_PREFIX}{doc_id}"
        vector_bytes = np.array(embedding, dtype=np.float32).tobytes()
        
        payload = {
            "tenant_id": tenant_id,
            "classification": classification,
            "created_at": created_at,
            "content": content,
            "embedding": embedding # Stored as array in JSON
        }
        
        pipeline = self.client.pipeline(transaction=True)
        pipeline.json().set(key, "$", payload)
        pipeline.execute()

    def hybrid_vector_search(self, tenant_id: str, query_embedding: List[float], 
                             top_k: int = 5) -> List[Dict[str, Any]]:
        query_bytes = np.array(query_embedding, dtype=np.float32).tobytes()
        
        # Pre-filter query syntax: strict tenant isolation
        base_query = f"(@tenant_id:{{{tenant_id}}})=>[KNN {top_k} @vector $query_vec AS vector_score]"
        
        q = (
            Query(base_query)
            .sort_by("vector_score", asc=True)
            .paging(0, top_k)
            .return_fields("vector_score", "$.content", "$.classification")
            .dialect(2)
        )
        
        params = {"query_vec": query_bytes}
        results = self.client.ft(self.INDEX_NAME).search(q, query_params=params)
        
        output = []
        for doc in results.docs:
            output.append({
                "doc_id": doc.id,
                "score": float(doc.vector_score),
                "classification": getattr(doc, "$.classification", None),
                "content": getattr(doc, "$.content", None)
            })
        return output
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Arsitektur E-Commerce Global Fraud & Similarity Engine
- **Volume Data**: 50 Juta User Profiles, 20.000 Transaksi per Detik (TPS).
- **Kebutuhan**: 
  1. *Immediate Duplicate / Attack Detection* (Mengecek apakah device fingerprint atau payment token sudah pernah terlihat dalam 30 hari).
  2. *Real-time Frequency Bounding* (Mencegah brute force via IP/Card velocity check).
  3. *Fraud Vector Similarity*: Memetakan vector profiling perilaku transaksi saat ini ke vector fraud patterns yang diketahui dalam waktu < 2 milidetik.

#### Solusi Topologi:
```
[Client Edge / API Gateway]
            |
            v
[Fraud Detection Orchestrator]
      |            |             |
(Cuckoo Filter) (CMS)     (RediSearch HNSW)
      |            |             |
      v            v             v
+----------------------------------------------------------------+
|                   REDIS STACK CLUSTER                          |
|                                                                |
|  Node Shard 1 .. N                                             |
|  - Cuckoo Filter: 50M fingerprints (Memory: ~64MB)             |
|    Command: CF.CHECK device_fingerprints <device_hash>         |
|                                                                |
|  - Count-Min Sketch: IP Velocity Tracking                      |
|    Command: CMS.INCRBY ip_velocity_sketch <ip_address> 1       |
|    Evaluation: IF count > THRESHOLD -> Block                   |
|                                                                |
|  - RedisJSON + RediSearch HNSW: Real-time Embeddings           |
|    Vector Dim: 256, Cosine Distance                            |
|    Command: FT.SEARCH idx:fraud_patterns ...                   |
+----------------------------------------------------------------+
```

#### Metrik Dampak Produksi:
- **Reduksi Memori**: Menggantikan Redis `SET` untuk 50 juta token perangkat dari 4.8 GB menjadi 68 MB menggunakan Cuckoo Filter.
- **Latensi**: Transversal pencarian fraud vector selesai dalam 1.2ms (p99) menggunakan index HNSW ($M=32, efRuntime=40$).
- **Throughput**: Cluster 6 node (3 master, 3 replica) berhasil melayani 35.000 Ops/sec pada 40% CPU utilization.

---

### 9. Trade-offs

| Dimensi | Opsi A | Opsi B | Analisis Trade-off Arsitektur |
| :--- | :--- | :--- | :--- |
| **Vector Index Type** | **HNSW** | **FLAT** | **HNSW**: Menawarkan search latency $O(\log N)$ yang sangat cepat, namun memakan overhead memori tambahan 1.5x - 2.5x untuk graf, serta durasi indexing tinggi. Cocok untuk search real-time.<br>**FLAT**: Tanpa indexing overhead dan memori graf 0 byte. Akan tetapi, komputasi linear $O(N)$ menyebabkan CPU spike masif pada scale $>50.000$ item. Cocok untuk dataset terisolasi per tenant kecil. |
| **Probabilistic Deduplication** | **Bloom Filter** | **Cuckoo Filter** | **Bloom**: Efisiensi bit tertinggi, throughput penulisan sangat tinggi, namun tidak bisa menghapus item individual.<br>**Cuckoo**: Mendukung mutasi `DELETE` dan false positive rate stabil pada kapasitas tinggi, namun throughput penulisan terdegradasi saat kapasitas mendekati 95% (kicking loops). |
| **Frequency Estimation** | **Count-Min Sketch** | **Redis Sorted Set (ZSET)** | **CMS**: Memori flat dan fixed (misal: 100KB untuk milyaran event), namun mengorbankan akurasi (terdapat *overestimation* probabilitas tinggi akibat hash collision).<br>**ZSET**: Akurasi 100% dan mutasi presisi, namun *unbounded memory growth* ($O(N)$) yang memicu OOM pada production. |
| **Document State Storage** | **RedisJSON** | **Protobuf / MessagePack di String** | **RedisJSON**: Memungkinkan mutasi in-place parsial via path dan query sekunder via RediSearch, namun memakan alokasi memori heap internal lebih besar.<br>**Binary Serialization**: Footprint memori terminimalisasi secara drastis, namun setiap update 1 byte memerlukan transfer dan serialisasi ulang seluruh payload oleh aplikasi client. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Out-of-Memory (OOM) Akibat HNSW Graph Bloat
- **Gejala**: Memori Redis melonjak drastis melebihi estimasi ukuran raw vectors.
- **Penyebab**: Menyetel parameter `M` terlalu besar (misal: $M = 64$ atau $128$) pada dimensi vektor tinggi ($D = 1536$). Setiap node menyimpan hingga $M$ pointer per layer.
- **Mitigasi**: Kurangi $M$ ke rentang $16 \le M \le 32$. Turunkan dimensionalitas vektor via teknik PCA/Matryoshka Embeddings jika memungkinkan.

#### 2. Scalable Bloom Filter Memory Leaks
- **Gejala**: Filter Bloom bertambah ukurannya secara eksponensial dan response time `BF.EXISTS` melonjak bertahap.
- **Penyebab**: Tidak menentukan `NONSCALING` saat pembuatan filter, sementara data yang masuk melebihi kapasitas awal hingga puluhan kali lipat. RedisBloom membuat sub-filter baru secara berantai, memaksa evaluasi $k$ hash function dikalikan jumlah sub-filter.
- **Mitigasi**: Tentukan `capacity` awal mendekati batas atas skala produksi (misal: $1.5 \times \text{proyeksi 1 tahun}$) dan gunakan rotasi time-based filter (misal: daily/weekly bloom).

#### 3. Latency Spike Akibat Missing Coordinate System Normalization
- **Gejala**: RediSearch mengembalikan hasil dengan skor jarak ngawur saat menggunakan `COSINE` distance metric.
- **Penyebab**: Vektor yang di-insert tidak dinormalisasi ke *unit length* ($||v|| = 1$), sementara RediSearch mengasumsikan perhitungan dot product optimal untuk normalized vectors pada cosine distance.
- **Mitigasi**: Lakukan normalisasi L2 pada client-side sebelum mengubah array float menjadi bytes:
  ```python
  norm = np.linalg.norm(vec)
  normalized_vec = vec if norm == 0 else vec / norm
  ```

#### 4. Diagnostic Toolkit
Untuk memeriksa kesehatan memori indeks dan performa eksekusi kueri, jalankan:
```redis
-- Mengecek status indeks, jumlah record terindeks, dan footprint memori RediSearch
FT.INFO idx:products

-- Menganalisis alokasi detail struktur memori Redis
MEMORY USAGE product:101 SAMPLES 0

-- Mengukur eksekusi query search secara bertahap (ekivalen EXPLAIN ANALYZE)
FT.PROFILE idx:products SEARCH QUERY "(@category:{hardware})=>[KNN 5 @vector $vec]" PARAMS 2 vec "..."
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Konfigurasi Memory Allocator**: Pastikan Redis dikompilasi menggunakan `jemalloc` (bukan standard `glibc malloc`) untuk meminimalkan fragmentasi memori akibat alokasi granular pada RedisJSON.
- [ ] **Threaded I/O Configuration**: Aktifkan `io-threads 4` (atau sesuai vCPU) pada `redis.conf` untuk memparalelkan proses pembacaan socket payload vektor yang berukuran besar.
- [ ] **Cluster Cross-Slot Mitigation**: Saat mendesain struktur keys RediSearch pada mode Redis Cluster, gunakan Hash Tags secara hati-hati:
  `doc:{tenant_123}:item_001`. Catatan: RediSearch v2 Enterprise menangani pencarian terdistribusi dengan mengirim sub-queries ke seluruh shards (scatter-gather architecture).
- [ ] **Penyetelan `efRuntime` Dinamis**: Jangan set `EF_RUNTIME` tinggi di skema permanen. Kirim via parameter query `FT.SEARCH ... PARAMS 2 ef_runtime 40` untuk menyesuaikan latensi vs akurasi secara adaptif berdasarkan traffic SLA.
- [ ] **Persistensi Engine (RDB/AOF)**: Hindari `save ""` murni jika menggunakan Vector Search. Rekonstruksi graf HNSW dari AOF saat startup memakan waktu CPU berjam-jam (*slow boot*). Gunakan Snapshotting RDB dengan `bgsave` yang terjadwal rapi untuk *fast restore*.
- [ ] **Vector Dimension Validation**: Kunci aplikasi client agar memvalidasi panjang array embedding secara strict sebelum serialization. Runtime rejection dari Redis membuang-buang siklus network roundtrip.

---

### 12. Hands-on Practice

Buat direktori dan berkas implementasi di: `hands-on/m02/`

#### File: `hands-on/m02/docker-compose.yml`
```yaml
version: '3.8'
services:
  redis-stack:
    image: redis/redis-stack-server:7.2.0-v10
    container_name: redis-modern-enterprise
    ports:
      - "6379:6379"
    environment:
      - REDIS_ARGS=--maxmemory 2gb --maxmemory-policy volatile-lru --save 900 1
    volumes:
      - redis_data:/data
volumes:
  redis_data:
```

#### File: `hands-on/m02/requirements.txt`
```
redis==5.0.3
numpy==1.26.4
```

#### File: `hands-on/m02/verify_stack.py`
Jalankan skrip ini untuk memverifikasi pipeline RedisJSON, HNSW Vector Indexing, dan Bloom Filter secara end-to-end:

```python
import redis
import numpy as np
from redis.commands.search.field import VectorField, TagField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

def main():
    r = redis.Redis(host='localhost', port=6379, decode_responses=False)
    r.flushall()
    print("[+] Database flushed.")

    # 1. Test Bloom Filter
    # Inisialisasi Bloom Filter: error_rate=0.01 (1%), initial_capacity=1000
    r.bf().create("blacklist:tokens", 0.01, 1000)
    r.bf().add("blacklist:tokens", "token_xyz_expired")
    
    assert r.bf().exists("blacklist:tokens", "token_xyz_expired") == 1
    assert r.bf().exists("blacklist:tokens", "token_valid_active") == 0
    print("[+] Bloom Filter verified successfully.")

    # 2. Setup Vector Search over JSON
    INDEX_NAME = "idx:embeddings"
    schema = (
        TagField("$.namespace", as_name="namespace"),
        VectorField(
            "$.vector",
            "HNSW",
            {
                "TYPE": "FLOAT32",
                "DIM": 4,
                "DISTANCE_METRIC": "L2",
                "M": 16,
                "EF_CONSTRUCTION": 64
            },
            as_name="vec"
        )
    )
    
    r.ft(INDEX_NAME).create_index(
        schema, 
        definition=IndexDefinition(prefix=["data:"], index_type=IndexType.JSON)
    )
    print("[+] HNSW Vector Index created.")

    # Ingest dummy items
    vectors = {
        "data:1": ([0.1, 0.2, 0.1, 0.0], "public"),
        "data:2": ([0.9, 0.8, 0.7, 0.9], "private"),
        "data:3": ([0.12, 0.19, 0.08, 0.02], "public"),
    }

    for key, (v, ns) in vectors.items():
        payload = {"namespace": ns, "vector": v}
        r.json().set(key, "$", payload)
    
    print("[+] Documents ingested to RedisJSON.")

    # 3. Execute Vector Search
    query_vector = np.array([0.1, 0.2, 0.1, 0.0], dtype=np.float32).tobytes()
    query_str = "(@namespace:{public})=>[KNN 2 @vec $query_vec AS dist]"
    q = Query(query_str).sort_by("dist").return_fields("dist", "$.namespace").dialect(2)
    
    res = r.ft(INDEX_NAME).search(q, query_params={"query_vec": query_vector})
    
    print(f"[+] Found {res.total} matching documents:")
    for doc in res.docs:
        print(f"    - ID: {doc.id}, Distance: {doc.dist}")

    assert res.total == 2
    assert res.docs[0].id == b"data:1" or res.docs[0].id == "data:1"
    print("[+] Verification complete: ALL MODULES OPERATING NOMINALLY.")

if __name__ == "__main__":
    main()
```

---

### 13. Exercise

#### Level: Easy
Instansiasikan sebuah Count-Min Sketch menggunakan command Redis CLI (`CMS.INITBYPROB`) dengan toleransi error $\epsilon = 0.001$ dan probabilitas kegagalan $\delta = 0.01$. Tambahkan nilai frekuensi sebesar 50 ke item `"user:402"` dan ambil estimasi nilainya.
- **Ekspektasi Output**: Pembacaan via `CMS.QUERY` menghasilkan nilai 50 tanpa deviasi pada dataset kecil.

#### Level: Medium
Tuliskan skrip (Python/Go) untuk membandingkan alokasi memori antara:
1. Menyimpan 100.000 user UUID menggunakan Redis `SET`.
2. Menyimpan 100.000 user UUID menggunakan `BF.ADD` pada Bloom Filter dengan $p = 0.01$.
- Gunakan `MEMORY USAGE` untuk mengukur total konsumsi byte pada kedua implementasi dan hitung rasio kompresinya.

#### Level: Hard
Bangun implementasi RAG Search Retrieval pipeline di mana:
1. Skema RedisJSON memuat payload artikel: `{ "doc_id": "...", "text": "...", "tenant_id": "...", "timestamp": ..., "vector": [...] }`.
2. Lakukan kueri hybrid: Ambil dokumen dengan filter rentang waktu 7 hari terakhir (`timestamp`), terisolasi pada `tenant_id = "finance_corp"`, dan cari Top 3 vector terdekat berdasarkan Cosine Similarity.
3. Kueri wajib memproyeksikan hanya field `text` dan `score`, tanpa mengembalikan array `vector` (untuk menghemat network bandwidth).

---

### 14. Challenge

**Skenario Kasus**: Anda memegang peran Chief Architect pada platform AdTech global. Sistem harus memproses 100.000 bid request per detik. 
Persyaratan sistem:
1. **Pencegahan Fraud Click**: Melakukan drop click jika IP address melakukan klik lebih dari 10 kali dalam sliding window 1 menit (Memori bounded).
2. **Frequency Capping**: Setiap profile user (ada 500 juta profile unik) tidak boleh melihat campaign yang sama lebih dari 3 kali sehari.
3. **Dynamic Lookalike Targeting**: Setiap iklan memiliki context vector (128 dimensi). Anda harus mencari Top 5 kampanye iklan paling relevan terhadap interest profile user yang sedang browsing secara real-time ($<3$ ms SLA latency).
4. **Constraints**: Total alokasi server RAM untuk layer caching/hot data dibatasi maksimal 32 GB.

**Tugas Arsitektur**:
Rancang dokumen rancangan teknis yang mencakup:
- Pemilihan struktur data (kombinasi Redis core, Probabilistik, JSON, RediSearch).
- Formula sizing kalkulasi memori untuk 500 juta entitas.
- Skema partisi cluster (Sharding strategy & key naming convention).
- Mitigasi skenario cold-start dan node failover.
- Konfigurasi parameter Redis Module internals.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level
1. **Apakah dokumen yang disimpan menggunakan RedisJSON dapat diindeks oleh RediSearch tanpa menduplikasi data ke struktur data lain?**
   - A. Tidak, RediSearch memerlukan replikasi data ke `HASH`.
   - B. Ya, RediSearch v2+ dapat langsung memetakan indeks sekunder ke field di dalam RedisJSON menggunakan JSONPath.
   - C. Hanya bisa jika dokumen JSON tidak mengandung array.
   - D. Hanya jika data dikonversi manual ke format XML.
   *Kunci Jawaban: B* | *Alasan: Modul RediSearch v2.0+ mendukung Index Definition bertipe `IndexType.JSON` yang membaca referensi node internal memory RedisJSON langsung via JSONPath.*

2. **Berapa nilai False Negative Rate pada struktur data Bloom Filter standar?**
   - A. Tergantung jumlah fungsi hash.
   - B. Setara dengan False Positive Rate ($p$).
   - C. 0% (Nol).
   - D. 50%.
   *Kunci Jawaban: C* | *Alasan: Secara matematis, jika suatu elemen pernah dimasukkan, bit-bit yang bersangkutan pasti bernilai 1. Oleh karena itu, Bloom filter tidak pernah menghasilkan False Negative.*

3. **Struktur data probabilistik manakah yang mendukung operasi penghapusan item individual?**
   - A. Standard Bloom Filter
   - B. HyperLogLog
   - C. Cuckoo Filter
   - D. Count-Min Sketch
   *Kunci Jawaban: C* | *Alasan: Cuckoo filter menyimpan fingerprint dalam bucket array hash yang dapat dicari dan didelete secara terisolasi tanpa merusak integritas elemen lainnya.*

4. **Metrik jarak manakah di RediSearch Vector yang paling optimal untuk embeddings yang telah dinormalisasi (unit vectors)?**
   - A. L2 (Euclidean)
   - B. COSINE / IP (Inner Product)
   - C. HAMMING
   - D. MANHATTAN
   *Kunci Jawaban: B* | *Alasan: Untuk vektor yang ternormalisasi, Cosine distance ekuivalen secara proporsional terhadap Inner Product, memungkinkan kalkulasi aljabar linier dot-product berjalan sangat efisien di level CPU SIMD/AVX.*

5. **Apa fungsi utama dari struktur data t-digest di ekosistem Redis?**
   - A. Menghitung kardinalitas data unik secara akurat.
   - B. Mengestimasi nilai quantile/percentile (seperti p99) pada streaming dataset dengan memori konstan.
   - C. Kompresi gambar thumbnail secara lossless.
   - D. Pencarian path terpendek pada graf dokumen.
   *Kunci Jawaban: B* | *Alasan: t-digest didesain secara spesifik untuk memetakan distribusi data numerik dan mengestimasi extreme percentiles dengan akurasi tinggi pada bounding memory tetap.*

#### Intermediate Level
6. **Pada indexing HNSW di RediSearch, apa konsekuensi langsung dari memperbesar nilai parameter `M` (misal dari 16 ke 64)?**
   - A. Mempercepat waktu indexing dokumen baru.
   - B. Menurunkan akurasi/recall pencarian.
   - C. Meningkatkan konsumsi memori RAM per node graf dan menaikkan recall rate.
   - D. Mengurangi konsumsi memori hingga 50%.
   *Kunci Jawaban: C* | *Alasan: Parameter `M` mendefinisikan jumlah connection edges maksimal per node graf. Nilai lebih tinggi menambah kepadatan graf (meningkatkan kualitas lintasan pencarian/recall), namun menaikkan kebutuhan alokasi heap pointer secara linear.*

7. **Mengapa mutasi parsial pada RedisJSON (`JSON.SET key $.status "ACTIVE"`) lebih efisien secara performa daripada `SET key <stringified_json>`?**
   - A. RedisJSON mengompresi string menggunakan GZIP secara otomatis.
   - B. Menghindari transfer network payload keseluruhan dan hanya mengalokasikan ulang memori pada target node parsing tanpa re-serializing seluruh pohon.
   - C. RedisJSON mengeksekusi mutasi di thread background terpisah.
   - D. Operasi stringified JSON selalu memblokir master selama 1 detik.
   *Kunci Jawaban: B* | *Alasan: RedisJSON memelihara tree node internal. Mutasi parsial hanya memodifikasi sub-tree target secara in-place, meminimalkan overhead I/O jaringan dan siklus parser CPU.*

8. **Apa yang terjadi ketika struktur data Count-Min Sketch mengalami saturasi (kapasitas event jauh melampaui alokasi width/depth)?**
   - A. Redis akan mengembalikan error `OOM command not allowed`.
   - B. Terjadi underestimation (nilai frekuensi terbaca jauh lebih kecil dari aslinya).
   - C. Terjadi overestimation masif (nilai frekuensi terbaca jauh lebih besar akibat tabrakan hash pada counter).
   - D. CMS secara otomatis mereset counter ke nilai 0.
   *Kunci Jawaban: C* | *Alasan: CMS hanya melakukan increment pada shared counter array. Tabrakan hash yang intensif akan meningkatkan nilai pada sel array, sehingga pembacaan `min()` menghasilkan frekuensi yang terlampau tinggi (*overestimate*).*

9. **Dalam kueri Hybrid RediSearch `(@status:{active})=>[KNN 10 @vector $vec]`, bagaimana mesin kueri mengeksekusi filtering secara optimal?**
   - A. Menjalankan vector search pada seluruh dokumen, lalu membuang dokumen yang tidak memiliki status active.
   - B. Menggunakan inverted index untuk membuat bitmask dokumen berstatus active, lalu traversal HNSW dibatasi hanya mengevaluasi simpul yang valid pada bitmask tersebut (pre-filtering).
   - C. Mendownload semua raw vectors ke client side untuk difilter via aplikasi.
   - D. Mengeksekusi dua query terpisah lalu menggabungkannya via Redis Lua script.
   *Kunci Jawaban: B* | *Alasan: RediSearch menerapkan integrated iterative pre-filtering, membatasi ruang eksplorasi graf HNSW hanya pada dokumen yang lolos kriteria tag/numeric index.*

10. **Apa implikasi dari mengaktifkan `NONSCALING` pada pembuatan Bloom Filter via `BF.RESERVE`?**
    - A. Filter akan otomatis menghapus key terlama saat kapasitas tercapai.
    - B. Filter menolak penambahan item baru dan mengembalikan error ketika kapasitas target terlampaui, sehingga mempertahankan jaminan target false-positive rate.
    - C. Kecepatan baca berkurang 50%.
    - D. Memori filter akan otomatis dikurangi jika data berkurang.
    *Kunci Jawaban: B* | *Alasan: Tanpa scaling berjenjang, RedisBloom tidak akan menambahkan sub-filter baru, mencegah konsumsi memori tak terbatas dan menjaga latency verifikasi bit tetap deterministik.*

#### Production Scenario Analysis
11. **Skenario 1**: 
Sebuah sistem streaming analytics menggunakan Redis Stack untuk menyimpan metrik latensi network secara berkala. Insinyur menggunakan Redis `SORTED SET (ZSET)` dengan score berupa execution timestamp dan member berupa float latency: `ZADD latencies <timestamp> <latency_value>`. Pada hari ke-3, performa Redis anjlok drastis, latensi API melonjak ke 500ms, dan alert OOM menyala.
- **Analisis Masalah**: `ZSET` mempertahankan alokasi memory overhead sebesar $\approx 32-64$ bytes per elemen (skiplist node + hash table entry + string object). Jutaan metrik tak terhingga memicu saturasi jemalloc dan fragmentasi parah.
- **Solusi Arsitektur**: Ganti dengan struktur **Redis t-digest**. t-digest mempertahankan memory footprint tetap (constant bounding) dalam rentang beberapa kilobyte terlepas dari miliaran datapoint yang dimasukkan via `TDIGEST.ADD`, sambil menyediakan estimasi p50, p90, p99 yang sangat presisi via `TDIGEST.QUANTILE`.

12. **Skenario 2**: 
Tim AI mengimplementasikan semantic search RAG dengan 2.000.000 dokumen internal menggunakan RediSearch HNSW Index ($D=1536$). Server Redis mengalami reboot tak terduga. Saat startup, Redis membutuhkan waktu lebih dari 45 menit untuk membaca file `.aof` dan selama durasi tersebut server menolak seluruh koneksi (`LOADING Redis is loading the dataset in memory`).
- **Analisis Masalah**: RediSearch harus merekonstruksi graf HNSW layer-demi-layer dari append log sequential saat memproses ulang write commands di file AOF. Membangun graf $2 \times 10^6$ node dengan dimensi 1536 memakan komputasi CPU murni yang sangat masif.
- **Solusi Arsitektur**:
  1. Ubah konfigurasi persistensi: Nonaktifkan AOF rebuilding penuh untuk vector index data; gunakan periodic **RDB (Snapshotting)** murni untuk persistence state RediSearch (RDB menyimpan serialisasi raw memory graph yang langsung di-load secara mmap/in-memory tanpa kalkulasi ulang edge graph).
  2. Implementasikan arsitektur Master-Replica: Biarkan read replica menangani kueri saat Master sedang recovery, atau lakukan index pre-warm pada instance staging sebelum dialihkan ke route traffic produksi.

13. **Skenario 3**: 
Layanan autentikasi mendeteksi token reuse menggunakan Bloom Filter dengan konfigurasi `BF.RESERVE auth:tokens 0.0001 1000000`. Setelah 6 bulan berjalan tanpa restart, user valid mengeluhkan sering terblokir secara acak dengan pesan "Token already consumed", meskipun token baru saja digenerate oleh IdP.
- **Analisis Masalah**: Kapasitas awal diset 1.000.000 item. Tanpa disadari, sistem telah memproses 50.000.000 token. Karena scaling berantai default aktif, puluhan layer sub-filter terbuat, dan akumulasi False Positive Rate melonjak drastis melampaui $0.0001$, menyebabkan token valid baru teridentifikasi keliru sebagai "sudah ada" (False Positive collision).
- **Solusi Arsitektur**: Terapkan arsitektur **Sliding-Window Partitioned Filters**. Alih-alih satu filter abadi:
  1. Buat filter berbasis rentang waktu (misal harian): `auth:tokens:2026-03-30`.
  2. Pengecekan keberadaan dilakukan via pipeline ke filter hari ini dan filter hari kemarin (`BF.EXISTS`).
  3. Berikan key TTL (misal 48 jam) pada tiap filter harian agar Redis mengeksekusi eviction memori secara otomatis, menjaga kardinalitas filter selalu berada di bawah batas desain 1.000.000 item per bucket.

---

### 16. Summary

1. **Evolusi Redis**: Redis telah bertransformasi dari sekadar key-value cache engine primitif menjadi multi-model real-time state store berlatensi sub-milidetik, didukung oleh modul native yang terintegrasi langsung pada memory layer.
2. **Efisiensi Struktur Probabilistik**: Penggunaan Bloom Filter, Cuckoo Filter, Count-Min Sketch, dan t-digest memberikan jaminan efisiensi ruang memori berlipat ganda ($>90\%$ reduction) dibanding struktur data diskrit konvensional, dengan kompensasi deviasi statistik terukur (*controlled error rate*).
3. **Pemberdayaan AI via RediSearch & RedisJSON**: Kombinasi representasi data JSON native dengan indeks vektor HNSW menghadirkan fondasi ideal bagi arsitektur Retrieval-Augmented Generation (RAG) dan recommendation engine. Sistem mampu mengeksekusi kalkulasi similaritas vektor berdimensi tinggi secara presisi di samping filter metadata kompleks dalam satu siklus roundtrip.
4. **Prinsip Skalabilitas Enterprise**: Penggelaran Redis Stack pada taraf produksi berskala besar menuntut pemahaman arsitektur memori mendalam (jemalloc overhead, HNSW parameter trade-off, dan persistensi state RDB vs AOF) untuk menjaga stabilitas kueri p99 di bawah ambang batas sub-milidetik.