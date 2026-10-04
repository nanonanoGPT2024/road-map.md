package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"math/rand"
	"sync"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
	"github.com/redis/go-redis/v9"
	"github.com/segmentio/kafka-go"
	"golang.org/x/sync/singleflight"
)

// --- MODELS & STRUCTS ---

type Order struct {
	ID        string    `json:"id"`
	UserID    string    `json:"user_id"`
	Amount    float64   `json:"amount"`
	Status    string    `json:"status"`
	CreatedAt time.Time `json:"created_at"`
}

type OutboxEvent struct {
	ID            int64     `json:"id"`
	AggregateType string    `json:"aggregate_type"`
	AggregateID   string    `json:"aggregate_id"`
	Payload       string    `json:"payload"`
	Status        string    `json:"status"`
	CreatedAt     time.Time `json:"created_at"`
}

// OrderService bertindak sebagai pengendali utama alur domain.
type OrderService struct {
	db          *sql.DB
	redis       *redis.Client
	kafkaWriter *kafka.Writer
	sfGroup     singleflight.Group
}

func NewOrderService(db *sql.DB, rdb *redis.Client, kw *kafka.Writer) *OrderService {
	return &OrderService{
		db:          db,
		redis:       rdb,
		kafkaWriter: kw,
	}
}

// --- WRITE PATH DENGAN TRANSACTIONAL OUTBOX ---

func (s *OrderService) CreateOrder(ctx context.Context, order Order) error {
	tx, err := s.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return fmt.Errorf("gagal memulai transaksi: %w", err)
	}
	defer tx.Rollback() // Aman dipanggil; diabaikan jika Commit sukses

	// 1. Simpan Order ke Database
	orderQuery := `INSERT INTO orders (id, user_id, amount, status, created_at) 
	               VALUES ($1, $2, $3, $4, $5)`
	_, err = tx.ExecContext(ctx, orderQuery, order.ID, order.UserID, order.Amount, order.Status, order.CreatedAt)
	if err != nil {
		return fmt.Errorf("gagal insert order: %w", err)
	}

	// 2. Serialisasi data order untuk outbox payload
	payloadBytes, err := json.Marshal(order)
	if err != nil {
		return fmt.Errorf("gagal marshal outbox payload: %w", err)
	}

	// 3. Simpan Event ke Outbox Table pada transaksi DB yang SAMA
	outboxQuery := `INSERT INTO outbox_events (aggregate_type, aggregate_id, payload, status, created_at) 
	                VALUES ($1, $2, $3, 'PENDING', $4)`
	_, err = tx.ExecContext(ctx, outboxQuery, "ORDER", order.ID, string(payloadBytes), time.Now())
	if err != nil {
		return fmt.Errorf("gagal insert outbox event: %w", err)
	}

	// Commit transaksi ACID
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("gagal commit database: %w", err)
	}

	return nil
}

// --- BACKGROUND OUTBOX RELAY WORKER ---

func (s *OrderService) StartOutboxWorker(ctx context.Context) {
	ticker := time.NewTicker(500 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Println("Menghentikan outbox worker...")
			return
		case <-ticker.C:
			s.processOutboxBatch(ctx)
		}
	}
}

func (s *OrderService) processOutboxBatch(ctx context.Context) {
	// Menggunakan FOR UPDATE SKIP LOCKED untuk menghindari race condition antar replica worker
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		log.Printf("[Outbox] Gagal start tx: %v\n", err)
		return
	}
	defer tx.Rollback()

	query := `SELECT id, aggregate_id, payload 
	          FROM outbox_events 
	          WHERE status = 'PENDING' 
	          ORDER BY id ASC 
	          LIMIT 20 
	          FOR UPDATE SKIP LOCKED`

	rows, err := tx.QueryContext(ctx, query)
	if err != nil {
		log.Printf("[Outbox] Gagal query events: %v\n", err)
		return
	}
	defer rows.Close()

	type eventToPublish struct {
		id          int64
		aggregateID string
		payload     string
	}
	var events []eventToPublish

	for rows.Next() {
		var e eventToPublish
		if err := rows.Scan(&e.id, &e.aggregateID, &e.payload); err != nil {
			log.Printf("[Outbox] Scan error: %v\n", err)
			return
		}
		events = append(events, e)
	}

	if len(events) == 0 {
		return
	}

	var kafkaMessages []kafka.Message
	for _, e := range events {
		kafkaMessages = append(kafkaMessages, kafka.Message{
			Key:   []byte(e.aggregateID),
			Value: []byte(e.payload),
			Time:  time.Now(),
		})
	}

	// Publish ke broker Kafka
	err = s.kafkaWriter.WriteMessages(ctx, kafkaMessages...)
	if err != nil {
		log.Printf("[Outbox] Broker publish gagal: %v\n", err)
		return
	}

	// Update status outbox menjadi PROCESSED
	for _, e := range events {
		_, err := tx.ExecContext(ctx, `UPDATE outbox_events SET status = 'PROCESSED' WHERE id = $1`, e.id)
		if err != nil {
			log.Printf("[Outbox] Update status gagal: %v\n", err)
			return
		}
	}

	if err := tx.Commit(); err != nil {
		log.Printf("[Outbox] Commit update outbox gagal: %v\n", err)
	}
}

// --- READ PATH: CACHE-ASIDE + SINGLEFLIGHT ---

func (s *OrderService) GetOrderByID(ctx context.Context, orderID string) (*Order, error) {
	cacheKey := fmt.Sprintf("order:%s", orderID)

	// 1. Coba ambil dari Cache Redis
	val, err := s.redis.Get(ctx, cacheKey).Result()
	if err == nil {
		var cachedOrder Order
		if err := json.Unmarshal([]byte(val), &cachedOrder); err == nil {
			return &cachedOrder, nil
		}
	} else if !errors.Is(err, redis.Nil) {
		// Log error jika redis mati, namun teruskan eksekusi fallback ke DB
		log.Printf("[Redis Warning] gagal get data: %v\n", err)
	}

	// 2. Cache Miss: Gunakan Singleflight untuk melindungi database dari thundering herd
	result, err, _ := s.sfGroup.Do(orderID, func() (interface{}, error) {
		// Query database utama
		query := `SELECT id, user_id, amount, status, created_at FROM orders WHERE id = $1`
		var ord Order
		err := s.db.QueryRowContext(ctx, query, orderID).Scan(
			&ord.ID, &ord.UserID, &ord.Amount, &ord.Status, &ord.CreatedAt,
		)
		if err != nil {
			return nil, err
		}

		// Hitung TTL dengan Jitter (Mencegah sinkronisasi kedaluwarsa serempak)
		baseTTL := 15 * time.Minute
		jitter := time.Duration(rand.Intn(180)) * time.Second
		effectiveTTL := baseTTL + jitter

		// Simpan kembali ke Redis secara asinkron (non-blocking untuk caller)
		payload, err := json.Marshal(ord)
		if err == nil {
			_ = s.redis.Set(context.Background(), cacheKey, payload, effectiveTTL).Err()
		}

		return &ord, nil
	})

	if err != nil {
		return nil, fmt.Errorf("database query error: %w", err)
	}

	return result.(*Order), nil
}

// --- CONSUMER PATH: IDEMPOTENT PROCESSING ---

func StartIdempotentConsumer(ctx context.Context, reader *kafka.Reader, db *sql.DB) {
	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if errors.Is(err, context.Canceled) {
				return
			}
			log.Printf("[Consumer] Fetch error: %v\n", err)
			continue
		}

		// Eksekusi logic dengan idempotency check
		err = processEventAtomically(ctx, db, msg)
		if err != nil {
			log.Printf("[Consumer] Gagal proses event id %s: %v\n", string(msg.Key), err)
			// Jangan commit offset, biarkan redelivery atau route ke DLQ
			continue
		}

		// Commit offset manual setelah proses berhasil (At-Least-Once safety)
		if err := reader.CommitMessages(ctx, msg); err != nil {
			log.Printf("[Consumer] Offset commit failed: %v\n", err)
		}
	}
}

func processEventAtomically(ctx context.Context, db *sql.DB, msg kafka.Message) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	// 1. Cek idempotensi menggunakan tabel riwayat deduplikasi
	// Gunakan message identifier (Key atau custom UUID dari Kafka header)
	eventKey := string(msg.Key)
	res, err := tx.ExecContext(ctx, 
		`INSERT INTO processed_events (event_id, processed_at) VALUES ($1, NOW()) ON CONFLICT (event_id) DO NOTHING`, 
		eventKey,
	)
	if err != nil {
		return fmt.Errorf("deduplication check query failed: %w", err)
	}

	rowsAffected, err := res.RowsAffected()
	if err != nil {
		return err
	}

	// Jika rowsAffected == 0, event ini SUDAH PERNAH diproses sebelumnya! Abaikan operasi downstream.
	if rowsAffected == 0 {
		log.Printf("[Consumer Deduplication] Event %s telah diproses sebelumnya. Melewati mutasi data.\n", eventKey)
		return tx.Commit()
	}

	// 2. Eksekusi Business Logic Konsumen (Contoh: Potong limit/Kirim Invoicing)
	var ord Order
	if err := json.Unmarshal(msg.Value, &ord); err != nil {
		return fmt.Errorf("unmarshal error: %w", err)
	}

	// Simulasi mutasi state lain...
	_, err = tx.ExecContext(ctx, 
		`INSERT INTO audit_invoices (order_id, user_id, settled_amount) VALUES ($1, $2, $3)`,
		ord.ID, ord.UserID, ord.Amount,
	)
	if err != nil {
		return fmt.Errorf("invoicing record error: %w", err)
	}

	return tx.Commit()
}
