# Bab 09: Konkurensi Modern & Pemrograman Paralel
## Module 01: Ruby Ractors: Eksekusi Paralel Murni & Model Aktor pada Ruby 3+

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer mampu:
- Menganalisis batasan *Global VM Lock* (GVL/GIL) pada CRuby (MRI) dan merancang arsitektur konkurensi yang melampauinya.
- Mengimplementasikan isolasi memori thread-safe menggunakan primitif `Ractor` (Ruby's Actor-like concurrent abstraction).
- Mengelola transfer state antar-Ractor menggunakan mekanisme *Copy*, *Move Semantics*, dan *Shareable Objects*.
- Mengidentifikasi serta mencegah race condition, deadlocks, dan kebocoran memori saat mendistribusikan beban komputasi CPU-bound lintas core prosesor pada lingkungan produksi Ruby.

---

### 2. Prerequisite
- Pemahaman mendalam tentang siklus hidup proses (*OS Process*), *Thread*, dan *Fiber*.
- Pemahaman dasar arsitektur CRuby internals: *Global VM Lock* (GVL) dan alokasi memori heap Ruby (`VALUE`, `RBasic`, `RObject`).
- Penguasaan konsep *mutability* Ruby (`#freeze`, duplikasi objek, dan reference passing).

---

### 3. Concept
Secara historis, implementasi CRuby standar menggunakan *Global VM Lock* (GVL) untuk memproteksi struktur internal runtime dari korupsi data akibat akses simultan oleh banyak OS native threads. Konsekuensinya, meskipun CRuby menggunakan native threads tingkat kernel, hanya **satu thread yang dapat mengeksekusi instruksi YARV bytecode pada satu waktu**. Ini membuat multi-threading standar di Ruby hanya efektif untuk *I/O-bound operations*, tetapi tidak mampu memberikan akselerasi komputasi *CPU-bound* pada arsitektur multi-core.

Diperkenalkan secara resmi pada Ruby 3.0, **Ractor** (singkatan dari *Ruby Actor*) adalah model konkurensi berbasis *Actor Model* yang dirancang untuk menyediakan **eksekusi paralel murni (true multi-core parallelism) di dalam satu OS process** tanpa terkendala oleh GVL global tunggal. 

Arsitektur Ractor beroperasi dengan membagi eksekusi menjadi beberapa unit independen yang masing-masing memiliki:
1. **GVL Terisolasi**: Setiap Ractor memiliki GVL-nya sendiri. Dua atau lebih Ractor dapat mengeksekusi bytecode Ruby secara paralel pada core CPU yang berbeda secara bersamaan.
2. **Ruang Objek Terisolasi (Shared-Nothing Memory Architecture)**: Secara default, Ractor tidak berbagi objek memori biasa. Komunikasi antar-Ractor dilakukan secara asinkron atau sinkron melalui pertukaran pesan (*message passing*).
3. **Objek yang Dapat Dibagi (Shareable Objects)**: Ruby membagi tipe data menjadi:
   - *Non-shareable*: Objek mutable standar (e.g., `String`, `Array`, `Hash`). Objek ini tidak boleh diakses oleh lebih dari satu Ractor sekaligus untuk mencegah data race.
   - *Shareable*: Objek yang dijamin thread-safe secara intrinsik, seperti objek numerik (`Integer`, `Float`), simbol (`Symbol`), objek boolean (`true`, `false`, `nil`), kelas dan modul (`Class`, `Module`), serta objek kompleks apa pun yang telah dibekukan secara mendalam (*deeply frozen*) via `Ractor.make_shareable`.

---

### 4. Why
Sebelum Ruby 3+, alternatif untuk eksekusi paralel CPU-bound di Ruby adalah:
1. **Multi-processing (Forking)**: Menggunakan `Process.fork`.
   - *Urgensi*: Memakan konsumsi memori tinggi (*Copy-on-Write fragmentation*) dan overhead context-switch level kernel yang berat. Komunikasi antar-proses (IPC via UNIX sockets/pipes) memerlukan serialisasi/deserialisasi (seperti Marshal/JSON) yang lambat.
2. **Background Job Engines (e.g., Sidekiq, Resque)**:
   - *Urgensi*: Menambah dependensi infrastruktur eksternal (Redis/PostgreSQL) dan latency jaringan yang masif hanya untuk memparalelkan kalkulasi CPU lokal.

Ractor menyelesaikan masalah ini pada tingkat runtime:
- **Zero-Serialization Overhead**: Objek shareable dapat dibaca langsung oleh jutaan Ractor tanpa alokasi memori tambahan.
- **Hardware Saturation**: Memanfaatkan 100% kapasitas seluruh core CPU dari satu proses tanpa dependensi external worker.
- **Safety by Design**: Mencegah bug *data race* secara deterministik pada tingkat compiler/interpreter; runtime akan melempar `Ractor::IsolationError` jika kode mencoba mengakses mutable state lintas batas Ractor.

---

### 5. What
Komponen utama dalam ekosistem Ractor:

| Komponen | Definisi & Fungsi |
| :--- | :--- |
| `Ractor.new { ... }` | Instansiasi unit eksekusi paralel baru. Menerima blok kode yang akan dieksekusi secara independen. |
| `Ractor#send(msg)` & `Ractor.receive` | Mekanisme Push-type communication: Mengirim pesan ke mailbox Ractor tujuan (non-blocking) dan membacanya (blocking). |
| `Ractor.yield(msg)` & `Ractor#take` | Mekanisme Pull-type communication: Ractor pekerja memancarkan hasil ke consumer yang memanggil `#take`. |
| `Ractor.select(*ractors)` | Menunggu pesan pertama yang tersedia dari sekumpulan Ractor (mirip `select(2)` pada socket programming). |
| `Ractor.shareable?(obj)` | Metode introspeksi boolean untuk memvalidasi apakah suatu objek aman dibagikan antar-Ractor. |
| `Ractor.make_shareable(obj)` | Melakukan pembekuan rekursif (*deep freeze*) terhadap struktur data agar menjadi *shareable*. |
| `move: true` modifier | Flag transfer kepemilikan memori: Memindahkan referensi objek dari Ractor asal ke Ractor tujuan tanpa menyalin, membatalkan (*invalidating*) akses pada Ractor asal. |

---

### 6. How
Alur transfer data antar-Ractor:

```
[Ractor Pengirim (Ractor A)]
             │
      Objek: obj
             │
      Apakah 'obj' Shareable?
      ├── YES ──> [Zero-Copy Reference Transfer] ───────────────┐
      │                                                        │
      └── NO ───> Opsi Pengiriman:                             │
                     ├── Default (Copy):                        │
                     │     └── Deep Copy via Marshal/Internal   │
                     │         (Alokasi memori baru di B)       │
                     │                                         ▼
                     └── move: true: ────────────> [Ractor Penerima (Ractor B)]
                           └── Reference Displaced    Akses langsung ke objek
                               (obj di Ractor A        (Ractor A crash jika
                                menjadi inaccessible)   mencoba akses)
```

Proses komunikasi:
1. **Push Model**: Ractor A memanggil `target_ractor.send(payload)`. Payload masuk ke antrean *incoming port* (mailbox) milik `target_ractor`. `target_ractor` membaca antrean via `Ractor.receive`.
2. **Pull Model**: Ractor B menghitung data, lalu memanggil `Ractor.yield(result)`. Pemanggil (biasanya Ractor Main) memanggil `b.take` untuk menarik hasil komputasi tersebut secara sinkron.

---

### 7. Analogy
Bayangkan sebuah kantor arsitektur:
- **Model Threading Lama**: 8 arsitek (Threads) bekerja di satu ruangan sempit mengelilingi 1 papan gambar fisik yang sama (Shared Memory). Hanya 1 arsitek yang boleh memegang pensil pada satu waktu (GVL). Meskipun ada 8 orang, kecepatan menggambar tidak bertambah 8x lipat.
- **Model Forking (Multi-process)**: Anda menyewa 8 ruko terpisah yang identik (Processes). Biaya sewa (RAM) melonjak 8x lipat. Jika arsitek 1 ingin mengirim sketsa ke arsitek 2, mereka harus membungkusnya dalam paket pos dan mengirimkannya melalui kurir (IPC/Serialization).
- **Model Ractor**: 8 arsitek bekerja di meja kerja masing-masing yang terisolasi di dalam satu gedung besar (Satu OS Process). Masing-masing memiliki pensil sendiri dan menggambar serentak (Parallel execution tanpa GVL bottleneck). Jika ingin berbagi materi:
  - Mereka dapat memfotokopi dokumen (*Copy*).
  - Menyerahkan dokumen asli sepenuhnya sehingga pengirim tidak memilikinya lagi (*Move semantics*).
  - Atau merujuk ke buku standar arsitektur nasional berlaminasi kaca yang tidak bisa diubah oleh siapapun (*Shareable / Deep-Frozen Objects*).

---

### 8. Diagram

```
+-----------------------------------------------------------------------------------+
| OS PROCESS (Single PID)                                                           |
|                                                                                   |
|  +-----------------------------+                 +-----------------------------+  |
|  | Ractor 1 (Main)             |                 | Ractor 2 (Worker)           |  |
|  | [Core 0]                    |                 | [Core 1]                    |  |
|  | - Dedicated GVL             |                 | - Dedicated GVL             |  |
|  | - Local Memory Heap         |                 | - Local Memory Heap         |  |
|  |                             |                 |                             |  |
|  |   +---------------------+   |                 |   +---------------------+   |  |
|  |   | Thread 1A | Thread 1B |  |                 |   | Thread 2A           |   |  |
|  |   +---------------------+   |                 |   +---------------------+   |  |
|  +--------------+--------------+                 +--------------^--------------+  |
|                 |                                               |                 |
|                 | Ractor.send(data, move: true)                 |                 |
|                 +-----------------------------------------------+                 |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  | SHARED GLOBAL HEAP (Zero-Lock Read Access)                                  |  |
|  |                                                                             |  |
|  |  - Deep-frozen Objects (Ractor.make_shareable)                              |  |
|  |  - Symbols, Numeric Classes, Frozen Strings                                 |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

### 9. Simple Example

```ruby
# Validasi eksekusi paralel murni via Ractors
require 'benchmark'

def cpu_intensive_work(n)
  10_000_000.times.reduce(0) { |acc, i| acc + (i ^ n) }
end

time = Benchmark.realtime do
  # Membuat 4 Ractor pekerja
  workers = 4.times.map do |id|
    Ractor.new(id) do |worker_id|
      # Ractor mengeksekusi komputasi independen di core terpisah
      cpu_intensive_work(worker_id)
    end
  end

  # Menarik (take) hasil dari seluruh Ractor secara sinkron
  results = workers.map(&:take)
  puts "Kalkulasi selesai. Total sample: #{results.size}"
end

puts "Durasi Eksekusi: #{time.round(2)} detik"
```

---

### 10. Practical Example
Pipeline pemrosesan dan verifikasi integritas batch data berukuran besar menggunakan pola *Worker Pool* berbasis Ractor.

```ruby
# frozen_string_literal: true
require 'digest'
require 'securerandom'

module BatchProcessor
  class IntegrityWorkerPool
    def initialize(size:)
      @size = size
      @workers = []
      @pool_pipe = Ractor.new do
        loop do
          # Ractor penghubung: menerima tugas lalu meneruskannya ke worker yang siap
          task = Ractor.receive
          Ractor.yield(task)
        end
      end
      
      init_workers
    end

    def process(batches)
      # Memasukkan seluruh pekerjaan ke message pipeline
      feeder = Thread.new do
        batches.each do |batch|
          # Objek dijadikan shareable sebelum dikirimkan ke worker
          shareable_batch = Ractor.make_shareable(batch)
          @pool_pipe.send(shareable_batch)
        end
      end

      results = []
      batches.size.times do
        # Mengambil hasil dari worker mana pun yang pertama selesai
        completed_task = Ractor.select(*@workers)
        # Ractor.select mengembalikan tuple: [ractor_instance, yielded_value]
        results << completed_task[1]
      end

      feeder.join
      results
    end

    private

    def init_workers
      @workers = @size.times.map do |idx|
        Ractor.new(@pool_pipe, idx) do |pipe, worker_id|
          loop do
            # Worker menarik task dari pipeline secara konkuren
            payload = pipe.take
            
            # Simulasi algoritma CPU-bound (hashing bertingkat)
            computed_hash = payload[:data].reduce(payload[:salt]) do |acc, chunk|
              Digest::SHA256.hexdigest("#{acc}:#{chunk}")
            end

            # Mengirim kembali hasil komputasi
            Ractor.yield({
              batch_id: payload[:batch_id],
              worker_id: worker_id,
              result_hash: computed_hash,
              status: :ok
            })
          end
        end
      end
    end
  end
end

# === Simulasi Beban Kerja Produksi ===
raw_batches = Array.new(16) do |i|
  {
    batch_id: "BATCH-#{i + 1}",
    salt: SecureRandom.hex(16),
    data: Array.new(20_000) { SecureRandom.alphanumeric(32) }
  }
end

puts "Memulai pemrosesan 16 batch pada thread pool Ractor..."
start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)

pool = BatchProcessor::IntegrityWorkerPool.new(size: 4)
processed_results = pool.process(raw_batches)

duration = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time
puts "Selesai memproses #{processed_results.size} batch dalam #{duration.round(3)} detik."
puts "Sample output: #{processed_results.first}"
```

---

### 11. Real World Example
**Skenario: Pipeline Telemetri dan Audit Fraud Skala Besar (Fintech)**

Sebuah payment gateway memproses ribuan data transaksi per detik. Setiap batch transaksi membutuhkan:
1. Validasi struktur JSON data payload.
2. Kalkulasi *checksum* kriptografis berlapis (HMAC-SHA512).
3. Evaluasi aturan fraud engine berbasis pola regex kompleks terhadap histori string transaksi.

```
[Ingress API Router] (Puma Threads / I/O-bound)
         │
         │ Batch of 50,000 tx/sec
         ▼
[Ingestion Buffer]
         │
         │ Ractor.make_shareable(batch) (Zero overhead memory freeze)
         ▼
+--------------------------------------------------------------+
| Ractor Core Engine Pool (4 - 32 Cores Saturated)             |
|                                                              |
| [Ractor Worker 01] ──> Decrypt & Calculate HMAC               |
| [Ractor Worker 02] ──> Signature Verification                |
| [Ractor Worker 03] ──> Dynamic Regex Engine Scoring          |
| [Ractor Worker ..] ──> Anomaly Vector Evaluation             |
+--------------------------------------------------------------+
         │
         │ Ractor.yield(eval_result)
         ▼
[Storage Aggregator] ──> PostgreSQL / Kafka Sink
```

Sebelum migrasi ke Ractor, arsitektur lama menggunakan klaster worker multi-proses (16 proses background). Masalah muncul:
- Memory footprint mencapai **12 GB** karena fragmentasi Copy-on-Write (CoW) Ruby saat memuat data cache referensi fraud rules.
- Latensi serialisasi antar-proses via Redis queue memakan waktu rata-rata **45ms**.

**Penerapan Solusi Ractor**:
Aturan referensi fraud dibekukan ke memori bersama via `Ractor.make_shareable(RULES_ENGINE_STATE)`. Worker Ractor memvalidasi ribuan transaksi secara paralel murni di dalam proses yang sama. 
- **Hasil**: Memory footprint turun dari **12 GB menjadi 1.4 GB** (efisiensi 88%). 
- Serialization latency tereliminasi ke **0ms** (akses langsung referensi memori shareable), memangkas *p99 latency* transaksi dari **120ms ke 18ms**.

---

### 12. Trade-offs

| Aspek | Ractor (Model Aktor) | Multi-threading Klasik (`Thread`) | Multi-processing (`Process.fork`) |
| :--- | :--- | :--- | :--- |
| **Eksekusi Paralel CPU** | **Murni (Multi-core)** | Tidak (Terbatas oleh 1 GVL) | **Murni (Multi-core)** |
| **Overhead Memori** | **Rendah** (Shared heap untuk immutable objects) | **Sangat Rendah** (Satu memori heap) | **Tinggi** (Duplikasi virtual memory & CoW degradation) |
| **Keamanan Data Race** | **Tinggi** (Dijamin oleh compiler/runtime) | **Rendah** (Rawan race condition/deadlock) | **Tinggi** (Ruang memori OS terisolasi total) |
| **Overhead Komunikasi** | **Nol s/d Rendah** (Zero-copy untuk shareables) | **Nol** (Akses memori instan tanpa isolasi) | **Tinggi** (Serialisasi IPC: Socket/Pipes) |
| **Kompatibilitas Ekosistem** | **Rendah** (Banyak Gem belum Ractor-safe) | **Tinggi** (Didukung mayoritas Gem ekosistem) | **Sangat Tinggi** (Arsitektur standar Unix) |

---

### 13. When To Use
- **CPU-Bound Pipelines**: Komputasi algoritma intensif, kriptografi, image/video manipulation, transformasi dataset besar, dan kompresi data.
- **Isolasi Mutasi Ketat**: Sistem yang membutuhkan jaminan bahwa komponen worker tidak akan merusak status memori internal komponen lain tanpa sengaja.
- **Sistem Memory-Constrained**: Lingkungan kontainer (seperti Kubernetes pod dengan limit memory ketat) yang ingin memanfaatkan multi-core tanpa overhead menduplikasi ratusan megabyte RAM seperti pada `Process.fork`.

---

### 14. When NOT To Use
- **Aplikasi Web Rails Monolitik Tradisional**: Framework Rails dan mayoritas ekosistem gem gem ActiveRecord memiliki ratusan status mutable global yang belum Ractor-safe.
- **I/O-Bound Workloads Murni**: Untuk aplikasi yang menghabiskan 95% waktunya menunggu respons jaringan (HTTP API calls, database query), gunakan **Fibers (Async gem)** atau standard **Threads**. Overhead context-switching Ractor tidak memberikan keuntungan performa untuk I/O murni.
- **Kebutuhan Berbagi Objek Kompleks yang Mutable**: Jika arsitektur aplikasi bergantung pada database cache in-memory yang sering dimutasi secara konkuren, struktur shared-nothing Ractor akan memicu bottleneck akibat overhead kloning objek.

---

### 15. Common Mistakes

#### 1. Mengakses Konstanta atau Variabel Mutable Global di Luar Scope
```ruby
# SALAH: Memicu Ractor::IsolationError
CONFIG = { timeout: 30 } # Hash mutable secara default

r = Ractor.new do
  puts CONFIG[:timeout] # Error: can not access non-shareable objects by constants
end
r.take
```
*Solusi*:
```ruby
# BENAR: Bekukan objek secara mendalam sebelum diakses
CONFIG = Ractor.make_shareable({ timeout: 30 })

r = Ractor.new do
  puts CONFIG[:timeout] # Aman: Objek shareable
end
r.take
```

#### 2. Mengakses Objek Asal Setelah Melakukan `move: true`
```ruby
# SALAH
data = "buffer data rahasia".dup
r = Ractor.new do
  msg = Ractor.receive
  msg.upcase!
end

r.send(data, move: true)
puts data # Memicu Ractor::MovedError: can not send any methods to a moved object
```
*Solusi*: Pastikan kepemilikan objek diserahkan seutuhnya dan referensi lokal dihentikan penggunaannya.

#### 3. Mengasumsikan Instance Variable Class Aman Diakses di Ractor
```ruby
# SALAH
class Service
  def initialize
    @state = "initial"
  end

  def execute_parallel
    Ractor.new do
      puts @state # Error: can not access instance variables of other Ractors
    end.take
  end
end
Service.new.execute_parallel
```
*Solusi*: Kirim state yang dibutuhkan melalui argumen parameter `Ractor.new(arg)`.

---

### 16. Best Practices (Production Checklist)
- [ ] **Validasi Kemurnian Shareable**: Selalu uji struktur data referensi global menggunakan `Ractor.shareable?(DATA)` sebelum proses *boot* aplikasi.
- [ ] **Terapkan `#freeze` Rekursif**: Gunakan `Ractor.make_shareable(OBJECT)` untuk seluruh kamus lookup, metadata, dan konfigurasi saat inisialisasi modul.
- [ ] **Batasi Jumlah Ractor Berdasarkan Core Fisik**: Jangan membuat Ractor tak terbatas. Tetapkan batas atas pool sesuai core mesin: `Etc.nprocessors`.
- [ ] **Hindari Alokasi Memori di Loop Komunikasi**: Kirim referensi data shareable atau gunakan *move semantics* untuk meminimalkan beban kerja Garbage Collector antar-Ractor.
- [ ] **Tangani Error Boundary**: Bungkus isi blok Ractor dengan standard exception handling. Uncaught exception di dalam Ractor akan di-*re-raise* sebagai `Ractor::RemoteError` saat `#take` dipanggil.

---

### 17. Troubleshooting

#### Kasus 1: `Ractor::IsolationError` saat Menjalankan Library Eksternal
- **Indikasi**: Stacktrace menunjukkan kegagalan akses class variable (`@@var`), constant mutable, atau method definisi dinamis.
- **Penyebab**: Library tersebut dirancang sebelum Ruby 3.0 dan mengandalkan shared global state.
- **Mitigasi**: Isolasi eksekusi library ke dalam satu Ractor terdedikasi (Actor Singleton), atau bungkus library tersebut di level antrean *OS process* terpisah.

#### Kasus 2: Deadlock Antar-Ractor Menggunakan Metode Push/Pull Campuran
- **Indikasi**: Semua thread CPU idle, proses menggantung tanpa terminasi.
- **Penyebab**: Ractor A menunggu `Ractor.receive` dari Ractor B, sementara Ractor B menunggu `A.take` sebelum mengirim data.
- **Mitigasi**: Standarisasi arah komunikasi: gunakan topologi satu arah (*unidirectional pipeline*) atau gunakan mekanisme `Ractor.select` dengan timeout guard.

```ruby
# Pola penanganan timeout Ractor.select
def take_with_timeout(ractor, timeout_sec)
  timer = Ractor.new(timeout_sec) do |sec|
    sleep sec
    :timeout
  end

  selected_ractor, value = Ractor.select(ractor, timer)
  raise Timeout::Error, "Ractor operation timed out" if value == :timeout

  value
end
```

---

### 18. Exercise
Implementasikan sebuah fungsi bernama `parallel_prime_sum(ranges)`:
- Menerima sebuah Array berisi Range angka (contoh: `[1..500_000, 500_001..1_000_000]`).
- Memproses penemuan bilangan prima dan menjumlahkannya secara paralel murni memanfaatkan 1 Ractor per range yang diberikan.
- Fungsi harus mengembalikan total akumulasi penjumlahan dari seluruh range tersebut.
- Pastikan tidak ada data race dan exception ditangani dengan benar.

---

### 19. Challenge
Bangun sebuah class **`RactorMapReduce`**:
1. Mengambil dataset masukan berupa array string teks acak (minimal 500,000 string).
2. Memiliki metode `#map` yang mendistribusikan tokenisasi pemecahan kata ke dalam sejumlah $N$ Ractors ($N =$ jumlah core CPU mesin).
3. Memiliki tahap penghubung (*Shuffle*) yang mengelompokkan kata yang sama tanpa menggunakan variabel global mutable.
4. Memiliki metode `#reduce` berbasis Ractor yang mengakumulasi total frekuensi kemunculan tiap kata secara paralel.
5. **Batasan**: Penggunaan RAM tidak boleh bertambah lebih dari 1.5x ukuran dataset asal (Gunakan *Move Semantics* untuk efisiensi memori mutlak).

---

### 20. Summary
- **Ruby Ractor** membawa paradigma konkurensi baru ke CRuby dengan menghadirkan eksekusi multi-core paralel murni bebas dari batasan satu GVL global.
- Arsitektur **Shared-Nothing** Ractor memisahkan ruang memori secara ketat, mengeliminasi bug data-race yang sering terjadi pada multi-threading tradisional.
- Data dapat dikirim antar-Ractor melalui tiga cara: **Deep Copy** (aman tapi ada alokasi overhead), **Move Semantics** (cepat dengan transfer kepemilikan), dan **Shareable Objects** (zero-copy untuk objek immutable).
- Ractor sangat unggul untuk komputasi CPU-bound dan pemrosesan data volume tinggi, namun harus diintegrasikan secara hati-hati pada codebase lama mengingat dependensi ekosistem Ruby yang belum seluruhnya Ractor-safe.