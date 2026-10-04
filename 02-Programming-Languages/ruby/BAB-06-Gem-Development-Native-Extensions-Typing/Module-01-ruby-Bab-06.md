# Bab 06 Module 01: Metaprogramming — Ruby Object Model, Eigenclass, dan Dynamic Dispatch

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
* Membedah dan menavigasi hirarki internal **Ruby Object Model** secara komputasional melalui pelacakan *ancestors chain*, pointer `klass`, dan pointer `super`.
* Mengidentifikasi, mengisolasi, dan memanipulasi **Eigenclass (Singleton Class)** untuk instansiasi perilaku objek yang independen dari definisi kelas utama.
* Mengimplementasikan teknik **Dynamic Method Dispatch** menggunakan `public_send` dan konstruksi runtime method via `define_method` secara aman (*thread-safe* & *memory-safe*).
* Mencegah eksploitasi keamanan *arbitrary method invocation* dan degradasi performa yang diakibatkan oleh *method cache invalidation* di YJIT/MRI.

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib memahami:
* Fondasi Object-Oriented Ruby: Deklarasi `class`, `module`, `include`, `extend`, dan `prepend`.
* Eksekusi blok dan closures: Perbedaan arsitektural antara `Proc`, `lambda`, dan `yield`.
* Dasar eksekusi VM C-Ruby (YARV): Konsep alokasi memori heap Ruby (`RVALUE`), *call frame stack*, dan manipulasi simbol (`Symbol` vs `String`).

---

### 3. Concept
Ruby mengimplementasikan paradigma murni *"Everything is an Object"*. Secara arsitektur, sebuah kelas di Ruby hanyalah sebuah objek dari instansiasi kelas `Class`, dan setiap modul adalah instansi dari kelas `Module`.

```
                    +--------------------+
                    |    BasicObject     |
                    +--------------------+
                              ^
                              | (super)
                    +--------------------+
                    |       Object       |
                    +--------------------+
                              ^
                              | (super)
                    +--------------------+
                    |       Module       |
                    +--------------------+
                              ^
                              | (super)
                    +--------------------+
                    |       Class        |
                    +--------------------+
```

#### Struktur Internal C-Ruby (MRI)
Pada representasi struct C di internal Ruby (misalnya `struct RClass`), setiap objek membawa dua pointer fundamental:
1. `klass` pointer: Mengarah ke kelas tempat metode objek tersebut berada.
2. `super` pointer: Terdapat pada struktur kelas, mengarah ke *superclass* dalam mata rantai pewarisan (*ancestor chain*).

#### Konsep Eigenclass (Singleton Class)
Ketika sebuah metode hanya ditambahkan pada satu objek individual (singleton method), Ruby tidak menyimpannya di kelas asli objek tersebut (karena akan berdampak pada objek lain dari kelas yang sama). Ruby menyisipkan kelas siluman (*anonymous/shadow class*) di antara objek dan kelas aslinya. Kelas ini disebut **Eigenclass**, **Singleton Class**, atau **Metaclass**.

```
[Objek Instansi] --(klass)--> [#<Class:Objek>] --(super)--> [Kelas Asli]
```

#### Algoritma Method Lookup
Ketika sebuah pesan dikirim ke objek (misalnya `receiver.process_data`):
1. VM melihat ke pointer `klass` milik receiver (memeriksa keberadaan Eigenclass).
2. Jika tidak ditemukan pada Eigenclass, VM menelusuri modul yang di-`prepend` pada kelas receiver.
3. Mencari di dalam definisi instansiasi kelas receiver.
4. Menelusuri modul yang di-`include` (dalam urutan terbalik dari penulisan `include`).
5. Bergerak ke `super` pointer menuju Superclass, mengulangi siklus modul (prepend -> class -> include).
6. Bergerak terus hingga mencapai `Object`, lalu `BasicObject`.
7. Jika tetap tidak ditemukan, VM memicu eksekusi internal `method_missing` mulai dari langkah 1 kembali.

---

### 4. Why
Dalam sistem monolitik atau framework terdistribusi berskala besar (seperti Ruby on Rails, dry-rb, atau Sidekiq), deklarasi kode secara statis menghasilkan duplikasi boilerplate ribuan baris:
* **Pengurangan Duplikasi (DRYing out codebases):** Menghindari penulisan puluhan accessor atau RPC proxy secara manual.
* **Perancangan Domain-Specific Languages (DSL):** Memungkinkan sintaksis deklaratif seperti routing Sinatra, migrasi Rails, atau state machine.
* **Dynamic Adaptation:** Menghubungkan skema basis data atau payload JSON eksternal yang berubah dinamis langsung ke antarmuka objek Ruby tanpa perlu kompilasi ulang kode.

---

### 5. What
Komponen inti yang digunakan dalam dynamic dispatch dan introspeksi objek:
* `Class#ancestors`: Mengembalikan representasi array dari mata rantai hierarki resolusi metode.
* `Object#singleton_class`: Mengakses representasi kelas siluman milik objek.
* `Object#define_singleton_method`: Mendaftarkan metode spesifik ke dalam Eigenclass objek.
* `Module#define_method`: Membuat instance method baru secara dinamis menggunakan penutupan (*closure*).
* `Object#send`: Melakukan dispatch pesan (eksekusi metode) dinamis mengabaikan enkapsulasi visibilitas (`public`, `protected`, `private`).
* `Object#public_send`: Alternatif aman dari `send` yang tetap mematuhi kontrol akses visibilitas enkapsulasi.

---

### 6. How
Alur kerja integrasi metode dinamis dan eksekusi pesan:

```
[Permintaan Masuk: :update_user]
               │
               ▼
   Validasi Allowlist Simbol
               │
      [Lolos Validasi?]
         ├── Tidak ──► [Raise SecurityError / ArgumentError]
         └── Ya
               │
               ▼
      Cek: Apakah method sudah terdefinisi? (method_defined?)
         ├── Tidak ──► [Inisialisasi Module#define_method via Closure]
         └── Ya
               │
               ▼
   Eksekusi: target.public_send(:update_user, *args)
               │
               ▼
  Resolusi Method Cache YARV / YJIT
               │
               ▼
          Return Value
```

---

### 7. Analogy
Bayangkan sebuah dokumen diplomatik (*Receiver*). 
* Ketika ada instruksi masuk (*Method Call*), kurir tidak langsung pergi ke kementerian pusat (*Class*). 
* Kurir memeriksa apakah dokumen tersebut memiliki **catatan memo tempel khusus** (*Eigenclass*) yang ditempel khusus untuk dokumen itu saja. 
* Jika instruksi ada di catatan memo tersebut, kurir mengeksekusinya. 
* Jika tidak, kurir mendatangi kantor kementerian regional (*Prepended/Included Modules* & *Class*), lalu ke kantor pusat nasional (*Superclass*), hingga kementerian luar negeri (*Object/BasicObject*).
* Menggunakan `send` seperti memberi wewenang khusus bagi agen rahasia untuk membaca memo bertanda "Rahasial/Private", sedangkan `public_send` adalah prosedur perizinan resmi yang mematuhi izin edar dokumen.

---

### 8. Diagram
Struktur memori Ruby Object Model dan relasi pointer:

```
                     +-----------------------------+
                     |        BasicObject          |
                     +-----------------------------+
                                    ^
                                    | (super)
                     +-----------------------------+
                     |           Object            |
                     +-----------------------------+
                                    ^
                                    | (super)
   +-------------------+            |
   |      Module       |------------+
   +-------------------+
             ^
             | (super)
   +-------------------+
   |       Class       |
   +-------------------+
             ^
             | (klass)
+-------------------------+      (super)      +-------------------------+
|   #<Class:User>         |------------------>|  #<Class:ActiveRecord>  |
|   (Eigenclass User)     |                   |  (Eigenclass AR::Base)  |
+-------------------------+                   +-------------------------+
             ^                                             ^
             | (klass)                                     | (super)
+-------------------------+      (super)      +-------------------------+
|          User           |------------------>|    ActiveRecord::Base   |
+-------------------------+                   +-------------------------+
             ^
             | (klass)
+-------------------------+
| user_1 = User.new       |
+-------------------------+
             ^
             | (klass)
+-------------------------+
| #<Class:#<User:0x001>>  |  (Jika singleton_method didefinisikan pada user_1)
+-------------------------+
```

---

### 9. Simple Example

```ruby
class PaymentGateway
  def process_credit_card(amount)
    "Memproses kartu kredit: $#{amount}"
  end

  def process_crypto(amount)
    "Memproses crypto: $#{amount}"
  end
end

gateway = PaymentGateway.new
method_type = "credit_card"

# 1. Dynamic Dispatch menggunakan public_send
action = "process_#{method_type}"
puts gateway.public_send(action, 100) # Output: Memproses kartu kredit: $100

# 2. Manipulasi Eigenclass
class << gateway
  def emergency_kill_switch!
    "Sistem pembayaran dimatikan secara instan untuk instansi ini."
  end
end

puts gateway.emergency_kill_switch!
# gateway_baru = PaymentGateway.new
# gateway_baru.emergency_kill_switch! => NoMethodError (Hanya ada di Eigenclass gateway)
```

---

### 10. Practical Example
Implementasi runtime dynamic accessor builder untuk Data Transfer Object (DTO) dengan dynamic dispatching aman.

```ruby
# frozen_string_literal: true

module DynamicEntity
  def self.included(base)
    base.extend(ClassMethods)
  end

  module ClassMethods
    def schema(definitions)
      @allowed_attributes = definitions.keys.map(&:to_sym)

      definitions.each do |field, expected_type|
        # Buat Getter
        define_method(field) do
          @attributes[field]
        end

        # Buat Setter dengan validasi tipe dinamis
        define_method("#{field}=") do |value|
          unless value.is_a?(expected_type)
            raise TypeError, "Mismatched Type: #{field} expects #{expected_type}, got #{value.class}"
          end

          @attributes[field] = value
        end
      end
    end

    def allowed_attributes
      @allowed_attributes || []
    end
  end

  def initialize(attributes = {})
    @attributes = {}
    assign_attributes(attributes)
  end

  def assign_attributes(params)
    params.each do |key, value|
      sym_key = key.to_sym
      unless self.class.allowed_attributes.include?(sym_key)
        raise ArgumentError, "Unknown attribute: #{key}"
      end

      # Safe Dynamic Dispatch
      public_send(:"#{sym_key}=", value)
    end
  end

  def export_state
    self.class.allowed_attributes.each_with_object({}) do |attr, hash|
      hash[attr] = public_send(attr)
    end
  end
end

class OrderPayload
  include DynamicEntity

  schema(
    order_id: String,
    total_cents: Integer,
    paid: TrueClass
  )
end

# Eksekusi
payload = OrderPayload.new(order_id: "ORD-99182", total_cents: 25000, paid: true)
puts payload.export_state
# Output: {:order_id=>"ORD-99182", :total_cents=>25000, :paid=>true}

# payload.total_cents = "Not an Integer" -> Raise TypeError: Mismatched Type
```

---

### 11. Real World Example
Studi Kasus: **Optimasi Dynamic Webhook Event Router pada Platform Pembayaran Skala Enterprise (Mirip Stripe API Event Processing)**.

```ruby
# frozen_string_literal: true

module WebhookEventHandlers
  # Namespace untuk kumpulan module event
end

class EventRouter
  ALLOWED_EVENTS = Set.new(%w[payment_succeeded payment_failed charge_refunded]).freeze

  def initialize(analytics_collector)
    @analytics = analytics_collector
  end

  def route(raw_payload)
    event_name = raw_payload[:type]
    payload_data = raw_payload[:data]

    # Validasi defensive untuk mencegah arbitrary dispatch exploit
    validate_event!(event_name)

    method_identifier = :"on_#{event_name}"

    # Lazily compile event handler jika belum terdaftar untuk efisiensi bootstrap
    ensure_handler_exists(method_identifier, event_name)

    # Eksekusi Dynamic Dispatch
    public_send(method_identifier, payload_data)
  end

  private

  def validate_event!(event_name)
    return if ALLOWED_EVENTS.include?(event_name)

    raise SecurityError, "Unregistered or malicious event type: #{event_name}"
  end

  def ensure_handler_exists(method_id, event_type)
    return if respond_to?(method_id, true)

    self.class.define_method(method_id) do |data|
      # Isolasi metrics dan logging
      @analytics.public_send(:track, event_type, data[:transaction_id])
      
      # Logika pemrosesan
      "[SUCCESS] Handled #{event_type} for #{data[:transaction_id]}"
    end
  end
end

# Simulasi Driver
class MockAnalytics
  def track(event, tx_id)
    # Background emission logic
  end
end

router = EventRouter.new(MockAnalytics.new)
result = router.route({ type: "payment_succeeded", data: { transaction_id: "TX_8812" } })
puts result
# Output: [SUCCESS] Handled payment_succeeded for TX_8812
```

---

### 12. Trade-offs

| Kategori | Dynamic Approach (`define_method`, `send`) | Static Approach (Explicit Hardcoding) |
| :--- | :--- | :--- |
| **Advantages** | Reduksi duplikasi kode, fleksibilitas integrasi, adaptasi skema instan. | Performa prediktif, optimalisasi kompilasi YJIT murni, keamanan tipe static-analysis. |
| **Disadvantages** | Sulit di-trace dengan static code analysis (misal: Solargraph/Sorbet), stack trace rumit. | *Code bloat*, tingginya *human-error* saat skema berubah. |
| **Complexity** | Kompleksitas konseptual tinggi; bergantung pada state runtime VM. | Kompleksitas rendah; eksekusi alur kerja terlihat jelas (*explicit*). |
| **Performance** | Invalidation pada *global method cache* jika disalahgunakan; alokasi memori symbol runtime. | Kecepatan optimal; YARV inline caching langsung mengenali call-site inline method. |
| **Cost** | Biaya onboarding engineer tinggi karena memerlukan keahlian mendalam arsitektur Ruby. | Biaya *maintenance* tinggi seiring meningkatnya baris kode yang terduplikasi. |

---

### 13. When To Use
* Saat merancang **Framework atau Library Engine** yang perlu mengekstrak pola berulang tanpa memaksa end-user menduplikasi struktur API.
* Pengolahan integrasi data eksternal (Database Columns, RPC calls, dynamic serialization/deserialization serializers).
* Konstruksi **DSL internal** yang declarative (misal: konfigurasi environment, migrasi, state charts).

---

### 14. When NOT To Use
* **Core Business Invariant Logic:** Logika domain bisnis esensial (seperti kalkulasi bunga bank, pemotongan saldo) harus ditulis eksplisit agar mudah diaudit.
* **Proyek dengan adopsi Static Typing Ketat (Sorbet/RBS):** Dynamic dispatch mematikan kemampuan inferensi tipe otomatis secara penuh, menimbulkan noise peringatan sintaksis.
* Ketika pemanggilan metode dipicu langsung oleh input eksternal mentah tanpa lapisan validasi allowlist/whitelist.

---

### 15. Common Mistakes
1. **Menggunakan `send` Alih-alih `public_send`:** Menggunakan `send` membuka akses method internal `private`, merusak enkapsulasi keamanan objek.
2. **Dynamic Symbol Exhaustion / Memory Leak:** Menjalankan `String#to_sym` secara serampangan dari input mentah pada dynamic dispatch. Walaupun Ruby >= 2.2 memiliki GC untuk Symbol, instansiasi method runtime yang berlebihan via `define_method` tetap meningkatkan konsumsi memori heap secara permanen.
3. **Invalidasi Global Method Cache:** Memanggil `define_method` terus-menerus di dalam perulangan request (seharusnya didefinisikan sekali di level class/boot sequence). Ini mematikan optimasi *Inline Cache* YARV dan YJIT.

---

### 16. Best Practices (Production Checklist)
* [ ] Selalu gunakan `public_send` untuk dynamic dispatch kecuali secara sadar membutuhkan akses ke method private dalam testing unit isolation.
* [ ] Lindungi target dynamic dispatch dengan allowlist (menggunakan `Set` beku / `freeze`) untuk mencegah arbitrary method execution attacks.
* [ ] Definisikan metode dinamis (`define_method`) pada fase boot/inisialisasi kelas, bukan di dalam siklus *hot path* pemrosesan request HTTP.
* [ ] Berikan override yang jelas pada `respond_to_missing?` setiap kali mengimplementasikan fallback `method_missing`.
* [ ] Sertakan benchmark performa sebelum dan sesudah menerapkan metaprogramming menggunakan `Benchmark.ips`.

---

### 17. Troubleshooting

| Gejala Masalah | Penyebab Teknis | Solusi Perbaikan |
| :--- | :--- | :--- |
| `NoMethodError` padahal method terdefinisi di class. | Objek memanggil instance method yang berada di dalam *Eigenclass* dari instance yang berbeda. | Validasi bahwa method terdaftar di class level (`Module#define_method`), bukan di `Object#define_singleton_method`. |
| YJIT lambat / Penurunan throughput drastis. | Sering terjadi *Method Cache Invalidation* karena modifikasi class atau modul saat runtime. | Pindahkan seluruh pemanggilan `define_method`, `include`, atau `alias_method` ke initializers aplikasi. |
| `ArgumentError: wrong number of arguments` dari `define_method`. | *Closure capturing* pada parameter `define_method` tidak sinkron dengan *arity* block. | Pastikan blok `define_method` menggunakan signature yang tepat, atau manfaatkan explicit splat parameter (`*args, **kwargs`). |

---

### 18. Exercise
**Instruksi Pengerjaan:**
1. Buat class `SanitizedBuilder`.
2. Implementasikan method level class `sanitize_fields(*fields)` yang secara dinamis membangun method setter khusus untuk setiap field yang didaftarkan.
3. Setter tersebut harus secara otomatis memotong (*strip*) whitespace dari input String sebelum disimpan ke instance variable `@<field>`.
4. Jika nilai yang diberikan bukan String, simpan apa adanya.

```ruby
# Kerangka Solusi
class SanitizedBuilder
  def self.sanitize_fields(*fields)
    # LENGKAPI LOGIKA DI SINI
  end
end

class UserInput < SanitizedBuilder
  sanitize_fields :username, :email
end

# Ekspektasi:
# input = UserInput.new
# input.username = "  johndoe  "
# input.username => "johndoe"
```

---

### 19. Challenge
**Deskripsi Skenario:**
Bangun sebuah kelas lightweight ORM Query Proxy bernama `StrictQueryProxy` tanpa bergantung pada library eksternal. 

**Spesifikasi Teknis:**
1. Proxy membungkus array of hashes internal:
   ```ruby
   DATA = [
     { id: 1, name: "Alice", role: "admin", active: true },
     { id: 2, name: "Bob", role: "engineer", active: false },
     { id: 3, name: "Charlie", role: "admin", active: true }
   ]
   ```
2. Saat kelas di-boot, kelas harus membaca keys dari sample data pertama dan menggunakan `define_method` untuk memproduksi filter dinamis dengan format: `find_by_<attribute>(value)` (contoh: `find_by_role("admin")`).
3. Pemanggilan `find_by_*` harus dapat di-chaining (mengembalikan instance proxy baru tanpa memutasi instance yang sedang berjalan).
4. Gunakan `public_send` untuk mengarahkan operasi filtering secara dinamis.
5. Jika atribut tidak valid dipanggil, lemparkan exception `NoMethodError`.

---

### 20. Summary
Metaprogramming di Ruby berakar langsung pada keterbukaan dan konsistensi dari **Ruby Object Model**. Seluruh hierarki method lookup dikendalikan oleh navigasi pointer internal (`klass` dan `super`) yang melintasi instansi, Eigenclass, modul yang disertakan, hingga hirarki superclass.

Dengan menguasai mekanika **Dynamic Dispatch** (`public_send`) dan sintesis runtime method (`define_method`), engineer dapat membangun arsitektur sistem yang modular, minim boilerplate, dan sangat adaptif. Namun, fleksibilitas ini memerlukan kedisiplinan rekayasa tingkat tinggi: pembatasan akses dispatcher via allowlist demi keamanan, serta penghindaran mutasi kelas pada *runtime execution path* untuk menjaga optimasi method caching mesin YARV/YJIT.