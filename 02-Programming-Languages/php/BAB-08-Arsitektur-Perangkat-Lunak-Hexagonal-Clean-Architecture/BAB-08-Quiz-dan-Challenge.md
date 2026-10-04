# BAB 08: Quiz, Challenge, & Knowledge Check
**Arsitektur Perangkat Lunak: Hexagonal & Clean Architecture**

Dokumen evaluasi ini dirancang untuk menguji penguasaan arsitektural tingkat lanjut pada ekosistem PHP modern. Fokus pengujian mencakup dekonstruksi batas arsitektur, orkestrasi *Ports & Adapters*, preservasi kemurnian *Domain*, serta mitigasi kebocoran abstraksi infrastruktur pada sistem *enterprise*.

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Dependency Inversion Principle (DIP) dan Batas Arsitektural
Jelaskan secara matematis/konseptual bagaimana *Dependency Inversion Principle* (DIP) membalikkan arah dependensi antara *Domain Layer* dan *Infrastructure Layer* pada Clean Architecture. Mengapa antarmuka (*Port*) harus dimiliki (*owned*) dan didefinisikan oleh lapisan dalam (*Application/Domain*), bukan oleh lapisan luar (*Infrastructure*) yang mengimplementasikannya? Apa konsekuensinya terhadap *Stable Abstractions Principle* (SAP)?

### Soal 1.2: Driving vs. Driven Ports & Adapters
Dalam arsitektur Hexagonal (Alistair Cockburn), bedakan secara fundamental peran serta siklus eksekusi antara:
1. **Primary/Inbound (Driving) Ports & Adapters**
2. **Secondary/Outbound (Driven) Ports & Adapters**

Sertakan pemetaan konkret untuk kedua jenis port/adapter tersebut dalam konteks runtime PHP (misalnya: penanganan HTTP Request via FPM/Swoole versus pemanggilan database atau external API client).

### Soal 1.3: Entitas Domain vs. Entitas ORM (Active Record / Data Mapper)
Mengapa mencampur *Domain Entity* murni dengan *Active Record Model* (seperti Eloquent pada Laravel) atau memetakan anotasi basis data langsung ke *Domain Entity* (seperti atribut Doctrine ORM) dikategorikan sebagai pelanggaran batas arsitektur (*architectural boundary breach*)? Analisis dampaknya terhadap pengujian unit (*pure unit testing*) dan *framework lock-in*.

### Soal 1.4: Invariant Validation vs. Contextual/Input Validation
Jelaskan pemisahan tanggung jawab antara validasi input HTTP (misal: validasi tipe data string, email format pada Form Request) dengan penegakan *Business Invariant* pada *Rich Domain Model*. Di mana batas tegas letak eksekusi kedua validasi tersebut dalam Clean Architecture, dan apa dampaknya jika *Business Invariant* bocor ke *Application Services* atau *Controllers*?

### Soal 1.5: Peran Data Transfer Object (DTO) dan Anti-Corruption Layer (ACL)
Jelaskan risiko arsitektural jika sebuah *Application Service* (Use Case) mengembalikan representasi *Domain Entity* langsung ke *Presentation Layer* (Controller/CLI/API Responder). Bagaimana DTO dan mekanisme *Presenter/Transformer* memutus siklus kebocoran status internal entitas ke dunia luar?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Transaksi Basis Data Melintasi Batas Use Case (*Transaction Demarcation*)
Pada sistem murni berbasis Hexagonal, *Application Service* mengorkestrasi perubahan pada beberapa *Aggregates* yang harus bersifat atomik (*ACID*). Namun, antarmuka `PDO`, `EntityManagerInterface`, atau `DB::transaction()` berada di *Infrastructure*. Bagaimana Anda merancang kontrak abstraksi abstraksi transaksi (*Unit of Work* atau *TransactionManagerPort*) agar *Application Layer* dapat mengontrol batas *commit/rollback* tanpa mengimpor *class* atau konsep spesifik dari pustaka infrastruktur?

### Soal 2.2: Mitigasi ORM Lazy Loading & N+1 Problem pada Domain Boundary
Ketika *Domain Entity* dimodelkan terpisah dari ORM, pengambilan data relasional agregat kompleks sering kali menghadapi masalah *eager loading* yang terlalu rakus (*over-fetching*) atau eksekusi query tersembunyi (*implicit lazy loading*). Bagaimana Anda mendesain *Repository Port* dan implementasi *Hydration* di Adapter agar *Domain Entity* selalu berada dalam status valid dan lengkap tanpa mengekspos abstraksi query database (seperti `IQueryable` atau *query builders*) ke lapisan Domain?

### Soal 2.3: Masalah "Dual-Write" pada Domain Events
Pertimbangkan skenario di mana *Application Service* mengeksekusi `orderRepository->save(order)` kemudian memanggil `eventDispatcher->dispatch(new OrderPaidDomainEvent)`. Jika basis data berhasil melakukan `commit`, tetapi *message broker* (misal: RabbitMQ/Kafka) mengalami *network partition* saat dispatching, data sistem menjadi *inconsistent*. Jelaskan bagaimana pola *Transactional Outbox* diimplementasikan secara elegan dalam arsitektur Hexagonal untuk mengatasi problem ini tanpa mencemari Domain dengan logika konkurensi.

### Soal 2.4: Mengelola Siklus Hidup Dependency Injection pada Long-Running Process
Pada *runtime* modern PHP seperti RoadRunner, FrankenPHP, atau Swoole, *Worker* tidak me-reset memori antar *request*. Bagaimana Anda mencegah fenomena *state pollution* dan *memory leak* pada lapisan *Adapter* (misal: Adapter klien HTTP, *In-Memory Caches*, atau *Database Connection Pools*) yang diinjeksi ke dalam Use Case bertipe *Singleton* versus *Scoped/Transient Lifecycle*?

### Soal 2.5: Isolasi Framework Exception vs. Domain Exception
Sebuah *Infrastructure Adapter* (misal: `StripePaymentAdapter`) melempar exception pustaka vendor: `\Stripe\Exception\CardException: Card declined`. Bagaimana mekanisme pemetaan exception di *Adapter boundary* agar Use Case dan Domain tidak menangkap (*catch*) vendor exception tersebut secara eksplisit, melainkan menerima representasi *Domain/Application Exception* yang terpadu? Sertakan pola *Exception Translation* yang tepat.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Kegagalan Skalabilitas Akibat Kebocoran Abstraksi Eloquent
Sebuah platform *e-commerce enterprise* yang memproses 8.000 pesanan per menit saat *flash sale* mengalami lonjakan *latency* P99 dari 120ms menjadi 18.500ms, diiringi kehabisan memori (*OOM Crash*) pada *PHP-FPM worker pools*. 

**Investigasi Awal:**
Ditemukan bahwa tim pengembang menggunakan *Active Record* (Eloquent) langsung di dalam *Application Service*. Model `Order` memiliki relasi `OrderItems`, `Customer`, dan `ShippingAddress`. Kode Use Case:
```php
public function execute(string $orderId): OrderResponseDto
{
    $order = Order::with(['items', 'customer'])->findOrFail($orderId);
    $order->status = 'PROCESSING';
    $order->save();
    
    // Logika kalkulasi diskon yang memodifikasi relasi item di dalam looping
    foreach ($order->items as $item) {
        $item->applyDiscount($this->discountService->getFor($item));
        $item->save();
    }
    
    return OrderResponseDto::fromEloquent($order);
}
```
**Pertanyaan Diagnostik:**
1. Bedah titik-titik kritis kegagalan performa dan integritas yang disebabkan oleh ketiadaan batas *Aggregate Root* yang terisolasi.
2. Rancang ulang skenario di atas menggunakan prinsip *Clean Architecture*: definisikan antarmuka *Port*, rekonstruksi *Domain Aggregate*, dan jelaskan bagaimana *Repository Adapter* melakukan persistensi secara atomik dalam satu batch query teroptimasi.

---

### Skenario B: Race Condition dan Anomali Saldo pada Transaksi Finansial
Sebuah sistem *Core Banking* berbasis PHP mengalami diskrepansi audit saldo sebesar ratusan juta rupiah. Penyebab utamanya adalah fenomena *Lost Update* pada penarikan dana simultan melalui ATM dan Mobile Banking di detik yang sama.

**Kondisi Teknis Saat Ini:**
Use Case membaca saldo akun, memvalidasi aturan bisnis di memori, dan menyimpan entitas kembali:
```php
$account = $this->accountRepository->findById($accountId);
if (!$account->hasSufficientBalance($amount)) {
    throw new InsufficientBalanceException();
}
$account->withdraw($amount);
$this->accountRepository->save($account);
```
Pengembang mencoba menyelesaikan masalah ini dengan menambahkan anotasi `DB::beginTransaction()` langsung di dalam *Controller*, yang kemudian memicu *database lock contention* masif dan *connection pool exhaustion*.

**Pertanyaan Diagnostik:**
1. Mengapa penempatan *locking/transaction* di Controller melanggar *Separation of Concerns* dan justru memperburuk skenario konkurensi?
2. Bagaimana Anda menerapkan *Optimistic Concurrency Control* (menggunakan versi aggregate/ETag) atau *Pessimistic Locking* murni melalui *Repository Port* di *Application Layer* tanpa membocorkan sintaks SQL `FOR UPDATE` ke dalam *Domain Logic*? Tuliskan pseudo-arsitektur implementasinya.

---

### Skenario C: Over-Engineering dan Paralisis Arsitektural pada Sistem B2B
Sebuah startup B2B logistik tahap awal mengimplementasikan arsitektur *Clean Architecture* secara dogmatis. Untuk sebuah entitas sederhana berkategori CRUD (*Warehouse Location*), tim pengembang membuat:
- 1 Domain Entity
- 4 Value Objects
- 2 Inbound Ports
- 2 Outbound Ports
- 4 DTOs (Request, Response, Command, Query)
- 3 Mappers terpisah
- 1 Controller, 1 Application Service, 2 Adapter (Database & Cache)

Dampaknya, waktu pengembangan fitur baru melambat 400%, penggunaan memori PHP-FPM membengkak karena ribuan pemanggilan *dynamic allocation* objek kecil, dan tim junior kebingungan menavigasi kode (*indirection hell*).

**Pertanyaan Diagnostik:**
1. Sebagai *Principal Architect*, di mana Anda menarik garis batas antara komponen sistem yang mutlak membutuhkan *Rich Domain + Hexagonal Isolation* versus komponen yang cukup menggunakan pola *Pragmatic CQRS* atau *Transaction Script*?
2. Bagaimana Anda merestrukturisasi sistem tersebut dengan konsep *Strategic DDD (Core Domain vs. Supporting/Generic Subdomains)* agar arsitektur tetap bersih tanpa mengorbankan kecepatan rilis (*developer velocity*) dan efisiensi eksekusi PHP?

---

## 4. Chapter Challenge

### Tantangan Praktis: Engine Pembayaran & Settlement Multi-Gateway Berbasis Hexagonal Murni

#### Deskripsi Masalah
Sebuah platform SaaS global membutuhkan subsistem penagihan (*Billing & Settlement Engine*) yang tangguh. Subsistem ini harus mampu berganti-ganti gateway pembayaran (*Stripe*, *Midtrans*, dan *Adyen*) secara dinamis berdasarkan mata uang dan tingkat kegagalan gateway, mengeksekusi penagihan secara idempoten, mencatat mutasi ke buku besar (*Ledger*), serta menerbitkan *Domain Events* untuk keperluan notifikasi tanpa bergantung pada framework manapun.

#### Persyaratan Arsitektural (Requirements)
1. **Domain Layer (Zero Dependencies):**
   - Bangun *Aggregate Root* `SubscriptionPayment` dengan state machine yang valid (`Draft`, `Processing`, `Settled`, `Failed`).
   - Implementasikan *Value Objects*: `Money` (presisi tinggi via `bcmath`), `Currency`, dan `PaymentMethodId`.
   - Bangun *Domain Invariant*: Pembayaran tidak boleh berstatus `Settled` jika nominal yang diterima gateway tidak sama persis dengan tagihan; status tidak boleh mundur ke fase sebelumnya.
   - Entitas menghasilkan *Domain Event*: `PaymentSettledDomainEvent`.
2. **Application Layer (Use Cases & Ports):**
   - Buat *Inbound Port* (Command): `SettlePaymentUseCase` beserta DTO input/output yang *immutable*.
   - Definisikan *Outbound Ports*:
     - `PaymentRepositoryPort`: Operasi persistensi aggregate.
     - `PaymentGatewayPort`: Kontrak transaksi ke eksternal vendor.
     - `OutboxEventRepositoryPort`: Kontrak persistensi domain event untuk pola transactional outbox.
     - `TransactionManagerPort`: Abstraksi atomisitas operasi.
3. **Infrastructure Layer (Adapters):**
   - Implementasikan Adapter mock untuk `StripePaymentGatewayAdapter` dan `MidtransPaymentGatewayAdapter`.
   - Implementasikan `InMemoryPaymentRepositoryAdapter` yang mematuhi kontrak persistence port.
   - Implementasikan `PdoTransactionManagerAdapter` (atau simulasi murni) yang mengelola siklus transaksi database.
4. **Presentation Layer (Primary Adapter):**
   - Bangun sebuah simulasi CLI/HTTP Controller yang menerima request payload, memvalidasi input transport, memetakan ke Command DTO, memanggil *Application Service*, dan merender JSON Response.

#### Batasan Teknis (Constraints)
- **PHP 8.3+**: Wajib menggunakan `strict_types=1`, *readonly properties/classes*, *enums*, dan *named arguments*.
- **Kemurnian Domain & Aplikasi**: Folder `src/Domain` dan `src/Application` **DILARANG KERAS** mengimpor pustaka eksternal (tidak ada namespace pihak ketiga, termasuk Laravel, Symfony, Doctrine, Guzzle, dsb). Hanya fungsi native PHP dan ekstensi `ext-bcmath` yang diizinkan.
- Domain Event tidak boleh langsung memanggil antarmuka jaringan I/O di dalam siklus eksekusi use case.

#### Output yang Diharapkan
1. **Diagram/Struktur Direktori**: Menampilkan isolasi boundary folder arsitektur.
2. **Kode Sumber Inti**:
   - `SubscriptionPayment` (Aggregate Root)
   - `SettlePaymentUseCase` (Application Service)
   - Seluruh interfaces/ports yang relevan
   - Implementasi salah satu Gateway Adapter
   - Implementasi pola Transactional Outbox pada tahap akhir use case
3. **Unit Test Murni**: Tunjukkan sebuah test suite untuk `SettlePaymentUseCase` menggunakan *Mock/Stub In-Memory Adapters* tanpa mem-booting basis data atau HTTP client sama sekali.

---

## 5. Knowledge Check & Checklist

Konfirmasi penguasaan materi arsitektur Anda dengan memeriksa daftar kemampuan teknis berikut:

### Saya harus memahami:
- [ ] Aturan Ketergantungan (*The Dependency Rule*): dependensi kode sumber hanya boleh mengarah ke dalam, menuju abstraksi level yang lebih tinggi.
- [ ] Perbedaan esensial antara arsitektur berlapis tradisional (*N-Tier Layered Architecture*) yang berpusat pada Database, dengan *Hexagonal Architecture* yang menempatkan Database sebagai *detail implementasi* di luar core.
- [ ] Konsep kepemilikan antarmuka (*Interface Ownership*): mengapa caller/client yang harus mendefinisikan port, bukan implementor.
- [ ] Batas tanggung jawab antara *Aggregate Root*, *Entity*, *Value Object*, dan *Domain Service*.
- [ ] Dampak buruk dari kebocoran primitif basis data (*leaky database abstractions*) seperti model Active Record terhadap biaya pemeliharaan sistem jangka panjang.
- [ ] Perbedaan antara *Synchronous In-Process Events* dan *Asynchronous Distributed Events (Transactional Outbox)*.

### Saya tidak perlu menghafal:
- [ ] Sintaks konfigurasi dependensi spesifik dari framework (misal: penulisan berkas `services.yaml` di Symfony atau `AppServiceProvider` di Laravel) selama memahami konsep *Inversion of Control Container*.
- [ ] Kode implementasi library pihak ketiga untuk event broker (misal: signature fungsi internal klien Kafka atau AWS SNS SDK).
- [ ] Seluruh anotasi/metadata ORM Doctrine/Eloquent; cukup pahami mekanisme pemetaan data (*Data Mapper pattern*).

### Saya harus bisa melakukan:
- [ ] Memisahkan sistem monolitik PHP yang terikat ketat pada framework menjadi komponen Domain, Application, dan Infrastructure independen.
- [ ] Merancang antarmuka *Port* yang ekspresif secara bisnis tanpa terpengaruh batasan teknis API pihak ketiga atau skema tabel SQL.
- [ ] Menulis tes unit domain dan use case yang berjalan ultra-cepat (< 10ms per test file) tanpa koneksi I/O jaringan maupun disk basis data.
- [ ] Mengimplementasikan *Data Mapper* kustom untuk mengonversi data mentah PDO/SQL menjadi *Rich Domain Entity* tanpa memanggil constructor yang merusak status invariant.
- [ ] Mengisolasi penanganan transaksi ACID melalui abstraksi *Transaction Manager* pada *Application Boundary*.