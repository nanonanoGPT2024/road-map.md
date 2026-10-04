# Bab 03: Sinkronisasi State, Interpolasi, & Prediksi Klien

## 1. Learning Objectives
Setelah menyelesaikan bab ini, Anda diharapkan mampu:
* **Menganalisis** dampak anomali jaringan (*packet loss*, *latency jitter*, dan *out-of-order delivery*) terhadap model konsistensi *authoritative game loop*.
* **Mengimplementasikan** pipeline *Client-Side Prediction* dan *Server Reconciliation* menggunakan Go untuk mengeliminasi *perceived input latency* pada *player controller* lokal.
* **Membangun** sistem *Snapshot Interpolation* (Entity Interpolation) berbasis *jitter buffer* adaptif untuk merender pergerakan entitas non-lokal dan agen AI secara mulus tanpa *stuttering*.
* **Merancang** skema *Delta Compression* dan *State Quantization* guna mengoptimalkan throughput bandwidth transmisi *network snapshot*.
* **Mengevaluasi dan Mengatasi** desinkronisasi deterministik akibat divergensi *floating-point arithmetic* lintas platform pada simulasi fisik.

---

## 2. Concept Overview
Dalam arsitektur *authoritative game server*, server bertindak sebagai satu-satunya *single source of truth* (SSoT). Klien tidak memiliki hak (*authority*) untuk memutasi *state* permainan secara langsung; klien hanya mengirimkan *intent* (input mentah seperti penekanan tombol dan rotasi kamera) dan menerima *state snapshots* yang telah divalidasi oleh server.

```
       +-------------------------------------------------------+
       |             Authoritative Server (SSoT)               |
       |  - Validates Inputs                                   |
       |  - Advances Physics/Simulation (Fixed Tick Rate)      |
       |  - Broadcasts Compressed World Snapshots              |
       +---------------------------+---------------------------+
                                   ^
            Raw Inputs             |   Snapshots (Tick N)
         (Seq #, Action, dt)       |   (Transform, Velocity, ...)
                                   v
       +-------------------------------------------------------+
       |                  Remote Client Game                   |
       |  - Prediction: Simulates local entity immediately     |
       |  - Reconciliation: Re-simulates on server divergence  |
       |  - Interpolation: Renders remote entities in past     |
       +-------------------------------------------------------+
```

Tantangan fundamental dalam paradigma ini adalah pembatasan fisika propagasi sinyal: latensi jaringan (RTT, *Round-Trip Time*) berkisar antara puluhan hingga ratusan milidetik. Menunggu respons server sebelum memperbarui entitas lokal akan menghasilkan *input lag* ekstrem, membuat permainan bergenre aksi real-time menjadi tidak responsif.

Untuk menyelesaikan friksi antara otoritas penuh server dan responsivitas klien, tiga pilar arsitektur diterapkan:
1. **Client-Side Prediction**: Klien secara proaktif memprediksi hasil dari input lokal secara instan pada *frame* aktif sebelum server mengonfirmasi validitasnya.
2. **Server Reconciliation**: Ketika server mengirimkan *authoritative state* pada tick masa lalu yang tidak sesuai dengan *state* prediksi klien (misalnya terjadi benturan fisika atau koreksi validasi server), klien memundurkan (*rollback*) state lokal ke *state* valid server, lalu menyimulasikan ulang (*replay*) seluruh input yang belum diproses server hingga tick terkini.
3. **Snapshot Interpolation**: Untuk entitas non-lokal (pemain lain, proyektil, bot AI otonom), klien tidak memprediksi pergerakannya secara spekulatif melainkan merendernya dengan sedikit penundaan waktu (*interpolation delay*), menginterpolasikan posisi di antara dua *snapshot* historis yang telah diterima secara berurutan.

---

## 3. Why It Matters
Dalam ekosistem multiplayer kompetitif dan simulasi multi-agent otonom:
* **Integritas Kompetitif vs. Responsivitas**: Klien yang diizinkan menentukan posisinya sendiri sangat rentan terhadap eksploitasi seperti *speed hacks*, *teleportation*, dan *phase-walking*. Sebaliknya, arsitektur *dumb terminal* yang murni menunggu server menyebabkan *perceptual unresponsiveness* (gameplay terasa melayang atau tertahan).
* **AI & Autonomous Agents Interoperability**: Agen AI yang berjalan di server mengandalkan kondisi dunia yang deterministik dan sinkron. Jika server dan klien tidak terkalibrasi secara presisi, agen AI otonom akan mengeksekusi *pathfinding* dan penyerangan berbasis data spasial yang tidak valid terhadap persepsi visual pemain manusia.
* **Efisiensi Finansial & Bandwidth Enterprise**: Mengirimkan *full state* mentah dari ratusan entitas 60 kali per detik ke ribuan *concurrent users* (CCU) akan mengakibatkan lonjakan biaya *egress* cloud yang masif. Pengetahuan atas *delta compression* dan *state quantification* menjadi prasyarat krusial untuk menekan *operational expenditure* (OpEx).

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur pemrosesan input dari klien lokal, validasi pada server authoritative, hingga penanganan rendering entitas remote via *interpolation buffer*.

```
   CLIENT RUNTIME                                         SERVER RUNTIME
========================================================================================
[Player Input Engine]
        |
        +---> (1) Apply to Local Physics ---> Render immediately (Tick K)
        |
        +---> Record to [History Buffer] (Seq K, Input, State K)
        |
        +---> [UDP Packet: Input] ------------------------> [Input Ingestion Queue]
                                                                     |
                                                                     v
                                                            [Validation Engine]
                                                                     |
                                                            [Server Tick Loop]
                                                            Advance Physics (Tick N)
                                                                     |
                                                            [World Snapshot Gen]
                                                                     |
   <--------- [UDP Packet: Snapshot Tick N] ------------------------+
   |          (Ack Seq K-x, Position, Velocity)
   v
[Snapshot Ingestion]
   |
   +---> Is Local Entity?
   |        |
   |        +---> YES: [Reconciliation Engine]
   |        |           - Compare Snapshot(N) vs History(N)
   |        |           - Divergence > Threshold?
   |        |                NO  --> Discard historical input < N
   |        |                YES --> ROLLBACK state to N
   |        |                        REPLAY inputs from N+1 to K
   |        |                        Correct Local View
   |
   +---> Is Remote Entity / AI?
            |
            +---> YES: [Interpolation Buffer] (Jitter Buffer)
                        - Store Snapshot(N) with Timestamp
                        - Set Render Time = Current Time - InterpolationDelay
                        - Sample between Snapshot(A) and Snapshot(B)
                        - Output smoothly blended Transform to Renderer
========================================================================================
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Authoritative Tick Rate & Input Acknowledgment
Server beroperasi pada frekuensi pembaruan tetap (*fixed tick rate*), misalnya $60\text{ Hz}$ ($\Delta t \approx 16.66\text{ ms}$). Setiap *tick*, server memproses input yang masuk dari antrean, mengeksekusi simulasi fisik, mendeteksi collision, dan secara berkala (misal $20\text{-}30\text{ Hz}$) menyiarkan *world state snapshot* ke seluruh klien.

Klien melampirkan *Monotonically Increasing Sequence Number* pada setiap paket input:
$$\text{InputPacket} = \{ \text{SequenceNumber}, \Delta t, \vec{u}_{\text{input}} \}$$
Server memproses input tersebut dan menyematkan sequence number input terakhir yang dieksekusi ke dalam snapshot:
$$\text{SnapshotPacket} = \{ \text{ServerTick}, \text{LastAckedInputSeq}, \vec{x}_{\text{authoritative}}, \vec{v}_{\text{authoritative}} \}$$

### 5.2 Server Reconciliation (Rollback & Replay)
Ketika klien menerima snapshot dari server dengan $\text{LastAckedInputSeq} = i$:
1. Klien mencari $\text{PredictedState}_i$ pada cincin memori (*ring buffer*).
2. Menghitung error euclidean:
   $$\epsilon = \|\vec{x}_{\text{authoritative}, i} - \vec{x}_{\text{predicted}, i}\|$$
3. Jika $\epsilon > \text{DesyncThreshold}$ (misalnya akibat interaksi eksternal seperti dorongan dari agen AI atau tabrakan yang diabaikan klien):
   * State entitas lokal di-reset ke $\vec{x}_{\text{authoritative}, i}$.
   * Semua input dari sequence $i + 1$ hingga sequence terkini $k$ disimulasikan ulang secara deterministik dalam satu frame CPU:
     $$\vec{x}_{t} = f(\vec{x}_{t-1}, \text{Input}_t, \Delta t) \quad \forall t \in [i+1, k]$$
   * Error residual dihaluskan (*smoothed*) ke kamera untuk menghindari efek *snapping visual* (*rubber-banding*).

### 5.3 Snapshot Interpolation (Entity Interpolation)
Klien merender entitas lain dari data historis yang sudah divalidasi server. Untuk menjamin pergerakan yang kontinu di tengah variasi latensi (*jitter*), klien sengaja menunda waktu rendering (*render time*) sebesar $t_{\text{delay}}$:
$$t_{\text{render}} = t_{\text{client\_current}} - t_{\text{delay}}$$
Di mana $t_{\text{delay}} \ge 2 \times \text{TickInterval} + \text{NetworkJitter}$.

Klien mencari dua snapshot historis, $S_1$ dan $S_2$, sedemikian rupa sehingga:
$$S_1.\text{timestamp} \le t_{\text{render}} \le S_2.\text{timestamp}$$
Faktor interpolasi dinormalisasi:
$$\alpha = \frac{t_{\text{render}} - S_1.\text{timestamp}}{S_2.\text{timestamp} - S_1.\text{timestamp}}, \quad \alpha \in [0.0, 1.0]$$
Posisi akhir dihitung melalui *Linear Interpolation (LERP)* atau *Hermite Cubic Spline*:
$$\vec{x}_{\text{render}} = \text{LERP}(\vec{x}_{S_1}, \vec{x}_{S_2}, \alpha) = (1 - \alpha)\vec{x}_{S_1} + \alpha\vec{x}_{S_2}$$
Rotasi disinkronkan melalui *Spherical Linear Interpolation (SLERP)* pada kuaternion untuk mencegah distorsi gimbal lock:
$$q_{\text{render}} = \text{SLERP}(q_{S_1}, q_{S_2}, \alpha)$$

Jika paket terhenti hingga $t_{\text{render}} > S_2.\text{timestamp}$, sistem beralih ke mode **Extrapolation (Dead Reckoning)**:
$$\vec{x}_{\text{extrapolated}} = \vec{x}_{S_2} + \vec{v}_{S_2} \cdot (t_{\text{render}} - S_2.\text{timestamp})$$

---

## 6. Production-Ready Code Implementation

Berikut implementasi lengkap pipeline sinkronisasi authoritative state dalam bahasa Go. Arsitektur ini mencakup *Server Physics Loop*, *Client Prediction Buffer*, *Server Reconciliation Engine*, dan *Snapshot Interpolator*.

```go
package main

import (
	"errors"
	"fmt"
	"math"
	"sync"
	"time"
)

// --- Domain Models & Vectors ---

type Vector2 struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
}

func (v Vector2) Add(o Vector2) Vector2 {
	return Vector2{X: v.X + o.X, Y: v.Y + o.Y}
}

func (v Vector2) Sub(o Vector2) Vector2 {
	return Vector2{X: v.X - o.X, Y: v.Y - o.Y}
}

func (v Vector2) Scale(s float64) Vector2 {
	return Vector2{X: v.X * s, Y: v.Y * s}
}

func (v Vector2) Length() float64 {
	return math.Sqrt(v.X*v.X + v.Y*v.Y)
}

func LerpVector2(a, b Vector2, alpha float64) Vector2 {
	return a.Add(b.Sub(a).Scale(alpha))
}

type UserInput struct {
	Sequence uint64  `json:"sequence"`
	DeltaTime float64 `json:"delta_time"`
	Direction Vector2 `json:"direction"` // Normalized input direction
}

type EntityState struct {
	Position Vector2 `json:"position"`
	Velocity Vector2 `json:"velocity"`
}

type Snapshot struct {
	Tick               uint64      `json:"tick"`
	Timestamp          float64     `json:"timestamp"`
	LastProcessedInput uint64      `json:"last_processed_input"`
	State              EntityState `json:"state"`
}

// --- Physics Logic (Deterministic Subsystem) ---

const (
	PlayerSpeed        = 100.0 // Units per second
	DesyncThresholdSq = 0.0001 // Position error threshold squared
	HistoryBufferSize  = 256
)

func AdvanceSimulation(current EntityState, input UserInput) EntityState {
	// Normalize input direction defensively
	dir := input.Direction
	mag := dir.Length()
	if mag > 1.0 {
		dir = dir.Scale(1.0 / mag)
	}

	vel := dir.Scale(PlayerSpeed)
	pos := current.Position.Add(vel.Scale(input.DeltaTime))

	return EntityState{
		Position: pos,
		Velocity: vel,
	}
}

// --- Authoritative Server Simulation ---

type ServerWorld struct {
	mu           sync.RWMutex
	currentTick  uint64
	state        EntityState
	inputQueue   []UserInput
	latestAckSeq uint64
}

func NewServerWorld(initialPos Vector2) *ServerWorld {
	return &ServerWorld{
		state: EntityState{Position: initialPos},
	}
}

func (s *ServerWorld) EnqueueInput(input UserInput) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.inputQueue = append(s.inputQueue, input)
}

func (s *ServerWorld) Tick(dt float64) Snapshot {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.currentTick++

	// Process all queued client inputs
	for _, input := range s.inputQueue {
		s.state = AdvanceSimulation(s.state, input)
		s.latestAckSeq = input.Sequence
	}
	s.inputQueue = s.inputQueue[:0] // Clear queue

	return Snapshot{
		Tick:               s.currentTick,
		Timestamp:          float64(s.currentTick) * dt,
		LastProcessedInput: s.latestAckSeq,
		State:              s.state,
	}
}

// --- Client System (Prediction, Reconciliation & Interpolation) ---

type PredictionRecord struct {
	Sequence uint64
	Input    UserInput
	State    EntityState
}

type ClientPredictor struct {
	mu            sync.Mutex
	currentState  EntityState
	inputSequence uint64
	historyBuffer []PredictionRecord
}

func NewClientPredictor(startPos Vector2) *ClientPredictor {
	return &ClientPredictor{
		currentState:  EntityState{Position: startPos},
		historyBuffer: make([]PredictionRecord, 0, HistoryBufferSize),
	}
}

// PredictLocalMovement calculates local physics immediately
func (c *ClientPredictor) PredictLocalMovement(dir Vector2, dt float64) UserInput {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.inputSequence++
	input := UserInput{
		Sequence:  c.inputSequence,
		DeltaTime: dt,
		Direction: dir,
	}

	c.currentState = AdvanceSimulation(c.currentState, input)

	record := PredictionRecord{
		Sequence: c.inputSequence,
		Input:    input,
		State:    c.currentState,
	}

	if len(c.historyBuffer) >= HistoryBufferSize {
		c.historyBuffer = c.historyBuffer[1:]
	}
	c.historyBuffer = append(c.historyBuffer, record)

	return input
}

// Reconcile evaluates server authority and re-runs inputs if state drifted
func (c *ClientPredictor) Reconcile(snapshot Snapshot) (bool, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	ackSeq := snapshot.LastProcessedInput
	if ackSeq == 0 {
		return false, nil
	}

	// Locate historical state for ackSeq
	matchIdx := -1
	for i, record := range c.historyBuffer {
		if record.Sequence == ackSeq {
			matchIdx = i
			break
		}
	}

	// If sequence is not in buffer, historical state was already discarded
	if matchIdx == -1 {
		return false, errors.New("ack sequence evicted from history buffer or out of order")
	}

	predictedAtTick := c.historyBuffer[matchIdx].State
	diffX := snapshot.State.Position.X - predictedAtTick.Position.X
	diffY := snapshot.State.Position.Y - predictedAtTick.Position.Y
	errSq := diffX*diffX + diffY*diffY

	if errSq <= DesyncThresholdSq {
		// Prediction correct within margin: prune old history
		c.historyBuffer = c.historyBuffer[matchIdx+1:]
		return false, nil
	}

	// Divergence detected: Rollback & Replay
	rewoundState := snapshot.State
	replayInputs := c.historyBuffer[matchIdx+1:]

	for i, record := range replayInputs {
		rewoundState = AdvanceSimulation(rewoundState, record.Input)
		replayInputs[i].State = rewoundState
	}

	c.currentState = rewoundState
	c.historyBuffer = replayInputs
	return true, nil
}

func (c *ClientPredictor) GetCurrentState() EntityState {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.currentState
}

// --- Remote Entity Snapshot Interpolator ---

type InterpolationBuffer struct {
	mu        sync.RWMutex
	snapshots []Snapshot
}

func NewInterpolationBuffer() *InterpolationBuffer {
	return &InterpolationBuffer{
		snapshots: make([]Snapshot, 0, 32),
	}
}

func (b *InterpolationBuffer) AddSnapshot(s Snapshot) {
	b.mu.Lock()
	defer b.mu.Unlock()

	// Keep sorted by tick
	if len(b.snapshots) > 0 && s.Tick <= b.snapshots[len(b.snapshots)-1].Tick {
		return // Drop old/duplicate packets
	}
	b.snapshots = append(b.snapshots, s)

	// Keep buffer constrained
	if len(b.snapshots) > 30 {
		b.snapshots = b.snapshots[1:]
	}
}

func (b *InterpolationBuffer) SampleState(renderTime float64) (EntityState, error) {
	b.mu.RLock()
	defer b.mu.RUnlock()

	if len(b.snapshots) == 0 {
		return EntityState{}, errors.New("no snapshots available")
	}

	// Edge case 1: Render time is older than the oldest snapshot
	if renderTime <= b.snapshots[0].Timestamp {
		return b.snapshots[0].State, nil
	}

	// Edge case 2: Render time surpasses newest snapshot (Extrapolation)
	newest := b.snapshots[len(b.snapshots)-1]
	if renderTime >= newest.Timestamp {
		extrapolationDelta := renderTime - newest.Timestamp
		pos := newest.State.Position.Add(newest.State.Velocity.Scale(extrapolationDelta))
		return EntityState{Position: pos, Velocity: newest.State.Velocity}, nil
	}

	// Normal Case: Find bounding snapshots for interpolation
	for i := 0; i < len(b.snapshots)-1; i++ {
		s0 := b.snapshots[i]
		s1 := b.snapshots[i+1]

		if s0.Timestamp <= renderTime && renderTime <= s1.Timestamp {
			span := s1.Timestamp - s0.Timestamp
			if span == 0 {
				return s0.State, nil
			}
			alpha := (renderTime - s0.Timestamp) / span
			interpolatedPos := LerpVector2(s0.State.Position, s1.State.Position, alpha)
			interpolatedVel := LerpVector2(s0.State.Velocity, s1.State.Velocity, alpha)

			return EntityState{
				Position: interpolatedPos,
				Velocity: interpolatedVel,
			}, nil
		}
	}

	return newest.State, nil
}

// --- Main Verification Entrypoint ---

func main() {
	const fixedDt = 1.0 / 60.0 // 60Hz tick
	server := NewServerWorld(Vector2{X: 0, Y: 0})
	client := NewClientPredictor(Vector2{X: 0, Y: 0})
	interpBuffer := NewInterpolationBuffer()

	fmt.Println("=== Initializing Simulation State Synchronization ===")

	// 1. Simulate 3 consecutive frames of local client input
	var sentInputs []UserInput
	for i := 0; i < 3; i++ {
		input := client.PredictLocalMovement(Vector2{X: 1, Y: 0}, fixedDt)
		sentInputs = append(sentInputs, input)
	}

	fmt.Printf("Client predicted state after 3 frames: Pos = {X: %.4f, Y: %.4f}\n",
		client.GetCurrentState().Position.X, client.GetCurrentState().Position.Y)

	// 2. Server receives inputs with latency and executes tick
	for _, in := range sentInputs {
		server.EnqueueInput(in)
	}
	serverSnap := server.Tick(fixedDt)

	fmt.Printf("Server state generated at Tick %d: Pos = {X: %.4f, Y: %.4f}\n",
		serverSnap.Tick, serverSnap.State.Position.X, serverSnap.State.Position.Y)

	// 3. Client processes reconciliation
	reconciled, err := client.Reconcile(serverSnap)
	if err != nil {
		fmt.Printf("Reconciliation error: %v\n", err)
	} else {
		fmt.Printf("Reconciliation executed. Divergence detected: %t, Final Pos: {X: %.4f, Y: %.4f}\n",
			reconciled, client.GetCurrentState().Position.X, client.GetCurrentState().Position.Y)
	}

	// 4. Remote Entity Snapshot Interpolation Demonstration
	interpBuffer.AddSnapshot(Snapshot{Tick: 1, Timestamp: 0.00, State: EntityState{Position: Vector2{X: 0, Y: 0}, Velocity: Vector2{X: 10, Y: 0}}})
	interpBuffer.AddSnapshot(Snapshot{Tick: 2, Timestamp: 0.05, State: EntityState{Position: Vector2{X: 0.5, Y: 0}, Velocity: Vector2{X: 10, Y: 0}}})
	interpBuffer.AddSnapshot(Snapshot{Tick: 3, Timestamp: 0.10, State: EntityState{Position: Vector2{X: 1.0, Y: 0}, Velocity: Vector2{X: 10, Y: 0}}})

	// Sample at target render time = 0.075s (midway between Tick 2 and Tick 3)
	sampleTarget := 0.075
	sampledState, _ := interpBuffer.SampleState(sampleTarget)

	fmt.Printf("Sampled Remote Entity at t=%.3fs: Pos = {X: %.4f, Y: %.4f} (Expected: X=0.7500)\n",
		sampleTarget, sampledState.Position.X, sampledState.Position.Y)
}
```

---

## 7. Edge Cases & Failure Modes

| Edge Case / Failure Mode | Akar Penyebab (*Root Cause*) | Mitigasi Arsitektural / Production Fallback |
| :--- | :--- | :--- |
| **Visual Snapping (Rubber-Banding)** | Rekonsiliasi mengubah posisi lokal secara drastis setelah terjadi divergensi akibat tabrakan lingkungan. | **Error Decay / Smoothing**: Alih-alih melakukan *teleport* instan, hitung vektor selisih $\vec{e} = \vec{x}_{\text{corrected}} - \vec{x}_{\text{visual}}$ dan terapkan peluruhan eksponensial (*exponential decay*) ke visual mesh selama $100\text{-}150\text{ ms}$, sementara sistem fisika tetap mengadopsi posisi terkoreksi. |
| **Desync Drift (Floating-Point Non-Determinism)** | Perbedaan arsitektur prosesor (x86 SSE vs ARM NEON) mengeksekusi operasi floating-point dengan pembulatan berbeda (*IEEE 754 precision drift*). | **Fixed-Point Arithmetic**: Gunakan representasi bilangan *fixed-point integer* (misal: format `Q24.8` atau `Q16.16`) pada modul simulasi fisika inti server dan klien lokal untuk menjamin determinisme 100%. |
| **Input Buffer Saturation (Speed Hack Attempt)** | Klien yang dimodifikasi mengirimkan paket input dengan frekuensi lebih cepat daripada interval *delta time* nyata untuk memacu kecepatan gerak. | **Token Bucket Rate Limiting & Input Clamping**: Server memvalidasi bahwa total akumulasi $\sum \Delta t_{\text{input}}$ per detik tidak melebihi alokasi waktu fisik server ($1.0\text{ s} \pm \text{toleransi drift } 5\%$). Input yang berlebih otomatis di-drop. |
| **Snapshot Starvation / Jitter Spike** | Fluktuasi jaringan membuat paket snapshot datang terlambat melewati batas jendela *interpolation buffer*. | **Adaptive Jitter Buffer & Extrapolation**: Ukuran delay interpolasi ($t_{\text{delay}}$) ditingkatkan secara dinamis berbasis moving average latency. Jika kelaparan paket berlanjut, aktifkan *dead reckoning* maksimum sepanjang $250\text{ ms}$; jika terlampaui, entitas dibekukan (*freeze*) sementara. |
| **Sequence Number Overflow** | Simulasi berjalan sangat lama sehingga integer counter pada `uint32` atau `uint16` meluap (*wrap-around*). | **Sequence Wrapping Arithmetic**: Gunakan fungsi pembanding modul: `bool IsNewer(uint16_t s1, uint16_t s2) { return (s1 > s2) && (s1 - s2 < 32768) || (s1 < s2) && (s2 - s1 > 32768); }`. Gunakan `uint64` untuk durasi server tanpa wrap-around teoritis selama ribuan tahun. |

---

## 8. Trade-offs & Alternatif Solusi

Setiap paradigma sinkronisasi mengharuskan kompromi antara responsivitas, konsumsi bandwidth, pemanfaatan CPU, dan kerentanan eksploitasi:

```
+---------------------------------------------------------------------------------------+
| ARCHITECTURE COMPARISON MATRIX                                                        |
+------------------------------------+----------------+-----------------+---------------+
| Metrik / Karakteristik             | Deterministic  | Snapshot        | Client Auth + |
|                                    | Lockstep       | Interpolation   | Server Check  |
+------------------------------------+----------------+-----------------+---------------+
| Bandwidth Footprint                | Ultra Rendah   | Tinggi          | Moderat       |
| Latency Sensitivity (Input Lag)    | Sangat Tinggi  | Sangat Rendah   | Sangat Rendah |
| Server CPU Load                    | Minimal        | Sangat Tinggi   | Rendah        |
| Anti-Cheat Capability             | Sempurna       | Superior        | Rapuh         |
| Cocok untuk Skala Entitas Besar    | Ya (RTS)       | Tidak (Tergelak)| Ya            |
| Dukungan Drop-in/Late-join Klien   | Sangat Sulit   | Sangat Mudah    | Moderat       |
+------------------------------------+----------------+-----------------+---------------+
```

### Kapan Menggunakan Snapshot Interpolation vs Lockstep?
1. **Pilih Deterministic Lockstep (RTS/Turn-Based/Fighting Games)**:
   * Ketika terdapat ribuan unit yang harus disinkronkan secara simultan (misalnya *StarCraft* atau *Age of Empires*). Mengirim snapshot posisi ribuan entitas melampaui limit bandwidth broadband. Klien hanya mengirimkan input perintah aksi pemain, sementara state disimulasikan secara paralel di setiap klien secara deterministik.
2. **Pilih Snapshot Interpolation + Client Prediction (FPS, TPS, Action-RPG)**:
   * Ketika game menuntut *zero perceptual latency* pada kontrol kamera dan gerakan instan 1 karakter, dan server bertindak sebagai entitas fisik yang memvalidasi hit registration (*lag compensation / server rewinding*).

---

## 9. Best Practices & Standard Industri

* **State Quantization**: Jangan pernah mentransmisikan *float* 32-bit mentah jika tidak diperlukan. Posisikan dunia dalam koordinat terbatas, misalnya dari rentang $[-1000.0, 1000.0]$:
  $$\text{QuantizedInt16} = \text{uint16}\left( \frac{\text{Pos} - \text{Min}}{\text{Max} - \text{Min}} \times 65535 \right)$$
  Langkah ini menghemat pemakaian bandwidth transform spasial hingga $50\%$.
* **Delta Snapshots (Delta Compression)**: Implementasikan representasi bitmask (*dirty bits*) untuk mengidentifikasi properti entitas mana yang berubah dibandingkan *baseline acked tick*. Jika entitas diam, payload yang ditransmisikan mendekati nol byte.
* **Jitter Buffer Sizing Policy**: Tetapkan ukuran jitter buffer secara dinamis menggunakan nilai persentil ke-99 ($p_{99}$) RTT:
  $$t_{\text{interp\_delay}} = \mu_{\text{RTT}} + 3 \times \sigma_{\text{jitter}} + \Delta t_{\text{tick}}$$
* **Clock Synchronization via EMA**: Lakukan sinkronisasi waktu jaringan klien-ke-server menggunakan algoritma turunan NTP dengan *Exponential Moving Average* (EMA):
  $$\text{Offset}_{\text{filtered}} = (1 - \alpha) \cdot \text{Offset}_{\text{old}} + \alpha \cdot \text{Offset}_{\text{sample}}, \quad \alpha \approx 0.1$$
* **Multi-agent AI Replication Decoupling**: Untuk agen AI otonom di server, jangan kirimkan snapshot dengan tick rate yang sama dengan pemain. Jalankan sinkronisasi AI pada frekuensi dinamis berdasarkan kedekatan jarak (*Proximity-based Spatial Hashing / Interest Management*). Bot AI yang berada jauh dari pemain lokal dapat diperbarui pada frekuensi $5\text{-}10\text{ Hz}$ dan dihaluskan melalui interpolasi spline di klien.

---

## 10. Hands-on Lab Exercise

### Skenario Lab
Anda ditugaskan memverifikasi ketahanan sistem rekonsiliasi server ketika klien mengalami degradasi jaringan artifisial, serta mendemonstrasikan koreksi otomatis divergensi state saat klien salah memprediksi akibat rintangan tak terlihat (*server-side boundary collision*).

### Setup Petunjuk Langkah demi Langkah
1. Salin implementasi Go dari Bagian 6 ke dalam direktori lokal: `workspace/sync_lab/main.go`.
2. Modifikasi loop eksekusi utama (`main`) untuk menambahkan simulasi *Network Latency Buffer* dan skenario benturan (*Collision Injection*).

```go
// Tambahkan skenario pengujian di main.go:
func runDesyncExperiment() {
	fixedDt := 1.0 / 60.0
	server := NewServerWorld(Vector2{X: 0, Y: 0})
	client := NewClientPredictor(Vector2{X: 0, Y: 0})

	fmt.Println("\n--- LAB EXPERIMENT: Server Collision Correction Test ---")

	// Frame 1-5: Klien bergerak bebas ke kanan (X: 1, Y: 0)
	var networkPipe []UserInput
	for frame := 1; frame <= 5; frame++ {
		input := client.PredictLocalMovement(Vector2{X: 1, Y: 0}, fixedDt)
		networkPipe = append(networkPipe, input)
	}

	fmt.Printf("[Client] Posisi sebelum koreksi: X=%.4f\n", client.GetCurrentState().Position.X)

	// Server memproses frame, namun pada Frame 3, server mendeteksi dinding tak terlihat di X=3.0
	// yang membatasi posisi maksimal ke 3.0 (Klien tidak tahu ada dinding ini)
	for _, input := range networkPipe {
		server.EnqueueInput(input)
		// Inject Server Collision Hook
		if server.state.Position.X > 3.0 {
			server.state.Position.X = 3.0
		}
	}
	serverSnapshot := server.Tick(fixedDt)
	fmt.Printf("[Server] Authoritative Snapshot State: X=%.4f (Terdampak Dinding)\n", serverSnapshot.State.Position.X)

	// Client menerima snapshot server dan memproses rekonsiliasi
	diverged, err := client.Reconcile(serverSnapshot)
	if err != nil {
		panic(err)
	}

	fmt.Printf("[Client] Divergensi terdeteksi: %t\n", diverged)
	fmt.Printf("[Client] Posisi lokal setelah Reconcile & Replay: X=%.4f\n", client.GetCurrentState().Position.X)

	// Verifikasi Validasi Kriteria Sukses
	if math.Abs(client.GetCurrentState().Position.X-3.0) < 0.001 {
		fmt.Println(">> LAB STATUS: SUCCESS - Client berhasil merekonsiliasi posisi sesuai batas server!")
	} else {
		fmt.Println(">> LAB STATUS: FAILED - State desinkronisasi berlanjut!")
	}
}
```

3. Jalankan program dengan perintah:
   ```bash
   go run main.go
   ```
4. **Analisis Hasil**: Perhatikan bagaimana klien memundurkan koordinatnya kembali ke koordinat `3.0` dan memutar ulang input berikutnya dengan titik awal yang telah dikoreksi secara akurat tanpa manipulasi state ilegal.