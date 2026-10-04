# BAB 05: Profiling, Tracing & Performance Engineering
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis (Analyze):** Mengurai runtime overhead, timer interruptions, dan event recording engine pada Go runtime execution tracer serta profiler (`pprof`).
- **Mengevaluasi (Evaluate):** Mengidentifikasi degradasi performa pada tingkat kernel-runtime interface (scheduler latency, lock contention, GC pauses, off-CPU blocking) menggunakan flamegraph dan timeline trace.
- **Mengimplementasikan (Implement):** Membangun sistem *Continuous Profiling* terdistribusi yang aman untuk lingkungan produksi dengan overhead CPU $< 2\%$.
- **Merekayasa (Create):** Merancang arsitektur profiling berbasis label (*Execution Tracer user annotations* dan *pprof labels*) untuk melacak degradasi latensi p99.9 pada layanan multi-tenant bertransaksi tinggi.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Go Runtime Fundamentals:** Model konkurensi $M:P:G$ (Machine, Processor, Goroutine) dan algoritma work-stealing scheduler.
- **Memory Management:** Mekanisme alokasi memori (Stack vs Heap, Escape Analysis), dan siklus Tri-color Mark-Sweep Garbage Collector.
- **Dasar Profiling:** Penggunaan dasar paket `net/http/pprof` dan pembacaan metrik dasar (CPU, Heap, Goroutine stack).
- **Sistem Operasi & Networking:** Pengetahuan mengenai POSIX Signals (terutama `SIGPROF`), thread context-switching, virtual memory page faults, dan protokol HTTP/gRPC.

---

### 3. Concept & Internal Architecture

#### 3.1. Mekanisme Internal Profiler Go (`runtime/pprof`)
Profiler Go beroperasi menggunakan metode *statistical sampling* (berbasis interupsi), bukan instrumentasi kode menyeluruh.

```
       +-------------------------------------------------------+
       |                  Linux Kernel Space                   |
       +-------------------------------------------------------+
          |                                                 ^
  setitimer(ITIMER_PROF)                                    |
  Interval: 10ms (100Hz)                                    |
          |                                                 |
          v                                                 |
     OS Timer fires -------------------------------+        |
          |                                        |        |
          v                                        v        |
   [Thread (M1)]                            [Thread (M2)]   |
   Receives SIGPROF                         Receives SIGPROF|
          |                                        |        |
+---------|----------------------------------------|--------|--+
|         v                                        v        |  |
|  sighandler()                             sighandler()    |  |
|         |                                        |        |  |
|  runtime.sigprof()                        runtime.sigprof()| |
|         \                                        /        |  |
|          +------------------+-------------------+         |  |
|                             |                             |  |
|                             v                             |  |
|                 Read Program Counter (PC)                 |  |
|                 Unwind Stack (Max 64 frames)              |  |
|                 Attach pprof Goroutine Labels             |  |
|                             |                             |  |
|                             v                             |  |
|               Write to Lock-Free Trace/Prof               |  |
|                      Ring Buffer                          |  |
|                             |                             |  |
|                             v                             |  |
|             Read by Profiler Consumer Goroutine           |  |
|                             |                             |  |
+-----------------------------|-----------------------------|--+
                              v                             |
                   Gzip stream over HTTP                    |
                   (e.g., /debug/pprof/profile)             |
```

1. **Inisiasi & Timer:** Saat profiling CPU dimulai via `pprof.StartCPUProfile(w)`, runtime memanggil *syscall* `setitimer(ITIMER_PROF)` (atau `timer_create` pada sistem modern). Kernel dikonfigurasi untuk mengirimkan sinyal `SIGPROF` setiap 10ms (frekuensi default 100 Hz).
2. **Sinyal Handling:** Ketika kernel mengirimkan `SIGPROF` ke OS Thread ($M$), eksekusi kode normal dihentikan sementara. Sinyal dicegat oleh fungsi `runtime.sighandler` di runtime Go.
3. **Stack Unwinding:** Runtime mengeksekusi `runtime.sigprof(pc, sp, lr, gp, mp)`. Fungsi ini mengambil *Program Counter* (PC) saat ini, menelusuri rantai pointer frame (stack unwinding hingga batas kedalaman tertentu, default 64 frame), dan merekam call chain.
4. **Context Association:** Jika Goroutine memiliki metadata (disuntikkan melalui `pprof.Labels`), runtime membaca label TLS (*Thread Local Storage*) atau Goroutine descriptor (`g`) dan memetakan sampel profil ke label konteks tersebut.
5. **Buffer Collection:** Data sampel dimasukkan ke dalam profil ring buffer internal secara thread-safe menggunakan primitif lock-free. Goroutine latar belakang kemudian membaca buffer ini, memformatnya ke format proto gzip standar (`profile.proto`), dan mengalirkannya ke output `io.Writer`.

#### 3.2. Arsitektur Eksekusi Tracer (`runtime/trace`)
Berbeda dari CPU profiler yang berbasis sampling probabilistik, **Execution Tracer** berbasis **deterministic event-driven logging**.

```
           Go Runtime Execution Tracer Architecture

   Logical Processor (P0)               Logical Processor (P1)
  +-----------------------+            +-----------------------+
  | Goroutine (G1)        |            | Goroutine (G2)        |
  | [ Event Occurs ]      |            | [ Event Occurs ]      |
  | (e.g. chan send/recv) |            | (e.g. syscall entry)  |
  +-----------+-----------+            +-----------+-----------+
              |                                    |
              v                                    v
     traceEventWriter()                   traceEventWriter()
              |                                    |
              v                                    v
  +-----------------------+            +-----------------------+
  |  Per-P Trace Buffer   |            |  Per-P Trace Buffer   |
  |  (Local Lock-Free)    |            |  (Local Lock-Free)    |
  +-----------+-----------+            +-----------+-----------+
              |                                    |
              | Buffer Full                        | Buffer Full
              v                                    v
     +--------------------------------------------------+
     |        Global Central Trace Buffer Queue         |
     |         (Protected by trace.lock Mutex)          |
     +--------------------------------------------------+
                              |
                              v
                  Trace Collector Goroutine
                              |
                              v
                    Compression (zlib)
                              |
                              v
                      Output trace.out
```

- **Per-P Local Buffering:** Menghindari contention lock global. Setiap logical processor ($P$) memiliki buffer trace privat. Event seperti `traceEvGoCreate`, `traceEvGoBlock`, `traceEvGoSched`, dan `traceEvGCStart` ditulis langsung ke buffer lokal milik $P$ aktif tanpa mutual exclusion lock.
- **Flushing:** Ketika buffer lokal penuh (umumnya 64KB), kepemilikan buffer ditransfer ke antrean global di bawah perlindungan `trace.lock`, lalu buffer baru dialokasikan ke $P$.
- **Monotonic Timestamp:** Event menggunakan pembacaan register CPU langsung (seperti RDTSC pada x86-64) untuk mendapatkan timestamp berresolusi nanodetik dengan overhead instruksi minimal.

#### 3.3. Continuous Profiling Architecture
Dalam lingkungan cloud-native modern (Kubernetes), menarik profil ad-hoc ketika insiden terjadi bersifat reaktif dan sering kali terlambat (masalah transien sudah hilang). Continuous Profiling mengumpulkan profil secara konstan dari seluruh armada server.

Terdapat dua paradigma utama:
1. **Pull-based (Agent-scraped):** Daemon (misal: Prometheus-style scraper seperti Grafana Pyroscope Agent) melakukan HTTP GET secara berkala ke endpoint `/debug/pprof/*` setiap pod. Kelemahan: Membutuhkan pembukaan port debug dan overhead scraping jaringan.
2. **Push-based / eBPF-based (Non-invasive):** Menggunakan eBPF program di kernel space untuk membaca stack traces langsung dari kernel memory tanpa memodifikasi binary, atau agen in-process yang mengirimkan batch profil via push protocol (gRPC) ke storage terpusat.

---

### 4. Why & What

| Dimensi | CPU Profiling (`pprof`) | Execution Tracing (`runtime/trace`) | Continuous Profiling |
| :--- | :--- | :--- | :--- |
| **Apa yang diukur?** | Konsumsi siklus CPU per fungsi (On-CPU time). | Timeline event, scheduling latency, GC pause, lock contention, network I/O wait (On & Off-CPU). | Profiling agregat multi-dimensi (CPU, Memory, Goroutine, Block) secara historis. |
| **Overhead** | Rendah (~1-3%). Aman untuk produksi berkelanjutan. | Moderat hingga Tinggi (~5-20% tergantung throughput event). Berbahaya jika dijalankan konstan. | Terkendali (sampling terdistribusi ~1-2%). |
| **Resolusi Data** | Statistik agregat (histogram stack trace). | Runtun waktu nanodetik per Goroutine/Processor. | Agregat temporal berkelanjutan (10 detik - menit). |
| **Kapan Digunakan?** | Optimasi algoritma, mencari hotspot CPU tinggi. | Menganalisis tail latency (p99/p99.9), Goroutine starvation, lock contention. | Investigasi regresi performa antar rilis, insiden pasca-kejadian (post-mortem). |

---

### 5. How (Diagnostic & Engineering Workflow)

Alur kerja investigasi latensi tak terduga (*latency spikes*) di produksi:

```
[Alert: Latency Spike p99.9 > 500ms]
                |
                v
Step 1: Identifikasi Komponen via Continuous Profiler
  - Periksa Flamegraph CPU vs Memory Alloc vs Block/Mutex
  - Filter berdasarkan Service & Waktu Kejadian
                |
  +-------------+-------------+
  | CPU Hotspot               | Off-CPU / Wait Time
  v                           v
Step 2A: Analisis Algoritma   Step 2B: Jalankan Targeted Execution Trace
  - Evaluasi escape analysis   - Capture 5-10 detik via API internal runtime/trace
  - Cek regex / json unmarshal - Filter event pada range waktu spike
  - Optimasi inlining         |
  +-------------+-------------+
                |
                v
Step 3: Analisis Timeline Trace
  - Periksa Scheduler Latency (G waiting in runnable state)
  - Identifikasi Stop-The-World (STW) Phase GC
  - Analisis Syscall / Network blocking
                |
                v
Step 4: Rekayasa Solusi
  - Refaktor pool objek (`sync.Pool`)
  - Konfigurasi GOGC / GOMEMLIMIT
  - Mitigasi lock contention (sharding / lock-free)
                |
                v
Step 5: Verifikasi Benchmarking & Continuous Canary
  - A/B Testing menggunakan Continuous Profiler delta views
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
- **CPU Profiler (pprof):** Seperti fotografer yang mengambil snapshot acak setiap 10 milidetik di sebuah dapur restoran cepat saji. Jika koki sering terlihat sedang memotong bawang di sebagian besar foto, dapat disimpulkan memotong bawang memakan porsi waktu kerja terbesar.
- **Execution Tracer:** Seperti kamera CCTV berkecepatan tinggi yang merekam *setiap kali* koki meletakkan pisau, membuka kulkas, menunggu wajan panas, atau tertahan karena koki lain menghalangi jalurnya. Ini mencatat waktu tunggu dan koordinasi, bukan hanya aksi kerja.

```
Execution Trace Event Serialization Buffer Pipeline:

[Goroutine G10]  ---> Event: GoBlockNet (Timestamp: 100423400) ---\
[Goroutine G10]  ---> Event: GoUnblock   (Timestamp: 100423950) ----+--> [P0 Local Buffer (64KB)]
[Goroutine G11]  ---> Event: GoSyscall   (Timestamp: 100424100) ---/            |
                                                                               | (Buffer Full)
                                                                               v
[System Mutex] <------------------------------------------------- [Acquire trace.lock]
                                                                               |
                                                                               v
                                                            [Move to Global Event Queue]
                                                                               |
                                                                               v
                                                            [Trace Consumer Thread]
                                                                               |
                                                                               v
                                                               [Compressed File: trace.out]
```

---

### 7. Simple & Practical Code Examples

#### 7.1. Contoh Dasar: Menambahkan Custom Profiling Labels
pprof labels memungkinkan pengikatan data kontekstual (seperti `tenant_id` atau `handler`) ke stack samples.

```go
package main

import (
	"context"
	"fmt"
	"math/rand"
	"os"
	"runtime/pprof"
	"time"
)

func processOrder(ctx context.Context, tenantID string) {
	// Memasukkan pprof labels ke context
	labels := pprof.Labels("tenant_id", tenantID, "operation", "crypto_validation")
	pprof.Do(ctx, labels, func(c context.Context) {
		// Pekerjaan intensif CPU yang akan diberi tag label di CPU Profile
		start := time.Now()
		acc := 0
		for time.Since(start) < 200*time.Millisecond {
			acc += rand.Intn(100)
		}
		_ = acc
	})
}

func main() {
	f, err := os.Create("cpu_labeled.pprof")
	if err != nil {
		panic(err)
	}
	defer f.Close()

	if err := pprof.StartCPUProfile(f); err != nil {
		panic(err)
	}
	defer pprof.StopCPUProfile()

	ctx := context.Background()
	// Simulasi pemrosesan paralel multi-tenant
	for i := 0; i < 5; i++ {
		go processOrder(ctx, fmt.Sprintf("tenant-00%d", i))
	}

	time.Sleep(1 * time.Second)
}
```

#### 7.2. Implementasi Lanjutan: Dynamic Production Trace Flight Recorder
Merekam trace secara terus menerus ke ring-buffer di memori, dan hanya membuangnya ke disk saat terjadi anomali latensi, mencegah pembengkakan ukuran disk dan membatasi overhead.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"runtime/trace"
	"sync"
	"sync/atomic"
	"time"
)

// FlightRecorder mengelola trace on-demand saat terdeteksi degradasi performa.
type FlightRecorder struct {
	mu         sync.Mutex
	isTracing  atomic.Bool
	outputDir  string
	stopChan   chan struct{}
}

func NewFlightRecorder(outputDir string) *FlightRecorder {
	return &FlightRecorder{
		outputDir: outputDir,
	}
}

// TriggerTrace mencatat trace selama durasi tertentu secara aman tanpa blocking caller.
func (fr *FlightRecorder) TriggerTrace(duration time.Duration, reason string) error {
	if !fr.isTracing.CompareAndSwap(false, true) {
		return errors.New("flight recorder: trace collection already in progress")
	}

	go func() {
		defer fr.isTracing.Store(false)

		filename := fmt.Sprintf("%s/trace_%s_%d.out", fr.outputDir, reason, time.Now().UnixNano())
		f, err := os.Create(filename)
		if err != nil {
			log.Printf("ERROR: gagal membuat trace file: %v", err)
			return
		}
		defer f.Close()

		log.Printf("AUDIT: Memulai emergency execution trace. Reason: %s", reason)
		if err := trace.Start(f); err != nil {
			log.Printf("ERROR: trace.Start gagal: %v", err)
			return
		}

		time.Sleep(duration)
		trace.Stop()
		log.Printf("AUDIT: Emergency execution trace selesai disimpan di %s", filename)
	}()

	return nil
}

func latencyMonitorMiddleware(recorder *FlightRecorder, threshold time.Duration, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx, task := trace.NewTask(r.Context(), "HTTPRequest:"+r.URL.Path)
		defer task.End()

		start := time.Now()
		next.ServeHTTP(w, r.WithContext(ctx))
		duration := time.Since(start)

		if duration > threshold {
			trace.Logf(ctx, "latency_warning", "request memakan waktu %v melebihi threshold %v", duration, threshold)
			_ = recorder.TriggerTrace(3*time.Second, "latency_threshold_breach")
		}
	})
}
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Kasus: P99.9 Spikes pada Sistem Settlement Pembayaran FinTech
- **Skala:** 45.000 Transaksi per Detik (TPS), terdistribusi pada cluster Kubernetes (64 Pods, 16 vCPU, 32GB RAM per pod).
- **Gejala:** Latensi rata-rata stabil pada 15ms. Namun pada p99.9, latensi melonjak tajam hingga 1.8 detik, menyebabkan *timeout cascade* pada reverse proxy.
- **Investigasi Gagal:** CPU Profiler standar (`pprof CPU`) hanya menunjukkan 45% utilisasi. Heap profile tidak menunjukkan memory leak yang signifikan.

#### Diagnosa Mendalam Menggunakan Execution Trace & Block Profiler
1. **Analisis Block & Mutex Profiling:**
   ```bash
   go tool pprof -http=:8080 http://payment-service:6060/debug/pprof/mutex
   ```
   Ditemukan adanya contention tersembunyi pada `sync.Map` global yang digunakan sebagai cache validasi sesi pedagang (*merchant session cache*).
2. **Execution Trace Analysis:**
   Saat timeline trace dibuka (`go tool trace trace.out`):
   - **Proc Graphic:** Menunjukkan *Processor Starvation*. $P$ berada pada status *idle*, sementara ratusan Goroutine antre dalam status *runnable*.
   - **User Task & GC Interaction:** Siklus Garbage Collector STW (*Sweep Termination* & *Mark Termination*) memicu de-scheduling goroutine transaksi kritis. Goroutine terperangkap dalam `runtime.park` saat mencoba menulis metrics audit secara tersinkronisasi (*synchronous channel write* tanpa buffer).

```
Timeline Trace Diagnosis:

Thread 1 [ RUNNING ] -> GC Assist Alloc ---------------> STW Pause
Thread 2 [ RUNNING ] -> Mutex Wait (Merchant Cache) ---> PARKED
Thread 3 [ RUNNING ] -> Metric Chan Push (Full) --------> PARKED
               |
               v
Result: Semua P thread lokal stalls; Request p99.9 membengkak drastis.
```

#### Solusi Arsitektural:
1. **Sharding Mutex Cache:** Mengganti cache global dengan implementasi cache sharded (32 strip partitions) berbasis hash key untuk meminimalkan contention.
2. **Lock-Free Logging & Metrics Pipeline:** Mengganti unbuffered channel dengan ring-buffer berbasis `disruptor-pattern` atau slice memory pre-allocated ber-buffer besar.
3. **GC Tuning:** Mengatur target `GOGC=200` dan mengonfigurasi `GOMEMLIMIT=26GiB` (menggunakan 80% dari total alokasi pod 32GiB) untuk meredam frekuensi siklus GC tanpa melanggar OOMKilled limit.

**Hasil Pasca-Mitigasi:**
- Latensi P99.9 turun dari **1.800ms** menjadi **32ms**.
- Total alokasi memory per request berkurang sebesar 38%.

---

### 9. Trade-offs: Analisis Komparatif

```
Overhead vs Visibility Trade-off Matrix:

High  ^
      |                                  [Execution Trace]
      |                                  - High CPU impact (~5-20%)
      |                                  - Huge storage demand
O     |                                  - Nanosecond detail
v     |
e     |                 [Block/Mutex Profiling]
r     |                 - Medium impact (~3-8%)
h     |                 - Requires sampling tuning
e     |
a     |   [Continuous CPU/Heap Profiling]
d     |   - Low overhead (< 2%)
      |   - High statistical value
Low   +------------------------------------------------------------>
      Low                                                      High
                             Observability Depth
```

| Tipe Instrumentasi | Overhead CPU | Memory Footprint | Network I/O & Disk | Rekomendasi di Lingkungan Produksi |
| :--- | :--- | :--- | :--- | :--- |
| **CPU Profiler (100Hz)** | Rendah (~1-2%) | Ring buffer kecil terisolasi | Minimal (~puluhan KB per scraping) | **Wajib:** Jalankan konstan via continuous profiling. |
| **Heap Profiler** | Hampir 0% (in-memory tracking) | Jejak memori alokasi tracked | Minimal | **Wajib:** Ekstraksi berkala (setiap 1-5 menit). |
| **Mutex / Block Profiler** | Variabel (~2-10% jika rate 1:1) | Bergantung jumlah contention | Rendah hingga Sedang | **Kondisional:** Jangan set rate 1:1. Set `runtime.SetMutexProfileFraction(5)` atau sampling acak. |
| **Execution Tracer** | Tinggi (~5-25% pada high QPS) | Sangat besar (dapat membengkak ratusan MB/detik) | Sangat Tinggi jika dialirkan mentah | **Dilarang Konstan:** Hanya aktifkan manual via trigger durasi pendek (3-10 detik). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Menjalankan Execution Tracer Secara Terbuka & Permanen di Produksi
*Gejala:* Utilisasi CPU melonjak 30%, latensi umum memburuk drastis, disk terisi penuh dalam hitungan menit hingga pod mengalami crash.
*Akar Masalah:* Trace buffer merekam setiap event scheduler. Pada service dengan throughput tinggi (ratusan ribu event/detik), overhead serialisasi data biner membebani thread runtime.
*Solusi:* Batasi runtime trace menggunakan mekanisme *Self-Limiting Circuit Breaker*: batasi maksimal snapshot 5-10 detik dengan cool-off period minimal 10 menit.

#### Kesalahan 2: Menggunakan Micro-Benchmark Tanpa Mematikan Optimasi Compiler
*Gejala:* Hasil profiling benchmark tampak mencurigakan sangat cepat ($0.2\text{ ns/op}$), fungsi alokasi kompleks seakan-akan tidak memakan memori.
*Akar Masalah:* Compiler Go mengeliminasi kode mati (*Dead Code Elimination*) dan melakukan *Inlining* secara agresif jika hasil pemanggilan fungsi tidak ditugaskan ke package-level sink.
*Solusi:* Selalu gunakan global sink variable pada testing package:

```go
var globalResult any

func BenchmarkComplexLogic(b *testing.B) {
	var r any
	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		r = executeComplexLogic()
	}
	globalResult = r // Menghindari compiler optimizations
}
```

#### Kesalahan 3: Membuka Endpoint `net/http/pprof` Tanpa Autentikasi / Network Isolation
*Gejala:* Server dieksploitasi oleh pihak luar; memory dump diekstraksi penyerang menggunakan endpoint heap profile yang membocorkan data rahasia (*PII, cryptographic keys*).
*Akar Masalah:* Penggunaan `import _ "net/http/pprof"` mengaitkan rute secara otomatis ke `http.DefaultServeMux`. Jika server HTTP aplikasi publik menggunakan default mux, endpoint pprof otomatis terbuka ke internet.
*Solusi:* Selalu inisiasi instance server pprof pada internal/private network port terpisah yang tidak terhubung dengan router publik.

---

### 11. Best Practices & Production Checklist

#### Production Readiness Checklist
- [ ] **Mux Isolation:** Endpoint debugging pprof dipisahkan ke HTTP Server internal (`localhost` atau internal VPC port saja, misal `:6060`).
- [ ] **Mutex Profiling Rate:** `runtime.SetMutexProfileFraction` dan `runtime.SetBlockProfileRate` tidak diset ke `1`. Gunakan sampling rate adaptif (misal: 1 sample per 10-100 event).
- [ ] **Context Propagation:** Seluruh trace spans dan context metadata membawa `pprof.Labels` pada batas ingress network.
- [ ] **GOMEMLIMIT Defined:** Konfigurasi `GOMEMLIMIT` diset pada 80-85% dari batas Hard Cgroup Memory Kubernetes pod untuk mencegah OOMKills.
- [ ] **Automated Continuous Profiler:** Mengintegrasikan agen non-blocking (e.g., Pyroscope, Parca) untuk menangkap degradasi performa sebelum deployment dinyatakan stabil.

#### Pola Pemisahan Port Debugging (Enterprise Pattern):
```go
func runInternalDebugServer(ctx context.Context, internalPort string) {
	mux := http.NewServeMux()
	mux.HandleFunc("/debug/pprof/", pprof.Index)
	mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
	mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
	mux.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
	mux.HandleFunc("/debug/pprof/trace", pprof.Trace)

	debugServer := &http.Server{
		Addr:         internalPort,
		Handler:      mux,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 60 * time.Second,
	}

	go func() {
		if err := debugServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Printf("Internal debug server error: %v", err)
		}
	}()

	<-ctx.Done()
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = debugServer.Shutdown(shutdownCtx)
}
```

---

### 12. Hands-on Practice: Analisis Latensi & Contention

Dalam sesi praktikum ini, Anda akan mereproduksi dan mendiagnosis masalah lock contention parah serta memory allocations menggunakan `pprof` dan `go tool trace`.

#### Struktur Direktori:
```
hands-on/m02/
├── Makefile
├── cmd/
│   └── server/
│       └── main.go
└── internal/
    └── processor/
        └── queue.go
```

#### Langkah 1: Siapkan File `internal/processor/queue.go`
```go
package processor

import (
	"sync"
	"time"
)

type WorkItem struct {
	ID        int
	Data      []byte
	CreatedAt time.Time
}

// GlobalQueue menyimpan data dengan lock contention tinggi (Anti-Pattern)
type GlobalQueue struct {
	mu    sync.Mutex
	items []WorkItem
}

func NewGlobalQueue() *GlobalQueue {
	return &GlobalQueue{
		items: make([]WorkItem, 0),
	}
}

func (q *GlobalQueue) Push(item WorkItem) {
	q.mu.Lock()
	defer q.mu.Unlock()
	
	// Simulasi pemrosesan di dalam lock (kesalahan umum)
	time.Sleep(50 * time.Microsecond)
	q.items = append(q.items, item)
}

func (q *GlobalQueue) ProcessAll() int {
	q.mu.Lock()
	defer q.mu.Unlock()

	processed := len(q.items)
	q.items = q.items[:0] // Reset slice tanpa alokasi baru
	return processed
}
```

#### Langkah 2: Siapkan File `cmd/server/main.go`
```go
package main

import (
	"context"
	"fmt"
	"math/rand"
	"net/http"
	_ "net/http/pprof" // Digunakan untuk keperluan hands-on lokal
	"os"
	"os/signal"
	"runtime"
	"syscall"
	"time"

	"hands-on/m02/internal/processor"
)

func main() {
	// Enable mutex and block profiling
	runtime.SetMutexProfileFraction(5)
	runtime.SetBlockProfileRate(1000)

	queue := processor.NewGlobalQueue()

	// Menjalankan endpoint profiling internal
	go func() {
		fmt.Println("Debug profiling server berjalan pada :6060")
		_ = http.ListenAndServe("localhost:6060", nil)
	}()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// Simulasi 50 worker goroutines memicu contention
	for i := 0; i < 50; i++ {
		go func(workerID int) {
			r := rand.New(rand.NewSource(time.Now().UnixNano()))
			for {
				select {
				case <-ctx.Done():
					return
				default:
					data := make([]byte, 1024*10) // 10KB alokasi memory terus menerus
					r.Read(data)
					queue.Push(processor.WorkItem{
						ID:        workerID,
						Data:      data,
						CreatedAt: time.Now(),
					})
					time.Sleep(time.Duration(r.Intn(2)) * time.Millisecond)
				}
			}
		}(i)
	}

	// Consumer routine
	go func() {
		for {
			select {
			case <-ctx.Done():
				return
			case <-time.After(100 * time.Millisecond):
				_ = queue.ProcessAll()
			}
		}
	}()

	fmt.Println("Simulasi beban berjalan. Tekan Ctrl+C untuk berhenti.")
	<-ctx.Done()
	fmt.Println("Menghentikan sistem...")
}
```

#### Langkah 3: Siapkan `Makefile`
```makefile
.PHONY: run profile-cpu profile-mutex trace analyze-trace

run:
	go run cmd/server/main.go

profile-cpu:
	go tool pprof -http=:8081 http://localhost:6060/debug/pprof/profile?seconds=10

profile-mutex:
	go tool pprof -http=:8082 http://localhost:6060/debug/pprof/mutex

trace:
	curl -o trace.out http://localhost:6060/debug/pprof/trace?seconds=5

analyze-trace:
	go tool trace trace.out
```

#### Panduan Eksekusi:
1. Jalankan aplikasi: `make run`
2. Pada terminal terpisah, tangkap trace selama 5 detik: `make trace`
3. Buka UI trace visualizer: `make analyze-trace`
4. Analisis grafik:
   - Akses menu **View trace**.
   - Perhatikan baris Goroutine. Temukan pola tumpukan status Goroutine yang terblokir (`sync.Mutex.Lock`).
   - Periksa bagian **Synchronization blocking profile** untuk melihat waktu tunggu agregat yang terbuang akibat fungsi `Push`.

---

### 13. Exercises

#### Level 1 - Easy: Memory Allocation Footprint Reduction
- **Soal:** Diberikan fungsi deserializer JSON yang memicu alokasi heap tinggi pada endpoint publik.
- **Tugas:** Gunakan `pprof` alloc_space vs inuse_space. Modifikasi fungsi untuk memanfaatkan `sync.Pool` atau teknik stream decoding (`json.NewDecoder`), buktikan dengan benchmark bahwa alokasi memori berkurang hingga minimal 70%.

#### Level 2 - Medium: Diagnosa Goroutine Starvation
- **Soal:** Sebuah sistem background queue mendadak berhenti memproses pesan ketika workload request HTTP eksternal meningkat tajam.
- **Tugas:** Aktifkan trace capturing dan identifikasi apakah thread runtime ($M$) tersaturasi oleh komputasi intensif tak berbatas (misal: JSON parsing tanpa yield) yang mencegah Goroutine consumer mendapatkan giliran execution time slice. Perbaiki menggunakan pembatasan konkurensi (worker pool) dan kooperatif runtime yielding (`runtime.Gosched`).

#### Level 3 - Hard: Dynamic Sampling Rate Controller
- **Soal:** Beban aplikasi web bervariasi antara siang (50.000 QPS) dan malam (500 QPS). Sampling rate profiling statis akan membuat crash pada jam sibuk atau kehilangan visibilitas pada jam sepi.
- **Tugas:** Rancang dan bangun modul Go yang secara dinamis menyesuaikan nilai `runtime.SetMutexProfileFraction` dan `runtime.SetBlockProfileRate` secara adaptif berdasarkan metrik throughput aplikasi saat itu juga (misal: menggunakan Moving Average window throughput).

---

### 14. Challenge: Automated Anomaly Flight Recorder Daemon

Rancang sistem arsitektur internal berstandar industri dengan spesifikasi teknis berikut:
- **Latar Belakang:** Aplikasi pembayaran sering mengalami lag P99.9 acak yang hanya berlangsung selama 1-2 detik tiap beberapa jam. Tim operasional tidak mungkin menangkapnya secara manual melalui web browser.
- **Tugas:** Implementasikan package independen (misal: `flightrecorder`) yang:
  1. Beroperasi sebagai background daemon tanpa membebani path kritis runtime.
  2. Memantau metrik latensi internal (rolling window p99 percentile calculation) setiap 100ms.
  3. Menggunakan circular ring-buffer in-memory untuk menyimpan data execution tracer secara aman.
  4. Begitu p99 latency melewati threshold yang ditentukan (misal: $> 250\text{ ms}$), sistem secara otomatis mengekspor 5 detik trace terakhir ke format file terkompresi lokal, dan mengirimkan notification payload ke channel webhook eksternal.
  5. Memiliki mekanisme *cooldown window* otomatis (misal: 15 menit) pasca-ekspor untuk mencegah storm trace writing saat terjadi degradasi performa berkepanjangan.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konsep Dasar (5 Soal)
1. **Berapa frekuensi default sampling CPU Profiler pada Go runtime standar, dan sinyal OS apa yang diandalkan pada arsitektur Unix?**
   - *Jawaban:* Frekuensi default adalah 100 Hz (sampel diambil setiap 10 milidetik), menggunakan sinyal OS `SIGPROF`.

2. **Apa perbedaan mendasar antara representasi metrik `alloc_space` dan `inuse_space` pada analisis Heap Profile?**
   - *Jawaban:* `alloc_space` mencatat total kumulatif memori yang telah dialokasikan sejak aplikasi mulai berjalan (termasuk yang sudah dibersihkan oleh GC), sedangkan `inuse_space` hanya mencatat memori heap aktif yang masih belum dibebaskan (saat profil diambil).

3. **Mengapa pprof labels (`pprof.Labels`) sangat penting dalam aplikasi enterprise multi-tenant?**
   - *Jawaban:* Karena memungkinkan stack trace CPU dan blocking diagregasikan berdasarkan konteks bisnis spesifik (seperti ID penyewa, nama fungsi API), bukan hanya berdasarkan simbol file dan baris kode fisik.

4. **Bagaimana cara kerja sampling profiler saat suatu thread Go terjebak dalam blocking system call (Syscall)?**
   - *Jawaban:* Timer profiling `SIGPROF` tidak menghitung waktu goroutine yang terblokir pada kernel syscall murni (off-CPU) sebagai konsumsi CPU profile; waktu blocking tersebut hanya dapat dideteksi via Block Profile atau Execution Tracer.

5. **Apa dampak langsung terhadap runtime jika memanggil `runtime.SetBlockProfileRate(1)` di lingkungan produksi?**
   - *Jawaban:* Nilai 1 memerintahkan runtime untuk merekam 100% (setiap satu event) peristiwa pemblokiran goroutine tanpa sampling, yang menimbulkan overhead performa sangat masif pada aplikasi dengan konkurensi tinggi.

#### Bagian B: Analisis Arsitektur & Intermediat (5 Soal)
6. **Mengapa Execution Tracer (`runtime/trace`) menghasilkan overhead CPU yang jauh lebih besar daripada CPU Profiler (`runtime/pprof`)?**
   - *Jawaban:* Karena execution tracer bersifat deterministik (mencatat setiap event perubahan state goroutine, P, M, GC, dan network) ke dalam ring-buffer nanodetik, bukan sampling berkala probabilistik seperti pprof.

7. **Bagaimana mekanisme *Per-P Trace Buffer* mencegah degradasi performa pada sistem multi-core saat tracing aktif?**
   - *Jawaban:* Masing-masing Logical Processor ($P$) menulis ke memory buffer lokal miliknya sendiri tanpa perlu mengunci global mutex. Global lock hanya diakuisisi sesekali saat buffer lokal sudah penuh untuk dipindahkan ke buffer sentral.

8. **Kapan kondisi di mana visualisasi Flamegraph menunjukkan flat wide top plate (datar dan lebar di bagian atas)?**
   - *Jawaban:* Menunjukkan bahwa fungsi spesifik di puncak tersebut adalah leaf-function yang secara langsung memakan persentase siklus CPU terbesar (hotspot utama), bukan karena memanggil fungsi-fungsi lain di bawahnya.

9. **Apa fungsi dari parameter `GOMEMLIMIT` yang diperkenalkan pada Go 1.19 dalam konteks Garbage Collection tuning?**
   - *Jawaban:* Memberi tahu runtime batas absolut memori sebelum GC dipaksa berjalan secara agresif, mencegah terjadinya siklus GC yang terlalu sering saat memori fisik masih melimpah, sekaligus melindungi kontainer dari Linux OOM-Killer.

10. **Mengapa pemanggilan `runtime.GC()` manual di dalam kode produksi dianggap sebagai anti-pattern yang berbahaya bagi performance engineering?**
    - *Jawaban:* Memaksa siklus Garbage Collection Stop-The-World (STW) penuh berjalan di luar jadwal heuristik runtime, mengacaukan mekanisme adaptif pacing GC dan menyebabkan lonjakan tail-latency yang parah.

#### Bagian C: Skenario Kasus Produksi (3 Soal)
11. **Skenario 1:** *Sebuah microservice melaporkan kenaikan penggunaan memori yang stabil (grafik gergaji naik terus tanpa turun) di Kubernetes hingga pod mati karena OOM (Out Of Memory). Namun, saat tim developer memeriksa `pprof inuse_space`, ukuran heap aktif hanya tercatat 200MB, padahal container limit adalah 2GB.*
    - *Pertanyaan:* Apa kemungkinan besar penyebab disparitas ini, dan tools apa yang harus digunakan untuk membuktikannya?
    - *Jawaban Analisis:* Kemungkinan terjadi memory leak di luar heap yang dikelola Go GC, seperti alokasi CGo (native C memory), thread stack leak akibat ribuan goroutine yang menggantung, memory fragmentation pada OS page allocator, atau file descriptor buffer. Solusinya: Periksa `debug/pprof/goroutine` (analisis total stack memory), periksa alokasi CGo via tool eksternal OS seperti jemalloc profiling / Valgrind, dan pantau metrik runtime `go_memstats_sys_bytes`.

12. **Skenario 2:** *Sebuah worker pipeline pemrosesan pesan Kafka menunjukkan CPU utilization rendah (~15%), tetapi throughput pemrosesan sangat lambat dan lag offset Kafka terus membengkak. Hasil CPU Profile kosong dari bottleneck yang jelas.*
    - *Pertanyaan:* Langkah diagnostik apa yang harus Anda lakukan berikutnya untuk menemukan akar masalah sistem?
    - *Jawaban Analisis:* CPU profiler tidak berguna pada kasus ini karena sistem berada dalam kondisi Off-CPU. Developer harus mengaktifkan **Block Profile** (`/debug/pprof/block`), **Mutex Profile** (`/debug/pprof/mutex`), atau menangkap 5 detik **Execution Trace**. Kemungkinan besar Goroutine terhenti menunggu response I/O synchronous, database connection pool exhaustion, channel lock berlebih, atau unbuffered channel synchronization latency.

13. **Skenario 3:** *Tim engineering mengaktifkan continuous profiling menggunakan scraping HTTP endpoint setiap 30 detik. Beberapa saat kemudian, network error connection refused terjadi di seluruh pod.*
    - *Pertanyaan:* Mengapa skenario scraping ini dapat mematikan service, dan bagaimana mitigasi arsitekturnya?
    - *Jawaban Analisis:* CPU Profiling endpoint secara default menahan request scraping selama durasi profile yang diminta (misal: profiling 30 detik memblokir 1 koneksi worker HTTP selama 30 detik). Jika scraper mengirim beberapa concurrent request atau interval antar scrape bertabrakan, pool socket internal dapat jenuh atau profiling beruntun terus mengunci runtime thread. Mitigasi: Pisahkan profil scraping ke listener terisolasi, batasi frekuensi profiling (misal: scraping 5 detik per 2 menit), atau beralih ke sampling push agent / eBPF profiler yang tidak membebani Go HTTP server.

---

### 16. Summary

1. **Profiling vs Tracing:** CPU Profiling (`runtime/pprof`) adalah instrumen berbasis **sampling probabilistik** (100Hz default) yang ideal untuk mencari hotspot efisiensi algoritma dengan overhead rendah ($<2\%$). Sebaliknya, Execution Tracing (`runtime/trace`) adalah pencatatan **event-driven deterministik** nanodetik untuk memecah masalah Off-CPU latency, scheduler starvation, dan GC pauses.
2. **Context-Aware Diagnostics:** Penggunaan `pprof.Labels` dan `trace.WithRegion` mengaitkan metrik komputasi teknis ke konteks transaksi bisnis secara transparan, memungkinkan identifikasi bottleneck multi-tenant di skala enterprise.
3. **Production Safety First:** Jangan pernah membuka endpoint pprof pada public-facing router, hindari menjalankan execution trace tanpa circuit breaker durasi pendek, dan kendalikan sampling rate pada block dan mutex profiling untuk mencegah degradasi performa yang diakibatkan oleh sistem monitoring itu sendiri.