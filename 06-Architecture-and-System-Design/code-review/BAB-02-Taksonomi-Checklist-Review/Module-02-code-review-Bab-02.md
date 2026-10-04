# BAB 02: Taksonomi Checklist Review
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonstruksi dan mengoperasionalkan **Multidimensional Code Review Taxonomy** yang mencakup aspek *Correctness*, *Security*, *Concurrency*, *Performance/Scalability*, *Backward Compatibility*, dan *Operability/Observability*.
- Merancang arsitektur gatekeeping otomatis yang mengintegrasikan *Policy-as-Code* (Open Policy Agent / Conftest) ke dalam siklus *pull request* (PR) sebelum tahap peer review manusia.
- Mengidentifikasi defek arsitektur tingkat lanjut (*race conditions*, *deadlock patterns*, kebocoran goroutine/memory, *cascading failures*, dan pemecahan kompatibilitas skema database/gRPC) menggunakan teknik *semantic and structural code review*.
- Menerapkan metodologi *Risk-Based Review Tiering* untuk membedakan kedalaman inspeksi berdasarkan *impact radius* dan *criticality score* dari perubahan kode.

---

### 2. Prerequisite
- Pemahaman mendalam tentang *distributed system fundamentals* (CAP theorem, isolation levels transaksi database, konsistensi data).
- Pengalaman minimal 2 tahun dalam membaca dan menulis kode dalam bahasa backend modern (*Go*, *Rust*, *Java*, atau *TypeScript/Node.js*).
- Pemahaman tentang CI/CD pipelines, Git workflows (*trunk-based development* vs *GitFlow*), dan implementasi SAST/Linter dasar.
- Pengetahuan operasional mengenai protokol komunikasi (gRPC/Protobuf, HTTP/REST) dan sistem penyimpanan (SQL RDBMS, Distributed Cache/Redis).

---

### 3. Concept & Internal Architecture (Mendalam)

Proses code review tingkat enterprise tidak dapat mengandalkan intuisi subjektif perekayasa perangkat lunak (*cognitive ad-hoc inspection*). Diperlukan arsitektur taksonomi yang terstruktur secara ortogonal untuk meminimalkan *cognitive load* reviewer dan mencegah *defect leakage* ke lingkungan *staging* dan *production*.

```
+-------------------------------------------------------------------------------+
|                       PR Submission & Orchestration                           |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| Layer 1: Automated Gate (Static Analysis & Policy Enforcement)                |
| - Linter (golangci-lint, ESLint) | SAST (Semgrep, SonarQube)                  |
| - Dependency Audit (Trivy)        | Policy-as-Code (OPA / Conftest)            |
| - API Diff (buf breaking, oasdiff)| Contract Testing (Pact)                   |
+-------------------------------------------------------------------------------+
                                      |
                                  [Passed?]
                                 /         \
                              [No]         [Yes]
                              /               \
            (Fast-Fail: Reject PR)             v
+-------------------------------------------------------------------------------+
| Layer 2: Tiered Risk Classification & Routing Engine                          |
| - Calculate Blast Radius (Lines of Code, Files touched, Core Domain Impact)   |
| - Assign Review Tier: Tier 1 (Low), Tier 2 (Standard), Tier 3 (Critical)       |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| Layer 3: Human Cognitive Review (Orthogonal Checklist Execution)             |
|                                                                               |
|  [Dimension A] Core Correctness & Business Logic Invariants                   |
|  [Dimension B] Concurrency, Distributed State, & Thread Safety                |
|  [Dimension C] Security, Authentication, & Zero-Trust Verification            |
|  [Dimension D] Latency, N+1 Query Patterns, & Algorithmic Complexity          |
|  [Dimension E] Backward/Forward Wire & Schema Compatibility                  |
|  [Dimension F] Observability, Metrics (RED/USE), Trace Propagation, & Logs    |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| Merge Approval & Immutable Audit Trail Generation                             |
+-------------------------------------------------------------------------------+
```

#### Taksonomi Checklist Ortogonal Tingkat Enterprise
1. **Domain Correctness & State Transitions**: Memvalidasi *pre-conditions*, *post-conditions*, *invariants*, dan *state machine transitions*. Reviewer memastikan bahwa *edge-cases* batas batas nilai (0, -1, MaxInt, null pointer, string truncation) ditangani dengan benar.
2. **Concurrency & Thread Safety**: Analisis model memori, cakupan *mutex lock/unlock*, siklus *deadlock*, penggunaan atomik, *goroutine leaks*, serta penanganan *cancellation signal* melalui *context propagation*.
3. **Storage & Data Access Boundaries**: Evaluasi interaksi basis data meliputi analisis *index hit*, *transaction isolation anomalies* (*dirty reads*, *non-repeatable reads*, *phantom reads*, *write skew*), pola query *N+1*, dan *connection pool starvation*.
4. **Resiliency & Distributed Failure Handling**: Verifikasi keberadaan pola *fail-fast*, *timeout handling*, penanganan *retry storms* via *exponential backoff with full jitter*, *circuit breaking*, serta *bulkheading*.
5. **Contract & Wire Compatibility**: Proteksi terhadap *breaking changes* pada field Protobuf/JSON, *zero-downtime database migration* (*Expand and Contract pattern*), dan isolasi dependensi eksternal.
6. **Telemetry & Operability**: Verifikasi metrik operasional (*Rate, Errors, Duration*), penyuntikan *distributed context traces* (OpenTelemetry traceparent), serta struktur log terstruktur (*JSON-formatted*) tanpa *Personally Identifiable Information* (PII).

---

### 4. Why & What

| Dimensi | Pendekatan Ad-Hoc / Konvensional | Pendekatan Enterprise Taxonomy-Driven |
| :--- | :--- | :--- |
| **Why (Tujuan)** | Menemukan bug visual, memvalidasi sintaksis, dan memperdebatkan gaya format kode. | Menjamin stabilitas sistem, performa terukur, keamanan data, *zero-downtime deployment*, dan transfer domain knowledge secara sistematis. |
| **What (Objek Review)**| *Formatting*, *typo*, *indentation*, preferensi idiom personal reviewer. | *Architectural invariants*, *race conditions*, *leakage of abstraction*, *data race vector*, *wire-level breaking changes*. |
| **How (Metodologi)** | Reviewer membaca *diff* secara acak dari atas ke bawah tanpa struktur mental. | Eksekusi checklist bergradasi berdasarkan kategori risiko (*Tiered Review Matrix*) didahului oleh *automated policy gating*. |
| **Throughput & SLA** | PR menumpuk, proses review menjadi *bottleneck* (*days to weeks*). | *Time-to-merge* prediktif (< 4 jam untuk Tier 1, < 24 jam untuk Tier 3) dengan *rejection rate* rendah di fase manual. |

---

### 5. How (Workflow detail)

Implementasi taksonomi checklist ke dalam *production engineering cycle* dijalankan melalui 5 fase terukur:

```
[Phase 1: Automated Gating]
         |
         v
[Phase 2: Risk Scoring & Tier Assignment]
         |
         v
[Phase 3: Structural Context Discovery]
         |
         v
[Phase 4: Deep Taxonomic Inspection]
         |
         v
[Phase 5: Consensus, Actionable Feedback & Resolution]
```

#### Langkah 1: Automated Gating Enforcement
Sebelum PR dialokasikan ke engineer:
- CI Pipeline mengeksekusi *linter* dan *code style formatters*.
- SAST Tool (misal: Semgrep, Gosec) memeriksa kerentanan umum (SQLi, CWE-22, Hardcoded Secrets).
- Schema/API Checker (misal: `buf breaking --against`) memvalidasi kompatibilitas Protobuf.
- Skrip *Policy-as-Code* memvalidasi ketersediaan tiket referensi (misal: Jira/Linear ID) dan batasan ukuran *diff* (< 400 lines of code).

#### Langkah 2: Risk Scoring & Tier Assignment
Sistem secara otomatis mengevaluasi risiko PR:
- **Tier 1 (Low Risk)**: Perubahan murni dokumentasi, penambahan konfigurasi non-kritis, perubahan asset statis. Memerlukan: 1 reviewer umum.
- **Tier 2 (Medium Risk)**: Perubahan logika bisnis standar, implementasi endpoint baru tanpa perubahan skema database kompleks. Memerlukan: 1 domain peer reviewer.
- **Tier 3 (High Risk / Critical)**: Perubahan core billing/payment engine, migrasi skema database, modifikasi modul concurrency/caching, perubahan kontrak API publik. Memerlukan: 2 senior/staff reviewers + 1 Security/DBA champion.

#### Langkah 3: Structural Context Discovery
Reviewer mengabaikan rincian implementasi baris per baris pada awalnya:
- Pahami deskripsi dan problem statement dari RFC/Issue tiket terkait.
- Periksa diagram sequence atau spesifikasi API baru.
- Identifikasi *entry points* (misal: HTTP/gRPC handlers atau Kafka consumer listeners).

#### Langkah 4: Deep Taxonomic Inspection
Reviewer mengeksekusi checklist spesifik secara berurutan:
- **Checkpoint 1 (Concurrency/State)**: Apakah ada data yang dibagikan antar thread/goroutine tanpa sinkronisasi eksplisit? Apakah lifetime objek terisolasi?
- **Checkpoint 2 (Resource Lifecycle)**: Apakah context propagation terpasang ke seluruh I/O calls? Apakah koneksi database, file descriptors, dan HTTP response bodies di-close dalam blok `defer`?
- **Checkpoint 3 (Database & I/O)**: Apakah query dieksekusi di dalam loop? Apakah indeks database tersedia untuk klausa WHERE/JOIN? Apakah migrasi skema backward-compatible?
- **Checkpoint 4 (Observability & Failures)**: Apakah ada logging data sensitif (PII/kredensial)? Apakah ada metrik error increment saat blok penanganan error terpanggil?

#### Langkah 5: Consensus, Actionable Feedback & Resolution
- Reviewer memformulasikan komentar menggunakan konvensi terstandarisasi (misal: *Conventional Comments*):
  - `nitpick:` Saran non-blocking terkait estetika/idiom minor.
  - `question:` Klarifikasi tanpa memblokir merge.
  - `issue (blocking):` Pelanggaran arsitektur, bug fungsional, atau kerentanan performa/keamanan yang wajib diperbaiki sebelum merge.
- Seluruh thread diskusi wajib di-resolve oleh peninjau (bukan pembuat PR) setelah verifikasi commit perbaikan.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Inspeksi Pesawat Komersial Sebelum Penerbangan (*Pre-Flight Checklist*)
Mengandalkan review kode ad-hoc sama seperti seorang kapten pilot yang memeriksa kelayakan pesawat hanya dengan "melihat-lihat secara umum keliling badan pesawat". Pilot profesional menggunakan checklist terstruktur ortogonal: *Instrument Systems*, *Hydraulics & Flight Controls*, *Avionics*, dan *Fuel Reserves*. Jika satu instrumen navigasi cadangan tidak lolos uji checklist, pesawat *dilarang lepas landas* (Blocked). 

Demikian pula, taksonomi review memastikan sistem backend berdaya tahan tinggi tidak mengalami *crash* di produksi akibat kelalaian pada dimensi yang luput dari pandangan sekilas.

#### Diagram Interaksi PR Review Pipeline & Blast Radius Mapping

```
+---------------------------------------------------------------------------------+
| PR Blast Radius Matrix                                                          |
+---------------------------------------------------------------------------------+
| Metric             | Tier 1 (Low)     | Tier 2 (Standard)  | Tier 3 (Critical)  |
|--------------------+------------------+--------------------+--------------------|
| LOC Diff           | < 50 LOC         | 50 - 350 LOC       | > 350 LOC          |
| Blast Area         | Docs, UI Styles  | Internal Service   | Auth, Engine, DB   |
| DB Migration       | None             | Add column (NULL)  | Lock-prone alter   |
| API Contract       | Internal Private | Backward Compatible| Breaking Wire / V2 |
| Human Reviewers    | 1 Peer           | 1 Senior Engineer  | 2 Staff + Sec/DBA  |
+---------------------------------------------------------------------------------+

                      +--------------------------+
                      |   Author Submits PR      |
                      +--------------------------+
                                   |
                                   v
             +---------------------------------------------+
             | Automated Static & Policy Checks (Conftest) |
             +---------------------------------------------+
                                   |
                     +-------------+-------------+
                     |                           |
                 [Passed]                    [Failed]
                     |                           |
                     v                           v
      +-----------------------------+   +-------------------+
      | Blast Radius Classification |   | PR Blocked: Fix   |
      +-----------------------------+   | Policy Violations |
                     |                  +-------------------+
                     v
      +-----------------------------------------------------+
      | Reviewer Checklist Execution:                       |
      |                                                     |
      |   [ ] Concurrency: Check Race, Channels, Deadlocks  |
      |   [ ] Database: Check Indexing, N+1, Write-Skews    |
      |   [ ] Wire: Check Protobuf Wire Compatibility       |
      |   [ ] Resiliency: Context Timeouts, Retries         |
      |   [ ] Observability: Distributed Tracing & RED      |
      +-----------------------------------------------------+
                     |
                     v
         [Checklist Items Cleared?]
           /                     \
        [No]                     [Yes]
         /                         \
        v                           v
+------------------+     +-----------------------------+
| Blocking Comment |     | Approved: Ready for Staging |
| Cycle (Fix-Loop) |     +-----------------------------+
+------------------+
```

---

### 7. Simple Example & Practical Example (Kode Standar Industri)

Berikut adalah komparasi kode backend Go yang mengilustrasikan penerapan Checklist Taksonomi pada endpoint pemrosesan order perbankan/fintech.

#### ❌ Kode Buruk (Gagal Taksonomi Checklist)
*Defek: Unsafe concurrency, SQL N+1 Query, hilangnya Context propagation, hilangnya log terstruktur/tracing, dan ketiadaan Transaction Isolation management.*

```go
package orders

import (
	"database/sql"
	"encoding/json"
	"net/http"
)

var DB *sql.DB // Global state, tidak terisolasi

type OrderRequest struct {
	UserID  string   `json:"user_id"`
	ItemIDs []string `json:"item_ids"`
	Amount  float64  `json:"amount"`
}

// Handler rentan: Memory leak, race condition, no timeout, N+1 database queries
func HandleProcessOrder(w http.ResponseWriter, r *http.Request) {
	var req OrderRequest
	_ = json.NewDecoder(r.Body).Decode(&req) // Tidak validasi error parsing atau payload limit

	// BUG: Tidak ada context propagation, jika client putus, query tetap berjalan
	var balance float64
	row := DB.QueryRow("SELECT balance FROM accounts WHERE user_id = '" + req.UserID + "'") // BUG: SQL Injection
	_ = row.Scan(&balance)

	if balance < req.Amount {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte("insufficient balance"))
		return
	}

	// BUG: Concurrency Race Condition. Balance divalidasi dan diupdate di luar transaksi terisolasi
	_, _ = DB.Exec("UPDATE accounts SET balance = balance - $1 WHERE user_id = $2", req.Amount, req.UserID)

	// BUG: N+1 Query pattern - melakukan I/O dalam loop tanpa bulk insert atau batching
	for _, itemID := range req.ItemIDs {
		_, _ = DB.Exec("INSERT INTO order_items (user_id, item_id) VALUES ($1, $2)", req.UserID, itemID)
	}

	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"success"}`))
}
```

####  Kode Baik (Lolos Taksonomi Checklist Arsitektur Produksi)
*Penerapan: Context cancellation, strict payload limits, atomic transaction dengan Row-Level Locking (`SELECT FOR UPDATE`), Batch I/O, error handling komprehensif, dan OpenTelemetry structured observability.*

```go
package orders

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/google/uuid"
	"github.com/lib/pq"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
	"go.uber.org/zap"
)

var (
	ErrInsufficientFunds = errors.New("insufficient funds")
	ErrAccountNotFound   = errors.New("account not found")
	ErrPayloadTooLarge   = errors.New("payload limit exceeded")
)

const (
	MaxPayloadBytes = 1 << 20 // 1 MB payload protection
	DBTimeout       = 5 * time.Second
)

type OrderRequest struct {
	UserID  uuid.UUID   `json:"user_id"`
	ItemIDs []uuid.UUID `json:"item_ids"`
	Amount  int64       `json:"amount_cents"` // Menggunakan integer untuk moneter, mencegah float precision issue
}

func (r *OrderRequest) Validate() error {
	if r.UserID == uuid.Nil {
		return errors.New("user_id is required")
	}
	if len(r.ItemIDs) == 0 {
		return errors.New("item_ids cannot be empty")
	}
	if len(r.ItemIDs) > 500 {
		return errors.New("item_ids exceeds maximum batch limit (500)")
	}
	if r.Amount <= 0 {
		return errors.New("amount must be positive")
	}
	return nil
}

type OrderHandler struct {
	db     *sql.DB
	logger *zap.Logger
	tracer trace.Tracer
}

func NewOrderHandler(db *sql.DB, logger *zap.Logger) *OrderHandler {
	return &OrderHandler{
		db:     db,
		logger: logger,
		tracer: otel.Tracer("orders-handler"),
	}
}

func (h *OrderHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	ctx, span := h.tracer.Start(r.Context(), "HandleProcessOrder")
	defer span.End()

	w.Header().Set("Content-Type", "application/json")

	// Checklist: Security - Limit request size to prevent DoS via memory starvation
	r.Body = http.MaxBytesReader(w, r.Body, MaxPayloadBytes)
	
	var req OrderRequest
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields() // Checklist: Contract enforcement

	if err := decoder.Decode(&req); err != nil {
		h.respondError(w, http.StatusBadRequest, "Invalid request payload format", err)
		return
	}

	if err := req.Validate(); err != nil {
		h.respondError(w, http.StatusUnprocessableEntity, err.Error(), err)
		return
	}

	span.SetAttributes(
		attribute.String("user.id", req.UserID.String()),
		attribute.Int("items.count", len(req.ItemIDs)),
		attribute.Int64("order.amount", req.Amount),
	)

	// Checklist: Concurrency, Storage & Isolation - Execute in isolated transaction
	if err := h.executeOrderTransaction(ctx, req); err != nil {
		switch {
		case errors.Is(err, ErrInsufficientFunds):
			h.respondError(w, http.StatusPaymentRequired, "Insufficient funds", err)
		case errors.Is(err, ErrAccountNotFound):
			h.respondError(w, http.StatusNotFound, "Account record not found", err)
		case errors.Is(err, context.DeadlineExceeded), errors.Is(err, context.Canceled):
			h.respondError(w, http.StatusGatewayTimeout, "Request execution timed out", err)
		default:
			h.logger.Error("Database transaction failure", zap.Error(err), zap.String("trace_id", span.SpanContext().TraceID().String()))
			h.respondError(w, http.StatusInternalServerError, "Internal system processing failure", err)
		}
		return
	}

	w.WriteHeader(http.StatusCreated)
	_, _ = w.Write([]byte(`{"status":"created"}`))
}

func (h *OrderHandler) executeOrderTransaction(ctx context.Context, req OrderRequest) error {
	// Checklist: Timeout & Resource Management - Enforce explicit database timeout
	txCtx, cancel := context.WithTimeout(ctx, DBTimeout)
	defer cancel()

	tx, err := h.db.BeginTx(txCtx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return fmt.Errorf("failed to initialize transaction: %w", err)
	}
	defer func() {
		// Checklist: Resilience - Safe rollback pattern
		_ = tx.Rollback()
	}()

	// Checklist: Concurrency Isolation - Row lock prevents race condition / balance double spend
	var currentBalance int64
	queryAccount := `SELECT balance_cents FROM accounts WHERE user_id = $1 FOR UPDATE`
	err = tx.QueryRowContext(txCtx, queryAccount, req.UserID).Scan(&currentBalance)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return ErrAccountNotFound
		}
		return fmt.Errorf("account query failed: %w", err)
	}

	if currentBalance < req.Amount {
		return ErrInsufficientFunds
	}

	// Update balance
	queryDeduct := `UPDATE accounts SET balance_cents = balance_cents - $1, updated_at = NOW() WHERE user_id = $2`
	if _, err := tx.ExecContext(txCtx, queryDeduct, req.Amount, req.UserID); err != nil {
		return fmt.Errorf("balance deduction failed: %w", err)
	}

	// Checklist: Database Optimization - Use batch/array insertion instead of N+1 loop execution
	queryBatchInsert := `
		INSERT INTO order_items (user_id, item_id, created_at)
		SELECT $1, unnest($2::uuid[]), NOW()`
	
	if _, err := tx.ExecContext(txCtx, queryBatchInsert, req.UserID, pq.Array(req.ItemIDs)); err != nil {
		return fmt.Errorf("bulk item insertion failed: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("transaction commit failed: %w", err)
	}

	return nil
}

func (h *OrderHandler) respondError(w http.ResponseWriter, code int, msg string, internalErr error) {
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(map[string]string{
		"error":   msg,
		"code_id": http.StatusText(code),
	})
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Race Condition Deadlock & Data Inconsistency pada Payment Gateway Skala Global
- **Latar Belakang**: Sebuah platform e-commerce enterprise dengan 35 juta Daily Active Users (DAU) merilis fitur flash-sale. Tim backend melakukan refactoring pada settlement worker yang mengonsumsi antrean Kafka untuk memotong saldo wallet dan mencatat ledger transaksi secara paralel.
- **Defek yang Luput**:
  1. Pengurutan penguncian (*Lock Ordering*) pada level database tidak deterministik: Thread A mengunci `Account A` lalu `Account B`, sedangkan Thread B mengunci `Account B` lalu `Account A`.
  2. PR lolos review karena reviewer hanya fokus pada aspek kebersihan kode (*clean architecture*, interface separation) tanpa mengeksekusi checklist taksonomi *Concurrency & Deadlock Safety*.
- **Dampak di Produksi**:
  - Saat event flash sale berlangsung, database engine PostgreSQL mengalami lonjakan *Active Session* hingga mencapai limit `max_connections` (5.000 koneksi) dalam waktu 4 menit.
  - Terjadi peningkatan tajam pada *Deadlock Detections* (>450 per detik).
  - Terjadi *cascading failure* yang merobohkan pool koneksi untuk service pembayaran, menyebabkan total outage checkout selama 42 menit dengan estimasi kerugian $1.2 juta.
- **RCA (Root Cause Analysis)**:
  - PR memiliki 850 lines of code dan direview dalam tempo 8 menit oleh 1 orang engineer (kelelahan kognitif / *rubber-stamping*).
  - Tidak ada automated check untuk lock-order pattern.
  - Reviewer tidak memvalidasi query `SELECT ... FOR UPDATE` multi-resource tanpa klausul deterministik (`ORDER BY resource_id ASC`).
- **Remediasi & Penerapan Taksonomi Baru**:
  1. **Enforcement Lock-Order Taxonomy**: Setiap transaksi yang melibatkan lebih dari satu baris entitas *wajib* melakukan sorting ID sebelum eksekusi penguncian.
  2. **Automated Static Guard**: Penambahan linter kustom yang menandai setiap query `FOR UPDATE` jika tidak memiliki klausa `ORDER BY`.
  3. **Strict Blast-Radius Review Policy**: Setiap perubahan yang menyentuh direktori `services/billing/**` secara otomatis diklasifikasikan sebagai **Tier 3**, mewajibkan minimal 2 Staff Engineer dan 1 Database Reliability Engineer (DBRE) dengan checklist wajib verifikasi isolasi transaksi.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

Penerapan checklist taksonomi review yang ketat melibatkan kompromi teknis dan operasional yang harus diseimbangkan oleh arsitek sistem:

| Parameter | Pendekatan Longgar / Minimalis | Pendekatan Taksonomi Ketat (Tier 3 Gate) | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Engineering Latency (PR Lead Time)** | Rendah (PR merge dalam hitungan jam). | Meningkat (PR Tier 3 dapat memakan waktu 24 - 48 jam hingga lolos checklist). | Mengorbankan kecepatan rilis jangka pendek demi proteksi *mean time between failures* (MTBF) dan pencegahan insiden Sev-1 di produksi. |
| **Runtime Performance & System Latency** | Tidak terprediksi. Rentan degradasi akibat N+1 queries dan unindexed joins. | Optimal. Operasi I/O dibatasi, bulk-loaded, dan di-profile sebelum rilis. | Pengorbanan waktu saat review menghemat ratusan jam profiling darurat dan optimasi query reaktif di database produksi. |
| **Infrastructure Cost** | Tinggi. Resource compute/database harus di-overprovision untuk meredam inefisiensi. | Efisien. Query terkontrol, connection footprint rendah, alokasi memori terpantau. | Mengurangi Tagihan Cloud Infrastruktur secara signifikan; resource sizing dapat dihitung secara deterministik. |
| **Developer Cognitive Load** | Rendah di awal, sangat tinggi saat *on-call* menghadapi kegagalan sistem. | Tinggi di awal selama siklus authoring & review kode. | Memindahkan beban kognitif dari *crisis mitigation* (on-call jam 3 pagi) ke lingkungan kolaborasi terencana di jam kerja. |

---

### 10. Common Mistakes & Troubleshooting

Berikut adalah defek kritis yang sering lolos dari pengawasan reviewer beserta cara mendeteksi dan memperbaikinya:

#### 1. Mutex Copying / Slice Re-allocation Race
- **Gejala**: Program mengalami *panic* secara intermiten dengan log `fatal error: concurrent map read and map write` atau race detector flagging.
- **Penyebab**: Struct yang menampung `sync.Mutex` dioper secara value (bukan pointer), sehingga mutex terduplikasi dan state sinkronisasinya putus.
- **Deteksi Review**:
  ```go
  // SALAH: Receiver berbasis value meng-copy internal state mutex
  func (s ServiceState) Update(key string, val int) {
      s.mu.Lock()
      defer s.mu.Unlock()
      s.data[key] = val
  }
  
  // BENAR: Gunakan pointer receiver
  func (s *ServiceState) Update(key string, val int) { ... }
  ```

#### 2. Protobuf / Wire Contract Breaking Changes
- **Gejala**: Klien lama mengalami crash saat melakukan decoding payload pasca-deployment service baru.
- **Penyebab**: Perubahan nomor field (`tag number`) pada file `.proto`, atau penggantian tipe field dari `string` menjadi `int32`.
- **Deteksi Review**: Periksa diff `.proto`. Tag number bersifat *immutable* sekali dirilis ke production. Pasang `buf breaking` pada CI pipeline untuk memblokir PR sebelum fase peer review.

#### 3. Database Migration Table-Locking Vector
- **Gejala**: Deployment pipeline hang di tahap database migration; aplikasi mengalami timeout massal.
- **Penyebab**: Menambahkan kolom dengan `DEFAULT` value tanpa constraint `NOT NULL` pada versi database lawas, atau mengeksekusi `ALTER TABLE ... ADD CONSTRAINT` tanpa klausa `NOT VALID` (Postgres).
- **Deteksi Review**: Checklist database harus memverifikasi bahwa penambahan index dilakukan secara concurrent:
  ```sql
  -- SALAH: Mengunci seluruh tabel dari operasi read/write
  CREATE INDEX idx_orders_user_id ON orders(user_id);

  -- BENAR: Mengizinkan proses DML tetap berjalan
  CREATE INDEX CONCURRENTLY idx_orders_user_id ON orders(user_id);
  ```

---

### 11. Best Practices (Production Checklist)

Gunakan checklist multidimensional ini sebagai template standar evaluasi Pull Request tingkat arsitektur enterprise:

#### 1. Correctness & Business Invariants
- [ ] Apakah setiap kondisi batas (boundary edge-cases: array kosong, ID null, batas maksimum) ditangani secara eksplisit?
- [ ] Apakah tipe data untuk nilai finansial menggunakan representasi tepat (fixed-point integer / cents) dan bukan floating-point IEEE-754?
- [ ] Apakah error propagation mempertahankan root-cause via error wrapping (`fmt.Errorf("...: %w", err)`)?

#### 2. Concurrency & Asynchronous State
- [ ] Apakah pointer receiver digunakan secara konsisten pada tipe struct yang memiliki mutex?
- [ ] Apakah channel memiliki buffer limit yang terukur untuk menghindari deadlock producer-consumer?
- [ ] Apakah goroutine/thread baru dijamin lifecycle termination-nya (tidak ada background goroutine tanpa termination signal)?

#### 3. Storage, Queries, & Caching
- [ ] Apakah tidak ada query database yang berjalan di dalam loop (*N+1 pattern detection*)?
- [ ] Apakah query `SELECT ... FOR UPDATE` memiliki klausa deterministik `ORDER BY` untuk mencegah deadlock?
- [ ] Apakah setiap key yang ditulis ke Redis/Memcached memiliki Time-To-Live (TTL) eksplisit?
- [ ] Apakah migrasi database menerapkan strategi *Expand and Contract* (backward-compatible)?

#### 4. Resiliency & Timeouts
- [ ] Apakah seluruh external outbound network calls (HTTP, RPC, DB) dilindungi oleh explicit timeout berbasis `context.Context`?
- [ ] Apakah mekanisme retry menerapkan *exponential backoff* dan *full jitter* untuk mencegah *thundering herd problem*?

#### 5. Security & Isolation
- [ ] Apakah query terbebas dari string concatenation/interpolation (menjamin SQL injection protection)?
- [ ] Apakah log payload memfilter data sensitif (*PII, Access Tokens, Credit Card PAN*)?
- [ ] Apakah payload input dibatasi ukurannya sebelum parsing memori via `http.MaxBytesReader`?

#### 6. Observability
- [ ] Apakah distributed trace context (`traceparent`) diteruskan ke outbound network calls?
- [ ] Apakah setiap blok failure path mencatat log pada level `WARN` atau `ERROR` dengan metadata terstruktur (bukan flat string)?
- [ ] Apakah metrik kustom (Prometheus/OpenTelemetry) di-increment saat state transisi utama terjadi?

---

### 12. Hands-on Practice

Buat dan operasionalkan Policy-as-Code gatekeeper menggunakan **Open Policy Agent (OPA)** dan **Conftest** untuk mengevaluasi checklist arsitektur secara otomatis pada file konfigurasi/PR metadata.

#### Struktur Direktori Praktikum
```
hands-on/m02/
├── policy/
│   └── pull_request.rego
├── fixtures/
│   ├── pr_bad.json
│   └── pr_good.json
└── run_test.sh
```

#### Langkah 1: Tulis Policy OPA (`policy/pull_request.rego`)
Simpan policy berikut untuk mendeteksi pelanggaran checklist: ukuran PR melebihi batas tanpa label bypass, atau perubahan skema tanpa review DBA.

```rego
package architecture.governance

default allow = false

# Aturan 1: PR tidak boleh melebihi 400 LOC kecuali memiliki label 'large-pr-approved'
violations[msg] {
    input.lines_changed > 400
    not has_bypass_label(input.labels, "large-pr-approved")
    msg := sprintf("PR Blast Radius Failure: Perubahan %v LOC melebihi batas 400 lines tanpa label approval khusus.", [input.lines_changed])
}

# Aturan 2: Perubahan pada direktori skema database mewajibkan review dari DBRE / Data Architect
violations[msg] {
    touches_database_schema(input.modified_files)
    not has_dbre_approval(input.approvers)
    msg := "Database Invariant Violation: Migrasi skema database terdeteksi namun belum disetujui oleh tim DBRE."
}

allow {
    count(violations) == 0
}

touches_database_schema(files) {
    some i
    startswith(files[i], "migrations/")
}

has_bypass_label(labels, target) {
    some i
    labels[i] == target
}

has_dbre_approval(approvers) {
    some i
    approvers[i] == "alice-dbre"
}
```

#### Langkah 2: Buat Test Fixtures
File `fixtures/pr_bad.json`:
```json
{
  "id": 1042,
  "lines_changed": 550,
  "labels": ["feature"],
  "modified_files": [
    "migrations/20260330_add_user_index.sql",
    "services/billing/handler.go"
  ],
  "approvers": ["bob-junior-dev"]
}
```

File `fixtures/pr_good.json`:
```json
{
  "id": 1043,
  "lines_changed": 150,
  "labels": ["feature"],
  "modified_files": [
    "migrations/20260330_add_user_index.sql",
    "services/billing/handler.go"
  ],
  "approvers": ["bob-junior-dev", "alice-dbre"]
}
```

#### Langkah 3: Eksekusi Validasi Policy
Jalankan evaluasi menggunakan Docker atau OPA engine binary:
```bash
#!/usr/bin/env bash
# run_test.sh

echo "Evaluating Bad PR against Architecture Review Governance..."
docker run --rm -v $(pwd):/workspace openpolicyagent/conftest verify \
  --policy /workspace/policy/pull_request.rego \
  --input json /workspace/fixtures/pr_bad.json || true

echo -e "\nEvaluating Good PR against Architecture Review Governance..."
docker run --rm -v $(pwd):/workspace openpolicyagent/conftest verify \
  --policy /workspace/policy/pull_request.rego \
  --input json /workspace/fixtures/pr_good.json
```

---

### 13. Exercise

#### Level Easy
Tinjau potongan kode Go berikut:
```go
func CacheGetUser(id string) (*User, error) {
    mu.Lock()
    user, found := userCache[id]
    mu.Unlock()
    if found {
        return user, nil
    }
    user, err := fetchFromDB(id)
    if err != nil {
        return nil, err
    }
    mu.Lock()
    userCache[id] = user
    mu.Unlock()
    return user, nil
}
```
*Tugas*: Identifikasi celah konkurensi arsitektur (*Cache Stampede / Thundering Herd Problem*) dan refactor menggunakan single-flight pattern.

#### Level Medium
Sebuah PR menambahkan query berikut pada service inventory:
```sql
SELECT i.id, i.stock_count, p.price 
FROM inventory i 
JOIN prices p ON i.product_id = p.id 
WHERE i.warehouse_id = $1 
FOR UPDATE;
```
*Tugas*: Analisis dampak locking dari query di atas terhadap performa tabel `prices` yang bersifat global/read-heavy. Tulis rekomendasi review dan query perbaikannya menggunakan klausul spesifik target table locking (`FOR UPDATE OF ...`).

#### Level Hard
Sebuah PR gRPC API mengubah definisi Protobuf berikut:
```protobuf
// Versi Lama (v1)
message TransactionLog {
  int64 transaction_id = 1;
  string user_id = 2;
  double amount = 3;
}

// Versi Baru (Diusulkan di PR)
message TransactionLog {
  string transaction_id = 1; // Mengubah int64 menjadi string UUID
  string account_id = 2;     // Mengganti nama field user_id
  int64 amount_cents = 3;    // Mengubah tipe amount double menjadi int64
}
```
*Tugas*: Buat dokumen checklist review yang membedah kegagalan backward-compatibility pada wire-format level Protobuf dari PR ini, serta petunjuk tahapan migrasi yang aman tanpa memicu crash deserialisasi pada downstream consumer.

---

### 14. Challenge

**Studi Kasus Sistem Skala Raksasa: "Zero-Downtime Distributed Ledger Refactoring"**

Anda menjabat sebagai Principal Platform Architect pada sebuah unicorn fintech. Tim Core Banking mengajukan PR cross-service yang mengubah algoritma pemrosesan pembayaran:
- PR memodifikasi skema database Postgres utama (tabel `ledgers` berisi 1.2 miliar baris, ukuran tabel 850 GB) dari single-currency balance menjadi multi-currency sub-wallets.
- PR mengubah pola lock single-record menjadi distributed lock multi-resource via Redis Redlock.
- PR memodifikasi kontrak event Kafka yang diproduksi ke 14 downstream microservices.

**Tantangan**:
1. Buat checklist review multidimensional komprehensif yang dirancang spesifik untuk PR ini. Checklist harus mencakup skenario kegagalan:
   - Partial network partition saat fase Redlock acquisition.
   - Replikasi lag antara primary DB dan read-replicas.
   - Kafka schema drift pada konsumen yang belum diperbarui (*canary deployment mismatch*).
2. Tentukan kriteria strictly blocking vs non-blocking pada PR tersebut.
3. Rancang rencana mitigasi rollback jika terjadi lonjakan p99.9 latency sebesar 200ms pasca-merging.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. Apa kelemahan utama dari code review yang hanya mengandalkan intuisi subjektif reviewer tanpa taksonomi terstruktur?
   - A. Menurunkan jumlah pull request yang diajukan developer.
   - B. Terjadinya *cognitive fatigue* dan inkonsistensi pendeteksian defek kritis (seperti bug konkurensi dan security).
   - C. Terlalu banyak unit test yang dibuat oleh pengembang.
   - D. Waktu eksekusi CI/CD pipeline menjadi lebih lambat secara signifikan.
2. Mengapa penambahan field/kolom database dengan constraint `NOT NULL` tanpa nilai default yang tepat dapat memicu kegagalan saat proses zero-downtime deployment?
   - A. Karena aplikasi versi lama akan menolak membaca kolom tersebut.
   - B. Karena database otomatis mematikan engine saat ada kolom baru.
   - C. Karena instance aplikasi lama yang belum di-deploy akan gagal mengeksekusi operasi `INSERT` tanpa menyediakan field tersebut.
   - D. Karena ukuran payload index akan mengecil secara drastis.
3. Manakah indikator yang menandakan suatu PR tergolong dalam *Tier 3 (High-Risk/Critical)*?
   - A. PR hanya mengubah struktur penamaan file dokumentasi markdown.
   - B. PR menyentuh core billing engine, mengisolasi transaksi database, dan memodifikasi schema migration.
   - C. PR melakukan refactoring CSS/SASS pada antarmuka dashboard admin internal.
   - D. PR memperbarui versi library linter statis.
4. Apa tujuan utama integrasi *Policy-as-Code* (seperti OPA/Conftest) dalam tahap automated gating code review?
   - A. Menggantikan seluruh proses peer-review yang dilakukan oleh engineer manusia.
   - B. Mempercepat proses compile binary microservice.
   - C. Memvalidasi ketaatan arsitektur dan batasan risiko secara otomatis sebelum reviewer manusia meluangkan waktu kognitifnya.
   - D. Menghapus kebutuhan penulisan unit test pada kode sumber.
5. Pada review kode Go, apa bahaya meloloskan struct yang memuat `sync.Mutex` dengan receiver fungsi non-pointer (`func (s Struct)`)?
   - A. Program tidak dapat di-compile oleh compiler Go.
   - B. Struct akan mengalami memory leak di heap.
   - C. Mutex akan di-copy secara passing-by-value, merusak state penguncian dan memicu *data race condition*.
   - D. Seluruh goroutine akan otomatis mati seketika.

#### Intermediate (5 Soal)
6. Manakah dari pola query berikut yang mengindikasikan adanya anti-pattern *N+1 Query* pada tahap code review?
   - A. Menjalankan query `SELECT * FROM users WHERE id IN ($1, $2, $3)`.
   - B. Mengiterasi slice ID pengguna di loop aplikasi dan memanggil `db.QueryRow("SELECT ... WHERE id = $1", id)` pada tiap iterasi.
   - C. Menjalankan migrasi database menggunakan klausul `CREATE INDEX CONCURRENTLY`.
   - D. Melakukan agregasi menggunakan fungsi `GROUP BY` dan `HAVING` pada SQL RDBMS.
7. Saat meninjau perubahan schema Protobuf, mengapa penggantian nomor field/tag (`field tag number`) dikategorikan sebagai *breaking change* yang fatal?
   - A. Protobuf tidak membaca nama teks field saat transmisi biner, melainkan mereferensikan field secara eksklusif menggunakan tag number.
   - B. File `.proto` tidak akan bisa dikonversi menjadi file biner `.pb.go`.
   - C. Semua koneksi TLS gRPC akan terputus seketika.
   - D. File Protobuf akan mengalami overflow ukuran buffer memori.
8. Dalam konteks isolasi database, fenomena anomali apakah yang coba dicegah saat reviewer mewajibkan penggunaan `SELECT ... FOR UPDATE` pada transaksi pengecekan dan pengurangan saldo?
   - A. Dirty Reads pada Read Committed level.
   - B. Write Skew / Lost Updates yang disebabkan oleh modifikasi konkuren di luar transaksi yang terisolasi.
   - C. Koneksi database timeout akibat idle connection.
   - D. Kegagalan parser sintaks SQL.
9. Praktik terbaik apa yang harus ditegakkan dalam review checklist terkait penanganan sinyal pembatalan klien (*Client Disconnect*) pada HTTP handlers?
   - A. Mengabaikan context bawaan request (`r.Context()`) dan membuat context baru dengan `context.Background()`.
   - B. Meneruskan context bawaan request ke seluruh query database dan I/O calls downstream agar eksekusi dibatalkan saat client disconnect.
   - C. Menggunakan channel blocking tak berbatas untuk menahan request di memory.
   - D. Mematikan worker server secara berkala.
10. Apa indikasi utama terjadinya goroutine leak yang dapat dideteksi selama code review?
    - A. Goroutine memanggil fungsi `runtime.GC()` secara manual.
    - B. Goroutine membaca channel yang tidak pernah ditutup oleh sender atau memblokir pada channel send tanpa pembaca aktif dan tanpa context timeout.
    - C. Goroutine dibuat di dalam function main program.
    - D. Goroutine menerima parameter berupa pointer struct.

#### Skenario Kasus Produksi (3 Soal)
11. **Skenario Kasus 1**:
    Developer mengajukan PR yang menambahkan cache Redis untuk mengoptimalkan pembacaan data katalog produk:
    ```go
    val, err := redisClient.Get(ctx, productID).Result()
    if err == redis.Nil {
        val = db.FetchProduct(productID)
        redisClient.Set(ctx, productID, val, 0) // TTL = 0 (No Expiry)
    }
    return val
    ```
    Sebagai senior reviewer yang menerapkan Taksonomi Checklist Arsitektur, apa 2 defek produksi terparah yang wajib Anda tandai sebagai **BLOCKING ISSUE**?
    - A. Penggunaan variabel `val` yang terlalu pendek dan ketiadaan komentar function.
    - B. Ketiadaan TTL yang memicu memori Redis tak terbatas (*memory exhaustion*), serta rentan *Cache Stampede* saat cold start jika database lambat.
    - C. Penulisan kode tidak menggunakan library ORM pihak ketiga.
    - D. Fungsi `FetchProduct` tidak menggunakan protokol HTTP/2.

12. **Skenario Kasus 2**:
    Sebuah PR menyertakan migrasi skema database PostgreSQL berikut untuk tabel `audit_events` yang berukuran 400 juta baris:
    ```sql
    ALTER TABLE audit_events ADD COLUMN client_ip VARCHAR(45) NOT NULL;
    ```
    Reviewer menandai PR ini sebagai **DANGEROUS (Blocked)**. Mengapa migrasi ini sangat berbahaya jika dijalankan pada database produksi dengan beban traffic tinggi?
    - A. Tipe data `VARCHAR(45)` tidak didukung oleh arsitektur database modern.
    - B. Operasi penambahan kolom `NOT NULL` tanpa nilai default pada PostgreSQL versi lama akan memicu penulisan ulang seluruh tabel (*full table rewrite*) dan memperoleh *Exclusive Lock* yang memblokir semua operasi pembacaan dan penulisan.
    - C. Kolom baru tersebut secara otomatis menghapus index primary key tabel yang ada.
    - D. Nama kolom `client_ip` melanggar aturan penamaan standar ANSI SQL.

13. **Skenario Kasus 3**:
    Pada PR microservice distributed lock, developer mengimplementasikan skema pelepasan kunci (*lock release*) sebagai berikut:
    ```go
    func (s *LockService) ReleaseLock(ctx context.Context, lockKey string) {
        s.redisClient.Del(ctx, lockKey)
    }
    ```
    Dalam checklist arsitektur konkurensi terdistribusi, apa potensi bencana yang dapat terjadi akibat implementasi ini jika proses eksekusi worker berjalan lambat melampaui masa kedaluwarsa lock?
    - A. Redis server akan kehabisan CPU cycles akibat eksekusi perintah `DEL`.
    - B. Worker A yang mengalami GC pause panjang melepaskan lock milik Worker B yang telah mengambil alih lock tersebut setelah TTL kadaluarsa (*Split Brain / Data Corruption*).
    - C. Request downstream akan otomatis dialihkan ke database RDBMS secara rekursif.
    - D. Mutex internal aplikasi Go akan mengalami state deadlock permanen.

---

### Kunci Jawaban Quiz

#### Basic
1. **B** - Tanpa taksonomi checklist, reviewer rentan terdistraksi oleh hal-hal sepele (*bikeshedding*) dan melewatkan cacat sistem kritis akibat beban kognitif yang tidak terarah.
2. **C** - Instance aplikasi lama yang masih aktif selama proses rolling deployment tidak mengetahui keberadaan kolom mandatory baru tersebut, sehingga query insert-nya akan gagal (*rejection error*).
3. **B** - Perubahan yang memiliki *blast radius* tinggi menyentuh komponen inti finansial, persistensi skema, dan konkurensi diklasifikasikan sebagai Tier 3.
4. **C** - Policy-as-Code bertindak sebagai pre-filter mekanis untuk menolak PR yang tidak memenuhi kriteria tata kelola dasar secara otomatis.
5. **C** - Mutex berisi field internal yang melacak state penguncian; jika dioper sebagai value, copy baru dibuat dan penguncian asli tidak berefek pada goroutine lain.

#### Intermediate
6. **B** - Melakukan query database individual di dalam loop iterasi data adalah karakteristik klasik anti-pattern N+1 yang merusak latensi dan membebani koneksi DB.
7. **A** - Protobuf memetakan field payload biner berdasarkan integer tag-nya. Mengubah nomor tag pada field yang sama akan menyebabkan parsing salah arah pada downstream consumer.
8. **B** - Penguncian baris (`FOR UPDATE`) mencegah *race conditions* saat dua transaksi paralel mencoba membaca saldo yang sama dan saling menimpa sisa pengurangan secara parsial.
9. **B** - Context propagation memastikan bahwa jika client membatalkan request, operasi database/I/O yang sedang berlangsung segera dihentikan demi menghemat kapasitas compute/koneksi.
10. **B** - Goroutine yang diblokir selamanya pada I/O channel tanpa ada jalur exit atau pembatalan context akan terus menduduki memori stack di heap secara permanen.

#### Skenario Kasus Produksi
11. **B** - Mengatur TTL = 0 pada data transaksional dapat mengakibatkan Redis OOM (Out Of Memory crash), serta tanpa mekanisme *single-flight/locking*, ribuan request paralel akan serempak menghantam database jika cache kosong.
12. **B** - Menambahkan kolom `NOT NULL` tanpa default value memaksa engine memvalidasi seluruh baris tabel secara eksklusif, memicu tabel terkunci (*table lock*) penuh yang mengakibatkan seluruh query aplikasi antre dan timeout massal.
13. **B** - Pelepasan lock terdistribusi wajib bersifat aman (misalnya memverifikasi kepemilikan nilai token acak via Lua Script). Perintah `DEL` secara membabi-buta dapat menghapus lock yang baru saja diklaim oleh worker lain setelah worker pertama mengalami jeda/lag melebihi durasi TTL.

---

### 16. Summary

Implementasi **Multidimensional Code Review Taxonomy** mentransformasi proses peer-review dari aktivitas yang bersifat subjektif, lambat, dan rentan kelalaian kognitif menjadi disiplin rekayasa perangkat lunak enterprise yang terukur, deterministik, dan dapat diaudit. 

Dengan menyaring PR terlebih dahulu menggunakan **Automated Gating Engine** (*Policy-as-Code*, linter, SAST, dan contract validators), reviewer manusia dapat memusatkan energi kognitif mereka pada dimensi arsitektural esensial: **Invariant State**, **Thread & Concurrency Safety**, **Database Isolation & Migration Safety**, **Distributed Resiliency**, serta **Observability Compliance**. Penerapan metodologi ini secara konsisten merupakan fondasi utama dalam memelihara reliabilitas sistem skala enterprise dengan arsitektur *zero-downtime high-throughput*.