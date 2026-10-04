# Bab 04: Query DSL & Engine Scoring Internals
## Module 01: Deep Dive Query DSL & Relevance Scoring

---

### 01 Identitas Modul
* **Track:** Backend and Database
* **Course:** Elasticsearch Engineering
* **Module Code:** ELS-ENG-0401
* **Level:** Advanced (L4)
* **Prerequisites:** ELS-ENG-0102 (Inverted Index Mechanics), ELS-ENG-0201 (Mapping & Analysis Pipeline), Distributed Systems Fundamentals
* **Time Commitment:** 8 Jam (4 Jam Teori & Analisis Internal, 4 Jam Hands-on & Optimasi Lab)

---

### 02 Learning Objectives
1. **Membedah Formula Scoring Okapi BM25:** Menghitung dan menganalisis parameter $k_1$, $b$, Inverse Document Frequency (IDF), dan Field-Length Normalization secara matematis dan implementatif.
2. **Arsitektur Query DSL:** Membedakan eksekusi `query context` (relevance-driven) vs `filter context` (bitset caching) pada level Apache Lucene.
3. **Compound Queries Orchestration:** Menguasai perancangan kompleksitas `bool` query (`must`, `should`, `filter`, `must_not`), `dis_max`, serta manipulasi relevansi menggunakan `boosting` dan `function_score`/`script_score`.
4. **Scoring Diagnostics:** Mendekonstruksi payload `_explain` API dan Profile API untuk mendiagnosis anomali relevansi serta bottleneck eksekusi query.
5. **Optimasi Latensi & Throughput:** Mengimplementasikan teknik optimasi Top-K retrieval (Block-Max WAND) untuk menurunkan konsumsi CPU pada query frekuensi tinggi.

---

### 03 Concept Map Diagram ASCII

```
                                  [ Client Query Request ]
                                             │
                                             ▼
                       ┌───────────────────────────────────────────┐
                       │          Elasticsearch Coordinator        │
                       └─────────────────────┬─────────────────────┘
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
             [ Query Context ]                            [ Filter Context ]
        (Relevance Scoring Needed)                   (Exact Match Yes/No Only)
                       │                                           │
                       ▼                                           ▼
         ┌───────────────────────────┐                ┌─────────────────────────┐
         │ Lucene Weight / Scorer    │                │ Lucene Weight / Scorer  │
         │ - Term Frequency (TF)     │                │ - Skip List Traversals  │
         │ - Inverted Doc Freq (IDF) │                │ - Roaring Bitsets Cache │
         │ - Field-length Norm (L)   │                │ - No Math Scoring (0.0) │
         └─────────────┬─────────────┘                └────────────┬────────────┘
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │      Okapi BM25 Retrieval Engine        │
                        │ score(D,Q) = ∑ IDF · (TF / (TF + k1·N)) │
                        └────────────────────┬────────────────────┘
                                             │
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │       Scoring Modifiers Pipeline        │
                        │ - Boosting / Tie Breaker (dis_max)      │
                        │ - Function Score / Script Score         │
                        │ - Block-Max WAND (Early Termination)    │
                        └────────────────────┬────────────────────┘
                                             │
                                             ▼
                                  [ Sorted Hits Payload ]
```

---

### 04 Mengapa Relevan
Pada sistem pencarian skala enterprise (e-commerce, legal tech, enterprise workplace search), mengembalikan dokumen saja tidak cukup; dokumen paling relevan harus berada di posisi 3 teratas (*Top-3 hits*). 

Ketidakpahaman terhadap algoritma scoring menyebabkan dua kegagalan fatal:
1. **Search Precision Degradation:** Dokumen usang atau spam kata kunci mendominasi hasil teratas karena over-matching pada field deskripsi panjang.
2. **Cluster Compute Degradation:** Penggunaan `query context` untuk pencarian berbasis status/kategori yang seharusnya menggunakan `filter context` menghancurkan performa CPU dan mematikan fungsi *Node Query Cache*.

Modul ini membongkar lapisan abstraksi Query DSL hingga ke engine Lucene, memberikan fondasi mathematically-sound untuk mengendalikan relevansi dan performa pencarian.

---

### 05 Anatomi Konsep Inti

#### 1. Formulasi Matematika Okapi BM25
Lucene mengimplementasikan Okapi BM25 sebagai default similarity algorithm, menggantikan TF-IDF klasik. Diberikan query $Q$ yang terdiri dari term-term $q_1, q_2, \dots, q_n$, skor BM25 untuk dokumen $D$ didefinisikan sebagai:

$$\text{Score}(D, Q) = \sum_{i=1}^{n} \text{IDF}(q_i) \cdot \frac{f(q_i, D) \cdot (k_1 + 1)}{f(q_i, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$

Di mana:
* $f(q_i, D)$: Term Frequency dari term $q_i$ di dalam dokumen $D$.
* $|D|$: Panjang dokumen $D$ (dihitung dari jumlah term dalam field).
* $\text{avgdl}$: Rata-rata panjang dokumen pada field tersebut di seluruh indeks.
* $k_1$: Mengontrol saturasi non-linear Term Frequency. Nilai default Lucene adalah $1.2$. Nilai yang lebih tinggi meningkatkan pengaruh frekuensi kata.
* $b$: Mengontrol seberapa agresif *Field-Length Normalization* diterapkan. Default Lucene adalah $0.75$. Nilai $b = 1.0$ menormalkan skor secara penuh berdasarkan panjang field; $b = 0.0$ menonaktifkan normalisasi panjang field seluruhnya.

Perhitungan $\text{IDF}(q_i)$ dihitung sebagai:

$$\text{IDF}(q_i) = \ln \left( 1 + \frac{N - n(q_i) + 0.5}{n(q_i) + 0.5} \right)$$

* $N$: Total dokumen di dalam shard/indeks.
* $n(q_i)$: Jumlah dokumen yang mengandung term $q_i$.

```
     Score Component Comparison: TF-IDF vs Okapi BM25
  Score
    ▲
    │                                  TF-IDF (Linear / Sqrt Growth)
    │                                 /
    │                                /
    │     Okapi BM25                /
    │    (Saturated Curve)         /
    │       ┌─────────────────────/───── Asymptote limit: (k1 + 1)
    │      /                     /
    │     /                     /
    │    /                     /
    │   /                     /
    │  /                     /
    │ /                     /
    └──────────────────────────────────────► Term Frequency (TF)
```

#### 2. Query Context vs Filter Context
* **Query Context (`"query"`):** "Seberapa cocok dokumen ini terhadap klausa query?" Menghitung kalkulasi float `_score`, memproses analisis teks, mengevaluasi field norm, dan mengeksekusi similarity scoring. Tidak dapat di-cache secara utuh sebagai bitset.
* **Filter Context (`"filter"`, `"must_not"`):** "Apakah dokumen ini cocok terhadap klausa query?" Pertanyaan biner (Yes/No). Mengembalikan `_score: 0.0`. Lucene membangun struktur data **Roaring Bitsets** yang disimpan di JVM off-heap memory (*Node Query Cache*), memungkinkan lookup berkecepatan tinggi ($\mathcal{O}(1)$ bitwise operations).

#### 3. Compound Queries Mechanics
* **`bool` Query:** Menggabungkan daun query (`leaf queries`) menggunakan logika Boolean.
  * `must`: Wajib cocok, berkontribusi terhadap `_score`.
  * `filter`: Wajib cocok, mengabaikan `_score`, memanfaatkan caching.
  * `should`: Menambah skor jika cocok. Jika tidak ada klausa `must`, minimal satu `should` harus cocok (`minimum_should_match: 1`).
  * `must_not`: Wajib tidak cocok, beroperasi dalam Filter Context.
* **`dis_max` (Disjunction Max):** Menghasilkan dokumen yang cocok dengan satu atau lebih sub-query, tetapi hanya menggunakan skor dari sub-query terbaik (*best-matching field*), ditambah fraksi kecil dari sub-query lain via parameter `tie_breaker`. Mengatasi problem *albino elephant* pada perbandingan multi-field.
* **`function_score` & `script_score`:** Memungkinkan injeksi variabel eksternal (contoh: popularitas, jarak geografis, margin profit, freshness decay) ke dalam formula BM25 default.

#### 4. Block-Max WAND (Weak AND)
Algoritma optimasi pada level shard Lucene untuk query Top-K. Alih-alih mengevaluasi BM25 pada setiap dokumen yang cocok di inverted list, Block-Max WAND membagi inverted list menjadi blok-blok dokumen (umumnya 128 doc per blok) dan mencatat skor maksimum potensial dari blok tersebut. Jika nilai maksimum blok lebih rendah dari skor dokumen ke-$K$ yang telah ditemukan, seluruh blok (128 dokumen) diabaikan (*skipped*) seketika.

---

### 06 Panduan Implementasi Step-by-Step

#### Step 1: Membuat Custom Similarity Mapping
Mengonfigurasi parameter BM25 ($k_1$ dan $b$) spesifik untuk field judul (`title`) dan deskripsi (`body`).

```json
PUT /ecommerce_products
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 1,
    "index": {
      "similarity": {
        "title_similarity": {
          "type": "BM25",
          "k1": 1.5,
          "b": 0.3
        },
        "body_similarity": {
          "type": "BM25",
          "k1": 1.2,
          "b": 0.8
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "similarity": "title_similarity",
        "fields": {
          "edge_ngram": {
            "type": "text",
            "analyzer": "standard"
          }
        }
      },
      "body": {
        "type": "text",
        "similarity": "body_similarity"
      },
      "category_id": {
        "type": "keyword"
      },
      "brand_id": {
        "type": "keyword"
      },
      "price": {
        "type": "scaled_float",
        "scaling_factor": 100
      },
      "sales_velocity": {
        "type": "float"
      },
      "created_at": {
        "type": "date"
      },
      "status": {
        "type": "keyword"
      }
    }
  }
}
```

#### Step 2: Ingest Data Sampel
```json
POST /ecommerce_products/_bulk
{"index":{"_id":"1"}}
{"title":"Mechanical Keyboard Wireless RGB","body":"Ultra-fast wireless mechanical gaming keyboard with tactile switches and long battery life.","category_id":"peripherals","brand_id":"logi","price":129.99,"sales_velocity":8.5,"created_at":"2023-10-01T00:00:00Z","status":"ACTIVE"}
{"index":{"_id":"2"}}
{"title":"Mechanical Switches Pack","body":"Pack of 110 silent mechanical keyboard switches for custom builds. Tactile and smooth.","category_id":"components","brand_id":"gateron","price":35.00,"sales_velocity":4.2,"created_at":"2023-11-15T00:00:00Z","status":"ACTIVE"}
{"index":{"_id":"3"}}
{"title":"Wireless Gaming Mouse RGB","body":"Ergonomic wireless mouse with RGB lighting and high precision sensor. Pairs well with mechanical keyboard.","category_id":"peripherals","brand_id":"logi","price":79.99,"sales_velocity":12.1,"created_at":"2024-01-05T00:00:00Z","status":"ACTIVE"}
{"index":{"_id":"4"}}
{"title":"Vintage Mechanical Typewriter","body":"Fully restored vintage mechanical typewriter from 1960. Antique collectible item.","category_id":"antiques","brand_id":"vintage","price":450.00,"sales_velocity":0.3,"created_at":"2022-01-01T00:00:00Z","status":"OUT_OF_STOCK"}
```

#### Step 3: Membangun Multi-Tier Relevancy Search Query
Menerapkan optimasi Filter Context, Disjunction Max, dan Scoring Decay.

```json
POST /ecommerce_products/_search
{
  "query": {
    "bool": {
      "filter": [
        { "term": { "status": "ACTIVE" } },
        { "range": { "price": { "gte": 20, "lte": 500 } } }
      ],
      "must": [
        {
          "dis_max": {
            "queries": [
              {
                "match": {
                  "title": {
                    "query": "mechanical keyboard",
                    "boost": 4.0
                  }
                }
              },
              {
                "match": {
                  "body": {
                    "query": "mechanical keyboard",
                    "boost": 1.0
                  }
                }
              }
            ],
            "tie_breaker": 0.3
          }
        }
      ],
      "should": [
        {
          "term": {
            "brand_id": {
              "value": "logi",
              "boost": 1.5
            }
          }
        }
      ]
    }
  }
}
```

---

### 07 Contoh Kasus Sederhana

#### Eksplorasi Relevansi & Scoring Explain API
Untuk memahami secara tepat bagaimana Elasticsearch menghitung skor dokumen id `1` dari query di atas:

```json
GET /ecommerce_products/_explain/1
{
  "query": {
    "match": {
      "title": "mechanical keyboard"
    }
  }
}
```

#### Dekonstruksi Output `_explain`
Ekstraksi data penting dari respons Lucene:

```json
{
  "_index": "ecommerce_products",
  "_id": "1",
  "matched": true,
  "explanation": {
    "value": 0.8754101,
    "description": "sum of:",
    "details": [
      {
        "value": 0.4125812,
        "description": "weight(title:mechanical in 0) [PerFieldSimilarity], result of:",
        "details": [
          {
            "value": 0.4125812,
            "description": "score(freq=1.0), computed as boost * idf * tf from:",
            "details": [
              { "value": 1.0, "description": "boost" },
              { "value": 0.35667494, "description": "idf, computed as log(1 + (N - n + 0.5) / (n + 0.5))" },
              {
                "value": 1.1567438,
                "description": "tf, computed as freq / (freq + k1 * (1 - b + b * dl / avgdl))",
                "details": [
                  { "value": 1.0, "description": "freq, occurrences of term within document" },
                  { "value": 1.5, "description": "k1, term saturation parameter" },
                  { "value": 0.3, "description": "b, length normalization parameter" },
                  { "value": 4.0, "description": "dl, length of field" },
                  { "value": 3.6666667, "description": "avgdl, average length of field across all documents" }
                ]
              }
            ]
          }
        ]
      },
      {
        "value": 0.4628289,
        "description": "weight(title:keyboard in 0) [PerFieldSimilarity], result of:",
        "details": [
          {
            "value": 0.4628289,
            "description": "score(freq=1.0), computed as boost * idf * tf from:",
            "details": [
              { "value": 1.0, "description": "boost" },
              { "value": 0.4054651, "description": "idf" },
              { "value": 1.1414765, "description": "tf" }
            ]
          }
        ]
      }
    ]
  }
}
```

---

### 08 Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi Search Service berbasis Golang menggunakan client resmi `elastic/go-elasticsearch/v8`. Implementasi ini mengintegrasikan custom scoring engine via `script_score` (menggabungkan BM25, decayed publication date, dan log-scaled popularity) dengan penanganan context, timeout, dan zero-allocation JSON parsing.

```go
package main

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"time"

	elasticsearch "github.com/elastic/go-elasticsearch/v8"
	esapi "github.com/elastic/go-elasticsearch/v8/esapi"
)

// SearchEngine mendefinisikan layer wrapper untuk Elasticsearch operations
type SearchEngine struct {
	client *elasticsearch.Client
}

// ProductDocument mewakili representasi data dalam Elasticsearch
type ProductDocument struct {
	ID            string    `json:"id"`
	Title         string    `json:"title"`
	Body          string    `json:"body"`
	CategoryID    string    `json:"category_id"`
	BrandID       string    `json:"brand_id"`
	Price         float64   `json:"price"`
	SalesVelocity float64   `json:"sales_velocity"`
	CreatedAt     time.Time `json:"created_at"`
	Status        string    `json:"status"`
}

// SearchParams mendefinisikan input filter dan scoring modifier
type SearchParams struct {
	SearchQuery string
	CategoryID  string
	MinPrice    float64
	MaxPrice    float64
	Page        int
	Size        int
}

// SearchResponse merepresentasikan struktur data balikan
type SearchResponse struct {
	TotalHits int64             `json:"total_hits"`
	MaxScore  float64           `json:"max_score"`
	Documents []ProductDocument `json:"documents"`
	TookMs    int64             `json:"took_ms"`
}

func NewSearchEngine(addresses []string, username, password string) (*SearchEngine, error) {
	cfg := elasticsearch.Config{
		Addresses: addresses,
		Username:  username,
		Password:  password,
		Transport: &http.Transport{
			MaxIdleConnsPerHost:   30,
			ResponseHeaderTimeout: 3 * time.Second,
			DialContext: (&net.Dialer{
				Timeout:   5 * time.Second,
				KeepAlive: 30 * time.Second,
			}).DialContext,
			TLSClientConfig: &tls.Config{
				InsecureSkipVerify: false,
			},
		},
	}

	client, err := elasticsearch.NewClient(cfg)
	if err != nil {
		return nil, fmt.Errorf("failed to create es client: %w", err)
	}

	// Ping cluster
	res, err := client.Ping()
	if err != nil {
		return nil, fmt.Errorf("ping failed: %w", err)
	}
	defer res.Body.Close()

	if res.IsError() {
		return nil, fmt.Errorf("ping returned error status: %s", res.Status())
	}

	return &SearchEngine{client: client}, nil
}

func (s *SearchEngine) ExecuteAdvancedSearch(ctx context.Context, params SearchParams) (*SearchResponse, error) {
	if params.Size <= 0 {
		params.Size = 10
	}
	from := params.Page * params.Size

	// Membangun Query DSL menggunakan Script Score untuk Dynamic Relevance
	// Formula: BM25_Score * (1 + log10(sales_velocity + 1)) * Recency_Decay
	queryDsl := map[string]interface{}{
		"from":             from,
		"size":             params.Size,
		"track_total_hits": true,
		"query": map[string]interface{}{
			"script_score": map[string]interface{}{
				"query": map[string]interface{}{
					"bool": map[string]interface{}{
						"filter": []map[string]interface{}{
							{
								"term": map[string]interface{}{
									"status": "ACTIVE",
								},
							},
							{
								"term": map[string]interface{}{
									"category_id": params.CategoryID,
								},
							},
							{
								"range": map[string]interface{}{
									"price": map[string]interface{}{
										"gte": params.MinPrice,
										"lte": params.MaxPrice,
									},
								},
							},
						},
						"must": []map[string]interface{}{
							{
								"dis_max": map[string]interface{}{
									"queries": []map[string]interface{}{
										{
											"match": map[string]interface{}{
												"title": map[string]interface{}{
													"query": params.SearchQuery,
													"boost": 3.0,
												},
											},
										},
										{
											"match": map[string]interface{}{
												"body": map[string]interface{}{
													"query": params.SearchQuery,
													"boost": 1.0,
												},
											},
										},
									},
									"tie_breaker": 0.2,
								},
							},
						},
					},
				},
				"script": map[string]interface{}{
					"source": `
						double bm25 = _score;
						double velocity = doc['sales_velocity'].empty ? 0.0 : doc['sales_velocity'].value;
						double logVelocity = Math.log10(velocity + 1.0);
						
						// Recency factor using epoch millis
						long now = params.now;
						long docDate = doc['created_at'].value.toEpochMilli();
						double daysOld = (double)(now - docDate) / (1000.0 * 3600.0 * 24.0);
						double recencyDecay = 1.0 / (1.0 + (daysOld * 0.01));
						
						return bm25 * (1.0 + logVelocity) * recencyDecay;
					`,
					"params": map[string]interface{}{
						"now": time.Now().UnixMilli(),
					},
				},
			},
		},
	}

	var buf bytes.Buffer
	if err := json.NewEncoder(&buf).Encode(queryDsl); err != nil {
		return nil, fmt.Errorf("failed to encode query DSL: %w", err)
	}

	req := esapi.SearchRequest{
		Index: []string{"ecommerce_products"},
		Body:  &buf,
	}

	res, err := req.Do(ctx, s.client)
	if err != nil {
		return nil, fmt.Errorf("es request failed: %w", err)
	}
	defer res.Body.Close()

	if res.IsError() {
		rawErr, _ := io.ReadAll(res.Body)
		return nil, fmt.Errorf("search error [%s]: %s", res.Status(), string(rawErr))
	}

	// Payload struct parser
	var rawResult struct {
		Took int64 `json:"took"`
		Hits struct {
			Total struct {
				Value int64 `json:"value"`
			} `json:"total"`
			MaxScore float64 `json:"max_score"`
			Hits     []struct {
				ID         string          `json:"_id"`
				Score      float64         `json:"_score"`
				SourceData ProductDocument `json:"_source"`
			} `json:"hits"`
		} `json:"hits"`
	}

	if err := json.NewDecoder(res.Body).Decode(&rawResult); err != nil {
		return nil, fmt.Errorf("failed to decode response payload: %w", err)
	}

	output := &SearchResponse{
		TotalHits: rawResult.Hits.Total.Value,
		MaxScore:  rawResult.Hits.MaxScore,
		TookMs:    rawResult.Took,
		Documents: make([]ProductDocument, 0, len(rawResult.Hits.Hits)),
	}

	for _, hit := range rawResult.Hits.Hits {
		doc := hit.SourceData
		doc.ID = hit.ID
		output.Documents = append(output.Documents, doc)
	}

	return output, nil
}

func main() {
	esAddress := os.Getenv("ELASTICSEARCH_URL")
	if esAddress == "" {
		esAddress = "http://localhost:9200"
	}

	engine, err := NewSearchEngine([]string{esAddress}, "elastic", "changeme")
	if err != nil {
		log.Fatalf("Initialization failed: %v", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	params := SearchParams{
		SearchQuery: "mechanical keyboard",
		CategoryID:  "peripherals",
		MinPrice:    10.0,
		MaxPrice:    300.0,
		Page:        0,
		Size:        10,
	}

	result, err := engine.ExecuteAdvancedSearch(ctx, params)
	if err != nil {
		if errors.Is(ctx.Err(), context.DeadlineExceeded) {
			log.Fatalf("Search timeout exceeded")
		}
		log.Fatalf("Execution error: %v", err)
	}

	fmt.Printf("Search Completed in %d ms | Total Hits: %d | Top Score: %.4f\n", 
		result.TookMs, result.TotalHits, result.MaxScore)
	
	for i, doc := range result.Documents {
		fmt.Printf("[%d] ID: %s | Title: %-35s | Price: $%-6.2f | Velocity: %.1f\n", 
			i+1, doc.ID, doc.Title, doc.Price, doc.SalesVelocity)
	}
}
```

---

### 09 Diagram Alur Kerja Eksekusi Query Internal (Lucene Level)

```
                       [ Incoming Search Request ]
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │ Shard-Level Query Phase (Coordinator -> Data Node)     │
       └────────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
                  ┌──────────────────────────────────┐
                  │ Evaluate Filter Context First    │
                  └─────────────────┬────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        [ In-Memory Query Cache ]          [ Iterate Doc IDs ]
        (Roaring Bitset Lookup)            (Build Bitset & Cache)
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
                ┌───────────────────────────────────────┐
                │ Intersect Filter Bitset with Postings │
                └───────────────────┬───────────────────┘
                                    │ (Matching Doc IDs)
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │ Block-Max WAND Scoring Evaluation                      │
       │ - Read Max-Score Metadata per Block (128 docs)         │
       │ - If (Current Block Max < Top-K Threshold) -> SKIP     │
       │ - Else -> Compute Okapi BM25 for docs in block         │
       └────────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │ Apply Secondary Scoring (Script/Decay/Tie-Breaker)     │
       └────────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │ Populate Min-Heap (Size = from + size)                 │
       │ Return Top Docs IDs + Float Scores to Coordinator      │
       └────────────────────────────────────────────────────────┘
```

---

### 10 Analisis Trade-offs

| Pendekatan Query | Keuntungan | Kerugian | Rekomendasi Kasus Penggunaan |
| :--- | :--- | :--- | :--- |
| **Pure `match` (Query Context)** | Akurasi linguistik tinggi, menghitung TF/IDF/BM25 murni. | CPU-intensive, zero-caching, skalabilitas rendah untuk filtering besar. | Free-text search pada field artikel, deskripsi, atau konten buku. |
| **`bool` with `filter` Context** | Latensi rendah, menggunakan Roaring Bitset Cache, hemat CPU. | Tidak menghasilkan skor dinamis (skor biner 0.0). | Filter status, category ID, multi-tenant ID, rentang tanggal/harga. |
| **`dis_max` vs `bool.should`** | `dis_max` mencegah efek kumulatif dari field redundan (*anti-skewing*). | Sedikit overhead evaluasi tie-breaker pada banyak sub-query. | Cross-field multi-match searching (contoh: match di `title` vs `body`). |
| **`script_score` (Painless)** | Fleksibilitas tinggi dalam memanipulasi ranking secara programmatic. | Menonaktifkan Block-Max WAND optimizations, lonjakan latensi shard. | Dynamic business scoring (Personalization, Recency Decay, Stock weight). |
| **`function_score` (Built-in)** | Lebih teroptimasi daripada script manual jika menggunakan function native. | DSL kompleks, parsing overhead, akan di-deprecate demi `script_score`. | Legacy index boosting berbasis standard Gaussian decay. |

---

### 11 Best Practices & Antipatterns

#### Best Practices
1. **Isolasi Logika Biner ke Filter Context:** Seluruh klausa query yang tidak membutuhkan perhitungan relevansi (misal: `tenant_id`, `status: ACTIVE`, `is_deleted: false`) **wajib** ditempatkan di dalam array `filter` atau `must_not`.
2. **Kustomisasi Parameter BM25 Terarah:** Atur parameter $b$ rendah ($0.1 - 0.3$) untuk field pendek dengan panjang tetap (misal: `SKU`, `product_name`), dan atur $b$ tinggi ($0.75 - 0.9$) untuk field panjang (misal: `article_body`, `user_reviews`) guna mereduksi spam repetisi term.
3. **Konfigurasi `track_total_hits: false` atau `track_total_hits: 10000`:** Memungkinkan Lucene mengaktifkan Block-Max WAND secara optimal tanpa harus menghitung seluruh kecocokan dokumen dalam indeks.

#### Antipatterns
* ❌ **Scoring Field Status:** Menjalankan `{ "must": [ { "term": { "status": "AVAILABLE" } } ] }`. Ini memaksa Lucene menghitung TF/IDF pada field status yang nilainya homogen, memboroskan siklus CPU.
* ❌ **Over-Boosting Wildcard/Regexp:** Menjalankan un-anchored wildcard `*term*` dalam query context. Ini memicu memory exhaustion dan melumpuhkan Lucene FST (Finite State Transducer).
* ❌ **Complex Scripting on Millions of Hits:** Menggunakan `script_score` tanpa mendahuluinya dengan filter yang ketat di query context. Hal ini memaksa evaluasi interpreter Painless pada jutaan dokumen.

---

### 12 Security Hardening

1. **Painless Scripting Sandbox Lockdown:** Pastikan regex pada Painless script dimatikan untuk mencegah DoS via *Catastrophic Backtracking*.
   Konfigurasi di `elasticsearch.yml`:
   ```yaml
   script.painless.regex.enabled: false
   script.max_compilations_rate: 150/1m
   ```
2. **Query String Injection Mitigation:** Hindari penggunaan raw `query_string` query yang menerima parameter langsung dari HTTP input user tanpa sanitasi. Gunakan `simple_query_string` query yang secara otomatis mengabaikan operator parsing ilegal (`AND`, `OR`, `NOT`, tanda kurung) yang dapat mengekspos struktur internal.
3. **Limit Max Clause Count:** Cegah DoS via Boolean Query Explosion dengan membatasi jumlah klausa Boolean:
   ```yaml
   indices.query.bool.max_clause_count: 1024
   ```

---

### 13 Observabilitas & Debugging

#### 1. Native Profiling Analysis
Gunakan Profile API untuk mengidentifikasi komponen Lucene yang memakan durasi terpanjang dalam proses searching.

```json
POST /ecommerce_products/_search
{
  "profile": true,
  "query": {
    "bool": {
      "filter": [{ "term": { "status": "ACTIVE" } }],
      "must": [{ "match": { "title": "mechanical" } }]
    }
  }
}
```

Analisis respons Profile API:
* Periksa metrics `time_in_nanoseconds` pada setiap Lucene Scorer: `TermQuery`, `BooleanQuery`, `PointRangeQuery`.
* Verifikasi apakah `MatchNoDocsQuery` terbentuk akibat short-circuiting.
* Pantau parameter `count` untuk melihat berapa kali `nextDoc()` dan `advance()` dipanggil.

#### 2. Metrik Esensial Monitoring Cluster
* `elasticsearch.node.query_cache.memory_size_in_bytes`: Total memori heap yang dipakai Roaring Bitsets.
* `elasticsearch.node.query_cache.hit_count` vs `miss_count`: Efisiensi Filter Context.
* `elasticsearch.indices.search.query.time_in_millis` / `elasticsearch.indices.search.query.total`: Rata-rata latensi query phase.

---

### 14 Benchmarking & Performance

Jalankan pengujian performa Query DSL menggunakan Rally atau tool load testing (k6/vegeta) untuk melihat korelasi antara Query Context vs Filter Context.

#### Hasil Eksperimen Benchmark (Dataset: 10 Juta Dokumen, 