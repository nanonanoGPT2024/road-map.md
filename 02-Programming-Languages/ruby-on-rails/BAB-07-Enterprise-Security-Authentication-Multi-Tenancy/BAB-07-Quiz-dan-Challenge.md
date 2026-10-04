# BAB 07: Quiz, Challenge, & Knowledge Check
**Enterprise Security, Authentication & Multi-Tenancy**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi Proteksi CSRF di Rails Engine:**
   Jelaskan secara mendalam bagaimana Rails memvalidasi request authenticity melalui token CSRF (`authenticity_token`). Bedakan implementasi teknis dan implikasi keamanan antara strategi `:exception`, `:reset_session`, dan `:null_session` pada method `protect_from_forgery`. Kapan `:null_session` menjadi vektor eksploitasi jika API endpoint mengandalkan sesi berbasis cookie?

2. **Kriptografi & Mekanisme Internal `has_secure_password`:**
   Bagaimana Rails mengimplementasikan `ActiveModel::SecurePassword` di bawah kap mesin? Jelaskan peran *salt*, *cost factor* (work factor) pada algoritma `bcrypt`, dan bagaimana method `authenticate` memitigasi risiko *timing attacks* saat memvalidasi kecocokan string password dengan `password_digest`.

3. **Batasan Keamanan Strong Parameters:**
   Mengapa deklarasi `params.require(:user).permit!` dianggap sebagai pelanggaran keamanan fatal (*Mass Assignment Vulnerability*), dan bagaimana Rails secara internal menandai parameter sebagai *permitted* atau *unpermitted*? Jelaskan skenario di mana nested attributes (`accepts_nested_attributes_for`) yang tidak divalidasi strukturnya secara eksplisit dapat dieksploitasi untuk mengubah relasi record milik entitas lain.

4. **Kelemahan Inheren `default_scope` dalam Multi-Tenancy:**
   Banyak developer pemula menggunakan `default_scope { where(tenant_id: Current.tenant.id) }` untuk isolasi data tenant berbasis *row-level*. Jelaskan secara teknis mengapa pendekatan ini dianggap sebagai *anti-pattern* berbahaya di sistem enterprise (kaitkan dengan mekanisme `unscoped`, *default scope inheritance*, dan operasi asosiasi database).

5. **Session Store Internals: CookieStore vs CacheStore/Redis:**
   Analisis perbedaan arsitektur keamanan antara `ActionDispatch::Session::CookieStore` dan storage berbasis server seperti `RedisStore`. Bagaimana Rails 7/8 memanfaatkan `ActiveSupport::MessageEncryptor` dan `secret_key_base` untuk mengamankan *encrypted cookie*, dan apa risiko replay attack jika sesi dihentikan (*revoked*) di aplikasi tanpa adanya *server-side state*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **ActiveRecord Encryption: Deterministic vs Non-Deterministic:**
   Diperkenalkan sejak Rails 7, `encrypts :attribute` menawarkan mode deterministik dan non-deterministik. Jelaskan perbedaan matematis/kriptografis kedua mode ini, trade-off terkait kemampuan query (`where(attribute: value)`), dan bagaimana strategi *key rotation* dijalankan di lingkungan produksi tanpa menyebabkan *downtime* atau *data corruption*.

2. **Thread Safety & State Leakage pada `ActiveSupport::CurrentAttributes`:**
   Diberikan implementasi berikut untuk multi-tenancy:
   ```ruby
   class Current < ActiveSupport::CurrentAttributes
     attribute :tenant, :user
   end
   ```
   Jelaskan siklus hidup (*lifecycle*) objek `CurrentAttributes` per request pada web server berbasis multi-threaded (Puma). Apa yang terjadi jika thread yang sama dialokasikan kembali untuk me-request resource lain sementara Rails Executor gagal mengeksekusi `Current.reset`? Bagaimana mitigasi kebocoran konteks ini pada Sidekiq background job?

3. **Eksploitasi SQL Injection Modern via `Arel.sql` dan Dynamic Ordering:**
   Mengapa kode berikut memicu peringatan deprecation/keamanan di Rails dan bagaimana penyerang dapat mengeksploitasinya jika `params[:sort_by]` tidak divalidasi:
   ```ruby
   User.order(Arel.sql("#{params[:sort_by]} #{params[:direction]}"))
   ```
   Jelaskan mekanisme internal Rails SQL sanitization dan demonstrasikan bagaimana penyerang menyuntikkan fungsi *conditional time delay* (misal: `pg_sleep`) melalui parameter tersebut.

4. **Isolasi Database Multi-Tenancy: PostgreSQL Row-Level Security (RLS) vs Connection Pooling:**
   Ketika mengintegrasikan Rails dengan PostgreSQL RLS menggunakan session variable:
   ```sql
   SET LOCAL app.current_tenant_id = 'tenant_123';
   ```
   Jelaskan kegagalan fatal yang dapat terjadi apabila sistem menggunakan PgBouncer dengan mode `transaction pooling` jika perintah `SET` dijalankan di luar blok transaksi aktif (`ActiveRecord::Base.transaction`). Bagaimana arsitektur *connection checkout/checkin lifecycle* pada `ActiveRecord::ConnectionAdapters::ConnectionPool` harus dikonfigurasi untuk mencegah kebocoran data antar-tenant?

5. **Content Security Policy (CSP) & Cryptographic Nonces:**
   Bagaimana Rails mengelola CSP nonces secara dinamis per HTTP request? Jika aplikasi menggunakan kombinasi server-rendered views dan dynamic SPA bootstrapping, jelaskan mengapa penggunaan directive `'unsafe-inline'` menggagalkan seluruh proteksi XSS dan bagaimana mekanisme `content_security_policy_nonce` disuntikkan ke dalam asset pipeline/importmaps secara aman.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Kebocoran Data Lintas Tenant pada Background Job Pipeline
Sebuah platform B2B FinTech memproses pembuatan invoice massal menggunakan Sidekiq Enterprise dengan 20 worker threads per process. Setiap tenant memiliki template invoice dan data transaksi sendiri. 

Tiba-tiba, Tenant Alpha melaporkan bahwa mereka menerima draft invoice milik Tenant Beta yang merupakan kompetitor langsungnya. Investigasi awal menunjukkan bahwa bug ini tidak terjadi di lingkungan controller (HTTP request), melainkan sporadis di background job:

```ruby
class InvoiceGeneratorJob < ApplicationJob
  queue_as :critical

  def perform(invoice_id)
    invoice = Invoice.find(invoice_id)
    # Current.tenant diasumsikan sudah terpasang oleh middleware kustom
    PdfGenerator.new(invoice, Current.tenant).generate_and_send!
  end
end
```

* **Pertanyaan Diagnostik:**
  1. Identifikasi akar masalah arsitektural mengapa `Current.tenant` bernilai salah atau *stale* di dalam thread Sidekiq yang digunakan kembali (*reused thread*).
  2. Rancang solusi arsitektur permanen menggunakan custom Sidekiq Client/Server Middleware yang menjamin `Current.tenant` diisolasi secara deterministik untuk setiap execution frame dan di-reset secara mutlak tanpa mengandalkan inisialisasi manual di dalam body job.

---

### Skenario B: Race Condition & Token Replay pada Dual-Token (Access/Refresh) API Auth
Aplikasi mobile enterprise Rails menggunakan arsitektur stateless token: Access Token (masa aktif 15 menit) dan Refresh Token (masa aktif 30 hari). Sistem menerapkan strategi *Refresh Token Rotation* (setiap kali refresh token digunakan, token tersebut diinvalidasi dan sepasang token baru diterbitkan). 

Di kondisi jaringan tidak stabil (edge network), aplikasi mobile mengirimkan 3 request refresh token secara simultan (*concurrent burst*). Akibatnya:
- Request pertama berhasil me-refresh token.
- Request kedua dan ketiga menggunakan token lama yang sudah diinvalidasi, sehingga sistem mendeteksinya sebagai *Security Breach Attempt* (Token Theft Replay) dan langsung memblokir akun user secara otomatis (*automatic session revocation*). Hal ini menyebabkan komplain ribuan eksekutif perusahaan yang mendapati akun mereka terkunci tiba-tiba.

* **Pertanyaan Diagnostik:**
  1. Analisis titik kegagalan (*race condition*) pada database level saat beberapa request refresh membaca dan memvalidasi token yang sama secara paralel.
  2. Rancang pola mitigasi teknis (melibatkan *optimistic locking*, *distributed lock* Redis, atau *grace period window* dengan status *token rotation grace*) agar sistem toleran terhadap network jitter tanpa membuka celah replay attack yang sesungguhnya.

---

### Skenario C: Dilema Arsitektur Multi-Tenancy: Shared Database (Tenant ID) vs Schema-per-Tenant
Platform SaaS ERP Anda memiliki 5.000 tenant UMKM (aktivitas rendah) dan 10 tenant Enterprise berskala multinasional (aktivitas jutaan transaksi per jam). Sistem saat ini menggunakan satu database PostgreSQL bersama (*shared database*) dengan kolom `tenant_id` dan integrasi gem `acts_as_tenant`.

Masalah muncul:
1. *Noisy Neighbor Effect*: Query analitik berat dari satu tenant Enterprise menyebabkan query operasional tenant UMKM mengalami timeout.
2. Ukuran table transaksi mencapai 500 juta baris; proses Rails database migration (`db:migrate`) saat deploy menimbulkan lock table dan degrading performa seluruh sistem.
3. Klien Enterprise baru mensyaratkan isolasi data fisik untuk kepatuhan SOC2 dan GDPR.

* **Pertanyaan Diagnostik:**
  1. Bandingkan secara objektif arsitektur **Shared Database with PostgreSQL RLS** vs **Schema-per-Tenant (PostgreSQL Schemas via Apartment/Ros-Apartment)** vs **Database-per-Tenant**. Evaluasi dari aspek: overhead koneksi database, kompleksitas migrasi skema, dan skalabilitas jangka panjang.
  2. Berikan rancangan arsitektur hibrida (*hybrid multi-tenancy model*) yang memungkinkan Rails melayani ribuan tenant kecil dalam shared database, namun secara transparan memisahkan tenant Enterprise ke database/schema terdedikasi tanpa memecah codebase Rails menjadi multi-aplikasi.

---

## 4. Chapter Challenge

### Tantangan Praktis: Membangun Enterprise Zero-Trust Multi-Tenant Engine Berbasis PostgreSQL RLS & Context-Aware Authorization

#### Deskripsi Masalah
Banyak aplikasi Rails enterprise mengalami kegagalan compliance keamanan akibat kebocoran data (*data leakage*) yang disebabkan oleh human error pengembang (misalnya: lupa menambahkan scoping `.where(tenant_id: ...)` atau bypass otorisasi di endpoint baru). Anda ditugaskan untuk merancang dan mengimplementasikan modul keamanan inti dari awal (*zero-trust engine*) yang mengunci isolasi data langsung di layer PostgreSQL dan memberlakukan otorisasi berbasis atribut (*Attribute-Based Access Control* - ABAC).

#### Requirements
1. **Database-Level Isolation (PostgreSQL RLS):**
   * Buat migrasi PostgreSQL untuk mengaktifkan RLS pada tabel sensitif (`organizations`, `projects`, `audit_logs`).
   * Terapkan policy RLS yang membatasi akses baca/tulis hanya jika `tenant_id` pada baris data sesuai dengan session variable `app.current_tenant_uuid`.
   * Buat mekanisme Rails Connection Handler/Executor yang secara otomatis mengeksekusi `SET LOCAL app.current_tenant_uuid = ...` setiap kali koneksi dipinjam dari pool, dan memastikan nilainya dibersihkan (*reverted*) saat transaksi selesai.
2. **Context Propagation Engine:**
   * Bangun abstraksi `ApplicationContext` yang aman secara thread (*thread-safe*), mengkapsulasi data `current_tenant`, `current_user`, dan `client_ip`.
   * Integrasikan context ini ke dalam Rack middleware, ActionController, dan Sidekiq middleware (Client & Server) sehingga tenant context berpindah secara deterministik ke background jobs.
3. **ABAC Policy Layer:**
   * Implementasikan authorization engine (menggunakan Pundit atau Action Policy) yang memvalidasi tidak hanya peran (*role*), tetapi atribut konteks dinamis:
     * Pengguna hanya boleh membaca data project jika IP address mereka terdaftar di whitelist IP Tenant.
     * Jika role adalah `auditor`, akses otomatis bersifat *read-only* terlepas dari scope permission lainnya.
4. **Tamper-Evident Audit Logging:**
   * Setiap operasi mutasi (Create, Update, Destroy) pada tabel tenant harus mencatat audit trail ke tabel `audit_logs` secara otomatis (via ActiveRecord Callback atau Database Trigger).
   * Payload audit log harus menyertakan: `tenant_id`, `actor_id`, `action`, `delta_changes` (diff data sebelum & sesudah), dan `request_uuid`.
   * Kolom audit log harus diproteksi dari modifikasi atau penghapusan manual, bahkan oleh admin tenant sekalipun.

#### Constraints
* Dilarang menggunakan gem multi-tenancy *magic* siap pakai (seperti `acts_as_tenant`, `apartment`, atau `milia`). Seluruh logika isolasi RLS dan routing context harus ditulis murni (*pure architectural code*).
* Wajib kompatibel dengan PgBouncer (mode `transaction pooling`). Pengaturan session variable PostgreSQL harus strictly menggunakan `SET LOCAL` di dalam blok database transaction.
* Coverage automated tests (RSpec) minimal 95% mencakup:
  * Uji penetrasi kebocoran data antar-tenant (membuktikan bahwa query raw `Project.unscoped.all` tetap gagal melihat data tenant lain saat RLS aktif).
  * Uji multithreading concurrency (memastikan dua thread berbeda mengeksekusi query secara bersamaan untuk dua tenant berbeda tanpa cross-talk data).

#### Expected Output
* File migrasi database Rails lengkap dengan script DDL PostgreSQL RLS (`ENABLE ROW LEVEL SECURITY`, `CREATE POLICY`).
* Service `TenantContext` & Middleware stack kustom (Rack + Sidekiq).
* Modul integrasi `ActiveRecord` connection checkout hooks.
* Implementation classes: Model, Policy, dan Controller concern.
* File RSpec suite (`spec/security/rls_isolation_spec.rb` dan `spec/security/thread_leak_spec.rb`) yang memvalidasi seluruh skenario pengujian di atas.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup proteksi CSRF di Rails dan perbedaan mendalam penanganan autentikasi via Session Cookie vs Bearer Token.
- [ ] Cara kerja internal hashing `bcrypt`, peranan *stretching/cost factor*, dan mitigasi *side-channel/timing attacks* dengan `ActiveSupport::SecurityUtils.secure_compare`.
- [ ] Risiko keamanan arsitektural pada `ActiveSupport::CurrentAttributes` dalam lingkungan multi-threaded dan asynchronous.
- [ ] Vektor serangan SQL Injection tingkat lanjut yang lolos dari validasi standar Rails (Arel injection, dynamic table/column identifiers).
- [ ] Konsep kriptografi pada ActiveRecord Encryption (perbedaan skema *Envelope Encryption*, *AES-GCM*, serta implikasi *deterministic vs non-deterministic* terhadap query B-Tree index).
- [ ] Mekanisme kerja PostgreSQL Row-Level Security (RLS) dan integrasinya dengan session-level configuration (`SET LOCAL`).
- [ ] Arsitektur perbandingan Multi-Tenancy: *Shared Database vs Schema-per-Tenant vs Database-per-Tenant* beserta trade-off performa, migrasi, dan isolasi.
- [ ] Content Security Policy (CSP), nonce lifecycle per-request, dan integrasi HTTP Security Headers (HSTS, X-Frame-Options, Permissions-Policy).

### Saya tidak perlu menghafal:
- [ ] Sintaks spesifik setiap algoritma kriptografi hashing internal bcrypt/AES (Rails dan OpenSSL mengabstraksi detail implementasi low-level ini).
- [ ] Seluruh daftar puluhan directive CSP standar W3C (cukup pahami fondasi `'self'`, nonces, `'strict-dynamic'`, dan cara men-debug pelanggaran via browser console/reporting endpoint).
- [ ] API method privat internal dari gem autentikasi pihak ketiga (Devise/Warden/Rodauth).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi dan mengamankan session management Rails dari serangan *Session Fixation* dan *Cookie Tampering*.
- [ ] Mengimplementasikan isolasi multi-tenant anti-bocor menggunakan PostgreSQL RLS yang kompatibel dengan connection pooler skala enterprise (PgBouncer).
- [ ] Menulis Sidekiq middleware untuk serialisasi dan deserialisasi state tenant/user context secara aman melintasi boundary proses.
- [ ] Mendiagnosis dan memperbaiki celah keamanan *Mass Assignment*, *Insecure Direct Object References (IDOR)*, dan *Broken Object Level Authorization (BOLA)* menggunakan Pundit atau Action Policy.
- [ ] Menerapkan *ActiveRecord Encryption* dengan rotasi kunci berkala (*zero-downtime key rotation*) pada data sensitif (PII/Finansial).
- [ ] Menulis test suite otomatis (RSpec) yang secara spesifik menyimulasikan serangan konkurensi data, kebocoran thread-local storage, dan penetrasi bypass otorisasi.