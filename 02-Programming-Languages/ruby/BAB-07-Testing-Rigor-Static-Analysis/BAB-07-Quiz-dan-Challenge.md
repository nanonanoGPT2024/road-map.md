# BAB 07: Quiz, Challenge, & Knowledge Check
**Testing Rigor & Static Analysis**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Evaluasi RSpec: `let`, `let!`, dan `before(:each)`
Jelaskan perbedaan mendasar dalam siklus hidup (*lifecycle*), alokasi memori, dan semantik eksekusi antara `let`, `let!`, dan *instance variable* yang didefinisikan di dalam blok `before(:each)`. Kapan *lazy-evaluation* pada `let` dapat menjadi sumber *anti-pattern* atau *silent test failure*, terutama ketika berhadapan dengan pengujian efek samping (*side-effects*) pada basis data?

### Soal 1.2: Verifying Doubles vs Pure Doubles
Bandingkan implementasi internal antara `double()` / `mock_model()` biasa dengan *verifying doubles* (`instance_double`, `class_double`, `object_double`) pada RSpec Mocks. Mengapa penggunaan *pure doubles* tanpa verifikasi dianggap sebagai celah arsitektur (*brittle test smell*) saat terjadi refaktor antarmuka publik (*public interface drift*), dan bagaimana *verifying doubles* memvalidasi eksistensi metode serta *arity* saat pengujian berjalan?

### Soal 1.3: Mutation Testing vs Code Coverage Metrics
Mengapa metrik *line coverage* dan *branch coverage* (misalnya via SimpleCov) sering kali memberikan rasa aman palsu (*false sense of security*) pada sistem finansial atau transaksi kritis? Jelaskan secara matematis dan konseptual bagaimana teknik *Mutation Testing* (menggunakan *tool* seperti `mutant`) mengevaluasi ketahanan *test suite* melalui manipulasi AST (*Abstract Syntax Tree*), serta definisikan apa yang dimaksud dengan *mutant killed*, *mutant survived*, dan kaitannya dengan *assertion density*.

### Soal 1.4: Arsitektur AST Parser dan RuboCop Cops
Bagaimana RuboCop membedah kode Ruby menggunakan parser berbasis Whitequark AST? Jelaskan struktur dasar sebuah *node* (tipe, *children*, *source map*) dan bagaimana mekanisme *NodePattern* bekerja dalam mencocokkan pola instruksi berbahaya di level sintaksis sebelum kode tersebut dieksekusi oleh YARV (*Ruby VM*).

### Soal 1.5: Gradual Typing: Filosofi Sorbet vs RBS/Steep
Analisis perbedaan arsitektural antara pendekatan Sorbet (`sorbet-runtime` + static checker via `.rbi`) dan RBS/Steep (separasi file `.rbs` eksternal berstandar Ruby Core). Bagaimana Sorbet menangani *runtime type assertion* melalui *method wrapping* versus verifikasi murni berbasis tipe statis pada Steep? Apa konsekuensi performa pada fase *booting* aplikasi jika *runtime assertions* diaktifkan di level produksi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Database Cleaner, Isolation Level, dan Multi-Threaded Specs
Pada pengujian integrasi (misalnya sistem checkout) yang melibatkan *background workers* atau *feature specs* (Capybara/Selenium) yang berjalan di *thread* terpisah dari *test runner thread*:
```ruby
# Spec setup
RSpec.describe "Concurrent Checkout", type: :feature do
  before { DatabaseCleaner.strategy = :transaction }
  # ...
end
```
Mengapa strategi `:transaction` menyebabkan *race condition*, *record lock*, atau *record not found* antar-*thread*? Bagaimana mekanisme PostgreSQL *snapshot isolation* bekerja di sini, dan bagaimana konfigurasi `DatabaseCleaner.strategy = :truncation` atau penggunaan *connection pooling sharing* menyelesaikan masalah tersebut secara internal?

### Soal 2.2: Mocking Clock & Time Travel Side-Effects
Tinjau potongan kode berikut yang menggunakan `Timecop` atau `ActiveSupport::Testing::TimeHelpers`:
```ruby
it "expires token after TTL" do
  travel_to 1.day.from_now
  expect(token.expired?).to be true
end
```
Jika pengujian gagal di tengah jalan sebelum blok pembersihan dijalankan (atau pengujian berjalan secara konkuren menggunakan `parallel_tests`), apa dampak internal manipulasi `Time.now` terhadap komponen Ruby seperti `Process.clock_gettime(Process::CLOCK_MONOTONIC)`, *timeout thread*, *thread scheduler*, dan koneksi HTTP berbasis SSL/TLS?

### Soal 2.3: Memory Bloat pada Large Test Suites
Sebuah *monolithic test suite* dengan 12.000 spesifikasi mengalami *continuous memory degradation* (membengkak dari 800 MB hingga 7 GB RAM) sehingga memicu *Linux Out-Of-Memory (OOM) Killer* di CI container. Sebutkan tiga akar masalah internal pada RSpec yang mempertahankan referensi objek Ruby ke dalam *global memory* (misalnya metadata retenstion, instance variables leakage pada example group, atau memoized subject), serta berikan solusi profiling menggunakan `ObjectSpace` atau GC profiler untuk mendeteksinya.

### Soal 2.4: Sorbet Dynamic Metaprogramming Escape Hatch
Diberikan sebuah modul yang menggunakan metaprogramming ekstrim:
```ruby
class DynamicRepository
  [:find_by_user, :find_by_account].each do |method_name|
    define_method(method_name) do |id|
      query_db(method_name, id)
    end
  end
end
```
Bagaimana Anda mengetikkan (*type signature*) metode dinamis ini menggunakan Sorbet tanpa menurunkan level ke `T.unsafe`? Jelaskan cara pembuatan `.rbi` file via metaprogramming generator (seperti Tapioca / `srb rbi hidden-definitions`) dan jelaskan bahaya tersembunyi dari kebocoran tipe (*type leakage*) jika tanda tangan metode dideklarasikan sebagai `T.untyped`.

### Soal 2.5: AST Node Traversal & Custom RuboCop Cop Debugging
Anda diwajibkan menulis *Custom Cop* untuk memblokir pemanggilan `eval`, `send`, dan `binding.eval` yang menggunakan argumen dinamis dari *user input*. Diberikan potongan AST berikut:
```
(send nil? :send
  (lvar :target_method)
  (lvar :payload))
```
Tuliskan *NodePattern* matcher yang valid untuk mendeteksi *offensive node* tersebut serta bagaimana metode `on_send(node)` mengevaluasi apakah argumen pertama adalah simbol statis (yang diizinkan) atau variabel lokal/ekspresi dinamis (yang harus dilaporkan sebagai *security violation*).

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Enterprise Test Suite Bottleneck & Flaky Spec Profiling
Sebuah platform perbankan digital memiliki test suite RSpec dengan 18.000 specs yang memakan waktu 1 jam 15 menit di CI pipeline (16 node paralel). Sekitar 3% dari spesifikasi mengalami *flakiness* (gagal intermiten tanpa ada perubahan kode).

```
Pipeline Log Failure Pattern:
- PG::TRDeadlockDetected: ERROR: deadlock detected ...
- Net::ReadTimeout (faraday external call not stubbed)
- RSpec::Expectations::ExpectationNotMetError: expected 10, got 9 (depends on test ordering)
```

1. **Root Cause Analysis**: Rancang metodologi komprehensif untuk mendiagnosis:
   - Sumber deterministik dari kegagalan intermiten terkait urutan eksekusi (*order-dependent failures* via `--bisect`).
   - Kebocoran I/O (eksternal HTTP calls) yang lolos dari WebMock/VCR.
2. **Architecture Remediation**: Rancang arsitektur paralelisasi berbasis pembagian waktu bobot (*knapsack execution splitting*) dan eliminasi overhead alokasi database menggunakan transient in-memory storage atau unlogged tables di PostgreSQL.

---

### Skenario B: Race Condition & Transaction Isolation pada Event-Driven Testing
Sistem *Order Processing* mempublikasikan domain event ke RabbitMQ via *transactional outbox pattern*. Di RSpec, pengujian memvalidasi bahwa event berhasil masuk ke antrean hanya jika database commit berhasil.

```ruby
# Service Implementation
def place_order(order_params)
  ActiveRecord::Base.transaction do
    order = Order.create!(order_params)
    EventOutbox.create!(event_name: 'OrderPlaced', payload: order.as_json)
  end
  EventPublisher.publish_pending! # Mengambil dari EventOutbox dan push ke MQ
end

# The Failing Spec
it "publishes order placed event to MQ" do
  expect(RabbitMQClient).to receive(:publish).with(hash_including("event_name" => "OrderPlaced"))
  OrderService.new.place_order(valid_params)
end
```

Spesifikasi di atas lulus di lokal (*green*), namun ketika *worker thread* asinkron diaktifkan dalam lingkungan *staging-like test*, sistem mengalami kondisi: *Publisher* berjalan sebelum transaksi di-commit oleh PostgreSQL, memicu *race condition* di mana `EventOutbox` membaca baris data yang belum ada (*phantom read*).

1. Mengapa konfigurasi transaksi RSpec menyembunyikan *bug* konkurensi ini?
2. Bagaimana Anda mendesain ulang *test harness* menggunakan *commit callbacks* (`after_commit`) dan memverifikasi *eventual consistency* tanpa memperkenalkan sleep arbitrary (`sleep 2`) yang memperlambat suite?

---

### Skenario C: Migrasi Monolith Legacy ke Strict Typing (Sorbet vs Steep/RBS)
Perusahaan e-commerce skala besar dengan 1,5 juta baris kode Ruby 3.2 legacy yang sarat dengan *ActiveSupport concerns*, *dynamic method definitions*, dan monkey-patching, memutuskan untuk mengadopsi *static typing* untuk menurunkan angka `NoMethodError` (undefined method for nil:NilClass) yang mencapai 42% dari total error di Sentry.

Tim terbelah menjadi dua:
- Tim A mengusulkan **Sorbet** karena kecepatan eksekusi tipe (*C++ based compiler*) dan integrasi adopsi gradual (`# typed: false`, `# typed: true`, `# typed: strict`).
- Tim B mengusulkan **RBS + Steep** karena merupakan standar resmi Ruby core, tidak mencemari sintaksis Ruby dengan DSL runtime (`sig { params(...).returns(...) }`), dan memisahkan tipe ke direktori signatures.

1. **Trade-off Analysis**: Bandingkan kedua pendekatan ini berdasarkan aspek: *developer ergonomics*, *CI check overhead*, *tooling/LSP support*, serta interoperabilitas dengan *gems* eksternal yang tidak memiliki type signature.
2. **Migration Blueprint**: Susun strategi migrasi 4-fase yang aman untuk legacy monolith tersebut, termasuk penentuan matriks batas adopsi tipe (*boundary layers*) seperti DTO, Domain Entities, dan Controller.

---

## 4. Chapter Challenge

### Tantangan Praktis: Mengembangkan Custom RuboCop Cop & Zero-Mock Contract Validator

#### Deskripsi Masalah
Dalam arsitektur *Clean Architecture* / *Domain-Driven Design* di Ruby, Domain Services dilarang keras memanggil langsung metode persistensi database (`ActiveRecord::Base` sub-classes methods seperti `.save`, `.update`, `.destroy`, `.create`) atau mengeksekusi *raw SQL*. Domain Services harus mendelegasikan persistensi ke *Repository Interfaces*. Selain itu, developer sering menyalahgunakan generic `double()` yang menyebabkan *contract drift* antara Service dan Repository.

#### Requirements
1. **Custom RuboCop Rule (`RuboCop::Cop::Architecture::NoDirectActiveRecordPersistenceInDomain`)**:
   - Bangun sebuah Cop kustom menggunakan Whitequark AST parser.
   - Periksa semua file di dalam folder `app/domain/**/*.rb`.
   - Cop harus mendeteksi dan memberi *offense* jika menemukan pemanggilan metode mutasi ActiveRecord (`create`, `create!`, `save`, `save!`, `update`, `update!`, `destroy`, `destroy!`, `delete`, `delete_all`) baik secara direct receiver maupun chained method.
   - Harus menyediakan *autocorrect* jika polanya adalah delegasi trivial (opsional) atau memberikan pesan error edukatif yang mencantumkan nama Repository yang harus digunakan.
2. **Contract Enforcer Extension pada RSpec**:
   - Tulis sebuah module ekstensi RSpec (`ContractEnforcer`) yang mengintersepsi DSL mocking.
   - Matikan pemanggilan `double()` murni di dalam direktori `spec/domain/`. Jika developer menulis `double("UserRepository")`, test runner harus melempar exception: `UnverifiedDoubleForbiddenError: Use instance_double(UserRepository) instead to guarantee contract safety`.
   - Validasi bahwa setiap stubbing menggunakan `instance_double` benar-benar memverifikasi kesesuaian tipe data kembalian (*return type signature*) terhadap kontrak interface.

#### Constraints
- Custom Cop harus memiliki performa tinggi (< 15ms traversal per file) dan tidak boleh crash saat memproses file kosong atau sintaks Ruby kompleks.
- RSpec Extension tidak boleh merusak fungsionalitas RSpec bawaan di luar direktori `spec/domain/`.
- Kode harus ditulis dalam sintaks Ruby 3.x modern, dilengkapi dengan spesifikasi unit pengujian cop itu sendiri menggunakan `rubocop/rspec/support`.

#### Expected Output
1. File implementasi `lib/rubocop/cop/architecture/no_direct_active_record_persistence_in_domain.rb` lengkap dengan `NodePattern`.
2. File spec pengujian cop `spec/rubocop/cop/architecture/no_direct_active_record_persistence_in_domain_spec.rb` yang menguji *positive* dan *negative cases*.
3. File konfigurasi dan ekstensi RSpec `spec/support/contract_enforcer.rb` yang menginjeksi *lifecycle validation hooks*.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus internal eksekusi RSpec: `before(:suite)` -> `before(:context)` -> `before(:example)` -> `example` -> `after(:example)` dan hierarki alokasi memorinya.
- [ ] Perbedaan fundamental antara Dummy, Stub, Spy, Mock, Fake, dan Verifying Doubles dalam arsitektur pengujian piramida (*Test Pyramid*).
- [ ] Bagaimana Whitequark AST memetakan kode Ruby menjadi struktur *S-Expressions* `(type, *children)` dan cara menulis *NodePattern* kompleks.
- [ ] Mekanisme kerja Sorbet Static Type Checker (Biarritz core) dan bagaimana dynamic runtime signatures (`sorbet-runtime`) membungkus method dispatch via Module prepending.
- [ ] Prinsip kerja *Mutation Testing* dan bagaimana *mutant* merekayasa operator aritmatika, perbandingan, penggantian nilai balikan, dan percabangan AST.
- [ ] Masalah konkurensi pada database pooling saat pengujian berjalan paralel (`parallel_tests` vs RSpec built-in multi-threading).

### Saya tidak perlu menghafal:
- [ ] Seluruh sintaks AST NodePattern RuboCop (gunakan `ruby-parse -E` atau *AST explorer* untuk inspeksi visual).
- [ ] Semua konfigurasi flags `.rubocop.yml` (cukup pahami inheritance, target version, dan severities: `fatal`, `error`, `warning`, `convention`, `refactor`).
- [ ] Seluruh signature grammar Sorbet `.rbi` untuk standard library Ruby (manfaatkan *Sorbet RBI Central* dan generator otomatis *Tapioca*).

### Saya harus bisa melakukan:
- [ ] Melakukan isolasi dan eliminasi *flaky test* menggunakan `rspec --seed <number> --bisect` secara sistematis.
- [ ] Menulis *Custom RuboCop Cops* untuk membatasi boundary arsitektur spesifik domain perusahaan.
- [ ] Mengonfigurasi `mutant` pada level CI pipeline untuk memastikan critical paths memiliki mutation score minimal 85%+.
- [ ] Menyetel DatabaseCleaner dan transactional fixtures secara tepat untuk skenario pengujian asinkron / multi-threaded Puma workers.
- [ ] Mengadopsi Sorbet atau RBS/Steep pada repositori legacy secara inkremental tanpa memblokir kecepatan *delivery* tim engineering.