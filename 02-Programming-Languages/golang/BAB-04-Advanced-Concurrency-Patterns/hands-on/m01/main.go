package main

import (
	"context"
	"errors"
	"fmt"
	"math/rand"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"golang.org/x/sync/errgroup"
)

type Transaction struct {
	ID        string
	Amount    float64
	Timestamp time.Time
}

type EnrichedTransaction struct {
	Transaction
	RiskScore float64
	FraudFlag bool
	ProcessedBy int
}

// Simulasi layanan penilaian risiko eksternal
func externalRiskScoringService(ctx context.Context, txID string) (float64, error) {
	select {
	case <-ctx.Done():
		return 0.0, ctx.Err()
	case <-time.After(time.Duration(15+rand.Intn(20)) * time.Millisecond): // Simulasi I/O
		if rand.Float32() < 0.001 { // 0.1% transient network failure
			return 0.0, errors.New("upstream gateway timeout")
		}
		return rand.Float64(), nil
	}
}

// Engine Orchestrator
type ProcessingEngine struct {
	workerCount int
	bufferSize  int
}

func NewProcessingEngine(workerCount, bufferSize int) *ProcessingEngine {
	return &ProcessingEngine{
		workerCount: workerCount,
		bufferSize:  bufferSize,
	}
}

func (pe *ProcessingEngine) Run(ctx context.Context, inputData []Transaction) error {
	// Root errgroup untuk koordinasi seluruh goroutine
	g, gCtx := errgroup.WithContext(ctx)

	inflowChan := make(chan Transaction, pe.bufferSize)
	resultsChan := make(chan EnrichedTransaction, pe.bufferSize)

	// 1. Stage Ingestion (Producer)
	g.Go(func() error {
		defer close(inflowChan)
		for _, tx := range inputData {
			select {
			case <-gCtx.Done():
				return gCtx.Err()
			case inflowChan <- tx:
			}
		}
		return nil
	})

	// 2. Stage Processing (Worker Pool dengan Fan-Out)
	var workerWg sync.WaitGroup
	for w := 1; w <= pe.workerCount; w++ {
		workerID := w
		workerWg.Add(1)
		g.Go(func() error {
			defer workerWg.Done()
			for {
				select {
				case <-gCtx.Done():
					return gCtx.Err()
				case tx, ok := <-inflowChan:
					if !ok {
						return nil // Inflow ditutup dan kosong, worker keluar
					}

					// Enrich via external I/O
					score, err := externalRiskScoringService(gCtx, tx.ID)
					if err != nil {
						// Jika terjadi error fatal, gagalkan pipeline
						return fmt.Errorf("worker %d failed processing tx %s: %w", workerID, tx.ID, err)
					}

					enriched := EnrichedTransaction{
						Transaction: tx,
						RiskScore:   score,
						FraudFlag:   score > 0.85,
						ProcessedBy: workerID,
					}

					select {
					case <-gCtx.Done():
						return gCtx.Err()
					case resultsChan <- enriched:
					}
				}
			}
		})
	}

	// 3. Supervisor untuk menutup channel results setelah seluruh worker selesai
	g.Go(func() error {
		workerWg.Wait()
		close(resultsChan)
		return nil
	})

	// 4. Stage Sink/Aggregation (Consumer)
	g.Go(func() error {
		var processedCounter int
		var fraudCount int

		for res := range resultsChan {
			processedCounter++
			if res.FraudFlag {
				fraudCount++
			}
		}

		fmt.Printf("[METRIC] Total Transaksi Diproses: %d | Terindikasi Fraud: %d\n", processedCounter, fraudCount)
		return nil
	})

	// Tunggu hingga seluruh komponen selesai atau terjadi error pertama
	if err := g.Wait(); err != nil {
		if errors.Is(err, context.Canceled) {
			fmt.Println("[SYSTEM] Pipeline dihentikan via pembatalan konteks.")
			return nil
		}
		return fmt.Errorf("pipeline execution halted with error: %w", err)
	}

	return nil
}

func main() {
	// Konfigurasi sistem
	const (
		totalRecords = 1000
		concurrency  = 20
		bufferLimit  = 100
	)

	// Mock Data Input
	dataset := make([]Transaction, totalRecords)
	for i := 0; i < totalRecords; i++ {
		dataset[i] = Transaction{
			ID:        fmt.Sprintf("TXN-%05d", i+1),
			Amount:    float64(rand.Intn(100000)) / 100.0,
			Timestamp: time.Now(),
		}
	}

	// Menyiapkan Graceful Shutdown Context
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	engine := NewProcessingEngine(concurrency, bufferLimit)
	
	start := time.Now()
	fmt.Printf("[SYSTEM] Memulai pemrosesan %d transaksi dengan concurrency limit %d...\n", totalRecords, concurrency)

	if err := engine.Run(ctx, dataset); err != nil {
		fmt.Fprintf(os.Stderr, "[ERROR] Kegagalan sistem: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("[SYSTEM] Eksekusi tuntas dengan aman dalam: %s\n", time.Since(start))
}
