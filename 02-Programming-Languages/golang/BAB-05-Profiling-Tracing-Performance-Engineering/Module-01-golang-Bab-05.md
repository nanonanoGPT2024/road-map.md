# SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: GOL-05-01
* **Kategori**: 02-Programming-Languages / Go
* **Judul**: Profiling, Tracing & Performance Engineering
* **Level**: Advanced (Tingkat Lanjut)
* **Estimasi Waktu Belajar**: 8 - 10 Jam
* **Prasyarat**: 
  * Pemahaman mendalam tentang runtime Go (GMP Scheduler, Memory Allocator, Garbage Collector).
  * Kemahiran dalam concurrency primitive Go (`goroutine`, `channel`, `sync.Mutex`, `sync.WaitGroup`).
  * Pemahaman arsitektur sistem operasi dasar (Virtual Memory, Context Switching, CPU Cache L1/L2/L3, Kernel Signals).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Mekanisme Sampling Internal Go**: Menguraikan cara runtime Go menginterupsi eksekusi menggunakan `SIGPROF` dan bagaimana stack unwinding dilakukan untuk mengumpulkan profil CPU, Memori, Mutex, dan Block.
2. **Mengoperasikan Runtime Profiling Toolchain**: Mengonfigurasi, menghasilkan, dan menginterpretasikan profil (`cpu`, `heap`, `allocs`, `goroutine`, `block`, `mutex`) menggunakan `runtime/pprof`, `net/http/pprof`, dan CLI `go tool pprof`.
3. **Mendiagnosis Bottleneck dengan Go Execution Tracer**: Menganalisis trace timeline menggunakan `go tool trace` untuk mendeteksi goroutine starvation, sysmon blocking, network poller contention, dan overhead Garbage Collection (STW vs Concurrent Mark/Sweep).
4. **Menerapkan Analisis Statis & Kompilator**: Mengidentifikasi titik alokasi memori melalui Escape Analysis (`go build -gcflags="-m"`) dan memverifikasi eliminasi alokasi yang tidak perlu.
5. **Merancang Sistem Berperforma Tinggi**: Memitigasi beban Garbage Collector menggunakan teknik *Zero-Allocation*, object pooling (`sync.Pool`), memory padding untuk menghindari *False Sharing*, dan struktur data yang ramah CPU cache (*Data-Oriented Design*).
6. **Mengamankan Endpoint Profiling di Lingkungan Produksi**: Merancang arsitektur eksposur metrik diagnostik yang terisolasi dari akses publik guna mencegah eksfiltrasi memori dan serangan Denial of Service (DoS).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### 1. The Fallacy of Intuition vs. The Rigor of Measurement
Intuisi manusia sangat buruk dalam memprediksi bottleneck performa pada sistem konkuren terdistribusi. Hukum dasar rekayasa performa adalah:
> *"Jangan menebak. Ukur, formulasikan hipotesis, verifikasi dengan profil, lakukan perubahan minimal, dan ukur ulang menggunakan data statistik yang valid (benchstat)."*

### 2. Mechanical Sympathy
Software tidak berjalan di atas ruang hampa abstrak; ia dieksekusi oleh transistor, register CPU, cache line (biasanya 64 bytes), branch predictor, dan translation lookaside buffers (TLB). Menulis kode Go performa tinggi menuntut *Mechanical Sympathy*—keselarasan antara semantik Go (slice, pointer, goroutine) dengan model fisik perangkat keras modern:
* Alokasi heap bukan sekadar masalah ruang; itu adalah latensi translasi pointer dan beban masa depan bagi GC.
* Akses data sekuensial (array/slice traversals) ratusan kali lebih cepat dibanding melompat pointer (linked list/node graph) karena L1/L2 data prefetcher.

### 3. Profiling vs. Tracing: Ruang Keadaan (State-Space)
* **Profiling (Agregat & Statistik)**: Menjawab pertanyaan *"Di mana waktu atau memori paling banyak dihabiskan secara kumulatif?"*. Profiling mengambil sampel periodik dari call stack sistem.
* **Tracing (Kronologis & Kausalitas)**: Menjawab pertanyaan *"Kapan peristiwa ini terjadi, mengapa goroutine ini terblokir, dan core mana yang menanganinya?"*. Tracing merekam transisi status (state transitions) diskret setiap kali entitas GMP berinteraksi.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Arsitektur Koleksi Data Profiling & Tracing di Go Runtime

```
 +-----------------------------------------------------------------------------------+
 |                                   OS & HARDWARE                                   |
 |  +-----------------------+     +--------------------+     +--------------------+  |
 |  |    Hardware Timer     |     |   L1/L2/L3 Cache   |     |    Physical RAM    |  |
 |  |  (ITIMER_PROF 100Hz)  |     |   (64-byte Line)   |     |                    |  |
 +------+-------------------+-----+--------------------+-----+--------------------+--+
        |                                                                 ^
  SIGPROF (Interrupt)                                                     | Alloc/Free
        v                                                                 v
 +-----------------------------------------------------------------------------------+
 |                                    GO RUNTIME                                     |
 |                                                                                   |
 |  +--------------------+   Stack Unwind    +------------------------------------+  |
 |  | Signal Handler     | =================>| runtime.gentraceback()             |  |
 |  | (sighandler)       |                   +------------------+-----------------+  |
 |  +--------------------+                                      |                    |
 |                                                              v                    |
 |  +--------------------+                   +------------------------------------+  |
 |  | Memory Allocator   | (mallocgc hook)   | Profile Hash Table Bucket Map      |  |
 |  | (mcache / mcentral)| =================>| (Key: Stack Trace -> Value: Counts)|  |
 |  +--------------------+                   +------------------+-----------------+  |
 |                                                              |                    |
 |  +--------------------+   Event Ring Buf  +------------------v-----------------+  |
 |  | GMP Scheduler      | =================>| Trace Buffer (Per-P Batch Buffer)  |  |
 |  | (G states, Sysmon) |                   +------------------+-----------------+  |
 +--------------------------------------------------------------|--------------------+
                                                                | Flush
                                                                v
                                             +------------------------------------+
                                             |      pprof / trace Byte Stream     |
                                             +------------------+-----------------+
                                                                |
                                       +------------------------+------------------------+
                                       |                                                 |
                                       v                                                 v
                        [ runtime/pprof File Output ]                       [ net/http/pprof Endpoint ]
                                       |                                                 |
                                       +------------------------+------------------------+
                                                                v
                                              +-----------------------------------+
                                              |       ANALYTICAL TOOLCHAIN        |
                                              |  go tool pprof  /  go tool trace  |
                                              +-----------------------------------+
```

### Siklus Eksekusi Pengambilan Sampel CPU Profiling

```
      Thread (M) Running Goroutine (G)
                    |
                    |  (Clock ticks: 10ms interval)
                    v
           OS sends SIGPROF to M
                    |
                    v
    M intercepts signal via sighandler()
                    |
                    v
       Is M running Go code or C/Syscall?
         /                          \
   [Go Code]                   [Syscall/C]
        |                            |
  gentraceback() walks          Record top frame / 
  G stack to extract PC         system stack
        |                            |
        +------------+---------------+
                     |
                     v
   Format call stack into Program Counters (PCs)
                     |
                     v
   Write to CPU Profile Buffer (Lock-free Ring Buffer)
                     |
                     v
      Resume normal G execution on M
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. CPU Profiling: Mekanisme Interupsi Berbasis Sinyal
Saat CPU profiling diaktifkan (`pprof.StartCPUProfile`):
* Runtime mengatur timer sistem operasi melalui `setitimer(ITIMER_PROF)` (pada Unix-like) yang memancarkan sinyal `SIGPROF` dengan frekuensi default 100 Hz (setiap 10 milidetik).
* Ketika thread OS (`M`) menerima sinyal `SIGPROF`, eksekusi normal dihentikan sementara. OS mengalihkan kontrol ke fungsi `runtime.sighandler`.
* `sighandler` memanggil `runtime.gentraceback` untuk membaca register instruksi (`PC` / Program Counter) dan menelusuri stack pointer goroutine (`G`) yang sedang aktif pada thread tersebut.
* Hasil stack trace (deretan alamat instruksi/PC) dimasukkan ke dalam hash map internal yang memetakan rantai stack ke jumlah kemunculan (*hit counter*).
* Karena bersifat statistik (sampling), pemanggilan fungsi yang berjalan di bawah 10ms mungkin tidak tertangkap sama sekali, atau tertangkap berlebihan jika durasinya berkorelasi dengan frekuensi sinyal (*aliasing artifact*).

### 2. Heap & Allocation Profiling: Sampling Berbasis Byte
Berbeda dengan CPU profiling, profiling memori **tidak berbasis waktu**, melainkan **berbasis byte yang dialokasikan**:
* Variabel global runtime `runtime.MemProfileRate` (default: `512 * 1024` byte atau 512KB) menentukan interval sampling.
* Setiap kali fungsi `runtime.mallocgc` dipanggil untuk mengalokasikan objek pada heap, runtime mengurangi ukuran alokasi dari pseudo-random sampling counter internal thread (`mcache.next_sample`).
* Ketika counter bernilai $\le 0$, alokasi tersebut dipilih sebagai sampel. Runtime memanggil `gentraceback` untuk merekam call stack yang meminta alokasi tersebut dan mengaitkannya dengan ukuran objek.
* Terdapat dua metrik:
  * **Allocations (`alloc_space` / `alloc_objects`)**: Total akumulasi alokasi sejak proses berjalan, terlepas dari apakah memori tersebut telah dibebaskan oleh GC.
  * **In-Use (`inuse_space` / `inuse_objects`)**: Memori yang saat ini masih hidup dan dapat dijangkau oleh GC pointer graph.

### 3. Block & Mutex Contention Profiling
* **Block Profiling (`runtime.SetBlockProfileRate`)**: Mengukur durasi goroutine menunggu pada operasi unbuffered channel, select, sleep, atau sinkronisasi I/O. Nilai laju menentukan ambang batas durasi (dalam nanodetik) untuk dicatat.
* **Mutex Profiling (`runtime.SetMutexProfileFraction`)**: Mengukur durasi goroutine menunggu perebutan kunci (`sync.Mutex` atau `sync.RWMutex`). Runtime mengambil sampel 1 dari setiap $N$ kejadian kontensi mutex yang terselesaikan.

### 4. Go Execution Tracer Architecture
Tracer merekam setiap event runtime secara deterministik (non-sampling):
* Scheduler Events: Goroutine state transition (`_Gidle` $\to$ `_Grunnable` $\to$ `_Grunning` $\to$ `_Gwaiting`).
* System Events: Syscall invocation, Network Poller wakeups.
* GC Events: STW phase, Concurrent Mark Worker activity, Sweeping.
* Setiap Processor (`P`) memiliki buffer penulisan biner lokal tanpa lock (*lock-free local trace buffer*). Ketika buffer lokal penuh, ia di-flush ke buffer global, meminimalkan overhead tracing (biasanya overhead tracing berada pada kisaran 1-3% CPU overhead).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Escape Analysis: Stack vs. Heap Allocation
Kompilator Go menggunakan graph-reachability algorithm untuk menentukan apakah masa hidup (*lifetime*) sebuah variabel terikat mutlak pada frame fungsi yang mendeklarasikannya:

$$\text{Variabel } V \text{ lolos (escapes) ke Heap} \iff \exists \text{ path alur data dari } V \text{ ke referensi global, interface, atau stack pemanggil/goroutine lain.}$$

Jika compiler tidak dapat membuktikan bahwa variabel tidak dirujuk setelah fungsi kembali (*return*), variabel dialokasikan ke Heap.
* **Konsekuensi Stack Allocation**: Murah (hanya pergeseran register SP - Stack Pointer), zero GC cost, cache-locality tinggi.
* **Konsekuensi Heap Allocation**: Kompleks (pencarian span pada `mcache`/`mcentral`), menambah pointer scanning cost pada phase GC Mark, meningkatkan potensi fragmentasi memori.

### 2. Garbage Collection Cost Breakdown: The Three-Color Concurrent Mark Sweep
Go mengimplementasikan *Tri-color concurrent mark-sweep collector* dengan *write barrier*:
* **Mark Assist**: Jika laju alokasi aplikasi melampaui kemampuan background mark worker, runtime memaksa goroutine yang mengalokasikan memori untuk membantu proses scanning stack/objek (*Mark Assist*). Hal ini menyebabkan degradasi latensi transaksi secara tiba-tiba (*latency degradation tail events*).
* **GC Pacer**: Algoritma yang menghitung kapan GC harus dimulai berdasarkan variabel lingkungan `GOGC` (default: 100). Jika `GOGC=100`, GC dipicu ketika heap hidup bertambah 100%. Sejak Go 1.19, `GOMEMLIMIT` menyediakan batasan memori lunak (*soft memory limit*) yang mencegah OOM (*Out-Of-Memory*) tanpa memicu thrashing GC pada heap kecil.

### 3. Cache Line Contention & False Sharing
Arsitektur multi-core modern mempertahankan koherensi cache melalui protokol seperti MESI/MOESI pada tingkat Cache Line (umumnya 64 byte).
Jika dua goroutine pada thread OS terpisah memodifikasi dua variabel independen yang kebetulan berada dalam cache line 64-byte yang sama, core CPU akan terus-menerus membatalkan (*invalidate*) cache line satu sama lain melalui interconnect bus. Fenomena ini disebut **False Sharing**, yang dapat menurunkan throughput konkuren secara drastis meskipun tidak ada lock logis yang bentrok.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah program mandiri yang mendemonstrasikan cara mengaktifkan dan mengonfigurasi CPU profiling, memory profiling, block profiling, mutex profiling, dan runtime tracing secara murni tanpa server HTTP:

```go
package main

import (
	"context"
	"fmt"
	"math/rand"
	"os"
	"runtime"
	"runtime/pprof"
	"runtime/trace"
	"sync"
	"time"
)

const (
	cpuProfileFile   = "cpu.pprof"
	memProfileFile   = "mem.pprof"
	blockProfileFile = "block.pprof"
	mutexProfileFile = "mutex.pprof"
	traceProfileFile = "trace.out"
)

func main() {
	// 1. Konfigurasi Profiling Contention & Mutex
	runtime.SetBlockProfileRate(1000)     // Catat blocking event > 1 mikrodetik
	runtime.SetMutexProfileFraction(1)    // Ambil sampel 100% perebutan mutex

	// 2. Inisialisasi CPU Profiling
	cpuF, err := os.Create(cpuProfileFile)
	if err != nil {
		panic(fmt.Sprintf("gagal membuat file CPU profile: %v", err))
	}
	defer cpuF.Close()

	if err := pprof.StartCPUProfile(cpuF); err != nil {
		panic(fmt.Sprintf("gagal memulai CPU profile: %v", err))
	}
	defer pprof.StopCPUProfile()

	// 3. Inisialisasi Execution Tracer
	traceF, err := os.Create(traceProfileFile)
	if err != nil {
		panic(fmt.Sprintf("gagal membuat file trace: %v", err))
	}
	defer traceF.Close()

	if err := trace.Start(traceF); err != nil {
		panic(fmt.Sprintf("gagal memulai trace: %v", err))
	}
	defer trace.Stop()

	// 4. Simulasi Beban Kerja Rekayasa
	ctx, task := trace.NewTask(context.Background(), "BebanKomputasiUtama")
	simulateWorkload(ctx)
	task.End()

	// 5. Ekstraksi Heap Profile (Snapshot akhir)
	memF, err := os.Create(memProfileFile)
	if err != nil {
		panic(fmt.Sprintf("gagal membuat file Mem profile: %v", err))
	}
	defer memF.Close()

	runtime.GC() // Paksa GC agar inuse_space akurat merefleksikan retained memory
	if err := pprof.WriteHeapProfile(memF); err != nil {
		panic(fmt.Sprintf("gagal menulis heap profile: %v", err))
	}

	// 6. Ekstraksi Block & Mutex Profile
	writeProfile(blockProfileFile, "block")
	writeProfile(mutexProfileFile, "mutex")

	fmt.Println("Diagnostik performa selesai. Output tersimpan secara lokal.")
}

func simulateWorkload(ctx context.Context) {
	var wg sync.WaitGroup
	var mu sync.Mutex
	sharedData := make(map[int][]byte)

	// Profiler labels untuk mengidentifikasi goroutine spesifik
	labels := pprof.Labels("worker_pool", "data_cruncher")
	pprof.Do(ctx, labels, func(c context.Context) {
		for i := 0; i < 4; i++ {
			wg.Add(1)
			workerID := i
			go func() {
				defer wg.Done()
				region := trace.StartRegion(c, fmt.Sprintf("worker-%d", workerID))
				defer region.End()

				r := rand.New(rand.NewSource(int64(workerID)))
				for j := 0; j < 50000; j++ {
					// Simulasi CPU Burn & Alokasi Memori
					data := make([]byte, 1024) // 1 KB allocation per iteration
					for k := range data {
						data[k] = byte(r.Intn(256))
					}

					// Simulasi Contention Mutex
					if j%50 == 0 {
						mu.Lock()
						sharedData[workerID] = data
						time.Sleep(10 * time.Microsecond) // Simulasi critical section latency
						mu.Unlock()
					}
				}
			}()
		}
		wg.Wait()
	})
}

func writeProfile(fileName, profileName string) {
	f, err := os.Create(fileName)
	if err != nil {
		panic(fmt.Sprintf("gagal membuat file %s: %v", fileName, err))
	}
	defer f.Close()

	p := pprof.Lookup(profileName)
	if p == nil {
		panic(fmt.Sprintf("profile %s tidak ditemukan", profileName))
	}

	if err := p.WriteTo(f, 0); err != nil {
		panic(fmt.Sprintf("gagal menulis profile %s: %v", profileName, err))
	}
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis terhadap implementasi kode pada Seksi 07:

1. **Baris 27-28 (`runtime.SetBlockProfileRate` & `runtime.SetMutexProfileFraction`)**:
   * `SetBlockProfileRate(1000)`: Menginstruksikan runtime untuk mencatat event pemblokiran (blocking) yang memiliki durasi $\ge 1.000$ nanodetik ($1\ \mu\text{s}$). Nilai `1` merekam seluruh pemblokiran, namun memberikan overhead runtime yang signifikan pada aplikasi high-concurrency.
   * `SetMutexProfileFraction(1)`: Mengatur sampling rate mutex contention. Nilai `1` berarti setiap kejadian pertikaian kepemilikan mutex (ketika sebuah goroutine harus antre pada semaphore) akan direkam. Di lingkungan produksi bernilai tinggi, disarankan menggunakan fraksi seperti `5` atau `10`.
2. **Baris 35-38 (`pprof.StartCPUProfile`)**:
   * Mengaktifkan sinyal kernel `SIGPROF` dan mengalokasikan ring buffer berkapasitas tetap di internal runtime untuk menampung stack trace program counter. Eksekusi berjalan konkuren di latar belakang.
3. **Baris 49-52 (`trace.Start`)**:
   * Membuka kanal penulisan biner langsung dari P-local trace buffer. Tracing mencatat transisi status internal scheduler, berbeda dengan sampling statistik CPU profiling.
4. **Baris 55, 60 (`trace.NewTask`, `trace.StartRegion`)**:
   * Menghubungkan tracing eksekusi dengan konteks logika bisnis aplikasi. Saat dianalisis via `go tool trace`, developer dapat menyaring timeline berdasarkan nama task ("BebanKomputasiUtama") dan region individual per worker, memudahkan pelacakan latensi antar komponen logis.
5. **Baris 63-65 (`pprof.Labels`, `pprof.Do`)**:
   * Menempelkan profiler labels (key-value metadata) ke dalam thread-local/goroutine-local descriptor context. Ketika data CPU profile divisualisasikan, stack trace dapat difilter berdasarkan label `worker_pool: data_cruncher`.
6. **Baris 67 (`runtime.GC()`) sebelum `pprof.WriteHeapProfile`**:
   * Memicu siklus Garbage Collection sinkron penuh sebelum snapshot heap ditulis. Tindakan ini membersihkan objek unreachable (sampah) yang belum disapu, sehingga representasi `inuse_space` benar-benar merefleksikan data hidup (*retained memory*) yang aktif, memisahkan kebocoran memori (leak) dari sampah temporer.
7. **Baris 112 (`pprof.Lookup(profileName).WriteTo(f, 0)`)**:
   * Mengambil snapshot in-memory dari profil terdaftar runtime (`block`, `mutex`, `goroutine`, `threadcreate`). Parameter debug `0` menghasilkan output terkompresi berbasis protobuf standar pprof. Jika diubah menjadi `1` atau `2`, output berupa teks stack trace human-readable (khusus debugging manual).

---

# SEKSI 09 — STUDI KASUS NYATA

### Konteks: Masalah Latensi P99 pada High-Throughput Ingestion Engine
Sebuah financial processing gateway yang memproses 50.000 transaksi pembayaran per detik (TPS) mengalami lonjakan latensi persentil P99 dari baseline 2ms melonjak hingga 450ms secara periodik setiap 15 detik. Penggunaan CPU global server melonjak hingga 100%, dan terjadi pemutusan koneksi TCP akibat timeout.

### Langkah Diagnostik & Analisis Telemetri
1. **Inspeksi Heap Profiling**:
   * Melalui `go tool pprof http://localhost:6060/debug/pprof/allocs`, ditemukan bahwa fungsi parsing JSON:
     `json.Unmarshal([]byte, &transactionPayload)`
     mengalokasikan 4.2 GB data per detik ke heap.
   * `alloc_objects` menunjukkan terciptanya 12.000.000 objek kecil berumur pendek per detik.
2. **Inspeksi Execution Tracer (`go tool trace`)**:
   * Analisis timeline mengungkap bahwa Garbage Collector memasuki fase **Mark Assist** secara agresif.
   * Karena goroutine aplikasi mengalokasikan memori jauh lebih cepat dibanding kapasitas *Concurrent Mark Worker* membersihkannya, runtime Go secara otomatis membajak (*hijack*) goroutine worker transaksi yang masuk untuk memindai pointer graph memori (*GC Mark Assist*).
   * Akibatnya, goroutine yang seharusnya melayani HTTP request tertahan selama ratusan milidetik hanya untuk membantu GC, merusak kurva latensi P99.
3. **Inspeksi Mutex Profile**:
   * Teridentifikasi adanya lock contention terpusat pada layer caching in-memory yang menggunakan struktur global tunggal `sync.Mutex` untuk memperbarui status transaksi.

### Solusi Rekayasa
1. Mengganti standard reflection-based deserializer dengan code-generated serializer (`easyjson` / `sonic`) atau zero-allocation binary protocol (Protobuf).
2. Menggunakan `sync.Pool` untuk pooling slice buffer dan struct penampung request JSON guna meniadakan alokasi heap berulang.
3. Mengganti single global mutex cache menjadi Sharded/Striped Lock Map untuk mendistribusikan perebutan lock ke beberapa cache line independen.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah arsitektur mikro untuk Ingestion Worker Engine yang telah direkayasa dengan zero-allocation pool, thread-safe sharded map, serta safe HTTP diagnostic profiling server yang terpisah dari network ingress data utama.

```go
package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"fmt"
	"hash/fnv"
	"net/http"
	_ "net/http/pprof" // Mendaftarkan route /debug/pprof otomatis pada DefaultServeMux
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"
)

// Ukuran packet biner: 8 byte ID, 8 byte Timestamp, 8 byte Amount, 40 byte Meta = 64 bytes
type IngestionPayload struct {
	ID        uint64
	Timestamp int64
	Amount    float64
	Metadata  [40]byte
}

// 1. Zero-Allocation Object Pool
var payloadPool = sync.Pool{
	New: func() any {
		return new(IngestionPayload)
	},
}

// 2. Sharded Mutex Map untuk Menghindari Lock Contention
const ShardCount = 32

type ShardedMetrics struct {
	shards [ShardCount]*Shard
}

type Shard struct {
	mu    sync.Mutex
	total uint64
	_pad  [56]byte // Cache line padding (64 bytes total) untuk mencegah False Sharing!
}

func NewShardedMetrics() *ShardedMetrics {
	sm := &ShardedMetrics{}
	for i := 0; i < ShardCount; i++ {
		sm.shards[i] = &Shard{}
	}
	return sm
}

func (sm *ShardedMetrics) Add(key uint64, val uint64) {
	// FNV hash ring distribution
	shardIdx := key % ShardCount
	shard := sm.shards[shardIdx]

	shard.mu.Lock()
	shard.total += val
	shard.mu.Unlock()
}

func (sm *ShardedMetrics) ReadTotal() uint64 {
	var total uint64
	for i := 0; i < ShardCount; i++ {
		sm.shards[i].mu.Lock()
		total += sm.shards[i].total
		sm.shards[i].mu.Unlock()
	}
	return total
}

func main() {
	// Menjalankan diagnostic pprof server di port internal terisolasi (Security Isolation)
	go func() {
		diagServer := &http.Server{
			Addr:         "127.0.0.1:6060",
			ReadTimeout:  5 * time.Second,
			WriteTimeout: 60 * time.Second, // Timeout panjang untuk pprof heap/cpu dump
		}
		if err := diagServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			fmt.Printf("Diagnostic server error: %v\n", err)
		}
	}()

	metrics := NewShardedMetrics()
	stopChan := make(chan os.Signal, 1)
	signal.Notify(stopChan, os.Interrupt, syscall.SIGTERM)

	// Simulasi Pipeline Ingesti Konkuren
	ctx, cancel := context.WithCancel(context.Background())
	workerCount := 16
	var wg sync.WaitGroup

	for i := 0; i < workerCount; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			processIngress(ctx, workerID, metrics)
		}(i)
	}

	fmt.Println("Ingestion Engine berjalan optimal. Profile siap di http://127.0.0.1:6060/debug/pprof/")
	<-stopChan
	fmt.Println("Menghentikan sistem...")

	cancel()
	wg.Wait()

	fmt.Printf("Total Nilai Transaksi Terproses: %d\n", metrics.ReadTotal())
}

// processIngress mengeksekusi streaming data tanpa alokasi heap baru di per-loop
func processIngress(ctx context.Context, id int, metrics *ShardedMetrics) {
	// Buffer frame lokal untuk parsing
	rawStream := make([]byte, 64)
	binary.BigEndian.PutUint64(rawStream[0:8], uint64(id+1000))
	binary.BigEndian.PutUint64(rawStream[8:16], uint64(time.Now().UnixNano()))

	for {
		select {
		case <-ctx.Done():
			return
		default:
			// Ambil objek dari pool (Memory Reuse)
			payload := payloadPool.Get().(*IngestionPayload)

			// Zero-Copy deserialization manual dari buffer biner langsung ke struct field
			payload.ID = binary.BigEndian.Uint64(rawStream[0:8])
			payload.Timestamp = int64(binary.BigEndian.Uint64(rawStream[8:16]))
			copy(payload.Metadata[:], rawStream[24:64])

			// Update sharded metric dengan alokasi 0
			metrics.Add(payload.ID, 1)

			// Bersihkan objek sebelum dikembalikan ke pool (Pembersihan state)
			*payload = IngestionPayload{}
			payloadPool.Put(payload)

			// Kompensasi laju throttle microsecond untuk stabilitas simulasi
			time.Sleep(100 * time.Nanosecond)
		}
	}
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Matrix Karakteristik Performa Toolchain Go

| Dimensi | CPU Profiling (`pprof`) | Heap Profiling (`pprof`) | Execution Tracer (`trace`) | Benchmark Profiling (`go test -bench`) |
| :--- | :--- | :--- | :--- | :--- |
| **Metode Koleksi** | Statistical Sampling (100Hz SIGPROF) | Byte Allocation Counter (~512KB interval) | Deterministic Event Tracing via P-buffer | Statistical Iteration Loop + Timer |
| **Runtime Overhead** | Rendah (~1% - 3% degradasi throughput) | Sangat Rendah (< 1% overhead CPU) | Menengah - Tinggi (Beban I/O & CPU 5% - 15%) | Sangat Tinggi (Isolasi buatan, no concurrent traffic) |
| **Akurasi Resolusi** | Makro/Statistik (Call-stack aggregates) | Agregat Volume Byte & Hitungan Objek | Mikro/Deterministik (Nanosecond timing per event) | Siklus per Operasi (ns/op, B/op, allocs/op) |
| **Penggunaan Ideal** | Menemukan algoritma CPU-bound (panas) | Menemukan Memory Leaks & Objek Bloat | Menganalisis Concurrency, GC STW, Contention | Memverifikasi optimasi kode secara terisolasi |
| **Output File Size** | Kecil (Kilobytes - Megabytes) | Kecil (Umumnya < 10 MB) | Sangat Besar (Ratusan MB per menit tracing) | Teks log terminal murni |
| **Kesesuaian di Produksi** | **Aman Digunakan Kontinu** | **Aman Digunakan Kontinu** | **Gunakan Pendek (1-5 detik saja)** | **Tidak Berlaku di Produksi** |

### Trade-off Teknis: Object Pooling (`sync.Pool`) vs Garbage Collector
* **Kelebihan `sync.Pool`**: Mengeliminasi panggilan alokasi heap baru, mengurangi laju pemuatan GC, menekan lonjakan latensi tail P99/P999.
* **Biaya/Kerugian `sync.Pool`**:
  * Peningkatan kompleksitas kode (keharusan pembersihan status / *zeroing struct* secara manual; risiko kebocoran data sensitif antar thread jika lupa di-clear).
  * Memori dalam pool tetap di-*evict* secara otomatis oleh runtime ketika siklus 2x GC berjalan tanpa aktivitas, sehingga tidak cocok untuk cache jangka panjang (*cache durability* nol).

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Sampling Bias & The Nyquist-Shannon Sampling Problem
Jika suatu fungsi komputasi secara presisi dieksekusi setiap 10ms dan durasinya hanya 1ms, dan timer sinyal CPU sampling runtime (`ITIMER_PROF`) juga berosilasi pada interval 10ms yang sinkron dengan clock tersebut, ada kemungkinan besar sinyal sampling **selalu meleset** dari fungsi tersebut atau **selalu mengenainya**. Hasil CPU profile akan terdistorsi (bisa nol persen atau 100% dari total waktu).

### 2. Inlining Bias pada Compiler
Kompilator Go menginjeksi kode fungsi yang kecil secara langsung ke dalam caller (*inlining*). Saat Anda menganalisis output `go tool pprof`, fungsi tersebut mungkin tidak muncul sama sekali di graph call stack, membuat pemula mengira fungsi tersebut tidak dieksekusi.
* Solusi Diagnostik: Analisis binary dengan flag compiler dinonaktifkan (`-gcflags="-l"` untuk mematikan inlining) HANYA untuk eksperimen profiling lokal:
  ```bash
  go test -gcflags="-l" -bench=. -cpuprofile=cpu.pprof
  ```

### 3. Profiling Cgo & Kernel Boundaries
Runtime `pprof` Go **tidak dapat menelusuri** (*unwind*) stack frame internal kode assembly C pihak ketiga (Cgo) atau context switch internal syscall kernel secara transparan. Jika fungsi C mengalami deadlock atau sleep tanpa melepaskan kontrol thread Go via scheduler, `pprof` akan melaporkan thread tersebut menganggur (*idle*) atau stack trace terputus di fungsi perantara `runtime.cgocall`.

### 4. Overzealous Tracing Ukuran File
Mengaktifkan execution tracing (`trace.Start`) di bawah beban produksi 100.000 QPS selama lebih dari 5 detik dapat menghasilkan file trace sebesar beberapa gigabyte. Membuka file ini di browser menggunakan `go tool trace` akan menyebabkan peramban (Chrome) mengalami crash akibat konsumsi memori browser yang melampaui 4GB (V8 heap limit).

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Membuka Endpoint Profiling ke Publik Tanpa Autentikasi
* **Pola Buruk**: Menulis `import _ "net/http/pprof"` dan mendaftarkan route HTTP server aplikasi langsung pada port ingress publik (misal: `:8080`).
* **Dampak Keamanan**: Penyerang dapat mengunduh memory heap dump (`/debug/pprof/heap`), yang berisi token JWT, kredensial basis data plaintext, data privasi pengguna, atau memicu DoS dengan mengunduh trace durasi panjang secara simultan.
* **Perbaikan Arsitektur**: Daftarkan router `pprof` hanya pada loopback address lokal (`127.0.0.1:6060`), atau pisahkan total HTTP mux internal dengan middleware otentikasi ketat (Mutual TLS / Internal Admin Subnet).

### 2. Terkecoh Antara `alloc_space` vs `inuse_space`
* **Kesalahan Interpretasi**: Pengembang melihat grafik heap profile dan panik karena ada fungsi yang menggunakan 20 GB memori. Namun, yang mereka lihat adalah `alloc_space` (total akumulatif yang pernah dialokasikan sejak boot aplikasi), bukan `inuse_space` (memori yang saat ini ditahan).
* **Solusi Perbaikan**: Gunakan flag spesifik saat membedah heap:
  ```bash
  go tool pprof -sample_index=inuse_space http://localhost:6060/debug/pprof/heap
  ```
  Gunakan `alloc_space` untuk menekan alokasi GC rate; gunakan `inuse_space` untuk menemukan memory leak fisik.

### 3. Mengukur Microbenchmark yang Tidak Stabil (Benchmarking Pitfall)
* **Pola Buruk**: Mengukur fungsi dengan alokasi memori tanpa mengatur `b.ResetTimer()` setelah tahap setup, atau membiarkan compiler mengeliminasi kode akibat *Dead Code Elimination*.
* **Solusi**: Pastikan hasil return fungsi di-*assign* ke package-level global sink:
  ```go
  var GlobalResult any

  func BenchmarkOptimizedFunc(b *testing.B) {
      b.ReportAllocs()
      var localResult any
      b.ResetTimer()
      for i := 0; i < b.N; i++ {
          localResult = HeavyCompute()
      }
      GlobalResult = localResult // Mencegah dead code elimination oleh compiler!
  }
  ```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan `benchstat` untuk Validasi Statistik**:
   Jangan pernah menyimpulkan optimasi performa hanya dari satu kali run `go test -bench`. Jalankan benchmark minimal 10 kali (`-count=10`) sebelum dan sesudah perubahan kode, lalu bandingkan distribusinya secara statistik menggunakan tool resmi Go `benchstat`:
   ```bash
   go test -bench=BenchmarkProcess -count=10 > old.txt
   # Lakukan optimasi pada kode sumber
   go test -bench=BenchmarkProcess -count=10 > new.txt
   benchstat old.txt new.txt
   ```
   Hanya terima optimasi jika p-value $< 0.05$ (secara statistik signifikan, bukan noise OS).

2. **Continuous Profiling di Tingkat Produksi**:
   Alih-alih profiling manual saat sistem sudah terlanjur *down*, terapkan Continuous Profiling di armada kluster Anda menggunakan open-source engine seperti **Pyroscope** atau **Parca**. Continuous profiler mengambil data sampel profil pprof sebesar 1-2% overhead secara berkala dan memadukannya ke dalam time-series flame graph.

3. **Verifikasi Keputusan Compiler via Escape Analysis Flags**:
   Gunakan feedback langsung dari compiler Go saat mengompilasi kode untuk memverifikasi apakah struct lolos ke heap:
   ```bash
   go build -gcflags="-m -m" ./cmd/app/ 2>&1 | grep "escapes to heap"
   ```

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Slice Pre-Allocation (Eliminasi Pertumbuhan Dinamis)
Saat slice Go tumbuh melebihi kapasitasnya via `append`, runtime memicu alokasi array pendukung baru berkapasitas $2\times$ lipat (atau $1.25\times$ pada ukuran besar), menyalin elemen lama ke lokasi baru, dan membuang array lama ke heap.
```go
// BURUK: Menghasilkan log2(N) alokasi heap berulang & overhead GC
res := make([]int, 0)
for i := 0; i < 10000; i++ {
    res = append(res, i)
}

// OPTIMAL: 1x alokasi heap tunggal dengan kapasitas pasti
res := make([]int, 0, 10000)
for i := 0; i < 10000; i++ {
    res = append(res, i)
}
```

### 2. Cache Line Padding untuk Struktur Terkontensi
Ketika mendesain struktur sinkronisasi tingkat tinggi, pisahkan variabel yang sering diubah oleh goroutine konkuren yang berbeda agar tidak berbagi cache line 64-byte yang sama:
```go
import "golang.org/x/sys/cpu"

type HighThroughputCounter struct {
    readCounter  uint64
    _            cpu.CacheLinePad // Memastikan margin 64 bytes
    writeCounter uint64
    _            cpu.CacheLinePad
}
```

### 3. Mengurangi Pointer pada Heap Data Structures
Garbage collector Go memindai setiap pointer pada heap untuk menandai objek hidup. Semakin banyak pointer (misal: `map[string]*User` vs `map[uint64]User`), semakin lama fase Mark STW/Assist berlangsung.
* Buat struktur data tanpa pointer (*pointer-free data structures*). Runtime Go mengoptimalkan pemindaian memori: jika sebuah slice atau block heap tidak mengandung pointer fisik (hanya integer murni, float, byte array), garbage collector melewati (*skip scan*) blok memori tersebut secara total.

---

# SEKSI 16 — KEAMANAN & HARDENING

Mengaktifkan fitur diagnostik runtime pada software production membawa implikasi keamanan tingkat tinggi:

### 1. Memory Dumping Exfiltration
Endpoint `/debug/pprof/heap` dan `/debug/pprof/goroutine` mengekstrak representasi stack pointer dan snapshot buffer. Jika memory leak terjadi di stack yang memuat enkripsi private key, plain password, atau data PII (Personally Identifiable Information), penyerang yang dapat mengakses endpoint tersebut dapat merekonstruksi data sensitif dari dump file biner.

### 2. Denial of Service via Resource Exhaustion
Endpoint `/debug/pprof/profile?seconds=60` memaksa runtime untuk menyalakan signal handler frekuensi tinggi. Jika 50 request profiling dieksekusi simultan oleh adversary, CPU server akan habis termakan oleh profiling interrupt overhead itu sendiri, mengakibatkan *cascading failure* sistem.

### 3. Implementasi Isolasi Standar Produksi
Pisahkan multiplexer profiling sepenuhnya dari internet facing router menggunakan custom server pattern:

```go
package main

import (
	"net/http"
	"net/http/pprof"
)

// NewDiagnosticMux membuat HTTP ServeMux terisolasi khusus administrasi internal
func NewDiagnosticMux() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/debug/pprof/", pprof.Index)
	mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
	mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
	mux.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
	mux.HandleFunc("/debug/pprof/trace", pprof.Trace)
	mux.HandleFunc("/debug/pprof/heap", pprof.Handler("heap").ServeHTTP)
	mux.HandleFunc("/debug/pprof/goroutine", pprof.Handler("goroutine").ServeHTTP)
	mux.HandleFunc("/debug/pprof/block", pprof.Handler("block").ServeHTTP)
	mux.HandleFunc("/debug/pprof/mutex", pprof.Handler("mutex").ServeHTTP)
	return mux
}

func StartAdminServer(bindAddr string) *http.Server {
	return &http.Server{
		Addr:    bindAddr, // Wajib di-bind ke internal interface, misal: "127.0.0.1:9099" atau IP VPC Private
		Handler: NewDiagnosticMux(),
	}
}
```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Profiling ad-hoc harus diselaraskan dengan telemetry pipeline modern:

### 1. Profiler Labels untuk Korelasi Distributed Tracing (OpenTelemetry)
Anda dapat memetakan context OpenTelemetry Span ID ke dalam runtime Go pprof label. Dengan cara ini, sampel CPU profiling yang ditangkap runtime dapat disaring spesifik untuk transaksi pelanggan tertentu (*Trace Context Correlation*):

```go
import (
	"context"
	"runtime/pprof"
	"go.opentelemetry.io/otel/trace"
)

func InstrumentWithPprof(ctx context.Context, span trace.Span, fn func(context.Context)) {
	spanCtx := span.SpanContext()
	labels := pprof.Labels(
		"trace_id", spanCtx.TraceID().String(),
		"span_id", spanCtx.SpanID().String(),
	)
	
	pprof.Do(ctx, labels, func(labeledCtx context.Context) {
		fn(labeledCtx)
	})
}
```

### 2. Runtime Metrics Introspection (`runtime/metrics`)
Sejak Go 1.16+, paket `runtime/metrics` menyediakan interface berbiaya sangat rendah untuk membaca status internal engine Go secara terstruktur (menggantikan `runtime.ReadMemStats` yang memerlukan penghentian STW singkat):

```go
package main

import (
	"fmt"
	"runtime/metrics"
)

func ReadEngineTelemetry() {
	const (
		gcCyclesMetric    = "/gc/cycles/total:gc-cycles"
		heapInUseMetric   = "/memory/classes/heap/objects:bytes"
		goroutinesMetric  = "/sched/goroutines:goroutines"
	)

	samples := make([]metrics.Sample, 3)
	samples[0].Name = gcCyclesMetric
	samples[1].Name = heapInUseMetric
	samples[2].Name = goroutinesMetric

	// Pembacaan instan tanpa alokasi & tanpa STW
	metrics.Read(samples)

	for _, sample := range samples {
		name := sample.Name
		switch sample.Value.Kind() {
		case metrics.KindUint64:
			fmt.Printf("%s: %d\n", name, sample.Value.Uint64())
		case metrics.KindFloat64:
			fmt.Printf("%s: %f\n", name, sample.Value.Float64())
		}
	}
}
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### CLI Quick Reference

```bash
# 1. Menjalankan interaktif CLI CPU analysis via HTTP
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

# 2. Menjalankan interaktif Web UI Flamegraph untuk Heap
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/heap

# 3. Menganalisis alokasi akumulatif (mencari alokator terbesar)
go tool pprof -sample_index=alloc_space http://localhost:6060/debug/pprof/allocs

# 4. Menganalisis Goroutine Dump (mendeteksi goroutine leak)
go tool pprof http://localhost:6060/debug/pprof/goroutine

# 5. Mengunduh dan visualisasi Execution Trace
curl -o trace.out http://localhost:6060/debug/pprof/trace?seconds=5
go tool trace trace.out

# 6. Menjalankan benchmark mikro dengan alokasi memori
go test -run=^$ -bench=. -benchmem -memprofile=mem.pprof -cpuprofile=cpu.pprof

# 7. Memeriksa escape analysis keputusan compiler
go build -gcflags="-m -l" .
```

### Navigasi Interaktif dalam Shell `go tool pprof`

* `top [N]`: Menampilkan $N$ baris fungsi teratas yang mengonsumsi sumber daya (Flat vs Cum).
* `list <NamaFungsiRegex>`: Menampilkan disassembly kode sumber fungsi baris demi baris beserta konsumsi latensi/memori di samping baris kode.
* `web`: Mengekspor graf relasi panggilan ke file SVG dan membukanya di browser (memerlukan instalasi Graphviz).
* `peek <NamaFungsi>`: Menampilkan pemanggil (*callers*) dan fungsi yang dipanggil (*callees*) dari target.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah satu jawaban yang paling tepat dan pelajari pembahasannya!

### Soal Basic (1 - 5)

**1. Bagaimana runtime Go mengumpulkan data CPU Profile selama eksekusi program?**
* A. Menggunakan code injection pada saat kompilasi ke setiap statement.
* B. Interupsi sinyal kernel OS periodik (`SIGPROF`) pada interval 10ms dan melakukan stack unwinding.
* C. Membaca counter register perangkat keras CPU terus-menerus dalam perulangan tak terbatas.
* D. Menghentikan program setiap milidetik menggunakan mekanik Stop-The-World.
* *Kunci Jawaban: B*
* *Pembahasan*: Go mengonfigurasi timer kernel OS (`setitimer`) untuk memancarkan sinyal `SIGPROF` (~100Hz). Sinyal ini menginterupsi eksekusi thread normal, lalu runtime menjalankan fungsi internal `gentraceback` untuk membaca stack pointer goroutine yang berjalan saat sinyal tiba.

**2. Apa perbedaan paling fundamental antara metrik profiling `inuse_space` dan `alloc_space` pada heap profile?**
* A. `inuse_space` mencatat memori yang dialokasikan di stack, sedangkan `alloc_space` memori di heap.
* B. `inuse_space` mencatat snapshot memori heap yang masih ditahan dan belum dibebaskan; `alloc_space` mencatat total kumulatif seluruh alokasi sejak proses hidup.
* C. `inuse_space` adalah memori RAM fisik, sedangkan `alloc_space` adalah swap disk memory.
* D. `alloc_space` digunakan untuk memantau data Cgo, sedangkan `inuse_space` murni untuk objek runtime Go.
* *Kunci Jawaban: B*
* *Pembahasan*: `alloc_space` merekam total akumulasi semua alokasi (sangat cocok untuk melacak penghasil sampah GC), sedangkan `inuse_space` hanya merefleksikan alokasi yang saat ini masih hidup di heap (cocok untuk investigasi kebocoran memori).

**3. Manakah perintah CLI yang benar untuk membuka visualisasi Execution Trace interaktif di antarmuka web?**
* A. `go tool pprof --trace trace.out`
* B. `go tool trace -http=:8080 trace.out` (atau `go tool trace trace.out`)
* C. `go trace view trace.out`
* D. `go test -trace=trace.out`
* *Kunci Jawaban: B*
* *Pembahasan*: Tool terintegrasi Go untuk melihat trace file biner adalah `go tool trace <file>`, yang memicu web server lokal dan merender graphical scheduler visualization via peramban web.

**4. Apa implikasi terhadap Garbage Collection jika sebuah struct berukuran 10 MB dialokasikan ke Heap dan memiliki ribuan pointer di dalamnya dibandingkan dengan struct tanpa pointer?**
* A. Tidak ada perbedaan karena ukuran memorinya sama persis (10 MB).
* B. GC Mark phase akan membutuhkan waktu jauh lebih lama pada struct dengan ribuan pointer karena GC harus menelusuri setiap pointer address secara rekursif.
* C. Struct tanpa pointer akan langsung dialokasikan ke stack secara otomatis.
* D. Struct dengan pointer akan membuat memory leak permanen secara otomatis.
* *Kunci Jawaban: B*
* *Pembahasan*: Fase penandaan (Marking phase) pada GC bertugas melacak graf keterjangkauan pointer (*pointer reachability*). Semakin banyak pointer yang tersimpan pada objek heap, semakin banyak dereferensi yang harus dilakukan GC worker, memicu overhead CPU dan potensi Mark Assist.

**5. Mengapa mengekspos `net/http/pprof` secara terbuka di port produksi publik dianggap sebagai kerentanan keamanan kritis?**
* A. Karena pprof memungkinkan injeksi script cross-site scripting (XSS).
* B. Karena penyerang dapat membaca heap dump yang berpotensi mengekspos token, kredensial, data sensitif memori, atau memicu DoS melalui trace request panjang.
* C. Karena modul pprof secara otomatis mematikan proteksi firewall Linux.
* D. Karena pprof menghentikan seluruh goroutine secara permanen ketika diakses.
* *Kunci Jawaban: B*
* *Pembahasan*: Profiler mengekstrak status internal proses. Heap dump berisi dump memori yang dapat dibaca kembali untuk mengekstraksi rahasia plaintext, dan endpoint trace dapat memicu kehabisan CPU serta I/O disk jika diserang secara simultan.

---

### Soal Intermediate (6 - 10)

**6. Anda menganalisis grafik trace Go (`go tool trace`) dan menemukan blok waktu panjang di mana goroutine aplikasi berubah status menjadi "Waiting" dengan event deskripsi "GC Mark Assist". Apa akar permasalahan dari kondisi ini?**
* A. Terjadi kebocoran memori pada Cgo subsystem.
* B. Thread OS kekurangan virtual memory sehingga swap drive aktif.
* C. Laju goroutine mengalokasikan memori melampaui kemampuan background GC worker menyapu objek, sehingga runtime membajak goroutine untuk membantu proses scanning pointer.
* D. Mutex contention mengalami deadlock mutual exclusion.
* *Kunci Jawaban: C*
* *Pembahasan*: Pacer GC runtime mendeteksi laju alokasi aplikasi (*allocation rate*) melebihi batas target sebelum sweep deadline. Untuk mencegah OOM, goroutine yang sedang mencoba mengalokasikan heap dialihkan tugasnya oleh runtime untuk melakukan pemindaian objek pointer (*Mark Assist*).

**7. Apa dampak fenomena "False Sharing" pada arsitektur multi-core modern dan bagaimana cara mendeteksinya dalam kode Go?**
* A. Goroutine memanggil fungsi recursive tanpa batas; dideteksi dengan pprof goroutine count.
* B. Dua core CPU memodifikasi dua variabel berbeda yang berada di dalam 64-byte Cache Line yang sama, memicu invalidasi cache berulang melalui bus CPU; dimitigasi dengan memory padding.
* C. Pemasangan mutex secara redundan di dua package berbeda; dideteksi dengan flag `-race`.
* D. Kesalahan data race akibat channel ditutup dua kali; dideteksi dengan error panic runtime.
* *Kunci Jawaban: B*
* *Pembahasan*: False sharing adalah masalah arsitektur hardware di mana dua variabel independen terletak di cache line yang sama (biasanya 64 bytes). Modifikasi pada satu variabel membatalkan seluruh cache line pada core lain, menurunkan throughput secara masif.

**8. Perhatikan potongan kode berikut:**
```go
func createBuffer() []byte {
    buf := make([]byte, 1024)
    return buf
}
```
**Mengapa slice `buf` di atas lolos (*escapes*) ke Heap menurut analisis Escape Analysis kompilator Go?**
* A. Karena ukurannya melebihi ambang batas ukuran stack Linux (8 MB).
* B. Karena tipe byte tidak didukung oleh arsitektur stack frame Go.
* C. Karena referensi memori data array pendukung slice dikembalikan melampaui frame eksekusi fungsi `createBuffer()`, sehingga stack frame tersebut tidak valid lagi setelah fungsi return.
* D. Karena kompilator Go tidak mendukung pengembalian slice pointer secara direct.
* *Kunci Jawaban: C*
* *Pembahasan*: Nilai kembali fungsi merujuk ke blok memori yang dialokasikan di dalam fungsi tersebut. Jika dialokasikan pada stack frame `createBuffer`, memori itu akan tertimpa saat fungsi selesai dan stack diputar kembali. Oleh karena itu, compiler memindahkannya ke Heap (*escapes to heap*).

**9. Kapan Anda sebaiknya memilih menggunakan Execution Tracer (`go tool trace`) daripada CPU Profiling (`go tool pprof`)?**
* A. Ketika Anda ingin mengidentifikasi fungsi matematika murni yang mengonsumsi kalkulasi floating point terlama.
* B. Ketika Anda ingin memantau performa aplikasi selama 7 hari berturut-turut di server produksi.
* C. Ketika Anda mendeteksi isu latensi tail (misal: P99 latency spikes) yang disebabkan oleh network polling, lock contention, atau penjadwalan goroutine (desynchronization), bukan oleh komputasi CPU intensif.
* D. Ketika Anda ingin membandingkan dua algoritma komparasi string via benchmark loop.
* *Kunci Jawaban: C*
* *Pembahasan*: CPU Profiling hanya menunjukkan konsumsi CPU agregat. Jika masalahnya adalah latensi di mana CPU justru 0% (karena goroutine terblokir pada channel, lock, atau menunggu scheduler mengalokasikan Processor P), pprof tidak memberikan konteks urutan temporal. Tracing memberikan timeline mikroskopis kapan thread berhenti dan mengapa.

**10. Manakah metodologi yang benar saat menggunakan library `sync.Pool` untuk menghindari kebocoran memori atau bug inkonsistensi data logis?**
* A. Menyimpan pointer objek ke dalam pool, dan mengabaikan state isi objek saat diambil kembali via `.Get()`.
* B. Memanggil `runtime.GC()` manual segera setelah melakukan `pool.Put(obj)`.
* C. Melakukan reset nilai struct (zeroing fields) atau membersihkan slice length (`slice = slice[:0]`) sebelum atau sesaat setelah mengambil/mengembalikan objek ke pool.
* D. Menggunakan `sync.Pool` untuk menyimpan koneksi basis data TCP persisten jangka panjang.
* *Kunci Jawaban: C*
* *Pembahasan*: Objek di dalam `sync.Pool` digunakan kembali lintas goroutine. Jika data lama tidak dibersihkan (*zeroing*), field dari request transaksi sebelumnya dapat bocor ke transaksi berikutnya. Selain itu, `sync.Pool` membersihkan seluruh isinya saat GC berjalan, sehingga tidak cocok untuk objek koneksi TCP permanen.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Diagnostic & Remediation Lab: The High-Latency Pipeline"

### Deskripsi Skenario
Anda bertindak sebagai Staff Performance Engineer pada sistem pemrosesan stream log real-time. Tim Anda mewarisi layanan ingestion yang performanya sangat buruk: hanya mampu memproses 2.000 log events/detik sebelum CPU server mencapai 100% dan latensi melonjak drastis. Target engineering kuartal ini adalah mengoptimasi engine tersebut agar mampu mencapai **100.000 log events/detik** pada spesifikasi hardware yang sama dengan alokasi heap mendekati **0 byte per operasi**.

### Langkah Pengerjaan Lab Praktikum

#### Langkah 1: Eksperimen Kode Baseline yang Bermasalah
Buat direktori baru bernama `remediation-lab` dan tulis file `main_flawed_test.go`:

```go
package main

import (
	"crypto/sha256"
	"fmt"
	"strconv"
	"strings"
	"testing"
)

// FlawedProcessor mendemonstrasikan anti-pattern alokasi dan string concatenation masif
type FlawedProcessor struct{}

func (fp *FlawedProcessor) ProcessLog(rawLog string) string {
	// 1. Alokasi heap berlebihan via strings.Split
	parts := strings.Split(rawLog, "|")
	if len(parts) < 3 {
		return ""
	}

	// 2. Alokasi string parsing berulang
	timestamp, _ := strconv.ParseInt(parts[0], 10, 64)
	level := strings.ToUpper(parts[1])
	message := parts[2]

	// 3. String concatenation via fmt.Sprintf (Escape analysis killer)
	transformed := fmt.Sprintf("TS=%d;LVL=%s;MSG=%s", timestamp, level, message)

	// 4. Komputasi hash yang memicu alokasi heap baru setiap panggilan
	hasher := sha256.New()
	hasher.Write([]byte(transformed))
	hashResult := fmt.Sprintf("%x", hasher.Sum(nil))

	return hashResult
}

func BenchmarkFlawedProcessor(b *testing.B) {
	processor := &FlawedProcessor{}
	sampleLog := "1710000000|info|koneksi database berhasil dibuka pada cluster prod-db-01"

	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = processor.ProcessLog(sampleLog)
	}
}
```

Jalankan profil diagnostik awal:
```bash
go test -bench=BenchmarkFlawedProcessor -benchmem -cpuprofile=cpu_old.pprof -memprofile=mem_old.pprof
```
*Catat metrik awal: Berapa ns/op? Berapa B/op? Berapa allocs/op?*

#### Langkah 2: Analisis Profiling
1. Masuk ke interactive pprof mode:
   ```bash
   go tool pprof -top mem_old.pprof
   ```
2. Identifikasi baris kode yang memicu `alloc_space` tertinggi menggunakan perintah:
   ```text
   (pprof) list ProcessLog
   ```
3. Periksa keputusan compiler escape analysis:
   ```bash
   go build -gcflags="-m" main_flawed_test.go
   ```

#### Langkah 3: Rekayasa Optimasi (Tugas Anda)
Rancang struktur `OptimizedProcessor` yang memenuhi kriteria berikut:
1. **Zero String Splitting Allocation**: Gunakan `bytes.IndexByte` atau slice slicing langsung pada byte slice (`[]byte`) alih-alih `strings.Split`.
2. **Eliminasi `fmt.Sprintf`**: Gunakan buffer writer berbasis scratch-buffer lokal atau `sync.Pool` yang menggunakan byte buffer (`[]byte`).
3. **Optimasi State Cryptographic Hash**: Alih-alih membuat instance hasher baru via `sha256.New()` di setiap iterasi loop (yang mengalokasikan struct cipher ke heap), gunakan teknik hashing langsung pada array stack atau reuse instance hasher menggunakan `hasher.Reset()`.
4. **Zero-Alloc Target**: Capai performa:
   * **Allocations: 0 allocs/op**
   * **Allocated Bytes: 0 B/op**
   * **Latensi: Reduksi durasi ns/op minimal 80% dibanding baseline**.

#### Langkah 4: Validasi Statistik dengan `benchstat`
1. Tulis fungsi `BenchmarkOptimizedProcessor` dalam file benchmark yang sama.
2. Jalankan komparasi 10 siklus pengujian:
   ```bash
   go test -bench=BenchmarkFlawedProcessor -count=10 > baseline.txt
   go test -bench=BenchmarkOptimizedProcessor -count=10 > optimized.txt
   benchstat baseline.txt optimized.txt
   ```
3. Pastikan output `benchstat` membuktikan penurunan alokasi memori sebesar **-100.00%** dengan tingkat signifikansi statistik valid ($p < 0.05$).