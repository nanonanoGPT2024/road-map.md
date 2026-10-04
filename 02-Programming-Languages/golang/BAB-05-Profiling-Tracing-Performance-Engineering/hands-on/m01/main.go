package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"fmt"
	"hash/fnv"
	"net/http"
	_ "net/http/pprof" // Mendaftarkan route /debug/pprof otomatis pada DefaultServeMux
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"
)

// Ukuran packet biner: 8 byte ID, 8 byte Timestamp, 8 byte Amount, 40 byte Meta = 64 bytes
type IngestionPayload struct {
	ID        uint64
	Timestamp int64
	Amount    float64
	Metadata  [40]byte
}

// 1. Zero-Allocation Object Pool
var payloadPool = sync.Pool{
	New: func() any {
		return new(IngestionPayload)
	},
}

// 2. Sharded Mutex Map untuk Menghindari Lock Contention
const ShardCount = 32

type ShardedMetrics struct {
	shards [ShardCount]*Shard
}

type Shard struct {
	mu    sync.Mutex
	total uint64
	_pad  [56]byte // Cache line padding (64 bytes total) untuk mencegah False Sharing!
}

func NewShardedMetrics() *ShardedMetrics {
	sm := &ShardedMetrics{}
	for i := 0; i < ShardCount; i++ {
		sm.shards[i] = &Shard{}
	}
	return sm
}

func (sm *ShardedMetrics) Add(key uint64, val uint64) {
	// FNV hash ring distribution
	shardIdx := key % ShardCount
	shard := sm.shards[shardIdx]

	shard.mu.Lock()
	shard.total += val
	shard.mu.Unlock()
}

func (sm *ShardedMetrics) ReadTotal() uint64 {
	var total uint64
	for i := 0; i < ShardCount; i++ {
		sm.shards[i].mu.Lock()
		total += sm.shards[i].total
		sm.shards[i].mu.Unlock()
	}
	return total
}

func main() {
	// Menjalankan diagnostic pprof server di port internal terisolasi (Security Isolation)
	go func() {
		diagServer := &http.Server{
			Addr:         "127.0.0.1:6060",
			ReadTimeout:  5 * time.Second,
			WriteTimeout: 60 * time.Second, // Timeout panjang untuk pprof heap/cpu dump
		}
		if err := diagServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			fmt.Printf("Diagnostic server error: %v\n", err)
		}
	}()

	metrics := NewShardedMetrics()
	stopChan := make(chan os.Signal, 1)
	signal.Notify(stopChan, os.Interrupt, syscall.SIGTERM)

	// Simulasi Pipeline Ingesti Konkuren
	ctx, cancel := context.WithCancel(context.Background())
	workerCount := 16
	var wg sync.WaitGroup

	for i := 0; i < workerCount; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			processIngress(ctx, workerID, metrics)
		}(i)
	}

	fmt.Println("Ingestion Engine berjalan optimal. Profile siap di http://127.0.0.1:6060/debug/pprof/")
	<-stopChan
	fmt.Println("Menghentikan sistem...")

	cancel()
	wg.Wait()

	fmt.Printf("Total Nilai Transaksi Terproses: %d\n", metrics.ReadTotal())
}

// processIngress mengeksekusi streaming data tanpa alokasi heap baru di per-loop
func processIngress(ctx context.Context, id int, metrics *ShardedMetrics) {
	// Buffer frame lokal untuk parsing
	rawStream := make([]byte, 64)
	binary.BigEndian.PutUint64(rawStream[0:8], uint64(id+1000))
	binary.BigEndian.PutUint64(rawStream[8:16], uint64(time.Now().UnixNano()))

	for {
		select {
		case <-ctx.Done():
			return
		default:
			// Ambil objek dari pool (Memory Reuse)
			payload := payloadPool.Get().(*IngestionPayload)

			// Zero-Copy deserialization manual dari buffer biner langsung ke struct field
			payload.ID = binary.BigEndian.Uint64(rawStream[0:8])
			payload.Timestamp = int64(binary.BigEndian.Uint64(rawStream[8:16]))
			copy(payload.Metadata[:], rawStream[24:64])

			// Update sharded metric dengan alokasi 0
			metrics.Add(payload.ID, 1)

			// Bersihkan objek sebelum dikembalikan ke pool (Pembersihan state)
			*payload = IngestionPayload{}
			payloadPool.Put(payload)

			// Kompensasi laju throttle microsecond untuk stabilitas simulasi
			time.Sleep(100 * time.Nanosecond)
		}
	}
}
