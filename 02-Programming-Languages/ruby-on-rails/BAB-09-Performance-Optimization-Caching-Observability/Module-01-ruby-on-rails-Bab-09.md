# SEKSI 01 — IDENTITAS MODUL

*   **Modul:** Bab 09 Module 01 — *Performance Optimization, Caching & Observability*
*   **Track:** 02-Programming-Languages / Ruby on Rails
*   **Tingkat Kesulitan:** Advanced / Senior Engineering
*   **Prasyarat:** Pemahaman mendalam tentang Rails MVC, ActiveRecord Query Interface, Rack Middleware Pipeline, concurrency model Puma (Process vs. Thread), serta arsitektur database relasional (PostgreSQL/MySQL).
*   **Estimasi Waktu:** 8 - 10 Jam Pembelajaran Mandiri & Hands-on Lab
*   **Ekosistem Teknologi:** Ruby 3.3+ (YJIT enabled), Rails 7.1/7.2, Redis 7+, Solid Cache, OpenTelemetry SDK, Lograge, PostgreSQL 15+.

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1.  **Mendiagnosis dan Mengeliminasi Database Bottlenecks:** Menganalisis *allocation profiling*, mendeteksi N+1 queries, membedakan mekanisme internal antara `preload`, `eager_load`, dan `includes`, serta mengimplementasikan *strict loading* dan *counter caches*.
2.  **Mengarsitekturi Multi-Tier Caching:** Mengimplementasikan strategi *Russian Doll Caching* berbasis `cache_key_with_version`, memanfaatkan *Low-Level Caching* dengan proteksi *race condition*, dan memilih cache store yang tepat (Redis vs. Solid Cache).
3.  **Mengoptimalkan Runtime Ruby & Concurrency:** Mengonfigurasi Ruby Garbage Collection (RGenGC) dan Ruby 3.3 YJIT (*Yet Another Ruby JIT*), menyelaraskan rasio *Puma workers/threads* dengan ukuran *ActiveRecord database connection pool*.
4.  **Membangun Sistem Observabilitas Komprehensif:** Mengintegrasikan telemetry berbasis OpenTelemetry, mengonversi log Rails ke format JSON terstruktur via Lograge, serta mengekspor metrik latensi p95/p99 ke sistem monitoring produksi.
5.  **Mencegah Degenerasi Kinerja Ekstrem:** Memitigasi anomali skala besar seperti *Cache Stampede* (Dogpiling), kebocoran memori akibat retensi objek ActiveRecord, dan *cache churn*.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa sistem berkinerja tinggi, optimasi bukanlah sekadar kumpulan trik sintaksis; optimasi adalah disiplin saintifik berbasis data kuantitatif (*Mechanical Sympathy*).

```
          [ HUKUM KINERJA SISTEM ]
  "Premature optimization is the root of all evil"
                   vs.
  "Unmeasured architecture is the root of bankruptcy"
```

### 1. Hukum Amdahl (Amdahl's Law)
Peningkatan kecepatan sistem secara keseluruhan dibatasi oleh bagian program yang tidak dapat diparalelkan atau tidak dapat di-cache. Mengurangi durasi eksekusi Ruby dari 5ms ke 2ms pada endpoint yang menghabiskan 250ms di PostgreSQL hanya memberikan peningkatan marjinal (< 1.2%). Prioritaskan optimasi pada segmen dengan latensi terlama (biasanya I/O bound).

### 2. Mental Model: *Data Path vs. Allocation Path*
Setiap alokasi objek Ruby membebani *Garbage Collector* (GC). Di sistem ber-throughput tinggi (misal: 5.000 RPS), mengalokasikan 10.000 objek ActiveRecord per request memicu *GC mark-and-sweep* terus-menerus, memblokir eksekusi thread (*stop-the-world pauses*). Kunci kinerja Rails bukan hanya seberapa cepat kode dieksekusi, melainkan **seberapa sedikit alokasi memori yang diciptakan untuk menyelesaikan suatu operasi**.

### 3. Mental Model Caching: *State Invalidation Hierarchy*
Cache bukanlah penyimpanan permanen, melainkan *ephemeral memoization* dari hasil komputasi mahal. Jangan membuat mekanisme invalidasi cache manual yang kompleks (*imperative invalidation*). Gunakan *key-based expiration* deklaratif: saat data model berubah, kunci cache berubah secara otomatis, mengabaikan data lama tanpa memerlukan aksi `DELETE` eksplisit.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram aliran request end-to-end melalui lapisan optimasi, caching, dan instrumentasi observabilitas:

```
[ Client Request ]
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. EDGE / REVERSE PROXY LAYER (Cloudflare / NGINX)          │
│    - HTTP Conditional GET (ETag / Last-Modified)            │
│    - Status 304 Not Modified -> Early Exit                 │
└──────────────────────────────┬──────────────────────────────┘
                               │ Cache Miss / Expired
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. RACK MIDDLEWARE & INSTRUMENTATION PIPELINE               │
│    - OpenTelemetry Rack Tracer (Context Propagation)        │
│    - Rack::Deflater / Rack::Attack                          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. RAILS ACTION CONTROLLER                                  │
│    - `fresh_when` / `stale?` Verification                   │
│    - Puma Worker/Thread Hand-off                            │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
     Cache Hit │                    Cache Miss│
               │                              ▼
               │              ┌───────────────────────────────┐
               │              │ 4. ACTIVE RECORD QUERY LAYER  │
               │              │    - Strict Loading Check     │
               │              │    - Query Cache (In-Memory)  │
               │              │    - Database Connection Pool │
               │              └───────────────┬───────────────┘
               │                              │
               │                              ▼
               │              ┌───────────────────────────────┐
               │              │ 5. DATABASE (PostgreSQL)      │
               │              │    - B-Tree Index Scan        │
               │              │    - Eager Loaded Joins       │
               │              └───────────────┬───────────────┘
               │                              │ Data Materialized
               ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. VIEW LAYER: RUSSIAN DOLL CACHING                         │
│    - Outer Fragment (Category) [Key v2]                     │
│      └─ Inner Fragment (Product #42) [Key v1.3]             │
│    - Cache Store: Redis 7.0 / Solid Cache (Disk/DB)         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. RESPONSE & TELEMETRY DISPATCH                            │
│    - Lograge JSON Payload Emission                          │
│    - ActiveSupport::Notifications -> OpenTelemetry Exporter │
└─────────────────────────────────────────────────────────────┘
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi `ActiveSupport::Cache::Store`
Rails menyediakan abstraksi seragam untuk caching. Format internal penyimpanan kunci Rails terdiri dari:
`views/[template_digest]/[model_name]/[model_id]-[timestamp]`

```ruby
# Bentuk dasar kompilasi cache key Rails
record = Product.find(1)
record.cache_key_with_version
# => "products/1-20231024103000123456"
#     └─ Name ─┘└ID┘ └─ Updated_at Nano ─┘
```

Ketika model di-update via touch atau save:
1. Kolom `updated_at` berubah di PostgreSQL.
2. `cache_key_with_version` menghasilkan hash string baru.
3. Operasi pembacaan cache (`read`) berikutnya mencari kunci baru ini. Kunci lama ditinggalkan (*abandoned*) dan dievakuasi oleh algoritma cache eviction (misal: LRU/LFU di Redis atau retention trimming di Solid Cache).

### 2. Mekanisme Internal ActiveRecord Query Loading
Pahami perbedaan fundamental tiga strategi pemuatan asosiasi:

*   **`preload`**: Menjalankan *selalu* 2 query SQL terpisah (`SELECT * FROM posts`, dilanjutkan `SELECT * FROM comments WHERE post_id IN (...)`). Tidak memungkinkan filter `WHERE` pada tabel asosiasi.
*   **`eager_load`**: Memaksa penggunaan 1 query raksasa via `LEFT OUTER JOIN`. Semua kolom dimuat ke memori, kemudian Rails menginstansiasi objek dan mengasosiasikannya di memori Ruby. Mahal dalam alokasi memori jika record anak sangat banyak.
*   **`includes`**: Bertindak sebagai *query planner*. Secara default menggunakan strategi `preload`. Namun, jika ada klausul `.where("comments.approved = true").references(:comments)`, Rails secara otomatis mengalihkan strateginya ke `eager_load`.

```
                  ┌───────────────────────┐
                  │ Product.includes(...) │
                  └───────────┬───────────┘
                              │
               Ada klausul .where / .order
               pada tabel relasi?
                             / \
                           Ya   Tidak
                           /     \
                          ▼       ▼
           [ eager_load ]           [ preload ]
         (LEFT OUTER JOIN)     (Dua Query Terpisah)
```

### 3. ActiveSupport::Notifications Engine
Jantung dari observabilitas Rails adalah *instrumentation bus* berbasis `ActiveSupport::Notifications`. Ketika Rails menjalankan query SQL, merender partial, atau memproses request controller, ia memicu *event*:

```ruby
ActiveSupport::Notifications.instrument("sql.active_record", payload) do
  # Operasi database yang dipantau
end
```

Subscriber mendaftarkan listener ke event channel ini tanpa memodifikasi kode inti (Observer Pattern non-intrusif), memotong dependensi langsung antara domain logik dan tracing tool.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Russian Doll Caching & Nesting Dynamics
Strategi fragment caching dua tingkat atau lebih di mana partial dalam bersarang di dalam partial luar. Masalah terbesar caching adalah dependensi cascading: jika record anak berubah, fragmen induk harus diperbarui.

Solusinya adalah mekanisme **`touch: true`** pada asosiasi ActiveRecord:

```ruby
class Review < ApplicationRecord
  belongs_to :product, touch: true
end

class Product < ApplicationRecord
  has_many :reviews
end
```

Saat review baru disimpan, `touch: true` secara otomatis meng-update kolom `updated_at` pada `Product`. Hal ini menginvalidasi cache fragment `Product` (kunci luar), tetapi semua fragmen review lainnya (kunci dalam yang tidak berubah) **tetap dipertahankan (Cache Hit)**.

### 2. Mitigasi Cache Stampede: Race Condition TTL
Ketika sebuah cache key dengan komputasi mahal kedaluwarsa pada traffic tinggi (100 req/sec), 100 thread yang berjalan simultan mendapati *cache miss*. Keseluruhan 100 thread tersebut akan mengeksekusi query database mahal secara bersamaan, memicu *CPU exhaustion* atau *connection pool starvation*.

Rails memitigasi ini menggunakan parameter `race_condition_ttl`:

```ruby
Rails.cache.fetch("expensive_metric", expires_in: 1.hour, race_condition_ttl: 10.seconds) do
  CalculateComplexAnalyticsJob.run
end
```

**Mekanisme Internal:** Saat cache dianggap expired, thread pertama yang masuk memperpanjang metadata waktu kadaluwarsa kunci sebesar 10 detik secara atomik di storage, kemudian menjalankan blok kode. 99 thread lainnya yang masuk beberapa milidetik setelahnya akan menerima data lama (*stale data*) sementara proses komputasi berlangsung di thread pertama.

### 3. Ruby 3.3 YJIT & Concurrency Memory Model
YJIT (*Yet Another Just-In-Time Compiler*) beroperasi dengan teknik *Basic Block Versioning* (BBV). YJIT mengompilasi instruksi virtual machine (YARV bytecode) menjadi instruksi mesin native secara bertahap saat metode dipanggil berulang kali.

*   **Puma Architecture:** Master process menjalankan booting Rails, memuat kode aplikasi ke memori, kemudian melakukan `fork()` ke sejumlah Puma Workers.
*   **Copy-on-Write (CoW):** Memori fisik dibagi bersama antar worker. Namun, jika Garbage Collector memodifikasi flag objek (mark-and-sweep), halaman memori kotor (*dirty pages*) terduplikasi, menghilangkan efisiensi CoW. Ruby compaction algorithm (`GC.compact`) dijalankan sebelum proses forking untuk meminimalkan fragmentasi memori.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Contoh implementasi optimasi query, low-level caching dengan locking, dan eliminasi N+1 menggunakan `strict_loading`.

```ruby
# app/models/order.rb
class Order < ApplicationRecord
  belongs_to :customer
  has_many :order_items, inverse_of: :order
  has_many :products, through: :order_items

  # Mencegah lazy loading yang memicu N+1 di layer view/service
  self.strict_loading_by_default = true

  scope :recent_optimized, -> {
    strict_loading(false) # Override eksplisit jika scope mengelola pemuatannya sendiri
      .preload(:customer, order_items: :product)
      .where("created_at >= ?", 30.days.ago)
      .order(created_at: :desc)
  }
end

# app/services/order_analytics_service.rb
class OrderAnalyticsService
  CACHE_VERSION = "v1"

  def initialize(customer_id)
    @customer_id = customer_id
  end

  def total_revenue
    cache_key = "customers/#{@customer_id}/revenue_stats:#{CACHE_VERSION}"

    Rails.cache.fetch(cache_key, expires_in: 30.minutes, race_condition_ttl: 5.seconds) do
      # Kalkulasi agregasi langsung via database SQL, hindari instansiasi ActiveRecord
      Order.strict_loading(false)
           .where(customer_id: @customer_id)
           .joins(:order_items)
           .sum("order_items.quantity * order_items.unit_price")
    end
  end
end
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis dari implementasi kode di Seksi 07:

1.  `self.strict_loading_by_default = true`:
    *   Mengaktifkan proteksi runtime engine. Jika sebuah association diakses di controller atau template tanpa di-load di query awal (misal: `order.customer.name` tanpa `preload(:customer)`), Rails akan langsung melempar exception `ActiveRecord::StrictLoadingViolatedError` alih-alih mengeksekusi query database tambahan.
2.  `scope :recent_optimized, -> { ... }`:
    *   `.strict_loading(false)`: Mematikan proteksi strict loading khusus pada query ini karena developer telah mendefinisikan strategi fetching secara presisi.
    *   `.preload(:customer, order_items: :product)`: Menjalankan 3 query terpisah dengan alokasi minimal:
        1. `SELECT * FROM orders WHERE ...`
        2. `SELECT * FROM customers WHERE id IN (...)`
        3. `SELECT * FROM order_items WHERE order_id IN (...)`
        4. `SELECT * FROM products WHERE id IN (...)`
        Ini mencegah penggunaan `JOIN` raksasa yang membebani memori Ruby.
3.  `CACHE_VERSION = "v1"`:
    *   Bertindak sebagai *schema identifier* cache. Jika rumus komputasi diubah (misalnya ditambahkan diskon atau pajak), kita cukup menaikkan versi menjadi `"v2"`, menginvalir seluruh cache secara instan (*key mutation*).
4.  `Rails.cache.fetch(cache_key, expires_in: 30.minutes, race_condition_ttl: 5.seconds)`:
    *   Mengecek eksistensi kunci di store. Jika ada dan valid, langsung mengembalikan nilainya.
    *   Jika kedaluwarsa, parameter `race_condition_ttl` mengamankan database dari serbuan ribuan concurrency requests dengan memberikan toleransi 5 detik bagi thread pertama untuk memperbarui cache.
5.  `.joins(:order_items).sum("order_items.quantity * order_items.unit_price")`:
    *   Optimasi komputasi: Agregasi dilakukan langsung di dalam engine database melalui satu perintah `SUM()`. Tidak ada model Ruby atau array objek yang dialokasikan ke heap memory Ruby.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Flash-Sale E-Commerce API & SSR Degradation
Sebuah platform e-commerce berbasis Rails meluncurkan event penjualan kilat (*Flash Sale*). Karakteristik beban:
*   Trafik melonjak dari 150 RPS ke 8.500 RPS dalam 30 detik.
*   Spesifikasi endpoint: Katalog Produk per Kategori beserta status stok, review agregat, dan varian.
*   **Gejala Kegagalan:** Response time p99 melonjak dari 45ms ke 12.000ms. CPU server database PostgreSQL mencapai 100%, pool koneksi database exhausted (`ActiveRecord::ConnectionTimeoutError`). Memori server Puma melonjak hingga OOM (Out Of Memory) killed oleh kernel Linux.

### Akar Masalah:
1.  **N+1 Query Masif:** Template merender list produk di mana setiap item melakukan query tambahan untuk varian dan rating review.
2.  **Uncached Serialization:** Setiap request memicu serialisasi JSON berulang dari 100 objek ActiveRecord yang sama.
3.  **ActiveRecord Allocation Churn:** Penggunaan RAM meledak karena 8.500 thread aktif mencoba menginstansiasi puluhan ribu objek Ruby secara bersamaan, memicu GC compaction stall.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut solusi komprehensif skala produksi untuk mengatasi insiden pada Seksi 09:

### 1. Database Migration: Counter Cache & Indeks Komposit

```ruby
# db/migrate/20231024000001_add_performance_optimizations_to_products.rb
class AddPerformanceOptimizationsToProducts < ActiveRecord::Migration[7.1]
  def change
    add_column :products, :reviews_count, :integer, default: 0, null: false
    add_column :products, :average_rating, :decimal, precision: 3, scale: 2, default: 0.0

    # Indeks komposit covering query katalog
    add_index :products, [:category_id, :status, :created_at], 
              name: "idx_products_catalog_perf"
  end
end
```

### 2. Model: Touch Invalidation, Counter Cache & Strict Associations

```ruby
# app/models/review.rb
class Review < ApplicationRecord
  belongs_to :product, touch: true, counter_cache: true

  after_commit :recalculate_product_rating, on: [:create, :update, :destroy]

  private

  def recalculate_product_rating
    # Menggunakan update_columns untuk bypass callback demi menghindari looping update
    avg = product.reviews.average(:rating).to_f.round(2)
    product.update_columns(average_rating: avg, updated_at: Time.current)
  end
end

# app/models/product.rb
class Product < ApplicationRecord
  belongs_to :category, touch: true
  has_many :variants, dependent: :destroy
  has_many :reviews, dependent: :destroy

  enum :status, { draft: 0, active: 1, archived: 2 }

  # Skema cache digest yang unik untuk payload serialisasi
  def catalog_cache_key
    "product:#{id}:#{updated_at.to_fs(:usec)}"
  end
end
```

### 3. Controller: HTTP Caching & Eager Loading Orchestration

```ruby
# app/controllers/catalog_controller.rb
class CatalogController < ApplicationController
  def show
    @category = Category.find(params[:id])

    # 1. HTTP CONDITIONAL CACHING (ETag / 304 Not Modified)
    # Jika browser/CDN memiliki ETag yang cocok dengan category.updated_at, eksekusi berhenti di sini
    return if stale?(etag: @category, last_modified: @category.updated_at, public: true)

    # 2. QUERY OPTIMIZATION MENGGUNAKAN PRELOAD DENGAN KONDISI STRICT
    @products = @category.products
                         .active
                         .strict_loading
                         .preload(:variants)
                         .order(created_at: :desc)
                         .limit(50)

    respond_to do |format|
      format.html
      format.json { render json: cached_catalog_json }
    end
  end

  private

  def cached_catalog_json
    # Low-level cache untuk response JSON
    cache_key = "category_json:#{@category.id}:#{@category.updated_at.to_fs(:usec)}"
    
    Rails.cache.fetch(cache_key, expires_in: 1.hour, race_condition_ttl: 10.seconds) do
      @products.map do |product|
        {
          id: product.id,
          name: product.name,
          rating: product.average_rating,
          review_count: product.reviews_count,
          variants: product.variants.map { |v| { id: v.id, sku: v.sku, price: v.price.to_s } }
        }
      end.to_json
    end
  end
end
```

### 4. View: Russian Doll Caching Implementation

```erb
<%# app/views/catalog/show.html.erb %>
<%# Kunci Fragmen Terluar: Berdasarkan Category Digest %>
<% cache ["catalog_view_v1", @category] do %>
  <div class="category-header">
    <h1><%= @category.name %></h1>
    <p>Last Updated: <%= @category.updated_at %></p>
  </div>

  <div class="products-grid">
    <% @products.each do |product| %>
      <%# Kunci Fragmen Terdalam: Otomatis menggunakan Product#cache_key_with_version %>
      <% cache product do %>
        <div class="product-card" id="product-<%= product.id %>">
          <h2><%= product.name %></h2>
          <div class="rating-badge">★ <%= product.average_rating %> (<%= product.reviews_count %> reviews)</div>
          
          <ul class="variants-list">
            <% product.variants.each do |variant| %>
              <li><%= variant.sku %> - $<%= variant.price %></li>
            <% end %>
          </ul>
        </div>
      <% end %>
    <% end %>
  </div>
<% end %>
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### 1. Evaluasi Komparatif Rails Cache Stores

| Parameter Evaluasi | MemoryStore | RedisCacheStore | Solid Cache |
| :--- | :--- | :--- | :--- |
| **Arsitektur Penyimpanan** | RAM (In-process memory) | RAM (External dedicated process) | RDBMS (Disk-backed via PostgreSQL/MySQL/SQLite) |
| **Throughput / Latency** | Ultra Fast (< 0.1ms) | Very Fast (0.5ms - 2ms) | Moderate (2ms - 10ms) |
| **Kapasitas Skala** | Sangat Rendah (terbatas RAM proses) | Menengah (Dibatasi RAM server) | Sangat Besar (Terbatas kapasitas SSD/NVMe) |
| **Biaya Operasional ($)**| Rendah (Included) | Tinggi (Dedicated Redis Cluster) | Sangat Rendah (Memanfaatkan storage database) |
| **Cross-Process Sharing**| Tidak (Terisolasi per worker) | Ya (Shared cluster-wide) | Ya (Shared cluster-wide) |
| **Kasus Penggunaan Terbaik** | Testing, single-process apps | Low-latency mission critical sessions | Fragment caching masif berbiaya rendah |

### 2. Perbandingan Strategi Pemuatan Asosiasi ActiveRecord

| Kriteria | `preload` | `eager_load` | `joins` |
| :--- | :--- | :--- | :--- |
| **Strategi SQL** | $N+1$ query terpisah ($1 + \text{jumlah relasi}$) | Single query raksasa via `LEFT OUTER JOIN` | Single query via `INNER JOIN` |
| **Memori Heap Ruby** | Optimal (Record dialokasikan per baris asli) | Cenderung Boros (Duplikasi baris join di-instansiasi) | Minimal (Hanya record tabel utama yang di-instansiasi) |
| **Filter Kolom Relasi** | ❌ Gagal (`WHERE` pada relasi akan error) | ✅ Berhasil (Mendukung `WHERE` pada tabel anak) | ✅ Berhasil (Hanya untuk filtering data) |
| **Akses Data Asosiasi** | ✅ Aman dari query tambahan | ✅ Aman dari query tambahan | ❌ Memicu N+1 jika asosiasi dipanggil di view |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Serialization Overhead pada Low-Level Caching
**Jebakan:** Menyimpan seluruh array objek ActiveRecord yang besar secara langsung ke dalam Redis cache store:
```ruby
# PITFALL: Jangan lakukan ini!
Rails.cache.write("active_users", User.where(active: true).to_a)
```
**Mengapa Bahaya?** Ruby harus menjalankan `Marshal.dump` saat penulisan dan `Marshal.load` saat pembacaan. Proses de-serialisasi ribuan objek ActiveRecord membakar CPU dan menciptakan ribuan alokasi objek baru di heap Ruby, meniadakan manfaat latensi dari caching itu sendiri.
**Solusi:** Cache data dalam bentuk murni: primitif ID array, serialisasi string JSON, atau hash murni (`.pluck` / `.as_json`).

### 2. Cache Churn Akibat Polimorfisme Waktu
**Jebakan:** Menyertakan nilai yang terus berubah dinamis ke dalam kunci cache:
```ruby
# PITFALL: Cache Churn Generator
<% cache ["user_dashboard", current_user, Date.current] do %>
```
Saat pergantian hari tiba (pukul 00:00 UTC), seluruh kunci cache di server menjadi usang seketika. Hal ini memicu lonjakan beban masif secara mendadak ke database (*Cache Invalidation Cascade*).

### 3. Database Connection Pool Exhaustion vs. Puma Threads
Jika Puma dikonfigurasi dengan:
`threads_count = 16`
Dan konfigurasi `database.yml` memiliki:
`pool: 5`
Di bawah beban tinggi, thread ke-6 hingga ke-16 yang mencoba melakukan query database akan diblokir selama durasi `checkout_timeout` (default 5 detik), kemudian melemparkan error fatal `ActiveRecord::ConnectionTimeoutError`.

**Aturan Emas:** `pool size` minimal harus selalu sama dengan jumlah Puma `max_threads` per worker:
$$\text{Pool Size} \ge \text{Puma Max Threads}$$

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Pemanggilan `.count` pada Koleksi yang Sudah Dimuat
*   *Bad:*
    ```ruby
    # View Template
    <span>Total Items: <%= @order.order_items.count %></span>
    ```
    *Dampak:* `.count` selalu memicu query SQL baru: `SELECT COUNT(*) FROM order_items WHERE ...`, mengabaikan koleksi `@order.order_items` yang sudah dimuat ke memori via eager loading.
*   *Good:*
    ```ruby
    <span>Total Items: <%= @order.order_items.size %></span>
    ```
    *Mekanisme:* `.size` bertindak cerdas: jika asosiasi sudah dimuat di memori, ia menghitung elemen array Ruby secara lokal tanpa query database. Jika belum dimuat, barulah ia menjalankan `COUNT(*)`.

### 2. Mengabaikan Penggunaan `touch: true` pada Hierarki Bersarang
*   *Bad:*
    ```ruby
    class Comment < ApplicationRecord
      belongs_to :post # Tanpa touch: true
    end
    ```
    *Dampak:* Mengedit komentar tidak akan mengupdate `updated_at` pada model `Post`. Akibatnya, fragment cache `Post` di view tetap menampilkan data komentar lama, menyebabkan data tampil basi tanpa batas waktu.
*   *Good:*
    ```ruby
    class Comment < ApplicationRecord
      belongs_to :post, touch: true
    end
    ```

### 3. Terjadi N+1 Query pada Method Turunan (Virtual Attributes)
*   *Bad:*
    ```ruby
    class User < ApplicationRecord
      def full_address
        "#{street}, #{city.name}" # Memanggil relasi city
      end
    end
    # Controller: User.all.each { |u| puts u.full_address }
    ```
    *Dampak:* Meskipun `User.all` dipanggil, pemanggilan `city.name` memicu N query tambahan karena asosiasi `city` tidak di-preload.
*   *Good:* Pastikan controller melakukan `User.includes(:city)` atau gunakan strict loading untuk mendeteksi pelanggaran tersebut di tahap pengujian otomatis (*test suite*).

### 4. Penulisan Cache Tanpa Batasan Batas Waktu Kadaluwarsa (TTL)
*   *Bad:*
    ```ruby
    Rails.cache.write("system_config", Config.load_all)
    ```
    *Dampak:* Redis kehabisan memori (*out of memory*) karena kunci-kunci permanen menumpuk tanpa batas, memaksa Redis melakukan eviksi agresif atau menolak perintah simpan baru.
*   *Good:* Selalu definisikan `expires_in` pada setiap penulisan cache:
    ```ruby
    Rails.cache.write("system_config", Config.load_all, expires_in: 24.hours)
    ```

### 5. Menggunakan Default Logger Rails di Produksi Berkecepatan Tinggi
*   *Bad:* Membiarkan Rails menggunakan multi-line string logger default:
    ```
    Processing by CatalogController#show as HTML
      Parameters: {"id"=>"1"}
      User Load (0.5ms)  SELECT "users".* FROM "users" WHERE ...
    Completed 200 OK in 15ms (Views: 12.1ms | ActiveRecord: 1.2ms)
    ```
    *Dampak:* I/O disk logging terbebani oleh string multi-baris yang sulit di-parse oleh sistem sentralisasi log (seperti Elastic/Loki), serta alokasi string formatting Ruby membebani throughput.
*   *Good:* Gunakan `Lograge` untuk menghasilkan log JSON single-line yang padat dan terstruktur.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Strict Loading di Lingkungan Development & Test:**
    Konfigurasikan aplikasi Rails agar melempar error saat N+1 terjadi di development:
    ```ruby
    # config/environments/development.rb
    config.active_record.action_on_strict_loading_violation = :raise
    ```
2.  **Koleksi Cache Keys Berbasis Array:**
    Gunakan identifikasi array deklaratif yang memanfaatkan semantic hashing:
    ```ruby
    cache [:v1, :admin, current_account, @report] do
      # Content
    end
    ```
3.  **Gunakan Read Replicas untuk Query Analitik:**
    Konfigurasikan pembagian peran koneksi database (*database role switching*) di controller untuk query yang memakan resource besar:
    ```ruby
    ActiveRecord::Base.connected_to(role: :reading) do
      @reports = HeavyReport.generate_for(current_company)
    end
    ```
4.  **Tuning Konfigurasi Eviction Redis:**
    Pastikan Redis `maxmemory-policy` disetel ke `volatile-lru` (jika Redis dipakai bersama sidekiq/background jobs) atau `allkeys-lru` (jika instance didedikasikan 100% untuk Rails Cache).
5.  **Batasi Pluck Kolom Besar:**
    Jangan mengambil kolom teks masif (`TEXT`, `JSONB`) kecuali benar-benar diperlukan oleh UI. Gunakan `.select(:id, :name)` untuk mereduksi footprint RAM secara dramatis.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Konfigurasi YJIT di Produksi (Ruby 3.3+)
Aktifkan YJIT melalui variabel lingkungan atau inisialisasi command line:
```bash
# Dockerfile / Environment variables
ENV RUBY_YJIT_ENABLE=1
```
Tambahkan monitoring runtime untuk memverifikasi rasio kompilasi instruksi native:
```ruby
# config/initializers/yjit_telemetry.rb
Rails.application.config.after_initialize do
  if defined?(RubyVM::YJIT) && RubyVM::YJIT.enabled?
    Rails.logger.info("[YJIT] Compilation status: Enabled")
  end
end
```

### 2. Tuning Garbage Collection Ruby (RGenGC)
Optimalkan parameter memori heap untuk lingkungan aplikasi berskala besar agar GC tidak berjalan terlalu agresif:

```bash
# Konfigurasi container runtime env
ENV RUBY_CRuby_GC_HEAP_INIT_SLOTS=1000000
ENV RUBY_GC_HEAP_FREE_SLOTS=500000
ENV RUBY_GC_HEAP_GROWTH_FACTOR=1.25
ENV RUBY_GC_MALLOC_LIMIT=64000000
ENV RUBY_GC_MALLOC_LIMIT_GROWTH_FACTOR=1.4
```

### 3. Profiling Memori via `derailed_benchmarks`
Untuk mendeteksi permata dependensi (*gem bloat*) yang menyerap memori berlebih saat booting aplikasi:
```bash
bundle exec derailed exec bundle:mem
```
Dan untuk mengisolasi titik alokasi objek tinggi per endpoint:
```ruby
# Gemfile development
gem 'memory_profiler'

# Di console/test
report = MemoryProfiler.report do
  CatalogController.new.dispatch(:show, request, response)
end
report.pretty_print(scale_bytes: true)
```

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Pencegahan Information Leakage pada Russian Doll Caching
*   **Kerentanan:** Fragmen tampilan menyimpan data sensitif pengguna (misal: saldo dompet, alamat pengiriman) di dalam fragmen global yang dapat dibaca oleh pengguna lain.
*   **Hardening Pattern:** Selalu pisahkan fragmen publik dari fragmen privat, atau masukkan user identity token ke dalam cache key:
```erb
<%# SALAH: Fragmen ini akan di-cache secara global dan tampil ke user lain! %>
<% cache @product do %>
  <h2><%= @product.name %></h2>
  <div>Your special discount: <%= current_user.personal_discount %>%</div>
<% end %>

<%# BENAR: Pisahkan konten privat ke dalam key yang terisolasi %>
<% cache @product do %>
  <h2><%= @product.name %></h2>
<% end %>

<% cache [@product, current_user, "pricing"] do %>
  <div>Your special discount: <%= current_user.personal_discount %>%</div>
<% end %>
```

### 2. Cache Poisoning via Unsanitized Parameters
*   **Kerentanan:** Memasukkan parameter input langsung sebagai bagian dari penamaan cache key:
```ruby
# RENTAN TERHADAP CACHE POISONING & KEY INJECTION
Rails.cache.fetch("search_results_#{params[:filter_query]}")
```
*   **Mitigasi:** Hash parameter menggunakan algoritma kriptografis sebelum dijadikan kunci:
```ruby
sanitized_key = Digest::SHA256.hexdigest(params[:filter_query].to_s)
Rails.cache.fetch("search_results/#{sanitized_key}", expires_in: 10.minutes)
```

### 3. Otentikasi dan Enkripsi Cache Store
*   Pastikan koneksi ke Redis Cache Store mewajibkan SSL (`rediss://`) dan autentikasi password yang kuat.
*   Isolasi network Redis cache melalui Private VPC/Subnet yang tidak memiliki IP publik.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Arsitektur observabilitas modern Rails mengintegrasikan logging terstruktur dan telemetry OpenTelemetry.

### 1. Implementasi Lograge Terstruktur (JSON Logging)

```ruby
# config/environments/production.rb
Rails.application.configure do
  config.lograge.enabled = true
  config.lograge.formatter = Lograge::Formatters::Json.new

  # Tambahkan context distributed tracing ke setiap record log
  config.lograge.custom_options = lambda do |event|
    {
      time: Time.current.iso8601,
      remote_ip: event.payload[:remote_ip],
      user_id: event.payload[:user_id],
      trace_id: OpenTelemetry::Trace.current_span.context.hex_trace_id,
      span_id: OpenTelemetry::Trace.current_span.context.hex_span_id,
      allocations: event.allocations,
      params: event.payload[:params].except("controller", "action", "format")
    }
  end
end
```

### 2. Integrasi OpenTelemetry SDK Instrumentation

```ruby
# config/initializers/opentelemetry.rb
require 'opentelemetry/sdk'
require 'opentelemetry/exporter/otlp'
require 'opentelemetry/instrumentation/all'

OpenTelemetry::SDK.configure do |c|
  c.service_name = "rails-core-monolith"
  c.service_version = "2.4.1"

  # Memuat instrumentasi otomatis untuk Rails, ActiveRecord, Redis, dan Puma
  c.use_all({
    'OpenTelemetry::Instrumentation::ActiveRecord' => {
      payload_attribute_keys: %w[sql type name]
    },
    'OpenTelemetry::Instrumentation::Rack' => {
      untraced_endpoints: ['/up', '/healthz']
    }
  })
end
```

### 3. Custom Performance Subscriber (ActiveSupport::Notifications)
Contoh listener untuk menangkap query database yang berjalan lebih lambat dari 100ms (*slow query tracker*):

```ruby
# config/initializers/slow_query_subscriber.rb
ActiveSupport::Notifications.subscribe("sql.active_record") do |name, start, finish, id, payload|
  duration_ms = (finish - start) * 1000

  if duration_ms > 100.0 && payload[:name] != "SCHEMA"
    Rails.logger.warn(
      {
        event: "slow_query_detected",
        duration_ms: duration_ms.round(2),
        query_name: payload[:name],
        sql: payload[:sql],
        connection_id: payload[:connection_id]
      }.to_json
    )
  end
end
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### 1. Database Association Loading Decision Matrix

```
Apakah data asosiasi dibutuhkan di view/eksekusi selanjutnya?
│
├── TIDAK  ──> Gunakan `.joins(...)` (Hanya filtering data tanpa alokasi objek relasi)
│
└── YA     ──> Apakah Anda melakukan filtering (WHERE/ORDER) pada kolom tabel relasi tersebut?
               │
               ├── YA   ──> Gunakan `.eager_load(...)` (Membuat 1 SQL via LEFT OUTER JOIN)
               │
               └── TIDAK──> Gunakan `.preload(...)` (Membuat query sekunder bersih)
                            *Note: `.includes(...)` otomatis memilih antara preload/eager_load.
```

### 2. Cache Invalidation Patterns Quick Reference
*   **Russian Doll Model Caching:** Pasang `belongs_to :parent, touch: true` pada model anak.
*   **Low-Level Caching:** `Rails.cache.fetch(key, expires_in: X, race_condition_ttl: Y) { ... }`.
*   **HTTP Conditional Caching:** Gunakan `fresh_when(record)` atau `stale?(record)` langsung di controller untuk mengembalikan respon `304 Not Modified`.
*   **Count vs Size:** Gunakan `collection.size` untuk menghindari pemanggilan query `COUNT(*)` jika array sudah ada di memori.

### 3. Komando CLI Kinerja

```bash
# Audit N+1 queries saat test automation
bundle exec rspec --tag strict_loading

# Analisis pemakaian memori gem saat proses startup
bundle exec derailed exec bundle:mem

# Benchmarking endpoint menggunakan Apache Bench (1000 requests, 50 concurrency)
ab -n 1000 -c 50 -H "Accept-Encoding: gzip" https://api.local/catalog/1
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Uji penguasaan konsep Anda. Jawab pertanyaan berikut terlebih dahulu secara mandiri sebelum membaca kunci dan penjelasannya.

### Soal Evaluasi

#### Level: Basic (5 Soal)
1. Apa perbedaan fungsional antara mengeksekusi `@users.count`, `@users.length`, dan `@users.size` pada sebuah koleksi ActiveRecord?
2. Bagaimana mekanisme `touch: true` pada relasi `belongs_to` memicu pembaharuan fragment cache bersarang (*Russian Doll Cache*)?
3. Sebutkan risiko yang terjadi jika Anda menyetel Puma `threads_count = 16` sementara `pool` di database PostgreSQL hanya disetel ke `5`.
4. Mengapa kita tidak disarankan menyimpan langsung objek ActiveRecord (`ActiveRecord::Base`) ke dalam Redis Cache Store?
5. Apa keuntungan menggunakan gem Lograge dibandingkan format log multi-baris standar Rails pada arsitektur produksi?

#### Level: Intermediate (5 Soal)
6. Kapan Rails secara internal memutuskan untuk mengonversi strategi pemanggilan query dari `preload` menjadi `eager_load` saat method `.includes(...)` digunakan?
7. Jelaskan fenomena *Cache Stampede* (Dogpiling), dan bagaimana parameter `race_condition_ttl` bekerja secara internal untuk mengatasinya.
8. Bagaimana aktivasi Ruby 3.3 YJIT mempengaruhi throughput aplikasi Rails, dan metrik apa yang harus dipantau untuk memastikan efektivitasnya?
9. Bagaimana mekanisme kerja HTTP Conditional Get menggunakan method `stale?` di Rails controller menghemat sumber daya jaringan dan server?
10. Dalam skenario apa penggunaan `Solid Cache` lebih menguntungkan dibandingkan menggunakan cluster `Redis` dedicated?

---

### Kunci Jawaban & Rationale Teknis

1.  **Jawaban:**
    *   `.count`: Selalu mengeksekusi query database `SELECT COUNT(*)`.
    *   `.length`: Menginstansiasi seluruh record ke memori Ruby sebagai Array lalu memanggil method panjang array bawaan Ruby (bisa memicu boros RAM jika data besar).
    *   `.size`: Menggunakan hasil perhitungan memori jika data sudah dimuat, atau mengeksekusi `COUNT(*)` jika data belum dimuat. Paling efisien untuk kasus serbaguna.
2.  **Jawaban:**
    Saat objek anak diubah (save/update), `touch: true` memperbarui kolom `updated_at` pada record induk. Ini mengubah nilai `cache_key_with_version` milik induk. Template fragment luar yang memantau objek induk otomatis mengalami *cache miss*, membaca ulang layout luar, namun tetap dapat membaca fragment anak lain yang tidak berubah (*cache hit*).
3.  **Jawaban:**
    Terjadi *Pool Starvation*. Thread ke-6 hingga ke-16 yang mencoba mengeksekusi query database akan terblokir menunggu koneksi bebas. Jika waktu tunggu melebihi 5 detik, aplikasi melemparkan error `ActiveRecord::ConnectionTimeoutError` dan menghasilkan error 500 ke klien.
4.  **Jawaban:**
    Objek ActiveRecord menyimpan referensi metadata internal yang besar (skema tabel, state mutasi, koneksi). Serialisasi via `Marshal.dump` dan rekonstruksinya via `Marshal.load` menguras resource CPU secara signifikan dan menyebabkan alokasi memori berlebih, membatalkan efisiensi caching.
5.  **Jawaban:**
    Lograge mentransformasi log request dari multi-baris yang tersebar menjadi satu baris tunggal JSON terstruktur. Hal ini mengurangi I/O penulisan disk secara masif, memudahkan parsing instan oleh centralized log aggregator (seperti Elasticsearch/Vector/Loki), dan mencegah log context terpecah saat dieksekusi secara concurrent oleh thread Puma yang berbeda.
6.  **Jawaban:**
    Saat query yang menggunakan `.includes(...)` menyertakan klausa `.where(...)` atau `.order(...)` yang secara eksplisit merujuk pada tabel relasi tersebut (via `.references(...)`), Rails tidak bisa membagi query menjadi dua query independen. Akibatnya, Rails mengubah strateginya menggunakan `eager_load` (`LEFT OUTER JOIN`) dalam satu query.
7.  **Jawaban:**
    *Cache Stampede* terjadi saat kunci cache yang memproses data mahal kedaluwarsa pada kondisi beban trafik tinggi, menyebabkan ratusan request secara bersamaan mencoba mengompilasi ulang data yang sama ke database. Parameter `race_condition_ttl` mengatasinya dengan memperpanjang masa berlaku kunci yang kedaluwarsa selama beberapa detik secara atomik untuk request-request berikutnya, sementara satu request pertama diizinkan menghitung dan memperbarui cache yang baru.
8.  **Jawaban:**
    YJIT mengompilasi YARV bytecode berulang menjadi machine code native, mengurangi beban interpretasi instruksi VM sehingga latensi p95/p99 turun antara 15% - 25%. Metrik yang wajib dipantau adalah `code_region_size` dan rasio eksekusi instruksi native (`ratio_in_yjit` via `RubyVM::YJIT.runtime_stats`), memastikan memori instruksi tidak melebihi alokasi.
9.  **Jawaban:**
    Method `stale?` mengecek header HTTP `If-None-Match` (ETag) dan `If-Modified-Since` dari client. Jika data model di database tidak berubah (timestamp dan ID identik), Rails langsung menghentikan proses rendering dan merespons dengan header `304 Not Modified` tanpa body payload. Ini mengeliminasi rendering template view dan menghemat bandwidth transmisi data.
10. **Jawaban:**
    Solid Cache menggunakan disk-based storage (PostgreSQL/NVMe) yang menawarkan rasio kapasitas-ke-harga jauh lebih besar dibanding RAM Redis. Ini ideal untuk aplikasi dengan fragment cache berukuran puluhan gigabyte yang jarang berubah, di mana latensi beberapa milidetik SSD dapat diterima demi memangkas biaya server cluster memory secara signifikan.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Misi Rekayasa: Penyelamatan Katalog Performa Rendah (*Performance Tuning*)

Anda diberikan sistem katalog yang mengalami degradasi performa: latensi p99 mencapai **1.450ms** pada 1.000 RPS. Tugas Anda adalah melakukan refactor total arsitektur endpoint tersebut untuk menurunkan latensi p99 ke **di bawah 40ms**.

#### Spesifikasi Model Domain:
```ruby
# Domain Context:
# Store memiliki banyak Product (1 Store -> 50.000 Products).
# Setiap Product memiliki banyak ProductVariant (1 Product -> 5 Variants).
# Setiap Product memiliki banyak ProductReview (1 Product -> ~50 Reviews).
```

#### Persyaratan Tugas:
1.  **Database Layer Optimization:**
    *   Buat migrasi database baru yang menambahkan `counter_cache` untuk `reviews_count` dan kolom `cached_rating` pada `Product`.
    *   Tambahkan indeks komposit pada `products` untuk mendukung filtering `store_id`, `status: :active`, dan pengurutan `created_at: :desc`.
2.  **Implementation of Strict Loading & Association Preloading:**
    *   Implementasikan query controller yang memuat 20 item produk per halaman dengan proteksi `strict_loading`.
    *   Gunakan strategi pemuatan asosiasi yang benar agar tidak ada query database tambahan saat varian dirender.
3.  **Implementasi Russian Doll Caching:**
    *   Buat view ERB atau serialisasi JSON yang membungkus seluruh store dan masing-masing item produk.
    *   Pastikan jika sebuah review baru masuk pada salah satu produk, **hanya** fragment produk bersangkutan yang mengalami cache miss.
4.  **Instrumentation & Benchmark Validation:**
    *   Tulis RSpec integration test yang memvalidasi bahwa endpoint hanya mengeksekusi maksimal **4 query database**, terlepas dari berapa banyak produk yang dirender.
    *   Gunakan block `Benchmark.realtime` untuk memvalidasi bahwa eksekusi cache hit berjalan dalam waktu **< 15ms**.

#### Snippet Kode Template Awal yang Harus Di-refactor:

```ruby
# PERBAIKI KODE LAMBAT INI:
class Api::V1::StoresController < ApplicationController
  def show
    @store = Store.find(params[:id])
    # SLOW: Memuat ribuan record tanpa batasan, rentan memory spike dan N+1
    render json: @store.products.map { |p|
      {
        id: p.id,
        name: p.name,
        average_rating: p.product_reviews.average(:rating).to_f,
        review_count: p.product_reviews.count,
        variants: p.product_variants.map { |v| { sku: v.sku, price: v.price } }
      }
    }
  end
end
```

#### Kriteria Keberhasilan (*Acceptance Criteria*):
*   Zero N+1 Query: Terbukti lulus pengujian strict loading tanpa eksepsi.
*   Cache Hit Latency: Di bawah 15ms pada request berulang.
*   Memory Footprint: Alokasi heap konstan dan tidak meningkat sebanding dengan volume request (*zero linear memory growth*).