# BAB 03: Concurrency Primitives & Goroutine Scheduler
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. **Menganalisis Internal Runtime Go**: Membedah mekanisme internal *Goroutine Scheduler* (model GMP), *work-stealing algorithm*, *network poller*, serta transisi *cooperative* menuju *asynchronous preemption* berbasis sinyal OS.
2. **Mengevaluasi Struktur Data Konkurensi**: Memahami layout memori internal channels (`hchan`, `waitq`, `sudog`) dan primitives sinkronisasi (`sync.Mutex`, `sync.RWMutex`, `sync.Pool`, `sync.Cond`).
3. **Mengeliminasi Memory Latency & Lock Contention**: Menerapkan strategi *lock-free programming* berbasis paket `sync/atomic`, memitigasi fenomena *false sharing* pada CPU cache lines, dan mengoptimalkan throughput sistem konkuren.
4. **Membangun Resilient Concurrency Patterns**: Merancang worker pools adaptif, rate limiters, backpressure pipelines, dan context cancellation tree yang terisolasi dari *goroutine leaks*.
5. **Melakukan Debugging & Diagnostics Tingkat Lanjut**: Menggunakan `go tool trace`, `pprof` (goroutine, block, mutex), serta race detector untuk mengidentifikasi degradasi performa di lingkungan produksi skala masif.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib memiliki pemahaman mendalam tentang:
* Konsep threading OS (Kernel Space vs User Space threads, Context Switching overhead, TLB flushing).
* Memori arsitektur modern (Von Neumann, CPU Caches L1/L2/L3, Cache Coherence Protocols seperti MESI, Memory Barrier/Fences).
* Sintaks dasar goroutine, pointer, dan primitive channel di Go.
* Pemahaman fundamental mengenai I/O Multiplexing (`epoll` pada Linux, `kqueue` pada BSD/macOS).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Model GMP (Goroutine, Machine, Processor)
Go runtime tidak memetakan goroutine 1:1 ke thread sistem operasi (OS thread), melainkan menggunakan model penjadwalan $M:N$. Tiga entitas inti yang mengatur model ini adalah:

```
  +-------------------------------------------------------------+
  |                        Go Runtime                           |
  |                                                             |
  |   +-----------------------+     +-----------------------+   |
  |   | Global Run Queue(GRQ) |     | Global Run Queue(GRQ) |   |
  |   +-----------------------+     +-----------------------+   |
  |                                                             |
  |        [P0] (Processor)              [P1] (Processor)       |
  |    +----------------------+      +----------------------+   |
  |    | LRQ (Local Run Queue)|      | LRQ (Local Run Queue)|   |
  |    |  [G2] [G3] [G4] ...  |      |  [G5] [G6] [G7] ...  |   |
  |    | runnext: [G1]        |      | runnext: nil         |   |
  |    +----------------------+      +----------------------+   |
  |               |                             |               |
  |           binds to                      binds to            |
  |               v                             v               |
  |             [M0] (OS Thread)              [M1] (OS Thread)  |
  |               |                             |               |
  |           executes                      executes            |
  |               v                             v               |
  |             [G1]                          [G5]              |
  +-------------------------------------------------------------+
                  |                             |
                  v                             v
           +-------------+               +-------------+
           | CPU Core 0  |               | CPU Core 1  |
           +-------------+               +-------------+
```

1. **G (Goroutine)**:
   * Representasi konteks eksekusi user-space.
   * Struktur memori dialokasikan melalui struct `runtime.g`.
   * Dimulai dari stack sangat kecil (2 KB pada Go modern) yang dialokasikan pada heap secara dinamis via *contiguous stack allocation* (menggandakan stack ketika batas tercapai, memindahkan memori dan menyesuaikan pointer internal).
   * Menyimpan Program Counter (`PC`), Stack Pointer (`SP`), dan status (`_Gidle`, `_Grunnable`, `_Grunning`, `_Gsyscall`, `_Gwaiting`, dll.).
2. **M (Machine)**:
   * Representasi Kernel Thread OS (`runtime.m`).
   * Dibuat oleh runtime sesuai kebutuhan (dibatasi maksimum default 10.000 thread oleh runtime, namun yang aktif secara bersamaan ditentukan oleh nilai P).
   * M membutuhkan P untuk mengeksekusi kode Go. Namun, M dapat berjalan tanpa P jika sedang terblokir pada blocking syscall atau cgo call.
3. **P (Processor)**:
   * Abstraksi resource logika komputasi (`runtime.p`).
   * Jumlah P dibatasi oleh `GOMAXPROCS` (default: jumlah logical CPU cores).
   * Memiliki **Local Run Queue (LRQ)** berkapasitas 256 goroutine yang beroperasi lock-free bagi P pemiliknya, plus pointer `runnext` berelevansi tinggi yang diprioritaskan untuk afinitas cache L1/L2.

#### 3.2 Scheduler Lifecycle & Work-Stealing Algorithm
Saat sebuah thread $M$ mencari pekerjaan untuk dieksekusi, fungsi `runtime.findrunnable` menjalankan algoritma terstruktur:
1. **Periksa `runnext`**: Jika ada G pada slot `runnext` lokal di $P$, jalankan G tersebut.
2. **Periksa LRQ**: Ambil G dari LRQ lokal milik $P$.
3. **Periksa Global Run Queue (GRQ)**: Setiap 61 tick scheduler, P wajib memeriksa GRQ menggunakan lock global (`sched.lock`). Algoritma `tick % 61 == 0` ini mencegah *starvation* pada goroutine yang terisolasi di GRQ.
4. **Periksa Network Poller**: Jika ada abstraksi I/O siap baca/tulis yang telah selesai pada descriptor epoll/kqueue, ambil goroutine yang terbangun.
5. **Work-Stealing**: Jika LRQ lokal dan GRQ kosong, $P$ memilih target processor $P_{target}$ secara acak dari array P. $P$ akan mencoba "mencuri" (*steal*) setengah ($\lfloor N/2 \rfloor$) dari total isi LRQ $P_{target}$ untuk mengurangi lock contention antar processor.
6. **Syscall Handoff**: 
   * Saat Goroutine memanggil Blocking System Call (misal: read file blocking dari disk), runtime memanggil `runtime.entersyscall`.
   * Thread $M$ dilepaskan dari konteks $P$. Processor $P$ masuk ke status `_Psyscall`.
   * Thread monitor runtime (`sysmon`) mendeteksi $P$ yang terdisosiasi selama durasi tertentu (>10ms). Jika masih ada pekerjaan runnable di sistem, runtime akan memisahkan $P$ dari $M$ dan mengasosiasikannya ke thread lain ($M_{idle}$ atau spawn $M$ baru via `runtime.startm`).
   * Ketika syscall selesai (`runtime.exitsyscall`), $M$ mencoba mengakuisisi kembali $P$ aslinya. Jika gagal, ia mencoba mencari $P$ idle lain. Jika seluruh $P$ sibuk, goroutine dipindahkan ke Global Run Queue dan thread $M$ ditidurkan (*parked*).

#### 3.3 Asynchronous Preemption (Go 1.14+)
Sebelum Go 1.14, scheduler sepenuhnya kooperatif: goroutine hanya menyerahkan kendali (*yield*) pada saat alokasi stack (prologue fungsi `runtime.morestack`), channel operation, syscall, atau panggilan eksplisit `runtime.Gosched()`. Loop komputasi murni tanpa pemanggilan fungsi (misal: `for {}`) dapat memblokir satu core thread $M$ secara permanen (*tight loop starvation*).

Go 1.14 memperkenalkan **Non-Cooperative Signal-Based Preemption**:
* Thread background `sysmon` berjalan secara reguler tanpa memerlukan $P$.
* Jika sebuah goroutine terdeteksi berjalan kontinu lebih dari 10ms pada $P$ yang sama, `sysmon` mengirimkan sinyal OS POSIX `SIGURG` langsung ke OS Thread ($M$) yang bersangkutan.
* Kernel menghentikan thread dan melompat ke signal handler yang didaftarkan oleh Go runtime (`runtime.sighandler`).
* Signal handler memodifikasi register instruksi konteks thread untuk menyuntikkan pemanggilan ke `runtime.asyncPreempt`.
* Goroutine dihentikan secara aman pada titik instruksi mana pun yang berstatus *safe-point* GC, disimpan ke LRQ, dan $P$ menjadwalkan goroutine berikutnya.

#### 3.4 Anatomi Internal Channel (`hchan` dan `sudog`)
Channel bukan sekadar antrean buffer primitif, melainkan struktur data sinkronisasi terlindungi lock yang kompleks:

```go
// Representasi simplifikasi runtime/chan.go
type hchan struct {
    qcount   uint           // Total elemen di dalam buffer
    dataqsiz uint           // Kapasitas buffer sirkular
    buf      unsafe.Pointer // Pointer ke buffer ring buffer array
    elemsize uint16
    closed   uint32
    elemtype *_type         // Metadata tipe data elemen
    sendx    uint           // Indeks buffer untuk pengiriman berikutnya
    recvx    uint           // Indeks buffer untuk penerimaan berikutnya
    recvq    waitq          // Antrean goroutine yang menunggu untuk membaca (sudog list)
    sendq    waitq          // Antrean goroutine yang menunggu untuk menulis (sudog list)
    lock     mutex          // Spinlock internal melindungi seluruh operasi channel
}
```

* **Operasi Zero-Copy Optimization**: Jika sebuah goroutine $G_{reader}$ sudah menunggu pada `recvq` saat $G_{writer}$ mengeksekusi operasi send pada unbuffered channel, $G_{writer}$ tidak menyalin data ke memori internal channel buffer. Runtime akan **langsung menyalin data dari stack $G_{writer}$ ke stack frame milik $G_{reader}$** melalui low-level memory copy (`runtime.memmove`), melewati fase buffering sepenuhnya, dan menandai status $G_{reader}$ dari `_Gwaiting` menjadi `_Grunnable`.
* **Objek `sudog`**: Goroutine tidak dapat dimasukkan langsung ke dalam antrean tunggu channel (`waitq`). Goroutine dibungkus dalam abstraksi struct `sudog` untuk mengizinkan satu goroutine terdaftar pada beberapa wait queues secara simultan (misalnya saat mengeksekusi statement `select` multi-channel).

---

### 4. Why & What

| Dimensi | OS Thread (Kernel Space) | Goroutine (User Space Runtime) |
| :--- | :--- | :--- |
| **Ukuran Memori Alokasi** | Fixed, umumnya 2MB – 8MB per thread (termasuk guard page). | Dynamic contiguous stack. Dimulai dari 2KB, membesar/mengecil otomatis. |
| **Overhead Context Switch** | ~1000 - 1500 ns (Memerlukan kernel privilege transition, register saving, TLB invalidate). | ~100 - 200 ns (Instruksi user-space murni; hanya 14 register esensial disimpan). |
| **Mekanisme Scheduling** | Preemptive berbasis hardware timer interrupt oleh kernel scheduler. | Hybrid: Asynchronous Preemption (`SIGURG`) + Cooperative safe-points. |
| **Komunikasi & Sinkronisasi** | Pthreads primitives, Mutex OS, Semaphore, Unix Domain Sockets (Kernel heavy). | Channel internals via user-space spinlocks, direct-stack copying, Futex Go hybrid. |
| **Kapasitas Skalabilitas** | Ribuan thread per node sebelum mengalami Kernel Out of Memory (OOM) / Thashing. | Jutaan goroutine aktif secara simultan dalam satu single host instances. |

**Kapan Menggunakan Channel vs. Mutex?**
* **Channel**: Gunakan untuk *passing ownership data*, merancang distributed pipelines, mengoordinasikan transisi state antar komponen (*actor-like models*), atau mengimplementasikan stream event asinkron.
* **Mutex / Atomics**: Gunakan untuk perlindungan state memori internal (*in-memory state caches, counters, metrics*) dengan scope sempit dan performa tinggi di mana channel traversal memperkenalkan overhead allocation dan context switching yang tidak diinginkan.

---

### 5. How (Workflow Detail)

#### Alur Eksekusi Pengiriman Data ke Channel (`ch <- data`):

```
                     [Mulai Operasi ch <- data]
                                  |
                        [Channel == nil?]
                          /            \
                       (Ya)            (Tidak)
                        /                \
          [Park Goroutine Selamanya]     [Lock ch.lock]
          (Fatal Goroutine Leak)          |
                                         [Channel Tertutup (closed)?]
                                           /            \
                                        (Ya)            (Tidak)
                                         /                \
                                [Panic: send on]      [Ada G di recvq?]
                                [closed channel]       /            \
                                                    (Ya)            (Tidak)
                                                     /                \
                              [Salin data langsung]          [Buffer masih longgar?]
                              [ke stack penerima]              /                 \
                                     |                       (Ya)                (Tidak)
                              [Lepas ch.lock]                 /                     \
                                     |            [Tulis ke ch.buf[sendx]]   [Alokasi/Ambil sudog]
                           [Bangunkan penerima]   [Update ch.sendx++]        [Enq ke ch.sendq]
                                     |                    |                  [goparkunlock(&ch.lock)]
                                  [Selesai]         [Lepas ch.lock]                 |
                                                          |                  [G tertidur hingga]
                                                       [Selesai]             [dibangunkan receiver]
                                                                                    |
                                                                             [Lanjut Eksekusi]
```

1. **Evaluasi Nilai Channel**: Jika channel bernilai `nil`, runtime memanggil `runtime.gopark()`. Goroutine tertidur selamanya tanpa pernah dibangunkan (penyebab klasik memory leak).
2. **Locking**: Spinlock internal `ch.lock` diakuisisi untuk menjaga serializability akses buffer dan queue.
3. **Pengecekan Close Status**: Jika channel telah ditutup (`ch.closed != 0`), runtime segera melepas lock dan memicu runtime panic: `"send on closed channel"`.
4. **Pemeriksaan Receiver Queue (`recvq`)**: 
   * Jika pada `ch.recvq` terdapat entri `sudog` yang sedang tertahan, ambil `sudog` pertama dari antrean FIFO tersebut.
   * Panggil `runtime.sendDirect()` untuk menyalin byte data langsung dari variabel lokal stack sender ke alamat pointer memori stack receiver target.
   * Lepaskan lock internal.
   * Panggil `runtime.goready(recv_g)` untuk mengubah status goroutine penerima menjadi `_Grunnable` dan masukkan ke LRQ lokal $P$.
5. **Pemeriksaan Ruang Buffer**:
   * Jika kapasitas buffer belum penuh (`ch.qcount < ch.dataqsiz`):
   * Hitung offset memori menggunakan `ch.sendx`.
   * Salin data ke alamat `ch.buf` pada indeks tersebut.
   * Update `ch.sendx = (ch.sendx + 1) % ch.dataqsiz` dan `ch.qcount++`.
   * Lepaskan lock internal, instruksi pengiriman selesai.
6. **Blokade Pengirim (Enqueue & Park)**:
   * Jika buffer penuh atau tidak ada buffer (unbuffered channel), sender harus diblokir.
   * Runtime mengambil representasi `sudog` milik goroutine sender saat ini dari cache P (atau alokasi baru).
   * Nilai data yang akan dikirim diikatkan pada field `sudog.elem`.
   * Objek `sudog` di-append ke antrean linked-list `ch.sendq`.
   * Fungsi `runtime.gopark()` dieksekusi bersamaan dengan pelepasan spinlock `ch.lock`.
   * Status goroutine beralih ke `_Gwaiting`. Thread $M$ dilepaskan dari goroutine ini dan scheduler mengeksekusi goroutine runnable lain pada P.

---

### 6. Analogy & Diagram ASCII

#### Analogi Pabrik Manufaktur Modul Perangkat Keras
Bayangkan sebuah pabrik komponen mikroprosesor presisi tinggi:
* **G (Goroutine)**: Lembar Perintah Kerja (*Work Order*). Bobotnya ringan, hanya selembar kertas. Anda dapat mencetak 1.000.000 lembar kerja tanpa membebani fasilitas fisik.
* **P (Processor)**: Meja Kerja Logis terakreditasi (*Workstations*). Jumlah meja kerja dibatasi persis sesuai lisensi ruangan (`GOMAXPROCS`). Meja kerja memiliki nampan antrean lokal berisi 256 map instruksi kerja (*LRQ*).
* **M (Machine / Thread OS)**: Pekerja Manusia Fisik (*Laborer*).
  * Pekerja harus menempati Meja Kerja (P) agar dapat membaca Lembar Perintah Kerja (G).
  * Jika Lembar Perintah Kerja memerlukan pasokan suku cadang dari vendor eksternal yang lambat (*Blocking Disk/Syscall*), si pekerja ($M_1$) meninggalkan meja kerja ($P$) dan pergi ke gudang vendor.
  * Meja kerja ($P$) tidak boleh dibiarkan menganggur. Mandor pengawas (*sysmon*) akan segera memanggil pekerja cadangan ($M_2$) untuk mengambil alih meja kerja ($P$) dan mengeksekusi Lembar Perintah Kerja berikutnya.
  * **Work-Stealing**: Jika antrean meja kerja milik meja $P_1$ habis, pekerja di meja $P_1$ akan melongok ke meja $P_2$, lalu mengambil separuh map kerja dari nampan meja $P_2$ untuk dikerjakan di mejanya sendiri.

#### Arsitektur Channel Memory Layout

```
         +-----------------------------------------------------------+
         |                       struct hchan                        |
         +-----------------------------------------------------------+
         | qcount: 2  | dataqsiz: 4 | lock: [unlocked]               |
         | sendx:  2  | recvx:    0 | closed: 0                      |
         +-----------------------------------------------------------+
         | buf: unsafe.Pointer -----> [ Slot 0 ] [ Slot 1 ] [ ] [ ]  |
         +-----------------------------------------------------------+
         | recvq: [Head] -> nil                                      |
         | sendq: [Head] -> [sudog G101] <-> [sudog G102] -> nil     |
         +-----------------------------------------------------------+
```

---

### 7. Practical Implementation: High-Throughput Safe Concurrency Patterns

Berikut adalah implementasi skala industri untuk **Dynamic Resilient Worker Pool** yang mengimplementasikan bounded-memory backpressure, asynchronous execution, cancellation propagation, panic recovery, dan graceful draining.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

// Task merepresentasikan unit kerja komputasi independen.
type Task struct {
	ID      string
	Payload string
	Execute func(ctx context.Context) error
}

// Result mengemas status hasil eksekusi unit kerja.
type Result struct {
	TaskID   string
	Err      error
	Duration time.Duration
}

// PoolConfig mengonfigurasi batas operasional worker pool.
type PoolConfig struct {
	NumWorkers   int
	QueueSize    int
	SubmitTimeout time.Duration
}

// BoundedWorkerPool mengelola orkestrasi goroutine worker secara deterministik.
type BoundedWorkerPool struct {
	cfg       PoolConfig
	tasks     chan Task
	results   chan Result
	ctx       context.Context
	cancel    context.CancelFunc
	wg        sync.WaitGroup
	isClosed  atomic.Bool
	activeOps atomic.Int64
}

// NewBoundedWorkerPool menginisialisasi dan menyalakan worker pool.
func NewBoundedWorkerPool(parentCtx context.Context, cfg PoolConfig) (*BoundedWorkerPool, error) {
	if cfg.NumWorkers <= 0 || cfg.QueueSize <= 0 {
		return nil, errors.New("konfigurasi worker dan queue size harus bernilai positif > 0")
	}

	ctx, cancel := context.WithCancel(parentCtx)

	pool := &BoundedWorkerPool{
		cfg:     cfg,
		tasks:   make(chan Task, cfg.QueueSize),
		results: make(chan Result, cfg.QueueSize),
		ctx:     ctx,
		cancel:  cancel,
	}

	pool.start()
	return pool, nil
}

// start meluncurkan M worker goroutine yang diatur secara deterministik.
func (p *BoundedWorkerPool) start() {
	for i := 0; i < p.cfg.NumWorkers; i++ {
		p.wg.Add(1)
		go p.worker(i)
	}
}

// worker adalah loop inti pemrosesan setiap goroutine.
func (p *BoundedWorkerPool) worker(workerID int) {
	defer p.wg.Done()

	for {
		select {
		case <-p.ctx.Done():
			// Context dibatalkan secara eksternal; kuras task sisa jika diperlukan atau hentikan segera.
			return
		case task, ok := <-p.tasks:
			if !ok {
				// Queue channel telah ditutup secara gracefully via p.Stop()
				return
			}
			p.processTask(workerID, task)
		}
	}
}

// processTask mengeksekusi fungsi payload task dengan perlindungan panic recovery.
func (p *BoundedWorkerPool) processTask(workerID int, task Task) {
	startTime := time.Now()
	var taskErr error

	p.activeOps.Add(1)
	defer p.activeOps.Add(-1)

	// Isolasi kegagalan runtime (segfault, nil dereference) agar worker goroutine tidak mati.
	defer func() {
		if r := recover(); r != nil {
			taskErr = fmt.Errorf("panic terdeteksi pada worker %d: %v", workerID, r)
			p.dispatchResult(task.ID, taskErr, time.Since(startTime))
		}
	}()

	// Eksekusi fungsi dengan bound context pool
	taskErr = task.Execute(p.ctx)
	p.dispatchResult(task.ID, taskErr, time.Since(startTime))
}

// dispatchResult menyalurkan hasil eksekusi ke output channel secara non-blocking terhadap cancel.
func (p *BoundedWorkerPool) dispatchResult(id string, err error, dur time.Duration) {
	select {
	case p.results <- Result{TaskID: id, Err: err, Duration: dur}:
	case <-p.ctx.Done():
		log.Printf("Gagal mendistribusikan result untuk task %s: context dibatalkan", id)
	}
}

// Submit mendaftarkan unit kerja baru ke antrean dengan backpressure timeout.
func (p *BoundedWorkerPool) Submit(task Task) error {
	if p.isClosed.Load() {
		return errors.New("tidak dapat mengirim task: pool telah ditutup")
	}

	timer := time.NewTimer(p.cfg.SubmitTimeout)
	defer timer.Stop()

	select {
	case p.tasks <- task:
		return nil
	case <-timer.C:
		return errors.New("backpressure: antrean penuh, submit time-out")
	case <-p.ctx.Done():
		return p.ctx.Err()
	}
}

// Results mengembalikan read-only channel hasil eksekusi worker.
func (p *BoundedWorkerPool) Results() <-chan Result {
	return p.results
}

// Stop menghentikan worker pool secara graceful: menguras antrean dan menunggu seluruh proses selesai.
func (p *BoundedWorkerPool) Stop() {
	if !p.isClosed.CompareAndSwap(false, true) {
		return // Hindari double closure
	}

	// 1. Hentikan penerimaan task baru dengan menutup channel tasks
	close(p.tasks)

	// 2. Tunggu seluruh worker menyelesaikan task yang ada di antrean buffer
	p.wg.Wait()

	// 3. Batalkan context internal
	p.cancel()

	// 4. Tutup channel results setelah semua writer worker terminated
	close(p.results)
}

func main() {
	// Global cancellation handler
	rootCtx, stopRoot := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stopRoot()

	cfg := PoolConfig{
		NumWorkers:    4,
		QueueSize:     16,
		SubmitTimeout: 100 * time.Millisecond,
	}

	pool, err := NewBoundedWorkerPool(rootCtx, cfg)
	if err != nil {
		log.Fatalf("Inisialisasi pool gagal: %v", err)
	}

	// Consumer Goroutine: Membaca hasil secara independen
	var consumerWg sync.WaitGroup
	consumerWg.Add(1)
	go func() {
		defer consumerWg.Done()
		for res := range pool.Results() {
			if res.Err != nil {
				log.Printf("[OUTPUT] Task ID: %s GAGAL (Durasi: %v): %v", res.TaskID, res.Duration, res.Err)
			} else {
				log.Printf("[OUTPUT] Task ID: %s SUKSES (Durasi: %v)", res.TaskID, res.Duration)
			}
		}
	}()

	// Producer Simulation
	go func() {
		for i := 1; i <= 20; i++ {
			taskID := fmt.Sprintf("TASK-%03d", i)
			payloadVal := fmt.Sprintf("DATA-%d", i)

			task := Task{
				ID:      taskID,
				Payload: payloadVal,
				Execute: func(ctx context.Context) error {
					// Mensimulasikan komputasi/IO
					select {
					case <-ctx.Done():
						return ctx.Err()
					case <-time.After(50 * time.Millisecond):
						if taskID == "TASK-005" {
							panic("simulasi panic yang tidak tertangani!")
						}
						if taskID == "TASK-013" {
							return errors.New("koneksi database time-out")
						}
						return nil
					}
				},
			}

			if err := pool.Submit(task); err != nil {
				log.Printf("[BACKPRESSURE] Menolak %s: %v", taskID, err)
			}
			time.Sleep(10 * time.Millisecond)
		}

		// Selesai memproduksi task, lakukan graceful stop
		log.Println("Producer selesai mengirim task, mematikan pool...")
		pool.Stop()
	}()

	// Menunggu seluruh pipeline selesai
	consumerWg.Wait()
	log.Println("Sistem worker pool berhenti dengan bersih dan aman.")
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus Arsitektur: High-Throughput Financial Ingestion Engine
* **Konteks**: Sistem Payment Gateway menerima rata-rata 250.000 transaksi/detik pada jam puncak via gRPC/HTTP2.
* **Masalah Awal**:
  1. Penggunaan unbounded goroutine (`go handleTransaction(tx)`) menghasilkan 3.000.000 goroutine aktif saat terjadi downstream latency spike pada payment clearing house.
  2. Latensi p99 melonjak dari 15ms menjadi 4.200ms akibat GC STW (*Stop The World*) scan phase menandai jutaan pointer stack, memicu crash OOM fatal pada Kubernetes Pods.
  3. Penggunaan unbuffered logging channel global memicu lock contention masif pada `ch.lock`, menyebabkan throughput drop hingga 80%.

```
[Kondisi Awal: Unbounded Spawn]
API Clients ---> [Ingress Pod] ---> go func() x 3,000,000 ---> (Downstream Degradation)
                                         |
                                         v
                         [GC Scanner overload & Crash OOM]

[Kondisi Solusi: Partitioned Ring-Buffer Pipeline]
API Clients ---> [Ingress Engine] 
                       |
                       +--> [Hash Partitioner] (TxID % NumWorkers)
                                     |
                +--------------------+--------------------+
                |                    |                    |
                v                    v                    v
          [Local Ring 0]       [Local Ring 1]       [Local Ring N]
                |                    |                    |
                v                    v                    v
          [Worker Goroutine]   [Worker Goroutine]   [Worker Goroutine]
          (Lock-Free/Pinned)   (Lock-Free/Pinned)   (Lock-Free/Pinned)
                |                    |                    |
                +--------------------+--------------------+
                                     |
                                     v
                  Downstream Client (Bulk Micro-Batch)
```

* **Solusi Rekayasa Sistem**:
  1. **Strict Goroutine Bounding via Partitioning**: Mengganti dynamic spawn dengan model worker statis berbasis partisi hash (`TransactionID % NumPartitions`). Hal ini mengeliminasi cross-thread mutex synchronization antar worker.
  2. **Zero-Allocation Data Transport (`sync.Pool`)**: Seluruh struct representasi transaksi didaur ulang via `sync.Pool`. Objek dibersihkan (*reset fields*) sebelum dikembalikan ke pool, menurunkan frekuensi garbage collector dari 45 siklus/menit menjadi 2 siklus/menit.
  3. **Striped Ring-Buffer Channels**: Daripada mengalirkan 250k event ke satu channel terpusat, alur dibagi ke 64 independent bounded channels (striped queues). Tiap channel diproses oleh dedicated processor worker tanpa berebut `hchan.lock`.
* **Dampak Metrik**:
  * P99 Latency tereduksi dari 4.200ms menjadi **12.4ms**.
  * Heap footprint stabil pada rentang **380 MB** (sebelumnya berfluktuasi liar dari 2 GB hingga 14 GB OOM).
  * Penggunaan CPU turun 42% karena pengurangan drastis context switching overhead pada OS threads.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Biaya / Konsekuensi | Skenario Pemilihan |
| :--- | :--- | :--- | :--- |
| **Channel Bounded (`make(chan T, N)`)** | Memberikan native backpressure, otomatis menghentikan produser yang agresif, isolasi memori kepemilikan. | Memory pre-allocated di awal, risiko deadlock tinggi jika ukuran antrean diestimasi salah atau pembaca berhenti. | Streaming pipelines, task scheduling, asynchronous job submission. |
| **`sync.Mutex` / `sync.RWMutex`** | Alokasi memori mendekati nol, latensi raw instruksi sangat cepat jika low contention, fleksibel untuk update state lokal. | Rawan deadlocks karena lock inversion, tidak memiliki mekanisme built-in signaling timeout/cancellation. | Melindungi struct lokal, in-memory caches, aggregators, data structures in-memory. |
| **Atomic Operations (`sync/atomic`)** | Lock-free, kecepatan tingkat hardware instruksi native CPU (`CMPXCHG`), tidak pernah memicu sleep/park scheduler. | Hanya mendukung tipe data primitif dan pointer manipulasi sederhana, rentan bugs *ABA Problem* jika merancang queue sendiri. | Hit counter, atomic status flags, lock-free pointers reload, dynamic configuration toggles. |
| **`sync.Pool`** | Mengurangi alokasi heap secara drastis, memotong beban cycle GC CPU secara signifikan. | Objek dapat dihapus sewaktu-waktu oleh GC tanpa pemberitahuan. Rawan *data contamination* jika lupa melakukan sanitasi struct. | Buffer IO serialization (`bytes.Buffer`), decoding decoder context, parsing payload berulang. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Goroutine Leak Akibat Unbuffered Channel Tanpa Receiver
* **Kesalahan**: Menjalankan goroutine produser yang mengabaikan error/cancellation context consumer.
  ```go
  // ANTI-PATTERN: Fatal Goroutine Leak
  func queryFirstSuccess(ctx context.Context, urls []string) string {
      ch := make(chan string) // Unbuffered!
      for _, url := range urls {
          go func(u string) {
              res := fetch(u)
              ch <- res // BLOCKED SELAMANYA jika fungsi return lebih dulu!
          }(url)
      }
      return <-ch // Hanya membaca elemen pertama, goroutine sisanya leak!
  }
  ```
* **Remediasi**: Gunakan buffered channel berukuran cukup untuk menampung seluruh respons, atau gunakan `select` dengan `ctx.Done()`.
  ```go
  // PRODUCTION-READY FIX
  func queryFirstSuccess(ctx context.Context, urls []string) string {
      ch := make(chan string, len(urls)) // Buffer aman menampung seluruh hasil
      for _, url := range urls {
          go func(u string) {
              res := fetch(u)
              ch <- res // Tidak akan pernah terblokir meskipun main function selesai
          }(url)
      }
      return <-ch
  }
  ```

#### 10.2 Copying Synchronization Primitives by Value
* **Kesalahan**: Mem-passing struct yang membungkus `sync.Mutex` atau `sync.WaitGroup` secara pass-by-value (copying).
  ```go
  type StatsCollector struct {
      mu sync.Mutex
      counter int
  }

  // BUG: Struct dicopy, menduplikasi mutex internal state!
  func update(s StatsCollector) {
      s.mu.Lock()
      s.counter++
      s.mu.Unlock()
  }
  ```
* **Remediasi**: Selalu gunakan pointer receiver (`*StatsCollector`). Gunakan `go vet` dalam pipeline CI/CD untuk menangkap pelanggaran `copylocks`.

#### 10.3 Timer Leaks via `time.After` dalam Select Loop
* **Kesalahan**: Memanggil `time.After` di dalam infinite loop `select`.
  ```go
  // ANTI-PATTERN: High Memory Leaks
  for {
      select {
      case data := <-ch:
          process(data)
      case <-time.After(5 * time.Minute): // Alokasi timer BARU setiap loop iterasi!
          cleanup()
      }
  }
  ```
  Objek `time.Timer` tidak akan digarbage-collect sampai 5 menit kedaluwarsa, meskipun branch channel lain terpilih berulang kali.
* **Remediasi**: Gunakan `time.NewTimer` reuse pattern dengan memanggil `Stop()` dan drain channel drain secara eksplisit.

#### 10.4 Diagnostik Runtime via Profiling
Gunakan perintah diagnostik resmi berikut saat meneliti insiden performa:
1. **Mendeteksi Goroutine Leaks**:
   ```bash
   go tool pprof http://localhost:6060/debug/pprof/goroutine
   ```
   Ketik `traces` untuk memeriksa stack trace titik goroutine terblokir.
2. **Mendeteksi Lock Contention**:
   Aktifkan profiling pada `main.go`:
   ```go
   runtime.SetBlockProfileRate(10000) // Deteksi block events > 10 microsecond
   runtime.SetMutexProfileFraction(5) // Sample 1/5 mutex contention events
   ```
   Analisis via pprof:
   ```bash
   go tool pprof http://localhost:6060/debug/pprof/mutex
   go tool pprof http://localhost:6060/debug/pprof/block
   ```
3. **Execution Tracer**:
   ```bash
   go test -trace=trace.out
   go tool trace trace.out
   ```
   Memvisualisasikan interaksi langsung thread OS, GMP scheduling, Syscall switch, dan GC latency spikes secara timeline web visual.

---

### 11. Best Practices (Production Checklist)

- [ ] **Defensive Stack Allocation**: Jangan pernah membuat goroutine di dalam loop tanpa batasan absolut (Gunakan bounded worker pool atau semaphore `golang.org/x/sync/semaphore`).
- [ ] **Static Analysis Enforcement**: Pasang `go vet`, `staticcheck`, dan linter `gocritic` pada pipeline CI/CD untuk memvalidasi `copylocks` dan channel semantics.
- [ ] **Race Detection Audit**: Jalankan unit test dan integration test menggunakan flag `-race` (`go test -race -v ./...`). Jangan tolerir data race sekecil apa pun di staging.
- [ ] **Context Propagation Guarantee**: Setiap goroutine yang bertindak sebagai worker turunan wajib mendengarkan `ctx.Done()` untuk memastikan parent shutdown membersihkan children trees secara instan.
- [ ] **Panic Isolation**: Setiap background goroutine liar yang di-spawn wajib menyertakan defer-recover internal agar crash pada satu event tidak membunuh seluruh proses aplikasi.
- [ ] **Channel Ownership Paradigm**: Hanya goroutine produser (pembuat/pengisi) yang memiliki wewenang memanggil `close(ch)`. Goroutine konsumen dilarang menutup channel untuk menghindari runtime panic `send on closed channel`.
- [ ] **Metrics Visibility**: Ekspor metrik performa: jumlah goroutine aktif (`runtime.NumGoroutine()`), GC pauses via `runtime/metrics`, serta queue occupancy ke Prometheus/OpenTelemetry.

---

### 12. Hands-on Practice

Implementasikan simulasi komprehensif ini untuk menguji arsitektur starvation, non-cooperative signal preemption, dan memory contention.

Simpan struktur file pada project directory:
```
hands-on/m02/
├── go.mod
├── main.go
└── scheduler_test.go
```

#### File: `hands-on/m02/go.mod`
```go
module hands-on/concurrency-deepdive

go 1.22
```

#### File: `hands-on/m02/main.go`
```go
package main

import (
	"context"
	"fmt"
	"runtime"
	"sync"
	"sync/atomic"
	"time"
)

// ShardedCounter memecah counter untuk mengurangi cache contention (False Sharing Mitigation).
type ShardedCounter struct {
	shards []paddedCounter
	mask   uint64
}

// paddedCounter menggunakan padding 56 bytes untuk menyamai ukuran Cache Line CPU (64 bytes).
type paddedCounter struct {
	value atomic.Uint64
	_pad  [56]byte // Cache line padding: 8 byte value + 56 byte pad = 64 bytes
}

func NewShardedCounter(numShards int) *ShardedCounter {
	// Pastikan numShards adalah perpangkatan 2 untuk bitwise mask fast lookup
	size := 1
	for size < numShards {
		size <<= 1
	}
	return &ShardedCounter{
		shards: make([]paddedCounter, size),
		mask:   uint64(size - 1),
	}
}

func (sc *ShardedCounter) Add(workerID uint64, val uint64) {
	idx := workerID & sc.mask
	sc.shards[idx].value.Add(val)
}

func (sc *ShardedCounter) Total() uint64 {
	var total uint64
	for i := range sc.shards {
		total += sc.shards[i].value.Load()
	}
	return total
}

func main() {
	fmt.Println("=== Hands-on M02: Concurrency & Cache Optimization ===")
	fmt.Printf("GOMAXPROCS: %d Logical Cores\n", runtime.GOMAXPROCS(0))

	const numWorkers = 8
	const iterations = 10_000_000

	// 1. Uji Kontensi False Sharing & Lock-Free Atomic Scaling
	sharded := NewShardedCounter(numWorkers)
	var wg sync.WaitGroup

	startTime := time.Now()
	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func(id uint64) {
			defer wg.Done()
			for j := 0; j < iterations; j++ {
				sharded.Add(id, 1)
			}
		}(uint64(i))
	}

	wg.Wait()
	elapsed := time.Since(startTime)
	fmt.Printf("Hasil Sharded Counter: %d dihitung dalam %v\n", sharded.Total(), elapsed)

	// 2. Demonstrasi Asynchronous Preemption (Go 1.14+)
	fmt.Println("\nMenguji Preemption Scheduler terhadap Infinite Tight-Loop...")
	ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
	defer cancel()

	var tightLoopExecutionFinished atomic.Bool

	// Spawn tight CPU-bound computation loop tanpa alokasi memori atau syscall function calls
	go func() {
		fmt.Println("[TightLoop] Memulai spin-lock compute-bound...")
		var counter uint64
		for !tightLoopExecutionFinished.Load() {
			counter++ // Komputasi murni tanpa stack expansion prologue
		}
		fmt.Printf("[TightLoop] Berhasil terhenti secara kooperatif. Loop count: %d\n", counter)
	}()

	// Beri kesempatan scheduler mengeksekusi goroutine di atas
	time.Sleep(50 * time.Millisecond)

	// Goroutine monitor mengecek apakah runtime dapat menjadwalkan pekerjaan lain
	done := make(chan struct{})
	go func() {
		defer close(done)
		fmt.Println("[Monitor] Berhasil di-schedule oleh runtime berkat Preemption Signal SIGURG!")
	}()

	select {
	case <-done:
		fmt.Println("[Sukses] Runtime Scheduler membuktikan kapasitas Non-Cooperative Preemption.")
	case <-ctx.Done():
		fmt.Println("[Gagal] Starvation terdeteksi: Goroutine loop memblokir thread sepenuhnya.")
	}

	tightLoopExecutionFinished.Store(true)
	time.Sleep(50 * time.Millisecond)
	fmt.Println("Hands-on selesai dengan aman.")
}
```

#### Jalankan Praktikum:
```bash
cd hands-on/m02
go run main.go
```

---

### 13. Exercise

#### Level Easy: Safe In-Memory Dynamic TTL Map
* **Instruksi**: Buat struct `ThreadSafeTTLMap` yang mendukung operasi `Set(key string, val any, ttl time.Duration)`, `Get(key string) (any, bool)`, dan `Delete(key string)`. Gunakan `sync.RWMutex` untuk menjamin keamanan konkuren.
* **Syarat**: Wajib menyertakan background cleanup goroutine tunggal yang membersihkan item kedaluwarsa secara berkala tanpa menyebabkan starvation pembacaan dan memory leak.

#### Level Medium: Non-Leaking Token Bucket Rate Limiter
* **Instruksi**: Rancang Rate Limiter berbasis algoritma *Token Bucket* murni menggunakan goroutine, context, dan primitive channel.
* **Syarat**: 
  1. Method `Allow() bool` tidak boleh memblokir eksekusi caller (non-blocking).
  2. Method `Wait(ctx context.Context) error` harus menunggu sampai token tersedia atau context dibatalkan.
  3. Dilarang keras memicu *Timer Leaks* saat caller keluar dari `Wait()` akibat timeout konteks.

#### Level Hard: Lock-Free Single-Producer Single-Consumer (SPSC) Ring Buffer
* **Instruksi**: Buat implementasi data-structure Queue Circular Buffer kapasitas statis (perpangkatan 2) tanpa menggunakan `sync.Mutex` atau channel `hchan`.
* **Syarat**:
  1. Operasi `Push(val any) bool` dan `Pop() (any, bool)` hanya boleh menggunakan primitive pointer load/store dari `sync/atomic`.
  2. Implementasikan struktur padding CPU cache line (64 bytes) untuk memisahkan indeks Head dan Tail agar terbebas sepenuhnya dari fenomena *False Sharing*.

---

### 14. Challenge

#### Skenario: Resilient Multi-Tier Distributed-Style Circuit Breaker & Adaptive Bulkhead
Rancang sebuah library internal Go concurrency engine yang menangani pemanggilan eksternal microservice dengan spesifikasi kelas perbankan:
1. **Adaptive Concurrency Limit (Little's Law)**: Alih-alih menetapkan ukuran pool statis, engine harus menyesuaikan kapasitas konkurensi maksimum secara dinamis berdasarkan formula gradient:
   $$\text{Limit}_{baru} = \text{Limit}_{lama} \times \left( \frac{\text{Target Latency}}{\text{Observed P90 Latency}} \right)$$
2. **Panic Containment & Circuit Breaker**: Jika tingkat kegagalan (termasuk panic recovery downstream) melampaui 30% dalam jendela 5 detik (*sliding window*), engine beralih ke state `Open`, langsung menolak seluruh request (Fast-Fail) selama 3 detik sebelum memasuki state `Half-Open`.
3. **Strict Zero-Allocation Metrics Collection**: Sistem logging metrik harus menghitung moving latency dan error rate secara lock-free menggunakan atomic bit-shifting tanpa menyentuh heap garbage collector pada hot path.

*Tantangan ini tidak disediakan solusinya. Buktikan implementasi Anda bebas race-condition dengan `go test -race -count=100`.*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Berapakah ukuran awal stack sebuah Goroutine pada Go versi modern, dan bagaimana cara runtime menanganinya jika batas stack tersebut terlampaui?**
   * *Jawaban*: Ukuran awal adalah 2 KB. Ketika fungsi memerlukan ruang melebihi alokasi yang ada, compiler menyuntikkan prologue check yang memicu `runtime.morestack`. Runtime mengalokasikan contiguous memory block baru berukuran 2x lipat di heap, menyalin seluruh stack frame lama ke alamat baru, menyesuaikan internal pointer, dan membebaskan stack lama.
2. **Apa yang terjadi secara internal jika sebuah Goroutine mengeksekusi operasi pengiriman (`ch <- val`) ke sebuah channel yang bernilai `nil`?**
   * *Jawaban*: Goroutine tersebut akan masuk ke state `_Gwaiting` melalui pemanggilan fungsi internal `runtime.gopark()`. Karena tidak pernah ada referensi untuk membangunkannya kembali, Goroutine tersebut akan tertidur selamanya (*permanent leak*).
3. **Mengapa `sync.WaitGroup` atau `sync.Mutex` tidak boleh dioperasikan atau diteruskan sebagai argumen fungsi secara value (*pass-by-value*)?**
   * *Jawaban*: Kedua struct tersebut memiliki field internal (state counter/lock mask) yang bersifat privat. Mem-passing secara value akan menyalin salinan bitwise dari nilai saat ini. Modifikasi pada salinan tidak merefleksikan state asli, memecah sinkronisasi antar goroutine dan menimbulkan race condition atau deadlocks.
4. **Apa signifikansi algoritma $N \% 61 == 0$ saat Processor (P) mencari Goroutine yang siap dieksekusi?**
   * *Jawaban*: Setiap 61 iterasi scheduler loop, P diwajibkan memeriksa Global Run Queue (GRQ) menggunakan mutex global. Ini mencegah skenario *starvation* di mana goroutine di GRQ tidak pernah dieksekusi karena P terus-menerus disibukkan oleh pekerjaan di Local Run Queue (LRQ) lokalnya.
5. **Mengapa pembacaan variabel primitif `bool` di dalam infinite loop yang diakses oleh dua goroutine berbeda tetap membutuhkan primitive sinkronisasi atau atomic?**
   * *Jawaban*: CPU modern dan compiler Go menerapkan optimasi instruksi. Tanpa memory barrier (`atomic` atau `mutex`), nilai variabel dapat disimpan secara permanen di CPU core register/L1 cache tanpa pernah disinkronisasikan ke L3/Main Memory (pelanggaran *Sequential Consistency*), atau dioptimasi oleh compiler menjadi register load statis.

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Jelaskan perbedaan mendasar antara implementasi Channel unbuffered vs buffered dengan kapasitas $N=1$ ditinjau dari alur eksekusi $G_{sender}$!**
   * *Jawaban*: Pada unbuffered channel, $G_{sender}$ mutlak diblokir dan diparkir (`gopark`) kecuali sudah ada $G_{receiver}$ yang siap menunggu di `recvq` untuk melakukan direct stack memory copy. Pada buffered channel ($N=1$), selama buffer kosong, $G_{sender}$ langsung menulis byte ke array memori channel (`hchan.buf`), menggeser indeks ring buffer, dan langsung kembali melanjutkan instruksi tanpa memblokir thread atau menunggu kedatangan receiver.
7. **Bagaimana Go 1.14 menyelesaikan masalah goroutine starvation pada komputasi murni (*tight loop*) yang tidak memiliki alokasi memori atau pemanggilan fungsi?**
   * *Jawaban*: Melalui *Asynchronous Signal Preemption*. Background thread `sysmon` mendeteksi jika goroutine berjalan >10ms pada sebuah $P$. `sysmon` meluncurkan sinyal sistem operasi `SIGURG` ke thread $M$. Signal handler OS Go runtime menerima sinyal tersebut, menyimpan program context goroutine saat ini, mendaftarkan pemanggilan paksa ke `runtime.asyncPreempt`, dan mengembalikan goroutine ke antrean agar $P$ dapat menjadwalkan goroutine lain.
8. **Apa yang dimaksud dengan fenomena *False Sharing* pada arsitektur CPU cache dan bagaimana strategi mengatasinya di Go?**
   * *Jawaban*: False Sharing terjadi ketika dua variabel independen yang dimodifikasi oleh thread yang berjalan di core terpisah berada pada baris cache fisik yang sama (CPU Cache Line, tipikal 64 bytes). Modifikasi pada Core A memaksa Core B meng-invalidasi seluruh baris cache-nya via cache coherence protocol (misal: MESI), melambatkan performa write. Solusinya adalah menambahkan padding byte kosong (misal: `_pad [56]byte`) agar masing-masing variabel terisolasi pada cache line yang berbeda.
9. **Kapan Anda memilih menggunakan `sync.Cond` dibandingkan Channel biasa?**
   * *Jawaban*: `sync.Cond` ideal digunakan saat satu atau banyak goroutine harus menunggu (*wait*) suatu kondisi mutasi state kompleks yang dilindungi oleh Mutex, di mana ada kebutuhan untuk menyiarkan sinyal bangun secara broadcast (`Broadcast()`) ke puluhan atau ratusan goroutine yang tertidur sekaligus tanpa perlu membanjiri memory buffer allocation dari channel.
10. **Jelaskan mekanisme kerja `sync.Pool` dan mengapa struct ini tidak cocok digunakan sebagai database connection pool!**
    * *Jawaban*: `sync.Pool` mengelola sekumpulan objek sementara yang terikat secara thread-local ke masing-masing $P$. Ketika Garbage Collector berjalan, seluruh objek di dalam `sync.Pool` yang tidak dirujuk secara permanen akan dibersihkan tanpa peringatan. Hal ini kontradiktif dengan *Connection Pool* database yang membutuhkan stabilitas koneksi jaringan persisten, pembatasan ukuran koneksi minimum/maksimum yang deterministik, dan siklus hidup koneksi yang terkendali.

#### Bagian 3: Analisis Skenario Produksi (3 Pertanyaan)
11. **Skenario A**: Tim Anda mendapati sebuah API Gateway Go mengalami kenaikan tajam metrik memory heap usage secara gradual selama 48 jam hingga tewas terkena OOMKilled oleh Kubernetes. Hasil heap profile pprof tidak menunjukkan alokasi data besar yang mencurigakan. Di mana letak potensi akar masalah konkurennya?
    * *Analisis & Solusi*: Ini adalah indikasi klasik **Goroutine Leak**. Pprof heap profile hanya melacak memori yang dialokasikan oleh kode aktif; ia seringkali tidak memperhitungkan memory overhead dari jutaan Goroutine stack frame yang sedang berada pada status `_Gwaiting`. Akar masalahnya kemungkinan besar berasal dari channel pengiriman yang tidak pernah dibaca, pembacaan HTTP response body yang tidak ditutup (`resp.Body.Close()`), atau pemanggilan goroutine yang tertahan pada context tanpa timeout. Solusinya: Lakukan analisis `go tool pprof /debug/pprof/goroutine` dan periksa stack traces yang memiliki volume entri terbanyak untuk menemukan titik blocking.
12. **Skenario B**: Pada sistem perdagangan saham ultra-low latency, sebuah service yang memproses order book menggunakan `sync.RWMutex` terpusat. Ketika market crash terjadi dan volume pembacaan (`RLock`) serta penulisan order baru (`Lock`) melonjak 100x lipat, latensi penulisan order transaksi drop secara katastropik. Apa penyebab internal di level primitive runtime?
    * *Analisis & Solusi*: `sync.RWMutex` di Go bersifat *write-preferring*. Ketika ada satu Goroutine yang meminta `Lock()`, seluruh operasi `RLock()` yang datang berikutnya akan diblokir hingga writer selesai. Jika frekuensi permintaan `Lock()` dan pembacaan `RLock()` sama-sama ekstrem masif, terjadi kontensi dahsyat pada internal atomic mask lock mutex tersebut. Setiap lock switch memicu cache line invalidation badai di seluruh CPU core. Solusinya: Hilangkan lock terpusat dengan melakukan partisi data (misal: Sharding Order Book per Symbol Saham menggunakan individual worker goroutine / Actor Model pattern via ring buffer).
13. **Skenario C**: Seorang engineer mencoba mempercepat pipeline ETL dengan membuat 50.000 worker goroutine secara serentak yang masing-masing mengeksekusi blocking syscall IO membaca disk (`os.ReadFile`). Meskipun CPU core mesin berjumlah 64, aplikasi menjadi tidak responsif dan metrik OS melaporkan context switch kernel meningkat drastis hingga sistem hang. Apa yang terjadi pada scheduler Go?
    * *Analisis & Solusi*: Karena operasi I/O file pada disk lokal di Linux tidak terintegrasi dengan runtime network poller (`epoll` tidak mendukung regular disk files), Go runtime terpaksa mengorbankan thread sistem operasi ($M$). Saat 50.000 goroutine melakukan blocking disk syscall secara serentak, `sysmon` secara agresif melepaskan $P$ dan memicu *spawning* OS Kernel Thread ($M$) baru secara masif hingga menyentuh batas default (`10.000` OS threads). Kernel OS mengalami *thrashing* akibat biaya switching ribuan OS threads fisik. Solusinya: Batasi konkurensi operasi disk IO secara ketat menggunakan semaphore atau bounded worker pool kecil (misal: seimbang dengan 2x - 4x jumlah physical core).

---

### 16. Summary

1. **GMP adalah Jantung Eksekusi**: Go mengabstraksi eksekusi komputasi via model $M:N$. Pemisahan antara representasi komputasi logika ($P$) dan kernel thread fisik ($M$) memungkinkan runtime mengelola jutaan Goroutine ($G$) dengan alokasi stack dinamis hemat memori (2 KB) dan context switch user-space yang sangat murah.
2. **Channel Bukanlah Magic Primitives**: Channel adalah struct konkret (`hchan`) yang dilindungi oleh spinlock memori internal. Komunikasi via unbuffered channel memanfaatkan optimasi direct stack copying antar goroutine. Kelalaian dalam manajemen channel (nil channels, unbalanced sender/receiver) adalah sumber utama goroutine leaks dan deadlocks di produksi.
3. **Evolusi Penjadwalan Go**: Scheduling di Go telah bertransformasi dari sekadar kooperatif menjadi model hybrid canggih. Kehadiran Asynchronous Preemption berbasis POSIX signal (`SIGURG`) di Go 1.14 mengamankan sistem dari bahaya *tight CPU loops starvation*.
4. **Pragmatisme Ekosistem**: Gunakan primitive yang tepat sesuai beban kerja: Bounded Channels untuk pipeline backpressure dan state coordination, Atomics/Mutex untuk sinkronisasi state internal latensi rendah, serta hindari alokasi liar dengan mengendalikan siklus goroutine secara presisi menggunakan batas terukur (*bounded parallelism*).