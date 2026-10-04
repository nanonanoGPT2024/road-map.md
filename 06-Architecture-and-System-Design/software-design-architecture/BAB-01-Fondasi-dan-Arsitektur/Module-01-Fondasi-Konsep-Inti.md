# Bab 01 Module 01: Dasar-dasar Arsitektur & Desain Perangkat Lunak (Architectural Drivers, Boundaries, & Separation of Concerns)

---

### 1. Learning Objectives (Tujuan Pembelajaran)
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
* **Mendiferensiasikan** secara presisi antara Software Architecture (*architectural decisions*, struktur makro, *system capabilities*) dan Software Design (*code organization*, pola mikro, *implementation details*).
* **Mengidentifikasi dan mengekstraksi** *Architectural Drivers* (Quality Attributes/Non-Functional Requirements, Functional Requirements, Technical Constraints, dan Business Goals) dari dokumen spesifikasi sistem.
* **Merancang batas sistem (*System Boundary*)** menggunakan prinsip *Separation of Concerns* (SoC), *Loose Coupling*, dan *High Cohesion*.
* **Mengevaluasi trade-off** antara kompleksitas struktural (*accidental complexity*) dan ketahanan sistem (*system resilience & maintainability*).
* **Mengimplementasikan abstraksi batas modular** dalam kode nyata yang menegakkan isolasi domain dan *inversion of control*.

---

### 2. Fundamental Concepts (Konsep Fundamental)
Arsitektur perangkat lunak bukanlah sekadar diagram kotak dan panah (*boxes and arrows*), melainkan fondasi struktural yang menentukan bagaimana elemen-elemen sistem didistribusikan, diisolasi, dan berinteraksi.

Tiga pilar fundamental:
1. **Architectural Drivers:** Kumpulan faktor yang secara langsung memandu bentuk arsitektur. Driver ini mencakup kriteria performa, latensi, konkurensi, keandalan, kepatuhan regulasi, hingga batasan anggaran infrastruktur.
2. **Coupling vs. Cohesion:**
   * **Coupling:** Derajat ketergantungan antar-modul. Target arsitektur adalah *loose coupling*, di mana modul $A$ dapat berevolusi, direfaktor, atau diganti tanpa memicu efek domino (*shotgun surgery*) pada modul $B$.
   * **Cohesion:** Derajat keterkaitan internal tanggung jawab dalam satu modul. Target arsitektur adalah *high cohesion*, di mana seluruh elemen di dalam modul bekerja untuk satu tujuan domain yang tunggal dan spesifik.
3. **Architectural Boundary:** Batasan logis atau fisik yang memisahkan subsistem yang berbeda tingkat abstraksinya (misal: *Core Business Logic* terisolasi dari *Infrastructure/Database*).

---

### 3. Why It Matters (Mengapa Hal Ini Krusial)
* **Pencegahan The Big Ball of Mud:** Tanpa pemisahan batas (*boundaries*) yang tegas sejak awal, sistem secara gradual akan membusuk (*software rot*). Dependensi melingkar (*cyclic dependencies*) membuat refaktorisasi menjadi mustahil dan deployment berisiko tinggi.
* **Skalabilitas Organisasional (Conway’s Law):** Arsitektur sistem mencerminkan struktur komunikasi organisasi. Batas arsitektural yang jelas memungkinkan pembagian kepemilikan tim (*team ownership*) tanpa konflik merge atau ketergantungan deployment timbal balik (*coupled deployments*).
* **Total Cost of Ownership (TCO):** 80% biaya siklus hidup perangkat lunak dialokasikan pada fase *maintenance*. Arsitektur yang dirancang berdasarkan *Architectural Drivers* menekan biaya regresi dan waktu henti (*downtime*) saat terjadi perubahan spesifikasi bisnis.

---

### 4. What It Is (Definisi & Esensi Teknis)
* **Software Architecture:** Himpunan keputusan desain yang fundamental dan krusial—yaitu keputusan yang **sulit atau mahal untuk diubah di kemudian hari**. Arsitektur berfokus pada *Quality Attributes* (seperti *scalability*, *availability*, *modifiability*, *security*).
* **Software Design:** Pengambilan keputusan pada skala mikro mengenai penataan modul, kelas, fungsi, algoritma, dan tipe data. Keputusan ini biasanya terisolasi di dalam batas subsistem dan dapat diubah tanpa mempengaruhi sistem secara holistik.
* **Separation of Concerns (SoC):** Prinsip arsitektural yang membagi sistem ke dalam domain-domain terpisah, di mana masing-masing bagian hanya menangani satu aspek logis (misalnya: penanganan protokol I/O dipisahkan dari evaluasi aturan validasi bisnis).

---

### 5. How It Works (Mekanisme Kerja Arsitektur & Desain)
Proses dekonstruksi dan perancangan arsitektur beroperasi melalui alur deterministik:

1. **Analisis Driver:** Mengonversi kebutuhan bisnis menjadi metrik kualitas yang terukur (misal: "Sistem harus cepat" diterjemahkan menjadi "$P_{99} \text{ Latency} < 150\text{ms}$ pada beban $10.000\text{ RPS}$").
2. **Identifikasi Subdomain:** Memecah domain problem space menjadi *Core*, *Supporting*, dan *Generic subdomains*.
3. **Pemberian Batas Arsitektural (*Boundary Encapsulation*):** Memisahkan modul domain dari dunia luar menggunakan antarmuka formal (*contracts/interfaces*).
4. **Dependency Inversion:** Memastikan arah dependensi kode selalu mengarah dari detail implementasi (infrastruktur, basis data, HTTP framework) menuju abstraksi domain, bukan sebaliknya.

---

### 6. Architecture Diagram (Diagram Arsitektur ASCII)

Berikut adalah visualisasi batas arsitektural (*Architectural Boundaries*) dan aliran kontrol vs. dependensi dependensi:

```text
+-----------------------------------------------------------------------+
|                         INFRASTRUCTURE LAYER                          |
|  [HTTP Controller]      [Message Queue Consumer]    [PostgreSQL Repo] |
+---------+--------------------------+-----------------------+----------+
          |                          |                       |
          | Calls                    | Calls                 | Implements
          v                          v                       v
+---------+--------------------------+-----------------------+----------+
|                         APPLICATION LAYER                             |
|                    [Use Case: ProcessPayment]                         |
|                                                                       |
|   +---------------------------------------------------------------+   |
|   | Input Port (Interface)            Output Port (Interface)     |   |
|   | +execute(dto: PaymentDTO)         +save(payment: Payment)     |   |
|   +---------------------------------------------------------------+   |
+------------------------------------+----------------------------------+
                                     |
                                     | Operates On
                                     v
+------------------------------------+----------------------------------+
|                            DOMAIN LAYER                               |
|                     [Entity: PaymentTransaction]                      |
|                                                                       |
|   - Rules: Validasi State, Invariant Transaksi, Kalkulasi Pajak      |
|   - NO external dependencies (Pure business logic)                   |
+-----------------------------------------------------------------------+

Dependency Direction:  Infrastructure  ------>  Application  ------>  Domain
Control Flow:          Client -> HTTP  ------>  Application  ------>  DB Driver
```

---

### 7. Component Deep Dive (Bedah Komponen Arsitektural)

1. **Domain Entities:** Objek yang merepresentasikan konsep bisnis murni. Mengandung *state* dan *business invariants*. Bebas dari dependensi framework, ORM, maupun protokol jaringan.
2. **Ports (Interfaces):**
   * *Inbound/Primary Ports:* Kontrak yang mendefinisikan apa yang dapat dilakukan lapisan luar terhadap use case (misal: Application Service Interface).
   * *Outbound/Secondary Ports:* Kontrak yang mendefinisikan dependensi eksternal yang dibutuhkan oleh domain/aplikasi untuk menyelesaikan tugasnya (misal: Repositori, Payment Gateway Interface).
3. **Adapters (Infrastruktur):** Implementasi konkrit dari *ports*. Bertanggung jawab menerjemahkan data dari protokol eksternal (seperti HTTP Request, Event Payload) ke format model domain internal, dan sebaliknya.

---

### 8. Minimal / Simple Implementation Example (Implementasi Minimal)

Pemisahan dependensi menggunakan Go: Domain murni bebas dari dependensi penyimpanan data.

```go
package main

import (
	"context"
	"errors"
	"fmt"
)

// --- DOMAIN LAYER (Zero external dependencies) ---

type OrderStatus string

const (
	StatusCreated OrderStatus = "CREATED"
	StatusPaid    OrderStatus = "PAID"
)

type Order struct {
	ID     string
	Amount float64
	Status OrderStatus
}

func (o *Order) MarkPaid() error {
	if o.Status == StatusPaid {
		return errors.New("order is already paid")
	}
	if o.Amount <= 0 {
		return errors.New("invalid order amount")
	}
	o.Status = StatusPaid
	return nil
}

// --- PORTS LAYER (Abstractions) ---

type OrderRepository interface {
	GetByID(ctx context.Context, id string) (*Order, error)
	Save(ctx context.Context, order *Order) error
}

// --- APPLICATION USE CASE LAYER ---

type OrderService struct {
	repo OrderRepository // Inverted Dependency
}

func NewOrderService(repo OrderRepository) *OrderService {
	return &OrderService{repo: repo}
}

func (s *OrderService) CompleteOrder(ctx context.Context, orderID string) error {
	order, err := s.repo.GetByID(ctx, orderID)
	if err != nil {
		return fmt.Errorf("lookup failed: %w", err)
	}

	if err := order.MarkPaid(); err != nil {
		return fmt.Errorf("domain invariant violation: %w", err)
	}

	return s.repo.Save(ctx, order)
}
```

---

### 9. Real-World Practical Example (Implementasi Nyata / Produksi)

Implementasi adaptasi infrastruktur dengan pertahanan konkurensi, context tracing, dan validasi *boundary* di lapisan data persistence.

```go
package main

import (
	"context"
	"database/sql"
	"fmt"
	"time"
)

// PostgresOrderRepository adalah Adapter untuk Secondary Port: OrderRepository
type PostgresOrderRepository struct {
	db *sql.DB
}

func NewPostgresOrderRepository(db *sql.DB) *PostgresOrderRepository {
	return &PostgresOrderRepository{db: db}
}

func (r *PostgresOrderRepository) GetByID(ctx context.Context, id string) (*Order, error) {
	ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	query := `SELECT id, amount, status FROM orders WHERE id = $1`
	row := r.db.QueryRowContext(ctx, query, id)

	var o Order
	var statusStr string
	if err := row.Scan(&o.ID, &o.Amount, &statusStr); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, fmt.Errorf("order %s not found: %w", id, errors.New("NOT_FOUND"))
		}
		return nil, fmt.Errorf("database query failure: %w", err)
	}
	o.Status = OrderStatus(statusStr)

	return &o, nil
}

func (r *PostgresOrderRepository) Save(ctx context.Context, order *Order) error {
	ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	query := `
		INSERT INTO orders (id, amount, status)
		VALUES ($1, $2, $3)
		ON CONFLICT (id) DO UPDATE 
		SET status = EXCLUDED.status, amount = EXCLUDED.amount
	`
	_, err := r.db.ExecContext(ctx, query, order.ID, order.Amount, string(order.Status))
	if err != nil {
		return fmt.Errorf("failed executing save order: %w", err)
	}
	return nil
}
```

---

### 10. Data Flow & Execution Path (Alur Data & Siklus Eksekusi)

Berikut adalah siklus eksekusi dari batas luar (*Network*) menuju batas dalam (*Domain*), lalu persistensi:

```text
[Client / HTTP Request]
         |  Payload: JSON { "order_id": "ORD-123" }
         v
+-----------------------------------------------------------+
| 1. HTTP Adapter (Handler/Controller)                      |
|    - Deserialisasi JSON Payload                           |
|    - Validasi format data transport (syntax validation)    |
|    - Memetakan request ke DTO/primitive types             |
+----------------------------+------------------------------+
                             |
                             | Inbound Call: CompleteOrder(ctx, "ORD-123")
                             v
+-----------------------------------------------------------+
| 2. Use Case (Application Layer)                           |
|    - Mengorkestrasi interaksi domain dan infrastruktur     |
|    - Membuka transaksi database bila diperlukan           |
|    - Memanggil r.repo.GetByID(ctx, id)                   |
+----------------------------+------------------------------+
                             |
                             | Fetch data via Outbound Port
                             v
+-----------------------------------------------------------+
| 3. Repository Adapter (Infrastructure Layer)              |
|    - Eksekusi SQL Query ke PostgreSQL                     |
|    - Memetakan SQL Relational rows -> Domain Entity       |
+----------------------------+------------------------------+
                             |
                             | Returns Domain Entity Instance
                             v
+-----------------------------------------------------------+
| 4. Domain Logic (Entity Boundary)                         |
|    - Eksekusi order.MarkPaid()                            |
|    - Validasi invariant internal domain                   |
|    - State berubah: StatusCreated -> StatusPaid          |
+----------------------------+------------------------------+
                             |
                             | Persist perubahan via Outbound Port
                             v
+-----------------------------------------------------------+
| 5. Repository Adapter                                     |
|    - Eksekusi SQL UPDATE dengan timeout & context tracing |
+-----------------------------------------------------------+
```

---

### 11. Boundary Conditions & Failure Modes (Kondisi Batas & Mode Kegagalan)

* **Kondisi Batas:**
  * **Network Partitions:** Adapter infrastruktur harus menangani timeout, circuit breaking, dan retry budget saat berinteraksi dengan API pihak ketiga atau basis data.
  * **Partial Failure:** Operasi komposit use-case yang gagal di tengah eksekusi harus menerapkan kompensasi state (*rollback* atau pola *Saga*) agar tidak meninggalkan sistem dalam kondisi *corrupt*.
* **Mode Kegagalan:**
  * **Domain Leakage:** Tipe data database (seperti `sql.NullString`) menembus masuk ke dalam entitas domain. Jika schema DB berubah, domain logic ikut rusak.
  * **Implicit Fallthrough:** Menelan galat (*error swallowing*) pada adapter tanpa membungkusnya (*wrapping*) ke tipe galat yang dipahami oleh domain/use case.

---

### 12. Performance & Resource Considerations (Performa & Manajemen Sumber Daya)
* **Abstraksi vs. Alokasi Memori:** Desain berbasis antarmuka (*interface dispatch*) di Go menimbulkan alokasi memori heap tambahan (*escape analysis*) dibandingkan pemanggilan *concrete struct direct call*. Namun, rasio overhead ini (beberapa nanodetik) dapat diterima dibandingkan nilai *maintainability*-nya, kecuali pada jalur pemrosesan data kritis (*hot path* skala mikrosekon).
* **Connection Pooling:** Boundary infrastruktur harus mengisolasi siklus hidup pooling koneksi database. Penggunaan pooling tidak boleh dikendalikan oleh use case individual.
* **Context Propagation:** Selalu propagasikan `context.Context` dari pintu masuk sistem (*ingress*) untuk menghentikan pemrosesan I/O yang sia-sia jika client membatalkan koneksi (*client disconnects*).

---

### 13. Trade-offs Analysis (Analisis Trade-off)

| Karakteristik | Desain Monolitik/Coupled | Desain Clean / Hexagonal Boundary |
| :--- | :--- | :--- |
| **Initial Velocity** | Sangat Tinggi (cepat di awal) | Rendah ke Moderat (butuh boilerplate) |
| **Cognitive Load** | Rendah saat codebase kecil | Tinggi di awal (banyak layer, mapper, & ports) |
| **Testability** | Buruk (butuh database nyata / mock berat) | Sangat Tinggi (isolasi unit test murni) |
| **Refactoring Cost** | Eksponensial seiring waktu | Konstan dan terprediksi |
| **Kesesuaian Masalah** | Script sederhana, CRUD dasar, prototype | Sistem enterprise berskala menengah-besar |

---

### 14. Security Implications (Implikasi Keamanan)
* **Untrusted Data Boundaries:** Batas terluar (Controller/Adapter) harus mengasumsikan seluruh payload adalah serangan potensial. Lakukan sanitasi tipe data dan batasi ukuran payload (*payload size limit*) sebelum melewati batas ke lapisan domain.
* **Invariant Enforcement:** Business logic tidak boleh mempercayai lapisan presentasi. Domain model harus memvalidasi integritasnya sendiri secara internal (*self-validating invariants*) untuk mencegah eksploitasi manipulasi parameter (*mass assignment attacks*).
* **Least Privilege Isolation:** Lapisan persistensi hanya boleh memiliki izin database (*database permissions*) yang relevan untuk operasinya; pemisahan adapter read/write (CQRS) mempertegas batas keamanan data.

---

### 15. Anti-Patterns & Pitfalls (Anti-Pola & Jebakan Desain)
* **Anemic Domain Model:** Domain entity hanya berisi *getter* dan *setter* tanpa behavior. Semua logika bisnis tercecer di use case atau *services*, mengubah arsitektur kembali menjadi prosedural.
* **Vendor Lock-in via Core Coupling:** Mengimpor modul database pihak ketiga (misal: AWS SDK, GORM) secara langsung ke dalam entity domain. Jika vendor database diganti, seluruh *core business logic* harus diubah dan diuji ulang.
* **Leaky Abstractions:** Pengecualian (*exceptions/errors*) dari framework infrastruktur (seperti `MongoTimeoutException`) lolos tanpa ditangkap dan diteruskan langsung ke client tanpa abstraksi domain error.

---

### 16. Testing & Verification Strategies (Strategi Pengujian & Verifikasi)

* **Unit Testing Domain murni:** Dijalankan tanpa I/O, database, atau mocking framework eksternal. Waktu eksekusi harus dalam orde milidetik.
* **Testing Lapisan Use Case:** Menggunakan in-memory fake repositories untuk menguji orkestrasi bisnis.

```go
// Unit test murni tanpa database mock library eksternal
func TestOrder_MarkPaid_PreventsDoublePayment(t *testing.T) {
	order := &Order{
		ID:     "ORD-001",
		Amount: 100.50,
		Status: StatusPaid,
	}

	err := order.MarkPaid()
	if err == nil {
		t.Fatalf("expected error when paying already paid order, got nil")
	}

	expectedErr := "order is already paid"
	if err.Error() != expectedErr {
		t.Errorf("expected '%s', got '%v'", expectedErr, err)
	}
}
```

* **Integration Testing:** Memverifikasi kontrak adapter infrastruktur dengan basis data nyata menggunakan ephemeral environment (seperti Testcontainers).
* **Architecture Compliance Testing:** Memanfaatkan linter (misalnya `depguard` atau `arch-go`) untuk menggagalkan fase CI/CD secara otomatis bila ada dependensi lapisan dalam yang merujuk lapisan luar.

---

### 17. Observability & Telemetry (Observabilitas & Telemetri)
* **Contextual Tracing:** Masukkan TraceID dan SpanID pada setiap batas layer. Span dimulai pada level HTTP Adapter dan diteruskan ke Use Case hingga ke Database Driver.
* **Domain Metrics:** Jangan hanya memantau metrik infrastruktur (CPU, Memory). Rekam metrik domain arsitektural:
  * Jumlah invariant rejection rates (mengindikasikan potensi bug pada client atau fraud).
  * Latensi use case bisnis versus latensi persistensi murni.
* **Structured Boundary Logging:** Log error pada boundary adapter dengan konteks lengkap (*error cause chain*), tetapi kirimkan pesan error yang aman tanpa detail internal (*sanitized error messages*) ke client.

---

### 18. Best Practices Checklist (Daftar Panduan Praktik Terbaik)
- [ ] Apakah domain entity sama sekali tidak mengimpor modul eksternal (zero 3rd-party non-standard library dependencies)?
- [ ] Apakah seluruh operasi I/O didefinisikan melalui *interfaces* (Ports)?
- [ ] Apakah arah dependensi selalu menuju ke dalam (menuju Core Business Logic)?
- [ ] Apakah setiap use-case hanya memiliki satu alasan untuk berubah (*Single Responsibility*)?
- [ ] Apakah context dengan batas timeout diaplikasikan pada setiap panggilan I/O jaringan?
- [ ] Apakah verifikasi aturan arsitektur diotomasi dalam pipeline CI/CD?

---

### 19. Practical Exercises / Labs (Latihan Praktik Mandiri)

#### Skenario Masalah
Sebuah platform *e-commerce* memiliki modul reservasi stok (*Inventory Allocation*). Implementasi saat ini menggabungkan eksekusi SQL langsung di dalam fungsi HTTP handler tanpa validasi entitas yang terpusat, menyebabkan insiden *overselling* saat promo flash sale akibat *race condition*.

#### Tugas Implementasi:
1. **Rancang Domain Entity:** Buat `InventoryItem` dengan batasan bahwa stok tidak boleh bernilai negatif saat dialokasikan.
2. **Definisikan Outbound Port:** Buat interface `InventoryRepository` yang mendukung operasi atomik atau optimistik (*optimistic locking / version check*).
3. **Bangun Application Service:** Buat use case `AllocateInventoryUseCase` yang mengorkestrasikan reservasi stok.
4. **Tulis Unit Test:** Buat unit test murni yang membuktikan bahwa reservasi stok yang melebihi kapasitas akan digagalkan oleh invariant domain tanpa memerlukan koneksi database aktif.

---

### 20. Summary & Knowledge Check (Rangkuman & Evaluasi Pemahaman)

#### Rangkuman Eksekutif
* Arsitektur adalah keputusan tentang hal-hal yang berdampak jangka panjang dan mahal untuk diubah; desain adalah penataan kode untuk memenuhi keputusan tersebut.
* *Architectural drivers* mendikte struktur; jangan biarkan infrastruktur (seperti framework atau jenis database) mendikte logika bisnis inti Anda.
* Mengisolasi domain melalui *interfaces* (Ports) dan *Dependency Inversion* membebaskan sistem dari ketergantungan teknologi (*future-proofing*) dan memungkinkan sistem diuji secara modular dan deterministik.

#### Uji Pemahaman:
1. **Mengapa implementasi ORM Entity (misal: entity class dengan tag bawaan DB) yang digunakan langsung sebagai domain logic dianggap sebagai pelanggaran batas arsitektural?**
2. **Sebutkan minimal tiga skenario di mana arsitektur *Clean / Hexagonal* justru menjadi *anti-pattern* dan membebani proyek!**
3. **Bagaimana cara menerapkan prinsip *Dependency Inversion* jika bahasa pemrograman yang Anda gunakan tidak memiliki dukungan antarmuka berbasis *structural typing*?**