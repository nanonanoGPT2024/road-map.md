# Kurikulum Rekayasa Perangkat Lunak Enterprise: Go (Golang)
## Kategori: 02-Programming-Languages
### BAB-04: Advanced Concurrency Patterns
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Principal Software Engineer / Staff Backend Engineer diharapkan mampu:
*   Menganalisis dan mengeksploitasi karakteristik runtime internal Go (GMP Scheduler, struktur data internal `hchan`, `sudog`, dan `mcache`) untuk meminimalkan *thread contention* dan *context-switching latency*.
*   Merancang dan mengimplementasikan arsitektur *concurrent pipeline* modular berkinerja tinggi yang mengintegrasikan mekanisme *bounded fan-out/fan-in*, *dynamic work-stealing*, *graceful teardown*, dan *bidirectional backpressure*.
*   Menerapkan sinkronisasi *low-latency* menggunakan primitif `sync/atomic` (CAS loop, atomic pointers) dan memitigasi anomali *hardware-level* seperti *false sharing* melalui optimasi *cache-line padding*.
*   Mendiagnosis kebocoran memori berbasis goroutine (*goroutine leaks*), *channel deadlocks*, serta *data races* secara deterministik menggunakan Go Execution Tracer, pprof, dan runtime instrumentation tingkat lanjut.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib menguasai:
*   **Go Fundamentals**: Memory model (heap vs. stack escape analysis), pointer semantics, slices/interfaces internals.
*   **Basic Concurrency**: Primitif `go`, `chan`, `sync.Mutex`, `sync.RWMutex`, `sync.WaitGroup`, dan `select`.
*   **Operating System Internals**: CPU cache hierarchy (L1/L2/L3), memory barriers/fences, thread scheduling (kernel-space vs. user-space context switching), virtual memory.
*   **Tooling**: Pemahaman dasar eksekusi `go test -race`, `go tool compile -m`, dan analisis heap via `go tool pprof`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 The GMP Scheduler Deep Dive
Go mengabstraksi thread sistem operasi (OS threads) melalui model penjadwalan **M:N** (M goroutine dipetakan ke N OS threads menggunakan P processor contexts).

```
 +-----------------------------------------------------------------------+
 |                         Go Runtime Execution                          |
 +-----------------------------------------------------------------------+
        [ Global Run Queue (GRQ) ] -> Lock contention via sched.lock
                     ^
                     | (1/61 tick check)
                     v
             +---------------+               +---------------+
             |  Processor P0 |               |  Processor P1 |
             +---------------+               +---------------+
             | LRQ (cap 256) |               | LRQ (cap 256) |
             | [G1][G2][G3]  |               | [G4][G5]      |
             +---------------+               +---------------+
                     |                               |
                     v                               v
             +---------------+               +---------------+
             |   Machine M0  |               |   Machine M1  |
             |  (OS Thread)  |               |  (OS Thread)  |
             +---------------+               +---------------+
                     |                               |
                     v                               v
             +-----------------------------------------------+
             |                  G (Current)                  |
             +-----------------------------------------------+
```

*   **G (Goroutine)**: Representasi thread level pengguna. Berisi execution stack (mulai dari 2 KB, tumbuh secara dinamis hingga batas arsitektur), program counter (`PC`), status eksekusi (`_Grunning`, `_Grunnable`, `_Gwaiting`, dll.), dan dependensi sinkronisasi.
*   **M (Machine)**: OS thread aktual yang dibuat via `clone()` syscall (Linux). M bertugas mengeksekusi instruksi mesin dari Goroutine.
*   **P (Processor)**: Resource logis yang dibutuhkan untuk mengeksekusi Go code. Nilai default dibatasi oleh `GOMAXPROCS`. Setiap P memiliki **Local Run Queue (LRQ)** berkapasitas 256 runnable Goroutines.
*   **Work-Stealing Algorithm**: Ketika P kehabisan G di LRQ-nya:
    1.  P memeriksa LRQ miliknya sendiri.
    2.  P memeriksa **Global Run Queue (GRQ)** secara periodik (setiap 61 ticks untuk mencegah kelaparan/starvation).
    3.  P memeriksa *network poller* (epoll/kqueue) untuk I/O yang telah *ready*.
    4.  P melakukan **Work Stealing**: Mengambil setengah (50%) isi LRQ dari P lain secara acak menggunakan operasi *lock-free atomic*.
*   **Syscall & Preemption (Non-cooperative)**:
    *   *Async Preemption* (sejak Go 1.14): Sinyal OS (`SIGURG`) diinjeksikan oleh sysmon thread ke M ketika G berjalan lebih dari 10ms tanpa titik preemption (seperti loop tanpa alokasi memori atau panggilan fungsi). Context G disimpan, dan P beralih ke G lain.

#### 3.2 Channel Internals (`hchan` & `sudog`)
Channel di Go bukan sekadar *ring buffer*; channel dialokasikan di heap melalui `runtime.makechan` dan didefinisikan dalam struct `hchan`:

```go
// Representasi konseptual runtime/chan.go
type hchan struct {
    qcount   uint           // Total elemen dalam ring buffer
    dataqsiz uint           // Kapasitas buffer (make(chan T, dataqsiz))
    buf      unsafe.Pointer // Pointer ke array data ring buffer
    elemsize uint16
    closed   uint32
    elemtype *_type         // Metadata tipe data
    sendx    uint           // Index write ring buffer
    recvx    uint           // Index read ring buffer
    recvq    waitq          // Doubly linked list sudog yang diblokir saat menunggu read
    sendq    waitq          // Doubly linked list sudog yang diblokir saat menunggu write
    lock     mutex          // Mengamankan semua operasi pada hchan (bukan lockless!)
}
```

*   **Pengiriman Data Langsung (Zero-Copy Optimization)**:
    *   Jika G1 mengirim ke channel unbuffered dan G2 sudah menunggu di `recvq`, runtime **tidak menulis ke buffer**. Runtime menyalin data langsung dari stack frame G1 ke stack frame G2 menggunakan fungsi internal `runtime.memmove`, lalu menandai G2 menjadi `_Grunnable`.
*   **Sudog**: Struktur alokasi yang membungkus G ketika G harus parkir (`gopark`) di `recvq` atau `sendq`. Satu Goroutine dapat berada di banyak wait queue jika berpartisipasi dalam multi-channel `select`.

#### 3.3 Memory Model, Memory Barriers & False Sharing
*   **Happens-Before Relationship**:
    *   *Send completion* pada unbuffered channel terjadi **sebelum** *receive completion* selesai.
    *   *Close* channel terjadi **sebelum** *receive* yang mengembalikan nilai zero/false selesai.
    *   Inisialisasi variabel di goroutine sebelum `go statement` dijalankan dijamin terlihat oleh goroutine baru tersebut.
*   **Cache Line Padding (False Sharing Mitigation)**:
    Sistem multiprosesor modern memuat memori ke dalam baris cache (umumnya 64 byte). Jika dua core CPU memodifikasi dua variabel independen yang berada pada 64 byte yang sama secara konkuren, terjadi invalidasi cache yang memaksa sinkronisasi bus hardware (berdampak buruk pada *latency*). Solusi: Menggunakan padding eksplisit `[56]byte` atau `cpu.CacheLinePad`.

---

### 4. Why & What

| Pendekatan / Pola | Karakteristik Desain | Kasus Penggunaan Ideal | Trade-off / Batasan |
| :--- | :--- | :--- | :--- |
| **Worker Pool Sederhana** | Pool statis goroutine membaca dari satu input channel. | Background asynchronous tasks, batch processing. | Rentan *head-of-line blocking*; tidak efisien untuk beban kerja fluktuatif ekstrem. |
| **Bounded Dynamic Worker Pool** | Goroutine dibuat dan dihancurkan sesuai *load burst*; batas kapasitas tegas. | HTTP request dispatching, RPC client pools, processing pipeline. | Overhead *lifecycle management* worker; alokasi memori dinamis. |
| **ErrGroup with Limits** | Eksekusi konkuren sub-tasks dengan pembatasan paralelisme dan *short-circuit cancellation*. | Fan-out aggregators, microservice scatter-gather calls. | Error pertama membatalkan seluruh operasi; kurang cocok untuk partial-tolerance. |
| **Pipeline with Backpressure** | Rangkaian tahapan (*stages*) terhubung via *bounded channels* dengan propagasi `context`. | Streaming analytics, data transformation, ingestion engines. | Perlu kalibrasi ukuran buffer secara presisi agar tidak memicu memory ballooning. |
| **Lock-Free Atomic State** | Menggunakan instruksi CPU `LOCK CMPXCHG` alih-alih mutual exclusion locks. | High-frequency metric counters, circuit breakers, cache state. | Sangat kompleks; terbatas pada operasi primitif atau pointer swapping. |

---

### 5. How (Workflow Detail)

Arsitektur data pipeline enterprise melibatkan propagasi sinyal terminasi, kontrol throughput, dan koordinasi sinkronisasi:

```
[Ingress Producer] 
       │ 
       ▼ (Context Done Detection)
[Bounded Input Queue: chan T (cap: N)]
       │
       ├────────────────────────┬────────────────────────┐
       ▼                        ▼                        ▼
[Worker Node 1]          [Worker Node 2]          [Worker Node N]  <-- Managed by ErrGroup/Semaphore
       │                        │                        │
       ├────────────────────────┴────────────────────────┘
       ▼ (Merge Results via Fan-In Multiplexer)
[Bounded Output Aggregator: chan Result]
       │
       ▼
[Egress Sink / Persister] ──► Ack / Metrics Emission
```

#### Siklus Hidup Eksekusi Pipeline:
1.  **Inisialisasi**: Root `context.WithCancel` atau `WithTimeout` dikonfigurasi.
2.  **Backpressure Enforcement**: Channel upstream diberikan limit *bounded capacity*. Jika downstream mengalami saturasi, buffer upstream terisi penuh, memblokir *send operation* producer secara alami tanpa memicu memory leak.
3.  **Cancellation Cascade**: Ketika upstream mendeteksi error fatal atau timeout, root context dibatalkan (`cancel()`). Seluruh worker yang memantau `ctx.Done()` segera menghentikan komputasi, mengosongkan parsial data, dan menutup egress channels.
4.  **Drain Phase**: Konsumen downstream menguras sisa elemen pada buffered channel untuk mencegah *producer goroutine deadlock*.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Dapur Restoran Bintang Lima
*   **M (Machine/OS Thread)**: Koki fisik di dapur.
*   **P (Processor/Context)**: Meja kerja kompor koki dengan perlengkapan lengkap. Jika kompor terbatas (misal 4), hanya 4 koki yang bisa memasak simultan.
*   **G (Goroutine)**: Tiket pesanan pelanggan. Tiket sangat ringan, bisa ada ribuan tiket dalam antrean.
*   **Syscall Block**: Koki harus keluar ke gudang pasar (Disk/Network IO). Ia melepaskan meja kompornya (P) agar koki lain dapat menggunakannya. Ketika kembali, koki mencari meja kosong mana pun.
*   **Work-Stealing**: Jika meja koki A kosong dari tiket, ia mengambil setengah tumpukan tiket dari meja koki B secara diam-diam tanpa mengganggu koki B.

#### Diagram: Perilaku Sudog dan Channel Deserialization

```
Goroutine G1 (Sender)                  Channel `hchan`               Goroutine G2 (Receiver)
+-------------------+             +-----------------------+           +-------------------+
| Executing:        |             | lock: Mutex (FREE)    |           | Waiting:          |
| ch <- payload     |             | qcount: 0             |           | data := <-ch      |
+-------------------+             | dataqsiz: 0           |           +-------------------+
        │                         | recvq: [sudog_G2] ───┼──────────►| Status: _Gwaiting |
        │                         +-----------------------+           | Stack address:    |
        │                                                             |   &data           |
        │                                                             +-------------------+
        │ 1. Acquire Lock                                                       ▲
        │ 2. Detect Waiting Receiver (sudog_G2 in recvq)                        │
        │ 3. Direct Memory Copy: Copy 'payload' direct to G2's stack address ───┘
        │ 4. Pop sudog_G2 from recvq
        │ 5. runtime.goready(G2) -> Change G2 status to _Grunnable
        │ 6. Release Lock
        ▼
   G1 Continues
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Pipeline Dasar dengan Context & Cancellation
Contoh ini mendemonstrasikan penghindaran kebocoran goroutine via `select` over `ctx.Done()`.

```go
package main

import (
	"context"
	"fmt"
	"time"
)

// generator memproduksi data integer secara kontinu hingga context dibatalkan.
func generator(ctx context.Context, limit int) <-chan int {
	out := make(chan int)
	go func() {
		defer close(out)
		for i := 1; i <= limit; i++ {
			select {
			case <-ctx.Done():
				return
			case out <- i:
			}
		}
	}()
	return out
}

// multiplyByTwo melakukan transformasi data.
func multiplyByTwo(ctx context.Context, in <-chan int) <-chan int {
	out := make(chan int)
	go func() {
		defer close(out)
		for n := range in {
			select {
			case <-ctx.Done():
				return
			case out <- n * 2:
			}
		}
	}()
	return out
}

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()

	pipeline := multiplyByTwo(ctx, generator(ctx, 100000))

	for result := range pipeline {
		fmt.Printf("%d ", result)
		if result >= 10 {
			break // Break lebih awal, trigger defer cancel() untuk membersihkan upstream goroutines.
		}
	}
	fmt.Println("\nPipeline gracefully stopped.")
}
```

#### 7.2 Practical Example: Enterprise-Grade Bounded Worker Pool dengan Graceful Degradation & Atomics
Implementasi berikut menggunakan pattern Worker-Pool terisolasi dengan rate/concurrency-limiting menggunakan *semaphore*, penghitungan metrik berbasis *atomic cache-line padded*, dan propagasi error menggunakan `golang.org/x/sync/errgroup`.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"sync/atomic"
	"time"

	"golang.org/x/sync/errgroup"
)

// MetricCollector menggunakan cache-line padding untuk mencegah False Sharing pada multicore systems.
type MetricCollector struct {
	processedJobs uint64
	_             [56]byte // Padding 56-byte untuk menggenapkan 64-byte L1 cache line (8 + 56)
	failedJobs    uint64
	_             [56]byte
}

func (m *MetricCollector) IncProcessed() {
	atomic.AddUint64(&m.processedJobs, 1)
}

func (m *MetricCollector) IncFailed() {
	atomic.AddUint64(&m.failedJobs, 1)
}

type Job struct {
	ID    int
	Data  string
	Retry int
}

type Result struct {
	JobID  int
	Output string
	Err    error
}

type Dispatcher struct {
	maxWorkers int
	jobQueue   chan Job
	metrics    MetricCollector
}

func NewDispatcher(maxWorkers int, queueCapacity int) *Dispatcher {
	return &Dispatcher{
		maxWorkers: maxWorkers,
		jobQueue:   make(chan Job, queueCapacity),
	}
}

func (d *Dispatcher) Submit(ctx context.Context, job Job) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	case d.jobQueue <- job:
		return nil
	default:
		// Backpressure applied: antrean penuh, tolak request secara deterministik
		d.metrics.IncFailed()
		return errors.New("backpressure triggered: worker pool queue full")
	}
}

func (d *Dispatcher) Start(ctx context.Context) error {
	g, groupCtx := errgroup.WithContext(ctx)

	// Bounded Worker Pool: Buat tepat N worker goroutines
	for w := 1; w <= d.maxWorkers; w++ {
		workerID := w
		g.Go(func() error {
			return d.worker(groupCtx, workerID)
		})
	}

	return g.Wait()
}

func (d *Dispatcher) worker(ctx context.Context, id int) error {
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case job, ok := <-d.jobQueue:
			if !ok {
				return nil // Job channel ditutup, terminasi normal
			}
			if err := d.executeJob(ctx, job); err != nil {
				d.metrics.IncFailed()
				// Logika fail-fast dapat mengembalikan error di sini jika fatal
			} else {
				d.metrics.IncProcessed()
			}
		}
	}
}

func (d *Dispatcher) executeJob(ctx context.Context, j Job) error {
	// Mensimulasikan komputasi I/O intensif yang mematuhi context cancellation
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-time.After(10 * time.Millisecond):
		return nil
	}
}

func (d *Dispatcher) Shutdown() {
	close(d.jobQueue)
}

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	dispatcher := NewDispatcher(4, 16)

	go func() {
		if err := dispatcher.Start(ctx); err != nil && !errors.Is(err, context.Canceled) {
			fmt.Printf("Dispatcher runtime error: %v\n", err)
		}
	}()

	// Simulasi submission data secara agresif
	for i := 1; i <= 30; i++ {
		err := dispatcher.Submit(ctx, Job{ID: i, Data: fmt.Sprintf("payload-%d", i)})
		if err != nil {
			fmt.Printf("Submit Rejected for Job %d: %v\n", i, err)
		}
	}

	<-ctx.Done()
	dispatcher.Shutdown()

	fmt.Printf("Shutdown complete. Processed: %d, Failed: %d\n",
		atomic.LoadUint64(&dispatcher.metrics.processedJobs),
		atomic.LoadUint64(&dispatcher.metrics.failedJobs),
	)
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Sistem Ingesti Mutasi Finansial Skala Tinggi (Core Ledger Ingestion Engine)
*   **Beban Operasi**: 150.000 events/detik transaksi streaming dari Kafka yang harus divalidasi ke 3 downstream microservices, dihitung state-nya, dan dicatat ke persistent storage (ScyllaDB).
*   **Masalah Arsitektural Awal**:
    *   Penggunaan satu goroutine per event (`go process(msg)`) mengakibatkan pembengkakan memori tak terkendali saat downstream mengalami network latency spikes (GC pause mencapai 4.2 detik, memori OOM mencapai 32GB karena 2+ juta goroutine tertahan).
    *   Data race terjadi pada cache lokal agregasi saldo akun karena sinkronisasi mutex global mengalami *lock contention* parah (>85% CPU core terperangkap di `runtime.futex`).

```
                    Kafka Partition Consumers
                               │
                               ▼
        ┌──────────────────────────────────────────────┐
        │  Consistent Hash Router (Account ID Routing)  │
        └──────────────────────────────────────────────┘
           │                   │                    │
    Hash(Acc1)%N        Hash(Acc2)%N         Hash(AccN)%N
           │                   │                    │
           ▼                   ▼                    ▼
    ┌─────────────┐     ┌─────────────┐      ┌─────────────┐
    │ Acc-Queue 1 │     │ Acc-Queue 2 │      │ Acc-Queue N │ (Bounded Ring Buffers)
    └─────────────┘     └─────────────┘      └─────────────┘
           │                   │                    │
           ▼                   ▼                    ▼
    ┌─────────────┐     ┌─────────────┐      ┌─────────────┐
    │ Dedicated   │     │ Dedicated   │      │ Dedicated   │ (Actor-like Single Worker)
    │ Worker 1    │     │ Worker 2    │      │ Worker N    │ No Mutex Needed!
    └─────────────┘     └─────────────┘      └─────────────┘
           │                   │                    │
           └───────────────────┼────────────────────┘
                               ▼
            [Batching Micro-Collector (sync/atomic)]
                               │
                               ▼
                 Batch Write to Persistent Storage
```

*   **Solusi Enterprise**:
    1.  **Actor-Model Partitioning via Consistent Hashing**: Menghapus penggunaan mutex sinkronisasi saldo akun. Event dirutekan berdasarkan `Hash(AccountID) % NumWorkers` ke channel antrean tetap (*ring buffer*). Setiap *worker* secara eksklusif memproses mutasi akun tertentu secara serial, menjamin determinisme transaksi tanpa lock (*zero-lock data structure*).
    2.  **Bounded Channel Backpressure**: Setiap worker memiliki bounded channel berkapasitas 4.096. Jika worker tertunda karena I/O DB, channel terisi penuh dan memblokir Kafka consumer commit offset, memindahkan backpressure secara natural ke cluster Kafka alih-alih meledakkan RAM internal Go.
    3.  **Batch Flusher dengan Ticker dan Context**: Menggabungkan mutasi per worker setiap 50ms atau 500 transaksi menggunakan dual-trigger `select` untuk melakukan bulk INSERT ke ScyllaDB.
*   **Hasil Metrik Produksi**:
    *   P99 Latency turun dari 820ms menjadi 18ms.
    *   Alokasi heap stabil di 450MB konstan di bawah beban 150k rps.
    *   Penggunaan CPU turun 62% karena hilangnya *lock contention* dan *GC overhead*.

---

### 9. Trade-offs

```
  High Concurrency Patterns Performance Spectrum:

  [ sync.Mutex ] ◄── Low Latency / Low Contention
       │
       ▼
  [ sync.RWMutex ] ◄── Read-Heavy Contention (90%+ Reads)
       │
       ▼
  [ Bounded Channels ] ◄── Complex Pipelines / Backpressure (Overhead: Mutex internal `hchan`)
       │
       ▼
  [ Sharded/Partitioned State ] ◄── High Contention Elimination (Overhead: Hashing / Memory Fragmentation)
       │
       ▼
  [ sync/atomic CAS Loops ] ◄── Ultimate High-Throughput (Overhead: Code Complexity / CPU Busy-Waiting)
```

| Primitif / Pola | Kelebihan | Kelemahan | Trade-off Analisis |
| :--- | :--- | :--- | :--- |
| **sync.Mutex** | Sederhana, aman untuk state sharing kompleks. | Skalabilitas buruk pada core tinggi jika contention tinggi. | Gunakan jika durasi critical section < 1µs dan tidak ada blocking I/O di dalamnya. |
| **Unbuffered Channel** | Jaminan sinkronisasi mutlak (*rendezvous*). | Throughput rendah; sender terblokir hingga receiver siap. | Gunakan hanya untuk koordinasi lifecycle (sinyal start/stop), hindari untuk data streaming berkecepatan tinggi. |
| **Buffered Channel** | Mengisolasi produsen dari variabilitas latensi konsumen pendek. | Alokasi memori heap tinggi; latensi meningkat jika buffer terisi penuh. | Harus selalu diukur kapasitasnya; buffer berukuran sembarangan hanya menunda kegagalan OOM. |
| **sync/atomic** | Lock-free, latensi sub-nanodetik, tidak ada thread-suspension overhead. | Hanya mendukung data type primitif/pointer swap; rawan bug logis (*ABA problem*, infinite CAS loop under heavy write). | Wajib untuk metrik counter dan flag status yang diakses ratusan ribu kali per detik. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Goroutine Leak Akibat Unbuffered Channel Abandonment
*   **Gejala**: Memori server naik secara linear (*staircase memory pattern*), pprof goroutine count terus bertambah tanpa pernah turun.
*   **Penyebab**: Sender goroutine mencoba mengirim data ke unbuffered channel, namun receiver selesai lebih dulu (misal keluar loop via `return` atau error). Sender macet selamanya di `hchan.sendq`.

```go
// ANTI-PATTERN: Goroutine Leak
func getFirstResponse(urls []string) string {
	ch := make(chan string) // unbuffered!
	for _, url := range urls {
		go func(u string) {
			ch <- fetch(u) // Goroutine kalah cepat akan terblokir selamanya di sini!
		}(url)
	}
	return <-ch // Mengambil pemenang pertama, meninggalkan sisa worker tergantung
}

// PRODUCTION FIX: Buffered Channel sesuai kapasitas kandidat
func getFirstResponseFixed(urls []string) string {
	ch := make(chan string, len(urls)) // Buffer menjamin sender tidak terblokir
	for _, url := range urls {
		go func(u string) {
			ch <- fetch(u)
		}(url)
	}
	return <-ch
}
```

#### 10.2 Variable Capture pada Concurrent Closure
*   **Gejala**: Seluruh goroutine mencetak nilai index yang sama atau data saling tertimpa secara acak.
*   **Deteksi**: `go vet ./...` atau `go test -race ./...`.
*   **Perbaikan**: Selalu teruskan variabel loop sebagai argumen parameter fungsi closure (terutama penting sebelum Go 1.22; tetap merupakan *clean-code standard*).

#### 10.3 Channel Closing Panic & Send on Closed Channel
*   **Penyebab**: Mencoba menutup channel dari sisi konsumen atau dari beberapa goroutine produsen konkuren.
*   **Aturan Dasar**: **Hanya produsen unik yang berhak menutup channel**. Jika produsen lebih dari satu, gunakan `sync.Once` untuk penutupan channel, atau gunakan cancellation channel terpisah (`quit chan struct{}`).

#### 10.4 Panduan Debugging dengan pprof dan Tracer
1.  **Cek Goroutine Leaks**:
    ```bash
    curl http://localhost:6060/debug/pprof/goroutine?debug=2 > goroutines.txt
    # Analisis teks untuk melihat stack trace Goroutine berstatus "chan send" atau "select"
    ```
2.  **Deteksi Race Conditions**:
    ```bash
    go test -race -v -run TestConcurrentOperation ./...
    ```
3.  **Trace Analysis untuk Scheduler Latency**:
    ```bash
    go test -trace=trace.out -bench=.
    go tool trace trace.out
    # Periksa view "Goroutine Analysis" untuk durasi GC blocking dan Network wait.
    ```

---

### 11. Best Practices (Production Checklist)

*   [ ] **Setiap pembuatan goroutine memiliki termination path**: Tidak ada pemanggilan `go func()` tanpa kepastian bagaimana dan kapan ia akan keluar.
*   [ ] **Gunakan context untuk pembatalan berantai**: Teruskan `ctx context.Context` sebagai argumen pertama ke semua fungsi asynchronous atau concurrent stages.
*   [ ] **Tentukan batas kapasitas channel (*Bounded Buffers*)**: Dilarang menggunakan channel unbuffered untuk beban batch/streaming intensif; hindari juga nilai buffer arbitrer tanpa kalkulasi konsumsi throughput.
*   [ ] **Drain Channel sebelum Discard**: Konsumsi channel yang tersisa saat proses terminasi untuk memastikan sender tidak menggantung di `sendq`.
*   [ ] **Gunakan `errgroup.WithContext`**: Gunakan lib ini alih-alih manual `sync.WaitGroup` jika ada potensi *error failure* di dalam sub-goroutine.
*   [ ] **Mitigasi False Sharing**: Terapkan memory padding pada struct counter global dengan `[56]byte` / `[64]byte`.
*   [ ] **Hindari Mutex dalam I/O Loop**: Jangan memanggil panggilan network (HTTP, DB query) atau pembacaan file sistem saat mengunci `sync.Mutex`.
*   [ ] **Konfigurasi `GOMAXPROCS` pada Lingkungan Container**: Gunakan library `go.uber.org/automaxprocs` di binary Kubernetes untuk mencegah ketidaksesuaian quota CPU CFS dan thread scheduling Go.

---

### 12. Hands-on Practice

Buat dan simpan struktur praktikum ini pada direktori: `hands-on/m02/`

#### File: `hands-on/m02/pipeline_test.go`
Langkah praktikum: Implementasikan multi-stage pipeline berkinerja tinggi yang memproses log string secara asinkron dengan fitur rate limiting dan graceful drain.

```go
package pipeline_test

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

type Event struct {
	ID        int
	RawData   string
	Validated bool
	Checksum  uint64
}

// Stage 1: Generator
func StreamGenerator(ctx context.Context, total int) <-chan Event {
	out := make(chan Event, 100)
	go func() {
		defer close(out)
		for i := 1; i <= total; i++ {
			select {
			case <-ctx.Done():
				return
			case out <- Event{ID: i, RawData: "raw-packet-content"}:
			}
		}
	}()
	return out
}

// Stage 2: Concurrent Validator (Fan-Out)
func ValidatorStage(ctx context.Context, workers int, in <-chan Event) <-chan Event {
	out := make(chan Event, 100)
	var wg sync.WaitGroup

	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				select {
				case <-ctx.Done():
					return
				case e, ok := <-in:
					if !ok {
						return
					}
					// Komputasi validasi simulatif
					e.Validated = true
					select {
					case <-ctx.Done():
						return
					case out <- e:
					}
				}
			}
		}()
	}

	go func() {
		wg.Wait()
		close(out)
	}()

	return out
}

// Stage 3: Consumer Sink
func ProcessSink(ctx context.Context, in <-chan Event, processedCount *uint64) {
	for {
		select {
		case <-ctx.Done():
			return
		case _, ok := <-in:
			if !ok {
				return
			}
			atomic.AddUint64(processedCount, 1)
		}
	}
}

func TestCompletePipelineExecution(t *testing.T) {
	totalEvents := 50000
	workers := 8
	var processed uint64

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	genStream := StreamGenerator(ctx, totalEvents)
	valStream := ValidatorStage(ctx, workers, genStream)

	ProcessSink(ctx, valStream, &processed)

	if processed != uint64(totalEvents) {
		t.Fatalf("Expected processed events %d, got %d", totalEvents, processed)
	}
}

func BenchmarkPipelineThroughput(b *testing.B) {
	for i := 0; i < b.N; i++ {
		ctx := context.Background()
		var processed uint64
		genStream := StreamGenerator(ctx, 1000)
		valStream := ValidatorStage(ctx, 4, genStream)
		ProcessSink(ctx, valStream, &processed)
	}
}
```

Jalankan pengujian menggunakan:
```bash
cd hands-on/m02/
go test -v -race -bench=. pipeline_test.go
```

---

### 13. Exercise

#### Tingkat Easy
1.  **Bounded Context Fan-In**: Buat fungsi `FanIn[T any](ctx context.Context, channels ...<-chan T) <-chan T` yang menggabungkan output dari variadic channel menjadi satu stream channel tunggal dengan penutupan yang aman saat seluruh producer selesai atau context dibatalkan.
2.  **Goroutine Safe Counter**: Buat modul counter yang mengekspos method `Inc()`, `Dec()`, dan `Value()` tanpa menggunakan `sync.Mutex` atau `sync.RWMutex`.

#### Tingkat Medium
1.  **Sliding Window Rate Limiter**: Rancang struktur data limitasi frekuensi request konkuren menggunakan channel dan ticker internal tanpa dependensi eksternal. Jika kapasitas window penuh, request baru harus langsung mengembalikan status *drop/rejected*.
2.  **Worker-Pool Dynamic Scaler**: Kembangkan worker pool yang secara otomatis menambah jumlah worker saat buffer queue mencapai kapasitas >80% dan memangkas jumlah worker kembali ke ukuran baseline saat utilisasi antrean <20% selama 30 detik.

#### Tingkat Hard
1.  **Lock-Free Bounded Ring Buffer Queue**: Implementasikan ring-buffer FIFO konkuren berkapasitas tetap (*bounded*) murni menggunakan instruksi `sync/atomic` (CAS), cache-line padding, dan memory barriers tanpa mengimpor package `sync` atau channel Go sama sekali. Queue harus tahan uji konkurensi multi-producer multi-consumer (MPMC).

---

### 14. Challenge (Tantangan Produksi Kompleks)

**Deskripsi Kasus**: 
Sebuah sistem penyedia payment gateway memproses request transaksi webhook dari ribuan merchant secara serentak. Anda diminta merancang package `batcher` modular dengan spesifikasi kritis:

1.  **Adaptive Auto-Flushing & Sizing**:
    *   Package harus menampung data transaksi ke dalam batch internal.
    *   Batch akan di-*flush* ke database relasional jika salah satu dari kondisi berikut tercapai: (a) Batch mencapai ukuran 1.000 item, (b) Interval timer 100ms tercapai, atau (c) Total ukuran memori buffer mendekati ambang batas tertentu.
2.  **Strict Ordering per Merchant**:
    *   Setiap merchant memiliki `MerchantID`. Transaksi dari `MerchantID` yang sama **wajib** diproses sesuai urutan waktu kedatangan (*strictly sequential*), namun transaksi antar merchant yang berbeda **harus** diproses secara paralel (*concurrent cross-merchants*).
3.  **Circuit Breaking & Dynamic Backpressure**:
    *   Jika sink database downstream melambat (latensi flush > 1 detik), antrean input ingestion harus memperlambat penerimaan request menggunakan non-blocking drop atau sinyal error backpressure instan ke HTTP handler agar tidak menyebabkan memory ballooning.
4.  **Zero Data Loss Graceful Teardown**:
    *   Saat sinyal `SIGTERM` diterima, ingress baru ditutup seketika, namun seluruh transaksi yang sudah terlanjur masuk antrean memori internal wajib di-flush tuntas ke database hingga selesai dengan alokasi grace-period maksimal 10 detik sebelum proses exit.

*Kriteria Keberhasilan*: Lulus pengujian beban dengan flag `-race` tanpa ada data race, zero panics, zero deadlock, dan zero data loss pada kondisi forced cancellation timeout.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1.  Apa yang membedakan goroutine dari kernel thread sistem operasi dalam hal footprint memori dan alokasi stack awal?
2.  Mengapa membaca dari channel yang telah ditutup (`closed`) tidak menghasilkan panic, sedangkan menulis ke channel yang telah ditutup selalu menghasilkan panic?
3.  Bagaimana runtime Go mendeteksi bahwa unbuffered channel siap melakukan operasi baca/tulis langsung secara *zero-copy*?
4.  Apa fungsi dari parameter `GOMAXPROCS` pada Go runtime?
5.  Apa representasi status goroutine `_Gwaiting` dalam arsitektur GMP Go?

#### Bagian 2: Intermediate (5 Pertanyaan)
6.  Jelaskan mekanisme kerja *work-stealing algorithm* pada scheduler Go ketika Local Run Queue (LRQ) dari sebuah processor P kosong!
7.  Bagaimana fenomena *False Sharing* terjadi pada sistem CPU multicore modern dan bagaimana cara mendesain struct di Go untuk mencegahnya?
8.  Mengapa implementasi channel internal (`hchan`) tetap menggunakan mutex lock biasa dan bukan implementasi full *lock-free*?
9.  Kapan non-cooperative asynchronous preemption diaktifkan oleh sysmon thread, dan sinyal OS apa yang diinjeksi ke OS thread pada Linux?
10. Apa risiko fatal memanggil `ctx.Done()` di luar blok `select` statement saat menangani pemrosesan channel?

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario A**: Dalam microservice scraping web, terdapat fungsi yang mengeksekusi 100 HTTP request menggunakan `for _, url := range urls { go fetch(url) }`. Setelah 24 jam berjalan, terjadi lonjakan penggunaan memori virtual hingga 40GB dan latency service melonjak. Ketika dianalisis via pprof, terdapat 450.000 Goroutine berstatus `select (DNS lookup)`. Apa akar masalahnya dan bagaimana desain arsitektur koreksinya?
12. **Skenario B**: Tim engineer Anda membuat cache in-memory berbasis `sync.RWMutex`. Profiling menunjukkan CPU utilization mencapai 95% pada sistem dengan 64 core, dengan porsi terbesar waktu dihabiskan pada runtime `sync.runtime_SemacquireMutex`. Padahal rasio pembacaan (*read*) adalah 99% dan penulisan (*write*) hanya 1%. Jelaskan mengapa `sync.RWMutex` mengalami *performance degradation* pada situasi tersebut dan tawarkan solusinya!
13. **Skenario C**: Anda memiliki worker pool pipeline yang membaca data transaksi perbankan. Pipeline mendadak deadlock total saat terjadi spike beban transaksi. Tidak ada log error, dan CPU drop hingga 0%. Profiling stack trace menunjukkan seluruh worker goroutine tertahan di `ch <- result`, sementara consumer akhir sedang tertahan di `wg.Wait()`. Analisis bagaimana siklus dependensi deadlock ini terbentuk dan tuliskan refactoring code untuk memutusnya!

---

### 16. Summary

*   Model konkurensi Go bertumpu pada **GMP Scheduler**, yang memfasilitasi abstraksi M goroutine di atas N thread kernel menggunakan P processor contexts melalui mekanisme *work-stealing* dan *non-cooperative preemption*.
*   Channel Go adalah struktur data berstatus (*stateful*) berbasis heap (`hchan`) yang dikontrol oleh mutex internal, ring buffer, dan antrean tunggu dua arah (`sudog`). Memahami siklus `hchan` krusial untuk mencegah deadlock dan degradasi throughput.
*   **Backpressure** dan **Graceful Lifecycle Management** adalah fondasi sistem concurrency enterprise. Mengizinkan produksi data tanpa batas (*unbounded goroutine creation*) merupakan anti-pattern fatal yang berujung pada kehabisan memori (OOM).
*   Optimasi konkurensi tingkat lanjut menuntut pertimbangan arsitektur perangkat keras: cache lines (menghindari *false sharing* via memory padding) dan pemanfaatan instruksi CPU tingkat rendah (*atomic CAS loops*) jika sinkronisasi mutex menjadi bottleneck throughput utama.
*   Pencegahan kebocoran goroutine wajib diterapkan secara konsisten melalui integrasi `context.Context` cancellation pada setiap cabang eksekusi konkuren.