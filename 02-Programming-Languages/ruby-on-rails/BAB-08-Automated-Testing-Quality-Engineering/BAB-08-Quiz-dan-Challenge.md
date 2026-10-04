# BAB 08: Quiz, Challenge, & Knowledge Check
**Automated Testing & Quality Engineering**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Evaluasi Siklus Hidup State RSpec (`let`, `let!`, dan `before(:each)`)
Jelaskan perbedaan mendasar antara `let`, `let!`, dan `before(:each)` dari perspektif:
1. *Evaluation strategy* (lazy vs eager loading).
2. Alokasi memori dan persistensi *memoized helper* di dalam scope blok pengujian (`it`).
3. Dampak deterministik terhadap pengujian mutasi database (*side-effects*). Mengapa penggunaan `let` secara keliru dapat menyembunyikan bug pada query ActiveRecord yang mengandalkan state awal database?

### Soal 1.2: Mekanisme Transaksional Rails Fixtures vs Database Cleaner
Secara default, Rails menggunakan `use_transactional_tests = true` (atau transactional fixtures). 
1. Terangkan bagaimana mekanisme PostgreSQL `SAVEPOINT` dan `ROLLBACK TO SAVEPOINT` dimanfaatkan oleh Rails Test Runner untuk mengisolasi state data antar-eksekusi test case tanpa perlu mengeksekusi perintah DDL `TRUNCATE`.
2. Pada skenario apa mekanisme transaksional ini runtuh sehingga memaksa engineer beralih ke strategi `truncation` atau `deletion` (misalnya saat melibatkan multi-threaded web drivers seperti Selenium/Capybara atau background worker asynchronous)?

### Soal 1.3: FactoryBot Graph Explosion & Trade-off vs Static Fixtures
`FactoryBot` menawarkan fleksibilitas tinggi namun sering menjadi penyebab utama degradasi performa test suite (*factory cascade / object graph explosion*).
1. Analisis bagaimana pemanggilan `create(:invoice)` yang memiliki dependensi asosiasi bertingkat (`belongs_to :user`, `belongs_to :account`, `has_many :items`) dapat mengeksekusi puluhan query `INSERT` yang tidak diinginkan secara eksponensial.
2. Bandingkan performa dan *maintainability* FactoryBot dengan pendekatan native Rails Fixtures (menggunakan `ActiveRecord::FixtureSet`) pada codebase monolitik berskala ratusan ribu baris kode.

### Soal 1.4: London School (Mockist) vs Chicago School (Classicist) dalam Domain Rails
Dalam ekosistem Ruby on Rails:
1. Kapan penerapan *Mockist approach* (menggunakan RSpec `instance_double`, `spy`, dan `receive`) menjadi anti-pattern yang meloloskan bug ke level produksi (*false positives* akibat *drifting contract*)?
2. Bagaimana *Classicist approach* (menguji interaksi riil antar service object, database, dan domain models) dapat dipertahankan efisiensinya tanpa mengorbankan isolasi unit testing?

### Soal 1.5: Arsitektur Eksekusi Rails System Tests
Jelaskan rantai interaksi arsitektural saat sebuah Rails System Test dieksekusi:
```
[RSpec/Capybara] -> [Driver (Cuprite/Selenium)] -> [Headless Browser] -> [HTTP Request] -> [Puma Server (Test Thread)] -> [ActiveRecord Thread Pool]
```
Mengapa pengujian system test memerlukan konfigurasi Puma server tersendiri yang berjalan pada thread/proses terpisah dari runner RSpec, dan bagaimana Rails mengelola *database connection sharing* antar kedua entitas tersebut?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Debugging Asynchronous Race Condition pada Capybara
Perhatikan cuplikan kegagalan uji coba flappy/flaky berikut:
```ruby
# Spec
it "updates the user balance immediately after payment", :js do
  find("#submit-payment-btn").click
  expect(user.reload.balance).to eq(100_000)
end
```
1. Mengapa assertion langsung terhadap `user.reload.balance` hampir selalu menghasilkan *race condition* / *false failure* ketika form dikirimkan via Hotwire/Turbo atau AJAX asynchronous?
2. Jelaskan cara kerja internal Capybara *dynamic waiting mechanism* (`Capybara.default_max_wait_time`) dan modifikasi assertion di atas agar thread-safe dan deterministik tanpa menggunakan `sleep`.

### Soal 2.2: Time Travel Testing & Mutasi Clock Internal
Rails menyediakan modul `ActiveSupport::Testing::TimeHelpers` (`travel_to`, `freeze_time`).
1. Bagaimana `travel_to` memanipulasi waktu sistem pada level Ruby runtime (`Time.now`, `DateTime.now`, `Date.today`), dan apakah manipulasi ini memengaruhi `Process.clock_gettime(Process::CLOCK_MONOTONIC)`?
2. Apa risiko teknis stubbing manual seperti `allow(Time).to receive(:now).and_return(...)` terhadap internal timeout library koneksi database (misalnya connection pool checkout timeout) dan web server?

### Soal 2.3: Isolasi Shared State dan Order-Dependent Failures
Sebuah test suite lolos ketika dijalankan secara individual:
`bundle exec rspec spec/services/tax_calculator_spec.rb`
Namun gagal ketika dijalankan secara penuh dengan seed acak:
`bundle exec rspec --seed 48291`
1. Uraikan metodologi sistematis untuk melakukan isolasi dan bisecting terhadap *culprit spec* (test case penyebab kebocoran state) menggunakan flag RSpec `--bisect`.
2. Sebutkan 3 vektor utama kebocoran state pada Ruby runtime yang persisten lintas siklus pengujian (misalnya: Class Variables `@@`, singleton state, memoization pada `Thread.current`, atau konfigurasi global `CurrentAttributes`), serta cara mitigasinya.

### Soal 2.4: Determinisme HTTP Interception: WebMock vs VCR
Saat menguji integrasi Payment Gateway:
1. Bagaimana WebMock melakukan intercept terhadap socket connection di level Ruby standard library (`Net::HTTP`, `HTTPClient`, dsb.)?
2. Pada implementasi `vcr`, apa bahaya merekam dynamic payloads (misalnya *timestamp*, *nonce*, atau *HMAC-SHA256 signature*) ke dalam file cassette YAML, dan bagaimana menyusun konfigurasi *custom request matcher* serta parameter filter untuk menjamin determinisme replay?

### Soal 2.5: Semantic Coverage vs Code Coverage via Mutation Testing
Sebuah module memiliki metrik 100% *Line Coverage* pada SimpleCov. Namun saat diuji menggunakan `mutant-rspec`, nilai *Mutation Score* hanya mencapai 42%.
1. Jelaskan bagaimana Mutation Testing bekerja pada level Abstract Syntax Tree (AST) Ruby (misalnya penggantian operator binary, penghapusan statement, atau pembalikan conditional logic).
2. Mengapa *high line coverage* dapat memberikan ilusi keamanan (*false sense of security*), dan bagaimana mutasi yang bertahan (*alive mutants*) mengindikasikan test assertion yang lemah (*assertion-free tests*)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck dan Memory Bloat pada Test Suite Skala Enterprise
* **Konteks:** Sebuah aplikasi core banking monolitik berbasis Rails memiliki 15.000 test cases (kombinasi Unit, Request, dan System specs). Eksekusi CI pipeline di GitHub Actions memakan waktu 1 jam 15 menit. Penggunaan memori pada worker container melonjak secara linier dari 800MB hingga menyentuh batas OOM (Out-of-Memory) 7GB pada menit ke-40.
* **Gejala Tambahan:** Sebagian besar developer mulai menambahkan tag `:skip` untuk mempercepat development, dan branch master sering rusak karena developer mengabaikan pengetesan lokal.
* **Pertanyaan Diagnostik:**
  1. Rancang arsitektur paralelisasi test suite modern menggunakan strategi *dynamic test allocation* berbasis historical timing data (misalnya Knapsack Pro atau Gitlab/GitHub parallel matrix). Bagaimana Anda mendistribusikan test suite tersebut ke dalam 10 worker nodes?
  2. Identifikasi akar penyebab *memory leak* linier selama eksekusi RSpec yang panjang di Ruby (hubungkan dengan retensi object graph oleh RSpec metadata, profiling loggers, dan retensi class-level memoization).
  3. Konfigurasi garbage collection (GC) tuning apa (`RUBY_GC_*`) yang harus dioptimasi untuk lingkungan CI guna mengurangi frekuensi major GC execution tanpa memicu OOM?

### Skenario B: Race Condition dan Deadlock Database pada Parallel Testing
* **Konteks:** Tim engineering mengaktifkan fitur bawaan Rails parallel testing:
  ```ruby
  class ActiveSupport::TestCase
    parallelize(workers: :number_of_processors)
  end
  ```
  Segera setelah diaktifkan pada mesin CI berkekuatan 16-core, pengujian mulai gagal secara acak dengan galat:
  `ActiveRecord::Deadlocked: PG::TRDeadlockDetectedError: ERROR: deadlock detected`
  dan sesekali:
  `ActiveRecord::RecordNotUnique: PG::UniqueViolation: ERROR: duplicate key value violates unique constraint`
* **Arsitektur:** Database menggunakan PostgreSQL. Entitas yang diuji melibatkan model `LedgerAccount` yang menggunakan callback `after_commit` untuk memicu background job verifikasi saldo via Redis.
* **Pertanyaan Diagnostik:**
  1. Mengapa parallel execution dengan multi-process (`parallelize`) dapat memicu `PG::UniqueViolation` pada data yang seharusnya diisolasi per-worker, dan bagaimana Rails mengonfigurasi penamaan database worker (`test-database-0`, `test-database-1`, dst.) untuk mengatasinya?
  2. Jika database antar-worker sudah terisolasi, bagaimana kebocoran state pada shared infrastructure eksternal (seperti Redis shared database index, Elasticsearch shared index, atau Localstack S3 bucket) dapat memicu kegagalan cross-worker? Rancang solusi arsitektural pengujian untuk shared resources tersebut.

### Skenario C: Architectural Testing & Boundary Enforcement
* **Konteks:** Perusahaan menerapkan arsitektur *Modular Monolith* (Packwerk) dengan domain boundaries yang ketat antara domain `Billing`, `Identity`, dan `Order`. Ditemukan bahwa para engineer menulis pengujian unit untuk domain `Billing` dengan cara memanggil factory dan model langsung dari domain `Identity` (`User.create!`, `Session.create!`) di dalam database yang sama.
* **Dampak:** Test suite di domain `Billing` sangat lambat dan rapuh; setiap kali skema internal domain `Identity` bermigrasi, ratusan test di domain `Billing` patah, melanggar prinsip *loose coupling*.
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda merancang strategi testing contract (*Contract Testing*) di level unit/integration tests antara domain `Billing` dan `Identity` tanpa melibatkan dependensi database langsung?
  2. Bagaimana mengimplementasikan boundary verification tests secara otomatis di CI (menggunakan tooling seperti Packwerk, custom RuboCop rules, atau RSpec custom matchers) untuk mencegah dependensi model lintas domain bocor ke dalam test fixtures/factories?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rekayasa Resilient & High-Performance Test Engine untuk Sub-Sistem Transaksi Keuangan

#### Deskripsi Kasus
Anda adalah Principal Quality Engineer di sebuah platform e-commerce finansial. Anda diminta membangun test suite yang sangat deterministik, cepat, dan anti-flaky untuk komponen kritis: `WalletTransferService`. Komponen ini bertanggung jawab memindahkan dana antar dua wallet, memeriksa limit harian anti-fraud via panggilan external microservice HTTP, menulis catatan mutasi ganda (*double-entry bookkeeping*), dan mempublikasikan domain event ke Kafka.

#### Problem Statement
Test suite eksisting saat ini:
1. Lambat karena menggunakan `FactoryBot.create` berulang kali.
2. Flaky pada pengujian HTTP timeout ke microservice anti-fraud.
3. Mengabaikan validasi concurrency (race condition jika transfer ganda terjadi dalam fraksi milidetik yang sama).
4. Tidak memiliki verifikasi mutasi testing (coverage 100% palsu).

#### Requirements
1. **Double-Entry & Concurrency Testing:**
   * Tulis RSpec integration spec yang mensimulasikan minimal 10 concurrent threads yang mencoba menarik saldo dari satu wallet dengan saldo terbatas (Race Condition Attack test).
   * Buktikan bahwa sistem menangani locking (Pessimistic locking via `SELECT FOR UPDATE`) secara benar: tidak terjadi *double-spending*, hanya 1 transaksi lolos, dan 9 transaksi sisanya menghasilkan eksepsi transaksi yang tertangani dengan rollback database sempurna.
2. **Network Resilience & Mocking:**
   * Gunakan `WebMock` untuk mensimulasikan kegagalan jaringan pada Fraud Detection Engine: (a) HTTP Connection Timeout, (b) HTTP 500 Internal Server Error, (c) Response payload corrupt.
   * Pastikan service mengimplementasikan mekanisme retry deterministik dan *fallback degradation* yang terverifikasi dalam unit test tanpa sleep latency riil.
3. **Optimasi Alokasi Memori & Factory Isolation:**
   * Tulis factory untuk `Wallet`, `Account`, dan `LedgerEntry` menggunakan `FactoryBot` yang dioptimasi: sediakan strategi `build_stubbed` yang valid untuk unit testing domain logic tanpa menyentuh database sama sekali.
   * Hilangkan seluruh factory cascades. Asosiasi hanya boleh dipersist jika atribut eksplisit dipanggil.
4. **Mutant Proofing:**
   * Buat test suite yang lolos verifikasi `mutant` (skor mutasi minimal 90%) pada class `WalletTransferService`. Seluruh branch logic, border conditions (misalnya: transfer nominal 0 atau negatif, batas transfer tepat pada limit, saldo wallet tepat habis menjadi 0) harus memiliki test assertion eksplisit.

#### Constraints
* Tidak boleh ada `sleep(...)` dalam kode test. Seluruh penungguan asynchronous harus menggunakan polling loop deterministik atau mock timer.
* Eksekusi keseluruhan test suite untuk modul ini (termasuk 10-thread concurrency test) tidak boleh melebihi 3 detik di lingkungan lokal.
* Dilarang menonaktifkan RuboCop atau Brakeman warnings.

#### Expected Output
1. File `spec/services/wallet_transfer_service_spec.rb` yang mencakup:
   * Concurrency integration test dengan `Thread.new` array dan database transaction verification.
   * Unit test menggunakan `build_stubbed` dan mock contract boundaries.
   * HTTP fault-tolerance specs menggunakan WebMock expectations.
2. File `spec/factories/wallets.rb` yang menerapkan transient attributes untuk mencegah *graph explosion*.
3. Konfigurasi `spec/support/` yang mengimplementasikan pembersihan shared state dan isolasi database thread-pool.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme kerja isolation level SQL (`SAVEPOINT`, `READ COMMITTED`, `SERIALIZABLE`) dalam konteks `ActiveRecord::TestFixtures`.
- [ ] Perbedaan siklus hidup lifecycle RSpec: `before(:suite)`, `before(:all)` / `before(:context)`, `before(:each)` / `around(:each)` beserta dampak kebocoran memori/datanya.
- [ ] Anatomi Dynamic Waiting pada Capybara dan bagaimana ia berinteraksi dengan DOM nodes rendering via JavaScript/Turbo streams.
- [ ] Prinsip kerja Abstract Syntax Tree (AST) mutation testing untuk mengukur ketahanan tes secara objektif.
- [ ] Karakteristik performa antara I/O disk, alokasi memori GC Ruby, dan overhead network layer saat merancang arsitektur CI testing.
- [ ] Mengapa stubbing/mocking terhadap ActiveRecord internal queries (`where`, `joins`) adalah architectural anti-pattern (*tight coupling to implementation details*).

### Saya tidak perlu menghafal:
- [ ] Seluruh sintaks RSpec built-in matchers (cukup pahami konsep `expect(...).to match(...)` dan cara membuat custom matcher).
- [ ] Argumen konfigurasi low-level ChromeDriver / Selenium Options (gunakan wrapper seperti Cuprite / webdrivers / selenium-webdriver defaults).
- [ ] Daftar lengkap mutator flags pada gem `mutant` (cukup pahami konsep mutator substitution rules dan cara membaca report mutasi yang *alive*).

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi, mengisolasi, dan mereparasi *flaky test* menggunakan teknik bisecting seed dan profiler timeline.
- [ ] Melakukan profiling test suite yang lambat menggunakan tools seperti `rspec --profile`, `test-prof` (EventProf, FactoryProf).
- [ ] Menghilangkan dependensi eksternal I/O dari test suite menggunakan `WebMock`, VCR, atau isolated custom fake adapters.
- [ ] Mengonfigurasi parallel test execution pada CI pipeline multi-core yang bebas dari *database deadlocks* dan *shared resource collisions*.
- [ ] Menulis test assertion berbasis status perubahan domain (`change { ... }.by(...)`) daripada memeriksa state absolut yang rentan perubahan context.