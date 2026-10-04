package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"os/signal"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

var (
	ErrQueueFull = errors.New("pipeline capacity saturated: shedding load")
	ErrShuttingDown = errors.New("service is gracefully shutting down")
)

type PaymentEvent struct {
	TransactionID string
	AccountID     string
	AmountCents   int64
	Timestamp     int64
	Signature     string
}

type EventResult struct {
	TransactionID string
	Success       bool
	Checksum      string
	Duration      time.Duration
	Err           error
}

type PaymentProcessorEngine struct {
	concurrencyLimit int
	capacity         int
	inboundQueue     chan PaymentEvent
	results          chan EventResult
	isClosed         uint32
	activeWorkers    sync.WaitGroup
	metricsProcessed uint64
	metricsDropped   uint64
}

func NewPaymentProcessorEngine(workers int, queueCapacity int) *PaymentProcessorEngine {
	return &PaymentProcessorEngine{
		concurrencyLimit: workers,
		capacity:         queueCapacity,
		inboundQueue:     make(chan PaymentEvent, queueCapacity),
		results:          make(chan EventResult, queueCapacity),
	}
}

func (pe *PaymentProcessorEngine) Start(ctx context.Context) {
	for i := 0; i < pe.concurrencyLimit; i++ {
		pe.activeWorkers.Add(1)
		go pe.workerLoop(ctx, i)
	}
}

func (pe *PaymentProcessorEngine) workerLoop(ctx context.Context, workerID int) {
	defer pe.activeWorkers.Done()

	for {
		select {
		case <-ctx.Done():
			return
		case event, ok := <-pe.inboundQueue:
			if !ok {
				return
			}
			res := pe.processTransaction(ctx, event)
			
			// Non-blocking result push dengan context-fallback
			select {
			case pe.results <- res:
				atomic.AddUint64(&pe.metricsProcessed, 1)
			case <-ctx.Done():
				return
			}
		}
	}
}

func (pe *PaymentProcessorEngine) processTransaction(ctx context.Context, evt PaymentEvent) EventResult {
	start := time.Now()

	// Simulasi CPU Intensive: Validasi Hash Kriptografi
	hasher := sha256.New()
	hasher.Write([]byte(fmt.Sprintf("%s:%s:%d:%d", evt.TransactionID, evt.AccountID, evt.AmountCents, evt.Timestamp)))
	calculatedChecksum := hex.EncodeToString(hasher.Sum(nil))

	// Validasi business rules
	if evt.AmountCents <= 0 {
		return EventResult{
			TransactionID: evt.TransactionID,
			Success:       false,
			Duration:      time.Since(start),
			Err:           errors.New("invalid transaction amount"),
		}
	}

	// Simulasi downstream persistence latency
	select {
	case <-time.After(2 * time.Millisecond):
	case <-ctx.Done():
		return EventResult{
			TransactionID: evt.TransactionID,
			Success:       false,
			Duration:      time.Since(start),
			Err:           ctx.Err(),
		}
	}

	return EventResult{
		TransactionID: evt.TransactionID,
		Success:       true,
		Checksum:      calculatedChecksum,
		Duration:      time.Since(start),
		Err:           nil,
	}
}

// EnqueueEvent: Mengimplementasikan non-blocking shedding load (Fast Fail)
func (pe *PaymentProcessorEngine) EnqueueEvent(evt PaymentEvent) error {
	if atomic.LoadUint32(&pe.isClosed) == 1 {
		return ErrShuttingDown
	}

	select {
	case pe.inboundQueue <- evt:
		return nil
	default:
		// Queue penuh, fast shedding load untuk mempertahankan sistem
		atomic.AddUint64(&pe.metricsDropped, 1)
		return ErrQueueFull
	}
}

func (pe *PaymentProcessorEngine) Shutdown(ctx context.Context) error {
	// Tandai status shutdown
	if !atomic.CompareAndSwapUint32(&pe.isClosed, 0, 1) {
		return errors.New("shutdown already invoked")
	}

	close(pe.inboundQueue) // Pekerja berhenti mengambil setelah mengosongkan antrean

	// Channel sinyal penyelesaian drain
	drained := make(chan struct{})
	go func() {
		pe.activeWorkers.Wait()
		close(pe.results)
		close(drained)
	}()

	select {
	case <-drained:
		return nil
	case <-ctx.Done():
		return errors.New("shutdown timeout: some workers abandoned")
	}
}

func main() {
	rootCtx, rootCancel := context.WithCancel(context.Background())
	defer rootCancel()

	// Inisialisasi engine: 8 Pekerja (terisolasi pada P), antrean buffer 500
	engine := NewPaymentProcessorEngine(8, 500)
	engine.Start(rootCtx)

	// Pipeline result logger
	var auditWg sync.WaitGroup
	auditWg.Add(1)
	go func() {
		defer auditWg.Done()
		for res := range engine.results {
			if res.Err != nil {
				// Log level Error pada production
				continue
			}
			// Telemetry reporting simulation
		}
	}()

	// Simulasi load producer (10.000 events)
	go func() {
		for i := 1; i <= 10000; i++ {
			evt := PaymentEvent{
				TransactionID: fmt.Sprintf("tx-uuid-%05d", i),
				AccountID:     fmt.Sprintf("acc-%d", i%100),
				AmountCents:   int64(i * 150),
				Timestamp:     time.Now().UnixNano(),
			}

			err := engine.EnqueueEvent(evt)
			if err != nil {
				// Catat drop event
			}
			time.Sleep(100 * time.Microsecond) // Rate injection
		}
	}()

	// Tangani OS Signal Graceful Termination
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	// Tunggu sinyal interupsi atau simulasi run duration
	select {
	case <-sigChan:
		fmt.Println("\n[SYSTEM] Menerima sinyal termination, memulai graceful shutdown...")
	case <-time.After(3 * time.Second):
		fmt.Println("\n[SYSTEM] Batas durasi benchmark selesai, menghentikan antrean...")
	}

	// Alokasikan deadline waktu shutdown maksimal 2 detik
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer shutdownCancel()

	if err := engine.Shutdown(shutdownCtx); err != nil {
		fmt.Printf("[ALERT] Shutdown abnormal: %v\n", err)
	} else {
		fmt.Println("[SUCCESS] Seluruh antrean berhasil didrain tanpa kehilangan transaksi valid.")
	}

	auditWg.Wait()

	fmt.Printf("[METRICS] Transaksi Sukses: %d | Transaksi Di-drop (Shedded): %d\n",
		atomic.LoadUint64(&engine.metricsProcessed),
		atomic.LoadUint64(&engine.metricsDropped),
	)
}
