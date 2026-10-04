# BAB 07: Distributed Game Server Clustering & Actor Model
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   Mendesain dan mengimplementasikan arsitektur **Distributed Virtual Actor Engine** untuk game berskala masif (MMO/Real-time Spatial) menggunakan prinsip *Location Transparency* dan *Consistent Hashing*.
*   Mengonfigurasi protokol keanggotaan kluster (*Cluster Membership*) berbasis **SWIM (Structured Weakly-Consistent Infection-Style Process Group Membership Protocol)** dengan mekanisme *Suspicion*.
*   Mengimplementasikan mekanisme **Actor Lifecycle Management**: *Passivation*, *Rehydration*, *Message Stashing*, dan *Supervision Strategy* untuk toleransi kesalahan (*fault tolerance*).
*   Mengonfigurasi strategi mitigasi **Split-Brain** menggunakan algoritma *Quorum-based Lease Resolution* untuk mencegah anomali *state divergence*.
*   Melakukan profiling dan mitigasi terhadap *actor mailbox congestion*, *lock contention*, dan latensi serialisasi jaringan pada *inter-node actor communication*.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, Anda wajib menguasai:
*   Pemahaman mendalam tentang konkurensi (Thread-safety, Goroutine/Task, Mutex, Channel, Non-blocking I/O).
*   Dasar-dasar Actor Model (Mailbox, Message Passing, Actor Reference) dari Modul 01.
*   Protokol Jaringan: TCP, UDP, KCP, gRPC, serta format serialisasi performa tinggi (Protocol Buffers, FlatBuffers).
*   Konsep Sistem Terdistribusi: Teorema CAP, PACELC, Hash Rings, dan Eventual Consistency.
*   Lingkungan: Go (versi 1.22+) atau C# (.NET 8), Docker, dan Redis/etcd untuk distributed lock/lease.

---

### 3. Concept & Internal Architecture

Dalam arsitektur *monolithic stateful game server*, *player state* diikat langsung ke memori satu proses fisik. Jika proses tersebut kelebihan beban (*overloaded*) atau mengalami *crash*, seluruh sesi pemain yang terhubung akan putus. Di lingkungan produksi enterprise, kita mengadopsi model **Distributed Virtual Actor (Grain-based)**.

```
+---------------------------------------------------------------------------------------+
|                                    CLUSTER BOUNDARY                                   |
|                                                                                       |
|  +--------------------+        +--------------------+        +---------------------+  |
|  |     Node A         |        |     Node B         |        |      Node C         |  |
|  | +----------------+ |        | +----------------+ |        |  +----------------+ |  |
|  | | Actor: Player1 | |        | | Actor: Room101 | |        |  | Actor: Player2 | |  |
|  | +----------------+ |        | +----------------+ |        |  +----------------+ |  |
|  |         ^          |        |         ^          |        |          ^          |  |
|  |         |          |        |         |          |        |          |          |  |
|  |   [Local Mailbox]  |        |   [Local Mailbox]  |        |    [Local Mailbox]  |  |
|  |         |          |        |         |          |        |          |          |  |
|  | +----------------+ |        | +----------------+ |        |  +----------------+ |  |
|  | | Actor System   | |        | | Actor System   | |        |  | Actor System   | |  |
|  | | Shard Region   | |        | | Shard Region   | |        |  | Shard Region   | |  |
|  +--------+-----------+        +---------+----------+        +----------+----------+  |
|           |                              |                              |             |
|           +====== gRPC Transport ========+====== SWIM Gossip ===========+             |
|                                                                                       |
+---------------------------------------------------------------------------------------+
```

#### A. Location Transparency & Entity Sharding
Pada Distributed Actor Model, entitas pemanggil (*caller*) tidak perlu mengetahui alamat fisik IP atau port dari target actor. Entitas berkomunikasi via `ActorRef` logis atau Entity ID. 

Mekanisme **Entity Sharding** bekerja sebagai berikut:
1.  **Actor ID**: ID unik aktor (contoh: `PlayerActor:UUID-12845`).
2.  **Shard ID**: Ditentukan melalui fungsi *consistent hashing*: 
    $$\text{ShardID} = \text{MurmurHash3}(\text{ActorID}) \pmod{\text{TotalShards}}$$
3.  **Shard Coordinator**: Mengelola alokasi Shard ke Node tertentu di kluster.
4.  **Shard Region**: Router lokal di setiap node yang melakukan lookup ke tabel alokasi kluster dan meneruskan pesan ke shard lokal atau me-routing secara RPC ke shard di node remote.

#### B. Cluster Membership: SWIM Protocol with Suspicion Mechanism
Menghindari ketergantungan pada *heartbeat* terpusat (seperti etcd/ZooKeeper) untuk keanggotaan ribuan node, kluster modern menggunakan protokol *Gossip* berbasis SWIM:
*   Setiap $T'$ detik, Node $A$ memilih acak Node $B$ dan mengirim `Ping`.
*   Jika Node $B$ membalas dengan `Ack`, Node $B$ dianggap *Healthy*.
*   Jika $B$ tidak membalas dalam batas waktu $\Delta$, Node $A$ memilih $k$ node tidak langsung ($C_1, C_2, ..., C_k$) untuk mengirim `Ping-Req(B)`.
*   Jika tidak ada *Ack* dalam batas waktu, Node $B$ ditandai sebagai `Suspect` (bukan langsung `Dead`).
*   Status `Suspect` disebarkan via *piggybacked gossip*. Jika setelah periode $\tau$ Node $B$ tidak membantah status tersebut dengan pesan `Alive` baru (dengan *incarnation number* lebih tinggi), Node $B$ dideklarasikan `Dead` dan dikeluarkan dari Hash Ring.

#### C. Split-Brain Resolver (SBR) & Distributed Lease
Ketika terjadi *network partition*, kluster dapat terpecah menjadi dua sub-kluster terisolasi (misal: Sub-kluster $X$ berisi 3 node, Sub-kluster $Y$ berisi 2 node). Jika kedua sub-kluster menganggap sub-kluster lainnya mati dan merehidrasi aktor yang sama, terjadi **Split-Brain** dan korupsi data (*duplicate entities*).

Strategi resolusi enterprise:
*   **Static Quorum**: Sub-kluster bertahan hanya jika memiliki ukuran node $> N/2$.
*   **Distributed Lease (etcd/Consul)**: Sub-kluster yang ingin tetap aktif harus berhasil memperbarui lease terdistribusi di metadata store eksternal dengan *time-to-live* (TTL) ketat. Sub-kluster yang gagal memperoleh lease wajib melakukan terminasi mandiri (*auto-kill/poison pill*).

---

### 4. Why & What

| Dimensi | Stateful Monolith Game Server | Distributed Actor Cluster |
| :--- | :--- | :--- |
| **Penyimpanan State** | In-Memory pada 1 dedicated room instance | In-Memory terdistribusi di seluruh node kluster |
| **Kapasitas Pemain** | Terbatas pada batas vertikal RAM & CPU satu server | Elastis, scale-out horizontal melintasi ratusan server |
| **Node Failure Handling** | Sesi terputus total; *state* hilang jika belum ter-flush | Aktor dipindahkan & direhidrasi otomatis di node lain |
| **Routing Pesan** | Manual melalui gateway/proxy router kaku | Transparan (*Location Transparency*) via Hash Ring |
| **Concurrency Model** | Mutex locking multi-threading rawan deadlock | Single-threaded per Actor (Lock-free message passing) |

---

### 5. How (Workflow Detail)

Alur penanganan siklus hidup pesan dan *actor passivation*:

```
[Gateway]             [ShardRegion (Node A)]       [ShardRegion (Node B)]        [PlayerActor (Node B)]        [Database]
    |                            |                            |                            |                        |
    | 1. RouteMsg(PlayerX, Cmd)  |                            |                            |                        |
    |--------------------------->|                            |                            |                        |
    |                            | 2. Resolve Shard(PlayerX)  |                            |                        |
    |                            |    Target = Node B         |                            |                        |
    |                            | 3. Forward RPC(PlayerX)    |                            |                        |
    |                            |--------------------------->|                            |                        |
    |                            |                            | 4. Is Actor Alive? (NO)    |                        |
    |                            |                            | 5. Stash Message           |                        |
    |                            |                            | 6. Spawn Actor instance    |                        |
    |                            |                            |--------------------------->|                        |
    |                            |                            |                            | 7. LoadSnapshot()      |
    |                            |                            |                            |----------------------->|
    |                            |                            |                            | 8. State Loaded        |
    |                            |                            |                            |<-----------------------|
    |                            |                            | 9. Actor Ready             |                        |
    |                            |                            |<---------------------------|                        |
    |                            |                            | 10. Unstash & Deliver      |                        |
    |                            |                            |--------------------------->|                        |
    |                            |                            |                            | 11. Process Command    |
    |                            |                            |                            |     & Mutate State     |
    |                            |                            |                            |                        |
    |                            |                            |                            | (Idle for 15 mins)     |
    |                            |                            | 12. Passivate Entity       |                        |
    |                            |                            |<---------------------------|                        |
    |                            |                            | 13. Persist Final State    |                        |
    |                            |                            |---------------------------------------------------->|
    |                            |                            | 14. Terminate Actor        |                        |
    |                            |                            |--------------------------->|                        |
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem Kedutaan Diplomatik
Bayangkan sistem surat-menyurat diplomatik antar-negara:
*   **Pemain** adalah seorang Diplomat.
*   **Actor ID** adalah Nama Diplomat tersebut, bukan alamat rumahnya.
*   **Shard Coordinator** adalah Departemen Luar Negeri yang memiliki buku direktori di mana setiap diplomat ditugaskan saat ini.
*   **Shard Region** adalah Kantor Pos Diplomatik Lokal. Jika Anda mengirim surat ke "Diplomat X", Anda memasukkannya ke kantor pos lokal Anda. Kantor pos mencari tahu bahwa Diplomat X saat ini ada di Jenewa (Node B), lalu membungkus surat itu dalam kantong diplomatik berkecepatan tinggi (gRPC).
*   Jika Diplomat X sedang tidur (Passivated), Kantor Pos Jenewa menahan surat di meja depan (*Stash*), membangunkan sang diplomat, menyerahkan berkas arsip masa lalu (*Database Snapshot*), dan setelah diplomat bangun, surat langsung diberikan.

---

### 7. Simple Example & Practical Example

#### A. Simple Example: In-Memory Virtual Actor Mailbox dengan Passivation Timer (Go)
Contoh dasar mekanisme aktor lokal yang mengelola mailbox-nya sendiri dan memicu *passivation* jika idle.

```go
package main

import (
	"context"
	"fmt"
	"sync"
	"time"
)

type Message interface{}

type PlayerCommand struct {
	Command string
	Payload string
}

type PassivateMessage struct{}

type SimplePlayerActor struct {
	id          string
	mailbox     chan Message
	idleTimeout time.Duration
	timer       *time.Timer
	ctx         context.Context
	cancel      context.CancelFunc
	mu          sync.Mutex
	isDead      bool
}

func NewSimplePlayerActor(id string, idleTimeout time.Duration) *SimplePlayerActor {
	ctx, cancel := context.WithCancel(context.Background())
	actor := &SimplePlayerActor{
		id:          id,
		mailbox:     make(chan Message, 100),
		idleTimeout: idleTimeout,
		ctx:         ctx,
		cancel:      cancel,
	}
	actor.timer = time.AfterFunc(idleTimeout, actor.triggerPassivation)
	go actor.run()
	return actor
}

func (a *SimplePlayerActor) triggerPassivation() {
	a.mailbox <- PassivateMessage{}
}

func (a *SimplePlayerActor) resetTimer() {
	a.mu.Lock()
	defer a.mu.Unlock()
	if !a.isDead {
		a.timer.Reset(a.idleTimeout)
	}
}

func (a *SimplePlayerActor) run() {
	for {
		select {
		case <-a.ctx.Done():
			return
		case msg := <-a.mailbox:
			switch m := msg.(type) {
			case PassivateMessage:
				a.mu.Lock()
				fmt.Printf("[Actor %s] Passivating due to inactivity...\n", a.id)
				a.isDead = true
				a.cancel()
				close(a.mailbox)
				a.mu.Unlock()
				return
			case PlayerCommand:
				a.resetTimer()
				fmt.Printf("[Actor %s] Executing command: %s (Payload: %s)\n", a.id, m.Command, m.Payload)
			}
		}
	}
}

func (a *SimplePlayerActor) Tell(msg Message) error {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.isDead {
		return fmt.Errorf("actor %s is passivated/dead", a.id)
	}
	a.mailbox <- msg
	return nil
}

func main() {
	player := NewSimplePlayerActor("player-1001", 500*time.Millisecond)

	player.Tell(PlayerCommand{Command: "MOVE", Payload: "x:10,y:20"})
	time.Sleep(200 * time.Millisecond)
	player.Tell(PlayerCommand{Command: "ATTACK", Payload: "target:orc_1"})

	// Tunggu idle passivate terpicu
	time.Sleep(700 * time.Millisecond)

	err := player.Tell(PlayerCommand{Command: "MOVE", Payload: "x:15,y:25"})
	if err != nil {
		fmt.Printf("Message failed: %v\n", err)
	}
}
```

#### B. Practical Example: Production-Grade Shard Region, Dynamic Rehydration, and Consistent Hashing Router
Implementasi Go tingkat enterprise dengan algoritma Hash Ring, message stashing, dan *state rehydration*.

```go
package main

import (
	"context"
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

// --- Consistent Hash Ring ---

type HashRing struct {
	mu       sync.RWMutex
	vnodes   int
	ring     []uint32
	nodeMap  map[uint32]string
	nodesSet map[string]struct{}
}

func NewHashRing(vnodes int) *HashRing {
	return &HashRing{
		vnodes:   vnodes,
		nodeMap:  make(map[uint32]string),
		nodesSet: make(map[string]struct{}),
	}
}

func (h *HashRing) hash(val string) uint32 {
	hasher := sha256.New()
	hasher.Write([]byte(val))
	bytes := hasher.Sum(nil)
	return binary.BigEndian.Uint32(bytes[:4])
}

func (h *HashRing) AddNode(node string) {
	h.mu.Lock()
	defer h.mu.Unlock()

	if _, exists := h.nodesSet[node]; exists {
		return
	}
	h.nodesSet[node] = struct{}{}

	for i := 0; i < h.vnodes; i++ {
		vkey := node + "#" + strconv.Itoa(i)
		hashVal := h.hash(vkey)
		h.ring = append(h.ring, hashVal)
		h.nodeMap[hashVal] = node
	}
	sort.Slice(h.ring, func(i, j int) bool { return h.ring[i] < h.ring[j] })
}

func (h *HashRing) RemoveNode(node string) {
	h.mu.Lock()
	defer h.mu.Unlock()

	if _, exists := h.nodesSet[node]; !exists {
		return
	}
	delete(h.nodesSet, node)

	newRing := make([]uint32, 0, len(h.ring)-(h.vnodes))
	for _, val := range h.ring {
		if h.nodeMap[val] == node {
			delete(h.nodeMap, val)
		} else {
			newRing = append(newRing, val)
		}
	}
	h.ring = newRing
}

func (h *HashRing) GetNode(key string) (string, error) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	if len(h.ring) == 0 {
		return "", errors.New("hash ring is empty")
	}

	hashVal := h.hash(key)
	idx := sort.Search(len(h.ring), func(i int) bool {
		return h.ring[i] >= hashVal
	})

	if idx == len(h.ring) {
		idx = 0
	}
	return h.nodeMap[h.ring[idx]], nil
}

// --- Actor Domain & Sharding Primitives ---

type Envelope struct {
	EntityID  string
	Action    string
	Data      []byte
	ReplyChan chan Response
}

type Response struct {
	Success bool
	Result  string
	Err     error
}

type EntityState struct {
	EntityID string
	Health   int32
	Position string
	Version  uint64
}

type EntityActor struct {
	id         string
	state      EntityState
	inbox      chan Envelope
	stash      []Envelope
	isHydrated bool
	isStopping int32
	lastAccess int64
	ctx        context.Context
	cancel     context.CancelFunc
}

func NewEntityActor(id string) *EntityActor {
	ctx, cancel := context.WithCancel(context.Background())
	actor := &EntityActor{
		id:         id,
		inbox:      make(chan Envelope, 512),
		stash:      make([]Envelope, 0),
		isHydrated: false,
		lastAccess: time.Now().UnixNano(),
		ctx:        ctx,
		cancel:     cancel,
	}
	go actor.eventLoop()
	return actor
}

func (e *EntityActor) eventLoop() {
	// Rehidrasi State secara asinkron saat instansiasi
	e.rehydrate()

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-e.ctx.Done():
			return

		case <-ticker.C:
			// Cek apakah aktor idle lebih dari 5 detik (passivation)
			idle := time.Duration(time.Now().UnixNano() - atomic.LoadInt64(&e.lastAccess))
			if idle > 5*time.Second {
				e.passivate()
				return
			}

		case env, ok := <-e.inbox:
			if !ok {
				return
			}
			atomic.StoreInt64(&e.lastAccess, time.Now().UnixNano())

			if !e.isHydrated {
				// Simpan pesan di stash jika state belum selesai di-load
				e.stash = append(e.stash, env)
				continue
			}

			e.processMessage(env)
		}
	}
}

func (e *EntityActor) rehydrate() {
	// Simulasi I/O load dari cold storage / database
	time.Sleep(100 * time.Millisecond)
	e.state = EntityState{
		EntityID: e.id,
		Health:   100,
		Position: "0,0,0",
		Version:  1,
	}
	e.isHydrated = true

	// Unstash seluruh pesan tertunda
	for _, env := range e.stash {
		e.processMessage(env)
	}
	e.stash = nil
}

func (e *EntityActor) processMessage(env Envelope) {
	switch env.Action {
	case "MOVE":
		e.state.Position = string(env.Data)
		e.state.Version++
		env.ReplyChan <- Response{Success: true, Result: fmt.Sprintf("Pos: %s, Ver: %d", e.state.Position, e.state.Version)}
	case "DAMAGE":
		atomic.AddInt32(&e.state.Health, -10)
		env.ReplyChan <- Response{Success: true, Result: fmt.Sprintf("Health: %d", e.state.Health)}
	default:
		env.ReplyChan <- Response{Success: false, Err: errors.New("unknown command")}
	}
}

func (e *EntityActor) passivate() {
	if atomic.CompareAndSwapInt32(&e.isStopping, 0, 1) {
		fmt.Printf("[Cluster Node] Passivating Actor %s to free memory. State persisted at version %d\n", e.id, e.state.Version)
		e.cancel()
		close(e.inbox)
	}
}

// --- Shard Region Engine ---

type ShardRegion struct {
	mu        sync.RWMutex
	nodeID    string
	hashRing  *HashRing
	entities  map[string]*EntityActor
	transport func(targetNode string, env Envelope) (Response, error) // Simulasi RPC
}

func NewShardRegion(nodeID string, ring *HashRing) *ShardRegion {
	return &ShardRegion{
		nodeID:   nodeID,
		hashRing: ring,
		entities: make(map[string]*EntityActor),
	}
}

func (sr *ShardRegion) SetTransport(t func(string, Envelope) (Response, error)) {
	sr.transport = t
}

func (sr *ShardRegion) Tell(env Envelope) (Response, error) {
	targetNode, err := sr.hashRing.GetNode(env.EntityID)
	if err != nil {
		return Response{}, err
	}

	// Jika target bukan node lokal, route via transport inter-node
	if targetNode != sr.nodeID {
		if sr.transport != nil {
			return sr.transport(targetNode, env)
		}
		return Response{}, fmt.Errorf("remote node %s unreachable: transport undefined", targetNode)
	}

	// Target adalah local node
	sr.mu.Lock()
	actor, exists := sr.entities[env.EntityID]
	if !exists || atomic.LoadInt32(&actor.isStopping) == 1 {
		actor = NewEntityActor(env.EntityID)
		sr.entities[env.EntityID] = actor
	}
	sr.mu.Unlock()

	actor.inbox <- env
	res := <-env.ReplyChan
	return res, nil
}

func main() {
	ring := NewHashRing(100)
	ring.AddNode("node-alpha")
	ring.AddNode("node-beta")

	regionAlpha := NewShardRegion("node-alpha", ring)
	regionBeta := NewShardRegion("node-beta", ring)

	// Inisialisasi Mock Transport Loopback antar Region
	transport := func(targetNode string, env Envelope) (Response, error) {
		if targetNode == "node-alpha" {
			return regionAlpha.Tell(env)
		} else if targetNode == "node-beta" {
			return regionBeta.Tell(env)
		}
		return Response{}, errors.New("node unknown")
	}

	regionAlpha.SetTransport(transport)
	regionBeta.SetTransport(transport)

	// Uji 1: Kirim request ke Entity yang memetakan ke Node lain
	targets := []string{"player_xyz_01", "player_abc_99", "boss_dragon_world"}

	for _, target := range targets {
		destNode, _ := ring.GetNode(target)
		fmt.Printf("Entity %s mapped to Hash Ring -> %s\n", target, destNode)

		replyCh := make(chan Response, 1)
		env := Envelope{
			EntityID:  target,
			Action:    "MOVE",
			Data:      []byte("124.5,88.0,12.0"),
			ReplyChan: replyCh,
		}

		// Kirim selalu via regionAlpha, routing internal akan bekerja otomatis
		res, err := regionAlpha.Tell(env)
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			continue
		}
		fmt.Printf("Executed on [%s] Result: %s\n", destNode, res.Result)
	}

	// Demonstrasi Stash & Passivation
	fmt.Println("\nWaiting for passivation sweep...")
	time.Sleep(6 * time.Second)

	// Akses kembali entity yang sudah ter-passivate -> Auto Rehydration
	fmt.Println("Accessing passivated entity (Auto-Rehydration)...")
	replyCh := make(chan Response, 1)
	res, err := regionAlpha.Tell(Envelope{
		EntityID:  "player_xyz_01",
		Action:    "DAMAGE",
		Data:      nil,
		ReplyChan: replyCh,
	})
	if err != nil {
		fmt.Printf("Error: %v\n", err)
	} else {
		fmt.Printf("Rehydration Success. Result: %s\n", res.Result)
	}
}
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Konteks Sistem
*   **Genre Game**: Massive Multiplayer Online Action RPG (PvP Spatial).
*   **Beban Puncak**: 120.000 Concurrent Users (CCU), 400 node kluster server terdistribusi di multi-AZ (AWS).
*   **Karakteristik Komputasi**: Real-time positional validation, non-blocking tick-loop (20 Hz per zone shard), spatial entity tracking.

#### Arsitektur Kluster Produksi
```
                                        +----------------------------+
                                        | Elastic Load Balancer (UDP)|
                                        +--------------+-------------+
                                                       |
                             +-------------------------+-------------------------+
                             |                                                   |
                   +---------v---------+                               +---------v---------+
                   |  Gateway Node 01  |                               |  Gateway Node 02  |
                   +----+------------+-+                               +----+------------+-+
                        |            |                                      |            |
         +--------------+            +---------------+       +--------------+            +--------------+
         |                                           |       |                                          |
+--------v--------------------------------+        +-v-------v-------------------------------+        +-v---------------------------------------+
| Core Node A (Shard Region 01-100)       |        | Core Node B (Shard Region 101-200)      |        | Core Node C (Shard Region 201-300)      |
| +-------------------------------------+ |        | +-------------------------------------+ |        | +-------------------------------------+ |
| | Virtual Actor: Room 42 (Tick Engine)| | <====> | | Virtual Actor: Player 88312         | | <====> | | Virtual Actor: Guild War Manager   | |
| +-------------------------------------+ |  gRPC  | +-------------------------------------+ |  gRPC  | +-------------------------------------+ |
| Memberlist / SWIM Consensus Agent     |  Mesh   | Memberlist / SWIM Consensus Agent     |  Mesh   | Memberlist / SWIM Consensus Agent     |
+-----------------------------------------+        +-----------------------------------------+        +-----------------------------------------+
                     |                                                  |                                                  |
                     +----------------------------------+---------------+--------------------------------------------------+
                                                        |
                                       +----------------v------------------+
                                       | Redis Cluster + ScyllaDB (Snap)   |
                                       +-----------------------------------+
```

#### Kasus Insiden Produksi (Post-Mortem: The Cascading Death Spiral)
*   **Insiden**: Saat Boss Raid event, 15.000 pemain berkumpul di satu area virtual. Core Node B mengalami *Out-Of-Memory (OOM)* karena ukuran mailbox aktor melonjak tajam (backpressure gagal).
*   **Dampak Rantai**: SWIM protocol mendeteksi Core Node B *Dead*. Shard Coordinator memicu mass-rehydration 15.000 Virtual Actors ke Core Node A dan C secara bersamaan.
*   **Thundering Herd**: Database snapshot (ScyllaDB) mengalami *spike latency* hingga 4.5 detik. Core Node A dan C kehabisan thread pool karena *blocking wait* pada proses rehydration, menyebabkan SWIM *Ack timeout* dan ditandai *Dead* oleh node lain. Terjadi *total cluster collapse*.

#### Rekayasa Solusi Penanganan:
1.  **Backpressure & Mailbox Bounding**: Mailbox dibatasi secara ketat maksimal 2.048 pesan. Jika penuh, client gateway menerima respon `DROPPED_CONGESTION` dan memotong transmisi data yang tidak kritikal (misal: non-combat cosmetic packet).
2.  **Circuit Breaker & Bulkhead pada Rehydration**: Rehidrasi massal dibatasi menggunakan *token bucket rate limiter* (maksimal 200 aktor per detik per node). Sisanya ditahan di stash gateway.
3.  **Split Sharding (Sub-Actors)**: Aktor Ruangan dipecah menjadi *Spatial Quadtree Actors*. Tiap sub-sektor peta dikelola oleh aktor terpisah, mencegah konsentrasi beban ke satu titik proses.

---

### 9. Trade-offs

| Aspek | Opsi A: Virtual Actor (Grains) | Opsi B: Explicit Dedicated Server Process |
| :--- | :--- | :--- |
| **Pemanfaatan Resource** | **Tinggi (Elastis)**. Aktor yang idle otomatis passivated. Server dapat menampung rasio entitas per GB RAM yang sangat tinggi. | **Rendah hingga Sedang**. Proses instance dedicated (misal: UE Dedicated Server) membutuhkan alokasi memori dasar yang besar sekalipun ruangan kosong. |
| **Kompleksitas State Sync** | **Kompleks**. Memerlukan infrastruktur *event sourcing* atau berkala *snapshotting* untuk mengatasi *node eviction*. | **Sederhana**. State berada di memori proses dari awal sesi pertandingan sampai game selesai (*match-based*). |
| **Latensi Antar-Aktor** | **Variabel (0.01ms - 5ms)**. 0.01ms jika aktor berada di node yang sama (*in-proc pointer passing*), 1-5ms jika remote (*serialization + network hop*). | **Deterministik**. Seluruh entitas dalam match berada di address space yang sama (akses memori lokal konstan). |
| **Biaya Operasional (Infra)** | **Efisiensi Finansial Tinggi**. Penggabungan ribuan entitas ke kluster terkonsolidasi memangkas *idle cost* CPU instance. | **Mahal**. Seringkali membutuhkan autoscaling kelompok instance VM berukuran besar yang lambat merespons *traffic spike*. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Blocking Call di Dalam Message Receive Loop
*   **Anti-Pattern**:
    ```go
    // FATAL: Menghentikan pemrosesan pesan lain di aktor yang sama
    func (a *PlayerActor) Receive(msg Message) {
        resp, _ := http.Get("http://inventory-api/items") // BLOCKING I/O
        a.updateInventory(resp)
    }
    ```
*   **Solusi**: Gunakan mekanisme Asynchronous Pipe-To-Self atau Task Continuation. Buat asynchronous job di luar *actor main loop*, lalu kirimkan hasilnya kembali ke Mailbox aktor dalam bentuk pesan baru.

#### 2. Poison Pill Cascade & Mailbox Congestion
*   **Gejala**: Memori node kluster naik linear hingga OOM; latensi tick melompat dari 15ms menjadi 5000ms.
*   **Akar Masalah**: Pesan rusak (*malformed payload*) menyebabkan panic di aktor, memicu supervisor melakukan restart tanpa batas sementara pesan yang sama tetap diproses ulang, mengunci antrean.
*   **Deteksi & Perbaikan**:
    *   Terapkan **Dead Letter Queue (DLQ)**. Jika sebuah pesan gagal diproses setelah $N$ percobaan (misal: 3 kali), isolasi pesan ke DLQ dan lewati pesan tersebut.
    *   Pasang *Mailbox Watermark Metrics*:
        $$\text{Alert Trigger}: \text{Len(Mailbox)} > 0.8 \times \text{MaxCapacity}$$

#### 3. Split-Brain Divergence
*   **Gejala**: Dua kelompok pemain di room yang sama berada di dua server fisik berbeda; perubahan status gold/inventory menduplikasi (*Item Duplication Exploit*).
*   **Akar Masalah**: Network split terjadi antara AZ-1 dan AZ-2; kedua sisi mempromosikan diri sebagai quorum mayoritas tanpa lease resolver eksternal.
*   **Solusi**: Wajib implementasikan *Fencing Token* berbasis etcd key lease. Sebelum aktor menerima mutasi transaksi state, node harus memvalidasi kepemilikan lease aktif dengan TTL pendek (1-2 detik).

---

### 11. Best Practices (Production Checklist)

1.  [ ] **Zero-Allocation Serialization**: Gunakan Protobuf dengan generator buffer pooling atau FlatBuffers untuk komunikasi inter-node, hindari JSON/standard `encoding/gob`.
2.  [ ] **Strict Supervision Strategies**: Konfigurasi supervisor hierarchy (`OneForOne` vs `AllForOne`) dengan batas `maxRetries` dan `withinTimeRange`.
3.  [ ] **Heartbeat Tuning**:
    *   SWIM Gossip Interval: 200ms - 500ms.
    *   Suspicion Timeout Factor: $\log(\text{ClusterSize}) \times \text{Interval}$.
4.  [ ] **Mailbox Sizing**: Tetapkan kapasitas tetap (*bounded channels*). Jangan gunakan *unbounded queue* di tingkat produksi game.
5.  [ ] **Backpressure Handling**: Terapkan drop-policy yang jelas: Drop oldest, drop newest, atau tolak paket di transport level dengan return error code ke gateway.
6.  [ ] **Graceful Drain / Coordinated Shutdown**: Saat node di-terminate (misal saat autoscaling in), jalankan fase:
    *   (a) Hentikan penerimaan message baru dari gateway,
    *   (b) Flush seluruh dirty state ke persistence store,
    *   (c) Handoff shard allocation ke node lain melalui Shard Coordinator,
    *   (d) Kirim pesan SWIM `Leave` ke kluster.
7.  [ ] **Deterministic Actor Turn**: Pastikan mutasi internal state aktor benar-benar single-threaded tanpa concurrency internal tersembunyi.

---

### 12. Hands-on Practice
Simpan seluruh implementasi praktikum ini pada direktori repositori: `hands-on/m02/`

#### Skenario Laboratorium
Membangun simulasi cluster 3-Node lokal dengan *fault-injection* jaringan:
1.  **Langkah 1**: Buat direktori `hands-on/m02/` dan inisialisasi module:
    ```bash
    mkdir -p hands-on/m02 && cd hands-on/m02
    go mod init cluster-actor-m02
    ```
2.  **Langkah 2**: Tulis file `cluster_sim.go` yang mengimplementasikan arsitektur *Practical Example* di atas dengan penambahan integrasi metrik performa (*tick time*, *latency tracking*).
3.  **Langkah 3**: Tambahkan simulasi pemutusan node (*Network Isolation*):
    *   Jalankan 3 node (`node-1`, `node-2`, `node-3`).
    *   Kirim traffic acak sebanyak 5.000 pesan per detik.
    *   Putus koneksi `node-2` dari routing ring secara tiba-tiba saat runtime.
4.  **Langkah 4**: Amati proses handoff dan *rehydration* entitas dari `node-2` ke node yang masih hidup tanpa menyebabkan race-condition pada database snapshot.

---

### 13. Exercises

#### Level Easy
Tambahkan struktur metrik pada `EntityActor` untuk mencatat jumlah pesan yang berhasil diproses, jumlah pesan yang di-stash, dan waktu tunggu rata-rata di mailbox. Ekspor data ini ke log output setiap 5 detik.

#### Level Medium
Modifikasi `ShardRegion` agar mendukung operasi **Graceful Handoff**. Ketika perintah `DrainNode(targetNode)` dipanggil, node tersebut harus menyelesaikan pemrosesan antrean pesan di mailbox-nya, mengekspor state ke layer persistensi, dan menyerahkan kepemilikan sharding ke node tetangga sebelum ditutup.

#### Level Hard
Rancang dan implementasikan modul **Distributed Lease Provider** sederhana menggunakan Channel dan Mutex terdistribusi (atau integrasi mini-etcd client). Jika sebuah Shard Region terisolasi dari *majority partition* kluster, batalkan seluruh siklus pemrosesan aktor di region tersebut dalam waktu $\le 500\text{ ms}$ untuk menghindari modifikasi state yang tidak sah.

---

### 14. Challenge

#### Deskripsi Skenario
Sebuah game Battle Royale skala besar (100 pemain per arena) memiliki mekanisme *Spatial Zone Boundary* yang membagi area pulau menjadi 4 Sub-Kuadran. Masing-masing Sub-Kuadran dikelola oleh satu aktor (`ZoneActor`) pada node yang berbeda di kluster.

```
       Quad 1 (Node A)    |    Quad 2 (Node B)
                          |
   -----------------------+-----------------------
                          |
       Quad 3 (Node C)    |    Quad 4 (Node D)
```

Ketika seorang pemain bergerak melewati garis batas kuadran (contoh: dari Quad 1 ke Quad 2), sistem harus melakukan **Seamless Actor Handoff**:
1.  Tidak boleh ada *tick frame* yang hilang bagi pemain tersebut (zero desync).
2.  Proyektil peluru yang ditembakkan melintasi batas kuadran harus dapat berpindah kepemilikan kalkulasi tabrakan (*collision detection*) antar-node dengan deterministik.
3.  Jika Node B tiba-tiba mengalami *network latency spike* (ping > 300ms), transfer entitas harus di-*abort* secara elegan dan pemain ditahan sementara di batas Quad 1 dengan interpolasi visual.

#### Tugas Arsitektural
Rancang spesifikasi arsitektur state handoff, urutan serialisasi pesan, diagram sequence mitigasi kegagalan, dan skema *dual-write/shadow-processing* untuk memastikan perpindahan berlangsung mulus di bawah 30 milidetik.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual Singkat)
1.  Apa yang dimaksud dengan *Location Transparency* dalam Distributed Actor System?
    *   A. Setiap aktor mengetahui alamat IP publik dari klien.
    *   B. Pengirim pesan tidak perlu mengetahui lokasi node fisik dari aktor penerima; routing ditangani oleh sistem kluster.
    *   C. Seluruh aktor harus ditempatkan di server fisik yang sama agar lokasi seragam.
    *   D. Aktor hanya dapat berkomunikasi menggunakan GPS koordinat di dalam game.
2.  Apa fungsi utama dari mekanisme *Actor Passivation*?
    *   A. Menghentikan aktor yang curang (*cheater*).
    *   B. Menghapus state aktor dari database secara permanen.
    *   C. Mengeluarkan instance aktor yang idle dari RAM setelah menyimpan snapshot state, guna menghemat memori server.
    *   D. Memaksa aktor mengirim pesan ke server database setiap tick.
3.  Pada protokol SWIM, apa tujuan dari mekanisme *Suspicion* sebelum menandai node *Dead*?
    *   A. Mengurangi false-positive deteksi kematian akibat lonjakan latensi jaringan sementara (*transient network lag*).
    *   B. Menghapus data logging yang tidak diperlukan.
    *   C. Mempercepat proses reboot node secara paksa.
    *   D. Mengenkripsi pesan gossip antar server.
4.  Apa yang terjadi jika kita menggunakan antrean *Unbounded Mailbox* pada game server dengan CCU sangat tinggi?
    *   A. Latensi pengiriman pesan menjadi 0 ms.
    *   B. Server berisiko mengalami *Out Of Memory (OOM)* jika produsen pesan lebih cepat dibanding konsumen pesan.
    *   C. Data pemain otomatis tersimpan ke disk.
    *   D. Kecepatan CPU node meningkat dua kali lipat.
5.  Apa perbedaan utama antara *Classic Actor* (seperti Erlang/Akka standar) dan *Virtual Actor* (seperti Orleans)?
    *   A. Virtual Actor tidak memerlukan pemrosesan CPU.
    *   B. Virtual Actor dikelola siklus hidupnya secara otomatis oleh platform (auto-instantiate saat dipanggil, auto-passivate saat idle).
    *   C. Classic Actor tidak dapat menerima pesan jaringan.
    *   D. Virtual Actor hanya bisa berjalan di lingkungan cloud AWS.

#### Bagian 2: Intermediate (Analisis Arsitektur)
6.  Jelaskan mengapa blocking operation (seperti direct SQL queries atau sync HTTP calls) di dalam method `Receive()` aktor merupakan antipattern paling destruktif pada sistem aktor game server!
7.  Bagaimana peran *Consistent Hashing Ring* dalam meminimalisir migrasi state ketika sebuah node baru ditambahkan ke dalam kluster?
8.  Dalam implementasi Virtual Actor, jelaskan kegunaan konsep **Message Stashing** selama proses rehidrasi state berlangsung!
9.  Mengapa protokol SWIM gossip lebih scalable ($O(\log N)$) dibandingkan metode tradisional *all-to-all heartbeating* ($O(N^2)$)?
10. Apa risiko terbesar dari penerapan strategi supervisor `AllForOne` di dalam sistem game di mana ribuan aktor pemain berada di bawah satu supervisor yang sama?

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario Kasus 1**: Pada pukul 20:00, database game Anda mengalami degradasi latensi tulis dari 5ms menjadi 800ms. Seluruh Virtual Actor yang menjalankan auto-save periodik mulai menumpuk pesan di mailbox-nya. Analisis apa yang akan terjadi pada kluster jika tidak ada sistem *Backpressure*, dan rancang mitigasi teknisnya!
12. **Skenario Kasus 2**: Kluster server Anda terbagi menjadi dua partisi: Node [A, B] dan Node [C, D, E] akibat jalur jaringan antar-rack terputus. Jelaskan bagaimana algoritma *Quorum-based Split Brain Resolver* merespons situasi ini untuk memastikan data inventory pemain tidak terkorupsi!
13. **Skenario Kasus 3**: Seorang desainer game membuat fitur world boss di mana 2.000 pemain dapat memukul boss yang sama secara bersamaan dalam interval 100ms. Jika boss tersebut diimplementasikan sebagai satu aktor tunggal (`WorldBossActor`), jelaskan mengapa mailbox bottleneck akan terjadi dan berikan rancangan perbaikan arsitekturnya (*Scatter-Gather* atau *Aggregation Worker Tree*)!

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Kunci Jawaban Bagian 1
1.  **B** — Pengirim pesan hanya merujuk ke Actor ID/Grain ID, Shard Region yang me-resolve lokasinya.
2.  **C** — Passivation mengosongkan footprint memori dari entitas yang tidak aktif tanpa kehilangan datanya.
3.  **A** — Suspicion mencegah node dideklarasikan mati hanya karena satu packet loss atau GC pause singkat.
4.  **B** — Unbounded queue terus mengonsumsi heap memory hingga proses di-kill oleh OS OOM Killer.
5.  **B** — Virtual Actor memisahkan eksistensi logis aktor dari instansiasi fisiknya di memori.

#### Panduan Jawaban Bagian 2
6.  **Analisis Blocking**: Aktor memproses pesan secara sekuensial (single-threaded turn). Jika thread terhenti menunggu I/O eksternal, seluruh pesan lain di antrean mailbox tertahan. Tick processing terhenti, latensi game melonjak, dan sistem timeout kluster dapat salah mendeteksi aktor sebagai *unresponsive*.
7.  **Consistent Hashing**: Menggunakan distributed hash ring memastikan bahwa saat node baru masuk (atau keluar), hanya $K/N$ kunci entitas yang perlu dipindahkan (di mana $K$ adalah total kunci, $N$ adalah jumlah node), bukan me-rehash seluruh kunci seperti pada modulo hashing biasa.
8.  **Message Stashing**: Saat aktor di-spawn secara on-demand, pemuatan state dari database membutuhkan waktu (asinkron). Pesan yang tiba selama jendela waktu ini tidak boleh ditolak atau di-drop; pesan disimpan di stash array lokal, lalu di-*unstash* dan diproses berurutan segera setelah status aktor menjadi *Hydrated*.
9.  **SWIM Scalability**: Pada all-to-all, beban transmisi melonjak eksponensial seiring bertambahnya node ($N \times (N-1)$ pesan). Pada SWIM, setiap node mengirim probe dengan frekuensi konstan ke target acak, menyebarkan metadata via infeksi epidemiologis (gossip), mempertahankan overhead bandwidth per node konstan tanpa peduli besarnya kluster.
10. **Supervision AllForOne**: Strategi ini mendikte bahwa jika *satu* anak gagal (crash), *seluruh* anak di bawah supervisor tersebut harus di-restart. Jika diterapkan pada ribuan pemain, error tak tertangani pada satu data pemain akan memicu pemutusan massal dan restart pada ribuan pemain lain yang tidak bersalah.

#### Panduan Jawaban Bagian 3 (Skenario Kasus)
11. **Skenario 1**:
    *   *Analisis*: Aktor akan memblokir siklus pemrosesan saat menunggu DB ack jika sinkron, atau kehabisan RAM karena buffer IO pool membengkak. Hal ini memicu GC pauses panjang, yang berujung pada SWIM timeout (node salah dikira mati).
    *   *Mitigasi*: Ubah arsitektur autosave menjadi *asynchronous detached snapshot worker*. Batasi mailbox capacity. Terapkan *adaptive rate shedding*: lewati snapshot interval saat antrean DB lambat, asalkan log transaksi (*write-ahead log*) tetap terjaga.
12. **Skenario 2**:
    *   *Penyelesaian*: Total node = 5. Quorum mayoritas adalah $\lfloor 5/2 \rfloor + 1 = 3$ node. Sub-kluster [A, B] hanya memiliki 2 node (minoritas), sehingga otomatis menghentikan Shard Region-nya (*self-fencing/poison pill*) dan menolak koneksi client. Sub-kluster [C, D, E] memiliki 3 node (mayoritas), memegang quorum, mempertahankan operasional, dan mengambil alih shard yang sebelumnya berada di A dan B secara aman.
13. **Skenario 3**:
    *   *Penyelesaian*: `WorldBossActor` menerima 20.000 pesan/detik, melampaui kemampuan single-thread processing (1 core CPU).
    *   *Solusi Arsitektur (Aggregation Tree)*: Buat 10 `DamageAggregatorActor` yang terdistribusi di beberapa node. Gateway me-routing serangan pemain ke aggregator secara round-robin/hashing. Aggregator mengakumulasi total damage setiap 50ms (windowing), lalu mengirimkan *satu* pesan rangkuman damage terkonsolidasi ke `WorldBossActor`. Boss Actor hanya perlu memproses 200 pembaruan/detik, mereduksi tekanan mailbox sebesar 99%.

---

### 16. Summary
*   Arsitektur **Distributed Virtual Actor** mengabstraksi lokasi fisik server, menyediakan mekanisme penskalaan horizontal masif, serta menjaga integritas state in-memory game multiplayer melalui model konkurensi single-threaded turn.
*   Keandalan kluster tingkat enterprise bertumpu pada 3 fondasi utama: keanggotaan terdesentralisasi berbasis **SWIM Gossip**, routing deterministik dengan **Consistent Hash Ring**, dan proteksi partisi menggunakan **Split-Brain Resolvers** berbasis lease/quorum.
*   Stabilitas produksi sangat bergantung pada penerapan disiplin arsitektural: tidak pernah melakukan pemanggilan *blocking I/O* di dalam aktor, mengisolasi pesan gagal ke Dead Letter Queue, membatasi ukuran mailbox dengan backpressure eksplisit, dan merancang pola agregasi bertingkat untuk entitas yang menjadi titik panas (*hotspot entities*) di dunia virtual.