# Kurikulum Enterprise Rekayasa Perangkat Lunak: Ruby on Rails
## Bab 03: Data Modeling & Active Record Mastery
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik pada tingkat Software Architect / Principal Engineer diharapkan mampu:
- **Menganalisis dan Membedah Internal Active Record Engine:** Memahami siklus hidup kueri dari AST Arel (*Abstract Syntax Tree*), *Connection Pooling*, hingga *Type Casting* dan instansiasi objek Ruby.
- **Mengorkestrasi Arsitektur Database Kompleks:** Mengimplementasikan pola *Delegated Types* sebagai pengganti modern *Single Table Inheritance* (STI) guna menghindari *anti-pattern sparse table*.
- **Mengoptimalkan Kinerja Pembacaan dan Penulisan Skala Tinggi:** Menerapkan strategi *eager loading* tingkat lanjut (`preload`, `eager_load`, `includes`), eliminasi N+1 secara terprogram via `strict_loading`, dan query paralel non-blocking (`load_async`).
- **Menguasai Mekanisme Concurrency & Locking Terdistribusi:** Mengimplementasikan *Optimistic Locking* (`lock_version`) dan *Pessimistic Locking* (`SELECT FOR UPDATE NOWAIT / SKIP LOCKED`) untuk mitigasi *race conditions* pada transaksi finansial dan reservasi inventaris.
- **Mendesain Arsitektur Multi-Database Tingkat Lanjut:** Mengonfigurasi *Automatic Role Switching* (Primary/Replica) serta partisi horizontal (*sharding*) bawaan Rails secara modular dan transaksional aman.

---

### 2. Prerequisites
Sebelum mendalami modul ini, peserta wajib menguasai:
- Pengetahuan solid mengenai sintaksis Ruby lanjutan: *Metaprogramming*, blok/procs/lambdas, dan model memori Ruby MRI (GIL, *Object Allocation*).
- Pemahaman Active Record Dasar: Migrasi, validasi standar, asosiasi relasional dasar (`belongs_to`, `has_many`), dan operasi CRUD.
- Fondasi Database Relasional (PostgreSQL): Konsep ACID, tingkat isolasi transaksi (*Read Committed*, *Repeatable Read*, *Serializable*), struktur indeks (B-Tree, Partial, Composite), dan analisis *Execution Plan* (`EXPLAIN ANALYZE`).

---

### 3. Concept & Internal Architecture

Active Record bukan sekadar lapisan *Object-Relational Mapping* (ORM) deklaratif; ia merupakan *engine* kompilasi SQL canggih yang bekerja di atas tiga subsistem utama:

```
[ Active Record Model (Domain Layer) ]
                   │
                   ▼
       [ Arel AST Engine (IR) ]
                   │ (Visitor Pattern)
                   ▼
  [ Database Adapter (PG, MySQL, etc.) ]
                   │
                   ▼
   [ Connection Pool Management ]
                   │
                   ▼
          [ Database Engine ]
```

#### 3.1 Arel: The Abstract Syntax Tree (AST) Engine
Setiap kali Anda memanggil *query interface* seperti `User.where(active: true)`, Active Record tidak memformat teks SQL secara langsung. Rails membentuk struktur data pohon sintaksis bernama **Arel** (*A Relational Algebra*).
- **Nodes:** Setiap klausa SQL direpresentasikan sebagai node (`Arel::Nodes::Equality`, `Arel::Nodes::SelectStatement`, `Arel::Nodes::Binary`).
- **Visitors:** Adapter basis data (misal: PostgreSQL Adapter) menggunakan *Visitor Pattern* (`Arel::Visitors::PostgreSQL`) untuk menelusuri AST dan mengompilasinya menjadi dialek SQL mentah yang spesifik untuk target basis data.
- **Keunggulan:** Memungkinkan manipulasi query relasional yang *composable*, *type-safe*, dan kebal terhadap *SQL Injection* secara struktural sebelum dialirkan ke koneksi TCP.

#### 3.2 Query Life-Cycle & Instantiation Overhead
Siklus eksekusi pembacaan data Active Record:
1. **Compilation:** `ActiveRecord::Relation` mengompilasi Arel AST menjadi string SQL.
2. **Checkout Connection:** Thread meminta koneksi dari `ActiveRecord::ConnectionAdapters::ConnectionPool`.
3. **Execution:** Socket TCP mengirimkan kueri ke server DB; PGclient membaca *raw byte stream*.
4. **Type Casting:** Adapter memetakan OID tipe data PostgreSQL (misal: `timestamp`, `jsonb`, `uuid`) ke kelas objek Ruby (`ActiveSupport::TimeWithZone`, `Hash`, dsb.) melalui modul `ActiveModel::Type`.
5. **Model Instantiation:** Untuk setiap baris (*tuple*), Active Record memanggil `.allocate` dan `init_with_attributes`, mengalokasikan memori untuk *Dirty Tracking* (`ActiveModel::Dirty`) dan state persistensi.

> **Peringatan Skalabilitas:** Mengambil 100.000 baris record via Active Record akan mengalokasikan jutaan objek Ruby di heap memori, memicu *Garbage Collection (GC) pauses*. Untuk pembacaan massal (*read-only*), gunakan pluck atau streaming.

#### 3.3 Connection Pooling & Multi-Threading Architecture
Secara default, Rails menggunakan server multithreaded (Puma). `ConnectionPool` mengelola array thread-safe yang berisi objek koneksi basis data.
- Ukuran pool (`pool: ENV.fetch("RAILS_MAX_THREADS")`) harus sinkron dengan jumlah thread worker Puma.
- Jika thread mencoba melakukan kueri sementara semua koneksi sedang digunakan (*busy*), thread akan diblokir selama durasi `checkout_timeout` sebelum memunculkan galat `ActiveRecord::ConnectionTimeoutError`.

#### 3.4 Delegated Types vs Single Table Inheritance (STI)
- **STI:** Menyimpan semua hierarki kelas dalam satu tabel dengan kolom `type`.
  *Kelemahan:* Pelanggaran normalisasi database (banyak kolom `NULL`), ukuran baris tabel membengkak (*row bloat*), dan hilangnya integritas constraint database (`NOT NULL` tidak bisa dipasang pada field spesifik subkelas).
- **Delegated Types (Rails 6.1+):** Mengadopsi pola *composition-over-inheritance*. Disediakan tabel *superklass* (menyimpan data umum, metadata, routing) yang mereferensikan tabel konkret tersendiri via relasi polimorfik formal. Tidak ada kolom *sparse/null*, integritas basis data terjaga penuh, dan konkurensi I/O terdistribusi.

---

### 4. Why & What

| Dimensi | Pendekatan Naif / Tradisional | Pendekatan Enterprise Modern |
| :--- | :--- | :--- |
| **Pola Inheritance** | Single Table Inheritance (STI) dengan puluhan kolom `NULL`. | **Delegated Types** dengan tabel terpartisi secara ternormalisasi. |
| **Pencegahan N+1** | Audit visual manual atau menunggu laporan log produksi. | **Strict Loading Enforcement** (`strict_loading!`) di tingkat runtime dan testing. |
| **Mitigasi Race Conditions** | Mengandalkan validasi memori aplikasi (`validates_uniqueness_of`). | **Pessimistic DB Locks** (`FOR UPDATE NOWAIT`) dan *Database Unique Index Constraints*. |
| **Data Fetching Massal** | `.all.each` (Memory exhaustion) atau `.find_each` standar. | **Cursor-based pagination**, streaming kueri, dan `load_async` non-blocking. |
| **Routing Kueri** | Skema satu database untuk seluruh operasional. | **Multi-DB Architecture** (Primary/Replica Split dengan *automatic lag-tolerant switching*). |

---

### 5. How (Workflow Detail)

Alur perancangan akses data tingkat lanjut mengikuti metodologi berikut:

```
[ Domain Modeling: Evaluasi Kompleksitas Polimorfisme ]
  ├── Jika shared table > 30% sparse columns ──> Terapkan Delegated Types
  └── Terapkan Validasi Transaksional & State Isolation
         │
         ▼
[ Konfigurasi Multi-Database & Connection Layer ]
  ├── database.yml: Konfigurasi Primary (Writer) & Replica (Reader)
  └── Model Base: connects_to database: { writing: :primary, reading: :replica }
         │
         ▼
[ Penulisan Query Interface & Arel Nodes ]
  ├── Definisikan Relasi Terkomposisi (Scopes via Arel)
  └── Proteksi N+1 via strict_loading(:n_plus_one_only)
         │
         ▼
[ Orkestrasi Transaksi & Locking Execution ]
  ├── Mulai transaksi dengan tingkat isolasi terdefinisi
  ├── Eksekusi `SELECT FOR UPDATE` dengan batas timeout
  └── Trigger eksekusi side-effects HANYA di `after_commit`
```

---

### 6. Analogy & Diagram ASCII

#### 6.1 Analogi Pemrosesan Kueri: Arel & Factory Pipeline
Bayangkan Active Record sebagai manajer pesanan furnitur. 
- Anda tidak langsung memotong kayu saat pelanggan memesan (Lazy Evaluation).
- Anda menggambar cetak biru modular (*AST Arel*). Jika pelanggan menambahkan "warna merah" dan "kaki besi", Anda hanya menambahkan catatan ke cetak biru tanpa membuat material fisik.
- Cetak biru tersebut kemudian diserahkan kepada perakit lokal (*PostgreSQL Adapter Visitor*) yang menerjemahkan cetak biru menjadi instruksi mesin bubut spesifik (*Raw SQL*). 
- Kayu yang selesai dipotong dikemas ke wadah terstandarisasi (*Active Record Instantiated Models*).

#### 6.2 Visualisasi Arsitektur: Delegated Types vs Multi-DB Switching

```
                 [ Incoming Application Request ]
                                │
               [ ActiveRecord Context Switching ]
               /                                \
    (Write Operations)                   (Read Operations)
            │                                    │
            ▼                                    ▼
    [ Primary Database ]                [ Read Replica ]
     (WAL Replication) ─────────────────────────>│
            │
  ┌─────────┴─────────────────────────────────┐
  │  Delegated Type: Payment                  │
  │  id: uuid                                 │
  │  amount: decimal                          │
  │  paymentable_type: "CreditCardPayment"    │
  │  paymentable_id: uuid                     │
  └─────────┬─────────────────────────────────┘
            │ 1:1 Concrete Relation
      ┌─────┴─────────────────────────┐
      ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│ CreditCardPayment (Table) │   │ CryptoPayment (Table)     │
│ card_last4: string        │   │ tx_hash: string           │
│ gateway_ref: string       │   │ network_confirmations: int│
└───────────────────────────┘   └───────────────────────────┘
```

---

### 7. Code Implementations

#### 7.1 Simple Example: Membangun Dynamic Complex Scope Menggunakan Arel Mentah
Menembus batas Active Record query DSL standar dengan memanipulasi AST Arel secara langsung untuk perbandingan berbasis fungsi matematis/vektor.

```ruby
# app/models/product.rb
class Product < ApplicationRecord
  # Pencarian produk berdasarkan algoritma diskon dinamis yang kompleks
  # SQL: WHERE (price - (price * discount_percentage / 100)) <= :max_budget
  scope :affordable_under, ->(budget) {
    products_table = arel_table

    price_col = products_table[:price]
    discount_col = products_table[:discount_percentage]

    # Membangun node perkalian: (price * discount_percentage)
    discount_amount = Arel::Nodes::Multiplication.new(price_col, discount_col)
    
    # Membangun node pembagian: discount_amount / 100
    actual_discount = Arel::Nodes::Division.new(discount_amount, Arel::Nodes.build_quoted(100))
    
    # Membangun node pengurangan: price - actual_discount
    final_price = Arel::Nodes::Subtraction.new(price_col, actual_discount)

    # Membangun node komparasi: final_price <= budget
    where(Arel::Nodes::LessThanOrEqual.new(final_price, Arel::Nodes.build_quoted(budget)))
  }
end
```

#### 7.2 Practical Enterprise Example: Delegated Types, Strict Loading, & Concurrency Lock
Membangun infrastruktur mutasi dompet digital (*Ledger Engine*) kelas perbankan yang tahan terhadap *race conditions*, bebas N+1, dan menggunakan *Delegated Types*.

```ruby
# db/migrate/20260330000001_create_ledger_system.rb
class CreateLedgerSystem < ActiveRecord::Migration[7.1]
  def change
    create_table :wallets, id: :uuid do |t|
      t.references :user, null: false, foreign_key: true, type: :uuid
      t.decimal :balance, precision: 18, scale: 4, default: 0.0, null: false
      t.integer :lock_version, default: 0, null: false # Optimistic locking fallback
      t.timestamps
    end

    create_table :ledger_entries, id: :uuid do |t|
      t.references :wallet, null: false, foreign_key: true, type: :uuid
      t.decimal :amount, precision: 18, scale: 4, null: false
      t.string :entryable_type, null: false
      t.uuid :entryable_id, null: false
      t.timestamps
    end
    add_index :ledger_entries, [:entryable_type, :entryable_id], unique: true

    create_table :transfer_entries, id: :uuid do |t|
      t.uuid :recipient_wallet_id, null: false
      t.string :tracking_code, null: false, index: { unique: true }
    end

    create_table :merchant_payment_entries, id: :uuid do |t|
      t.string :merchant_id, null: false
      t.decimal :tax_deduction, precision: 10, scale: 4, default: 0.0
    end
  end
end
```

```ruby
# app/models/ledger_entry.rb
class LedgerEntry < ApplicationRecord
  # Implementasi DELEGATED TYPES
  delegated_type :entryable, types: %w[TransferEntry MerchantPaymentEntry], dependent: :destroy

  belongs_to :wallet

  validates :amount, presence: true, numericality: { other_than: 0 }
end

# app/models/concerns/entryable.rb
module Entryable
  extend ActiveSupport::Concern

  included do
    has_one :ledger_entry, as: :entryable, touch: true
    has_one :wallet, through: :ledger_entry
  end
end

# app/models/transfer_entry.rb
class TransferEntry < ApplicationRecord
  include Entryable
  validates :recipient_wallet_id, :tracking_code, presence: true
end

# app/models/merchant_payment_entry.rb
class MerchantPaymentEntry < ApplicationRecord
  include Entryable
  validates :merchant_id, presence: true
end
```

```ruby
# app/services/wallet_settlement_service.rb
class WalletSettlementService
  class InsufficientFundsError < StandardError; end
  class ConcurrencyConflictError < StandardError; end

  def initialize(wallet_id:, amount:, entryable_attributes:)
    @wallet_id = wallet_id
    @amount = BigDecimal(amount.to_s)
    @entryable_attributes = entryable_attributes
  end

  def execute!
    # Mengisolasi eksekusi dengan Pessimistic Locking tingkat baris
    ApplicationRecord.transaction(isolation: :read_committed) do
      # SELECT * FROM wallets WHERE id = ? FOR UPDATE
      wallet = Wallet.lock("FOR UPDATE NOWAIT").find(@wallet_id)

      new_balance = wallet.balance + @amount
      if new_balance.negative?
        raise InsufficientFundsError, "Saldo tidak mencukupi untuk pemotongan buku besar."
      end

      # 1. Update wallet balance
      wallet.update!(balance: new_balance)

      # 2. Polymorphic entry generation via Delegated Types
      entry = wallet.ledger_entries.build(
        amount: @amount,
        entryable: build_concrete_entry
      )
      entry.save!

      # Event dipicu HANYA jika transaksi komit secara fisik ke disk DB
      execute_after_commit_actions(wallet, entry)
      
      entry
    end
  rescue ActiveRecord::LockWaitTimeout, PG::LockNotAvailable => e
    # Mengubah database exception menjadi domain-specific error
    raise ConcurrencyConflictError, "Terjadi konflik transaksi paralel. Coba lagi beberapa saat."
  end

  private

  def build_concrete_entry
    case @entryable_attributes[:type]
    when "Transfer"
      TransferEntry.new(@entryable_attributes.except(:type))
    when "Merchant"
      MerchantPaymentEntry.new(@entryable_attributes.except(:type))
    else
      raise ArgumentError, "Tipe entri mutasi buku besar tidak valid."
    end
  end

  def execute_after_commit_actions(wallet, entry)
    ActiveRecord::Base.connection.after_commit do
      # Non-blocking telemetry or async Sidekiq dispatch
      MetricsPublisher.emit_balance_changed(wallet_id: wallet.id, delta: @amount)
    end
  end
end
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Kasus: Flash Sale E-Commerce Tier-1 (Black Friday Event)
- **Kondisi:** Sistem penjualan mengalami lonjakan hingga 85.000 Request Per Second (RPS) pada 10 item promosi flash-sale.
- **Masalah:** Terjadi *overselling* (stok minus), database primary mengalami kegagalan *thread pool exhaustion* akibat *lock contention* tinggi pada kueri `UPDATE inventory SET stock = stock - 1 WHERE id = ?`, dan latensi API meningkat dari 20ms menjadi 18.000ms.
- **Solusi Arsitektural Menggunakan Active Record:**
  1. **Read-Replica Offloading:** Kueri ketersediaan stok umum dialihkan ke node Read-Replica dengan perlindungan lag menggunakan `ActiveRecord::Base.connected_to(role: :reading)`.
  2. **Inventory Partitioning via Arel Batch Allocation:** Stok tidak disimpan dalam satu baris global, melainkan dipecah ke 10 bucket independen (`stock_buckets`).
  3. **Non-blocking Locks:** Menggunakan `lock("FOR UPDATE SKIP LOCKED")` untuk memilih bucket yang tidak sedang dikunci oleh proses background lain.

```ruby
# app/models/inventory_bucket.rb
class InventoryBucket < ApplicationRecord
  belongs_to :product

  # Mengambil 1 unit stok secara non-blocking
  def self.reserve_stock!(product_id, quantity = 1)
    # Memilih bucket pertama yang tidak terkunci oleh thread lain
    # SELECT * FROM inventory_buckets 
    # WHERE product_id = ? AND remaining_stock >= ? 
    # ORDER BY id ASC LIMIT 1 FOR UPDATE SKIP LOCKED
    bucket = where(product_id: product_id)
             .where("remaining_stock >= ?", quantity)
             .order(:id)
             .lock("FOR UPDATE SKIP LOCKED")
             .first

    raise OutOfStockError, "Seluruh slot inventaris sedang diproses atau habis." unless bucket

    bucket.decrement!(:remaining_stock, quantity)
    bucket
  end
end
```

- **Dampak Implementasi:**
  - *Zero Overselling* (Akurasi konsistensi 100%).
  - Penghapusan total fenomena *Lock Wait Timeouts*.
  - Latensi checkout transaksi p99 turun drastis ke 85 milidetik.

---

### 9. Trade-offs

| Aspek | Pilihan A | Pilihan B | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Locking Strategy** | *Optimistic Locking* (`lock_version`) | *Pessimistic Locking* (`FOR UPDATE`) | Optimistic lebih cepat pada kueri rendah konflik; gagal keras (*frequent rollbacks*) pada high-concurrency write hotspot. Pessimistic memblokir antrean koneksi, namun menjamin eksekusi sekuensial deterministik. |
| **Eager Loading** | `.preload` (Separate Queries) | `.eager_load` (`LEFT OUTER JOIN`) | `.preload` mencegah duplikasi data memori hasil join yang besar, namun tidak bisa memfilter klausa `WHERE` pada tabel asosiasi. `.eager_load` menghasilkan satu query raksasa, menghemat roundtrip DB tetapi menaikkan CPU overhead deserialisasi di Ruby. |
| **Pola Asosiasi** | Single Table Inheritance (STI) | Delegated Types | STI menyederhanakan kueri satu tabel tanpa `JOIN`, namun merusak integritas skema (ratusan kolom null). Delegated types menuntut ekstra `INNER JOIN`, namun menormalisasi basis data secara optimal. |
| **Evaluasi Kueri** | `.load_async` | Evaluasi Standar Sekuensial | `.load_async` memotong wall-clock time I/O dengan thread parallel, namun menghabiskan kapasitas *Connection Pool* secara agresif. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Memanggil Side-Effects / HTTP Request di Dalam Transaksi Database
- **Kesalahan:** Memanggil API pihak ketiga (misal: Stripe / Midtrans) di dalam blok `ActiveRecord::Base.transaction`.
- **Dampak Fatal:** Koneksi basis data tetap tertahan (*idle in transaction*) selama durasi network call (bisa 2–5 detik). Hal ini memicu *connection pool exhaustion* dan melumpuhkan seluruh aplikasi.
- **Remediasi:** Pastikan blok transaksi sesingkat mungkin dan alihkan eksekusi network call ke *post-commit hook* (`after_commit` callback atau *Transactional Outbox Pattern*).

#### 10.2 Jebakan `.find_each` dengan `.order(...)` Kustom
- **Kesalahan:** Menjalankan `User.order(:created_at).find_each { ... }`.
- **Dampak Fatal:** Active Record mengabaikan klausa `order` kustom Anda secara diam-diam dan menimpanya dengan urutan `ORDER BY id ASC`. Jika primary key bukan tipe sekuensial (misal: random UUIDv4), *batching* akan melompat secara kacau dan menghasilkan data duplikat atau terlewat.
- **Remediasi:** Gunakan *Cursor-based pagination* menggunakan Arel atau pastikan UUID menggunakan format terurut waktu seperti *UUIDv7*.

#### 10.3 Inconsistent Locking Order (Deadlock Generation)
- **Kesalahan:** 
  Thread A: Mengunci Akun 1, kemudian mengunci Akun 2.
  Thread B: Mengunci Akun 2, kemudian mengunci Akun 1.
- **Dampak Fatal:** Terjadi **Deadlock**. PostgreSQL mendeteksi siklus ketergantungan dan menghentikan salah satu thread secara paksa (`PG::TRDeadlockDetected`).
- **Remediasi:** Selalu lakukan sorting deterministik terhadap ID sumber daya sebelum melakukan penguncian:

```ruby
# Safe Locking Pattern
account_ids = [sender_id, recipient_id].sort
accounts = Account.where(id: account_ids).order(:id).lock("FOR UPDATE")
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Aktifkan Strict Loading Terstandarisasi:** Terapkan `self.strict_loading_by_default = true` pada model inti transaksi guna mencegah kemunculan N+1 query yang tidak terdeteksi.
- [ ] **Rasio Connection Pool Seimbang:** Set ukuran pool: `POOL_SIZE = (WEB_CONCURRENCY * RAILS_MAX_THREADS) + SIDEKIQ_CONCURRENCY + 2`.
- [ ] **Hindari Implicit Callback Re-entrance:** Jangan pernah memanggil `.save` atau `.update` pada instance yang sama di dalam callback `after_save` atau `after_update` (bisa memicu infinite loop).
- [ ] **Set Database Timeouts Secara Rigor:** Konfigurasi batas waktu di `database.yml`:
  ```yaml
  production:
    variables:
      statement_timeout: 5000 # 5 detik maksimal eksekusi kueri
      lock_timeout: 2000      # 2 detik batas antrean kunci DB
  ```
- [ ] **Indeks Foreign Keys Secara Menyeluruh:** Validasi bahwa seluruh asosiasi relasional memiliki indeks B-Tree struktural di level basis data melalui gem pendeteksi skema (`lol_dba` atau `database_consistency`).

---

### 12. Hands-on Practice: Membangun High-Scale Subledger Engine

Simpan seluruh hasil latihan berikut di direktori direktori kerja: `hands-on/m02/`

#### Langkah 1: Setup Proyek & Engine Sandboxing
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
rails new subledger_engine --database=postgresql --api -T
cd subledger_engine
```

#### Langkah 2: Konfigurasi Multi-Database
Buka file `config/database.yml` dan implementasikan routing primary serta replica:

```yaml
default: &default
  adapter: postgresql
  encoding: unicode
  pool: <%= ENV.fetch("RAILS_MAX_THREADS") { 5 } %>
  timeout: 5000

development:
  primary:
    <<: *default
    database: subledger_engine_development
  primary_replica:
    <<: *default
    database: subledger_engine_development
    replica: true
```

#### Langkah 3: Definisikan Model Koneksi Dasar
Buka `app/models/application_record.rb`:

```ruby
class ApplicationRecord < ActiveRecord::Base
  primary_abstract_class

  # Menghubungkan peran baca dan tulis
  connects_to database: { writing: :primary, reading: :primary_replica }

  # Menerapkan proteksi N+1 pada level fundamental
  self.strict_loading_by_default = true
end
```

#### Langkah 4: Implementasikan Migrasi & Delegated Types
Buat migrasi untuk skema Order dan Event Settlement:
```bash
bin/rails g migration CreateOrdersAndSettlements
```

Isi file migrasi:
```ruby
class CreateOrdersAndSettlements < ActiveRecord::Migration[7.1]
  def change
    create_table :orders, id: :uuid do |t|
      t.decimal :total_amount, precision: 12, scale: 2, null: false
      t.string :status, default: "pending", null: false
      t.timestamps
    end

    create_table :settlement_records, id: :uuid do |t|
      t.references :order, null: false, foreign_key: true, type: :uuid
      t.string :settleable_type, null: false
      t.uuid :settleable_id, null: false
      t.timestamps
    end

    create_table :crypto_settlements, id: :uuid do |t|
      t.string :network, null: false
      t.string :transaction_hash, null: false
    end

    create_table :fiat_settlements, id: :uuid do |t|
      t.string :bank_reference, null: false
      t.string :clearing_code, null: false
    end
  end
end
```
Jalankan migrasi:
```bash
bin/rails db:create && bin/rails db:migrate
```

---

### 13. Exercises

#### 13.1 Level: Easy
Buat model `Order` dan scope bernama `.high_value_recent` yang mengombinasikan dua kondisi: bernilai lebih dari Rp 10.000.000 dan dibuat dalam 24 jam terakhir. Gunakan Arel Nodes untuk menyusun klausul tanggal secara eksplisit tanpa interpolasi string SQL.

#### 13.2 Level: Medium
Tulis sebuah Service Object bernama `AccountRebalanceService` yang menerima parameter `source_account_id`, `destination_account_id`, dan `amount`. Terapkan *Pessimistic Locking* dengan mekanisme *Sorting Array ID* deterministik untuk mencegah terjadinya kondisi deadlock database saat dua proses mencoba mentransfer dana silang secara simultan.

#### 13.3 Level: Hard
Rancang dan implementasikan sebuah *Cursor-based Pagination Concern* berbasis Arel (`app/models/concerns/cursor_paginatable.rb`) yang tidak mengandalkan SQL `OFFSET`. Concern harus mendukung multi-column sorting (contoh: `[created_at: :desc, id: :desc]`) menggunakan perbandingan baris tupel Arel (*Tuple Comparison* / `Arel::Nodes::Grouping`) untuk memastikan performa query pagination stabil ($O(1)$) pada volume tabel di atas 50 juta baris data.

---

### 14. Real-World Challenge

**Konteks Tantangan:** 
Sebuah platform perbankan digital mengalami insiden kritis: terjadi duplikasi pencairan dana pinjaman instan sebesar miliaran rupiah pada event pencairan massal. Setelah investigasi, ditemukan adanya *Double-Submit* dari sisi gateway nasabah yang menembus lapisan aplikasi dalam interval 15 milidetik. Sistem menggunakan arsitektur *Read-Replica* dan *ActiveRecord Callback* `after_save :trigger_disbursement`.

**Spesifikasi Persyaratan:**
1. Desain skema dan model Active Record yang menerapkan mekanisme **Idempotency Key Engine** berbasis database constraint.
2. Eliminasi penuh ketergantungan aksi pemanggilan eksternal dari callback internal Active Record (`after_save`). Gantilah dengan implementasi **Transactional Outbox Pattern** di mana event pencairan ditulis ke dalam tabel `outbox_events` dalam satu transaksi atomik bersama pembaruan status pinjaman.
3. Kueri pengecekan status duplikasi harus dipaksa berjalan pada node **Primary** (*Writer*), mem-bypass *Read-Replica* guna menghindari isu inkonsistensi data akibat *Replication Lag*.
4. Solusi harus tahan terhadap beban konkurensi 10.000 permintaan identik secara paralel tanpa memunculkan inkonsistensi saldo kredit atau eksekusi transfer ganda ke penyedia sistem kliring.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa fungsi utama dari internal engine **Arel** pada Active Record?
   - a. Mengelola connection pool HTTP socket.
   - b. Mengompilasi pohon sintaksis relasional (AST) menjadi string query SQL yang spesifik terhadap adapter database.
   - c. Menghapus memori instansiasi objek Ruby secara otomatis via Garbage Collector.
   - d. Menjalankan serialisasi data format JSON API.

2. Metode eager loading manakah yang selalu menghasilkan satu query SQL raksasa menggunakan klausa `LEFT OUTER JOIN`?
   - a. `.preload`
   - b. `.eager_load`
   - c. `.includes` tanpa klausa referensi tambahan
   - d. `.load_async`

3. Mengapa *Single Table Inheritance* (STI) sering dihindari dalam desain database relasional skala besar?
   - a. Karena STI tidak mendukung tipe data foreign key berupa UUID.
   - b. Karena STI mengakibatkan tabel menjadi *sparse* (dipenuhi kolom `NULL`) dan merusak integritas *database constraint*.
   - c. Karena STI membuat Rails tidak mampu mendeteksi model secara otomatis.
   - d. Karena STI memperlambat migrasi database lokal.

4. Apa dampak penggunaan `strict_loading!` pada suatu instance atau relasi Active Record?
   - a. Mencegah mutasi atribut (menjadikan instance read-only).
   - b. Memunculkan error `ActiveRecord::StrictLoadingViolationError` seketika jika model mencoba memanggil asosiasi yang belum di-eager-load (N+1).
   - c. Mematikan fitur dirty tracking atribut.
   - d. Memvalidasi format string email secara ketat.

5. Callback Active Record manakah yang merupakan tempat paling aman untuk memicu pemanggilan job asynchronous Sidekiq yang mengandalkan data di basis data?
   - a. `after_save`
   - b. `before_commit`
   - c. `after_commit`
   - d. `around_update`

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Pendek)
6. Manakah konfigurasi penulisan kueri berikut yang secara eksplisit memaksa operasi pembacaan dieksekusi langsung pada basis data replika?
   - a. `ActiveRecord::Base.connected_to(role: :reading) { User.all }`
   - b. `User.reading_database.all`
   - c. `User.where(replica: true)`
   - d. `ActiveRecord::Base.transaction(isolation: :replica) { User.all }`

7. Apa arti klausa `SKIP LOCKED` pada pemanggilan kueri `SELECT ... FOR UPDATE SKIP LOCKED`?
   - a. Database membatalkan eksekusi jika menemukan baris yang terkunci.
   - b. Kueri mengabaikan baris data yang sedang dikunci oleh transaksi lain dan hanya mengembalikan baris bebas kunci berikutnya.
   - c. Kueri memaksa pelepasan kunci transaksi lain secara agresif.
   - d. Kueri melompati pemeriksaan tipe data indeks.

8. Kapan mekanisme `Optimistic Locking` (`lock_version`) Active Record melempar eksepsi `ActiveRecord::StaleObjectError`?
   - a. Ketika nilai `statement_timeout` database terlampaui.
   - b. Ketika nilai `lock_version` di database lebih besar daripada nilai `lock_version` lokal yang dipegang objek saat eksekusi `UPDATE`.
   - c. Ketika server basis data kehilangan koneksi jaringan.
   - d. Ketika koneksi pool kehabisan thread worker.

9. Apa kelemahan performa terbesar dari pemanggilan metode `.load_async` jika dieksekusi secara masif di controller yang padat trafik?
   - a. Mengalokasikan terlalu banyak string SQL statis.
   - b. Menguras kuota koneksi `ConnectionPool` aplikasi dengan sangat cepat karena mengeksekusi banyak thread paralel per kueri.
   - c. Mematikan fitur caching fragment Rails.
   - d. Menjadikan query rentan terhadap *Race Condition*.

10. Perhatikan cuplikan kode berikut:
```ruby
Order.transaction do
  order = Order.find(order_id)
  order.update!(status: "paid")
  PaymentGatewayClient.charge(order.amount) # 2.500 ms latency
end
```
Apa risiko arsitektur paling kritikal dari pola di atas pada sistem berskala ribuan transaksi per detik?
- Jawaban Singkat: Penahanan koneksi database (*Idle in Transaction*) selama 2,5 detik memicu *Connection Pool Exhaustion*, menghentikan kueri lain di seluruh aplikasi.

#### Bagian 3: Production Scenario Case Studies
11. **Skenario Kasus A:**
    Aplikasi logistik enterprise Anda memiliki tabel `deliveries` dengan 40 juta baris data. Anda menambahkan relasi polimorfik baru menggunakan *Delegated Types* bernama `delivery_mechanism` (`DroneDelivery`, `CourierDelivery`). Pada dashboard analitik harian, kueri yang menghitung total pengiriman gabungan memakan waktu 45 detik dan membekukan Puma workers.
    *Tugas Analisis:* Identifikasi kemungkinan bottleneck (misal: join amplification, missing compound indexes) dan susun struktur indeks composite PostgreSQL serta perbaikan kueri menggunakan `load_async` atau `eager_load` selektif.

12. **Skenario Kasus B:**
    Dua microservice secara konkuren mengakses akun saldo yang sama. Terjadi error deadlock secara terus menerus (`PG::TRDeadlockDetected`) di log Sentry setiap kali Service 1 (transfer keluar) dan Service 2 (pendebetan biaya bulanan otomatis) berjalan pada jam yang sama.
    *Tugas Analisis:* Analisis struktur query dan susun arsitektur penguncian pesimistik deterministik yang aman dari ancaman deadlock antar-layanan.

13. **Skenario Kasus C:**
    Pada arsitektur Multi-Database (Primary & Read-Replica), nasabah baru saja memperbarui data profilnya. Namun saat controller me-redirect pengguna ke halaman profil (`show`), data yang tampil masih data lama sebelum update (terjadi fenomena *Stale Read* akibat adanya replication delay selama 300ms dari primary ke replica).
    *Tugas Analisis:* Solusikan mekanisme penanganan *read-your-own-writes consistency* menggunakan fitur otomatis Active Record (`automatic_role_switching` dengan `delay: 2.seconds`).

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **b** — Arel adalah AST engine untuk merepresentasikan aljabar relasional secara formal.
2. **b** — `.eager_load` selalu memaksa Rails menggunakan query tunggal dengan `LEFT OUTER JOIN`.
3. **b** — STI menyatukan semua entitas subkelas dalam satu tabel sehingga menciptakan banyak kolom null (*sparse*) dan merusak *NOT NULL constraints*.
4. **b** — `strict_loading!` memicu eksepsi saat relasi yang belum ter-load diakses untuk mencegah N+1.
5. **c** — `after_commit` menjamin bahwa baris database benar-benar sudah ditulis permanen sebelum dibaca oleh worker async luar.

#### Bagian 2: Intermediate
6. **a** — `ActiveRecord::Base.connected_to(role: :reading)` mengalihkan konteks thread ke pool replica.
7. **b** — `SKIP LOCKED` menginstruksikan database untuk melewati record yang sedang terkunci oleh proses transaksi paralel lain.
8. **b** — Konflik terdeteksi saat versi basis data tidak cocok lagi dengan versi saat objek dibaca.
9. **b** — Setiap eksekusi async menyewa thread pool database independen; eksekusi masif memicu starvation pool.
10. **Analisis Singkat:** *Idle in transaction* memblokir connection pool dan mengakibatkan degradasi performa sistem secara menyeluruh.

#### Bagian 3: Production Scenario (Pedoman Penilaian Arsitektural)
11. **Evaluasi Kasus A:**
    - Bottleneck: Hilangnya composite index pada `[:delivery_mechanism_type, :delivery_mechanism_id]`, memicu *Full Table Scan* pada 40 juta baris saat join dieksekusi.
    - Solusi: Menambahkan compound index konkrit di PostgreSQL, menyusun scope berbasis filter waktu dengan Arel, dan menggunakan denormalisasi parsial via PostgreSQL Materialized View jika data historis jarang berubah.
12. **Evaluasi Kasus B:**
    - Bottleneck: Urutan penguncian baris (`FOR UPDATE`) tidak konsisten antara Service 1 dan Service 2, sehingga menciptakan *cycle of dependencies*.
    - Solusi: Mewajibkan penguncian akun target dengan urutan deterministik (contoh: selalu urutkan `Account.lock.find([id_1, id_2].sort)`), serta mengonfigurasi `lock_timeout = '2s'` untuk mencegah infinite hang.
13. **Evaluasi Kasus C:**
    - Bottleneck: *Replication Lag* alami pada distributed database.
    - Solusi: Mengaktifkan konfigurasi Rails Automatic Role Switching:
      ```ruby
      config.active_record.database_selector = { delay: 2.seconds }
      config.active_record.database_resolver = ActiveRecord::Middleware::DatabaseSelector::Resolver
      config.active_record.database_resolver_context = ActiveRecord::Middleware::DatabaseSelector::Resolver::Session
      ```
      Mekanisme ini memanfaatkan cookie sesi penanda waktu tulis (*last write timestamp*) untuk memaksa pembacaan diarahkan ke primary selama 2 detik pasca penulisan data.

---

### 16. Summary

Menguasai Active Record di tingkat enterprise menuntut pergeseran paradigma: dari sekadar pembuat kueri CRUD deklaratif menjadi arsitek layer data yang memahami seluk-beluk aljabar relasional Arel AST, batas konkurensi memori, dan manajemen I/O tingkat rendah. 

Kunci stabilitas arsitektur berpusat pada:
1. **Pemisahan Model yang Bersih:** Mengganti skema STI yang rapuh dengan **Delegated Types** yang ternormalisasi.
2. **Disiplin Kinerja Akses:** Menegakkan proteksi N+1 via **Strict Loading**, serta selektif menggunakan metode eager loading (`preload` vs `eager_load`).
3. **Integritas Konkurensi Transaksional:** Mengeliminasi race conditions melalui penguncian deterministik (**Pessimistic Locking dengan urutan terurut** atau `SKIP LOCKED`).
4. **Skalabilitas Multi-Database:** Mengalihkan beban secara transparan menggunakan pemisahan peran (*Primary/Replica Connection Switching*) dengan perlindungan *stale read*.

Dengan mengadopsi prinsip-prinsip ini, Active Record dapat beroperasi dengan performa tinggi, deterministik, dan tangguh di bawah beban jutaan kueri terdistribusi.