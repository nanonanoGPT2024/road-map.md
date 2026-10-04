# BAB 02: Quiz, Challenge, & Knowledge Check
**Deep-Dive Object-Oriented Design & Metaprogramming**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Resolusi Method Lookup Path dan Model Linearitas Objek
Jelaskan secara presisi algoritma resolusi *method lookup* pada MRI Ruby saat sebuah pemanggilan method (`receiver.message`) dieksekusi. Bagaimana urutan hierarki traversal dari *singleton class* (eigenclass), kelas instansiasi, modul yang di-`prepend`, modul yang di-`include`, hingga superclass dan `BasicObject`? Mengapa Ruby mendesain lookup path sebagai rantai linear (*ancestors chain*) tunggal?

### Soal 1.2: Semantik Kontekstual `instance_eval` vs `class_eval`
Bandingkan secara arsitektural penggunaan `BasicObject#instance_eval` dan `Module#class_eval` (atau `module_eval`). 
1. Objek apa yang menjadi `self` di dalam blok masing-masing?
2. Di mana *metaclass* atau *class definition scope* diarahkan ketika membuat method baru menggunakan sintaksis keyword `def` di dalam masing-masing blok tersebut?
3. Bagaimana resolusi konstanta (lexical scope lookup) dipengaruhi oleh kedua metode tersebut?

### Soal 1.3: Kontrak `method_missing` dan `respond_to_missing?`
Mengapa overriding terhadap `method_missing` **wajib** selalu disertai dengan implementasi `respond_to_missing?` dan pemanggilan `super` pada cabang unhandled message? Jelaskan implikasinya terhadap integritas reflection API (seperti `Object#respond_to?`, `Object#method`), delegasi aman, dan risiko *infinite recursion* jika integrasi fallback gagal.

### Soal 1.4: Perbedaan Runtime `define_method` vs Keyword `def`
Ditinjau dari alokasi memori dan *lexical scope*, jelaskan perbedaan mendasar antara mendefinisikan method menggunakan keyword `def` versus `Module#define_method` yang menerima blok. Kapan `define_method` mempertahankan binding lingkungan pembuatnya (*closure retention*), dan apa implikasi jangka panjangnya terhadap *Garbage Collection* (GC) pada proses yang berjalan lama?

### Soal 1.5: Mekanisme Internal `include` vs `extend`
Jelaskan apa yang terjadi pada *ancestor chain* dan struktur tabel metode (*method table*) internal saat sebuah kelas mengeksekusi `include MyModule` dibandingkan dengan `extend MyModule`. Tunjukkan bahwa `extend` sebenarnya hanyalah operasi `include` pada *singleton class* dari objek target.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Invalidasi Inline Method Cache pada YARV
MRI Ruby (YARV) menggunakan *inline method caching* (monomorphic/polymorphic call sites) dan *global method state serial* untuk mempercepat dispatch method dinamis. Jelaskan bagaimana operasi metaprogramming seperti pembukaan kelas runtime (*monkey patching*), pemanggilan `define_method` secara kontinyu, atau penggunaan `prepend` pada hot-path loop dapat merusak (*invalidate*) cache tersebut dan menurunkan performa eksekusi CPU.

### Soal 2.2: Kebocoran Ghost Method pada Proxy Pattern
Diberikan kode berikut:
```ruby
class AuditProxy
  def initialize(target)
    @target = target
  end

  def method_missing(name, *args, &block)
    puts "[AUDIT] Calling #{name}"
    @target.public_send(name, *args, &block)
  end
end

user = AuditProxy.new("Sensitive String Data")
puts user.display # Mengapa ini tidak memicu method_missing?
puts user.to_s    # Mengapa ini mencetak objek inspeksi proxy, bukan string?
```
Diagnosis mengapa method `display` dan `to_s` tidak didelegasikan ke target. Bagaimana cara merancang proxy yang sepenuhnya transparan (*blank slate architecture*) menggunakan `BasicObject` dan mitigasi terhadap method bawaan `Kernel`?

### Soal 2.3: Perilaku `super` pada `Module#prepend` dan ICLASS
Ketika sebuah modul di-`prepend` ke dalam sebuah kelas, Ruby menyisipkan *Internal Class* (`ICLASS`) ke dalam rantai inheritance sebelum kelas itu sendiri. Jika modul tersebut memiliki method `initialize` yang memanggil `super`, apa sebenarnya yang dipanggil oleh `super`? Jelaskan urutan instansiasi objek dan bagaimana state initialization dapat terganggu jika parameter `super` tidak diteruskan secara transparan.

### Soal 2.4: Anti-Pattern Class Variable (`@@`) dalam Multi-Tenant Inheritance
Perhatikan kode berikut:
```ruby
class BaseService
  @@rate_limit = 100

  def self.rate_limit
    @@rate_limit
  end
end

class TenantAService < BaseService
  @@rate_limit = 500
end

class TenantBService < BaseService
  # Mengandalkan default limit
end
```
Apa output dari `BaseService.rate_limit`, `TenantAService.rate_limit`, dan `TenantBService.rate_limit`? Jelaskan struktur internal Ruby yang menyebabkan mutasi state global ini terjadi, dan rekonstruksi kode tersebut menggunakan *Class Instance Variables* (`@rate_limit` pada singleton class) beserta inheritance hook-nya (`self.inherited`).

### Soal 2.5: Binding Hijacking dan Mutasi Konteks Privat
Bagaimana method `Kernel#binding` dapat diekspos melalui metaprogramming untuk mengakses dan memutasi variabel lokal yang didefinisikan secara leksikal di dalam sebuah method privat? Jelaskan implikasi keamanan dari exposing `binding` object dari sudut pandang *encapsulation leak* dan manipulasi state internal yang tidak terprediksi.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden OOM Akibat Metaprogramming Dynamic Serialization Engine
**Kasus:**
Sebuah platform e-commerce skala besar mengalami degradasi latency hingga akhirnya memicu *Out of Memory (OOM) Kill* berulang kali pada worker Puma setiap 4 jam. Setelah dianalisis via heap dump, ditemukan jutaan class anonim dan string method symbol yang tidak pernah di-cleanup oleh GC. Tim Anda menemukan potongan kode adapter integrasi third-party API berikut:

```ruby
class DynamicPayloadParser
  def parse(payload)
    # payload berisi format dinamis dari vendor: { "field_1283" => "value", ... }
    dynamic_klass = Class.new do
      payload.each do |key, value|
        # Membuat getter dan setter on-the-fly
        attr_accessor key.to_sym
      end
    end
    
    instance = dynamic_klass.new
    payload.each { |k, v| instance.public_send("#{k}=", v) }
    instance
  end
end
```

**Pertanyaan Diagnostik:**
1. Mengapa pembuatan `Class.new` dan pemanggilan `attr_accessor` dengan parameter symbol dinamis dalam siklus request tinggi menyebabkan memory leak tak terkendali di MRI Ruby?
2. Bagaimana representasi Symbol Table dan Method Table di level internal Ruby bekerja dalam kaitannya dengan GC pada kasus di atas?
3. Tuliskan refaktor arsitektur dari engine parsing tersebut tanpa kehilangan fleksibilitas akses method (`instance.field_name`), namun menghasilkan alokasi memori yang konstan dan GC-friendly.

---

### Skenario B: Race Condition pada DSL Configuration Engine Multi-Threaded
**Kasus:**
Aplikasi web berbasis Puma (Clustered + Multi-threaded) menggunakan custom gem internal untuk manajemen autentikasi berbasis DSL. Sesekali di bawah beban traffic tinggi (concurrency spike), request dari Tenant X secara misterius menggunakan kredensial API dan secret token milik Tenant Y, yang menyebabkan insiden keamanan data cross-tenant.

Potongan kode konfigurasi gem yang ditemukan:
```ruby
module CloudAuthenticator
  class << self
    def configure(&block)
      instance_eval(&block)
    end

    def set_credentials(tenant_id, secret)
      @tenant_id = tenant_id
      @secret = secret
    end

    def authenticate_request(payload)
      Signer.sign(payload, @tenant_id, @secret)
    end
  end
end

# Dipanggil di middleware per-request:
CloudAuthenticator.configure do
  set_credentials(request.headers["X-Tenant"], request.headers["X-Secret"])
end
CloudAuthenticator.authenticate_request(request.body)
```

**Pertanyaan Diagnostik:**
1. Tunjukkan dengan tepat bagaimana kondisi *race condition* terjadi saat Thread 1 dan Thread 2 mengeksekusi middleware secara simultan.
2. Mengapa penggunaan instance variable pada Singleton Module/Class (`@tenant_id` pada `class << self`) menjadi bencana konkuren dalam runtime Ruby ber-thread banyak?
3. Desain ulang arsitektur configuration engine tersebut agar sepenuhnya *thread-safe* dan *re-entrant* tanpa overhead locking mutex yang memblokir I/O throughput.

---

### Skenario C: Dilema Arsitektur: Dynamic Meta-DSL vs Explicit Composition
**Kasus:**
Tim engineering Anda sedang membangun sistem audit logging dan event emission untuk seluruh service domain (terdapat 80+ service classes). 
- **Opsi A (Metaprogramming Hook):** Senior Architect mengusulkan pembuatan module `Auditable` yang di-`prepend` ke semua service. Modul ini menggunakan `method_added` hook untuk mencegat setiap method yang didefinisikan, membungkus eksekusi method secara otomatis dengan timing, error capturing, dan Kafka event emission menggunakan dynamic method aliasing atau `Module#prepend`.
- **Opsi B (Explicit Composition / Decorator Pattern):** Principal Engineer menolak usulan tersebut dan menyarankan pembuatan *Explicit Decorator* atau *Command Pattern* berbasis komposisi murni (misal: `AuditedCommand.call(ServiceClass.new)`), dengan argumen *maintainability*, kemudahan static typing (Sorbet/RBS), dan kemudahan tracing stacktrace saat runtime error.

**Pertanyaan Diagnostik:**
1. Evaluasi Opsi A dari sudut pandang *developer ergonomics*, observabilitas stack trace saat terjadi exception, dan kompatibilitas terhadap static analysis tooling (RBS/TypeProf/Sorbet).
2. Evaluasi Opsi B dari sudut pandang *boilerplate overhead*, konsistensi developer (risiko lupa memanggil wrapper), dan evolusi arsitektur.
3. Sebagai Senior Staff Engineer, berikan keputusan arsitektural final Anda: Opsi mana yang Anda pilih (atau kombinasi desain seperti apa), dan buat panduan teknis (*technical blueprint*) untuk mengimplementasikan solusi tersebut.

---

## 4. Chapter Challenge

### Tantangan Praktis: Membangun Production-Grade Dynamic Schema Model (`MicroSchema`)

#### Deskripsi Problem
Framework active-record bawaan terlalu lambat dan berat memori untuk skenario data ingest streaming (100.000 events/detik) yang membutuhkan parsing schema cepat, konversi tipe data, validasi, dan dirty tracking. Anda diminta untuk membuat library stand-alone bernama `MicroSchema` murni menggunakan Ruby Metaprogramming tingkat tinggi tanpa eksternal gem apa pun.

#### Requirements Teknis
1. **DSL Deklarasi Atribut:**
   Mendukung pendefinisian atribut dengan tipe data, opsi default, dan validasi kehadiran:
   ```ruby
   class EventSchema
     include MicroSchema

     attribute :event_id, type: String, required: true
     attribute :payload,  type: Hash,   default: -> { {} }
     attribute :attempts, type: Integer, default: 0
   end
   ```
2. **Fast Dynamic Method Compilation (Bukan `method_missing`):**
   - Getter, setter (`name=`), predicate (`name?`), dan dirty-tracking methods (`name_changed?`, `name_was`) **harus dikompilasi secara dinamis ke dalam sebuah dedicated anonymous module** yang di-`include` ke dalam kelas penampung.
   - Tidak boleh ada method resolution fallback via `method_missing` pada hot-path pembacaan atribut untuk menjamin performa mendekati instansiasi Ruby native.
   - Mendukung pemanggilan `super` di dalam kelas turunan jika pengguna ingin melakukan override pada getter/setter.
3. **Dirty State Tracking:**
   - Objek harus dapat melacak apakah suatu atribut telah bermutasi sejak inisialisasi: `schema.event_id_changed?` (mengembalikan Boolean).
   - Objek harus menyimpan nilai awal sebelum mutasi: `schema.event_id_was` (mengembalikan nilai lama).
   - Method `changes` mengembalikan hash `{ attribute_name => [old_value, new_value] }`.
4. **Strict Type Coercion & Validation:**
   - Memberikan error custom `MicroSchema::TypeError` jika tipe data yang diberikan pada saat instansiasi atau asignasi tidak cocok dengan tipe yang dideklarasikan (dan tidak bisa di-cast secara aman).
   - Method `valid?` dan `validate!` untuk memastikan semua constraint (seperti `required: true`) terpenuhi.

#### Constraints
1. **Zero External Dependencies:** Hanya menggunakan standard library Ruby (Ruby Core).
2. **Thread Safety:** Pendefinisian schema pada level kelas harus aman dari konkurensi (schema compilation terjadi pada load time, bukan runtime instansiasi).
3. **Memory Isolation:** Tidak boleh ada class variables (`@@`). State konfigurasi per-schema harus diisolasi menggunakan Class Instance Variables atau Singleton Class Attributes agar aman terhadap inheritance hierarkis.
4. **Metaprogramming Hygiene:** 
   - Wajib mengimplementasikan hook `inherited` agar subclass dari schema yang sudah ada mewarisi semua atribut parent tanpa memutasi skema parent (*immutable inheritance*).

#### Expected Output
Implementasi lengkap file `micro_schema.rb` yang lulus test harness skenario berikut:

```ruby
class UserEvent
  include MicroSchema

  attribute :id, type: Integer, required: true
  attribute :email, type: String
  attribute :metadata, type: Hash, default: -> { {} }
end

class SpecialUserEvent < UserEvent
  attribute :vip_code, type: String, default: -> { "NONE" }
  
  # Override test dengan super
  def email=(val)
    super(val.to_s.downcase.strip)
  end
end

# Inisialisasi
event = SpecialUserEvent.new(id: 1, email: "  TEST@DOMAIN.COM  ")

puts event.id # => 1
puts event.email # => "test@domain.com"
puts event.metadata # => {}
puts event.vip_code # => "NONE"
puts event.email_changed? # => true
puts event.email_was # => nil
puts event.changes # => {"id" => [nil, 1], "email" => [nil, "test@domain.com"], ...}

event.email = "new@domain.com"
puts event.email_was # => "test@domain.com"
puts event.changes["email"] # => ["test@domain.com", "new@domain.com"]

# Validasi Type Failure
begin
  SpecialUserEvent.new(id: "BUKAN_INTEGER")
rescue MicroSchema::TypeError => e
  puts "Type check worked: #{e.message}"
end

# Isolasi Inheritance Test
puts UserEvent.attributes.key?(:vip_code) # => HARUS FALSE
puts SpecialUserEvent.attributes.key?(:vip_code) # => HARUS TRUE
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Topologi lengkap Ruby Object Model: relasi antara `Object`, `Class`, `Module`, `BasicObject`, dan posisi *Singleton Class* (Eigenclass/Metaclass).
- [ ] Mekanisme linearitas *Ancestor Chain* untuk `include`, `prepend`, dan `extend`, serta keberadaan representasi internal `ICLASS`.
- [ ] Perbedaan kontekstual, pemindahan `self`, dan binding lingkungan antara `class_eval`, `instance_eval`, dan `module_eval`.
- [ ] Konsekuensi teknis modifikasi objek dinamis terhadap YARV Inline Method Cache invalidation dan performa bytecode execution.
- [ ] Dampak closures capture pada `define_method` terhadap siklus hidup Garbage Collector (GC) dan retensi memori lexical scope.
- [ ] Bahaya konkurensi dari mutasi Class Variables (`@@`) vs isolasi aman via Class Instance Variables (`@var` di class context).
- [ ] Kontrak eksplisit antara `method_missing` dan `respond_to_missing?` untuk transparansi reflection API.

### Saya tidak perlu menghafal:
- [ ] Nomor opcode internal YARV (misal: `opt_send_without_block`, `invokeblock`) yang dihasilkan saat kompilasi dynamic dispatch.
- [ ] Seluruh daftar C struct internals MRI (`RClass`, `RString`, `rb_classext_t`), cukup memahami perilaku semantik tingkat tinggi di runtime.
- [ ] Kode implementasi native library pihak ketiga (seperti internal ActiveSupport::Concern), selama menguasai *vanilla Ruby hooks* (`included`, `extended`, `prepended`).

### Saya harus bisa melakukan:
- [ ] Mengembangkan DSL deklaratif yang fleksibel namun aman tanpa menimbulkan memory leak atau degradasi performa dispatch.
- [ ] Melakukan debugging dan introspeksi hierarki objek rumit menggunakan reflection API (`ancestors`, `singleton_class`, `method`, `instance_variables`, `binding`).
- [ ] Membangun Proxy transparan dengan zero method leakage menggunakan `BasicObject` dan selective method aliasing.
- [ ] Mencegah dan mengeliminasi race conditions pada arsitektur Ruby multi-threaded yang memanfaatkan dynamic class/module generation.
- [ ] Mengimplementasikan dynamic code generation berbasis modul anonim terisolasi agar tetap menyediakan titik integrasi `super` yang elegan bagi end developer.