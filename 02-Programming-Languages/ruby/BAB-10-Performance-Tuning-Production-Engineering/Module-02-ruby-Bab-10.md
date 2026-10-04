# BAB 10: Performance Tuning & Production Engineering
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Internal Runtime CRuby**: Membedah mekanisme Garbage Collection (Generational RGenGC, Compacting GC), alokasi memori heap CRuby, serta optimasi Object Shapes (Ruby 3.2+).
2. **Mengoptimalkan Memory Footprint**: Mengeliminasi fragmentasi memori dan memory bloat menggunakan *custom memory allocator* (`jemalloc`) serta melacak alokasi via `ObjectSpace` dan `derailed_benchmarks`.
3. **Mengeksploitasi YJIT (Yet Another Ruby JIT)**: Mengonfigurasi, melakukan profiling kompilasi, dan menganalisis metrik runtime YJIT untuk beban kerja throughput tinggi secara efisien.
4. **Mendesain Arsitektur Server Web Kinerja Tinggi**: Mengonfigurasi cluster web server enterprise (Puma vs Pitchfork vs Falcon) dengan preservasi Copy-on-Write (CoW) maksimal.
5. **Menerapkan Continuous Profiling & Observability**: Mengintegrasikan profiling berbasis sampling tingkat produksi (`stackprof`, `vernier`) tanpa memicu degradasi latensi P99.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
- Arsitektur konkurensi Ruby dasar: Global VM Lock (GVL), Thread, Fiber, dan Process model.
- Konsep dasar UNIX/Linux: Virtual Memory, Resident Set Size (RSS), Page Faults, Signals (`SIGTERM`, `SIGTTIN`), dan Socket I/O multiplexing (`epoll`).
- Penggunaan dasar Rack interface dan server HTTP (Puma/Unicorn).
- Metrik sistem dasar: Latency (P50, P95, P99), Throughput (RPS/RPM), CPU Saturation, dan System Calls (`strace`).

---

### 3. Concept & Internal Architecture

#### A. CRuby Memory Management & Heap Structure
CRuby mengelola memori menggunakan struktur fixed-size slot yang disebut `RVALUE` (berukuran 40 byte pada arsitektur 64-bit). Kumpulan 40-byte slot ini ditampung dalam **Heap Page** (berukuran sekitar 16 KB per page pada sistem operasi standar).

```
+-------------------------------------------------------------------+
|                         OS Virtual Memory                         |
+-------------------------------------------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                        CRuby Heap Space                           |
|  +--------------------+  +--------------------+  +--------------+ |
|  |     Heap Page 1    |  |     Heap Page 2    |  | Heap Page N  | |
|  | (approx. 16KB)     |  | (approx. 16KB)     |  |              | |
|  | +----------------+ |  | +----------------+ |  |              | |
|  | | RVALUE (40B)   | |  | | RVALUE (40B)   | |  |              | |
|  | | RVALUE (40B)   | |  | | RVALUE (40B)   | |  |              | |
|  | | [Embedded Str] | |  | | [Object Slot]  | |  |              | |
|  | +----------------+ |  | +----------------+ |  |              | |
|  +--------------------+  +--------------------+  +--------------+ |
+-------------------------------------------------------------------+
         | (Jika objek > 24-40 bytes, alokasi via malloc)
         v
+-------------------------------------------------------------------+
|                    System Heap (glibc / jemalloc)                 |
|  [Raw Buffers, Large Strings, Arrays, Hashes capacity dynamic]     |
+-------------------------------------------------------------------+
```

- **Slot Embedding**: Objek kecil (seperti string $\le$ 23 bytes) disimpan langsung di dalam `RVALUE` (*embedded object*).
- **External Malloc**: Objek yang ukurannya melebihi kapasitas `RVALUE` akan mengalokasikan memori tambahan di system heap melalui `malloc()`.
- **Generational RGenGC**: Membagi objek menjadi *Young Generation* (objek sementara, dibersihkan lewat Minor GC berlatensi rendah) dan *Old Generation* (objek yang bertahan setelah beberapa siklus sweep, dipromosikan dan hanya dicek pada Major GC).
- **Compacting GC (`GC.compact`)**: Menata ulang slot yang tersebar untuk mengonsolidasikan heap pages yang kosong kembali ke OS, meminimalisir fragmentasi internal, dan memaksimalkan efisiensi CoW.

#### B. YJIT (Yet Another Ruby JIT) Internals
YJIT menerapkan teknik **Lazy Basic Block Versioning (LBBV)**:
1. Kode Ruby dikonversi ke YARV bytecode terlebih dahulu.
2. YJIT tidak langsung mengompilasi seluruh method/file menjadi *machine code*. Kompilasi dilakukan per *Basic Block* saat eksekusi mencapai jalur tersebut (*cold code* tidak pernah dikompilasi).
3. Berdasarkan tipe runtime aktual (misal: variabel bertipe `Integer` vs `String`), YJIT menghasilkan kode mesin x86-64 atau ARM64 yang terspesialisasi secara spesifik.
4. Jika tipe data berubah di tengah eksekusi, runtime melakukan **Deoptimization (Bailout)** dan kembali ke interpreter YARV standar.

#### C. Memory Allocators: Glibc PTMalloc vs. Jemalloc
- **Glibc `ptmalloc`**: Mengalokasikan memory arena independen untuk setiap thread demi mengurangi lock contention. Dampak negatifnya pada Ruby multi-threaded: penggunaan virtual memory membengkak secara masif dan alokasi chunk yang terfragmentasi jarang dilepaskan kembali ke OS kernel via `brk`/`madvise`.
- **`jemalloc`**: Membagi alokasi berdasarkan bins/size classes yang terstruktur ketat, menggunakan metadata tracking yang presisi, dan secara aktif melakukan *purging* dirty pages (`MADV_DONTNEED`) kembali ke kernel Linux. Hal ini menurunkan memory bloat pada aplikasi Ruby produksi sebesar 20% hingga 40%.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan Production Engineering Enterprise |
| :--- | :--- | :--- |
| **Memory Allocator** | Standard OS `glibc malloc` | `jemalloc` dikompilasi dengan parameter *background threads* |
| **GC Strategy** | Menyerahkan sepenuhnya ke default CRuby GC | Penyesuaian `RUBY_GC_*`, manual compaction sebelum *fork*, OOM-protection |
| **JIT Compiler** | Dimatikan atau JIT eksperimental (`MJIT`) | YJIT diaktifkan dengan alokasi *exec_mem_size* terukur (Ruby 3.2+) |
| **Web Server** | Puma threading murni tanpa worker tuning | Puma Worker Preload / Pitchfork dengan preservasi Copy-on-Write (CoW) |
| **Profiling** | Log APM pasif (Datadog/NewRelic agent saja) | Profiling On-Demand / Continuous Profiling via `Vernier` / `Stackprof` |

#### Mengapa Rekayasa Tingkat Rendah Ini Dibutuhkan?
Ruby secara historis dipandang lambat dan boros memori. Pada kenyataannya, sebagian besar kegagalan performa di lingkungan produksi skala besar bersumber dari:
1. **Memory Fragmentation**: Alokasi array dinamis dan string mutabel yang masif memblokir OS untuk mereklamasi memori fisik.
2. **CoW Invalidation**: Penggunaan master-worker cluster yang menulis ulang objek di memory space worker, membatalkan halaman Copy-on-Write dan melipatgandakan penggunaan RSS.
3. **GVL Contention**: Server Puma multi-thread yang mengonsumsi CPU berlebih pada pekerjaan komputasi (*CPU-bound*), mengakibatkan thread kelaparan (*thread starvation*).

---

### 5. How (Workflow Profiling & Tuning)

Langkah terstruktur rekayasa performa dari diagnosis hingga verifikasi produksi:

```
[1. Baseline & Observability]
     |--> Pasang continuous profiling / Stackprof sampling pada staging/canary.
     |--> Monitor metrik: Latency P99, Memory RSS, Thread saturation, GC Duration.
     v
[2. Allocator & OS Isolation]
     |--> Bind runtime ke libjemalloc.so via LD_PRELOAD.
     |--> Verifikasi status: malloc_stats_print().
     v
[3. Code-Level Allocations Elimination]
     |--> Identifikasi Hotspot alokasi via `memory_profiler`.
     |--> Terapkan Object Reuse, frozen string literals, dan in-place mutation.
     v
[4. Architecture Tuning (CoW & Clustering)]
     |--> Konfigurasi Web Server: Preload app, GC compaction sebelum fork.
     |--> Evaluasi Pitchfork vs Puma cluster worker tuning.
     v
[5. JIT Optimization (YJIT Engine)]
     |--> Aktifkan `--yjit` dan parameter `--yjit-exec-mem-size`.
     |--> Analisis metrik deoptimization (Bailout rates).
     v
[6. Verifikasi & Penetration Testing]
     |--> Load testing via k6 / wrk. Validasi eliminasi GC-pause spikes.
```

---

### 6. Analogy & Diagram ASCII

#### A. Copy-on-Write (CoW) Degradation
Ketika worker di-fork dari master process, keduanya berbagi physical memory pages yang sama secara read-only. Segera setelah worker memodifikasi objek di memori, OS mengalokasikan physical page baru (*dirty page*).

```
SEBELUM MODIFIKASI (CoW Optimal):
Physical RAM:     [ Page 1 (App Code) ]  [ Page 2 (Constants) ]  [ Page 3 (Heap Data) ]
                           ^                        ^                       ^
                           | Shared                 | Shared                | Shared
Master Process:  [ Virtual Page A ]       [ Virtual Page B ]      [ Virtual Page C ]
Worker Process:  [ Virtual Page A ]       [ Virtual Page B ]      [ Virtual Page C ]

SETELAH LAZY INVOCATION / UNCOMPACTED GC RUN (CoW Broken):
Physical RAM:     [ Page 1 (App Code) ]  [ Page 2 (Constants) ]  [ Page 3 (Heap-Master) ] [ Page 4 (Heap-Worker DIRTY) ]
                           ^                        ^                       ^                       ^
Master Process:  [ Virtual Page A ]       [ Virtual Page B ]      [ Virtual Page C ]               |
Worker Process:  [ Virtual Page A ]       [ Virtual Page B ] ---------------------------------------+
(RSS Worker meningkat secara drastis karena OS menduplikasi halaman memori)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: YJIT Metrics Inspection & Allocation Tracing
Skrip berikut mengukur efektivitas kompilasi YJIT dan alokasi objek secara langsung dari Ruby runtime:

```ruby
# benchmark_yjit.rb
# Jalankan dengan: ruby --yjit benchmark_yjit.rb

require 'objspace'

# 1. Pastikan YJIT aktif
unless defined?(RubyVM::YJIT) && RubyVM::YJIT.enabled?
  abort("Harap jalankan skrip dengan flag --yjit")
end

def computationally_heavy_task(iterations)
  acc = 0
  iterations.times do |i|
    acc += (i % 2 == 0 ? (i * 2) : (i * 3))
  end
  acc
end

# Pemanasan (Warmup) untuk memicu kompilasi LBBV YJIT
puts "Menjalankan Warmup..."
5.times { computationally_heavy_task(100_000) }

# Ukur metrik YJIT
stats_before = RubyVM::YJIT.runtime_stats
alloc_before = ObjectSpace.each_object.count

t0 = Process.clock_gettime(Process::CLOCK_MONOTONIC)
computationally_heavy_task(1_000_000)
t1 = Process.clock_gettime(Process::CLOCK_MONOTONIC)

stats_after = RubyVM::YJIT.runtime_stats
alloc_after = ObjectSpace.each_object.count

puts format("Durasi Eksekusi       : %.4f ms", (t1 - t0) * 1000)
puts format("Total Objek Teralokasi: %d", (alloc_after - alloc_before))
puts format("YJIT Compiled Blocks  : %d", stats_after[:compiled_block_count] - stats_before[:compiled_block_count])
puts format("YJIT Bailout / Inval  : %d", stats_after[:invalidation_count] - stats_before[:invalidation_count])
```

#### B. Practical Example: Enterprise Puma Configuration with CoW Preserving, Compaction, and Jemalloc Dynamic Inspection

Konfigurasi server HTTP production-grade (`config/puma.rb`) yang menerapkan *pre-fork architecture*, isolasi jemalloc, serta mitigasi memory leak terkendali.

```ruby
# config/puma.rb
# Puma Production Configuration

# Definisikan environment dan resources
threads_count = Integer(ENV.fetch('RAILS_MAX_THREADS', 5))
workers_count = Integer(ENV.fetch('WEB_CONCURRENCY', 4))

threads threads_count, threads_count
workers workers_count

# Bind port
port ENV.fetch('PORT', 3000)
environment ENV.fetch('RAILS_ENV', 'production')

# Preload application code untuk efisiensi Copy-on-Write
preload_app!

# Hook: Sebelum proses master melakukan fork ke worker
before_fork do
  # 1. Disconnect database connections untuk mencegah shared file descriptors
  if defined?(ActiveRecord::Base)
    ActiveRecord::Base.connection_pool.disconnect!
  end

  # 2. Tutup Redis connections jika menggunakan connection pool
  $redis_pool&.shutdown(&:close) if defined?($redis_pool)

  # 3. Compact heap untuk merapatkan slot memori dan memaksimalkan CoW
  # Dijalankan 2-3 kali untuk memindahkan objek Old-Gen ke halaman terkonsolidasi
  if GC.respond_to?(:compact)
    3.times { GC.start }
    GC.compact
    puts "[Puma Master] Garbage Collection compacted successfully."
  end
end

# Hook: Setelah worker berhasil di-fork oleh master process
on_worker_boot do |_worker_index|
  # 1. Re-establish Database Connection
  if defined?(ActiveRecord::Base)
    ActiveRecord::Base.establish_connection
  end

  # 2. Validasi jemalloc terpasang via LD_PRELOAD
  begin
    require 'fiddle'
    handle = Fiddle.dlopen(nil)
    malloc_conf = handle['mallctl']
    puts "[Puma Worker #{_worker_index}] Verified: jemalloc active via libc symbols."
  rescue StandardError
    warn "[Puma Worker #{_worker_index}] WARNING: jemalloc NOT detected. Operating on system malloc."
  end
end

# Lifecycle & Leak mitigation
worker_timeout 60

# Optional: Integrasi Puma Worker Killer berbasis Memory RSS
# Menghentikan worker secara graceful jika konsumsi memori melewati batas ambang
before_worker_shutdown do
  puts "[Puma Worker] Shutting down cleanly..."
end
```

---

### 8. Real World Case Study

#### Kasus Produksi: "PayFlow Enterprise Engine"
- **Konteks**: Sistem pemrosesan transaksi webhook finansial dengan volume **120.000 Request Per Minute (RPM)**.
- **Masalah**: 
  - Latensi P99 melesat ke angka **850 ms** pada jam sibuk.
  - Setiap container Puma (berisi 4 workers) mengalami *memory bloat* dari **450 MB ke 2.8 GB** dalam kurun waktu 3 jam, memicu *OOMKilled* (Exit Code 137) oleh Kubernetes.
- **Analisis Akar Masalah (RCA)**:
  1. **Memory Allocator Inefficiency**: Penggunaan default `glibc` menyebabkan *heap fragmentation*. Ribuan payload JSON parsing berukuran besar ($> 500 \text{ KB}$) menyisakan dirty memory pages yang tidak bisa di-reclaim kernel.
  2. **CoW Broken by Lazy Loading**: Inisialisasi service library pihak ketiga dilakukan di dalam method controller (setelah fork), bukan saat boot aplikasi, merusak Copy-on-Write worker.
  3. **GC Stop-the-world Latency**: Minor dan Major GC terpicu terlalu sering akibat parameter heap default CRuby yang terlalu kecil.

#### Solusi Rekayasa yang Diterapkan:
1. **Injeksi Jemalloc**:
   Dockerfile dimodifikasi untuk mengaktifkan Jemalloc dengan flag `background_thread`:
   ```dockerfile
   ENV LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libjemalloc.so.2"
   ENV MALLOC_CONF="dirty_decay_ms:1000,muzzy_decay_ms:1000,background_thread:true"
   ```
2. **GC Tuning via Environment Variables**:
   ```bash
   RUBY_GC_HEAP_INIT_SLOTS=1000000
   RUBY_GC_HEAP_FREE_SLOTS=500000
   RUBY_GC_HEAP_GROWTH_FACTOR=1.25
   RUBY_GC_MALLOC_LIMIT=64000000
   RUBY_GC_MALLOC_LIMIT_GROWTH_FACTOR=1.4
   ```
3. **Optimasi YJIT**:
   Menambahkan flag `--yjit --yjit-exec-mem-size=128` pada perintah entrypoint.

#### Hasil Pasca-Implementasi:
- Latensi P99 turun dari **850 ms ke 38 ms** (Penurunan sebesar 95.5%).
- Memory Footprint per worker stabil di kisaran **680 MB - 720 MB** konstan selama 7 hari operasi tanpa OOM restart.
- Throughput CPU meningkat: Beban Node berkurang dari 32 server menjadi 14 server AWS c6i.2xlarge, memangkas biaya infrastruktur sebesar **56% per bulan**.

---

### 9. Trade-offs

| Pendekatan / Komponen | Keuntungan (Pros) | Biaya / Kerugian (Cons) | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- |
| **YJIT Engine** | Peningkatan raw CPU execution speed (15% - 40%). | Mengonsumsi memory footprint tambahan (+50-150MB untuk machine code cache). | Direkomendasikan untuk aplikasi I/O-heavy yang bercampur parsing CPU intensif. Matikan jika memory RAM container $\le 512\text{MB}$. |
| **Jemalloc** | Menghilangkan fragmentasi memori, latensi alokasi stabil, CoW ramah. | Membutuhkan dependensi library OS native dan penyesuaian tuning manual `MALLOC_CONF`. | **Wajib** untuk semua aplikasi Ruby level enterprise yang berjalan di platform Linux. |
| **Puma (Hybrid) vs Pitchfork (Fork-only)** | Puma: Fleksibel, hemat memori untuk I/O berkat threading. Pitchfork: CoW murni, zero GVL contention antar worker, refork dynamic. | Puma: GVL bottleneck jika ada CPU spikes. Pitchfork: Konsumsi memori linear terhadap worker jika CoW rusak. | Puma untuk API heterogen; Pitchfork/Falcon untuk pure microservices atau async high-concurrency. |
| **Aggressive GC Compaction** | Memaksimalkan halaman memori shared dan meminimalkan RSS worker. | Membutuhkan waktu eksekusi CPU saat startup (`GC.compact` membutuhkan 100-800ms tergantung ukuran heap). | Jalankan hanya sekali pada fase `before_fork` pada preloading server HTTP. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Merusak Copy-on-Write (CoW) dengan Mutasi Objek Global
- **Masalah**: Mendefinisikan cache in-memory atau mutasi hash global di dalam siklus request worker.
- **Troubleshooting**: Periksa `/proc/<worker_pid>/smaps` atau gunakan gem `derailed_benchmarks` untuk memeriksa *Private Dirty Memory*. Jika memory worker bertumbuh signifikan seiring berjalannya request, terdapat mutasi objek global.

#### 2. String Allocation Churn pada JSON Serializer
- **Masalah**: Menggunakan interpolasi string atau penggabungan string (`+`) alih-alih `freeze` atau `append` (`<<`), memicu ribuan alokasi `RVALUE` temporer per detik.
- **Solusi**: Gunakan magic comment `# frozen_string_literal: true` di seluruh file dan manfaatkan library parsing biner native (misal: `oj` gem dengan mode `:compat` / `:fast`).

#### 3. Thread-Safety Leak pada Server Puma
- **Masalah**: Penggunaan *Class Variables* (`@@var`) atau *Class Instance Variables* tanpa thread synchronization.
- **Troubleshooting**:
  ```ruby
  # SALAH: Race condition dan memory leak across threads
  class ReportGenerator
    def self.cache(data)
      @cache ||= {}
      @cache[Thread.current.object_id] = data # Memory leak!
    end
  end

  # BENAR: Gunakan Thread.current / Concurrent::Map dengan batasan
  class ReportGenerator
    THREAD_SAFE_CACHE = Concurrent::Map.new
    def self.cache(key, data)
      THREAD_SAFE_CACHE.compute_if_absent(key) { data }
    end
  end
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Native Allocator**: Pastikan binary `libjemalloc.so` ter-load via `LD_PRELOAD` dengan opsi `background_thread:true`.
- [ ] **YJIT Enablement**: Jalankan Ruby 3.2+ dengan flag `--yjit` dan monitor metrik `code_region_size`.
- [ ] **CoW Maximization**: Pastikan `preload_app!` diaktifkan di Puma, dan lakukan `GC.compact` di hook `before_fork`.
- [ ] **Thread Pool Tuning**: Atur `RAILS_MAX_THREADS` antara 3-5 untuk CRuby. Setting di atas 5 umumnya kontraproduktif karena GVL contention.
- [ ] **Worker Killing Thresholds**: Konfigurasikan batas daur ulang worker (misal Puma Worker Killer) berbasis memory limit absolut untuk menangkal memory leak dari library C-extensions.
- [ ] **Continuous Profiling**: Pasang sampler profiling (seperti Stackprof sampling 1:100 atau Vernier) yang mengekspor data ke format pprof secara berkala.
- [ ] **Connection Pooling**: Pastikan ukuran database pool $\ge$ jumlah Puma threads per worker (`pool = ENV['RAILS_MAX_THREADS']`).

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

#### Langkah 1: Siapkan Diagnostic Script
Simpan kode berikut sebagai `hands-on/m02/alloc_test.rb`.

```ruby
# hands-on/m02/alloc_test.rb
# frozen_string_literal: true

require 'memory_profiler'

def generate_transactions(count)
  list = []
  count.times do |i|
    # Objek yang berpotensi menyebabkan alokasi boros jika tidak dioptimalkan
    tx = {
      id: "tx-#{i}",
      amount: i * 100.50,
      timestamp: Time.now.to_s,
      status: "COMPLETED"
    }
    list << tx
  end
  list
end

puts "Memulai Profiling Alokasi..."
report = MemoryProfiler.report do
  generate_transactions(10_000)
end

report.pretty_print(scale_bytes: true)
```

#### Langkah 2: Setup Environment & Jemalloc Wrapper
Jalankan langkah berikut di Linux terminal untuk membandingkan baseline memory:

```bash
mkdir -p hands-on/m02
cd hands-on/m02

# 1. Install gem dependensi
gem install memory_profiler stackprof

# 2. Jalankan baseline tanpa jemalloc
ruby alloc_test.rb > baseline_alloc.txt

# 3. Jalankan dengan Jemalloc (Pastikan libjemalloc terinstall di distro Linux Anda)
# Untuk Debian/Ubuntu: apt-get install libjemalloc2
LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libjemalloc.so.2" ruby alloc_test.rb > jemalloc_alloc.txt

# 4. Amati perbandingan retain memory
diff -u baseline_alloc.txt jemalloc_alloc.txt || true
```

#### Langkah 3: Profiling Profil CPU & Sampling Menggunakan Stackprof
Simpan kode berikut sebagai `hands-on/m02/stackprof_test.rb`:

```ruby
# hands-on/m02/stackprof_test.rb
# frozen_string_literal: true

require 'stackprof'

def heavy_json_simulation
  10_000.times.map do |i|
    { id: i, payload: "data_payload_#{i}".upcase }.to_s
  end
end

StackProf.run(mode: :cpu, out: 'tmp/stackprof-cpu.dump', raw: true) do
  heavy_json_simulation
end

puts "Profiling selesai. File disimpan di tmp/stackprof-cpu.dump"
```

Jalankan dan periksa output Flamegraph / Text report:
```bash
mkdir -p tmp
ruby stackprof_test.rb
stackprof tmp/stackprof-cpu.dump --text --limit 5
```

---

### 13. Exercise

#### Level: Easy
**Soal**: Diberikan method pembaca data stream string:
```ruby
def build_payload(items)
  res = ""
  items.each do |item|
    res = res + item.to_s + "\n"
  end
  res
end
```
Optimalkan method di atas agar tidak menghasilkan alokasi string intermediat yang membebani CRuby Heap!

<details>
<summary><b>Jawaban Solusi Easy</b></summary>

```ruby
# frozen_string_literal: true

def build_payload(items)
  # Alokasi buffer dengan pra-estimasi kapasitas jika memungkinkan,
  # dan gunakan in-place mutation (<<) untuk menghindari pembuatan objek String baru.
  res = String.new(capacity: items.size * 32)
  items.each do |item|
    res << item.to_s << "\n"
  end
  res
end
```
**Penjelasan Teknis**: Operator `+` mengalokasikan objek `String` baru pada setiap iterasi loop, memicu pembengkakan slot `RVALUE` pada Eden space. Menggunakan `String.new(capacity: ...)` dan `<<` melakukan mutasi buffer secara langsung pada memori yang dialokasikan tanpa alokasi objek ganda.
</details>

---

#### Level: Medium
**Soal**: Buatlah class Rack Middleware bernama `HeapCompactorMiddleware` yang secara otomatis mencatat metrik `GC.stat` ke standard log, dan jika jumlah slot yang tersisa (`GC.stat[:heap_free_slots]`) kurang dari 10% dari total slot, memicu `GC.start(full_mark: false)` secara asinkron tanpa memblokir siklus HTTP utama secara masif.

<details>
<summary><b>Jawaban Solusi Medium</b></summary>

```ruby
# frozen_string_literal: true

class HeapCompactorMiddleware
  def initialize(app, threshold_ratio: 0.10)
    @app = app
    @threshold_ratio = threshold_ratio
  end

  def call(env)
    response = @app.call(env)
    evaluate_heap_health
    response
  end

  private

  def evaluate_heap_health
    stat = GC.stat
    total_slots = stat[:heap_live_slots] + stat[:heap_free_slots]
    return if total_slots.zero?

    ratio = stat[:heap_free_slots].to_f / total_slots

    if ratio < @threshold_ratio
      # Pemicu Minor GC untuk membersihkan slot Young Gen tanpa melakukan Full sweep yang mahal
      GC.start(full_mark: false, immediate_sweep: true)
      warn(format("[HeapWatch] Free slot ratio low (%.2f%%). Minor GC triggered.", ratio * 100))
    end
  end
end
```
**Penjelasan Teknis**: Middleware mengevaluasi rasio `heap_free_slots`. Pemanggilan `GC.start(full_mark: false)` menginstruksikan RGenGC untuk hanya memproses Young Generation, meminimalkan durasi *Stop-The-World* (biasanya $< 5\text{ms}$) sambil membebaskan slot transien.
</details>

---

#### Level: Hard
**Soal**: Tuliskan implementasi custom Object Pool thread-safe di Ruby untuk membungkus buffer objek koneksi biner yang berat (`StringIO` atau raw memory buffer). Pool harus memiliki fitur: batas kapasitas maksimal, eviction timeout untuk worker yang meminjam resource, serta pencegahan alokasi memori berlebih saat terjadi lonjakan traffic mendadak.

<details>
<summary><b>Jawaban Solusi Hard</b></summary>

```ruby
# frozen_string_literal: true

require 'timeout'
require 'thread'

class HighPerformanceBufferPool
  def initialize(max_size: 20, buffer_capacity: 65_536)
    @max_size = max_size
    @buffer_capacity = buffer_capacity
    @pool = []
    @mutex = Mutex.new
    @condition = ConditionVariable.new
    @created_count = 0

    # Pre-populate pool
    @max_size.times do
      @pool << allocate_buffer
      @created_count += 1
    end
  end

  def with_buffer(timeout_sec: 2.0)
    buffer = acquire(timeout_sec)
    begin
      yield buffer
    ensure
      release(buffer)
    end
  end

  private

  def allocate_buffer
    # Alokasi buffer dengan initial byte capacity untuk menghindari reallocations
    StringIO.new(String.new(capacity: @buffer_capacity))
  end

  def acquire(timeout_sec)
    deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC) + timeout_sec

    @mutex.synchronize do
      loop do
        return @pool.pop unless @pool.empty?

        remaining = deadline - Process.clock_gettime(Process::CLOCK_MONOTONIC)
        raise Timeout::Error, "Buffer pool exhausted within timeout" if remaining <= 0

        @condition.wait(@mutex, remaining)
      end
    end
  end

  def release(buffer)
    # Bersihkan state buffer tanpa menghancurkan alokasi raw string di baliknya
    buffer.reopen(String.new(capacity: @buffer_capacity))

    @mutex.synchronize do
      @pool << buffer
      @condition.signal
    end
  end
end
```
**Penjelasan Teknis**: Pendekatan ini menggunakan algoritma synchronization primitives (`Mutex` dan `ConditionVariable`). Objek `StringIO` didaur ulang melalui metode `reopen` dengan buffer baru yang memiliki alokasi kapasitas tetap, mengeliminasi GC churn saat ratusan thread concurrent meminta alokasi I/O buffer besar secara bersamaan.
</details>

---

### 14. Challenge

#### Skenario: Arsitektur Engine Ingest Webhook 200k RPM Zero-Allocation
Sebuah platform fintech mengalami lonjakan traffic webhook dari gateway pembayaran dengan karakteristik:
- **Volume**: 200.000 requests/menit, ukuran payload rata-rata 8 KB.
- **Kondisi Batasan (Constraints)**:
  - Memory RAM dibatasi maksimal **2 GB** total pada cluster instance (4 Pods Kubernetes, masing-masing 512 MB).
  - P99 latency SLA mutlak **< 25 ms**.
  - Runtime diwajibkan menggunakan Ruby 3.3+.
  
#### Tugas Tantangan:
1. Rancang arsitektur web layer Ruby (Pilih antara Puma, Falcon, atau Pitchfork).
2. Tuliskan blueprint konfigurasi server lengkap beserta optimasi OS, GC parameter, allocator, dan YJIT setting.
3. Rancang mekanisme mitigasi parser: Bagaimana memproses validasi signature HMAC-SHA256 dan ekstraksi 3 field JSON (`transaction_id`, `amount`, `status`) tanpa menginstansiasi pohon AST JSON penuh dari payload 8 KB tersebut.
4. Buat disaster-recovery strategy ketika terjadi spike tak terduga (contoh: 500.000 RPM) tanpa membuat container meledak karena *OOMKilled*.

*(Kerjakan rancangan arsitektur ini secara menyeluruh dalam dokumen spesifikasi teknis dan serahkan dalam format PR dokumen arsitektur).*

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Berapakah ukuran default sebuah slot `RVALUE` pada CRuby 64-bit, dan apa yang terjadi jika string memiliki panjang melebihi kapasitas embedding slot tersebut?
2. Apa tujuan utama dari Generational Garbage Collector (RGenGC) pada Ruby?
3. Mengapa flag `--yjit` membutuhkan konsumsi memori tambahan dibandingkan menjalankan interpreter Ruby murni?
4. Apa fungsi dari pemanggilan `GC.compact`?
5. Mengapa shared memory pada mekanisme Copy-on-Write (CoW) dapat rusak (*dirty*) saat sebuah worker process membaca objek Ruby yang belum pernah diakses sebelumnya?

#### B. Pertanyaan Intermediate
6. Bagaimana cara kerja flag `background_thread:true` pada `jemalloc` dalam menanggulangi lonjakan memory fragmentation pada aplikasi Ruby multi-threaded?
7. Apa indikator metrik pada `RubyVM::YJIT.runtime_stats` yang menunjukkan bahwa YJIT mengalami deoptimization yang buruk (terlalu banyak code bailout)?
8. Pada Puma web server, mengapa koneksi database ActiveRecord harus diputus (`disconnect!`) sebelum melakukan `fork` worker, dan dihubungkan kembali (`establish_connection`) di dalam worker?
9. Jelaskan perbedaan struktural mendasar antara thread model Puma (pre-fork master + hybrid worker threads) dan async fiber model Falcon!
10. Bagaimana magic comment `# frozen_string_literal: true` dapat meningkatkan efisiensi memori pada level CRuby Heap?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Aplikasi API Anda di Kubernetes menggunakan Puma dengan 4 worker dan 5 thread. Anda mengamati bahwa segera setelah pod aktif, memori berada pada angka 300 MB. Namun, setelah melayani 50.000 request, konsumsi memori naik menjadi 1.2 GB dan tidak pernah turun meskipun traffic kembali ke 0 RPM. APM menunjukkan tidak ada retain object permanen di `ObjectSpace`. Apa yang sebenarnya terjadi dan bagaimana solusinya?
12. **Skenario 2**: Setelah mengaktifkan YJIT di production canary, Anda menemukan bahwa latency P50 membaik sebesar 25%, tetapi latency P99 melonjak drastis setiap 10 menit sekali. Tim infrastruktur mengonfirmasi tidak ada aktivitas jaringan luar. Apa akar masalahnya pada YJIT runtime cache?
13. **Skenario 3**: Sebuah worker service memproses background queue (Sidekiq) yang mengonsumsi jobs berukuran besar secara batch. Server mendadak membeku (unresponsive) selama 4-6 detik secara acak tanpa adanya log error. Metrik CPU menunjukkan saturasi 100% pada satu core selama jendela waktu beku tersebut. Diagnosa penyebabnya!

---

<details>
<summary><b>Kunci Jawaban Quiz</b></summary>

1. **Basic 1**: 40 bytes. Jika string melebihi batas embedded slot (umumnya > 23-24 bytes), CRuby akan memanggil system `malloc()` untuk mengalokasikan memori di luar heap slot CRuby, dan slot `RVALUE` hanya menyimpan pointer ke alokasi memori heap eksternal tersebut.
2. **Basic 2**: Mengurangi overhead latency GC. Berdasarkan hipotesis generasi (*Weak Generational Hypothesis*), sebagian besar objek mati muda. Dengan membagi objek menjadi Old dan Young Gen, Ruby dapat menjalankan Minor GC secara cepat hanya pada objek baru tanpa perlu menelusuri seluruh memori heap (*Stop-The-World* minimal).
3. **Basic 3**: YJIT mengalokasikan executable memory space terdedikasi (diatur via `--yjit-exec-mem-size`, default 64MB+) untuk menampung machine code yang dihasilkan dari kompilasi runtime LBBV serta metadata profiling tipe data.
4. **Basic 4**: Melakukan defragmentasi heap CRuby dengan memindahkan objek aktif ke slot-slot kosong di heap page awal, sehingga heap page kosong di ujung memory space dapat dikembalikan ke sistem operasi dan memaksimalkan densitas CoW.
5. **Basic 5**: Karena runtime Ruby mengimplementasikan *lazy internal bookkeeping* (misalnya penandaan GC flags, update age counter, atau penentuan class shape). Membaca atau mengakses objek dapat memicu penulisan bit metadata pada objek tersebut di memori fisik, yang memaksa OS menandai halaman tersebut sebagai dirty dan melakukan copy.
6. **Intermediate 6**: `jemalloc` menggunakan thread background asynchronous terpisah untuk memonitor dirty memory pages dan membersihkannya secara berkala (`decay`) via system call `MADV_DONTNEED`, tanpa memblokir thread eksekusi Ruby utama yang sedang memproses I/O atau komputasi.
7. **Intermediate 7**: Rasio antara `ratio_in_yjit` yang rendah disertai dengan peningkatan drastis pada `invalidation_count` dan nilai bailout yang tinggi di `binding_allocations` atau `leave_yjit`.
8. **Intermediate 8**: File descriptor socket TCP database yang dibuka di master process tidak boleh dibagikan ke multiple forked worker processes. Jika dibagikan, respons dari database akan mengalami *race condition* dan data paket TCP corrupt antar worker yang menggunakan socket ID yang sama.
9. **Intermediate 9**: Puma menggunakan pooling thread OS native (yang dibatasi oleh GVL untuk eksekusi CPU Ruby), sedangkan Falcon berbasis non-blocking event loop murni menggunakan async Fiber di mana ribuan fiber dapat berjalan kooperatif di atas satu thread tanpa overhead context switching kernel thread OS.
10. **Intermediate 10**: Mencegah alokasi slot `RVALUE` baru setiap kali literal string yang sama dibaca. Interpreter Ruby mengarahkan semua referensi literal string yang sama ke satu objek `RVALUE` ter-freeze yang sama di memory space.
11. **Skenario 1**: Ini adalah kasus klasik **OS-level memory fragmentation** akibat alokasi memori glibc bawaan, bukan memory leak kode Ruby. Glibc ptmalloc menolak mengembalikan dirty chunks ke kernel karena slot memori terfragmentasi di berbagai arena. **Solusi**: Integrasikan `jemalloc` melalui `LD_PRELOAD` dengan konfigurasi `MALLOC_CONF="dirty_decay_ms:1000,muzzy_decay_ms:1000,background_thread:true"`.
12. **Skenario 2**: YJIT memory cache kehabisan ruang (`--yjit-exec-mem-size` terlalu kecil untuk footprint kode aplikasi). Saat memori kode YJIT penuh, YJIT melakukan **Code GC** atau membuang seluruh compiled machine code dan mengompilasi ulang dari nol secara berkala, memicu lonjakan latensi masif saat siklus pemanasan ulang (compilation spike). **Solusi**: Tingkatkan ukuran alokasi memori YJIT (misal: 128MB atau 256MB) dan monitor `RubyVM::YJIT.runtime_stats[:code_region_size]`.
13. **Skenario 3**: Terjadi **Major GC Full Stop-the-world run** yang disertai sweeping dan heap expansion besar-besaran. Ketika batch data besar dialokasikan sekaligus, batas `RUBY_GC_MALLOC_LIMIT` terlampaui secara drastis, memaksa GC menghentikan seluruh thread eksekusi untuk menandai ratusan ribu objek lama. **Solusi**: Sesuaikan parameter `RUBY_GC_MALLOC_LIMIT` dan `RUBY_GC_HEAP_GROWTH_FACTOR`, serta ubah pemrosesan batch data menggunakan enumerator batching berukuran kecil (`find_in_batches`/streaming processing) alih-alih me-load seluruh array ke dalam memori.
</details>

---

### 16. Summary

1. **Runtime Efficiency**: Performa tinggi pada CRuby tingkat produksi bergantung pada minimalisasi kerja Garbage Collector. Mengontrol siklus hidup objek (mengurangi alokasi string dan objek transien) secara langsung memangkas latensi P99.
2. **Infrastructure Synergy**: Pemilihan memory allocator native (`jemalloc`) merupakan fondasi krusial bagi aplikasi Ruby modern di lingkungan Linux/Kubernetes untuk mengeliminasi memory bloat akibat fragmentasi arena `glibc`.
3. **Optimasi Lanjutan**: YJIT memberikan akselerasi performa eksekusi komputasi secara signifikan di Ruby 3.x, asalkan batas executable memory dikonfigurasi dengan tepat untuk menghindari kompilasi ulang yang berulang-ulang.
4. **Copy-on-Write Maximization**: Arsitektur server pre-forking (seperti Puma cluster mode) harus memadukan *eager preloading*, *database disconnection*, dan *pre-fork compaction* (`GC.compact`) guna memastikan efisiensi pemakaian memori fisik antar worker process.