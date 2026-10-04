# Kurikulum Enterprise Architecture & System Design
## Topik: API Design
### BAB 08: Lifecycle, Versioning, and Evolution
#### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis & Mengisolasi Trade-Off Pola Versioning**: Memilih dan mengimplementasikan strategi versioning (URI Path, Custom Header, Content Negotiation/Accept Header) berdasarkan profiling beban sistem, topologi caching (CDN/Edge), serta kapabilitas client SDK.
- **Mendesain Non-Breaking Schema Evolution**: Menerapkan prinsip *Tolerant Reader*, aturan kompatibilitas skema terdistribusi (backward, forward, full compatibility), dan mitigasi deserialization hazards pada data contract berbasis JSON Schema dan Protocol Buffers.
- **Mengarsiteksi Dynamic Traffic Routing & API Mutation**: Membangun layer mediasi pada level API Gateway (Envoy/Go-based proxy) untuk traffic splitting (Canary/Blue-Green), shadow mirroring, dan dynamic payload transformation antara versi API.
- **Mengotomatisasi Lifecycle & Deprecation Engine**: Menerapkan standar RFC 8594 (`Sunset`), RFC draft-ietf-httpapi-deprecation-header (`Deprecation`), serta integrasi telemetri observability (Prometheus metrics) untuk mengidentifikasi consumer yang tertinggal.
- **Membangun CI/CD Verification Gate**: Mengintegrasikan automated contract testing (Consumer-Driven Contract Testing) untuk menggagalkan pipeline build saat terdeteksi schema drift atau breaking changes.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, Anda harus memahami:
- **HTTP/1.1 & HTTP/2 Specification**: RFC 9110 (HTTP Semantics), mekanisme negosiasi konten, caching directive, serta manipulasi header transit.
- **Modern API Styles**: Fondasi mendalam mengenai RESTful constraints, gRPC/Protobuf serialisation, dan GraphQL schema design.
- **Edge Routing & Proxy Concepts**: Konfigurasi dasar Reverse Proxy/API Gateway (Envoy, NGINX, atau Traefik), TLS termination, and L7 routing rules.
- **Distributed Systems Telemetry**: Distributed tracing (W3C Trace Context/OpenTelemetry) dan dimensional metric exposition (Prometheus).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Taksonomi Versioning & Karakteristik Transport Layer

Versioning bukan sekadar mengubah string URL; ini adalah keputusan arsitektural yang berdampak langsung pada lapisan L7 routing, HTTP cache efficiency, edge state, dan pipeline deserialisasi runtime.

```
+------------------------------------------------------------------------------------+
|                                 CONSUMER REQUEST                                   |
+------------------------------------------------------------------------------------+
         |                                |                               |
         v                                v                               v
 [URI Path Versioning]          [Header Versioning]             [Content Negotiation]
  GET /v2/orders/101             GET /orders/101                 GET /orders/101
                                 X-API-Version: 2024-05-01       Accept: application/vnd.company.v2+json
         |                                |                               |
+------------------------------------------------------------------------------------+
|                         L7 REVERSE PROXY / API GATEWAY                             |
|  - Parse Routing Key          - Vary: X-API-Version           - Vary: Accept       |
|  - CDN Edge Caching           - Path Rewriting                - Serialization Flow |
+------------------------------------------------------------------------------------+
         |                                |                               |
         +--------------------------------+-------------------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |         UPSTREAM MICROSERVICES        |
                      |   - Contract Deserializer (v1/v2)     |
                      |   - Business Domain Logic             |
                      +---------------------------------------+
```

1. **URI Path Versioning (`/v1/resource`)**:
   - *Mekanisme Internal*: Path routing eksplisit dieksekusi di edge tanpa perlu inspeksi header payload. URL bertindak sebagai resource identifier yang unik.
   - *Routing Engine Impact*: Lookup radix-tree sederhana pada router gateway (misal: `httprouter` atau Envoy route tables). Sangat ramah caching CDN secara *out-of-the-box* karena URL berbeda menciptakan *cache key* terisolasi.
   - *Kelemahan*: Pelanggaran murni terhadap prinsip REST—entitas yang sama memiliki multipel Uniform Resource Identifiers seiring waktu.

2. **Custom Header Versioning (`X-API-Version: 2` atau `API-Version: 2024-01-01`)**:
   - *Mekanisme Internal*: Router gateway harus membaca HTTP header map sebelum mengeksekusi routing logic. CDN harus dikonfigurasi untuk menyertakan custom header tersebut ke dalam *Cache Key Hash*.
   - *HTTP Spec Obligation*: Wajib mengembalikan respons dengan header `Vary: X-API-Version` untuk mencegah cache poisoning di shared intermediate caches.

3. **Content Negotiation / Vendor MIME-Type (`Accept: application/vnd.enterprise.v2+json`)**:
   - *Mekanisme Internal*: Memisahkan identitas resource (URI) dari representasi data (Payload Schema). Router mencocokkan parser serializer berdasarkan string MIME type.
   - *Kompleksitas*: Memerlukan parsing RFC 9110 media-type sub-parameters pada layer aplikasi, menaikkan footprint CPU pada throughput tinggi. Wajib menyertakan header `Vary: Accept`.

#### B. Teori Kompatibilitas Skema (Schema Evolution Theory)

Evolusi skema API enterprise harus mematuhi model validasi matematis untuk menjamin keandalan komunikasi antar-layanan:

```
Versi Skema V_lama (S_old)  --->  Himpunan Pesan Valid M(S_old)
Versi Skema V_baru (S_new)  --->  Himpunan Pesan Valid M(S_new)
```

| Tipe Kompatibilitas | Formula Himpunan | Penjelasan Operasional | Aturan Transformasi Skema |
| :--- | :--- | :--- | :--- |
| **Backward Compatible** | $M(S_{old}) \subseteq M(S_{new})$ | Consumer V_lama dapat membaca payload yang digenerate oleh Producer V_baru. | Menambah field opsional baru; tidak boleh menambah validasi mandatory baru. |
| **Forward Compatible** | $M(S_{new}) \subseteq M(S_{old})$ | Consumer V_baru dapat membaca payload yang digenerate oleh Producer V_lama. | Menghapus field opsional; reader mentoleransi field yang hilang. |
| **Full Compatible** | $M(S_{old}) = M(S_{new})$ | Kombinasi Backward dan Forward. Client lama dan baru dapat bertukar pesan secara bebas. | Hanya boleh menambah/menghapus atribut non-wajib dengan nilai default. |
| **Breaking (None)** | $M(S_{old}) \cap M(S_{new}) \neq M$ | Ketidakcocokan struktural total. Kegagalan deserialisasi instan. | Mengubah tipe data, mengganti nama field, menambah validasi required. |

*Prinsip Tolerant Reader (Postel's Robustness Principle)*:
Aplikasi backend dan consumer SDK harus dirancang untuk:
1. Mengabaikan field yang tidak dikenali pada incoming payload (jangan return HTTP 400 hanya karena ada unknown JSON keys).
2. Memetakan null/undefined ke zero-value atau default state tanpa runtime panic/exception.
3. Selalu mengirim representasi data yang paling ketat dan terstandarisasi saat bertindak sebagai producer.

#### C. Arsitektur Gateway-Mediated Dynamic Routing & Mutation

Saat migrasi enterprise dari v1 ke v2 dilakukan secara masif, mengorbankan backward compatibility secara langsung adalah anti-pattern. Solusinya adalah menempatkan *Dynamic Payload Mutation Engine* pada gateway atau BFF (Backend-For-Frontend) layer.

```
[Client v1] ---> (Payload v1) ---> [ API Gateway / Ingress Controller ]
                                       |
                                       +--> [Schema Translator / WASM Plugin]
                                                | Mengonversi Model v1 -> Model v2
                                                | Inject Field Defaults
                                                v
                                            [Service Core Backend v2]
```

---

### 4. Why & What

#### Problem Statement: Naive Versioning Hell
Organisasi enterprise sering kali terjebak dalam "Naive Versioning", yaitu membuat copy-paste endpoint/controller (`/v1/checkout` -> `/v2/checkout` -> `/v3/checkout`) di codebase yang sama. Hal ini memicu:
- **Code Duplication & Divergence**: Logic payment/fraud processing diduplikasi, menyebabkan perbaikan bug di v2 tidak terpropagasi ke v1.
- **Cache Invalidation Nightmare**: Satu resource yang diubah via v2 tidak menginvalir cache v1 di CDN edge.
- **Zombie Consumers**: Endpoint lama hidup selamanya karena tidak ada telemetri yang melacak client mana yang masih mengonsumsinya.

#### Solusi Arsitektural Modern
Pendekatan terkontrol menggunakan:
1. **Additive Evolution**: Mengembangkan resource tanpa breaking changes selama minimal 12–24 bulan.
2. **Deterministic Sunsetting**: Menggunakan HTTP RFC standard (`Deprecation` dan `Sunset`) yang terbaca secara programmatic oleh client SDK.
3. **Gateway-Level Telemetry & Transmutation**: Menyerap backward compatibility parsing di edge/gateway, menjaga core business logic tetap ramping pada versi terbaru.

---

### 5. How (Workflow Detail Migration & Deprecation)

Alur transisi siklus hidup endpoint dari aktif hingga terminasi fisik:

```
[ PHASE 1: Active Production ]
       |
       v
[ PHASE 2: Announce Deprecation ]
       |-- Set RFC Header 'Deprecation: @<timestamp>'
       |-- Set RFC Header 'Sunset: <HTTP-date>'
       |-- Set Header 'Link: <docs-uri>; rel="deprecation"'
       |
       v
[ PHASE 3: Consumer Audit & Telemetry Tracking ]
       |-- Extract 'User-Agent' & Client Identity dari incoming v1 traffic
       |-- Export Prometheus Metric: `api_deprecated_endpoint_hits_total`
       |-- Alerting notification ke client/owner via developer portal
       |
       v
[ PHASE 4: Brownout (Chaos Testing for API Lifecycle) ]
       |-- Simulasi error terencana (misal: inject HTTP 429 atau 410 selama 10 menit di off-peak)
       |-- Memaksa developer client membaca log kegagalan sebelum final sunset
       |
       v
[ PHASE 5: Hard Sunset / Decommission ]
       |-- Return HTTP 410 Gone secara permanen
       |-- Hapus upstream routing logic & schema converter
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan **Colokan Listrik Internasional**.
- **Naive Migration**: Mencabut seluruh stopkontak tipe A dari dinding hotel dan langsung menggantinya dengan tipe G. Seluruh turis (client) yang membawa charger tipe A seketika tidak bisa mengisi daya (system outage).
- **Enterprise Lifecycle Migration**: Hotel menyediakan universal socket (backward compatibility), kemudian memasang papan peringatan bahwa tipe A akan dimatikan dalam 3 bulan (`Deprecation/Sunset`), menyediakan konverter adapter di front desk (Gateway dynamic mutation), dan akhirnya menutup port tipe A secara fisik saat sensor menunjukkan 0% penggunaan (`HTTP 410 Gone`).

#### Topology Diagram: Multi-Version Routing & Metric Egress

```
                                      INTERNET
                                         |
                                         | [Request with Version Specifier]
                                         v
                         +-------------------------------+
                         |   Edge CDN / Cloudflare       |
                         |   (Vary: Accept, API-Version) |
                         +-------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                        ENTERPRISE API GATEWAY (KONG / ENVOY)                   |
|                                                                                 |
|  +------------------------+  +-----------------------+  +--------------------+  |
|  | Version Detector Engine|  | RFC Deprecation Inject|  | Prometheus Exposer |  |
|  | - URI Regex Matching   |  | - Deprecation Header  |  | - Consumer Tagging |  |
|  | - Header Inspection    |  | - Sunset Header       |  | - Hit Counters     |  |
|  +------------------------+  +-----------------------+  +--------------------+  |
|                |                                                                |
|                +------------------+------------------+                          |
|                                   |                  |                          |
|       (Path Rewriting v1)         | (Path Pass-through v2)                      |
|                                   v                  v                          |
+-----------------------------------|------------------|--------------------------+
                                    |                  |
           +------------------------+                  +---------+
           |                                                     |
           v                                                     v
+-----------------------+                             +-----------------------+
|  V1 LEGACY ADAPTER    |                             |   V2 CANONICAL CORE   |
|  - Tolerant Reader    |                             |  - Clean Domain Model |
|  - Dynamic Mutation   |                             |  - High-Perf Protobuf |
|  - Calls Core v2 API  |                             |                       |
+-----------------------+                             +-----------------------+
           |                                                     ^
           +-----------------------------------------------------+
                             (Internal gRPC call)
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Native HTTP RFC Deprecation & Sunset Handler (Go)

Handler minimal yang mendemonstrasikan implementasi standar RFC 8594 secara presisi.

```go
package main

import (
	"net/http"
	"time"
)

func legacyUserHandler(w http.ResponseWriter, r *http.Request) {
	// RFC 8594 - Sunset Header: Menandakan kapan endpoint dimatikan permanen (format: HTTP-Date)
	sunsetTime := time.Date(2025, time.December, 31, 23, 59, 59, 0, time.UTC)
	w.Header().Set("Sunset", sunsetTime.Format(http.TimeFormat))

	// Draft RFC - Deprecation Header: Timestamp deprecation atau boolean "true"
	w.Header().Set("Deprecation", "@1704067200") // Unix timestamp: 1 Jan 2024

	// Memberikan tautan ke dokumentasi migrasi untuk machine-readable client
	w.Header().Set("Link", `<https://api.enterprise.com/docs/v2/migration>; rel="deprecation"; type="text/html"`)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"id": 101, "name": "Budi Gunawan", "note": "Use /v2/users instead"}`))
}

func main() {
	http.HandleFunc("/v1/users/101", legacyUserHandler)
	http.ListenAndServe(":8080", nil)
}
```

#### Practical Example: Production-Ready Content-Negotiation Gateway Layer

Di bawah ini adalah implementasi router/middleware mutasi skema tingkat lanjut pada API Gateway internal menggunakan Go. Middleware ini menangani versioning negosiasi konten, ekstraksi telemetry ID, backward schema normalization, serta penyisipan RFC Sunset headers.

```go
package main

import (
	"bytes"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"regexp"
	"strings"
	"sync/atomic"
	"time"
)

// Metric Registry sederhana untuk simulasi dimensional telemetry
var (
	deprecatedHitsCounter uint64
	v2HitsCounter         uint64
)

// Representasi Domain Core V2 (Model Kanonikal)
type UserV2Response struct {
	ID        string    `json:"id"`
	FullName  string    `json:"full_name"`
	Email     string    `json:"email"`
	UpdatedAt time.Time `json:"updated_at"`
}

// Representasi Domain Legacy V1 (Flat structure)
type UserV1Response struct {
	ID        string `json:"userId"`
	FirstName string `json:"first_name"`
	LastName  string `json:"last_name"`
	Contact   string `json:"contact_email"`
}

// CustomResponseWriter untuk intercept response body jika mutasi downstream diperlukan
type InterceptingResponseWriter struct {
	http.ResponseWriter
	statusCode int
	body       *bytes.Buffer
}

func NewInterceptingResponseWriter(w http.ResponseWriter) *InterceptingResponseWriter {
	return &InterceptingResponseWriter{
		ResponseWriter: w,
		statusCode:     http.StatusOK,
		body:           new(bytes.Buffer),
	}
}

func (rw *InterceptingResponseWriter) WriteHeader(code int) {
	rw.statusCode = code
}

func (rw *InterceptingResponseWriter) Write(b []byte) (int, error) {
	return rw.body.Write(b)
}

// Regex parser untuk Content-Negotiation Vendor MIME Type
// Contoh: application/vnd.enterprise.v1+json
var vendorMimeRegex = regexp.MustCompile(`application/vnd\.enterprise\.v([0-9]+)\+json`)

func VersioningAndLifecycleMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Pasang header Vary untuk mencegah cache pollution pada downstream caching proxy
		w.Header().Add("Vary", "Accept")
		w.Header().Add("Vary", "X-Consumer-ID")

		acceptHeader := r.Header.Get("Accept")
		matches := vendorMimeRegex.FindStringSubmatch(acceptHeader)

		version := "2" // Default canonical fallback version
		if len(matches) > 1 {
			version = matches[1]
		}

		consumerID := r.Header.Get("X-Consumer-ID")
		if consumerID == "" {
			consumerID = "anonymous"
		}

		if version == "1" {
			atomic.AddUint64(&deprecatedHitsCounter, 1)
			log.Printf("[AUDIT ALERT] Deprecated v1 accessed by consumer='%s' from IP='%s'", consumerID, r.RemoteAddr)

			// Injeksi standar lifecycle RFC
			w.Header().Set("Deprecation", "@1704067200") // 2024-01-01
			w.Header().Set("Sunset", "Wed, 31 Dec 2025 23:59:59 GMT")
			w.Header().Set("Link", `<https://api.enterprise.com/migration/v1-to-v2>; rel="sunset"; type="text/html"`)

			// Intercept dan jalankan mutasi respon
			proxyWriter := NewInterceptingResponseWriter(w)
			next.ServeHTTP(proxyWriter, r)

			// Parse response kanonikal v2 dari downstream service
			var v2Data UserV2Response
			if err := json.Unmarshal(proxyWriter.body.Bytes(), &v2Data); err != nil {
				http.Error(w, "Gateway Deserialization Mutation Error", http.StatusBadGateway)
				return
			}

			// Mutasi V2 -> V1
			names := strings.SplitN(v2Data.FullName, " ", 2)
			firstName := names[0]
			lastName := ""
			if len(names) > 1 {
				lastName = names[1]
			}

			v1Data := UserV1Response{
				ID:        v2Data.ID,
				FirstName: firstName,
				LastName:  lastName,
				Contact:   v2Data.Email,
			}

			w.Header().Set("Content-Type", "application/vnd.enterprise.v1+json")
			w.WriteHeader(proxyWriter.statusCode)
			json.NewEncoder(w).Encode(v1Data)
			return
		}

		// Direct canonical throughput
		atomic.AddUint64(&v2HitsCounter, 1)
		w.Header().Set("Content-Type", "application/vnd.enterprise.v2+json")
		next.ServeHTTP(w, r)
	})
}

// Canonical Microservice Handler (Hanya memproses Core Domain V2)
func CanonicalUserHandler(w http.ResponseWriter, r *http.Request) {
	user := UserV2Response{
		ID:        "usr-89471928",
		FullName:  "Alex Ferguson",
		Email:     "alex.f@enterprise.com",
		UpdatedAt: time.Now().UTC(),
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(user)
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/users/current", CanonicalUserHandler)

	pipeline := VersioningAndLifecycleMiddleware(mux)

	server := &http.Server{
		Addr:         ":8080",
		Handler:      pipeline,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	log.Println("Production Versioning Gateway operating on port :8080...")
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server aborted: %s", err)
	}
}
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Konteks: Global Payment Gateway Core API Overhaul
Sebuah unicorn fintech memproses **85.000 transaksi/detik** dengan ribuan merchant aktif. Model transaksi `v1` lama menggunakan representasi non-standar:
- Mata uang dinyatakan dalam unit desimal (`amount: 10.50`).
- Status pembayaran berbasis integer flag (`status: 1` untuk PENDING, `2` untuk SUCCESS).

Model `v2` mewajibkan:
- ISO-4217 minor currency units/cents (`amount: 1050` untuk mencegah floating-point roundoff issues).
- Status pembayaran berbasis String Enumeration (`status: "PAYMENT_SUCCEEDED"`).

Kegagalan langsung menghentikan `v1` akan merusak integrasi POS fisik yang pembaruan firmware-nya memakan waktu bulanan.

#### Strategi Eksekusi Lifecycle & Routing

```
                         [ Global Merchant Requests ]
                                      |
                       +--------------+--------------+
                       |                             |
             (Header: v1 / URI: v1)        (Header: v2 / URI: v2)
                       |                             |
                       v                             v
           +-----------------------+     +-----------------------+
           | Gateway Transmutation |     |  Direct Canary Envoy  |
           | Engine (Lua / WASM)   |     |                       |
           +-----------------------+     +-----------------------+
                       |                             |
                       | (Transform to ISO-4217)     | (Passthrough)
                       +--------------+--------------+
                                      |
                                      v
                        [ Immutable Core Engine v2 ]
                                      |
                                      +--> [ Kafka Event Sinks ]
```

1. **Dual Ingestion Layer via WASM**:
   - Tim platform membangun filter Envoy proxy berbasis WASM (C++/Rust).
   - Filter mendeteksi skema lama, mengonversi floating amount menjadi integer minor unit secara real-time di memori ($0.05$ ms overhead), dan meneruskannya ke core v2.
2. **Deterministic Sunsetting**:
   - RFC `Sunset` diaktifkan dengan durasi grace period 18 bulan.
   - Gateway secara otomatis menyaring consumer yang mengirim header `v1`, lalu mengekstraksi credential API Key ke Apache Pinot untuk analytics dashboard.
3. **Automated Churn Telemetry**:
   - Account Manager merchant secara otomatis menerima alert bulanan yang menampilkan daftar persentase traffic mereka yang masih berjalan di `v1`.
4. **Execution of Chaos Brownout**:
   - 30 hari sebelum tanggal Sunset final, Gateway mengaktifkan *brownout period* terencana: setiap hari Selasa pukul 02:00–02:15 UTC, seluruh payload v1 dijawab dengan `HTTP 429 Too Many Requests` disertai header retry dan link deprecation.
   - Hasil: 98.5% merchant yang pasif segera memperbarui SDK mereka sebelum batas waktu akhir.

---

### 9. Trade-offs & Matrix Evaluasi

Setiap pendekatan evolution & versioning memiliki ongkos implementasi sistemik:

| Dimensi Arsitektural | URI Path Versioning (`/v1/...`) | Custom Header (`X-API-Version`) | Content Negotiation (`Accept: ...`) | Dynamic Gateway Translation |
| :--- | :--- | :--- | :--- | :--- |
| **Edge Cacheability (CDN)** | **Sangat Baik**: Cache key otomatis terisolasi berdasarkan request path. | **Moderat**: Wajib konfigurasi explicit cache key hash + header `Vary`. | **Kompleks**: Harus mengurai MIME header di CDN edge compute level. | **Bergantung Pola**: CDN meng-cache berdasarkan downstream response state. |
| **Latensi Gateway Processing** | $\sim 0$ ms (Radix Tree routing biasa). | $< 0.1$ ms (Header map lookup). | $0.2 - 0.5$ ms (String parsing & MIME regex). | $1.0 - 3.5$ ms (JSON deserialization + field transmutation). |
| **Ergonomi Pengembang Client** | **Sangat Mudah**: Bisa dites langsung via browser address bar. | **Sedang**: Membutuhkan HTTP client yang mendukung header kustom. | **Sulit**: Sering salah konfigurasi pada tooling non-standar / cURL. | **Transparan**: Client lama tidak menyadari mutasi di balik layar. |
| **Purity Filosofi REST** | **Buruk**: Melanggar URI addressability invariance. | **Cukup**: Memisahkan context metadata dari URI entitas. | **Sempurna**: Mengikuti RFC 9110 media-type representation model. | **Netral**: Desain domain internal terlindungi dari polusi skema lama. |
| **Biaya Komputasi & Scaling** | Minimal. Upstream handle multi-version. | Minimal. Routing berbasis map. | Sedang. Header payload allocation. | **Tinggi**: Konsumsi CPU & Memori masif di reverse-proxy layer. |

---

### 10. Common Mistakes & Troubleshooting

#### Pitfall 1: Missing the `Vary` HTTP Header
*Gejala*: Client A meminta payload v2, namun menerima payload v1 dari cache. Sebaliknya, Client B meminta payload v1 dan menerima response v2 yang memicu parsing crash.
*Akar Masalah*: Reverse proxy/CDN (Cloudflare, Fastly, Akamai) menyimpan cache berdasarkan URI saja. Jika versioning berada di `Accept` atau `X-API-Version`, cache engine tidak tahu representasinya berbeda.
*Solusi*: Wajib injeksi response header:
```http
HTTP/1.1 200 OK
Vary: Accept, X-API-Version
```

#### Pitfall 2: Breaking Evolution via "Hidden Constraints"
*Gejala*: Menambahkan field baru ke request payload downstream dianggap non-breaking oleh developer, namun seluruh request dari client mobile lama langsung gagal.
*Akar Masalah*: Client SDK lama dikompilasi dengan serializer yang menolak data yang tidak terdaftar (*Strict JSON Parsing / Deserialization Fail on Unknown Properties*).
*Solusi*: 
- Sediakan Client SDK yang secara default mengabaikan unknown fields (misal: Jackson `@JsonIgnoreProperties(ignoreUnknown = true)` di Java, atau `Decodable` tanpa strict decoding di Swift).
- Di sisi server, jangan pernah mengubah validation constraint dari *optional* ke *mandatory* tanpa menaikkan versi API mayor.

#### Diagnostic Playbook: Debugging Lifecycle & Cache Drift

Langkah-langkah mendiagnosis issue routing versioning pada cluster gateway:

```bash
# 1. Verifikasi header Vary dan Lifecycle RFC pada level Edge Proxy
curl -s -D - -o /dev/null https://api.enterprise.com/orders/1001 \
  -H "Accept: application/vnd.enterprise.v1+json" \
  -H "X-Consumer-ID: merchant_test_42"

# Output yang HARUS muncul:
# HTTP/2 200
# vary: Accept, X-Consumer-ID
# deprecation: @1704067200
# sunset: Wed, 31 Dec 2025 23:59:59 GMT

# 2. Periksa apakah Edge CDN menyajikan konten yang salah akibat cache poisoning
curl -s -X GET "https://api.enterprise.com/orders/1001" \
  -H "Accept: application/vnd.enterprise.v2+json" \
  --head | grep -E "(CF-Cache-Status|X-Cache|Vary|Content-Type)"

# 3. Lacak jejak socket TCP jika parsing Content-Negotiation memicu abort
tcpdump -nn -vv -i eth0 'tcp port 8080 and (((ip[2:2] - ((ip[0]&0xf)<<2)) - ((tcp[12:2]&0xf0)>>2)) != 0)'
```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis evolusi API mayor ke cluster produksi:

- [ ] **Strict Semantic Contract**: Tidak ada breaking changes (misal: perubahan field type `int` menjadi `string`, rename `customer_id` ke `accountId`) di dalam mayor version yang sama.
- [ ] **Dual-Header Lifecycle Compliance**: Endpoint yang direncanakan pensiun mengekspos header `Sunset` (RFC 8594) dan header `Deprecation` (Draft IETF).
- [ ] **Proper Dynamic Caching Rules**: Header `Vary: Accept` atau `Vary: X-API-Version` diinjeksi jika mekanisme versioning non-URI diaktifkan.
- [ ] **Observability Instrumentation**: Metrik telemetri (`http_requests_total{version="v1", consumer="app-client-x"}`) terdaftar di monitoring engine untuk tracking real-time client migration.
- [ ] **Backward-Compatible Reader Implementation**: Core downstream engine mengaktifkan permissive parsing untuk incoming unknown fields.
- [ ] **Automated Brownout Policy**: Jadwal degradasi buatan (brownout) disepakati minimal 30 hari sebelum Hard Sunset dilakukan.
- [ ] **Fallback Documentation Links**: Header `Link: <url>; rel="deprecation"` menyertakan panduan migrasi yang valid secara machine-readable.

---

### 12. Hands-on Practice

Target path praktikum: `hands-on/m02/`

#### Langkah 1: Siapkan Struktur Direktori
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
go mod init enterprise.com/lifecycle-demo
```

#### Langkah 2: Buat Entrypoint Server (`hands-on/m02/main.go`)
Salin kode berikut untuk membangun simulator traffic mutasi dinamis:

```go
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

type CanonicalPayload struct {
	ID        string    `json:"id"`
	AmountCents int64   `json:"amount_cents"`
	Currency  string    `json:"currency"`
	Status    string    `json:"status"`
	Timestamp time.Time `json:"timestamp"`
}

func paymentEndpoint(w http.ResponseWriter, r *http.Request) {
	version := r.Header.Get("X-Api-Version")
	w.Header().Set("Vary", "X-Api-Version")

	// Payload data internal kanonikal
	internalData := CanonicalPayload{
		ID:          "txn_1029384",
		AmountCents: 50000, // Rp 500.00
		Currency:    "IDR",
		Status:      "SUCCESS",
		Timestamp:   time.Now().UTC(),
	}

	if version == "1" || version == "" {
		// Logika Deprecated V1
		w.Header().Set("Deprecation", "@1704067200")
		w.Header().Set("Sunset", "Fri, 01 Aug 2025 00:00:00 GMT")
		w.Header().Set("Link", `<http://localhost:8080/docs/migration>; rel="deprecation"`)
		w.Header().Set("Content-Type", "application/json")

		// Transformasi mutasi inline
		v1Map := map[string]interface{}{
			"id":         internalData.ID,
			"amount":     float64(internalData.AmountCents) / 100.0,
			"statusCode": 2, // 2 = SUCCESS pada legacy code
			"created_at": internalData.Timestamp.Unix(),
		}
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(v1Map)
		return
	}

	// Canonical V2
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(internalData)
}

func main() {
	http.HandleFunc("/payments/verify", paymentEndpoint)
	fmt.Println("Server running on port :8080...")
	http.ListenAndServe(":8080", nil)
}
```

#### Langkah 3: Eksekusi Pengujian Verifikasi

Jalankan server:
```bash
go run main.go
```

Buka terminal kedua dan jalankan suite test berikut:

1. **Test Payload Legacy V1 (Perhatikan transformasi floating amount & status integer):**
```bash
curl -i -X GET http://localhost:8080/payments/verify \
  -H "X-Api-Version: 1"
```
*Validasi Output*: Pastikan header `Sunset`, `Deprecation`, dan `Link` muncul, serta format payload menggunakan field `amount: 500` dan `statusCode: 2`.

2. **Test Payload Kanonikal V2:**
```bash
curl -i -X GET http://localhost:8080/payments/verify \
  -H "X-Api-Version: 2"
```
*Validasi Output*: Pastikan header lifecycle tidak muncul, dan JSON payload memiliki field `amount_cents: 50000` dan `status: "SUCCESS"`.

---

### 13. Exercises

#### Level: Easy
Implementasikan middleware HTTP sederhana dalam bahasa pilihan Anda yang mendeteksi path `/api/v1/*`. Jika diakses, middleware menambahkan header:
- `Deprecation: true`
- `Sunset: Sat, 01 Nov 2025 00:00:00 GMT`
*Acceptance Criteria*: Unit test memvalidasi keberadaan kedua header tersebut pada seluruh response path v1.

#### Level: Medium
Rancang skema JSON Schema evolutif untuk entity `CustomerAddress`.
1. Versi 1: Memiliki single field `street_address: string`.
2. Versi 2: Memecah data menjadi `street_name: string`, `building_number: string`, dan `unit: string`.
Buat middleware Go yang menerima request JSON `POST /customers` dari kedua versi di atas, lalu menormalisasinya menjadi model domain seragam tanpa return HTTP 400.
*Acceptance Criteria*: Payload v1 dan v2 sama-sama tersimpan secara valid pada backend database yang memakai model v2.

#### Level: Hard
Bangun Envoy Filter configuration (menggunakan Lua filter atau OpenResty Lua) yang membaca `Accept` header. Jika client meminta v1, filter menginspeksi in-flight upstream response JSON:
1. Mengubah format penamaan field dari `camelCase` menjadi `snake_case`.
2. Menghitung dynamic processing latency overhead dalam mikrosekon.
3. Mengembalikan error `HTTP 410 Gone` secara otomatis jika waktu server telah melewati tanggal batas `Sunset`.
*Acceptance Criteria*: Sistem mendemonstrasikan cut-off otomatis tepat saat tanggal validasi terlewati tanpa restart proses container Envoy.

---

### 14. Architecture Challenge

Anda ditunjuk sebagai Principal API Architect untuk ekosistem ERP Perbankan Skala Global:
- **Kondisi Eksisting**: API monolitik `/v1/core-banking` telah digunakan oleh **450 institusi finansial B2B eksternal**.
- **Kebutuhan**: Core engine sedang dimigrasikan ke arsitektur microservices berbasis event-driven dengan payload model baru yang mematuhi format ISO 20022.
- **Batasan Ketat**:
  1. Kontrak SLA perbankan: Zero Downtime selama migrasi.
  2. Regulator melarang pemutusan paksa API client tanpa masa transisi terbukti minimal 1 tahun.
  3. Setiap institusi memiliki custom-built legacy client yang menolak field tak terdaftar di XML/JSON mereka (Strict unmarshaling).
  4. Throughput puncak mencapai 120.000 req/sec dengan batas SLA $P_{99} \le 15$ ms.

**Tugas Arsitektural Anda**:
Rancang blueprint arsitektur end-to-end yang mencakup:
1. Topologi Ingress Routing & Dynamic Adaptation Pipeline (Jelaskan teknologi proxy yang dipilih dan estimasi latency budget).
2. Algoritma Audit Consumer & Telemetry Ingestion (Cara memetakan setiap HTTP call ke client ID unik secara akurat tanpa degradasi throughput).
3. Fallback Disaster Recovery Plan jika payload translator mengalami memory leak / spike latency di jam sibuk.
4. Framework pengujian otomatis di pipeline CI/CD untuk memastikan backward compatibility tidak pernah bocor ke ekosistem produksi.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic (5 Soal)
1. **Apa fungsi utama dari header standard HTTP `Sunset` (RFC 8594)?**
   - A. Menandakan waktu kapan server akan di-reboot untuk maintenance.
   - B. Menandakan tanggal dan waktu spesifik kapan endpoint API akan dihentikan secara permanen (decommissioned/unresponsive).
   - C. Menghitung sisa kuota rate-limiting consumer API.
   - D. Menghapus sesi otentikasi JWT client secara otomatis.
   *Jawaban*: **B**. RFC 8594 secara eksplisit mendefinisikan header `Sunset` sebagai penanda waktu di masa depan saat ketersediaan resource terkait akan berakhir.

2. **Manakah dari perubahan skema berikut yang dikategorikan sebagai BACKWARD COMPATIBLE?**
   - A. Mengubah tipe data field `zip_code` dari integer ke string.
   - B. Menghapus field `status` dari model response.
   - C. Menambahkan field opsional baru dengan nilai default pada model response.
   - D. Mengubah format response dari JSON ke XML.
   *Jawaban*: **C**. Menambah field opsional tidak merusak client lama yang menggunakan Tolerant Reader pattern.

3. **Mengapa menambahkan header `Vary: Accept` sangat penting saat menerapkan versioning berbasis Content Negotiation?**
   - A. Untuk memaksa browser membuka download dialog.
   - B. Untuk mencegah Shared Intermediate Cache/CDN menyajikan representasi versi data yang salah kepada consumer yang berbeda.
   - C. Untuk mengompres body payload dengan algoritma GZIP.
   - D. Untuk mengenkripsi header authorization di transit.
   *Jawaban*: **B**. Header `Vary` memberitahu intermediate caches bahwa cache key harus mempertimbangkan nilai dari header `Accept`.

4. **Menurut prinsip Robustness (Postel's Law), apa yang harus dilakukan aplikasi consumer terhadap field JSON yang tidak dikenal?**
   - A. Segera melempar parsing exception dan memutus koneksi socket.
   - B. Mengabaikan (ignore) field tersebut secara aman dan memproses field yang dikenali.
   - C. Mengirim log error `HTTP 500` kembali ke server.
   - D. Mengubah field tersebut menjadi format plaintext.
   *Jawaban*: **B**. Prinsip toleransi menyatakan: *"Be liberal in what you accept, and conservative in what you send"*.

5. **Kode status HTTP manakah yang paling semantik untuk menandakan bahwa suatu versi API telah dimatikan secara permanen?**
   - A. `404 Not Found`
   - B. `400 Bad Request`
   - C. `410 Gone`
   - D. `503 Service Unavailable`
   *Jawaban*: **C**. `410 Gone` mengindikasikan bahwa resource ditargetkan sengaja dihapus dan tidak akan pernah tersedia lagi, berbeda dengan 404 yang bersifat sementara atau tidak sengaja.

#### Pertanyaan Intermediate (5 Soal)
6. **Dalam integrasi API Gateway, apa dampak performa utama dari penempatan dynamic schema translation (v1 -> v2) pada layer proxy?**
   - A. Meningkatkan kecepatan routing jaringan karena caching URL.
   - B. Peningkatan penggunaan CPU dan latensi per-request akibat alokasi memori untuk parsing JSON, manipulasi pohon AST/objek, dan serialisasi ulang.
   - C. Terjadinya bypass mekanisme TLS handshake secara otomatis.
   - D. Memory leak permanen pada upstream backend service.
   *Jawaban*: **B**. Membaca stream body, deserialisasi JSON, mengubah struktur, dan serialisasi ulang di gateway memakan CPU cycle yang signifikan dan menambah latensi baseline.

7. **Bagaimana format nilai yang valid untuk header draft standard `Deprecation`?**
   - A. Format tanggal HTTP (misal: `Sun, 06 Nov 1994 08:49:37 GMT`).
   - B. Boolean flag (`@true`) atau Unix timestamp yang diawali karakter `@` (misal: `@1704067200`).
   - C. Angka integer versi API (misal: `v1`).
   - D. URL string ke panduan commit Git.
   *Jawaban*: **B**. Spesifikasi draft HTTP API Deprecation header mendefinisikan nilainya dapat berupa boolean flag atau HTTP date / Unix timestamp dengan prefix `@`.

8. **Anda memiliki consumer yang memproses payload secara sekuensial. Jika API Gateway mengubah ordering key dari JSON response pada versi baru, apakah hal ini melanggar backward compatibility?**
   - A. Ya, untuk semua tipe client di dunia tanpa terkecuali.
   - B. Secara spesifikasi JSON (RFC 8259) tidak, karena JSON Object adalah himpunan unordered key/value, namun secara praktis ya untuk client dengan parser primitif/naive regex.
   - C. Tidak pernah ada client yang membaca JSON secara parsial.
   - D. JSON ordering diatur oleh header `Content-Length`.
   *Jawaban*: **B**. Menurut RFC 8259 JSON Object tidak memiliki urutan (unordered), namun naive client yang parsing menggunakan regex atau deserializer naif berbasis token scanner dapat mengalami failure.

9. **Apa peran utama dari Consumer-Driven Contract Testing (seperti Pact) dalam siklus hidup API?**
   - A. Melakukan load test untuk mencari limit concurrency gateway.
   - B. Memverifikasi secara otomatis di CI/CD pipeline bahwa perubahan skema yang dilakukan Producer tidak merusak ekspektasi yang didefinisikan oleh seluruh Consumer aktif.
   - C. Meng-generate kode dokumentasi Swagger secara otomatis dari unit test.
   - D. Menghapus baris kode yang deprecated secara otomatis di repositori Git upstream.
   *Jawaban*: **B**. Contract testing memvalidasi kontrak skema antara consumer dan producer di pipeline sebelum kode dideploy ke lingkungan produksi.

10. **Kapan strategi URI Versioning (`/v1`, `/v2`) LEBIH DISUKAI dibandingkan Content Negotiation?**
    - A. Ketika resource payload harus identik secara murni dengan konsep Semantic Web.
    - B. Ketika API ditujukan untuk konsumsi publik yang masif dengan berbagai client heterogen, dan dependensi terhadap layer caching CDN publik sangat dominan.
    - C. Ketika organisasi tidak memiliki izin untuk mengonfigurasi routing gateway.
    - D. Ketika ukuran request body melebihi 100 Megabytes.
    *Jawaban*: **B**. URI versioning sangat mudah dipahami oleh developer publik, minim konfigurasi rumit di HTTP client, dan secara natural kompatibel dengan konfigurasi default seluruh vendor CDN di dunia.

#### Pertanyaan Skenario Kasus Produksi (3 Soal)

11. **Skenario Kasus 1**:
    Tim engineering merilis API v2 untuk resource `/invoices`. Di v1, status pembayaran adalah string `status: "PAID"`. Di v2, tim backend mengubahnya menjadi enum array `statuses: ["PAYMENT_RECEIVED", "CLEARED"]`. Segera setelah deployment, API Gateway meledak dengan CPU usage 100% dan latency $P_{99}$ melonjak dari 5ms ke 1200ms.
    *Pertanyaan*: Apa kemungkinan besar penyebab kegagalan arsitektur ini dan mitigasi tercepatnya?
    *Jawaban & Analisis*: Penyebabnya adalah gateway translation engine melakukan unmarshaling, transformasi struktur single-to-array, dan serialisasi JSON secara synchronous pada high concurrency tanpa CPU core limit yang memadai, atau terjadi infinite recursion/memory reallocation pada unmarshaler. Mitigasi: Rollback deployment gateway, alihkan beban translasi skema dari Ingress Gateway ke upstream dedicated legacy adapter pods, atau deploy fallback cache untuk invariant dynamic transformation.

12. **Skenario Kasus 2**:
    Sebuah merchant besar melaporkan bahwa webhook callback mereka mogok setelah Anda menambahkan field baru `tracking_url: null` ke dalam JSON event payload. Merchant tersebut menuntut kompensasi atas downtime.
    *Pertanyaan*: Berdasarkan kontrak evolusi skema, siapa yang melanggar spesifikasi dan bagaimana arsitektur Anda mencegah hal ini di masa depan?
    *Jawaban & Analisis*: Merchant melanggar prinsip *Tolerant Reader* karena webhook receiver mereka melakukan parsing yang rapuh terhadap field nullable atau properti baru. Namun, dari sisi enterprise producer, merilis field dengan explicit `null` sering kali memicu error pada strongly-typed client (misal: Golang `string` tanpa pointer, atau Java primitives). Mitigasi produsen: Konfigurasikan serializer dengan opsi `omitempty` untuk menyembunyikan properti bernilai kosong daripada mengirim explicit `null`, serta sediakan webhook payload testing sandbox di Developer Portal.

13. **Skenario Kasus 3**:
    Perusahaan Anda memutuskan untuk melakukan Hard Sunset pada legacy API `/v1/auth` pada 1 Juni 2025. Data telemetri menunjukkan bahwa 5% traffic masih mengakses v1, namun 100% dari traffic tersebut tidak menyertakan identitas autentikasi atau token usang (unauthenticated spam/crawler bots). Tim support ragu-ragu untuk mematikan endpoint karena khawatir komplain dari client enterprise.
    *Pertanyaan*: Langkah verifikasi arsitektural apa yang harus diambil untuk membuktikan secara pasti apakah 5% traffic tersebut aman untuk dimatikan?
    *Jawaban & Analisis*: 
    1. Terapkan gateway filter untuk memvalidasi authorization layer terlebih dahulu sebelum menghitung metrik traffic. Pisahkan dashboard: `v1_authenticated_hits` vs `v1_unauthenticated_hits`.
    2. Jika metrik authenticated adalah nol (0), jalankan *Brownout Phase* terencana (misal: inject HTTP 401 Unauthorized secara selektif selama rentang waktu bertahap).
    3. Analisis log IP address, TLS fingerprint (JA3/JA4), dan User-Agent dari traffic 5% tersebut untuk memverifikasi apakah polanya cocok dengan automated scanner / scraping bots.
    4. Setelah terkonfirmasi bahwa tidak ada enterprise client token yang valid di log, proses hard decommission ke HTTP 410 Gone dapat dieksekusi dengan aman.

---

### 16. Summary

- **Evolution over Revolution**: Mengubah versi API mayor adalah opsi terakhir. Utamakan **Additive Evolution** (menambah field baru opsional, toleransi unknown attributes) untuk meminimalkan fragmentasi arsitektur dan maintainability overhead.
- **Contract Explicitly**: Setiap pola versioning (URI, Header, Vendor MIME Type) memiliki konsekuensi performa pada layer caching CDN dan proxy CPU. Content Negotiation memberikan puritas model domain, namun URI versioning tetap menjadi standar de-facto untuk performa dan interoperabilitas publik.
- **Programmatic Sunsetting**: Gunakan protokol standard HTTP RFC 8594 (`Sunset`), `Deprecation`, dan `Link` rel="deprecation" untuk mengomunikasikan siklus hidup API langsung ke mesin consumer SDK, bukan sekadar lewat email announcement.
- **Mediation Layering**: Lindungi core service logic dari legacy backward compatibility debt dengan menempatkan dynamic mutation adapters di tepi perimeter gateway atau micro-BFF terisolasi.
- **Visibility-Driven Retirement**: Anda tidak bisa mematikan apa yang tidak bisa Anda ukur. Pastikan telemetri dimensional (Prometheus/OpenTelemetry) selalu melacak metadata client ID sebelum eksekusi `HTTP 410 Gone` dilakukan.