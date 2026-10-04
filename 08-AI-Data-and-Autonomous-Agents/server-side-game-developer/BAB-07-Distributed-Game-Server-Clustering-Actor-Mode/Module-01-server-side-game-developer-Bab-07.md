# Bab 07: Distributed Game Server Clustering & Actor Model
## Modul 01: Fondasi Actor Model & State Distribution untuk Autonomous Game Entities

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
*   **Menganalisis dan Memilih** pola konkurensi Actor Model vs Shared-Memory Multi-Threading untuk sistem simulasi game terdistribusi berbasis metrik throughput, latensi tick rate, dan isolasi kegagalan (*fault isolation*).
*   **Merancang dan Mengimplementasikan** primitif Actor Engine (*Actor, Context, PID, Mailbox*) secara *thread-safe* dan bebas *deadlock* menggunakan Go.
*   **Membangun Sistem Dynamic Cluster Routing** berbasis *Consistent Hashing with Virtual Nodes* untuk memetakan jutaan Autonomous Game Agents (NPCs/World Entities) ke dalam node server yang berbeda secara deterministik.
*   **Menerapkan Pola Backpressure dan Supervision Strategy** (*One-for-One*, *One-for-All*) guna mencegah kegagalan kaskade (*cascading failures*) akibat *slow consumers* atau *poison pill messages*.
*   **Mengevaluasi dan Mengatasi Trade-offs** antara konsistensi data (*strong consistency*) dan performa *real-time* (*eventual consistency*) pada state sinkronisasi agent di cluster terdistribusi.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Dalam rekayasa *backend* game berskala masif (MMORPG, Persistent World, Dynamic Autonomous Simulations), pendekatan tradisional berbasis *Shared-Memory Multi-threading* (menggunakan Mutex/RWLock pada global state) menemui jalan buntu: **Lock Contention** dan risiko **Deadlock**. Ketika ribuan Autonomous AI Agent mencoba membaca dan memperbarui state dunia secara simultan, latensi meningkat tajam, merusak *tick rate* server (misal: target 20 Hz hingga 60 Hz).

**Actor Model** membalik paradigma ini melalui prinsip: *“Do not communicate by sharing memory; instead, share memory by communicating.”*

```
[ Thread-safe Concurrent World ]
  +-------------+                  +-------------+
  |   Actor A   | -- Message -->   |   Actor B   |
  |  (Private   |    (Async)       |  (Private   |
  |   State)    |                  |   State)    |
  +-------------+                  +-------------+
         |                                |
    [Mailbox Queue]                  [Mailbox Queue]
         |                                |
  [Single-threaded                 [Single-threaded
   Execution Loop]                  Execution Loop]
```

#### Komponen Kunci Actor Model:
1.  **Actor State**: State bersifat privat murni, terisolasi, dan tidak pernah diekspos langsung ke memori luar. Mutasi state hanya dapat dipicu oleh pemrosesan pesan masuk.
2.  **Mailbox (Message Queue)**: Antrean pesan FIFO yang menampung pesan masuk sebelum diproses oleh loop internal Actor secara sekuensial (menghilangkan kebutuhan lock pada state bisnis).
3.  **Behavior & Message Handler**: Logika eksekusi yang mendefinisikan respons aktor terhadap tipe pesan tertentu, termasuk kemampuan mengubah perilakunya sendiri (*hot-swapping behavior*) secara dinamis.
4.  **Location Transparency**: Pengirim (*Sender*) tidak perlu tahu apakah Actor penerima berada di goroutine lokal, thread terpisah, atau mesin fisik lain di cluster. Komunikasi diabstraksikan melalui **PID (Process Identifier)** atau Entity ID terdistribusi.

Dalam konteks **Autonomous Agents & AI Game Servers**, setiap NPC atau unit AI direpresentasikan sebagai satu Actor mandiri. Agent memiliki siklus internal (*Tick Message*), persepsi lokal, pohon perilaku (*Behavior Tree/Utility AI*), dan koordinat posisi tanpa memblokir thread eksekusi agent lainnya.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada arsitektur game enterprise seperti *EVE Online*, *World of Warcraft*, atau simulasi autonomous agent berskala jutaan entitas:
*   **Skalabilitas Horizontal**: Menjalankan 500.000 NPC otonom dengan persepsi spasial pada satu mesin adalah hal yang mustahil secara batasan CPU core dan bus memori. Actor Model memungkinkan partisi otomatis entitas melintasi *cluster node*.
*   **Zero Lock Overhead**: Menghilangkan *lock-wait time* mikro-detik yang terakumulasi. Karena setiap aktor memproses pesan secara single-threaded, logika AI (Pathfinding state, Aggro calculation, Inventory mutations) berjalan pada performa maksimal CPU cache tanpa *race conditions*.
*   **Fault Isolation & Self-Healing**: Jika satu AI Agent mengalami panic/exception (misal: *null reference pointer* saat perhitungan pathfinding navmesh), kegagalan terisolasi hanya pada aktor tersebut. Melalui *Supervision Trees*, supervisor aktor dapat me-restart agent tersebut ke kondisi state stabil terakhir tanpa mematikan seluruh instance server game (*crash-resilience*).

---

### 4. Arsitektur & Diagram Komponen

Arsitektur berikut mengilustrasikan ekosistem **Clustered Actor System** untuk Autonomous Game Agents:

```
+-----------------------------------------------------------------------------------+
|                                 GAME CLIENTS / GATEWAY                            |
+-----------------------------------------------------------------------------------+
                                         |
                                         v (RPC / Socket Packets)
+-----------------------------------------------------------------------------------+
|                        CLUSTER ROUTER & HASH RING PROXY                           |
|       (Consistent Hashing Ring with Virtual Nodes to resolve Actor Placement)     |
+-----------------------------------------------------------------------------------+
             |                                                    |
             v (gRPC / Custom TCP Frame)                          v (Local In-Memory)
+------------------------------------------+    +------------------------------------------+
|             CLUSTER NODE 01              |    |             CLUSTER NODE 02              |
|                                          |    |                                          |
|  +------------------------------------+  |    |  +------------------------------------+  |
|  |           ACTOR SYSTEM             |  |    |  |           ACTOR SYSTEM             |  |
|  |                                    |  |    |  |                                    |  |
|  |  +------------------------------+  |  |    |  |  +------------------------------+  |  |
|  |  |  Autonomous Agent: Boss-01   |  |  |    |  |  |  Autonomous Agent: Minion-42  |  |  |
|  |  |  - State: Health, AggroTable |  |  |    |  |  |  - State: Guard, PatrolPath  |  |  |
|  |  |  - Mailbox (Ring Buffer)     |  |  |    |  |  |  - Mailbox (Ring Buffer)     |  |  |
|  |  |  - Tick Loop (20 Hz)         |  |  |    |  |  |  - Tick Loop (10 Hz)         |  |  |
|  |  +------------------------------+  |  |    |  +------------------------------------+  |
|  |                                    |  |    |                                          |
|  |  +------------------------------+  |  |    |  +------------------------------------+  |
|  |  |  Supervisor Actor (Zone A)   |  |  |    |  |  Supervisor Actor (Zone B)     |  |  |
|  |  |  - Strategy: One-For-One     |  |  |    |  |  - Strategy: Escalate           |  |  |
|  |  +------------------------------+  |  |    |  +------------------------------------+  |
|  +------------------------------------+  |    +------------------------------------------+
|                     ^                    |                          ^
|                     |                    |                          |
|         Cluster Membership Protocol      |                          |
|         (SWIM / Gossip-based Heartbeat) <==========================>+
+------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Mailbox Mechanics & Concurrency Model
Mailbox harus didesain untuk throughput tinggi dengan overhead alokasi memori minimal. Pendekatan standar mengandalkan antrean *bounded lock-free queue* atau Go Channels dengan *backpressure strategy*. Ketika aktor menerima pesan, pesan tersebut dimasukkan ke dalam antrean. Goroutine aktor bertindak sebagai *consumer* tunggal yang membaca pesan satu per satu, mengeksekusi logika yang relevan, lalu beralih ke pesan berikutnya.

#### B. Autonomous Tick Generation
Agar sebuah agent dapat bertindak secara independen (*autonomous*), agent tidak hanya merespons input eksternal (misal: *PlayerAttackMessage*), tetapi juga memerlukan *pulse* waktu berkala. Hal ini dicapai menggunakan internal ticker yang mem-posting `TickMessage` ke mailbox-nya sendiri secara periodik:
$$\Delta t = t_{now} - t_{last\_tick}$$
Pada setiap eksekusi `TickMessage`, Agent mengevaluasi sensor lingkungannya, menjalankan *State Machine* (Idle $\rightarrow$ Patrol $\rightarrow$ Chase $\rightarrow$ Attack), dan memperbarui posisinya.

#### C. Consistent Hashing & Virtual Nodes Topology
Untuk mendistribusikan jutaan Agent ID secara merata ke dalam cluster tanpa *rebalancing* masif saat node bertambah/berkurang, digunakan **Consistent Hashing Ring**:
*   Sebuah ring didefinisikan pada rentang integer $[0, 2^{32}-1]$.
*   Setiap node fisik direpresentasikan oleh sejumlah $V$ *virtual nodes* untuk memitigasi ketimpangan distribusi (*hotspots*).
*   Hash dari Actor ID ($H(EntityID)$) dipetakan pada ring; aktor akan dialokasikan pada node terdekat searah jarum jam (*clockwise*).
*   Kompleksitas lookup lokasi adalah $O(\log(N \times V))$ menggunakan binary search.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem Actor terdistribusi minimalis, tangguh, dan berperforma tinggi dalam **Go**. Kode mencakup:
1.  **Actor Core Primitives** (*PID, Context, Actor Interface, Mailbox*).
2.  **Supervisor & Lifecycle Management**.
3.  **Consistent Hash Ring Router** untuk partisi cluster.
4.  **Autonomous AI Agent Actor Implementation** dengan internal tick loop.

```go
package main

import (
	"context"
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"fmt"
	"log"
	"sort"
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

// ==========================================
// 1. MESSAGES DEFINITIONS
// ==========================================

type Message interface{}

type PoisonPill struct{}

type TickMessage struct {
	DeltaTime time.Duration
}

type MoveCommand struct {
	TargetX float64
	TargetY float64
}

type AttackCommand struct {
	TargetActorID string
	Damage        float64
}

type AgentStateReport struct {
	ActorID string
	X       float64
	Y       float64
	Health  float64
	CurrentState string
}

// ==========================================
// 2. ACTOR PRIMITIVES & INTERFACES
// ==========================================

type PID struct {
	Address string // Node identifier
	ID      string // Entity identifier
	inbox   chan Message
	done    chan struct{}
}

func (p *PID) Tell(msg Message) error {
	select {
	case <-p.done:
		return errors.New("actor is terminated")
	case p.inbox <- msg:
		return nil
	default:
		// Backpressure handling: mailbox full
		return errors.New("mailbox is full, message dropped (backpressure)")
	}
}

type ActorContext interface {
	Self() *PID
	Receive() Message
	Context() context.Context
}

type Actor interface {
	Receive(ctx ActorContext)
}

type actorContextImpl struct {
	pid     *PID
	current Message
	ctx     context.Context
}

func (c *actorContextImpl) Self() *PID {
	return c.pid
}

func (c *actorContextImpl) Receive() Message {
	return c.current
}

func (c *actorContextImpl) Context() context.Context {
	return c.ctx
}

// ==========================================
// 3. CONSISTENT HASH RING (CLUSTER ROUTING)
// ==========================================

type HashRing struct {
	sync.RWMutex
	vnodes       int
	ring         []uint32
	nodeMapping  map[uint32]string
	activeNodes  map[string]bool
}

func NewHashRing(vnodes int) *HashRing {
	return &HashRing{
		vnodes:      vnodes,
		nodeMapping: make(map[uint32]string),
		activeNodes: make(map[string]bool),
	}
}

func (h *HashRing) hash(key string) uint32 {
	hasher := sha256.New()
	hasher.Write([]byte(key))
	digest := hasher.Sum(nil)
	return binary.BigEndian.Uint32(digest[:4])
}

func (h *HashRing) AddNode(node string) {
	h.Lock()
	defer h.Unlock()

	if h.activeNodes[node] {
		return
	}
	h.activeNodes[node] = true

	for i := 0; i < h.vnodes; i++ {
		vnodeKey := node + "#" + strconv.Itoa(i)
		hashVal := h.hash(vnodeKey)
		h.ring = append(h.ring, hashVal)
		h.nodeMapping[hashVal] = node
	}
	sort.Slice(h.ring, func(i, j int) bool { return h.ring[i] < h.ring[j] })
}

func (h *HashRing) RemoveNode(node string) {
	h.Lock()
	defer h.Unlock()

	if !h.activeNodes[node] {
		return
	}
	delete(h.activeNodes, node)

	newRing := make([]uint32, 0, len(h.ring)-(h.vnodes))
	for _, hashVal := range h.ring {
		if h.nodeMapping[hashVal] == node {
			delete(h.nodeMapping, hashVal)
		} else {
			newRing = append(newRing, hashVal)
		}
	}
	h.ring = newRing
}

func (h *HashRing) GetNode(entityID string) (string, error) {
	h.RLock()
	defer h.RUnlock()

	if len(h.ring) == 0 {
		return "", errors.New("empty hash ring: no nodes available")
	}

	hashVal := h.hash(entityID)
	idx := sort.Search(len(h.ring), func(i int) bool {
		return h.ring[i] >= hashVal
	})

	if idx == len(h.ring) {
		idx = 0 // Wrap around the circle
	}

	return h.nodeMapping[h.ring[idx]], nil
}

// ==========================================
// 4. AUTONOMOUS AGENT ACTOR
// ==========================================

type AgentAIState int

const (
	StateIdle AgentAIState = iota
	StatePatrol
	StateCombat
)

type AutonomousAgentActor struct {
	id           string
	x, y         float64
	targetX      float64
	targetY      float64
	health       float64
	maxHealth    float64
	aiState      AgentAIState
	speed        float64
	reportTicker *time.Ticker
	cancelFunc   context.CancelFunc
}

func NewAutonomousAgentActor(id string, startX, startY float64) *AutonomousAgentActor {
	return &AutonomousAgentActor{
		id:        id,
		x:         startX,
		y:         startY,
		targetX:   startX,
		targetY:   startY,
		health:    100.0,
		maxHealth: 100.0,
		aiState:   StateIdle,
		speed:     5.0, // units per second
	}
}

func (a *AutonomousAgentActor) Receive(ctx ActorContext) {
	msg := ctx.Receive()

	switch m := msg.(type) {
	case TickMessage:
		a.onTick(m.DeltaTime)
	case MoveCommand:
		a.targetX = m.TargetX
		a.targetY = m.TargetY
		a.aiState = StatePatrol
		log.Printf("[Agent %s] New destination received: (%.2f, %.2f)", a.id, a.targetX, a.targetY)
	case AttackCommand:
		a.health -= m.Damage
		log.Printf("[Agent %s] Took %.2f damage! Current HP: %.2f", a.id, m.Damage, a.health)
		if a.health <= 0 {
			log.Printf("[Agent %s] Eliminated. Poisoning self...", a.id)
			_ = ctx.Self().Tell(PoisonPill{})
		} else {
			a.aiState = StateCombat
		}
	case PoisonPill:
		log.Printf("[Agent %s] Stopping agent execution loop gracefully.", a.id)
		if a.cancelFunc != nil {
			a.cancelFunc()
		}
	default:
		log.Printf("[Agent %s] Unknown message received: %T", a.id, m)
	}
}

func (a *AutonomousAgentActor) onTick(dt time.Duration) {
	seconds := dt.Seconds()

	// Logic State Machine AI
	switch a.aiState {
	case StateIdle:
		// Standstill behavior
	case StatePatrol, StateCombat:
		// Steering / Movement calculations
		dx := a.targetX - a.x
		dy := a.targetY - a.y
		distSq := dx*dx + dy*dy

		if distSq > 0.01 {
			dist := 1.0 // Approximation for vector normalization
			if distSq > 1.0 {
				dist = distSq // Simple damping approximation
			}
			step := a.speed * seconds
			a.x += (dx / dist) * step
			a.y += (dy / dist) * step
		} else {
			a.x = a.targetX
			a.y = a.targetY
			if a.aiState == StatePatrol {
				a.aiState = StateIdle
			}
		}
	}
}

// ==========================================
// 5. ACTOR SYSTEM RUNTIME & SUPERVISOR
// ==========================================

type ActorSystem struct {
	nodeID    string
	actors    sync.Map // map[string]*PID
	isRunning int32
}

func NewActorSystem(nodeID string) *ActorSystem {
	return &ActorSystem{
		nodeID:    nodeID,
		isRunning: 1,
	}
}

func (sys *ActorSystem) Spawn(id string, actor Actor, mailboxSize int) (*PID, error) {
	if atomic.LoadInt32(&sys.isRunning) == 0 {
		return nil, errors.New("actor system is shut down")
	}

	pid := &PID{
		Address: sys.nodeID,
		ID:      id,
		inbox:   make(chan Message, mailboxSize),
		done:    make(chan struct{}),
	}

	if _, loaded := sys.actors.LoadOrStore(id, pid); loaded {
		return nil, fmt.Errorf("actor with ID %s already exists in node %s", id, sys.nodeID)
	}

	ctx, cancel := context.WithCancel(context.Background())
	if agent, ok := actor.(*AutonomousAgentActor); ok {
		agent.cancelFunc = cancel
	}

	// Internal Goroutine (The Execution Thread for this Actor)
	go sys.actorLoop(ctx, pid, actor)

	return pid, nil
}

func (sys *ActorSystem) actorLoop(ctx context.Context, pid *PID, actor Actor) {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("[Supervisor] Panic recovered in Actor %s: %v. Restarting/Cleaning up...", pid.ID, r)
		}
		sys.actors.Delete(pid.ID)
		close(pid.done)
	}()

	actCtx := &actorContextImpl{pid: pid, ctx: ctx}

	for {
		select {
		case <-ctx.Done():
			return
		case msg, ok := <-pid.inbox:
			if !ok {
				return
			}
			if _, isPoison := msg.(PoisonPill); isPoison {
				actCtx.current = msg
				actor.Receive(actCtx)
				return
			}
			actCtx.current = msg
			actor.Receive(actCtx)
		}
	}
}

func (sys *ActorSystem) Shutdown() {
	atomic.StoreInt32(&sys.isRunning, 0)
	sys.actors.Range(func(key, value interface{}) bool {
		pid := value.(*PID)
		_ = pid.Tell(PoisonPill{})
		return true
	})
}

// ==========================================
// 6. MAIN SIMULATION ENTRYPOINT
// ==========================================

func main() {
	log.Println("Initializing Distributed Cluster Topology Simulation...")

	// 1. Setup Cluster Router
	hashRing := NewHashRing(100)
	nodeNodes := []string{"cluster-node-eu-01", "cluster-node-eu-02", "cluster-node-us-01"}
	for _, n := range nodeNodes {
		hashRing.AddNode(n)
	}

	// 2. Setup Local Actor System for Node 01
	localNodeID := "cluster-node-eu-01"
	system := NewActorSystem(localNodeID)
	defer system.Shutdown()

	// 3. Register Entities & Route Placement
	entities := []string{"boss_dragon_001", "goblin_scout_01", "goblin_scout_02", "npc_merchant_05"}

	for _, entityID := range entities {
		targetNode, err := hashRing.GetNode(entityID)
		if err != nil {
			log.Fatalf("Routing error: %v", err)
		}

		log.Printf("Entity [%s] mapped deterministically to -> [%s]", entityID, targetNode)

		// If mapped to local node, spawn actor
		if targetNode == localNodeID {
			agent := NewAutonomousAgentActor(entityID, 0.0, 0.0)
			pid, err := system.Spawn(entityID, agent, 100)
			if err != nil {
				log.Printf("Failed to spawn %s: %v", entityID, err)
				continue
			}

			// Run periodic tick producer for autonomous behavior (e.g. 10 Hz)
			go func(p *PID) {
				ticker := time.NewTicker(100 * time.Millisecond)
				defer ticker.Stop()
				for range ticker.C {
					err := p.Tell(TickMessage{DeltaTime: 100 * time.Millisecond})
					if err != nil {
						return // Actor likely dead
					}
				}
			}(pid)

			// Dispatch a sample command
			_ = pid.Tell(MoveCommand{TargetX: 50.0, TargetY: 25.0})
		}
	}

	// Simulate system running for a few ticks
	time.Sleep(300 * time.Millisecond)

	// Simulate Damage to entity if alive locally
	if val, ok := system.actors.Load("boss_dragon_001"); ok {
		bossPID := val.(*PID)
		_ = bossPID.Tell(AttackCommand{TargetActorID: "player_warrior_99", Damage: 45.0})
		_ = bossPID.Tell(AttackCommand{TargetActorID: "player_mage_01", Damage: 60.0}) // Fatal damage
	}

	time.Sleep(200 * time.Millisecond)
	log.Println("Simulation cycle completed.")
}
```

---

### 7. Edge Cases & Failure Modes

Pada skala *enterprise real-time clustering*, sistem wajib menangani skenario batas berikut:

#### 1. Network Partitioning & Split-Brain Syndrome
*   **Kasus**: Terputusnya koneksi antar-node (misal: Node 01 dan Node 02 tidak dapat saling ping). Kedua node mengasumsikan node pasangannya mati dan berusaha men-spawn instance aktor yang sama (*Duplicate Autonomous Agents*).
*   **Mitigasi**: Gunakan konsensus quorum (*Raft* atau *Zookeeper/etcd lease*) untuk distributed lock kepemilikan partisi ring, atau terapkan *Generation/Epoch ID* (fencing token) pada database storage agent state. State update dengan Epoch kadaluarsa ditolak secara absolut.

#### 2. Mailbox Overflow (Slow Consumer vs Fast Producer)
*   **Kasus**: AI Agent terjebak pada komputasi berat (*misal: complex A\* pathfinding*), sementara ribuan event broadcast *Tick* atau *Network Update* membanjiri antrean mailbox.
*   **Mitigasi**: Implementasi **Bounded Mailboxes** dengan strategi *Drop Oldest* untuk state transient seperti navigasi spasial, atau terapkan *backpressure* ke gateway layer menggunakan HTTP 429/TCP window sizing.

#### 3. Poison Pill & Cascading Failures
*   **Kasus**: Pesan dengan struktur payload korup membuat loop aktor mengalami panic berulang kali.
*   **Mitigasi**: Terapkan **Dead Letter Queue (DLQ)**. Jika sebuah pesan menyebabkan panic dan retry count mencapai limit ($N \ge 3$), alihkan pesan ke DLQ untuk analisis offline dan biarkan aktor melanjutkan eksekusi pesan berikutnya tanpa shutdown sistemik.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter Arsitektur | Actor Model (ProtoActor/Orleans) | Shared Memory Multi-Threading | Entity Component System (ECS) |
| :--- | :--- | :--- | :--- |
| **State Synchronization** | Bebas lock; komunikasi via message-passing asinkron. | Mutex, Spinlock, Atomic primitives. Risiko tinggi deadlock. | Memory continuous array (Archetypes/Chunks); CPU Cache optimal. |
| **Skalabilitas Spasial** | **Tinggi (Cluster-wide)**: Location transparency memudahkan pemindahan actor. | **Rendah**: Terbatas pada satu node komputasi fisik (Vertical scale). | **Menengah-Tinggi**: Sangat cepat single-machine, rumit di-cluster. |
| **Kompleksitas Debugging**| **Tinggi**: Non-deterministic async trace, dependensi message ordering. | **Tinggi**: Race conditions, memory sanitization, dump analysis. | **Rendah**: Deterministic sequential processing per system. |
| **Overhead Komputasi** | Message allocation & channel/queue context switching. | Minimum context switch jika lock contention terkendali rendah. | Zero context-switch; vectorization (SIMD) cache hits. |

---

### 9. Best Practices & Standard Industri

1.  **Keep Actor Messages Immutable**: Jangan pernah mengirim pointer yang mereferensikan mutable struct ke mailbox aktor lain. Buat deep-copy atau gunakan value-types untuk mengeliminasi silent data corruption.
2.  **Separate Compute-Intensive Tasks**: Jangan jalankan perhitungan berat (seperti algoritma NavMesh generation, pathfinding jarak jauh, atau deep learning inference) secara langsung di dalam Actor Execution Loop utama. Delegasikan kalkulasi ke *Worker Pool* terpisah dan kirim hasilnya kembali ke Actor Mailbox sebagai event asinkron.
3.  **Observability & Telemetry Instrumentation**:
    *   Monitor parameter **Mailbox Size / Queue Depth** per aktor secara real-time. Lonjakan mendadak adalah indikator starvation atau bottleneck.
    *   Ukur **Actor Processing Latency** (durasi pemrosesan pesan individu). Alerting harus dipicu jika $P_{99} > 15 \text{ ms}$ pada tick rate 60 Hz.
4.  **Graceful Rebalancing (Cluster Resizing)**: Saat node baru masuk ke dalam cluster hash ring, terapkan pola **Handoff/Migration State**. Node lama menolak request baru, mengekspor snapshot state aktor via gRPC streaming ke node baru, lalu mengirim *PoisonPill* ke instance lokal lama.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab:
Anda ditugaskan mengimplementasikan mekanisme **Dynamic Node Failure Recovery & Autonomous State Re-routing** pada simulasi kluster mini 3-Node.

#### Langkah-langkah Praktikum:
1.  **Inisialisasi Proyek**: Salin kode implementasi Go pada Bagian 6 ke dalam berkas `main.go`.
2.  **Simulasi Penambahan Node Dinamis**:
    *   Tuliskan fungsi helper `SimulateNodeLeave(ring *HashRing, nodeID string, sys *ActorSystem)`.
    *   Hapus `cluster-node-eu-01` dari hash ring secara real-time saat simulasi tick sedang berjalan.
3.  **Implementasikan Re-routing Fallback**:
    *   Sebelum node dimatikan, tangkap semua aktor yang aktif di node tersebut.
    *   Serialisasikan state terakhir (`X`, `Y`, `Health`, `State`) ke dalam memory map snapshot.
    *   Gunakan Hash Ring yang telah diperbarui untuk menentukan node tujuan baru, kemudian aktifkan kembali agent di node baru dengan state snapshot tersebut.
4.  **Verifikasi & Validasi**:
    *   Jalankan pengujian menggunakan flag: `go run -race main.go`.
    *   Pastikan **Zero Data Race** terdeteksi oleh thread sanitizer Go.
    *   Pastikan health point dan koordinat agent yang bermigrasi tetap berlanjut secara konsisten tanpa reset ke origin $(0.0, 0.0)$.