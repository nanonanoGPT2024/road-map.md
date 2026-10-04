# BAB 03: Quiz, Challenge, & Knowledge Check
**Data Modeling & Active Record Mastery**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Eager Loading Internals (`preload` vs `eager_load` vs `includes`)**  
   Jelaskan perbedaan mendasar mekanisme eksekusi SQL antara `preload` dan `eager_load`. Bagaimana Active Record menentukan strategi query saat Anda menggunakan `includes`, dan kondisi teknis apa (seperti referensi relasi pada klausa `where`) yang memaksa Rails beralih dari strategi *two-query* (`preload`) ke *single-query with LEFT OUTER JOIN* (`eager_load`)? Apa implikasi alokasi memorinya pada Ruby Heap?

2. **Application-level Validations vs Database Integrity**  
   Mengapa deklarasi `validates :email, uniqueness: true` di model Active Record sama sekali tidak menjamin integritas keunikan data di lingkungan multi-threaded atau multi-process (Puma/Sidekiq)? Jelaskan konsep *Time-of-Check to Time-of-Use* (TOCTOU) race condition yang terjadi, dan bagaimana mitigasi wajib dilakukan pada level *storage engine* (RDBMS).

3. **Lifecycle Callbacks & Transaksional Trap**  
   Analisis perbedaan eksekusi antara callback `after_save`/`after_create` dan `after_commit`. Mengapa memicu *background job* (seperti Sidekiq worker) di dalam `after_create` berpotensi menimbulkan *race condition* berupa error `ActiveRecord::RecordNotFound` di worker process, sementara `after_commit` menjamin ketersediaan data tersebut?

4. **Polymorphic Associations vs Delegated Types**  
   Jelaskan perbedaan arsitektural dan skema database antara *Polymorphic Associations* tradisional (`imageable_type`, `imageable_id`) dan *Delegated Types* yang diperkenalkan pada Rails 6.1+. Mengapa polymorphic associations menyulitkan penerapan *Foreign Key constraints* di level database, dan bagaimana Delegated Types menyelesaikan masalah referensial integritas tersebut?

5. **Scopes vs Class Methods & Query Laziness**  
   Secara fungsional, `scope :active, -> { where(active: true) }` dan `def self.active; where(active: true); end` terlihat identik. Namun, bagaimana Active Record menangani evaluasi kondisional ketika query menghasilkan *falsy/nil*? Jelaskan mengapa `scope` selalu menjamin pengembalian objek `ActiveRecord::Relation` yang dapat di-*chain*, sedangkan *class method* biasa rentan menyebabkan `NoMethodError` jika mengembalikan `nil`.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Memory Blowout pada Batch Processing**  
   Diberikan sebuah task: membaca 2.000.000 record dari tabel `orders` untuk kalkulasi analitik harian.  
   - Mengapa penggunaan `Order.where(status: 'completed').each` memicu Out-of-Memory (OOM) killer pada container Rails?  
   - Bagaimana cara kerja internal `find_each` dan `in_batches` dalam membagi query menggunakan *keyset cursor pagination* (berbasis primary key)?  
   - Mengapa menambahkan klausul `.order("created_at DESC")` pada `find_each` menyebabkan Active Record mengabaikan atau melempar pengecualian (*runtime error*) terkait batasan sorting?

2. **Concurrency Control: Optimistic Locking vs Pessimistic Locking**  
   Anda diminta menangani mutasi saldo dompet digital (`wallets.balance`).  
   - Jelaskan implementasi internal *Optimistic Locking* menggunakan kolom `lock_version`, serta jenis exception yang dilempar (`ActiveRecord::StaleObjectError`) saat terjadi tabrakan pembaruan.  
   - Bandingkan dengan *Pessimistic Locking* (`with_lock` / `lock!`) yang mengeksekusi `SELECT ... FOR UPDATE`.  
   - Kapan penggunaan pessimistic locking menyebabkan ancaman *Database Deadlock*, dan strategi urutan penguncian (*lock ordering*) apa yang harus diterapkan untuk mencegahnya?

3. **Arel and SQL Injection Mitigation on Dynamic Queries**  
   Perhatikan pemanggilan berikut:
   ```ruby
   # Query A
   User.order(params[:sort_by])
   
   # Query B
   User.where("name = #{params[:name]}")
   
   # Query C
   User.where("name = ?", params[:name])
   ```
   Jelaskan bagaimana Rails 5.2/6+ menangkap kerentanan pada Query A dan mengapa `Arel.sql` diperlukan sebagai *explicit consent*. Apa perbedaan mendasar antara Query B dan Query C dalam hal mekanisme *query parsing* dan *parameter binding* oleh database driver (misal: `pg` gem)?

4. **Connection Pool Depletion & Thread Exhaustion**  
   Sebuah aplikasi Rails dengan Puma (konfigurasi: 5 process, 16 thread per process) sering mengalami error `ActiveRecord::ConnectionTimeoutError: could not obtain a connection from the pool within 5.000 seconds`.  
   - Bagaimana formula ideal penentuan `pool` size di `database.yml` terhadap concurrency Puma dan Sidekiq?  
   - Mengapa penulisan blok kode seperti `Thread.new { User.find(id) }` di dalam controller action dapat membocorkan *Active Record connection* jika tidak disertai dengan *connection checkout handling* (`ActiveRecord::Base.connection_pool.with_connection`)?

5. **Single Table Inheritance (STI) Anti-patterns & Structural Bloat**  
   STI menyatukan beberapa model turunan ke dalam satu tabel fisik melalui kolom `type`.  
   - Analisis dua dampak negatif terbesar STI terhadap arsitektur database relasional berskala besar (pertimbangkan aspek *column sparsity/NULL density* dan ketidakmampuan menerapkan constraint `NOT NULL` pada kolom spesifik subclass).  
   - Dalam kondisi arsitektur apa Anda harus memecah STI menjadi *Multiple Table Inheritance* (MTI via Delegated Types) atau *Class Table Inheritance*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Black Friday Query Bottleneck (N+1 & Unbounded Scans)
**Latar Belakang:**  
Saat event flash sale Black Friday, utilisasi CPU Postgres RDS melonjak dari 15% ke 100% dalam waktu 3 menit. APM (Datadog/NewRelic) menunjukkan query lambat didominasi oleh endpoint katalog produk:
```ruby
# Controllers/ProductsController.rb
def index
  @products = Product.where(category_id: params[:category_id]).limit(50)
end
```
```erb
<%# views/products/index.html.erb %>
<% @products.each do |product| %>
  <div>
    <h3><%= product.name %></h3>
    <p>Vendor: <%= product.merchant.profile.business_name %></p>
    <span>Price: <%= product.variants.pluck(:price).min %></span>
    <span>Review Avg: <%= product.reviews.average(:rating) %></span>
  </div>
<% end %>
```
**Pertanyaan Diagnostik:**
1. Hitung jumlah query yang dieksekusi per satu kali render HTTP request jika terdapat 50 produk, di mana masing-masing produk memiliki merchant, merchant memiliki profile, varian, dan reviews.
2. Rancang refactor lengkap pada layer Controller, Model, dan Database (termasuk penggunaan counter cache, denormalisasi selektif, atau *subquery aggregations*) untuk memangkas eksekusi query tersebut menjadi **maksimal 2–3 query konstan** tanpa memicu memory ballooning di server Rails!

---

### Skenario B: Double-Spending pada Sistem Ledger Transaksi
**Latar Belakang:**  
Sebuah startup fintech mendapati anomali: pengguna dapat menarik uang lebih dari saldo yang mereka miliki saat melakukan *withdrawal* simultan secara instan (mengirimkan 5 request bersamaan dalam rentang 10 milidetik).  
Kode implementasi yang sedang berjalan:
```ruby
class Account < ApplicationRecord
  validates :balance, numericality: { greater_than_or_equal_to: 0 }

  def withdraw(amount)
    if balance >= amount
      self.balance -= amount
      save!
    else
      raise InsufficientFundsError
    end
  end
end
```
**Pertanyaan Diagnostik:**
1. Bedah secara mekanis mengapa validasi model Active Record gagal mencegah saldo akun menjadi minus saat dieksekusi secara konkuren.
2. Tuliskan implementasi solusi perbaikan menggunakan dua pendekatan berbeda:
   - **Pendekatan 1:** Atomic update pada level database (`update_all` / raw SQL decrement with conditional `WHERE`).
   - **Pendekatan 2:** Database-level locking (`with_lock`) di dalam transaksi ACID, lengkap dengan penanganan idempotency key.

---

### Skenario C: Zero-Downtime Migration pada Skala 100 Juta Baris Data
**Latar Belakang:**  
Tabel `invoices` memiliki 120.000.000 baris data aktif di PostgreSQL. Anda diminta menambahkan kolom baru `metadata` bertipe data `jsonb` dengan nilai bawaan `{}` (bukan null) serta menambahkan index pada `user_id` dan `status` secara composite. Developer junior membuat migration berikut:
```ruby
class AddMetadataAndIndexToInvoices < ActiveRecord::Migration[7.1]
  def change
    add_column :invoices, :metadata, :jsonb, default: {}, null: false
    add_index :invoices, [:user_id, :status]
  end
end
```
Saat deployment dijalankan di staging berskala besar, proses migrasi menyebabkan *table lock* berkepanjangan (Access Exclusive Lock), yang jika terjadi di produksi akan menyebabkan seluruh request *timeout* (HTTP 504) dan aplikasi *down*.

**Pertanyaan Diagnostik:**
1. Mengapa perintah `add_index` dan `add_column` di atas menyebabkan *exclusive table lock* di PostgreSQL? Jelaskan dampaknya terhadap antrian operasi `SELECT`, `INSERT`, dan `UPDATE`.
2. Tuliskan ulang skrip migrasi tersebut dengan mematuhi prinsip **Zero-Downtime Database Migration** (menggunakan `disable_ddl_transaction!`, `algorithm: :concurrently`, dan pemisahan penambahan kolom serta backfilling/constraint application secara bertahap).

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Idempotent Ledger Engine with Concurrency Safeguards

#### Deskripsi Masalah
Anda diminta membangun fondasi mesin pencatatan transaksi (*Double-Entry Bookkeeping Ledger Engine*) untuk sistem e-wallet core banking. Sistem harus mampu menangani ribuan transaksi debit dan kredit simultan antar akun, menjamin tidak ada uang yang tercipta dari ketiadaan (*zero-sum balance*), kebal terhadap race condition, dan tidak membocorkan query N+1 saat inspeksi log akun.

#### Spesifikasi Kebutuhan & Arsitektur
1. **Schema & Models:**
   - Model `Account` (memiliki `balance_cents`, `currency`, `lock_version`, status).
   - Model `LedgerEntry` (menggunakan *Delegated Types* untuk mengabstraksi tipe transaksi: `TransferEntry`, `DisbursementEntry`, `TopUpEntry`).
   - Kolom audit transaksi: `idempotency_key`, `amount_cents`, `source_account_id`, `destination_account_id`, `status`.
2. **Database Integrity:**
   - Foreign key constraints eksplisit dengan strategi `on_delete: :restrict`.
   - Database constraint Check: `balance_cents >= 0` pada tabel `accounts`.
   - Index unik pada `idempotency_key` di level DB.
3. **Execution Service (`TransferService`):**
   - Menerima `source_account_id`, `destination_account_id`, `amount_cents`, dan `idempotency_key`.
   - Eksekusi diisolasi dalam satu DB Transaction dengan *Pessimistic Locking* terurut (urutkan ID akun secara leksikografis sebelum mengunci untuk memitigasi deadlock).
   - Menghasilkan dua baris `LedgerEntry` (debit dan kredit) secara atomik.
   - Pengecekan idempotensi: jika `idempotency_key` yang sama dikirimkan kembali, sistem harus mengembalikan objek transaksi yang sudah ada tanpa melakukan mutasi ganda (*idempotent replay*).
4. **Optimasi & Callbacks:**
   - Callback notifikasi: Saat transaksi sukses, trigger job asynchronous (`PublishLedgerNotificationJob`) menggunakan callback `after_commit`, bukan `after_save`.
   - Sediakan scope `.recent_audit_trail` pada `Account` yang mengambil 20 riwayat transaksi terakhir lengkap dengan polymorphic record tanpa N+1 query.

#### Batasan Teknis (Constraints)
- Wajib menggunakan Rails 7.x/8.x convention.
- Dilarang membiarkan ada celah *arithmetic overflow* atau ketidakpresisian *floating point* (gunakan integer/cents).
- Dilarang menggunakan raw SQL `execute` tanpa parameterization (perlindungan penuh terhadap SQL injection).
- Tidak boleh terjadi memory leak pada pengujian simulasi throughput tinggi.

#### Expected Output
1. File migrasi database (`db/migrate/XXXXXX_create_ledger_engine.rb`) dengan constraint, indexing, dan foreign keys yang ketat.
2. File definisi model: `Account`, `LedgerEntry`, dan delegated type models.
3. Service object `TransferService` yang siap diuji secara konkuren (menggunakan thread concurrency test).
4. Potongan RSpec / Minitest concurrent integration test yang membuktikan:
   - 20 thread mencoba mendebit akun yang sama hanya dengan saldo cukup untuk 5 transaksi; tepat 5 transaksi berhasil dan 15 lainnya ditolak secara elegan tanpa merusak integritas database.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kematangan teknis Anda setelah mempelajari modul Data Modeling & Active Record Mastery:

### Saya harus memahami:
- [ ] Siklus hidup Active Record Query: Bagaimana Arel mengompilasi representasi AST menjadi native SQL string spesifik adapter (PG/MySQL).
- [ ] Perbedaan fungsional, performa, dan memori antara `preload`, `eager_load`, dan `includes`.
- [ ] Mekanisme kerja isolation level transaksi database (Read Committed, Repeatable Read, Serializable) serta bagaimana Rails berinteraksi dengannya.
- [ ] Anatomi Database Locks: Perbedaan Shared Lock (`FOR SHARE`), Exclusive Lock (`FOR UPDATE`), dan DDL Lock (Access Exclusive).
- [ ] Pola Delegated Types sebagai solusi alternatif dari Single Table Inheritance (STI) untuk skalabilitas skema.
- [ ] Bahaya callback lifecycle jika digunakan untuk business domain logic yang kompleks (fat model callback anti-pattern).

### Saya tidak perlu menghafal:
- [ ] Seluruh flag parameter pada generator migration (cukup pahami sintaks DDL inti di file migration Ruby).
- [ ] Daftar lengkap method kalkulasi Arel internal privat yang tidak di-expose di public API Active Record.
- [ ] Konfigurasi default adapter database non-relasional yang tidak didukung langsung oleh core Active Record.

### Saya harus bisa melakukan:
- [ ] Menemukan dan mengeliminasi bug N+1 query menggunakan profiling tools (Bullet, Rack-Mini-Profiler, atau SQL logs) dalam hitungan menit.
- [ ] Mendesain schema migration zero-downtime untuk tabel berskala puluhan juta baris tanpa mengganggu operasi write/read di produksi.
- [ ] Menulis query batching yang efisien pada data berukuran gigabyte menggunakan `in_batches` tanpa memicu Ruby Heap OOM.
- [ ] Mengimplementasikan *Pessimistic Locking* bebas deadlock untuk operasi finansial atau inventaris dengan high-contention rate.
- [ ] Mengatur konfigurasi connection pool database yang sinkron dan tangguh terhadap konkurensi Puma threads dan worker Sidekiq.