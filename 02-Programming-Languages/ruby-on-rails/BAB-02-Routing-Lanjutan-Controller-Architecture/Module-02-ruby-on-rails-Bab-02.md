# Kurikulum Rekayasa Perangkat Lunak Enterprise: Ruby on Rails
## Bab 02: Routing Lanjutan & Controller Architecture
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis dan Membongkar Engine Routing Rails**: Memahami secara matematis dan teknis bagaimana Journey Engine mengompilasi rute menjadi *Deterministic Finite Automaton* (DFA) dan *Abstract Syntax Tree* (AST) untuk optimasi pencarian rute $O(k)$ di mana $k$ adalah panjang URI path.
2. **Mengimplementasikan Advanced Routing Architecture**: Merancang *dynamic constraints*, *routing lambdas*, *route engines mounting*, *scoped localized routing*, serta custom route mappers yang meminimalisir alokasi memori saat boot time.
3. **Mendekonstruksi Hirarki Action Controller**: Menguasai arsitektur internal dari `AbstractController::Base`, `ActionController::Metal`, hingga `ActionController::API` dan `ActionController::Base`, serta memilih basis controller yang optimal untuk rasio *throughput-to-latency*.
4. **Menguasai Filter Chain Internals & Optimization**: Menganalisis *callback graph* yang dikompilasi oleh `ActiveSupport::Callbacks`, mengeliminasi *overhead dynamic dispatch*, serta mencegah jebakan eksekusi filter yang redundan.
5. **Mengamankan dan Memvalidasi State dengan Advanced Strong Parameters**: Mengonfigurasi sanitasi parameter berlapis (*deeply nested polymorphic attributes*), mengisolasi parameter mutasi, dan mencegah kerentanan *mass-assignment*.
6. **Membangun Real-Time HTTP Streams**: Mengimplementasikan `ActionController::Live` untuk *Server-Sent Events* (SSE) dengan proteksi terhadap *concurrency thread-pool exhaustion* pada web server Puma.
7. **Menerapkan HTTP Conditional Caching Level Enterprise**: Mengonfigurasi *freshness validation* melalui ETag digest dan Last-Modified timestamp (`fresh_when`, `stale?`) guna memangkas *database I/O* dan beban transmisi jaringan.
8. **Mendesain Decoupled Controller Architecture**: Mentransformasi *Fat Controller* anti-pattern menjadi arsitektur modular enterprise berbasis *Service Objects*, *Form Objects*, *Query Objects*, dan *Result Monads* (`Dry::Monads` style).

---

### 2. Prerequisite

Sebelum menempuh modul ini, peserta wajib menguasai:
*   **Ruby Metaprogramming & Internals**: Pemahaman mendalam mengenai method synthesis (`define_method`, `class_eval`), `Module#prepend`, block binding, closure, serta alokasi memori Ruby Object (RVALUE dan GC compaction).
*   **Spesifikasi Rack (Rack Specification v2/v3)**: Pemahaman siklus hidup Rack environment hash (`env`), Rack tuple responses `[status, headers, body]`, dan penyusunan Rack middleware chain.
*   **Protokol HTTP/1.1 & HTTP/2**: RFC 7232 (Conditional Requests: `If-None-Match`, `If-Modified-Since`), RFC 7234 (Caching), RFC 7540 (Multiplexing & Streaming primitives).
*   **Dasar-dasar Routing & MVC Rails**: Penggunaan dasar `resources`, `namespace`, serta filter standar (`before_action`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Journey Routing Engine: AST & State Machine

Rails tidak menggunakan pencocokan *linear array regex* konvensional untuk routing. Sejak Rails 3.2 hingga versi modern (Rails 7/8), subsistem routing `ActionDispatch::Routing::RouteSet` didelegasikan ke internal engine bernama **Journey**.

```
URI Path Input: "/organizations/acme/projects/42"
                      │
                      ▼
     ┌──────────────────────────────────┐
     │ Journey Scanner (Lexer / Token)  │
     └──────────────────────────────────┘
                      │ Tokens: [SLASH, LITERAL("organizations"), SLASH, ...]
                      ▼
     ┌──────────────────────────────────┐
     │       Journey Parser (AST)       │
     └──────────────────────────────────┘
                      │ AST (Nodes: Cat, Slash, Symbol, Literal)
                      ▼
     ┌──────────────────────────────────┐
     │ Glushkov / Thompson Construction │
     └──────────────────────────────────┘
                      │ Non-deterministic Finite Automaton (NFA)
                      ▼
     ┌──────────────────────────────────┐
     │     Subset Construction (DFA)    │
     └──────────────────────────────────┘
                      │ Deterministic Finite Automaton
                      ▼
              Match Evaluator ──► Dispatch ke Rack Target
```

1. **Tokenisasi & Parsing AST**: String rute di-parse menjadi AST. Contoh rute `/users/:id(.:format)` direpresentasikan sebagai node tree:
   * Node `Cat` (penggabungan)
   * Node `Slash` (`/`)
   * Node `Literal` (`"users"`)
   * Node `Symbol` (`:id`)
   * Node `Group` yang membungkus format opsional.
2. **Kompilasi DFA**: AST dikonversi menjadi NFA melalui algoritma Glushkov, kemudian diubah menjadi DFA (Deterministic Finite Automaton). DFA memastikan bahwa proses evaluasi rute berlangsung dalam kompleksitas $O(k)$ terhadap panjang path URI, terlepas dari apakah aplikasi memiliki 50 rute atau 5.000 rute.
3. **Route Constraints Injection**: Ketika *constraint* dinamis ditambahkan (misal: validasi UUID atau inspeksi subdomain via database), Journey memisahkan rute menjadi dua segmen: *Path Matcher* (DFA) dan *Parameter/Request Constraint Evaluator*. Constraint class atau lambda dievaluasi langsung di context Rack sebelum rute dialokasikan ke controller dispatcher.

#### 3.2 Dekonstruksi Action Controller: Metal hingga Base

Hirarki controller Rails dirancang berbasis modularitas *ancestor chain* menggunakan concern ActiveSupport.

```
                  ┌───────────────────────────────┐
                  │    AbstractController::Base   │
                  └──────────────┬────────────────┘
                                 │ Provides: Action dispatch, view rendering context
                                 ▼
                  ┌───────────────────────────────┐
                  │    ActionController::Metal    │
                  └──────────────┬────────────────┘
                                 │ Provides: Rack interface (response, request)
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
┌───────────────────────────────┐       ┌────────────────────────────────┐
│     ActionController::API     │       │    ActionController::Base      │
│  (Optimal for Microservices)  │       │  (Full-stack Web Architecture) │
└───────────────────────────────┘       └────────────────────────────────┘
 - ActionController::Rendering           - Menghimpun seluruh modul API +
 - ActionController::StrongParameters    - ActionController::Flash
 - ActionController::DataStreaming       - ActionController::Cookies
 - ActionController::Rescue              - ActionView::Layouts & Rendering
                                         - ActionController::RequestForgeryProtection
```

*   `AbstractController::Base`: Menyediakan pondasi logika controller murni tanpa ketergantungan pada HTTP. Menangani mekanisme `action_name`, argumen dispatch, dan konteks komputasi view.
*   `ActionController::Metal`: Titik temu antara `AbstractController` dengan HTTP via Rack. Membaca hash `env`, menginstansiasi objek `ActionDispatch::Request` dan `ActionDispatch::Response`. Memiliki footprint memori yang sangat kecil, ideal untuk micro-endpoint dengan kebutuhan throughput tinggi.
*   `ActionController::API`: Ditargetkan untuk REST/JSON API. Menghilangkan layer-layer yang tidak diperlukan oleh API murni seperti CSRF protection (`RequestForgeryProtection`), Cookie store, Flash messages, dan layout view resolver.
*   `ActionController::Base`: Implementasi monolitik standar yang menyertakan seluruh modul fungsionalitas UI, Flash, Asset Pipeline helpers, template engines, dan form builder integration.

#### 3.3 Anatomi Filter Chain & Callback Compilation

Filter (`before_action`, `around_action`, `after_action`) dibangun di atas `ActiveSupport::Callbacks`. Rails tidak melakukan iterasi array dinamis pada setiap request. Sebaliknya, saat inisialisasi class atau request pertama (tergantung mode caching class), Rails mengompilasi callback chain menjadi sebuah blok/method Ruby tunggal.

*   Eksekusi method yang terkompilasi ini bekerja layaknya teknik *nested closures* (*onion architecture*).
*   Jika salah satu callback pada `before_action` melakukan `render` atau `redirect_to`, proses halted terjadi: eksekusi rantai callback dihentikan seketika melalui mekanisme pelemparan internal symbol (`throw :abort`), mencegah eksekusi action target dan callback berikutnya.
*   *Overhead* terjadi ketika developer menyusun callback yang terlalu panjang atau memodifikasi state antar callback, yang meningkatkan *cyclomatic complexity* dan menyulitkan pelacakan alur eksekusi aplikasi secara deterministik.

#### 3.4 Action Controller Live & Asynchronous Streaming Architecture

Secara default, response HTTP di Rails bersifat *buffered*: seluruh output dikumpulkan dalam buffer memory, kemudian di-*flush* sebagai satu kesatuan response body. 

Modul `ActionController::Live` mengubah perilaku ini:
*   Membungkus response body ke dalam `ActionController::Live::Buffer` yang thread-safe.
*   Setiap pemanggilan `response.stream.write(data)` langsung memicu flushing chunk data ke socket web server (Puma) melalui HTTP/1.1 *Chunked Transfer Encoding*.
*   **Peringatan Threading**: Action dijalankan di dalam thread terpisah dari worker utama Puma. Hal ini berarti connection pool database (ActiveRecord) harus dikelola secara eksplisit: kegagalan menutup koneksi ActiveRecord di dalam thread stream akan memicu *Database Connection Pool Exhaustion*.

---

### 4. Why & What

| Pendekatan | Karakteristik Teknis | Keuntungan | Kerugian & Batasan |
| :--- | :--- | :--- | :--- |
| **Fat Controller (Konvensional)** | Seluruh business logic, query ActiveRecord, notifikasi, dan parameter handling ditulis langsung di action controller. | Cepat dibuat untuk prototyping; pemahaman awal yang rendah. | Pelanggaran SRP (Single Responsibility Principle); pengujian unit lambat (harus memicu controller test); rawan race conditions; maintainability buruk. |
| **Slim Controller + Service Objects** | Controller hanya bertindak sebagai orkestrator; business logic dipindahkan ke plain Ruby classes (PORO) atau Interactor. | Business logic mudah diuji secara modular tanpa HTTP context; *reusable* antar channel (CLI, Webhook, REST, GraphQL). | Menambah abstraksi; boilerplate kode meningkat jika tidak menggunakan framework monad atau pipeline yang konsisten. |
| **Form Object + Query Object** | Sanitasi input kompleks dipisahkan ke Form Object; query database kompleks dipisahkan ke Query Object. | Isolasi validasi multi-model; query ActiveRecord terenkapsulasi dan mudah dioptimalkan (*anti-N+1*). | Memerlukan arsitektur mapping manual antara form object dan persistensi model jika tidak terstandarisasi. |
| **ActionController::Live (SSE)** | Mengirim data ke client secara terus-menerus melalui koneksi persistent HTTP. | Latensi real-time rendah tanpa overhead protokol WebSocket; integrasi mudah dengan EventSource di browser. | Menahan (holds) Puma worker thread; risiko *thread exhaustion* pada load tinggi; membutuhkan penanganan koneksi DB manual. |

---

### 5. How (Workflow Detail)

Berikut adalah detail tahapan aliran eksekusi request tingkat rendah dari Rack Middleware hingga Controller Action:

```
[Incoming HTTP Request]
         │
         ▼
[Puma / Falcon Web Server]
         │ Parsing HTTP stream menjadi Rack env hash
         ▼
[ActionDispatch::Routing::RouteSet (Journey Engine)]
         │ 1. Evaluasi Dynamic Constraints & Lambdas
         │ 2. Pencocokan DFA AST Matcher
         │ 3. Identifikasi Controller, Action, Path Parameters
         ▼
[Controller Factory / Dispatcher]
         │ Instansiasi instance Controller baru (contoh: Api::V1::OrdersController)
         ▼
[ActionController::Metal#dispatch(action, request, response)]
         │ Inisialisasi request context, headers, params parsing
         ▼
[ActiveSupport::Callbacks Pipeline (Filter Chain)]
         │
         ├───► before_action Hooks (Auth, Rate Limiting, Constraint checks)
         │     └─ (Jika halted via render/redirect -> Lompat ke response formatting)
         │
         ├───► action execution (Method invocations)
         │     ├─ Parameters permitted via Strong Parameters
         │     ├─ Interactor / Service execution
         │     └─ Conditional GET Evaluation (fresh_when / stale?)
         │
         └───► after_action Hooks (Auditing, Custom Header Appends)
         │
         ▼
[Response Pipeline & Serialization]
         │ Serialisasi Payload (JSON, HTML Chunk, SSE Stream Buffer)
         ▼
[Rack Response Extraction]
         │ Konversi menjadi tuple: [Status, Headers Hash, Body Stream]
         ▼
[Client Socket Transmission]
```

1. **Routing Resolution**: `ActionDispatch::Routing::RouteSet` memproses URI path. Lambda/Class constraint dievaluasi. Jika constraint return `false`, Journey melanjutkan traversal rute berikutnya tanpa menyentuh controller lifecycle.
2. **Controller Allocation**: Ketika rute valid ditemukan, controller class memanggil method `.dispatch(action, req, res)`. Rails membuat *fresh instance* dari controller untuk menjamin *thread-safety* antar request.
3. **Filter Chain Execution**: Method internal `run_callbacks(:process_action)` dieksekusi. Callback dikomputasi berurutan. Jika terjadi pengecualian atau method render dipanggil, eksekusi dipotong (*halted*).
4. **Conditional Cache Inspection**: Jika controller memanggil `fresh_when(etag: ..., last_modified: ...)`, Rails langsung membandingkan header `If-None-Match` dan `If-Modified-Since` dari client. Jika *fresh*, Rails menetapkan status HTTP `304 Not Modified`, mengosongkan response body, dan langsung mengembalikan response tanpa memproses serialisasi payload.
5. **Payload Serialization & Teardown**: Data payload ditulis ke response body stream. Callback `ensure` dieksekusi untuk menutup file descriptor atau mengembalikan koneksi DB pool jika menggunakan streaming.

---

### 6. Analogy & Diagram ASCII

#### Analogy
Bayangkan sebuah **Bandar Udara Internasional Berkapasitas Tinggi**:
*   **Journey Router**: Petugas ATC (Air Traffic Control) dan gerbang pemindai otomatis. Pesawat (request) tidak diarahkan satu per satu secara manual. Ada sistem radar berkecepatan tinggi ($O(k)$) yang memilah: apakah pesawat ini kargo domestik, jet VIP, atau maskapai komersial internasional (Dynamic Constraints). Jika izin terbang salah, pesawat ditolak mendarat sebelum menyentuh landasan pacu.
*   **Action Controller**: Terminal Kedatangan.
*   **Filter Chain (`before_action`)**: Pemeriksaan Imigrasi, Bea Cukai, dan Karantina. Setiap penumpang harus melewati antrean terstruktur. Jika paspor tidak valid (Auth Failure), penumpang langsung dikarantina (Halted Response) dan dilarang masuk ke terminal utama.
*   **Action Logic**: Konter Pengambilan Bagasi (bisnis inti).
*   **Strong Parameters**: Mesin X-Ray koper. Penumpang membawa banyak barang, tetapi hanya barang yang dideklarasikan secara sah yang diizinkan masuk ke bagasi mobil. Barang terlarang/tak dikenal diabaikan atau dibuang (Sanitasi Param).
*   **Conditional Caching (`fresh_when`)**: Sistem "Fast Track Paspor Biometrik". Jika wajah dan sidik jari penumpang sama persis dengan database kedatangan 5 menit lalu, penumpang langsung dipersilakan lewat pintu darurat tanpa harus melalui proses interogasi panjang.

#### Diagram Arsitektur Pemrosesan Parameter & Decoupling Controller

```
                    RACK REQUEST PARAMS HASH
                               │
                               ▼
        ┌──────────────────────────────────────────────┐
        │        ActionController::Parameters          │
        │             (Mutated / Tainted)              │
        └──────────────────────┬───────────────────────┘
                               │
               require(:order).permit(...)
                               │
                               ▼
        ┌──────────────────────────────────────────────┐
        │          Sanitized Parameters Hash           │
        └──────────────────────┬───────────────────────┘
                               │
                               ▼
  ┌──────────────────────────────────────────────────────────┐
  │                 Controller Entry Point                   │
  │        (Orkestrator Tipis - Bebas Business Logic)        │
  └──────────────┬─────────────────────────────┬─────────────┘
                 │                             │
    Validasi Form Multi-Model                  │ Eksekusi Logika Bisnis
                 ▼                             ▼
  ┌──────────────────────────────┐    ┌──────────────────────────────┐
  │       Form Object            │    │    Service Object Engine     │
  │ (Data Mapping, Struct Check) │    │  (Dry::Monads / Result Type) │
  └──────────────────────────────┘    └──────────────┬───────────────┘
                                                     │
                                       ┌─────────────┴─────────────┐
                                       ▼                           ▼
                                  [ Success ]                  [ Failure ]
                                       │                           │
                                       ▼                           ▼
                             HTTP 200/201 (Payload)       HTTP 422/400 (Error)
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Dynamic Route Constraint & Custom Mapper

Implementasi constraint tingkat lanjut untuk memvalidasi UUID v4 pada URI segment dan membatasi akses routing hanya untuk IP internal enterprise atau tenant subdomain yang aktif.

```ruby
# config/initializers/routing_mappers.rb
module CustomRouteMappers
  # Custom route mapper macro
  def api_version(version, &block)
    namespace :api, defaults: { format: :json } do
      namespace version, &block
    end
  end
end

ActionDispatch::Routing::Mapper.include(CustomRouteMappers)

# lib/constraints/uuid_constraint.rb
class UuidConstraint
  UUID_V4_REGEX = /\A[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\z/i

  def matches?(request)
    id = request.path_parameters[:id]
    id.present? && id.match?(UUID_V4_REGEX)
  end
end

# lib/constraints/tenant_subdomain_constraint.rb
class TenantSubdomainConstraint
  RESERVED_SUBDOMAINS = %w[www admin api staging mail].freeze

  def matches?(request)
    subdomain = request.subdomain
    subdomain.present? && !RESERVED_SUBDOMAINS.include?(subdomain)
  end
end

# config/routes.rb
Rails.application.routes.draw do
  api_version :v1 do
    constraints(TenantSubdomainConstraint.new) do
      resources :tenants, only: [:show] do
        resources :workspaces, constraints: { id: UuidConstraint.new }, only: [:show, :update]
      end
    end

    # Endpoint diagnostik dengan constraint lambda Rack env
    get "health/internal", to: "health#internal",
      constraints: lambda { |req| ["127.0.0.1", "::1"].include?(req.remote_ip) }
  end
end
```

#### 7.2 Practical Example: Enterprise Decoupled Controller

Implementasi arsitektur produksi menggunakan `ActionController::API`, `ActionController::Live` untuk streaming, `fresh_when` untuk optimasi caching, Strong Parameters tingkat lanjut, dan integrasi Result Monad.

##### Domain Models & Migrations Context (Mental Model)
Aplikasi memproses entitas `Order` yang memiliki banyak `OrderItems`, terkait dengan `PaymentSource`.

##### 1. The Result Monad Contract (Lightweight Monad Pattern)
```ruby
# app/services/application_service.rb
class ApplicationService
  Result = Struct.new(:success, :data, :error, keyword_init: true) do
    def success?
      success
    end

    def failure?
      !success
    end
  end

  def self.call(...)
    new(...).call
  end

  protected

  def success(data = nil)
    Result.new(success: true, data: data, error: nil)
  end

  def failure(error = nil)
    Result.new(success: false, data: nil, error: error)
  end
end
```

##### 2. Advanced Form Object & Strong Parameters Sanitizer
```ruby
# app/forms/order_creation_form.rb
class OrderCreationForm
  include ActiveModel::Model
  include ActiveModel::Attributes

  attribute :customer_id, :string
  attribute :currency, :string, default: "USD"
  attribute :items, default: -> { [] }
  attribute :metadata, default: -> { {} }

  validates :customer_id, presence: true
  validates :currency, inclusion: { in: %w[USD EUR IDR JPY] }
  validate :validate_items_payload

  def initialize(attributes = {})
    super(attributes)
    normalize_items!
  end

  private

  def normalize_items!
    return unless items.is_a?(Array)

    self.items = items.map do |item|
      item.permit(:product_id, :quantity, :unit_price).to_h
    end
  end

  def validate_items_payload
    errors.add(:items, "harus memiliki minimal 1 item valid") if items.blank?

    items.each_with_index do |item, index|
      errors.add("items[#{index}].product_id", "tidak boleh kosong") if item["product_id"].blank?
      errors.add("items[#{index}].quantity", "harus lebih besar dari 0") if item["quantity"].to_i <= 0
      errors.add("items[#{index}].unit_price", "tidak valid") if item["unit_price"].to_f <= 0
    end
  end
end
```

##### 3. Service Object: Isolated Business Logic
```ruby
# app/services/orders/create_order_service.rb
module Orders
  class CreateOrderService < ApplicationService
    def initialize(form:)
      @form = form
    end

    def call
      return failure(@form.errors.full_messages) unless @form.valid?

      order = nil
      ActiveRecord::Base.transaction do
        order = Order.create!(
          customer_id: @form.customer_id,
          currency: @form.currency,
          metadata: @form.metadata,
          status: "pending"
        )

        @form.items.each do |item|
          order.order_items.create!(
            product_id: item["product_id"],
            quantity: item["quantity"],
            unit_price: item["unit_price"]
          )
        end
      end

      # Memancarkan event domain / async job di sini jika diperlukan
      success(order)
    rescue ActiveRecord::RecordInvalid => e
      failure("Database validation failure: #{e.message}")
    rescue StandardError => e
      # Log error secara mendalam di observability layer
      Rails.logger.error("[Orders::CreateOrderService] Exception: #{e.class} - #{e.message}\n#{e.backtrace.join("\n")}")
      failure("Internal server error saat pemrosesan pesanan")
    end
  end
end
```

##### 4. Controller API Produksi (Handling REST, Caching & ActionController::Live)
```ruby
# app/controllers/api/v1/orders_controller.rb
module Api
  module V1
    class OrdersController < ActionController::API
      include ActionController::Live

      # Filter chain terstruktur
      before_action :authenticate_request!
      before_action :set_order, only: [:show, :audit_stream]

      # GET /api/v1/orders/:id
      # Implementasi Conditional GET menggunakan fresh_when (HTTP 304)
      def show
        # Memeriksa ETag berbasis data order & updated_at secara hemat query
        # Client dengan cache valid langsung menerima 304 Not Modified
        return if fresh_when(
          etag: [@order, @order.order_items.maximum(:updated_at)],
          last_modified: @order.updated_at.utc,
          public: false
        )

        render json: @order.as_json(
          include: { order_items: { only: [:id, :product_id, :quantity, :unit_price] } },
          except: [:lock_version]
        )
      end

      # POST /api/v1/orders
      # Form Object + Service Object decoupling
      def create
        form = OrderCreationForm.new(order_params)
        result = Orders::CreateOrderService.call(form: form)

        if result.success?
          render json: result.data, status: :created
        else
          render json: { errors: result.error }, status: :unprocessable_entity
        end
      end

      # GET /api/v1/orders/:id/audit_stream
      # Implementasi SSE (Server-Sent Events) via ActionController::Live
      def audit_stream
        response.headers["Content-Type"] = "text/event-stream"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no" # Menonaktifkan Nginx response buffering

        sse = ActionController::Live::SSE.new(response.stream, retry: 300, event: "audit_event")

        # Ambil ringkasan log audit
        10.times do |i|
          break if response.stream.closed?

          sse.write({ step: i + 1, timestamp: Time.current.iso8601, message: "Validating state segment #{i}" })
          sleep 0.5
        end
      rescue ActionController::Live::ClientDisconnected
        Rails.logger.info("Client disconnected from SSE audit stream for order #{@order.id}")
      ensure
        sse.close if sse
        # PENTING: Kembalikan koneksi database pool jika action membuka connection
        ActiveRecord::Base.clear_active_connections!
      end

      private

      def authenticate_request!
        token = request.headers["Authorization"]&.split(" ")&.last
        render json: { error: "Unauthorized" }, status: :unauthorized unless token == "enterprise-secret-key"
      end

      def set_order
        @order = Order.includes(:order_items).find_by(id: params[:id])
        render json: { error: "Order not found" }, status: :not_found unless @order
      end

      # Deeply nested Strong Parameters configuration
      def order_params
        params.require(:order).permit(
          :customer_id,
          :currency,
          metadata: {}, # Mengizinkan arbitrary payload JSON untuk metadata
          items: [
            :product_id,
            :quantity,
            :unit_price
          ]
        )
      end
    end
  end
end
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Stripe-Scale Global Webhook Receiver Architecture

Sebuah platform pembayaran FinTech menerima rata-rata **50.000 incoming webhooks per detik** pada periode flash-sale dari 12 penyedia payment gateway global (Visa, Mastercard, Stripe, Adyen, Midtrans).

#### Tantangan Skalabilitas & Latensi:
1. **Puma Thread Pool Saturation**: Setiap webhook memicu database transaction untuk menyimpan payload, memverifikasi cryptographic signature, dan mencatat audit log. Worker thread cepat habis, memicu antrean socket TCP dan HTTP 504 Gateway Timeout.
2. **Payload Size Variance**: Ukuran payload webhook bervariasi dari 1 KB hingga 2 MB. Penggunaan `params` standar Rails langsung mengalokasi memori GC besar-besaran karena `ActionController::Parameters` mem-parse seluruh parameter nested ke hash Ruby.
3. **Double Verification**: Signature hashing dilakukan di controller setelah parsing parameter selesai, sehingga membuang siklus CPU jika signature ternyata palsu.

#### Solusi Rekayasa Controller & Routing:
1. **Dynamic Routing Constraint Pre-Check**: Verifikasi struktur HTTP Header dan Whitelist IP dilakukan pada layer Journey Constraint sebelum alokasi controller terjadi.
2. **ActionController::Metal Implementation**: Webhook receiver diubah menggunakan `ActionController::Metal` murni, membypass middleware parsing JSON standar Rails.
3. **Zero-Copy Payload Ingestion**: Body stream mentah (`request.raw_post`) diverifikasi menggunakan HMAC-SHA256 tanpa di-parse menjadi Ruby Hash, lalu langsung diproteksi idempotency key-nya ke Redis via atomic Lua Script, dan di-offload ke RabbitMQ/Kafka.
4. **Immediate 202 Accepted Response**: Controller merespons dalam < 5 milidetik dengan payload `[202, {"Content-Type" => "application/json"}, ['{"status":"queued"}']]`.

```ruby
# app/controllers/api/v1/raw_webhooks_controller.rb
module Api
  module V1
    class RawWebhooksController < ActionController::Metal
      include ActionController::Instrumentation
      include ActionController::Rescue

      # Hanya sertakan module yang mutlak dibutuhkan
      ABSTRACT_CORE = [
        ActionController::Rendering
      ].freeze

      def receive
        provider = params[:provider]
        signature = request.headers["X-Signature-SHA256"]
        raw_body = request.raw_post

        # 1. Validasi Keberadaan Header Cepat
        if signature.blank? || raw_body.blank?
          self.status = 400
          self.content_type = "application/json"
          self.response_body = '{"error":"Invalid payload signature headers"}'
          return
        end

        # 2. Verifikasi Kriptografi Langsung pada Raw Buffer (O(1) Memory Alloc)
        unless WebhookSecurity.valid_signature?(provider: provider, payload: raw_body, signature: signature)
          self.status = 401
          self.content_type = "application/json"
          self.response_body = '{"error":"Signature mismatch"}'
          return
        end

        # 3. Offload Asinkron ke Pipeline Messaging (Kafka/Sidekiq)
        idempotency_key = request.headers["X-Idempotency-Key"] || Digest::SHA256.hexdigest(raw_body)
        
        # Enqueue job secara non-blocking
        WebhookIngestionJob.perform_later(provider, idempotency_key, raw_body)

        # 4. Fast Ack Response
        self.status = 202
        self.content_type = "application/json"
        self.response_body = '{"status":"accepted","idempotency_key":"' + idempotency_key + '"}'
      end
    end
  end
end
```

---

### 9. Trade-offs

```
                  ┌──────────────────────────────────────────────┐
                  │          Throughput vs Complexity            │
                  └──────────────────────────────────────────────┘
                    ▲
     ActionController::Metal (Tinggi)
                    │           * Raw Webhooks (Minimal Allocations)
                    │
                    │      * ActionController::API (REST JSON)
                    │
                    │
                    │ * ActionController::Base (Full Stack Monolith)
     Low Latency    │
     Low Overhead   │
                    └──────────────────────────────────────────────►
                    Rendah                                 Tinggi
                                Abstraksi & Developer Ergonomics
```

| Dimensi Rekayasa | ActionController::Base | ActionController::API | ActionController::Metal | ActionController::Live |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput (RPS)** | Menengah (~1.5k RPS) | Tinggi (~4.5k RPS) | Maksimal (~10k+ RPS) | Sangat Bergantung Puma Thread Pool (~500 streams) |
| **Alokasi Memori / Req** | 120 - 300 KB | 40 - 90 KB | 5 - 15 KB | 60 - 150 KB (menahan buffer) |
| **Footprint Callback** | Penuh (CSRF, Cookies, Flash) | Menengah (Params, Rescue, Render) | Minimal / Manual | Penuh + Async Life Cycle Overhead |
| **Developer Productivity** | Sangat Cepat (Konvensi Lengkap) | Cepat (Format JSON otomatis) | Lambat (Manual wiring Rack response) | Menengah (Wajib audit thread leak) |
| **Database Pool Impact** | Standar (Check-in/Check-out per request) | Standar | Terkendali | Kritis (Bisa menghabiskan pool jika streaming lambat) |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Mutasi Objek pada Filter Chain Callback (`before_action`)
*   *Kesalahan*: Mengubah objek global atau class variable di dalam callback controller (`@@shared_context = params[:id]`).
*   *Dampak*: *Data leakage* lintas tenant karena instance controller dapat berjalan di thread Puma yang berbagi memori proses Ruby yang sama.
*   *Troubleshooting*: Gunakan `CurrentAttributes` dengan disiplin pembersihan otomatis (`ActiveSupport::CurrentAttributes`) atau teruskan data secara eksplisit via method arguments.

#### 2. Double Render / Double Redirect Error (`ActionController::DoubleRenderError`)
*   *Kesalahan*: Menulis logika kondisional bercabang tanpa kata kunci `return` setelah memanggil `render` atau `redirect_to`.
    ```ruby
    # SALAH
    def set_user
      redirect_to(login_path) unless logged_in?
      @user = User.find(params[:id]) # Tetap dieksekusi!
    end
    ```
*   *Troubleshooting*: Selalu gunakan explicit guard clause: `return redirect_to(login_path) unless logged_in?` atau andalkan `throw :abort` jika berada di dalam internal callback context.

#### 3. Thread-Pool Exhaustion pada `ActionController::Live`
*   *Gejala*: Aplikasi berhenti merespons (hang) secara global setelah 16-32 request streaming dibuka bersamaan di server Puma dengan 16 threads.
*   *Akar Masalah*: Worker Puma memegang thread terbuka selama streaming berlangsung. Koneksi ActiveRecord yang dibuka di awal controller tidak dikembalikan ke pool.
*   *Troubleshooting*: Selalu jalankan `ActiveRecord::Base.clear_active_connections!` di dalam blok `ensure`, dan pisahkan Puma worker pool untuk traffic streaming atau alihkan implementasi long-polling/SSE ke engine non-blocking seperti Falcon atau server WebSocket mandiri (AnyCable).

#### 4. Parameter Injection Melalui `params.permit!` (Whitelisting Arbitrary)
*   *Kesalahan*: Memanggil `params.require(:data).permit!` untuk mempermudah penerimaan payload dinamis.
*   *Dampak*: Kerentanan *Mass Assignment Privilege Escalation*. Penyerang dapat menyisipkan `role: "admin"` atau `is_verified: true` ke dalam database model.
*   *Troubleshooting*: Jangan pernah menggunakan `permit!` pada context mutasi model. Gunakan pemetaan eksplisit atau manfaatkan form objects schema validation.

---

### 11. Best Practices (Production Checklist)

1. **Routing Constraints Execution**: Validasi semua ID parameter yang menggunakan format terstruktur (UUID, Slug) pada route constraint untuk memangkas *unroutable traffic* sebelum menyentuh controller lifecycle.
2. **Gunakan `ActionController::API` untuk Service Berbasis JSON**: Buang ketergantungan flash, cookies, dan form authentication untuk mengurangi footprint alokasi memori per request hingga 60%.
3. **Patuhi Prinsip Skinny Controller**: Batasi baris kode action controller maksimal 10-15 baris. Tindakan controller harus dibatasi hanya pada:
   - Verifikasi otorisasi konteks.
   - Ekstraksi parameter input yang diizinkan.
   - Panggilan ke 1 Service/Form Object.
   - Format dan pengembalian HTTP response status.
4. **Implementasikan HTTP 304 Freshness Everywhere**: Gunakan `fresh_when` atau `stale?` pada semua endpoint resource GET yang sering diakses namun jarang berubah.
5. **Gunakan Nil-Safe Parameter Fetching**: Hindari `params[:order][:user_id]` yang rawan `NoMethodError: undefined method '[]' for nil:NilClass`. Gunakan `params.dig(:order, :user_id)`.
6. **Eksplisitkan Return pada Guard Clauses**: Pastikan setiap filter atau branch yang memanggil `render`/`redirect_to` dieksekusi dengan `return`.
7. **Isolasi Koneksi DB pada Controller Streaming**: Tutup koneksi ActiveRecord segera setelah data inisial diambil jika menggunakan `ActionController::Live`.
8. **Explicit Strong Parameters Structure**: Definisikan skema array dan nested hash secara presisi; jangan biarkan scalar types bertindak sebagai nested parameters.
9. **Kompilasi Rute Production**: Pastikan `config.eager_load = true` aktif di environment produksi agar state machine Journey DFA terkompilasi penuh saat server booting, bukan pada saat request pertama.
10. **Custom Exception Handling**: Gunakan `rescue_from` secara terpusat pada `ApplicationController` untuk memetakan error domain (contoh: `RecordNotFound`, `UnauthorizedError`) ke serialisasi output JSON yang konsisten.

---

### 12. Hands-on Practice

Simpan seluruh hasil latihan praktikum ini ke dalam direktori: `hands-on/m02/`.

#### Langkah 1: Inisialisasi Aplikasi Rails Minimal
Jalankan perintah shell berikut untuk menginisialisasi workspace:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
rails new enterprise_controller_lab --api --minimal --database=sqlite3
cd enterprise_controller_lab
```

#### Langkah 2: Buat Model & Migrasi Uji
```bash
bin/rails generate model Account name:string api_key:string
bin/rails generate model Device account:references uuid:string status:string metadata:json
bin/rails db:migrate
```

Isi data seeds di `db/seeds.rb`:
```ruby
account = Account.create!(name: "Enterprise Alpha", api_key: "ak_live_secure_999")
10.times do |i|
  account.devices.create!(
    uuid: SecureRandom.uuid,
    status: i.even? ? "active" : "offline",
    metadata: { firmware: "v1.0.#{i}", location: "Edge Node #{i}" }
  )
end
```
Jalankan seed: `bin/rails db:seed`

#### Langkah 3: Implementasikan Route Constraints
Buat file `lib/constraints/api_key_constraint.rb`:
```ruby
class ApiKeyConstraint
  def matches?(request)
    api_key = request.headers["X-API-KEY"]
    api_key.present? && Account.exists?(api_key: api_key)
  end
end
```

Konfigurasi `config/routes.rb`:
```ruby
require_relative "../lib/constraints/api_key_constraint"

Rails.application.routes.draw do
  namespace :api, defaults: { format: :json } do
    namespace :v1 do
      constraints(ApiKeyConstraint.new) do
        resources :devices, only: [:index, :show, :create] do
          member do
            get :telemetry_stream
          end
        end
      end
    end
  end
end
```

#### Langkah 4: Implementasi Controller dengan Streaming & Conditional GET
Tulis controller pada `app/controllers/api/v1/devices_controller.rb`:
```ruby
module Api
  module V1
    class DevicesController < ActionController::API
      include ActionController::Live

      before_action :set_account
      before_action :set_device, only: [:show, :telemetry_stream]

      # GET /api/v1/devices
      def index
        @devices = @account.devices
        # Conditional GET berbasis ETag kumpulan data
        return if fresh_when(etag: @devices, last_modified: @devices.maximum(:updated_at))

        render json: @devices
      end

      # GET /api/v1/devices/:id
      def show
        return if fresh_when(@device)

        render json: @device
      end

      # POST /api/v1/devices
      def create
        device = @account.devices.build(device_params)
        if device.save
          render json: device, status: :created
        else
          render json: { errors: device.errors.full_messages }, status: :unprocessable_entity
        end
      end

      # GET /api/v1/devices/:id/telemetry_stream
      def telemetry_stream
        response.headers["Content-Type"] = "text/event-stream"
        response.headers["Cache-Control"] = "no-cache"

        sse = ActionController::Live::SSE.new(response.stream, event: "ping")

        5.times do |i|
          break if response.stream.closed?

          sse.write({ pulse: i + 1, timestamp: Time.now.to_i, uuid: @device.uuid })
          sleep 0.2
        end
      rescue ActionController::Live::ClientDisconnected
        Rails.logger.info("Stream closed by client.")
      ensure
        sse.close if sse
        ActiveRecord::Base.clear_active_connections!
      end

      private

      def set_account
        @account = Account.find_by!(api_key: request.headers["X-API-KEY"])
      end

      def set_device
        @device = @account.devices.find(params[:id])
      end

      def device_params
        params.require(:device).permit(:uuid, :status, metadata: {})
      end
    end
  end
end
```

#### Langkah 5: Eksekusi Pengujian & Verifikasi Response Caching
Jalankan server: `bin/rails server -p 3000`

Uji coba via `curl`:
```bash
# 1. Test Unauthenticated (Harus 404 dari Routing Constraint karena key tidak cocok)
curl -i http://localhost:3000/api/v1/devices

# 2. Test Success
curl -i -H "X-API-KEY: ak_live_secure_999" http://localhost:3000/api/v1/devices

# 3. Test Conditional Caching (Copy ETag dari response di atas, contoh: W/"...")
curl -i -H "X-API-KEY: ak_live_secure_999" \
     -H 'If-None-Match: <PASTE_ETAG_DI_SINI>' \
     http://localhost:3000/api/v1/devices
# Amati status return: HTTP/1.1 304 Not Modified

# 4. Test SSE Stream
curl -N -H "X-API-KEY: ak_live_secure_999" http://localhost:3000/api/v1/devices/1/telemetry_stream
```

---

### 13. Exercise

#### Level Easy
Ubah implementasi `params.require(:device).permit(...)` pada Hands-on Practice untuk menolak secara eksplisit jika parameter `:uuid` bukan format UUID v4 standar, menggunakan ActiveModel validation langsung di level form validator sederhana. Simpan file di `hands-on/m02/exercise_easy.rb`.

#### Level Medium
Buat sebuah Route Constraint bernama `RolloutConstraint` yang menerima nama fitur (*feature flag*). Constraint ini memeriksa header `X-User-ID`, menghitung integer CRC32 dari user ID tersebut, dan hanya merutekan request ke controller experimental jika `CRC32(user_id) % 100 < target_percentage`. Rancang routing fallback ke controller stable jika constraint bernilai `false`.

#### Level Hard
Rancang dan implementasikan custom controller dispatcher berbasis `ActionController::Metal` bernama `MetricsIngestionController`. Controller ini harus:
1. Menerima payload kompresi gzip (`Content-Encoding: gzip`).
2. Melakukan dekompresi on-the-fly dari stream `request.body`.
3. Memparsing payload JSON metrik berukuran hingga 10MB tanpa membebani memori utama Ruby (manfaatkan streaming IO atau GC compaction trigger).
4. Merespons dalam waktu di bawah 15ms.
Sertakan integration test lengkap menggunakan `Rack::Test` di direktori latihan.

---

### 14. Challenge

#### Skenario Kasus Nyata: Puma Thread Starvation Under Degrading Infrastructure

**Konteks Masalah**:
Sistem backend enterprise Anda mendadak mengalami *Thread Pool Starvation* total di kluster Kubernetes produksi selama masa promosi jam sibuk. Puma dikonfigurasi dengan 5 worker proses, masing-masing 16 threads (kapasitas: 80 concurent requests). Rata-rata RPS normal adalah 2.000 RPS.

Sebuah fitur baru bernama `InventoryStreamController` mengimplementasikan SSE via `ActionController::Live` untuk mengabarkan perubahan sisa stok inventaris secara real-time ke aplikasi mobile frontend. 

Namun, terjadi anomali:
1. Koneksi seluler ribuan pengguna klien mengalami *flapping* (koneksi terputus-putus secara sporadis).
2. Database Read-Replica mengalami latency spike dari 2ms melonjak menjadi 1.200ms.
3. Seluruh 80 thread Puma hang di status `busy_threads`, seluruh endpoint API non-streaming (termasuk Login, Cart Checkout, dan Health Check) menghasilkan HTTP 502/504.
4. Kubernetes mulai membunuh (kill) pod Rails karena kegagalan probe `/healthz`. Pod baru yang booting langsung tumbang dalam 30 detik setelah menerima traffic.

**Tugas Anda**:
Rancang dokumen rancangan perbaikan arsitektur (*Architecture Remediation Blueprint*) dan implementasikan prototipe solusinya tanpa menghapus fitur real-time updates.

*   Bagaimana Anda mendesain ulang routing layer untuk mengisolasi traffic streaming dari traffic transactional kritis?
*   Bagaimana controller SSE harus menangani lifecycle koneksi ActiveRecord, pendeteksian socket hangup dari client (*broken pipe*), dan pembatasan timeout transmisi buffer?
*   Tuliskan kode controller mitigasi lengkap yang siap deployed ke cluster produksi, yang menjamin ketersediaan resource DB pool dan thread Puma tidak akan terkuras habis saat downstream DB mengalami degradasi performa.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Apa algoritma internal yang digunakan Journey Engine pada Rails Routing untuk mencocokkan URI path?**
   - A. Linear String Comparison
   - B. Deterministic Finite Automaton (DFA) berbasis Glushkov/Thompson AST
   - C. Radix Tree murni berbasis Hash table
   - D. Binary Search Tree pada seluruh rute
2. **Apa perbedaan struktural utama antara `ActionController::API` dan `ActionController::Base`?**
   - A. `ActionController::API` tidak mendukung database ActiveRecord.
   - B. `ActionController::API` mengeliminasi module view rendering, flash messages, cookies, dan CSRF protection secara default.
   - C. `ActionController::API` tidak dapat memproses JSON parameters.
   - D. `ActionController::Base` hanya bekerja untuk HTTP GET requests.
3. **Bagaimana cara menghentikan eksekusi callback chain di dalam filter `before_action` pada Rails modern?**
   - A. Mengembalikan nilai `false` (`return false`)
   - B. Memanggil method `halt!`
   - C. Melempar `throw :abort` atau memanggil `render`/`redirect_to`
   - D. Menyetel `response.status = 500`
4. **Apa status kode HTTP yang dihasilkan oleh pemanggilan conditional caching `fresh_when` jika client memiliki ETag yang identik?**
   - A. 200 OK
   - B. 204 No Content
   - C. 301 Moved Permanently
   - D. 304 Not Modified
5. **Apa fungsi utama dari method `permit` pada `ActionController::Parameters`?**
   - A. Mengonversi tipe data string ke integer secara otomatis
   - B. Menandai atribut parameter yang diizinkan untuk *mass assignment*, membuang key yang tidak terdaftar
   - C. Melakukan enkripsi parameter sensitif sebelum disimpan ke database
   - D. Mengubah format parameter dari XML menjadi JSON

#### Bagian 2: Intermediate (5 Soal)
6. **Kapan instance dari class Controller dibuat selama lifecycle request di Rails?**
   - A. Satu kali saat server boot (Singleton pattern)
   - B. Satu kali per thread worker Puma
   - C. Instance baru dibuat pada setiap request yang lolos dari routing resolution
   - D. Dibuat kembali setiap kali sebuah filter callback selesai dieksekusi
7. **Mengapa penulisan `ActiveRecord::Base.clear_active_connections!` sangat krusial pada action yang menyertakan `ActionController::Live`?**
   - A. Untuk membersihkan cache query database di memory Redis.
   - B. Karena streaming menahan thread Puma dalam durasi lama, sehingga koneksi DB pool harus dikembalikan agar tidak habis (*starvation*).
   - C. Untuk membatalkan transaksi database yang belum di-commit secara paksa.
   - D. Agar garbage collector dapat mendelokasi objek ActiveRecord secara instan.
8. **Diberikan skema rute: `get "/items/:id", to: "items#show", constraints: { id: /\d+/ }`. Apa yang terjadi jika client melakukan request ke `/items/abc`?**
   - A. Rails melempar exception `ActionController::RoutingError: Parameter Invalid`.
   - B. Rails merender response HTTP 400 Bad Request secara otomatis.
   - C. Routing engine memperlakukan rute tersebut seolah tidak pernah ada dan mencari rute berikutnya, atau menghasilkan HTTP 404.
   - D. Controller `ItemsController#show` tetap dipanggil dengan `params[:id] = nil`.
9. **Apa risiko keamanan utama jika developer menggunakan `params.fetch(:user).permit!` pada controller pendaftaran user?**
   - A. Remote Code Execution (RCE) via deserialisasi YAML
   - B. Privilege Escalation via Mass Assignment, penyerang bisa mengirim payload seperti `admin: true`
   - C. Denial of Service (DoS) akibat regex backtracking
   - D. SQL Injection otomatis pada seluruh query builder
10. **Bagaimana cara kerja callback compilation pada `ActiveSupport::Callbacks` mengoptimalkan latency request?**
    - A. Mengompilasi seluruh callback menjadi bytecode native C via YJIT.
    - B. Menggabungkan serangkaian method symbol dan proc menjadi satu method Ruby dinamis tunggal untuk meminimalisir dynamic dispatch loop.
    - C. Mengeksekusi seluruh callback secara paralel menggunakan thread pool background.
    - D. Menyimpan hasil return callback ke dalam memori Redis.

#### Bagian 3: Skenario Kasus Produksi (3 Soal)
11. **Skenario Audit Log Memory Leak**:
    Sebuah aplikasi mencatat audit log dengan menyimpan payload request lengkap pada callback:
    `after_action { AuditLogger.log(request.params) }`
    Pada load test tinggi, penggunaan memory RSS worker Puma terus naik (*bloated*) dan tidak pernah turun kembali setelah pengujian selesai. Profiling memory mengindikasikan jutaan instance `String` tertahan di heap. Apa akar masalahnya?
    - A. `request.params` mengembalikan `ActionController::Parameters` yang menduplikasi seluruh hash dan menahan referensi memory buffer string dari Rack I/O stream.
    - B. Puma memiliki bug internal yang menahan string callback di Ruby Heap.
    - C. Callback `after_action` tidak didukung pada arsitektur API Rails.
    - D. Modul `AuditLogger` mengunci koneksi ActiveRecord sehingga garbage collector dicegah berjalan.
12. **Skenario Dynamic Routing Degradation**:
    Sebuah tim menambahkan routing constraint berupa database query:
    `constraints: lambda { |req| Tenant.exists?(subdomain: req.subdomain) }`
    Setelah rute ini ditambahkan, latency rata-rata untuk request statis dan rute 404 melonjak dari 1ms menjadi 45ms per request. Apa rekomendasi arsitektur terbaik untuk memecahkan masalah ini?
    - A. Mengubah database ke SQLite in-memory.
    - B. Memindahkan validasi tenant dari Route Constraint ke Redis-backed cache layer, atau menanganinya di level `before_action` pada tenant-scoped controller base class.
    - C. Mengganti Puma dengan Unicorn server.
    - D. Menghapus arsitektur multi-tenant dan memecahnya menjadi 100 aplikasi monolitik terpisah.
13. **Skenario Broken Pipe pada SSE Streaming**:
    Pada endpoint `ActionController::Live`, client browser sering menutup tab secara mendadak saat data sedang di-stream. Log Rails dipenuhi oleh exception `Errno::EPIPE` dan `ActionController::Live::ClientDisconnected`. Apa pendekatan mitigasi paling tangguh untuk menangani kondisi ini tanpa mencemari error tracking dashboard (Sentry/Datadog)?
    - A. Mengabaikan seluruh exception secara global dengan `rescue Exception`.
    - B. Menangkap `ActionController::Live::ClientDisconnected` dan `Errno::EPIPE` secara spesifik di dalam block action, menutup buffer via `response.stream.close`, dan memastikan koneksi ActiveRecord di-release di block `ensure`.
    - C. Memperbesar Puma worker timeout menjadi 300 detik.
    - D. Mematikan fitur keep-alive pada load balancer Nginx.

---

### Kunci Jawaban & Rasional Evaluasi

#### Bagian 1: Basic
1. **B** — Journey Engine mengompilasi rute Rails menggunakan teori automata (NFA to DFA) berbasis parsing AST untuk pencarian rute efisien berkecepatan tinggi $O(k)$.
2. **B** — `ActionController::API` adalah subset ramping dari `Base` yang membuang layer middleware view, layout, session cookie, flash, dan CSRF token.
3. **C** — Sejak Rails 5+, penghentian callback harus dilakukan secara eksplisit dengan memanggil render/redirect atau melempar symbol penanda `throw :abort`. Mengembalikan `false` sudah usang (*deprecated*).
4. **D** — Spesifikasi HTTP RFC 7232 menyatakan bahwa jika entitas resource belum termodifikasi sesuai validasi ETag/Last-Modified, server wajib membalas dengan status 304 Not Modified tanpa body.
5. **B** — `permit` berfungsi memfilter key parameter dan menandai flag *permitted* internal pada instance `ActionController::Parameters`, mengamankan model dari mass-assignment attack.

#### Bagian 2: Intermediate
6. **C** — Untuk menjaga *thread safety*, Rails menginstansiasi objek controller baru pada setiap request yang masuk dan mendestruksinya setelah Rack response dikembalikan.
7. **B** — Puma menjalankan model multi-threaded. Saat streaming menahan eksekusi action selama bermenit-menit, jika thread tersebut memegang koneksi ActiveRecord, pool koneksi database akan habis dan memblokir request lain.
8. **C** — Route constraint yang tidak terpenuhi dievaluasi oleh Journey sebagai ketidakcocokan rute (*route mismatch*), sehingga traversal dilanjutkan ke rute berikutnya hingga jatuh ke 404 jika tidak ada rute yang cocok.
9. **B** — Memanggil `permit!` secara membabi-buta membuka seluruh key input yang dikirim client, memungkinkan manipulasi field sensitif database.
10. **B** — `ActiveSupport::Callbacks` mengompilasi daftar callback method menjadi dynamic evaluation method tunggal, menghilangkan overhead iterasi array dinamis pada level runtime request.

#### Bagian 3: Skenario Kasus Produksi
11. **A** — `request.params` mengurai seluruh payload HTTP mentah ke dalam hash parameter Ruby baru di setiap pemanggilan. Jika ditahan oleh referensi objek logger, memori tidak dapat di-reclaim oleh GC (*memory retention*).
12. **B** — Melakukan I/O query database synchronous di dalam Journey Route Constraint memicu bottleneck ekstrim karena constraint dievaluasi pada setiap request (termasuk static assets / invalid routes). Solusinya adalah memvalidasi via in-memory lookup (Redis) atau menundanya hingga controller level.
13. **B** — Pemutusan koneksi sepihak oleh client adalah peristiwa normal pada HTTP streaming. Exception ini harus ditangani secara elegan (*graceful degradation*) dengan menutup IO stream dan membersihkan active connections tanpa menaikkan error log level ke alert.

---

### 16. Summary

1. **Routing Journey Internals**: Routing Rails didukung oleh Journey Engine yang mengubah definisi rute DSL menjadi AST, kemudian dikompilasi menjadi Deterministic Finite Automaton (DFA). Pencocokan rute bekerja dalam kompleksitas $O(k)$ terhadap panjang path.
2. **Decoupled Architecture**: Arsitektur controller enterprise harus menerapkan pemisahan tanggung jawab (*Separation of Concerns*). Controller modern bertindak murni sebagai *thin HTTP orchestrator*. Logika validasi data dipindahkan ke **Form Objects**, eksekusi bisnis ke **Service Objects/Interactors**, dan optimasi query ke **Query Objects**.
3. **Controller Inheritance Spectrum**: Gunakan `ActionController::Metal` untuk high-throughput ingestion/webhooks, `ActionController::API` untuk layanan JSON REST mikro dan service enterprise, serta pertahankan `ActionController::Base` hanya untuk monolitik full-stack yang mengandalkan SSR (Server-Side Rendering).
4. **Conditional Caching & HTTP Protocol Compliance**: Pemanfaatan `fresh_when` dan `stale?` secara presisi mengurangi beban komputasi database dan serialisasi JSON secara masif dengan memanfaatkan kemampuan caching browser/CDN melalui response `304 Not Modified`.
5. **Resource Management pada Async Streaming**: Penggunaan `ActionController::Live` membuka kapabilitas Server-Sent Events tanpa WebSocket. Namun, developer wajib mengelola koneksi database secara manual (`ActiveRecord::Base.clear_active_connections!`) dan menangani *socket broken-pipe* guna mengeliminasi risiko *Puma thread starvation*.