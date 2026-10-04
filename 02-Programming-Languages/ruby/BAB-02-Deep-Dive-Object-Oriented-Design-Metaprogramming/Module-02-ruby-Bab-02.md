# BAB 02: Deep Dive Object-Oriented Design & Metaprogramming
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** representasi memori C-Ruby (MRI) pada struktur data `RBasic`, `RObject`, dan `RClass`, termasuk mekanisme pointer `klass` dan resolusi *singleton class* (*eigenclass*).
- **Mengevaluasi** performa eksekusi YARV bytecode terhadap *inline method cache* (IC) dan *global method cache* (GMC), serta memitigasi dampak *cache invalidation* akibat modifikasi kelas dinamis.
- **Merancang** sistem DSL (*Domain-Specific Language*) deklaratif berbasis metaprogramming tingkat lanjut menggunakan `instance_eval`, `class_eval`, `define_method`, dan *lexical binding scope* dengan penanganan isolasi memori.
- **Mengimplementasikan** arsitektur *Plugin & Middleware Pipeline* berlatensi rendah untuk beban kerja *multi-tenant enterprise* yang bebas dari kebocoran memori closure (*closure leak*) dan degradasi thread safety.

---

### 2. Prerequisite

Peserta wajib menguasai:
- Ruby fundamental (Object Oriented Programming dasar: class, module, inheritance).
- Model konkurensi Ruby dasar (Thread, Fiber, Global VM Lock/GVL).
- Pemahaman sistem operasi mengenai alokasi memori heap, stack, dan pointer referensi memori (khususnya C memory structure).
- Ruby versi 3.2+ terpasang pada lingkungan pengembangan.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Representasi Memori C-Ruby (MRI)

Di dalam MRI (Matz's Ruby Interpreter), setiap entitas Ruby direpresentasikan sebagai nilai bertipe `VALUE`, yang merupakan sebuah pointer (pada arsitektur 64-bit) ke heap MRI atau *immediate value* (seperti `Fixnum`/`Integer` kecil, `true`, `false`, `nil`, dan `Symbol` terkontrol) melalui teknik *tagged pointer*.

Untuk objek kompleks yang dialokasikan di heap, `VALUE` menunjuk ke struktur union `RVALUE`. Setiap `RVALUE` diawali oleh header `RBasic`:

```c
struct RBasic {
    VALUE flags; // Menyimpan type flag (T_OBJECT, T_CLASS, dll) dan GC flags (WB, marking)
    VALUE klass; // Pointer ke RClass asal objek
};

struct RObject {
    struct RBasic basic;
    union {
        struct {
            uint32_t numiv;      // Jumlah instance variables
            VALUE *ivptr;        // Heap array pointer untuk ivar jika numiv > ROBJECT_EMBED_LEN_MAX
            void *iv_index_tbl;  // Index mapping dari shape tree
        } heap;
        VALUE ary[ROBJECT_EMBED_LEN_MAX]; // Embedded array untuk ivar kecil (hingga 3 variabel)
    } as;
};
```

Pada Ruby 3.2+, representasi instance variable memanfaatkan arsitektur **Shape Tree** (mirip dengan Hidden Classes V8), di mana setiap penambahan instance variable (`@ivar`) mentransisikan `shape_id` objek, bukan lagi mengalokasikan hash table per-instance.

`RClass` adalah struktur yang memuat metadata eksekusi:

```c
struct RClass {
    struct RBasic basic;
    VALUE super;                  // Pointer ke superclass
    rb_classext_t *ptr;           // Menyimpan method table (m_tbl), ivar cache, dan flags
    struct rb_id_table *m_tbl;    // Table berisi method ID -> rb_method_entry_t
};
```

#### 3.2 Method Lookup Algorithm & Singleton Class (Eigenclass) Hierarchy

Resolusi pemanggilan method (`foo.bar`) mengikuti aturan strict traversal pointer `klass` dan `super`:

```
Objek -> Singleton Class (jika ada) -> Included Module (prepend) -> 
Class Asal -> Included Module (include) -> Superclass -> ... -> 
Object -> Kernel -> BasicObject
```

1. **Instance Resolution**: Saat method dipanggil pada instance `inst`, runtime memeriksa pointer `RBasic.klass` dari `inst`. Jika instance memiliki *singleton class* (dibuat saat membuka `class << inst` atau mendefinisikan method khusus instance), pointer `RBasic.klass` menunjuk ke singleton class tersebut. Jika tidak, ia menunjuk langsung ke `RClass` dari kelas pembuatnya.
2. **Prepend vs Include**:
   - `include M`: Menyisipkan entry wrapper `ICLASS` (Inclusion Class) yang mereferensikan `M` tepat di antara kelas target dan `super`-nya.
   - `prepend M`: Menyisipkan `ICLASS` untuk kelas target di bawah `M`, mengarahkan pointer `klass` pemanggil langsung ke `M`.
3. **Singleton Hierarchy**: Singleton class dari sebuah Class (misal `class << User`) memiliki rantai pewarisan yang merefleksikan hierarki kelasnya: `klass` dari `User` adalah singleton class `User`, dan `super` dari singleton class `User` adalah singleton class dari `User.superclass`.

```
           +--------------------+
           |    BasicObject     |
           +---------^----------+
                     |
           +---------+----------+
           |       Object       |
           +---------^----------+
                     |
           +---------+----------+
           |     Superclass     |<--------------------+
           +---------^----------+                     |
                     |                                | super
                     | super                          |
           +---------+----------+           +---------+----------+
           |       Class        |           |  SingletonClass    |
           |     (Target)       |           |   (Superclass)     |
           +---------^----------+           +---------^----------+
                     |                                |
                     | klass                          | super
           +---------+----------+           +---------+----------+
           |      Instance      |           |  SingletonClass    |
           |      (Target)      |---------->|     (Target)       |
           +--------------------+   klass   +--------------------+
```

#### 3.3 YARV Dynamic Method Dispatch & Method Caching

YARV mengompilasi pemanggilan method menjadi instruksi `opt_send_without_block` atau `send`. Untuk memitigasi overhead traversal traversi pohon pewarisan yang kompleks, YARV mengimplementasikan dua layer caching:

1. **Global Method Cache (GMC)**: Hash table global yang memetakan tuple `(klass, method_id)` ke `rb_method_entry_t`.
2. **Inline Cache (IC)**: Cache yang tertanam langsung pada instruksi bytecode call site. Struktur cache menyimpan referensi ke kelas target dan cache token validasi kelas.

##### Mekanisme Deoptimasi (Cache Invalidation)
Setiap kali metaprogramming digunakan untuk mengubah struktur kelas secara dinamis pada runtime (`define_method`, `alias_method`, `include`, `remove_method`), Ruby mengeksekusi operasi internal:

```c
rb_clear_cache(); // atau pembaruan class serial global pada MRI modern
```

Pada C-Ruby, setiap kelas memiliki atribut `class_serial`. Ketika sebuah kelas dimodifikasi, `class_serial` miliknya dan seluruh subkelasnya diinkrementasi. Hal ini menyebabkan **seluruh Inline Cache yang terasosiasi dengan rantai kelas tersebut invalid**, memaksa YARV melakukan deoptimasi, beralih dari single-instruction callsite execution kembali ke full-path method lookup (`rb_callable_method_entry()`), yang meningkatkan latensi CPU secara signifikan jika terjadi di dalam loop throughput tinggi.

---

### 4. Why & What

| Dimensi | Pendekatan Metaprogramming Dinamis | Pendekatan Static / Boilerplate |
| :--- | :--- | :--- |
| **Why (Justifikasi)** | Memungkinkan pembuatan DSL deklaratif tingkat tinggi, mengurangi ratusan baris plumbing code, decoupling implementasi terhadap interface runtime secara fleksibel. | Menjamin determinisme kompilasi, kejelasan call stack tracing, dan zero risk terhadap GMC invalidation. |
| **What (Mekanisme)** | Menggunakan `define_method`, `method_missing`, manipulasi dynamic scope via `Binding`, dan modifikasi `m_tbl` saat runtime. | Pola desain klasik: Strategy, Visitor, atau Explicit Command pattern dengan deklarasi kelas statis. |
| **Kapan Digunakan** | Framework core, ORM mapping dinamis, Dynamic RPC Client, Policy/Rule Engine dinamis dengan DSL enterprise. | Domain logic inti perbankan, financial calculation loop, mission-critical microservice dengan requirement latensi sub-milidetik. |
| **Dampak Performa** | Pemanggilan dinamis via `method_missing` memakan waktu 2x-4x lebih lama dibanding dispatch method normal jika tidak dicache; modifikasi runtime memicu *Inline Cache Thrashing*. | Prediktabilitas memori stabil, branch prediction CPU bekerja maksimal, memori shape tetap konstan. |

---

### 5. How (Workflow Detail)

Alur eksekusi saat sebuah method dinamis dipanggil hingga YARV mengeksekusi body fungsinya:

```
[ Pemanggilan: object.process_transaction(payload) ]
                        |
                        v
    [ Periksa Inline Cache (IC) pada Call-site ]
     /                                        \
  (Cache Hit: Class serial valid)           (Cache Miss / Invalid)
   /                                            \
  v                                              v
[ Eksekusi rb_method_entry_t ]      [ Search RClass m_tbl ]
                                     /                    \
                                (Ditemukan)          (Tidak Ditemukan)
                                  /                        \
                                 v                          v
                      [ Update Inline Cache ]     [ Traverse RClass->super ]
                                 |                          |
                                 v                  (Sampai BasicObject)
                      [ Eksekusi Bytecode ]                 |
                                                            v
                                            [ Method Not Found Trigger ]
                                                            |
                                                            v
                                            [ Search m_tbl: method_missing ]
                                             /                            \
                                        (Ditemukan)                  (Default)
                                          /                                \
                                         v                                  v
                               [ Bungkus argumen & ID ]             [ Raise NoMethodError ]
                                         |
                                         v
                               [ Eksekusi method_missing ]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Birokrasi Gedung Arsip Nasional
- **Instance**: Pengunjung yang membawa formulir kosong.
- **RBasic `klass`**: Pintu masuk loket yang tertera pada tiket pengunjung.
- **Singleton Class**: Petugas konsierge pribadi yang berdiri tepat di depan pengunjung, menangani permintaan khusus yang tidak terdaftar di buku SOP umum.
- **Ancestor Chain (super)**: Lantai gedung bertingkat. Jika loket di lantai 1 tidak memiliki arsip yang diminta, petugas naik ke lantai 2 (`Superclass`), terus hingga ke ruang arsip induk di lantai paling atas (`BasicObject`).
- **Inline Cache**: Memo tempel di saku petugas. Jika pengunjung menanyakan hal yang sama berulang kali, petugas langsung melihat memo tanpa mencari kembali ke lemari arsip pusat.
- **Metaprogramming Runtime (`define_method`)**: Mengganti atau menempel instruksi baru pada papan SOP pusat secara tiba-tiba, yang mewajibkan seluruh petugas membuang semua memo tempel mereka (*Cache Invalidation*).

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Dynamic Method Synthesis vs `method_missing`

Kode berikut mendemonstrasikan perbedaan performa dan cara kerja antara fallback `method_missing` yang lambat versus lazy dynamic generation via `define_method` yang mengembalikan inline caching.

```ruby
# frozen_string_literal: true

class DynamicAttributeStore
  def initialize(attributes = {})
    @attributes = attributes
  end

  # Pendekatan 1: Fallback Traversal Dinamis
  def method_missing(method_name, *args, &block)
    attr_key = method_name.to_s
    if attr_key.end_with?('=')
      base_key = attr_key.chop.to_sym
      return @attributes[base_key] = args.first
    elsif @attributes.key?(method_name)
      # Self-healing optimization: Sintesis method agar pemanggilan berikutnya melewati IC
      self.class.define_attribute_reader(method_name)
      return @attributes[method_name]
    end

    super
  end

  def respond_to_missing?(method_name, include_private = false)
    attr_key = method_name.to_s.delete_suffix('=').to_sym
    @attributes.key?(attr_key) || super
  end

  # Pendekatan 2: Metaprogramming Terencana (Zero GMC Penalty setelah kompilasi kelas)
  def self.define_attribute_reader(name)
    define_method(name) do
      @attributes[name]
    end
  end
end

# Pengujian
store = DynamicAttributeStore.new(balance: 100_000_000, currency: 'IDR')
puts store.respond_to?(:balance) # => true
puts store.balance              # => 100000000 (Memicu method_missing sekali, menyintesis method, run IC seterusnya)
puts store.currency             # => IDR
```

#### 7.2 Practical Example: Enterprise Contract DSL dengan Clean Scoping

Implementasi framework deklarasi validasi yang memisahkan eksekusi block scope menggunakan `clean_binding` guna mencegah *memory capture leak*.

```ruby
# frozen_string_literal: true

module EnterpriseContract
  class Rule
    attr_reader :field, :predicate, :error_message

    def initialize(field, predicate, error_message)
      @field = field
      @predicate = predicate
      @error_message = error_message
    end

    def validate(entity)
      value = entity.public_send(field)
      predicate.call(value)
    end
  end

  class Schema
    attr_reader :rules

    def initialize
      @rules = []
    end

    def check(field, error_message:, &predicate)
      raise ArgumentError, 'Predicate block required' unless block_given?
      @rules << Rule.new(field, predicate, error_message)
    end
  end

  module ClassMethods
    def schema(&block)
      @schema ||= Schema.new
      if block_given?
        # Menjalankan evaluasi definisi DSL dalam konteks terisolasi
        DocDSL.new(@schema).instance_eval(&block)
      end
      @schema
    end
  end

  # Object builder DSL terisolasi untuk menghindari polusi namespace kelas target
  class DocDSL
    def initialize(schema)
      @schema = schema
    end

    def assert(field, message, &block)
      @schema.check(field, error_message: message, &block)
    end
  end

  def self.included(base)
    base.extend(ClassMethods)
  end

  def validate!
    schema = self.class.schema
    errors = []

    schema.rules.each do |rule|
      unless rule.validate(self)
        errors << { field: rule.field, error: rule.error_message }
      end
    end

    errors
  end
end

# Penggunaan pada Domain Model
class TransactionPayload
  include EnterpriseContract

  attr_reader :amount, :account_id, :currency

  def initialize(amount:, account_id:, currency:)
    @amount = amount
    @account_id = account_id
    @currency = currency
  end

  schema do
    assert(:amount, 'Amount harus lebih besar dari 0') { |v| v.is_a?(Numeric) && v.positive? }
    assert(:account_id, 'Account ID invalid') { |v| v.to_s.start_with?('ACC-') }
    assert(:currency, 'Currency tidak didukung') { |v| %w[IDR USD EUR].include?(v) }
  end
end

payload = TransactionPayload.new(amount: -500, account_id: 'USR-123', currency: 'SGD')
violations = payload.validate!
puts violations
# Output:
# [{:field=>:amount, :error=>"Amount harus lebih besar dari 0"}, 
#  {:field=>:account_id, :error=>"Account ID invalid"}, 
#  {:field=>:currency, :error=>"Currency tidak didukung"}]
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Sistem *Core Banking Payment Gateway* memproses 20.000 transaksi/detik. Sistem memerlukan audit logging dinamis, instrumentasi latensi, serta injeksi *trace-id* terdistribusi pada ribuan service endpoint tanpa memodifikasi class business logic secara manual, dan tanpa menimbulkan memory leak akibat closure dynamic metadata.

#### Masalah Arsitektur
Penggunaan `alias_method_chain` konvensional atau `method_missing` menyebabkan deoptimasi YARV method cache global, memicu peningkatan alokasi GC sebesar 35%, serta memunculkan stack trace rekursif yang merusak pelaporan OpenTelemetry.

#### Solusi Arsitektural: Module Prepend Interceptor Engine
Membangun zero-overhead dynamic interceptor engine berbasis `Module.prepend` yang dikompilasi saat booting aplikasi (*freeze phase*), bukan secara dinamis saat runtime pemrosesan transaksi.

```ruby
# frozen_string_literal: true

require 'securerandom'
require 'logger'

module EnterpriseTelemetry
  # Registry metadata global untuk isolasi thread
  Context = Struct.new(:trace_id, :actor)
  
  def self.current_context
    Thread.current[:_telemetry_ctx] ||= Context.new(SecureRandom.uuid, 'system')
  end

  class InterceptorBuilder
    def self.instrument(target_klass, *methods)
      interceptor_mod = Module.new

      methods.each do |method_name|
        raise ArgumentError, "Method #{method_name} tidak ditemukan di #{target_klass}" unless target_klass.method_defined?(method_name)

        interceptor_mod.module_eval do
          define_method(method_name) do |*args, **kwargs, &block|
            ctx = EnterpriseTelemetry.current_context
            start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond)
            
            # Audit trail capture tanpa alokasi object hash berlebih
            begin
              result = super(*args, **kwargs, &block)
              duration_ms = (Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond) - start_time) / 1_000_000.0
              EnterpriseTelemetry.logger.info(
                "[AUDIT-SUCCESS] Trace: #{ctx.trace_id} | Class: #{target_klass} | Method: #{method_name} | Latency: #{duration_ms.round(3)}ms"
              )
              result
            rescue StandardError => e
              duration_ms = (Process.clock_gettime(Process::CLOCK_MONOTONIC, :nanosecond) - start_time) / 1_000_000.0
              EnterpriseTelemetry.logger.error(
                "[AUDIT-FAILURE] Trace: #{ctx.trace_id} | Class: #{target_klass} | Method: #{method_name} | Err: #{e.class}-#{e.message} | Latency: #{duration_ms.round(3)}ms"
              )
              raise
            end
          end
        end
      end

      # Memasukkan interceptor ke dalam ancestor hierarchy tepat sebelum target_klass
      target_klass.prepend(interceptor_mod)
    end
  end

  def self.logger
    @logger ||= Logger.new($stdout).tap do |l|
      l.formatter = proc { |severity, datetime, _progname, msg| "#{datetime.iso8601} [#{severity}] #{msg}\n" }
    end
  end
end

# Core Banking Service (Domain murni tanpa dependensi telemetry)
class FundTransferService
  def execute_transfer(source_acc:, target_acc:, amount_cents:)
    # Simulasi latensi database I/O
    sleep(0.02)
    raise ArgumentError, 'Saldo tidak mencukupi' if amount_cents > 10_000_000

    { status: 'SUCCESS', transaction_id: "TX-#{SecureRandom.hex(4)}" }
  end
end

# Phase: Bootstrapping / Initialization (Hanya dieksekusi 1x saat startup)
EnterpriseTelemetry::InterceptorBuilder.instrument(FundTransferService, :execute_transfer)
FundTransferService.freeze # Mencegah mutasi class pasca-bootstrapping

# Phase: Runtime execution
service = FundTransferService.new
puts service.execute_transfer(source_acc: 'ACC-001', target_acc: 'ACC-002', amount_cents: 5_000_000)

begin
  service.execute_transfer(source_acc: 'ACC-001', target_acc: 'ACC-002', amount_cents: 20_000_000)
rescue StandardError
  # Exception tertangkap setelah ter-audit
end
```

---

### 9. Trade-offs

```
                       LATENCY & EXECUTION OVERHEAD
                                    ^
                                    |
   (High Latency / High Flexibility)|  [method_missing]
                                    |      * Fallback traversal penuh
                                    |      * GMC miss beruntun
                                    |      * No method cache hit
                                    |
                                    |  [Dynamic define_method at Runtime]
                                    |      * Global cache invalidation
                                    |      * Closure memory retention
                                    |
                                    |  [Module.prepend at Bootstrapping]
                                    |      * Static YARV Inline Caching
                                    |      * Zero-allocation dispatch
                                    |
                                    +----------------------------------->
                                   ZERO                             EXTREME
                                          DYNAMIC ARCHITECTURAL AGILITY
```

| Pendekatan | Performance & Latency | Scalability & Memory | Cost / Dev Complexity |
| :--- | :--- | :--- | :--- |
| **`method_missing` + `respond_to_missing?`** | Latensi pemanggilan ~200ns-500ns per-call site. Melewatkan mekanisme inline cache YARV. | Menghemat memori kelas karena tidak ada node method baru di `m_tbl`. | Mudah diimplementasikan, namun debugging call stack sangat sulit (*leaking abstractions*). |
| **Runtime `define_method` (On-demand)** | Latensi awal tinggi saat sintesis, panggilan berikutnya turun ke ~30ns. Memicu deoptimasi kelas global (`class_serial++`). | **Risiko kebocoran memori tinggi**. Setiap closure retain environment local variable pembuatnya, menahan objek dari GC. | Kompleksitas tinggi; rawan race condition pada lingkungan multi-thread tanpa Mutex. |
| **Boot-time `Module.prepend` Interception** | Latensi setara pemanggilan method normal (~25ns-35ns). Inline cache stabil karena class hierarki statis setelah boot. | Overhead memori hanya berupa pembuatan alokasi `ICLASS` satu kali saat bootstrap. | Membutuhkan arsitektur lifecycle aplikasi yang ketat (Boot -> Freeze -> Serve). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Lupa Mendefinisikan `respond_to_missing?`
*Gejala*: Object merespons method via `method_missing`, tetapi `obj.respond_to?(:method)` mengembalikan `false`, merusak serialisasi framework (misal: JSON serializers, form builders).
*Solusi*: Wajib mengimplementasikan pasangan `respond_to_missing?` secara strictly paired.

```ruby
# SALAH
def method_missing(name, *args)
  return "Handling #{name}" if name.start_with?('find_by_')
  super
end

# BENAR
def method_missing(name, *args, &block)
  return "Handling #{name}" if name.start_with?('find_by_')
  super
end

def respond_to_missing?(name, include_private = false)
  name.start_with?('find_by_') || super
end
```

#### 10.2 Memory Leak via Closure Scope Capture pada `define_method`
*Gejala*: Memory footprint naik secara linear (*heap exhaustion*) meskipun transaksi sudah selesai.
*Penyebab*: `define_method` mempertahankan binding scope di mana ia dieksekusi. Jika scope tersebut memuat objek besar (misal array buffer, file descriptor), GC tidak dapat membersihkannya.

```ruby
# SALAH: Closure menahan referensi 'huge_data_buffer' selamanya di heap
def setup_worker(huge_data_buffer)
  define_singleton_method(:process) do
    puts "Processing #{huge_data_buffer.bytesize} bytes"
  end
end

# BENAR: Putus binding lexical scope menggunakan method helper tanpa retain objek besar
def setup_worker(huge_data_buffer)
  size = huge_data_buffer.bytesize
  bind_processor(size)
end

def bind_processor(size)
  define_singleton_method(:process) do
    puts "Processing #{size} bytes"
  end
end
```

#### 10.3 Dynamic Cache Invalidation Storm
*Gejala*: CPU spike 100% pada sistem enterprise dengan throughput tinggi tanpa adanya peningkatan volume transaksi.
*Diagnosa*: Melakukan profiling menggunakan Ruby VM memory stat:
```ruby
RubyVM.stat(:global_method_state) # Nilai ini melonjak setiap kali ada kelas yang dimodifikasi
```
*Penyebab*: Terdapat worker thread yang memanggil `def`, `class_eval`, atau `alias_method` di dalam execution loop request/response.

---

### 11. Best Practices (Production Checklist)

- [ ] **Freeze Dynamic Classes**: Jalankan `.freeze` pada class dan module setelah bootstrapping selesai untuk mencegah race conditions dan runtime monkey-patching.
- [ ] **No Metaprogramming in Hot Paths**: Jangan pernah memanggil `define_method`, `class_eval`, atau `remove_method` di dalam per-request execution path.
- [ ] **Method Missing Boundary**: Jika menggunakan `method_missing`, terapkan validasi guard clause secepat mungkin, dan selalu delegasikan ke `super` jika kriteria method tidak cocok.
- [ ] **Explicit Arity and Kwargs Forwarding**: Gunakan argument forwarding modern (`...`) pada method synthesis untuk meminimalkan alokasi array dan hash parameter di YARV VM:
  ```ruby
  define_method(:proxy_call) do |...|
    target.forward(...)
  end
  ```
- [ ] **Avoid String Eval**: Jangan pernah menggunakan `eval(string)`. Gunakan block-based `class_eval` atau `instance_exec` untuk mempertahankan parsing syntax pohon AST yang aman dari SQL/Code Injection.
- [ ] **Namespace Isolation**: Bangun instance DSL di dalam kelas evaluator khusus (*BlankSlate* atau subclass dari `BasicObject`) untuk mencegah leakage instance variable ke scope business logic.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

#### Task: Membangun Thread-Safe Dynamic Data Mapper Engine Berlatensi Rendah

##### Langkah 1: Siapkan Struktur Direktori
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

##### Langkah 2: Buat File `data_mapper.rb`
Implementasikan kode berikut:

```ruby
# hands-on/m02/data_mapper.rb
# frozen_string_literal: true

module EnterpriseOrm
  class Model
    # Shape Tree stabilization: Inisialisasi struktur ivar di awal
    def initialize(attributes = {})
      @attributes = {}
      assign_attributes(attributes)
    end

    def assign_attributes(attributes)
      attributes.each do |key, value|
        writer_method = :"#{key}="
        if respond_to?(writer_method)
          public_send(writer_method, value)
        else
          @attributes[key.to_sym] = value
        end
      end
    end

    def read_attribute(name)
      @attributes[name]
    end

    def write_attribute(name, value)
      @attributes[name] = value
    end

    class << self
      def inherited(subclass)
        super
        subclass.instance_variable_set(:@columns, {})
      end

      def column(name, type, default: nil)
        name = name.to_sym
        @columns[name] = { type: type, default: default }

        # Metaprogramming Compile-time: Menghasilkan getter & setter eksplisit
        # Menghindari method_missing overhead sepenuhnya
        define_method(name) do
          @attributes.fetch(name, default)
        end

        define_method(:"#{name}=") do |val|
          coerced_val = EnterpriseOrm::TypeCoercer.coerce(val, type)
          @attributes[name] = coerced_val
        end
      end

      def columns
        @columns
      end
    end
  end

  class TypeCoercer
    def self.coerce(val, type)
      return nil if val.nil?

      case type
      when :integer then val.to_i
      when :string  then val.to_s
      when :float   then val.to_f
      when :boolean then !!val
      else
        val
      end
    end
  end
end
```

##### Langkah 3: Buat File `benchmark.rb`
Uji integritas performa dan pemeliharaan Inline Cache antara compiled dynamic method vs `method_missing`:

```ruby
# hands-on/m02/benchmark.rb
# frozen_string_literal: true

require 'benchmark'
require_relative 'data_mapper'

# Implementasi alternatif berbasis method_missing murni
class SlowModel
  def initialize(attributes = {})
    @attributes = attributes
  end

  def method_missing(name, *args)
    attr_name = name.to_s.delete_suffix('=').to_sym
    return @attributes[attr_name] = args.first if name.end_with?('=')
    return @attributes[attr_name] if @attributes.key?(attr_name)
    super
  end

  def respond_to_missing?(name, _)
    true
  end
end

class FastAccount < EnterpriseOrm::Model
  column :id, :integer
  column :balance, :float
  column :holder, :string
end

ITERATIONS = 1_000_000

fast_acc = FastAccount.new(id: 101, balance: 50_000.75, holder: 'Alice')
slow_acc = SlowModel.new(id: 101, balance: 50_000.75, holder: 'Alice')

puts "Menjalankan Benchmark #{ITERATIONS} iterasi..."

Benchmark.bm(25) do |x|
  x.report('Fast Dynamic Accessor:') do
    ITERATIONS.times do
      fast_acc.balance = 55_000.50
      _ = fast_acc.balance
    end
  end

  x.report('Slow method_missing:') do
    ITERATIONS.times do
      slow_acc.balance = 55_000.50
      _ = slow_acc.balance
    end
  end
end
```

##### Langkah 4: Eksekusi dan Analisis
```bash
ruby hands-on/m02/benchmark.rb
```
*Ekspektasi Output*: Implementasi `Fast Dynamic Accessor` akan 3x hingga 6x lebih cepat dibanding `Slow method_missing` karena pemanfaatan Inline Cache YARV.

---

### 13. Exercise

#### Level Easy
Tulis sebuah modul `SafeAttributeReader` yang saat di-extend oleh sebuah kelas, membaca file configuration `YAML` dan membuat getter method dinamis secara deklaratif menggunakan `define_method`. Pastikan jika method yang didefinisikan sudah ada sebelumnya, lemparkan error `ArgumentError` untuk mencegah overwrite tanpa sengaja.
*Kriteria Sukses*: Method terdaftar di kelas, lolos verifikasi `respond_to?`, tidak menimpa method bawaan `Object`.

#### Level Medium
Buat DSL routing HTTP mikro (mirip routing framework Sinatra/Grape) bernama `MicroRouter`.
- Memiliki DSL: `get '/path'`, `post '/path'`.
- Routing handler dipetakan menggunakan `instance_eval` pada runtime request.
- Setiap pemanggilan handler harus mengisolasi eksekusi dalam instance baru agar tidak terjadi *state bleeding* antar concurrent thread.
*Kriteria Sukses*: Thread-safe, lolos pengujian 100 concurrent execution tanpa race condition state.

#### Level Hard
Rancang dynamic proxy middleware engine yang mengimplementasikan sistem Circuit Breaker.
- Proxy membungkus arbitrary target class tanpa mengubah kode target (*non-invasive*).
- Menggunakan `prepend` secara otomatis pada target class saat registrasi.
- Mengintersepsi setiap pemanggilan method publik.
- Jika method gagal 3x berturut-turut dalam kurun waktu 10 detik, interceptor langsung melempar exception `CircuitOpenError` dalam waktu O(1) tanpa memanggil method asli pada panggilan berikutnya.
*Kriteria Sukses*: Zero overhead saat circuit closed, lock-free atau minimal contention thread safety, memulihkan state (*Half-Open*) otomatis setelah 5 detik.

---

### 14. Challenge

**Studi Kasus Arsitektural**: Rancang sebuah **Dynamic Multi-tenant Runtime Feature Flag Engine** untuk sistem perbankan berlatensi tinggi (P99 < 5ms).

#### Batasan & Kebutuhan Teknis:
1. **Dynamic Method Injection**: Setiap tenant memiliki set aturan bisnis yang dapat berubah sewaktu-waktu melalui database config (misal: algoritma diskon transaksi, fee structure).
2. **Zero Global Method Cache Invalidation**: Anda **dilarang keras** memicu pemanggilan `define_method` atau mutasi class structure saat sistem sedang melayani HTTP request produksi, karena hal tersebut akan merusak Inline Cache seluruh request tenant lain.
3. **Isolasi Context**: Aturan evaluasi tenant A tidak boleh bocor atau dapat diakses oleh tenant B, dan harus dieksekusi dengan memory allocation serendah mungkin (zero-alloc allocation per loop).
4. **Hot Reloading Requirement**: Saat tenant mengubah policy via database, runtime harus beralih ke logika baru tanpa proses restart aplikasi server.

#### Output Deliverables:
- Arsitektur diagram alir eksekusi objek (ASCII).
- Desain pola pemisahan Class vs Object Binding (mengapa tidak boleh memutasi `m_tbl` milik class utama).
- Implementasi solusi menggunakan Ruby (minimal 1 file representasi engine yang mendemonstrasikan evaluasi tenant switcher secara instan tanpa cache invalidation).

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. **Mengapa pemanggilan `method_missing` secara signifikan lebih lambat dibanding pemanggilan method yang terdefinisi via `def` atau `define_method`?**
   - *Jawaban*: `method_missing` memicu traversal penuh dari pointer `klass` melewati seluruh hierarki inheritance (`super`) hingga `BasicObject`. Setelah seluruh rantai gagal menemukan method tersebut, YARV mengulang kembali traversal dari awal untuk mencari implementasi method `method_missing`. Seluruh proses ini tidak dapat dioptimalkan secara penuh oleh Inline Method Cache call site.

2. **Apa yang disimpan dalam pointer `klass` milik sebuah objek instance biasa, dan apa bedanya jika instance tersebut memiliki Singleton Class?**
   - *Jawaban*: Pada instance biasa, pointer `RBasic.klass` menunjuk langsung ke `RClass` dari kelas pembuatnya. Jika instance memiliki singleton class, pointer `klass` diarahkan ke instance singleton class (`#<Class:#<Object>>`), yang mana pointer `super` dari singleton class tersebut barulah menunjuk ke `RClass` aslinya.

3. **Apa perbedaan fungsional utama antara `class_eval` dan `instance_eval`?**
   - *Jawaban*: `instance_eval` mengevaluasi kode dalam konteks instance objek target, mengubah `self` menjadi objek tersebut dan mendefinisikan singleton method pada objek tersebut. `class_eval` (atau `module_eval`) hanya dapat dipanggil pada Class/Module, mengubah `self` menjadi class tersebut, dan mendefinisikan regular instance method yang akan diwariskan ke seluruh instance dari class tersebut.

4. **Kapan Anda harus menggunakan `respond_to_missing?` dan apa dampak arsitektural jika mengabaikannya?**
   - *Jawaban*: Wajib digunakan setiap kali meng-override `method_missing`. Jika diabaikan, `Object#respond_to?` akan mengembalikan `false` meskipun method dapat dieksekusi, yang melanggar kontrak polimorfisme Ruby dan menyebabkan malfungsi pada library serialisasi, dependency injection, dan metaprogramming framework lainnya.

5. **Mengapa `Module#prepend` lebih direkomendasikan daripada `alias_method` untuk arsitektur interception method modern?**
   - *Jawaban*: `Module#prepend` menyisipkan module di depan class target dalam ancestor hierarchy, mempertahankan rantai pemanggilan method asli melalui keyword `super` secara natural, tidak mengubah atau menduplikasi method table asli, dan tidak menimbulkan degradasi debugging stack trace seperti rekursi tak berujung akibat duplikasi nama method pada `alias_method`.

#### 5 Pertanyaan Intermediate
6. **Jelaskan mekanisme kerja Shape Tree pada Ruby 3.2+ dan bagaimana metaprogramming dapat merusak optimasinya.**
   - *Jawaban*: Shape Tree memetakan urutan penambahan instance variable (`@ivar`) sebagai state transisi berbentuk tree global (`shape_id`). Jika sebuah method metaprogramming menambahkan instance variable pada instance dengan urutan acak/tidak konsisten pada runtime, Ruby akan membuat branch baru pada Shape Tree (shape explosion), menyebabkan deoptimasi akses memory cache instance variable (`ivptr` fallback).

7. **Bagaimana `define_method` dapat menyebabkan memory leak jika didefinisikan di dalam scope method lain yang memiliki local variable besar?**
   - *Jawaban*: `define_method` menerima closure (Proc/block) yang mempertahankan seluruh lexical scope (Binding context) tempat ia diciptakan. Jika method pembungkus memiliki local variable besar, referensi memori tersebut tetap dipegang oleh closure method baru selama method tersebut hidup di dalam `m_tbl` kelas, mencegah Garbage Collector mereclaim memori tersebut.

8. **Apa perbedaan arsitektur method lookup antara `include M` vs `extend M` saat dieksekusi di dalam class body?**
   - *Jawaban*: `include M` menyisipkan `M` ke dalam ancestor chain untuk instance class tersebut (tepat di atas class pada `m_tbl`). Sedangkan `extend M` sesungguhnya mengeksekusi `singleton_class.include(M)`, yang menyisipkan `M` ke dalam ancestor chain dari singleton class milik class tersebut, menjadikannya class method.

9. **Apa dampak pemanggilan `eval(string)` terhadap kinerja JIT compiler (MJIT/YJIT) pada Ruby modern?**
   - *Jawaban*: `eval(string)` memaksa runtime menjalankan Ruby parser dan YARV instruction compiler saat runtime, menghasilkan instruction sequences (`iseq`) baru di heap. YJIT tidak dapat mengoptimalkan atau meng-inline block kode dinamis tersebut secara efektif, dan mengeksekusi kode tersebut membatalkan sejumlah invariant machine-code compilation yang telah dibentuk sebelumnya.

10. **Bagaimana cara mencegah evaluasi dynamic DSL memodifikasi atau mengakses instance variable kelas induk evaluator?**
    - *Jawaban*: Mengeksekusi block DSL di dalam konteks instance kelas khusus *Clean Room* (misalnya turunan dari `BasicObject` yang tidak mewarisi `Kernel` atau `Object`), dan meneruskan state secara eksplisit via parameter atau builder pattern tanpa membagikan lexical context class target.

#### 3 Skenario Kasus Produksi
11. **Skenario 1**: Sebuah microservice sistem trading mengalami *P99 latency degradation* dari 3ms melonjak ke 120ms setelah deployment library audit trail baru yang menggunakan metaprogramming. Saat dianalisis, utilisasi CPU mencapai 100% padahal request volume konstan. Apa penyebab internal di level VM dan bagaimana memperbaikinya?
    - *Analisis & Solusi*: Library audit trail memanggil `define_method` atau `class_eval` secara dinamis setiap kali ada request transaksi masuk untuk merekam konteks user. Hal ini secara terus-menerus menaikkan `class_serial` global dan memicu *Global Inline Cache Invalidation Thrashing* pada YARV di seluruh thread. Solusinya: Ubah arsitektur audit trail menggunakan statically prepended module atau context parameter passing, dan freeze seluruh class definition saat aplikasi selesai melakukan proses bootstrapping.

12. **Skenario 2**: Anda menemukan memory footprint worker process Puma naik 100MB setiap 1 jam hingga memicu OOM (Out Of Memory) Killer. Dump heap snapshot menunjukkan jutaan objek bertipe `Symbol` dan `Proc` yang tidak dapat di-GC. Area metaprogramming mana yang harus diaudit pertama kali?
    - *Analisis & Solusi*: Penyebab utama adalah konversi string input eksternal menjadi dynamic symbol via `.to_sym` pada dynamic dispatch (misal: `public_send(params[:action].to_sym)`), atau dynamic generation method tanpa batas menggunakan `define_method` yang menangkap local context (closure leak). Solusinya: Ganti `.to_sym` dengan whitelist lookup menggunakan static string hash comparison, dan pastikan tidak ada sintesis method dinamis berbasis arbitrary user input.

13. **Skenario 3**: Sebuah tim ingin mengimplementasikan sistem enkripsi field database otomatis menggunakan metaprogramming. Setiap kali model membaca attribute (misal: `user.ssn`), data didekripsi secara on-the-fly. Jika menggunakan `method_missing`, performa batch processing 100.000 data sangat lambat. Alternatif metaprogramming apa yang memberikan performa tercepat dan thread-safe?
    - *Analisis & Solusi*: Gunakan metaprogramming pada level class declaration (macro pattern) dengan mendefinisikan method secara langsung via `Module.new` yang di-prepend ke class target saat inisialisasi class:
      ```ruby
      def self.encrypts(attr_name)
        mod = Module.new do
          define_method(attr_name) do
            raw = super()
            EncryptionEngine.decrypt(raw)
          end
        end
        prepend(mod)
      end
      ```
      Pendekatan ini menyisipkan wrapper langsung ke ancestor chain, mendukung YARV Inline Caching, thread-safe karena dieksekusi sebelum aplikasi melayani traffic, dan menghasilkan performa dispatch mendekati native static method.

---

### 16. Summary

1. **Ruby Object Model Structure**: Fondasi eksekusi Ruby MRI berakar pada C struct `RBasic`, `RObject`, dan `RClass`. Navigasi pemanggilan method adalah proses deterministik melintasi pointer `klass` dan `super`, yang mencakup singleton class, prepend wrappers, dan include modules.
2. **YARV Optimization Awareness**: Inline Method Caching adalah kunci performa eksekusi Ruby modern. Modifikasi struktur kelas saat runtime (`define_method`, `alias_method`) membatalkan validitas cache tersebut secara global atau hierarkis via mekanisme `class_serial`, yang berdampak fatal pada sistem ber-throughput tinggi.
3. **Metaprogramming Lifecycle Boundary**: Pisahkan fase aplikasi menjadi dua: **Bootstrapping Phase** (di mana metaprogramming, dynamic module prepending, dan DSL evaluation diizinkan untuk fleksibilitas arsitektur) dan **Execution Phase** (di mana seluruh class hierarki di-*freeze*, hanya eksekusi static method lookup yang diperbolehkan demi latensi stabil dan thread safety absolut).
4. **Clean Abstractions**: Hindari anti-pattern manipulasi lexical scope yang menahan closure memory. Terapkan pemisahan tegas menggunakan DSL clean-room evaluator objects untuk mencegah polusi namespace, maintainability nightmare, serta memory leaks pada aplikasi enterprise berskala besar.