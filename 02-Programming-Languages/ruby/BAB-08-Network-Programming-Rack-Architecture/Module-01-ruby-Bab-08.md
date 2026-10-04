# Bab 08: Metaprogramming & Dynamic Ruby
## Module 01: Dynamic Method Definition, Dynamic Dispatch, dan Runtime Introspection

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda memiliki kemampuan praktis terukur untuk:
*   Mendesain dan mengimplementasikan mekanisme **dynamic dispatching** yang aman menggunakan `public_send` dan memvalidasi message input untuk mencegah eksekusi kode arbitrer (*Remote Code Execution / Arbitrary Method Call*).
*   Melakukan sintesis metode dinamis runtime menggunakan `define_method` berbasis *lexical scope closures* dengan mitigasi terhadap *memory bloat*.
*   Mengimplementasikan pola dynamic fallback menggunakan `method_missing` yang dipasangkan secara atomik dengan `respond_to_missing?` sesuai kontrak internal Ruby Object Model.
*   Mengisolasi modifikasi *Open Classes* (*monkey patching*) menggunakan `Refinements` guna mencegah pencemaran global (*scope leakage*) pada aplikasi multithreaded.
*   Menganalisis dan mengukur dampak manipulasi runtime terhadap *YARV Global Method Cache* dan *Callsite Inline Caching*.

---

### 2. Prerequisite
Untuk memahami modul ini secara komprehensif, Anda wajib menguasai:
*   **Ruby Object Model**: Hirarki `BasicObject`, `Object`, `Module`, `Class`, serta konsep *Singleton Class* (*Eigenclass/Metaclass*).
*   **Closures**: Mekanisme leksikal `Block`, `Proc`, dan `Lambda`, termasuk bagaimana variable binding (`Binding`) ditahan di memori.
*   **Method Lookup Chain**: Urutan resolusi metode Ruby (`Class` $\rightarrow$ `Prepended Modules` $\rightarrow$ `Superclass` $\rightarrow$ `Included Modules`).

---

### 3. Concept
Ruby adalah bahasa berorientasi objek dinamis murni di mana kelas (*classes*) adalah objek kelas satu (*first-class objects*) yang dapat dimodifikasi kapan saja selama siklus hidup runtime. Metaprogramming di Ruby mengacu pada kemampuan program untuk menulis, memodifikasi, dan menginspeksi kodenya sendiri saat berjalan (*runtime code synthesis*).

Secara internal pada implementasi CRuby (YARV - *Yet Another Ruby VM*), sebuah method call bukanlah eksekusi fungsi langsung dengan offset statis, melainkan pengiriman pesan (*message passing*). Setiap kali suatu objek menerima pesan, VM melakukan traversal terhadap tabel metode (`m_tbl`) yang tersimpan di dalam struktur data C internal kelas (`RClass`).

```
Panggilan Objek: receiver.process(payload)
      |
      v
Message Passing: Mengirim pesan :process ke receiver
```

Ketika metaprogramming diterapkan:
1.  **Dynamic Dispatch (`send` / `public_send`)**: Memungkinkan evaluasi pesan yang dikirim ke penerima ditentukan pada runtime melalui sebuah `Symbol` atau `String`, melewati fase resolusi kode statis.
2.  **Runtime Method Definition (`define_method`)**: Menyisipkan entry metode baru langsung ke dalam `m_tbl` milik kelas target menggunakan blok (`Proc`). Ini mempertahankan lingkungan leksikal (*outer scope variables*) saat blok dideklarasikan.
3.  **Dynamic Fallback (`method_missing`)**: Mengintersep siklus lookup metode tepat sebelum VM melempar eksepsi `NoMethodError`. Jika metode tidak ditemukan di sepanjang rantai `ancestors`, VM memicu panggilan internal ke `method_missing`.
4.  **Scoped Monkey Patching (`Refinements`)**: Memodifikasi behavior kelas target secara lokal pada modul atau file tertentu, mencegah efek samping tak terduga pada thread atau dependensi lain (*monkey patch pollution*).

Setiap mutasi runtime pada kelas berpotensi menginvalidasi *Inline Cache (IC)* dan *Global Method Cache (GMC)* di YARV, yang memaksa VM mengulang traversal lookup metode dari awal pada callsite berikutnya.

---

### 4. Why
Di lingkungan produksi skala enterprise, metaprogramming memberikan keuntungan:
*   **Eliminasi *Boilerplate Code***: Menghilangkan ribuan baris kode repetitif (misalnya serialisasi data, pemetaan skema database ke atribut kelas seperti pada ActiveRecord).
*   **Desain Declarative DSL (Domain-Specific Language)**: Mengizinkan pembuatan API internal yang ekspresif, intuitif, dan mendekati spesifikasi bisnis alami (seperti konfigurasi routing, job worker, atau state machine).
*   **Ekstensibilitas Runtime Tanpa Hardcoupling**: Mengintegrasikan sistem plugin atau driver dinamis yang dapat memuat kapabilitas fungsional baru berdasarkan manifest konfigurasi runtime tanpa me-restart arsitektur inti.

Tanpa pemahaman sistem internal:
*   Penyalahgunaan `send` menggunakan input dari HTTP request dapat memicu pembajakan alur eksekusi aplikasi (misalnya memanggil `instance_eval`, `exit`, atau private lifecycle hooks).
*   Penggunaan `define_method` di dalam loop tanpa kontrol scope dapat menahan referensi objek besar di memori (*memory leak via closure retention*).

---

### 5. What
Komponen kunci metaprogramming di Ruby mencakup:

*   **`send(symbol, *args, &block)`**: Mengirim pesan ke objek dan mengeksekusi metode yang cocok, **mengabaikan** visibilitas metode (`public`, `protected`, maupun `private`).
*   **`public_send(symbol, *args, &block)`**: Serupa dengan `send`, namun **menghormati** enkapsulasi visibilitas metode; melempar `NoMethodError` jika metode yang ditargetkan berstatus `private` atau `protected`.
*   **`define_method(name) { |*args| ... }`**: Metode privat pada `Module` untuk mendefinisikan instance method secara dinamis dengan body berupa blok kode.
*   **`method_missing(symbol, *args, &block)`**: Hook internal Ruby untuk menangani pesan yang tidak terdaftar dalam `m_tbl` kelas maupun rantai `ancestors`-nya.
*   **`respond_to_missing?(symbol, include_all)`**: Pasangan wajib dari `method_missing` untuk memastikan introspeksi runtime (`respond_to?`, `method()`) berjalan konsisten.
*   **`refine(klass) { ... }` dan `using(module)`**: Fitur bahasa untuk mengaplikasikan modifikasi kelas (*patch*) secara leksikal terkontrol, membatasi cakupan mutasi agar tidak merembes secara global.

---

### 6. How
Berikut adalah alur eksekusi dan resolusi pesan internal pada Ruby VM:

```
[ Pemanggilan Pesan: receiver.target_method ]
                     |
                     v
   [ Periksa YARV Inline Method Cache ]
         /                      \
    (Cache Hit)             (Cache Miss)
       /                          \
[ Eksekusi C-func / ISeq ]         v
                     [ Traversal RClass ancestors ]
                                  |
               +------------------+------------------+
               |                                     |
         (Ditemukan)                           (Tidak Ada)
               |                                     |
   [ Update Inline Cache ]                           v
               |                        [ Panggil method_missing ]
   [ Eksekusi Method Body ]                          |
                                       +-------------+-------------+
                                       |                           |
                                (Ditangani)                  (Default VM)
                                       |                           |
                               [ Selesai ]             [ Raise NoMethodError ]
```

#### Alur Kerja Runtime Method Definition (`define_method`):
1. Pengembang memanggil `Module#define_method` dengan identifier (`Symbol`) dan memberikan sebuah `Block`.
2. Ruby VM membuat objek `rb_method_definition_t` bertipe `VM_METHOD_TYPE_BMETHOD`.
3. Blok dibungkus dalam sebuah struktur `Proc` yang mempertahankan *environment frame* leksikal saat itu.
4. Metode didaftarkan ke dalam hash table `m_tbl` milik target `RClass`.
5. Ruby VM menginkrementasi *global method serial number* untuk menginvalidasi seluruh inline cache terkait kelas tersebut.

---

### 7. Analogy
Bayangkan **Direct Dispatch** (pemanggilan metode biasa) sebagai menekan tombol ekstensi telepon internal yang sudah tertera nomornya di meja resepsionis gedung kantor. Sinyal langsung dialihkan ke meja tujuan dengan cepat tanpa perantara.

**Dynamic Dispatch (`public_send`)** diibaratkan seperti berbicara kepada operator resepsionis gedung: *"Tolong hubungkan saya ke divisi X"*. Operator akan mengecek apakah divisi X terdaftar dan apakah Anda memiliki izin akses publik ke sana. Jika ya, panggilan disambungkan.

**Insecure Dispatch (`send`)** seperti seseorang yang memiliki kartu master kunci darurat: dapat menyambungkan diri ke nomor privat manapun, termasuk ruang brankas keamanan yang tidak boleh diakses oleh pihak luar.

**`method_missing`** adalah petugas *Customer Escalation*. Jika penelepon menanyakan nama divisi yang sudah bubar atau tidak terdaftar, operator tidak langsung menutup telepon, melainkan mengalihkan panggilan ke petugas ini untuk mencari solusi alternatif atau mencatat log pertanyaan.

---

### 8. Diagram
Diagram berikut merepresentasikan relasi traversal pencarian metode dinamis serta interaksi antara Open Class, Refinements, dan lookup cache:

```
+-------------------------------------------------------------------------+
|                              Ruby VM Heap                               |
|                                                                         |
|   +-----------------------+              +--------------------------+   |
|   |   Lexical Context     |              |     Target RClass        |   |
|   |  (using DynamicPatch) |              |  (e.g., PaymentGateway)  |   |
|   +-----------+-----------+              +------------+-------------+   |
|               |                                       |                 |
|               | Activates                             | Contains        |
|               v                                       v                 |
|   +-----------------------+              +--------------------------+   |
|   | Refinement Method Table|              |  Standard Method Table   |   |
|   |  - :execute_securely  |              |  (m_tbl)                 |   |
|   +-----------+-----------+              |  - :process              |   |
|               |                          |  - :authenticate         |   |
|   Overrides at|callsite                  +------------+-------------+   |
|               |                                       |                 |
|               +-------------------+                   | Missing?        |
|                                   |                   v                 |
|                                   |      +--------------------------+   |
|                                   +----->|      method_missing      |   |
|                                          |  - dynamic fallback      |   |
|                                          +------------+-------------+   |
|                                                       |                 |
|                                                       v                 |
|                                          +--------------------------+   |
|                                          |   respond_to_missing?    |   |
|                                          |  - truthy/falsy audit    |   |
|                                          +--------------------------+   |
+-------------------------------------------------------------------------+
```

---

### 9. Simple Example
Contoh dasar perbedaan dispatch dan dynamic method definition:

```ruby
class Account
  def initialize(balance)
    @balance = balance
  end

  def public_balance
    "Saldo publik: #{@balance}"
  end

  private

  def secret_token
    "SEC-XYZ-998811"
  end
end

account = Account.new(100_000)

# 1. Dynamic Dispatch yang aman
method_name = :public_balance
puts account.public_send(method_name)
# => Saldo publik: 100000

# 2. Pelanggaran enkapsulasi menggunakan send
puts account.send(:secret_token)
# => SEC-XYZ-998811 (Berhasil diakses meskipun metode private)

# 3. Dynamic Dispatch menggunakan public_send mencegah pelanggaran enkapsulasi
begin
  account.public_send(:secret_token)
rescue NoMethodError => e
  puts "Proteksi Aktif: #{e.message}"
  # => Proteksi Aktif: private method `secret_token' called for #<Account:...>
end

# 4. Sintesis Dynamic Method via Module
module AuditExtension
  [:audit_login, :audit_logout].each do |action|
    define_method(action) do |user_id|
      "[#{Time.now.utc}] Audit Event: #{action} triggered for User: #{user_id}"
    end
  end
end

Account.include(AuditExtension)
puts account.audit_login(42)
# => [2026-03-30 00:00:00 UTC] Audit Event: audit_login triggered for User: 42
```

---

### 10. Practical Example
Berikut adalah implementasi deklaratif untuk sebuah micro-framework **Event-Driven Command Router** yang memetakan payload API ke handler domain secara dinamis, mengisolasi manipulasi string menggunakan `Refinements`, dan menolak eksekusi metode ilegal menggunakan whitelist reflection.

```ruby
# frozen_string_literal: true

# Modul Refinement untuk manipulasi String secara lokal
module CoreExtensions
  refine String do
    def to_snake_case
      gsub(/([A-Z]+)([A-Z][a-z])/, '\1_\2')
        .gsub(/([a-z\d])([A-Z])/, '\1_\2')
        .tr("-", "_")
        .downcase
    end
  end
end

# Modul DSL Metaprogramming untuk Command Handling
module CommandRouterDSL
  def self.included(base)
    base.extend(ClassMethods)
  end

  module ClassMethods
    def register_command(command_name, &execution_block)
      sanitized_name = command_name.to_sym
      
      # Mencegah penimpaan metode kritis
      if instance_methods.include?(sanitized_name)
        raise ArgumentError, "Command '#{sanitized_name}' sudah terdaftar!"
      end

      # Sintesis metode baru pada runtime
      define_method("handle_#{sanitized_name}", &execution_block)
      
      # Simpan ke dalam whitelist internal
      registered_commands << sanitized_name
    end

    def registered_commands
      @registered_commands ||= Set.new
    end
  end
end

class PaymentProcessor
  using CoreExtensions # Mengaktifkan Refinement hanya di scope class ini
  include CommandRouterDSL

  register_command(:credit_card) do |payload|
    { status: :success, provider: :stripe, amount: payload[:amount] }
  end

  register_command(:bank_transfer) do |payload|
    { status: :pending, provider: :swift, amount: payload[:amount] }
  end

  def dispatch(command_type_string, payload)
    # Refinement to_snake_case dipanggil secara aman di sini
    normalized_type = command_type_string.to_s.to_snake_case.to_sym

    # Guard Clause: Validasi whitelist untuk mencegah arbitrary method dispatch
    unless self.class.registered_commands.include?(normalized_type)
      return handle_unknown_command(normalized_type)
    end

    target_method = "handle_#{normalized_type}".to_sym
    
    # Eksekusi dynamic dispatch dengan enforcement visibilitas
    public_send(target_method, payload)
  end

  # Fallback handler yang atomik
  def method_missing(method_name, *args, &block)
    if method_name.start_with?("handle_")
      command = method_name.to_s.delete_prefix("handle_").to_sym
      raise ArgumentError, "Perintah #{command} tidak dikenali oleh PaymentProcessor"
    else
      super
    end
  end

  def respond_to_missing?(method_name, include_private = false)
    method_name.start_with?("handle_") || super
  end

  private

  def handle_unknown_command(command)
    { status: :error, code: 404, message: "Perintah '#{command}' belum diimplementasikan." }
  end
end

# Execution verification
processor = PaymentProcessor.new
puts processor.dispatch("CreditCard", { amount: 500_000 })
# => {:status=>:success, :provider=>:stripe, :amount=>500000}

puts processor.dispatch("VirtualAccount", { amount: 120_000 })
# => {:status=>:error, :code=>404, :message=>"Perintah 'virtual_account' belum diimplementasikan."}

# Audit introspeksi
puts processor.respond_to?(:handle_credit_card) # => true
puts processor.respond_to?(:handle_crypto_currency) # => true (via respond_to_missing?)
puts processor.respond_to?(:undefined_method_xyz) # => false
```

---

### 11. Real World Example
#### Arsitektur Skala Besar: Transisi Active Record (Shopify / GitHub)
Pada era awal Ruby on Rails, fitur seperti Dynamic Finders (`find_by_first_name_and_city(...)`) dieksekusi murni via `method_missing`.

```
[ Request Masuk: User.find_by_email(val) ]
                   |
                   v
[ Traversal: User Class -> Superclass -> Nilai tidak ada di m_tbl ]
                   |
                   v
[ method_missing terpicu -> Parse Regexp String -> Eksekusi SQL Query ]
```

##### Permasalahan di Skala Jutaan Request per Detik:
1.  **Cache Thrashing**: Pemanggilan `method_missing` menyebabkan kegagalan pencarian YARV Inline Method Cache secara persisten. VM harus menyisir setiap rantai pewarisan modul (`ActiveRecord::Base`, dsb.) pada *setiap* request.
2.  **String Parsing Overhead**: Parsing regex pada nama metode di setiap siklus eksekusi membuang cycle CPU.

##### Solusi Arsitektural Modern:
Pada versi Rails modern, implementasi diubah menjadi strategi **Lazy Dynamic Synthesis**:
Saat pemanggilan dynamic finder pertama kali terjadi via `method_missing`:
1. Nama dan signature divalidasi.
2. Parser menyusun kode metode yang optimal.
3. Mesin memanggil `define_method` (atau `class_eval`) untuk menanam metode baru secara permanen di class proxy.
4. Panggilan subsequent untuk metode tersebut akan langsung terkena *Inline Cache Hit*, melewati `method_missing` sepenuhnya. Throughput naik hingga lebih dari 300% pada level abstraksi ORM.

---

### 12. Trade-offs

| Aspek | Dynamic Metaprogramming | Static Explicit Declaration |
| :--- | :--- | :--- |
| **Keringkasan Kode (DRY)** | **Sangat Tinggi**: Mengurangi ratusan baris boilerplate class/method. | **Rendah**: Membutuhkan penulisan metode eksplisit satu per satu. |
| **Debuggability** | **Sulit**: Stack trace tidak menunjuk ke baris kode fisik tertentu, melainkan ke blok pembungkus metaprogramming. | **Sangat Mudah**: Baris kode langsung merepresentasikan lokasi error fisik di file. |
| **Analisis Statis & IDE Tooling** | **Buruk**: Sorbet, Steep, Solargraph, dan RuboCop kesulitan melakukan type inference tanpa *RBI files* atau plugin khusus. | **Sempurna**: Static analyzer dapat membaca signatures, arity, dan types tanpa kompilasi/eksekusi runtime. |
| **Performa (Throughput)** | **Rentan Bottleneck**: Sering memicu cache de-optimization jika metadata kelas terus bermutasi di tengah runtime. | **Optimal**: Memungkinkan VM memanfaatkan inline caching dan JIT compiler (MJIT/YJIT) secara agresif. |
| **Kompleksitas Kognitif** | **Tinggi**: Membutuhkan pemahaman mendalam tentang siklus hidup Ruby VM dan scoping. | **Rendah**: Alur logika linear dan mudah dipahami oleh engineer level junior. |

---

### 13. When To Use
*   Ketika membangun framework internal, driver middleware, atau library abstraksi infrastruktur (misalnya: database adapter, custom RPC client).
*   Ketika merancang Domain-Specific Language (DSL) deklaratif untuk konfigurasi kompleks yang harus mudah dibaca oleh non-engineer atau business logic author.
*   Ketika memproses API pihak ketiga yang memiliki ratusan endpoint identik dengan skema request/response serupa, sehingga pembuatan fungsi otomatis via iterasi metadata adalah solusi terbaik.

---

### 14. When NOT To Use
*   Pada domain model yang bersifat strictly-typed atau core transaction ledger (misalnya: Core Accounting Engine), di mana prediktabilitas pemanggilan kode jauh lebih berharga daripada keringkasan syntax.
*   Pada *tight loops* atau alur komputasi mikroperforma di mana setiap latency nanodetik sangat krusial. Metaprogramming dapat mengacaukan optimasi JIT (YJIT).
*   Sebagai pengganti pola desain Object-Oriented standar (seperti Strategy, Command, atau Visitor Pattern). Jangan gunakan metaprogramming jika polymorphism sederhana sudah cukup menyelesaikan masalah.

---

### 15. Common Mistakes
1.  **Menggunakan `send` untuk Memetakan Parameter HTTP Secara Mentah**:
    ```ruby
    # SANGAT BERBAHAYA (Arbitrary Method Execution / Remote Code Execution)
    # Client mengirim: params[:action] = "instance_eval"
    def execute_user_action
      current_user.send(params[:action], params[:payload])
    end
    ```
2.  **Lupa Mengimplementasikan `respond_to_missing?`**:
    Meng-override `method_missing` tanpa `respond_to_missing?` merusak prinsip introspeksi. Panggilan `object.respond_to?(:metode_dinamis)` akan mengembalikan `false`, membingungkan ekosistem library pihak ketiga.
3.  **Closure Retention Leak**:
    Mendefinisikan metode dinamis menggunakan blok yang menangkap referensi objek besar yang tidak lagi dibutuhkan:
    ```ruby
    def generate_methods
      huge_blob_data = load_gigantic_dataset # Objek 500MB
      
      # Metrik ini akan menahan huge_blob_data di memori selamanya (GC tidak bisa membersihkannya)
      self.class.define_method(:get_status) do
        "Status: Active" # huge_blob_data tetap tertahan dalam lexical binding!
      end
    end
    ```
4.  **Monkey Patching Global Tanpa Batasan (*Scope Pollution*)**:
    Membuka kelas bawaan Ruby (`String`, `Array`, `Hash`) dan menambahkan metode secara global tanpa menggunakan `Refinements`. Dependensi library lain yang mengasumsikan interface standar akan crash atau mengalami *race condition behavior*.

---

### 16. Best Practices (Production Checklist)
*   [ ] **Gunakan `public_send` Secara Default**: Jangan gunakan `send` kecuali Anda sedang menulis unit testing untuk private methods atau assertion framework internals.
*   [ ] **Wajib Whitelist**: Selalu cocokkan input dynamic dispatch dengan whitelist bertipe `Set` atau `Array` sebelum dipassing ke `public_send`.
*   [ ] **Pasangkan `method_missing` dan `respond_to_missing?` Secara Atomik**: Pastikan parameter `include_private` selalu diteruskan ke `super`.
*   [ ] **Hindari Runtime Re-definitions**: Kumpulkan seluruh sintesis metode dinamis (`define_method`) pada fase *boot/initialization* aplikasi. Hindari mendefinisikan metode di tengah-tengah alur request HTTP.
*   [ ] **Gunakan Refinements**: Isolasi semua mutasi open class di dalam namespace lokal modul untuk menjamin isolasi dependensi.
*   [ ] **Monitor Garbage Collection dan Inline Cache Miss**: Gunakan `RubyVM.stat` pada lingkungan staging untuk mendeteksi apakah kode metaprogramming memicu degradasi global cache secara konstan.

---

### 17. Troubleshooting
*   **Investigasi `NoMethodError` Misterius pada Dynamic Fallback**:
    *   *Penyebab*: `method_missing` Anda tidak memanggil `super` di percabangan akhir, menyebabkan error tertelan atau menghasilkan exception yang salah.
    *   *Solusi*: Pastikan branch `else` pada `method_missing` selalu memanggil `super`.
*   **Debugging Stack Trace yang Hilang**:
    *   *Penyebab*: `define_method` menyembunyikan nama file dan nomor baris implementasi asli.
    *   *Solusi*: Gunakan `method(:target).source_location` untuk menemukan baris kode exact di mana blok `define_method` dideklarasikan:
        ```ruby
        p processor.method(:handle_credit_card).source_location
        # => ["/app/services/payment_processor.rb", 42]
        ```
*   **Memory Footprint Meningkat Tajam (*Memory Leak*)**:
    *   *Penyebab*: Closure pada `define_method` menahan variabel lokal yang besar.
    *   *Solusi*: Gunakan kelas pembantu (*method definition helper*) yang terisolasi dari variabel lokal besar untuk membersihkan leksikal binding sebelum memanggil `define_method`.

---

### 18. Exercise
**Instruksi Penugasan**:
Bangun sebuah modul bernama `SanitizedAttributes` yang bertindak sebagai micro-attribute validator.
1. Modul harus memiliki method level kelas `define_sanitized_attr(attr_name, sanitizer_type)`.
2. Sanitizer type yang didukung adalah `:string_strip` (menghapus whitespace depan/belakang) dan `:integer_positive` (mengubah input ke integer, jika negatif ubah menjadi `0`).
3. Modul harus mendefinisikan getter dan setter dinamis untuk `attr_name`.
4. Jika `sanitizer_type` tidak terdaftar, lemparkan `ArgumentError`.
5. Pastikan setter menggunakan dynamic method definition dan tidak membiarkan nilai invalid lolos.

```ruby
# Tulis implementasi Anda di bawah:
module SanitizedAttributes
  # Implementasikan logika ClassMethods dan define_sanitized_attr di sini
end

# Verification:
class UserProfile
  include SanitizedAttributes

  define_sanitized_attr :username, :string_strip
  define_sanitized_attr :age, :integer_positive
end

profile = UserProfile.new
profile.username = "  johndoe  "
profile.age = -25

# Ekspektasi:
# profile.username => "johndoe"
# profile.age => 0
```

---

### 19. Challenge
**Deskripsi Skenario Nyata**:
Anda diminta merancang sistem **Dynamic Telemetry & Circuit Breaker Proxy** untuk microservice client.
1. Buat kelas `ServiceProxy` yang membungkus objek service apapun (misalnya `DatabaseClient` atau `HTTPClient`).
2. Gunakan `method_missing` dan `respond_to_missing?` untuk meneruskan seluruh pemanggilan metode target secara transparan (*transparent delegation*).
3. Namun, tambahkan aturan:
    *   Jika pemanggilan metode target memakan waktu lebih dari 100ms atau menghasilkan eksepsi, catat kegagalan tersebut (*failure counter*).
    *   Jika kegagalan pada metode tertentu mencapai 3 kali berturut-turut, *Circuit Breaker* untuk metode tersebut harus beralih ke state `:open`.
    *   Ketika circuit breaker `:open`, pemanggilan metode tersebut harus langsung melempar runtime exception `CircuitBreakerOpenError` tanpa mengeksekusi metode pada target receiver.
4. **Optimasi Performa**: Begitu sebuah metode telah dipanggil dan dievaluasi sebanyak 10 kali secara normal, buatkan wrapper metode permanen menggunakan `define_method` pada singleton class dari proxy instance tersebut guna mengoptimalkan inline cache untuk pemanggilan-pemanggilan berikutnya!

---

### 20. Summary
*   **Dynamic Dispatch** (`public_send`) mengabstraksi eksekusi logika bisnis menjadi berbasis data (*data-driven architecture*), tetapi selalu membutuhkan lapisan validasi whitelist untuk menjaga keamanan runtime.
*   **`define_method`** memungkinkan sintesis fungsionalitas kelas secara terprogram, namun memerlukan kewaspadaan tinggi terhadap *closure variable retention* yang dapat membebani Garbage Collector.
*   **`method_missing`** adalah mekanisme pertahanan terakhir (*fallback hook*). Menggunakannya tanpa menyertakan **`respond_to_missing?`** adalah anti-pattern yang merusak introspeksi Ruby Object Model.
*   **Refinements** menyelesaikan masalah historis *monkey patching* global dengan menyediakan cakupan leksikal terkontrol, memastikan modifikasi kelas inti tidak bocor ke luar modul yang membutuhkannya.
*   Metaprogramming tingkat tinggi harus diimbangi dengan pemahaman terhadap arsitektur YARV VM, khususnya mengenai implikasi invalidasi method cache dan performa eksekusi jangka panjang.