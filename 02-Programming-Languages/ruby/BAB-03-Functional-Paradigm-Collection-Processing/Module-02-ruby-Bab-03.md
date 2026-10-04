# Kurikulum Rekayasa Perangkat Lunak Enterprise: Ruby
## Bab 03: Functional Paradigm & Collection Processing
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Engineer / Senior Ruby Engineer diharapkan mampu:

1. **Menganalisis Internal Runtime CRuby**: Membedah mekanisme eksekusi `Enumerable`, `Enumerator`, dan `Enumerator::Lazy` pada level C-extension (`enum.c`) serta manajemen *execution context* YARV (*Yet Another Ruby VM*).
2. **Merancang Pipeline Data Berorientasi Fungsi (Pure Functional Data Pipelines)**: Mengimplementasikan *function composition* (`Proc#>>`, `Proc#<<`), *currying*, dan dekonstruksi *pattern matching* (`case ... in`) dengan paradigma *stateless* dan *immutable*.
3. **Mengoptimalkan Memory Footprint & GC Pressure**: Mengeliminasi alokasi *intermediate arrays* pada pemrosesan dataset berskala gigabyte menggunakan lazy evaluation dan stream processing, serta memitigasi memory leak akibat *closure binding retention*.
4. **Mengisolasi Konkurensi & State Mutability**: Membangun pipeline pemrosesan data thread-safe menggunakan primitif fungsional murni tanpa race conditions pada multi-threaded runtime (Puma/Falcon).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta harus menguasai:
* Arsitektur YARV dasar: Stack frame, call info, *instruction sequences* (`ISeq`).
* Sintaks dasar Ruby Blocks, `yield`, `Proc`, dan `lambda`.
* Penggunaan dasar modul `Enumerable` (`map`, `select`, `reduce`).
* Pemahaman dasar tentang alokasi memori heap Ruby (`RVALUE`, Garbage Collector Generasional *RGenGC*).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi C-Level Modul Enumerable (`enum.c`)

Modul `Enumerable` tidak menyimpan state secara langsung; ia bertindak sebagai *mixin contract* yang menuntut host class untuk mendefinisikan metode `each`.

```
+-------------------------------------------------------------+
|                     Ruby User Space                         |
|   collection.map { |x| x * 2 }                              |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                  CRuby Internals (enum.c)                   |
|                                                             |
|   1. rb_block_call(obj, id_each, 0, 0, enum_map_i, ary)    |
|   2. YARV Control Frame beralih ke context pemanggil       |
|   3. Callback C-function (enum_map_i) dipanggil per elemen   |
|   4. Elemen ditambahkan ke intermediate VALUE ary (RArray)  |
+-------------------------------------------------------------+
```

Pada level native C (`enum.c`), pemanggilan seperti `map` diimplementasikan melalui fungsi internal `rb_block_call`:
1. CRuby mengeksekusi metode `each` milik objek target.
2. Setiap kali blok melakukan iterasi, VM memicu C callback (contoh: `enum_map_i`).
3. Callback ini mengalokasikan slot baru pada struktur C `VALUE ary` (`RArray`).
4. Jika terdapat method chaining (`list.map{}.select{}.reject{}`), CRuby menciptakan instance `Array` sementara (*intermediate array*) baru di setiap rantai method, yang secara eksponensial membebani Eden Heap dan memicu siklus Minor/Major GC.

#### 3.2. Enumerator vs Enumerator::Lazy: Fiber vs Generator

`Enumerator` biasa bekerja secara **eager** ketika dieksekusi dengan metode Enumerable. Untuk iterasi eksternal (`enum.next`), `Enumerator` membungkus eksekusi di dalam **Fiber** internal (lihat `eval.c` / `coroutine`). Fiber mempertahankan execution context stack mandiri; peralihan konteks via `Fiber.yield` membutuhkan alokasi C-stack minimal (biasanya 4KB–16KB tergantung OS/arsitektur) serta context switching cost.

Sebaliknya, `Enumerator::Lazy` (diimplementasikan di `enum.c` sebagai `lazy_*`) **tidak menggunakan Fiber**. `Enumerator::Lazy` menggunakan struktur berantai (*chained closures*) berbasis C-struct `lazy_state`:
* Setiap pemanggilan metode lazy (`.lazy.map {}.select {}`) tidak memproses elemen secara langsung, melainkan membungkus enumerator sebelumnya ke dalam representasi internal `rb_cLazy`.
* Evaluasi ditunda hingga metode terminal (seperti `force`, `first`, `take`, `to_a`) dipanggil.
* Pemrosesan dilakukan secara vertikal per elemen (elemen 1 menembus seluruh pipeline map $\to$ select $\to$ sink, baru lanjut ke elemen 2), menghasilkan performa alokasi memori berorde $O(1)$ terhadap ukuran data total.

#### 3.3. Closures, Bindings, dan GC Retention

Sebuah `Proc` atau `lambda` di Ruby menangkap (*closes over*) seluruh lexical environment tempat ia dideklarasikan melalui struktur C `rb_binding_t`. Struktur ini mencakup:
* Seluruh local variables di scope tersebut.
* Nilai referensi `self`.
* Blok parameter dan call frame context.

```
+---------------------------------------------------------------+
|                      Lexical Scope A                          |
|                                                               |
|  massive_payload = "X" * 100_000_000 # 100MB String           |
|  id_extractor    = ->(record) { record[:id] }                 |
|                                                               |
|  +---------------------------------------------------------+  |
|  | id_extractor (Proc Binding Reference)                   |  |
|  | - Menyimpan referensi implisit ke Lexical Scope A       |  |
|  | - massive_payload TIDAK BISA di-sweep oleh GC           |  |
|  +---------------------------------------------------------+  |
+---------------------------------------------------------------+
```

Jika fungsi berumur panjang (*long-lived object*, misal singleton/service worker) menyimpan referensi ke `Proc` yang dideklarasikan di dalam scope yang memiliki objek besar (*short-lived large memory*), objek besar tersebut **tidak akan dapat di-sweep oleh Garbage Collector**, menyebabkan silent memory leak di environment produksi.

---

### 4. Why & What

| Paradigma / Pendekatan | Karakteristik Utama | Kelemahan di Skala Enterprise |
| :--- | :--- | :--- |
| **Imperative Loops (`for`, `while`)** | Mutasi state manual, variabel penghitung (*counters*) eksplisit. | *Error-prone*, berpotensi race condition dalam concurrent code, melanggar prinsip modularitas. |
| **Standard Enumerable (Eager Chaining)** | Membaca mudah, deklaratif, idiomatis. | Menciptakan *n* array temporer di memory untuk *n* tahapan transformasi. Menyebabkan GC trashing dan crash OOM (*Out Of Memory*) pada data besar. |
| **Pure Functional Chaining (Lazy / Transducer)** | Transformasi pipeline stateless, alokasi memori $O(1)$, dekonstruksi deklaratif via pattern matching. | Memerlukan pemahaman paradigma fungsional murni; overhead pemanggilan metode sedikit lebih tinggi untuk dataset kecil ($N < 1000$). |

---

### 5. How (Workflow Detail)

Arsitektur Functional Data Processing Engine di Ruby enterprise harus mengikuti workflow stream-processing standar:

```
[Ingestion Stream (IO/Socket/DB Cursor)]
                    |
                    v
    [Enumerator Creation (chunking/lazy)]
                    |
                    v
  [Pipeline Invariant: Functional Transformers]
   |--> Step 1: Normalizer  (Proc Currying)
   |--> Step 2: Validator   (Pattern Matching)
   |--> Step 3: Enricher    (Method Object Composition)
                    |
                    v
     [Terminal Consumer / Bounded Sink]
   (e.g., Bulk Insertion / HTTP Multipart Batch)
                    |
                    v
          [Explicit GC Flush Hook]
```

1. **Ingestion**: Sumber data streaming dibuka menggunakan buffer IO bounded (contoh: `IO#each_line` atau cursor batch).
2. **Lazy Promotion**: Kumpulan data diangkat menjadi lazy pipeline via `.lazy`.
3. **Pipeline Transformation**:
   * Fungsi transformasi didefinisikan sebagai fungsi murni (*pure functions*) via `lambda` atau `Method` objects.
   * Fungsi-fungsi tersebut dikomposisikan menggunakan operator compose `>>` (left-to-right) atau `<<` (right-to-left).
   * Data diekstrak dan divalidasi menggunakan structurally-typed pattern matching (`case ... in`).
4. **Bounded Consumption**: Data dikonsumsi secara bertahap menggunakan sink berbasis batching (`each_slice`), memastikan buffer tidak pernah melampaui batas RAM container (cgroups).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pabrik Perakitan Mobil vs Konveyor Batch

* **Eager Chaining (Pabrik Konvensional)**: 
  Mobil mentah sebanyak 100.000 unit dicat semuanya sekaligus (membutuhkan lapangan parkir raksasa untuk menampung 100.000 mobil basah), kemudian semuanya dipasangi roda (butuh lapangan parkir lain), lalu semuanya diuji. Jika lapangan parkir penuh, pabrik kolaps (OOM).
* **Lazy Stream Pipeline (Konveyor Berjalan)**:
  Satu mobil masuk konveyor, langsung dicat, dipasangi roda, dan keluar ke truk pengiriman. Lapangan parkir hanya butuh kapasitas untuk 1 mobil pada satu waktu tertentu.

#### Diagram Arsitektur Alokasi Memori: Eager vs Lazy

```
Eager Processing (3 Intermediate Arrays Created in Heap):
Raw Stream (1GB) 
   | 
   v
[ .map ] --------> Membengkak: Alokasi Heap Array 1 (1.2GB)
   | 
   v
[ .select ] -----> Membengkak: Alokasi Heap Array 2 (600MB)
   | 
   v
[ .reject ] -----> Membengkak: Alokasi Heap Array 3 (550MB) 
   |
   +--> Total memory spike: ~3.35GB (Memicu Major GC / OOM Killer)

Lazy Pipeline (Zero Intermediate Arrays):
Raw Stream (1GB)
   |
   v
[ .lazy ]
   |
   +===[ Elemen 1 ]===> [ map ] ===> [ select ] ===> [ reject ] ===> Sink (Output)
   |
   +===[ Elemen 2 ]===> [ map ] ===> [ select ] ===> [ reject ] ===> Sink (Output)
   |
   +--> Resident Set Size (RSS) stabil pada ~25MB konstan.
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Currying dan Function Composition

```ruby
# frozen_string_literal: true

# Base Pure Functions
sanitize = ->(str) { str.strip.downcase }
prefix   = ->(pref, str) { "#{pref}_#{str}" }
hashify  = ->(str) { { key: str, length: str.bytesize } }

# Currying untuk partial application
curried_prefix = prefix.curry
with_env_prefix = curried_prefix.call("prod")

# Komposisi Pipeline secara Deklaratif: sanitize -> prefix -> hashify
pipeline = sanitize >> with_env_prefix >> hashify

# Eksekusi
result = pipeline.call("  ORDER_SERVICE  ")
# => {:key=>"prod_order_service", :length=>18}
puts result
```

#### 7.2. Practical Example: Production-Grade Telemetry Log Stream Transformer

Transformasi stream log besar tanpa alokasi intermediate arrays menggunakan Pattern Matching dan Method Objects.

```ruby
# frozen_string_literal: true

require "json"
require "stringio"

module TelemetryPipeline
  # Struktur immutable untuk hasil akhir
  AuditEvent = Data.define(:timestamp, :level, :correlation_id, :payload)

  class LogProcessor
    def initialize(target_level: "ERROR")
      @target_level = target_level
    end

    def process_stream(io_stream)
      # Membuka lazy stream dari IO
      io_stream
        .each_line
        .lazy
        .map(&method(:parse_json))
        .filter_map(&method(:filter_and_transform))
        .map(&method(:build_audit_event))
    end

    private

    def parse_json(raw_line)
      JSON.parse(raw_line, symbolize_names: true)
    rescue JSON::ParserError
      nil
    end

    # Menggunakan Ruby 3 Pattern Matching untuk ekstraksi struktural
    def filter_and_transform(parsed_data)
      case parsed_data
      in { level: level, ctx: { trace_id: String => trace_id }, data: payload, time: Integer => epoch } if level == @target_level
        { level: level, trace_id: trace_id, payload: payload, epoch: epoch }
      else
        nil # Diabaikan oleh filter_map
      end
    end

    def build_audit_event(transformed)
      AuditEvent.new(
        timestamp: Time.at(transformed[:epoch]).utc,
        level: transformed[:level],
        correlation_id: transformed[:trace_id],
        payload: transformed[:payload]
      )
    end
  end
end

# Simulasi stream input log JSON raksasa
mock_io = StringIO.new(<<~NDJSON)
  {"time":1700000000,"level":"INFO","ctx":{"trace_id":"tr-1"},"data":{"msg":"Ping"}}
  {"time":1700000001,"level":"ERROR","ctx":{"trace_id":"tr-2"},"data":{"err":"DB Timeout"}}
  INVALID JSON LINE
  {"time":1700000002,"level":"ERROR","ctx":{"trace_id":"tr-3"},"data":{"err":"Mem Leak"}}
NDJSON

processor = TelemetryPipeline::LogProcessor.new(target_level: "ERROR")
# Konsumsi hasil secara streaming
processor.process_stream(mock_io).each do |audit_event|
  puts "[AUDIT] #{audit_event.timestamp} | Trace: #{audit_event.correlation_id} | Payload: #{audit_event.payload}"
end
```

---

### 8. Real World Case Study: FinTech Transaction Reconciliation Engine

#### Latar Belakang Masalah
Sebuah gateway pembayaran skala enterprise memproses file mutasi bank harian berukuran **12 GB** (format CSV/NDJSON gabungan) per malam. Worker runtime (Sidekiq pod pada Kubernetes) memiliki *hard memory limit* sebesar **1.5 GB RAM**. Implementasi sebelumnya menggunakan `CSV.read` dan chaining eager enumerable (`map -> select -> group_by`), yang menyebabkan memory container melesat hingga 8 GB dan terbunuh oleh OOM Killer (Linux signal 9 / `SIGKILL`).

#### Solusi Arsitektur
Membangun pipeline fungsional murni berbasis *reactive stream pull-model*:
1. Stream generator berbasis `Enumerator` memetakan pembacaan file baris per baris.
2. Penggunaan `Enumerator::Lazy` untuk memproses validasi skema dan normalisasi mata uang.
3. Batching fungsional (`slice_after` / `each_slice`) untuk mengirimkan data ke database via *PostgreSQL COPY stream* dalam batch 5.000 record tanpa pernah memuat seluruh dataset ke dalam RAM.

#### Implementasi Produksi

```ruby
# frozen_string_literal: true

require "zlib"
require "objspace"

module ReconciliationEngine
  Transaction = Data.define(:txn_id, :source_account, :amount_cents, :currency)

  class IngestionPipeline
    BATCH_SIZE = 5_000

    def initialize(file_path)
      @file_path = file_path
    end

    def run!
      initial_mem = current_rss_mb
      puts "[START] Initial RSS Memory: #{initial_mem} MB"

      # Stream reader dengan auto-decompression
      open_stream do |io|
        io
          .each_line
          .lazy
          .drop(1) # Skip header baris pertama
          .map(&:chomp)
          .reject(&:empty?)
          .map(&method(:tokenize))
          .filter_map(&method(:validate_and_normalize))
          .each_slice(BATCH_SIZE)
          .each_with_index do |batch, index|
            persist_batch_to_storage(batch, index)
          end
      end

      final_mem = current_rss_mb
      puts "[END] Final RSS Memory: #{final_mem} MB (Delta: #{final_mem - initial_mem} MB)"
    end

    private

    def open_stream(&block)
      File.open(@file_path, "r:UTF-8", &block)
    end

    def tokenize(line)
      line.split(",")
    end

    # Menggunakan Alternative Pattern Matching
    def validate_and_normalize(tokens)
      case tokens
      in [String => id, String => acc, String => raw_amount, ("IDR" | "USD" as curr)]
        cents = (Float(raw_amount) * 100).to_i
        Transaction.new(txn_id: id, source_account: acc, amount_cents: cents, currency: curr)
      else
        nil # Skip data korup secara silently atau route ke Dead-Letter-Queue
      end
    rescue ArgumentError
      nil
    end

    def persist_batch_to_storage(batch, batch_index)
      # Simulasi write via bulk insert atau PG COPY
      # Di sini kita hanya mengamati konsistensi memori
      print "\rProcessing Batch ##{batch_index + 1} (Size: #{batch.size} elements)..."
      batch.clear # Hint referensi internal
    end

    def current_rss_mb
      `ps -o rss= -p #{Process.pid}`.to_i / 1024
    end
  end
end

# Pembuatan data pengujian 1.000.000 baris
test_file = "/tmp/large_transactions.csv"
File.open(test_file, "w") do |f|
  f.puts "id,account,amount,currency"
  1_000_000.times do |i|
    curr = i.even? ? "IDR" : "USD"
    f.puts "TXN-#{i},ACC-#{rand(1000..9999)},#{rand(10..5000)}.50,#{curr}"
  end
end

# Eksekusi pipeline rekonsiliasi
ReconciliationEngine::IngestionPipeline.new(test_file).run!
File.delete(test_file) if File.exist?(test_file)
```

#### Hasil Metrik Produksi
* **Memory Footprint (RSS)**: Turun dari **8.4 GB** menjadi stabil di kisaran **38 MB - 45 MB**.
* **GC Pause Time**: Minor/Major GC pauses berkurang hingga 88% karena ketiadaan alokasi array berskala ratusan megabyte.
* **Throughput**: Memproses 1.000.000 record dalam 6.2 detik pada CPU AMD EPYC 7763.

---

### 9. Trade-offs: Architectural Decision Records (ADR)

| Parameter Dimensi | Eager Processing (`Enumerable`) | Lazy Processing (`Enumerator::Lazy`) | Transducers / Custom Loop |
| :--- | :--- | :--- | :--- |
| **Heap Memory Allocation** | Buruk ($O(N)$ memory, di mana $N$ adalah jumlah data). | Sangat Baik ($O(1)$ flat memory). | Unggul ($O(1)$, tanpa overhead wrapper block). |
| **Throughput (Small Data $N < 10.000$)**| Sangat Cepat (Optimasi C murni pada array internal). | 20%–40% lebih lambat (overhead dispatching block wrapper). | Cepat, implementasi manual minim alokasi. |
| **CPU Cycles & Method Dispatch** | Rendah (looping C terisolasi). | Sedang-Tinggi (banyak frame callback per elemen). | Rendah. |
| **Debuggability & Stack Traces** | Sederhana; stack trace menunjukkan lokasi persis. | Sulit; stack trace terkubur dalam internal `lazy.rb` dan `enum.c`. | Sederhana. |
| **Code Maintainability** | Idiomatis Ruby, mudah dipahami engineer junior. | Deklaratif, membutuhkan pemahaman fungsional. | Kompleks, rawan bug pemeliharaan state. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Menginjeksi Eager Method di Tengah Lazy Chain
Kesalahan paling umum yang merusak sifat streaming adalah memasukkan metode pemecah alur lazy.

```ruby
# SALAH (Fatal): Array di-materialisasi seluruhnya di memori saat memanggil .sort
large_stream.lazy.map { |x| transform(x) }.sort.take(10).to_a

# BENAR: Lakukan sorting di level storage (SQL ORDER BY) atau gunakan priority queue (min-heap)
# Jika harus via lazy, batasi data terlebih dahulu:
large_stream.lazy.map { |x| transform(x) }.take(10).to_a.sort
```

#### 10.2. Memory Leak Akibat Closure Scope Retention
Menangkap objek besar di dalam closure secara tidak sengaja.

```ruby
# SALAH: binding menangkap variable massive_buffer
def build_transformer
  massive_buffer = File.read("giant_file.bin") # 500MB
  schema_version = "v1"

  ->(record) { "#{schema_version}: #{record[:id]}" } # massive_buffer terkunci di binding!
end

# BENAR: Isolasi context closure atau gunakan Method object terpisah
def build_isolated_transformer
  schema_version = "v1"
  # massive_buffer tidak dideklarasikan di sini
  ->(record) { "#{schema_version}: #{record[:id]}" }
end
```

#### 10.3. Thread-Safety: Mutasi Objek yang Dikirim Melalui Functional Pipeline
Mengira bahwa Functional Pipeline secara otomatis membuat objek di dalamnya immutable.

```ruby
# SALAH: Mutasi in-place merusak idempotency dalam sistem konkuren
pipeline = ->(hash) { hash[:status] = "PROCESSED"; hash }

# BENAR: Gunakan immutable copy atau Frozen Value Objects
pipeline = ->(hash) { hash.merge(status: "PROCESSED").freeze }
```

#### Troubleshooting Heap Menggunakan `ObjectSpace`
Jika terjadi peningkatan RSS saat pemrosesan stream:

```ruby
require "objspace"

def debug_memory_allocations
  GC.start
  puts "Total Heap Allocated Pages: #{GC.stat[:heap_allocated_pages]}"
  
  # Hitung jumlah instance Array dan Hash di heap
  counts = Hash.new(0)
  ObjectSpace.each_object { |o| counts[o.class] += 1 }
  
  puts "Array count: #{counts[Array]}"
  puts "Hash count:   #{counts[Hash]}"
  puts "String count: #{counts[String]}"
end
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Selalu Gunakan `#frozen_string_literal: true`**: Menghindari alokasi instansi String duplikat di setiap iterasi transformasi.
- [ ] **Gunakan `filter_map`**: Daripada menggabungkan `.map { ... }.compact` atau `.select { ... }.map { ... }`, gunakan `.filter_map` untuk memotong 50% alokasi perulangan.
- [ ] **Batasi Lazy Infinite Enumerators**: Selalu gunakan guard seperti `.take(n)` saat bekerja dengan `Enumerator.produce` atau deret tak hingga untuk mencegah *infinite loop hang*.
- [ ] **Gunakan Struct / Data.define Sebagai Ganti Hash**: Menggunakan `Data.define` (Ruby 3.2+) menghemat alokasi memori hingga 40% dibandingkan Hash dan menyediakan jaminan *immutability*.
- [ ] **Hindari Regex Compilation di Dalam Loop**: Kompilasi Regexp harus dilakukan di luar blok pipeline (jadikan konstanta beku `REGEXP = /pattern/.freeze`).
- [ ] **Pemberian Ukuran pada Batching Sink**: Sesuaikan batch sink dengan metrik limit IO upstream/downstream (misal: batasan batch query SQL atau payload HTTP gateway, lazimnya 1.000–5.000 item).

---

### 12. Hands-on Practice: Langkah Praktikum Detail

Skenario: Membangun real-time metric accumulator berbasis functional lazy stream pipeline untuk memproses ribuan payload payload log tanpa kebocoran memori.

#### Langkah 1: Siapkan Struktur Direktori
```bash
mkdir -p hands-on/m02
cd hands-on/m02
touch stream_processor.rb
```

#### Langkah 2: Tuliskan Implementasi Lengkap Pipeline
Simpan kode berikut ke dalam `hands-on/m02/stream_processor.rb`:

```ruby
# frozen_string_literal: true

require "benchmark"

# 1. Definisikan Domain Model
Metric = Data.define(:service, :latency_ms, :status)

module StreamEngine
  class << self
    def generate_dummy_data(count)
      Enumerator.new do |yielder|
        services = %w[auth payment order notification warehouse]
        statuses = [200, 200, 200, 400, 500]

        count.times do |i|
          yielder << {
            id: i,
            service: services.sample,
            latency: rand(5..1200),
            status: statuses.sample,
            timestamp: Time.now.to_i
          }
        end
      end
    end

    def build_pipeline(data_source)
      data_source
        .lazy
        .filter_map(&method(:validate_and_extract))
        .select(&method(:high_latency_only?))
        .map(&method(:enrich_metric_tags))
    end

    private

    def validate_and_extract(payload)
      case payload
      in { service: String => s, latency: Integer => l, status: Integer => st }
        Metric.new(service: s, latency_ms: l, status: st)
      else
        nil
      end
    end

    def high_latency_only?(metric)
      metric.latency_ms > 200
    end

    def enrich_metric_tags(metric)
      severity = metric.latency_ms > 1000 ? :critical : :warning
      {
        service_name: metric.service,
        duration: metric.latency_ms,
        status_code: metric.status,
        alert_level: severity
      }
    end
  end
end

# 3. Benchmark Eager vs Lazy
RECORD_COUNT = 500_000

puts "Memulai Eksekusi Pipeline #{RECORD_COUNT} records..."

# Pengukuran Alokasi Memori
def measure_memory
  GC.start
  mem_before = `ps -o rss= -p #{Process.pid}`.to_i
  yield
  GC.start
  mem_after = `ps -o rss= -p #{Process.pid}`.to_i
  "#{mem_after - mem_before} KB"
end

mem_used = measure_memory do
  raw_source = StreamEngine.generate_dummy_data(RECORD_COUNT)
  pipeline   = StreamEngine.build_pipeline(raw_source)

  # Materialisasi hanya 10 item pertama (Short-circuit termination)
  top_10 = pipeline.take(10).to_a
  puts "Top 10 High Latency Events:"
  top_10.each { |evt| puts "  - #{evt}" }
end

puts "\nMemori Tambahan Digunakan: #{mem_used}"
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan skrip dari terminal:
```bash
ruby hands-on/m02/stream_processor.rb
```
*Pastikan memori yang digunakan tidak bertambah signifikan (< 5 MB) meskipun dataset generator dikonfigurasi hingga 500.000 elemen.*

---

### 13. Exercise

#### Level: Easy
Buatlah fungsi `functional_slugify` menggunakan method composition (`Proc#>>`) yang menerima string mentah dan mengembalikan URL slug yang valid.
* Tahapan: Hapus whitespace di awal/akhir $\to$ Ubah ke lowercase $\to$ Ganti spasi/karakter non-alphanumerik dengan strip (`-`) $\to$ Hilangkan multiple strip berurutan.
* **Syarat**: Menggunakan komposisi lambda tanpa assignment variabel temporer.

#### Level: Medium
Tulis sebuah fungsi fungsional murni `chunked_rate_limiter` yang menerima sebuah lazy stream dan integer batas laju `rate_per_sec`.
* Fungsi harus menghasilkan stream baru di mana setiap batch item berukuran `rate_per_sec` ditahan (*sleep interval*) secara terkalkulasi sebelum di-yield ke proses selanjutnya, tanpa memakan memori di luar batch yang sedang berjalan.

#### Level: Hard
Implementasikan custom Enumerable class bernama `TransducedStream` yang memproses operasi `map` dan `filter` tanpa membuat subclass `Enumerator::Lazy` ataupun menggunakan `Fiber`.
* **Syarat**: Seluruh transformasi harus direpresentasikan sebagai komposisi fungsi tingkat tinggi (*higher-order functions*) yang menerima reducer `(accumulator, input) -> output` dan mengembalikan reducer baru.
* Buktikan bahwa alokasi heap `GC.stat[:total_allocated_objects]` dari rantai 5 transformasi data pada 100.000 elemen sama dengan 0 alokasi intermediate array.

---

### 14. Challenge: Zero-Allocation Multi-Source Ledger Audit Engine

Rancang dan bangun arsitektur sistem berbasis Ruby murni untuk menyelesaikan tantangan industri berikut tanpa solusi instan:

#### Konteks Masalah
Terdapat 3 aliran stream data finansial independen:
1. `AuthStream`: Stream log autentikasi pengguna (berisi `user_id`, `ip_address`, `session_token`).
2. `PaymentStream`: Stream instruksi transfer (berisi `session_token`, `amount`, `destination_account`).
3. `CoreBankStream`: Stream status core banking (berisi `txn_ref`, `status`, `account_no`).

Data datang dalam format NDJSON tak terurut (*out-of-order*) melalui tiga Unix domain sockets yang berbeda.

#### Ketentuan Sistem
1. **Zero-Intermediate Allocation**: Pipeline dilarang keras memuat seluruh data ke dalam in-memory database atau native Ruby `Array` tanpa batas.
2. **Dynamic Sliding Windowing**: Buat mekanisme functional sliding window berbasis waktu (Window rentang 5 detik) untuk merekonsiliasi transaksi yang cocok antara ketiga stream tersebut berdasarkan `session_token` dan `account_no`.
3. **State Immutability**: State window rekonsiliasi harus dikelola secara fungsional menggunakan representasi struktur data persisten (*Persistent Data Structures* atau frozen structures), menjamin ketiadaan side-effects.
4. **Backpressure Propagation**: Jika salah satu stream menghasilkan data lebih cepat daripada kecepatan komparasi rekonsiliasi, pipeline harus secara otomatis menahan laju konsumsi IO socket tersebut (*pull-based backpressure*).
5. **Output**: Stream hasil rekonsiliasi anomali (fraud event / missing record) harus langsung di-stream ke pipe `STDOUT` dalam format streaming JSON.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)

1. Apa perbedaan mendasar dalam alokasi memori antara `collection.map {}.select {}` dan `collection.lazy.map {}.select {}`?
2. Mengapa operator `filter_map` lebih disukai dibandingkan kombinasi `.map.compact` dalam pipeline collection Ruby?
3. Sebutkan struktur internal C di dalam VM Ruby yang bertanggung jawab menyimpan konteks lexical scope saat sebuah `Proc` diciptakan!
4. Apa output dari kode berikut: `f = ->(x, y) { x * y }.curry; double = f.call(2); puts double.call(5)`?
5. Mengapa pemanggilan metode `.sort` di tengah-tengah pemrosesan `Enumerator::Lazy` menghilangkan benefit lazy evaluation?

#### Bagian 2: Intermediate (5 Pertanyaan)

1. Jelaskan bagaimana `Enumerator.produce` bekerja dan bagaimana cara menghentikan evaluasinya agar tidak menyebabkan infinite execution loop!
2. Bagaimana mekanisme YARV menangani pencocokan nilai pada ekspresi `case ... in` dengan guard clause (`if condition`)?
3. Jelaskan potensi resiko memory leak yang terjadi ketika sebuah objek berumur panjang (*long-lived*) mereferensikan sebuah lambda yang dideklarasikan di dalam controller action!
4. Jelaskan perbedaan mekanisme iterasi eksternal (`Enumerator#next`) yang berbasis Fiber dibandingkan iterasi internal (`Enumerator#each`) dari sudut pandang alokasi C-stack!
5. Apa kegunaan operator `Proc#>>` dibandingkan `Proc#<<`? Berikan representasi matematisnya ($f \circ g$)!

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

1. **Kasus 1 (Memory Explosion pada Background Job)**:
   Sebuah worker Sidekiq yang membaca data export 50 juta pengguna dari database mengalami lonjakan memori (*RSS spike*) dari 300MB menjadi 4.5GB dalam waktu 30 detik, yang berujung pada status `Killed: 9` dari cgroups OOM manager. Kode saat ini:
   ```ruby
   User.find_each.map(&:to_csv_row).each_slice(1000) { |batch| upload(batch) }
   ```
   Analisis penyebab kegagalan alokasi tersebut dan ubah strukturnya agar memori RSS tidak pernah melampaui 500MB!

2. **Kasus 2 (Race Condition pada Pipeline Konkuren)**:
   Tim Anda menggunakan Falcon (server web berbasis Fiber/Async) dan menerapkan pipeline fungsional berikut di level request handler:
   ```ruby
   TRANSFORMER = ->(payload) {
     @shared_cache ||= {}
     @shared_cache[:counter] = @shared_cache.fetch(:counter, 0) + 1
     payload.merge(request_id: @shared_cache[:counter])
   }
   ```
   Identifikasi potensi bahaya dari kode di atas dalam arsitektur konkurensi non-blocking dan rancang solusi fungsional murninya!

3. **Kasus 3 (CPU Bottleneck pada Lazy Chaining)**:
   Seorang insinyur menerapkan `.lazy` pada seluruh transformasi array di dalam aplikasi microservice mereka, termasuk pada array yang hanya memiliki rata-rata 5 sampai 10 elemen. Profiling APM menunjukkan peningkatan latency sebesar 35% pada CPU utilization. Jelaskan mengapa hal ini terjadi berdasarkan arsitektur internal CRuby!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian 1: Basic
1. `collection.map{}.select{}` mengalokasikan *intermediate array* penuh di heap untuk setiap tahapan ($O(N)$ memory), sedangkan lazy pipeline memproses satu elemen hingga ujung pipeline sebelum memproses elemen berikutnya, meniadakan array sementara ($O(1)$ memory).
2. `filter_map` memadukan operasi pemfilteran (truthy predicate) dan pemetaan dalam satu lintasan iterasi tunggal di C level (`enum_filter_map`), menghemat alokasi array perantara dan overhead 1 siklus perulangan penuh.
3. `rb_binding_t` (yang merujuk pada `rb_env_t` di internal VM).
4. Output: `10`. Currying memungkinkan aplikasi parsial argumen pertama (`x = 2`), menghasilkan fungsi baru yang menunggu argumen kedua (`y = 5`).
5. Karena untuk menentukan urutan sorting (`.sort`), algoritma harus mengetahui dan membandingkan *seluruh* elemen dalam koleksi secara lengkap. Hal ini memaksa lazy enumerator untuk mematerialisasi seluruh data ke dalam memori (*eager buffering*).

#### Bagian 2: Intermediate
1. `Enumerator.produce(initial_state) { |prev| next_state }` menghasilkan generator tanpa batas (*infinite stream*). Untuk menghentikannya, kita harus memanggil metode pemotong bounded seperti `.take(n)` atau melempar `:stop_iteration` via `raise StopIteration` di dalam blok.
2. YARV mengeksekusi pemeriksaan pola struktural terlebih dahulu (melalui instruction sequence `checkmatch` atau dekonstruksi C internal). Jika struktur pola cocok, ekspresi guard dievaluasi. Jika guard bernilai `false`, VM melanjutkan pencarian ke cabang pattern `in` berikutnya tanpa keluar dari struktur `case`.
3. Lambda tersebut membawa referensi binding (`rb_binding_t`) ke seluruh lexical environment di mana ia dibuat. Jika lexical environment tersebut memiliki variabel lokal yang menyimpan objek besar (seperti payload respon API mentah atau model ActiveRecord), objek tersebut tidak dapat di-sweep oleh GC selama objek penampung lambda masih hidup.
4. `Enumerator#next` membungkus iterasi di dalam Fiber terpisah dan memanfaatkan Fiber context-switching untuk menghentikan (*suspend*) dan melanjutkan (*resume*) eksekusi, yang membutuhkan alokasi C-stack independen. `Enumerator#each` berjalan langsung di atas current execution frame thread yang bersangkutan tanpa overhead alokasi Fiber stack.
5. `Proc#>>` adalah forward composition: `(f >> g).call(x)` sama dengan `g(f(x))`. Sedangkan `Proc#<<` adalah backward composition: `(f << g).call(x)` sama dengan `f(g(x))` (ekuivalen dengan definisi matematis $f \circ g$).

#### Bagian 3: Solusi Kasus Produksi
1. **Solusi Kasus 1**:
   Penyebab: `User.find_each` mengembalikan Enumerator, namun pemanggilan `.map` di belakangnya bersifat **eager**. Pemanggilan `.map(&:to_csv_row)` memaksa 50 juta record database dikonversi ke dalam sebuah Array raksasa di dalam memori sebelum diteruskan ke `each_slice`.
   Perbaikan: Gunakan lazy pipeline atau proses batch langsung di dalam loop:
   ```ruby
   User.find_each
       .lazy
       .map(&:to_csv_row)
       .each_slice(1000) { |batch| upload(batch) }
   ```
2. **Solusi Kasus 2**:
   Penyebab: Mutasi state bersama (`@shared_cache[:counter]`) melanggar prinsip kemurnian fungsional dan tidak thread-safe/fiber-safe. Pada runtime asynchronous/concurrent, Fiber switching dapat terjadi di antara operasi pembacaan dan penulisan hash, menyebabkan *lost updates* dan race conditions pada counter.
   Perbaikan: Hilangkan mutable state bersama. Gunakan identifier unik non-stateful seperti `SecureRandom.uuid_v7` yang digabungkan langsung via pure function:
   ```ruby
   TRANSFORMER = ->(payload) {
     payload.merge(request_id: SecureRandom.uuid_v7).freeze
   }
   ```
3. **Solusi Kasus 3**:
   Penyebab: `Enumerator::Lazy` memiliki overhead cost per-elemen karena pembungkusan callback blok berantai (*chained dynamic dispatching* dan pembuatan objek enumerator pembungkus). Pada koleksi kecil ($N < 10.000$), algoritma C native dari `Array#map` dan `Array#select` jauh lebih cepat dan teroptimasi pada level CPU cache/memory locality dibandingkan overhead traversal method chaining dari lazy enumerator.

---

### 16. Summary

* **Enumerable vs Lazy**: Gunakan eager `Enumerable` untuk dataset kecil hingga menengah di mana latensi CPU dan kesederhanaan kode menjadi prioritas. Beralihlah ke `Enumerator::Lazy` atau streaming murni ketika ukuran dataset melampaui kapasitas L3 CPU Cache atau mendekati batas cgroups RAM environment produksi.
* **Functional Pipelines**: Manfaatkan `Proc#>>`, currying, dan pattern matching (`case ... in`) untuk membangun pipeline transformasi data deklaratif, modular, dan bebas mutasi (*stateless*).
* **Memory Lifecycle**: Hati-hati terhadap penutupan lexical scope (*closure bindings*) pada lambda berumur panjang untuk menghindari memory retention leak. Selalu pastikan sink pemrosesan membatasi konsumsi stream melalui *bounded batching* (`each_slice`).