# BAB 02: Quiz, Challenge, & Knowledge Check
**Routing Lanjutan & Controller Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Routing Scoping Semantics**  
   Jelaskan perbedaan mendasar secara arsitektural dan implikasi *URL generation* serta *controller dispatching* antara deklarasi routing menggunakan `namespace :admin`, `scope module: :admin`, dan `scope path: :admin`! Berikan contoh pemetaan URI dan *controller target* untuk masing-masing pendekatan.

2. **The Anti-Pattern of Deep Nesting vs. Shallow Routes**  
   Rails Guide secara eksplisit menyarankan pembatasan *nested resources* maksimal 1 level (`shallow: true`). Mengapa *deep nesting* (misal: `/teams/:team_id/projects/:project_id/tasks/:task_id/comments`) dianggap sebagai *code smell* arsitektural? Jelaskan dampaknya terhadap perancangan RESTful controller, kompleksitas parameter parsing, dan query SQL!

3. **Strong Parameters Execution Context & Security Boundary**  
   Bagaimana cara kerja internal `ActionController::Parameters` dalam membedakan tipe data primitif (*scalar*) dengan struktur data bersarang (*nested arrays/hashes*)? Mengapa eksekusi `params.permit!` pada *nested association attributes* (`accepts_nested_attributes_for`) berpotensi membuka kerentanan *mass-assignment* fatal jika tidak dikonfigurasi secara eksplisit?

4. **ActionController Lifecycle & Rendering Pipeline**  
   Jelaskan urutan deterministik eksekusi request pada controller mulai dari penanganan middleware Rack, eksekusi callback (`before_action`, `around_action`), pemanggilan method aksi, hingga proses rendering template. Mengapa pemanggilan `redirect_to` diikuti oleh baris eksekusi kode lain tanpa instruksi `return` dapat memicu `ActionController::DoubleRenderError`?

5. **`ActionController::Base` vs. `ActionController::API` Architectural Trade-Off**  
   Middleware dan modul fungsionalitas apa saja yang dipangkas saat sebuah controller mewarisi `ActionController::API` alih-alih `ActionController::Base`? Apa konsekuensi teknis pemangkasan ini terhadap fitur *session state*, *cookies*, *CSRF protection*, dan *content negotiation*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Journey Router Engine & Route Dispatch Mechanics**  
   Di balik layar, Rails memanfaatkan pustaka `Journey` untuk mengompilasi routing table ke dalam bentuk graf DFA (*Deterministic Finite Automaton*). Bagaimana cara Rails menyelesaikan rute ambigu ketika ada dua rute yang cocok secara pola path (misalnya `GET /posts/:id` vs `GET /posts/analytics`)? Bagaimana urutan penulisan file `routes.rb` memengaruhi resolusi DFA ini?

2. **Thread-Safety Issues with Callback Invocations and State Leaks**  
   Perhatikan pola penanganan multi-tenancy berikut:
   ```ruby
   class ApplicationController < ActionController::Base
     around_action :set_current_tenant

     private

     def set_current_tenant
       Tenant.current = Tenant.find_by(subdomain: request.subdomain)
       yield
     end
   end
   ```
   Jika terjadi *unhandled exception* di dalam aksi controller atau filter lanjutan, apa dampak fatal implementasi `around_action` di atas terhadap thread Puma yang melayani request selanjutnya? Bagaimana pola perbaikan standar industri menggunakan blok `ensure` atau `ActiveSupport::CurrentAttributes`?

3. **Debugging: The Silent Failure of Strong Parameters**  
   Sebuah API endpoint menerima payload JSON berupa:
   ```json
   {
     "organization": {
       "name": "Acme Corp",
       "settings": {
         "features": ["billing", "audit_logs"],
         "limits": { "users": 100 }
       }
     }
   }
   ```
   Developer menuliskan strong parameters:
   ```ruby
   params.require(:organization).permit(:name, settings: [:features, :limits])
   ```
   Namun, payload `settings.features` dan `settings.limits` selalu bernilai `nil` atau tereliminasi (*unpermitted*). Jelaskan akar masalah mekanisme internal Strong Parameters terkait *array of scalars* vs *arbitrary nested hash*, dan tuliskan sintaks perbaikan yang tepat!

4. **Dynamic Route Constraints Performance Impact**  
   Sebuah rute menggunakan dynamic class constraint:
   ```ruby
   constraints(SubdomainConstraint.new) do
     # routes
   end
   ```
   Kapan tepatnya method `matches?(request)` dievaluasi oleh Rack/Journey stack? Jika Anda melakukan query database `Tenant.exists?(subdomain: request.subdomain)` langsung di dalam method `matches?`, analisis apa dampak performa terhadap p99 latency aplikasi untuk seluruh request yang masuk (termasuk static asset request jika routing engine tidak diisolasi)?

5. **Exception Handling Hierarchy (`rescue_from` Bottom-Up Resolution)**  
   Bagaimana urutan deklarasi `rescue_from` diwariskan dan dievaluasi di level Controller? Mengapa potongan kode di bawah ini justru menangkap `StandardError` terlebih dahulu daripada `ActiveRecord::RecordNotFound` ketika `ActiveRecord::RecordNotFound` terjadi?
   ```ruby
   class ApplicationController < ActionController::API
     rescue_from ActiveRecord::RecordNotFound, with: :handle_not_found
     rescue_from StandardError, with: :handle_internal_error
     # ...
   end
   ```

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi & Memory Leak pada High-Throughput Ingestion Controller
* **Konteks:** Perusahaan IoT memiliki endpoint ingestion `POST /v1/telemetry` yang menerima 40.000 Request Per Second (RPS). Controller mewarisi `ApplicationController` (`ActionController::Base`) standar. Profiling menggunakan `rack-mini-profiler` dan APM menunjukkan bahwa controller mengalokasikan memori > 80MB per request cycle hanya untuk instansiasi Action Pack objects, rendering, session parsing, dan Flash storage, yang memicu CPU throttling akibat Ruby Garbage Collection (GC) stop-the-world.
* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana Anda merancang ulang controller ini menggunakan `ActionController::Metal` atau bare Metal Rack application di dalam ekosistem routing Rails untuk meniadakan middleware stack yang tidak perlu?
  2. Komponen modul controller apa saja yang minimal wajib diikutsertakan agar endpoint tetap mampu menangkap payload JSON dan melakukan response berstatus `204 No Content` secara aman?

### Skenario B: Race Condition & Cross-Tenant Data Leakage via Static Context
* **Konteks:** Pada audit kepatuhan ISO 27001, ditemukan insiden fatal: Tenant A terkadang dapat melihat data sensitif Tenant B pada sistem Enterprise B2B SaaS. Investigasi root-cause menemukan controller mengimplementasikan:
  ```ruby
  class ApplicationController < ActionController::Base
    before_action :set_tenant

    def set_tenant
      ActsAsTenant.current_tenant = Tenant.find(params[:tenant_id])
    end
  end
  ```
  Aplikasi berjalan di atas cluster Puma dengan konfigurasi multi-threaded (`threads 16, 16`).
* **Pertanyaan Diagnostik & Solusi:**
  1. Mengapa penetapan state tenant langsung pada variabel kelas/thread tanpa reset deterministik menyebabkan *cross-request context contamination* saat worker thread melayani request berikutnya?
  2. Rancang arsitektur controller boundary yang aman menggunakan middleware lifecycle atau `ActiveSupport::CurrentAttributes` lengkap dengan mekanisme pembersihan (*cleanup*) untuk menjamin *zero context bleed* antar-request!

### Skenario C: Migrasi Controller "God Class" (Massive Monolithic Action)
* **Konteks:** Sebuah aplikasi e-commerce memiliki `OrdersController#create` sepanjang 650 baris kode yang menangani: verifikasi kupon, perhitungan pajak multi-negara, fraud checking, reservasi inventaris via HTTP call, pembuatan record pesanan, pemrosesan kartu kredit via Stripe SDK, pengiriman email notifikasi, dan penyusunan JSON response. Kegagalan API eksternal sering membuat database transaksi gantung (*lock acquisition timeout*), dan controller hampir mustahil diuji secara unit (*test suite* membutuhkan waktu 4 menit hanya untuk controller ini).
* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana strategi pemecahan controller ini menggunakan arsitektur *Skinny Controller, Fat Domain* berbasis Service Objects / Command Pattern / Form Objects?
  2. Bagaimana controller seharusnya mengembalikan status respon HTTP yang berbeda (misal: `201 Created`, `422 Unprocessable Entity`, `402 Payment Required`, `504 Gateway Timeout`) tanpa mencemari controller dengan *nested `begin-rescue` blocks*?

---

## 4. Chapter Challenge

### Tantangan Praktis: Dynamic API Versioning Router Engine & Multi-Tenant Isolated Controller Subsystem

#### Problem Statement
Sebuah platform perbankan digital membutuhkan arsitektur routing dan controller enterprise yang mendukung:
1. **API Versioning** dinamis melalui HTTP Header (`Accept: application/vnd.bank.v1+json` vs `Accept: application/vnd.bank.v2+json`) dengan *graceful fallback* ke versi default.
2. **Subdomain-based Multi-Tenancy** dengan route constraints yang memblokir akses jika tenant berstatus `suspended` atau rute diakses melalui domain IP mentah, tanpa memicu overhead N+1 query database pada setiap request traversal di routing tree.
3. **Strict Parameter Sanitization & Mutation Engine** untuk endpoint transfer dana yang memvalidasi tipe data scalar ketat, array transaksi bersarang, dan *idempotency keys*.

#### Requirements
1. Buat custom constraint class `ApiVersionConstraint` yang membaca header `Accept` dan mengevaluasi versi target.
2. Buat custom constraint class `TenantConstraint` yang menginspeksi subdomain, membaca cache memori/Redis (mock interface) untuk validasi status tenant, dan menolak request invalid di gerbang routing.
3. Tuliskan file `config/routes.rb` yang mendemonstrasikan:
   - Nested resources menggunakan pattern `shallow: true`.
   - Routing concerns untuk fungsionalitas repeatable (misal: auditing / tracking).
   - Scoping modul terpisah antara versi `Api::V1` dan `Api::V2`.
4. Implementasikan `Api::BaseController` yang:
   - Mewarisi `ActionController::API`.
   - Menggunakan `ActiveSupport::CurrentAttributes` untuk tenant & request contextual isolation.
   - Mengimplementasikan `rescue_from` dengan handler error RESTful yang terstandarisasi (RFC 7807 Problem Details).
5. Implementasikan `Api::V1::TransfersController#create` yang menggunakan Form Object atau Command Object terisolasi; controller hanya bertugas: deserialisasi params via Strong Parameters, eksekusi service, dan response dispatching.

#### Constraints
- **Thread Safety:** Dilarang menggunakan *class variable* (`@@tenant`) atau *global variable* (`$tenant`).
- **Performance:** Eksekusi route constraint `matches?` tidak boleh memicu synchronous blocking SQL query langsung ke tabel master DB.
- **Fail-Safe:** Nilai `CurrentAttributes` wajib dibersihkan secara deterministik di akhir lifecycle eksekusi.
- **Pure REST:** Mengembalikan representasi payload standar RFC 7807 (`application/problem+json`) jika terjadi error validasi atau unhandled exception.

#### Expected Output
1. File `app/constraints/api_version_constraint.rb`
2. File `app/constraints/tenant_constraint.rb`
3. File `config/routes.rb`
4. File `app/controllers/api/base_controller.rb`
5. File `app/controllers/api/v1/transfers_controller.rb`
6. Penjelasan singkat analisis kompleksitas waktu & alokasi memori dari implementasi tersebut.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme kerja internal DFA Journey Router dalam memetakan HTTP request ke controller dan action.
- [ ] Perbedaan semantik, fungsional, dan performa antara `namespace`, `scope module:`, `scope path:`, dan *shallow routing*.
- [ ] Alur hidup (*lifecycle*) filter controller (`before_action`, `around_action`, `after_action`) dan bahaya *thread state leak* pada callback context.
- [ ] Perbedaan internal arsitektur `ActionController::Base` vs `ActionController::API` vs `ActionController::Metal`.
- [ ] Aturan mutasi data dan batasan keamanan pada `ActionController::Parameters` (Strong Parameters), khususnya penanganan array of scalars, arbitrary hashes, dan nested association attributes.
- [ ] Mekanisme resolusi hierarki `rescue_from` (bottom-to-top evaluation) dan interaksinya dengan middleware `ActionDispatch::ShowExceptions`.
- [ ] Bahaya I/O blocking di dalam Routing Constraints (`matches?`) terhadap request lifecycle.

### Saya tidak perlu menghafal:
- [ ] Seluruh daftar method bawaan helper URL (`*_path`, `*_url`) untuk setiap kemungkinan kombinasi rute.
- [ ] Format exact regex bawaan Rails untuk parsing IP address atau HTTP headers.
- [ ] Daftar lengkap middleware internal default di dalam `Rails.application.config.middleware`.
- [ ] Nama-nama konkrit status code symbol yang jarang dipakai (cukup memahami kode HTTP standar: 200, 201, 204, 400, 401, 403, 404, 422, 500, 503).

### Saya harus bisa melakukan:
- [ ] Merancang routing table yang clean, scalable, dan bebas dari *deep-nesting anti-pattern*.
- [ ] Membangun custom route constraint untuk sub-domain routing dan API header versioning tanpa membebani performa I/O database.
- [ ] Melakukan refactoring *God Controller* menjadi arsitektur decoupled berbasis Service Object, Form Object, atau Interactor Pattern.
- [ ] Mengonfigurasi filter multi-tenant yang 100% *thread-safe* di lingkungan server *concurrent/threaded* seperti Puma menggunakan `ActiveSupport::CurrentAttributes`.
- [ ] Melakukan sanitasi payload kompleks menggunakan Strong Parameters secara presisi tanpa meninggalkan celah *mass-assignment*.
- [ ] Mengisolasi controller berkinerja tinggi (*high-throughput*) menggunakan `ActionController::Metal` guna mereduksi memory allocation dan latensi GC.