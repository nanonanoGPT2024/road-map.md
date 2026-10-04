# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Ruby Lanjutan & Anatomi Rails Engine**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Resolusi Pencarian Metode (*Method Lookup Path*) & Eigenclass**
   Jelaskan secara mendalam bagaimana Ruby Virtual Machine (CRuby/YARV) mencari eksekusi metode ketika sebuah pesan (*message*) dikirim ke sebuah objek. Uraikan perbedaan struktural antara `include`, `prepend`, dan `extend` dalam diagram *ancestors chain*, serta jelaskan di mana posisi *singleton class* (*eigenclass*) bertempat dalam hierarki pewarisan objek.

2. **Perilaku Semantik Eksekusi: Block, Proc, dan Lambda**
   Meskipun ketiganya merupakan bentuk *closure* dalam Ruby, jelaskan dua perbedaan kritis antara `Proc` dan `lambda` terkait penanganan kata kunci `return` dan evaluasi *arity* (pencocokan argumen). Bagaimana perbedaan ini memengaruhi keandalan (*predictability*) kode di tingkat internal Rails callback?

3. **Spesifikasi Protokol Rack dan Siklus Transmisi HTTP**
   Definisikan kontrak arsitektur paling mendasar dari *Rack interface*. Mengapa *return value* dari metode `call(env)` harus berupa array tiga elemen `[status, headers, body]`? Jelaskan implikasi teknis pada web server (seperti Puma) jika elemen `body` gagal merespons pemanggilan `#each` atau jika sebuah Rack Middleware menutup (*close*) objek body sebelum data dialirkan ke klien.

4. **Siklus Hidup Bootstrapping Rails dan Topological Sorting Initializer**
   Gambarkan alur inisialisasi aplikasi Rails mulai dari eksekusi `config.ru`, pemanggilan `config/boot.rb`, `config/application.rb`, hingga eksekusi `config/environment.rb`. Bagaimana `Rails::Railtie` dan `Rails::Engine` menggunakan algoritma *topological sort* untuk mengeksekusi kumpulan blok `initializer` dengan dependensi `before:` dan `after:`?

5. **Model Konkurensi Ruby: GVL, OS Threads, dan Fibers**
   Jelaskan peran *Global VM Lock* (GVL) pada CRuby saat mengeksekusi operasi CPU-bound versus IO-bound pada lingkungan web server *multi-threaded* (misalnya Puma). Mengapa penulisan variabel kelas global (seperti `@@variable`) atau *memoization* non-atomik (`@var ||= ...`) di dalam controller dapat menyebabkan *data race* fatal meskipun GVL aktif?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Zeitwerk, Lexical Nesting, dan Autoloading Edge Cases**
   Rails menggunakan Zeitwerk untuk *code loading* berbasis konvensi direktori dan penamaan file. Mengapa struktur kode berikut dapat memicu `NameError: uninitialized constant Admin::User` atau memuat kelas yang salah saat dijalankan di lingkungan produksi (*eager load*) versus pengembangan (*autoload*), dan bagaimana resolusi konstanta lexical (`Module.nesting`) memengaruhinya?
   ```ruby
   # app/controllers/admin/users_controller.rb
   class Admin::UsersController < ApplicationController
     def show
       @user = User.find(params[:id]) # Apakah ini ::User atau Admin::User?
     end
   end
   ```

2. **Dampak Metaprogramming terhadap Inline Method Caching & YJIT**
   Metode dinamis dapat dibuat menggunakan `define_method` atau `class_eval` dengan evaluasi string. Jelaskan perbedaan performa keduanya dalam konteks alokasi memori internal Ruby dan dampaknya terhadap *Inline Caches* (IC) serta deoptimasi pada *Ruby Just-in-Time Compiler* (YJIT). Mengapa pemanggilan `Module#remove_method` atau redefinisi metode pada *runtime* dihindari dalam sistem throughput tinggi?

3. **Refinements vs. Monkey Patching Global**
   Analisis mekanisme internal Ruby `Refinements` (`using MyRefinement`). Bagaimana Ruby mengisolasi perubahan metode agar hanya aktif dalam *lexical scope* file tertentu tanpa mengotori tabel metode global? Apa batasan teknis dari *Refinements* saat berinteraksi dengan pemanggilan dinamis seperti `send`, `method(:symbol)`, atau evaluasi blok di luar file konteks?

4. **Fragmentasi Memori, Compacting GC, dan Copy-on-Write (CoW)**
   Puma *clustered mode* memanfaatkan mekanisme *fork* dari sistem operasi Linux untuk menghemat memori melalui *Copy-on-Write* (CoW). Mengapa eksekusi kode Ruby pasca-*fork* (seperti lazy loading konstanta atau alokasi *mutable global state*) dapat merusak halaman memori CoW (*dirty pages*)? Bagaimana GC Compactor (`GC.compact`) bekerja untuk mengatasi fragmentasi memori tanpa melanggar referensi pointer di level C extension?

5. **Middleware Short-circuiting dan Mutasi State Objek `env`**
   Perhatikan kasus di mana sebuah downstream Rack Middleware gagal menerima header autentikasi yang diinjeksi oleh upstream middleware. Saat Anda melakukan inspeksi pada middleware stack via `bin/rails middleware`, susunannya tampak benar. Apa yang menyebabkan `env['HTTP_AUTHORIZATION']` menghilang jika sebuah middleware di tengah stack memanggil `dup` secara dangkal (*shallow copy*) pada objek `env` atau mengeksekusi *early return* tanpa mengalirkan *downstream response*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden OOM Storm Pasca Deployment pada High-Throughput Engine
* **Konteks:** Perusahaan fintech baru saja mengekstrak modul pembayaran ke dalam isolated mountable `Rails::Engine`. Setelah deployment rilis terbaru ke klaster produksi (Puma clustered mode: 4 worker, 16 thread per worker), terjadi insiden Out-of-Memory (OOM) storm yang menyebabkan Linux OOM Killer mematikan Puma worker setiap 15 menit di bawah beban 12.000 RPS.
* **Gejala:** Metrik New Relic menunjukkan *heap expansion* terus melonjak tanpa diiringi *major garbage collection* yang efektif. Log mencatat ribuan dynamic symbol dibuat per menit di layer deserialisasi payload Webhook Engine, serta penggunaan `define_singleton_method` di dalam siklus request per transaksi.
* **Pertanyaan Diagnostik:**
  1. Identifikasi dua akar masalah mekanis di level Ruby VM yang menyebabkan *memory retention/leak* pada skenario tersebut.
  2. Bagaimana Anda memanfaatkan modul `ObjectSpace` dan `GC.stat` untuk mendiagnosis jenis objek yang menahan alokasi memori paling besar secara presisi di lingkungan staging?
  3. Rancang strategi perbaikan arsitektural di tingkat Engine untuk meniadakan dynamic metaprogramming tersebut tanpa mengubah skema kontrak JSON API yang diterima.

---

### Skenario B: Race Condition pada Concurrency Model Rails Engine
* **Konteks:** Sebuah `Rails::Engine` bernama `CoreInventory::Engine` menangani alokasi stok produk. Pada saat *flash sale*, tercatat stok bernilai negatif di basis data PostgreSQL, padahal validasi tingkat aplikasi telah diimplementasikan.
* **Inspeksi Kode:** Ditemukan implementasi *memoization pattern* pada layer domain engine sebagai berikut:
  ```ruby
  module CoreInventory
    class StockManager
      class << self
        def current_allocator
          @current_allocator ||= Allocator.new(Tenant.current_id)
        end

        def reserve_stock(item_id, quantity)
          current_allocator.process(item_id, quantity)
        end
      end
    end
  end
  ```
* **Pertanyaan Diagnostik:**
  1. Tunjukkan dengan presisi di mana letak kerentanan *thread-safety violation* pada kode di atas saat dieksekusi di bawah Puma multi-threaded mode.
  2. Jelaskan mengapa *cross-tenant data leakage* dapat terjadi akibat lifecycle dari class instance variable `@current_allocator`.
  3. Tuliskan refaktor kode lengkap yang menjamin isolasi data berbasis *Fiber-local storage* atau *CurrentAttributes* yang *thread-safe*, serta jelaskan kapan Anda harus membersihkan state tersebut untuk mencegah *memory leak*.

---

### Skenario C: Circular Dependency & Bootstrapping Deadlock pada Multi-Engine Architecture
* **Konteks:** Arsitektur monolit terdistribusi memiliki dua internal Engines: `Authentication::Engine` dan `AuditLogging::Engine`. Engine `Authentication` membutuhkan `AuditLogging` untuk mencatat setiap upaya login. Namun, `AuditLogging::Engine` membutuhkan kelas `Authentication::CurrentSession` pada initializer-nya untuk mengonfigurasi interceptor audit.
* **Gejala:** Saat booting Rails di production (`RAILS_ENV=production bin/rails runner "puts 'Booted'"`), aplikasi mengalami deadlock / crash dengan pesan:
  `NameError: uninitialized constant Authentication::CurrentSession` atau `SystemStackError: stack level too deep` di fase `initializers.run`.
* **Pertanyaan Diagnostik:**
  1. Analisis mengapa dependency cycle antar-engine gagal diselesaikan oleh Zeitwerk saat `config.eager_load = true`.
  2. Bagaimana arsitektur `ActiveSupport.on_load` hooks memecahkan masalah dependensi sirkular ini dibandingkan langsung memanggil konstanta di dalam `config/initializers/`?
  3. Rancang desain pemisahan (*decoupling*) dependensi kedua engine tersebut dengan pola *Event-Driven Notification* menggunakan `ActiveSupport::Notifications` sehingga kedua engine tidak saling memanggil konstanta secara langsung saat booting.

---

## 4. Chapter Challenge

### Tantangan Praktis: Membangun Thread-Safe High-Performance Isolation Engine & Observability Middleware

#### Problem Statement
Anda ditugaskan merancang modul inti aplikasi SaaS berskala enterprise dalam bentuk mountable `Rails::Engine` bernama `TelemetryControl::Engine`. Engine ini bertugas menyaring seluruh HTTP request, mengukur alokasi memori objek Ruby per-request secara presisi, membatasi ukuran request payload, dan menginjeksi correlation ID ke dalam request tracing context tanpa menggunakan gem eksternal pihak ketiga (pure Ruby & Rails primitives).

#### Requirements
1. **Isolated Namespace Engine:**
   * Engine harus diisolasi menggunakan `isolate_namespace TelemetryControl`.
   * Harus menyediakan konfigurasi internal engine melalui DSL deklaratif (misal: `TelemetryControl.configure { |c| c.max_payload_bytes = 1_048_576 }`).

2. **Custom Zero-Allocation (Low-Overhead) Rack Middleware:**
   * Buat middleware `TelemetryControl::Rack::MetricsCollector` yang disuntikkan secara otomatis ke dalam middleware stack host application tepat sebelum `ActionDispatch::Executor`.
   * Middleware harus menghitung delta alokasi heap object Ruby menggunakan `GC.stat(:total_allocated_objects)` selama siklus request-response.
   * Middleware harus menolak request dengan status `413 Payload Too Large` secara langsung jika `CONTENT_LENGTH` melampaui batas yang dikonfigurasi, tanpa membaca seluruh IO stream ke memori.

3. **Trace Context Execution Wrapper:**
   * Gunakan `ActiveSupport::CurrentAttributes` atau `Fiber[:current_telemetry_context]` untuk menyimpan trace data (misal: `request_id`, `allocated_objects_delta`, `tenant_uuid`) agar dapat diakses dari service object manapun dalam thread/fiber yang sama secara aman (*thread-safe*).

4. **Metaprogramming Instrumentation via Module Prepension:**
   * Buat sebuah modul tracer `TelemetryControl::Tracer` yang di-*prepend* secara otomatis ke kelas `ActiveRecord::Base` saat event `ActiveSupport.on_load(:active_record)` terpicu.
   * Modul ini harus mengukur execution time metode `#save` dan mengirimkan event metrik via `ActiveSupport::Notifications`. Pastikan tidak ada deoptimasi inline cache global yang merusak YJIT.

#### Constraints
* **Thread Safety:** Bebas dari *class-level state mutation* global. Tidak boleh menggunakan `@@class_variables`.
* **Zero Monkey-Patching Global:** Dilarang melakukan redefinisi metode global tanpa `Module#prepend`.
* **Engine Lifecycle:** Engine harus mendaftarkan middleware dan active record hooks menggunakan rail tie `initializer` dengan dependensi yang didefinisikan secara eksplisit (`after: ...`, `before: ...`).
* **Environment:** Kompatibel dengan Ruby 3.3+ (mendukung YJIT dan M:N Threading) dan Rails 7.1+.

#### Expected Output
1. File `lib/telemetry_control/engine.rb` yang mendefinisikan setup Engine, lifecycle initializers, dan registrasi middleware.
2. File `lib/telemetry_control/rack/metrics_collector.rb` yang berisi implementasi Rack Middleware lengkap dengan *early-exit* dan pengukuran delta GC.
3. File `lib/telemetry_control/current_context.rb` untuk implementasi thread-safe context storage.
4. File `lib/telemetry_control/tracer.rb` dengan implementasi `prepend` yang di-hook secara elegan melalui `ActiveSupport.on_load`.
5. Contoh *RSpec snippet* (`spec/middleware/metrics_collector_spec.rb`) yang menguji skenario middleware menolak payload berukuran besar dan skenario downstream processing normal.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Topologi urutan lookup metode Ruby: Object, Module inclusion, Module prepension, Superclass, Kernel, BasicObject, dan posisi Eigenclass.
- [ ] Arsitektur internal Rack: Peran argumen `env`, siklus pemanggilan `call`, serta pemrosesan *streaming body* berbasis protokol I/O `#each` dan `#close`.
- [ ] Perbedaan fundamental konkurensi Ruby: Cooperative Fibers, OS Threads, GVL scheduling, memory visibility, dan implikasinya pada Puma web server.
- [ ] Mekanisme internal autoloading Zeitwerk: Hubungan antara *file path*, *constant reference*, lexical scoping nesting, dan pemuatan saat boot (`eager_load`).
- [ ] Anatomi Rails Boot Engine: Urutan siklus hidup dari `config.ru` hingga `to_prepare`, relasi dependency graph initializer menggunakan `before`/`after`.
- [ ] Konsekuensi alokasi memori tingkat rendah: Objek RString/RArray, fragmentasi heap Ruby, dampaknya pada Linux Copy-on-Write (CoW), dan strategi `GC.compact`.

### Saya tidak perlu menghafal:
- [ ] Seluruh daftar variabel environment CGI standar yang ada pada hash `Rack env` (cukup pahami variabel inti seperti `PATH_INFO`, `REQUEST_METHOD`, `rack.input`).
- [ ] Daftar lengkap kode konstanta numeric C internal dari CRuby Virtual Machine instruksi YARV.
- [ ] Semua konfigurasi default internal Rails Engine bawaan yang dapat dilihat kapan saja melalui dokumentasi `Rails::Engine.subclasses`.
- [ ] Angka persis dari statistik `GC.stat` (cukup pahami metrik kunci seperti `:total_allocated_objects`, `:heap_live_slots`, dan `:major_gc_count`).

### Saya harus bisa melakukan:
- [ ] Mengonstruksi mountable dan isolated `Rails::Engine` dari awal dan mengintegrasikannya ke dalam Host Application secara clean.
- [ ] Menulis kustom Rack Middleware yang thread-safe, minim alokasi heap, dan mampu melakukan intercepting/short-circuiting request secara efisien.
- [ ] Melakukan debugging kegagalan resolusi konstanta Zeitwerk dan *circular dependency* pada arsitektur monolit berlapis.
- [ ] Mencegah dan memperbaiki *thread-safety race conditions* dan *memory leak* yang dipicu oleh mutasi state global atau unmanaged class instance variables.
- [ ] Memanfaatkan `Module#prepend` bersama `ActiveSupport.on_load` hooks untuk instrumentasi performa tinggi yang ramah terhadap YJIT inline method caching.