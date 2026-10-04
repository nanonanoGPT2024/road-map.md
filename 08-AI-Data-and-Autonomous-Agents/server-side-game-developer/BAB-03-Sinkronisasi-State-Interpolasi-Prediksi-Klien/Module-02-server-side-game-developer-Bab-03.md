# Kurikulum Rekayasa Server Game Enterprise
## Topik: Server-Side Game Development (AI, Data, and Autonomous Systems)
### BAB 03: Sinkronisasi State, Interpolasi, Prediksi Klien, & Kompensasi Lag
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis & Mengimplementasikan** sistem *Authoritative Server State Synchronization* menggunakan model *Client-Side Prediction* (CSP) dan *Server Reconciliation*.
- **Merancang** struktur data *Circular Ring Buffer* bebas alokasi memori (zero-allocation) untuk riwayat input klien dan snapshot status fisik server guna mendukung *Lag Compensation* (Rewind Hit-Registration).
- **Membangun** algoritma *Snapshot Interpolation* adaptif dengan *Dynamic Jitter Buffering* untuk meminimalkan *visual micro-stuttering* pada variasi latensi jaringan (network jitter).
- **Menerapkan** teknik kompresi state berbasis *Delta Compression* dan *Bit-packing* untuk memangkas *bandwidth footprint* di bawah batas Maximum Transmission Unit (MTU) 1200 bytes per paket UDP.
- **Mengidentifikasi & Memitigasi** masalah sinkronisasi kritis: *rubber-banding*, *floating-point nondeterminism*, *client clock-drift*, dan eksploitasi manipulasi *timestamp* (speed hacking).

---

### 2. Prerequisites
Sebelum mempelajari modul ini, engineer wajib menguasai:
- **Jaringan Komputer Lanjutan**: UDP socket programming, Packet Loss, Round Trip Time (RTT), Jitter, MTU, Path MTU Discovery, congestion control kustom (misal: DCCP atau reliable-UDP ala ENet/WebRTC DataChannel).
- **Matematika & Fisika Game**: Aljabar linier (vektor, kuaternion, matriks transformasi 3D), AABB (Axis-Aligned Bounding Box), ray-casting, discrete vs continuous collision detection (CCD).
- **Pemrograman Sistem & Konkurensi**: Memory layout, cache locality (struct-of-arrays vs array-of-structs), atomic operations, GC pressure reduction, ring buffer design, dan pointer arithmetic (disarankan: C++, Go, atau Rust).
- **Konsep Arsitektur Engine**: Pemahaman mendalam mengenai arsitektur decoupled render loop vs fixed-step simulation loop.

---

### 3. Concept & Internal Architecture

Dalam arsitektur *Dedicated Server Authoritative Multiplayer*, server adalah satu-satunya sumber kebenaran (*single source of truth*). Klien tidak diizinkan mengubah state dunia secara langsung; klien hanya mengirimkan input intent (misal: "tombol W ditekan pada frame $N$"), dan server mengembalikan *canonical state*.

Tiga tantangan fundamental rekayasa pada model ini adalah:
1. **Latency Penalty**: Menunggu respons server sebelum merender gerakan lokal membuat game terasa *laggy* dan tidak responsif.
2. **Visual Inconsistency**: Menerima update server dengan frekuensi lebih rendah dari refresh rate layar (misal: server 60 Hz, klien 144 Hz) menghasilkan gerakan patah-patah (*stutter*).
3. **Temporal Paradox**: Menembak target yang sedang bergerak pada layar klien berarti menembak posisi masa lalu target dari sudut pandang server saat paket tiba (*peeker's advantage & latency disparity*).

Untuk mengatasi tantangan di atas, arsitektur sinkronisasi game modern dibangun di atas empat pilar internal:

```
+-------------------------------------------------------------------------------+
|                       ARSITEKTUR LENGKAP SINKRONISASI STATE                   |
+-------------------------------------------------------------------------------+
|                                                                               |
|   [CLIENT]                                                                    |
|   +-------------------+       Inputs (Seq=K, dt)      +-------------------+   |
|   | Input Generator   | ----------------------------> | Raw Network Socket|   |
|   +-------------------+                               +-------------------+   |
|             |                                                   |             |
|             v                                                   | UDP Packets |
|   +-------------------+                                         v             |
|   | Client Prediction | <---+ Replay                          [SERVER]        |
|   | Simulation Loop   |     | Unacknowledged          +-------------------+   |
|   +-------------------+     | Inputs                  | Input Buffer      |   |
|             |               |                         | Sorting / Queue   |   |
|             v               |                         +-------------------+   |
|   +-------------------+     |                                   |             |
|   | Render State      |     |                                   v             |
|   | (Interpolated)    |     |                         +-------------------+   |
|   +-------------------+     |                         | Fixed Tick (60Hz) |   |
|             ^               |                         | World Simulation  |   |
|             |               |                         +-------------------+   |
|   +-------------------+     |                                   |             |
|   | Jitter Buffer &   |     |                                   v             |
|   | Interpolator      |     |                         +-------------------+   |
|   +-------------------+     |                         | Historical State  |   |
|             ^               |                         | Buffer (Rewind)   |   |
|             |               |                         +-------------------+   |
|   +-------------------+     |                                   |             |
|   | Reconciliation    | ----+                         +-------------------+   |
|   | Logic (Error Fix) | <---------------------------- | Snapshot Packing  |   |
|   +-------------------+      Snapshots (Tick=S)       | & Delta Encoding  |   |
|                                                       +-------------------+   |
+-------------------------------------------------------------------------------+
```

#### 3.1. Client-Side Prediction (CSP) & Server Reconciliation Loop
Klien menerapkan input lokal ke simulasi lokal secara instan tanpa menunggu konfirmasi server. Klien menyimpan riwayat input dalam `InputHistoryBuffer` melingkar bersama state hasil prediksi.

Ketika snapshot server tiba pada tick $T_{server}$ dengan state $S_{canonical}$:
1. Klien membandingkan state hasil prediksinya pada tick $T_{server}$ dengan $S_{canonical}$.
2. Jika delta $|\Delta S| = |S_{predicted}(T_{server}) - S_{canonical}| > \epsilon$ (ambang batas toleransi), terjadi desinkronisasi.
3. **Reconciliation**: State lokal di-*overwrite* seketika menggunakan $S_{canonical}$.
4. Seluruh input yang belum diproses oleh server dari tick $T_{server} + 1$ sampai tick saat ini ($T_{current}$) disimulasikan ulang secara deterministik (*replay loop*) dalam satu frame.

#### 3.2. Entity Interpolation & Adaptive Jitter Buffer
Untuk entitas non-lokal (lawan, proyektil, kendaraan), klien tidak memprediksi masa depan karena ketiadaan input intent lawan. Klien merender entitas tersebut di masa lalu menggunakan snapshot server:

$$\text{Render Time} = T_{client\_now} - T_{interpolation\_delay}$$

Di mana:
$$T_{interpolation\_delay} = RTT/2 + Jitter + T_{tick\_interval}$$

Dua snapshot $S_A$ dan $S_B$ dipilih sedemikian rupa sehingga $S_A.timestamp \le \text{Render Time} \le S_B.timestamp$. Nilai posisi dan orientasi diinterpolasi menggunakan LERP (*Linear Interpolation*) untuk posisi dan SLERP (*Spherical Linear Interpolation*) untuk rotasi:

$$P(t) = (1 - \alpha) P_A + \alpha P_B, \quad \alpha = \frac{\text{Render Time} - S_A.timestamp}{S_B.timestamp - S_A.timestamp}$$

#### 3.3. Lag Compensation (Hitbox Rewind System)
Ketika Klien A menembak Klien B pada waktu render lokal $T_{render}$, paket tembakan dikirim ke server membawa informasi timestamp $T_{render}$.
Saat server menerima perintah tembak:
1. Server memvalidasi bahwa $T_{render}$ valid (tidak lebih lama dari ukuran buffer rewind, biasanya 1000 ms, dan tidak berada di masa depan).
2. Server mengambil seluruh bounding box entitas dari `HistoryRingBuffer` pada timestamp $T_{render}$.
3. Bounding box dunia sementara dimundurkan (*rewind*) ke posisi spasial persis saat Klien A menarik pelatuk di layarnya.
4. Server mengeksekusi *ray-cast* penembakan pada state masa lalu tersebut.
5. Server mengembalikan seluruh bounding box ke kondisi tick sekarang (*un-rewind*) sebelum melanjutkan siklus simulasi berikutnya.

---

### 4. Why & What: Analisis Komparatif Paradigma Sinkronisasi

| Paradigma | Mekanisme Inti | Kelebihan | Kelemahan Fatal di Skala Enterprise | Use Case Ideal |
| :--- | :--- | :--- | :--- | :--- |
| **Deterministic Lockstep** | Klien hanya bertukar input; seluruh mesin menjalankan simulasi identik tick demi tick. | Bandwidth sangat kecil (hanya kirim command). | Rentan desync akibat perbedaan arsitektur CPU; game berhenti total jika ada satu klien lag (*freeze*). | RTS (StarCraft), Turn-based strategy. |
| **P2P State Push** | Tiap klien menghitung state sendiri lalu menyiarkannya (*broadcast*) ke peer lain. | Tidak perlu infrastruktur server mahal; latensi peer-to-peer rendah secara geografis. | Rawan eksploitasi cheat; skala koneksi $O(N^2)$; inkonsistensi state tinggi. | Game Co-op santai 2-4 pemain. |
| **Snapshot Replication (Authoritative)** | Server menghitung seluruh logika; memancarkan absolute state secara periodik ke semua klien. | Cheat-resistant; determinisme multi-platform tidak wajib absolut pada klien; klien lemah tetap sinkron. | Bandwidth tinggi jika tanpa kompresi; CPU server terbebani simulasi penuh. | Arena Shooter, Extraction Shooters, Battle Royale. |
| **Delta State Sync + Lag Comp (State of The Art)** | Server authoritative; hanya menyiarkan delta tick; menggunakan rewind spatial rollback untuk validasi aksi. | Sangat responsif; keadilan kompetitif maksimal; bandwidth optimal via bitpacking. | Arsitektur sangat kompleks; server memory footprint bertambah untuk rewind ring buffers. | Competitive FPS (CS2, Valorant, Apex Legends). |

---

### 5. How: Alur Kerja & Workflow Sinkronisasi Produksi

```
[CLIENT TIMELINE]                                           [SERVER TIMELINE]
Frame 100: Kumpul Input U_100
           Simulasi Prediksi Posisi P_100
           Kirim Packet(U_100, Tick=100) --\
                                            \  [Internet Transit: RTT/2 = 30ms]
                                             \--> Server Tick 50:
                                                  Terima U_100
                                                  Tempatkan pada Input Queue
                                                  Simulasi State Resmi S_50
                                             /--  Kirim Snapshot(S_50, Ack=100)
                                            /
Frame 103: <-------------------------------/
           Terima Snapshot(S_50, Ack=100)
           Cek: Error = |P_100_prediksi - S_50_resmi|
           If Error > Toleransi:
              Rollback ke S_50
              Replay Input U_101 -> U_102 -> U_103
              Dapatkan P_103_koreksi baru
```

#### Langkah-langkah Pemrosesan Input dan Eksekusi Server:
1. **Fase Ingestion (Server Tick Start)**:
   - Server membaca seluruh buffer soket UDP non-blocking.
   - Input dipilah berdasarkan `ClientID` dan diurutkan berdasarkan `TickNumber`.
   - Mengabaikan paket duplikat atau paket usang (*out-of-order drop*).
2. **Fase Validasi Integritas**:
   - Memastikan laju input tidak melampaui toleransi tick rate (mencegah *speed hack* dengan mendeteksi anomali akumulasi input).
3. **Fase Simulasi Fisika & Logika**:
   - Mengeksekusi fixed-timestep physics update (misal: 16.66ms per tick untuk 60 Hz).
   - Menyimpan *transform snapshot* seluruh entitas ke dalam `LagCompensationHistoryBuffer`.
4. **Fase Broadcast Snapshot**:
   - Mengekstrak delta perubahan state dibandingkan dengan snapshot terakhir yang diakui (*ACKed*) oleh masing-masing klien.
   - Melakukan bit-packing dan mengirimkan snapshot individual atau broadcast via UDP.

---

### 6. Diagram Alur & Representasi Temporal

#### 6.1. Mekanisme Lag Compensation Rewind
```
Waktu Server:  T=100 (Sekarang)
                 |
                 v
Riwayat Server: [T=90] --- [T=93] --- [T=95] --- [T=97] --- [T=100]
                                ^
                                |
               Target ditembak oleh Shooter
               pada pandangan Shooter di T=93 (karena delay interpolasi & latency)
                                |
[Server Process]:
1. Shooter kirim: ShootCmd(target_tick=93, ray=origin/dir)
2. Server simpan state saat ini (T=100).
3. Server memundurkan target collider ke [T=93].
4. Server eksekusi RayCast(origin, dir) vs Collider[T=93].
5. Result: HIT! (Apply damage).
6. Server kembalikan target collider ke [T=100].
```

#### 6.2. Interpolation Jitter Buffer Timeline
```
Packet Arrival (Berantakan karena Jitter Internet):
Tick 1 (t=15ms) ----> Tick 3 (t=55ms) -> Tick 2 (t=60ms) -------> Tick 4 (t=110ms)
                               |
                               v
Jitter Buffer (Smoothing Delay Window = 50ms):
[ Slot 1 ] -------> [ Slot 2 ] -------> [ Slot 3 ] -------> [ Slot 4 ]
       \                 /
        \-- LERP State -/ 
                 |
                 v
         Smooth Render Output (Klien bebas stutter)
```

---

### 7. Implementasi Lanjutan Arsitektur Produksi

Berikut adalah implementasi sistem inti server-side game network dalam bahasa **Go** modern, dirancang dengan pola *zero heap allocation* di dalam per-tick simulation loop.

#### 7.1. Struktur Data & Buffer Management
```go
package network

import (
	"errors"
	"math"
	"sync/atomic"
)

const (
	MaxHistoryTicks = 128 // Ukuran ring buffer (pangkat 2 untuk masking)
	HistoryMask     = MaxHistoryTicks - 1
	PositionEpsilon = 0.001
)

// Vector3 merepresentasikan koordinat 3D deterministik sederhana
type Vector3 struct {
	X, Y, Z float32
}

func (v Vector3) Sub(o Vector3) Vector3 {
	return Vector3{v.X - o.X, v.Y - o.Y, v.Z - o.Z}
}

func (v Vector3) LengthSq() float32 {
	return v.X*v.X + v.Y*v.Y + v.Z*v.Z
}

func (v Vector3) Lerp(target Vector3, alpha float32) Vector3 {
	return Vector3{
		X: v.X + alpha*(target.X-v.X),
		Y: v.Y + alpha*(target.Y-v.Y),
		Z: v.Z + alpha*(target.Z-v.Z),
	}
}

// EntityTransform menyimpan transformasi spatial untuk kompensasi lag
type EntityTransform struct {
	Position Vector3
	Rotation float32 // Sederhana: orientasi yaw (radian)
}

// FrameSnapshot menyimpan kondisi seluruh world pada satu tick server
type FrameSnapshot struct {
	Tick      uint32
	Timestamp int64 // Milliseconds Unix epoch
	Entities  map[uint32]EntityTransform
}

// UserInput menyimpan payload input yang dikirim klien
type UserInput struct {
	Sequence uint32
	Tick     uint32
	DeltaX   float32
	DeltaY   float32
	IsFire   bool
}

// LagCompensationBuffer mengelola ring-buffer transformasi untuk spatial rewind
type LagCompensationBuffer struct {
	buffer [MaxHistoryTicks]FrameSnapshot
	head   uint32
}

func NewLagCompensationBuffer() *LagCompensationBuffer {
	b := &LagCompensationBuffer{}
	for i := 0; i < MaxHistoryTicks; i++ {
		b.buffer[i] = FrameSnapshot{
			Entities: make(map[uint32]EntityTransform, 64),
		}
	}
	return b
}

func (b *LagCompensationBuffer) SaveTick(tick uint32, timestamp int64, transforms map[uint32]EntityTransform) {
	idx := tick & HistoryMask
	snap := &b.buffer[idx]
	snap.Tick = tick
	snap.Timestamp = timestamp
	for id, t := range transforms {
		snap.Entities[id] = t
	}
	atomic.StoreUint32(&b.head, tick)
}

// GetStateAtTime mengambil transform snapshot tervolusi dari titik waktu tertentu
func (b *LagCompensationBuffer) GetStateAtTime(targetTimestamp int64) (map[uint32]EntityTransform, error) {
	currentHead := atomic.LoadUint32(&b.head)
	if currentHead == 0 {
		return nil, errors.New("buffer uninitialized")
	}

	// Cari dua slice snapshot yang mengapit targetTimestamp
	var older, newer *FrameSnapshot
	for i := uint32(0); i < MaxHistoryTicks-1; i++ {
		tIdx := (currentHead - i) & HistoryMask
		prevIdx := (currentHead - i - 1) & HistoryMask

		sNew := &b.buffer[tIdx]
		sOld := &b.buffer[prevIdx]

		if sOld.Timestamp <= targetTimestamp && targetTimestamp <= sNew.Timestamp {
			older = sOld
			newer = sNew
			break
		}
	}

	if older == nil || newer == nil {
		return nil, errors.New("temporal timestamp out of compensation window")
	}

	// Lakukan interpolasi jika berada di antara dua tick
	timeRange := float32(newer.Timestamp - older.Timestamp)
	var alpha float32 = 0.0
	if timeRange > 0 {
		alpha = float32(targetTimestamp-older.Timestamp) / timeRange
	}

	result := make(map[uint32]EntityTransform, len(newer.Entities))
	for id, newTrans := range newer.Entities {
		oldTrans, exists := older.Entities[id]
		if !exists {
			result[id] = newTrans
			continue
		}
		result[id] = EntityTransform{
			Position: oldTrans.Position.Lerp(newTrans.Position, alpha),
			Rotation: oldTrans.Rotation + alpha*(newTrans.Rotation-oldTrans.Rotation),
		}
	}

	return result, nil
}
```

#### 7.2. Client-Side Prediction & Server Reconciliation Driver
```go
package network

type PlayerState struct {
	Tick     uint32
	Position Vector3
}

type ClientReconciliationEngine struct {
	AcknowledgedState PlayerState
	PredictedState    PlayerState
	InputBuffer       [MaxHistoryTicks]UserInput
	LastAckSeq        uint32
	MoveSpeed         float32
}

func NewClientReconciliationEngine(speed float32) *ClientReconciliationEngine {
	return &ClientReconciliationEngine{
		MoveSpeed: speed,
	}
}

// SimulateInput mengaplikasikan model simulasi kinematis lokal deterministik
func (c *ClientReconciliationEngine) SimulateStep(pos Vector3, input UserInput, dt float32) Vector3 {
	return Vector3{
		X: pos.X + input.DeltaX*c.MoveSpeed*dt,
		Y: pos.Y,
		Z: pos.Z + input.DeltaY*c.MoveSpeed*dt,
	}
}

// OnServerSnapshotAcknowledged menerima state dari server dan melakukan koreksi jika ada desync
func (c *ClientReconciliationEngine) OnServerSnapshotAcknowledged(canonical PlayerState, ackSeq uint32, dt float32) {
	c.AcknowledgedState = canonical

	// Ambil state lokal dari buffer sejarah pada sekuens bersangkutan
	predictedPosAtTick := c.PredictedState.Position // Simpan state prediksi lokal

	// Deteksi error deviasi
	distSq := canonical.Position.Sub(predictedPosAtTick).LengthSq()
	if distSq > PositionEpsilon {
		// RECONCILIATION: Terjadi misprediksi server, rollback dan putar ulang!
		c.PredictedState.Position = canonical.Position
		c.PredictedState.Tick = canonical.Tick

		// Replay seluruh input dari ackSeq hingga frame saat ini
		for seq := ackSeq + 1; seq <= c.LastAckSeq; seq++ {
			input := c.InputBuffer[seq&HistoryMask]
			c.PredictedState.Position = c.SimulateStep(c.PredictedState.Position, input, dt)
			c.PredictedState.Tick++
		}
	}
}
```

---

### 8. Real-World Case Study: FPS Taktis Skala Global

#### Kasus Masalah
Pada peluncuran game FPS taktis 5v5 skala kompetitif, terjadi *hit registration inconsistency* parah saat pemain dengan ping 20ms berhadapan dengan pemain berlatensi 120ms (*peeker's advantage*). Pemain berlatensi rendah merasa ditembak ketika sudah bersembunyi di balik tembok solid (*dying behind cover*).

#### Akar Masalah Teknis
1. Server menggunakan jendela kompensasi lag yang terlalu longgar (hingga 400ms).
2. Tembakan dari pemain berlatensi tinggi diterima terlambat, tetapi server tetap melakukan rewind historis sejauh 250ms ke belakang, memvalidasi peluru menembus posisi korban sebelum berlindung.
3. Klien korban telah bergerak lebih maju 100ms dalam waktu riil dan berada di balik perlindungan.

#### Solusi Rekayasa Sistem
1. **Asymmetric Lag Clamping**:
   Server membatasi maksimum rewind window menjadi $\min(RTT, 120\text{ ms})$. Jika latensi penembak $>120\text{ ms}$, penembak harus memprediksi pergerakan (*lead their shot*), bukan server yang memundurkan dunia secara ekstrem.
2. **Sub-Tick Input Precision**:
   Mengadopsi pemetaan sub-tick: Klien menyematkan fraksi presisi waktu floating-point kapan klik mouse terjadi di antara tick ($0.0 \le \tau < 1.0$), sehingga ray-cast server diinterpolasi secara continuous, bukan discrete tick-rounded.
3. **Adaptive Visual Rollback Bleeding**:
   Pada rekonsiliasi lokal korban, perpindahan posisi tidak dipotong secara instan (*hard snap/teleport*), melainkan diserap menggunakan kurva pemulihan eksponensial selama 3 frame untuk menghindari disorientasi kamera.

---

### 9. Trade-offs Architecture Matrix

```
                      TRADE-OFF SPACE
             Bandwidth Compression
                      ▲
                      │         * Delta State Packing
                      │           (High CPU, Low Bandwidth)
                      │
                      │
  Full Snapshot       │
  Replication         │
  (Low CPU, High BW)  │
  ◄───────────────────┼───────────────────► Simulation Tick Rate
                      │                    (e.g., 128Hz vs 64Hz)
                      │
                      │   * Continuous Collision Rewind
                      │     (Extreme Memory, Lowest Lag Artifact)
                      │
                      ▼
               Memory & CPU Footprint
```

| Dimensi | Pendekatan A | Pendekatan B | Analisis Komparasi Engineering |
| :--- | :--- | :--- | :--- |
| **Penyimpanan Snapshot History** | **Linked List Dynamically Allocated** | **Pre-allocated Circular Flat Ring Buffer** | Linked List menyebabkan heap fragmentation & cache miss fatal pada loop tick server. Ring Buffer berukuran tetap menghasilkan nol alokasi runtime dan optimalisasi L1/L2 data cache. |
| **Kompensasi Lag** | **Server-side Full Raycast Rewind** | **Client-side Hit Validation with Server Checks** | Client-side hit detection rawan modifikasi binary memory (aimbot/triggerbot injection). Server Rewind menuntut CPU server tinggi, tetapi mutlak untuk integritas anti-cheat turnamen. |
| **Koreksi Rekonsiliasi** | **Hard Correction (Snap to Pos)** | **Exponential Smoothing / Slerp Blend** | Hard Snap membuat pemain pusing saat terjadi sedikit network loss. Smoothing ramah visual, namun jika desync parah dapat menyebabkan tembakan meleset sementara. |
| **Sync Protocol** | **Full Delta Snapshots** | **Event Sourcing (Input Only)** | Event Sourcing hemat data namun jika 1 bit salah, simulasi divergen selamanya. Full Delta Snapshot memastikan pemulihan total saat terjadi packet drop masif. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Fatal yang Sering Terjadi
1. **Floating Point Non-Determinism di Replay Loop**:
   Menggunakan arsitektur CPU berbeda (x86 SSE vs ARM NEON) untuk simulasi deterministik pada rekonsiliasi. Pembulatan floating-point berbeda memicu infinite reconciliation loop (*rubber-banding abadi*).
2. **Double-Applying Input pada Re-simulation**:
   Input saat ini dimasukkan kembali ke antrean saat proses rollback, mengakibatkan entitas melesat dua kali lebih cepat.
3. **Mengabaikan MTU Boundary**:
   Snapshot membesar melebihi batas MTU (1200-1400 bytes), memaksa fragmentasi IP di router jaringan yang melipatgandakan *packet loss rate*.
4. **Unclamped Client Clock Timestamps**:
   Memercayai *timestamp* input klien secara mentah tanpa validasi terhadap server monotonic tick counter (membuka celah eksploitasi manipulasi *engine speed*).

#### 10.2. Panduan Troubleshooting
```
Gejala: Pemain melompat-lompat / bergetar terus menerus (Micro-rubberbanding)
Langkah Investigasi:
1. Catat log |PredictedPos - ServerPos|. Jika konstan berada di atas ambang batas Epsilon:
   --> Cek delta time (dt). Pastikan klien dan server menggunakan TICK_INTERVAL identik (misal: 0.01666667s).
2. Cek apakah ada komponen fisika lokal (misal: gravitasi engine non-fixed) memengaruhi posisi.
3. Evaluasi urutan eksekusi input: Apakah ackSeq server mengabaikan 1 frame input klien yang hilang?
```

---

### 11. Best Practices & Production Checklist

#### Production Verification Checklist
- [ ] **Alokasi Heap Nol di Loop Utama**: Tidak ada `malloc`, `new`, atau instansiasi slice/map dinamis di dalam tick server rate (60/128 Hz).
- [ ] **Enkapsulasi Input Sequencing**: Seluruh input menggunakan modulo serial integer uint32 monotonically increasing untuk menangani overflow dengan aman.
- [ ] **Klem Jendela Rewind**: Batas maksimum kompensasi lag dibatasi keras (rekomendasi: 150-200ms) untuk melindungi pemain dengan koneksi stabil.
- [ ] **Isolasi Fixed Timestep**: Fisika simulasi dan state synchronization berjalan pada loop independen dari variable framerate rendering engine.
- [ ] **Quantization & Bit-packing**: Koordinat world float32 dikonversi ke signed fixed-point integer (misal: 16-bit integer dengan presisi 2 desimal) sebelum transmisi payload.

---

### 12. Hands-on Practice: Membangun authoritative state pipeline

Struktur direktori praktikum harus diorganisir sebagai berikut:
```
hands-on/m02/
├── cmd/
│   ├── client/
│   │   └── main.go
│   └── server/
│       └── main.go
├── internal/
│   ├── netcode/
│   │   ├── bitpack.go
│   │   ├── buffer.go
│   │   └── reconciliation.go
│   └── protocol/
│       └── messages.go
├── go.mod
└── README.md
```

#### Langkah Pengerjaan:
1. Inisialisasi modul Go:
   ```bash
   mkdir -p hands-on/m02/cmd/server hands-on/m02/cmd/client hands-on/m02/internal/netcode hands-on/m02/internal/protocol
   cd hands-on/m02
   go mod init enterprise-netcode
   ```
2. Implementasikan struktur paket dan kuantisasi data di `internal/protocol/messages.go`:
```go
package protocol

import "math"

// QuantizePosition mengubah float32 ke int16 untuk efisiensi transfer jaringan
func QuantizePosition(val float32, min float32, max float32) int16 {
	clamped := math.Max(float64(min), math.Min(float64(max), float64(val)))
	normalized := (clamped - float64(min)) / float64(max-min)
	return int16(normalized*65535 - 32768)
}

// DequantizePosition memulihkan float32 dari int16
func DequantizePosition(val int16, min float32, max float32) float32 {
	normalized := float64(val+32768) / 65535.0
	return float32(normalized*float64(max-min) + float64(min))
}
```

3. Jalankan server simulasi:
   ```bash
   go run cmd/server/main.go
   ```
4. Jalankan dua instans klien terpisah dengan simulasi packet latency buatan:
   ```bash
   go run cmd/client/main.go -rtt=40
   go run cmd/client/main.go -rtt=150
   ```
5. Amati dashboard log: Pastikan rekonsiliasi berjalan sukses tanpa memicu *rubber-banding loop* saat kedua klien berpapasan secara agresif.

---

### 13. Latihan Terstruktur (Exercises)

#### 13.1. Level Easy: Deteksi Desync
Buat fungsi deterministik penguji desinkronisasi:
- **Input**: Slice `clientPositions []Vector3` dan `serverPositions []Vector3` sepanjang $N$ tick.
- **Tugas**: Kembalikan tick pertama saat deviasi Euclidean distance melampaui `0.05` unit secara konsekutif selama 3 frame.
- **Ekspektasi Output**: Nilai `firstDesyncTick uint32` dan status `bool`.

#### 13.2. Level Medium: Bit-Packed Snapshot Encoder
Implementasikan encoder/decoder bit-level untuk merepresentasikan input aksi pemain:
- Input berisi: 8 tombol arah (boolean), 1 bit Status Menembak, 1 bit Status Lompat, dan Float rotasi Yaw ($0$ - $360$ derajat).
- **Tantangan**: Kompres seluruh payload state ini ke dalam maksimal **3 byte** buffer memory tanpa kehilangan akurasi rotasi lebih dari 1.5 derajat.

#### 13.3. Level Hard: Dead Reckoning with Dynamic Extrapolation
Implementasikan sistem *Dead Reckoning* pada klien untuk menangani situasi *packet loss burst* selama 250ms (3-4 frame snapshot server lenyap):
- Buat model ekstrapolasi berbasis percepatan (*acceleration-based second order kinematics*):
  $$P_{extrapolated} = P_0 + V_0 \Delta t + \frac{1}{2} A (\Delta t)^2$$
- Jika snapshot server baru akhirnya tiba, buat algoritma *blending* agar kamera klien tidak tersentak (*anti-visual glitch*).

---

### 14. Real-World Architectural Challenge

#### Konteks Kasus
Anda adalah Principal Netcode Architect pada sebuah game *competitive extraction shooter* 60 Hz dengan 64 pemain per instance match server.

#### Masalah Produksi
Terjadi eksploitasi di mana cheater sengaja melakukan *artificial outgoing packet throttling* (mematikan transmisi uplink selama 1.5 detik, berjalan memutari sudut ruangan, lalu menyemburkan seluruh paket input sekaligus). Server memproses seluruh paket input tersebut, meloloskan verifikasi lag compensation, dan membunuh musuh tanpa musuh tersebut sempat melihat cheater keluar dari sudut (*god-mode peek*).

#### Spesifikasi Tantangan Desain
Rancang dokumen arsitektur dan algoritma pseudocode komprehensif yang mencakup:
1. **Input Choke Mitigation**: Mekanisme deteksi batas akumulasi input per timeframe server dengan *Token Bucket Rate Limiting* berbasis tick deterministik.
2. **Lag Compensation Ceiling Policy**: Penanganan status tembakan jika `Timestamp` paket berada di luar batas deviasi standar sliding window RTT klien.
3. **Ghost Simulation Execution**: Bagaimana server memvalidasi pergerakan spasial pemain selama masa "koneksi terputus sengaja" tersebut tanpa merugikan pemain yang mengalami spike jitter wajar dari ISP.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konsep Dasar (Basic)
1. Apa fungsi utama *Client-Side Prediction* dalam game multiplayer berlatensi tinggi?
2. Mengapa protokol UDP secara universal lebih dipilih dibanding TCP untuk sinkronisasi state pergerakan pemain?
3. Apa perbedaan matematis antara interpolasi linear (LERP) dan interpolasi sferikal (SLERP)? Kapan SLERP mutlak dibutuhkan?
4. Apa yang dimaksud dengan *Server Reconciliation* dan komponen apa yang memicunya?
5. Mengapa snapshot history buffer pada server lag compensation umumnya diimplementasikan sebagai Circular Ring Buffer?

#### Bagian B: Analisis Menengah (Intermediate)
6. Jelaskan bagaimana *Clock Drift* antara server monotonic hardware clock dan client operating system clock dapat merusak akurasi perhitungan snapshot interpolation!
7. Jika server berjalan pada 60 Hz dan klien berjalan pada 144 Hz, jelaskan apa yang terjadi jika klien me-render state entitas tanpa algoritma interpolasi snapshot!
8. Apa kelemahan utama kompensasi lag (rewind system) dari sudut pandang korban yang ditembak (*victim perspective*)?
9. Mengapa variabel status game server tidak boleh menggunakan tipe data floating point standar (`float32`/`float64`) tanpa mitigasi determinisme pada arsitektur deterministic lockstep?
10. Bagaimana cara teknik *Delta Compression* memangkas ukuran paket data transmisi snapshot?

#### Bagian C: Skenario Produksi (Production Scenarios)
11. **Skenario 1**: Setelah merilis patch baru, 25% pemain melaporkan efek "karakter terdorong kembali ke posisi 1 detik lalu (*teleport rubber-band*)" setiap kali melompat dekat dinding. Investigasi apa yang harus Anda lakukan dan komponen arsitektur mana yang paling dicurigai gagal?
12. **Skenario 2**: Server game Anda menggunakan alokasi dinamis `map[uint32]Transform` setiap kali menyimpan snapshot tick untuk lag compensation (60 tick/detik, 64 pemain). Setelah 10 menit gameplay, CPU server mengalami lonjakan latency periodik (*stutter spikes*). Analisis penyebab utama di level memory management runtime dan berikan solusinya!
13. **Skenario 3**: Sebuah tim QA menemukan celah: Pemain dapat mempercepat laju tembakan shotgun semi-otomatis dengan mengirimkan packet tick number yang sengaja dimajukan 5 tick ke masa depan. Bagaimana arsitektur authoritative server Anda menangkal anomali temporal ini?

---

### 16. Summary & Key Takeaways

1. **Authoritative Server Rule**: Server adalah pemegang otoritas absolut. Klien tidak pernah mendeklarasikan status posisinya ke server; klien hanya mengirimkan input aksi dan waktu intent.
2. **Triad Sinkronisasi Modern**:
   - **Client-Side Prediction**: Mengatasi latensi aksi bagi pemain lokal.
   - **Entity Interpolation**: Memberikan ilusi kelancaran visual pergerakan pemain lain di masa lalu.
   - **Lag Compensation**: Membawa keadilan temporal bagi penembak tanpa meniadakan otoritas server.
3. **Zero Allocation Principle**: Loop simulasi server game pada skala tick 60-128 Hz tidak boleh menghasilkan sampah alokasi heap (*garbage collection overhead*). Gunakan flat circular pre-allocated memory pools.
4. **Temporal Boundaries**: Kompensasi lag harus memiliki batas restriksi keras (*clamp ceiling*) untuk mencegah ketidakadilan akibat manipulasi latensi tinggi oleh pemain nakal. Bandwidth, CPU, dan fairness kompetitif adalah segitiga kompromi abadi dalam rekayasa server game.