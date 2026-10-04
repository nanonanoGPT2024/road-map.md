# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis dan Mengimplementasikan Arsitektur Siklus Hidup Layanan (*Service Lifecycle*)**: Membangun mekanisme *Graceful Shutdown* dan *Health Check Probes* (Liveness, Readiness, Startup) yang menguras (*drain*) koneksi aktif tanpa *dropped requests* saat orkestrator kontainer (e.g., Kubernetes) melakukan *rolling update*.
2. **Mengonfigurasi dan Mengoptimalkan Abstraksi Koneksi Data Tier**: Mengonfigurasi *Database Connection Pool* (`max_open_conns`, `max_idle_conns`, `conn_max_lifetime`) berdasarkan metrik kapasitas I/O dan karakteristik konkurensi runtime, serta mencegah *connection leak* dan *thread starvation*.
3. **Mendesain Engine Idempoten & Pengendalian Konkurensi**: Mengimplementasikan *Idempotency-Key pattern* dengan *atomic storage* dan pola *Optimistic Concurrency Control* (OCC) menggunakan verifikasi versi state untuk memitigasi anomali *Lost Updates* pada transaksi paralel.
4. **Menerapkan Pola Ketahanan Sistem Terdistribusi (*Resilience Patterns*)**: Mengonstruksi pola *Retry with Exponential Backoff and Full Jitter*, *Timeout Context Propagation*, dan *Circuit Breaker* untuk mencegah *cascading failure* antar layanan backend.
5. **Menstandardisasi Observabilitas Berbasis Konteks**: Mengintegrasikan *Structured JSON Logging* yang terikat dengan standar W3C *TraceContext* (`traceparent`) dan *Correlation ID* untuk penelusuran *end-to-end request lifecycle*.

---

## 2. Prerequisite

Sebelum memulai modul ini, Anda harus telah menguasai:
* Fundamental protokol HTTP/1.1 dan HTTP/2 (Metode, Status Code, Header, Connection Reuse/Keep-Alive).
* Dasar-dasar RDBMS, SQL DDL/DML, dan konsep dasar transaksi (ACID).
* Paradigma konkurensi (Goroutine/Channels pada Go, atau Event Loop & Promises pada Node.js/TypeScript).
* Arsitektur RESTful API standar dan integrasi layer database dasar.
* Memahami struktur direktori modul sebelumnya: `01-Core-Foundations/BAB-10-Materi-Lanjutan/Module 01`.

---

## 3. Concept & Internal Architecture (Mendalam)

Membangun backend yang siap untuk lingkungan produksi (*production-grade*) membutuhkan pemahaman komprehensif mengenai interaksi antara **Application Runtime Engine**, **OS Kernel Network Stack**, dan **Database Engine Subsystem**.

```
+-----------------------------------------------------------------------------------+
| APPLICATION RUNTIME (Go / Node.js / JVM)                                          |
|                                                                                   |
|  [ Inbound Request ]                                                              |
|          |                                                                        |
|          v                                                                        |
|  +---------------+      +-------------------------+      +---------------------+  |
|  | Context &     | ---> | Idempotency Engine      | ---> | Business Logic      |  |
|  | W3C Tracing   |      | (Redis Atomic Check)    |      | (OCC / State Valid) |  |
|  +---------------+      +-------------------------+      +---------------------+  |
|                                                                     |             |
|                                                                     v             |
|  +------------------------------------------------------------------------------+ |
|  | DATABASE CLIENT CONNECTION POOL (Thread-Safe Ring Buffer / Free-List Pool)   | |
|  |  +------------------+  +------------------+  +------------------+            | |
|  |  | Conn 1: In-Use   |  | Conn 2: Idle     |  | Conn 3: Idle     |  ...       | |
|  |  +------------------+  +------------------+  +------------------+            | |
|  |  * max_open: 50 | max_idle: 25 | conn_max_lifetime: 5m | conn_max_idle: 2m  | |
|  +------------------------------------------------------------------------------+ |
|          | (Pooled TCP Connections)                                               |
+----------|------------------------------------------------------------------------+
           |
           v
+-----------------------------------------------------------------------------------+
| OS KERNEL & NETWORK SUBSYSTEM                                                     |
|                                                                                   |
|  +--------------------------+          +--------------------------+               |
|  | Socket Send/Recv Buffers |  <---->  | TCP Sliding Window /     |               |
|  | (SO_SNDBUF, SO_RCVBUF)   |          | Keep-Alive Probes        |               |
|  +--------------------------+          +--------------------------+               |
|          ^                                                                        |
|          | (TCP Handshake SYN-ACK / File Descriptors: epoll / kqueue)             |
+----------|------------------------------------------------------------------------+
           v
+-----------------------------------------------------------------------------------+
| RDBMS ENGINE (e.g., PostgreSQL / MySQL)                                           |
|                                                                                   |
|  [ Backend Worker Process per Connection / Thread Pool ]                          |
|  +------------------------------------------------------------------------------+ |
|  | Write-Ahead Log (WAL) Buffer ---> Disk (fsync)                                | |
|  | Shared Buffer Pool / InnoDB Buffer Pool (Dirty Pages vs Clean Pages)         | |
|  | MVCC Multi-Version Concurrency Engine (xmin/xmax / Undo Log segments)         | |
|  +------------------------------------------------------------------------------+ |
+-----------------------------------------------------------------------------------+
```

### A. Connection Pool Internals & OS File Descriptors
Aplikasi backend berinteraksi dengan database melalui socket TCP berbasis *network file descriptors* (FD). Setiap pembuatan socket baru memerlukan mekanisme TCP Three-Way Handshake ($SYN \to SYN-ACK \to ACK$) ditambah TLS Handshake (jika terenkripsi). Proses ini memakan sumber daya CPU dan menambah latensi jaringan secara signifikan (1 hingga 3 *network round-trips* / RTT).

Connection Pool memelihara kumpulan socket TCP yang tetap berada dalam status `ESTABLISHED`.
1. **Borrow Phase**: Thread/Goroutine meminta koneksi. Pool mengecek apakah terdapat koneksi idle yang valid.
   - Jika ada koneksi idle: status dialihkan menjadi *in-use*, lalu diserahkan ke thread.
   - Jika tidak ada dan `total_open < max_open`: Pool mengalokasikan socket baru via kernel `connect()`.
   - Jika `total_open >= max_open`: Thread diblokir (*wait queue*) hingga batas timeout peminjaman (`wait_timeout`) terlampaui.
2. **Validation on Borrow**: Memverifikasi apakah socket masih terbuka dengan mengirim paket TCP kosong (e.g., Ping / No-op SQL) atau mengandalkan status socket OS.
3. **Return Phase**: Setelah query selesai dieksekusi, koneksi tidak ditutup via `close()`, melainkan dikembalikan ke *idle queue* connection pool.

### B. Concurrency Control: Optimistic vs. Pessimistic Locking
Ketika dua transaksi membaca dan memperbarui data yang sama secara bersamaan, muncul anomali *Lost Update*.
* **Pessimistic Locking (`SELECT ... FOR UPDATE`)**:
  - Mengunci row data di tingkat penyimpanan engine database (*row-level exclusive lock*).
  - Transaksi lain yang mencoba mengakses baris tersebut akan ditangguhkan (*blocked*) hingga transaksi pertama menjalankan `COMMIT` atau `ROLLBACK`.
  - **Risiko**: Mengurangi *throughput* sistem secara drastis, meningkatkan latensi antrean, dan rawan memicu kondisi *Deadlock* jika urutan penguncian antartabel tidak seragam.
* **Optimistic Concurrency Control (OCC)**:
  - Mengasumsikan konflik konkurensi jarang terjadi. Transaksi membaca data tanpa *lock* eksklusif, menyertakan kolom `version` (integer bertambah bertahap) atau `timestamp`.
  - Ketika data diperbarui, aplikasi mengeksekusi:
    $$\text{UPDATE table SET val = new\_val, version = version + 1 WHERE id = target\_id AND version = current\_version;}$$
  - Jika `RowsAffected == 0`, berarti transaksi lain telah memperbarui data tersebut lebih dulu. Aplikasi kemudian dapat menggagalkan operasi atau melakukan *retry* dari pembacaan awal.

### C. The Idempotency Layer Mechanism
Operasi HTTP POST/PATCH pada sistem backend sering mengalami gangguan jaringan (*network blips* / *packet loss*). Client mengirim request, backend memproses dan menulis ke database, namun respons HTTP terputus sebelum tiba di client. Akibatnya, client melakukan *retry*. Tanpa lapisan idempoten, request duplikat tersebut akan mengeksekusi operasi bisnis berulang kali (e.g., *double charging*).

Arsitektur Idempotency Engine menggunakan penyimpanan *in-memory* terdistribusi (Redis) yang atomic:
1. Membaca header `Idempotency-Key`.
2. Mengeksekusi instruksi atomik: `SET key req_fingerprint NX EX 120` (Not Exists, Expire 120 detik).
3. Jika gagal diset (kunci sudah ada):
   - Jika status masih `IN_PROGRESS`: Kembalikan HTTP `409 Conflict` atau hold/poll sementara.
   - Jika status `COMPLETED`: Baca hasil respons yang telah di-cache, lalu kembalikan langsung ke client tanpa memicu logika bisnis ulang.
4. Jika berhasil diset: Eksekusi transaksi bisnis, simpan payload respons ke Redis, lalu mutakhirkan status menjadi `COMPLETED`.

---

## 4. Why & What

| Dimensi | Pendekatan Naif / Non-Produksi | Pendekatan Enterprise / Arsitektur Lanjutan |
| :--- | :--- | :--- |
| **Siklus Hidup Proses** | Proses dimatikan langsung menggunakan `SIGKILL` atau `os.Exit(0)`. Request yang sedang berjalan putus di tengah jalan (*corrupted state*). | Menangkap `SIGINT` / `SIGTERM`, menghentikan penerimaan trafik baru pada port listener, menyelesaikan request aktif (*draining*), menutup pool koneksi database secara tertib. |
| **Koneksi Database** | Membuat koneksi baru (`sql.Open()`) pada setiap fungsi atau handler HTTP. Menguras pool port TCP OS (*epoll socket exhaustion*). | Menggunakan pool koneksi global terkonfigurasi: batas *open*, batas *idle*, validasi masa aktif koneksi, dan penanganan *idle timeout*. |
| **Penanganan Mutasi Bersamaan** | Langsung `UPDATE accounts SET balance = balance - 100 WHERE id = 1;` tanpa validasi state saat ini. Rentan *Race Condition*. | Optimistic Locking berbasis `version` atau state machine terverifikasi yang memastikan data hanya berubah jika *initial state* belum berubah. |
| **Kegagalan Layanan Eksternal** | Melakukan *retry* tak terbatas (*infinite loop*) atau *retry* konstan secara bersamaan, memicu efek *Thundering Herd* dan melumpuhkan dependensi. | Pola *Retry* dengan *Exponential Backoff* dan *Full Jitter*, dibatasi oleh Context Timeout ketat dan dilindungi Circuit Breaker. |
| **Pelacakan Masalah (Debugging)** | `fmt.Println` atau string log tanpa konteks dan tanpa format terstruktur. Mustahil diurai (*unparseable*) oleh log aggregator (e.g., Elasticsearch, Loki). | Log terstruktur berbasis JSON (*key-value*) yang menyertakan atribut kontekstual wajib: `timestamp`, `level`, `trace_id`, `span_id`, dan `caller`. |

---

## 5. How (Workflow Detail)

### Alur Eksekusi: Request Lifecycle dengan Idempotency, OCC, dan Resilience

```
Client               API Gateway / Handler         Idempotency Store (Redis)      Postgres Database
  |                            |                               |                          |
  |--- [1] POST /transfers --->|                               |                          |
  |    (Header: Idempotency)   |--- [2] Atomic Acquire Lock -->|                          |
  |                            |    (SET key NX EX 60)         |                          |
  |                            |<-- [3] OK (Lock Acquired) ----|                          |
  |                            |                               |                          |
  |                            |--- [4] Ambil Data & Version ---------------------------->|
  |                            |<-- [5] Return balance=500, version=3 --------------------|
  |                            |                               |                          |
  |                            |    [6] Validasi & Mutasi      |                          |
  |                            |    (new_balance = 400)        |                          |
  |                            |                               |                          |
  |                            |--- [7] UPDATE ... WHERE id=1 AND version=3 ------------->|
  |                            |<-- [8] Rows Affected = 1 (Sukses) -----------------------|
  |                            |                               |                          |
  |                            |--- [9] Simpan Hasil Respons ->|                          |
  |                            |    (SET key_resp JSON EX 86400)                          |
  |                            |<-- [10] OK -------------------|                          |
  |                            |                               |                          |
  |<-- [11] HTTP 201 Created --|                               |                          |
```

1. **Inisialisasi Konteks & Tracing**: Handler menerima request, mengekstrak W3C `traceparent` dari header. Jika tidak ada, handler menghasilkan UUID v4 baru sebagai Correlation/Trace ID dan menyuntikkannya ke dalam konteks eksekusi.
2. **Pengecekan Idempotensi**:
   - Handler mengekstrak header `Idempotency-Key`.
   - Mengirim perintah atomik ke Redis. Jika kunci sudah memiliki nilai respons, handler menghentikan alur dan langsung mengembalikan payload respons tersebut dengan header `X-Cache-Lookup: HIT`.
3. **Optimistic Concurrency Check (OCC)**:
   - Handler membaca baris basis data saat ini beserta kolom `version`.
   - Menjalankan kalkulasi logika domain pada layer aplikasi.
   - Menjalankan mutasi `UPDATE` yang menyertakan klausa `WHERE version = :current_version`.
4. **Verifikasi Mutasi**:
   - Jika `RowsAffected == 0`, mutasi gagal karena konflik konkurensi (versi telah berubah oleh proses lain). Handler membatalkan transaksi (*abort*) dan menjalankan skema *exponential retry* atau melempar HTTP `409 Conflict`.
   - Jika `RowsAffected == 1`, transaksi berhasil di-*commit*.
5. **Persistensi Idempotensi**:
   - Menyimpan payload respons sukses dan status HTTP ke dalam Redis dengan durasi *Time-To-Live* (TTL).
6. **Graceful Pipeline Exit**:
   - Handler mengembalikan respons ke client. Seluruh koneksi database dan Redis dikembalikan ke pool masing-masing.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem: Dapur Restoran Bintang Lima vs. Dapur Amatir
* **Amatir (Non-Produksi)**: Setiap kali pesanan masuk, koki pergi ke pasar untuk membeli wajan baru (*handshake TCP baru*). Saat jam tutup tiba, lampu dapur langsung dimatikan paksa (*SIGKILL*), meninggalkan makanan yang sedang dimasak gosong di wajan (*corrupted dirty write*).
* **Enterprise (Produksi)**:
  * **Connection Pool**: Dapur memiliki rak berisi 20 wajan yang selalu bersih dan siap pakai. Koki mengambil wajan yang tersedia, memakainya, mencucinya, lalu mengembalikannya ke rak. Jika semua wajan sedang dipakai, pesanan berikutnya menunggu di antrean hingga batas waktu tertentu.
  * **Graceful Shutdown**: Saat jam operasional berakhir, pelayan menolak pelanggan baru di pintu depan (*Readiness Probe: Unhealthy*). Koki menyelesaikan semua masakan yang sudah dipesan (*draining in-flight requests*). Setelah pesanan terakhir disajikan, koki mematikan kompor dan mengunci dapur (*resource cleanup*).

### State Transition Diagram: Graceful Shutdown Lifecycle

```
[OS Signal: SIGTERM / SIGINT]
             |
             v
+-------------------------------------------------------------+
| State 1: SHUTTING_DOWN Triggered                            |
| - Readiness Probe dialihkan ke HTTP 503 Service Unavailable |
| - Kubernetes / Load Balancer mencabut Pod dari target pool  |
| - Server listener berhenti menerima koneksi baru            |
+-------------------------------------------------------------+
             |
             | (Berikan window jeda toleransi traffic route: 5s)
             v
+-------------------------------------------------------------+
| State 2: Request Draining Phase                             |
| - Menunggu context server (HTTP Server Shutdown)            |
| - Menyelesaikan semua koneksi TCP yang sedang aktif         |
| - Dibatasi oleh max timeout shutdown (e.g., 30 detik)       |
+-------------------------------------------------------------+
             |
             | (Setelah seluruh HTTP Handler selesai)
             v
+-------------------------------------------------------------+
| State 3: Downstream Teardown Phase                          |
| - Menutup Pool Koneksi Database (db.Close())                |
| - Menutup Koneksi Redis Cache & Message Broker (AMQP/Kafka) |
| - Membilas buffer log ke output stream (Flush logger)       |
+-------------------------------------------------------------+
             |
             v
[Process Exit: Code 0]
```

---

## 7. Simple Example & Practical Example

### Practical Example: Production Core Engine (Go)
Implementasi berikut menggunakan pustaka standar Go dan driver `pgx`/database standar industri untuk mendemonstrasikan:
1. Pool koneksi teroptimasi.
2. Graceful Shutdown multi-tahap.
3. Structured Logging dengan penelusuran konteks (*context-bound tracing*).
4. Mutasi aman berbasis Optimistic Concurrency Control (OCC).

```go
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

// --- Domain Models & Exceptions ---

var (
	ErrOptimisticLockConflict = errors.New("konflik konkurensi: state data telah berubah")
	ErrAccountNotFound        = errors.New("akun target tidak ditemukan")
	ErrInsufficientBalance    = errors.New("saldo tidak mencukupi")
)

type Account struct {
	ID        int64     `json:"id"`
	OwnerName string    `json:"owner_name"`
	Balance   int64     `json:"balance"` // Menggunakan integer (satuan sen/cents) untuk mencegah floating-point inaccuracy
	Version   int64     `json:"version"`
	UpdatedAt time.Time `json:"updated_at"`
}

type TransferRequest struct {
	AccountID int64 `json:"account_id"`
	Amount    int64 `json:"amount"`
}

// --- Application Server Engine ---

type ApplicationEngine struct {
	db      *sql.DB
	logger  *slog.Logger
	isReady atomic.Bool
}

func (app *ApplicationEngine) SetupDatabasePool(dsn string) error {
	db, err := sql.Open("pgx", dsn)
	if err != nil {
		return fmt.Errorf("gagal menginisialisasi driver database: %w", err)
	}

	// Konfigurasi Pool Produksi
	db.SetMaxOpenConns(25)                  // Disesuaikan dengan batas kapasitas koneksi core database
	db.SetMaxIdleConns(10)                  // Mencegah spike handshake connection
	db.SetConnMaxLifetime(15 * time.Minute) // Menutup koneksi lama untuk load balancing PgBouncer/RDS
	db.SetConnMaxIdleTime(5 * time.Minute)  // Mengurangi footprint memori saat trafik rendah

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		return fmt.Errorf("ping awal database gagal: %w", err)
	}

	app.db = db
	return nil
}

// Service Mutasi Akun Menggunakan OCC (Optimistic Concurrency Control)
func (app *ApplicationEngine) DeductBalanceOCC(ctx context.Context, accountID int64, amount int64) (*Account, error) {
	const maxRetries = 3
	var backoff = 50 * time.Millisecond

	for attempt := 1; attempt <= maxRetries; attempt++ {
		// 1. Baca data dan versi saat ini
		queryRead := `SELECT id, owner_name, balance, version, updated_at FROM accounts WHERE id = $1`
		row := app.db.QueryRowContext(ctx, queryRead, accountID)

		var acc Account
		err := row.Scan(&acc.ID, &acc.OwnerName, &acc.Balance, &acc.Version, &acc.UpdatedAt)
		if err != nil {
			if errors.Is(err, sql.ErrNoRows) {
				return nil, ErrAccountNotFound
			}
			return nil, fmt.Errorf("gagal query akun: %w", err)
		}

		// 2. Validasi aturan bisnis
		if acc.Balance < amount {
			return nil, ErrInsufficientBalance
		}

		// 3. Eksekusi conditional update menggunakan version tag
		queryUpdate := `
			UPDATE accounts 
			SET balance = balance - $1, version = version + 1, updated_at = NOW() 
			WHERE id = $2 AND version = $3
			RETURNING version, updated_at`

		var newVersion int64
		var newUpdatedAt time.Time

		err = app.db.QueryRowContext(ctx, queryUpdate, amount, acc.ID, acc.Version).Scan(&newVersion, &newUpdatedAt)
		if err != nil {
			if errors.Is(err, sql.ErrNoRows) {
				// Terjadi benturan data dengan proses lain, jalankan retry
				app.logger.WarnContext(ctx, "deteksi konflik OCC, memulai retry",
					slog.Int("attempt", attempt),
					slog.Int64("account_id", accountID),
					slog.Int64("conflict_version", acc.Version),
				)
				select {
				case <-ctx.Done():
					return nil, ctx.Err()
				case <-time.After(backoff):
					backoff *= 2 // Exponential backoff sederhana
					continue
				}
			}
			return nil, fmt.Errorf("eksekusi update gagal: %w", err)
		}

		// Update berhasil
		acc.Balance -= amount
		acc.Version = newVersion
		acc.UpdatedAt = newUpdatedAt
		return &acc, nil
	}

	return nil, ErrOptimisticLockConflict
}

// --- HTTP Handlers ---

func (app *ApplicationEngine) HandleDeduct(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	traceID := r.Header.Get("X-Trace-ID")
	if traceID == "" {
		traceID = fmt.Sprintf("trace-%d", time.Now().UnixNano())
	}

	// Buat context log terstruktur
	log := app.logger.With(slog.String("trace_id", traceID))

	var req TransferRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		log.ErrorContext(ctx, "payload request tidak valid", slog.String("error", err.Error()))
		http.Error(w, `{"error":"payload malformed"}`, http.StatusBadRequest)
		return
	}

	updatedAccount, err := app.DeductBalanceOCC(ctx, req.AccountID, req.Amount)
	if err != nil {
		switch {
		case errors.Is(err, ErrInsufficientBalance):
			http.Error(w, `{"error":"saldo tidak mencukupi"}`, http.StatusUnprocessableEntity)
		case errors.Is(err, ErrAccountNotFound):
			http.Error(w, `{"error":"akun tidak ditemukan"}`, http.StatusNotFound)
		case errors.Is(err, ErrOptimisticLockConflict):
			http.Error(w, `{"error":"konflik transaksi, silakan coba beberapa saat lagi"}`, http.StatusConflict)
		default:
			log.ErrorContext(ctx, "kegagalan internal sistem", slog.String("error", err.Error()))
			http.Error(w, `{"error":"kesalahan sistem internal"}`, http.StatusInternalServerError)
		}
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(updatedAccount)
}

func (app *ApplicationEngine) HandleReadiness(w http.ResponseWriter, r *http.Request) {
	if !app.isReady.Load() {
		http.Error(w, "Service Unavailable - Shutting Down", http.StatusServiceUnavailable)
		return
	}

	// Validasi kesiapan koneksi database
	ctx, cancel := context.WithTimeout(r.Context(), 1*time.Second)
	defer cancel()

	if err := app.db.PingContext(ctx); err != nil {
		http.Error(w, "Database Unreachable", http.StatusServiceUnavailable)
		return
	}

	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"UP"}`))
}

// --- Main Bootstrap & Graceful Shutdown Orchestration ---

func main() {
	// 1. Inisialisasi Structured Logging Engine (JSON Output)
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))

	engine := &ApplicationEngine{
		logger: logger,
	}

	// 2. Setup Persistence Layer
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "postgres://postgres:postgres@localhost:5432/core_banking?sslmode=disable"
	}
	if err := engine.SetupDatabasePool(dsn); err != nil {
		logger.Error("kegagalan bootstrap database", slog.String("error", err.Error()))
		os.Exit(1)
	}
	defer func() {
		if err := engine.db.Close(); err != nil {
			logger.Error("error saat menutup koneksi database pool", slog.String("error", err.Error()))
		}
	}()

	// 3. Routing Layer
	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/accounts/deduct", engine.HandleDeduct)
	mux.HandleFunc("/healthz/ready", engine.HandleReadiness)

	srv := &http.Server{
		Addr:         ":8080",
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// Tandai status aplikasi aktif (Readiness = UP)
	engine.isReady.Store(true)

	// 4. Thread Pengawasan Signal OS (SIGINT/SIGTERM)
	shutdownSignal := make(chan os.Signal, 1)
	signal.Notify(shutdownSignal, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		logger.Info("server HTTP listening pada port :8080")
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("server HTTP crash mendadak", slog.String("error", err.Error()))
			os.Exit(1)
		}
	}()

	// Menunggu sinyal interupsi sistem
	sig := <-shutdownSignal
	logger.Info("sinyal terminasi diterima, memulai graceful shutdown sequence", slog.String("signal", sig.String()))

	// LANGKAH 1: Set readiness menjadi false agar load balancer mengalihkan traffic baru
	engine.isReady.Store(false)
	logger.Info("readiness probe diubah ke status: NOT READY")

	// LANGKAH 2: Jeda singkat untuk sinkronisasi pembaruan rute pada load balancer
	time.Sleep(2 * time.Second)

	// LANGKAH 3: Beri batasan waktu total draining koneksi aktif
	drainCtx, drainCancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer drainCancel()

	if err := srv.Shutdown(drainCtx); err != nil {
		logger.Error("graceful shutdown dipaksa berhenti karena melampaui timeout", slog.String("error", err.Error()))
	} else {
		logger.Info("seluruh request aktif berhasil diselesaikan (drained)")
	}

	logger.Info("sistem backend berhenti secara bersih (clean exit)")
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Flash Sale E-Commerce Tier-1 & Anomali Double-Disbursement

#### Latar Belakang & Gejala Masalah
Sebuah platform marketplace skala besar meluncurkan kampanye diskon kilat (*Flash Sale*). Pada detik peluncuran, sistem menerima 45.000 Request Per Second (RPS) pada endpoint `/checkout`. Terjadi dua insiden fatal:
1. **Database Connection Exhaustion**: Layanan backend langsung mengalami *crash loop* karena driver membuat ribuan koneksi baru ke basis data. Hal ini memicu *thread starvation* pada database engine, membuat CPU PostgreSQL mencapai 100%, dan transaksi non-flash-sale ikut terdampak (*cascading failure*).
2. **Double Spending & Negative Inventory**: Kuota item flash sale yang seharusnya hanya berjumlah 100 unit, terjual hingga 128 unit (selisih 28 item). Selain itu, akun dompet digital pelanggan terpotong dua kali (*double deduction*) saat jaringan seluler pengguna mengalami gangguan intermiten (*retry storm*).

#### Akar Masalah (Root Cause Analysis)
* **Ketiadaan Pool Sizing**: Konfigurasi koneksi dibiarkan *default* (`max_open_conns` tanpa batas). Akibatnya, 20 instans backend masing-masing membuka hingga 500 koneksi ke basis data, melebihi kapasitas memori kerja (`work_mem`) instance database.
* **Race Condition / Lost Update**: Transaksi inventaris menggunakan logika baca lalu tulis biasa:
  ```sql
  -- VULNERABLE PATTERN
  SELECT stock FROM products WHERE id = 101; 
  -- Logika aplikasi: if (stock > 0)
  UPDATE products SET stock = stock - 1 WHERE id = 101;
  ```
  Di bawah konkurensi 1.000 thread paralel, beberapa thread membaca nilai `stock = 1` secara bersamaan sebelum mutasi pertama di-commit, menyebabkan pengurangan ganda.
* **Absennya Lapisan Idempotensi**: Aplikasi frontend mengirimkan request ulang setiap kali request pertama mengalami timeout pada jaringan seluler (3G/4G). Backend tidak memiliki mekanisme deduplikasi, sehingga memproses ulang request tersebut sebagai transaksi baru.

#### Solusi Arsitektur & Hasil

```
[ Client Request ]
        |
        v
[ API Gateway / Envoy Proxy ]
        | (Distributed Rate Limiting via Redis Token Bucket)
        v
[ Backend Pods Engine ]
   ├──> [ Idempotency Interceptor ] ---> Validasi Key & Status Redis
   ├──> [ Connection Pool Limiter ] ---> Dibatasi: max_open = 20 per pod
   └──> [ Optimistic Lock Handler ] ---> Conditional State Mutation
                                           |
                                           v
                          [ PostgreSQL with Strict OCC ]
                          UPDATE products 
                          SET stock = stock - 1, version = version + 1 
                          WHERE id = 101 AND version = :v AND stock > 0;
```

1. **Penerapan Connection Sizing Formula**:
   Pool database disesuaikan menggunakan rumus baku:
   $$\text{Max Connections} = (\text{Core CPU DB} \times 2) + \text{Spindle Disk Count}$$
   Pada server 16 vCPU, total pool ditetapkan maksimum 34 koneksi. Nilai ini dibagi merata ke setiap pod backend dengan buffer proksi PgBouncer di depannya.
2. **Implementasi Idempotency Engine**:
   Setiap transaksi wajib membawa header `Idempotency-Key` (UUIDv4 yang dibuat di sisi client). Backend memverifikasi kunci ini ke kluster Redis menggunakan operasi *atomic conditional write*. Jika kunci sudah tercatat dalam 24 jam terakhir, request duplikat langsung mendapatkan hasil tanpa memproses ulang mutasi data.
3. **Optimistic Concurrency Control (OCC) + DB Invariant Check**:
   Klausa mutasi stok diubah menjadi atomic invariant update:
   `UPDATE products SET stock = stock - 1 WHERE id = 101 AND stock >= 1;`
   Jika `RowsAffected == 0`, sistem langsung memberikan respons bahwa stok telah habis tanpa membebani transaksi database dengan mekanisme *exclusive lock*.

**Hasil**: Platform mampu memproses lonjakan 60.000 RPS tanpa *crash*, inkonsistensi stok berkurang menjadi 0 kasus, dan utilisasi CPU database stabil di angka 68%.

---

## 9. Trade-offs

| Parameter Desain | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Concurrency Control** | **Optimistic Locking (OCC)** (Basis Version/Timestamp) | **Pessimistic Locking** (`SELECT ... FOR UPDATE`) | **OCC** memiliki throughput sangat tinggi pada kondisi sistem yang didominasi operasi baca (*read-heavy*), tanpa risiko transaksi menggantung (*deadlock-free*). Namun, jika tingkat konflik data sangat tinggi (*extreme contention*), OCC memicu banyak proses *retry* yang membebani CPU.<br>**Pessimistic** menjamin kepastian mutasi pada percobaan pertama, namun menahan koneksi data lebih lama, meningkatkan latensi antrean, dan berisiko memicu *deadlock*. |
| **Connection Pool Sizing** | **Aggressive Pooling** (`max_open` bernilai sangat besar, misal: 500) | **Conservative/Lean Pooling** (`max_open` disesuaikan dengan kapasitas vCPU DB, misal: 25) | Pool yang terlalu besar membebani *memory context-switching* pada kernel database dan berisiko memicu *Out-Of-Memory* (OOM). Sebaliknya, pool yang terlalu kecil menyebabkan request tertahan di antrean aplikasi (*application queuing delay*), meningkatkan respons time pada jam sibuk (*tail latency*). |
| **Idempotency Strategy** | **Client-Generated Key (Header Driven)** | **Payload Fingerprinting** (Hash SHA-256 dari seluruh isi request) | **Client-Generated Key** memberikan fleksibilitas bagi client untuk menentukan intensi transaksi. Namun, sistem rentan terhadap bug jika implementasi generator UUID di client tidak acak.<br>**Payload Hashing** mencegah perubahan payload pada data yang sama, tetapi membebani CPU backend untuk kalkulasi hash dan dapat keliru jika urutan key JSON berubah. |
| **Resilience Strategy** | **Fast Fail** (Langsung kembalikan pesan error tanpa retry) | **Retry with Exponential Backoff + Jitter** | **Fast Fail** menjaga ketersediaan sumber daya komputasi internal, namun berdampak langsung pada pengalaman pengguna akhir (*poor user experience*).<br>**Retry + Jitter** meningkatkan probabilitas keberhasilan operasi saat terjadi gangguan jaringan intermiten, namun menambah waktu tunggu client (*higher latency*) dan kompleksitas tracing. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Connection Leak Akibat Tidak Menutup Query Result Set
* **Gejala**: Metrik koneksi aktif (`open_connections`) terus merangkak naik hingga menyentuh batas maksimum `max_open_conns`. Request baru mulai mengalami timeout dengan pesan error: `context deadline exceeded (driver: connection pool exhausted)`.
* **Penyebab**: Kode program mengeksekusi `db.Query()`, namun lupa memanggil `rows.Close()` di dalam blok `defer`. Akibatnya, koneksi TCP tetap dialokasikan ke result-set dan tidak pernah kembali ke pool.
* **Solusi Perbaikan**:
  ```go
  // SALAH: Memory & Connection leak
  rows, err := db.QueryContext(ctx, "SELECT id FROM large_table")
  // Jika handler keluar di sini karena error parsing, koneksi hang selamanya

  // BENAR: Selalu gunakan defer rows.Close() langsung setelah error handling
  rows, err := db.QueryContext(ctx, "SELECT id FROM large_table")
  if err != nil {
      return err
  }
  defer rows.Close() // Pastikan baris ini selalu dieksekusi untuk mengembalikan koneksi
  ```

### 2. Goroutine/Thread Leaks pada Mekanisme Graceful Shutdown
* **Gejala**: Aplikasi menerima sinyal `SIGTERM`, namun proses tidak kunjung mati hingga batas waktu terminasi orkestrator terlewati (e.g., Kubernetes mengirimkan `SIGKILL` paksa setelah 30 detik).
* **Penyebab**: Terdapat *worker goroutine* atau *background task* yang mendengarkan channel tanpa menyediakan opsi pembatalan konteks (`ctx.Done()`), sehingga goroutine tersebut terblokir selamanya (*hang*).
* **Solusi Perbaikan**: Pastikan seluruh loop dan pembacaan channel downstream selalu memantau pembatalan konteks:
  ```go
  for {
      select {
      case <-ctx.Done():
          // Bersihkan resource lokal, lalu keluar dari loop
          return ctx.Err()
      case msg := <-taskQueue:
          processTask(msg)
      }
  }
  ```

### 3. Masalah Thundering Herd Akibat Retry Tanpa Jitter
* **Gejala**: Layanan hilir (*downstream service*) sempat mengalami perlambatan selama beberapa detik. Saat layanan tersebut mulai pulih, seluruh layanan hulu (*upstream*) mengirimkan request *retry* secara serentak di detik yang sama, menyebabkan downstream kembali *crash* total.
* **Penyebab**: Menggunakan formula retry backoff deterministik:
  $$\text{Interval} = \text{base\_delay} \times 2^{\text{attempt}}$$
  Hal ini menyebabkan ribuan request yang gagal di waktu $T$ akan mencoba ulang secara bersamaan di waktu $T + 2\text{s}$, $T + 4\text{s}$, dan seterusnya.
* **Solusi Perbaikan**: Terapkan algoritma **Full Jitter**:
  ```go
  // Formula Full Jitter: Sleep = rand(0, min(cap, base * 2^attempt))
  temp := math.Min(float64(maxCap), float64(baseDelay)*math.Pow(2, float64(attempt)))
  sleep := time.Duration(rand.Float64() * temp)
  time.Sleep(sleep)
  ```

---

## 11. Best Practices (Production Checklist)

Gunakan tabel checklist evaluasi mandiri berikut sebelum merilis layanan ke Production:

| Status | Komponen | Item Verifikasi Kritis |
| :---: | :--- | :--- |
| [ ] | **Lifecycle** | Penanganan sinyal OS `SIGINT` dan `SIGTERM` terdaftar secara eksplisit pada process runner utama. |
| [ ] | **Lifecycle** | Prosedur shutdown menyediakan waktu toleransi (*grace period*) minimal 5–15 detik untuk menyelesaikan *in-flight requests*. |
| [ ] | **Lifecycle** | Endpoint `/healthz/ready` (Readiness Probe) langsung mengembalikan status HTTP `503` segera setelah sinyal shutdown diterima. |
| [ ] | **Persistence** | `MaxOpenConns` dikonfigurasi secara eksplisit (tidak menggunakan nilai default tak terbatas). |
| [ ] | **Persistence** | `ConnMaxLifetime` diatur lebih singkat daripada nilai timeout koneksi TCP pada infrastruktur (e.g., AWS NAT Gateway = 350 detik, PgBouncer = 1 jam). |
| [ ] | **Persistence** | Setiap pemanggilan query SQL memanfaatkan `QueryContext` atau `ExecContext` dengan pembatasan durasi via `context.WithTimeout`. |
| [ ] | **Concurrency** | Tabel basis data yang sering mengalami mutasi bersamaan dilengkapi kolom `version` (OCC) atau pengecekan *invariant condition*. |
| [ ] | **Concurrency** | Setiap mutasi penting mengembalikan dan memvalidasi `RowsAffected` untuk mendeteksi potensi anomali *Lost Updates*. |
| [ ] | **Idempotency** | Seluruh transaksi pengubahan data finansial atau mutasi inventaris mewajibkan penggunaan header `Idempotency-Key`. |
| [ ] | **Resilience** | Pemanggilan API eksternal dibatasi timeout ketat dan menerapkan retry dengan algoritma *Exponential Backoff* + *Jitter*. |
| [ ] | **Observability** | Seluruh output log menggunakan format JSON terstruktur ke `stdout` dan menyertakan `trace_id` atau W3C `traceparent`. |

---

## 12. Hands-on Practice

Buatlah struktur proyek berikut untuk menguji pemahaman arsitektur Anda di lingkungan lokal:

```text
hands-on/m02/
├── cmd/
│   └── api/
│       └── main.go
├── internal/
│   ├── config/
│   │   └── database.go
│   ├── platform/
│   │   ├── idempotency/
│   │   │   └── memory_store.go
│   │   └── resilience/
│   │       └── retry.go
│   └── service/
│       └── account_service.go
├── go.mod
└── docker-compose.yml
```

### Langkah 1: Siapkan Lingkungan Kerja Database via Docker Compose
Simpan file berikut di `hands-on/m02/docker-compose.yml`:
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: engine_user
      POSTGRES_PASSWORD: engine_password
      POSTGRES_DB: engine_db
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U engine_user -d engine_db"]
      interval: 5s
      timeout: 5s
      retries: 5
```
Jalankan dependensi basis data:
```bash
docker compose up -d
```

### Langkah 2: Inisialisasi Skema Database OCC
Hubungkan client database ke PostgreSQL lalu eksekusi DDL berikut:
```sql
CREATE TABLE IF NOT EXISTS accounts (
    id BIGSERIAL PRIMARY KEY,
    owner_name VARCHAR(100) NOT NULL,
    balance BIGINT NOT NULL CHECK (balance >= 0),
    version BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO accounts (id, owner_name, balance, version) 
VALUES (1, 'Alice Corp Treasury', 1000000, 1)
ON CONFLICT (id) DO NOTHING;
```

### Langkah 3: Implementasi Modul Retry dengan Full Jitter
Tulis kode berikut di `hands-on/m02/internal/platform/resilience/retry.go`:
```go
package resilience

import (
	"context"
	"crypto/rand"
	"math/big"
	"time"
)

type RetryableFunc func(ctx context.Context) error

func ExecuteWithRetry(ctx context.Context, maxAttempts int, baseDelay time.Duration, fn RetryableFunc) error {
	var err error
	for attempt := 0; attempt < maxAttempts; attempt++ {
		if err = fn(ctx); err == nil {
			return nil
		}

		if attempt == maxAttempts-1 {
			break
		}

		// Kalkulasi Full Jitter: Sleep = rand(0, baseDelay * 2^attempt)
		multiplier := int64(1 << attempt)
		maxSleepMs := baseDelay.Milliseconds() * multiplier

		randomBig, _ := rand.Int(rand.Reader, big.NewInt(maxSleepMs+1))
		jitteredDuration := time.Duration(randomBig.Int64()) * time.Millisecond

		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(jitteredDuration):
		}
	}
	return err
}
```

### Langkah 4: Uji Skenario Concurrency Race
Jalankan pengujian beban konkurensi menggunakan utilitas *curl* paralel atau script testing untuk membuktikan bahwa OCC berhasil mencegah race condition tanpa merusak konsistensi saldo:
```bash
# Kirim 10 request secara paralel untuk mendebet akun id=1 sebesar 10.000
for i in {1..10}; do
  curl -X POST http://localhost:8080/api/v1/accounts/deduct \
    -H "Content-Type: application/json" \
    -H "X-Trace-ID: manual-test-$i" \
    -d '{"account_id": 1, "amount": 10000}' &
done
wait
```

---

## 13. Exercise

### Level Easy
Modifikasi handler `/healthz/ready` pada program utama agar membaca metrik database pool (`db.Stats()`). Kembalikan kode status HTTP `503 Service Unavailable` apabila parameter `db.Stats().WaitDuration` rata-rata melebihi 500 milidetik (indikasi antrean koneksi database mulai jenuh).
* **Acceptance Criteria**: Endpoint merespons dengan format JSON yang memuat detail metrik (`open_connections`, `in_use`, `wait_count`) dan mengembalikan kode status 503 saat pool koneksi jenuh.

### Level Medium
Bangun middleware HTTP Idempotensi menggunakan media penyimpanan *in-memory* yang aman dari race condition (`sync.Map`). Middleware bertugas:
1. Membaca header `Idempotency-Key`. Jika header tidak ditemukan, kembalikan respons error `400 Bad Request`.
2. Jika request pertama sedang diproses, request kedua dengan key yang sama harus menunggu maksimal 3 detik sebelum mengembalikan error `409 Conflict`.
3. Mengembalikan salinan respons yang sama (termasuk status code dan header) jika key tersebut sudah pernah diproses hingga selesai.
* **Acceptance Criteria**: Lolos pengujian konkurensi (20 request simultan dengan key yang identik hanya boleh mengeksekusi *core business handler* sebanyak satu kali).

### Level Hard
Implementasikan skema mitigasi anomali transaksi *Cross-Service Orchestration* sederhana. Buat sebuah worker engine yang membatalkan (*rollback via compensating transaction*) mutasi saldo rekening apabila pengiriman notifikasi via webhook pihak ketiga mengalami kegagalan permanen setelah melewati batas 3 kali *retry with jitter*.
* **Acceptance Criteria**: Database menggunakan prinsip ACID yang ketat; mutasi dibatalkan secara konsisten menggunakan kompensasi saldo (`balance = balance + amount`), dan log audit mencatat seluruh siklus hidup transaksi lengkap beserta `trace_id`.

---

## 14. Challenge

### Studi Kasus: High-Throughput Ticket Booking Engine (Overselling Zero-Tolerance)

#### Deskripsi Tantangan
Anda ditugaskan merancang modul inti *Ticket Reservation Engine* untuk konser berskala internasional. Sistem memiliki kuota 5.000 tiket. Diperkirakan 250.000 pengguna akan mengakses sistem secara serentak pada 10 detik pertama pembukaan penjualan. 

#### Kebutuhan & Batasan Sistem:
1. **Zero Overselling**: Sistem sama sekali tidak boleh menjual tiket melebihi kapasitas kuota (kuota akhir mutlak harus bernilai $\ge 0$).
2. **Fairness Timeout Window**: Tiket yang sudah dipilih oleh pengguna akan ditahan (*reserved*) selama 10 menit. Jika pengguna tidak menyelesaikan pembayaran dalam kurun waktu tersebut, reservasi harus otomatis kedaluwarsa dan kuota tiket kembali tersedia untuk pengguna lain.
3. **Database Guardrails**: Server database memiliki spesifikasi terbatas (4 vCPU, 8 GB RAM). Anda dilarang membiarkan ribuan request membebani database dengan *lock* baris yang lama (*long-held pessimistic locks*).
4. **Resilience**: Sistem harus tetap beroperasi secara normal meskipun salah satu node cache mengalami *restart* mendadak di tengah event penjualan.

#### Deliverable yang Harus Dipersiapkan:
* Skema arsitektur penyimpanan (DDL PostgreSQL dan/atau skema key data structure Redis).
* Pseudocode alur proses reservasi tiket, lengkap dengan penanganan batas waktu (*expiry worker*), mitigasi *concurrency race condition*, dan penerapan lapisan idempoten.
* Analisis teknis mengenai alasan pemilihan pola konkurensi yang Anda gunakan, serta perhitungan estimasi kapasitas *throughput* sistem.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara sinyal sistem operasi `SIGTERM` dan `SIGKILL`?**
   - A. `SIGTERM` mematikan proses seketika tanpa peringatan, sedangkan `SIGKILL` memberikan jeda waktu 10 detik.
   - B. `SIGTERM` dapat ditangkap dan ditangani oleh aplikasi untuk memulai proses pembersihan (*cleanup*), sedangkan `SIGKILL` langsung menghentikan proses di tingkat OS kernel.
   - C. `SIGTERM` dikirim oleh CPU saat memori habis, sedangkan `SIGKILL` dipicu manual oleh administrator.
   - D. Tidak ada perbedaan fungsional; keduanya merupakan alias pada POSIX kernel.
   *Jawaban yang benar: B* — `SIGTERM` adalah sinyal terminasi yang memberi kesempatan pada aplikasi untuk menjalankan *graceful shutdown*, sedangkan `SIGKILL` langsung menghentikan eksekusi thread proses di level kernel.

2. **Apa dampak utama jika nilai konfigurasi `db.SetMaxIdleConns()` disetel ke angka 0?**
   - A. Aplikasi berjalan lebih efisien karena konsumsi memori menjadi minimum.
   - B. Seluruh query yang dijalankan aplikasi akan otomatis mengalami kegagalan.
   - C. Setiap query yang selesai dieksekusi akan langsung menutup koneksi TCP, memaksa query berikutnya melakukan *three-way handshake* ulang.
   - D. Koneksi database pool menjadi bersifat *unlimited*.
   *Jawaban yang benar: C* — Jika `MaxIdleConns` bernilai 0, pool tidak akan menyimpan koneksi idle; setiap koneksi yang selesai digunakan langsung ditutup, sehingga sistem kehilangan manfaat penggunaan ulang koneksi (*connection reuse*).

3. **Anomali konkurensi apa yang terjadi saat dua transaksi membaca data yang sama lalu menulis pembaruan secara bersamaan tanpa mekanisme locking?**
   - A. Dirty Read.
   - B. Non-Repeatable Read.
   - C. Lost Update.
   - D. Phantom Read.
   *Jawaban yang benar: C* — Kondisi di mana pembaruan dari satu transaksi menimpa pembaruan dari transaksi lain tanpa memperhitungkan perubahan yang baru saja dilakukan disebut *Lost Update*.

4. **Metode HTTP mana yang menurut spesifikasi RFC 7231 harus bersifat idempoten secara natural?**
   - A. POST, PATCH, CONNECT.
   - B. GET, PUT, DELETE.
   - C. POST, PUT, DELETE.
   - D. Seluruh metode HTTP bersifat idempoten jika backend menggunakan RDBMS.
   *Jawaban yang benar: B* — Spesifikasi RFC mendefinisikan GET (safe/idempotent), PUT (idempotent), dan DELETE (idempotent) sebagai metode yang memberikan status sistem akhir yang sama meskipun dipanggil berulang kali dengan parameter serupa.

5. **Apa fungsi utama komponen Jitter pada mekanisme Exponential Backoff?**
   - A. Mengurangi pemakaian CPU saat melakukan kalkulasi hashing.
   - B. Menghindari tabrakan request berkala dengan menambahkan variasi acak pada interval waktu tunggu retry.
   - C. Mempercepat proses pengiriman request dengan memotong durasi tunggu menjadi setengahnya.
   - D. Memastikan durasi penundaan setiap worker memiliki nilai yang sama persis.
   *Jawaban yang benar: B* — Jitter menyuntikkan keacakan pada interval penundaan retry untuk memecah sinkronisasi percobaan ulang serentak dari banyak client (*Thundering Herd*).

---

### Bagian 2: Intermediate (5 Pertanyaan)
6. **Pada pola Optimistic Concurrency Control (OCC), apa arti indikator teknis `RowsAffected == 0` saat query UPDATE berbasis versi dieksekusi?**
   - A. Database mengalami kerusakan pada tabel data.
   - B. Nilai data yang dikirim identik dengan data lama di storage.
   - C. Terjadi anomali konkurensi di mana data telah dimutasi oleh transaksi lain sehingga nilai versi di database sudah berubah.
   - D. Driver database kehilangan koneksi TCP ke engine.
   *Jawaban yang benar: C* — Klausa `WHERE id = ? AND version = ?` tidak menemukan baris yang cocok karena nilai versi telah diperbarui oleh transaksi lain, menandakan terjadinya konflik konkurensi.

7. **Mengapa pengaturan `Readiness Probe` harus dialihkan ke status Unhealthy sebelum server HTTP mulai menutup koneksi yang sedang aktif (*draining*)?**
   - A. Agar orkestrator kontainer (e.g., Kubernetes) segera menghapus Pod dari daftar endpoint load balancer sebelum koneksi lama ditutup.
   - B. Untuk memicu dump file memori aplikasi secara otomatis.
   - C. Karena server HTTP akan langsung mematikan socket listener tanpa menunggu konfirmasi OS.
   - D. Agar kernel Linux membersihkan alokasi swap space lebih cepat.
   *Jawaban yang benar: A* — Memberi jeda waktu dan mengubah status readiness menjadi *unhealthy* memungkinkan layer routing (seperti Kube-Proxy/Ingress) berhenti mengarahkan traffic baru ke Pod tersebut sebelum proses pengurasan request lama dimulai.

8. **Kapan teknik Pessimistic Locking (`SELECT ... FOR UPDATE`) lebih direkomendasikan dibandingkan Optimistic Locking (OCC)?**
   - A. Saat sistem didominasi oleh operasi pembacaan data (read-heavy, 99% Read).
   - B. Saat tingkat konflik modifikasi data sangat tinggi (*high contention*) dan biaya komputasi untuk *retry* transaksi jauh lebih mahal daripada menahan antrean lock.
   - C. Saat aplikasi berjalan di lingkungan database tanpa dukungan transaksi ACID.
   - D. Saat aplikasi backend tidak memiliki akses network ke penyimpanan cache Redis.
   *Jawaban yang benar: B* — Pada skenario dengan tingkat benturan data yang sangat padat, OCC akan memicu *retry storm* berulang-ulang yang menguras CPU; dalam kasus ini, penahanan baris secara deterministik (*pessimistic lock*) jauh lebih efisien.

9. **Apa bahaya terbesar membiarkan parameter `conn_max_lifetime` bernilai 0 (tanpa batas kedaluwarsa) saat aplikasi backend terhubung ke Managed Cloud Database di balik Load Balancer?**
   - A. Menghabiskan memori RAM lokal karena koneksi diduplikasi otomatis.
   - B. Load balancer infrastruktur dapat memutus koneksi idle secara sepihak (*silent TCP termination*), menyebabkan error `broken pipe` atau `connection reset by peer` di aplikasi backend.
   - C. Aplikasi backend akan otomatis menolak koneksi baru setelah 24 jam.
   - D. Database cloud otomatis mengubah mode instance menjadi read-only.
   *Jawaban yang benar: B* — Perangkat perantara jaringan (seperti AWS NAT Gateway atau Azure Load Balancer) memiliki tabel batas waktu idle TCP; jika koneksi pool tidak pernah di-recycle, pool akan menyimpan koneksi "mati" yang sudah diputus sepihak oleh load balancer.

10. **Bagaimana format propagasi konteks pelacakan standar yang didefinisikan oleh W3C TraceContext pada header HTTP?**
    - A. `X-B3-TraceId` dan `X-B3-SpanId`.
    - B. `traceparent: {version}-{trace_id}-{parent_id/span_id}-{trace_flags}`.
    - C. `Correlation-ID: uuidv4`.
    - D. `X-Request-Context: base64_encoded_json`.
    *Jawaban yang benar: B* — Spesifikasi standar global W3C TraceContext menggunakan header `traceparent` dengan format 4 segmen: versi (misal `00`), trace ID 16-byte, parent/span ID 8-byte, dan trace flags 8-bit.

---

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario Kasus Produksi A**:
    Layanan transfer dana perbankan menerima request duplikat secara serentak (berselisih 5 milidetik) dengan `Idempotency-Key` yang identik. Pemeriksaan awal menunjukkan bahwa Redis Idempotency Engine menggunakan dua instruksi terpisah:
    1. `GET key` (mengecek apakah data sudah ada)
    2. `SET key response` (menyimpan data jika belum ada)
    
    Kedua request membaca bahwa kunci belum tersedia, sehingga keduanya tetap menjalankan pemotongan saldo di database. Modifikasi arsitektur apa yang paling tepat untuk mengatasi kerentanan ini secara permanen?
    - **Solusi Rekayasa**: Ganti dua instruksi tersebut dengan operasi atomik tunggal `SET key "PROCESSING" NX EX 60`. Argumen `NX` (*Not Exists*) menjamin bahwa Redis hanya akan mengalokasikan data untuk satu request tercepat. Request kedua yang mencoba mengeksekusi perintah yang sama akan mendapatkan kembalian `nil/false`, sehingga dapat langsung ditahan atau ditolak dengan HTTP `409 Conflict` tanpa menyentuh layer database.

12. **Skenario Kasus Produksi B**:
    Saat melakukan peluncuran versi baru (*rolling update deployment*) di lingkungan Kubernetes, grafik metrik mencatat peningkatan drastis pada error HTTP `502 Bad Gateway` selama 10 detik pertama pembaruan Pod. Kode aplikasi backend sudah mengimplementasikan penanganan sinyal OS graceful shutdown standar. Apa penyebab utama munculnya error 502 tersebut dan bagaimana cara mengatasinya?
    - **Solusi Rekayasa**: Masalah ini disebabkan oleh adanya *propagation delay* pada jaringan orkestrator: Pod menerima sinyal `SIGTERM` dan langsung menutup socket listener seketika, padahal iptables / Kube-Proxy masih dalam proses menyinkronkan pencabutan IP Pod tersebut dari pool load balancer. Akibatnya, request baru masih sempat diarahkan ke Pod yang socket-nya sudah tertutup. Solusinya adalah menambahkan *preStop lifecycle hook* pada konfigurasi pod deployment (misalnya mengeksekusi `sleep 5` sebelum runtime menerima sinyal) atau menyuntikkan jeda `time.Sleep` singkat di awal penanganan sinyal di dalam kode aplikasi sebelum mematikan listener HTTP.

13. **Skenario Kasus Produksi C**:
    Sebuah aplikasi backend monolitik yang menangani transaksi inventaris sering mengalami *database lock wait timeout exceeded*. Investigasi menunjukkan adanya transaksi besar yang mengeksekusi serangkaian proses berikut di dalam satu blok transaksi basis data:
    1. Memulai transaksi SQL (`BEGIN`)
    2. Membaca baris inventaris dengan `SELECT ... FOR UPDATE`
    3. Mengirim request HTTP ke API gateway logistik pihak ketiga untuk mendapatkan nomor resi
    4. Mengupdate database (`UPDATE`)
    5. Menyelesaikan transaksi SQL (`COMMIT`)
    
    Identifikasi anomali desain di atas dan langkah refaktorisasi wajib yang harus dilakukan.
    - **Solusi Rekayasa**: Melakukan panggilan I/O jaringan eksternal (HTTP call) di dalam blok transaksi database yang sedang menahan *exclusive lock* merupakan anti-pattern yang berbahaya (*Holding locks across network boundaries*). Jika API pihak ketiga mengalami lonjakan latensi (misal 5 detik), koneksi database dan lock baris tersebut akan tertahan selama 5 detik, menyebabkan antrean transaksi lain macet total. **Langkah Refaktorisasi**: Keluarkan pemanggilan API pihak ketiga dari blok transaksi database. Lakukan reservasi awal menggunakan skema state machine sementara (misal status: `PENDING_RESERVATION`), commit transaksi SQL lokal, lakukan HTTP call ke pihak ketiga di luar konteks transaksi, lalu jalankan transaksi SQL terpisah yang singkat untuk memperbarui status akhir menjadi `CONFIRMED`.

---

## 16. Summary

1. **Service Lifecycle & Graceful Shutdown**: Menghentikan proses backend di lingkungan produksi membutuhkan orkestrasi bertahap: tandai status kesehatan menjadi *unhealthy* untuk memutus rute trafik baru, selesaikan pemrosesan request aktif yang sedang berjalan (*draining*), dan tutup seluruh pool koneksi downstream secara berurutan guna menjaga integritas data.
2. **Database Connection Pool Optimization**: Connection pool adalah penyeimbang kapasitas antara runtime backend dan engine database. Pengaturan `MaxOpenConns`, `MaxIdleConns`, dan `ConnMaxLifetime` harus disesuaikan dengan kapasitas vCPU database serta topologi jaringan perantara guna mencegah lonjakan handshake TCP dan habisnya socket kernel OS.
3. **Optimistic Concurrency Control (OCC)**: Pada platform berskala besar dengan beban konkurensi tinggi, pencegahan anomali *Lost Updates* lebih aman ditangani melalui pola OCC berbasis kolom versi atau verifikasi status invarian daripada menahan *pessimistic locks* yang rentan memicu *deadlock*.
4. **Idempotency Strategy**: Keandalan sistem di atas jaringan yang rentan gangguan (*unreliable networks*) bergantung pada implementasi lapisan idempoten. Operasi atomik (`SET NX`) pada storage in-memory memastikan request *retry* dari client tidak memicu eksekusi logika bisnis berulang kali.
5. **Resilient System Interconnection**: Integrasi antar-layanan backend wajib dibatasi oleh *context timeout*, dilindungi mekanisme *circuit breaker*, dan menerapkan pola *retry* dengan algoritma *Exponential Backoff* plus *Full Jitter* untuk mengeliminasi fenomena *Cascading Failures* dan *Thundering Herd*.
6. **Context-Driven Observability**: Structured JSON logging yang membawa metadata konteks terdistribusi (Trace ID / W3C TraceContext) merupakan prasyarat mutlak untuk pelacakan anomali, analisis performa, dan pemeliharaan backend modern berskala enterprise.