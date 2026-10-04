# BAB 09: Quiz, Challenge, & Knowledge Check
**Performance Optimization, Caching & Observability**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik & Mekanisme Query Loading
Jelaskan perbedaan mendasar antara `preload`, `eager_load`, dan `includes` dalam ActiveRecord! Kapan ActiveRecord memutuskan untuk mengeksekusi dua query terpisah vs satu query tunggal dengan `LEFT OUTER JOIN`, dan bagaimana implikasi pemilihan ini terhadap alokasi memori (Ruby heap allocation) ketika memuat relasi *one-to-many* dengan kardinalitas tinggi?

### Soal 1.2: Anatomi Russian Doll Caching & Write-Amplification
Uraikan cara kerja *Russian Doll Caching* pada ActionView! Bagaimana mekanisme `touch: true` pada relasi model mengeliminasi kompleksitas manual *cache invalidation* melalui *key-based cache expiration*, dan apa konsekuensi sistemik (*write-amplification* & *lock contention*) pada tabel induk database jika opsi `touch: true` digunakan secara agregat di sistem dengan volume write tinggi?

### Soal 1.3: HTTP Conditional GET vs Server-Side Fragment Caching
Bandingkan arsitektur HTTP Caching berbasis `stale?` / `fresh_when` (ETag & Last-Modified) dengan server-side caching berbasis `Rails.cache.fetch`! Pada kondisi seperti apa sebuah request yang di-cache menggunakan `Rails.cache` tetap membebani throughput I/O jaringan server, sementara HTTP Conditional GET mampu memangkas TTFB (*Time to First Byte*) dan bandwidth hingga mendekati nol?

### Soal 1.4: Event-Driven Instrumentation via ActiveSupport::Notifications
Bagaimana `ActiveSupport::Notifications` mengimplementasikan pola arsitektur *Publish-Subscribe* di dalam thread execution context Rails? Jelaskan siklus hidup instrumentasi saat event `sql.active_record` atau `process_action.action_controller` dipancarkan, serta bagaimana data transien tersebut dapat diadaptasi menjadi span distributed tracing berstandar OpenTelemetry!

### Soal 1.5: Ruby MRI Memory Management & Object Allocation Profiling
Mengapa eksekusi query ActiveRecord yang mengembalikan 20.000 baris data dapat menyebabkan lonjakan memori (*memory bloat*) pada Ruby Process yang tidak langsung turun meskipun Garbage Collector (GC) telah dijalankan? Jelaskan relasi antara *Ruby Heap Pages*, fragmentasi memori pada allocator OS (`glibc` vs `jemalloc`), dan retensi memori objek transien!

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik Memory Bloat vs Real Memory Leak
Dalam worker Sidekiq atau proses Puma, Resident Set Size (RSS) meningkat secara monotonik hingga terkena sanksi OOM (*Out Of Memory*) Killer dari kernel Linux. Uraikan metodologi langkah demi langkah untuk membedakan apakah masalah tersebut merupakan *True Memory Leak* (objek tertahan secara permanen pada root reference/global constant) atau *Memory Fragmentation/Bloat*! Tool apa (`derailed_benchmarks`, `memory_profiler`, atau `rbtrace`) yang Anda gunakan dan apa metrik spesifik yang dicari?

### Soal 2.2: Mitigasi Cache Stampede & Race Condition TTL
Jelaskan fenomena *Cache Stampede* (dikenal juga sebagai *thundering herd* atau *dog-piling effect*) saat sebuah cache key bernilai komputasi tinggi kedaluwarsa pada traffic 10.000 RPS! Bagaimana opsi `race_condition_ttl` pada `Rails.cache.fetch` memitigasi masalah ini secara deterministik di level algoritma, dan apa batasan dari mekanisme tersebut jika proses background worker gagal menyelesaikan re-generasi data?

### Soal 2.3: Bahaya Ekstrim Serialisasi Objek ActiveRecord pada Cache Store
Mengapa menyimpan objek mentah ActiveRecord langsung ke dalam cache (`Rails.cache.write("user:#{id}", @user)`) dianggap sebagai *anti-pattern* berbahaya di lingkungan produksi dibanding menyimpan data terstruktur murni (*plain primitives*, JSON, atau MessagePack)? Tinjau jawaban Anda dari perspektif:
1. Deserialization overhead & memory footprint.
2. Risiko *schema drift* / migrasi database yang menyebabkan `TypeMismatch` atau deserialization crash pada versi model yang berbeda.
3. Kerentanan keamanan eksekusi kode (*Remote Code Execution*) via `Marshal.load`.

### Soal 2.4: Bottleneck Analysis pada Rack Middleware Stack
Jelaskan bagaimana Anda mendeteksi degradasi performa yang terjadi *sebelum* request menyentuh `ActionController::Metal`! Jika APM menunjukkan latensi transaksi 800ms, tetapi instrumentasi internal `process_action.action_controller` hanya mencatat 40ms, sebutkan tiga kemungkinan bottleneck tersembunyi pada Rack Middleware pipeline dan bagaimana cara memprofiling setiap layer middleware secara terisolasi!

### Soal 2.5: Sizing & Saturasi Database Connection Pool
Bagaimana relasi matematis antara parameter concurrency Puma (`RAILS_MAX_THREADS`), pool size ActiveRecord (`pool` pada `database.yml`), dan batas kapasitas thread PostgreSQL/MySQL? Apa tanda-tanda spesifik di sisi metrik aplikasi (*ActiveSupport connection metrics*) dan database engine metrics saat terjadi *Connection Pool Depletion/Starvation*, dan bagaimana dampaknya terhadap p99 response time?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Flash-Sale Black Friday Database Meltdown
Sebuah platform e-commerce berbasis Rails meluncurkan flash sale untuk produk elektronik unggulan. Traffic melonjak dari 500 RPS menjadi 15.000 RPS seketika. 

* **Kondisi Sistem:**
  * CPU Database PostgreSQL langsung melonjak ke 100%, load average mencapai 80 pada mesin 16-core.
  * Endpoint bermasalah: `GET /api/v1/promotions/active_deals`
  * Cache engine menggunakan Redis Cluster. Cache Hit Ratio berada pada angka 98.5%.
  * Controller mengeksekusi query agregasi kompleks dengan 4 `JOIN` tabel untuk 1.5% traffic yang mengalami cache miss.
  * Aplikasi mulai melempar error `ActiveRecord::ConnectionTimeoutError: could not obtain a connection from the pool within 5.000 seconds`.
* **Tugas Diagnostik & Solusi:**
  1. Identifikasi *root cause* mengapa database kolaps padahal 98.5% request berhasil di-handle oleh Redis!
  2. Rancang rencana mitigasi darurat dalam kurun waktu 15 menit tanpa downtime/redeploy!
  3. Buat arsitektur refactoring permanen untuk endpoint tersebut menggunakan pattern *Probabilistic Early Expiration* (XFetch) atau *Background Lock-Striped Cache Invalidation*!

### Skenario B: Race Condition & Data Corruption pada High-Frequency Ledger
Sebuah sistem *multi-tenant digital wallet* memproses mutasi saldo menggunakan background worker Sidekiq yang sangat agresif.

* **Kondisi Sistem:**
  * Pengguna melaporkan anomali: Saldo akhir terpotong dua kali atau tidak sinkron saat mutasi saldo terjadi simultan di beberapa thread/worker.
  * Tim developer sebelumnya mencoba mempercepat proses dengan mem-bypass callback model dan menggunakan:
    ```ruby
    # In a fast-path worker:
    Wallet.where(id: wallet_id).update_all("balance = balance - #{amount}")
    Rails.cache.delete("wallets/#{wallet_id}/balance")
    ```
  * Endpoint API read saldo mengimplementasikan caching:
    ```ruby
    def balance
      @balance = Rails.cache.fetch("wallets/#{params[:id]}/balance", expires_in: 1.hour) do
        Wallet.find(params[:id]).balance
      end
      render json: { balance: @balance }
    end
    ```
* **Tugas Diagnostik & Solusi:**
  1. Bedah titik-titik terjadinya *race condition* (baik di layer database write maupun cache-read desynchronization) pada potongan kode di atas!
  2. Mengapa kombinasi `update_all` mentah dan `Rails.cache.delete` berisiko menyajikan data basi (*stale data*) selamanya pada concurrent traffic tinggi?
  3. Tuliskan implementasi perbaikan menggunakan *Strict Pessimistic Locking*, transaksi database atomik, dan perbaikan strategi cache synchronization yang menjamin *strict consistency*!

### Skenario C: APM Overhead & High-Cardinality Metrics Choke
Perusahaan SaaS skala global mengadopsi OpenTelemetry SDK dan Prometheus metric exporter pada Rails monolith mereka untuk memantau performa multitenant micro-billing.

* **Kondisi Sistem:**
  * Setelah instrumentasi dirilis ke produksi, rata-rata latency p50 melonjak 30%, CPU penggunaan cluster Kubernetes naik 40%, dan biaya ingestion APM vendor pihak ketiga melonjak 500%.
  * Developer memasukkan metadata berikut ke setiap tracing span dan Prometheus histogram metric:
    * `tenant_id` (100.000 entitas)
    * `user_id` (4.000.000 pengguna)
    * `request_id` (UUID acak unik per request)
    * `query_sql` (string mentah query lengkap beserta parameter ID)
  * Memory footprint pada setiap Pod Rails naik 250MB secara persisten.
* **Tugas Diagnostik & Solusi:**
  1. Analisis mengapa penambahan label/tag di atas merusak efisiensi Prometheus (*time series database*) dan alokasi memori Ruby process (*High Cardinality problem*)!
  2. Tentukan variabel mana yang mutlak **dilarang** berada di level Metrics (Prometheus) dan hanya boleh berada di level Tracing Span atau Structured Log!
  3. Formulasikan strategi *Sampling* (Head-based vs Tail-based) untuk distributed tracing serta demonstrasikan bagaimana mengonfigurasi filter/sanitizer pada `ActiveSupport::Notifications` agar performa aplikasi kembali ke baseline tanpa kehilangan visibilitas error kritis!

---

## 4. Chapter Challenge

### Tantangan Praktis: Engineering a Resilient High-Throughput Catalog Engine
Anda ditugaskan mendesain ulang modul core e-commerce catalog API endpoint: `GET /api/v1/products` yang saat ini mengalami degradasi fatal setiap kali event promosi berlangsung.

#### Problem Statement:
Endpoint catalog saat ini mengembalikan daftar produk beserta relasi kategorinya, review score, inventory level, dan data merchant. Saat load mencapai 4.000 RPS:
1. Endpoint memicu ratusan N+1 queries.
2. Fragment cache meledak (*memory eviction*) di Redis.
3. Garbage Collection pause mencapai 400ms per siklus karena instansiasi ratusan ribu objek `Product` per detik.
4. Response time p99 menyentuh angka 6.2 detik.

#### Requirements:
1. **ActiveRecord Optimization:**
   * Eliminasi seluruh N+1 query.
   * Cegah instansiasi objek ActiveRecord yang tidak perlu untuk reporting read-only menggunakan pluck/select terfokus atau custom projection.
2. **Layered Resilient Caching:**
   * Implementasikan *Russian Doll Caching* pada serialisasi JSON.
   * Gunakan low-level cache untuk agregasi metrik (misal: review rating aggregate) dengan parameter `race_condition_ttl: 10.seconds` dan `expires_in: 1.hour`.
   * Terapkan kompresi data cache di level Redis store untuk payload yang lebih besar dari 1KB.
3. **Low-Allocation Serialization:**
   * Hindari rendering view via Jbuilder standar jika terbukti lambat; gunakan serialisasi alternatif berbasis Fast JSON API, Alba, atau direct SQL JSON aggregation (`json_build_object`).
4. **Custom Observability Hook:**
   * Buat kustom instrumentasi menggunakan `ActiveSupport::Notifications` bernama `catalog.render_time` yang melacak durasi serialisasi dan jumlah produk yang di-render.
   * Tulis sebuah Subscriber mandiri yang mencatat log peringatan jika alokasi objek Ruby melampaui ambang batas tertentu dalam sebuah siklus request.

#### Constraints:
* **Latency SLA:** P99 response time wajib di bawah 80 milidetik pada saat simulasi 2.000 RPS.
* **Allocations:** Alokasi objek Ruby harus ditekan hingga di bawah 1.500 objek per HTTP request untuk rendering 50 items katalog.
* **Data Freshness:** Data stok dan harga harus konsisten (stale window tidak boleh melebihi 15 detik), sedangkan detail metadata produk (deskripsi/kategori) dapat menggunakan toleransi *stale window* hingga 1 jam.

#### Expected Output:
1. File Controller: `app/controllers/api/v1/products_controller.rb` yang ramping dan efisien.
2. File Query/Service Object: `app/queries/catalog_search_query.rb` yang menangani pembacaan data berperforma tinggi.
3. File Serializer / Template Builder yang mengimplementasikan caching multi-lapis.
4. File Initializer: `config/initializers/catalog_instrumentation.rb` yang mendaftarkan event notification & metric subscriber.
5. Panduan Singkat (Markdown) verifikasi performa menggunakan benchmarking script (`benchmark-ips` atau command `k6`/`wrk`).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan eksekusi SQL internal dan alokasi memori antara `preload`, `eager_load`, dan `includes`.
- [ ] Siklus hidup *Key-Based Cache Expiration* dan propagasi `touch: true` pada model hierarki Rails.
- [ ] Cara kerja memory allocator OS (`jemalloc` vs default `glibc`) dalam konteks fragmentasi memori Ruby MRI.
- [ ] Dampak *High Cardinality* pada sistem observabilitas (Prometheus labels & APM tracing span tags).
- [ ] Perbedaan fundamental antara HTTP conditional caching (`ETag`, `Last-Modified`) dan Server-Side Store Caching (`RedisCacheStore`).
- [ ] Mekanisme pencegahan *Cache Stampede* menggunakan algoritma `race_condition_ttl` dan early expiration.
- [ ] Arsitektur internal `ActiveSupport::Notifications` dan cara kerjanya sebagai decoupled event bus untuk APM.
- [ ] Hubungan antara alokasi objek di heap, siklus minor/major GC Ruby, dan degradasi p99 tail-latency.

### Saya tidak perlu menghafal:
- [ ] Seluruh nama event internal bawaan `ActiveSupport::Notifications` (cukup pahami pola event utama seperti `sql.active_record`, `process_action.action_controller`).
- [ ] Sintaks baris demi baris konfigurasi file C extensions atau tuning flags spesifik internal glibc (`MALLOC_ARENA_MAX`, dsb.) di luar pemahaman konseptualnya.
- [ ] Detail algoritma kompresi internal Redis (misal: LZF, ZSTD) selain mengetahui trade-off komputasi CPU vs bandwidth-nya.

### Saya harus bisa melakukan:
- [ ] Mengidentifikasi dan memusnahkan N+1 queries menggunakan Rails log analysis, `bullet`, atau custom instrumentation subscriber.
- [ ] Menganalisis flamegraph memori dan CPU menggunakan tool profiling (`stackprof`, `memory_profiler`, atau `rack-mini-profiler`) untuk menemukan alokasi objek liar.
- [ ] Mengonfigurasi `database.yml` dan Puma concurrency setting secara presisi untuk mencegah connection starvation di bawah beban tinggi.
- [ ] Mengimplementasikan *Russian Doll Caching* lengkap dengan penanganan fallback data invalidation yang aman.
- [ ] Melakukan isolasi bottleneck lambat pada middleware Rack kustom menggunakan micro-benchmarking.
- [ ] Membangun custom instrumentasi APM/OpenTelemetry yang memancarkan span dan metrik tanpa mencemari sistem dengan overhead kardinalitas tinggi.