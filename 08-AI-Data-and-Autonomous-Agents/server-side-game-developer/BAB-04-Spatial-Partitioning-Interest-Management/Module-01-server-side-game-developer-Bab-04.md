# Bab 04: Spatial Partitioning & Interest Management
## Module 01: Fondasi Spatial Partitioning & Area of Interest (AoI) Engine

---

### 1. Learning Objectives (Spesifik & Terukur)
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Memilih Struktur Data Spasial**: Mengidentifikasi trade-off komputasi antara *Uniform Grid*, *Sparse Spatial Hashing*, *Quadtree/Octree*, dan *Bounding Volume Hierarchy (BVH)* berdasarkan profil densitas entitas dinamis (homogen vs. klaster hiper-padat).
- **Mengimplementasikan Spatial Hash Grid $O(1)$**: Membangun sistem partisi spasial berbasis *sparse hashing* berkinerja tinggi dalam bahasa Go dengan alokasi memori mendekati nol (*zero-allocation steady state*).
- **Membangun Area of Interest (AoI) Subscription Engine**: Merancang subsistem manajemen visibilitas entitas yang memisahkan peran *Observer* dan *Subject*, serta memitigasi kompleksitas *broadcasting* dari $O(N^2)$ menjadi $O(N \cdot M)$ di mana $M \ll N$.
- **Menerapkan Algoritma Hysteresis Buffer**: Mengeliminasi fenomena *boundary thrashing* (osilasi *subscribe/unsubscribe* berulang) pada entitas yang bergerak bolak-balik di garis batas partisi spasial.
- **Mengintegrasikan Sistem Persepsi AI Otonom**: Menyediakan pipeline *spatial query* deterministik berlatensi rendah ($< 2\text{ ms}$ pada tick rate 30 Hz untuk 10.000 entitas) yang melayani *sensing sub-system* dari *autonomous agents*.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Di dalam arsitektur *authoritative game server* dan simulasi agen otonom berskala masif, tantangan komputasi paling destruktif adalah masalah interaksi $N$-ke-$N$ ($O(N^2)$). Jika sebuah dunia virtual menampung $N$ entitas dan setiap entitas harus mengevaluasi status $N-1$ entitas lainnya pada setiap *tick* simulasi (untuk persepsi AI, deteksi tabrakan, atau replikasi state jaringan), beban komputasi melonjak secara kuadratik.

```
N = 1.000 entitas   =>      1.000.000 evaluasi/tick
N = 10.000 entitas  =>    100.000.000 evaluasi/tick
N = 50.000 entitas  =>  2.500.000.000 evaluasi/tick  --> Server Crash (CPU Starvation)
```

**Spatial Partitioning** memecah ruang koordinat kontinu 2D/3D menjadi sub-ruang diskret. Dengan mengindeks entitas ke dalam partisi-partisi ini, agen AI atau *observer* hanya perlu mengevaluasi entitas yang berada di partisi yang sama atau partisi tetangga (*neighboring cells*).

**Interest Management (IM)** adalah lapisan abstraksi di atas partisi spasial yang mengatur relevansi data. IM menentukan:
1. Siapa yang perlu melihat apa (*Network Replication Filtering*).
2. Entitas apa saja yang dapat dideteksi oleh sensor persepsi agen AI (*Perception Radius Filtering*).

#### Model Mental: Observer vs. Subject
Dalam Interest Management, setiap entitas dapat memiliki dua peran yang terisolasi:
- **Subject**: Objek di dunia yang memiliki representasi fisik spasial (posisi, rotasi, ukuran) dan memancarkan pembaruan status (*state updates*).
- **Observer**: Objek yang memiliki sensor persepsi (kamera pemain, sistem penglihatan/pendengaran bot) dengan radius pandang diskret. Observer berlangganan (*subscribe*) ke Subject di sekitarnya.

```
+-------------------------------------------------------------------+
|                        WORLD COORDINATES                          |
|                                                                   |
|   [Cell 0,0]              [Cell 1,0]              [Cell 2,0]     |
|   +---------------+       +---------------+       +-----------+   |
|   |  Subject A    |       |  Observer B   |       |           |   |
|   |  (Position)   |<......|  (AoI Radius) |       |           |   |
|   +---------------+       +-------+-------+       +-----------+   |
|                                   :                               |
|   [Cell 0,1]              [Cell 1,1]              [Cell 2,1]     |
|   +---------------+       +-------:-------+       +-----------+   |
|   |               |       |  Subject C    |       |           |   |
|   |               |       |  (Position)   |       |           |   |
|   +---------------+       +---------------+       +-----------+   |
+-------------------------------------------------------------------+
   Observer B melihat Subject A dan C, mengabaikan Cell di luar jangkauan.
```

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada game MMO (*Massively Multiplayer Online*), *open-world survival*, atau simulasi agen autonomous berskala enterprise, sumber daya jaringan (*bandwidth egress*) dan siklus CPU server adalah batasan terberat.

1. **Bandwidth Saturation**: Jika 2.000 bot mengirimkan pembaruan transform (posisi, rotasi, kecepatan: ~64 byte) tanpa IM pada 30 Hz:
   $$\text{Egress} = 2.000 \times 2.000 \times 64\text{ bytes} \times 30\text{ Hz} \approx 7.68\text{ GB/detik} \ (61.44\text{ Gbps})$$
   Kondisi ini memicu saturasi kartu jaringan (*NIC saturation*) dan pembengkakan biaya infrastruktur cloud. Melalui implementasi AoI, rata-rata subjek yang relevan per observer berkurang menjadi ~50 entitas:
   $$\text{Egress} = 2.000 \times 50 \times 64\text{ bytes} \times 30\text{ Hz} \approx 192\text{ MB/detik} \ (1.53\text{ Gbps})$$
   Pengurangan volume bandwidth mencapai **97.5%**.

2. **AI Perception Optimization**: Autonomous agent yang digerakkan oleh Behavior Trees atau Utility AI mengeksekusi *environmental queries* ("Cari musuh terdekat", "Cari tempat berlindung"). Jika sistem persepsi memindai seluruh *entity array*, *cache miss* pada memori L1/L2 melonjak drastis, mengakibatkan *CPU stall* yang menjatuhkan *tick rate* server dari 60 Hz ke angka di bawah 10 Hz.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur sistem manajemen spasial terisolasi dari *physics engine* murni dan bertindak sebagai *middleware* antara *Entity Component System (ECS)*, *Perception Subsystem*, dan *Packet Replication Engine*.

```
+---------------------------------------------------------------------------------------+
|                                    GAME TICK LOOP                                     |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                                 SPATIAL ENGINE CORE                                   |
|                                                                                       |
|  +-------------------------+             +-----------------------------------------+  |
|  |     Grid Coordinator    |             |             Hysteresis State            |  |
|  |  - Computes Cell Keys   |             |  - Inner Radius (Enter AoI)             |  |
|  |  - Spatial Hash Table   |             |  - Outer Radius (Leave AoI)             |  |
|  +------------+------------+             +--------------------+--------------------+  |
|               |                                               |                       |
|               v                                               v                       |
|  +-------------------------+                     +---------------------------+        |
|  |   Spatial Hash Cells    |                     |      Subscription Set     |        |
|  |   (Buckets of EntityID) |-------------------->|    (Observer -> Subjects) |        |
|  +-------------------------+                     +-------------+-------------+        |
+----------------------------------------------------------------|----------------------+
                                                                 |
               +-------------------------------------------------+-------------------------------------------------+
               |                                                                                                   |
               v                                                                                                   v
+-----------------------------------------------+                                   +-----------------------------------------------+
|         AI PERCEPTION SUBSYSTEM               |                                   |          NETWORK REPLICATION ENGINE           |
|  - Queries visible agents within radius       |                                   |  - Serializes delta state                     |
|  - Feeds stimuli into Behavior Trees          |                                   |  - Packs UDP replication packets              |
|  - Triggers aggro/evasion behaviors           |                                   |  - Sends packets ONLY to subscribed clients   |
+-----------------------------------------------+                                   +-----------------------------------------------+
```

#### Struktur Alur Data pada Mutasi Entitas
```
[Entity Moves] ---> [Spatial Engine: UpdatePosition()]
                          |
                          v
         [Hash Key Changed? (OldCell != NewCell)]
                    /                 \
                 [YES]                [NO]
                  /                     \
                 v                       v
      [Remove from Old Cell]     [Update Internal Coordinates]
      [Insert into New Cell]             |
                 |                       v
                 v            [Query Nearby Observers]
   [Recalculate AoI Differences]         |
   - Emit OnEntityEnteredAoI             v
   - Emit OnEntityLeftAoI     [Notify Subscribed Observers]
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Spatial Hashing Berbasis Grid 2D/3D
Ruang kontinu dipetakan ke dalam cell grid diskret berukuran $S$. Untuk posisi sembarang $(x, y, z)$, indeks grid dihitung dengan pembagian berbasis *floor*:

$$c_x = \lfloor x / S \rfloor, \quad c_y = \lfloor y / S \rfloor, \quad c_z = \lfloor z / S \rfloor$$

Untuk memetakan koordinat sel integer $(c_x, c_y, c_z)$ ke indeks array satu dimensi atau hash map tanpa alokasi string, digunakan fungsi hash non-linear bilangan prima besar (*prime hashing*):

$$\text{Hash}(c_x, c_y, c_z) = \Big( (c_x \cdot p_1) \oplus (c_y \cdot p_2) \oplus (c_z \cdot p_3) \Big) \pmod M$$

Di mana $p_1 = 73856093$, $p_2 = 19349663$, $p_3 = 83492791$, dan $M$ adalah kapasitas bucket array.

#### B. Hysteresis Buffer untuk Mengatasi Boundary Thrashing
Masalah krusial pada sistem AoI berbasis radius murni adalah entitas yang berhenti atau bergerak bolak-balik tepat di batas luar radius pengamatan. Hal ini memicu rentetan *Enter/Leave events* pada setiap tick:

```
Tick N:   Dist = 20.01m -> Entity Leaves AoI (Send Despawn Packet)
Tick N+1: Dist = 19.99m -> Entity Enters AoI (Send Full Spawn Packet)
Tick N+2: Dist = 20.01m -> Entity Leaves AoI (Send Despawn Packet)
```
Kondisi ini memboroskan alokasi bandwidth dan CPU (*thrashing*). 

Solusi enterprise menggunakan dua ambang batas radius (**Dual-Threshold Hysteresis**):
- **$R_{\text{enter}}$ (Inner Radius)**: Jarak di mana subjek *mulai* dianggap terlihat dan masuk ke dalam himpunan visibilitas observer.
- **$R_{\text{leave}}$ (Outer Radius)**: Jarak di mana subjek *keluar* dari himpunan visibilitas observer, di mana $R_{\text{leave}} = R_{\text{enter}} + \Delta_{\text{margin}}$.

```
               [Observer Center]
                      |
                      v
 ( . . . . . . . . . (o) . . . . . . . . . )   <-- R_enter (misal: 50m)
( . . . . . . . . . . . . . . . . . . . . . )  <-- R_leave (misal: 60m)
                     |---|
                       ^
                 Hysteresis Margin (10m)
```
- Entitas yang belum terlihat harus menembus $R_{\text{enter}} \le 50\text{ m}$ untuk memicu event `Enter`.
- Entitas yang sudah terlihat baru memicu event `Leave` jika jaraknya melebihi $R_{\text{leave}} > 60\text{ m}$.
- Di antara $50\text{ m}$ dan $60\text{ m}$, status tidak berubah.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi lengkap Spatial Partitioning Grid dan Interest Management Engine berbasis Go. Kode ini dirancang thread-safe, minim alokasi memori, serta mendukung hysteresis buffer.

```go
// Package spatial menyediakan engine partisi spasial dan manajemen Area of Interest (AoI).
package spatial

import (
	"math"
	"sync"
)

// EntityID merepresentasikan identifier unik dari setiap entitas game.
type EntityID uint64

// Vector3 merepresentasikan koordinat 3D pada ruang kontinu authoritatif.
type Vector3 struct {
	X float64
	Y float64
	Z float64
}

// DistanceSquared menghitung kuadrat jarak Euclidean untuk menghindari pemanggilan math.Sqrt yang mahal.
func (v Vector3) DistanceSquared(other Vector3) float64 {
	dx := v.X - other.X
	dy := v.Y - other.Y
	dz := v.Z - other.Z
	return dx*dx + dy*dy + dz*dz
}

// CellCoord mendefinisikan koordinat integer sel diskret dalam partisi grid.
type CellCoord struct {
	X int32
	Y int32
	Z int32
}

// EntityRecord menyimpan data spasial dan konfigurasi observasi entitas.
type EntityRecord struct {
	ID                 EntityID
	Position           Vector3
	IsObserver         bool
	EnterRadiusSquared float64
	LeaveRadiusSquared float64
	CurrentCell        CellCoord
}

// AoIEvent merepresentasikan perubahan visibilitas antar-entitas.
type AoIEventType uint8

const (
	EventEntityEntered AoIEventType = iota
	EventEntityLeft
)

type AoIEvent struct {
	Type     AoIEventType
	Observer EntityID
	Subject  EntityID
}

// SpatialHashGrid mengelola partisi sel dan pendaftaran entitas.
type SpatialHashGrid struct {
	cellSize float64
	mu       sync.RWMutex
	cells    map[CellCoord]map[EntityID]struct{}
	entities map[EntityID]*EntityRecord

	// Visibility tracking: observerID -> set of currently visible subjectIDs
	visibilityMap map[EntityID]map[EntityID]struct{}
}

// NewSpatialHashGrid menginisialisasi instans grid spasial baru.
func NewSpatialHashGrid(cellSize float64) *SpatialHashGrid {
	if cellSize <= 0.0 {
		cellSize = 10.0
	}
	return &SpatialHashGrid{
		cellSize:      cellSize,
		cells:         make(map[CellCoord]map[EntityID]struct{}),
		entities:      make(map[EntityID]*EntityRecord),
		visibilityMap: make(map[EntityID]map[EntityID]struct{}),
	}
}

// worldToCell mengonversi koordinat dunia kontinu ke koordinat sel diskret.
func (grid *SpatialHashGrid) worldToCell(pos Vector3) CellCoord {
	return CellCoord{
		X: int32(math.Floor(pos.X / grid.cellSize)),
		Y: int32(math.Floor(pos.Y / grid.cellSize)),
		Z: int32(math.Floor(pos.Z / grid.cellSize)),
	}
}

// RegisterEntity mendaftarkan entitas baru ke dalam spatial system.
func (grid *SpatialHashGrid) RegisterEntity(
	id EntityID,
	initialPos Vector3,
	isObserver bool,
	enterRadius float64,
	hysteresisMargin float64,
) {
	grid.mu.Lock()
	defer grid.mu.Unlock()

	leaveRadius := enterRadius + hysteresisMargin
	cell := grid.worldToCell(initialPos)

	record := &EntityRecord{
		ID:                 id,
		Position:           initialPos,
		IsObserver:         isObserver,
		EnterRadiusSquared: enterRadius * enterRadius,
		LeaveRadiusSquared: leaveRadius * leaveRadius,
		CurrentCell:        cell,
	}

	grid.entities[id] = record

	// Tambahkan ke bucket sel
	if _, exists := grid.cells[cell]; !exists {
		grid.cells[cell] = make(map[EntityID]struct{})
	}
	grid.cells[cell][id] = struct{}{}

	if isObserver {
		grid.visibilityMap[id] = make(map[EntityID]struct{})
	}
}

// UnregisterEntity menghapus entitas secara permanen dari grid dan visibilitas.
func (grid *SpatialHashGrid) UnregisterEntity(id EntityID) []AoIEvent {
	grid.mu.Lock()
	defer grid.mu.Unlock()

	var events []AoIEvent
	record, exists := grid.entities[id]
	if !exists {
		return events
	}

	// Hapus dari sel aktif
	if cellEntities, ok := grid.cells[record.CurrentCell]; ok {
		delete(cellEntities, id)
		if len(cellEntities) == 0 {
			delete(grid.cells, record.CurrentCell)
		}
	}

	// Jika ini adalah observer, buat event Left untuk semua subject yang saat ini dipantau
	if record.IsObserver {
		if visibleSubjects, ok := grid.visibilityMap[id]; ok {
			for subjectID := range visibleSubjects {
				events = append(events, AoIEvent{
					Type:     EventEntityLeft,
					Observer: id,
					Subject:  subjectID,
				})
			}
			delete(grid.visibilityMap, id)
		}
	}

	// Jika entitas adalah subject yang sedang diamati oleh observer lain
	for observerID, subjects := range grid.visibilityMap {
		if _, watching := subjects[id]; watching {
			delete(subjects, id)
			events = append(events, AoIEvent{
				Type:     EventEntityLeft,
				Observer: observerID,
				Subject:  id,
			})
		}
	}

	delete(grid.entities, id)
	return events
}

// UpdatePosition memperbarui posisi fisik entitas dan mengembalikan selisih event AoI.
func (grid *SpatialHashGrid) UpdatePosition(id EntityID, newPos Vector3) []AoIEvent {
	grid.mu.Lock()
	defer grid.mu.Unlock()

	var events []AoIEvent

	record, exists := grid.entities[id]
	if !exists {
		return events
	}

	oldCell := record.CurrentCell
	newCell := grid.worldToCell(newPos)
	record.Position = newPos

	// Jika entitas berpindah sel diskret, perbarui mapping sel
	if oldCell != newCell {
		if oldBucket, ok := grid.cells[oldCell]; ok {
			delete(oldBucket, id)
			if len(oldBucket) == 0 {
				delete(grid.cells, oldCell)
			}
		}

		if _, ok := grid.cells[newCell]; !ok {
			grid.cells[newCell] = make(map[EntityID]struct{})
		}
		grid.cells[newCell][id] = struct{}{}
		record.CurrentCell = newCell
	}

	// Evaluasi AoI jika entitas adalah Observer
	if record.IsObserver {
		observerEvents := grid.evaluateObserverAoI(record)
		events = append(events, observerEvents...)
	}

	// Evaluasi Observer lain yang memantau entitas ini sebagai Subject
	subjectEvents := grid.evaluateSubjectForObservers(record)
	events = append(events, subjectEvents...)

	return events
}

// evaluateObserverAoI mengecek area sekitar untuk observer yang bergerak.
func (grid *SpatialHashGrid) evaluateObserverAoI(observer *EntityRecord) []AoIEvent {
	var events []AoIEvent
	currentVisibles := grid.visibilityMap[observer.ID]

	// Tentukan radius sel yang perlu di-query berdasarkan leave radius
	maxRadius := math.Sqrt(observer.LeaveRadiusSquared)
	cellSpan := int32(math.Ceil(maxRadius / grid.cellSize))

	candidates := make(map[EntityID]struct{})

	// Kumpulkan kandidat dari sel tetangga
	for dx := -cellSpan; dx <= cellSpan; dx++ {
		for dy := -cellSpan; dy <= cellSpan; dy++ {
			for dz := -cellSpan; dz <= cellSpan; dz++ {
				targetCell := CellCoord{
					X: observer.CurrentCell.X + dx,
					Y: observer.CurrentCell.Y + dy,
					Z: observer.CurrentCell.Z + dz,
				}
				if bucket, found := grid.cells[targetCell]; found {
					for candidateID := range bucket {
						if candidateID != observer.ID {
							candidates[candidateID] = struct{}{}
						}
					}
				}
			}
		}
	}

	// Evaluasi kriteria Hysteresis untuk kandidat
	for candidateID := range candidates {
		target, ok := grid.entities[candidateID]
		if !ok {
			continue
		}

		distSq := observer.Position.DistanceSquared(target.Position)
		_, isAlreadyVisible := currentVisibles[candidateID]

		if isAlreadyVisible {
			// Masih dalam pengamatan kecuali melewati batas outer radius
			if distSq > observer.LeaveRadiusSquared {
				delete(currentVisibles, candidateID)
				events = append(events, AoIEvent{
					Type:     EventEntityLeft,
					Observer: observer.ID,
					Subject:  candidateID,
				})
			}
		} else {
			// Belum terlihat, hanya masuk jika menembus inner radius
			if distSq <= observer.EnterRadiusSquared {
				currentVisibles[candidateID] = struct{}{}
				events = append(events, AoIEvent{
					Type:     EventEntityEntered,
					Observer: observer.ID,
					Subject:  candidateID,
				})
			}
		}
	}

	// Evaluasi entitas yang sebelumnya terlihat namun sekarang berada di luar jangkauan sel kandidat
	for visibleID := range currentVisibles {
		if _, isCandidate := candidates[visibleID]; !isCandidate {
			delete(currentVisibles, visibleID)
			events = append(events, AoIEvent{
				Type:     EventEntityLeft,
				Observer: observer.ID,
				Subject:  visibleID,
			})
		}
	}

	return events
}

// evaluateSubjectForObservers mengevaluasi ulang relasi ketika Subject bergerak.
func (grid *SpatialHashGrid) evaluateSubjectForObservers(subject *EntityRecord) []AoIEvent {
	var events []AoIEvent

	for observerID, visibleSet := range grid.visibilityMap {
		if observerID == subject.ID {
			continue
		}

		observer, exists := grid.entities[observerID]
		if !exists {
			continue
		}

		distSq := observer.Position.DistanceSquared(subject.Position)
		_, isVisible := visibleSet[subject.ID]

		if isVisible {
			if distSq > observer.LeaveRadiusSquared {
				delete(visibleSet, subject.ID)
				events = append(events, AoIEvent{
					Type:     EventEntityLeft,
					Observer: observerID,
					Subject:  subject.ID,
				})
			}
		} else {
			if distSq <= observer.EnterRadiusSquared {
				visibleSet[subject.ID] = struct{}{}
				events = append(events, AoIEvent{
					Type:     EventEntityEntered,
					Observer: observerID,
					Subject:  subject.ID,
				})
			}
		}
	}

	return events
}

// QueryRadius mengambil semua entitas di dalam radius tertentu tanpa memengaruhi status AoI internal.
func (grid *SpatialHashGrid) QueryRadius(center Vector3, radius float64) []EntityID {
	grid.mu.RLock()
	defer grid.mu.RUnlock()

	var results []EntityID
	radiusSq := radius * radius
	cellSpan := int32(math.Ceil(radius / grid.cellSize))
	centerCell := grid.worldToCell(center)

	for dx := -cellSpan; dx <= cellSpan; dx++ {
		for dy := -cellSpan; dy <= cellSpan; dy++ {
			for dz := -cellSpan; dz <= cellSpan; dz++ {
				targetCell := CellCoord{
					X: centerCell.X + dx,
					Y: centerCell.Y + dy,
					Z: centerCell.Z + dz,
				}
				if bucket, found := grid.cells[targetCell]; found {
					for entityID := range bucket {
						entity := grid.entities[entityID]
						if entity.Position.DistanceSquared(center) <= radiusSq {
							results = append(results, entityID)
						}
					}
				}
			}
		}
	}

	return results
}
```

---

### 7. Edge Cases & Failure Modes

#### 1. Hotspot Collapse (The "Flash Mob" Problem)
- **Skenario Kegagalan**: Ribuan entitas (misal: event pertarungan massal) berkumpul di koordinat yang sama persis sehingga jatuh ke dalam satu cell grid yang identik.
- **Dampak**: Mekanisme partisi spasial terdegradasi menjadi $O(N^2)$. Kompleksitas hashing tidak memberi keuntungan karena seluruh pemindaian bermuara pada satu bucket tunggal, memicu lonjakan latensi tick dari $1\text{ ms}$ menjadi $500\text{ ms}$.
- **Mitigasi**: 
  - Terapkan **Density Throttling**: Batasi jumlah maksimum entitas yang diproses per sel per frame.
  - Implementasikan **Hierarchical Dynamic Sub-gridding**: Pecah sel menjadi *sub-cells* berukuran lebih kecil secara dinamis saat kepadatan entitas melampaui batas ambang tertentu ($N_{\text{threshold}} > 128$).

#### 2. High-Velocity Tunneling Across Multiple Cells
- **Skenario Kegagalan**: Entitas bergerak sangat cepat (misal: teleportasi atau peluru artileri berkecepatan $5.000\text{ m/s}$) melintasi beberapa sel dalam interval 1 frame ($33.3\text{ ms}$).
- **Dampak**: Observer di sel-sel perantara tidak pernah mendeteksi keberadaan entitas (*missed trigger*), merusak logika aggro AI dan deteksi tabrakan proyektil.
- **Mitigasi**: Gunakan **Raymarching / Bresenham's Line Algorithm 3D** untuk mengiterasi seluruh sel yang dilalui lintasan vektor $\vec{v} = P_{\text{new}} - P_{\text{old}}$, memicu validasi parsial pada setiap sel yang dilintasi secara sekuensial.

#### 3. Mutex Contention pada Tick Multi-Threaded
- **Skenario Kegagalan**: Ratusan thread AI agent memanggil `UpdatePosition` secara serentak pada global mutex `SpatialHashGrid.mu`.
- **Dampak**: CPU thread mengalami *lock contention* tinggi, menurunkan utilisasi multi-core CPU.
- **Mitigasi**: Gunakan arsitektur **Striped Locking** atau **Spatial Lock Sharding**, di mana setiap area kuadran dunia memiliki mutex independen, atau terapkan pendekatan pembaruan posisi berbasis pesan (*actor/message queue* via Go channel).

---

### 8. Trade-offs & Alternatif Solusi

| Parameter | Uniform Spatial Hash Grid | Pointer-based Quadtree/Octree | Dynamic Bounding Volume Hierarchy (BVH) |
| :--- | :--- | :--- | :--- |
| **Biaya Insert/Move** | $\mathcal{O}(1)$ | $\mathcal{O}(\log N)$ | $\mathcal{O}(\log N)$ hingga $\mathcal{O}(N)$ jika rebalance |
| **Biaya Query Radius** | $\mathcal{O}(K)$ ($K$ = isi tetangga) | $\mathcal{O}(\log N + K)$ | $\mathcal{O}(\log N + K)$ |
| **Kesesuaian Distribusi**| Paling optimal untuk distribusi merata | Optimal untuk klaster padat & renggang | Optimal untuk objek dengan variasi ukuran ekstrem |
| **Memory Footprint** | Rendah (hanya alokasi sel aktif) | Tinggi (overhead node pointer & re-alloc) | Sedang hingga Tinggi |
| **Cache Locality** | Sangat Tinggi (Flat Array/Flat Hash) | Buruk (Pointer chasing ke heap memori) | Sedang |
| **Kompleksitas Kode** | Rendah - Menengah | Menengah | Tinggi |

#### Kapan Memilih Solusi Alternatif?
- Gunakan **BVH**: Jika ukuran entitas di dunia memiliki disparitas masif (misal: pesawat luar angkasa raksasa berukuran $2\text{ km}$ berinteraksi dengan drone berukuran $1\text{ m}$). Uniform grid gagal mengelola entitas raksasa secara efisien karena entitas tersebut akan tumpang tindih dengan ratusan sel sekaligus.
- Gunakan **Quadtree**: Jika dunia game sangat luas namun densitas entitasnya sangat tidak merata (misalnya $90\%$ area kosong, dan hanya ada 2 kota besar yang padat).

---

### 9. Best Practices & Standar Industri

1. **Zero-Allocation Memory Reuse**:
   Dalam loop game berkecepatan 30-60 Hz, garbage collector (GC) dapat memicu *frame drop*. Hindari membuat slice sementara `[]AoIEvent` secara terus-menerus. Gunakan *pre-allocated fixed ring buffers* atau `sync.Pool` untuk menampung event slice yang didaur ulang setiap akhir tick.

2. **Decoupled Spatial Tick Rate**:
   Jangan jalankan pembaruan AoI pada frekuensi yang sama dengan simulasi fisika lokal. Fisika berjalan pada 50 Hz atau 60 Hz, sementara Interest Management cukup diperbarui pada 10 Hz atau 15 Hz. Sistem persepsi AI dan sinkronisasi jaringan mentolerir sedikit latensi propagasi (~66 ms) yang secara drastis menghemat siklus komputasi server.

3. **Metrics & Telemetry Essentials**:
   Pantau metrik server berikut di dashboard analitik (misal: Prometheus & Grafana):
   - `spatial_entities_count`: Total entitas aktif yang terindeks.
   - `spatial_cells_active_count`: Jumlah bucket sel aktif.
   - `spatial_query_duration_microseconds`: Waktu eksekusi query radius dan AoI evaluation.
   - `spatial_events_emitted_rate`: Frekuensi emisi event `Enter` dan `Leave` per detik (lonjakan tajam menandakan batas hysteresis yang buruk).

---

### 10. Hands-on Lab Exercise

#### Skenario Laboratorium
Bimbing implementasi benchmark dan uji deterministik untuk membuktikan efektivitas sistem Spatial Hash Grid terhadap Boundary Thrashing dan performa eksekusi di bawah beban 10.000 entitas dinamis.

#### File: `spatial_test.go`
Buat file pengujian komprehensif berikut untuk menguji dan memverifikasi implementasi engine spasial Anda:

```go
package spatial

import (
	"math/rand"
	"testing"
)

// TestHysteresisMitigation memverifikasi bahwa entitas yang bergerak bolak-balik di garis batas tidak memicu event ganda.
func TestHysteresisMitigation(t *testing.T) {
	grid := NewSpatialHashGrid(20.0)

	observerID := EntityID(1)
	subjectID := EntityID(2)

	// Observer berada di (0, 0, 0) dengan Enter Radius = 10m dan Margin Hysteresis = 2m (Leave Radius = 12m)
	grid.RegisterEntity(observerID, Vector3{X: 0, Y: 0, Z: 0}, true, 10.0, 2.0)

	// Subject mulai di luar jangkauan (15m)
	grid.RegisterEntity(subjectID, Vector3{X: 15, Y: 0, Z: 0}, false, 0, 0)

	// Step 1: Subject bergerak ke 11m (Antara Enter dan Leave). Belum boleh memicu Enter.
	events := grid.UpdatePosition(subjectID, Vector3{X: 11, Y: 0, Z: 0})
	if len(events) != 0 {
		t.Fatalf("Ekspektasi 0 event pada jarak 11m, didapat: %d", len(events))
	}

	// Step 2: Subject bergerak ke 9m (Menembus Enter Radius 10m). Harus memicu EventEntityEntered.
	events = grid.UpdatePosition(subjectID, Vector3{X: 9, Y: 0, Z: 0})
	if len(events) != 1 || events[0].Type != EventEntityEntered {
		t.Fatalf("Ekspektasi 1 EventEntityEntered pada jarak 9m, didapat: %+v", events)
	}

	// Step 3: Subject mundur ke 11m (Di atas Enter Radius, tetapi MASIH DI DALAM Leave Radius 12m).
	// Tidak boleh memicu EventEntityLeft!
	events = grid.UpdatePosition(subjectID, Vector3{X: 11, Y: 0, Z: 0})
	if len(events) != 0 {
		t.Fatalf("Hysteresis gagal! Ekspektasi 0 event pada jarak 11m saat mundur, didapat: %d", len(events))
	}

	// Step 4: Subject mundur ke 13m (Menembus Leave Radius 12m). Harus memicu EventEntityLeft.
	events = grid.UpdatePosition(subjectID, Vector3{X: 13, Y: 0, Z: 0})
	if len(events) != 1 || events[0].Type != EventEntityLeft {
		t.Fatalf("Ekspektasi 1 EventEntityLeft pada jarak 13m, didapat: %+v", events)
	}
}

// BenchmarkSpatialTick10kEntities mengevaluasi performa spatial hashing pada 10.000 entitas.
func BenchmarkSpatialTick10kEntities(b *testing.B) {
	grid := NewSpatialHashGrid(50.0)
	const totalEntities = 10000
	const worldBounds = 5000.0

	rng := rand.New(rand.NewSource(42))

	// Inisialisasi 10.000 entitas acak
	for i := 0; i < totalEntities; i++ {
		isObserver := (i%10 == 0) // 10% entitas bertindak sebagai Observer
		pos := Vector3{
			X: rng.Float64() * worldBounds,
			Y: 0,
			Z: rng.Float64() * worldBounds,
		}
		grid.RegisterEntity(EntityID(i), pos, isObserver, 75.0, 15.0)
	}

	b.ResetTimer()

	// Simulasi tick iterasi pembaruan posisi entitas
	for n := 0; n < b.N; n++ {
		targetID := EntityID(rng.Intn(totalEntities))
		deltaX := (rng.Float64() - 0.5) * 2.0 // Geser posisi entitas secara incremental
		deltaZ := (rng.Float64() - 0.5) * 2.0

		record := grid.entities[targetID]
		newPos := Vector3{
			X: record.Position.X + deltaX,
			Y: 0,
			Z: record.Position.Z + deltaZ,
		}

		_ = grid.UpdatePosition(targetID, newPos)
	}
}
```

#### Langkah Verifikasi dan Eksekusi
Jalankan pengujian unit dan tolok ukur (*benchmark*) via CLI:

```bash
# Jalankan pengujian logika Hysteresis
go test -v -run TestHysteresisMitigation

# Jalankan profiling performa benchmark pembaruan 10.000 entitas
go test -bench=BenchmarkSpatialTick10kEntities -benchmem
```

#### Kriteria Keberhasilan Tolok Ukur (*Target Baseline*)
- `TestHysteresisMitigation`: **PASS** tanpa ada event terduplikasi saat objek bervibrasi di koordinat batas 11.0m.
- `BenchmarkSpatialTick10kEntities`: Waktu eksekusi rata-rata berada di bawah **$5.000\text{ ns/op}$** ($< 0.005\text{ ms}$ per pembaruan posisi entitas individual), dengan pemakaian heap memory stabil tanpa kebocoran alokasi slice yang tak terkendali.