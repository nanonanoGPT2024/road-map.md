# Bab 02: Arsitektur Integrasi Sistem Legacy
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

Sebagai Forward-Deployed Engineer (FDE), medan tempur utama Anda jarang berupa sistem *greenfield* yang bersih. Anda dituntut untuk memasang kapabilitas modern (seperti *real-time AI decisioning*, *distributed ledger*, atau platform analitik berbasis *event-driven*) langsung ke atas sistem *brownfield* enterprise yang telah berusia puluhan tahun: Core Banking AS400/COBOL, SAP ECC R/3, basis data relasional monolitik yang terkunci, serta Message Broker berbasis IBM MQ/TIBCO.

Modul ini membedah arsitektur integrasi tingkat lanjut untuk mengekstraksi, mentransformasikan, dan menyinkronkan data transaksional secara *bidirectional* tanpa membebani (*zero-overhead impact*) sistem sumber atau merusak konsistensi transaksi enterprise.

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Mendesain Anti-Corruption Layer (ACL)** tingkat lanjut yang memisahkan model domain modern dari semantik dan batasan sistem legacy.
- **Mengimplementasikan Change Data Capture (CDC)** berbasis parsing Write-Ahead Log (WAL) / Redo Log untuk mengekstraksi event transaksi dengan latensi sub-detik tanpa memicu *table lock* atau *CPU degradation* pada database monolitik.
- **Mengeliminasi Anomali Dual-Write** menggunakan implementasi *Transactional Outbox Pattern* yang tahan terhadap kegagalan jaringan, *broker downtime*, dan *split-brain*.
- **Merancang Mekanisme Rekonsiliasi Otomatis (Reconciliation Loop)** untuk mendeteksi serta memulihkan *data drift* antara sistem enterprise legacy dan sistem edge terdistribusi.
- **Menerapkan Pola Event-Driven Strangler Fig** guna memigrasikan *write-path* monolitik secara bertahap menggunakan *idempotent routing* dan kompensasi transaksi saga.

---

### 2. Prerequisite

Sebelum mendalami modul ini, Anda wajib menguasai:
- **Distributed Systems Core**: Teorema CAP/PACELC, ACID vs BASE, Linearizability, At-least-once vs Exactly-once semantics.
- **Database Internals**: Struktur B-Tree, Write-Ahead Logging (WAL/Redo Log), isolation levels (Read Committed, Repeatable Read, Serializable), dan locking mechanism (MVCC, Row/Table Locks).
- **Protokol & Networking**: TCP/IP socket programming, pemahaman protokol sinkron vs asinkron (HTTP/gRPC vs AMQP/Kafka/IBM MQ), TLS 1.3 mutual authentication (mTLS).
- **Bahasa Pemrograman**: Kemahiran tingkat menengah-lanjut dalam Go atau Rust untuk implementasi konkurensi, memory management, dan *low-level I/O integration*.

---

### 3. Concept & Internal Architecture (Mendalam)

Integrasi sistem enterprise modern oleh FDE bertumpu pada lima pilar arsitektur dasar:

```
+---------------------------------------------------------------------------------------+
|                                MODERN DEPLOYED SYSTEM                                 |
|                                                                                       |
|  +------------------------+  gRPC / CloudEvents   +--------------------------------+  |
|  | Modern Event Processor | <===================> | Domain Logic (Clean Hexagonal) |  |
|  +------------------------+                       +--------------------------------+  |
+--------------^---------------------------------------------------^--------------------+
               |                                                   |
   Events (CDC via Kafka/Redpanda)                     gRPC / JSON-RPC
               |                                                   |
+--------------v---------------------------------------------------v--------------------+
|                         ANTI-CORRUPTION LAYER (ACL) ENGINE                            |
|                                                                                       |
|  +---------------------+   +---------------------+   +-----------------------------+  |
|  | Schema Canonicalizer|   | In-Flight Mediator  |   | Circuit Breaker / Rate Limit|  |
|  +---------------------+   +---------------------+   +-----------------------------+  |
|  +---------------------------------------------------------------------------------+  |
|  | Bidirectional Idempotency Engine & Distributed State Store (Redis / RocksDB)     |  |
+--------------^---------------------------------------------------^--------------------+
               |                                                   |
      Engine-Specific Adapters                          Protocol Translators
   (WAL Sniffing / Transaction Log)               (SOAP, EBCDIC, Fixed-Width, ISO 8583)
               |                                                   |
+--------------v---------------------------------------------------v--------------------+
|                                LEGACY ENTERPRISE SYSTEM                               |
|                                                                                       |
|  +------------------------+                       +--------------------------------+  |
|  | Oracle / IBM DB2 / IMS |                       | IBM MQ / TIBCO / SOAP ESB      |  |
|  | (Underlying DB Storage)|                       | (Legacy Core Monolith System)  |  |
|  +------------------------+                       +--------------------------------+  |
+---------------------------------------------------------------------------------------+
```

#### 3.1. The Anti-Corruption Layer (ACL) Internals
ACL bukan sekadar middleware penerjemah format payload (seperti JSON ke XML). Pada level kernel enterprise, ACL berfungsi sebagai:
1. **Semantic Boundary**: Menerjemahkan konsep model usang (misal: `FLAG_STATUS_01 = 'A'`) menjadi *first-class domain aggregate* modern (`AccountStatus = SuspendedPendingKYC`).
2. **Backpressure Buffer**: Melindungi sistem legacy yang hanya mampu menangani 50 TPS dari lonjakan beban sistem modern yang memproduksi 10.000 TPS menggunakan mekanisme *reactive streams leaky-bucket*.
3. **Protocol Adapter**: Melakukan terminasi koneksi TCP raw, unmarshaling framing biner EBCDIC/ISO-8583, dan membungkusnya ke dalam konteks gRPC thread-safe.

#### 3.2. Change Data Capture (CDC) vs Database Triggers
Pendekatan naif menggunakan SQL Triggers untuk audit/sinkronisasi menyebabkan degradasi performa eksponensial:
* **Trigger Overhead**: Dieksekusi dalam konteks transaksi yang sama (*synchronous write-amplification*), memperpanjang durasi *row-exclusive locks*, dan meningkatkan risiko *deadlock*.
* **CDC Non-Invasive Approach**: Bekerja asinkron dengan membaca binary storage engine WAL (misal: PostgreSQL `pgoutput`, MySQL `binlog`, Oracle `Redo Log / LogMiner`). I/O read dilakukan secara berurutan (*sequential disk read*), tidak memicu *lock contention*, dan independen dari lifecycle transaksi aplikasi monolit.

#### 3.3. Dual-Write Hazard & The Transactional Outbox Pattern
Ketika aplikasi modern harus memperbarui database lokal dan mengirim notifikasi ke sistem legacy, kegagalan jaringan di antara kedua operasi tersebut akan menyebabkan status inkonsisten (*partial failure state*).

```
   Pola Salah (Dual Write):
   DB.Save(Order)  -------> Sukses
   MQ.Publish(Order) -----> Jaringan Putus / Crash ==> INKONSISTENSI!

   Pola Benar (Transactional Outbox):
   BEGIN TRANSACTION
     DB.Save(Order)
     DB.Save(OutboxEvent)  <-- Disimpan dalam satu atomic transaction
   COMMIT
   
   Background Poller / WAL Reader --> Publish ke MQ --> Mark as Processed (ACK)
```

---

### 4. Why & What

| Dimensi | Metode Polling / Query Tradisional | Metode Event-Driven CDC & Outbox (Target FDE) |
| :--- | :--- | :--- |
| **Beban Database Sumber** | Sangat Tinggi (`SELECT * FROM table WHERE updated_at > ...` memicu *Full Table Scan*). | Mendekati Nol (Membaca file log transaksi secara asinkron dari memori/disk stream). |
| **Latensi Deteksi Data** | Berbasis interval polling (Detik hingga Menit). | Sub-detik (*near real-time* ~ 5-50 milidetik). |
| **Deteksi Operasi Hapus** | Tidak dapat mendeteksi `DELETE` fisik tanpa soft-delete audit triggers. | Menangkap event `DELETE` secara native via tombstone log record. |
| **Integritas Transaksi** | Rentan *missed updates* jika transaksi memiliki timestamp yang identik. | Deterministik penuh berdasarkan Log Sequence Number (LSN) atau System Change Number (SCN). |
| **Coupling Aplikasi** | Membutuhkan modifikasi skema tabel legacy (*timestamp index*). | Zero-code modification pada basis data aplikasi sumber. |

---

### 5. How (Workflow Detail)

Alur kerja implementasi *Strangler Fig Pattern* dan integrasi CDC enterprise:

```
[Legacy Monolith]
       |
       | 1. Transaksi Bisnis (INSERT/UPDATE/DELETE)
       v
[Database Storage (WAL/Redo)]
       |
       | 2. Streaming LSN Log Records (Asinkron)
       v
[CDC Engine (Debezium/Engine Core)]
       |
       | 3. Normalisasi Struct & Parsing Schema Engine
       v
[Anti-Corruption Layer (ACL)]
       |
       | 4. Deduplikasi via Redis Lock & Canonical Transformation
       v
[Modern Platform Pipeline]
       |
       | 5. Process & Apply Modern Business Rules
       v
[Idempotency State Store] ---> [Reconciliation Engine] (Verifikasi Checksum Periodik)
```

1. **Eksfiltrasi Log Transaksi**: CDC Engine mengikat koneksi replikasi ke database master legacy, membaca byte stream LSN (Log Sequence Number).
2. **Canonical Transformation**: Payload mentah diekstrak oleh ACL, menghapus artefak struktur database legacy, dan memetakan field ke proto spec CloudEvents v1.0.
3. **Penyimpanan Status Idempoten**: Pesan diproses dengan *deduplication key* (kombinasi `entity_id` + `version`/`timestamp`). Jika kunci terdeteksi duplikat pada sliding-window 24 jam, event dibuang tanpa error (*idempotent drop*).
4. **Validasi Skema Bertingkat**: Schema Registry memverifikasi kepatuhan payload. Jika terjadi evolusi skema legacy tanpa koordinasi (*drift*), payload dikirim ke Dead Letter Queue (DLQ) khusus disertai *alert level critical*.
5. **Periodic Reconciliation Sweep**: Engine sinkronisasi menjalankan *batch hashing verification* di luar jam sibuk untuk mencocokkan total record dan mendeteksi anomali transmisi data.

---

### 6. Analogy & Diagram ASCII

#### Analogi Penerjemah dan Diplomat Kedutaan
Bayangkan sistem legacy sebagai **Kaisar Kuno** yang hanya berbicara dalam dialek arkais dan memiliki temperamen buruk; sedikit interupsi tak terduga akan membuatnya murka (*system crash*). Sistem modern Anda adalah **Aliansi Bisnis Multinasional** dengan ribuan delegasi yang bergerak sangat cepat. 

FDE tidak membiarkan ribuan delegasi tersebut menyerbu istana Kaisar sekaligus. FDE membangun **Kedutaan Besar Khusus (Anti-Corruption Layer)** di luar gerbang istana:
- Para delegasi menyerahkan proposal modern mereka ke Kedutaan.
- Kedutaan menerjemahkan, memeriksa etiket istana, mengatur antrean diplomatik satu per satu (*rate limiting*), dan mencatat stempel kerajaan (*transaction commit*) secara cermat ke dalam buku besar (*WAL stream*).

```
                      ARSITEKTUR PIPELINE INTEGRASI LEGACY
                      
 Modern Requests        Leaky-Bucket Rate Limiter           Legacy System (Protected)
 +------------+        +--------------------------+        +-------------------------+
 | gRPC Call  | -----> | [x][x][x][ ] [ ]         | -----> | SOAP / RFC Monolith     |
 | 5,000 TPS  |        | Drops excess/Queueing    |        | Max Cap: 100 TPS        |
 +------------+        +--------------------------+        +-------------------------+
                                                                     | Writes
                                                                     v
                                                            +-------------------------+
                                                            | DB Relational Monolith  |
                                                            +-------------------------+
                                                                     |
                                                                     | WAL/Redo Extraction
                                                                     v
 Modern Consumer       Anti-Corruption Layer               +-------------------------+
 +------------+        +--------------------------+        | CDC Engine (Tailer)     |
 | Modern App | <===== | [De-dup Engine]          | <===== | Read LSN Changes        |
 | Event Sink |        | [Schema Mapping to gRPC] |        | Non-invasive streaming  |
 +------------+        +--------------------------+        +-------------------------+
```

---

### 7. Simple Example & Practical Example

Berikut adalah implementasi sistem produksi pipeline Anti-Corruption Layer (ACL) berkinerja tinggi menggunakan Go. Pipeline ini mengonsumsi raw change event dari basis data legacy, mengisolasi model mutasi, memverifikasi idempodensi secara terdistribusi, dan menyalurkannya ke model domain baru.

```go
package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"sync"
	"time"
)

// --- LEGACY MODELS (Domain Usang / Raw Schema) ---

// LegacyAccountRecord merepresentasikan tuple mentah dari DB2/Oracle legacy
type LegacyAccountRecord struct {
	AccNo        string `json:"ACC_NO"`
	CustStat     string `json:"CUST_STAT"` // "1" = Active, "2" = Suspended, "9" = Terminated
	BalAmt       int64  `json:"BAL_AMT"`   // Satuan sen (cents)
	LastUpdEpoch int64  `json:"LST_UPD"`   // Epoch millisecond
	OpType       string `json:"_op"`       // CDC metadata: "c"=Create, "u"=Update, "d"=Delete
}

// --- MODERN MODELS (Clean Architecture Domain) ---

type AccountStatus string

const (
	StatusActive    AccountStatus = "ACTIVE"
	StatusSuspended AccountStatus = "SUSPENDED"
	StatusClosed    AccountStatus = "CLOSED"
	StatusUnknown   AccountStatus = "UNKNOWN"
)

type ModernAccountEvent struct {
	EventID        string        `json:"eventId"`
	AccountNumber  string        `json:"accountNumber"`
	CurrentBalance float64       `json:"currentBalance"`
	Status         AccountStatus `json:"status"`
	Version        int64         `json:"version"`
	OccurredAt     time.Time     `json:"occurredAt"`
}

// --- PORTS & INTERFACES ---

type IdempotencyStore interface {
	IsProcessed(ctx context.Context, key string) (bool, error)
	MarkProcessed(ctx context.Context, key string, ttl time.Duration) error
}

type EventPublisher interface {
	Publish(ctx context.Context, event ModernAccountEvent) error
}

// --- ANTI-CORRUPTION LAYER (ACL) ENGINE ---

type ACLEngine struct {
	store     IdempotencyStore
	publisher EventPublisher
	mu        sync.RWMutex
}

func NewACLEngine(store IdempotencyStore, publisher EventPublisher) *ACLEngine {
	return &ACLEngine{
		store:     store,
		publisher: publisher,
	}
}

// TransformAndTranslate mengeksekusi konversi semantik batas domain
func (acl *ACLEngine) TransformAndTranslate(raw LegacyAccountRecord) (ModernAccountEvent, error) {
	if raw.AccNo == "" {
		return ModernAccountEvent{}, errors.New("invalid legacy record: missing ACC_NO")
	}

	var status AccountStatus
	switch raw.CustStat {
	case "1":
		status = StatusActive
	case "2":
		status = StatusSuspended
	case "9":
		status = StatusClosed
	default:
		status = StatusUnknown
	}

	// Normalisasi kalkulasi floating-point dari raw integer balance
	balance := float64(raw.BalAmt) / 100.0

	// Deterministic Event ID generation (Hashing)
	hashInput := fmt.Sprintf("%s:%d:%d", raw.AccNo, raw.BalAmt, raw.LastUpdEpoch)
	hasher := sha256.New()
	hasher.Write([]byte(hashInput))
	eventID := hex.EncodeToString(hasher.Sum(nil))

	return ModernAccountEvent{
		EventID:        eventID,
		AccountNumber:  raw.AccNo,
		CurrentBalance: balance,
		Status:         status,
		Version:        raw.LastUpdEpoch,
		OccurredAt:     time.UnixMilli(raw.LastUpdEpoch).UTC(),
	}, nil
}

// IngestCDCRecord menangani penerimaan mutasi data CDC dengan jaminan idempodensi
func (acl *ACLEngine) IngestCDCRecord(ctx context.Context, rawPayload []byte) error {
	var legacyRec LegacyAccountRecord
	if err := json.Unmarshal(rawPayload, &legacyRec); err != nil {
		return fmt.Errorf("failed to unmarshal legacy payload: %w", err)
	}

	// Lewati operasi yang tidak didukung dalam streaming sinkronisasi akun
	if legacyRec.OpType == "d" {
		// Logika tombstone handling diletakkan di sini sesuai kesepakatan domain
		return nil
	}

	modernEvent, err := acl.TransformAndTranslate(legacyRec)
	if err != nil {
		return fmt.Errorf("acl transformation error: %w", err)
	}

	// Evaluasi Idempodensi: Lindungi sistem hilir dari mutasi berulang/out-of-order
	idempotencyKey := fmt.Sprintf("idemp:account:%s:%d", modernEvent.AccountNumber, modernEvent.Version)
	alreadyProcessed, err := acl.store.IsProcessed(ctx, idempotencyKey)
	if err != nil {
		return fmt.Errorf("idempotency check failure: %w", err)
	}
	if alreadyProcessed {
		// Duplikasi terdeteksi secara graceful: ack tanpa memproses ulang
		return nil
	}

	// Dispatch ke ekosistem terdistribusi modern
	if err := acl.publisher.Publish(ctx, modernEvent); err != nil {
		return fmt.Errorf("failed to dispatch canonical event: %w", err)
	}

	// Tandai status eksekusi berhasil dengan TTL batas toleransi replay window
	if err := acl.store.MarkProcessed(ctx, idempotencyKey, 24*time.Hour); err != nil {
		// Peringatan sistem: Berhasil publish namun gagal commit idempodensi state
		return fmt.Errorf("critical state mismatch: %w", err)
	}

	return nil
}

// --- MOCK IN-MEMORY IMPLEMENTATIONS FOR DEMONSTRATION ---

type InMemoryIdempotencyStore struct {
	m  map[string]time.Time
	mu sync.Mutex
}

func (s *InMemoryIdempotencyStore) IsProcessed(_ context.Context, key string) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	expiry, exists := s.m[key]
	if !exists {
		return false, nil
	}
	if time.Now().After(expiry) {
		delete(s.m, key)
		return false, nil
	}
	return true, nil
}

func (s *InMemoryIdempotencyStore) MarkProcessed(_ context.Context, key string, ttl time.Duration) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.m[key] = time.Now().Add(ttl)
	return nil
}

type StandardOutPublisher struct{}

func (p *StandardOutPublisher) Publish(_ context.Context, event ModernAccountEvent) error {
	out, _ := json.MarshalIndent(event, "", "  ")
	fmt.Printf("[PUBLISHED TO MODERN BROKER]\n%s\n", string(out))
	return nil
}

func main() {
	ctx := context.Background()
	store := &InMemoryIdempotencyStore{m: make(map[string]time.Time)}
	pub := &StandardOutPublisher{}
	engine := NewACLEngine(store, pub)

	// Simulasi event raw dari dekomposisi data streaming legacy
	sampleLegacyPayload := []byte(`{
		"ACC_NO": "ACC-ID-992811",
		"CUST_STAT": "1",
		"BAL_AMT": 55000050,
		"LST_UPD": 1711929600000,
		"_op": "u"
	}`)

	fmt.Println("--- Ingesting Incoming Event #1 ---")
	if err := engine.IngestCDCRecord(ctx, sampleLegacyPayload); err != nil {
		panic(err)
	}

	fmt.Println("\n--- Ingesting Duplicate Payload #2 (Simulasi Replay / Network Retry) ---")
	if err := engine.IngestCDCRecord(ctx, sampleLegacyPayload); err != nil {
		panic(err)
	}
	fmt.Println("Replay berhasil diabaikan secara idempoten.")
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Klien
Sebuah Bank Tier-1 di Asia Tenggara memiliki sistem Core Banking berbasis **IBM AS/400 (DB2)** yang telah berjalan selama 28 tahun. Core ini memproses transaksi mutasi rekening, buku besar (*general ledger*), dan pinjaman. 

#### Masalah Bisnis & Teknis
- Platform *Fraud Detection* berbasis Machine Learning modern memerlukan *real-time balance and transaction delta updates* dalam batas SLA < 150 milidetik sejak penarikan di ATM atau transfer online terjadi.
- Vendor core banking melarang injeksi kueri audit atau trigger langsung ke tabel `TXN_LOG` utama, karena utilisasi CPU AS/400 sudah mencapai 82% pada jam sibuk (*peak hours*). Peningkatan utilisasi di atas 90% memicu ancaman kegagalan transaksi ATM regional.
- Batch extractor file dump CSV setiap 6 jam menghasilkan blindspot fraud hingga miliaran rupiah per kuartal.

#### Solusi Forward-Deployed Engineering
1. **Penerapan CDC Journal-Tailer**:
   FDE mengonfigurasi mekanisme integrasi membaca *Journal Receiver* internal IBM iSeries (`QSYS/QJRN`) secara streaming langsung ke bridge engine eksternal. Pendekatan ini menurunkan overhead CPU AS/400 menjadi < 1.5%.
2. **Dynamic In-flight Buffering**:
   Di sisi ingestion layer, FDE menggelar cluster Kafka 3-node yang dipadukan dengan Anti-Corruption Layer yang ditulis dalam bahasa Rust. Rust bertugas melakukan parsing frame data biner EBCDIC ke canonical JSON schema yang kompatibel dengan Kafka Schema Registry.
3. **Partition-key Routing**:
   Event di-routing ke Kafka Partition menggunakan hashing `Account_Number`. Ini menjamin transaksi untuk rekening yang sama diproses secara *strictly-ordered* di mesin inferensi fraud modern tanpa memerlukan *distributed locks* lintas partisi.

#### Metrik Keberhasilan yang Dicapai
- **End-to-End Latency**: Penurunan latensi sinkronisasi dari 6 jam (batch) menjadi **42 milidetik** (persentil P99).
- **CPU Impact**: Lonjakan beban tambahan pada Core AS/400 tercatat hanya **0.8%**.
- **Fraud Prevention**: Menghentikan anomali penarikan dana simultan (*parallel cash-out attack*) dalam waktu < 200 milidetik, menyelamatkan kerugian estimasi senilai $4.2 Juta USD pada kuartal pertama implementasi.

---

### 9. Trade-offs

Setiap keputusan arsitektur integrasi legacy memiliki konsekuensi teknis yang harus dikelola secara sadar:

```
+----------------------------------------------------------------------------------------------------+
|                                    CDC via WAL vs Outbox Table                                     |
+------------------------------------+---------------------------------------------------------------+
| METODE CDC (Log Mining)            | METODE TRANSACTIONAL OUTBOX                                   |
+------------------------------------+---------------------------------------------------------------+
| (+) Performa murni: Zero DB write  | (-) Write amplification: Menulis 2x ke tabel bisnis dan tabel |
|     amplification pada app layer.  |     outbox dalam transaksi database yang sama.                |
| (+) Zero schema modification pada  | (-) Membutuhkan perubahan DDL atau kode monolitik lama untuk   |
|     database legacy.               |     menyertakan insert outbox.                                |
| (-) Memerlukan hak akses superuser | (+) Sepenuhnya agnostik database: Dapat bekerja pada DBMS apa  |
|     / root replication privilege.  |     saja yang mendukung ACID dasar tanpa adapter log binary.  |
| (-) Sangat sensitif terhadap DDL   | (+) Data yang masuk ke outbox dapat disaring dan dimodelkan    |
|     schema breakages tak terdokum. |     lebih bersih sejak dari level aplikasi legacy.             |
+------------------------------------+---------------------------------------------------------------+
```

- **Latency vs Resource Cost**: CDC Streaming via Redo Log memberikan latensi sub-detik, tetapi lisensi tools perantara (misal: Oracle GoldenGate atau Qlik Replicate) dapat memakan biaya operasional ratusan ribu dolar jika tidak menggunakan Debezium open-source.
- **In-process ACL vs Standalone Gateway**:
  - *In-process ACL*: Latensi *ultra-low*, *zero network-hop*, tetapi siklus deployment terikat mati dengan aplikasi konsumen.
  - *Standalone Gateway ACL*: *Decoupled lifecycle*, skalaritas independen, namun menambah *network serialization latency* (~2-5 ms per request hop).

---

### 10. Common Mistakes & Troubleshooting

#### 1. Poison Pill Event Jamming
- **Gejala**: Pipeline konsumsi CDC berhenti total; lag pada partisi broker terus membengkak (*partition lag spike*).
- **Penyebab**: Event memiliki format corrupt yang gagal di-parse oleh serializer ACL, memicu crash loop pada consumer loop tanpa committing offset.
- **Solusi**: Implementasikan *dead-letter routing with circuit break context*. Bungkus unmarshaling dalam blok `recover()` (Go) atau penanganan error bertingkat; alihkan record invalid ke antrean `dlq.legacy.corrupt` bersama seluruh header context tracing.

#### 2. Sequence Drift / Out-of-Order Execution
- **Gejala**: Status rekening di sistem baru teroverride menjadi status lama (misal: kembali menjadi `SUSPENDED` padahal sudah `ACTIVE`).
- **Penyebab**: Transaksi legacy di-publish secara asinkron menggunakan multi-threading tanpa partisi berbasis Entity ID, merusak urutan temporal log.
- **Solusi**: Gunakan strictly monotonic sequence IDs (seperti LSN/SCN database atau Kafka Message Keys berbasis Hash Rekening). Pada ACL, pasang conditional write:
  $$\text{Reject update if: } \text{IncomingVersion} \le \text{CurrentStoreVersion}$$

#### 3. Log Expiration / WAL Disk Bloat
- **Gejala**: Storage server database legacy mendadak penuh hingga 100%, menyebabkan database mengalami *panic shutdown*.
- **Penyebab**: Slot replikasi CDC offline atau consumer mengalami downstream bottleneck. Database master menahan penghapusan berkas WAL lama karena menunggu ACK dari replika CDC yang tertinggal.
- **Solusi**: Pasang hard-limit retention pada server database (misal: `max_slot_wal_keep_size` pada PostgreSQL) dan terapkan monitoring alerting ketat pada `Replication Lag Bytes`.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum mengaktifkan koneksi integrasi di lingkungan produksi:

- [ ] **Credential Minimization**: Kredensial CDC hanya memiliki hak baca pada slot replikasi transaksi, tanpa hak akses mutasi DDL/DML ke tabel data.
- [ ] **High Availability State Store**: Idempotency layer didukung oleh shared memory cache berkecepatan tinggi (Redis Sentinel / Cluster) dengan konfigurasi memory eviction `volatile-lru`.
- [ ] **Schema Drift Guard**: Schema registry terpasang dengan mode kompatibilitas backward-transitive enforcement.
- [ ] **Strict Connection Pooling**: Driver legacy dibatasi koneksi maksimumnya ($MaxPoolSize \le 20\%$) dari sisa koneksi monolit yang tersedia.
- [ ] **Safe Reconciliation Schedule**: Rekonsiliasi audit penuh (*Full Hash Check*) hanya dieksekusi di jendela batch terjadwal (*maintenance window* pukul 01:00 - 03:00).
- [ ] **Correlation Tracking**: Memetakan atau menginjeksi Transaction Tracking Tag / UUID modern ke dalam log audit legacy (misal: memanfaat field `USER_AGENT` atau `CLIENT_INFO` pada session Oracle).

---

### 12. Hands-on Practice

Target Praktikum: Membangun pipeline terintegrasi anti-corruption layer berbasis Go yang memvalidasi parsing stream event dari mock PostgreSQL WAL. Kode praktikum disimpan pada direktori: `hands-on/m02/`.

#### Langkah 1: Siapkan Docker Compose (`hands-on/m02/docker-compose.yml`)
```yaml
version: '3.8'
services:
  legacy-db:
    image: postgres:15-alpine
    container_name: legacy_db
    environment:
      POSTGRES_USER: legacy_user
      POSTGRES_PASSWORD: secret_password
      POSTGRES_DB: core_bank
    ports:
      - "5432:5432"
    command: ["postgres", "-c", "wal_level=logical"]

  redis-idemp:
    image: redis:7-alpine
    container_name: redis_idemp
    ports:
      - "6379:6379"
```

#### Langkah 2: Inisialisasi Skema Legacy (`hands-on/m02/init.sql`)
```sql
CREATE TABLE T_LEGACY_LEDGER (
    ACC_ID VARCHAR(32) PRIMARY KEY,
    CURR_BAL BIGINT NOT NULL,
    STATUS_CODE CHAR(1) NOT NULL,
    SYS_TIMESTAMP BIGINT NOT NULL
);

INSERT INTO T_LEGACY_LEDGER VALUES ('ID_ACCT_001', 100000, 'A', 1711929600);
```

#### Langkah 3: Eksekusi Kode ACL Consumer (`hands-on/m02/main.go`)
1. Jalankan dependency: `docker compose up -d`.
2. Tulis consumer yang membaca event streaming (simulasikan input JSON dari log streamer).
3. Jalankan aplikasi Go: `go run main.go`.
4. Uji ketahanan dengan mengirim payload yang sama berkali-kali untuk membuktikan bahwa downstream publisher hanya terpicu tepat **satu kali**.

---

### 13. Exercise

Kerjakan latihan berikut langsung di repositori latihan Anda:

- **Level Easy**: 
  Modifikasi `TransformAndTranslate` pada kode Go Bagian 7 untuk menangani skema legacy baru: `CURR_CODE` (string misal: "IDR", "USD"). Jika mata uang bukan "IDR", konversikan saldo ke IDR menggunakan nilai tukar statis hardcoded, lalu tandai flag boolean `IsConverted: true` pada model modern.
- **Level Medium**: 
  Rancang middleware circuit-breaker pada pipeline ingestion. Jika downstream modern publisher mengembalikan error 5xx secara beruntun sebanyak 5 kali, hentikan penarikan pesan dari queue legacy selama 10 detik, lalu masuk ke status *half-open*.
- **Level Hard**: 
  Bangun in-memory *Reconciliation Engine* yang menerima slice of `LegacyAccountRecord` dan slice of `ModernAccountEvent`. Algoritma harus mendeteksi dan menampilkan laporan:
  1. Record yang hilang di sistem modern (*missing data*).
  2. Record yang nilainya inkonsisten (*drifted value*).
  3. Menggunakan kompleksitas waktu maksimum $\mathcal{O}(N + M)$ dan alokasi memori tambahan minimum.

---

### 14. Challenge

Sebagai Senior Forward-Deployed Engineer, Anda ditempatkan di sebuah konglomerat logistik maritim. Sistem legasi mereka adalah mainframe berbasis file teks flat (COBOL fixed-width record) yang hanya diperbarui tiap 12 jam via FTP, sementara sistem modern yang Anda deploy adalah IoT Automated Port Dispatcher yang memerlukan koordinasi kontainer *real-time*.

**Tugas Arsitektur:**
1. Desain arsitektur integrasi yang menangani kondisi di mana pembaruan data kontainer di-push secara real-time dari sensor IoT modern, tetapi database mainframe lama tetap bertindak sebagai *source of truth* hukum perkapalan.
2. Selesaikan dilema *concurrent write conflict*: Bagaimana strategi Anda ketika kapal merapat di dermaga dan memicu update status di edge, sementara file flat dari pelabuhan asal baru saja tiba di mainframe dan menimpa status kontainer tersebut dengan status data usang?
3. Sajikan dokumen desain teknis yang mencakup:
   - Diagram aliran data State-Machine.
   - Mekanisme rekonsiliasi berbasis vektor waktu (*Vector Clock* atau *Conflict-free Replicated Data Types/CRDT*).
   - Strategi mitigasi resiko jika sambungan satelit kapal terputus selama 48 jam di laut lepas (*offline-first sync*).

---

### 15. Quiz Evaluasi Pemahaman

Jawablah pertanyaan-pertanyaan evaluasi berikut untuk menguji kesiapan arsitektural Anda.

#### Bagian A: Basic (Pilihan Ganda)
1. Apa fungsi utama Anti-Corruption Layer (ACL) dalam arsitektur integrasi?
   - A. Mempercepat eksekusi query database legacy dengan indexing otomatis.
   - B. Membatasi dan mengisolasi model konseptual legacy agar tidak mencemari model domain modern.
   - C. Mengenkripsi seluruh data transit dari sistem legacy ke sistem modern.
   - D. Menggantikan peran hardware load balancer.
2. Mengapa CDC berbasis Write-Ahead Log (WAL) lebih disukai daripada SQL Polling berkala?
   - A. Karena WAL tidak menggunakan memori server sama sekali.
   - B. Karena SQL Polling membutuhkan lisensi terpisah dari vendor database.
   - C. Karena WAL membaca log secara asinkron tanpa memicu resource lock contention yang berat pada database operasional.
   - D. Karena WAL secara otomatis mengubah format SQL ke JSON tanpa konfigurasi.
3. Kapan Transactional Outbox Pattern mutlak diperlukan?
   - A. Saat sistem hanya memiliki satu database dan tidak menggunakan network message broker.
   - B. Saat sistem harus mengubah state database lokal sekaligus mengirim event ke broker eksternal secara atomik tanpa dual-write hazard.
   - C. Saat kita ingin mempercepat proses baca pada analitik data.
   - D. Saat menggunakan protokol UDP untuk transmisi data.
4. Apa yang dimaksud dengan *idempotent consumer*?
   - A. Consumer yang hanya memproses pesan jika formatnya JSON valid.
   - B. Consumer yang memproses pesan lebih dari satu kali dan menghasilkan efek samping status akhir yang sama seperti diproses satu kali.
   - C. Consumer yang menghapus seluruh data usang di database secara berkala.
   - D. Consumer yang secara otomatis melakukan roll-back transaksi setiap terjadi network error.
5. Log Sequence Number (LSN) pada basis data relasional berfungsi sebagai:
   - A. Token autentikasi untuk klien remote.
   - B. Penanda urutan byte monolitik unik yang merefleksikan posisi riwayat mutasi data di storage engine.
   - C. Nomor port komunikasi internal database engine.
   - D. Total waktu (dalam detik) server database telah berjalan.

#### Bagian B: Intermediate (Analisis Sistem)
1. Jelaskan mengapa pendekatan *Distributed Two-Phase Commit (2PC)* sangat dihindari untuk menghubungkan sistem microservices modern dengan sistem monolit legacy!
2. Dalam skenario replikasi CDC, apa yang dimaksud dengan fenomena *Tombstone Event* dan bagaimana ACL harus meresponsnya?
3. Sebutkan dua skenario spesifik di mana Transactional Outbox Pattern masih dapat menghasilkan duplikasi pengiriman pesan ke downstream broker!
4. Bagaimana cara mengamankan integritas schema registry ketika tim core legacy melakukan modifikasi tipe kolom database tanpa pemberitahuan sebelumnya?
5. Mengapa mekanisme *Leaky-Bucket* lebih direkomendasikan daripada *Token-Bucket* murni ketika sistem modern berinteraksi dengan API legacy yang sangat rapuh?

#### Bagian C: Skenario Kasus Produksi
1. **Kasus 1**: Sistem integrasi CDC Anda tiba-tiba mengalami lonjakan replikasi lag dari 50ms ke 45 menit setelah tim operasional legacy menjalankan perintah migrasi batch: `UPDATE ACCOUNTS SET STATUS = 'INACTIVE' WHERE REGION = 'NORTH'`. Analisis apa yang terjadi pada pipeline Anda dan bagaimana langkah remediasinya!
2. **Kasus 2**: Anda menemukan bahwa kunci idempodensi di Redis tiba-tiba terhapus lebih cepat sebelum consumer kedua memproses event duplikat yang datang terlambat akibat network retry. Apa dampak sistemik yang ditimbulkan dan bagaimana arsitektur diperbaiki?
3. **Kasus 3**: Core mainframe bank hanya menerima request via protokol biner TCP ISO-8583 dan mematikan koneksi secara paksa jika menerima lebih dari 30 koneksi paralel. Rancang arsitektur konektor gateway untuk menghubungkan 50 service instance Kubernetes modern yang perlu bertransaksi ke mainframe tersebut.

---

### 16. Summary

Mengintegrasikan sistem legacy dengan arsitektur modern bukan sekadar urusan *network routing* atau konversi format payload. Ini adalah rekayasa keandalan sistem terdistribusi di bawah batasan sistem lawas yang rapuh:

1. **Anti-Corruption Layer (ACL)** bertindak sebagai perisai semantik dan peredam kejut struktural yang memisahkan kebersihan domain modern dari kompleksitas teknis legacy.
2. **Change Data Capture (CDC)** non-invasif berbasis WAL adalah standar industri untuk membebaskan data enterprise tanpa membebani CPU sistem monolitik.
3. **Transactional Outbox & Idempotent Consumer** adalah kombinasi mutlak guna meniadakan risiko kegagalan *dual-write* dan menjamin status data tetap konsisten (*eventually consistent*) di tengah gangguan jaringan.
4. **Prinsip FDE Sejati**: Kita tidak menunggu klien memodernisasi sistem lama mereka; kita membangun jembatan arsitektur yang aman, berkinerja tinggi, dan tahan banting agar sistem modern dapat langsung memberikan nilai bisnis sejak hari pertama pemasangan.