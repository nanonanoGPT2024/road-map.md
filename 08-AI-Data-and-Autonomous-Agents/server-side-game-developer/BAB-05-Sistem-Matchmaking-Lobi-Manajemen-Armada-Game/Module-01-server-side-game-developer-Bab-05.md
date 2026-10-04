# Bab 05: Sistem Matchmaking, Lobi, & Manajemen Armada Game
**Modul 01: Desain Engine Matchmaking Skalabilitas Tinggi, State Synchronized Lobby, dan Game Server Fleet Orchestration**

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang Matchmaking Engine Berlatensi Rendah:** Mengimplementasikan algoritma tiket berbasis *Dynamic Expansion Window* (MMR + Ping Matrix) menggunakan struktur data terdistribusi.
- **Membangun Stateful Lobby System Bebas Race Condition:** Memprogram sistem lobi game berbasis *in-memory* dengan jaminan konsistensi data menggunakan Redis Lua Scripting dan optimistic concurrency control.
- **Mengorkestrasi Dedicated Game Server (DGS) Lifecycle:** Menghubungkan engine matchmaking dengan armada server game (Fleet Orchestrator) menggunakan standar alokasi gRPC berkinerja tinggi.
- **Menangani Degradasi & Starvation:** Menerapkan strategi injeksi autonomous bot/AI agent dan buffer-based auto-scaling untuk menjaga SLA alokasi armada game di bawah ambang batas P99 < 500ms.

---

### 2. Concept Overview

Sistem multiplayer modern bersandar pada tiga domain komputasi backend yang saling berkolaborasi secara asinkron:

```
[ Matchmaking Engine ]  ---> Menemukan N pemain dengan atribut seimbang (Skill, Latensi, Modus)
         │
         ▼
[ Stateful Lobby ]      ---> Menjaga status pra-pertandingan (Slot, Loadout, Party, Ready Check)
         │
         ▼
[ Fleet Management ]    ---> Mengalokasikan instance komputasi DGS (Dedicated Game Server)
```

#### The Triad Mental Model
1. **Matchmaker (Combinatorial Optimizer):** Mengubah *unstructured pool of requests* (tiket pemain individual dan *party*) menjadi *structured arrays* (tim yang seimbang). Sistem ini harus mengatasi masalah kombinatorial NP-hard di bawah batasan waktu ketat.
2. **Lobby (Synchronized State Machine):** Mengelola sesi transisi sebelum game server berjalan. Komponen ini menahan kepemilikan data pemain (*ownership*), koordinasi antar-anggota party, dan memastikan tidak ada pemain yang dapat berada di dua pertandingan sekaligus (*double reservation*).
3. **Fleet Manager (Infrastructure Controller):** Bertanggung jawab atas ketersediaan proses DGS biner (seperti Unreal Engine atau Unity headless server). Mengingat DGS bersifat *heavyweight* (memakan 1–4 core CPU dan 1–4 GB RAM per instance) serta *stateful* (tidak bisa dihentikan mendadak saat game berlangsung), orkestrasinya tidak dapat ditangani oleh Horizontal Pod Autoscaler (HPA) Kubernetes standar. Pendekatan yang dibutuhkan adalah kontrol armada khusus (misal: Agones lifecycle model).

---

### 3. Why It Matters

Dalam arsitektur game kompetitif skala enterprise:
- **Retensi Pemain vs. Queue Time:** Penambahan waktu tunggu antrean (*queue time*) sebesar 10 detik meningkatkan churn rate hingga 8%. Sebaliknya, match yang tidak adil (*skill mismatch*) menyebabkan *rage quit* dan penurunan Customer Lifetime Value (LTV).
- **Efisiensi Finansial (Cloud Compute):** DGS yang idle membakar biaya infrastruktur cloud secara masif. Sebaliknya, kehabisan armada siap pakai (*fleet capacity exhaustion*) mengakibatkan *allocation timeout* dan kegagalan peluncuran sesi game.
- **Integritas Konkurensi:** Pada skala puluhan ribu concurrent users (CCU), skenario seperti pembatalan tiket di milidetik yang sama saat match ditemukan (*cancellation race conditions*) dapat merusak state machine, membuat server game kosong (*zombie matches*), dan mengunci pemain dalam antrean tanpa ujung.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur berikut mengisolasi domain *read/write matchmaking*, *distributed coordination*, dan *server compute allocation*:

```
+---------------------------------------------------------------------------------------+
|                                    CLIENT LAYER                                       |
|  [ Player Client A ]            [ Player Client B ]            [ Player Client C ]    |
+----------+-------------------------------+-------------------------------+------------+
           │                               │                               │
           │ (WebSocket/HTTP2)             │ (WebSocket/HTTP2)             │
           ▼                               ▼                               ▼
+---------------------------------------------------------------------------------------+
|                         EDGE / API GATEWAY (Envoy / Traefik)                          |
+------------------------------------------+--------------------------------------------+
                                           │
                        Routing via Player ID Hash / gRPC
                                           ▼
+---------------------------------------------------------------------------------------+
|                                  LOBBY SERVICE CLUSTER                                |
|  - Validasi Status Pemain        - Read/Write Lobby State     - Broadcast Party Event |
+------------------+-----------------------------------------------+--------------------+
                   │                                               │
     Atomic Ops / Distributed Lock                    Pub/Sub State Sync
                   ▼                                               ▼
+------------------------------------+           +--------------------------------------+
|       REDIS CLUSTER (PRIMARY)      |           |     REDIS CLUSTER (PUBSUB / BUS)     |
| - Key: `lobby:{id}` (Hash)         |           | - Channel: `lobby:events:{id}`       |
| - Key: `player:session:{id}`       |           |                                      |
+------------------+-----------------+           +--------------------------------------+
                   │
         Enqueue Matching Ticket
                   ▼
+---------------------------------------------------------------------------------------+
|                                MATCHMAKING ENGINE CORE                                |
|                                                                                       |
|  +------------------------+   Evaluate Intervals    +------------------------------+  |
|  |   Ticket Ingestor      | --------------------->  |       Matcher Worker         |  |
|  | - Region-based Queues  |                         | - Dynamic Range Expansion    |  |
|  | - Sorted Sets by MMR   |                         | - Ping Matrix Optimizer      |  |
|  +------------------------+                         +--------------+---------------+  |
+--------------------------------------------------------------------│------------------+
                                                                     │ Match Formed!
                                                                     ▼
+---------------------------------------------------------------------------------------+
|                              FLEET DIRECTOR & ALLOCATOR                               |
|  1. Request Server Allocation via gRPC                                                |
|  2. Pass Context (MatchID, IP/Port, Encryption Keys)                                  |
+------------------------------------------+--------------------------------------------+
                                           │
                         gRPC: Allocate()  ▼
+---------------------------------------------------------------------------------------+
|                       KUBERNETES ARMADA (AGONES ORCHESTRATOR)                         |
|                                                                                       |
|    +-----------------------------+           +-----------------------------+          |
|    | GameServer Pod 01 (Allocated|           | GameServer Pod 02 (Ready)   |          |
|    | - Dedicated Binary (UE5)    |           | - Dedicated Binary (UE5)    |          |
|    | - Agones Sidecar SDK        |           | - Agones Sidecar SDK        |          |
|    +-----------------------------+           +-----------------------------+          |
|    +-----------------------------------------------------------------------+          |
|    | Fleet Autoscaler Controller (Buffer: Min 10% Ready Instances)         |          |
+----+-----------------------------------------------------------------------+----------+
```

#### DGS Lifecycle State Machine

```
                   crash / unrecoverable
       +--------------------------------------------+
       │                                            │
       ▼                                            │
 [ NonExistent ]                                    │
       │                                            │
       │ Controller provisions Pod                  │
       ▼                                            │
    [ Scheduled ]                                   │
       │                                            │
       │ Binary boots, AgonesSDK().Ready()          │
       ▼                                            │
     [ Ready ] <------- Game Finishes (Recycle) ---+│
       │                                            │
       │ Director calls Allocate()                  │
       ▼                                            │
   [ Allocated ]                                    │
       │                                            │
       │ Match Ends / AgonesSDK().Shutdown()        │
       ▼                                            │
 [ Terminating ] -----------------------------------+
       │
       ▼
 [ Tombstone ]
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Matchmaking Queue & Dynamic Range Expansion
Algoritma engine menggunakan interval waktu diskrit (*evaluation tick*). Tiket disimpan pada Redis Sorted Sets (`ZSET`), di mana *Score* merepresentasikan MMR (Matchmaking Rating).

Untuk menghindari situasi *starvation* pada pemain dengan MMR ekstrem (paling bawah atau paling atas), sistem menerapkan pelebaran jendela toleransi secara dinamis:

$$\Delta\text{MMR}(t) = \text{MMR}_{\text{base}} \times \left(1 + \alpha \cdot \ln(1 + \beta \cdot t)\right)$$

- $t$: Durasi waktu tunggu tiket dalam antrean (detik).
- $\alpha, \beta$: Koefisien pelebaran jangkauan toleransi skill.

Jika $t > t_{\text{bot\_threshold}}$, sistem secara deterministik menginjeksi autonomous agent/bot ke dalam ruang pencarian untuk mencegah *infinite queue*.

#### B. Lobby State Synchronization & Atomic Slots
Masalah utama dalam sistem lobi terdistribusi adalah *Slot Contention*: dua pemain mengklaim slot terakhir secara bersamaan. Pendekatan konvensional dengan *read-then-write* database relasional memicu *deadlock* atau *inconsistent states*.

Solusi enterprise menggunakan Redis Lua Scripting yang dieksekusi secara atomik single-threaded di Redis engine. Skrip memvalidasi kapasitas maksimal, status kesiapan (*ready status*), dan mengunci slot tanpa risiko *lost updates*.

#### C. Dedicated Game Server (DGS) Allocation Handshake
1. **Pemesanan (*Allocation Request*):** Matchmaker mengidentifikasi kecocokan dan mengirimkan permintaan alokasi ke *Fleet Director*.
2. **Kueri Agones CRD:** Director memanggil control plane cluster (Agones API) untuk mengalihkan status satu server dari `Ready` ke `Allocated`. Operasi ini harus idempotent; jika timeout, token alokasi tidak boleh menduplikasi pemesanan server lain.
3. **Pemberitahuan (*Connection Dispatch*):** Setelah IP publik dan Port didapatkan, informasi dikirimkan kembali ke klien melalui koneksi WebSocket Lobby yang aktif.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi skala enterprise dalam bahasa **Go**, mencakup Matchmaker Worker dengan sliding-window expansion, atomic Lua-based Lobby Manager, dan Fleet Allocator mock client.

#### Struktur Modul
```
game-backend/
├── go.mod
├── cmd/main.go
└── pkg/
    ├── fleet/allocator.go
    ├── lobby/manager.go
    └── matchmaker/engine.go
```

#### `go.mod`
```go
module game-backend

go 1.22

require (
	github.com/google/uuid v1.6.0
	github.com/redis/go-redis/v9 v9.5.1
)
```

#### `pkg/matchmaker/engine.go`
```go
package matchmaker

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

type Ticket struct {
	ID        string    `json:"id"`
	PlayerID  string    `json:"player_id"`
	MMR       int       `json:"mmr"`
	Region    string    `json:"region"`
	CreatedAt time.Time `json:"created_at"`
}

type Match struct {
	MatchID string    `json:"match_id"`
	Tickets []Ticket  `json:"tickets"`
	Region  string    `json:"region"`
}

type Engine struct {
	rdb            *redis.Client
	region         string
	teamSize       int
	baseMMRSpread  int
	expansionAlpha float64
	expansionBeta  float64
	botThreshold   time.Duration
	stopCh         chan struct{}
	wg             sync.WaitGroup
}

func NewEngine(rdb *redis.Client, region string, teamSize int) *Engine {
	return &Engine{
		rdb:            rdb,
		region:         region,
		teamSize:       teamSize,
		baseMMRSpread:  50,
		expansionAlpha: 1.5,
		expansionBeta:  0.05,
		botThreshold:   45 * time.Second,
		stopCh:         make(chan struct{}),
	}
}

func (e *Engine) EnqueueTicket(ctx context.Context, ticket Ticket) error {
	ticket.CreatedAt = time.Now().UTC()
	data, err := json.Marshal(ticket)
	if err != nil {
		return fmt.Errorf("failed to marshal ticket: %w", err)
	}

	queueKey := fmt.Sprintf("mm:queue:%s", e.region)
	metaKey := fmt.Sprintf("mm:tickets:%s", ticket.ID)

	pipe := e.rdb.TxPipeline()
	pipe.Set(ctx, metaKey, data, 10*time.Minute)
	pipe.ZAdd(ctx, queueKey, redis.Z{
		Score:  float64(ticket.MMR),
		Member: ticket.ID,
	})
	_, err = pipe.Exec(ctx)
	if err != nil {
		return fmt.Errorf("failed to enqueue ticket: %w", err)
	}
	return nil
}

func (e *Engine) Start(ctx context.Context, outMatches chan<- Match) {
	e.wg.Add(1)
	go func() {
		defer e.wg.Done()
		ticker := time.NewTicker(1000 * time.Millisecond)
		defer ticker.Stop()

		for {
			select {
			case <-e.stopCh:
				return
			case <-ctx.Done():
				return
			case <-ticker.C:
				e.processQueue(ctx, outMatches)
			}
		}
	}()
}

func (e *Engine) Stop() {
	close(e.stopCh)
	e.wg.Wait()
}

func (e *Engine) calculateAllowedSpread(waitTime time.Duration) int {
	t := waitTime.Seconds()
	multiplier := 1.0 + e.expansionAlpha*math.Log(1.0+e.expansionBeta*t)
	return int(float64(e.baseMMRSpread) * multiplier)
}

func (e *Engine) processQueue(ctx context.Context, outMatches chan<- Match) {
	queueKey := fmt.Sprintf("mm:queue:%s", e.region)

	// Dapatkan semua ID tiket dalam antrean
	ticketIDs, err := e.rdb.ZRange(ctx, queueKey, 0, -1).Result()
	if err != nil || len(ticketIDs) < e.teamSize*2 {
		return
	}

	matchedIndices := make(map[string]bool)

	for i := 0; i < len(ticketIDs); i++ {
		leadID := ticketIDs[i]
		if matchedIndices[leadID] {
			continue
		}

		leadMeta, err := e.fetchTicketMeta(ctx, leadID)
		if err != nil {
			continue
		}

		waitTime := time.Since(leadMeta.CreatedAt)
		allowedDelta := e.calculateAllowedSpread(waitTime)

		potentialGroup := []Ticket{*leadMeta}

		// Cari kandidat yang sesuai dalam rentang MMR
		for j := i + 1; j < len(ticketIDs); j++ {
			candidateID := ticketIDs[j]
			if matchedIndices[candidateID] {
				continue
			}

			candMeta, err := e.fetchTicketMeta(ctx, candidateID)
			if err != nil {
				continue
			}

			if int(math.Abs(float64(candMeta.MMR-leadMeta.MMR))) <= allowedDelta {
				potentialGroup = append(potentialGroup, *candMeta)
				if len(potentialGroup) == e.teamSize*2 {
					break
				}
			}
		}

		targetSize := e.teamSize * 2

		// Evaluasi Injeksi Bot jika antrean melewati batas ambang waktu tunggu
		if len(potentialGroup) < targetSize && waitTime >= e.botThreshold {
			neededBots := targetSize - len(potentialGroup)
			for b := 0; b < neededBots; b++ {
				botTicket := Ticket{
					ID:        fmt.Sprintf("bot-%d-%s", b, leadID),
					PlayerID:  fmt.Sprintf("agent-bot-%d", b),
					MMR:       leadMeta.MMR,
					Region:    e.region,
					CreatedAt: time.Now().UTC(),
				}
				potentialGroup = append(potentialGroup, botTicket)
			}
		}

		// Jika jumlah grup pertandingan terpenuhi, finalisasi match
		if len(potentialGroup) == targetSize {
			var idsToRemove []interface{}
			for _, t := range potentialGroup {
				if t.ID[:3] != "bot" {
					matchedIndices[t.ID] = true
					idsToRemove = append(idsToRemove, t.ID)
				}
			}

			if len(idsToRemove) > 0 {
				e.rdb.ZRem(ctx, queueKey, idsToRemove...)
			}

			outMatches <- Match{
				MatchID: fmt.Sprintf("match-%d", time.Now().UnixNano()),
				Tickets: potentialGroup,
				Region:  e.region,
			}
		}
	}
}

func (e *Engine) fetchTicketMeta(ctx context.Context, ticketID string) (*Ticket, error) {
	metaKey := fmt.Sprintf("mm:tickets:%s", ticketID)
	data, err := e.rdb.Get(ctx, metaKey).Bytes()
	if err != nil {
		return nil, err
	}
	var t Ticket
	if err := json.Unmarshal(data, &t); err != nil {
		return nil, err
	}
	return &t, nil
}
```

#### `pkg/lobby/manager.go`
```go
package lobby

import (
	"context"
	"errors"
	"fmt"

	"github.com/redis/go-redis/v9"
)

var (
	ErrLobbyFull     = errors.New("lobby capacity reached")
	ErrLobbyNotFound = errors.New("lobby does not exist")
	ErrSlotTaken     = errors.New("target slot index occupied")
)

const joinLobbyLua = `
local lobbyKey = KEYS[1]
local playerID = ARGV[1]
local maxCap   = tonumber(ARGV[2])

if redis.call("EXISTS", lobbyKey) == 0 then
    return -1
end

local currentMembers = redis.call("SCARD", lobbyKey .. ":members")
if currentMembers >= maxCap then
    return -2
end

redis.call("SADD", lobbyKey .. ":members", playerID)
redis.call("HSET", lobbyKey .. ":player_state", playerID, "NOT_READY")
return 1
`

type Manager struct {
	rdb *redis.Client
}

func NewManager(rdb *redis.Client) *Manager {
	return &Manager{rdb: rdb}
}

func (m *Manager) CreateLobby(ctx context.Context, lobbyID string, maxCapacity int) error {
	lobbyKey := fmt.Sprintf("lobby:%s", lobbyID)
	err := m.rdb.HSet(ctx, lobbyKey, map[string]interface{}{
		"max_capacity": maxCapacity,
		"state":        "FORMING",
	}).Err()
	if err != nil {
		return fmt.Errorf("failed to create lobby: %w", err)
	}
	return nil
}

func (m *Manager) JoinLobby(ctx context.Context, lobbyID, playerID string, maxCapacity int) error {
	lobbyKey := fmt.Sprintf("lobby:%s", lobbyID)
	res, err := m.rdb.Eval(ctx, joinLobbyLua, []string{lobbyKey}, playerID, maxCapacity).Int()
	if err != nil {
		return fmt.Errorf("redis execution failure: %w", err)
	}

	switch res {
	case -1:
		return ErrLobbyNotFound
	case -2:
		return ErrLobbyFull
	default:
		return nil
	}
}

func (m *Manager) SetPlayerReady(ctx context.Context, lobbyID, playerID string, isReady bool) error {
	stateStr := "NOT_READY"
	if isReady {
		stateStr = "READY"
	}
	lobbyKey := fmt.Sprintf("lobby:%s", lobbyID)
	return m.rdb.HSet(ctx, lobbyKey+":player_state", playerID, stateStr).Err()
}
```

#### `pkg/fleet/allocator.go`
```go
package fleet

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"
)

var ErrFleetExhausted = errors.New("no dedicated game servers available in target region")

type GameServerInstance struct {
	ID        string
	Address   string
	Port      int
	Region    string
	Status    string
	Allocated bool
}

type Allocator interface {
	AllocateServer(ctx context.Context, matchID string, region string) (*GameServerInstance, error)
}

// MockAgonesFleetManager mensimulasikan kontroler armada DGS
type MockAgonesFleetManager struct {
	mu      sync.Mutex
	servers map[string][]*GameServerInstance
}

func NewMockAgonesFleetManager() *MockAgonesFleetManager {
	mgr := &MockAgonesFleetManager{
		servers: make(map[string][]*GameServerInstance),
	}
	// Seed pool server
	mgr.servers["ap-southeast-1"] = []*GameServerInstance{
		{ID: "dgs-sea-01", Address: "103.21.244.2", Port: 7777, Region: "ap-southeast-1", Status: "Ready", Allocated: false},
		{ID: "dgs-sea-02", Address: "103.21.244.3", Port: 7778, Region: "ap-southeast-1", Status: "Ready", Allocated: false},
	}
	return mgr
}

func (m *MockAgonesFleetManager) AllocateServer(ctx context.Context, matchID string, region string) (*GameServerInstance, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	pool, exists := m.servers[region]
	if !exists {
		return nil, fmt.Errorf("invalid region %s: %w", region, ErrFleetExhausted)
	}

	for _, srv := range pool {
		if !srv.Allocated && srv.Status == "Ready" {
			srv.Allocated = true
			srv.Status = "Allocated"
			return srv, nil
		}
	}

	return nil, ErrFleetExhausted
}
```

#### `cmd/main.go`
```go
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"game-backend/pkg/fleet"
	"game-backend/pkg/lobby"
	"game-backend/pkg/matchmaker"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
)

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Inisialisasi Redis Client
	rdb := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
	})
	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Printf("Peringatan: Redis tidak tersedia (%v). Gunakan infrastruktur nyata di production.\n", err)
	}

	// 1. Inisialisasi Sub-sistem
	lobbyMgr := lobby.NewManager(rdb)
	matchEngine := matchmaker.NewEngine(rdb, "ap-southeast-1", 1) // 1v1 match untuk pengujian sederhana
	fleetMgr := fleet.NewMockAgonesFleetManager()

	matchesChan := make(chan matchmaker.Match, 100)

	// 2. Jalankan Engine Matchmaker
	matchEngine.Start(ctx, matchesChan)
	log.Println("[INFO] Engine Matchmaking berjalan...")

	// 3. Match Allocation Worker
	go func() {
		for {
			select {
			case <-ctx.Done():
				return
			case m := <-matchesChan:
				log.Printf("[MATCH FORMED] MatchID: %s | Pemain: %d\n", m.MatchID, len(m.Tickets))
				
				// Alokasikan Armada DGS
				allocCtx, allocCancel := context.WithTimeout(context.Background(), 2*time.Second)
				srv, err := fleetMgr.AllocateServer(allocCtx, m.MatchID, m.Region)
				allocCancel()

				if err != nil {
					log.Printf("[FLEET ERROR] Gagal mengalokasikan server untuk Match %s: %v\n", m.MatchID, err)
					continue
				}

				log.Printf("[DGS ALLOCATED] MatchID: %s dialokasikan ke Node: %s di IP: %s:%d\n",
					m.MatchID, srv.ID, srv.Address, srv.Port)
			}
		}
	}()

	// 4. Simulasi Ingesti Tiket
	go func() {
		p1 := uuid.New().String()
		p2 := uuid.New().String()

		_ = lobbyMgr.CreateLobby(ctx, "lob-test-01", 2)
		_ = lobbyMgr.JoinLobby(ctx, "lob-test-01", p1, 2)
		_ = lobbyMgr.JoinLobby(ctx, "lob-test-01", p2, 2)
		_ = lobbyMgr.SetPlayerReady(ctx, "lob-test-01", p1, true)
		_ = lobbyMgr.SetPlayerReady(ctx, "lob-test-01", p2, true)

		// Masukkan tiket pemain ke dalam engine
		_ = matchEngine.EnqueueTicket(ctx, matchmaker.Ticket{
			ID:       uuid.New().String(),
			PlayerID: p1,
			MMR:      1500,
			Region:   "ap-southeast-1",
		})

		_ = matchEngine.EnqueueTicket(ctx, matchmaker.Ticket{
			ID:       uuid.New().String(),
			PlayerID: p2,
			MMR:      1520, // MMR berdekatan
			Region:   "ap-southeast-1",
		})
	}()

	// Graceful Shutdown
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	<-sigCh

	log.Println("[SHUTDOWN] Menghentikan subsistem game backend...")
	matchEngine.Stop()
	cancel()
	log.Println("[SHUTDOWN] Selesai.")
}
```

---

### 7. Edge Cases & Failure Modes

#### 1. The "Ghost Allocation" Dilemma
- **Kasus:** Director Matchmaker memanggil API alokasi armada game. Server berhasil dialokasikan di Agones (`Allocated`), tetapi jaringan terputus sebelum respons IP/Port kembali ke Matchmaker.
- **Dampak:** DGS terjebak dalam status `Allocated` tanpa ada pemain yang tahu alamat IP server tersebut. Resource bocor.
- **Solusi Mitigasi:** Implementasikan **Allocation TTL/Heartbeat**. DGS menjalankan timer independen: jika dalam waktu 30 detik setelah status berubah menjadi `Allocated` tidak ada koneksi game client (UDP handshake), DGS otomatis mengeksekusi self-termination atau kembali ke status `Ready`.

#### 2. Party Cancellation Race Condition
- **Kasus:** Ketua party membatalkan antrean tiket di milidetik yang sama saat matcher worker membentuk pertandingan.
- **Dampak:** Server DGS teralokasi, namun hanya separuh tim yang tersambung.
- **Solusi Mitigasi:** Gunakan skema **Two-Phase Commit (2PC) / Reservation Token** via Redis. Tiket yang dipilih oleh matchmaker diubah statusnya menjadi `RESERVED` secara atomik menggunakan Lua script. Jika pembatalan terjadi pada fase ini, tiket di-*reject* dari matchmaking, dan match dibatalkan sebelum DGS dialokasikan.

#### 3. Fleet Capacity Exhaustion (Thundering Herd)
- **Kasus:** Terjadi lonjakan login pemain akibat event perilisan skin/season baru, melebihi kapasitas `Ready` buffer armada DGS di region target.
- **Dampak:** Panggilan `AllocateServer()` mengembalikan error; latensi sistem melonjak.
- **Solusi Mitigasi:**
  1. *Backpressure Queue:* Penahanan tiket di matchmaker dengan peningkatan estimasi *queue time* secara dinamis kepada client.
  2. *Regional Failover/Spillover:* Jika latensi RTT pemain masih dalam toleransi maksimum ($<100\text{ ms}$), alihkan sesi ke region komputasi sekunder terdekat secara otomatis.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Desain | Arsitektur A: Custom Go + Redis Engine | Arsitektur B: Open Match (Cloud Native Framework) | Arsitektur C: Fully Managed (AWS GameLift) |
| :--- | :--- | :--- | :--- |
| **Kontrol Algoritma** | **Mutlak:** Fleksibilitas total optimasi bitwise & kustomisasi MMR. | **Tinggi:** Berbasis Open-Match Swagger & gRPC Match Functions (MMF). | **Rendah-Sedang:** Dibatasi oleh rule-set FlexMatch JSON. |
| **Kompleksitas Operasional** | **Sedang:** Maintenance Redis Cluster & DGS Agent sendiri. | **Tinggi:** Memerlukan pengelolaan Kubernetes CRD, banyak pods core, dan gRPC link. | **Sangat Rendah:** Operasional fully managed oleh cloud provider. |
| **Allocation Latency** | **Ultra-Rendah:** $\sim 5 - 20\text{ ms}$ (Direct memory cache). | **Sedang:** $\sim 100 - 300\text{ ms}$ (Serialization overhead gRPC stream). | **Tinggi:** $\sim 500 - 2000\text{ ms}$ bergantung polling cycle. |
| **Vendor Lock-in** | **Nol:** Agnostik komputasi (bisa berjalan di Bare-metal, Hybrid, GCP, AWS). | **Nol:** Open-source standar K8s Agones. | **Tinggi:** Sangat terikat pada ekosistem AWS stack. |

---

### 9. Best Practices & Standar Industri

1. **UDP Packet Padding & Port Binding:** Jalankan instance DGS pada mode *HostPort* atau *HostNetwork* di node pool Kubernetes khusus compute (Game Nodes) untuk menghindari packet loss akibat double NAT pada Kubernetes CNI.
2. **Deterministic Dynamic Server Draining:** Ketika merilis update versi binary game, ubah state armada versi lama menjadi `Allocated-Only`. Cegah server versi lama masuk ke status `Ready` kembali setelah pertandingan usai. Izinkan Pod mati secara alami setelah *Match Completed*.
3. **Observabilitas & Metrik Kritikal:**
   - `matchmaking_queue_duration_seconds`: P50, P90, P99 dikelompokkan berdasarkan Region dan MMR Range.
   - `fleet_allocated_ratio`: $\frac{\text{Armada Allocated}}{\text{Total Kapasitas Armada}}$. Jika rasio $> 0.8$, pacu instansiasi node baru via auto-scaler.
   - `dgs_session_health_heartbeat_dropped`: Deteksi dini silent memory leak atau deadlock thread game engine (Unreal Server Crash).

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda diminta menyimulasikan antrean *high-load* matchmaking regional dengan skenario lonjakan pemain dan mengamati ekspansi window toleransi MMR secara langsung hingga alokasi DGS berhasil diproses.

#### Langkah-Langkah Pelaksanaan

1. **Jalankan In-Memory Data Store (Redis):**
   ```bash
   docker run -d --name redis-lab -p 6379:6379 redis:7-alpine
   ```

2. **Inisialisasi Project dan Dependency:**
   ```bash
   mkdir -p game-backend-lab/pkg/{fleet,lobby,matchmaker}
   cd game-backend-lab
   go mod init game-backend
   go get github.com/redis/go-redis/v9 github.com/google/uuid
   ```

3. **Deploy File Implementasi:**
   Salin source code Go dari **Bagian 6** ke direktori masing-masing:
   - `pkg/matchmaker/engine.go`
   - `pkg/lobby/manager.go`
   - `pkg/fleet/allocator.go`
   - `cmd/main.go`

4. **Uji Simulasi Beban (Load Test Ingestion):**
   Buat file pengujian beban `cmd/load_sim/main.go`:
   ```go
   package main

   import (
       "context"
       "fmt"
       "math/rand"
       "time"

       "game-backend/pkg/matchmaker"
       "github.com/google/uuid"
       "github.com/redis/go-redis/v9"
   )

   func main() {
       rdb := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
       engine := matchmaker.NewEngine(rdb, "ap-southeast-1", 1)

       fmt.Println("[TEST] Memompa 100 tiket dengan variasi skill MMR acak...")
       for i := 0; i < 100; i++ {
           _ = engine.EnqueueTicket(context.Background(), matchmaker.Ticket{
               ID:        uuid.New().String(),
               PlayerID:  fmt.Sprintf("player-%d", i),
               MMR:       800 + rand.Intn(1600), // MMR antara 800 - 2400
               Region:    "ap-southeast-1",
               CreatedAt: time.Now().UTC(),
           })
       }
       fmt.Println("[TEST] Selesai. Amati terminal utama server matchmaker untuk alokasi real-time.")
   }
   ```

5. **Eksekusi dan Validasi Output:**
   - Terminal 1 (Core Server):
     ```bash
     go run cmd/main.go
     ```
   - Terminal 2 (Load Injector):
     ```bash
     go run cmd/load_sim/main.go
     ```

6. **Kriteria Verifikasi Evaluasi:**
   - Amati log Terminal 1: Setiap tiket berhasil dipasangkan (`[MATCH FORMED]`) dengan delta MMR terkecil terlebih dahulu.
   - Periksa status ketersediaan armada saat permintaan memuncak: Log harus menampilkan `[DGS ALLOCATED]` hingga server uji habis, lalu mengeluarkan failure alert `ErrFleetExhausted` saat kapasitas armada telah jenuh.
   - Pastikan tidak terjadi *panic* atau *deadlock* saat tiket saling berkompetisi mengambil slot yang sama.