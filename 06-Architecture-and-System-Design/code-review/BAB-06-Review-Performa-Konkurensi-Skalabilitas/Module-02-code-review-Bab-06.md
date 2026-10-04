# BAB 06: Review Performa, Konkurensi, & Skalabilitas
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Mengidentifikasi dan Memitigasi Cacat Konkurensi Tingkat Rendah:** Mendeteksi *data race*, *race condition*, *deadlock*, *livelock*, *lock contention*, dan *starvation* pada PR (*Pull Request*) tanpa hanya bergantung pada eksekusi runtime.
2. **Mengevaluasi Karakteristik Memori dan CPU-Cache:** Mengaudit kode terhadap anomali performa mikro seperti *false sharing*, alokasi memori berlebih yang memicu *Garbage Collection (GC) thrashing*, serta penyalahgunaan sinkronisasi primitif.
3. **Menganalisis Batasan Transaksi dan Konkurensi Basis Data:** Menilai dampak PR terhadap *database connection pool*, tingkat isolasi transaksi (*read committed*, *repeatable read*, *serializable*), serta strategi penguncian (*optimistic* vs *pessimistic locking*).
4. **Merancang Pipeline Review Otomatis:** Mengintegrasikan kakas profil statis/dinamis, *race detector*, dan uji beban berbasis regresi ke dalam alur *Continuous Integration* (CI).
5. **Menyeimbangkan Kompromi Arsitektur:** Mengambil keputusan teknis berbasis data mengenai *throughput*, latensi *p99*, kompleksitas kode, dan biaya infrastruktur saat meninjau sistem terdistribusi.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:
- **Model Memori (Memory Model):** Konsep dasar *happens-before relationship*, memori *heap* vs *stack*, serta *atomic operations* (CAS - *Compare-And-Swap*).
- **Primitif Sinkronisasi:** Penggunaan Mutex, RWMutex, Semaphore, Channel, dan Condition Variables.
- **Arsitektur Sistem Operasi:** Thread kernel vs User-space thread/Coroutines (misalnya: Goroutine pada Go atau Virtual Threads pada Java), serta *context switching overhead*.
- **Transaksional Basis Data:** Prinsip ACID, anomali baca (*dirty read*, *non-repeatable read*, *phantom read*), dan pembuatan indeks b-tree.

---

### 3. Concept & Internal Architecture

Dalam rekayasa perangkat lunak enterprise, masalah performa dan konkurensi jarang muncul pada lingkungan *staging* dengan beban rendah. Masalah ini bersifat probabilistik dan laten, meledak hanya saat terjadi lonjakan trafik konkuren di produksi.

```
+-----------------------------------------------------------------------------------+
|                                 CPU Die                                           |
|                                                                                   |
|  +-----------------------------+        +-----------------------------+           |
|  |           Core 0            |        |           Core 1            |           |
|  |  +-----------------------+  |        |  +-----------------------+  |           |
|  |  | L1 Data Cache (32KB)  |  |        |  | L1 Data Cache (32KB)  |  |           |
|  |  +-----------------------+  |        |  +-----------------------+  |           |
|  |  | L2 Cache (512KB)      |  |        |  | L2 Cache (512KB)      |  |           |
|  |  +-----------+-----------+  |        |  +-----------+-----------+  |           |
|  +--------------|--------------+        +--------------|--------------+           |
|                 +-----------------------+--------------+                          |
|                                         |                                         |
|                       +-----------------+-----------------+                       |
|                       |        Shared L3 Cache (16MB)     |                       |
|                       +-----------------+-----------------+                       |
+-----------------------------------------|-----------------------------------------+
                                          |
                               +----------+----------+
                               |     Main Memory     |
                               +---------------------+
```

#### A. Hardware Level: Cache Coherency & False Sharing
Komputer modern menggunakan protokol koherensi *cache* (seperti MESI: *Modified, Exclusive, Shared, Invalid*). Unit terkecil transfer memori adalah *Cache Line* (umumnya 64 byte). 

Jika dua variabel independen digunakan oleh dua *thread* berbeda pada dua inti CPU terpisah, namun kedua variabel tersebut berada di dalam *cache line* 64-byte yang sama, modifikasi pada satu variabel akan memaksa CPU membatalkan (*invalidate*) seluruh baris *cache* di inti lainnya. Fenomena ini disebut **False Sharing**. Akibatnya, latensi memori melonjak dari ~1ns (L1) ke ~50-100ns (Main Memory) tanpa adanya penguncian logis antar-*thread*.

#### B. Runtime Level: The Scheduling & Synchronization Overhead
Ketika meninjau kode konkuren (misal: Go runtime dengan model scheduler M:P:N atau JVM dengan OS-thread wrapping):
- **Lock Contention:** Terjadi ketika beberapa eksekutor bersaing memperebutkan satu *lock* (`sync.Mutex`). Sistem akan memindahkan eksekutor dari *running state* ke *waiting queue*, memicu *kernel-space context switch* yang memakan ribuan siklus CPU.
- **Unbounded Concurrency:** Menginisialisasi *goroutine* atau *thread* secara bebas tanpa batas (*unbounded pool*) menyebabkan kehabisan alokasi memori *stack*, penumpukan beban pada GC, serta *thread starvation*.

#### C. Database Level: Lock Granularity & Serialization Bottlenecks
Pada layer persistensi, review arsitektur harus memeriksa apakah perubahan kode memperkenalkan eskalasi kunci dari *Row-Level Lock* ke *Table-Level Lock*, atau mengeksekusi operasi jaringan eksternal di dalam blok transaksi yang memicu antrean kunci (*lock wait timeout*).

---

### 4. Why & What

| Dimensi | Mengapa Ini Penting (*Why*) | Apa yang Harus Ditinjau (*What*) |
| :--- | :--- | :--- |
| **Data Integrity** | Kondisi balapan (*Race Condition*) menghasilkan korupsi data *silent* tanpa melempar pengecualian fatal. | Mutasi status bersama (*shared state*), penggunaan struktur data aman (*thread-safe*), dan visibilitas memori. |
| **Predictable Latency** | Antrean kunci yang panjang mendegradasi *p99 latency*, menyebabkan kegagalan bertingkat (*cascading failure*). | Durasi penahanan *lock* (*critical section*), alokasi I/O dalam transaksi, penggunaan pembacaan non-pemblokir. |
| **System Throughput** | Efisiensi paralelisasi CPU menurun drastis akibat *lock contention* dan fragmentasi memori. | Pola partisi data, *lock stripping*, struktur data non-pemblokir (*lock-free/CAS*), dan *worker pools*. |
| **Resource Saturation** | Kode yang tidak membersihkan sumber daya memicu kebocoran memori, deskriptor berkas, atau koneksi DB. | Penutupan sumber daya (`defer`, `try-with-resources`), pembatalan *context*, batas waktu I/O (*timeouts*). |

---

### 5. How: Workflow Review Performa & Konkurensi

Saat sebuah PR menyentuh alur data dengan konkurensi tinggi, terapkan protokol tinjauan sistematis berikut:

```
[Mulai Review PR]
       |
       v
[1. Identifikasi Shared State] 
       |---> Apakah ada struktur data/pointer yang diakses >1 thread?
       |     NO  --> Lanjut ke Analisis I/O
       |     YES --> Periksa mekanisme sinkronisasi (Mutex, Channel, Atomic)
       v
[2. Analisis Critical Section]
       |---> Apakah terdapat operasi I/O / Network Call di dalam Lock?
       |     YES --> REJECT: Blokir PR, pindahkan I/O ke luar Lock
       |     NO  --> Lanjut ke Cek Granularitas Kunci
       v
[3. Periksa Batas Sumber Daya (Boundedness)]
       |---> Apakah ada worker spawn tanpa batas (misal: go worker() per request)?
       |     YES --> REJECT: Wajib gunakan Bounded Worker Pool / Semaphore
       |     NO  --> Lanjut ke Transaksi DB
       v
[4. Audit Transaksi Basis Data]
       |---> Berapa lama transaksi terbuka? Apakah ada 'SELECT FOR UPDATE' tanpa limit?
       |     Pola Optimistic Locking valid? Idempotensi terjamin?
       v
[5. Verifikasi Otomatis]
       |---> Jalankan `-race`, cek alokasi via pprof/benchmark regresi di CI.
       v
[PR Disetujui / Ditolak dengan Solusi Spesifik]
```

---

### 6. Analogy & Diagram ASCII

#### A. Analogi: Loket Jalan Tol (Granularitas Lock)

- **Coarse-Grained Locking:** Seluruh jalan tol dengan 10 jalur ditutup total setiap kali satu mobil melewati satu loket pembayaran. Aman dari tabrakan, tetapi antrean mengular hingga puluhan kilometer (Throughput hancur).
- **Fine-Grained Locking:** Setiap gardu tol memiliki sensor independen. Jalur 1 tidak memengaruhi Jalur 2.
- **Lock Contention:** 10.000 mobil diarahkan masuk hanya ke 1 gardu tol yang sama secara bersamaan.

```
COARSE-GRAINED LOCK (Bottleneck Parah)
[Trafik Masuk] ===> [ GLOBAL LOCK (Hanya 1 Mobil Bergerak) ] ===> [Keluar]

FINE-GRAINED / SHARDED LOCK (Skalabilitas Maksimal)
[Trafik Jalur 1] ===> [Lock Shard 1] ===> [Keluar]
[Trafik Jalur 2] ===> [Lock Shard 2] ===> [Keluar]
[Trafik Jalur 3] ===> [Lock Shard 3] ===> [Keluar]
```

#### B. False Sharing Visualization

Dua inti CPU memproses dua variabel independen, namun berada pada baris *cache* yang sama:

```
64-Byte Cache Line
+-----------------------------------+-----------------------------------+
| Variable A (8 Bytes) - Diubah CPU 0| Variable B (8 Bytes) - Diubah CPU 1|
+-----------------------------------+-----------------------------------+
  ^                                   ^
  |                                   |
Core 0 menulis A                   Core 1 menulis B
[Cache Line INVALIDATED di Core 1] [Cache Line INVALIDATED di Core 0]
===> Bus Traffic Melonjak Tajam & CPU Stalls Terjadi Berulang Kali <===
```

---

### 7. Simple & Practical Examples

#### A. Simple Example: Deteksi Race Condition & False Sharing

##### Bad Implementation (Anti-Pattern)
```go
package counter

// BadCounter mengalami False Sharing jika diakses sebagai array multi-core,
// serta rentan race condition jika method Add tidak atomic.
type BadCounter struct {
	CountA uint64 // 8 byte
	CountB uint64 // 8 byte (berada pada 64-byte cache line yang sama dengan CountA)
}

func (c *BadCounter) IncrementA() {
	c.CountA++ // DATA RACE: Mutasi tanpa sinkronisasi
}

func (c *BadCounter) IncrementB() {
	c.CountB++ // DATA RACE: Mutasi tanpa sinkronisasi
}
```

##### Good Implementation (Enterprise Production Pattern)
```go
package counter

import (
	"sync/atomic"
)

// GoodCounter menggunakan padding untuk mencegah False Sharing pada arsitektur 64-byte cache line,
// serta primitive atomic untuk menjamin memory ordering dan thread-safety tanpa overhead OS mutex.
type GoodCounter struct {
	CountA uint64
	_      [7]uint64 // 56-byte cache line padding (Total 64 bytes)
	CountB uint64
	_      [7]uint64 // 56-byte cache line padding (Total 64 bytes)
}

func (c *GoodCounter) IncrementA() {
	atomic.AddUint64(&c.CountA, 1)
}

func (c *GoodCounter) IncrementB() {
	atomic.AddUint64(&c.CountB, 1)
}
```

---

#### B. Practical Enterprise Example: High-Throughput Inventory Ledger

Kasus: Sistem alokasi inventaris gudang yang menangani ribuan transaksi paralel per detik tanpa mengunci seluruh basis data atau membocorkan memori.

##### Anti-Pattern (PR yang Harus Ditolak saat Review)
```go
// ANTI-PATTERN: Reviewer WAJIB menolak kode ini.
package inventory

import (
	"database/sql"
	"net/http"
	"sync"
)

type Service struct {
	db *sql.DB
	mu sync.Mutex
}

func (s *Service) DeductStock(w http.ResponseWriter, r *http.Request) {
	s.mu.Lock() // BAD: Global lock melumpuhkan throughput seluruh API
	defer s.mu.Unlock()

	sku := r.URL.Query().Get("sku")
	
	// BAD: Memulai goroutine unbounded tanpa kontrol konkurensi
	go func() {
		tx, _ := s.db.Begin() // BAD: Error diabaikan, potensi connection leak
		var stock int
		
		// BAD: Network call eksternal di dalam transaksi aktif
		http.Get("https://audit-logger.internal/notify?sku=" + sku)

		tx.QueryRow("SELECT stock FROM inventory WHERE sku = $1", sku).Scan(&stock)
		if stock > 0 {
			tx.Exec("UPDATE inventory SET stock = stock - 1 WHERE sku = $1", sku)
		}
		tx.Commit() // BAD: Jika terjadi panic/timeout, transaksi menggantung selamanya
	}()
	
	w.WriteHeader(http.StatusOK)
}
```

##### Production-Ready Implementation
```go
package inventory

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"net/http"
	"time"

	"golang.org/x/sync/semaphore"
)

var (
	ErrInsufficientStock = errors.New("insufficient stock")
	ErrSystemBusy        = errors.New("system busy, please try again later")
)

type InventoryRepository interface {
	DeductStockOptimistic(ctx context.Context, sku string, quantity int) error
}

type PostgresInventoryRepo struct {
	db *sql.DB
}

// DeductStockOptimistic menggunakan Atomic Conditional Update (Optimistic Concurrency Control)
// untuk menghindari exclusive table-level locks.
func (r *PostgresInventoryRepo) DeductStockOptimistic(ctx context.Context, sku string, quantity int) error {
	query := `
		UPDATE inventory 
		SET stock = stock - $1, version = version + 1 
		WHERE sku = $2 AND stock >= $1`

	res, err := r.db.ExecContext(ctx, query, quantity, sku)
	if err != nil {
		return fmt.Errorf("db exec failed: %w", err)
	}

	rows, err := res.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed fetching rows affected: %w", err)
	}

	if rows == 0 {
		return ErrInsufficientStock
	}

	return nil
}

type AllocationService struct {
	repo    InventoryRepository
	limiter *semaphore.Weighted
	timeout time.Duration
}

func NewAllocationService(repo InventoryRepository, maxConcurrent int64, timeout time.Duration) *AllocationService {
	return &AllocationService{
		repo:    repo,
		limiter: semaphore.NewWeighted(maxConcurrent),
		timeout: timeout,
	}
}

// DeductStock mengisolasi konkurensi menggunakan semaphore pembatas beban
// dan transaksi non-pemblokir berbasis optimistic update.
func (s *AllocationService) DeductStock(ctx context.Context, sku string, qty int) error {
	// 1. Concurrency Throttling (Backpressure Mechanism)
	if !s.limiter.TryAcquire(1) {
		return ErrSystemBusy
	}
	defer s.limiter.Release(1)

	// 2. Strict Context Timeout Propagation
	ctxWithTimeout, cancel := context.WithTimeout(ctx, s.timeout)
	defer cancel()

	// 3. Execution without holding application-level locks
	return s.repo.DeductStockOptimistic(ctxWithTimeout, sku, qty)
}
```

---

### 8. Real World Case Study: Flash-Sale Catastrophe

#### Konteks
Sebuah platform e-commerce meluncurkan kampanye diskon kilat. Layanan pemesanan (*order-service*) mendadak berhenti merespons (*hanging*) saat trafik mencapai 120.000 RPS. Penggunaan CPU database melonjak ke 100%, sementara server aplikasi mati karena *Out-Of-Memory (OOM)*.

#### Investigasi Post-Mortem & Penemuan pada PR
Kode baru yang di-*merge* ke produksi berisi logika berikut:
```go
// Kode yang diloloskan tanpa review menyeluruh:
func ProcessOrder(ctx context.Context, db *sql.DB, itemID string) {
    tx, _ := db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelSerializable})
    defer tx.Rollback()
    
    // Anomali 1: Pessimistic Row Lock dengan SERIALIZABLE isolation level
    row := tx.QueryRow("SELECT stock FROM items WHERE id = $1 FOR UPDATE", itemID)
    
    // Anomali 2: Operasi I/O lambat (RPC ke payment gateway) berada di dalam transaksi
    paymentSuccess := callPaymentGatewayWithSlowTimeout(itemID)
    
    if paymentSuccess {
        tx.Exec("UPDATE items SET stock = stock - 1 WHERE id = $1", itemID)
        tx.Commit()
    }
}
```

#### Analisis Kegagalan
1. **Lock Contention Ekstrem:** Ribuan koneksi konkuren meminta `SELECT FOR UPDATE` pada satu baris `itemID` yang sama (*Hot-Key*).
2. **Koneksi Database Habis:** Pemanggilan HTTP Payment Gateway memakan waktu 300ms–2s. Selama durasi itu, koneksi basis data tetap ditahan (*held open*). *Connection Pool* (kapasitas 200) habis dalam waktu kurang dari 50 milidetik.
3. **Cascading Failure:** Seluruh permintaan API lain yang membutuhkan koneksi basis data mengalami *timeout*. Permintaan yang tertahan menumpuk di memori aplikasi, memicu *GC overhead* dan akhirnya OOM crash.

#### Solusi Arsitektur Pasca Review
1. Pindahkan verifikasi pembayaran ke luar transaksi basis data.
2. Gunakan **Redis In-Memory Atomic Decr (DecrBy)** dengan skrip Lua untuk menahan stok di muka sebelum memicu persistensi.
3. Alihkan penulisan ke database menggunakan antrean Kafka berbasis partisi *consistent hashing* (partisi berbasis `itemID`), sehingga basis data hanya mengeksekusi mutasi baris secara serial tanpa perebutan *lock*.

---

### 9. Trade-Offs Matrix

| Strategi Sinkronisasi | Throughput | Latensi (p99) | Kompleksitas Kode | Biaya Resource | Cocok Digunakan Untuk |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Global/Coarse Mutex** | Sangat Rendah | Sangat Tinggi (Antrean) | Sangat Rendah | Minimal | Inisialisasi satu kali (*Singleton pattern*). |
| **Fine-Grained/Sharded Mutex** | Tinggi | Rendah-Sedang | Sedang | Rendah | *In-memory cache*, routing tabel terisolasi. |
| **Optimistic Concurrency (OCC)** | Sangat Tinggi | Rendah (Tinggi jika konflik ekstrim) | Sedang | Sedang (Biaya Retry) | Transaksi dengan rasio baca >> tulis. |
| **Pessimistic Locking (`FOR UPDATE`)** | Rendah | Tinggi | Rendah | Tinggi (Beban DB) | Sistem perbankan dengan integritas mutlak tanpa toleransi kompensasi. |
| **Lock-Free / Atomic Primitives** | Maksimal | Minimal | Sangat Tinggi | Minimal | *Metrics counter*, *ring buffers*, *event loops*. |

---

### 10. Common Mistakes & Troubleshooting Guide

Saat meninjau kode, waspadai cacat-cacat umum ini:

#### 1. Defer Lock Release Inside Loops
```go
// ANTI-PATTERN: Lock tidak dilepas hingga seluruh iterasi loop selesai!
for _, item := range items {
    mu.Lock()
    defer mu.Unlock() // BUG: defer hanya dieksekusi saat fungsi pembungkus selesai, bukan per iterasi!
    process(item)
}

// FIX: Gunakan blok fungsi anonim untuk membatasi scope defer
for _, item := range items {
    func() {
        mu.Lock()
        defer mu.Unlock()
        process(item)
    }()
}
```

#### 2. Channel Deadlock on Early Return
```go
// ANTI-PATTERN: Pengirim goroutine menggantung selamanya jika buffer penuh dan receiver return duluan
ch := make(chan error) // Unbuffered
go func() {
    ch <- doSomething() // Akan terblokir selamanya jika fungsi utama return lebih awal!
}()

if conditionFailed {
    return errors.New("failed") // ch tidak pernah dibaca, goroutine bocor!
}
```

#### 3. Unsafe Iteration over Maps Under Concurrency
Membaca dan menulis `map` standar bawaan bahasa Go secara simultan tanpa *sync primitive* memicu kepanikan runtime fatal: `fatal error: concurrent map read and map write`. Peninjau kode harus memastikan penggunaan `sync.RWMutex` atau `sync.Map` jika kuncinya stabil dan operasinya *read-heavy*.

---

### 11. Production Code Review Checklist

Gunakan daftar periksa ini saat memvalidasi PR terkait performa dan konkurensi:

- [ ] **Lock Scope:** Apakah *lock* hanya membungkus mutasi memori dan **tidak pernah** membungkus panggilan I/O, network call, atau RPC?
- [ ] **Deadlock Ordering:** Jika kode mengakuisisi lebih dari satu *lock*, apakah urutan akuisisinya konsisten secara deterministik di seluruh sistem?
- [ ] **Context Propagation:** Apakah semua operasi I/O dan konkurensi menerima dan menghormati sinyal pembatalan `context.Context`?
- [ ] **Resource Bounds:** Apakah semua penampung (*buffers*), *worker pools*, dan koneksi memiliki batas maksimum eksplisit (*bounded*)?
- [ ] **Leak Auditing:** Apakah setiap pembuatan goroutine dijamin memiliki jalur keluar (*exit condition*) yang deterministik?
- [ ] **False Sharing Mitigation:** Apakah struktur data konkuren intensif pada CPU memiliki *padding* antar-*field* yang dimutasi bersamaan?
- [ ] **Database Transaction Boundaries:** Apakah transaksi dibuka sesingkat mungkin, dan query diuji terhadap *index scanning* untuk menghindari penguncian tabel penuh?

---

### 12. Hands-on Practice

Buat repositori dan jalankan investigasi kebocoran konkurensi secara mandiri pada direktori `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── Makefile
├── go.mod
├── leaky_worker.go
├── leaky_worker_test.go
└── profile.sh
```

#### Langkah Praktikum

##### 1. Siapkan Proyek
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init concurrency-audit
```

##### 2. Tulis File `leaky_worker.go`
```go
package main

import (
	"context"
	"fmt"
	"sync"
	"time"
)

type Hub struct {
	dataChan chan int
}

func NewHub() *Hub {
	return &Hub{
		dataChan: make(chan int), // unbuffered channel
	}
}

// ProcessQueue mengandung goroutine leak saat timeout terjadi
func (h *Hub) ProcessQueue(ctx context.Context, total int) int {
	var wg sync.WaitGroup
	resultCounter := 0
	var mu sync.Mutex

	for i := 0; i < total; i++ {
		wg.Add(1)
		go func(val int) {
			defer wg.Done()
			select {
			case <-ctx.Done():
				// BUG: Data diabaikan tapi channel unbuffered tidak ditangani secara tuntas
				return
			case h.dataChan <- val:
				// sent
			}
		}(i)
	}

	// Consumer parsial dengan batas waktu
	ctxTimeout, cancel := context.WithTimeout(ctx, 10*time.Millisecond)
	defer cancel()

ConsumerLoop:
	for {
		select {
		case <-ctxTimeout.Done():
			break ConsumerLoop
		case v := <-h.dataChan:
			mu.Lock()
			resultCounter += v
			mu.Unlock()
		}
	}

	return resultCounter
}

func main() {
	fmt.Println("Hands-on Concurrency Review Running...")
}
```

##### 3. Tulis File `leaky_worker_test.go`
```go
package main

import (
	"context"
	"runtime"
	"testing"
	"time"
)

func TestGoroutineLeakVerification(t *testing.T) {
	initialGoroutines := runtime.NumGoroutine()
	hub := NewHub()

	// Eksekusi operasi berulang kali
	for i := 0; i < 5; i++ {
		hub.ProcessQueue(context.Background(), 100)
	}

	// Berikan waktu penyesuaian GC
	time.Sleep(100 * time.Millisecond)
	finalGoroutines := runtime.NumGoroutine()

	t.Logf("Goroutines awal: %d, Goroutines akhir: %d", initialGoroutines, finalGoroutines)
	if finalGoroutines-initialGoroutines > 50 {
		t.Fatalf("Gagal! Terjadi kebocoran Goroutine yang parah: %d goroutine tertahan.", finalGoroutines-initialGoroutines)
	}
}
```

##### 4. Jalankan Deteksi Race & Goroutine Leak
```bash
go test -v -race ./...
```
*Tugas Anda:* Modifikasi implementasi `leaky_worker.go` agar tes lulus tanpa menyisakan goroutine yang menggantung (gunakan bounded buffering atau channel draining pattern).

---

### 13. Exercises

#### Level Easy
Tinjau potongan kode berikut. Temukan potensi *data race* dan tuliskan perbaikannya:
```go
type SessionManager struct {
    sessions map[string]string
}
func (sm *SessionManager) Set(k, v string) { sm.sessions[k] = v }
func (sm *SessionManager) Get(k string) string { return sm.sessions[k] }
```

#### Level Medium
Tinjau sebuah PR yang memproses *event streams* di mana pengembang menggunakan *unbounded goroutine* per event:
```go
func HandleEvents(events []Event) {
    for _, event := range events {
        go process(event) // Apa bahayanya jika slices events berisi 1.000.000 elemen?
    }
}
```
Rancang ulang kode di atas menggunakan pola **Worker Pool Terbatas (Bounded Worker Pool)** dengan ukuran pool dinamis berdasarkan `runtime.NumCPU()`.

#### Level Hard
Buat implementasi sebuah **Sharded Concurrent Cache** yang membagi satu `sync.RWMutex` besar ke dalam 32 *shards* berdasarkan algoritma FNV-1a Hash pada kunci *string*. Buktikan peningkatan skalabilitasnya melalui Go Benchmark dengan pengujian *concurrent write-heavy* (90% Write, 10% Read).

---

### 14. Architecture Challenge

**Scenario:**
Sebuah bank digital merancang sistem transfer saldo antar-rekening (*ledger-transfer*). Setiap transfer memotong Saldo Pengirim dan menambah Saldo Penerima. 

Arsitek sebelumnya meninggalkan draf kode PR berikut:
```go
func Transfer(db *sql.DB, fromID, toID string, amount int64) error {
    tx, _ := db.Begin()
    defer tx.Rollback()

    // Query 1: Kunci pengirim
    tx.Exec("SELECT balance FROM accounts WHERE id = $1 FOR UPDATE", fromID)
    tx.Exec("UPDATE accounts SET balance = balance - $1 WHERE id = $2", amount, fromID)

    // Query 2: Kunci penerima
    tx.Exec("SELECT balance FROM accounts WHERE id = $1 FOR UPDATE", toID)
    tx.Exec("UPDATE accounts SET balance = balance + $1 WHERE id = $2", amount, toID)

    return tx.Commit()
}
```

**Tantangan Anda:**
1. **Analisis Masalah:** Kode di atas dapat memicu **Deadlock Sistemik Parah** di bawah beban konkuren tinggi jika dua akun saling mentransfer uang secara simultan (Akun A transfer ke B, bersamaan dengan Akun B transfer ke A). Jelaskan mengapa hal ini terjadi.
2. **Desain Perbaikan:** Tuliskan proposal arsitektur PR review untuk menjamin transaksi ini bebas dari deadlock secara deterministik (petunjuk: *resource ordering algorithm*) tanpa mengorbankan performa basis data.
3. Sertakan pertimbangan bagaimana menangani *Hot-Account* (misalnya akun *payroll* korporasi yang mentransfer dana ke 50.000 karyawan secara paralel).

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa perbedaan mendasar antara *Race Condition* dan *Data Race*?
2. Mengapa memasukkan panggilan HTTP client di dalam blok `mutex.Lock()` sangat dilarang dalam sistem berskala besar?
3. Apa indikator metrik database yang menunjukkan terjadinya fenomena *lock contention* tinggi?
4. Mengapa penggunaan channel unbuffered tanpa goroutine penerima yang deterministik dapat memicu *memory leak*?
5. Apa fungsi dari flag `-race` pada kompilator Go, dan berapa perkiraan biaya performa saat flag ini diaktifkan?

#### Pertanyaan Intermediate
6. Bagaimana fenomena *False Sharing* terjadi pada CPU multi-core, dan bagaimana cara memitigasinya pada struktur data bahasa Go?
7. Jelaskan anomali konkurensi yang dapat dicegah oleh isolasi level *Repeatable Read* tetapi tidak dapat dicegah oleh *Read Committed*!
8. Apa kelemahan utama dari pola *Optimistic Concurrency Control (OCC)* saat diaplikasikan pada skenario *write-heavy* ekstrem?
9. Bagaimana alur kerja strategi *Lock Stripping* (misalnya *sharded map*) dalam mereduksi waktu tunggu CPU?
10. Mengapa metode `defer mu.Unlock()` berpotensi merusak latensi pada fungsi yang memiliki cabang logika pemrosesan yang panjang?

#### Skenario Kasus Produksi
11. **Kasus 1:** Dashboard monitoring Grafana menunjukkan metrik *Goroutine Count* naik linear secara konstan tanpa pernah turun selama 48 jam pasca deployment rilis baru. Apa langkah investigasi pertama yang harus Anda minta pada pengembang sebelum PR perbaikan diajukan?
12. **Kasus 2:** Sebuah PR mengubah isolasi transaksi basis data dari *Read Committed* menjadi *Serializable* untuk mencegah inkonsistensi data saldo. Namun, saat uji beban, throughput sistem drop hingga 80% dan log dipenuhi oleh pesan *Serialization Failure / Deadlock detected*. Bagaimana Anda mereview dan mengarahkan ulang desain PR tersebut?
13. **Kasus 3:** Seorang pengembang membuat microservice baru yang menggunakan *connection pool* dengan ukuran maksimum 50. Di dalam kodenya, satu request memanggil database sebanyak 3 kali secara paralel menggunakan 3 goroutine anak. Di bawah beban 100 RPS, seluruh aplikasi langsung hang (*threadpool exhaustion*). Analisis akar masalahnya!

---

### 16. Summary

- **Reviewing for concurrency is an architectural gatekeeping role:** Masalah konkurensi tidak dapat diselesaikan hanya dengan unit testing standar karena sifatnya yang non-deterministik.
- **Locking is a Double-Edged Sword:** Penguncian yang terlalu longgar menyebabkan korupsi data; penguncian yang terlalu ketat menghancurkan throughput sistem dan memicu deadlock.
- **Isolate I/O from Locks:** Aturan baku enterprise: Jangan pernah menahan *application lock* atau *database transaction lock* saat menjalankan operasi jaringan atau komputasi lambat.
- **Embrace Predictable Bounds:** Sistem yang skalabel adalah sistem yang menerapkan batasan (*bounded*). Setiap alokasi memori, antrean pesan, worker pool, dan durasi penahanan sumber daya wajib memiliki batas maksimum dan penanganan *timeout* yang tegas.