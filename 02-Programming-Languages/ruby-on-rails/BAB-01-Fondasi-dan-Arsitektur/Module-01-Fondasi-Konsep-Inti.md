# Modul 01: Arsitektur Fundamental dan Request Lifecycle
## Bab 01: Filosofi Rails, Arsitektur MVC, dan Anatomi Request-Response Pipeline

---

### 1. Learning Objectives
Setelah menyelesaikan bab ini, Anda diharapkan mampu:
- **Menganalisis** filosofi inti Ruby on Rails (*Convention over Configuration*, *Don't Repeat Yourself*, dan *The Rails Doctrine*) serta implikasinya terhadap desain arsitektur perangkat lunak.
- **Mengurai** arsitektur *Model-View-Controller* (MVC) spesifik implementasi Rails, termasuk batas tanggung jawab (*separation of concerns*) antar komponen.
- **Memetakan** *end-to-end execution path* dari HTTP request mentah melalui Application Server (Puma), Rack Middleware stack, Router (`ActionDispatch`), Controller (`ActionController`), Model (`ActiveRecord`), hingga serialisasi View (`ActionView`/Jbuilder).
- **Mendiagnosis** dan **mengatasi** isu performa dan *leakage abstraction* pada siklus hidup *request-response* Rails.

---

### 2. Conceptual Foundation
Ruby on Rails adalah *full-stack web framework* berbasis Ruby yang dibangun di atas paradigma *Convention over Configuration* (CoC). Alih-alih mengharuskan rekayasawan menulis konfigurasi deklaratif XML/YAML yang masif untuk setiap relasi dan routing, Rails mengasumsikan sekumpulan konvensi standar (seperti penamaan kelas, tabel basis data, dan struktur direktori). 

Secara arsitektural, Rails memformalisasikan pola Model-View-Controller (MVC):
- **Model (`ActiveRecord`):** Membungkus logika bisnis, enkapsulasi state, dan persistensi data dengan pola *Active Record pattern* (Martin Fowler), di mana sebuah objek merepresentasikan baris dalam tabel basis data dan logika domain yang melekat padanya.
- **View (`ActionView`):** Menangani logika presentasi. Bertanggung jawab mengompilasi representasi data (HTML, JSON, XML) tanpa mengeksekusi *state-mutating operations*.
- **Controller (`ActionController`):** Bertindak sebagai koordinator (*orchestrator*). Mengurai input dari HTTP request, mengeksekusi *domain commands* via Model, dan menentukan representasi View yang tepat untuk direspons ke klien.

Di balik abstraksi MVC, fondasi Rails bertumpu pada **Rack**—antarmuka modular minimalis antara server web (seperti Puma) dan framework Ruby.

---

### 3. Why It Matters
Tanpa pemahaman yang presisi mengenai arsitektur internal Rails dan *underlying HTTP pipeline*, tim engineering sering kali terjebak dalam:
1. **Fat Controller / Anemic Domain Model:** Controller membengkak ribuan baris karena logika orkestrasi tercampur dengan persistensi dan integrasi pihak ketiga.
2. **"Rails Magic" Paralyzation:** Ketidakmampuan melakukan *debugging* saat terjadi anomali (misalnya middleware memodifikasi headers, atau *autoloading failure* akibat Zeitwerk naming convention) karena memandang Rails sebagai *black-box*.
3. **Suboptimal Throughput:** Salah mengonfigurasi interaksi antara web server multi-threaded (Puma) dan *database connection pool* (`ActiveRecord::Base.connection_pool`), yang menyebabkan thread starvation dan latensi tinggi.

Memahami siklus hidup request dari layer OS socket hingga Rails application kernel adalah prasyarat mutlak untuk membangun sistem berskala enterprise yang *resilient* dan *high-throughput*.

---

### 4. What It Is
Secara teknis, sebuah aplikasi Rails adalah objek *callable* berbasis Rack yang merespons metode `#call(env)`. Komponen penyusun utamanya adalah:

```
+-------------------------------------------------------------------+
|                           PUMA / WEBSERVER                        |
+-------------------------------------------------------------------+
                                  │
                       Puma IO Thread Pool
                                  │
                                  ▼
+-------------------------------------------------------------------+
|                        RACK MIDDLEWARE STACK                      |
| (ActionDispatch::HostAuthorization, Rack::Sendfile,               |
|  ActionDispatch::Executor, Rack::Session, Rack::MethodOverride...) |
+-------------------------------------------------------------------+
                                  │
                                  ▼
+-------------------------------------------------------------------+
|                    ROUTER (ActionDispatch::Routing)               |
|  - Tokenisasi URI & HTTP Method                                   |
|  - Ekstraksi Parameter (:id, :format)                             |
|  - Instansiasi Target Controller                                  |
+-------------------------------------------------------------------+
                                  │
                                  ▼
+-------------------------------------------------------------------+
|                   CONTROLLER (ActionController::Base)             |
|  - Callback Chain (before_action, around_action)                  |
|  - Strong Parameters Extraction                                   |
+-------------------------------------------------------------------+
           │                                             │
           ▼                                             ▼
+---------------------+                       +---------------------+
| MODEL (ActiveRecord)|                       | VIEW (ActionView)   |
| - Query Engine      |                       | - Template Compiler |
| - State Management  |                       | - Layout Resolution |
| - Validasi/Callback |                       | - Streaming/JSON    |
+---------------------+                       +---------------------+
```

- **Puma:** Web server HTTP/1.1 dan HTTP/2 concurrent yang menggunakan arsitektur hybrid multi-process dan multi-threaded.
- **Rack Middleware Stack:** Rantai komponen modular yang mengeksekusi transformasi *in-flight request* dan *out-flight response* (enkripsi cookie, proteksi CSRF, manajemen session).
- **Zeitwerk:** Thread-safe code loader engine yang memetakan nama file Ruby secara deterministik ke konstanta Ruby (Class/Module).

---

### 5. How It Works
Eksekusi sebuah HTTP request di Rails melewati tahapan deterministik berikut:

1. **Ingress & Parsing:** Puma menerima raw TCP connection, mem-parse HTTP payload, mengemasnya ke dalam Hash environment (`env`), dan memanggil `Rails.application.call(env)`.
2. **Middleware Traversal:** Request melewati array middleware secara serial via metode downstream `#call`. Komponen penting seperti `ActionDispatch::Executor` membungkus eksekusi ke dalam thread-safety context Rails (memvalidasi koneksi DB dan reload code jika environment = development).
3. **Routing Resolution:** `ActionDispatch::Journey::Router` mencocokkan pola URI path dan HTTP Verb terhadap konfigurasi `config/routes.rb`. Jika rute cocok, router mengarahkan payload ke aksi controller spesifik (misalnya `OrdersController#create`).
4. **Controller Orchestration:**
   - Instansiasi instance baru dari kelas controller target.
   - Pengeksekusian siklus filter/callback (`before_action`).
   - Eksekusi aksi (`#create`): parsing parameter melalui *Strong Parameters*, invoking domain methods pada model `ActiveRecord`.
5. **Database Interaction:** `ActiveRecord` mengonversi method chain menjadi abstract syntax tree (AST) via Arel, menghasilkan raw SQL, meminjam koneksi dari connection pool, dan menginstansiasi objek domain dari hasil recordset.
6. **Rendering & Serialization:** Controller memicu `render`. `ActionView` mengompilasi file template (ERB, Haml) ke dalam byte-compiled Ruby method untuk performa rendering optimal.
7. **Egress Pipeline:** Response dikemas dalam format triplet Rack standar `[status_code, headers_hash, response_body_enumerable]` dan diteruskan kembali ke atas melalui middleware stack, di mana header dimodifikasi (misal: penambahan caching headers atau kompresi gzip) sebelum Puma menuliskannya ke TCP socket.

---

### 6. Architecture & Flow Diagram

```
[HTTP Client: curl / Browser]
           │
           │  1. TCP Socket (Raw HTTP Request)
           ▼
┌────────────────────────────────────────────────────────┐
│ PUMA WEB SERVER                                        │
│ Reactor -> Worker Process -> Worker Thread Pool        │
└──────────────────────────┬─────────────────────────────┘
                           │
                           │ 2. env Hash: rack.input, REQUEST_METHOD, etc.
                           ▼
┌────────────────────────────────────────────────────────┐
│ RACK MIDDLEWARE PIPELINE                               │
│                                                        │
│  [ActionDispatch::HostAuthorization]                   │
│         │                                              │
│  [ActionDispatch::Static] (Serve /public assets)       │
│         │                                              │
│  [ActionDispatch::Executor] (Thread isolation context) │
│         │                                              │
│  [Rack::MethodOverride] (POST to PATCH/PUT handler)    │
│         │                                              │
│  [ActionDispatch::Cookies & Session Management]        │
└──────────────────────────┬─────────────────────────────┘
                           │
                           │ 3. Dispatched Rack Env
                           ▼
┌────────────────────────────────────────────────────────┐
│ ACTION DISPATCH: JOURNEY ROUTER                        │
│ Parse path -> Match pattern -> Extract params          │
└──────────────────────────┬─────────────────────────────┘
                           │
                           │ 4. Route Matched: OrdersController#show
                           ▼
┌────────────────────────────────────────────────────────┐
│ ACTION CONTROLLER SUBSYSTEM                            │
│                                                        │
│  - Execute Callback Stack (before_action)              │
│  - Sanitize parameters via Strong Parameters           │
│  - Execute action: OrdersController#show               │
│         │                                              │
│         │ 5. Domain Logic / DB Read                    │
│         ▼                                              │
│  ┌─────────────────────────┐                           │
│  │ ACTIVE RECORD DOMAIN    │                           │
│  │ - Acquire connection    │                           │
│  │ - Arel generates SQL    │                           │
│  │ - Query DB & Map Entities                           │
│  └─────────────────────────┘                           │
│         │                                              │
│         │ 6. Model objects initialized                 │
│         ▼                                              │
│  ┌─────────────────────────┐                           │
│  │ ACTION VIEW SUBSYSTEM   │                           │
│  │ - Compile template      │                           │
│  │ - Resolve Layout        │                           │
│  │ - Render HTML/JSON      │                           │
│  └─────────────────────────┘                           │
└──────────────────────────┬─────────────────────────────┘
                           │
                           │ 7. Return Tuple: [200, {'Content-Type' => 'text/html'}, [body]]
                           ▼
┌────────────────────────────────────────────────────────┐
│ MIDDLEWARE RESPONSE UNWINDING (Reverse Traversal)      │
│  - Set-Cookie parsing                                  │
│  - ETags calculation                                   │
│  - Response body compression (Deflater)                │
└──────────────────────────┬─────────────────────────────┘
                           │
                           │ 8. HTTP/1.1 200 OK (Wire Protocol)
                           ▼
[HTTP Client: curl / Browser]
```

---

### 7. Minimal Working Example
Berikut adalah implementasi web server Rails level fundamental tanpa dependensi generator standar, mengilustrasikan bagaimana Rails adalah aplikasi Rack murni. Simpan sebagai file `minimal_rails.rb`:

```ruby
# minimal_rails.rb
# Eksekusi via terminal: ruby minimal_rails.rb

require "bundler/inline"

# Inisialisasi dependensi secara inline untuk portabilitas pengujian
gemfile do
  source "https://rubygems.org"
  gem "rails", "~> 7.1.0"
  gem "puma"
end

require "action_controller/railtie"

class MinimalApp < Rails::Application
  config.hosts.clear # Nonaktifkan proteksi host checking untuk development
  config.secret_key_base = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
  config.eager_load = false
  config.logger = Logger.new($stdout)
  
  # Minimal routing inline
  routes.draw do
    root to: "ping#index"
    get "/inspect_env", to: "ping#inspect_env"
  end
end

class PingController < ActionController::Base
  def index
    render plain: "PONG - Rails Core Runtime Operasional"
  end

  def inspect_env
    # Mengekstrak status low-level rack environment
    render json: {
      request_method: request.method,
      server_software: request.headers["SERVER_SOFTWARE"],
      rails_version: Rails.version,
      rack_version: Rack::RELEASE
    }
  end
end

# Jalankan Rails Application via Puma webserver
require "rack/handler/puma"
Rack::Handler::Puma.run(MinimalApp, Port: 3000)
```

Untuk menguji:
```bash
ruby minimal_rails.rb
# Pada tab terminal lain:
curl -i http://localhost:3000/inspect_env
```

---

### 8. Real-World Practical Example
Struktur implementasi arsitektur enterprise untuk pemrosesan order inventaris e-commerce dengan decoupling antara domain logic, persistence, dan boundary controller.

#### 1. Routing Definition (`config/routes.rb`)
```ruby
# config/routes.rb
Rails.application.routes.draw do
  namespace :api do
    namespace :v1 do
      resources :orders, only: [:create, :show]
    end
  end
end
```

#### 2. Domain Model & Migration (`app/models/order.rb`)
```ruby
# db/migrate/20231027000001_create_orders.rb
class CreateOrders < ActiveRecord::Migration[7.1]
  def change
    create_table :orders, id: :uuid do |t|
      t.string :order_number, null: false, index: { unique: true }
      t.decimal :total_amount, precision: 12, scale: 2, null: false
      t.string :status, default: "pending", null: false
      t.jsonb :line_items, default: {}, null: false

      t.timestamps
    end
    add_index :orders, :status
  end
end

# app/models/order.rb
class Order < ApplicationRecord
  enum status: {
    pending: "pending",
    processing: "processing",
    completed: "completed",
    failed: "failed"
  }, _default: "pending"

  validates :order_number, presence: true, uniqueness: true
  validates :total_amount, numericality: { greater_than_or_equal_to: 0 }
  
  before_validation :generate_order_number, on: :create

  private

  def generate_order_number
    self.order_number ||= "ORD-#{SecureRandom.alphanumeric(8).upcase}"
  end
end
```

#### 3. Controller Implementation (`app/controllers/api/v1/orders_controller.rb`)
```ruby
# app/controllers/api/v1/orders_controller.rb
module Api
  module V1
    class OrdersController < ApplicationController
      # Mencegah mass-assignment vulnerability menggunakan Strong Parameters
      # Error handling deterministik terpusat
      rescue_from ActiveRecord::RecordNotFound, with: :record_not_found
      rescue_from ActionController::ParameterMissing, with: :bad_request

      def show
        order = Order.find(params[:id])
        render json: OrderSerializer.new(order).as_json, status: :ok
      end

      def create
        order = Order.new(order_params)

        if order.save
          render json: OrderSerializer.new(order).as_json, status: :created
        else
          render json: { errors: order.errors.full_messages }, status: :unprocessable_entity
        end
      end

      private

      def order_params
        params.require(:order).permit(:total_amount, line_items: [:sku, :quantity, :unit_price])
      end

      def record_not_found(exception)
        render json: { error: exception.message }, status: :not_found
      end

      def bad_request(exception)
        render json: { error: exception.message }, status: :bad_request
      end
    end
  end
end
```

#### 4. Serializer View Layer (`app/serializers/order_serializer.rb`)
```ruby
# app/serializers/order_serializer.rb
class OrderSerializer
  def initialize(order)
    @order = order
  end

  def as_json
    {
      id: @order.id,
      order_number: @order.order_number,
      status: @order.status,
      total_amount: @order.total_amount.to_f,
      line_items: @order.line_items,
      created_at: @order.created_at.iso8601
    }
  end
end
```

---

### 9. Deep Dive: Edge Cases & Gotchas

#### 1. Mutasi Thread-Unsafe pada Controller Context
Puma mengeksekusi request secara multi-threaded di dalam proses yang sama. Controller diinstansiasi ulang per request, tetapi **Class variables (`@@var`)** atau modifikasi state pada singleton object/konstanta adalah thread-unsafe.
```ruby
# JANGAN LAKUKAN INI:
class ProductsController < ApplicationController
  @@cached_tax_rate = 0.11 # Race condition antar thread Puma!

  def calculate_tax
    @@cached_tax_rate = params[:rate].to_f # Mutasi ini merusak request dari thread lain
  end
end

# MITIGASI: Gunakan RequestStore atau thread-isolated attributes:
class Current < ActiveSupport::CurrentAttributes
  attribute :tax_rate # Terisolasi di dalam Thread.current[:current_attributes]
end
```

#### 2. Perilaku Autoloading Zeitwerk (File Naming Conventions)
Zeitwerk memetakan representasi path ke identifier konstanta:
- Path: `app/services/payment_gateway/v1/processor.rb`
- Konstanta yang wajib diekspos: `PaymentGateway::V1::Processor`

Jika nama file adalah `processor.rb` namun deklarasi kelasnya adalah `class V1::Processor`, aplikasi akan melempar error:
`Zeitwerk::NameError: expected file ... to define constant ...` pada saat runtime atau eager-load boot.

#### 3. Middleware Ordering Trap
Jika menaruh custom middleware yang membutuhkan session data di atas `ActionDispatch::Session::CookieStore`, maka session payload tidak akan bisa dibaca:
```ruby
# config/application.rb
# FATAL: CustomAuthMiddleware dieksekusi SEBELUM Session cookies di-decrypt
config.middleware.insert_before ActionDispatch::Cookies, CustomAuthMiddleware

# BENAR:
config.middleware.insert_after ActionDispatch::Session::CookieStore, CustomAuthMiddleware
```

---

### 10. Performance Considerations & Profiling

#### Database Connection Pool Sizing
Jika Puma dikonfigurasi dengan $N$ threads per worker, koneksi basis data harus dikonfigurasi minimal sama besarnya dengan ukuran thread pool untuk menghindari thread terblokir menunggu koneksi data (`ActiveRecord::ConnectionTimeoutError`).

Perhitungan Pool Minimum:
$$\text{DB Pool Size} = \text{Puma Max Threads} \times \text{Puma Worker Processes}$$

Konfigurasi pada `config/database.yml`:
```yaml
production:
  adapter: postgresql
  encoding: unicode
  pool: <%= ENV.fetch("RAILS_MAX_THREADS") { 5 } %>
  timeout: 5000
```

#### Memory Bloat via Large ActiveRecord Instantiations
Memuat 10.000 record menggunakan `Order.all.to_a` mengalokasikan ratusan ribu objek Ruby (`Hash`, `String`, internal attributes), memicu Ruby Garbage Collection (GC) berjalan agresif dan meningkatkan latency response secara signifikan.

*Optimasi Batching:*
```ruby
# Anti-pattern: Menghabiskan memory buffer
Order.where(status: 'pending').each { |o| o.process! }

# Production pattern: Cursor pagination via SQL batches (default 1000 record per batch)
Order.where(status: 'pending').find_each(batch_size: 1000) do |order|
  order.process!
end
```

---

### 11. Security Implications

```
+-----------------------------------------------------------+
|                      ATTACK SURFACE                       |
+-----------------------------------------------------------+
| 1. Mass Assignment -> Mengubah attribute privat (e.g. role)|
| 2. CSRF (Cross-Site Request Forgery)                     |
| 3. Unchecked Parameter Parsing (SQL Injection)            |
+-----------------------------------------------------------+
```

1. **Mass Assignment:** Rails mewajibkan penggunaan *Strong Parameters*. Jangan pernah memanggil `.permit!` secara global pada model yang memiliki atribut sensitif (misalnya `is_admin`, `balance`).
   ```ruby
   # EKSPLOITATIF:
   params.require(:user).permit! 
   
   # TERPROTEKSI:
   params.require(:user).permit(:username, :email)
   ```
2. **CSRF Protection:** Untuk aplikasi server-side rendered, modul `ActionController::RequestForgeryProtection` menyisipkan token acak berbasis session di meta tags dan hidden fields. Untuk pure JSON REST API, gunakan `ActionController::API` (bukan `ActionController::Base`), karena API berbasis token header (JWT/Bearer) tidak rentan terhadap cookie-based CSRF exploit.
3. **Parameter Injection:** ActiveRecord memitigasi SQL Injection secara *out-of-the-box* dengan *parameterized queries*:
   ```ruby
   # RENTAN:
   Order.where("order_number = '#{params[:id]}'") 

   # AMAN (Prepared Statements):
   Order.where(order_number: params[:id])
   ```

---

### 12. Architectural Trade-offs & Alternatives

| Kriteria | Rails MVC Monolith | Modular Monolith (Packwerk) | Decoupled API + SPA (React/Rails API) |
| :--- | :--- | :--- | :--- |
| **Development Velocity** | **Sangat Tinggi**. Konvensi terpusat meminimalisir glue code. | **Tinggi**. Menjaga batas domain jelas seiring bertambahnya tim. | **Sedang**. Duplikasi tipe data dan kontrak API ganda. |
| **System Complexity** | **Rendah**. Satu codebase, deployment atomic. | **Sedang**. Enforcing modul via boundary analyzers. | **Tinggi**. Stateful auth, CORS, deployment independen. |
| **Latency / TTFB** | **Sangat Rendah**. Server-Side Rendered (HTML over the wire). | **Sangat Rendah**. In-memory communication antar module. | **Sedang/Tinggi**. Extra network roundtrips via JSON API serialization. |
| **Scaling Boundaries** | Scaling horizontal komputasi (proses/kontainer). | Scaling domain codebases terisolasi. | Scaling UI dan Backend secara independen. |

---

### 13. Best Practices & Idiomatic Patterns
- **Skinny Controllers, Focused Models/Services:** Controller hanya mengekstrak parameter, menginstansiasi objek koordinasi, dan merender view.
- **Convention-based Path Naming:** Gunakan resource routing standar:
  `index`, `show`, `new`, `create`, `edit`, `update`, `destroy`. Hindari rute *ad-hoc* seperti `/orders/process_payment_now`.
- **Query Objects untuk Logic Database yang Kompleks:** Hindari penulisan scope chaining yang terlalu panjang di controller.
- **Null Object Pattern:** Gunakan untuk mengeliminasi defensive coding yang penuh dengan conditional `if object.nil?`.

Contoh Idiomatic Query Object:
```ruby
# app/queries/orders/high_value_pending_query.rb
module Orders
  class HighValuePendingQuery
    def self.call(relation = Order.all, threshold: 10_000)
      relation
        .where(status: :pending)
        .where("total_amount >= ?", threshold)
        .order(total_amount: :desc)
    end
  end
end

# Penggunaan di Controller:
orders = Orders::HighValuePendingQuery.call
```

---

### 14. Anti-patterns & Code Smells to Avoid

#### 1. The Controller Logic Garbage Dump
Menempatkan logika third-party HTTP calls langsung di dalam controller action.
```ruby
# ANTI-PATTERN:
class CheckoutController < ApplicationController
  def checkout
    # Mengikat HTTP cycle Rails dengan latency payment provider
    Stripe::Charge.create(...) 
    OrderMailer.confirmation(order).deliver_now # Blocking!
  end
end

# PATTERN PERBAIKAN:
class CheckoutController < ApplicationController
  def checkout
    CheckoutProcessor.call(order_params) # Service Object
    OrderMailer.confirmation(order).deliver_later # Asinkron via ActiveJob
  end
end
```

#### 2. Hidden Side-effects via ActiveRecord Callbacks
Menggunakan callback seperti `after_create` atau `after_save` untuk memicu aksi domain independen (seperti pengiriman email, logging eksternal, atau billing). Hal ini menyebabkan model tightly coupled, lambat diuji via unit test, dan rawan transactional rollback loop.

---

### 15. Testing Strategies & Test Implementation
Pengujian arsitektur MVC Rails memanfaatkan tingkatan piramida tes:
- **Model Tests (`ActiveSupport::TestCase`):** Memvalidasi logika bisnis, constraints, dan query.
- **Request Tests (`ActionDispatch::IntegrationTest`):** Menguji end-to-end request lifecycle secara penuh (Router $\to$ Middleware $\to$ Controller $\to$ View) tanpa mock server.

#### Implementasi Request Test (`test/controllers/api/v1/orders_controller_test.rb`)
```ruby
require "test_helper"

class Api::V1::OrdersControllerTest < ActionDispatch::IntegrationTest
  setup do
    @valid_payload = {
      order: {
        total_amount: 1500.50,
        line_items: [
          { sku: "SKU-PRO-01", quantity: 2, unit_price: 750.25 }
        ]
      }
    }
  end

  test "POST #create mengembalikan 201 Created dengan payload JSON yang valid" do
    assert_difference("Order.count", 1) do
      post api_v1_orders_url, 
           params: @valid_payload, 
           as: :json
    end

    assert_response :created
    json_response = JSON.parse(response.body)

    assert_not_nil json_response["id"]
    assert_equal 1500.50, json_response["total_amount"]
    assert_equal "pending", json_response["status"]
    assert_match(/^ORD-/, json_response["order_number"])
  end

  test "POST #create mengembalikan 422 Unprocessable Entity ketika data tidak valid" do
    invalid_payload = { order: { total_amount: -10 } }

    assert_no_difference("Order.count") do
      post api_v1_orders_url, params: invalid_payload, as: :json
    end

    assert_response :unprocessable_entity
    json_response = JSON.parse(response.body)
    assert_includes json_response["errors"], "Total amount must be greater than or equal to 0"
  end
end
```

---

### 16. Operational & Observability Considerations
Rails memancarkan instrumentasi terperinci secara internal menggunakan `ActiveSupport::Notifications`. 

#### 1. Structured Logging Setup
Format log default Rails tidak ramah agregator log mesin (seperti Datadog, ELK). Konfigurasikan output JSON di production:
```ruby
# config/environments/production.rb
config.log_tags = [ :request_id ]
config.logger = ActiveSupport::Logger.new(STDOUT)
  .tap  { |logger| logger.formatter = ::Logger::Formatter.new }
  .then { |logger| ActiveSupport::TaggedLogging.new(logger) }
```

#### 2. Key Telemetry Metrics
Monitor metrik-metrik berikut pada level Puma dan Rails runtime:
- `Puma.backlog`: Jumlah connection socket yang mengantre di kernel TCP queue sebelum diambil oleh thread. Jika $> 0$, Puma kekurangan thread/worker.
- `sql.active_record`: Waktu eksekusi DB query per request cycle.
- `process_action.action_controller`: Total request execution time, terbagi atas `view_runtime`, `db_runtime`, dan `controller_runtime`.

---

### 17. Integration Points
- **Web Interface:** Puma bertindak sebagai Reverse Proxy downstream target dari NGINX atau AWS Application Load Balancer (ALB).
- **Socket Passing:** Menggunakan UNIX domain sockets (`unix:///tmp/puma.sock`) alih-alih local TCP loopback (`127.0.0.1:3000`) untuk komunikasi inter-process NGINX-to-Puma guna mengurangi context switching dan alokasi port TCP.
- **Ruby VM Execution:** Rails berjalan di atas standard MRI (CRuby). Eksekusi thread dibatasi oleh Global VM Lock (GVL) untuk CPU-bound tasks, namun I/O-bound operations (Database queries, HTTP calls) mengeksekusi *release GVL*, memungkinkan konkurensi Puma multi-threaded berjalan efisien.

---

### 18. Summary & Key Takeaways
- Rails bukan sekadar kumpulan library; Rails adalah *framework opiniated* yang mengadopsi MVC secara kaku melalui konvensi nama dan struktur direktori deterministik.
- Sebuah request HTTP diproses dalam format linear: **Client $\to$ Puma Socket $\to$ Rack Middleware Stack $\to$ Journey Router $\to$ Controller $\to$ ActiveRecord/Business Engine $\to$ View Serialization $\to$ Unwinding Rack Stack $\to$ Client**.
- Controller adalah gerbang orkestrasi; controller tidak boleh memuat logika kalkulasi domain yang kompleks atau eksekusi query raw berlebihan.
- Arsitektur Puma berbasis multithreading mengharuskan seluruh kode Rails aplikasi bersifat *thread-safe*: hindari state mutasi pada level class/singleton scope.

---

### 19. Challenge Exercise

#### Problem Statement:
Sebuah API endpoints Rails yang mengembalikan data detail pesanan (`GET /api/v1/orders/:id`) mengalami lonjakan latency (P99 $> 4$ detik) dan memory leak saat memproses data order yang memiliki banyak nested `line_items`.

Diberikan kode bermasalah:
```ruby
# app/controllers/api/v1/orders_controller.rb
class Api::V1::OrdersController < ApplicationController
  def show
    @order = Order.find(params[:id])
    @@last_accessed_order = @order # Memory leak & Thread safety issue
    
    # Nested iterations memicu query massal dan alokasi string repetitif
    items = []
    @order.line_items.each do |item|
      items << {
        name: item["sku"],
        price: item["unit_price"],
        tax: item["unit_price"] * 0.11
      }
    end
    
    render json: { order: @order, items: items }
  end
end
```

#### Tugas Anda:
1. Identifikasi dan jelaskan 3 pelanggaran arsitektur fundamental Rails dan problem konkurensi pada kode di atas.
2. Refaktorisasi endpoint ini dengan memisahkan logic komputasi ke presenter/serializer independen.
3. Pastikan thread-safety terjamin secara absolut di lingkungan multi-threaded Puma.
4. Tulis satu unit request test untuk memvalidasi performa dan validitas respon JSON yang dihasilkan.