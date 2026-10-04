# Bab 02: Model Arsitektur Dedicated Game Server & Loop Engine

---

## 1. Learning Objectives

Setelah menyelesaikan bab ini, Anda diharapkan mampu:

- **Menganalisis dan Memilih Paradigma Loop Engine**: Membedakan secara matematis dan arsitektural antara *Variable Timestep*, *Semi-Fixed Timestep*, dan *Fixed Timestep with Accumulator* untuk server game otoritatif.
- **Mengeliminasi Fenomena *Spiral of Death***: Merancang mekanisme pertahanan deterministik terhadap lonjakan komputasi CPU menggunakan *frame time clamping* dan *sub-stepping debt dissipation*.
- **Mengimplementasikan Dedicated Game Server Loop Berkinerja Tinggi**: Membangun loop engine multithreaded menggunakan Go yang terisolasi dari *network jitter*, beroperasi pada presisi nanodetik, dan mendukung alokasi memori zero-allocation pada *hot path*.
- **Mendesain Pola Sinkronisasi State & AI Sub-ticking**: Mengintegrasikan subsistem AI Agent dan verifikasi input ke dalam arsitektur siklus tick tanpa memblokir thread simulasi utama.
- **Mengukur dan Memitigasi Tick Drift**: Mengidentifikasi latensi thread scheduling OS, sleep precision jitter, dan GC pauses melalui instrumentasi metrik waktu nyata.

---

## 2. Concept Overview

Pada arsitektur multiplayer modern, **Dedicated Game Server (DGS)** berfungsi sebagai *Single Source of Truth* (SSoT). Server tidak bertindak sebagai penerima input pasif yang sekadar merelai data ke client lain (seperti pada model peer-to-peer), melainkan sebagai simulator fisika dan aturan logika yang deterministik dan otoritatif.

```
       +-------------------------------------------------------------+
       |               DEDICATED GAME SERVER (DGS)                   |
       |                                                             |
       |  +-------------------+       +---------------------------+  |
       |  | Network I/O Loop  | ====> | Input Verification Buffer |  |
       |  +-------------------+       +---------------------------+  |
       |           ^                                |                |
       |           | Snapshots                      v                |
       |  +-------------------+       +---------------------------+  |
       |  | State Broadcast   | <==== | Authoritative Game Loop   |  |
       |  +-------------------+       | (Fixed Timestep Simulation|  |
       |                              +---------------------------+  |
       +-------------------------------------------------------------+
```

Mental model dari DGS adalah sebuah **Discrete Dynamical System**:

$$S_{t + \Delta t} = f(S_t, I_t)$$

Di mana:
- $S_t$ merepresentasikan seluruh *World State* pada tick $t$.
- $I_t$ merepresentasikan himpunan input tervalidasi yang diterima dari semua client pada window tick $t$.
- $f$ adalah fungsi transisi deterministik (fisika, pergerakan, state machine AI, game rules).
- $\Delta t$ adalah durasi waktu diskret yang invarian (misalnya, $16.666\text{ ms}$ untuk 60 Hz).

Perbedaan mendasar antara game loop client dan game loop server:

1. **Client Game Loop**: Terikat pada *refresh rate* hardware display (V-Sync, 60–240 FPS) atau dibiarkan *unbound*. Menggunakan interpolasi visual untuk menghaluskan pergerakan antar frame.
2. **Server Game Loop**: Harus berjalan pada frekuensi pembaruan yang kaku (*Fixed Tick Rate*). Server tidak melakukan rendering; server mengeksekusi integrasi matematika, navigasi AI, resolusi tabrakan, dan broadcast snapshot. Variasi waktu pemrosesan tick tidak boleh mengubah hasil perhitungan fisika.

---

## 3. Why It Matters

Dalam game kompetitif berskala global (CS2, Valorant, Dota 2, Apex Legends), integritas simulasi adalah fondasi ekonomi game:

- **Eksploitasi Client-Side (Speedhacking & Desync)**: Tanpa fixed tick rate di sisi server yang terisolasi dari clock client, manipulasi waktu lokal pada paket jaringan client dapat menyebabkan karakter bergerak lebih cepat dari batas normal atau menembus batas tabrakan (*noclip*).
- **Non-Deterministik Fisika**: Jika kalkulasi Euler Integration pada server menggunakan $\Delta t$ dinamis:
  
  $$x_{t+1} = x_t + v_t \cdot \Delta t$$
  
  Nilai $\Delta t$ yang berfluktuasi akibat beban CPU server akan menghasilkan lintasan proyektil dan tabrakan yang berbeda pada frame rate yang berbeda.
- **Spiral of Death (Death Spiral)**: Terjadi ketika beban satu tick melebihi anggaran waktu ($\text{Tick Duration} > \Delta t$). Server mencoba mengejar defisit waktu tersebut di frame berikutnya dengan menjalankan kalkulasi ganda. Akibatnya, CPU terbebani lebih parah, frame berikutnya memakan waktu lebih lama lagi, hingga server mengalami *catastrophic lag* atau OOM (*Out of Memory*).
- **Alokasi Sumber Daya Server Enterprise**: Menjalankan ribuan instans DGS pada kluster Kubernetes (misalnya menggunakan Agones) menuntut utilisasi CPU yang stabil dan dapat diprediksi. Server loop yang boros alokasi memori akan memicu siklus Garbage Collector yang menghentikan simulasi (*Stop-the-World*), menyebabkan lonjakan latensi jutaan pemain secara massal.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut menggambarkan alur internal eksekusi thread Dedicated Game Server dengan decoupling total antara Ingress Jaringan, Ticking Engine, dan Egress Snapshot.

```
       +--------------------------------------------------------------------------+
       |                         DGS ARCHITECTURE ENGINE                          |
       +--------------------------------------------------------------------------+
                                            |
                 [ Network Ingress Socket: UDP / WebSocket / KCP ]
                                            |
                                            v
       +--------------------------------------------------------------------------+
       | Network Thread Pool                                                      |
       | - Kernel epoll / kqueue                                                  |
       | - Packet Deserialization & Cryptographic Validation                      |
       | - Rate Limiting & Sequence Ordering                                      |
       +--------------------------------------------------------------------------+
                                            |
                                            | Lock-free MPSC Queue
                                            v
       +--------------------------------------------------------------------------+
       | Simulation Worker Thread (Authoritative Game Loop)                       |
       |                                                                          |
       |   +------------------------------------------------------------------+   |
       |   | Time Measurement & Accumulator Ingestion                         |   |
       |   | (Clock Monotonic Nanosecond Resolution)                          |   |
       |   +------------------------------------------------------------------+   |
       |                                    |                                     |
       |                                    v                                     |
       |   +------------------------------------------------------------------+   |
       |   | Loop Accumulator Phase: while(accumulator >= FIXED_DELTA)        |   |
       |   |                                                                  |   |
       |   |   [1] Consume Ingress RingBuffer -> Assign Inputs to Tick N      |   |
       |   |   [2] AI Agents Perception & Behavior Trees (Sub-tick LOD)       |   |
       |   |   [3] Fixed Physics Integration & Spatial Partitioning Update    |   |
       |   |   [4] Collision Resolution & Authoritative Hit Registration      |   |
       |   |   [5] Game Rule & Win/Loss Condition Evaluation                  |   |
       |   |   [6] State Serialization -> Snapshot History Buffer             |   |
       |   |   [7] accumulator -= FIXED_DELTA                                 |   |
       |   |   [8] TickCounter++                                              |   |
       |   +------------------------------------------------------------------+   |
       |                                    |                                     |
       |                                    v                                     |
       |   +------------------------------------------------------------------+   |
       |   | Drift Correction & Adaptive Sleeping (Yield / Spinlock Balance)  |   |
       |   +------------------------------------------------------------------+   |
       +--------------------------------------------------------------------------+
                                            |
                                            | RingBuffer Pointer Swap
                                            v
       +--------------------------------------------------------------------------+
       | Broadcast & Egress Worker Thread Pool                                    |
       | - Delta Compression (Snapshot[N] - Snapshot[N-1])                        |
       | - Interest Management (Spatial Culling)                                  |
       | - Socket Outbound Serialization                                          |
       +--------------------------------------------------------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 The Mathematical Core: Fixed Timestep with Accumulator

Implementasi paling robust di industri game server mengadopsi algoritma **Glenn Fiedler ("Fix Your Timestep")**. Logika ini memisahkan konsumsi waktu aktual dari kalkulasi fisika:

$$\text{frameTime} = t_{\text{current}} - t_{\text{previous}}$$

$$\text{accumulator} = \text{accumulator} + \text{frameTime}$$

$$\text{while } (\text{accumulator} \ge \Delta t_{\text{fixed}}):$$

$$\text{Simulate}(\Delta t_{\text{fixed}})$$

$$\text{accumulator} = \text{accumulator} - \Delta t_{\text{fixed}}$$

### 5.2 Pertahanan "Spiral of Death"

Jika pemrosesan di dalam `Simulate()` memakan waktu $25\text{ ms}$, sementara $\Delta t_{\text{fixed}} = 16.66\text{ ms}$, accumulator tidak akan pernah habis. Loop `while` akan berulang tanpa batas hingga sistem crash. Solusinya adalah menerapkan **Max Frame Clamping**:

$$\text{frameTime}_{\text{clamped}} = \min(\text{frameTime}, \text{MAX\_ACCUMULATOR\_CAP})$$

Jika terjadi spike ekstrem (misalnya sistem mengalami thread pause OS selama $200\text{ ms}$), accumulator dipaksa membatasi iterasi tick masksimal (umumnya $3$ hingga $5$ tick per frame loop), dan sisa waktu dibuang (*time-debt truncation*) sembari memicu event telemetri `TICK_DROPPED_WARNING`.

### 5.3 High-Precision Sleeping vs. Busy-Wait Loop

Tantangan arsitektural pada OS generik (Linux/Windows) adalah akurasi fungsi sleep standar:

- `time.Sleep()` atau `nanosleep()` memiliki resolusi yang bergantung pada OS scheduler tick (biasanya $1\text{ ms}$ hingga $15.6\text{ ms}$ default pada Windows, $\sim 1\text{ ms}$ pada Linux default tanpa kernel RT).
- Tidur terlalu lama menyebabkan tick terlambat (*tick under-run*).
- Pola *hybrid wait* adalah standar: Panggil sleep/yield untuk sebagian besar waktu luang, lalu beralih ke *busy-wait* (spinning) pada $1\text{ ms} - 500\text{ µs}$ terakhir sebelum tick dimulai untuk mencapai presisi sub-mikrodetik.

### 5.4 AI Sub-Ticking & Level of Detail (LOD)

Tidak semua entitas AI perlu dieksekusi pada setiap tick simulasi:
- **Tick Rate Server**: 60 Hz ($\Delta t = 16.66\text{ ms}$).
- **AI Ticking Policy**:
  - *Tier 1 (Combat Range)*: Update Behavior Tree & Pathfinding setiap 1 tick (60 Hz).
  - *Tier 2 (Proximity Alert)*: Update setiap 3 tick (20 Hz).
  - *Tier 3 (Distant / Idle)*: Update setiap 12 tick (5 Hz).

Loop engine harus memiliki scheduler internal berbasis modulo tick counter (`TickCount % N == 0`) untuk mendistribusikan beban AI secara merata (*Time-Slicing*) agar tidak menciptakan *frame spike* pada tick tertentu.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi Dedicated Game Server Engine di **Go**. Implementasi ini mencakup:
- High-precision fixed-timestep loop dengan hybrid sleep-spin.
- Clamp mitigasi *Spiral of Death*.
- Zero-allocation tick pipeline pattern.
- Thread-safe non-blocking input ingestion.
- Structured metrics logger.

```go
package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"runtime"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

// Config merepresentasikan parameter deterministik engine.
type Config struct {
	TickRate         int           // Frekuensi tick per detik (Hz)
	MaxSubSteps      int           // Batas maksimal sub-stepping sebelum clamping spiral of death
	MaxTelemetryDrift time.Duration // Batas drift toleransi sebelum dicatat sebagai degradasi
}

// PlayerInput menyimpan data input mentah yang dikirim client.
type PlayerInput struct {
	PlayerID  uint64
	Sequence  uint32
	VectorX   float32
	VectorY   float32
	Actions   uint32
	ClientTimestamp int64
}

// WorldState merepresentasikan data otoritatif snapshot.
type WorldState struct {
	TickNumber   uint64
	TimestampNano int64
	EntitiesCount int
}

// Engine mendefinisikan Dedicated Game Server loop core.
type Engine struct {
	cfg         Config
	fixedDelta  time.Duration
	running     atomic.Bool
	tickCounter uint64

	// Concurrency & Ingress
	inputQueueLock sync.Mutex
	inputQueue     []PlayerInput

	// Metrics
	metrics struct {
		totalTicks     atomic.Uint64
		droppedTicks   atomic.Uint64
		lastTickExecNs atomic.Int64
	}

	logger *slog.Logger
}

// NewEngine menginisialisasi state engine dan memvalidasi parameter konfigurasinya.
func NewEngine(cfg Config, logger *slog.Logger) (*Engine, error) {
	if cfg.TickRate <= 0 {
		return nil, fmt.Errorf("invalid tick rate: %d, must be > 0", cfg.TickRate)
	}
	if cfg.MaxSubSteps <= 0 {
		cfg.MaxSubSteps = 3 // Standard default fallback
	}

	fixedDeltaNs := int64(time.Second) / int64(cfg.TickRate)

	return &Engine{
		cfg:         cfg,
		fixedDelta:  time.Duration(fixedDeltaNs),
		inputQueue:  make([]PlayerInput, 0, 1024),
		logger:      logger,
	}, nil
}

// PushInput dipanggil oleh network thread untuk menambahkan input ke buffer server.
func (e *Engine) PushInput(input PlayerInput) {
	e.inputQueueLock.Lock()
	e.inputQueue = append(e.inputQueue, input)
	e.inputQueueLock.Unlock()
}

// Start menjalankan loop utama engine secara blocking sampai context dibatalkan.
func (e *Engine) Start(ctx context.Context) error {
	// Mengunci OS thread untuk menghindari thread migration penalty pada high frequency loops
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()

	e.running.Store(true)
	defer e.running.Store(false)

	e.logger.Info("Starting dedicated server engine loop",
		slog.Int("tick_rate_hz", e.cfg.TickRate),
		slog.Duration("fixed_delta", e.fixedDelta),
		slog.Int("max_sub_steps", e.cfg.MaxSubSteps),
	)

	previousTime := time.Now()
	var accumulator time.Duration

	// Hybrid Sleep-Spin Threshold
	// Tidur via runtime.Gosched / Sleep jika sisa waktu > 2ms, spinlock untuk akurasi sub-milidetik.
	const spinLockThreshold = 2 * time.Millisecond

	for {
		select {
		case <-ctx.Done():
			e.logger.Info("Shutdown signal received. Stopping engine loop...")
			return nil
		default:
		}

		currentTime := time.Now()
		frameDuration := currentTime.Sub(previousTime)
		previousTime = currentTime

		// Edge Case Mitigation: Antisipasi suspensi proses atau freeze eksternal
		// Clamping max accumulator untuk mencegah "Spiral of Death"
		maxAccumulatorCap := e.fixedDelta * time.Duration(e.cfg.MaxSubSteps)
		if frameDuration > maxAccumulatorCap {
			e.logger.Warn("Severe frame duration spike detected! Clamping accumulator to prevent Death Spiral.",
				slog.Duration("actual_frame_duration", frameDuration),
				slog.Duration("clamped_to", maxAccumulatorCap),
			)
			e.metrics.droppedTicks.Add(uint64((frameDuration - maxAccumulatorCap) / e.fixedDelta))
			frameDuration = maxAccumulatorCap
		}

		accumulator += frameDuration

		// Eksekusi tick simulasi secara deterministik
		for accumulator >= e.fixedDelta {
			tickStart := time.Now()

			e.runSingleTick(e.tickCounter, e.fixedDelta)

			e.tickCounter++
			e.metrics.totalTicks.Add(1)
			accumulator -= e.fixedDelta

			tickElapsed := time.Since(tickStart)
			e.metrics.lastTickExecNs.Store(tickElapsed.Nanoseconds())

			if tickElapsed > e.fixedDelta {
				e.logger.Warn("Tick time-budget exceeded!",
					slog.Uint64("tick", e.tickCounter),
					slog.Duration("budget", e.fixedDelta),
					slog.Duration("elapsed", tickElapsed),
				)
			}
		}

		// Hybrid Precise Waiting Mechanism:
		// Menghitung waktu tunggu hingga frame berikutnya tiba untuk menstabilkan CPU
		targetNextTick := previousTime.Add(e.fixedDelta - accumulator)
		timeRemaining := time.Until(targetNextTick)

		for timeRemaining > 0 {
			if timeRemaining > spinLockThreshold {
				// Relinquish OS slice sebentar untuk efisiensi CPU
				time.Sleep(time.Millisecond)
			} else {
				// Spin wait secara agresif untuk mencapai presisi tingkat nanodetik
				runtime.Gosched()
			}
			timeRemaining = time.Until(targetNextTick)
		}
	}
}

// runSingleTick adalah *hot path* simulasi otoritatif.
func (e *Engine) runSingleTick(tick uint64, dt time.Duration) {
	// 1. Swap & Dapatkan Input Jaringan Secara Cepat
	e.inputQueueLock.Lock()
	var currentInputs []PlayerInput
	if len(e.inputQueue) > 0 {
		currentInputs = make([]PlayerInput, len(e.inputQueue))
		copy(currentInputs, e.inputQueue)
		e.inputQueue = e.inputQueue[:0] // Clear slice tanpa relokasi kapasitas
	}
	e.inputQueueLock.Unlock()

	// 2. Proses Input Validation
	for i := range currentInputs {
		e.processPlayerInput(&currentInputs[i])
	}

	// 3. AI Processing (Time-Sliced Level of Detail)
	e.updateAIAgents(tick, dt)

	// 4. Fixed Step Physics & Movement Integration
	e.integratePhysics(dt)

	// 5. Broadcast State Replication (Non-blocking async handoff)
	if tick%2 == 0 { // Contoh: Broadcast snapshot pada 30Hz jika server 60Hz
		e.publishSnapshot(tick)
	}
}

func (e *Engine) processPlayerInput(in *PlayerInput) {
	// Logika verifikasi: Bounds checking, packet sequence validation, anti-teleport
	_ = in
}

func (e *Engine) updateAIAgents(tick uint64, dt time.Duration) {
	// Time-slicing AI workload berdasarkan tick modulo
	switch {
	case tick%1 == 0:
		// Update entitas AI agresif/dekat pemain (Combat Sub-loop)
	case tick%3 == 0:
		// Update entitas patroli/sedang (Pathing Sub-loop)
	case tick%12 == 0:
		// Update entitas pasif/jauh (Background Decision Sub-loop)
	}
}

func (e *Engine) integratePhysics(dt time.Duration) {
	// Integrasi matematika deterministik (Verlet atau Symplectic Euler)
	_ = dt.Seconds()
}

func (e *Engine) publishSnapshot(tick uint64) {
	// Serialisasi internal buffer dan kirim ke ringbuffer thread egress
	_ = tick
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))

	engineCfg := Config{
		TickRate:         60, // 60 Hz = ~16.666ms budget
		MaxSubSteps:      4,  // Maksimal akumulasi 66.6ms sebelum drop
		MaxTelemetryDrift: 5 * time.Millisecond,
	}

	engine, err := NewEngine(engineCfg, logger)
	if err != nil {
		logger.Error("Failed to initialize engine", slog.Any("error", err))
		os.Exit(1)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Menangkap OS termination signals untuk graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		sig := <-sigChan
		logger.Info("System signal caught, terminating engine...", slog.String("signal", sig.String()))
		cancel()
	}()

	// Simulasikan Ingress Network Worker pada goroutine terpisah
	go func() {
		ticker := time.NewTicker(10 * time.Millisecond)
		defer ticker.Stop()
		var seq uint32

		for {
			select {
			case <-ctx.Done():
				return
			case t := <-ticker.C:
				seq++
				engine.PushInput(PlayerInput{
					PlayerID:        1001,
					Sequence:        seq,
					VectorX:         1.0,
					VectorY:         0.0,
					ClientTimestamp: t.UnixNano(),
				})
			}
		}
	}()

	if err := engine.Start(ctx); err != nil {
		logger.Error("Engine crashed with error", slog.Any("error", err))
		os.Exit(1)
	}

	logger.Info("Dedicated Game Server stopped cleanly.",
		slog.Uint64("total_ticks_executed", engine.metrics.totalTicks.Load()),
		slog.Uint64("total_ticks_dropped", engine.metrics.droppedTicks.Load()),
	)
}
```

---

## 7. Edge Cases & Failure Modes

### 7.1 Monotonic Clock vs. Wall Clock Skew

- **Gejala Kerusakan**: Server tiba-tiba membekukan pergerakan karakter atau melompati ratusan tick dalam seketika.
- **Penyebab**: Menggunakan Wall Clock (`time.Now().Unix()`) yang terkena sinkronisasi *NTP (Network Time Protocol) skew* atau penyesuaian waktu sistem (*leap second*).
- **Mitigasi**: Gunakan referensi waktu yang dijamin monotonik (`time.Now()` pada runtime Go secara default mengikutsertakan pembacaan monotonic clock OS sejak Go 1.9). Jangan pernah mengukur akumulator dari serialisasi epoch eksternal.

### 7.2 Thread Migration Latency & Kernel Scheduling Noise

- **Gejala Kerusakan**: *Micro-stuttering* periodik di mana satu tick acak memakan waktu $30\text{ ms}$ padahal utilisasi CPU server di bawah 20%.
- **Penyebab**: OS scheduler memindahkan thread simulasi ke Core CPU lain yang memiliki *cold cache* (*cache miss penalty*), atau core tersebut sedang dalam status hemat daya (*CPU frequency scaling down*).
- **Mitigasi**:
  - Gunakan `runtime.LockOSThread()` untuk menahan context runtime di thread OS yang sama.
  - Terapkan CPU Pinning / Thread Affinity pada sistem Linux produksi:
    ```bash
    taskset -c 1 ./game_server_binary
    ```
  - Set CPU governor sistem operasi ke profil `performance` bukan `powersave`.

### 7.3 GC-Induced Tick Exceeds Budget (Go / C# Runtimes)

- **Gejala Kerusakan**: Setiap beberapa puluh detik, terjadi lonjakan durasi tick yang menyebabkan snapshot jaringan drop massal.
- **Penyebab**: Alokasi objek sementara di dalam loop tick utama (`runSingleTick`) memicu GC sweep.
- **Mitigasi**:
  - Menerapkan arsitektur Zero-Allocation pada *hot path*. Gunakan kembali buffer slice (`queue = queue[:0]`), `sync.Pool`, atau alokasi flat primitive array secara kontinu di awal eksekusi (*pre-allocation*).

---

## 8. Trade-offs & Alternatif Solusi

| Pendekatan Arsitektur | Keuntungan | Kerugian | Skenario Penggunaan Terbaik |
| :--- | :--- | :--- | :--- |
| **Fixed Timestep with Accumulator** *(Pendekatan Terpilih)* | Deterministik penuh, komputasi fisika stabil, independen terhadap frame rate, anti-speedhack. | Beban komputasi konstan, risiko *Spiral of Death* jika budget tick terlampaui tanpa clamp. | FPS Kompetitif (Valorant, CS2), MOBA, Simulator Fisika Akurat. |
| **Variable Timestep ($\Delta t$ Dinamis)** | Sederhana, CPU tidak dipaksa mengejar frame yang tertinggal, hemat daya saat idle. | Fisika tidak deterministik, rawan exploit tunnelling (tembus dinding), rekonsiliasi mustahil. | Server Game Turn-Based, Hyper-Casual, Game Tycoon/Manajemen. |
| **Deterministic Lockstep** | Bandwidth jaringan ultra-rendah (hanya mengirim input aksi, bukan full snapshot). | Sangat sensitif terhadap lag: satu client lambat memperlambat seluruh server game. | RTS Klasik (StarCraft), Fighting Games (Rollback Netcode P2P). |
| **Tickless / Sub-Tick Engine** (e.g., CS2 Sub-Tick) | Input dicatat pada timestamp waktu tepat kejadian di antara tick, meminimalisir delay input. | Kompleksitas kalkulasi rollback server meningkat drastis; latensi network out-of-order tinggi. | First-Person Shooters ultra-kompetitif modern AAA. |

---

## 9. Best Practices & Standard Industri

1. **Pisahkan Simulasi dari Operasi Jaringan**:
   - Jangan pernah melakukan panggilan I/O jaringan (seperti pembacaan UDP socket langsung secara synchronous) di dalam simulation loop. Gunakan pola *RingBuffer / Channel* untuk memindahkan data input dari network goroutine/worker thread ke simulation thread.

2. **Skalabilitas AI Menggunakan Budget Allocation**:
   - Terapkan alokasi kuota waktu maksimum untuk pemrosesan AI pada setiap tick (misalnya: maksimum $3\text{ ms}$ dari total budget $16.6\text{ ms}$). Jika kuota habis, entitas AI berikutnya ditunda eksekusinya ke tick berikutnya.

3. **Pre-allocated Memory & Object Pooling**:
   - Dilarang keras melakukan instansiasi objek dinamis (seperti `new`, `malloc`, dynamic slice resizing) di dalam tick execution block. Semua array entitas harus dialokasikan sejak server dimuat (*pre-warmed memory arena*).

4. **Kompensasi Latensi Menggunakan Ring Buffer Snapshots**:
   - Simpan state historis server selama 1 hingga 2 detik terakhir ke dalam buffer memori melingkar (*Circular Buffer* berukuran $N$ tick). Hal ini wajib untuk mendukung sistem *Lag Compensation / Server-Side Rewind* saat memverifikasi tembakan senjata (*hitscan validation*).

---

## 10. Hands-on Lab Exercise

### Judul Lab: Membangun Resilient Fixed-Timestep Dedicated Game Loop dengan Anti-Death-Spiral & Sub-Tick AI Scheduling

### Skenario
Anda ditugaskan merancang core engine loop untuk game aksi multiplayer 60 Hz. Server sering mengalami kondisi spike CPU acak akibat integrasi sistem AI. Anda harus memverifikasi bahwa engine mampu mempertahankan tick rate deterministik dan pulih secara anggun (*graceful recovery*) saat diinjeksi beban kejut (*artificial latency spike*).

### Langkah Implementasi

1. **Inisialisasi Project**:
   ```bash
   mkdir dgs-core-loop && cd dgs-core-loop
   go mod init dgs-core-loop
   ```

2. **Implementasikan Loop Driver**:
   - Buat file `main.go` menggunakan source code production-ready dari **Bagian 6**.

3. **Injeksi Artificial Heavy Workload**:
   - Modifikasi fungsi `integratePhysics` untuk merekayasa beban kerja CPU yang melebihi batas budget tick secara acak:
   ```go
   func (e *Engine) integratePhysics(dt time.Duration) {
       // Simulasi beban kalkulasi normal: ~2ms
       time.Sleep(2 * time.Millisecond)

       // Simulasi CPU spike ekstrem setiap tick kelipatan 300
       if e.tickCounter%300 == 0 && e.tickCounter > 0 {
           // Terjadi lag mendadak sebesar 100ms (jauh melampaui 16.6ms)
           time.Sleep(100 * time.Millisecond)
       }
   }
   ```

4. **Jalankan Engine dan Monitor Output**:
   ```bash
   go run main.go
   ```

### Evaluasi & Validasi Keberhasilan
- Perhatikan log output JSON pada konsol.
- Pastikan bahwa saat tick kelipatan 300 tiba, sistem menghasilkan log peringatan:
  ```json
  {"level":"WARN","msg":"Severe frame duration spike detected! Clamping accumulator to prevent Death Spiral.","actual_frame_duration":"...","clamped_to":"66.666664ms"}
  ```
- Amati metrik akhir setelah mematikan server dengan `Ctrl+C`:
  - `total_ticks_dropped` harus merefleksikan tick yang dibuang secara terukur akibat lag spike.
  - Engine **tidak boleh** mengalami kondisi hanging permanen atau mengeksekusi puluhan sub-step berulang yang membekukan processing socket input secara berkepanjangan.