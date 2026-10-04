## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran:** Forward Deployed Engineering (FDE)
*   **Kategori:** 06-Architecture-and-System-Design
*   **Bab 09:** Manajemen Stakeholder Teknis, Eksekutif & Upstreaming
*   **Modul 01:** Diplomasi Teknis, Ekspektasi Klien vs Roadmap Produk, Abstraksi Kebutuhan Klien ke Core Upstream
*   **Tingkat Kesulitan:** Advanced / Senior
*   **Prasyarat Konseptual:** Software Architecture Patterns (Microservices, Modular Monoliths, Hexagonal/Ports & Adapters), Product Lifecycle Management, Git Flow & Monorepo/Multi-repo Architecture, Distributed Systems Design.
*   **Estimasi Durasi Pengerjaan:** 4 - 6 Jam Pembelajaran Intensif

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1.  **Mendekomposisi dan Mengabstraksi Kebutuhan Lapangan (Bespoke Requirements):** Mengidentifikasi pola dasar dari kebutuhan kustom klien enterprise yang highly-specific, lalu memetakan dan mentransformasikannya ke dalam primitif domain generik yang dapat diintegrasikan ke *core upstream product engine*.
2.  **Mengeksekusi Diplomasi Teknis dan Manajemen Divergensi:** Mengelola konflik prioritas antara *hard deadline deployment* klien versus integritas arsitektural jangka panjang roadmap produk inti tanpa menyebabkan *fork drift* atau pembengkakan utang teknis (*technical debt*).
3.  **Mendesain Ekstensibilitas Berkelanjutan via Dynamic Extension Patterns:** Mengimplementasikan pola arsitektur *Plugin Engine*, *Open/Closed Hooks*, dan *Schema-Driven Ingestion* guna memisahkan *bespoke logic* (downstream) dari *core engine invariants* (upstream).
4.  **Menulis RFC/ADR Upstreaming Berstandar Industri:** Menyusun *Request for Comments* (RFC) dan *Architecture Decision Records* (ADR) defensif untuk meyakinkan Core Product Team agar menerima abstraksi fitur klien ke dalam rilis *mainline*.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                       [CLIENT DEPLOYMENT REALITY]
                                   │
               ┌───────────────────┴───────────────────┐
               ▼                                       ▼
    [Bespoke Edge Cases]                    [Fixed Client SLAs]
               │                                       │
               └───────────────────┬───────────────────┘
                                   │
                    (Technical Diplomacy Filter)
                                   │
                                   ▼
        [Forward Deployed Engineer (Architectural Translation)]
                                   │
       ┌───────────────────────────┼───────────────────────────┐
       ▼                           ▼                           ▼
[Downstream Extension]   [Upstream Core Abstraction]   [Deprecation / Rejection]
- Client Hook / Plugin   - Generic Domain Primitive   - Out of Scope / Anti-pattern
- Isolated Adapter Layer - Canonical Data Model       - Push back via ADR/RFC
- Non-breaking Overrides - Parameterized Engine Flow
       │                           │
       └─────────────┬─────────────┘
                     ▼
          [Upstream RFC Submission]
                     │
                     ▼
        [Core Mainline Integration]
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Salah satu kegagalan paling fatal dari perusahaan penyedia platform enterprise (B2B SaaS, Data Platforms, On-Premise Deployable Systems) adalah fenomena **Product Forking Trap**. 

Ketika enterprise customer dengan nilai kontrak jutaan dolar menuntut kustomisasi fungsionalitas (misalnya: *custom authentication protocols*, modifikasi pipeline ingest data legacy, atau skema validasi audit internal), Forward Deployed Engineer (FDE) sering berada di bawah tekanan eksekutif untuk melakukan *hardcode patch* langsung pada codebase cabang (*branch*) klien.

Hasil dari kompromi tersebut adalah:
*   **Fork Divergence Catastrophe:** Branch deployment klien bergeser terlalu jauh dari *core mainline*. FDE tidak lagi dapat menarik pembaruan keamanan, perbaikan bug, atau performa dari upstream tanpa merge conflicts massal.
*   **Consulting Trap:** Perusahaan produk bergeser menjadi perusahaan konsultan bespoke berbiaya tinggi, di mana 80% alokasi engineering dihabiskan untuk menjaga kompatibilitas cabang kustom alih-alih berinovasi pada core platform.
*   **Burnout dan Operational Attrition:** FDE terperangkap di tengah gesekan antara Chief Revenue Officer (yang berjanji pada klien) dan Head of Product/Core Platform Lead (yang menolak PR kotor masuk ke repo utama).

Menguasai teknik diplomasi teknis dan kemampuan abstraksi upstream adalah pembeda antara seorang *mediocre implementation engineer* dan seorang *high-leverage Senior Forward Deployed Engineer*. FDE tingkat lanjut tidak hanya "membuat sistem bekerja di klien", melainkan mengidentifikasi *missing primitive* dari platform utama, mengabstraksinya secara elegan, dan mengembalikan solusinya ke codebase upstream sehingga platform menjadi lebih kuat untuk ribuan klien berikutnya.

---

## SEKSI 05 — APA ITU (WHAT)

### Definisi Diplomasi Teknis (Technical Diplomacy)
Diplomasi Teknis adalah metodologi negosiasi berbasis rekayasa sistem yang memediasi kebutuhan bisnis klien yang mendesak dengan standar arsitektur jangka panjang dari Core Engineering Team. Tujuannya adalah mencapai *win-win architecture*: klien mendapatkan kapabilitas yang dibutuhkan tepat waktu sesuai SLA, sementara platform inti tidak terkontaminasi oleh asumsi-asumsi lokal klien (*local domain assumptions*).

### Definisi Core Upstream Abstraction
Abstraksi Upstream adalah proses ekstraksi logika komputasi, skema, atau alur kerja yang sangat spesifik untuk satu klien tertentu (*client-specific downstream implementation*) menjadi primitif arsitektur kelas-satu (*first-class generic primitive*) di dalam repositori inti upstream.

Tiga pilar dalam arsitektur upstreaming:
1.  **Invariance vs Variance Isolation:** Memisahkan komponen sistem yang mutlak konstan (invariants, misal: distributed consensus, security envelope, transactional integrity) dari komponen yang dinamis antar klien (variance, misal: mapping skema, transformasi payload, protokol integrasi legacy).
2.  **Protocol-Oriented Decoupling:** Penggunaan antarmuka abstrak (*Interface Contracts*), SPI (*Service Provider Interface*), atau *Event/Webhook interception* alih-alih modifikasi inline logic.
3.  **Upstream Engineering Loop:** Siklus hidup di mana ekstensi darurat (*tactical shim/adapter*) yang diuji di lapangan distandardisasi menjadi Core RFC, di-merge ke mainline, dan shim downstream dihapus (*deprecate and align*).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Alur Ekstraksi: Dari Bespoke Request Menjadi Upstream Primitive

Proses abstraksi dan diplomasi teknis berjalan dalam 4 fase struktural:

```
[Phase 1: Ingestion & Isolation]
   Klien meminta integrasi custom SAP RFC format proprietary.
   FDE TIDAK mengedit `core/ingestion_engine.go`.
   FDE membuat `SAPInboundAdapter` di layer downstream menggunakan plugin interface yang sudah ada.

[Phase 2: Pattern Recognition & Generalization]
   FDE menganalisis: Apakah ini benar-benar unik untuk SAP, atau ini variasi dari "Stateful Chunked Ingestion"?
   Kebutuhan diabstraksi: "Core platform membutuhkan abstraksi StatefulStreamingSource".

[Phase 3: Tactical Shim vs Strategic RFC]
   SLA Klien menuntut delivery dalam 2 minggu. Upstream roadmap butuh 6 minggu.
   Tactical: FDE deploy Adapter downstream menggunakan Hook Point lokal.
   Strategic: FDE menulis RFC Core Architecture untuk 'StatefulStreamingSource', lengkap dengan mock test & benchmark.

[Phase 4: Upstreaming & Convergence]
   Core Engineering menerima RFC dan merilis v2.4.0.
   FDE me-refactor adapter klien: membuang bespoke engine, beralih ke Core Primitive v2.4.0.
   Downstream kembali identik (drift = 0) dengan upstream.
```

### Framework Keputusan Negosiasi: Client vs Roadmap

Setiap kali permintaan fitur klien muncul, FDE mengevaluasinya menggunakan matriks berikut:

| Karakteristik Kebutuhan | Klasifikasi | Tindakan Arsitektural | Negosiasi Stakeholder |
| :--- | :--- | :--- | :--- |
| Spesifik satu klien, format data proprietary, melanggar standar platform | **Pure Downstream Edge** | Bangun di Out-of-Process Adapter / Sidecar / Webhook Extension. | *"Kami mendukung ini 100% via plugin layer tanpa mengorbankan stabilitas core platform."* |
| Klien meminta variasi validasi/transformasi yang masuk akal namun belum ada di core | **Core Gap (Candidate Primitive)** | Desain hook interface baru di core upstream; implementasi adapter downstream. | *"Fitur ini masuk upstream core via fast-track RFC. Kami sediakan beta adapter hari ini."* |
| Klien menolak paradigma platform (e.g. meminta synchronous direct-to-db access pada async platform) | **Architectural Anti-Pattern** | Tolak secara diplomatis. Tawarkan alternatif asinkron berbasis event/IDempotent API. | Tunjukkan data performa, risiko kegagalan skalabilitas, dan batasan SLA jika pola buruk dipaksakan. |

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah arsitektur sistem yang membedakan penanganan anti-pattern (*Bespoke Direct Coupling*) versus arsitektur enterprise modern (*Hexagonal Core with Dynamic Downstream Extension Isolation*):

### Anti-Pattern: Bespoke Direct Coupling (Fork Drift Disaster)
```
       REPO UPSTREAM MAINLINE                    REPO FORK CLIENT A
┌─────────────────────────────────┐      ┌─────────────────────────────────┐
│        Core Pipeline Engine     │      │        Core Pipeline Engine     │
│                                 │      │                                 │
│  func Process(data Data) {      │      │  func Process(data Data) {      │
│      Validate(data)             │      │      if ClientA {               │
│      TransformGeneric(data)     │      │          TransformBespoke(data) │ <-- HARDCODED
│      SaveToDatabase(data)       │      │      } else {                   │
│  }                              │      │          TransformGeneric(data) │
│                                 │      │      }                          │
│                                 │      │      SaveToDatabase(data)       │
└─────────────────────────────────┘      │  }                              │
                                         └─────────────────────────────────┘
                                                          ▲
                                                          │ 500 Commits Behind
                                                          │ Can NEVER merge cleanly!
```

### Production Architecture: Extensible Core via Inversion of Control & Upstream Driver SPI
```
                 ┌────────────────────────────────────────────────────────┐
                 │                  CORE UPSTREAM ENGINE                  │
                 │                                                        │
                 │   ┌────────────────────────────────────────────────┐   │
                 │   │            Domain Pipeline Pipeline            │   │
                 │   │                                                │   │
                 │   │   Invariants: Auth, Tracing, Retry, Metrics    │   │
                 │   └───────────────────────┬────────────────────────┘   │
                 │                           │                            │
                 │                           ▼                            │
                 │         <<Interface>> IngestionTransformer             │
                 │   + Transform(ctx Context, in []byte) (Record, error)  │
                 └───────────────────────────┬────────────────────────────┘
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       │ Implements (via SPI or dynamic load)       │
                       ▼                                           ▼
┌───────────────────────────────────────────────┐ ┌───────────────────────────────────────────────┐
│        UPSTREAM DEFAULT PLUGIN                │ │           DOWNSTREAM CLIENT ADAPTER           │
│                                               │ │                                               │
│  type JSONTransformer struct{}                │ │  type ClientBespokeEBCDICTransformer struct{} │
│  func (j *JSONTransformer) Transform(...)     │ │  func (c *ClientBespokeEBCDICTransformer)     │
│  (Integrated inside Core Engine codebase)     │ │        Transform(...)                         │
│                                               │ │  (Maintained in Client Deployment Repo Layer) │
└───────────────────────────────────────────────┘ └───────────────────────────────────────────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah demonstrasi bagaimana mengubah hardcoded conditional logic klien menjadi interface-driven design yang aman dan siap di-upstream.

### Bad Approach: Conditional Anti-pattern
```go
// core/processor.go - JANGAN LAKUKAN INI
func ProcessOrder(orderType string, payload []byte) error {
    if orderType == "ACME_CORP_LEGACY" {
        // Logika custom klien ACME Corp merusak kesucian upstream codebase
        return processAcmeOrder(payload)
    }
    // Standar platform
    return processStandardOrder(payload)
}
```

### Good Approach: Strategic Upstream Abstraction via Registry Pattern

```go
// core/processor.go (UPSTREAM CLEAN CODEBASE)
package core

import (
	"context"
	"fmt"
	"sync"
)

// IngestionPayload merepresentasikan generic canonical record
type IngestionPayload struct {
	ID        string
	Timestamp int64
	Body      []byte
	Metadata  map[string]string
}

// IngestionTransformer adalah extension contract (SPI)
type IngestionTransformer interface {
	Supports(format string) bool
	Transform(ctx context.Context, raw []byte) (*IngestionPayload, error)
}

// Registry memelihara registered transformers
type TransformerRegistry struct {
	mu           sync.RWMutex
	transformers map[string]IngestionTransformer
}

var DefaultRegistry = &TransformerRegistry{
	transformers: make(map[string]IngestionTransformer),
}

func (r *TransformerRegistry) Register(format string, t IngestionTransformer) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.transformers[format] = t
}

func (r *TransformerRegistry) Get(format string) (IngestionTransformer, error) {
	r.mu.RUnlock()
	defer r.mu.RUnlock()
	t, exists := r.transformers[format]
	if !exists {
		return nil, fmt.Errorf("transformer format %s not registered", format)
	}
	return t, nil
}

// Engine mengeksekusi pipeline invariants tanpa memedulikan implementasi parsing
func ExecuteIngestionPipeline(ctx context.Context, format string, data []byte) (*IngestionPayload, error) {
	transformer, err := DefaultRegistry.Get(format)
	if err != nil {
		return nil, err
	}

	// Invariant Core: Audit, Context Check, Metrics
	if ctx.Err() != nil {
		return nil, ctx.Err()
	}

	payload, err := transformer.Transform(ctx, data)
	if err != nil {
		return nil, fmt.Errorf("pipeline transform failure: %w", err)
	}

	return payload, nil
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### Skenario Lapangan Real-World
Klien: Bank Enterprise Tier-1 menuntut sistem *Compliance Audit Event Log* kita untuk mendukung hashing hardware khusus via *Hardware Security Module* (HSM) lokal mereka dengan protokol PKCS#11, bukan default cloud hashing (KMS/Ed25519) bawaan core platform kita.

Jika FDE mengabaikan arsitektur upstream, FDE akan menyuntikkan driver library C-Go PKCS#11 langsung ke dalam container pipeline utama, mematahkan automated CI/CD pipeline upstream platform karena driver tersebut membutuhkan dependency OS proprietary.

### Solusi FDE: Dynamic Crypto Provider SPI + Remote gRPC Out-of-Process Hook

#### 1. Core Upstream Contract Definition (Golang)
*File: `upstream/pkg/crypto/signer.go`*
```go
package crypto

import (
	"context"
	"errors"
)

var ErrProviderNotFound = errors.New("crypto provider not found in runtime")

// SignatureResult adalah representasi generik hasil signing
type SignatureResult struct {
	Signature []byte
	KeyID     string
	Algorithm string
}

// SignerProvider adalah SPI contract upstream
type SignerProvider interface {
	Algorithm() string
	Sign(ctx context.Context, digest []byte) (*SignatureResult, error)
}
```

#### 2. Downstream Remote Adapter (Client Deployment Layer)
FDE tidak memasukkan driver PKCS#11 ke upstream, melainkan membuat *gRPC Sidecar Provider* di downstream yang mengimplementasikan interface `SignerProvider`.

*File: `downstream/adapters/hsm_sidecar_provider.go`*
```go
package adapters

import (
	"context"
	"fmt"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	
	"upstream/pkg/crypto"
	// Import auto-generated protobuf client
	pb "downstream/proto/client_hsm"
)

type RemoteHSMProvider struct {
	client pb.HSMSigningServiceClient
	conn   *grpc.ClientConn
}

func NewRemoteHSMProvider(sidecarAddress string) (*RemoteHSMProvider, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	conn, err := grpc.DialContext(
		ctx,
		sidecarAddress,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithBlock(),
	)
	if err != nil {
		return nil, fmt.Errorf("failed connecting to client HSM sidecar: %w", err)
	}

	return &RemoteHSMProvider{
		client: pb.NewHSMSigningServiceClient(conn),
		conn:   conn,
	}, nil
}

func (p *RemoteHSMProvider) Algorithm() string {
	return "PKCS11-HSM-SHA256"
}

func (p *RemoteHSMProvider) Sign(ctx context.Context, digest []byte) (*crypto.SignatureResult, error) {
	req := &pb.SignRequest{
		Digest: digest,
	}

	res, err := p.client.SignHash(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("remote sidecar HSM sign failed: %w", err)
	}

	return &crypto.SignatureResult{
		Signature: res.GetSignatureBytes(),
		KeyID:     res.GetKeyArn(),
		Algorithm: p.Algorithm(),
	}, nil
}

func (p *RemoteHSMProvider) Close() error {
	return p.conn.Close()
}
```

#### 3. Core Engine Pipeline Invariance
*File: `upstream/pkg/audit/pipeline.go`*
```go
package audit

import (
	"context"
	"crypto/sha256"
	"fmt"

	"upstream/pkg/crypto"
)

type AuditPipeline struct {
	signer crypto.SignerProvider
}

func NewAuditPipeline(signer crypto.SignerProvider) *AuditPipeline {
	return &AuditPipeline{signer: signer}
}

func (p *AuditPipeline) CommitLog(ctx context.Context, logPayload []byte) error {
	// Compute canonical digest
	hash := sha256.Sum256(logPayload)

	// Delegate signing via abstract provider (could be Cloud KMS, Local Ed25519, or Client HSM Sidecar)
	sigResult, err := p.signer.Sign(ctx, hash[:])
	if err != nil {
		return fmt.Errorf("audit log signing failed: %w", err)
	}

	// Persist log + signature securely
	fmt.Printf("[AUDIT] Log signed successfully with Algo: %s, KeyID: %s\n", 
		sigResult.Algorithm, sigResult.KeyID)
	return nil
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan | Keuntungan (+)| Kerugian (-) | Skenario Terbaik |
| :--- | :--- | :--- | :--- |
| **In-Process Custom Patching** (Hardcoding branch klien) | Sangat cepat diimplementasikan untuk *quick-win* demo / deadline SLA agresif. | Menyebabkan *branch drift*, kompilasi rapuh, *nightmare merge*, dan regresi bug upstream. | **Strictly NEVER in production**. Hanya untuk PoC < 48 jam yang akan dibuang (*throwaway prototype*). |
| **Out-of-Process Hook (gRPC Sidecar/Webhook)** | Isolasi kegagalan 100%. Dependency proprietary klien tidak mengotori *core binary*. Bebas bahasa pemrograman. | Menambah latensi jaringan (network hop overhead), kompleksitas orkestrasi Kubernetes (sidecars), dan *serialization cost*. | Integrasi legacy banking, dependensi library binary tak terpercaya (C/C++ SO, DLL), atau HSM lokal. |
| **Upstream Dynamic SPI Plugin (Core Interface)** | Performa zero-latency overhead. Tercakup dalam *type-safe compile time checks*. Kode terstandardisasi upstream. | Memerlukan siklus approval RFC Core Team yang lebih panjang; rilis terikat jadwal Core Product Roadmap. | Fungsionalitas yang terbukti dibutuhkan oleh minimal 2 enterprise clients (misal: format auth OAuth2 mTLS baru). |

---

## SEKSI 11 — BEST PRACTICES

1.  **Terapkan Hukum Zero Core Modifications:** Jangan pernah mengubah file inti domain tanpa persetujuan RFC, kecuali Anda memanggil *well-defined extension interface*.
2.  **Sediakan Adapter 'Escape Hatch':** Selalu sediakan antarmuka generik berbasis *Byte-in, Byte-out* atau *Metadata Context* di pipeline utama agar custom transformation downstream dapat berjalan tanpa harus membedah sistem upstream.
3.  **Dokumentasikan Kontrak dengan Architectural Decision Record (ADR):** Tuliskan alasan teknis mengapa suatu kebutuhan kustom ditolak untuk masuk ke core dan dialihkan ke sidecar plugin. Jadikan ADR ini artefak diplomasi saat berbicara dengan eksekutif.
4.  **Terapkan Semantic Versioning pada Plugin Interfaces:** Interface yang diekspos ke klien atau downstream harus stabil. Setiap modifikasi tanda tangan method (*method signature*) wajib menaikkan *major version* dan menyediakan backwards-compatibility layer.
5.  **Terapkan Sandbox / Circuit Breaker pada Client Extensions:** Logika kustom yang dijalankan di downstream tidak boleh menyebabkan thread starvation, memory leak, atau blocking I/O tanpa batas waktu pada invariant core upstream platform. Gunakan `context.WithTimeout` pada setiap pemanggilan extension hook.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1.  **The "Yes-Man" Trap (Overpromising to Executive):** FDE menyetujui semua permintaan VP of Sales klien tanpa melakukan *Technical Feasibility Review*, yang berujung pada komitmen deadline yang mustahil dipenuhi tanpa merusak codebase platform.
2.  **Leaky Domain Abstractions:** Membawa istilah atau terminologi klien langsung ke upstream repository. 
    *   *Contoh salah:* Membuat interface `type CitibankAccountParser interface`.
    *   *Contoh benar:* Membuat interface `type FinancialRecordParser interface` dengan implementasi `CitibankParser` di downstream package.
3.  **Upstream Ghosting:** FDE membuat solusi bespoke di layer downstream, namun tidak pernah membuat ticket atau RFC upstream untuk memperbaiki *root cause architectural limitation*. Hasilnya, tim downstream berikutnya akan terus menulis shim yang sama secara berulang-ulang.
4.  **The Monolithic Core Bleed:** Membiarkan C-bindings, dynamic native libraries, atau security license key milik klien masuk ke core Dockerfile platform upstream.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan: Mengabstraksi Custom Enterprise Authentication Mechanism

#### Konteks:
Klien "Enterprise-X" menggunakan header autentikasi HTTP kustom: `X-Enterprise-Auth: User|Signature|Timestamp`. Format signature adalah HMAC-SHA1 dari hash token rahasia mereka.
Core platform Anda hanya mendukung header `Authorization: Bearer <JWT>`.

#### Tugas:
1.  Buka struktur Golang di bawah ini.
2.  Jangan ubah `CoreAuthMiddleware` secara langsung dengan hardcoded `if`.
3.  Implementasikan `AuthStrategy` pattern.
4.  Buat implementasi `LegacyClientXAuthenticator` dan daftarkan ke middleware pipeline.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"strings"
)

type UserIdentity struct {
	Username string
	Roles    []string
}

// LENGKAPI INTERFACE INI (UPSTREAM PRIMITIVE)
type AuthStrategy interface {
	// TODO: Tentukan method contract
}

// ENGINE CORE MIDDLEWARE (TIDAK BOLEH BERUBAH)
type SecurityManager struct {
	strategies []AuthStrategy
}

func NewSecurityManager() *SecurityManager {
	return &SecurityManager{strategies: make([]AuthStrategy, 0)}
}

func (sm *SecurityManager) RegisterStrategy(s AuthStrategy) {
	sm.strategies = append(sm.strategies, s)
}

func (sm *SecurityManager) AuthenticateRequest(req *http.Request) (*UserIdentity, error) {
	// TODO: Implementasikan iterasi fallback autentikasi yang aman
	return nil, errors.New("authentication failed across all strategies")
}

// IMPLEMENTASIKAN STRATEGI CLIENT-X DI SINI
type EnterpriseXCustomStrategy struct {
	SecretKey string
}

func main() {
	// Verifikasi implementasi Anda bekerja
	sm := NewSecurityManager()
	
	// Daftarkan Custom Strategy
	// sm.RegisterStrategy(...)
	
	req, _ := http.NewRequest("GET", "/api/v1/resource", nil)
	req.Header.Set("X-Enterprise-Auth", "admin|valid_mock_signature|1690000000")
	
	user, err := sm.AuthenticateRequest(req)
	if err != nil {
		fmt.Printf("FAILED: %v\n", err)
	} else {
		fmt.Printf("SUCCESS: Authenticated as %s\n", user.Username)
	}
}
```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1.  **Apa indikator utama bahwa sebuah custom requirement harus diimplementasikan sebagai upstream core primitive alih-alih downstream custom adapter?**
    *   A. Ketika Chief Revenue Officer meminta requirement tersebut diprioritaskan.
    *   B. Ketika requirement tersebut merepresentasikan missing capability generik yang dapat dimanfaatkan oleh minimal 2 atau lebih enterprise clients di masa depan.
    *   C. Ketika klien bersedia membayar 20% lebih banyak dari nilai kontrak awal.
    *   D. Ketika library pihak ketiga hanya kompatibel dengan Linux kernel versi terbaru.

2.  **Apa risiko terbesar dari mempertahankan bespoke code branch (long-lived forks) khusus untuk masing-masing enterprise client?**
    *   A. Meningkatnya konsumsi disk space pada GitHub/GitLab server.
    *   B. Biaya transfer data jaringan cloud yang lebih mahal.
    *   C. Fork Drift, yang mengakibatkan merge conflicts masif dan ketidakmampuan platform klien untuk menerima upstream security patches.
    *   D. Tim Core Product akan kehilangan visibilitas terhadap metrics deployment.

3.  **Manakah cara yang benar secara diplomasi teknis untuk menolak permintaan hardcode klien yang melanggar integritas arsitektur platform?**
    *   A. Mengatakan secara eksplisit bahwa sistem klien mereka sudah kuno dan platform menolak arsitektur tersebut.
    *   B. Menolak tanpa memberikan alternatif teknis karena hal tersebut di luar skop kontrak.
    *   C. Menyediakan extension point/sidecar adapter untuk kebutuhan saat ini, sembari menulis ADR yang memaparkan dampak performa dan biaya operasional dari pendekatan tersebut.
    *   D. Menerima permintaan klien secara diam-diam dan menyembunyikannya di cabang repository downstream tanpa memberitahu tim inti.

4.  **Dalam konsep Hexagonal Architecture (Ports and Adapters), peran apa yang dijalankan oleh FDE saat melakukan deployment integration?**
    *   A. Mengubah Domain Entities di Core Hexagon agar cocok dengan database legacy milik klien.
    *   B. Mengimplementasikan Secondary/Driven Adapters baru di outside hexagon untuk menerjemahkan protokol legacy klien ke domain contract invariant.
    *   C. Menghapus Ports interfaces untuk meningkatkan performa komputasi.
    *   D. Mengabaikan domain boundary demi mempercepat SLA integrasi.

*(Kunci Jawaban: 1-B, 2-C, 3-C, 4-B)*

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Buku:**
    *   *Software Architecture: The Hard Parts* oleh Neal Ford, Mark Richards, Pramod Sadalage, Zhamak Dehghani (O'Reilly Media).
    *   *The Staff Engineer's Path: A Guide for Individual Contributors Navigating Innovation and Change* oleh Tanya Reilly.
    *   *Clean Architecture: A Craftsman's Guide to Software Structure and Design* oleh Robert C. Martin.
*   **Makalah & Standar:**
    *   *Architecture Decision Records (ADRs)* - Michael Nygard template & ThoughtWorks Technology Radar Guidance.
    *   *Google Engineering Practices Documentation:* Code Review Developer Guide (Handling Divergence and Architectural Integrity).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

Forward Deployed Engineering bukan semata-mata tentang penulisan kode integrasi, melainkan seni menjaga keseimbangan antara komersialisme solusi lapangan (*tactical delivery*) dengan kebersihan arsitektural produk (*strategic platform integrity*).

Kunci sukses upstreaming:
1.  **Never Fork, Always Extend:** Jangan biarkan branch repo klien terisolasi dari mainline repo.
2.  **Pattern Over Specifics:** Ubah nama spesifik klien menjadi terminologi primitif domain yang generik di upstream layer.
3.  **Diplomacy Through Architecture:** Katakan "Ya, kami bisa mendukungnya via Isolated Extension Layer" alih-alih mengatakan "Tidak bisa", sembari melindungi core invariants platform dari degradasi teknis.

---

## SEKSI 17 — GLOSARIUM

*   **Upstream:** Repositori atau codebase produk utama yang menjadi sumber kebenaran (*single source of truth*) yang dikelola oleh Core Product Engineering.
*   **Downstream:** Codebase, repositori deployment, atau konfigurasi lokal yang berjalan di lingkungan klien tertentu (*client-specific deployment environment*).
*   **Fork Drift:** Deviasi kode yang terjadi ketika salinan repositori klien berjalan menyimpang terlalu jauh dari upstream repository hingga tidak lagi mungkin disinkronkan secara otomatis.
*   **SPI (Service Provider Interface):** Pola antarmuka yang memungkinkan fungsionalitas pihak ketiga atau eksternal disuntikkan ke dalam sistem inti tanpa modifikasi kode sumber inti tersebut.
*   **ADR (Architecture Decision Record):** Dokumen struktural singkat yang menangkap keputusan arsitektur penting beserta konteks dan konsekuensinya.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Poin Penekanan Materi:** Tekankan bahwa mahasiswa/peserta sering tergoda untuk menjadi "Pahlawan" di mata klien dengan mengiyakan semua request secara cepat via dirty-patching. Berikan studi kasus kegagalan startup enterprise yang mati akibat terjebak dalam *consulting doom-loop* akibat dirty-patching tersebut.
*   **Panduan Diskusi Kelas:** Tanyakan kepada peserta: *"Bagaimana respon Anda jika VP of Engineering dari klien enterprise Anda memaksa Anda menginstal modul kernel custom di Kubernetes nodes yang kita sediakan?"* Bimbing diskusi ke arah negosiasi batas tanggung jawab SLA, isolasi sistem (e.g. sidecars), dan analisis trade-offs.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Oktober 2023):**
    *   Rilis awal materi Bab 09 Module 01.
    *   Standardisasi modul sesuai pedoman kurikulum teknis FDE.
    *   Penambahan skema gRPC Sidecar Provider & Driver SPI Pattern.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** 05-Reliability-Observability / Bab 08 / Module 03 — *Disaster Recovery, Chaos Engineering & Failover Orchestration in Enterprise Infrastructure*
*   **Modul Berikutnya:** 06-Architecture-and-System-Design / Bab 09 / Module 02 — *Pola Arsitektur Multi-Tenant vs Hybrid On-Premise Single-Tenant Isolation*