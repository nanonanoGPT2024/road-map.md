# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Spatial Partitioning & Interest Management**  
**Jalur Pembelajaran: Server-Side Game Developer (AI, Data, and Autonomous Agents)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis & Mengeliminasi Bottleneck $O(N^2)$**: Mengidentifikasi titik kritis komputasi interaksi spasial pada arsitektur *authoritative game server* dan mereduksinya menjadi amortized $O(1)$ atau $O(k \log N)$ menggunakan struktur data spasial modern.
2. **Mendesain Hierarchical Dynamic Spatial Partitioning**: Mengimplementasikan *Loose Quadtree/Octree* dan *Flat Array Spatial Hash Grid* dengan alokasi memori berorientasi *Data-Oriented Design* (DOD) untuk meminimalkan *cache misses* (L1/L2/L3) dan *garbage collection pauses*.
3. **Mengembangkan Sistem Interest Management (AoI) Terdistribusi**: Mengimplementasikan mekanisme pub-sub berbasis *observer-subject*, kalkulasi *view frustum/radius AoI*, serta integrasi *hysteresis boundary* untuk mencegah fluktuasi *network churn*.
4. **Mengorkestrasi Entity Handoff & Ghosting Antar-Node**: Mengarsitekturi sinkronisasi entitas lintas *spatial worker boundary* secara mulus (*seamless cross-node handoff*) dengan latensi sub-50ms menggunakan teknik *ghosting/replication proxy*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* **Matematika Vektor Spasial**: Operasi vektor 2D/3D (Dot Product, Cross Product, Euclidean vs Manhattan Distance, Axis-Aligned Bounding Box/AABB intersection test).
* **Memory Layout & Computer Architecture**: Struktur data *Cache-friendly* (Structure of Arrays vs Array of Structures), penanganan *CPU cache line false sharing*, dan *memory pooling*.
* **Konkurensi & Sinkronisasi**: Read-Copy-Update (RCU), *lock-free primitives* (Atomic pointers, CAS), serta pemahaman atas *race condition* pada *tick-loop multi-threaded*.
* **Dasar Networking Game**: Protokol UDP/Reliable-UDP, snapshot interpolation, delta compression, dan limitasi paket *Maximum Transmission Unit* (MTU).

---

## 3. Concept & Internal Architecture

### 3.1 Krisis Komputasi Spasial Skala Masif
Pada arsitektur game *authoritative*, server bertanggung jawab memvalidasi pergerakan, deteksi tabrakan (broad-phase), kalkulasi agropatrolling NPC, dan broadcast state entitas. Pendekatan naif memeriksa jarak setiap entitas terhadap seluruh entitas lain:
$$\text{Total Interaksi} = \frac{N(N - 1)}{2} \implies O(N^2)$$
Jika $N = 10.000$, server harus memproses $\approx 49.995.000$ kalkulasi jarak per tick. Pada tick rate 30 Hz (33.33ms budget), satu tick hanya menyisakan fraksi nanodetik per komparasi—pasti menyebabkan *tick degradation* dan *rubberbanding*.

Interest Management (AoI) memangkas kompleksitas ini dengan memastikan klien hanya menerima update paket data entitas yang berada dalam radius persepsi sensorisnya (visual, audio, radar).

```
   [ Naive $O(N^2)$ Network Fan-out ]                 [ Spatial AOI Partitioning ]
          (Entity E1)                                      [Cell A]        [Cell B]
        /   |   |   \                                      (E1) (E2)         (E4)
      (E2) (E3)(E4) (E5)  <-- Broadcast All                 \  /
                                                             (Local AOI)    [Cell C]
   10k Entitas = 100M Pesan/detik                          E1 hanya menerima (E2)
   Server Bandwidth Collapsed                              CPU & Network Scalable
```

### 3.2 Taksonomi Partisi Spasial
Arsitektur produksi modern memilih struktur data berdasarkan distribusi spasial dan rasio dinamis-statis entitas:

| Karakteristik | Spatial Hash Grid (Flat Array) | Loose Quadtree / Octree | Dynamic Bounding Volume Hierarchy (BVH) |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Query** | Amortized $O(1)$ | $O(\log N)$ | $O(\log N)$ |
| **Kompleksitas Update** | $O(1)$ | $O(\log N)$ | $O(\log N)$ up to $O(N)$ rebalance |
| **Karakteristik Memori** | Contiguous dense array, predictable cache-line | Pointer-heavy (node overhead), cache-unfriendly jika tidak di-pool | Tree node pointers, tree balance overhead |
| **Perilaku Entitas Cepat** | Sangat efisien, re-hash instan | Memerlukan traversal up-down tree | Sering memicu subtree refitting/rebalancing |
| **Boundary Problem** | Entitas di perbatasan sel rentan multi-bucket insert | *Loose boundaries* melonggarkan batas hingga 2x ukuran sel | Tidak ada batas kaku sel, membungkus objek presisi |
| **Best For** | MMO Open World, Dense 2D/2.5D Surface, Uniform Entities | 3D Space/Flight Simulator, Non-uniform sparse distribution | Raycast Query, Physics Broad-phase, Ragdolls |

### 3.3 Anatomi Loose Quadtree
Berbeda dari Quadtree reguler yang membagi ruang secara kaku (di mana objek yang memotong batas sel (*boundary crossing*) harus disimpan pada *parent node* yang besar), **Loose Quadtree** memperbesar dimensi setiap node dengan faktor kelonggaran $k$ (umumnya $k = 2$):
$$\text{Dimensi Node Baru} = \text{Dimensi Reguler} \times k$$
Dengan aturan ini, objek dengan radius tertentu dijamin dapat dimasukkan ke dalam node terdalam yang muat tanpa harus didorong ke *root*, mencegah degradasi performa pada persimpangan sel.

### 3.4 Spatial Hashing dengan Morton Encoding (Z-Order Curve)
Spatial Hash konvensional sering menggunakan fungsi modulus:
$$\text{Hash}(x, y) = ((x \cdot p_1) \oplus (y \cdot p_2)) \pmod M$$
Kelemahan pendekatan ini adalah hilangnya *spatial locality* dalam memori—sel tetangga fisik berada pada alamat memori acak.

Sistem enterprise performa tinggi memanfaatkan **Morton Encoding (Z-Order Curve)**:
```
Koordinat X (biner):  0 1 0 1  (5 desimal)
Koordinat Y (biner):  1 0 1 0  (10 desimal)
Interleave X & Y:     1 0 0 1 1 0 0 1 (Morton Code: 153)
```
Dengan mengurutkan array sel menggunakan Morton Code, traversal sel tetangga ($x \pm 1, y \pm 1$) mengakses blok memori contiguous di DRAM, memaksimalkan *hardware prefetching* CPU L1/L2 data cache.

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal di Skala Enterprise?
1. **Garbage Collection Pressure**: Penggunaan struktur berbasis pointer dinamis (seperti linked list per grid bucket di Java/Go/C#) memicu alokasi jutaan objek kecil per detik. Alokasi ini menyebabkan GC *Stop-The-World* (STW), meningkatkan jitter latensi di atas ambang batas kritis (100ms).
2. **Boundary Thrashing**: Ketika entitas berosilasi di antara dua sel spasial per tick, sistem tanpa *hysteresis* akan mendaftarkan (*subscribe*) dan membatalkan (*unsubscribe*) entitas secara berulang, membanjiri antrean paket jaringan dengan event `SpawnEntity`/`DespawnEntity`.
3. **Cross-Worker Edge Faults**: Saat membagi dunia game ke dalam beberapa mesin terdistribusi (*world slicing*), batas partisi menjadi *single point of contention*. Tanpa strategi *entity ghosting*, AI tidak dapat melihat pemain yang berdiri 1 meter di seberang batas server.

### Apa Solusinya?
* Mengganti pointer individual dengan **Indexed Contiguous Array Pools**.
* Menggunakan **Hysteresis AoI Buffers**: Radius pandang (Enter AoI) diset lebih besar dari radius keluar (Leave AoI).
* Mengintegrasikan **Ghost Replication Proxy Pipeline**: Node server pemilik (*master*) mereplikasi *read-only state* entitas ke node tetangga (*shadow worker*) dalam interval tick yang disinkronkan.

---

## 5. How (Workflow Detail)

Siklus eksekusi Interest Management per server tick (misal: 30 Hz / 33.33ms per tick):

```
+-----------------------------------------------------------------------------------+
|                           PHASE 1: INGRESS & MOVEMENT                             |
|  - Parse input paket klien (UDP Payload)                                          |
|  - Update Physics & Transform Matrix (X, Y, Z)                                     |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        PHASE 2: SPATIAL GRID RE-INDEXING                          |
|  - Deteksi perpindahan koordinat sel lama -> sel baru                            |
|  - Zero-alloc Morton Key compute via Bit Manipulation                             |
|  - Update Flat Bucket Index (Swap-back removal, O(1) re-index)                   |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                     PHASE 3: AOI EVALUATION & HYSTERESIS                          |
|  - Ambil 9 (atau 27 pada 3D) tetangga sel terdekat                                |
|  - Evaluasi Hysteresis:                                                           |
|      Dist(Observer, Target) <= R_enter  --> Trigger Subscription (Spawn Packet)   |
|      Dist(Observer, Target) >  R_exit   --> Trigger Unsubscription (Despawn Packet)|
|      R_enter < Dist <= R_exit           --> Pertahankan status saat ini           |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                  PHASE 4: VISIBILITY & OCCLUSION CULLING                          |
|  - Evaluasi Frustum Culling (FOV Observer vs Target Vector)                       |
|  - Raycast Culling statis (Static Occluders / Fog-of-War / Tembok)                |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                    PHASE 5: REPLICATION & DELTA ENCODING                          |
|  - Serialisasi delta-state entitas yang relevan per Observer                      |
|  - Bandwidth prioritisation (Entitas dekat = 30Hz, Entitas jauh = 5Hz)            |
|  - Kompresi & Batch UDP Egress Buffer                                             |
+-----------------------------------------------------------------------------------+
```

---

## 6. Analogy & Diagram ASCII

### 6.1 Analogi Hysteresis AoI
Bayangkan sebuah pintu otomatis di pusat perbelanjaan. Jika sensor disetel untuk membuka pada jarak 2 meter dan langsung menutup begitu Anda mundur ke 2.01 meter, langkah bolak-balik kecil akan membuat pintu membuka dan menutup dengan keras tanpa henti (*thrashing*). 

Solusinya: Sensor membuka pintu pada jarak **3 meter** (*Enter Radius*), dan baru menutupnya jika orang menjauh lebih dari **4 meter** (*Leave Radius*). Di antara jarak 3 hingga 4 meter adalah **Buffer Zone (Hysteresis)** di mana status tidak berubah.

### 6.2 Diagram Spatial Cell, Ghosting, dan Radius Hysteresis

```
+---------------------------------------+---------------------------------------+
| SERVER WORKER NODE A                  | SERVER WORKER NODE B                  |
|                                       |                                       |
|               (Cell 11)               |               (Cell 12)               |
|                                       |                                       |
|                                       |                                       |
|                   Boundary Line       |                                       |
|                         |             |                                       |
|                         |             |                                       |
|            +---------+  |             |                                       |
|            | Observer|  |             |                                       |
|            |   (O1)  |  |             |                                       |
|            +----+----+  |             |                                       |
|                 |       |             |                                       |
|       ..---'''' | ''''---..           |                                       |
|    .-'          |          '-.        |                                       |
|  .'       [R_Enter: 40m]      '.      |                                       |
| /               |               \     |                                       |
|;          ..---'|'---..          ;    |          +-------------------+        |
||        .'      |      '.        ||   |          | Target Master (T) |        |
||       /  [R_Exit: 50m]  \       ||   |          +---------+---------+        |
||      ;         |         ;      ||   |                    |                  |
||      |         +---------+------++---|--------------------+                  |
||      ;                          ;    |                    | Cross-Server     |
||       \                        /     |                    | Replication      |
| \       '.                    .'      |                    v                  |
|  '.       ''---......---''   .'       |           [T_Ghost Proxy]             |
|    '-.                      .-'       |           (Local Entity Copy)         |
|       ''---............---''          |                                       |
|                         |             |                                       |
|               (Cell 21) |             |               (Cell 22)               |
+---------------------------------------+---------------------------------------+
```

---

## 7. Implementation: Simple vs Practical

### 7.1 Simple Example (Anti-Pattern Demo)
Struktur di bawah ini menunjukkan pendekatan naif yang sering ditemukan pada implementasi prototipe. Pendekatan ini menghasilkan *pointer chasing* dan alokasi heap yang agresif.

```go
// ANTI-PATTERN: Heap-allocated slices and pointers trigger GC pauses
package naive

type Entity struct {
    ID   uint64
    X, Y float64
}

type NaiveGrid struct {
    CellSize float64
    // Peta pointer-to-slice memicu alokasi heap masif saat jutaan entitas dipindahkan
    Buckets  map[int]map[int][]*Entity
}

func (g *NaiveGrid) Insert(e *Entity) {
    cx := int(e.X / g.CellSize)
    cy := int(e.Y / g.CellSize)
    if g.Buckets[cx] == nil {
        g.Buckets[cx] = make(map[int][]*Entity)
    }
    // Append terus-menerus memicu alokasi ulang array slice
    g.Buckets[cx][cy] = append(g.Buckets[cx][cy], e)
}
```

### 7.2 Practical Example (Production-Grade Zero-Allocation Spatial Hash Grid)
Implementasi berikut menggunakan arsitektur *contiguous memory*, *static entity pooling*, serta pendekatan *flat dynamic array* untuk menjamin performa deterministik dan meminimalkan alokasi memori runtime.

```go
package spatial

import (
	"math"
	"sync"
	"sync/atomic"
)

const (
	MaxEntitiesPerWorld = 65536
	InvalidIndex        = math.MaxUint32
)

// EntityID merepresentasikan ID unik entitas dalam range uint32
type EntityID uint32

// SpatialEntity merepresentasikan data spasial dalam layout struct contiguous
type SpatialEntity struct {
	ID       EntityID
	X, Y     float32
	Radius   float32
	PrevCell uint32
	Next     uint32 // Linked list pointer berbasis index (mengeliminasi pointer heap 64-bit)
	Prev     uint32
}

// GridConfig mendefinisikan konfigurasi matematis grid
type GridConfig struct {
	WorldWidth  float32
	WorldHeight float32
	CellSize    float32
	Cols        uint32
	Rows        uint32
}

// SpatialHashGrid mengimplementasikan partisi flat contiguous tanpa alokasi memori dinamis runtime
type SpatialHashGrid struct {
	config  GridConfig
	cells   []uint32        // Head pointer index untuk setiap cell (size = Cols * Rows)
	pool    []SpatialEntity // Contiguous memory pool untuk semua entitas
	freeIdx uint32          // Head of free pool stack
	mu      sync.RWMutex
}

// NewSpatialHashGrid mengalokasikan seluruh memori yang dibutuhkan di awal (pre-allocation)
func NewSpatialHashGrid(cfg GridConfig) *SpatialHashGrid {
	cols := uint32(math.Ceil(float64(cfg.WorldWidth / cfg.CellSize)))
	rows := uint32(math.Ceil(float64(cfg.WorldHeight / cfg.CellSize)))
	totalCells := cols * rows

	grid := &SpatialHashGrid{
		config: GridConfig{
			WorldWidth:  cfg.WorldWidth,
			WorldHeight: cfg.WorldHeight,
			CellSize:    cfg.CellSize,
			Cols:        cols,
			Rows:        rows,
		},
		cells: make([]uint32, totalCells),
		pool:  make([]SpatialEntity, MaxEntitiesPerWorld),
	}

	for i := range grid.cells {
		grid.cells[i] = InvalidIndex
	}

	for i := 0; i < MaxEntitiesPerWorld-1; i++ {
		grid.pool[i].Next = uint32(i + 1)
		grid.pool[i].Prev = InvalidIndex
		grid.pool[i].PrevCell = InvalidIndex
	}
	grid.pool[MaxEntitiesPerWorld-1].Next = InvalidIndex
	grid.pool[MaxEntitiesPerWorld-1].Prev = InvalidIndex
	grid.pool[MaxEntitiesPerWorld-1].PrevCell = InvalidIndex

	return grid
}

func (g *SpatialHashGrid) calculateCellIndex(x, y float32) uint32 {
	if x < 0 {
		x = 0
	}
	if y < 0 {
		y = 0
	}
	cx := uint32(x / g.config.CellSize)
	cy := uint32(y / g.config.CellSize)

	if cx >= g.config.Cols {
		cx = g.config.Cols - 1
	}
	if cy >= g.config.Rows {
		cy = g.config.Rows - 1
	}

	return cy*g.config.Cols + cx
}

// Insert menambahkan entitas dari memory pool ke dalam sel spasial
func (g *SpatialHashGrid) Insert(id EntityID, x, y, radius float32) uint32 {
	g.mu.Lock()
	defer g.mu.Unlock()

	idx := atomic.LoadUint32(&g.freeIdx)
	if idx == InvalidIndex {
		panic("Spatial pool exhausted! MaxEntitiesPerWorld reached.")
	}
	g.freeIdx = g.pool[idx].Next

	cellIdx := g.calculateCellIndex(x, y)

	g.pool[idx].ID = id
	g.pool[idx].X = x
	g.pool[idx].Y = y
	g.pool[idx].Radius = radius
	g.pool[idx].PrevCell = cellIdx
	g.pool[idx].Prev = InvalidIndex
	g.pool[idx].Next = g.cells[cellIdx]

	if g.cells[cellIdx] != InvalidIndex {
		g.pool[g.cells[cellIdx]].Prev = idx
	}
	g.cells[cellIdx] = idx

	return idx
}

// Update memvalidasi apakah pergerakan melewati batas sel dan merestrukturisasi linked list jika perlu
func (g *SpatialHashGrid) Update(poolIdx uint32, newX, newY float32) {
	g.mu.Lock()
	defer g.mu.Unlock()

	entity := &g.pool[poolIdx]
	oldCell := entity.PrevCell
	newCell := g.calculateCellIndex(newX, newY)

	entity.X = newX
	entity.Y = newY

	if oldCell == newCell {
		return // Tidak melewati batas cell, tidak ada manipulasi pointer grid
	}

	// Unlink dari oldCell
	if entity.Prev != InvalidIndex {
		g.pool[entity.Prev].Next = entity.Next
	} else {
		g.cells[oldCell] = entity.Next
	}

	if entity.Next != InvalidIndex {
		g.pool[entity.Next].Prev = entity.Prev
	}

	// Link ke newCell
	entity.PrevCell = newCell
	entity.Prev = InvalidIndex
	entity.Next = g.cells[newCell]

	if g.cells[newCell] != InvalidIndex {
		g.pool[g.cells[newCell]].Prev = poolIdx
	}
	g.cells[newCell] = poolIdx
}

// QueryAoI mencari seluruh entitas dalam radius observasi dengan alokasi buffer eksternal (Zero GC)
func (g *SpatialHashGrid) QueryAoI(centerX, centerY, radius float32, outBuffer []EntityID) int {
	g.mu.RLock()
	defer g.mu.RUnlock()

	minX := float32(math.Max(0, float64(centerX-radius)))
	maxX := float32(math.Min(float64(g.config.WorldWidth-1), float64(centerX+radius)))
	minY := float32(math.Max(0, float64(centerY-radius)))
	maxY := float32(math.Min(float64(g.config.WorldHeight-1), float64(centerY+radius)))

	startCol := uint32(minX / g.config.CellSize)
	endCol := uint32(maxX / g.config.CellSize)
	startRow := uint32(minY / g.config.CellSize)
	endRow := uint32(maxY / g.config.CellSize)

	count := 0
	maxCap := len(outBuffer)
	rSq := radius * radius

	for r := startRow; r <= endRow; r++ {
		rowOffset := r * g.config.Cols
		for c := startCol; c <= endCol; c++ {
			curr := g.cells[rowOffset+c]
			for curr != InvalidIndex {
				e := &g.pool[curr]
				dx := e.X - centerX
				dy := e.Y - centerY
				if (dx*dx + dy*dy) <= rSq {
					if count < maxCap {
						outBuffer[count] = e.ID
						count++
					} else {
						return count // Buffer jenuh, return hasil parsial
					}
				}
				curr = e.Next
			}
		}
	}
	return count
}
```

---

## 8. Real World Case Study: MMO Battle Arena Scalability Failure

### Skenario Insiden Produksi
Sebuah game aksi MMO terdistribusi meluncurkan event pertempuran massal di satu titik koordinat (World Boss Event). 
* **Arsitektur Awal**: Spatial Hash dinamis dengan ukuran sel kaku $50\text{m} \times 50\text{m}$.
* **Load**: $3.500$ pemain berkumpul dalam area $80\text{m} \times 80\text{m}$.
* **Dampak**: 
  1. Sekitar 80% dari total pemain jatuh ke dalam 4 sel yang sama.
  2. Komparasi per tick melonjak drastis pada sel tersebut: $\frac{3500 \times 3499}{2} \approx 6.12 \times 10^6$ interaksi fisik dan visibility raycast.
  3. Waktu pemrosesan tick melonjak dari 15ms menjadi 420ms (Tick Rate drop dari 30 Hz ke 2.3 Hz).
  4. Terjadi *cascade disconnect* akibat buffer TCP/UDP socket kernel meluap (*Receive/Send Queue saturation*).

### Investigasi & Root Cause
* Bucket data spasial mengalami degradasi menjadi linked list raksasa yang tidak terdistribusi secara seimbang.
* Interest Management mengevaluasi jarak tanpa batas maksimal entitas (*relevance saturation*), mencoba membroadcast 3.500 entitas ke setiap klien (3.500 × 3.500 = 12.25 juta update paket per detik).

### Solusi Remediasi Rekayasa
1. **Dynamic Quadtree Sub-clustering / Adaptive Cell Resizing**: Ketika entitas dalam satu sel melebihi ambang batas (*threshold* = 64 entitas), sel otomatis membagi dirinya menjadi 4 sub-sel secara rekursif hingga kedalaman maksimum tercapai.
2. **AoI Relevance Prioritization (Distance & FOV Decay)**: Mengimplementasikan filter hard-cap: Klien maksimal menerima status 50 entitas paling relevan.
   $$\text{Score} = w_1 \cdot \text{Distance} + w_2 \cdot \text{IsInCombat} + w_3 \cdot \text{IsPartyMember} + w_4 \cdot \cos(\theta_{\text{view}})$$
   Entitas dengan skor relevansi tertinggi mendapatkan prioritas alokasi bandwidth.
3. **Tick Budget Interleaving**: Entitas dengan jarak $> 60\text{m}$ diperbarui dengan frekuensi lebih rendah (5 Hz) menggunakan integrasi *dead-reckoning extrapolation*, sedangkan entitas dalam jarak pertempuran ($< 15\text{m}$) diperbarui penuh pada 30 Hz.

---

## 9. Trade-offs

| Pendekatan / Algoritma | Keuntungan | Kerugian & Batasan | Dampak Biaya Infrastruktur |
| :--- | :--- | :--- | :--- |
| **Flat Spatial Hash Grid** | Akses $O(1)$, zero memory allocation overhead jika di-pool, implementasi konkurensi berbasis RW-lock per sel sangat cepat. | Memori terbuang jika densitas dunia *sparse* (laut/gunung kosong tetap memakan alokasi sel). Terjadi degradasi performa jika entitas berkumpul di satu sel. | Sangat rendah. Menghemat resource CPU secara deterministik. |
| **Loose Hierarchical Octree** | Adaptif terhadap kluster entitas non-uniform (misal: dogfight luar angkasa). Menghindari komparasi redundan di ruang hampa. | Traversal rekursif menyebabkan *branch misprediction* pada CPU. Biaya pointer tinggi jika tidak dikemas dalam format DOD (*Linear Tree*). | Moderat. Membutuhkan CPU cycle lebih tinggi per query dibanding Direct Hashing. |
| **Distance-Only Hysteresis** | Implementasi ringan. Efektif mengeliminasi *network oscillation* pada tepi sensorik. | Tidak memperhitungkan oklusi lingkungan (misal: pemain di balik tembok tebal beton tetap dikirimkan ke klien). | Rendah secara komputasi, namun menyia-nyiakan bandwidth klien untuk target tak terlihat. |
| **Frustum + Dynamic Raycast Culling** | Menghemat bandwidth jaringan secara drastis (hingga 70%). Mencegah *wallhack cheat* karena entitas tersembunyi tidak dikirim ke klien. | Membebani performa CPU/GPU Dedicated Server secara masif untuk kalkulasi BVH ray tracing statis/dinamis. | Tinggi. Server membutuhkan alokasi compute instance yang jauh lebih mahal (Compute-Optimized Nodes). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Boundary Thrashing
* **Gejala**: Klien menerima paket `Spawn` dan `Despawn` puluhan kali per detik ketika berjalan di garis batas sel, menyebabkan model karakter berkedip (*flickering*) dan lonjakan bandwidth.
* **Solusi**: Terapkan Hysteresis:
  ```go
  // Misal: Masuk pada 45m, keluar hanya jika jarak > 55m
  const EnterAoIRadius = 45.0
  const LeaveAoIRadius = 55.0
  ```

### 10.2 Cache-Line False Sharing pada Paralelisasi Grid
* **Gejala**: Multithreading tick loop dengan Goroutine/Pthreads gagal mencapai *linear scaling*, CPU utilization 100% namun throughput stagnan.
* **Penyebab**: Entitas atau mutex sel-sel yang berdekatan disimpan dalam cache line CPU yang sama (64 byte), memicu protokol *cache coherency bus invalidation* terus-menerus.
* **Solusi**: Berikan *padding* pada struktur memori sel atau pisahkan state tulis (*write-state*) dari state baca (*read-state*):
  ```go
  type AlignedCell struct {
      HeadIndex uint32
      _padding  [60]byte // Pastikan ukuran struct kelipatan 64 bytes (1 cache line)
  }
  ```

### 10.3 Ghost Node Entity Desynchronization
* **Gejala**: Karakter berpindah antar server worker (node border), lalu menghilang dari dunia (*despawn forever*) atau terduplikasi menjadi dua entitas aktif (*split-brain*).
* **Solusi**: Terapkan protokol **Two-Phase Commit Handover**:
  1. *Node A* menandai entitas sebagai `MIGRATING_OUT`. Mencegah pemrosesan state baru, mengekspor snapshot state.
  2. *Node B* mengimpor snapshot, menginstansiasi entitas sebagai `MIGRATING_IN`.
  3. *Node B* mengirimkan ACK ke *Node A*.
  4. *Node A* menghapus state lokal secara atomik dan mengirimkan respons `FINAL_AUTHORITY` ke *Node B*.
  5. *Node B* mengubah status entitas menjadi `AUTHORITATIVE_ACTIVE`.

---

## 11. Best Practices (Production Checklist)

1. [ ] **Pre-allocate Pool Size**: Jangan pernah menggunakan dynamic resizing `append()` pada hot-path tick loop server.
2. [ ] **Profile Cache Miss Rates**: Ukur metrik L1 Data Cache Miss via `perf` (Linux) untuk loop traversal AoI:
   ```bash
   perf stat -e L1-dcache-load-misses,L1-dcache-loads ./gameserver
   ```
   Rasio miss harus ditekan di bawah 5%.
3. [ ] **Clamp Maximum Tracked Entities**: Berikan batasan absolut jumlah entitas maksimal yang bisa diobservasi oleh satu klien (misal: $K = 64$).
4. [ ] **Hysteresis Delta**: Tetapkan rasio delta radius keluar-masuk minimal sebesar 15–20% dari total radius pandang.
5. [ ] **Compress Bitmasks**: Gunakan bitset flat array untuk tracking *seen/unseen entities* per observer daripada struktur `map[uint64]bool`.
6. [ ] **Worker Boundary Safe Zones**: Pastikan lebar zona replikasi ghost minimal sama dengan kecepatan lari tercepat entitas dikalikan latensi *round-trip time* (RTT) terburuk ditambah margin keamanan $2\times$:
   $$\text{Margin Width} \ge V_{\max} \times (\text{RTT}_{\max} + \text{TickDelta}) \times 2$$

---

## 12. Hands-on Practice

Buat dan jalankan modul praktikum berorientasi performa pada direktori `hands-on/m02/`.

### Langkah 1: Setup Workspace & Struktur Folder
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init aoi-production
```

### Langkah 2: Implementasi Memory Pooled Spatial Engine
Buat berkas `engine.go`:
```go
package main

import (
	"fmt"
	"math/rand"
	"time"
)

type Entity struct {
	ID uint32
	X  float32
	Y  float32
}

func main() {
	fmt.Println("Menginisialisasi Spatial Engine Simulation...")
	const entityCount = 10000
	const worldSize = 2000.0
	const aoiRadius = 50.0

	// Alokasi statis array koordinat (DOD Structure-of-Arrays)
	xPositions := make([]float32, entityCount)
	yPositions := make([]float32, entityCount)

	for i := 0; i < entityCount; i++ {
		xPositions[i] = rand.Float32() * worldSize
		yPositions[i] = rand.Float32() * worldSize
	}

	outBuffer := make([]uint32, 256)

	// Simulasi 1 Tick Benchmark
	start := time.Now()
	
	// Implementasi linear sweep benchmark
	found := 0
	observerX := float32(1000.0)
	observerY := float32(1000.0)
	rSq := float32(aoiRadius * aoiRadius)

	for i := 0; i < entityCount; i++ {
		dx := xPositions[i] - observerX
		dy := yPositions[i] - observerY
		if (dx*dx + dy*dy) <= rSq {
			if found < len(outBuffer) {
				outBuffer[found] = uint32(i)
				found++
			}
		}
	}

	elapsed := time.Since(start)
	fmt.Printf("Sweep selesai dalam %v. Entitas terdeteksi: %d\n", elapsed, found)
}
```

### Langkah 3: Eksekusi Profiling
```bash
go run engine.go
go test -bench=. -benchmem
```

---

## 13. Exercises

### Tingkat: Easy
Implementasikan fungsi evaluasi jarak menggunakan **Manhattan Distance** ($|x_1 - x_2| + |y_1 - y_2|$) sebagai pre-filter cepat sebelum menjalankan kalkulasi Euclidean Distance berakar kuadrat $\sqrt{dx^2 + dy^2}$, lalu ukur perubahan latensinya.

### Tingkat: Medium
Modifikasi `SpatialHashGrid` pada bagian 7.2 untuk mendukung entitas berukuran dinamis (bounding radius bervariasi). Entitas dengan radius lebih besar dari ukuran sel grid harus secara aman dimasukkan ke beberapa sel yang tumpang-tindih (*multi-bucket registration*) tanpa menyebabkan duplikasi deteksi query.

### Tingkat: Hard
Rancang dan implementasikan **Bitset-Based Observer History Table**. Setiap entitas pengamat memiliki array bitset 64-bit:
* Bit bernilai `1`: Entitas target terlihat pada tick sebelumnya.
* Bit bernilai `0`: Entitas target belum terlihat.
Saat query AoI berjalan pada tick baru, gunakan operasi bitwise `AND`, `OR`, `XOR` untuk menghasilkan daftar entitas yang perlu dikirimi event `SpawnPacket`, `UpdatePacket`, dan `DespawnPacket` secara langsung tanpa alokasi memori dinamis (`0 allocs/op`).

---

## 14. Architecture Challenge

**Scenario**: Anda memimpin tim arsitektur teknis untuk game simulasi perang ruang angkasa masif (*Zoneless Seamless Space Warfare*).
* **Kebutuhan**: 1 Dunia tanpa loading screen, volume kubus 3D ($100.000\text{km} \times 100.000\text{km} \times 10.000\text{km}$).
* **Karakteristik Entitas**:
  - $50.000$ pesawat tempur kecil (kecepatan tinggi, radius persepsi $5\text{km}$).
  - $200$ stasiun luar angkasa raksasa dan mothership (kecepatan lambat/statis, radius radar $500\text{km}$).
* **Spesifikasi Mesin**: Sistem didistribusikan ke cluster Kubernetes (masing-masing worker mengelola partisi spasial tertentu).

**Tugas Arsitektur**:
1. Buat dokumen desain detail: Bagaimana struktur data spasial menangani perbedaan ekstrim pada radius observasi ($5\text{km}$ vs $500\text{km}$) tanpa merusak performa *small cells*?
2. Bagaimana mekanisme koordinasi antar worker node saat sebuah armada berpindah melintasi 3 node spasial terpisah secara bersamaan tanpa menimbulkan visual hitching pada klien?
3. Rancang format packet binary interest mask untuk menghemat konsumsi bandwidth jaringan outbound (Egress) di bawah 15 KB/s per klien dalam kondisi pertempuran sengit.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Berapa kompleksitas waktu komputasi pemrosesan kedekatan spasial antara seluruh entitas jika dilakukan tanpa teknik partisi spasial?**
   - A. $O(N)$
   - B. $O(N \log N)$
   - C. $O(N^2)$
   - D. $O(1)$
2. **Apa fungsi utama parameter kelonggaran (looseness factor, misal $k=2$) pada struktur Loose Quadtree?**
   - A. Menurunkan resolusi floating-point
   - B. Mencegah entitas yang berada di perbatasan sel dipaksa naik ke *root node*
   - C. Mempercepat kalkulasi physics raycast statis
   - D. Mengurangi alokasi CPU thread
3. **Mengapa implementasi Spatial Hash berbasis `map[int]map[int][]*Entity` tidak disarankan untuk game server high-performance di Golang atau C#?**
   - A. Syntax terlalu panjang
   - B. Menyebabkan alokasi objek dinamis masif di heap yang membebani Garbage Collector
   - C. Tidak mendukung komputasi floating-point
   - D. Menghasilkan race condition otomatis pada read-only thread
4. **Apa yang dimaksud dengan "Hysteresis" dalam konteks Area of Interest (AoI)?**
   - A. Mekanisme kompresi data rotasi quaternion
   - B. Pemisahan radius masuk (*enter*) dan radius keluar (*exit*) untuk mencegah osilasi event jaringan
   - C. Sinkronisasi jam fisik antara server dan klien
   - D. Algoritma enkripsi paket UDP menggunakan key dinamis
5. **Morton Code (Z-Order Curve) memetakan ruang multidimensi ke dalam ruang satu dimensi dengan cara...**
   - A. Menjumlahkan seluruh koordinat secara linear
   - B. Menginterleave (menyisipkan bergantian) representasi biner dari koordinat spasial
   - C. Mengalikan koordinat dengan bilangan prima besar
   - D. Mengonversi vektor float menjadi integer matrix

### Bagian 2: Intermediate (5 Pertanyaan)
6. **Pada arsitektur game multi-node, apa peran utama entitas "Ghost" (atau Shadow Proxy)?**
   - A. Menyimpan log data audit transaksi pemain ke database SQL
   - B. Entitas tiruan read-only di server tetangga untuk memvalidasi interaksi di perbatasan tanpa pemindahan otoritas langsung
   - C. Bot AI pengisi kekosongan ruang game
   - D. Karakter mati yang menunggu respawn cycle
7. **Dalam memory layout CPU, mengapa representasi linked list konvensional (menggunakan node pointer 64-bit) rentan menimbulkan degradasi performa pada tick loop spasial?**
   - A. Compiler menolak optimasi SIMD
   - B. Pointer chasing memicu banyak L1/L2 cache misses karena node tersebar acak di DRAM
   - C. Ukuran pointer terlalu kecil untuk 64-bit architecture
   - D. Menghabiskan alokasi stack memory
8. **Jika entitas berpindah dari koordinat $(12.1, 8.4)$ ke $(12.3, 8.6)$ pada grid dengan ukuran sel $50\text{m}$, operasi apa yang dilakukan pada Spatial Hash Grid yang optimal?**
   - A. Rebuild seluruh isi grid secara global
   - B. Memperbarui nilai koordinat X dan Y entitas tanpa manipulasi pointer linked list
   - C. Menghapus entitas lalu mengalokasikan entitas baru di heap
   - D. Menjalankan fungsi garbage collection secara paksa
9. **Kondisi apa yang menyebabkan ukuran cell pada Uniform Spatial Hash Grid menjadi tidak efisien?**
   - A. Semua entitas terdistribusi secara seragam di seluruh peta
   - B. Entitas sangat dinamis dan berpindah setiap frame
   - C. Terjadi pengelompokan ekstrim (*heavy clustering*) di mana ribuan entitas berkumpul di satu area kecil yang sama
   - D. Kecepatan tick server dinaikkan dari 30 Hz ke 60 Hz
10. **Metrik jaringan mana yang secara langsung dihemat paling banyak dengan penerapan Interest Management yang ketat?**
    - A. Round-Trip Time (RTT) fisik fiber optic
    - B. Outbound Bandwidth / Egress Traffic Server
    - C. MTU size packet
    - D. IP Packet Header Size

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario Kasus 1**:  
    Sistem game Anda menggunakan dedicated worker terpisah untuk mengelola physics dan interest management. Saat evaluasi beban server pada 10.000 entitas, latency tick melonjak secara eksponensial. Profiling CPU menunjukkan 65% waktu terbuang pada fungsi `runtime.mallocgc` dan `runtime.scanobject`. Setelah ditelusuri, sistem spatial query menghasilkan array baru `[]*Entity` di setiap tick untuk setiap pemain.  
    *Tindakan arsitektural apa yang paling tepat untuk mengeliminasi masalah ini secara permanen tanpa mengubah bahasa pemrograman?*

12. **Skenario Kasus 2**:  
    Pada game penembak taktis (Tactical Shooter), sistem Interest Management hanya mengandalkan perhitungan jarak Euclidean 2D ($R = 60\text{m}$). Pemain melaporkan maraknya penggunaan program ilegal (*radar hack*) yang mampu mendeteksi musuh di balik tembok tebal beton pada jarak $30\text{m}$.  
    *Perubahan arsitektur spasial server apa yang harus diterapkan untuk menutup celah informasi ini dengan tetap menjaga performa server?*

13. **Skenario Kasus 3**:  
    Server game MMO Open-World membagi dunia menjadi grid server cluster berukuran $1\text{km} \times 1\text{km}$ per node server fisik. Seorang pemain menembakkan roket berkecepatan $200\text{m/s}$ melintasi perbatasan dari Server Node 1 ke Server Node 2. Di layar klien, roket terlihat berhenti mendadak selama 200ms di perbatasan sebelum tiba-tiba muncul dan meledak di Server Node 2.  
    *Analisis penyebab kegagalan pipeline ini dan jelaskan solusi sinkronisasinya.*

---

### Kunci Jawaban & Rasional Evaluasi

#### Bagian 1 & 2
1. **C** - Setiap entitas harus dicek terhadap seluruh entitas lain: $N \times (N - 1) / 2 \implies O(N^2)$.
2. **B** - Loose Quadtree memperlebar batas bounding box node internal, sehingga objek yang melintasi garis tengah tetap tertampung di level child node.
3. **B** - Map bersarang dan dynamic slice pointer memicu ribuan alokasi kecil yang harus dilacak dan dibersihkan oleh Garbage Collector, memicu lonjakan latensi STW.
4. **B** - Hysteresis membedakan jarak *acquire* vs *release* target untuk meredam osilasi add/remove interest event.
5. **B** - Bit interleaving menyisipkan bit-bit biner antar dimensi sehingga mengonversi koordinat 2D/3D ke 1D secara lokal.
6. **B** - Ghost proxy mereplikasi data transenden dari server tetangga agar sistem lokal (AoI dan Physics) dapat berinteraksi tanpa menunggu migrasi kepemilikan.
7. **B** - Linked list berbasis pointer melompat-lompat di alamat RAM acak, mengakibatkan CPU pipeline terhenti (*cache stall*) menunggu data dari DRAM.
8. **B** - Karena ukuran sel 50m, perpindahan dari (12.1, 8.4) ke (12.3, 8.6) masih berada dalam sel yang sama; tidak perlu modifikasi pointer bucket sama sekali.
9. **C** - Distribusi data yang sangat timpang membuat satu bucket membesar tak terkendali, mendegradasi spatial hash menjadi pencarian linear $O(N)$.
10. **B** - Mengeliminasi pengiriman state paket entitas yang tidak relevan secara signifikan menurunkan konsumsi data outbound (egress).

#### Bagian 3 (Skenario Produksi)
11. **Rasional Solusi Kasus 1**:
    Alokasi memori dinamis harus dihilangkan sepenuhnya dari hot path loop. Solusinya:
    - Gunakan **Pre-allocated Flat Memory Buffer** (atau *Memory Pooling* via `sync.Pool`).
    - Modifikasi fungsi query spasial agar menerima *slice buffer* yang dialokasikan di awal (disediakan oleh caller) alih-alih me-return slice baru: `func Query(..., outBuf []EntityID) int`.
    - Simpan entitas dalam bentuk array contiguous bertipe ID numerik murni alih-alih pointer objek (`*Entity`). Hal ini memangkas kerja GC root-scanning hingga 99%.
12. **Rasional Solusi Kasus 2**:
    Jarak Euclidean murni tidak memverifikasi jalur visibilitas. Langkah mitigasi:
    - Integrasikan **Static Occlusion / Potentially Visible Set (PVS)** atau **Raycast Visibility Culling** pada tahap *narrow-phase* interest management.
    - Sebelum broadcast state target ke observer, tembakkan *line-of-sight raycast* terhadap sistem partisi statis dunia (BVH dari map collider). Jika terhalang dinding tanpa pintu, entitas dikeluarkan dari daftar update jaringan untuk klien tersebut, mencegah data jatuh ke memori RAM klien hacker.
13. **Rasional Solusi Kasus 3**:
    Masalah ini adalah akibat *Handoff Latency Stall*—proses serah-terima kepemilikan (*authority transfer*) roket terlambat diproses saat roket menyentuh batas sel. Solusinya:
    - Terapkan **Proactive Ghost Replication Boundary**. Roket di Server 1 harus sudah di-ghosting di Server 2 ketika berada dalam jarak $X$ meter menjelang perbatasan ($X \ge V \times \text{RTT}$).
    - Ketika melintasi garis perbatasan secara tepat, transfer otoritas cukup membalik bendera flag dari `Ghost` menjadi `Authoritative Master` di Node 2 tanpa perlu deserialisasi objek baru dari awal, menghilangkan jeda visual hitching.

---

## 16. Summary

* **Kompleksitas Spasial**: Mengabaikan partisi spasial akan membatasi kapasitas game pada kompleksitas $O(N^2)$. Struktur data terpartisi mereduksi komparasi secara deterministik menjadi level yang terukur.
* **Arsitektur Memori**: Pilihan struktur data harus selaras dengan arsitektur hardware modern (*Data-Oriented Design*). Struktur flat array dengan spatial index (seperti Morton Grid) lebih unggul daripada struktur data berbasis pointer dinamis dalam hal *CPU cache hits* dan eliminasi *GC pressure*.
* **Stabilitas Jaringan**: Interest Management bukan sekadar pemotongan jarak; sistem memerlukan **Hysteresis**, **Relevance Priority Culling**, dan **Ghost Proxying Cross-Boundary** untuk mempertahankan kestabilan gameplay, efisiensi bandwidth jaringan, dan integritas visual multi-node game terdistribusi skala industri.