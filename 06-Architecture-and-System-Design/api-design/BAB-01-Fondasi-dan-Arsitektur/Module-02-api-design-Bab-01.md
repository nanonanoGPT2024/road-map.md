# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 06-Architecture-and-System-Design  
**Bab 01:** BAB-01-Fondasi-dan-Arsitektur  
**Topik:** API Design

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Merancang & Mengimplementasikan Advanced API Patterns:** Menguasai paradigma *Idempotent Mutations*, *Distributed Rate Limiting*, serta standardisasi *Error Handling RFC 9457 (Problem Details)* pada sistem terdistribusi.
2. **Mengevaluasi & Memilih API Protocols Secara Kritis:** Mengambil keputusan arsitektural berbasis metrik performa (*p99 latency, serialization cost, transport overhead*) antara REST, gRPC (HTTP/2), GraphQL Federation, dan Event-Driven Webhooks.
3. **Membangun Resilient API Contracts:** Merancang evolusi skema (*backward & forward compatibility*) tanpa *breaking changes*, serta menerapkan strategi versioning (*URI, Header, Content Negotiation*) pada skala *enterprise*.
4. **Mendesain Lapisan Zero-Trust API Security & Gateway:** Mengintegrasikan Mutual TLS (mTLS), otentikasi JWT terdistribusi berbasis JWKS, dan arsitektur *Policy Enforcement Point (PEP)* vs *Policy Decision Point (PDP)*.

---

## 2. Prerequisite

Sebelum mendalami modul ini, Anda wajib memahami:

* Fondasi protokol jaringan (OSI Layer 4 TCP vs Layer 7 HTTP/1.1, HTTP/2, HTTP/3).
* Konsep dasar RESTful APIs (HTTP Methods, Status Codes, Resource-Oriented Modeling).
* Dasar-dasar konkurensi, *race conditions*, serta struktur data *in-memory* (Redis primitives: String, Hash, Sorted Sets).
* Pengalaman membaca/menulis bahasa pemrograman backend bertipe statis (diutamakan Go atau TypeScript) dan pemahaman format JSON/Protobuf.

---

## 3. Concept & Internal Architecture

### 3.1 Serialization & Transport Layer: JSON vs Protocol Buffers

Efisiensi API tingkat produksi ditentukan oleh bagaimana data dikonversi dari representasi memori menjadi aliran bita (*wire format*).

* **JSON (REST):** Bersifat tekstual (*human-readable*), skema implisit (*self-describing*), dan membutuhkan alokasi memori serta komputasi parsing CPU yang tinggi (*reflection, string scanning, IEEE 754 float precision issues*).
* **Protocol Buffers (gRPC):** Menggunakan *binary serialization* dengan representasi data berbasis *Tag-Length-Value (TLV)* dan *Varint encoding*. Skema didefinisikan secara eksplisit via file `.proto`. Tidak ada metadata *field name* yang dikirimkan pada *wire*, melainkan representasi integer tag (1-4 byte), yang memangkas ukuran *payload* hingga 60-80% dibanding JSON mentah.

```
Wire Format Comparison: Field "id" = 1000

JSON (11 bytes):
[ 0x7b, 0x22, 0x69, 0x64, 0x22, 0x3a, 0x31, 0x30, 0x30, 0x30, 0x7d ]
  {     "     i     d     "     :     1     0     0     0     }

Protobuf (3 bytes):
[ 0x08, 0xe8, 0x07 ]
  0x08 -> Field Tag: 1, Type: Varint (00001 000)
  0xe8, 0x07 -> Varint 1000: (11101000 00000111 -> 1000)
```

### 3.2 Idempotency Engine: State Machine & Distributed Locking

Dalam sistem terdistribusi, kegagalan jaringan bersifat tak terhindarkan (*network timeouts are ambiguous*). Klien tidak dapat membedakan apakah mutasi data (*POST/PATCH*) gagal dieksekusi oleh server atau responsnya yang hilang saat transmisi kembali.

Untuk menjamin semantik *Exactly-Once Execution* dari perspektif bisnis (meskipun transport layer menerapkan *At-Least-Once Delivery*), kita membutuhkan **Idempotency Engine**.

```
                   Idempotency Engine State Machine

               +----------------------------------+
               | Incoming Request (Idempotency-Key)|
               +----------------------------------+
                                |
                                v
                     [Check Redis/Database]
                                |
          +---------------------+---------------------+
          | Key Exist?                                | Key Does NOT Exist
          v                                           v
   +---------------+                          +---------------+
   | Status Check  |                          | Atomic Lock   |
   +---------------+                          | (SETNX / Px)  |
     |           |                            +---------------+
     | PENDING   | COMPLETED                          |
     |           |                                    v
     v           v                            +---------------+
[HTTP 409 Conflict] [Return Cached Response]  | Execute       |
(In-Progress)       (Payload + Status Code)   | Business Logic|
                                              +---------------+
                                                      |
                                                      v
                                              +---------------+
                                              | Save Response |
                                              | & Status = OK |
                                              +---------------+
```

Komponen inti:
1. **Idempotency Key Injection:** Klien menghasilkan UUIDv4 unik untuk setiap mutasi logis.
2. **Mutual Exclusion (Locking):** Gateway/Service menggunakan operasi atomic (misal: Redis `SET key request_fingerprint NX EX 30`) untuk mencegah *concurrent duplicate requests*.
3. **Execution Fingerprinting:** *Payload* di-hash (misal: SHA-256) untuk memastikan jika klien mengirim key yang sama tetapi dengan *payload* berbeda, sistem wajib menolak dengan HTTP `422 Unprocessable Entity` (mencegah *payload spoofing/tampering*).
4. **Result Storage:** Setelah komputasi selesai, *response body* dan *HTTP status code* disimpan dalam cache dengan TTL tertentu (misal: 24 jam).

### 3.3 Distributed Rate Limiting: Algorithms & Trade-offs

| Algoritma | Kompleksitas Waktu | Konsumsi Memori | Karakteristik Edge Case | Skenario Terbaik |
| :--- | :--- | :--- | :--- | :--- |
| **Token Bucket** | $O(1)$ | $O(1)$ per client | Mengizinkan burst trafik hingga batas kapasitas bucket. | Public Enterprise API (e.g., Stripe, AWS). |
| **Leaky Bucket** | $O(1)$ | $O(1)$ per client | Mengalirkan output pada *rate* yang konstan; meratakan burst (*traffic shaping*). | API yang mengarah ke sistem legacy / background queues. |
| **Fixed Window Counter**| $O(1)$ | $O(1)$ per client | Rentan terhadap *double burst* pada batas pergantian jendela (*window boundary*). | Proteksi anti-DDoS sederhana tingkat dasar. |
| **Sliding Window Log** | $O(N)$ di mana $N$ = jumlah request | $O(N)$ tinggi (menyimpan timestamp per request) | Sangat akurat, nol anomali batas jendela. | API keamanan tinggi dengan volume trafik rendah. |
| **Sliding Window Counter**| $O(1)$ | $O(1)$ per client | Estimasi bobot dari jendela sebelumnya: $N_{current} + N_{prev} \times (1 - \frac{t_{elapsed}}{window})$. | High-throughput distributed API gateways. |

---

## 4. Why & What

### Mengapa Desain API Fundamental Gagal di Skala Enterprise?
Banyak sistem gagal di lingkungan produksi karena meremehkan aspek kegagalan parsial (*partial failures*). API yang hanya berfokus pada fungsionalitas ("asal jalan") umumnya menunjukkan cacat arsitektur berikut:
* **The "Dual-Write / Ghost Mutation" Disaster:** Klien mengalami HTTP timeout, melakukan *retry*, dan menyebabkan pengguna ditagih dua kali karena API tidak mengimplementasikan *idempotency*.
* **Cascading Gateway Exhaustion:** Ketiadaan mekanisme *concurrency limit* dan *circuit breaking* menyebabkan satu *downstream service* yang lambat memakan seluruh *connection pool* API Gateway, menumbangkan seluruh arsitektur microservices.
* **Contract Drift:** Perubahan non-breaking menurut satu tim (seperti mengubah integer menjadi string, atau menghapus field null) merusak *client parser* di production karena tidak ada validasi skema otomatis dan deprecation protocol yang ketat.

### Apa yang Membedakan Enterprise Production API?
API kelas enterprise dirancang dengan asumsi: **Jaringan tidak dapat dipercaya, klien akan melakukan retry tanpa aturan, dan downstream dependencies akan mengalami degradasi performa.** 
Oleh karena itu, arsitektur API enterprise wajib mengimplementasikan:
1. *Strict Schema Validation & Zero-Trust Parsing*.
2. *Deterministic Idempotency*.
3. *Unified RFC-compliant Error Handling*.
4. *Adaptive Rate Limiting & Graceful Degradation*.

---

## 5. How (Workflow Detail)

Alur eksekusi request pada arsitektur API Enterprise skala produksi:

```
[Client]
   |
   | 1. HTTPS / HTTP/2 (TLS 1.3 Termination, mTLS Verification)
   v
[Edge / Cloudflare / WAF]
   |
   | 2. DDoS Mitigation, IP Reputation Check
   v
[Enterprise API Gateway (e.g., Kong, Envoy)]
   |-- 3. Distributed Rate Limiter (Redis Token Bucket / Sliding Window)
   |-- 4. Auth & RBAC (JWT Validation via in-memory JWKS cache)
   |-- 5. Request Schema Validation (OpenAPI / Protobuf Validator)
   |-- 6. Idempotency Check (Check-and-Lock via Redis Lua Script)
   |
   | 7. Downstream Routing (gRPC / HTTP Upstream)
   v
[Core Service / Worker]
   |-- 8. Business Logic Execution
   |-- 9. Transactional Outbox Pattern (Database commit + Outbox event)
   |
   +--> [Save Result to Redis Idempotency Engine]
   |
   | 10. Structured Response RFC 9457 (if error) / Standard DTO
   v
[API Gateway]
   |-- 11. Inject Telemetry Headers (X-Trace-Id, X-Request-Id, RateLimit-*)
   v
[Client]
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Konter Layanan Teller Bank dengan Deposit Box Unik
Bayangkan Anda melakukan deposit tunai bernilai besar:
* **Rate Limiter:** Petugas keamanan di lobi membatasi hanya 5 orang per menit yang boleh masuk antrean untuk menghindari desak-desakan (*Token Bucket*).
* **Idempotency Key:** Anda diberikan amplop berlabel kode transaksi unik dari rumah (*Idempotency-Key*). Jika Anda pingsan dan lupa apakah Anda sudah menyerahkan amplop tersebut, rekan Anda datang ke teller membawa amplop dengan kode yang persis sama. Teller mengecek buku besar: *"Kode ini sudah selesai diproses 2 menit lalu, ini bukti transaksinya."* Uang tidak didepositkan dua kali.
* **Circuit Breaker:** Jika brankas bank macet, teller langsung menolak antrean di loket depan dalam waktu 1 detik (*Fail-Fast*) daripada membiarkan 200 nasabah menunggu 30 menit di loket tanpa kepastian.

### Diagram: Distributed Token Bucket via Redis Lua

```
           Token Bucket Algorithm Architecture (Atomic Redis Lua)

        Request Arrives (Rate Limit Check: IP / User ID)
                           |
                           v
          +----------------------------------+
          | Execute Lua Script atomically    |
          | in Redis                         |
          +----------------------------------+
                           |
      +--------------------+--------------------+
      |                                         |
      v                                         v
[Fetch Bucket Metadata]                 [Compute New Tokens]
- last_updated_time                     - delta = now - last_updated_time
- tokens_remaining                      - tokens = min(capacity, 
                                                       tokens + delta * refill_rate)
                                                |
                                                v
                                      +-------------------+
                                      | tokens >= 1 ?     |
                                      +-------------------+
                                        |               |
                                   YES  |               | NO
                                        v               v
                        [tokens = tokens - 1]     [Rate Limit Exceeded!]
                        [Update Bucket State]           |
                                |                       v
                                v               [Return HTTP 429]
                        [Allow Request]         [Header: Retry-After]
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: RFC 9457 Problem Details Standard Error
Standar modern penanganan error menggantikan pola inkonsisten seperti `{"error": "something went wrong"}`.

```json
{
  "type": "https://api.enterprise.com/errors/insufficient-funds",
  "title": "Insufficient Funds",
  "status": 403,
  "detail": "Account balance of $12.50 is below the required transfer amount of $50.00.",
  "instance": "/accounts/acc_891273/transfers/txn_091283",
  "invalid_params": [],
  "balance": 12.50,
  "currency": "USD",
  "trace_id": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
}
```

### 7.2 Practical Example: Enterprise Idempotency Middleware (Go + Redis)
Implementasi tingkat produksi menggunakan *Atomic Redis Scripting* untuk mengunci request, memverifikasi hash payload, dan menyimpan respon.

```go
package middleware

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	HeaderIdempotencyKey = "Idempotency-Key"
	IdempotencyTTL        = 24 * time.Hour
	LockExpiry           = 30 * time.Second
)

type IdempotencyRecord struct {
	Status      string `json:"status"` // "LOCKED", "RESOLVED"
	RequestHash string `json:"request_hash"`
	StatusCode  int    `json:"status_code"`
	Headers     map[string]string `json:"headers"`
	Body        string `json:"body"`
}

type IdempotencyMiddleware struct {
	client *redis.Client
}

func NewIdempotencyMiddleware(client *redis.Client) *IdempotencyMiddleware {
	return &IdempotencyMiddleware{client: client}
}

func (m *IdempotencyMiddleware) Handler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Idempotency hanya berlaku untuk mutasi non-idempotent HTTP methods
		if r.Method != http.MethodPost && r.Method != http.MethodPatch {
			next.ServeHTTP(w, r)
			return
		}

		key := r.Header.Get(HeaderIdempotencyKey)
		if key == "" {
			// Fail-safe: Tolak mutasi kritikal tanpa idempotency key
			writeRFC9457Error(w, http.StatusBadRequest, "Missing Idempotency-Key", "Idempotency-Key header is required for this operation.")
			return
		}

		ctx := r.Context()
		bodyBytes, err := io.ReadAll(r.Body)
		if err != nil {
			writeRFC9457Error(w, http.StatusInternalServerError, "Request Error", "Unable to read payload.")
			return
		}
		r.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))

		hasher := sha256.New()
		hasher.Write(bodyBytes)
		currentHash := hex.EncodeToString(hasher.Sum(nil))

		redisKey := fmt.Sprintf("idempotency:%s", key)

		// Evaluasi State Atomic dengan Redis SETNX
		initialRecord := IdempotencyRecord{
			Status:      "LOCKED",
			RequestHash: currentHash,
		}
		rawRecord, _ := json.Marshal(initialRecord)

		acquired, err := m.client.SetNX(ctx, redisKey, rawRecord, LockExpiry).Result()
		if err != nil {
			writeRFC9457Error(w, http.StatusServiceUnavailable, "Storage Failure", "Idempotency engine unavailable.")
			return
		}

		if !acquired {
			// Key sudah ada. Ambil datanya.
			existingVal, err := m.client.Get(ctx, redisKey).Result()
			if err != nil {
				writeRFC9457Error(w, http.StatusInternalServerError, "Storage Error", "Failed to retrieve idempotency data.")
				return
			}

			var rec IdempotencyRecord
			if err := json.Unmarshal([]byte(existingVal), &rec); err != nil {
				writeRFC9457Error(w, http.StatusInternalServerError, "Internal Deserialization Error", "Failed to read cache record.")
				return
			}

			// Validasi Request Tampering
			if rec.RequestHash != currentHash {
				writeRFC9457Error(w, http.StatusUnprocessableEntity, "Idempotency Conflict", "Payload does not match original request.")
				return
			}

			// Operasi masih berjalan
			if rec.Status == "LOCKED" {
				writeRFC9457Error(w, http.StatusConflict, "Request In Progress", "A transaction with this idempotency key is actively processing.")
				return
			}

			// Operasi selesai: Return Cached Response
			for k, v := range rec.Headers {
				w.Header().Set(k, v)
			}
			w.Header().Set("X-Cache-Lookup", "HIT - Idempotent Replay")
			w.WriteHeader(rec.StatusCode)
			w.Write([]byte(rec.Body))
			return
		}

		// Intercept writer response
		recorder := &responseRecorder{
			ResponseWriter: w,
			statusCode:     http.StatusOK,
			body:           &bytes.Buffer{},
			headers:        make(http.Header),
		}

		next.ServeHTTP(recorder, r)

		// Simpan payload response final
		completedRecord := IdempotencyRecord{
			Status:      "RESOLVED",
			RequestHash: currentHash,
			StatusCode:  recorder.statusCode,
			Headers:     map[string]string{"Content-Type": recorder.Header().Get("Content-Type")},
			Body:        recorder.body.String(),
		}
		completedBytes, _ := json.Marshal(completedRecord)

		m.client.Set(ctx, redisKey, completedBytes, IdempotencyTTL)
	})
}

type responseRecorder struct {
	http.ResponseWriter
	statusCode int
	body       *bytes.Buffer
	headers    http.Header
}

func (r *responseRecorder) WriteHeader(code int) {
	r.statusCode = code
	r.ResponseWriter.WriteHeader(code)
}

func (r *responseRecorder) Write(b []byte) (int, error) {
	r.body.Write(b)
	return r.ResponseWriter.Write(b)
}

func writeRFC9457Error(w http.ResponseWriter, status int, title, detail string) {
	w.Header().Set("Content-Type", "application/problem+json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"type":   "https://api.enterprise.com/errors/general",
		"title":  title,
		"status": status,
		"detail": detail,
	})
}
```

---

## 8. Real World Case Study: Payment Processing Gateway Under Partition

### Konteks Kasus
Platform e-commerce skala besar memproses rata-rata 15.000 transaksi pembayaran per detik (*peak*: 45.000 TPS). Sistem gateway berkomunikasi dengan upstream Third-Party Payment Service Providers (PSP) seperti Visa/Mastercard networks.

### Masalah Produksi
Terjadi degradasi jaringan (*packet drop* 12%) antara Payment Core Service dan PSP Gateway. Klien seluler mengalami *read-timeout* pada 2.500 ms, lalu mengotomatisasi *retry* secara agresif.
1. Akun nasabah terdebit berkali-kali untuk 1 transaksi pembelian (*Over-debit crisis*).
2. Upstream PSP memberlakukan penalti *hard rate limit* karena lonjakan beban mendadak (*thundering herd*), yang mengakibatkan *cascading failure* sistemik di seluruh checkout funnel.

### Solusi Arsitektural Enterprise
1. **Penerapan Deterministic Idempotency Key:** Klien diwajibkan menyertakan UUIDv4 saat `POST /v1/charges`. Key disimpan di Redis Cluster multi-zone dengan semantic lock.
2. **Exponential Backoff dengan Full Jitter:** Klien dilarang melakukan retry langsung. Algoritma retry diformulasikan:
   $$T_{sleep} = \min(M, \text{random}(0, 2^{\text{attempt}} \times B))$$
   di mana $B = 0.5\text{ detik}$, $M = 30\text{ detik}$.
3. **Outbox Pattern + Reconciliation Engine:** Apabila core gateway menerima status *PSP Timeout*, transaksi ditandai `PENDING_RECONCILIATION`. Webhook asinkron atau scheduled background worker melakukan *inquiry* status ke PSP secara deterministik tanpa re-executing credit card charge.

---

## 9. Trade-offs

Mengembangkan API bukan sekadar menentukan format terbaik secara mutlak, melainkan memetakan trade-off teknis dan bisnis:

```
                      Latency / Serialization Speed
                                 /\
                                /  \
                               /    \
                       gRPC   /      \  GraphQL
                             /        \
                            /          \
                           +------------+
                     Developer      Query Flexibility /
                    Ergonomics      Client Independence
                    (REST API)
```

| Dimensi | REST (JSON/HTTP/1.1 or 2) | gRPC (Protobuf/HTTP/2) | GraphQL (JSON/HTTP) | Async Webhooks (Event-Driven) |
| :--- | :--- | :--- | :--- | :--- |
| **P99 Latency** | Sedang (Tinggi CPU parse) | Sangat Rendah (< 5ms baseline)| Rendah - Buruk (Resolver nesting)| Sangat Cepat (Asinkron / Non-blocking) |
| **Payload Size**| Besar (Verbose Keys) | Sangat Kecil (Binary) | Disesuaikan kebutuhan klien | Bervariasi |
| **Cacheability**| Ekselen (HTTP Cache-Control natively)| Buruk (Harus pada layer aplikasi)| Sulit (POST request standard) | N/A (Event delivery) |
| **Over-fetching**| Kerap Terjadi | Terjadi (Skema paten) | Nol (Klien deklarasi field) | N/A |
| **Ecosystem** | Universal (Browser natively) | Memerlukan gRPC-Web di frontend| Kaya, tooling frontend matang | Webhook receiver variability |
| **Governance** | Manual via OpenAPI specs | Ketat via proto contracts | Sangat Ketat via GraphQL Schema| Skema Event Registry (CloudEvents) |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Kritis Lapisan Produksi

1. **"200 OK" Mengandung Error Payload:**
   * *Anti-Pattern:* Mengembalikan HTTP 200 dengan body `{"success": false, "error": "Unauthorized"}`.
   * *Dampak:* Menghancurkan kapabilitas monitoring APM (Datadog, New Relic), reverse proxy, dan WAF edge yang membaca metrik HTTP Status Code secara native.
   * *Solusi:* Gunakan kode status HTTP Layer 7 secara presisi (`401`, `403`, `422`, `503`).

2. **Non-Atomic Distributed Rate Limiting (Race Condition):**
   * *Anti-Pattern:* Mengambil counter `GET counter`, menjumlahkan di kode aplikasi `counter + 1`, lalu melakukan `SET counter`.
   * *Dampak:* Pada konkurensi tinggi, 10 request bersamaan membaca counter yang sama, menyebabkan klien dapat menembus batas kuota hingga 10x lipat.
   * *Solusi:* Seluruh operasi pengecekan dan pengurangan limit wajib berada di dalam satu transaksi atomic (Redis Lua Script atau `HINCRBY`).

3. **In-Memory Rate Limiting pada Multi-Instance Services:**
   * *Anti-Pattern:* Menggunakan *in-memory Go sync.Map* atau *Node.js memory* di balik load balancer.
   * *Dampak:* Klien melakukan rotasi request ke N server yang berbeda, sehingga batas kuota efektif ter-amplifikasi sebanyak N node instance.
   * *Solusi:* Sentralisasikan rate limit state ke distributed cache (Redis) dengan pipeline round-trip yang minimal.

---

## 11. Best Practices (Production Checklist)

### Contract & Evolution
- [ ] Schema terdefinisi menggunakan OpenAPI 3.1 atau Protocol Buffers versi 3.
- [ ] Breaking changes dicegah menggunakan automated schema diffing pada pipeline CI/CD (contoh: `buf breaking` atau `oasdiff`).
- [ ] Format tanggal/waktu dipaksakan mutlak ISO-8601 UTC (`YYYY-MM-DDTHH:mm:ssZ`).
- [ ] Deprecated field ditandai eksplisit dengan header `Deprecation: @<timestamp>` dan `Sunset: <date>` (RFC 8594).

### Resiliency & Performance
- [ ] Seluruh endpoint mutasi non-safe (`POST`, `PATCH`) mengimplementasikan *Idempotency-Key*.
- [ ] Request timeout dikonfigurasi secara eksplisit di seluruh layer (Gateway to Service: 3s, Service to DB: 1s).
- [ ] Pagination menggunakan metode *Cursor-Based Pagination* (menghindari `OFFSET` tinggi yang membebani query SQL).
- [ ] Kompresi gzip/brotli diaktifkan untuk payload di atas 1 KB.

### Security
- [ ] Strict CORS headers (hindari `Access-Control-Allow-Origin: *` pada internal APIs).
- [ ] Gateway memvalidasi `Content-Type: application/json` atau format yang diharapkan; tolak `text/html` yang mencurigakan.
- [ ] TLS 1.3 diwajibkan secara mutlak pada seluruh traffic publik.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sebuah implementasi produksi: **Idempotent Transaction API Gateway** menggunakan Node.js/TypeScript (atau Go) dengan Redis backplane yang dapat menangani retries deterministik.

### Struktur Direktori
```
hands-on/m02/
├── docker-compose.yml
├── package.json
├── tsconfig.json
└── src/
    ├── app.ts
    ├── middleware/
    │   └── idempotency.ts
    └── utils/
        └── redis.ts
```

### Langkah 1: Siapkan `docker-compose.yml`
```yaml
version: '3.8'
services:
  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
    command: ["redis-server", "--appendonly", "yes"]
```

Jalankan container:
```bash
docker compose up -d
```

### Langkah 2: Inisialisasi Project TypeScript
```bash
mkdir -p hands-on/m02/src/middleware hands-on/m02/src/utils
cd hands-on/m02
npm init -y
npm install express ioredis crypto
npm install --save-dev typescript @types/express @types/ioredis @types/node ts-node
npx tsc --init
```

### Langkah 3: Implementasikan Idempotency Engine (`src/middleware/idempotency.ts`)

```typescript
import { Request, Response, NextFunction } from 'express';
import Redis from 'ioredis';
import crypto from 'crypto';

const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');

export const idempotencyMiddleware = async (req: Request, res: Response, next: NextFunction) => {
  if (!['POST', 'PATCH'].includes(req.method)) {
    return next();
  }

  const idempotencyKey = req.header('Idempotency-Key');
  if (!idempotencyKey) {
    return res.status(400).json({
      type: "https://api.enterprise.com/errors/missing-header",
      title: "Bad Request",
      status: 400,
      detail: "Idempotency-Key header is strictly required."
    });
  }

  const payloadHash = crypto.createHash('sha256').update(JSON.stringify(req.body || {})).digest('hex');
  const cacheKey = `idempotency:${idempotencyKey}`;

  try {
    // Lua script: Atomic check and lock
    const acquireLockScript = `
      local current = redis.call('GET', KEYS[1])
      if current == false then
        redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
        return 'ACQUIRED'
      else
        return current
      end
    `;

    const lockPayload = JSON.stringify({ status: 'PENDING', hash: payloadHash });
    const result = await redis.eval(acquireLockScript, 1, cacheKey, lockPayload, 60) as string;

    if (result !== 'ACQUIRED') {
      const parsedRecord = JSON.parse(result);

      if (parsedRecord.hash !== payloadHash) {
        return res.status(422).json({
          type: "https://api.enterprise.com/errors/conflict",
          title: "Payload Mismatch",
          status: 422,
          detail: "This Idempotency-Key was already used for a different payload."
        });
      }

      if (parsedRecord.status === 'PENDING') {
        return res.status(409).json({
          type: "https://api.enterprise.com/errors/in-progress",
          title: "Conflict",
          status: 409,
          detail: "A transaction with this key is currently in processing. Try again later."
        });
      }

      // Replay Cached Result
      res.setHeader('X-Cache-Lookup', 'HIT - Replayed');
      return res.status(parsedRecord.statusCode).json(parsedRecord.body);
    }

    // Hijack res.json to capture response
    const originalJson = res.json.bind(res);
    res.json = (body: any): Response => {
      const finalPayload = JSON.stringify({
        status: 'RESOLVED',
        hash: payloadHash,
        statusCode: res.statusCode,
        body: body
      });

      // Simpan data resolusi final dengan TTL 24 jam
      redis.set(cacheKey, finalPayload, 'EX', 86400).catch(console.error);
      return originalJson(body);
    };

    next();
  } catch (error) {
    return res.status(500).json({
      type: "https://api.enterprise.com/errors/internal",
      title: "Internal Error",
      status: 500,
      detail: "Idempotency engine failure."
    });
  }
};
```

### Langkah 4: Hubungkan ke Server Application (`src/app.ts`)

```typescript
import express from 'express';
import { idempotencyMiddleware } from './middleware/idempotency';

const app = express();
app.use(express.json());

app.post('/api/v1/payments', idempotencyMiddleware, async (req, res) => {
  const { amount, recipient } = req.body;

  // Simulasi processing delay
  await new Promise(resolve => setTimeout(resolve, 1500));

  return res.status(201).json({
    transaction_id: `txn_${Math.random().toString(36).substring(2, 9)}`,
    amount,
    recipient,
    status: "SETTLED",
    timestamp: new Date().toISOString()
  });
});

app.listen(3000, () => {
  console.log("Enterprise API Gateway running on port 3000");
});
```

### Langkah 5: Pengujian Verifikasi CLI
1. Jalankan server: `npx ts-node src/app.ts`
2. Kirim transaksi pertama:
```bash
curl -i -X POST http://localhost:3000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-uuid-001" \
  -d '{"amount": 1000, "recipient": "user_abc"}'
```
*Hasil:* Respon `201 Created` setelah 1.5 detik.

3. Kirim *request* duplikat instan:
```bash
curl -i -X POST http://localhost:3000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-uuid-001" \
  -d '{"amount": 1000, "recipient": "user_abc"}'
```
*Hasil:* Respon langsung (`X-Cache-Lookup: HIT - Replayed`), `transaction_id` identik, tanpa re-eksekusi delay.

4. Coba *tampering payload* dengan key yang sama:
```bash
curl -i -X POST http://localhost:3000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-uuid-001" \
  -d '{"amount": 999999, "recipient": "attacker"}'
```
*Hasil:* Ditolak langsung dengan `422 Unprocessable Entity`.

---

## 13. Exercise

### Level Easy
Modifikasi skema error pada middleware hands-on agar sepenuhnya patuh terhadap spesifikasi **RFC 9457**.
* *Acceptance Criteria:* Format JSON keluaran harus memuat field `type`, `title`, `status`, `detail`, dan `instance` yang merefleksikan URI path request yang sedang diproses.

### Level Medium
Implementasikan skema **Distributed Sliding Window Counter Rate Limiter** menggunakan script Redis Lua di Node.js/Go.
* *Acceptance Criteria:* Rate limit dibatasi maksimal 100 request per menit per Client API Key. Algoritma harus menghitung beban window saat ini dan sisa bobot window sebelumnya secara proporsional. Request ke-101 wajib menghasilkan `HTTP 429 Too Many Requests` disertai header `Retry-After`.

### Level Hard
Bangun mekanisme **Graceful Degradation Circuit Breaker** pada API Gateway:
* *Acceptance Criteria:* Jika service downstream mengalami failure rate > 50% dalam window rolling 10 detik atau P95 latency > 2000ms, circuit trip ke mode `OPEN`. Seluruh request yang masuk langsung dilempar ke static fallback response atau dikembalikan dengan `HTTP 503 Service Unavailable` dalam waktu < 2 milidetik, tanpa membebani downstream yang sedang kolaps.

---

## 14. Challenge

### Studi Kasus: Multi-Region Active-Active Idempotency Under Split-Brain

Sebuah institusi perbankan global memiliki Deployment API di dua region: `ap-southeast-1` (Singapura) dan `us-east-1` (Virginia). Arsitektur dirancang Active-Active: klien dapat diarahkan ke region mana pun melalui Anycast DNS.

**Masalah:**
Kabel bawah laut terputus, menyebabkan degradasi komunikasi data WAN (*network partition*) antara Singapura dan Virginia selama 45 detik. Pada saat yang bersamaan, sebuah script otomasi klien payment gateway mengirimkan request pembayaran berulang kali dengan *Idempotency-Key* yang persis sama. Request pertama mendarat di node Singapura, sedangkan request *retry* mendarat di node Virginia.

**Tugas Arsitektural:**
1. Rancang arsitektur sinkronisasi state idempotency yang mampu mencegah *double charging* tanpa menambahkan penalti latency WAN lintas benua (*cross-region RTT penalty*) sebesar 200ms pada setiap transaksi normal.
2. Tentukan trade-off CAP Theorem apa yang Anda ambil (AP vs CP). Jika memilih CP, bagaimana Anda memitigasi availability loss? Jika memilih AP, bagaimana mekanisme *eventual reconciliation* menyelesaikan *double-spend* yang sudah terlanjur terjadi di dua region berbeda?
3. Buat bagan arsitektur sistem dan urutan mitigasi kegagalan (*step-by-step recovery process*).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Basic Level

1. **Mengapa `HTTP POST` didefinisikan sebagai non-idempotent sedangkan `HTTP PUT` idempotent menurut spesifikasi HTTP?**
   * *Jawaban:* `PUT` merepresentasikan penggantian (*replacement*) total resource pada URI spesifik; mengeksekusinya 1 kali atau 100 kali dengan representasi yang sama menghasilkan state akhir yang identik pada server. `POST` merepresentasikan pembuatan sub-resource subordinat atau eksekusi proses; memanggil `POST` berulang kali secara default akan membuat resource baru berulang kali atau memicu efek samping tambahan.

2. **Apa signifikansi header `Content-Type: application/problem+json`?**
   * *Jawaban:* Header ini mengindikasikan bahwa body respons menggunakan skema standar machine-readable RFC 7807/9457 untuk mendeskripsikan rincian error secara konsisten di seluruh enterprise.

3. **Mengapa Protocol Buffers lebih hemat bandwidth dibandingkan JSON?**
   * *Jawaban:* Protobuf mengonversi data menjadi biner menggunakan skema tag integer pendek dan pengkodean numerik efisien (*varint*), menghapus overhead nama-nama field teks dan spasi yang selalu dikirimkan pada JSON.

4. **Apa fungsi utama dari header `Retry-After` pada respons HTTP 429?**
   * *Jawaban:* Memberi tahu klien secara presisi berapa detik atau pada timestamp kapan klien diizinkan mencoba mengirimkan request kembali tanpa melanggar kuota rate limit.

5. **Apa perbedaan antara *Authentication* (AuthN) dan *Authorization* (AuthZ) pada level API Gateway?**
   * *Jawaban:* AuthN memvalidasi kebenaran identitas pengirim request (contoh: validitas signature JWT), sedangkan AuthZ menentukan apakah identitas yang sudah terverifikasi tersebut memiliki hak akses terhadap resource/aksi tertentu (RBAC/ABAC).

---

### 15.2 Intermediate Level

6. **Mengapa algoritma Fixed Window Counter rentan terhadap traffic spike pada batas jendela?**
   * *Jawaban:* Jika kuota adalah 100 request/menit, seorang penyerang dapat mengirim 100 request pada detik 00:59 dan 100 request lagi pada detik 01:01. Walaupun kedua request lolos pada masing-masing window, server sebenarnya menerima 200 request dalam interval waktu 2 detik, yang berpotensi melumpuhkan sistem.

7. **Bagaimana cara mencegah race condition pada implementasi Distributed Rate Limiter berbasis Redis?**
   * *Jawaban:* Mengemas seluruh logika pembacaan timestamp, kalkulasi token, dan penulisan state ke dalam sebuah **Redis Lua Script** yang dieksekusi secara atomic dan single-threaded oleh Redis engine, atau menggunakan primitive `INCR` ber-pipelined.

8. **Mengapa hash dari request body perlu disimpan bersamaan dengan Idempotency Key?**
   * *Jawaban:* Untuk mendeteksi *payload tampering* atau *accidental key collision*. Jika klien mengirimkan key yang sama namun memodifikasi data body, server dapat menolak request tersebut dengan `HTTP 422 Unprocessable Entity` guna mencegah manipulasi aksi bisnis.

9. **Apa risiko arsitektural penggunaan GraphQL di lingkungan enterprise publik dibanding REST?**
   * *Jawaban:* GraphQL rentan terhadap *Denial of Service* melalui *Deeply Nested Queries* atau *Cyclic Queries* (contoh: `author -> posts -> author -> posts`). Tanpa proteksi *Query Depth Limiting* dan *Query Cost Analysis*, penyerang dapat melumpuhkan database dengan 1 request GraphQL tunggal.

10. **Apa perbedaan pendekatan Versioning API via URI (`/v1/users`) vs Content Negotiation Header (`Accept: application/vnd.company.v1+json`)?**
    * *Jawaban:* URI versioning sangat eksplisit, mudah di-routing oleh gateway dan ramah browser caching, namun melanggar puritas REST di mana URI seharusnya merepresentasikan entitas, bukan versi representasi. Header Content Negotiation secara arsitektural benar menurut REST, menjaga URI tetap bersih, namun rumit dikonfigurasi di level reverse proxy, edge caching, dan manual testing tools.

---

### 15.3 Skenario Kasus Produksi

11. **Skenario 1:** *Sebuah payment service menggunakan circuit breaker. Saat payment gateway eksternal melambat (P99 naik dari 200ms ke 8000ms), API Gateway Anda kehabisan seluruh thread pool dan berhenti merespon seluruh request klien (termasuk static route yang tidak ada hubungannya). Apa root cause dan perbaikan arsitekturnya?*
    * *Analisis Root Cause:* Tidak diterapkannya isolasi resources (contoh: Thread Pool Isolation / Bulkhead Pattern) dan hilangnya timeout yang ketat (*missing upstream timeouts*). Gateway membiarkan koneksi menggantung menunggu respons lambat hingga seluruh worker pool terblokir.
    * *Solusi Arsitektural:*
      1. Terapkan pattern **Bulkhead Isolation**: Pisahkan alokasi thread pool dan HTTP connection pool untuk rute payments dari rute-rute independen lainnya.
      2. Set timeout agresif di API Gateway: *Read timeout* maksimum 2.5 detik.
      3. Konfigurasi Circuit Breaker dengan batas failure/slow-call threshold (misal: jika >30% call melebihi 2 detik, buka circuit secara instan).

12. **Skenario 2:** *Client melaporkan bahwa mereka menerima HTTP 409 Conflict secara acak pada endpoint idempotent saat koneksi seluler mereka tidak stabil. Pemeriksaan log server menunjukkan sistem memproses request pertama dengan status LOCKED.*
    * *Analisis Root Cause:* Klien seluler memiliki timeout lokal yang terlalu pendek (misal: 500ms) sedangkan server membutuhkan 1200ms untuk menyelesaikan transaksi. Klien memutuskan koneksi lalu melakukan *retry* instan dengan *Idempotency-Key* yang sama saat transaksi pertama masih aktif di server (*in-flight*).
    * *Solusi Arsitektural:*
      1. Tingkatkan timeout klien ke ambang batas wajar (misal: 3-5 detik) disertai *exponential backoff*.
      2. Ubah handling middleware: jika klien menerima status `LOCKED`, alih-alih melempar error statis `409`, middleware dapat menyediakan header `Retry-After: 1` atau klien mengimplementasikan polling status transaksi terhadap key tersebut.

13. **Skenario 3:** *Sebuah microservice internal mempublikasikan breaking change pada format respons Protobuf dengan mengubah tipe field `int32 user_id = 1;` menjadi `string user_id = 1;`. Layanan downstream yang belum compile-ulang protobuf mendadak panik dan crash. Mengapa ini terjadi padahal Protobuf dirancang backward-compatible?*
    * *Analisis Root Cause:* Protobuf menjamin backward-compatibility HANYA jika aturan evolusi skema dipatuhi. Mengubah tipe data untuk **nomor field yang sama** (*wire tag 1*) melanggar wire-format parsing. Protobuf melakukan encoding `int32` via format *Varint*, sedangkan `string` menggunakan format *Length-Delimited*. Parser biner downstream mencoba membaca *Length-Delimited bytes* sebagai *Varint*, memicu deserialization panic.
    * *Solusi Arsitektural:*
      1. Dilarang keras mengubah tipe data pada field tag yang sudah ada.
      2. Deprecate tag 1: `int32 old_user_id = 1 [deprecated = true];`
      3. Buat field baru dengan tag berbeda: `string user_id = 2;`
      4. Pasang CI/CD linter skema (contoh: `buf breaking --against`) untuk memblokir pull request yang melanggar integritas skema biner.

---

## 16. Summary

Merancang API skala produksi membutuhkan pergeseran paradigma: dari sekadar mendefinisikan rute dan *payload* menjadi mengelola sistem terdistribusi yang resilient terhadap kegagalan jaringan:

1. **Deterministic Idempotency:** Wajib diterapkan pada seluruh mutasi non-safe untuk menjamin semantik *Exactly-Once* pada domain bisnis menggunakan *Atomic Locking Engine* dan *Request Fingerprinting*.
2. **Standardized Contracts:** Gunakan RFC 9457 untuk pelaporan error terstruktur dan OpenAPI/Protobuf untuk mendefinisikan kontrak yang tervalidasi secara otomatis.
3. **Resilience Engineering:** Lindungi ekosistem API Anda dengan distributed rate limiting (Token/Sliding Window), circuit breaking, bulkhead isolation, dan graceful degradation.
4. **Protocol Selection by Merit:** Gunakan REST untuk integrasi publik dan kemudahan integrasi klien; manfaatkan gRPC untuk throughput tinggi serta latensi ultra-rendah pada komunikasi internal antar-layanan (*East-West traffic*).