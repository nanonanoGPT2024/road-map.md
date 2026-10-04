# BAB 09: Observabilitas, Telemetri & Real-Time Profiling
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis (Analyze)** dampak overhead telemetri (CPU cycles, memory footprint, cache misses, dan GC pauses) pada loop simulasi game server berfrekuensi tinggi (*high-tick rate* $\ge 60\text{ Hz}$).
- **Merancang (Design)** arsitektur observabilitas terdistribusi *zero-allocation* dan *out-of-band* yang mengintegrasikan OpenTelemetry, Continuous Profiling (eBPF/pprof), dan metrics pipeline untuk sistem AI otonom serta dedicated game server (DGS).
- **Mengimplementasikan (Implement)** injeksi dan ekstraksi konteks *distributed tracing* W3C TraceContext ke dalam paket biner kustom UDP/WebSocket tanpa degradasi throughput jaringan.
- **Mengevaluasi (Evaluate)** anomali performa server (*tick budget exhaustion*, micro-stutters, thread contention) menggunakan flame graph continuous profiling dan metrik performa AI agent (*behavior tree / utility AI tick cost*).

---

### 2. Prerequisites
Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Arsitektur Dedicated Game Server (DGS)**: Siklus *fixed-timestep game loop*, state synchronization, dan model thread per-room/per-match.
- **Sistem AI Server-Side**: Konsep dasar *Behavior Trees*, *Utility AI*, *NavMesh Pathfinding*, dan dynamic agent spawning.
- **Bahasa Pemrograman Tingkat Sistem**: Go atau Rust/C++ (pada modul ini kode implementasi menggunakan Go tingkat lanjut dengan idiom *zero-allocation* dan manipulasi unsafe/binary pointers).
- **Dasar Jaringan Game**: Protokol transport UDP, framing biner, MTU budget, dan paket serialisasi (Protobuf/FlatBuffers).

---

### 3. Concept & Internal Architecture

Menjalankan observabilitas pada server web stateless berbasis HTTP sangat berbeda dengan dedicated game server (DGS) stateful. Pada web server biasa, penambahan latensi 2ms akibat pembuatan span OpenTelemetry masih dapat ditoleransi. Namun, pada DGS dengan *tick rate* 60 Hz, seluruh simulasi dunia (fisika, interaksi pemain, evaluasi state AI, dan replikasi jaringan) harus selesai dalam **16.66 milidetik** (*tick budget*). Jika telemetri mengonsumsi 2ms, Anda membuang $12\%$ dari total komputasi tick.

```
       +--------------------------------------------------------------+
       |                  TICK BUDGET: 16.66 ms (60 Hz)               |
       +-------------------+--------------------+---------------------+
       | Physics & Spatial | AI & Agent Routing | Net Sync & Snapshot |
       |     (~5.0 ms)     |     (~6.5 ms)      |      (~3.5 ms)      |
       +-------------------+--------------------+---------------------+
                                                       ^
                                            Sisa Budget: ~1.66 ms
                     (Overhead Telemetri HARUS <= 0.1 ms / < 1% CPU Core)
```

#### A. Lock-Free Zero-Allocation Telemetry Pipeline
Untuk mengeliminasi *thread contention* dan alokasi heap dinamis yang memicu Garbage Collection (GC) pauses pada game loop:
1. **Thread-Local Ring Buffers**: Game tick thread tidak pernah langsung mem-push metrik atau span melalui jaringan (I/O). Telemetri ditulis ke ring buffer sirkular lokal thread secara atomik (*lock-free single-producer single-consumer / SPSC*).
2. **Out-of-Band Background Exporter**: Thread pekerja latar belakang (*background worker*) secara periodik mendrainase buffer menggunakan instruksi batch biner dan mengirimkannya ke OpenTelemetry Collector atau Prometheus Pushgateway via shared memory atau Unix Domain Socket (UDS).

#### B. Continuous Profiling Engine (eBPF & Sampling Profiler)
Tracing berbasis span memberikan gambaran *kapan* dan *di mana* sebuah request berlangsung, namun tidak dapat menjelaskan mengapa algoritma *NavMesh pathfinding* tiba-tiba mengalami *CPU stall*. Continuous profiling (misal: Pyroscope/Parca) bekerja pada level kernel melalui eBPF atau signal sampling (`SIGPROF` pada Go/POSIX). Profiler mengambil *call stack snapshot* 100 kali per detik ($100\text{ Hz}$) tanpa menginterupsi alur kritis game server, menghasilkan agregasi Flame Graph secara real-time.

#### C. Trace Context Injection pada Frame Biner UDP
Dedicated Game Server berkomunikasi menggunakan UDP biner mentah. Tidak ada header HTTP untuk membawa `traceparent` W3C. Arsitektur produksi mewajibkan bit-packing Trace Context (16-byte TraceID + 8-byte SpanID + 1-byte TraceFlags = 25 bytes) ke dalam struktur header UDP paket kontrol permainan, atau menggunakan skema korelasi *Tick-Indexed Trace Correlation* di mana Trace Context hanya dikirimkan saat *handshake* dan dikaitkan dengan `TickNumber` biner 32-bit.

---

### 4. Why & What

| Dimensi | Observabilitas Web Tradisional | Observabilitas Dedicated Game Server (DGS) & AI |
| :--- | :--- | :--- |
| **Model Eksekusi** | Request-Response I/O Bound | Tight Loop CPU/Memory-Bound ($16.66\text{ ms}$ fixed loop) |
| **Toleransi Overhead** | Latensi $\le 10-20\text{ ms}$ wajar | Budget telemetri $\le 100\ \mu\text{s}$ ($0.1\text{ ms}$), 0 heap allocation |
| **Protokol Transport** | HTTP/1.1, HTTP/2, gRPC | Raw UDP, KCP, WebSockets, Protobuf/FlatBuffers |
| **State Tracking** | Stateless / External DB | In-Memory World State, Spatial Grid, Local AI Context |
| **Kegagalan Utama** | Error rate 5xx, Latency spike HTTP | Desynchronization, Tick Drop, Pathfinding Starvation |

---

### 5. How (Workflow Detail)

Alur kerja telemetri real-time skala produksi:

```
[ Game Loop Thread (Tick 60Hz) ]
   │
   ├─► 1. Tick Start (Timestamp t0)
   │
   ├─► 2. AI Subsystem Update (Tick AI Agents)
   │     ├─ Trace Sample Decision? (Deterministic Hash / Modulo Tick)
   │     └─ Record Delta: Write to SPSC Lock-Free Ring Buffer (Zero-Alloc)
   │
   ├─► 3. Spatial Simulation & Network Serialization
   │     └─ Inject TraceContext (25 bytes) ke Binary Header Packet (Snapshot/StateSync)
   │
   ├─► 4. Tick End (Timestamp t1) -> Record TickDuration Metric
   │
[ Shared Memory / Lock-Free Ring Buffer ]
   │
   ▼
[ Telemetry Drain Worker Thread (Asynchronous, Core Terisolasi) ]
   │
   ├─► Agregasi Metrik (Batching)
   ├─► OTel Protocol (OTLP) Encode via FlatBuffers/Protobuf
   └─► Kirim via Unix Domain Socket (UDS) -> [ OTel Collector Agent ]
                                                   │
                                                   ├─► Prometheus / M3DB (Metrics)
                                                   ├─► Jaeger / Tempo (Traces)
                                                   └─► Pyroscope / Parca (Profiles)
```

---

### 6. Analogy & Diagram ASCII

Bayangkan DGS seperti **Mobil Balap Formula 1**.
- **Web App Tradisional** seperti truk kargo: Menambah sensor seberat 10 kg (overhead tracing) tidak mempengaruhi operasional harian pengiriman barang.
- **High-Tick Game Server** adalah mobil F1: Setiap miligram dan hambatan aerodinamis sangat berpengaruh. Menaruh komputer telemetri berat langsung di setir pembalap (sinkron dalam game loop) akan menyebabkan mobil oleng (tick drop).
- **Solusi**: Pasang sensor mikroskopis berkecepatan tinggi yang mengirim data via radio frekuensi khusus ke kru pit di pinggir trek (Ring Buffer ke Worker Thread terisolasi).

```
+---------------------------------------------------------------------------------------+
| DEDICATED GAME SERVER RUNTIME MEMORY ARCHITECTURE                                     |
|                                                                                       |
|  +----------------------------------------------------+                               |
|  | GAME SIMULATION CORE (Core 1-3)                    |                               |
|  |                                                    |                               |
|  |  +----------------------------------------------+  |                               |
|  |  | Main Simulation Loop                         |  |                               |
|  |  |                                              |  |                               |
|  |  |  for range ticker.C {                        |  |                               |
|  |  |      UpdateAI();                             |  |                               |
|  |  |      TelemetryRing.Push(metricData); --------+--+-----------+                   |
|  |  |  }                                           |  |           |                   |
|  |  +----------------------------------------------+  |           |                   |
|  +----------------------------------------------------+           |                   |
|                                                                   v                   |
|  +----------------------------------------------------+   +-----------------------+   |
|  | TELEMETRY EXPORTER WORKER (Core 4 - Isolated)      |   | Lock-Free SPSC Ring   |   |
|  |                                                    |   | Buffer (Cache-Aligned)|   |
|  |   DrainQueue() <-----------------------------------+---+                       |   |
|  |      │                                             |   +-----------------------+   |
|  |      ▼                                             |                               |
|  |   Encode OTLP (Protobuf)                           |                               |
|  |      │                                             |                               |
|  |      ▼                                             |                               |
|  |   UDS Socket Write (/var/run/otel.sock)            |                               |
|  +----------------------------------------------------+                               |
+---------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Enterprise Example

#### A. Kode Sederhana (Konseptual): Zero-Allocation High-Precision Tick Watchdog
Contoh bagaimana mencatat latensi loop tanpa alokasi heap via `time.Duration`.

```go
package main

import (
	"fmt"
	"time"
)

type TickWatchdog struct {
	targetDuration time.Duration
	warnThreshold  time.Duration
}

func (w *TickWatchdog) ValidateTick(start, end time.Time, tickNumber uint64) {
	delta := end.Sub(start)
	if delta > w.warnThreshold {
		// Logika minimal: hindari fmt.Printf di loop kritis produksi!
		fmt.Printf("[CRITICAL TICK DROP] Tick: %d exceeded budget! Took: %v\n", tickNumber, delta)
	}
}

func main() {
	watchdog := TickWatchdog{
		targetDuration: 16666 * time.Microsecond, // 60Hz = ~16.66ms
		warnThreshold:  15000 * time.Microsecond,
	}
	t0 := time.Now()
	// Simulasi komputasi
	time.Sleep(16 * time.Millisecond)
	t1 := time.Now()
	watchdog.ValidateTick(t0, t1, 1024)
}
```

#### B. Implementasi Produksi: Lock-Free SPSC Telemetry Ring Buffer & Binary UDP Trace Propagator

Implementasi nyata tingkat enterprise dalam Go:
1. Zero-Allocation SPSC (Single Producer Single Consumer) Ring Buffer dengan *cache line padding* untuk menghindari *false sharing*.
2. Binary Trace Context Injector/Extractor untuk UDP Packet Game State Sync.

```go
package main

import (
	"encoding/binary"
	"errors"
	"fmt"
	"sync/atomic"
	"time"
	"unsafe"
)

// =======================================================================
// 1. CACHE-ALIGNED ZERO-ALLOCATION SPSC RING BUFFER
// =======================================================================

const RingBufferSize = 65536 // Harus bernilai 2^n untuk masking bitwise cepat

// MetricEvent merepresentasikan rekaman eksekusi subsystem AI
type MetricEvent struct {
	TickNumber   uint64
	SubsystemID  uint16
	DurationNano uint32
	AgentCount   uint16
	Flags        uint8
	_pad         [1]byte // Align ke 16-byte boundary
}

// SPSCRingBuffer mengimplementasikan antrian thread-safe tanpa lock
// untuk komunikasi antara thread game loop dan background exporter.
type SPSCRingBuffer struct {
	// Head ditulis oleh Producer (Game Loop), dibaca oleh Consumer
	head uint64
	_pad0 [56]byte // 64 - 8 byte = 56 byte padding (Mencegah False Sharing pada CPU Cache L1/L2)

	// Tail ditulis oleh Consumer (Worker), dibaca oleh Producer
	tail uint64
	_pad1 [56]byte

	buffer [RingBufferSize]MetricEvent
}

func NewSPSCRingBuffer() *SPSCRingBuffer {
	return &SPSCRingBuffer{}
}

// Push memasukkan event dari game loop. Mengembalikan false jika buffer penuh (drop-oldest/backpressure).
// Sifat: Non-blocking, Zero Heap Allocation.
func (rb *SPSCRingBuffer) Push(event MetricEvent) bool {
	head := atomic.LoadUint64(&rb.head)
	tail := atomic.LoadUint64(&rb.tail)

	// Jika buffer penuh (jarak head dan tail sama dengan ukuran buffer)
	if (head - tail) >= RingBufferSize {
		return false // Buffer penuh, drop metrik demi menjaga integritas loop
	}

	rb.buffer[head&(RingBufferSize-1)] = event
	atomic.StoreUint64(&rb.head, head+1)
	return true
}

// Pop mengambil event dari exporter background thread.
func (rb *SPSCRingBuffer) Pop() (MetricEvent, bool) {
	tail := atomic.LoadUint64(&rb.tail)
	head := atomic.LoadUint64(&rb.head)

	if tail == head {
		return MetricEvent{}, false // Buffer kosong
	}

	event := rb.buffer[tail&(RingBufferSize-1)]
	atomic.StoreUint64(&rb.tail, tail+1)
	return event, true
}

// =======================================================================
// 2. BINARY UDP TRACE PROPAGATION (W3C TraceContext In Raw Bytes)
// =======================================================================

// W3CTraceBinary merepresentasikan 25-byte standar header tracing terdistribusi
// TraceID: 16 bytes, SpanID: 8 bytes, Flags: 1 byte
type W3CTraceBinary struct {
	TraceID [16]byte
	SpanID  [8]byte
	Flags   byte
}

const BinaryTraceSize = 25

var (
	ErrBufferTooSmall = errors.New("buffer UDP tidak cukup besar untuk inject/extract trace")
)

// InjectTraceContext menyisipkan Trace Context ke offset awal buffer UDP
// Menggunakan unsafe pointer casts / binary encoding zero allocation
func InjectTraceContext(trace W3CTraceBinary, dest []byte) error {
	if len(dest) < BinaryTraceSize {
		return ErrBufferTooSmall
	}

	copy(dest[0:16], trace.TraceID[:])
	copy(dest[16:24], trace.SpanID[:])
	dest[24] = trace.Flags

	return nil
}

// ExtractTraceContext mengekstrak konteks distributed trace dari paket jaringan masuk
func ExtractTraceContext(src []byte) (W3CTraceBinary, error) {
	var trace W3CTraceBinary
	if len(src) < BinaryTraceSize {
		return trace, ErrBufferTooSmall
	}

	copy(trace.TraceID[:], src[0:16])
	copy(trace.SpanID[:], src[16:24])
	trace.Flags = src[24]

	return trace, nil
}

// =======================================================================
// 3. GAME RUNTIME EXECUTION SIMULATION
// =======================================================================

func main() {
	fmt.Printf("[SYSTEM] Starting High-Performance DGS Telemetry Runtime...\n")
	fmt.Printf("[SYSTEM] MetricEvent Memory Size: %d bytes\n", unsafe.Sizeof(MetricEvent{}))

	ringBuffer := NewSPSCRingBuffer()
	done := make(chan bool)

	// Background Exporter Worker (Out-of-band CPU Worker)
	go func() {
		var drainCount uint64
		ticker := time.NewTicker(50 * time.Millisecond)
		defer ticker.Stop()

		for {
			select {
			case <-done:
				fmt.Printf("[EXPORTER] Finalized. Total telemetri terproses: %d\n", drainCount)
				return
			default:
				event, ok := ringBuffer.Pop()
				if ok {
					drainCount++
					if drainCount%1000 == 0 {
						fmt.Printf("[EXPORTER] Processed batch up to tick: %d, Subsystem: %d, Duration: %dns\n",
							event.TickNumber, event.SubsystemID, event.DurationNano)
					}
				} else {
					// Yield processor to avoid 100% spin in worker
					time.Sleep(100 * time.Microsecond)
				}
			}
		}
	}()

	// Simulasi Main Game Loop (60 Hz -> 16.66ms per tick)
	targetTickDuration := 16666 * time.Nanosecond
	totalSimulationTicks := uint64(5000)

	fmt.Printf("[MAIN] Memulai Game Loop Simulasi (%d ticks)...\n", totalSimulationTicks)
	for tick := uint64(1); tick <= totalSimulationTicks; tick++ {
		t0 := time.Now()

		// 1. Simulasi Evaluasi Behavior Tree AI
		// Simulasi latensi AI processing 2-4ms
		agentCount := uint16(128)
		aiProcessingDuration := uint32(2_500_000) // 2.5 ms dalam nanodetik

		// 2. Kirim metrik ke Lock-Free Ring Buffer (Out-of-Band)
		ev := MetricEvent{
			TickNumber:   tick,
			SubsystemID:  1, // 1 = BehaviorTree AI
			DurationNano: aiProcessingDuration,
			AgentCount:   agentCount,
			Flags:        0x01,
		}
		
		if !ringBuffer.Push(ev) {
			// Buffer overflow handling: di produksi, increment atomic counter 'telemetry_dropped_total'
		}

		// 3. Simulasi Serialization State Update dengan Distributed Trace Context
		udpPayload := make([]byte, 128) // Buffer UDP state packet
		mockTrace := W3CTraceBinary{
			TraceID: [16]byte{0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10},
			SpanID:  [8]byte{0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22},
			Flags:   0x01, // Sampled
		}
		
		_ = InjectTraceContext(mockTrace, udpPayload)

		// Ekstraksi verifikasi pada sisi penerima (Client / Proxy Gateway)
		extractedTrace, _ := ExtractTraceContext(udpPayload)
		if tick == 1 {
			fmt.Printf("[NET] UDP Trace Context Berhasil Diinjeksi & Diekstrak. TraceID Prefix: %x\n", extractedTrace.TraceID[0:4])
		}

		elapsed := time.Since(t0)
		if elapsed < time.Duration(targetTickDuration) {
			// Jaga fixed-timestep
			time.Sleep(time.Duration(targetTickDuration) - elapsed)
		}
	}

	time.Sleep(100 * time.Millisecond)
	done <- true
	fmt.Printf("[SYSTEM] Game Server Loop Shutdown cleanly.\n")
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: "The Phantom 45-Hz Degrade" pada Battle Royale 100-Player DGS
- **Konteks**: Dedicated server game survival Battle Royale skala besar (100 pemain per match, 400 AI NPC bots per instance) mengalami degradasi tick rate dari 60 Hz menjadi 42–45 Hz setiap kali permainan memasuki zona lingkaran ke-4 (*mid-game circle*).
- **Gejala**: Metrik rata-rata CPU penggunaan hanya $68\%$, tidak ada saturasi bandwidth jaringan, namun pemain melaporkan *rubber-banding* dan tembakan yang tidak teregistrasi (*hit registration drop*).
- **Investigasi Telemetri Konvensional**: Grafana Prometheus hanya menunjukkan latensi tick rata-rata naik ke $23\text{ ms}$. Tidak ada detail subsystem mana yang bertanggung jawab karena span OpenTelemetry konvensional dinonaktifkan di level produksi akibat overhead alokasi memori.
- **Implementasi Diagnostik Lanjutan**:
  1. Tim mengaktifkan **Continuous Profiling eBPF (Pyroscope)** pada 5 node server canary di cluster Kubernetes (Agones).
  2. Mengimplementasikan SPSC Lock-Free Ring Buffer untuk menangkap metrik per-subsystem AI (`NavMesh`, `BehaviorTree`, `PerceptionSystem`).
- **Akar Masalah (Root Cause)**:
  Flame Graph Pyroscope memperlihatkan $41\%$ CPU cycle terkonsentrasi pada fungsi `spatial.QueryRaycast()` yang dipanggil oleh `PerceptionSystem` milik AI NPC. Ketika zona menyusut, kepadatan bot meningkat drastis di area grid yang sama. Setiap bot mengevaluasi line-of-sight ke bot lain secara kuadratik $O(N^2)$, memicu lock contention pada pointer struktur Octree dunia simulasi.
- **Solusi Arsitektur**:
  1. Mengganti query Octree sinkron dengan *Time-Sliced Batched Raycasting* terdistribusi (maksimal 50 raycasts per tick).
  2. Menerapkan adaptive sampling telemetri: Jika sisa tick budget $< 2\text{ ms}$, bot perception updates ditunda (*throttled*) ke tick berikutnya.
- **Hasil**: Tick rate stabil di $60.02\text{ Hz}$ sepanjang pertandingan, CPU overhead telemetri terpangkas dari $4.2\%$ menjadi $0.18\%$.

---

### 9. Trade-offs

```
                  FIDELITY / RESOLUTION
                           ▲
                           │        * Full OTel Tracing per Tick
                           │          (Terlalu Lambat untuk DGS 60Hz)
                           │
                           │   * Adaptive Sampling + Ring Buffer
                           │     (Optimal Production Balance)
                           │
                           │
       * eBPF Kernel       │
         Sampling Profiling│
                           │
                           └──────────────────────────────► PERFORMANCE
                 Low CPU Overhead             High CPU Cost
```

| Pendekatan | Keuntungan | Kerugian & Batasan | Mitigasi Desain |
| :--- | :--- | :--- | :--- |
| **In-Band Tracing (Direct OTel Span per Tick)** | Visibilitas end-to-end lengkap, relasi dependensi jelas di APM. | Alokasi heap tinggi memicu GC pauses; latensi I/O dapat membekukan game loop. | Gunakan hanya di lingkungan Local Integration Test / QA Canary. |
| **Out-of-Band Ring Buffering (Metrik Custom)** | Overhead CPU mendekati nol ($<0.1\%$), deterministik, zero allocation. | Data span individual tidak memiliki context tree hirarkis yang kaya. | Gunakan bit-flags biner padat dan lakukan rekonstruksi konteks di sisi Collector. |
| **Continuous Profiling (eBPF)** | Menganalisis CPU stall, cache misses, dan lock contention hingga level assembly kernel. | Data bersifat statistik/sampling, tidak merepresentasikan satu tick spesifik secara diskret. | Korelasikan *Flame Graph* dengan lonjakan *Tick Duration Metric* via grafana overlay. |
| **Binary Context Injection pada UDP** | Propagation konteks trace melintasi jaringan tanpa parsing teks HTTP. | Mengonsumsi 25-byte dari MTU budget paket UDP game ($1200-1400$ bytes). | Terapkan delta compression atau kirim trace ID hanya pada paket frame sinkronisasi penting. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Melakukan Alokasi Memori Dinamis di dalam Subsystem Tick
- **Kesalahan**: Menggunakan `fmt.Sprintf()`, membuat slice dinamis, atau menginisialisasi map di dalam fungsi telemetri per-tick.
- **Dampak**: Memicu alokasi heap jutaan objek per detik, memicu *Go Stop-The-World (STW) GC Pause* atau memicu fragmentasi memori pada C++.
- **Solusi**: Alokasikan *pre-allocated flat arrays* atau ring buffer statis sejak fase inisialisasi server.

#### 2. False Sharing pada Ring Buffer Concurrency
- **Kesalahan**: Menempatkan variabel pointer `head` dan `tail` berdampingan di memori struct tanpa padding.
- **Dampak**: Core CPU produser dan core CPU konsumer memperebutkan baris *L1/L2 Cache Line* (64 byte) yang sama (*cache bounce*), menurunkan throughput hingga $80\%$.
- **Solusi**: Sisipkan padding byte array `_pad [56]byte` di antara variabel `head` dan `tail` agar keduanya berada pada cache line yang terisolasi.

#### 3. Blocking I/O saat Flush Telemetri
- **Kesalahan**: Melakukan transmisi socket TCP/HTTP secara sinkron ketika flush batch telemetri gagal atau buffer penuh.
- **Dampak**: Seluruh frame rate server anjlok ke 0 fps (game server freeze) selama I/O timeout berlangsung.
- **Solusi**: Desain buffer dengan mekanisme *Drop Oldest on Overflow* non-blocking dan laporkan counter metrik drop secara terpisah.

---

### 11. Best Practices (Production Checklist)

- [ ] **Tick Budget Allocation**: Batasi telemetri maksimal $\le 0.2\text{ ms}$ per tick pada server 60 Hz.
- [ ] **Zero Heap Allocation**: Buktikan telemetri loop kritis menghasilkan $0\text{ B/op}$ via Go benchmark (`go test -benchmem`).
- [ ] **CPU Cache Isolation**: Struktur data telemetri concurrent dilindungi dengan padding 64-byte untuk menghindari CPU cache line contention.
- [ ] **Out-of-Band Offloading**: Seluruh serialisasi OTLP dan I/O jaringan dijalankan pada core CPU dedicated yang terpisah dari thread game simulation.
- [ ] **Transport Protocol Efficiency**: Gunakan Unix Domain Socket (UDS) atau FlatBuffers biner untuk transmisi telemetri lokal ke host collector daemon.
- [ ] **Deterministic Dynamic Sampling**: Sampling span distributed tracing dikendalikan oleh modulus Tick Number (misal: hanya sample $1$ tick setiap $120$ ticks, kecuali jika durasi tick melampaui ambang batas $16.66\text{ ms}$).
- [ ] **Graceful Degradation**: Matikan telemetri non-esensial secara otomatis jika game server mendeteksi thermal throttling atau CPU usage $> 90\%$.

---

### 12. Hands-on Practice

Buat dan simpan file-file berikut di folder `hands-on/m02/` untuk membangun pipeline validasi performa tick game server.

#### Langkah 1: Buat file implementasi Ring Buffer
Simpan kode berikut sebagai `hands-on/m02/ringbuffer.go`:
```go
package main

import (
	"sync/atomic"
)

const BufferSize = 1024

type TelemetryPayload struct {
	TickID    uint64
	Subsystem uint8
	ExecNanos uint32
}

type FastTelemetryBuffer struct {
	head uint64
	_pad0 [56]byte
	tail uint64
	_pad1 [56]byte
	data [BufferSize]TelemetryPayload
}

func NewFastBuffer() *FastTelemetryBuffer {
	return &FastTelemetryBuffer{}
}

func (b *FastTelemetryBuffer) TryPush(p TelemetryPayload) bool {
	head := atomic.LoadUint64(&b.head)
	tail := atomic.LoadUint64(&b.tail)

	if (head - tail) >= BufferSize {
		return false
	}

	b.data[head&(BufferSize-1)] = p
	atomic.StoreUint64(&b.head, head+1)
	return true
}

func (b *FastTelemetryBuffer) TryPop() (TelemetryPayload, bool) {
	tail := atomic.LoadUint64(&b.tail)
	head := atomic.LoadUint64(&b.head)

	if tail == head {
		return TelemetryPayload{}, false
	}

	p := b.data[tail&(BufferSize-1)]
	atomic.StoreUint64(&b.tail, tail+1)
	return p, true
}
```

#### Langkah 2: Buat unit benchmark untuk memverifikasi alokasi
Simpan kode berikut sebagai `hands-on/m02/ringbuffer_test.go`:
```go
package main

import (
	"testing"
)

func BenchmarkBufferPushNoAlloc(b *testing.B) {
	buf := NewFastBuffer()
	payload := TelemetryPayload{
		TickID:    100,
		Subsystem: 2,
		ExecNanos: 125000,
	}

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		if !buf.TryPush(payload) {
			// Drain if full to keep benchmark loop running
			buf.TryPop()
		}
	}
}
```

#### Langkah 3: Eksekusi pengujian
Jalankan di terminal Anda:
```bash
cd hands-on/m02/
go test -bench=. -benchmem
```
*Pastikan output menunjukkan `0 B/op` dan `0 allocs/op`.*

---

### 13. Exercise

#### Level Easy
Ubah implementasi `MetricEvent` pada kode contoh seksi 7 agar mendukung pelaporan status *Memory Fragmentation* (tambahkan flag bitmask 8-bit untuk merepresentasikan *spatial chunk allocation status*) tanpa mengubah alignment memori struct melebihi 24 byte.

#### Level Medium
Buat modul evaluator `TickBudgetGuard` yang memonitor persentase waktu yang dihabiskan oleh Subsystem AI. Jika dalam 5 tick berturut-turut durasi evaluasi AI melebihi $40\%$ dari total budget $16.66\text{ ms}$, sistem harus memicu event `AI_LOD_DEGRADE` untuk menurunkan frekuensi evaluasi bot NPC secara otomatis.

#### Level Hard
Implementasikan custom OpenTelemetry Exporter di Go yang membaca data langsung dari memory ring buffer yang telah kita bangun, mengonversi data menjadi format Wire Protocol OTLP/gRPC tanpa alokasi objek per-item menggunakan memory pooling (`sync.Pool`), dan menembakkannya ke OpenTelemetry Collector lokal.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Server Architect untuk game MMO aksi serempak. Server Anda menampung 500 AI Agent terdistribusi pada dynamic grid NavMesh yang disimulasikan pada tick rate 60 Hz.
Pada saat pertempuran massal (*siege event*), beberapa match mengalami *catastrophic tick starvation* (tick rate terjun bebas ke 12 Hz selama 4 detik, lalu kembali ke normal). Namun, log error standar kosong dan metrik agregat 1 menit Prometheus tidak mendeteksi anomali karena diratakan oleh interval sampling (*scraping averaging*).

**Tugas Anda**:
1. Rancang arsitektur telemetri yang mampu mendeteksi dan mengisolasi insiden *micro-stall* dengan resolusi sub-detik (per-frame level) tanpa meningkatkan penggunaan CPU lebih dari $0.5\%$.
2. Gambarkan diagram topologi pemrosesan data telemetri dari CPU core eksekusi hingga storage backend.
3. Tentukan mekanisme *Dynamic Trace Triggering*: bagaimana cara server secara retrospektif menyimpan snapshot memori eksekusi 30 frame terakhir HANYA saat micro-stall terdeteksi?

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. Berapa batas waktu maksimum (budget) satu game tick pada game server yang berjalan pada target frekuensi 60 Hz?
2. Mengapa penggunaan library distributed tracing standar HTTP (seperti middleware OTel biasa) dilarang keras di dalam simulation loop dedicated game server?
3. Apa fungsi penyisipan padding byte (misal: `[56]byte`) di antara pointer atomic `head` dan `tail` pada struktur data ring buffer concurrent?
4. Apa yang dimaksud dengan continuous profiling berbasis eBPF dan apa keunggulannya dibanding tracing manual?
5. Mengapa format biner UDP game state paket memerlukan injeksi W3C TraceContext jika kita ingin mengamati alur jaringan end-to-end?

#### Intermediate (5 Pertanyaan)
6. Bagaimana cara kerja instruksi bitwise `head & (BufferSize - 1)` dalam menggantikan operasi modulo CPU (`%`) pada implementasi circular ring buffer?
7. Jelaskan fenomena *False Sharing* pada multicore CPU architecture dan dampaknya terhadap latency-sensitive game server.
8. Bagaimana strategi "Adaptive Telemetry Sampling" bekerja saat sistem AI mendeteksi sisa tick budget berada di bawah margin keamanan (misal: $<1.0\text{ ms}$)?
9. Mengapa continuous profiler berbasis sampling (misal $100\text{ Hz}$) tidak mencatat 100% eksekusi fungsi di server? Apa batas teoretisnya?
10. Sebutkan trade-off mendasar antara mengirim data metrik via UDS (Unix Domain Socket) lokal dibandingkan langsung via network socket (TCP/UDP) ke remote server backend!

#### Kasus Produksi (3 Skenario Kasus)
11. **Skenario 1**: Grafana menunjukkan metrik CPU Dedicated Game Server hanya $40\%$, namun server loop terus melaporkan *Tick Drop* (tick budget selalu terlampaui). Apa kemungkinan penyebab konkurensi di balik ini dan bagaimana telemetri tingkat lanjut membuktikannya?
12. **Skenario 2**: Setelah memasang agen continuous profiling berbasis eBPF, server game mendadak mengalami crash segmentasi memori (*kernel panic / SIGSEGV*) di lingkungan kernel Linux bare-metal. Langkah forensik apa yang harus Anda lakukan?
13. **Skenario 3**: Paket sinkronisasi game state UDP Anda memiliki MTU ketat sebesar 1200 byte. Payload state snapshot game menghabiskan 1180 byte. Bagaimana cara Anda menyisipkan distributed tracing tanpa menyebabkan paket terfragmentasi di level IP router?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Basic
1. $1000\text{ ms} / 60 = 16.66\text{ milidetik}$.
2. Karena library standar melakukan alokasi heap dinamis masif, string formatting, context locking, dan I/O sinkron yang memicu latensi tinggi dan Garbage Collection STW pauses.
3. Untuk mencegah *False Sharing*, memastikan `head` dan `tail` berada pada CPU cache line (64 byte) yang berbeda sehingga core producer dan consumer tidak saling membatalkan cache L1/L2.
4. Continuous profiling eBPF mengambil sampel call stack thread langsung dari level kernel tanpa memodifikasi kode sumber atau menghentikan eksekusi thread, dengan overhead CPU sangat rendah ($<1\%$).
5. Karena paket UDP biner murni tidak memiliki header HTTP metadata bawaan untuk melacak korelasi span antara client, edge relay server, dan backend AI simulator.

#### Intermediate
6. Operasi `AND` bitwise hanya valid jika ukuran buffer adalah eksponen 2 ($2^n$). Operasi ini hanya membutuhkan 1 CPU cycle, jauh lebih cepat dibanding instruksi divisi biner CPU (`DIV`/`IDIV`) yang membutuhkan 10-40 cycles.
7. False sharing terjadi ketika dua core CPU memodifikasi variabel independen yang kebetulan berada di cache line 64-byte yang sama. Hal ini memaksa invalidate cache lintas bus sistem berulang-ulang, menghancurkan throughput pemrosesan tick.
8. Sistem menghitung sisa waktu tick. Jika waktu tersisa mendekati ambang batas bahaya, subsystem AI secara deterministik menonaktifkan pembuatan trace mendalam dan hanya mengirimkan raw metric counter.
9. Karena sampling profiler mengambil *snapshot* pada interval diskret. Fungsi yang dieksekusi dan selesai di antara dua interval sampling (sangat cepat, misal $<10\ \mu\text{s}$) berpotensi tidak terekam dalam Flame Graph.
10. UDS menghindari overhead stack TCP/IP, checksum computation, dan routing kernel, memproses jutaan event dengan latensi sub-mikrodetik, namun dibatasi hanya untuk komunikasi lokal pada node/pod yang sama.

#### Panduan Kasus Produksi
11. **Analisis**: CPU rendah dengan tick budget terlampaui mengindikasikan adanya *Thread Blocking / Lock Contention* (misal: mutex lock saat mengakses NavMesh global, database read sinkron, atau spin-lock starvation). Gunakan off-CPU profiling atau eBPF tracepoints (`sched_switch`) untuk mengidentifikasi thread mana yang tertidur (*blocked state*) saat game tick berjalan.
12. **Analisis**: Periksa kompatibilitas versi Linux Kernel dengan hook eBPF program, periksa tracepoint BTF (BPF Type Format), dan pastikan program eBPF tidak membaca invalid kernel memory pointer. Periksa log sistem menggunakan `dmesg -T` untuk melihat stack dump kernel crash.
13. **Analisis**: Karena sisa payload hanya 20 byte sedangkan standar W3C butuh 25 byte, Anda tidak bisa menyisipkan full W3C TraceContext langsung. Solusi: Gunakan skema **Tick & Match Indexed Context Relay**. Kirim mapping TraceID 25-byte hanya sekali saat koneksi handshake (TCP/Reliable UDP). Pada paket game per-tick, cukup bawa integer ID 16-bit atau 32-bit yang memetakan snapshot tersebut ke Trace Context di sisi gateway.

---

### 16. Summary

- **Observabilitas Dedicated Game Server** menuntut paradigma performa ekstrem: alokasi heap nol (*zero-allocation*), komputasi *out-of-band*, dan overhead CPU mutlak $\le 1\%$ dari total *tick budget*.
- Pola arsitektur standar enterprise memisahkan loop kritis simulasi dari thread telemetri menggunakan struktur data **Lock-Free SPSC Ring Buffer** dengan mitigasi *cache false-sharing*.
- Tracing terdistribusi pada transmisi biner game UDP diwujudkan melalui teknik bit-packing TraceContext standar W3C atau korelasi state berbasis index frame/tick.
- Penggabungan **Continuous Profiling eBPF** dengan metrik subsystem real-time merupakan metode definitif dalam mengidentifikasi anomali performa AI seperti *pathfinding starvation* dan *micro-stutters* sebelum berdampak pada pengalaman jutaan pemain.