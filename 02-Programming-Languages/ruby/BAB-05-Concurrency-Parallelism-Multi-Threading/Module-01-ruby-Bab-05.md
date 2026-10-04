# BAB 05 / MODUL 01: CONCURRENCY, PARALLELISM, & MULTI-THREADING DALAM RUBY

---

## SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** `02-Programming-Languages`
* **Track:** Ruby Enterprise Engineering
* **Bab:** 05 — Advanced Execution Models & Concurrency
* **Modul:** 01 — Concurrency, Parallelism, & Multi-Threading
* **Tingkat Kesulitan:** Advanced / Senior Software Engineer
* **Prasyarat Pengetahuan:**
  * Penguasaan mendalam atas Object Model Ruby, Block, Proc, dan Lambda.
  * Pemahaman arsitektur sistem operasi: Thread, Process, Virtual Memory, Syscalls, dan I/O Multiplexing (`epoll`/`kqueue`).
  * Pemahaman dasar tentang memori heap/stack dan siklus Garbage Collection (GC).
* **Target Runtime:** MRI Ruby (CRuby) 3.2+ (dengan perbandingan struktural terhadap JRuby dan TruffleRuby).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik memiliki kompetensi terverifikasi untuk:

1. **Membedakan secara rigid** batas ontologis antara *Concurrency* (struktur penanganan banyak tugas secara parsial/interleaved) dan *Parallelism* (eksekusi simultan tugas pada multi-core hardware).
2. **Membedah mekanika Global VM Lock (GVL)** pada CRuby, termasuk aturan pelepasan lock pada blocking I/O dan syscalls, serta implikasinya terhadap performa CPU-bound vs I/O-bound.
3. **Mengimplementasikan dan mengamankan sinkronisasi multi-thread** menggunakan primitif native: `Thread`, `Mutex`, `Monitor`, `ConditionVariable`, dan thread-safe data structures (`Queue`, `SizedQueue`).
4. **Mendeteksi, mendiagnosis, dan memitigasi anomali konkurensi:** Race Conditions, Deadlocks, Livelocks, Priority Inversion, dan Thread Leakage.
5. **Mengevaluasi trade-offs arsitektural** antara Multi-Threading, Multi-Processing (`fork`), Coroutine/Cooperative Concurrency (`Fiber`), dan Actor-based Concurrency (`Ractor`).
6. **Membangun sistem background worker/processor multi-thread tingkat enterprise** yang dilengkapi *bounded worker pool*, *backpressure handling*, *graceful shutdown*, dan *exception isolation*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: Konkurensi Bukan Paralelisme

Bayangkan dapur restoran dengan koki dan kompor:
* **Konkurensi (Concurrency):** Satu koki (1 CPU Core) mengelola 4 masakan sekaligus (4 Threads). Koki merebus pasta, lalu saat pasta menunggu mendidih (Blocking I/O), koki beralih memotong bawang (CPU task), lalu mengecek panggangan. Banyak tugas berjalan secara bersamaan dalam jendela waktu tertentu, tetapi hanya satu tindakan fisik yang dieksekusi koki pada instan waktu tertentu.
* **Paralelisme (Parallelism):** Restoran mempekerjakan 4 koki berbeda (4 CPU Cores) yang masing-masing memotong bahan secara fisik bersamaan pada detik yang sama persis.
* **Global VM Lock (GVL):** Di CRuby, terdapat satu "spatula emas" di dapur. Meskipun ada 8 koki (8 thread OS native), hanya koki yang memegang spatula emas yang boleh menyentuh bahan masakan Ruby (mengeksekusi bytecode Ruby). Koki lain harus menunggu spatula diserahkan, kecuali jika seorang koki sedang menunggu bahan dikirim pemasok dari luar dapur (I/O syscall), maka spatula diserahkan sementara ke koki lain.

### Prinsip Deterministik vs Non-Deterministik

Dalam eksekusi sekuensial (single-thread), status program bersifat deterministik linear: $S_{n+1} = f(S_n)$. 

Dalam eksekusi multi-thread, interleaving instruksi ditentukan oleh *OS Thread Scheduler* dan *Ruby VM Scheduler*. Jika dua thread membaca dan memodifikasi shared memory tanpa koordinasi eksplisit, urutan instruksi menjadi non-deterministik:
```
Thread A: Read X -> Modify X -> Write X
Thread B:        Read X -----------------> Modify X -> Write X (Data Overwritten!)
```
Sebagai arsitek perangkat lunak, mindset Anda harus bergeser dari:
> *"Kode saya dieksekusi baris demi baris"*

menjadi:
> *"Setiap operasi antar-baris (dan sub-operasi bytecode) dapat diinterupsi oleh thread lain kapan saja, kecuali dijamin oleh synchronization primitive."*

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Arsitektur Threading CRuby (MRI) dengan GVL

```
+-----------------------------------------------------------------------+
|                             RUBY PROCESS                              |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  |                    Global VM Lock (GVL)                         |  |
|  |         [ Held by Thread 1: Executing Ruby Bytecode ]           |  |
|  +-----------------------------------------------------------------+  |
|               |                                  ^                    |
|      Releases on I/O / Syscall                   | Acquires GVL back  |
|               v                                  | on I/O return      |
|  +-------------------------+        +------------------------------+  |
|  | Native OS Thread 1      |        | Native OS Thread 2           |  |
|  | State: Blocking in I/O  |        | State: Runnable / Running    |  |
|  | Syscall: read(2) / poll |        | Executing Ruby Bytecode      |  |
|  +-------------------------+        +------------------------------+  |
|               ^                                  ^                    |
|               | Kernel Context Switch            |                    |
+---------------|----------------------------------|--------------------+
                v                                  v
+-----------------------------------------------------------------------+
|                           OS KERNEL SPACE                             |
|                                                                       |
|    [ CPU Core 0 ]              [ CPU Core 1 ]          [ Socket Buf ] |
|   Running Thread 2             Thread 1 (Blocked) <--- Data Arrives   |
+-----------------------------------------------------------------------+
```

### 2. Alur Transisi State Thread & Mutex Acquisition

```
   [ Thread.new ]
          |
          v
   +--------------+
   |   CREATED    |
   +--------------+
          |
          | (Enters scheduler run-queue)
          v
   +--------------+       Acquire Mutex Failed       +--------------+
   |   RUNNABLE   | -------------------------------> |   SLEEPING   |
   +--------------+                                  | (Mutex Lock) |
          |  ^                                       +--------------+
Scheduler |  | Preemption /                                 |
Picks Up  |  | Timer Thread (100ms)                         | Mutex Unlocked
          v  |                                              v
   +--------------+        I/O Syscall / Sleep       +--------------+
   |   RUNNING    | -------------------------------> |   SLEEPING   |
   +--------------+                                  | (I/O Wait)   |
          |                                          +--------------+
          | Thread finishes / Error                         |
          v                                                 | I/O Done
   +--------------+                                         |
   |     DEAD     | <---------------------------------------+
   +--------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. 1:1 Native Thread Mapping

Pada masa Ruby 1.8 (Green Threads), Ruby VM mengelola thread di *User Space* sepenuhnya di atas 1 OS process. Sejak Ruby 1.9+, CRuby mengadopsi model **1:1 Native Threading**. 
* Setiap instance `Thread.new` membuat thread sistem operasi native yang sebenarnya (`pthread_create` di Linux/macOS atau `CreateThread` di Windows).
* Thread-thread ini dialokasikan kernel stack sendiri (default 1MB–8MB tergantung OS) dan dijadwalkan oleh kernel OS.

### 2. Global VM Lock (GVL / GIL) Deep Dive

Meskipun setiap thread Ruby adalah native OS thread, CRuby membungkus eksekusi bytecode dalam sebuah mutex internal yang disebut **GVL**.
* **Tujuan GVL:** Melindungi struktur internal CRuby yang *not thread-safe*, terutama alokasi memory heap, ObjectSpace, method cache, dan Garbage Collector (GC).
* **Mekanisme Preemption:** 
  * CRuby menjalankan *timer thread* internal (tick rate default: 100 milidetik pada sistem POSIX).
  * Setelah interval ini tercapai, timer thread mengirim interupsi ke native thread yang sedang mengeksekusi bytecode Ruby.
  * Native thread tersebut memeriksa flag interupsi pada *safe point*, melepaskan GVL, dan menyerahkan kesempatan kepada thread Ruby lain yang siap berjalan (*preemptive multitasking* pada layer VM).

### 3. I/O Release Invariant

Ketika kode Ruby memanggil I/O (misalnya `File.read`, `TCPSocket#write`, `Kernel.sleep`, atau gem C-extension yang memanggil API eksternal yang dibungkus `rb_thread_call_without_gvl()`):
1. Native thread mengeksekusi fungsi C runtime CRuby.
2. CRuby mencatat bahwa thread ini memasuki kondisi I/O blocking.
3. Thread **melepaskan GVL**.
4. Native thread memanggil blocking syscall di OS kernel (misal `read(2)` atau `epoll_wait(2)`).
5. Thread lain langsung mengambil alih GVL dan mengeksekusi instruksi Ruby.
6. Saat syscall thread pertama selesai, ia tidak bisa langsung melanjutkan kode Ruby; ia harus mengantre untuk **mengakuisisi kembali GVL** sebelum membaca respon buffer ke dalam struktur `RString`.

### 4. MRI vs JRuby vs TruffleRuby

| Parameter | CRuby (MRI) | JRuby | TruffleRuby |
| :--- | :--- | :--- | :--- |
| **Bentuk Thread** | Native 1:1 (pthreads) | Native 1:1 (JVM Threads) | Native 1:1 (GraalVM / pthreads) |
| **GVL/GIL** | **ADA** (Bytecode lock) | **TIDAK ADA** | **TIDAK ADA** |
| **Paralelisme CPU-bound** | Tidak (Gunakan Process/Ractor) | Ya (Full Multi-core) | Ya (Full Multi-core) |
| **Paralelisme I/O-bound** | Ya (via GVL release) | Ya | Ya |
| **Safety Overhead** | Lebih mudah terhindar dari crash VM C | Butuh sinkronisasi penuh pada shared state | Butuh sinkronisasi penuh pada shared state |

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. The Myth: "GVL Makes Ruby Thread-Safe"

Ini adalah miskonsepsi fatal terbesar di ekosistem Ruby.
**GVL melindungi integritas internal VM C, BUKAN integritas aplikasi kode Ruby Anda.**

Perhatikan operasi sederhana ini:
```ruby
@counter += 1
```
Pada tingkat bytecode YARV (Yet Another Ruby VM), operasi di atas diterjemahkan menjadi minimal 3 instruksi:
```text
0000 getinstancevariable    :@counter
0002 opt_plus               <call-info>
0004 setinstancevariable    :@counter
```
Timer thread CRuby atau OS scheduler dapat memotong eksekusi tepat di antara instruksi `getinstancevariable` dan `setinstancevariable`. Jika Thread A membaca `@counter` (nilai 5), terinterupsi, Thread B masuk dan membaca `@counter` (nilai 5), menambahkan 1 menjadi 6, menyimpannya. Lalu Thread A kembali berjalan, menambahkan 1 ke nilai lokalnya (5 + 1 = 6), dan menyimpannya. 
Hasil akhir: `@counter` bernilai 6, padahal dieksekusi 2 kali. Terjadi **Race Condition**.

### 2. Synchronization Primitives

#### A. Mutex (Mutual Exclusion)
`Mutex` menjamin bahwa hanya satu thread yang dapat mengeksekusi blok kode *critical section* pada satu waktu.
```ruby
mutex = Mutex.new

mutex.synchronize do
  # Critical section: operasi read-modify-write atomik
  @counter += 1
end
```
Operasi `synchronize` secara otomatis melepaskan lock bahkan jika eksepsi (exception) terjadi di dalam blok, mencegah kebocoran lock (*lock leak*).

#### B. ConditionVariable
Digunakan ketika thread harus menanti kondisi tertentu terpenuhi tanpa melakukan *busy-waiting* (spinning CPU 100%). `ConditionVariable` harus selalu digunakan bersamaan dengan `Mutex`.
* `wait(mutex)`: Melepaskan mutex secara atomik dan menidurkan thread.
* `signal`: Membangunkan satu thread yang sedang menunggu di condition variable ini.
* `broadcast`: Membangunkan seluruh thread yang sedang menunggu.

#### C. Thread-Safe Queues (`Queue` & `SizedQueue`)
CRuby menyediakan primitif struktur data thread-safe native di dalam module `Thread`:
* `Thread::Queue`: Antrean unbounded (tanpa batas). Operasi `push` non-blocking, `pop` blocking jika antrean kosong.
* `Thread::SizedQueue`: Antrean bounded (memiliki kapasitas maksimum). Memberikan kapabilitas **Backpressure**: jika antrean penuh, thread produsen (producer) akan di-suspend sampai konsumen (consumer) mengambil item.

### 3. Paradigma Alternatif: Fibers & Ractors

* **Fibers (Cooperative Concurrency):** Ringan (alokasi memori ~4KB vs Thread ~1MB). Tidak ada preemption otomatis. Fiber berpindah eksekusi secara eksplisit via `Fiber.yield` dan `fiber.resume`. Ruby 3.0+ memperkenalkan `Fiber::Scheduler` yang mengotomasi switching I/O non-blocking secara transparan.
* **Ractors (Ruby 3+ Parallel Execution):** Menyediakan true parallelism tanpa GVL bottleneck di CRuby. Setiap Ractor memiliki GVL-nya sendiri. Komunikasi antar Ractor dilakukan via message passing tanpa berbagi mutable object secara bebas (Share-nothing architecture). Objek yang dikirim harus di-*freeze* atau di-*move*.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode komparatif interaktif: mendemonstrasikan timbulnya Race Condition dan eliminasinya menggunakan `Mutex` serta `ConditionVariable`.

```ruby
# frozen_string_literal: true

require 'benchmark'

class ConcurrencyPlayground
  def self.demonstrate_race_condition
    puts "=== 1. SIMULASI RACE CONDITION (UNSAFE) ==="
    counter = 0
    threads = []

    # Jalankan 10 thread, masing-masing melakukan increment 10.000 kali
    10.times do
      threads << Thread.new do
        10_000.times do
          # Interleaving buatan agar VM memaksa preemption
          current = counter
          Thread.pass # Menyerahkan sisa time-slice ke thread lain secara paksa
          counter = current + 1
        end
      end
    end

    threads.each(&:join)
    puts "Nilai teoretis : 100000"
    puts "Nilai aktual   : #{counter}"
    puts "Status         : #{counter == 100_000 ? 'SUCCESS' : 'CORRUPTED (RACE CONDITION DETECTED)'}\n\n"
  end

  def self.demonstrate_mutex_synchronization
    puts "=== 2. SIMULASI SYNCHRONIZATION DENGAN MUTEX ==="
    counter = 0
    mutex = Mutex.new
    threads = []

    10.times do
      threads << Thread.new do
        10_000.times do
          mutex.synchronize do
            current = counter
            Thread.pass
            counter = current + 1
          end
        end
      end
    end

    threads.each(&:join)
    puts "Nilai teoretis : 100000"
    puts "Nilai aktual   : #{counter}"
    puts "Status         : #{counter == 100_000 ? 'SUCCESS (THREAD-SAFE)' : 'CORRUPTED'}\n\n"
  end

  def self.demonstrate_condition_variable
    puts "=== 3. PRODUCER-CONSUMER VIA CONDITION VARIABLE ==="
    mutex = Mutex.new
    resource_ready = ConditionVariable.new
    buffer = []

    consumer = Thread.new do
      mutex.synchronize do
        puts "[Consumer] Menunggu payload..."
        # Selalu gunakan loop 'while', bukan 'if', untuk menangani Spurious Wakeups
        resource_ready.wait(mutex) while buffer.empty?
        item = buffer.pop
        puts "[Consumer] Menerima payload: #{item}"
      end
    end

    producer = Thread.new do
      sleep 0.5 # Mensimulasikan I/O latency pembuatan data
      mutex.synchronize do
        puts "[Producer] Data selesai diproduksi. Memasukkan ke buffer."
        buffer.push("PACKET_#42")
        resource_ready.signal # Bangunkan consumer
      end
    end

    [consumer, producer].each(&:join)
  end
end

ConcurrencyPlayground.demonstrate_race_condition
ConcurrencyPlayground.demonstrate_mutex_synchronization
ConcurrencyPlayground.demonstrate_condition_variable
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Kasus 1: Race Condition Playground
* `Thread.new do ... end`: Mengalokasikan 1 Native OS Thread. Blok di dalamnya mulai dieksekusi secara asynchronous di bawah pengelolaan thread scheduler OS dan CRuby GVL.
* `current = counter`: Membaca variabel lokal luar (closure capture) ke dalam context stack lokal thread.
* `Thread.pass`: Memaksa scheduler VM untuk melepaskan giliran eksekusi (*yield execution*) dan melepaskan GVL secara sukarela. Ini mengekspos race window secara konsisten untuk tujuan demonstrasi.
* `counter = current + 1`: Mengeset variabel bersama dengan nilai yang telah basi (*stale value*) jika thread lain sempat mengubahnya di sela jeda.
* `threads.each(&:join)`: Blok thread pemanggil (Main Thread) akan di-*suspend* sampai thread yang di-`join` selesai mengeksekusi instruksi terakhirnya. Tanpa ini, Main Thread akan langsung keluar dan mematikan seluruh worker thread secara prematur.

### Analisis Kasus 2: Mutex Synchronization
* `mutex = Mutex.new`: Menginisialisasi primitif sinkronisasi tingkat C level. Mutex ini melacak ID thread pemilik yang sedang memegang lock.
* `mutex.synchronize do ... end`: 
  1. Thread memanggil `mutex.lock`. Jika mutex dipegang thread lain, thread pemanggil masuk ke state `SLEEPING` dan melepaskan GVL.
  2. Menjamin eksekusi blok kode hanya oleh 1 thread dalam satu waktu.
  3. Memastikan `ensure` block dieksekusi di level internal C untuk memanggil `mutex.unlock`, menjamin pelepasan lock secara deterministik bahkan saat terjadi `StandardError`, `NoMemoryError`, atau interupsi `Thread#kill`.

### Analisis Kasus 3: ConditionVariable Coordination
* `resource_ready = ConditionVariable.new`: Objek signal queue antar thread.
* `resource_ready.wait(mutex) while buffer.empty?`:
  * **Kritis:** Penggunaan loop `while`, bukan `if`. Ini adalah standar industri untuk memitigasi **Spurious Wakeup** (keadaan di mana OS membangunkan thread tanpa ada sinyal eksplisit) atau kondisi balapan di mana sinyal diterima oleh thread lain terlebih dahulu.
  * Ketika `wait` dipanggil, `mutex` **dilepaskan secara atomik** oleh VM dan thread beralih status menjadi dormant (`SLEEPING`).
* `resource_ready.signal`: Memindahkan satu thread dari antrean tunggu ConditionVariable kembali ke antrean Runnable (yang kemudian harus mengakuisisi ulang `mutex` sebelum melanjutkan blok eksekusinya).

---

## SEKSI 09 — STUDI KASUS NYATA (PRODUCTION SCENARIO)

### Latar Belakang Masalah
Sebuah platform perbankan digital perlu melakukan verifikasi status transaksi ke 5.000 gateway pihak ketiga setiap jam (Batch Health Audit). 
* **Karakteristik Task:** Murni I/O-bound (HTTP latency bervariasi antara 100ms hingga 2.500ms).
* **Masalah Desain Naif (Single-Thread):** $5000 \times 1\text{s} = 5000\text{s} \approx 83\text{ menit}$ (Melebihi jendela eksekusi 1 jam!).
* **Masalah Desain Reaktif Naif (`Thread.new` tak terbatas):** Membuka 5.000 thread native secara serentak menyebabkan:
  1. *Resource Exhaustion:* Memori meledak ($5000 \times \sim 1\text{MB OS Stack} \approx 5\text{GB RAM}$).
  2. *OS File Descriptor Limits (`EMFILE` error):* Kehabisan socket open file limits.
  3. *DoS pada Gateway Target:* Terkena blokir WAF / Rate Limiter IP.

### Solusi Arsitektur Enterprise
Membangun **Bounded Thread-Pool Worker Pipeline** dengan spesifikasi:
1. Pool Thread statis dan terkontrol (misal: 25 worker).
2. `SizedQueue` untuk membatasi buffer antrean pekerjaan (Backpressure control).
3. Penanganan error yang terisolasi (satu thread gagal tidak merusak pool).
4. Penanganan sinyal OS (`SIGINT`, `SIGTERM`) untuk **Graceful Shutdown**: menyelesaikan pekerjaan yang sedang berjalan dan menolak antrean baru tanpa data loss.
5. Thread-safe metrics collector.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi lengkap, modular, dan siap digunakan di production untuk Bounded Worker Pool.

```ruby
# frozen_string_literal: true

require 'net/http'
require 'uri'
require 'json'
require 'logger'

module Core
  class ThreadPool
    attr_reader :size, :queue_capacity

    def initialize(size:, queue_capacity:)
      @size = size
      @queue_capacity = queue_capacity
      @work_queue = SizedQueue.new(queue_capacity)
      @workers = []
      @shutdown_flag = false
      @mutex = Mutex.new
      @logger = Logger.new($stdout)
      @logger.formatter = proc do |severity, datetime, _progname, msg|
        "[#{datetime.strftime('%Y-%m-%d %H:%M:%S.%L')}] [#{severity}] [TID-#{Thread.current.object_id}] #{msg}\n"
      end

      spawn_workers!
    end

    def post(payload, &block)
      @mutex.synchronize do
        raise 'ThreadPool is shutdown, rejecting new work' if @shutdown_flag
      end

      # Blocking push: jika antrean mencapai @queue_capacity, caller thread akan disuspend
      # Ini mencegah buffer-bloat / memory exhaustion
      @work_queue.push([payload, block])
      true
    end

    def shutdown
      @mutex.synchronize do
        return if @shutdown_flag
        @logger.info("Menerima sinyal shutdown. Menghentikan worker...")
        @shutdown_flag = true
      end

      # Mengirim 'POISON PILL' sejumlah worker untuk memutus loop worker secara anggun
      @size.times do
        @work_queue.push(:POISON_PILL)
      end

      @workers.each(&:join)
      @logger.info("Semua worker berhasil dimatikan secara aman.")
    end

    private

    def spawn_workers!
      @size.times do |i|
        @workers << Thread.new do
          Thread.current.name = "ThreadPool-Worker-#{i + 1}"
          loop do
            work = @work_queue.pop

            break if work == :POISON_PILL

            payload, task = work
            execute_task(payload, task)
          end
        rescue Exception => e
          # Tangkal fatal error di luar task execution agar thread pool tidak bocor
          @logger.fatal("FATAL: Worker thread anjlok akibat: #{e.class}: #{e.message}")
        end
      end
    end

    def execute_task(payload, task)
      task.call(payload)
    rescue StandardError => e
      @logger.error("Kegagalan task pada payload #{payload}: #{e.class} - #{e.message}")
      @logger.debug(e.backtrace.join("\n"))
    end
  end
end

# === Skenario Penggunaan Nyata: Batch Verification Worker ===

class TransactionAuditor
  def initialize
    @pool = Core::ThreadPool.new(size: 5, queue_capacity: 10)
    @metrics_mutex = Mutex.new
    @processed_count = 0
    @failure_count = 0
  end

  def run_audit(transactions)
    puts "Mulai menjadwalkan #{transactions.size} transaksi..."

    transactions.each do |tx|
      # Backpressure bekerja di sini: jika antrean penuh, caller ditahan
      @pool.post(tx) do |data|
        process_transaction(data)
      end
    end

    # Graceful shutdown saat selesai
    @pool.shutdown
    print_metrics
  end

  private

  def process_transaction(tx)
    # Simulasi I/O HTTP Request ke Payment Gateway API
    # MRI melepaskan GVL selama operasi sleep ini!
    latency = rand(0.05..0.2)
    sleep(latency)

    if rand < 0.1 # Simulasi kegagalan 10%
      raise StandardError, "Network Gateway Timeout (HTTP 504) untuk TX_ID: #{tx[:id]}"
    end

    record_metric(success: true)
  rescue StandardError => e
    record_metric(success: false)
    raise e # Re-raise agar logger internal ThreadPool menangkap error ini
  end

  def record_metric(success:)
    @metrics_mutex.synchronize do
      if success
        @processed_count += 1
      else
        @failure_count += 1
      end
    end
  end

  def print_metrics
    puts "\n=== LAPORAN EKSEKUSI AUDIT ==="
    puts "Total Sukses : #{@processed_count}"
    puts "Total Gagal  : #{@failure_count}"
    puts "Total Diproses: #{@processed_count + @failure_count}"
  end
end

# Eksekusi Demo
dummy_transactions = (1..50).map { |i| { id: "TX-#{1000 + i}", amount: rand(10..500) } }
auditor = TransactionAuditor.new
auditor.run_audit(dummy_transactions)
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Untuk memilih model konkurensi/paralelisme yang tepat di ekosistem Ruby, evaluasi matriks trade-off teknis berikut:

| Karakteristik | Multi-Threading (`Thread`) | Multi-Processing (`Process.fork`) | Fiber Scheduler (`Fiber`) | Ractor (`Ractor`) |
| :--- | :--- | :--- | :--- | :--- |
| **Model Memori** | Shared Memory | Copy-on-Write (Isolated) | Shared Memory (Cooperative) | Share-Nothing / Isolated Heap |
| **Beban Overhead Memori** | Rendah (~1MB per OS stack) | Tinggi (Duplikasi Heap footprint) | Sangat Ringan (~4KB) | Sedang (Per-actor memory heap) |
| **Kemampuan Multi-Core** | Tidak di CRuby (Ya di JRuby) | **Ya (True Parallelism)** | Tidak (Single Core per loop) | **Ya (True Parallelism)** |
| **Safety Terhadap Race Conditions** | **Rentan** (Wajib Mutex) | **Sangat Aman** | Sedang (Non-preemptive switch) | **Aman** (Object immutability check) |
| **Kasus Penggunaan Optimal** | I/O Bound (HTTP Client, DB query) | CPU Bound (Image processing, ETL berat) | High-Concurrency I/O (WebSockets, Proxies) | CPU Bound paralel murni dalam 1 process |
| **Kompleksitas Debugging** | Tinggi (Heisenbugs, Deadlocks) | Rendah (State terisolasi antar worker) | Sedang (Tracing async context) | Tinggi (Error sharing mutable objects) |
| **Kompatibilitas Ekosistem Gem** | Tinggi (Mayoritas gem modern safe) | Sangat Tinggi | Menengah (Perlu non-blocking socket shim) | Masih Eksperimental / Terbatas |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Silent Thread Death (Menelan Error Secara Diam-Diam)
Secara default di versi Ruby lawas, atau jika konfigurasi diabaikan, thread yang memicu uncaught exception akan langsung mati tanpa mencetak trace atau menghentikan main program. Program Anda tampak "hang" seolah-olah kekurangan worker.
* **Solusi Mutlak:**
  ```ruby
  # Aktifkan flag global ini saat inisialisasi aplikasi
  Thread.abort_on_exception = true
  ```
  Atau aktifkan per-thread instance:
  ```ruby
  t = Thread.new { ... }
  t.abort_on_exception = true
  ```

### 2. Mutex Deadlocks
Deadlock terjadi ketika Thread A menanti sumber daya yang dipegang Thread B, sementara Thread B menanti sumber daya yang dipegang Thread A (Circular Wait).
```ruby
# POTENSI DEADLOCK:
# Thread 1:
mutex_a.synchronize do
  sleep 0.1
  mutex_b.synchronize { ... }
end

# Thread 2:
mutex_b.synchronize do
  sleep 0.1
  mutex_a.synchronize { ... }
end
```
* **Pencegahan:** Selalu akuisisi lock dalam **urutan hierarkis yang sama secara konsisten** di seluruh bagian codebase. Alternatif: gunakan `mutex.try_lock` dengan timeout dan fallback logic.

### 3. Thread-Safety pada Core Data Structures
Array (`[]`) dan Hash (`{}`) di CRuby **BUKAN THREAD-SAFE**. Meskipun operasi internal C-level hash lookups memiliki perlindungan mikro GVL, mutasi struktural (`<<`, `[]=`, `.delete`) dari multiple thread dapat menyebabkan segfault level C atau data loss:
```ruby
# BERBAHAYA
unsafe_hash = {}
10.times.map do
  Thread.new { 1000.times { |i| unsafe_hash[rand(100)] = i } }
end.each(&:join)
# Hash internal buckets bisa mengalami pointer corruption!
```
* **Solusi:** Bungkus akses ke hash dengan `Mutex`, atau gunakan struktur data concurrent dari gem `concurrent-ruby` (`Concurrent::Map`).

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Mistake 1: Menggunakan `Thread.kill` atau `Thread#terminate` Secara Kasar
Mematikan thread secara paksa (`Thread#kill`) memotong eksekusi secara instan di sembarang baris assembly.
```ruby
# ANTI-PATTERN
worker = Thread.new do
  mutex.synchronize do
    # Tulis file atau database transaction
  end
end
worker.kill # KATASTROPIK! Mutex terkunci selamanya, IO handle bocor.
```
* **Koreksi:** Gunakan cooperative cancellation flag:
```ruby
# PATTERN BENAR
@running = true
worker = Thread.new do
  while @running
    # Lakukan tugas kecil
  end
  # Cleanup code
end
# Request shutdown
@running = false
worker.join
```

### Mistake 2: Variabel Closure Terikat pada Loop Variable
```ruby
# ANTI-PATTERN
threads = []
10.times do |i|
  threads << Thread.new do
    puts i # Seluruh thread bisa mencetak angka 9 atau 10 akibat race condition variable binding!
  end
end
threads.each(&:join)
```
* **Koreksi:** Operasikan passing variable sebagai argumen eksplisit ke blok `Thread.new`:
```ruby
# PATTERN BENAR
threads = []
10.times do |i|
  threads << Thread.new(i) do |thread_local_i|
    puts thread_local_i # Aman, terisolasi dalam stack frame lokal thread
  end
end
threads.each(&:join)
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Favor Message Passing over Shared Memory:** Adopsi filosofi Go: *"Do not communicate by sharing memory; instead, share memory by communicating."* Gunakan `Thread::Queue` atau `Thread::SizedQueue` untuk memindahkan data antar thread alih-alih memanipulasi shared array/hash global.
2. **Never Execute Arbitrary Code inside Mutex:** Jaga agar durasi di dalam blok `mutex.synchronize` sependek mungkin. Jangan pernah memanggil network I/O, disk write lambat, atau dynamic callback di dalam critical section karena akan memblokir thread lain secara masif.
3. **Always Bound Your Threads:** Jangan biarkan aplikasi melakukan alokasi thread tak terbatas berdasarkan input external (misal: 1 incoming HTTP request = 1 new Thread). Gunakan bounded worker pools dengan fixed capacity.
4. **Nama-i Setiap Thread Anda:** Selalu berikan nama identifikasi pada thread menggunakan `Thread.current.name = "Worker-Name"`. Ini sangat krusial saat membaca log diagnostic atau thread dumps (`Thread.list`).
5. **Gunakan Gem Standar Industri untuk Kebutuhan Kompleks:** Daripada membuat primitif tingkat rendah sendiri untuk production level kompleks, gunakan gem yang telah teruji battle-tested seperti **`concurrent-ruby`** (`Concurrent::ThreadPoolExecutor`, `Concurrent::Map`, `Concurrent::Promise`).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Menentukan Kapasitas Thread Pool
Formula matematis industri untuk estimasi jumlah thread optimal:

$$N_{\text{threads}} = N_{\text{CPU}} \times \left(1 + \frac{\text{Wait Time (I/O)}}{\text{Compute Time (CPU)}}\right)$$

* **Aplikasi CPU-Bound:** $\text{Wait Time} \approx 0 \implies N_{\text{threads}} = N_{\text{CPU}}$ (Gunakan Process/Ractor, multi-thread tidak menguntungkan di CRuby karena GVL).
* **Aplikasi I/O-Bound (misal HTTP Gateway Scraper):** Jika waktu pemrosesan CPU adalah 5ms dan waktu latensi tunggu jaringan adalah 95ms:
  $$\frac{\text{Wait}}{\text{Compute}} = \frac{95}{5} = 19$$
  Maka pada mesin 4 Core: $4 \times (1 + 19) = 80\text{ Threads}$.

### 2. Alokasi Memori Stack
Pada Linux, thread native mengalokasikan virtual memory untuk call stack. Jika Anda menjalankan 500 thread, konfigurasi stack OS dapat menghabiskan virtual memory secara cepat. Anda dapat mengontrol ukuran stack VM Ruby via environment variables:
```bash
# Kurangi ukuran stack thread ruby (default biasanya bervariasi antara 512KB - 1MB)
export RUBY_THREAD_VM_STACK_SIZE=524288 # 512KB
```

### 3. Dampak terhadap Ruby Garbage Collector (GC)
Thread allocation yang intensif menciptakan pressure besar pada Garbage Collector. GC di CRuby mengadopsi mekanisme *Stop-The-World* (STW):
* Saat GC full run berlangsung, **seluruh thread Ruby dihentikan seketika** terlepas apakah thread tersebut sedang memegang GVL atau tidak.
* Hindari instansiasi objek sementara (*ephemeral objects*) di dalam loop cepat multi-thread agar tidak memicu GC cycle terlalu sering.

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Thread Pool Exhaustion / Denial of Service (DoS)
Jika endpoint aplikasi memicu pembuatan thread baru tanpa batas, penyerang dapat mengirimkan ribuan request lambat secara simultan (*Slowloris attack*). OS akan kehabisan thread descriptors atau memory, memicu crash kernel:
* **Mitigasi:** Pasang batas tegas pada level application server (misal konfigurasi thread Puma: `threads min_threads, max_threads` dengan batas rasional, misal max 16-32 per process).

### 2. Time-of-Check to Time-of-Use (TOCTOU) Flaws
Kerentanan keamanan konkurensi di mana pemeriksaan kondisi otorisasi atau validasi saldo dipisahkan dari eksekusinya:
```ruby
# VULNERABLE TOCTOU EXPLOIT
def withdraw(amount)
  if @balance >= amount # Thread A & Thread B lolos cek bersamaan
    Thread.pass
    @balance -= amount # Saldo menjadi negatif!
  end
end
```
* **Hardening:** Pastikan atomic check-and-set menggunakan Mutex atau DB-level row locking (`SELECT FOR UPDATE`).

### 3. Reentrancy Hazard
`Mutex` standar di Ruby bersifat **non-reentrant**. Jika sebuah thread mencoba mengunci kembali mutex yang telah dipegangnya sendiri, sistem akan langsung memicu error:
```ruby
m = Mutex.new
m.synchronize do
  m.synchronize do # Menghasilkan: ThreadError: deadlock; recursive locking
  end
end
```
Jika arsitektur membutuhkan locking rekursif, gunakan `Monitor` dari standard library (`require 'monitor'`), yang mengizinkan locking reentrant oleh thread pemilik yang sama.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Thread Dumps Secara On-Demand
Ketika aplikasi hang atau mengalami deadlock di production, ambil thread dump seketika tanpa mematikan process.

```ruby
def dump_thread_backtraces
  puts "================== THREAD DUMP SNAPSHOT =================="
  Thread.list.each do |t|
    puts "Thread TID: #{t.object_id} Name: '#{t.name}' Status: #{t.status}"
    puts "Priority: #{t.priority} AbortOnException: #{t.abort_on_exception}"
    puts (t.backtrace || []).map { |line| "  #{line}" }.join("\n")
    puts "---------------------------------------------------------"
  end
end

# Daftarkan trap sinyal SIGQUIT (Ctrl+\) atau SIGUSR1 untuk memicu dump
trap("SIGUSR1") do
  dump_thread_backtraces
end
```

### 2. Structured Logging dengan Contextual Thread IDs
Dalam aplikasi multi-thread, output log dari berbagai thread akan bercampur aduk secara acak. Log analyzer (Datadog, Elastic, Loki) membutuhkan contextual ID untuk merekonstruksi alur program per-thread:

```ruby
require 'logger'

class ThreadContextFormatter < Logger::Formatter
  def call(severity, time, _progname, msg)
    tid = Thread.current[:request_id] || Thread.current.name || Thread.current.object_id
    sprintf(
      "[%s] [%s] [Worker: %s] %s\n",
      time.iso8601(3),
      severity,
      tid,
      msg2str(msg)
    )
  end
end
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```ruby
# -------------------------------------------------------------
# CHEAT SHEET: THREADING & SYNCHRONIZATION PRIMITIVES
# -------------------------------------------------------------

# 1. INSTANSIASI THREAD
t = Thread.new(arg1, arg2) do |a, b|
  Thread.current.name = "MyWorker"
  # Eksekusi kerja di sini
end
t.join(5.0) # Tunggu hingga selesai, timeout 5 detik

# 2. MUTEX LOCKING ATOMIK
m = Mutex.new
m.synchronize do
  # Critical section aman dari race condition
end

# 3. THREAD-SAFE QUEUE (PRODUCER/CONSUMER)
q = SizedQueue.new(100) # Kapasitas maks 100 item (Backpressure)
q.push(item)            # Block jika penuh
data = q.pop            # Block jika kosong

# 4. CONDITION VARIABLE (SIGNALING)
cv = ConditionVariable.new
m.synchronize do
  cv.wait(m) while condition_not_met? # Lepas mutex & sleep
  cv.signal                           # Bangunkan 1 waiter
  cv.broadcast                        # Bangunkan semua waiter
end

# 5. DIAGNOSTIK GLOBAL
Thread.list                 # Daftar semua thread aktif di VM
Thread.abort_on_exception = true # Hindari silent death
```

* **Aturan Emas GVL:** CRuby **tidak bisa** mengeksekusi instruksi CPU Ruby secara paralel pada banyak core. Multi-threading di CRuby murni ditujukan untuk menyembunyikan **latensi I/O**.
* **Keamanan Shared State:** Jika lebih dari 1 thread dapat mengakses objek mutable, Anda **wajib** menggunakan synchronization (`Mutex`, `Queue`).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Uji penguasaan konsep Anda terhadap sistem multi-threading Ruby melalui soal evaluasi berikut.

### Kategori Basic

1. **Apakah dua thread di CRuby (MRI) dapat mengeksekusi kalkulasi enkripsi matematika (CPU-bound) pada dua CPU Core yang berbeda secara simultan?**
   * A. Ya, karena Ruby 1.9+ menggunakan Native OS Thread.
   * B. Ya, jika diaktifkan via environment variable `RUBY_PARALLEL=1`.
   * C. Tidak, karena GVL (Global VM Lock) membatasi eksekusi bytecode Ruby hanya pada 1 thread dalam satu waktu.
   * D. Tidak, karena Ruby tidak mendukung Native Threads.
   * *Jawaban:* **C**. Penjelasan: Meskipun thread Ruby adalah native OS threads, GVL mencegah eksekusi paralel bytecode Ruby pada CPU-bound task di CRuby.

2. **Apa yang terjadi secara default jika sebuah background thread di Ruby memicu error `RuntimeError` yang tidak di-rescue?**
   * A. Seluruh sistem operasi melakukan restart.
   * B. Process Ruby crash seketika dengan return code 1.
   * C. Thread tersebut mati diam-diam (*silent death*), sementara thread lain tetap berjalan kecuali `Thread.abort_on_exception` aktif.
   * D. Error secara otomatis di-forward ke Main Thread.
   * *Jawaban:* **C**. Penjelasan: Secara historis dan default, uncaught exception pada thread anak akan mematikan thread tersebut tanpa menghentikan process utama, kecuali thread tersebut di-`join` atau flag `abort_on_exception` diset `true`.

3. **Mengapa pemanggilan method `Thread.pass` berguna dalam pengujian kode multi-thread?**
   * A. Membunuh thread yang sedang idle.
   * B. Mengalokasikan core CPU baru secara dinamis.
   * C. Meminta thread scheduler OS/VM untuk merelokasi jatah waktu (yield) ke thread lain, memicu race window jika kode tidak sinkron.
   * D. Membersihkan alokasi memori GC.
   * *Jawaban:* **C**. Penjelasan: `Thread.pass` memberikan petunjuk kepada VM scheduler untuk menyerahkan giliran eksekusi ke thread lain, sangat berguna untuk mereproduksi bug race condition dalam test suites.

4. **Di antara struktur data berikut, manakah yang merupakan implementasi bawaan (built-in) Ruby yang sudah thread-safe?**
   * A. `Array`
   * B. `Hash`
   * C. `Thread::Queue`
   * D. `Set`
   * *Jawaban:* **C**. Penjelasan: `Thread::Queue` dan `Thread::SizedQueue` dirancang khusus di layer internal C dengan penguncian mutex bawaan sehingga sepenuhnya thread-safe.

5. **Apa fungsi utama dari method `Thread#join`?**
   * A. Menggabungkan dua variabel stack dari thread yang berbeda.
   * B. Menghentikan sementara Main Thread hingga thread yang dipanggil menyelesaikan eksekusinya.
   * C. Mengunci mutex milik thread lain.
   * D. Memaksa thread berjalan secara paralel murni.
   * *Jawaban:* **B**. Penjelasan: `join` memblokir thread pemanggil sampai target thread selesai dieksekusi atau batas waktu timeout tercapai.

---

### Kategori Intermediate

6. **Mengapa evaluasi kondisi pada `ConditionVariable#wait` wajib dibungkus dalam loop `while condition` dan BUKAN sekadar `if condition`?**
   * A. Karena `ConditionVariable` membutuhkan loop counter untuk membebaskan memory.
   * B. Untuk menangani potensi *Spurious Wakeup* atau situasi di mana status buffer telah dikonsumsi thread lain sesaat setelah sinyal dipancarkan.
   * C. Karena sintaks Ruby tidak mengizinkan `if` di dalam mutex block.
   * D. Agar loop tidak melepaskan mutex.
   * *Jawaban:* **B**. Penjelasan: Thread dapat terbangun tanpa sinyal nyata (spurious wakeup), atau thread lain dapat merebut payload sebelum thread yang baru dibangunkan sempat mengakuisisi kembali mutex. Maka kondisi harus selalu diuji ulang.

7. **Apa konsekuensi dari memanggil kode pemblokir I/O eksternal (misal: `Net::HTTP.get`) di dalam blok `mutex.synchronize` pada server berbeban tinggi?**
   * A. Thread akan langsung memicu error `Errno::EINTR`.
   * B. GVL akan crash.
   * C. Seluruh thread lain yang membutuhkan mutex tersebut akan terhambat selama durasi response network, menurunkan throughput sistem secara drastis (*Lock Contention Bottleneck*).
   * D. Mutex akan melepaskan lock-nya secara otomatis setelah 5 milidetik.
   * *Jawaban:* **C**. Penjelasan: Menahan lock selama operasi eksternal I/O yang lambat menyebabkan thread lain mengantre panjang (*high contention*), menghancurkan concurrency benefits.

8. **Manakah perilaku yang benar terkait GVL CRuby saat sebuah thread melakukan blocking socket write (`syswrite`)?**
   * A. Thread menahan GVL sampai seluruh data terkirim ke kabel fisik.
   * B. CRuby melepaskan GVL sebelum thread masuk ke blocking syscall OS, memungkinkan thread Ruby lain berjalan.
   * C. Ruby VM membagi thread menjadi dua child process sementara.
   * D. Seluruh process Ruby tertidur pulas hingga socket buffer kosong.
   * *Jawaban:* **B**. Penjelasan: Ini adalah esensi keunggulan I/O multi-threading CRuby: GVL dilepaskan saat thread memasuki IO syscall, sehingga IO waiting tidak memblokir eksekusi thread Ruby lainnya.

9. **Apa perbedaan struktural utama antara `Thread` dan `Fiber` di Ruby modern?**
   * A. Fiber dijadwalkan secara pre-emptive oleh OS kernel; Thread dijadwalkan oleh user.
   * B. Thread dijadwalkan secara pre-emptive oleh OS/VM; Fiber dijadwalkan secara kooperatif (manual switching) oleh programmer/scheduler.
   * C. Fiber memiliki stack size 8MB, Thread 4KB.
   * D. Fiber dapat berjalan multi-core parallel di MRI, Thread tidak bisa.
   * *Jawaban:* **B**. Penjelasan: Thread adalah pre-emptive (OS menentukan kapan context switch terjadi), sedangkan Fiber bersifat cooperative (context switch hanya terjadi jika dipanggil via `yield`/`resume` atau fiber scheduler intercept).

10. **Sebuah sistem mendadak memicu exception `ThreadError: deadlock; recursive locking`. Apa penyebab pasti dari error ini?**
    * A. Dua thread mencoba mengunci mutex yang sama dari file fisik yang berbeda.
    * B. Satu thread mencoba memanggil `mutex.lock` pada `Mutex` non-reentrant yang saat itu sudah dimilikinya sendiri.
    * C. Memory sistem operasi habis saat mengalokasikan thread baru.
    * D. Database mengalami deadlock tabel.
    * *Jawaban:* **B**. Penjelasan: Standard `Mutex` di Ruby tidak mengizinkan penguncian berulang (non-reentrant) oleh pemilik yang sama. Melakukannya dianggap sebagai self-deadlock seketika.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Proyek: *Resilient Multi-Threaded Dead-Letter Event Dispatcher*

Bangun sebuah modul Ruby enterprise bernama `ResilientDispatcher` yang memproses ribuan data event secara asinkron dengan spesifikasi ketat:

#### Arsitektur & Spesifikasi Wajib:
1. **Producer-Consumer Pattern:**
   * Main thread memproduksi 1.000 payload event (format: `{ id: Integer, attempts: Integer, payload: String }`).
   * Antrean wajib menggunakan `Thread::SizedQueue` dengan limit buffer maksimal **50 elemen** untuk membatasi konsumsi memory.
2. **Worker Pool:**
   * Menggunakan 8 worker thread native.
   * Setiap worker mengambil event, melakukan pemrosesan simulated I/O latency ($10-50\text{ms}$).
3. **Resilience & Retry Mechanism:**
   * Simulasi kegagalan network acak sebesar $15\%$ pada setiap eksekusi.
   * Jika event gagal diproses, naikkan nilai `attempts`. Jika `attempts < 3`, masukkan kembali event ke antrean pemrosesan dengan backoff delay sederhana.
   * Jika kegagalan telah mencapai `attempts == 3`, kirim payload ke data structure **Dead-Letter Queue (DLQ)** yang aman dari race-condition (`Concurrent Dead-Letter Collector`).
4. **Shutdown Signal Handling:**
   * Terapkan intercept sinyal OS `SIGINT` (`Ctrl+C`):
   * Saat sinyal ditangkap, producer berhenti mengirim data baru.
   * Worker pool diberi waktu timeout maksimal 3 detik untuk mengosongkan sisa buffer antrean (*drain queue*).
   * Cetak audit komprehensif di terminal: Total Diproses, Total Sukses, Total Masuk DLQ, Waktu Total Eksekusi.

#### Target Verifikasi Keberhasilan:
* Tidak ada error memory leak.
* Tidak ada transaksi yang "hilang" (Total Sukses + Total DLQ + Sisa antrean saat force-kill = 1.000).
* Eksekusi 1.000 item selesai dalam $< 5\text{ detik}$ (membuktikan efektivitas concurrency dibanding single-thread yang butuh $\sim 30\text{ detik}$).