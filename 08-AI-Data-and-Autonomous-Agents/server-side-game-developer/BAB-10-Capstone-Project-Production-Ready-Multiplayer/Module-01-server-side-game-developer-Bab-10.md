# Bab 10: Capstone Project Production-Ready Multiplayer Battle Arena Engine
## Module 01: Core Authoritative Engine, Spatial Partitioning, & Autonomous Agent Architecture

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Mengimplementasikan** *fixed-timestep authoritative game loop* (60 Hz / 30 Hz) menggunakan Go dengan *drift compensation* dan akurasi deviasi waktu $< 0.5\%$.
- **Merancang dan membangun** sistem partisi spasial berbasis *Uniform Dynamic Grid* untuk mereduksi kompleksitas pencarian tetangga dan deteksi benturan agent dari $O(N^2)$ menjadi rata-rata $O(1)$ amortized per entitas.
- **Mengintegrasikan** *Autonomous Agent Brain* berbasis *Utility AI System* yang mampu mengeksekusi siklus persepsi, evaluasi skor utilitas, dan eksekusi aksi deterministik pada skala 500+ agent per node komputasi tanpa melebihi batas *frame budget* 16.6ms.
- **Menganalisis dan mengisolasi** kegagalan *sub-tick* (seperti NaN/Infinite coordinates, thread-safety panic, dan heap allocations bottleneck) melalui implementasi *defensive zero-allocation design patterns*.
- **Mengevaluasi** metrik performa engine melalui instrumentasi terdistribusi (p95 dan p99 *tick duration*, *memory allocations per tick*, serta *spatial cache-hit ratio*).

---

### 2. Concept Overview (Mental Model & Teori Inti)

Membangun engine arena multi-pemain dengan AI otonom menuntut kontrol penuh atas determinisme status, latensi, dan skalabilitas komputasi server. Berbeda dengan aplikasi web berbasis request-response standar I/O-bound, *dedicated game server* (DGS) adalah sistem yang sangat *CPU-bound* dan *memory-latency sensitive*.

```
+-------------------------------------------------------------------------+
|                        AUTHORITATIVE TICK LOOP                          |
|                                                                         |
|  [Accumulator += DeltaTime]                                             |
|           |                                                             |
|           v                                                             |
|  +-------------------------------------------------------------------+  |
|  | WHILE (Accumulator >= FixedDeltaTime):                            |  |
|  |   1. Ingest & Validate Input (Client Packets & Agent Intents)     |  |
|  |   2. Update Spatial Partitioning (Dynamic Bucket Reassignment)   |  |
|  |   3. Tick Autonomous Agents (Perception -> Utility -> Action)     |  |
|  |   4. Resolve Combat & Physics (Raycasts, Hitboxes, Collision)     |  |
|  |   5. Commit State & Advance Monotonic Tick Sequence               |  |
|  |   6. Accumulator -= FixedDeltaTime                                |  |
|  +-------------------------------------------------------------------+  |
|           |                                                             |
|           v                                                             |
|  [Generate State Snapshot / Delta Compression for Replication]         |
+-------------------------------------------------------------------------+
```

#### Mental Model: The Authoritative World State Pipeline
1. **Authoritative Simulation**: Klien hanya mengirimkan intensi (*input command*). Server mengabaikan koordinat yang dilaporkan klien, menghitung seluruh status fisika, menangani pergerakan, dan mengevaluasi kalkulasi damage. AI Agent di server diperlakukan sebagai entitas lokal dengan antarmuka input yang setara dengan pemain manusia.
2. **Fixed-Timestep Tick Architecture**: Simulasi berjalan menggunakan interval waktu konstan ($\Delta t$, misal 16.66ms untuk 60 Hz). Pendekatan ini menghilangkan variabilitas numerik akibat floating-point instability yang biasa terjadi pada delta time dinamis.
3. **Spatial Awareness Budgeting**: Membiarkan ratusan agent memeriksa seluruh agent lain di arena ($O(N^2)$) akan melumpuhkan CPU. *Spatial partitioning* membatasi evaluasi persepsi dan *hit-testing* hanya ke sel grid lokal terdekat ($O(K)$, di mana $K$ adalah densitas lokal entitas).
4. **Decoupled Perception-Action Frequency**: Agen tidak perlu mengevaluasi *brain utility* di setiap tick. Eksekusi fisika berjalan pada 60 Hz, sementara *decision-making* agen diturunkan (*time-sliced*) ke 10 Hz atau 5 Hz untuk menjaga anggaran CPU (*CPU budget*).

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Di lingkungan produksi berskala enterprise (misal: MOBA 5v5 dengan ratusan minion/neutral creeps, atau battle royale berukuran kecil yang diisi AI bot adaptif):
- **Server Death Spiral**: Jika kalkulasi loop memakan waktu lebih lama dari alokasi tick (misal 22ms pada tick 16.6ms), accumulator internal server akan terus bertambah. Hal ini memicu loop yang tak berujung (*tick starvation*), lonjakan latensi (*lag spikes*), dan akhirnya pemutusan koneksi massal pemain (*crash/timeout*).
- **Algorithmic Catastrophe ($O(N^2)$)**: 100 entitas membutuhkan $10.000$ operasi kalkulasi jarak per tick. Pada 1000 entitas, nilainya melonjak menjadi $1.000.000$ operasi per tick. Pada 60 tick per detik, ini setara dengan 60 juta evaluasi floating-point per detik hanya untuk memeriksa "siapa di dekat saya". Tanpa partisi spasial, server kolaps sebelum kalkulasi logika tempur sempat dijalankan.
- **Non-Deterministic Edge Exploits**: Implementasi AI yang lambat atau tidak terkoordinasi dengan loop utama server membuka celah eksploitasi, seperti *state desync*, desinkronisasi animasi-ke-hitbox, dan kerentanan packet injection pada simulasi status agen.

---

### 4. Arsitektur & Diagram Komponen

```
                  +----------------------------------------------+
                  |               OS Monotonic Clock             |
                  +----------------------------------------------+
                                         |
                                         v
                  +----------------------------------------------+
                  |              Engine Core Loop                |
                  |     (Time Accumulator / Drift Manager)       |
                  +----------------------------------------------+
                                         |
         +-------------------------------+-------------------------------+
         |                               |                               |
         v                               v                               v
+------------------+           +-------------------+           +-------------------+
|  Spatial Grid    |<--------->| Autonomous Agent  |<--------->|   Combat Engine   |
|  (2D Flat Array) |           |  Brain Subsystem  |           | (Resolver/Damage) |
+------------------+           +-------------------+           +-------------------+
         ^                               |                               |
         | Read/Update Position          | Evaluates Utility / Queries   | Writes Health/
         |                               | Surrounding Targets           | State Flags
         |                               v                               |
+----------------------------------------------------------------------------------+
|                             Authoritative World State                            |
|             (Thread-Safe Flat Entity Storage, Component Buffers)                 |
+----------------------------------------------------------------------------------+
                                         |
                                         v
                  +----------------------------------------------+
                  |       Delta State / Snapshot Generator       |
                  |     (Output to Network Replication Layer)    |
                  +----------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. High-Frequency Fixed-Timestep Loop & Drift Management
Sistem operasi tidak menjamin `time.Sleep()` berjalan secara presisi. `time.Sleep(16 * time.Millisecond)` dapat diblokir oleh scheduler OS selama 18-24ms tergantung beban CPU. 
Untuk mengatasi hal ini, loop engine menggunakan kombinasi:
1. Akumulasi berbasis monotonic clock (`time.Now()` / `time.Since()`).
2. Konsumsi delta konstan dalam loop internal `for accumulator >= fixedDelta`.
3. Mekanisme *clamping* pada akumulator (*Spiral-of-Death Protection*): jika akumulator melampaui ambang batas maksimum (misal 100ms atau ~6 ticks), engine memotong akumulator dan mengeluarkan peringatan performa (drop ticks).

#### B. Dynamic Spatial Hash Grid
Alih-alih menggunakan tree dinamis (seperti Quadtree/BVH) yang memerlukan alokasi heap pointer kontinu dan rebalancing kompleks, *Flat Uniform Spatial Grid* menggunakan hashing berbasis array dimensi datar:
- Dunia dibagi menjadi grid dengan ukuran sel berdimensi $C$ (misal $10 \times 10$ meter, disesuaikan dengan radius penglihatan/interaksi agen).
- Indeks sel dihitung dengan rumus:
  $$\text{CellX} = \lfloor X / C \rfloor, \quad \text{CellY} = \lfloor Y / C \rfloor$$
  $$\text{CellIndex} = \text{CellY} \times \text{GridWidth} + \text{CellX}$$
- Sel menyimpan slice identitas entitas. Ketika entitas berpindah sel, ia dihapus dari sel lama dan didaftarkan ke sel baru. Kueri radius hanya mengecek sel tempat entitas berada dan 8 sel tetangganya.

#### C. Autonomous Utility AI System
Utility AI bekerja berdasarkan kurva respons (*response curves*):
1. **Sensors/Perception**: Mengumpulkan fakta dari dunia melalui kueri spasial (misal: jarak ke musuh terdekat, persentase HP saat ini, jarak ke base).
2. **Considerations & Normalization**: Mengubah fakta mentah menjadi skor ternormalisasi $[0.0, 1.0]$.
3. **Utility Scoring**: Menggabungkan skor pertimbangan menggunakan bobot atau perkalian geometris:
   $$Score = \prod_{i=1}^{M} C_i$$
4. **Action Selection**: Aksi dengan skor tertinggi memenangkan hak kontrol entitas pada tick tersebut (*Attack*, *Retreat*, *Patrol*, *EngageSkill*).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi modul engine lengkap dan fungsional menggunakan **Go**. Mengedepankan *zero-allocation patterns*, *type safety*, pemanfaatan thread-concurrency yang aman, serta penanganan error bertaraf enterprise.

```go
// Package engine mengimplementasikan core battle arena loop, spatial grid, dan utility-based AI.
package engine

import (
	"context"
	"errors"
	"fmt"
	"math"
	"sync"
	"sync/atomic"
	"time"
)

// --- MATH & PRIMITIVES ---

type Vector2 struct {
	X float64
	Y float64
}

func (v Vector2) DistanceSquared(other Vector2) float64 {
	dx := v.X - other.X
	dy := v.Y - other.Y
	return dx*dx + dy*dy
}

func (v Vector2) Distance(other Vector2) float64 {
	return math.Sqrt(v.DistanceSquared(other))
}

func (v Vector2) Sub(other Vector2) Vector2 {
	return Vector2{X: v.X - other.X, Y: v.Y - other.Y}
}

func (v Vector2) Normalize() Vector2 {
	m := math.Hypot(v.X, v.Y)
	if m == 0 {
		return Vector2{0, 0}
	}
	return Vector2{X: v.X / m, Y: v.Y / m}
}

// --- ENTITY & STATE DEFINITION ---

type EntityType uint8

const (
	TypePlayer EntityType = iota
	TypeMinion
	TypeBoss
)

type EntityState struct {
	ID        uint32
	Type      EntityType
	Position  Vector2
	Velocity  Vector2
	MaxHealth float64
	Health    float64
	Speed     float64
	AttackRange float64
	Damage    float64
	TargetID  uint32
	IsDead    bool
}

// --- UNIFORM SPATIAL GRID ---

var (
	ErrOutOfBounds = errors.New("entity position is out of grid boundaries")
	ErrEntityNull  = errors.New("entity pointer cannot be nil")
)

type SpatialGrid struct {
	mu         sync.RWMutex
	cellSize   float64
	width      int
	height     int
	worldWidth float64
	worldHeight float64
	cells      [][]uint32 // Flat array indexing: index = y * width + x
}

func NewSpatialGrid(worldWidth, worldHeight, cellSize float64) *SpatialGrid {
	w := int(math.Ceil(worldWidth / cellSize))
	h := int(math.Ceil(worldHeight / cellSize))
	cells := make([][]uint32, w*h)
	for i := range cells {
		cells[i] = make([]uint32, 0, 16) // Pre-allocate capacity per bucket
	}
	return &SpatialGrid{
		cellSize:    cellSize,
		width:       w,
		height:      h,
		worldWidth:  worldWidth,
		worldHeight: worldHeight,
		cells:       cells,
	}
}

func (g *SpatialGrid) getCellIndex(pos Vector2) (int, error) {
	if pos.X < 0 || pos.X >= g.worldWidth || pos.Y < 0 || pos.Y >= g.worldHeight {
		return -1, ErrOutOfBounds
	}
	cx := int(pos.X / g.cellSize)
	cy := int(pos.Y / g.cellSize)
	if cx >= g.width {
		cx = g.width - 1
	}
	if cy >= g.height {
		cy = g.height - 1
	}
	return cy*g.width + cx, nil
}

func (g *SpatialGrid) Insert(id uint32, pos Vector2) error {
	idx, err := g.getCellIndex(pos)
	if err != nil {
		return err
	}

	g.mu.Lock()
	defer g.mu.Unlock()
	g.cells[idx] = append(g.cells[idx], id)
	return nil
}

func (g *SpatialGrid) Update(id uint32, oldPos, newPos Vector2) error {
	oldIdx, err1 := g.getCellIndex(oldPos)
	newIdx, err2 := g.getCellIndex(newPos)

	if err1 != nil || err2 != nil {
		return ErrOutOfBounds
	}

	if oldIdx == newIdx {
		return nil // Still within the same spatial bucket
	}

	g.mu.Lock()
	defer g.mu.Unlock()

	// Remove from old
	oldBucket := g.cells[oldIdx]
	for i, entityID := range oldBucket {
		if entityID == id {
			g.cells[oldIdx] = append(oldBucket[:i], oldBucket[i+1:]...)
			break
		}
	}
	// Append to new
	g.cells[newIdx] = append(g.cells[newIdx], id)
	return nil
}

func (g *SpatialGrid) QueryNearby(pos Vector2, radius float64, outIDs *[]uint32) {
	*outIDs = (*outIDs)[:0] // Zero allocation reuse
	minX := int(math.Max(0, math.Floor((pos.X-radius)/g.cellSize)))
	maxX := int(math.Min(float64(g.width-1), math.Floor((pos.X+radius)/g.cellSize)))
	minY := int(math.Max(0, math.Floor((pos.Y-radius)/g.cellSize)))
	maxY := int(math.Min(float64(g.height-1), math.Floor((pos.Y+radius)/g.cellSize)))

	g.mu.RLock()
	defer g.mu.RUnlock()

	for y := minY; y <= maxY; y++ {
		row := y * g.width
		for x := minX; x <= maxX; x++ {
			cellIdx := row + x
			*outIDs = append(*outIDs, g.cells[cellIdx]...)
		}
	}
}

// --- UTILITY AI SYSTEM ---

type ActionType string

const (
	ActionIdle   ActionType = "IDLE"
	ActionAttack ActionType = "ATTACK"
	ActionFlee   ActionType = "FLEE"
	ActionChase  ActionType = "CHASE"
)

type UtilityBrain struct {
	DecisionCooldown time.Duration
	LastEvaluated    time.Time
	CurrentAction    ActionType
}

func (b *UtilityBrain) Evaluate(self *EntityState, world *World) ActionType {
	if self.IsDead {
		b.CurrentAction = ActionIdle
		return ActionIdle
	}

	// Fact 1: Health Ratio [0.0 - 1.0]
	healthRatio := self.Health / self.MaxHealth

	// Fact 2: Nearest Enemy
	nearbyIDs := make([]uint32, 0, 32)
	world.Grid.QueryNearby(self.Position, 25.0, &nearbyIDs)

	var nearestEnemy *EntityState
	lowestDistSq := math.MaxFloat64

	for _, id := range nearbyIDs {
		if id == self.ID {
			continue
		}
		target := world.GetEntity(id)
		if target == nil || target.IsDead || target.Type == self.Type {
			continue
		}

		distSq := self.Position.DistanceSquared(target.Position)
		if distSq < lowestDistSq {
			lowestDistSq = distSq
			nearestEnemy = target
		}
	}

	// Utility Calculations
	scoreAttack := 0.0
	scoreChase := 0.0
	scoreFlee := (1.0 - healthRatio) * 1.2 // High urgency when low HP

	if nearestEnemy != nil {
		self.TargetID = nearestEnemy.ID
		dist := math.Sqrt(lowestDistSq)

		if dist <= self.AttackRange {
			scoreAttack = 1.0 // Maximum priority if target is within attack range
		} else {
			scoreChase = 0.7 * healthRatio // Chase only if healthy
		}
	} else {
		self.TargetID = 0
	}

	// Action Arbitrator
	bestAction := ActionIdle
	bestScore := 0.1 // Minimum activation threshold

	if scoreFlee > bestScore {
		bestScore = scoreFlee
		bestAction = ActionFlee
	}
	if scoreChase > bestScore {
		bestScore = scoreChase
		bestAction = ActionChase
	}
	if scoreAttack > bestScore {
		bestScore = scoreAttack
		bestAction = ActionAttack
	}

	b.CurrentAction = bestAction
	return bestAction
}

// --- WORLD STATE & ENGINE RUNTIME ---

type World struct {
	mu       sync.RWMutex
	Entities map[uint32]*EntityState
	Brains   map[uint32]*UtilityBrain
	Grid     *SpatialGrid
}

func NewWorld(width, height float64) *World {
	return &World{
		Entities: make(map[uint32]*EntityState),
		Brains:   make(map[uint32]*UtilityBrain),
		Grid:     NewSpatialGrid(width, height, 10.0),
	}
}

func (w *World) AddEntity(e *EntityState, hasAI bool) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.Entities[e.ID] = e
	if hasAI {
		w.Brains[e.ID] = &UtilityBrain{DecisionCooldown: 100 * time.Millisecond}
	}
	_ = w.Grid.Insert(e.ID, e.Position)
}

func (w *World) GetEntity(id uint32) *EntityState {
	w.mu.RLock()
	defer w.mu.RUnlock()
	return w.Entities[id]
}

type ArenaEngine struct {
	World          *World
	TickRate       int
	FixedDeltaTime time.Duration
	CurrentTick    uint64
	isRunning      atomic.Bool
	stopChan       chan struct{}
}

func NewArenaEngine(world *World, tickRate int) *ArenaEngine {
	return &ArenaEngine{
		World:          world,
		TickRate:       tickRate,
		FixedDeltaTime: time.Second / time.Duration(tickRate),
		stopChan:       make(chan struct{}),
	}
}

func (e *ArenaEngine) Start(ctx context.Context) error {
	if !e.isRunning.CompareAndSwap(false, true) {
		return errors.New("engine is already executing")
	}

	go e.runLoop(ctx)
	return nil
}

func (e *ArenaEngine) Stop() {
	if e.isRunning.CompareAndSwap(true, false) {
		close(e.stopChan)
	}
}

func (e *ArenaEngine) runLoop(ctx context.Context) {
	tickerInterval := e.FixedDeltaTime
	previousTime := time.Now()
	var accumulator time.Duration

	maxAccumulator := tickerInterval * 5 // Spiral-of-death threshold limit

	for {
		select {
		case <-ctx.Done():
			return
		case <-e.stopChan:
			return
		default:
			currentTime := time.Now()
			frameDuration := currentTime.Sub(previousTime)
			previousTime = currentTime

			// Protect against extreme pauses (e.g. debugging / scheduler stalls)
			if frameDuration > maxAccumulator {
				frameDuration = maxAccumulator
			}
			accumulator += frameDuration

			for accumulator >= e.FixedDeltaTime {
				e.tick(float64(e.FixedDeltaTime.Seconds()))
				accumulator -= e.FixedDeltaTime
			}

			// Sleep minimal balance duration to prevent aggressive busy-spin
			time.Sleep(time.Millisecond)
		}
	}
}

func (e *ArenaEngine) tick(dt float64) {
	atomic.AddUint64(&e.CurrentTick, 1)

	// Step 1: AI Perception & Utility Execution
	e.World.mu.RLock()
	for id, brain := range e.World.Brains {
		entity := e.World.Entities[id]
		if entity == nil || entity.IsDead {
			continue
		}
		action := brain.Evaluate(entity, e.World)
		e.applyAction(entity, action)
	}
	e.World.mu.RUnlock()

	// Step 2: Physics Integration & Spatial Grid Updates
	e.World.mu.Lock()
	for _, entity := range e.World.Entities {
		if entity.IsDead {
			continue
		}

		oldPos := entity.Position
		newPos := Vector2{
			X: entity.Position.X + entity.Velocity.X*dt,
			Y: entity.Position.Y + entity.Velocity.Y*dt,
		}

		// Boundary Constraints
		if newPos.X < 0 {
			newPos.X = 0
		} else if newPos.X >= e.World.Grid.worldWidth {
			newPos.X = e.World.Grid.worldWidth - 0.01
		}
		if newPos.Y < 0 {
			newPos.Y = 0
		} else if newPos.Y >= e.World.Grid.worldHeight {
			newPos.Y = e.World.Grid.worldHeight - 0.01
		}

		entity.Position = newPos
		_ = e.World.Grid.Update(entity.ID, oldPos, newPos)
	}
	e.World.mu.Unlock()

	// Step 3: Combat Resolution
	e.resolveCombat()
}

func (e *ArenaEngine) applyAction(entity *EntityState, action ActionType) {
	switch action {
	case ActionAttack:
		entity.Velocity = Vector2{0, 0}
	case ActionChase:
		target := e.World.GetEntity(entity.TargetID)
		if target != nil {
			dir := target.Position.Sub(entity.Position).Normalize()
			entity.Velocity = Vector2{X: dir.X * entity.Speed, Y: dir.Y * entity.Speed}
		}
	case ActionFlee:
		target := e.World.GetEntity(entity.TargetID)
		if target != nil {
			dir := entity.Position.Sub(target.Position).Normalize() // Vector opposite from enemy
			entity.Velocity = Vector2{X: dir.X * entity.Speed, Y: dir.Y * entity.Speed}
		}
	case ActionIdle:
		entity.Velocity = Vector2{0, 0}
	}
}

func (e *ArenaEngine) resolveCombat() {
	e.World.mu.Lock()
	defer e.World.mu.Unlock()

	for _, entity := range e.World.Entities {
		if entity.IsDead || entity.TargetID == 0 {
			continue
		}

		target, exists := e.World.Entities[entity.TargetID]
		if !exists || target.IsDead {
			entity.TargetID = 0
			continue
		}

		distSq := entity.Position.DistanceSquared(target.Position)
		if distSq <= (entity.AttackRange * entity.AttackRange) {
			// Apply damage (Normalized to tick interval damage)
			damagePerTick := entity.Damage / float64(e.TickRate)
			target.Health -= damagePerTick

			if target.Health <= 0.0 {
				target.Health = 0.0
				target.IsDead = true
				target.Velocity = Vector2{0, 0}
			}
		}
	}
}
```

---

### 7. Edge Cases & Failure Modes

1. **Spatial Boundary Violations & Out-of-Bounds Glitches**:
   - *Problem*: Entitas terdorong keluar batas arena (`pos.X < 0` atau `pos.X >= worldWidth`) akibat tabrakan fisika eksternal atau floating-point truncation, memicu *index out of range panic* pada array spasial.
   - *Defense*: Terapkan validasi *clamping* deterministik pada tahap akhir kalkulasi posisi sebelum grid update dipanggil. Jika koordinat mendeteksi `NaN` (`math.IsNaN(pos.X)`), reset posisi ke *safe spawn point* terdekat secara otomatis dan catat *critical telemetry log*.
2. **Tick Accumulator Overflow (The Spiral of Death)**:
   - *Problem*: Latensi komputasi GC cycle OS melebihi 200ms. Nilai accumulator membesar drastis, memaksa server memproses puluhan frame dalam satu siklus tanpa jeda sehingga I/O jaringan terhenti.
   - *Defense*: Batasi nilai maksimum akumulator: `if accumulator > 5 * fixedDelta { accumulator = fixedDelta }`. Laporkan frame drop ke metrik OpenTelemetry untuk memantau performa instance.
3. **Utility Thrashing (Action Oscillation)**:
   - *Problem*: Agen memiliki evaluasi utilitas yang berfluktuasi tipis di ambang batas nilai (misal: skor Flee 0.501, Chase 0.499, lalu pada tick berikutnya skor Flee 0.499, Chase 0.501). Agen akan bergetar di tempat tanpa bergerak.
   - *Defense*: Terapkan *Hysteresis* atau *Momentum Bias*. Berikan penalti skor switching ($0.15$) pada aksi baru kecuali selisih skornya melampaui margin tersebut, atau kunci durasi aksi minimum selama $N$ tick (*Action Lockout Window*).
4. **Data Race via Parallel Brain Execution**:
   - *Problem*: Memproses `Evaluate()` pada banyak thread bersamaan dapat memicu *race condition* jika sistem membaca dan menulis state dunia pada pointer yang sama secara un-synchronized.
   - *Defense*: Terapkan arsitektur *Double Buffering* atau pisahkan state menjadi dua fase: fase read-only (Perception & Scoring) dan fase write-back (Commit Intent) yang dieksekusi secara sekuensial atau dengan chunked-locking per node.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter | Uniform Spatial Hash Grid | Dynamic Quadtree / BVH | Spatial Hashing (Unbounded Hash Map) |
| :--- | :--- | :--- | :--- |
| **Kesesuaian Penggunaan** | Arena terbatas (MOBA, Battle Arena berukuran tetap). | Dunia terbuka (*open-world*) yang sangat luas dan sparsitas spasial tinggi. | Dunia berukuran tak terbatas (*infinite procedural terrain*). |
| **Kompleksitas Query** | Rata-rata $O(1)$ untuk radius pencarian lokal. | $O(\log N)$ dengan overhead tree traversal. | Rata-rata $O(1)$, namun rentan collision hash. |
| **Alokasi Heap (GC)** | Sangat Rendah: Array/Slice teralokasi sejak awal (*pre-allocated*). | Sangat Tinggi: Node splitting dan dereferencing pointer terus-menerus. | Sedang: Operasi rehash pada map memicu overhead alokasi memory. |
| **Performa CPU Cache** | **Sangat Baik**: Akses data sekuensial pada memory flat array. | Buruk: Pointer chasing antar node memicu CPU cache miss. | Sedang: Bergantung pada algoritma hashing bucket memory. |

---

### 9. Best Practices & Standar Industri

1. **Zero Heap Allocations dalam Inner Loop**:
   - Dilarang membuat instance slice, maps, atau pointer objek baru di dalam blok `tick(dt)`. Gunakan *Object Pooling* (`sync.Pool`) atau gunakan *pre-allocated fixed-size buffers* untuk menampung ID hasil kueri target.
2. **Defensive Monotonic Timestamps**:
   - Gunakan selalu *monotonic time* (`time.Since()`, bukan sistem jam dinding `time.Now().Unix()`) untuk komputasi delta loop game guna menghindari kegagalan sinkronisasi saat terjadi penyesuaian NTP clock pada node server.
3. **Data-Oriented Thinking**:
   - Jika jumlah entitas melebihi $5.000$, tinggalkan struktur model OOP berbasis `map[uint32]*EntityState` dan beralihlah ke arsitektur ECS (*Entity Component System*) atau *Structure of Arrays (SoA)* (misal: `Positions []Vector2`, `Velocities []Vector2`, `Healths []float32`). Hal ini memaksimalkan efisiensi *CPU L1/L2 cache line* dan mendukung auto-vectorization (SIMD).
4. **Telemetry & Heartbeat Monitoring**:
   - Lakukan instrumentasi pada setiap tick. Publikasikan metrik:
     - `tick_execution_time_ms` (Gauge)
     - `tick_overrun_count` (Counter)
     - `agent_utility_distribution` (Histogram)

---

### 10. Hands-on Lab Exercise: Stress Testing & Profiling Simulation Engine

#### Skenario Lab
Anda diminta memvalidasi performa battle arena engine ini untuk menangani skenario beban tinggi: **500 Autonomous Minion Agents** yang bertarung serentak dalam arena berukuran $200 \times 200$ meter pada tick rate 60 Hz. Batas toleransi rata-rata tick loop processing time tidak boleh melampaui **8ms** (separuh dari anggaran frame 16.6ms) guna menyisakan ruang untuk network serialization.

#### Langkah-langkah Praktik

1. **Inisialisasi Project**:
   ```bash
   mkdir arena-core-engine && cd arena-core-engine
   go mod init arena-core-engine
   ```

2. **Simpan File Implementasi**:
   Simpan kode bagian 6 ke dalam file `engine.go`.

3. **Buat Runner Simulation & Benchmark (`main.go`)**:
   ```go
   package main

   import (
   	"context"
   	"fmt"
   	"math/rand"
   	"runtime"
   	"time"

   	"arena-core-engine/engine"
   )

   func main() {
   	fmt.Println("=== INITIALIZING BATTLE ARENA STRESS TEST ===")
   	runtime.GOMAXPROCS(runtime.NumCPU())

   	const (
   		WorldWidth  = 200.0
   		WorldHeight = 200.0
   		EntityCount = 500
   		Duration    = 10 * time.Second
   		TickRate    = 60
   	)

   	world := engine.NewWorld(WorldWidth, WorldHeight)
   	r := rand.New(rand.NewSource(42)) // Deterministic seed

   	for i := uint32(1); i <= EntityCount; i++ {
   		eType := engine.TypeMinion
   		if i%2 == 0 {
   			eType = engine.TypePlayer // Set hostile opposition
   		}

   		entity := &engine.EntityState{
   			ID:          i,
   			Type:        eType,
   			Position:    engine.Vector2{X: r.Float64() * (WorldWidth - 1), Y: r.Float64() * (WorldHeight - 1)},
   			MaxHealth:   100.0,
   			Health:      100.0,
   			Speed:       3.5,
   			AttackRange: 2.0,
   			Damage:      15.0,
   		}
   		world.AddEntity(entity, true)
   	}

   	gameEngine := engine.NewArenaEngine(world, TickRate)
   	ctx, cancel := context.WithTimeout(context.Background(), Duration)
   	defer cancel()

   	startTime := time.Now()
   	_ = gameEngine.Start(ctx)

   	fmt.Printf("Engine running at %d Hz with %d agents for %v...\n", TickRate, EntityCount, Duration)
   	<-ctx.Done()
   	gameEngine.Stop()

   	totalTicks := gameEngine.CurrentTick
   	elapsed := time.Since(startTime).Seconds()
   	effectiveHz := float64(totalTicks) / elapsed

   	fmt.Println("\n=== SIMULATION RESULTS ===")
   	fmt.Printf("Total Ticks Executed: %d\n", totalTicks)
   	fmt.Printf("Elapsed Time: %.2f seconds\n", elapsed)
   	fmt.Printf("Effective Tick Rate: %.2f Hz\n", effectiveHz)

   	if effectiveHz < float64(TickRate)*0.95 {
   		fmt.Printf("[FAIL] Engine suffered tick degradation below 95%% threshold!\n")
   	} else {
   		fmt.Printf("[SUCCESS] Engine maintained rock-solid %d Hz target loop!\n", TickRate)
   	}
   }
   ```

4. **Eksekusi Pengujian & Profiling Memori**:
   Jalankan simulation test dengan Go benchmark tool:
   ```bash
   go run main.go
   ```

5. **Uji Validasi Analisis (Profil Alokasi)**:
   Jalankan micro-benchmark untuk memastikan tidak ada alokasi heap yang tidak terkontrol:
   ```bash
   go test -bench=. -benchmem -cpuprofile=cpu.pprof -memprofile=mem.pprof
   ```
   *Ekspektasi Output*:
   - Target frame time terjaga di bawah 16.6ms.
   - P99 Tick execution loop stabil tanpa lonjakan latensi (*jitter free*).
   - Metrik `0 allocs/op` pada hot path fungsi `SpatialGrid.QueryNearby` dan query kalkulasi pergerakan entitas.