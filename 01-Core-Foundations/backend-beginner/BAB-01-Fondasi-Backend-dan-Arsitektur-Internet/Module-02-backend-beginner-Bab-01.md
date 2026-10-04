# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Bab:** 01 (BAB-01-Fondasi-dan-Arsitektur)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Mekanisme I/O Kernel Tingkat Rendah:** Membedakan cara kerja model I/O *blocking*, *non-blocking*, *multiplexing* (`select`, `poll`, `epoll`), dan *asynchronous* (AIO/io_uring) pada sistem operasi Linux.
2. **Merancang Model Konkurensi Skala Tinggi:** Mengidentifikasi *trade-off* internal antara model *thread-per-request*, *event-loop* reaktor tunggal, dan *M:N hybrid green-threads* (Goroutine/Virtual Thread) dalam menangani C10K hingga C100K *concurrent connections*.
3. **Mengeliminasi Socket & Resource Leaks:** Mengimplementasikan siklus hidup koneksi HTTP yang tangguh, termasuk manajemen *file descriptor*, mitigasi status `TIME_WAIT`/`CLOSE_WAIT`, serta *zero-downtime graceful shutdown*.
4. **Menerapkan Layered & Clean Architecture:** Mengisolasi *business logic* murni dari protokol transport (HTTP/gRPC) dan infrastruktur basis data tanpa adanya *leaky abstractions*.
5. **Mendiagnosis Kegagalan Jaringan & Bottleneck Sistem:** Melakukan profiling performa, inspeksi sistem menggunakan perkakas observabilitas Linux (`ss`, `strace`, `lsof`), dan mendesain *connection pool* yang optimal untuk beban produksi enterprise.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Dasar Pemrograman Sistem & Backend:** Pemahaman sintaksis bahasa tingkat menengah ke atas (Go diutamakan, atau C/Rust/Node.js/Java).
- **Dasar Jaringan Komputer:** Pemahaman model OSI, TCP 3-Way Handshake, TCP 4-Way Teardown, dan struktur dasar protokol HTTP/1.1.
- **Sistem Operasi Linux:** Pemahaman dasar terkait *process*, *thread*, alokasi memori (*stack* vs *heap*), dan eksekusi instruksi via antarmuka POSIX shell.
- **CLI Tools:** Keterbiasa menggunakan terminal Linux untuk instruksi dasar seperti `curl`, `nc`, dan `top`.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Linux Kernel I/O Models & The Epoll Abstraction

Pada tingkat kernel sistem operasi Linux, operasi I/O jaringan berpusat pada abstraksi **File Descriptor (FD)**. Saat sebuah *socket* dibuka, kernel mengalokasikan integer non-negatif pada tabel deskriptor proses.

```
+-------------------------------------------------------------------+
|                        USER SPACE                                 |
|  [ Application Handler ] <---> [ Runtime / Green Thread Pool ]    |
+-------------------------------------------------------------------+
        | System Calls (read, write, epoll_wait)
        v
+-------------------------------------------------------------------+
|                        KERNEL SPACE                               |
|  [ VFS / Socket Layer ]                                           |
|         |                                                         |
|  [ TCP/IP Stack ] <---> [ Socket Rx/Tx Buffers ]                  |
|         |                                                         |
|  [ Network Device Driver (e1000e, ixgbe, etc.) ]                  |
+-------------------------------------------------------------------+
        | DMA (Direct Memory Access)
        v
+-------------------------------------------------------------------+
|                     HARDWARE (NIC)                                |
+-------------------------------------------------------------------+
```

#### Evolusi Model Penanganan I/O:
1. **Synchronous Blocking I/O:**
   Aplikasi memanggil *syscall* `read()`. Thread dipindahkan oleh scheduler dari status *Running* ke *Waiting (Sleeping)*. Terjadi dua kali *context switch* dan dua kali penyalinan data:
   - Data disalin dari NIC ke kernel buffer (via *DMA* dan *hardware interrupt*).
   - Data disalin dari kernel buffer ke user space buffer.
   - Kelemahan: Satu thread tertahan untuk satu koneksi (*1:1 Thread-to-Connection ratio*).

2. **I/O Multiplexing (`epoll`):**
   Memecahkan masalah C10K dengan memisahkan penungguan kesiapan I/O dari pembacaan data:
   - `epoll_create1(0)`: Mengalokasikan struktur data internal kernel berupa **Red-Black Tree** (untuk pencarian O(log N) pendaftaran FD) dan **Ready List** berupa Doubly Linked List (berisi FD yang siap dibaca/tulis).
   - `epoll_ctl(epfd, EPOLL_CTL_ADD, fd, &event)`: Mendaftarkan FD dengan *callback* perangkat keras.
   - `epoll_wait(epfd, events, maxevents, timeout)`: Menidurkan thread dan hanya membangunkannya jika ada item pada *Ready List*. Tidak ada iterasi O(N) linier seperti pada `select()` atau `poll()`. Kompleksitasnya adalah **O(k)** di mana $k$ adalah jumlah FD yang aktif.

```
       epoll Instance (Kernel Space)
      +-----------------------------------------+
      |        Red-Black Tree (All FDs)         |
      |                 [FD 12]                 |
      |                 /     \                 |
      |             [FD 5]   [FD 24]            |
      |                                         |
      |        Ready List (Doubly Linked)       |
      |          [FD 5] <--> [FD 24]            |
      +-----------------------------------------+
                          ^
                          | Event Notification (NIC IRQ Callback)
                          v
         Socket Buffer Ready to Read
```

### 3.2 User Space vs Kernel Space, Syscalls, & Context Switching

Setiap perpindahan dari *User Space* (Ring 3) ke *Kernel Space* (Ring 0) melalui *syscall* (`accept`, `read`, `epoll_wait`) memicu *overhead* berikut:
1. **Register Saving:** Nilai-nilai register CPU (RIP, RSP, general purpose registers) disimpan ke dalam *Kernel Stack*.
2. **TLB Flushes & Cache Thrashing:** Pergantian *page table address space* menurunkan rasio *hit* pada CPU L1/L2/L3 *caches*.
3. **Branch Target Buffer (BTB) Invalidations:** Berpotensi memicu kerentanan mitigasi spekulatif seperti Spectre/Meltdown yang menurunkan *throughput* komputasi.

Teknologi modern mengandalkan **Zero-Copy** (seperti *syscall* `sendfile(2)` atau `splice(2)`) yang mentransfer data langsung dari cache *page fault* kernel ke *socket buffer* tanpa menduplikasinya ke *user space buffer*.

### 3.3 Concurrency Architecture Models

| Metrik / Karakteristik | Thread-per-Request (e.g., Apache Prefork, Old Java) | Single-Threaded Event Loop (e.g., Node.js, Redis) | M:N Green Threads / Coroutines (e.g., Go Goroutines, Java Loom) |
| :--- | :--- | :--- | :--- |
| **Model Threading** | 1 Native Thread = 1 Request/Connection | 1 Native Thread = N Connections (Non-blocking) | M Green Threads dipetakan ke N Native Threads |
| **Beban Memori Dasar** | ~1MB - 8MB per thread stack | Ringan (~beberapa KB per event loop context) | ~2KB - 4KB per goroutine stack (dynamically resized) |
| **Overhead Context Switch** | Sangat Tinggi (Kernel context switch, Ring 3 -> Ring 0) | Minimum (Tetap di user space, cooperative) | Sangat Rendah (Runtime user space scheduler switch) |
| **Pemanfaatan Multi-Core** | Otomatis via OS Kernel Scheduler | Buruk secara native (Memerlukan *Worker Processes*) | Sangat Optimal (Work-stealing scheduler melintasi semua core) |
| **Bottleneck Utama** | Kehabisan memori & thrashing scheduler pada load tinggi | Blocking operations pada CPU-bound code memblokir loop | Overhead GC & channel contention bila desentralisasi buruk |

### 3.4 Deep Protocol State Machine: Socket Lifecycle & HTTP/1.1 vs HTTP/2

Koneksi TCP bergerak melalui serangkaian *state machine* yang diatur oleh RFC 793:

```
CLIENT                                          SERVER
  |                                               |
  |--- SYN (Seq=x) ------------------------------>| LISTEN
  |                                               |  v (accept queue)
  |<-- SYN-ACK (Seq=y, Ack=x+1) ------------------| SYN-RECEIVED
  |                                               |
  |--- ACK (Seq=x+1, Ack=y+1) ------------------->| ESTABLISHED
  |                                               |
  |           [ DATA TRANSFER PHASE ]             |
  |                                               |
  |--- FIN (Seq=u) ------------------------------>|
  |<-- ACK (Ack=u+1) -----------------------------| CLOSE_WAIT
  |                                               | (Server app cleans up)
  |                                               |<-- Calls close()
  |<-- FIN (Seq=v) -------------------------------| LAST_ACK
  |--- ACK (Ack=v+1) ---------------------------->|
  | TIME_WAIT (2MSL = ~60s)                       | CLOSED
  v                                               v
CLOSED
```

- **TIME_WAIT (Client/Active Closer):** Mencegah paket lambat (*delayed/duplicated segments*) dari koneksi lama mengorup koneksi baru yang memakai kuartet tuple IP/Port yang sama, serta memastikan pihak seberang menerima ACK atas FIN terakhirnya.
- **CLOSE_WAIT (Passive Closer):** Menunjukkan bahwa kernel telah menerima FIN dari *remote party*, tetapi aplikasi lokal belum menutup socket via `close()`. Akumulasi *socket* dalam status `CLOSE_WAIT` **100% merupakan bug pada aplikasi backend** (contoh: *unclosed HTTP request/response stream*).

---

## 4. Why & What

### Mengapa Pendekatan Naif Gagal di Produksi?
Aplikasi backend yang dibangun tanpa memperhitungkan aspek sistem sering menggunakan pengaturan *default* bawaan framework:
- Mengabaikan batas *timeouts*: Menyebabkan thread/goroutine tertahan selamanya saat klien atau layanan upstream mengalami *hang* (*Silent Degradation*).
- Ketiadaan *Backpressure*: Server menerima seluruh request tanpa batas antrean hingga kehabisan memori (*OOM-Kill*).
- Model arsitektur monolitik tanpa isolasi (*Spaghetti Code*): Menyatukan *business logic* dengan *driver SQL* dan framework HTTP menyebabkan sistem rapuh, sulit diuji tanpa *mocking* berat, serta menyulitkan transisi antar protokol (misal: HTTP ke gRPC/Event-driven).

### Apa Solusinya?
1. **Penggunaan I/O Non-Blocking & Asinkron:** Runtime mengelola abstraksi `epoll` sehingga satu thread OS dapat memproses puluhan ribu koneksi terbuka.
2. **Defensive Connection Configuration:** Konfigurasi eksplisit untuk `ReadTimeout`, `ReadHeaderTimeout`, `WriteTimeout`, `IdleTimeout`, dan `MaxHeaderBytes`.
3. **Decoupled Layered Architecture (Clean Architecture):** Memisahkan sistem menjadi 4 lapisan berbatas tegas:
   - **Domain Entity Layer:** Objek data dan aturan bisnis fundamental (agnostik terhadap database/web framework).
   - **Use Case / Service Layer:** Orkestrasi alur kerja sistem.
   - **Repository / Infrastructure Layer:** Komunikasi basis data, HTTP client eksternal, atau message broker.
   - **Delivery / Transport Layer:** REST Controllers, gRPC Handlers, Middleware, dan CLI Entrypoints.

---

## 5. How (Workflow Detail)

Alur eksekusi request tingkat rendah dari antarmuka jaringan hingga ke layer domain:

```
[ NIC Ring Buffer ]
       |
       v (Hardware Interrupt / DMA)
[ OS Kernel Network Stack ] -> Socket Buffer (ESTABLISHED)
       |
       v (epoll_wait wakes up)
[ Go Netpoller / Runtime Scheduler ]
       |
       v (Spawns / Assigns Goroutine M:N)
[ Transport Middleware: Timeout & Panic Recovery ]
       |
       v
[ Routing / Transport Layer: Unmarshal HTTP JSON -> DTO ]
       |
       v
[ Domain / Service Layer: Business Validation & Transaction ]
       |
       v
[ Infrastructure Layer: Connection Pool -> Database / Cache ]
       |
       v
[ Transport Serialization & HTTP 200 OK Flush to Client ]
```

1. **Ingress:** Paket TCP tiba di Network Interface Card (NIC), ditransfer ke kernel memory via *Direct Memory Access* (DMA).
2. **Kernel Eventing:** Kernel mengirimkan *soft interrupt* (ksoftirqd), menyusun kembali segmen TCP, dan memicu *event* siap-baca pada instans `epoll`.
3. **Runtime Dispatch:** Go *netpoller* (atau Node.js *libuv*) mendeteksi ketersediaan data, lalu menjadwalkan unit eksekusi (Goroutine) untuk mengeksekusi operasi baca (`read`) tanpa memblokir thread OS fisik.
4. **Pipeline Processing:** Request melewati *chain middleware* (Panic Recovery, Request ID Tracing, Rate Limiter, Context Deadline).
5. **Decoupled Execution:** Handler memvalidasi *request payload*, mengonversinya menjadi *Domain Entity*, lalu mengeksekusi logika bisnis murni di level *Service*.
6. **Persistence via Connection Pool:** Service memanggil *Repository* yang meminjam koneksi TCP yang telah terotentikasi dari *Connection Pool* database, mengeksekusi kueri, dan mengembalikan koneksi tersebut ke *pool*.
7. **Egress:** Response diserialisasi, dialirkan kembali ke kernel socket buffer, dan dikirimkan kembali ke klien.

---

## 6. Analogy & Diagram ASCII

### Analogi Restoran Cepat Saji Skala Enterprise

- **Blocking Thread-per-Request (Restoran Tradisional dengan Pelayan Privat):**
  Setiap pelanggan yang masuk mendapatkan satu pelayan khusus yang mendampingi sejak pelanggan duduk, melihat menu (menunggu I/O), memasak di dapur, hingga selesai makan. Jika ada 1.000 pelanggan masuk bersamaan, restoran memerlukan 1.000 pelayan. Restoran akan kolaps karena ruang gerak habis (kehabisan memori) dan pelayan saling bertabrakan (*context switching*).

- **Non-blocking Event-Driven Multiplexing (`epoll` - Kafe Modern Sistem Buzzer):**
  Satu kasir menerima pesanan pelanggan, memberikan struk nomor (Buzzer/FD token), lalu langsung melayani pelanggan berikutnya. Pesanan dikirim ke dapur. Ketika makanan siap, *buzzer bergetar* (kernel memicu interrupt/epoll event). Kasir (atau pelayan yang senggang) menyerahkan pesanan kepada pelanggan yang buzzernya bergetar. Skalabilitas tercapai dengan jumlah staf yang minimal.

### Diagram Arsitektur Komponen Internal

```
+-------------------------------------------------------------------------------+
|                             DELIVERY LAYER (Transport)                        |
|  [HTTP Router / Chi / Gin]  [Request Validation]  [Context Timeout Handler]   |
+---------------------------------------+---------------------------------------+
                                        | (Calls via Service Interface)
                                        v
+-------------------------------------------------------------------------------+
|                              SERVICE LAYER (Use Cases)                        |
|         [Order Creation Engine]                 [Payment Processing Workflow] |
|   - Depends strictly on Domain Entities         - Agnostic of HTTP / SQL      |
+---------------------------------------+---------------------------------------+
                                        | (Calls via Repository Interface)
                                        v
+-------------------------------------------------------------------------------+
|                         REPOSITORY LAYER (Infrastructure)                     |
|  [Postgres Implementation]       [Redis Cache Engine]    [Third-party Client] |
|  - Uses pgxpool (Conn Pool)      - Redigo / go-redis     - Hardened HTTP Clt  |
+-------------------------------------------------------------------------------+
                                        |
                                        v
                     [ Physical Infrastructure: PostgreSQL, Redis ]
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example (Anti-Pattern: Naive HTTP Server)

Berikut adalah contoh anti-pattern yang sering ditemukan di produksi:
- Menggunakan `http.ListenAndServe` secara langsung (tidak memiliki timeout, rentan terhadap serangan *Slowloris*).
- Response body tidak ditutup (`body leak`).
- Menggunakan `http.DefaultClient` tanpa timeout.

```go
// ANTI-PATTERN: JANGAN GUNAKAN DI LINGKUNGAN PRODUKSI
package main

import (
	"io"
	"net/http"
)

func naiveHandler(w http.ResponseWriter, r *http.Request) {
	// Menggunakan DefaultClient tanpa timeout: Rentan hanging selamanya
	resp, err := http.Get("https://httpbin.org/delay/60")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	// LUPA: resp.Body.Close() -> Membocorkan File Descriptor & Memory Buffer!

	body, _ := io.ReadAll(resp.Body)
	w.Write(body)
}

func main() {
	http.HandleFunc("/naive", naiveHandler)
	// ListenAndServe tanpa Server struct: Zero timeout protection
	http.ListenAndServe(":8080", nil)
}
```

### 7.2 Practical Example (Production-Ready Architecture)

Implementasi enterprise di bawah ini mematuhi standar ketat:
- **Clean Architectural Separation:** Handler $\rightarrow$ Service Interface $\rightarrow$ Repository Interface.
- **Hardened HTTP Server:** Konfigurasi batas timeout jaringan lengkap.
- **Graceful Shutdown:** Menangkap sinyal OS (`SIGINT`, `SIGTERM`) untuk menyelesaikan *in-flight requests*.
- **Structured Database Connection Pooling:** Konfigurasi *pool* terisolasi.

#### Struktur Direktori:
```text
.
├── cmd
│   └── api
│       └── main.go
└── internal
    ├── domain
    │   └── user.go
    ├── repository
    │   └── memory_user_repo.go
    ├── service
    │   └── user_service.go
    └── transport
        └── http_handler.go
```

#### File: `internal/domain/user.go`
```go
package domain

import (
	"context"
	"errors"
	"time"
)

var (
	ErrUserNotFound      = errors.New("user not found")
	ErrInvalidUserData   = errors.New("invalid user data payload")
	ErrExecutionTimedOut = errors.New("operation execution timed out")
)

type User struct {
	ID        string    `json:"id"`
	Email     string    `json:"email"`
	Name      string    `json:"name"`
	CreatedAt time.Time `json:"created_at"`
}

type UserRepository interface {
	GetByID(ctx context.Context, id string) (*User, error)
	Create(ctx context.Context, user *User) error
}

type UserService interface {
	FetchUserProfile(ctx context.Context, id string) (*User, error)
	RegisterUser(ctx context.Context, id, email, name string) (*User, error)
}
```

#### File: `internal/repository/memory_user_repo.go`
```go
package repository

import (
	"context"
	"sync"

	"module02/internal/domain"
)

type InMemoryUserRepository struct {
	mu    sync.RWMutex
	store map[string]*domain.User
}

func NewInMemoryUserRepository() *InMemoryUserRepository {
	return &InMemoryUserRepository{
		store: make(map[string]*domain.User),
	}
}

func (r *InMemoryUserRepository) GetByID(ctx context.Context, id string) (*domain.User, error) {
	// Menghormati pembatalan context upstream
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	default:
	}

	r.mu.RLock()
	defer r.mu.RUnlock()

	user, exists := r.store[id]
	if !exists {
		return nil, domain.ErrUserNotFound
	}
	return user, nil
}

func (r *InMemoryUserRepository) Create(ctx context.Context, user *domain.User) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	default:
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	r.store[user.ID] = user
	return nil
}
```

#### File: `internal/service/user_service.go`
```go
package service

import (
	"context"
	"strings"
	"time"

	"module02/internal/domain"
)

type userServiceImpl struct {
	repo domain.UserRepository
}

func NewUserService(repo domain.UserRepository) domain.UserService {
	return &userServiceImpl{repo: repo}
}

func (s *userServiceImpl) FetchUserProfile(ctx context.Context, id string) (*domain.User, error) {
	if strings.TrimSpace(id) == "" {
		return nil, domain.ErrInvalidUserData
	}
	return s.repo.GetByID(ctx, id)
}

func (s *userServiceImpl) RegisterUser(ctx context.Context, id, email, name string) (*domain.User, error) {
	if id == "" || !strings.Contains(email, "@") || strings.TrimSpace(name) == "" {
		return nil, domain.ErrInvalidUserData
	}

	user := &domain.User{
		ID:        id,
		Email:     email,
		Name:      name,
		CreatedAt: time.Now().UTC(),
	}

	if err := s.repo.Create(ctx, user); err != nil {
		return nil, err
	}

	return user, nil
}
```

#### File: `internal/transport/http_handler.go`
```go
package transport

import (
	"encoding/json"
	"errors"
	"net/http"

	"module02/internal/domain"
)

type UserHTTPHandler struct {
	service domain.UserService
}

func NewUserHTTPHandler(svc domain.UserService) *UserHTTPHandler {
	return &UserHTTPHandler{service: svc}
}

type CreateUserRequest struct {
	ID    string `json:"id"`
	Email string `json:"email"`
	Name  string `json:"name"`
}

func (h *UserHTTPHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	switch {
	case r.Method == http.MethodGet && stringsHasPrefix(r.URL.Path, "/users/"):
		h.handleGetByID(w, r)
	case r.Method == http.MethodPost && r.URL.Path == "/users":
		h.handleCreate(w, r)
	default:
		w.WriteHeader(http.StatusNotFound)
	}
}

func (h *UserHTTPHandler) handleGetByID(w http.ResponseWriter, r *http.Request) {
	id := r.URL.Path[len("/users/"):]
	if id == "" {
		http.Error(w, `{"error":"missing user id"}`, http.StatusBadRequest)
		return
	}

	// Teruskan Request Context (membawa timeout dan sinyal pembatalan)
	user, err := h.service.FetchUserProfile(r.Context(), id)
	if err != nil {
		if errors.Is(err, domain.ErrUserNotFound) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusNotFound)
			w.Write([]byte(`{"error":"user not found"}`))
			return
		}
		http.Error(w, `{"error":"internal server error"}`, http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(user)
}

func (h *UserHTTPHandler) handleCreate(w http.ResponseWriter, r *http.Request) {
	var req CreateUserRequest
	// Mencegah denial of service via payload berukuran gigantis
	r.Body = http.MaxBytesReader(w, r.Body, 1048576) // Batas 1MB

	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&req); err != nil {
		http.Error(w, `{"error":"malformed payload"}`, http.StatusBadRequest)
		return
	}

	user, err := h.service.RegisterUser(r.Context(), req.ID, req.Email, req.Name)
	if err != nil {
		if errors.Is(err, domain.ErrInvalidUserData) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"error":"invalid validation rules"}`))
			return
		}
		http.Error(w, `{"error":"internal server error"}`, http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(user)
}

func stringsHasPrefix(s, prefix string) bool {
	return len(s) >= len(prefix) && s[0:len(prefix)] == prefix
}
```

#### File: `cmd/api/main.go`
```go
package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"module02/internal/repository"
	"module02/internal/service"
	"module02/internal/transport"
)

func main() {
	// 1. Inisialisasi Lapisan Dependensi (Dependency Injection)
	userRepo := repository.NewInMemoryUserRepository()
	userSvc := service.NewUserService(userRepo)
	userHandler := transport.NewUserHTTPHandler(userSvc)

	mux := http.NewServeMux()
	mux.Handle("/users", userHandler)
	mux.Handle("/users/", userHandler)

	// 2. Hardened Production HTTP Server Configuration
	srv := &http.Server{
		Addr:              ":8080",
		Handler:           mux,
		ReadHeaderTimeout: 2 * time.Second,  // Melindungi terhadap serangan Slowloris
		ReadTimeout:       5 * time.Second,  // Waktu maks membaca seluruh request
		WriteTimeout:      10 * time.Second, // Waktu maks menulis response
		IdleTimeout:       120 * time.Second,// Waktu simpan koneksi keep-alive
		MaxHeaderBytes:    1 << 20,          // 1 MB batas header
	}

	// 3. Menjalankan Server di Goroutine Terpisah
	serverErrors := make(chan error, 1)
	go func() {
		log.Printf("INFO: Server produksi beroperasi pada port %s", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			serverErrors <- err
		}
	}()

	// 4. Konfigurasi Graceful Shutdown
	// Menangkap sinyal interupsi sistem operasi
	shutdownSig := make(chan os.Signal, 1)
	signal.Notify(shutdownSig, os.Interrupt, syscall.SIGTERM)

	select {
	case err := <-serverErrors:
		log.Fatalf("FATAL: Kegagalan inisialisasi server: %v", err)

	case sig := <-shutdownSig:
		log.Printf("WARN: Sinyal terminasi diterima: %v. Memulai proses graceful shutdown...", sig)

		// Berikan batas waktu penyelesaian in-flight requests (Drain Period)
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()

		// Server.Shutdown menghentikan listener baru, menutup koneksi idle,
		// dan menunggu koneksi aktif selesai diproses
		if err := srv.Shutdown(ctx); err != nil {
			log.Printf("ERROR: Shutdown paksa dipicu akibat timeout: %v", err)
			if closeErr := srv.Close(); closeErr != nil {
				log.Fatalf("FATAL: Gagal menutup server secara paksa: %v", closeErr)
			}
		}
		log.Println("INFO: Server berhasil ditutup secara bersih tanpa data loss.")
	}
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Insiden Exhaustion Socket & Pool Starvation pada Event Flash Sale
- **Skala:** 40 node backend microservices (Go-based) melayani ~25.000 Request Per Second (RPS) pada puncak flash sale platform e-commerce.
- **Gejala:** 
  1. Tingkat kegagalan sistem (*HTTP 502 Bad Gateway*) melonjak drastis hingga 42% di Application Load Balancer (ALB).
  2. Latensi p99 meningkat tajam dari 45ms menjadi 12.000ms.
  3. Penggunaan CPU aplikasi tetap berada di bawah 25%, namun node tidak dapat merespons request baru.

### Investigasi Mendalam (Root Cause Analysis - RCA):
Menggunakan instrumentasi Linux pada server produksi:
```bash
# 1. Analisis status koneksi TCP aktif
$ ss -s
Total: 65420
TCP:   64300 (estab 1200, closed 62000, orphaned 120, timewait 61500)

# 2. Cek akumulasi socket TIME_WAIT
$ netstat -nat | awk '{print $6}' | sort | uniq -c | sort -n
      1 LISTEN
   1200 ESTABLISHED
  61500 TIME_WAIT
```

**Temuan 1: Socket Exhaustion Akibat HTTP Client Default**
Ditemukan kode integrasi pembayaran pihak ketiga yang membuat instance `http.Client{}` baru di setiap fungsi request tanpa menggunakan *shared transport*. Akibatnya, backend melakukan handshake baru untuk setiap request ke payment gateway dan menutup koneksinya secara aktif (`Active Close`). Ini menyebabkan *ephemeral ports* (rentang default: 32768–60999 = 28.231 port) habis terikat dalam status `TIME_WAIT` (selama $2 \times MSL = 60 \text{ detik}$). Ketika port habis, kernel melempar error: `dial tcp: bind: cannot assign requested address`.

**Temuan 2: Database Connection Pool Starvation**
Konfigurasi database connection pool diatur secara serampangan:
`SetMaxOpenConns(500)` per pod.
Dengan 40 pod, backend menuntut hingga $40 \times 500 = 20.000$ koneksi ke PostgreSQL primer. Akibatnya, PostgreSQL mengalami lonjakan *context-switching* pada process worker backend-nya, memicu penguncian (*lock contention*) pada tabel transaksi utama dan membuat seluruh pool backend kehabisan worker yang tersedia.

### Solusi & Remediasi Produksi:
1. **Singleton HTTP Transport dengan HTTP Keep-Alive:**
   ```go
   var PaymentHTTPClient = &http.Client{
       Transport: &http.Transport{
           Proxy: http.ProxyFromEnvironment,
           DialContext: (&net.Dialer{
               Timeout:   3 * time.Second,
               KeepAlive: 30 * time.Second,
           }).DialContext,
           MaxIdleConns:        1000,
           MaxIdleConnsPerHost: 200,
           IdleConnTimeout:     90 * time.Second,
       },
       Timeout: 5 * time.Second,
   }
   ```
2. **Kalkulasi & Restrukturisasi Ukuran Database Connection Pool:**
   Menerapkan rumus koneksi berbasis hardware database:
   $$\text{Max Connections} = (\text{Core Count} \times 2) + \text{Spindle Effective Count}$$
   PostgreSQL 32-core diatur menerima maksimal 2.000 koneksi via *PgBouncer*. Konfigurasi di sisi Go diubah:
   - `SetMaxOpenConns(25)` per node ($25 \times 40 = 1.000$ total koneksi teralokasi, menyisakan margin aman).
   - `SetMaxIdleConns(25)` untuk mencegah koneksi berulang kali dibuka-tutup.
   - `SetConnMaxLifetime(15 * time.Minute)`.
3. **Penyetelan Kernel Linux (`/etc/sysctl.conf`):**
   ```ini
   # Mengizinkan reuse socket TIME_WAIT untuk koneksi keluar yang aman
   net.ipv4.tcp_tw_reuse = 1
   # Memperluas range ephemeral port
   net.ipv4.ip_local_port_range = 10240 65535
   # Memperbesar ukuran antrean SYN backlog
   net.core.somaxconn = 4096
   ```

### Hasil:
- Tingkat kegagalan turun ke 0.001%.
- Latensi p99 stabil pada 38ms di bawah beban 28.000 RPS.
- Jumlah koneksi `TIME_WAIT` ditekan di bawah 2.000 koneksi konstan.

---

## 9. Trade-offs

| Pendekatan / Komponen | Pilihan A | Pilihan B | Trade-off & Dampak Performa |
| :--- | :--- | :--- | :--- |
| **Model Eksekusi Transaksi Database** | **Direct DB Connection** | **Dedicated Connection Pooler (misal: PgBouncer)** | Direct Connection memiliki latensi nol untuk overhead proxy, namun membatasi skalabilitas horizontal service Pods (PostgreSQL menderita jika $N > 1000$ koneksi). PgBouncer mengonsumsi memory proxy ekstra dan menambah latensi jaringan (~0.5ms), tetapi memungkinkan puluhan ribu Pod terhubung secara multiplexing. |
| **Pola Arsitektur Kode** | **Layered / Clean Architecture** | **Flat / Pragmatic Single-Package Architecture** | Clean Architecture meningkatkan redundansi penulisan struct (DTO, Domain, Entity) dan overhead *interface dynamic dispatch*, namun menjamin *unit testability* tinggi dan zero leaking domain logic. Flat Architecture sangat cepat untuk *Time-To-Market* prototipe, tetapi biaya *refactoring* melonjak eksponensial setelah basis kode melebihi 20.000 baris kode. |
| **Komunikasi Jaringan Antar-Service** | **JSON over HTTP/1.1** | **Protobuf over gRPC (HTTP/2 Multiplexing)** | JSON sangat mudah dibaca manusia (*human-readable*) dan didukung peramban secara universal, namun boros serialisasi CPU dan bandwidth (teks mentah). Protobuf/gRPC memangkas latency hingga 60% dan menghemat CPU via binary framing, tetapi memerlukan *schema compilation* kaku dan konfigurasi L7 Load Balancer yang lebih kompleks. |
| **Alokasi Memori** | **Stack Allocation (Pass-by-value)** | **Heap Allocation (Pass-by-pointer)** | Pass-by-value mengeliminasi tekanan pada Garbage Collector (GC) karena alokasi dibersihkan otomatis saat stack frame ditutup, namun boros penyalinan memori jika struct berukuran besar. Pass-by-pointer efisien untuk data besar, tetapi memaksa compiler melakukan *escape analysis* ke Heap, yang dapat memicu *Stop-The-World (STW)* GC pause pada throughput ekstrem. |

---

## 10. Common Mistakes & Troubleshooting

### 1. The Undrained/Unclosed HTTP Response Body Leak
- **Kesalahan Fatal:** Mengabaikan `resp.Body.Close()` atau membaca data tanpa mengonsumsi seluruh stream respons.
- **Dampak:** Koneksi TCP underlying tidak dapat digunakan kembali (*cannot be reused in keep-alive pool*). Sistem operasi mempertahankan File Descriptor terbuka hingga mencapai batas limit `ulimit -n`, memicu error `too many open files`.
- **Solusi Benar:**
  ```go
  resp, err := client.Do(req)
  if err != nil {
      return err
  }
  // Selalu defer Close secara tepat setelah cek error nil
  defer resp.Body.Close()

  // Jika payload tidak dibutuhkan seutuhnya, discard untuk reuse connection:
  _, _ = io.Copy(io.Discard, resp.Body)
  ```

### 2. The Goroutine Leak via Unbuffered Channels & Dead Contexts
- **Kesalahan Fatal:** Membuka goroutine baru yang memblokir penulisan ke *unbuffered channel* tanpa mekanisme pembatalan (*cancellation listener*).
- **Dampak:** Jumlah goroutine naik linier tanpa batas (*leak*), memicu pembengkakan konsumsi memori heap dan degradasi performa scheduler.
- **Deteksi:**
  ```bash
  # Menggunakan profiling endpoint internal runtime
  curl -s http://localhost:6060/debug/pprof/goroutine?debug=1 | head -n 20
  ```

### 3. Panduan Sistematis Troubleshooting Jaringan & Sistem Linux

```
Gejala: API Mulai Melempar Timeout / Error 504
  |
  +---> [Langkah 1: Periksa Limit Socket & File Descriptor]
  |     Jalankan: lsof -p <PID> | wc -l
  |     Bandingkan dengan: ulimit -n
  |     Jika mendekati batas: Indikasi kebocoran File Descriptor.
  |
  +---> [Langkah 2: Periksa Distribusi Status TCP]
  |     Jalankan: ss -tan '( dport = :8080 or sport = :8080 )'
  |     Banyak CLOSE_WAIT? -> Bug kode aplikasi backend tidak menutup socket.
  |     Banyak TIME_WAIT?  -> Klien atau server melakukan active closure tanpa keep-alive.
  |
  +---> [Langkah 3: Periksa Syscall Latency & Blockage]
  |     Jalankan: strace -c -p <PID>
  |     Amati panggilan sistem dengan waktu tunggu kumulatif tertinggi (misal: futex, epoll_wait).
  |
  +---> [Langkah 4: Periksa CPU / Goroutine Profile]
        Jalankan: go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30
        Identifikasi function hotspot yang menyebabkan lock contention atau spin-locking.
```

---

## 11. Best Practices (Production Checklist)

Gunakan tabel checklist evaluasi ini sebelum mempromosikan kode ke tahap staging/produksi:

| Domain | Item Checklist | Status Verifikasi |
| :--- | :--- | :--- |
| **Networking** | Server tidak menggunakan `http.DefaultServeMux` atau `http.ListenAndServe` telanjang. | [ ] Diverifikasi |
| **Networking** | `ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout`, dan `IdleTimeout` dikonfigurasi eksplisit. | [ ] Diverifikasi |
| **Resource Limits** | Request payload dibatasi menggunakan `http.MaxBytesReader` untuk mencegah serangan Denial-of-Service OOM. | [ ] Diverifikasi |
| **Clean Lifecycle**| Aplikasi mengimplementasikan `Graceful Shutdown` yang memutus sinyal OS dengan batas waktu *drain* (maks 15-30 detik). | [ ] Diverifikasi |
| **Client Resiliency**| Seluruh pemanggilan downstream HTTP Client memiliki batas `Timeout` yang lebih rendah dari timeout parent handler. | [ ] Diverifikasi |
| **Database Pool** | `MaxOpenConns`, `MaxIdleConns`, dan `ConnMaxLifetime` dihitung berdasarkan daya tampung hardware DB dan batasan node horizontal. | [ ] Diverifikasi |
| **Architecture** | Domain layer sama sekali tidak mengimpor package transport HTTP (misal: `net/http`) atau library database eksternal (SQL driver). | [ ] Diverifikasi |
| **Observability** | Context propagation (`ctx`) diteruskan di setiap pemanggilan I/O antar-lapisan (Handler $\rightarrow$ Service $\rightarrow$ Repo). | [ ] Diverifikasi |

---

## 12. Hands-on Practice

Buatlah sistem HTTP API tangguh dengan batas proteksi produksi dalam direktori `hands-on/m02/`.

### Langkah 1: Inisialisasi Proyek
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init enterprise-core
```

### Langkah 2: Buat Implementasi Kode Server Produksi
Tuliskan kode berikut ke dalam file `hands-on/m02/server.go`:

```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

type HealthResponse struct {
	Status    string    `json:"status"`
	Timestamp time.Time `json:"timestamp"`
	WorkerID  int       `json:"worker_id"`
}

func hardenedHandler(w http.ResponseWriter, r *http.Request) {
	// Mensimulasikan pemrosesan beban kerja
	processDuration := time.Duration(50+rand.Intn(100)) * time.Millisecond
	
	select {
	case <-time.After(processDuration):
		// Pemrosesan selesai normal
	case <-r.Context().Done():
		// Klien memutus koneksi sebelum selesai diproses
		log.Printf("WARN: Permintaan dibatalkan oleh klien: %v", r.Context().Err())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(HealthResponse{
		Status:    "HEALTHY_OPERATIONAL",
		Timestamp: time.Now().UTC(),
		WorkerID:  os.Getpid(),
	})
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/health", hardenedHandler)

	server := &http.Server{
		Addr:              ":9090",
		Handler:           mux,
		ReadHeaderTimeout: 1 * time.Second,
		ReadTimeout:       3 * time.Second,
		WriteTimeout:      5 * time.Second,
		IdleTimeout:       30 * time.Second,
	}

	idleConnsClosed := make(chan struct{})
	go func() {
		sigint := make(chan os.Signal, 1)
		signal.Notify(sigint, os.Interrupt, syscall.SIGTERM)
		<-sigint

		log.Println("INFO: Menerima sinyal terminasi. Menghentikan server...")
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		if err := server.Shutdown(shutdownCtx); err != nil {
			log.Printf("ERROR: HTTP server Shutdown failed: %v", err)
		}
		close(idleConnsClosed)
	}()

	log.Printf("INFO: Server berjalan di http://localhost%s", server.Addr)
	if err := server.ListenAndServe(); err != http.ErrServerClosed {
		log.Fatalf("FATAL: HTTP server ListenAndServe: %v", err)
	}

	<-idleConnsClosed
	log.Println("INFO: Server berhasil ditutup secara terkontrol.")
}
```

### Langkah 3: Eksekusi Beban Uji & Simulasi Terminasi
Buka Terminal 1 dan jalankan aplikasi:
```bash
go run server.go
```

Buka Terminal 2 dan lakukan simulasi load testing menggunakan tool benchmarking (misal: `hey` atau `wrk`):
```bash
# Instalasi hey jika belum terpasang: go install github.com/rakyll/hey@latest
hey -n 10000 -c 100 http://localhost:9090/api/v1/health
```

Saat *load test* sedang berjalan di Terminal 2, kirimkan sinyal SIGTERM ke proses di Terminal 1:
```bash
# Cari PID dan kirim SIGTERM
kill -SIGTERM $(pgrep -f "server.go")
```

**Evaluasi:** Amati bahwa tidak ada request yang menghasilkan respons *dropped connection* atau *connection refused*. Server akan menolak koneksi TCP baru, menuntaskan 100 koneksi yang sedang berjalan dalam batas drain timeout 10 detik, lalu keluar dengan status `exit code 0`.

---

## 13. Exercise

### Level Easy
**Tugas:** Tuliskan sebuah custom middleware HTTP `TimeoutMiddleware(timeout time.Duration)` di Go yang memanfaatkan `context.WithTimeout`. Jika eksekusi handler melewati durasi yang ditentukan, batalkan *context chain* downstream dan berikan respons HTTP `504 Gateway Timeout` dalam format JSON.
- **Kriteria Validasi:** Handler simulasi yang memanggil `time.Sleep(2 * time.Second)` harus otomatis diputus jika middleware memiliki konfigurasi timeout `500 * time.Millisecond`.

### Level Medium
**Tugas:** Buat representasi arsitektur bersih (*Clean Architecture*) sederhana untuk fitur transfer saldo:
1. `Account` entity pada layer domain.
2. `AccountRepository` interface dengan fungsi `GetBalance` dan `UpdateBalance`.
3. `TransferService` yang menjamin eksekusi transfer bersifat atomik. Jika saldo tidak cukup, kembalikan domain error `ErrInsufficientFunds`.
- **Kriteria Validasi:** Unit test harus memverifikasi service logic secara 100% menggunakan *mock repository* murni berbasis memory tanpa melibatkan driver database SQL atau server HTTP.

### Level Hard
**Tugas:** Rancang sebuah worker pool konkuren berbasis Goroutine yang membaca tasks dari buffered channel dengan mekanisme **Adaptive Dynamic Throttling**:
1. Menampung kapasitas maksimum $N$ goroutines.
2. Mengukur latensi rata-rata p95 pemrosesan tugas secara real-time.
3. Jika latensi p95 naik melebihi ambang batas 200ms, turunkan jumlah pemrosesan *concurrency* secara dinamis untuk memberi ruang bernapas pada downstream resource.
- **Kriteria Validasi:** Buat simulasi di mana downstream latensi meningkat buatan, amati penurunan *throughput concurrency* otomatis pada log metrik, dan pastikan tidak terjadi *race condition* (`go run -race`).

---

## 14. Challenge

### Studi Kasus: The Cascading Death-Spiral & The CLOSE_WAIT Avalanche

**Konteks Insiden:**
Sebuah platform perbankan digital berskala besar mengalami down total selama *peak hour*. Tim SRE melaporkan bahwa ketika satu microservice internal (*Core Ledger Service*) melambat akibat penguncian row database, microservice gerbang utama (*API Gateway*) mulai mengalami kegagalan beruntun.

**Hasil Observasi Diagnostik:**
1. CPU API Gateway melonjak ke 100%.
2. Nilai metrik sistem mencatat lonjakan socket pada status `CLOSE_WAIT` hingga menyentuh batas OS file descriptor limit (`1.048.576`).
3. Load Balancer upstream mencatat ratusan ribu error *HTTP 502/504*.
4. Ketika service API Gateway di-*restart*, sistem langsung kolaps kembali dalam rentang waktu 30 detik (Death Spiral).

**Tantangan Anda:**
1. **Analisis Akar Masalah Arsitektur:** Deskripsikan secara mendalam bagaimana kelambatan di satu service hilir (*downstream*) dapat memicu akumulasi jutaan socket status `CLOSE_WAIT` di service hulu (*upstream* API Gateway). Sertakan analisis terkait interaksi TCP State Machine dan penanganan I/O di tingkat aplikasi.
2. **Desain Solusi Rekayasa Sistem Tanpa Single Point of Failure:**
   Rancang arsitektur proteksi komprehensif yang harus diimplementasikan pada API Gateway untuk menangkal kegagalan tersebut, meliputi:
   - Pola *Circuit Breaking* & *Rate Limiting* (tuliskan spesifikasi state machine-nya).
   - Penyetelan parameter *HTTP Transport Pool* dan batas *Deadlines Context*.
   - Strategi degradasi layanan (*Graceful Degradation*) ketika Core Ledger tidak merespons dalam 200ms.
3. **Penyusunan Execution Plan & Mitigation Runbook:**
   Sajikan langkah perbaikan konkret dan runbook mitigasi teknis untuk engineer yang bertugas agar sistem terlindung secara permanen dari fenomena *cascading failure* ini di kemudian hari.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Basic Questions

1. **Apa perbedaan mendasar antara syscall `select()`/`poll()` dengan `epoll()` pada kernel Linux dalam hal kompleksitas waktu penanganan File Descriptor?**
   - **Jawaban:** `select()` dan `poll()` memiliki kompleksitas waktu $\mathcal{O}(N)$ karena keduanya harus mengiterasi keseluruhan array/set File Descriptor yang didaftarkan untuk mengetahui deskriptor mana yang siap menerima I/O. Sebaliknya, `epoll()` menggunakan arsitektur event-driven berbasis Red-Black Tree dan Ready List dengan kompleksitas $\mathcal{O}(k)$ di mana $k$ adalah jumlah File Descriptor yang secara riil aktif.

2. **Apa yang menyebabkan sebuah socket TCP berada dalam status `TIME_WAIT`, dan pihak mana yang menyandangnya?**
   - **Jawaban:** Status `TIME_WAIT` selalu dialami oleh pihak yang **secara aktif menginisiasi penutupan koneksi** (*Active Closer* yang mengirimkan segmen FIN pertama). Tujuannya adalah memastikan paket ACK terakhir benar-benar diterima oleh pihak seberang dan mencegah segmen lama yang tersesat di rute IP disalahartikan oleh koneksi baru yang memakai tuple IP/port yang identik.

3. **Mengapa penggunaan `http.DefaultClient` di Go sangat dilarang untuk arsitektur tingkat produksi?**
   - **Jawaban:** Karena `http.DefaultClient` secara struktural mendefinisikan batas timeout sebesar nol (`Timeout: 0`). Ini berarti client tidak akan pernah memutus koneksi jika upstream tidak memberikan respons, yang dapat menyebabkan akumulasi goroutine atau thread tak berbatas hingga server kehabisan memori.

4. **Dalam Clean Architecture, mengapa lapisan Domain tidak boleh memiliki dependensi ke framework web HTTP atau driver database?**
   - **Jawaban:** Untuk menjaga independensi *Core Business Logic* dari perubahan eksternal. Jika domain bergantung pada framework atau basis data, pengujian unit murni menjadi mustahil tanpa infrastruktur eksternal, dan migrasi teknologi (misal: mengganti library database atau beralih dari HTTP ke gRPC) akan merusak seluruh logika bisnis.

5. **Apa fungsi dari `http.MaxBytesReader` pada pemrosesan request body?**
   - **Jawaban:** Berfungsi membatasi kapasitas maksimum ukuran byte yang boleh dialirkan dan dibaca dari incoming request body stream, melindungi server dari serangan DoS berbasis exhaustion memory (alokasi JSON payload tak terbatas).

---

### 15.2 Intermediate Questions

1. **Bagaimana Go Runtime Network Poller menjembatani kesenjangan antara syscall I/O Linux yang non-blocking (`epoll`) dengan model pemrograman sekuensial pada Goroutine?**
   - **Jawaban:** Ketika goroutine memanggil operasi baca/tulis pada network socket, socket telah diubah ke mode non-blocking (`O_NONBLOCK`). Jika syscall mengembalikan error `EAGAIN` atau `EWOULDBLOCK`, runtime Go tidak memblokir thread sistem operasi fisik, melainkan mendaftarkan file descriptor tersebut ke Netpoller (`epoll_ctl`) dan memarkir goroutine ke status *Waiting*. Thread OS dialihkan untuk mengeksekusi goroutine lain. Ketika kernel memicu notifikasi epoll, Netpoller membangunkan goroutine terkait ke status *Runnable* untuk melanjutkan pembacaan secara sekuensial.

2. **Jelaskan perbedaan mendasar kegagalan sistem yang ditandai oleh akumulasi status `TIME_WAIT` vs status `CLOSE_WAIT` yang masif pada server backend!**
   - **Jawaban:** Akumulasi `TIME_WAIT` masif menandakan backend secara agresif memutus koneksi ke upstream/klien tanpa mekanisme connection reuse (Keep-Alive), yang berisiko menghabiskan ephemeral port. Akumulasi `CLOSE_WAIT` masif menandakan **adanya bug kebocoran resource pada kode backend**, di mana klien upstream telah menutup koneksi (mengirim FIN), kernel lokal telah merespons dengan ACK, tetapi kode aplikasi tidak pernah memanggil method `.Close()` pada socket/stream terkait.

3. **Mengapa pengaturan `db.SetMaxIdleConns(n)` harus diatur mendekati atau sama dengan `db.SetMaxOpenConns(n)` pada aplikasi backend dengan lalu lintas tinggi?**
   - **Jawaban:** Jika `MaxIdleConns` disetel jauh lebih rendah daripada `MaxOpenConns`, koneksi database yang baru saja dibuka untuk memproses beban lonjakan akan langsung dihancurkan (*killed*) saat idle sesaat. Akibatnya, pada request berikutnya, backend dipaksa melakukan *handshake* ulang TCP, pertukaran SSL/TLS, dan otentikasi database yang sangat membebani komputasi CPU dan meningkatkan latensi secara drastis.

4. **Bagaimana zero-copy melalui syscall `sendfile()` meningkatkan efisiensi transfer data statis dibanding pemanggilan berulang `read()` lalu `write()`?**
   - **Jawaban:** Pada pola `read()` diikuti `write()`, data berpindah 4 kali: NIC/Disk $\rightarrow$ Kernel Buffer $\rightarrow$ User Buffer $\rightarrow$ Kernel Socket Buffer $\rightarrow$ NIC, disertai 4 kali context switch mode OS. Dengan `sendfile()`, kernel mentransfer data langsung dari Disk Page Cache ke Socket Buffer di dalam Kernel Space (hanya 2 perpindahan via DMA dan 2 context switch), sepenuhnya memotong duplikasi data ke User Space.

5. **Apa konsekuensi teknis jika implementasi Graceful Shutdown hanya mengandalkan pemutusan listener server HTTP tanpa mengatur konteks timeout penyelesaian request in-flight?**
   - **Jawaban:** Tanpa konteks timeout (*drain deadline*), server dapat menggantung (*hung*) selamanya jika terdapat request yang terjebak dalam proses komputasi tak berujung, kebuntuan (*deadlock*), atau menunggu I/O pihak ketiga yang tidak responsif. Hal ini menghalangi orkestrator kontainer (seperti Kubernetes) menyelesaikan proses deployment secara deterministik.

---

### 15.3 Production Scenario Questions

#### Kasus 1: "The Thread-Exhaustion Outage"
Aplikasi Monolith enterprise berbasis Java Thread-per-Request mengalami crash saat kampanye broadcast notifikasi pesan promosi. Penggunaan CPU menyentuh 98%, dan error log dipenuhi oleh `java.lang.OutOfMemoryError: unable to create new native thread`. 
- **Pertanyaan Evaluasi:** Berdasarkan prinsip arsitektur yang telah dipelajari, identifikasi 2 akar masalah fundamental arsitektural dari sistem tersebut dan berikan 2 langkah remediasi jangka panjang!
- **Kriteria Evaluasi Jawaban yang Tepat:**
  - *Akar Masalah:* Beban konkurensi melampaui kemampuan OS scheduler (1 request = 1 OS thread berukuran stack ~1MB). Trashing CPU terjadi karena context switching berlebihan saat thread berstatus *runnable* melebihi jumlah core CPU fisik.
  - *Remediasi:* Beralih ke model asynchronous non-blocking I/O multiplexing (atau beralih ke Java Virtual Threads/Project Loom / Go Goroutines) dan menerapkan isolasi antrean pemrosesan via message broker (Kafka/RabbitMQ) dengan *rate limiting backpressure*.

#### Kasus 2: "The Broken Circuit Cascade"
Microservice Order memanggil Microservice Payment melalui koneksi HTTP keep-alive pool. Secara mendadak, node database Payment mengalami *failover*, menyebabkan endpoint Payment melambat dari merespons dalam 100ms menjadi 45 detik per request. Seketika itu juga, Service Order kehabisan seluruh resource memory dan memicu *CrashLoopBackOff*.
- **Pertanyaan Evaluasi:** Mengapa perlambatan di microservice Payment dapat mematikan microservice Order, padahal service Order memiliki alokasi memori yang sangat besar?
- **Kriteria Evaluasi Jawaban yang Tepat:**
  - Penjelasan harus mencakup ketiadaan *deadline propagation* (Context timeout) pada HTTP Client Service Order. Goroutine/Thread di Service Order terus diproduksi seiring datangnya traffic masuk, namun tertahan menunggu I/O Payment. Akibatnya alokasi stack per-goroutine mengonsumsi seluruh memory heap pod hingga diputus paksa oleh OS *OOM-Killer*.
  - Solusi harus menyertakan implementasi *Circuit Breaker pattern* (misal: Hystrix/Go-resilience) yang membuka sirkuit (fail-fast) saat tingkat latensi melampaui batas ambang, serta konfigurasi transport client timeout maksimal yang ketat.

#### Kasus 3: "The Unclosed Body Phantom"
Sebuah microservice proxy scraping mengumpulkan data dari ratusan portal berita. Setelah berjalan mulus selama 4 hari berturut-turut di Kubernetes cluster, pod mulai melempar pesan kegagalan `dial tcp: lookup news.example.com: device or resource busy` atau `socket: too many open files`, meskipun volume request scraping konstan dan sangat rendah (hanya 5 RPS).
- **Pertanyaan Evaluasi:** Lakukan diagnosis terhadap log tersebut dan tentukan di mana lokasi baris cacat kode dan langkah perbaikan mutlaknya!
- **Kriteria Evaluasi Jawaban yang Tepat:**
  - Indikasi jelas dari kebocoran File Descriptor akibat instansiasi pemanggilan HTTP di mana `response.Body` tidak ditutup via `defer resp.Body.Close()`, atau data di dalam `Body` tidak dibaca hingga selesai (`io.Copy(io.Discard, resp.Body)`).
  - Akibatnya socket file descriptor tetap menggantung di tabel sistem operasi Linux pod hingga menyentuh limit konfigurasi `ulimit -n` (atau limit file descriptor proses). Perbaikan mutlak mencakup penambahan pembersihan body secara deterministik dan profiling via command `lsof -p <PID>`.

---

## 16. Summary

Fondasi arsitektur backend berkinerja tinggi tidak bertumpu pada pemilihan framework web yang populer, melainkan pada pemahaman mendalam tentang **interaksi antara kode aplikasi, runtime, dan kernel sistem operasi**.

### Poin Kunci Pembelajaran:
1. **I/O Multiplexing (`epoll`):** Pondasi dari seluruh runtime backend modern berskala tinggi. Memisahkan penungguan ketersediaan jaringan dari pembacaan data, menghapuskan beban $\mathcal{O}(N)$ dari polling linier dan pemborosan memori model thread-per-request.
2. **Defensive Network Configuration:** Di lingkungan produksi, tidak ada operasi jaringan yang boleh berjalan tanpa batas waktu (*zero timeout*). Konfigurasi `ReadTimeout`, `WriteTimeout`, dan pemanfaatan `context.Context` adalah garis pertahanan pertama terhadap serangan degradasi koneksi.
3. **Socket Lifecycle Hygiene:** Memahami fase handshake dan teardown TCP mencegah terjadinya krisis socket exhaustion (`TIME_WAIT` berlebihan akibat non-reuse connections) dan file descriptor leaks (`CLOSE_WAIT` akibat unclosed response streams).
4. **Clean Decoupled Architecture:** Pemisahan fungsionalitas yang ketat (Domain $\rightarrow$ Service $\rightarrow$ Repository $\rightarrow$ Delivery) menjamin integritas logika bisnis murni, menyederhanakan automated testing tanpa overhead dependensi, serta menghasilkan sistem backend yang adaptif dan siap berkembang menuju skala enterprise.