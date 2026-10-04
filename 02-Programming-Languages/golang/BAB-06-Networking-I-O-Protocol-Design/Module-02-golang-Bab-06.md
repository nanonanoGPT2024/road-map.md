# Kurikulum Kelas Enterprise: Go (Golang)
## Kategori: 02-Programming-Languages
## Bab 06: BAB-06-Networking-I-O-Protocol-Design
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Internal Go Runtime Netpoller**: Memahami konvergensi antara *system call* kernel (`epoll`, `kqueue`, `IOCP`), *Go Scheduler* ($M, P, G$), dan abstraksi non-blocking I/O pada `net.Conn`.
2. **Merancang Custom Binary Wire Protocol**: Mengembangkan protokol komunikasi biner berbasis *framing* (Length-Field Based Frame Decoder, TLV, Magic Bytes, Payload Checksum) yang aman dari serangan eksploitasi memori (*buffer overflow*, *OOM attack*).
3. **Mengeliminasi Alokasi Memori (Zero/Low-Allocation I/O)**: Mengimplementasikan manajemen *buffer* menggunakan `sync.Pool`, *ring buffer*, dan `io.Reader`/`io.Writer` pipeline untuk mencapai efisiensi *Garbage Collection* (GC) maksimal di throughput tinggi (>100k req/detik).
4. **Mengelola Siklus Hidup Socket dan Konkurensi Skala Enterprise**: Menerapkan mekanisme *backpressure*, *graceful shutdown*, TCP *keepalive tuning*, *deadline propagation*, dan penanganan *zombie connections* secara deterministik.
5. **Mendiagnosis Kegagalan Jaringan Tingkat Kernel & Aplikasi**: Menggunakan *tooling* observabilitas (`pprof`, `strace`, `tcpdump`, metrik kernel TCP socket) untuk memecahkan *head-of-line blocking*, *connection leak*, dan degradasi latensi P99.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib menguasai:
* Fundamental konkurensi Go: Goroutine lifecycle, Channels, Package `sync` (`Mutex`, `RWMutex`, `WaitGroup`, `sync.Pool`), dan Package `context`.
* Dasar-dasar I/O Streams: Abstraksi `io.Reader`, `io.Writer`, `io.Closer`, `bufio.Reader`, dan `bufio.Writer`.
* Konsep Jaringan Komputer Lanjutan: Model TCP/IP 4-Layer, TCP 3-Way Handshake, TCP Teardown (FIN/RST), TCP Sliding Window, Flow Control, Congestion Control, dan struktur Packet framing.
* Pengalaman dasar pemrograman socket Go: `net.Listen`, `net.Dial`, dan penanganan error standar I/O (`io.EOF`, `net.OpError`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Arsitektur Internal Go Netpoller
Pada bahasa pemrograman tradisional seperti C/C++ zaman awal atau arsitektur thread-per-client di Java (sebelum Project Loom), satu thread OS dipetakan ke satu koneksi TCP. Model ini memiliki batas skalabilitas karena *overhead context switching* kernel dan penggunaan memori thread stack (1-8 MB per thread).

Go mengadopsi model **$M:N$ Scheduler** (GOMAXPROCS) yang dikombinasikan secara erat dengan **Runtime Netpoller**.

```
[Userspace Go Runtime]
  Goroutine (G1) --------\
  Goroutine (G2) ---------> [ Go Scheduler (M:N) ] <---> [ OS Threads (M) ]
  Goroutine (Gn) --------/           ^
                                     |
                          [ Netpoller Subsystem ]
                                     |
=====================================|====================================
[OS Kernel]                          v
                         [ epoll / kqueue / IOCP ]
                                     |
                         [ Network Interface Card ]
```

##### Alur Eksekusi System Call:
1. Ketika sebuah Goroutine mengeksekusi `conn.Read(buf)`:
   * Runtime Go mengonfigurasi *file descriptor* (FD) socket tersebut ke mode **Non-Blocking** (`O_NONBLOCK`) sejak socket dibuat melalui fungsi `sysSocket`.
   * Go runtime mencoba melakukan pembacaan langsung menggunakan *system call* `read()`:
     * Jika data sudah tersedia di kernel socket receive buffer (`SO_RCVBUF`), data disalin ke *slice* userspace `buf`, dan Goroutine melanjutkan eksekusinya secara sinkron tanpa jeda.
     * Jika data belum ada, kernel mengembalikan error `EAGAIN` atau `EWOULDBLOCK`.
2. Penanganan `EAGAIN` oleh Runtime:
   * Goroutine tidak diblokir di level OS thread ($M$). Sebaliknya, runtime memanggil `runtime.netpollblock()`.
   * FD socket didaftarkan ke *Event Demultiplexer* kernel (`epoll_ctl` dengan flag `EPOLLIN | EPOLLOUT | EPOLLRDHUP | EPOLLET` pada Linux) yang dikelola oleh satu thread khusus Netpoller.
   * Goroutine diubah statusnya dari `_Grunning` menjadi `_Gwaiting` dengan alasan `waitReasonIOWait`, lalu diparkir (`gopark()`). Thread OS ($M$) dilepaskan dan bebas mengeksekusi Goroutine lain ($G$) yang berada di *run queue*.
3. Notifikasi Ketersediaan Data:
   * Ketika paket data tiba di NIC, kernel memicu interrupt, memproses paket pada protokol TCP/IP, dan menaruh data di `SO_RCVBUF`.
   * Pada iterasi scheduler berikutnya (atau via thread `sysmon`), Netpoller memanggil `epoll_wait()`.
   * FD yang siap dideteksi, Goroutine ($G$) yang diasosiasikan dengan FD tersebut diambil kembali, diubah statusnya menjadi `_Grunnable` via `goready()`, dan dimasukkan ke dalam *run queue* processor ($P$).
   * Goroutine bangun dari titik `conn.Read()`, membaca data yang kini sudah tersedia, dan melanjutkan instruksi aplikasi.

#### 3.2 Desain Frame Protokol Biner
Komunikasi berbasis HTTP/1.1 atau JSON-over-TCP menghasilkan *overhead* berupa:
1. *Parsing overhead*: Validasi string, escape character, dan komputasi CPU intensif.
2. *Bandwidth footprint*: Header ASCII berukuran besar.
3. *GC Pressure*: Ribuan alokasi string dan deserialisasi objek *transient*.

Arsitektur jaringan enterprise menuntut **Custom Binary Wire Protocol**. Desain protokol biner menggunakan struktur diskrit dengan ukuran field deterministik.

##### Format Anatomi Protokol Biner Enterprise:
```
+-----------------------------------------------------------------------------------+
| Field Name     | Offset (Bytes) | Size (Bytes) | Deskripsi                         |
+-----------------------------------------------------------------------------------+
| Magic Byte     | 0              | 2            | Validasi protokol (e.g., 0xCAFEB) |
| Protocol Ver   | 2              | 1            | Versi spec protokol (e.g., 0x01)  |
| Message Type   | 3              | 1            | Command ID (e.g., Heartbeat, Req) |
| Serialization  | 4              | 1            | Tipe format (0:Raw, 1:Proto, 2:MsgPack)|
| Flags          | 5              | 1            | Bitmask (Bit 0: Compressed, dsb.) |
| Stream / SeqID | 6              | 8            | Correlation ID (Multiplexing)     |
| Payload Length | 14             | 4            | Panjang byte data (Big-Endian)    |
| Header Checksum| 18             | 4            | CRC32 dari byte header (0..17)    |
| Payload Data   | 22             | N            | Konten pesan biner aktual         |
+-----------------------------------------------------------------------------------+
```

#### 3.3 Zero-Allocation Streaming Pipeline
Untuk memproses volume data masif (misal: 1 Gbps traffic), pembuatan slice *transient* secara naif di loop pembacaan socket:
```go
// ANTI-PATTERN: Menyebabkan alokasi jutaan objek di Heap per detik -> Latency Spikes akibat GC
for {
    buf := make([]byte, 4096)
    n, err := conn.Read(buf)
    // ...
}
```
harus digantikan dengan:
1. **Slab Allocation / Pooled Buffers via `sync.Pool`**: Mendaur ulang slice kapasitas tetap.
2. **Deterministic Frame Slicing**: Membaca frame header langsung ke buffer stack-allocated atau pooled array, lalu membaca *exact payload size* menggunakan `io.ReadFull`.

---

### 4. Why & What

| Dimensi | Pendekatan HTTP/JSON Standar | Pendekatan Custom Binary Protocol Engine |
| :--- | :--- | :--- |
| **Throughput (RPS)** | Moderat (10k - 50k req/sec/node) | Sangat Tinggi (>200k req/sec/node) |
| **Overhead Bandwidth**| Tinggi (Header teks berulang: 500B - 2KB) | Minimal (Fixed Header: 22 Bytes) |
| **P99 / P99.9 Latency**| Fluktuatif (GC spikes karena alokasi string/map) | Stabil & Deterministik (< 1-2 ms) |
| **Framing Boundary** | Tergantung delimiter (`\r\n\r\n` atau chunked) | Deterministic Length-Prefix Parsing |
| **Resource Footprint**| Memori tinggi per koneksi (Keepalive buffers) | Zero-Alloc per message flow via Pool |

**Kapan Menggunakannya?**
* Financial Trading Systems (LMAX, Crypto matching engine, Order Routing).
* Real-time Gaming Gateway & IoT Telemetry Ingestion Platform.
* Inter-node Cluster Synchronization (Custom Raft / Gossip protocol engine).

---

### 5. How (Workflow Detail)

Alur penanganan koneksi berkinerja tinggi:

```
[Client]                      [Go TCP Server]                 [Worker Pipeline]
   |                                 |                                |
   |---- TCP 3-Way Handshake ------->|                                |
   |                                 | (net.Listen & Accept)          |
   |                                 |--- Set Socket Options -------->| (TCP_NODELAY, KeepAlive)
   |                                 |--- Spawn Reader Goroutine ---->|
   |                                 |                                |
   |-- Binary Frame (Header+Data) -->|                                |
   |                                 |-- Get Buffer from sync.Pool -->|
   |                                 |-- io.ReadFull(Header) -------->|
   |                                 |-- Validate Magic & Checksum -->|
   |                                 |-- io.ReadFull(Payload) ------->|
   |                                 |                                |
   |                                 |-- Dispatch Job (Non-blocking)->| Dispatch to Worker Pool
   |                                 |                                |-- Process Business Logic
   |                                 |                                |-- Generate Response Frame
   |                                 |<- Push to Client Write Chan ---|
   |                                 |                                |
   |                                 |-- Write Buffer to TCP Socket ->| Flush via bufio.Writer
   |                                 |-- Return Buffer to sync.Pool --|
   |<-- Binary Frame Response -------|                                |
```

#### Langkah-langkah Pengendalian I/O:
1. **Penerimaan Socket**: Loop `Accept()` utama mendistribusikan FD langsung ke sebuah Goroutine baru. Socket dikonfigurasi dengan `SetNoDelay(true)` guna menonaktifkan Algoritma Nagle (menghilangkan latensi 40ms ACK delay).
2. **Buffer Leasing**: Goroutine mengambil *read/write scratchpad* dari `sync.Pool`.
3. **Strict Header Extraction**: Server memanggil `io.ReadFull(conn, headerBuf)` untuk menjamin seluruh byte metadata frame terkumpul sebelum payload dialokasikan.
4. **Validation & Protection Guard**:
   * Cek `Magic Byte`. Jika tidak cocok, putus koneksi seketika (*untrusted client protection*).
   * Cek `Payload Length`. Bandingkan dengan `MaxFrameSize` (misal 4MB). Jika ukuran melebihi batas, gagalkan request untuk mencegah eksploitasi kehabisan memori (*OOM Panic*).
5. **Payload Processing & Dispatch**: Data diekstraksi dan dilempar ke *worker queue* melalui channel internal atau dieksekusi secara lokal tergantung pola *backpressure*.
6. **Connection Recycling & Teardown**: Deadline I/O (`SetReadDeadline`, `SetWriteDeadline`) selalu di-refresh di setiap siklus untuk memotong *half-open connections* (koneksi mati yang tidak mengirim paket FIN).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Loket Pos Konvensional vs Saluran Pipa Pneumatik Pabrik
* **Blocking I/O Konvensional (Thread-per-client)**: Seperti loket kantor pos di mana setiap petugas pos (OS Thread) melayani satu pelanggan (Socket). Jika pelanggan sedang mencari dokumen di dompetnya (menunggu data jaringan), petugas pos harus berdiri mematung, tidak dapat melayani antrean lain di belakangnya.
* **Go Netpoller (Non-blocking I/O)**: Seperti jaringan pipa pneumatik otomatis modern. Setiap dokumen (paket data) yang masuk ke tabung stasiun diberi label. Jika tabung kosong, petugas pos (Goroutine) meninggalkannya dan mengerjakan instruksi lain. Begitu sensor mendeteksi tabung terisi (Kernel `epoll` event), bel berbunyi (`goready`), dan petugas mana pun yang menganggur langsung mengambil dokumen tersebut untuk diproses.

#### Diagram Interaksi Netpoller:
```
           +---------------------------------------------+
           |               Go Application                |
           +---------------------------------------------+
                   |                             ^
       1. Read()   |                             | 7. Return n Bytes
                   v                             |
           +---------------------------------------------+
           |        Go Runtime (Non-Blocking Syscall)     |
           +---------------------------------------------+
                   |                             ^
   2. sys_read()   | EAGAIN                      | 6. goready(G)
      returns      v                             |
           +--------------------+         +--------------------+
           |  runtime.gopark()  |         | Worker Scheduler   |
           |  G state -> WAITING|         | G state -> RUNNABLE|
           +--------------------+         +--------------------+
                   |                             ^
   3. Register FD  |                             | 5. Event Fired
                   v                             |
           +---------------------------------------------+
           |         OS Kernel (epoll/kqueue/IOCP)       |
           |   Monitors FD for EPOLLIN with edge-trigger |
           +---------------------------------------------+
                   ^                             |
                   | 4. Packet Arrives at NIC    |
           +---------------------------------------------+
           |           Physical Network / NIC            |
           +---------------------------------------------+
```

---

### 7. Implementasi Kode Teruji & Standar Industri

Berikut adalah implementasi sistem jaringan lengkap yang terdiri dari:
1. Protokol Framing Biner (*Encoder/Decoder*).
2. Pool Manajemen Buffer Berkinerja Tinggi.
3. TCP Server dengan Socket Tuning, Deadline Propagation, dan Backpressure Management.

```go
package main

import (
	"context"
	"crypto/rand"
	"encoding/binary"
	"errors"
	"fmt"
	"hash/crc32"
	"io"
	"log"
	"net"
	"os"
	"os/signal"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

// ============================================================================
// 1. PROTOCOL DEFINITIONS & SPECIFICATION
// ============================================================================

const (
	MagicBytes        uint16 = 0xCAFE
	CurrentProtocolV1 uint8  = 0x01

	// Ukuran Frame Header tetap:
	// Magic (2B) + Version (1B) + MsgType (1B) + Flags (1B) + StreamID (8B) + Length (4B) + CRC32 (4B) = 21 Bytes
	HeaderSizeBytes int = 2 + 1 + 1 + 1 + 8 + 4 + 4

	// Keamanan memori: Mencegah serangan eksploitasi alokasi payload raksasa
	MaxPayloadSizeBytes uint32 = 4 * 1024 * 1024 // 4MB
)

type MessageType uint8

const (
	MsgTypeHeartbeat MessageType = 0x00
	MsgTypeRequest   MessageType = 0x01
	MsgTypeResponse  MessageType = 0x02
	MsgTypeError     MessageType = 0xFF
)

var (
	ErrInvalidMagic   = errors.New("invalid protocol magic byte")
	ErrUnknownVersion = errors.New("unsupported protocol version")
	ErrFrameTooLarge  = errors.New("payload exceeds maximum allowed limit")
	ErrChecksumFailed = errors.New("header checksum mismatch")
)

// Frame merepresentasikan paket biner pada layer aplikasi.
type Frame struct {
	Magic      uint16
	Version    uint8
	Type       MessageType
	Flags      uint8
	StreamID   uint64
	PayloadLen uint32
	Checksum   uint32
	Payload    []byte
}

// ============================================================================
// 2. HIGH PERFORMANCE BUFFER POOL
// ============================================================================

type BufferPool struct {
	pool sync.Pool
	size int
}

func NewBufferPool(bufferSize int) *BufferPool {
	return &BufferPool{
		size: bufferSize,
		pool: sync.Pool{
			New: func() any {
				b := make([]byte, bufferSize)
				return &b
			},
		},
	}
}

func (bp *BufferPool) Get() *[]byte {
	return bp.pool.Get().(*[]byte)
}

func (bp *BufferPool) Put(b *[]byte) {
	if cap(*b) < bp.size {
		return // Hindari menyimpan buffer yang telah mengalami shrink
	}
	*b = (*b)[:bp.size]
	bp.pool.Put(b)
}

var (
	headerPool  = NewBufferPool(HeaderSizeBytes)
	payloadPool = sync.Pool{
		New: func() any {
			// Slices dialokasikan secara dinamis sesuai kebutuhan, tetapi di-pool untuk variasi umum
			b := make([]byte, 32*1024)
			return &b
		},
	}
)

// ============================================================================
// 3. CODEC ENGINE (ZERO/LOW-ALLOC ENCODER & DECODER)
// ============================================================================

type ProtocolCodec struct {
	crcTable *crc32.Table
}

func NewProtocolCodec() *ProtocolCodec {
	return &ProtocolCodec{
		crcTable: crc32.MakeTable(crc32.Castagnoli),
	}
}

// DecodeFrame membaca stream TCP dan menghasilkan objek Frame.
// Buffer payload dipinjam dari pool atau dialokasikan dengan batas MaxPayloadSizeBytes.
func (c *ProtocolCodec) DecodeFrame(r io.Reader) (*Frame, error) {
	hBufPtr := headerPool.Get()
	defer headerPool.Put(hBufPtr)
	headerBytes := *hBufPtr

	// 1. Ekstraksi Header secara persis menggunakan io.ReadFull
	if _, err := io.ReadFull(r, headerBytes); err != nil {
		return nil, err
	}

	// 2. Validasi Magic Bytes
	magic := binary.BigEndian.Uint16(headerBytes[0:2])
	if magic != MagicBytes {
		return nil, fmt.Errorf("%w: received 0x%X", ErrInvalidMagic, magic)
	}

	// 3. Validasi Version
	version := headerBytes[2]
	if version != CurrentProtocolV1 {
		return nil, fmt.Errorf("%w: version %d", ErrUnknownVersion, version)
	}

	msgType := MessageType(headerBytes[3])
	flags := headerBytes[4]
	streamID := binary.BigEndian.Uint64(headerBytes[5:13])
	payloadLen := binary.BigEndian.Uint32(headerBytes[13:17])
	checksum := binary.BigEndian.Uint32(headerBytes[17:21])

	// 4. Integritas Header via Checksum
	calculatedChecksum := crc32.Checksum(headerBytes[0:17], c.crcTable)
	if checksum != calculatedChecksum {
		return nil, ErrChecksumFailed
	}

	// 5. Memory Explosion Protection Guard
	if payloadLen > MaxPayloadSizeBytes {
		return nil, fmt.Errorf("%w: requested %d bytes", ErrFrameTooLarge, payloadLen)
	}

	// 6. Alokasi Buffer untuk Payload
	payload := make([]byte, payloadLen)
	if payloadLen > 0 {
		if _, err := io.ReadFull(r, payload); err != nil {
			return nil, fmt.Errorf("failed reading payload: %w", err)
		}
	}

	return &Frame{
		Magic:      magic,
		Version:    version,
		Type:       msgType,
		Flags:      flags,
		StreamID:   streamID,
		PayloadLen: payloadLen,
		Checksum:   checksum,
		Payload:    payload,
	}, nil
}

// EncodeFrame mengemas struct Frame menjadi byte slice dan menulisnya ke writer stream.
func (c *ProtocolCodec) EncodeFrame(w io.Writer, f *Frame) error {
	f.PayloadLen = uint32(len(f.Payload))
	f.Magic = MagicBytes
	f.Version = CurrentProtocolV1

	hBufPtr := headerPool.Get()
	defer headerPool.Put(hBufPtr)
	headerBytes := *hBufPtr

	binary.BigEndian.PutUint16(headerBytes[0:2], f.Magic)
	headerBytes[2] = f.Version
	headerBytes[3] = byte(f.Type)
	headerBytes[4] = f.Flags
	binary.BigEndian.PutUint64(headerBytes[5:13], f.StreamID)
	binary.BigEndian.PutUint32(headerBytes[13:17], f.PayloadLen)

	// Hitung Checksum
	f.Checksum = crc32.Checksum(headerBytes[0:17], c.crcTable)
	binary.BigEndian.PutUint32(headerBytes[17:21], f.Checksum)

	// Tulis Frame secara atomic ke connection layer
	// Menggunakan buffer berurutan untuk meminimalkan write syscalls
	var writeBuf []byte
	totalSize := HeaderSizeBytes + int(f.PayloadLen)

	// Mengoptimalkan I/O: Gabungkan write Header + Payload untuk menghindari latency
	if totalSize <= 65536 {
		pBufPtr := payloadPool.Get().(*[]byte)
		defer payloadPool.Put(pBufPtr)

		writeBuf = (*pBufPtr)[:totalSize]
		copy(writeBuf[0:HeaderSizeBytes], headerBytes)
		if f.PayloadLen > 0 {
			copy(writeBuf[HeaderSizeBytes:], f.Payload)
		}
		_, err := w.Write(writeBuf)
		return err
	}

	// Fallback untuk ukuran payload yang lebih besar
	if _, err := w.Write(headerBytes); err != nil {
		return err
	}
	if f.PayloadLen > 0 {
		if _, err := w.Write(f.Payload); err != nil {
			return err
		}
	}

	return nil
}

// ============================================================================
// 4. PRODUCTION-GRADE TCP SERVER
// ============================================================================

type ServerMetrics struct {
	ActiveConnections int64
	TotalRequests     uint64
	DroppedFrames     uint64
}

type TCPServer struct {
	address     string
	listener    net.Listener
	codec       *ProtocolCodec
	readTimeout time.Duration
	writeTimeout time.Duration
	maxClients  int64
	activeConns int64
	metrics     ServerMetrics
	shutdownCtx context.Context
	cancelFunc  context.CancelFunc
	wg          sync.WaitGroup
}

func NewTCPServer(addr string, maxClients int64) *TCPServer {
	ctx, cancel := context.WithCancel(context.Background())
	return &TCPServer{
		address:      addr,
		codec:        NewProtocolCodec(),
		readTimeout:  30 * time.Second,
		writeTimeout: 10 * time.Second,
		maxClients:   maxClients,
		shutdownCtx:  ctx,
		cancelFunc:   cancel,
	}
}

func (s *TCPServer) Start() error {
	var lc net.ListenConfig
	// Linux Control hook untuk kernel reuse-port (opsional, load balancing socket)
	lc.Control = func(network, address string, c syscall.RawConn) error {
		var opErr error
		err := c.Control(func(fd uintptr) {
			opErr = syscall.SetsockoptInt(int(fd), syscall.SOL_SOCKET, syscall.SO_REUSEADDR, 1)
		})
		if err != nil {
			return err
		}
		return opErr
	}

	l, err := lc.Listen(s.shutdownCtx, "tcp", s.address)
	if err != nil {
		return fmt.Errorf("failed to bind tcp listener on %s: %w", s.address, err)
	}
	s.listener = l
	log.Printf("[INFO] TCP Protocol Server initialized on %s (Max Conns: %d)", s.address, s.maxClients)

	s.wg.Add(1)
	go s.acceptLoop()

	return nil
}

func (s *TCPServer) acceptLoop() {
	defer s.wg.Done()

	for {
		conn, err := s.listener.Accept()
		if err != nil {
			select {
			case <-s.shutdownCtx.Done():
				// Normal termination triggered
				return
			default:
				log.Printf("[ERROR] Listener accept failure: %v", err)
				// Backoff transient error untuk mencegah infinite tight-loop
				time.Sleep(5 * time.Millisecond)
				continue
			}
		}

		// Backpressure & Connection Load Shedding
		if atomic.LoadInt64(&s.activeConns) >= s.maxClients {
			log.Printf("[WARN] Max connection threshold reached (%d). Rejecting: %s", s.maxClients, conn.RemoteAddr())
			atomic.AddUint64(&s.metrics.DroppedFrames, 1)
			_ = conn.Close()
			continue
		}

		// Socket Tuning: Optimize for Low-Latency Real-Time I/O
		if tcpConn, ok := conn.(*net.TCPConn); ok {
			_ = tcpConn.SetNoDelay(true)                           // Disable Nagle algorithm
			_ = tcpConn.SetKeepAlive(true)                         // Enable TCP Keepalive
			_ = tcpConn.SetKeepAlivePeriod(30 * time.Second)      // Probing interval
			_ = tcpConn.SetReadBuffer(64 * 1024)                  // 64KB OS RCVBUF
			_ = tcpConn.SetWriteBuffer(64 * 1024)                 // 64KB OS SNDBUF
		}

		atomic.AddInt64(&s.activeConns, 1)
		s.wg.Add(1)
		go s.handleConnection(conn)
	}
}

func (s *TCPServer) handleConnection(conn net.Conn) {
	defer func() {
		_ = conn.Close()
		atomic.AddInt64(&s.activeConns, -1)
		s.wg.Done()
	}()

	clientAddr := conn.RemoteAddr().String()

	for {
		select {
		case <-s.shutdownCtx.Done():
			return
		default:
		}

		// Deadline Enforcements to neutralize Zombie Connections / Slowloris
		_ = conn.SetReadDeadline(time.Now().Add(s.readTimeout))

		// 1. Decode Frame
		frame, err := s.codec.DecodeFrame(conn)
		if err != nil {
			if errors.Is(err, io.EOF) {
				// Client cleanly closed connection
				return
			}
			var netErr net.Error
			if errors.As(err, &netErr) && netErr.Timeout() {
				log.Printf("[DEBUG] Read timeout hit for client: %s", clientAddr)
				return
			}
			log.Printf("[WARN] Protocol violation/error from %s: %v", clientAddr, err)
			return
		}

		atomic.AddUint64(&s.metrics.TotalRequests, 1)

		// 2. Dispatch Logic
		if err := s.processFrame(conn, frame); err != nil {
			log.Printf("[ERROR] Failed processing frame stream=%d: %v", frame.StreamID, err)
			return
		}
	}
}

func (s *TCPServer) processFrame(conn net.Conn, req *Frame) error {
	_ = conn.SetWriteDeadline(time.Now().Add(s.writeTimeout))

	switch req.Type {
	case MsgTypeHeartbeat:
		// Ping-Pong Keepalive response
		resp := &Frame{
			Type:     MsgTypeHeartbeat,
			StreamID: req.StreamID,
			Payload:  []byte("PONG"),
		}
		return s.codec.EncodeFrame(conn, resp)

	case MsgTypeRequest:
		// Simulasi Pemrosesan Data & Respons Transaksional
		processedPayload := append([]byte("ACK: "), req.Payload...)
		resp := &Frame{
			Type:     MsgTypeResponse,
			StreamID: req.StreamID,
			Payload:  processedPayload,
		}
		return s.codec.EncodeFrame(conn, resp)

	default:
		// Unsupported Command
		resp := &Frame{
			Type:     MsgTypeError,
			StreamID: req.StreamID,
			Payload:  []byte("UNKNOWN_MESSAGE_TYPE"),
		}
		return s.codec.EncodeFrame(conn, resp)
	}
}

func (s *TCPServer) Stop() error {
	log.Println("[INFO] Commencing server graceful shutdown sequence...")
	s.cancelFunc()
	if s.listener != nil {
		_ = s.listener.Close()
	}

	// Tunggu Goroutine aktif keluar dengan batas toleransi graceful
	done := make(chan struct{})
	go func() {
		s.wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		log.Println("[INFO] All active connections processed and terminated cleanly.")
	case <-time.After(15 * time.Second):
		log.Println("[WARN] Graceful drain timeout exceeded. Force exiting.")
	}

	return nil
}

// ============================================================================
// 5. ENTRYPOINT & RUNNER
// ============================================================================

func main() {
	server := NewTCPServer("127.0.0.1:9099", 10000)

	if err := server.Start(); err != nil {
		log.Fatalf("Fatal: failed to run server: %v", err)
	}

	// Demo: Simulasi Client Terpisah
	go runClientDemo("127.0.0.1:9099")

	// Handling OS Signals for Graceful Teardown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	<-sigChan
	log.Println("\n[SIGNAL] Termination interrupt received.")
	_ = server.Stop()
}

func runClientDemo(targetAddr string) {
	time.Sleep(200 * time.Millisecond) // Tunggu server listener siap
	conn, err := net.Dial("tcp", targetAddr)
	if err != nil {
		log.Printf("[CLIENT ERROR] Dial failure: %v", err)
		return
	}
	defer conn.Close()

	codec := NewProtocolCodec()

	// Kirim 3 Request Frame
	for i := uint64(1); i <= 3; i++ {
		req := &Frame{
			Type:     MsgTypeRequest,
			StreamID: i,
			Payload:  []byte(fmt.Sprintf("OrderExecutionData_Payload_Idx_%d", i)),
		}

		if err := codec.EncodeFrame(conn, req); err != nil {
			log.Printf("[CLIENT ERROR] Encode fail: %v", err)
			return
		}

		resp, err := codec.DecodeFrame(conn)
		if err != nil {
			log.Printf("[CLIENT ERROR] Decode fail: %v", err)
			return
		}

		log.Printf("[CLIENT SUCCESS] Received from Server -> StreamID: %d, Type: 0x%X, Payload: %s",
			resp.StreamID, resp.Type, string(resp.Payload))
		time.Sleep(100 * time.Millisecond)
	}
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Gateway Telemetri Finansial (High-Frequency Trading Ingestion)
* **Konteks**: Sebuah bursa komoditas memproses jutaan *tick-data orderbook* dari 500+ entitas pialang. Gateway awalnya dibangun menggunakan REST/Websocket dengan payload JSON.
* **Gejala Masalah**:
  1. *GC Pause Extreme*: Penggunaan memori melonjak hingga 30 GB dengan waktu stop-the-world (STW) GC mencapai 35ms. Mengakibatkan antrean pesanan tertahan (*jitter* fatal pada pasar likuid).
  2. *Connection Drops*: Muncul ribuan error `connection reset by peer` di jam pembukaan pasar karena kernel backlog penuh (`syn flood protection` terpicu).
  3. Latensi P99 meleset dari target SLA 2ms, melonjak ke 120ms.

#### Akar Masalah:
1. Parsing string JSON di Goroutine membaca koneksi menghasilkan alokasi jutaan pointer kecil per detik.
2. Tidak adanya kontrol batas socket read buffer di OS level: socket buffer default terlalu kecil (sering terjadi window full dan drop paket TCP).
3. Goroutine explosion: Setiap koneksi spawn 2 goroutine yang memakan memori tanpa ada batas *concurrency limits* dan tidak ada penanganan *slow-consumer*.

#### Solusi Arsitektural Go yang Diimplementasikan:
1. **Migrasi ke Custom Binary Protocol Frame**: Seluruh skema diubah ke framing biner (Header 21-byte deterministik). Latensi serialization terpangkas dari 1,200ns ke 45ns.
2. **Buffer Pooling Mutlak**: Menerapkan `sync.Pool` untuk buffer I/O (`io.ReadFull`), menjamin alokasi *zero-heap* pada jalur utama pemrosesan stream. GC STW turun dari 35ms ke < 0.5ms.
3. **Tuning Kernel TCP Stack**:
   ```bash
   sysctl -w net.core.somaxconn=65535
   sysctl -w net.ipv4.tcp_max_syn_backlog=65535
   sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
   sysctl -w net.ipv4.tcp_wmem="4096 65536 16777216"
   ```
4. **Ring Buffer Worker Pools**: Melepaskan ketergantungan model unbounded goroutine. Koneksi mem-push paket ke *Disruptor/Ring-Buffer* antrean lock-free internal dengan kapasitas terukur. Bila antrean penuh, *backpressure* langsung menahan pembacaan FD socket (`conn.Read` dihentikan sementara, menyebabkan TCP Window menyusut dan memaksa client memperlambat transmisi paket).

---

### 9. Trade-offs Architecture Matrix

| Strategi I/O | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Goroutine-per-Connection (Model Standar Go)** | Sederhana, idiomatik, kode linier & sangat mudah di-*maintain*. Performa luar biasa untuk koneksi $\le 50,000$. | Konsumsi stack memory minimum (2 KB - 8 KB per Goroutine). Pada 1 juta koneksi idle, membutuhkan 2 - 8 GB RAM hanya untuk stack. |
| **Event-Loop Non-blocking (epoll manual via cgo / `gnet` / `evio`)** | Penggunaan memori minimal pada *massive idle connections* (C1000K problem). Stack Goroutine tereliminasi. | Menghilangkan kenyamanan library standar Go. Kompatibilitas buruk dengan library standar `net/http`. *Spaghetti state-machine* callbacks. |
| **Zero-Allocation Slicing (`sync.Pool`)** | Meniadakan tekanan Garbage Collector secara radikal, latensi P99 sangat datar dan deterministik. | Bahaya kebocoran data jika buffer dikembalikan ke pool sebelum goroutine lain selesai membaca (*Data Race* & korupsi memori). |
| **Strict Framing vs Streaming Chunking** | Parsing deterministik, validasi ukuran sebelum alokasi heap, proteksi OOM instan. | Paket yang terfragmentasi harus menunggu (`io.ReadFull`) sampai seluruh frame tiba, potensi kerentanan *Slowloris* jika tanpa deadline. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Partial Read Trap (`conn.Read` vs `io.ReadFull`)
* **Kesalahan**: Mengasumsikan `conn.Read(buf)` akan mengembalikan seluruh byte yang dikirim oleh pengirim dalam satu kali pemanggilan.
* **Realita**: TCP adalah *byte-stream*, bukan *message-stream*. Paket dapat terpotong di level MTU (1500 bytes). Jika Anda mengirim frame 4000 bytes, `conn.Read(buf)` bisa saja hanya membaca 1440 bytes pertama.
* **Solusi**: Selalu gunakan `io.ReadFull(conn, targetBuf)` untuk data dengan panjang deterministik.

#### 2. Leaking Goroutine Akibat Ketiadaan Deadline
* **Kesalahan**: Tidak menetapkan `SetReadDeadline()` pada koneksi socket.
* **Gejala Produksi**: Ketika client memutus koneksi secara tidak wajar (misal: kabel LAN dicabut, laptop mati seketika), kernel tidak mengirimkan paket FIN/RST. Goroutine `conn.Read()` akan *tergantung selamanya* (`_Gwaiting`), mengakibatkan kebocoran Goroutine masif.
* **Solusi**:
  ```go
  // Terapkan pattern rolling deadline
  conn.SetReadDeadline(time.Now().Add(heartbeatInterval * 2))
  ```

#### 3. Poisoned Buffer Reuse pada `sync.Pool`
* **Kesalahan**: Menyimpan kembali slice yang dimensinya telah dimodifikasi (misal: di-*reslice* menjadi lebih pendek) tanpa mengembalikan kapasitas aslinya.
* **Dampak**: Read berikutnya mendapatkan buffer kerdil yang memicu buffer-overflow logic atau runtime panic index out of range.
* **Solusi**: Reset slice ke kapasitas penuh sebelum ditaruh kembali: `*b = (*b)[:cap(*b)]`.

#### Checklist Troubleshooting Produksi:
* `ss -ntp | grep <port>`: Periksa status kolom `Recv-Q` dan `Send-Q`. Jika `Recv-Q` tinggi secara persisten, berarti aplikasi Go lambat membaca dari socket OS buffer.
* `pprof/goroutines`: Identifikasi jumlah goroutine yang tertahan di status `runtime.netpollblock`.
* `strace -c -p <PID>`: Pantau rasio *system call* `epoll_wait` vs `read`/`write`. Jika rasio `epoll_wait` tidak normal, terjadi context-switch thrashing.

---

### 11. Best Practices (Production Checklist)

- [ ] **TCP_NODELAY**: Wajib diaktifkan untuk koneksi RPC / interaktif guna mematikan Algoritma Nagle.
- [ ] **Rolling Read & Write Deadlines**: Terapkan batas waktu pada setiap operasi I/O; jangan pernah biarkan blocking tanpa batas waktu.
- [ ] **Defensive Payload Boundaries**: Validasi `Payload Length` dari header sebelum memanggil `make([]byte, payloadLen)`. Batasi secara keras dengan konstanta `MaxPayloadSize`.
- [ ] **Panic Isolation**: Bungkus setiap Goroutine koneksi dengan handler `recover()` untuk mencegah crash satu koneksi menjatuhkan seluruh server instance.
- [ ] **SO_REUSEPORT & Multi-Listener**: Gunakan `SO_REUSEPORT` jika perlu menjalankan multiple listener process yang mengikat port yang sama untuk skalabilitas core multiprocessor.
- [ ] **Observabilitas Metrik**: Ekspor metrik `ActiveConnections`, `TCPBytesReadTotal`, `TCPBytesWrittenTotal`, dan `MalformedFramesTotal` ke Prometheus.
- [ ] **Backpressure Circuit**: Terapkan pembatasan jumlah goroutine / worker pool, tolak koneksi dengan status `Server Busy` atau tutup socket jika batas beban terlampaui.

---

### 12. Hands-on Practice

Buatlah struktur proyek lokal berikut untuk menguji performa protokol:
```text
hands-on/m02/
├── cmd/
│   ├── client/main.go
│   └── server/main.go
├── protocol/
│   ├── codec.go
│   └── frame.go
└── go.mod
```

#### Langkah 1: Inisialisasi Modul
```bash
mkdir -p hands-on/m02/{cmd/client,cmd/server,protocol}
cd hands-on/m02
go mod init enterprise/networking
```

#### Langkah 2: Buat Modul Protokol (`protocol/frame.go`)
Salin definisi struct `Frame`, konstanta protokol, dan `ProtocolCodec` dari Seksi 7 ke dalam file `protocol/frame.go` di package `protocol`.

#### Langkah 3: Buat Server Engine (`cmd/server/main.go`)
Implementasikan server dengan membaca implementasi Seksi 7. Pastikan server memiliki graceful shutdown listener.

#### Langkah 4: Buat Benchmarking Test Client (`cmd/client/main.go`)
Bangun client multithreaded (100 goroutine simultan) yang membanjiri server dengan 10,000 pesan frame per goroutine untuk memvalidasi zero-leak buffer pool.

#### Langkah 5: Jalankan Pengujian
```bash
# Terminal 1: Jalankan Server
go run cmd/server/main.go

# Terminal 2: Pantau Metrik Koneksi
watch -n 1 'ss -tan | grep 9099'

# Terminal 3: Jalankan Load Tester Client
go run cmd/client/main.go
```

---

### 13. Exercise (Tingkat: Easy, Medium, Hard)

#### Easy
* **Tugas**: Tambahkan flag bitmask kompresi pada Header Frame.
* **Instruksi**: Gunakan bit ke-0 pada field `Flags`. Jika bit bernilai 1, enkripsi/kompresi sederhana aktif. Buat fungsi helper `IsCompressed(flags uint8) bool` dan `SetCompressed(flags *uint8, val bool)`.

#### Medium
* **Tugas**: Implementasikan Mekanisme Heartbeat Terjadwal.
* **Instruksi**: Tambahkan channel timer di client yang mengirim frame `MsgTypeHeartbeat` setiap 5 detik jika tidak ada aktivitas data. Server harus mereset timer read-deadline setiap kali menerima heartbeat, lalu membalas dengan payload `PONG`. Jika dalam 11 detik tidak ada data atau heartbeat, server harus memutus koneksi secara deterministik.

#### Hard
* **Tugas**: Sliding Window Flow Control & Multiplexing Client Engine.
* **Instruksi**: Modifikasi arsitektur client agar mampu mengirim banyak request secara asinkron lewat **satu koneksi TCP tunggal** (Multiplexing) menggunakan `StreamID` sebagai korelasi token. Respons dari server dapat diterima tidak berurutan (*out-of-order execution*), dan client harus memetakan kembali respons tersebut ke pemanggil yang benar menggunakan mekanisme channel correlation table yang aman dari *race condition* (`sync.Map` atau mutex-protected map).

---

### 14. Challenge (Studi Kasus Kompleks)

**Judul Challenge**: *Ultra-Low-Latency Zero-Copy Resilient Financial Order Ingestion Gateway*

#### Skenario:
Anda adalah Principal Architect pada perusahaan pialang saham bervolume tinggi. Anda diminta merancang sub-sistem Ingestion Gateway yang menghubungkan sistem algoritma trading internal ke bursa sentral dengan spesifikasi ketat:

1. **Throughput Target**: Mampu memproses minimum **500,000 orders/sec** pada hardware server 16 Core / 32 GB RAM.
2. **Latensi**: P99 latensi pemrosesan frame I/O di aplikasi tidak boleh melebihi **500 mikrodetik** ($\mu s$).
3. **Resilience & Backpressure**:
   * Jika downstream Order Matching Engine mengalami degradasi (antrean proses membesar), Ingestion Gateway **dilarang keras** melakukan alokasi memori tak terbatas yang berujung pada OOM crash.
   * Gateway harus memperlambat pembacaan socket TCP secara otomatis (*Backpressure via TCP Window Zero Probe*).
4. **Security Hardening**:
   * Gateway harus tahan terhadap serangan *Slowloris* (pengiriman frame 1 byte per detik).
   * Gateway harus memitigasi serangan manipulasi alokasi payload raksasa tanpa melakukan kill process.

#### Syarat Implementasi:
* Bangun sistem ini menggunakan Go standar (tanpa framework eksternal).
* Tidak boleh ada alokasi heap di jalur parsing utama (Buktikan dengan profiling `go test -benchmem`).
* Implementasikan mekanisme *graceful drain* di mana ketika sinyal SIGTERM diterima, koneksi tidak langsung diputus, melainkan menyelesaikan semua order yang sudah masuk ke buffer kernel sebelum mengakhiri proses.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Mengapa Go runtime menggunakan non-blocking I/O pada socket jaringan secara internal?**
   * *Jawaban*: Agar thread OS ($M$) tidak terblokir ketika operasi read/write menunggu ketersediaan data. Dengan non-blocking I/O, Go runtime dapat memarkir Goroutine yang menunggu dan menggunakan thread OS untuk mengeksekusi Goroutine lain.

2. **Apa fungsi utama dari pemanggilan `io.ReadFull(conn, buf)` dibandingkan `conn.Read(buf)`?**
   * *Jawaban*: `io.ReadFull` menjamin buffer terisi penuh sejumlah *length* yang diminta sebelum fungsi mengembalikan hasil, mengatasi karakteristik TCP stream yang dapat memotong paket secara arbitrer ke berbagai fragmen.

3. **Apa konsekuensi mematikan Algoritma Nagle dengan `tcpConn.SetNoDelay(true)`?**
   * *Jawaban*: Mengurangi latensi paket kecil karena paket langsung dikirim tanpa menunggu ukuran buffer penuh atau adanya ACK sebelumnya, dengan trade-off sedikit peningkatan jumlah paket IP kecil di jaringan.

4. **Bagaimana cara mencegah kebocoran memori heap saat membaca jutaan pesan pada koneksi persisten?**
   * *Jawaban*: Menggunakan buffer pooling (seperti `sync.Pool`) untuk mendaur ulang byte slice yang digunakan saat parsing, alih-alih mengalokasikan slice baru menggunakan `make([]byte, size)` di dalam loop pembacaan.

5. **Apa yang terjadi pada socket FD ketika Goroutine diparkir via `runtime.gopark` selama operasi `conn.Read`?**
   * *Jawaban*: File descriptor didaftarkan ke event loop kernel (`epoll` pada Linux) oleh Netpoller. Goroutine masuk ke status wait sampai kernel memberitahu Netpoller bahwa socket siap dibaca.

#### Intermediate (5 Soal)
6. **Jelaskan risiko arsitektur jika `Payload Length` dari header paket langsung dialokasikan ke memori tanpa validasi batas!**
   * *Jawaban*: Attacker dapat mengirim frame dengan Header palsu yang menyatakan ukuran payload adalah 2GB. Server yang naif akan mengeksekusi `make([]byte, 2*1024*1024*1024)`, yang seketika menyebabkan lonjakan alokasi memori heap, memicu OOM killer OS, dan membuat server crash.

7. **Mengapa penting untuk memanggil `SetReadDeadline` secara berulang (rolling) di setiap awal iterasi loop koneksi TCP?**
   * *Jawaban*: Jika tidak di-refresh, deadline lama akan langsung terpicu pada request berikutnya. Sebaliknya, jika deadline tidak diset sama sekali, koneksi yang mati di tengah jalan tanpa mengirim paket FIN (zombie) akan menahan Goroutine selamanya.

8. **Dalam implementasi `sync.Pool` untuk byte slice berukuran besar, apa masalah yang muncul jika kita menyimpan slice dengan ukuran yang bervariasi secara ekstrem?**
   * *Jawaban*: Masalah fragmentasi dan retensi memori heap yang tidak terduga. Objek besar yang masuk ke pool akan terus ditahan di memori sampai GC berikutnya menyapu pool, mengurangi prediktabilitas footprint memori server.

9. **Apa perbedaan mendasar antara model pemrosesan I/O Go Netpoller dengan pustaka Event-Loop murni seperti libuv (Node.js) atau Netty (Java)?**
   * *Jawaban*: Go Netpoller menyembunyikan arsitektur asynchronous callback/reactor di balik antarmuka sinkronik (Goroutine terlihat memblokir operasi baca, padahal di level kernel beroperasi secara non-blocking), memberikan keunggulan kode linier yang bersih tanpa *callback hell*.

10. **Bagaimana fenomena TCP Head-of-Line (HoL) Blocking terjadi pada custom protocol biner tunggal yang melayani banyak stream?**
    * *Jawaban*: Karena TCP menjamin transfer data strictly sequential, kehilangan satu segmen TCP di level fisik akan menahan seluruh stream lain di koneksi yang sama di kernel buffer sampai paket yang hilang di-retransmit, meskipun stream lain tersebut tidak mengalami kerusakan data.

#### Production Scenarios (3 Kasus)
11. **Kasus 1**: Pada jam sibuk, metrik server menunjukkan jumlah goroutine meningkat drastis hingga puluhan ribu dalam 5 menit, sementara throughput turun ke nol. CPU usage 100% didominasi oleh `runtime.findrunnable` dan `runtime.gcBgMarkWorker`.
    * *Analisis Diagnostik*: Terjadi alokasi memori tak terkendali di dalam handler I/O yang membebani Garbage Collector. Tingginya GC overhead memakan siklus CPU, menyebabkan Goroutine scheduler lambat memproses I/O, menghasilkan tumpukan koneksi baru yang terus menumpuk di accept queue.
    * *Langkah Solusi*: Ambil heap profile dan goroutine dump via `pprof`. Ganti alokasi dinamis dengan `sync.Pool`. Terapkan pembatasan koneksi aktif maksimum (*worker pool pattern* atau *leaky bucket* rate limiter) untuk menolak traffic sebelum GC kewalahan.

12. **Kasus 2**: Client melaporkan bahwa sesekali data yang mereka terima tertukar dengan data pengguna lain pada sistem biner streaming ber-throughput tinggi.
    * *Analisis Diagnostik*: Terjadi *Race Condition* pada level pooling buffer. Buffer yang dipinjam dari `sync.Pool` dikembalikan ke pool (`Put`) sebelum data selesai ditulis sepenuhnya ke socket wire (misalnya: operasi `w.Write` dijalankan di Goroutine terpisah tanpa sinkronisasi WaitGroup atau penguncian).
    * *Langkah Solusi*: Audit siklus hidup kepemilikan buffer (*buffer ownership lifecycle*). Buffer hanya boleh dikembalikan ke `sync.Pool` oleh pemilik terakhir setelah operasi I/O kernel dipastikan selesai sepenuhnya (*synchronous write*).

13. **Kasus 3**: Server TCP Go Anda berada di belakang Cloud Load Balancer. Koneksi terputus acak setiap 60 detik dengan error `read: connection reset by peer`, meskipun server Anda tidak menunjukkan error apa pun di log aplikasi.
    * *Analisis Diagnostik*: Load Balancer memiliki default *idle timeout* (misal: 60 detik). Jika server dan client tidak mengirimkan data dalam rentang waktu tersebut, Load Balancer memutus koneksi secara sepihak dengan mengirim paket TCP RST ke kedua belah pihak.
    * *Langkah Solusi*: Aktifkan TCP Keepalive pada socket connection di Go menggunakan `tcpConn.SetKeepAlive(true)` dan atur interval ke angka yang lebih rendah dari timeout LB, misalnya `tcpConn.SetKeepAlivePeriod(20 * time.Second)`. Tambahkan frame `Heartbeat` level aplikasi untuk mendeteksi integritas end-to-end.

---

### 16. Summary
* **Abstraksi Netpoller Go**: Menjembatani kesenjangan performa tinggi arsitektur non-blocking berbasis *event-driven* (`epoll`) dengan kesederhanaan kode sinkron menggunakan Goroutine scheduler.
* **Protokol Biner Determinik**: Menggunakan framing terstruktur (Header terukur, Magic Byte, Checksum, dan Payload Length Prefix) adalah fondasi wajib sistem komunikasi jaringan berperforma tinggi dan berlatensi ultra-rendah.
* **Disiplin Manajemen Memori**: Penggunaan `sync.Pool` dan pembacaan socket deterministik (`io.ReadFull`) meniadakan GC pause spikes yang menjadi musuh utama dari latensi P99 di sistem enterprise.
* **Hardening Socket**: Sistem produksi wajib memiliki proteksi menyeluruh: rolling timeout/deadlines, penanganan *partial read*, pembatasan kapasitas frame, serta socket options tuning (`TCP_NODELAY`, `KeepAlive`).