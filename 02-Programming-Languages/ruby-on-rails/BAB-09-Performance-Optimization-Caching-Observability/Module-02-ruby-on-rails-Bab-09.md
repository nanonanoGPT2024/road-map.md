# KURIKULUM REKAYASA PERANGKAT LUNAK TINGKAT ENTERPRISE: RUBY ON RAILS
## BAB 09: Performance Optimization, Caching & Observability
### MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Principal Engineer/Staff Engineer diharapkan memiliki kompetensi untuk:
1. **Mengarsiteksi Topologi Caching Skala Multi-Tier**: Mengimplementasikan *Russian Doll Caching*, fragment caching berjenjang, dan *low-level caching* dengan mekanisme mitigasi *Cache Stampede* (*dogpiling*) menggunakan algoritma *Probabilistic Early Expiration* (XFetch) dan `race_condition_ttl`.
2. **Menguasai Profiling & Eliminasi Alokasi Memori**: Mendiagnosis fragmentasi memori *glibc vs jemalloc*, menganalisis retensi Ruby Heap menggunakan `derail_benchmarks` dan `memory_profiler`, serta men-tuning konfigurasi *Ruby Garbage Collection* (RGenGC) pada runtime produksi.
3. **Membangun Arsitektur Observability Terdistribusi**: Menginstrumentasi *ActiveSupport::Notifications* ke OpenTelemetry (OTel), Prometheus, dan structured JSON logging untuk penelusuran metrik *P99 latency*, *database connection pool starvation*, dan *thread contention*.
4. **Mengoptimalkan Pipeline HTTP Caching & Edge Invalidation**: Memanfaatkan ETag, `stale?`, `fresh_when`, dan header `Surrogate-Key`/`Cache-Tag` untuk integrasi CDN (Fastly/Cloudflare) dengan latensi sub-milidetik.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib memahami secara komprehensif:
*   Siklus hidup request-response Rails (ActionDispatch pipeline, Rack Middleware stack).
*   Dasar fragment caching, view helpers (`cache`, `cache_if`), dan model callbacks.
*   Model eksekusi Puma: *Cluster Mode* (Forking) vs *Worker Threads*, serta Global VM Lock (GVL) pada MRI Ruby.
*   Dasar komunikasi jaringan TCP/IP, protokol HTTP/1.1 & HTTP/2, serta sintaks Redis core commands.

---

### 3. Concept & Internal Architecture

#### 3.1 Ruby MRI Memory Management & The Allocator Dilemma
Ruby MRI (CRuby 3.x) mengelola memori melalui dua lapisan: **Ruby Heap** (berisi *RVALUE* berukuran tetap 40 byte) dan **System Allocator** (mengelola alokasi memori dinamis di luar slot RVALUE, seperti string panjang, hash besar, dan array).

```
+-----------------------------------------------------------------------+
|                            OS Virtual Memory                          |
|  +-----------------------------------------------------------------+  |
|  |                 System Allocator (jemalloc / glibc)             |  |
|  |  +-----------------------------------------------------------+  |  |
|  |  |                     Ruby Heap Page                        |  |  |
|  |  |  +---------+ +---------+ +---------+     +---------+      |  |  |
|  |  |  | RVALUE  | | RVALUE  | | RVALUE  | ... | RVALUE  |      |  |  |
|  |  |  | 40 Byte | | 40 Byte | | 40 Byte |     | 40 Byte |      |  |  |
|  |  |  +----+----+ +---------+ +----+----+     +---------+      |  |  |
|  |  +-------|-----------------------|---------------------------+  |  |
|  |          | (malloc)              | (malloc)                     |  |
|  |          v                       v                              |  |
|  |     [String Data]           [Hash Buckets]                      |  |
|  |    (Heap Fragment)         (Heap Fragment)                      |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

*Default memory allocator* pada Linux (`glibc ptmalloc`) mendesain arena memori per-thread. Ketika thread-thread Puma dialokasikan secara dinamis, `glibc` menahan arena memori tersebut dan jarang melepaskannya kembali ke OS (efek *memory fragmentation*). Hal ini menyebabkan masalah klasik *Rails Memory Bloat*. 
Implementasi **jemalloc** menggantikan arena glibc dengan chunk metadata yang terindeks (*slab allocation*), menghasilkan fragmentasi jauh lebih rendah dan melepaskan *dirty pages* via `madvise(MADV_DONTNEED)` secara agresif.

#### 3.2 ActiveSupport::Cache Architecture & Russian Doll Invalidation
Topologi *Russian Doll Caching* mengandalkan asosiasi database yang saling merambat naik (*bubble-up touch*). Rails menggunakan cache store adaptor (`:redis_cache_store`, `:mem_cache_store`) yang membungkus *serialized payload* bersama *digest key*.

Struktur Cache Key Rails:
`views/v1/products/[ID]-[updated_at_timestamp]/[template_tree_digest]`

Ketika objek anak berubah, ia memicu callback `touch: true` pada `belongs_to`, memperbarui `updated_at` parent, yang secara otomatis mengubah cache key parent tanpa perlu melakukan invalidasi manual (penghapusan data fisik). Data lama di Redis/Memcached akan kedaluwarsa secara alami via kebijakan LRU (*Least Recently Used*).

#### 3.3 ActiveSupport::Notifications Event Bus & Instrumentation
Instrumentation internal Rails berbasis pola *Pub/Sub synchronous* berkinerja tinggi. Modul inti Rails membungkus blok eksekusi dengan `ActiveSupport::Notifications.instrument(name, payload)`. Event dialirkan ke subscribers yang mengeksekusi ekstraksi metrik tanpa mengalokasikan string secara berlebih, meminimalkan overhead latency pada thread request.

---

### 4. Why & What

| Komponen / Masalah | Pendekatan Konvensional | Pendekatan Arsitektur Produksi Lanjutan | Mengapa Diperlukan di Skala Enterprise? |
| :--- | :--- | :--- | :--- |
| **Penyimpanan Cache** | Redis tunggal, tanpa kompresi, serialisasi Marshal standar. | Redis Cluster / Sharded, MessagePack / Libyaml serializer, kompresi Zstandard (zstd). | Menghemat memory footprint Redis hingga 60%, mencegah single point of failure (SPOF), dan memangkas deserialization overhead CPU. |
| **Cache Invalidation** | Manual `Rails.cache.delete` berbasis observer atau callbacks. | Key-based Expiration (Russian Doll) + CDN `Surrogate-Key` edge purge. | Menghilangkan *race conditions*, menghindari stale data antar microservices, serta memindahkan 90% load dari origin ke edge network. |
| **Lonjakan Beban (Stampede)** | Request langsung query DB saat cache miss. | Lock-based (`race_condition_ttl`) atau XFetch Probabilistic Early Recomputation. | Menghindari *thundering herd problem* saat cache key dengan traffic 50.000 RPS kedaluwarsa, yang dapat meruntuhkan database relasional dalam hitungan detik. |
| **Alokasi Memori** | Menambah kapasitas RAM server secara vertikal. | jemalloc preload, GC tuning environment variable, audit alokasi berbasis jemalloc stats. | Mencegah OOM Killers pada container Kubernetes, menstabilkan P99 latency akibat *Stop-The-World* GC pauses. |
| **Observability** | Parsing teks log Rails default (`production.log`) via regex. | Structured JSON Logging, integrasi OpenTelemetry SDK terpadu ke OTLP Collector. | Memungkinkan query multi-dimensi (trace_id, user_id, duration) dan korelasi distributed tracing end-to-end lintas distributed microservices. |

---

### 5. How: Alur Eksekusi & Workflow Detail

#### 5.1 Alur Mitigasi Cache Stampede Menggunakan Algoritma Probabilistic Early Expiration (XFetch)

Ketika cache mendekati masa kedaluwarsa, algoritma XFetch menghitung probabilitas apakah thread saat ini harus melakukan *recompute* di latar belakang sebelum nilai benar-benar habis:

$$\text{Tentukan Recompute Jika: } -\beta \times \delta \times \ln(r) \ge (\text{expiry} - \text{current\_time})$$

*   $\beta > 0$: Nilai agresivitas (default 1.0).
*   $\delta$: Waktu eksekusi yang dibutuhkan untuk komputasi ulang data (*delta*).
*   $r$: Angka acak seragam antara 0 dan 1 ($r \in (0, 1)$).

```
Request Datang -> Baca Cache (Nilai, Delta, Expiry)
      |
      +---> [Data Tidak Ada?] ---> Eksekusi Query DB -> Simpan Cache -> Return Data
      |
      +---> [Data Ada]
                |
                v
       Hitung Algoritma XFetch
                |
       +--------+--------+
       |                 |
  [XFetch = True]   [XFetch = False]
       |                 |
       |                 +--> Return Cached Data Seketika
       v
  Acquire Mutex Non-blocking
       |
  +----+----+
  |         |
[Berhasil] [Gagal / Sedang Dihitung Thread Lain]
  |         |
  |         +--> Return Cached Data Seketika (Tanpa Tunggu)
  v
Async / Sync Recompute DB
  |
Simpan Nilai Baru, Delta Baru, Expiry Baru ke Cache Store
  |
Return Nilai Terkini
```

---

### 6. Analogi & Diagram ASCII

#### 6.1 Analogi: Dapur Restoran Bintang Lima vs Memori Rails
Bayangkan dapur restoran (*Rails Process*):
*   **glibc Ptmalloc**: Seperti koki yang membeli wajan khusus baru setiap kali ada menu pesanan baru, lalu menumpuk wajan kotor di lorong dapur alih-alih mengembalikannya ke rak gudang. Dapur cepat kehabisan ruang (fragmentasi), meskipun kapasitas fisik gedung masih luas.
*   **jemalloc**: Manajer peralatan yang mengorganisir wajan ke dalam kompartemen ukuran terstandarisasi (*slab*). Wajan yang selesai dipakai langsung dibersihkan dan disiapkan kembali secara instan, atau dilipat untuk memberi ruang gerak.
*   **Russian Doll Caching**: Seperti bento box bertingkat. Selama lauk utama belum basi, tutup kotak tidak perlu dibongkar. Jika sebutir anggur diganti (anak objek diupdate), cukup bungkus kompartemen buah yang diganti, kotak luarnya hanya mencatat label stiker baru secara instan.

#### 6.2 Diagram Arsitektur Caching & Observability

```
                                      CLIENT / BROWSER
                                             |
                                  [HTTPS GET /products/42]
                                             |
                                             v
                           +-----------------------------------+
                           |        EDGE CDN (Cloudflare)      |
                           |  Cache Hit via Surrogate-Key?     |
                           +-----------------+-----------------+
                                             | MISS
                                             v
                               +---------------------------+
                               |     NGINX / INGRESS       |
                               | (Upstream Load Balancing) |
                               +-------------+-------------+
                                             |
                                             v
                    +-------------------------------------------------+
                    |               PUMA APP SERVER                   |
                    | (Preloaded with LD_PRELOAD=libjemalloc.so.2)    |
                    |                                                 |
                    |  +-------------------------------------------+  |
                    |  | Middleware Stack: OTel Rack Trace Inject  |  |
                    |  +---------------------+---------------------+  |
                    |                        |                        |
                    |                        v                        |
                    |      Controllers & Russian Doll Views           |
                    |  +-------------------------------------------+  |
                    |  | Read Parent Fragment                      |  |
                    |  |   --> Read Child Fragments (Multi-Get)    |  |
                    |  +---------------------+---------------------+  |
                    |                        |                        |
                    |  +---------------------+---------------------+  |
                    |  | ActiveSupport::Notifications Event Bus    |  |
                    |  +--+--------------------+-------------------+  |
                    +-----|--------------------|----------------------+
                          |                    |
         Cache Miss/Multi |                    | Telemetry Metrics
                          v                    v
              +--------------------+   +--------------------------------+
              | REDIS CLUSTER 7.X  |   | OPENTELEMETRY COLLECTOR        |
              | (L2 Shared Cache)  |   | -> Export Prometheus Scrape    |
              | Driver: hiredis    |   | -> Export Jaeger/Tempo Traces  |
              +---------+----------+   +--------------------------------+
                        |
            Query Miss  v
              +--------------------+
              | POSTGRESQL CLUSTER |
              | (Primary / Replica)|
              +--------------------+
```

---

### 7. Implementasi Kode Standar Industri

#### 7.1 Konfigurasi Low-Allocation Cache Store dengan Zstandard Compression
File: `config/environments/production.rb`

```ruby
# frozen_string_literal: true

require "active_support/core_ext/integer/time"

Rails.application.configure do
  # Menggunakan Redis Cache Store dengan pooling berkinerja tinggi
  config.cache_store = :redis_cache_store, {
    url: ENV.fetch("REDIS_CACHE_URL") { "redis://127.0.0.1:6379/1" },
    connect_timeout: 0.5,       # 500ms connection timeout
    read_timeout: 0.2,          # 200ms read timeout
    write_timeout: 0.5,         # 500ms write timeout
    reconnect_attempts: 1,
    pool_size: ENV.fetch("RAILS_MAX_THREADS") { 5 }.to_i * 2,
    pool_timeout: 1.0,
    
    # Kompresi payload menggunakan algoritma zstd (Level 3 untuk rasio/CPU trade-off optimal)
    compressor: Class.new {
      def self.dump(entry)
        Zstandard.compress(Marshal.dump(entry), level: 3)
      end

      def self.load(payload)
        Marshal.load(Zstandard.decompress(payload))
      end
    },
    
    # Ambang batas kompresi: hanya kompresi objek > 1KB
    compress: true,
    compress_threshold: 1.kilobyte,
    
    # Mencegah cache stampede bawaan Rails
    race_condition_ttl: 5.seconds,
    
    error_handler: ->(method:, returning:, exception:) {
      # Mencegah kegagalan Redis mematikan siklus request Rails
      OpenTelemetry::Trace.current_span.record_exception(exception)
      PrometheusMetrics.redis_errors_counter.increment(labels: { method: method })
      Rails.logger.error("[CACHE ERROR] Method: #{method} failed: #{exception.class} - #{exception.message}")
    }
  }
end
```

#### 7.2 Implementasi Advanced Russian Doll Caching dengan CDN Surrogate-Keys
File: `app/models/product.rb`

```ruby
# frozen_string_literal: true

class Product < ApplicationRecord
  belongs_to :category, touch: true # Menginvalidasi cache kategori secara berantai
  has_many :variants, dependent: :destroy
  
  # Validasi ketersediaan data untuk digest key
  validates :title, :price_cents, presence: true

  # Cache key granularitas tinggi
  def cache_key_with_version
    "v1/products/#{id}-#{updated_at.utc.to_fs(:usec)}"
  end
end
```

File: `app/controllers/products_controller.rb`

```ruby
# frozen_string_literal: true

class ProductsController < ApplicationController
  # Penerapan HTTP Caching berbasis Conditional GET (ETag / Last-Modified)
  def show
    @product = Product.includes(:variants).find(params[:id])

    # Injeksi header Surrogate-Key untuk Fastly/Cloudflare instant purging
    response.headers["Surrogate-Key"] = "product-#{@product.id} category-#{@product.category_id}"
    response.headers["Surrogate-Control"] = "max-age=86400, stale-while-revalidate=60"

    # Evaluasi conditional HTTP cache validation
    return unless stale?(
      etag: @product,
      last_modified: @product.updated_at,
      public: true,
      template: false
    )

    respond_to do |format|
      format.html
      format.json { render json: @product }
    end
  end
end
```

File: `app/views/products/show.html.erb`

```erb
<%# Outer Russian Doll: Cache Parent View %>
<% cache ["v1", @product] do %>
  <div class="product-card" id="product_<%= @product.id %>">
    <h1><%= @product.title %></h1>
    <p class="description"><%= @product.description %></p>

    <div class="variants-container">
      <%# Inner Russian Doll: Cache Collection terfragmentasi %>
      <%= render partial: "variants/variant", collection: @product.variants, cached: true %>
    </div>
  </div>
<% end %>
```

File: `app/views/variants/_variant.html.erb`

```erb
<%# Child Fragment %>
<% cache ["v1", variant] do %>
  <div class="variant-item" id="variant_<%= variant.id %>">
    <span class="sku"><%= variant.sku %></span>
    <span class="price"><%= number_to_currency(variant.price) %></span>
    <span class="stock"><%= variant.stock_count %> units left</span>
  </div>
<% end %>
```

#### 7.3 Implementasi High-Throughput Safe Low-Level Cache (XFetch Engine)
File: `app/services/resilient_cache.rb`

```ruby
# frozen_string_literal: true

class ResilientCache
  DEFAULT_BETA = 1.0

  class << self
    # Mengambil atau menghitung data menggunakan evaluasi probabilitas XFetch
    def fetch_xfetch(key, ttl:, beta: DEFAULT_BETA, store: Rails.cache)
      meta_key = "#{key}:__xfetch_meta__"
      data = store.read(key)
      meta = store.read(meta_key)

      now = Process.clock_gettime(Process::CLOCK_MONOTONIC)

      if data && meta
        delta = meta[:delta]
        expiry = meta[:expiry]

        # Logika Inti XFetch: -beta * delta * ln(rand())
        # Jika nilai acak melampaui sisa waktu (expiry - now), lakukan komputasi ulang sekarang
        should_recompute = (-beta * delta * Math.log(rand)).to_f >= (expiry - now)

        unless should_recompute
          return data
        end
      end

      # Atomic distributed lock untuk menjamin hanya SATU worker yang menghitung
      lock_acquired = store.write("#{key}:__lock__", "1", raw: true, unless_exist: true, expires_in: 10.seconds)

      if !lock_acquired && data
        # Jika proses lain sedang menghitung, kembalikan data lama tanpa menunggu
        return data
      end

      begin
        start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)
        
        # Eksekusi blok mahal
        fresh_data = yield
        
        delta = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time
        target_expiry = Process.clock_gettime(Process::CLOCK_MONOTONIC) + ttl.to_f

        # Tulis secara pipelined / berurutan
        store.write(key, fresh_data, expires_in: ttl + 1.minute) # Tambahkan slack buffer
        store.write(meta_key, { delta: delta, expiry: target_expiry }, expires_in: ttl + 1.minute)

        fresh_data
      ensure
        store.delete("#{key}:__lock__") if lock_acquired
      end
    end
  end
end
```

#### 7.4 Observability Pipeline: Structured Logging & ActiveSupport Metric Exporter
File: `config/initializers/observability.rb`

```ruby
# frozen_string_literal: true

require "open_telemetry"

# Structured Semantic Logging
Rails.logger.formatter = proc do |severity, datetime, _progname, msg|
  current_span = OpenTelemetry::Trace.current_span
  trace_id = current_span.context.valid? ? current_span.context.hex_trace_id : "nil"
  span_id = current_span.context.valid? ? current_span.context.hex_span_id : "nil"

  log_entry = {
    timestamp: datetime.utc.iso8601(3),
    severity: severity,
    pid: Process.pid,
    thread_id: Thread.current.object_id.to_s(16),
    trace_id: trace_id,
    span_id: span_id,
    message: msg.is_a?(String) ? msg : msg.inspect
  }

  "#{log_entry.to_json}\n"
end

# Subscribe ke ActiveSupport::Notifications untuk SQL Metrics Extraction
ActiveSupport::Notifications.subscribe("sql.active_record") do |name, start, finish, id, payload|
  duration_ms = (finish - start) * 1000.0
  sql = payload[:sql].strip

  # Abaikan schema queries dan transactional booleans
  unless %w[SCHEMA EXPLAIN BEGIN COMMIT ROLLBACK].any? { |word| sql.start_with?(word) }
    if duration_ms > 250.0 # Slow query alert threshold
      Rails.logger.warn(
        event: "slow_query_detected",
        duration_ms: duration_ms.round(2),
        statement: sql,
        binds: payload[:type_casted_binds]&.call
      )
    end
  end
end
```

---

### 8. Real World Case Study: E-Commerce Flash Sale Architecture

#### Kasus Masalah
Perusahaan e-commerce skala besar di Asia Tenggara mengalami downtime berkala setiap event flash sale tanggal kembar (11.11, 12.12). 
*   **Beban Puncak**: 85.000 RPS pada route `/api/v1/campaigns/flash-sale`.
*   **Insiden**: Saat cache produk utama kedaluwarsa pada detik ke-00 jam promosi, ribuan thread secara bersamaan mengalami *cache miss* (*Cache Stampede*). 
*   Database PostgreSQL utama mengalami lonjakan koneksi (Postgres DB Max Connections tercapai = 5000), CPU Database mencapai 100%, IOPS EBS disk mengalami *throttling*, dan seluruh instance Puma mengalami connection pool starvation. 
*   Penggunaan memori worker meningkat hingga 2 GB per worker akibat alokasi ribuan *ActiveRecord instances*, memicu OOM (Out Of Memory) Killer pada pod Kubernetes.

#### Analisis Akar Masalah (Root Cause Analysis)
1. Fragmentasi Memori Akut: Linux allocator standar (`glibc`) menolak mengembalikan memori kotor dari payload JSON serialisasi besar ke sistem operasi.
2. Tidak adanya *anti-stampede locking* pada Rails cache: 85.000 thread berebut mengeksekusi query kompleks 5-way SQL join ke primary database.
3. Arsitektur Caching Naif: Tidak ada segregasi antara *shared cache* (Redis) dan *Edge CDN*. Request GET statis tidak memiliki kontrol validasi ETag yang terdistribusi.

#### Desain Solusi Skala Enterprise
1. **Memory Subsystem Upgrade**: Inject `libjemalloc.so.2` melalui `LD_PRELOAD` di seluruh image Docker, konfigurasi `MALLOC_CONF="dirty_decay_ms:1000,narenas:2"`.
2. **Penerapan XFetch Probabilistic Caching Engine**: Mencegah kedaluwarsa cache secara tiba-tiba di level backend. Jika masa kedaluwarsa mendekati 15 detik terakhir, worker pertama secara otomatis menghitung ulang di background; 84.999 request lainnya tetap membaca versi cache sebelumnya tanpa pernah menyentuh PostgreSQL.
3. **Edge Optimization**: Menambahkan edge caching via CDN dengan header:
   `Cache-Control: public, s-maxage=300, stale-while-revalidate=30`
   `Surrogate-Key: campaign-flash-sale`
   Ketika stok habis via event Kafka, Rails menembakkan asinkron Edge Purge API via gem `fastly-rails` hanya untuk surrogate key tersebut dalam tempo < 150 milidetik.

#### Metrik Hasil Transformasi

```
Metrik Performa             Sebelum Transformasi      Setelah Transformasi      Impact
--------------------------------------------------------------------------------------------------
P99 API Response Latency    4.850 ms                  12 ms                     99.75% Reduksi
PostgreSQL CPU Peak Load    100% (Crash)              14%                       Kapasitas Stabil
Puma Pod Memory Avg         2.1 GB (Memory Leak OOM)  540 MB (Datar)            74.2% Konservasi RAM
Edge Cache Hit Ratio        0%                        94.8%                     Offloading Origin
Maksimum RPS Terserap       12.000 RPS (Saturation)   120.000+ RPS              Peningkatan 10x
```

---

### 9. Trade-offs Architecture Matrix

| Strategi / Teknik | Trade-off: Performance | Trade-off: Latency | Trade-off: Scalability | Trade-off: Cost / Complexity |
| :--- | :--- | :--- | :--- | :--- |
| **Russian Doll View Caching** | Sangat Tinggi. CPU core web server terbebas dari rendering overhead. | Memangkas P50/P90 hingga < 5ms. P99 tetap bergantung latensi Redis. | Mendukung partisi Redis horizontal tanpa batasan horizontal pod scaling. | **Kompleksitas Tinggi**: Rentan query N+1 tersembunyi saat partial lookup jika data relasi tidak di-eager load secara manual. |
| **jemalloc Memory Allocator** | Tinggi. Mengurangi siklus CPU terbuang untuk sweep GC berulang. | Mengeliminasi spike latency sporadis akibat Stop-The-World GC. | Sangat Tinggi. Mengizinkan density worker per node 2x lipat lebih rapat. | **Rendah**: Cukup mengubah instalasi container OS dan environment variables. |
| **XFetch Anti-Stampede** | Optimal. Menghilangkan lonjakan beban spike ke relational database. | Flatline latency tanpa spike saat transisi rotasi cache. | Menjaga stabilitas throughput database pada traffic ekstrem (> 100K RPS). | **Sedang**: Tambahan memory Redis untuk menyimpan metadata komputasi delta dan kunci lock. |
| **Edge Surrogate CDN Caching** | Maksimal. Menghindari request menyentuh origin server Rails sama sekali. | Sub-milidetik (disajikan dari PoP terdekat dengan end-user). | Tak terbatas (menyerahkan scaling load ke backbone CDN). | **Biaya Tinggi**: Memerlukan infrastruktur CDN enterprise (Fastly/Akamai) dan sistem event-driven edge purge yang presisi. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Polusi Memori Akibat Cache Key Tanpa Versi Serializer
*Gejala*: Perubahan kode logic di View partial atau Serializer tidak terefleksi di user browser, atau aplikasi memicu error `ArgumentError: undefined class/method` saat melakukan deploy versi baru.
*Root Cause*: Cache key hanya menggunakan `[record.id, record.updated_at]`, tanpa memvalidasi SHA256 digest dari source code template (*ActionView template digest tree*).
*Solusi*: Gunakan helper `cache [record]` resmi dari ActionView daripada manual string keys, atau kombinasikan versi kode git release SHA ke dalam cache key global:

```ruby
# SALAH
Rails.cache.fetch("product_data_#{product.id}_#{product.updated_at.to_i}") { render_data }

# BENAR (Low Level)
RELEASE_VERSION = ENV.fetch("APP_GIT_COMMIT_SHA", "v1")
Rails.cache.fetch([RELEASE_VERSION, "product_data", product.cache_key_with_version]) { render_data }
```

#### Kesalahan 2: Connection Pool Starvation di Puma Multi-Thread
*Gejala*: Request gagal dengan log fatal: `ActiveRecord::ConnectionTimeoutError: could not obtain a connection from the pool within 5.000 seconds`.
*Root Cause*: Konfigurasi `RAILS_MAX_THREADS` pada Puma bernilai 16, tetapi PostgreSQL pool size pada `config/database.yml` diatur ke nilai default (5). Saat 16 thread bekerja simultan, 11 thread mati kutu menunggu koneksi DB yang kosong.
*Solusi*: Selaraskan connection pool minimal sama atau lebih besar dari jumlah thread Puma per worker:

```yaml
# config/database.yml
production:
  adapter: postgresql
  pool: <%= ENV.fetch("RAILS_MAX_THREADS") { 5 }.to_i + 2 %> # +2 Slack buffer untuk background jobs/actioncable
  checkout_timeout: 3.0
```

#### Kesalahan 3: Missing `touch: true` pada Skema Hirarki Mendalam
*Gejala*: Administrator memperbarui harga varian, tetapi halaman utama katalog produk tetap menyajikan harga diskon lama hingga hitungan minggu.
*Root Cause*: Model `Variant` tidak menyertakan opsi `touch: true` pada deklarasi relasi `belongs_to :product`.
*Troubleshooting Step*:
1. Periksa event log database: pastikan ada statement `UPDATE "products" SET "updated_at" = ... WHERE "products"."id" = ...` segera setelah varian disimpan.
2. Tambahkan assertion test case pada level model suite:

```ruby
test "updating variant touches parent product updated_at" do
  product = products(:valid_product)
  variant = product.variants.first
  
  assert_changes -> { product.reload.updated_at } do
    variant.update!(price_cents: 99_00)
  end
end
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Allocator**: Set LD_PRELOAD untuk mengaktifkan jemalloc di Dockerfile produksi:
  `ENV LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libjemalloc.so.2"`
- [ ] **Tuning GC Environment Variable**: Terapkan parameter RGenGC pada production orchestrator:
  *   `RUBY_GC_HEAP_INIT_SLOTS=1000000`
  *   `RUBY_GC_HEAP_FREE_SLOTS=500000`
  *   `RUBY_GC_HEAP_GROWTH_FACTOR=1.25`
  *   `RUBY_GC_MALLOC_LIMIT=64000000`
- [ ] **Redis Connection Pooling**: Selalu sertakan gem `connection_pool` saat menggunakan Redis Cache Store dan batasi timeout jaringan secara ketat (Connect: 500ms, Read: 200ms).
- [ ] **Anti-Stampede Guards**: Aktifkan `race_condition_ttl: 5.seconds` pada seluruh instance cache store terdistribusi.
- [ ] **Eager-Loading Audit**: Manfaatkan gem `bullet` pada CI pipeline untuk menggagalkan automated tests jika query N+1 terdeteksi dalam caching view template.
- [ ] **Compression Engine**: Validasi bahwa cache store menggunakan kompresi `zstd` untuk mencegah saturasi bandwidth antar server aplikasi dan cluster Redis.
- [ ] **Distributed Tracing**: Pastikan setiap log JSON menginjeksi metadata konteks trace (`trace_id` dan `span_id`) dari OpenTelemetry SDK.

---

### 12. Hands-on Practice: Membangun Production-Grade Observability & Anti-Stampede Engine

Simpan seluruh file praktikum di direktori repositori: `hands-on/m02/`

#### Langkah 1: Persiapan Lingkungan & Gemfile
Buat file `hands-on/m02/Gemfile`:

```ruby
# hands-on/m02/Gemfile
source "https://rubygems.org"
ruby ">= 3.2.0"

gem "rails", "~> 7.1.0"
gem "pg", "~> 1.5"
gem "puma", "~> 6.4"
gem "redis", "~> 5.1"
gem "connection_pool", "~> 2.4"
gem "zstandard", "~> 1.6"

# Observability Suite
gem "opentelemetry-api", "~> 1.2"
gem "opentelemetry-sdk", "~> 1.4"
gem "opentelemetry-instrumentation-all", "~> 0.50"
gem "opentelemetry-exporter-otlp", "~> 0.28"

group :development, :test do
  gem "memory_profiler", "~> 1.0"
  gem "derail_benchmarks", "~> 2.1"
end
```

Jalankan perintah instalasi dependency:
```bash
bundle config set path 'vendor/bundle'
bundle install
```

#### Langkah 2: Dockerfile dengan jemalloc Injection
Buat file `hands-on/m02/Dockerfile`:

```dockerfile
FROM ruby:3.2.2-slim-bullseye

# Install paket dasar sistem, postgres dev libraries, dan jemalloc
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev \
      libjemalloc2 \
      curl && \
    rm -rf /var/lib/apt/lists/*

# Konfigurasi LD_PRELOAD global untuk menggunakan jemalloc
ENV LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libjemalloc.so.2"
ENV MALLOC_CONF="dirty_decay_ms:1000,narenas:2"

WORKDIR /rails
COPY Gemfile Gemfile.lock ./
RUN bundle install

COPY . .

EXPOSE 3000
CMD ["bundle", "exec", "puma", "-C", "config/puma.rb"]
```

#### Langkah 3: Setup Profiling Rake Task Menggunakan Memory Profiler
Buat file `hands-on/m02/lib/tasks/profile_memory.rake`:

```ruby
# hands-on/m02/lib/tasks/profile_memory.rake
require "memory_profiler"

namespace :perf do
  desc "Audit memory allocation profiling for complex serialization"
  task profile_allocations: :environment do
    puts "Starting allocations audit..."

    # Buat sampel data tiruan di memory
    Product.transaction do
      100.times do |i|
        p = Product.create!(
          title: "Enterprise Product #{i}",
          description: "High performance memory footprint test scenario",
          price_cents: 500_00
        )
        5.times { |v| p.variants.create!(sku: "SKU-#{i}-#{v}", price: 50.0, stock_count: 10) }
      end
    end

    report = MemoryProfiler.report do
      # Blok kode yang akan dievaluasi alokasinya
      products = Product.includes(:variants).limit(100).to_a
      
      # Simulasi rendering representasi JSON
      payload = products.map do |prod|
        {
          id: prod.id,
          title: prod.title,
          variants: prod.variants.map { |v| { sku: v.sku, price: v.price } }
        }
      end.to_json
    end

    # Tampilkan laporan metrik alokasi
    report.pretty_print(scale_bytes: true)
  end
end
```

Eksekusi profiling dengan command:
```bash
bundle exec rake perf:profile_allocations
```

---

### 13. Latihan (Exercises)

#### Level Easy
Konfigurasikan caching fragmen sederhana pada partial `app/views/shared/_navbar.html.erb` yang membaca data *current user* dan *menu links*. Cache fragment ini harus otomatis invalidasi ketika objek user mengubah atribut `role` atau avatar-nya.
*Instruksi*: Tuliskan kode partial ERB dengan cache key komposit yang menyertakan atribut penanda validitas tersebut.

#### Level Medium
Buat sebuah custom Rack Middleware `hands-on/m02/app/middleware/query_budget_guard.rb`. Middleware ini harus memanfaatkan `ActiveSupport::Notifications` untuk menghitung total query SQL yang dieksekusi pada siklus sebuah HTTP request. Jika sebuah controller mengeksekusi lebih dari 30 query SQL dalam single request pada lingkungan `staging`/`test`, kembalikan HTTP response `429 Unprocessable Entity` disertai header `X-Query-Count` dan rincian query log sebagai warning.

#### Level Hard
Rancang dan implementasikan class `TieredCacheStore` yang mengombinasikan **L1 Cache (In-Memory `ActiveSupport::Cache::MemoryStore`)** pada memory pod lokal, dan **L2 Cache (Distributed `ActiveSupport::Cache::RedisCacheStore`)**. 
Spesifikasi implementasi:
1. Pembacaan selalu mencoba mengakses L1 terlebih dahulu (latensi < 100 mikrosekon).
2. Jika L1 Miss, baca L2 (Redis). Jika L2 Hit, isi L1 lokal dengan TTL pendek (10 detik) untuk memitigasi round-trip jaringan.
3. Penulisan dan Invalidasi harus terpropagasi sinkron ke L2, serta mengumumkan invalidasi L1 ke pod-pod aplikasi lain melalui Redis Pub/Sub topic `cache_invalidation_channel`.

---

### 14. Tantangan Rekayasa Sistem (Engineering Challenge)

#### Skenario: Arsitektur Zero-Downtime Cache Warm-Up & Anti-Dogpiling untuk 500K RPS Flash Sale
Anda memegang peran sebagai Lead Infrastructure Architect untuk platform tiket konser kelas dunia. Penjualan tiket untuk superstar internasional akan dibuka serentak tepat pukul 10:00:00 WIB. Sistem diperkirakan menerima lonjakan 500.000 RPS seketika pada halaman endpoint `/events/world-tour-2026`.

#### Batasan Arsitektural:
1. Tidak ada toleransi query ke PostgreSQL pada 5 menit pertama flash sale untuk operasi read. Database primary hanya dialokasikan khusus menangani transaksi checkout (booking order & payment write-state).
2. Format data inventaris tiket berubah setiap detik (stok berkurang cepat saat antrean checkout bergerak).
3. Pod worker Rails bersifat dinamis (dapat di-scale-out oleh Horizontal Pod Autoscaler dari 50 pod menjadi 300 pod secara instan).
4. Edge CDN tidak boleh menyajikan data stok palsu yang sudah kedaluwarsa lebih dari 3 detik (Strict Latency Bound).

#### Tugas Anda:
1. Susun dokumen arsitektur komprehensif yang merancang alur pipeline data:
   *   Mekanisme pre-warming Redis cluster sebelum jam 10:00:00 tanpa menyebabkan OOM.
   *   Desain state sync: Bagaimana state database PostgreSQL yang berubah secara cepat dipropagasikan ke Redis tanpa overhead query polling.
   *   Spesifikasi integrasi HTTP Caching (Edge-Worker Handshake): Konfigurasi header CDN (`stale-while-revalidate`, `stale-if-error`), locking primitives, serta algoritma proteksi cache invalidation cascade.
2. Tuliskan kode modul Ruby/Rails pendukung implementasi ini (State Engine & Cache Synchronization Manager) yang tahan terhadap fragmentasi memori dan kegagalan partisi jaringan (*network split-brain*).

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Apa fungsi parameter `touch: true` pada relasi `belongs_to` dalam konteks Russian Doll Caching?
2. Mengapa alokator default sistem Linux (`glibc`) cenderung menyebabkan *memory bloat* pada aplikasi Rails yang menjalankan web server multi-threaded Puma?
3. Sebutkan perbedaan utama fungsionalitas antara directive HTTP Cache `Cache-Control: no-cache` dan `Cache-Control: no-store`!
4. Pada layer arsitektur apa event yang didefinisikan lewat `ActiveSupport::Notifications.instrument` dieksekusi: *asynchronous via background queue* atau *synchronous in-thread*?
5. Mengapa serializer bawaan Ruby `Marshal` berisiko jika digunakan untuk membaca payload cache eksternal yang diakses lintas versi rilis aplikasi?

#### 5 Pertanyaan Intermediate
6. Bagaimana cara kerja opsi `race_condition_ttl` pada `ActiveSupport::Cache::Store` untuk meredam thundering herd problem?
7. Mengapa kompresi payload cache dengan algoritma Zstandard (zstd) lebih dianjurkan untuk Redis dibanding Gzip pada lingkungan high-throughput?
8. Bagaimana implementasi metode `stale?` pada ActionController menghemat utilisasi CPU server dan bandwidth egress jaringan secara bersamaan?
9. Apa dampak buruk dari eksekusi `GC.start` secara manual di dalam controller action terhadap performa aplikasi Rails multi-threaded?
10. Bagaimana format JSON Structured Logging berkontribusi terhadap proses incident response pada sistem distributed tracing APM?

#### 3 Skenario Kasus Produksi
11. **Kasus 1**: Pada dashboard metrik Grafana, nilai alokasi memori RSS (*Resident Set Size*) pod Puma Anda naik secara konstan berbentuk gergaji (linearly increasing) dari 300MB hingga mencapai batas limit pod 2GB dalam kurun waktu 12 jam, sebelum akhirnya mati di-kill oleh OS OOM Killer. Namun, saat dieksekusi `GC.start` melalui Rails console pada pod yang sama, memori yang terpakai tidak berkurang sama sekali. Komponen mana yang bocor dan bagaimana langkah troubleshooting terstrukturnya?
12. **Kasus 2**: Sebuah API endpoint katalog produk membaca fragment cache Redis. Terjadi anomali di mana latency P99 melonjak dari 15ms menjadi 3.500ms secara berkala setiap 1 jam sekali tepat pada menit ke-00. Metrik IOPS CPU Redis melonjak tajam dan bandwidth transfer jenuh. Apa diagnosis Anda terhadap penyebab insiden periodik ini dan bagaimana solusinya?
13. **Kasus 3**: Anda memimpin migrasi aplikasi monolit Rails ke arsitektur Kubernetes multi-region. Ditemukan bahwa subscriber `ActiveSupport::Notifications` yang mengirim trace metrik ke Datadog/Prometheus menyebabkan throughput request HTTP turun sebesar 35%. Analisis akar permasalahannya dan jelaskan desain ulang pipeline pengiriman metrik tersebut!

---

### 16. Rangkuman Materi Pokok (Summary)

1. **Efisiensi Alokator & Runtime Memori**: Mengganti alokator sistem bawaan dengan **jemalloc** adalah langkah fundamental tanpa perubahan kode logic yang secara drastis memitigasi fragmentasi memori Linux pada server Puma multi-thread. Penyetelan RGenGC melalui environment variables menstabilkan latensi P99 dengan meminimalkan frekuensi *Stop-The-World full GC sweeps*.
2. **Topologi Caching Berlapis (Multi-Tier Caching)**: Membangun sistem caching berkinerja tinggi membutuhkan kombinasi **Russian Doll Caching** pada level tampilan, mitigasi stampede menggunakan algoritma cerdas (**XFetch / `race_condition_ttl`**) pada layer Redis, serta pendelegasian otentikasi data statis ke **Edge Network (CDN)** via conditional headers (`ETag`, `Surrogate-Keys`).
3. **Observability sebagai Desain Fondasional**: Observability pada ekosistem Rails modern tidak lagi mengandalkan teks log konvensional yang diparsing regex. Standar produksi enterprise menuntut instrumentasi presisi via **ActiveSupport::Notifications**, terintegrasi ke spesifikasi terbuka **OpenTelemetry**, serta logging berformat **Structured JSON** yang menyematkan metadata trace context secara terdistribusi.
4. **Resiliensi Caching**: Cache store tidak boleh menjadi *Single Point of Failure* (SPOF). Pustaka cache harus dibungkus dengan konfigurasi connection pool yang presisi, batas waktu koneksi agresif (sub-detik), *fallback graceful error handlers*, dan kompresi payload berkecepatan tinggi (**zstandard**) guna menjaga ketersediaan layanan sistem perbankan dan transaksi skala masif.