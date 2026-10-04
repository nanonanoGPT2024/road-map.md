# Bab 03 Module 01: Data Modeling & Active Record Mastery

---

## SEKSI 01 — IDENTITAS MODUL

| Parameter | Spesifikasi |
| :--- | :--- |
| **Kategori Kurikulum** | 02-Programming-Languages |
| **Jalur Keahlian** | Ruby on Rails Backend Engineering |
| **Kode Modul** | ROR-0301 |
| **Nama Modul** | Data Modeling & Active Record Mastery |
| **Tingkat Kesulitan** | Intermediate to Advanced |
| **Estimasi Waktu Belajar** | 12 - 16 Jam |
| **Prasyarat** | Pemahaman Ruby OOP dasar, SQL tingkat menengah, arsitektur dasar MVC Rails, eksekusi Rails CLI dasar. |
| **Target Ekosistem** | Ruby 3.2+, Rails 7.1+, PostgreSQL 14+ |

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan memiliki kapabilitas teknis untuk:

1. **Menganalisis dan Mengimplementasikan Arsitektur Active Record:** Menguasai siklus hidup objek (lifecycle), *Arel Abstract Syntax Tree (AST)*, serta mekanisme abstraksi basis data yang digunakan Rails untuk memetakan logika bisnis ke tabel relasional.
2. **Merancang Relasi Data Kompleks:** Mengonfigurasi relasi `belongs_to`, `has_many :through`, asosiasi polimorfik (*polymorphic associations*), dan *Delegated Types* dengan integritas referensial yang ketat pada level aplikasi dan database.
3. **Mengeliminasi Inefisiensi Kueri Data:** Mengidentifikasi dan memitigasi masalah *N+1 Query*, menganalisis perbedaan mendalam antara `includes`, `preload`, dan `eager_load`, serta mengonfigurasi `strict_loading` secara granular.
4. **Menjamin Konsistensi Transaksional:** Mengimplementasikan teknik penguncian konkurensi (*Pessimistic vs Optimistic Locking*) dan atomisitas transaksi multi-model guna mencegah *race condition* pada sistem dengan throughput tinggi.
5. **Menerapkan Zero-Downtime Migration:** Menyusun migrasi skema database tingkat produksi yang aman untuk tabel skala jutaan baris tanpa menimbulkan penguncian tabel (*table lock*) destruktif.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Active Record Pattern vs. Data Mapper Pattern
Dalam rekayasa perangkat lunak perusahaan, terdapat dua paradigma utama *Object-Relational Mapping (ORM)*:
- **Active Record (Rails):** Sebuah baris database dibungkus secara langsung ke dalam sebuah objek yang menggabungkan status data (atribut) dan perilaku (metode bisnis, persistensi, validasi).
- **Data Mapper (ROM-rb, Hibernate):** Memisahkan status data murni (*Entity*) dari logika persistensi (*Repository/Mapper*).

```
Paradigma Active Record:
+-------------------------------------------------------------+
|                     User (Model Class)                      |
|  [Data: id, email, balance] + [Logika: charge!, save, sync] |
+-------------------------------------------------------------+
                               |
                               v (Persistensi Langsung)
                       [ Tabel: users ]
```

### Mental Model Representasi Data
Jangan memandang `ActiveRecord::Relation` sebagai *Array of Objects*. `ActiveRecord::Relation` adalah sebuah **Query Definition Proxy** yang bersifat *lazy-evaluated*. Evaluasi kueri database hanya terjadi ketika data benar-benar diakses (misalnya pemanggilan `.each`, `.to_a`, `.first`, atau inspeksi di konsol). Sebelum dievaluasi, relasi dapat dirangkai (*chained*), digabungkan (*merged*), dan dimodifikasi tanpa membebani I/O database.

### Single Source of Truth: Database vs. Ruby VM
Banyak insinyur pemula berasumsi bahwa validasi Rails di memori (`validates :email, uniqueness: true`) sudah cukup untuk menjamin integritas data. Mental model yang benar: **Database adalah benteng pertahanan terakhir**. Status di dalam memori Ruby VM bersifat fana (*ephemeral*) dan rentan terhadap konkurensi antar-thread maupun multi-process worker. Validasi Rails berfungsi untuk memberikan umpan balik cepat (*user-friendly error messaging*), sedangkan *Database Constraints* (unique indexes, foreign keys, check constraints) menjamin kebenaran absolut (*data integrity*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Arsitektur Eksekusi Kueri: Dari Ruby ke SQL (Arel Engine)

```
+-------------------------------------------------------------------------+
|                              Ruby Layer                                 |
|   User.where(active: true).joins(:orders).where(orders: { status: 1 })  |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                       ActiveRecord::Relation                            |
|             Menampung representasi klausa (WhereClause, Joins)          |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                              Arel AST                                   |
|   Struktur Pohon Sintaks Abstrak: nodes/equality.rb, nodes/select.rb    |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                  Database Adapter (PostgreSQLAdapter)                   |
|   Arel::Visitors::PostgreSQL mengompilasi AST menjadi Raw SQL String    |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                       Connection Pool (pg gem)                          |
|             Mengeksekusi SQL melalui koneksi soket TCP/Unix             |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                       Type Casting & Instansiasi                        |
|  Mentransformasikan PostgreSQL binary/text result ke Ruby Model Object  |
+-------------------------------------------------------------------------+
```

### Siklus Hidup Transaksi dan Callbacks

```
  [ Pemanggilan .save / .create ]
                 |
                 v
      +---------------------+
      |   before_validation |
      +---------------------+
                 |
                 v
      +---------------------+
      |      validate       |  ---> (Gagal) -> Transaksi Dibatalkan
      +---------------------+
                 |
                 v
      +---------------------+
      |   after_validation  |
      +---------------------+
                 |
                 v
    === START DB TRANSACTION ===
                 |
                 v
      +---------------------+
      |     before_save     |
      +---------------------+
                 |
                 v
      +---------------------+
      |    before_create    |
      +---------------------+
                 |
                 v
      [ INSERT INTO database ]
                 |
                 v
      +---------------------+
      |    after_create     |
      +---------------------+
                 |
                 v
      +---------------------+
      |     after_save      |
      +---------------------+
                 |
                 v
    === COMMIT DB TRANSACTION ===
                 |
                 v
      +---------------------+
      |    after_commit     |  <--- Aman untuk Sidekiq / External Webhooks
      +---------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Arel Engine
Arel (Active Record Relation Engine) adalah pustaka internal pengelola *Abstract Syntax Tree (AST)* SQL. Alih-alih merangkai string secara naif, Active Record memetakan kueri ke dalam simpul-simpul pohon:
- `Arel::Table`: Memetakan representasi tabel skema.
- `Arel::Nodes::Node`: Node spesifik seperti `Equality`, `GreaterThan`, `Grouping`, `And`, `Or`.
- Visitor Pattern (`Arel::Visitors::ToSql`): Bertugas menyusuri pohon tersebut dan mengompilasinya menjadi dialek SQL spesifik target DBMS (PostgreSQL, MySQL, SQLite).

### 2. Type Casting & Schema Reflection
Saat aplikasi Rails melakukan *booting*, Active Record memeriksa katalog database (`pg_attribute`, `information_schema`) untuk mendeteksi kolom, tipe data, nilai default, dan nullability. Nilai string dari respons socket database dikonversi ke tipe objek Ruby yang sesuai (misal PostgreSQL `jsonb` menjadi Ruby `Hash`, `timestamp with time zone` menjadi `ActiveSupport::TimeWithZone`) menggunakan modul `ActiveModel::Type`.

### 3. Dirty Tracking (`ActiveModel::Dirty`)
Active Record melacak mutasi pada atribut model sebelum disimpan ke database:
- `attribute_changed?`: Memeriksa apakah ada perubahan.
- `attribute_was`: Mengambil nilai sebelum terjadi mutasi di memori.
- `changes`: Menghasilkan hash perubahan `{"status" => ["draft", "published"]}`.
Internal Rails menggunakan snapshot *mutation tracker* untuk hanya mengirim kolom yang termutasi (`UPDATE table SET status = 'published' WHERE id = 1`) alih-alih menimpa seluruh kolom.

### 4. Connection Pool
Koneksi database dikelola melalui `ActiveRecord::ConnectionAdapters::ConnectionPool`. Mekanisme ini membatasi jumlah soket koneksi yang terbuka secara simultan untuk melayani beberapa thread eksekusi (seperti web server Puma). Setiap thread yang membutuhkan kueri akan meminjam koneksi (*checkout*) dan mengembalikannya (*checkin*) ke dalam pool setelah blok pemrosesan selesai.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Strategi Penanganan Hubungan Asosiasi Data
1. **`has_many :through` vs. `has_and_belongs_to_many` (HABTM):**
   - Gunakan `has_many :through` di hampir seluruh kasus produksi. Pendekatan ini menggunakan model perantara (*join model*) yang memiliki entitas mandiri, memungkinkan penambahan validasi, stempel waktu (`created_at`), dan metadata atribut lainnya.
   - HABTM adalah peninggalan legasi tanpa model join eksplisit yang sulit dikembangkan ketika kebutuhan bisnis berevolusi.

2. **Polymorphic Associations vs. Delegated Types:**
   - **Polimorfisme Tradisional:** Menggunakan dua kolom (`commentable_type`, `commentable_id`). Kelemahan: Kehilangan integritas *Foreign Key* sejati pada level database PostgreSQL karena `commentable_id` merujuk ke tabel yang dinamis.
   - **Delegated Types (Rails 6.1+):** Mengabstraksi pemodelan *Class Table Inheritance (CTI)*. Entitas superclass (misal `Entry`) merepresentasikan baris konkret dengan ID dan foreign key nyata, lalu mendelegasikan perilaku dan data spesifik ke tabel turunan (`Message`, `Comment`) melalui skema relasional yang terindeks dan aman secara referensial.

3. **Mekanisme Eager Loading: `preload`, `eager_load`, dan `includes`:**
   - `preload`: Memisahkan eksekusi menjadi dua kueri independen (`SELECT * FROM users; SELECT * FROM profiles WHERE user_id IN (...)`). Tidak mengizinkan pemfilteran pada tabel asosiasi menggunakan klausa `WHERE`.
   - `eager_load`: Memaksa Active Record melakukan `LEFT OUTER JOIN` tunggal untuk menarik semua asosiasi sekaligus. Mengonsumsi memori lebih besar pada database dan Ruby VM karena duplikasi baris *Cartesian product*, namun memungkinkan pemfilteran langsung pada tabel join.
   - `includes`: Logika otomatis (*heuristic*). Jika kueri tidak menyertakan klausa kondisi pada tabel relasi, Rails mengeksekusi strategi `preload`. Jika terdapat klausa kondisi (misal `.where("profiles.verified = true").references(:profiles)`), Rails otomatis beralih ke strategi `eager_load`.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi dasar data model relasional: Sebuah platform penerbitan artikel yang memiliki `Organization`, `User`, `Article`, dan `Tag`.

### 1. Migrasi Database (PostgreSQL)

```ruby
# db/migrate/20240101000001_create_core_publishing_schema.rb
class CreateCorePublishingSchema < ActiveRecord::Migration[7.1]
  def change
    create_table :organizations do |t|
      t.string :name, null: false
      t.string :slug, null: false
      t.timestamps
    end
    add_index :organizations, :slug, unique: true

    create_table :users do |t|
      t.references :organization, null: false, foreign_key: { on_delete: :cascade }, index: true
      t.string :email, null: false
      t.string :role, null: false, default: "author"
      t.timestamps
    end
    add_index :users, [:organization_id, :email], unique: true

    create_table :articles do |t|
      t.references :user, null: false, foreign_key: true, index: true
      t.string :title, null: false
      t.text :body
      t.integer :status, default: 0, null: false
      t.integer :view_count, default: 0, null: false
      t.datetime :published_at
      t.timestamps
    end
    add_index :articles, :status
    add_index :articles, :published_at

    create_table :tags do |t|
      t.string :name, null: false
      t.timestamps
    end
    add_index :tags, :name, unique: true

    create_table :article_tags do |t|
      t.references :article, null: false, foreign_key: { on_delete: :cascade }
      t.references :tag, null: false, foreign_key: { on_delete: :restrict }
      t.timestamps
    end
    add_index :article_tags, [:article_id, :tag_id], unique: true
  end
end
```

### 2. Definisi Model Active Record

```ruby
# app/models/organization.rb
class Organization < ApplicationRecord
  has_many :users, dependent: :destroy
  has_many :articles, through: :users

  validates :name, presence: true
  validates :slug, presence: true, uniqueness: { case_sensitive: false }
end

# app/models/user.rb
class User < ApplicationRecord
  belongs_to :organization
  has_many :articles, dependent: :destroy

  enum :role, { author: "author", editor: "editor", admin: "admin" }, validate: true

  validates :email, presence: true, format: { with: URI::MailTo::EMAIL_REGEXP }
  validates :email, uniqueness: { scope: :organization_id, case_sensitive: false }
end

# app/models/tag.rb
class Tag < ApplicationRecord
  has_many :article_tags, dependent: :destroy
  has_many :articles, through: :article_tags

  validates :name, presence: true, uniqueness: { case_sensitive: false }
end

# app/models/article_tag.rb
class ArticleTag < ApplicationRecord
  belongs_to :article
  belongs_to :tag

  validates :tag_id, uniqueness: { scope: :article_id }
end

# app/models/article.rb
class Article < ApplicationRecord
  belongs_to :user
  has_one :organization, through: :user
  has_many :article_tags, dependent: :destroy
  has_many :tags, through: :article_tags

  enum :status, { draft: 0, under_review: 1, published: 2, archived: 3 }

  validates :title, presence: true, length: { maximum: 255 }
  validates :status, presence: true

  scope :published, -> { where(status: :published).where("published_at <= ?", Time.current) }
  scope :recent, -> { order(published_at: :desc) }
  scope :by_tag, ->(tag_name) { joins(:tags).where(tags: { name: tag_name }) }

  def publish!
    transaction do
      update!(status: :published, published_at: Time.current)
    end
  end
end
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Migrasi (`CreateCorePublishingSchema`)
- `add_index :organizations, :slug, unique: true`: Mencegah duplikasi slug pada tingkat storage engine PostgreSQL.
- `foreign_key: { on_delete: :cascade }`: Menjaga integritas data jika organisasi dihapus, maka seluruh data pengguna di bawah organisasi tersebut otomatis terhapus langsung oleh engine database, bukan satu per satu oleh Ruby VM.
- `add_index :users, [:organization_id, :email], unique: true`: Indeks komposit (*composite index*) untuk menegakkan multi-tenancy: Pengguna yang sama tidak boleh terdaftar ganda di organisasi yang sama.
- `foreign_key: { on_delete: :restrict }` pada `article_tags`: Mencegah penghapusan `Tag` jika tag tersebut masih dikaitkan dengan satu atau lebih artikel aktif.

### Analisis Definisi Model
- `has_many :articles, through: :users`: Relasi bertingkat (*nested association*). Memungkinkan pengambilan artikel milik suatu organisasi secara langsung (`organization.articles`) melalui join implisit pada tabel `users`.
- `enum :status, { draft: 0, under_review: 1, ... }`: Menggunakan pemetaan integer-to-symbol. Menyimpan integer di database menghemat byte storage, namun diekspos sebagai status representatif di Ruby (`article.draft?`, `article.published!`).
- `scope :published, -> { where(...) }`: Implementasi scope dengan lambda (`->`). Lambda menjamin bahwa ekspresi `Time.current` dievaluasi secara dinamis saat kueri dieksekusi, bukan saat kelas pertama kali di-*load* ke memori saat server booting.
- `scope :by_tag, ->(tag_name) { joins(:tags).where(tags: { name: tag_name }) }`: Menggunakan mekanisme `INNER JOIN` ke tabel `article_tags` dan `tags` untuk memfilter koleksi artikel berdasarkan tag tertentu secara efisien di level SQL.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur Multi-Tenant B2B Billing & Ledger System
Perusahaan SaaS finansial B2B berskala global menangani puluhan ribu transaksi per menit. Sistem harus menangani:
1. Pembuatan faktur (*Invoicing*) dan pencatatan buku besar (*Double-entry General Ledger*).
2. Penanganan mutasi saldo kredit prabayar tenant.
3. Kebutuhan ketat: Nilai akun tidak boleh bernilai negatif (*invariance*), dan saldo tidak boleh terkorupsi oleh *concurrent balance deductions* (misalnya penagihan API otomatis yang datang secara simultan pada milidetik yang sama).

### Masalah Arsitektur:
- Pengecekan saldo naif (`if account.balance >= amount; account.update(balance: balance - amount)`) akan mengalami *race condition* (phantom read dan lost updates) saat ada concurrent requests.
- Mutasi ledger harus bersifat ACID dan tidak boleh mengandalkan perhitungan memori Ruby.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem ledger keuangan tahan banting dengan penguncian pesimis (*pessimistic locking*), constraint database murni, dan penelusuran audit immutability.

### 1. Migrasi Skema Database dengan Constraints Tingkat Lanjut

```ruby
# db/migrate/20240101000002_create_financial_ledger_engine.rb
class CreateFinancialLedgerEngine < ActiveRecord::Migration[7.1]
  def change
    create_table :ledgers do |t|
      t.string :name, null: false
      t.string :currency, limit: 3, null: false, default: "USD"
      t.timestamps
    end

    create_table :accounts do |t|
      t.references :ledger, null: false, foreign_key: true, index: true
      t.string :account_number, null: false
      t.string :account_type, null: false # asset, liability, equity, revenue, expense
      t.bigint :balance_cents, default: 0, null: false
      t.integer :lock_version, default: 0, null: false # Optimistic locking fallback
      t.timestamps
    end
    add_index :accounts, [:ledger_id, :account_number], unique: true

    # Check constraint: Saldo tidak boleh negatif untuk tipe akun aset tertarget
    add_check_constraint :accounts, "balance_cents >= 0", name: "check_account_balance_non_negative"

    create_table :journal_entries do |t|
      t.references :ledger, null: false, foreign_key: true
      t.string :reference_id, null: false
      t.text :description
      t.datetime :posted_at, null: false
      t.timestamps
    end
    add_index :journal_entries, :reference_id, unique: true

    create_table :ledger_lines do |t|
      t.references :journal_entry, null: false, foreign_key: true
      t.references :account, null: false, foreign_key: true
      t.bigint :amount_cents, null: false # Positif untuk Debit, Negatif untuk Kredit
      t.timestamps
    end
    add_index :ledger_lines, [:journal_entry_id, :account_id]
  end
end
```

### 2. Implementasi Model & Service Mutasi Atomik

```ruby
# app/models/ledger.rb
class Ledger < ApplicationRecord
  has_many :accounts, dependent: :restrict_with_exception
  has_many :journal_entries, dependent: :restrict_with_exception

  validates :currency, length: { is: 3 }
end

# app/models/account.rb
class Account < ApplicationRecord
  belongs_to :ledger
  has_many :ledger_lines, dependent: :restrict_with_error

  enum :account_type, {
    asset: "asset",
    liability: "liability",
    equity: "equity",
    revenue: "revenue",
    expense: "expense"
  }

  validates :account_number, presence: true
  validates :balance_cents, numericality: { greater_than_or_equal_to: 0 }
end

# app/models/journal_entry.rb
class JournalEntry < ApplicationRecord
  belongs_to :ledger
  has_many :ledger_lines, inverse_of: :journal_entry, dependent: :destroy

  validates :reference_id, presence: true, uniqueness: true
  validate :must_be_balanced

  accepts_nested_attributes_for :ledger_lines

  private

  def must_be_balanced
    total = ledger_lines.sum { |line| line.amount_cents.to_i }
    return if total.zero?

    errors.add(:base, "Entri buku besar tidak seimbang (Unbalanced). Selisih delta: #{total} cents.")
  end
end

# app/models/ledger_line.rb
class LedgerLine < ApplicationRecord
  belongs_to :journal_entry
  belongs_to :account

  validates :amount_cents, numericality: { other_than: 0 }
end
```

### 3. Core Engine: Transaksi Transfer Atomik Bebas Deadlock

```ruby
# app/services/ledger_transaction_service.rb
class LedgerTransactionService
  class InsufficientFundsError < StandardError; end
  class AccountMismatchError < StandardError; end

  def self.transfer(ledger:, source_account:, destination_account:, amount_cents:, reference_id:, description:)
    new(ledger, source_account, destination_account, amount_cents, reference_id, description).execute
  end

  def initialize(ledger, source_account, destination_account, amount_cents, reference_id, description)
    @ledger = ledger
    @source_account = source_account
    @destination_account = destination_account
    @amount_cents = Integer(amount_cents)
    @reference_id = reference_id
    @description = description
  end

  def execute
    raise ArgumentError, "Jumlah transfer harus bernilai positif" if @amount_cents <= 0
    validate_ledger_association!

    # PENCEGAHAN DEADLOCK: Urutkan ID akun saat mengunci baris (Row-Level Locking)
    ordered_account_ids = [@source_account.id, @destination_account.id].sort

    ActiveRecord::Base.transaction(isolation: :serializable) do
      # 1. Pessimistic Locking: SELECT FOR UPDATE berdasarkan ID terurut
      locked_accounts = Account.where(id: ordered_account_ids).order(:id).lock("FOR UPDATE").index_by(&:id)

      locked_source = locked_accounts[@source_account.id]
      locked_dest = locked_accounts[@destination_account.id]

      # 2. Verifikasi Saldo di dalam isolasi transaksi
      if locked_source.balance_cents < @amount_cents
        raise InsufficientFundsError, "Saldo akun #{@source_account.account_number} tidak mencukupi."
      end

      # 3. Mutasi Saldo secara atomik
      locked_source.balance_cents -= @amount_cents
      locked_dest.balance_cents += @amount_cents

      locked_source.save!
      locked_dest.save!

      # 4. Buat Audit Trail Journal Entry (Immutability)
      entry = @ledger.journal_entries.build(
        reference_id: @reference_id,
        description: @description,
        posted_at: Time.current
      )

      # Aturan Akuntansi: Debit mengurangi kredit/mengubah aset, kredit meningkatkan aset
      entry.ledger_lines.build(account: locked_source, amount_cents: -@amount_cents)
      entry.ledger_lines.build(account: locked_dest, amount_cents: @amount_cents)

      entry.save!
      entry
    end
  rescue ActiveRecord::RecordNotUnique
    raise ArgumentError, "Transaksi dengan ID referensi '#{@reference_id}' telah diproses."
  end

  private

  def validate_ledger_association!
    return if @source_account.ledger_id == @ledger.id && @destination_account.ledger_id == @ledger.id

    raise AccountMismatchError, "Akun-akun yang terlibat harus berada di bawah Ledger yang sama."
  end
end
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### 1. Active Record Pattern vs. Data Mapper Pattern (Sequel/ROM-rb)

| Dimensi Parameter | Active Record (Rails) | Data Mapper (ROM-rb / Sequel) |
| :--- | :--- | :--- |
| **Kecepatan Pengembangan** | Ekstrem cepat. CRUD otomatis tanpa konfigurasi mapping. | Lebih lambat pada tahap inisiasi (*boilerplate* tinggi). |
| **Separation of Concerns** | Rendah. Objek memegang domain logic dan DB storage logic. | Sangat Tinggi. Entities adalah *Plain Old Ruby Objects* (PORO). |
| **Domain Logic Kompleks** | Rentan bloat (*God Objects*) jika arsitektur Service/Concern buruk. | Sangat bersih; pemetaan database diisolasi dari aturan bisnis. |
| **Overhead Memori** | Tinggi. Model mengemas metadata, dynamic attributes, dirty tracking. | Sangat Rendah. Alokasi memori efisien untuk dataset besar. |

### 2. Strategi Penguncian: Pessimistic vs. Optimistic Locking

| Pendekatan | Cara Kerja | Kapan Digunakan | Kelemahan / Trade-off |
| :--- | :--- | :--- | :--- |
| **Pessimistic Locking** (`lock("FOR UPDATE")`) | Mengunci baris database secara fisik melalui RDBMS. Thread lain harus menunggu. | Sistem Finansial, Alokasi Inventaris Tiket/Flash Sale. | Resiko deadlock tinggi bila urutan lock salah; throughput turun jika lock ditahan terlalu lama. |
| **Optimistic Locking** (`lock_version`) | Memeriksa kolom integer `lock_version` saat UPDATE; jika berubah, lempar error. | CMS, Pengeditan Profil, data dengan konflik benturan rendah. | Memerlukan penanganan manual *retry strategy* pada level aplikasi ketika terjadi `StaleObjectError`. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Phantom Read & Race Condition pada `validates_uniqueness_of`
- **Gejala:** Dua thread secara bersamaan menjalankan query `SELECT EXISTS(...)` untuk email yang sama. Keduanya menerima hasil `false`, lalu keduanya mengeksekusi `INSERT INTO users...`.
- **Dampak:** Duplikasi data lolos ke database, merusak konsistensi aplikasi.
- **Solusi Wajib:** Jangan pernah percaya hanya pada validasi Rails. Letakkan *Unique Constraint/Index* pada tingkat database (`add_index :users, :email, unique: true`).

### 2. Bahaya Eksekusi Non-Transactional Callbacks (`after_commit` vs `after_save`)
- **Gejala:** Meluncurkan Sidekiq Worker dari `after_save`:
  ```ruby
  after_save :enqueue_background_sync
  def enqueue_background_sync
    SyncWorker.perform_async(self.id)
  end
  ```
- **Pitfall:** Sidekiq worker langsung mengambil job dari Redis dan mengeksekusi kueri `User.find(id)` sebelum database menyelesaikan `COMMIT` dari transaksi induk thread Rails. Hasil: `ActiveRecord::RecordNotFound` di Sidekiq.
- **Solusi:** Selalu gunakan callback `after_commit :enqueue_background_sync, on: :create` yang menjamin job hanya diantrekan setelah database mengonfirmasi commit fisik secara tuntas.

### 3. Inconsistensi Objek Memori saat Transaction Rollback
- **Gejala:** Status objek di memori Ruby VM berubah, tetapi transaksi database di-rollback:
  ```ruby
  user = User.find(1)
  ActiveRecord::Base.transaction do
    user.balance = 500
    user.save!
    raise ActiveRecord::Rollback
  end
  puts user.balance # Mengembalikan 500, padahal di DB masih bernilai lama!
  ```
- **Solusi:** Panggil `user.reload` setelah kegagalan transaksi untuk menyelaraskan kembali status memori Ruby dengan status data riil di database.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Masalah Kueri N+1 (N+1 Query Problem)
- **Kode Buruk:**
  ```ruby
  # Controller
  @articles = Article.limit(100)

  # View
  <% @articles.each do |article| %>
    <%= article.user.email %> <!-- Menembak 1 kueri baru per baris (1 + 100 kueri) -->
  <% end %>
  ```
- **Kode Benar:**
  ```ruby
  # Controller
  @articles = Article.includes(:user).limit(100) # Hanya 2 Kueri SQL dieksekusi
  ```

### 2. Modifikasi Atribut dalam Callback `after_save`
- **Kode Buruk:**
  ```ruby
  class Invoice < ApplicationRecord
    after_save :calculate_totals

    def calculate_totals
      self.update(total: lines.sum(:amount)) # BAHAYA: Memicu infinite loop recursive save!
    end
  end
  ```
- **Kode Benar:**
  Gunakan callback `before_save` untuk memodifikasi status internal tanpa melakukan eksekusi `update` terpisah ke database:
  ```ruby
  class Invoice < ApplicationRecord
    before_save :calculate_totals

    def calculate_totals
      self.total = lines.sum(&:amount) # Memodifikasi atribut sebelum disimpan
    end
  end
  ```

### 3. Mengabaikan Batasan `default_scope`
- **Kode Buruk:** Menggunakan `default_scope { where(deleted_at: nil) }`.
- **Dampak:** `default_scope` meresap ke seluruh asosiasi, subquery, dan administrasi database. Menghapusnya memerlukan pemanggilan `unscoped`, yang secara berbahaya juga menghapus *scoping keamanan* multi-tenancy (`current_tenant`).
- **Solusi:** Gunakan scope eksplisit bernama seperti `scope :active, -> { where(deleted_at: nil) }`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

### 1. Prinsip Skema Database (Database First Mindset)
- **Foreign Key Constraints:** Setiap relasi `belongs_to` wajib memiliki foreign key fisik (`foreign_key: true`) di database untuk mencegah data yatim (*orphaned records*).
- **Nullability Enforcers:** Jangan biarkan kolom opsional jika bisnis menghendakinya wajib. Gunakan `null: false` pada tingkat migrasi bersamaan dengan `validates :attribute, presence: true`.

### 2. Pemisahan Tanggung Jawab (Separation of Concerns)
- **Thin Models, Clean Architecture:** Jangan menumpuk integrasi pihak ketiga, pengiriman email, atau parsing file CSV rumit ke dalam class `ActiveRecord::Base`. Model murni hanya bertanggung jawab atas validasi data, relasi asosiasi, dan kalkulasi status internal.
- **Pindahkan Alur Kerja ke Service Objects:** Seperti contoh `LedgerTransactionService` pada Seksi 10, gunakan Service Object untuk orkestrasi mutasi multi-model.

### 3. Zero-Downtime Safe Migrations
- Jika menambahkan kolom dengan nilai default pada database PostgreSQL versi < 11, jangan langsung menggunakan `default: value` bersamaan dengan `add_column` karena ini mengunci seluruh tabel. (PostgreSQL 11+ sudah mendukung penambahan kolom ber-default secara aman dan instan).
- Untuk indeks pada tabel besar, gunakan `algorithm: :concurrently`:
  ```ruby
  class AddIndexToOrdersPlacedAt < ActiveRecord::Migration[7.1]
    disable_ddl_transaction!

    def change
      add_index :orders, :placed_at, algorithm: :concurrently
    end
  end
  ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Batch Processing untuk Data Skala Besar
Jangan pernah memanggil `.all.each` pada dataset yang berisi jutaan baris karena Ruby VM akan mengalokasikan seluruh baris tersebut ke RAM, memicu *Out Of Memory (OOM) Killer*.

```ruby
# SALAH: Meledakkan memori
User.where(active: true).each do |user|
  user.generate_compliance_report!
end

# BENAR: Mengambil data per batch (default 1000 baris per kueri) menggunakan kursor ID
User.where(active: true).find_each(batch_size: 1000) do |user|
  user.generate_compliance_report!
end
```

### 2. Strict Loading (Rails 6.1+)
Cegah masalah kueri N+1 secara permanen pada level kode pengujian dan pengembangan dengan mengaktifkan `strict_loading`:

```ruby
class User < ApplicationRecord
  has_many :articles, strict_loading: true
end

# Atau pada level kueri individual:
user = User.strict_loading.first
user.articles.to_a # Akan melempar ActiveRecord::StrictLoadingViolationError
```

### 3. Counter Cache untuk Mengurangi Agregasi Berulang
Hindari `COUNT(*)` berulang yang lambat:

```ruby
# Migrasi
add_column :users, :articles_count, :integer, default: 0, null: false

# Model
class Article < ApplicationRecord
  belongs_to :user, counter_cache: true
end

# Penggunaan:
user.articles.size # Membaca langsung kolom articles_count tanpa menembak kueri SELECT COUNT(*)
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. SQL Injection melalui Fragment Kueri Dinamis
Active Record secara default memfilter dan melakukan escaping pada input hash. Namun, penggunaan string interpolation mentah mematikan proteksi parameter sanitasi:

```ruby
# SANGAT RENTAN (SQL Injection)
params_user_input = "admin' OR '1'='1"
User.where("username = '#{params_user_input}'")
# Menghasilkan: SELECT * FROM users WHERE username = 'admin' OR '1'='1'

# AMAN: Menggunakan Parameter Binding / Placeholders
User.where("username = ?", params_user_input)
# Atau menggunakan Hash syntax:
User.where(username: params_user_input)
```

### 2. Arel SQL Injection Vulnerability Mitigation
Mulai dari Rails 5.2+, pengiriman raw SQL ke dalam klausa selektif seperti `.order()` harus dibungkus eksplisit dengan `Arel.sql()` untuk mencegah modifikasi AST yang tidak diinginkan, namun pastikan nilainya telah di-*whitelist*:

```ruby
# AMAN: Whitelisting input pengguna sebelum diserahkan ke Arel.sql
ALLOWED_DIRECTIONS = %w[asc desc].freeze
ALLOWED_COLUMNS = %w[created_at balance title].freeze

direction = ALLOWED_DIRECTIONS.include?(params[:direction]) ? params[:direction] : "asc"
column = ALLOWED_COLUMNS.include?(params[:sort]) ? params[:sort] : "created_at"

Article.order(Arel.sql("#{column} #{direction}"))
```

### 3. Mass Assignment Defense
Jangan gunakan `update(params)` mentah. Wajib terapkan *Strong Parameters* di layer controller dan pastikan atribut sensitif (seperti `admin_flag`, `ledger_id`, `balance`) tidak diekspos ke akses eksternal.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Menggunakan SQL Query Explanation (`explain`)
Analisis eksekusi kueri PostgreSQL langsung dari Rails Console:

```ruby
# Di Rails Console
puts Article.where(status: :published).order(published_at: :desc).explain(:analyze)
```
Output ini menampilkan rencana kueri mesin database (*Execution Plan*), pemakaian indeks (*Index Scan vs Sequential Scan*), alokasi buffer, dan waktu eksekusi aktual dalam milidetik.

### 2. Bullet Gem untuk Mendeteksi Masalah Kueri Secara Realtime
Integrasikan gem `bullet` di lingkungan `development` (`config/environments/development.rb`):

```ruby
config.after_initialize do
  Bullet.enable = true
  Bullet.alert = true
  Bullet.bullet_logger = true
  Bullet.console = true
  Bullet.rails_logger = true
  Bullet.add_footer = true
end
```
Bullet memantau eksekusi runtime kueri dan segera menampilkan popup alert browser atau log peringatan jika mendeteksi kueri N+1 atau *unused eager loading* (melakukan `includes` namun tidak digunakan).

### 3. ActiveSupport Instrumentation untuk Query Auditing
Dengarkan event kueri internal untuk metrik sistem:

```ruby
ActiveSupport::Notifications.subscribe("sql.active_record") do |name, start, finish, id, payload|
  duration = (finish - start) * 1000 # Durasi dalam milidetik
  if duration > 200 # Log kueri lambat yang melampaui 200ms
    Rails.logger.warn("[SLOW QUERY WARNING] (#{duration.round(2)}ms) - SQL: #{payload[:sql]}")
  end
end
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Perintah Penting Active Record

| Operasi | Sintaks | Fungsi |
| :--- | :--- | :--- |
| **Fetch Distinct** | `Model.select(:category).distinct` | Mengambil nilai kategori unik |
| **Safe Bulk Write** | `Model.insert_all([...])` | Menyisipkan ribuan data dalam 1 SQL Statement (Melewati validasi/callbacks) |
| **Pluck Direct** | `Model.pluck(:id, :email)` | Menarik data spesifik langsung ke Array Ruby tanpa membuat objek model |
| **Exists Check** | `Model.where(role: 'admin').exists?` | Kueri cepat `SELECT 1 AS one FROM ... LIMIT 1` yang ringan |
| **Merge Scope** | `User.joins(:articles).merge(Article.published)` | Menggabungkan scope model lain ke dalam kueri model saat ini |
| **Row Locking** | `Model.lock.find(id)` | Menjalankan `SELECT ... FOR UPDATE` untuk mencegah manipulasi paralel |

### Matriks Penggunaan Eager Loading

```
               Apakah Anda memerlukan kondisi WHERE pada tabel anak?
                                    |
                +-------------------+-------------------+
                |                                       |
              TIDAK                                     YA
                |                                       |
                v                                       v
         Gunakan: preload()                    Gunakan: eager_load()
  (Eksekusi 2 kueri terpisah;             (Eksekusi 1 kueri tunggal via
   Sangat efisien dalam memori)             LEFT OUTER JOIN tabel anak)
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Apa perbedaan fungsional utama antara metode `.count`, `.length`, dan `.size` pada `ActiveRecord::Relation`?**
   - *Jawaban:*
     - `.count`: Selalu menjalankan kueri SQL `SELECT COUNT(*) FROM ...` ke database, tidak peduli apakah data sudah dimuat ke memori atau belum.
     - `.length`: Memuat seluruh kumpulan baris menjadi array model di memori Ruby, lalu menghitung panjang array tersebut (`Array#length`).
     - `.size`: Menggunakan jalur optimasi adaptif. Jika koleksi sudah termuat di memori, ia menghitung panjang array tanpa kueri tambahan. Jika belum, ia mengeksekusi kueri `SELECT COUNT(*)`.

2. **Kapan Anda sebaiknya menggunakan `delete` vs `destroy` pada objek Active Record?**
   - *Jawaban:*
     - `destroy`: Menjalankan seluruh siklus hidup callback model (seperti `before_destroy`, `after_destroy`), menghormati dependensi relasi (`dependent: :destroy`), dan memicu validasi.
     - `delete`: Menembak langsung kueri SQL `DELETE FROM table WHERE id = ?` secara instan, memotong (*bypass*) seluruh callbacks Ruby dan validasi model.

3. **Mengapa validasi `validates :username, uniqueness: true` di model Rails tetap dapat menghasilkan data duplikat?**
   - *Jawaban:* Karena masalah *race condition* (konkurensi). Di antara proses pembacaan data (`SELECT 1`) dan penulisan (`INSERT`), thread eksekusi lain dapat menyisipkan username yang sama. Solusinya adalah melengkapi model dengan *Unique Index* di database.

4. **Bagaimana cara kerja metode `find_each` dan mengapa ia lebih aman dibandingkan metode `.all.each` pada tabel besar?**
   - *Jawaban:* `find_each` membagi pengambilan baris data menjadi sekumpulan batch kecil (secara default 1000 baris) berdasarkan urutan *Primary Key* menggunakan batas limit dan offset terindeks. Ini mencegah kehabisan memori server (*Out-of-Memory / OOM*).

5. **Apa fungsi dari metode `.pluck` dan kapan sebaiknya metode ini dipilih daripada metode `.map`?**
   - *Jawaban:* `.pluck` mengonversi kolom basis data langsung menjadi Ruby Array murni tanpa memicu inisialisasi (*instantiation*) ribuan instance objek `ActiveRecord::Base`. Ini menghemat waktu eksekusi CPU dan alokasi memori heap secara dramatis.

---

### Soal Tingkat Menengah (Intermediate)

6. **Analisis skenario berikut: Mengapa pemanggilan `after_save` yang menembakkan event ke Apache Kafka atau Sidekiq berisiko menimbulkan galat *Race Condition*, dan bagaimana cara memperbaikinya?**
   - *Jawaban:* Transaksi database belum tentu telah di-`COMMIT` saat `after_save` selesai dieksekusi. Jika Sidekiq atau Kafka consumer memproses event sebelum commit database rampung, data record belum terlihat oleh koneksi worker lain. Solusinya: Ubah menjadi callback `after_commit, on: [:create, :update]`.

7. **Jelaskan perbedaan mendasar mekanisme join antara `.joins()` dan `.left_outer_joins()` dalam Active Record!**
   - *Jawaban:* `.joins()` mengeksekusi `INNER JOIN`, yang menyaring dan hanya menampilkan baris model induk yang memiliki pasangan kecocokan di tabel anak. Sebaliknya, `.left_outer_joins()` menyertakan seluruh baris model induk terlepas dari apakah mereka memiliki asosiasi pada tabel anak atau tidak (nilai atribut anak bernilai `NULL`).

8. **Apa yang menyebabkan terjadinya kebocoran memori (*memory bloat*) pada penggunaan `ActiveRecord::Relation` yang dirangkai secara berlebihan di dalam proses cron/background worker yang berjalan terus menerus?**
   - *Jawaban:* Objek `ActiveRecord::Relation` meng-cache hasil kueri di variabel internal `@records`. Jika instance scope atau relasi dipertahankan dalam variabel global atau kelas (*class variable/memoization*) pada proses berumur panjang, memori tidak akan pernah dibebaskan oleh *Ruby Garbage Collector (GC)*.

9. **Diberikan dua model: `Author` dan `Book`. Bagaimana cara menuliskan kueri Active Record untuk mengambil semua `Author` yang belum memiliki `Book` sama sekali tanpa menggunakan raw SQL?**
   - *Jawaban:*
     ```ruby
     Author.where.missing(:books)
     # Atau pendekatan klasik:
     Author.left_outer_joins(:books).where(books: { id: nil })
     ```

10. **Bagaimana cara kerja mekanisme `lock("FOR UPDATE")` pada tingkat RDBMS PostgreSQL dan apa dampaknya jika transaksi berlangsung lama (*long-running transaction*)?**
    - *Jawaban:* RDBMS menempatkan kunci eksklusif (*Exclusive Row-Level Lock*) pada baris-baris yang terpilih hingga transaksi memanggil `COMMIT` atau `ROLLBACK`. Transaksi lain yang mencoba mengakses atau memodifikasi baris tersebut akan diblokir (*blocking/wait*). Jika transaksi berlangsung lama, hal ini akan menghabiskan batas *connection pool*, meningkatkan latensi aplikasi, dan berpotensi memicu *Cascading Connection Starvation*.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: High-Concurrency Flash Sale Inventory Engine

### Deskripsi Skenario:
Anda ditugaskan merancang subsistem inventaris untuk produk berstatus *flash sale*. Sebanyak 5.000 pengguna akan menekan tombol "Beli" secara simultan dalam jendela waktu 5 detik untuk memperebutkan stok produk yang hanya berjumlah 50 item.

### Kebutuhan Teknis Sistem:
1. **Pencegahan Overselling:** Stok inventaris tidak boleh bernilai negatif dalam keadaan apa pun (*Invariance Constraint*).
2. **Strict Concurrency Control:** Wajib mengimplementasikan *Pessimistic Locking* pada pemilihan dan pembaruan alokasi stok.
3. **Idempotency Guarantee:** Permintaan berulang dari pengguna yang sama (akibat jaringan lambat dan penekanan tombol berkali-kali) hanya boleh berhasil memotong stok sebanyak satu kali.
4. **Audit Immutability:** Setiap reservasi harus menghasilkan baris `InventoryReservation` dengan status `pending`, `confirmed`, atau `cancelled`.
5. **Zero Data Leakage:** Gunakan database constraints untuk memvalidasi batasan kuantitas selain validasi model Ruby.

### Spesifikasi Skema Database yang Harus Dibuat:
- Tabel `products` (`id`, `name`, `total_stock`, `available_stock`).
- Tabel `inventory_reservations` (`id`, `product_id`, `user_id`, `idempotency_key`, `quantity`, `status`).
- Check constraint PostgreSQL pada `products`: `available_stock >= 0`.
- Unique Index pada `inventory_reservations`: `[:product_id, :idempotency_key]`.

### Tugas yang Harus Diselesaikan:
1. Tulis migrasi Rails yang lengkap dengan seluruh index dan check constraints database PostgreSQL.
2. Bangun model `Product` dan `InventoryReservation` dengan relasi yang tepat.
3. Bangun Service Object `ReserveInventoryService` yang menerima parameter `(product_id:, user_id:, quantity:, idempotency_key:)`.
4. Bungkus mutasi di dalam transaksi database serializable/pessimistic lock menggunakan `lock("FOR UPDATE")`.
5. Tulis skrip pengujian konkurensi mini menggunakan thread Ruby (`10.times.map { Thread.new { ... } }`) untuk membuktikan bahwa tidak terjadi *overselling* saat beberapa thread bersaing memperebutkan sisa stok terakhir.

Modul ini membekali Anda dengan landasan solid Active Record tingkat produksi, berfokus pada kebenaran data, keandalan transaksional, dan efisiensi query tingkat tinggi. Terapkan prinsip-prinsip ini secara konsisten dalam setiap rancangan basis data sistem enterprise.