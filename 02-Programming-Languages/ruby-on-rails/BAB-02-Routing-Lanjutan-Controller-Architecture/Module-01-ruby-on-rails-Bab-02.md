# Bab 02: Arsitektur Inti Rails (Rails Core Internals)
## Modul 01: Arsitektur Request-Response Pipeline: Rack, Action Pack, dan Engine Internals

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengurai alur hidup paket data HTTP dari soket server web (Puma) hingga eksekusi controller action dengan presisi tingkat kernel framework.
- Mengimplementasikan, memodifikasi, dan menata ulang *middleware stack* (`ActionDispatch::MiddlewareStack`) untuk kebutuhan *cross-cutting concerns* berperforma tinggi.
- Menganalisis cara kerja mesin perutean *Journey* dalam memetakan URI ke controller endpoint menggunakan Finite State Automata.
- Menulis *custom Rack middleware* yang *thread-safe*, efisien terhadap alokasi objek Ruby, dan mematuhi spesifikasi Rack Lint.
- Mendiagnosis dan mengeliminasi *latency overhead* serta kebocoran memori (*memory bloat*) pada fase perutean dan middleware sebelum request mencapai lapisan *Action View* atau *Active Record*.

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
- **Ruby Metaprogramming & Object Model**: Pemahaman mendalam tentang *singleton class*, `Module#prepend`, *block bindings*, dan alokasi `Proc`/`Method`.
- **Protokol HTTP/1.1 & HTTP/2**: Semantik header, representasi *status code*, koneksi *keep-alive*, dan mekanisme *chunked transfer encoding*.
- **Konkurensi Ruby**: Model konkurensi Puma berbasis *worker/threads*, Global VM Lock (GVL) pada YJIT/CRuby, serta batas-batas keutuhan *thread-safety*.
- **CLI Debugging**: Familiaritas dengan `bin/rails middleware`, `bin/rails routes`, dan profiler memori seperti `stackprof` atau `memory_profiler`.

---

### 3. Concept
Rails bukanlah sebuah monolit yang mengeksekusi kode secara magis; Rails pada dasarnya adalah aplikasi berbasis spesifikasi **Rack** yang terdistribusi ke dalam *middleware pipeline*, mesin perutean (*routing engine* berbasis DFA/NFA), dan eksekutor controller (*Action Pack*).

Secara internal:
1. **Rack Specification**: Fondasi antarmuka antara server web (Puma/Falcon) dan Rails. Antarmuka ini hanya mewajibkan satu protokol sederhana: sebuah objek yang merespons metode `call(env)` dan mengembalikan *array* tiga elemen: `[status_code, headers_hash, body_enumerable]`.
2. **Action Pack (Action Dispatch & Action Controller)**:
   - **`ActionDispatch`**: Membungkus objek `env` primitif menjadi `ActionDispatch::Request`, mengelola tumpukan middleware, menangani SSL terminated proxy, manipulasi cookies terenkripsi, serta menjalankan mesin resolusi rute (*Journey*).
   - **`Journey Engine`**: Komponen internal `ActionDispatch::Routing` yang mengompilasi rute di `config/routes.rb` menjadi ekspresi reguler terpadu menggunakan *Deterministic Finite Automaton* (DFA). Mesin ini menyelesaikan pencocokan rute dalam kompleksitas waktu $O(k)$ (di mana $k$ adalah panjang URI path), bukan $O(n)$ berdasarkan jumlah rute.
3. **Action Controller Metal**: Sub-komponen minimalis dari controller yang memangkas modul-modul Rails yang tidak dibutuhkan. Saat `ActionController::Base` mewarisi puluhan modul (seperti `MimeResponds`, `Flash`, `FormBuilder`), `ActionController::Metal` memberikan kontrol langsung ke eksekusi aksi dengan *overhead* mendekati nol.

---

### 4. Why
Memahami request pipeline hingga ke level Rack dan Action Dispatch sangat krusial dalam rekayasa aplikasi tingkat produksi:
- **Efisiensi Sumber Daya**: Operasi seperti autentikasi token murni, penolakan IP (*blocklisting*), atau manipulasi header CORS yang dieksekusi di level *Controller* menghabiskan ribuan alokasi objek Ruby yang memicu *Garbage Collection* (GC) *pause*. Memindahkannya ke *Rack Middleware* memangkas siklus CPU hingga 70% untuk permintaan yang ditolak.
- **Pencegahan Celana Keamanan**: Kegagalan memahami interaksi antara proxy terluar (Nginx/Cloudflare), server Puma, dan `ActionDispatch::RemoteIp` dapat menyebabkan *IP Spoofing*, membuka kerentanan pada mekanisme *rate limiting* berbasis IP.
- **Isolasi Kegagalan Sistem**: Memahami *lifecycle* request memungkinkan developer membangun mekanisme *fail-safe*, metrik pelacakan kustom (*APM instrumentation*), dan *graceful degradation* tepat di batas luar (*perimeter*) aplikasi.

---

### 5. What
Komponen arsitektural utama yang menyusun pipeline:

| Komponen | Peran Arsitektur | Lokasi / Ekstensi Kode |
| :--- | :--- | :--- |
| **Puma Web Server** | Menerima soket TCP/UNIX, parsing byte HTTP ke `env` Hash. | `puma/server.rb` |
| **`config.ru`** | Titik masuk Rack standar yang memanggil `Rails.application`. | Root aplikasi |
| **`Rails::Application`** | Subclass dari `Rails::Engine`. Berperan sebagai Rack App primer. | `config/application.rb` |
| **`ActionDispatch::MiddlewareStack`** | Rantai linked-list fungsional dari puluhan middleware. | `ActionDispatch::MiddlewareStack` |
| **`Journey::Router`** | Mengurai AST rute dan memetakan path HTTP ke controller target. | `ActionDispatch::Journey` |
| **`ActionDispatch::Request`** | Abstraksi OOP tingkat tinggi di atas `env` Hash. | Lapisan Controller |
| **`ActionController::Metal`** | Konteks eksekusi aksi tanpa redundansi fungsionalitas views. | `AbstractController::Base` |

---

### 6. How
Alur hidup eksekusi sebuah request HTTP di Rails berjalan melalui tahapan sekuensial berikut:

1. **Inisialisasi I/O & Rack Handoff**: Server Puma menerima koneksi pada thread pekerja, mengurai byte HTTP menjadi Hash `env`, lalu mengeksekusi `Rails.application.call(env)`.
2. **Middleware Traversal (Inbound)**: Request melintasi rantai middleware secara berurutan. Setiap middleware menerima `env`, menjalankan mutasi parsial jika perlu, lalu memanggil `@app.call(env)`.
   - *Security layer*: `ActionDispatch::HostAuthorization`, `ActionDispatch::SSL`.
   - *Network layer*: `ActionDispatch::RemoteIp` (resolusi IP nyata melalui validasi daftar proksi terpercaya).
   - *State layer*: `Rack::Session::Cookie`, `ActionDispatch::Cookies`.
3. **Route Matching via Journey**:
   - Request mencapai `ActionDispatch::Routing::RouteSet`.
   - `Journey::Router` memetakan path URI dan HTTP verb ke node rute tujuan menggunakan DFA state walker. Parameter path diekstraksi ke dalam `env['action_dispatch.request.path_parameters']`.
4. **Instansiasi Controller & Dispatch**:
   - Controller tujuan diinstansiasi secara dinamis melalui representasi internal endpoint.
   - Dispatcher mengeksekusi metode entrypoint: `endpoint.dispatch(action, request, response)`.
5. **Controller Processing Pipeline**:
   - `ActionController::Metal` menjalankan lifecycle callback `AbstractController::Callbacks` (`before_action`).
   - Action method dieksekusi, menghasilkan payload (JSON string, file stream, atau HTML dari *Action View*).
6. **Middleware Unwinding (Outbound)**:
   - Array tiga elemen `[status, headers, body]` dikembalikan ke tumpukan middleware secara mundur (unwinding).
   - Middleware seperti `Rack::ETag` atau `Rack::Deflater` memodifikasi header dan payload secara streaming atau buffering.
7. **Socket Writing**: Server Puma menulis array respons kembali ke soket TCP klien dan membersihkan konteks memori per-thread.

---

### 7. Analogy
Bayangkan request HTTP sebagai **truk kargo logistik** yang hendak masuk ke area gudang inti (Controller Action):
- **Soket Puma** adalah gerbang perbatasan fisik terluar yang menerima truk.
- **Rack Spec** adalah formulir manifes standar internasional yang wajib dimiliki setiap truk agar diizinkan masuk.
- **Middleware Stack** adalah serangkaian pos inspeksi di sepanjang jalan bebas hambatan:
  - *Pos 1 (SSL)*: Memeriksa apakah truk menggunakan jalur aman.
  - *Pos 2 (HostAuthorization)*: Memverifikasi izin plat nomor truk untuk memasuki teritori.
  - *Pos 3 (Cookies/Session)*: Membuka segel identitas pengemudi dan mencocokkannya dengan buku catatan logistik.
- **Journey Router** adalah menara pengatur jalur rel persimpangan jalan tol. Menara ini memeriksa alamat tujuan pada manifes dan secara instan mengarahkan tuas wesel rel ke dermaga bongkar-muat yang tepat tanpa harus memeriksa dermaga satu per satu.
- **Controller Action** adalah dermaga pemrosesan kargo di mana muatan dibongkar dan kargo baru (respons) dimuat kembali untuk dibawa pulang melewati jalur yang sama secara terbalik.

---

### 8. Diagram
```
+-----------------------------------------------------------------------------------+
|                           CLIENT / BROWSER / API CONSUMER                         |
+-----------------------------------------------------------------------------------+
                                         |
                                         | HTTP/1.1 or HTTP/2 Request
                                         v
+-----------------------------------------------------------------------------------+
|                        PUMA / FALCON WEB SERVER (Pthread)                         |
|  - Parse raw socket bytes                                                         |
|  - Construct Rack Environment Hash: env = { 'REQUEST_METHOD' => 'POST', ... }     |
+-----------------------------------------------------------------------------------+
                                         |
                                         | Rails.application.call(env)
                                         v
+-----------------------------------------------------------------------------------+
|                   ActionDispatch::MiddlewareStack (Outermost -> Innermost)        |
|                                                                                   |
|   +---------------------------------------------------------------------------+   |
|   | ActionDispatch::HostAuthorization                                         |   |
|   |   +-------------------------------------------------------------------+   |   |
|   |   | ActionDispatch::RemoteIp (Calculates client IP safely)            |   |   |
|   |   |   +-----------------------------------------------------------+   |   |   |
|   |   |   | Rack::Deflater (Gzip Compression)                         |   |   |   |
|   |   |   |   +---------------------------------------------------+   |   |   |   |
|   |   |   |   | ActionDispatch::Executor (Reloader / Thread Cleans)|   |   |   |   |
|   |   |   |   |   +-------------------------------------------+   |   |   |   |   |
|   |   |   |   |   | ActionDispatch::Cookies -> Session Store  |   |   |   |   |   |
|   |   |   |   |   |   +-----------------------------------+   |   |   |   |   |   |
|   |   |   |   |   |   | Custom Production Middlewares     |   |   |   |   |   |   |
|   |   |   |   |   |   |   +---------------------------+   |   |   |   |   |   |   |
|   |   |   |   |   |   |   | ActionDispatch::Routing   |   |   |   |   |   |   |   |
|   |   |   |   |   |   |   |   RouteSet -> Journey DFA |   |   |   |   |   |   |   |
+---+---+---+---+---+---+---+---+---------------------------+---+---+---+---+---+---+
                                              |
                                              | Match: "GET /api/v1/orders"
                                              | Resolve: OrdersController#index
                                              v
+-----------------------------------------------------------------------------------+
|                      ACTION CONTROLLER (Execution Context)                        |
|                                                                                   |
|   OrdersController < ActionController::Metal (or Base)                            |
|   +---------------------------------------------------------------------------+   |
|   | 1. Instantiate Controller Instance                                        |   |
|   | 2. Wrap `env` with `ActionDispatch::Request`                              |   |
|   | 3. Execute `AbstractController::Callbacks` (:before_action chains)       |   |
|   | 4. Invoke target action: `#index`                                         |   |
|   | 5. Process business logic (Interactors, Services, DB via AR)              |   |
|   | 6. Format Serialization (Raw JSON via Oj, Alba, or ActionView template)   |   |
|   +---------------------------------------------------------------------------+   |
|                                         |                                         |
|                                         | Returns: [status, headers, body]        |
|                                         v                                         |
+-----------------------------------------------------------------------------------+
                                         |
                                         | Unwinding back through Middleware Stack
                                         v
+-----------------------------------------------------------------------------------+
|                    PUMA: Writes Byte Stream to Client Socket                      |
+-----------------------------------------------------------------------------------+
```

---

### 9. Simple Example
Implementasi spesifikasi Rack murni tanpa Rails untuk memahami batas kontrak arsitektur dasar.

Simpan file berikut sebagai `config.ru`:

```ruby
# frozen_string_literal: true

# Middleware custom yang memodifikasi header respons dan menghitung waktu eksekusi
class ExecutionTimer
  def initialize(app)
    @app = app
  end

  def call(env)
    start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)
    
    # Forward request ke aplikasi atau middleware berikutnya
    status, headers, body = @app.call(env)
    
    end_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)
    duration = (end_time - start_time) * 1000 # konversi ke milidetik

    # Salin header untuk mutasi yang aman tanpa membekukan hash global
    new_headers = headers.dup
    new_headers['X-Internal-Runtime'] = format('%.3fms', duration)

    [status, new_headers, body]
  end
end

# Aplikasi Rack dasar
class BaseApplication
  def call(env)
    request_method = env['REQUEST_METHOD']
    path_info = env['PATH_INFO']

    if request_method == 'GET' && path_info == '/health'
      [
        200,
        { 'content-type' => 'application/json' },
        ['{"status":"pass","cluster":"edge-01"}']
      ]
    else
      [
        404,
        { 'content-type' => 'text/plain' },
        ['Route Not Found']
      ]
    end
  end
end

# Pipeline Composition
use ExecutionTimer
run BaseApplication.new
```

Jalankan langsung melalui terminal menggunakan gem rack:
```bash
gem install rack rackup puma
rackup config.ru -p 9292
curl -i http://localhost:9292/health
```

---

### 10. Practical Example
Berikut adalah implementasi *thread-safe production middleware* pada aplikasi Rails 7/8. Middleware ini berfungsi untuk memvalidasi *Tenant ID* dari header, mengisolasi konteks eksekusi tenant menggunakan `ActiveSupport::CurrentAttributes`, dan secara otomatis menolak request malformasi sebelum menyentuh alokasi controller apa pun.

#### 1. Definisi State Tenant
```ruby
# app/models/current.rb
# frozen_string_literal: true

class Current < ActiveSupport::CurrentAttributes
  attribute :tenant_id, :request_id
end
```

#### 2. Definisi Production-Grade Rack Middleware
```ruby
# lib/middleware/tenant_enforcer.rb
# frozen_string_literal: true

module Middleware
  class TenantEnforcer
    TENANT_HEADER = 'HTTP_X_TENANT_UUID'
    UUID_REGEX    = /\A[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\z/i
    EXCLUDED_PATH = %r{\A/up\z|\A/assets/|\A/favicon.ico}.freeze

    def initialize(app)
      @app = app
    end

    def call(env)
      # Bypass endpoint internal seperti health check & aset statis
      if EXCLUDED_PATH.match?(env['PATH_INFO'])
        return @app.call(env)
      end

      tenant_id = env[TENANT_HEADER]

      # Validasi presensi dan format UUID RFC 4122 tanpa alokasi Exception
      if tenant_id.nil? || !tenant_id.match?(UUID_REGEX)
        return render_rejection(
          status: 400,
          error_code: 'INVALID_OR_MISSING_TENANT_HEADER',
          message: 'Header X-Tenant-UUID wajib diisi dengan format UUID valid.'
        )
      end

      # Set thread-safe context
      Current.tenant_id = tenant_id
      Current.request_id = env['action_dispatch.request_id']

      # Eksekusi downstream middleware & controller pipeline
      @app.call(env)
    ensure
      # Reset state setelah eksekusi request selesai untuk mencegah cross-request pollution
      Current.reset
    end

    private

    def render_rejection(status:, error_code:, message:)
      body = {
        error: {
          code: error_code,
          message: message,
          timestamp: Time.now.utc.iso8601(3)
        }
      }.to_json

      [
        status,
        {
          'content-type' => 'application/json',
          'content-length' => body.bytesize.to_s,
          'cache-control' => 'no-store, no-cache'
        },
        [body]
      ]
    end
  end
end
```

#### 3. Registrasi pada Pipeline Rails
Letakkan middleware tepat sebelum perutean dimulai agar overhead downstream terminimalisir.

```ruby
# config/application.rb
require_relative "boot"
require "rails/all"
require_relative "../lib/middleware/tenant_enforcer"

module HighLoadApp
  class Application < Rails::Application
    config.load_defaults 7.1

    # Tempatkan Middleware TenantEnforcer sebelum ActionDispatch::Routing::RouteSet
    # Ini memastikan validasi terjadi sebelum eksekusi route parsing
    config.middleware.insert_before ActionDispatch::Routing::RouteSet, Middleware::TenantEnforcer
  end
end
```

---

### 11. Real World Example
#### Studi Kasus: Mitigasi Trafik Scraping & Pengurangan Memory GC pada Shopify / GitHub Scale

**Skenario**:
Platform API e-commerce skala besar menerima sekitar 120.000 request per detik (RPS). Sekitar 18% dari trafik tersebut merupakan bot usang atau request terorisasi yang mengirimkan header `User-Agent` usang atau request dengan format serialization JSON yang merusak parser Active Support.

**Masalah**:
Jika validasi bot dan header parsing dilakukan di controller Rails via `before_action :validate_client`:
1. Rails harus mengeksekusi routing `Journey`.
2. Rails mengalokasikan objek controller lengkap beserta seluruh modul yang di-*include* (`ActionController::Base`).
3. Objek alokasi mencapai 4.500–6.000 objek Ruby per request yang ditolak.
4. GC Run terpicu setiap beberapa ratus milidetik, menyebabkan *P99 Latency* melonjak drastis hingga >1.200ms.

**Solusi Arsitektural**:
Mereka mengekstrak seluruh proses inspeksi awal ke dalam sebuah **Early-Drop Rack Middleware** yang ditempatkan tepat setelah `ActionDispatch::HostAuthorization` (di lapis terluar pipeline Rails).

```ruby
# lib/middleware/bot_perimeter_defense.rb
class BotPerimeterDefense
  BLOCKED_AGENTS = /(scrapy|curl\/7\.1|python-requests\/0\.)/i.freeze

  def initialize(app, redis_pool)
    @app = app
    @redis_pool = redis_pool
  end

  def call(env)
    ua = env['HTTP_USER_AGENT']

    if ua.nil? || BLOCKED_AGENTS.match?(ua)
      # Mengembalikan respons dengan zero Ruby dynamic object allocation
      return [403, { 'content-type' => 'text/plain' }.freeze, ['Access Denied by Perimeter Shield'.freeze]]
    end

    @app.call(env)
  end
end
```

**Dampak Produksi**:
- **Alokasi Objek**: Berkurang dari ~5.000 objek menjadi 2 objek per request yang ditolak.
- **P99 Latency**: Turun dari 1.200ms menjadi 85ms di seluruh kluster server.
- **Kapasitas Server**: Kapasitas *throughput* per Puma pod meningkat 3,4 kali lipat tanpa penambahan infrastruktur CPU/RAM.

---

### 12. Trade-offs

| Pendekatan | Keuntungan (Pros) | Kerugian (Cons) | Kompleksitas | Dampak Performa |
| :--- | :--- | :--- | :--- | :--- |
| **Logic di Rack Middleware** | Eksekusi sangat cepat; melewati Controller instantiation; alokasi objek minimal; isolasi kegagalan request. | Tidak memiliki akses langsung ke helper Rails (e.g., `render`, cookie parsing otomatis jika ditaruh sebelum cookie middleware). | Tinggi (wajib mengelola thread-safety dan status serialisasi secara manual). | **Sangat Tinggi** (~5-10x lebih hemat CPU dibanding controller). |
| **Logic di `before_action` Controller** | Akses penuh ke Active Record, session, template views, responder helpers, dan dependensi domain. | Beban komputasi tinggi; seluruh rantai middleware dan instansiasi controller harus selesai dieksekusi terlebih dahulu. | Rendah (idiom standar konvensional Rails). | **Rendah** (memerlukan alokasi ribuan objek per request). |
| **Pemisahan via Rails Engine** | Isolasi modularitas fungsionalitas tinggi; dapat di-*mount* sebagai sub-path mandiri dengan middleware stack terisolasi. | Menambah lapisan delegasi; arsitektur dependensi antar engine berpotensi membingungkan tim. | Sangat Tinggi (pengaturan namespace, routes, dan isolated state). | **Moderat** (tergantung ketebalan stack dalam engine). |

---

### 13. When To Use
Gunakan manipulasi pada level **Rack Middleware / Engine Pipeline** jika Anda menghadapi skenario:
1. **Global Header Interception**: Menambahkan header keamanan (misal: *Strict-Transport-Security*, *Content-Security-Policy*, pelacakan *Distributed Tracing ID* via OpenTelemetry).
2. **Early Request Termination**: Otentikasi berbasis *API Key Signatures*, rate-limiting presisi, atau *IP Blocklisting*.
3. **Payload Transformation**: Dekompresi data kustom (*payload unpacking*) sebelum data tersebut diparsing oleh `ActionDispatch::Http::Parameters`.
4. **Health Check Endpoints**: Endpoint Kubernetes `liveness` dan `readiness` yang memerlukan respon berkecepatan mikrodetik tanpa menyentuh *database pool* Rails.

---

### 14. When NOT To Use
Jangan gunakan **Rack Middleware** untuk:
1. **Aturan Bisnis Domain Spesifik**: Seperti "Pengguna dengan status *suspended* tidak boleh melakukan checkout". Gunakan *Domain Service* atau *Controller Policy Objects* karena logic ini membutuhkan query Active Record dan konteks bisnis yang kaya.
2. **Operasi yang Memerlukan Format Templating**: Mengembalikan tampilan HTML kaya atau XML khusus. Menulis HTML generator manual di dalam middleware melanggar prinsip *Single Responsibility* dan menghilangkan ekosistem Action View.
3. **Mekanisme yang Bergantung Penuh pada Authorization Engine**: Seperti evaluasi *Pundit* atau *CanCanCan* yang memerlukan instansiasi model pengguna secara mendalam.

---

### 15. Common Mistakes
1. **Menyimpan State di Instance Variable Middleware**:
   ```ruby
   # FATAL THREAD-SAFETY BUG
   class UnsafeMiddleware
     def initialize(app)
       @app = app
     end

     def call(env)
       # BAD: @user_id dibagikan ke SEMUA THREAD di worker Puma yang sama!
       # Ini menyebabkan kebocoran sesi antar-user (Session Leaks).
       @user_id = env['HTTP_X_USER_ID'] 
       @app.call(env)
     end
   end
   ```
   *Solusi*: Middleware adalah *singleton instance* yang dipanggil oleh banyak thread sekaligus. Semua variabel yang berkaitan dengan request wajib bersifat lokal ke metode `call(env)` atau disimpan di thread-safe store seperti `CurrentAttributes`.

2. **Memodifikasi Hash `env` Global Tanpa Duplikasi yang Tepat**:
   Mengubah referensi `env` yang dibekukan (`frozen`) atau menimpa variabel kritis seperti `PATH_INFO` tanpa memahami implikasinya pada *Journey Router* akan menghasilkan `RoutingError` yang sulit dilacak.

3. **Membaca Request Body Berulang Kali (`env['rack.input']`)**:
   `env['rack.input']` adalah sebuah IO stream (`StringIO` atau `Tempfile`).
   ```ruby
   # BUG: Stream dibaca tanpa rewind!
   def call(env)
     raw_body = env['rack.input'].read # Pointer IO berpindah ke akhir stream
     # ActionDispatch nantinya membaca body kosong!
     @app.call(env)
   end
   ```
   *Solusi*: Selalu jalankan `env['rack.input'].rewind` segera setelah membaca dari IO stream.

---

### 16. Best Practices
Daftar periksa teknis untuk lingkungan produksi:
- [ ] **Thread-Safety Guaranteed**: Pastikan objek middleware tidak memiliki status termutasi (*stateless*) pada *instance variables* setelah fase `initialize`.
- [ ] **Stream Rewinding**: Jika membaca `env['rack.input']`, bungkus pembacaan di dalam `ensure` block untuk mengeksekusi `rewind`.
- [ ] **Freeze Static Constants**: String header, regex, dan pesan kegagalan harus berstatus `.freeze` untuk mencegah alokasi GC berulang.
- [ ] **Tepat Menentukan Posisi**: Gunakan `bin/rails middleware` untuk menginspeksi urutan dan gunakan `insert_before` atau `insert_after` secara kalkulatif.
- [ ] **Mematuhi Rack Body Protocol**: Kembalikan objek `body` yang merespons `#each`, `#close` (jika IO stream), dan pastikan penanganan streaming ditutup secara benar untuk mencegah kebocoran file descriptor soket.

---

### 17. Troubleshooting

#### 1. Masalah: `ActionDispatch::RemoteIp::IpSpoofAttackError`
- **Gejala**: Permintaan gagal dengan status 500 dan log mencatat: `IP spoofing attack frame detected`.
- **Akar Masalah**: Terdapat perbedaan antara header `X-Forwarded-For` dan `Client-Ip` yang dikirim oleh CDN/Load Balancer karena konfigurasi *trusted proxies* Rails tidak mengenali IP reverse proxy internal Anda.
- **Penyelesaian**: Konfigurasi subnet proksi terpercaya di `config/environments/production.rb`:
  ```ruby
  config.action_dispatch.trusted_proxies = [
    IPAddr.new("10.0.0.0/8"),
    IPAddr.new("172.16.0.0/12")
  ]
  ```

#### 2. Masalah: Header Modifikasi Tidak Terbaca di Controller
- **Gejala**: Anda menambahkan `env['HTTP_X_CUSTOM_HEADER'] = 'value'` di middleware, tetapi `request.headers['X-Custom-Header']` bernilai `nil`.
- **Akar Masalah**: Middleware Anda diletakkan *setelah* instansiasi objek `ActionDispatch::Request` pada layer routing.
- **Penyelesaian**: Jalankan `bin/rails middleware`, pastikan custom middleware Anda disisipkan sebelum `ActionDispatch::Routing::RouteSet`.

---

### 18. Exercise
1. **Analisis Middleware**: Jalankan perintah `bin/rails middleware` di aplikasi Rails Anda. Identifikasi posisi middleware `ActionDispatch::Cookies` relatif terhadap `ActionDispatch::Session::CookieStore`. Mengapa `Cookies` harus selalu berada sebelum `Session::CookieStore`?
2. **Pembuatan Middleware Profiler Sederhana**: Buatlah sebuah file middleware di `lib/middleware/payload_size_validator.rb` yang memeriksa header `Content-Length`. Jika ukuran body melebihi 2MB pada request `POST` atau `PUT`, middleware harus langsung mengembalikan response status `413 Payload Too Large` dalam format JSON tanpa melanjutkan request ke pipeline internal.

---

### 19. Challenge
Implementasikan sebuah **Atomic Distributed Token Bucket Rate Limiter** murni sebagai Rack Middleware dengan kriteria berikut:
1. **Letak Eksekusi**: Terpasang sebelum `ActionDispatch::Routing::RouteSet`.
2. **Dependensi Konkurensi**: Gunakan koneksi `ConnectionPool` ke Redis yang aman terhadap akses thread paralel Puma.
3. **Spesifikasi**:
   - Kapasitas ember: 100 token per IP.
   - Refill rate: 10 token per detik.
   - Mengembalikan HTTP 429 ketika token habis dengan menyertakan header `Retry-After` yang menghitung waktu pasti dalam detik hingga ember terisi token baru berikutnya.
   - Alokasi memori lokal Ruby harus mendekati nol: dilarang menginstansiasi objek `ActiveRecord` atau memanggil layer `ActionController`.
4. **Validasi**: Tulis spesifikasi pengujian integrasi berbasis `Rack::MockRequest` untuk memvalidasi presisi penghitungan saat diuji menggunakan simulasi *parallel burst* 200 request.

---

### 20. Summary
Pipeline request-response Rails adalah komposisi linear yang terstruktur dengan elegan di atas pondasi spesifikasi **Rack**. 

- Server web bertindak sebagai jembatan dari soket sistem operasi ke Ruby dengan mengonversi HTTP stream menjadi Hash `env`.
- Rantai **`ActionDispatch::MiddlewareStack`** mengeksekusi transformasi inkremental terhadap request dan response secara bertingkat.
- Mesin perutean **`Journey`** mengeksekusi pemetaan efisien berbasis automaton matematika tanpa pemindaian linear rute satu demi satu.
- **`ActionController`** hanyalah batas ujung dari perjalanan data tersebut untuk pengorganisasian domain logika.

Menguasai arsitektur internal ini mengubah cara pandang insinyur perangkat lunak terhadap ekosistem Rails: dari paradigma manipulasi framework "kotak hitam" (*black-box*) menjadi penguasaan penuh atas efisiensi komputasi, keandalan sistem berskala masif, dan optimasi arsitektural hingga ke tingkat instruksi mesin terendah pada tumpukan web.