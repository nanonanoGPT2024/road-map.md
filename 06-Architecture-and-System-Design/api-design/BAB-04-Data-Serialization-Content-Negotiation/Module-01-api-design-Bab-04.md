## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `ARCH-API-04-01`
* **Nama Modul**: Data Serialization, Filtering, & Content Negotiation
* **Kategori**: 06-Architecture-and-System-Design
* **Kurikulum**: API Design & Engineering
* **Level**: Advanced / L4-L5
* **Prasyarat**:
  * Pemahaman mendalam tentang HTTP/1.1 dan HTTP/2 Framing (RFC 7231 / RFC 7540).
  * Pemahaman mekanisme Relational Database Indexing (B-Tree, composite index, execution plan).
  * Pengalaman membangun RESTful atau RPC services berbasis microservices.
  * Familiaritas dengan struktur data biner dan byte array manipulation.
* **Estimasi Waktu**: 6–8 jam pembelajaran mandiri dan laboratorium praktis.
* **Target Audiens**: Senior Backend Engineers, API Architects, Distributed Systems Engineers, Platform Engineers.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis & Mengimplementasikan Mekanisme Content Negotiation**: Memanfaatkan header `Accept`, `Accept-Encoding`, `Content-Type`, serta mengonfigurasi header `Vary` secara presisi untuk mencegah keracunan cache (*cache poisoning*) pada downstream reverse proxy/CDN.
2. **Mengevaluasi & Mendesain Strategi Paginasi Skala Besar**: Menjelaskan dekomposisi komputasi internal engine RDBMS antara Offset-based, Keyset-based, dan Cursor-based pagination; mampu memitigasi masalah performa $O(N)$ scanning pada deep pagination.
3. **Membangun Arsitektur Sparse Fieldsets & Dynamic Filtering**: Merancang API yang mengizinkan seleksi atribut granular (mengurangi *over-fetching*) yang terintegrasi langsung ke dalam *dynamic database query projection* guna mencegah inefisiensi alokasi memori I/O.
4. **Melakukan Benchmarking Komparatif Serialisasi Biner vs Teks**: Mengukur latensi, utilisasi CPU, throughput, dan ukuran payload antara JSON, Protocol Buffers (Protobuf), dan Apache Avro pada berbagai variasi payload throughput tinggi.
5. **Menerapkan Enkapsulasi Opaque Cursor**: Mengonstruksi token cursor yang aman, *tamper-proof*, dan terabstraksi dari struktur internal skema database menggunakan enkoding/enkripsi deterministik.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                              [API DATA DELIVERY PIPELINE]
                                           |
         +---------------------------------+---------------------------------+
         |                                 |                                 |
         v                                 v                                 v
[CONTENT NEGOTIATION]             [DATA WINDOWING]                  [DATA ENCODING]
  ├── Proactive (Client-driven)     ├── Offset-based (LIMIT/OFFSET)   ├── Textual (JSON)
  │     ├── Accept: application/*   │     └── O(N) Degradation        │     └── Human-readable, bloated
  │     └── Accept-Encoding: gzip   ├── Keyset-based (WHERE id > x)   ├── Binary (Protobuf)
  ├── Reactive (Server-driven)      │     └── O(log N) B-Tree Seek    │     └── Field tags, Varints
  └── HTTP Caching Semantics        └── Cursor-based                  └── Schema-dependent (Avro)
        └── Vary: Accept, ...             └── Opaque Base64/Crypto          └── Confluent Schema Registry
                                           |
                                           v
                                  [BANDWIDTH REDUCTION]
                                    └── Sparse Fieldsets (?fields=id,name)
                                          └── Query Projection (SELECT id, name)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pada skala sistem enterprise dan microservices terdistribusi dengan throughput jutaan request per detik (RPS), kegagalan mendesain representasi data dan transfer layer menyebabkan inefisiensi yang eksponensial.

1. **Biaya Jaringan dan Egress**: Serialisasi JSON yang verbose mengirimkan metadata redundan (kunci string berulang) pada setiap record. Pada transfer data terdistribusi multi-region, 60–80% bandwidth terbuang hanya untuk membaca karakter format teks ketimbang muatan data aktual.
2. **Database Crash Akibat Deep Pagination**: Penggunaan `OFFSET 1000000 LIMIT 20` memaksa storage engine membaca 1.000.020 tuple dari disk/buffer pool, menyusunnya di memori, membuang 1.000.000 baris pertama, dan hanya mengembalikan 20 baris. Operasi ini menguras CPU dan I/O IOPS database secara masif.
3. **Over-fetching Memori pada Service Consumer**: Mengirimkan objek raksasa berisi 50 field ketika consumer hanya membutuhkan status transaksi membebani *Garbage Collector* (GC) pada microservices hulu dan hilir, memicu spike latensi p99.
4. **Cache Inconsistency**: Kesalahan penanganan Content Negotiation HTTP tanpa konfigurasi header `Vary` yang benar memicu CDN menyajikan payload JSON kepada client yang meminta format Protobuf, merusak contract API dan menyebabkan pemadaman sistem (*system outage*).

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Content Negotiation (ConNeg)
Mekanisme yang didefinisikan dalam RFC 7231, memungkinkan client dan server menyepakati format representasi data terbaik untuk dikirimkan melalui koneksi HTTP.
* **Proactive Negotiation**: Client mengirimkan preferensi media type via header `Accept`, preferensi karakter via `Accept-Charset`, serta kompresi via `Accept-Encoding`, dilengkapi pembobotan kualitas (*q-factor*, rentang 0.0 s.d. 1.0).
* **Vary Header**: Sinyal bagi HTTP cache proxy (seperti Varnish, Cloudflare, NGINX) bahwa entitas cache harus diindeks berdasarkan kombinasi URL *dan* header request tertentu (contoh: `Vary: Accept, Accept-Encoding`).

### 2. Paradigma Paginasi Data
* **Offset Pagination**: Paginasi berbasis nomor halaman (*page number*) dan batas per halaman (*page size*). Diterjemahkan menjadi statemen `LIMIT m OFFSET n`.
* **Keyset Pagination**: Paginasi yang memanfaatkan nilai kolom berindeks dari baris terakhir yang diambil (*last seen record*) sebagai referensi pencarian record selanjutnya secara langsung (`WHERE (created_at, id) < (prev_created_at, prev_id)`).
* **Cursor Pagination**: Bentuk lanjutan dari Keyset Pagination di mana tuple nilai referensi dienkapsulasi menjadi string opaque (terenkripsi atau di-*encode* base64url) yang aman, tidak dapat dimanipulasi oleh consumer, serta mengabstraksi struktur query database di belakangnya.

### 3. Sparse Fieldsets
Spesifikasi (dipopulerkan oleh JSON:API dan GraphQL) yang memberikan otorisasi kepada client untuk meminta hanya subset kolom tertentu dari resource (`GET /users?fields=id,email,status`). Tujuannya memangkas beban parsing JSON, menghemat alokasi buffer memori, dan mengoptimalkan query database menjadi *Index-Only Scan* / projection query.

### 4. Serialisasi Biner (Protobuf vs Avro vs JSON)
* **JSON**: Format berbasis teks tanpa skema wajib saat runtime; *self-describing*, mudah di-debug manusia, namun sangat lambat dalam proses parsing dan membutuhkan ruang penyimpanan besar.
* **Protocol Buffers (Protobuf)**: Format binary serialization yang dikembangkan Google. Memanfaatkan compiler IDL (`protoc`) untuk menghasilkan representasi biner kompak berbasis *field tags*, *varints*, dan *zigzag encoding*. Skema embedded pada compiled code.
* **Apache Avro**: Framework serialisasi data yang heavily relying pada dynamic skema berbasis JSON. Data biner Avro tidak menyertakan tag atau tipe kolom dalam payload; pembacaan *hanya* dapat dilakukan jika sistem membaca payload bersamaan dengan skema schema definitions (biasanya diresolusi melalui Confluent Schema Registry).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Mekanisme Internal Paginasi: Database Engine Execution

#### A. Anatomi Offset Pagination
Ketika query dieksekusi:
```sql
SELECT id, name, created_at FROM orders ORDER BY created_at DESC LIMIT 10 OFFSET 100000;
```
1. Engine membaca B-Tree index pada kolom `created_at`.
2. Engine menelusuri leaf nodes B-Tree dan melakukan *table lookup* (Heap Scan) untuk **100.010 baris data**.
3. Baris 1 hingga 100.000 disimpan sementara dalam buffer memory kemudian di-*discard* (dibuang).
4. Sisa 10 baris terakhir dikembalikan ke client.
5. Kompleksitas: $\mathcal{O}(N + M)$ di mana $N$ adalah nilai offset dan $M$ adalah limit.

#### B. Anatomi Keyset Pagination
Ketika query dieksekusi:
```sql
SELECT id, name, created_at 
FROM orders 
WHERE (created_at, id) < ('2023-10-27 10:00:00.000000', 482910)
ORDER BY created_at DESC, id DESC 
LIMIT 10;
```
1. Menggunakan Composite Index `(created_at DESC, id DESC)`.
2. Engine melakukan **B-Tree Seek** langsung menuju node daun yang cocok dengan koordinat tuple `('2023-10-27 10:00:00.000000', 482910)`.
3. Engine membaca tepat **10 baris berikutnya** secara traversal sekuensial pada leaf node.
4. Nol baris dibuang sia-sia.
5. Kompleksitas: $\mathcal{O}(\log K + M)$ di mana $K$ adalah total baris tabel dan $M$ adalah limit.

### Mekanisme Wire Format Encoding Protobuf vs Avro

#### Protobuf Wire Format
Protobuf membuang nama field. Payload disusun atas record berpasangan: `(Key, Value)`.
* **Key** adalah integer 32-bit yang mengompresi Field Number dan Wire Type:
  $$\text{Key} = (\text{field\_number} \ll 3) \mid \text{wire\_type}$$
* Nilai integer dikompresi menggunakan format **Varint** (Variable-Length Quantity): memecah integer menjadi segmen 7-bit, dengan bit paling signifikan (MSB) bertindak sebagai flag kontinuitas (`1` = bit selanjutnya masih bagian dari integer, `0` = akhir byte).

```
Nilai integer 300:
Representasi biner 300: 00000001 00101100
Pecah 7-bit:            [0000010] [0101100]
Reverse (Little-endian):[0101100] [0000010]
Set MSB flag:           10101100  00000010  -> Hex: AC 02
```

#### Avro Encoding
Avro tidak menyertakan field number maupun data type ke dalam wire bytes.
* Nilai dikompresi berurutan sesuai skema: `[Value 1][Value 2][Value 3]`.
* Karena ketiadaan identitas field dalam wire format, deserializer **wajib** memiliki akses ke salinan schema exact yang digunakan oleh serializer. Resolver mencocokkan *Writer's Schema* dengan *Reader's Schema*.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Perbandingan Alur Eksekusi Database: Offset vs Keyset

```
OFFSET PAGINATION: O(N) Scan Overhead
+-------------------------------------------------------------------------+
| Disk / Buffer Pool                                                      |
| [Row 1] [Row 2] ... [Row 100,000] [Row 100,001] ... [Row 100,010]       |
+-------------------------------------------------------------------------+
       |                                      |
       v (Engine reads ALL 100,010 rows)       v (Takes only 10 rows)
+-----------------------------------+     +-------------------------------+
| DISCARDED DATA MEMORY DUMP        |     | RETURN TO CLIENT (LIMIT 10)   |
| (100,000 rows fetched & dumped)   |     | Rows: 100,001 - 100,010       |
+-----------------------------------+     +-------------------------------+
Impact: High Disk I/O, High CPU, Latency spikes on high page numbers.


KEYSET PAGINATION: O(log N) Direct Index Seek
+-------------------------------------------------------------------------+
| B-Tree Composite Index (created_at, id)                                 |
|                     [Root Node]                                         |
|                    /           \                                        |
|             [Internal]        [Internal]                                |
|             /        \        /        \                                |
|         [Leaf]      [Leaf]  [Target Leaf]                               |
+----------------------------------|--------------------------------------+
                                   | DIRECT SEEK POINTER via WHERE clause
                                   v
+-------------------------------------------------------------------------+
| Disk Heap / Clustered Index (Scan directly takes exact 10 records)      |
| [Target: 2023-10-27, ID: 482910] -> [Rec 1] [Rec 2] ... [Rec 10]        |
+-------------------------------------------------------------------------+
Impact: Predictable O(1) page-to-page performance, constant CPU/RAM.
```

### 2. Content Negotiation Pipeline & Cache Invalidation

```
+--------+            +-------------------+            +------------------+
| Client |            | Reverse Proxy/CDN |            | API Origin Node  |
+--------+            +-------------------+            +------------------+
    |                           |                               |
    | GET /api/v1/orders/101    |                               |
    | Accept: application/x-protobuf                            |
    | Accept-Encoding: gzip     |                               |
    |-------------------------->|                               |
    |                           | Cache MISS                    |
    |                           | Key: /orders/101              |
    |                           | (No cache variant yet)        |
    |                           |------------------------------>|
    |                           |                               | Evaluate Accept headers
    |                           |                               | Marshal to Protobuf binary
    |                           |                               | Compress with Gzip
    |                           |<------------------------------|
    |                           | 200 OK                        |
    |                           | Content-Type: application/x-protobuf
    |                           | Vary: Accept, Accept-Encoding |
    |                           | Content-Encoding: gzip        |
    |                           | Cache-Control: max-age=3600   |
    |                           |-------------------------------+
    |                           | Store Cache Variant:          |
    |                           | [/orders/101] +               |
    |                           | [app/x-protobuf + gzip]       |
    |<--------------------------|                               |
    | Payload: <Protobuf Gzipped>                               |
    |                           |                               |
    |--- Next Request: Same URL, Different Accept --------------|
    |                           |                               |
    | GET /api/v1/orders/101    |                               |
    | Accept: application/json  |                               |
    |-------------------------->|                               |
    |                           | Cache MISS (Variant Mismatch) |
    |                           | Fetch correct type from origin|
    |                           |------------------------------>|
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Contoh berikut menunjukkan implementasi native Content Negotiation parser sederhana pada Go standard library, mengevaluasi q-factors dari header `Accept`.

```go
package main

import (
	"fmt"
	"net/http"
	"strconv"
	"strings"
)

type MediaTypePreference struct {
	Type    string
	QFactor float64
}

func parseAcceptHeader(header string) []MediaTypePreference {
	var preferences []MediaTypePreference
	if header == "" {
		return []MediaTypePreference{{"*/*", 1.0}}
	}

	parts := strings.Split(header, ",")
	for _, part := range parts {
		subparts := strings.Split(strings.TrimSpace(part), ";")
		mediaType := subparts[0]
		qfactor := 1.0

		for _, param := range subparts[1:] {
			param = strings.TrimSpace(param)
			if strings.HasPrefix(param, "q=") {
				if val, err := strconv.ParseFloat(param[2:], 64); err == nil {
					qfactor = val
				}
			}
		}
		preferences = append(preferences, MediaTypePreference{Type: mediaType, QFactor: qfactor})
	}
	return preferences
}

func OrderHandler(w http.ResponseWriter, r *http.Request) {
	// Pastikan proxy downstream mengisolasi cache berdasarkan header Accept
	w.Header().Set("Vary", "Accept")

	acceptHeader := r.Header.Get("Accept")
	preferences := parseAcceptHeader(acceptHeader)

	chosenType := "application/json" // Default fallback
	for _, pref := range preferences {
		if pref.Type == "application/x-protobuf" {
			chosenType = "application/x-protobuf"
			break
		} else if pref.Type == "application/json" || pref.Type == "*/*" {
			chosenType = "application/json"
			break
		}
	}

	switch chosenType {
	case "application/x-protobuf":
		w.Header().Set("Content-Type", "application/x-protobuf")
		// Mengirimkan binary stream fiktif: [0x08, 0x96, 0x01] (Field 1, Varint 150)
		w.WriteHeader(http.StatusOK)
		w.Write([]byte{0x08, 0x96, 0x01})
	case "application/json":
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"order_id": 150}`))
	default:
		w.WriteHeader(http.StatusNotAcceptable)
		w.Write([]byte(`{"error": "Unsupported Media Type"}`))
	}
}

func main() {
	http.HandleFunc("/orders", OrderHandler)
	fmt.Println("Server running on :8080")
	http.ListenAndServe(":8080", nil)
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Implementasi produksi Cursor-based Pagination terintegrasi dengan Sparse Fieldsets menggunakan Golang, Postgres SQL Driver, dan Token Enkapsulasi Opaque Base64.

### 1. Definisi Model dan Cursor Opaque

```go
package main

import (
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"
)

// InternalCursor menyimpan posisi sekuensial penanda pembacaan
type InternalCursor struct {
	CreatedAt time.Time `json:"ca"`
	ID        int64     `json:"id"`
}

// EncodeCursor mengubah struct state internal menjadi opaque base64 safe string
func EncodeCursor(t time.Time, id int64) string {
	raw, _ := json.Marshal(InternalCursor{CreatedAt: t, ID: id})
	return base64.URLEncoding.EncodeToString(raw)
}

// DecodeCursor mendekode opaque token kembali ke bentuk koordinat data
func DecodeCursor(token string) (*InternalCursor, error) {
	bytes, err := base64.URLEncoding.DecodeString(token)
	if err != nil {
		return nil, errors.New("malformed_cursor")
	}
	var cur InternalCursor
	if err := json.Unmarshal(bytes, &cur); err != nil {
		return nil, errors.New("invalid_cursor_payload")
	}
	return &cur, nil
}
```

### 2. Dynamic Fieldset & Safe Query Engine

```go
type Order struct {
	ID        int64      `json:"id,omitempty"`
	Customer  *string    `json:"customer,omitempty"`
	Total     *float64   `json:"total,omitempty"`
	CreatedAt *time.Time `json:"created_at,omitempty"`
}

// AllowedFields mendefinisikan whitelist kolom untuk menghindari SQL Injection
var AllowedFields = map[string]string{
	"id":         "orders.id",
	"customer":   "orders.customer",
	"total":      "orders.total",
	"created_at": "orders.created_at",
}

func BuildDynamicQuery(fieldsParam string, cursor *InternalCursor, limit int) (string, []interface{}) {
	selectedFields := []string{}
	requested := strings.Split(fieldsParam, ",")

	for _, f := range requested {
		col, exists := AllowedFields[strings.TrimSpace(f)]
		if exists {
			selectedFields = append(selectedFields, col)
		}
	}

	// Always fallback to id and created_at for cursor integrity
	if len(selectedFields) == 0 {
		selectedFields = []string{"orders.id", "orders.customer", "orders.total", "orders.created_at"}
	}

	query := fmt.Sprintf("SELECT %s FROM orders ", strings.Join(selectedFields, ", "))
	args := []interface{}{}
	argCounter := 1

	if cursor != nil {
		query += fmt.Sprintf("WHERE (orders.created_at, orders.id) < ($%d, $%d) ", argCounter, argCounter+1)
		args = append(args, cursor.CreatedAt, cursor.ID)
		argCounter += 2
	}

	query += fmt.Sprintf("ORDER BY orders.created_at DESC, orders.id DESC LIMIT $%d", argCounter)
	args = append(args, limit+1) // Fetch 1 baris ekstra untuk mendeteksi apakah has_next_page bernilai true

	return query, args
}
```

### 3. API Handler Layer

```go
type ResponsePayload struct {
	Data       []map[string]interface{} `json:"data"`
	Pagination PaginationMeta           `json:"pagination"`
}

type PaginationMeta struct {
	NextCursor string `json:"next_cursor,omitempty"`
	HasMore    bool   `json:"has_more"`
	Limit      int    `json:"limit"`
}

func GetOrdersHandler(db *sql.DB) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Vary", "Accept, Accept-Encoding")

		// 1. Ekstraksi Query Parameters
		limit := 10
		if l := r.URL.Query().Get("limit"); l != "" {
			if parsedL, err := strconv.Atoi(l); err == nil && parsedL > 0 && parsedL <= 100 {
				limit = parsedL
			}
		}

		var cursor *InternalCursor
		if curStr := r.URL.Query().Get("cursor"); curStr != "" {
			var err error
			cursor, err = DecodeCursor(curStr)
			if err != nil {
				w.WriteHeader(http.StatusBadRequest)
				w.Write([]byte(`{"error": "Invalid cursor token provided"}`))
				return
			}
		}

		fieldsParam := r.URL.Query().Get("fields")

		// 2. Build Query & Eksekusi ke Database
		query, args := BuildDynamicQuery(fieldsParam, cursor, limit)
		rows, err := db.Query(query, args...)
		if err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"error": "Database error execution"}`))
			return
		}
		defer rows.Close()

		// 3. Dynamic Column Mapping
		cols, _ := rows.Columns()
		results := make([]map[string]interface{}, 0)

		var lastID int64
		var lastCreatedAt time.Time

		for rows.Next() {
			columns := make([]interface{}, len(cols))
			columnPointers := make([]interface{}, len(cols))
			for i := range columns {
				columnPointers[i] = &columns[i]
			}

			if err := rows.Scan(columnPointers...); err != nil {
				continue
			}

			rowMap := make(map[string]interface{})
			for i, colName := range cols {
				val := columnPointers[i].(*interface{})
				rowMap[colName] = *val
				
				// Simpan metadata cursor secara dinamis
				if colName == "id" {
					if v, ok := (*val).(int64); ok { lastID = v }
				}
				if colName == "created_at" {
					if v, ok := (*val).(time.Time); ok { lastCreatedAt = v }
				}
			}
			results = append(results, rowMap)
		}

		// 4. Hitung State Window Halaman Berikutnya
		hasMore := false
		if len(results) > limit {
			hasMore = true
			results = results[:limit] // Potong kembali ke ukuran limit awal
		}

		var nextCursorToken string
		if hasMore && len(results) > 0 {
			nextCursorToken = EncodeCursor(lastCreatedAt, lastID)
		}

		response := ResponsePayload{
			Data: results,
			Pagination: PaginationMeta{
				NextCursor: nextCursorToken,
				HasMore:    hasMore,
				Limit:      limit,
			},
		}

		json.NewEncoder(w).Encode(response)
	}
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

### 1. Matrix Komparasi Paginasi

| Dimensi | Offset Pagination (`LIMIT/OFFSET`) | Keyset Pagination (`WHERE k > v`) | Cursor Pagination (Opaque Token) |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Query DB** | $\mathcal{O}(N)$ — Semakin lambat di halaman dalam. | $\mathcal{O}(\log N)$ — Konsisten via Index Seek. | $\mathcal{O}(\log N)$ — Konsisten via Index Seek. |
| **Performa Deep Paging** | Sangat Buruk (Degradasi eksponensial). | Superior (Latensi flat terprediksi). | Superior (Latensi flat terprediksi). |
| **Random Page Jump** | Mendukung jump acak (Halaman 1 langsung ke 50). | Tidak Mendukung (Hanya traversal sekuensial). | Tidak Mendukung (Wajib request pointer berantai). |
| **Konsistensi Real-time** | Rentan data drift & duplikasi saat ada data insert/delete. | Konsisten penuh (Anchor pointer mutlak). | Konsisten penuh (Anchor pointer mutlak). |
| **Abstraksi Keamanan** | Rendah (Skema DB terekspos jelas). | Menengah (Nama kolom terlihat di query param). | Tinggi (Parameter pointer dienkapsulasi). |

### 2. Matrix Komparasi Serialisasi Data

| Karakteristik | JSON (RFC 8259) | Protocol Buffers v3 | Apache Avro |
| :--- | :--- | :--- | :--- |
| **Representasi Wire** | Textual UTF-8 | Binary (Varints, Tag-Length-Value) | Binary (Pure values sequential) |
| **Payload Footprint** | Besar (Baseline: 100%) | Sangat Kecil (20% – 35% dari JSON) | Terkecil (15% – 25% dari JSON) |
| **Throughput CPU Parsing** | Rendah (Parsing string parsing & regex intensif) | Tinggi (Operasi bitwise & pointer shifts) | Tinggi (Direct mapped parsing via schema) |
| **Kebutuhan Schema** | Skema bersifat opsional (Loose contract) | Wajib via `.proto` (IDL ahead-of-time compile) | Wajib via JSON Schema / Schema Registry |
| **Human Debuggability**| Native (dapat dibaca via cURL & browser) | Sulit (harus didekode via proto schema) | Mustahil tanpa schema definition file |
| **Ekosistem & Support** | Universal di seluruh bahasa dan OS | Luas di industri (gRPC, Microservices) | Dominan pada Event-driven/Kafka Streaming |

---

## SEKSI 11 — BEST PRACTICES

1. **Composite B-Tree Indexes Wajib Deterministik**: Saat menerapkan Keyset pagination, jangan mengurutkan hanya berdasarkan kolom non-unik seperti `created_at`. Selalu sertakan primary key unik di urutan akhir: `CREATE INDEX idx_orders_pagination ON orders (created_at DESC, id DESC);`.
2. **Kompensasi Header `Vary` untuk Cache Poisoning**: Wajib mengirimkan `Vary: Accept, Accept-Encoding` jika endpoint yang sama menyajikan variasi payload (JSON, Protobuf, Brotli, Gzip). Kegagalan melakukan ini mengakibatkan edge-proxy melayani data biner gRPC/Protobuf ke Web Browser yang meminta JSON.
3. **Whitelist dan Sanitasi Sparse Fieldsets**: Jangan menginjeksikan input client `?fields=...` mentah ke dalam klausa SQL SELECT untuk mencegah serangan SQL Injection dan Database Denial of Service (eksploitasi mengeksekusi ekspresi subquery mahal).
4. **Enkripsi Cursor Sensitif**: Jika kolom keyset mengekspos identifier sekuensial transaksi keuangan atau timestamp privat, gunakan enkripsi simetris (AES-128-GCM) bukan sekadar Base64 encoding saat mengonstruksi cursor string ke client.
5. **Fail Safely dengan Maximum Limit**: Batasi nilai maksimal limit halaman (misalnya batas keras $M \le 100$). Tolak request atau enforce batasan otomatis jika client meminta limit yang berpotensi membebani shared memory pool engine database.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. The Infinite Skip / Deep-Offset Death Spiral
**Masalah**: Developer mengadopsi Offset pagination pada endpoint publik table audit log atau transaksi besar.
```sql
-- Client membuka halaman 10.000:
SELECT * FROM audit_logs ORDER BY id LIMIT 50 OFFSET 500000;
```
Ketika bot scraper merayapi seluruh tabel hingga halaman dalam, database kehabisan I/O IOPS karena membaca jutaan record dan langsung drop koneksi.
**Solusi**: Migrasi secara menyeluruh ke cursor pagination untuk data tabular time-series berukuran masif. Batasi pagination offset maksimal hingga 1.000 baris pertama.

### 2. Missing Vary Header Pada ConNeg
**Masalah**: Service mendukung JSON dan Protobuf pada path `/products/{id}`. Client iOS meminta Protobuf, Origin mengembalikan biner Protobuf. CDN meng-cache biner ini tanpa validasi request header. Client Web meminta URL yang sama via browser (Accept: application/json). CDN menyajikan cached protobuf binary, menyebabkan parsing error pada frontend JavaScript.
**Solusi**: Tambahkan header eksplisit di response level:
```http
HTTP/1.1 200 OK
Content-Type: application/x-protobuf
Vary: Accept
```

### 3. Data Inconsistency (Duplicate/Skipped Records)
**Masalah**: Menggunakan offset pagination pada feed berita aktif. Ketika user berada di page 1 dan membaca 10 record, 2 item baru masuk ke database di urutan teratas. Saat user menekan page 2 (`OFFSET 10`), 2 record terakhir dari page 1 terdorong ke posisi 11 dan 12. User melihat data yang sama dua kali.
**Solusi**: Gunakan Keyset pagination dengan immutable record ID. Record baru yang masuk di bagian atas tidak akan mengubah posisi relative traversal pointer cursor yang dipegang oleh client.

### 4. Overfetching Mengabaikan SELECT Projection
**Masalah**: Developer mengimplementasikan sparse fieldset pada layer serialisasi (Jackson/Go JSON encoder) tetapi mengeksekusi `SELECT *` pada layer database database.
```go
// Anti-pattern: Database tetap membaca disk untuk 40 kolom,
// memori dialokasikan penuh, hanya dibuang saat JSON Marshal.
db.Query("SELECT * FROM large_table")
```
**Solusi**: Terapkan Dynamic Query Projection. Pastikan Sparse Fieldset query parameter mengubah statemen query database hingga ke tingkat I/O data fetcher.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Deteksi & Optimasi Deep Paginasi (Tingkat: Menengah)
* **Skenario**: Anda mendapati query sistem laporan melambat seiring bertambahnya data:
  ```sql
  EXPLAIN ANALYZE SELECT id, tenant_id, amount, created_at 
  FROM payments 
  WHERE tenant_id = 42 
  ORDER BY created_at DESC 
  LIMIT 20 OFFSET 500000;
  ```
* **Tugas**:
  1. Identifikasi metrik bottleneck pada output plan (`Rows Removed by Filter`, `Buffers Read`).
  2. Susun ulang query tersebut menggunakan Cursor/Keyset Pagination pattern.
  3. Tuliskan DDL Composite Index yang tepat untuk mendukung eksekusi query baru dengan target cost plan mendekati $\mathcal{O}(1)$.

### Latihan 2: Implementasi Secure Tamper-Proof Cursor (Tingkat: Lanjut)
* **Skenario**: Sistem cursor yang menggunakan plain Base64 string rentan dimanipulasi oleh user dengan mengubah payload tanggal atau ID agar bisa membaca data record tenant lain.
* **Tugas**:
  1. Buat modul enkapsulasi cursor di bahasa pilihan Anda (Go/Node.js/Python) yang mengikutsertakan HMAC-SHA256 signature ke dalam base64 payload.
  2. Implementasikan fungsi validasi cursor yang membatalkan request (HTTP 400 Bad Request) jika cursor string telah diubah 1 bit saja oleh pihak ketiga.

### Latihan 3: Protobuf Dynamic Content Negotiation Dispatcher (Tingkat: Lanjut)
* **Skenario**: Bangun microservice minimalis yang memiliki 1 buah struct User `(ID: int64, Name: string, Email: string)`.
* **Tugas**:
  1. Siapkan schema `.proto` dan kompilasi menjadi Go/Java struct/class.
  2. Buat routing handler HTTP yang memeriksa header `Accept`.
  3. Jika `Accept: application/x-protobuf`, serialisasikan model menggunakan compiler protobuf binary.
  4. Jika `Accept: application/json` atau kosong, serialisasikan model menggunakan json encoder standar.
  5. Konfigurasikan header HTTP response code, content type, dan cache control headers secara komprehensif.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa fungsi utama dari header response `Vary: Accept` dalam sistem arsitektur berbasis Content Negotiation?**
   * A. Memaksa server memvalidasi tipe MIME request setiap detik.
   * B. Menginstruksikan HTTP Cache/CDN untuk mengindeks salinan cache secara terpisah berdasarkan nilai header `Accept` request client.
   * C. Mencegah format transfer data diubah oleh sistem load balancer.
   * D. Menolak otomatis semua request yang tidak memiliki header `Accept`.
   * *Jawaban yang Benar*: **B**. HTTP cache menggunakan header yang terdaftar dalam `Vary` sebagai secondary composite cache key agar response tidak tertukar antar-client yang membutuhkan representasi format data berbeda.

2. **Mengapa Keyset pagination secara dramatis lebih cepat daripada Offset pagination pada tabel berjumlah 100 juta baris?**
   * A. Keyset pagination mengompresi data tabel ke memori buffer database.
   * B. Keyset pagination menggunakan query background thread paralel.
   * C. Keyset pagination melakukan B-Tree Direct Seek menuju koordinat index secara spesifik tanpa perlu membaca dan membuang baris data sebelumnya.
   * D. Offset pagination mematikan fitur indexing tabel relational.
   * *Jawaban yang Benar*: **C**. Offset pagination menelusuri leaf-nodes index dari awal sebanyak $N+M$ records lalu membuang $N$ records secara sia-sia, sedangkan Keyset pagination meloncat langsung via pointer B-Tree traversal ke lokasi record menggunakan index lookup $\mathcal{O}(\log K)$.

3. **Manakah dari format serialisasi berikut yang mewajibkan ketersediaan schema definition file exact yang sama pada kedua belah pihak (client dan server) tanpa field-tags dalam byte stream datanya?**
   * A. JSON.
   * B. Apache Avro.
   * C. Protocol Buffers v3.
   * D. MessagePack.
   * *Jawaban yang Benar*: **B**. Avro tidak menyimpan tag atau identitas kolom dalam wire format datanya sama sekali, sehingga pembacaan payload biner sepenuhnya bergantung pada pencocokan urutan dan tipe skema (*Writer's Schema* vs *Reader's Schema*).

4. **Kelemahan paling signifikan dari Keyset / Cursor Pagination murni dibandingkan Offset Pagination adalah:**
   * A. Tidak mampu mengurutkan data berdasarkan urutan tanggal.
   * B. Membutuhkan kapasitas penyimpanan disk dua kali lipat.
   * C. Ketidakmampuan melompat langsung secara acak ke halaman tertentu (misalnya melompat dari halaman 1 langsung ke halaman 50).
   * D. Hanya mendukung koneksi HTTP/2.
   * *Jawaban yang Benar*: **C**. Karena Keyset traversal membutuhkan tuple referensi dari record terakhir halaman aktif, sistem tidak dapat mengkalkulasi koordinat awal halaman di masa depan tanpa menelusuri data halaman-halaman perantaranya secara berurutan.

5. **Apa risiko keamanan utama jika cursor pagination dirancang dengan mengekspos identifier internal (misal: ID sekuensial) yang hanya di-*encode* menggunakan Base64 standar?**
   * A. SQL Injection via Base64 string payload.
   * B. Memory buffer overflow pada reverse proxy server.
   * C. Parameter Tampering dan Data Enumeration: Client dapat mendekode string, menebak interval ID, dan membaca data yang seharusnya tidak diotorisasi.
   * D. Cache poisoning pada Content Delivery Network.
   * *Jawaban yang Benar*: **C**. Base64 bukanlah mekanisme kriptografi (bukan enkripsi). Siapa pun dapat mendekode payload Base64, memanipulasi parameter ID, dan merekonstruksi cursor token palsu guna merayapi data yang bukan hak aksesnya.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **Internet Engineering Task Force (IETF)**:
   * *RFC 7231: Hypertext Transfer Protocol (HTTP/1.1): Semantics and Content* (Seksi 5.3: Content Negotiation, Seksi 7.1.4: Vary Header).
   * *RFC 7396: JSON Merge Patch*.
2. **Spesifikasi Formal & Dokumentasi Proyek**:
   * *Google Protocol Buffers Developer Guide: Encoding Internals* (developers.google.com/protocol-buffers/docs/encoding).
   * *Apache Avro Specification* (avro.apache.org/docs/current/spec.html).
   * *JSON:API Specification v1.1* (jsonapi.org/format/#fetching-sparse-fieldsets).
3. **Buku & Paper Rekomendasi**:
   * Kleppmann, Martin. (2017). *Designing Data-Intensive Applications: The Big Ideas Behind Reliable, Scalable, and Maintainable Systems*. O'Reilly Media. (Chapter 4: Encoding and Evolution).
   * Winand, Markus. (2012). *SQL Performance Explained*. (Paginasi B-Tree Seek Mechanics).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

```
===================================================================================================
                                  API ENGINE DATA SERIALIZATION MATRIX
===================================================================================================
FORMAT     SCHEMALESS?    WIRE FORMAT    CPU USAGE     LATENCY     BEST USE-CASE
---------------------------------------------------------------------------------------------------
JSON       Ya             Text (UTF-8)   Tinggi        Moderat     Public APIs, Web Clients
Protobuf   Tidak          Binary (TLV)   Rendah        Sangat Rendah Microservices, High RPS gRPC
Avro       Tidak          Pure Binary    Sangat Rendah Terendah    Streaming Pipelines, Kafka Event Bus
===================================================================================================
PAGINATION STRATEGY OVERVIEW
---------------------------------------------------------------------------------------------------
TIPE                DB COMPLEXITY   CONSISTENCY   RANDOM ACCESS   PRIMARY USE-CASE
Offset (LIMIT/OFF)  O(N)            Rentan Drift  Ya              Admin Portals (Data < 10k items)
Keyset (Direct)     O(log N)        Ketat         Tidak           High-Scale Timeline Feeds
Cursor (Opaque)     O(log N)        Ketat         Tidak           Public Scalable Enterprise APIs
===================================================================================================
```

* Content Negotiation bukan sekadar membaca format data request, melainkan menjamin stabilitas ekosistem cache terdistribusi melalui koordinasi header HTTP `Vary`.
* Penggunaan `LIMIT` dan `OFFSET` pada skala dataset besar adalah anti-pattern performa. Gunakan Keyset pagination dengan pointer tuple terindeks untuk menjamin latensi flat $\mathcal{O}(\log N)$.
* Sparse Fieldset harus diintegrasikan langsung ke query database layer (Query Dynamic Projection) untuk mengurangi memory overhead dan saturasi I/O bus secara optimal.
* Pilihan format serialisasi adalah kompromi (*trade-off*) antara kemudahan integrasi dan human readability (JSON) berbanding performa throughput dan efisiensi utilisasi CPU/Jaringan (Protobuf/Avro).

---

## SEKSI 17 — GLOSARIUM

* **Varint (Variable-length Integer)**: Metode serialisasi integer yang menggunakan satu atau lebih byte, di mana nilai yang lebih kecil mengonsumsi jumlah byte yang lebih sedikit.
* **Tag-Length-Value (TLV)**: Pola encoding biner di mana setiap elemen data didahului oleh nomor identitas field (tag), ukuran panjang byte (length), dan payload data aktual (value).
* **Opaque Cursor**: Nilai representasi status paginasi yang strukturnya dienkapsulasi dan diabstraksikan, sehingga format internalnya tidak dapat dan tidak boleh dianalisis oleh client.
* **B-Tree Seek**: Algoritma pencarian indeks database yang menuruni tree nodes dari root ke leaf secara langsung dengan kompleksitas waktu logaritmik $\mathcal{O}(\log N)$.
* **B-Tree Scan**: Penelusuran berurutan horizontal pada leaf nodes di sepanjang link list B-Tree.
* **Cache Poisoning**: Kerusakan isi penyimpanan cache di mana server perantara (reverse proxy) menyajikan data respon yang salah atau berbahaya ke client akibat inkonsistensi cache key.
* **Proactive Content Negotiation**: Negosiasi format data yang diprakarsai oleh client melalui deklarasi eksplisit pada HTTP headers sebelum resource diproses oleh server.
* **Dynamic Query Projection**: Teknik penyusunan query database di mana kolom pada statemen `SELECT` ditentukan secara dinamis saat runtime sesuai field yang diminta pemanggil.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Pedoman Pengajaran
* **Visualisasikan B-Tree Traversal**: Saat menjelaskan transisi dari Offset ke Keyset, jangan hanya memperlihatkan syntax SQL. Gambarkan struktur leaf-nodes B-Tree di papan tulis. Tunjukkan bagaimana pointer database terpaksa berjalan $N$ langkah pada offset pagination, dibandingkan dengan lompatan instan pada keyset.
* **Demonstrasi Live Bandwidth**: Gunakan wireshark atau cURL (`curl -w "%{size_download}\n"`) untuk membandingkan transfer object kompleks 1.000 items dalam bentuk JSON mentah vs Protobuf terkompresi. Visualisasi perbandingan ukuran bytes ini memberikan impresi nyata bagi peserta didik.
* **Perangkap Implementasi Keyset**: Ingatkan peserta didik bahwa Keyset Pagination **hanya berfungsi** jika kolom yang dijadikan dasar pengurutan dijamin memiliki urutan strictly monotonic (unik dan deterministik). Menjadikan kolom duplikat sebagai acuan keyset tunggal akan memicu bug *skipping records*.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0** (Inisialisasi Materi):
  * Modul komprehensif Data Serialization, Filtering, dan Content Negotiation diterbitkan.
  * Penambahan implementasi komparasi Offset vs Keyset vs Cursor pagination engine.
  * Penyusunan modul Go dinamis: Cursor Base64 token generation + Dynamic Database Projection whitelisting.
  * Benchmarking mendalam internal wire-format encoding Protobuf vs Avro vs JSON.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `ARCH-API-03-03` — API Authentication, Authorization, and Identity Propagation Patterns (OAuth2, OIDC, JWT, PASETO, MTLS).
* **Modul Saat Ini**: `ARCH-API-04-01` — Data Serialization, Filtering, & Content Negotiation.
* **Modul Berikutnya**: `ARCH-API-04-02` — Batch Processing, Bulk Operations, and Bulkhead API Rate Limiting Design.
* **Kembali ke Indeks**: `ARCH-API-00-00` — Kurikulum Utama API Architecture and System Design.