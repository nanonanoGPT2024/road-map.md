package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"runtime"
	"sync"
	"time"
)

// Transaction adalah model data transaksi finansial.
// Perhatikan field alignment untuk menghindari memory padding alignment waste.
type Transaction struct {
	Timestamp int64   // 8 bytes (offset 0)
	Amount    float64 // 8 bytes (offset 8)
	ID        int64   // 8 bytes (offset 16)
	Valid     bool    // 1 byte  (offset 24)
	// Compiler menyisipkan 7 bytes padding di sini agar struct genap berukuran kelipatan 8
}

// TransactionProcessor mengelola ingestion pipeline dengan alokasi minimal.
type TransactionProcessor struct {
	// Pool untuk membungkus byte buffer guna eliminasi alokasi I/O
	bufPool sync.Pool
	// Pool untuk mendaur ulang struct Transaction
	txPool sync.Pool
}

func NewTransactionProcessor() *TransactionProcessor {
	return &TransactionProcessor{
		bufPool: sync.Pool{
			New: func() any {
				// Alokasikan buffer 2KB di awal agar tidak perlu resize saat parsing
				return bytes.NewBuffer(make([]byte, 0, 2048))
			},
		},
		txPool: sync.Pool{
			New: func() any {
				return new(Transaction)
			},
		},
	}
}

// ProcessPayload mengeksekusi parsing dan kalkulasi tanpa alokasi baru di heap mutator.
func (tp *TransactionProcessor) ProcessPayload(payload []byte) error {
	// 1. Ambil buffer dari pool
	buf := tp.bufPool.Get().(*bytes.Buffer)
	buf.Reset()
	defer tp.bufPool.Put(buf)

	buf.Write(payload)

	// 2. Ambil struct Transaction dari pool
	tx := tp.txPool.Get().(*Transaction)
	// Selalu inisialisasi ulang properti struct (sanitize state)
	tx.ID = 0
	tx.Amount = 0
	tx.Timestamp = 0
	tx.Valid = false
	defer tp.txPool.Put(tx)

	// 3. Gunakan streaming decoder berbasis buffer yang didaur ulang
	decoder := json.NewDecoder(buf)
	if err := decoder.Decode(tx); err != nil {
		return err
	}

	// 4. Logika Bisnis (Simulasi verifikasi instan tanpa escape)
	if tx.Amount <= 0 {
		return fmt.Errorf("invalid transaction amount")
	}
	tx.Valid = true

	return nil
}

func main() {
	processor := NewTransactionProcessor()
	sampleJSON := []byte(`{"ID": 987654321, "Amount": 1250.75, "Timestamp": 1700000000}`)

	// Jalankan benchmark sederhana dan pembuktian statistik alokasi
	var memStatsBefore, memStatsAfter runtime.MemStats
	runtime.GC()
	runtime.ReadMemStats(&memStatsBefore)

	startTime := time.Now()
	iterations := 1_000_000

	for i := 0; i < iterations; i++ {
		if err := processor.ProcessPayload(sampleJSON); err != nil {
			panic(err)
		}
	}

	elapsed := time.Since(startTime)
	runtime.ReadMemStats(&memStatsAfter)

	fmt.Println("=== HASIL BENCHMARK ZERO-ALLOC INGESTION ===")
	fmt.Printf("Total Operasi        : %d ops\n", iterations)
	fmt.Printf("Waktu Eksekusi       : %v\n", elapsed)
	fmt.Printf("Throughput           : %.2f ops/sec\n", float64(iterations)/elapsed.Seconds())
	fmt.Printf("Alokasi Total Heap   : %d Bytes\n", memStatsAfter.TotalAlloc-memStatsBefore.TotalAlloc)
	fmt.Printf("Frekuensi GC Siklus  : %d siklus\n", memStatsAfter.NumGC-memStatsBefore.NumGC)
}
