# BAB-07: Testing Rigor & Static Analysis
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Principal Software Engineer dan Test Architect diharapkan mampu:
- **Merancang Arsitektur Pengujian Skala Enterprise**: Mengimplementasikan test suite RSpec deterministik berkecepatan tinggi dengan isolasi transaksi multi-database dan pengoptimalan alokasi memori.
- **Menguasai Internal Static Analysis & AST Ruby**: Mengembangkan *custom cops* pada RuboCop melalui manipulasi Abstract Syntax Tree (AST) dan mengintegrasikan Sorbet (`typed: strict`) untuk verifikasi statis dan runtime.
- **Mengeksekusi Mutation Testing**: Menjalankan evaluasi ketahanan kode menggunakan Mutant untuk memvalidasi efektivitas test suite hingga mencapai skor mutasi target (>85%).
- **Mengeliminasi Test Flakiness & Bottleneck CI**: Mengidentifikasi serta memperbaiki *order-dependent tests*, *state leakage*, memory bloat, dan menyusun pipeline paralelisasi pengujian berbasis beban runtime dinamis.

---

### 2. Prerequisites
Sebelum mendalami modul ini, Anda wajib memiliki pemahaman mendalam tentang:
- **Ruby Metaprogramming & Runtime**: Metaclass/Eigenclass, dynamic dispatch (`method_missing`, `define_method`), module prepending, dan bindings.
- **RSpec Core Fundamentals**: Lifecycle hooks (`before`, `after`, `around`), `let` vs `let!`, memoization, metadata, dan mock/stub lifecycle.
- **Database Transaction Primitives**: ACID, isolation levels, database savepoints, connection pools, dan mekanika rollback transaksi di PostgreSQL/MySQL.
- **Stateless Execution**: Thread safety, Global Variable contamination (`$`, `ENV`, Class Variables `@@`), dan manipulasi monotonic time.

---

### 3. Concept & Internal Architecture

#### 3.1 RSpec Core Engine & Execution Lifecycle
RSpec tidak mengeksekusi test suite secara linier seperti skrip biasa. RSpec Engine beroperasi dalam dua fase utama: **Definition Phase** dan **Execution Phase**.

```
[ Definition Phase ]
  CLI Options -> Configuration -> Runner -> Load Spec Files
                                               │
                                               ▼
                                      ExampleGroups & Examples
                                      (Hierarchical AST of Blocks)
                                               │
───────────────────────────────────────────────┼──────────────────────────────
                                               ▼
[ Execution Phase ]                   Spec Runner Core
                                               │
                   ┌───────────────────────────┴───────────────────────────┐
                   ▼                                                       ▼
            Hooks: suite/all                                        Hooks: suite/all
                   │                                                       │
                   ▼                                                       ▼
         [ ExampleGroup Run ]                                    [ ExampleGroup Run ]
                   │                                                       │
         ┌─────────┴─────────┐                                             │
         ▼                   ▼                                             │
    around(:each)      around(:each)                                       │
         │                   │                                             │
   before(:each)       before(:each)                                       │
         │                   │                                             │
   [Example Execution] [Example Execution]                                │
         │                   │                                             │
   after(:each)        after(:each)                                        │
```

- **Definition Phase**: RSpec mengevaluasi blok `RSpec.describe` dan `context`. Di fase ini, instance dari `RSpec::Core::ExampleGroup` dikonstruksi secara hierarkis. Evaluasi kode di luar blok `it`, `before`, atau `let` dijalankan hanya **sekali** pada tahap pemuatan (load-time), bukan per-test.
- **Execution Phase**: `RSpec::Core::Runner` memanggil `#run` pada root node kelompok pengujian. Setiap `Example` dieksekusi di dalam *instance unik* dari subclass `ExampleGroup`. Ini menjamin metode dan instance variable (`@var`) tidak bocor antar-contoh uji dalam kelas yang sama, meskipun resource global dan status database tetap dapat terkontaminasi jika tidak diisolasi.

#### 3.2 Abstract Syntax Tree (AST) & Parser Internals pada RuboCop
RuboCop menggunakan gem `parser` dan `rubocop-ast` untuk memecah source code Ruby menjadi format **s-expressions (S-specs)**.

```
Source Code:
  User.where(active: true).first

AST Tree Representation:
  (send
    (send
      (const nil :User) :where
      (hash
        (pair
          (sym :active)
          (true)))) :first)
```

Proses static analysis beroperasi via **Visitor Pattern**:
1. Source file dibaca dan diparsing menjadi node bertipe `RuboCop::AST::Node`.
2. RuboCop mengiterasi AST melalui `RuboCop::AST::Traversal`.
3. Node diproses menggunakan Pattern Matching Macro (`def_node_matcher`) atau inspeksi manual terhadap tipe node (`send`, `const`, `def`, `class`).
4. Jika node melanggar constraint arsitektur, Cop meregistrasikan pelanggaran (`add_offense`) dengan membawa `Parser::Source::Range` untuk auto-correction.

#### 3.3 Mutation Testing Internals (Mutant)
Mutation testing bukan sekadar mengukur seberapa banyak baris kode yang dieksekusi (*code coverage*), melainkan menguji apakah test suite benar-benar gagal ketika kode aplikasi diubah secara sengaja (*fault injection*).

```
   [ Original AST ] ──> Mutation Engine (Mutant) ──> [ Mutated AST (Killed/Survived?) ]
         │                                                      │
         ▼                                                      ▼
  foo > 0 ? bar : baz   ─── Mutation Operator (swap) ───>  foo >= 0 ? bar : baz
                        ─── Mutation Operator (nil)  ───>  nil
                        ─── Mutation Operator (drop) ───>  foo > 0 ? nil : baz
```

1. **AST Injection**: Mutant mem-parse source code ke AST via gem `parser`.
2. **Mutation Operators**: Mutant menerapkan serangkaian mutator terhadap node AST:
   - *Relational Operator Replacement* (`>` menjadi `>=`, `==` menjadi `!=`).
   - *Literal Replacement* (`true` menjadi `false`, `"string"` menjadi `""`, integer dimutasi).
   - *Statement Deletion* (menghapus pemanggilan method atau baris assignment).
3. **VM Bytecode Compilation**: Mutant mengompilasi kembali mutated AST ke bytecode Ruby VM (YARV) menggunakan `RubyVM::InstructionSequence`.
4. **Isolasi Evaluasi**: Test suite dijalankan terhadap kode termutasi.
   - **Killed**: Test suite gagal (`spec failure`). Kode mutan terdeteksi. Target terpenuhi.
   - **Survived**: Test suite tetap hijau/lolos (`spec pass`). Pengujian memiliki *blind spot* kritis.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Ad-hoc) | Pendekatan Enterprise Rigor |
| :--- | :--- | :--- |
| **Database Isolation** | Truncation table manual atau recreate schema per-run. | Nested Transaction Savepoints via Connection Pools berkinerja tinggi. |
| **Code Quality Gate** | Review manual dan RuboCop konfigurasi default. | Custom Cops penegak Boundary Arsitektur + Static Typing Sorbet (`typed: strict`). |
| **Test Quality Metric** | Line Coverage standard (SimpleCov 100%). | Mutation Score (`mutant`) > 85% untuk critical enterprise domain core. |
| **CI Execution Time** | Serial / Basic split per-file. | Dynamic Knapsack parallelization terbagi berdasarkan execution histogram. |
| **Memory Lifecycle** | Test runner dibiarkan mengalami leak memori hingga swap. | Profiling alokasi object RSpec & pembersihan memoized global state per batch. |

- **Mengapa pendekatan konvensional gagal pada skala enterprise?** 
  Cakupan 100% line coverage dapat dicapai tanpa assertion tunggal (hanya mengeksekusi path). Flakiness meningkat seiring bertambahnya stateful mock. Pada sistem perbankan atau sistem transaksi kritis, false positive pada test suite dapat mengakibatkan bug finansial lolos ke production.
- **Apa yang ditawarkan enterprise testing rigor?**
  Verifikasi matematis keabsahan state melalui assertion ketat, validasi AST otomatis untuk mencegah *architectural erosion*, dan kepastian bahwa setiap baris kode domain dilindungi oleh test yang benar-benar memvalidasi logika bisnis.

---

### 5. How: Workflow Detail Arsitektur Pengujian Enterprise

Langkah integrasi pipeline testing enterprise:

```
[ Developer Commit / Push ]
           │
           ▼
[ Phase 1: Fast-Fail Linting & Static Types ]
  ├── Sorbet Static Typing Verification (`srb tc`)
  ├── Brakeman Security AST Scan
  └── RuboCop Lint + Custom Architecture Cops
           │
           ▼ (Success)
[ Phase 2: Unit, Domain, & Contract Specs ]
  ├── RSpec Isolated Execution (In-Memory / Savepoints)
  └── Dynamic Parallelism via Test Splitter Engine
           │
           ▼ (Success)
[ Phase 3: Verification of Test Suite Resilience ]
  └── Mutation Testing (Mutant) on Critical Domain Diffs
           │
           ▼ (Score >= Target)
[ Build Ready for Artifact Packaging ]
```

1. **Local Pre-commit / Early CI**: Eksekusi static type check dan lint AST (<10 detik). Tidak ada database yang dimuat.
2. **Dynamic Splitting CI Nodes**: Runner membagi pengujian berdasarkan timing metadata JSON dari eksekusi sebelumnya, bukan sekadar jumlah file spec.
3. **Mutation Gate**: Kode baru dianalisis secara inkremental via git diff. Jika mutan lolos dari test suite baru, build dinyatakan gagal.

---

### 6. Analogy & Architecture Diagram

#### Analogi: Inspeksi Pabrik Pesawat Komersial
- **SimpleCov / Line Coverage** adalah seperti mencatat apakah seorang inspektur telah *berjalan melewati* setiap ruang kabin pesawat. Berjalan melewatinya tidak membuktikan apakah mesin berfungsi.
- **Mutation Testing** adalah seperti teknisi sengaja melepaskan satu kabel secara acak (*fault injection*), lalu memeriksa: **Apakah alarm kokpit berbunyi?** Jika alarm tidak berbunyi, prosedur inspeksi gagal.
- **RuboCop AST Analysis** adalah pemindai dimensi sinar-X otomatis pada cetak biru struktur pesawat: mendeteksi ketidaksesuaian standar struktural sebelum material dipotong.

#### Database Isolation Levels Diagram
```
Physical Database Engine (PostgreSQL)
  └── Connection Pool
        └── BEGIN (Global Test Transaction)
              │
              ├── SAVEPOINT test_point_1
              │     ├── Spec 1 inserts User (id: 1)
              │     ├── Spec 1 verifies User presence
              │     └── ROLLBACK TO SAVEPOINT test_point_1
              │
              ├── SAVEPOINT test_point_2
              │     ├── Spec 2 queries User (Result: Empty / Clean DB)
              │     └── ROLLBACK TO SAVEPOINT test_point_2
              │
              └── ROLLBACK (Global Test Transaction teardown)
```

---

### 7. Implementation Examples

#### 7.1 Custom RSpec Matcher (Value Object Invariant Verification)
Membuat matcher kustom yang mengecek invariant domain dan memberikan pesan error terperinci ketika terjadi failure pada event-driven ledger.

```ruby
# lib/rspec/matchers/be_valid_ledger_entry.rb
# frozen_string_literal: true

require 'rspec/expectations'

RSpec::Matchers.define :be_valid_ledger_entry do |expected_currency|
  match do |actual_entry|
    return false unless actual_entry.respond_to?(:debit_amount) && actual_entry.respond_to?(:credit_amount)
    return false unless actual_entry.currency == expected_currency
    
    # Invariant: Double-entry must balance or have positive divergence strictly isolated
    @balance = actual_entry.debit_amount - actual_entry.credit_amount
    @balance.zero? && actual_entry.timestamp <= Time.now
  end

  failure_message do |actual_entry|
    "Expected #{actual_entry.inspect} to be a valid balanced ledger entry in #{expected_currency}, " \
    "but resulted in delta: #{@balance} and currency: #{actual_entry.currency}"
  end

  failure_message_when_negated do |actual_entry|
    "Expected #{actual_entry.inspect} NOT to be a valid ledger entry in #{expected_currency}, but it passed invariants."
  end

  description do
    "be a balanced ledger entry strictly denominated in #{expected_currency}"
  end
end
```

#### 7.2 Custom RuboCop Rule: Enforce Immutable Data Layer
Mendeteksi pemanggilan destructive method (`save!`, `update!`, `delete`) di dalam Read-Model Query Service melalui Abstract Syntax Tree inspection.

```ruby
# lib/rubocop/cop/architecture/no_write_in_query_service.rb
# frozen_string_literal: true

require 'rubocop'

module RuboCop
  module Cop
    module Architecture
      class NoWriteInQueryService < Base
        MSG = 'Query services must be read-only. Destructive mutation method `.%s` is strictly prohibited.'
        RESTRICT_ON_SEND = %i[save save! update update! create create! delete destroy destroy!].freeze

        def on_send(node)
          return unless inside_query_service_class?(node)

          method_name = node.method_name
          add_offense(node.loc.selector, message: format(MSG, method_name))
        end

        private

        def inside_query_service_class?(node)
          class_node = node.each_ancestor(:class).first
          return false unless class_node

          class_name = class_node.identifier.const_name
          class_name.end_with?('QueryService', 'Query', 'ReadRepository')
        end
      end
    end
  end
end
```

#### 7.3 Sorbet Strict Typing & Spec Rigor
Implementasi command service domain finansial dengan Sorbet typing level `strict` beserta unit test yang membuktikan boundary exception.

```ruby
# typed: strict
# app/services/banking/transfer_funds_service.rb
# frozen_string_literal: true

module Banking
  class TransferFundsService
    extend T::Sig

    class InsufficientFundsError < StandardError; end
    class InvalidCurrencyError < StandardError; end

    sig { params(source_account_id: String, target_account_id: String, amount_cents: Integer, currency: String).returns(String) }
    def self.call(source_account_id:, target_account_id:, amount_cents:, currency:)
      raise InvalidCurrencyError, "Currency #{currency} not supported" unless %w[USD IDR EUR].include?(currency)
      raise InsufficientFundsError, "Amount must be strictly positive" if amount_cents <= 0

      # Return generated transaction reference
      "TXN-#{SecureRandom.uuid}"
    end
  end
end
```

Unit Test Spec:

```ruby
# spec/services/banking/transfer_funds_service_spec.rb
# frozen_string_literal: true

require 'spec_helper'

RSpec.describe Banking::TransferFundsService do
  describe '.call' do
    let(:source_id) { "ACC-100" }
    let(:target_id) { "ACC-200" }
    let(:currency)  { "IDR" }

    it 'generates a deterministic transaction prefix when inputs are valid' do
      result = described_class.call(
        source_account_id: source_id,
        target_account_id: target_id,
        amount_cents: 10_000_000,
        currency: currency
      )

      expect(result).to start_with('TXN-')
    end

    it 'raises InsufficientFundsError when amount is zero or negative' do
      expect {
        described_class.call(
          source_account_id: source_id,
          target_account_id: target_id,
          amount_cents: 0,
          currency: currency
        )
      }.to raise_error(Banking::TransferFundsService::InsufficientFundsError, /Amount must be strictly positive/)
    end

    it 'raises InvalidCurrencyError when unmapped ISO currency is provided' do
      expect {
        described_class.call(
          source_account_id: source_id,
          target_account_id: target_id,
          amount_cents: 50_000,
          currency: "XYZ"
        )
      }.to raise_error(Banking::TransferFundsService::InvalidCurrencyError, /XYZ not supported/)
    end
  end
end
```

---

### 8. Real-World Case Study: Core Settlement Engine Test Pipeline

#### Konteks Masalah
Sebuah platform fintech memproses transaksi settlement antar-bank sebesar Rp 4 Triliun per hari. Test suite aplikasi tersebut terdiri dari 4.500 specs dengan masalah:
1. Waktu eksekusi CI memakan waktu **42 menit**, memperlambat siklus release.
2. Sering terjadi kegagalan acak (*flakiness* sebesar ~6% pada test runs) yang disebabkan oleh *state leak* database dan manipulasi `Timecop` global yang tidak di-reset.
3. Target audit keuangan menemukan bahwa branch coverage 94% tetap meloloskan bug pembulatan desimal ke staging.

#### Arsitektur Solusi
Engine testing ditata ulang dengan blueprint berikut:

```
[ CI Runner Initializer ]
         │
         ├── Step 1: Pre-run Invariant Validation (No ENV mutations allowed)
         │
         ├── Step 2: In-Memory PostgreSQL Schema via RAMDisk (`/dev/shm`)
         │
         ├── Step 3: Test Split Engine (Knapsack based on CPU/Time variance)
         │     ├── Worker 1: Core Financial Ledger Specs (Parallel Node A)
         │     ├── Worker 2: Settlement Batches (Parallel Node B)
         │     └── Worker 3: Edge Invariants & Integration (Parallel Node C)
         │
         └── Step 4: Mutant Verification Pipeline on `lib/settlement/`
```

1. **Transaction Isolation**: Mengganti strategi DatabaseCleaner `truncation` menjadi native transaction hooks dengan explicit PostgreSQL connection pools via savepoints. Waktu setup-teardown terpangkas dari 18ms per spec menjadi 0.8ms per spec.
2. **Mutant Configuration (`.mutant.yml`)**:
```yaml
includes:
  - lib
requires:
  - config/environment
integration:
  name: rspec
matcher:
  subjects:
    - Settlement::CalculationEngine*
    - Settlement::FeeDistributor*
threshold:
  coverage: 100.0
```
3. **Penyelesaian Time Leak**: Mengganti pustaka `Timecop` dengan native `ActiveSupport::Testing::TimeHelpers` (`travel_to`) yang dieksekusi via `around(:each)` blocks dengan strict auto-restore.

#### Hasil
- CI execution time turun dari **42 menit** menjadi **4 menit 15 detik** (paralelisasi 8 node).
- Flakiness turun menjadi **0%** dalam kurun waktu 90 hari operasional.
- Mutant mendeteksi **14 unhandled mutants** pada engine pembulatan kurs valuta asing yang sebelumnya lolos dari unit test konvensional.

---

### 9. Trade-offs & Deep Architectural Analysis

| Keputusan Arsitektur | Keuntungan | Biaya & Kompensasi (Trade-offs) |
| :--- | :--- | :--- |
| **Transactional Fixtures vs Truncation Strategy** | Kecepatan eksekusi naik hingga 15-20x lipat; overhead I/O minimal. | Tidak dapat mendeteksi bug isolation levels yang sebenarnya di database concurrency (e.g., Phantom Reads, multi-threaded test cases). Solusi: Jalankan spec multi-thread dengan truncation terisolasi secara terpisah. |
| **Sorbet Strict (`typed: strict`)** | Menghilangkan class error nil-pointer/type mismatch pada compile time; mendokumentasikan input-output secara deterministik. | Menghilangkan fleksibilitas dynamic metaprogramming khas Ruby. Memerlukan penulisan RBI (Ruby Interface) files untuk gem pihak ketiga yang belum bertipe. |
| **Mutation Testing (Mutant)** | Menjamin ketahanan test assertion secara matematis; mengekspos false-positive branch coverage. | Mengonsumsi CPU intensif; eksekusi mutation run pada seluruh codebase enterprise memakan waktu berjam-jam. Wajib dibatasi pada *git diff* atau domain modul inti (*core aggregates*). |
| **In-Memory RAMDisk Database (`/dev/shm`)** | I/O disk zero-latency; operasi database setara dengan kecepatan memory access. | Memori server CI harus besar. Hilangnya persistensi saat runner restart (bukan masalah untuk transient CI). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Global State Leaks via Thread/Class Variables
- **Kesalahan Fatal**:
  ```ruby
  # Anti-pattern: Mengubah status class variable di dalam spec
  it 'sets current currency context' do
    CurrencyContext.current_currency = 'USD'
    expect(Ledger.calculate).to eq(100)
  end
  # Jika test berikutnya berjalan, CurrencyContext.current_currency tetap 'USD'!
  ```
- **Solusi Enterprise (Around Block Sandbox)**:
  ```ruby
  around(:each) do |example|
    original_currency = CurrencyContext.current_currency
    example.run
  ensure
    CurrencyContext.current_currency = original_currency
  end
  ```

#### 10.2 AST Node Matching Mismatch pada Custom RuboCop
- **Penyebab**: Menulis AST matcher tanpa memperhitungkan variasi pemanggilan method Ruby, seperti safe navigation (`&.`) atau blok tanda kurung kurawal vs `do...end`.
- **Diagnosis**: Gunakan command parser internal untuk memeriksa struktur node:
  ```bash
  ruby-parse -e "User&.save!(validate: false)"
  ```
  Output S-Expression menunjukkan node adalah `csend` (conditional send), bukan `send`. Jika cop hanya mengecek `on_send`, safe navigation method call akan terlewati (lolos dari deteksi).

#### 10.3 Mock Leaks & `any_instance_of` Anti-Pattern
- **Masalah**: Penggunaan `allow_any_instance_of(PaymentGateway).to receive(...)` memodifikasi class table global pada runtime Ruby VM. Jika RSpec runner terinterupsi atau mengalami timeout, method stub tidak ter-unmock dengan sempurna, mencemari test berikutnya.
- **Solusi**: Gunakan explicit dependency injection:
  ```ruby
  # Gunakan verified instance doubles dan injeksikan langsung
  let(:mock_gateway) { instance_double(PaymentGateway) }
  let(:service) { ProcessPaymentService.new(gateway: mock_gateway) }
  ```

---

### 11. Best Practices & Production Checklist

#### Production Checklist Table
- [ ] **Gems Lock**: Versi `rspec-core`, `rubocop`, `sorbet`, dan `mutant` terkunci via `Gemfile.lock` dengan checksum SHA256 terverifikasi.
- [ ] **Deterministic Seed**: Flag `--order rand:<seed>` selalu dicatat pada artefak CI untuk memungkinkan reproduksi exact sequence saat test gagal.
- [ ] **Zero Global Mock**: Tidak ada penggunaan `any_instance_of` dalam codebase.
- [ ] **Static Analysis Enforcement**: Pipeline CI memvalidasi `srb tc` dan `bundle exec rubocop` sebelum job RSpec dimulai.
- [ ] **Memory Leak Check**: Monitoring object allocations via `GC.stat` pada suite runs untuk mendeteksi memory degradation.
- [ ] **Fail-Fast Policy**: Konfigurasikan `--fail-fast=3` pada level local container untuk mempercepat feedback loop developer.

---

### 12. Hands-on Practice: Membangun Enterprise Testing Harness

Simpan seluruh file berikut ke direktori workspace: `hands-on/m02/`

#### Struktur Proyek
```
hands-on/m02/
├── .rubocop.yml
├── Gemfile
├── lib/
│   ├── arch_cops/
│   │   └── enforce_service_immutability.rb
│   └── domain/
│       └── ledger_allocator.rb
└── spec/
    ├── spec_helper.rb
    ├── arch_cops/
    │   └── enforce_service_immutability_spec.rb
    └── domain/
        └── ledger_allocator_spec.rb
```

#### Langkah 1: Siapkan `Gemfile`
```ruby
# hands-on/m02/Gemfile
source 'https://rubygems.org'

gem 'rspec', '~> 3.12'
gem 'rubocop', '~> 1.57'
gem 'rubocop-ast', '~> 1.30'
gem 'sorbet-runtime', '~> 0.5'
```
Jalankan di shell:
```bash
bundle install
```

#### Langkah 2: Buat Domain Code dengan Sorbet Runtime
```ruby
# hands-on/m02/lib/domain/ledger_allocator.rb
# frozen_string_literal: true
require 'sorbet-runtime'

module Domain
  class LedgerAllocator
    extend T::Sig

    AllocatedLine = Struct.new(:target, :amount, :ratio)

    sig { params(total_cents: Integer, ratios: T::Array[Float]).returns(T::Array[AllocatedLine]) }
    def self.allocate(total_cents, ratios)
      raise ArgumentError, "Total must be non-negative" if total_cents < 0
      
      sum_ratios = ratios.sum
      raise ArgumentError, "Ratios sum must equal 1.0" unless (sum_ratios - 1.0).abs < 0.0001

      remainder = total_cents
      results = []

      ratios.each_with_index do |ratio, idx|
        if idx == ratios.length - 1
          # Invariant: Last party gets the exact remainder to eliminate rounding leaks
          results << AllocatedLine.new("TARGET_#{idx}", remainder, ratio)
        else
          share = (total_cents * ratio).floor
          remainder -= share
          results << AllocatedLine.new("TARGET_#{idx}", share, ratio)
        end
      end

      results
    end
  end
end
```

#### Langkah 3: Buat Custom RuboCop Rule
Mencegah deklarasi variable instance (`@variable`) secara langsung di dalam class bertipe `Allocator`.
```ruby
# hands-on/m02/lib/arch_cops/enforce_service_immutability.rb
# frozen_string_literal: true
require 'rubocop'

module ArchCops
  class EnforceServiceImmutability < RuboCop::Cop::Base
    MSG = 'Direct assignment to instance variables (@) inside stateless Domain engines is prohibited.'

    def on_ivasgn(node)
      class_node = node.each_ancestor(:class).first
      return unless class_node

      class_name = class_node.identifier.const_name
      if class_name.end_with?('Allocator')
        add_offense(node.loc.name)
      end
    end
  end
end
```

#### Langkah 4: Tulis Spec Helper & Domain Unit Tests
```ruby
# hands-on/m02/spec/spec_helper.rb
# frozen_string_literal: true
require 'rspec'
require_relative '../lib/domain/ledger_allocator'

RSpec.configure do |config|
  config.order = :random
  Kernel.srand config.seed
  config.disable_monkey_patching!
  config.warnings = true
end
```

```ruby
# hands-on/m02/spec/domain/ledger_allocator_spec.rb
# frozen_string_literal: true
require_relative '../spec_helper'

RSpec.describe Domain::LedgerAllocator do
  describe '.allocate' do
    it 'distributes odd values precisely without leaking pennies' do
      # Kasus pembagian 100 sen ke 3 pihak (0.33, 0.33, 0.34)
      distribution = described_class.allocate(100, [0.33, 0.33, 0.34])

      total_allocated = distribution.sum(&:amount)
      expect(total_allocated).to eq(100)
      expect(distribution.map(&:amount)).to eq([33, 33, 34])
    end

    it 'raises ArgumentError if ratios do not equal 1.0' do
      expect {
        described_class.allocate(100, [0.5, 0.2])
      }.to raise_error(ArgumentError, /Ratios sum must equal 1.0/)
    end

    it 'raises ArgumentError when total_cents is negative' do
      expect {
        described_class.allocate(-50, [1.0])
      }.to raise_error(ArgumentError, /Total must be non-negative/)
    end
  end
end
```

#### Langkah 5: Eksekusi Test dan Validasi
Jalankan spec dari direktori `hands-on/m02/`:
```bash
bundle exec rspec spec/domain/ledger_allocator_spec.rb --format documentation
```

---

### 13. Exercises

#### Level Easy
Buat custom RSpec predicate matcher `be_monotonically_increasing` yang memverifikasi bahwa sebuah array integer bertambah secara berurutan tanpa penurunan nilai (contoh: `[1, 2, 2, 4]` lolos, `[1, 3, 2]` gagal). Pastikan matcher menghasilkan pesan error failure yang menyebutkan index dan nilai yang melanggar.

#### Level Medium
Kembangkan custom RuboCop cop (`Cop/Performance/AvoidRubyTimeNow`) yang mendeteksi penggunaan `Time.now` dalam direktori `app/services/` dan secara otomatis memperbaikinya (*autocorrect*) menjadi `Time.current` untuk menjaga konsistensi zona waktu.

#### Level Hard
Rancang test engine yang mengabstraksi eksekusi batch specs ke dalam dynamic transaction rollbacks. Buat framework harness yang menerima arbitrary blocks, membungkus eksekusinya ke dalam nested PostgreSQL savepoints via Ruby `Thread`, dan memvalidasi bahwa koneksi database secara absolut tidak mengalami kebocoran status/lock setelah block selesai dieksekusi secara konkuren.

---

### 14. Challenge: Arsitektur Self-Healing Deterministic Test Pipeline

**Skenario**:
Anda ditugaskan sebagai Lead Architect pada enterprise payment unicorn. Sistem memiliki 15.000 test specs yang berjalan selama 1 jam 15 menit pada CI. Sebanyak 12% kegagalan CI bersifat *non-deterministic* (flaky) yang umumnya terselesaikan hanya dengan me-rerun build. Selain itu, compliance audit PCI-DSS mewajibkan 100% mutasi terbunuh (*zero surviving mutants*) pada library settlement `VaultCore`.

**Kebutuhan Desain**:
1. Rancang arsitektur pipeline CI yang memisahkan specs ke dalam 3 tier isolasi (*Purity Layers*):
   - Tier 0: Pure Memory AST / Functional (Zero side-effect, run in parallel < 30 detik).
   - Tier 1: Transaction-Isolated Database Specs (Savepoint-managed, multi-core worker).
   - Tier 2: Real I/O, Third-party Gateway, & Asynchronous Workers.
2. Buat mekanisme **AST Mutation-Detection Engine** yang berjalan di git pre-push hook: Hanya file yang dimodifikasi dan specs dependensinya yang dieksekusi oleh Mutant runner.
3. Rancang isolasi memori: Hilangkan dependency leak antar spec akibat polusi memori ObjectSpace tanpa me-restart Ruby VM di setiap file.

*Deliverable*: Dokumentasi arsitektur, diagram alur eksekusi proses, dan implementasi custom RSpec runner extension (`RSpec::Core::Formatters` atau monkey-patch hook resmi) yang merekam metrik degradasi alokasi heap Ruby per ExampleGroup.

---

### 15. Evaluasi Pemahaman (Quiz)

#### Bagian 1: Basic (5 Pertanyaan)
1. Kapan kode di dalam blok `RSpec.describe` dieksekusi oleh RSpec runner?
   - A. Tepat sebelum setiap blok `it` dieksekusi.
   - B. Pada Definition Phase saat spec files dimuat ke memori.
   - C. Hanya ketika ada assertion yang gagal.
   - D. Di dalam loop thread worker database.

2. Mengapa penggunaan `let` dianjurkan dibandingkan mendefinisikan instance variable (`@var`) di dalam blok `before(:each)`?
   - A. `let` di-evaluasi secara lazy (hanya saat dipanggil), mengurangi alokasi memori yang tidak dibutuhkan.
   - B. `let` tidak menggunakan alokasi memori heap Ruby.
   - C. Instance variable `@var` dibagikan (*shared*) ke seluruh ExampleGroup lain secara global.
   - D. `let` mengeksekusi thread baru untuk setiap pemanggilan.

3. Apa perbedaan fundamental antara Line Coverage (SimpleCov) dan Mutation Score (Mutant)?
   - A. Line Coverage menguji performa, Mutation Score menguji keamanan.
   - B. Line Coverage hanya menandai baris yang dilewati eksekusi; Mutation Score memvalidasi apakah pengujian gagal jika logika baris tersebut diubah.
   - C. Mutation score hanya dapat dihitung pada static types.
   - D. Line Coverage memerlukan compiler, Mutation Score dijalankan pada level AST.

4. Pada RuboCop AST, tipe node apa yang merepresentasikan pemanggilan method seperti `account.debit(500)`?
   - A. `def`
   - B. `send`
   - C. `args`
   - D. `block`

5. Apa efek samping utama penggunaan `allow_any_instance_of` pada RSpec?
   - A. Memperlambat koneksi database.
   - B. Memodifikasi class table secara global pada runtime Ruby VM yang berisiko bocor ke test lain jika teardown gagal.
   - C. Menghapus method asli secara permanen dari file source code.
   - D. Mengharuskan Ruby dijalankan dalam mode multi-threading.

---

#### Bagian 2: Intermediate (5 Pertanyaan)
6. Perhatikan potongan kode berikut:
   ```ruby
   RSpec.describe LedgerWorker do
     let!(:account) { create(:account, balance: 1000) }
     
     context 'when updating' do
       before { Thread.current[:active_account] = account }
       it 'processes balance' do
         expect(LedgerWorker.run).to be_truthy
       end
     end
   end
   ```
   Mengapa pengujian di atas berpotensi menimbulkan *flakiness* pada suite berskala besar?
   - A. `let!` tidak mendukung pembuatan model Active Record.
   - B. `Thread.current` tidak dibersihkan via `after`/`ensure`, sehingga status thread berpotensi bocor ke spec lain yang menggunakan worker thread yang sama.
   - C. `be_truthy` bukan matcher valid di RSpec.
   - D. Database rollback otomatis membersihkan data thread context.

7. Mengapa static type checker Sorbet (`typed: strict`) mewajibkan penulisan signature (`sig`) pada setiap method?
   - A. Agar Ruby dapat mengompilasi method tersebut menjadi native C binary.
   - B. Untuk menghilangkan dynamic runtime overhead 100%.
   - C. Agar verifikasi tipe dapat dibuktikan secara statis tanpa harus menjalankan kode, serta memvalidasi kesesuaian tipe input/output saat runtime.
   - D. Karena Ruby VM tidak mendukung dynamic dispatch tanpa metadata tipe.

8. Dalam strategi Database Cleaner, apa kelemahan mendasar dari strategi `truncation` dibandingkan dengan strategi `transaction`?
   - A. `truncation` tidak menghapus data secara bersih.
   - B. `truncation` memaksa reset schema database setiap kali dijalankan.
   - C. `truncation` melakukan I/O disk penuh dengan menerbitkan perintah `TRUNCATE TABLE` untuk setiap tabel, yang secara signifikan jauh lebih lambat daripada `ROLLBACK TO SAVEPOINT`.
   - D. `transaction` tidak bekerja pada PostgreSQL.

9. Apa yang terjadi jika sebuah mutan dinyatakan *Survived* dalam mutation testing?
   - A. Seluruh test suite Anda berhasil membuktikan error pada mutan.
   - B. Kode mutan yang disuntikkan gagal dieksekusi karena syntax error.
   - C. Kode aplikasi telah dimodifikasi perilakunya, tetapi test suite tetap bernilai hijau (pass), mengindikasikan assertion yang lemah.
   - D. Compiler Ruby membatalkan mutasi secara otomatis.

10. Pada arsitektur AST RuboCop, metode apa yang digunakan untuk mencari node tertentu di dalam tree turunan tanpa rekursi manual?
    - A. `node.ancestors`
    - B. `node.each_node(:send)`
    - C. `node.children.first`
    - D. `node.dig_node(:target)`

---

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario Deadlock Database pada Parallel Spec**:
    Anda mengonfigurasi paralelisasi pengujian RSpec menjadi 8 worker processes menggunakan database yang sama secara konkuren. Tiba-tiba, test suite mengalami `ActiveRecord::Deadlocked` atau *PostgreSQL Lock Acquisition Timeout* secara acak pada tabel `tenants`.
    Langkah arsitektur apa yang **paling tepat** untuk mengeliminasi issue ini secara permanen?
    - A. Menurunkan timeout transaksi database ke 1 milidetik.
    - B. Mengonfigurasi database terisolasi untuk masing-masing worker process (e.g., `test_db_1`, `test_db_2`) menggunakan environment variable `TEST_ENV_NUMBER`.
    - C. Menggunakan mutex global pada spec helper untuk memaksa test berjalan sinkron pada tabel `tenants`.
    - D. Mengubah isolation level database production menjadi `READ UNCOMMITTED`.

12. **Skenario Flaky Spec Akibat Pergeseran Waktu**:
    Sebuah test suite perbankan memvalidasi kedaluwarsa token:
    ```ruby
    it 'validates token expiration' do
      token = Token.generate(expires_in: 1.hour)
      Timecop.freeze(Time.now + 3601)
      expect(token.expired?).to be true
    end
    ```
    Spec ini sesekali gagal di pipeline CI saat server sedang mengalami beban CPU tinggi. Apa akar masalah teknisnya dan mitigasi enterprise terbaiknya?
    - A. Token di database terhapus secara otomatis oleh cronjob; jalankan ulang runner.
    - B. `Time.now` dipanggil dua kali tanpa pembekuan waktu awal yang deterministik, menyebabkan perbedaan beberapa mikrodetik pada evaluasi logika; mitigasi dengan membungkus blok menggunakan `Timecop.freeze(Time.zone.at(fixed_timestamp)) { ... }` atau helper native `travel_to`.
    - C. Garbage Collection Ruby membebaskan memory token secara prematur.
    - D. Database clock dan host CPU clock tidak tersinkronisasi via NTP.

13. **Skenario AST Auto-Correct Rusak**:
    Anda menulis custom Cop untuk memodifikasi pemanggilan method deprecated `LegacyBilling.charge(amount, user)` menjadi `NewBilling.charge(user: user, amount: amount)`. Ketika autocorrect dijalankan (`rubocop -A`), kode berubah menjadi format yang invalid: `NewBilling.charge(user: user, amount: amount).baris_berikutnya`.
    Apa penyebab kegagalan tersebut pada level manipulasi AST?
    - A. Parser Ruby tidak mengizinkan pergantian method arguments.
    - B. `corrector.replace` menggunakan `node.source_range` yang overlap atau tidak memperhitungkan node end range dengan tepat, sehingga memotong baris berikutnya; solusinya adalah memanfaatkan range selector yang tepat (`node.loc.expression`).
    - C. File source code tidak memiliki header `# frozen_string_literal: true`.
    - D. RuboCop tidak mendukung keyword arguments dalam AST auto-correction engine.

---

#### Kunci Jawaban Quiz

##### Bagian 1: Basic
1. **B** — Definition Phase mengevaluasi blok hierarki deskriptor saat file dimuat sebelum test runner mengeksekusi assertion.
2. **A** — `let` melakukan komputasi secara lazy ketika variabel pertama kali dipanggil, menghindari alokasi memori yang tidak dibutuhkan.
3. **B** — Line coverage hanya memvalidasi execution path; Mutation testing memvalidasi efektivitas assertion dengan menyuntikkan defect buatan ke source code.
4. **B** — Pemanggilan method dalam representasi AST Ruby diklasifikasikan sebagai node `send`.
5. **B** — `allow_any_instance_of` mengubah metaclass secara global di Ruby VM dan berisiko bocor jika teardown lifecycle mengalami crash.

##### Bagian 2: Intermediate
6. **B** — Penyimpanan state pada `Thread.current` tanpa mekanisme pembersihan pasti (`ensure`) mencemari konteks thread worker lain yang di-reuse oleh test pool.
7. **C** — Sorbet Strict menuntut signature lengkap agar analisis graf dependensi statis dapat dibuktikan sebelum runtime, dan runtime checker memvalidasi parameter saat dieksekusi.
8. **C** — `truncation` mengeksekusi operasi DDL/DML berat ke disk database fisik untuk mereset data, sedangkan `transaction` hanya mengeksekusi rollback memory savepoint.
9. **C** — Survived mutant berarti aplikasi diubah logikanya menjadi salah, tetapi test suite Anda tetap lolos (tidak ada assertion yang mendeteksi kerusakan).
10. **B** — `node.each_node(:type)` adalah traversal generator RuboCop untuk menyaring seluruh subtree yang memiliki tipe node tersebut.

##### Bagian 3: Skenario Kasus Produksi
11. **B** — Menggunakan multi-tenancy database per process (`test_db_N`) mengisolasi resource locking secara fisik di level DBMS, menghilangkan resource contention antar-process.
12. **B** — Pemanggilan dynamic time tanpa baseline absolut rentan terhadap microsecond precision drift di server CI. Baseline waktu statis deterministik wajib diisolasi penuh.
13. **B** — Kesalahan manipulasi range buffer AST terjadi ketika perhitungan boundary text (`Parser::Source::Range`) menimpa token diluar expression node yang ditargetkan.

---

### 16. Summary

Testing rigor dan static analysis pada skala enterprise mentransformasi test suite dari sekadar formalitas checklist menjadi **sistem jaminan kualitas deterministik**.

1. **RSpec Internals**: Pemisahan jelas antara *definition phase* dan *execution phase* mencegah alokasi memori berlebih dan *leakage* antar unit pengujian. Hindari modifikasi global environment tanpa *safe unwinding* via `ensure`.
2. **Static Architecture Guardrails**: Penggunaan AST traversal via **RuboCop Custom Cops** bertindak sebagai *linter arsitektur* otomatis yang mencegah *anti-patterns* menembus production.
3. **Formal Contract Typing**: **Sorbet** mengonversi sifat open-ended Ruby menjadi sistem bertipe ketat (`typed: strict`), menangkap *type divergence* dan potensi nil-pointer exception sebelum kode masuk ke proses eksekusi test.
4. **Validasi Kualitas Assertion**: **Mutation Testing (Mutant)** menembus ilusi semu "100% Code Coverage" dengan membuktikan secara matematis bahwa test suite Anda memiliki kapabilitas untuk mendeteksi *fault injection* pada domain logika bisnis kritis.
5. **Optimalisasi Pipeline CI**: Isolasi transaksi database menggunakan nested savepoints, eliminasi *deadlocks* via database-per-worker, dan paralelisasi adaptif memangkas execution time hingga mencapai target feedback loop di bawah 5 menit.