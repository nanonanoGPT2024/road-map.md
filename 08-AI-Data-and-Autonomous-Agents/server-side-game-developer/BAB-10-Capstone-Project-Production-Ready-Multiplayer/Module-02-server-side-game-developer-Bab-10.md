# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Track:** Server-Side Game Developer  
**Bab 10:** Capstone Project - Production-Ready Multiplayer Dedicated Game Server (DGS)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Mengonstruksi Authoritative Game Loop Presisi Tinggi**: Mengimplementasikan fixed-timestep simulation loop dengan kompensasi *tick drift* mikrodetik menggunakan Go/C++ primitives.
2. **Mendesain Network Relevancy & Spatial Partitioning**: Mengurangi bandwidth overhead hingga 85% menggunakan algoritma *Spatial Hash Grid* dan *Area of Interest (AoI)* filtering dinamis.
3. **Mengimplementasikan State Synchronization Tingkat Lanjut**: Membangun protokol serialisasi biner berbasis *Delta Compression* dan *Bit-packing* untuk snapshot entities real-time.
4. **Mengorkestrasi Dedicated Game Server (DGS)**: Mengonfigurasi siklus hidup container stateful di atas Kubernetes menggunakan *Agones GameServer Custom Resource Definitions (CRDs)*.
5. **Mengintegrasikan Client-Side Prediction Reconciliation**: Menyusun backend endpoint untuk melayani client reconciliation data, verifikasi inputs non-deterministik, dan mitigasi desinkronisasi.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Pemrograman Go (Tingkat Lanjut: Pointer, Unsafe, Bitwise operations, Channels, Concurrency Sync Primitives).
* Pemahaman mendalam tentang stack jaringan: UDP, TCP, WebSocket, dan arsitektur QUIC/WebTransport.
* Konsep dasar *Dead Reckoning*, *Interpolation/Extrapolation*, dan *Authoritative Server Pattern*.
* Fondasi containerization: Docker OCI runtime, Linux namespaces/cgroups, dan Kubernetes architecture primitives.

---

## 3. Concept & Internal Architecture

Membangun server game multiplayer skala enterprise memerlukan pergeseran paradigma dari model arsitektur mikroservis stateless konvensional (REST/gRPC request-response) menuju **Stateful Authoritative Dedicated Game Server (DGS)** berbasis stream UDP dengan siklus eksekusi deterministik (*tick-based*).

```
                 +-------------------------------------------------+
                 |            DEDICATED GAME SERVER (DGS)          |
                 |                                                 |
  UDP Ingress    |  +-------------------------------------------+  |
[Packet Client] --->| Packet Ingestion Buffer (RingBuffer Zero) |  |
                 |  +-------------------------------------------+  |
                 |                       |                         |
                 |                       v                         |
                 |  +-------------------------------------------+  |
                 |  |       Input Validation & Jitter Buffer    |  |
                 |  +-------------------------------------------+  |
                 |                       |                         |
                 |                       v                         |
                 |  +-------------------------------------------+  |
                 |  |       ECS World: Authoritative Tick       |  |
                 |  |  (Physics / Collision / State Machine)    |  |
                 |  +-------------------------------------------+  |
                 |                       |                         |
                 |         +-------------+-------------+           |
                 |         |                           |           |
                 |         v                           v           |
                 |  +---------------+         +-----------------+  |
                 |  | Spatial Grid  |         | State Historian |  |
                 |  | (AoI Filter)  |         | (Rewind Engine) |  |
                 |  +---------------+         +-----------------+  |
                 |         |                           |           |
                 |         +-------------+-------------+           |
                 |                       |                         |
                 |                       v                         |
  UDP Egress     |  +-------------------------------------------+  |
[Delta Snapshot]<---| Delta Compression & Bit-Packing Broadcast |  |
                 |  +-------------------------------------------+  |
                 +-------------------------------------------------+
```

### A. The Fixed-Timestep Authoritative Game Loop
Server game tidak boleh bergantung pada clock dinding murni (`time.Sleep`) karena jitter scheduler OS (Linux CFS) dapat menyebabkan *tick starvation* atau *burst execution*. Arsitektur loop server enterprise menggunakan akumulator waktu berpresisi tinggi dengan resolusi nanodetik:

$$\Delta t_{\text{accumulated}} = t_{\text{current}} - t_{\text{previous}}$$
$$\text{While } \Delta t_{\text{accumulated}} \ge \Delta t_{\text{fixed}} \implies \text{UpdateSimulation}(\Delta t_{\text{fixed}}), \quad \Delta t_{\text{accumulated}} \gets \Delta t_{\text{accumulated}} - \Delta t_{\text{fixed}}$$

Jika $\Delta t_{\text{accumulated}} > \text{MaxAccumulatorThreshold}$ (misalnya server hang akibat GC pause atau I/O blocking), akumulator harus di-*clamp* (*spiral of death protection*) guna mencegah server mengeksekusi puluhan frame secara mendadak.

### B. Spatial Partitioning: Dynamic Spatial Hash Grid
Dalam game arena terbuka dengan $N$ entitas, komputasi visibilitas dan replikasi paket brute-force membutuhkan kompleksitas $\mathcal{O}(N^2)$.
Spatial Hash Grid memetakan ruang kontinu 2D/3D ke dalam bucket diskrit berbasis bitwise integer hashing:

$$\text{CellX} = \lfloor X / \text{CellSize} \rfloor, \quad \text{CellY} = \lfloor Y / \text{CellSize} \rfloor$$
$$\text{Hash}(CellX, CellY) = ((CellX \times P_1) \oplus (CellY \times P_2)) \pmod{BucketsCount}$$

Entitas hanya akan menerima paket snapshot (state updates) dari entitas lain yang menempati cell yang sama atau adjacent cell di dalam radius Area of Interest (AoI).

### C. State Synchronization: Baseline Delta Compression
Daripada mengirim seluruh state entitas ($S_{\text{full}}$) setiap tick (yang membutuhkan bandwidth ratusan KB/s per client), DGS enterprise mengimplementasikan **Delta Compression berbasis Acknowledgement (ACK)**:
1. Server menyimpan histori snapshot untuk setiap frame $K$ dalam *ring buffer* melingkar.
2. Client mengirim ACK bahwa snapshot $K-n$ telah diterima.
3. Server menghitung selisih bitwise $\Delta = S_{\text{current}} \oplus S_{K-n}$.
4. Hanya bit-field yang berubah (*dirty flag mask*) dan nilai terkompresi yang dikirimkan melalui transmisi UDP terfragmentasi minimal.

---

## 4. Why & What

| Dimensi | Pendekatan Web / Stateful RPC Tradisional | Pendekatan Production-Ready Authoritative DGS |
| :--- | :--- | :--- |
| **Protokol Dasar** | TCP / HTTP/2 / WebSockets standar. Mengalami *Head-of-Line (HoL) Blocking*. | Raw UDP / KCP / WebTransport. Tidak ada HoL blocking; payload loss diabaikan jika digantikan data baru. |
| **Model Replikasi** | Replikasi state penuh (*Full Object State JSON/Protobuf* serialization). | Bit-packed Delta Binary Arrays. Kompresi koordinat integer 16-bit quantize. |
| **Penyelesaian Latensi**| Client pasif, menunggu respon server (UI spinner / Action lock). | *Client-Side Prediction*, *Server Reconciliation*, & *Lag Compensation (History Rewind)*. |
| **Manajemen Node** | Kubernetes Deployment / ReplicaSet (Stateless scaling). Pod dimatikan sembarangan saat scale-down. | Agones GameServer CRD. Pod ditandai `Allocated` dan dilindungi dari penghentian paksa hingga match selesai. |

---

## 5. How (Workflow Detail)

Alur eksekusi per-tick (misal: 60Hz = 16.66ms) pada thread game loop utama:

```
[Start Tick N]
  |
  +--> 1. Socket Ingestion: Drain kernel socket buffer via recvmmsg (batch UDP read).
  |
  +--> 2. Input Processing: Validasi input seq #, filter duplikasi, insert ke Jitter Buffer per-pemain.
  |
  +--> 3. Fixed Tick Physics/Logic:
  |      +-- Proses input terlama yang valid dari jitter buffer.
  |      +-- Eksekusi pergerakan entitas & kalkulasi deteksi tabrakan (Spatial Query).
  |      +-- Mutasi state game (Health, Cooldowns, Ammo).
  |
  +--> 4. Spatial Hash Grid Indexing:
  |      +-- Update posisi entitas ke dalam bucket koordinat ruang.
  |      +-- Query tetangga terdekat (Neighbor Search) untuk tiap pemain (AoI Calculation).
  |
  +--> 5. Delta Serialization:
  |      +-- Bandingkan entitas dalam AoI terhadap ACK snapshot terakhir client.
  |      +-- Susun Payload: [Header | Frame ACK | Bitmask Dirty | Quantized Transform Data].
  |
  +--> 6. Socket Egress: Flush paket biner via batch UDP send (sendmmsg).
  |
  +--> 7. Garbage & State Recording: Simpan snapshot tick N ke ring buffer history (untuk rewind engine).
  |
[Sleep / Precise Yield hingga batas 16.66ms]
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem DGS ini sebagai **Kantor Pos Radar Bandara**:

*   **Brute Force (Tanpa Spatial Hash):** Menara pengawas menyiarkan posisi SEMUA pesawat di seluruh benua ke SETIAP pilot melalui radio. Frekuensi tersumbat seketika (*Bandwidth Saturation*).
*   **Spatial Hash Grid:** Menara membagi peta menjadi petak-petak koordinat. Pilot hanya diberi transmisi tentang pesawat yang berada dalam sektor petak radar mereka dan petak tetangga langsung.
*   **Delta Compression:** Menara pengawas tidak mendiktekan: *"Pesawat A di (102.342, 54.123), kecepatan 400, ketinggian 10000, arah 90 derajat..."* setiap detik. Menara hanya menyiarkan: *"Pesawat A: Maju 2 meter"* jika atribut lainnya tetap konstan.

```
       Spatial Hash Grid Matrix (AoI System)
       +-----------+-----------+-----------+
       | Cell(0,2) | Cell(1,2) | Cell(2,2) |
       |           |  Entity B |           |
       +-----------+-----------+-----------+
       | Cell(0,1) | Cell(1,1) | Cell(2,1) |
       |           |  PLAYER A |           |
       |           | [Radius]  |           |
       +-----------+-----------+-----------+
       | Cell(0,0) | Cell(1,0) | Cell(2,0) |
       |  Entity C |           |           |
       +-----------+-----------+-----------+
  -> Player A hanya mereplikasi Entity B (Adjacent Cell).
  -> Entity C (di Cell 0,0) di-cull secara instan (Zero Bandwidth Cost).
```

---

## 7. Simple Example & Practical Example

### Implementasi Authoritative Dedicated Game Server Core (Go)

Kode di bawah mengimplementasikan high-performance game server engine:
1. Fixed-timestep 60-Tick Loop dengan sub-millisecond accuracy.
2. Spatial Hash Grid untuk isolasi Area of Interest (AoI).
3. Bit-packing serializer untuk kompresi koordinat transform 3D.

```go
package main

import (
	"encoding/binary"
	"fmt"
	"math"
	"net"
	"sync"
	"time"
)

const (
	TickRate       = 60
	TickDuration   = time.Second / TickRate
	CellSize       = 32.0 // Ukuran grid dalam satuan meter dunia
	MaxWorldSize   = 1024
	HashBuckets    = 1024
	QuantizeFactor = 100.0 // Presisi 2 digit desimal (0.01m)
)

// Bitmask untuk tracking perubahan state (Dirty Flags)
const (
	DirtyPositionX uint16 = 1 << 0
	DirtyPositionY uint16 = 1 << 1
	DirtyPositionZ uint16 = 1 << 2
	DirtyRotation  uint16 = 1 << 3
)

type Vector3 struct {
	X, Y, Z float32
}

type Entity struct {
	ID       uint32
	Position Vector3
	Rotation float32
	Dirty    uint16
}

// SpatialHashGrid mengoptimalkan AoI query
type SpatialHashGrid struct {
	cellSize float32
	buckets  map[int][]uint32
	mu       sync.RWMutex
}

func NewSpatialHashGrid(cellSize float32) *SpatialHashGrid {
	return &SpatialHashGrid{
		cellSize: cellSize,
		buckets:  make(map[int][]uint32),
	}
}

func (grid *SpatialHashGrid) hash(x, z float32) int {
	xi := int(math.Floor(float64(x / grid.cellSize)))
	zi := int(math.Floor(float64(z / grid.cellSize)))
	return ((xi * 73856093) ^ (zi * 19349663)) % HashBuckets
}

func (grid *SpatialHashGrid) Insert(id uint32, pos Vector3) {
	grid.mu.Lock()
	defer grid.mu.Unlock()
	h := grid.hash(pos.X, pos.Z)
	grid.buckets[h] = append(grid.buckets[h], id)
}

func (grid *SpatialHashGrid) Clear() {
	grid.mu.Lock()
	defer grid.mu.Unlock()
	for k := range grid.buckets {
		delete(grid.buckets, k)
	}
}

func (grid *SpatialHashGrid) QueryNearby(pos Vector3, radius float32) []uint32 {
	grid.mu.RLock()
	defer grid.mu.RUnlock()

	resultSet := make(map[uint32]struct{})
	minX := pos.X - radius
	maxX := pos.X + radius
	minZ := pos.Z - radius
	maxZ := pos.Z + radius

	for x := minX; x <= maxX; x += grid.cellSize {
		for z := minZ; z <= maxZ; z += grid.cellSize {
			h := grid.hash(x, z)
			for _, id := range grid.buckets[h] {
				resultSet[id] = struct{}{}
			}
		}
	}

	result := make([]uint32, 0, len(resultSet))
	for id := range resultSet {
		result = append(result, id)
	}
	return result
}

// Quantized Bit-Packing Binary Serialization
func SerializeDeltaEntity(buf []byte, e *Entity) int {
	offset := 0
	binary.BigEndian.PutUint32(buf[offset:], e.ID)
	offset += 4

	binary.BigEndian.PutUint16(buf[offset:], e.Dirty)
	offset += 2

	// Quantization: Float32 dikonversi ke Int16 untuk menghemat bandwidth
	if e.Dirty&DirtyPositionX != 0 {
		val := int16(e.Position.X * QuantizeFactor)
		binary.BigEndian.PutUint16(buf[offset:], uint16(val))
		offset += 2
	}
	if e.Dirty&DirtyPositionY != 0 {
		val := int16(e.Position.Y * QuantizeFactor)
		binary.BigEndian.PutUint16(buf[offset:], uint16(val))
		offset += 2
	}
	if e.Dirty&DirtyPositionZ != 0 {
		val := int16(e.Position.Z * QuantizeFactor)
		binary.BigEndian.PutUint16(buf[offset:], uint16(val))
		offset += 2
	}
	if e.Dirty&DirtyRotation != 0 {
		val := uint8((e.Rotation / 360.0) * 255.0)
		buf[offset] = val
		offset += 1
	}

	return offset
}

type ServerEngine struct {
	entities map[uint32]*Entity
	grid     *SpatialHashGrid
	conn     *net.UDPConn
	running  bool
	mu       sync.RWMutex
}

func NewServerEngine(bindAddr string) (*ServerEngine, error) {
	addr, err := net.ResolveUDPAddr("udp", bindAddr)
	if err != nil {
		return nil, err
	}
	conn, err := net.ListenUDP("udp", addr)
	if err != nil {
		return nil, err
	}

	return &ServerEngine{
		entities: make(map[uint32]*Entity),
		grid:     NewSpatialHashGrid(CellSize),
		conn:     conn,
		running:  true,
	}, nil
}

func (s *ServerEngine) Run() {
	ticker := time.NewTicker(TickDuration)
	defer ticker.Stop()

	var previousTime = time.Now()
	var accumulator time.Duration

	fmt.Printf("[Engine] Dedicated Server running on 60Hz (Tick Interval: %v)\n", TickDuration)

	for s.running {
		now := <-ticker.C
		elapsed := now.Sub(previousTime)
		previousTime = now
		accumulator += elapsed

		// Spiral of death prevention: clamp accumulator
		if accumulator > TickDuration*5 {
			accumulator = TickDuration * 5
		}

		// Fixed Tick Simulation Loop
		for accumulator >= TickDuration {
			s.fixedTickUpdate(float32(TickDuration.Seconds()))
			accumulator -= TickDuration
		}
	}
}

func (s *ServerEngine) fixedTickUpdate(dt float32) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.grid.Clear()

	// Update game state simulation
	for _, entity := range s.entities {
		// Mock movement
		entity.Position.X += 0.05
		entity.Dirty = DirtyPositionX // Mark dirty for serialization
		s.grid.Insert(entity.ID, entity.Position)
	}

	// Dynamic AoI Serialization Buffer
	packetBuffer := make([]byte, 1400) // Ukuran MTU aman UDP
	for _, entity := range s.entities {
		nearby := s.grid.QueryNearby(entity.Position, 64.0)
		offset := 0

		for _, otherID := range nearby {
			otherEntity := s.entities[otherID]
			written := SerializeDeltaEntity(packetBuffer[offset:], otherEntity)
			offset += written
		}

		// Simulasi Egress: packetBuffer[0:offset] siap dikirimkan via UDP ke client
	}
}

func main() {
	engine, err := NewServerEngine("0.0.0.0:7777")
	if err != nil {
		panic(err)
	}

	// Mock entities
	engine.entities[1] = &Entity{ID: 1, Position: Vector3{X: 10, Y: 0, Z: 10}}
	engine.entities[2] = &Entity{ID: 2, Position: Vector3{X: 12, Y: 0, Z: 15}}
	engine.entities[3] = &Entity{ID: 3, Position: Vector3{X: 500, Y: 0, Z: 500}} // Terisolasi jauh di AoI lain

	// Run loop non-blocking
	go engine.Run()

	time.Sleep(200 * time.Millisecond)
	fmt.Println("[Engine] Execution verified. Fixed-tick loop active.")
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: 100-Player Real-Time Extraction Shooter (Skala Global)
*   **Platform Target:** Kubernetes Cluster pada GCP dengan 15 Region, mengelola 250.000 Concurrent Users (CCU).
*   **Masalah Arsitektural:** 
    *   Penggunaan JSON serialization menyebabkan bandwidth out tembus **1.2 Gbps per server node**.
    *   Kubernetes Default Scheduler membunuh container game saat *Autoscaler* melakukan downscaling (membuat 100 pemain terputus mendadak saat sesi game sedang berlangsung).
    *   GC Pause pada runtime bahasa tingkat tinggi menyebabkan *rubber-banding* masif setiap 45 detik.
*   **Penyelesaian Teknis:**
    1.  **Deployment Agones:** Mengubah deployment standar menjadi `Agones GameServer` custom resources. Saat pod masuk status `Allocated`, Agones memblokir *drain-node* dan *horizontal scaler* dari mematikan Pod tersebut hingga match lifecycle mengirimkan signal `SDK.Shutdown()`.
    2.  **Transmisi Kustom Berbasis Bit-Packing:** Koordinat float 32-bit (4 byte) dikuantisasi menjadi int16 (2 byte) dalam rentang bounded arena. Bandwidth per-node anjlok dari 1.2 Gbps menjadi **48 Mbps** per 100-player instance (efisiensi 96%).
    3.  **Zero-Allocation Ingestion:** Menghilangkan alokasi heap (`sync.Pool` untuk packet arrays dan pointer reuse). Latensi GC 99th percentile berkurang dari 32ms ke **0.8ms**.

---

## 9. Trade-offs: Architectural Decision Matrix

```
                [Arsitektur Networking Game Server]
                                |
        +-----------------------+-----------------------+
        |                                               |
        v                                               v
[Authoritative Server]                        [Peer-to-Peer / Relay]
  * Keamanan Mutlak (Anti-Cheat)                * Murah (Serverless compute)
  * Biaya Compute Tinggi ($$$)                  * Rentan Cheating / Desync
  * Latensi Tambahan (Round-trip)               * Dependen pada NAT Traversal
        |
        +---> [Pilihan State Serialization]
                 |
                 +--> Protobuf / FlatBuffers
                 |      + Multi-bahasa, schema enforcement ketat
                 |      - Padding overhead bitwise, parsing cost
                 |
                 +--> Manual Raw Bit-Packing (Bitstreams)
                        + Zero-allocation, throughput maksimal, payload terkecil
                        - Maintenance kompleks, backward compatibility sulit
```

| Matriks Keputusan | Authoritative State Streaming | Lockstep Deterministic | Client-Authoritative Relay |
| :--- | :--- | :--- | :--- |
| **Throughput Jaringan** | Sedang - Tinggi (tergantung delta) | Sangat Rendah (hanya kirim input) | Sangat Tinggi |
| **Toleransi Jitter/Loss** | Tinggi (Snapshot baru menimpa yang lama) | Buruk (Satu drop menahan seluruh game) | Buruk |
| **Beban Server Compute** | Sangat Tinggi (Server memutar physics) | Sangat Rendah (Server hanya relay) | Minimal |
| **Ketahanan Exploit** | Level Enterprise (Anti-cheat server-side) | Rentan *Memory Tampering* Client | Zero Defense (Sangat Rentan) |

---

## 10. Common Mistakes & Troubleshooting

### 1. The Clock-Drift Death Spiral
*   **Penyebab:** Memanggil `time.Sleep(16.66ms)` secara langsung di dalam perulangan goroutine. Akurasi sleep pada Linux kernel tergantung pada `CONFIG_HZ` dan sleep sleep-drift dapat meleset 1-5ms per frame, menyebabkan tick rate aktual turun ke 45Hz alih-alih 60Hz.
*   **Solusi:** Gunakan monotonic time delta accumulator dengan `runtime.Gosched()` atau presisi tinggi channel select loop yang memperhitungkan sisa waktu tick.

### 2. AoI Boundary Edge-Cases (Entity Oscillation)
*   **Penyebab:** Ketika entitas musuh berada tepat di garis batas Cell AoI dan bergerak bolak-balik tipis, entitas tersebut akan masuk (*spawn*) dan keluar (*despawn*) dari radar client setiap tick, memicu pembuatan dan penghapusan garbage memory pada sisi client.
*   **Solusi:** Terapkan **Hysteresis Band**. Tetapkan radius kemunculan (Spawn Visibility) sebesar $R$, namun tetapkan radius penghapusan (Despawn Cull) sebesar $R + \text{Padding}$ (misal: spawn pada 50m, despawn baru terpicu jika jarak melebihi 60m).

---

## 11. Best Practices (Production Checklist)

- [ ] **Socket Level:** Mengaktifkan kernel buffer socket `SO_RCVBUF` dan `SO_SNDBUF` minimal ke 4MB hingga 16MB guna mencegah silent packet-drop saat traffic spike.
- [ ] **Zero Memory Allocations:** Tidak membuat slice atau map baru di dalam loop `fixedTickUpdate`. Gunakan array statis atau alokasi buffer di awal (*scratchpad buffers*).
- [ ] **MTU Protection:** Membatasi ukuran payload UDP maksimum pada angka **1200 - 1350 byte** untuk mencegah IP fragmentation di router internet publik.
- [ ] **State Sanity Clamping:** Seluruh input vektor arah dari client dinormalisasi secara wajib pada backend:
  ```go
  if length := math.Hypot(input.X, input.Z); length > 1.0 {
      input.X /= length
      input.Z /= length
  }
  ```
- [ ] **Agones Health Pings:** Implementasi goroutine terpisah yang mengirim sinyal healthcheck Agones setiap 2-5 detik agar Pod yang mengalami deadlock logika server dapat langsung di-*restart* otomatis oleh kubelet.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum ini di dalam repositori Anda pada direktori: `hands-on/m02/`.

### Langkah 1: Siapkan Struktur Proyek
```bash
mkdir -p hands-on/m02/agones
cd hands-on/m02
go mod init m02-game-server
```

### Langkah 2: Buat Konfigurasi Agones Fleet Game Server (`hands-on/m02/agones/gameserver.yaml`)
```yaml
apiVersion: "agones.dev/v1"
kind: GameServer
metadata:
  name: "dedicated-arena-server"
spec:
  ports:
  - name: default
    portPolicy: Dynamic
    containerPort: 7777
    protocol: UDP
  health:
    initialDelaySeconds: 5
    periodSeconds: 2
    failureThreshold: 3
  template:
    spec:
      containers:
      - name: game-server
        image: game-engine/arena-server:v1.0.0
        resources:
          requests:
            memory: "512Mi"
            cpu: "1000m"
          limits:
            memory: "1024Mi"
            cpu: "2000m"
```

### Langkah 3: Eksekusi Benchmark Bandwidth Replikasi
Buat test file `hands-on/m02/serializer_test.go` untuk mengukur alokasi memori pada proses enkripsi payload:
```go
package main

import (
	"testing"
)

func BenchmarkSerializationAllocation(b *testing.B) {
	entity := &Entity{
		ID:       999,
		Position: Vector3{X: 124.55, Y: 10.0, Z: -54.22},
		Rotation: 180.0,
		Dirty:    DirtyPositionX | DirtyPositionY | DirtyPositionZ | DirtyRotation,
	}
	buf := make([]byte, 64)

	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		_ = SerializeDeltaEntity(buf, entity)
	}
}
```
Jalankan benchmark:
```bash
go test -bench=. -benchmem
```
*Ekspektasi Output: `0 B/op` dan `0 allocs/op`.*

---

## 13. Exercise

### Level Easy
Modifikasi struct `Entity` dan fungsi `SerializeDeltaEntity` untuk menambahkan komponen status `Health` (0 - 100) menggunakan kuantisasi `uint8`. Pastikan bitmask dirty diupdate dan alokasi heap tetap bernilai 0 allocs/op.

### Level Medium
Implementasikan struktur data **Circular Ring Buffer** dengan kapasitas 128 elemen untuk mencatat histori state world game setiap frame tick. Buffer ini harus memiliki fungsi pencarian:
`GetHistoricalSnapshot(tickID uint32) (*Snapshot, error)` untuk melayani lag compensation system.

### Level Hard
Implementasikan algoritma **Hysteresis AoI Caching**: Buat sistem relevansi jaringan yang melacak daftar entitas yang dilihat oleh setiap pemain. Entitas baru didaftarkan jika jaraknya $\le 30$ meter, dan baru dihentikan replikasinya (dihapus dari daftar relevan) jika jaraknya melebihi $> 40$ meter.

---

## 14. Challenge

**Skenario Masalah Produksi:**
Sebuah server game fast-paced brawler mengalami masalah *teleportation glitch* dan *ghost hits* saat diakses oleh pemain dengan latensi fluktuatif (jitter 80ms - 250ms). Di samping itu, memory server bocor secara perlahan ketika CCU mencapai 5.000 entity simultan dalam satu single-world zone.

**Instruksi:**
1. Desain arsitektur **Authoritative History Rewind / Lag Compensation** yang mampu memutar mundur (*rewind*) posisi kapsul tabrakan (bounding box) musuh ke waktu lampau saat input pemain dieksekusi, lalu memverifikasi keabsahan raycast tembakan, kemudian mengembalikan posisi dunia ke tick waktu sekarang tanpa memicu *race condition* terhadap thread rendering atau update paralel.
2. Buat dokumentasi teknis mitigasi memory leak terkait penanganan socket fragmentation UDP dan alokasi dynamic buffer slice di level kernel-userspace interface.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. **Mengapa protokol UDP lebih dipilih daripada TCP dalam game multiplayer real-time kompetitif?**
   * A. UDP memiliki enkripsi bawaan yang lebih kuat.
   * B. TCP memblokir pembacaan stream jika terjadi packet loss (*Head-of-Line Blocking*).
   * C. UDP otomatis mengompresi payload menjadi bitwise stream.
   * D. TCP tidak mengizinkan pengiriman data biner mentah.

2. **Berapa alokasi durasi waktu maksimal untuk 1 frame tick pada server dengan spesifikasi 60 Hz?**
   * A. 33.33 milidetik.
   * B. 8.33 milidetik.
   * C. 16.66 milidetik.
   * D. 10.00 milidetik.

3. **Apa kegunaan utama dari teknik "Quantization" pada serialisasi data koordinat game?**
   * A. Mengenkripsi posisi pemain agar aman dari sniffing.
   * B. Mengubah format float (misal 32-bit) ke integer berukuran lebih kecil untuk mereduksi ukuran byte paket.
   * C. Menghitung rotasi matriks 3D secara instan.
   * D. Mengeliminasi floating-point non-determinism antara platform CPU Intel dan ARM.

4. **Kapan kondisi "Spiral of Death" terjadi pada fixed-timestep game loop?**
   * A. Saat jaringan client mengalami disconnect tiba-tiba.
   * B. Saat waktu pemrosesan frame game loop lebih lambat daripada durasi timestep target secara terus-menerus.
   * C. Ketika paket UDP mengalami drop di atas ambang batas 50%.
   * D. Ketika database Redis kehabisan alokasi pool koneksi.

5. **Apa fungsi dari dirty flags bitmask dalam state replication?**
   * A. Menandai koneksi client yang terindikasi menggunakan cheat engine.
   * B. Menandakan variabel atau komponen entitas mana saja yang telah bermutasi dan perlu direplikasi.
   * C. Membersihkan entitas yang sudah berada di luar batas dunia (*out-of-bounds*).
   * D. Menandai memori kernel yang siap untuk di-garbage collect.

---

### Bagian 2: Intermediate (Analisis Singkat)
1. Jelaskan bagaimana **Spatial Hash Grid** mencegah kompleksitas komputasi replikasi $\mathcal{O}(N^2)$ saat menangani ribuan pemain dalam satu arena besar!
2. Mengapa implementasi default `Kubernetes Horizontal Pod Autoscaler (HPA)` tidak aman digunakan secara langsung pada container **Dedicated Game Server (DGS)** yang bersifat stateful?
3. Sebutkan perbedaan fundamental antara **Client-Side Prediction** dan **Lag Compensation (History Rewind)** dalam arsitektur server-side game!
4. Apa bahaya melakukan alokasi memori dinamis (`heap allocation`) baru di dalam tubuh loop fungsi per-tick server game yang berjalan pada frekuensi tinggi?
5. Jelaskan peran sistem **Acknowledgement (ACK) Bitfield** pada protokol transport UDP custom yang dibangun di atas server game tanpa bantuan layer TCP!

---

### Bagian 3: Skenario Kasus Produksi
1. **Analisis Latensi Tak Terduga:**  
   Server DGS Anda berjalan lancar pada lokal test. Namun saat stress test dengan 1.000 simulasi client terhubung ke satu node host, metrik mencatat CPU usage hanya 25%, namun tick-rate anjlok parah dari 60Hz ke 18Hz. Paket UDP banyak yang hilang sebelum sampai ke kode logika server. Analisis akar penyebab masalah pada layer OS/Kernel Linux dan berikan solusi tuning kernel parameternya!
2. **Desinkronisasi Input:**  
   Pemain di belahan dunia dengan latensi tinggi melaporkan bahwa karakter mereka mengalami *snapback* (tertarik mundur kembali ke posisi beberapa detik lalu) secara terus-menerus saat mencoba melompat rintangan. Telusuri letak kegagalan logika antara input validation server, determinisme physics, dan error reconciliation threshold client!
3. **Exploitasi Wallhack & AoI Leaks:**  
   Pemain menemukan cheat yang memungkinkan mereka melihat posisi lawan di seluruh peta meskipun lawan berada di balik dinding tebal atau di balik gunung yang sangat jauh. Setelah ditelusuri, client-side hacker membaca memory paket jaringan game. Langkah perbaikan arsitektural apa yang wajib diambil pada Spatial Partitioning dan Network Visibility backend server Anda?

---

### Kunci Jawaban & Panduan Solusi

#### Bagian 1: Basic
1. **B** — TCP memaksakan in-order delivery yang menyebabkan transmisi terhenti jika ada paket hilang (Head-of-Line blocking).
2. **C** — $1000\text{ms} / 60 \approx 16.66\text{ms}$.
3. **B** — Mengonversi float ke bounded integer (misal range -327.68 s/d 327.67 dalam 16-bit integer) menghemat byte transmisi.
4. **B** — Ketika tick lambat, accumulator menumpuk, menyebabkan tick berikutnya berjalan lebih banyak, membuat loop semakin lambat hingga crash total.
5. **B** — Menghindari pengiriman atribut-atribut entitas yang tidak mengalami perubahan sejak snapshot terakhir.

#### Bagian 2: Intermediate
1. Spatial Hash Grid memecah dunia menjadi sel-sel berdimensi tetap. Setiap entitas hanya didaftarkan ke sel terkait. Pencarian tetangga (AoI) hanya mengecek entitas pada sel lokal dan tetangga terdekat, menurunkan kompleksitas komparasi ke level mendekati $\mathcal{O}(N)$ atau konstan lokal.
2. HPA default Kubernetes mengasumsikan pod stateless; HPA dapat mematikan pod secara sewenang-wenang saat penggunaan resource rata-rata turun, memutus paksa sesi game aktif para pemain. Agones mengatasi ini dengan lifecycle state `Allocated`.
3. *Client-side prediction* dijalankan di client untuk merespon input seketika tanpa menunggu konfirmasi server. *Lag compensation* dijalankan di server untuk memverifikasi tembakan/aksi di masa lalu dengan memutar mundur bounding box target ke waktu saat aksi itu ditembakkan oleh client.
4. Alokasi memori berfrekuensi tinggi (60 kali per detik per entity) akan membebani garbage collector (GC), memicu pause GC periodik yang menyebabkan server membeku selama beberapa milidetik (*tick-spike/rubberbanding*).
5. Karena UDP tidak memiliki ACK, game server menyematkan nomor sequence paket terakhir yang diterima dalam payload. Dengan demikian server tahu snapshot referensi mana yang sudah valid di tangan client untuk dijadikan baseline penghitungan data Delta berikutnya.

#### Bagian 3: Skenario Kasus Produksi
1. **Analisis:** CPU rendah namun tick turun dan packet loss tinggi mengindikasikan antrean kernel socket UDP penuh (*socket buffer overflow*). Buffer default OS Linux (`rmem_default`, `rmem_max`) terlalu kecil untuk menerima semburan ribuan paket UDP per detik, sehingga network stack kernel langsung membuang paket sebelum userspace aplikasi sempat memanggil `recv/recvmmsg`.  
   **Solusi:** Tingkatkan kapasitas buffer socket Linux via `sysctl`:
   ```bash
   sysctl -w net.core.rmem_max=16777216
   sysctl -w net.core.wmem_max=16777216
   sysctl -w net.core.netdev_max_backlog=10000
   ```
   Dan perbarui aplikasi menggunakan sistem batch socket pooling via `recvmmsg`.
2. **Analisis:** Jitter tinggi membuat paket input client tiba tidak teratur di server. Jika server tidak memiliki Jitter Buffer yang memadai, server akan mengeksekusi tick tanpa input client (mengasumsikan diam), lalu saat rentetan input terlambat tiba sekaligus, server membuangnya karena dianggap *outdated*. Akibatnya posisi simulasi server tertinggal jauh di belakang posisi prediksi client, melampaui batas toleransi reconciliation threshold, memicu hard reset posisi pemain ke server state (*snapback*).  
   **Solusi:** Implementasikan adaptive jitter buffer pada server dan terapkan *smooth interpolation blending* pada reconciliation client alih-alih melakukan teleportasi instan jika koreksi berada di bawah ambang batas kritis.
3. **Analisis:** Server melakukan kesalahan fatal dengan membroadcast seluruh entitas global ke semua client dan mengandalkan client untuk menyembunyikan model karakter via *render culling*.  
   **Solusi:** Pindahkan logika culling sepenuhnya ke server-side (*Authoritative Network Culling*). Gunakan Spatial Hash Grid dikombinasikan dengan *Raycast Occlusion Mesh* (PVS - Potentially Visible Sets) di backend. Jika pemain lawan berada di luar AoI atau terhalang dinding absolut, hilangkan entitas tersebut seluruhnya dari packet snapshot transmisi UDP. Data yang tidak dikirim oleh server mustahil dapat dibaca oleh cheat memory scanner di client.

---

## 16. Summary

*   Membangun arsitektur Dedicated Game Server (DGS) produksi menuntut presisi deterministik tinggi di mana model arsitektur stateless standar tidak dapat diaplikasikan.
*   Pondasi performa bergantung pada: **Zero-Allocation Game Loop**, eliminasi latensi OS via **Fixed Timestep Accumulator**, optimasi komputasi melalui **Spatial Hash Grid**, serta kompresi transmisi via **Quantization & Bit-Packing Delta Encoding**.
*   Orkestrasi skala masif diwujudkan melalui abstraksi stateful seperti **Agones**, yang melindungi sesi game aktif dari interupsi cluster autoscaling. Keamanan integritas kompetitif game sepenuhnya ditentukan oleh prinsip **Never Trust The Client**, di mana backend server bertindak sebagai entitas tunggal pemegang otoritas simulasi fisika dan logika.