# Bab 01 Module 01: Topologi Jaringan Game (Authoritative Dedicated Server vs P2P) & Rekayasa Transport Layer UDP/TCP

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis (C4)** perbedaan mendasar antara topologi *Peer-to-Peer* (P2P), *Listen Server*, dan *Authoritative Dedicated Server* berdasarkan batas toleransi latensi, konsistensi data (*state consistency*), dan vektor kerentanan manipulasi memori (*cheating*).
- **Mengevaluasi (C5)** karakteristik Layer 4 Transport (*TCP, UDP, WebSockets, QUIC*) untuk menentukan protokol transmisi yang optimal sesuai kebutuhan gameplay (*fast-paced real-time* vs *turn-based*).
- **Mengidentifikasi (C2)** mekanisme *Head-of-Line (HoL) Blocking* pada TCP dan dampaknya terhadap *frame jitter* serta *tick desynchronization*.
- **Mengimplementasikan (C3)** *engine* jaringan berbasis UDP non-blocking dengan sistem *fixed-rate tick loop* menggunakan bahasa Go, yang mampu menerima input *payload*, memvalidasi batas fisika server, dan membroadcast *world snapshot* secara deterministik.
- **Mengukur (C5)** alokasi memori (*heap allocations*) dan kestabilan *tick rate* menggunakan *profiler* sistem guna mencegah *Garbage Collection (GC) pauses* pada *hot path*.

---

### 2. Introduction & High-Level Concept
Server-side game development berada pada persimpangan antara rekayasa sistem terdistribusi, komunikasi jaringan berlatensi ultra-rendah, dan simulasi fisika deterministik. Berbeda dengan server web konvensional berbasis HTTP (stateless, request-response), server game beroperasi sebagai **Continuous State Simulation Engine** (stateful, continuous real-time loop).

Analogi mendasar:
> Bayangkan sebuah pertandingan sepak bola. 
> - **Topologi P2P**: Pemain bermain tanpa wasit; setiap pemain saling mencocokkan persepsi mereka tentang apakah bola sudah melewati garis gawang. Jika satu pemain berbohong atau mengalami gangguan penglihatan (latensi/desync), integritas pertandingan runtuh.
> - **Authoritative Dedicated Server**: Wasit independen berada di tengah lapangan dan memegang satu-satunya jam resmi pertandingan serta buku catatan skor. Pemain hanya dapat menyampaikan intensi ("Saya ingin menendang bola ke arah sudut kanan atas"), namun hanya wasit yang menentukan apakah tendangan tersebut sah, di mana bola mendarat, dan siapa yang mencetak gol.

Server game bertindak sebagai wasit absolut ini: ia memegang kebenaran tunggal (*single source of truth*) dari dunia game (*world state*).

---

### 3. Why It Matters
Dalam sistem web standar (seperti *e-commerce* atau perbankan), latensi transmisi 100–300 ms dengan protokol TCP adalah hal wajar karena integritas transaksi ACID dan pengiriman paket terurut (*ordered delivery*) menjadi prioritas absolut. 

Namun pada game kompetitif real-time (*first-person shooter*, MOBA, *racing*), toleransi latensi berada pada skala **16.66 ms hingga 50 ms**. 
1. **Physical Latency Bottleneck**: Sinyal optik di serat kaca merambat sekitar $200.000\text{ km/s}$ (~$5\mu\text{s/km}$). Pulang-pergi (*Round Trip Time* / RTT) lintas benua tidak bisa dihilangkan karena batasan fisika kecepatan cahaya.
2. **Head-of-Line (HoL) Blocking Disaster**: Jika menggunakan TCP pada koneksi internet publik dengan *packet loss* 2%, TCP menahan seluruh paket berikutnya di *receive buffer* kernel sampai paket yang hilang ditransmisikan ulang. Hal ini memicu fenomena *freeze-then-teleport* (rubber-banding) yang menghancurkan pengalaman bermain.
3. **Cheating Prevention**: Klien game yang dijalankan di mesin pemain secara inheren berada di lingkungan yang tidak aman (*hostile environment*). Tanpa server yang memegang kendali simulasi (*authoritative*), pemain dapat memodifikasi nilai memori lokal (posisi, HP, amunisi) menggunakan tools seperti Cheat Engine.

---

### 4. What: Core Mechanics & Deep Architecture

#### A. Topologi Jaringan Game
1. **Peer-to-Peer (Deterministic Lockstep)**:
   - Setiap klien saling terhubung (*mesh topology*).
   - Klien hanya mengirimkan input kontrol, bukan state objek.
   - Simulasi berjalan di semua klien secara lokal. Frame $N$ hanya bisa dieksekusi jika input frame $N$ dari *seluruh* pemain telah diterima.
   - *Kelemahan*: Game berjalan selambat koneksi pemain dengan latensi paling buruk; desynchronization sulit diperbaiki; rentan terhadap serangan manipulasi state jika satu klien bertindak sebagai host logic.
2. **Listen Server (Client-Host)**:
   - Salah satu pemain bertindak ganda: sebagai klien lokal sekaligus server bagi pemain lain.
   - *Kelemahan*: Host memiliki keunggulan latensi 0 ms (*host advantage*); jika host keluar (*rage quit*), harus dilakukan migrasi host yang kompleks; IP host terekspos langsung ke publik (risiko serangan DDoS).
3. **Authoritative Dedicated Server (Standard Industri AAA)**:
   - Server berjalan sebagai aplikasi *headless* (tanpa rendering grafis) di data center atau cloud.
   - Menjalankan *fixed simulation tick-loop* (misalnya 60 Hz = 16.66 ms per tick).
   - Menerima input mentah (*unverified inputs*) dari klien, memvalidasi batasan fisika/logika permainan, mengeksekusi integrasi matematika gerak ($v = v_0 + at$, $x = x_0 + vt$), dan membroadcast *world snapshot* ke semua klien terhubung.

#### B. Anatomi Protokol Transport (OSI Layer 4)
- **TCP (Transmission Control Protocol)**:
  - Berorientasi koneksi (*Three-Way Handshake* SYN-SYN/ACK-ACK menambah RTT di awal).
  - Mengimplementasikan Nagle's Algorithm secara default (menggabungkan paket-paket kecil, memperburuk latensi kecuali disetel `TCP_NODELAY`).
  - *Reliable & Ordered*: Kehilangan 1 segmen mengunci seluruh antrean antarmuka baca aplikasi (*Head-of-Line Blocking*).
- **UDP (User Datagram Protocol)**:
  - *Connectionless*, tanpa jaminan urutan (*unordered*), tanpa jaminan tiba (*unreliable*), preservasi batas datagram (*datagram boundaries*).
  - Header minimal (8 byte vs TCP 20–60 byte), mengurangi overhead transmisi bandwidth.
  - Server game modern menggunakan UDP dan membangun **Reliability Layer selektif di atas UDP** (misal: input pergerakan dikirim *unreliable*, event kematian/chat dikirim *reliable*).
- **WebSockets / WebTransport**:
  - WebSockets: Berbasis TCP dengan framing tipis di atas HTTP. Berguna untuk web/HTML5 game atau lobby service, namun membawa seluruh kelemahan HoL TCP.
  - WebTransport: Berbasis HTTP/3 over QUIC (UDP), mendukung transmisi *unreliable datagrams* dan *reliable streams* independen langsung dari browser.

---

### 5. How: Implementation Step-by-Step

Membangun fondasi Authoritative Dedicated Game Server dengan UDP:
1. **Socket Allocation & Binding**: Buka socket non-blocking UDP pada port target (misal: `:7777`) dan tingkatkan buffer OS kernel (`SO_RCVBUF`, `SO_SNDBUF`) untuk menghindari drop paket di layer OS saat traffic spike.
2. **Memory Pool Initialization**: Alokasikan *buffer pool* menggunakan `sync.Pool` guna meminimalisasi kerja Garbage Collector (GC) akibat alokasi byte-array berulang pada siklus penerimaan paket.
3. **Deterministic Timestep Loop Setup**: Buat loop simulasi berbasis fixed timestep ($\Delta t = \text{const}$) terpisah dari loop I/O jaringan untuk menjaga determinisme kalkulasi fisika.
4. **Packet Ingestion Pipeline**: Baca datagram mentah dari socket, parse header (Sequence ID, Packet Type, Client ID), verifikasi keabsahan urutan (*monotonic sequence counter*).
5. **State Ingestion & Input Buffering**: Masukkan input klien ke dalam antrean *ring buffer* per pemain.
6. **Simulation Tick Update**:
   - Ambil input klien dari buffer.
   - Validasi batas kecepatan gerak ($| \Delta \vec{p} | \le v_{\text{max}} \times \Delta t$).
   - Mutasikan state entitas dalam memori server.
7. **Snapshot Serialization & Broadcast**:
   - Serialisasi posisi seluruh entitas ke dalam format biner kompak.
   - Kirimkan datagram state snapshot ke seluruh klien melalui socket UDP.

---

### 6. ASCII Architecture / Flow Diagram

#### Topologi Komparasi Jaringan
```
A. PEER-TO-PEER (Full Mesh)           B. AUTHORITATIVE DEDICATED SERVER
     [ Client 1 ]                          [ Dedicated Server ]
      /        \                           (Single Source of Truth)
     /          \                            /        |        \
[ Client 2 ]---[ Client 3 ]           [ Client 1 ] [ Client 2 ] [ Client 3 ]
(Tiap klien saling percaya,          (Klien hanya kirim Input;
 latency terikat link terlemah)       Server kirim verified State Snapshots)
```

#### Fenomena Head-of-Line Blocking: TCP vs UDP
```
--- TCP Transmission Stream (Reliable & Ordered) ---
Client TX:  [Packet #1] -> [Packet #2 (LOST)] -> [Packet #3] -> [Packet #4]
Kernel RX:  [Packet #1] ->       [ ??? ]      -> [Blocked]  -> [Blocked]
App Read:   Memproses #1... Menunggu retransmisi #2... 
            *STALL / JITTER TERJADI HINGGA RETRANSMISI #2 TIBA*

--- UDP Transmission Datagrams (Unreliable & Unordered) ---
Client TX:  [Packet #1] -> [Packet #2 (LOST)] -> [Packet #3] -> [Packet #4]
Kernel RX:  [Packet #1] ->       [ DROP ]     -> [Packet #3] -> [Packet #4]
App Read:   Memproses #1 -> Memproses #3 (Abaikan #2, data lama sudah usang!)
            *SIMULASI GAME TETAP REAL-TIME BERJALAN PADA 60 HZ*
```

#### Alur Eksekusi Authoritative Game Loop (Server)
```
       +-------------------------------------------------+
       |             OS UDP Receive Buffer               |
       +-------------------------------------------------+
                                | ReadMsgUDP (Non-blocking)
                                v
       +-------------------------------------------------+
       |      Worker Goroutine: Ingestion & Deserializer |
       |    (Reuse buffer from sync.Pool, validate MAC)   |
       +-------------------------------------------------+
                                |
                                v
       +-------------------------------------------------+
       |       Client Input Queue (Ring Buffer)          |
       +-------------------------------------------------+
                                |
                                v
+=================================================================+
|                      TICK LOOP (e.g. 60Hz)                      |
|                                                                 |
|   1. Akumulasi Delta Time (dt)                                  |
|   2. Pop & Validasi Input Klien (Speed-hack detection)          |
|   3. Eksekusi Simulasi Logika Fisika / Game Rules               |
|   4. Update World State (ECS / Data Oriented Structures)        |
|   5. Kompresi World State -> Snapshot Buffer                   |
+=================================================================+
                                |
                                v
       +-------------------------------------------------+
       |       UDP Outbound Broadcast (WriteToUDP)       |
       +-------------------------------------------------+
```

---

### 7. Simple Code Example (Minimalist Raw UDP Echo/Latency Probe)
Contoh dasar socket UDP di Go untuk mengukur Round Trip Time (RTT).

```go
package main

import (
	"fmt"
	"net"
	"os"
)

func main() {
	addr, err := net.ResolveUDPAddr("udp", "0.0.0.0:7777")
	if err != nil {
		fmt.Printf("Error resolving address: %v\n", err)
		os.Exit(1)
	}

	conn, err := net.ListenUDP("udp", addr)
	if err != nil {
		fmt.Printf("Error listening on UDP: %v\n", err)
		os.Exit(1)
	}
	defer conn.Close()

	fmt.Printf("[SERVER] UDP Echo Server aktif di %s\n", addr.String())

	buf := make([]byte, 1024)
	for {
		// ReadFromUDP memblokir thread hingga ada datagram masuk
		n, clientAddr, err := conn.ReadFromUDP(buf)
		if err != nil {
			fmt.Printf("Read error: %v\n", err)
			continue
		}

		// Echo kembali payload yang sama ke klien untuk kalkulasi RTT
		_, err = conn.WriteToUDP(buf[:n], clientAddr)
		if err != nil {
			fmt.Printf("Write error: %v\n", err)
		}
	}
}
```

---

### 8. Practical / Production Code Example

Di bawah ini adalah implementasi sistematis *Authoritative Dedicated Game Server Loop* di Go. Memanfaatkan buffer pooling (`sync.Pool`), fixed simulation timestep (60 Hz), safe thread locking via atomics/channels, dan validasi pergerakan (*speed-cheat prevention*).

```go
package main

import (
	"context"
	"encoding/binary"
	"fmt"
	"math"
	"net"
	"os"
	"os/signal"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

const (
	ServerPort       = 7777
	TargetTickRate   = 60
	TickDuration     = time.Second / TargetTickRate
	MaxSpeedPerSec   = 10.0 // Satuan game unit per detik
	MaxMovementDelta = MaxSpeedPerSec * (1.0 / float64(TargetTickRate))
	PayloadSize      = 20 // ClientID (uint32) + Seq (uint32) + TargetX (float32) + TargetY (float32) + Padding/CRC
)

type PlayerInput struct {
	ClientID uint32
	Sequence uint32
	TargetX  float32
	TargetY  float32
}

type PlayerState struct {
	ID       uint32
	X        float32
	Y        float32
	LastSeq  uint32
	LastAddr *net.UDPAddr
}

type GameServer struct {
	conn         *net.UDPConn
	stateMutex   sync.RWMutex
	players      map[uint32]*PlayerState
	inputQueue   chan PlayerInput
	bufferPool   *sync.Pool
	currentTick  uint64
	bytesRxTotal uint64
}

func NewGameServer(port int) (*GameServer, error) {
	addr := &net.UDPAddr{
		Port: port,
		IP:   net.ParseIP("0.0.0.0"),
	}

	conn, err := net.ListenUDP("udp", addr)
	if err != nil {
		return nil, fmt.Errorf("failed to bind UDP socket: %w", err)
	}

	// Optimasi buffer kernel: alokasikan 4MB RX buffer untuk meredam lonjakan traffic
	if err := conn.SetReadBuffer(4 * 1024 * 1024); err != nil {
		return nil, fmt.Errorf("failed to set OS read buffer: %w", err)
	}

	return &GameServer{
		conn:       conn,
		players:    make(map[uint32]*PlayerState),
		inputQueue: make(chan PlayerInput, 10000), // Buffer antrean input klien
		bufferPool: &sync.Pool{
			New: func() any {
				b := make([]byte, 512)
				return &b
			},
		},
	}, nil
}

// Network Ingestion Loop: Membaca paket dari socket secepat mungkin
func (gs *GameServer) StartNetworkIngestion(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		default:
			bufPtr := gs.bufferPool.Get().(*[]byte)
			buf := *bufPtr

			n, addr, err := gs.conn.ReadFromUDP(buf)
			if err != nil {
				gs.bufferPool.Put(bufPtr)
				continue
			}

			atomic.AddUint64(&gs.bytesRxTotal, uint64(n))

			if n < PayloadSize {
				gs.bufferPool.Put(bufPtr)
				continue // Abaikan malformed packet
			}

			// Deserialisasi input: BigEndian byte ordering
			cid := binary.BigEndian.Uint32(buf[0:4])
			seq := binary.BigEndian.Uint32(buf[4:8])
			xBits := binary.BigEndian.Uint32(buf[8:12])
			yBits := binary.BigEndian.Uint32(buf[12:16])

			input := PlayerInput{
				ClientID: cid,
				Sequence: seq,
				TargetX:  math.Float32frombits(xBits),
				TargetY:  math.Float32frombits(yBits),
			}

			gs.registerOrUpdateClient(cid, addr)

			select {
			case gs.inputQueue <- input:
			default:
				// Dropping input jika antrean overload (mencegah memory explosion)
			}

			gs.bufferPool.Put(bufPtr)
		}
	}
}

func (gs *GameServer) registerOrUpdateClient(clientID uint32, addr *net.UDPAddr) {
	gs.stateMutex.Lock()
	defer gs.stateMutex.Unlock()

	p, exists := gs.players[clientID]
	if !exists {
		gs.players[clientID] = &PlayerState{
			ID:       clientID,
			X:        0.0,
			Y:        0.0,
			LastAddr: addr,
		}
	} else {
		p.LastAddr = addr
	}
}

// Authoritative Tick Loop: Simulasi fisika independen dengan interval konstan
func (gs *GameServer) StartSimulationLoop(ctx context.Context) {
	ticker := time.NewTicker(TickDuration)
	defer ticker.Stop()

	var lastTime = time.Now()

	for {
		select {
		case <-ctx.Done():
			return
		case now := <-ticker.C:
			dt := now.Sub(lastTime).Seconds()
			lastTime = now

			gs.currentTick++
			gs.processInputs()
			gs.updatePhysics(dt)
			gs.broadcastSnapshots()
		}
	}
}

func (gs *GameServer) processInputs() {
	// Drain antrean input yang terkumpul hingga tick saat ini
	drainLen := len(gs.inputQueue)
	for i := 0; i < drainLen; i++ {
		input := <-gs.inputQueue

		gs.stateMutex.Lock()
		player, exists := gs.players[input.ClientID]
		if !exists || input.Sequence <= player.LastSeq {
			// Tolak paket out-of-order atau replay attack
			gs.stateMutex.Unlock()
			continue
		}

		player.LastSeq = input.Sequence

		// VALIDASI AUTHORITATIVE: Anti Speed-Hack
		dx := float64(input.TargetX - player.X)
		dy := float64(input.TargetY - player.Y)
		distanceReq := math.Sqrt(dx*dx + dy*dy)

		// Batasi pergerakan maksimum yang diizinkan per tick
		if distanceReq <= MaxMovementDelta {
			player.X = input.TargetX
			player.Y = input.TargetY
		} else {
			// Clamp/Koreksi posisi paksa: Normalisasi vektor dan geser sejauh batas toleransi
			ratio := MaxMovementDelta / distanceReq
			player.X += float32(dx * ratio)
			player.Y += float32(dy * ratio)
		}
		gs.stateMutex.Unlock()
	}
}

func (gs *GameServer) updatePhysics(dt float64) {
	// Logika game deterministik, kalkulasi bounds arena, environmental hazard, dll
}

func (gs *GameServer) broadcastSnapshots() {
	gs.stateMutex.RLock()
	defer gs.stateMutex.RUnlock()

	// Snapshot Payload: Tick (8 byte) + PlayerCount (2 byte) + [ID(4) + X(4) + Y(4)] * N
	packetSize := 10 + (len(gs.players) * 12)
	buf := make([]byte, packetSize)

	binary.BigEndian.PutUint64(buf[0:8], gs.currentTick)
	binary.BigEndian.PutUint16(buf[8:10], uint16(len(gs.players)))

	offset := 10
	for _, p := range gs.players {
		binary.BigEndian.PutUint32(buf[offset:offset+4], p.ID)
		binary.BigEndian.PutUint32(buf[offset+4:offset+8], math.Float32bits(p.X))
		binary.BigEndian.PutUint32(buf[offset+8:offset+12], math.Float32bits(p.Y))
		offset += 12
	}

	// Broadcast snapshot ke semua endpoint klien yang terdaftar
	for _, p := range gs.players {
		if p.LastAddr != nil {
			_, _ = gs.conn.WriteToUDP(buf, p.LastAddr)
		}
	}
}

func main() {
	server, err := NewGameServer(ServerPort)
	if err != nil {
		fmt.Printf("Fatal initialization error: %v\n", err)
		os.Exit(1)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	fmt.Printf("[SERVER] Authoritative Game Server berjalan di UDP :%d | Tick: %d Hz\n", ServerPort, TargetTickRate)

	go server.StartNetworkIngestion(ctx)
	go server.StartSimulationLoop(ctx)

	// Graceful shutdown handling
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	fmt.Println("\n[SERVER] Memulai proses shutdown sistem...")
	cancel()
	_ = server.conn.Close()
	fmt.Println("[SERVER] Socket ditutup. Server berhenti secara bersih.")
}
```

---

### 9. Edge Cases, Failure Modes & Mitigations

1. **UDP Packet Burst Loss**:
   - *Failure Mode*: 10–20 snapshot UDP berturut-turut hilang karena instabilitas ISP.
   - *Mitigation*: Gunakan *Delta Compression* (misal: RFC 1979 / Huffman / Bit-packing) yang mengacu pada *acknowledged baseline snapshot*, atau gunakan teknik *Full Snapshot Keyframe* setiap $N$ tick sekali (misalnya tiap 1 detik / 60 tick).
2. **Packet Replay Attacks & Out-of-Order Delivery**:
   - *Failure Mode*: Datagram lama tiba terlambat di server namun mengeksekusi state kadaluarsa.
   - *Mitigation*: Pasang *Monotonically Increasing Sequence Number* pada setiap paket UDP. Server memelihara sliding bit-mask (32-bit atau 64-bit) untuk menolak sequence lama atau duplikat secara instan ($O(1)$).
3. **Tick Degradation / Frame Death Spiral**:
   - *Failure Mode*: Kalkulasi simulasi server memakan waktu lebih dari 16.66 ms (misal 25 ms), menyebabkan tick tertunda dan antrean input menumpuk tanpa batas.
   - *Mitigation*: Terapkan batasan akumulasi $\Delta t$ (*clamp delta time*) maksimal (misal: `math.Min(dt, 0.1)`). Jika tick terus tertunda, jalankan sistem *Input Dropping* dan *Entity Level-of-Detail (LoD)* di server.
4. **Asymmetric NAT State Timeout**:
   - *Failure Mode*: NAT Router di pihak klien menutup port binding UDP karena klien tidak mengirim data selama 30 detik.
   - *Mitigation*: Mekanisme heartbeat UDP reguler (*Keep-alive ping*) setiap 5–10 detik dari klien ke server.

---

### 10. Trade-offs & Alternatives Matrix

| Parameter / Fitur | Peer-to-Peer (Lockstep) | Listen Server | Dedicated Authoritative Server |
| :--- | :--- | :--- | :--- |
| **Biaya Infrastruktur** | Sangat Rendah (Nol server cost) | Nol (Pemain menjadi host) | **Tinggi** (Perlu compute nodes 24/7) |
| **Integritas / Anti-Cheat** | Sangat Buruk (Memory reading / sync cheat) | Buruk (Host memegang data absolut) | **Maksimal** (Hostile client mitigation) |
| **Distribusi Latensi** | Dibatasi oleh klien terlambat | Tidak adil (Host latensi 0 ms) | Fair & terprediksi (Bergantung rute DC) |
| **Kebutuhan Bandwidth Server**| 0 bps | Ditanggung sepenuhnya oleh Host | **Sangat Tinggi** ($O(N \times M)$ data out) |
| **Privasi Pemain (DDoS)** | Rendah (IP terekspos antar peer) | Rendah (IP host terbuka) | **Tinggi** (Hanya IP server yang terekspos) |

#### Komparasi Layer 4 Transport

| Metrik | TCP | Raw UDP | WebSockets | WebTransport (QUIC) |
| :--- | :--- | :--- | :--- | :--- |
| **Head-of-Line Blocking** | **Ya** (Kritis) | **Tidak** | **Ya** (Di layer TCP) | **Tidak** (Datagram stream) |
| **Header Overhead** | 20-60 Bytes | **8 Bytes** | 2-14 Bytes + TCP overhead | Minimal framing over UDP |
| **Pengiriman Terurut** | Ya (Enforced OS) | Opsional (Custom Logic) | Ya (Enforced OS) | Dukungan ganda (Stream / Datagram)|
| **Dukungan Browser** | Native Socket via Flash/Plug (Obsolete) | Tidak didukung langsung | **Didukung Penuh** | Didukung (Modern Browser) |
| **Penggunaan Ideal** | Lobby, Matchmaking, Turn-based | Real-time FPS, MOBA, Racing | Web Game Kasual | Web Game Real-time generasi baru |

---

### 11. Security & Anti-Cheat / Integrity Considerations

1. **Prinsip Utama: "The Client is in the Hands of the Enemy"**:
   - Klien tidak boleh mengirimkan state absolut dunia game (misal: "Saya sekarang berada di posisi X, Y, Z dan membunuh musuh B").
   - Klien hanya diizinkan mengirimkan **Intensi/Input** (misal: "Saya menekan tombol arah maju, dan menembak ke sudut rotasi $\theta$"). Server melakukan raycasting/physic simulation untuk menentukan apakah tembakan mengenai musuh.
2. **UDP Amplification & Reflection Mitigation**:
   - Server UDP game tidak boleh merespons datagram dari klien yang belum diotentikasi dengan payload yang ukurannya lebih besar daripada request yang diterima.
   - Gunakan skema **Handshake Token / Stateless Connect Challenge**: Server mengirimkan cookie kriptografis kecil yang wajib dikirim kembali oleh klien sebelum socket state dialokasikan.
3. **Sequence Counter & Tamper Resistance**:
   - Lindungi payload UDP menggunakan HMAC-SHA256 atau AES-GCM tag jika game mengekspos transaksi ekonomi sensitif secara live.
   - Lindungi dari *replay attack* dengan menolak paket dengan `SequenceID <= LastReceivedSequenceID`.

---

### 12. Performance & Memory Profiling

Dalam server game dengan target 60 Hz, server memiliki batas waktu keras **16.66 milidetik** untuk menyelesaikan seluruh loop. Satu kali siklus GC pause sebesar 30 ms akan menyebabkan *tick hitch*, yang dirasakan ratusan pemain secara bersamaan sebagai desinkronisasi.

#### Profiling Hot Path di Go
- Gunakan `sync.Pool` untuk semua alokasi buffer receive/send. Jangan gunakan slice dinamis `make([]byte, size)` di dalam loop I/O.
- Matikan alokasi heap tak terlihat (*escape analysis check*):
  ```bash
  go build -gcflags="-m -m" . 2>&1 | grep "escapes to heap"
  ```
- Hindari penggunaan pointer berlebihan pada struct berukuran kecil untuk mempertahankan cache locality pada CPU (L1/L2 cache). Gunakan format *Data-Oriented Design (DoD)* atau flat arrays/slices dibanding representasi linked-nodes/deep-object trees.
- Analisis profil CPU dan heap memori secara real-time:
  ```go
  import _ "net/http/pprof"
  go func() {
      log.Println(http.ListenAndServe("localhost:6060", nil))
  }()
  ```

---

### 13. Observability, Metrics & Telemetry

Metrik kunci yang wajib dipaparkan ke dashboard sistem monitoring (seperti Prometheus & Grafana):

1. **Server Tick Duration (Histogram)**: Waktu aktual yang dihabiskan untuk memproses satu tick simulasi.
   - P99 < 10 ms (sehat untuk target tick 16.66 ms).
   - Nilai mendekati 16 ms mengindikasikan server mendekati kapasitas komputasi jenuh.
2. **Packet Processing Rate (Counter)**:
   - `udp_packets_in_total` vs `udp_packets_out_total`.
3. **Drops & Desync Counter (Counter)**:
   - `player_input_rejected_speed_total`: Frekuensi koreksi posisi klien (indikasi adanya pemain dengan lag parah atau upaya manipulasi speed cheat).
   - `input_queue_dropped_total`: Indikasi thread worker CPU bottleneck.
4. **Kernel Socket Drops**:
   - Pantau metrik Linux UDP socket buffer drop:
     ```bash
     cat /proc/net/snmp | grep -w Udp
     # Perhatikan kolom UdpInErrors dan RcvbufErrors
     ```

---

### 14. Testing & Verification Strategies

#### Pengujian Simulasi Emulasi Latensi dan Packet Loss
Jangan menguji game server di interface `localhost` (`127.0.0.1`) tanpa rekayasa degradasi jaringan. Gunakan utility Linux Traffic Control (`tc`) atau tools seperti `Toxiproxy`.

```bash
# Tambahkan latency 80ms dengan variasi jitter 15ms dan packet loss 5% pada loopback adapter
sudo tc qdisc add dev lo root handle 1: netem delay 80ms 15ms loss 5%

# Verifikasi konfigurasi
sudo tc qdisc show dev lo

# Bersihkan rule setelah selesai pengujian
sudo tc qdisc del dev lo root
```

#### Headless Load Testing Bot (Go Test Script)
Buat tool terpisah yang melakukan instansiasi 500 koneksi bot concurrent untuk membanjiri game server dengan input deterministik guna mengukur ketahanan socket buffer dan CPU utilization under load.

---

### 15. Cross-Platform & Infrastructure Constraints

1. **Virtualization Jitter ("Noisy Neighbors")**:
   - Server game real-time sangat sensitif terhadap *CPU Steal Time* pada infrastruktur Cloud VM publik multi-tenant (AWS t-series atau standard droplet). Gunakan *Dedicated/Compute-Optimized Instances* (misal: AWS c6i/c7g metal atau dedicated vCPU) dengan *CPU pinning*.
2. **Maximum Transmission Unit (MTU) Bounds**:
   - Standar internet MTU adalah **1500 bytes**.
   - Header IP (20 bytes) + UDP Header (8 bytes) = 28 bytes.
   - Ukuran payload maksimal yang aman dari fragmentasi IP level router adalah:
     $$\text{Safe Payload} = 1500 - 28 = 1472\text{ bytes}$$
   - Praktik standar industri membatasi ukuran packet datagram server game di kisaran **1200 - 1300 bytes** untuk mengakomodasi enkapsulasi layer tunneling tambahan (seperti PPPoE atau VPN). Fragmentasi IP adalah musuh utama karena jika 1 fragmen hilang, seluruh paket datagram dibuang oleh OS.

---

### 16. Best Practices & Code Smells

#### Good Practices
- Gunakan **Fixed Simulation Timestep** untuk kalkulasi fisika (jangan gunakan variable delta time murni berbasis waktu frame, karena variable timestep menghasilkan integrasi gerak non-deterministik antar mesin).
- Pisahkan secara tegas loop pembacaan socket jaringan dari loop pemrosesan game tick menggunakan channel atau antrean *lock-free ring buffer*.
- Buat format serialisasi custom berbasis biner murni (*little/big-endian packed bytes*) atau format performa tinggi (FlatBuffers). Hindari JSON, XML, atau string parsing pada transmisi real-time gameplay.

#### Code Smells to Avoid
- **Smell: Allocating inside the Tick Path**: Melakukan alokasi array atau object baru di dalam `updatePhysics()` atau `broadcastSnapshots()`. Ini memicu Garbage Collection cycle mendadak.
- **Smell: Trusting Client Collisions**: Membiarkan klien memutuskan kapan peluru miliknya mengenai musuh (*Client-authoritative hit detection*) tanpa verifikasi server-side validation / lag compensation.
- **Smell: Blocking Socket Reads inside Simulation Tick**: Memanggil pembacaan I/O blocking di tengah-tengah loop simulasi frame.

---

### 17. Real-World Case Study
**Transisi Insurgency / CS:GO / Valorant Network Model**:
Pada awal pengembangan game berbasis First-Person Shooter, model Client-Side Authoritative sering memicu maraknya eksploitasi *Teleportation Hacks* dan *Speed Hacks*. 

Riot Games saat merancang arsitektur jaringan untuk *Valorant* menetapkan standar:
- Seluruh pergerakan diproses secara **Server-Authoritative pada 128 Hz**.
- Server menolak seluruh modifikasi posisi dari klien. Klien hanya mengirimkan input keyboard (`W, A, S, D`) dan event lompat.
- Untuk mengeliminasi keuntungan pemain dengan koneksi lambat yang menyerang sudut (*Peeker's Advantage*), server secara agresif membatasi buffer input maksimal sebesar 72 ms.
- Arsitektur ini menuntut server didesain di platform C++/Go dengan optimasi epoll kustom dan penempatan container di edge network (AWS Outposts / Bare-metal custom data center) guna menjamin kestabilan tick loop tanpa jitter dari layer virtualisasi OS.

---

### 18. Self-Assessment / Hands-On Challenges

1. **Challenge 1: Monotonic Sequence Ingestion Filter**:
   - Modifikasi kode Go pada Bab 8 dengan menambahkan struct tracking sequence berbasis bitmask 32-bit.
   - Server harus mampu menerima paket out-of-order dalam batas jendela 32 paket terakhir, namun menolak paket yang berada di luar rentang jendela tersebut atau paket duplikat.
2. **Challenge 2: The "Speed-Hacker" Adversarial Bot**:
   - Buat klien dummy menggunakan script Go terpisah yang mengirimkan koordinat target yang bergerak 10 kali lebih cepat daripada `MaxSpeedPerSec`.
   - Pastikan server berhasil mendeteksi anomali ini, melakukan *clamping* pergerakan secara matematis, dan mencatat log warning fraud detection.
3. **Challenge 3: Profiling & Zero-Allocation Serialization**:
   - Ubah fungsi `broadcastSnapshots()` agar tidak melakukan alokasi buffer baru (`buf := make([]byte, packetSize)`) setiap tick.
   - Gunakan `sync.Pool` atau reusable write-buffer terisolasi untuk mencapai **0 allocs/op** pada path serialisasi dan broadcast.

---

### 19. Troubleshooting Guide

| Gejala Masalah | Penyebab Utama (*Root Cause*) | Solusi Tindakan |
| :--- | :--- | :--- |
| Klien mengalami efek *rubber-banding* konstan meskipun ping rendah. | 1. Algoritma speed-validation di server terlalu ketat terhadap deviasi floating point.<br>2. Adanya thread lock contention di state server. | Bandingkan floating-point dengan epsilon toleransi ($10^{-4}$); kurangi lock contention dengan pemisahan Read/Write mutex atau arsitektur Actor. |
| Server crash atau memory leak seiring berjalannya waktu. | Channel `inputQueue` penuh atau objek dialokasikan di loop tanpa pernah di-release oleh GC. | Tambahkan policy *drop oldest packet* jika queue overload; gunakan static buffer arrays; jalankan `go tool pprof -heap`. |
| Paket UDP drop masif di level host saat player count meningkat. | Kernel RX socket buffer OS Linux terlalu kecil (`net.core.rmem_default`). | Tingkatkan buffer OS via sysctl: `sysctl -w net.core.rmem_max=26214400` dan panggil `conn.SetReadBuffer()`. |
| Simulasi game melambat saat jumlah entitas bertambah. | Bottleneck kalkulasi $O(N^2)$ pada collision checking di thread simulasi. | Terapkan algoritma *Spatial Partitioning* (Grid Hashing, Quadtree, atau BVH) untuk memangkas kalkulasi collision menjadi $O(N \log N)$. |

---

### 20. Summary & Next Steps

Pada modul ini, kita telah membedah fondasi rekayasa server-side game:
- Memahami mengapa **Authoritative Dedicated Server** adalah fondasi mutlak bagi game kompetitif multiplayer modern untuk mencegah cheating dan memastikan keadilan kompetitif.
- Menganalisis kelemahan fatal **Head-of-Line Blocking** pada TCP serta bagaimana **UDP** memberikan kontrol transmisi latensi rendah.
- Mengimplementasikan dasar arsitektur server UDP non-blocking dengan sistem *fixed-rate tick loop* dan validasi pergerakan anti-cheat.

#### Jembatan ke Modul Berikutnya:
Dengan adanya latensi jaringan (RTT), posisi yang dilihat klien akan selalu berada di masa lalu dibandingkan server, menyebabkan kontrol game terasa *sluggish* atau delay jika tidak diantisipasi. 
Pada **Bab 01 Module 02**, kita akan membedah dan mengimplementasikan algoritma kompensasi jaringan mutakhir: **Client-Side Prediction, Server Reconciliation, Interpolation, dan Dead Reckoning**.