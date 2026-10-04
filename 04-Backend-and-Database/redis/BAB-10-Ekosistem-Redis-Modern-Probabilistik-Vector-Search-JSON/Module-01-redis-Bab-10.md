# Module 01 — Ekosistem Redis Modern: Probabilistik, Vector Search, & JSON

---

## 01: Identitas Modul
* **Track:** 04-Backend-and-Database
* **Course:** Redis
* **Bab:** 10 (Modern Redis Stack Ecosystem)
* **Modul:** 01 (Ekosistem Redis Modern: Probabilistik, Vector Search, & JSON)
* **Tingkat Kesulitan:** Advanced
* **Prasyarat:** Pemahaman mendalam struktur data dasar Redis (Strings, Hashes, Sets, Sorted Sets), Arsitektur Memori Redis, Dasar-dasar Aljabar Linier & Vector Embedding, serta Protokol Redis Serialization Protocol (RESP3).

---

## 02: Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Mengoperasikan dan Mengintegrasikan Engine JSON Asli:** Menerapkan manipulasi dokumen JSON semi-terstruktur secara *in-place* menggunakan `RedisJSON` via path expression JSONPath tanpa *overhead* parsing/serializing di sisi aplikasi.
2. **Mendesain Indeks Multi-Model & Hybrid Query:** Membangun indeks sekunder terstruktur, teks penuh (*Full-Text*), dan numerik menggunakan engine `RediSearch` di atas dokumen JSON dan Hashes.
3. **Mengimplementasikan Vector Similarity Search (VSS):** Menghitung jarak embedding representasi teks/gambar menggunakan algoritma *Flat (Index Flat/Brute-force)* dan *HNSW (Hierarchical Navigable Small World)* dengan metrik `COSINE`, `L2`, dan `IP`.
4. **Mengoptimalkan Efisiensi Memori dengan Data Structures Probabilistik:** Mengimplementasikan *Bloom Filter*, *Cuckoo Filter*, *Count-Min Sketch*, *Top-K*, dan *HyperLogLog* untuk use case filtering, frekuensi, dan kardinalitas tinggi dengan kompleksitas ruang $O(1)$ atau sub-linear.
5. **Membangun Sistem RAG (Retrieval-Augmented Generation) & Semantic Cache:** Mengembangkan layer inferensi AI berlatensi sub-milidetik yang menggabungkan Vector Search dengan filter metadata JSON secara atomik.

---

## 03: Concept Map Diagram ASCII

```
+-------------------------------------------------------------------------------+
|                       REDIS STACK MODERN ENGINE (RESP3)                       |
+------------------------------------+------------------------------------------+
                                     |
    +--------------------------------+--------------------------------+
    |                                |                                |
+---v------------------+   +---------v------------+   +---------------v---------+
|      REDISJSON       |   |      REDISEARCH      |   |   REDIS PROBABILISTIC   |
| (Native JSON Tree)   |   |   (Indexing & VSS)   |   | (Sub-linear Structures) |
+---+------------------+   +---------+------------+   +---------------+---------+
    |                                |                                |
    |-- JSON.SET / JSON.GET          |-- Inverted Index (Text)        |-- Bloom Filter (BF)
    |-- JSON.ARRAPPEND               |-- Numeric / Tag Filter         |-- Cuckoo Filter (CF)
    |-- In-Place Memory Tree Mut.    |-- Vector Search Engine:        |-- Count-Min Sketch (CMS)
    |                                |   |-- FLAT (Exact Search)      |-- Top-K Engine
    |                                |   +-- HNSW (Approximate NN)    |-- HyperLogLog (HLL)
    +--------------------------------+--------------------------------+
                                     |
                                     v
       +-------------------------------------------------------------+
       |   HYBRID QUERY ENGINE (JSON + Vector Similarity Search)     |
       |   FT.SEARCH idx "@vector:[KNN 5 @v $BLOB] @status:{ACTIVE}"  |
       +-------------------------------------------------------------+
```

---

## 04: Mengapa Relevan

Redis telah berevolusi dari sekadar key-value cache berbasis RAM menjadi *multi-model in-memory database* yang tangguh. Pola arsitektur klasik yang mengambil seluruh JSON string dari Redis via `GET`, melakukan deserialisasi CPU-heavy di Node.js/Go/Python, memodifikasi field, lalu melakukan `SET` ulang ke memori, menimbulkan inefisiensi transmisi I/O jaringan, *CPU thrashing*, serta rentan terhadap *race condition*.

Hadirnya **RedisJSON** memungkinkan manipulasi tree dokumen JSON secara langsung di memori Redis dengan kompleksitas waktu $O(M)$ (di mana $M$ adalah ukuran sub-tree/field yang dimutasi, bukan ukuran seluruh dokumen).

Di era Artificial Intelligence dan Large Language Models (LLM), pencarian dokumen tidak lagi cukup menggunakan *exact-string matching*. **RediSearch Vector Similarity Search (VSS)** memungkinkan Redis bertindak sebagai *In-Memory Vector Database* ultra-rendah latensi (<2ms) untuk pipeline RAG (*Retrieval-Augmented Generation*), *semantic caching*, dan *recommendation system*, melengkapi struktur data probabilistik yang memecahkan masalah skala analitik *real-time* (seperti filter fraud, tracking trending topics) dengan penghematan memori RAM hingga 99% dibandingkan struktur data deterministik konvensional.

---

## 05: Anatomi Konsep Inti

```
+-----------------------------------------------------------------------------+
|                           REDIS MEMORY INTERNALS                            |
|                                                                             |
|  [RedisJSON Document Object]                                                |
|  +-----------------------------------------------------------------------+  |
|  | Root Node (JSON Tree)                                                 |  |
|  |   |-- Key: "profile" -> String Object ("Alice")                       |  |
|  |   |-- Key: "metrics" -> Object -> {"views": 1004, "score": 9.4}       |  |
|  |   +-- Key: "embedding" -> Vector Binary (Float32 Array [1536 dim])    |  |
|  +-----------------------------------------------------------------------+  |
|                                     | Pointer                               |
|                                     v                                       |
|  [RediSearch Index Schema: "idx:profiles"]                                  |
|  +-----------------------------------------------------------------------+  |
|  | Inverted Index (TAG):  "Alice"  --> DocID: doc:101                    |  |
|  | Numeric Range B-Tree:  "views"  --> (0..1000), (1001..2000)           |  |
|  | HNSW Graph (Vector):                                                  |  |
|  |   Layer 2: [Node A] --------------------> [Node B]                    |  |
|  |   Layer 1: [Node A] ------> [Node C] ---> [Node B]                    |  |
|  |   Layer 0: [Node A] -> [D] -> [Node C] -> [E] -> [Node B]             |  |
|  +-----------------------------------------------------------------------+  |
|                                                                             |
|  [Probabilistic Engine]                                                     |
|  +-----------------------------------------------------------------------+  |
|  | Bloom: [0|1|0|0|1|0|1|1] (Hash k=3: h1(x), h2(x), h3(x))             |  |
|  | CMS:   Matrix d x w (Frequency estimation via min-hash increment)     |  |
|  | Top-K: Heavy-Keepers Algorithm (Tracking Top N items without sort)     |  |
|  +-----------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------+
```

### 1. RedisJSON Internals
RedisJSON mem-parsing string JSON menjadi representasi *hierarchical tree data structure* terpadu di dalam memori C via parsing `cJSON` / internal DOM engine. Setiap node merepresentasikan tipe data primitif JSON (`String`, `Number`, `Boolean`, `Null`, `Array`, `Object`). Modifikasi seperti `JSON.NUMINCRBY` atau `JSON.ARRAPPEND` mengeksekusi pointer traversal langsung ke memory offset field terkait tanpa merekonstruksi payload dokumen secara global.

### 2. RediSearch & Vector Similarity Search (VSS)
RediSearch mengabstraksi *secondary indexing engine* yang beroperasi paralel dengan mutasi data Redis:
* **HNSW (Hierarchical Navigable Small World):** Algoritma *Approximate Nearest Neighbor (ANN)* berbasis grafik multi-layer. Memiliki kompleksitas pencarian $O(\log N)$, sangat cepat untuk pencarian vektor dimensi tinggi (e.g., OpenAI ada-002: 1536-dim, text-embedding-3: 3072-dim) dengan sedikit *recall trade-off*. Parameter kritis: `M` (jumlah maksimum koneksi per node), `EF_CONSTRUCTION` (kedalaman evaluasi saat indexing), dan `EF_RUNTIME` (kedalaman evaluasi saat query).
* **FLAT (Brute-Force):** Menghitung jarak Euclidean/Cosine ke seluruh vektor dalam database ($O(N)$). Membutuhkan komputasi intensif namun menghasilkan 100% recall akurasi. Cocok untuk dataset kecil (<50,000 dokumen) atau skenario *strict-filtering* tinggi.
* **Metrik Jarak:**
  * **COSINE:** $\text{Distance} = 1 - \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2}$
  * **L2 (Euclidean):** $\text{Distance} = \|\mathbf{u} - \mathbf{v}\|^2$
  * **IP (Inner Product):** $\text{Distance} = 1 - (\mathbf{u} \cdot \mathbf{v})$ (optimal untuk normalized vector).

### 3. Struktur Data Probabilistik
* **Bloom Filter (`BF.*`):** Array bit berukuran $m$ dengan $k$ fungsi hash independen. Mengembalikan **False Negative: 0%** (pasti tidak ada), dan **False Positive: $p$** (mungkin ada). Operasi insert/lookup $O(k)$. Item tidak dapat dihapus.
* **Cuckoo Filter (`CF.*`):** Menggunakan hashing berbasis fingerprint dan tabel routing Cuckoo. Mendukung operasi penghapusan item (`CF.DEL`) dengan efisiensi memori lebih baik dibanding Bloom Filter pada target false-positive rate rendah ($p < 0.001$).
* **Count-Min Sketch (`CMS.*`):** Matriks sub-linear berdimensi $w \times d$ untuk memperkirakan frekuensi elemen dalam streaming data kontinu tanpa menyimpan elemen aslinya.
* **Top-K (`TOPK.*`):** Mengimplementasikan algoritma Heavy-Keepers yang menggunakan decay dan array hashing untuk melacak $K$ elemen paling sering muncul secara presisi dengan alokasi memori deterministik dan konstan.

---

## 06: Panduan Implementasi Step-by-Step

### Step 1: Inisialisasi Environment Redis Stack
Redis standar (`redis:latest`) tidak menyertakan modul-modul ini secara *default*. Anda wajib menggunakan image **`redis/redis-stack-server`**.

```bash
docker run -d --name redis-stack-enterprise \
  -p 6379:6379 \
  -e REDIS_ARGS="--save '' --appendonly no" \
  redis/redis-stack-server:latest
```

### Step 2: Operasi Dokumen RedisJSON
```redis
# 1. Simpan dokumen JSON
JSON.SET user:1001 $ '{"name":"Raden Adrian","age":32,"skills":["Go","Redis","AI"],"metrics":{"reputation":89.5,"active":true}}'

# 2. Ambil field spesifik menggunakan JSONPath
JSON.GET user:1001 $.skills[0]
# Output: "[\"Go\"]"

# 3. Manipulasi in-place: Increment atomic value
JSON.NUMINCRBY user:1001 $.metrics.reputation 5.5
# Output: "[95]"

# 4. Tambah elemen ke dalam JSON Array
JSON.ARRAPPEND user:1001 $.skills '"Distributed Systems"'
# Output: [4]
```

### Step 3: Membuat Indeks RediSearch + Vector Search Schema
```redis
# Buat Secondary Index di atas dokumen JSON
FT.CREATE idx:users ON JSON PREFIX 1 "user:" SCHEMA \
  $.name AS name TEXT WEIGHT 1.0 \
  $.age AS age NUMERIC SORTABLE \
  $.skills[*] AS skills TAG \
  $.metrics.active AS is_active TAG \
  $.v_embedding AS embedding VECTOR HNSW 6 \
    TYPE FLOAT32 \
    DIM 4 \
    DISTANCE_METRIC COSINE \
    M 16 \
    EF_CONSTRUCTION 200
```

### Step 4: Menjalankan Hybrid Query (Vector KNN + Tag/Numeric Metadata Filtering)
```redis
# Update dokumen dengan dummy 4-dimensional vector embedding (Float32 binary-equivalent array)
JSON.SET user:1001 $.v_embedding '[0.12, 0.85, 0.05, 0.44]'
JSON.SET user:1002 $ '{"name":"Budi Santoso","age":28,"skills":["Python","AI"],"metrics":{"active":true},"v_embedding":[0.10, 0.88, 0.02, 0.41]}'

# Eksekusi Hybrid Vector Search: Cari 1 user paling mirip, HANYA YANG aktif dan punya skill AI
FT.SEARCH idx:users "(@skills:{AI} @is_active:{true})=>[KNN 1 @embedding $QUERY_VEC AS score]" \
  PARAMS 2 QUERY_VEC "\x71\x3d\x0a\x3e\x33\x33\x5b\x3f\x0a\xd7\x23\x3d\x71\x3d\x0a\x3e" \
  SORTBY score ASC \
  RETURN 3 name score $.skills \
  DIALECT 2
```

### Step 5: Alur Probabilistik (Bloom, Cuckoo, Top-K)
```redis
# Inisialisasi Bloom Filter dengan error rate 0.01 (1%) dan kapasitas 1,000,000 elemen
BF.RESERVE bf:fraud_check 0.01 1000000
BF.ADD bf:fraud_check "account:bad_actor_99"
BF.EXISTS bf:fraud_check "account:bad_actor_99" # Returns 1
BF.EXISTS bf:fraud_check "account:innocent_user" # Returns 0

# Inisialisasi Top-K untuk tracking 3 trending search term
TOPK.RESERVE topk:search_terms 3 2000 7 0.925
TOPK.ADD topk:search_terms "vector_db" "redis_stack" "redis_stack" "rag_pipeline" "redis_stack"
TOPK.LIST topk:search_terms
# Returns: 1) "redis_stack" 2) "vector_db" 3) "rag_pipeline"
```

---

## 07: Contoh Kasus Sederhana

**Problem:** Kita ingin mencegah duplikasi pemrosesan *webhook event payload* id (10 juta payload/hari) dan menghitung frekuensi endpoint target tanpa menghabiskan RAM gigabyte.

```redis
# Skenario: Idempotency check menggunakan Cuckoo Filter (Mendukung penghapusan saat lifecycle selesai)
CF.RESERVE cf:webhook_events 5000000

# 1. Cek apakah Event ID sudah diproses
CF.ADDNX cf:webhook_events "evt_998124_stripe"
# Output: (integer) 1 -> Berhasil masuk (Belum pernah diproses)

CF.ADDNX cf:webhook_events "evt_998124_stripe"
# Output: (integer) 0 -> Sudah ada! (Duplicate event, reject processing)

# 2. Lacak frekuensi route payload via Count-Min Sketch
CMS.INITBYPROB cms:endpoint_hits 0.001 0.01
CMS.INCRBY cms:endpoint_hits "/api/v1/checkout" 1 "/api/v1/webhooks" 5
CMS.QUERY cms:endpoint_hits "/api/v1/webhooks" "/api/v1/checkout"
# Output: 1) (integer) 5
#         2) (integer) 1

# 3. Clean up event id yang sudah lewat status retention (Cuckoo Filter mendukung DEL)
CF.DEL cf:webhook_events "evt_998124_stripe"
```

---

## 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi *Enterprise-grade Semantic Document Store & AI Caching System* menggunakan **Go (Golang)** dengan driver resmi `go-redis/v9`.

```go
package main

import (
	"context"
	"encoding/binary"
	"fmt"
	"log"
	"math"
	"time"

	"github.com/redis/go-redis/v9"
)

// Document merepresentasikan struktur domain yang disimpan dalam RedisJSON
type Document struct {
	ID        string    `json:"id"`
	Content   string    `json:"content"`
	Category  string    `json:"category"`
	TenantID  string    `json:"tenant_id"`
	Embedding []float32 `json:"embedding"`
	CreatedAt int64     `json:"created_at"`
}

type SemanticStore struct {
	client *redis.Client
	ctx    context.Context
}

func NewSemanticStore(addr string, password string) *SemanticStore {
	rdb := redis.NewClient(&redis.Options{
		Addr:         addr,
		Password:     password,
		DB:           0,
		PoolSize:     50,
		MinIdleConns: 10,
		ReadTimeout:  2 * time.Second,
		WriteTimeout: 2 * time.Second,
	})

	return &SemanticStore{
		client: rdb,
		ctx:    context.Background(),
	}
}

// Float32SliceToBytes mengonversi array Float32 ke little-endian byte stream untuk RediSearch Vector Engine
func Float32SliceToBytes(vector []float32) []byte {
	bytes := make([]byte, 4*len(vector))
	for i, v := range vector {
		binary.LittleEndian.PutUint32(bytes[i*4:], math.Float32bits(v))
	}
	return bytes
}

// InitializeSchema membuat index RediSearch jika belum ada
func (s *SemanticStore) InitializeSchema(indexName string) error {
	// Pengecekan keberadaan Index
	_, err := s.client.Do(s.ctx, "FT.INFO", indexName).Result()
	if err == nil {
		log.Printf("Index %s sudah terdaftar, skipping creation.\n", indexName)
		return nil
	}

	cmd := []interface{}{
		"FT.CREATE", indexName,
		"ON", "JSON",
		"PREFIX", "1", "doc:",
		"SCHEMA",
		"$.tenant_id", "AS", "tenant_id", "TAG",
		"$.category", "AS", "category", "TAG",
		"$.created_at", "AS", "created_at", "NUMERIC", "SORTABLE",
		"$.embedding", "AS", "vector", "VECTOR", "HNSW", "6",
		"TYPE", "FLOAT32",
		"DIM", "4",
		"DISTANCE_METRIC", "COSINE",
		"M", "16",
		"EF_CONSTRUCTION", "200",
	}

	err = s.client.Do(s.ctx, cmd...).Err()
	if err != nil {
		return fmt.Errorf("gagal membuat search index: %w", err)
	}
	log.Printf("Berhasil membuat Vector Index: %s\n", indexName)
	return nil
}

// InsertDocument mengunggah dokumen via RedisJSON
func (s *SemanticStore) InsertDocument(doc Document) error {
	key := fmt.Sprintf("doc:%s", doc.ID)
	// Menyimpan raw JSON secara langsung menggunakan JSON.SET
	err := s.client.Do(s.ctx, "JSON.SET", key, "$", doc).Err()
	if err != nil {
		return fmt.Errorf("gagal menyimpan JSON untuk key %s: %w", key, err)
	}
	return nil
}

// SemanticSearch mengeksekusi Hybrid Vector Search (Filter Metadata + KNN Similarity)
func (s *SemanticStore) SemanticSearch(indexName string, tenantID string, queryVec []float32, topK int) ([]string, error) {
	queryBlob := Float32SliceToBytes(queryVec)
	// Syntax Dialect 2: Hybrid Query dengan filter Tag Tenant ID & KNN
	queryString := fmt.Sprintf("(@tenant_id:{%s})=>[KNN %d @vector $BLOB AS score]", tenantID, topK)

	cmd := []interface{}{
		"FT.SEARCH", indexName, queryString,
		"PARAMS", "2", "BLOB", queryBlob,
		"SORTBY", "score", "ASC",
		"RETURN", "2", "score", "$.content",
		"DIALECT", "2",
	}

	res, err := s.client.Do(s.ctx, cmd...).Result()
	if err != nil {
		return nil, fmt.Errorf("search query failure: %w", err)
	}

	var results []string
	if rawList, ok := res.([]interface{}); ok {
		totalResults := rawList[0].(int64)
		log.Printf("Total relevan ditemukan: %d dokumen\n", totalResults)

		for i := 1; i < len(rawList); i += 2 {
			docKey := rawList[i].(string)
			docFields := rawList[i+1].([]interface{})
			results = append(results, fmt.Sprintf("Key: %s, Data: %v", docKey, docFields))
		}
	}

	return results, nil
}

func main() {
	store := NewSemanticStore("localhost:6379", "")
	indexName := "idx:knowledge_base"

	// 1. Setup Index
	if err := store.InitializeSchema(indexName); err != nil {
		log.Fatalf("Initialization schema failed: %v", err)
	}

	// 2. Insert Mock Data
	doc1 := Document{
		ID:        "uuid-1",
		Content:   "Arsitektur Microservices dengan Go dan gRPC",
		Category:  "Engineering",
		TenantID:  "tenant-alpha",
		Embedding: []float32{0.01, 0.95, 0.22, 0.15},
		CreatedAt: time.Now().Unix(),
	}

	doc2 := Document{
		ID:        "uuid-2",
		Content:   "Panduan Memasak Rendang Tradisional Padang",
		Category:  "Culinary",
		TenantID:  "tenant-alpha",
		Embedding: []float32{0.89, 0.05, 0.11, 0.02},
		CreatedAt: time.Now().Unix(),
	}

	_ = store.InsertDocument(doc1)
	_ = store.InsertDocument(doc2)

	// 3. Search Query Vector (Mencari vektor terkait programming microservice)
	queryVector := []float32{0.02, 0.91, 0.20, 0.18}
	results, err := store.SemanticSearch(indexName, "tenant-alpha", queryVector, 1)
	if err != nil {
		log.Fatalf("Search execution error: %v", err)
	}

	fmt.Println("--- Hasil Pencarian Vector ---")
	for _, match := range results {
		fmt.Println(match)
	}
}
```

---

## 09: Diagram Alur Kerja ASCII

Berikut adalah siklus eksekusi query hibrida (Pencarian Metadata + Algoritma KNN Vector Graph) di dalam RediSearch Engine:

```
[ Client Request ]
       | (Payload: Filter Tenant="alpha" + Query Vector Embedding)
       v
+---------------------------------------------------------------+
|                      REDIS REDISEARCH ENGINE                  |
|                                                               |
| 1. PARSE QUERY & DIALECT 2 EVALUATOR                          |
|    Syntax: (@tenant_id:{alpha})=>[KNN 5 @vec $BLOB]          |
|                                                               |
| 2. TAG INVERTED INDEX LOOKUP                                  |
|    +------------------------------------------------------+   |
|    | Bitset Filter Mask -> Tag "tenant-alpha"             |   |
|    | Valid Candidate Doc IDs: [Doc#1, Doc#2, Doc#99]     |   |
|    +------------------------------------------------------+   |
|                               | Filtered Candidate IDs        |
|                               v                               |
| 3. HNSW VECTOR GRAPH TRAVERSAL                                |
|    +------------------------------------------------------+   |
|    | Multi-layer Entry Point                              |   |
|    | Evaluate Cosine Distance (Vector_Doc vs Query_Vector)|   |
|    | Discard unmasked / Non-matching Tenant IDs           |   |
|    | Iterate greedy graph routing down to Layer 0         |   |
|    +------------------------------------------------------+   |
|                               | Nearest Neighbors Set         |
|                               v                               |
| 4. AGGREGATE & SCORE SORTING                                  |
|    Rank top results by Cosine Distance ASC                    |
+-------------------------------+-------------------------------+
                                |
                                v
+---------------------------------------------------------------+
|                      REDISJSON RESOLVER                       |
|    Fetch $.content directly from JSON memory tree offsets     |
+-------------------------------+-------------------------------+
                                |
                                v
               [ Returned Result Set to Client ]
```

---

## 10: Analisis Trade-offs

| Aspek | RediSearch HNSW Index | RediSearch FLAT Index | Tradisional Hash Cache + SQL |
| :--- | :--- | :--- | :--- |
| **Search Latency** | **Ultra-Low (< 3ms)** pada jutaan vector | **Linear/Tinggi ($O(N)$)** seiring membesarnya dataset | **Tinggi (10-100ms)** I/O bottleneck parsing |
| **Indexing Overhead** | **Sangat Tinggi** (Komputasi pembangunan Graph) | **Minimal** (Hanya append array byte) | **Nol pada Redis**, ada pada DB sekunder |
| **Memory Footprint**| **Besar** (Payload vector + Graph connection pointers) | **Moderat** (Hanya memori flat array) | **Kecil** (Hanya serialized string) |
| **Recall / Accuracy**| **Approximate (~95-99%)** (Parameter dependent) | **100% Exact** (Brute-force) | N/A (Tergantung exact indexing SQL) |
| **Penskalaan Update**| **Costly** (Mutasi graph memicu re-balance node) | **Cepat** ($O(1)$ memory replace) | Sangat cepat |

---

## 11: Best Practices & Antipatterns

### Best Practices
1. **Normalisasi Vektor di Sisi Klien:** Jika menggunakan *Cosine Distance*, pastikan vektor dinormalisasi menjadi *unit length* ($\|v\|=1$) di aplikasi jika beralih ke `IP` (Inner Product) untuk throughput komputasi SIMD Redis yang lebih cepat.
2. **Kustomisasi Efisien HNSW:** Set parameter `M` bernilai 16–64 dan `EF_CONSTRUCTION` bernilai 128–512 saat inisialisasi schema. Naikan `EF_RUNTIME` via query params hanya jika presisi *recall* kurang tinggi.
3. **Pemberian Indeks JSONPath Spesifik:** Jangan mengindeks root path `$` tanpa filter type. Selalu petakan field terdalam secara eksplisit (misal: `$.user.meta.id AS meta_id TAG`).
4. **Scale-Out Indexing:** Pisahkan Redis Vector Node dari master node komputasi OLTP standar untuk menghindari *CPU starvation* saat komputasi kalkulasi jarak vektor berjalan.

### Antipatterns
1. **Memperlakukan RedisJSON seperti Object Storage Raksasa:** Menyimpan dokumen individual JSON > 5MB ke dalam RedisJSON. Ini memicu alokasi fragmentasi memori besar (*jemalloc thrashing*) dan memblokir event-loop.
2. **Mengabaikan Redis Dialect:** Menggunakan query RediSearch tanpa parameter `DIALECT 2` atau `DIALECT 3`. Versi default lama (Dialect 1) tidak memiliki parser *Vector Search KNN syntax* yang efisien.
3. **Menggunakan Bloom Filter Tanpa Scaling Sizing:** Menjalankan `BF.ADD` pada Bloom Filter yang tidak dikonfigurasi (`BF.RESERVE`) sehingga menggunakan kapasitas default kecil. Hal ini memicu penambahan *sub-filter auto-scaling* berulang yang memperburuk latensi secara tajam.

---

## 12: Security Hardening

Modul modern Redis menambah beban parsing memori dinamis. Amankan dengan parameter berikut:

1. **Redis Access Control Lists (ACL) untuk Modul:** Batasi execution command module hanya untuk microservice yang berhak.
   ```redis
   # Batasi worker read-only: Hanya boleh Read JSON dan Search VSS
   ACL SETUSER vector_worker on >SecretPass123! ~doc:* ~idx:* +JSON.GET +FT.SEARCH +FT.INFO -@all
   ```
2. **Denial-of-Service (DoS) Mitigation via Query Bounds:** Batasi limit eksekusi search query agar query regex atau VSS yang salah tidak memblokir redis event-loop:
   ```redis
   # Batasi timeout eksekusi query RediSearch maksimal 500ms di redis.conf
   FT.CONFIG SET TIMEOUT 500
   FT.CONFIG SET ON_TIMEOUT RETURN # Return partial results saat timeout tercapai
   ```
3. **Alokasi Batas Memori Index Search:**
   ```redis
   # Mencegah RediSearch memakan semua RAM server saat index graph membengkak
   FT.CONFIG SET MAXEXPANSIONS 1000
   ```

---

## 13: Observabilitas & Debugging

Pantau kesehatan internal Modul Redis Stack secara mendalam:

```redis
# 1. Mendapatkan statistik mendalam terkait memori, geometri graph, dan kapasitas index
FT.INFO idx:knowledge_base

# Metrik krusial yang wajib dipantau:
# - num_docs: Total dokumen terindeks
# - memory_indexed_human: Total memori yang dikonsumsi oleh struktur index
# - vector_index_sz: Ukuran memori khusus struktur HNSW graph
# - indexing: Nilai 1 jika background re-indexing sedang berjalan

# 2. Menganalisis Profil Eksekusi Search Query (Mengetahui letak bottleneck latency)
FT.PROFILE idx:knowledge_base SEARCH QUERY "(@category:{Engineering})=>[KNN 10 @vector $BLOB]" PARAMS 2 BLOB "\x00..."

# 3. Observasi penggunaan memori struktur data probabilistik
DEBUG OBJECT bf:fraud_check
MEMORY USAGE cf:webhook_events
```

---

## 14: Benchmarking & Performance

Jalankan performance stress test menggunakan utility **`memtier_benchmark`** atau skrip benchmark vector khusus:

```bash
# Uji Throughput Read/Write RedisJSON vs Standar Redis Hash
memtier_benchmark -s 127.0.0.1 -p 6379 \
  --protocol=redis \
  --clients=50 \
  --threads=4 \
  --test-time=60 \
  --command='JSON.SET __key__ $ "{\"metric\":__randint__,\"data\":\"payload\"}"' \
  --key-prefix="bench_json:" \
  --key-minimum=1 \
  --key-maximum=1000000
```

### Karakteristik Ekspektasi Performa:
* **JSON In-Place Patching (`JSON.NUMINCRBY`):** ~90,000 – 120,000 Ops/Sec pada cluster CPU modern (Single-thread core bound).
* **VSS HNSW KNN Query (dimensi 1536, EF=64):** ~2,500 – 6,000 QPS per core dengan p99 latency < 2.5ms.
* **Probabilistic Add (`BF.ADD` / `CF.ADD`):** Mendekati batas *in-memory wire speed* (~130,000 Ops/Sec).

---

## 15: Hands-on Lab Mini-Project

### Objective: Membangun Semantic Cache Engine untuk OpenAI API
Tujuan Anda adalah mencegat query LLM yang identik secara semantik agar tidak terus-menerus memanggil OpenAI API berbayar, melainkan mengambil respon dari Redis dalam hitungan sub-milidetik.

```
Prompt User -> Generate Embedding -> Redis Vector Search
   |
   +-> Jika Distance <= 0.08 (Cache Hit)  -> Return Cached Response dari RedisJSON (Latency < 2ms)
   +-> Jika Distance >  0.08 (Cache Miss) -> Panggil LLM API -> Simpan Response ke RedisJSON
```

```python
# semantic_cache.py
import json
import numpy as np
import redis
from redis.commands.search.field import TextField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

# 1. Koneksi ke Redis Stack
r = redis.Redis(host='localhost', port=6379, decode_responses=False)

INDEX_NAME = "idx:semantic_cache"
VECTOR_DIM = 4 # Dummy 4-dimensi untuk pengujian lokal

def setup_cache_index():
    try:
        r.ft(INDEX_NAME).info()
        print("Semantic Cache Index already exists.")
    except:
        schema = (
            TextField("$.prompt", as_name="prompt"),
            TextField("$.response", as_name="response"),
            VectorField("$.embedding", "HNSW", {
                "TYPE": "FLOAT32",
                "DIM": VECTOR_DIM,
                "DISTANCE_METRIC": "COSINE"
            }, as_name="vector")
        )
        r.ft(INDEX_NAME).create_index(
            schema,
            definition=IndexDefinition(prefix=["cache:"], index_type=IndexType.JSON)
        )
        print("Semantic Cache Index initialized.")

def get_semantic_cache(query_vector, similarity_threshold=0.10):
    # Serialisasi vektor query ke float32 binary format
    query_bytes = np.array(query_vector, dtype=np.float32).tobytes()
    
    q = (
        Query(f"*=>[KNN 1 @vector $BLOB AS score]")
        .sort_by("score", asc=True)
        .return_fields("prompt", "response", "score")
        .paging(0, 1)
        .dialect(2)
    )
