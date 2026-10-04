# Bab 01: Arsitektur Runtime, Memory Model, dan Kompilasi
## Module 01: Anatomi Go Runtime: Kompilasi, Memory Layout, dan Penjadwalan GMP

---

### 1. Metadata Module
* **Module ID**: `GOLANG-ARCH-0101`
* **Level**: Advanced Fundamentals
* **Prerequisites**: Pengetahuan dasar arsitektur komputer (registers, L1/L2/L3 cache, virtual memory), konsep OS thread, dan sintaks dasar Go.
* **Target Audience**: Systems Engineers, Backend Infrastructure Engineers, High-Throughput Platform Developers.
* **Tooling Version**: Go 1.22+ (Linux/macOS AMD64/ARM64).

---

### 2. Learning Objectives
Setelah menyelesaikan modul ini, engineer mampu:
* **Menganalisis** transformasi source code Go dari AST (*Abstract Syntax Tree*), SSA (*Static Single Assignment*), hingga machine code melalui pipeline compiler.
* **Mengaudit** alokasi memori runtime menggunakan *Escape Analysis* compiler flags untuk membedakan alokasi pada contiguous stack vs concurrent mark-sweep managed heap.
* **Membongkar** mekanisme kerja penjadwal M:N Go (GMP Model: Goroutine, Machine, Processor) termasuk work-stealing, network poller, dan kooperasi preemptif berbasis signal.
* **Mengidentifikasi** bottleneck performa sistem akibat kontensi thread OS, context switching, dan latensi *Stop-The-World* (STW) Garbage Collection.
* **Mengonfigurasi** runtime Go di level kernel/container menggunakan environment variables tingkat lanjut (`GODEBUG`, `GOMEMLIMIT`, `GOGC`).

---

### 3. Conceptual Foundation
Runtime Go bukan sekadar *virtual machine* atau interpreter; runtime Go adalah pustaka sistem yang di-link secara statis ke dalam setiap binary binary Go. Arsitektur ini mengabstraksi perangkat keras dan kernel sistem operasi menggunakan tiga pilar utama:

1. **User-Space Cooperative & Preemptive Scheduling (M:N Model)**:
   Thread kernel (1:1 model) mahal dalam hal alokasi memori (*footprint* stack default 2MB–8MB) dan biaya context-switch (~1–2 mikrosekon) karena harus melewati trap switch privilege level OS (Ring 3 ke Ring 0). Go mengimplementasikan penjadwalan M:N di mana $M$ *green threads* (Goroutine) dipetakan ke $N$ thread sistem operasi (*Kernel Threads*) menggunakan abstraksi context $P$ (*Logical Processor*). Goroutine berbobot sangat ringan: dialokasikan dengan stack 2KB yang dapat tumbuh secara dinamis (*contiguous stack allocation*), dengan biaya context-switch sub-mikrosekon (~10–100 nanosekon).

2. **TCMalloc-Derived Memory Allocator**:
   Untuk menghindari *lock contention* global di multi-core processor, runtime Go mengadopsi model alokasi memori berbasis TCMalloc (*Thread-Caching Malloc*). Alokasi memori dibagi menjadi tingkatan:
   * Thread-local cache (`mcache` tanpa lock).
   * Central list (`mcentral` dengan lock per-size-class).
   * Page heap (`mheap` untuk alokasi besar dan manajemen *virtual memory arena* dari OS).

3. **Compiler Directives & Escape Analysis**:
   Compiler Go menentukan lokasi alokasi variabel saat *compile-time*, bukan *runtime*. Jika referensi variabel tidak keluar (*escape*) dari scope stack frame fungsi yang memanggilnya, variabel dijamin tetap berada di stack (alokasi instan melalui manipulasi *Stack Pointer register* `SP`, zero GC cost). Jika compiler mendeteksi variabel dapat diakses di luar stack frame (misal: return pointer, capture by closure, assign to interface), compiler akan memindahkan alokasinya ke Heap (*escape to heap*).

---

### 4. Technical Architecture Deep-Dive
Arsitektur runtime Go dikoordinasikan oleh entitas fundamental GMP:

* **G (Goroutine)**: Representasi thread level pengguna. Berisi context stack (`stack.lo`, `stack.hi`), program counter (`PC`), stack pointer (`SP`), dan status internal (`_Gidle`, `_Grunnable`, `_Grunning`, `_Gsyscall`, `_Gwaiting`).
* **M (Machine)**: Thread OS yang dikelola oleh kernel scheduler. `M` mengeksekusi instruksi mesin aktual. `M` membutuhkan struct `P` untuk dapat mengeksekusi instruksi Go.
* **P (Processor)**: Logical context atau token eksekusi. Jumlah `P` default sama dengan `GOMAXPROCS` (jumlah core CPU logical). `P` mengelola *Local Run Queue* (LRQ) berkapasitas 256 runnable Goroutine.

```
       +-------------------------------------------------------+
       |                  Global Run Queue (GRQ)               |
       |                   [ G7, G8, G9, ... ]                 |
       +-------------------------------------------------------+
                ^                       ^
     Lock-based | Steal             Lock | Push
     Every 61 ticks                     |
                v                       v
       +-----------------+     +-----------------+
       |  Processor P0   |     |  Processor P1   |
       | [LRQ: G1, G2]   |     | [LRQ: G4, G5]   |
       +-----------------+     +-----------------+
       | mcache          |     | mcache          |
       +-----------------+     +-----------------+
                |                       |
                | Bound                 | Bound
                v                       v
       +-----------------+     +-----------------+
       |   Thread M0     |     |   Thread M1     |
       | (Executing G0)  |     | (Executing G3)  |
       +-----------------+     +-----------------+
                |                       |
         Kernel | Context Switch Kernel | Context Switch
                v                       v
       ===========================================
                 CPU Core 0          CPU Core 1
       ===========================================
                ^                       ^
                |                       |
       +-----------------+     +-----------------+
       | Syscall Poller  |     | Network Poller  |
       | (sysmon thread) |     | (epoll/kqueue)  |
       +-----------------+     +-----------------+
```

#### Alur Penjadwalan Kerja (Scheduling Loop):
1. Thread `M` mencari Goroutine executable (`findrunnable`):
   * Memeriksa GRQ setiap 61 scheduler tick (mencegah starvation pada GRQ).
   * Memeriksa LRQ milik `P` lokal tanpa atomic/lock.
   * Melakukan *work-stealing*: Mencuri separuh isi LRQ milik `P` lain jika LRQ lokal kosong.
   * Memeriksa Network Poller (`epoll` di Linux, `kqueue` di macOS) untuk Goroutine I/O yang telah *ready*.
   * Mengambil dari GRQ jika semua step di atas nihil.
2. Jika sebuah Goroutine melakukan blocking system call:
   * Thread `M` melepaskan `P` (*handoff*).
   * Thread `M` terblokir di level kernel OS bersama `G`.
   * Thread `M` baru dibuat atau dibangunkan dari *idle pool* untuk mengambil alih `P` dan melanjutkan eksekusi runnable Goroutine lainnya.
3. Thread background khusus `sysmon` (tidak terikat pada `P`) melakukan audit periodik:
   * Mengirim signal preemptif OS `SIGURG` ke `M` jika suatu `G` mengeksekusi komputasi intensif tanpa *function call* > 10ms.
   * Melakukan retensi Goroutine yang tersangkut di network poller dan syscall.

---

### 5. Compilation, Memory, & Execution Model

#### Compilation Pipeline
Compiler Go (`go tool compile`) memproses kode sumber melalui tahap-tahap deterministik:
1. **Parsing & Type Checking**: Kode Go dikonversi menjadi AST. Tipe data divalidasi secara ketat.
2. **Escape Analysis & Inlining**: Analisis pergerakan data dilakukan. Fungsi yang cukup kecil di-inline untuk memangkas overhead pemanggilan fungsi.
3. **SSA Generation (Static Single Assignment)**: AST diubah menjadi representasi SSA di mana setiap variabel di-assign tepat satu kali. Optimasi seperti *Dead Code Elimination* (DCE), *Bounds Check Elimination* (BCE), dan *Constant Folding* dieksekusi di fase ini.
4. **Machine Code Generation**: SSA diterjemahkan ke assembly spesifik arsitektur target (Plan 9 assembly dialect), lalu di-encode menjadi instruksi biner ELF/Mach-O/PE.

#### Memory Layout
Setiap program Go memetakan memori ke dalam segmen virtual:
* **Stack**:
  * Dimulai dari alokasi 2048 bytes (2KB).
  * Bersifat *contiguous*: Jika stack penuh saat fungsi baru dipanggil, runtime mengalokasikan stack baru sebesar 2x lipat dari stack lama, menyalin memori stack lama ke stack baru, menyesuaikan seluruh internal pointer, dan membebaskan stack lama.
* **Heap (TCMalloc Derivative)**:
  * Dibagi menjadi blok-blok 8KB yang disebut `page`.
  * Rangkaian page dikelompokkan menjadi `mspan`.
  * `mspan` dialokasikan untuk 67 kelas ukuran diskrit (*Size Classes*, dari 8 bytes hingga 32KB). Objek $> 32KB$ dialokasikan langsung dari `mheap`.
  * Pointer scanning menggunakan bit-bitmap (*scan bits*) untuk GC Mark Phase.

---

### 6. Production Code Blueprint 01: Minimal Isolated Core
Blueprint ini mendemonstrasikan inspeksi langsung terhadap alokasi memori internal, analisis *escape analysis*, dan deteksi stack growth secara eksplisit.

```go
// File: cmd/runtime_core/main.go
package main

import (
	"fmt"
	"runtime"
	"sync/atomic"
	"unsafe"
)

// Structural alignment demonstration (Memory Padding)
type PackedStruct struct {
	A bool    // 1 byte
	_ [7]byte // Explicit padding
	B int64   // 8 bytes
	C bool    // 1 byte
	_ [7]byte // Explicit padding
}

// Global sink to prevent compiler Dead Code Elimination (DCE)
var GlobalSink any

//go:noinline
func inspectVariableLocation(val int) *int {
	// Demonstrasi escape analysis:
	// val dialokasikan di stack frame inspectVariableLocation,
	// tetapi alamat memorinya di-escape ke luar melalui return pointer.
	escapedVar := val * 2
	return &escapedVar
}

//go:noinline
func triggerStackGrowth(depth int, val [1024]byte) {
	if depth <= 0 {
		return
	}
	// Setiap pemanggilan fungsi ini mengonsumsi ~1KB di stack.
	// Runtime terpaksa memperbesar stack frame saat batas terlewati.
	triggerStackGrowth(depth-1, val)
}

func main() {
	var memStats runtime.MemStats
	runtime.ReadMemStats(&memStats)
	initialAlloc := memStats.Alloc

	// 1. Uji Escape Analysis
	ptr := inspectVariableLocation(42)
	GlobalSink = ptr

	// 2. Struct Memory Footprint Inspection
	ps := PackedStruct{A: true, B: 1337, C: false}
	size := unsafe.Sizeof(ps)
	align := unsafe.Alignof(ps)

	// 3. Inspeksi Pertumbuhan Contiguous Stack
	var dummyPayload [1024]byte
	triggerStackGrowth(10, dummyPayload)

	runtime.ReadMemStats(&memStats)
	postAlloc := memStats.Alloc

	fmt.Printf("[Core Architecture Diagnostic]\n")
	fmt.Printf("Pointer Escape Target Address  : %p\n", ptr)
	fmt.Printf("PackedStruct Total Size        : %d Bytes (Align: %d Bytes)\n", size, align)
	fmt.Printf("Heap Alloc Delta               : %d Bytes\n", postAlloc-initialAlloc)
	fmt.Printf("Active OS Threads (M)          : %d\n", runtime.NumGoroutine())
	fmt.Printf("Configured Processors (P)      : %d\n", runtime.GOMAXPROCS(0))
}
```

Verifikasi escape analysis melalui compiler:
```bash
go build -gcflags="-m -m" cmd/runtime_core/main.go
```
*Output compiler akan menunjukkan: `escapedVar escapes to heap`.*

---

### 7. Production Code Blueprint 02: Resilient Production-Ready Real-World Implementation
Komponen infrastruktur: **High-Throughput In-Memory Task Batcher** dengan optimasi alokasi zero-GC, memanfaatkan `sync.Pool`, batch execution yang meminimalisir lock contention pada GMP runtime, dan graceful draining context-aware.

```go
// File: pkg/batcher/batcher.go
package batcher

import (
	"context"
	"errors"
	"runtime"
	"sync"
	"sync/atomic"
	"time"
)

var (
	ErrBatcherClosed = errors.New("batcher: system is closed to new payloads")
	ErrQueueFull     = errors.New("batcher: internal buffer queue capacity saturated")
)

type WorkItem struct {
	ID        uint64
	Payload   []byte
	CreatedAt time.Time
}

// TaskProcessor mendefinisikan signature fungsi eksekusi batch eksternal.
type TaskProcessor func(ctx context.Context, batch []*WorkItem) error

// Engine mengelola ingestion payload dan eksekusi batch terkoordinasi.
type Engine struct {
	processor   TaskProcessor
	maxBatch    int
	flushPeriod time.Duration

	incomingCh chan *WorkItem
	pool       sync.Pool

	wg        sync.WaitGroup
	ctx       context.Context
	cancel    context.CancelFunc
	closed    atomic.Bool
	processed atomic.Uint64
}

func NewEngine(p TaskProcessor, maxBatch int, flushPeriod time.Duration, bufferCap int) *Engine {
	ctx, cancel := context.WithCancel(context.Background())
	e := &Engine{
		processor:   p,
		maxBatch:    maxBatch,
		flushPeriod: flushPeriod,
		incomingCh:  make(chan *WorkItem, bufferCap),
		ctx:         ctx,
		cancel:      cancel,
		pool: sync.Pool{
			New: func() any {
				// Mencegah alokasi heap repetitif pada alur ingest cepat
				return &WorkItem{
					Payload: make([]byte, 0, 512),
				}
			},
		},
	}

	e.wg.Add(1)
	go e.runWorker()

	return e
}

// Ingest menerima data dan menugaskan alokasi dari pool.
func (e *Engine) Ingest(id uint64, rawData []byte) error {
	if e.closed.Load() {
		return ErrBatcherClosed
	}

	item := e.pool.Get().(*WorkItem)
	item.ID = id
	item.CreatedAt = time.Now()
	item.Payload = append(item.Payload[:0], rawData...) // Zero-realloc if within cap

	select {
	case e.incomingCh <- item:
		return nil
	default:
		// Kembalikan ke pool jika antrean jenuh untuk menghindari kebocoran alokasi
		e.pool.Put(item)
		return ErrQueueFull
	}
}

func (e *Engine) runWorker() {
	defer e.wg.Done()

	// Pre-allocate slice pointer untuk mencegah re-alokasi heap selama siklus flush
	batch := make([]*WorkItem, 0, e.maxBatch)
	ticker := time.NewTicker(e.flushPeriod)
	defer ticker.Stop()

	flush := func() {
		if len(batch) == 0 {
			return
		}

		// Eksekusi pemrosesan batch
		if err := e.processor(e.ctx, batch); err != nil {
			// Pada produksi, integrasikan structured logger di sini
		}

		e.processed.Add(uint64(len(batch)))

		// Daur ulang instance struct ke sync.Pool
		for _, item := range batch {
			e.pool.Put(item)
		}

		// Reset length tanpa membebaskan kapasitas underlying array (Zero Heap Realloc)
		batch = batch[:0]
	}

	for {
		select {
		case <-e.ctx.Done():
			// Flush sisa antrean saat shutdown dipicu
			for {
				select {
				case item := <-e.incomingCh:
					batch = append(batch, item)
					if len(batch) >= e.maxBatch {
						flush()
					}
				default:
					flush()
					return
				}
			}

		case item := <-e.incomingCh:
			batch = append(batch, item)
			if len(batch) >= e.maxBatch {
				flush()
			}

		case <-ticker.C:
			flush()
		}
	}
}

// Shutdown mengeksekusi graceful drain terhadap sistem dan scheduler runtime.
func (e *Engine) Shutdown(timeout time.Duration) error {
	if !e.closed.CompareAndSwap(false, true) {
		return nil
	}

	shutdownDone := make(chan struct{})
	go func() {
		e.cancel()
		e.wg.Wait()
		close(e.incomingCh)
		close(shutdownDone)
	}()

	select {
	case <-shutdownDone:
		return nil
	case <-time.After(timeout):
		return errors.New("batcher: graceful shutdown timed out; pending items dropped")
	}
}

func (e *Engine) TotalProcessed() uint64 {
	return e.processed.Load()
}
```

---

### 8. Step-by-Step Implementation Guide

Berikut adalah implementasi bertahap untuk membangun modul di atas:

1. **Step 1: Arsitektur Memori dan Struct Sizing**
   Tentukan tipe entitas data. Gunakan `unsafe.Sizeof` dan `unsafe.Alignof` untuk memastikan struktur struct bebas dari padding tersembunyi yang boros memori (urutkan field struct dari tipe data terbesar ke terkecil: misal `int64`, disusul pointer, lalu `int32`, `int16`, terakhir `bool` / `byte`).

2. **Step 2: Menghilangkan Alokasi Menggunakan `sync.Pool`**
   Inisialisasi objek `sync.Pool`. Terapkan pola `slice = slice[:0]` saat mengembalikan memori slice ke dalam pool guna mempertahankan buffer kapasitas memori yang mendasarinya (*underlying array*), sehingga garbage collector tidak perlu melakukan alokasi dan dealokasi berulang kali.

3. **Step 3: Mencegah Scheduler Preemption Overhead**
   Hindari pengiriman payload tunggal melalui kanal (*unbuffered channel*) dalam skenario volume ultra-tinggi. Unbuffered channels memaksa context-switch GMP secara intensif. Selalu sediakan buffer kapasitas yang realistis dan gunakan batching internal.

4. **Step 4: Graceful Shutdown Coordination**
   Gunakan kombinasi state atomic `closed.CompareAndSwap()` dan koordinasi `sync.WaitGroup` serta `context.Context` untuk memastikan runtime scheduler memiliki waktu menguras (*draining*) LRQ/GRQ sebelum binary proses dihentikan oleh sinyal kernel (`SIGTERM`).

---

### 9. Anti-Patterns & Common Pitfalls

| Anti-Pattern | Mengapa Salah (Underlying Mechanism) | Solusi Benar (Correct Pattern) |
|---|---|---|
| **Unbounded Goroutine Spawning** (`go func() { ... }()`) | Menyebabkan memori membengkak eksponensial. Walau 1 Goroutine = 2KB, 1 juta Goroutine = 2GB RAM. P scheduler overhead melonjak drastis, GRQ penuh, STW GC tertekan. | Terapkan *Bounded Worker Pool* atau semafor menggunakan buffered channel berkapasitas fixed. |
| **Passing Value to `any`/`interface{}` in Critical Loop** | Mengonversi concrete type ke interface memaksa alokasi memori ke heap (`convT2E` / `convT64`), karena interface membutuhkan representasi metadata tipe runtime (`itab`). | Teruskan data concrete type secara langsung, atau gunakan Go Generics untuk mempertahankan type constraint saat kompilasi. |
| **Goroutine Leak via Nil Channel/Blocking Operation** | Goroutine yang terblokir selamanya di channel tidak pernah dipungut GC. Struct `runtime.g` beserta seluruh stack frame-nya bocor permanen di memori. | Selalu sertakan timeout berbasis `context.WithTimeout` atau channel pembatalan pada operasi I/O dan channel recv/send. |
| **Variable Capture in Loop Closures** | Menangkap iterator variabel pointer di anonymous goroutine secara paralel menghasilkan race conditions dan memindahkan variabel tersebut dari stack ke heap. | Teruskan variabel loop secara eksplisit sebagai parameter nilai ke anonymous Goroutine. |

---

### 10. Alternative Approaches & Comparative Evaluation

Pendekatan model konkurensi dan manajemen memori Go dibanding platform lain:

| Karakteristik | Go (GMP Runtime) | Rust (Async/Tokio) | Java (Virtual Threads - Loom) | C++ (Native POSIX Pthreads) |
|---|---|---|---|---|
| **Model Threading** | M:N User-space Scheduler | M:N Cooperative via Epoll Poller | M:N User-space Scheduler | 1:1 Kernel Threads |
| **Memory Footprint Awal** | ~2 KB per Goroutine | ~0.5 KB per Task (Zero-cost abstraction) | ~1 KB per Virtual Thread | 2 MB - 8 MB per Thread |
| **Stack Allocation** | Contiguous Stack (Dynamic resizing 2KB - 1GB) | Fixed Heap-allocated Frame (Generator state machine) | Continuation-based Dynamic Chunked Stack | Fixed Size Stack (Ditentukan saat compile/OS spawn) |
| **Garbage Collection Model** | Concurrent Mark-Sweep (STW < 1ms) | Tidak ada (Deterministic RAII / Borrow Checker) | Generational ZGC/G1 (Tuned for throughput & latency) | Tidak ada (Manual allocator / smart pointer) |
| **Preemption Model** | Asynchronous Preemption (Signal `SIGURG`) + Cooperative check | Strictly Cooperative (Hanya saat titik `.await`) | Cooperative (Yielding points pada I/O blocking) | Preemptive (Diatur mutlak oleh Kernel OS) |

---

### 11. Verification, Diagnostics, & Testing
Diagnostik performa runtime membutuhkan inspeksi level instruksi compiler dan trace GC.

#### Profiling & Compilation Verification
Jalankan testing dengan mengaktifkan pemeriksaan alokasi memori dan deteksi race condition:
```bash
# Uji unit test dan ukur alokasi memori presisi
go test -v -race -bench=. -benchmem ./...

# Analisis assembly yang dihasilkan oleh compiler untuk fungsi spesifik
go tool compile -S pkg/batcher/batcher.go | grep -E "CALL.*runtime.newobject"

# Ekspor execution trace untuk dibaca via browser
go test -trace trace.out ./pkg/batcher
go tool trace trace.out
```

#### Unit & Benchmark Test
```go
// File: pkg/batcher/batcher_test.go
package batcher

import (
	"context"
	"sync/atomic"
	"testing"
	"time"
)

func BenchmarkBatcherIngest(b *testing.B) {
	processor := func(ctx context.Context, batch []*WorkItem) error {
		// Mock latency eksekusi
		return nil
	}

	engine := NewEngine(processor, 100, 10*time.Millisecond, 100000)
	defer engine.Shutdown(1 * time.Second)

	payload := []byte("standardized-benchmark-payload-data")

	b.ResetTimer()
	b.ReportAllocs() // Audit alokasi memori per operasi

	b.RunParallel(func(pb *testing.PB) {
		var id uint64
		for pb.Next() {
			currentID := atomic.AddUint64(&id, 1)
			if err := engine.Ingest(currentID, payload); err != nil {
				b.Errorf("Ingestion failed: %v", err)
			}
		}
	})
}
```

---

### 12. Security Considerations & Hardening

1. **Unbounded Memory Exhaustion via Goroutines (DoS Vector)**:
   * **Risiko**: Penyerang mengirim jutaan request HTTP secara bersamaan. Jika program menjalankan 1 Goroutine per request tanpa rate limiting, alokasi stack 2KB per Goroutine dengan cepat menguras RAM hingga host mengalami crash OOM (*Out Of Memory*).
   * **Mitigasi**: Terapkan rate-limiting di reverse proxy atau level runtime melalui semafor `golang.org/x/sync/semaphore` untuk membatasi eksekusi paralel.
2. **Data Race Memory Corruption**:
   * **Risiko**: Go tidak *memory-safe* secara inheren terhadap *concurrent memory writes*. Dua Goroutine yang memodifikasi tipe non-primitif (misal `map` atau `slice header`) secara simultan dapat merusak pointer internal, memicu kernel level Segmentation Fault (`SIGSEGV`), atau menyebabkan pembacaan memori acak (*arbitrary memory read*).
   * **Mitigasi**: Selalu aktifkan `-race` pada CI/CD pipeline pipeline. Gunakan instrumen atomik atau `sync.RWMutex`.
3. **CGO Memory Boundary Vulnerabilities**:
   * **Risiko**: Alokasi memori C via CGO berada di luar kendali GC dan compiler Go. Memory leak atau buffer overflow di layer C dapat membobol isolasi memori proses Go runtime.
   * **Mitigasi**: Minimalkan CGO. Jika wajib, gunakan boundary validation yang ketat dan audit alokasi secara manual dengan `free()`.

---

### 13. Performance Tuning & Latency Profile

#### 1. Menjinakkan Garbage Collector: `GOMEMLIMIT` dan `GOGC`
Pada Go 1.19+, lingkungan produksi dengan memory limit terdefinisi (misal Kubernetes Pod) wajib mengonfigurasi `GOMEMLIMIT`.
* Atur `GOMEMLIMIT` ke 85–90% dari batas hard limit cgroup container (misal Pod 1GiB $\to$ `GOMEMLIMIT=900MiB`).
* GC akan menyesuaikan siklus mark-sweep secara dinamis: jika pemakaian memori jauh dari batas limit, `GOGC` akan dibiarkan melebar untuk menghemat CPU. Begitu memori mendekati 900MiB, frekuensi GC ditingkatkan agar proses tidak dimatikan oleh OOM Killer kernel Linux (*Signal 9 SIGKILL*).

#### 2. CPU Core Allocation: `GOMAXPROCS`
Di lingkungan container virtualized (cgroups quota), runtime Go secara default terkadang membaca jumlah core CPU fisik host induk, bukan kuota container.
* Masalah: Host memiliki 64 Core, pod dibatasi 2 CPU. Go akan mengalokasikan 64 `P`. Hal ini memicu CPU throttling brutal dan overhead context switching antar-M.
* Solusi: Impor pustaka auto-tuning runtime di `main.go`:
  ```go
  import _ "go.uber.org/automaxprocs"
  ```

#### 3. Eliminasi False Sharing
Jika dua Goroutine pada Core terpisah sering memperbarui variabel independen yang berada pada baris cache CPU (*CPU Cache Line*, standar 64 bytes) yang sama, CPU harus memvalidasi ulang cache L1/L2 secara kontinu (*cache bouncing*).
* Solusi: Lakukan padding pada struct atomic:
  ```go
  type CacheLinePaddedCounter struct {
      counter uint64
      _       [56]byte // 64 - 8 = 56 bytes padding
  }
  ```

---

### 14. Failure Modes, Edge Cases, & Recovery Strategies

#### Mode Kegagalan 1: Preemption Starvation pada Tight Loop (Legacy / CGO Issue)
* **Karakteristik**: Goroutine melakukan perulangan matematika ketat tanpa alokasi memori, manipulasi slice/pointer, atau pemanggilan fungsi.
* **Gejala**: Goroutine lain kelaparan (*starving*), aplikasi freeze parsial, GC STW membeku karena menunggu seluruh Goroutine tiba di *Safe-Point*.
* **Penanganan**: Walau Go 1.14+ telah menerapkan signal-based preemption via `SIGURG`, loop interop CGO masih kebal terhadap sinyal ini. Selipkan pemanggilan kooperatif `runtime.Gosched()` di dalam perulangan intensif native CGO.

#### Mode Kegagalan 2: Deep Recursion Stack Overflow
* **Karakteristik**: Fungsi rekursif tanpa basis terminasi yang benar.
* **Gejala**: Stack tumbuh melewati batas maksimum sistem (default: 1 GB untuk arsitektur 64-bit, 250 MB untuk 32-bit).
* **Pemulihan**: Runtime akan langsung memicu *fatal error* yang **tidak dapat di-recover** via fungsi `recover()`:
  ```
  runtime: goroutine stack exceeds 1000000000-byte limit
  fatal error: stack overflow
  ```
* **Pencegahan**: Selalu gunakan pendekatan iteratif dengan data structure eksplisit di heap jika depth rekursi dinamis tidak terbatas.

---

### 15. Operational Runbook & Observability

#### Critical Runtime Metrics
Monitor metrik-metrik berikut melalui package `runtime/metrics` (Go 1.16+) atau Prometheus exporter:

1. `/sched/goroutines:goroutines`: Lonjakan tajam menandakan adanya *goroutine leak*.
2. `/sched/latencies:seconds`: Waktu tunggu Goroutine di Run Queue sebelum mendapatkan slot eksekusi di `M`. Latensi tinggi menandakan saturasi CPU.
3. `/gc/pauses:seconds`: Durasi STW GC. Ambang kritis: $p99 > 5\text{ms}$.
4. `/memory/classes/heap/objects:bytes`: Volume heap aktif. Indikator akurat kebocoran memori.

#### Diagnostik Produksi Menggunakan Trace Logging
Aktifkan scheduler tracing real-time tanpa modifikasi source code dengan runtime environment flags:
```bash
# Menampilkan status GMP setiap 1000ms ke stderr
GODEBUG=schedtrace=1000,scheddetail=1 ./my-go-binary
```
*Interpretasi Log:*
`SCHED 1004ms: gomaxprocs=4 idleprocs=2 threads=6 spinningthreads=1 needspin=0 idlethreads=0 runqueue=3 [0 0 1 0]`
* `gomaxprocs=4`: Terpasang 4 logical processor.
* `runqueue=3`: Ada 3 Goroutine antre di GRQ.
* `[0 0 1 0]`: Kapasitas antrean lokal (LRQ) pada P0, P1, P2, P3.

---

### 16. Applied Mental Model
Pahami GMP seperti **Sistem Layanan di Bandara**:
* **Goroutine ($G$)**: **Penumpang** yang membawa barang bawaan. Mereka ingin terbang (dieksekusi), membutuhkan ruang tunggu, berukuran ringan, dan bisa datang dalam jumlah puluhan ribu.
* **Processor ($P$)**: **Meja Loket Check-in**. Jumlahnya terbatas sesuai alokasi operasional bandara (`GOMAXPROCS`). Setiap loket memiliki antrean lokal masing-masing (LRQ) agar penumpang tidak menumpuk di lobi utama.
* **Machine ($M$)**: **Petugas Bandara**. Tanpa petugas, loket check-in tidak dapat memproses penumpang. Petugas melayani penumpang di loket. Jika loket kehabisan antrean penumpang, petugas melirik loket sebelah dan mengambil separuh antrean mereka (*work-stealing*). Jika seorang penumpang tertahan verifikasi visa rumit yang lama (blocking Syscall), petugas mengalihkan loket ke staf pengganti agar penumpang di belakangnya tidak terbengkalai (*handoff*).

---

### 17. Complete Working Code Artifact
File berikut menyatukan seluruh konsep menjadi utilitas komputasi konkuren yang self-contained:

```go
// File: cmd/runtime_demo/main.go
package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"runtime"
	"runtime/metrics"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

// ProcessPayload mendemonstrasikan struct berorientasi efisiensi cache
type ProcessPayload struct {
	ID        uint64
	Timestamp int64
	Value     float64
}

// MemoryManager mengelola reuse memori payload
type MemoryManager struct {
	pool sync.Pool
}

func NewMemoryManager() *MemoryManager {
	return &MemoryManager{
		pool: sync.Pool{
			New: func() any {
				return new(ProcessPayload)
			},
		},
	}
}

func (mm *MemoryManager) Acquire(id uint64, val float64) *ProcessPayload {
	p := mm.pool.Get().(*ProcessPayload)
	p.ID = id
	p.Timestamp = time.Now().UnixNano()
	p.Value = val
	return p
}

func (mm *MemoryManager) Release(p *ProcessPayload) {
	mm.pool.Put(p)
}

func printRuntimeDiagnostic() {
	const goroutinesMetric = "/sched/goroutines:goroutines"
	const heapAllocMetric = "/memory/classes/heap/objects:bytes"

	samples := make([]metrics.Sample, 2)
	samples[0].Name = goroutinesMetric
	samples[1].Name = heapAllocMetric

	metrics.Read(samples)

	fmt.Printf("\n--- [System Runtime Metric Report] ---\n")
	fmt.Printf("Logical Processors (P)    : %d\n", runtime.GOMAXPROCS(0))
	fmt.Printf("Active OS Threads (M)     : %d\n", runtime.NumGoroutine())
	fmt.Printf("Metric - Goroutine Total  : %d\n", samples[0].Value.Uint64())
	fmt.Printf("Metric - Active Heap Obj  : %d Bytes\n", samples[1].Value.Uint64())
	fmt.Printf("--------------------------------------\n\n")
}

func main() {
	fmt.Println("Memulai Demonstrasi Ekosistem Runtime Go...")

	// 1. Tangkap sinyal OS untuk Graceful Shutdown
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	memMgr := NewMemoryManager()
	var processedCount atomic.Uint64
	workerCount := runtime.GOMAXPROCS(0)
	taskQueue := make(chan *ProcessPayload, 1000)
	var wg sync.WaitGroup

	// 2. Spawn Bounded Worker Pool (Mencegah Unbounded Goroutines)
	for i := 0; i < workerCount; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			for {
				select {
				case <-ctx.Done():
					return
				case task, ok := <-taskQueue:
					if !ok {
						return
					}
					// Simulasi kalkulasi CPU ringan
					_ = task.Value * 3.14159
					processedCount.Add(1)
					memMgr.Release(task)
				}
			}
		}(i)
	}

	// 3. Task Producer
	producerDone := make(chan struct{})
	go func() {
		defer close(producerDone)
		var seq uint64
		ticker := time.NewTicker(50 * time.Microsecond)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				seq++
				task := memMgr.Acquire(seq, float64(seq)*0.5)
				select {
				case taskQueue <- task:
				default:
					// Jika antrean saturasi, segera kembalikan payload ke sync.Pool
					memMgr.Release(task)
				}
			}
		}
	}()

	// 4. Runtime Observer Loop
	metricsTicker := time.NewTicker(1 * time.Second)
	defer metricsTicker.Stop()

	go func() {
		for {
			select {
			case <-ctx.Done():
				return
			case <-metricsTicker.C:
				printRuntimeDiagnostic()
			}
		}
	}()

	fmt.Println("Sistem beroperasi. Tekan CTRL+C untuk memicu terminasi aman...")
	<-ctx.Done()
	fmt.Println("\nSinyal terminasi diterima, menguras pipeline (draining)...")

	<-producerDone
	close(taskQueue)
	wg.Wait()

	fmt.Printf("Shutdown selesai secara deterministik. Total payload diproses: %d\n", processedCount.Load())
}
```

---

### 18. Guided Exercises

#### Exercise 1 (Guided / Level 1)
* **Problem**: Ubah fungsi berikut agar compiler tidak memindahkan variabel `UserSession` ke heap.
  ```go
  type UserSession struct {
      UserID   uint64
      IsActive bool
  }

  func CreateSession(id uint64) *UserSession {
      s := UserSession{UserID: id, IsActive: true}
      return &s
  }
  ```
* **Hint**: Evaluasi escape analysis. Jika Anda me-return pointer dari stack frame lokal, compiler Go *wajib* mengalokasikannya ke Heap. Pertimbangkan perancangan passing pointer ke dalam fungsi (*inversion of allocation control*).

#### Exercise 2 (Unguided with Constraints / Level 2)
* **Problem**: Rancang sebuah pipeline streaming pemrosesan log yang membaca chunk data 64KB. Sistem harus mampu mempertahankan alokasi heap di angka **$0\text{ B/op}$** pada benchmark test.
* **Constraints**:
  * Gunakan `sync.Pool`.
  * Dilarang menggunakan `fmt.Sprintf` atau `fmt.Println` di critical execution path.
  * Verifikasi menggunakan flag benchmark `-benchmem`.

#### Exercise 3 (Challenge / Level 3)
* **Problem**: Buat simulasi *Work-Stealing Scheduler* primitif menggunakan Go.
* **Constraints**:
  * Definisikan struct `SimpleP` yang memiliki ring buffer LRQ berukuran 16 elemen.
  * Buat algoritma pencurian di mana jika `SimpleP` lokal kehabisan task, ia menggunakan atomic load untuk mengambil separuh isi task dari antrean `SimpleP` target tanpa menimbulkan *deadlock*.

---

### 19. Enterprise Case Study
**Skenario**: Sistem Payment Gateway FinTech mengalami lonjakan *p99 latency* dari 15ms menjadi 1800ms tiap kali lonjakan transaksi 10.000 TPS (*Transactions Per Second*) terjadi. Analisis CPU profiler menunjukkan bahwa CPU utilization menyentuh 100%, di mana 65% siklus CPU dihabiskan oleh fungsi `runtime.gcBgMarkWorker`.

**Investigasi & Analisis Akar Masalah**:
1. Tim backend mengonversi payload transaksi internal menjadi struct logging menggunakan `any` interface, memicu *hidden escape to heap* sebanyak 10.000 alokasi/detik untuk tipe data primitif.
2. Setiap request HTTP memicu pembentukan goroutine baru tanpa kontrol batas (*unbounded*). P scheduler dipaksa mengelola jutaan runnable goroutines, membebani heap allocations secara masif.
3. Pod memiliki memory limit 2GB, namun tidak ada variabel `GOMEMLIMIT` yang dikonfigurasi. GC berjalan agresif hanya mengandalkan nilai default `GOGC=100`.

**Solusi & Resolusi Arsitektur**:
1. Menghilangkan logging berbasis dynamic interface di critical path; beralih ke Zero-Allocation Logger berbasis byte buffers.
2. Mengganti pola Goroutine ad-hoc dengan *Worker Pool* yang dipatok sebanding dengan jumlah alokasi CPU core Pod (`runtime.GOMAXPROCS(0)`).
3. Mengonfigurasi parameter pod: `GOMEMLIMIT=1800MiB` dan menurunkan `GOGC=80`.
4. **Hasil**: Latensi *p99* turun drastis ke 4.2ms pada beban 10.000 TPS. Alokasi siklus GC berkurang dari 65% menjadi hanya 4% dari total CPU resources.

---

### 20. Self-Assessment & Knowledge Check

1. **Apa perbedaan mendasar antara alokasi variabel via Contiguous Stack vs Heap pada Go runtime?**
   * *Jawaban Model Teknis*: Alokasi stack bersifat terisolasi per Goroutine, diproses instan dengan menggeser pointer register `SP`, memori dibersihkan seketika saat fungsi return tanpa melibatkan Garbage Collector. Alokasi Heap bersifat global, dikelola melalui algoritma allocator TCMalloc (mcache/mcentral/mheap), membutuhkan lock/atomic synchronization pada multi-size allocations, serta memerlukan pelacakan siklus *Concurrent Mark-Sweep* GC yang mengonsumsi bandwidth CPU dan STW latency.

2. **Mengapa pemanggilan fungsi `fmt.Println(myVar)` hampir selalu menyebabkan `myVar` di-escape ke Heap oleh compiler?**
   * *Jawaban Model Teknis*: Fungsi signature `fmt.Println(a ...any)` menerima parameter variadik dari tipe interface kosong (`interface{}` / `any`). Compiler Go tidak dapat memprediksi secara deterministik pada fase kompilasi bagaimana implementasi package `fmt` akan menggunakan pointer variabel tersebut, sehingga variabel dikonversi via runtime `convT` dan terpaksa dipindahkan ke heap.

3. **Bagaimana mekanisme Go runtime menangani Goroutine yang terblokir pada Network I/O versus Goroutine yang terblokir pada Blocking File System Call?**
   * *Jawaban Model Teknis*: Pada Network I/O, Go mengalihkan Goroutine ke *Network Poller* internal (berbasis `epoll`/`kqueue`/`IOCP`). Goroutine dilepas dari thread OS `M`, dan `M` dapat langsung mengeksekusi Goroutine runnable lainnya. Pada Blocking File I/O (yang tidak selalu mendukung non-blocking epoll di semua kernel OS), thread `M` harus terblokir di level kernel bersama Goroutine tersebut, memicu mekanisme *P-Handoff* di mana `P` melepaskan diri dari `M` yang terblokir dan berpindah ke thread `M` baru untuk melanjutkan pekerjaan.

4. **Kapan alokasi memori sebuah Goroutine stack digandakan (stack growth), dan apa dampaknya terhadap pointer lokal?**
   * *Jawaban Model Teknis*: Pada setiap prolog fungsi (kecuali jika ditandai `//go:nosplit`), compiler menyisipkan pengecekan batas stack (*stack bound check*). Jika frame fungsi baru melampaui batas stack 2KB (atau kapasitas saat itu), runtime memanggil `runtime.morestack`, yang mengalokasikan memori contiguous baru sebesar 2x lipat, memindahkan isi stack lama ke stack baru, dan melakukan penyesuaian (*pointer adjustment*) terhadap seluruh alamat pointer yang merujuk ke elemen-elemen di stack lama agar menunjuk ke lokasi memori baru.

5. **Apa fungsi thread `sysmon` dalam runtime Go dan mengapa ia tidak membutuhkan logical Processor `P`?**
   * *Jawaban Model Teknis*: `sysmon` (*system monitor*) adalah background kernel thread OS yang beroperasi mandiri tanpa asosiasi ke `P` agar ia tidak terhalang oleh siklus penjadwalan aplikasi. Tugasnya mencakup: menarik Goroutine dari network poller yang telah siap dieksekusi, memicu preemption paksa via sinyal `SIGURG` terhadap Goroutine yang berjalan lebih dari 10ms, memaksa siklus GC berjalan jika belum berjalan dalam 2 menit terakhir, serta mengambil kembali `P` yang ditinggalkan oleh syscall yang terblokir lama.