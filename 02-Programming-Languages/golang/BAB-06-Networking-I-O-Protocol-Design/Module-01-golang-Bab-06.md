---

# SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: GOL-06-01
* **Kategori**: 02-Programming-Languages / Advanced Go
* **Judul Modul**: Networking, I/O & Protocol Design
* **Tingkat Kesulitan**: Advanced
* **Prasyarat**:
  * Penguasaan Go Concurrency (`goroutine`, `channel`, `sync.Pool`, `sync.WaitGroup`).
  * Pemahaman sistem operasi: File Descriptor (FD), System Calls (`read`, `write`, `epoll`/`kqueue`), TCP/IP Stack.
  * Pemahaman manipulasi bit, byte, dan memori (`byte slice`, `unsafe.Pointer`, `encoding/binary`).
* **Estimasi Waktu Belajar**: 8–10 Jam
* **Target Capaian**: Menguasai arsitektur low-level networking Go, runtime netpoller, abstraksi `io.Reader`/`io.Writer`, mitigasi jebakan stream-oriented TCP, perancangan dan implementasi protokol biner proprietary kustom dengan performa tinggi (*low-allocation*).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:
1. **Menganalisis** siklus hidup I/O jaringan Go melalui abstraksi Runtime Netpoller (`epoll`/`kqueue`/`IOCP`) dan perbedaannya dengan model *thread-per-connection* tradisional.
2. **Mengimplementasikan** pola streaming I/O berbasis antarmuka `io.Reader`, `io.Writer`, dan variasinya (`io.ReadFull`, `io.LimitReader`) secara benar tanpa asumsi ukuran *chunk*.
3. **Merancang** protokol biner *application-layer* berbasis *framing* (misal: *Length-Prefixed Framing*) yang tahan terhadap fragmentasi paket TCP dan serangan *packet injection*.
4. **Mencegah** kebocoran sumber daya (*goroutine leak*, *file descriptor exhaustion*, dan *unbounded memory allocation*) dengan menerapkan *deadline management*, mitigasi Slowloris, dan alokasi memori terkontrol menggunakan `sync.Pool`.
5. **Mengembangkan** server TCP *production-ready* yang mengimplementasikan *graceful shutdown*, pembatasan beban (*rate limiting/concurrency bounding*), serta pemantauan metrik I/O secara langsung.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model 1: TCP adalah Stream Byte, Bukan Paket Pesan
TCP tidak memiliki konsep "satu kali `Write` = satu kali `Read`". TCP adalah pipa air yang mengalirkan byte berurutan tanpa pembatas bawaan. Jika pengirim mengeksekusi `conn.Write([]byte("HALO"))` sebanyak dua kali, penerima dapat membaca:
* Satu blok 8 byte: `"HALOHALO"`
* Dua blok terpisah: `"HALO"` lalu `"HALO"`
* Tiga blok arbitrer: `"HA"`, `"LOHA"`, `"LO"`

Mengabaikan fakta ini adalah penyebab utama *intermittent bugs* pada aplikasi jaringan. Protokol aplikasi bertanggung jawab secara eksplisit menentukan batas pesan (*framing*).

```
Pengirim: [ WRITE: 4B ] [ WRITE: 4B ]
                │           │
TCP Pipeline:   ▼           ▼
             [ H | A | L | O | H | A | L | O ]  <-- Aliran Byte Kontinu
                                    │
Penerima:    [ READ: 2B ] [ READ: 5B ] [ READ: 1B ]
               "HA"         "LOHAL"       "O"
```

### Mental Model 2: Netpoller — Abstraksi Sinkron di atas I/O Asinkron
Dalam bahasa seperti C/C++, pengembang sering memilih antara model blokir sinkron (*multi-threaded blocking I/O*, boros memori) atau *non-blocking event-loop* asinkron (*callback-hell* / *state machine complexity* via `epoll`). 

Go menggabungkan keunggulan keduanya:
* **Pengalaman Menulis Kode**: Bersih, sekuensial, dan sinkron (`conn.Read(buf)` memblokir goroutine).
* **Fakta Eksekusi di Kernel**: Asinkron murni (*non-blocking* OS FD). Runtime Go memarkir (*park*) goroutine yang menunggu I/O tanpa memblokir *OS Thread* (`M`), memindahkan `M` untuk mengeksekusi goroutine (`G`) lain. Notifikasi kesiapan FD dikelola oleh Netpoller berbasis `epoll`/`kqueue`.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Arsitektur Go Runtime Netpoller

```
+-------------------------------------------------------------------+
|                        Go Application Code                        |
|                                                                   |
|   Goroutine 1 (G1)                  Goroutine 2 (G2)              |
|   n, err := conn.Read(buf)          n, err := conn.Write(buf)     |
+-------------------------------------------------------------------+
             │                                     ▲
   (EAGAIN / Blocks)                      (Notified / Runnable)
             ▼                                     │
+-------------------------------------------------------------------+
|                         Go Runtime Engine                         |
|                                                                   |
|   gopark()                               goready()                |
|   G1 diubah ke status _Gwaiting          G2 diubah ke _Grunnable  |
|   M dilepaskan untuk G lain              M dimasukkan ke Run Queue|
+-------------------------------------------------------------------+
             │                                     ▲
      netpoll_arm()                         netpoll_poll()
             ▼                                     │
+-------------------------------------------------------------------+
|                   Operating System Kernel (OS)                    |
|                                                                   |
|   Linux: epoll_ctl(EPOLLIN/OUT)                                   |
|   Darwin/BSD: kqueue(EVFILT_READ/WRITE)                           |
|   Windows: IOCP (I/O Completion Ports)                            |
+-------------------------------------------------------------------+
```

### 2. Siklus Hidup Frame Protokol Kustom (Length-Prefixed)

```
+---------------+----------------+--------------------------------------+
|  Magic (2B)   |  MsgType (1B)  | Payload Length (4B) | Payload (N-B)  |
|  0xDEAD       |  0x01 (PING)   | 0x00000008 (8 Bytes)| [Data...]      |
+---------------+----------------+--------------------------------------+
        │               │                  │                   │
        │               │                  │                   └─ Step 4: io.ReadFull(conn, payloadBuf)
        │               │                  └─ Step 3: uint32 = BigEndian(LengthBytes)
        │               └─ Step 2: Validasi Tipe Pesan
        └─ Step 1: io.ReadFull(conn, headerBuf[:2]) & Verifikasi Integritas
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Runtime Netpoller (`runtime/netpoll.go`)
Ketika soket TCP diinisialisasi melalui `net.Dial` atau `net.Listen`:
1. Soket dibuat secara default dalam mode *non-blocking* menggunakan flag OS (`O_NONBLOCK`).
2. File Descriptor (FD) didaftarkan ke sub-sistem polling OS menggunakan fungsi runtime `netpollopen(fd uintptr, pd *pollDesc)`.
3. Pada Linux, ini memanggil `epoll_ctl(epfd, EPOLL_CTL_ADD, fd, &ev)`.

Ketika aplikasi memanggil `conn.Read()`:
1. `internal/poll.FD.Read` mengeksekusi system call `read(fd, p)`.
2. Jika data tersedia di buffer kernel, syscall langsung mengembalikan jumlah byte terbaca (`n, nil`).
3. Jika buffer kernel kosong, syscall mengembalikan galat `EAGAIN` atau `EWOULDBLOCK`.
4. Runtime Go mendeteksi galat ini dan mengeksekusi `pd.wait('r', false)` di `internal/poll/fd_poll_runtime.go`.
5. Goroutine diparkir (`runtime.gopark`), statusnya diubah menjadi `_Gwaiting`, dan asosiasi FD dimasukkan ke pemantauan Netpoller.
6. Saat paket TCP tiba di interface jaringan, kernel membangunkan *sysmon* atau thread OS yang mengeksekusi `runtime.netpoll()`. Netpoller menandai G sebagai `_Grunnable` via `goready(g)`. Scheduler Go (`Go Scheduler`) memasukkan kembali G ke *run queue* untuk melanjutkan eksekusi `read(fd, p)`.

### Abstraksi `net.Conn` dan `net.FD`
* `net.Conn` adalah antarmuka yang membungkus pointer `*net.netFD`.
* `net.netFD` menyematkan struct `poll.FD`.
* `poll.FD` memiliki properti krusial:
  * `sysfd`: Raw OS file descriptor integer.
  * `pd`: Poller descriptor (penghubung runtime netpoller).
  * `rt`, `wt`: Timer untuk *Read Deadline* dan *Write Deadline*.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Semantik Streaming I/O: `io.Reader` dan `io.Writer`

Antarmuka `io.Reader` didefinisikan sebagai:
```go
type Reader interface {
    Read(p []byte) (n int, err error)
}
```
Aturan krusial implementasi & konsumsi:
* `Read` membaca hingga `len(p)` byte ke dalam `p`.
* Fungsi mengembalikan `n` (0 <= `n` <= `len(p)`) dan error yang ditemui.
* **Hukum Utama:** Jika `n > 0`, data harus diproses terlebih dahulu sebelum mengecek `err == io.EOF`. Banyak pembaca mengembalikan `n > 0` bersamaan dengan `io.EOF` pada potongan terakhir stream.
* Jangan pernah berasumsi `Read` akan mengisi penuh buffer `p` meskipun stream belum habis. Untuk membaca tepat sejumlah byte tertentu, **wajib** menggunakan `io.ReadFull` atau `io.ReadAtLeast`.

### 2. Desain Protokol Jaringan Aplikasi
Tiga pendekatan umum dalam menentukan batas frame (framing) pada layer aplikasi:

| Tipe Framing | Mekanisme | Keunggulan | Kelemahan |
| :--- | :--- | :--- | :--- |
| **Delimiter-based** | Karakter khusus (misal `\r\n` pada HTTP/1.1 atau `\0`) | Sederhana, *human-readable* | Rawan *delimiter injection*, memerlukan *escaping* byte payload, inefisien untuk payload biner. |
| **Fixed-size** | Ukuran setiap pesan konstan (misal: 64 byte) | Sangat mudah di-*parse* | Tidak fleksibel; memboroskan bandwidth jika data kecil (*padding*), membatasi data besar. |
| **Length-prefixed** | Header ukuran tetap menyertakan panjang payload | Sangat efisien, ramah data biner, *zero-copy friendly* | Membutuhkan alokasi dinamis berbasis header; rawan serangan OOM jika *length* tidak divalidasi. |

### 3. Endianness (Byte Ordering)
Dalam komunikasi jaringan, protokol standar menggunakan **Big-Endian** (*Network Byte Order*), di mana byte paling signifikan (*Most Significant Byte/MSB*) diletakkan pada alamat memori terendah. Arsitektur x86/x64 dan modern ARM menggunakan **Little-Endian**. Go menyediakan package `encoding/binary` untuk konversi deterministik:
* `binary.BigEndian.Uint32(b)`
* `binary.BigEndian.PutUint32(b, val)`

### 4. Manajemen Deadline vs Context
* `conn.SetDeadline(t)` menentukan batas absolut waktu untuk pembacaan dan penulisan di masa depan.
* `conn.SetReadDeadline(t)` dan `conn.SetWriteDeadline(t)` mengisolasi operasi I/O.
* Deadline **bukan** batas durasi (*timeout*), melainkan *point-in-time* absolut (`time.Time`). Jika batas waktu tercapai, operasi I/O akan langsung gagal dan mengembalikan error yang memenuhi `os.ErrDeadlineExceeded` (atau `net.Error` dengan `Timeout() == true`).
* Reset deadline: `conn.SetDeadline(time.Time{})` menghapus batas waktu (menjadi tak terbatas).

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi *Protocol Codec* biner berbasis *Length-Prefixed Framing*.

```
Format Paket Protokol:
+---------------+---------------+-------------------+----------------------+
| Magic (2B)    | Version (1B)  | Length (4B, BE)   | Payload (Length-B)   |
| 0xAA 0x55     | 0x01          | uint32            | byte slice           |
+---------------+---------------+-------------------+----------------------+
Total Header Size: 7 Bytes.
```

### File: `protocol/frame.go`

```go
package protocol

import (
	"encoding/binary"
	"errors"
	"fmt"
	"io"
)

const (
	MagicByte1       = 0xAA
	MagicByte2       = 0x55
	CurrentVersion   = 0x01
	HeaderSize       = 7
	MaxPayloadLength = 4 * 1024 * 1024 // Batasi maks 4MB untuk mencegah OOM
)

var (
	ErrInvalidMagic   = errors.New("invalid protocol magic bytes")
	ErrInvalidVersion = errors.New("unsupported protocol version")
	ErrPayloadTooLarge = errors.New("payload exceeds maximum allowed size")
)

type Frame struct {
	Version uint8
	Payload []byte
}

// Encode menulis Frame ke dalam io.Writer dengan layout biner terstandarisasi.
func Encode(w io.Writer, payload []byte) error {
	payloadLen := len(payload)
	if payloadLen > MaxPayloadLength {
		return ErrPayloadTooLarge
	}

	header := make([]byte, HeaderSize)
	header[0] = MagicByte1
	header[1] = MagicByte2
	header[2] = CurrentVersion
	binary.BigEndian.PutUint32(header[3:7], uint32(payloadLen))

	// Tulis header terlebih dahulu
	if _, err := w.Write(header); err != nil {
		return fmt.Errorf("gagal menulis frame header: %w", err)
	}

	// Tulis payload jika ada
	if payloadLen > 0 {
		if _, err := w.Write(payload); err != nil {
			return fmt.Errorf("gagal menulis frame payload: %w", err)
		}
	}

	return nil
}

// Decode membaca satu Frame lengkap dari io.Reader.
func Decode(r io.Reader) (*Frame, error) {
	headerBuf := make([]byte, HeaderSize)
	
	// Wajib gunakan ReadFull untuk menjamin seluruh komponen header terbaca utuh
	if _, err := io.ReadFull(r, headerBuf); err != nil {
		return nil, err // Error mencakup io.EOF atau io.ErrUnexpectedEOF
	}

	// Validasi Magic Bytes
	if headerBuf[0] != MagicByte1 || headerBuf[1] != MagicByte2 {
		return nil, ErrInvalidMagic
	}

	// Validasi Versi
	version := headerBuf[2]
	if version != CurrentVersion {
		return nil, ErrInvalidVersion
	}

	// Ekstraksi Ukuran Payload
	payloadLen := binary.BigEndian.Uint32(headerBuf[3:7])
	if payloadLen > MaxPayloadLength {
		return nil, ErrPayloadTooLarge
	}

	payload := make([]byte, payloadLen)
	if _, err := io.ReadFull(r, payload); err != nil {
		return nil, fmt.Errorf("gagal membaca payload: %w", err)
	}

	return &Frame{
		Version: version,
		Payload: payload,
	}, nil
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis komponen kritis dari `protocol/frame.go`:

1. `MaxPayloadLength = 4 * 1024 * 1024`:
   * **Mengapa penting:** Mencegah serangan *denial of service* (DoS) berbasis konsumsi memori. Jika klien jahat mengirimkan *header* dengan ukuran payload `0xFFFFFFFF` (4 GB), server tanpa batas maksimum akan mencoba mengalokasikan 4 GB RAM secara instan melalui `make([]byte, payloadLen)`, memicu *Out-Of-Memory* (OOM) panic.
2. `header[0] = MagicByte1; header[1] = MagicByte2`:
   * Pola sinkronisasi awal. Membantu parser memverifikasi bahwa *stream* yang diterima benar-benar menggunakan protokol yang sesuai, bukan koneksi liar seperti scanner port TLS/HTTP.
3. `binary.BigEndian.PutUint32(header[3:7], uint32(payloadLen))`:
   * Mengubah integer ukuran sistem lokal ke dalam representasi Big-Endian 4-byte secara deterministik.
4. `_, err := io.ReadFull(r, headerBuf)`:
   * **Kritis:** Menggunakan `r.Read(headerBuf)` biasa adalah anti-pattern! Pemanggilan `r.Read()` pada soket TCP bisa saja hanya mengembalikan 1, 3, atau 5 byte tergantung segmentasi MTU jaringan. `io.ReadFull` menjamin pemanggilan `Read` berulang hingga seluruh 7 byte buffer terisi penuh atau mengembalikan `io.ErrUnexpectedEOF`.
5. `payload := make([]byte, payloadLen)`:
   * Mengalokasikan buffer penerima sesuai ukuran yang dideklarasikan oleh header setelah divalidasi keamanannya terhadap `MaxPayloadLength`.
6. `_, err := io.ReadFull(r, payload)`:
   * Membaca tepat sebanyak `payloadLen` byte. Memastikan eksekusi parser berikutnya berada pada awal paket baru (*frame boundary*), menjaga sinkronisasi stream TCP tetap utuh.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: High-Throughput IoT Telemetry Gateway
Sebuah perusahaan logistik memiliki 50.000 perangkat tracker armada GPS. Setiap tracker mengirimkan metrik telemetri biner terkompresi setiap 5 detik melalui koneksi TCP jangka panjang (*long-lived connection*).

### Masalah pada Implementasi Lama:
1. **Goroutine & Buffer Thrashing:** Menggunakan model HTTP/JSON lama menghasilkan lonjakan alokasi objek JSON kecil, memicu aktivitas Go Garbage Collector (GC) yang ekstrem (>25% CPU time).
2. **Koneksi Menggantung (Slowloris):** Tracker dengan konektivitas seluler buruk (2G/Edge) menahan koneksi terbuka tanpa mengirim data, menghabiskan File Descriptors limit (ulimit) pada server.
3. **Data Framing Rusak:** Terjadi galat parsing parser karena penggabungan paket (TCP stream chunking) saat armada melintasi terowongan sinyal lemah.

### Solusi:
Membangun Gateway berbasis Raw TCP dengan protokol biner kustom, `sync.Pool` untuk penggunaan ulang (*recycling*) buffer memori baca/tulis, isolasi *idle timeout* via `SetDeadline`, dan batasan maksimum *concurrent active workers*.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut implementasi lengkap dari **High-Performance IoT Telemetry Ingestion Server**.

### File: `server/main.go`

```go
package main

import (
	"context"
	"encoding/binary"
	"errors"
	"fmt"
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

const (
	NetworkAddr     = ":9050"
	HeaderSize      = 6 // DeviceID (uint32) + PayloadSize (uint16)
	MaxPayloadLimit = 2048
	ReadTimeout     = 10 * time.Second
	WriteTimeout    = 5 * time.Second
)

// IngestionStats melacak metrik throughput server.
type IngestionStats struct {
	ActiveConnections int64
	MessagesProcessed uint64
	BytesReceived     uint64
}

var stats IngestionStats

// BufferPool mengelola alokasi buffer pembacaan secara efisien untuk GC.
var bufferPool = sync.Pool{
	New: func() any {
		// Mengalokasikan array ukuran tetap untuk meminimalkan heap allocation
		b := make([]byte, HeaderSize+MaxPayloadLimit)
		return &b
	},
}

type TelemetryServer struct {
	listener net.Listener
	quit     chan struct{}
	wg       sync.WaitGroup
}

func NewTelemetryServer(addr string) (*TelemetryServer, error) {
	l, err := net.Listen("tcp", addr)
	if err != nil {
		return nil, fmt.Errorf("gagal bind listener: %w", err)
	}

	return &TelemetryServer{
		listener: l,
		quit:     make(chan struct{}),
	}, nil
}

func (s *TelemetryServer) Start() {
	log.Printf("[SERVER] Berjalan pada alamat %s\n", s.listener.Addr().String())
	for {
		conn, err := s.listener.Accept()
		if err != nil {
			select {
			case <-s.quit:
				return // Normal shutdown
			default:
				log.Printf("[ERR] Accept error: %v\n", err)
				continue
			}
		}

		s.wg.Add(1)
		atomic.AddInt64(&stats.ActiveConnections, 1)
		go s.handleConnection(conn)
	}
}

func (s *TelemetryServer) handleConnection(conn net.Conn) {
	defer func() {
		_ = conn.Close()
		atomic.AddInt64(&stats.ActiveConnections, -1)
		s.wg.Done()
	}()

	// Buffer dialokasikan dari pool
	bufPtr := bufferPool.Get().(*[]byte)
	defer bufferPool.Put(bufPtr)
	buf := *bufPtr

	for {
		// Proteksi terhadap Slowloris: perbarui deadline sebelum setiap read
		if err := conn.SetReadDeadline(time.Now().Add(ReadTimeout)); err != nil {
			return
		}

		// 1. Baca Header: [DeviceID: 4B][PayloadLen: 2B]
		headerBuf := buf[:HeaderSize]
		if _, err := io.ReadFull(conn, headerBuf); err != nil {
			if errors.Is(err, io.EOF) || errors.Is(err, net.ErrClosed) {
				return // Client disconnect normal
			}
			var netErr net.Error
			if errors.As(err, &netErr) && netErr.Timeout() {
				log.Printf("[WARN] %s: Read deadline terlampaui (Idle Timeout)\n", conn.RemoteAddr())
				return
			}
			return
		}

		deviceID := binary.BigEndian.Uint32(headerBuf[0:4])
		payloadLen := binary.BigEndian.Uint16(headerBuf[4:6])

		// 2. Proteksi Alokasi Memori
		if payloadLen > MaxPayloadLimit {
			log.Printf("[REJECT] %s: Ukuran payload %d melebihi batas\n", conn.RemoteAddr(), payloadLen)
			return
		}

		// 3. Baca Body Payload
		payloadBuf := buf[HeaderSize : HeaderSize+payloadLen]
		if _, err := io.ReadFull(conn, payloadBuf); err != nil {
			log.Printf("[ERR] %s: Gagal membaca payload penuh: %v\n", conn.RemoteAddr(), err)
			return
		}

		// Update metrics
		atomic.AddUint64(&stats.MessagesProcessed, 1)
		atomic.AddUint64(&stats.BytesReceived, uint64(HeaderSize+payloadLen))

		// Simulasi Pemrosesan Telemetri
		processTelemetry(deviceID, payloadBuf)

		// 4. Kirimkan ACK (1 Byte: 0x06 - ASCII ACK)
		if err := conn.SetWriteDeadline(time.Now().Add(WriteTimeout)); err != nil {
			return
		}
		if _, err := conn.Write([]byte{0x06}); err != nil {
			return
		}
	}
}

func processTelemetry(deviceID uint32, payload []byte) {
	// Business logic parsing telemetri non-blocking di sini
	_ = deviceID
	_ = payload
}

func (s *TelemetryServer) Stop() {
	close(s.quit)
	_ = s.listener.Close()
	s.wg.Wait()
	log.Println("[SERVER] Berhenti dengan bersih (Graceful Shutdown selesai).")
}

func main() {
	server, err := NewTelemetryServer(NetworkAddr)
	if err != nil {
		log.Fatalf("Fatal init server: %v", err)
	}

	// Tangkap sinyal OS untuk Graceful Shutdown
	sigCtx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go server.Start()

	// Goroutine observabilitas metrik
	go func() {
		ticker := time.NewTicker(3 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				log.Printf("[METRICS] Active Conns: %d | Msg Processed: %d | Total Bytes: %d\n",
					atomic.LoadInt64(&stats.ActiveConnections),
					atomic.LoadUint64(&stats.MessagesProcessed),
					atomic.LoadUint64(&stats.BytesReceived),
				)
			case <-sigCtx.Done():
				return
			}
		}
	}()

	<-sigCtx.Done()
	log.Println("[SERVER] Sinyal penutupan diterima, menghentikan koneksi...")
	server.Stop()
}
```

### File: `client/simulator.go` (Pengujian Beban)

```go
package main

import (
	"encoding/binary"
	"fmt"
	"io"
	"net"
	"time"
)

func main() {
	conn, err := net.Dial("tcp", "127.0.0.1:9050")
	if err != nil {
		panic(err)
	}
	defer conn.Close()

	deviceID := uint32(99012)
	payload := []byte("LAT:-6.2088;LON:106.8456;SPEED:45kmh")
	payloadLen := uint16(len(payload))

	// Rakit Frame
	frame := make([]byte, 6+payloadLen)
	binary.BigEndian.PutUint32(frame[0:4], deviceID)
	binary.BigEndian.PutUint16(frame[4:6], payloadLen)
	copy(frame[6:], payload)

	for i := 0; i < 5; i++ {
		// Kirim frame
		if _, err := conn.Write(frame); err != nil {
			panic(err)
		}

		// Terima ACK
		ack := make([]byte, 1)
		if _, err := io.ReadFull(conn, ack); err != nil {
			panic(err)
		}

		if ack[0] == 0x06 {
			fmt.Printf("[CLIENT] ACK diterima untuk pengiriman #%d\n", i+1)
		}
		time.Sleep(1 * time.Second)
	}
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### 1. Komparasi Transport Level

```
               TRANSPORT LEVEL MATRIX
+-------------------+-----------------+--------------------+
| Karakteristik     | TCP             | UDP                |
+-------------------+-----------------+--------------------+
| Koneksi           | Connection-     | Connectionless     |
|                   | oriented        |                    |
| Keandalan Data    | Dijamin, ACK,   | Best-effort,       |
|                   | Rekonstruksi    | Paket bisa hilang  |
| Ordering (Urutan) | Terjamin Absolut| Tanpa jaminan      |
| Overhead Header   | 20 - 60 Bytes   | 8 Bytes            |
| Flow & Congestion | Bawaan kernel   | Tidak ada          |
| Kasus Terbaik     | Transaksi, RPC, | Game realtime,     |
|                   | Data kritis     | Streaming suara    |
+-------------------+-----------------+--------------------+
```

### 2. Protokol Serialization / Framing

| Pendekatan | Latensi Parsing | Alokasi Memori | Human-Readability | Skalabilitas Skema |
| :--- | :--- | :--- | :--- | :--- |
| **JSON over TCP** | Sangat Tinggi (CPU intensive) | Sangat Tinggi (banyak string/objek) | Ya (Plain text) | Tinggi (fleksibel) |
| **Length-Prefixed Binary** | Nol (Direct byte slice indexing) | Nol / Terkontrol (`sync.Pool`) | Tidak (Raw bytes) | Rendah (butuh serialisasi kustom) |
| **gRPC (Protobuf)** | Rendah | Rendah - Menengah | Tidak (Biner) | Sangat Tinggi (Schema-first via `.proto`) |

---

# SEKSI 12 — EDGE CASES & PITFALLS

1. **TCP Half-Close State:**
   * Jika satu sisi memanggil `CloseWrite()`, soket lokal tidak bisa menulis lagi, tetapi masih bisa membaca data yang dikirim oleh sisi lain. Mengabaikan penanganan `io.EOF` akan membuat server mengira koneksi masih normal sehingga goroutine tertahan selamanya.
2. **Buffer Allocation Exploit (Allocation Panics):**
   * Jika menerima ukuran payload dari header tanpa batas atas, penyerang mengirim paket berukuran `math.MaxUint32`. Kode `make([]byte, size)` akan menyebabkan server crash dengan `panic: runtime error: makeslice: len out of range` atau memicu OOM Killer Linux.
3. **Partial Writes:**
   * Memanggil `conn.Write(buf)` tidak menjamin seluruh `buf` terkirim dalam satu panggilan syscall. Selalu gunakan `io.Copy`, `w.Write()` dengan loop verifikasi panjang data terkirim, atau method pembungkus teruji.
4. **Deadline Persistence Trap:**
   * Deadline pada `net.Conn` bersifat **persisten**. Memanggil `conn.SetReadDeadline(time.Now().Add(5*time.Second))` sekali di awal, akan menyebabkan koneksi gagal pada detik ke-5.001 meskipun komunikasi sedang aktif. Deadline harus direset setiap kali siklus I/O baru dimulai.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Asumsi Ukuran Bacaan pada Raw TCP
```go
// SALAH: Mengasumsikan Read mengembalikan seluruh paket
buf := make([]byte, 1024)
n, err := conn.Read(buf) 
// Jika paket 500 byte dipecah kernel menjadi 200 dan 300 byte,
// logic berikut akan memproses data rusak/setengah utuh!
processPacket(buf[:n]) 

// BENAR: Gunakan io.ReadFull dengan ukuran yang telah ditentukan secara eksplisit
payload := make([]byte, expectedSize)
_, err := io.ReadFull(conn, payload)
if err != nil {
    // tangani galat pembacaan terpotong
}
```

### Anti-Pattern 2: Goroutine Leak pada Server Loop
```go
// SALAH: Tidak menghentikan pembacaan saat worker selesai
go func() {
    for {
        data := make([]byte, 100)
        conn.Read(data) // Memblokir selamanya jika client hang dan tanpa SetDeadline
    }
}()

// BENAR: Gunakan Deadline aktif dan mekanisme pembatalan Context
go func() {
    defer conn.Close()
    for {
        conn.SetReadDeadline(time.Now().Add(30 * time.Second))
        _, err := io.ReadFull(conn, buf)
        if err != nil {
            return // Keluar dari goroutine dan lepaskan memory
        }
    }
}()
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Zero Allocations di Hot Path:** Hindari inisialisasi slice atau instansiasi objek di dalam loop pemrosesan frame TCP. Gunakan `sync.Pool` untuk buffer I/O.
2. **Set TCP Keep-Alive:** Aktifkan pemeriksaan *dead-peer* di level OS untuk koneksi *long-lived* TCP.
   ```go
   tcpConn, ok := conn.(*net.TCPConn)
   if ok {
       _ = tcpConn.SetKeepAlive(true)
       _ = tcpConn.SetKeepAlivePeriod(3 * time.Minute)
   }
   ```
3. **Komposisi Interface I/O:** Buat fungsi jaringan menerima tipe sesempit mungkin. Gunakan `io.Reader` atau `io.Writer` murni daripada mengikat parameter ke `*net.TCPConn`, guna mempermudah *unit testing* dengan `bytes.Buffer`.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Manipulasi Ukuran Buffer Soket OS
Secara default, Linux mengalokasikan auto-tuning TCP buffer (`tcp_rmem`, `tcp_wmem`). Untuk lalu lintas masif, kita dapat memanipulasi buffer soket via `SetReadBuffer` dan `SetWriteBuffer`:
```go
tcpConn.SetReadBuffer(64 * 1024)  // 64 KB
tcpConn.SetWriteBuffer(64 * 1024) // 64 KB
```

### 2. Disable Nagle's Algorithm (`TCP_NODELAY`)
Nagle's Algorithm menggabungkan paket kecil sebelum dikirim untuk menghemat bandwidth header, tetapi menyebabkan latensi artifisial (hingga 40ms) jika dipadukan dengan TCP Delayed ACK. Di Go, `TCP_NODELAY` aktif secara default pada package `net`. Pastikan flag ini tidak diubah sembarangan jika membangun protokol interaktif latensi rendah:
```go
tcpConn.SetNoDelay(true) // Menonaktifkan Nagle, kirim paket seketika
```

### 3. Zero-Copy Operations via `io.Copy` & `sendfile`
Jika mentransfer file lokal langsung ke koneksi soket, hindari menyalin data ke *user-space memory*. Gunakan `io.Copy(conn, file)`: Go mendeteksi jika kedua deskriptor mendukung *zero-copy* dan akan langsung memanggil system call `sendfile(2)` atau `splice(2)` di kernel Linux.

---

# SEKSI 16 — KEAMANAN & HARDENING

1. **Slowloris Mitigation:** Selalu tetapkan batas waktu pembacaan header (`SetReadDeadline`). Serangan Slowloris mengeksploitasi server dengan mengirimkan data yang valid tetapi sangat lambat (misal: 1 byte setiap 10 detik) untuk menghabiskan pool koneksi.
2. **Strict Maximum Payload Bounds:** Selalu validasi deklarasi panjang paket *sebelum* alokasi memori buffer:
   ```go
   if declaredLength > MaxAllowedBuffer {
       conn.Close() // Putuskan koneksi agresif terhadap klien abnormal
       return ErrMalformedPacket
   }
   ```
3. **Transport Layer Security (TLS):** Bungkus soket mentah dengan `crypto/tls`:
   ```go
   cer, err := tls.LoadX509KeyPair("server.crt", "server.key")
   if err != nil { log.Fatal(err) }
   config := &tls.Config{Certificates: []tls.Certificate{cer}, MinVersion: tls.VersionTLS13}
   l, err := tls.Listen("tcp", ":9443", config)
   ```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Metrik Operasional Soket
Ekspos metrik runtime soket esensial ke Prometheus atau sistem monitoring:
* Total koneksi aktif saat ini (*gauge*).
* Durasi siklus *Read-Process-Write* (*histogram*).
* Total byte masuk dan keluar (*counters*).
* Frekuensi galat *timeout* / *deadline exceeded* (*counters*).

### 2. Debugging Jaringan Tingkat Rendah
* **Inspeksi Paket:** Gunakan `tcpdump` untuk melihat apakah masalah ada di segmentasi TCP atau di kode Go:
  ```bash
  sudo tcpdump -i any -nn -vv -X port 9050
  ```
* **Status File Descriptor OS:** Periksa kebocoran koneksi (FD Leak):
  ```bash
  lsof -p <PID> | grep TCP
  ss -tan '( sport = :9050 )'
  ```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

| Operasi | Sintaks / Pola Go | Catatan Penting |
| :--- | :--- | :--- |
| **Membaca Tepat N Byte** | `io.ReadFull(conn, buf)` | Menghindari *partial read*; blokir sampai buffer penuh/error. |
| **Deadline Reset** | `conn.SetDeadline(time.Time{})` | Menghapus seluruh batas waktu deadline. |
| **Read Timeout** | `conn.SetReadDeadline(time.Now().Add(d))` | Harus dieksekusi sebelum pemanggilan operasi `Read`. |
| **Endianness Encode** | `binary.BigEndian.PutUint32(b, val)` | Membutuhkan `len(b) >= 4`. Hindari *out-of-bounds index*. |
| **Endianness Decode** | `val := binary.BigEndian.Uint32(b)` | Membutuhkan `len(b) >= 4`. |
| **Zero-Memory Alloc Buffer** | `sync.Pool` | Daur ulang buffer `[]byte` untuk meringankan GC di hot-path. |

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1–5)

1. **Apa yang dikembalikan oleh `conn.Read(buf)` ketika klien menutup koneksi TCP secara normal?**
   * A. Menghasilkan panic
   * B. Mengembalikan `n = 0` dan error `io.EOF`
   * C. Mengembalikan error `io.ErrUnexpectedEOF`
   * D. Fungsi memblokir selamanya
   * *Jawaban:* **B**. `io.EOF` adalah penanda baku penutupan stream secara teratur.

2. **Mengapa `conn.Read(buf)` tidak aman digunakan untuk membaca header protokol berukuran 10 byte secara langsung?**
   * A. Karena `conn.Read` hanya bisa membaca kelipatan 4 byte.
   * B. Karena TCP berorientasi stream; `Read` pertama bisa saja hanya menerima kurang dari 10 byte tergantung segmentasi paket.
   * C. Karena `conn.Read` menghapus magic bytes secara otomatis.
   * D. Karena Go runtime selalu mengalokasikan 4096 byte per read.
   * *Jawaban:* **B**. TCP tidak menjamin batasan frame, gunakan `io.ReadFull`.

3. **Format byte order mana yang merupakan standar komunikasi protokol jaringan (*Network Byte Order*)?**
   * A. Little-Endian
   * B. Middle-Endian
   * C. Big-Endian
   * D. Native CPU Endian
   * *Jawaban:* **C**. Big-Endian adalah representasi standar untuk nomor biner di jaringan.

4. **Apa efek pemanggilan `conn.SetDeadline(time.Now().Add(5 * time.Second))` terhadap operasi I/O berikutnya yang berjalan 10 detik kemudian?**
   * A. Tidak ada efek, deadline otomatis bertambah saat data lewat.
   * B. Operasi I/O tersebut langsung gagal dengan error timeout/deadline exceeded.
   * C. Deadline dibatalkan secara otomatis jika ada transfer data.
   * D. Server mengalami crash fatal (OS panic).
   * *Jawaban:* **B**. Deadline adalah nilai absolut yang tetap aktif sampai diperbarui atau direset.

5. **Apa fungsi utama dari Runtime Netpoller pada Go?**
   * A. Mengonversi data biner menjadi format JSON.
   * B. Memindahkan goroutine yang menunggu I/O ke status non-blocking via OS event loop (`epoll`/`kqueue`) tanpa memblokir thread kernel OS.
   * C. Mematikan koneksi yang memakan bandwidth terlalu tinggi.
   * D. Mengatur enkripsi SSL/TLS secara otomatis.
   * *Jawaban:* **B**. Netpoller menyembunyikan kompleksitas epoll asinkron menjadi pemanggilan sinkron goroutine.

### Soal Intermediate (6–10)

6. **Sebuah klien mengirim data 1 MB, tetapi header memuat informasi payload length sebesar `4 GB`. Apa dampak paling berbahaya jika server langsung menjalankan `make([]byte, length)`?**
   * A. Kompilasi Go akan gagal.
   * B. Pemanggilan tersebut ditolak langsung oleh kernel OS tanpa menggunakan RAM.
   * C. Server akan mengalami OOM (Out Of Memory) Panic atau dimatikan oleh OOM Killer sistem operasi.
   * D. Memori dialokasikan di hard disk via virtual swap tanpa beban di RAM.
   * *Jawaban:* **C**. Alokasi tanpa validasi batas atas memicu instansiasi memori masif instan yang merusak ketersediaan layanan.

7. **Bagaimana cara yang benar untuk mendeteksi apakah error dari `conn.Read` disebabkan oleh habisnya batas waktu deadline?**
   * A. Mengecek `err.Error() == "timeout"`.
   * B. Menggunakan assertion `errors.Is(err, os.ErrDeadlineExceeded)` atau `netErr, ok := err.(net.Error); ok && netErr.Timeout()`.
   * C. Memeriksa nilai `n == -1`.
   * D. Mengecek status pointer soket `conn == nil`.
   * *Jawaban:* **B**. Standar pengecekan Go idiomatik memanfaatkan `errors.Is` atau interface `net.Error`.

8. **Kapan Anda sebaiknya menonaktifkan algoritma Nagle (`TCP_NODELAY`)?**
   * A. Saat aplikasi mentransfer file raksasa berukuran puluhan gigabyte secara batch.
   * B. Saat membangun protokol streaming interaktif yang membutuhkan latensi pengiriman sekecil mungkin tanpa menunggu akumulasi data (misal: game packet, shell input).
   * C. Saat menghemat konsumsi bandwidth jaringan di koneksi seluler lambat.
   * D. Kapanpun aplikasi menggunakan HTTPS.
   * *Jawaban:* **B**. `TCP_NODELAY` menghilangkan buffering artifisial, mengurangi latensi dengan mengorbankan sedikit overhead paket header.

9. **Jika server memproses ribuan koneksi per detik, mengapa penggunaan `sync.Pool` untuk buffer byte pembacaan sangat direkomendasikan dibandingkan alokasi `make([]byte, N)` di dalam worker?**
   * A. `sync.Pool` mencegah terjadinya data race secara otomatis.
   * B. Menghilangkan fragmentasi heap dan secara drastis menurunkan frekuensi serta durasi jeda Garbage Collector (*GC Pause*).
   * C. `sync.Pool` menyimpan buffer di dalam CPU Cache L1.
   * D. Karena Go melarang alokasi slice di dalam for-loop koneksi.
   * *Jawaban:* **B**. Penggunaan ulang buffer meminimalkan sampah objek di heap, meringankan alokator memori Go.

10. **Perhatikan skenario: Pengirim menutup soket dengan `conn.Close()`. Apa yang dibaca penerima melalui `conn.Read` setelah seluruh buffer sisa TCP dibaca habis?**
    * A. Menghasilkan galat `syscall.ECONNRESET`.
    * B. Mengembalikan `n > 0` tanpa galat selamanya.
    * C. Mengembalikan `n = 0` dan galat `io.EOF`.
    * D. Koneksi memblokir sampai pengirim menyala kembali.
    * *Jawaban:* **C**. Penutupan normal (FIN handshake) menghasilkan sinyal `io.EOF` setelah seluruh byte di antrean TCP terbaca.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Misi: Membangun Resilient Multiplexed Binary Chat Gateway

Rancang dan bangun aplikasi *Server & Client CLI* berbasis TCP murni dengan spesifikasi protokol biner ketat berikut:

#### Spesifikasi Protokol:
1. **Magic Header (2 Byte):** `0x42 0x43` (ASCII: 'B', 'C' -> Binary Chat).
2. **Channel ID (1 Byte):** Menentukan nomor channel tujuan pesan (0–255).
3. **Payload Type (1 Byte):** 
   * `0x01`: Broadcast Text Message.
   * `0x02`: Direct Private Message.
   * `0x03`: Heartbeat / Ping-Pong.
4. **Data Length (2 Byte, Big-Endian):** Menentukan panjang sisa payload (Maksimum 1024 Byte).
5. **Payload (N Byte):** Byte data pesan.

#### Persyaratan Sistem Server:
* Implementasikan pemisahan logic reader/writer goroutine per koneksi client.
* Server harus mengelola *Room Routing*: pesan dengan Channel ID yang sama hanya dibagikan ke client yang terdaftar pada Channel ID tersebut.
* Implementasikan proteksi **Heartbeat**: Jika client tidak mengirim paket apa pun dalam durasi 15 detik, server memutus koneksi secara sepihak dan membersihkan alokasi memori (Graceful Cleanup).
* Server tidak boleh mengalokasikan slice baru per frame di hot-path; seluruh buffer pembacaan wajib memanfaatkan `sync.Pool`.
* Menolak dan memutuskan client secara instan jika magic byte tidak cocok atau ukuran melebihi batas 1024 byte.
* Sediakan mekanisme Graceful Shutdown yang mengirim pesan broadcast pemberitahuan ke semua client aktif sebelum listener ditutup.