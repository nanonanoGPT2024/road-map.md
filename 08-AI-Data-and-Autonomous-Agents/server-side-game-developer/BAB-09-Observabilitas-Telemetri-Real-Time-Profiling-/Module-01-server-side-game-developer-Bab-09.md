# Bab 09: Observabilitas, Telemetri Real-Time, & Profiling Tick

## Modul 01: Low-Overhead Agent Tick Telemetry & Performance Profiling

---

### 1. Learning Objectives (Spesifik & Terukur)
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   **Menganalisis dan Mengukur Alokasi Tick Budget**: Menguraikan *budget* eksekusi loop AI server (misal: budget 10ms pada loop 20Hz / 50ms) menjadi fase diskrit (*Perception*, *Decision/Behavior Tree*, *Steering/Movement*) dengan akurasi mikrodetik ($\mu s$).
*   **Mengimplementasikan Telemetri Nir-Alokasi (*Zero-Allocation Profiler*)**: Membangun sistem pencatatan metrik dan *trace profiling* internal menggunakan *lock-free circular ring-buffer* dan alokasi memori statis guna mencegah latensi tambahan akibat *Garbage Collection* (GC) pause.
*   **Mengintegrasikan Standar OpenTelemetry & Prometheus**: Mentransformasikan telemetri *tick phase* ke metrik dimensional tanpa mengalami ledakan kardinalitas (*cardinality explosion*).
*   **Mendeteksi dan Memitigasi *Cascading Tick Overrun***: Mengonfigurasi mekanisme proteksi *backpressure*, *dynamic phase degradation*, dan *flamegraph sampling* otomatis saat terdeteksi *tick drift* atau pelanggaran ambang batas p99 > 85% *tick budget*.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Di dalam arsitektur *authoritative game server*, loop simulasi berjalan pada frekuensi tetap (*Fixed Delta-Time* / $\Delta t$). Jika server menargetkan simulasi 20 Hz, setiap siklus (*tick*) memiliki durasi total 50 milidetik. Dalam satu siklus ini, seluruh subsistem—termasuk *Networking IO*, *Physics Resolution*, *Replication*, dan *AI/Autonomous Agents*—harus selesai dieksekusi.

```
+-----------------------------------------------------------------------+
| Total Server Tick Duration (e.g., 50ms @ 20Hz)                        |
+-------------------+----------------+-------------------+--------------+
| Networking & RPCs | Physics & Coll | AI Subsystem      | Replication  |
| (10ms)            | (15ms)         | BUDGET: MAX 15ms  | (10ms)       |
+-------------------+----------------+---------+---------+--------------+
                                               |
                     +-------------------------+------------------------+
                     | Breakdown AI Phase Budget                        |
                     +------------------+------------------+------------+
                     | Perception & Nav | Decision (BT/GOAP| Actuation  |
                     | Spatial Query    | / Utility AI)    | & Steering |
                     | (~5ms)           | (~7ms)           | (~3ms)     |
                     +------------------+------------------+------------+
```

Observabilitas pada subsistem AI menghadapi tantangan yang dikenal sebagai **The Observer Effect Paradox**: instrumentasi telemetri yang naif (seperti alokasi *string formatting*, pembuatan *heap-allocated spans*, sinkronisasi *mutex* pada *hot-path*, atau pemanggilan *I/O block*) akan memakan waktu komputasi itu sendiri. Hal ini dapat meningkatkan latensi *tick*, memicu *tick drop*, hingga menyebabkan *death spiral* (kondisi di mana server tertinggal satu frame dan mencoba mengejar frame berikutnya dengan beban yang menumpuk).

Oleh karena itu, prinsip inti observabilitas tick-based AI berfokus pada:
1.  **Deterrent of Heap Allocation**: Telemetri tidak boleh mengalokasikan objek baru di heap saat loop simulasi berjalan.
2.  **Lock-Free & Thread-Decoupled**: Pencatatan durasi fase dilakukan secara atomik ke dalam struktur data sirkular lokal, kemudian dialirkan ke sistem telemetri eksternal (Prometheus, OTel Collector) oleh *worker thread* terpisah.
3.  **Phase Breakdown Isolation**: AI harus memisahkan metrik antara *Perception* (pencarian entitas di *spatial grid*), *Evaluation* (penelusuran *Behavior Tree* / *State Machine*), dan *Actuation* (perhitungan *Raycast avoidance* & *A\* Pathfinding*).

---

### 3. Why It Matters

Pada game skala enterprise dengan ratusan hingga ribuan agen otonom (NPC, bot pertarungan, kerumunan dinamis), kegagalan performa AI jarang terdistribusi secara linear. Masalah performa kerap muncul sebagai **lonjakan ekstrim pada persentil ke-99 (p99/p99.9 latency spikes)**.

Kondisi ini umumnya dipicu oleh skenario batas (*edge cases*), seperti:
*   Sebuah granat meledak dan memaksa 200 bot melakukan kalkulasi rute (*re-pathfinding*) secara serempak di frame yang sama.
*   Pemeriksaan visibilitas (*line-of-sight*) yang meledak secara eksponensial ($O(N^2)$) saat semua agen berkumpul dalam satu ruangan sempit.

Jika tim *engine* atau server-side developer hanya mengandalkan metrik rata-rata (*average tick rate*), server terlihat sehat di angka 20 Hz, padahal pemain mengalami *rubberbanding* atau *stuttering* parah akibat lonjakan p99 yang menembus 80 milidetik. Tanpa instrumentasi bertingkat fase (*sub-tick profiling*), tim operasi tidak dapat memvalidasi apakah degradasi performa disebabkan oleh algoritma pathfinding, pembengkakan evaluasi *Behavior Tree*, atau kemacetan transmisi data ke klien.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur observabilitas tick AI memisahkan jalur eksekusi berkecepatan tinggi (*critical path*) dari jalur pelaporan data (*asynchronous egress*).

```
 +-----------------------------------------------------------------------------------+
 | GAME SERVER ENGINE THREAD (Simulation Loop)                                      |
 |                                                                                   |
 |  [Tick Start: N]                                                                  |
 |         │                                                                         |
 |         ▼                                                                         |
 |  ┌──────────────┐     Timestamp     ┌──────────────────────────────────────────┐  |
 |  │ AI Subsystem │ ────────────────> │ Fast Tick Profiler (Per-Thread / Static) │  |
 |  └──────────────┘                   └──────────────────────────────────────────┘  |
 |         │                                       │                                 |
 |         ├─► Phase 1: Spatial Perception         │ Emits TickPhaseMetrics          |
 |         │   (Query Grid, Cast Rays)             │ (Zero Heap Allocation)          |
 |         ├─► Phase 2: Logic Evaluation           ▼                                 |
 |         │   (Behavior Tree / Utility)   ┌──────────────────────────────────────┐  |
 |         └─► Phase 3: Kinematics/Steer   │ Lock-Free Circular Ring Buffer       │  |
 |                                         │ [Slot 0][Slot 1]...[Slot N]          │  |
 |  [Tick End: Capture Drift & Overrun]    └──────────────────────────────────────┘  |
 +------------------------------------------------------------│----------------------+
                                                              │ Atomic Pointer Drains
                                                              ▼
 +-----------------------------------------------------------------------------------+
 | TELEMETRY WORKER THREAD (Background Ingestion Pipeline)                           |
 |                                                                                   |
 |  ┌─────────────────────────┐                                                      |
 |  │ Ring Buffer Consumer    │                                                      |
 |  └────────────┬────────────┘                                                      |
 |               │                                                                   |
 |               ├───────────────────────────────┬───────────────────────────────┐   |
 |               ▼                               ▼                               ▼   |
 |  ┌─────────────────────────┐   ┌───────────────────────────┐   ┌──────────────┴─┐ |
 |  │ Prometheus Metrics Engine│   │ Dynamic Trace Sampler     │   │ Overrun Watch  │ |
 |  │ - Histogram: tick_phase │   │ (p99 > 85% Budget Trigger)│   │ (Dump State on │ |
 |  │ - Counter: agent_drops  │   │ Creates OpenTelemetry Spans│  │ Tick Spiral)   │ |
 |  └────────────┬────────────┘   └──────────────┬────────────┘   └────────────────┘ |
 +---------------│-------------------------------│-----------------------------------+
                 ▼                               ▼
       Prometheus Scrape (/metrics)     OTel Collector (gRPC/Protobuf)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Tick Budget Allocator & High-Resolution Sampling
Waktu tick diukur menggunakan monotonic clock native hardware (misal: `CLOCK_MONOTONIC_RAW` pada kernel Linux atau runtime CPU cycle counters via assembly). Sistem menghindari instruksi OS yang memicu *context-switch*. Durasi setiap fase disimpan sebagai integer mentah dalam representasi nanodetik:

$$\Delta t_{phase} = t_{end} - t_{start}$$

Jika $\sum_{i=1}^{m} \Delta t_{phase, i} > \text{Budget}_{\text{total}}$, profiler menandai frame tersebut sebagai **Overrun Tick** dan memicu *sampler* untuk membongkar status internal agen pada tick tersebut.

#### B. Pre-Allocated Ring Buffer & Nir-Kunci
Game loop tidak boleh menunggu *lock* metrik atau membuat string baru untuk label. Profiler menggunakan array berukuran tetap ($2^N$ untuk optimasi operasi *bitwise AND* menggantikan operasi modulo) dari struct `TickMetricsSnapshot`.

Indeks *head* diperbarui secara eksklusif oleh *Game Thread*, sedangkan indeks *tail* dibaca oleh *Telemetry Worker Thread* menggunakan operasi atomik (`atomic.LoadUint64` & `atomic.StoreUint64`). Apabila buffer penuh akibat worker telemetri tertahan, profiler engine memilih untuk mengabaikan telemetri lama (*overwrite/drop oldest*) daripada memblokir jalannya simulasi game.

#### C. Kardinalitas Rendah & Agregasi Dimensi Metrik
Alih-alih mengirimkan metrik dengan label ID entitas setiap bot (yang akan menciptakan jutaan time-series unik pada Prometheus), telemetri dikelompokkan berdasarkan **Agent Archetype**, **LOD Level (Level of Detail)**, dan **Simulation Partition/Room ID**:

*   *Bad Pattern*: `ai_tick_duration_ms{agent_id="bot_918293"}` (Kardinalitas tak terhingga $\rightarrow$ *OOM Crashes* pada Prometheus).
*   *Good Pattern*: `ai_tick_duration_ms_bucket{archetype="humanoid_soldier", lod="lod_0", phase="perception"}`.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem profiling tick AI berkinerja tinggi menggunakan bahasa **Go**. Dirancang dengan memprioritaskan alokasi heap nol pada critical path simulasi, menggunakan struktur *pre-allocated lock-free ring-buffer*, dan diekspor ke format OpenTelemetry/Prometheus-compatible.

```go
package telemetry

import (
	"context"
	"errors"
	"fmt"
	"sync/atomic"
	"time"
	"unsafe"
)

// PhaseType mendefinisikan fase diskrit dalam siklus tick AI
type PhaseType uint8

const (
	PhasePerception PhaseType = iota
	PhaseDecision
	PhaseSteering
	PhaseActuation
	PhaseCount // Sentinel value untuk ukuran array
)

func (p PhaseType) String() string {
	switch p {
	case PhasePerception:
		return "perception"
	case PhaseDecision:
		return "decision"
	case PhaseSteering:
		return "steering"
	case PhaseActuation:
		return "actuation"
	default:
		return "unknown"
	}
}

// TickSnapshot merepresentasikan data telemetri komprehensif satu siklus AI.
// Struct ini di-padding untuk mencegah fenomena False Sharing pada cache line L1/L2.
type TickSnapshot struct {
	TickIndex   uint64
	TimestampNs int64
	DurationsNs [PhaseCount]int64
	TotalTimeNs int64
	AgentCount  uint32
	BudgetNs    int64
	Overrun     bool
	_           [16]byte // Padding cache-line (64 bytes alignment alignment boundary)
}

const (
	RingBufferSize uint64 = 1024 // Wajib bernilai 2^N untuk manipulasi bitwise mask
	RingBufferMask uint64 = RingBufferSize - 1
)

var (
	ErrBufferOverflow = errors.New("telemetry buffer overflow: telemetry consumer falling behind")
)

// LockFreeTickProfiler mengelola pencatatan telemetri tick berlatensi rendah.
type LockFreeTickProfiler struct {
	buffer [RingBufferSize]TickSnapshot
	head   uint64 // Ditulis secara eksklusif oleh Game/AI Simulation Thread
	tail   uint64 // Dibaca oleh Background Telemetry Worker

	budgetNs int64
}

// NewLockFreeTickProfiler menginisialisasi profiler dengan alokasi statis di awal (zero runtime allocation).
func NewLockFreeTickProfiler(budget time.Duration) *LockFreeTickProfiler {
	return &LockFreeTickProfiler{
		budgetNs: budget.Nanoseconds(),
	}
}

// TickSession melacak siklus tick tunggal pada simulation thread.
// Tidak boleh dialokasikan di heap; gunakan nilai balik langsung (value semantics).
type TickSession struct {
	profiler   *LockFreeTickProfiler
	snapshot   TickSnapshot
	phaseStart int64
}

// StartTick memulai pengukuran frame simulasi baru.
func (p *LockFreeTickProfiler) StartTick(tickIndex uint64, agentCount uint32) TickSession {
	now := time.Now().UnixNano()
	return TickSession{
		profiler: p,
		snapshot: TickSnapshot{
			TickIndex:   tickIndex,
			TimestampNs: now,
			AgentCount:  agentCount,
			BudgetNs:    p.budgetNs,
		},
		phaseStart: now,
	}
}

// EnterPhase menandai akhir fase sebelumnya dan mencatat awal fase baru.
func (s *TickSession) EnterPhase(nextPhase PhaseType) {
	now := time.Now().UnixNano()
	dur := now - s.phaseStart
	s.phaseStart = now

	// Menentukan fase yang baru saja selesai
	if nextPhase > 0 && nextPhase <= PhaseCount {
		s.snapshot.DurationsNs[nextPhase-1] = dur
	}
}

// EndTick menutup tick, mengagregasi total waktu, memvalidasi budget, dan menulis ke ring buffer.
func (s *TickSession) EndTick() {
	now := time.Now().UnixNano()
	// Catat fase terakhir yang aktif
	s.snapshot.DurationsNs[PhaseCount-1] = now - s.phaseStart
	s.snapshot.TotalTimeNs = now - s.snapshot.TimestampNs

	if s.snapshot.TotalTimeNs > s.snapshot.BudgetNs {
		s.snapshot.Overrun = true
	}

	p := s.profiler
	head := atomic.LoadUint64(&p.head)
	slot := head & RingBufferMask

	// Menulis data snapshot ke dalam slot yang dialokasikan secara statis
	p.buffer[slot] = s.snapshot

	// Perbarui pointer head menggunakan StoreRelease semantics
	atomic.StoreUint64(&p.head, head+1)
}

// TelemetryConsumer mengekstrak metrik dari profiler dan mengekspornya ke log/OTel.
type TelemetryConsumer struct {
	profiler *LockFreeTickProfiler
	stopChan chan struct{}
}

func NewTelemetryConsumer(profiler *LockFreeTickProfiler) *TelemetryConsumer {
	return &TelemetryConsumer{
		profiler: profiler,
		stopChan: make(chan struct{}),
	}
}

// StartWorker menjalankan loop konsumsi metrik secara independen dari game simulation thread.
func (tc *TelemetryConsumer) StartWorker(ctx context.Context, flushInterval time.Duration) {
	ticker := time.NewTicker(flushInterval)
	go func() {
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-tc.stopChan:
				return
			case <-ticker.C:
				tc.drainMetrics()
			}
		}
	}()
}

func (tc *TelemetryConsumer) Stop() {
	close(tc.stopChan)
}

// drainMetrics membaca data tanpa menghentikan komputasi pada game thread.
func (tc *TelemetryConsumer) drainMetrics() {
	head := atomic.LoadUint64(&tc.profiler.head)
	tail := atomic.LoadUint64(&tc.profiler.tail)

	if tail == head {
		return // Buffer kosong, tidak ada telemetri baru
	}

	// Deteksi jika consumer tertinggal melampaui kapasitas buffer (Lap Overrun)
	if head-tail > RingBufferSize {
		// Log warning dan geser pointer tail secara paksa
		atomic.StoreUint64(&tc.profiler.tail, head-RingBufferSize)
		tail = head - RingBufferSize
	}

	for tail < head {
		slot := tail & RingBufferMask
		snapshot := tc.profiler.buffer[slot]

		// Eksekusi penanganan telemetri
		tc.processSnapshot(&snapshot)

		tail++
	}

	// Simpan tail baru
	atomic.StoreUint64(&tc.profiler.tail, tail)
}

func (tc *TelemetryConsumer) processSnapshot(s *TickSnapshot) {
	if s.Overrun {
		// Emit metric alert jika terjadi overrun pada loop simulasi
		fmt.Printf("[CRITICAL ALERT] Tick %d Budget Exceeded! Total: %.2fms, Budget: %.2fms | "+
			"Perception: %.2fms, Decision: %.2fms, Steering: %.2fms, Actuation: %.2fms, Agents: %d\n",
			s.TickIndex,
			float64(s.TotalTimeNs)/1e6,
			float64(s.BudgetNs)/1e6,
			float64(s.DurationsNs[PhasePerception])/1e6,
			float64(s.DurationsNs[PhaseDecision])/1e6,
			float64(s.DurationsNs[PhaseSteering])/1e6,
			float64(s.DurationsNs[PhaseActuation])/1e6,
			s.AgentCount,
		)
	}

	// Integrasi OTel / Prometheus metrics exporter:
	// Prometheus metrics update (mocked untuk representasi arsitektur)
	// aiTickDurationHistogram.WithLabelValues("all").Observe(float64(s.TotalTimeNs)/1e9)
	// aiPhaseDurationHistogram.WithLabelValues("perception").Observe(float64(s.DurationsNs[PhasePerception])/1e9)
}
```

---

### 7. Edge Cases & Failure Modes

#### 1. Telemetry Queue Desynchronization (Ring Lap Overwrite)
*   **Kondisi**: Worker telemetri terblokir oleh I/O OS (misalnya *network degradation* saat flushing spans ke OpenTelemetry Collector), sementara engine game terus menulis tick baru ke buffer sirkular.
*   **Kegagalan**: Pointer `head` melewati `tail` lebih dari `RingBufferSize`, merusak data histori yang belum terbaca (*data tearing*).
*   **Mitigasi**: Terapkan deteksi jarak pointer secara atomik: `if (head - tail) > RingBufferSize`, secara sadar lewatkan data lama, naikkan metrik *telemetry_dropped_ticks_total*, dan atur pointer `tail` ke `head - RingBufferSize`. Jangan pernah memblokir *Game Simulation Thread* hanya demi mempertahankan integritas log metrik.

#### 2. False Overhead Injection Akibat GC Tracing
*   **Kondisi**: Developer menyematkan label dinamis seperti: `fmt.Sprintf("agent_%d", agent.ID)` ke dalam label metrik pada loop aktif.
*   **Kegagalan**: Terjadinya ribuan alokasi kecil pada heap per frame simulasi. Hal ini menyebabkan siklus *Garbage Collection mark-and-sweep* aktif lebih sering, mencuri *CPU cycles* dan menimbulkan *hitch/stuttering* berkala pada game server.
*   **Mitigasi**: Gunakan static string literals atau enumeration integer token. Terapkan rule CI linter (`go-lint` / `clang-tidy`) yang melarang alokasi heap di dalam paket loop simulasi agen (`0 allocs/op`).

#### 3. Cascading Tick Death Spiral
*   **Kondisi**: Beban AI melebihi budget tick ($TotalTime > Budget$), menyebabkan server berusaha mengejar ketertinggalan dengan memproses akumulasi tick secara beruntun (*catch-up ticks*).
*   **Kegagalan**: Server mengalami stagnasi permanen, I/O terputus, dan klien game mengalami diskoneksi serentak (*mass timeout*).
*   **Mitigasi**: Profiler mendeteksi pelanggaran beruntun melalui *Sustained Overrun Circuit Breaker*. Jika terjadi overrun selama 5 tick berturut-turut, profiler mengirimkan sinyal ke AI Coordinator untuk mengaktifkan **Dynamic LOD Fallback**: menurunkan frekuensi kalkulasi pathfinding, menonaktifkan visibilitas raycast sekunder, dan mengeksekusi logika agen berbasis interpolasi matematika sederhana.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Pendekatan | Ring Buffer Lokal (Implementasi di atas) | Channel-Based Event Bus | OpenTelemetry In-Line SDK Direct |
| :--- | :--- | :--- | :--- |
| **Overhead Latensi** | **Sangat Rendah** (~10–25 ns per snapshot record) | Sedang (~150–400 ns per operasi antrean) | Tinggi (> 2–5 $\mu s$ per span context creation) |
| **Alokasi Heap** | **0 Bytes/op** (Array statis teralokasi di awal) | Berpotensi terjadi boxing overhead jika payload bervariasi | Tinggi, membuat objek span, context, dan map label |
| **Dukungan Distributed Trace** | Terbatas (perlu *worker* khusus untuk rekonstruksi trace) | Sedang (dapat diekspor secara terpusat) | **Native & Luas** (Langsung terhubung dengan trace parent Jaeger/Zipkin) |
| **Ketahanan Spillover** | Data lama terhapus jika I/O terhambat (*fail-safe*) | Buffer channel penuh dapat memblokir eksekusi game | Menyerap resource server; GC spike dapat mematikan process |

*Alternatif Desain*: Untuk studio yang membutuhkan visualisasi *Call-Tree Flamegraph* interaktif tanpa instrumen manual berkelanjutan, penggunaan **Continuous Profiler** berbasis OS kernel eBPF (misalnya: Pixie, Parca, atau Pyroscope) adalah alternatif terbaik. Profiler eBPF membaca register CPU dan stack pointer dengan overhead <1% tanpa memodifikasi kode game loop. Namun kekurangannya, profil eBPF tidak memiliki konteks domain game tingkat tinggi (seperti *Archetype Agent*, *LOD Level*, atau *Tick Index*).

---

### 9. Best Practices & Standar Industri

1.  **Strict 0 B/op Allocation In Tick Path**: Validasi melalui unit test benchmarking menggunakan parameter `-benchmem`:
    ```go
    func BenchmarkTickProfilerExecution(b *testing.B) {
        profiler := NewLockFreeTickProfiler(15 * time.Millisecond)
        b.ReportAllocs()
        b.ResetTimer()
        for i := 0; i < b.N; i++ {
            session := profiler.StartTick(uint64(i), 500)
            session.EnterPhase(PhasePerception)
            session.EnterPhase(PhaseDecision)
            session.EnterPhase(PhaseSteering)
            session.EnterPhase(PhaseActuation)
            session.EndTick()
        }
    }
    ```
    *Kriteria Lolos*: `0 allocs/op` dan waktu eksekusi total < 100 ns.
2.  **Telemetry Aggregation Windowing**: Jangan mengekspor data metrik ke server Prometheus pada setiap tick. Kumpulkan (*batch*) metrik ke dalam histogram internal dan publikasikan secara berkala (misal: setiap 1000ms).
3.  **Alerting Baselines**:
    *   **Peringatan (Warning)**: $p95 \text{ tick duration} \ge 0.70 \times \text{Budget}$.
    *   **Kritis (Critical)**: $p99 \text{ tick duration} \ge 0.90 \times \text{Budget}$.
    *   **Darurat (Emergency)**: Terdapat 3 frame simulasi berturut-turut dengan status *Overrun*.

---

### 10. Hands-on Lab Exercise

#### Skenario Laboratorium
Anda ditugaskan mendiagnosis degradasi performa pada game server tempur kooperatif. Server mengalami lonjakan p99 tick duration secara periodik ketika 500 bot agent berhadapan dengan pemain. Anda harus menerapkan profiler nir-alokasi, mengidentifikasi fase yang mengalami *bottleneck*, dan memvalidasi penghapusan beban alokasi heap.

#### Langkah 1: Implementasi AI Loop Simulator
Buat file `main.go` yang mensimulasikan game loop dengan beban buatan (*synthetic workload*) pada salah satu fasenya:

```go
package main

import (
	"context"
	"math/rand"
	"time"
	"yourmodule/telemetry" // Path package profiler di atas
)

func simulateAISubsystem(phase telemetry.PhaseType) {
	switch phase {
	case telemetry.PhasePerception:
		// Simulasi beban query spatial yang stabil
		time.Sleep(2 * time.Millisecond)
	case telemetry.PhaseDecision:
		// Simulasi latency spike acak (misal: pathfinding lock contention)
		if rand.Float32() < 0.05 {
			time.Sleep(12 * time.Millisecond) // Memicu Overrun!
		} else {
			time.Sleep(3 * time.Millisecond)
		}
	case telemetry.PhaseSteering:
		time.Sleep(1 * time.Millisecond)
	case telemetry.PhaseActuation:
		time.Sleep(1 * time.Millisecond)
	}
}

func main() {
	// Budget total simulasi AI adalah 10 milidetik
	profiler := telemetry.NewLockFreeTickProfiler(10 * time.Millisecond)
	consumer := telemetry.NewTelemetryConsumer(profiler)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Jalankan telemetri consumer worker (drains setiap 500ms)
	consumer.StartWorker(ctx, 500*time.Millisecond)

	// Simulasikan 100 Tick AI
	for tick := uint64(1); tick <= 100; tick++ {
		session := profiler.StartTick(tick, 500)

		simulateAISubsystem(telemetry.PhasePerception)
		session.EnterPhase(telemetry.PhaseDecision)

		simulateAISubsystem(telemetry.PhaseDecision)
		session.EnterPhase(telemetry.PhaseSteering)

		simulateAISubsystem(telemetry.PhaseSteering)
		session.EnterPhase(telemetry.PhaseActuation)

		simulateAISubsystem(telemetry.PhaseActuation)
		session.EndTick()

		time.Sleep(40 * time.Millisecond) // Jeda antar-tick (Simulasi loop 20-25Hz)
	}

	consumer.Stop()
}
```

#### Langkah 2: Verifikasi Alokasi Memori
Jalankan benchmark dan analisis profil memori untuk memastikan telemetri tick bekerja tanpa alokasi heap:

```bash
go test -bench=. -benchmem -memprofile=mem.out
go tool pprof -alloc_space mem.out
```
*Hasil yang diharapkan*: Tidak ditemukan trace dari struct `TickSnapshot` atau pemanggilan method profiler pada output pprof.

#### Langkah 3: Analisis Root Cause Output
Jalankan simulasi utama:
```bash
go run main.go
```
Identifikasi output konsol:
```text
[CRITICAL ALERT] Tick 24 Budget Exceeded! Total: 16.12ms, Budget: 10.00ms | Perception: 2.01ms, Decision: 12.05ms, Steering: 1.02ms, Actuation: 1.04ms, Agents: 500
```
Dari data telemetri yang dihasilkan secara real-time, Anda dapat langsung mengisolasi akar permasalahan secara presisi: fase `Decision` memakan waktu $12.05\text{ ms}$, yang melampaui total budget keseluruhan siklus tick ($10.00\text{ ms}$). Tim pengembang dapat langsung memfokuskan investigasi ke logika pengambilan keputusan (*Behavior Tree*) tanpa harus membuang waktu menganalisis subsistem *Perception* atau *Steering*.