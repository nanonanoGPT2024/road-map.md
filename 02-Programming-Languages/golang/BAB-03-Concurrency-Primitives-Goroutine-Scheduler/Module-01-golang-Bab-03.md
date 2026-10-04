# Bab 03 Module 01: Concurrency Primitives & Goroutine Scheduler

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** 02-Programming-Languages
* **Track:** Go (Golang) Enterprise Engineering
* **Bab:** 03 — Advanced Concurrency & Systems Architecture
* **Modul:** 01 — Concurrency Primitives & Goroutine Scheduler
* **Tingkat Kesulitan:** Advanced / Senior Level
* **Prasyarat:** Pemahaman sintaks Go dasar, Pointer, Interface, Memory Layout (Stack vs Heap), serta pengenalan dasar System Calls (Syscalls) pada sistem operasi berbasis UNIX.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Mendekonstruksi Model GMP:** Menjelaskan secara presisi siklus hidup eksekusi runtime Go melalui interaksi entitas *Goroutine* ($G$), *Machine/OS Thread* ($M$), dan *Logical Processor* ($P$).
2. **Menganalisis Algoritma Work-Stealing & Preemption:** Menguraikan proses mitigasi thread starvation via Local Run Queue (LRQ), Global Run Queue (GRQ), Network Poller, serta mekanisme *asynchronous preemption* berbasis sinyal OS (`SIGURG`).
3. **Menguasai Primitif Sinkronisasi Standar:** Memilih dan mengimplementasikan primitif konkurensi dari package `sync` (`Mutex`, `RWMutex`, `WaitGroup`, `Once`, `Cond`) dan operasi atomik (`sync/atomic`) secara aman tanpa race condition.
4. **Menerapkan Pola Channeling Tingkat Lanjut:** Mengonstruksi alur data terisolasi menggunakan unbuffered vs buffered channel, fan-out/fan-in, worker pools, dan multiplexing via statement `select`.
5. **Mendiagnosis Concurrency Bugs:** Mendeteksi deadlock, livelock, data race, dan goroutine leak menggunakan Race Detector (`-race`) serta Runtime Execution Tracer (`go tool trace`).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam paradigma rekayasa perangkat lunak modern, konkurensi (*concurrency*) sering kali disalahartikan sebagai paralelisme (*parallelism*). Mental model yang tepat adalah:

> **Konkurensi adalah tentang menangani banyak hal sekaligus (struktur komposisi kode), sedangkan Paralelisme adalah tentang melakukan banyak hal pada saat yang persis sama (eksekusi fisik pada multi-core hardware).**

```
     CONCURRENCY (Komposisi Struktur)            PARALLELISM (Eksekusi Fisik)
     
        Task A       Task B                       Core 1: Task A [====]
        [====]       [----]                       Core 2: Task B [----]
           \          /                                      (Bersamaan)
            v        v
        Single CPU Core (Interleaved)
```

Untuk memahami Go Runtime:
* Bayangkan **$M$ (Machine)** sebagai pekerja fisik (karyawan/OS thread) yang digaji mahal dan membutuhkan seragam berat.
* Bayangkan **$P$ (Processor)** sebagai meja kerja atau izin lisensi kerja yang jumlahnya terbatas (`GOMAXPROCS`). Pekerja ($M$) tidak dapat bekerja tanpa meja ($P$).
* Bayangkan **$G$ (Goroutine)** sebagai lembar instruksi tugas yang sangat ringan. Ribuan lembar tugas dapat menumpuk di laci meja ($P$), dan pekerja ($M$) menyelesaikannya satu per satu secara bergantian.

Jangan menganggap Goroutine sebagai thread murah semata. Goroutine adalah *user-space cooperatively-scheduled tasks with runtime-enforced asynchronous preemption*. Jangan berkomunikasi dengan membagikan memori; sebaliknya, bagikan memori dengan berkomunikasi (*"Do not communicate by sharing memory; instead, share memory by communicating"*). Namun, pahami kapan aturan emas ini harus dikesampingkan demi kebutuhan performa latensi ultra-rendah yang menuntut primitif sinkronisasi berbasis memori bersama (`sync/atomic` atau `sync.Mutex`).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Model penjadwalan Go Runtime bergantung pada model $M:N$, di mana $M$ goroutine dipetakan ke $N$ kernel OS thread dengan perantara $P$ logical context.

### 1. Arsitektur Komponen Runtime GMP

```
+-----------------------------------------------------------------------+
|                         GLOBAL RUN QUEUE (GRQ)                        |
|                         [ G5, G6, G7, G8, ... ]                       |
+-----------------------------------------------------------------------+
        ^                                               ^
        | lock-protected                                | lock-protected
        v                                               v
+------------------+                            +------------------+
|   PROCESSOR (P0) |                            |   PROCESSOR (P1) |
| [LRQ: G2, G3, G4]| <--- Work Stealing (50%) - | [LRQ: (Empty)]   |
+------------------+                            +------------------+
        |                                               |
        | binds to                                      | binds to
        v                                               v
+------------------+                            +------------------+
|   THREAD (M0)    |                            |   THREAD (M1)    |
|   Executing G1   |                            |   Idle/Searching |
+------------------+                            +------------------+
        |                                               |
======================= KERNEL SPACE (OS) ===============================
        |                                               |
+------------------+                            +------------------+
|    CPU Core 0    |                            |    CPU Core 1    |
+------------------+                            +------------------+
```

### 2. Syscall Handoff Architecture & Network Poller

Ketika $G$ melakukan blocking I/O (Syscall atau Network Socket):

```
Skenario A: Blocking Syscall (Read/Write Disk File)
+-----+     Detaches     +-----+     Binds to New/Idle M     +-----+
|  P  | -------------->  | M0  |     ===================>    |  P  |
+-----+                  +-----+                             +-----+
                           |                                    |
                           v (Blocking)                         v
                         +-----+                              +-----+
                         |  G1 |                              |  M2 | (Executes G2)
                         +-----+                              +-----+

Skenario B: Network I/O Non-Blocking (Network Poller via epoll/kqueue)
+-----+     G1 blocks     +--------------------+     Ready     +-----+
|  M  |    on Network     |   NETWORK POLLER   | ===========>  | LRQ |
|  P  | ----------------> |  (epoll / kqueue)  |               +-----+
+-----+                   +--------------------+                  |
   |                                                              v
Executes G2                                                  P picks G1 up
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Struktur Data Inti Runtime Go

Diimplementasikan dalam direktori runtime engine Go (`src/runtime/runtime2.go`):

#### 1. Entitas $G$ (Goroutine)
* **`stack`**: Batas memori stack nyata (`lo` dan `hi`).
* **`sched` (`gobuf`)**: Konteks eksekusi penyimpan program counter (`pc`), stack pointer (`sp`), register flags, dan referensi pointer ke $G$ itu sendiri.
* **`atomicstatus`**: Status lifecycle goroutine (`_Gidle`, `_Grunnable`, `_Grunning`, `_Gsyscall`, `_Gwaiting`, `_Gdead`).
* **`preempt`**: Boolean flag untuk permintaan cooperative preemption.

#### 2. Entitas $M$ (Machine)
* Mewakili kernel thread yang dibuat oleh clone/pthread OS.
* **`g0`**: Goroutine khusus dengan alokasi stack besar bawaan OS (bukan stack dinamis) yang bertugas mengeksekusi kode penjadwalan runtime (alokasi memori, runtime scheduler, GC).
* **`curg`**: Pointer ke goroutine aplikasi ($G$) yang sedang berjalan pada saat ini.
* **`p`**: Pointer ke logical processor ($P$) yang sedang digenggam untuk eksekusi kode Go.

#### 3. Entitas $P$ (Processor)
* Mewakili resource yang dibutuhkan untuk mengeksekusi Go code. Dikonfigurasi default sesuai `runtime.NumCPU()`.
* **`runq`**: Local Run Queue (LRQ), circular buffer berkapasitas 256 goroutine yang bersifat lock-free (menggunakan atomic operations untuk push/pop dari thread pemilik).
* **`runnext`**: Pointer prioritas khusus untuk $G$ berikutnya yang dieksekusi secara instan, mengabaikan antrean umum guna memaksimalkan *cache locality*.

### Siklus Penjadwalan & Algoritma Work-Stealing

Ketika sebuah $M$ terasosiasi dengan $P$, eksekusi loop internal (`runtime.schedule()`) berjalan:

```
[M Cari Tugas]
      |
      v
1. Periksa giliran Global Run Queue (GRQ) setiap 61 ticks scheduler (Cegah Starvation GRQ)
      |
      +---> Ditemukan? --> Eksekusi G
      |
      v (Tidak)
2. Periksa P.runnext, kemudian Local Run Queue (LRQ) milik P sendiri
      |
      +---> Ditemukan? --> Eksekusi G
      |
      v (Tidak)
3. Periksa Network Poller (epoll_wait secara non-blocking)
      |
      +---> Ada G siap? --> Masukkan antrean & Eksekusi G
      |
      v (Tidak)
4. Work-Stealing: Kunjungi P lain secara acak 4 kali lipat, coba curi setengah (50%) isi LRQ target
      |
      +---> Ditemukan? --> Pindahkan ke LRQ lokal & Eksekusi G
      |
      v (Tidak)
5. Kunjungi GRQ dengan locking global
      |
      +---> Ditemukan? --> Ambil batch & Eksekusi G
      |
      v (Tidak)
6. Polling Network Poller secara blocking, atau lepaskan P, parkirkan M (Thread Sleep)
```

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Evolusi Preemption: Cooperative ke Asynchronous Signal-Based

Hingga Go 1.13, scheduler Go murni beroperasi secara *cooperative*. Titik preemption disisipkan oleh compiler hanya pada prologue fungsi (pemeriksaan `morestack()` untuk membesarkan stack). Kelemahan fatal pola ini: jika terdapat goroutine yang mengeksekusi tight-loop tanpa pemanggilan fungsi (`for {}`), goroutine tersebut memonopoli $P$ tanpa bisa dihentikan, melumpuhkan garbage collection dan goroutine lain (*thread starvation*).

Dimulai dari Go 1.14, implementasi **Asynchronous Preemption** diperkenalkan:
* Runtime mengaktifkan timer internal (`sysmon` thread).
* Jika sebuah $G$ berjalan lebih dari 10ms tanpa henti pada core yang sama, `sysmon` mengirimkan sinyal OS posix: **`SIGURG`** ke thread $M$ yang menjalankannya.
* Signal handler OS menginterupsi register $M$, menyimpan status komputasi saat itu, dan membelokkan instruksi penunjuk instruction pointer program counter register ke `runtime.asyncPreempt`.
* Goroutine dipindahkan secara paksa ke status `_Grunnable` dan dimasukkan ke Global Run Queue (GRQ), membebaskan $P$ untuk melayani $G$ lain.

### 2. Segmented Stacks vs Dynamic Contiguous Stacks

* **Thread OS Tradisional:** Memerlukan alokasi memori stack statis berukuran 1MB - 8MB sejak awal deklarasi. Jika membuat 10.000 thread, dialokasikan $~10-80\text{ GB}$ memori virtual.
* **Goroutine Awal (Go < 1.4):** Menggunakan *segmented stacks*. Stack dialokasikan 2KB, jika habis membuat segmen 2KB lain yang dihubungkan dengan linked list (*stack split*). Masalah muncul saat fungsi bolak-balik melewati batas ambang segmen, memicu kondisi *hot split overhead* (alokasi dan dealokasi berulang secara agresif).
* **Goroutine Modern (Go 1.4+):** Menggunakan **Contiguous Stack**.
  * Dimulai dari ukuran sangat kecil: **2 KB**.
  * Jika goroutine membutuhkan stack lebih besar, runtime mengalokasikan blok memori contiguous baru sebesar **2x lipat**, menyalin seluruh isi frame stack lama ke lokasi baru, memutakhirkan seluruh pointer lokal internal, dan menghancurkan frame stack lama.
  * Stack dapat menyusut (halving) saat garbage collector mendeteksi pemakaian stack kurang dari seperempat kapasitas pasca-eksekusi fungsi berat.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL (STEP-BY-STEP)

Berikut adalah program fungsional yang mendemonstrasikan orkestrasi konkurensi: pembatasan akses resource via bounded channel pool, penghentian anggun via cancellation `context`, pengamanan state via `sync.RWMutex`, dan penungguan via `sync.WaitGroup`.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"sync/atomic"
	"time"
)

// Task merepresentasikan unit pekerjaan terisolasi.
type Task struct {
	ID       int
	Payload  string
	Result   string
	Err      error
}

// ThreadSafeRegistry menyimpan status runtime secara konkuren.
type ThreadSafeRegistry struct {
	mu      sync.RWMutex
	records map[int]string
}

func NewRegistry() *ThreadSafeRegistry {
	return &ThreadSafeRegistry{
		records: make(map[int]string),
	}
}

func (r *ThreadSafeRegistry) Set(id int, val string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.records[id] = val
}

func (r *ThreadSafeRegistry) Get(id int) (string, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	val, ok := r.records[id]
	return val, ok
}

// WorkerPool membatasi concurrency throughput.
type WorkerPool struct {
	concurrency int
	taskQueue   chan Task
	resultQueue chan Task
	registry    *ThreadSafeRegistry
	processed   uint64
	wg          sync.WaitGroup
}

func NewWorkerPool(concurrency int, queueCap int, reg *ThreadSafeRegistry) *WorkerPool {
	return &WorkerPool{
		concurrency: concurrency,
		taskQueue:   make(chan Task, queueCap),
		resultQueue: make(chan Task, queueCap),
		registry:    reg,
	}
}

func (wp *WorkerPool) Start(ctx context.Context) {
	for i := 1; i <= wp.concurrency; i++ {
		wp.wg.Add(1)
		go wp.worker(ctx, i)
	}
}

func (wp *WorkerPool) worker(ctx context.Context, workerID int) {
	defer wp.wg.Done()
	for {
		select {
		case <-ctx.Done():
			// Handle graceful shutdown saat context dibatalkan
			return
		case task, ok := <-wp.taskQueue:
			if !ok {
				// Task queue ditutup, drain selesai
				return
			}

			// Eksekusi pekerjaan
			processedTask := wp.executeTask(ctx, workerID, task)

			// Kirim hasil atau abort jika context cancel
			select {
			case wp.resultQueue <- processedTask:
				atomic.AddUint64(&wp.processed, 1)
			case <-ctx.Done():
				return
			}
		}
	}
}

func (wp *WorkerPool) executeTask(ctx context.Context, workerID int, t Task) Task {
	// Simulasi CPU/IO bound dengan pengecekan context interrupt
	select {
	case <-ctx.Done():
		t.Err = ctx.Err()
		return t
	case <-time.After(10 * time.Millisecond):
		if t.ID%7 == 0 {
			t.Err = errors.New("simulated transient failure")
			return t
		}
		t.Result = fmt.Sprintf("Handled by Worker-%d at %s", workerID, time.Now().Format(time.RFC3339Nano))
		wp.registry.Set(t.ID, t.Result)
		return t
	}
}

func (wp *WorkerPool) Submit(ctx context.Context, t Task) bool {
	select {
	case <-ctx.Done():
		return false
	case wp.taskQueue <- t:
		return true
	}
}

func (wp *WorkerPool) Stop() {
	close(wp.taskQueue)
	wp.wg.Wait()
	close(wp.resultQueue)
}

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	registry := NewRegistry()
	pool := NewWorkerPool(4, 20, registry)

	pool.Start(ctx)

	// Goroutine untuk pipeline pengumpul hasil (Consumer)
	collectorDone := make(chan struct{})
	go func() {
		defer close(collectorDone)
		for res := range pool.resultQueue {
			if res.Err != nil {
				fmt.Printf("[REJECTED] Task %d: %v\n", res.ID, res.Err)
				continue
			}
			fmt.Printf("[RESOLVED] Task %d -> %s\n", res.ID, res.Result)
		}
	}()

	// Producer mempublikasikan task
	go func() {
		for i := 1; i <= 30; i++ {
			task := Task{ID: i, Payload: fmt.Sprintf("Data-%d", i)}
			if !pool.Submit(ctx, task) {
				fmt.Printf("[DROPPED] Context deadline exceeded saat submit Task %d\n", i)
				break
			}
		}
		pool.Stop()
	}()

	<-collectorDone
	fmt.Printf("Total Task Berhasil Diproses: %d\n", atomic.LoadUint64(&pool.processed))
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut dekonstruksi mekanis instruksi dari kode di atas:

1. **`type ThreadSafeRegistry struct` & `sync.RWMutex`:**
   * Baris ini mendeklarasikan struktur shared memory. Pemisahan antara `mu.RLock()` dan `mu.Lock()` mengizinkan pembacaan simultan tak terbatas oleh ratusan goroutine, namun memblokir seluruh operasi ketika ada satu goroutine yang mengeksekusi penulisan mutating map (`records`).
2. **`atomic.AddUint64(&wp.processed, 1)`:**
   * Menghindari lock overhead untuk operasi counter tunggal. Diterjemahkan langsung menjadi instruksi CPU tingkat rendah berawalan lock prefix (`LOCK XADDQ` pada arsitektur x86_64) yang menjamin atomisitas modifikasi memori pada level level-1/level-2 CPU cache line.
3. **`wp.taskQueue <-make(chan Task, queueCap)`:**
   * Mengalokasikan un-allocated ring-buffer thread-safe di heap. Melindungi memory starvation dan membatasi backpressure bila producer beroperasi lebih cepat dari kemampuan processing worker.
4. **`select { case <-ctx.Done(): ... case task, ok := <-wp.taskQueue: ... }`:**
   * Mencegah thread blocking permanen. Pernyataan `select` dikompilasi ke runtime call `runtime.selectgo()`, yang mengacak polling antrean channel agar tidak terjadi bias starvation pada cabang evaluasi pertama. Pengecekan `if !ok` penting untuk mendeteksi penutupan antrean hulu (*closed channel draining*).
5. **`pool.Stop()` Implementation Pattern:**
   * Menggunakan urutan strict deterministic teardown: `close(taskQueue)` menandakan tidak ada data baru, `wp.wg.Wait()` menahan caller sampai semua alur goroutine pekerja benar-benar keluar dari stack execution, kemudian `close(resultQueue)` mengakhiri loop channel reader collector secara elegan tanpa memicu panic runtime `send on closed channel`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Real-Time High-Throughput Financial Event Processing Gateway

Sebuah perusahaan fintech payment gateway memproses ribuan payload webhook transaksi per detik dari puluhan perbankan mitra. 

#### Tantangan Masalah Arsitektur:
1. **Unbounded Goroutine Spawning:** Model lama menggunakan `go handleWebhook(req)` pada setiap request HTTP yang masuk. Saat terjadi lonjakan trafik mendadak (15.000 req/detik) berbarengan dengan melambatnya database downstream (p99 latency naik dari 5ms ke 1.200ms), jumlah goroutine melonjak dari 500 menjadi 250.000 dalam 30 detik.
2. **OOM Crash (Out of Memory):** 250.000 goroutine dengan stack dasar 2KB ditambah escape analysis payload rata-rata 32KB menghabiskan memori fisik hingga menyentuh batas cgroup memory limit di Kubernetes. OOM-Killer mematikan container berulang kali.
3. **High Latency Tail (GC Pauses):** Heap runtime membengkak memicu Garbage Collector bekerja terus-menerus (*stop-the-world scanning phase saturation*), CPU throttled 100%.

#### Solusi Berbasis Primitif Konkurensi:
* Membangun **Tiered Concurrency Pipeline**: Menggunakan fixed-size internal Ring Worker Pool yang dipasangkan dengan semaphore pattern via buffered channel untuk backpressure control.
* Menerapkan pembatasan kapasitas buffer transien: Jika buffer penuh, kembalikan response `429 Too Many Requests` (shedding load) secara instan ke upstream alih-alih menumpuk memory leak tak berujung.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Sistem Gateway Transaksi Keuangan dengan Adaptive In-Memory Ring Worker Pool, Rate-Limiting, Data Race Free, dan Graceful Eviction.

```go
package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"os/signal"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

var (
	ErrQueueFull = errors.New("pipeline capacity saturated: shedding load")
	ErrShuttingDown = errors.New("service is gracefully shutting down")
)

type PaymentEvent struct {
	TransactionID string
	AccountID     string
	AmountCents   int64
	Timestamp     int64
	Signature     string
}

type EventResult struct {
	TransactionID string
	Success       bool
	Checksum      string
	Duration      time.Duration
	Err           error
}

type PaymentProcessorEngine struct {
	concurrencyLimit int
	capacity         int
	inboundQueue     chan PaymentEvent
	results          chan EventResult
	isClosed         uint32
	activeWorkers    sync.WaitGroup
	metricsProcessed uint64
	metricsDropped   uint64
}

func NewPaymentProcessorEngine(workers int, queueCapacity int) *PaymentProcessorEngine {
	return &PaymentProcessorEngine{
		concurrencyLimit: workers,
		capacity:         queueCapacity,
		inboundQueue:     make(chan PaymentEvent, queueCapacity),
		results:          make(chan EventResult, queueCapacity),
	}
}

func (pe *PaymentProcessorEngine) Start(ctx context.Context) {
	for i := 0; i < pe.concurrencyLimit; i++ {
		pe.activeWorkers.Add(1)
		go pe.workerLoop(ctx, i)
	}
}

func (pe *PaymentProcessorEngine) workerLoop(ctx context.Context, workerID int) {
	defer pe.activeWorkers.Done()

	for {
		select {
		case <-ctx.Done():
			return
		case event, ok := <-pe.inboundQueue:
			if !ok {
				return
			}
			res := pe.processTransaction(ctx, event)
			
			// Non-blocking result push dengan context-fallback
			select {
			case pe.results <- res:
				atomic.AddUint64(&pe.metricsProcessed, 1)
			case <-ctx.Done():
				return
			}
		}
	}
}

func (pe *PaymentProcessorEngine) processTransaction(ctx context.Context, evt PaymentEvent) EventResult {
	start := time.Now()

	// Simulasi CPU Intensive: Validasi Hash Kriptografi
	hasher := sha256.New()
	hasher.Write([]byte(fmt.Sprintf("%s:%s:%d:%d", evt.TransactionID, evt.AccountID, evt.AmountCents, evt.Timestamp)))
	calculatedChecksum := hex.EncodeToString(hasher.Sum(nil))

	// Validasi business rules
	if evt.AmountCents <= 0 {
		return EventResult{
			TransactionID: evt.TransactionID,
			Success:       false,
			Duration:      time.Since(start),
			Err:           errors.New("invalid transaction amount"),
		}
	}

	// Simulasi downstream persistence latency
	select {
	case <-time.After(2 * time.Millisecond):
	case <-ctx.Done():
		return EventResult{
			TransactionID: evt.TransactionID,
			Success:       false,
			Duration:      time.Since(start),
			Err:           ctx.Err(),
		}
	}

	return EventResult{
		TransactionID: evt.TransactionID,
		Success:       true,
		Checksum:      calculatedChecksum,
		Duration:      time.Since(start),
		Err:           nil,
	}
}

// EnqueueEvent: Mengimplementasikan non-blocking shedding load (Fast Fail)
func (pe *PaymentProcessorEngine) EnqueueEvent(evt PaymentEvent) error {
	if atomic.LoadUint32(&pe.isClosed) == 1 {
		return ErrShuttingDown
	}

	select {
	case pe.inboundQueue <- evt:
		return nil
	default:
		// Queue penuh, fast shedding load untuk mempertahankan sistem
		atomic.AddUint64(&pe.metricsDropped, 1)
		return ErrQueueFull
	}
}

func (pe *PaymentProcessorEngine) Shutdown(ctx context.Context) error {
	// Tandai status shutdown
	if !atomic.CompareAndSwapUint32(&pe.isClosed, 0, 1) {
		return errors.New("shutdown already invoked")
	}

	close(pe.inboundQueue) // Pekerja berhenti mengambil setelah mengosongkan antrean

	// Channel sinyal penyelesaian drain
	drained := make(chan struct{})
	go func() {
		pe.activeWorkers.Wait()
		close(pe.results)
		close(drained)
	}()

	select {
	case <-drained:
		return nil
	case <-ctx.Done():
		return errors.New("shutdown timeout: some workers abandoned")
	}
}

func main() {
	rootCtx, rootCancel := context.WithCancel(context.Background())
	defer rootCancel()

	// Inisialisasi engine: 8 Pekerja (terisolasi pada P), antrean buffer 500
	engine := NewPaymentProcessorEngine(8, 500)
	engine.Start(rootCtx)

	// Pipeline result logger
	var auditWg sync.WaitGroup
	auditWg.Add(1)
	go func() {
		defer auditWg.Done()
		for res := range engine.results {
			if res.Err != nil {
				// Log level Error pada production
				continue
			}
			// Telemetry reporting simulation
		}
	}()

	// Simulasi load producer (10.000 events)
	go func() {
		for i := 1; i <= 10000; i++ {
			evt := PaymentEvent{
				TransactionID: fmt.Sprintf("tx-uuid-%05d", i),
				AccountID:     fmt.Sprintf("acc-%d", i%100),
				AmountCents:   int64(i * 150),
				Timestamp:     time.Now().UnixNano(),
			}

			err := engine.EnqueueEvent(evt)
			if err != nil {
				// Catat drop event
			}
			time.Sleep(100 * time.Microsecond) // Rate injection
		}
	}()

	// Tangani OS Signal Graceful Termination
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	// Tunggu sinyal interupsi atau simulasi run duration
	select {
	case <-sigChan:
		fmt.Println("\n[SYSTEM] Menerima sinyal termination, memulai graceful shutdown...")
	case <-time.After(3 * time.Second):
		fmt.Println("\n[SYSTEM] Batas durasi benchmark selesai, menghentikan antrean...")
	}

	// Alokasikan deadline waktu shutdown maksimal 2 detik
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer shutdownCancel()

	if err := engine.Shutdown(shutdownCtx); err != nil {
		fmt.Printf("[ALERT] Shutdown abnormal: %v\n", err)
	} else {
		fmt.Println("[SUCCESS] Seluruh antrean berhasil didrain tanpa kehilangan transaksi valid.")
	}

	auditWg.Wait()

	fmt.Printf("[METRICS] Transaksi Sukses: %d | Transaksi Di-drop (Shedded): %d\n",
		atomic.LoadUint64(&engine.metricsProcessed),
		atomic.LoadUint64(&engine.metricsDropped),
	)
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Tabel Komparasi: Primitif Sinkronisasi & Komunikasi

| Karakteristik | `sync.Mutex` | `sync.RWMutex` | Unbuffered Channel | Buffered Channel | `sync/atomic` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Kasus Penggunaan Optimal** | Mutasi data struct internal kompleks | Rasio Read >> Write (misal: Dynamic Config) | Sinkronisasi rendezvous, jaminan serah terima | Pipeline decoupling, Worker Pool backpressure | Counter, flags state, pointer swap terisolasi |
| **Overhead CPU** | Sangat Rendah | Sedang-Tinggi (bila write contention tinggi) | Menengah (runtime scheduling lock) | Menengah (ring-buffer locking) | Terendah (hardware level instructions) |
| **Throughput Penulisan** | Tinggi | Rendah jika Read terus memegang kunci | Terbatas sinkronisasi | Tinggi hingga buffer penuh | Maksimal |
| **Throughput Pembacaan** | Terserialisasi | Paralel (skalabilitas tinggi) | Terserialisasi | Terserialisasi | Paralel maksimal |
| **Risiko Deadlock** | Tinggi (jika locking ganda tanpa urutan) | Sangat Tinggi (Writer Starvation / Reentrant) | Tinggi (sender/receiver tertahan selamanya) | Sedang (deadlock terjadi saat buffer jenuh) | Nol |
| **Alokasi Heap** | Zero alokasi | Zero alokasi | Mengalokasikan struct `hchan` di heap | Mengalokasikan struct `hchan` + memory buffer | Zero alokasi |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Channel Nil Block Permanen
Membaca atau menulis ke channel bernilai `nil` (`var ch chan int`) tidak menyebabkan panic runtime melainkan memblokir goroutine secara permanen untuk selamanya (*perpetual sleep*). Menutup channel nil memicu panic `panic: close of nil channel`.

### 2. Send On Closed Channel Panic
Mengirim data ke channel yang telah ditutup memicu panic instan yang mematikan proses: `panic: send on closed channel`. Pola arsitektur yang aman: **Hanya goroutine pembuat data (producer) yang berhak menutup channel (Never close from consumer side).**

### 3. Reentrant Lock Deadlock pada `sync.Mutex`
Tidak seperti `ReentrantLock` di Java, `sync.Mutex` pada Go **tidak bersifat reentrant**. Jika goroutine yang sama memanggil `.Lock()` dua kali berturut-turut pada mutex yang sama tanpa membukanya, goroutine akan mengalami self-deadlock.

```go
// ANTI-PATTERN: Menghasilkan self-deadlock fatal
func UpdateProfile(mu *sync.Mutex) {
    mu.Lock()
    defer mu.Unlock()
    // Operasi internal...
    UpdateAddress(mu) // DEADLOCK! mu terkunci oleh dirinya sendiri
}

func UpdateAddress(mu *sync.Mutex) {
    mu.Lock()
    defer mu.Unlock()
    // Operasi update
}
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Closure Data Race pada For-Loop Variable Capture
Sebelum Go 1.22, variabel loop iterasi dialokasikan pada alamat memori yang sama di setiap iterasi.

```go
// SALAH (Go < 1.22): Seluruh goroutine mengeksekusi referensi memori variabel 'v' yang sama
for _, v := range dataList {
    go func() {
        fmt.Println(v) // Nilai tercetak acak atau elemen terakhir berulang
    }()
}

// BENAR: Mengoper loop value secara eksplisit via stack argument
for _, v := range dataList {
    go func(val string) {
        fmt.Println(val)
    }(v)
}
```
*(Catatan: Go 1.22+ mengubah semantik per-iteration loop scoping, namun passing parameter tetap merupakan praktik defensif yang dianjurkan).*

### Kesalahan Fatal 2: Copying Mutex by Value
Menyalin struct yang memuat `sync.Mutex` menduplikasi status internal mutex. Saat salinan di-lock, mutex asli tetap unlocked, merusak isolasi konkurensi.

```go
// SALAH: Struct dioper secara value (pass-by-value menduplikasi Mutex)
type Counter struct {
    mu sync.Mutex
    val int
}

func BadIncrement(c Counter) { // Meminjam salinan c
    c.mu.Lock()
    c.val++
    c.mu.Unlock()
}

// BENAR: Menggunakan Pointer Receiver
func SafeIncrement(c *Counter) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.val++
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Jalankan Strict Static Linter:** Jalankan `go vet` dan pasang analyzer `go.uber.org/nilaway` serta `golang.org/x/tools/go/analysis/passes/copylock` pada pipeline CI/CD untuk mencegah penyalinan primitif lock.
2. **Desain Lifecycle Goroutine Secara Deterministik:** Jangan mengeksekusi `go func()` tanpa mengetahui persis:
   * Apa yang menyebabkannya berhenti?
   * Berapa lama waktu maksimal hidupnya?
   * Apakah alur terminasinya dikoordinasikan oleh `context.Context`?
3. **Lebih Memilih Channel Directional Typing:** Konfigurasikan signature fungsi menggunakan status kepemilikan directional (`chan<- T` send-only atau `<-chan T` receive-only) guna memvalidasi batasan arsitektur pada level kompilasi.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Mereduksi Memory Cache Contention (False Sharing)
Pada arsitektur multicore modern, CPU membaca memori ke dalam baris cache (*cache line*, umumnya 64 byte). Jika dua variabel atomik diakses oleh dua goroutine pada core berbeda namun terletak dalam satu baris cache line yang sama, performa drop drastis akibat *cache invalidation bouncing*.

```go
// Cache Line Padding Optimization
import "golang.org/x/sys/cpu"

type HighlyContendedStats struct {
    // Menyelipkan padding 64-byte agar CPU core tidak berebut baris cache yang sama
    Reads           uint64
    _               cpu.CacheLinePad
    Writes          uint64
    _               cpu.CacheLinePad
}
```

### 2. Tuning Scheduler Runtime
* **`GOMAXPROCS`:** Mengontrol jumlah $P$. Untuk workload CPU-bound murni, atur senilai core hardware fisik. Pada lingkungan containerized (Kubernetes), gunakan library `go.uber.org/automaxprocs` agar runtime Go membaca CFS quota CPU sebenarnya alih-alih seluruh core hardware node fisik VM host.
* **`GODEBUG=schedtrace=1000`:** Menghasilkan dump telemetri status jumlah $G$, $M$, $P$, LRQ, dan GRQ setiap 1.000 milidetik langsung ke `os.Stderr`.

---

## SEKSI 16 — KEAMANAN & HARDENING

Eksploitasi konkurensi dapat menyebabkan kerentanan sistem:

1. **Time-of-Check to Time-of-Use (TOCTOU):**
   * *Bahaya:* Memeriksa saldo (`if balance >= amount`) lalu mendebit saldo pada operasi non-atomik terpisah dapat dieksploitasi melalui *double-spending attack* via concurrent HTTP request.
   * *Solusi:* Seluruh blok pengecekan dan mutasi wajib dibungkus dalam single mutual exclusion lock atau dieksekusi secara terisolasi via serial processing goroutine.
2. **Goroutine Exhaustion (Denial of Service):**
   * *Bahaya:* Membuka Goroutine tanpa batasan batas throughput pada endpoint publik dapat membuat attacker menghabiskan memori virtual OS hingga service lumpuh total.
   * *Solusi:* Selalu gunakan fixed worker pool atau bounded token-bucket semaphore pattern.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Deteksi Race Condition
Jalankan test suite menggunakan runtime race detector berbasis instrumen ThreadSanitizer:
```bash
go test -race -v -count=1 ./...
go run -race main.go
```
*Catatan:* Race detector menambah overhead alokasi CPU 2x-10x dan memory 5x-20x. Hindari menyalakan flag `-race` pada seluruh instance binary production skala penuh (gunakan persentase canary instance terbatas).

### 2. Profiling Menggunakan Execution Tracer
Hasilkan trace runtime detail:
```go
import "runtime/trace"

func main() {
    f, _ := os.Create("trace.out")
    defer f.Close()
    trace.Start(f)
    defer trace.Stop()

    // Logika konkurensi Anda berjalan di sini...
}
```
Visualisasikan trace di browser:
```bash
go tool trace trace.out
```
Antarmuka web trace menampilkan:
* Garis waktu pergerakan Goroutine antar Thread ($M$) dan Core ($P$).
* Waktu mutlak pemblokiran Syscall vs Network Wait.
* Waktu eksekusi mutlak Garbage Collection Stop-The-World (STW).

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+---------------------------------------------------------------------------------------------------+
| GO CONCURRENCY CHEAT SHEET                                                                        |
+-------------------+-----------------------------+-------------------------------------------------+
| Operasi Channel   | Channel Terbuka (Open)      | Channel Tertutup (Closed)                       |
+-------------------+-----------------------------+-------------------------------------------------+
| Read (<-ch)       | Nilai/Block jika kosong     | Sisa elemen, lalu nilai default (zero-value, ok)|
| Write (ch <-)     | Berhasil/Block jika penuh   | PANIC: send on closed channel                   |
| Close (close(ch)) | Berhasil                    | PANIC: close of closed channel                  |
| Read/Write (nil)  | BLOCK PERMANEN (Hangs)      | BLOCK PERMANEN (Hangs)                          |
+-------------------+-----------------------------+-------------------------------------------------+

FORMULA WORK-STEALING RUNTIME:
1. Periksa GRQ jika schedtick % 61 == 0.
2. Ambil dari runnext, lalu runq lokal (LRQ).
3. Polling Network Poller non-blocking.
4. Curi (Steal) 1/2 antrean LRQ milik P lain secara acak.
5. Ambil antrean GRQ dengan lock.
6. Polling Network Poller secara blocking.
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Uji penguasaan konsep Anda terhadap materi yang telah dipelajari:

### Soal Tingkat Basic (1-5)

1. Apa perbedaan mendasar antara alokasi stack Goroutine dengan OS Kernel Thread?
2. Berapakah ukuran default memori stack awal untuk sebuah goroutine baru di Go modern, dan bagaimana perilakunya saat kapasitasnya terlampaui?
3. Apa fungsi utama pemanggilan `runtime.NumCPU()` dikaitkan dengan variabel environment `GOMAXPROCS`?
4. Apa yang terjadi secara mekanis ketika goroutine membaca channel yang berstatus `nil`?
5. Mengapa menutup channel dari sisi receiver (konsumen) dianggap sebagai anti-pattern berbahaya dalam arsitektur Go?

### Soal Tingkat Intermediate (6-10)

6. Bagaimana mekanisme sinyal `SIGURG` pada Go 1.14+ mengatasi problem infinite tight-loop (`for {}`) yang sebelumnya melumpuhkan penjadwal cooperative?
7. Terangkan peran krusial goroutine spesial `g0` pada setiap OS thread ($M$) yang dikelola oleh Go runtime!
8. Pada algoritma work-stealing, mengapa scheduler memprioritaskan pemeriksaan Global Run Queue (GRQ) setiap 61 siklus (*ticks*)?
9. Apa perbedaan komputasi tingkat rendah antara penguncian menggunakan `sync.Mutex` dengan operasi atomik pada package `sync/atomic`?
10. Diberikan skenario di mana ratusan goroutine membaca variable konfigurasi global setiap 10ms dan satu goroutine memperbaruinya setiap 5 menit. Mengapa `sync.RWMutex` lebih diunggulkan dibanding `sync.Mutex`, dan apa potensi risiko tersembunyinya jika write-load mendadak melonjak?

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: Resilient Distributed-Priority Task Dispatcher

Bangunlah sebuah library command-line berbasis Go murni tanpa library pihak ketiga eksternal yang mengimplementasikan sistem penjadwalan prioritas internal dengan spesifikasi teknis berikut:

#### Persyaratan Fungsional:
1. **Multi-tier Priority Queue:** Dispatcher harus mengelola 3 tingkatan prioritas antrean data: `Critical`, `Standard`, dan `Low`.
2. **Worker Pool Dinamis:** Mengalokasikan worker pool sejumlah $P$ (`runtime.GOMAXPROCS(0)`).
3. **Starvation Prevention Mechanism:** Buat mekanisme scheduler mandiri di mana antrean `Low` dipastikan dieksekusi minimal 1 kali setiap ada 5 eksekusi tugas antrean `Critical` atau `Standard` berturut-turut.
4. **Adaptive Preemption Context:** Setiap task dibekali batas `context.WithTimeout`. Jika task macet melebihi SLA eksekusi lokal (misal: 100ms), worker harus membatalkan task tersebut dan beralih ke tugas lain tanpa terjadi goroutine leak.
5. **Observability Endpoint:** Implementasikan fungsi statistik thread-safe yang mengembalikan total task sukses, total task timeout, dan average throughput per detik via operasi atomik (`sync/atomic`).
6. **Verifikasi Kualitas:** Wajib lulus pengetesan `-race` tanpa ada peringatan race condition dan buktikan ketiadaan memory leak dengan integrasi execution tracer.

---

### Kunci Jawaban Kuis Evaluasi (Gunakan untuk Self-Assessment)

1. *Stack Goroutine dialokasikan di user-space secara dinamis (tumbuh/susut) berukuran awal ~2KB, sedangkan OS thread dialokasikan secara fixed berukuran besar (1-8MB) pada kernel space.*
2. *2 KB. Jika penuh, runtime mengalokasikan stack baru 2x lebih besar, menyalin memori stack lama, memperbarui pointer, lalu membebaskan stack lama (Contiguous Stack).*
3. *`runtime.NumCPU()` mengidentifikasi core logika fisik hardware, sedangkan `GOMAXPROCS` menentukan kuota entitas logical processor ($P$) yang dapat mengeksekusi instruksi user Go code secara paralel.*
4. *Goroutine akan diblokir selamanya (*perpetual sleep*), memicu potensi goroutine leak.*
5. *Karena jika terdapat lebih dari satu sender yang mencoba mengirim ke channel tersebut pasca-close, sender akan crash seketika akibat panic `send on closed channel`.*
6. *Runtime thread `sysmon` mendeteksi tugas berjalan >10ms lalu mengirim sinyal OS `SIGURG`. Signal handler OS menginterupsi eksekusi register $M$ dan mengalihkan program counter ke fungsi penjadwal `runtime.asyncPreempt`.*
7. *`g0` memiliki stack OS berukuran penuh dan bertugas mengeksekusi tugas administratif runtime internal (scheduler, alokasi heap baru, GC) terpisah dari stack goroutine aplikasi biasa.*
8. *Untuk mencegah starvasi (*GRQ starvation*). Tanpa interval berkala ini, antrean lokal (LRQ) dan work-stealing antar $P$ dapat memonopoli komputasi sehingga goroutine pada GRQ tidak pernah dieksekusi.*
9. *`sync.Mutex` melibatkan runtime sleep/wake scheduling overhead dan semafor kernel, sedangkan `sync/atomic` menggunakan instruksi CPU tingkat rendah langsung (seperti `CMPXCHG`, `LOCK XADD`) tanpa context-switch overhead.*
10. *`sync.RWMutex` mengizinkan konkurensi pembacaan simultan tak terbatas tanpa saling memblokir. Namun, jika write-load melonjak, throughput drop akibat writer lock contention yang memblokir seluruh reader dan writer lain secara eksklusif.*