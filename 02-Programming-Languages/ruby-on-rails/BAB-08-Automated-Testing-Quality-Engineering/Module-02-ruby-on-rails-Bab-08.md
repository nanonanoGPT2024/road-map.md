# Kurikulum Rekayasa Perangkat Lunak Enterprise: Ruby on Rails
## Kategori: 02-Programming-Languages
### BAB 08: Automated Testing & Quality Engineering
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Principal Software Engineer / Staff Engineer diharapkan mampu:
- **Menganalisis dan Membedah** arsitektur internal eksekusi pengujian Rails, termasuk lifecycle manajemen koneksi database, transactional fixtures, memory footprint, dan mutasi AST (*Abstract Syntax Tree*).
- **Merancang Arsitektur Test Suite Enterprise** berskala puluhan ribu test case dengan eksekusi paralel terdistribusi, isolasi state mutlak, dan deterministik (*zero-flakiness*).
- **Mengimplementasikan Pola Mocking dan Stubbing Tingkat Lanjut** menggunakan *Verifying Doubles*, *Spies*, dan *Contract Testing* (Pact) tanpa terjebak ke dalam *fragile test anti-patterns*.
- **Mengoptimalkan Kinerja Test Suite** menggunakan strategi alokasi memori FactoryBot, evaluasi lazy/eager, komparasi `build_stubbed` vs `create`, serta eliminasi I/O bottleneck.
- **Mengintegrasikan Automated Quality Gates** modern berbasis *Mutation Testing* (Mutant), static security analysis (Brakeman AST rules), serta branch-level coverage monitoring pada CI/CD pipeline skala besar.

---

### 2. Prerequisites
Sebelum menelaah modul ini, pembaca diasumsikan telah menguasai:
- Ruby Metaprogramming, Object Model, dan Ruby Virtual Machine (YARV) internals (Object allocation, Garbage Collection).
- Penggunaan dasar RSpec (syntax `describe`, `context`, `it`, `expect`), FactoryBot, dan DatabaseCleaner.
- Mekanisme konkurensi Ruby: Thread, Fiber, Multi-Process (Forking), dan GIL/GVL semantics.
- Arsitektur Database Relasional (PostgreSQL): Transaction Isolation Levels, Savepoints, Locks, dan Connection Pools.

---

### 3. Concept & Internal Architecture

#### 3.1 Siklus Hidup Test Execution & Transactional Fixtures
Rails menyediakan pengujian berbasis transaksi menggunakan `ActiveRecord::TestFixtures` (sering dikonfigurasi melalui `config.use_transactional_fixtures = true`). Di balik layar, arsitektur ini memanipulasi transaction nesting:

```
[Test Runner Start]
        │
        ▼
ActiveRecord::Base.connection_handler.connection_pool
        │
        ▼
[before(:suite)] ──> Load Schema / Run Migrations (No Transaction)
        │
        ▼ (Loop per Test Process / Fork)
   [Example Group: describe/context]
        │
        ▼
   [before(:example)]
        │ ──> Checkout Connection dari Pool
        │ ──> BEGIN Transaction (Top-Level)
        │ ──> Set Savepoint (Opsional jika nested transaction aktif)
        │
        ▼
   [EKSEKUSI SPESIFIKASI / TEST CODE]
        │ ──> Model.create! (Menulis ke DB di dalam uncommitted transaction)
        │ ──> Assertion checks
        │
        ▼
   [after(:example)]
        │ ──> ROLLBACK Transaction (Menghapus seluruh state mutasi data)
        │ ──> Check-in Connection kembali ke Pool
        │ ──> Bersihkan Thread-local variables
        │
        ▼
[Test Runner Finish]
```

Ketika kode aplikasi memanggil `ActiveRecord::Base.transaction`, Rails mengonversinya menjadi `SAVEPOINT` Postgres secara internal karena koneksi telah dibungkus oleh transaksi top-level dari test runner:

```ruby
# Konsep internal Rails ActiveRecord Transaction nesting di test harness
connection.begin_transaction(joinable: false) # Eksekusi di before(:example)
# Kode spesifikasi dieksekusi di sini:
#   User.create!(...) -> Menghasilkan: INSERT INTO users ...
#   ActiveRecord::Base.transaction do -> Menghasilkan: SAVEPOINT active_record_1
#     Profile.create!(...)
#   end -> Menghasilkan: RELEASE SAVEPOINT active_record_1
connection.rollback_transaction # Eksekusi di after(:example), rollback ke initial state
```

Jika `joinable: false` digunakan, nested block transaction tidak diizinkan untuk melakukan commit ke root transaction. Masalah terjadi saat test melibatkan background job (sidekiq process berbeda) atau multi-threaded tests, di mana koneksi database berada pada thread/proses terpisah dan tidak dapat membaca transaksi yang belum di-commit oleh main thread (*transaction isolation phantom read*).

#### 3.2 FactoryBot Internal Compilation & Memory Optimization
FactoryBot tidak sekadar mengeksekusi instantiation ActiveRecord. FactoryBot mengompilasi factory definition ke dalam abstract definition graph:

1. **`FactoryBot::DeclarationList`**: Mengompilasi atribut dinamis (block/lazy), statis, dan deklarasi traits.
2. **`FactoryBot::Evaluator`**: Menyediakan scope eksekusi untuk attributes evaluator.
3. **Execution Strategies**:
   - `build`: Menginstansiasi instance ActiveRecord di memori tanpa memanggil `save!`.
   - `create`: Menginstansiasi, mengevaluasi asosiasi secara rekursif, lalu mengeksekusi `save!` (I/O intensif).
   - `build_stubbed`: Tidak menyentuh database sama sekali. Menginstansiasi model, memalsukan primary key (ID integer acak), menandai record seolah-olah sudah di-persist (`persisted? == true`), dan men-stubbing method mutasi (`save`, `update`, `destroy`) agar memicu error jika terpanggil secara tidak sengaja.

```
FactoryBot Allocation Profile:
-------------------------------------------------------------------------
Strategy        | Allocations (Objects) | DB roundtrips | Memory Cost
-------------------------------------------------------------------------
build_stubbed   | ~120 objects          | 0             | Sangat Rendah
build           | ~450 objects          | 0 (jika no rel)| Rendah
create          | ~2,800+ objects       | 3 - 10 queries| Sangat Tinggi
-------------------------------------------------------------------------
```

#### 3.3 Mutation Testing (Mutant) Engine Mechanics
Mutation testing mengukur kualitas test suite dengan cara menginjeksi mutasi sintaksis (*mutants*) ke dalam kode sumber menggunakan manipulasi AST melalui parser Ruby.

```
Kode Asli (AST) ──> Parser/Parser Gem ──> Rewriter (Mutant) ──> Mutated AST ──> VM Execution
      │                                                                           │
      ▼                                                                           ▼
`x > 0 ? true : false`       Diubah menjadi: `x >= 0 ? true : false`        Test Suite Dijalankan
                                             `x < 0 ? true : false`
                                             `true`
```
Jika mutasi sintaksis dilakukan tetapi seluruh test suite tetap berstatus **PASSED**, maka mutant dianggap **SURVIVED** (mengindikasikan assertion gap/false confidence). Jika test suite menjadi **FAILED**, maka mutant dianggap **KILLED** (valid).

---

### 4. Why & What

| Dimensi Enterprise | Pendekatan Konvensional (Naive) | Pendekatan Enterprise Modern |
| :--- | :--- | :--- |
| **Kecepatan CI/CD** | Sequential run atau blind horizontal partition. Memakan waktu 30-60 menit. | Intelligent dynamic splitting berbasis execution runtime metrics (Knapsack algorithm). Eksekusi di bawah 5 menit. |
| **Factory Strategy** | `create` di semua level spec. Over-fetching dan cascades association berlebih. | Strict usage: `build_stubbed` sebagai default, `build` untuk integrasi model, `create` khusus database-bound logic. |
| **State Sanitization** | `DatabaseCleaner.clean_with(:truncation)` pada setiap test cycle (I/O disk exhaustion). | Transactional fixtures dengan dynamic connection leasing, truncation eksklusif untuk specs multi-thread/headless browser. |
| **Test Boundary** | Menembak network API nyata atau stubbing parsial tanpa verifikasi skema. | Strict Contract Testing (Pact) & OpenAPI validation dengan Schema Conformance Enforcement. |
| **Mocking Safety** | Menggunakan raw doubles (`double("User")`) yang rentan terhadap antarmuka usang (*mock drift*). | Verifying Doubles (`instance_double`, `class_double`, `object_double`) yang memvalidasi eksistensi method secara statis/dinamis. |

---

### 5. How (Workflow Detail)

Untuk mengoperasikan test harness modern pada Rails enterprise monolith, ikuti siklus pipeline berikut:

```
[Developer commit code]
        │
        ▼
[Static Analysis & Fast-Fail Gate]
 ├── RuboCop (Custom AST rules)
 ├── Brakeman (AST security taint analysis)
 └── FactoryBot Lint (Dry-run compiling all factories)
        │
        ▼
[Dynamic Orchestration: Knapsack Partitioning]
 ├── Node 1: Specs [00:00 - 05:00] (Heavy DB/Integration)
 ├── Node 2: Specs [00:00 - 05:00] (Domain Service Specs)
 └── Node N: Specs [00:00 - 05:00] (Parallel System/Request Specs)
        │
        ▼
[RSpec In-Node Multi-Process Execution]
 ├── Rails Parallel Testing (Fork worker 1..M based on CPU Cores)
 ├── Transactional Rollback per worker
 └── Isolated PostgreSQL Schema/Database per worker (test_db_1, test_db_2)
        │
        ▼
[Mutation Testing Gate (Pull Request Changed Files Only)]
 └── Mutant runs on targeted git diff namespace
        │
        ▼
[Artifact Collection & Flaky Spec Detection Engine]
 ├── SimpleCov branch coverage aggregation (S3/GCS bucket upload)
 └── Log parsing: retry failed specs & record run-order dependencies
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Staging Teater Broadway vs Syuting Film Skala Besar
- **Pengujian Naive (`create` & Truncation)**: Seperti merobohkan dan membangun kembali seluruh gedung teater dan propertinya dari nol setiap kali aktor selesai mengucapkan satu baris dialog. Boros energi, merusak infrastruktur, dan memakan waktu berhari-hari.
- **Pengujian Enterprise (`build_stubbed` & Transactional Savepoints)**: Seperti aktor yang menggunakan properti replika ringan (busa) saat latihan meja (*table read*). Ketika set fisik panggung digunakan, semua perubahan cat atau perabotan ditarik kembali menggunakan katrol dan proyektor ilusi optik (*Savepoint Rollback*) dalam hitungan milidetik, tanpa ada puing yang perlu disapu.

#### Arsitektur Database Worker Isolation
```
                    ┌─────────────────────────┐
                    │  RSpec Orchestrator     │
                    │  (Parallel Test Runner) │
                    └────────────┬────────────┘
                                 │ Fork Processes
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  Worker 1 (PID)  │   │  Worker 2 (PID)  │   │  Worker N (PID)  │
│  Thread Pool     │   │  Thread Pool     │   │  Thread Pool     │
└────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  PostgreSQL      │   │  PostgreSQL      │   │  PostgreSQL      │
│  DB: app_test_1  │   │  DB: app_test_2  │   │  DB: app_test_n  │
│  (Rollback Iso)  │   │  (Rollback Iso)  │   │  (Rollback Iso)  │
└──────────────────┘   └──────────────────┘   └──────────────────┘
```

---

### 7. Implementation: Simple vs Practical Example

#### 7.1 Simple Example: Optimal FactoryBot Architecture & Verifying Doubles

**Anti-Pattern (Lambat, Boros DB I/O, Rapuh):**
```ruby
# spec/factories/users.rb
FactoryBot.define do
  factory :user do
    name { "John Doe" }
    association :account # Creates Account
    association :profile # Creates Profile
    association :billing_address # Creates Address
  end
end

# spec/services/naive_notification_spec.rb
RSpec.describe NotificationSender do
  it "sends an email" do
    # Memicu 4 queries INSERT, memakan memori alokasi ~10,000 objects
    user = FactoryBot.create(:user)
    
    # Raw double: Tidak memvalidasi apakah UserMailer benar-benar memiliki method deliver_welcome
    fake_mailer = double("UserMailer") 
    allow(fake_mailer).to receive(:deliver_welcome)
    
    NotificationSender.new(user, mailer: fake_mailer).execute
    expect(fake_mailer).to have_received(:deliver_welcome)
  end
end
```

**Enterprise Production Pattern:**
```ruby
# spec/factories/users.rb
FactoryBot.define do
  factory :user do
    name { "John Doe" }

    # Isolasi asosiasi dengan strategi eksplisit agar tidak auto-create
    trait :with_account do
      account { association :account, strategy: build_strategy }
    end
  end
end

# spec/services/optimized_notification_spec.rb
RSpec.describe NotificationSender do
  describe "#execute" do
    # Zero DB roundtrips, ID disimulasikan, validasi method contract terjamin
    let(:user) { build_stubbed(:user) }
    let(:mailer) { instance_double(UserMailer) }

    it "mendelegasikan pengiriman email selamat datang ke UserMailer" do
      # instance_double akan melempar exception jika UserMailer tidak memiliki #deliver_welcome
      expect(mailer).to receive(:deliver_welcome).with(user).once

      service = described_class.new(user: user, mailer: mailer)
      service.execute
    end
  end
end
```

---

#### 7.2 Practical Enterprise Example: Financial Ledger Transfer Engine Spec

Berikut adalah implementasi spesifikasi untuk mesin mutasi buku besar perbankan (*Double-entry Bookkeeping Engine*). Kode ini menguji konkurensi, custom matchers, validasi skema, dan transactional rollback isolation.

##### File: `app/services/ledger/transfer_service.rb`
```ruby
# frozen_string_literal: true

module Ledger
  class InsufficientFundsError < StandardError; end
  class ConcurrencyLockError < StandardError; end

  class TransferService
    def initialize(source_account_id:, destination_account_id:, amount_cents:, idempotency_key:)
      @source_account_id = source_account_id
      @destination_account_id = destination_account_id
      @amount_cents = Integer(amount_cents)
      @idempotency_key = idempotency_key
      raise ArgumentError, "Amount must be positive" if @amount_cents <= 0
    end

    def call
      ActiveRecord::Base.transaction(isolation: :serializable) do
        idempotency_record = IdempotencyKey.lock("FOR UPDATE NOWAIT").find_or_initialize_by(key: @idempotency_key)
        return idempotency_record.response_payload if idempotency_record.persisted?

        # Mencegah deadlock dengan mengurutkan penguncian ID (Resource Ordering Pattern)
        ordered_ids = [@source_account_id, @destination_account_id].sort
        accounts = Account.lock("FOR UPDATE").where(id: ordered_ids).index_by(&:id)

        source = accounts.fetch(@source_account_id)
        destination = accounts.fetch(@destination_account_id)

        raise InsufficientFundsError, "Saldo tidak mencukupi" if source.balance_cents < @amount_cents

        source.update!(balance_cents: source.balance_cents - @amount_cents)
        destination.update!(balance_cents: destination.balance_cents + @amount_cents)

        ledger_entry = LedgerEntry.create!(
          source_account: source,
          destination_account: destination,
          amount_cents: @amount_cents,
          idempotency_key: @idempotency_key
        )

        response = { status: "SUCCESS", ledger_entry_id: ledger_entry.id, amount: @amount_cents }
        idempotency_record.update!(response_payload: response)

        ActiveSupport::Notifications.instrument("ledger.transfer_completed", response)
        response
      end
    rescue ActiveRecord::LockWaitTimeout
      raise ConcurrencyLockError, "Gagal mengunci akun untuk transfer"
    end
  end
end
```

##### File: `spec/support/matchers/be_monetarily_balanced.rb`
```ruby
# frozen_string_literal: true

# Custom AST/Domain RSpec Matcher untuk memastikan integritas saldo
RSpec::Matchers.define :be_monetarily_balanced do
  match do |ledger_entry|
    source_debit = ledger_entry.source_account.balance_cents
    destination_credit = ledger_entry.destination_account.balance_cents
    
    @net_delta = source_debit + destination_credit
    @expected_sum == @net_delta
  end

  chain :with_initial_aggregate do |expected_sum|
    @expected_sum = expected_sum
  end

  failure_message do |ledger_entry|
    "Diharapkan aggregate balance bernilai #{@expected_sum}, namun terdeteksi delta #{@net_delta} pada Ledger ID: #{ledger_entry.id}"
  end
end
```

##### File: `spec/services/ledger/transfer_service_spec.rb`
```ruby
# frozen_string_literal: true

require "rails_helper"

RSpec.describe Ledger::TransferService, type: :service do
  # Menggunakan tag metadata kustom untuk optimasi suite hook
  describe "#call", :db_transactional do
    let(:initial_source_balance) { 1_000_000 }
    let(:initial_dest_balance) { 500_000 }
    let(:transfer_amount) { 250_000 }
    let(:idempotency_key) { "idemp_tx_#{SecureRandom.hex(12)}" }

    let!(:source_account) do
      create(:account, balance_cents: initial_source_balance)
    end

    let!(:destination_account) do
      create(:account, balance_cents: initial_dest_balance)
    end

    subject(:execute_service) do
      described_class.new(
        source_account_id: source_account.id,
        destination_account_id: destination_account.id,
        amount_cents: transfer_amount,
        idempotency_key: idempotency_key
      ).call
    end

    context "dalam kondisi alur transaksi nominal valid" do
      it "mengurangi saldo pengirim, menambah saldo penerima, dan mencatat ledger entry secara atomik" do
        total_aggregate = initial_source_balance + initial_dest_balance

        expect { execute_service }
          .to change { source_account.reload.balance_cents }.by(-transfer_amount)
          .and change { destination_account.reload.balance_cents }.by(transfer_amount)

        latest_entry = LedgerEntry.last
        expect(latest_entry).to be_monetarily_balanced.with_initial_aggregate(total_aggregate)
      end

      it "memancarkan event instrumentasi ActiveSupport untuk audit trail" do
        expect { execute_service }.to instrument_notification("ledger.transfer_completed")
      end
    end

    context "ketika rekurensi idempotency key yang sama dikirim ulang" do
      before { execute_service }

      it "mengembalikan payload tersimpan tanpa menduplikasi pemindahan dana (Zero State Mutation)" do
        expect { execute_service }
          .to not_change { source_account.reload.balance_cents }
          .and not_change { destination_account.reload.balance_cents }
          .and not_change { LedgerEntry.count }

        expect(execute_service["status"]).to eq("SUCCESS")
      end
    end

    context "ketika saldo akun pengirim tidak mencukupi" do
      let(:transfer_amount) { 2_000_000 }

      it "melempar Ledger::InsufficientFundsError dan me-rollback seluruh mutasi state DB" do
        expect { execute_service }.to raise_error(Ledger::InsufficientFundsError, /Saldo tidak mencukupi/)

        expect(source_account.reload.balance_cents).to eq(initial_source_balance)
        expect(destination_account.reload.balance_cents).to eq(initial_dest_balance)
        expect(LedgerEntry.where(idempotency_key: idempotency_key)).not_to exist
      end
    end

    context "pengujian konkurensi (Race Condition Resilience)" do
      it "mengeksekusi 2 transfer paralel secara serial tanpa merusak saldo agregat" do
        threads = []
        barrier = Concurrent::CyclicBarrier.new(2)

        # Thread 1: Transfer dari A -> B
        threads << Thread.new do
          ActiveRecord::Base.connection_pool.with_connection do
            barrier.wait
            described_class.new(
              source_account_id: source_account.id,
              destination_account_id: destination_account.id,
              amount_cents: 100_000,
              idempotency_key: "tx_conc_1"
            ).call
          end
        end

        # Thread 2: Transfer balik dari B -> A
        threads << Thread.new do
          ActiveRecord::Base.connection_pool.with_connection do
            barrier.wait
            described_class.new(
              source_account_id: destination_account.id,
              destination_account_id: source_account.id,
              amount_cents: 50_000,
              idempotency_key: "tx_conc_2"
            ).call
          end
        end

        threads.each(&:join)

        # Expected: Source = 1_000_000 - 100_000 + 50_000 = 950_000
        # Destination = 500_000 + 100_000 - 50_000 = 550_000
        expect(source_account.reload.balance_cents).to eq(950_000)
        expect(destination_account.reload.balance_cents).to eq(550_000)
      end
    end
  end
end
```

---

### 8. Real World Case Study: FinTech Monolith Scale Test Suite Transformation

#### Skenario & Skala Masalah
Sebuah platform pembayaran unicorn di Asia Tenggara memiliki repositori monolitik Ruby on Rails dengan metrik berikut:
- **Basis Kode**: 1.2 juta baris kode (LOC).
- **Test Suite**: 24.500 RSpec examples.
- **Waktu Eksekusi CI (Sebelumnya)**: 58 menit pada CI pipeline (40 worker nodes).
- **Tingkat Flakiness**: ~14% build gagal secara acak setiap hari karena database deadlocks, dynamic time-travel specs (`Timecop`), dan memory leaks pada heap Ruby.
- **Biaya Operasional CI**: > $15,000 USD/bulan hanya untuk compute compute node CI runner.

#### Analisis Akar Masalah (Root-Cause Profiling)
1. **Factory Cascades**: Sebuah pemanggilan `create(:order)` menginstansiasi 42 record terkait secara implisit (User, Store, Tenant, Geolocation, Item, TaxCategory, Wallet). 70% waktu spec terbuang pada operasi disk `INSERT` & `DELETE`.
2. **DatabaseCleaner Abuse**: 4.000 spesifikasi API menggunakan strategi `DatabaseCleaner.clean_with(:truncation)`, yang mengeksekusi perintah DDL `TRUNCATE TABLE` secara agresif. Ini menghapus query plan cache internal Postgres dan membebani file descriptor engine.
3. **Flaky Thread Leaks**: Pengujian asinkronus (ActiveJob/Sidekiq) yang berjalan di latar belakang tidak di-drain dengan bersih sebelum example selesai, menyebabkan worker thread menyusup (*polluting*) ke test case berikutnya.

#### Solusi Rekayasa Sistem
1. **Eliminasi Truncation via Transaction Isolation**:
   Mengganti seluruh suite integrasi agar berjalan di atas `ActiveRecord::TestFixtures` dengan PostgreSQL schema uncommitted reads. Truncation dibatasi eksklusif hanya untuk suite System Spec / Selenium Headless Chrome.
2. **FactoryBot Pruning & Association Nullification**:
   Semua factory refactored menggunakan *Explicit Dependency Declaration*:
   ```ruby
   # Sebelum: factory mendefinisikan seluruh relasi secara eager
   # Sesudah: relasi dideklarasikan secara opsional via traits
   factory :order do
     association :store, strategy: :build_stubbed
     # User tidak dibuat otomatis kecuali trait :with_user ditambahkan
   end
   ```
3. **Penerapan Knapsack Pro Dynamic Partitioning**:
   Mengganti alokasi file statis dengan dynamic queueing model: worker nodes meminta file spec berikutnya dari centralized Redis coordinator secara real-time berdasarkan beban CPU aktual, mengeliminasi idle time pada worker terakhir (*straggler problem*).
4. **Time Isolation Sandbox**:
   Mencegah penggunaan library non-reentrant. Mengganti manipulasi waktu manual dengan Rails native `travel_to` yang dibungkus dalam blok `around(:example)` wajib, memastikan resetting waktu via ensure block.

#### Hasil Metrik Arsitektur Baru
- **Waktu Eksekusi CI**: Dari **58 menit** terpangkas menjadi **4 menit 18 detik** (peningkatan kecepatan **~13.5x**).
- **Tingkat Kegagalan (Flakiness)**: Turun dari **14%** ke **< 0.05%**.
- **Penghematan Finansial**: Mengurangi kebutuhan CI runner node dari 40 menjadi 16 high-performance worker instance, memangkas biaya cloud CI sebesar **$9,800 USD/bulan**.
- **Mutant Score**: 86% pada level domain core services.

---

### 9. Trade-offs Architecture Matrix

| Strategi Arsitektur | Keuntungan Utama | Kompensasi / Kelemahan (Trade-off) | Rekomendasi Skenario Penggunaan |
| :--- | :--- | :--- | :--- |
| **`build_stubbed` over `create`** | Eksekusi instan; 0 queries database; alokasi memori minimal. | Mengabaikan DB constraints (foreign keys, uniqueness, NOT NULL check). | Domain Logic, Service Objects, Value Objects, Presenters/Serializers. |
| **Transactional Fixtures** | Sangat cepat; memulihkan state DB via rollback Postgres; aman untuk paralel. | Tidak mendukung pengujian multi-thread native (misal: Capybara running against live server Puma). | Controller/Request Specs, Model Specs, Service Specs standar. |
| **Truncation Strategy** | Menjamin reset mutlak state DB; mendukung external processes membaca data. | Sangat lambat; me-reset sequence auto-increment; menghancurkan internal cache buffer DB. | Hanya untuk Webdriver/E2E Browser System Specs. |
| **Mutation Testing (Mutant)** | Mengidentifikasi *false-positive assertions* dan *dead code*; presisi pengujian maksimal. | Waktu komputasi ekstrem; memakan CPU tinggi; sulit diterapkan pada 100% legacy monolith. | Dibatasi hanya pada Pull Request changed files (Differential Mutation). |
| **Contract Testing (Pact)** | Menghindari network dependency; menangkap API drift antar microservices sebelum deploy. | Overhead manajemen pact broker file; membutuhkan koordinasi antar tim provider dan consumer. | Ekosistem Microservices dengan komunikasi synchronous REST/gRPC. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Global State Contamination via Class-Level State
**Kesalahan:** Mengubah state global atau class variable (`@@var` atau `Current.user`) dalam pengujian tanpa merestorasinya.
```ruby
# ANTI-PATTERN
it "changes the global configuration" do
  AppConfig.maintenance_mode = true
  expect(HealthCheck.status).to eq("MAINTENANCE")
  # Jika assertion gagal di sini, baris restorasi di bawah tidak dieksekusi!
  AppConfig.maintenance_mode = false
end
```
**Solusi Produksi:** Gunakan isolasi lifecycle block dengan `ensure` pattern atau native rspec sandbox:
```ruby
# PRODUCTION PATTERN
around(:example) do |example|
  original_state = AppConfig.maintenance_mode
  begin
    example.run
  ensure
    AppConfig.maintenance_mode = original_state
  end
end
```

#### 10.2 ActiveRecord Shared Connection Deadlocks pada Parallel Test
**Gejala:** Worker test membeku (*hanging indefinitely*) atau melempar exception `ActiveRecord::LockWaitTimeout: Lock wait timeout exceeded`.
**Penyebab:** Dua parallel worker (misal: Worker 1 dan Worker 2) mencoba mengakses database yang sama karena konfigurasi nama database test tidak menyertakan ENV worker pool index.
**Troubleshooting Checklist:**
1. Verifikasi `config/database.yml`:
   ```yaml
   test:
     adapter: postgresql
     database: myapp_test<%= ENV['TEST_ENV_NUMBER'] %>
   ```
2. Pastikan database telah di-provision sebelum suite berjalan:
   `bin/rails parallel:setup`
3. Hindari penguncian table (`LOCK TABLE`) manual dalam model callbacks selama test berlangsung.

#### 10.3 Mock Leaks (Unverified Stubbing Drift)
**Gejala:** Test lulus di lokal dan CI, namun melempar `NoMethodError` saat running di production.
**Penyebab:** Menggunakan `allow(PaymentGateway).to receive(:charge)` padahal nama method yang sebenarnya di kelas produksi adalah `PaymentGateway#process_charge`.
**Solusi Produksi:** Konfigurasi RSpec Mock framework agar memverifikasi interface target secara ketat:
```ruby
# spec/spec_helper.rb
RSpec.configure do |config|
  config.mock_with :rspec do |mocks|
    mocks.verify_partial_doubles = true # MELEMPARKAN ERROR JIKA METHOD TIDAK ADA
    mocks.verify_doubled_constant_names = true
  end
end
```

---

### 11. Production Checklist (Best Practices)

- [ ] **RSpec Verification Policy**: `verify_partial_doubles = true` aktif di `spec_helper.rb`.
- [ ] **Default Factory Strategy**: Menggunakan `build_stubbed` sebagai pilihan utama; pemanggilan `create` harus memerlukan justifikasi operasional DB.
- [ ] **Schema Conformance**: Integrasikan gem `database_consistency` pada test pipeline untuk memverifikasi keselarasan validasi ActiveRecord dengan PostgreSQL constraints.
- [ ] **Dynamic Parallelism**: Menggunakan worker forking berbasis core CPU: `PARALLEL_WORKERS=$(nproc) bin/rails test:all`.
- [ ] **No Raw Time Mutations**: Seluruh manipulasi temporal menggunakan `travel_to` dan `travel_back` dari `ActiveSupport::Testing::TimeHelpers`.
- [ ] **Memory Allocation Guard**: Batasi Garbage Collection sweep frequency menggunakan environment variables:
  `RUBY_GC_HEAP_GROWTH_FACTOR=1.1 RUBY_GC_MALLOC_LIMIT=64000000`.
- [ ] **Contract Gate**: API Request Specs memvalidasi response body terhadap OpenAPI schema specification:
  `expect(response).to match_response_schema("orders/v1")`.
- [ ] **Network Sandbox**: Memblokir seluruh koneksi eksternal TCP/HTTP keluar selama running tests menggunakan `WebMock.disable_net_connect!(allow_localhost: true)`.
- [ ] **Order Randomization Determinism**: Mengaktifkan order random execution: `config.order = :random`. Simpan seed failure pada log CI untuk reproduksi instan via `rspec --seed <SEED_NUMBER>`.
- [ ] **Differential Mutation Coverage**: CI memvalidasi diff pull request dengan Mutant dengan skor threshold minimal 80%.

---

### 12. Hands-on Practice

Buat struktur pengujian skala enterprise pada direktori: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/spec/{support,services,factories}
```

#### Langkah 1: Konfigurasi Mock Framework Strict Rules
Buat file `hands-on/m02/spec/support/rspec_config.rb`:
```ruby
# frozen_string_literal: true

RSpec.configure do |config|
  config.expect_with :rspec do |expectations|
    expectations.include_chain_clauses_in_custom_matcher_descriptions = true
    expectations.syntax = :expect
  end

  config.mock_with :rspec do |mocks|
    mocks.verify_partial_doubles = true
    mocks.verify_doubled_constant_names = true
  end

  config.shared_context_metadata_behavior = :apply_to_host_groups
  config.filter_run_when_matching :focus
  config.example_status_persistence_file_path = "tmp/spec_examples.txt"
  config.disable_monkey_patching!
  config.warnings = false
  config.order = :random
  Kernel.srand config.seed
end
```

#### Langkah 2: Setup Database Connection Profiler Hook
Buat file `hands-on/m02/spec/support/db_query_counter.rb`:
```ruby
# frozen_string_literal: true

module TestUtils
  class DBQueryCounter
    attr_reader :count, :queries

    def initialize
      @count = 0
      @queries = []
    end

    def callback
      lambda do |_name, _start, _finish, _id, payload|
        unless %w[CACHE SCHEMA].include?(payload[:name])
          @count += 1
          @queries << payload[:sql]
        end
      end
    end
  end
end

RSpec.configure do |config|
  config.around(:example, :assert_query_count) do |example|
    counter = TestUtils::DBQueryCounter.new
    subscriber = ActiveSupport::Notifications.subscribe("sql.active_record", counter.callback)
    
    max_queries = example.metadata[:assert_query_count]
    example.run

    ActiveSupport::Notifications.unsubscribe(subscriber)

    if counter.count > max_queries
      raise "N+1 Query Regression Detected! Max allowed: #{max_queries}, actual queries executed: #{counter.count}.\nQueries:\n#{counter.queries.join("\n")}"
    end
  end
end
```

#### Langkah 3: Eksekusi Spec dengan Pengendalian Query N+1
Buat file `hands-on/m02/spec/services/inventory_allocator_spec.rb`:
```ruby
# frozen_string_literal: true

require "rails_helper"
require_relative "../support/db_query_counter"

class Product < ActiveRecord::Base; end

RSpec.describe "Inventory Allocation Suite" do
  describe "Batch Check", :assert_query_count => 1 do
    it "hanya mengeksekusi 1 single batch query untuk 100 entitas produk" do
      # Mensimulasikan query database
      Product.connection.execute("SELECT 1 FROM pg_database WHERE false")
      
      # Jika uncomment query kedua di bawah ini, spec akan melempar failure:
      # Product.connection.execute("SELECT 1 FROM pg_database WHERE false")
      
      expect(true).to be true
    end
  end
end
```

---

### 13. Exercises

#### Level: Easy
1. Refactor test suite berikut agar tidak menulis data ke database:
   ```ruby
   it "calculates full name" do
     user = FactoryBot.create(:user, first_name: "Bruce", last_name: "Wayne")
     expect(user.full_name).to eq("Bruce Wayne")
   end
   ```
   *Kriteria Penyelesaian:* Hilangkan pemanggilan I/O disk menggunakan strategi FactoryBot yang paling optimal.

#### Level: Medium
2. Buat sebuah RSpec Custom Matcher bernama `prevent_n_plus_one_queries` yang mampu membungkus eksekusi sebuah block service code dan memvalidasi bahwa query SQL yang terjadi tidak bertambah secara linear terhadap jumlah koleksi objek input.
   *Kriteria Penyelesaian:* Matcher harus menerima parameter `tolerance: Integer` dan mencetak daftar trace query jika validasi gagal.

#### Level: Hard
3. Tulis sebuah parallel-safe spec suite untuk sebuah Worker distributed locking yang menggunakan Redis.
   *Kriteria Penyelesaian:*
   - Mensimulasikan dua thread konkuren yang berebut acquiring lock yang sama menggunakan `Redlock-rb`.
   - Menguji skenario lock timeout, renewal heartbeat, dan lock releasing.
   - Bersihkan seluruh redis keys yang terbuat secara terisolasi tanpa memanggil `FLUSHDB` (karena akan membatalkan status worker lain pada parallel test runner).

---

### 14. Enterprise Challenge

**Konteks Sistem:**
Anda adalah Staff Quality Engineer pada perbankan digital. Sistem menggunakan Rails Event Store untuk mengimplementasikan *Event Sourcing* pada transaksi perbankan.

**Permasalahan:**
Komponen `AccountAggregate` bertanggung jawab memproses stream jutaan event (`MoneyDeposited`, `TransferInitiated`, `TransactionFailed`). Saat ini, test suite untuk memvalidasi state agregat berjalan sangat lambat karena setiap spec melakukan replay event dari PostgreSQL asli. Setiap kali stream event bertambah panjang, waktu running spec meningkat secara kuadratik $O(N^2)$. Selain itu, pengembang sering kali menulis event tanpa mematuhi JSON Schema versioning, menyebabkan regression bug di production saat deserialisasi data lama.

**Tantangan Arsitektur:**
1. Rancang dan implementasikan sebuah *In-Memory Abstract Event Store Engine* khusus environment test yang mengemulasikan semantics PostgreSQL Event Store lengkap dengan atomisitas transaksi, optimistic concurrency control via sequence revision number, namun murni berjalan di heap RAM Ruby (Zero Disk I/O).
2. Tulis sebuah custom RSpec DSL module bernama `EventSourcingTestKit`:
   - Menyediakan syntax deklaratif: `given_events([Event1, Event2]).when_executing(Command).then_events([EventExpected])`.
   - Mampu memvalidasi payload seluruh emitted events terhadap JSON Schema draft-07 secara otomatis di background tanpa konfigurasi tambahan pada setiap spec.
3. Buktikan bahwa implementasi test harness Anda mampu mengeksekusi 10.000 assertions event replay dalam waktu kurang dari 2 detik dengan Mutant coverage score 100% pada aggregate domain.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konsep Dasar (Basic)
1. **Apa perbedaan mendasar antara FactoryBot `build` dan `build_stubbed`?**
   - A. `build` menyimpan record ke database tanpa validasi, `build_stubbed` menjalankan validasi.
   - B. `build` menginstansiasi objek tanpa menyimpannya ke DB, sedangkan `build_stubbed` membuat objek dengan ID palsu dan men-stub persistensi seolah-olah sudah disimpan di DB.
   - C. `build_stubbed` membuat record di dalam in-memory SQLite database terpisah.
   - D. Keduanya identik, hanya alias sintaksis.

2. **Mengapa `instance_double` jauh lebih direkomendasikan dibandingkan generic `double` dalam RSpec?**
   - A. `instance_double` mengeksekusi method di thread terpisah.
   - B. `instance_double` memverifikasi bahwa method yang di-stub atau di-expect benar-benar ada pada class target model yang didefinisikan.
   - C. `instance_double` menggunakan memori 50% lebih sedikit.
   - D. Generic `double` dilarang oleh interpreter Ruby 3.

3. **Apa fungsi dari `ActiveRecord::TestFixtures` dengan transactional fixtures aktif?**
   - A. Melakukan `TRUNCATE TABLE` sebelum setiap test dimulai.
   - B. Menghapus database dan membuat migrasi baru untuk setiap example group.
   - C. Membuka database transaction di awal setiap example dan melakukan `ROLLBACK` di akhir example agar state kembali bersih secara instan.
   - D. Menyimpan data pengujian ke file CSV sementara.

4. **Kapan strategi pembersihan database `DatabaseCleaner.clean_with(:truncation)` wajib digunakan?**
   - A. Pada setiap Unit Test service object.
   - B. Ketika menguji pengiriman email dengan ActionMailer.
   - C. Pada End-to-End System Tests (misal: Capybara dengan browser driver terpisah) di mana webserver Rails dan browser driver berjalan pada thread/proses terpisah dari test runner.
   - D. Ketika testing custom validators pada ActiveRecord.

5. **Apa indikasi utama sebuah mutant dinyatakan "SURVIVED" pada Mutation Testing?**
   - A. Terjadi sintaks error pada kode aplikasi.
   - B. Kode sumber dimutasi, namun seluruh test suite tetap berstatus PASSED (hijau).
   - C. Test suite melempar unhandled exception.
   - D. Database koneksi terputus saat pengetesan berjalan.

---

#### Bagian B: Analisis Tingkat Lanjut (Intermediate)
6. **Perhatikan kode berikut. Apa risiko performa terbesarnya pada test suite berskala 10.000 test case?**
   ```ruby
   describe SubscriptionEngine do
     before(:all) do
       @user = FactoryBot.create(:user)
       @subscription = FactoryBot.create(:subscription, user: @user)
     end
   end
   ```
   - A. `before(:all)` tidak diizinkan oleh RSpec versi modern.
   - B. Objek yang dibuat pada blok `before(:all)` / `before(:context)` tidak dibungkus oleh per-example transactional rollback, sehingga datanya mengotori database untuk specs berikutnya dan memaksa eksekusi truncation lambat.
   - C. Data `@user` akan otomatis terhapus saat instance variable diakses.
   - D. RSpec akan mengeksekusi blok ini sebanyak 10 kali secara rekursif.

7. **Pada pengujian konkuren yang melibatkan multithreading dalam satu example, mengapa `ActiveRecord::Rollback` di `after(:example)` sering gagal membersihkan data yang dibuat di thread turunan?**
   - A. Thread turunan berjalan di sandbox memory V8.
   - B. Thread turunan mengambil koneksi database yang berbeda dari connection pool, dan transaksi yang dibuka oleh thread turunan tersebut melakukan commit independen di luar root transaction milik main test thread.
   - C. Ruby GVL mematikan transaksi database jika thread lebih dari satu.
   - D. ActiveRecord secara otomatis memblokir koneksi dari thread selain main thread.

8. **Bagaimana Knapsack algorithm mengoptimalkan eksekusi parallel test suite di CI pipeline?**
   - A. Mengompresi file spec menjadi format biner.
   - B. Membagi file spec ke worker nodes berdasarkan bobot historis durasi waktu eksekusi file, bukan sekadar jumlah file, guna mencegah bottleneck pada worker tertentu.
   - C. Mengubah spesifikasi Ruby menjadi parallel code C++ bindings.
   - D. Melewatkan (*skipping*) test yang jarang mengalami perubahan kode.

9. **Apa kegunaan opsi `joinable: false` pada internal implementasi Rails database transaction?**
   - A. Mencegah nested transaction block me-release atau me-rollback transaksi level root di luar kendalinya.
   - B. Memaksa database untuk melakukan query JOIN secara paralel.
   - C. Mematikan foreign key integrity checks.
   - D. Menggabungkan dua pool koneksi Postgres yang terpisah.

10. **Apa perbedaan antara `have_received` matcher dan `receive` message expectation pada RSpec Mocks?**
    - A. Tidak ada perbedaan fungsional.
    - B. `receive` mendefinisikan ekspektasi sebelum aksi dijalankan (*Mock*), sedangkan `have_received` memvalidasi bahwa message telah dipanggil setelah aksi dijalankan (*Spy*).
    - C. `have_received` hanya bisa digunakan untuk HTTP request calls.
    - D. `receive` mengeksekusi method asli tanpa stubbing.

---

#### Bagian C: Skenario Kasus Produksi (Production Scenarios)

11. **Skenario 1**:
    Sebuah tim microservices mengeluhkan CI pipeline mereka sering *intermittent failure* (merah acak) pada spec berikut:
    ```ruby
    it "expires the token after 1 hour" do
      user = create(:user)
      token = user.generate_token!
      sleep 3601 # Menunggu satu jam
      expect(token.reload.expired?).to be true
    end
    ```
    Selain masalah runtime execution, analisislah kegagalan arsitektural spec ini dan rancang solusi deterministik yang berjalan dalam orde milidetik!

12. **Skenario 2**:
    Pada monolitik Rails dengan PostgreSQL, Anda menemukan bahwa pengujian paralel menggunakan `parallel_tests` gem mengalami kegagalan deadlock acak pada baris:
    `PG::TRDeadlockDetected: ERROR: deadlock detected`.
    Setelah diselidiki, dua worker berbeda (`Worker 1` dan `Worker 2`) ternyata mengeksekusi model callbacks yang memanggil:
    `User.connection.execute("ALTER TABLE users AUTO_INCREMENT = 1")`.
    Jelaskan mengapa DDL operation ini menghancurkan isolasi concurrent test suite dan rekomendasikan restrukturisasi strateginya!

13. **Skenario 3**:
    Sebuah sistem checkout e-commerce memiliki integration spec yang memvalidasi callback pembayaran dari Stripe Webhook. Spesifikasi tersebut menggunakan stubbing:
    ```ruby
    allow(Stripe::Webhook).to receive(:construct_event).and_return(fake_event)
    ```
    Ketika Stripe SDK di-upgrade dari versi 5.x ke 11.x, nama parameter method `construct_event` berubah dan melempar argument error di environment staging. Mengapa test suite yang ada tidak menangkap error perubahan antarmuka library ini, dan bagaimana arsitektur pengujian seharusnya diperbaiki untuk mengantisipasi *library contract breaking changes*?

---

### Kunci Jawaban & Pembahasan Quiz

#### Bagian A: Dasar
1. **B** — `build_stubbed` adalah strategi in-memory penuh yang mensimulasikan persistence state (ID integer, `persisted? = true`) dan memblokir network/DB calls tanpa menyentuh PostgreSQL sama sekali.
2. **B** — `instance_double` mengikat target ke kelas aslinya. Jika method yang di-stub tidak ada pada kelas asli, RSpec akan langsung melempar exception, mencegah tes lolos padahal implementasi aslinya sudah berubah (*mock drift*).
3. **C** — Rails membungkus eksekusi test dalam level root transaction (`BEGIN`), mengeksekusi blok kode, lalu melempar `ROLLBACK` di `after(:example)`.
4. **C** — Truncation hanya dibutuhkan saat proses eksternal (seperti Webdriver / browser) perlu membaca basis data yang sama, di mana proses eksternal tersebut tidak dapat melihat uncommitted transactional fixtures dari main thread test runner.
5. **B** — Definisi *survived mutant* adalah mutasi kode buatan (misal operator logika dibalik) yang tetap menghasilkan test suite HIJAU. Hal ini membuktikan bahwa test case tidak menguji skenario logika tersebut secara tuntas (*assertion deficiency*).

#### Bagian B: Lanjutan
6. **B** — Data yang dibuat dalam `before(:all)` / `before(:context)` hidup di luar siklus rollback per-example. Data ini akan tertinggal di PostgreSQL database dan terbawa ke test case berikutnya, memicu *side-effects* dan *order-dependent failures*.
7. **B** — Setiap thread mengambil koneksi DB terpisah dari pool. Berdasarkan PostgreSQL ACID semantics, Thread A tidak dapat melihat uncommitted state milik Thread B kecuali data di-commit. Jika di-commit, data bocor keluar dari boundary transactional rollback.
8. **B** — Dynamic runtime bin-packing: Knapsack mendistribusikan file spec berdasarkan rekaman eksekusi waktu aktual sebelumnya, mencegah salah satu node CI bekerja 20 menit sementara node lain menganggur setelah 2 menit.
9. **A** — `joinable: false` menandai bahwa savepoint/transaksi internal yang dipanggil di dalam kode aplikasi tidak boleh mengubah siklus hidup rollback root transaction milik harness test.
10. **B** — `receive` adalah classical Mock (didefinisikan di awal/ARRANGE), sedangkan `have_received` mengimplementasikan Spies Pattern (ditegaskan di akhir/ASSERT), meningkatkan keterbacaan kode (Arrange-Act-Assert structure).

#### Bagian C: Skenario Kasus Produksi
11. **Pembahasan Skenario 1**:
    - *Kegagalan Arsitektural*: Penggunaan `sleep 3601` memblokir thread eksekusi selama 1 jam nyata, merusak throughput CI, dan rentan terhadap context switching OS timeout.
    - *Solusi Enterprise*: Gunakan `ActiveSupport::Testing::TimeHelpers`:
      ```ruby
      it "expires the token after 1 hour" do
        user = create(:user)
        token = user.generate_token!
        travel 1.hour + 1.second do
          expect(token.reload.expired?).to be true
        end
      end
      ```
      Ini memanipulasi representasi waktu internal Ruby Virtual Machine secara deterministik dalam hitungan fraksi mikrodetik tanpa threading sleep.
12. **Pembahasan Skenario 2**:
    - *Akar Masalah*: Perintah DDL (`ALTER TABLE`) meminta penguncian eksklusif tingkat tabel (*AccessExclusiveLock*) di PostgreSQL. Jika dua worker paralel mengakses database cluster yang sama atau mencoba mengubah relasi tabel bersamaan, terjadi dependency cycle antar lock request, menghasilkan Deadlock Exception.
    - *Solusi Enterprise*:
      1. Isolasi Database fisik per-worker menggunakan environment variable `TEST_ENV_NUMBER` pada `database.yml` (`myapp_test_1`, `myapp_test_2`).
      2. Hapus seluruh perintah DDL/Auto-increment resets dari runtime spec. Biarkan sequence integer berjalan natural; test assertions tidak boleh mengandalkan asumsi hardcoded ID (misal: jangan pernah menulis `expect(user.id).to eq(1)`).
13. **Pembahasan Skenario 3**:
    - *Akar Masalah*: Generic stubbing menggunakan `allow(...)` tanpa memverifikasi perubahan signature upstream SDK gem. Mocking dilakukan terlalu dangkal (*leaky abstraction*) pada 3rd-party library yang rentan terhadap antarmuka usang.
    - *Solusi Enterprise*:
      1. Gunakan `instance_double` atau aktifkan `mocks.verify_partial_doubles = true` di RSpec config untuk mendeteksi perubahan aritas atau method signature yang hilang secara statis.
      2. Terapkan **Adapter Pattern**: Bungkus SDK Stripe ke dalam internal wrapper service aplikasi (misal: `PaymentGateway::StripeAdapter`). Uji wrapper tersebut terhadap payload asli Stripe menggunakan VCR / WebMock network recording di level contract tests, lalu stub hanya internal wrapper adapter Anda pada level business logic unit test.

---

### 16. Summary

Implementasi Automated Testing & Quality Engineering kelas enterprise pada ekosistem Ruby on Rails melampaui sekadar penulisan syntax RSpec standar:
1. **Efisiensi Database**: Kunci kecepatan test suite berbanding lurus dengan minimnya I/O disk. Dominasi penggunaan `build_stubbed` dan isolasi PostgreSQL Transaction Savepoints merupakan fondasi wajib untuk test suite berskala puluhan ribu case.
2. **Mocking Hygiene**: Hilangkan *fragile assertions* dan *mock drift* dengan menerapkan *Verifying Doubles* (`instance_double`) dan *Spy Assertions* (`have_received`), serta isolasi third-party API via strict contract boundaries.
3. **Deterministik & Zero Flakiness**: Eliminasi mutasi global state, isolasi database per-worker core CPU, dan gantikan primitive time blocks dengan Time-travel sandboxing.
4. **Active Quality Assurance**: Mengukur ketahanan suite bukan hanya dari Code Coverage persentase (yang seringkali bias), melainkan menggunakan *Mutation Testing* (Mutant) untuk menjamin setiap baris logika bisnis memiliki pengujian yang benar-benar memvalidasi kegagalan regresi secara akurat.