# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 10: High-Scale Clustering, Distributed Gateways, and Distributed Orchestration**  
**Kategori: 08-AI-Data-and-Autonomous-Agents / openclaw**

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** arsitektur internal OpenClaw Gateway dalam menangani kluster agen otonom berskala jutaan *concurrent event loops*.
- **Mengimplementasikan** mekanisme *Consistent Hashing with Bounded Loads* untuk menjamin *session affinity* agen dan distribusi beban kerja stateful tanpa titik kegagalan tunggal (*single point of failure*).
- **Membangun** sistem komunikasi antar-node berbasis gRPC Multiplexed Streams dan protokol *Gossip* (SWIM) untuk *failure detection* secara terdistribusi.
- **Mengonfigurasi** orkestrasi runtime agen di atas cluster terdistribusi menggunakan teknik *worker sandboxing* berbasis eBPF/cgroups v2 dengan *backpressure propagation*.
- **Memecahkan masalah** degradasi latensi (*tail latency p99*), *split-brain scenario*, serta *cascading failures* pada level infrastruktur produksi multi-wilayah.

---

## 2. Prerequisites
Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Sistem Terdistribusi**: Algoritma konsensus (Raft/Paxos), *Gossip Protocol* (SWIM/memberlist), CAP/PACELC Theorem, serta *Vector Clocks / CRDTs*.
- **Pemrograman Sistem & Jaringan**: Pemrograman Go tingkat lanjut (goroutine scheduling, channel semantics, low-level network I/O, gRPC/Protobuf).
- **Infrastruktur & Kernel**: Linux cgroups v2, namespaces, epoll event loops, eBPF dasar, dan platform container (Docker/OCI/Kubernetes).
- **Arsitektur Agen AI**: Siklus hidup *ReAct loop*, *short-term/long-term memory sync*, pemanggilan fungsi terdistribusi (*distributed tool execution*), dan integrasi context stream LLM.

---

## 3. Concept & Internal Architecture (Mendalam)

OpenClaw dirancang sebagai platform gateway dan runtime terdistribusi berkinerja tinggi untuk agen otonom berskala *enterprise*. Saat ribuan agen otonom menjalankan eksekusi paralel—melibatkan inferensi LLM, pembacaan memori persisten, dan *tool calling* (eksekusi API, sandboxed shell, database queries)—gateway tradisional yang bersifat stateless akan kolaps akibat *state synchronization overhead* dan lonjakan latensi jaringan.

Arsitektur kluster OpenClaw Gateway memecahkan masalah ini melalui pemisahan tegas antara tiga bidang arsitektur (*planes*):

```
+-----------------------------------------------------------------------+
|                           CONTROL PLANE                               |
|       (Raft Metadata Store, Topology Coordinator, Auth, Billing)       |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|                          ROUTING GATEWAY                              |
|   (Edge TLS Term, Consistent Hash Ring, gRPC Multiplex, Auth Cache)   |
+-----------------------------------------------------------------------+
         |                                             |
         v                                             v
+---------------------------------+   +---------------------------------+
|        WORKER NODE A            |   |        WORKER NODE B            |
| +-----------------------------+ |   | +-----------------------------+ |
| |   Agent Runtime Supervisor  | |   | |   Agent Runtime Supervisor  | |
| | +---------+ +---------+     | |   | | +---------+ +---------+     | |
| | | Agent 1 | | Agent 2 | ... | |   | | | Agent K | | Agent N | ... | |
| | +---------+ +---------+     | |   | | +---------+ +---------+     | |
| +-----------------------------+ |   | +-----------------------------+ |
| | Ephemeral Sandboxes (cgroups)| |   | | Ephemeral Sandboxes (cgroups)| |
| | Local Cache (Pebble/Badger) | |   | | Local Cache (Pebble/Badger) | |
+---------------------------------+   +---------------------------------+
         ^                                             ^
         +================= SWIM Gossip ===============+
```

### 3.1. Topology & Control Plane Separation
Control plane mengelola topologi kluster, alokasi kuota agen, dan metadata perutean global. Status keanggotaan node didistribusikan menggunakan varian protokol **SWIM (Structured Weakly-Consistent Infection-Style Process Group Membership Protocol)** dengan ekstensi piggybacking. Hal ini memastikan deteksi node mati (*dead node detection*) dalam waktu sub-detik tanpa membebani jaringan dengan pesan *heartbeat broadcast* terpusat.

### 3.2. Data Plane & Consistent Hash Ring with Bounded Load
Untuk mencegah *cache churn* pada konteks memori agen, OpenClaw menggunakan algoritma *Consistent Hashing with Bounded Loads* (Karger & Mirrokni algorithm). 
- Setiap node worker diwakili oleh sejumlah *virtual nodes* (vnodes) pada ring 64-bit/128-bit (menggunakan algoritma hashing Murmur3 atau xxHash).
- Ditetapkan parameter kapasitas beban maksimal $C = 1 + \epsilon$ (di mana $\epsilon$ biasanya $0.15$ hingga $0.25$).
- Jika node target pertama memiliki utilisasi melebihi kapasitas $C \times \text{AverageLoad}$, permintaan secara deterministik dialihkan ke node berikutnya sepanjang cincin searah jarum jam (*next clockwise node*). Mekanisme ini mencegah fenomena *thundering herd* pada satu node ketika agen tertentu menjadi sangat aktif.

### 3.3. Memory Subsystem & Ephemeral Sandbox Execution
Di dalam worker node:
- **Agent Runtime Supervisor**: Bertanggung jawab atas siklus hidup agen, memulihkan status sesi (*checkpoint restoration*) dari cache terdistribusi (Redis/Dragonfly atau S3-compatible snapshot), dan memvalidasi token batas konteks (*context window budget*).
- **Execution Sandbox Isolation**: Eksekusi *tool* otonom (misalnya eksekusi Python, bash, atau kompilasi kode) dijalankan di dalam container mikro *ephemeral* terisolasi yang diatur oleh cgroups v2, PID/Network namespaces, dan filter seccomp terestriksi, mencegah *lateral privilege escalation*.
- **Embedded Fast Tier Storage**: Tiap worker memelihara embedded key-value engine lokal (seperti Pebble/BadgerDB) sebagai buffer transfer status agen sebelum di-*flush* secara asinkron ke storage cluster persisten.

---

## 4. Why & What

### 4.1. Masalah yang Diselesaikan (Why)
1. **Agent State Incoherency**: Agen otonom bukan sekadar panggilan stateless. Agen memiliki memori jangka pendek (*sliding window messages*), status internal variabel, dan koneksi *long-polling/streaming* ke LLM. Routing sembarangan ke node berbeda menyebabkan hilangnya latensi akibat *context re-hydration*.
2. **Cascading Failure akibat Tool Execution**: Eksekusi script yang tidak terbatas pada agen yang bertingkah aneh (*rogue agent*) dapat menghabiskan memori dan CPU host, merobohkan seluruh gateway instance jika worker tidak diisolasi secara ketat.
3. **Imbalance Routing**: Hashing standar berdasarkan ID Agen sering kali menyebabkan ketimpangan beban yang ekstrem (*hotspotting*) ketika beberapa agen memproses batch input multi-modal yang masif.

### 4.2. Definisi Arsitektur OpenClaw (What)
OpenClaw Gateway adalah distributed reverse proxy dan fabric orkestrasi runtime berbasis gRPC/HTTP2 yang:
- Mengarahkan lalu lintas agen berdasarkan hash sesi berbatas beban (*bounded-load session affinity*).
- Melakukan multiplexing ribuan koneksi stream agen ke dalam satu jalur backbone internal TCP/HTTP2.
- Menyediakan *circuit breaking* per agen dan alokasi sumber daya adaptif (*adaptive concurrency limits*).

---

## 5. How (Workflow Detail)

Alur kerja berikut mendetailkan lifecycle pemrosesan sebuah *Autonomous Agent Execution Turn*:

```
Client             OpenClaw Gateway         Worker Node A (Primary)    Tool Sandbox / LLM
  |                       |                           |                       |
  |--- 1. POST /execute ->|                           |                       |
  |    (AgentID: "ag-99") |                           |                       |
  |                       |--- 2. Hash(ag-99) Ring -->|                       |
  |                       |    Target: Worker Node A  |                       |
  |                       |    Load Check <= Cap      |                       |
  |                       |                           |                       |
  |                       |--- 3. gRPC Stream Turn -->|                       |
  |                       |                           |--- 4. Restore Context |
  |                       |                           |    from Local/L2 Store|
  |                       |                           |                       |
  |                       |                           |--- 5. LLM Prompt ---->|
  |                       |                           |<-- 6. Tool Call Req --|
  |                       |                           |                       |
  |                       |                           |--- 7. Spawn Sandbox ->|
  |                       |                           |<-- 8. Exec Result ----|
  |                       |                           |                       |
  |                       |                           |--- 9. Next LLM Turn ->|
  |                       |                           |<-- 10. Final Response |
  |                       |                           |                       |
  |                       |<-- 11. Stream Result -----|--- 12. Async State    |
  |                       |    (gRPC Multiplex)       |    Flush to Pebble/S3 |
  |<-- 13. HTTP/SSE Stream|                           |                       |
```

### Tahapan Eksekusi:
1. **Ingress & Authentication**: Klien mengirimkan payload eksekusi melalui gRPC/HTTP/2. Gateway memverifikasi signature JWT dan kuota rate-limit menggunakan token bucket terdistribusi.
2. **Ring Lookup & Bounded Load Selection**: Gateway menghitung hash ID Agen (`ag-99`). Memeriksa apakah kapasitas Worker Node A berada di bawah threshold $(C \times \text{AvgLoad})$. Jika ya, pilih Worker A; jika terlampaui, lakukan probe ke node berikutnya pada ring.
3. **Multiplexed Transmission**: Gateway meneruskan permintaan via gRPC bi-directional stream yang sudah dibuka sebelumnya (*connection pooling*) ke Worker A.
4. **Context Hydration**: Worker memeriksa apakah memori sesi agen sudah ada di RAM (L1) atau PebbleDB lokal (L2). Jika *cold cache*, ambil dari penyimpanan tersentralisasi (L3/Object Storage).
5. **Execution Loop & Sandboxing**: Jika agen mengeksekusi *tool action*, worker men-dispatch proses ke namespace terisolasi yang dibatasi oleh CPU-quota cgroups v2 (`cpu.max`) dan memori (`memory.high` & `memory.max`).
6. **Streaming & Asynchronous Snapshotting**: Respon dialirkan kembali ke gateway menuju klien via Server-Sent Events (SSE) atau gRPC stream. Sementara itu, mutasi state agen dimasukkan ke antrean *write-ahead log* lokal untuk disinkronkan ke layer persisten.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem: Sistem Menara Kontrol Bandara Internasional
Bayangkan OpenClaw seperti bandara internasional:
- **Routing Gateway** adalah **Radar & Menara ATC (Air Traffic Control)**. Pesawat (permintaan agen) yang masuk tidak diarahkan ke sembarang landasan pacu. ATC melihat jadwal pilot (ID agen) dan memastikan landasan pacu reguler mereka (Node A). Namun, jika landasan A sedang penuh antrean (beban > 115%), ATC langsung mengalihkan pendaratan ke landasan B yang terdekat pada denah bandara (*bounded consistent hashing*).
- **Worker Node** adalah **Terminal & Hangar Pesawat**.
- **Ephemeral Sandbox** adalah **Ruang Karantina Khusus**. Jika penumpang pesawat membawa muatan berbahaya yang perlu diuji (eksekusi kode dari agen), muatan dibawa ke ruang berdinding baja tahan ledakan (*cgroups & seccomp*), terpisah dari terminal umum agar ledakan tidak melumpuhkan seluruh operasional bandara.

### Diagram Arsitektur Komponen Internal

```
================================ OPENCLAW CLUSTER ================================

                       +-----------------------------+
                       |    API Traffic (K8s Ingress)|
                       +-----------------------------+
                                      |
         +----------------------------+----------------------------+
         v                                                         v
+-------------------------------+                         +-------------------------------+
|     GATEWAY INSTANCE 01       |                         |     GATEWAY INSTANCE 02       |
|  +-------------------------+  |                         |  +-------------------------+  |
|  | Consistent Hash Ring    |  |                         |  | Consistent Hash Ring    |  |
|  | (xxHash64 + Bounded L.) |  |                         |  | (xxHash64 + Bounded L.) |  |
|  +-------------------------+  |                         |  +-------------------------+  |
|  | Conn Pool / gRPC Stream |  |                         |  | Conn Pool / gRPC Stream |  |
|  +-------------------------+  |                         |  +-------------------------+  |
+-------------------------------+                         +-------------------------------+
         |             \                                           /             |
         |              \_________________       _________________/              |
         |                                \     /                                |
         v                                 v   v                                 v
+-----------------------------------+             +-----------------------------------+
|          WORKER NODE 01           |             |          WORKER NODE 02           |
|                                   |             |                                   |
|  +-----------------------------+  |    SWIM     |  +-----------------------------+  |
|  |  Agent Supervisor (Pool)    |  |<===========>|  |  Agent Supervisor (Pool)    |  |
|  |  - Active Context: 1,420    |  |   Gossip    |  |  - Active Context: 1,380    |  |
|  +-----------------------------+  |   Channel   |  +-----------------------------+  |
|                 |                 |             |                 |                 |
|       +---------+---------+       |             |       +---------+---------+       |
|       v                   v       |             |       v                   v       |
|  +---------+         +---------+  |             |  +---------+         +---------+  |
|  | Sandbox |         | Sandbox |  |             |  | Sandbox |         | Sandbox |  |
|  | (cgroup)|         | (cgroup)|  |             |  | (cgroup)|         | (cgroup)|  |
|  +---------+         +---------+  |             |  +---------+         +---------+  |
|  +-----------------------------+  |             |  +-----------------------------+  |
|  | Embedded Store (PebbleDB)   |  |             |  | Embedded Store (PebbleDB)   |  |
|  +-----------------------------+  |             |  +-----------------------------+  |
+-----------------------------------+             +-----------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Consistent Hash Ring dengan Virtual Nodes
File: `ring/simple_ring.go`
Contoh sederhana implementasi dasar Ring Hashing menggunakan xxHash tanpa bounded-load library eksternal.

```go
package ring

import (
	"fmt"
	"sort"
	"strconv"
	"sync"

	"github.com/cespare/xxhash/v2"
)

type SimpleHashRing struct {
	sync.RWMutex
	vnodes   int
	ring     []uint64
	nodeMap  map[uint64]string
	nodes    map[string]bool
}

func NewSimpleHashRing(vnodes int) *SimpleHashRing {
	return &SimpleHashRing{
		vnodes:  vnodes,
		nodeMap: make(map[uint64]string),
		nodes:   make(map[string]bool),
	}
}

func (r *SimpleHashRing) AddNode(node string) {
	r.Lock()
	defer r.Unlock()

	if r.nodes[node] {
		return
	}
	r.nodes[node] = true

	for i := 0; i < r.vnodes; i++ {
		vnodeKey := node + "#" + strconv.Itoa(i)
		hash := xxhash.Sum64String(vnodeKey)
		r.ring = append(r.ring, hash)
		r.nodeMap[hash] = node
	}
	sort.Slice(r.ring, func(i, j int) bool { return r.ring[i] < r.ring[j] })
}

func (r *SimpleHashRing) GetNode(key string) (string, error) {
	r.RLock()
	defer r.RUnlock()

	if len(r.ring) == 0 {
		return "", fmt.Errorf("ring is empty")
	}

	hash := xxhash.Sum64String(key)
	idx := sort.Search(len(r.ring), func(i int) bool {
		return r.ring[i] >= hash
	})

	if idx == len(r.ring) {
		idx = 0
	}

	return r.nodeMap[r.ring[idx]], nil
}
```

---

### 7.2. Practical Example: Production-Grade Bounded-Load Router & Dispatcher
Komponen router terdistribusi nyata yang mendukung *Consistent Hashing with Bounded Loads*, pelacakan kapasitas live, dan gRPC client stream pooling.

File: `router/bounded_load_router.go`

```go
package router

import (
	"context"
	"errors"
	"fmt"
	"math"
	"sort"
	"strconv"
	"sync"
	"sync/atomic"

	"github.com/cespare/xxhash/v2"
	"google.golang.org/grpc"
	"google.golang.org/grpc/connectivity"
	"google.golang.org/grpc/credentials/insecure"
)

var (
	ErrNoNodesAvailable = errors.New("tidak ada node yang tersedia dalam cluster ring")
	ErrCapacityOverload = errors.New("seluruh worker node melampaui ambang batas bounded-load")
)

type WorkerNode struct {
	ID          string
	Address     string
	ActiveLoads int64
	ClientConn  *grpc.ClientConn
}

type ConsistentHashBoundedLoadRouter struct {
	mu           sync.RWMutex
	vnodesFactor int
	epsilon      float64 // Faktor toleransi overload, misal 0.25 (beban max = 1.25 * rata-rata)
	ring         []uint64
	vnodeToNode  map[uint64]*WorkerNode
	nodes        map[string]*WorkerNode
	totalLoads   int64
}

func NewBoundedLoadRouter(vnodesFactor int, epsilon float64) *ConsistentHashBoundedLoadRouter {
	return &ConsistentHashBoundedLoadRouter{
		vnodesFactor: vnodesFactor,
		epsilon:      epsilon,
		vnodeToNode:  make(map[uint64]*WorkerNode),
		nodes:        make(map[string]*WorkerNode),
	}
}

func (r *ConsistentHashBoundedLoadRouter) RegisterWorker(id, address string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.nodes[id]; exists {
		return fmt.Errorf("node %s sudah terdaftar", id)
	}

	// Dial gRPC connection
	conn, err := grpc.Dial(address, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return fmt.Errorf("gagal dial ke worker node %s: %w", address, err)
	}

	worker := &WorkerNode{
		ID:         id,
		Address:    address,
		ClientConn: conn,
	}

	r.nodes[id] = worker

	for i := 0; i < r.vnodesFactor; i++ {
		vnodeKey := fmt.Sprintf("%s#vn-%d", id, i)
		hashVal := xxhash.Sum64String(vnodeKey)
		r.ring = append(r.ring, hashVal)
		r.vnodeToNode[hashVal] = worker
	}

	sort.Slice(r.ring, func(i, j int) bool {
		return r.ring[i] < r.ring[j]
	})

	return nil
}

func (r *ConsistentHashBoundedLoadRouter) UnregisterWorker(id string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	worker, exists := r.nodes[id]
	if !exists {
		return fmt.Errorf("node %s tidak ditemukan", id)
	}

	if worker.ClientConn != nil {
		_ = worker.ClientConn.Close()
	}

	// Rebuild ring
	newRing := make([]uint64, 0, len(r.ring)-(r.vnodesFactor))
	for _, h := range r.ring {
		if r.vnodeToNode[h].ID == id {
			delete(r.vnodeToNode, h)
		} else {
			newRing = append(newRing, h)
		}
	}
	r.ring = newRing
	delete(r.nodes, id)
	atomic.AddInt64(&r.totalLoads, -worker.ActiveLoads)

	return nil
}

// RouteAgentTurn mengembalikan WorkerNode optimal berdasarkan hash bounded load
func (r *ConsistentHashBoundedLoadRouter) RouteAgentTurn(ctx context.Context, agentID string) (*WorkerNode, func(), error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	numNodes := len(r.nodes)
	if numNodes == 0 {
		return nil, nil, ErrNoNodesAvailable
	}

	currentTotal := atomic.LoadInt64(&r.totalLoads)
	avgLoad := float64(currentTotal+1) / float64(numNodes)
	maxAllowedLoad := int64(math.Ceil(avgLoad * (1.0 + r.epsilon)))

	keyHash := xxhash.Sum64String(agentID)
	startIdx := sort.Search(len(r.ring), func(i int) bool {
		return r.ring[i] >= keyHash
	})

	ringLen := len(r.ring)
	for i := 0; i < ringLen; i++ {
		currIdx := (startIdx + i) % ringLen
		node := r.vnodeToNode[r.ring[currIdx]]

		// Evaluasi konektivitas gRPC
		if node.ClientConn.GetState() == connectivity.TransientFailure ||
			node.ClientConn.GetState() == connectivity.Shutdown {
			continue
		}

		// Evaluasi Bounded Load
		currentWorkerLoad := atomic.LoadInt64(&node.ActiveLoads)
		if currentWorkerLoad < maxAllowedLoad {
			atomic.AddInt64(&node.ActiveLoads, 1)
			atomic.AddInt64(&r.totalLoads, 1)

			releaseFunc := func() {
				atomic.AddInt64(&node.ActiveLoads, -1)
				atomic.AddInt64(&r.totalLoads, -1)
			}
			return node, releaseFunc, nil
		}
	}

	return nil, nil, ErrCapacityOverload
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Kasus Enterprise Autonomous Financial Audit Agent
- **Klien**: Lembaga Kliring Transaksi Keuangan Global.
- **Skala**: 150.000 Agen Otonom paralel memvalidasi anomali transaksi per jam.
- **Total Workload**: Rata-rata 45.000 RPS *Turn-Events*, $15.000$ tool executions per detik (DB SQL + Python Sandbox).
- **Infrastruktur**:
  - 12 Node OpenClaw Gateway (c6i.8xlarge, 32 vCPU, 64GB RAM).
  - 80 Node OpenClaw Worker (c6i.16xlarge, 64 vCPU, 128GB RAM).
  - Jaringan: AWS VPC Cluster Placement Group dengan latency < 1ms intra-cluster.

```
Incoming Stream (45k Turn/sec)
            |
            v
[ 12x OpenClaw Gateways ] 
     | Consistent Hash Ring (Bounded Load eps=0.20)
     | Connection-pooled Multiplexed gRPC
     v
[ 80x OpenClaw Worker Nodes ]
     |-> Agent Session Cache (PebbleDB NVMe Tier)
     |-> Tool Isolation (cgroups v2 + custom seccomp runner)
```

### Masalah Awal (Degradasi Produksi):
Saat peluncuran awal tanpa bounded load:
1. Terjadi insiden di mana 300 agen *high-frequency* secara acak di-hash ke worker node yang sama (Node-27). Node-27 mengalami *CPU starvation*, menyebabkan tail-latency p99 meroket hingga 14.800 ms.
2. Mekanisme health check standar Kubernetes (HTTP readiness probe) menganggap Node-27 mati dan melakukan restart pod. Hal ini memicu *thundering herd* ke Node-28, menciptakan *cascading crash* yang menjatuhkan 8 node berturut-turut.

### Solusi Arsitektural:
1. **Implementasi Bounded Loads ($\epsilon = 0.20$)**: Kapasitas maksimal tiap worker dikunci pada $1.20 \times \text{AvgLoad}$. Permintaan yang melebihi kuota secara transparan diteruskan ke vnode penerus (*successor node*) terdekat tanpa membuat node overload.
2. **Backpressure Propagation**: Saat antrean eksekusi sandbox pada worker node melampaui kedalaman buffer 256, worker merespons dengan status error gRPC `RESOURCE_EXHAUSTED` disertai header `retry-after-ms`. Gateway secara proaktif mengaktifkan circuit breaker lokal per agen ID.
3. **Hasil Metrik Setelah Penerapan**:
   - **p99 Execution Latency**: Turun dari 14.800 ms menjadi **310 ms**.
   - **Resource Skewness**: Variansi pemanfaatan CPU antar-node berkurang dari $\sigma = 42\%$ menjadi $\sigma = 4.8\%$.
   - **Cascading Crash**: Tereliminasi sepenuhnya (0 insiden dalam 90 hari operasional).

---

## 9. Trade-offs

| Aspek Arsitektur | Pilihan Desain | Trade-off / Keuntungan | Konsekuensi / Biaya |
| :--- | :--- | :--- | :--- |
| **State Affinity** | Consistent Hashing with Bounded Loads | Mencegah *hotspotting*; memaksimalkan L1/L2 cache hit rate pada worker. | Node traversal overhead pada ring saat hampir seluruh kluster berada di kapasitas puncak ($\mathcal{O}(N)$ worst-case). |
| **Cluster Membership** | SWIM-based Gossip Protocol | Deteksi kegagalan peer-to-peer tanpa ketergantungan single-point; lalu lintas metadata rendah. | *Weak consistency*: Adanya jeda konvergensi topologi ring selama beberapa ratus milidetik ketika terjadi churn masif. |
| **Tool Execution** | Micro-Sandbox (cgroups v2 + Seccomp) | Proteksi memori tingkat host; membatasi *noisy neighbor* agen berbahaya. | Overhead startup sebesar 15–30 ms per eksekusi container mikro jika dibandingkan *in-process execution*. |
| **State Snapshotting**| Local Write-Ahead Log + Async S3 Flush | Eksekusi turn agen memiliki throughput sangat tinggi; latency commit rendah. | Risiko kehilangan mutasi turn terakhir (*window < 200ms*) jika worker node mengalami *kernel panic* mendadak. |

---

## 10. Common Mistakes & Troubleshooting

### Tabel Kesalahan Umum dan Remediasi

| Gejala Masalah | Akar Masalah (*Root Cause*) | Mitigasi / Perbaikan Teknis |
| :--- | :--- | :--- |
| **P99 Latency Spikes sporadis** | Virtual node factor terlalu kecil ($< 50$), menghasilkan sebaran ring yang tidak merata. | Naikkan faktor vnodes ke kisaran $150 - 256$. Monitor deviasi standar beban menggunakan metrik ring balance. |
| **Worker OOM-Killed oleh Kernel** | Eksekusi tool Python pada agen mengabaikan alokasi *memory cgroups* terisolasi. | Buat cgroup terpisah via slice systemd, pasang `memory.high` untuk throttling dan `memory.max` untuk hard kill isolated tool. |
| **Goroutine Leak di Gateway** | Koneksi gRPC stream ke worker tidak ditutup secara aman saat klien memutuskan koneksi HTTP. | Tangani pembatalan `context.Done()` pada seluruh relay worker streams, pastikan deferred cleanup fungsi rilis pembebanan terpanggil. |
| **State Invalidation Churn** | Kluster mengalami *flapping node* akibat parameter timeout SWIM gossip terlalu agresif. | Tingkatkan interval ping gossip dari 200ms ke 500ms; aktifkan fase probe `indirect-ping` sebelum menandai node sebagai dead. |

### Panduan Troubleshooting Terstruktur
1. **Diagnosis Degradasi Node**: Jalankan profiling interkoneksi cluster:
   ```bash
   # Cek konektivitas latensi antar gateway dan worker
   grpc_cli call <WORKER_IP>:50051 openclaw.v1.HealthCheck/Check "{}"
   
   # Cek saturasi cgroups v2 memory pressure
   cat /sys/fs/cgroup/openclaw-workers/memory.pressure
   ```
2. **Inspeksi Unbalanced Ring Load**:
   Gunakan endpoint metrik internal Prometheus:
   ```promql
   sum by (worker_node) (openclaw_gateway_active_agent_streams)
   ```
   Jika deviasi relatif antar-node $> 30\%$, verifikasi apakah nilai `epsilon` pada bounded-load router telah di-*override* secara salah.

---

## 11. Best Practices (Production Checklist)

### Security
- [ ] Aktifkan mTLS menggunakan sertifikat SPIFFE/SPIRE untuk seluruh komunikasi antar-gateway dan worker node.
- [ ] Batasi eksekusi sandbox agen dengan flag seccomp tanpa `SYS_PTRACE`, `SYS_ADMIN`, dan blokir akses ke socket Docker `/var/run/docker.sock`.
- [ ] Enkripsi snapshot status agen saat *at-rest* (AES-256-GCM) sebelum di-*dump* ke PebbleDB atau remote object storage.

### Observability
- [ ] Distribusikan trace menggunakan OpenTelemetry context propagation melintasi Gateway $\rightarrow$ Worker $\rightarrow$ LLM $\rightarrow$ Tool Sandbox.
- [ ] Pasang metrik ring load: `openclaw_bounded_load_violations_total`, `openclaw_ring_lookup_duration_seconds`.
- [ ] Setup alert jika p99 stream duration melampaui $2 \times$ SLA normal.

### Resilience & Capacity
- [ ] Setel buffer bounded load $\epsilon$ antara $0.15 \le \epsilon \le 0.25$.
- [ ] Pasang batas hard resource per sandbox agent: max CPU core 1.0, max RAM 512MB, execution timeout 30 detik.
- [ ] Sediakan *standby worker nodes* (minimal $N+2$ redundancy) per zona ketersediaan (*availability zone*).

---

## 12. Hands-on Practice: Membangun Resilient Gateway Cluster

Struktur folder praktikum yang akan kita bangun di `hands-on/m02/`:
```
hands-on/m02/
├── cmd/
│   ├── gateway/
│   │   └── main.go
│   └── worker/
│       └── main.go
├── proto/
│   └── agent_service.proto
├── pkg/
│   ├── cluster/
│   │   └── ring.go
│   └── sandbox/
│       └── runner.go
├── go.mod
└── docker-compose.yml
```

### Langkah 1: Siapkan Protobuf Definition
File: `hands-on/m02/proto/agent_service.proto`

```protobuf
syntax = "proto3";

package openclaw.v1;
option go_package = "openclaw/proto";

service AgentExecutionService {
  rpc ExecuteTurnStream(stream AgentExecutionRequest) returns (stream AgentExecutionResponse);
  rpc GetNodeStatus(NodeStatusRequest) returns (NodeStatusResponse);
}

message AgentExecutionRequest {
  string agent_id = 1;
  string session_id = 2;
  string input_payload = 3;
}

message AgentExecutionResponse {
  string agent_id = 1;
  string output_chunk = 2;
  bool is_completed = 3;
  string executed_by_worker = 4;
}

message NodeStatusRequest {}

message NodeStatusResponse {
  string node_id = 1;
  int64 active_sessions = 2;
  double cpu_usage_percent = 3;
}
```

### Langkah 2: Implementasi Worker Runtime Engine
File: `hands-on/m02/cmd/worker/main.go`

```go
package main

import (
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"

	"google.golang.org/grpc"
	"openclaw/proto"
)

type WorkerServer struct {
	proto.UnimplementedAgentExecutionServiceServer
	nodeID        string
	activeStreams int64
}

func (s *WorkerServer) ExecuteTurnStream(stream proto.AgentExecutionService_ExecuteTurnStreamServer) error {
	atomic.AddInt64(&s.activeStreams, 1)
	defer atomic.AddInt64(&s.activeStreams, -1)

	for {
		req, err := stream.Recv()
		if err == io.EOF {
			return nil
		}
		if err != nil {
			return err
		}

		// Simulasi Agen ReAct: 3 chunk respons bertahap
		for i := 1; i <= 3; i++ {
			chunk := fmt.Sprintf("[Node: %s] Turn chunk %d untuk Agen: %s", s.nodeID, i, req.AgentId)
			res := &proto.AgentExecutionResponse{
				AgentId:            req.AgentId,
				OutputChunk:        chunk,
				IsCompleted:        (i == 3),
				ExecutedByWorker:   s.nodeID,
			}
			if err := stream.Send(res); err != nil {
				return err
			}
			time.Sleep(100 * time.Millisecond) // Latensi eksekusi simulatif
		}
	}
}

func (s *WorkerServer) GetNodeStatus(req *proto.NodeStatusRequest, stream proto.AgentExecutionService_GetNodeStatusServer) (*proto.NodeStatusResponse, error) {
	return &proto.NodeStatusResponse{
		NodeId:         s.nodeID,
		ActiveSessions: atomic.LoadInt64(&s.activeStreams),
	}, nil
}

func main() {
	nodeID := os.Getenv("WORKER_NODE_ID")
	port := os.Getenv("WORKER_PORT")
	if nodeID == "" {
		nodeID = "worker-default-1"
	}
	if port == "" {
		port = "50051"
	}

	lis, err := net.Listen("tcp", ":"+port)
	if err != nil {
		log.Fatalf("Gagal membuka listener port %s: %v", port, err)
	}

	grpcServer := grpc.NewServer()
	srv := &WorkerServer{nodeID: nodeID}
	proto.RegisterAgentExecutionServiceServer(grpcServer, srv)

	log.Printf("Worker %s online pada port :%s", nodeID, port)

	go func() {
		if err := grpcServer.Serve(lis); err != nil {
			log.Fatalf("Server terminated: %v", err)
		}
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	log.Println("Shutting down worker node gracefully...")
	grpcServer.GracefulStop()
}
```

### Langkah 3: Implementasi Gateway Ingress Proxy
File: `hands-on/m02/cmd/gateway/main.go`

```go
package main

import (
	"context"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"openclaw/pkg/cluster"
	"openclaw/proto"
)

func main() {
	gatewayPort := os.Getenv("GATEWAY_PORT")
	if gatewayPort == "" {
		gatewayPort = "8080"
	}

	// Inisialisasi Ring dengan 100 vnodes dan epsilon 0.25 (Bounded Load)
	ringRouter := cluster.NewBoundedLoadRouter(100, 0.25)

	// Registrasi mock cluster nodes
	workers := map[string]string{
		"worker-01": "127.0.0.1:50051",
		"worker-02": "127.0.0.1:50052",
		"worker-03": "127.0.0.1:50053",
	}

	for id, addr := range workers {
		if err := ringRouter.RegisterWorker(id, addr); err != nil {
			log.Printf("Peringatan: Gagal registrasi %s: %v", id, err)
		} else {
			log.Printf("Terdaftar %s pada router cluster ring", id)
		}
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/v1/agent/stream", func(w http.ResponseWriter, r *http.Request) {
		agentID := r.URL.Query().Get("agent_id")
		if strings.TrimSpace(agentID) == "" {
			http.Error(w, "Parameter 'agent_id' wajib diisi", http.StatusBadRequest)
			return
		}

		targetWorker, releaseFunc, err := ringRouter.RouteAgentTurn(r.Context(), agentID)
		if err != nil {
			http.Error(w, fmt.Sprintf("Routing error: %v", err), http.StatusServiceUnavailable)
			return
		}
		defer releaseFunc()

		client := proto.NewAgentExecutionServiceClient(targetWorker.ClientConn)
		stream, err := client.ExecuteTurnStream(r.Context())
		if err != nil {
			http.Error(w, fmt.Sprintf("Stream init failed: %v", err), http.StatusBadGateway)
			return
		}

		// Set header SSE (Server-Sent Events)
		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Connection", "keep-alive")
		flusher, ok := w.(http.Flusher)
		if !ok {
			http.Error(w, "Streaming unsupported", http.StatusInternalServerError)
			return
		}

		// Kirim turn request ke worker
		turnReq := &proto.AgentExecutionRequest{
			AgentId:      agentID,
			SessionId:    fmt.Sprintf("sess-%d", time.Now().UnixNano()),
			InputPayload: "Analyze telemetry logs",
		}
		if err := stream.Send(turnReq); err != nil {
			http.Error(w, "Stream send failure", http.StatusInternalServerError)
			return
		}
		_ = stream.CloseSend()

		// Stream response kembali ke browser / HTTP client
		for {
			resp, err := stream.Recv()
			if err == io.EOF {
				break
			}
			if err != nil {
				log.Printf("Stream recv error: %v", err)
				break
			}

			fmt.Fprintf(w, "data: {\"chunk\": \"%s\", \"worker\": \"%s\"}\n\n", resp.OutputChunk, resp.ExecutedByWorker)
			flusher.Flush()
		}
	})

	srv := &http.Server{
		Addr:    ":" + gatewayPort,
		Handler: mux,
	}

	go func() {
		log.Printf("Gateway online pada http://0.0.0.0:%s", gatewayPort)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Gateway failure: %v", err)
		}
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	log.Println("Stopping gateway safely...")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = srv.Shutdown(ctx)
}
```

### Langkah 4: Menjalankan dan Menguji Kluster
1. Buka 3 terminal terpisah untuk menjalankan 3 worker instances:
   ```bash
   # Terminal 1
   WORKER_NODE_ID=worker-01 WORKER_PORT=50051 go run cmd/worker/main.go
   
   # Terminal 2
   WORKER_NODE_ID=worker-02 WORKER_PORT=50052 go run cmd/worker/main.go
   
   # Terminal 3
   WORKER_NODE_ID=worker-03 WORKER_PORT=50053 go run cmd/worker/main.go
   ```
2. Jalankan Gateway:
   ```bash
   # Terminal 4
   GATEWAY_PORT=8080 go run cmd/gateway/main.go
   ```
3. Lakukan pengujian streaming via curl:
   ```bash
   curl -N "http://localhost:8080/v1/agent/stream?agent_id=financial-agent-007"
   ```

---

## 13. Exercises

### Level Easy
Modifikasi implementasi `SimpleHashRing` pada seksi 7.1 agar menambahkan metode `RemoveNode(node string)`.
- **Kriteria Keberhasilan**: Saat sebuah node dihapus, seluruh vnodes miliknya terhapus dari slice ring, slice tetap terurut, dan fungsi pencarian `GetNode` tidak lagi mereturn node yang dihapus tersebut.

### Level Medium
Tambahkan mekanisme *Passive Health Checking* pada `ConsistentHashBoundedLoadRouter`.
- **Kriteria Keberhasilan**: Jika sebuah worker node mereturn kode error `gRPC Unavailable` sebanyak 3 kali berturut-turut dalam kurun waktu 5 detik, tandai status node sebagai `UNHEALTHY` dan lewati vnode miliknya dalam ring resolution selama 30 detik (*cooldown period*).

### Level Hard
Implementasikan protokol penyebaran beban (*load gossip piggybacking*).
- **Kriteria Keberhasilan**: Setiap kali Gateway menerima respons dari Worker via stream, ekstrak header metadata gRPC `x-worker-active-load` yang diisi oleh worker. Perbarui metrik beban `ActiveLoads` pada gateway secara dinamis berdasarkan data dari worker tersebut alih-alih hanya mengandalkan perhitungan lokal atomic counter.

---

## 14. Challenge: Split-Brain & Thundering Herd Resilience
Rancang dan implementasikan strategi arsitektur untuk mengatasi skenario ekstrim berikut:
- **Kondisi Kasus**: Jaringan antar-datacenter mengalami partisi (*network partition* split-brain). Gateway di Region East (US-East) kehilangan kontak dengan 40% Worker Nodes di Region West (US-West).
- **Tantangan Teknis**:
  1. Bagaimana gateway mencegah *cascading overload* pada sisa 60% worker lokal ketika traffic agen dialihkan mendadak?
  2. Bagaimana mencegah dua instance agen yang sama dijalankan secara bersamaan (*dual-primary state conflict*) pada kedua sisi partisi jaringan jika klien terus mengirimkan permintaan ke gateway di masing-masing wilayah?
- **Deliverables**: Buat dokumen spesifikasi desain arsitektur (disertai pseudocode / Go logic) yang mengintegrasikan Distributed Fencing Token dan Circuit Breaker berbasis Exponential Backoff with Jitter.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic
1. Mengapa algoritma hashing standar seperti modulo `hash(agentID) % N` tidak layak digunakan untuk gateway arsitektur agen terdistribusi?
2. Apa fungsi parameter *vnodes* (virtual nodes) dalam implementasi Consistent Hashing?
3. Sebutkan peran protokol SWIM dibandingkan protokol Heartbeat Master-Worker tersentralisasi!
4. Apa yang dimaksud dengan *bounded load* pada algoritma konsisten hashing?
5. Mengapa sandboxing eksekusi tool agen harus menggunakan isolasi level cgroups/seccomp daripada mengeksekusinya langsung di thread yang sama dengan gateway?

### 15.2. Pertanyaan Intermediate
6. Jelaskan bagaimana *cascading failure* dapat terjadi pada kluster worker agen ketika sebuah worker crash akibat beban berlebih!
7. Bagaimana penanganan *streaming multiplexing* via gRPC membantu mengurangi penggunaan port dan koneksi TCP pada sistem gateway berkapasitas tinggi?
8. Kapan fallback routing terjadi pada algoritma Consistent Hashing with Bounded Loads?
9. Bagaimana mitigasi OpenClaw terhadap serangan eksfiltrasi data host jika agen mengeksekusi shell command berbahaya?
10. Mengapa sinkronisasi status agen ke storage tersentralisasi (misal S3) dianjurkan dilakukan secara asinkron pasca-turn?

### 15.3. Skenario Kasus Produksi
11. **Kasus A**: Kluster Anda memiliki 10 node worker. Pemanfaatan rata-rata adalah 100 koneksi per node. Dengan konfigurasi $\epsilon = 0.20$, berapa beban maksimal yang diizinkan pada satu worker sebelum router mengalihkan trafik ke node berikutnya pada ring?
12. **Kasus B**: Gateway Anda menerima lonjakan lalu lintas yang tidak terduga, dan seluruh worker node di ring telah mencapai kapasitas bounded load tertingginya. Tindakan apa yang harus diambil oleh gateway router untuk melindungi kluster dari kegagalan total?
13. **Kasus C**: Setelah penambahan 5 worker node baru ke dalam kluster yang sedang berjalan, terjadi penurunan performa drastis selama 2 menit pertama sebelum performa kembali stabil. Analisis apa yang menjadi penyebab fenomena ini dan bagaimana solusinya!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Jawaban Basic:
1. Karena jika jumlah node $N$ berubah (akibat penambahan/kegagalan node), hampir $100\%$ pemetaan kunci akan bergeser, memaksa re-hidrasi konteks memori pada seluruh agen secara serentak yang memicu *thundering herd* dan *cache invalidation crisis*.
2. Vnodes menyebarkan hash footprint dari satu node fisik ke berbagai titik acak di seluruh cincin, menghasilkan distribusi beban yang seragam (*uniform distribution*) dan mencegah pembentukan segment hash yang timpang.
3. SWIM mendistribusikan beban deteksi kesehatan secara peer-to-peer dan desentralistik, sehingga overhead jaringan konstan $\mathcal{O}(1)$ per node tanpa ada single point of bottleneck pada master node.
4. Mekanisme pembatasan kuota beban maksimum yang boleh diterima oleh node mana pun, dihitung sebagai persentase tertentu di atas rata-rata beban kluster saat ini ($(1 + \epsilon) \times \text{AvgLoad}$).
5. Untuk mencegah starvation CPU/RAM host akibat loop kode tak terhingga (*rogue scripts*), melindungi memori proses utama dari crash/segfault, serta memblokir modifikasi sistem file host melalui pembatasan akses kernel syscall.

#### Jawaban Intermediate:
6. Ketika satu node overload dan crash, bebannya dipindahkan ke node tetangga. Jika node tetangga sudah beroperasi mendekati kapasitas batasnya, beban limpahan akan membuatnya ikut overload dan crash, memicu reaksi berantai yang meruntuhkan seluruh kluster node secara berurutan.
7. Multiplexing gRPC memungkinkan pengiriman ribuan request/response stream logis secara independen melalui satu koneksi TCP fisik tunggal, menghilangkan overhead TCP 3-way handshake berulang, konsumsi socket file-descriptor, dan alokasi memori buffer kernel yang masif.
8. Fallback terjadi saat vnode utama yang ditunjuk oleh hash ID agen sedang dalam status koneksi mati (*dead/unhealthy*) atau telah melampaui ambang batas beban `maxAllowedLoad`.
9. Menggunakan isolasi cgroups v2 untuk CPU/memori, isolasi *mount namespace* (filesystem sandbox kosong/ephemeral), serta memfilter syscall berbahaya (seperti `sys_chroot`, `sys_ptrace`, raw socket network) menggunakan profil Seccomp terestriksi.
10. Agar proses eksekusi agen tidak terhambat (*blocking*) oleh latensi I/O remote storage, menjaga latency respons real-time (p99) ke pengguna tetap rendah sementara persistensi dijamin oleh write-ahead log lokal sementara.

#### Solusi Kasus Produksi:
11. Rata-rata beban = 100 koneksi. Kapasitas maksimum per node $= \lceil 100 \times (1 + 0.20) \rceil = \mathbf{120}$ koneksi. Permintaan ke-121 pada node tersebut akan dialihkan secara deterministik ke node berikutnya pada ring.
12. Gateway harus mengaktifkan mekanisme **Global Backpressure & Shedding**: kembalikan error eksplisit `HTTP 503 Service Unavailable` atau status gRPC `RESOURCE_EXHAUSTED` dengan header `Retry-After`. Jangan biarkan request antre tanpa batas di memori gateway karena dapat memicu Out-of-Memory crash pada gateway tier itu sendiri.
13. Fenomena ini disebabkan oleh **Cold Cache Penalty**. Node baru belum memiliki status konteks agen lokal di memori L1/L2 mereka, sehingga seluruh request yang masuk ke node baru harus melakukan fetch penuh dari remote storage (L3). Solusinya adalah menerapkan *Warm-up Routine*: router gateway mengalihkan trafik ke node baru secara bertahap menggunakan bobot adaptif (*gradual traffic shifting / ramp-up phase*).

---

## 16. Summary

- **OpenClaw Distributed Gateway Architecture** memadukan keandalan *Stateful Session Affinity* dengan fleksibilitas skalabilitas *Stateless Ingress*.
- Penerapan **Consistent Hashing with Bounded Loads** adalah kunci dalam menyeimbangkan dua tujuan yang bertentangan: mempertahankan lokasi sesi agen pada node yang sama untuk memaksimalkan *cache hit*, sembari secara matematis mencegah *hotspotting* dan fenomena *cascading collapse*.
- Isolasi ketat pada level runtime worker (menggunakan *cgroups v2, ephemeral namespaces,* dan pembatasan seccomp) merupakan prasyarat mutlak untuk eksekusi kode otonom pada skala enterprise.
- Ketahanan kluster ditentukan oleh pemantauan *failure detection* yang cepat via varian protokol Gossip (SWIM), mitigasi *backpressure* proaktif, serta arsitektur persistensi hibrida (L2 Local Engine $\rightarrow$ L3 Remote Tier).