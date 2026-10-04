## SEKSI 01 — IDENTITAS MODUL

*   **Modul ID:** `ARCH-06-07-01`
*   **Nama Modul:** Scalability, Resilience & High Availability: Horizontal Scaling Patterns, Circuit Breakers, Bulkheads, Disaster Recovery (RPO/RTO), Multi-Region Active-Active
*   **Kategori:** 06-Architecture-and-System-Design
*   **Jalur Kurikulum:** Software Architect
*   **Tingkat Kesulitan:** Advanced / Principal
*   **Estimasi Waktu Belajar:** 6 - 8 Jam
*   **Prasyarat:** Pemahaman mendalam tentang Distributed Systems Fundamentals, Jaringan Komputer (TCP/IP, DNS, BGP), Protokol Komunikasi (gRPC, REST), Database Internal (Transaksional, Replikasi, ACID), dan Desain Microservices.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1.  **Mendiagnosis dan Menghilangkan Bottleneck Skalabilitas:** Merancang arsitektur sistem berbasis *stateless compute* dan *partitioned state* yang mampu melakukan scale-out secara elastis di bawah beban trafik ekstrim tanpa degradasi performa linear.
2.  **Mengimplementasikan Pola Ketahanan (Resilience Patterns):** Merekayasa mekanisme isolasi kegagalan (*fault isolation*) menggunakan *Circuit Breaker* adaptif dan *Bulkhead Compartmentalization* guna meredam efek *cascading failure*.
3.  **Mengonstruksi Strategi Disaster Recovery Berbasis Metrik RPO dan RTO:** Menghitung toleransi kehilangan data (*Recovery Point Objective*) dan batas waktu pemulihan (*Recovery Time Objective*), serta memvalidasi kesesuaian arsitektur penyimpanan (sinkron vs asinkron).
4.  **Merancang Arsitektur Multi-Region Active-Active:** Menyusun topologi multi-region terdistribusi dengan routing lalu lintas global, resolusi konflik data (CRDT / Last-Write-Wins), serta mitigasi *split-brain scenario* di tingkat komputasi dan penyimpanan.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            [SISTEM TINGKAT TINGGI]
                                       |
    +----------------------------------+----------------------------------+
    |                                  |                                  |
    v                                  v                                  v
[SKALABILITAS]                   [KETAHANAN (RESILIENCE)]      [KETERSEDIAAN (HA & DR)]
    |                                  |                                  |
    +--> Horizontal Scaling            +--> Fault Isolation               +--> Disaster Recovery
    |    |-- Stateless Services        |    |-- Circuit Breaker (Closed,  |    |-- RPO (Data Loss Window)
    |    |-- State Offloading (Redis)  |    |    Open, Half-Open)         |    +-- RTO (Downtime Duration)
    |    +-- Partitioning/Sharding     |    +-- Bulkhead Pattern          |
    |                                  |        |-- Thread Pool Isolation +--> Multi-Region Topology
    +--> Load Balancing Topology       |        +-- Semaphore Throttling       |-- Active-Passive (Pilot Light)
         |-- L4 (TCP/UDP IP Hash)      +--> Graceful Degradation               +-- Active-Active
         +-- L7 (Path/Header/Least)         |-- Fallback Caching                    |-- GSLB / Anycast DNS
                                            +-- Load Shedding & Jitter              +-- Cross-Region Conflict
                                                                                        Resolution (CRDT/LWW)
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

1.  **Hukum Kegagalan Tak Terhindarkan (Murphy's Law in Distributed Systems):** Dalam sistem monolitik, *failure* bersifat biner: aplikasi hidup atau mati. Dalam sistem terdistribusi berskala besar (ratusan *node* dan layanan), sistem berada dalam kondisi konstan di mana *sebagian komponen pasti sedang mengalami kegagalan* (*partial failure*). Tanpa mitigasi, satu layanan lambat (*slow dependency*) akan mengonsumsi *thread pool* pemanggil, memicu kehabisan sumber daya berantai (*thread starvation*), dan melumpuhkan seluruh platform (*cascading failure*).
2.  **Dampak Finansial Downtime:** Ketersediaan 99.9% (*three nines*) mengakibatkan toleransi *downtime* ~8.76 jam per tahun. Bagi sistem finansial, *e-commerce global*, atau *core banking*, angka ini merepresentasikan potensi kerugian jutaan dolar per jam. Ketersediaan tingkat 99.999% (*five nines*) hanya mentoleransi ~5.26 menit *downtime* per tahun, yang secara absolut menuntut otomatisasi *failover* multi-region tanpa intervensi manual.
3.  **Batasan Fisika (Speed of Light & Latency):** Skalabilitas vertikal (*scale-up*) memiliki batas keras fisik perangkat keras (*diminishing returns* dan batas daya/CPU). Sementara itu, replikasi data global terkendala oleh kecepatan rambat cahaya di serat optik (~5 ms per 1000 km RTT). Memahami pola *Active-Active* dan konsistensi data terdistribusi adalah satu-satunya cara memberikan latensi rendah bagi pengguna global sembari mempertahankan integritas data.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Skalabilitas Horizontal (Scale-Out)
Skalabilitas horizontal adalah kemampuan sistem untuk menangani pertambahan beban kerja dengan menambahkan lebih banyak unit komputasi (*node*), bukan meningkatkan kapasitas perangkat keras dari satu mesin (*scale-up*). Syarat mutlak dari pola ini adalah pemisahan antara logika eksekusi (*stateless compute*) dan persistensi (*stateful layer*).

### 2. Circuit Breaker Pattern
Pola stabilitas perangkat lunak yang membungkus pemanggilan fungsi yang rawan gagal ke layanan eksternal. Pola ini memonitor frekuensi kegagalan. Jika rasio kegagalan melewati ambang batas (*threshold*), *circuit breaker* akan membuka sirkuit (*trips open*), dan seluruh permintaan berikutnya langsung dibatalkan (*fast-fail*) atau dialihkan ke logika cadangan (*fallback*) tanpa membebani sistem eksternal yang sedang terdegradasi.

### 3. Bulkhead Pattern
Pola isolasi sumber daya yang terinspirasi dari sekat-sekat kedap air pada lambung kapal laut. Jika satu sekat bocor, air hanya menggenangi kompartemen tersebut, mencegah kapal tenggelam secara keseluruhan. Dalam arsitektur sistem, *bulkhead* mengisolasi alokasi sumber daya kritis (seperti *thread pools*, koneksi database, atau antrean memori) berdasarkan tipe layanan/domain, mencegah kehabisan sumber daya global akibat satu komponen abnormal.

### 4. Disaster Recovery (DR): RPO dan RTO
*   **Recovery Point Objective (RPO):** Batas toleransi usia data yang hilang saat bencana terjadi, diukur dalam satuan waktu. Contoh: RPO = 5 menit mengindikasikan bahwa data yang tersimpan maksimal 5 menit sebelum insiden boleh hilang, menuntut frekuensi *snapshot* atau replikasi asinkron dengan delta maksimal 5 menit.
*   **Recovery Time Objective (RTO):** Durasi waktu maksimal yang ditoleransi untuk memulihkan sistem dari kondisi mati total hingga kembali beroperasi secara normal bagi pengguna akhir.

### 5. Multi-Region Active-Active
Topologi di mana infrastruktur independen didistribusikan ke minimal dua wilayah geografis berbeda, di mana *setiap wilayah* melayani trafik baca (*read*) dan tulis (*write*) secara bersamaan dalam kondisi normal. Pola ini menuntut sinkronisasi data dua arah (*bi-directional replication*) dan resolusi konflik data.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Mekanisme Horizontal Scaling
1.  **State Externalization:** Komputasi didesain tanpa memori lokal (*in-memory session* dilarang). Seluruh status dipindahkan ke *cache cluster* terdistribusi (Redis/KeyDB) atau *durable datastore*.
2.  **Load Distribution:**
    *   **L4 Balancing (Transport Layer):** Melakukan *packet forwarding* berbasis kombinasi IP sumber/tujuan dan port TCP/UDP (menggunakan Maglev, IPVS, atau AWS NLB). Bekerja dengan *overhead* latensi sangat rendah.
    *   **L7 Balancing (Application Layer):** Melakukan inspeksi muatan HTTP/gRPC, evaluasi TLS termination, parsing header, dan perutean berbasis *path* URL (misal Envoy, Nginx, Traefik).

### Mekanisme Circuit Breaker (State Machine)
Sirkuit beroperasi dalam tiga status utama:
*   **CLOSED:** Kondisi normal. Semua panggilan diteruskan ke dependensi. Panggilan sukses dan gagal dicatat dalam jendela geser (*sliding window*, berbasis waktu atau jumlah panggilan). Jika *failure rate* melampaui ambang batas ($P_{fail} \ge \tau$), status berubah menjadi **OPEN**.
*   **OPEN:** Panggilan ke dependensi langsung diputus (*fast-fail*) tanpa membuat koneksi jaringan. Komponen pemanggil mengeksekusi *fallback handler*. *Timer* transisi dijalankan ($T_{cooldown}$).
*   **HALF-OPEN:** Setelah $T_{cooldown}$ kedaluwarsa, sirkuit mengizinkan sejumlah terbatas permintaan uji coba (*canary requests*, misal $N=10$). Jika seluruh atau mayoritas uji coba sukses, sirkuit kembali ke status **CLOSED**. Jika ada kegagalan, sirkuit langsung kembali ke status **OPEN** dan memperpanjang *timer* secara eksponensial.

```
                  +-----------------------------------+
                  |                                   |
                  v                                   |
           +--------------+   P_fail >= Threshold     +--------------+
           |              |-------------------------->|              |
           |    CLOSED    |                           |     OPEN     |
           |              |<--------------------------|              |
           +--------------+      Uji Coba Berhasil    +--------------+
                  ^                                          |
                  |                                          | T_cooldown
                  |                                          | Expired
                  |         +-------------------+            |
                  +---------|     HALF-OPEN     |<-----------+
                            | (Canary Requests) |
                            +-------------------+
                                     |
                                     | Uji Coba Gagal
                                     v
                           (Kembali ke status OPEN)
```

### Mekanisme Bulkhead
Diterapkan melalui dua pendekatan primer:
1.  **Thread Pool Isolation:** Setiap dependensi eksternal dialokasikan *thread pool* terdedikasi dengan kapasitas tetap ($MaxThreads$, $QueueSize$). Jika dependensi A macet, hanya *thread pool* A yang habis; *thread pool* untuk dependensi B tetap berjalan tanpa terpengaruh.
2.  **Semaphore Isolation:** Membatasi jumlah eksekusi konkuren yang masuk ke klien dependensi menggunakan penghitung atomik (*atomic counter*). Pendekatan ini tidak memerlukan *context switching* antar-*thread*, menjadikannya hemat memori dengan latensi lebih rendah daripada model *thread pool*, namun tidak dapat menghentikan operasi secara asinkron (*non-interruptible* saat timeout).

### Mekanisme Replikasi Data & Resolusi Konflik Active-Active
Dalam arsitektur *Active-Active*, trafik tulis diterima di Region A dan Region B secara bersamaan:
1.  **Latency Constraints:** Replikasi sinkron lintas wilayah terpisah ribuan kilometer akan merusak *throughput* akibat latensi jaringan trans-kontinental (contoh: Frankfurt ke Singapura $\approx 160\text{ ms RTT}$). Oleh karena itu, replikasi data antar-region *wajib* dilakukan secara **asinkron**.
2.  **Write Conflicts:** Menulis ke baris (*row*) atau entitas data yang sama di Region A dan Region B dalam jendela propagasi asinkron memicu *write collision*.
3.  **Conflict Resolution Models:**
    *   **Last-Write-Wins (LWW):** Menggunakan stempel waktu fisik (*physical timestamp*). Pendekatan ini rentan terhadap deviasi waktu antar-server (*clock drift* / *NTP skew*).
    *   **Conflict-Free Replicated Data Types (CRDTs):** Struktur data matematika terdesentralisasi yang secara deterministik menggabungkan (*merge*) perubahan paralel tanpa memerlukan koordinasi terpusat (contoh: *P-N Counter*, *OR-Set*).
    *   **Partition-by-Key (Geo-Sharding):** Mengeliminasi konflik secara arsitektural dengan memastikan satu pengguna atau entitas data selalu diarahkan ke *satu primary region* untuk operasi tulis (berdasarkan *hashing* `user_id` atau lokasi domisili pengguna), sementara region lain bertindak sebagai replika baca dan DR instan.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah arsitektur multi-region Active-Active komprehensif yang memadukan perutean global, *stateless compute*, *edge resilience*, dan replikasi data terdistribusi:

```
+===================================================================================================================+
|                                              GLOBAL TRAFFIC MANAGEMENT                                            |
|                                [Anycast IP / Global Server Load Balancer (GSLB)]                                   |
|                        - Evaluasi Geolocation, RTT Latency, & Regional Health Status -                             |
+===================================================================================================================+
                                         /                                           \
                   [Region A Direct / Primary]                           [Region B Direct / Secondary]
                                       /                                               \
                                      v                                                 v
+=======================================================+     +=======================================================+
| REGION 1: US-EAST (Active)                            |     | REGION 2: EU-CENTRAL (Active)                         |
|-------------------------------------------------------|     |-------------------------------------------------------|
|  [Edge Gateway / L7 Envoy Reverse Proxy]              |     |  [Edge Gateway / L7 Envoy Reverse Proxy]              |
|         |                                             |     |         |                                             |
|         v                                             |     |         v                                             |
|  [APPLICATION CORE SERVICES]                          |     |  [APPLICATION CORE SERVICES]                          |
|  +-------------------------------------------------+  |     |  +-------------------------------------------------+  |
|  | Order Service Pod (Stateless Instance)          |  |     |  | Order Service Pod (Stateless Instance)          |  |
|  |                                                 |  |     |  |                                                 |  |
|  |  +-------------------------------------------+  |  |     |  |  +-------------------------------------------+  |  |
|  |  | BULKHEAD ENCLAVE                          |  |  |     |  |  | BULKHEAD ENCLAVE                          |  |  |
|  |  | - Payment ThreadPool (Cap: 20, Queue: 5)  |  |  |     |  |  | - Payment ThreadPool (Cap: 20, Queue: 5)  |  |  |
|  |  | - Inventory Semaphore (Permits: 50)       |  |  |     |  |  | - Inventory Semaphore (Permits: 50)       |  |  |
|  |  +-------------------------------------------+  |  |     |  |  +-------------------------------------------+  |  |
|  |         |                                       |  |     |  |         |                                       |  |
|  |         v                                       |  |     |  |         v                                       |  |
|  |  +-------------------------------------------+  |  |     |  |  +-------------------------------------------+  |  |
|  |  | CIRCUIT BREAKER PROXY                     |  |  |     |  |  | CIRCUIT BREAKER PROXY                     |  |  |
|  |  | Failure Rate Threshold: 50%               |  |  |     |  |  | Failure Rate Threshold: 50%               |  |  |
|  |  | Sliding Window Size: 100 reqs             |  |  |     |  |  | Sliding Window Size: 100 reqs             |  |  |
|  |  | Fallback: Cache Provider / Degraded Resp  |  |  |     |  |  | Fallback: Cache Provider / Degraded Resp  |  |  |
|  |  +-------------------------------------------+  |  |     |  |  +-------------------------------------------+  |  |
|  +-------------------------------------------------+  |     |  +-------------------------------------------------+  |
|         |                               |             |     |         |                               |             |
|         v (Local Read/Write)            |             |     |         v (Local Read/Write)            |             |
|  +------------------------+             |             |     |  +------------------------+             |             |
|  | Distributed Cache      |             |             |     |  | Distributed Cache      |             |             |
|  | (Local Redis Cluster)  |             |             |     |  | (Local Redis Cluster)  |             |             |
|  +------------------------+             |             |     |  +------------------------+             |             |
|                                         v             |     |                                         v             |
|  +-------------------------------------------------+  |     |  +-------------------------------------------------+  |
|  | PERSISTENCE LAYER                               |  |     |  | PERSISTENCE LAYER                               |  |
|  | Distributed Database Node (Region 1 Shard)      |  |     |  | Distributed Database Node (Region 2 Shard)      |  |
|  | Engine: CockroachDB / Cassandra / Spanner Engine|  |     |  | Engine: CockroachDB / Cassandra / Spanner Engine|  |
|  +-------------------------------------------------+  |     |  +-------------------------------------------------+  |
+=======================================================+     +=======================================================+
                           |                                                               |
                           |               CROSS-REGION REPLICATION LINK                   |
                           +===============================================================+
                           |   - Asynchronous WAL Streaming / CDC (Debezium/Kafka)         |
                           |   - Consensus Mechanism: Multi-Raft Leader Leasing / CRDTs    |
                           |   - Network Optimization: Dedicated Cloud Interconnect        |
                           +===============================================================+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi Circuit Breaker fundamental berbasis *Thread-Safe State Machine* dalam bahasa pemrograman Go, menggunakan pendekatan *consecutive failure count* dan *cooldown window*:

```go
package main

import (
	"errors"
	"fmt"
	"sync"
	"time"
)

type State int

const (
	StateClosed State = iota
	StateHalfOpen
	StateOpen
)

func (s State) String() string {
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

var ErrCircuitOpen = errors.New("circuit breaker is OPEN: fast-failing traffic")

type CircuitBreaker struct {
	mu               sync.Mutex
	state            State
	failureThreshold int
	failureCount     int
	successCount     int
	requiredSuccesses int
	cooldownDuration time.Duration
	lastStateChange  time.Time
}

func NewCircuitBreaker(failureThreshold int, requiredSuccesses int, cooldown time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		state:             StateClosed,
		failureThreshold: failureThreshold,
		requiredSuccesses: requiredSuccesses,
		cooldownDuration:  cooldown,
		lastStateChange:   time.Now(),
	}
}

func (cb *CircuitBreaker) Execute(action func() error) error {
	cb.mu.Lock()

	// Evaluasi transisi dari OPEN ke HALF-OPEN berdasarkan kedaluwarsa waktu
	if cb.state == StateOpen && time.Since(cb.lastStateChange) > cb.cooldownDuration {
		cb.state = StateHalfOpen
		cb.lastStateChange = time.Now()
		cb.failureCount = 0
		cb.successCount = 0
		fmt.Println("[CB TRANSITION] State berubah: OPEN -> HALF-OPEN")
	}

	// Jika sirkuit masih berstatus OPEN, tolak eksekusi secara instan
	if cb.state == StateOpen {
		cb.mu.Unlock()
		return ErrCircuitOpen
	}

	cb.mu.Unlock()

	// Eksekusi fungsi dependensi
	err := action()

	cb.mu.Lock()
	defer cb.mu.Unlock()

	if err != nil {
		cb.handleFailure()
		return err
	}

	cb.handleSuccess()
	return nil
}

func (cb *CircuitBreaker) handleFailure() {
	cb.failureCount++
	fmt.Printf("[CB EXEC] Eksekusi gagal. Failure count: %d/%d (State: %s)\n",
		cb.failureCount, cb.failureThreshold, cb.state)

	if cb.state == StateClosed && cb.failureCount >= cb.failureThreshold {
		cb.state = StateOpen
		cb.lastStateChange = time.Now()
		fmt.Println("[CB TRANSITION] Ambang batas gagal terlampaui. State berubah: CLOSED -> OPEN")
	} else if cb.state == StateHalfOpen {
		// Satu kegagalan pada status Half-Open langsung memicu status OPEN kembali
		cb.state = StateOpen
		cb.lastStateChange = time.Now()
		fmt.Println("[CB TRANSITION] Uji coba Half-Open gagal. State kembali ke: OPEN")
	}
}

func (cb *CircuitBreaker) handleSuccess() {
	if cb.state == StateHalfOpen {
		cb.successCount++
		fmt.Printf("[CB EXEC] Uji coba Half-Open sukses. Success count: %d/%d\n",
			cb.successCount, cb.requiredSuccesses)

		if cb.successCount >= cb.requiredSuccesses {
			cb.state = StateClosed
			cb.lastStateChange = time.Now()
			cb.failureCount = 0
			cb.successCount = 0
			fmt.Println("[CB TRANSITION] Stabilisasi tercapai. State berubah: HALF-OPEN -> CLOSED")
		}
	} else if cb.state == StateClosed {
		// Reset failure count jika berhasil dalam kondisi CLOSED
		cb.failureCount = 0
	}
}

func main() {
	cb := NewCircuitBreaker(3, 2, 2*time.Second)

	// Simulasi pemanggilan layanan eksternal yang mengalami degradasi
	unstableCall := func(succeed bool) error {
		if !succeed {
			return errors.New("upstream service error 500")
		}
		return nil
	}

	fmt.Println("--- Fase 1: Mengirim Permintaan Gagal ---")
	for i := 1; i <= 4; i++ {
		err := cb.Execute(func() error {
			return unstableCall(false)
		})
		if err != nil {
			fmt.Printf("Permintaan %d tertolak/gagal: %v\n", i, err)
		}
	}

	fmt.Println("\n--- Fase 2: Sirkuit OPEN, Permintaan Ditolak Otomatis (Fast-Fail) ---")
	err := cb.Execute(func() error {
		return unstableCall(true)
	})
	fmt.Printf("Permintaan saat open: %v\n", err)

	fmt.Println("\n--- Fase 3: Menunggu Durasi Cooldown Selesai... ---")
	time.Sleep(2100 * time.Millisecond)

	fmt.Println("\n--- Fase 4: Menguji Sirkuit (Transisi ke HALF-OPEN) ---")
	// Uji coba 1 sukses
	_ = cb.Execute(func() error { return unstableCall(true) })
	// Uji coba 2 sukses -> memulihkan sirkuit ke CLOSED
	_ = cb.Execute(func() error { return unstableCall(true) })

	fmt.Println("\n--- Fase 5: Status Sirkuit Setelah Pemulihan ---")
	err = cb.Execute(func() error {
		fmt.Println("Eksekusi dependensi normal berjalan lancar.")
		return nil
	})
	fmt.Printf("Status eksekusi akhir: %v\n", err)
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah contoh praktis integrasi **Semaphore-based Bulkhead Pattern** dikombinasikan dengan mekanisme **Timeout Protection** dan **Adaptive Fallback Execution**. Solusi ini mencegah pemanggilan dependensi pembayaran menghabiskan *thread* web server secara massal saat *gateway* pembayaran eksternal mengalami penurunan performa:

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"
)

var (
	ErrBulkheadLimitExceeded = errors.New("bulkhead capacity reached: request rejected to protect resources")
	ErrExecutionTimeout      = errors.New("operation timed out: upstream latency SLA breached")
)

// BulkheadResilienceCoordinator mengatur isolasi konkurensi dan batasan latensi
type BulkheadResilienceCoordinator struct {
	concurrencySemaphore chan struct{}
	executionTimeout     time.Duration
}

func NewBulkheadCoordinator(maxConcurrentCalls int, timeout time.Duration) *BulkheadResilienceCoordinator {
	return &BulkheadResilienceCoordinator{
		concurrencySemaphore: make(chan struct{}, maxConcurrentCalls),
		executionTimeout:     timeout,
	}
}

// ExecuteWithResilience mengeksekusi operasi terlindungi di dalam isolasi sekat Bulkhead
func (b *BulkheadResilienceCoordinator) ExecuteWithResilience(
	ctx context.Context,
	primaryAction func(ctx context.Context) (string, error),
	fallbackAction func(ctx context.Context, reason error) (string, error),
) (string, error) {

	// 1. Uji ketersediaan slot sekat isolasi (Non-blocking TryAcquire)
	select {
	case b.concurrencySemaphore <- struct{}{}:
		// Slot isolasi berhasil diperoleh
		defer func() { <-b.concurrencySemaphore }()
	default:
		// Bulkhead penuh, alihkan seketika ke Fallback
		return fallbackAction(ctx, ErrBulkheadLimitExceeded)
	}

	// 2. Terapkan Deadline Timeout spesifik pada batas operasi
	timeoutCtx, cancel := context.WithTimeout(ctx, b.executionTimeout)
	defer cancel()

	resultChan := make(chan string, 1)
	errChan := make(chan error, 1)

	// 3. Eksekusi tugas pada goroutine terisolasi
	go func() {
		res, err := primaryAction(timeoutCtx)
		if err != nil {
			errChan <- err
			return
		}
		resultChan <- res
	}()

	// 4. Sinkronisasi pemrosesan hasil vs pembatalan context / timeout
	select {
	case <-timeoutCtx.Done():
		if errors.Is(timeoutCtx.Err(), context.DeadlineExceeded) {
			return fallbackAction(ctx, ErrExecutionTimeout)
		}
		return fallbackAction(ctx, timeoutCtx.Err())

	case err := <-errChan:
		return fallbackAction(ctx, err)

	case result := <-resultChan:
		return result, nil
	}
}

func main() {
	// Definisikan Bulkhead: Maksimum 2 eksekusi konkuren, SLA timeout 500ms
	coordinator := NewBulkheadCoordinator(2, 500*time.Millisecond)

	primaryPaymentGateway := func(paymentID string, simulateDelay time.Duration) func(context.Context) (string, error) {
		return func(ctx context.Context) (string, error) {
			fmt.Printf("[%s] Menghubungi payment gateway eksternal...\n", paymentID)
			select {
			case <-time.After(simulateDelay):
				return fmt.Sprintf("PAYMENT_SUCCESS: Transaksi %s berhasil diproses", paymentID), nil
			case <-ctx.Done():
				return "", ctx.Err()
			}
		}
	}

	fallbackHandler := func(paymentID string) func(context.Context, error) (string, error) {
		return func(ctx context.Context, reason error) (string, error) {
			// Fallback: Masukkan ke durable queue lokal untuk diproses secara rekonsiliasi asinkron
			fmt.Printf(">>> [%s] FALLBACK TRIGGERED! Alasan: %v. Mengalihkan ke Dead-Letter Queue...\n", paymentID, reason)
			return fmt.Sprintf("PAYMENT_QUEUED: Transaksi %s disimpan untuk pemrosesan offline", paymentID), nil
		}
	}

	var wg sync.WaitGroup

	// Simulasi 5 request serentak: Slot hanya ada 2.
	// Sebagian akan lolos, sebagian terlempar karena Bulkhead penuh, dan sebagian timeout.
	requests := []struct {
		id    string
		delay time.Duration
	}{
		{"TX-101", 200 * time.Millisecond}, // Berhasil (slot didapat, tidak timeout)
		{"TX-102", 700 * time.Millisecond}, // Masuk slot, tapi timeout (>500ms)
		{"TX-103", 200 * time.Millisecond}, // Ditolak Bulkhead (slot penuh oleh TX-101 & TX-102)
		{"TX-104", 200 * time.Millisecond}, // Ditolak Bulkhead
		{"TX-105", 100 * time.Millisecond}, // Ditolak Bulkhead
	}

	for _, req := range requests {
		wg.Add(1)
		go func(r struct {
			id    string
			delay time.Duration
		}) {
			defer wg.Done()
			ctx := context.Background()
			output, _ := coordinator.ExecuteWithResilience(
				ctx,
				primaryPaymentGateway(r.id, r.delay),
				fallbackHandler(r.id),
			)
			fmt.Printf("<== Output Akhir [%s]: %s\n", r.id, output)
		}(req)
	}

	wg.Wait()
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektur | Opsi A | Opsi B | Trade-off Analysis & Dampak Desain |
| :--- | :--- | :--- | :--- |
| **Pola Skalabilitas** | **Scale-Up (Vertical)** | **Scale-Out (Horizontal)** | *Scale-up* tidak memerlukan penanganan konsistensi terdistribusi dan jaringan kompleks, tetapi memiliki batasan perangkat keras absolut (*ceiling limit*) dan *single point of failure*. *Scale-out* menawarkan skalabilitas teoritis tanpa batas, namun memperkenalkan latensi jaringan, kebutuhan orkestrasi kluster, serta tantangan konsistensi data terdistribusi (*distributed state management*). |
| **Isolasi Bulkhead** | **Thread Pool Isolation** | **Semaphore Isolation** | *Thread Pool* menyediakan isolasi total terhadap eksekusi komputasi serta mampu menginterupsi *thread* yang mengalami *freeze*, namun memakan alokasi memori substansial dan menghasilkan *overhead context switching*. *Semaphore* sangat cepat dan hemat memori (*lightweight atomic counters*), tetapi tidak dapat menghentikan komputasi dependensi internal secara paksa jika *blocking* bersifat native/tanpa *timeout awareness*. |
| **Sinkronisasi DR Data** | **Replikasi Sinkron** | **Replikasi Asinkron** | Replikasi sinkron menjamin **RPO = 0** (tanpa kehilangan data saat bencana), namun latensi transaksi meningkat drastis proporsional terhadap jarak fisik (*round-trip latency*), membatasi *write throughput*. Replikasi asinkron memberikan performa tulis sangat tinggi dan latensi minimal, namun memperkenalkan jendela data hilang saat terjadi *crash* tak terduga (**RPO > 0**). |
| **Multi-Region Strategy**| **Active-Passive (Hot Standby)**| **Active-Active (Multi-Master)**| *Active-Passive* secara operasional jauh lebih sederhana (tanpa penanganan *write conflict* lintas region), namun menyia-nyiakan 50% kapasitas komputasi (*idle resources*) dan RTO terikat pada durasi propagasi DNS saat *failover*. *Active-Active* memaksimalkan efisiensi utilisasi perangkat keras dan menghasilkan latensi terendah bagi pengguna global, namun memperkenalkan kompleksitas tinggi dalam resolusi konflik data (misal split-brain risk, penanganan konsistensi kausal). |

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan Exponential Backoff Disertai Full Jitter:**
    Jangan pernah melakukan *retry* langsung dengan interval konstan. Hal ini akan memicu *thundering herd problem* yang melumpuhkan layanan pemulihan. Formula standar:
    $$\text{Sleep} = \text{random}(0, \min(M, T_{\text{base}} \times 2^{\text{attempt}}))$$
    di mana $M$ adalah batas maksimum durasi tunggu (*cap*), dan $T_{\text{base}}$ adalah durasi inisial.
2.  **Terapkan Idempotency Key pada Seluruh Mutasi Data:**
    Dalam topologi *resilient* di mana *retry* dan *circuit breaker* aktif, permintaan HTTP/gRPC dapat diproses sebagian sebelum terjadi kegagalan jaringan. Semua API bertipe non-idempoten (seperti `POST /payments`) wajib menyertakan atribut unik `Idempotency-Key` di header, diverifikasi melalui atomik *conditional-insert* di tingkat penyimpanan sebelum memicu transaksi.
3.  **Batasi Ukuran Sliding Window pada Metrik Sirkuit:**
    Gunakan pendekatan *sliding time window* (misal 10-60 detik) daripada *rolling count* yang terlalu besar. *Sliding count* yang terlalu besar akan menahan sirkuit dalam kondisi OPEN lebih lama dari yang dibutuhkan, memperlambat proses *self-healing*.
4.  **Bungkus Fallback dalam Batas Kegagalan Independen:**
    Logika *fallback* tidak boleh mengakses database utama atau sistem hilir yang berpotensi turut terdegradasi. *Fallback* yang baik harus bersifat deterministik: membaca data dari *in-memory cache*, mengembalikan data parsial (*graceful degradation*), atau mengalihkan ke *message broker durable*.
5.  **Audit Jendela RPO Secara Proaktif Menggunakan Heartbeat CDC:**
    Monitor latensi replikasi antar-wilayah secara *real-time*. Jika *replication lag* melewati ambang batas toleransi RPO (contoh: *lag* replikasi terukur > 10 detik saat SLA RPO adalah 5 detik), sistem pemantauan wajib memicu alarm darurat sebelum bencana fisik terjadi.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1.  **Menghubungkan Semua Dependensi ke Default Connection Pool:**
    Banyak arsitek membiarkan klien HTTP atau ORM menggunakan *connection pool* global bawaan sistem (*shared resource pool*). Jika satu endpoint dependensi pihak ketiga macet (*hanging*), seluruh *pool* koneksi aplikasi terisi penuh oleh antrean yang menunggu timeout, memicu kelumpuhan total pada endpoint internal lain yang sebenarnya beroperasi normal.
2.  **Mengabaikan Sinkronisasi Jam Fisik (NTP Clock Skew) pada Active-Active:**
    Menggunakan algoritma resolusi *Last-Write-Wins* (LWW) murni berbasis stempel waktu mesin (`System.currentTimeMillis()`) tanpa perangkat keras atomik (*TrueTime* pada Google Spanner). *Clock drift* antar-mesin virtual di AWS/GCP sebesar 200ms dapat menimpa data transaksi baru dengan data lama yang memiliki stempel waktu jam drift yang lebih maju.
3.  **Active-Active Berbasis Database dengan Distributed Locking Lintas Benua:**
    Merancang sistem komputasi *Active-Active* di dua wilayah berbeda namun keduanya mengakses basis data terdistribusi yang mewajibkan mekanisme *two-phase locking* (2PL) lintas benua untuk setiap baris data. Latensi round-trip (RTT) inter-region akan membatasi sistem pada skala maksimal 5–10 transaksi per detik per data lock, menghancurkan *throughput*.
4.  **Pengabaian Mekanisme Load Shedding:**
    Hanya mengandalkan *Auto-scaling* horizontal saat lonjakan trafik masif (*flash crowd*). Skalabilitas horizontal berbasis *virtual machine* atau kontainer membutuhkan waktu inisialisasi (30 detik hingga 5 menit). Tanpa mekanisme *load shedding* (menolak trafik berlebih menggunakan HTTP status 503 secara instan di layer paling depan/gateway), sistem akan kolaps sebelum *node* baru sempat diaktifkan.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario Desain Arsitektur
Anda adalah Principal Architect pada entitas sistem kliring pembayaran perbankan digital. Sistem ini memproses otorisasi debit transaksi kartu dengan volume puncak 15.000 TPS (*transactions per second*).

### Spesifikasi Kebutuhan Sistem:
*   **Target Availability:** 99.999% (*Five Nines* = toleransi downtime maksimal ~5.26 menit per tahun).
*   **RPO:** 0 detik (Kehilangan data transaksi finansial sama sekali tidak dapat ditoleransi).
*   **RTO:** Kurang dari 30 detik untuk *failover* total antar-wilayah.
*   **Topologi Wilayah:** Dua data center aktif (Wilayah Alpha dan Wilayah Beta) yang berjarak 350 km satu sama lain, dengan latensi jaringan jaringan privat antar-wilayah terukur $RTT = 6\text{ ms}$.

### Instruksi Penugasan:
1.  **Rancang Topologi Komputasi & Routing:** Gambarkan bagaimana DNS global, BGP Anycast, atau Global Application Load Balancer mendistribusikan trafik, dan bagaimana sistem mendeteksi degradasi kesehatan salah satu DC dalam 5 detik.
2.  **Desain Skema Persistensi Berbasis RPO=0:** Berikan analisis apakah arsitektur ini memungkinkan penggunaan replikasi asinkron atau wajib replikasi sinkron berbasis konsensus (*Multi-Raft / Paxos*). Buktikan secara matematis korelasi antara latensi tambahan $6\text{ ms}$ terhadap SLA latensi otorisasi kartu (maksimum 100 ms per transaksi).
3.  **Skema Pembagian Partition Key:** Definisikan skema pembagian partisi (*sharding/routing key*) yang menjamin tidak adanya *two-way active write collision* pada akun rekening yang sama saat kedua DC aktif menerima transaksi.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Sebuah sistem e-commerce menerapkan Circuit Breaker pada layanan integrasi logistik ekspedisi. Parameter yang dikonfigurasi adalah: Window Size = 50 request, Failure Rate Threshold = 40%, Cooldown Period = 30 detik. Dari 50 request terakhir, 22 request mengalami HTTP 504 Gateway Timeout. Apa status sirkuit saat ini, dan apa yang terjadi jika datang request ke-51?**
    * A. Status sirkuit CLOSED; request ke-51 langsung diteruskan ke dependensi.
    * B. Status sirkuit HALF-OPEN; request ke-51 dikirim sebagai *canary probe*.
    * C. Status sirkuit OPEN; request ke-51 langsung dibatalkan (*fast-fail*) atau diarahkan ke *fallback*.
    * D. Status sirkuit OPEN; sistem memblokir request ke-51 hingga thread timeout selesai secara alami.
    * *Jawaban yang Benar:* **C**
    * *Penjelasan:* Rasio kegagalan terhitung adalah $22 / 50 = 44\%$. Karena $44\% > 40\%$ (ambang batas), pemutus sirkuit melompat ke status OPEN. Pada status OPEN, semua request baru selama durasi *cooldown* (30 detik) langsung ditolak seketika (*fast-fail*) tanpa membuat koneksi jaringan, guna melindungi ketersediaan sumber daya pemanggil.

2. **Karakteristik utama yang membedakan Semaphore Bulkhead dari Thread Pool Bulkhead adalah:**
    * A. Semaphore Bulkhead mengizinkan antrean request yang tak terbatas (*unbounded queuing*).
    * B. Semaphore Bulkhead tidak mengisolasi eksekusi pada thread terpisah, melainkan mengontrol konkurensi di atas thread pemanggil yang sama secara sinkron.
    * C. Thread Pool Bulkhead memiliki jejak memori (*memory footprint*) yang jauh lebih kecil daripada Semaphore Bulkhead.
    * D. Semaphore Bulkhead mampu membatalkan komputasi yang terhenti secara internal (*hard cancel*) menggunakan mekanisme interupsi thread.
    * *Jawaban yang Benar:* **B**
    * *Penjelasan:* Semaphore Bulkhead bekerja sebagai penghitung izin atomik (*atomic lease counter*) pada alur *thread* pemanggil langsung. Hal ini menghindari *overhead context-switch* dan alokasi *thread stack* terpisah, namun kehilangan kemampuan untuk secara paksa memotong (*interrupt*) eksekusi tugas jika dependensi tidak kooperatif terhadap *cancellation token*.

3. **Perusahaan FinTech menetapkan SLA: RPO = 0 dan RTO < 10 detik. Manakah kombinasi infrastruktur database yang valid untuk memenuhi kriteria tersebut?**
    * A. Replikasi Master-Replica Asinkron dengan *scheduled snapshot dump* setiap 15 menit.
    * B. Replikasi Sinkron multi-zona dengan konsensus quorum terdistribusi (misal CockroachDB/Spanner) dan orkestrasi *automated health-checking failover*.
    * C. Replikasi Log-Shipping Asinkron berbasis Kafka CDC lintas region trans-atlantik.
    * D. Replikasi Dual-Master Aktif-Aktif dengan resolusi Last-Write-Wins (LWW) berbasis NTP sinkronisasi harian.
    * *Jawaban yang Benar:* **B**
    * *Penjelasan:* RPO = 0 secara absolut mensyaratkan replikasi sinkron atau penulisan berbasis kuorum mayoritas (*consensus-based commit*), di mana commit transaksi tidak diakui hingga tersimpan di lebih dari satu kegagalan node independen. RTO < 10 detik mensyaratkan transisi pemilihan leader (*leader election*) yang terotomatisasi secara total melalui konsensus sistem tanpa campur tangan operator manusia.

4. **Dalam konteks multi-region Active-Active, apa bahaya utama dari strategi resolusi konflik Last-Write-Wins (LWW) yang mengandalkan stempel waktu fisik (physical system clock)?**
    * A. Menghasilkan pemakaian CPU 100% pada layer proxy jaringan.
    * B. Tidak dapat digabungkan dengan mekanisme Circuit Breaker.
    * C. Fenomena *clock drift* dapat menyebabkan transaksi baru ditimpa dan dihapus secara permanen oleh transaksi yang lebih lama yang memiliki stempel waktu lebih maju akibat ketidakakuratan jam server.
    * D. Menyebabkan database beralih otomatis ke mode *read-only*.
    * *Jawaban yang Benar:* **C**
    * *Penjelasan:* Jam fisik di server terdistribusi mengalami pergeseran (*clock drift* / *skew*) akibat fluktuasi termal dan keterbatasan NTP. Jika server A memiliki jam yang mendahului server B sebanyak 100ms, mutasi data yang lebih lama di server A akan dinilai "lebih baru" daripada mutasi di server B, mengakibatkan modifikasi data valid terbaru terhapus secara silent (*silent data loss*).

5. **Apa fungsi utama dari menyuntikkan "Jitter" ke dalam algoritma Exponential Backoff saat terjadi kegagalan sistem terdistribusi?**
    * A. Mengurangi alokasi bandwidth jaringan secara keseluruhan.
    * B. Mengacak waktu tunggu percobaan ulang (*retry*) agar beban koneksi dari ribuan klien tidak menghantam server target secara simultan (*thundering herd problem*).
    * C. Mengenkripsi payload HTTP selama proses retry berlangsung.
    * D. Mengurangi nilai latency hingga nol pada layer socket.
    * *Jawaban yang Benar:* **B**
    * *Penjelasan:* Tanpa jitter, ribuan klien yang gagal pada saat bersamaan ($t_0$) akan menghitung durasi tunggu yang identik (misal $2^1, 2^2, 2^3$), memicu lonjakan trafik berkala secara masif secara sinkron (*thundering herd / retry storms*) yang secara periodik menenggelamkan kembali server yang sedang berusaha pulih. Jitter memecah konsentrasi antrean tersebut ke dalam distribusi waktu yang acak seragam.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

*   **Buku Standar Industri:**
    *   *Release It!: Design and Deploy Production-Ready Software (2nd Edition)* oleh Michael T. Nygard (Pragmatic Bookshelf) — *Buku primer untuk referensi Circuit Breaker & Bulkhead.*
    *   *Designing Data-Intensive Applications* oleh Martin Kleppmann (O'Reilly Media) — *Rujukan utama mengenai replikasi, konsensus, dan konsistensi data terdistribusi.*
*   **Whitepaper Teknis:**
    *   *Spanner: Google’s Globally-Distributed Database* (OSDI 2012) — James C. Corbett et al.
    *   *Dynamo: Amazon’s Highly Available Key-value Store* (SOSP 2007) — Giuseppe DeCandia et al.
*   **Dokumentasi Resmi Kerangka Kerja:**
    *   *Envoy Proxy Circuit Breaking Architecture Documentation* (envoyproxy.io).
    *   *AWS Well-Architected Framework: Reliability Pillar Whitepaper*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1.  **Skalabilitas Horizontal Mensyaratkan Statelessness:** Scale-out tidak dapat diimplementasikan secara optimal tanpa eksternalisasi *state* komputasi ke cluster penyimpanan khusus dan penerapan load balancing L4/L7 yang tepat.
2.  **Isolasi Kegagalan Mencegah Keruntuhan Sistem:** Kegagalan parsial adalah keniscayaan dalam sistem terdistribusi. *Circuit Breaker* mencegah pemborosan siklus komputasi pada layanan yang mati (*fail fast*), sedangkan *Bulkhead* membatasi zona dampak kegagalan (*blast radius*) agar tidak merembet ke seluruh ekosistem.
3.  **DR adalah Fungsi Bisnis Berbasis Angka:** Metrik RPO mendefinisikan batasan kehilangan data yang diizinkan (menentukan pemilihan arsitektur replikasi sinkron vs asinkron), sedangkan RTO mengukur toleransi waktu pemulihan (menentukan derajat otomatisasi *failover*).
4.  **Multi-Region Active-Active Merupakan Kompromi Latensi vs Konsistensi:** Tidak ada koordinasi instan melintasi jarak geografis yang jauh. Arsitektur multi-region yang sukses mengandalkan *geo-sharding*, partisi domain tulis, atau algoritma resolusi data deterministik seperti CRDT untuk menghindari penguncian terdistribusi (*distributed locking*) lintas benua.

---

## SEKSI 17 — GLOSARIUM

*   **Blast Radius:** Luasnya jangkauan dampak negatif pada ekosistem platform ketika sebuah subsistem tunggal mengalami kegagalan fungsi.
*   **Clock Drift:** Deviasi pengukuran waktu pada jam fisik sistem komputer lokal dibandingkan standar waktu universal absolut (UTC) akibat ketidaksempurnaan perangkat keras osilator kuarsa.
*   **Conflict-Free Replicated Data Type (CRDT):** Struktur data terdesentralisasi yang dapat direplikasi di banyak node secara independen tanpa koordinasi, dan dapat digabungkan secara deterministik tanpa konflik.
*   **Fail-Fast:** Prinsip desain sistem yang menghentikan operasi secara instan dan melaporkan kegagalan jika kondisi prasyarat tidak terpenuhi, mencegah pemborosan sumber daya dan latensi antrean.
*   **Idempotency:** Properti dari operasi komputasi di mana pemanggilan fungsi secara berulang kali dengan parameter identik menghasilkan status sistem yang sama persis seperti pemanggilan tunggal pertama.
*   **Jitter:** Komponen variasi keacakan probabilistik yang ditambahkan ke algoritma perhitungan jeda waktu (*backoff*) untuk mencegah konkurensi periodik yang sinkron antar-komponen.
*   **Split-Brain:** Anomali berbahaya dalam cluster terdistribusi di mana sub-grup node yang terputus koneksi jaringannya sama-sama mengasumsikan peran sebagai koordinator utama (*primary/leader*), menyebabkan divergensi dan korupsi data permanen.
*   **Thundering Herd:** Kondisi saat sejumlah besar klien komputasi mencoba mengakses sumber daya yang sama secara bersamaan segera setelah terjadi suatu *event* atau pemulihan *service*, memicu kelebihan beban instan pada server.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Titik Rawan Pemahaman Peserta:** Peserta sering salah memahami bahwa *Active-Active* berarti *setiap baris data* dapat ditimpa secara simultan dari region mana pun tanpa konsekuensi. Tekankan kembali batasan fisika (*speed of light* pada latensi jaringan serat optik). Ajak peserta menghitung biaya RTT (Round Trip Time) lintas benua untuk membuktikan kemustahilan *two-phase commit* (2PC) global pada trafik skala tinggi.
*   **Penekanan Simulasi Hands-on:** Pastikan peserta mengeksekusi skenario uji coba dengan mematikan dependensi tiruan (*mock failure injection*) guna menyaksikan transisi status *Circuit Breaker* dari CLOSED $\to$ OPEN $\to$ HALF-OPEN $\to$ CLOSED secara visual di konsol terminal mereka.
*   **Alokasi Waktu yang Disarankan:**
    *   Teori Skalabilitas & Ketahanan (Bulkhead/Circuit Breaker): 2 Jam.
    *   Bedah Kode Implementasi (Golang/Concurrency): 2 Jam.
    *   Teori RPO/RTO & Arsitektur Multi-Region: 2 Jam.
    *   Latihan Hands-on & Diskusi Desain: 2 Jam.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi:** 1.0.0
*   **Tanggal Rilis:** 2026-03-30
*   **Penulis:** Senior Technical Curriculum Architect
*   **Perubahan Utama:**
    *   Rilis kurikulum awal Arsitektur Sistem Terdistribusi Tingkat Lanjut.
    *   Penyusunan kode implementasi referensi Go untuk Circuit Breaker dan Bulkhead.
    *   Penambahan skema perhitungan RPO/RTO dan mitigasi konflik data Active-Active.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `ARCH-06-06-01`: *Data Architecture at Scale: Distributed Caching Strategies, Database Sharding, Read/Write Splitting, and CDC Patterns*
*   **Modul Saat Ini:** `ARCH-06-07-01`: *Scalability, Resilience & High Availability: Horizontal Scaling Patterns, Circuit Breakers, Bulkheads, Disaster Recovery (RPO/RTO), Multi-Region Active-Active*
*   **Modul Berikutnya:** `ARCH-06-08-01`: *Event-Driven Architecture & Reactive Systems: Event Sourcing, CQRS, Message Brokers, Outbox Pattern, and Saga Orchestration*