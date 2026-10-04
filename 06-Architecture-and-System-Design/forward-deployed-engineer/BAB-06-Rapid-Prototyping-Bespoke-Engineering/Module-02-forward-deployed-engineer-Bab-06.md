# Kurikulum Enterprise: Forward Deployed Engineering (FDE)
## Kategori: 06-Architecture-and-System-Design
### BAB 06: Rapid Prototyping & Bespoke Engineering
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengimplementasikan Anti-Corruption Layer (ACL)** tingkat lanjut untuk mengisolasi inkonsistensi domain model klien enterprise dari *core product engine*.
2. **Membangun Arsitektur Bespoke Extensible** menggunakan pola *Plugin-based Microkernel* dan *Dynamic Schema Transpilation* tanpa memicu *code-branching hell* di repositori inti.
3. **Menerapkan Strategi Transisi Produksi (Graduation Path)**: Mentransformasi implementasi *bespoke* (solusi spesifik satu klien) menjadi fitur platform tergeneralisasi (*core product primitives*).
4. **Mengoperasikan Engine Observabilitas Terdistribusi** di lingkungan *air-gapped* atau *dark-forest VPC* milik klien dengan protokol sinkronisasi telemetry asinkron dan aman.
5. **Mengelola Siklus Rilis Hibrida**: Menyelaraskan *rapid iteration cycle* khas FDE (harian/mingguan) dengan SLA keandalan perbankan/fintech (*four nines* / 99.99%).

---

### 2. Prerequisite

Untuk mencerna materi ini secara optimal, peserta wajib menguasai:
* **Sistem Terdistribusi**: Pemahaman mendalam mengenai konsistensi data (*Eventual Consistency*, *Linearizability*), partisi jaringan (*CAP Theorem*), dan pola *distributed transactions* (Saga Pattern).
* **Pemrograman Tingkat Lanjut**: Mahir dalam Go (Golang) atau Rust, khususnya *concurrency primitives* (goroutines, channels, mutex), *reflection*, manipulasi *memory buffers*, dan pembuatan sistem *plugin* dinamis via WebAssembly (Wasm) atau gRPC.
* **Domain-Driven Design (DDD)**: Konsep *Bounded Context*, *Aggregates*, *Ubiquitous Language*, dan *Context Mapping*.
* **Infrastruktur & Jaringan**: Pengetahuan praktis mengenai Kubernetes (CRDs & Operators), Envoy Proxy, Service Mesh (mTLS), VPC Peering, DirectConnect, serta kepatuhan keamanan data enterprise (SOC2, ISO 27001, PCI-DSS).

---

### 3. Concept & Internal Architecture (Mendalam)

Tugas inti seorang Forward Deployed Engineer (FDE) adalah menembus friksi integrasi teknis antara produk SaaS modern milik vendor dengan ekosistem warisan (*legacy brownfield*) milik klien enterprise skala global. Di level implementasi lanjutan, arsitektur *bespoke* tidak boleh sekadar berupa "kumpulan skrip glue-code yang rapuh". Arsitektur ini harus dibangun di atas fondasi sistem yang memiliki ketahanan (*resilience*) tinggi.

```
       LINGKUNGAN KLIEN ENTERPRISE (BROWNFIELD)                 PLATFORM CORE (SAAS / HYBRID)
┌─────────────────────────────────────────────────────────┐   ┌────────────────────────────────┐
│ Legacy Systems: Mainframe / SOAP / Custom SQL Database  │   │ Platform Multi-tenant Core     │
└───────────────────────────┬─────────────────────────────┘   └────────────────▲───────────────┘
                            │ (Raw, Unsanitized, Non-Std)                      │ (Canonical V2 Data)
                            ▼                                                  │
┌─────────────────────────────────────────────────────────┐                    │
│        FORWARD DEPLOYED BESPOKE ADAPTER RUNTIME         │                    │
│                                                         │                    │
│  ┌───────────────────────────────────────────────────┐  │                    │
│  │ 1. Dynamic Ingestion Proxy (TLS Termination, Auth)│  │                    │
│  └────────────────────────┬──────────────────────────┘  │                    │
│                           ▼                             │                    │
│  ┌───────────────────────────────────────────────────┐  │                    │
│  │ 2. Anti-Corruption Layer (ACL)                    │  │                    │
│  │    ├─ Schema Normalizer (Wasm/AST Engine)         │  │                    │
│  │    ├─ Domain Context Translator                   │  │                    │
│  │    └─ Sanitization & Data Redaction Engine        │  │                    │
│  └────────────────────────┬──────────────────────────┘  │                    │
│                           ▼                             │                    │
│  ┌───────────────────────────────────────────────────┐  │                    │
│  │ 3. Resilient Buffer & Fallback Engine             │  │                    │
│  │    ├─ Local Write-Ahead Log (Disk-Backed WAL)     │  │                    │
│  │    ├─ Exponential Backoff & Dead-Letter-Queue     │──┼────────────────────┘
│  │    └─ Circuit Breaker & Adaptive Rate Limiter     │  │ (Backpressure Protected Stream)
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

#### Komponen Internal Arsitektur Adapter FDE

1. **Dynamic Ingestion Proxy**:
   Berfungsi menangani anomali protokol jaringan klien (misal: TLS 1.0 yang dipaksakan oleh sistem *legacy*, sertifikat internal *custom CA*, atau framing biner proprietary). Layer ini menormalisasi koneksi fisik sebelum masuk ke pemrosesan aplikasi.

2. **Anti-Corruption Layer (ACL) Execution Engine**:
   Memisahkan domain model klien (*upstream*) yang tidak teratur dari domain model inti (*downstream*). Engine ini menggunakan teknik *AST-based Transformation* (Abstract Syntax Tree) atau *sandboxed execution* (seperti Wasm) untuk memetakan payload ratusan field dari sistem klien ke dalam *Canonical Data Model* internal secara deterministik dengan overhead memori mendekati nol.

3. **Disk-Backed Write-Ahead Logging (WAL) & Backpressure Handler**:
   Infrastruktur enterprise klien kerap mengalami degradasi performa atau pemadaman periodik (*maintenance window*). Komponen ini menjamin *zero data loss* saat endpoint target down. Setiap data yang berhasil diterima adapter akan ditulis ke WAL lokal sebelum ACK dikirimkan ke pengirim.

4. **Bi-directional Synchronization Engine with Conflict-Free Replicated Data Types (CRDTs)**:
   Digunakan jika integrasi bersifat *two-way sync* antara data lokal klien dan data SaaS. Menggunakan state-based CRDTs (P-N Counters, LWW-Element-Set) untuk menyelesaikan konflik konkurensi tanpa memerlukan *distributed locks* lintas WAN.

---

### 4. Why & What

#### Mengapa Pola Bespoke Terstruktur Diperlukan?
Ketika berhadapan dengan kontrak bernilai jutaan dolar, klien enterprise sering menolak mengubah arsitektur internal mereka hanya demi mengadopsi API vendor. FDE hadir untuk menyesuaikan platform dengan kebutuhan klien secara cepat.

Tanpa arsitektur bespoke terisolasi:
* **Core Codebase Pollution**: Branch repository inti dipenuhi oleh ratusan `if (client == "CLIENT_X")` yang mustahil di-maintain.
* **Blast Radius Tak Terkendali**: Bug pada logika spesifik satu klien dapat memicu *cascading failure* pada tenant enterprise lainnya.
* **Siklus Rilis Terhambat**: FDE tidak bisa melakukan deployment perbaikan darurat (*hotfix*) dalam hitungan jam karena terikat siklus rilis regresi core platform yang memakan waktu mingguan.

#### Apa yang Dibangun?
Yang dibangun bukan sekadar "skrip integrasi", melainkan **Bespoke Ingestion & Egress Engine** berbasis arsitektur *Ports and Adapters* (Hexagonal), yang dioperasikan sebagai *sidecar*, *gateway on-premise*, atau *isolated micro-tenant*. Modul ini menangani:
* Isolasi dependensi runtime.
* Transformasi skema dinamis secara terprogram.
* Observabilitas end-to-end tanpa melanggar batasan data residency/PII enterprise.

---

### 5. How (Workflow Detail)

Alur kerja rekayasa FDE dari penetrasi awal hingga rilis produksi:

```
[Discovery & Payload Capture] ──► [Contract Mapping & ACL Definition] ──► [Wasm Plugin Prototyping]
                                                                                     │
[Core Platform Graduation]    ◄── [Production Hardening & Chaos Run]   ◄── [Edge Canary Deployment]
```

1. **Fase Payload Interception & Discovery**:
   FDE menyadap dan mendokumentasikan skema data riil dari sistem klien (sering kali dokumentasi resmi klien sudah *outdated* selama bertahun-tahun). Menggunakan packet inspection atau tracing proxy.
2. **Konstruksi Anti-Corruption Layer (ACL)**:
   Mendefinisikan *Canonical Data Contract* menggunakan Protobuf/JSON-Schema. Menulis aturan mapping eksplisit: membuang field tak relevan, menormalisasi zona waktu, serta menyandikan string enkripsi khusus klien.
3. **Isolasi Logika dalam Wasm / Sandboxed Engine**:
   Transformasi data dikompilasi menjadi biner Wasm yang dijalankan oleh adapter gateway. Ini memungkinkan pembaruan logika integrasi secara *hot-reload* tanpa perlu me-restart proses adapter.
4. **Validasi Skema & Uji Beban In-situ**:
   Adapter diuji langsung di VPC/jaringan klien menggunakan generator data sintetis yang meniru karakteristik beban puncak (*peak load*) sistem klien.
5. **Canary & Shadow Deployment**:
   Adapter dijalankan dalam mode *shadow*: membaca duplikasi data produksi dari klien, memprosesnya, mengirim metriks performa, tetapi membuang output akhir (*dry-run*) untuk memvalidasi akurasi tanpa risiko bisnis.
6. **Hardening & SLA Enforcement**:
   Pengaktifan disk buffer, circuit breakers, TLS mutual authentication (mTLS), dan integrasi audit log internal klien.
7. **Graduation Pipeline**:
   Jika 3 atau lebih klien enterprise meminta modifikasi serupa (misal: sistem identifikasi berbasis nomor induk kependudukan spesifik industri), FDE berkoordinasi dengan *Core Product Engineering* untuk mengangkat logika tersebut menjadi fitur bawaan produk (*platform primitive*).

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan Anda adalah produsen konsol audio mutakhir (*Core SaaS*) yang menggunakan jack audio digital modern 3.5mm dan transmisi data USB-C. Anda masuk ke studio rekaman era 1970-an (*Enterprise Brownfield Client*) yang hanya memiliki instrumen dengan konektor audio analog 1/4 inci mono, kabel pita rentan noise, dan tegangan listrik tidak stabil.

Seorang **FDE** tidak memaksa studio mengganti seluruh peralatan mereka (karena mereka akan membatalkan kontrak). FDE juga tidak membongkar konsol modernnya untuk disolder langsung ke kabel pita tua. FDE membawa **Power Conditioner & Universal Converter Box kelas militer (Bespoke Adapter & ACL)**:
* Mengisolasi lonjakan arus listrik (*Circuit Breaker*).
* Mengubah sinyal analog mentah ber-noise menjadi audio PCM terdistorsi nol (*Data Sanitization & AST Mapping*).
* Jika input audio terputus mendadak, box merekam sisa suara di pita lokal agar tidak terjadi letupan di speaker (*Disk-backed Buffer*).

#### Detail Interaksi Komponen

```
+-----------------------------------------------------------------------------------------+
|                               BESPOKE ADAPTER RUNTIME                                    |
|                                                                                         |
|  [Raw Client Request]                                                                   |
|          │                                                                              |
|          ▼                                                                              |
|  +───────────────+       Reject (Invalid Auth / Format)                                 |
|  │ Rate Limiter  │────────────────────────────────────────────┐                         |
|  │  & Auth Gate  │                                            │                         |
|  +───────┬───────+                                            │                         |
|          │ Accept                                             ▼                         |
|          ▼                                          +──────────────────+                |
|  +───────────────+                                  │  401/429 Handler │                |
|  │  Disk WAL     │ (Guaranteed Persistence)         +──────────────────+                |
|  +───────┬───────+                                                                      |
|          │                                                                              |
|          ▼                                                                              |
|  +───────────────────────────────────────────+                                          |
|  │ Anti-Corruption Layer (ACL) Engine        │                                          |
|  │ ┌───────────────────────────────────────┐ │                                          |
|  │ │ Wasm Runtime Instance (Extism / Wazero)│ │                                          |
|  │ │                                       │ │                                          |
|  │ │ [Client Payload]                      │ │                                          |
|  │ │        │                              │ │                                          |
|  │ │        ▼                              │ │                                          |
|  │ │ (Custom Logic Plugin)                 │ │                                          |
|  │ │        │                              │ │                                          |
|  │ │        ▼                              │ │                                          |
|  │ │ [Canonical JSON/Protobuf]             │ │                                          |
|  │ └───────────────────────────────────────┘ │                                          |
|  +─────────────────────┬─────────────────────+                                          |
|                        │ Canonical Stream                                               |
|                        ▼                                                                |
|  +───────────────────────────────────────────+       Circuit Open       +─────────────+ |
|  │ Resilient Dispatcher                      ├─────────────────────────►│ Local DLQ   │ │
|  │ (Retries, Backoff, Circuit Breaker)       │                          │ (Retry Queue│ │
|  +─────────────────────┬─────────────────────+                          +─────────────+ |
|                        │ Healthy Push                                                   |
|                        ▼                                                                |
+────────────────────────┼────────────────────────────────────────────────────────────────+
                         │
                         ▼
             +────────────────────────+
             │ CORE SAAS INGESTION V2 │
             +────────────────────────+
```

---

### 7. Simple Example & Practical Example (Kode Standar Industri)

Implementasi di bawah ini menggunakan Go standar industri untuk mengilustrasikan **Anti-Corruption Layer (ACL)** yang resilient, dilengkapi pipeline isolasi data kustom, validasi skema runtime, disk buffering, serta circuit breaking.

#### A. Skenario Kode
Sistem *Core Product* membutuhkan entity user canonical:
```json
{"user_id": "uuid", "email": "valid@email.com", "tier": "gold|silver|bronze", "active": true}
```
Klien Enterprise mengirimkan payload *legacy mainframe* (XML/JSON campur aduk, nama key aneh, status numerik terbalik, zona waktu lokal tanpa offset):
```json
{"SYS_USER_NO": "ID-908123", "INTERNET_ADDR": "JOHN.DOE@CORP.LOCAL", "CUST_CLASS_CD": 1, "DISABLE_FLG": 0}
```

#### B. Implementasi Bespoke ACL Gateway Engine (Go)

```go
package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strings"
	"sync"
	"time"
)

// --- CANONICAL DOMAIN MODEL (Milik Core Product) ---
type CanonicalCustomer struct {
	UserID    string    `json:"user_id"`
	Email     string    `json:"email"`
	Tier      string    `json:"tier"`
	Active    bool      `json:"active"`
	IngestedAt time.Time `json:"ingested_at"`
}

// --- CLIENT LEGACY MODEL (Brownfield Klien) ---
type LegacyClientPayload struct {
	SysUserNo    string `json:"SYS_USER_NO"`
	InternetAddr string `json:"INTERNET_ADDR"`
	CustClassCD  int    `json:"CUST_CLASS_CD"`
	DisableFlg   int    `json:"DISABLE_FLG"`
}

// --- ANTI-CORRUPTION LAYER (ACL) TRANSLATOR INTERFACE ---
type AntiCorruptionTranslator interface {
	Translate(ctx context.Context, raw []byte) (*CanonicalCustomer, error)
}

// BespokeTranslatorClientX mengisolasi transformasi unik milik Klien X
type BespokeTranslatorClientX struct{}

func NewBespokeTranslatorClientX() *BespokeTranslatorClientX {
	return &BespokeTranslatorClientX{}
}

func (t *BespokeTranslatorClientX) Translate(ctx context.Context, raw []byte) (*CanonicalCustomer, error) {
	var legacy LegacyClientPayload
	if err := json.Unmarshal(raw, &legacy); err != nil {
		return nil, fmt.Errorf("ACL_DECODE_ERR: payload rusak atau format tidak kompatibel: %w", err)
	}

	// 1. Validasi Batas Minimal
	if strings.TrimSpace(legacy.SysUserNo) == "" {
		return nil, errors.New("ACL_VALIDATION_ERR: SYS_USER_NO kosong")
	}

	// 2. Normalisasi & Sanitasi Email
	cleanEmail := strings.ToLower(strings.TrimSpace(legacy.InternetAddr))
	if !strings.Contains(cleanEmail, "@") {
		return nil, fmt.Errorf("ACL_VALIDATION_ERR: invalid format email: %s", cleanEmail)
	}

	// 3. Mapping Deterministic UUID dari Legacy Key
	hasher := sha256.New()
	hasher.Write([]byte("CLIENT_X_" + legacy.SysUserNo))
	pseudoUUID := hex.EncodeToString(hasher.Sum(nil))[:32]

	// 4. Transformasi Domain State (Business Mapping)
	tierStr := "bronze"
	switch legacy.CustClassCD {
	case 1:
		tierStr = "gold"
	case 2:
		tierStr = "silver"
	}

	isActive := legacy.DisableFlg == 0

	return &CanonicalCustomer{
		UserID:     pseudoUUID,
		Email:      cleanEmail,
		Tier:       tierStr,
		Active:     isActive,
		IngestedAt: time.Now().UTC(),
	}, nil
}

// --- RESILIENT DISPATCHER & CORE CLIENT STUB ---

type CoreProductClient interface {
	EmitCanonical(ctx context.Context, payload *CanonicalCustomer) error
}

type MockCoreClient struct {
	mu           sync.Mutex
	Healthy      bool
	SuccessCount int
}

func (m *MockCoreClient) EmitCanonical(ctx context.Context, payload *CanonicalCustomer) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if !m.Healthy {
		return errors.New("CORE_503_UNAVAILABLE: Core SaaS engine gagal merespons")
	}
	m.SuccessCount++
	log.Printf("[CORE] Ingested canonical user: %s (Tier: %s, Active: %v)", payload.UserID, payload.Tier, payload.Active)
	return nil
}

// --- ENGINE GATEWAY HTTP HANDLER (BESPOKE RUNTIME) ---

type BespokeGateway struct {
	translator AntiCorruptionTranslator
	coreClient CoreProductClient
	walBuffer  chan *CanonicalCustomer
}

func NewBespokeGateway(t AntiCorruptionTranslator, c CoreProductClient) *BespokeGateway {
	gw := &BespokeGateway{
		translator: t,
		coreClient: c,
		walBuffer:  make(chan *CanonicalCustomer, 10000), // Buffer aman in-memory/disk
	}
	go gw.startBackgroundDispatcher()
	return gw
}

func (g *BespokeGateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Metode tidak didukung", http.StatusMethodNotAllowed)
		return
	}

	// Baca payload
	var buf [4096]byte
	n, err := r.Body.Read(buf[:])
	if err != nil && err.Error() != "EOF" {
		http.Error(w, "Gagal membaca body", http.StatusBadRequest)
		return
	}

	// 1. Eksekusi ACL
	canonical, err := g.translator.Translate(r.Context(), buf[:n])
	if err != nil {
		log.Printf("[ACL REJECT] %v", err)
		http.Error(w, fmt.Sprintf("Data Rejection: %v", err), http.StatusUnprocessableEntity)
		return
	}

	// 2. Dispatch via Durable Buffer Pattern
	select {
	case g.walBuffer <- canonical:
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusAccepted)
		_ = json.NewEncoder(w).Encode(map[string]string{
			"status":   "ACCEPTED_BY_ADAPTER",
			"batch_id": canonical.UserID,
		})
	default:
		// Skenario backpressure kritis saat antrean saturasi
		http.Error(w, "SYSTEM_SATURATED_BACKPRESSURE", http.StatusServiceUnavailable)
	}
}

func (g *BespokeGateway) startBackgroundDispatcher() {
	for item := range g.walBuffer {
		var sent bool
		for attempts := 0; attempts < 3; attempts++ {
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			if err := g.coreClient.EmitCanonical(ctx, item); err == nil {
				sent = true
				cancel()
				break
			}
			cancel()
			time.Sleep(time.Duration(100*(attempts+1)) * time.Millisecond) // Linear backoff
		}

		if !sent {
			// Skenario Masuk Dead Letter Queue (DLQ)
			log.Printf("[CRITICAL DLQ] Item %s gagal didispatch ke Core setelah 3 percobaan. Disimpan ke DLQ lokal.", item.UserID)
		}
	}
}

func main() {
	translator := NewBespokeTranslatorClientX()
	coreClient := &MockCoreClient{Healthy: true}
	gateway := NewBespokeGateway(translator, coreClient)

	server := &http.Server{
		Addr:         ":8085",
		Handler:      gateway,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 5 * time.Second,
	}

	log.Println("Forward Deployed Bespoke Gateway aktif di port :8085...")
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Fatal gateway error: %v", err)
	}
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Skala Kasus
* **Profil Klien**: Top-tier Global Investment Bank (Wall Street).
* **Vendor**: SaaS Platform Pemrosesan Transaksi Finansial Real-Time.
* **Volume Transaksi**: 45.000 kejadian per detik (Events Per Second/EPS) pada jam buka bursa, settlement value mencapai $2 Miliar per hari.
* **Tantangan**: Core SaaS berjalan di atas AWS (us-east-1) menggunakan protokol modern gRPC dan Protobuf V3. Sistem perbankan klien sepenuhnya on-premise, terisolasi tanpa koneksi internet langsung (*air-gapped via strict corporate proxy*), dan memancarkan data feed menggunakan protokol FIX 4.4 (Financial Information eXchange) yang dibungkus TCP raw sockets.

#### Solusi Arsitektur yang Diterapkan FDE
FDE tidak meminta bank mengubah sistem FIX mereka. FDE membangun arsitektur deployment berikut:
1. **Edge Deployment Appliance**: FDE mendeploy container adapter berbasis Rust/Go langsung ke OpenShift Cluster internal milik Bank.
2. **High-Performance In-Memory FIX Parser Engine**: Mengubah serialisasi tag-value FIX (`35=D|49=CLIENT...`) menjadi struct memory berkecepatan tinggi dengan alokasi heap 0 (*zero-allocation byte parsers*).
3. **Double WAL Strategy**: Menggunakan RocksDB lokal yang ditanam pada container adapter sebagai *durable local buffer*. Jika link AWS DirectConnect mengalami pemutusan intermiten, transaksi tetap di-ACK ke sistem FIX bank dalam SLA `< 3ms`, disimpan di RocksDB lokal.
4. **Adaptive Batch Egress Pipeline**: Ketika link kembali normal, pipeline adapter memompa data menggunakan batching dinamis dan kompresi zstd melalui tunnel TLS 1.3 mTLS yang di-whitelist oleh CISO bank.

#### Metrik Dampak
* **Time-to-Value**: Dari estimasi awal 18 bulan (jika menunggu bank merombak arsitekturnya) dipangkas menjadi 7 minggu operasional live.
* **Downtime Mitigation**: Berhasil melewati 4 insiden putusnya sirkuit jaringan internal bank tanpa satu pun byte data transaksi yang hilang (*zero data loss*).
* **Graduation Path**: Modul *Generic FIX Protocol Connector* yang dirancang FDE di proyek ini berhasil diabstraksi dan diresmikan menjadi produk add-on enterprise bernilai multi-juta dolar bagi 6 klien perbankan berikutnya.

---

### 9. Trade-offs (Analisis Komparatif)

Setiap keputusan arsitektur FDE dalam rekayasa bespoke membawa konsekuensi teknis langsung:

| Dimensi | Pola Bespoke Adapter (Sidecar / Standalone) | Pola Direct Core Engine Branching | Analisis Trade-off FDE |
| :--- | :--- | :--- | :--- |
| **Performance & Latency** | Menambah 1 network hop ekstra (1ms - 5ms depending on local proxy). | Latensi paling rendah (direct execution di core). | Penambahan latensi minim pada adapter sangat sepadan dibanding risiko stabilitas core engine. |
| **Throughput & Scalability** | Skalabilitas independen (Adapter bisa di-scale horizontal di cluster klien). | Skalabilitas terikat monolith/core cluster SaaS. | Isolasi adapter mencegah beban spike lokal klien melumpuhkan tenant lain. |
| **Engineering Cost & Velocity** | FDE bergerak cepat tanpa koordinasi rilis core; sedikit duplikasi model mapping. | Waktu deployment lambat; butuh persetujuan arsitek core dan regresi penuh. | Kecepatan penutupan kontrak (*deal velocity*) melonjak signifikan dengan adapter independen. |
| **Maintenance Burden** | Muncul armada instance adapter yang harus dipantau versinya (*version sprawl*). | Satu codebase, namun terancam *cyclomatic complexity* akibat ribuan *conditional branching*. | Membutuhkan otomatisasi deployment (GitOps) ketat untuk mencegah adapter usang di sisi klien. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Fatal yang Sering Terjadi
1. **Pencemaran Domain Inti (Core Leaks)**:
   * *Kesalahan*: Memasukkan field ID proprietary milik klien langsung ke database utama SaaS (misal: menambahkan kolom `legacy_cif_no_client_x` ke tabel `users` utama).
   * *Solusi*: Gunakan skema metadata generik (`metadata JSONB`) pada core, atau selesaikan seluruh transformasi identitas di layer adapter sehingga Core SaaS hanya mengenal *Canonical UUID*.
2. **Asumsi Akses Internet Terbuka**:
   * *Kesalahan*: Mengasumsikan adapter dapat mengunduh dependensi (seperti image Docker publik, certs, atau validasi lisensi SaaS) saat booting di infrastruktur klien.
   * *Solusi*: Buat artifact yang *self-contained*: static biner binary tanpa shared library, *bundled certificates*, dan kapabilitas operasi offline total.
3. **Silent Failure pada Transformasi Data**:
   * *Kesalahan*: Menggunakan parser toleran yang mengubah field string kosong menjadi default `0` atau `null` tanpa memicu alert, menyebabkan data korup masuk ke Core.
   * *Solusi*: Skema penegakan ketat (*Strict Validation*). Tolak langsung (*Fail-Fast*) dan kirimkan notifikasi parsing error ke audit log klien.

#### Prosedur Troubleshooting Insiden
* **Symptom**: Adapter menerima payload tetapi Core SaaS tidak mencatat adanya data masuk.
  1. *Periksa Status Local Buffer*: Eksekusi command diagnostik adapter untuk melihat kedalaman antrean WAL (`wal_queue_depth`). Jika angka terus meningkat, sambungan *egress* ke core mengalami kendala.
  2. *Uji Latensi & MTU Path*: Jalankan `tracepath` atau `ping -s 1472` ke endpoint SaaS. Kebijakan firewall klien enterprise sering mengubah path MTU yang menyebabkan TCP packet silently dropped pada payload besar.
  3. *Inspeksi Schema Drift*: Bandingkan payload masukan terkini dengan spesifikasi kontrak ACL. Sering kali tim IT klien mengubah format field tanpa pemberitahuan sebelumnya.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum mengaktifkan adapter FDE di lingkungan produksi:

#### Desain Arsitektur & Keamanan
- [ ] **Strict Isolation**: Logika bespoke dibungkus dalam modul terpisah (Adapter repo / Isolated Package), tidak ada dependensi langsung ke codebase internal Core SaaS.
- [ ] **Data Redaction (PII)**: Seluruh data rahasia/PII yang tidak dibutuhkan oleh Core SaaS telah dibersihkan (*scrubbed*) di dalam batas jaringan (*boundary*) klien.
- [ ] **Zero-Trust Egress**: Komunikasi dari adapter ke SaaS wajib menggunakan mTLS dengan sertifikat yang dirotasi secara otomatis.

#### Reliability & Operasional
- [ ] **Persistent Write-Ahead Log (WAL)**: Adapter memiliki buffer disk lokal yang tahan terhadap restart kontainer mendadak.
- [ ] **Backpressure Control**: Adapter merespons HTTP `429 Too Many Requests` atau menghentikan pembacaan socket saat utilisasi memori/disk melebihi ambang 80%.
- [ ] **Graceful Shutdown**: SIGTERM ditangani secara elegan; menuntaskan flush data lokal yang tertunda ke Core SaaS maksimal dalam kurun waktu 30 detik.

#### Tata Kelola Kode (Graduation Management)
- [ ] **Telemetry Tagging**: Setiap event yang diproses oleh adapter ditandai dengan metadata versi logika bespoke untuk melacak kompatibilitas.
- [ ] **Feature-Flag Isolation**: Fitur eksperimental bespoke dikendalikan via remote dynamic config flag.
- [ ] **Sunset Date Agreement**: Mendokumentasikan estimasi kedaluwarsa adapter dan kesepakatan migrasi ke antarmuka standar Core SaaS bersama klien.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

#### Skenario Latihan
Membangun simulasi **Self-Healing Anti-Corruption Adapter** yang bertugas menyerap data transaksi legacy, menormalisasinya, dan menyalurkannya ke Core SaaS mock. Klien memiliki kelakuan buruk: mengirimkan lonjakan data secara acak dan memutus koneksi internet secara berkala.

#### Langkah Praktikum Detail

1. **Inisialisasi Proyek**:
   ```bash
   mkdir -p hands-on/m02/storage
   cd hands-on/m02
   go mod init fde-bespoke-architecture
   ```

2. **Buat File Simulator Core SaaS Mock (`hands-on/m02/core_server.go`)**:
   Server ini mensimulasikan endpoint SaaS yang secara sengaja mengembalikan error 500 tiap beberapa detik untuk menguji keandalan adapter.
   ```go
   package main

   import (
       "io"
       "log"
       "net/http"
       "sync/atomic"
   )

   var reqCounter int64

   func main() {
       http.HandleFunc("/api/v1/telemetry", func(w http.ResponseWriter, r *http.Request) {
           c := atomic.AddInt64(&reqCounter, 1)
           if c%5 == 0 { // Simulasi flakiness jaringan/server
               http.Error(w, "INTERNAL_FLAKY_ERROR", http.StatusInternalServerError)
               return
           }
           body, _ := io.ReadAll(r.Body)
           log.Printf("[CORE MOCK SERVER] 200 OK Received Payload: %s", string(body))
           w.WriteHeader(http.StatusOK)
           w.Write([]byte(`{"ack": true}`))
       })

       log.Println("Starting Core SaaS Mock on :9001...")
       log.Fatal(http.ListenAndServe(":9001", nil))
   }
   ```

3. **Buat File Bespoke Engine Lengkap (`hands-on/m02/adapter_engine.go`)**:
   Gunakan struktur kode dari Seksi 7, modifikasi target egress client agar menembak ke `http://localhost:9001/api/v1/telemetry`, dan jalankan service-nya.

4. **Uji Penanganan Payload Menggunakan cURL**:
   Kirimkan payload berformat jelek (*legacy format*):
   ```bash
   curl -X POST http://localhost:8085/ \
        -H "Content-Type: application/json" \
        -d '{"SYS_USER_NO": "VIP-9901", "INTERNET_ADDR": "ALICE.WONDER@ENTERPRISE.CORP", "CUST_CLASS_CD": 1, "DISABLE_FLG": 0}'
   ```

5. **Verifikasi Output**:
   Perhatikan log konsol: payload kotor klien berhasil dinormalisasi ke *Canonical Domain Model*, dan antrean buffer berhasil melakukan retry otomatis saat mock core server sengaja melemparkan status error `500`.

---

### 13. Exercise

#### Level Easy
Tambahkan validasi pada `BespokeTranslatorClientX` untuk menolak request jika panjang string `SYS_USER_NO` kurang dari 5 karakter. Berikan response error yang deskriptif tanpa mengekspos internal stack trace ke klien.

#### Level Medium
Ubah in-memory channel `walBuffer` pada kode Seksi 7 menjadi sistem antrean lokal berbasis disk sederhana (misal: menuliskan payload JSON per baris ke file log `buffer.wal` menggunakan mode append-only `os.O_APPEND`), sehingga jika proses adapter di-kill (`kill -9`) dan dijalankan ulang, antrean data yang belum terkirim tidak hilang.

#### Level Hard
Rancang dan implementasikan mekanisme *Hot-Reload Dynamic Field Mapping*. Adapter harus memuat aturan mapping skema (misal: mapping key `SYS_USER_NO` -> `user_id`) dari sebuah file konfigurasi JSON eksternal tanpa perlu me-restart proses adapter HTTP server. Gunakan `sync.RWMutex` untuk menjamin operasi pembacaan mapping tetap non-blocking bagi transaksi throughput tinggi.

---

### 14. Challenge (Studi Kasus Nyata)

#### Deskripsi Tantangan
Sebuah konglomerat logistik maritim multinasional meneken kontrak integrasi. Mereka memiliki 500 kapal kargo yang berlayar di laut lepas. Setiap kapal memiliki server mini yang mengumpulkan ribuan sinyal sensor telemetri kontainer pendingin.
* **Konektivitas Jaringan**: Menggunakan koneksi satelit berbiaya sangat tinggi, intermiten, dengan latensi rata-rata 1.200ms, serta paket data drop mencapai 15%.
* **Sistem Klien**: Sensor mengirimkan data serial binary payload berukuran variabel melalui UDP port lokal.
* **Kebutuhan Core SaaS**: Core platform membutuhkan ingestion terurut berbasis waktu (*time-series ordered*) via JSON-over-HTTPS.

#### Tugas Anda (Sebagai Lead FDE):
Rancang arsitektur implementasi bespoke komprehensif yang di-deploy di atas server mini kapal kargo tersebut. Solusi Anda harus menjawab:
1. Bagaimana arsitektur penyerapan UDP lokal tanpa kehilangan data saat server mengalami CPU spike.
2. Mekanisme deduplikasi dan pemadatan (*deduplication and delta compression*) sebelum data dikirim via satelit untuk meminimalkan tagihan bandwidth klien.
3. Strategi pengurutan (*re-ordering engine*) dan sinkronisasi data yang datang terlambat (*out-of-order/late-arriving data*) saat kapal kembali mendapatkan koneksi internet stabil di pelabuhan.

*Dokumentasikan rancangan arsitektur ini dalam bentuk dokumen arsitektur teknis lengkap (High-Level Design & Low-Level Design) beserta pseudo-code komponen penghematan bandwidth.*

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Tingkat Dasar (Basic)
1. Apa peran primer dari *Anti-Corruption Layer* (ACL) dalam arsitektur integrasi sistem terdistribusi?
2. Mengapa memasukkan logika kondisional kustom klien (misal: `if (client == "X")`) langsung ke dalam codebase produk inti dianggap sebagai *anti-pattern*?
3. Sebutkan keunggulan utama menggunakan runtime WebAssembly (Wasm) dibandingkan Dynamic Shared Libraries (`.so` / `.dll`) dalam arsitektur plugin bespoke!
4. Apa fungsi dari *Write-Ahead Log* (WAL) lokal pada adapter bespoke yang dipasang di on-premise klien?
5. Mengapa teknik *Data Redaction/Sanitization* wajib dieksekusi di edge (sisi klien) sebelum data dipancarkan ke SaaS vendor?

#### B. Pertanyaan Tingkat Menengah (Intermediate)
6. Bagaimana cara menangani *Schema Drift* (perubahan struktur skema mendadak oleh klien) tanpa menyebabkan adapter mengalami *panic / unhandled crash*?
7. Jelaskan perbedaan mendasar antara implementasi integrasi menggunakan *State-based CRDTs* dibanding *Two-Phase Commit* (2PC) pada koneksi WAN trans-kontinental!
8. Pada kondisi bagaimana sebuah adapter bespoke diwajibkan menerapkan status proteksi *Circuit Breaker*?
9. Bagaimana strategi FDE dalam mengisolasi konfigurasi rahasia (*API keys, database passwords*) milik klien ketika adapter harus dideploy pada lingkungan *shared-infrastructure*?
10. Sebutkan 3 indikator objektif bahwa suatu implementasi bespoke sudah layak untuk diekstraksi (*graduated*) menjadi fitur platform core bawaan!

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Adapter Anda di-deploy sebagai sidecar di cluster Kubernetes milik bank sentral. Tiba-tiba penggunaan memori container adapter melonjak dari 150MB menjadi 4GB dalam kurun waktu 10 menit, memicu penalti OOMKilled oleh kernel. Langkah investigasi profiling apa yang wajib Anda jalankan, dan apa kemungkinan akar masalahnya terkait lifecycle garbage collection dan network buffering?
12. **Skenario 2**: Klien menuntut garansi *Exactly-Once Processing* untuk event finansial yang dipancarkan melalui webhook legacy mereka yang tidak memiliki *idempotency key*. Sebagai FDE, bagaimana Anda merekayasa *Deterministic Key Generation* di layer ACL Anda untuk memenuhi kebutuhan tersebut?
13. **Skenario 3**: Sebuah adapter integrasi bespoke berjalan sukses di 2 klien terpisah. Klien A mengirimkan 1.000 EPS, sedangkan Klien B mengirimkan 80.000 EPS. Pola arsitektur apa yang harus diubah dari sisi concurrency primitives dan scheduling agar kode yang sama dapat menangani variasi beban ekstrem ini tanpa memboroskan sumber daya komputasi?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### A. Jawaban Tingkat Dasar
1. **Peran ACL**: Mengisolasi dan menerjemahkan model data serta semantik domain milik sistem eksternal/legacy agar tidak mencemari model domain internal aplikasi inti.
2. **Alasan Anti-Pattern**: Menciptakan *tight-coupling*, meningkatkan kompleksitas siklotronik, memperbesar risiko regresi bagi tenant lain, dan memperlambat laju rilis platform.
3. **Keunggulan Wasm**: *Sandboxed security* yang ketat (isolasi memori total), dependensi netral platform, performa mendekati native (*near-native execution*), serta kapabilitas *hot-reloading* kode dinamis tanpa restart host process.
4. **Fungsi WAL**: Menjamin durabilitas data lokal (*zero data loss*) saat downstream terputus atau proses adapter mati tiba-tiba sebelum data terdistribusi ke core engine.
5. **Urgensi Sanitasi di Edge**: Untuk mematuhi kepatuhan regulasi privasi data global (GDPR, HIPAA, PCI-DSS) dengan memastikan data sensitif/PII tidak pernah melintasi batas jaringan fisik klien.

#### B. Jawaban Tingkat Menengah
6. **Menangani Schema Drift**: Terapkan *Tolerant Reader Pattern* yang mengabaikan field baru tak dikenal secara aman, kombinasikan dengan schema validator kontraktual berbasis AST, dan arahkan payload abnormal ke saluran *Quarantine Queue* untuk ditelaah tanpa mematikan sistem.
7. **CRDTs vs 2PC**: 2PC membutuhkan komunikasi tersinkronisasi (*synchronous blocking coordination*) yang sangat rapuh dan lambat pada koneksi WAN berlatensi tinggi. State-based CRDTs bekerja secara *asynchronous* dan *eventually consistent*, menyelesaikan konflik secara matematis tanpa distributed lock.
8. **Kondisi Circuit Breaker**: Ketika downstream service (Core SaaS) mengalami kegagalan beruntun melebihi ambang batas error (misal: >50% HTTP 5xx dalam jendela 30 detik), memotong koneksi seketika untuk memberi waktu recovery bagi downstream dan mengalihkan traffic ke local fallback buffer.
9. **Isolasi Rahasia**: Menggunakan integrasi HashiCorp Vault lokal, Kubernetes Secrets dengan enkripsi at-rest, atau memori terenkripsi yang hanya didekripsi via token ephemeral saat runtime tanpa pernah ditulis ke plain storage.
10. **Indikator Graduation**: (1) Terdapat minimal 3-5 klien enterprise independen yang meminta fungsionalitas serupa; (2) Pola transformasi data tersebut telah stabil (tidak berubah signifikan) selama > 6 bulan; (3) Solusi tersebut membuka kapabilitas pasar baru yang selaras dengan *product roadmap* platform inti.

#### C. Jawaban Skenario Kasus Produksi
11. **Analisis Skenario 1**:
    * *Investigasi*: Ambil heap memory dump dan goroutine stack profile via Go `pprof` (`go tool pprof http://localhost:.../debug/pprof/heap`).
    * *Kemungkinan Akar Masalah*: Terjadi network backpressure dari arah Core SaaS yang lambat, sementara adapter terus menerima koneksi TCP masuk tanpa batas rate limiting. Channel antrean in-memory menggelembung (*unbounded queue*), atau terjadi *goroutine leak* akibat pembuatan HTTP connection baru tanpa penutupan `resp.Body.Close()`.
12. **Analisis Skenario 2**:
    * *Solusi*: Rekayasa *Composite Deterministic Fingerprinting*. ACL mengekstraksi kombinasi field bisnis yang bersifat unik secara logika (contoh: gabungan `Timestamp Transaksi` + `Nomor Rekening Pengirim` + `Nomor Rekening Penerima` + `Nominal Nilai`). Kombinasi string tersebut di-hash menggunakan algoritma SHA-256 untuk memproduksi UUID v5 deterministik sebagai Idempotency Key resmi ke Core SaaS. Core SaaS kemudian mengeksekusi mekanisme atomic deduplication melalui Redis/Distributed Cache.
13. **Analisis Skenario 3**:
    * *Solusi*: Beralih dari model *one-goroutine-per-request* biasa ke arsitektur **Worker Pool berbasis Adaptive Work-Stealing** atau ring buffer (LMAX Disruptor Pattern). Terapkan pooling alokasi memori menggunakan `sync.Pool` untuk memotong overhead Garbage Collection pada beban 80.000 EPS. Terapkan strategi *dynamic batching*: pada 1.000 EPS data dikirim langsung secara stream; pada 80.000 EPS data otomatis dikelompokkan ke dalam micro-batches (misal: per 500 event atau per 50ms) sebelum dipancarkan ke egress network.

---

### 16. Summary

Peran Forward Deployed Engineer (FDE) pada ranah Rapid Prototyping & Bespoke Engineering adalah jembatan vital antara potensi teknis produk inti vendor dengan realitas operasional infrastruktur enterprise klien.

* Pola **Anti-Corruption Layer (ACL)** menjamin integritas arsitektur core SaaS tidak terkompromi oleh kebiasaan buruk sistem legacy klien.
* Penempatan **Durable Local Buffer & Circuit Breaking** mengubah integrasi rapuh menjadi sistem tangguh bertaraf industri (*high resilience*).
* Menjaga siklus rilis yang independen lewat pola *plug-in microkernel* memastikan kecepatan iterasi FDE tanpa menaikkan *technical debt* platform inti.
* Kesuksesan bespoke engineering jangka panjang diukur bukan dari seberapa banyak kode kustom yang Anda tulis, melainkan **seberapa elegan Anda mengisolasi kode kustom tersebut hingga saatnya diangkat (*graduated*) menjadi platform primitives permanen**.