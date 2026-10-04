# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Bab 09: Manajemen Stakeholder & Upstreaming
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Memitigasi Fork Gravity & Upstream Divergence:** Mengidentifikasi indikator degradasi kode akibat kustomisasi lokal klien dan menyusun strategi refactoring berbasis arsitektur *hexagonal* (*ports and adapters*).
2. **Merancang Sistem Ekstensibilitas Terisolasi (*In-Process* dan *Out-of-Process*):** Mengimplementasikan pola plugin modular berbasis gRPC (*HashiCorp go-plugin style*) dan WASM (*WebAssembly*) untuk mengisolasi logika spesifik klien dari *core engine*.
3. **Membangun Pipeline Upstreaming dan Kontrak Integrasi Terotomasi:** Mengembangkan sistem pengujian kontrak (*consumer-driven contract testing*) dan *drift detection* guna menjamin kompatibilitas antara rilis *core* dan modifikasi lapangan (*field-deployed modules*).
4. **Mengelola Siklus Hidup Rilis Terdistribusi:** Mengatur alur percabangan Git (*topology-aware branching*), *semantic patch management*, dan otomatisasi rilis multi-tenant pada infrastruktur *air-gapped* maupun *hybrid-cloud*.

---

### 2. Prerequisite
Peserta wajib memiliki pemahaman mendalam pada domain berikut:
- **Arsitektur Sistem Terdistribusi:** IPC (*Inter-Process Communication*), gRPC, Protobuf, dan serialisasi data berkecepatan tinggi.
- **Bahasa Pemrograman Tingkat Lanjut:** Go (Golang) tingkat menengah-lanjut (Goroutine, Channels, Reflection, Dynamic Linking/Interfaces).
- **Sistem Kontrol Versi Lanjutan:** *Git plumbing commands*, *interactive rebase*, manipulasi Git tree, serta desain GitOps.
- **Containerization & Orchestration:** Docker, Kubernetes Custom Resource Definitions (CRDs), dan service mesh dasar.

---

### 3. Concept & Internal Architecture (Mendalam)

#### Masalah Utama: "The Customer Fork Trap"
Dalam ekosistem Forward Deployed Engineering (FDE), kebutuhan mendesak klien enterprise sering memicu jalan pintas: membuat salinan repositori (*hard fork*) atau menyisipkan percabangan logika berbasis tenant di dalam *core codebase*:

```go
// ANTI-PATTERN: Tenant Branching di Core Logic
func ProcessTransaction(ctx context.Context, tx *Transaction) error {
    if tx.TenantID == "BANK_MEGA_CORP" {
        return processLegacyISO8583(tx) // Logic klien mengotori Core Engine
    }
    return processStandard(tx)
}
```

Praktik ini menciptakan fenomena **Fork Gravity**, di mana biaya pemeliharaan (*maintenance overhead*) meningkat secara eksponensial terhadap waktu:

$$\text{Maintenance Overhead} \propto \mathcal{O}(N \times M^2)$$

Di mana $N$ adalah jumlah klien enterprise dan $M$ adalah jumlah commit diferensial antara *core mainline* dan *client branch*. Jika $M$ melampaui ambang batas toleransi, *backporting* patch keamanan dan pembaruan fitur inti menjadi mustahil secara ekonomis, berujung pada kegagalan operasional (*maintenance death spiral*).

#### Pola Solusi: Arsitektur Ekstensibilitas Hexagonal
Untuk memutus *fork gravity*, arsitektur harus memisahkan *Core Business Logic* dari *Tenant Customization* menggunakan abstraksi batas yang kaku:

```
+-----------------------------------------------------------------------+
|                         CORE PLATFORM DOMAIN                          |
|                                                                       |
|   +------------------+       Events        +----------------------+   |
|   |  State Machine   |-------------------->| Extension Dispatcher |   |
|   +------------------+                     +----------------------+   |
|            ^                                          |               |
|            | Inversion of Control                     |               |
|            v                                          v               |
|   +------------------+                     +----------------------+   |
|   | Core Service API |                     | Extension SPI (Port) |   |
|   +------------------+                     +----------------------+   |
+------------|------------------------------------------|---------------+
             |                                          |
             |                                 RPC / IPC / WASM Boundary
             |                                          |
             v                                          v
+------------------------+                  +---------------------------+
| Mainline HTTP/gRPC     |                  | Out-of-Process Plugin     |
| Adapters (Standard)    |                  | (Tenant-Specific Adapter) |
+------------------------+                  +---------------------------+
```

1. **Service Provider Interface (SPI):** *Core engine* mendefinisikan *interface contract* yang ketat menggunakan Protocol Buffers.
2. **Dynamic Plugin Execution:** Modifikasi klien dieksekusi di luar *binary core* utama melalui:
   - **Out-of-Process RPC (gRPC melalui Unix Domain Socket):** Menjamin isolasi memori (*fault isolation*). Kerusakan (*crash*) pada kode kustom klien tidak meruntuhkan *core engine*.
   - **WebAssembly (WASM):** Eksekusi *sandboxed in-process* dengan overhead komunikasi mendekati nol untuk logika transformasi data berlatensi rendah.
3. **Upstreaming Engine:** Segala modifikasi yang bersifat generik ditarik (*upstreamed*) ke *core mainline* melalui mekanisme standardisasi kapabilitas (*capability standardization*).

---

### 4. Why & What

| Dimensi | Hard Forking (Bespoke Implementation) | Upstreaming-First Architecture |
| :--- | :--- | :--- |
| **Pemisahan Logika** | Logika klien bercampur baur di repositori terpisah atau *branch* abadi. | *Core logic* bebas dari dependensi klien; modifikasi diisolasi via plugin/SPI. |
| **Siklus Pembaruan** | Setiap pembaruan *core* menuntut resolusi konflik manual (*merge hell*). | Pembaruan *core* dilakukan secara independen via *semantic versioning* dan pengujian kontrak. |
| **Blast Radius Kegagalan** | Bug kustomisasi klien berpotensi merusak fungsionalitas sistem global. | Terisolasi secara ketat (*sandboxed* via WASM atau *process boundary* gRPC). |
| **Total Cost of Ownership (TCO)** | Meningkat tajam seiring bertambahnya klien (tidak terukur). | Konstan atau terdistribusi secara linear sesuai kapabilitas tim FDE. |
| **Time-to-Value (TTV)** | Cepat pada hari ke-1, melambat secara fatal pada bulan ke-6. | Sedikit lebih lambat pada hari ke-1, konstan dan terprediksi selamanya. |

---

### 5. How (Workflow Upstreaming Terstruktur)

Proses transformasi fitur kustom klien menuju *core mainline* mengikuti 5 fase:

```
[Klien: Kebutuhan Kustom]
          |
          v
+-------------------+      Kebutuhan Sangat Spesifik
| Fase 1: Abstraksi |-------------------------------------> [Bangun Plugin / SPI]
| Analisis Variansi |                                               |
+-------------------+                                               |
          |                                                         |
          | Pola Ditemukan (>1 Klien)                              |
          v                                                         |
+-------------------+                                               |
| Fase 2: Kontrak   |                                               |
| Pembuatan Protobuf|                                               |
+-------------------+                                               |
          |                                                         |
          v                                                         |
+-------------------+                                               |
| Fase 3: Mainline  |                                               |
| Core Engine RFC   |                                               |
+-------------------+                                               |
          |                                                         |
          v                                                         |
+-------------------+                                               |
| Fase 4: Ekstraksi |                                               |
| Generic Kernel    |                                               |
+-------------------+                                               |
          |                                                         |
          v                                                         |
+-------------------+      Pasang Adapter Generik                   |
| Fase 5: Konsolidasi|<---------------------------------------------+
| Deprecate Plugin  |
+-------------------+
```

1. **Fase 1 (Analisis Variansi):** FDE mengidentifikasi apakah kebutuhan klien adalah variasi data (*data drift*), variasi protokol (*protocol drift*), atau variasi logika bisnis (*business rules drift*).
2. **Fase 2 (Isolasi Batas Kontrak):** Implementasikan *hook* interface pada *core* jika belum tersedia. Kembangkan logika klien sebagai plugin independen yang mematuhi Protobuf SPI.
3. **Fase 3 (RFC Upstream Mainline):** Jika >2 klien membutuhkan variasi serupa, ajukan RFC (*Request for Comments*) ke Core Platform Team untuk standardisasi interface/fitur.
4. **Fase 4 (Ekstraksi Kernel):** Core team mengimplementasikan abstraction engine generik pada mainline.
5. **Fase 5 (Konsolidasi & Deprecation):** FDE memigrasikan plugin klien ke konfigurasi standar *core engine*, lalu memensiunkan (*deprecate*) plugin kustom tersebut.

---

### 6. Analogi & Diagram ASCII

#### Analogi: Arsitektur Kernel Driver Linux
Pertimbangkan bagaimana OS Linux menangani ribuan vendor perangkat keras berbeda. Linux Kernel tidak membuat *fork* terpisah untuk laptop Dell, Lenovo, atau server HP. Kernel mendefinisikan *interface driver* yang stabil (VFS, Network Stack). 
- Jika vendor membuat modul *closed-source* (*out-of-tree*), setiap pembaruan kernel akan merusak modul tersebut.
- Solusi industri: Vendor bekerja sama meng-*upstream* abstraksi driver ke dalam *mainline tree*, memastikan kompatibilitas abadi dan pengujian otomatis terpusat.

#### Diagram Topologi Git & Deployment Kontrak
```
CORE REPO (Mainline)
(v1.0.0) ---> (v1.1.0) -------------------------> (v1.2.0) [Mainline Release]
                 |                                   |
                 +---- Contract Test Passed? --------+
                 |     (Consumer-Driven Contract)    |
                 v                                   v
CLIENT REPO / EXTENSION HOST             
                 +-----------------------------------+
                 | Plugin: Bank Mega ISO8583 Adapter |
                 | Built with Proto-v1.1.0           |
                 +-----------------------------------+
                                   |
              gRPC over UDS / WASM Module Sandbox
                                   |
                                   v
             [ Klien Deployment: Kubernetes Pod ]
             +----------------------------------+
             | Container A: Core Platform Host  |
             | Container B: Tenant Plugin (Sidecar)|
             +----------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Interface SPI & Factory (In-Process Upstream Pattern)
Contoh dasar bagaimana memisahkan algoritma routing order finansial tanpa menyentuh *core engine*:

```go
package main

import (
	"context"
	"errors"
	"fmt"
)

// Transaction mewakili payload transaksi standar enterprise.
type Transaction struct {
	ID     string
	Amount float64
	Route  string
}

// PaymentRouter adalah Extension Port (SPI).
type PaymentRouter interface {
	Route(ctx context.Context, tx *Transaction) (string, error)
}

// Registry memfasilitasi injeksi dependensi modul kustom tanpa merusak core runtime.
var routerRegistry = make(map[string]PaymentRouter)

func RegisterRouter(name string, router PaymentRouter) {
	routerRegistry[name] = router
}

// CoreExecutionEngine tidak memiliki dependensi langsung pada implementasi kustom.
type CoreExecutionEngine struct{}

func (e *CoreExecutionEngine) Execute(ctx context.Context, tx *Transaction) error {
	router, exists := routerRegistry[tx.Route]
	if !exists {
		return fmt.Errorf("router engine untuk %s belum terdaftar", tx.Route)
	}

	targetNode, err := router.Route(ctx, tx)
	if err != nil {
		return fmt.Errorf("routing failure: %w", err)
	}

	fmt.Printf("[Core] Transaksi %s dialihkan ke node: %s\n", tx.ID, targetNode)
	return nil
}

// IMPLEMENTASI KUSTOM KLIEN (Disimpan di repo terpisah atau package extension)
type BespokeClientRouter struct{}

func (b *BespokeClientRouter) Route(ctx context.Context, tx *Transaction) (string, error) {
	if tx.Amount > 1000000 {
		return "HIGH_VALUE_SETTLEMENT_CLUSTER", nil
	}
	return "STANDARD_CLEARING_CLUSTER", nil
}

func main() {
	// Registrasi dilakukan saat bootstrap runtime
	RegisterRouter("ENTERPRISE_CLIENT_X", &BespokeClientRouter{})

	engine := &CoreExecutionEngine{}
	tx := &Transaction{ID: "TX-9901", Amount: 2500000, Route: "ENTERPRISE_CLIENT_X"}

	if err := engine.Execute(context.Background(), tx); err != nil {
		panic(err)
	}
}
```

---

#### B. Practical Example: Out-of-Process Enterprise Plugin Engine via gRPC & Proto
Implementasi kelas produksi menggunakan arsitektur plugin out-of-process terisolasi, lengkap dengan *circuit breaker pattern* dan penanganan timeout.

##### 1. Definisi Kontrak: `proto/extension.proto`
```protobuf
syntax = "proto3";

package extension.v1;

option go_package = "github.com/enterprise/fde/extension/v1;extensionv1";

service TransactionHook {
  rpc BeforeProcess (HookRequest) returns (HookResponse);
}

message HookRequest {
  string transaction_id = 1;
  double amount = 2;
  string currency = 3;
  map<string, string> metadata = 4;
}

message HookResponse {
  bool approved = 1;
  string rejection_reason = 2;
  map<string, string> injected_headers = 3;
}
```

##### 2. Core Extension Host Engine: `core/plugin_host.go`
```go
package core

import (
	"context"
	"fmt"
	"net"
	"sync"
	"time"

	pb "github.com/enterprise/fde/extension/v1"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type PluginClient struct {
	client  pb.TransactionHookClient
	conn    *grpc.ClientConn
	timeout time.Duration
}

type ExtensionManager struct {
	mu      sync.RWMutex
	plugins map[string]*PluginClient
}

func NewExtensionManager() *ExtensionManager {
	return &ExtensionManager{
		plugins: make(map[string]*PluginClient),
	}
}

// ConnectPlugin menghubungkan core host ke unix domain socket plugin klien.
func (m *ExtensionManager) ConnectPlugin(tenantID, socketPath string, timeout time.Duration) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	conn, err := grpc.Dial(
		socketPath,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithContextDialer(func(ctx context.Context, addr string) (net.Conn, error) {
			return net.DialTimeout("unix", addr, timeout)
		}),
	)
	if err != nil {
		return fmt.Errorf("gagal menghubungkan plugin %s: %w", tenantID, err)
	}

	m.plugins[tenantID] = &PluginClient{
		client:  pb.NewTransactionHookClient(conn),
		conn:    conn,
		timeout: timeout,
	}
	return nil
}

// ExecutePreHook mengeksekusi validasi kustom klien dengan boundary fail-safe.
func (m *ExtensionManager) ExecutePreHook(ctx context.Context, tenantID string, req *pb.HookRequest) (*pb.HookResponse, error) {
	m.mu.RLock()
	plugin, exists := m.plugins[tenantID]
	m.mu.RUnlock()

	if !exists {
		// Default behavior jika tenant tidak mengimplementasikan custom hook (Open-Closed Principle)
		return &pb.HookResponse{Approved: true}, nil
	}

	ctxTimeout, cancel := context.WithTimeout(ctx, plugin.timeout)
	defer cancel()

	resp, err := plugin.client.BeforeProcess(ctxTimeout, req)
	if err != nil {
		// Fault-tolerance: Isolasi failure agar plugin yang crash tidak melumpuhkan core
		return nil, fmt.Errorf("plugin execution failure pada tenant %s: %w", tenantID, err)
	}

	return resp, nil
}

func (m *ExtensionManager) Close() {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, p := range m.plugins {
		_ = p.conn.Close()
	}
}
```

##### 3. Implementasi Plugin Lapangan oleh Klien (FDE Deployment): `plugin/client_plugin.go`
```go
package main

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/signal"
	"syscall"

	pb "github.com/enterprise/fde/extension/v1"
	"google.golang.org/grpc"
)

type BankMegaCustomHookServer struct {
	pb.UnimplementedTransactionHookServer
}

func (s *BankMegaCustomHookServer) BeforeProcess(ctx context.Context, req *pb.HookRequest) (*pb.HookResponse, error) {
	// Bespoke Business Rule: Batasi transaksi lebih dari USD 50,000 jika tanpa metadata clearance
	if req.Amount > 50000.00 && req.Currency == "USD" {
		if _, ok := req.Metadata["CLEARANCE_AUTH_LEVEL_2"]; !ok {
			return &pb.HookResponse{
				Approved:        false,
				Rejection_Reason: "Transaksi > 50,000 USD memerlukan regulasi auth clearance level 2",
			}, nil
		}
	}

	return &pb.HookResponse{
		Approved: true,
		Injected_Headers: map[string]string{
			"X-Custom-Audit-Engine": "MegaBank-Node-01",
		},
	}, nil
}

func main() {
	socketPath := "/tmp/bank_mega_hook.sock"
	_ = os.Remove(socketPath)

	listener, err := net.Listen("unix", socketPath)
	if err != nil {
		panic(fmt.Sprintf("Failed to bind socket: %v", err))
	}

	grpcServer := grpc.NewServer()
	pb.RegisterTransactionHookServer(grpcServer, &BankMegaCustomHookServer{})

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		fmt.Printf("Plugin Out-of-Process berjalan pada %s...\n", socketPath)
		if err := grpcServer.Serve(listener); err != nil {
			panic(err)
		}
	}()

	<-sigChan
	fmt.Println("Shutting down plugin gracefully...")
	grpcServer.GracefulStop()
	_ = os.Remove(socketPath)
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Klien:** Konsorsium 4 Bank Sentral & Bank Komersial Multinasional.
- **Sistem Inti:** High-throughput Ledger Platform (Rilis v2.4.0). Beban normal: 40.000 TPS.
- **Masalah:** Salah satu bank menuntut validasi tanda tangan ganda kustom menggunakan HSM (*Hardware Security Module*) lawas proprietary yang membutuhkan modul C/C++ native (*PKCS#11*), yang menghasilkan latensi ~45ms per transaksi.

#### Kegagalan Tim Sebelumnya (Anti-Pattern)
Tim FDE awal menduplikasi repositori utama (*branching* `feature/client-bank-x-pkcs11`), menempelkan pustaka CGO langsung di *core router pipeline*. 
- **Dampak Fatal:** 
  1. *Core Platform* tim merilis v2.5.0 dengan mitigasi kerentanan keamanan tinggi. Tim FDE gagal melakukan *rebase* karena 312 file bentrok (*merge conflicts*).
  2. Alokasi memori CGO di *core execution path* mengalami *memory leak*, meruntuhkan *main process* seluruh node pada jam sibuk perbankan (*segmentation fault*).

#### Intervensi Arsitektur (Solusi Upstream & Plugin)
1. **Isolasi Proses:** FDE merombak integrasi HSM menjadi *sidecar daemon* yang berkomunikasi via IPC Unix Domain Socket (menggunakan zero-copy byte buffers).
2. **Pola Upstream Mainline:** FDE merancang modul `SignatureVerificationSPI` ke repositori inti mainline v2.6.0.
3. **Hasil:**
   - *Core Engine* tetap netral tanpa baris CGO satupun.
   - Kebocoran memori HSM terbatas di dalam *sidecar container*, di-restart oleh Kubernetes tanpa memutus alur pemrosesan ledger utama.
   - Waktu siklus adopsi pembaruan *core engine* oleh klien berkurang dari 3 bulan menjadi 15 menit melalui rolling update image standar.

---

### 9. Trade-offs

```
+-----------------------------------------------------------------------------+
|                      TRADE-OFF EVALUATION MATRIX                            |
+----------------------+--------------------+---------------------------------+
| Arsitektur Pola      | Keuntungan         | Kerugian / Beban Biaya          |
+----------------------+--------------------+---------------------------------+
| Dynamic In-Process   | - Overhead latensi | - Potensi crash seluruh host    |
| Shared Libs (CGO)    |   ekstrem rendah   |   akibat memory leak / segfault |
|                      |   (< 1 µs).        | - Kompilasi silang rumit.       |
+----------------------+--------------------+---------------------------------+
| Out-of-Process       | - Blast radius     | - Latensi transfer context      |
| IPC/gRPC (UDS)       |   terisolasi total.|   IPC (100–300 µs).             |
|                      | - Bahasa bebas.    | - Manajemen lifecycle proses.   |
+----------------------+--------------------+---------------------------------+
| WebAssembly          | - Eksekusi aman di | - Kapabilitas I/O terbatas.     |
| (WASM Engine)        |   dalam memory host| - Tooling ekosistem belum       |
|                      | - Latensi rendah.  |   sepenuhnya matang.            |
+----------------------+--------------------+---------------------------------+
| Direct Code Fork     | - Cepat di awal    | - Maintenance overhead abadi    |
| (Anti-Pattern)       |   (TTV rendah).    |   dan risiko tech debt fatal.   |
+----------------------+--------------------+---------------------------------+
```

---

### 10. Common Mistakes & Troubleshooting

#### 1. "The Tenant-Leak Anti-Pattern"
*Core team* menemukan puluhan kondisi logika spesifik klien yang masuk ke dalam *pull request* mainline.
- **Deteksi:** Jalankan static analysis linter khusus pada CI core:
  ```bash
  # Mencegah nama entitas spesifik klien masuk ke mainline core
  grep -rnEI "BankMega|TenantXYZ|ClientCustom" ./core/pkg/ && exit 1 || exit 0
  ```

#### 2. gRPC Over-the-Network Latency Explosion
FDE mengimplementasikan out-of-process plugin tetapi menghubungkannya via TCP loopback (`127.0.0.1:50051`) alih-alih Unix Domain Sockets (`unix:///tmp/plugin.sock`).
- **Gejala:** Lonjakan latensi 2-4x dan degradasi socket exhaust di bawah beban tinggi (60.000+ ephemeral ports terpakai dalam status `TIME_WAIT`).
- **Solusi:** Wajibkan alur komunikasi lokal berbasis Unix Domain Sockets (UDS) untuk komunikasi node yang sama.

#### 3. Proto Contract Drift Silent Failure
Perubahan tipe field pada protobuf ekstensi menyebabkan serialisasi gagal secara parsial tanpa memicu *build error*.
- **Mitigasi:** Pasang alat bantu linting API seperti `buf breaking --against '.git#branch=main'` di dalam pipeline integrasi berkelanjutan (CI).

---

### 11. Best Practices (Production Checklist)

#### Arsitektur & Kustomisasi
- [ ] Logika varian klien dipisahkan secara fisik dari repositori *core* atau diisolasi di balik abstraksi dynamic driver/plugin interface.
- [ ] Komunikasi out-of-process intra-node menggunakan Unix Domain Socket (bukan loopback IP).
- [ ] Alokasi alur *fail-open* vs *fail-close* ditentukan secara eksplisit pada setiap plugin crash.

#### CI/CD & Governance
- [ ] Consumer-Driven Contract Tests (e.g., via Pact atau Protobuf compatibility checker) aktif di setiap commit.
- [ ] Drift Detection pipeline dijalankan harian untuk mengukur deviasi antara branch klien dan mainline platform.
- [ ] Tidak ada dependency circular antara modul *core* dan plugin extension host.

#### Operasional & Monitoring
- [ ] Eksekusi plugin memiliki batasan timeout eksplisit (SLA standar: max 50ms).
- [ ] Setiap pemanggilan plugin memancarkan metrik observabilitas: `extension_execution_duration_seconds{tenant="id", status="ok|error"}`.
- [ ] Circuit breaker terpasang untuk menonaktifkan plugin kustom secara otomatis jika error rate melampaui 5% dalam rolling window 1 menit.

---

### 12. Hands-on Practice

Buat dan operasikan seluruh infrastruktur pengujian upstreaming dan isolasi plugin pada direktori `hands-on/m02/`.

#### Langkah 1: Inisialisasi Lingkungan
```bash
mkdir -p hands-on/m02/{proto,core,plugin}
cd hands-on/m02
go mod init enterprise.fde/upstreaming
```

#### Langkah 2: Buat Kontrak Protobuf
Simpan ke `proto/service.proto`:
```protobuf
syntax = "proto3";
package validator;
option go_package = "./proto";

service EnrichmentService {
  rpc Enrich (DataPayload) returns (DataPayload);
}

message DataPayload {
  string id = 1;
  string payload = 2;
  bool is_enriched = 3;
}
```

Kompilasi kontrak:
```bash
# Pastikan protoc dan plugins telah terpasang
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
export PATH="$PATH:$(go env GOPATH)/bin"

protoc --go_out=. --go-grpc_out=. proto/service.proto
```

#### Langkah 3: Implementasikan Core Mainline Engine
Simpan kode berikut ke `core/main.go`:
```go
package main

import (
	"context"
	"fmt"
	"net"
	"time"

	pb "enterprise.fde/upstreaming/proto"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

func main() {
	socket := "/tmp/enrichment.sock"
	conn, err := grpc.Dial(socket, 
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithContextDialer(func(ctx context.Context, addr string) (net.Conn, error) {
			return net.Dial("unix", addr)
		}),
	)
	if err != nil {
		panic(err)
	}
	defer conn.Close()

	client := pb.NewEnrichmentServiceClient(conn)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	res, err := client.Enrich(ctx, &pb.DataPayload{
		Id:      "CORE-DATA-001",
		Payload: "Raw-Unprocessed-Alpha",
	})
	if err != nil {
		fmt.Printf("[Core ERROR] Plugin enrichment gagal: %v\n", err)
		return
	}

	fmt.Printf("[Core SUCCESS] Data Berhasil Diproses: %+v\n", res)
}
```

#### Langkah 4: Implementasikan Tenant Plugin
Simpan kode berikut ke `plugin/server.go`:
```go
package main

import (
	"context"
	"fmt"
	"net"
	"os"
	"strings"

	pb "enterprise.fde/upstreaming/proto"
	"google.golang.org/grpc"
)

type Server struct {
	pb.UnimplementedEnrichmentServiceServer
}

func (s *Server) Enrich(ctx context.Context, req *pb.DataPayload) (*pb.DataPayload, error) {
	fmt.Printf("[Plugin] Menerima data dari core: %s\n", req.Id)
	return &pb.DataPayload{
		Id:          req.Id,
		Payload:     strings.ToUpper(req.Payload) + "-PROCESSED-BY-BESPOKE-PLUGIN",
		IsEnriched: true,
	}, nil
}

func main() {
	socket := "/tmp/enrichment.sock"
	_ = os.Remove(socket)

	l, err := net.Listen("unix", socket)
	if err != nil {
		panic(err)
	}
	s := grpc.NewServer()
	pb.RegisterEnrichmentServiceServer(s, &Server{})
	fmt.Println("[Plugin] Daemon aktif pada /tmp/enrichment.sock...")
	if err := s.Serve(l); err != nil {
		panic(err)
	}
}
```

#### Langkah 5: Eksekusi dan Verifikasi
Buka dua terminal terpisah:
```bash
# Terminal 1: Jalankan Plugin
go run plugin/server.go

# Terminal 2: Jalankan Core Engine
go run core/main.go
```

**Verifikasi Output Berhasil:**
Terminal core mencetak payload yang dimodifikasi oleh plugin tanpa menyatukan basis kode keduanya ke satu proses runtime.

---

### 13. Exercise

#### Tingkat Easy
Modifikasi implementasi `hands-on/m02/core/main.go` untuk menangani skenario di mana file socket `/tmp/enrichment.sock` tidak ditemukan. Terapkan logika fallback agar core tidak panik, melainkan melanjutkan pemrosesan data standar secara internal.
*Expected Result:* Program mencetak log peringatan bahwa plugin tidak aktif dan mengembalikan payload asli dengan flag `is_enriched = false`.

#### Tingkat Medium
Implementasikan interceptor logging pada file `plugin/server.go` yang menghitung latensi eksekusi *hook* dalam satuan mikrodetik ($\mu s$) dan menyuntikkan execution latency tersebut ke dalam respons header metadata gRPC.
*Expected Result:* Header respons metadata gRPC memuat key `x-latency-micros` yang terbaca oleh core client.

#### Tingkat Hard
Bangun mekanisme deteksi konkurensi pada core platform yang mampu memanggil 3 plugin secara paralel (Scatter-Gather Pattern) menggunakan Goroutine dan Channels:
1. Validasi Keamanan (Security Verification)
2. Normalisasi Format (Format Normalization)
3. Audit Engine Logging (Audit Trail)
Jika salah satu plugin gagal atau melebihi timeout 150ms, batalkan panggilan plugin lain yang masih berjalan menggunakan `context.WithCancelCause` dan kembalikan state error deterministik ke pemanggil utama.
*Expected Result:* Implementasi pipeline paralel berlatensi rendah dengan timeout context propagation yang ketat.

---

### 14. Challenge

#### Skenario: Air-Gapped High-Frequency Synchronization Engine
Anda ditugaskan sebagai Principal FDE untuk platform pertukaran data intelijen pertahanan. Klien menggunakan instance *air-gapped* (tanpa koneksi internet publik) dari platform inti Anda. Klien memiliki tim developer in-house yang membuat **142 custom security patches** pada *fork* repositori v1.12.0 selama kurun waktu 18 bulan tanpa koordinasi dengan core platform team.

Kini, tim core merilis arsitektur v2.0.0 yang mengubah format engine database relational ke distributed key-value event store. Klien menolak upgrade v2.0.0 karena takut kehilangan 142 fitur kustom mereka, namun regulator mewajibkan upgrade karena adanya mitigasi CVE kritis pada versi 2.0.0.

#### Tugas Rekayasa Anda:
1. Rancang skema mitigasi teknis dan arsitektur ekstensibilitas (RFC Spec Document).
2. Tentukan algoritma komputasi untuk mengidentifikasi tingkat tumpang tindih (*code overlap/AST drift*) antara 142 patch klien dan kapabilitas baru di v2.0.0.
3. Rancang pola transformasi dari modifikasi langsung di core engine menuju *dynamic declarative policy engine* atau *sandboxed execution model* tanpa membuka kode internal inti v2.0.0 kepada pihak ketiga.
4. Buat peta jalan (*cutover plan*) tanpa down-time yang memvalidasi integritas data antar versi berbeda secara deterministik.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa definisi dari *Fork Gravity* dalam konteks Forward Deployed Engineering?
2. Mengapa penggunaan Unix Domain Socket lebih disukai daripada Network Loopback (TCP 127.0.0.1) untuk out-of-process extension lokal?
3. Sebutkan kelemahan utama dari pola in-process dynamic loading (seperti CGO / Go Plugin package)!
4. Kapan sebuah modifikasi lokal klien layak diusulkan untuk menjadi bagian dari *mainline core* platform?
5. Apa peran Consumer-Driven Contract Testing dalam arsitektur platform yang dapat diekstensi (*extensible platform*)?

#### Pertanyaan Intermediate
6. Bagaimana cara mencegah *thread exhaustion* pada core host engine saat plugin out-of-process mengalami kondisi *deadlock*?
7. Jelaskan bagaimana prinsip *Hexagonal Architecture (Ports and Adapters)* memfasilitasi proses upstreaming kode!
8. Apa kelemahan mekanisme WASM (*WebAssembly*) jika dibandingkan dengan out-of-process gRPC plugin pada eksekusi komputasi intensif I/O?
9. Bagaimana strategi menangani backward compatibility pada Protobuf field ID saat sebuah custom hook upstreamed ke core?
10. Mengapa conditional checking berbasis tenant ID (`if tenant == "X"`) di core platform dianggap sebagai failure mode terburuk dalam FDE?

#### Skenario Kasus Produksi
11. **Skenario A:** Plugin kustom klien memakan alokasi CPU 100% pada node Kubernetes tempat instance Core Platform berjalan, memicu Kubernetes OOM-killer atau CPU throttling yang memperlambat transaksi klien lain. Strategi arsitektur isolasi apa yang harus diterapkan?
12. **Skenario B:** Tim Core merilis versi patch darurat v1.8.1 untuk menutup celah zero-day exploit. Namun, sistem CI klien gagal melakukan deploy otomatis karena build plugin mereka rusak akibat perubahan private struct di Core yang tidak sengaja bocor ke public package. Di mana letak pelanggaran prinsip desainnya?
13. **Skenario C:** Sebuah sistem enterprise memproses 100.000 events/detik. Tim FDE ingin menambahkan plugin kustom untuk inspeksi payload tiap event. Komunikasi via out-of-process gRPC UDS menimbulkan latency overhead total 20 detik untuk 100.000 events. Pendekatan arsitektur apa yang dapat memangkas latensi ini ke batas sub-milidetik tanpa mengorbankan stabilitas core?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Basic
1. **Fork Gravity:** Akumulasi perbedaan teknis antara *client-specific fork* dan *upstream core repository* yang makin lama makin lebar, membuat biaya pemeliharaan, integrasi, dan rebase tumbuh eksponensial hingga platform tidak bisa diperbarui lagi.
2. **Unix Domain Socket:** Menghindari overhead traversal network stack TCP/IP lokal (tidak ada TCP checksum, packet framing, context switching port allocation), menghasilkan *throughput* lebih tinggi dan *latency* lebih rendah.
3. **Kelemahan Go Plugin / CGO:** Tidak memiliki batas isolasi memori (*fault isolation*); crash (segfault/panic) pada plugin runtime akan langsung mematikan *host process* utama. Kompilasi silang (*cross-compilation*) juga sangat kaku.
4. **Kelayakan Upstream:** Ketika suatu kebutuhan abstraksi data/alur fungsionalitas dibutuhkan oleh lebih dari satu klien enterprise, atau saat modifikasi tersebut memperkuat skalabilitas modul dasar tanpa menyertakan asumsi bisnis unik suatu pihak.
5. **Contract Testing:** Memastikan interface antara host dan extension tetap kompatibel di seluruh versi tanpa perlu menjalankan end-to-end integration test lingkungan klien yang kompleks.

#### Intermediate
6. **Mencegah Thread Exhaustion:** Terapkan konteks eksekusi berbasis *deadline/timeout*, batasi *concurrency pool* dengan worker queue terikat (*bounded worker pool*), dan gunakan *circuit breaker* (misal: Hystrix pattern).
7. **Hexagonal Architecture:** Inti bisnis berada di dalam domain terisolasi (*inside*), sedangkan protokol eksternal/integrasi klien adalah *adapters* (*outside*). Modifikasi klien hanya menyentuh adapter layer, menjaga kestabilan port/domain core.
8. **Kelemahan WASM untuk I/O:** WASM secara bawaan berjalan di sandbox tanpa akses host network/filesystem langsung tanpa interface WASI (*WebAssembly System Interface*), yang memiliki keterbatasan abstraksi driver dan asynchronous socket handling.
9. **Backward Compatibility Protobuf:** Jangan pernah mengubah field number numerik yang sudah dirilis. Tandai field lama sebagai `reserved` jika dihapus, dan tambahkan fungsionalitas baru dengan nomor tag baru yang opsional (*optional semantics*).
10. **Anti-pattern Tenant ID Check:** Melanggar Open-Closed Principle (OCP), mencemari domain core dengan context proprietary pihak ketiga, memicu *merge conflicts* masif, dan mengekspos rahasia implementasi klien ke klien lain.

#### Kasus Produksi
11. **Solusi Skenario A:** Pindahkan deployment plugin dari in-process/daemon bersama menjadi pola arsitektur **Dedicated Out-of-Process Pod (Sidecar atau Independent Microservice)** dengan resource quota eksplisit di Kubernetes (`resources.limits.cpu` dan `resources.limits.memory`). Pasang CPU hard-limit cgroups sehingga konsumsi komputasi plugin tidak pernah merusak pod Core Platform.
12. **Solusi Skenario B:** Pelanggaran enkapsulasi dan kebocoran boundary (*leaky abstraction*). Core platform melanggar hukum *Hyrum's Law* dan *Semantic Versioning*. Solusi: Public API SPI harus dipisahkan ke modul SDK independen dengan interface contract tertutup (Protobuf). Core logic internal tidak boleh diakses langsung oleh modul plugin klien.
13. **Solusi Skenario C:** Mengalihkan arsitektur dari out-of-process gRPC ke **In-Memory Shared Memory IPC** (seperti Apache Arrow / POSIX Shared Memory segments) atau menggunakan embedded runtime sandboxing **WASM (e.g., wazero runtime)**. Pendekatan ini memungkinkan core engine berbagi akses buffer memori langsung ke modul inspeksi tanpa overhead serialisasi JSON/Protobuf dan context switching IPC kernel.

---

### 16. Summary

1. **Bespoke Forking adalah Utang Teknis Berbunga Tinggi:** Membangun *branch* terpisah untuk setiap klien enterprise adalah jalan pintas yang merusak skalabilitas organisasi FDE.
2. **Arsitektur Berbasis SPI Menjamin Upstream Sederhana:** Inti dari upstreaming yang sukses bukan negosiasi tim, melainkan arsitektur sistem yang modular sejak hari pertama melalui *Ports & Adapters*, decoupling kontrak Protobuf, dan runtime berbasis plugin.
3. **Isolasi Blast-Radius Bersifat Mandatory:** Kustomisasi klien di level operasional produksi enterprise wajib memiliki isolasi komputasi yang ketat. Error, crash, memory leak, atau performa lambat dari kode spesifik klien tidak boleh meruntuhkan stabilitas *core transaction engine*.
4. **Upstreaming adalah Proses Kontinu:** Fitur spesifik klien harus selalu diperlakukan sebagai kandidat plugin sementara, yang pada akhirnya diabstraksikan, distandarisasi, dan di-upstream ke *mainline core* demi mempertahankan integritas evolusi platform jangka panjang.