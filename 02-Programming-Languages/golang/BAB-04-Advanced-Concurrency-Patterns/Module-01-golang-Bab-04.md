# Bab 04 Module 01: Advanced Concurrency Patterns

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran:** 02-Programming-Languages
*   **Mata Pelajaran:** Golang Core & Systems Engineering
*   **Bab:** 04 — Concurrency in Depth
*   **Modul:** 01 — Advanced Concurrency Patterns
*   **Tingkat Kesulitan:** Advanced / Senior Systems Engineer
*   **Prasyarat:** Pemahaman mendalam tentang syntax dasar Go, goroutine dasar, `sync.WaitGroup`, unbuffered/buffered channels, dan primitive locking (`sync.Mutex`, `sync.RWMutex`).
*   **Target Output:** Mampu merancang, menganalisis, mengimplementasikan, dan men-debug sistem konkuren berbasis CSP (*Communicating Sequential Processes*) dan *Structured Concurrency* yang bebas dari *goroutine leaks*, *race conditions*, serta *deadlocks* di lingkungan produksi bertaraf *high-throughput*.

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis & Mengevaluasi (Bloom's C4/C5):** Menilai kelemahan arsitektur konkurensi naïf dan mendeteksi potensi *goroutine leaks*, *unbounded growth*, serta *deadlock condition* secara presisi.
2.  **Merancang Pola Aliran Data Lanjutan (Bloom's C6):** Mengkonstruksi pola *Pipelines*, *Fan-Out/Fan-In*, *Dynamic Worker Pools*, dan *Bounded Context-Aware Stream Processing* secara terstruktur.
3.  **Mengimplementasikan Structured Concurrency (Bloom's C6):** Menerapkan paket `golang.org/x/sync/errgroup` dan context lifecycle propagation untuk memastikan pembatalan berantai (*cascading cancellation*) yang deterministik.
4.  **Mengoptimasi Resource Throughput (Bloom's C5):** Mengukur dan menyeimbangkan *backpressure*, ukuran buffer channel, dan alokasi memori runtime menggunakan profiling runtime (`trace`, `pprof`) serta metrik saturasi sistem.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Prinsip Inti: "Do not communicate by sharing memory; instead, share memory by communicating."

Model mental konkurensi di Go berakar pada formalisme CSP oleh C.A.R. Hoare. Paradigma tradisional berbasis *shared-memory multithreading* (seperti pada C++ POSIX Threads atau Java murni) memperlakukan konkurensi sebagai sekumpulan eksekutor yang memperebutkan akses ke area memori yang sama menggunakan *lock primitives*. Pola ini rapuh terhadap *deadlock*, *priority inversion*, dan *race conditions*.

```
   Shared Memory Model (Lock-based)            CSP Model (Channel-based)
   
        Thread A        Thread B                    Goroutine A     Goroutine B
           \              /                              \              ^
            \            /                                \            /
         [ Mutex Protected ]                               [ Channel ]
         [   Shared Data   ]                               (Ownership Transfer)
```

Sebaliknya, CSP Go memperlakukan data sebagai entitas bergerak yang kepemilikannya (*ownership*) ditransfer antar-rutin konkuren:

1.  **Pemisahan Tanggung Jawab (*Separation of Concerns*):** Satu goroutine memiliki eksklusivitas atas mutasi data pada satu titik waktu tertentu. Ketika data dikirim melalui channel, kepemilikan data dilepaskan oleh pengirim dan diambil alih oleh penerima.
2.  **Structured Concurrency:** Goroutine tidak boleh berjalan sebagai "fire-and-forget" tanpa pengawasan (*unowned lifetime*). Setiap goroutine harus memiliki:
    *   Pemilik (*creator/supervisor*).
    *   Batas waktu masa hidup (*lifetime boundary*).
    *   Mekanisme terminasi yang jelas via sinyal (*cancellation signal*).
3.  **Backpressure Awareness:** Mengirim data tanpa mempedulikan kapasitas konsumsi hilir (*downstream consumption capacity*) adalah akar dari degradasi performa sistem. Kapasitas channel dan konkurensi worker harus selalu dibatasi (*bounded*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram arsitektur untuk sistem pemrosesan terdistribusi lokal yang menggabungkan pola **Pipeline**, **Fan-Out (Penyebaran Beban)**, **Worker Pool**, dan **Fan-In (Agregasi)** dengan penanganan sinyal terminasi berbasis `context.Context`.

```
[ Ingestion Pipeline ] 
        |
        v
+---------------+
|  Data Source  |  (Generator Phase: membangkitkan stream event)
+---------------+
        |  out: <-chan Event
        v
+---------------+
| Stage 1: Prep |  (Sanitasi & Validasi Awal)
+---------------+
        |  out: <-chan Event
        +-----------------------------------------------+
        |                                               |
        | [ FAN-OUT ]                                   | [ Backpressure Boundary ]
        v                                               v
+------------------+                            +------------------+
|  Worker Node 01  |                            |  Worker Node 02  |  ... (N Workers)
|  - CPU Heavy     |                            |  - I/O Enrich    |
|  - Rate-limited  |                            |  - Rate-limited  |
+------------------+                            +------------------+
        |                                               |
        +-----------------------+-----------------------+
                                |
                                | [ FAN-IN ] (Multiplexing Stream)
                                v
                      +-------------------+
                      |   Aggregator /    |
                      |   Sink Collector  |
                      +-------------------+
                                |
                                v
                      +-------------------+
                      | Persistence/Queue |
                      +-------------------+
                                ^
                                | Context Cancel / Error Trigger
                      +-------------------+
                      |   Context Tree    | (Cascading Teardown)
                      +-------------------+
```

### Siklus Hidup Event & Sinyal Kontrol:
1.  **Context Tree:** Akar pembatalan (`Root Context`) mengalir ke setiap stage melalui `ctx.Done()`.
2.  **Pipeline Channels:** Jalur data bertipe kuat mentransfer entitas antar-tahap secara satu arah (`<-chan T` atau `chan<- T`).
3.  **Teardown Sequence:** Penutupan channel mengalir dari *upstream* ke *downstream* (kiri ke kanan / atas ke bawah), sedangkan sinyal pembatalan kesalahan (`error`) mengalir secara instan ke seluruh rantai melalui context.

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Go Runtime Scheduler (Model M:N)
Go runtime memetakan $M$ goroutines ke $N$ kernel threads (*OS threads*) menggunakan abstraksi $P$ (*Processor/Logical Context*):

```
       [ Global Run Queue (GRQ) ]
                   |
     +-------------+-------------+
     |                           |
   +---+                       +---+
   | P | (Logical Context)     | P |
   +---+                       +---+
   | M | (OS Thread)           | M |
   +---+                       +---+
     |                           |
  [ LRQ ] (Local Run Queue)   [ LRQ ]
   [G1, G2, G3]                [G4, G5]
```

*   **G (Goroutine):** Representasi stack (mulai dari 2 KB, dapat berkembang hingga 1 GB pada 64-bit), status eksekusi, dan *instruction pointer*.
*   **M (Machine):** Kernel thread OS yang sesungguhnya dialokasikan oleh kernel.
*   **P (Processor):** Sumber daya yang dibutuhkan untuk mengeksekusi kode Go; jumlahnya default setara dengan `runtime.GOMAXPROCS(0)`.
*   **Work-Stealing Algorithm:** Jika local run queue (LRQ) dari suatu $P$ kosong, $P$ tersebut akan mencoba mengambil setengah tugas dari LRQ milik $P$ lain. Jika LRQ lain kosong, ia memeriksa Global Run Queue (GRQ), lalu network poller.
*   **Syscall Preemption:** Saat goroutine menjalankan *blocking syscall*, runtime melepaskan thread $M$ dari konteks $P$, menciptakan thread $M$ baru untuk terus memproses tugas lain di antrean $P$.

### 2. Anatomi Internal Channel (`hchan` struct)
Channel di Go bukan sekadar memori bersama, melainkan pointer ke struktur `hchan` di dalam runtime (`src/runtime/chan.go`):

```go
type hchan struct {
    qcount   uint           // total data dalam antrean (queue)
    dataqsiz uint           // ukuran buffer sirkular
    buf      unsafe.Pointer // pointer ke array elemen circular buffer
    elemsize uint16
    closed   uint32
    elemtype *_type         // tipe elemen
    sendx    uint           // send index
    recvx    uint           // receive index
    recvq    waitq          // antrean goroutine yang menunggu pembacaan (sudog)
    sendq    waitq          // antrean goroutine yang menunggu penulisan (sudog)
    lock     mutex          // mutex internal penjaga integritas hchan
}
```

*   Channel diamankan secara internal menggunakan **spin-lock / futex internal (`hchan.lock`)**. Operasi send/receive memegang lock ini dalam durasi yang sangat singkat.
*   Jika goroutine mencoba membaca dari unbuffered/empty channel, goroutine tersebut dialokasikan dalam entitas `sudog`, ditambahkan ke daftar antrean `recvq`, lalu diparkir (*parked*) oleh scheduler via `gopark()`. Scheduler tidak memblokir OS thread, melainkan mengalihkan eksekusi ke goroutine lain.
*   Ketika goroutine pengirim tiba, ia mendeteksi keberadaan `sudog` di `recvq`, menyalin nilai secara langsung ke stack goroutine penerima (*direct memory copy*), lalu membangunkan goroutine tersebut via `goready()`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Bounded vs Unbounded Concurrency
*Unbounded concurrency* terjadi saat goroutine di-*spawn* secara dinamis tanpa batas (`go handle(req)`) untuk setiap unit tugas masuk. Di bawah beban *spike* (misal $100.000$ RPS), alokasi $100.000$ goroutine membutuhkan alokasi awal minimal $100.000 \times 2\text{ KB} = 200\text{ MB}$ hanya untuk stack, belum termasuk objek heap yang diakses. Hal ini dapat memicu saturasi GC (*Garbage Collection thrashing*), kehabisan *file descriptor*, atau OOM (*Out-of-Memory*).

*Bounded concurrency* memastikan sistem memiliki batas atas mutlak ($N$) jumlah operasi simultan. Ini dicapai dengan:
*   **Fixed Worker Pools:** Jumlah pekerja yang ditentukan di awal.
*   **Counting Semaphores:** Menggunakan buffer channel kosong (`chan struct{}`) untuk mengatur token kuota konkurensi.

### 2. Channel Ownership & Closure Rules
Aturan baku untuk mencegah *panic* ("send on closed channel" atau "close of closed channel"):
*   **Produser (pengirim) adalah pemilik tunggal:** Hanya goroutine yang bertindak sebagai produser eksklusif dari suatu channel yang berhak menutup channel tersebut (`close(ch)`).
*   **Konsumen dilarang menutup channel:** Konsumen hanya membaca hingga `val, ok := <-ch` mengembalikan `ok == false`.
*   **Multiple Producers:** Jika terdapat banyak produser, gunakan primitive koordinasi tingkat tinggi (misalnya `sync.WaitGroup` atau `sync.Once`) untuk mengamankan penutupan, atau serahkan kontrol penutupan kepada konteks pembatalan eksternal.

### 3. Backpressure & Bounded Buffers
Buffer channel bukan solusi untuk menyelesaikan masalah *throughput mismatch* jangka panjang. Buffer berfungsi sebagai penyerap fluktuasi transien (*micro-burst absorption*). Jika kecepatan rata-rata produser ($\lambda$) melampaui kapasitas konsumsi rata-rata sistem hilir ($\mu$), buffer channel berukuran berapapun pada akhirnya akan penuh. Ketika buffer penuh, sistem menerapkan *backpressure*: produser tertahan (*blocked*) pada operasi pengiriman, memperlambat laju masuk sistem secara alami.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi bertahap dari pola **Pipeline & Dynamic Fan-Out/Fan-In** dengan *graceful cancellation* berbasis `context.Context`.

```go
package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sync"
	"time"
)

// Unit kerja yang mengalir melalui pipeline
type Job struct {
	ID        int
	Payload   string
	Result    string
	Err       error
}

// Stage 1: Generator - Membangkitkan stream data dengan pembatalan context
func jobGenerator(ctx context.Context, totalJobs int) <-chan Job {
	out := make(chan Job)
	go func() {
		defer close(out)
		for i := 1; i <= totalJobs; i++ {
			select {
			case <-ctx.Done():
				return // Menghentikan emisi jika konteks dibatalkan
			case out <- Job{ID: i, Payload: fmt.Sprintf("event-payload-node-%d", i)}:
			}
		}
	}()
	return out
}

// Stage 2: Worker Core - Melakukan pemrosesan intensif (Fan-Out candidate)
func executeWork(ctx context.Context, in <-chan Job) <-chan Job {
	out := make(chan Job)
	go func() {
		defer close(out)
		for job := range in {
			select {
			case <-ctx.Done():
				return
			default:
				// Simulasi kalkulasi kriptografis
				hasher := sha256.New()
				hasher.Write([]byte(job.Payload))
				job.Result = hex.EncodeToString(hasher.Sum(nil))
				
				select {
				case <-ctx.Done():
					return
				case out <- job:
				}
			}
		}
	}()
	return out
}

// Stage 3: Fan-In Multiplexer - Menggabungkan N channel menjadi satu channel tunggal
func fanIn(ctx context.Context, channels ...<-chan Job) <-chan Job {
	var wg sync.WaitGroup
	multiplexed := make(chan Job)

	multiplex := func(c <-chan Job) {
		defer wg.Done()
		for job := range c {
			select {
			case <-ctx.Done():
				return
			case multiplexed <- job:
			}
		}
	}

	wg.Add(len(channels))
	for _, c := range channels {
		go multiplex(c)
	}

	// Goroutine supervisor untuk menutup channel downstream saat semua upstream selesai
	go func() {
		wg.Wait()
		close(multiplexed)
	}()

	return multiplexed
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Fungsi `jobGenerator`:
*   `out := make(chan Job)`: Membuat unbuffered channel. Pemilihan unbuffered memaksakan sinkronisasi ketat (*rendezvous*) antara generator dan konsumen berikutnya, mencegah akumulasi memori jika hilir belum siap.
*   `go func() { defer close(out) ... }()`: Menjalankan generator dalam goroutine terpisah dan menggunakan idiom `defer close(out)`. Ini menegakkan aturan bahwa pengirim bertanggung jawab penuh atas penutupan channel data.
*   `select { case <-ctx.Done(): return case out <- Job{...}: }`: Penjaga non-blocking leak. Jika konsumen dihentikan secara prematur, pengirim tidak akan *hang* selamanya saat mencoba menulis ke `out`.

### Analisis Fungsi `executeWork`:
*   `for job := range in`: Menerima data secara berulang hingga channel upstream `in` ditutup dan dikosongkan.
*   `select { case <-ctx.Done(): return default: ... }`: Menjamin goroutine dapat segera keluar jika sinyal pembatalan masuk saat berada dalam loop pemrosesan.
*   `select { case <-ctx.Done(): return case out <- job: }`: Proteksi ganda pada tahap write downstream. Mencegah goroutine tersangkut ketika mencoba mengirim hasil kalkulasi ke channel hilir yang tidak lagi dibaca karena context sudah dibatalkan.

### Analisis Fungsi `fanIn`:
*   `var wg sync.WaitGroup`: Menginisialisasi primitive sinkronisasi untuk memantau status terminasi seluruh *reader goroutines*.
*   `wg.Add(len(channels))`: Menetapkan delta counter tepat sejumlah channel input yang akan digabungkan.
*   `defer wg.Done()` di dalam `multiplex`: Memastikan setiap goroutine yang menyelesaikan pembacaan (baik karena input habis atau context batal) mengurangi counter WaitGroup.
*   `go func() { wg.Wait(); close(multiplexed) }()`: Pola mutlak fan-in. Goroutine supervisor terpisah memblokir eksekusi pada `wg.Wait()`. Segera setelah seluruh goroutine `multiplex` selesai, channel gabungan ditutup secara aman, memberikan sinyal EOF ke tahap berikutnya.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi:
Sebuah platform analitik finansial memproses aliran log transaksi berkecepatan tinggi dari ribuan terminal pembayaran. 

### Persyaratan Sistem:
1.  **High Throughput & Ingestion Rate:** Mampu menyerap transaksi tanpa memblokir edge endpoint pengirim.
2.  **External Enrichment:** Setiap transaksi harus diperkaya dengan skor risiko via REST API pihak ketiga yang memiliki latensi rata-rata $50\text{ ms}$ dan batasan kuota (*rate limit*).
3.  **Graceful Degradation & Timeout:** Jika layanan skor pihak ketiga melambat atau terjadi error massal, sistem tidak boleh mengalami crash OOM. Sistem harus membatasi konkurensi eksternal ke maksimal 20 worker simultan.
4.  **Graceful Teardown:** Ketika aplikasi menerima sinyal terminate (`SIGTERM`), sistem harus menguras transaksi yang sudah diterima hingga selesai diproses dan disimpan ke layer penyimpanan sebelum proses mati sepenuhnya.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem produksi menggunakan pola **Resilient Worker Pool** dengan dependensi `golang.org/x/sync/errgroup`, backpressure buffer, pembatalan terstruktur, serta agregasi hasil.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"math/rand"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"golang.org/x/sync/errgroup"
)

type Transaction struct {
	ID        string
	Amount    float64
	Timestamp time.Time
}

type EnrichedTransaction struct {
	Transaction
	RiskScore float64
	FraudFlag bool
	ProcessedBy int
}

// Simulasi layanan penilaian risiko eksternal
func externalRiskScoringService(ctx context.Context, txID string) (float64, error) {
	select {
	case <-ctx.Done():
		return 0.0, ctx.Err()
	case <-time.After(time.Duration(15+rand.Intn(20)) * time.Millisecond): // Simulasi I/O
		if rand.Float32() < 0.001 { // 0.1% transient network failure
			return 0.0, errors.New("upstream gateway timeout")
		}
		return rand.Float64(), nil
	}
}

// Engine Orchestrator
type ProcessingEngine struct {
	workerCount int
	bufferSize  int
}

func NewProcessingEngine(workerCount, bufferSize int) *ProcessingEngine {
	return &ProcessingEngine{
		workerCount: workerCount,
		bufferSize:  bufferSize,
	}
}

func (pe *ProcessingEngine) Run(ctx context.Context, inputData []Transaction) error {
	// Root errgroup untuk koordinasi seluruh goroutine
	g, gCtx := errgroup.WithContext(ctx)

	inflowChan := make(chan Transaction, pe.bufferSize)
	resultsChan := make(chan EnrichedTransaction, pe.bufferSize)

	// 1. Stage Ingestion (Producer)
	g.Go(func() error {
		defer close(inflowChan)
		for _, tx := range inputData {
			select {
			case <-gCtx.Done():
				return gCtx.Err()
			case inflowChan <- tx:
			}
		}
		return nil
	})

	// 2. Stage Processing (Worker Pool dengan Fan-Out)
	var workerWg sync.WaitGroup
	for w := 1; w <= pe.workerCount; w++ {
		workerID := w
		workerWg.Add(1)
		g.Go(func() error {
			defer workerWg.Done()
			for {
				select {
				case <-gCtx.Done():
					return gCtx.Err()
				case tx, ok := <-inflowChan:
					if !ok {
						return nil // Inflow ditutup dan kosong, worker keluar
					}

					// Enrich via external I/O
					score, err := externalRiskScoringService(gCtx, tx.ID)
					if err != nil {
						// Jika terjadi error fatal, gagalkan pipeline
						return fmt.Errorf("worker %d failed processing tx %s: %w", workerID, tx.ID, err)
					}

					enriched := EnrichedTransaction{
						Transaction: tx,
						RiskScore:   score,
						FraudFlag:   score > 0.85,
						ProcessedBy: workerID,
					}

					select {
					case <-gCtx.Done():
						return gCtx.Err()
					case resultsChan <- enriched:
					}
				}
			}
		})
	}

	// 3. Supervisor untuk menutup channel results setelah seluruh worker selesai
	g.Go(func() error {
		workerWg.Wait()
		close(resultsChan)
		return nil
	})

	// 4. Stage Sink/Aggregation (Consumer)
	g.Go(func() error {
		var processedCounter int
		var fraudCount int

		for res := range resultsChan {
			processedCounter++
			if res.FraudFlag {
				fraudCount++
			}
		}

		fmt.Printf("[METRIC] Total Transaksi Diproses: %d | Terindikasi Fraud: %d\n", processedCounter, fraudCount)
		return nil
	})

	// Tunggu hingga seluruh komponen selesai atau terjadi error pertama
	if err := g.Wait(); err != nil {
		if errors.Is(err, context.Canceled) {
			fmt.Println("[SYSTEM] Pipeline dihentikan via pembatalan konteks.")
			return nil
		}
		return fmt.Errorf("pipeline execution halted with error: %w", err)
	}

	return nil
}

func main() {
	// Konfigurasi sistem
	const (
		totalRecords = 1000
		concurrency  = 20
		bufferLimit  = 100
	)

	// Mock Data Input
	dataset := make([]Transaction, totalRecords)
	for i := 0; i < totalRecords; i++ {
		dataset[i] = Transaction{
			ID:        fmt.Sprintf("TXN-%05d", i+1),
			Amount:    float64(rand.Intn(100000)) / 100.0,
			Timestamp: time.Now(),
		}
	}

	// Menyiapkan Graceful Shutdown Context
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	engine := NewProcessingEngine(concurrency, bufferLimit)
	
	start := time.Now()
	fmt.Printf("[SYSTEM] Memulai pemrosesan %d transaksi dengan concurrency limit %d...\n", totalRecords, concurrency)

	if err := engine.Run(ctx, dataset); err != nil {
		fmt.Fprintf(os.Stderr, "[ERROR] Kegagalan sistem: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("[SYSTEM] Eksekusi tuntas dengan aman dalam: %s\n", time.Since(start))
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih mekanisme sinkronisasi dan model konkurensi menuntut pemahaman trade-off yang tepat:

| Dimensi Arsitektur | Channels (CSP) | `sync.Mutex` / State Sharing | `sync/atomic` Primitive |
| :--- | :--- | :--- | :--- |
| **Pola Penggunaan Utama** | Transfer kepemilikan data, stream processing, orkestrasi task. | Mutasi internal struktur data in-memory (misal: cache, map internal). | Operasi matematika sederhana pada angka tunggal / flag penanda status. |
| **Overhead Alokasi & CPU** | Lebih berat; overhead alokasi struktur `hchan`, `sudog`, dan internal mutex locks. | Ringan; pemanggilan primitive OS futex langsung, alokasi memori minimal. | Hampir nol; instruksi langsung pada level assembly mikroprosesor (LOCK CMPXCHG). |
| **Kompleksitas Desain** | Bersih pada arsitektur pipeline, namun rawan *deadlock* jika dependensi channel sirkular. | Rawan *race condition* jika ada developer yang lupa memanggil `Lock()`. | Sangat rentan bug jika digunakan untuk alur logika yang kompleks. |
| **Skalabilitas Kontensi** | Sangat baik jika digunakan dalam pola decoupled pipeline. | Performa turun drastis jika lock contention tinggi pada core CPU yang banyak. | Performa tertinggi untuk manipulasi nilai individual. |

### Buffered vs Unbuffered Channels:
*   **Unbuffered (`make(chan T)`):** Memberikan jaminan konsistensi deterministik terkuat (*strong temporal coupling*). Pengirim dijamin tahu bahwa penerima telah mengambil payload tepat saat ekspresi send selesai. Biayanya: penurunan throughput karena pengirim sering tertahan.
*   **Buffered (`make(chan T, N)`):** Melepaskan kopling waktu (*temporal decoupling*) untuk menangani lonjakan sementara. Risikonya: jika nilai $N$ terlalu besar, buffer menyembunyikan masalah *latent backpressure*, mengonsumsi memori besar, dan data di dalam buffer dapat hilang jika proses crash (*ungraceful termination*).

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Channel Range Deadlock
Ketika melakukan iterasi menggunakan `for val := range ch`, loop ini **tidak akan pernah berhenti** hingga channel ditutup secara eksplisit melalui `close(ch)`. Jika goroutine produser keluar atau lupa menutup channel, goroutine konsumen akan tertahan selamanya pada status `gopark`, memicu *goroutine leak* dan akhirnya *fatal error: all goroutines are asleep - deadlock!* jika seluruh runtime terkunci.

### 2. Leaking Context Listeners
Goroutine yang memantau context:
```go
go func() {
    <-ctx.Done()
    // Cleanup resources
}()
```
Jika `ctx` tidak pernah dibatalkan (misal menggunakan `context.Background()` tanpa timeout), goroutine di atas akan menetap di memori heap hingga proses aplikasi mati. Ini merupakan kebocoran memori pasif yang sangat sulit dideteksi tanpa profiling heap runtime.

### 3. Non-Blocking Select with Default Hazards
```go
select {
case ch <- data:
default:
    // Pesan diabaikan secara diam-diam!
}
```
Pola ini sering disalahgunakan untuk "menghindari blocking". Bahayanya: jika downstream sedikit saja mengalami perlambatan, blok `default` akan segera dieksekusi secara instan, menyebabkan *silent data loss* tanpa ada pesan error yang tercatat.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mengirim Data ke Channel yang Ditutup (*Send on Closed Channel*)
```go
// ANTI-PATTERN: Menutup channel dari sisi penerima
func badReceiver(ch chan int) {
    val := <-ch
    if val == -1 {
        close(ch) // FATAL: Jika pengirim masih berjalan, runtime akan PANIC!
    }
}
```
**Perbaikan:**
Hanya pihak pengirim yang memiliki otorisasi untuk menutup channel. Jika penerima ingin meminta penghentian, gunakan channel sinyal pembatalan atau `context.Context`:
```go
// IDIOMATIC: Mengirim sinyal pembatalan upstream via Context
func correctReceiver(ctx context.Context, cancel context.CancelFunc, ch <-chan int) {
    for val := range ch {
        if val == -1 {
            cancel() // Menginstruksikan produser untuk berhenti secara teratur
            return
        }
    }
}
```

### Kesalahan 2: Menyalin (*Passing by Value*) Mutex atau Sinkronisasi
Primitive sinkronisasi Go (`sync.Mutex`, `sync.WaitGroup`, `sync.Cond`) membungkus state internal runtime yang tidak boleh disalin.

```go
// ANTI-PATTERN: Struct sync primitive dilewatkan secara copy-by-value
func worker(wg sync.WaitGroup) { // Mengkopi state WaitGroup!
    defer wg.Done()              // Mutasi tidak berpengaruh ke pemanggil luar!
}
```
**Perbaikan:**
Selalu lewatkan melalui pointer (`wg *sync.WaitGroup`) atau bungkus dalam method receiver bertipe pointer:
```go
// IDIOMATIC: Melewatkan reference pointer
func worker(wg *sync.WaitGroup) {
    defer wg.Done()
}
```
*Gunakan `go vet` untuk mendeteksi pelanggaran penyalinan locks secara otomatis saat build.*

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Strict Channel Directionality:** Selalu deklarasikan channel pada signature fungsi dengan arah aliran data yang eksplisit. 
    *   `<-chan T` (hanya terima/read-only).
    *   `chan<- T` (hanya kirim/write-only).
    Ini membatasi kesalahan logika kompilasi secara statis (*compile-time safety*).
2.  **Explicit Goroutine Lifetime Ownership:** Jangan pernah memulai goroutine baru tanpa menjawab dua pertanyaan ini:
    *   *Kapan goroutine ini akan berhenti?*
    *   *Apa yang menghalanginya untuk berhenti tepat waktu?*
3.  **Fail-Fast Context Propagation:** Parameter `ctx context.Context` harus selalu menjadi parameter urutan pertama dalam fungsi yang menangani konkurensi atau operasi asinkron/blocking.
4.  **Use `golang.org/x/sync/errgroup` over Raw WaitGroups:** Untuk pipeline yang melibatkan potensi error pada worker-nya, `errgroup` menyediakan standardisasi penangkapan error pertama (*first-error capture*) dan sinkronisasi terminasi secara otomatis.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Menghindari False Sharing (Cache Line Contention)
Ketika multiple goroutine pada core CPU yang berbeda memodifikasi variabel bersebelahan di memori secara simultan, CPU membatalkan baris cache L1/L2 (*Cache Line Invalidation*), memicu fenomena *False Sharing* yang menurunkan performa.

```go
// Sub-optimal: Data bersebelahan berada dalam 1 cache line (biasanya 64 byte)
type MetricsSuboptimal struct {
    counterA uint64 // 8 byte
    counterB uint64 // 8 byte
}

// Teroptimasi: Padding data dengan boundary cache-line 64-byte
type MetricsOptimized struct {
    counterA uint64
    _        [56]byte // Padding memastikan counterB berada di cache-line berbeda
    counterB uint64
    _        [56]byte
}
```

### 2. Mengurangi Alokasi GC Menggunakan `sync.Pool`
Dalam high-throughput fan-out pipelines, pembuatan payload per-job yang berulang-ulang menciptakan beban berat bagi Garbage Collector.

```go
var payloadPool = sync.Pool{
    New: func() any {
        return make([]byte, 4096) // Pre-allocate buffer 4KB
    },
}

func ProcessJobWithPool() {
    buf := payloadPool.Get().([]byte)
    // Gunakan buffer
    payloadPool.Put(buf[:0]) // Reset slice length dan kembalikan ke pool
}
```

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **DDoS & Resource Exhaustion Protection:** Membatasi channel buffer dan mengimplementasikan timeout di setiap stage pipeline. Jika buffer dibiarkan unbounded atau dialokasikan tanpa batas, sistem rentan terhadap serangan denial-of-service berbasis kehabisan memori.
2.  **Panic Recovery within Goroutines:** Panic yang tidak ditangkap di dalam goroutine anak akan menyebabkan **seluruh proses crash**, bukan hanya goroutine tersebut. Setiap boundary worker pool wajib memiliki proteksi defer-recover:

```go
func SafeWorkerLauncher(task func()) {
    go func() {
        defer func() {
            if r := recover(); r != nil {
                // Log stack trace secara terstruktur menggunakan runtime/debug
                fmt.Fprintf(os.Stderr, "[PANIC RECOVERED] Error: %v\n", r)
            }
        }()
        task()
    }()
}
```

3.  **Automated Data Race Detection:** Wajib menjalankan validasi race detection pada continuous integration (CI) pipeline:
```bash
go test -race -count=10 ./...
```
*Catatan: binary yang dikompilasi dengan `-race` membutuhkan alokasi CPU 2-10x lebih banyak dan alokasi memori 5-20x lebih tinggi; jangan jalankan flag ini di deployment binary produksi utama.*

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Deteksi Goroutine Leak Menggunakan Runtime Profiles
Tambahkan pprof endpoint pada service production internal untuk melacak jumlah goroutine:

```go
import _ "net/http/pprof"

go func() {
    log.Println(http.ListenAndServe("localhost:6060", nil))
}()
```
Periksa dump goroutine melalui terminal jika metrik menunjukkan tren naik (*linear upward trend*) yang tidak pernah turun:
```bash
go tool pprof http://localhost:6060/debug/pprof/goroutine
```

### 2. Runtime Execution Tracing
Untuk menganalisis latency spikes, channel contention, dan interaksi scheduler, gunakan tool execution trace bawaan Go:

```go
import "runtime/trace"

func main() {
    f, _ := os.Create("trace.out")
    defer f.Close()
    trace.Start(f)
    defer trace.Stop()

    // Eksekusi kode pipeline konkuren di sini...
}
```
Visualisasikan trace di browser:
```bash
go tool trace trace.out
```
*Visualisasi trace menampilkan timeline presisi kapan goroutine di-block, durasi sys-call, channel synchronization overhead, serta aktivitas steal work oleh thread scheduler.*

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Tabel Ringkasan Pola Konkurensi:

| Pola | Kapan Digunakan | Kunci Keberhasilan |
| :--- | :--- | :--- |
| **Pipeline** | Aliran data bertahap linear (Filter $\to$ Transform $\to$ Sink). | Pengirim menutup channel (`close(out)`). Gunakan unbuffered/small buffer. |
| **Fan-Out** | Satu tahap I/O atau komputasi lambat menghambat tahap pipeline berikutnya. | Terapkan batasan jumlah worker (*Bounded Worker Pool*). |
| **Fan-In** | Menggabungkan hasil pemrosesan dari banyak worker paralel kembali ke 1 stream. | Gunakan `sync.WaitGroup` pada goroutine supervisor untuk `close(multiplexed)`. |
| **Orchestration** | Eksekusi tugas paralel yang harus berhenti bersamaan saat terjadi 1 error. | Gunakan `golang.org/x/sync/errgroup` dengan context pembatalan terpadu. |

### Cheatsheet Aturan Baku Runtime Go:
*   Membaca dari nil channel: **Block selamanya.**
*   Menulis ke nil channel: **Block selamanya.**
*   Menutup nil channel: **Panic!**
*   Menulis ke closed channel: **Panic!**
*   Membaca dari closed channel: **Mengembalikan nilai zero value segera (`val, ok := <-ch` di mana `ok == false`).**

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Bagian A: Pilihan Ganda Tingkat Dasar (Pahami Inti Dasar)

**Soal 1:** Apa yang terjadi jika sebuah goroutine mencoba mengirim data (`ch <- 10`) ke sebuah channel unbuffered yang tidak memiliki goroutine penerima yang sedang aktif?
*   A. Runtime langsung melempar sinyal panic.
*   B. Nilai data dibuang secara diam-diam.
*   C. Goroutine tersebut diparkir (*gopark*) dan dialihkan dari eksekusi thread hingga ada penerima yang siap.
*   D. Nilai dialokasikan sementara di Global Run Queue.

**Soal 2:** Manakah pernyataan yang paling tepat mengenai aturan penutupan channel di Go?
*   A. Channel harus selalu ditutup oleh fungsi `main()`.
*   B. Penerima harus menutup channel segera setelah membaca nilai pertama.
*   C. Pihak produser/pengirim data yang bertanggung jawab menutup channel saat transmisi data selesai.
*   D. Setiap goroutine yang berinteraksi dengan channel wajib memanggil `close()`.

**Soal 3:** Apa hasil eksekusi dari operasi `close(ch)` pada channel yang sebelumnya telah ditutup?
*   A. Mengembalikan nilai `false`.
*   B. Runtime panic: "close of closed channel".
*   C. Channel kembali terbuka dengan state reset.
*   D. Goroutine diblokir tanpa batas waktu.

**Soal 4:** Bagaimana cara mengecek secara deterministik bahwa sebuah channel telah kosong dan ditutup?
*   A. Menggunakan `len(ch) == 0`.
*   B. Memeriksa `cap(ch) == 0`.
*   C. Memeriksa boolean status `ok` pada idiom penerimaan: `val, ok := <-ch`.
*   D. Membungkus pembacaan di dalam blok `defer recover()`.

**Soal 5:** Apa fungsi utama dari paket `golang.org/x/sync/errgroup` dibandingkan `sync.WaitGroup` biasa?
*   A. Meningkatkan kecepatan eksekusi goroutine hingga 2x lipat.
*   B. Mengotomatisasi alokasi core CPU melalui pemanggilan GOMAXPROCS.
*   C. Mengikat siklus hidup kumpulan goroutine dengan penangkapan error pertama dan propagasi pembatalan konteks otomatis.
*   D. Menghilangkan kebutuhan alokasi heap pada goroutine.

---

### Bagian B: Analisis Masalah Tingkat Menengah

**Soal 6:** Diberikan potongan kode berikut:
```go
func streamData() <-chan int {
    ch := make(chan int)
    go func() {
        for i := 0; i < 5; i++ {
            ch <- i
        }
    }()
    return ch
}

func main() {
    data := streamData()
    for v := range data {
        fmt.Println(v)
    }
}
```
Apa anomali yang akan terjadi saat kode di atas dieksekusi hingga akhir?
*   A. Kode berjalan lancar dan mencetak angka 0 sampai 4 kemudian keluar normal.
*   B. Terjadi *deadlock* fatal di akhir eksekusi karena goroutine produser tidak pernah memanggil `close(ch)`.
*   C. Terjadi runtime panic "send on closed channel".
*   D. Nilai 0 dicetak secara berulang tanpa batas waktu (*infinite loop*).

**Soal 7:** Mengapa pola pengiriman berikut ini dianggap berbahaya pada sistem bertransaksi tinggi?
```go
select {
case queue <- task:
default:
    // Drop task
}
```
*   A. Karena syntax `default` pada `select` otomatis menonaktifkan garbage collector.
*   B. Menghapus data secara prematur (*dropped data*) saat sistem hilir hanya mengalami fluktuasi beban mikro sementara.
*   C. Menghasilkan panic jika channel `queue` belum diinisialisasi buffer-nya.
*   D. Mengakibatkan CPU spinning mencapai 100% secara permanen.

**Soal 8:** Perhatikan skenario ini: Goroutine A menunggu pembacaan dari Channel 1 untuk mengirim ke Channel 2. Goroutine B menunggu pembacaan dari Channel 2 untuk mengirim ke Channel 1. Kondisi patologis ini dinamakan:
*   A. Priority Inversion.
*   B. Circular Wait Deadlock.
*   C. Cache Thrashing.
*   D. Data Race Condition.

**Soal 9:** Mengapa passing `sync.Mutex` sebagai argumen nilai (by-value) ke fungsi lain dilarang keras di Go?
*   A. Mengakibatkan *compile error* langsung pada toolchain Go versi apapun.
*   B. Mengkopi mutex menduplikasi state internal kunci; lock yang diakuisisi fungsi baru tidak akan mengunci mutex asli yang digunakan fungsi pemanggil.
*   C. Menyebabkan memory leak pada heap runtime.
*   D. Menghentikan scheduler Go secara global.

**Soal 10:** Kapan kita sebaiknya memilih `sync.RWMutex` daripada `sync.Mutex` standar?
*   A. Ketika jumlah operasi penulisan (*write*) jauh lebih tinggi daripada pembacaan (*read*).
*   B. Ketika siklus hidup goroutine diatur langsung oleh kernel thread OS.
*   C. Ketika frekuensi operasi pembacaan (*read*) sangat dominan secara signifikan dibandingkan operasi penulisan (*write*), dan critical section memakan waktu non-sepele.
*   D. Ketika resource yang dilindungi bertipe data pointer interface.

---

### KUNCI JAWABAN KUIS:

*   **Soal 1: C** — Runtime memarkir goroutine dan mengalihkan thread ke goroutine lain (CSP blocking mechanism).
*   **Soal 2: C** — Aturan mutlak kepemilikan channel: pengirim yang menutup channel, bukan konsumen.
*   **Soal 3: B** — Melakukan close pada channel yang sudah berstatus closed akan memicu runtime panic seketika.
*   **Soal 4: C** — Idiom dua nilai `val, ok := <-ch`; `ok` bernilai `false` mengindikasikan channel tertutup dan tidak ada lagi sisa buffer.
*   **Soal 5: C** — `errgroup` menggabungkan sinkronisasi penyelesaian, penangkapan error pertama, dan propagasi context cancellation.
*   **Soal 6: B** — Loop `range data` di main goroutine terus menunggu data baru selamanya karena `ch` tidak pernah di-close, menghasilkan error deadlock fatal.
*   **Soal 7: B** — Tanpa backpressure queue yang terukur, pola non-blocking drop langsung membuang transaksi valid begitu buffer penuh sepersekian milidetik.
*   **Soal 8: B** — Circular wait adalah salah satu syarat terjadinya deadlock (Coffman conditions).
*   **Soal 9: B** — Pengkopian nilai memisahkan referensi mutual exclusion, membuat shared state tidak terlindungi sama sekali dari race condition.
*   **Soal 10: C** — `sync.RWMutex` optimal hanya jika proporsi read jauh lebih tinggi dari write, karena RWMutex memiliki overhead manajemen pembukuan reader tracking yang lebih tinggi dibandingkan Mutex biasa.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Tugas Praktikum:
Rancang dan bangunlah sistem mikro-pipeline bertajuk: **"Resilient Bulk Image Processing & Metadata Extractor"**.

### Kebutuhan Spesifikasi Fungsional:
1.  **Stage 1: Job Ingestion & Scanner:**
    *   Membaca antrean nama file dari slice in-memory (simulasi minimal 500 file).
    *   Memancarkan data melalui channel ber-buffer terbatas (*bounded buffer capacity = 50*).
2.  **Stage 2: Bounded Concurrent Processing (Worker Pool):**
    *   Gunakan pool berukuran tetap (maksimal 10 goroutine pekerja).
    *   Setiap pekerja melakukan simulasi: kompresi gambar, ekstraksi metadata SHA256, dan validasi header.
    *   Terapkan simulasi kegagalan acak sebesar 1%: jika sebuah file gagal diproses 3 kali berturut-turut, seluruh pipeline harus membatalkan tugas yang sedang berjalan secara teratur (*graceful cascading teardown*) menggunakan `errgroup`.
3.  **Stage 3: Fan-In Collector:**
    *   Satukan seluruh output pemrosesan dari ke-10 worker ke dalam satu channel output terpadu.
4.  **Stage 4: Aggregator & Audit Logger:**
    *   Konsumsi channel output terpadu dan kumpulkan metrik: Total bytes diproses, rata-rata durasi pemrosesan per item, dan total item berhasil.
5.  **Kriteria Uji Mutu (System Requirements):**
    *   Kode harus lulus pengujian rasial: `go run -race .` tanpa peringatan data race apapun.
    *   Dilarang memicu goroutine leak: setelah eksekusi selesai, `runtime.NumGoroutine()` sebelum program exit harus kembali ke kondisi baseline (hanya menyisakan goroutine sistem internal).
    *   Tangkap interrupt signal OS (`SIGINT`, `SIGTERM`) agar jika user menekan `Ctrl+C`, sistem mencetak laporan item yang sempat selesai diproses sebelum aplikasi ditutup dengan aman.