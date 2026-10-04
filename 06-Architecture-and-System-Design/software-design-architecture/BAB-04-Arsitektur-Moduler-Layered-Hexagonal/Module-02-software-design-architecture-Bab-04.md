# BAB 04: Arsitektur Moduler, Layered, & Hexagonal
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Invarian Arsitektural**: Mengidentifikasi batas konteks (*architectural boundaries*), memisahkan *business domain invariants* dari *infrastructure concerns*, serta menihilkan kebocoran abstraksi (*leaky abstractions*).
2. **Merancang Ports and Adapters Tingkat Lanjut**: Mengonstruksi *Driving (Inbound) Ports*, *Driven (Outbound) Ports*, serta adapter konkret dengan isolasi dependensi mutlak (*zero-dependency domain core*).
3. **Mengimplementasikan Pola Dekoupling Produksi**: Menerapkan *Object Mapping Boundaries*, *Transactional Outbox Pattern* di atas *driven ports*, dan mitigasi *distributed transaction anomalies* melalui *Application Orchestration*.
4. **Mengeksekusi Strategi Pengujian Komprehensif**: Mengembangkan pengujian arsitektur otomatis (*Architecture Fitness Functions*) dan *Sociable Unit Tests* tanpa bergantung pada mock infrastruktur eksternal.
5. **Mengevaluasi Trade-offs Kinerja & Kompleksitas**: Mengukur *overhead* alokasi memori, latensi serialisasi lintas layer, dan biaya kognitif arsitektur modular berbanding lurus dengan skalabilitas sistem jangka panjang.

---

### 2. Prerequisite

Sebelum mendalami modul ini, peserta wajib menguasai:
* **Pemrograman Berorientasi Objek & Fungsional Lanjutan**: *Interface segregation*, *Polymorphism*, *First-class functions*, dan *Generics*.
* **Prinsip SOLID Tingkat Mahir**: Khususnya *Single Responsibility Principle* (SRP) pada level modul dan *Dependency Inversion Principle* (DIP).
* **Konsep Dasar Layered Architecture**: Memahami *presentation*, *business logic*, dan *data access layer*, serta keterbatasan struktural coupling-nya.
* **Dasar-dasar Domain-Driven Design (DDD)**: Konsep *Aggregate Root*, *Entity*, *Value Object*, *Domain Event*, dan *Repository Interface*.
* **Concurrency & Persistence Primitives**: Transaksi basis data (ACID, isolation levels), *connection pooling*, dan *thread-safety/goroutine safety*.

---

### 3. Concept & Internal Architecture (Mendalam)

Hexagonal Architecture (dikenal juga sebagai *Ports and Adapters Architecture*, digagas oleh Alistair Cockburn) membalikkan paradigma dependensi tradisional yang berpusat pada basis data (*database-centric architecture*).

```
+-----------------------------------------------------------------------------------+
|                              INFRASTRUCTURE LAYER                                 |
|                                                                                   |
|      +------------------------+                  +-------------------------+      |
|      |  Driving / Inbound     |                  |   Driven / Outbound     |      |
|      |  Adapters              |                  |   Adapters              |      |
|      |  (HTTP, gRPC, CLI,     |                  |   (PostgreSQL, Redis,   |      |
|      |   Kafka Consumers)     |                  |    Stripe, Kafka Pub)   |      |
|      +-----------+------------+                  +------------^------------+      |
|                  |                                            |                   |
|  ================|============================================|=================  |
|                  |           APPLICATION BOUNDARY             |                   |
|                  v                                            |                   |
|      +------------------------+                  +------------+------------+      |
|      |  Inbound Ports         |                  |  Outbound Ports         |      |
|      |  (Use Case Interfaces) |                  |  (SPI / Repositories /  |      |
|      |                        |                  |   External Clients)     |      |
|      +-----------+------------+                  +------------^------------+      |
|                  |                                            |                   |
|                  v                                            |                   |
|      +--------------------------------------------------------+------------+      |
|      |                    APPLICATION SERVICE LAYER                        |      |
|      |                    (Use Case Orchestration)                         |      |
|      +--------------------------------+------------------------------------+      |
|                                       |                                           |
|  =====================================|=========================================  |
|                                       v              DOMAIN BOUNDARY              |
|                      +---------------------------------+                          |
|                      |           DOMAIN CORE           |                          |
|                      |  - Aggregates & Entities        |                          |
|                      |  - Value Objects                |                          |
|                      |  - Pure Domain Logic            |                          |
|                      +---------------------------------+                          |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

#### Anatomi Komponen Utama:

1. **Domain Core (The Hexagon Interior)**:
   * **Sifat**: Bebas dependensi eksternal secara mutlak (*Zero Framework/Driver Dependency*). Tidak mengandung anotasi ORM, serialization tags, atau referensi HTTP/Network.
   * **Isi**: *Entities*, *Value Objects*, *Domain Exceptions*, dan *Domain Services*.
   * **Invarian**: State mutlak dilindungi oleh *encapsulation*; modifikasi state hanya dapat dieksekusi melalui metode domain yang memvalidasi aturan bisnis.

2. **Ports (Boundary Interfaces)**:
   * **Inbound / Driving Ports**: Kontrak API internal aplikasi yang mendefinisikan apa yang *dapat dilakukan* oleh aktor luar terhadap sistem kita (misalnya: `PlaceOrderUseCase`, `CancelSubscriptionCommand`). Dimiliki oleh dan didefinisikan di dalam Application Layer.
   * **Outbound / Driven Ports**: Kontrak *Service Provider Interface* (SPI) yang mendefinisikan apa yang *dibutuhkan* oleh domain/aplikasi dari dunia luar untuk menyelesaikan tugasnya (misalnya: `OrderRepository`, `PaymentGatewayPort`, `EventPublisherPort`). Didefinisikan di Application Layer, namun diimplementasikan di Infrastructure Layer.

3. **Adapters (The Hexagon Exterior)**:
   * **Driving (Primary) Adapters**: Memulai interaksi ke dalam aplikasi. Mengonversi protokol transport eksternal (JSON over HTTP, gRPC frames, Kafka events) menjadi *Command/Query Data Transfer Objects (DTO)* yang dipahami oleh Inbound Ports.
   * **Driven (Secondary) Adapters**: Dipanggil oleh aplikasi. Mengonversi operasi domain abstrak menjadi operasi primitif spesifik vendor teknologi (misalnya: memetakan entitas domain ke schema tabel PostgreSQL via SQL query/ORM, atau memanggil REST API pihak ketiga).

---

### 4. Why & What

#### Problem: Degradasi Layered Architecture Tradisional
Pada arsitektur 3-tier tradisional (*Controller -> Service -> DAO/Repository*), dependensi mengalir secara transitif ke bawah: `Presentation -> Business -> Database`. Dampak strukturalnya meliputi:
* **Database-Driven Thinking**: Domain model dirancang mengikuti schema relasional tabel (anotasi JPA/GORM/Prisma langsung di entity). Akibatnya, perubahan skema database mendikte perubahan logika bisnis.
* **Anemic Domain Model**: Logika bisnis bocor ke layer service atau prosedur database (*stored procedures*), menjadikan domain model sekadar struktur data pasif (*getters/setters*).
* **High Coupling & Poor Testability**: Pengujian logika bisnis membutuhkan database aktif atau mocking pustaka ORM yang kompleks dan rapuh terhadap refaktorisasi internal.

#### Solution: Hexagonal Architecture
Hexagonal Architecture mengisolasi *Domain Core* sebagai inti aplikasi yang agnostik terhadap dunia luar melalui *Dependency Inversion*:
* Mengubah ketergantungan sehingga *Infrastruktur bergantung pada Domain*, bukan sebaliknya.
* Memungkinkan penggantian *delivery mechanism* (misalnya dari REST ke gRPC) atau *persistence engine* (misalnya dari PostgreSQL ke DynamoDB) tanpa memodifikasi satu baris pun kode logika domain.
* Mempercepat eksekusi unit test hingga level milidetik karena pengujian domain tidak memerlukan I/O, network socket, atau inisialisasi framework.

---

### 5. How (Workflow Detail)

Alur eksekusi komprehensif dari sebuah request produksi:

```
[External Client]
       |
       | 1. HTTP POST /orders (Payload JSON)
       v
+--------------------------------------------------------------------------+
| DRIVING ADAPTER (HttpOrderAdapter)                                       |
| - Bind HTTP Request ke Inbound DTO (CreateOrderRequest)                  |
| - Validasi format sintaksis dasar (Schema Validation)                    |
| - Map DTO ke Application Command (CreateOrderCommand)                    |
| - Invoke Inbound Port: OrderUseCase.CreateOrder(ctx, cmd)                |
+--------------------------------------------------------------------------+
       |
       | 2. Execution Jump via Interface
       v
+--------------------------------------------------------------------------+
| APPLICATION SERVICE (OrderApplicationService implements OrderUseCase)    |
| - Start Transactional Boundary (menggunakan Transaction Manager Port)    |
| - Invoke Driven Port (AccountRepoPort): Fetch Account Aggregate         |
| - Validasi Otorisasi & Kuota Bisnis lintas agregat                      |
| - Instantiate Order Aggregate via Domain Factory / Invariant Validator   |
| - Mutasi State Domain: order.ExecutePaymentHold(...)                     |
| - Invoke Driven Port (OrderRepoPort): Save(order)                        |
| - Invoke Driven Port (EventOutboxPort): Append(OrderCreatedDomainEvent)  |
| - Commit Transaction Boundary                                            |
| - Map Domain Entity ke Application Result DTO (OrderResult)              |
| - Return OrderResult ke Inbound Adapter                                  |
+--------------------------------------------------------------------------+
       |                                   |
       | 3a. Invoke Driven Port            | 3b. Invoke Driven Port
       v                                   v
+----------------------------+   +-----------------------------------------+
| DRIVEN ADAPTER             |   | DRIVEN ADAPTER                          |
| (PostgreSqlOrderAdapter)   |   | (KafkaOutboxAdapter)                    |
| - Map Domain -> DB Record  |   | - Serialize Domain Event -> JSON Binary |
| - Execute SQL INSERT       |   | - Insert into transactional outbox tbl  |
+----------------------------+   +-----------------------------------------+
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Port USB pada Komputer Modern
Bayangkan sebuah motherboard komputer:
* **Motherboard (Domain Core)** memiliki jalur komunikasi sirkuit standar (Logic).
* **Port USB (Inbound & Outbound Ports)** adalah spesifikasi antarmuka standar (*standardized interface*). Motherboard tidak peduli perangkat apa yang dicolokkan ke port tersebut.
* **Perangkat USB (Adapters)**: Anda dapat mencolokkan keyboard mekanikal, flash disk, mouse nirkabel, atau instrumen musik MIDI (Adapters). Perangkat tersebut menerjemahkan protokol spesifik perangkat menjadi sinyal USB yang dipahami oleh motherboard. Mengganti keyboard berkabel dengan keyboard nirkabel tidak memerlukan modifikasi pada sirkuit motherboard.

#### Pemetaan Object Lintas Boundary

```
[ External Protocol ]           [ Application Layer ]          [ Domain Layer ]
  HTTP Request Body                Command / DTO                 Aggregate Root
+--------------------+           +------------------+         +-------------------+
| {                  |           | type CreateOrder |         | type Order struct |
|   "acc_id": "A1",  | --(Map)-> | Command struct { | -(Map)->|   id AccountID    |
|   "total": 50000   |           |   AccountID: "A1"|         |   amount Money    |
| }                  |           |   Amount: 50000  |         |   status Status   |
+--------------------+           +------------------+         +---------+---------+
                                                                        |
                                                                   (Maps To)
                                                                        v
                                                             [ Infrastructure ]
                                                                Database Entity
                                                              +-------------------+
                                                              | Table "orders"    |
                                                              | - id: VARCHAR(36) |
                                                              | - balance: BIGINT |
                                                              | - state: SMALLINT |
                                                              +-------------------+
```

---

### 7. Simple Example & Practical Example

Bahasa implementasi: **Go (Golang)** dengan standard library dan idiom strict boundary isolation.

#### A. Simple Example (Konsep Port & Inversi Dependensi)

```go
package simple

// Outbound Port
type NotificationPort interface {
	SendAlert(message string) error
}

// Domain Service
type SecurityMonitor struct {
	notifier NotificationPort // Bergantung pada Abstraksi
}

func NewSecurityMonitor(n NotificationPort) *SecurityMonitor {
	return &SecurityMonitor{notifier: n}
}

func (s *SecurityMonitor) BreachDetected(zone string) error {
	// Domain rule: Zone 0 breaches must trigger urgent alerts
	return s.notifier.SendAlert("CRITICAL: Breach in " + zone)
}
```

---

#### B. Practical Example: Production-Grade Core Settlement Engine

Struktur Direktori:
```text
settlement/
├── domain/
│   ├── account.go          // Entities & Value Objects (Zero dependencies)
│   └── errors.go           // Explicit Domain Errors
├── application/
│   ├── ports.go            // Inbound & Outbound Ports
│   └── service.go          // Orchestration, Application Service
└── infrastructure/
    ├── adapters/
    │   ├── http_inbound.go // Inbound Controller Adapter
    │   └── postgres_repo.go// Outbound Database Adapter
    └── persistence/
        └── models.go       // ORM/SQL Data Models (Separate from Domain)
```

##### 1. Domain Layer (`domain/account.go`, `domain/errors.go`)
```go
package domain

import (
	"errors"
	"fmt"
	"time"
)

var (
	ErrInsufficientBalance = errors.New("domain: balance cannot fall below minimum threshold")
	ErrNegativeAmount       = errors.New("domain: transaction amount must be strictly positive")
	ErrAccountLocked        = errors.New("domain: account is currently locked for settlement")
)

// Value Object: Invarian selalu valid sejak inisialisasi
type Money struct {
	amount   int64  // Nilai disimpan dalam subunit terkecil (sen/rupiah murni tanpa floating point)
	currency string
}

func NewMoney(amount int64, currency string) (Money, error) {
	if amount <= 0 {
		return Money{}, ErrNegativeAmount
	}
	if currency != "IDR" && currency != "USD" {
		return Money{}, fmt.Errorf("domain: unsupported currency %s", currency)
	}
	return Money{amount: amount, currency: currency}, nil
}

func (m Money) Amount() int64    { return m.amount }
func (m Money) Currency() string { return m.currency }

// Aggregate Root
type SettlementAccount struct {
	id        string
	balance   int64
	currency  string
	isLocked  bool
	version   int
	updatedAt time.Time
}

// Reconstitute: Digunakan oleh Outbound Adapter untuk memulihkan state dari DB
func ReconstituteAccount(id string, balance int64, currency string, isLocked bool, version int, updatedAt time.Time) *SettlementAccount {
	return &SettlementAccount{
		id:        id,
		balance:   balance,
		currency:  currency,
		isLocked:  isLocked,
		version:   version,
		updatedAt: updatedAt,
	}
}

// Bisnis Method: Melindungi Invarian State
func (a *SettlementAccount) Debit(money Money) error {
	if a.isLocked {
		return ErrAccountLocked
	}
	if a.currency != money.Currency() {
		return fmt.Errorf("domain: currency mismatch. expected %s, got %s", a.currency, money.Currency())
	}
	if a.balance-money.Amount() < 0 {
		return ErrInsufficientBalance
	}

	a.balance -= money.Amount()
	a.updatedAt = time.Now().UTC()
	return nil
}

// Getters murni tanpa mengekspos pointer internal mutable
func (a *SettlementAccount) ID() string         { return a.id }
func (a *SettlementAccount) Balance() int64     { return a.balance }
func (a *SettlementAccount) Currency() string  { return a.currency }
func (a *SettlementAccount) Version() int       { return a.version }
func (a *SettlementAccount) UpdatedAt() time.Time { return a.updatedAt }
```

##### 2. Application Layer (`application/ports.go`, `application/service.go`)
```go
package application

import (
	"context"
	"settlement/domain"
)

// --- DRIVEN (OUTBOUND) PORTS ---
type AccountRepositoryPort interface {
	FindByID(ctx context.Context, id string) (*domain.SettlementAccount, error)
	Save(ctx context.Context, account *domain.SettlementAccount) error
}

type AuditLoggerPort interface {
	LogExecution(ctx context.Context, accountID string, action string, amount int64) error
}

// --- DRIVING (INBOUND) PORT ---
type SettleTransactionCommand struct {
	AccountID string
	Amount    int64
	Currency  string
}

type SettleTransactionResult struct {
	AccountID    string `json:"account_id"`
	FinalBalance int64  `json:"final_balance"`
	Success      bool   `json:"success"`
}

type SettlementUseCase interface {
	ExecuteSettlement(ctx context.Context, cmd SettleTransactionCommand) (*SettleTransactionResult, error)
}

// --- APPLICATION SERVICE IMPLEMENTATION ---
type SettlementService struct {
	repo   AccountRepositoryPort
	logger AuditLoggerPort
}

func NewSettlementService(repo AccountRepositoryPort, logger AuditLoggerPort) SettlementUseCase {
	return &SettlementService{
		repo:   repo,
		logger: logger,
	}
}

func (s *SettlementService) ExecuteSettlement(ctx context.Context, cmd SettleTransactionCommand) (*SettleTransactionResult, error) {
	money, err := domain.NewMoney(cmd.Amount, cmd.Currency)
	if err != nil {
		return nil, err // Domain invariant validation failed
	}

	account, err := s.repo.FindByID(ctx, cmd.AccountID)
	if err != nil {
		return nil, err
	}

	// Menjalankan bisnis logic pada agregat
	if err := account.Debit(money); err != nil {
		return nil, err
	}

	// Persistensi perubahan via Driven Port
	if err := s.repo.Save(ctx, account); err != nil {
		return nil, err
	}

	// Side effect non-blocking via Driven Port
	_ = s.logger.LogExecution(ctx, account.ID(), "SETTLEMENT_DEBIT", money.Amount())

	return &SettleTransactionResult{
		AccountID:    account.ID(),
		FinalBalance: account.Balance(),
		Success:      true,
	}, nil
}
```

##### 3. Infrastructure Layer (`infrastructure/adapters/postgres_repo.go`, `infrastructure/adapters/http_inbound.go`)
```go
package adapters

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"settlement/application"
	"settlement/domain"
	"time"
)

// === OUTBOUND ADAPTER (POSTGRESQL REPOSITORY) ===
type PostgresAccountAdapter struct {
	db *sql.DB
}

func NewPostgresAccountAdapter(db *sql.DB) *PostgresAccountAdapter {
	return &PostgresAccountAdapter{db: db}
}

func (a *PostgresAccountAdapter) FindByID(ctx context.Context, id string) (*domain.SettlementAccount, error) {
	query := `SELECT id, balance, currency, is_locked, version, updated_at FROM accounts WHERE id = $1`
	row := a.db.QueryRowContext(ctx, query, id)

	var (
		accID     string
		balance   int64
		currency  string
		isLocked  bool
		version   int
		updatedAt time.Time
	)

	if err := row.Scan(&accID, &balance, &currency, &isLocked, &version, &updatedAt); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, errors.New("infrastructure: account record not found")
		}
		return nil, err
	}

	// Reconstitute domain model dari snapshot data
	return domain.ReconstituteAccount(accID, balance, currency, isLocked, version, updatedAt), nil
}

func (a *PostgresAccountAdapter) Save(ctx context.Context, account *domain.SettlementAccount) error {
	// Menggunakan Optimistic Concurrency Control (OCC)
	query := `
		UPDATE accounts 
		SET balance = $1, version = version + 1, updated_at = $2 
		WHERE id = $3 AND version = $4`

	res, err := a.db.ExecContext(ctx, query, account.Balance(), account.UpdatedAt(), account.ID(), account.Version())
	if err != nil {
		return err
	}

	rowsAffected, err := res.RowsAffected()
	if err != nil {
		return err
	}

	if rowsAffected == 0 {
		return errors.New("infrastructure: concurrent modification detected, stale state")
	}

	return nil
}

// === INBOUND ADAPTER (HTTP HANDLER) ===
type HttpSettlementAdapter struct {
	useCase application.SettlementUseCase
}

func NewHttpSettlementAdapter(useCase application.SettlementUseCase) *HttpSettlementAdapter {
	return &HttpSettlementAdapter{useCase: useCase}
}

type SettlementHttpRequest struct {
	AccountID string `json:"account_id"`
	Amount    int64  `json:"amount"`
	Currency  string `json:"currency"`
}

func (h *HttpSettlementAdapter) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
		return
	}

	var req SettlementHttpRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Malformed JSON", http.StatusBadRequest)
		return
	}

	// Pemetaan dari DTO Transport ke Command Application
	cmd := application.SettleTransactionCommand{
		AccountID: req.AccountID,
		Amount:    req.Amount,
		Currency:  req.Currency,
	}

	result, err := h.useCase.ExecuteSettlement(r.Context(), cmd)
	if err != nil {
		// Terjemahkan domain/app error ke kode status HTTP yang tepat
		switch {
		case errors.Is(err, domain.ErrInsufficientBalance), errors.Is(err, domain.ErrNegativeAmount):
			http.Error(w, err.Error(), http.StatusUnprocessableEntity)
		case errors.Is(err, domain.ErrAccountLocked):
			http.Error(w, err.Error(), http.StatusLocked)
		default:
			http.Error(w, "Internal Settlement Error: "+err.Error(), http.StatusInternalServerError)
		}
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(result)
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Multi-Provider High-Throughput Payment Gateway (12.000 TPS)

* **Konteks**: Sistem pemrosesan transaksi dompet digital global perlu mendukung pengalihan (*failover*) dinamis antara 3 payment rails: Visa/Mastercard (ISO 8583 protocol), Swift GPI (MT103 standard), dan Real-Time Local Clearing (REST/JSON API).
* **Kendala Arsitektur Lama**:
  * Logika bisnis transaksi terikat erat pada SDK HTTP REST vendor awal.
  * Ketika integrasi ISO 8583 ditambahkan, kode dipenuhi blok kondisional:
    `if (provider == ISO8583) { ... parse byte payload ... } else { ... parse JSON ... }`.
  * Rata-rata waktu rilis (*time-to-market*) untuk integrasi vendor baru mencapai 14 minggu. Tingkat regresi sistem inti mencapai 22% setiap deployment.
* **Transformasi ke Hexagonal Architecture**:
  1. **Deklarasi Outbound Port Murni**:
     ```go
     type PaymentNetworkPort interface {
         AuthorizeFunds(ctx context.Context, authTx AuthorizationIntent) (NetworkReceipt, error)
     }
     ```
  2. **Isolasi Adapter Konkret**:
     * Dibangun 3 secondary adapters terpisah: `Iso8583SocketAdapter`, `SwiftMqAdapter`, dan `RestClearingAdapter`.
     * Setiap adapter menangani serialization byte-level, TCP keep-alive, buffer pooling, dan retry logic sendiri.
  3. **Runtime Dynamic Routing via Factory Adapter**:
     * Dibuat adapter komposit `SmartRoutingAdapter` yang mengimplementasikan `PaymentNetworkPort`. Adapter ini membaca latency histogram dari Redis dan mengalirkan traffic ke adapter downstream terbaik tanpa diketahui oleh Application Service.
* **Hasil Pengukuran Produksi**:
  * **Time-to-Market**: Integrasi provider baru berkurang dari 14 minggu menjadi 9 hari kerja.
  * **Test Coverage**: Logic core mencapai 98% line coverage dengan test runtime < 3 detik untuk 15.000 unit test kasus settlement.
  * **Downtime**: Menghilangkan 100% insiden regresi logika core saat penggantian integrasi third-party.

---

### 9. Trade-offs

| Aspek | Pendekatan Monolitik Tradisional (Layered 3-Tier) | Hexagonal Architecture (Ports & Adapters) |
| :--- | :--- | :--- |
| **Performance (CPU & Memory)** | **Unggul**: Nol mapping overhead. Entitas DB langsung diserialisasi ke JSON response. Alokasi memori minimal. | **Overhead Sedang**: Membutuhkan alokasi memori untuk mapping (Transport DTO -> App Command -> Domain Entity -> DB Record). |
| **Latency** | **Sangat Rendah**: Jalur eksekusi lurus langsung memanggil driver DB. | **Tambahan Latensi Mikrodetik**: Disebabkan konversi pointer dan alokasi stack/heap antar batas abstraksi. |
| **Maintainability & Evolution** | **Sangat Rendah**: Runtuh saat dependensi pihak ketiga berubah atau migrasi teknologi. | **Sangat Tinggi**: Core domain kebal terhadap evolusi runtime, database, framework, maupun third-party SDK. |
| **Cognitive Load & Boilerplate** | **Rendah pada awal proyek**: Struktur sederhana, cepat dibangun oleh engineer pemula. | **Tinggi**: Membutuhkan banyak antarmuka, file mapping terpisah, dan pemahaman ketat tentang batas dependensi. |
| **Testability Execution Speed** | **Lambat**: Bergantung pada in-memory database (H2/SQLite) atau Docker Testcontainers. | **Ekstrem Cepat**: 100% logika domain dan use case dapat diuji murni via mock/in-memory struct di level RAM. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Leaking Infrastructure Annotations into Domain
* **Anti-Pattern**:
  ```go
  type Order struct {
      ID string `gorm:"primaryKey" json:"id"` // KEBOCORAN ABSTRAKSI!
  }
  ```
* **Dampak**: Domain terikat pada bug atau behavior serialization framework tertentu.
* **Remediasi**: Jaga domain struct murni. Simpan tag `json:` hanya pada Transport DTO, dan tag `gorm:` / `db:` pada Persistence Models.

#### 2. Domain Calling Driven Adapters Directly
* **Anti-Pattern**: Mengirim pointer HTTP Client atau Database connection ke dalam method domain entity: `order.Save(dbConn)`.
* **Remediasi**: Terapkan *Pure Function / Side-effect Free* pada Domain. Biarkan Application Service yang mengambil state, mengirimkannya ke Domain untuk diproses, lalu mengoper hasilnya ke Driven Port.

#### 3. Generic Outbound Port ("Swiss Army Knife" Repository)
* **Anti-Pattern**:
  ```go
  type Repository[T any] interface {
      Save(T)
      FindAll() []T
      CustomQuery(rawSql string) // Merusak enkapsulasi port
  }
  ```
* **Remediasi**: Spesifikasikan port berdasarkan kebutuhan use case: `SettlementAccountRepository`, `LedgerAuditLogWriter`. Port harus berorientasi pada intensi bisnis, bukan kapabilitas SQL.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Strict Import Control**: Domain package tidak boleh mengimpor package di luar standard library dasar (tidak ada HTTP, Database, atau third-party package).
2. [ ] **Architecture Fitness Function**: Pasang linter arsitektur otomatis (seperti `archunit-jvm` untuk Java atau `depguard`/`golangci-lint` untuk Go) dalam pipeline CI untuk mencegah impor terlarang:
   ```yaml
   # Contoh konfigurasi depguard
   deny:
     - pkg: "database/sql"
       in: "**/domain/**"
     - pkg: "net/http"
       in: "**/domain/**"
   ```
3. [ ] **Explicit Boundary Mappers**: Gunakan mapper fungsi murni `ToDomain()` dan `ToDatabaseRecord()` yang terisolasi di dalam adapter file. Hindari *reflection-based automappers* untuk throughput kritis.
4. [ ] **Context & Deadline Propagation**: Teruskan `context.Context` (atau analoginya) melalui Inbound Port hingga ke Outbound Port untuk menjamin penanganan graceful cancellation dan distributed timeout.
5. [ ] **No Primitive Obsession**: Gunakan Value Objects untuk membungkus konsep kunci (seperti `AccountID`, `CurrencyCode`, `Email`) guna mencegah kesalahan parameter yang tertukar saat pemanggilan method.

---

### 12. Hands-on Practice

Buat dan operasikan project Hexagonal Architecture secara bertahap pada direktori kerja: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/ledger-system/{domain,application,infrastructure/adapters}
cd hands-on/m02/ledger-system
go mod init enterprise/ledger
```

#### Langkah 1: Buat Domain Core
Buat file `domain/transaction.go`:
```go
package domain

import (
	"errors"
	"time"
)

var ErrInvalidTransactionState = errors.New("cannot post an already finalized transaction")

type TxStatus string
const (
	Pending   TxStatus = "PENDING"
	Finalized TxStatus = "FINALIZED"
)

type Transaction struct {
	id        string
	amount    int64
	status    TxStatus
	createdAt time.Time
}

func NewTransaction(id string, amount int64) *Transaction {
	return &Transaction{
		id:        id,
		amount:    amount,
		status:    Pending,
		createdAt: time.Now().UTC(),
	}
}

func (t *Transaction) Finalize() error {
	if t.status == Finalized {
		return ErrInvalidTransactionState
	}
	t.status = Finalized
	return nil
}

func (t *Transaction) ID() string         { return t.id }
func (t *Transaction) Amount() int64     { return t.amount }
func (t *Transaction) Status() TxStatus   { return t.status }
```

#### Langkah 2: Buat Ports & Application Service
Buat file `application/ledger_usecase.go`:
```go
package application

import (
	"context"
	"enterprise/ledger/domain"
)

// Driven Port
type TransactionStorePort interface {
	Save(ctx context.Context, tx *domain.Transaction) error
	Get(ctx context.Context, id string) (*domain.Transaction, error)
}

// Inbound Port
type LedgerUseCase interface {
	PostTransaction(ctx context.Context, id string, amount int64) error
}

type LedgerService struct {
	store TransactionStorePort
}

func NewLedgerService(store TransactionStorePort) *LedgerService {
	return &LedgerService{store: store}
}

func (s *LedgerService) PostTransaction(ctx context.Context, id string, amount int64) error {
	tx := domain.NewTransaction(id, amount)
	if err := tx.Finalize(); err != nil {
		return err
	}
	return s.store.Save(ctx, tx)
}
```

#### Langkah 3: Implementasikan In-Memory Driven Adapter
Buat file `infrastructure/adapters/inmemory_store.go`:
```go
package adapters

import (
	"context"
	"enterprise/ledger/domain"
	"errors"
	"sync"
)

type InMemoryTxStore struct {
	mu   sync.RWMutex
	data map[string]*domain.Transaction
}

func NewInMemoryTxStore() *InMemoryTxStore {
	return &InMemoryTxStore{data: make(map[string]*domain.Transaction)}
}

func (m *InMemoryTxStore) Save(ctx context.Context, tx *domain.Transaction) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data[tx.ID()] = tx
	return nil
}

func (m *InMemoryTxStore) Get(ctx context.Context, id string) (*domain.Transaction, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	tx, exists := m.data[id]
	if !exists {
		return nil, errors.New("not found")
	}
	return tx, nil
}
```

#### Langkah 4: Hubungkan Seluruh Sistem (Dependency Injection Root)
Buat file `main.go`:
```go
package main

import (
	"context"
	"enterprise/ledger/application"
	"enterprise/ledger/infrastructure/adapters"
	"fmt"
)

func main() {
	// Composition Root
	drivenAdapter := adapters.NewInMemoryTxStore()
	useCase := application.NewLedgerService(drivenAdapter)

	// Invoke Inbound Flow via Context
	ctx := context.Background()
	txID := "tx-8831"

	err := useCase.PostTransaction(ctx, txID, 750000)
	if err != nil {
		panic(err)
	}

	persisted, _ := drivenAdapter.Get(ctx, txID)
	fmt.Printf("[PRODUKSI] Transaksi %s berhasil diproses. Status Akhir: %s, Nominal: %d\n",
		persisted.ID(), persisted.Status(), persisted.Amount())
}
```

Uji eksekusi modul:
```bash
go run main.go
```

---

### 13. Exercise

#### Level: Easy
1. Modifikasi file `domain/transaction.go` pada praktikum di atas:
   * Tambahkan invariant: `amount` tidak boleh bernilai kurang dari atau sama dengan `0`.
   * Return error `ErrNegativeAmount` jika dilanggar saat instansiasi `NewTransaction`.

#### Level: Medium
1. Implementasikan driven adapter baru bernama `infrastructure/adapters/ConsoleAuditAdapter` yang mengimplementasikan interface `AuditNotificationPort`:
   ```go
   type AuditNotificationPort interface {
       Notify(ctx context.Context, txID string, status string) error
   }
   ```
2. Hubungkan adapter tersebut ke dalam `LedgerService` sehingga setiap kali transaksi difinalisasi, sistem mencetak audit string ke standard output.

#### Level: Hard
1. Tambahkan middleware idempotensi pada Inbound Driving Adapter:
   * Bangun adapter HTTP Inbound murni menggunakan `net/http`.
   * Tangani parsing header `X-Idempotency-Key`.
   * Pastikan request dengan idempotency-key yang sama dalam rentang 60 detik tidak menjalankan UseCase dua kali, melainkan mengembalikan *cached response*.

---

### 14. Challenge

**Skenario**: Sistem Anda mengalami *Database Migration* berskala masif dari MongoDB (Document Store) ke ScyllaDB (Wide-column Store) dalam arsitektur live 24/7.

**Instruksi**:
1. Tanpa mengubah kode di dalam layer `domain/` dan `application/`, buatlah sebuah *Dual-Writing & Read-Repair Composite Driven Adapter* yang mengimplementasikan `TransactionStorePort`.
2. Adapter ini harus:
   * Menulis secara sinkron ke MongoDB (primary lama) dan asinkron (background worker pool) ke ScyllaDB (database baru).
   * Melakukan pembacaan data: Jika data tidak ditemukan di ScyllaDB, lakukan *fallback read* ke MongoDB dan secara otomatis migrasikan record tersebut ke ScyllaDB (*read-repair pattern*).
   * Menyediakan metrik prometheus counter untuk mengukur *replication lag* dan *drift discrepancy*.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual Cepat)
1. **Di mana interface Inbound Port harus didefinisikan dalam struktur direktori Hexagonal?**
   * A. Di Infrastructure layer bersama Controller.
   * B. Di Application Use Case layer.
   * C. Di Domain Entity layer.
   * D. Di Third-party SDK client library.
   * *Jawaban yang benar: B*

2. **Apa yang dimaksud dengan Inversion of Control (IoC) dalam konteks Hexagonal Architecture?**
   * A. Database memanggil domain service secara langsung.
   * B. Framework dependency injection wajib digunakan untuk menjalankan aplikasi.
   * C. Arah ketergantungan logika bisnis tidak lagi mengarah ke database, melainkan infrastruktur database yang diarahkan untuk bergantung pada kontrak interface domain/aplikasi.
   * D. Domain entity dapat secara bebas memanggil REST API pihak ketiga.
   * *Jawaban yang benar: C*

3. **Manakah dari hal berikut yang DILARANG KERAS berada di dalam Domain Core?**
   * A. Value Objects.
   * B. Business Domain Exceptions.
   * C. Struct tags ORM (misal: `gorm:"column:user_id"`).
   * D. Pure business logic functions.
   * *Jawaban yang benar: C*

4. **Apa peran utama dari Driving (Inbound) Adapter?**
   * A. Menulis record ke tabel basis data relasional.
   * B. Mengonversi protokol transport eksternal menjadi pemanggilan Use Case application.
   * C. Mengelola connection pool TCP ke broker pesan.
   * D. Melakukan snapshot serialization ke Redis cache.
   * *Jawaban yang benar: B*

5. **Apa fungsi dari metode `Reconstitute` pada implementasi Domain Entity?**
   * A. Membuat entity baru yang belum pernah tersimpan di database.
   * B. Memulihkan state entity internal dari database snapshot tanpa memicu validasi pembuatan awal (initial lifecycle events).
   * C. Mengonversi entity menjadi representasi JSON untuk dikirim via HTTP.
   * D. Menghapus entity dari memori secara permanen.
   * *Jawaban yang benar: B*

#### Bagian 2: Intermediate (Analisis Solusi)
6. **Mengapa Domain Entity tidak boleh mereferensikan DTO yang didefinisikan oleh Driving Controller?**
   * *Analisis*: DTO controller dirancang untuk merefleksikan payload transport (misal format HTTP request). Jika Domain Entity mereferensikan DTO, Domain akan bergantung secara transitif pada protokol eksternal. Perubahan payload API eksternal akan memaksa perubahan pada Domain Core, melanggar prinsip *Stable Abstractions Principle*.

7. **Bagaimana cara menangani integritas transaksi ACID pada operasi yang melibatkan dua driven adapter berbeda (misal: Database Write dan Message Broker Publish)?**
   * *Analisis*: Gunakan *Transactional Outbox Pattern*. Alih-alih mempublikasikan message langsung ke broker eksternal di dalam transaksi database yang sama (yang memicu distributed transaction anomalies), domain event disimpan ke dalam tabel outbox di database yang sama melalui driven adapter repo. Komponen independen (*Debezium CDC* atau *polling worker*) kemudian membaca tabel tersebut dan meneruskannya ke message broker.

8. **Apakah Value Object boleh memiliki method yang mengubah datanya sendiri (mutator)? Jelaskan.**
   * *Analisis*: Tidak boleh. Value Object bersifat *immutable*. Operasi apapun yang memodifikasi Value Object harus menghasilkan instans Value Object baru dengan nilai yang telah diubah, bukan memutasi nilai internal instans yang ada.

9. **Kapan waktu yang tepat untuk memisahkan model database dari entitas domain daripada menyatukannya?**
   * *Analisis*: Pada sistem produksi skala menengah hingga enterprise, pemisahan harus selalu dilakukan. Penyatuan hanya dapat ditoleransi pada *CRUD-heavy throwaway prototype*. Skema basis data dioptimalkan untuk penyimpanan dan querying (normalisasi/denormalisasi), sedangkan domain model dioptimalkan untuk menjaga integritas invarian bisnis dan aturan enkapsulasi.

10. **Bagaimana menguji Application Service secara menyeluruh tanpa menggunakan mocking library pihak ketiga?**
    * *Analisis*: Gunakan pola *In-Memory Fake Adapter*. Bangun struct adapter sederhana yang mengimplementasikan Outbound Port menggunakan `map[string]Entity` di memori lokal. Inject struct fake ini ke Application Service saat penulisan unit test. Hal ini menghasilkan pengujian deterministik, cepat, dan terisolasi dari kegagalan network/database.

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario Kasus 1**: Sistem Anda menggunakan Redis sebagai primary store untuk *real-time user session*. Tim infrastruktur memutuskan untuk mengganti Redis dengan KeyDB atau Aerospike karena kendala lisensi open-source. Jelaskan secara teknis bagaimana Hexagonal Architecture memitigasi risiko breaking changes pada use case otentikasi!
    * *Solusi Arsitektural*: Use case otentikasi hanya bergantung pada driven port: `type UserSessionPort interface`. Dibuat adapter baru (misal: `AerospikeSessionAdapter`) yang mengimplementasikan interface tersebut. Pengujian integrasi dijalankan spesifik terhadap adapter baru ini. Use case logic sama sekali tidak disentuh atau diubah. Saat switchover, dependency injection root (`main.go`) cukup diubah untuk menginisialisasi adapter Aerospike.

12. **Skenario Kasus 2**: Sebuah batch-processing service memproses 100.000 records per menit. Tim engineer mendapati latensi Garbage Collection (GC) spike tinggi. Profiling menunjukkan alokasi memori berlebih akibat pemetaan DTO -> Command -> Domain Entity -> Database Model untuk setiap baris. Bagaimana Anda menyelesaikan masalah performa ini tanpa merusak batas Hexagonal Architecture secara fundamental?
    * *Solusi Arsitektural*: Terapkan pola *Object Pooling* (`sync.Pool` di Go atau *Flyweight Pattern*), atau gunakan streaming processing pipeline berbasis batch chunking (misalnya memproses per 1.000 batch via pointer reuse). Untuk jalur analytical read-only intensif, terapkan pola **CQRS (Command Query Responsibility Segregation)**: Sisi Query dapat memotong jalur domain dan memetakan record DB langsung ke read-projection DTO melalui driven port khusus query, tanpa perlu instansiasi aggregate root yang kompleks.

13. **Skenario Kasus 3**: Audit keamanan mendeteksi bahwa beberapa engineer junior menulis query database langsung di dalam HTTP Controller dengan alasan "meningkatkan performa untuk endpoint pelaporan cepat". Langkah teknis dan arsitektural apa yang harus diimplementasikan untuk mencegah kejadian serupa terulang di masa depan?
    * *Solusi Arsitektural*:
      1. Terapkan segregasi modul/package level bahasa secara ketat: pastikan package `controller` tidak memiliki akses visibilitas terhadap package database driver (`database/sql`, `pgx`, dll).
      2. Pasang automated fitness tests (contoh: *ArchUnit* atau rules linter khusus pada CI pipeline) yang menggagalkan proses build jika terdapat import database di dalam package driving adapters.
      3. Rancang endpoint pelaporan melalui jalur Query Port yang sah dengan kontrak yang jelas tanpa mengekspos pointer koneksi basis data.

---

### 16. Summary

Hexagonal Architecture (*Ports and Adapters*) adalah pola fondasional untuk membangun perangkat lunak enterprise yang tahan terhadap perubahan zaman (*future-proof*). 

Kunci utama penguasaan arsitektur ini:
* **The Dependency Rule**: Dependensi source code hanya boleh mengarah ke dalam (menuju *Domain Core*). Bagian dalam tidak mengetahui apa pun tentang bagian luar.
* **Separation of Concerns via Ports**: Logika domain mendikte kontrak yang dibutuhkannya (*Driven Ports*) dan kontrak yang disediakannya (*Inbound Ports*).
* **Adapters as Isolators**: Segala kompleksitas protokol pihak ketiga, database serialization, networking, dan frameworks diisolasi di luar hexagon.
* **Decoupled Evolution**: Framework, database engine, dan protocol transport dapat diganti sewaktu-waktu dengan dampak zero-regression pada logika bisnis inti organisasi.