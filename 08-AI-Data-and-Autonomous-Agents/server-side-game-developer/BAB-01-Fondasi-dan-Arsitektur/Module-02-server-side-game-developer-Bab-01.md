# BAB 01: Fondasi & Arsitektur Server-Side Game Development
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang Arsitektur Server Game Otoritatif Berkinerja Tinggi**: Mengimplementasikan *tick-based simulation loop* deterministik dengan variasi *fixed timestep* dan mitigasi *spiral of death*.
- **Menguasai Protokol Transpor & Jaringan Tingkat Rendah**: Menganalisis dan mengimplementasikan transport berbasis UDP/Reliable-UDP (KCP/ENet/QUIC) serta *zero-allocation packet serialization*.
- **Membangun Sistem Sinkronisasi Status (State Synchronization)**: Mengembangkan mekanisme *Snapshot Interpolation*, *Client-Side Prediction*, *Server Reconciliation*, dan *Delta Compression*.
- **Mengimplementasikan Spatial Partitioning & Area of Interest (AoI)**: Mengurangi kompleksitas komputasi dan broadcast jaringan dari $O(N^2)$ menjadi $O(N \log N)$ atau $O(N + M)$ menggunakan *Spatial Hashing* / *Dynamic Quadtree*.
- **Mengeliminasi Latensi Garbage Collection**: Menerapkan pola alokasi memori nol (*zero-allocation patterns*), *object pooling*, dan representasi *Data-Oriented Design* (DOD) untuk membatasi *frame jitter* di bawah 1ms pada beban produksi.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta harus memiliki pemahaman mendalam tentang:
- **Sistem Operasi & Jaringan**: Socket programming (POSIX BSD sockets), TCP/IP stack internals, UDP, kernel-space vs user-space context switching, epoll/kqueue.
- **Konkurensi & Memori Tingkat Rendah**: Race conditions, atomic primitives, memory alignment, cache lines (L1/L2/L3 miss impact), serta thread synchronization primitives.
- **Bahasa Pemrograman Sistem**: Pemahaman menengah hingga mahir dalam Go, C++, atau Rust (modul ini menggunakan Go dengan idiom rekayasa sistem rendah latensi).

---

### 3. Concept & Internal Architecture

Dalam arsitektur *authoritative game server*, server bukan sekadar API gateway stateless; server adalah simulator fisika dan aturan permainan (*game rules*) yang berjalan pada kecepatan siklus konstan (*tick rate*). 

#### 3.1 Siklus Simulasi (The Authoritative Tick Loop)
Server berjalan pada frekuensi diskret, misalnya 30Hz atau 60Hz. Pada 60Hz, server memiliki *frame budget* sebesar tepat **16.66 milidetik** per tick untuk mengeksekusi seluruh siklus hidup komputasi:

$$\Delta t_{\text{budget}} = \frac{1000\text{ ms}}{\text{Tick Rate}} = 16.666\text{ ms (pada 60 Hz)}$$

Jika komputasi tick melebihi alokasi waktu tersebut, server mengalami *tick drop*, yang berujung pada desinkronisasi global dan deselerasi gerak bagi seluruh pemain di shard tersebut.

```
       +-------------------------------------------------------+
       |                  TICK ENGINE (60Hz)                   |
       |  Budget: 16.66ms                                      |
       +-------------------------------------------------------+
                                  |
    +-----------------------------+-----------------------------+
    |                             |                             |
    v                             v                             v
[Phase 1: Ingestion]    [Phase 2: Simulation]        [Phase 3: Egress]
- Drain Ring Buffers    - Process Systems (ECS)      - Compute AoI
- Parse & Validate      - NavMesh / AI Agent Ticks   - Delta Compression
- Anti-Cheat Sanity     - Resolve Collisions         - UDP Broadcast
```

#### 3.2 Komponen Inti Arsitektur Produksi
1. **Network Ingestion Layer**: Menggunakan model *non-blocking I/O* dengan *ring buffer* per koneksi untuk membaca paket UDP langsung ke buffer memori yang sudah dialokasikan di awal (*pre-allocated memory*).
2. **Input Queue & Validation Engine**: Melindungi server dari eksploitasi kecepatan (*speed-hack*) dan manipulasi waktu dengan memvalidasi *sequence number* serta stempel waktu (*timestamp*).
3. **Spatial Partitioning Engine (AoI)**: Mengelompokkan entitas ke dalam sel berbasis grid atau pohon hierarkis (*dynamic spatial hashes/quadtree*). Entitas hanya menerima pembaruan dari entitas lain yang berada di dalam radius visibilitas (*Area of Interest*).
4. **State Snapshot & Delta Compressor**: Menghasilkan *snapshot* dunia, menghitung selisih bit (*delta bitmask*) terhadap *acknowledged snapshot* terakhir dari klien tertentu, dan mengirimkan payload terkompresi.

---

### 4. Why & What

| Paradigma | Karakteristik | Kelemahan di Skala Produksi | Solusi Enterprise |
| :--- | :--- | :--- | :--- |
| **Peer-to-Peer / Lockstep** | Klien saling bertukar input; simulasi berjalan lokal di tiap klien. | Rentan eksploitasi (*maphack*, manipulasi status); *input lag* bertambah seiring latensi pemain terlambat (*slowest link*). | **Dedicated Authoritative Server**: Server menjadi satu-satunya sumber kebenaran (*single source of truth*). |
| **TCP / HTTP / RPC** | Reliable, in-order delivery, flow-control berbasis window. | **Head-of-Line Blocking**: Paket yang hilang menahan seluruh pemrosesan paket berikutnya, memicu *latency spike* hingga ratusan milidetik. | **UDP + Custom Reliability Layer**: Data input & snapshot status menggunakan UDP; keandalan diatur manual (*unreliable-sequenced* vs *reliable-ordered*). |
| **Naive Object Broadcasting** | Mengirimkan posisi setiap entitas ke setiap klien ($O(N^2)$). | Skalabilitas jaringan runtuh saat $N > 100$. Bandwidth = $O(N^2 \times \text{payload})$. | **Area of Interest (AoI) Culling**: Server hanya mengirimkan pembaruan entitas yang berada dalam jangkauan sensor/kamera klien ($O(N \times K)$). |

---

### 5. How: Alur Kerja Pipeline Pemrosesan

Alur komputasi dari penerimaan paket jaringan hingga pengiriman paket pembaruan status:

```
[Klien UDP Socket]
       |
       v (Raw UDP Datagram)
[Kernel OS Socket Buffer]
       |
       v (recvmmsg / epoll)
[Ingress Worker Pool] ---> [Ring Buffer Queue (Lock-Free)]
                                  |
                                  v
                    +-----------------------------+
                    | AUTHORITATIVE TICK LOOP     |
                    +-----------------------------+
                    | 1. Read Inputs              |
                    | 2. Reconcile Client State   |
                    | 3. Step Physics / AI Agents |
                    | 4. Update Spatial Hashes    |
                    | 5. Build Frame Snapshot     |
                    +-----------------------------+
                                  |
       +--------------------------+--------------------------+
       |                                                     |
       v (Entity List in AoI)                                v (Entity List in AoI)
[Client A Serialization Worker]              [Client B Serialization Worker]
       | (Delta Compression vs Ack)                          | (Delta Compression vs Ack)
       v                                                     v
[Egress UDP Socket Engine]                   [Egress UDP Socket Engine]
```

1. **Ingress Pipeline**: Worker membaca datagram secara masif menggunakan *batch system calls* (`recvmmsg` pada Linux), mendekode *header*, memvalidasi integritas paket, lalu memasukkannya ke antrean *lock-free single-producer single-consumer* (SPSC) milik tick worker.
2. **Tick Evaluation**: Simulator mengeksekusi sistem logika secara berurutan. AI Agent berjalan menggunakan *behavior tree* atau *utility system* di atas grid spatial yang sama dengan pemain.
3. **Egress Pipeline**: Di akhir tick, thread partisi spasial menentukan entitas mana yang relevan untuk setiap pemain. Delta state dikompresi menggunakan *bit packing*, lalu dikirim via antrean pengiriman tak-sinkron (*asynchronous send queue*).

---

### 6. Analogi & Diagram ASCII

#### Analogi Meja Catur Telegrafis
Bayangkan sebuah turnamen catur cepat di mana pemain tidak berhadapan langsung. Pemain mengirimkan instruksi gerakan telegrafis ("Pion ke E4") ke **Wasit Tunggal (Authoritative Server)**. 
- Pemain langsung menggerakkan pionnya di papan lokalnya sendiri (**Client-Side Prediction**) agar tidak perlu menunggu balasan telegraf.
- Wasit mengevaluasi gerakan tersebut terhadap aturan resmi. Jika ilegal (misal pion melompat dua petak saat terhalang), wasit mengirim telegram penolakan paksa (**Server Reconciliation**), dan pemain harus memindahkan kembali bidaknya ke posisi yang ditentukan wasit.
- Jika ada 100 papan catur di ruangan besar, wasit tidak membacakan status seluruh papan ke semua orang; ia hanya memberitahu pemain tentang kondisi papan mereka sendiri dan papan lawan yang sedang mereka amati (**Area of Interest**).

#### Arsitektur Internal Memori Spatial Hash Grid
```
Dunia Permainan 2D/3D (Dibagi ke dalam Sel-Sel Grid Diskret)
+-------------+-------------+-------------+-------------+
| Cell (0,2)  | Cell (1,2)  | Cell (2,2)  | Cell (3,2)  |
| [Player B]  |             | [Bot AI-1]  |             |
+-------------+-------------+-------------+-------------+
| Cell (0,1)  | Cell (1,1)  | Cell (2,1)  | Cell (3,1)  |
|             | [Player A]  | [Bot AI-2]  |             |
|             |  AoI Radius |             |             |
+-------------+-------------+-------------+-------------+
| Cell (0,0)  | Cell (1,0)  | Cell (2,0)  | Cell (3,0)  |
|             |             |             |             |
+-------------+-------------+-------------+-------------+

Spatial Hash Function:
Hash(X, Y) = ((floor(X / CellSize) * P1) ^ (floor(Y / CellSize) * P2)) % TableSize

Player A hanya memeriksa Cell: (0,2), (1,2), (2,2), (0,1), (1,1), (2,1), (0,0), (1,0), (2,0).
Entitas di Cell (3,X) diabaikan sepenuhnya dari kalkulasi pembaruan Player A!
```

---

### 7. Implementasi Kode Standar Industri

Di bawah ini adalah implementasi sistem produksi inti dalam bahasa Go, mencakup *Fixed-Timestep Game Loop*, *Spatial Hash Grid* berkinerja tinggi, dan *Zero-Allocation Memory Pooling*.

```go
package main

import (
	"context"
	"encoding/binary"
	"fmt"
	"math"
	"net"
	"sync"
	"sync/atomic"
	"time"
)

// --- KONSTANTA ENGINE ---
const (
	TickRate       = 60
	TickDuration   = time.Second / TickRate
	CellSize       = 32.0 // Ukuran sel grid dalam unit koordinat dunia
	MaxEntities    = 10000
	MaxPacketSize  = 1200 // MTU Safe size untuk UDP
	WorldBoundMaxX = 1024.0
	WorldBoundMaxY = 1024.0
)

// --- STRUKTUR DATA SPASIAL & ENTITAS ---

type Vector2 struct {
	X float32
	Y float32
}

func (v Vector2) DistanceSq(other Vector2) float32 {
	dx := v.X - other.X
	dy := v.Y - other.Y
	return dx*dx + dy*dy
}

type EntityType uint8

const (
	EntityPlayer EntityType = 1
	EntityAIAgent EntityType = 2
)

type Entity struct {
	ID        uint32
	Type      EntityType
	Position  Vector2
	Velocity  Vector2
	LastInput uint32 // Sequence ID dari input terakhir
	Active    bool
}

// SpatialHashGrid mengelola partisi spasial 2D untuk Area of Interest (AoI)
type SpatialHashGrid struct {
	cellSize float32
	buckets  map[int64][]uint32
	mu       sync.RWMutex
}

func NewSpatialHashGrid(cellSize float32) *SpatialHashGrid {
	return &SpatialHashGrid{
		cellSize: cellSize,
		buckets:  make(map[int64][]uint32, 1024),
	}
}

func (grid *SpatialHashGrid) hashCoords(x, y float32) int64 {
	gx := int64(math.Floor(float64(x / grid.cellSize)))
	gy := int64(math.Floor(float64(y / grid.cellSize)))
	return (gx * 73856093) ^ (gy * 19349663)
}

func (grid *SpatialHashGrid) Clear() {
	grid.mu.Lock()
	defer grid.mu.Unlock()
	for k := range grid.buckets {
		grid.buckets[k] = grid.buckets[k][:0]
	}
}

func (grid *SpatialHashGrid) Insert(id uint32, pos Vector2) {
	h := grid.hashCoords(pos.X, pos.Y)
	grid.mu.Lock()
	grid.buckets[h] = append(grid.buckets[h], id)
	grid.mu.Unlock()
}

func (grid *SpatialHashGrid) QueryRadius(pos Vector2, radius float32, result *[]uint32) {
	grid.mu.RLock()
	defer grid.mu.RUnlock()

	minX := pos.X - radius
	maxX := pos.X + radius
	minY := pos.Y - radius
	maxY := pos.Y + radius

	startGX := int64(math.Floor(float64(minX / grid.cellSize)))
	endGX := int64(math.Floor(float64(maxX / grid.cellSize)))
	startGY := int64(math.Floor(float64(minY / grid.cellSize)))
	endGY := int64(math.Floor(float64(maxY / grid.cellSize)))

	for gx := startGX; gx <= endGX; gx++ {
		for gy := startGY; gy <= endGY; gy++ {
			h := (gx * 73856093) ^ (gy * 19349663)
			if ids, exists := grid.buckets[h]; exists {
				*result = append(*result, ids...)
			}
		}
	}
}

// --- POOLING MEMORI TANPA ALOKASI GC (ZERO-ALLOCATION) ---

var packetPool = sync.Pool{
	New: func() interface{} {
		b := make([]byte, MaxPacketSize)
		return &b
	},
}

// --- ENGINE SIMULASI UTAMA ---

type ServerWorld struct {
	entities    []Entity
	entityMap   map[uint32]int // ID -> Index di slice
	spatialGrid *SpatialHashGrid
	tickCounter uint64
	udpConn     *net.UDPConn
	running     int32
	mu          sync.Mutex
}

func NewServerWorld(addr string) (*ServerWorld, error) {
	udpAddr, err := net.ResolveUDPAddr("udp", addr)
	if err != nil {
		return nil, err
	}
	conn, err := net.ListenUDP("udp", udpAddr)
	if err != nil {
		return nil, err
	}

	return &ServerWorld{
		entities:    make([]Entity, 0, MaxEntities),
		entityMap:   make(map[uint32]int, MaxEntities),
		spatialGrid: NewSpatialHashGrid(CellSize),
		udpConn:     conn,
		running:     1,
	}, nil
}

func (w *ServerWorld) SpawnEntity(id uint32, eType EntityType, pos Vector2) {
	w.mu.Lock()
	defer w.mu.Unlock()

	entity := Entity{
		ID:       id,
		Type:     eType,
		Position: pos,
		Active:   true,
	}
	w.entities = append(w.entities, entity)
	w.entityMap[id] = len(w.entities) - 1
}

// RunTickPipeline menjalankan loop dengan teknik Fixed Timestep Accumulator
func (w *ServerWorld) Start(ctx context.Context) {
	ticker := time.NewTicker(TickDuration)
	defer ticker.Stop()

	var lastTime = time.Now()
	var accumulator time.Duration

	// Buffer penampung sementara untuk query spasial tanpa alokasi baru
	localQueryBuf := make([]uint32, 0, 256)

	for atomic.LoadInt32(&w.running) == 1 {
		select {
		case <-ctx.Done():
			return
		case currentTime := <-ticker.C:
			frameTime := currentTime.Sub(lastTime)
			lastTime = currentTime

			// Mencegah akumulasi tak berbatas jika server mengalami stall
			if frameTime > time.Millisecond*100 {
				frameTime = time.Millisecond * 100
			}
			accumulator += frameTime

			for accumulator >= TickDuration {
				w.TickPhysicsAndAI(float32(TickDuration.Seconds()))
				w.BroadcastWorldSnapshots(&localQueryBuf)
				accumulator -= TickDuration
				w.tickCounter++
			}
		}
	}
}

func (w *ServerWorld) TickPhysicsAndAI(dt float32) {
	w.mu.Lock()
	defer w.mu.Unlock()

	w.spatialGrid.Clear()

	// Update posisi entitas, AI behaviour, dan sinkronisasi ke grid spasial
	for i := 0; i < len(w.entities); i++ {
		e := &w.entities[i]
		if !e.Active {
			continue
		}

		if e.Type == EntityAIAgent {
			// Sederhana: Autonomous wander AI loop
			e.Position.X += e.Velocity.X * dt
			e.Position.Y += e.Velocity.Y * dt

			// Cek batasan dunia
			if e.Position.X < 0 || e.Position.X > WorldBoundMaxX {
				e.Velocity.X *= -1
			}
			if e.Position.Y < 0 || e.Position.Y > WorldBoundMaxY {
				e.Velocity.Y *= -1
			}
		}

		// Re-insert ke spatial hash
		w.spatialGrid.Insert(e.ID, e.Position)
	}
}

func (w *ServerWorld) BroadcastWorldSnapshots(queryBuf *[]uint32) {
	w.mu.Lock()
	defer w.mu.Unlock()

	radius := float32(64.0) // Radius AoI visibilitas pemain

	for i := 0; i < len(w.entities); i++ {
		p := &w.entities[i]
		if !p.Active || p.Type != EntityPlayer {
			continue
		}

		*queryBuf = (*queryBuf)[:0]
		w.spatialGrid.QueryRadius(p.Position, radius, queryBuf)

		// Serialisasi snapshot relevan secara zero-alloc
		packetBufferPtr := packetPool.Get().(*[]byte)
		buf := *packetBufferPtr

		// Header Paket: [Tick (8 byte)] [Jumlah Entitas (2 byte)]
		binary.LittleEndian.PutUint64(buf[0:8], w.tickCounter)
		count := uint16(len(*queryBuf))
		binary.LittleEndian.PutUint16(buf[8:10], count)

		offset := 10
		for _, nearbyID := range *queryBuf {
			idx := w.entityMap[nearbyID]
			nearbyEnt := w.entities[idx]

			// Layout data: ID (4B), Type (1B), PosX (4B), PosY (4B) = 13 Byte per entitas
			if offset+13 > MaxPacketSize {
				break // Proteksi fragmentasi MTU
			}
			binary.LittleEndian.PutUint32(buf[offset:offset+4], nearbyEnt.ID)
			buf[offset+4] = byte(nearbyEnt.Type)
			binary.LittleEndian.PutUint32(buf[offset+5:offset+9], math.Float32bits(nearbyEnt.Position.X))
			binary.LittleEndian.PutUint32(buf[offset+9:offset+13], math.Float32bits(nearbyEnt.Position.Y))
			offset += 13
		}

		// Simulasi transmisi paket (panggilan non-blocking ke soket UDP sebenarnya)
		// w.udpConn.WriteToUDP(buf[:offset], p.RemoteAddr)

		packetPool.Put(packetBufferPtr)
	}
}

func main() {
	server, err := NewServerWorld("0.0.0.0:8080")
	if err != nil {
		panic(err)
	}

	fmt.Println("[GAME SERVER] Engine otoritatif berjalan di 60Hz...")

	// Spawn simulasi: 1 Player dan 500 AI Agents
	server.SpawnEntity(1, EntityPlayer, Vector2{X: 100, Y: 100})
	for i := uint32(2); i <= 500; i++ {
		server.SpawnEntity(i, EntityAIAgent, Vector2{
			X: float32(i % 1000),
			Y: float32((i * 7) % 1000),
		})
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	server.Start(ctx)
	fmt.Printf("[GAME SERVER] Simulasi selesai. Total Tick tereksekusi: %d\n", server.tickCounter)
}
```

---

### 8. Real World Case Study: Arsitektur Skala Besar (100k CCU Battle Royale)

#### Konteks Sistem
Arsitektur game laga multipemain dengan 100 pemain per pertandingan (*match*), 1.000 pertandingan simultan (**100.000 Concurrent Users / CCU**). Setiap instans server didistribusikan di atas kluster Kubernetes menggunakan orkestrator game server **Agones**.

#### Spesifikasi Kebutuhan & Beban
- **Tick Rate**: 30 Hz ($\Delta t = 33.33\text{ ms}$).
- **Inbound Bandwidth**: Maksimum 15 KB/s per pemain.
- **Outbound Bandwidth**: Maksimum 40 KB/s per pemain.
- **Batas Latensi Server Execution Time**: $t_{\text{tick}} \le 12\text{ ms}$ (memberikan *buffer* keamanan 21.33 ms untuk latensi I/O soket).

#### Implementasi Arsitektur
1. **Edge Packet Director**: Datagram masuk dialihkan langsung melalui eBPF / XDP di layer kernel host untuk memotong *conntrack overhead* Linux iptables yang biasa memicu *packet drop* pada throughput paket UDP tinggi (>500.000 PPS per node).
2. **Deterministic Navigation Mesh**: AI Bot dikalkulasi menggunakan C-bindings NavMesh yang disematkan langsung di dalam *tick execution loop*.
3. **Delta Compression Protocol**: Server menyimpan *circular ring history* dari 64 tick snapshot terakhir. Jika klien mengirimkan ACK untuk Tick 1020, dan saat ini Tick 1024, server hanya mengompresi dan mengirimkan delta posisi/aksi dari 4 tick tersebut via XOR bitmask compression.

```
       +---------------------------------------------+
       |   Internet (100k Players UDP Traffic)       |
       +---------------------------------------------+
                              |
                              v
       +---------------------------------------------+
       | Edge Nodes: eBPF Routing (Zero-Copy XDP)    |
       +---------------------------------------------+
                              |
              +---------------+---------------+
              v                               v
    +-------------------+           +-------------------+
    | Agones Node 1     |           | Agones Node N     |
    | (10 Match Shards) |           | (10 Match Shards) |
    | +---------------+ |           | +---------------+ |
    | | Shard #001    | |           | | Shard #999    | |
    | | 100 Players   | |           | | 100 Players   | |
    | | 30Hz Loop     | |           | | 30Hz Loop     | |
    | +---------------+ |           | +---------------+ |
    +-------------------+           +-------------------+
```

---

### 9. Trade-offs Architecture Matrix

| Aspek Desain | Pilihan A | Pilihan B | Analisis Trade-off Kritis |
| :--- | :--- | :--- | :--- |
| **Model State Engine** | **Snapshot Interpolation** | **Deterministic Lockstep** | **Snapshot Interpolation** membutuhkan *egress bandwidth* lebih tinggi untuk mengirim delta status, namun tahan terhadap *packet loss* parsial dan mendukung pemain *drop-in/drop-out* secara fleksibel. **Lockstep** sangat hemat bandwidth (hanya mengirim input), namun 1 pemain dengan transmisi lambat dapat membekukan simulasi seluruh server tanpa arsitektur rollback yang sangat rumit. |
| **Bahasa Engine** | **Managed Runtime (Go/C#)** | **Native Systems (C++/Rust)** | Go/C# mempercepat *developer velocity* dan mempermudah orkestrasi gRPC/Database backend, namun membutuhkan arsitektur manual *zero-heap allocation* untuk mencegah GC pause. C++/Rust memberikan determinisme penuh sub-milidetik tetapi meningkatkan kompleksitas pengembangan dan risiko kerentanan memori (*memory bugs*). |
| **Topologi Jaringan** | **Mesh AoI (Quadtree Dinamis)** | **Flat Spatial Hash Grid** | **Quadtree** adaptif terhadap kepadatan pemain lokal (misal: 80 pemain berkumpul di 1 titik peta), namun traversal memorinya memicu *pointer dereference* dan *L2 cache miss*. **Flat Grid** menawarkan akses $O(1)$ yang sangat ramah cache CPU, namun boros memori jika ruang dunia sangat masif dan banyak sel kosong. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum (Anti-Patterns)
1. **Membiarkan Timestep Mengambang (Floating Timestep / DeltaTime Naif)**:
   * *Anti-Pattern*: Menggunakan waktu diferensial aktual OS `dt = now() - last_frame` secara langsung pada kalkulasi fisika server.
   * *Dampak*: Menghancurkan determinisme. Dua server dengan variasi beban CPU sekecil apapun akan menghasilkan posisi koordinat berbeda untuk kalkulasi lintasan proyektil yang sama, memicu desinkronisasi fatal.
   * *Solusi*: Gunakan **Fixed Timestep Accumulator** dengan interval integer diskret.
2. **Alokasi Heap Di Dalam Loop Tick Inti**:
   * *Anti-Pattern*: Menginstansiasi `slice`, `map`, atau format string `fmt.Sprintf` di setiap tick untuk setiap entitas.
   * *Dampak*: Menumpuk objek di *Eden space / Gen 0 GC*, memicu jeda *Stop-The-World* (STW) GC setiap beberapa puluh detik yang merusak stabilitas tick.
   * *Solusi*: Alokasikan seluruh slice dan buffer jaringan di awal (*pre-allocate*), gunakan buffer statis dengan indeks, dan daur ulang struct via `sync.Pool`.
3. **Mengabaikan Spiral of Death**:
   * *Anti-Pattern*: Loop simulasi terus mencoba mengejar waktu tertinggal tanpa batas atas jika tick sebelumnya tertunda.
   * *Dampak*: Satu frame yang lambat membuat server menjalankan 5 tick di frame berikutnya, yang memakan waktu lebih lama lagi, menyebabkan server membeku permanen (*CPU lockup*).
   * *Solusi*: Pasang batas atas konsumsi akumulator (*clamping maximum accumulated time*, misal maksimal 100ms per frame).

#### Panduan Troubleshooting Desinkronisasi Status
```
[Indikasi]: Klien mengalami "Rubber-banding" (posisi karakter ditarik kembali secara kasar).

Langkah Diagnostik:
1. Ambil pprof CPU & memory trace pada server:
   go tool pprof -http=:8081 http://localhost:6060/debug/pprof/profile?seconds=30
2. Periksa apakah waktu eksekusi tick melebihi TickDuration:
   Metrics: histogram_quantile(0.99, sum(rate(server_tick_duration_ms_bucket[1m])) by (le))
3. Jika latency tick normal (<10ms), periksa desinkronisasi deterministik:
   Bandingkan Hash SHA-256 State Server vs State Klien pada Tick #N.
4. Identifikasi penyebab drift:
   a. Apakah ada penggunaan tipe data `float64/float32` standar tanpa IEEE-754 fast-math flags yang konsisten?
   b. Apakah urutan eksekusi entitas di loop tidak terurut (iterasi `map` non-deterministik di Go)?
```

---

### 11. Production Best Practices Checklist

- [ ] **Deterministik Iteration**: Hindari iterasi langsung pada struktur data `map` Go di dalam tick loop karena urutan pengembalian kunci sengaja diacak oleh runtime. Gunakan array/slice berindeks tetap.
- [ ] **Memory Pre-allocation**: Inisialisasi kapasitas maksimum entitas pada saat server booting (`make([]Entity, 0, MaxEntities)`).
- [ ] **Dead Reckoning & Extrapolation**: Klien harus menginterpolasi entitas remote dari *past snapshot queue* (biasanya 50-100ms di masa lalu) untuk menutupi *network jitter*.
- [ ] **MTU Fragmentation Shield**: Pastikan ukuran paket snapshot individual tidak melebihi **1200 Byte** untuk mencegah fragmentasi IP di tingkat router jaringan publik.
- [ ] **Dynamic Tick Rate Degradation**: Jika CPU host server mencapai utilisasi 90%, sistem harus secara dinamis menurunkan laju simulasi entitas yang jauh dari pemain (LOD logic) daripada menjatuhkan global tick rate.
- [ ] **Profiling Hooks**: Ekspos endpoint Prometheus untuk:
  - `tick_duration_seconds` (Histogram)
  - `active_entities_count` (Gauge)
  - `packets_dropped_buffer_full` (Counter)

---

### 12. Hands-on Practice: Membangun Core Tick Server

Praktikum ini disimpan pada direktori: `hands-on/m02/`

#### File: `hands-on/m02/ringbuffer.go`
Implementasi lock-free circular buffer untuk menampung input pengguna secara efisien.

```go
package main

import (
	"errors"
	"sync/atomic"
)

var ErrBufferFull = errors.New("ring buffer is full")
var ErrBufferEmpty = errors.New("ring buffer is empty")

type PlayerInput struct {
	EntityID uint32
	TargetX  float32
	TargetY  float32
	InputSeq uint32
}

type InputRingBuffer struct {
	buffer []PlayerInput
	cap    uint32
	head   uint32
	tail   uint32
}

func NewInputRingBuffer(capacity uint32) *InputRingBuffer {
	return &InputRingBuffer{
		buffer: make([]PlayerInput, capacity),
		cap:    capacity,
	}
}

func (rb *InputRingBuffer) Push(input PlayerInput) error {
	head := atomic.LoadUint32(&rb.head)
	tail := atomic.LoadUint32(&rb.tail)

	if (tail + 1) % rb.cap == head {
		return ErrBufferFull
	}

	rb.buffer[tail] = input
	atomic.StoreUint32(&rb.tail, (tail+1)%rb.cap)
	return nil
}

func (rb *InputRingBuffer) Pop() (PlayerInput, error) {
	head := atomic.LoadUint32(&rb.head)
	tail := atomic.LoadUint32(&rb.tail)

	if head == tail {
		return PlayerInput{}, ErrBufferEmpty
	}

	val := rb.buffer[head]
	atomic.StoreUint32(&rb.head, (head+1)%rb.cap)
	return val, nil
}
```

#### File: `hands-on/m02/main.go`
Eksekusi pengujian stres pipeline dengan 20.000 input acak.

```go
package main

import (
	"fmt"
	"time"
)

func main() {
	rb := NewInputRingBuffer(1024)

	// Producer thread (Simulasi paket masuk dari network)
	go func() {
		for i := uint32(0); i < 5000; i++ {
			err := rb.Push(PlayerInput{
				EntityID: 1,
				TargetX:  float32(i),
				TargetY:  float32(i * 2),
				InputSeq: i,
			})
			for err == ErrBufferFull {
				time.Sleep(time.Microsecond * 50)
				err = rb.Push(PlayerInput{
					EntityID: 1,
					TargetX:  float32(i),
					TargetY:  float32(i * 2),
					InputSeq: i,
				})
			}
		}
	}()

	// Consumer (Simulasi tick engine)
	consumed := 0
	start := time.Now()
	for consumed < 5000 {
		_, err := rb.Pop()
		if err == nil {
			consumed++
		} else {
			time.Sleep(time.Microsecond * 10)
		}
	}

	fmt.Printf("[HANDS-ON] Berhasil memproses %d paket input dalam %v!\n", consumed, time.Since(start))
}
```

#### Langkah Menjalankan:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init server-deepdive
go run ringbuffer.go main.go
```

---

### 13. Exercises

#### Level 1 (Easy)
Tambahkan fungsi validasi sanitasi input pada `PlayerInput` di `hands-on/m02/ringbuffer.go` untuk mendeteksi apakah `TargetX` atau `TargetY` mengandung nilai `math.IsNaN()` atau `math.IsInf()`. Tolak input tersebut sebelum dimasukkan ke ring buffer.

#### Level 2 (Medium)
Modifikasi implementasi `SpatialHashGrid` di seksi 7 agar mendukung pembaruan entitas yang bergerak (*update entity position*) secara efisien tanpa harus mengosongkan seluruh grid (`Clear()`) di setiap frame, yaitu hanya memperbarui sel hash jika entitas melewati batas sel asalnya.

#### Level 3 (Hard)
Bangun sistem kompresi snapshot *Delta-Bitmask* sederhana: Buat fungsi yang membandingkan dua *frame snapshot* berturutan. Jika koordinat suatu entitas tidak berubah dari frame sebelumnya, kirimkan satu bit `0`. Jika berubah, kirimkan bit `1` diikuti oleh posisi baru yang dikompresi ke integer 16-bit diskret (resolusi 0.1 unit). Tunjukkan pengurangan konsumsi bandwidth byte-per-frame.

---

### 14. Challenge: Kasus Sinkronisasi Arbitrase Ribuan Bot AI

**Deskripsi Kasus Nyata**:
Anda sedang memimpin pengembangan server untuk game *Massively Multiplayer Survival Simulation*. Di dunia permainan, terdapat **10.000 Bot AI Agent (Autonomous Wildlife)** dan **1.000 Pemain Simultan** di peta terbuka berukuran $4000 \times 4000$ unit. Server mengalami masalah latensi ekstrem:
1. Waktu pemrosesan tick melonjak dari 15ms menjadi **78ms** per tick saat sekelompok 500 bot berkumpul mengejar 20 pemain di kota tengah peta.
2. Jaringan internet klien langsung mengalami *packet loss* parah karena server mencoba menyiarkan pergerakan seluruh 500 bot tersebut kepada seluruh 20 pemain.
3. Alokasi heap Go melonjak hingga 4GB dalam 10 menit, memicu jeda GC selama 120ms.

**Tugas Arsitektural**:
Rancang dokumen arsitektur dan spesifikasi strategi sistem mitigasi (lengkap dengan pseudocode/komponen alur teknis) untuk:
- Mengimplementasikan **Dynamic Entity Level of Detail (LOD)**: AI bot yang berada di luar jarak sensor pandang pemain diturunkan tick ratenya menjadi 1Hz atau dievaluasi secara statistik murni, sementara bot di dekat pemain ditick pada 30Hz penuh.
- Membatasi kuota transmisi AoI: Batasi transfer maksimum 50 entitas paling kritis per frame ke klien menggunakan sistem pemeringkatan prioritas jarak (*Priority-Weighted Bucket Egress*).
- Menjamin stabilitas memori: Desain sistem penyimpanan entitas menggunakan array flat (Data-Oriented ECS) yang sepenuhnya menghilangkan alokasi heap baru saat runtime per-tick.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Mengapa server game kompetitif real-time hampir selalu dirancang sebagai *Authoritative Server* dibandingkan arsitektur *P2P*?**
   - *Jawaban*: Untuk mencegah kecurangan (*anti-cheat*) dengan menjadikan server satu-satunya penentu validitas aksi dan posisi status dunia yang sah, serta melindungi IP jaringan pemain lain dari paparan langsung.
2. **Apa yang dimaksud dengan satu *Tick* dalam konteks server game?**
   - *Jawaban*: Satu iterasi siklus eksekusi penuh diskret di mana server membaca input jaringan, memproses aturan logika, mengeksekusi simulasi fisika/AI, dan mengirimkan snapshot status terbaru ke klien.
3. **Mengapa protokol TCP umumnya dihindari untuk pengiriman snapshot pergerakan entitas real-time?**
   - *Jawaban*: TCP memiliki sifat *Head-of-Line Blocking*; jika satu paket hilang, TCP menahan seluruh data berikutnya sampai paket yang hilang ditransmisikan ulang, menyebabkan lonjakan latensi yang tidak dapat ditoleransi oleh game berkecepatan tinggi.
4. **Apa bahaya mengalokasikan memori pointer baru (heap allocation) di dalam fungsi tick loop server berkecepatan 60Hz?**
   - *Jawaban*: Memicu pembersihan memori (*Garbage Collection pauses*) secara konstan yang menghentikan eksekusi thread server (STW), mengakibatkan server kehilangan target waktu *frame budget* (terjadi *tick drop*).
5. **Apa fungsi utama dari *Spatial Partitioning* (seperti Grid Hash atau Quadtree) dalam server game?**
   - *Jawaban*: Mengurangi kompleksitas pencarian entitas di sekitarnya dan kalkulasi transmisi jaringan dari kompleksitas brute force $O(N^2)$ menjadi $O(N)$ atau $O(1)$ per query sel.

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Jelaskan perbedaan mendasar antara *Client-Side Prediction* dan *Server Reconciliation*.**
   - *Jawaban*: *Prediction* adalah eksekusi input lokal secara instan di klien tanpa menunggu respon server agar terasa bebas lag; *Reconciliation* adalah proses di mana klien menerima status otoritatif server yang tertunda, membuang prediksi yang salah jika ada divergensi, dan mengulang (*replay*) input lokal yang belum di-ack server dari titik status server tersebut.
7. **Bagaimana cara kerja teknik *Fixed Timestep with Accumulator* dalam mencegah ketidakkonsistenan simulasi?**
   - *Jawaban*: Mesin mengakumulasi waktu nyata yang berlalu dan hanya mengeksekusi simulasi dalam potongan waktu diskret bernilai konstan (misal: tepat 16.66ms per langkah). Sisa waktu disimpan untuk frame berikutnya, memastikan angka deterministik matematika tidak dipengaruhi fluktuasi frame rate mesin host.
8. **Apa itu fenomena *Spiral of Death* pada game loop dan bagaimana cara mencegahnya?**
   - *Jawaban*: Kondisi di mana komputasi frame memakan waktu lebih lama dari batas budget, menyebabkan akumulator bertambah besar; frame berikutnya mencoba mengejar ketertinggalan dengan menjalankan lebih banyak tick, yang justru semakin memperberat server hingga macet total. Dicegah dengan *clamping* batas atas waktu frame akumulator maksimum (misal max 100ms).
9. **Mengapa pada koordinat spasial hashing, penggunaan bilangan *floating point* rentan memicu bug jika tidak diflooring dengan benar?**
   - *Jawaban*: Bilangan float negatif (misal `-0.1`) jika dikonversi langsung ke integer casting tanpa fungsi `Floor` yang tepat akan memotong ke arah nol (`0`), menggabungkan dua sel grid yang berbeda ke dalam indeks yang sama dan merusak relasi spasial.
10. **Apa perbedaan antara strategi pengiriman *Full State Snapshot* dan *Delta Snapshot Compression*?**
    - *Jawaban*: *Full Snapshot* mengirimkan seluruh kondisi data entitas secara berkala (boros bandwidth, murah CPU server); *Delta Compression* hanya mengirimkan perubahan variabel (bit mask) yang berbeda dari snapshot terakhir yang telah dikonfirmasi (ACK) oleh klien tertentu (sangat hemat bandwidth, membutuhkan memori riwayat di server).

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan Kasus)
11. **Skenario 1**: Metrik server menunjukkan CPU usage hanya 25%, tidak ada memory leak, namun klien di seluruh dunia mengeluhkan pemain lain tampak "berteleportasi" setiap 5 detik. Latensi rata-rata RTT normal di 40ms. Apa yang paling mungkin terjadi di level arsitektur engine Go?
    - *Solusi Analisis*: Terjadi jeda Stop-The-World (STW) Garbage Collection singkat secara periodik atau thread starvation akibat blocking I/O pada goroutine yang memegang mutex global tick. Periksa metrik `go_gc_duration_seconds` dan pastikan tidak ada operasi disk logging sinkron atau pemanggilan database di dalam pipeline tick.
12. **Skenario 2**: Dua pemain menembakkan proyektil secara bersamaan pada waktu fisik lokal mereka. Server menerima Paket A pada $t=10.05$ dan Paket B pada $t=10.07$. Namun, pemain B memiliki ping 20ms dan pemain A memiliki ping 120ms. Siapa yang seharusnya menang dan bagaimana server mengevaluasinya secara adil?
    - *Solusi Analisis*: Server otoritatif yang mengimplementasikan **Lag Compensation / Backward Reconciliation** akan memundurkan (*rewind*) hitbox dunia ke stempel waktu saat Pemain A menekan pelatuk ($t_{\text{fire}} = t_{\text{receive}} - \text{Latency}$), mengevaluasi validitas tabrakan di masa lalu tersebut, dan menetapkan pemenang berdasarkan urutan stempel waktu aksi asli yang sah, bukan urutan kedatangan paket di socket server.
13. **Skenario 3**: Sebuah shard server battle royale menampung 100 pemain. Pada akhir game, 30 pemain yang masih hidup berkumpul di zona lingkaran aman terakhir yang sangat sempit ($20 \times 20$ meter). Alokasi bandwidth server melonjak drastis melebihi batas uplink NIC dan drop rate paket mencapai 40%. Mengapa algoritma Area of Interest (AoI) biasa gagal dalam skenario ini dan apa solusi arsitekturalnya?
    - *Solusi Analisis*: Algoritma AoI spasial memfilter berdasarkan jarak fisik; ketika seluruh pemain berada di sel yang sama, AoI berdegradasi kembali menjadi sistem naive $O(N^2)$, memaksa server mengirim 30 pembaruan ke 30 klien (900 updates/tick). Solusinya adalah menerapkan **Relevance Culling / Bandwidth Budgeting**: Batasi pembaruan per frame ke batas maksimal (misal 15 entitas paling relevan), prioritaskan musuh yang berada tepat di garis pandang mata (*Frustum/Occlusion Culling*), dan turunkan frekuensi pembaruan posisi musuh yang terhalang dinding menjadi 5Hz.

---

### 16. Summary

- **Fondasi Otoritatif**: Server game adalah simulator fisik dan logis deterministik. Klien hanya mengirimkan input aksi pengguna (*intentions*), server memvalidasi dan memproses simulasi, lalu mengembalikan status mutlak (*ground truth*).
- **Integritas Waktu (Tick Loop)**: Simulasi wajib diikat ke skema *Fixed Timestep Accumulator* untuk menjamin determinisme komputasi di berbagai platform perangkat keras serta mencegah jebakan deselerasi *Spiral of Death*.
- **Efisiensi Jaringan Skala Ekstrem**: UDP adalah fondasi utama transmisi status dinamis. Beban jaringan $O(N^2)$ wajib dipangkas menggunakan **Spatial Hash Grid (Area of Interest)** dan kompresi status berbasis **Delta Encoding / Bit-packing**.
- **Rekayasa Sistem Bebas Alokasi (Zero-Allocation)**: Di tingkat bahasa managed seperti Go, siklus tick berkecepatan tinggi menuntut penggunaan teknik *object pooling* (`sync.Pool`), buffer array statis berkapasitas tetap, serta penghindaran konversi interface atau dynamic heap allocation guna mengeliminasi jeda Garbage Collection yang merusak ritme simulasi real-time.