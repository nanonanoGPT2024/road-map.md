# BAB 05: Concurrency, Parallelism & Multi-Threading
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedah Internal GVL (Global VM Lock):** Menjelaskan siklus hidup thread level C, mekanisme preemption 100ms time-slice, pelepasan lock pada operasi I/O via `rb_thread_call_without_gvl`, serta implikasinya terhadap performa CPU-bound vs I/O-bound.
- **Mengimplementasikan True Parallelism dengan Ractor:** Menguasai paradigma Actor model pada Ruby 3+, memahami batas isolasi memori (*shareable* vs *non-shareable objects*), serta merancang arsitektur bebas data-race tanpa GVL.
- **Mengorkestrasi Concurrency Non-Blocking via Fiber Scheduler:** Memahami antarmuka `Fiber::SchedulerInterface` (Ruby 3+) untuk menangani ratusan ribu koneksi I/O konkuren secara kooperatif menggunakan pustaka seperti `Async`.
- **Menerapkan Primitif Sinkronisasi Tingkat Lanjut:** Menggunakan `Concurrent::Map`, `Concurrent::ThreadPoolExecutor`, `Mutex`, `ConditionVariable`, dan operasi atomic Compare-And-Swap (CAS) untuk memitigasi race condition, deadlock, dan memory bloat.
- **Mendesain dan Menyetel Arsitektur Web Server & Background Job Skala Enterprise:** Menemukan konfigurasi optimal perbandingan worker/thread (Puma/Sidekiq), memitigasi CoW (Copy-on-Write) degradation, serta mengatasi fragmentasi memori menggunakan *jemalloc*.

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
- **Ruby Fundamentals & OOP:** Pemahaman mendalam mengenai Object Model, Metaprogramming dasar, Block, Proc, dan Lambda.
- **Basic Concurrency (Module 01):** Konsep dasar `Thread.new`, `Fiber.new`, race condition primitif, dan penggunaan dasar `Mutex#synchronize`.
- **Sistem Operasi Tingkat Menengah:** Pemahaman mengenai Kernel POSIX threads (pthreads), Context Switching, User Space vs Kernel Space, Non-blocking I/O multiplexing (`epoll`/`kqueue`), serta alokasi memori virtual (VSS/RSS).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Anatomi Internal GVL (Global VM Lock) pada CRuby (MRI)
Meskipun CRuby memetakan setiap `Thread.new` secara 1:1 ke POSIX thread (pthread) di level OS kernel, eksekusi bytecode YARV (*Yet Another Ruby VM*) dibatasi oleh GVL. GVL menjamin bahwa **hanya satu thread yang mengeksekusi instruksi YARV pada satu waktu per proses VM**.

```
+-----------------------------------------------------------------------+
|                             CRuby Process                             |
|                                                                       |
|  +--------------------+  +--------------------+  +-----------------+  |
|  | Native Thread #1   |  | Native Thread #2   |  | Native Thread #3|  |
|  | (Ruby Context A)   |  | (Ruby Context B)   |  | (Ruby Context C)|  |
|  +---------+----------+  +---------+----------+  +--------+--------+  |
|            |                       |                      |           |
|            | Waiting for GVL       | Holds GVL            | In Syscall|
|            v                       v                      v           |
|     [ GVL Queue ] --------> [ YARV Engine ]       [ Kernel read() ]   |
|                                    |               (GVL Released)     |
|                                    v                      |           |
|                         [ Mutex / Heap Memory ] <---------+           |
+-----------------------------------------------------------------------+
```

1. **Scheduling & Preemption Timer:**
   CRuby mengimplementasikan timer thread internal yang mengirimkan interupsi berkala (default: 100ms) ke thread yang sedang berjalan. Ketika counter interupsi (`RUBY_VM_CHECK_INTS`) terpicu, VM memeriksa apakah thread saat ini harus melepaskan GVL untuk memberi kesempatan ke thread lain via `rb_thread_schedule()`.
2. **GVL Release pada Native System Call:**
   Ketika thread mengeksekusi blocking I/O (misal: `socket.read`, `File.write`, DB query via driver native C), ekstensi memanggil macro `rb_thread_call_without_gvl()`. Native thread melepaskan GVL, mengeksekusi blocking syscall di kernel, dan thread lain dapat segera mengambil GVL untuk mengeksekusi YARV. Begitu syscall selesai, native thread akan mencoba mengakuisisi kembali GVL sebelum memproses byte Ruby berikutnya.

#### B. Ractor: Actor Model & Eliminasi GVL untuk True Parallelism
Ruby 3 memperkenalkan Ractor (*Ruby Actor*), mengizinkan eksekusi paralel nyata pada multi-core CPU di dalam satu proses Ruby:
- **Isolated Execution Units:** Setiap Ractor memiliki GVL-nya sendiri. Ractor A dan Ractor B dapat mengeksekusi instruksi YARV secara simultan pada dua Core CPU berbeda.
- **Memory Isolation Rules:**
  - *Shareable Objects:* Objek yang di-freeze secara mendalam (`Ractor.make_shareable(obj)`), class/module objects, dan objek numerik/simbol immutabel.
  - *Non-Shareable Objects:* Objek biasa (string mutable, array, hash, instance class). Memindahkan non-shareable object antar Ractor harus dilakukan via **deep-copy** (`move: false`) atau **ownership transfer** (`move: true`). Jika ownership dipindahkan, referensi di Ractor pengirim menjadi tidak dapat diakses (*invalidated*).

#### C. Fiber Scheduler & Asynchronous I/O Event Loop
Sejak Ruby 3.0, class `Fiber` diperluas dengan hooks arsitektur non-blocking melalui `Fiber::SchedulerInterface`. Operasi I/O standar seperti `TCPSocket#read`, `IO#wait_readable`, atau `sleep` tidak lagi memblokir native thread jika Fiber Scheduler terdaftar.
- VM memanggil hook internal scheduler (seperti implementasi epoll/kqueue/io_uring di engine `Async`).
- State Fiber di-suspend (`Fiber.yield`), mentransfer kendali kembali ke event-loop tanpa context-switch OS yang mahal.
- Ketika kernel memberitahu bahwa socket siap dibaca, event loop me-resume Fiber terkait (`Fiber#resume`).

---

### 4. Why & What
- **Mengapa memahami batasan GVL itu krusial?**
  Banyak engineer berasumsi menambahkan `Thread.new` pada operasi data processing (CPU-bound) akan mempercepat eksekusi. Pada CRuby, hal ini justru menurunkan performa akibat overhead context switching POSIX thread dan lock contention GVL.
- **Apa solusi modern untuk CPU-Bound Concurrency?**
  Ractor memungkinkan komputasi paralel murni (seperti image processing, kriptografi, kompresi) tanpa perlu memecah aplikasi menjadi arsitektur multi-proses microservice yang kompleks dan boros RAM.
- **Kapan memilih Threads, Fibers, atau Processes?**
  - **Process (Fork):** Isolasi total, anti-deadlock via memory barrier OS, cocok untuk web server worker (Puma clustered), namun boros memori (copy-on-write degradation).
  - **Thread (Native + GVL):** Ideal untuk High-Latency I/O-bound tasks (HTTP API client calls, database queries konvensional) dengan footprint memori menengah.
  - **Fiber (Cooperative Event-Driven):** Ideal untuk Massive C10K/C100K I/O operations (WebSockets, SSE, telemetry stream scraping) dengan footprint memori sangat rendah (beberapa kilobyte per Fiber).
  - **Ractor:** Ideal untuk komputasi CPU-bound paralel yang memerlukan komunikasi antar-task terisolasi dalam satu VM.

---

### 5. How (Workflow Detail)

#### Siklus Eksekusi Ractor Ownership Transfer
```
Ractor A (Sender)                                  Ractor B (Receiver)
       |                                                    |
       |  data = "PAYLOAD-TOKEN"                            |
       |  Ractor.yield(data, move: true)                    |
       |--------------------------------------------------->|
       |  [data becomes MASKED/INACCESSIBLE in A]           |  data = Ractor.receive
       |  (Accessing data throws Ractor::MovedError)       |  (Ownership Claimed)
       v                                                    v
```

#### Lifecycle Synchronization via CAS (Compare-And-Swap) Loop
```
State: [ Current Val: 10 ]
Thread 1 reads 10. Computes 10 + 1 = 11.
Thread 2 reads 10. Computes 10 + 2 = 12.
Thread 1 executes CAS(expected: 10, new: 11) -> Success. State: 11.
Thread 2 executes CAS(expected: 10, new: 12) -> Fails! (Current is 11, expected 10).
Thread 2 re-reads current val (11). Re-computes 11 + 2 = 13.
Thread 2 executes CAS(expected: 11, new: 13) -> Success. State: 13.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Dapur Restoran Enterprise:
- **Process Forking:** Membuka 4 cabang restoran baru yang identik secara fisik. Membutuhkan sewa tempat baru, freezer baru, dan staf baru (Memory footprint tinggi), namun kebakaran di cabang A tidak berdampak pada cabang B.
- **Thread (CRuby GVL):** Satu dapur dengan 4 koki, namun hanya ada **1 pisau koki utama (GVL)**. Hanya 1 koki yang bisa memotong daging dalam satu waktu. Namun, saat koki A memasukkan ayam ke oven (I/O Wait), ia meletakkan pisau tersebut ke meja, sehingga koki B bisa langsung mengambil pisau dan memotong sayuran.
- **Ractor:** Satu dapur besar dengan 4 bilik kedap udara mandiri. Masing-masing koki memiliki pisau sendiri (Core VM sendiri). Mereka bertukar bahan makanan hanya lewat ban berjalan khusus (*Channel/Message Port*).
- **Fiber:** Satu koki yang melakukan multitasking secara sadar (*cooperative*). Jika sedang menunggu air mendidih, koki itu sendiri yang mencatat statusnya lalu beralih meracik bumbu tanpa dipaksa oleh alarm eksternal.

```
COMPARISON MATRIX: CRUBY CONCURRENCY MECHANISMS
+------------------+------------------+---------------------+-------------------+------------------+
| Mekanisme        | Skala Abstraksi  | Parallel (CPU Bound)| Parallel (I/O)    | Memory Footprint |
+------------------+------------------+---------------------+-------------------+------------------+
| Process (fork)   | Kernel Space     | YA                  | YA                | Sangat Besar     |
| Native Thread    | Kernel Space     | TIDAK (via GVL)     | YA (via GVL Yield)| Sedang (~1-2MB)  |
| Fiber (Async)    | User Space (VM)  | TIDAK               | YA (Evented Loop) | Sangat Ringan(KB)|
| Ractor           | User/VM Isolated | YA                  | YA                | Ringan-Sedang    |
+------------------+------------------+---------------------+-------------------+------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Menguji Karakteristik GVL (CPU vs I/O Bound)
Contoh berikut mendemonstrasikan secara empiris bahwa multi-threading CRuby tidak memberikan percepatan pada komputasi CPU, namun memberikan skalabilitas tinggi pada operasi I/O.

```ruby
# frozen_string_literal: true
require 'benchmark'

def cpu_work
  10_000_000.times { 2 + 2 }
end

def io_work
  sleep(0.5)
end

puts "=== 1. CPU-BOUND BENCHMARK (2 TASKS) ==="
Benchmark.bm(15) do |x|
  x.report("Sequential:") { 2.times { cpu_work } }
  x.report("2 Threads:") do
    t1 = Thread.new { cpu_work }
    t2 = Thread.new { cpu_work }
    t1.join; t2.join
  end
end

puts "\n=== 2. I/O-BOUND BENCHMARK (2 TASKS) ==="
Benchmark.bm(15) do |x|
  x.report("Sequential:") { 2.times { io_work } }
  x.report("2 Threads:") do
    t1 = Thread.new { io_work }
    t2 = Thread.new { io_work }
    t1.join; t2.join
  end
end
```

#### Practical Example: Advanced Worker Pool Menggunakan `concurrent-ruby` & Ractor Data Pipeline
Arsitektur hybrid: Menggunakan ThreadPool untuk ingestion dan isolasi Ractor murni untuk komputasi CPU paralel (misal: validasi hash & parsing payload JSON terenkripsi).

```ruby
# frozen_string_literal: true
require 'concurrent-ruby'
require 'json'
require 'digest'

# Pipeline CPU Worker via Ractor (True Parallelism)
module CryptoPipeline
  def self.spawn_workers(count)
    count.times.map do |id|
      Ractor.new(id) do |worker_id|
        loop do
          # Menerima payload mentah yang di-freeze
          payload = Ractor.receive
          break if payload == :terminate

          # Operasi CPU-bound murni (Parallel execution antar Core)
          computed_hash = Digest::SHA256.hexdigest(payload)
          
          # Mengirim hasil kembali ke consumer
          Ractor.yield({ worker_id: worker_id, hash: computed_hash }.freeze)
        end
      end
    end
  end
end

# Ingestion Coordinator (Menggunakan Concurrent ThreadPool)
class TelemetryIngestor
  def self.run
    ractor_workers = CryptoPipeline.spawn_workers(4)
    # Load balancer round-robin sederhana untuk mendistribusikan ke Ractors
    ractor_balancer = Concurrent::AtomicFixnum.new(0)

    # Thread Pool untuk I/O Simulation
    io_pool = Concurrent::ThreadPoolExecutor.new(
      min_threads: 5,
      max_threads: 20,
      max_queue: 100,
      fallback_policy: :caller_runs
    )

    puts "Starting telemetry ingestion pipeline..."

    10.times do |i|
      io_pool.post do
        # Simulasi network latency membaca payload dari upstream
        sleep(0.05)
        raw_data = { sensor_id: i, timestamp: Time.now.to_i, metrics: [rand, rand] }.to_json
        
        # Shareable immutable string
        frozen_data = Ractor.make_shareable(raw_data)

        # Dispatch ke Ractor Core
        target_idx = (ractor_balancer.increment - 1) % ractor_workers.size
        worker = ractor_workers[target_idx]
        
        worker.send(frozen_data)
        result = worker.take

        puts "[Ingestor] Packet #{i} processed by Ractor-Worker-#{result[:worker_id]}: #{result[:hash][0..10]}..."
      end
    end

    io_pool.shutdown
    io_pool.wait_for_termination

    # Bersihkan ractor
    ractor_workers.each { |r| r.send(:terminate) }
    puts "Pipeline shut down gracefully."
  end
end

TelemetryIngestor.run
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Financial Ledger High-Throughput Reconciliation Engine
**Konteks Masalah:**
Perusahaan Fintech Payment Gateway memproses rata-rata 15.000 transaksi/detik pada jam sibuk. Sistem lama menggunakan Sidekiq berbasis Redis konvensional, namun biaya memory-locking dan GVL contention menyebabkan latency spike reconciliation hingga 4,8 detik, menghasilkan race conditions pada saldo akhir akun merchant (Double-spending issue).

#### Solusi Arsitektur Concurrency:
1. **In-Memory Thread-Safe Ledger Accumulator:** Mengganti Redis global locks untuk aggregasi lokal dengan `Concurrent::Map` dan Optimistic Concurrency Control via `Concurrent::AtomicReference`.
2. **Actor Pattern Isolation via Ractor:** Setiap merchant dialokasikan ke Ractor unik berdasarkan hash partition `merchant_id % TOTAL_RACTORS`. Semua operasi mutasi ledger merchant dieksekusi secara serial di dalam Ractor tersebut (menjamin strict ordering dan bebas lock overhead), namun paralel antar merchant yang berbeda.
3. **Penyimpanan Batch Non-Blocking:** State ledger yang terkonsolidasi di-flush ke basis data PostgreSQL secara berkala menggunakan Fiber event-driven pool (`Async`).

#### Implementasi Ledger Partition Worker:
```ruby
# frozen_string_literal: true
require 'concurrent-ruby'

class FinancialLedgerEngine
  Account = Struct.new(:id, :balance, :version)

  class PartitionWorker
    def initialize(partition_id)
      @partition_id = partition_id
      @inbox = Thread::Queue.new
      @accounts = Concurrent::Map.new
      @running = true
      @worker_thread = Thread.new { process_stream }
    end

    def submit_transaction(account_id, amount)
      promise = Concurrent::Promise.new
      @inbox.push({ account_id: account_id, amount: amount, promise: promise })
      promise
    end

    def shutdown
      @running = false
      @inbox.push(:terminate)
      @worker_thread.join
    end

    private

    def process_stream
      while @running
        message = @inbox.pop
        break if message == :terminate

        acc_id = message[:account_id]
        amt = message[:amount]
        promise = message[:promise]

        begin
          current = @accounts.compute_if_absent(acc_id) { Account.new(acc_id, 0, 0) }
          
          # State Mutation terisolasi tanpa race condition
          current.balance += amt
          current.version += 1

          promise.set(current.dup)
        rescue StandardError => e
          promise.fail(e)
        end
      end
    end
  end

  def initialize(num_partitions = 8)
    @partitions = Array.new(num_partitions) { |idx| PartitionWorker.new(idx) }
  end

  def dispatch(account_id, amount)
    partition_index = account_id.hash.abs % @partitions.size
    @partitions[partition_index].submit_transaction(account_id, amount)
  end

  def shutdown
    @partitions.each(&:shutdown)
  end
end

# Driver Simulation
engine = FinancialLedgerEngine.new(4)
promises = []

500.times do |i|
  account_id = "ACC-#{i % 10}" # 10 akun unik yang disimulasikan
  amount = (i.even? ? 100 : -50)
  promises << engine.dispatch(account_id, amount)
end

# Tunggu semua promise terselesaikan
results = promises.map(&:value!)
final_state = results.last
puts "Contoh state akhir akun: #{final_state.inspect}"
engine.shutdown
```

**Dampak Produksi:**
- *Latency:* P99 latency rekonsiliasi terpangkas dari 4800ms menjadi **12ms**.
- *Throughput:* Naik dari 3.200 TPS menjadi **24.500 TPS** per node VM 16-Core.
- *Integritas Data:* 0 insiden ledger divergence atau double-credit anomalies.

---

### 9. Trade-offs

| Pendekatan | Keunggulan | Biaya & Konsekuensi | Skenario Penggunaan |
| :--- | :--- | :--- | :--- |
| **Multi-Process (Forking/Puma Clustered)** | - Isolasi memori 100%<br>- Crash 1 proses tidak mematikan cluster<br>- True Parallelism bebas GVL | - Overhead RAM masif akibat Copy-on-Write fragmentation<br>- IPC (*Inter-Process Comm*) kompleks | Traditional Rails HTTP APIs, aplikasi dengan gem native C non-thread-safe |
| **Multi-Thread (Puma Single/Worker Threads)** | - Penggunaan RAM sangat efisien<br>- Context-switching murah via OS scheduler | - Dibatasi GVL untuk kalkulasi CPU<br>- Rawan Data-Race & Deadlock jika state bocor | Microservices I/O heavy, Webhooks processor, Database querying |
| **Fibers (Async / Falcon)** | - Skalabilitas masif I/O (100K+ koneksi)<br>- Memory per fiber hanya beberapa KB<br>- Tanpa overhead OS Context Switch | - Codebase harus sepenuhnya non-blocking<br>- Gem C-extension konvensional yang memanggil syscall blocking langsung akan melumpuhkan seluruh thread loop | WebSocket servers, Streaming APIs, Proxy layer |
| **Ractor** | - True Parallelism dalam single VM<br>- Memory safety terjamin secara sintaktis | - Overhead messaging latency<br>- Ekosistem gem pihak ketiga belum sepenuhnya ramah shareable object | Heavy CPU computation, Video/Image processing, Local cryptographic hashing |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Deadlock melalui Hierarki Penguncian Tak Teratur (*Lock Ordering Fallacy*)
- **Gejala:** Thread hang tanpa status error, CPU 0%, Puma/Sidekiq berhenti memproses request.
- **Penyebab:** Thread A mengunci `Mutex 1` lalu mencoba mengambil `Mutex 2`. Di saat yang sama, Thread B mengunci `Mutex 2` lalu mencoba mengambil `Mutex 1`.
- **Troubleshooting:** Selalu peroleh lock dengan urutan deterministik (*Lock Ordering Pattern*) atau gunakan mekanisme `try_lock` dengan timeout.

```ruby
# BURUK (Penyebab Deadlock)
def transfer_bad(acc_a, acc_b, amount)
  acc_a.mutex.synchronize do
    acc_b.mutex.synchronize do
      acc_a.debit(amount)
      acc_b.credit(amount)
    end
  end
end

# BAIK (Deterministik via Object ID Sorting)
def transfer_safe(acc_a, acc_b, amount)
  first_lock, second_lock = [acc_a, acc_b].sort_by(&:id)
  first_lock.mutex.synchronize do
    second_lock.mutex.synchronize do
      acc_a.debit(amount)
      acc_b.credit(amount)
    end
  end
end
```

#### 2. Thread Leaks pada Dynamic Task Spawning
- **Gejala:** Penggunaan RAM meningkat konstan (linear O(N)), file descriptor habis (*Too many open files*).
- **Penyebab:** Memanggil `Thread.new` secara langsung di dalam controller Rails atau loop background tanpa lifecycle management.
- **Troubleshooting:** Gunakan `Concurrent::ThreadPoolExecutor` dengan batas `max_queue` dan `fallback_policy` yang jelas, pantau metrik `Thread.list.size`.

#### 3. Ractor `IsolationError` pada Penggunaan Global State
- **Gejala:** `Ractor::IsolationError: can not access non-shareable objects in constant ...`
- **Penyebab:** Mencoba membaca konstanta global yang mutable (seperti array/hash konfigurasi) dari dalam Ractor.
- **Troubleshooting:** Bekukan objek secara mendalam menggunakan `Ractor.make_shareable(CONFIG)`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan Jemalloc:** Aktifkan environment variable `LD_PRELOAD=/usr/lib/libjemalloc.so` dan `MALLOC_ARENA_MAX=2` untuk mencegah memory fragmentation pada sistem multi-threaded Ruby.
- [ ] **Konfigurasi Puma Pool:** Setel Puma thread pool tidak melebihi kapasitas koneksi pool database ActiveRecord (`PUMA_MAX_THREADS <= RAILS_MAX_THREADS <= DB_POOL_SIZE`).
- [ ] **Hindari Class-Level Mutex:** Jangan pernah mengunci class (`self.class.mutex.synchronize`), isolasi mutasi hanya pada level instance spesifik untuk mencegah bottleneck global.
- [ ] **Immutable By Default:** Terapkan `# frozen_string_literal: true` di seluruh file dan manfaatkan objek immutabel untuk mengurangi alokasi garbage collection saat sharing data antar thread.
- [ ] **Timeout Safeguard:** Selalu terapkan batas timeout tegas pada semua blocking operations (`Concurrent::Timeout.timeout(seconds)`).
- [ ] **Tuning Sidekiq Concurrency:** Jalankan proses Sidekiq lebih banyak dengan concurrency rendah (misal: 4 proses @ 5 thread) daripada 1 proses dengan concurrency tinggi (1 proses @ 20 thread) guna meredam GVL contention dan memory bloat.

---

### 12. Hands-on Practice

Buat struktur folder berikut di workstation Anda:
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

#### Langkah 1: Buat Thread Pool Engine Mandiri
Buat file `hands-on/m02/thread_pool.rb`:

```ruby
# frozen_string_literal: true
require 'thread'

class CustomThreadPool
  def initialize(size)
    @size = size
    @jobs = Thread::Queue.new
    @workers = Array.new(size) { spawn_worker }
    @shutdown = false
  end

  def post(&block)
    raise 'ThreadPool is terminated' if @shutdown
    @jobs.push(block)
  end

  def shutdown
    @shutdown = true
    @size.times { @jobs.push(:terminate) }
    @workers.each(&:join)
  end

  private

  def spawn_worker
    Thread.new do
      catch(:exit) do
        loop do
          job = @jobs.pop
          throw :exit if job == :terminate
          begin
            job.call
          rescue StandardError => e
            warn "[Worker Error] Execution failed: #{e.message}"
          end
        end
      end
    end
  end
end
```

#### Langkah 2: Buat Pipeline Verifikasi Paralel
Buat file `hands-on/m02/pipeline_runner.rb`:

```ruby
# frozen_string_literal: true
require_relative 'thread_pool'
require 'benchmark'

pool = CustomThreadPool.new(4)
counter = Thread::Mutex.new
processed_items = 0

time = Benchmark.realtime do
  20.times do |i|
    pool.post do
      # Simulasi I/O Latency
      sleep(0.1)
      counter.synchronize { processed_items += 1 }
      puts "Completed task: #{i} on Thread #{Thread.current.object_id}"
    end
  end

  pool.shutdown
end

puts "Executed #{processed_items} tasks in #{time.round(3)}s with thread pool."
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan di terminal Anda:
```bash
ruby pipeline_runner.rb
```
*Ekspektasi Output:* 20 tugas selesai dalam rentang waktu ~0.5 - 0.7 detik (bukan 2.0 detik sekuensial), mengonfirmasi concurrency berjalan optimal di atas thread pool custom.

---

### 13. Exercise

#### Level: Easy
Implementasikan class thread-safe `ThreadSafeCounter` tanpa menggunakan external gems.
- Gunakan `Mutex` untuk mengamankan operasi increment `#increment` dan `#value`.
- **Kriteria Keberhasilan:** Diuji dengan 10 thread yang masing-masing melakukan increment 1000 kali, nilai akhir counter harus tepat 10.000.

#### Level: Medium
Buat modul rate-limiter sederhana `ConcurrentRateLimiter` berbasis Token Bucket Algorithm.
- Harus dapat diakses bersamaan oleh multi-thread.
- Mendukung method `acquire` yang memblokir thread pemanggil sampai token tersedia.
- Token diisi ulang setiap interval tertentu via background timer thread.
- **Kriteria Keberhasilan:** Tidak ada token yang terdistribusi ganda saat diserbu oleh 50 thread secara paralel.

#### Level: Hard
Bangun implementasi `ActorModel` minimalis di atas CRuby menggunakan Thread murni dan Queue, yang meniru interface API `Ractor` (`send`, `receive`).
- Masing-masing Actor berjalan pada thread-nya sendiri dan memproses mailbox FIFO.
- Mendukung fitur supervisi: Jika sebuah actor crash karena uncaught exception, supervisor actor menerima signal dan me-restart worker actor tersebut.
- **Kriteria Keberhasilan:** Sistem mampu memulihkan worker yang diinjeksi exception secara otomatis tanpa kehilangan pesan di queue yang belum diproses.

---

### 14. Challenge

#### Skenario:
Anda adalah Staff Software Engineer di platform E-Commerce Global. Selama *Flash Sale Event*, sistem pencatatan inventaris mengalami anomali *overselling* (stok minus) karena jutaan request mengakses database secara konkuren melalui Puma. Database Connection Pool collaps karena thread contention.

#### Persyaratan Desain:
Rancang dan bangun prototipe Ruby murni bernama `DistributedInventoryGovernor`:
1. Mampu menangani request mutasi inventaris secara *in-memory* dengan latency transaksi P99 di bawah 5 milidetik.
2. Memanfaatkan partisi data stok berbasis Ractor (True Parallelism per SKU) atau partitioned Actor loop untuk mengeliminasi locking global.
3. Mengimplementasikan buffer peredam ke basis data: Mutasi stok diagregasikan secara lokal dan ditulis (*flushed*) ke database secara asinkron setiap 500 milidetik atau jika buffer mencapai 1.000 mutasi.
4. Memiliki mekanisme *circuit-breaker* & backpressure: Jika buffer antrean penuh, request baru harus ditolak secara graceful (*HTTP 429 Too Many Requests*) tanpa menjatuhkan proses Ruby VM.
5. Zero dependency terhadap Redis (In-Memory Ruby solution).

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apakah CRuby (MRI) Thread dapat mengeksekusi instruksi CPU secara paralel pada multi-core machine? Jelaskan alasannya secara singkat!
2. Apa yang dilakukan thread Ruby ketika memanggil `File.read` terkait dengan GVL?
3. Mengapa `Thread#kill` atau `Thread#terminate` dianggap sangat berbahaya dan dilarang digunakan di lingkungan produksi?
4. Mengapa kita harus membekukan (*freeze*) objek sebelum mengirimkannya ke Ractor?
5. Apa perbedaan mendasar antara Fiber dan Thread dalam hal *context switching*?

#### B. Pertanyaan Intermediate
6. Jelaskan apa yang dimaksud dengan kondisi *False Sharing* atau *Memory Bloat* akibat `MALLOC_ARENA_MAX` pada aplikasi Ruby multi-threaded di Linux!
7. Bagaimana arsitektur Fiber Scheduler (Ruby 3+) dapat mencegah socket I/O memblokir native OS thread tanpa mengubah kode Ruby menjadi callback-hell?
8. Kapan operasi pembacaan nilai variabel instans (`@status`) pada Ruby memerlukan Mutex, dan kapan itu aman diabaikan di bawah GVL?
9. Bagaimana method `Ractor.yield(obj, move: true)` menangani referensi objek pada Ractor pengirim?
10. Mengapa `Concurrent::Map` memiliki performa baca/tulis yang jauh lebih superior dibandingkan `Mutex.synchronize { hash[key] = val }` pada throughput thread yang tinggi?

#### C. Skenario Kasus Produksi
11. **Skenario 1:** Sebuah service microservice Ruby berbasis Puma (4 worker processes, 16 threads per worker) sering mengalami crash dengan error `Segmentation fault (core dumped)`. Trace dump menunjuk ke library native C JSON parser pihak ketiga. Mengapa masalah ini hanya muncul di production dengan traffic tinggi dan tidak pernah muncul di local environment development Anda?
12. **Skenario 2:** Aplikasi background worker Sidekiq Anda memakan memori hingga 4 GB per container dalam 6 jam operasional, padahal data payload tiap job relatif kecil. Ketika traffic sepi, penggunaan RAM tidak kunjung turun. Strategi diagnosa dan tuning apa yang harus dieksekusi?
13. **Skenario 3:** Tim Anda mengembangkan scraping engine web menggunakan 200 concurrent `Thread`. Namun, throughput tidak meningkat signifikan dan server mengalami lonjakan CPU load yang sangat tinggi (system load > 80%). Diagnosa akar masalahnya dan berikan re-arsitektur solusi!

---

#### Kunci Jawaban & Panduan Solusi

##### Jawaban Basic
1. **Tidak.** CRuby dibatasi oleh Global VM Lock (GVL) yang memastikan hanya satu native thread yang dapat mengeksekusi Ruby YARV bytecode pada satu waktu, sehingga komputasi CPU-bound berjalan sekuensial.
2. Thread melepaskan GVL via fungsi internal `rb_thread_call_without_gvl`, memungkinkan thread Ruby lain mengeksekusi kode sementara thread tersebut menunggu IO syscall kernel selesai.
3. Karena `Thread#kill` menghentikan thread secara abrupt tanpa membersihkan resource, meninggalkan lock/mutex dalam kondisi terkunci permanen (*deadlock*), atau memotong operasi mutasi data di tengah jalan (*state corruption*).
4. Untuk memastikan *thread-safety* dan mencegah *data-race*. Ractor menjamin isolasi memori mutlak; hanya *deeply frozen objects* (shareable) yang aman diakses bersamaan oleh Core CPU yang berbeda.
5. Thread di-switch secara *preemptive* oleh OS Kernel Scheduler. Fiber di-switch secara *cooperative* di level User Space oleh programmer/VM via `Fiber.yield` dan `resume`.

##### Jawaban Intermediate
6. Glibc alokator memori secara default membuat arena memori baru (hingga 8 x core CPU) untuk setiap thread baru guna menghindari lock contention. Hal ini menyebabkan fragmentasi virtual memory yang sangat masif pada Ruby (*Memory Bloat*). Solusinya adalah membatasi arena atau menggunakan `jemalloc`.
7. Ruby VM menyediakan antarmuka hook C (`rb_fiber_scheduler_t`). Saat operasi IO terjadi, runtime memeriksa apakah ada scheduler aktif. Jika ada, thread tidak memblokir syscall melainkan memarkir Fiber tersebut, mendaftarkan file descriptor ke kernel event poller (`epoll`/`kqueue`), dan melanjutkan eksekusi Fiber lain.
8. Pembacaan variabel tunggal atomik di level C-Ruby umumnya terlindungi GVL dari memory tearing, tetapi jika pembacaan tersebut merupakan bagian dari logika gabungan *Check-then-Act* (misal: `if @status == :ready; @status = :running; end`), maka Mutex mutlak diperlukan untuk mencegah race condition.
9. Ractor pengirim mentransfer kepemilikan memori secara eksklusif. VM menandai (*masks*) referensi lokal di Ractor pengirim sebagai tidak valid. Setiap upaya membaca objek tersebut setelah dipindahkan akan memunculkan exception `Ractor::MovedError`.
10. `Concurrent::Map` menggunakan teknik *Lock Striping* dan operasi atomic Compare-And-Swap (CAS). Hal ini membagi segmen penguncian menjadi beberapa bucket kecil, sehingga pembacaan bersifat lock-free dan operasi penulisan pada bucket yang berbeda tidak saling memblokir (*fine-grained locking*).

##### Solusi Skenario Produksi
11. **Diagnosa & Solusi:** C-extension parser tersebut tidak *thread-safe* (menggunakan static/global C variables yang termutasi silang). Di environment development, Puma biasanya berjalan dalam *single-thread/single-request mode*, sehingga race-condition di level C-memory tidak pernah terpicu. Di production dengan 16 thread aktif, terjadi *memory corruption* / invalid pointer dereferencing yang memicu OS kernel mengirimkan sinyal SIGSEGV. **Solusi:** Ganti library parser dengan yang thread-safe murni, atau lindungi pemanggilan C-gem tersebut dengan Mutex global.
12. **Diagnosa & Solusi:** Ini adalah kasus fragmentasi memori glibc dikombinasikan dengan Copy-on-Write (CoW) memory pollution saat GC berjalan. **Solusi:** (1) Ganti alokator sistem runtime container ke `jemalloc`. (2) Turunkan concurrency Sidekiq per process dari misalnya 25 menjadi 5 atau 10, dan perbanyak replica pod/container. (3) Jalankan `GC.compact` secara terencana setelah aplikasi booting sebelum job pertama diproses.
13. **Diagnosa & Solusi:** Menjalankan 200 OS Native Thread menyebabkan *Thread Thrashing*—OS menghabiskan sebagian besar siklus CPU hanya untuk context switching kernel threads dan mengelola call stack (1-2MB per thread). **Solusi Re-arsitektur:** Migrasikan dari Native Threads murni ke arsitektur Non-Blocking IO berbasis Event-Loop menggunakan gem `Async` (Fiber Scheduler). Dengan `Async`, 200-10.000 target URL dapat di-scrape di dalam 1 native thread saja secara efisien, mereduksi CPU system load hingga di bawah 10%.

---

### 16. Summary

```
                      +-----------------------------+
                      |   Ruby Concurrency Matrix   |
                      +-----------------------------+
                                     |
         +---------------------------+---------------------------+
         |                                                       |
   [ CPU-BOUND ]                                           [ I/O-BOUND ]
         |                                                       |
   Perlu Paralel Murni?                                   Skala Concurrency?
   +-----+-----+                                           +-----+-----+
   |           |                                           |           |
  YA          TIDAK                                      Kecil       Masif
   |           |                                       (< 100)      (> 1000)
   v           v                                           v           v
[Ractor]   [Process Fork]                               [Thread]    [Fiber Async]
(Ruby 3+)  (Puma Clustered)                            (Concurrent) (Non-blocking)
```

1. **GVL Bukan Musuh I/O:** GVL hanya membatasi eksekusi YARV bytecode paralel CPU-bound. Untuk operasi yang didominasi network & disk I/O, multi-threading native Ruby tetap sangat berdaya guna tinggi karena GVL dilepaskan selama system call berlangsung.
2. **Kedaulatan Ractor:** Ractor membuka babak baru komputasi multi-core CPU paralel murni di Ruby tanpa mengorbankan keamanan memori, menggantikan kebiasaan lama forking proses yang boros sumber daya.
3. **Fiber Scheduler Mengubah Lanskap I/O:** Fiber modern di Ruby 3+ mengubah Ruby menjadi platform event-driven berkemampuan tinggi setara Go goroutines atau Node.js event-loop tanpa callback-hell, menjadikannya arsitektur masa depan untuk platform I/O throughput masif.
4. **Disiplin Resource Produksi:** Eksekusi multi-threading enterprise menuntut arsitektur alokasi memori yang disiplin (wajib `jemalloc`), eliminasi unsafe dynamic thread spawning dengan thread pool yang dibatasi (*bounded queues*), serta isolasi state via primitif konkurensi modern.