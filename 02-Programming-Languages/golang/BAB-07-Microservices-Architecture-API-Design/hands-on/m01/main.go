package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"sync"
	"sync/atomic"
	"time"
)

// --- BAGIAN 1: RESILIENT CIRCUIT BREAKER ---

type State int32

const (
	StateClosed State = iota
	StateHalfOpen
	StateOpen
)

func (s State) String() string {
	switch s {
	case StateClosed:
		return "CLOSED"
	case StateHalfOpen:
		return "HALF-OPEN"
	case StateOpen:
		return "OPEN"
	default:
		return "UNKNOWN"
	}
}

var ErrCircuitOpen = errors.New("circuit breaker is OPEN: requests blocked")

type CircuitBreaker struct {
	mu           sync.RWMutex
	state        State
	failures     int64
	threshold    int64
	cooldown     time.Duration
	lastStateChg time.Time
}

func NewCircuitBreaker(threshold int64, cooldown time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		state:        StateClosed,
		threshold:    threshold,
		cooldown:     cooldown,
		lastStateChg: time.Now(),
	}
}

func (cb *CircuitBreaker) Execute(fn func() error) error {
	cb.mu.Lock()
	now := time.Now()

	// Evaluasi transisi dari OPEN ke HALF-OPEN
	if cb.state == StateOpen {
		if now.Sub(cb.lastStateChg) > cb.cooldown {
			cb.state = StateHalfOpen
			cb.lastStateChg = now
		} else {
			cb.mu.Unlock()
			return ErrCircuitOpen
		}
	}
	cb.mu.Unlock()

	// Eksekusi fungsi target
	err := fn()

	cb.mu.Lock()
	defer cb.mu.Unlock()

	if err != nil {
		cb.failures++
		if cb.state == StateHalfOpen || cb.failures >= cb.threshold {
			cb.state = StateOpen
			cb.lastStateChg = time.Now()
		}
		return err
	}

	// Sukses dieksekusi
	if cb.state == StateHalfOpen {
		cb.state = StateClosed
		cb.failures = 0
		cb.lastStateChg = time.Now()
	} else if cb.state == StateClosed {
		cb.failures = 0
	}

	return nil
}

// --- BAGIAN 2: TRACE CONTEXT PROPAGATION (W3C Standard) ---

const TraceParentHeader = "traceparent"

type TraceContext struct {
	TraceID string
	SpanID  string
}

func InjectTraceContext(ctx context.Context, req *http.Request) {
	if val := ctx.Value("trace_ctx"); val != nil {
		if tc, ok := val.(TraceContext); ok {
			headerVal := fmt.Sprintf("00-%s-%s-01", tc.TraceID, tc.SpanID)
			req.Header.Set(TraceParentHeader, headerVal)
		}
	}
}

// --- BAGIAN 3: SERVICE CLIENT WITH INSTRUMENTATION ---

type PaymentServiceClient struct {
	cb     *CircuitBreaker
	client *http.Client
}

func (c *PaymentServiceClient) Charge(ctx context.Context, orderID string, amount int64) error {
	return c.cb.Execute(func() error {
		reqCtx, cancel := context.WithTimeout(ctx, 800*time.Millisecond)
		defer cancel()

		req, err := http.NewRequestWithContext(
			reqCtx,
			http.MethodPost,
			"http://127.0.0.1:8081/v1/charge",
			nil,
		)
		if err != nil {
			return err
		}

		// Inject trace context lintas network boundary
		InjectTraceContext(ctx, req)
		req.Header.Set("X-Order-ID", orderID)

		resp, err := c.client.Do(req)
		if err != nil {
			return err
		}
		defer resp.Body.Close()

		if resp.StatusCode >= 500 {
			return fmt.Errorf("remote server returned status: %d", resp.StatusCode)
		}
		return nil
	})
}

// --- BAGIAN 4: SERVER IMPLEMENTATION (MOCK INFRASTRUCTURE) ---

func startMockPaymentGateway(failureTrigger *int32) *http.Server {
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/charge", func(w http.ResponseWriter, r *http.Request) {
		// Observasi traceparent yang dikirim client
		traceParent := r.Header.Get(TraceParentHeader)
		slog.Info("Downstream received request", "traceparent", traceParent)

		if atomic.LoadInt32(failureTrigger) == 1 {
			// Simulasi degradasi internal downstream (500 Internal Error)
			w.WriteHeader(http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"SUCCESS"}`))
	})

	srv := &http.Server{
		Addr:    ":8081",
		Handler: mux,
	}

	go func() {
		_ = srv.ListenAndServe()
	}()

	return srv
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	var downstreamFailure int32 = 0
	srv := startMockPaymentGateway(&downstreamFailure)
	defer srv.Close()

	cb := NewCircuitBreaker(3, 2*time.Second)
	client := &PaymentServiceClient{
		cb:     cb,
		client: &http.Client{Timeout: 2 * time.Second},
	}

	ctx := context.WithValue(context.Background(), "trace_ctx", TraceContext{
		TraceID: "4bf92f3577b34da6a3ce929d0e0e4736",
		SpanID:  "00f067aa0ba902b7",
	})

	slog.Info("Menjalankan panggilan normal (Healthy State)...")
	for i := 1; i <= 3; i++ {
		err := client.Charge(ctx, fmt.Sprintf("ORD-%03d", i), 1000)
		slog.Info("Charge Result", "attempt", i, "error", err, "cb_state", cb.state.String())
	}

	slog.Warn("Menginduksi Downstream Failure (Error State)...")
	atomic.StoreInt32(&downstreamFailure, 1)

	for i := 4; i <= 8; i++ {
		err := client.Charge(ctx, fmt.Sprintf("ORD-%03d", i), 1000)
		slog.Error("Charge Result", "attempt", i, "error", err, "cb_state", cb.state.String())
		time.Sleep(100 * time.Millisecond)
	}

	slog.Info("Downstream dipulihkan. Menunggu sirkuit Cooldown...")
	atomic.StoreInt32(&downstreamFailure, 0)
	time.Sleep(2100 * time.Millisecond)

	slog.Info("Mengeksekusi Canary Request pada State Half-Open...")
	for i := 9; i <= 10; i++ {
		err := client.Charge(ctx, fmt.Sprintf("ORD-%03d", i), 1000)
		slog.Info("Canary Result", "attempt", i, "error", err, "cb_state", cb.state.String())
	}
}
