# BAB 01: Fondasi dan Arsitektur
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi: Forward-Deployed Engineer (FDE)

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Mendesain Arsitektur Ekstensi Terisolasi (*Isolated Extension Architecture*)**: Merancang batas sistem (*system boundary*) yang memisahkan *Core Platform Engine* dari *Client-Specific Adaptation Layer* guna mencegah *codebase forking*.
2. **Mengimplementasikan Runtime Schema Reconciliation Dinamis**: Membangun *data mediation engine* menggunakan Go dan WebAssembly (WASM) atau gRPC *out-of-process plugins* untuk menangani *schema drift* pada data enterprise klien secara *real-time*.
3. **Mengoperasikan Pola Deployment Hybrid & Air-Gapped**: Mengonfigurasi arsitektur agen *forward-deployed* yang dapat berjalan di lingkungan *zero-trust*, *on-premises*, maupun *VPC-peered* dengan mekanisme sinkronisasi asinkron dan *tamper-proof telemetry*.
4. **Menerapkan Circuit Breaking & Resource Throttling**: Mengamankan *Core Platform* dari malafungsi sistem integrasi lokal klien menggunakan pola *resilience* tingkat lanjut.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Konsep tingkat lanjut **Arsitektur Heksagonal (*Ports & Adapters*)** dan *Domain-Driven Design* (DDD).
* Pemrograman sistem menggunakan **Golang** (Goroutines, Channels, Interfaces, Reflection, dan Cgo/WASM runtime basics).
* Mekanisme komunikasi sistem terdistribusi: **gRPC/Protobuf**, **mTLS**, dan **Event Streaming (Kafka/NATS)**.
* Infrastruktur kontainer dan orkestrasi: **Kubernetes Operator Pattern**, Helm, serta konsep jaringan L4/L7 (Service Mesh, Envoy).

---

### 3. Concept & Internal Architecture (Mendalam)

Peran *Forward-Deployed Engineer* (FDE) berada di garis batas antara rekayasa perangkat lunak inti (*Core Platform Engineering*) dan realitas infrastruktur klien enterprise yang heterogen, *legacy*, dan sering kali tidak ramah (*hostile network/restricted cloud*).

Tantangan arsitektur terbesar bagi FDE adalah: **Bagaimana memberikan kustomisasi radikal bagi klien enterprise berdaya bayar tinggi tanpa merusak integritas *Core Engine*, tanpa membuat cabang kode (*git branch*) permanen per klien, dan tanpa mengorbankan performa sistem terdistribusi?**

#### 3.1 The Architectural Dichotomy: Core Engine vs. Forward Extensions

Sistem enterprise yang sukses menerapkan pola FDE membagi arsitekturnya menjadi tiga lapisan diskret:

```
+-----------------------------------------------------------------------+
|                         Core Platform Engine                          |
|  - Immutable Business Logic        - Distributed Storage Engine       |
|  - Unified Identity Engine         - Consensus & Compute Plane        |
+-----------------------------------+-----------------------------------+
                                    | (Strict API Contract / Protobuf)
+-----------------------------------v-----------------------------------+
|                   FDE Adaptation Layer (Mediation Plane)              |
|  - Schema Normalization Engine    - Protocol Transformation           |
|  - Client Context Injector        - Dynamic Validation & Sanitization |
+-----------------------------------+-----------------------------------+
                                    | (Heterogeneous Enterprise Feeds)
+-----------------------------------v-----------------------------------+
|                     Client Infrastructure Boundary                    |
|  - Legacy RDBMS (Oracle/DB2)       - Custom Auth (Kerberos/SAML/NTLM) |
|  - Air-Gapped S3/HDFS Storage     - Event Buses (ActiveMQ/TIBCO)      |
+-----------------------------------------------------------------------+
```

1. **Core Platform Engine**: Komponen berbasis multi-tenant atau single-tenant terkelola yang bersifat *strictly agnostic* terhadap model data partikular milik satu klien. Semua operasi divalidasi berdasarkan *canonical schema*.
2. **FDE Adaptation Layer**: Komponen modular (dapat berupa *in-process WASM guest*, *out-of-process sidecar*, atau *edge forwarder agent*) yang ditulis atau dikonfigurasi oleh FDE di lapangan. Layer ini bertindak sebagai *anti-corruption layer* (ACL).
3. **Client Boundary**: Sistem hulu (*upstream*) dan hilir (*downstream*) milik klien dengan protokol proprietary, latensi tinggi, dan ketidakpastian skema (*dynamic schema drift*).

#### 3.2 Dynamic Schema Reconciliation Pipeline

Dalam integrasi enterprise, data klien jarang sekali sesuai dengan *canonical schema* platform inti. FDE harus menerapkan *schema-on-read* atau *dynamic schema reconciliation* berbasis pipeline:

1. **Raw Payload Ingestion**: Payload ditangkap melalui streaming agent atau webhook receiver.
2. **Dynamic Unmarshaling & Schema Inference**: Payload dipetakan ke representasi intermediat berbasis pohon token (*token tree*) atau *flattened key-value maps* tanpa serialisasi statis ganda.
3. **Transform Rules Execution**: Dijalankan melalui *isolated sandbox* (misalnya WASM engine seperti Wasmtime/Wazero atau runtime DSL terisolasi) untuk memastikan eksekusi kode kustom klien tidak menimbulkan *memory leak* atau *panic* pada host process.
4. **Validation against Canonical Contracts**: Memvalidasi hasil transformasi terhadap skema canonical via Protobuf/JSON Schema.
5. **Core Delivery**: Pengiriman via stream berkecepatan tinggi ke Core Engine dengan jaminan *at-least-once* menggunakan sinkronisasi WAL (*Write-Ahead Logging*).

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Ad-hoc Forking) | Pendekatan Enterprise FDE (Pluggable Runtime) |
| :--- | :--- | :--- |
| **Pola Manajemen Kode** | Membuat git branch per klien (`release/client-acme-bank`). | Satu *canonical codebase*; logika spesifik klien berada di repositori konfigurasi/plugin terisolasi. |
| **Siklus Pembaruan Platform** | *Merge conflict hell*. Fitur baru core butuh berminggu-minggu untuk di-porting ke branch klien. | Core diperbarui independen via CI/CD. Ekstensi klien mengimplementasikan API Contract berbasis semver. |
| **Isolasi Kegagalan** | Bug pada kode integrasi klien dapat menyebabkan *crash* pada *central processing engine*. | *Sandboxed execution* (WASM/Sidecar). Kegagalan integrasi klien diisolasi oleh *circuit breaker*. |
| **Audit & Kepatuhan** | Data klien bocor ke environment deployment lain karena pipeline deployment bercampur. | Ekstensi dijalankan *on-premises* atau di VPC klien; data tidak pernah meninggalkan batas kepatuhan (*compliance boundary*). |

---

### 5. How (Workflow Detail)

Alur kerja operasional dan sistematis dari implementasi FDE tingkat lanjut:

```
[Client Legacy Feed]
         |
         v
[Edge Agent: Ingestion Listener]
         |
         +--> [Disk-Backed WAL (Write-Ahead-Log)] (Data Protection)
         |
         v
[Plugin Sandbox Manager (Wasm/gRPC-Worker)]
         |
         +--> Fetches Dynamic Client Rules (from Control Plane)
         |
         +--> Transforms: Legacy Wire -> Canonical Protobuf
         |
         v
[Payload Canonical Validator]
         |
    +----+----+
    |         | (Invalid)
 (Valid)      +--> [Dead Letter Queue (DLQ)] -> [Alert to FDE Dashboard]
    |
    v
[mTLS / Egress Proxy via Forward Proxy / Tunnel]
         |
         v
[Core Platform Ingestion Gateway]
```

1. **Ingest**: Edge Agent menerima data mentah dari jaringan klien (Kafka, Mainframe dump via SFTP, CDC Debezium).
2. **Persist (WAL)**: Sebelum parsing dilakukan, raw byte stream dicatat ke disk lokal (WAL) untuk menjamin pemulihan jika terjadi kegagalan daya atau restart pod.
3. **Sandbox Transformation**: Data dilempar ke thread worker terisolasi (sandbox). Sandbox mengeksekusi *client-specific transformation bytecode*.
4. **Validation**: Output divalidasi terhadap kontrak Protobuf inti. Payload cacat diarahkan ke DLQ bersama metadata eksekusi untuk audit teknis FDE.
5. **Egress Streaming**: Payload valid di-stream ke Core Engine melalui terowongan terenkripsi (mTLS/WireGuard).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Stasiun Luar Angkasa Internasional (ISS) & Modul Dok Universal
Bayangkan Core Platform sebagai **Inti Stasiun Luar Angkasa (ISS)** dengan sistem pendukung kehidupan, daya, dan komunikasi yang kaku, teruji, dan tidak boleh dimodifikasi sembarangan. 

Setiap pesawat luar angkasa klien (SpaceX Dragon, Soyuz, Starliner) memiliki sistem propulsi, voltase, dan antarmuka mekanis yang berbeda. FDE bukanlah insinyur yang merombak dinding ISS demi menyesuaikan satu kapsul. FDE adalah tim yang merancang **Modul Adaptor Dok Universal (*Universal Docking Adapter*)**. Modul dok ini dapat menyerap getaran, mengonversi voltase, menyamakan tekanan udara, dan menerjemahkan protokol navigasi dari pesawat asing sebelum astronot atau kargo diizinkan melintasi batas lambung kapal ISS.

#### Diagram Arsitektur Runtime FDE

```
+---------------------------------------------------------------------------------------+
| CLIENT PRIVATE INFRASTRUCTURE (VPC / ON-PREMISE)                                      |
|                                                                                       |
|  +--------------------+        +---------------------------------------------------+  |
|  | Unstructured /     |        | FDE Forward-Deployed Agent                        |  |
|  | Proprietary Feeds  |        |                                                   |  |
|  |                    |        |  +---------------------------------------------+  |  |
|  | [Legacy DB/MQ/API] | raw    |  | Ingress Adaptor (Kafka, REST, gRPC, Socket)   |  |  |
|  +--------+-----------+ payload|  +----------------------+----------------------+  |  |
|           |                    |                         |                          |  |
|           +------------------->|  +----------------------v----------------------+  |  |
|                                |  | Resilience Layer: Local Disk WAL            |  |  |
|                                |  +----------------------+----------------------+  |  |
|                                |                         |                          |  |
|                                |  +----------------------v----------------------+  |  |
|                                |  | Isolated Sandbox Runtime (WASM / Extism)   |  |  |
|                                |  |  - Tenant-Specific Mapping Logic            |  |  |
|                                |  |  - Zero-Allocation Parsers                  |  |  |
|                                |  +----------------------+----------------------+  |  |
|                                |                         |                          |  |
|                                |  +----------------------v----------------------+  |  |
|                                |  | Egress Client Engine (Circuit Breaker)       |  |  |
|                                |  +----------------------+----------------------+  |  |
|                                +-------------------------|-------------------------+  |
+----------------------------------------------------------|----------------------------+
                                                           | mTLS (Encrypted Wire)
                                                           v
+---------------------------------------------------------------------------------------+
| CORE PLATFORM BOUNDARY (Multi-Tenant Cloud / Secured Target)                          |
|                                                                                       |
|  +---------------------------------------------------------------------------------+  |
|  | Core Ingestion Gateway (Stateless, Validates Canonical Schemas Only)             |  |
|  +---------------------------------------+-----------------------------------------+  |
|                                          |                                            |
|                                          v                                            |
|  +---------------------------------------------------------------------------------+  |
|  | Core Platform Domain Engine / Distributed Ledger / Analytical Plane             |  |
|  +---------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Dynamic Contract-Driven Ingestion Proxy (Go)

Contoh dasar berikut mendemonstrasikan bagaimana FDE mengabstraksi input spesifik klien menggunakan *contract pattern* berbasis interface Go untuk memastikan Core Engine tidak terkontaminasi logika parsing vendor.

```go
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"
)

// CanonicalEntity adalah representasi immutable di Core Platform
type CanonicalEntity struct {
	ID        string            `json:"id"`
	Source    string            `json:"source"`
	Timestamp int64             `json:"timestamp"`
	Payload   map[string]any    `json:"payload"`
	Metadata  map[string]string `json:"metadata"`
}

// ClientPayloadAdapter adalah kontrak yang harus diimplementasikan oleh FDE per klien
type ClientPayloadAdapter interface {
	Reconcile(raw []byte) (*CanonicalEntity, error)
	ClientID() string
}

// ClientAcmeAdapter: Implementasi khusus untuk Klien Acme Corp (Format Proprietary)
type ClientAcmeAdapter struct{}

func (a *ClientAcmeAdapter) ClientID() string {
	return "client-acme-corp"
}

func (a *ClientAcmeAdapter) Reconcile(raw []byte) (*CanonicalEntity, error) {
	// Acme mengirimkan data dalam format: {"acme_id": "XYZ", "epoch_ms": 170000000, "attributes": "k1=v1;k2=v2"}
	var acmeData struct {
		AcmeID     string `json:"acme_id"`
		EpochMs    int64  `json:"epoch_ms"`
		Attributes string `json:"attributes"`
	}

	if err := json.Unmarshal(raw, &acmeData); err != nil {
		return nil, fmt.Errorf("parsing error pada format legacy acme: %w", err)
	}

	if acmeData.AcmeID == "" {
		return nil, errors.New("mandatory field 'acme_id' tidak ditemukan")
	}

	return &CanonicalEntity{
		ID:        fmt.Sprintf("acme:%s", acmeData.AcmeID),
		Source:    a.ClientID(),
		Timestamp: acmeData.EpochMs,
		Payload: map[string]any{
			"raw_attributes": acmeData.Attributes,
		},
		Metadata: map[string]string{
			"reconciled_by": "fde-adapter-v1",
		},
	}, nil
}

// CoreIngestionPipeline hanya mengenali Interface, bukan struct konkret klien
type CoreIngestionPipeline struct {
	adapters map[string]ClientPayloadAdapter
}

func NewPipeline() *CoreIngestionPipeline {
	return &CoreIngestionPipeline{
		adapters: make(map[string]ClientPayloadAdapter),
	}
}

func (p *CoreIngestionPipeline) RegisterAdapter(adapter ClientPayloadAdapter) {
	p.adapters[adapter.ClientID()] = adapter
}

func (p *CoreIngestionPipeline) Process(ctx context.Context, clientID string, rawPayload []byte) (*CanonicalEntity, error) {
	adapter, exists := p.adapters[clientID]
	if !exists {
		return nil, fmt.Errorf("adapter tidak terdaftar untuk client_id: %s", clientID)
	}

	// Dynamic Reconciliation
	entity, err := adapter.Reconcile(rawPayload)
	if err != nil {
		return nil, fmt.Errorf("reconciliation failed: %w", err)
	}

	return entity, nil
}

func main() {
	pipeline := NewPipeline()
	pipeline.RegisterAdapter(&ClientAcmeAdapter{})

	rawClientData := []byte(`{"acme_id": "TX-9921", "epoch_ms": 1711928392000, "attributes": "tier=gold;risk=low"}`)

	entity, err := pipeline.Process(context.Background(), "client-acme-corp", rawClientData)
	if err != nil {
		panic(err)
	}

	fmt.Printf("[Core Ingestion Success] ID: %s | Source: %s | Timestamp: %d\n", entity.ID, entity.Source, entity.Timestamp)
}
```

---

#### 7.2 Practical Example: Enterprise-Grade FDE Data Mediator with Circuit Breaker, Concurrency Pools, and Metrics

Implementasi produksi berikut menghadirkan:
1. **Concurrency Pool** untuk mitigasi spike throughput.
2. **Circuit Breaker** (State: Closed, Open, Half-Open) untuk mencegah overload saat downstream Core terganggu.
3. **Pluggable Architecture** dengan proteksi isolasi runtime.

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
	"sync/atomic"
	"time"
)

// --- Domain Models ---

type StandardRecord struct {
	RecordUUID string            `json:"record_uuid"`
	TenantID   string            `json:"tenant_id"`
	Payload    map[string]any    `json:"payload"`
	Checksum   string            `json:"checksum"`
	IngestedAt time.Time         `json:"ingested_at"`
}

type TransformationEngine interface {
	Transform(ctx context.Context, raw []byte) (map[string]any, error)
}

// --- Circuit Breaker Pattern Implementation ---

type CircuitState int32

const (
	StateClosed CircuitState = iota
	StateHalfOpen
	StateOpen
)

func (s CircuitState) String() string {
	switch s {
	case StateClosed:
		return "CLOSED"
	case StateHalfOpen:
		return "HALF-OPEN"
	case StateOpen:
		return "OPEN"
	default:
		return "UNKNOWN"
	}
}

type CircuitBreaker struct {
	state          int32
	failureCount   int64
	failureThreshold int64
	lastFailure    int64 // Unix nano
	cooldownNano   int64
	mu             sync.Mutex
}

func NewCircuitBreaker(threshold int64, cooldown time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		state:            int32(StateClosed),
		failureThreshold: threshold,
		cooldownNano:     cooldown.Nanoseconds(),
	}
}

func (cb *CircuitBreaker) AllowRequest() bool {
	state := CircuitState(atomic.LoadInt32(&cb.state))
	if state == StateClosed {
		return true
	}

	now := time.Now().UnixNano()
	if state == StateOpen {
		last := atomic.LoadInt64(&cb.lastFailure)
		if now-last > cb.cooldownNano {
			if atomic.CompareAndSwapInt32(&cb.state, int32(StateOpen), int32(StateHalfOpen)) {
				return true
			}
		}
		return false
	}

	// State is Half-Open: allow controlled probe
	return true
}

func (cb *CircuitBreaker) RecordSuccess() {
	atomic.StoreInt64(&cb.failureCount, 0)
	atomic.StoreInt32(&cb.state, int32(StateClosed))
}

func (cb *CircuitBreaker) RecordFailure() {
	fails := atomic.AddInt64(&cb.failureCount, 1)
	atomic.StoreInt64(&cb.lastFailure, time.Now().UnixNano())

	if fails >= cb.failureThreshold {
		atomic.StoreInt32(&cb.state, int32(StateOpen))
	}
}

// --- FDE Processing Worker Engine ---

type DynamicTransformer struct{}

func (t *DynamicTransformer) Transform(ctx context.Context, raw []byte) (map[string]any, error) {
	// Simulasi translasi skema dinamis enterprise (misal: ISO8583 / FIX ke Unified Model)
	var dynamicMap map[string]any
	if err := json.Unmarshal(raw, &dynamicMap); err != nil {
		return nil, fmt.Errorf("invalid json payload: %w", err)
	}

	normalized := make(map[string]any)
	for k, v := range dynamicMap {
		normalized["fde_norm_"+k] = v
	}
	return normalized, nil
}

type ForwardDeployAgent struct {
	tenantID       string
	transformer    TransformationEngine
	circuitBreaker *CircuitBreaker
	workerPool     chan struct{}
	egressQueue    chan *StandardRecord
	stopSignal     chan struct{}
	wg             sync.WaitGroup
}

func NewForwardDeployAgent(tenantID string, concurrency int, egressBufferSize int) *ForwardDeployAgent {
	return &ForwardDeployAgent{
		tenantID:       tenantID,
		transformer:    &DynamicTransformer{},
		circuitBreaker: NewCircuitBreaker(3, 2*time.Second),
		workerPool:     make(chan struct{}, concurrency),
		egressQueue:    make(chan *StandardRecord, egressBufferSize),
		stopSignal:     make(chan struct{}),
	}
}

func (a *ForwardDeployAgent) StartEgressDispatcher(ctx context.Context) {
	a.wg.Add(1)
	go func() {
		defer a.wg.Done()
		for {
			select {
			case <-a.stopSignal:
				return
			case <-ctx.Done():
				return
			case record, ok := <-a.egressQueue:
				if !ok {
					return
				}
				a.sendToCore(record)
			}
		}
	}()
}

func (a *ForwardDeployAgent) Ingest(ctx context.Context, rawPayload []byte) error {
	if !a.circuitBreaker.AllowRequest() {
		return errors.New("upstream circuit breaker OPEN: client agent throttling active")
	}

	select {
	case a.workerPool <- struct{}{}:
		// Slot tersedia
	case <-ctx.Done():
		return ctx.Err()
	default:
		return errors.New("worker pool saturated: backpressure triggered")
	}

	go func() {
		defer func() { <-a.workerPool }()

		transformed, err := a.transformer.Transform(ctx, rawPayload)
		if err != nil {
			a.circuitBreaker.RecordFailure()
			return
		}

		hash := sha256.Sum256(rawPayload)
		record := &StandardRecord{
			RecordUUID: hex.EncodeToString(hash[:16]),
			TenantID:   a.tenantID,
			Payload:    transformed,
			Checksum:   hex.EncodeToString(hash[:]),
			IngestedAt: time.Now().UTC(),
		}

		select {
		case a.egressQueue <- record:
			a.circuitBreaker.RecordSuccess()
		case <-time.After(100 * time.Millisecond):
			a.circuitBreaker.RecordFailure()
		}
	}()

	return nil
}

func (a *ForwardDeployAgent) sendToCore(record *StandardRecord) {
	// Simulasi pengiriman via gRPC/mTLS ke Core Platform
	fmt.Printf("[EGRESS -> CORE] Transferred Record UUID=%s for Tenant=%s (Checksum=%s)\n",
		record.RecordUUID, record.TenantID, record.Checksum[:8])
}

func (a *ForwardDeployAgent) Close() {
	close(a.stopSignal)
	close(a.egressQueue)
	a.wg.Wait()
}

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	agent := NewForwardDeployAgent("enterprise-bank-us", 4, 100)
	agent.StartEgressDispatcher(ctx)

	// Ingest sample records
	for i := 1; i <= 5; i++ {
		payload := []byte(fmt.Sprintf(`{"account_num": "acc-%d", "amount": %d.50}`, i, i*100))
		if err := agent.Ingest(ctx, payload); err != nil {
			fmt.Printf("Ingest failed: %v\n", err)
		}
	}

	time.Sleep(500 * time.Millisecond)
	agent.Close()
	fmt.Println("FDE Ingestion Subsystem Shutdown Cleanly.")
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Global Investment Bank Legacy Integration
* **Skala**: Ingesti harian 850 juta transaksi portofolio valuta asing (Forex).
* **Kendala**:
  * Infrastruktur klien berada di lingkungan *on-premises air-gapped* tanpa konektivitas internet langsung ke SaaS Core Platform.
  * Format transmisi: File COBOL EBCDIC *fixed-width* via IBM MQ.
  * Batas kepatuhan regulasi: Data PII (Personally Identifiable Information) dilarang secara legal keluar dari batas perimeter fisik perbankan.

#### Arsitektur Solusi FDE
1. **Air-Gapped Deployment Operator**:
   FDE men-deploy Helm chart custom ke Red Hat OpenShift cluster milik bank. Chart tersebut mengemas:
   * *Local Gateway Adapter*: Membaca langsung dari IBM MQ queues.
   * *Zero-Knowledge Field Redactor*: Memisahkan data PII ke HashiCorp Vault lokal bank; mengganti PII dengan *cryptographic surrogate token*.
   * *WASM-based Fixed-Width Parser*: Mengubah representasi EBCDIC menjadi Protobuf format berkecepatan tinggi tanpa overhead garbage collection runtime berlebih.
2. **Asynchronous Batched Egress**:
   Agen lokal mengenkripsi batch pesan canonical menggunakan kunci publik Core Platform (Hybrid Encryption: RSA-4096 + AES-GCM-256) dan mengirimkannya melalui proxy mTLS institusi perbankan.

#### Hasil Terukur
* **Throughput**: Stabil pada 42.000 records/detik per node agent dengan alokasi memori terkendali di bawah 512 MB.
* **Keamanan**: 100% data audit PCI-DSS & GDPR compliant; tidak ada PII plain-text yang menyentuh Core Engine.
* **Stabilitas Core Engine**: Nol perubahan pada Core Platform codebase. Seluruh logika translasi format IBM MQ diisolasi di lingkungan OpenShift bank.

---

### 9. Trade-offs

| Pendekatan Ekstensi FDE | Latency Overhead | Blast Radius (Tingkat Dampak Kerusakan) | Skalabilitas & Biaya | Kompleksitas CI/CD & Pemeliharaan |
| :--- | :--- | :--- | :--- | :--- |
| **Monolithic Code Ingestion (If/Else Branches)** | Sangat Rendah (~0 ms) | **Bencana (Catastrophic)**: Panic/bug integrasi klien mematikan engine inti untuk semua tenant. | Biaya murah di awal, *astronomical tech-debt* di akhir. | Sangat rumit; *deployment freeze* sering terjadi. |
| **Microservice Sidecar (Out-of-Process / gRPC)** | Sedang (~2-5 ms per network hop L7) | **Rendah**: Sidecar crash hanya memutus ingesti lokal tanpa memengaruhi proses lain. | Konsumsi Resource tinggi (CPU/Memori terduplikasi per instance). | Sederhana; sidecar dapat di-deploy independen via Docker. |
| **WASM In-Process Sandboxing (Wazero/Wasmtime)** | Rendah (~0.1-0.3 ms FFI Boundary) | **Sangat Rendah**: WASM crash ditangkap host engine sebagai error biasa; memori dibatasi strict limit. | **Optimal**: High concurrency dengan zero memory duplication overhead. | Menengah; membutuhkan toolchain kompilasi bytecode (Rust/TinyGo). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Common Anti-Patterns
1. **The Core Infiltration Trap**: FDE tergoda menambahkan kolom khusus klien (misal: `acme_unique_tax_id`) langsung ke skema database relational Core Engine. **Mitigasi**: Gunakan kolom generik JSONB/Protobuf Any atau Semantic Attribute Entity Model.
2. **Unbounded Concurrency di Sisi Klien**: Agen FDE menyedot pesan dari database klien secepat mungkin hingga menumbangkan read-replica DB klien. **Mitigasi**: Terapkan *adaptive rate limiting* (Token Bucket) dan monitor metrik utilisasi database upstream.
3. **Log Poisoning & Secret Leaks**: Mengaktifkan log `DEBUG` di level pod agen yang secara tidak sengaja mencetak token otentikasi enterprise atau payload rahasia klien ke agregator log bersama. **Mitigasi**: Terapkan *field-level masking filter* pada output stream logger.

#### 10.2 Troubleshooting Guide: Memory Leaks pada Persistent Edge Agent
* **Gejala**: Pod Edge Agent mengalami OOMKilled (*Exit Code 137*) secara berkala setiap 6 jam di kluster Kubernetes klien.
* **Investigasi**:
  1. Ambil pprof heap snapshot dari running container:
     ```bash
     kubectl exec -it <agent-pod> -- curl -s http://localhost:6060/debug/pprof/heap > heap.pprof
     go tool pprof -top heap.pprof
     ```
  2. Identifikasi apakah terdapat `sync.Map` atau slice yang menimbun metadata transaksi tanpa retensi berbasis waktu (*time-to-live / TTL*).
* **Solusi**: Ganti map in-memory yang tidak terbatas dengan *ring buffer* berkapasitas tetap (*bounded circular queue*) atau *cache LRU ber-TTL*.

---

### 11. Best Practices (Production Checklist)

- [ ] **Contract Versioning**: Semua payload dari ekstensi FDE wajib menyematkan schema semantic version (`X-Schema-Version: 2.1.0`).
- [ ] **Backpressure Handling**: Terapkan bounded memory queues; tolak request dengan status `HTTP 429 / gRPC ResourceExhausted` jika buffer penuh daripada membiarkan proses OOM.
- [ ] **Dead Letter Queues (DLQ)**: Setiap record yang gagal ditransformasikan tidak boleh di-drop secara diam-diam; simpan ke storage presisten terpisah untuk analisis pasca-kegagalan.
- [ ] **Stateless Engine**: Desain agen FDE agar bersifat stateless; persistensi keadaan (*state*) hanya berada di storage terdistribusi atau disk WAL sementara.
- [ ] **Zero Hardcoded Secrets**: Semua konfigurasi klien, kredensial koneksi, dan certificate harus diinjeksikan via KMS/Secrets Manager lokal (bukan hardcode di Dockerfile/ConfigMap).
- [ ] **Deterministic Resource Limits**: Terapkan CPU requests/limits dan Memory limits ketat pada deployment manifest Helm di kluster klien.
- [ ] **Heartbeat & Telemetry Pinning**: Agen lokal wajib mengirim lightweight health ping berkala ke Control Plane pusat dengan latensi toleran terhadap fluktuasi koneksi.

---

### 12. Hands-on Practice

Buat dan simpan praktikum ini di direktori project: `hands-on/m02/`

#### Langkah 1: Inisialisasi Project & Struktur File
```bash
mkdir -p hands-on/m02/{cmd,pkg/adapter,pkg/engine}
cd hands-on/m02
go mod init fde-edge-runtime
```

#### Langkah 2: Buat Implementasi Dynamic Ingestion Pipeline
Simpan kode berikut di `hands-on/m02/cmd/main.go`:
```go
package main

import (
	"encoding/json"
	"fmt"
	"log"
)

type CanonicalEvent struct {
	ID        string `json:"id"`
	EventType string `json:"event_type"`
	Value     float64 `json:"value"`
}

type LegacyClientPayload struct {
	RefNum string `json:"ref_num"`
	Code   string `json:"code"`
	Amount string `json:"amount"`
}

func parseClientData(raw []byte) (*CanonicalEvent, error) {
	var legacy LegacyClientPayload
	if err := json.Unmarshal(raw, &legacy); err != nil {
		return nil, err
	}

	var val float64
	_, err := fmt.Sscanf(legacy.Amount, "$%f", &val)
	if err != nil {
		return nil, fmt.Errorf("gagal parsing mata uang: %w", err)
	}

	return &CanonicalEvent{
		ID:        "norm-" + legacy.RefNum,
		EventType: "TRANSACTION_" + legacy.Code,
		Value:     val,
	}, nil
}

func main() {
	rawInput := []byte(`{"ref_num": "A-8823", "code": "DEBIT", "amount": "$1550.75"}`)
	event, err := parseClientData(rawInput)
	if err != nil {
		log.Fatalf("Error: %v", err)
	}

	output, _ := json.MarshalIndent(event, "", "  ")
	fmt.Println("Canonical Output:")
	fmt.Println(string(output))
}
```

#### Langkah 3: Eksekusi dan Verifikasi
```bash
go run cmd/main.go
```
*Output yang diharapkan:*
```json
Canonical Output:
{
  "id": "norm-A-8823",
  "event_type": "TRANSACTION_DEBIT",
  "value": 1550.75
}
```

---

### 13. Exercise

#### Level 1: Easy
Modifikasi kode pada *Hands-on Practice* agar mengenali format mata uang Rupiah (`Rp 1500000.00`) selain Dollar (`$1550.75`), lalu konversi string tersebut ke float secara presisi.

#### Level 2: Medium
Bangun sistem validasi middleware berbasis Go channels yang menampung hingga 1.000 transaksi/detik dari 3 klien berbeda. Jika salah satu klien mengirim payload rusak, proses validasi untuk 2 klien lainnya tidak boleh terhenti (*goroutine error containment*).

#### Level 3: Hard
Buat implementasi *Write-Ahead-Log (WAL)* sederhana berbasis append-only file di disk lokal. Setiap payload yang diterima agent harus ditulis ke disk terlebih dahulu sebelum dimasukkan ke memory queue. Buat prosedur recovery: jika agent di-*kill* secara paksa (`SIGKILL`) dan di-restart, sistem membaca ulang disk log dan mengirimkan sisa data yang belum tersinkronisasi tanpa duplikasi (*idempotency key based on SHA256*).

---

### 14. Challenge

**Skenario**: Klien Anda adalah Lembaga Penjamin Simpanan yang beroperasi di dalam jaringan terisolasi (*air-gapped zero-trust network*) dengan regulasi keamanan ketat:
* Tidak diperbolehkan membuka port ingress sama sekali (semua komunikasi harus via egress-only polling atau reverse tunnel).
* Skema data transaksi dari 12 bank anggota mengalami *schema drift* tanpa pemberitahuan sebelumnya (kolom dapat berganti nama, tipe data integer dapat berubah menjadi string acak sewaktu-waktu).
* Batas penggunaan resource CPU: Maksimal 1.5 core dan RAM 1 GB.

**Tugas Arsitektur**:
Rancang dokumen spesifikasi teknis dan diagram alur terperinci yang mencakup:
1. Protokol konektivitas reverse-egress untuk transmisi data menuju Cloud Core Platform tanpa melanggar firewall zero-trust.
2. Mekanisme penanganan *schema drift* adaptif berbasis AI/Heuristics yang mendeteksi anomali skema, mengalihkan data yang rusak ke *Isolated Quarantined Bucket*, dan memberi tahu FDE tanpa menghentikan jalur pemrosesan data bank anggota yang lain.
3. Strategi kompresi dan batching adaptif untuk meminimalkan beban bandwidth pada koneksi satelit intermiten (*intermittent satellite link*).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara Forward-Deployed Engineer (FDE) dan Integration Engineer konvensional?**
   * *Jawaban*: FDE mengombinasikan rekayasa sistem tingkat lanjut, arsitektur, dan iterasi produk langsung di lapangan; membangun solusi yang modular dan dapat digunakan kembali (*reusable platform components*), bukan sekadar menulis script integrasi lem (*glue code*) sekali pakai.
2. **Mengapa branching codebase per klien dianggap sebagai anti-pattern fatal dalam arsitektur enterprise?**
   * *Jawaban*: Menyebabkan fragmentasi basis kode, konflik merge yang masif saat update platform inti, melipatgandakan beban pengujian CI/CD, dan menghalangi peluncuran patch keamanan universal.
3. **Apa peran Write-Ahead Logging (WAL) pada deployment Edge Agent?**
   * *Jawaban*: Mencegah hilangnya data (*data loss*) jika terjadi kegagalan sistem (*crash/power cut*) sebelum payload di-flush ke pipeline downstream atau storage pusat.
4. **Apa yang dimaksud dengan Circuit Breaker dalam konteks integrasi client-to-core?**
   * *Jawaban*: Mekanisme keamanan yang memutus sementara aliran request ke sistem target jika kegagalan melebihi ambang batas, mencegah fenomena *cascading failure* dan konsumsi resource sia-sia.
5. **Sebutkan tujuan utama penerapan Ports and Adapters (Arsitektur Heksagonal) bagi FDE!**
   * *Jawaban*: Mengisolasi domain bisnis inti dari ketergantungan teknologi eksternal (protokol jaringan, database pihak ketiga, library legacy klien).

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Kapan seorang FDE sebaiknya memilih WebAssembly (WASM) dibandingkan gRPC Sidecar untuk runtime plugin klien?**
   * *Jawaban*: Saat latensi FFI sangat kritis (<1 ms), kebutuhan efisiensi memori tinggi (ratusan tenant di satu pod), dan lingkungan tidak mengizinkan banyak proses independen berjalan.
7. **Bagaimana cara mencegah Backpressure merusak stabilitas container agent di sisi klien?**
   * *Jawaban*: Menggunakan *bounded buffers*, menerapkan kebijakan penolakan request (*fail-fast* / HTTP 429), dan menyerap lonjakan data ke persistent storage (disk-backed spooling).
8. **Mengapa idempotency key mutlak dibutuhkan saat mentransfer data dari edge klien ke core engine?**
   * *Jawaban*: Karena kegagalan jaringan pada level egress dapat memicu mekanisme transmisi ulang (*retry*), yang tanpa idempotensi akan mengakibatkan duplikasi data di Core Platform.
9. **Bagaimana pendekatan Zero-Knowledge Architecture melindungi PII di lingkungan FDE?**
   * *Jawaban*: Data sensitif ditokenisasi atau dienkripsi menggunakan kunci yang hanya dimiliki oleh klien sebelum payload meninggalkan batas perimeter infrastruktur klien.
10. **Apa implikasi performa dari dynamic JSON reflection parsing pada Go di pipeline ber-throughput tinggi?**
    * *Jawaban*: Menghasilkan alokasi heap memori yang tinggi, meningkatkan beban Garbage Collection (GC pauses), dan menurunkan throughput sistem secara signifikan dibanding schema-compiled parsers (Protobuf/FlatBuffers).

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario A**: Edge Agent Anda di klien mengirimkan data duplikat ke Core Platform setiap kali jaringan satelit klien mengalami flapping (putus-nyambung tiap 30 detik). Komponen apa yang gagal dan bagaimana solusinya?
    * *Jawaban*: Egress pipeline menggunakan semantik pengiriman *at-least-once* tanpa verifikasi ACK transaksional dan Core Platform tidak menerapkan idempotency checking. Solusinya: Implementasikan *distributed deduplication filter* berbasis Content-Addressed Hashing (SHA256) pada Core Gateway dan buat edge agent melacak acknowledgment per batch.
12. **Skenario B**: Kluster Kubernetes klien memberlakukan kebijakan *read-only root filesystem* yang ketat. Agen WAL Anda gagal melakukan inisialisasi dan crash-looping. Bagaimana merancang solusinya?
    * *Jawaban*: Agen mencoba menulis log ke root filesystem. Pasang volume khusus yang diizinkan untuk penulisan melalui `emptyDir` (berbasis RAM/in-memory) atau `PersistentVolumeClaim` (PVC) terenkripsi, lalu arahkan path WAL agen secara eksplisit ke mount path tersebut.
13. **Skenario C**: Salah satu transformasi data klien memicu infinite loop pada CPU thread agent Anda karena parsing string reguler ekspresi (ReDoS) yang kompleks. Bagaimana mengisolasi kegagalan ini?
    * *Jawaban*: Pindahkan eksekusi transformasi ke dalam runtime sandboxed yang mendukung batas eksekusi ketat berbasis resource fuel/instruction count (seperti WASM fuel consumption) atau jalankan engine transformasi dengan `context.WithTimeout` pada worker pool terisolasi.

---

### 16. Summary

1. Arsitektur Forward-Deployed Engineering yang efektif menuntut **pemisahan mutlak** antara *Core Platform Engine* yang deterministik dan *Adaptation Layer* yang fleksibel.
2. Mencegah *codebase forking* adalah hukum tertinggi dalam FDE; semua ragam keunikan sistem klien harus dijembatani melalui arsitektur modular (*Hexagonal, WASM, Sidecar, atau Dynamic Metadata Mediation*).
3. Runtime lingkungan klien enterprise sering kali memiliki keterbatasan jaringan (*air-gapped*), beban kepatuhan tinggi (*PII segregation*), dan sistem warisan (*legacy feeds*). Oleh karena itu, ketahanan sistem (*resilience*) melalui WAL, Circuit Breaking, Backpressure handling, dan Resource Sandboxing wajib diterapkan sebagai standar produksi enterprise.