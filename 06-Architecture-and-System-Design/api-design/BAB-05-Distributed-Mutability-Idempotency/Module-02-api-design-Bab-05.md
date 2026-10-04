# BAB 05: Distributed Mutability & Idempotency
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Merancang & Mengimplementasikan** *Enterprise Idempotency Engine* berbasis IETF Specification (`draft-ietf-httpapi-idempotency-key-header-04`) dengan *fingerprint validation* dan *distributed lock fencing*.
*   **Memitigasi Race Conditions & Double Mutation** pada transaksi terdistribusi konkuren tinggi menggunakan kombinasi Redis *distributed lock with dynamic leases* dan PostgreSQL *isolation levels* (`SERIALIZABLE` / `READ COMMITTED` dengan pessimistic locks).
*   **Menganalisis Trade-off Arsitektural** antara *latency overhead*, konsumsi memori cache, kompleksitas database, dan tingkat konsistensi (*at-least-once* vs *exactly-once execution semantics*).
*   **Melakukan Troubleshooting Kegagalan Sistem Transaksional** seperti *partial write failure*, *network timeout desynchronization*, *split-brain Redis clusters*, dan *stale locks*.

---

### 2. Prerequisite
Untuk menyerap materi secara optimal, Anda wajib memahami:
*   Prinsip ACID dan Distributed Transaction Management (Saga Pattern, 2PC).
*   HTTP Semantics (RFC 9110), khususnya perbedaan operasi *Safe*, *Idempotent* (GET, PUT, DELETE), dan *Non-Idempotent* (POST, PATCH).
*   Mekanisme *Distributed Locking* (Redis Redlock, lease-based locks, fencing tokens).
*   Go (Golang) tingkat lanjut (concurrency primitives: `sync.Mutex`, `goroutine`, `context`, channels).
*   SQL tingkat lanjut (PostgreSQL CTE, row-level locking `FOR UPDATE`, transaction isolation levels).

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi idempotensi pada sistem terdistribusi skala enterprise bukan sekadar menyimpan pasangan *key-value* di Redis. Operasi mutasi terdistribusi menghadapi tantangan fundamental: **The Two Generals' Problem** dan **Network Partitions (CAP Theorem)**.

#### Anatomi Idempotency Engine
Sebuah *Idempotency Engine* kelas produksi terdiri dari empat layer proteksi:

```
[ Request Inbound ]
        │
        ▼
[ Layer 1: Request Fingerprinting ]
  - Parse `Idempotency-Key` Header
  - Canonicalize JSON Payload + SHA-256 Hashing
  - Compare Signature (Mendeteksi Payload Tampering/Mismatched Replay)
        │
        ▼
[ Layer 2: Distributed Concurrency Guard (Atomic Mutex & Lease) ]
  - Redis SET NX EX dengan Fencing Token & Heartbeat/Lease Renewal
  - Mencegah eksekusi paralel dari request identik (Race Condition Prevention)
        │
        ▼
[ Layer 3: Persistent State Machine (PostgreSQL / Core Ledger) ]
  - Transisi Status: PENDING ➔ EXECUTING ➔ RESOLVED | FAILED
  - Database Unique Constraint (`idempotency_key`, `scope_id`)
  - Outbox Pattern Integration (Transactional Atomicity)
        │
        ▼
[ Layer 4: Response Caching & Stream Replay ]
  - HTTP Status, Headers, dan Body disimpan terkompresi
  - Replay response secara deterministik tanpa re-executing side-effects
```

#### Siklus Hidup Transaksi Idempotent (State Machine)
Sebuah request yang membawa `Idempotency-Key` harus melalui state machine formal:

```
                  ┌────────────────────────┐
                  │      REQUEST IN        │
                  └───────────┬────────────┘
                              │
                    Key Exists in Store?
                   /                    \
                [YES]                   [NO]
                 /                        \
    Fingerprint Matches?             Acquire Lock & Insert
    /                 \              State: 'STARTED'
  [NO]               [YES]                  │
   │                   │                    ▼
Emit 422/409     State == 'STARTED'?   Execute Business
Unprocessable    /               \     Domain Transaction
               [YES]             [NO]       │
                 │                 │        ▼
            Emit 409/Wait     State ==  Success?
             (In Flight)      'RESOLVED'? /     \
                                 │     [YES]    [NO]
                                 │       │        │
                            Replay Cached ──┐   Update State:
                               Response     │   'FAILED'
                                            │     │
                                            ▼     ▼
                                   Update State: 'RESOLVED'
                                   Save Response Payload
                                   Release Distributed Lock
```

1.  **STARTED**: Kunci terkunci; payload sedang diproses oleh domain logic.
2.  **RESOLVED**: Eksekusi sukses, response cache tersimpan permanen/semi-permanen.
3.  **FAILED**: Transaksi domain gagal secara fatal. Tergantung kebijakan bisnis, key dapat di-*release* agar klien dapat mencoba kembali (*retryable*) atau di-*lock* sebagai transaksi gagal permanen.

#### Rekayasa Request Fingerprinting
Menyimpan key tanpa memvalidasi payload adalah kerentanan keamanan dan integritas fatal. Jika client menggunakan kembali key `abc-123` untuk request `$10` ke user A, lalu secara keliru mengirim key yang sama untuk request `$10,000` ke user B, sistem **wajib menolak** request kedua dengan status `422 Unprocessable Entity` atau `409 Conflict`, bukan mengembalikan response dari transaksi pertama.

Formula Fingerprint:
$$\text{Fingerprint} = \text{HMAC-SHA256}(\text{IdempotencyKey} \parallel \text{HTTPMethod} \parallel \text{CanonicalURI} \parallel \text{CanonicalPayload}, \text{SecretKey})$$

*CanonicalPayload* mengharuskan normalisasi JSON (mengurutkan keys, menghapus spasi/whitespace non-signifikan) untuk menghindari kegagalan fingerprinting akibat perbedaan formatting whitespace serializer client.

---

### 4. Why & What

| Dimensi | Mengapa Dibutuhkan (The Why) | Apa Solusinya (The What) |
| :--- | :--- | :--- |
| **Network Flakiness** | Client mengirim request, server memprosesnya, tetapi koneksi TCP putus sebelum server mengirim response. Client melakukan retry otomatis. | Sistem mendeteksi `Idempotency-Key` yang sama, melompati pemrosesan domain, dan memutar ulang (*replay*) response dari *persistence layer*. |
| **Parallel Concurrent Retries** | Client agresif (misal: mobile app dengan connection hopping) mengirim request yang sama persis secara paralel dalam selang waktu < 50ms. | *Atomic Distributed Mutex* (Redis `SET NX` / Postgres row lock) memastikan hanya thread pertama yang mengeksekusi logic; thread kedua ditahan (*wait/poll*) atau menerima `409 Conflict`. |
| **Side-Effect Duplication** | Sistem melakukan mutasi internal lalu memanggil Third-Party API (misal: Visa, Stripe, Twilio) yang tidak idempotent secara default. | *Outbox Pattern* terintegrasi dengan Idempotency Engine untuk menjamin downstream event hanya di-dispatch tepat satu kali secara logis. |
| **Payload Inconsistency** | Human/Logic error pada client yang menggunakan shared sequence generator yang salah untuk payload yang berbeda. | Validasi *Request Fingerprint* membatalkan mutasi secara instan jika payload berubah untuk key yang sama. |

---

### 5. How (Workflow Detail)

Alur eksekusi internal middleware idempotensi standar perbankan:

1.  **Ekstraksi Header**: Baca header `Idempotency-Key`. Jika tidak ada, proses sebagai request standar non-idempotent (atau tolak jika konfigurasi mewajibkannya).
2.  **Normalisasi & Fingerprint**: Serialisasi ulang body request ke bentuk *canonical JSON*, gabungkan dengan path dan method, kalkulasikan SHA-256 hash.
3.  **Distributed Lock Acquisition**:
    *   Eksekusi Redis Command: `SET lock:{key} {worker_id} NX PX 30000` (TTL 30 detik).
    *   Jika gagal acquire lock: Masuk ke mekanisme *polling* selama maksimal N detik (menunggu request paralel pertama selesai) atau langsung return `409 Conflict` dengan header `Retry-After: 1`.
4.  **Database State Lookup**:
    *   Cari record idempotency di DB berdasarkan `key` dan `tenant_id`.
    *   Jika status `RESOLVED`: Validasi fingerprint. Jika cocok, decode cached response, set header `Idempotent-Replayed: true`, dan langsung kembalikan ke client (Short-circuit).
    *   Jika status `STARTED`: Lepaskan lock, return `409 Conflict` (*Concurrent Mutation In Progress*).
5.  **Eksekusi Domain Logic**: Jalankan proses bisnis dalam transaksi DB lokal.
6.  **Simpan Status & Response**:
    *   Dalam transaksi yang sama (atau transaksional outbox): simpan response status code, header, dan body ke tabel `idempotency_records` dengan status `RESOLVED`.
7.  **Pelepasan Distributed Lock**: Hapus kunci di Redis melalui Lua script (hanya hapus jika value sama dengan `worker_id` untuk mencegah accidental release akibat lease expired).
8.  **Return Response**: Kembalikan response asli ke pemanggil.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata
Bayangkan sebuah loket transfer bank dengan kotak deposit berlabel unik. Nasabah memasukkan instruksi transfer dalam amplop tertutup dengan stempel lilin bernomor seri unik (`Idempotency-Key`).
Jika nasabah tidak mendengar jawaban teller karena kaca pemisah kedap suara (network timeout) dan mengirimkan amplop kedua dengan nomor seri yang sama:
1. Teller pertama-tama memeriksa buku besar.
2. Jika transaksi dengan nomor seri tersebut sedang dihitung oleh teller lain, teller meminta nasabah menunggu.
3. Jika transaksi sudah selesai, teller langsung menyobek salinan kuitansi yang sudah ada di arsip dan memberikannya kepada nasabah tanpa memindahkan uang dari brankas lagi.
4. Jika isi amplop kedua berbeda nominalnya dengan catatan awal untuk nomor seri itu, teller membunyikan alarm penipuan (fingerprint mismatch).

#### Diagram Interaksi Konkuren (ASCII Flowchart)

```
Client A (Req-1)        Client B (Req-1 Retry)      API Gateway/Service         Redis Cache            PostgreSQL
   │                            │                            │                       │                     │
   ├─ POST /orders ─────────────┼───────────────────────────>│                       │                     │
   │  Key: "k-100", Body: {...} │                            │                       │                     │
   │                            │                            ├─ SET lock:k-100 NX ──>│                     │
   │                            │                            │<── OK (Acquired) ─────┤                     │
   │                            │                            │                                             │
   │                            │                            ├─ SELECT * FROM idempotency WHERE key='k-100'│
   │                            │                            │<── Empty (Not Found) ───────────────────────┤
   │                            │                            │                                             │
   │                            ├─ POST /orders ────────────>│                                             │
   │                            │  Key: "k-100", Body: {...} │                                             │
   │                            │                            ├─ SET lock:k-100 NX ──>│                     │
   │                            │                            │<── NIL (Failed) ──────┤                     │
   │                            │                            │                                             │
   │                            │<── 409 Conflict ───────────┤                                             │
   │                            │    (Processing In Flight)  │                                             │
   │                            │                            ├─ BEGIN TX ─────────────────────────────────>│
   │                            │                            │  INSERT INTO orders ...                     │
   │                            │                            │  INSERT INTO idempotency (k-100, RESOLVED)  │
   │                            │                            │  COMMIT TX ────────────────────────────────>│
   │                            │                            │                                             │
   │                            │                            ├─ DEL lock:k-100 ─────>│                     │
   │<── 201 Created (Original) ─┼────────────────────────────┤                                             │
   │                            │                            │                                             │
   │                            ├─ POST /orders (Retry 2) ──>│                                             │
   │                            │  Key: "k-100", Body: {...} │                                             │
   │                            │                            ├─ SELECT * FROM idempotency WHERE key='k-100'│
   │                            │                            │<── Record Found (RESOLVED) ─────────────────┤
   │                            │                            │                                             │
   │                            │<── 201 Created (Replayed) ─┤                                             │
   │                            │    Header: Idempotent-Replay: true                                       │
```

---

### 7. Simple Example & Practical Example

#### Simple Example (Konseptual - Redis Lock Basic)
```go
// Pola sederhana rawan kegagalan jika service crash di tengah eksekusi
func SimpleIdempotentHandler(w http.ResponseWriter, r *http.Request) {
    key := r.Header.Get("Idempotency-Key")
    val, err := redisClient.Get(ctx, key).Result()
    if err == nil {
        w.Write([]byte(val)) // Replay
        return
    }

    // Eksekusi domain
    res := executeBusiness()
    redisClient.Set(ctx, key, res, 24*time.Hour)
    w.Write([]byte(res))
}
```

#### Practical Example (Enterprise Production Standard)
Implementasi menggunakan Go, Redis (Distributed Lock dengan validasi ownership via Lua script), dan PostgreSQL (ACID Persistence & Fingerprint Verification).

```go
package idempotency

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
)

var (
	ErrLockAcquisitionFailed = errors.New("concurrent mutation in progress")
	ErrPayloadMismatch       = errors.New("idempotency key reused with different payload")
)

type RecordStatus string

const (
	StatusStarted  RecordStatus = "STARTED"
	StatusResolved RecordStatus = "RESOLVED"
	StatusFailed   RecordStatus = "FAILED"
)

type IdempotencyRecord struct {
	Key             string       `json:"key"`
	TenantID        string       `json:"tenant_id"`
	RequestHash     string       `json:"request_hash"`
	Status          RecordStatus `json:"status"`
	ResponseCode    int          `json:"response_code"`
	ResponseBody    []byte       `json:"response_body"`
	ResponseHeaders []byte       `json:"response_headers"`
	CreatedAt       time.Time    `json:"created_at"`
	UpdatedAt       time.Time    `json:"updated_at"`
}

type Engine struct {
	db          *sql.DB
	redisClient *redis.Client
	lockTTL     time.Duration
}

func NewEngine(db *sql.DB, rdb *redis.Client, lockTTL time.Duration) *Engine {
	return &Engine{
		db:          db,
		redisClient: rdb,
		lockTTL:     lockTTL,
	}
}

// ComputeFingerprint menghasilkan SHA256 string deterministik dari canonicalized payload
func (e *Engine) ComputeFingerprint(method, uri string, rawBody []byte) (string, error) {
	var canonicalJSON []byte
	if len(rawBody) > 0 {
		var jsonObj interface{}
		if err := json.Unmarshal(rawBody, &jsonObj); err != nil {
			return "", fmt.Errorf("invalid json body: %w", err)
		}
		var err error
		canonicalJSON, err = json.Marshal(jsonObj) // Membuang arbitrary whitespaces
		if err != nil {
			return "", err
		}
	}
	hasher := sha256.New()
	hasher.Write([]byte(method + ":" + uri + ":"))
	hasher.Write(canonicalJSON)
	return hex.EncodeToString(hasher.Sum(nil)), nil
}

// AcquireDistributedLock mengunci resource menggunakan safe Redis Mutex
func (e *Engine) AcquireDistributedLock(ctx context.Context, key string, workerID string) (bool, error) {
	lockKey := fmt.Sprintf("lock:idempotency:%s", key)
	return e.redisClient.SetNX(ctx, lockKey, workerID, e.lockTTL).Result()
}

// ReleaseDistributedLock melepas lock hanya jika ownership cocok (atomic lua script)
func (e *Engine) ReleaseDistributedLock(ctx context.Context, key string, workerID string) error {
	lockKey := fmt.Sprintf("lock:idempotency:%s", key)
	luaRelease := `
		if redis.call("get", KEYS[1]) == ARGV[1] then
			return redis.call("del", KEYS[1])
		else
			return 0
		end
	`
	return e.redisClient.Eval(ctx, luaRelease, []string{lockKey}, workerID).Err()
}

// ExecuteWrap mengelola siklus idempotency secara transaksional
func (e *Engine) ExecuteWrap(
	ctx context.Context,
	tenantID, key string,
	req *http.Request,
	body []byte,
	domainLogic func(tx *sql.Tx) (int, http.Header, []byte, error),
) (int, http.Header, []byte, bool, error) {

	requestHash, err := e.ComputeFingerprint(req.Method, req.URL.RequestURI(), body)
	if err != nil {
		return http.StatusBadRequest, nil, nil, false, err
	}

	workerID := uuid.New().String()

	// 1. Acquire Distributed Mutex
	acquired, err := e.AcquireDistributedLock(ctx, key, workerID)
	if err != nil {
		return http.StatusInternalServerError, nil, nil, false, err
	}
	if !acquired {
		return http.StatusConflict, nil, []byte(`{"error":"concurrent mutation in progress"}`), false, ErrLockAcquisitionFailed
	}
	defer e.ReleaseDistributedLock(context.Background(), key, workerID)

	// 2. Cek apakah record sudah ada di Database
	var existingRecord IdempotencyRecord
	query := `
		SELECT key, tenant_id, request_hash, status, response_code, response_body, response_headers 
		FROM idempotency_records 
		WHERE key = $1 AND tenant_id = $2 FOR UPDATE
	`
	tx, err := e.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return http.StatusInternalServerError, nil, nil, false, err
	}
	defer tx.Rollback()

	err = tx.QueryRowContext(ctx, query, key, tenantID).Scan(
		&existingRecord.Key,
		&existingRecord.TenantID,
		&existingRecord.RequestHash,
		&existingRecord.Status,
		&existingRecord.ResponseCode,
		&existingRecord.ResponseBody,
		&existingRecord.ResponseHeaders,
	)

	if err == nil {
		// Verifikasi Fingerprint
		if existingRecord.RequestHash != requestHash {
			return http.StatusUnprocessableEntity, nil, []byte(`{"error":"payload signature mismatch"}`), false, ErrPayloadMismatch
		}

		if existingRecord.Status == StatusResolved {
			var headers http.Header
			_ = json.Unmarshal(existingRecord.ResponseHeaders, &headers)
			return existingRecord.ResponseCode, headers, existingRecord.ResponseBody, true, nil
		}

		if existingRecord.Status == StatusStarted {
			return http.StatusConflict, nil, []byte(`{"error":"transaction is being processed"}`), false, ErrLockAcquisitionFailed
		}
	} else if !errors.Is(err, sql.ErrNoRows) {
		return http.StatusInternalServerError, nil, nil, false, err
	}

	// 3. Insert State STARTED
	insertQuery := `
		INSERT INTO idempotency_records (key, tenant_id, request_hash, status, response_code, created_at, updated_at)
		VALUES ($1, $2, $3, $4, 0, NOW(), NOW())
		ON CONFLICT (key, tenant_id) DO UPDATE SET updated_at = NOW()
	`
	if _, err := tx.ExecContext(ctx, insertQuery, key, tenantID, requestHash, StatusStarted); err != nil {
		return http.StatusInternalServerError, nil, nil, false, err
	}

	// 4. Eksekusi Domain Transaction Logic
	respCode, headers, respBody, domainErr := domainLogic(tx)
	if domainErr != nil {
		// Logika gagal, update status menjadi FAILED
		failQuery := `UPDATE idempotency_records SET status = $1, updated_at = NOW() WHERE key = $2 AND tenant_id = $3`
		_, _ = tx.ExecContext(ctx, failQuery, StatusFailed, key, tenantID)
		_ = tx.Commit()
		return respCode, headers, respBody, false, domainErr
	}

	// 5. Serialize Response Headers
	headersJSON, _ := json.Marshal(headers)

	// 6. Update Status ke RESOLVED & simpan Response
	resolveQuery := `
		UPDATE idempotency_records 
		SET status = $1, response_code = $2, response_body = $3, response_headers = $4, updated_at = NOW()
		WHERE key = $5 AND tenant_id = $6
	`
	if _, err := tx.ExecContext(ctx, resolveQuery, StatusResolved, respCode, respBody, headersJSON, key, tenantID); err != nil {
		return http.StatusInternalServerError, nil, nil, false, err
	}

	// 7. Commit Semua Mutasi Database Secara Atomik
	if err := tx.Commit(); err != nil {
		return http.StatusInternalServerError, nil, nil, false, err
	}

	return respCode, headers, respBody, false, nil
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Payment Settlement Engine (Transaksi Rp 5 Triliun/Hari)
*   **Insiden**: Saat promo "Harbolnas", traffic loncat dari 3,000 RPS ke 45,000 RPS. Terjadi lonjakan *HTTP 504 Gateway Timeout* antara API Gateway dan Core Ledger. Mobile app melakukan *exponential backoff retry* secara agresif.
*   **Dampak Buruk**: Muncul anomali *Double-Disbursement*. Saldo beberapa merchant terpotong dua kali untuk pesanan yang sama karena idempotency layer awal hanya berbasis Redis cache `SETNX` tanpa verifikasi row-lock transaksional database. Ketika Redis mengalami *memory pressure evictions*, kunci idempotency terhapus sebelum request timeout selesai diproses di Postgres. Request kedua masuk, mendapati Redis kosong, lalu memicu settlement ulang.

#### Solusi Arsitektural Produksi
1.  **Dual-tier Verification**: Redis hanya dialokasikan sebagai *Guard against Concurrency* (Short TTL: 30-60 detik). Sumber kebenaran mutlak idempotensi dipindahkan ke tabel PostgreSQL dengan partisi berbasis waktu (*Postgres Declarative Partitioning by Hash/Range*).
2.  **Explicit Fencing Tokens**: Mengintegrasikan sequence token atomik dari PostgreSQL ke dalam lock Redis. Jika transaksi thread pertama berjalan lambat melebihi TTL Redis, token thread pertama menjadi *stale*, mencegahnya melakukan *commit* ganda.
3.  **Graceful Recovery**: Ketika terjadi koneksi database overload, API Gateway memotong request dengan *Fast-fail* `429 Too Many Requests` disertai header `Retry-After`, daripada membiarkan koneksi menggantung hingga 504 Timeout.

---

### 9. Trade-offs

```
                       [ Konsistensi Mutlak ]
                       (PostgreSQL Row Locking)
                                 ▲
                                / \
                               /   \
                              /     \
                             /       \
                            /         \
    [ Latensi Minimal ] ◄───────────────► [ Skalabilitas Ekstrem ]
  (Redis Caching Standalone)               (Event-driven / Async Outbox)
```

| Pendekatan | Kelebihan | Kelemahan | Latency Impact | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- | :--- |
| **Pure Redis Cache-Aside** | Sangat cepat (< 2ms lookup overhead). | Rawan data loss saat eviction/failover; *at-least-once* violation. | Rendah (~1-3ms) | Read-heavy mutasi non-finansial (Like, Check-in). |
| **Pure Database Constraint** | Zero race condition; ACID compliance 100%. | Beban tinggi pada DB engine; degradasi IOPS; lock contention tinggi. | Sangat Tinggi (~25-80ms) | Low throughput, high-value core banking transactions. |
| **Hybrid (Redis Lock + DB State)** | Melindungi DB dari lonjakan paralel konkurensi; ACID guarantee tetap terjaga. | Kompleksitas kode bertambah (harus menangani Redis failure & DB failure terpisah). | Menengah (~8-18ms) | **Enterprise Gold Standard**: Payments, Order Creations, Inventory Allocations. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum 1: Ignorant Error Responses Caching
*   **Masalah**: Developer meng-cache response `500 Internal Server Error` ke dalam tabel idempotency.
*   **Konsekuensi**: Ketika database downstream atau third-party gateway pulih, pemanggilan berikutnya dari client terus-menerus disajikan error 500 yang di-replay dari cache secara permanen.
*   **Solusi**: Hanya simpan response dengan status code definitif (`2xx`, `4xx`). Response `5xx` harus menandai record sebagai `FAILED` dan membersihkan kuncinya agar client dapat me-retry operasi dengan payload yang sama.

#### Kesalahan Umum 2: Blind Trust to Client-Generated Keys
*   **Masalah**: Klien mengirimkan string statis seperti `"12345"` atau `null` di header `Idempotency-Key`.
*   **Solusi**: Terapkan *Key Validation Middleware*. Wajibkan format UUIDv4 atau string base64 dengan panjang minimal 24 karakter dan maksimal 128 karakter.

#### Troubleshooting Table

| Gejala Masalah | Investigasi Root Cause | Langkah Remediasi |
| :--- | :--- | :--- |
| **HTTP 409 Infinite Loop** | Request pertama crash di tengah jalan tanpa blok `defer` release lock; Redis lock tertinggal dengan TTL terlalu lama. | Terapkan *heartbeat lock extension* dan pastikan script pelepasan lock selalu berada dalam blok `defer`/`finally` yang aman terhadap panic runtime. |
| **HTTP 422 Payload Mismatch** | Client SDK mengirim field `timestamp` atau `dynamic nonce` di dalam JSON body saat melakukan retry. | Dokumentasikan ke tim client bahwa retry payload **harus identik secara byte**. Kecualikan field audit gateway non-deterministik saat menghitung hash. |
| **PostgreSQL Connection Pool Starvation** | Transaksi database dibiarkan terbuka (`BEGIN`) sambil menunggu panggilan HTTP ke third-party API eksternal. | **Anti-Pattern!** Dilarang melakukan Network I/O di dalam transaksi SQL. Gunakan Outbox Pattern: Commit state mutasi ke database terlebih dahulu, lalu lakukan network call melalui asynchronous worker. |

---

### 11. Best Practices (Production Checklist)

*   [ ] **Gunakan IETF Header Standard**: Gunakan header `Idempotency-Key` (hindari custom header seperti `X-Request-ID` untuk fungsi mutasi idempotensi).
*   [ ] **Implementasikan Canonical Payload Hashing**: Normalisasikan JSON sebelum melakukan hashing untuk mencegah mismatch akibat serialization quirks.
*   [ ] **Pisahkan Lock Concurrency dari Status Storage**: Gunakan Redis untuk distributed locking (TTL pendek: 30-120 detik) dan RDBMS untuk persistent audit & response store (TTL panjang: 7-90 hari).
*   [ ] **Simpan Response Lengkap**: Cache tidak hanya body, tetapi juga status HTTP dan response header esensial (seperti `Content-Type`, `Location`).
*   [ ] **Tandai Replayed Response**: Selalu sertakan header `Idempotent-Replayed: true` saat mengembalikan response dari cache agar dapat dipantau oleh client SDK dan monitoring tools.
*   [ ] **Terapkan Data Retention & Partitioning**: Buat scheduler (PostgreSQL pg_cron / TTL indexes di Mongo/Cassandra) untuk membersihkan idempotency records yang lebih lama dari retention window (misal: 30 hari).
*   [ ] **Zero Network Calls inside Locks/Transactions**: Jangan pernah memanggil external gateway di dalam scope Database Transaction atau Redis Lock yang ketat.

---

### 12. Hands-on Practice

Buatlah sistem verifikasi idempotensi lokal untuk memvalidasi proteksi double-spending.

#### Langkah 1: Struktur Direktori
Buat direktori proyek:
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
go mod init enterprise-idempotency
```

#### Langkah 2: Docker Compose (`hands-on/m02/docker-compose.yml`)
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: engine_user
      POSTGRES_PASSWORD: engine_password
      POSTGRES_DB: idempotency_db
    ports:
      - "5432:5432"
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

#### Langkah 3: Skema Migrasi SQL (`hands-on/m02/init.sql`)
```sql
CREATE TABLE IF NOT EXISTS idempotency_records (
    key VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(64) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    response_code INT NOT NULL,
    response_body BYTEA,
    response_headers JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, key)
);

CREATE INDEX idx_idempotency_lookup ON idempotency_records (tenant_id, key, status);
```

#### Langkah 4: Menjalankan Test Konkurensi Tinggi
Gunakan tool benchmark seperti `hey` atau bash script konkuren untuk menembakkan request identik:
```bash
docker-compose up -d
# Eksekusi database migration script ke postgres
# Jalankan service Golang Anda
```

Eksekusi script verifikasi ganda:
```bash
#!/usr/bin/env bash
KEY="test-tx-$(date +%s)"
PAYLOAD='{"account_id": "ACC-001", "amount": 500000}'

echo "Firing 5 concurrent requests with identical Idempotency-Key..."
for i in {1..5}; do
   curl -s -w "\nHTTP Code: %{http_code} | Time: %{time_total}s\n" \
        -X POST http://localhost:8080/api/v1/disburse \
        -H "Content-Type: application/json" \
        -H "Idempotency-Key: $KEY" \
        -H "X-Tenant-ID: tenant-indonesia" \
        -d "$PAYLOAD" &
done
wait
```

*Output yang Diharapkan*: Tepat **satu** request mengembalikan `HTTP 201 Created` (Original), sementara empat request lainnya mengembalikan `HTTP 409 Conflict` (jika request paralel belum selesai) atau `HTTP 201 Created` dengan `Idempotent-Replayed: true` (jika request pertama telah selesai). **Tidak boleh ada transaksi ganda di database.**

---

### 13. Exercise

#### Level: Easy
1. Modifikasi kode `ComputeFingerprint` pada section practical example untuk mengabaikan field dynamic `client_timestamp` yang disematkan client di root JSON body.

#### Level: Medium
2. Implementasikan mekanisme fallback: Jika Redis cluster down (connection refused/timeout), engine harus tetap dapat mempertahankan jaminan idempotensi menggunakan fallback ke database row locking (`SELECT FOR UPDATE NOWAIT`) tanpa menyebabkan crash sistem. Tangani error Postgres `55P03` (*lock_not_available*).

#### Level: Hard
3. Buat implementasi *Idempotency Heartbeat (Lock Extension)*. Jika domain logic berjalan lebih lama dari lock TTL awal (misal proses data lake yang memakan waktu 45 detik dengan TTL lock 10 detik), sebuah background goroutine harus memperpanjang TTL kunci di Redis setiap 5 detik secara aman hingga context selesai.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Architect di Bank Sentral yang memproses sistem kliring instan (*Real-Time Gross Settlement / RTGS*). Klien korporat mengalami network split tepat saat mutasi debit antar-bank berhasil dilakukan di ledger internal Anda, namun sebelum transaksi kliring eksternal dimulai.
Klien me-retry transaksi 30 detik kemudian dengan `Idempotency-Key` yang sama persis, tetapi saat itu database utama Anda sedang mengalami failover ke *Read-Replica* yang memiliki *replication lag* sebesar 2.5 detik.

**Tantangan**:
1. Rancang arsitektur yang menjamin sistem tidak mengeksekusi debit ulang meskipun *replica database* belum menerima catatan idempotency dari instance master yang lama (*stale read anomaly*).
2. Tentukan bagaimana response gateway dirancang agar klien enterprise tidak menganggap transaksinya gagal padahal debit telah terverifikasi.
3. Gambarkan diagram alur data lengkap penanganan split-brain tersebut tanpa mengorbankan Service Level Objective (SLO) ketersediaan API 99.999%.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Mengapa method HTTP POST secara default didefinisikan sebagai non-idempotent menurut RFC 9110?**
   * A. Karena POST tidak mendukung pengiriman payload JSON.
   * B. Karena pengiriman POST berulang dengan data yang sama menghasilkan side-effect baru di server (misal: duplikasi record).
   * C. Karena POST tidak dapat di-cache oleh browser.
   * D. Karena POST hanya digunakan untuk mengambil resource tanpa mutasi.
2. **Karakteristik header `Idempotency-Key` yang benar menurut standardisasi draft IETF adalah:**
   * A. Digenerate oleh server saat request pertama diterima.
   * B. Disimpan secara permanen di browser cookie.
   * C. Digenerate secara unik oleh client sebelum mengirimkan request mutasi.
   * D. Menggunakan counter incrementing angka dari database server.
3. **Apa kegunaan utama dari melakukan canonicalization pada JSON payload sebelum proses hashing?**
   * A. Mengurangi ukuran data payload hingga 50%.
   * B. Mengenkripsi payload agar tidak dapat dibaca oleh proxy layer.
   * C. Menghilangkan whitespace/formatting quirks sehingga hash identik meskipun format penulisan JSON berbeda.
   * D. Memvalidasi bahwa seluruh field request memiliki tipe data string.
4. **Header HTTP apa yang idealnya dikembalikan oleh server jika client mencoba mengakses key idempotency yang transaksinya masih berjalan di background?**
   * A. 200 OK
   * B. 404 Not Found
   * C. 409 Conflict
   * D. 502 Bad Gateway
5. **Operasi Redis manakah yang menjamin akuisisi distributed lock bersifat atomic?**
   * A. `GET` dilanjutkan dengan `SET`
   * B. `SET key value NX PX milliseconds`
   * C. `HSET key field value`
   * D. `LPUSH key value`

#### Intermediate (5 Soal)
6. **Apa bahaya terbesar jika distributed lock dilepas menggunakan perintah sederhana `redis.Del(ctx, key)` tanpa memvalidasi value tokennya?**
   * A. Menghasilkan error syntax pada Redis engine.
   * B. Menghapus lock milik proses lain jika proses saat ini berjalan melebihi durasi TTL lock (accidental unlock).
   * C. Mengunci Redis keyspace secara permanen.
   * D. Menurunkan throughput query database hingga 0.
7. **Jika client mengirimkan `Idempotency-Key` yang sama namun mengubah isi body request (misal nominal transfer berubah), tindakan apa yang wajib diambil oleh server?**
   * A. Update data transaksi lama dengan nominal baru.
   * B. Tolak transaksi dengan HTTP 422 Unprocessable Entity atau 409 Conflict (Payload Signature Mismatch).
   * C. Eksekusi transaksi baru dan timpa record idempotency lama.
   * D. Kembalikan cached response dari transaksi pertama tanpa error.
8. **Kapan response HTTP boleh disimpan ke dalam persistent idempotency store sebagai state `RESOLVED`?**
   * A. Sesaat sebelum distributed lock di-acquire.
   * B. Di awal middleware sebelum proses bisnis dijalankan.
   * C. Tepat setelah transaksi database bisnis di-commit secara atomik.
   * D. Saat koneksi TCP socket ke client berhasil ditutup.
9. **Dalam skenario Database Primary-Replica, apa bahaya membaca record idempotency dari replica node?**
   * A. Query selalu return error syntax.
   * B. Replication lag dapat menyebabkan cache-miss palsu yang berujung pada eksekusi ganda di master node.
   * C. Replica node otomatis mengunci tabel secara eksklusif.
   * D. Fingerprint SHA-256 tidak dapat dihitung di replica node.
10. **Bagaimana status `500 Internal Server Error` harus ditangani oleh Idempotency Engine?**
    * A. Disimpan secara permanen agar error terus di-replay untuk menjaga konsistensi.
    * B. Status transaksi ditandai `FAILED` atau kuncinya di-evict agar request yang sama dapat di-retry ulang oleh client.
    * C. Mengubah status HTTP menjadi 200 OK secara otomatis.
    * D. Menghapus seluruh tabel audit idempotency di database.

#### Skenario Kasus Produksi (3 Soal)
11. **Skenario 1**: Sebuah microservice order mengalami crash (Out-Of-Memory Panic) tepat setelah meng-insert record ke database order tetapi sebelum sempat mengupdate tabel idempotency dari `STARTED` ke `RESOLVED`. Ketika service hidup kembali, client mengirimkan retry request dengan key yang sama. Apa yang terjadi jika engine Anda tidak memiliki mekanisme expired-recovery pada state `STARTED`, dan bagaimana mitigasinya?
12. **Skenario 2**: Dua unit server app berada di zona waktu (NTP) yang terdesinkronisasi sebesar 3 detik. Server A memperoleh lock Redis, namun jam sistemnya melompat ke depan secara tiba-tiba karena NTP sync step. Apa dampaknya terhadap validitas lease distributed lock, dan mekanisme apa yang dapat mengatasinya (*Fencing token / Monotonic Clock*)?
13. **Skenario 3**: Sebuah platform e-commerce menerapkan retention time record idempotency selama 24 jam. Pada hari ke-2, seorang pengguna secara manual menekan tombol "Bayar Ulang" pada invoice yang sama yang menggunakan key dari hari sebelumnya. Apa yang terjadi pada sistem backend dan bagaimana arsitektur database harus dirancang untuk mencegah mutasi ganda yang melampaui batas retention window idempotency?

---

### Kunci Jawaban Evaluasi

#### Basic
1.  **B** — Operasi POST dirancang untuk mutasi subordinat yang menciptakan state baru setiap kali dipanggil, kecuali diproteksi oleh mekanisme kontraktual seperti idempotency key.
2.  **C** — Klien bertanggung jawab menggenerate key unik (biasanya UUID v4) untuk mengidentifikasi unit eksekusi request-nya secara spesifik.
3.  **C** — Membuang inkonsistensi formatting (whitespace, indentasi) sehingga payload dengan semantik yang sama menghasilkan hash byte yang identik.
4.  **C** — HTTP 409 Conflict mengindikasikan bahwa request serupa sedang dalam proses aktif eksekusi dan belum selesai.
5.  **B** — Argument NX (Not Exists) dan PX (Expiration milliseconds) menjamin akuisisi mutasi bersifat atomik di thread Redis.

#### Intermediate
6.  **B** — Jika worker 1 mengalami lag melampaui TTL, lock akan expired dan diakuisisi worker 2. Jika worker 1 tiba-tiba hidup kembali dan memanggil `DEL`, ia akan secara tidak sengaja menghapus lock milik worker 2.
7.  **B** — Idempotency key terikat kuat dengan representasi payload yang dikirim pertama kali. Modifikasi data dengan key yang sama adalah pelanggaran kontrak transaksi.
8.  **C** — Menyimpan status resolved harus berada dalam satu kesatuan unit atomik dengan mutasi domain untuk menghindari *phantom side-effects*.
9.  **B** — Eventual consistency pada replica memungkinkan transaksi yang baru ditulis di master belum terbaca di replica (*stale read*), sehingga server mengira key belum pernah diproses.
10. **B** — Transient system error tidak boleh di-cache permanen karena akan memblokir recovery client saat sistem backend sudah sehat kembali.

#### Analisis Skenario Produksi
11. **Solusi**: Tanpa *expired-recovery*, key akan tersangkut (*stuck*) di status `STARTED` selamanya, memicu false `409 Conflict` terus-menerus. Mitigasi: Tambahkan field `lease_expires_at` pada record database. Jika record berstatus `STARTED` tetapi `lease_expires_at < NOW()`, transaksi dianggap ditinggalkan (*orphaned*). Sistem diizinkan mengambil alih proses (*takeover*) atau membatalkan record lama dan memproses ulang payload.
12. **Solusi**: Jam dinding (Wall-clock) rentan terhadap NTP adjustments yang memicu pemendekan/pemanjangan TTL secara liar. Mitigasinya adalah menggunakan *Monotonic Clock* (`CLOCK_MONOTONIC`) untuk kalkulasi durasi lease internal, serta mengimplementasikan PostgreSQL sequence number sebagai *Fencing Token*. Database menolak penulisan jika fencing token yang dibawa request lebih rendah daripada fencing token transaksi terakhir yang berhasil di-commit.
13. **Solusi**: Jika record idempotency telah terhapus oleh policy TTL 24 jam, perlindungan layer idempotency cache akan tembus (*cache-miss*). Pertahanan lini terakhir wajib berada di **Core Domain Model**, yaitu *Database Unique Constraint* pada level entity bisnis (misal: `UNIQUE(order_id, payment_phase)`). Lapisan domain akan menolak transaksi dengan `Error: Invoice already settled`, terlepas dari ada atau tidaknya catatan di tabel idempotency.

---

### 16. Summary

Idempotensi pada mutasi terdistribusi adalah fondasi utama integritas data modern. Ia mengubah sifat jaringan yang *unreliable* menjadi eksekusi mutasi yang deterministik.

Kunci keberhasilan implementasi produksi:
1.  **Jangan Bergantung pada Satu Komponen**: Redis mengamankan konkurensi (throughput/locking); RDBMS menjamin konsistensi jangka panjang (ACID/Audit).
2.  **Validasi Integritas Payload**: `Idempotency-Key` tanpa *Payload Fingerprint Hashing* adalah celah keamanan dan integritas fatal.
3.  **Kelola Siklus Hidup Transaksi Secara Eksplisit**: Terapkan state machine (`STARTED`, `RESOLVED`, `FAILED`) dan pisahkan kegagalan jaringan sementara dari kegagalan domain permanen.
4.  **Pertahanan Berlapis (*Defense-in-depth*)**: Layer idempotency API adalah penjaga pintu gerbang, namun database constraints pada core data model adalah benteng absolut dari double-mutation.