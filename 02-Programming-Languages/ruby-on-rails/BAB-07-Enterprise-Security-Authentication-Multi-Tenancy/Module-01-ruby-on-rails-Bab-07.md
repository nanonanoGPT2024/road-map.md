# Bab 07 Module 01: Enterprise Security, Authentication & Multi-Tenancy

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** ROR-ENT-0701
* **Jalur Pembelajaran:** Advanced Ruby on Rails Engineering & Enterprise Architecture
* **Kategori:** 02-Programming-Languages
* **Tingkat Kesulitan:** Advanced / Enterprise-Grade
* **Prasyarat:** 
  * Pemahaman mendalam tentang siklus hidup Rack Middleware dan HTTP stack pada Rails.
  * Penguasaan ActiveRecord internals, dynamic dispatching, dan metaprogramming Ruby.
  * Pemahaman tentang arsitektur basis data relasional (khususnya PostgreSQL: Search Path, Tablespaces, dan Row-Level Security).
  * Pemahaman protokol kriptografi dasar, TLS termination, dan web security vectors (OWASP Top 10).
* **Estimasi Waktu Penyelesaian:** 12 - 16 Jam Pembelajaran Intensif

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Menganalisis dan Memilih Pola Multi-Tenancy (C4 - Analysis):** Mengidentifikasi perbedaan arsitektural antara *Row-Level Multi-Tenancy*, *Schema-Based Multi-Tenancy*, dan *Database-per-Tenant*, serta memilih strategi yang tepat berdasarkan skala data, kepatuhan regulasi (misal: GDPR, HIPAA), dan batasan infrastruktur.
2. **Mengimplementasikan Isolasi Data Tingkat Lanjut (C6 - Synthesis):** Mengintegrasikan PostgreSQL Row-Level Security (RLS) secara *native* ke dalam model ActiveRecord Rails tanpa bergantung mutlak pada application-level scoping seperti `default_scope`.
3. **Membangun Sistem Autentikasi Enterprise & SSO (C6 - Synthesis):** Merancang arsitektur Single Sign-On (SSO) berbasis SAML 2.0 / OIDC, rotasi token sesi berbasis kriptografi asimetris, dan mekanisme proteksi *Session Hijacking* serta *Session Fixation*.
4. **Mengeliminasi Kerentanan Tenant Data Leaks (C5 - Evaluation):** Mendiagnosis dan memitigasi kebocoran data antar-penyewa (cross-tenant leaks) yang diakibatkan oleh thread safety issues, context loss pada background workers (Sidekiq), dan cache key collisions.
5. **Menegakkan Kontrol Akses Terperinci (Fine-Grained Access Control) (C6 - Synthesis):** Mengimplementasikan otorisasi berbasis Role-Based Access Control (RBAC) dan Attribute-Based Access Control (ABAC) menggunakan ActionPolicy dengan performa overhead sub-milidetik.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pertahanan Berlapis (Defense-in-Depth) Multi-Tenancy

Di lingkungan enterprise B2B SaaS, data leak antar penyewa (*cross-tenant data breach*) adalah insiden level *Severity-0* yang dapat menghancurkan kredibilitas bisnis dan melanggar hukum secara fatal. Paradigma pengembangan Rails tradisional yang hanya mengandalkan kode aplikasi (`where(tenant_id: current_tenant.id)`) memiliki *flaw* kritis: **human error**. Developer junior dapat dengan mudah menulis `User.unscoped.all` atau mengeksekusi *raw SQL* yang mengabaikan scope.

```
+-------------------------------------------------------+
|  Lapisan 1: Jaringan / DNS / Gateway                  |
|  - Subdomain routing & TLS SNI resolution             |
+-------------------------------------------------------+
                           |
                           v
+-------------------------------------------------------+
|  Lapisan 2: Rack Middleware Context Pipeline          |
|  - Ekstraksi Tenant & Sanitasi Request Context        |
|  - Fiber/Thread-isolated State (CurrentAttributes)    |
+-------------------------------------------------------+
                           |
                           v
+-------------------------------------------------------+
|  Lapisan 3: Application Security & Policy (Rails)     |
|  - Strict Scoping (ActsAsTenant / Model Contracts)    |
|  - Fine-Grained Authorization (ActionPolicy / Pundit) |
+-------------------------------------------------------+
                           |
                           v
+-------------------------------------------------------+
|  Lapisan 4: Database Kernel Isolation (PostgreSQL RLS)|
|  - SET LOCAL app.current_tenant_id = 'xxx'            |
|  - Kernel-level enforcement (Bahkan raw SQL terisolasi)|
+-------------------------------------------------------+
```

Mental model yang harus ditanamkan: **"Aplikasi Rails Anda tidak boleh dipercaya oleh basis data Anda sendiri."** Database harus menjadi benteng pertahanan terakhir menggunakan *PostgreSQL Row-Level Security (RLS)*. Jika ada *bug* pada controller atau ActiveRecord query Rails yang mengekspos query tanpa filter, database kernel harus secara independen menolak atau memfilter baris tersebut.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur hidup sebuah request multi-tenant enterprise dari awal kedatangan hingga eksekusi kueri di level database:

```
[ HTTP Request ]
(misal: https://acme.enterprise.io/api/v1/invoices)
       |
       v
+----------------------------------------------------+
| 1. TenantIdentificationMiddleware (Rack)          |
|    - Ekstraksi subdomain 'acme'                    |
|    - Validasi UUID / CNAME kustom                  |
|    - Lookup Metadata Tenant dari Cache (Redis L1)  |
+----------------------------------------------------+
       |
       v
+----------------------------------------------------+
| 2. Authentication & Session Validation             |
|    - Verifikasi JWT / Enterprise Session Cookie    |
|    - Deteksi IP Spofing / User-Agent Fingerprint   |
|    - Bind ke Current.user & Current.tenant         |
+----------------------------------------------------+
       |
       v
+----------------------------------------------------+
| 3. Database Connection Wrapping (RLS Setter)       |
|    ActiveRecord::Base.connection_pool.with_conn    |
|    -> EXECUTE "SET LOCAL app.tenant_id = '1234'"   |
+----------------------------------------------------+
       |
       v
+----------------------------------------------------+
| 4. Controller Action Processing                    |
|    - ActionPolicy Authorize (InvoicePolicy)        |
|    - Query: Invoice.where(status: 'unpaid')        |
+----------------------------------------------------+
       |
       v
+----------------------------------------------------+
| 5. PostgreSQL Kernel Execution                     |
|    - Kueri: SELECT * FROM invoices WHERE status... |
|    - RLS Engine otomatis menginjeksi:              |
|      AND tenant_id = CURRENT_SETTING('app.tenant_id')
+----------------------------------------------------+
       |
       v
[ JSON Response Diisolasi Total ke Acme Tenant ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. `ActiveSupport::CurrentAttributes` vs Thread-Safety
Rails menyediakan `ActiveSupport::CurrentAttributes` untuk menangani *request-isolated globals*. 

Secara internal:
* `CurrentAttributes` menggunakan `Fiber.current[:storage]` atau `Thread.current[:storage]` (tergantung versi Ruby/Rails dan implementasi Fiber Scheduler).
* Pada Rails 7+, `CurrentAttributes` mengimplementasikan callback otomatis pada `ActionDispatch::Executor`. Setiap kali request selesai atau worker Sidekiq selesai memproses pekerjaan, method `.reset` secara internal dipanggil untuk membersihkan thread dictionary.
* **Risiko Fatal:** Jika context tidak di-reset secara deterministik saat error terjadi di luar controller lifecycle (misal: kustom Puma middleware atau background thread non-managed), thread pool reuse pada webserver *threaded* (seperti Puma) akan mewariskan context tenant sebelumnya ke request tenant yang baru.

### 2. PostgreSQL Row-Level Security (RLS) Mechanics
PostgreSQL mengimplementasikan RLS pada level storage engine table engine:
* RLS diaktifkan menggunakan `ALTER TABLE table_name ENABLE ROW LEVEL SECURITY;`.
* Policy didefinisikan dengan perintah `CREATE POLICY`.
* Tenant ID dilewatkan menggunakan konfigurasi *run-time parameter session*: `SET LOCAL app.current_tenant_id = 'uuid'`.
* Keyword `LOCAL` menjamin bahwa parameter konfigurasi tersebut **hanya berlaku selama transaksi basis data berlangsung** (`BEGIN ... COMMIT/ROLLBACK`). Saat koneksi dikembalikan ke *connection pool* Rails, state tersebut otomatis terhapus, mencegah polusi koneksi.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Tiga Paradigma Multi-Tenancy

```
+-----------------------------------------------------------------------------------+
| Model 1: Database-per-Tenant                                                      |
| [Tenant A DB]           [Tenant B DB]           [Tenant C DB]                     |
| - Isolasi Fisik Total   - Skalabilitas Buruk    - Biaya Overhead Sangat Tinggi    |
+-----------------------------------------------------------------------------------+
| Model 2: Schema-per-Tenant (PostgreSQL Schemas)                                   |
| [Database Utama]                                                                  |
|   |-- Schema 'tenant_a' (Tables: users, orders)                                   |
|   |-- Schema 'tenant_b' (Tables: users, orders)                                   |
| - Isolasi Logis Tinggi  - Migrasi Schema Kompleks Lambat (DDL locks bertingkat)   |
+-----------------------------------------------------------------------------------+
| Model 3: Row-Level Shared Database (Standard Enterprise)                          |
| [Database Utama] -> Table: orders (Kolom: id, tenant_id, amount, ...)             |
| - Efisiensi resource tinggi - Membutuhkan RLS + Application Level Scoping ketat   |
+-----------------------------------------------------------------------------------+
```

#### Komparasi Arsitektural Multi-Tenancy

| Metrik Evaluasi | Database-per-Tenant | Schema-per-Tenant | Row-Level Security (RLS) |
| :--- | :--- | :--- | :--- |
| **Isolasi Data** | Sempurna (Fisik) | Sangat Baik (Namespaces) | Sempurna via DB Kernel Policy |
| **Overhead Migrasi (`db:migrate`)** | $O(N)$ koneksi database | $O(N)$ DDL Schema operations | $O(1)$ Operasi tabel standar |
| **Batas Skalabilitas Tenant** | Rendah (~ratusan) | Menengah (~ribuan) | Sangat Tinggi (Jutaan tenant) |
| **Efisiensi Connection Pool** | Sangat Buruk (Exhaustion) | Menengah (Metadata bloat)| Maksimal (Shared pool) |
| **Risiko Human-Error Leak** | Hampir Nol | Rendah | Nol (Jika RLS ditegakkan) |

### Autentikasi Enterprise: SAML 2.0 & OIDC
Pada segmen enterprise, username/password digantikan oleh arsitektur federasi identitas menggunakan SAML 2.0 atau OpenID Connect (OIDC).
* **Identity Provider (IdP):** Okta, Azure AD, PingIdentity, Google Workspace.
* **Service Provider (SP):** Aplikasi Rails Anda.
* Kunci otentikasi terletak pada penanganan *assertions*, validasi cryptographic signature (X.509 certificate validation), dan pencegahan *XML Signature Wrapping (XSW) attacks* serta *Replay Attacks* via transient cache validasi `InResponseTo`.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental context tenant terisolasi menggunakan `ActiveSupport::CurrentAttributes` yang dikombinasikan dengan middleware dan basis model aman.

### 1. Definisi Central Current Context
```ruby
# app/models/current.rb
class Current < ActiveSupport::CurrentAttributes
  attribute :tenant, :user, :request_id

  # Resilient assignment dengan validasi invariant
  def tenant=(tenant_record)
    super
    # Bind context ke TaggedLogging Rails secara real-time
    Rails.logger.tagged("TENANT:#{tenant_record&.id || 'ANONYMOUS'}")
  end
end
```

### 2. Tenant Context Middleware
```ruby
# app/middleware/tenant_context_middleware.rb
class TenantContextMiddleware
  def initialize(app)
    @app = app
  end

  def call(env)
    request = ActionDispatch::Request.new(env)
    
    # 1. Resolusi tenant via subdomain atau custom header
    subdomain = request.subdomain
    tenant = resolve_tenant(subdomain, request.headers["X-Tenant-Key"])

    if tenant.nil? && requires_tenant?(request)
      return [404, { "Content-Type" => "application/json" }, [{ error: "Tenant Not Found" }.to_json]]
    end

    # 2. Inisialisasi Current context dalam thread execution scope
    Current.set(tenant: tenant, request_id: request.uuid) do
      # 3. Jalankan request di dalam database transaction scope dengan RLS variable
      if tenant
        TenantDatabaseScope.isolate(tenant) do
          @app.call(env)
        end
      else
        @app.call(env)
      end
    end
  end

  private

  def resolve_tenant(subdomain, tenant_key)
    return Tenant.find_by(api_key: tenant_key) if tenant_key.present?
    return nil if subdomain.blank? || subdomain == "www"

    # Gunakan cache layer untuk mitigasi load database berlebih
    Rails.cache.fetch(["tenant_by_subdomain", subdomain], expires_in: 10.minutes) do
      Tenant.find_by(subdomain: subdomain, active: true)
    end
  end

  def requires_tenant?(request)
    # Bypass tenant requirement untuk health checks & status endpoint
    !request.path.start_with?("/up", "/healthz")
  end
end
```

### 3. Modul Database RLS Wrapper
```ruby
# app/services/tenant_database_scope.rb
class TenantDatabaseScope
  def self.isolate(tenant)
    ActiveRecord::Base.connection_pool.with_connection do |conn|
      # Membuka transaksi database untuk memastikan `SET LOCAL` terisolasi pada koneksi saat ini
      conn.transaction do
        # SET LOCAL menjamin nilai variabel dibersihkan saat transaksi COMMIT/ROLLBACK
        sanitized_id = conn.quote(tenant.id)
        conn.execute("SET LOCAL app.current_tenant_id = #{sanitized_id};")
        
        yield
      end
    end
  end
end
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Mari kita bedah secara komprehensif mekanisme dari potongan kode di atas:

### File: `app/models/current.rb`
* **Baris 2:** `class Current < ActiveSupport::CurrentAttributes`
  * Mewarisi modul singleton thread-safe Rails. Setiap thread/fiber mendapatkan copy terpisah dari state ini via `Thread.current`.
* **Baris 3:** `attribute :tenant, :user, :request_id`
  * Mendeklarasikan dynamic accessors (`Current.tenant`, `Current.tenant=`, dll.). Rails mendefinisikan getter/setter yang secara internal mengakses namespace `ActiveSupport::CurrentAttributes`.
* **Baris 6–9:** Method `tenant=` override
  * Memanggil `super` untuk mutasi internal state. Menambahkan tagging log secara otomatis via `Rails.logger.tagged`, menjamin semua log downstream yang diproduksi dalam request memiliki label identitas tenant tanpa konfigurasi berulang.

### File: `app/services/tenant_database_scope.rb`
* **Baris 3:** `ActiveRecord::Base.connection_pool.with_connection do |conn|`
  * Mengambil koneksi dari connection pool secara aman dan menjamin koneksi dikembalikan ke pool setelah block selesai dieksekusi, mencegah connection leak.
* **Baris 5:** `conn.transaction do`
  * Menerapkan RLS via runtime variables **wajib** dibungkus dalam blok transaksi PostgreSQL. Jika dieksekusi di luar transaksi (`SET app.current_tenant_id`), konfigurasi tersebut akan menempel permanen pada koneksi pooling, mengakibatkan *tenant bleeding* ke request pengguna lain di pool yang sama.
* **Baris 7:** `sanitized_id = conn.quote(tenant.id)`
  * Mencegah eksploitasi SQL Injection via dynamic parameter session.
* **Baris 8:** `conn.execute("SET LOCAL app.current_tenant_id = #{sanitized_id};")`
  * Menetapkan setting konfigurasi spesifik pada level engine PostgreSQL berstatus `LOCAL`. Keyword `LOCAL` menginstruksikan PostgreSQL untuk mengembalikan variabel ini ke nilai `DEFAULT` segera setelah block transaksi berakhir.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur B2B FinTech "GlobalLedger"
**Konteks Masalah:**
Perusahaan B2B SaaS FinTech "GlobalLedger" melayani perbankan dan enterprise dengan kebutuhan audit PCI-DSS dan SOC2 Type II. Sistem lama mengandalkan `acts_as_tenant` (aplikasi-level filtering). 

**Insiden Kritis:**
Seorang engineer menjalankan query pelaporan menggunakan raw SQL:
```ruby
# KODE BERBAHAYA SEBELUM REFACTORING
ActiveRecord::Base.connection.execute("SELECT SUM(amount) FROM transactions WHERE status = 'settled'")
```
Karena query tersebut mengeksekusi *raw SQL* tanpa `where(tenant_id: ...)`, query tersebut menjumlahkan transaksi milik *seluruh bank yang menjadi nasabah*. Data keuangan antar perbankan bocor ke laporan dashboard salah satu bank.

**Solusi Arsitektural:**
1. Mengintegrasikan **PostgreSQL Row-Level Security (RLS)** murni pada tingkat skema database untuk semua tabel transaksional.
2. Membangun middleware Rails yang menginjeksi context tenant ke PostgreSQL session sebelum controller atau model apapun disentuh.
3. Mengganti autentikasi berbasis session standard dengan SAML 2.0 Identity Provider integration dan hardware-backed MFA (WebAuthn/FIDO2).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi end-to-end integrasi database kernel RLS, SAML authentication handler, dan thread-safe background isolation.

### 1. Migrasi Database PostgreSQL untuk Menegakkan RLS

```ruby
# db/migrate/20260330000001_create_enterprise_tenancy_and_rls.rb
class CreateEnterpriseTenancyAndRls < ActiveRecord::Migration[7.1]
  def change
    # Aktifkan ekstensi UUID untuk tenant-safe identification
    enable_extension 'pgcrypto' unless extension_enabled?('pgcrypto')

    create_table :tenants, id: :uuid do |t|
      t.string :name, null: false
      t.string :subdomain, null: false, index: { unique: true }
      t.string :saml_issuer, null: true
      t.text   :saml_certificate, null: true
      t.boolean :active, default: true, null: false
      t.timestamps
    end

    create_table :ledgers, id: :uuid do |t|
      t.references :tenant, type: :uuid, null: false, foreign_key: { on_delete: :cascade }, index: true
      t.string :account_number, null: false
      t.decimal :balance, precision: 18, scale: 4, default: 0.0, null: false
      t.timestamps
    end

    reversible do |dir|
      dir.up do
        # 1. Aktifkan RLS pada tabel ledgers
        execute "ALTER TABLE ledgers ENABLE ROW LEVEL SECURITY;"
        execute "ALTER TABLE ledgers FORCE ROW LEVEL SECURITY;" # Memaksa table owner agar terkena RLS

        # 2. Buat Security Policy berbasis app.current_tenant_id session variable
        execute <<~SQL
          CREATE POLICY tenant_isolation_policy ON ledgers
          AS RESTRICTIVE
          USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
        SQL
      end

      dir.down do
        execute "DROP POLICY IF EXISTS tenant_isolation_policy ON ledgers;"
        execute "ALTER TABLE ledgers DISABLE ROW LEVEL SECURITY;"
      end
    end
  end
end
```

### 2. Base Application Record Terproteksi RLS

```ruby
# app/models/application_record.rb
class ApplicationRecord < ActiveRecord::Base
  primary_abstract_class

  # Hook deterministik untuk model yang memiliki foreign_key tenant_id
  def self.enforce_tenant_scoping!
    before_validation :auto_assign_tenant, on: :create
    validates :tenant_id, presence: true

    # Scope darurat (Layer 3 App-Level Scoping sebagai pelengkap Layer 4 RLS)
    default_scope do
      if Current.tenant.present?
        where(tenant_id: Current.tenant.id)
      else
        all
      end
    end
  end

  private

  def auto_assign_tenant
    self.tenant_id ||= Current.tenant&.id
  end
end
```

### 3. Model Terisolasi

```ruby
# app/models/ledger.rb
class Ledger < ApplicationRecord
  enforce_tenant_scoping!

  belongs_to :tenant
  
  validates :account_number, presence: true, uniqueness: { scope: :tenant_id }
  validates :balance, numericality: true
end
```

### 4. Controller SAML Enterprise Authentication

```ruby
# app/controllers/auth/saml_sessions_controller.rb
module Auth
  class SamlSessionsController < ActionController::Base
    protect_from_forgery except: :consume # SAML POST berasal dari IdP eksternal

    # Inisiasi SSO: Redirect ke Okta/Azure AD
    def create
      tenant = Tenant.find_by!(subdomain: params[:subdomain])
      saml_request = OneLogin::RubySaml::Authrequest.new
      redirect_to saml_request.create(saml_settings_for(tenant)), allow_other_host: true
    end

    # Assertion Consumer Service (ACS) Endpoint
    def consume
      tenant = Tenant.find_by!(id: params[:RelayState])
      response = OneLogin::RubySaml::Response.new(
        params[:SAMLResponse],
        settings: saml_settings_for(tenant)
      )

      if response.is_valid?
        user = find_or_provision_user(tenant, response)
        
        # Rotasi Session Fixation ID
        reset_session
        
        session[:user_id] = user.id
        session[:tenant_id] = tenant.id
        session[:last_authenticated_at] = Time.current.to_i

        redirect_to dashboard_url(subdomain: tenant.subdomain), notice: "SSO Login Berhasil"
      else
        Rails.logger.error("SAML Validation Failure: #{response.errors}")
        render json: { error: "SAML Signature Invalid", details: response.errors }, status: :unauthorized
      end
    end

    private

    def saml_settings_for(tenant)
      settings = OneLogin::RubySaml::Settings.new
      settings.assertion_consumer_service_url = auth_saml_consume_url(subdomain: tenant.subdomain)
      settings.issuer                         = "globalledger-sp-entity-id"
      settings.idp_sso_target_url             = tenant.saml_issuer
      settings.idp_cert                       = tenant.saml_certificate
      settings.name_identifier_format         = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
      settings
    end

    def find_or_provision_user(tenant, saml_response)
      email = saml_response.nameid
      user = nil

      # Eksekusi write dalam database scope tenant
      TenantDatabaseScope.isolate(tenant) do
        user = User.find_or_initialize_by(email: email, tenant_id: tenant.id)
        user.first_name = saml_response.attributes["firstName"] || "Corporate"
        user.last_name  = saml_response.attributes["lastName"]  || "User"
        user.save!
      end

      user
    end
  end
end
```

### 5. Multi-Tenant Sidekiq Job Context Propagation

```ruby
# app/workers/application_tenant_job.rb
class ApplicationTenantJob
  include Sidekiq::Job

  # Error kelas khusus untuk mitigasi orphaned job
  class MissingTenantContextError < StandardError; end

  def perform(tenant_id, worker_payload)
    tenant = Tenant.find_by(id: tenant_id)
    raise MissingTenantContextError, "Tenant context #{tenant_id} missing on worker execution" unless tenant

    # Rekonstruksi thread context
    Current.set(tenant: tenant) do
      # Pasang RLS session level pada PostgreSQL connection milik worker
      TenantDatabaseScope.isolate(tenant) do
        execute_isolated_job(worker_payload)
      end
    end
  end

  def execute_isolated_job(payload)
    raise NotImplementedError, "Worker wajib mengimplementasikan execute_isolated_job"
  end
end

# Implementasi Job Konkret
# app/workers/generate_settlement_report_worker.rb
class GenerateSettlementReportWorker < ApplicationTenantJob
  def execute_isolated_job(payload)
    # Kueri di bawah ini 100% aman via RLS, bahkan jika developer tidak menyertakan tenant_id
    total_balance = Ledger.sum(:balance)
    Rails.logger.info("Ledger calculated for #{Current.tenant.name}: #{total_balance}")
    # Kirim report ke ERP service...
  end
end
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Arsitektur otorisasi dan kontrol akses memiliki implikasi trade-off performa yang signifikan.

```
                           KOMPLEKSITAS ARSITEKTURAL
                                      ^
                                      |            [ABAC: Policy Based Engine]
                                      |            (ActionPolicy + RLS Database)
                                      |            - Dynamic condition checks
                                      |            - Kepatuhan regulasi tinggi
                                      |
         [RBAC Sederhana]             |
         (Role string di users)       |
         - Cepat, memori kecil        |
         - Tidak elastis              |
         +----------------------------------------------------> OVERHEAD PERFORMA
```

### Perbandingan Framework Otorisasi: CanCanCan vs Pundit vs ActionPolicy

| Fitur / Parameter | CanCanCan | Pundit | ActionPolicy |
| :--- | :--- | :--- | :--- |
| **Model Evaluasi** | Monolitik (`Ability.rb`) | Plain Old Ruby Object (PORO) Policies | Pre-compiled Rules & Memoized AST |
| **Alokasi Memori (Allocations/Req)** | Sangat Tinggi ($O(rules)$ objek) | Rendah (1 instance per authorization) | Hampir Nol (Target memoization caching) |
| **Performa Predikat (Throughput)** | Lambat pada ribuan rule | Cepat | Paling Cepat (C-level optimization friendly) |
| **Dukungan Scoping / Multi-tenancy**| Sering menimbulkan SQL bloated | Tergantung Scope class | Otomatis via scoping rules teroptimasi |
| **Rekomendasi Enterprise** | Warisan (Legacy Only) | Standard Microservices | **Production Tier 1 Enterprise** |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Connection Pooling & Prepared Statements Polusi
* **Masalah:** Jika menggunakan `SET SESSION app.current_tenant_id` bukannya `SET LOCAL`, nilai variabel menetap di koneksi pool ActiveRecord. Ketika koneksi dikembalikan ke Puma worker thread lain untuk melayani request Tenant B, transaksi read dapat membaca data milik Tenant A.
* **Solusi:** Selalu gunakan `SET LOCAL` di dalam transaksi aktif (`conn.transaction do ... end`). Jangan biarkan variabel session RLS diset di luar batas blok transaksi.

### 2. Sidekiq Concurrency & Thread-Inherited Context
* **Masalah:** `Thread.current` tidak diwariskan ke thread pool Sidekiq secara implisit. Jika developer melakukan `SettlementJob.perform_async(data)` tanpa menyertakan `tenant_id`, worker akan berjalan dengan `Current.tenant = nil`. Jika database RLS aktif, query akan mengembalikan kumpulan data kosong (0 rows), menyebabkan data processing silent-failure.
* **Solusi:** Buat custom Sidekiq Client & Server Middleware yang otomatis mem-pack `Current.tenant.id` ke dalam payload jobs saat enqueueing, dan membongkarnya di server context.

### 3. Caching Collision via SolidCache / Redis
* **Masalah:** Menggunakan Rails fragment cache atau low-level cache:
  ```ruby
  Rails.cache.fetch("dashboard_stats") { compute_expensive_stats }
  ```
  Data milik satu tenant akan terbaca oleh tenant lain yang memanggil cache key yang sama.
* **Solusi:** Override namespace cache Rails agar otomatis menyertakan tenant ID:
  ```ruby
  # config/initializers/cache_tenant_namespace.rb
  module TenantCacheNamespace
    def expand_cache_key(key, namespace = nil)
      tenant_prefix = Current.tenant ? "tenant:#{Current.tenant.id}" : "tenant:global"
      super([tenant_prefix, key], namespace)
    end
  end
  ActiveSupport::Cache.singleton_class.prepend(TenantCacheNamespace)
  ```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Ketergantungan Tunggal pada `default_scope`
* **Anti-Pattern:**
  ```ruby
  class Order < ApplicationRecord
    default_scope { where(tenant_id: Current.tenant.id) }
  end
  ```
* **Dampak Buruk:** Pemanggilan method seperti `unscoped`, `Order.reorder(...)`, atau asosiasi bertingkat tertentu akan menghapus `default_scope`. Hal ini membuka proteksi isolasi data dan berpotensi menampilkan data semua tenant.
* **Perbaikan:** Gunakan PostgreSQL Row-Level Security (RLS) pada lapisan database sebagai pengaman utama, dan gunakan *explicit scoping* atau `acts_as_tenant` hanya untuk lapisan UI/API filtering.

### 2. SQL Injection pada Set Parameter RLS
* **Anti-Pattern:**
  ```ruby
  ActiveRecord::Base.connection.execute("SET LOCAL app.current_tenant_id = '#{params[:tenant_id]}'")
  ```
* **Dampak Buruk:** Attacker dapat menginjeksi payload: `' OR '' = '; --`, sehingga RLS bypassed atau dinonaktifkan.
* **Perbaikan:** Sanitasi ketat menggunakan `ActiveRecord::Base.connection.quote` atau gunakan prepared statement:
  ```ruby
  sanitized = ActiveRecord::Base.connection.quote(tenant.id)
  ActiveRecord::Base.connection.execute("SET LOCAL app.current_tenant_id = #{sanitized}")
  ```

### 3. Session Fixation pada Login Handler Kustom
* **Anti-Pattern:** Membiarkan Session ID Rails tetap sama sebelum dan sesudah verifikasi password/SAML.
* **Perbaikan:** Selalu panggil `reset_session` sebelum mengisi session data baru pasca-otentikasi berhasil:
  ```ruby
  def on_authentication_success(user)
    reset_session # Wajib: Hapus session lama dan alokasikan Cookie ID baru
    session[:user_id] = user.id
  end
  ```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Enforce Database Non-Bypassable RLS:** Gunakan `FORCE ROW LEVEL SECURITY` pada tabel-tabel penting. Secara default, PostgreSQL tidak menerapkan RLS pada database table owner/superuser kecuali klausul `FORCE` disematkan.
2. **Deterministic Cryptographic Key Management:** Pisahkan enkripsi data per-tenant menggunakan kunci turunan (*Envelope Encryption*). Kunci enkripsi root disimpan di AWS KMS / Vault, dengan *Data Encryption Key (DEK)* unik untuk masing-masing tenant.
3. **Session Hardening Flag:** Konfigurasikan Session Cookie secara ketat di `config/initializers/session_store.rb`:
   ```ruby
   Rails.application.config.session_store :cookie_store,
     key: '_enterprise_session',
     secure: Rails.env.production?,
     httponly: true,
     same_site: :strict,
     expire_after: 12.hours
   ```
4. **Zero-Trust Cross-Tenant Queries:** Jika proses background memerlukan agregasi lintas tenant (misal: penagihan global SaaS), buat role database khusus (`global_reporter`) yang diberikan hak bypass RLS secara eksplisit (`BYPASSRLS`), dan jalankan di database replica terpisah.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Indexing Komposit dengan Tenant ID
Dalam arsitektur *Shared-Database Row-Level*, seluruh query yang dioptimasi oleh engine PostgreSQL RLS akan diinjeksi klausul `AND tenant_id = 'xxx'`. Oleh karena itu, semua index tunggal tradisional harus diubah menjadi **Compound Indexes**.

```
[ Traditional Index ]
INDEX ON users(email)
Execution: Filter email -> Check RLS Tenant Condition (Heap Fetch Overhead)

[ Enterprise Composite Index ]
INDEX ON users(tenant_id, email)
Execution: B-Tree Index Jump langsung ke slice data Tenant -> Scan email
```

#### SQL Optimization Migration:
```ruby
class OptimizeIndexesForRls < ActiveRecord::Migration[7.1]
  disable_ddl_transaction!

  def change
    # Hapus indeks lama yang tidak memiliki tenant_id
    remove_index :ledgers, :account_number, if_exists: true

    # Buat indeks komposit concurrent tanpa locking tabel produksi
    add_index :ledgers, [:tenant_id, :account_number], 
              algorithm: :concurrently, 
              name: "idx_ledgers_tenant_account_perf"
  end
end
```

### Connection Pool Optimization
Hindari arsitektur *Database-per-tenant* jika tenant melebihi 50 entitas. Jika terdapat 200 tenant dengan 5 Puma worker per tenant, aplikasi memerlukan minimal 1.000 koneksi PostgreSQL idle. Ini dapat menyebabkan CPU context-switch berlebih dan degradasi performa pada database server. RLS dengan Shared Database mempertahankan jumlah koneksi konstan sesuai batas standard Puma pool size (misal: 15–20 koneksi per instance).

---

## SEKSI 16 — KEAMANAN & HARDENING

### Implementasi Dynamic Database Role Sandboxing

Untuk mencegah framework bug mengeksekusi DDL atau bypass kontrol, manfaatkan *Role Privilege Separation* di PostgreSQL.

```sql
-- Dijalankan pada provisioning database produksi
CREATE ROLE app_runtime_user WITH LOGIN PASSWORD 'strong_password';
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_runtime_user;

-- Hanya berikan DML pada runtime user
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_runtime_user;

-- Runtime user TIDAK BOLEH memiliki atribut superuser atau bypassrls
ALTER ROLE app_runtime_user NOBYPASSRLS;
```

### Content-Security-Policy (CSP) untuk Proteksi Sesi Enterprise
Cegah ekfiltrasi session cookie dan XSS yang dapat mencuri kredensial token enterprise:

```ruby
# config/initializers/content_security_policy.rb
Rails.application.configure do
  config.content_security_policy do |policy|
    policy.default_src :none
    policy.font_src    :self, :https, :data
    policy.img_src     :self, :https, :data
    policy.object_src  :none
    policy.script_src  :self
    policy.style_src   :self
    policy.connect_src :self
    policy.base_uri    :none
    policy.form_action :self
    policy.frame_ancestors :none # Mencegah Clickjacking
  end
  config.content_security_policy_nonce_generator = ->(request) { request.session.id.to_s }
  config.content_security_policy_nonce_directives = %w(script-src)
end
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Di lingkungan enterprise, pelacakan jejak audit (*audit trails*) adalah kewajiban regulasi. Logger harus secara konsisten memuat identitas tenant, user executor, dan correlation ID untuk distributed tracing.

### 1. Semantic Tagged Logger Setup
```ruby
# config/environments/production.rb
Rails.application.configure do
  config.log_tags = [
    :request_id,
    ->(req) { "Tenant:#{Current.tenant&.id || 'unassigned'}" },
    ->(req) { "User:#{Current.user&.id || 'anonymous'}" }
  ]
end
```

### 2. Tenant Context Telemetry Tracer (ActiveSupport::Notifications)
```ruby
# config/initializers/tenant_telemetry.rb
ActiveSupport::Notifications.subscribe("sql.active_record") do |name, start, finish, id, payload|
  # Pantau jika terjadi kueri tanpa tenant parameter di development/staging
  if Rails.env.development? && payload[:sql].match?(/FROM\s+"ledgers"/i)
    unless payload[:sql].include?("app.current_tenant_id") || payload[:sql].include?("tenant_id")
      Rails.logger.warn("[SECURITY WARN] Query pada tabel ledgers tanpa filter eksplisit: #{payload[:sql]}")
    end
  end
end
```

### Format Log Output:
```json
{
  "timestamp": "2026-03-30T10:14:22.102Z",
  "request_id": "c71a3962-e64e-4e4b-b0b9-502847a96df8",
  "tenant_id": "90e0b3c8-7f41-4c12-a1b9-3e33b666a7b1",
  "user_id": "3127",
  "severity": "INFO",
  "message": "Processing LedgersController#index (SQL 1.2ms) Duration: 14.2ms"
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **ActiveSupport::CurrentAttributes:** Thread-isolated global store. Selalu bungkus eksekusinya menggunakan `Current.set(...) do ... end` untuk memastikan proses cleanup context berjalan otomatis.
* **PostgreSQL RLS:** Mekanisme isolasi data pada level database kernel. Aktifkan dengan `ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;` dan paksakan dengan `FORCE ROW LEVEL SECURITY`.
* **Runtime Isolation:** Gunakan `SET LOCAL app.current_tenant_id = 'xxx'` di dalam PostgreSQL transaction block (`conn.transaction`). Jangan pernah menggunakan `SET` tanpa scope `LOCAL` pada shared connection pool.
* **Background Jobs (Sidekiq):** Context thread tidak ditransfer secara otomatis ke async workers. Selalu parsing `tenant_id` sebagai argumen pertama job, lalu rekonstruksi context menggunakan helper isolated wrapper.
* **Composite Indexes:** Ganti semua primary index unik menjadi komposit dengan `tenant_id` di posisi pertama: `add_index :table, [:tenant_id, :target_column]`.
* **Session Hardening:** Eksekusi `reset_session` saat login untuk mencegah session fixation. Konfigurasikan cookie dengan flag `SameSite=Strict`, `Secure=true`, dan `HttpOnly=true`.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah jawaban yang paling tepat dan cocokkan dengan kunci jawaban komprehensif.

### Bagian 1: Konsep Dasar (5 Soal)

**Soal 1:** Mengapa penggunaan `default_scope` tunggal di ActiveRecord dianggap tidak memadai untuk sistem multi-tenancy enterprise?
* A) Karena `default_scope` memperlambat kecepatan compile class Ruby.
* B) Karena `default_scope` dapat dilewati (*bypassed*) secara tidak sengaja melalui pemanggilan method seperti `unscoped`, `reorder`, atau kueri custom.
* C) Karena `default_scope` tidak dapat membaca nilai dari `CurrentAttributes`.
* D) Karena database PostgreSQL memblokir eksekusi query yang memiliki `default_scope`.

**Soal 2:** Apa fungsi kata kunci `LOCAL` pada perintah SQL `SET LOCAL app.current_tenant_id = 'uuid'`?
* A) Menetapkan parameter hanya pada mesin lokal (localhost/development environment).
* B) Memastikan konfigurasi tersimpan permanen di disk database PostgreSQL.
* C) Membatasi cakupan (*scope*) variabel konfigurasi hanya selama transaksi database aktif berlangsung.
* D) Mengubah timezone koneksi PostgreSQL sesuai timezone lokal pengguna.

**Soal 3:** Apa risiko terbesar menggunakan `Thread.current[:tenant]` secara manual tanpa membersihkannya di akhir request?
* A) Menimbulkan memory bloat pada RAM server hingga crash seketika.
* B) Nilai variabel tertinggal di thread yang sama, sehingga koneksi request berikutnya membaca data tenant lama (*cross-tenant bleeding*).
* C) Menyebabkan koneksi HTTP beralih otomatis dari protokol HTTPS ke HTTP biasa.
* D) Mengakibatkan database PostgreSQL mengalami deadlock pada penulisan baris baru.

**Soal 4:** Mengapa pemanggilan `reset_session` wajib dilakukan sesaat setelah proses otentikasi login pengguna berhasil?
* A) Untuk menghapus cache memori Redis aplikasi.
* B) Mencegah serangan *Session Hijacking* dan *Session Fixation* dengan mengacak kembali Session ID.
* C) Mengembalikan kuota database connection pool ke angka default.
* D) Menyetel ulang CSRF token menjadi nilai string kosong.

**Soal 5:** Apa manfaat menambahkan perintah `FORCE ROW LEVEL SECURITY` pada PostgreSQL?
* A) Menerapkan RLS ke semua pengguna, termasuk user owner pembuat tabel (kecuali bypass superuser khusus).
* B) Menghapus policy lama dan membuat policy baru secara otomatis.
* C) Mempercepat proses indexing B-Tree hingga dua kali lipat.
* D) Mencegah koneksi non-SSL masuk ke server database.

---

### Bagian 2: Skenario Kompleks & Analisis (5 Soal)

**Soal 6:** Sebuah background worker Sidekiq dijalankan dengan kode:
```ruby
def perform(order_id)
  order = Order.find(order_id)
  order.process_payment!
end
```
Jika PostgreSQL RLS diaktifkan dengan policy `tenant_id = current_setting('app.current_tenant_id')::uuid`, apa yang terjadi saat worker dieksekusi?
* A) Worker memproses pembayaran pesanan dengan normal dan mencatat log.
* B) Kueri menghasilkan error `ActiveRecord::RecordNotFound` karena setting session RLS belum diset (`NULL`), sehingga tabel memblokir pembacaan data.
* C) Sidekiq otomatis menyuntikkan `tenant_id` dari model `Order`.
* D) Database PostgreSQL secara otomatis menonaktifkan RLS saat membaca thread worker.

**Soal 7:** Seorang software architect mendesain arsitektur SaaS yang diproyeksikan memiliki 50.000 tenant UMKM. Model multi-tenancy manakah yang paling **buruk** untuk dipilih dan berisiko gagal secara infrastruktur?
* A) Row-Level Multi-Tenancy dengan PostgreSQL RLS.
* B) Row-Level Multi-Tenancy dengan ActsAsTenant.
* C) Database-per-Tenant.
* D) Single Database dengan composite indexing.

**Soal 8:** Perhatikan fragment cache berikut:
```erb
<% cache ["invoice_summary", @invoice.id] do %>
  <%= render @invoice %>
<% end %>
```
Kelemahan arsitektur security apa yang ada pada kode di atas pada environment Multi-Tenant?
* A) Cache fragment tidak dapat di-serialize oleh Redis.
* B) Terjadi potensi tabrakan cache (*Cache Poisoning/Bleeding*) jika ID antar tenant berupa integer auto-increment yang sama, sehingga data invoice tenant A tampil di layar tenant B.
* C) Rails tidak mengizinkan pemanggilan partial rendering di dalam block cache.
* D) Invoice otomatis terhapus dari database jika cache expired.

**Soal 9:** Mengapa index PostgreSQL `CREATE INDEX ON orders(created_at)` tidak efisien pada database multi-tenant dengan volume jutaan data ber-RLS?
* A) Karena RLS mematikan fungsionalitas B-Tree index secara total.
* B) Karena PostgreSQL harus membaca seluruh index `created_at` lalu melakukan filter sequential heap fetch terpisah untuk mencocokkan `tenant_id`.
* C) Karena kolom bertipe timestamp tidak didukung oleh RLS policy.
* D) Karena index tersebut akan terkunci (*table lock*) setiap kali transaksi baru dibuat.

**Soal 10:** Pada implementasi SAML 2.0 di Rails, apa tujuan utama dilakukannya validasi atribut `InResponseTo` pada respons token IdP?
* A) Mempercepat waktu respon koneksi HTTPS.
* B) Mencegah serangan *SAML Replay Attack*, yaitu penyerang menangkap paket autentikasi legal lalu mengirimkannya kembali ke sistem.
* C) Mengubah format nama atribut menjadi huruf kecil (lowercase).
* D) Mengatur umur sesi pengguna agar sinkron dengan IdP server.

---

### Kunci Jawaban & Pembahasan

1. **Jawaban: B.** `default_scope` sangat rentan karena mudah di-bypass oleh developer menggunakan `unscoped` atau query dinamis tertentu, sehingga membahayakan isolasi data tenant.
2. **Jawaban: C.** `LOCAL` membatasi efek variabel konfigurasi hanya pada transaksi aktif yang sedang berjalan dan di-reset saat transaksi selesai (commit/rollback).
3. **Jawaban: B.** Thread pool webserver (seperti Puma) menggunakan kembali thread yang sama untuk melayani request berikutnya. Jika context tidak di-reset, request baru akan mewarisi context tenant sebelumnya.
4. **Jawaban: B.** Mengganti Session ID lama dengan Session ID baru pasca-otentikasi adalah mitigasi standar untuk mencegah serangan Session Fixation.
5. **Jawaban: A.** Secara default di PostgreSQL, tabel owner/pembuat tabel bebas dari aturan RLS. `FORCE ROW LEVEL SECURITY` memaksa aturan RLS tetap dieksekusi meskipun diakses oleh user tabel owner.
6. **Jawaban: B.** Karena Sidekiq berjalan di proses/thread baru tanpa middleware Rails web, variabel session PostgreSQL bernilai `NULL`. Akibatnya, RLS policy menyaring dan memblokir baris data tersebut, menghasilkan exception `RecordNotFound`.
7. **Jawaban: C.** Membuka 50.000 database fisik berbeda akan menghabiskan sumber daya connection pool, membebani memory database engine, dan membuat proses migrasi schema mustahil dikelola dalam batas waktu pemeliharaan.
8. **Jawaban: B.** Auto-increment integer berulang pada tiap entitas tenant (misal: ID=1 milik Tenant A dan ID=1 milik Tenant B). Kunci cache harus selalu diberi namespace tenant (misal: `["tenant:#{current_tenant.id}", "invoice_summary", @invoice.id]`).
9. **Jawaban: B.** Tanpa index komposit `(tenant_id, created_at)`, database harus memindai data lintas seluruh tenant di index sebelum membuang data yang bukan milik tenant saat ini, menyebabkan overhead I/O tinggi.
10. **Jawaban: B.** Validasi `InResponseTo` memastikan assertion SAML yang diterima memang merupakan balasan langsung atas request spesifik yang dikirimkan oleh Service Provider, mencegah replay attack token bekas.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Real-World Engineering Lab: "Zero-Leak Multi-Tenant Core"

#### Deskripsi Misi:
Bangun sebuah micro-engine Rails 7+ API-only yang menerapkan sistem isolasi data Row-Level Security tingkat tinggi dengan skenario pengujian ketat (*zero-leak tolerance*).

#### Spesifikasi Fungsional:
1. **Model & Migration:**
   * Buat model `Organization` (sebagai Tenant) dengan kolom: `id (UUID)`, `subdomain (string)`, `api_key (string)`.
   * Buat model `Document` dengan kolom: `id (UUID)`, `organization_id (UUID)`, `title (string)`, `classified_content (text)`.
   * Tulis migration mentah PostgreSQL untuk mengaktifkan RLS pada tabel `documents` dengan policy berbasis session parameter `app.current_org_id`.
2. **Context Manager:**
   * Bangun custom Rack Middleware yang membaca header `X-Organization-Key`.
   * Bind tenant ke `Current.organization`.
   * Bungkus setiap request database ke dalam helper `with_tenant_isolation` yang memanggil `SET LOCAL app.current_org_id`.
3. **Automated Exploit Prevention Test (RSpec):**
   * Tulis Integration/Request Spec yang mendemonstrasikan bahwa:
     1. Organisasi A tidak dapat membaca dokumen milik Organisasi B via API standard.
     2. Eksekusi raw SQL `ActiveRecord::Base.connection.execute("SELECT * FROM documents")` di dalam controller action **hanya mengembalikan data milik organisasi yang sedang aktif**.
     3. Request tanpa header `X-Organization-Key` mengembalikan respon `401 Unauthorized` tanpa menyentuh layer database.
4. **Sidekiq Propagation Verification:**
   * Buat background job `DocumentArchiverWorker` yang menerima `organization_id` dan `document_id`.
   * Buktikan dalam unit test bahwa job tersebut gagal jika dijalankan tanpa membungkus prosesnya di dalam helper tenant scope.

#### Tolok Ukur Keberhasilan (Definition of Done):
* Seluruh test suite RSpec lulus tanpa error (`100% green`).
* Tidak ada query SQL di log aplikasi yang mengekspos kebocoran baris data milik organization lain.
* Codebase bersih dari penggunaan `default_scope` yang rapuh, dan sepenuhnya bergantung pada PostgreSQL RLS + Application Level Scoping yang redundan.