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
