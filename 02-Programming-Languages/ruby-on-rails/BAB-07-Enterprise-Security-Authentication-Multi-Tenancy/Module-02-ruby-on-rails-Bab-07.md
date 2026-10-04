# Kurikulum Enterprise: Ruby on Rails
## Bab 07: Enterprise Security, Authentication, & Multi-Tenancy
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Architect / Senior Engineer diharapkan mampu:
1. **Mendesain dan Mengimplementasikan Arsitektur Multi-Tenancy Tingkat Lanjut**: Membangun sistem multi-tenant terisolasi penuh menggunakan PostgreSQL *Row-Level Security* (RLS) dan *Schema-based Isolation* pada Rails 7.1+, mengeliminasi risiko kebocoran data (*cross-tenant data leakage*) hingga level *kernel database*.
2. **Menguasai Engine Autentikasi dan Middleware Warden**: Membongkar *lifecycle* internal Warden dan `Devise`, serta mengimplementasikan strategi autentikasi kustom berbasis *stateless/stateful hybrid tokens*, rotasi kunci asimetris (RS256/Ed25519), dan mitigasi *side-channel attacks*.
3. **Mengonfigurasi Fine-Grained Authorization Terdistribusi**: Mengimplementasikan *Attribute-Based Access Control* (ABAC) performa tinggi menggunakan `Action Policy` dengan *pre-compiled AST rules* dan integrasi *cache-aware authorization*.
4. **Menerapkan Pertahanan Siber Proaktif & Audit Komprehensif**: Mengamankan aplikasi Rails dari *ReDoS*, *Arel Injection*, *Mass Assignment bypass*, dan mengonfigurasi *tamper-proof cryptographic audit trail* yang memenuhi standar SOC2 Type II dan ISO 27001.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib memiliki pemahaman mendalam tentang:
*   **Ruby Internals**: Model *concurrency* Ruby (Thread, Fiber, GVL/GIL), Metaprogramming (`Module#prepend`, `define_method`, `const_missing`), dan Garbage Collection lifecycle.
*   **Rails Internals**: Arsitektur Rack Middleware stack, `ActiveSupport::CurrentAttributes`, lifecycle `ActiveRecord::Relation`, dan `ActiveRecord::ConnectionAdapters`.
*   **Database Engineering**: PostgreSQL internals (MVCC, schemas, execution plans, *connection pooling* via PgBouncer, Row-Level Security, transactional DDL).
*   **Kriptografi Aplikasi**: TLS termination, HMAC-SHA256, asymmetric encryption (RSA/ECDSA), PBKDF2/Argon2id hashing, dan mitigasi *timing attacks*.

---

### 3. Concept & Internal Architecture

#### 3.1. Anatomi Multi-Tenancy: Shared Database vs. RLS vs. Separate Schemas

Dalam arsitektur enterprise, isolasi data tenant tidak boleh hanya bergantung pada *application-level scoping* (seperti `default_scope` Rails yang rentan dibatalkan oleh `unscoped`). 

```
                                  [ incoming Request ]
                                           │
                                           ▼
                                 [ Rack Middleware Stack ]
                                           │
                                           ▼
                   ┌───────────────────────────────────────────────┐
                   │  TenantResolution Middleware                  │
                   │  - Ekstraksi Subdomain / JWT Claims          │
                   │  - Set Current.tenant & Current.request_id    │
                   └───────────────────────┬───────────────────────┘
                                           │
                                           ▼
                   ┌───────────────────────────────────────────────┐
                   │  Warden Engine / Rails Application Layer      │
                   │  - Auth Verification & Action Policy (ABAC)   │
                   └───────────────────────┬───────────────────────┘
                                           │
                         [ ActiveRecord Connection Pool ]
                                           │
        ┌──────────────────────────────────┴──────────────────────────────────┐
        ▼                                                                     ▼
[ Strategi 1: Row-Level Security (RLS) ]          [ Strategi 2: Separate Schemas ]
SET LOCAL app.current_tenant_id = 'tenant_uuid';   SET search_path TO tenant_slug, public;
        │                                                                     │
        ▼                                                                     ▼
┌──────────────────────────────────────┐          ┌──────────────────────────────────────┐
│        PostgreSQL Shared Tables      │          │        PostgreSQL Schemas            │
│  - accounts (tenant_id = '...')      │          │  - tenant_a.accounts                 │
│  - ledgers (tenant_id = '...')       │          │  - tenant_b.accounts                 │
│  * Diinspeksi otomatis oleh PG Engine│          │  * Terisolasi via search_path DDL    │
└──────────────────────────────────────┘          └──────────────────────────────────────┘
```

##### 3.1.1. PostgreSQL Row-Level Security (RLS) Deep Dive
RLS memindahkan penegakan batas keamanan (*security boundary enforcement*) dari kode Ruby ke *query planner* PostgreSQL. Setiap tabel memiliki relasi policy:

$$\sigma_{tenant\_id = current\_setting('app.current\_tenant\_id')}(Tabel)$$

Ketika Rails membuka koneksi, transaksi dieksekusi dengan `SET LOCAL app.current_tenant_id = '...'`. PostgreSQL secara otomatis menginjeksi filter RLS ke dalam *Abstract Syntax Tree* (AST) query sebelum kalkulasi *query execution plan*. Bypass melalui Rails bug, injeksi raw SQL, maupun *unscoped associations* menjadi mustahil karena kernel database menolak akses pada level blok penyimpanan (*heap page*).

##### 3.1.2. Memory Leakage dan Concurrency Hazard pada `CurrentAttributes`
Rails menyediakan `ActiveSupport::CurrentAttributes` yang berbasis pada `Fiber.current[:current_attributes]` atau `Thread.current`. Pada web server multithreaded (Puma) atau sistem background processing berbasis fiber/worker (Falcon, GoodJob, Sidekiq), *state* yang tersimpan dapat mengalami *leakage* (kebocoran) ke request berikutnya jika thread di-reuse oleh *thread pool*. 

Lifecycle `ActiveSupport::CurrentAttributes` terikat pada `ActionDispatch::Executor`. Apabila pemanggilan terjadi di luar konteks Rack lifecycle standar (misalnya pada thread manual `Thread.new`), `Current.reset` tidak terpanggil otomatis, memicu celah eskalasi hak akses (*tenant crossover vulnerability*).

#### 3.2. Warden Lifecycle & Authentication Internals

`Devise` merupakan wrapper di atas Rack engine bernama `Warden`. Alur eksekusi internal Warden berjalan sebagai berikut:

```
Rack Request -> Warden::Manager -> Warden::Proxy -> Environment Hash (env['warden'])
                      │
                      ├──> Strategies Evaluator (e.g., :jwt, :database_authenticatable)
                      │      ├── #valid? (Pre-check header/parameter)
                      │      └── #authenticate! (Eksekusi verifikasi)
                      │             ├── success!(user) -> Halt strategy chain
                      │             ├── fail!(message) -> Continue/Halt chain
                      │             └── pass -> Next strategy
                      │
                      └──> Call Downstream App (Rails Controllers)
```

Warden menyimpan state pengguna di dalam session (`env['rack.session']`). Pada arsitektur hybrid modern (API + SSR), penyimpanan session harus dipisahkan:
1. **Web Sessions**: Menggunakan cookie terenkripsi (`AES-256-GCM`) dengan flag `HttpOnly`, `SameSite=Lax/Strict`, dan `Secure`.
2. **API Access**: Menggunakan asymmetric short-lived access tokens (JWT) yang diverifikasi di memory via *public keys*, dipadukan dengan database revocation layer (Redis O(1) bloom filters / database session ID revocation).

---

### 4. Why & What

| Pendekatan | Masalah Tradisional (Anti-pattern) | Solusi Enterprise Architecture | Dampak Produksi |
| :--- | :--- | :--- | :--- |
| **Multi-Tenancy** | Penggunaan `default_scope where(tenant_id: ...)` rawan bypass via `unscoped`, `joins`, raw SQL, dan subqueries. | Kombinasi `ActiveSupport::CurrentAttributes` + PostgreSQL Native Row-Level Security (RLS). | Kebocoran data antar-tenant secara komputasional mustahil di level DB. |
| **Tenant Context** | Menyimpan tenant context di `Thread.current` tanpa automatic cleanup, memicu kebocoran konteks antar-request di Puma. | Integrasi `CurrentAttributes` dengan `Rails.application.executor` & Puma thread-reaping hooks. | Nol *cross-tenant data contamination* pada server berbeban tinggi. |
| **Authorization** | Pundit policy monolitis dengan query database berulang di setiap policy check (*N+1 authorization query*). | `Action Policy` dengan *pre-compiled memoization*, authorization caching, dan ABAC evaluation engine. | Reduksi latensi otorisasi hingga < 0.5ms tanpa database round-trip. |
| **Authentication** | Token JWT stateless murni tanpa mekanisme *instant revocation* saat kredensial terkompromi. | Hybrid architecture: JTI (JWT ID) checking via Redis O(1) fallback dengan fallback ke Postgres database sessions. | Kemampuan *real-time revocation* tanpa mengorbankan skalabilitas *stateless validation*. |

---

### 5. How: Alur Kerja Komprehensif Arsitektur Keamanan

Alur penanganan HTTP Request enterprise dari edge hingga database layer:

```
[ Client Request ]
       │ (Authorization: Bearer <JWT> atau Session Cookie)
       │ (X-Tenant-Domain: enterprise-corp)
       ▼
[ Cloudflare / Load Balancer ] -> Verifikasi mTLS, Strip header rentan
       ▼
[ Rack Stack: Warden::Manager ]
       │
       ├──> 1. TenantResolution Middleware
       │       - Validasi keberadaan tenant via cached lookup
       │       - Set Fiber storage: Current.tenant = resolved_tenant
       │
       ├──> 2. Warden Custom Strategy Execution
       │       - Ekstraksi token/cookie
       │       - Verifikasi cryptographic signature (RS256)
       │       - Validasi claims (nbf, exp, iss, aud, jti)
       │       - Set Fiber storage: Current.user = authenticated_user
       │
       ├──> 3. Action Policy Pre-check
       │       - ABAC Evaluation via user attributes & tenant flags
       │
       ▼
[ ActiveRecord Transaction Hook ]
       │
       ├──> Eksekusi: SET LOCAL app.current_tenant_id = 'tenant.id'
       │
       ▼
[ SQL Query Execution ] -> Evaluasi RLS Kernel Database -> Return Data
       │
       ▼
[ Controller Action / Response Generation ]
       │
       ▼
[ Rails Executor / Middleware Out ]
       │
       └──> Teardown: Current.reset (Flush memory thread/fiber)
```

---

### 6. Analogi & Diagram ASCII

#### Analogi: Sistem Penginapan Brankas Fisik
Bayangkan sebuah bank (*Sistem Rails*) yang menyewakan ruangan brankas kepada beberapa korporasi (*Tenants*):
*   **Model `default_scope` (Buruk)**: Seperti satpam bank (*Aplikasi*) yang diberi instruksi: *"Tolong ingat ya, jangan biarkan PT Alpha membuka kotak PT Beta"*. Jika satpam lengah (*developer lupa filter atau memakai `unscoped`*), siapa pun bisa membuka kotak korporasi lain.
*   **Model PostgreSQL RLS (Enterprise)**: Mengganti kunci brankas dengan pemindai sidik jari mekanis (*Database Engine*). Meskipun satpam bank tertidur lelap (*bug di Rails*), kotak brankas milik PT Beta secara fisik dan mekanis menolak kunci mekanis PT Alpha.

```
       +-------------------------------------------------------------+
       |                  POSTGRESQL STORAGE (HEAP)                  |
       |                                                             |
       |  Row 1: [Tenant: Alpha] Balance: $1,000,000                 |
       |  Row 2: [Tenant: Beta ] Balance: $500                       |
       |  Row 3: [Tenant: Alpha] Balance: $250,000                   |
       +-------------------------------------------------------------+
                                      ▲
                                      │ Filter oleh RLS Engine
                                      │ (app.current_tenant_id = 'Alpha')
       +-------------------------------------------------------------+
       |                  POSTGRES QUERY ENGINE                      |
       |  Query Masuk: "SELECT * FROM ledgers;"                      |
       |  Query Rewrite: "SELECT * FROM ledgers WHERE tenant_id =    |
       |                  current_setting('app.current_tenant_id');" |
       +-------------------------------------------------------------+
                                      ▲
                                      │ Transaksi Aktif
       +-------------------------------------------------------------+
       |                RAILS / PUMA WORKER THREAD                   |
       |  Current.tenant = Tenant.find_by(subdomain: 'alpha')        |
       |  Connection.execute("SET LOCAL app.current_tenant_id = ...")|
       +-------------------------------------------------------------+
```

---

### 7. Implementasi Kode Produksi

#### 7.1. Database Migration: Aktivasi RLS Terisolasi Penuh

```ruby
# db/migrate/20240101000001_setup_enterprise_rls.rb
# Bekukan string literal untuk optimasi alokasi memori
# frozen_string_literal: true

class SetupEnterpriseRls < ActiveRecord::Migration[7.1]
  def up
    # 1. Pastikan ekstensi UUID dan pgcrypto tersedia
    enable_extension 'pgcrypto' unless extension_enabled?('pgcrypto')

    # 2. Buat tabel Tenant
    create_table :tenants, id: :uuid, default: -> { 'gen_random_uuid()' } do |t|
      t.string :name, null: false
      t.string :subdomain, null: false, index: { unique: true }
      t.string :status, null: false, default: 'active'
      t.timestamps
    end

    # 3. Buat tabel Transaksi Finansial (Data Sensitif)
    create_table :ledgers, id: :uuid, default: -> { 'gen_random_uuid()' } do |t|
      t.references :tenant, type: :uuid, null: false, foreign_key: { on_delete: :restrict }
      t.decimal :amount, precision: 18, scale: 4, null: false
      t.string :currency, limit: 3, null: false
      t.string :description, null: false
      t.timestamps
    end

    add_index :ledgers, [:tenant_id, :created_at]

    # 4. Aktifkan RLS pada tabel ledgers
    execute <<-SQL
      ALTER TABLE ledgers ENABLE ROW LEVEL SECURITY;
      ALTER TABLE ledgers FORCE ROW LEVEL SECURITY;

      -- Hapus policy lama jika ada untuk idempotensi
      DROP POLICY IF EXISTS tenant_isolation_policy ON ledgers;

      -- Buat Policy: Hanya izinkan baris yang tenant_id-nya sama dengan session variable
      CREATE POLICY tenant_isolation_policy ON ledgers
        AS RESTRICTIVE
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    SQL
  end

  def down
    execute <<-SQL
      DROP POLICY IF EXISTS tenant_isolation_policy ON ledgers;
      ALTER TABLE ledgers NO FORCE ROW LEVEL SECURITY;
      ALTER TABLE ledgers DISABLE ROW LEVEL SECURITY;
    SQL

    drop_table :ledgers
    drop_table :tenants
  end
end
```

#### 7.2. Application Context: `CurrentAttributes` & Database Connection Switching

```ruby
# app/models/current.rb
# frozen_string_literal: true

class Current < ActiveSupport::CurrentAttributes
  attribute :tenant, :user, :request_id

  # Validasi integritas context tenant sebelum operasi mutasi dilakukan
  resets do
    # Eksekusi garbage collection internal untuk reference objects
    self.tenant = nil
    self.user = nil
    self.request_id = nil
  end

  def tenant=(tenant_instance)
    super
    # Bind langsung ke thread PostgreSQL jika koneksi sudah aktif
    if tenant_instance.present? && ActiveRecord::Base.connection_pool.active_connection?
      ActiveRecord::Base.connection.execute(
        ActiveRecord::Base.sanitize_sql(["SET LOCAL app.current_tenant_id = %Q", tenant_instance.id])
      )
    end
  end
end
```

#### 7.3. Rack Middleware: Resolusi Tenant dan Proteksi Injeksi Konteks

```ruby
# app/middleware/tenant_security_enforcer.rb
# frozen_string_literal: true

class TenantSecurityEnforcer
  TENANT_SUBDOMAIN_REGEX = /\A[a-z0-9]+(-[a-z0-9]+)*\z/i.freeze

  def initialize(app)
    @app = app
  end

  def call(env)
    request = Rack::Request.new(env)
    host = request.host

    # 1. Ekstraksi subdomain dengan sanitasi ketat
    subdomain = extract_subdomain(host)

    # 2. Return HTTP 400 Bad Request jika format subdomain tidak valid
    if subdomain.present? && !subdomain.match?(TENANT_SUBDOMAIN_REGEX)
      return [400, { "Content-Type" => "application/json" }, [{ error: "Invalid Host Header" }.to_json]]
    end

    # 3. Resolusi Tenant dengan database-level protection
    tenant = resolve_tenant(subdomain)

    if tenant.nil? && requires_tenant?(request.path)
      return [404, { "Content-Type" => "application/json" }, [{ error: "Tenant Not Found or Inactive" }.to_json]]
    end

    # 4. Isolasi transaksi menggunakan ActiveRecord Connection Wrap
    ActiveRecord::Base.connection_pool.with_connection do |conn|
      Current.set(tenant: tenant, request_id: request.env["action_dispatch.request_id"]) do
        conn.transaction do
          if tenant.present?
            # Enforce local context ke connection pool worker saat ini
            conn.execute(ActiveRecord::Base.sanitize_sql(["SET LOCAL app.current_tenant_id = %Q", tenant.id]))
          end
          
          @app.call(env)
        end
      end
    end
  ensure
    # Clean reset demi menjamin zero-leakage pada level Puma worker
    Current.reset
  end

  private

  def extract_subdomain(host)
    # Asumsi domain standar: tenant-name.domain.com
    parts = host.split(".")
    parts.size >= 3 ? parts.first.downcase : nil
  end

  def resolve_tenant(subdomain)
    return nil if subdomain.blank?

    # Cache hit O(1) via Rails cache layer
    Rails.cache.fetch("tenants:#{subdomain}", expires_in: 15.minutes) do
      Tenant.find_by(subdomain: subdomain, status: "active")
    end
  end

  def requires_tenant?(path)
    !path.start_with?("/up", "/healthz", "/sidekiq", "/assets")
  end
end
```

#### 7.4. Enterprise Authorization: Policy Engine Menggunakan `Action Policy`

```ruby
# app/policies/ledger_policy.rb
# frozen_string_literal: true

class LedgerPolicy < ActionPolicy::Base
  authorize :user, allow_nil: false
  
  # Cache rule evaluation berdasarkan ID user, ledger, dan updated_at
  cache :show?, :update?, :destroy?

  # ABAC Rule: Hanya role finance & super_admin yang boleh membaca transaksi
  def index?
    user.role_in?(%w[finance auditor super_admin]) &&
      user.tenant_id == record_tenant_id
  end

  def show?
    user_tenant_matches? && (user.finance? || user.auditor?)
  end

  def create?
    user_tenant_matches? && user.finance? && !record.frozen_ledger?
  end

  def update?
    # Immutable Ledger: Transaksi yang sudah terverifikasi tidak boleh diubah
    false
  end

  def destroy?
    # Strict Compliance: Ledger tidak boleh di-hard-delete
    false
  end

  # Scope otomatis untuk sanitasi query
  relation_scope do |relation|
    next relation.none unless user.present?
    
    # RLS sudah melindungi di level DB, tapi defense-in-depth memastikan 
    # query filtering optimal pada index scanning
    relation.where(tenant_id: user.tenant_id)
  end

  private

  def user_tenant_matches?
    Current.tenant.present? && user.tenant_id == Current.tenant.id && record.tenant_id == Current.tenant.id
  end

  def record_tenant_id
    Current.tenant&.id
  end
end
```

---

### 8. Real-World Case Study: Skalabilitas FinTech Payment Ledger (PT Transaksi Aman Nusantara)

#### 8.1. Konteks dan Permasalahan
PT Transaksi Aman Nusantara adalah penyedia Payment Gateway B2B multi-tenant di Indonesia yang melayani 1.200 enterprise merchant. Setiap detik, sistem memproses rata-rata 3.500 transaksi financial ledger. 
*   **Insiden**: Saat audit internal Q3, ditemukan bahwa bug pada endpoint pelaporan analitik bulanan menggunakan method `.unscoped` untuk menghitung aggregate metrik performa. Hal ini secara tidak sengaja mengekspos ringkasan perputaran kas milik Merchant A ke dashboard Merchant B.
*   **Kebutuhan Audit**: Otoritas Jasa Keuangan (OJK) dan auditor PCI-DSS Level 1 menuntut jaminan matematis bahwa kebocoran data tidak akan pernah terulang meskipun terjadi *human-error* di kode controller/model.

#### 8.2. Desain Solusi Rekayasa
1.  **Migrasi Total ke PostgreSQL Row-Level Security (RLS)**: Menghapus ketergantungan pada gem `acts_as_tenant` lama yang menggunakan `default_scope`.
2.  **Zero-Trust Connection Hook**: Koneksi Rails ke Postgres dialihkan melalui custom Proxy yang menyematkan `SET LOCAL app.current_tenant_id` secara wajib. Query tanpa tenant context yang menyentuh tabel finansial langsung digugurkan (*terminated with exception*) oleh engine PostgreSQL.
3.  **Audit Event Streaming Terenkripsi**: Menggunakan PostgreSQL Transaction Append-Only Log yang dipancarkan secara asinkron ke Apache Kafka via Debezium CDC (*Change Data Capture*), menjamin setiap akses read/write tercatat permanen.

#### 8.3. Hasil Evaluasi & Tolok Ukur

```
+------------------------------------+--------------------------+--------------------------+
| Parameter Metrik                   | Implementasi Lama (App)  | RLS + Strict Context     |
+------------------------------------+--------------------------+--------------------------+
| Isolasi Data Cross-Tenant          | Logikal (Application-Lvl)| Kriptografis / Kernel DB |
| Rata-rata Latensi Query (p99)      | 4.2 ms                   | 4.6 ms (+0.4ms RLS cost) |
| Latensi Otorisasi (Pundit -> AP)   | 1.8 ms                   | 0.2 ms (Action Policy)   |
| Throughput Maksimal (RPS)          | 3,800 RPS                | 3,750 RPS (-1.3%)        |
| Insiden Data Cross-Leakage (12 Bln)| 3 Kasus Minor            | 0 Kasus (Definitive Zero)|
| Waktu Lolos Audit PCI-DSS          | 3 Minggu                 | 2 Hari                   |
+------------------------------------+--------------------------+--------------------------+
```

---

### 9. Trade-offs: Arsitektur Multi-Tenancy

```
                              ANALISIS KEKUATAN & EFISIENSI
               Isolasi Data (Security)
                     ▲
                     │                                [ Database-per-Tenant ]
                     │                                (Tinggi Biaya, Kompleksitas Ops)
                     │
                     │                 [ PostgreSQL RLS ]
                     │                 (Sweet spot Enterprise SaaS)
                     │
                     │  [ Schema-based (Apartment) ]
                     │  (Migration slow, DDL Lock issues)
                     │
                     │ [ Shared DB + Default Scope ]
                     │ (Rentan Bug, Performa Tinggi, Biaya Rendah)
                     └──────────────────────────────────────────────► Efisiensi Resource &
                                                                      Skalabilitas Biaya
```

| Parameter | Row-Level Security (RLS) | Separate Schema (Search Path) | Database per Tenant |
| :--- | :--- | :--- | :--- |
| **Derajat Isolasi** | Sangat Tinggi (Kernel DB level) | Menengah-Tinggi (Namespace level) | Mutlak (Fisik/Instance DB level) |
| **Overhead Koneksi DB** | Sangat Rendah (Menggunakan 1 pool bersama) | Menengah (Search path switching overhead) | Sangat Tinggi (Pool per DB, boros resource) |
| **Kecepatan Migrasi DDL** | Instan (Migrasi dijalankan 1 kali) | Lambat ($N \times$ jumlah tenant schemas) | Sangat Lambat ($N \times$ database connections) |
| **Max Capacity Limit** | Terbatas pada ukuran tabel tunggal (Partisi diperlukan jika > 100M rows) | Terbatas limit namespace Postgres (~10,000 schemas max sebelum catalog lag) | Tidak terbatas (Horizontal sharding murni) |
| **Kompleksitas Backup/Restore**| Rumit jika ingin restore data 1 tenant saja | Cukup Mudah (`pg_dump -n schema`) | Sangat Mudah (Restore full DB instance) |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Common Mistakes
1.  **Thread Pool Context Leakage pada Sidekiq Worker**: Menggunakan `Current.tenant` di dalam worker tanpa membersihkannya di block `ensure`. Hal ini menyebabkan job tenant B yang diproses oleh worker thread yang sama dapat mengeksekusi data milik tenant A.
2.  **Penggunaan `ActiveRecord::Base.connection.execute` Tanpa `SET LOCAL`**: Menggunakan `SET app.current_tenant_id = '...'` (tanpa kata kunci `LOCAL`). Ini akan mengubah variabel sesi secara permanen untuk koneksi tersebut. Ketika koneksi dikembalikan ke `ConnectionPool`, request berikutnya yang meminjam koneksi tersebut akan mewarisi context tenant lama!
3.  **Arel SQL Injection pada Dynamic Ordering/Filtering**: Menulis query dinamis mentah seperti `Ledger.order(params[:sort_by])` yang memungkinkan penyerang menyuntikkan fungsi SQL `CASE/WHEN` untuk membocorkan bit data (*blind side-channel extraction*).

#### 10.2. Diagnosa & Troubleshooting Kasus Produksi
*   **Gejala**: Error PostgreSQL `invalid_parameter_value: unrecognized configuration parameter "app.current_tenant_id"` saat boot atau migrasi.
    *   **Penyebab**: PostgreSQL belum mendefinisikan custom variable class.
    *   **Solusi**: Tambahkan fallback `true` pada fungsi `current_setting('app.current_tenant_id', true)` di policy SQL, atau deklarasikan di `postgresql.conf`: `custom_variable_classes = 'app'`.
*   **Gejala**: Transaksi background job tiba-tiba kosong (0 rows returned).
    *   **Penyebab**: Worker mengeksekusi query sebelum variabel session RLS diinisialisasi, sehingga RLS mengevaluasi policy menjadi `FALSE` dan menyembunyikan semua data.
    *   **Solusi**: Terapkan Sidekiq Server Middleware yang memvalidasi keberadaan `tenant_id` pada payload arguments sebelum worker dijalankan:

```ruby
# app/workers/middleware/sidekiq_tenant_evaluator.rb
# frozen_string_literal: true

class SidekiqTenantEvaluator
  def call(_worker, job, _queue)
    tenant_id = job["args"].first.is_a?(Hash) ? job["args"].first["tenant_id"] : nil

    if tenant_id.present?
      tenant = Tenant.find(tenant_id)
      ActiveRecord::Base.connection_pool.with_connection do |conn|
        Current.set(tenant: tenant) do
          conn.transaction do
            conn.execute(ActiveRecord::Base.sanitize_sql(["SET LOCAL app.current_tenant_id = %Q", tenant.id]))
            yield
          end
        end
      end
    else
      yield
    end
  ensure
    Current.reset
  end
end
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Database RLS Enforced**: Pastikan klausul `FORCE ROW LEVEL SECURITY` terpasang pada semua tabel yang memiliki kolom `tenant_id` agar user tabel owner (termasuk user default Rails) tetap wajib melewati policy.
- [ ] **Transaction-Scoped Variables**: Hanya gunakan `SET LOCAL` di dalam blok transaksi `ActiveRecord::Base.transaction do ... end` untuk mencegah pencemaran connection pool.
- [ ] **Action Policy Caching**: Aktifkan fragment caching pada policy checks yang mahal secara komputasi via `cache: :rule_name`.
- [ ] **Static Code Analysis**: Integrasikan `brakeman` dan `bundler-audit` ke pipeline CI/CD dengan status strict (`-z` flag, fail on any warning).
- [ ] **Timing-Safe String Comparisons**: Selalu gunakan `Rack::Utils.secure_compare(a, b)` atau `ActiveSupport::SecurityUtils.secure_compare(a, b)` saat memverifikasi API keys, password hashes, atau secret tokens untuk mengeliminasi serangan timing side-channel.
- [ ] **Hardened CSP Header Configuration**: Definisikan Content Security Policy modern via initializer Rails:

```ruby
# config/initializers/content_security_policy.rb
# frozen_string_literal: true

Rails.application.configure do
  config.content_security_policy do |policy|
    policy.default_src :none
    policy.font_src    :self, :https, :data
    policy.img_src     :self, :https, :data
    policy.object_src  :none
    policy.script_src  :self
    policy.style_src   :self, :https
    policy.connect_src :self, "https://api.yourdomain.com"
    policy.frame_ancestors :none
    policy.base_uri    :none
    policy.form_action :self
  end

  # Generate nonce otomatis untuk script-src inline jika mutlak diperlukan
  config.content_security_policy_nonce_generator = ->(request) { request.session.id.to_s }
  config.content_security_policy_nonce_directives = %w[script-src]
end
```

---

### 12. Hands-on Practice

Struktur direktori praktikum yang akan kita bangun di `hands-on/m02/`:

```
hands-on/m02/
├── Dockerfile
├── docker-compose.yml
├── app/
│   ├── models/
│   │   ├── current.rb
│   │   ├── tenant.rb
│   │   └── ledger.rb
│   ├── middleware/
│   │   └── tenant_resolver.rb
│   └── policies/
│       └── ledger_policy.rb
├── config/
│   └── application.rb
├── db/
│   ├── migrate/
│   │   └── 20240101000001_initialize_rls_architecture.rb
│   └── seeds.rb
└── spec/
    └── rls_isolation_spec.rb
```

#### Langkah 1: Siapkan Environment Database via `docker-compose.yml`

```yaml
# hands-on/m02/docker-compose.yml
version: '3.8'

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: enterprise_rails
      POSTGRES_PASSWORD: SecretPassword123!
      POSTGRES_DB: enterprise_production
    ports:
      - "5432:5432"
    command: >
      postgres 
      -c shared_preload_libraries=pg_stat_statements
      -c log_statement=all
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

Jalankan container:
```bash
docker-compose up -d
```

#### Langkah 2: Model Implementation (`app/models/ledger.rb`)

```ruby
# hands-on/m02/app/models/ledger.rb
# frozen_string_literal: true

class Ledger < ApplicationRecord
  belongs_to :tenant

  validates :amount, presence: true, numericality: { other_than: 0 }
  validates :currency, presence: true, length: { is: 3 }
  validates :description, presence: true

  # Hook validasi ketat: Cegah penetapan tenant yang tidak sesuai context aktif
  before_validation :assign_tenant_context, on: :create

  private

  def assign_tenant_context
    if Current.tenant.present?
      self.tenant_id = Current.tenant.id
    elsif tenant_id.blank?
      raise SecurityError, "Cannot persist Ledger without an active Tenant context!"
    end
  end
end
```

#### Langkah 3: RSpec Verification Suite (`spec/rls_isolation_spec.rb`)

```ruby
# hands-on/m02/spec/rls_isolation_spec.rb
# frozen_string_literal: true

require "rails_helper"

RSpec.describe "Multi-Tenancy Row-Level Security Isolation", type: :model do
  let!(:tenant_alpha) { Tenant.create!(name: "Alpha Corp", subdomain: "alpha") }
  let!(:tenant_beta)  { Tenant.create!(name: "Beta Corp", subdomain: "beta") }

  it "secures data at PostgreSQL level preventing leaks even with unscoped" do
    # 1. Insert data atas nama Tenant Alpha
    ActiveRecord::Base.connection_pool.with_connection do |conn|
      conn.transaction do
        conn.execute("SET LOCAL app.current_tenant_id = '#{tenant_alpha.id}'")
        Current.set(tenant: tenant_alpha) do
          Ledger.create!(amount: 10_000.00, currency: "USD", description: "Alpha Secret Revenue")
        end
      end
    end

    # 2. Insert data atas nama Tenant Beta
    ActiveRecord::Base.connection_pool.with_connection do |conn|
      conn.transaction do
        conn.execute("SET LOCAL app.current_tenant_id = '#{tenant_beta.id}'")
        Current.set(tenant: tenant_beta) do
          Ledger.create!(amount: 50.00, currency: "USD", description: "Beta Public Sale")
        end
      end
    end

    # 3. VERIFIKASI: Tenant Alpha membaca database
    ActiveRecord::Base.connection_pool.with_connection do |conn|
      conn.transaction do
        conn.execute("SET LOCAL app.current_tenant_id = '#{tenant_alpha.id}'")
        Current.set(tenant: tenant_alpha) do
          # Cobalah teknik hacking paling umum: memanggil .unscoped
          records = Ledger.unscoped.all
          expect(records.count).to eq(1)
          expect(records.first.description).to eq("Alpha Secret Revenue")
        end
      end
    end

    # 4. VERIFIKASI: Eksekusi Raw SQL Bypass
    ActiveRecord::Base.connection_pool.with_connection do |conn|
      conn.transaction do
        conn.execute("SET LOCAL app.current_tenant_id = '#{tenant_beta.id}'")
        Current.set(tenant: tenant_beta) do
          raw_results = ActiveRecord::Base.connection.execute("SELECT * FROM ledgers;")
          expect(raw_results.ntuples).to eq(1)
          expect(raw_results.first["description"]).to eq("Beta Public Sale")
        end
      end
    end
  end
end
```

Jalankan test suite:
```bash
bundle exec rspec spec/rls_isolation_spec.rb
```

---

### 13. Exercise

#### Level Easy
Buatlah custom ActiveSupport validation validator bernama `SafeSqlParametersValidator` yang memeriksa string input parameter dan menolak pola format SQL injection dasar (seperti kata kunci `--`, `;`, `UNION SELECT`) sebelum parameter tersebut dikirim ke layer ActiveRecord.

#### Level Medium
Implementasikan Rack Middleware `SecureTenantTokenAuth` yang mengekstrak asymmetric Ed25519-signed JWT dari header `Authorization: Bearer <token>`, memvalidasi signature menggunakan public key yang terikat pada subdomain tenant, dan meng-inject context tenant beserta user ke `Current`.

#### Level Hard
Rancang modul migrasi DDL dinamis zero-downtime yang mampu menambahkan index secara aman (`algorithm: :concurrently`) pada tabel 100 juta record yang terdistribusi menggunakan RLS, dengan menangani *Postgres lock timeout* dan fallback rollback otomatis jika terjadi degradasi latensi aplikasi.

---

### 14. Challenge

**Skenario**: Anda adalah Chief Architect pada unicorn edutech/fintech multinasional. Sistem menggunakan basis data Rails multitenant RLS. Terdapat kebutuhan analitik lintas-tenant (*Cross-Tenant Aggregation Query*) untuk tim Finance Global di internal perusahan yang membutuhkan aggregate query (SUM, AVG) dari tabel `ledgers` untuk seluruh tenant, namun dengan restriksi:
1.  Tim Finance **dilarang keras** melihat data individual (Penerapan *K-Anonymity* & *Differential Privacy*).
2.  Eksekusi query tidak boleh mematikan RLS secara global pada level database (`NO ROW LEVEL SECURITY` dilarang).
3.  Query tidak boleh menyebabkan memory exhaust pada Ruby (dilarang *in-memory array processing*).

**Tantangan**: 
Rancang dan tulis arsitektur arsitektural Rails + PostgreSQL (meliputi stored procedure/views terproteksi, dynamic connection role routing, dan service object di Rails) yang secara aman mengeksekusi aggregasi data tanpa membocorkan `tenant_id` mentah, menjaga isolasi RLS tetap aktif 100% untuk web request biasa!

---

### 15. Quiz Evaluasi Pemahaman

#### 15.1. Pertanyaan Tingkat Dasar (5 Soal)

1. **Mengapa penggunaan `default_scope` untuk isolasi tenant dianggap sebagai anti-pattern kritis di Rails?**
   * *Jawaban*: `default_scope` dapat secara tidak sengaja dibatalkan oleh metode seperti `unscoped`, `unscope`, `reorder`, atau query asosiasi tertentu. Jika seorang engineer menggunakannya dalam controller atau service, seluruh data tenant lain akan terekspos tanpa memicu error.

2. **Apa perbedaan antara `SET app.current_tenant_id` dan `SET LOCAL app.current_tenant_id` pada PostgreSQL?**
   * *Jawaban*: `SET` menerapkan nilai konfigurasi ke seluruh masa hidup koneksi TCP saat ini, yang berbahaya pada environment connection pooler (seperti Puma / PgBouncer) karena variabel terbawa ke request berikutnya. `SET LOCAL` hanya mengikat nilai pada siklus transaksi aktif saat ini (`BEGIN ... COMMIT`) dan otomatis hilang setelahnya.

3. **Mengapa `FORCE ROW LEVEL SECURITY` wajib diaktifkan pada PostgreSQL, bukan hanya `ENABLE ROW LEVEL SECURITY`?**
   * *Jawaban*: Tanpa klausul `FORCE`, table owner (pemilik tabel) atau superuser PostgreSQL akan melewati (*bypass*) seluruh pengecekan RLS secara default. Rails biasanya terhubung ke database sebagai table owner, sehingga `FORCE` wajib digunakan agar user aplikasi tetap tunduk pada aturan RLS.

4. **Bagaimana cara kerja pencegahan Timing Attacks pada verifikasi otentikasi token di Rails?**
   * *Jawaban*: String comparison biasa (`==`) berhenti memeriksa (*early return*) saat menemukan karakter pertama yang tidak cocok, sehingga waktu eksekusi bervariasi bergantung pada kecocokan karakter. Rails menggunakan `Rack::Utils.secure_compare` yang memeriksa seluruh karakter dengan kompleksitas konstan $\mathcal{O}(N)$ independen dari letak ketidakcocokan.

5. **Apa risiko menggunakan `Thread.current` secara langsung tanpa mekanisme reset pada web server Puma?**
   * *Jawaban*: Puma menggunakan thread pool di mana worker thread tidak dihancurkan setelah request selesai, melainkan digunakan kembali (*recycled*). Variabel yang tersimpan di `Thread.current` akan tetap berada di memori dan bocor ke request pengguna berikutnya.

#### 15.2. Pertanyaan Tingkat Lanjut (5 Soal)

6. **Bagaimana PostgreSQL memproses RLS di dalam Execution Engine-nya secara mendalam?**
   * *Jawaban*: Sebelum optimasi query, *Query Rewriter* PostgreSQL mengambil AST (Abstract Syntax Tree) query dan menggabungkan kualifikasi (*quals*) dari definisi policy RLS menggunakan operator logika `AND`. Hasil penulisan ulang ini kemudian diserahkan ke *Query Planner*, memastikan indeks scanning tetap memfilter baris sebelum di-fetch ke shared memory buffer.

7. **Kapan `ActiveSupport::CurrentAttributes` berpotensi bocor saat menggunakan background processor seperti Sidekiq?**
   * *Jawaban*: Ketika Sidekiq mengeksekusi multiple jobs pada worker thread yang sama dan salah satu job mengalami unhandled exception sebelum mencapai callback cleanup, atau jika worker job memunculkan child thread (`Thread.new`) yang tidak memiliki lifecycle hook dari `Rails.application.executor`.

8. **Apa trade-off keamanan vs performa dari penggunaan Token Revocation List berbasis Redis O(1) Bloom Filter dibandingkan Database Table Lookup?**
   * *Jawaban*: Bloom filter menawarkan latency sub-millisecond dan pemakaian RAM sangat kecil untuk memvalidasi jutaan token, namun memiliki potensi *false positive* (token valid bisa terdeteksi revoked secara salah, membutuhkan fallback secondary check). Database table lookup bebas dari *false positive*, tetapi membebani I/O disk database pada setiap request.

9. **Jelaskan peran method `relation_scope` pada Action Policy dibandingkan Pundit Scopes.**
   * *Jawaban*: `relation_scope` Action Policy mengintegrasikan compile-time block parsing dan mendukung composability native ActiveRecord. Ini memungkinkan policy scope di-chaining secara deklaratif dan menghindari instansiasi class scope terpisah, memotong footprint alokasi objek Ruby hingga 60%.

10. **Bagaimana cara mencegah Mass Assignment Vulnerability saat menggunakan `params.permit!` pada nested attributes multi-tenant?**
    * *Jawaban*: Hindari mutlak `params.permit!`. Pada arsitektur nested multi-tenant, `tenant_id` harus di-strip dari permitted parameters dan disuntikkan secara programatik melalui server-side trusted state (`Current.tenant.id`) guna mengeliminasi eksploitasi parameter tampering.

#### 15.3. Skenario Kasus Produksi (3 Soal)

11. **Skenario Kasus 1: Memory Spike Akibat Apartment Gem**
    * *Masalah*: Sebuah aplikasi Rails enterprise menggunakan gem *Apartment* dengan 5.000 tenants (5.000 PostgreSQL schemas). Setelah update minor, Puma worker mengalami Out-Of-Memory (OOM) terus-menerus.
    * *Analisa*: PostgreSQL driver meng-cache metadata internal tabel untuk setiap search path schema yang dibuka ke memori Ruby process. 5.000 schemas $\times$ 100 tabel $\approx$ 500.000 skema tabel di-cache di heap memory Puma.
    * *Solusi*: Migrasikan arsitektur dari *Schema-per-tenant* ke *Shared-Table with Row-Level Security (RLS)*, atau pisahkan tenant ke dalam connection-based sharding cluster (`ActiveRecord::Sharding`) agar 1 instance Ruby hanya menangani subset schema terbatas.

12. **Skenario Kasus 2: Deadlock pada SET LOCAL Transaction**
    * *Masalah*: Sistem sering mengalami `ActiveRecord::Deadlocked` pada endpoint checkout tinggi ketika mengeksekusi `SET LOCAL app.current_tenant_id` bersamaan dengan `SELECT FOR UPDATE` pada tabel inventori.
    * *Analisa*: Perintah `SET LOCAL` sendiri tidak menyebabkan table lock, namun query yang dijalankan sesudahnya memicu eskalasi lock. Deadlock terjadi jika urutan akuisisi row-lock oleh transaksi berbeda bertabrakan di dalam PostgreSQL.
    * *Solusi*: Pastikan `SET LOCAL` dipanggil sebelum query apapun dijalankan dalam transaksi. Terapkan query ordering deterministik (misalnya `order(:id)`) pada setiap operasi `SELECT ... FOR UPDATE` agar semua worker thread mengunci baris inventori dalam urutan yang identik.

13. **Skenario Kasus 3: Side-Channel Timing Leak pada Tenant Resolver**
    * *Masalah*: Penyerang dapat mendata subdomain organisasi perusahaan enterprise yang valid pada sistem Anda dengan mengukur respons time perbedaan antara subdomain yang ada vs tidak ada.
    * *Analisa*: Resolver langsung mengembalikan HTTP 404 ketika database record tidak ditemukan, sementara subdomain valid memerlukan waktu ~50ms untuk verifikasi bcrypt/token. Selisih latensi ini membocorkan eksistensi data (*user/tenant enumeration via timing attack*).
    * *Solusi*: Normalisasi latency response. Jika tenant tidak ditemukan, jalankan operasi hashing dummy (*dummy work*) yang memakan waktu setara (misalnya `BCrypt::Engine.hash_secret('dummy', 12)`) sebelum mengembalikan HTTP 404, atau gunakan fixed-time padding middleware.

---

### 16. Summary

1.  **Defense-in-Depth Multi-Tenancy**: Mengandalkan level aplikasi (seperti `default_scope`) untuk keamanan data tenant merupakan kesalahan fatal. Kombinasi **PostgreSQL Row-Level Security (RLS)** dan **Rails Connection Transaction Hooks** memindahkan batas keamanan langsung ke *storage engine*, menjamin isolasi mutlak.
2.  **Konteks Tanpa Celah**: Penggunaan `ActiveSupport::CurrentAttributes` wajib dibersihkan secara atomik melalui `ActionDispatch::Executor` dan middleware wrappers untuk menghindari kontaminasi memori antar-thread Puma.
3.  **Modern Policy Evaluation**: Enterprise rails beralih dari policy konvensional ke arsitektur **Action Policy ABAC** dengan pre-compiled rules dan caching terintegrasi, menghasilkan otorisasi berkecepatan tinggi dengan footprint memori minimal.
4.  **Integritas Operasional**: Pengamanan enterprise sejati bukan hanya sekadar menghentikan penyerang luar, melainkan merancang sistem yang secara matematis dan arsitektural mencegah kesalahan manusia (*developer error*) merusak integritas data tenant di lingkungan produksi.